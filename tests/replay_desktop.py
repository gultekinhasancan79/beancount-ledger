"""Ledger Replay — a desktop window that replays saved rollouts and runs live ones.

    python tests/replay_desktop.py           # open the window
    python tests/replay_desktop.py --demo    # also start a local mock model, prefilled, zero cost
    python tests/replay_desktop.py --selftest  # headless: run the mock end to end, print events, exit

No browser. Everything runs on this machine: the window is tkinter (ships with
Python), the model is called through the environment's own client, the tools
are the environment's real tools, and every score on screen comes from the
production scorer (candidate/1) — the same call chain the environment runs at
episode end.

What you can do in the window:
  * Browse every saved run under outputs/evals/ (or open any results.jsonl):
    turns on the left, the ledger diff on the right, the scorer breakdown below.
  * Point the environment at your own OpenAI-compatible endpoint (base URL,
    API key or $ENV_VAR, model name), press Run, and watch the episode as it
    happens: each turn appears when the model answers, each write_ledger is
    diffed and scored the moment it is committed, and the finished rollout is
    saved under outputs/evals/ in vf-eval's own format, so tests/build_replay.py
    can embed it in docs/replay.html afterwards.
  * Tick several tasks and run them as a queue, one after another under the
    same settings; each is its own recorded run.
  * See the results across runs (one row per model, a task x model grid),
    export them with the selected run's timeline to outputs/evals/exports/,
    or copy them as Markdown.
  * Run under a budget other than the shipped one (episode turns, episode
    output tokens): the environment is built the way tests/budget_calibration.py
    builds its looser arm, and the run is recorded and shown as a non-default
    budget so it is never mistaken for a benchmark run.

The API key never leaves this process: it is placed in a per-run environment
variable for the environment's client, sent only to the base URL you typed,
and removed when the run ends. It is not logged and not written to disk.

Generated tasks (train:<n>, eval:<n>, train:<n>:hard) need the evaluator
secret; start the window with PIV_EVAL_SECRET set (and PIV_DEV_UNMANIFESTED=1
when no release manifest is installed — this script is a development
entrypoint under tests/, so that override is honoured). Those rollouts are
scored live through the loaded contract but cannot be re-scored later by
build_replay.py, which embeds them unscored.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import csv
import difflib
import hashlib
import inspect
import json
import os
import queue
import re
import statistics
import sys
import threading
import time
import tkinter as tk
import uuid
from dataclasses import dataclass, field
from tkinter import filedialog, messagebox, ttk
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_replay as br  # noqa: E402  (tests/build_replay.py: transcript walking, offline scoring, task facts)
from beancount_ledger import beancount_ledger as env_mod  # noqa: E402  (the turn cap is a module constant the prompt reads at load)
from beancount_ledger.beancount_ledger import (  # noqa: E402
    PIVEvaluationBatchInvalid,
    digests_of,
    load_environment,
    logical_text,
)
from beancount_ledger.candidate.committed import (  # noqa: E402
    CommittedSubmission,
    ProtocolRejected,
    commit,
    new_receipt,
    reject,
    rejection_result_digest,
    score_committed,
)
from beancount_ledger.candidate.normalise import Accepted, ProtocolFailure, parse_once  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402

EVALS = ROOT / "outputs" / "evals"
EXPORTS = EVALS / "exports"
DEFAULT_TASK = "bank_recon_001"
# The shipped episode budget. A run under any other budget is recorded as such
# (metadata.json "budget") and tagged in the window, so it is never read as a benchmark run.
DEFAULT_MAX_TURNS = int(env_mod.MAX_TURNS)
DEFAULT_EPISODE_TOKENS = int(env_mod.MAX_EPISODE_OUTPUT_TOKENS)
WEIGHT_TARGETS, WEIGHT_RESOLVED = 0.70, 0.30
PENALTIES = [
    ("collateral_damage", "Collateral damage", -0.40, False),
    ("removed_or_altered", "Tampered records", -0.40, False),
    ("merged_events", "Merged events", -0.40, False),
    ("fabricated", "Fabricated entries", -0.40, False),
    ("undocumented", "Undocumented repairs", -0.20, False),
    ("plug_accounts", "Plug accounts", -1.00, True),
]


# --------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------
@dataclass
class Call:
    id: str
    name: str
    args: dict
    result: str | None = None
    revision: int | None = None
    refused: bool = False
    unexecuted: bool = False


@dataclass
class Turn:
    no: int
    kind: str = "turn"          # "turn" | "note"
    role: str = "assistant"
    content: str = ""
    reasoning: str = ""
    calls: list = field(default_factory=list)
    secs: float | None = None
    usage: dict | None = None


@dataclass
class Revision:
    index: int
    turn: int
    text: str
    report: str = ""
    digest: str | None = None
    score: dict | None = None


@dataclass
class Rollout:
    label: str
    task_id: str | None
    model: str
    base_url: str
    turns: list = field(default_factory=list)
    revisions: list = field(default_factory=list)
    reward: float | None = None
    stop: str | None = None
    metrics: dict = field(default_factory=dict)
    tokens: dict = field(default_factory=dict)
    truncated: bool = False
    error: str | None = None
    task: dict | None = None
    live: bool = False
    saved_to: str | None = None
    status: str = ""
    turn_map: dict = field(default_factory=dict)   # live only: model turn index -> displayed turn number


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, str):
        return str(value)
    return value


def score_with_contract(contract, text: str, rollout_id: str, revision: int) -> dict:
    """Score a ledger text against a loaded contract, exactly as the environment would."""
    raw = text.encode("utf-8", errors="strict")
    digests = digests_of(raw, submitted=text)
    outcome = parse_once(logical_text(raw))
    receipt = new_receipt(rollout_id, revision, digests)
    if isinstance(outcome, Accepted):
        return score_committed_object(commit(outcome, contract, receipt))
    if isinstance(outcome, ProtocolFailure):
        return score_committed_object(reject(outcome, contract, receipt))
    return {"reward": 0.0, "outcome": "evaluator_failure", "detail": repr(outcome)[:300]}


def score_committed_object(committed) -> dict:
    """ScoreOutcome.as_dict() plus reward/outcome, for a CommittedSubmission or ProtocolRejected."""
    if isinstance(committed, CommittedSubmission):
        result = score_committed(committed)
        result.verify()
        out = _jsonable(result.as_dict())
        out["reward"] = float(result.total)
        out["outcome"] = "delivered" if result.renderable else "policy_blocked"
        return out
    if isinstance(committed, ProtocolRejected):
        return {"reward": 0.0, "outcome": "protocol_rejected", "reason": str(getattr(committed, "reason", "")),
                "detail": str(getattr(committed, "detail", "")), "result_digest": rejection_result_digest(committed)}
    return {"reward": 0.0, "outcome": "nothing_committed"}


_SCORE_CACHE: dict[tuple, dict] = {}


def score_saved(task_id: str, text: str, rollout_id: str, revision: int) -> dict | None:
    """Offline score for a saved transcript; only hand-authored tasks can be re-scored."""
    if task_id not in REGISTRY:
        return None
    key = (task_id, hashlib.sha256(text.encode("utf-8")).hexdigest())
    if key not in _SCORE_CACHE:
        _SCORE_CACHE[key] = br.score_ledger_text(task_id, text, rollout_id=rollout_id, revision=revision)
    return _SCORE_CACHE[key]


def task_from_contract(contract, task_id: str) -> dict:
    """Task facts for the panels, straight from a loaded contract (works for generated tasks too)."""
    if task_id in REGISTRY:
        return br.task_display(task_id)
    return {
        "id": task_id,
        "scored_accounts": list(contract.scored_accounts),
        "expected_balances": {a: str(v) for a, v in contract.expected_balances},
        "planted": [{"id": p.id, "date": p.date, "description": p.narration,
                     "required_postings": [[a, str(v)] for a, v in p.required],
                     "must_be_payee": list(p.must_be_payee)} for p in contract.planted],
        "traps": [],
    }


def normalize_row(row: dict, label: str, model: str, base_url: str, original: str | None = None) -> Rollout:
    """A vf-eval results row -> Rollout (same revision numbering as build_replay.revisions_of)."""
    comp = row.get("completion") or []
    task_id = (row.get("info") or {}).get("task_id") or row.get("answer")
    turns: list[Turn] = []
    revisions = [Revision(0, 0, "")]
    rev, i, turn_no = 0, 0, 0
    while i < len(comp):
        msg = comp[i]
        if msg.get("role") != "assistant":
            turn_no += 1
            turns.append(Turn(turn_no, kind="note", role=msg.get("role", "?"), content=str(msg.get("content") or "")))
            i += 1
            continue
        turn_no += 1
        calls = [Call(c["id"], c["name"], c["args"]) for c in (br._decode_call(tc) for tc in (msg.get("tool_calls") or []))]
        i += 1
        results = {}
        while i < len(comp) and comp[i].get("role") == "tool":
            results[comp[i].get("tool_call_id")] = comp[i].get("content")
            i += 1
        for c in calls:
            c.result = results.get(c.id)
            if c.result is None:
                c.unexecuted = True
            if c.name == "write_ledger":
                att = br._attestation(c.result)
                if att and att.get("committed"):
                    rev += 1
                    lines = (c.result or "").split("\n")
                    content = c.args.get("content")
                    revisions.append(Revision(rev, turn_no, content if isinstance(content, str) else "",
                                              report="\n".join(lines[1:]), digest=att.get("logical_text_digest")))
                    c.revision = rev
                elif isinstance(c.result, str):
                    c.refused = True
            if c.name == "submit" and isinstance(c.result, str) and not c.result.lower().startswith("submitted"):
                c.refused = True
        turns.append(Turn(turn_no, content=str(msg.get("content") or ""), reasoning=str(msg.get("reasoning_content") or ""), calls=calls))
    spans = (((row.get("timing") or {}).get("model") or {}).get("spans")) or []
    si = 0
    for t in turns:
        if t.kind == "turn":
            t.secs = spans[si].get("duration") if si < len(spans) and isinstance(spans[si], dict) else None
            si += 1
    if original is None:
        if task_id in REGISTRY:
            original = br.contract_for(task_id)[1].original_text
        else:
            original = ""
            for t in turns:
                for c in t.calls:
                    if c.name == "read_file" and c.args.get("path") == "ledger.beancount" and isinstance(c.result, str) and c.result.startswith("option "):
                        original = c.result
                        break
                if original:
                    break
    revisions[0].text = original
    r = Rollout(label=label, task_id=task_id, model=model, base_url=base_url, turns=turns, revisions=revisions,
                reward=row.get("reward"), stop=row.get("stop_condition"), metrics=row.get("metrics") or {},
                tokens=row.get("token_usage") or {}, truncated=bool(row.get("is_truncated")), error=row.get("error"),
                task=br.task_display(task_id) if task_id in REGISTRY else {"id": task_id, "planted": [], "traps": [], "scored_accounts": [], "expected_balances": {}})
    if task_id in REGISTRY:
        rid = f"replay:{label}"
        for rv in r.revisions:
            rv.score = score_saved(task_id, rv.text, rid, rv.index) if rv.text else None
    return r


def load_saved_runs() -> list[Rollout]:
    out = []
    for run in br.discover_runs():
        for idx, row in enumerate(run["rows"]):
            label = f"{run['model'].split('/')[-1]} · {run['id']} · rollout {idx + 1}/{len(run['rows'])}"
            try:
                r = normalize_row(row, label, run["model"], run.get("base_url", ""))
            except Exception as exc:  # noqa: BLE001 - one bad row must not hide the others
                r = Rollout(label=label + " (unreadable)", task_id=None, model=run["model"], base_url="", error=str(exc))
            r.saved_to = run["dir"]
            out.append(r)
    return out


def load_results_file(path: Path) -> list[Rollout]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    meta_path = path.parent / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    model = meta.get("model") or path.parent.parent.name
    return [normalize_row(row, f"{model.split('/')[-1]} · {path.parent.name} · rollout {i + 1}/{len(rows)}", model, meta.get("base_url", ""))
            for i, row in enumerate(rows)]


# --------------------------------------------------------------------------
# diff + markers
# --------------------------------------------------------------------------
def split_lines(text: str) -> list[str]:
    if not text:
        return []
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # the scorer reads logical text; diff the same thing
    lines = text.split("\n")
    if lines and lines[-1] == "" and text.endswith("\n"):
        lines.pop()
    return lines


def diff_lines(a_text: str, b_text: str) -> list[tuple]:
    """[(tag, a_index|None, b_index|None, line)] with tag in ' ', '+', '-'."""
    a, b = split_lines(a_text), split_lines(b_text)
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                ops.append((" ", i1 + k, j1 + k, a[i1 + k]))
        else:
            for k in range(i1, i2):
                ops.append(("-", k, None, a[k]))
            for k in range(j1, j2):
                ops.append(("+", None, k, b[k]))
    return ops


_TXN_HEAD = re.compile(r"^\d{4}-\d{2}-\d{2}\s+(\*|!|txn|[A-Z])")
_NON_TXN = re.compile(r"^\d{4}-\d{2}-\d{2}\s+(open|close|balance|pad|note|document|event|price|commodity)\b")


def txn_blocks(lines: list[str]) -> list[dict]:
    blocks = []
    for i, line in enumerate(lines):
        if _TXN_HEAD.match(line) and not _NON_TXN.match(line):
            j = i
            while j + 1 < len(lines) and re.match(r"^\s+\S", lines[j + 1]):
                j += 1
            blocks.append({"start": i, "end": j, "head": line, "body": lines[i:j + 1]})
    return blocks


def find_planted_blocks(lines: list[str], planted: list[dict]) -> dict:
    found = {}
    blocks = txn_blocks(lines)
    for p in planted or []:
        for b in blocks:
            if not b["head"].startswith(str(p.get("date", "")) + " "):
                continue
            need = [rp[0] for rp in p.get("required_postings", [])]
            if all(any(re.match(r"^\s+" + re.escape(acct) + r"(\s|$)", ln) for ln in b["body"]) for acct in need):
                found[p["id"]] = b
                break
    return found


def find_trap_blocks(lines: list[str], traps: list[dict]) -> dict:
    found = {}
    blocks = txn_blocks(lines)
    for t in traps or []:
        for b in blocks:
            if t.get("narration") and t["narration"] in b["head"]:
                found[t["id"]] = b
                break
    return found


KEY_VAR_RE = re.compile(r"(API_?KEY|_KEY|_TOKEN|_SECRET)$", re.IGNORECASE)
PROVIDER_URLS = {  # a base URL to suggest when a key variable is picked; OpenAI-compatible chat completions only
    "NVIDIA_API_KEY": "https://integrate.api.nvidia.com/v1",
    "OPENAI_API_KEY": "https://api.openai.com/v1",
    "OPENROUTER_API_KEY": "https://openrouter.ai/api/v1",
    "GROQ_API_KEY": "https://api.groq.com/openai/v1",
    "MISTRAL_API_KEY": "https://api.mistral.ai/v1",
    "TOGETHER_API_KEY": "https://api.together.xyz/v1",
    "DEEPSEEK_API_KEY": "https://api.deepseek.com/v1",
    "FIREWORKS_API_KEY": "https://api.fireworks.ai/inference/v1",
    "CEREBRAS_API_KEY": "https://api.cerebras.ai/v1",
    "XAI_API_KEY": "https://api.x.ai/v1",
    "GEMINI_API_KEY": "https://generativelanguage.googleapis.com/v1beta/openai",
    "ANTHROPIC_API_KEY": "https://api.anthropic.com/v1",
    "PRIME_API_KEY": "https://api.pinference.ai/api/v1",
    "HF_TOKEN": "https://router.huggingface.co/v1",
}


def _registry_env() -> dict[str, str]:
    """User-level environment variables as Windows stores them (HKCU\\Environment), so a key set
    after this shell was opened is still found. Empty elsewhere."""
    if sys.platform != "win32":
        return {}
    try:
        import winreg  # noqa: PLC0415
        out = {}
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            i = 0
            while True:
                try:
                    name, value, _kind = winreg.EnumValue(k, i)
                except OSError:
                    break
                if isinstance(value, str):
                    out[name] = value
                i += 1
        return out
    except OSError:
        return {}


def known_key_vars() -> list[dict]:
    """Names (never values) of environment variables on this PC that look like API keys."""
    names = set(os.environ) | set(_registry_env())
    out = []
    for name in sorted(names, key=str.upper):
        if name.upper().startswith(("PIV_", "CLAUDE_CODE_")) or not KEY_VAR_RE.search(name):
            continue  # our own secrets and tooling tokens are not model-provider keys
        out.append({"name": name, "base_url": PROVIDER_URLS.get(name.upper(), "")})
    return out


def resolve_env_value(name: str) -> str | None:
    """The value behind $NAME: the process environment first, then the user's registry environment."""
    return os.environ.get(name) or _registry_env().get(name)


