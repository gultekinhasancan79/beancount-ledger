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

    PIV_MANIFEST=~/.piv/manifest_v9.json python tests/budget_calibration.py --production \\
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
            for key in [k for k, v in m.items() if v is None]:
                m.pop(key, None)
        return native, extra


def run_one(selector: str, args) -> dict:
    t0 = time.time()
    env_mod.MAX_TURNS = args.turns                       # the prompt reads it when the environment is built
    env = env_mod.load_environment(selector, timeout_seconds=float(args.timeout),
                                   max_episode_output_tokens=int(args.tokens))
    client = TolerantClient(ClientConfig(client_type="openai_chat_completions", api_key_var=args.key_var,
                                         api_base_url=args.base_url, timeout=float(args.timeout),
                                         connect_timeout=10.0, max_retries=1))
    results = asyncio.run(env.evaluate(client=client, model=args.model, sampling_args={"max_tokens": int(args.max_tokens)},
                                       num_examples=1, rollouts_per_example=1, max_concurrent=1, max_retries=0,
                                       save_results=False, state_columns=["piv_observation_bytes", "piv_phase", "piv_score"]))
    out = results["outputs"][0]
    metrics = out.get("metrics") or {}
    usage = out.get("token_usage") or {}
    return {"selector": selector, "k": len(env.contract.planted),
            "profile": "hard" if selector.endswith(":hard") else "standard",
            "reward": out.get("reward"), "stop": out.get("stop_condition"), "error": (str(out.get("error"))[:160] if out.get("error") else None),
            "turns": metrics.get("num_turns", len(out.get("trajectory") or [])),
            "output_tokens": usage.get("output_tokens", usage.get("completion_tokens")) or 0,
            "observation_bytes": out.get("piv_observation_bytes"), "phase": out.get("piv_phase"),
            "contract_digest": getattr(env, "_episode_contract_digest", None), "secs": round(time.time() - t0)}


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
    args = parser.parse_args()
    if not os.environ.get(args.key_var):
        print(f"{args.key_var} is not set in this process"); return 2
    label = f"{args.model} @ {args.turns} turns / {args.tokens} tokens"
    print(f"budget calibration: {label}; {len(args.selectors)} worlds")
    t0 = time.time()
    rows = []
    for selector in args.selectors:
        try:
            r = run_one(selector, args)
        except Exception as exc:                        # noqa: BLE001
            r = {"selector": selector, "crashed": f"{type(exc).__name__}: {exc}"[:200]}
        rows.append(r)
        print(f"  {selector:<16} k={r.get('k', '?')} reward={r.get('reward', '?')} turns={r.get('turns', '?')} "
              f"out_tokens={r.get('output_tokens', '?')} stop={r.get('stop', r.get('crashed'))} {r.get('secs', '')}s", flush=True)
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps({"model": args.model, "turns": args.turns, "tokens": args.tokens,
                                             "rows": rows}, indent=1, default=str), encoding="utf-8")
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
