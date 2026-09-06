"""How much of the episode budget does an agent that KNOWS the answer need?

Four scripted strategies, each played through the real `env.evaluate()` door
with a client that reports realistic output tokens (the tool-call arguments
at four characters a token, plus a small per-turn overhead), so the package's
own turn cap and output-token ceiling bind exactly as they would on a model:

  minimal      list_files, read the ledger, write the golden ledger, submit
  diligent     list_files, read all eight public files, run_beancount, write
               the golden ledger, run_beancount, submit
  incremental  list_files, read all eight files, then ONE write_ledger per
               planted item (the ledger rewritten cumulatively, k writes),
               run_beancount, submit
  sloppy       as incremental, but after every write run_beancount and read
               the ledger back (k writes, k checks, k re-reads)

Measured per (world, strategy): turns, reported output tokens, observation
bytes, reward, stop condition. The question is calibration, not skill: if the
sloppy-but-correct route cannot finish inside 25 turns / 40,000 output tokens
on an eight-item world, the cap is what makes that world hard.

    PIV_MANIFEST=~/.piv/manifest_v9.json python tests/oracle_budget.py --production \\
        --selectors train:3 train:9 ... --json <out>
    python tests/oracle_budget.py --selectors train:0 train:1:hard        (test secret)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
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

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.beancount_ledger import LEDGER, PUBLIC_FILES, load_environment  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.generate import DEFAULT_PROFILE, HARD_PROFILE  # noqa: E402
from beancount_ledger.graph.mint import mint  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402
import reward_lattice_audit as RLA  # noqa: E402  (apply_repairs: the same text edits the lattice audit uses)
import test_episode_contract as tec  # noqa: E402  (calls/empty/TurnScript: the scripted client)

TURN_OVERHEAD_TOKENS = 150      # a short assistant sentence around each tool call
STRATEGIES = ("minimal", "diligent", "incremental", "sloppy")


def golden_for(selector: str) -> str:
    if selector in REGISTRY:
        world, task = REGISTRY[selector]
        return derive_contract(world, task)[1].golden_text
    namespace, index, *rest = selector.split(":")
    return mint(namespace, int(index), HARD_PROFILE if rest else DEFAULT_PROFILE).inputs.golden_text


def script_for(strategy: str, env, golden: str) -> list:
    original = env.public_files[LEDGER].decode("utf-8")
    items = list(env.contract.planted)
    reads = [tec.calls((f"r{i}", "read_file", {"path": name})) for i, name in enumerate(PUBLIC_FILES)]
    turns = [tec.calls(("l1", "list_files", {}))]
    if strategy == "minimal":
        turns += [tec.calls(("r1", "read_file", {"path": LEDGER})),
                  tec.calls(("w1", "write_ledger", {"content": golden})),
                  tec.calls(("s1", "submit", {}))]
        return turns
    turns += reads
    if strategy == "diligent":
        turns += [tec.calls(("b0", "run_beancount", {})),
                  tec.calls(("w1", "write_ledger", {"content": golden})),
                  tec.calls(("b1", "run_beancount", {})),
                  tec.calls(("s1", "submit", {}))]
        return turns
    for n in range(1, len(items) + 1):
        text = RLA.apply_repairs(original, golden, items[:n])
        turns.append(tec.calls((f"w{n}", "write_ledger", {"content": text})))
        if strategy == "sloppy":
            turns.append(tec.calls((f"b{n}", "run_beancount", {})))
            turns.append(tec.calls((f"rr{n}", "read_file", {"path": LEDGER})))
    if strategy == "incremental":
        turns.append(tec.calls(("b1", "run_beancount", {})))
    turns.append(tec.calls(("s1", "submit", {})))
    return turns


def realistic_script(turns):
    """A TurnScript whose reported completion tokens follow the tool-call
    arguments it emits: len(json)/4 plus a per-turn overhead."""
    from verifiers.legacy.types import Response, Usage

    class _Script(tec.TurnScript):
        async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
            self.turn += 1
            message = (self.turns[self.turn - 1] if self.turn <= len(self.turns) else tec.empty())
            args = ""
            for call in (getattr(message, "tool_calls", None) or []):
                fn = getattr(call, "function", None) or call
                args += str(getattr(fn, "arguments", "") or "")
            completion = TURN_OVERHEAD_TOKENS + math.ceil(len(args) / 4)
            usage = Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=completion,
                          total_tokens=10 + completion)
            return Response(id=f"oracle-{self.turn}", created=0, model=model, usage=usage, message=message)

    return _Script(turns)


def play(selector: str, strategy: str) -> dict:
    env = load_environment(selector)
    golden = golden_for(selector)
    turns = script_for(strategy, env, golden)
    client = realistic_script(turns)
    results = asyncio.run(env.evaluate(client=client, model=f"oracle-{strategy}", num_examples=1,
                                       rollouts_per_example=1, max_concurrent=1, save_results=False,
                                       state_columns=["piv_observation_bytes", "piv_phase", "piv_score"]))
    out = results["outputs"][0]
    metrics = out.get("metrics") or {}
    usage = out.get("token_usage") or {}
    return {"selector": selector, "strategy": strategy, "k": len(env.contract.planted),
            "profile": "hard" if selector.endswith(":hard") else ("manual" if selector in REGISTRY else "standard"),
            "planned_turns": len(turns), "turns": metrics.get("num_turns", len(out.get("trajectory") or [])),
            "output_tokens": usage.get("output_tokens", usage.get("completion_tokens")) or 0,
            "observation_bytes": out.get("piv_observation_bytes"), "reward": out.get("reward"),
            "stop": out.get("stop_condition"), "phase": out.get("piv_phase"), "error": out.get("error")}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--selectors", nargs="+", required=True)
    parser.add_argument("--strategies", nargs="*", default=list(STRATEGIES))
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    t0 = time.time()
    rows = []
    for selector in args.selectors:
        for strategy in args.strategies:
            try:
                r = play(selector, strategy)
            except Exception as exc:                # noqa: BLE001
                r = {"selector": selector, "strategy": strategy, "crashed": f"{type(exc).__name__}: {exc}"[:200]}
            rows.append(r)
            print(f"{selector:<16} {strategy:<12} k={r.get('k', '?')} turns={r.get('turns', '?')}/{env_mod.MAX_TURNS} "
                  f"out_tokens={r.get('output_tokens', '?')}/{env_mod.MAX_EPISODE_OUTPUT_TOKENS} "
                  f"obs={r.get('observation_bytes', '?')} reward={r.get('reward', '?')} stop={r.get('stop', r.get('crashed'))}",
                  flush=True)
    print(f"\n{len(rows)} scripted episodes in {time.time() - t0:.0f}s; caps: {env_mod.MAX_TURNS} turns "
          f"({env_mod.MAX_TURNS - 1} executable), {env_mod.MAX_EPISODE_OUTPUT_TOKENS} output tokens")
    print(f"{'profile':<9} {'k':>2} {'strategy':<12} {'n':>2} {'turns p50/max':>14} {'tokens p50/max':>15} {'solved':>7}")
    ok = [r for r in rows if "k" in r]
    classes = sorted({(r["profile"], r["k"]) for r in ok}, key=lambda c: (c[0], c[1]))
    for profile, k in classes:
        for strategy in args.strategies:
            rs = [r for r in ok if r["profile"] == profile and r["k"] == k and r["strategy"] == strategy]
            if not rs:
                continue
            turns = [r["turns"] for r in rs]
            toks = [r["output_tokens"] for r in rs]
            solved = sum(1 for r in rs if r["reward"] == 1.0)
            print(f"{profile:<9} {k:>2} {strategy:<12} {len(rs):>2} {statistics.median(turns):>7.0f}/{max(turns):<6} "
                  f"{statistics.median(toks):>8.0f}/{max(toks):<6} {solved:>3}/{len(rs)}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"caps": {"turns": env_mod.MAX_TURNS, "output_tokens": env_mod.MAX_EPISODE_OUTPUT_TOKENS},
                                         "rows": rows}, indent=1, default=str), encoding="utf-8")
        print(f"written {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