def list_models(base_url: str, api_key: str, timeout: float = 20.0) -> dict:
    """GET <base_url>/models on an OpenAI-compatible endpoint; ids only, the key never leaves this process."""
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    key = resolve_env_value(api_key[1:].strip()) if api_key.startswith("$") else api_key
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return {"models": [], "error": "type a base URL first"}
    if api_key.startswith("$") and not key:
        return {"models": [], "error": f"environment variable {api_key[1:]} is not set on this PC"}
    url = base + "/models"

    def redact(text: str) -> str:
        return text.replace(key, "***") if key and len(key) > 3 else text

    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key or 'EMPTY'}", "Accept": "application/json", "User-Agent": "ledger-replay"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - the user typed this URL
            body = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            pass
        return {"models": [], "error": redact(f"HTTP {exc.code} from {url}" + (f": {detail}" if detail else ""))}
    except Exception as exc:  # noqa: BLE001
        return {"models": [], "error": redact(f"{type(exc).__name__}: {exc}")}
    items = body.get("data") if isinstance(body, dict) else body
    if not isinstance(items, list):
        return {"models": [], "error": f"unexpected reply from {url}: no model list"}
    ids = {str(m.get("id") or m.get("name")) for m in items if isinstance(m, dict) and (m.get("id") or m.get("name"))}
    return {"models": sorted(ids, key=str.lower), "url": url}


class signal_tolerant:
    """Let the environment be built off the main thread.

    verifiers' Environment registers SIGINT/SIGTERM teardown handlers in
    __post_init__, which Python allows only on the main thread. A window's
    JS-bridge calls run on worker threads, so inside this block signal.signal
    becomes a no-op there; Ctrl+C teardown is irrelevant for a GUI process.
    """

    def __enter__(self):
        import signal  # noqa: PLC0415
        self._signal, self._orig = signal, signal.signal
        if threading.current_thread() is not threading.main_thread():
            signal.signal = lambda *_a, **_k: None
        return self

    def __exit__(self, *exc):
        self._signal.signal = self._orig
        return False


def summarize_reply(resp, sampling_args=None) -> dict:
    """finish reason, usage and which message fields were filled — the facts behind an empty reply."""
    choice = (getattr(resp, "choices", None) or [None])[0]
    msg = getattr(choice, "message", None)
    usage = getattr(resp, "usage", None)
    details = getattr(usage, "completion_tokens_details", None)
    extra = getattr(msg, "model_extra", None) or {}
    reasoning = None
    for name in ("reasoning_content", "reasoning", "reasoning_details"):
        val = getattr(msg, name, None) or extra.get(name)
        if val:
            reasoning = name
            break
    content = getattr(msg, "content", None)
    return {
        "model": getattr(resp, "model", None),
        "finish_reason": getattr(choice, "finish_reason", None),
        "content_chars": len(content) if isinstance(content, str) else (len(content) if isinstance(content, list) else 0),
        "tool_calls": len(getattr(msg, "tool_calls", None) or []),
        "reasoning_field": reasoning,
        "refusal": bool(getattr(msg, "refusal", None)),
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "reasoning_tokens": getattr(details, "reasoning_tokens", None) if details is not None else None,
        "max_tokens_sent": (sampling_args or {}).get("max_tokens") or (sampling_args or {}).get("max_completion_tokens"),
    }


def explain_provider_error(chain: str | None, reply: dict | None = None, retries: int | None = None) -> str | None:
    """The provider's error, what its last reply looked like, plus a plain hint for the usual suspects.

    `retries` is how many times the client retried a request before giving up; it
    only feeds the wording of the overloaded-endpoint hint.
    """
    if not chain and not reply:
        return None
    text = str(chain or "the provider answered, but the environment could not use the reply")
    low = text.lower()
    hint = None
    retried = f"the app retried {retries} time{'s' if retries != 1 else ''}" if retries is not None else "the app retried"
    if reply and ("emptymodelresponse" in low or "no content" in low):
        fr, ct, rt, cap = reply.get("finish_reason"), reply.get("completion_tokens"), reply.get("reasoning_tokens"), reply.get("max_tokens_sent")
        text += (f"  ·  last reply: finish_reason={fr}, content {reply.get('content_chars', 0)} chars, {reply.get('tool_calls', 0)} tool calls, "
                 f"reasoning field {reply.get('reasoning_field') or 'none'}, completion tokens {ct}" + (f" (reasoning {rt})" if rt else "") + (f", cap {cap}" if cap else ""))
        if fr == "length":
            hint = "the model used its whole per-turn token cap before producing anything visible (hidden thinking?): raise Tokens / turn, or pick a model that returns its reasoning in reasoning_content, or a non-reasoning model"
        elif fr == "content_filter":
            hint = "the provider's content filter blocked the reply"
        elif reply.get("refusal"):
            hint = "the model refused the request"
        else:
            hint = "the model answered with an empty message: it probably does not do tool calling in this mode; pick a model that supports function calling (the committed runs used nvidia/nemotron-3-ultra-550b-a55b)"
    elif "401" in low or "unauthorized" in low or "authentication" in low:
        hint = "the endpoint rejected the key (401): check the key or pick another one"
    elif "403" in low or "permission" in low:
        hint = "the key is valid but not allowed to use this model (403)"
    elif "404" in low and ("model" in low or "not found" in low):
        hint = "no such model at this endpoint (404): pick one from the model list"
    elif "413" in low or "tokens per minute" in low or "request too large" in low or ("tpm" in low and "limit" in low):
        # Groq's free tier (and others like it) caps tokens per minute below one turn's observation
        hint = ("the provider's free tier cannot carry a 12k-token observation per turn (413 / tokens-per-minute limit): "
                "pick another endpoint or a paid tier")
    elif "504" in low or "too many requests" in low or "overloaded" in low or "gateway" in low:
        hint = f"the endpoint is overloaded (504 / Too Many Requests); {retried} and gave up — wait and run it again, or pick another endpoint"
    elif "429" in low or "rate limit" in low or "quota" in low:
        hint = "rate limited or out of quota (429): wait a moment or use another key"
    elif "content" in low and "valid string" in low and ("none" in low or "null" in low):
        hint = "the provider rejects a replayed assistant message whose content is null (a reasoning-only turn); the window now sends an empty string instead, so run it again"
    elif "reasoning_content" in low or ("reasoning" in low and ("unknown" in low or "unexpected" in low or "extra" in low or "unsupported" in low)):
        hint = "this provider rejects the replayed reasoning_content field: turn off 'Replay hidden reasoning' and run again"
    elif ("400" in low or "invalid" in low or "schema" in low) and ("'properties'" in low or "properties" in low or "'required'" in low or "required" in low or "strict" in low) and ("tool" in low or "schema" in low or "function" in low or "properties" in low):
        # Groq validates tool schemas strictly: a parameterless tool with `required: []` and no
        # `properties`, or a strict tool whose optional argument was omitted, is refused with a 400
        hint = "this provider validates the tool schema strictly (400 naming properties/required/strict): tick 'Strict-schema provider (Groq)' and run again"
    elif ("finish_reason" in low or "service_tier" in low) and ("literal" in low or "validation" in low or "input should be" in low or "unexpected value" in low):
        hint = ("the endpoint's OpenAI compatibility is partial: it answered with a finish_reason or service_tier the SDK does not know; "
                "the app accepts any value there now, so run it again")
    elif ("tool" in low or "function" in low) and ("support" in low or "invalid" in low or "400" in low):
        hint = "this model does not accept tool definitions (400): the environment needs a model with function calling"
    elif "connection" in low or "connect" in low or "timeout" in low or "timed out" in low:
        hint = "could not reach the base URL: check the address (it must end with /v1 for most providers) and your network"
    elif "context" in low and ("length" in low or "window" in low):
        hint = "the request exceeded the model's context window: lower max tokens per turn or pick a larger model"
    return f"{text[:700]}" + (f"  →  {hint}" if hint else "")


def _rmdir_if_empty(path: Path) -> None:
    try:
        if path.exists() and path != EVALS and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


# --------------------------------------------------------------------------
# provider shims (ported from tests/budget_calibration.py)
# --------------------------------------------------------------------------
_LITERALS_RELAXED = False


def relax_response_literals() -> None:
    """Accept any string for two closed literals in the OpenAI SDK's response models.

    Groq answers `service_tier: "on_demand"`, Gemini a `finish_reason` of its own;
    the reply is otherwise a normal completion, and the SDK would reject it with a
    validation error before the environment saw a single token. Process-wide,
    applied once; the environment's own contract is untouched.
    """
    global _LITERALS_RELAXED
    if _LITERALS_RELAXED:
        return
    from typing import Optional  # noqa: PLC0415
    from openai.types.chat import chat_completion as _cc  # noqa: PLC0415
    for model, name in ((_cc.ChatCompletion, "service_tier"), (_cc.Choice, "finish_reason")):
        if name in model.model_fields:
            model.model_fields[name].annotation = Optional[str]
            model.model_rebuild(force=True)
    _LITERALS_RELAXED = True


def shim_tool_schemas(native):
    """A copy of the tool definitions that a strict-schema provider (Groq) accepts.

    A parameterless tool whose schema carries `required: []` beside an empty
    `properties` is refused ("'required' present but 'properties' is missing"), and
    a strict tool whose optional argument the model omitted (read_file offset/limit)
    is refused under strict validation. The copy gets an explicit empty `properties`,
    loses the empty `required`, and is sent with strict=false. Only the wire copy
    changes: the environment's contract objects are never touched (deep copy), and
    the run's metadata records that this shim was on.
    """
    native = copy.deepcopy(native)
    for tool in native or []:
        fn = tool.get("function") if isinstance(tool, dict) else getattr(tool, "function", None)
        params = fn.get("parameters") if isinstance(fn, dict) else getattr(fn, "parameters", None)
        if isinstance(params, dict):
            params.setdefault("properties", {})
            if not params["properties"] and params.get("required") == []:
                params.pop("required")
        if isinstance(fn, dict) and fn.get("strict"):
            fn["strict"] = False
        elif fn is not None and not isinstance(fn, dict) and getattr(fn, "strict", None):
            try:
                fn.strict = False
            except (AttributeError, TypeError, ValueError):
                pass
    return native


# --------------------------------------------------------------------------
# episode budget
# --------------------------------------------------------------------------
def budget_from_cfg(cfg: dict) -> dict:
    """{max_turns, max_episode_output_tokens, default}: the budget a run is built under."""
    turns = int(cfg.get("max_turns") or DEFAULT_MAX_TURNS)
    tokens = int(cfg.get("max_episode_tokens") or DEFAULT_EPISODE_TOKENS)
    if turns < 2 or tokens < 1000:
        raise ValueError(f"budget out of range: {turns} turns / {tokens} episode tokens (need at least 2 turns and 1,000 tokens)")
    return {"max_turns": turns, "max_episode_output_tokens": tokens,
            "default": turns == DEFAULT_MAX_TURNS and tokens == DEFAULT_EPISODE_TOKENS}


def load_environment_with_budget(task_id: str, budget: dict, timeout_seconds: float):
    """load_environment under a budget, the way tests/budget_calibration.py builds its looser arm.

    The turn cap is a module constant that the prompt reads while the environment
    is built (and the contract digest is computed and cached in the same call), so
    it is raised only around that call and put back right after.
    """
    previous = env_mod.MAX_TURNS
    env_mod.MAX_TURNS = int(budget["max_turns"])
    try:
        return load_environment(task_id, timeout_seconds=timeout_seconds, max_episode_output_tokens=int(budget["max_episode_output_tokens"]))
    finally:
        env_mod.MAX_TURNS = previous


# --------------------------------------------------------------------------
# results across runs: the same files the replay reads, aggregated
# --------------------------------------------------------------------------
def _row_facts(row: dict) -> dict:
    metrics = row.get("metrics") or {}
    usage = row.get("token_usage") or {}
    turns = metrics.get("num_turns")
    if turns is None:
        turns = sum(1 for m in (row.get("completion") or []) if isinstance(m, dict) and m.get("role") == "assistant")
    reward = row.get("reward")
    failed = reward is None or row.get("stop_condition") == "has_error" or bool(row.get("error"))
    return {"task": (row.get("info") or {}).get("task_id") or row.get("answer") or "?",
            "reward": None if failed else float(reward), "stop": row.get("stop_condition"),
            "turns": int(round(float(turns))) if turns is not None else None,
            "output_tokens": usage.get("output_tokens") if usage.get("output_tokens") is not None else usage.get("completion_tokens"),
            "failed": failed}


def _read_run_dir(run_dir: Path, quarantined: bool, evals: Path) -> dict:
    meta_path, results = run_dir / "metadata.json", run_dir / "results.jsonl"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except (OSError, ValueError):
        meta = {}
    rows = []
    if results.exists():
        for line in results.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    folder = run_dir.parent.name
    model = meta.get("model") or (folder.split("--", 1)[1].replace("--", "/") if "--" in folder else folder)
    return {"id": run_dir.name, "dir": str(run_dir.relative_to(evals.parent.parent)).replace("\\", "/") if evals.parent.parent in run_dir.parents else str(run_dir),
            "model": model, "rows": rows, "quarantined": quarantined,
            "budget": meta.get("budget"), "desktop": meta.get("replay_desktop"), "time": meta.get("time")}


