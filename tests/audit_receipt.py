"""The audit receipt: one machine-readable record per world, from the
evidence the package already produces, so a buyer can open any world and see
in one place why its reward can be trusted.

Per generated selector (the preflight population):
  gates            the preflight's own offline gates re-run on the freshly
                   minted world: minted, ledger within the envelope, publicly
                   identifiable, the public-only checker's repairs EQUAL the
                   seeded plan, the golden scores 1.0 through the real loop
  serving door     `load_environment(selector)` admitted by the signed release
                   manifest (PIV_MANIFEST), and the id it serves is the id the
                   gates minted
  public evidence  sha256 over the eight public files the agent gets
  scorer           the golden ledger scores 1.0 and complete; the untouched
                   ledger scores 0 with every seeded item unresolved
  reward lattice   the exhaustive subset audit's counts for this world
                   (tests/reward_lattice_audit.py, --lattice-json)
  exploit corpus   whether the nightly exploit sweep exercised this world and
                   with what outcome (--exploit-out, the sweep's log)

Per hand-authored task (--manual): the world verification (problems and
warnings), the same scorer facts, the same lattice counts.

    python tests/audit_receipt.py --production \\
        --train 1000 --eval 200 --hard 200 --workers 8 \\
        --lattice-json <lattice_v9_production.json> --exploit-out <exploit_sweep.out> --json reviews/audit_receipt_v9.json
    python tests/audit_receipt.py --manual --lattice-json <lattice_manual.json> --json <out>

Nothing secret enters the receipt: no seed, no rotation, no key. The manifest
file's sha256 identifies the population.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PRODUCTION = "--production" in sys.argv
if PRODUCTION:
    os.environ["PIV_PREFLIGHT_PHASE"] = "serve"     # preflight_manifest must not install the development flag
else:
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
from beancount_ledger.beancount_ledger import LEDGER, InitializationFailure, load_environment  # noqa: E402
from beancount_ledger.graph import manifest as MF  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.mint import GENERATOR_VERSION  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402
import preflight_manifest as PF  # noqa: E402
import reward_lattice_audit as RLA  # noqa: E402
from world_checks import check_world_task  # noqa: E402

SWEEP_LINE = re.compile(r"^\s*(ok|FAIL|GAP)\s+(\S+)\s+(\d+) attempted,\s+(\d+) reached,\s+(\d+) held,\s+(\d+) skipped")


def public_evidence_hash(env) -> str:
    h = hashlib.sha256()
    for name in sorted(env.public_files):
        h.update(name.encode("utf-8") + b"\0" + env.public_files[name] + b"\0")
    return h.hexdigest()


def scorer_facts(env, golden: str) -> dict:
    original = env.public_files[LEDGER].decode("utf-8")
    k = len(env.contract.planted)
    gold = RLA.score_chain(env.contract, golden, 1)
    base = RLA.score_chain(env.contract, original, 2)
    # With k=0 (the clean-month assurance pack) the untouched-original claim
    # INVERTS: the opening ledger is not a starting point that leaves items
    # unresolved, it IS the deliverable. `untouched_as_expected` is the claim
    # actually made for this task, and it is what `ok` is computed from;
    # `untouched_unresolved` keeps its old meaning so a receipt archived
    # before this pack existed still reads the same way.
    unresolved = (base.get("errors_resolved") == 0.0 and base["outcome"] == "delivered")
    as_expected = (base["reward"] == 1.0 and bool(base.get("complete")) and base["outcome"] == "delivered") if k == 0         else unresolved
    return {"golden_score": gold["reward"], "golden_complete": bool(gold.get("complete")),
            "untouched_score": base["reward"], "untouched_unresolved": unresolved,
            "untouched_as_expected": as_expected,
            "untouched_claim": "already the deliverable (nothing planted)" if k == 0 else "unresolved",
            "planted": k, "targets": list(env.contract.scored_accounts)}


def lattice_facts(rec: dict | None) -> dict:
    if not rec:
        return {"audited": False}
    return {"audited": True, "subsets": rec.get("n_subsets"), "monotonicity_violations": len(rec.get("monotonicity_violations", [])),
            "penalty_activations": len(rec.get("penalty_activations", [])), "unexpected_states": len(rec.get("unexpected_states", [])),
            "cancelling_hits": len(rec.get("cancelling_hits", [])), "loop_checked": rec.get("loop_checked"),
            "loop_mismatches": len(rec.get("loop_mismatches", [])), "ladder_rungs": len(rec.get("ladder", [])),
            "jump_p95": (rec.get("jumps") or {}).get("p95"), "jump_max": (rec.get("jumps") or {}).get("max")}


def generated_receipt(args_tuple) -> dict:
    selector, lattice_rec, exploit_rec = args_tuple
    t0 = time.time()
    namespace, index, *rest = selector.split(":")
    profile_name = "hard" if rest else "standard"
    rec = {"selector": selector, "kind": "generated", "profile": profile_name, "generator_version": GENERATOR_VERSION}
    gate = PF.gate_one((namespace, int(index), profile_name))
    rec["gates"] = gate.get("gates", {})
    rec["gate_notes"] = gate.get("notes", [])
    rec["minted_public_id"] = gate.get("public_id")
    rec["layout_attempt"] = gate.get("attempt")
    rec["ledger_bytes"] = gate.get("ledger_bytes")
    rec["ledger_lines"] = gate.get("ledger_lines")
    try:
        env = load_environment(selector)
        served = env.dataset[0]["info"]["task_id"] if len(env.dataset) else None
        rec["served_public_id"] = served
        rec["serving_door"] = {"admitted": True, "id_matches_minted": served == gate.get("public_id")}
        rec["public_evidence_sha256"] = public_evidence_hash(env)
        golden = RLA.mint(namespace, int(index), RLA.HARD_PROFILE if rest else RLA.DEFAULT_PROFILE).inputs.golden_text
        rec["scorer"] = scorer_facts(env, golden)
    except InitializationFailure as exc:
        rec["serving_door"] = {"admitted": False, "reason": str(exc)[:200]}
    rec["reward_lattice"] = lattice_facts(lattice_rec)
    rec["exploit_corpus"] = exploit_rec or {"exercised": False, "note": "the nightly corpus runs on the structural sentinels and a rotating shard"}
    rec["secs"] = round(time.time() - t0, 1)
    rec["ok"] = bool(all(rec["gates"].values()) and rec.get("serving_door", {}).get("admitted") and rec["serving_door"].get("id_matches_minted")
                     and rec.get("scorer", {}).get("golden_score") == 1.0 and rec.get("scorer", {}).get("untouched_as_expected")
                     and (not rec["reward_lattice"]["audited"] or (rec["reward_lattice"]["monotonicity_violations"] == 0
                          and rec["reward_lattice"]["penalty_activations"] == 0 and rec["reward_lattice"]["unexpected_states"] == 0
                          and rec["reward_lattice"]["loop_mismatches"] == 0)))
    return rec


def manual_receipt(task_id: str, lattice_rec: dict | None) -> dict:
    t0 = time.time()
    world, task = REGISTRY[task_id]
    module = sys.modules[type(world).__module__]  # noqa: F841  (the world is data; its module is not needed)
    problems, warnings = check_world_task(world, task, source_path=None)
    env = load_environment(task_id)
    golden = derive_contract(world, task)[1].golden_text
    rec = {"selector": task_id, "kind": "hand-authored", "world": world.id, "company": world.title.split(" - FY")[0],
           "period": task.period.label, "verification": {"problems": [str(p)[:200] for p in problems], "warnings": len(warnings)},
           "public_evidence_sha256": public_evidence_hash(env), "scorer": scorer_facts(env, golden),
           "reward_lattice": lattice_facts(lattice_rec), "secs": round(time.time() - t0, 1)}
    rec["ok"] = bool(not problems and rec["scorer"]["golden_score"] == 1.0 and rec["scorer"]["untouched_as_expected"]
                     and (not rec["reward_lattice"]["audited"] or (rec["reward_lattice"]["monotonicity_violations"] == 0
                          and rec["reward_lattice"]["penalty_activations"] == 0 and rec["reward_lattice"]["unexpected_states"] == 0)))
    return rec


def parse_exploit_log(path: Path | None) -> dict:
    if not path or not path.is_file():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = SWEEP_LINE.match(line)
        if m:
            status, selector, attempted, reached, held, skipped = m.groups()
            out[selector] = {"exercised": True, "status": status, "attempted": int(attempted), "reached": int(reached),
                             "held": int(held), "skipped": int(skipped)}
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=int, default=0)
    parser.add_argument("--eval", type=int, default=0)
    parser.add_argument("--hard", type=int, default=0)
    parser.add_argument("--selectors", nargs="*", default=None)
    parser.add_argument("--manual", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--lattice-json", type=Path, default=None)
    parser.add_argument("--exploit-out", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()

    lattice = {}
    if args.lattice_json and args.lattice_json.is_file():
        for w in json.load(open(args.lattice_json, encoding="utf-8"))["worlds"]:
            lattice[w["selector"]] = w
    exploit = parse_exploit_log(args.exploit_out)
    t0 = time.time()
    header = {"generator_version": GENERATOR_VERSION, "versions": MF.versions(), "mode": "production" if args.production else "test",
              "engine": "candidate/1"}
    manifest_file = os.environ.get("PIV_MANIFEST")
    if args.production and manifest_file and Path(manifest_file).is_file():
        header["manifest_sha256"] = hashlib.sha256(Path(manifest_file).read_bytes()).hexdigest()

    rows = []
    if args.manual:
        for task_id in sorted(REGISTRY):
            rows.append(manual_receipt(task_id, lattice.get(task_id)))
    else:
        selectors = args.selectors or ([f"train:{i}" for i in range(args.train)] + [f"eval:{i}" for i in range(args.eval)]
                                       + [f"train:{i}:hard" for i in range(args.hard)])
        jobs = [(s, lattice.get(s), exploit.get(s)) for s in selectors]
        if args.workers > 1:
            with Pool(args.workers) as pool:
                rows = pool.map(generated_receipt, jobs, chunksize=4)
        else:
            rows = [generated_receipt(j) for j in jobs]

    ok = sum(1 for r in rows if r.get("ok"))
    summary = {"worlds": len(rows), "ok": ok, "not_ok": [r["selector"] for r in rows if not r.get("ok")][:20],
               "seconds": round(time.time() - t0)}
    if not args.manual:
        summary["gates_all_passed"] = sum(1 for r in rows if r.get("gates") and all(r["gates"].values()))
        summary["admitted_and_id_matches"] = sum(1 for r in rows if r.get("serving_door", {}).get("admitted") and r["serving_door"].get("id_matches_minted"))
        summary["exploit_exercised"] = sum(1 for r in rows if r.get("exploit_corpus", {}).get("exercised"))
    summary["golden_1_0"] = sum(1 for r in rows if r.get("scorer", {}).get("golden_score") == 1.0)
    summary["untouched_unresolved"] = sum(1 for r in rows if r.get("scorer", {}).get("untouched_unresolved"))
    summary["untouched_as_claimed"] = sum(1 for r in rows if r.get("scorer", {}).get("untouched_as_expected"))
    summary["clean_months"] = sorted(r["selector"] for r in rows if r.get("scorer", {}).get("planted") == 0)
    summary["lattice_audited_clean"] = sum(1 for r in rows if r.get("reward_lattice", {}).get("audited")
                                           and r["reward_lattice"]["monotonicity_violations"] == 0 and r["reward_lattice"]["penalty_activations"] == 0
                                           and r["reward_lattice"]["unexpected_states"] == 0)
    print(f"audit receipt ({header['mode']}, generator {GENERATOR_VERSION}): {summary}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"header": header, "summary": summary, "worlds": rows}, indent=1, default=str), encoding="utf-8")
        print(f"written {args.json} ({args.json.stat().st_size:,} bytes)")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
