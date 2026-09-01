"""Unit tests for reward invariants the solution-file suite cannot express.

test_reward.py scores whole submissions against the one hand-built world. That
is the right shape for "this attack must not pay", but it pins a single opening
ledger, so any property that depends on the *original* being different — two
identical entries, a chart naming a plug — has nowhere to live there.

Every case below covers a branch changed in response to the M0 review. A fix
without a test is a fix that regresses silently, and three of these guard code
paths that were reachable only once a generator starts producing worlds nobody
hand-checked.

    python tests/test_invariants.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.reward import (  # noqa: E402
    _find_fabricated,
    _find_tampering,
    _find_undocumented,
    allocate,
    audit_allowed_accounts,
    declared_options,
    load_ledger,
    load_task,
)

HEAD = """\
option "title" "Test Co"
option "operating_currency" "USD"

2025-11-01 open Assets:Bank:Checking USD
2025-11-01 open Expenses:Rent USD
2025-11-01 open Expenses:BankFees USD
"""

# Two rent payments that are identical in every field a fingerprint sees. This
# is ordinary in real books and impossible to hand-wave away: a company can pay
# the same landlord the same amount twice in a month.
TWIN_RENT = """
2025-11-05 * "Kestrel Properties" "Rent"
  Expenses:Rent            2000.00 USD
  Assets:Bank:Checking    -2000.00 USD

2025-11-05 * "Kestrel Properties" "Rent"
  Expenses:Rent            2000.00 USD
  Assets:Bank:Checking    -2000.00 USD
"""

ONE_RENT = """
2025-11-05 * "Kestrel Properties" "Rent"
  Expenses:Rent            2000.00 USD
  Assets:Bank:Checking    -2000.00 USD
"""


def entries(text):
    parsed, parse_errors, _, options = load_ledger(text)
    assert not parse_errors, f"fixture does not parse: {parse_errors}"
    return parsed, options


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {name}")
    if not condition and detail:
        print(f"      {detail}")
    return condition


def test_duplicate_entry_deletion_is_visible():
    """Deleting one of two identical entries must be caught.

    Under a set-based comparison the second copy is free: both fingerprints are
    the same value, the set still contains it, and nothing reports a loss. The
    balances would catch this particular case, but only as collateral damage on
    an unrelated account — the tamper check, which is the one that names what
    happened, saw a clean ledger.
    """
    original, _ = entries(HEAD + TWIN_RENT)
    submitted, _ = entries(HEAD + ONE_RENT)
    lost = _find_tampering(original, submitted)
    return check(
        "deleting one of two identical entries is reported",
        len(lost) == 1,
        f"expected exactly 1 loss, got {len(lost)}: {lost}",
    )


def test_identical_entries_untouched_are_not_reported():
    """The counting must not fire on a submission that changed nothing.

    The other half of the branch. A check that reports a loss whenever two
    entries are identical would pass the test above for the wrong reason.
    """
    original, _ = entries(HEAD + TWIN_RENT)
    submitted, _ = entries(HEAD + TWIN_RENT)
    lost = _find_tampering(original, submitted)
    return check(
        "identical entries left alone are not reported as lost",
        lost == [],
        f"false positives: {lost}",
    )


def test_include_is_a_declared_option():
    """`include` must be visible to the option comparison.

    It sat on the volatile list, where it was inert under load_string and would
    have become a way to pull in unscored entries the moment worlds loaded from
    disk. The test is that the option is *compared*, not that includes resolve.
    """
    _, plain = entries(HEAD)
    return check(
        "include is not excluded from declared options",
        "include" in declared_options(plain),
        f"declared options: {sorted(declared_options(plain))}",
    )


def test_undocumented_checks_every_match_not_just_the_first():
    """A second copy of a resolving entry is never vouched for by the first.

    Two contracts in sequence. The first version stopped at the first
    match, so one correctly-named entry vouched for every later copy. The
    second checked every copy's payee independently of any other component,
    which let the resolver and the fabrication check disagree about which
    copy WAS the repair. Now one allocation decides: the named copy takes
    the planted slot in either order, the unnamed copy is one unexplained
    addition — priced once, as fabrication, not also as undocumented — and
    a lone unnamed copy is the resolution and is undocumented.
    """
    planted = [{
        "id": "TEST-1",
        "date": "2025-11-30",
        "required_postings": [
            ["Expenses:BankFees", "85.00"],
            ["Assets:Bank:Checking", "-85.00"],
        ],
        "must_be_payee": ["Cascade Bank"],
    }]
    good = """
2025-11-30 * "Cascade Bank" "Service charge"
  Expenses:BankFees          85.00 USD
  Assets:Bank:Checking      -85.00 USD
"""
    bad = """
2025-11-30 * "x" "x"
  Expenses:BankFees          85.00 USD
  Assets:Bank:Checking      -85.00 USD
"""
    problems = []
    original, _ = entries(HEAD)          # the chart is pre-existing; the repairs are the additions
    for label, text in (("named first", HEAD + good + bad), ("unnamed first", HEAD + bad + good)):
        submitted, _ = entries(text)
        allocation = allocate(original, submitted, planted)
        flagged = _find_undocumented(submitted, planted, allocation)
        unexplained = _find_fabricated(original, submitted, allocation)
        if flagged or len(unexplained) != 1 or "x" not in unexplained[0] or allocation.unmatched_planted:
            problems.append(f"{label}: undocumented={flagged} unexplained={unexplained} "
                            f"unmatched={allocation.unmatched_planted}")
    submitted, _ = entries(HEAD + bad)
    allocation = allocate(original, submitted, planted)
    if len(_find_undocumented(submitted, planted, allocation)) != 1 or _find_fabricated(original, submitted, allocation):
        problems.append("a lone unnamed copy should be the resolution and undocumented")
    return check(
        "one allocation: the named copy is the repair in either order, the unnamed copy is one unexplained addition",
        not problems,
        "\n".join(problems),
    )


def test_plug_shaped_allowed_account_is_a_task_defect():
    """A chart naming an allowed account like a plug must be rejected.

    `Expenses:Other` is an ordinary line in a real chart of accounts. When the
    plug check ran over allowed accounts too, a generator emitting one would
    produce a task where posting to an account the task explicitly permitted
    cost the largest penalty in the system — unwinnable, and silent about it.
    """
    ok = audit_allowed_accounts(["Assets:Bank:Checking", "Expenses:BankFees"]) == []
    caught = audit_allowed_accounts(["Expenses:Other"]) == ["Expenses:Other"]
    return check(
        "plug-shaped allowed accounts are a task defect, ordinary ones are not",
        ok and caught,
        f"clean chart passed: {ok}, plug-shaped chart caught: {caught}",
    )


def test_shipped_task_loads():
    """The task we actually ship must survive its own validation."""
    task = load_task(ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json")
    return check("the shipped task passes load-time validation", bool(task))


TESTS = [
    test_duplicate_entry_deletion_is_visible,
    test_identical_entries_untouched_are_not_reported,
    test_include_is_a_declared_option,
    test_undocumented_checks_every_match_not_just_the_first,
    test_plug_shaped_allowed_account_is_a_task_defect,
    test_shipped_task_loads,
]


def run() -> int:
    print(f"{len(TESTS)} invariant tests\n")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
