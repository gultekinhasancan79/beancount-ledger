"""Is a hard world accounting-hard or budget-hard? Real models, two budgets.

Runs a hosted model (any OpenAI-compatible endpoint; the key is read from an
environment variable and never printed) on a stratified set of generated
worlds under the shipped budget (25 turns / 40,000 output tokens) and under a
looser one, and reports strict solve rate, mean reward, turns and output
tokens per (profile, k) class. No training: calibration only.

The looser arm is built by raising the package's turn cap BEFORE the
environment is loaded (the prompt restates the cap it reads) and by
`load_environment(max_episode_output_tokens=...)`, which restates the
disclosed ceiling and recomputes the episode contract digest; the digest of
each arm is recorded so nobody mistakes a looser run for a benchmark run.

    python tests/budget_calibration.py --production \\
        --model nvidia/nemotron-3-super-120b-a12b --base-url https://integrate.api.nvidia.com/v1 \\
        --key-var NVIDIA_API_KEY --selectors train:0 train:1:hard ... --turns 25 --tokens 40000 --json <out>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PRODUCTION = "--production" in sys.argv
if not PRODUCTION:
    _src = (ROOT / "tests" / "test_generator.py").read_text(encoding="utf-8")
    os.environ.setdefault("PIV_EVAL_SECRET", re.search(r'TEST_SECRET = "([0-9a-f]{64})"', _src).group(1))
    os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")
os.environ.setdefault("HF_DATASETS_DISABLE_PROGRESS_BARS", "1")
try:
    import datasets as _datasets
    _datasets.disable_progress_bar()
except Exception:                           # noqa: BLE001
    pass

from verifiers.legacy.clients import OpenAIChatCompletionsClient  # noqa: E402
from verifiers.legacy.types import ClientConfig  # noqa: E402

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402


def relax_response_literals() -> None:
    """The OpenAI SDK's response models hold closed literals that some
    OpenAI-compatible providers do not respect: Groq answers
    `service_tier: "on_demand"`, Gemini a `finish_reason` of its own. The
    provider's answer is otherwise a normal completion, so for calibration
    those two fields accept any string. Calibration only; never the
    environment."""
    from typing import Optional
    from openai.types.chat import chat_completion as _cc
    for model, field in ((_cc.ChatCompletion, "service_tier"), (_cc.Choice, "finish_reason")):
        if field in model.model_fields:
            model.model_fields[field].annotation = Optional[str]
            model.model_rebuild(force=True)


relax_response_literals()


class TolerantClient(OpenAIChatCompletionsClient):
    """The provider quirks tests/replay_desktop.py learned the hard way: an
    assistant message with `content: null` or `tool_calls: null` is rejected
    by several OpenAI-compatible endpoints."""

    async def to_native_prompt(self, messages):
        native, extra = await super().to_native_prompt(messages)
        for m in native:
            if not isinstance(m, dict) or m.get("role") != "assistant":
                continue
            if m.get("content") is None:
                m["content"] = ""
            m.pop("reasoning_content", None)         # Groq: "property 'reasoning_content' is unsupported"
            for key in [k for k, v in m.items() if v is None]:
                m.pop(key, None)
        return native, extra

    @staticmethod
    def _with_properties(native):
        # (verifiers 0.3.1's legacy client has no to_native_tools hook: the wire tools
        # reach get_native_response directly, so that is the only place to shim them;
        # --tool-schema-fix at the source is what actually carried the Groq runs.)
        for tool in native or []:
            fn = tool.get("function") if isinstance(tool, dict) else getattr(tool, "function", None)
            params = fn.get("parameters") if isinstance(fn, dict) else getattr(fn, "parameters", None)
            if isinstance(params, dict):
                params.setdefault("properties", {})
                if not params["properties"] and params.get("required") == []:
                    params.pop("required")          # Groq: an empty `required` beside empty `properties` is refused
            if isinstance(fn, dict) and fn.get("strict"):
                fn["strict"] = False                # Groq validates calls against `required` under strict mode, so an
                                                    # omitted optional argument (read_file offset/limit) is refused
        return native

    async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
        if tools:
            tools = self._with_properties([dict(t) if isinstance(t, dict) else t for t in tools])
            if os.environ.get("PIV_CALIB_DEBUG"):
                import sys as _s
                print("TOOLS>", [(t.get("function", {}).get("name"), sorted((t.get("function", {}).get("parameters") or {}).keys())) for t in tools if isinstance(t, dict)], file=_s.stderr)
        return await super().get_native_response(prompt, model, sampling_args, tools=tools, **kwargs)


_ORIGINAL_TOOL_DEFS = env_mod.public_tool_defs


def _tool_defs_with_properties():
    """Groq refuses a parameterless tool whose schema carries `required: []`
    beside an empty `properties` (list_files, run_beancount, submit after the
    hidden workspace argument is filtered out): its validator reads the empty
    object as missing. For calibration the empty `required` is dropped here,
    at the source every request path reads; the episode contract digest of the
    run records the changed schema. The environment itself is unchanged: the
    fix belongs there under an episode-contract version bump. Contract 3 made
    that change in `public_tool_defs`, so this is a no-op on a current tree;
    it stays so that an older tree can still be measured against Groq."""
    defs = _ORIGINAL_TOOL_DEFS()
    for t in defs:
        params = t.parameters
        if isinstance(params, dict):
            params.setdefault("properties", {})
            if not params["properties"] and params.get("required") == []:
                params.pop("required")
    return defs


# Everything a budget arm needs archived. The runner used to keep the reward and
# the stop label and nothing else, so a row could not say what cap produced it —
# the setting the calibration exists to calibrate was the one field it dropped.
# `piv_request_max_tokens` is the per-turn cap the environment INTENDED for each
# turn (already clamped to what was left of the episode ceiling), so a row now
# carries the wire caps rather than the launcher's claim about them; the
# truncation and no-tool counters separate "ran out of room" from "stopped
# calling tools"; `piv_revision` is how many ledgers the agent actually wrote.
DIAGNOSTIC_STATE_COLUMNS = [
    "piv_observation_bytes", "piv_phase", "piv_score", "piv_request_max_tokens",
    "piv_consecutive_truncated_turns", "piv_no_tool_truncated_turns", "piv_no_tool_turns",
    "piv_truncation_limit_reached", "piv_no_tool_limit_reached", "piv_output_budget_exhausted",
    "piv_output_budget_deferred", "piv_revision", "piv_ledger_receipts", "piv_submitted",
    "piv_episode_contract_digest", "piv_turn",
    # the episode's workspace outlives the rollout; a sidecar reads the final ledger from it
    "workspace",
]


def run_one(selector: str, args) -> dict:
    t0 = time.time()
    env_mod.public_tool_defs = _tool_defs_with_properties if args.tool_schema_fix else _ORIGINAL_TOOL_DEFS
    env_mod.MAX_TURNS = args.turns                       # the prompt reads it when the environment is built
    env = env_mod.load_environment(selector, timeout_seconds=float(args.timeout),
                                   max_episode_output_tokens=int(args.tokens))
    client = TolerantClient(ClientConfig(client_type="openai_chat_completions", api_key_var=args.key_var,
                                         api_base_url=args.base_url, timeout=float(args.timeout),
                                         connect_timeout=10.0, max_retries=1))
    try:
        results = asyncio.run(env.evaluate(client=client, model=args.model, sampling_args={"max_tokens": int(args.max_tokens)},
                                           num_examples=1, rollouts_per_example=1, max_concurrent=1, max_retries=0,
                                           save_results=False, state_columns=DIAGNOSTIC_STATE_COLUMNS))
    except env_mod.PIVEvaluationBatchInvalid as exc:
        # the real reason lives in the batch artifact of THIS process; the key never reaches the record
        chain = None
        try:
            for rec in env_mod.quarantine_artifact(exc.batch_id):
                out = rec.get("output") if isinstance(rec, dict) else None
                err = out.get("error") if isinstance(out, dict) else None
                chain = (err.get("error_chain_repr") or err.get("message") or str(err)) if isinstance(err, dict) else (str(err) if err else None)
                if chain:
                    break
        except Exception as inner:                          # noqa: BLE001
            chain = f"artifact unavailable: {type(inner).__name__}"
        secret = os.environ.get(args.key_var, "")
        chain = (chain or str(exc)).replace(secret, "***") if secret else (chain or str(exc))
        return {"selector": selector, "k": len(env.contract.planted),
                "profile": "hard" if selector.endswith(":hard") else "standard",
                "reward": None, "quarantined": chain[:600], "secs": round(time.time() - t0)}
    out = results["outputs"][0]
    metrics = out.get("metrics") or {}
    usage = out.get("token_usage") or {}
    return {"selector": selector, "k": len(env.contract.planted),
            "profile": "hard" if selector.endswith(":hard") else "standard",
            "reward": out.get("reward"), "stop": out.get("stop_condition"), "error": (str(out.get("error"))[:160] if out.get("error") else None),
            "turns": metrics.get("num_turns", len(out.get("trajectory") or [])),
            "output_tokens": usage.get("output_tokens", usage.get("completion_tokens")) or 0,
            "observation_bytes": out.get("piv_observation_bytes"), "phase": out.get("piv_phase"),
            "contract_digest": getattr(env, "_episode_contract_digest", None), "secs": round(time.time() - t0),
            # the arm's own settings, so a row is self-describing and two rows can
            # be pooled (or refused) on their contents rather than on a memory of
            # how they were launched
            "per_turn_cap": int(args.max_tokens), "episode_ceiling": int(args.tokens), "max_turns": int(args.turns),
            "request_max_tokens": out.get("piv_request_max_tokens"),
            # the stop label is not the diagnosis: an episode can end at the ceiling
            # and still have delivered, so the counters are kept beside it
            "truncated_run": out.get("piv_consecutive_truncated_turns"),
            "no_tool_truncated_turns": out.get("piv_no_tool_truncated_turns"),
            "no_tool_turns": out.get("piv_no_tool_turns"),
            "truncation_limit_reached": out.get("piv_truncation_limit_reached"),
            "no_tool_limit_reached": out.get("piv_no_tool_limit_reached"),
            "budget_exhausted": out.get("piv_output_budget_exhausted"),
            "budget_deferred": out.get("piv_output_budget_deferred"),
            "ledger_revisions": out.get("piv_revision"), "ledger_receipts": out.get("piv_ledger_receipts"),
            "submitted": out.get("piv_submitted"), "score": out.get("piv_score"),
            "served_model": args.model, "base_url": args.base_url}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--key-var", required=True, help="name of the environment variable holding the key")
    parser.add_argument("--selectors", nargs="+", required=True)
    parser.add_argument("--turns", type=int, default=env_mod.MAX_TURNS)
    parser.add_argument("--tokens", type=int, default=env_mod.MAX_EPISODE_OUTPUT_TOKENS)
    parser.add_argument("--max-tokens", type=int, default=8000, help="per-turn completion cap sent to the provider")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--tool-schema-fix", action="store_true", help="complete parameterless tool schemas with an empty properties object (Groq)")
    parser.add_argument("--retries", type=int, default=8,
                        help="retries of an episode the provider refused for a reason of its own "
                             "(429, 5xx, a timeout): the endpoint's weather, not the model's answer")
    parser.add_argument("--pace", type=float, default=0.0,
                        help="seconds to wait between episodes, to stay inside a free tier's rate limit")
    parser.add_argument("--backoff", type=float, default=90.0, help="seconds to wait before such a retry")
    args = parser.parse_args()
    if not os.environ.get(args.key_var):
        # On Windows a key set with setx (or by the desktop app) lives in the
        # user's environment in the registry, which a shell started earlier
        # does not see; read it from there rather than asking for a new shell.
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
                    value, _ = winreg.QueryValueEx(handle, args.key_var)
                if value:
                    os.environ[args.key_var] = value
            except OSError:
                pass
    if not os.environ.get(args.key_var):
        print(f"{args.key_var} is not set on this machine"); return 2
    label = f"{args.model} @ {args.turns} turns / {args.tokens} tokens"
    print(f"budget calibration: {label}; {len(args.selectors)} worlds")
    t0 = time.time()
    rows = []
    for selector in args.selectors:
        for attempt in range(1, args.retries + 2):
            try:
                r = run_one(selector, args)
            except Exception as exc:                    # noqa: BLE001
                r = {"selector": selector, "crashed": f"{type(exc).__name__}: {exc}"[:200]}
            trouble = str(r.get("quarantined", "")) + str(r.get("crashed", ""))
            transient = any(mark in trouble for mark in
                            ("429", "RateLimit", "500", "502", "503", "504", "Timeout", "timed out",
                             "InternalServerError", "APIConnectionError", "Too Many Requests", "overloaded"))
            if not transient or attempt > args.retries:
                break
            print(f"  {selector:<16} the endpoint refused ({trouble[:70]}); waiting {args.backoff}s "
                  f"(attempt {attempt}/{args.retries})", flush=True)
            time.sleep(args.backoff)
        r["attempts"] = attempt
        rows.append(r)
        if args.pace and selector != args.selectors[-1]:
            time.sleep(args.pace)
        print(f"  {selector:<16} k={r.get('k', '?')} reward={r.get('reward', '?')} turns={r.get('turns', '?')} "
              f"out_tokens={r.get('output_tokens', '?')} stop={r.get('stop', r.get('crashed') or r.get('quarantined'))} {r.get('secs', '')}s", flush=True)
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            # The arm's identity, not just its name: two files are poolable only if
            # every one of these agrees, and the per-turn cap is the one this file
            # used to omit.
            args.json.write_text(json.dumps({"model": args.model, "turns": args.turns, "tokens": args.tokens,
                                             "per_turn_cap": args.max_tokens, "base_url": args.base_url,
                                             "tool_schema_fix": bool(args.tool_schema_fix),
                                             "production": bool(args.production), "rows": rows},
                                            indent=1, default=str), encoding="utf-8")
    ok = [r for r in rows if "k" in r and r.get("reward") is not None]
    print(f"\n{len(rows)} episodes in {(time.time() - t0) / 60:.0f} min; {len(ok)} scored, {len(rows) - len(ok)} failed/quarantined")
    print(f"{'profile':<9} {'k':>2} {'n':>2} {'strict':>6} {'mean reward':>12} {'turns p50':>10} {'tokens p50':>11} {'cap hits':>9}")
    for profile, k in sorted({(r["profile"], r["k"]) for r in ok}):
        rs = [r for r in ok if r["profile"] == profile and r["k"] == k]
        strict = sum(1 for r in rs if r["reward"] == 1.0)
        caps = sum(1 for r in rs if str(r.get("stop", "")).startswith("piv_turn_cap") or "budget" in str(r.get("stop", "")))
        print(f"{profile:<9} {k:>2} {len(rs):>2} {strict:>3}/{len(rs):<2} {statistics.mean(r['reward'] for r in rs):>12.3f} "
              f"{statistics.median(r['turns'] for r in rs):>10.0f} {statistics.median(r['output_tokens'] for r in rs):>11.0f} {caps:>9}")
    if ok:
        print(f"ALL       {'':>2} {len(ok):>2} {sum(1 for r in ok if r['reward'] == 1.0):>3}/{len(ok):<2} "
              f"{statistics.mean(r['reward'] for r in ok):>12.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
