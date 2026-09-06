"""The differential, distribution-wide, with a structural coverage matrix.

`tests/test_identify_differential.py` runs the checker-versus-scorer property
over ten worlds so that CI stays under a minute. This script runs the same
property over the whole released hard population plus a rotating shard of
the standard one, and reports coverage STRUCTURALLY rather than as a count
of green seeds: a run that never met a five-row component with two
cheapest matchings has not exercised the ambiguity logic, however many worlds
it passed.

    python tests/differential_sweep.py [--hard N] [--standard N] [--shard K]
                                       [--workers W] [--json PATH]

Defaults: every hard selector `train:0..299:hard`, and a rotating shard of 30
standard selectors — shard K of `train:0..1499` picked by `index % 50 == K`,
so successive nightly runs walk the whole standard manifest. `--shard` with no
argument rotates on the day of the year.

Per selector this runs the SAME property the fast differential asserts —
the checker's verdict is `unique` exactly when the real scorer admits one
complete semantic solution class, and the checker's repairs are that class's
repairs under the full shared repair key — and records:

    component sizes           rows x movements per connected component
    admissible edges          settlements and alterations, per world
    matchings                 how many realise the forced settlement count
    semantic readings         how many survive the whole-month constraint
    dropped readings          how many were discarded for leaving something
                              unexplained (the constraint doing its work)
    plant-kind mix            omit / alter / duplicate
    retry attempt index       which bounded layout attempt minted the world

Exit code 1 on any violation. Not part of `run_all.py`: it takes minutes and
needs the evaluator secret.
"""

from __future__ import annotations

import collections
import datetime
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

BANK = "Assets:Bank:Checking"


def one(job) -> dict:
    """One selector's comparison. Any failure below the mint is REPORTED as a
    violation rather than raised: an exception out of a pool worker takes the
    whole sweep down and prints one traceback instead of a coverage matrix,
    which is how two latent defects (`structure()`'s free `rows`, and the
    repair grammar swallowing an end-of-file omission) stayed invisible."""
    try:
        return _one(job)
    except Exception as exc:                       # noqa: BLE001
        namespace, index, profile = job
        name = f"{namespace}:{index}" if profile == "standard" else f"{namespace}:{index}:{profile}"
        return {"sel": name, "problems": [f"the comparison raised {type(exc).__name__}: {exc}"[:300]]}


