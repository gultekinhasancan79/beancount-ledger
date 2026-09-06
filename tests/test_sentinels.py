"""The structural CI sentinel set: pinned, re-checked, and differentiated.

A small fixed set of worlds that together reach every structural branch a
topology-dependent regression could hide in is what fast CI needs, so that it
is not "one selector per profile plus hope".
`tests/select_sentinels.py` derives that set — it describes 270 minted worlds
by structural feature and takes a deterministic greedy cover — and prints it.
This file PINS the answer and re-earns it on every run:

    the pinned selectors still exhibit every feature the choice was made for,
    so a generator change that stops producing (say) `attempt>0` or
    `mix:alter+alter+duplicate+duplicate` fails here instead of quietly
    thinning the coverage;

    the fast differential — `check_identifiable` unique <=> the real scorer
    admits exactly one complete semantic solution class, and the checker's
    repairs ARE that class's repairs under the full shared repair key — runs
    over exactly these worlds, which is the property `test_identify_differential`
    runs over its own ten and `differential_sweep` runs over hundreds.

The feature vocabulary and what each item is for are documented in
`select_sentinels.py`. The set is pinned rather than recomputed because a set
recomputed every run is a set nobody has to look at when it changes.

    python tests/test_sentinels.py
"""

from __future__ import annotations

import collections
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("PIV_EVAL_SECRET", "5f1c7b9e2a4d6c8b0e1f3a5c7d9b2e4f6a8c0d2e4f6a8b0c1d3e5f7a9b1c3d5e")  # gitleaks:allow  (a public test constant, not a credential: determinism compares runs under one key)
os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")

try:                                        # the dataset "Map:" bar is noise in a test log
    import datasets as _datasets
    _datasets.disable_progress_bar()
except Exception:                           # noqa: BLE001
    pass

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402
import select_sentinels as SS  # noqa: E402
import test_identify_differential as DIFF  # noqa: E402
import test_generator as TG  # noqa: E402
from repair_keys import master_names, planted_key  # noqa: E402

BANK = "Assets:Bank:Checking"

# Chosen by `python tests/select_sentinels.py --pool 300` over the minted
# worlds (300 standard train, 300 hard, 75 eval: 675/675 minted, none
# refused, none ambiguous) under the test secret at GENERATOR_VERSION 9: a
# deterministic greedy cover of the 44 structural features that pool
# exhibits. Under the dense profiles (five to eight items a world) almost
# every world carries almost every feature, so the cover is four worlds; the
# rarest features are the two-kind mixes (alter+omit 37/675, duplicate+omit
# 71/675) and a transposed office payment (171/675). Regenerate with that
# script and re-pin whenever the generator version changes — the worlds a
# selector names move with `(secret, generator version, profile)`.
SENTINELS = [
    "train:263:hard",
    "eval:2",
    "eval:10",
    "eval:11",
]

# Every feature the set was chosen to cover. Grouped by requirement, so a
# reader can check the list against the ask rather than against the script.
REQUIRED = {
    "each plant kind": ("kind:omit", "kind:alter", "kind:duplicate"),
    "every kind mix in the population": (
        "mix:alter+duplicate+omit", "mix:alter+omit", "mix:duplicate+omit"),
    "a kind planted more than once": ("repeat:omit", "repeat:alter", "repeat:duplicate"),
    "every (kind, rule) pair the generator plants": (
        "plant:unrecorded_customer_deposit", "plant:unrecorded_supplier_payment",
        "plant:unrecorded_card_payment", "plant:unrecorded_bank_fee",
        "plant:transposed_customer_receipt", "plant:transposed_vendor_payment",
        "plant:transposed_expense_payment", "plant:transposed_bank_fee",
        "plant:duplicated_customer_receipt", "plant:duplicated_vendor_payment",
        "plant:duplicated_expense_payment", "plant:duplicated_bank_fee"),
    "every rail": ("rail:ach_in", "rail:ach_out", "rail:cheque", "rail:card", "rail:bank_initiated"),
    "positive and zero date lag": ("lag:positive", "lag:zero"),
    "duplicate multiplicity": ("duplicate-multiplicity",),
    "outstanding and in-transit alternatives": ("outstanding:check", "outstanding:in-transit"),
    "repeated counterparty, amount and source-document reference": (
        "repeated:counterparty", "repeated:amount", "repeated:reference"),
    "the reference ontology's roles": ("ref-role:instrument", "ref-role:document", "ref-role:memo"),
    "the supplier-payment rule": ("policy-attributed-row",),
    "more than one admissible edge and more than one occurrence-level matching": (
        "edges>rows", "matchings>1", "dropped>0"),
    "a retry attempt > 0": ("attempt>0",),
    "both profiles": ("profile:standard", "profile:hard"),
}


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:40]:
            print(f"      {line}")
    return ok


def note(text):
    print(f"      · {text}")


