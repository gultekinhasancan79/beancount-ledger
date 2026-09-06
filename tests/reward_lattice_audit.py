"""The reward lattice, audited through the real scorer: every subset of a
world's golden repairs is applied to the untouched ledger and scored with the
production chain (parse_once -> commit -> score_committed, engine candidate/1),
exactly as a committed revision is scored inside an episode.

For a world with k planted items that is 2^k candidates (k <= 8: at most 256).
Per world the audit checks:

  monotonicity     R(S + {e}) >= R(S) for every subset S and every correct
                   repair e not in S — a correct repair never lowers the reward
  penalties        no subset of correct repairs triggers a penalty (collateral,
                   removed/altered, fabricated, merged, undocumented, plug)
  expected states  every subset is delivered (renderable) and scores exactly
                   0.70 * targets_hit + 0.30 * |S|/k, where a target counts as
                   hit when every planted item touching it is in S; the full
                   set scores 1.0 and is complete; nothing else is complete
  marginal jumps   the distribution of R(S + {e}) - R(S) (p50/p90/p95/p99/max),
                   and for every jump above 0.25 whether the bank target is
                   what unlocked it
  the real loop    a sample of subsets is also submitted through the production
                   loop (workspace -> write_ledger -> env_response -> score_core)
                   and must score the same as the chain

Repairs are text edits on the original ledger, per item: omit -> insert the
golden's same-head block in chronological position; alter -> replace the
same-head block whose amounts equal `replaces` with the golden's block;
duplicate -> delete one copy of the same-head block.

    python tests/reward_lattice_audit.py --train 30 --eval 10 --hard 10 --workers 4
        under the suite's test secret and the development route (the default)
    python tests/reward_lattice_audit.py --manual --workers 4
        every hand-authored task in the registry (no secret involved)
    PIV_MANIFEST=~/.piv/manifest_v9.json python tests/reward_lattice_audit.py --production \\
        --train 1000 --eval 200 --hard 200 --workers 8 --json <out>
        under the evaluator's own secret through the serving door; nothing
        secret is printed, and the development flag is never set

Exit status 1 when any hard requirement fails: a monotonicity violation, a
penalty on a correct-repair subset, an unexpected state, or a loop mismatch.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import random
import re
import statistics
import sys
import time
from decimal import Decimal
from multiprocessing import Pool
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PRODUCTION = "--production" in sys.argv
if not PRODUCTION:
    # the suite's public test constant (tests/test_generator.py) and the
    # development route; never in production mode
    _src = (ROOT / "tests" / "test_generator.py").read_text(encoding="utf-8")
    os.environ.setdefault("PIV_EVAL_SECRET", re.search(r'TEST_SECRET = "([0-9a-f]{64})"', _src).group(1))
    os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")
os.environ.setdefault("HF_DATASETS_DISABLE_PROGRESS_BARS", "1")

try:                                        # the dataset "Map:" bar is noise in a log
    import datasets as _datasets
    _datasets.disable_progress_bar()
except Exception:                           # noqa: BLE001
    pass

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.beancount_ledger import LEDGER, InitializationFailure, digests_of, load_environment, logical_text  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate.committed import commit, new_receipt, score_committed  # noqa: E402
from beancount_ledger.candidate.normalise import Accepted, ProtocolFailure, parse_once  # noqa: E402
from beancount_ledger.graph.generate import DEFAULT_PROFILE, HARD_PROFILE  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.mint import GENERATOR_VERSION, mint  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402

BIG_JUMP = 0.25
PENALTY_LISTS = ("collateral_damage", "removed_or_altered", "fabricated", "merged_events", "undocumented", "plug_accounts")
HEAD = re.compile(r'^(\d{4}-\d{2}-\d{2}) \* "(.*)" "(.*)"$')


# --------------------------------------------------------------------------
# the scorer chain, and the real loop
# --------------------------------------------------------------------------

def score_chain(contract, text: str, revision: int) -> dict:
    raw = text.encode("utf-8", errors="strict")
    digests = digests_of(raw, submitted=text)
    outcome = parse_once(logical_text(raw))
    receipt = new_receipt("lattice", revision, digests)
    if isinstance(outcome, Accepted):
        result = score_committed(commit(outcome, contract, receipt))
        result.verify()
        d = result.as_dict()
        return {"reward": float(result.total), "outcome": "delivered" if result.renderable else "policy_blocked",
                "targets_hit": float(d["components"]["targets_hit"]),
                "errors_resolved": float(d["components"]["errors_resolved"]),
                # a miss reads "Account: expected X, got Y"; keep the account
                "target_misses": [str(m).split(": expected", 1)[0] for m in d["target_misses"]],
                "complete": bool(d["complete"]),
                "penalties": {name: len(d[name]) for name in PENALTY_LISTS if d.get(name)}}
    if isinstance(outcome, ProtocolFailure):
        return {"reward": 0.0, "outcome": "protocol_rejected", "reason": str(outcome.reason)[:200]}
    return {"reward": 0.0, "outcome": "evaluator_failure", "detail": repr(outcome)[:200]}


def rollout(env, text: str) -> dict:
    """One submission through the production loop, exactly as `verifiers`
    drives it (the helper tests/test_generator.py uses, copied so that
    production mode never imports the test module's secret)."""
    state: dict = {}
    env._workspace(state)
    call = SimpleNamespace(id="call-1", name="write_ledger", arguments=json.dumps({"content": text}))
    asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))
    if state.get("piv_committed") is None:
        return {"committed": False, "total": None}
    total = env_mod.score_core(state)
    delivery, result = state["piv_delivery"], state["piv_result"]
    return {"committed": True, "total": float(Decimal(str(total))), "outcome": delivery.outcome,
            "complete": bool(result and result.complete)}