def load_run_records(evals: Path = EVALS) -> list[dict]:
    """Every run folder under outputs/evals — scored ones and the quarantined ones set aside — as
    {id, dir, model, rows, quarantined, budget, desktop}. Nothing is scored here."""
    if not evals.exists():
        return []
    records = [_read_run_dir(r.parent, False, evals) for r in sorted(evals.glob("*/*/results.jsonl")) if r.parent.parent.name not in ("quarantined", "exports")]
    records += [_read_run_dir(m.parent, True, evals) for m in sorted((evals / "quarantined").glob("*/*/metadata.json"))]
    return records


def _median(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    m = statistics.median(values)
    return int(m) if float(m).is_integer() else m   # 8, not 8.0, in a table of turn counts


def summarize_runs(records: list[dict]) -> dict:
    """One row per model (runs, mean reward, strict-solve rate, medians, failed) and a task × model reward grid."""
    models: dict[str, dict] = {}
    tasks: dict[str, dict] = {}
    for rec in records:
        name = rec.get("model") or "?"
        m = models.setdefault(name, {"rollouts": [], "failed": 0, "non_default_budget": 0})
        budget = rec.get("budget") or {}
        non_default = bool(budget) and not budget.get("default", True)
        if rec.get("quarantined"):
            m["failed"] += max(1, len(rec.get("rows") or []))
            continue
        for row in rec.get("rows") or []:
            f = _row_facts(row)
            if f["failed"]:
                m["failed"] += 1
                continue
            if non_default:
                m["non_default_budget"] += 1
            m["rollouts"].append(f)
            tasks.setdefault(f["task"], {}).setdefault(name, []).append(f["reward"])
    out_models = []
    for name in sorted(models, key=str.lower):
        rs = models[name]["rollouts"]
        rewards = [r["reward"] for r in rs]
        strict = sum(1 for r in rewards if r == 1.0)
        out_models.append({"model": name, "runs": len(rs), "failed": models[name]["failed"],
                           "mean_reward": statistics.mean(rewards) if rewards else None,
                           "strict": strict, "strict_rate": strict / len(rewards) if rewards else None,
                           "median_turns": _median(r["turns"] for r in rs),
                           "median_output_tokens": _median(r["output_tokens"] for r in rs),
                           "non_default_budget": models[name]["non_default_budget"]})
    order = [m["model"] for m in out_models]
    out_tasks = [{"task": t, "cells": {name: {"reward": statistics.mean(v), "n": len(v), "strict": sum(1 for x in v if x == 1.0)}
                                        for name, v in tasks[t].items()}} for t in sorted(tasks)]
    return {"models": out_models, "model_order": order, "tasks": out_tasks, "records": len(records),
            "rollouts": sum(m["runs"] for m in out_models), "failed": sum(m["failed"] for m in out_models)}


def _f3(v):
    return "–" if v is None else f"{float(v):.3f}"


def _pct(v):
    return "–" if v is None else f"{100 * float(v):.0f}%"


def _n(v):
    return "–" if v is None else f"{int(round(float(v))):,}"


def summary_markdown(summary: dict, timeline: dict | None = None) -> str:
    """The summary (and, when given, one run's turn timeline) as GitHub-flavoured Markdown tables."""
    out = ["## Results by model", "",
           "| Model | Runs | Mean reward | Strict solves | Median turns | Median output tokens | Failed / quarantined | Non-default budget |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for m in summary.get("models") or []:
        out.append(f"| {m['model']} | {m['runs']} | {_f3(m['mean_reward'])} | {m['strict']} ({_pct(m['strict_rate'])}) | {_n(m['median_turns'])} | "
                   f"{_n(m['median_output_tokens'])} | {m['failed']} | {m['non_default_budget'] or ''} |")
    if not summary.get("models"):
        out.append("| (no scored runs) | | | | | | | |")
    order = summary.get("model_order") or []
    out += ["", "## Reward by task", ""]
    if summary.get("tasks") and order:
        out.append("| Task | " + " | ".join(order) + " |")
        out.append("|---|" + "---:|" * len(order))
        for t in summary["tasks"]:
            cells = []
            for name in order:
                c = t["cells"].get(name)
                cells.append(f"{_f3(c['reward'])} (n={c['n']})" if c else "–")
            out.append(f"| {t['task']} | " + " | ".join(cells) + " |")
    else:
        out.append("(no tasks with scored runs)")
    if timeline:
        head = f"{timeline.get('model', '?')} on {timeline.get('task', '?')}"
        if timeline.get("run_id"):
            head += f" (run {timeline['run_id']})"
        out += ["", f"## Turn timeline — {head}", ""]
        facts = [f"reward {_f3(timeline.get('reward'))}"]
        if timeline.get("stop"):
            facts.append(f"stop {timeline['stop']}")
        if timeline.get("budget") and not (timeline["budget"] or {}).get("default", True):
            b = timeline["budget"]
            facts.append(f"non-default budget: {b.get('max_turns')} turns / {_n(b.get('max_episode_output_tokens'))} episode tokens")
        out += [" · ".join(facts), "", "| Turn | Kind | Tool calls | Ledger | Score after | Time |", "|---:|---|---|---|---:|---:|"]
        for r in timeline.get("rows") or []:
            secs = "" if r.get("secs") is None else f"{float(r['secs']):.1f} s"
            out.append(f"| {r.get('turn', '')} | {r.get('kind', '')} | {r.get('tools', '')} | {r.get('ledger', '')} | {_f3(r.get('score'))} | {secs} |")
    return "\n".join(out) + "\n"


def write_exports(summary: dict, timeline: dict | None = None, exports_dir: Path = EXPORTS, stamp: str | None = None) -> dict:
    """Write <stamp>.md and <stamp>.csv under outputs/evals/exports; returns their paths (LF line endings, UTF-8)."""
    exports_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    md_path, csv_path = exports_dir / f"{stamp}.md", exports_dir / f"{stamp}.csv"
    md_path.write_text(summary_markdown(summary, timeline), encoding="utf-8", newline="\n")
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        # three blocks, each with its own header row: a person opens this in a spreadsheet
        w.writerow(["model", "runs", "mean_reward", "strict_solves", "strict_rate", "median_turns", "median_output_tokens", "failed_or_quarantined", "non_default_budget_runs"])
        for m in summary.get("models") or []:
            w.writerow([m["model"], m["runs"], "" if m["mean_reward"] is None else f"{m['mean_reward']:.6f}", m["strict"],
                        "" if m["strict_rate"] is None else f"{m['strict_rate']:.4f}", "" if m["median_turns"] is None else m["median_turns"],
                        "" if m["median_output_tokens"] is None else m["median_output_tokens"], m["failed"], m["non_default_budget"]])
        w.writerow([])
        order = summary.get("model_order") or []
        w.writerow(["task"] + order)
        for t in summary.get("tasks") or []:
            w.writerow([t["task"]] + [(f"{t['cells'][n]['reward']:.6f}" if n in t["cells"] else "") for n in order])
        if timeline:
            w.writerow([])
            w.writerow(["run_id", "model", "task", "reward", "stop", "max_turns", "max_episode_output_tokens"])
            b = timeline.get("budget") or {}
            w.writerow([timeline.get("run_id", ""), timeline.get("model", ""), timeline.get("task", ""), "" if timeline.get("reward") is None else timeline["reward"],
                        timeline.get("stop", ""), b.get("max_turns", ""), b.get("max_episode_output_tokens", "")])
            w.writerow(["turn", "kind", "tool_calls", "ledger", "score_after", "secs"])
            for r in timeline.get("rows") or []:
                w.writerow([r.get("turn", ""), r.get("kind", ""), r.get("tools", ""), r.get("ledger", ""), "" if r.get("score") is None else r["score"], "" if r.get("secs") is None else r["secs"]])
    rel = lambda p: str(p.relative_to(ROOT)).replace("\\", "/") if ROOT in p.parents else str(p)  # noqa: E731
    return {"md": rel(md_path), "csv": rel(csv_path)}


def copy_to_clipboard(text: str) -> str:
    """Put text on the system clipboard from Python; returns which route did it.

    Windows: the Win32 clipboard through ctypes (survives this process). Elsewhere:
    a throw-away Tk root — on macOS the pasteboard keeps the text; on X11 the
    selection belongs to the Tk root and may go with it, a Tk limitation.
    """
    if sys.platform == "win32":
        _win32_set_clipboard(text)
        return "Windows clipboard"
    root = tk.Tk()
    try:
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    finally:
        root.destroy()
    return "Tk clipboard"


def _win32_set_clipboard(text: str) -> None:
    import ctypes  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not user32.OpenClipboard(None):
        raise OSError("the clipboard is held by another application")
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
        if not handle:
            raise OSError("GlobalAlloc failed")
        ptr = kernel32.GlobalLock(handle)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(13, handle):  # CF_UNICODETEXT; the system owns the handle from here
            raise OSError("SetClipboardData failed")
    finally:
        user32.CloseClipboard()


# --------------------------------------------------------------------------
# live engine
# --------------------------------------------------------------------------
class LiveRun:
    """One live episode: env built on the calling (main) thread, rollout on a worker thread.

    Events (dicts with a "type") go to `events`: start, revision, assistant, tools,
    done, stopped, error.
    """

    def __init__(self, cfg: dict, events: queue.Queue):
        self.cfg = cfg
        self.events = events
        self.env = None
        self.loop = None
        self.task = None
        self.thread = None
        self.rollout_id = "live"
        self._last_secs = None
        self.results_path = None
        self.budget = None
        self.finished = False   # a terminal event (done / stopped / error) has been emitted

    def emit(self, **ev):
        secret = getattr(self, "_secret", "")
        if secret and len(secret) > 3:
            for k in ("message", "quarantined", "cause"):
                if isinstance(ev.get(k), str):
                    ev[k] = ev[k].replace(secret, "***")
        if ev.get("type") in ("done", "stopped", "error"):
            self.finished = True
        self.events.put(ev)

    def start(self):
        cfg = self.cfg
        self.budget = budget_from_cfg(cfg)
        env = load_environment_with_budget(cfg["task"], self.budget, timeout_seconds=float(cfg.get("timeout", 1800)))
        env.env_id = "beancount-ledger"
        env.env_args = {} if cfg["task"] == DEFAULT_TASK else {"task_id": cfg["task"]}
        self.env = env
        original = logical_text(env.public_files["ledger.beancount"])
        task = task_from_contract(env.contract, cfg["task"])
        self.emit(type="start", task=task, original=original, model=cfg["model"], base_url=cfg["base_url"],
                  system_prompt=getattr(env, "system_prompt", ""), budget=self.budget,
                  strict_schema=bool(cfg.get("strict_schema")), contract_digest=getattr(env, "_episode_contract_digest", None))
        self.emit(type="revision", revision=0, turn=0, text=original, report="", digest=None,
                  score=score_with_contract(env.contract, original, "live", 0))
        self._install_hooks(env)
        if cfg.get("save", True):
            safe = re.sub(r"[^A-Za-z0-9._-]+", "--", cfg["model"].replace("/", "--")).strip("-") or "model"
            self.results_path = EVALS / f"beancount-ledger--{safe}" / uuid.uuid4().hex[:8]
        self.thread = threading.Thread(target=self._worker, name="ledger-replay-rollout", daemon=True)
        self.thread.start()

    def _install_hooks(self, env):
        run = self
        orig_gmr = env.get_model_response

        async def get_model_response(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return await orig_gmr(*args, **kwargs)
            finally:
                run._last_secs = time.perf_counter() - t0
        env.get_model_response = get_model_response

        orig_ats = env.add_trajectory_step

        def after_step(state, step):
            try:
                msg = step["completion"][-1]
                resp = step.get("response")
                usage = getattr(resp, "usage", None)
                run.emit(type="assistant", turn=len(state["trajectory"]),
                         content=getattr(msg, "content", "") or "",
                         reasoning=getattr(msg, "reasoning_content", "") or "",
                         tool_calls=[{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in (getattr(msg, "tool_calls", None) or [])],
                         usage={"prompt_tokens": getattr(usage, "prompt_tokens", None), "completion_tokens": getattr(usage, "completion_tokens", None),
                                "reasoning_tokens": getattr(usage, "reasoning_tokens", None)} if usage else None,
                         finish_reason=getattr(getattr(resp, "message", None), "finish_reason", None),
                         truncated=bool(step.get("is_truncated")), secs=run._last_secs)
            except Exception as exc:  # noqa: BLE001 - never let the viewer break the rollout
                run.emit(type="log", message=f"assistant hook: {exc!r}")

        if inspect.iscoroutinefunction(orig_ats):
            async def add_trajectory_step(state, step):
                r = await orig_ats(state, step)
                after_step(state, step)
                return r
        else:
            def add_trajectory_step(state, step):
                r = orig_ats(state, step)
                after_step(state, step)
                return r
        env.add_trajectory_step = add_trajectory_step

        orig_er = env.env_response

        async def env_response(messages, state, **kwargs):
            rev_before = state.get("piv_revision", 0)
            replies = await orig_er(messages, state, **kwargs)
            try:
                run.rollout_id = state.get("piv_rollout_id", run.rollout_id)
                phase = state.get("piv_phase")
                phase = getattr(phase, "value", str(phase)) if phase is not None else None
                results = [{"role": getattr(m, "role", "tool"), "tool_call_id": getattr(m, "tool_call_id", None), "content": getattr(m, "content", "") or ""} for m in (replies or [])]
                rev_now = state.get("piv_revision", 0)
                if rev_now > rev_before:
                    text = ""
                    for tc in (getattr(messages[-1], "tool_calls", None) or []):
                        if tc.name == "write_ledger":
                            try:
                                text = json.loads(tc.arguments).get("content", "")
                            except (json.JSONDecodeError, AttributeError):
                                text = ""
                    report, digest = "", None
                    for r_ in results:
                        att = br._attestation(r_["content"])
                        if att and att.get("committed"):
                            report = "\n".join(r_["content"].split("\n")[1:])
                            digest = att.get("logical_text_digest")
                    run.emit(type="revision", revision=rev_now, turn=state.get("piv_turn"), text=text, report=report, digest=digest,
                             score=score_committed_object(state.get("piv_committed")))
                run.emit(type="tools", turn=state.get("piv_turn"), results=results, revision=rev_now, phase=phase,
                         final=state.get("final_env_response") is not None)
            except Exception as exc:  # noqa: BLE001
                run.emit(type="log", message=f"tools hook: {exc!r}")
            return replies
        env.env_response = env_response

    def _worker(self):
        try:
            self._worker_body()
        except BaseException as exc:  # noqa: BLE001 - the window must always hear how a run ended
            self.emit(type="error", message=f"{type(exc).__name__}: {exc}")
            self._discard_empty_run()

    def _worker_body(self):
        from verifiers.legacy.clients.openai_chat_completions_client import OpenAIChatCompletionsClient  # noqa: PLC0415
        from verifiers.legacy.types import ClientConfig  # noqa: PLC0415 - keep import cost off the UI thread

        diag = self._diag = {}
        run_cfg = self.cfg
        try:
            relax_response_literals()   # always: a non-standard finish_reason/service_tier must not void a good reply
        except Exception as exc:  # noqa: BLE001 - an SDK that changed shape still works for standard providers
            self.emit(type="log", message=f"could not relax the SDK response literals: {exc!r}")

        class DiagnosticClient(OpenAIChatCompletionsClient):
            """The framework client, remembering the shape of the last provider reply.

            When a rollout is quarantined the error chain names the exception class
            only; the reply's finish reason, token usage and which message fields
            were filled are what actually explain an empty answer.
            """

            replay_reasoning = bool(run_cfg.get("replay_reasoning", True))
            strict_schema = bool(run_cfg.get("strict_schema", False))   # off by default: it changes the schema the model sees

            async def to_native_prompt(self, messages):
                native, extra = await super().to_native_prompt(messages)
                for m in native:
                    if not isinstance(m, dict) or m.get("role") != "assistant":
                        continue
                    # A reasoning-only or tool-call-only turn comes back with content None; several
                    # OpenAI-compatible servers (NVIDIA's gpt-oss endpoints among them) reject null
                    # content with a 400, while every one of them accepts "". Same meaning on the wire.
                    if m.get("content") is None:
                        m["content"] = ""
                    if not self.replay_reasoning:
                        m.pop("reasoning_content", None)   # the README's "no replay" arm: prior-turn reasoning stays private
                    # Never send an explicit null for an optional field: a turn without tool calls is
                    # serialised as tool_calls=None, and some servers iterate it ("'NoneType' object
                    # is not an iterator", a 400 seen from NVIDIA's gpt-oss endpoint). Omit the key.
                    for key in [k for k, v in m.items() if v is None]:
                        m.pop(key, None)
                return native, extra

            async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
                if tools and self.strict_schema:
                    tools = shim_tool_schemas(tools)   # the framework may hand tools in here already converted
                resp = await super().get_native_response(prompt, model, sampling_args, tools=tools, **kwargs)
                try:
                    diag["last"] = summarize_reply(resp, sampling_args)
                except Exception as exc:  # noqa: BLE001 - diagnostics must never break the call
                    diag["last"] = {"note": f"could not summarise the reply: {exc!r}"}
                return resp

        cfg = self.cfg
        key_var = f"PIV_LIVE_KEY_{uuid.uuid4().hex[:8]}"
        key = cfg.get("api_key") or ""
        if key.startswith("$"):
            key_var = key[1:].strip()
            value = resolve_env_value(key_var)
            if not value:
                self.emit(type="error", message=f"environment variable {key_var} is not set on this PC")
                return
            os.environ[key_var] = value   # the client reads it by name; a registry-only value is loaded here
        else:
            os.environ[key_var] = key or "EMPTY"
        self._secret = os.environ.get(key_var, "")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop = loop
        client = DiagnosticClient(ClientConfig(client_type="openai_chat_completions", api_key_var=key_var, api_base_url=cfg["base_url"],
                                               timeout=float(cfg.get("request_timeout", 600)), connect_timeout=10.0, max_retries=int(cfg.get("max_retries", 1))))
        client.base_url = cfg["base_url"]   # metadata.json takes base_url from the client object when one is passed directly
        try:
            self.task = loop.create_task(self.env.evaluate(
                client=client, model=cfg["model"], sampling_args={"max_tokens": int(cfg.get("max_tokens", 8000))},
                num_examples=1, rollouts_per_example=1, max_concurrent=1, max_retries=0,
                save_results=self.results_path is not None, results_path=self.results_path))
            results = loop.run_until_complete(self.task)
            self._guarded_finish(results)
        except asyncio.CancelledError:
            self.emit(type="stopped", removed=self._discard_empty_run())
        except PIVEvaluationBatchInvalid as exc:
            cause, row = self._quarantine_details(exc)
            self._guarded_finish(None, quarantined=f"{type(exc).__name__}: {exc}", cause=cause, row=row)
        except Exception as exc:  # noqa: BLE001
            self._discard_empty_run()
            self.emit(type="error", message=f"{type(exc).__name__}: {exc}")
        finally:
            if not key.startswith("$"):
                os.environ.pop(key_var, None)
            self._secret = ""
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:  # noqa: BLE001
                pass
            loop.close()

    def _quarantine_details(self, exc) -> tuple[str | None, dict | None]:
        """The real reason behind a quarantine: the error chain the environment stored for the batch."""
        try:
            from beancount_ledger.beancount_ledger import quarantine_artifact  # noqa: PLC0415
            records = quarantine_artifact(exc.batch_id)
        except Exception:  # noqa: BLE001 - evicted or unavailable; the summary still names the class
            records = []
        for rec in records:
            out = rec.get("output") if isinstance(rec, dict) else None
            if not isinstance(out, dict):
                continue
            err = out.get("error")
            chain = None
            if isinstance(err, dict):
                chain = err.get("error_chain_repr") or err.get("message") or err.get("error")
            elif err:
                chain = str(err)
            return (explain_provider_error(chain, getattr(self, "_diag", {}).get("last"), retries=self._retries()) if chain else None), out
        return explain_provider_error(None, getattr(self, "_diag", {}).get("last"), retries=self._retries()), None

    def _retries(self) -> int:
        return int(self.cfg.get("max_retries", 1))

    def _annotate_metadata(self) -> None:
        """Record in the run's metadata.json what the window changed about the request: the budget it was
        built under (so a looser run is never read as a benchmark run) and which provider shims were on."""
        rp = self.results_path
        if not rp:
            return
        meta_path = rp / "metadata.json"
        if not meta_path.exists():
            return
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["budget"] = dict(self.budget or budget_from_cfg(self.cfg), episode_contract_digest=getattr(self.env, "_episode_contract_digest", None))
            meta["replay_desktop"] = {"strict_schema": bool(self.cfg.get("strict_schema")), "replay_reasoning": bool(self.cfg.get("replay_reasoning", True)),
                                      "max_retries": self._retries()}
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=None), encoding="utf-8", newline="\n")
        except (OSError, ValueError) as exc:
            self.emit(type="log", message=f"could not annotate metadata.json: {exc}")

    def _guarded_finish(self, results, quarantined: str | None = None, cause: str | None = None, row: dict | None = None):
        try:
            self._finish(results, quarantined=quarantined, cause=cause, row=row)
        except Exception as exc:  # noqa: BLE001 - the window must always get a terminal event
            self.emit(type="error", message=f"finish: {type(exc).__name__}: {exc}")

    def _discard_empty_run(self) -> bool:
        """A stopped or failed run leaves metadata.json + an empty results.jsonl behind; that is not a run."""
        import shutil  # noqa: PLC0415
        rp = self.results_path
        if rp and rp.exists():
            rows = rp / "results.jsonl"
            if not rows.exists() or rows.stat().st_size == 0:
                shutil.rmtree(rp, ignore_errors=True)
                _rmdir_if_empty(rp.parent)
                return True
        return False

    def _set_aside_quarantined(self) -> str | None:
        """Move a quarantined run out of outputs/evals/<model>/ so no viewer or build embeds it as a scored run."""
        import shutil  # noqa: PLC0415
        rp = self.results_path
        if not rp or not rp.exists():
            return None
        dest = EVALS / "quarantined" / rp.parent.name / rp.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(rp), str(dest))
        _rmdir_if_empty(rp.parent)
        return str(dest.relative_to(ROOT)).replace("\\", "/")

    def _finish(self, results, quarantined: str | None = None, cause: str | None = None, row: dict | None = None):
        if row is not None:
            row = json.loads(json.dumps(row, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o)))
        if row is None and self.results_path and (self.results_path / "results.jsonl").exists():
            lines = [l for l in (self.results_path / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                row = json.loads(lines[-1])
        if row is None and results is not None:
            try:
                out = results["outputs"][0]
                row = dict(out) if not isinstance(out, dict) else out
                row = json.loads(json.dumps(row, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o)))
            except Exception:  # noqa: BLE001
                row = None
        status = None
        try:
            status = results["metadata"].get("piv_status") if results is not None else None
        except Exception:  # noqa: BLE001
            status = None
        err = (row or {}).get("error")
        if cause is None and isinstance(err, dict):
            cause = explain_provider_error(err.get("error_chain_repr") or err.get("message") or err.get("error"), retries=self._retries())
        elif cause is None and err:
            cause = explain_provider_error(str(err), retries=self._retries())
        self._annotate_metadata()   # before a quarantined record is moved: the note travels with it
        saved_to = str(self.results_path.relative_to(ROOT)).replace("\\", "/") if self.results_path else None
        if quarantined or (row or {}).get("stop_condition") == "has_error":
            saved_to = self._set_aside_quarantined()
        self.emit(type="done", row=row, saved_to=saved_to, quarantined=quarantined, status=status, cause=cause,
                  reward=(row or {}).get("reward"), stop=(row or {}).get("stop_condition"), budget=self.budget,
                  task=self.cfg.get("task"), model=self.cfg.get("model"))

    def stop(self):
        if self.loop and self.task and not self.task.done():
            self.loop.call_soon_threadsafe(self.task.cancel)


# --------------------------------------------------------------------------
# demo agent: a local mock OpenAI-compatible endpoint (zero cost)
# --------------------------------------------------------------------------
def start_demo_server() -> str:
    """A scripted agent behind a local /v1/chat/completions: reads, writes the golden ledger, submits."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: PLC0415

    # One golden ledger per registered task, keyed by the task prompt the environment
    # puts in the user message: the scripted agent then "solves" whichever task it is run on.
    from beancount_ledger.graph.derive import derive_contract  # noqa: PLC0415

    goldens = {}
    for _task_id, (_world, _task) in REGISTRY.items():
        try:
            goldens[_task.prompt.strip()] = (_task_id, derive_contract(_world, _task)[1].golden_text)
        except Exception:  # noqa: BLE001 - a world that will not derive simply has no demo
            pass
    fallback = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")

    def script_for(messages):
        prompt_text = " ".join(str(m.get("content") or "") for m in messages if m.get("role") == "user").strip()
        task_id, golden = next(((tid, g) for p_, (tid, g) in goldens.items() if p_ and p_ in prompt_text), ("bank_recon_001", fallback))
        return [
            ("Let me see what files I have.", [("list_files", {})]),
            ("I need the manifest, the policy and the ledger, plus the bank statement to reconcile against.",
             [("read_file", {"path": "manifest.md"}), ("read_file", {"path": "policy.md"}), ("read_file", {"path": "ledger.beancount"}), ("read_file", {"path": "bank_statement.csv"})]),
            (f"Comparing the statement with the ledger under the policy for {task_id}: the differences are the planted ones, and the uncleared item is a timing difference to leave alone. Writing the corrected ledger.",
             [("write_ledger", {"content": golden})]),
            ("The ledger loads cleanly and the bank balance agrees with the statement after the outstanding items. Submitting.",
             [("submit", {})]),
        ]

    class Mock(BaseHTTPRequestHandler):
        def log_message(self, *a):  # noqa: D401 - silence the default access log
            pass

        def do_GET(self):  # /v1/models, so the model picker works against the demo too
            body = json.dumps({"object": "list", "data": [{"id": "demo/scripted-agent", "object": "model", "owned_by": "beancount-ledger"},
                                                          {"id": "demo/scripted-agent-slow", "object": "model", "owned_by": "beancount-ledger"}]}).encode("utf-8")
            self.send_response(200 if self.path.rstrip("/").endswith("/models") else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or b"{}"))
            n = sum(1 for m in body.get("messages", []) if m.get("role") == "assistant")
            script = script_for(body.get("messages", []))
            reasoning, calls = script[min(n, len(script) - 1)]
            tool_calls = [{"id": f"call_{n + 1}_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}} for i, (name, args) in enumerate(calls)]
            payload = reasoning + "".join(tc["function"]["arguments"] for tc in tool_calls)
            cap = int(body.get("max_completion_tokens") or body.get("max_tokens") or 10**9)
            completion_tokens = min(max(8, len(payload) // 4), cap)
            resp = {"id": f"chatcmpl-demo-{n + 1}", "object": "chat.completion", "created": int(time.time()), "model": body.get("model", "demo"),
                    "choices": [{"index": 0, "finish_reason": "tool_calls",
                                 "message": {"role": "assistant", "content": "", "reasoning_content": reasoning, "tool_calls": tool_calls}}],
                    "usage": {"prompt_tokens": 1200 + 900 * n, "completion_tokens": completion_tokens, "total_tokens": 1200 + 900 * n + completion_tokens,
                              "completion_tokens_details": {"reasoning_tokens": max(1, len(reasoning) // 4)}}}
            time.sleep(0.6)  # so the live view visibly steps
            out = json.dumps(resp).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=srv.serve_forever, name="ledger-replay-demo-model", daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}/v1"


# --------------------------------------------------------------------------
# window
# --------------------------------------------------------------------------
UI_FONT = ("Segoe UI", 10)
UI_BOLD = ("Segoe UI", 10, "bold")
UI_SMALL = ("Segoe UI", 9)
MONO = ("Consolas", 10)
MONO_BIG = ("Consolas", 26, "bold")
C = {  # a light, cool-paper palette (the same family as docs/replay.html)
    "paper": "#f3f5f8", "surface": "#ffffff", "surface2": "#e9edf2", "ink": "#1a2230", "ink2": "#4b5768", "muted": "#5f6b7c",
    "rule": "#d8dde5", "accent": "#2e4a7d", "accent_soft": "#e2e9f5", "sel": "#fff3d1",
    "add": "#e6f4ea", "add_ink": "#1d5b33", "del": "#fbe8e6", "del_ink": "#8a2b21",
    "good": "#0ca30c", "good_soft": "#e2f3e2", "crit": "#d03b3b", "crit_soft": "#f9e0e0", "warn_soft": "#fdf1d6",
    "series1": "#2a78d6", "series2": "#eb6834",
}


def fmt_score(v):
    return "–" if v is None else f"{float(v):.3f}"


def fmt_int(v):
    return "–" if v is None else f"{int(round(float(v))):,}"


def fmt_money(v):
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return "–" if v in (None, "") else str(v)


class App(tk.Tk):
    def __init__(self, demo_url: str | None = None, probe_size: tuple[int, int] | None = None):
        super().__init__()
        self.title("Ledger Replay")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self._probe_size = probe_size
        if probe_size:
            self.geometry(f"{probe_size[0]}x{probe_size[1]}+{sw + 200}+{sh + 200}")  # off-screen: layout checks only
        else:
            self.geometry(f"{min(1480, sw - 60)}x{min(940, sh - 90)}+20+20")
            if sys.platform == "win32":
                self.after(50, lambda: self.state("zoomed"))
        self.minsize(1000, 640)
        self.configure(bg=C["paper"])
        self.rollouts: list[Rollout] = []
        self.current: Rollout | None = None
        self.sel_turn = 1
        self.sel_rev = 0
        self.view = tk.StringVar(value="diff")
        self.base = tk.StringVar(value="original")
        self.follow = tk.BooleanVar(value=True)
        self.events: queue.Queue = queue.Queue()
        self.live: LiveRun | None = None
        self._last_event_at = time.time()
        self._status_base = ""
        self._build_styles()
        self._build_form(demo_url)
        self._build_status()   # packed at the bottom first, so the panes can never squeeze it out
        self._build_body()
        self.after(150, self._drain_events)
        self.bind("<Left>", lambda e: self._step_turn(-1))
        self.bind("<Right>", lambda e: self._step_turn(1))
        self._reload_saved(select_last=False)
        self._sash_set = False
        self.body_pane.bind("<Configure>", self._place_sash)

    def _place_sash(self, event=None):
        """Give the scorer panel about 45% of the height (never under 250 px) once the window has its real size."""
        if self._sash_set or self.body_pane.winfo_height() < 300:
            return
        self._sash_set = True
        h = self.body_pane.winfo_height()
        self.after(50, lambda: self.body_pane.sash_place(0, 0, max(220, h - max(280, int(h * 0.45)))))

    # ---------------- styles / layout
    def _build_styles(self):
        st = ttk.Style(self)
        try:
            st.theme_use("vista")
        except tk.TclError:
            st.theme_use("clam")
        st.configure(".", font=UI_FONT, background=C["paper"])
        st.configure("TFrame", background=C["paper"])
        st.configure("Card.TFrame", background=C["surface"], relief="solid", borderwidth=1)
        st.configure("TLabel", background=C["paper"], foreground=C["ink"])
        st.configure("Card.TLabel", background=C["surface"], foreground=C["ink"])
        st.configure("Eyebrow.TLabel", background=C["surface"], foreground=C["muted"], font=("Segoe UI", 8, "bold"))
        st.configure("EyebrowP.TLabel", background=C["paper"], foreground=C["muted"], font=("Segoe UI", 8, "bold"))
        st.configure("Big.TLabel", background=C["surface"], foreground=C["accent"], font=MONO_BIG)
        st.configure("Title.TLabel", background=C["paper"], foreground=C["ink"], font=("Georgia", 16))
        st.configure("Muted.TLabel", background=C["paper"], foreground=C["muted"], font=UI_SMALL)
        st.configure("CardMuted.TLabel", background=C["surface"], foreground=C["muted"], font=UI_SMALL)
        st.configure("Treeview", font=UI_FONT, rowheight=22, background=C["surface"], fieldbackground=C["surface"])
        st.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        st.configure("Run.TButton", font=UI_BOLD)

    def _build_form(self, demo_url):
        top = ttk.Frame(self, padding=(14, 10, 14, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Ledger Replay", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="   saved rollouts replayed, live ones run against any OpenAI-compatible endpoint; every score is the environment's real scorer",
                  style="Muted.TLabel", wraplength=700, justify="left").pack(side="left", anchor="s", pady=(0, 3))

        pick = ttk.Frame(self, padding=(14, 0, 14, 4))
        pick.pack(fill="x")
        ttk.Label(pick, text="Rollout", style="EyebrowP.TLabel").pack(side="left", padx=(0, 8))
        self.saved_box = ttk.Combobox(pick, state="readonly", width=64)
        self.saved_box.pack(side="left", fill="x", expand=True)
        self.saved_box.bind("<<ComboboxSelected>>", lambda e: self._select_rollout(self.saved_box.current()))
        ttk.Button(pick, text="Open results.jsonl…", command=self._open_file).pack(side="left", padx=(8, 0))
        ttk.Button(pick, text="Refresh", command=lambda: self._reload_saved(select_last=False)).pack(side="left", padx=(4, 0))

        shell = ttk.Frame(self, padding=(14, 0, 14, 4))
        shell.pack(fill="x")
        tall = (self._probe_size[1] if self._probe_size else self.winfo_screenheight()) >= 900
        self.form_open = tk.BooleanVar(value=tall)  # on short screens start folded; the panes need the room
        self.form_toggle = ttk.Checkbutton(shell, text="Run your own model, live", variable=self.form_open, style="Toolbutton", command=self._toggle_form)
        self.form_toggle.pack(anchor="w")
        form = ttk.Frame(shell, padding=(10, 2, 10, 4), style="Card.TFrame")
        if self.form_open.get():
            form.pack(fill="x", pady=(2, 0))
        self.form_body = form
        self.v_base = tk.StringVar(value=demo_url or "http://localhost:11434/v1")
        self.v_key = tk.StringVar(value="demo" if demo_url else "")
        self.v_model = tk.StringVar(value="demo/scripted-agent" if demo_url else "")
        self.v_task = tk.StringVar(value=DEFAULT_TASK)
        self.v_tokens = tk.StringVar(value="8000")
        self.v_save = tk.BooleanVar(value=not demo_url)  # demo runs are not worth keeping unless you say so
        form.columnconfigure((0, 1, 2), weight=1)

        def field(col, row, label, widget_fn):
            f = ttk.Frame(form, style="Card.TFrame")
            f.grid(row=row, column=col, sticky="ew", padx=(0, 14), pady=(0, 4))
            ttk.Label(f, text=label, style="Eyebrow.TLabel").pack(anchor="w")
            w = widget_fn(f)
            w.pack(fill="x")
            return w

        field(0, 0, "Base URL", lambda f: ttk.Entry(f, textvariable=self.v_base, font=UI_FONT))
        field(1, 0, "API key (or $ENV_VAR)", lambda f: ttk.Entry(f, textvariable=self.v_key, font=UI_FONT, show="•"))
        field(2, 0, "Model", lambda f: ttk.Entry(f, textvariable=self.v_model, font=UI_FONT))
        row1 = ttk.Frame(form, style="Card.TFrame")
        row1.grid(row=1, column=0, columnspan=3, sticky="ew")
        f = ttk.Frame(row1, style="Card.TFrame"); f.pack(side="left", padx=(0, 14))
        ttk.Label(f, text="Task", style="Eyebrow.TLabel").pack(anchor="w")
        self.task_box = ttk.Combobox(f, textvariable=self.v_task, width=15, values=sorted(REGISTRY) + ["train:7", "eval:3", "train:7:hard"])
        self.task_box.pack(anchor="w")
        f = ttk.Frame(row1, style="Card.TFrame"); f.pack(side="left", padx=(0, 14))
        ttk.Label(f, text="Max tokens / turn", style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Spinbox(f, textvariable=self.v_tokens, from_=2000, to=40000, increment=500, width=7, font=UI_FONT).pack(anchor="w")
        f = ttk.Frame(row1, style="Card.TFrame"); f.pack(side="left", padx=(0, 10), anchor="s")
        ttk.Checkbutton(f, text="Save run", variable=self.v_save).pack(side="left")
        ttk.Checkbutton(f, text="Follow live", variable=self.follow).pack(side="left", padx=(8, 0))
        f = ttk.Frame(row1, style="Card.TFrame"); f.pack(side="right", anchor="s")
        self.btn_run = ttk.Button(f, text="▶ Run", style="Run.TButton", command=self._run, width=8)
        self.btn_run.pack(side="left")
        self.btn_stop = ttk.Button(f, text="■ Stop", command=self._stop, state="disabled", width=8)
        self.btn_stop.pack(side="left", padx=(6, 0))
        hint = "The key stays in this process and goes only to the base URL above. Saved runs land under outputs/evals/. Generated tasks need PIV_EVAL_SECRET in the environment."
        if demo_url:
            hint = f"Demo mode: a scripted agent is listening at {demo_url}. Press Run to watch a live episode at zero cost, or point the form at a real endpoint."
        self._hint = hint

    def _toggle_form(self):
        if self.form_open.get():
            self.form_body.pack(fill="x", pady=(2, 0))
        else:
            self.form_body.pack_forget()
        self._sash_set = False

    def _build_body(self):
        self.tiles = ttk.Frame(self, padding=(14, 0, 14, 6))
        self.tiles.pack(fill="x")
        self.tile_vars = {}
        for key, label in [("reward", "Reward"), ("stop", "Outcome"), ("agent", "Agent"), ("turns", "Turns"), ("calls", "Tool calls"), ("tok_out", "Tokens out"), ("tok_in", "Tokens in"), ("time", "Time")]:
            card = ttk.Frame(self.tiles, style="Card.TFrame", padding=(8, 2))
            card.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ttk.Label(card, text=label, style="Eyebrow.TLabel").pack(anchor="w")
            var = tk.StringVar(value="–")
            ttk.Label(card, textvariable=var, style="Big.TLabel" if key == "reward" else "Card.TLabel",
                      font=("Consolas", 20, "bold") if key == "reward" else ("Consolas", 13) if key in ("turns", "calls", "tok_out", "tok_in", "time") else UI_SMALL,
                      wraplength=150).pack(anchor="w")
            self.tile_vars[key] = var

        body = tk.PanedWindow(self, orient="vertical", sashwidth=6, sashrelief="flat", bg=C["paper"], bd=0, opaqueresize=True)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        self.body_pane = body
        upper = ttk.PanedWindow(body, orient="horizontal")
        body.add(upper, minsize=220, stretch="always")

        # left: turns + details
        left = ttk.Frame(upper)
        upper.add(left, weight=2)
        ttk.Label(left, text="Agent turns", style="Title.TLabel").pack(anchor="w")
        cols = ("turn", "tools", "rev", "secs")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=4, selectmode="browse")
        for c_, w, text, anchor in [("turn", 44, "T", "center"), ("tools", 330, "Tool calls", "w"), ("rev", 120, "Ledger", "w"), ("secs", 64, "Time", "e")]:
            self.tree.heading(c_, text=text)
            self.tree.column(c_, width=w, anchor=anchor, stretch=(c_ == "tools"))
        self.tree.tag_configure("write", background=C["accent_soft"])
        self.tree.tag_configure("submit", font=UI_BOLD)
        self.tree.tag_configure("refused", background=C["crit_soft"])
        self.tree.tag_configure("note", background=C["warn_soft"])
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        ttk.Label(left, text="Turn detail", style="EyebrowP.TLabel").pack(anchor="w", pady=(6, 0))
        self.detail = self._text(left, height=6)
        self.detail.pack(fill="both", expand=True)

        # right: ledger
        right = ttk.Frame(upper)
        upper.add(right, weight=3)
        head = ttk.Frame(right); head.pack(fill="x")
        ttk.Label(head, text="Ledger", style="Title.TLabel").pack(side="left")
        ctl = ttk.Frame(head); ctl.pack(side="right")
        for text, val in [("Diff", "diff"), ("Full text", "text")]:
            ttk.Radiobutton(ctl, text=text, value=val, variable=self.view, command=self._render_ledger).pack(side="left")
        bar = ttk.Frame(right); bar.pack(fill="x", pady=(2, 4))
        self.rev_bar = ttk.Frame(bar); self.rev_bar.pack(side="left")
        base_ctl = ttk.Frame(bar); base_ctl.pack(side="right")
        for text, val in [("vs original", "original"), ("vs previous", "previous")]:
            ttk.Radiobutton(base_ctl, text=text, value=val, variable=self.base, command=self._render_ledger).pack(side="left")
        self.ledger_foot = ttk.Label(right, text="", style="Muted.TLabel")
        self.ledger_foot.pack(side="bottom", anchor="w")
        self.ledger = self._text(right, height=8, font=MONO)
        self.ledger.pack(fill="both", expand=True)
        for tag, kw in [("ln", {"foreground": C["muted"]}), ("add", {"background": C["add"], "foreground": C["add_ink"]}), ("del", {"background": C["del"], "foreground": C["del_ink"], "overstrike": True}),
                        ("mark_ok", {"background": C["good_soft"], "font": ("Segoe UI", 9, "bold")}), ("mark_miss", {"background": C["surface2"], "font": ("Segoe UI", 9, "bold")}),
                        ("mark_trap", {"background": C["accent_soft"], "font": ("Segoe UI", 9, "bold")}), ("mark_bad", {"background": C["crit_soft"], "font": ("Segoe UI", 9, "bold")}),
                        ("h", {"font": UI_BOLD}), ("dim", {"foreground": C["muted"]}), ("hl", {"background": C["sel"]})]:
            self.ledger.text.tag_configure(tag, **kw)

        # bottom: scorer
        lower = ttk.Frame(body, style="Card.TFrame", padding=(12, 8))
        body.add(lower, minsize=280, stretch="never")
        self.scorer = lower
        sh = ttk.Frame(lower, style="Card.TFrame"); sh.pack(fill="x")
        ttk.Label(sh, text="Scorer breakdown", style="Card.TLabel", font=("Georgia", 14)).pack(side="left")
        self.scorer_sub = ttk.Label(sh, text="", style="CardMuted.TLabel"); self.scorer_sub.pack(side="left", padx=(12, 0))
        self.flags = ttk.Label(sh, text="", style="CardMuted.TLabel"); self.flags.pack(side="right")
        self.prov = ttk.Label(lower, text="", style="CardMuted.TLabel", wraplength=1000, justify="left"); self.prov.pack(side="bottom", anchor="w", pady=(4, 0))
        grid = ttk.Frame(lower, style="Card.TFrame"); grid.pack(fill="both", expand=True, pady=(6, 0))
        grid.columnconfigure((0, 1, 2, 3), weight=1, uniform="score")
        grid.rowconfigure(0, weight=1)
        # reward + meter
        c0 = ttk.Frame(grid, style="Card.TFrame"); c0.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(c0, text="Reward", style="Eyebrow.TLabel").pack(anchor="w")
        self.big = ttk.Label(c0, text="–", style="Big.TLabel", font=("Consolas", 18, "bold")); self.big.pack(anchor="w")
        self.meter = tk.Canvas(c0, height=42, width=200, bg=C["surface"], highlightthickness=0); self.meter.pack(fill="x")
        self.formula = self._text(c0, height=3, font=("Segoe UI", 8)); self.formula.pack(fill="both", expand=True)
        # planted
        c1 = ttk.Frame(grid, style="Card.TFrame"); c1.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        ttk.Label(c1, text="Planted discrepancies", style="Eyebrow.TLabel").pack(anchor="w")
        self.planted = self._text(c1, height=6, font=UI_SMALL); self.planted.pack(fill="both", expand=True)
        self.planted.text.tag_configure("RESOLVED", background=C["good_soft"], font=("Consolas", 9, "bold"))
        self.planted.text.tag_configure("MISSING", background=C["surface2"], font=("Consolas", 9, "bold"))
        self.planted.text.tag_configure("other", background=C["warn_soft"], font=("Consolas", 9, "bold"))
        self.planted.text.tag_configure("name", font=("Consolas", 9, "bold"))
        self.planted.text.tag_configure("mono", font=("Consolas", 9), foreground=C["ink2"])
        self.planted.text.tag_configure("dim", foreground=C["muted"])
        # target accounts
        c2 = ttk.Frame(grid, style="Card.TFrame"); c2.grid(row=0, column=2, sticky="nsew", padx=(0, 12))
        ttk.Label(c2, text="Target accounts", style="Eyebrow.TLabel").pack(anchor="w")
        self.acct = ttk.Treeview(c2, columns=("acct", "exp", "got", "st"), show="headings", height=4)
        for c_, w, text, anchor in [("acct", 130, "Scored account", "w"), ("exp", 72, "Expected", "e"), ("got", 72, "Got", "e"), ("st", 46, "", "center")]:
            self.acct.heading(c_, text=text); self.acct.column(c_, width=w, minwidth=w if c_ != "acct" else 50, anchor=anchor, stretch=(c_ == "acct"))
        self.acct.tag_configure("miss", background=C["crit_soft"])
        self.acct.pack(fill="x")
        self.acct_note = ttk.Label(c2, text="", style="CardMuted.TLabel", wraplength=320, justify="left"); self.acct_note.pack(anchor="w", pady=(4, 0))
        # penalties
        c3 = ttk.Frame(grid, style="Card.TFrame"); c3.grid(row=0, column=3, sticky="nsew")
        self.pen_title = ttk.Label(c3, text="Penalties", style="Eyebrow.TLabel"); self.pen_title.pack(anchor="w")
        self.pen = self._text(c3, height=6, font=UI_SMALL); self.pen.pack(fill="both", expand=True)
        self.pen.text.tag_configure("hit", background=C["crit_soft"], font=("Segoe UI", 9, "bold"))
        self.pen.text.tag_configure("mono", font=("Consolas", 9), foreground=C["ink2"])

    def _build_status(self):
        bar = ttk.Frame(self, padding=(14, 2, 14, 6)); bar.pack(side="bottom", fill="x")
        self.status = ttk.Label(bar, text="Ready. " + getattr(self, "_hint", ""), style="Muted.TLabel", wraplength=1200, justify="left"); self.status.pack(side="left")
        ttk.Label(bar, text="←  → step through turns", style="Muted.TLabel").pack(side="right")

    def _text(self, parent, height=8, font=UI_FONT):
        frame = ttk.Frame(parent)
        t = tk.Text(frame, height=height, width=24, wrap="none" if font == MONO else "word", font=font, bg=C["surface"], fg=C["ink"], relief="flat",
                    padx=8, pady=6 if font == MONO else 3, highlightthickness=1, highlightbackground=C["rule"], state="disabled", cursor="arrow")
        ys = ttk.Scrollbar(frame, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=ys.set)
        t.grid(row=0, column=0, sticky="nsew"); ys.grid(row=0, column=1, sticky="ns")
        if font == MONO:
            xs = ttk.Scrollbar(frame, orient="horizontal", command=t.xview)
            t.configure(xscrollcommand=xs.set); xs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        frame.text = t
        return frame

    @staticmethod
    def _set(frame, fill):
        """fill(t) writes into the Text widget t (already cleared and enabled)."""
        t = frame.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        fill(t)
        t.configure(state="disabled")

    # ---------------- data plumbing
    def _reload_saved(self, select_last: bool):
        live = [r for r in self.rollouts if r.live]
        try:
            saved = load_saved_runs()
        except Exception as exc:  # noqa: BLE001
            saved = []
            self._status(f"could not read outputs/evals: {exc}")
        self.rollouts = live + saved
        self._refresh_saved_box()
        if self.rollouts and (self.current is None or select_last):
            self._select_rollout(0 if not select_last else len(live) - 1 if live else 0)

    def _refresh_saved_box(self):
        self.saved_box["values"] = [f"{r.label} · reward {fmt_score(r.reward)}" + (" · live" if r.live else "") for r in self.rollouts]
        if self.current in self.rollouts:
            self.saved_box.current(self.rollouts.index(self.current))

    def _open_file(self):
        path = filedialog.askopenfilename(title="Open a vf-eval results.jsonl", filetypes=[("results.jsonl", "*.jsonl"), ("All files", "*.*")])
        if not path:
            return
        try:
            rs = load_results_file(Path(path))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Could not open", f"{path}\n\n{exc}")
            return
        self.rollouts = rs + self.rollouts
        self._refresh_saved_box()
        self._select_rollout(0)

    def _select_rollout(self, idx: int):
        if not (0 <= idx < len(self.rollouts)):
            return
        self.current = self.rollouts[idx]
        self.saved_box.current(idx)
        if self.current.error:
            self._status(f"{self.current.label}: {self.current.error}")
        first_write = next((rv for rv in self.current.revisions if rv.index == 1), None)
        self.sel_rev = 1 if first_write else 0
        self.sel_turn = first_write.turn if first_write else (self.current.turns[0].no if self.current.turns else 1)
        self._render_all()

    # ---------------- live run
    def _run(self):
        if self.live is not None:
            return
        base, model, task = self.v_base.get().strip(), self.v_model.get().strip(), self.v_task.get().strip()
        if not base or not model or not task:
            messagebox.showwarning("Missing", "Base URL, model and task are required.")
            return
        try:
            max_tokens = int(self.v_tokens.get())
        except ValueError:
            messagebox.showwarning("Max tokens", "Max tokens per turn must be a number.")
            return
        r = Rollout(label=f"{model.split('/')[-1]} · live {time.strftime('%H:%M:%S')}", task_id=task, model=model, base_url=base, live=True, status="starting")
        r.revisions = [Revision(0, 0, "")]
        self.rollouts.insert(0, r)
        self.current = r
        self.sel_turn, self.sel_rev = 1, 0
        self._refresh_saved_box()
        self.saved_box.current(0)
        self._status(f"loading task {task}…")
        self.update_idletasks()
        cfg = {"base_url": base, "api_key": self.v_key.get(), "model": model, "task": task, "max_tokens": max_tokens, "save": self.v_save.get()}
        self.live = LiveRun(cfg, self.events)
        try:
            self.live.start()
        except Exception as exc:  # noqa: BLE001
            self.live = None
            r.status = "failed to start"
            r.error = str(exc)
            self._status(f"could not start: {exc}")
            messagebox.showerror("Could not start the episode", str(exc))
            self._render_all()
            return
        self.btn_run.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._status(f"running {model} on {task} · waiting for the first turn…")
        self._render_all()

    def _stop(self):
        if self.live:
            self.live.stop()
            self._status("stopping…")

    def _drain_events(self):
        try:
            while True:
                ev = self.events.get_nowait()
                self._last_event_at = time.time()
                try:
                    self._apply_event(ev)
                except Exception as exc:  # noqa: BLE001 - a rendering slip must not freeze the window
                    self._status(f"viewer error while showing a {ev.get('type')} event: {exc!r}")
        except queue.Empty:
            pass
        finally:
            if self.live is not None:
                if self.live.thread is not None and not self.live.thread.is_alive() and self.events.empty():
                    self._finish_live("the run ended without a result (see the console for the traceback)")
                elif time.time() - self._last_event_at > 5:
                    self._tick_status()
            self.after(150, self._drain_events)

    def _tick_status(self):
        base = self._status_base or "waiting for the model…"
        self.status.configure(text=f"{base} · {int(time.time() - self._last_event_at)} s since the last event")

    def _apply_event(self, ev: dict):
        r = next((x for x in self.rollouts if x.live and x.status not in ("done", "stopped", "failed")), None)
        if r is None:
            return
        kind = ev.get("type")
        if kind == "start":
            r.task = ev["task"]
            r.revisions[0].text = ev["original"]
            r.status = "running"
        elif kind == "revision":
            idx = ev["revision"]
            rv = Revision(idx, r.turn_map.get(ev.get("turn"), ev.get("turn") or 0), ev.get("text") or "", ev.get("report") or "", ev.get("digest"), ev.get("score"))
            if idx == 0:
                r.revisions[0] = rv
            else:
                r.revisions = [x for x in r.revisions if x.index != idx] + [rv]
                r.revisions.sort(key=lambda x: x.index)
                for t in r.turns:
                    if t.no == rv.turn:
                        for c in t.calls:
                            if c.name == "write_ledger" and c.revision is None:
                                c.revision = idx
                                break
                self.sel_rev = idx
            self._status(f"revision {idx} scored: {fmt_score((ev.get('score') or {}).get('reward'))}")
        elif kind == "assistant":
            # number as the saved transcript will: nudges (user messages) take a turn number of their own
            disp = r.turn_map.get(ev["turn"]) or ((r.turns[-1].no + 1) if r.turns else 1)
            r.turn_map[ev["turn"]] = disp
            turn = Turn(disp, content=ev.get("content") or "", reasoning=ev.get("reasoning") or "",
                        calls=[Call(tc["id"], tc["name"], self._args(tc.get("arguments"))) for tc in ev.get("tool_calls") or []],
                        secs=ev.get("secs"), usage=ev.get("usage"))
            r.turns = [t for t in r.turns if t.no != turn.no] + [turn]
            r.turns.sort(key=lambda t: t.no)
            if self.follow.get():
                self.sel_turn = turn.no
            self._status(f"turn {turn.no}: {', '.join(c.name for c in turn.calls) or 'no tool call'}")
        elif kind == "tools":
            results = {x["tool_call_id"]: x["content"] for x in ev.get("results") or [] if x.get("tool_call_id")}
            nudges = [x for x in ev.get("results") or [] if x.get("role") == "user"]
            disp = r.turn_map.get(ev.get("turn"), ev.get("turn"))
            for t in r.turns:
                if t.no == disp:
                    for c in t.calls:
                        if c.id in results:
                            c.result = results[c.id]
                            if c.name == "write_ledger" and not (br._attestation(c.result) or {}).get("committed"):
                                c.refused = True
                            if c.name == "submit" and not c.result.lower().startswith("submitted"):
                                c.refused = True
            if nudges:
                no = (r.turns[-1].no if r.turns else 0) + 1
                r.turns.append(Turn(no, kind="note", role="user", content=nudges[0]["content"]))
        elif kind == "done":
            failed = bool(ev.get("quarantined")) or ev.get("stop") == "has_error"
            r.status = "failed" if failed else "done"
            r.saved_to = ev.get("saved_to")
            row = ev.get("row")
            if row:
                try:
                    fresh = normalize_row(row, r.label, r.model, r.base_url, original=r.revisions[0].text if r.revisions else None)
                    scores = {rv.index: rv.score for rv in r.revisions}
                    for rv in fresh.revisions:
                        rv.score = scores.get(rv.index, rv.score)
                    r.turns, r.revisions, r.reward, r.stop, r.metrics, r.tokens, r.truncated, r.error = fresh.turns, fresh.revisions, fresh.reward, fresh.stop, fresh.metrics, fresh.tokens, fresh.truncated, fresh.error
                    if fresh.task and fresh.task.get("planted"):
                        r.task = fresh.task
                except Exception as exc:  # noqa: BLE001
                    r.error = f"could not normalise the saved row: {exc}"
            r.reward = ev.get("reward", r.reward)
            r.stop = ev.get("stop", r.stop)
            if failed:
                r.reward = None
                r.error = " · ".join(x for x in (ev.get("cause"), ev.get("quarantined")) if x) or r.error or "the provider returned an error"
                self._finish_live(f"failed (quarantined, not a scored run): {r.error}" + (f" · record set aside under {r.saved_to}" if r.saved_to else ""))
            else:
                if self.follow.get() and r.turns:
                    self.sel_turn = r.turns[-1].no
                elif not any(t.no == self.sel_turn for t in r.turns):
                    self.sel_turn = r.turns[-1].no if r.turns else 1
                self.sel_rev = max([rv.index for rv in r.revisions if rv.index > 0 and rv.turn <= self.sel_turn] or [0])
                self._finish_live(f"done · reward {fmt_score(r.reward)} · {r.stop or ''}" + (f" · saved to {r.saved_to}" if r.saved_to else " · not saved"))
        elif kind == "stopped":
            r.status = "stopped"
            self._finish_live("stopped by you; nothing saved" + (" (the empty run folder was removed)" if ev.get("removed") else ""))
        elif kind == "error":
            r.status = "failed"
            r.error = ev.get("message")
            self._finish_live(f"failed: {ev.get('message')}")
        elif kind == "log":
            self._status(ev.get("message", ""))
        self._refresh_saved_box()
        if r is self.current:
            self._render_all()

    def _finish_live(self, msg):
        self.live = None
        self.btn_run.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self._status(msg)

    @staticmethod
    def _args(arguments):
        if isinstance(arguments, dict):
            return arguments
        try:
            parsed = json.loads(arguments or "{}")
        except (json.JSONDecodeError, TypeError):
            return {"_raw": arguments}
        return parsed if isinstance(parsed, dict) else {"_raw": arguments}

    # ---------------- rendering
    def _status(self, msg):
        self._status_base = msg
        self.status.configure(text=msg)

    def _render_all(self):
        r = self.current
        if r is None:
            return
        self._render_tiles(r)
        self._render_turns(r)
        self._render_detail(r)
        self._render_ledger()
        self._render_scorer(r)

    def _render_tiles(self, r: Rollout):
        v = self.tile_vars
        v["reward"].set(fmt_score(r.reward) if r.reward is not None else ("…" if r.live and r.status == "running" else "–"))
        v["agent"].set(r.model.split("/")[-1] or "–")
        v["turns"].set(str(len([t for t in r.turns if t.kind == "turn"])))
        v["calls"].set(str(sum(len(t.calls) for t in r.turns)))
        v["tok_out"].set(fmt_int(r.tokens.get("output_tokens")) if r.tokens else fmt_int(sum((t.usage or {}).get("completion_tokens") or 0 for t in r.turns) or None))
        v["tok_in"].set(fmt_int(r.tokens.get("input_tokens")) if r.tokens else fmt_int(sum((t.usage or {}).get("prompt_tokens") or 0 for t in r.turns) or None))
        secs = sum(t.secs or 0 for t in r.turns)
        v["time"].set(f"{secs:.0f} s" if secs else "–")
        v["stop"].set((r.stop or r.status or "–") + (" ✕" if r.error else ""))

    def _render_turns(self, r: Rollout):
        self.tree.delete(*self.tree.get_children())
        for t in r.turns:
            if t.kind == "note":
                self.tree.insert("", "end", iid=str(t.no), values=(f"T{t.no}", f"{t.role} message", "", ""), tags=("note",))
                continue
            names = {}
            for c in t.calls:
                names[c.name] = names.get(c.name, 0) + 1
            tools = ", ".join(f"{n}×{k}" if k > 1 else n for n, k in names.items()) or "(no tool call)"
            tags = []
            if any(c.refused for c in t.calls):
                tags.append("refused")
            elif any(c.name == "submit" for c in t.calls):
                tags.append("submit")
            elif any(c.name == "write_ledger" for c in t.calls):
                tags.append("write")
            rev = ""
            for c in t.calls:
                if c.name == "write_ledger":
                    if c.revision:
                        rv = next((x for x in r.revisions if x.index == c.revision), None)
                        base = next((x for x in r.revisions if x.index == c.revision - 1), None)
                        if rv and base:
                            d = diff_lines(base.text, rv.text)
                            rev = f"rev {c.revision}: +{sum(1 for o in d if o[0] == '+')} −{sum(1 for o in d if o[0] == '-')}"
                        else:
                            rev = f"rev {c.revision}"
                    elif c.refused:
                        rev = "refused"
                    elif c.unexecuted:
                        rev = "not executed"
            self.tree.insert("", "end", iid=str(t.no), values=(f"T{t.no}", tools, rev, f"{t.secs:.1f} s" if t.secs else ""), tags=tuple(tags))
        if self.tree.exists(str(self.sel_turn)):
            self.tree.selection_set(str(self.sel_turn))
            self.tree.see(str(self.sel_turn))

    def _on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if not sel or self.current is None:
            return
        self.sel_turn = int(sel[0])
        self.sel_rev = max([rv.index for rv in self.current.revisions if rv.index > 0 and rv.turn <= self.sel_turn] or [0])
        self._render_detail(self.current)
        self._render_ledger()
        self._render_scorer(self.current)

    def _step_turn(self, delta):
        if self.current is None or not self.current.turns:
            return
        nos = [t.no for t in self.current.turns]
        i = nos.index(self.sel_turn) if self.sel_turn in nos else 0
        j = max(0, min(len(nos) - 1, i + delta))
        self.tree.selection_set(str(nos[j]))
        self.tree.see(str(nos[j]))

    def _render_detail(self, r: Rollout):
        t = next((x for x in r.turns if x.no == self.sel_turn), None)

        def fill(w):
            w.tag_configure("h", font=UI_BOLD)
            w.tag_configure("dim", foreground=C["muted"])
            w.tag_configure("mono", font=("Consolas", 9))
            if t is None:
                w.insert("end", "Select a turn.", "dim")
                return
            if t.kind == "note":
                w.insert("end", f"{t.role} message\n", "h")
                w.insert("end", t.content)
                return
            if t.content.strip():
                w.insert("end", "Assistant\n", "h")
                w.insert("end", t.content.strip() + "\n\n")
            if t.reasoning:
                w.insert("end", f"Hidden reasoning · {len(t.reasoning):,} chars\n", "h")
                w.insert("end", t.reasoning.strip() + "\n\n", "dim")
            if t.usage:
                w.insert("end", f"usage: prompt {fmt_int(t.usage.get('prompt_tokens'))} · completion {fmt_int(t.usage.get('completion_tokens'))}\n\n", "dim")
            for c in t.calls:
                args = ", ".join(f"{k}={json.dumps(v) if not (c.name == 'write_ledger' and k == 'content') else str(len(str(v).split(chr(10)))) + ' lines'}" for k, v in c.args.items())
                w.insert("end", f"{c.name}({args})\n", "h")
                if c.result is None:
                    w.insert("end", "  not executed (the episode ended before this call ran)\n\n", "dim")
                elif c.name == "read_file" and c.args.get("path") == "ledger.beancount" and c.result.startswith("option "):
                    w.insert("end", f"  → complete ledger, {len(split_lines(c.result))} lines (shown in the ledger panel)\n\n", "dim")
                elif c.name == "write_ledger":
                    w.insert("end", "  → " + c.result.split("\n")[-1] + (f" (revision {c.revision})" if c.revision else " (refused)") + "\n\n", "dim")
                else:
                    w.insert("end", "  → " + c.result.strip() + "\n\n", "mono")
        self._set(self.detail, fill)

    def _render_ledger(self):
        r = self.current
        if r is None:
            return
        for w in self.rev_bar.winfo_children():
            w.destroy()
        for rv in r.revisions:
            label = "Original" if rv.index == 0 else f"Rev {rv.index} · T{rv.turn}"
            if rv.score:
                label += f"  {fmt_score(rv.score.get('reward'))}"
            b = ttk.Button(self.rev_bar, text=label, command=lambda i=rv.index, t=rv.turn: self._pick_rev(i, t))
            b.pack(side="left", padx=(0, 4))
            if rv.index == self.sel_rev:
                b.state(["pressed"])
        rv = next((x for x in r.revisions if x.index == self.sel_rev), r.revisions[0] if r.revisions else None)
        task = r.task or {}
        planted, traps = task.get("planted", []), task.get("traps", [])

        def fill(w):
            if rv is None or not rv.text:
                w.insert("end", "No ledger text for this revision.", "dim")
                return
            lines = split_lines(rv.text)
            p_blocks = find_planted_blocks(lines, planted)
            t_blocks = find_trap_blocks(lines, traps)
            orig_lines = split_lines(r.revisions[0].text)
            t_orig = find_trap_blocks(orig_lines, traps)
            sc = rv.score or {}
            marks: dict[int, list] = {}
            for p in planted:
                b = p_blocks.get(p["id"])
                st = (sc.get("item_states") or {}).get(p["id"])
                if b:
                    tag = "mark_ok" if st == "RESOLVED" else "mark_miss"
                    what = "resolved — scorer state RESOLVED" if st == "RESOLVED" else (f"posted, but scorer state is {st}" if st else "posted (unscored)")
                    marks.setdefault(b["start"], []).append((tag, f"◆ {p['id']} · {what} — {p.get('description', '')}"))
            for t in traps:
                b, b0 = t_blocks.get(t["id"]), t_orig.get(t["id"])
                untouched = b and b0 and b["body"] == b0["body"]
                if b:
                    if rv.index == 0:
                        marks.setdefault(b["start"], []).append(("mark_trap", f"△ {t['id']} · trap: must be left untouched — {t.get('description', '')}"))
                    elif untouched:
                        marks.setdefault(b["start"], []).append(("mark_trap", f"△ {t['id']} · trap left untouched, as required"))
                    else:
                        marks.setdefault(b["start"], []).append(("mark_bad", f"△ {t['id']} · trap was altered — {t.get('description', '')}"))
                elif b0 and rv.index > 0:
                    w.insert("end", f"△ {t['id']} · trap entry is missing from this revision\n", "mark_bad")
            if self.view.get() == "text" or rv.index == 0:
                for i, s in enumerate(lines):
                    for tag, text in marks.get(i, []):
                        w.insert("end", text + "\n", tag)
                    w.insert("end", f"{i + 1:4}      ", "ln")
                    w.insert("end", s + "\n")
            else:
                base_rv = next((x for x in r.revisions if x.index == rv.index - 1), r.revisions[0]) if self.base.get() == "previous" else r.revisions[0]
                for tag, ai, bi, s in diff_lines(base_rv.text, rv.text):
                    if bi is not None:
                        for mtag, text in marks.get(bi, []):
                            w.insert("end", text + "\n", mtag)
                    w.insert("end", f"{'' if ai is None else ai + 1:>4} {'' if bi is None else bi + 1:>4} ", "ln")
                    w.insert("end", f"{tag if tag != ' ' else ' '} {s}\n", "add" if tag == "+" else "del" if tag == "-" else "")
            for p in planted:
                if p["id"] not in p_blocks:
                    w.insert("end", f"◆ {p['id']} · not posted in this revision — {p.get('description', '')}\n", "mark_miss")
        self._set(self.ledger, fill)
        foot = []
        if rv and rv.text:
            foot.append(f"{len(split_lines(rv.text))} lines")
            if rv.index > 0:
                d = diff_lines(r.revisions[0].text, rv.text)
                foot.append(f"+{sum(1 for o in d if o[0] == '+')} −{sum(1 for o in d if o[0] == '-')} vs original")
                if rv.report:
                    foot.append(rv.report.split("\n")[0])
                if rv.digest:
                    foot.append("logical digest " + rv.digest[:12])
            else:
                foot.append("as the agent first read it")
        self.ledger_foot.configure(text="   ".join(foot))

    def _pick_rev(self, index, turn):
        self.sel_rev = index
        if index > 0:
            self.sel_turn = turn
            if self.tree.exists(str(turn)):
                self.tree.selection_set(str(turn))
        self._render_ledger()
        if self.current:
            self._render_detail(self.current)
            self._render_scorer(self.current)

    def _render_scorer(self, r: Rollout):
        rv = next((x for x in r.revisions if x.index == self.sel_rev), None)
        sc = rv.score if rv else None
        self.scorer_sub.configure(text="the ledger as the agent received it, before any write" if (rv and rv.index == 0) else (f"revision {rv.index}, written on turn {rv.turn}" if rv else ""))
        if not sc:
            self.big.configure(text="–")
            self.flags.configure(text="")
            self.meter.delete("all")
            note = "No score for this revision." if rv else "Select a revision."
            if r.task_id and r.task_id not in REGISTRY and not r.live:
                note = "Generated task: saved transcripts cannot be re-scored offline (the evaluator secret is needed). Recorded reward: " + fmt_score(r.reward)
            self._set(self.formula, lambda w: w.insert("end", note))
            self._set(self.planted, lambda w: None)
            self.acct.delete(*self.acct.get_children())
            self.acct_note.configure(text="")
            self._set(self.pen, lambda w: None)
            self.prov.configure(text="")
            return
        th = float((sc.get("components") or {}).get("targets_hit") or 0)
        er = float((sc.get("components") or {}).get("errors_resolved") or 0)
        pen = 0.0
        for key, _label, each, once in PENALTIES:
            n = len(sc.get(key) or [])
            if n:
                pen += each if once else each * n
        total = float(sc.get("reward") or 0)
        self.big.configure(text=fmt_score(total), foreground=C["accent"] if total > 0 else C["ink2"])
        flags = []
        if sc.get("outcome") == "protocol_rejected":
            flags.append("✕ rejected by the ledger protocol: " + str(sc.get("reason", "")))
        else:
            flags.append("✓ complete month close" if sc.get("complete") else "incomplete")
            flags.append("✓ renderable" if sc.get("renderable") else "✕ not renderable")
            flags.append("✕ gated by a bookkeeping defect" if sc.get("gated") else "not gated")
            for b in sc.get("blocked_by") or []:
                flags.append("blocked: " + b)
        if rv and r.revisions and rv.index == r.revisions[-1].index and rv.index > 0 and (not r.live or r.status == "done"):
            flags.append("final delivery")
        self.flags.configure(text="   ".join(flags))
        # meter
        m = self.meter
        m.delete("all")
        m.update_idletasks()
        W = max(240, m.winfo_width() or 320)
        x0, x1, y, hgt = 12, W - 12, 13, 10

        def X(v):
            return x0 + max(0.0, min(1.0, v)) * (x1 - x0)
        m.create_line(x0, y + hgt + 4, x1, y + hgt + 4, fill=C["rule"])
        for v in (0, 0.25, 0.5, 0.75, 1):
            m.create_line(X(v), y + hgt + 4, X(v), y + hgt + 9, fill=C["rule"])
            m.create_text(X(v), y + hgt + 18, text=f"{v:.2f}", fill=C["ink2"], font=("Consolas", 8), anchor="n" if 0 < v < 1 else ("nw" if v == 0 else "ne"))
        t_, e_ = WEIGHT_TARGETS * th, WEIGHT_RESOLVED * er
        if t_ > 0:
            m.create_rectangle(X(0), y, X(t_) - 1, y + hgt, fill=C["series1"], outline="")
        if e_ > 0:
            m.create_rectangle(X(t_) + 1, y, X(t_ + e_), y + hgt, fill=C["series2"], outline="")
        if pen < 0 and t_ + e_ > 0:
            m.create_rectangle(X(max(0, t_ + e_ + pen)), y - 3, X(t_ + e_), y + hgt + 3, fill=C["crit"], outline="")
        m.create_line(X(total), y - 6, X(total), y + hgt + 4, fill=C["ink"], width=2)
        m.create_text(X(total) + (-4 if total > 0.85 else 4), y - 7, text=f"total {total:.3f}", fill=C["ink"], font=("Consolas", 9, "bold"), anchor="se" if total > 0.85 else "sw")

        def fill_formula(w):
            w.tag_configure("mono", font=("Consolas", 8))
            w.tag_configure("s1", foreground=C["series1"], font=("Segoe UI", 9, "bold"))
            w.tag_configure("s2", foreground=C["series2"], font=("Segoe UI", 9, "bold"))
            w.tag_configure("s3", foreground=C["crit"], font=("Segoe UI", 9, "bold"))
            n_acct = len((r.task or {}).get("scored_accounts") or [])
            n_hit = n_acct - len(sc.get("target_misses") or []) if n_acct else "?"
            items = sc.get("item_states") or {}
            w.insert("end", "■ ", "s1"); w.insert("end", f"targets {n_hit}/{n_acct}  ", ""); w.insert("end", f"0.70 × {th:.3f} = {t_:.3f}\n", "mono")
            w.insert("end", "■ ", "s2"); w.insert("end", f"resolved {sum(1 for s in items.values() if s == 'RESOLVED')}/{len(items)}  ", ""); w.insert("end", f"0.30 × {er:.3f} = {e_:.3f}\n", "mono")
            w.insert("end", "■ ", "s3"); w.insert("end", "penalties ", ""); w.insert("end", f"{pen:.2f}", "mono")
            if sc.get("gated"):
                w.insert("end", "  · gated → 0", "")
            elif not sc.get("renderable", True):
                w.insert("end", "  · not renderable → 0", "")
            w.insert("end", "  · clamped [0,1] = ", ""); w.insert("end", f"{total:.3f}", "mono")
        self._set(self.formula, fill_formula)

        planted = (r.task or {}).get("planted") or []

        def fill_planted(w):
            items = sc.get("item_states") or {}
            if not items:
                w.insert("end", "none in this task", "dim")
            for pid, st in items.items():
                p = next((x for x in planted if x["id"] == pid), {"id": pid, "description": "", "required_postings": [], "date": "", "must_be_payee": []})
                w.insert("end", f" {st} ", st if st in ("RESOLVED", "MISSING") else "other")
                w.insert("end", "  " + pid + "\n", "name")
                if p.get("description"):
                    w.insert("end", p["description"] + "\n")
                if p.get("required_postings"):
                    payee = " or ".join(f'"{x}"' for x in p.get("must_be_payee") or [])
                    w.insert("end", f"{p.get('date', '')}{'  payee ' + payee if payee else ''}\n", "mono")
                    for acct, amt in p["required_postings"]:
                        w.insert("end", f"  {acct}  {fmt_money(amt)}\n", "mono")
                when = next((x.turn for x in r.revisions if x.index > 0 and (x.score or {}).get("item_states", {}).get(pid) == "RESOLVED"), None)
                if st == "RESOLVED":
                    w.insert("end", f"first resolved on turn {when}\n\n" if when else "resolved\n\n", "dim")
                elif when and rv.index > 0 and when < rv.turn:
                    w.insert("end", f"was resolved on turn {when}, not in this revision\n\n", "dim")
                elif when:
                    w.insert("end", f"not yet posted; resolved later, on turn {when}\n\n", "dim")
                else:
                    w.insert("end", "not posted as its own dated entry\n\n", "dim")
        self._set(self.planted, fill_planted)

        self.acct.delete(*self.acct.get_children())
        misses = {}
        for s in sc.get("target_misses") or []:
            mm = re.match(r"^(.*?): expected (-?[0-9.]+), got (-?[0-9.]+)$", s)
            if mm:
                misses[mm.group(1)] = (mm.group(2), mm.group(3))
        accounts = (r.task or {}).get("scored_accounts") or list(misses)
        expected = (r.task or {}).get("expected_balances") or {}
        for acct in accounts:
            if acct in misses:
                self.acct.insert("", "end", values=(acct, fmt_money(misses[acct][0]), fmt_money(misses[acct][1]), "✕ miss"), tags=("miss",))
            else:
                self.acct.insert("", "end", values=(acct, fmt_money(expected.get(acct)), fmt_money(expected.get(acct)), "✓ hit"))
        coll = sc.get("collateral_damage") or []
        self.acct_note.configure(text=("Collateral: " + "; ".join(coll)) if coll else "Every other account came out unchanged.")

        def fill_pen(w):
            any_ = False
            for key, label, each, once in PENALTIES:
                lbls = sc.get(key) or []
                n = len(lbls)
                any_ = any_ or n > 0
                w.insert("end", f"{label}{' ×' + str(n) if n else ''}", "hit" if n else "")
                w.insert("end", f"   {(each if once else each * n):.2f}\n" if n else f"   {each:.2f} {'once' if once else 'each'}\n", "mono")
                for l in lbls:
                    w.insert("end", "   " + l + "\n", "mono")
            self.pen_title.configure(text="Penalties charged" if any_ else "Penalties (none charged)")
        self._set(self.pen, fill_pen)
        self.prov.configure(text=("Scored " + ("live, the moment the write was committed, " if r.live else "offline for every revision, including the untouched original, ")
                                  + "by beancount_ledger.candidate.committed.score_committed (engine candidate/1) — the same function the environment calls at episode end. "
                                  + (f"The final reward recorded for this rollout is {fmt_score(r.reward)}; it is the score of the last committed revision, not the best one. " if r.reward is not None else "")
                                  + "No model judged anything here."))


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------
def selftest() -> int:
    """Headless: run the demo agent through the live engine and print every event."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # the tables carry "−" and "·"; a cp125x console must not abort the test
    url = start_demo_server()
    events: queue.Queue = queue.Queue()
    run = LiveRun({"base_url": url, "api_key": "demo", "model": "demo/scripted-agent", "task": DEFAULT_TASK, "max_tokens": 4000, "save": False}, events)
    run.start()
    deadline = time.time() + 120
    final = None
    while time.time() < deadline:
        try:
            ev = events.get(timeout=1)
        except queue.Empty:
            continue
        brief = {k: (v if k not in ("text", "original", "system_prompt", "row", "task", "results", "content", "reasoning") else f"<{len(json.dumps(v, default=str))} chars>") for k, v in ev.items()}
        if ev["type"] == "revision":
            brief["score"] = {k: ev["score"].get(k) for k in ("reward", "outcome", "complete", "item_states")}
        print(json.dumps(brief, default=str))
        if ev["type"] in ("done", "error", "stopped"):
            final = ev
            break
    if not final or final["type"] != "done":
        print("SELFTEST FAILED:", final)
        return 1
    ok = final.get("reward") == 1.0 and final.get("stop") == "piv_submitted"
    print("SELFTEST live run", "OK" if ok else "FAILED", "reward", final.get("reward"), "stop", final.get("stop"))
    problems = selftest_offline()
    for p in problems:
        print("SELFTEST FAILED:", p)
    print("SELFTEST", "OK" if ok and not problems else "FAILED")
    return 0 if ok and not problems else 1


def selftest_offline() -> list[str]:
    """The pieces that need no model: aggregation over a synthetic outputs/evals tree, the export
    writer, the schema shim and the error hints. Returns the problems found (empty = pass)."""
    import shutil  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    problems = []

    def check(cond, what):
        if not cond:
            problems.append(what)

    def row(task, reward, turns, out_tokens, stop="piv_submitted", error=None):
        return {"info": {"task_id": task}, "reward": reward, "stop_condition": stop, "error": error,
                "metrics": {"num_turns": turns}, "token_usage": {"input_tokens": 10 * out_tokens, "output_tokens": out_tokens},
                "completion": [{"role": "assistant", "content": ""}] * turns}

    tmp = Path(tempfile.mkdtemp(prefix="ledger-replay-selftest-"))
    try:
        evals = tmp / "outputs" / "evals"

        def write_run(model_dir, run_id, rows, meta_extra=None, quarantined=False):
            d = (evals / "quarantined" / model_dir / run_id) if quarantined else (evals / model_dir / run_id)
            d.mkdir(parents=True)
            meta = {"model": model_dir.split("--", 1)[1].replace("--", "/"), "base_url": "http://x/v1", "time": 1.0}
            meta.update(meta_extra or {})
            (d / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
            (d / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

        write_run("beancount-ledger--acme--alpha", "r1", [row("bank_recon_001", 1.0, 7, 7000), row("bank_recon_001", 0.7, 9, 9000), row("ap_payment_run_001", 1.0, 11, 12000)])
        write_run("beancount-ledger--acme--alpha", "r2", [row("bank_recon_001", 0.0, 25, 40000, stop="has_error", error="boom")])
        write_run("beancount-ledger--acme--alpha", "r3", [row("payroll_001", 1.0, 5, 3000)], meta_extra={"budget": {"max_turns": 60, "max_episode_output_tokens": 120000, "default": False}})
        write_run("beancount-ledger--beta--bravo", "q1", [], quarantined=True)
        write_run("beancount-ledger--beta--bravo", "r4", [row("bank_recon_001", 0.3, 12, 20000)])
        (evals / "exports").mkdir()
        records = load_run_records(evals)
        check(len(records) == 5, f"expected 5 run records, got {len(records)}")
        s = summarize_runs(records)
        by = {m["model"]: m for m in s["models"]}
        a, b = by.get("acme/alpha"), by.get("beta/bravo")
        check(a is not None and b is not None, f"models missing from the summary: {sorted(by)}")
        if a:
            check(a["runs"] == 4 and a["failed"] == 1, f"acme/alpha runs/failed = {a['runs']}/{a['failed']}, expected 4/1")
            check(abs(a["mean_reward"] - (1.0 + 0.7 + 1.0 + 1.0) / 4) < 1e-9, f"acme/alpha mean reward {a['mean_reward']}")
            check(a["strict"] == 3 and abs(a["strict_rate"] - 0.75) < 1e-9, f"acme/alpha strict {a['strict']} rate {a['strict_rate']}")
            check(a["median_turns"] == 8, f"acme/alpha median turns {a['median_turns']}, expected 8")
            check(a["median_output_tokens"] == 8000, f"acme/alpha median output tokens {a['median_output_tokens']}, expected 8000")
            check(a["non_default_budget"] == 1, f"acme/alpha non-default budget runs {a['non_default_budget']}, expected 1")
        if b:
            check(b["runs"] == 1 and b["failed"] == 1, f"beta/bravo runs/failed = {b['runs']}/{b['failed']}, expected 1/1 (one quarantined folder)")
        tasks = {t["task"]: t["cells"] for t in s["tasks"]}
        check(set(tasks) == {"bank_recon_001", "ap_payment_run_001", "payroll_001"}, f"task rows {sorted(tasks)}")
        cell = tasks.get("bank_recon_001", {}).get("acme/alpha")
        check(cell is not None and cell["n"] == 2 and abs(cell["reward"] - 0.85) < 1e-9, f"bank_recon_001 × acme/alpha cell {cell}")
        check("beta/bravo" in tasks.get("bank_recon_001", {}) and "beta/bravo" not in tasks.get("payroll_001", {}), "per-task grid has a cell where no run exists")
        timeline = {"run_id": "r1", "model": "acme/alpha", "task": "bank_recon_001", "reward": 1.0, "stop": "piv_submitted",
                    "budget": {"max_turns": 25, "max_episode_output_tokens": 40000, "default": True},
                    "rows": [{"turn": 1, "kind": "turn", "tools": "list_files", "ledger": "", "score": None, "secs": 0.5},
                             {"turn": 2, "kind": "turn", "tools": "write_ledger", "ledger": "rev 1: +3 −1", "score": 1.0, "secs": 1.25}]}
        paths = write_exports(s, timeline, exports_dir=evals / "exports", stamp="selftest")
        md, csv_text = (evals / "exports" / "selftest.md"), (evals / "exports" / "selftest.csv")
        check(md.exists() and csv_text.exists(), f"export files missing: {paths}")
        md_text = md.read_text(encoding="utf-8")
        check("| acme/alpha | 4 | 0.925 | 3 (75%) | 8 | 8,000 | 1 | 1 |" in md_text, "markdown model row is not as expected:\n" + md_text)
        check("| bank_recon_001 | 0.850 (n=2) | 0.300 (n=1) |" in md_text, "markdown task row is not as expected:\n" + md_text)
        check("| 2 | turn | write_ledger | rev 1: +3 −1 | 1.000 | 1.2 s |" in md_text, "markdown timeline row is not as expected:\n" + md_text)
        check("\r" not in md.read_bytes().decode("utf-8"), "markdown export has CR line endings")
        lines = csv_text.read_text(encoding="utf-8").splitlines()
        check(lines[0].startswith("model,runs,mean_reward") and "acme/alpha,4,0.925000,3,0.7500,8,8000,1,1" in lines, "csv model block is not as expected:\n" + "\n".join(lines))
        check("task,acme/alpha,beta/bravo" in lines and "bank_recon_001,0.850000,0.300000" in lines, "csv task block is not as expected:\n" + "\n".join(lines))
        check("2,turn,write_ledger,rev 1: +3 −1,1.0,1.25" in lines, "csv timeline block is not as expected:\n" + "\n".join(lines))
        check(load_run_records(evals) and summarize_runs(load_run_records(evals))["records"] == 5, "exports folder must not count as a run")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # the schema shim: an explicit empty properties, no empty required, strict off; the input untouched
    tools = [{"type": "function", "function": {"name": "submit", "strict": True, "parameters": {"type": "object", "required": [], "additionalProperties": False}}},
             {"type": "function", "function": {"name": "read_file", "strict": True, "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]
    shimmed = shim_tool_schemas(tools)
    p0, p1 = shimmed[0]["function"]["parameters"], shimmed[1]["function"]["parameters"]
    check(p0.get("properties") == {} and "required" not in p0 and shimmed[0]["function"]["strict"] is False, f"shim on a parameterless tool: {shimmed[0]}")
    check(p1.get("required") == ["path"] and shimmed[1]["function"]["strict"] is False, f"shim on read_file: {shimmed[1]}")
    check(tools[0]["function"]["strict"] is True and "properties" not in tools[0]["function"]["parameters"], "shim mutated the environment's tool definitions")

    # the hints learned this week
    cases = [
        ("Error code: 400 - {'error': {'message': \"tool schema: 'required' present but 'properties' is missing\"}}", "Strict-schema"),
        ("Error code: 400 - property 'reasoning_content' is unsupported", "Replay hidden reasoning"),
        ("Error code: 413 - Request too large for model: tokens per minute (TPM) limit 6000", "free tier"),
        ("Error code: 429 - Rate limit reached: tokens per minute (TPM)", "free tier"),
        ("1 validation error for ChatCompletion choices.0.finish_reason Input should be 'stop', 'length', 'tool_calls', 'content_filter' or 'function_call' [type=literal_error]", "partial"),
        ("Error code: 504 - <html>Gateway Time-out</html>", "retried 3 times"),
        ("Error code: 503 - Too Many Requests", "overloaded"),
        ("Error code: 429 - insufficient_quota", "quota"),
    ]
    for chain, needle in cases:
        got = explain_provider_error(chain, retries=3) or ""
        check(needle.lower() in got.lower(), f"hint for {chain[:60]!r} lacks {needle!r}: {got}")
    check("sk-secret" not in (explain_provider_error("Error code: 401 - key sk-secret invalid") or "").split("→")[1], "the hint text must not carry key material")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Ledger Replay desktop window")
    parser.add_argument("--demo", action="store_true", help="start a local scripted agent and prefill the form with it")
    parser.add_argument("--selftest", action="store_true", help="headless end-to-end run against the scripted agent; exit 0 on success")
    parser.add_argument("--autorun", action="store_true", help=argparse.SUPPRESS)  # with --demo: press Run on open
    parser.add_argument("--layout-probe", metavar="WxH", help=argparse.SUPPRESS)  # off-screen window at WxH, demo run, print overflow report, exit
    parser.add_argument("--classic", action="store_true", help="use the plain tkinter window instead of the web-rendered one")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if sys.platform == "win32":
        try:
            import ctypes  # noqa: PLC0415
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    if args.layout_probe:
        return layout_probe(tuple(int(x) for x in args.layout_probe.lower().split("x")))
    if not args.classic:
        try:
            import webview  # noqa: F401, PLC0415
        except ImportError:
            print("pywebview is not installed; opening the classic window (uv pip install pywebview for the modern one)", file=sys.stderr)
        else:
            import replay_webview  # noqa: PLC0415
            return replay_webview.main(demo=args.demo, autorun=args.autorun)
    demo_url = start_demo_server() if args.demo else None
    app = App(demo_url=demo_url)
    app.lift()
    app.attributes("-topmost", True)
    app.after(800, lambda: app.attributes("-topmost", False))
    if args.autorun and demo_url:
        app.after(1500, app._run)
    app.mainloop()
    return 0


def layout_probe(size: tuple[int, int]) -> int:
    """Open the window off-screen at `size`, run the demo, then report every widget whose requested size exceeds its allotted size."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    demo_url = start_demo_server()
    app = App(demo_url=demo_url, probe_size=size)
    app.v_save.set(False)
    app.after(1200, app._run)

    def report():
        if app.live is not None:
            app.after(300, report)
            return
        app.update_idletasks()
        rows = []

        def walk(w, depth=0):
            try:
                rw, rh, aw, ah = w.winfo_reqwidth(), w.winfo_reqheight(), w.winfo_width(), w.winfo_height()
            except tk.TclError:
                return
            name = f"{type(w).__name__}:{str(w).split('.')[-1]}"
            if w.winfo_manager() and (rw > aw + 2 or rh > ah + 2) and aw > 1:
                rows.append(f"OVERFLOW {'  ' * depth}{name}: needs {rw}x{rh}, has {aw}x{ah}")
            for c in w.winfo_children():
                walk(c, depth + 1)
        walk(app)
        print(f"window {app.winfo_width()}x{app.winfo_height()}  status: {app.status.cget('text')}")
        print(f"tiles: needs {app.tiles.winfo_reqwidth()} has {app.tiles.winfo_width()}")
        print(f"scorer pane: {app.scorer.winfo_width()}x{app.scorer.winfo_height()} (needs {app.scorer.winfo_reqwidth()}x{app.scorer.winfo_reqheight()})")
        print(f"ledger text: {app.ledger.text.winfo_width()}x{app.ledger.text.winfo_height()}  turns tree: {app.tree.winfo_width()}x{app.tree.winfo_height()}")
        print(f"reward tile: {app.tile_vars['reward'].get()}  big: {app.big.cget('text')}  flags: {app.flags.cget('text')[:80]}")
        print(f"rev buttons: {[b.cget('text') for b in app.rev_bar.winfo_children()]}")
        print("\n".join(rows) if rows else "no overflow")
        app.destroy()
    app.after(2000, report)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
