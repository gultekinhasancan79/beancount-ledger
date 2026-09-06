"""Choose the structural CI sentinel set, and print the matrix that justifies it.

One fixed selector per profile is enough only for exploit families that are
genuinely topology-independent. It is not enough for matching, duplicate
occurrence, timing, reference or stale-state attacks; fast CI needs a small
structural sentinel set instead. This script picks that set and shows its
coverage, so the choice is a derivation rather than a taste.

    python tests/select_sentinels.py [--pool N] [--json PATH]

Every selector in the pool is minted under the evaluator secret and described
by a set of STRUCTURAL FEATURES — one property per requirement, each
read off the minted world or off `identify.structure()`:

    profile:*                   standard and hard
    kind:*                      omit / alter / duplicate, individually
    mix:*                       every plant-kind mix the population produces
    rail:*                      ach_in, ach_out, cheque, card, bank_initiated,
                                over the rows the plants are on
    lag:positive / lag:zero     the recognition date differs from the bank
                                date, or does not
    duplicate-multiplicity      a planted duplicate: the books carry two
                                copies of one occurrence
    outstanding:check           an outstanding cheque (money out, uncleared)
    outstanding:in-transit      a deposit in transit (money in, uncredited)
    repeated:counterparty       one party on two or more bank movements
    repeated:amount             one absolute amount on two or more rows of the
                                current statement and the archive together
    repeated:reference          one normalised reference quoted twice
    ref-role:*                  a row whose reference is an instrument, a
                                document, or neither
    policy-attributed-row       a money-out row attributed by
                                `## Payments to suppliers`
    edges>rows                  a component where some row has more than one
                                admissible edge
    matchings>1                 a component where more than one occurrence-level
                                matching had to be compared before the readings
                                were quotiented
    dropped>0                   a component where the whole-month constraint
                                actually discarded a reading
    repeat:*                    a kind planted more than once in one world
    plant:*                     the (kind, rule) pair a planted item is:
                                its mutation id without the -again suffix
    attempt>0                   a world a bounded layout retry produced

The set is then a deterministic greedy cover: repeatedly take the selector
that covers the most still-uncovered features, breaking ties by the selector
name, until every feature the pool offers is covered. Greedy is not minimal,
but it is reproducible and small, and `tests/test_sentinels.py` pins the
result so a later change to the generator has to be looked at rather than
silently absorbed.

Not part of `run_all.py`: it mints hundreds of worlds. Its OUTPUT is, as a
pinned list.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")

BANK = "Assets:Bank:Checking"


def features(namespace: str, index: int, profile_name: str) -> dict:
    """Every structural feature one minted world exhibits."""
    from beancount_ledger.graph import identify as ID
    from beancount_ledger.graph.generate import DEFAULT_PROFILE, HARD_PROFILE
    from beancount_ledger.graph.mint import mint

    selector = f"{namespace}:{index}" if profile_name == "standard" else f"{namespace}:{index}:{profile_name}"
    profile = HARD_PROFILE if profile_name == "hard" else DEFAULT_PROFILE
    try:
        minted = mint(namespace, index, profile)
    except Exception as exc:                       # noqa: BLE001 — a refused seed is not a sentinel
        return {"sel": selector, "skipped": f"{type(exc).__name__}: {exc}"[:160]}

    period = minted.task.period
    public = {name: data.decode("utf-8") for name, data in minted.inputs.public_files}
    verdict = ID.check_identifiable(public, bank_account=minted.world.bank_account,
                                    period_start=period.start, period_end=period.end)
    shape = ID.structure(public, bank_account=minted.world.bank_account,
                         period_start=period.start, period_end=period.end)

    found = {f"profile:{profile_name}"}
    kinds = sorted(p.kind for p in minted.inputs.planted)
    # Which kinds a plan combines, and which it repeats. Under the dense
    # profiles (GENERATOR_VERSION 9: five to eight items a world) the exact
    # multiset of kinds is a forty-way vocabulary that would pin a sentinel
    # per shape; what moves a checker's branches is co-occurrence and
    # repetition, so those are the features.
    found.add("mix:" + "+".join(sorted(set(kinds))))
    for kind in set(kinds):
        found.add(f"kind:{kind}")
        if kinds.count(kind) > 1:
            found.add(f"repeat:{kind}")
        if kind == "duplicate":
            found.add("duplicate-multiplicity")
    # Which (kind, rule) pairs the plan carries — the mutation id without its
    # "-again" suffix: an omitted fee and a transposed receipt reach different
    # accounts and different repair shapes.
    for spec in minted.inputs.planted:
        found.add("plant:" + spec.id.split("-again")[0])
    for spec in minted.inputs.planted:
        rec = minted.bundle.recognition(spec.recognition_id)
        movement = next((m for m in minted.bundle.movements if m.event_id == rec.event_id), None)
        if movement is None:
            continue
        found.add(f"rail:{movement.rail.value}")
        found.add("lag:positive" if movement.cleared_on != rec.date else "lag:zero")
    for item in verdict.outstanding:
        # the signed amount `LedgerMovement.__str__` prints: money in is a
        # deposit in transit, money out is an outstanding cheque
        signed = next((t for t in item.split()
                       if t[:1] in "+-" and t[1:].replace(".", "").isdigit()), "")
        found.add("outstanding:in-transit" if signed.startswith("+") else "outstanding:check")

    # repeated evidence, read off the public bytes the agent gets
    movements = ID.ledger_movements(public[ID.LEDGER_FILE], BANK, equity_accounts=frozenset(),
                                    period_start=period.start, period_end=period.end)[0]
    payees = collections.Counter(m.payee for m in movements)
    if any(count > 1 for count in payees.values()):
        found.add("repeated:counterparty")
    amounts: collections.Counter = collections.Counter()
    references: collections.Counter = collections.Counter()
    for file_name in (ID.STATEMENT_FILE, ID.ARCHIVE_FILE):
        for line in public.get(file_name, "").splitlines()[1:]:
            parts = line.split(",")
            if len(parts) != 6 or not (parts[3] or parts[4]):
                continue
            amounts[parts[3] or parts[4]] += 1
            if parts[2]:
                references[ID._norm_ref(parts[2])] += 1
    if any(count > 1 for count in amounts.values()):
        found.add("repeated:amount")
    if any(count > 1 for count in references.values()):
        found.add("repeated:reference")

    for role, count in shape["reference_roles"].items():
        if count:
            found.add(f"ref-role:{role}")
    if shape["policy_attributed_rows"]:
        found.add("policy-attributed-row")
    for component in shape["components"]:
        if component["readings"] is None:
            continue
        if component["edges"] > component["rows"]:
            found.add("edges>rows")
        if (component["matchings"] or 0) > 1:
            found.add("matchings>1")
        if (component["dropped"] or 0) > 0:
            found.add("dropped>0")
    if minted.provenance.attempt > 0:
        found.add("attempt>0")
    if not verdict.unique:
        found.add("NOT-UNIQUE")                    # never a sentinel: mint should have refused it

    return {"sel": selector, "features": sorted(found), "task_id": minted.inputs.task_id,
            "attempt": minted.provenance.attempt}


def _job(args):
    return features(*args)


def cover(described: list) -> list:
    """Deterministic greedy set cover, tie-broken by selector name."""
    universe = sorted({f for row in described for f in row["features"]} - {"NOT-UNIQUE"})
    uncovered = set(universe)
    by_sel = {row["sel"]: set(row["features"]) for row in described}
    chosen: list = []
    while uncovered:
        best = max(sorted(by_sel), key=lambda s: (len(by_sel[s] & uncovered), [-ord(c) for c in s]))
        gain = by_sel[best] & uncovered
        if not gain:
            break
        chosen.append(best)
        uncovered -= gain
    return chosen


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=int, default=300, help="selectors per profile to consider (300 reaches every kind mix and repetition the population carries)")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    jobs = ([("train", i, "standard") for i in range(args.pool)]
            + [("train", i, "hard") for i in range(args.pool)]
            + [("eval", i, "standard") for i in range(args.pool // 4)])
    with Pool(8) as pool:
        rows = pool.map(_job, jobs, chunksize=4)
    skipped = [r for r in rows if "skipped" in r]
    described = [r for r in rows if "features" in r]
    ambiguous = [r for r in described if "NOT-UNIQUE" in r["features"]]

    universe = sorted({f for r in described for f in r["features"]} - {"NOT-UNIQUE"})
    chosen = cover(described)
    by_sel = {r["sel"]: set(r["features"]) for r in described}

    print(f"pool {len(jobs)} selectors: {len(described)} minted, {len(skipped)} refused, "
          f"{len(ambiguous)} not unique")
    print(f"{len(universe)} structural features present in the pool\n")
    print("--- coverage matrix (rows: the chosen sentinels; columns: the features) ---")
    width = max(len(f) for f in universe) + 2
    for feature in universe:
        hits = [s for s in chosen if feature in by_sel[s]]
        pool_count = sum(1 for r in described if feature in r["features"])
        print(f"  {feature:<{width}} {len(hits)}/{len(chosen)} chosen, {pool_count}/{len(described)} in pool"
              f"   {', '.join(hits[:3])}{' ...' if len(hits) > 3 else ''}")
    print(f"\n--- the chosen set ({len(chosen)}) ---")
    for sel in chosen:
        print(f"  {sel:<22} {', '.join(sorted(by_sel[sel]))}")
    missing = [f for f in universe if not any(f in by_sel[s] for s in chosen)]
    print(f"\nuncovered: {missing or 'none'}")
    print("\nSENTINELS = [")
    for sel in chosen:
        print(f'    "{sel}",')
    print("]")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"universe": universe, "chosen": chosen,
                                         "described": described}, indent=1), encoding="utf-8")
        print(f"written {args.json}")
    return 1 if (missing or ambiguous) else 0


if __name__ == "__main__":
    raise SystemExit(main())