# --------------------------------------------------------------------------
# repairs as text edits
# --------------------------------------------------------------------------

def blocks(text: str):
    out, cur = [], []
    for line in text.splitlines():
        if line.strip() == "":
            if cur:
                out.append(cur)
                cur = []
        else:
            cur.append(line)
    if cur:
        out.append(cur)
    res = []
    for b in out:
        m = HEAD.match(b[0])
        res.append(((m.group(1), m.group(2), m.group(3)) if m else None, b))
    return res


def canon(v) -> str:
    d = Decimal(str(v))
    return "0" if d == 0 else str(d.normalize())


def amounts(block_lines) -> tuple:
    legs = []
    for line in block_lines[1:]:
        parts = line.split()
        if len(parts) >= 3:
            legs.append((parts[0], canon(parts[1])))
    return tuple(sorted(legs))


def apply_repairs(original: str, golden: str, chosen) -> str:
    obs = blocks(original)
    gbs = blocks(golden)
    for p in chosen:
        head = (p.date, p.payee, p.narration)
        req = tuple(sorted((a, canon(v)) for a, v in p.required))
        if p.kind == "omit":
            cand = [b for h, b in gbs if h == head and amounts(b) == req]
            if len(cand) != 1:
                raise LookupError(f"{p.id}: {len(cand)} golden blocks match the omitted item")
            pos = len(obs)
            for i, (h, _b) in enumerate(obs):
                if h and h[0] > p.date:
                    pos = i
                    break
            obs.insert(pos, (head, list(cand[0])))
        elif p.kind == "alter":
            rep = tuple(sorted((a, canon(v)) for a, v in p.replaces))
            idx = [i for i, (h, b) in enumerate(obs) if h == head and amounts(b) == rep]
            cand = [b for h, b in gbs if h == head and amounts(b) == req]
            if len(idx) != 1 or len(cand) != 1:
                raise LookupError(f"{p.id}: {len(idx)} original / {len(cand)} golden blocks match the altered item")
            obs[idx[0]] = (head, list(cand[0]))
        elif p.kind == "duplicate":
            idx = [i for i, (h, b) in enumerate(obs) if h == head and amounts(b) == req]
            if len(idx) != 2:
                raise LookupError(f"{p.id}: {len(idx)} original blocks match the doubled item, not two")
            del obs[idx[-1]]
        else:
            raise LookupError(f"{p.id}: unknown kind {p.kind}")
    return "\n\n".join("\n".join(b) for _, b in obs) + "\n"


