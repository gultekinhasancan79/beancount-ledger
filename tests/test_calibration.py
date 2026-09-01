"""The candidate/1 calibration corpus: rankings the contract promises.

`candidate/1` is a deliberate reward migration, not a numerical clone of
`raw-text/1`. So this suite pins PAIRWISE ORDERINGS, not snapshots — a
weight change that preserves every snapshot can still invert a ranking
when a new case arrives. Alongside it, the semantic claim: submissions that
mean the same thing tie under `candidate/1` even where `raw-text/1` told
them apart, and every closed exploit stays at or below its ceiling.

    python tests/test_calibration.py
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger import reward as raw  # noqa: E402  (archived raw-text/1, for the semantic comparison only)
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate.normalise import Accepted, EvaluationFailure, ProtocolFailure, parse_once  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402
from beancount_ledger.task import load_task  # noqa: E402  (the archived task file, for raw-text/1 only)

WORLD = ROOT / "beancount_ledger" / "world"
SOLUTIONS = ROOT / "tests" / "solutions"
TASK = load_task(ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json")
ORIGINAL_TEXT = (WORLD / "ledger.beancount").read_text(encoding="utf-8")
ORIGINAL = env_mod.logical_text((WORLD / "ledger.beancount").read_bytes())
_, INPUTS = derive_contract(*REGISTRY["bank_recon_001"])
ENV = K.load_contract(INPUTS)          # the production door: graph-derived inputs only

# Ceilings under candidate/1 for the semantic corpus, and the documented
# deltas from raw-text/1 with their rationale. Presentation-equivalent
# payloads TIE with the correct solution here by design.
# After the adversary pass: a record that is not fully explained (an
# unexplained entry, an altered or removed original, a lifecycle or option
# change, an account outside the chart) has NO deliverable and an official
# reward of 0 — one penalised item used to cost exactly the budget (0.60)
# and print verbatim. Only the documented-payee cases keep partial credit.
CEILINGS = {
    "bad_deleted_check": Decimal("0.00"),
    "bad_plug_account": Decimal("0.00"),
    "bad_altered_unrelated": Decimal("0.00"),
    "bad_copied_statement": Decimal("0.00"),
    "bad_merged_events": Decimal("0.00"),
    "bad_no_narration": Decimal("0.80"),        # raw 0.65: the prose channel is retired; the naming defect stays (−0.20)
    "bad_negated_keywords": Decimal("0.80"),    # same
    "bad_mocking_case": Decimal("0.80"),        # strict payee predicate: still undocumented (−0.20)
    "bad_opening_balance": Decimal("0.00"),
    "bad_opening_forgery_full": Decimal("0.00"),
    "bad_wash_transaction": Decimal("0.00"),    # was 0.65: the wash is unexplained, so there is no deliverable
    "bad_payee_rewrite": Decimal("0.00"),
    "bad_closed_accounts": Decimal("0.00"),
    "bad_duplicate_opens": Decimal("0.00"),     # policy: caps at 0.0 and blocks render
    "bad_removed_open": Decimal("0.00"),        # policy: gates all
    "baseline_untouched": Decimal("0.00"),
    # Flags and tags are NOT accounting, and the semantic candidate erases
    # them — but the preservation rule is structural: rewriting the flag or
    # stamping a tag on every PRE-EXISTING entry alters entries the task said
    # to leave alone, and `FIELD_DIMENSIONS` declares both reward-observed
    # for that role. So these are not ties; they rank with tampering.
    "bad_pending_flags": Decimal("0.00"),
    "bad_tagged_entries": Decimal("0.00"),
}
# The text-only channels: inexpressible under candidate/1, so these tie with
# the correct solution by design, where raw-text/1 penalised each.
PRESENTATION_TIES = ("bad_comment_injection", "bad_computed_amounts", "bad_overprecise_amounts")
PROTOCOL = ("bad_unparseable", "bad_elided_amounts", "bad_rewritten_options", "bad_padded_file", "bad_wide_line")


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:20]:
            print(f"      {line}")
    return ok


def outcome(text: str):
    r = parse_once(text)
    if isinstance(r, Accepted):
        return K.score_committed(K.commit(r, ENV, K.new_receipt("r", 1, env_mod.digests_of(text.encode("utf-8"), submitted=text))))
    return r


def total(text: str) -> Decimal | None:
    o = outcome(text)
    return o.total if isinstance(o, K.ScoreOutcome) else (Decimal("0") if isinstance(o, ProtocolFailure) else None)


def solution(name: str) -> str:
    return (SOLUTIONS / f"{name}.beancount").read_text(encoding="utf-8")


def test_rankings():
    golden = solution("golden")
    rhead = '2025-11-26 * "Harbor Freight Ltd" "Customer payment settling SI-1044"'
    deposit = rhead + "\n  Assets:Bank:Checking                      4800.00 USD\n  Assets:AR                                -4800.00 USD\n"
    fhead = '2025-11-30 * "Cascade Bank" "Monthly account service charge"'
    fee = fhead + "\n  Expenses:BankFees                           85.00 USD\n  Assets:Bank:Checking                       -85.00 USD\n"
    problems = []
    if deposit not in golden or fee not in golden:
        return check("rankings", False, "fixture drift: repairs not found in golden")
    g = total(golden)
    untouched = total(solution("baseline_untouched"))
    only_fee = total(golden.replace(deposit + "\n", ""))
    only_deposit = total(golden.replace(fee + "\n", "").replace(fee, ""))
    collateral = total(golden.replace("  Expenses:Office", "  Expenses:Rent", 1))
    table = {"golden": g, "untouched": untouched, "only fee": only_fee, "only deposit": only_deposit, "collateral": collateral}
    if g != Decimal("1"):
        problems.append(f"golden {g}")
    for label, partial in (("only fee", only_fee), ("only deposit", only_deposit)):
        if not (untouched < partial < g):
            problems.append(f"untouched {untouched} < {label} {partial} < golden {g} fails")
    if not (collateral < g):
        problems.append(f"collateral damage did not lower the rank: {collateral}")
    for name in PROTOCOL:
        o = outcome(solution(name))
        if not isinstance(o, ProtocolFailure):
            problems.append(f"{name}: expected a protocol rejection, got {type(o).__name__}")
    for name, ceiling in CEILINGS.items():
        o = outcome(solution(name))
        if not isinstance(o, K.ScoreOutcome):
            problems.append(f"{name}: {type(o).__name__} {o}")
            continue
        table[name] = o.total
        if o.total > ceiling:
            problems.append(f"{name}: {o.total} > ceiling {ceiling}")
        if o.total >= g:
            problems.append(f"{name}: not below golden")
    for name, o in ((n, outcome(solution(n))) for n in CEILINGS):
        if isinstance(o, K.ScoreOutcome) and not o.renderable and o.total != Decimal("0"):
            problems.append(f"{name}: non-renderable outcome scored {o.total}; the official reward of a file task without a file is 0")
    for name in PRESENTATION_TIES:
        o = outcome(solution(name))
        table[name] = o.total if isinstance(o, K.ScoreOutcome) else None
        if not isinstance(o, K.ScoreOutcome) or o.total != g:
            problems.append(f"{name}: expected a tie with golden, got {table[name]}")
        raw_total = raw.score(solution(name), TASK, ORIGINAL_TEXT)["total"]
        if raw_total >= Decimal("1"):
            problems.append(f"{name}: raw-text/1 does not distinguish it either — the tie claim is vacuous")
    print("      " + "\n      ".join(f"{k:26s} {v}" for k, v in table.items()))
    return check("candidate/1 rankings: untouched < partial < golden; collateral lowers; protocol is protocol; "
                 "exploits at or below ceiling; equivalent sources tie where raw-text/1 differs",
                 not problems, "\n".join(problems))


def test_facts_once_scored_twice():
    """Both engines must agree on the bookkeeping FACTS of every semantic
    case — resolved events, target and collateral accounts, plug accounts —
    before either applies its weights. A parser difference then cannot pass
    for an intentional weight delta, and the archived engine can disappear
    while its fact/score mapping stays as contract history."""
    problems = []
    for name in CEILINGS:
        if name in ("bad_pending_flags", "bad_tagged_entries"):
            continue   # flags/tags: the raw fingerprint and the structural record agree, but raw also counts prose
        text = solution(name)
        o = outcome(text)
        d = raw.score(text, TASK, ORIGINAL_TEXT)
        if not isinstance(o, K.ScoreOutcome):
            continue
        facts_c = {"unresolved": tuple(o.unresolved_planted),
                   "target_misses": tuple(sorted(m.split(":")[0] for m in o.target_misses)),
                   "collateral": tuple(sorted(m.split(":")[0] for m in o.collateral_damage)),
                   "plugs": tuple(sorted(o.plug_accounts))}
        facts_r = {"unresolved": tuple(d["unresolved_planted"]),
                   "target_misses": tuple(sorted(m.split(":")[0] for m in d["target_misses"])),
                   "collateral": tuple(sorted(m.split(":")[0] for m in d["collateral_damage"])),
                   "plugs": tuple(sorted(d["plug_accounts"]))}
        if facts_c != facts_r:
            problems.append(f"{name}: candidate {facts_c} vs raw {facts_r}")
    return check("facts once, scored twice: both engines agree on resolved events, target/collateral accounts and plugs",
                 not problems, "\n".join(problems))


def test_the_decimal_calibration_pins_the_exact_value():
    golden = solution("golden")
    exact = golden.replace("  Expenses:BankFees                           85.00 USD",
                           "  Expenses:BankFees                           85.000000000000000 USD")
    beyond = golden.replace("  Expenses:BankFees                           85.00 USD",
                            "  Expenses:BankFees                           85.000000000000001 USD")
    problems = []
    if total(exact) != Decimal("1"):
        problems.append(f"an exact fifteen-decimal spelling did not tie: {total(exact)}")
    o = outcome(beyond)
    # 1E-15 is finer than the numeric bound (1E-8), which fires before the money scale does
    if not isinstance(o, ProtocolFailure) or o.reason not in ("number.scale", "posting.units.scale"):
        problems.append(f"one unit beyond the money scale was not refused by name: {o}")
    finer = golden.replace("  Expenses:BankFees                           85.00 USD",
                           "  Expenses:BankFees                           85.001 USD")
    o = outcome(finer)
    if not isinstance(o, ProtocolFailure) or o.reason != "posting.units.scale":
        problems.append(f"a third decimal was not refused as posting.units.scale: {o}")
    return check("decimal calibration: 85.000000000000000 ties; 85.000000000000001 (number.scale) and 85.001 "
                 "(posting.units.scale) are refused by name", not problems, "\n".join(problems))


TESTS = [test_rankings, test_facts_once_scored_twice, test_the_decimal_calibration_pins_the_exact_value]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