def _one(job) -> dict:
    namespace, index, profile = job
    name = f"{namespace}:{index}" if profile == "standard" else f"{namespace}:{index}:{profile}"
    out: dict = {"sel": name}
    try:
        from beancount_ledger import beancount_ledger as env_mod
        from beancount_ledger.graph import identify as ID
        import test_generator as TG
        import test_identify_differential as DIFF
        from repair_keys import master_names, planted_key

        minted = TG.minted(namespace, index, profile)
        env = env_mod.load_environment(name)
    except Exception as exc:                       # noqa: BLE001 — a refused seed is not a violation
        out["skipped"] = f"{type(exc).__name__}: {exc}"[:200]
        return out

    public = {file_name: data.decode("utf-8") for file_name, data in minted.inputs.public_files}
    verdict = ID.check_identifiable(public, bank_account=minted.world.bank_account,
                                    period_start=minted.task.period.start,
                                    period_end=minted.task.period.end)
    shape = ID.structure(public, bank_account=minted.world.bank_account,
                         period_start=minted.task.period.start, period_end=minted.task.period.end)
    out["attempt"] = minted.provenance.attempt
    out["kinds"] = "+".join(sorted(p.kind for p in minted.inputs.planted))
    out["unique"] = bool(verdict.unique)
    out["readings"] = verdict.readings
    out["shape"] = shape

    classes: dict = {}
    enumerated = DIFF.candidates(minted, verdict)
    out["families"] = sorted({label.split(":")[0] for label, _text in enumerated})
    out["candidates"] = len(enumerated)
    for label, text in enumerated:
        outcome = DIFF.rollout(env, text)
        if DIFF.is_solution(outcome):
            classes.setdefault(outcome["fingerprint"], []).append(label)
    out["classes"] = len(classes)

    problems = []
    if verdict.unique != (len(classes) == 1):
        problems.append(f"checker says {'unique' if verdict.unique else 'AMBIGUOUS'}; the scorer admits "
                        f"{len(classes)} complete solution class(es)")
    elif not classes:
        problems.append("no enumerated candidate closed the month; the comparison is vacuous here")
    elif "golden" not in next(iter(classes.values())):
        problems.append(f"the one solution class is {next(iter(classes.values()))} and does not contain the golden")
    if verdict.unique:
        names = master_names(public)
        want = collections.Counter(planted_key(p, names, bank_account=minted.world.bank_account)
                                   for p in minted.inputs.planted)
        got = collections.Counter(ID.repair_key(r) for r in verdict.repairs)
        if want != got:
            problems.append(f"repair key mismatch: planted {sorted(str(k) for k in (want - got))} vs checker "
                            f"{sorted(str(k) for k in (got - want))}")
    if problems:
        out["problems"] = problems
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:])

    def take(flag, default):
        if flag not in argv:
            return default
        at = argv.index(flag)
        if at + 1 < len(argv) and not argv[at + 1].startswith("--"):
            value = int(argv[at + 1])
            del argv[at:at + 2]
            return value
        del argv[at]
        return None

    hard = take("--hard", 300)
    standard = take("--standard", 30)
    shard = take("--shard", None)
    workers = take("--workers", min(8, os.cpu_count() or 4))
    out_path = None
    if "--json" in argv:
        at = argv.index("--json")
        out_path = Path(argv[at + 1])
    if shard is None:
        shard = datetime.date.today().timetuple().tm_yday % 50

    jobs = [("train", i, "hard") for i in range(hard or 0)]
    picked = [i for i in range(1500) if i % 50 == shard][: (standard or 0)]
    jobs += [("train", i, "standard") for i in picked]
    print(f"{len(jobs)} selectors: {hard or 0} hard (train:0..{(hard or 1) - 1}:hard) and {len(picked)} "
          f"standard from shard {shard} of 50 (train:{picked[0] if picked else '-'}, step 50)")
    started = time.time()
    with Pool(workers) as pool:
        results = pool.map(one, jobs, chunksize=1)
    elapsed = time.time() - started

    violations = [r for r in results if r.get("problems")]
    skipped = [r for r in results if "skipped" in r]
    done = [r for r in results if "shape" in r]

    comp_sizes = collections.Counter()
    readings = collections.Counter()
    dropped = collections.Counter()
    settle_edges = collections.Counter()
    alter_edges = collections.Counter()
    kinds = collections.Counter()
    attempts = collections.Counter()
    families = collections.Counter()
    classes = collections.Counter()
    exhausted = 0
    for r in done:
        for component in r["shape"]["components"]:
            comp_sizes[(component["rows"], component["movements"])] += 1
            readings[component["readings"]] += 1
            dropped[component["dropped"]] += 1
        settle_edges[r["shape"]["settle_edges"]] += 1
        alter_edges[r["shape"]["alter_edges"]] += 1
        exhausted += r["shape"]["exhausted"]
        kinds[r["kinds"]] += 1
        attempts[r["attempt"]] += 1
        classes[r["classes"]] += 1
        for family in r["families"]:
            families[family] += 1

    def histogram(counter, limit=12):
        return ", ".join(f"{k}x{v}" for k, v in sorted(counter.items(), key=lambda kv: (kv[0] is None, kv[0]))[:limit])

    print(f"\n{len(done)} selectors compared in {elapsed:.0f}s ({len(skipped)} skipped, {len(violations)} violations)")
    print("\n--- structural coverage matrix ---")
    print(f"  components (rows x movements)   {histogram(comp_sizes, 16)}")
    print(f"  largest component              {max(comp_sizes, default=(0, 0))}")
    print(f"  semantic readings / component  {histogram(readings)}")
    print(f"  readings dropped as incomplete {histogram(dropped)}")
    print(f"  settlement edges / world       {histogram(settle_edges)}")
    print(f"  alteration edges / world       {histogram(alter_edges)}")
    print(f"  budget exhaustions             {exhausted}")
    print(f"  plant-kind mixes               {histogram(kinds, 20)}")
    print(f"  retry attempt index            {histogram(attempts)}")
    print(f"  solution classes / world       {histogram(classes)}")
    print(f"  wrong-variant families built   {dict(sorted(families.items()))}")
    for r in skipped[:5]:
        print(f"  skipped {r['sel']}: {r['skipped']}")
    for r in violations[:10]:
        print(f"  VIOLATION {r['sel']}: {'; '.join(r['problems'])[:400]}")
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"\nwritten {out_path}")
    print(f"\n{'PASS' if not violations else 'FAIL'}: {len(violations)} violations over {len(done)} selectors")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
