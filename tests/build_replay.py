"""Build docs/replay.html: a self-contained replay viewer for committed vf-eval transcripts.

    python tests/build_replay.py            # rebuild docs/replay.html from outputs/evals/**/results.jsonl
    python tests/build_replay.py --check    # also assert every rollout's final revision re-scores to its recorded reward

What the page shows is the transcript as vf-eval saved it, plus one thing the
transcript does not carry: the scorer's component breakdown for EVERY ledger
revision the agent wrote (and for the untouched original). Those numbers are
produced here by the production scorer itself — the same call chain the
environment runs at episode end (write_ledger -> parse_once -> commit ->
score_committed, see beancount_ledger.py `score_core`) — never by a JavaScript
re-implementation. The page renders what this script embeds.

Only hand-authored tasks (those in `beancount_ledger.graph.worlds.REGISTRY`)
can be scored offline; generated selectors need the evaluator secret and are
embedded unscored (the page then shows the recorded reward only).

Inputs:  outputs/evals/<env--model>/<run-id>/{metadata.json,results.jsonl}
         docs/replay.template.html
Output:  docs/replay.html (the template with __REPLAY_DATA__ replaced by JSON)

The output is static: it works from file://, from GitHub Pages, and as a
pasted artifact. No network access is needed to view it (fonts excepted).
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from beancount_ledger.beancount_ledger import digests_of, logical_text  # noqa: E402
from beancount_ledger.candidate.committed import (  # noqa: E402
    commit,
    load_contract,
    new_receipt,
    reject,
    rejection_result_digest,
    score_committed,
)
from beancount_ledger.candidate.normalise import Accepted, ProtocolFailure, parse_once  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402
from beancount_ledger.task import load_task  # noqa: E402

EVALS = ROOT / "outputs" / "evals"
TEMPLATE = ROOT / "docs" / "replay.template.html"
OUTPUT = ROOT / "docs" / "replay.html"
TASKS = ROOT / "beancount_ledger" / "tasks"
PLACEHOLDER = "__REPLAY_DATA__"

_CONTRACTS: dict[str, tuple] = {}


# --------------------------------------------------------------------------
# scoring: exactly the environment's path, without the tool loop
# --------------------------------------------------------------------------
def contract_for(task_id: str):
    """(LoadedEnvironment, ContractInputs) for a hand-authored task, as load_environment builds them."""
    if task_id not in _CONTRACTS:
        world, task = REGISTRY[task_id]
        _bundle, inputs = derive_contract(world, task)
        _CONTRACTS[task_id] = (load_contract(inputs), inputs)
    return _CONTRACTS[task_id]


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, str):
        return str(value)  # ScorerState is a str subclass; flatten it
    return value


def score_ledger_text(task_id: str, ledger_text: str, *, rollout_id: str, revision: int) -> dict:
    """Score one ledger text the way score_core scores the committed revision.

    rollout_id and revision only enter the receipt digests; they never touch
    the reward, the components or any diagnostic list.
    """
    env, _inputs = contract_for(task_id)
    raw = ledger_text.encode("utf-8", errors="strict")
    digests = digests_of(raw, submitted=ledger_text)
    outcome = parse_once(logical_text(raw))
    receipt = new_receipt(rollout_id, revision, digests)
    if isinstance(outcome, Accepted):
        committed = commit(outcome, env, receipt)
        result = score_committed(committed)
        result.verify()
        out = _jsonable(result.as_dict())
        out["reward"] = float(result.total)
        out["outcome"] = "delivered" if result.renderable else "policy_blocked"
        out["result_digest"] = result.result_digest
        return out
    if isinstance(outcome, ProtocolFailure):
        rejected = reject(outcome, env, receipt)
        return {
            "reward": 0.0,
            "outcome": "protocol_rejected",
            "reason": str(getattr(rejected, "reason", "")),
            "detail": str(getattr(rejected, "detail", "")),
            "result_digest": rejection_result_digest(rejected),
            "engine": "candidate/1",
        }
    return {"reward": 0.0, "outcome": "evaluator_failure", "detail": repr(outcome)[:400], "engine": "candidate/1"}


# --------------------------------------------------------------------------
# transcript walking (mirrors the page's normaliser: same revision numbering)
# --------------------------------------------------------------------------
def _decode_call(tc):
    call = tc
    if isinstance(call, str):
        try:
            call = json.loads(call)
        except json.JSONDecodeError:
            return {"id": "?", "name": "unparseable", "args": {}}
    if isinstance(call, dict) and "function" in call:
        call = {"id": call.get("id"), "name": call["function"].get("name"), "arguments": call["function"].get("arguments")}
    args = call.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {"_raw": args}
    return {"id": call.get("id"), "name": call.get("name") or "?", "args": args if isinstance(args, dict) else {}}


def _attestation(result):
    if not isinstance(result, str):
        return None
    head = result.split("\n", 1)[0]
    try:
        att = json.loads(head)
    except json.JSONDecodeError:
        return None
    return att if isinstance(att, dict) and "committed" in att else None


def revisions_of(row: dict) -> list[dict]:
    """[{index, turn, text}] for every attested write_ledger call, in transcript order."""
    comp = row.get("completion") or []
    out, rev, i, turn = [], 0, 0, 0
    while i < len(comp):
        msg = comp[i]
        turn += 1
        if msg.get("role") != "assistant":
            i += 1
            continue
        calls = [_decode_call(tc) for tc in (msg.get("tool_calls") or [])]
        i += 1
        results = {}
        while i < len(comp) and comp[i].get("role") == "tool":
            results[comp[i].get("tool_call_id")] = comp[i].get("content")
            i += 1
        for call in calls:
            if call["name"] != "write_ledger":
                continue
            att = _attestation(results.get(call["id"]))
            if att and att.get("committed"):
                rev += 1
                content = call["args"].get("content")
                out.append({"index": rev, "turn": turn, "text": content if isinstance(content, str) else ""})
    return out


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------
def discover_runs() -> list[dict]:
    runs = []
    for results in sorted(EVALS.glob("*/*/results.jsonl")):
        run_dir = results.parent
        meta_path = run_dir / "metadata.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        rows = []
        for line in results.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        if not rows:
            print(f"skipping {run_dir.relative_to(ROOT)}: no rollouts recorded (a stopped or failed run)", file=sys.stderr)
            continue
        for row in rows:
            row.pop("tool_defs", None)  # identical in every row; the page does not need it
        model = meta.get("model") or run_dir.parent.name
        runs.append({
            "id": run_dir.name,
            "dir": str(run_dir.relative_to(ROOT)).replace("\\", "/"),
            "label": f"{model.split('/')[-1]} · run {run_dir.name} · {len(rows)} rollout{'s' if len(rows) != 1 else ''}",
            "model": model,
            "base_url": meta.get("base_url", ""),
            "time": meta.get("time"),
            "avg_reward": meta.get("avg_reward"),
            "max_tokens": (meta.get("sampling_args") or {}).get("max_tokens"),
            "vf_version": (meta.get("version_info") or {}).get("vf_version"),
            "rows": rows,
        })
    return runs


def task_display(task_id: str) -> dict:
    """Public task facts for the page: what the scorer expects, phrased for a reader."""
    env, inputs = contract_for(task_id)
    descriptions: dict[str, dict] = {}
    json_path = TASKS / f"{task_id}.json"
    if json_path.exists():
        archived = load_task(json_path)
        descriptions = {p["id"]: p for p in archived.get("planted", [])}
        trap_desc = {t["id"]: t for t in archived.get("traps", [])}
    else:
        trap_desc = {}
    planted = []
    for p in inputs.planted:
        d = descriptions.get(p.id, {})
        planted.append({
            "id": p.id,
            "date": p.date,
            "description": d.get("description", getattr(p, "narration", "")),
            "required_postings": [[acct, str(Decimal(amt))] for acct, amt in p.required],
            "must_be_payee": list(p.must_be_payee),
            "kind": getattr(p, "kind", ""),
        })
    traps = []
    for t in inputs.traps:
        d = trap_desc.get(t.id, {})
        traps.append({"id": t.id, "date": t.date, "narration": t.narration, "description": d.get("description", t.narration)})
    return {
        "id": task_id,
        "type": inputs.task_type,
        "prompt": inputs.prompt,
        "period": dataclasses.asdict(inputs.period) if dataclasses.is_dataclass(inputs.period) else str(inputs.period),
        "currency": inputs.currency,
        "statement_closing_balance": str(inputs.statement_closing),
        "scored_accounts": list(inputs.scored_accounts),
        "expected_balances": {acct: str(v) for acct, v in inputs.expected_balances},
        "allowed_accounts": list(inputs.allowed_accounts),
        "planted": planted,
        "traps": traps,
        "environment_digest": getattr(env, "environment_digest", None),
    }


def git_head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001 - provenance is best-effort
        return None


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def build(check: bool) -> int:
    runs = discover_runs()
    if not runs:
        # A fresh checkout has no runs: build the page anyway, with an empty
        # picker, so the desktop app can open and record its first one.
        if check:
            print(f"no results.jsonl under {EVALS}: nothing to check")
            return 0
        template = TEMPLATE.read_text(encoding="utf-8")
        if PLACEHOLDER not in template:
            print(f"{TEMPLATE}: placeholder {PLACEHOLDER} missing", file=sys.stderr)
            return 2
        empty = json.dumps({"runs": [], "tasks": {}, "built": None}, ensure_ascii=False)
        OUTPUT.write_text(template.replace(PLACEHOLDER, empty), encoding="utf-8", newline="\n")
        print(f"no results.jsonl under {EVALS}; wrote {OUTPUT} with an empty run picker")
        return 0
    scores: dict[str, dict] = {}
    task_ids: set[str] = set()
    unscored: list[str] = []
    mismatches: list[str] = []
    table: list[tuple] = []
    for run in runs:
        for idx, row in enumerate(run["rows"]):
            task_id = (row.get("info") or {}).get("task_id") or row.get("answer")
            if task_id not in REGISTRY:
                unscored.append(f"{run['id']}/{idx}: task {task_id!r} is not hand-authored; embedded without offline scores")
                continue
            task_ids.add(task_id)
            _env, inputs = contract_for(task_id)
            rid = f"replay:{run['id']}:{idx}"
            scores[f"{run['id']}/{idx}/0"] = score_ledger_text(task_id, inputs.original_text, rollout_id=rid, revision=0)
            revs = revisions_of(row)
            for rv in revs:
                scores[f"{run['id']}/{idx}/{rv['index']}"] = score_ledger_text(task_id, rv["text"], rollout_id=rid, revision=rv["index"])
            recorded = row.get("reward")
            final = scores[f"{run['id']}/{idx}/{revs[-1]['index']}"]["reward"] if revs else 0.0
            table.append((run["id"], idx, task_id, len(revs), recorded, final))
            if recorded is not None and abs(float(recorded) - float(final)) > 1e-6:
                mismatches.append(f"{run['id']}/{idx}: recorded reward {recorded} but the last revision re-scores to {final}")
    if len(task_ids) > 1:
        print(f"note: {len(task_ids)} different tasks; the page describes the first ({sorted(task_ids)[0]})", file=sys.stderr)
    task = task_display(sorted(task_ids)[0]) if task_ids else None
    original = contract_for(task["id"])[1].original_text if task else ""

    payload = {
        "generated": {
            "at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ"),
            "commit": git_head(),
            "engine": "candidate/1",
            "function": "beancount_ledger.candidate.committed.score_committed",
            "builder": "tests/build_replay.py",
        },
        "task": task,
        "original_ledger": original,
        "runs": runs,
        "scores": scores,
        "unscored": unscored,
    }
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=_jsonable)
    data = data.replace("</", "<\\/")  # never close the carrying <script> tag
    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        print(f"{TEMPLATE}: placeholder {PLACEHOLDER} missing", file=sys.stderr)
        return 2
    OUTPUT.write_text(template.replace(PLACEHOLDER, data), encoding="utf-8", newline="\n")

    print(f"{'run':10} {'row':>3} {'task':16} {'revs':>4} {'recorded':>9} {'re-scored':>9}")
    for run_id, idx, task_id, nrev, recorded, final in table:
        print(f"{run_id:10} {idx:>3} {task_id:16} {nrev:>4} {str(recorded):>9} {final:>9.3f}")
    for note in unscored:
        print("unscored:", note)
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size:,} bytes; {len(runs)} runs, {sum(len(r['rows']) for r in runs)} rollouts, {len(scores)} scored revisions)")
    if mismatches:
        for m in mismatches:
            print("MISMATCH:", m, file=sys.stderr)
        if check:
            return 1
    elif check:
        print("check: every rollout's last committed revision re-scores to its recorded reward")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if any recorded reward differs from the offline re-score")
    args = parser.parse_args()
    sys.exit(build(check=args.check))