def _parts(selector: str):
    bits = selector.split(":")
    return bits[0], int(bits[1]), (bits[2] if len(bits) == 3 else "standard")


_DESCRIBED: dict = {}


def described(selector: str) -> dict:
    if selector not in _DESCRIBED:
        _DESCRIBED[selector] = SS.features(*_parts(selector))
    return _DESCRIBED[selector]


def test_the_pinned_sentinels_still_cover_every_structural_feature():
    """The coverage matrix, re-earned. Every feature in `REQUIRED` is
    exhibited by at least one pinned selector, no pinned selector is
    redundant (each one is the only cover of something), and none of them is
    a world the checker cannot read uniquely — a sentinel that mint would
    refuse is not a sentinel."""
    problems = []
    have: dict = {}
    for selector in SENTINELS:
        row = described(selector)
        if "features" not in row:
            problems.append(f"{selector}: {row.get('skipped')}")
            continue
        if "NOT-UNIQUE" in row["features"]:
            problems.append(f"{selector}: the public evidence admits more than one reading")
        for feature in row["features"]:
            have.setdefault(feature, []).append(selector)
    for requirement, features in sorted(REQUIRED.items()):
        missing = [f for f in features if f not in have]
        if missing:
            problems.append(f"{requirement}: no sentinel covers {missing}")
    unique_cover = [s for s in SENTINELS
                    if any(covers == [s] for feature, covers in have.items()
                           if feature in {f for group in REQUIRED.values() for f in group})]
    redundant = [s for s in SENTINELS if s not in unique_cover]
    if redundant:
        problems.append(f"pinned but covering nothing on its own: {redundant}")
    note(f"{len(SENTINELS)} sentinels, {len(have)} features, "
         f"{sum(len(v) for v in REQUIRED.values())} required")
    for requirement, features in sorted(REQUIRED.items()):
        note(f"{requirement}: " + ", ".join(f"{f}({len(have.get(f, ()))})" for f in features))
    return check("the pinned sentinel set still covers every structural feature it was chosen for, and every "
                 "member of it is the only cover of something", not problems, "\n".join(problems))


def test_the_differential_holds_over_exactly_the_sentinels():
    """The same property `test_identify_differential` asserts over its ten
    worlds and `differential_sweep` asserts over hundreds — the checker's
    verdict against the real scorer's solution classes — run over the worlds
    that were chosen because they reach the branches."""
    problems, reported = [], []
    started = time.time()
    built = set()
    for selector in SENTINELS:
        namespace, index, profile = _parts(selector)
        try:
            minted = TG.minted(namespace, index, profile)
            env = env_mod.load_environment(selector)
        except Exception as exc:                       # noqa: BLE001
            problems.append(f"{selector}: could not be built ({type(exc).__name__}: {exc})")
            continue
        public = {name: data.decode("utf-8") for name, data in minted.inputs.public_files}
        verdict = ID.check_identifiable(public, bank_account=minted.world.bank_account,
                                        period_start=minted.task.period.start,
                                        period_end=minted.task.period.end)
        classes: dict = {}
        enumerated = DIFF.candidates(minted, verdict)
        built |= {label.split(":")[0] for label, _text in enumerated}
        for label, text in enumerated:
            outcome = DIFF.rollout(env, text)
            if DIFF.is_solution(outcome):
                classes.setdefault(outcome["fingerprint"], []).append(label)
        if verdict.unique != (len(classes) == 1):
            problems.append(f"{selector}: checker {'unique' if verdict.unique else 'AMBIGUOUS'}, scorer "
                            f"{len(classes)} complete class(es): {verdict.reason[:200]}")
            continue
        if not classes:
            problems.append(f"{selector}: no enumerated candidate closed the month; the comparison is vacuous")
            continue
        if "golden" not in next(iter(classes.values())):
            problems.append(f"{selector}: the one solution class {next(iter(classes.values()))} is not the golden")
        names = master_names(public)
        want = collections.Counter(planted_key(p, names, bank_account=minted.world.bank_account)
                                   for p in minted.inputs.planted)
        got = collections.Counter(ID.repair_key(r) for r in verdict.repairs)
        if want != got:
            problems.append(f"{selector}: repair key mismatch — planted {sorted(str(k) for k in (want - got))} "
                            f"vs checker {sorted(str(k) for k in (got - want))}")
        reported.append(f"{selector}: {len(classes)} class, {len(enumerated)} candidates")
    missing = [family for family in DIFF.WRONG_FAMILIES if family not in built]
    if missing:
        problems.append(f"the repair grammar built no {missing} candidate over the sentinels")
    for line in reported:
        note(line)
    note(f"{time.time() - started:.1f}s")
    return check(f"the checker/scorer differential holds over all {len(SENTINELS)} structural sentinels, and "
                 f"the checker's repairs are the accepted class's repairs under the full shared repair key",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_pinned_sentinels_still_cover_every_structural_feature,
    test_the_differential_holds_over_exactly_the_sentinels,
]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