# --------------------------------------------------------------------------
# one world
# --------------------------------------------------------------------------

def percentile(values, q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[k]


def audit(selector: str, loop_sample: int) -> dict:
    t0 = time.time()
    try:
        env = load_environment(selector)
    except InitializationFailure as exc:
        return {"selector": selector, "refused": str(exc)[:300]}
    contract = env.contract
    if selector in REGISTRY:                        # a hand-authored task: the golden derives from the facts
        world, task = REGISTRY[selector]
        golden = derive_contract(world, task)[1].golden_text
    else:
        namespace, index, *rest = selector.split(":")
        golden = mint(namespace, int(index), HARD_PROFILE if rest else DEFAULT_PROFILE).inputs.golden_text
    original = env.public_files[LEDGER].decode("utf-8")
    items = list(contract.planted)
    k = len(items)
    targets = list(contract.scored_accounts)
    bank = next((a for a in targets if a.startswith("Assets:Bank")), targets[0] if targets else "")
    touch = {a: {i for i, p in enumerate(items) if any(x == a for x, _ in p.required)} for a in targets}

    rec = {"selector": selector, "generator_version": GENERATOR_VERSION, "k": k,
           "kinds": [p.kind for p in items], "targets": targets, "n_subsets": 2 ** k,
           "monotonicity_violations": [], "penalty_activations": [], "unexpected_states": [],
           "big_jumps": [], "loop_mismatches": [], "loop_checked": 0}
    scores: dict = {}
    texts: dict = {}
    rev = 0
    for n in range(k + 1):
        for subset in itertools.combinations(range(k), n):
            rev += 1
            try:
                text = apply_repairs(original, golden, [items[i] for i in subset])
            except LookupError as exc:
                rec["unexpected_states"].append({"subset": list(subset), "why": f"edit: {exc}"})
                continue
            s = score_chain(contract, text, rev)
            scores[subset] = s
            texts[subset] = text
            S = set(subset)
            hit = sum(1 for a in targets if touch[a] <= S) / len(targets)
            predicted = round(0.7 * hit + 0.3 * n / k, 6)
            if s["outcome"] != "delivered":
                rec["unexpected_states"].append({"subset": list(subset), "why": s["outcome"], "detail": s.get("reason") or s.get("detail")})
            elif abs(round(s["reward"], 6) - predicted) > 1e-6:
                rec["unexpected_states"].append({"subset": list(subset), "why": "reward differs from the contract's arithmetic",
                                                 "reward": s["reward"], "predicted": predicted,
                                                 "targets_hit": s["targets_hit"], "errors_resolved": s["errors_resolved"]})
            if s.get("penalties"):
                rec["penalty_activations"].append({"subset": list(subset), "penalties": s["penalties"]})
            if n == k and (s["reward"] != 1.0 or not s.get("complete")):
                rec["unexpected_states"].append({"subset": list(subset), "why": "the full set is not a complete 1.0", "reward": s["reward"]})
            if n < k and s.get("complete"):
                rec["unexpected_states"].append({"subset": list(subset), "why": "an incomplete subset reports complete"})

    jumps = []
    for subset, s in scores.items():
        for e in range(k):
            if e in subset:
                continue
            bigger = tuple(sorted(subset + (e,)))
            if bigger not in scores:
                continue
            t = scores[bigger]
            delta = round(t["reward"] - s["reward"], 6)
            jumps.append(delta)
            if delta < -1e-9:
                rec["monotonicity_violations"].append({"subset": list(subset), "repair": items[e].id,
                                                       "before": s["reward"], "after": t["reward"]})
            if delta > BIG_JUMP:
                bank_flipped = bank in s.get("target_misses", []) and bank not in t.get("target_misses", [])
                rec["big_jumps"].append({"subset_size": len(subset), "repair": items[e].id, "kind": items[e].kind,
                                         "delta": delta, "bank_unlocked": bank_flipped,
                                         "targets_unlocked": [a for a in s.get("target_misses", []) if a not in t.get("target_misses", [])]})
    rec["ladder"] = sorted({round(s["reward"], 4) for s in scores.values()})
    rec["jumps"] = {"n": len(jumps), "p50": percentile(jumps, 0.50), "p90": percentile(jumps, 0.90),
                    "p95": percentile(jumps, 0.95), "p99": percentile(jumps, 0.99), "max": max(jumps) if jumps else 0.0,
                    "mean": round(statistics.mean(jumps), 6) if jumps else 0.0}
    rec["big_jump_count"] = len(rec["big_jumps"])
    rec["big_jumps_bank"] = sum(1 for j in rec["big_jumps"] if j["bank_unlocked"])

    # the real loop, on a sample of subsets (always the empty set and the full set when sampled)
    if loop_sample > 0 and scores:
        rng = random.Random(f"lattice:{selector}")
        keys = list(scores)
        pick = {(), tuple(range(k))} if loop_sample >= 2 else set()
        while len(pick) < min(loop_sample, len(keys)):
            pick.add(rng.choice(keys))
        for subset in sorted(pick):
            r = rollout(env, texts[subset])
            rec["loop_checked"] += 1
            chain = scores[subset]
            if not r["committed"] or abs((r["total"] or 0.0) - chain["reward"]) > 1e-6 or bool(r["complete"]) != bool(chain.get("complete")):
                rec["loop_mismatches"].append({"subset": list(subset), "chain": chain["reward"], "loop": r.get("total"),
                                               "loop_outcome": r.get("outcome"), "committed": r["committed"]})
    rec["big_jumps"] = rec["big_jumps"][:12]        # keep the record small; the counts are complete
    rec["secs"] = round(time.time() - t0, 1)
    return rec


def _job(args):
    selector, loop_sample = args
    try:
        return audit(selector, loop_sample)
    except Exception as exc:                        # noqa: BLE001 - a crash is a finding, not a lost world
        return {"selector": selector, "crashed": f"{type(exc).__name__}: {exc}"[:300]}


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=int, default=30)
    parser.add_argument("--eval", type=int, default=10)
    parser.add_argument("--hard", type=int, default=10)
    parser.add_argument("--selectors", nargs="*", default=None, help="explicit selectors instead of the ranges")
    parser.add_argument("--manual", action="store_true", help="audit every hand-authored task in the registry instead of the ranges")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--loop-sample", type=int, default=2, help="subsets per world also sent through the real loop (0 = none)")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--production", action="store_true", help="evaluator secret and serving door; set PIV_MANIFEST yourself")
    args = parser.parse_args()

    if args.manual:
        selectors = sorted(REGISTRY)
    else:
        selectors = args.selectors or ([f"train:{i}" for i in range(args.train)] + [f"eval:{i}" for i in range(args.eval)]
                                       + [f"train:{i}:hard" for i in range(args.hard)])
    t0 = time.time()
    jobs = [(s, args.loop_sample) for s in selectors]
    if args.workers > 1:
        with Pool(args.workers) as pool:
            rows = pool.map(_job, jobs, chunksize=2)
    else:
        rows = [_job(j) for j in jobs]

    ok = [r for r in rows if "k" in r]
    refused = [r for r in rows if "refused" in r]
    crashed = [r for r in rows if "crashed" in r]
    mono = sum(len(r["monotonicity_violations"]) for r in ok)
    pen = sum(len(r["penalty_activations"]) for r in ok)
    unexpected = sum(len(r["unexpected_states"]) for r in ok)
    mismatches = sum(len(r["loop_mismatches"]) for r in ok)
    loop_checked = sum(r["loop_checked"] for r in ok)
    subsets = sum(r["n_subsets"] for r in ok)
    all_jumps_p95 = sorted(r["jumps"]["p95"] for r in ok)
    big = sum(r["big_jump_count"] for r in ok)
    big_bank = sum(r["big_jumps_bank"] for r in ok)
    n_jumps = sum(r["jumps"]["n"] for r in ok)
    max_jump = max((r["jumps"]["max"] for r in ok), default=0.0)
    ladder_sizes = [len(r["ladder"]) for r in ok]

    print(f"reward lattice audit: GENERATOR_VERSION {GENERATOR_VERSION}, engine candidate/1, "
          f"{'production serving door' if args.production else 'test secret / development route'}")
    print(f"{len(rows)} selectors in {time.time() - t0:.0f}s: {len(ok)} audited, {len(refused)} refused, {len(crashed)} crashed; "
          f"{subsets} subsets scored through the chain, {loop_checked} also through the real loop")
    print(f"HARD  monotonicity violations {mono}; correct-repair penalty activations {pen}; unexpected states {unexpected}; "
          f"loop mismatches {mismatches}")
    print(f"      marginal jumps: {n_jumps} steps; per-world p95 median {statistics.median(all_jumps_p95) if all_jumps_p95 else 0:.3f}, "
          f"per-world p95 max {max(all_jumps_p95) if all_jumps_p95 else 0:.3f}; overall max jump {max_jump:.3f}")
    print(f"      jumps above {BIG_JUMP}: {big} of {n_jumps} steps ({100.0 * big / n_jumps if n_jumps else 0:.2f}%), "
          f"{big_bank} of them unlock the bank target ({100.0 * big_bank / big if big else 0:.1f}%)")
    print(f"      ladder rungs per world: min {min(ladder_sizes) if ladder_sizes else 0}, median "
          f"{statistics.median(ladder_sizes) if ladder_sizes else 0}, max {max(ladder_sizes) if ladder_sizes else 0}")
    for r in refused[:5]:
        print(f"   REFUSED {r['selector']}: {r['refused']}")
    for r in crashed[:5]:
        print(f"   CRASHED {r['selector']}: {r['crashed']}")
    for r in ok:
        for v in r["monotonicity_violations"][:3]:
            print(f"   MONOTONICITY {r['selector']}: {v}")
        for v in r["penalty_activations"][:3]:
            print(f"   PENALTY {r['selector']}: {v}")
        for v in r["unexpected_states"][:3]:
            print(f"   UNEXPECTED {r['selector']}: {v}")
        for v in r["loop_mismatches"][:3]:
            print(f"   LOOP {r['selector']}: {v}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        summary = {"generator_version": GENERATOR_VERSION, "mode": "production" if args.production else "test",
                   "selectors": len(rows), "audited": len(ok), "refused": len(refused), "crashed": len(crashed),
                   "subsets": subsets, "loop_checked": loop_checked, "monotonicity_violations": mono,
                   "penalty_activations": pen, "unexpected_states": unexpected, "loop_mismatches": mismatches,
                   "jumps": n_jumps, "big_jumps": big, "big_jumps_bank": big_bank, "max_jump": max_jump,
                   "seconds": round(time.time() - t0)}
        args.json.write_text(json.dumps({"summary": summary, "worlds": rows}, indent=1, default=str), encoding="utf-8")
        print(f"written {args.json}")
    hard_fail = mono or pen or unexpected or mismatches or crashed
    print("FAIL: a hard requirement did not hold" if hard_fail else "PASS: every hard requirement holds")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
