"""Domain validation: total, correct on the known-good case, and cross-checked.

Three things are being asserted, in increasing order of how much they cost to
learn.

**The correct solution must validate.** Cheapest test in the suite and it has
already paid for itself once: an "every event must name a known counterparty"
rule went in, and the golden solution immediately came back invalid, because
the opening-balance entry has no counterparty and correctly should not. That
rule was a *task* requirement wearing the clothes of a universal invariant, and
it would have made every generated world unwinnable. A validator that rejects
the known-correct answer is wrong whatever it says about anything else.

**It must be total.** For every value constructible under the schema it returns
violations and does not raise. A validator that throws converts a malformed
submission into an evaluator crash, and an evaluator crash charged to the agent
is our bug turned into negative training data.

**It should agree with beancount where they overlap.** Beancount's validator no
longer runs in the reward path -- it assumes booked entries and encodes its
notion of a ledger rather than ours -- but it is a good independent oracle for
the invariants both of us claim to check. Disagreement there is our drift.

    python tests/test_validate.py
"""

import itertools
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.candidate.entities import build_resolver  # noqa: E402
from beancount_ledger.candidate.normalise import (  # noqa: E402
    Accepted,
    EvaluationFailure,
    ProtocolFailure,
    parse_once,
)
from beancount_ledger.candidate.schema import (  # noqa: E402
    AccountLifecycle,
    Event,
    LedgerCandidate,
    Posting,
)
from beancount_ledger.candidate.policy import (  # noqa: E402
    POLICIES,
    apply_policy,
    consequences,
)
from beancount_ledger.candidate.validate import validate_candidate  # noqa: E402
from beancount_ledger.candidate.canonical import summarise_findings  # noqa: E402

SOLUTIONS = Path(__file__).resolve().parent / "solutions"
WORLD = ROOT / "beancount_ledger" / "world"


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:8]:
            print(f"      {line}")
    return ok


def test_the_correct_solution_validates():
    """The one test that catches over-strictness for free."""
    resolver = build_resolver(WORLD).resolve
    result = parse_once((SOLUTIONS / "golden.beancount").read_text(encoding="utf-8"),
                        entity_resolver=resolver)
    if isinstance(result, (ProtocolFailure, EvaluationFailure)):
        return check("the correct solution validates", False, str(result))
    if not result.domain_valid:
        return check("the correct solution validates", False,
                     "\n".join(str(f) for f in result.domain_findings))
    return check("the correct solution validates", True)


def test_the_opening_world_validates():
    """The world we ship the agent must itself be a valid ledger.

    Distinct from the test above: the opening ledger is what every episode
    starts from, so a rule that rejects it makes the task unwinnable before the
    agent does anything at all.
    """
    resolver = build_resolver(WORLD).resolve
    result = parse_once((WORLD / "ledger.beancount").read_text(encoding="utf-8"),
                        entity_resolver=resolver)
    ok = isinstance(result, Accepted) and result.domain_valid
    return check("the opening world validates", ok, str(result) if not ok else "")


def _malformed_candidates():
    """Deliberately broken candidates, built directly rather than parsed.

    Constructed through the schema so they can express things no submission
    could get past the boundary -- an unbalanced event, a posting to an
    undeclared account, an account closed before it opens. That is the point:
    totality has to hold for every value the schema admits, not only for the
    ones the parser happens to produce.
    """
    p = lambda a, n: Posting(a, Decimal(n))  # noqa: E731
    ev = lambda d, ps, e="Acme": Event(d, e, None, tuple(ps))  # noqa: E731
    lc = lambda k, d, a: AccountLifecycle(k, d, a)  # noqa: E731

    yield "empty", LedgerCandidate("USD", (), ())
    yield "unbalanced", LedgerCandidate(
        "USD", (lc("open", "2025-01-01", "Assets:A"), lc("open", "2025-01-01", "Assets:B")),
        (ev("2025-11-05", [p("Assets:A", "1.00"), p("Assets:B", "-2.00")]),))
    yield "single posting", LedgerCandidate(
        "USD", (lc("open", "2025-01-01", "Assets:A"),),
        (ev("2025-11-05", [p("Assets:A", "0.00")]),))
    yield "no postings", LedgerCandidate(
        "USD", (lc("open", "2025-01-01", "Assets:A"),), (ev("2025-11-05", []),))
    yield "undeclared account", LedgerCandidate(
        "USD", (), (ev("2025-11-05", [p("Assets:Ghost", "1.00"), p("Assets:X", "-1.00")]),))
    yield "posted before open", LedgerCandidate(
        "USD", (lc("open", "2025-12-01", "Assets:A"), lc("open", "2025-12-01", "Assets:B")),
        (ev("2025-11-05", [p("Assets:A", "1.00"), p("Assets:B", "-1.00")]),))
    yield "posted after close", LedgerCandidate(
        "USD", (lc("open", "2025-01-01", "Assets:A"), lc("close", "2025-06-01", "Assets:A"),
                lc("open", "2025-01-01", "Assets:B")),
        (ev("2025-11-05", [p("Assets:A", "1.00"), p("Assets:B", "-1.00")]),))
    yield "close before open", LedgerCandidate(
        "USD", (lc("open", "2025-06-01", "Assets:A"), lc("close", "2025-01-01", "Assets:A")), ())
    yield "close without open", LedgerCandidate(
        "USD", (lc("close", "2025-01-01", "Assets:A"),), ())
    yield "duplicate open", LedgerCandidate(
        "USD", (lc("open", "2025-01-01", "Assets:A"), lc("open", "2025-02-01", "Assets:A")), ())
    yield "no entity", LedgerCandidate(
        "USD", (lc("open", "2025-01-01", "Assets:A"), lc("open", "2025-01-01", "Assets:B")),
        (ev("2025-11-05", [p("Assets:A", "1.00"), p("Assets:B", "-1.00")], None),))
    yield "empty currency", LedgerCandidate("", (), ())


def test_validation_is_total():
    """It must return violations for every constructible value, never raise."""
    problems = []
    for label, candidate in _malformed_candidates():
        try:
            validate_candidate(candidate)
        except Exception as exc:
            problems.append(f"{label}: raised {type(exc).__name__}: {exc}")
    return check(
        f"validation is total over {len(list(_malformed_candidates()))} malformed candidates",
        not problems,
        "\n".join(problems),
    )


def test_each_malformed_case_is_actually_caught():
    """Totality is worthless if the function returns nothing for everything.

    The other side of the pair. A `validate_candidate` that always returned an
    empty list would pass the totality test perfectly.
    """
    expected_clean = {"empty", "no entity", "empty currency"}
    problems = []
    for label, candidate in _malformed_candidates():
        found = validate_candidate(candidate)
        if label in expected_clean and found:
            problems.append(f"{label}: expected no violations, got {found[0].code}")
        elif label not in expected_clean and not found:
            problems.append(f"{label}: expected a violation, got none")
    return check(
        "every malformed case yields a violation and every valid one does not",
        not problems,
        "\n".join(problems),
    )


def test_agreement_with_beancount_on_the_overlap():
    """Beancount as an independent oracle, outside the reward path.

    One-way implication only, because the two validators do not have the same
    scope: if beancount rejects a ledger, ours should find something too. The
    converse does not hold -- we reject things beancount permits, which is the
    whole reason for having our own.

    The oracle uses the loader, which imports plugin modules. That is safe
    here and nowhere else: these are our own corpus files, and the test asserts
    separately that no submitted content ever reaches this function.
    """
    from beancount.loader import load_string

    resolver = build_resolver(WORLD).resolve
    disagreements = []
    for path in sorted(SOLUTIONS.glob("*.beancount")):
        text = path.read_text(encoding="utf-8")
        if "plugin" in text or "include" in text:
            continue  # never hand submitted controls to the loader
        ours = parse_once(text, entity_resolver=resolver)
        if isinstance(ours, (ProtocolFailure, EvaluationFailure)):
            continue  # no candidate to compare
        _, errors, _ = load_string(text)
        beancount_rejects = bool(errors)
        we_reject = not ours.domain_valid
        if beancount_rejects and not we_reject:
            kinds = sorted({type(e).__name__ for e in errors})
            disagreements.append(
                f"{path.stem}: beancount reports {kinds}, we report nothing")
    return check(
        "where beancount rejects a ledger, our validator also finds something",
        not disagreements,
        "\n".join(disagreements),
    )


def test_every_violation_code_has_a_disclosed_consequence():
    """No violation may reach scoring without a policy entry.

    A missing entry must raise, not default. A default is a scoring rule
    nobody wrote down and nobody disclosed — which is exactly how the four
    undisclosed rules got in the first time, and the reason this whole
    architecture exists.

    The codes are discovered by running the validator over the malformed
    fixtures rather than transcribed, so a new check added without a policy
    entry fails here instead of at scoring time.
    """
    emitted = set()
    for _, candidate in _malformed_candidates():
        emitted.update(v.code for v in validate_candidate(candidate))
    problems = []
    for task, table in POLICIES.items():
        missing = sorted(emitted - set(table))
        if missing:
            problems.append(f"{task}: no disposition for {missing}")
    return check(
        f"every reachable violation code has a consequence ({len(emitted)} codes)",
        not problems,
        "\n".join(problems),
    )


def test_an_unknown_code_raises_rather_than_defaulting():
    """The other half of the pair: silence must not be an answer."""
    from beancount_ledger.candidate.validate import DomainViolation
    try:
        consequences(summarise_findings([DomainViolation("invented.code", "x")]))
        return check("an unknown violation code raises", False,
                     "it returned a default instead")
    except KeyError as exc:
        return check("an unknown violation code raises", "invented.code" in str(exc))


def test_blocking_render_also_caps_the_reward():
    """A ledger the environment refuses to emit cannot be a full success.

    Duplicate `open` was classified as blocking render while leaving the score
    untouched, which meant the maximum was reachable with an unusable ledger —
    the high-score/unusable-output pattern, rebuilt by accident in the layer
    written to remove it.
    """
    problems = []
    for task, table in POLICIES.items():
        for code, cons in table.items():
            if not cons.blocks_render:
                continue
            reachable = not cons.gates_all and (cons.caps_reward is None or cons.caps_reward >= 1.0)
            if reachable:
                problems.append(f"{task}.{code}: blocks render but full reward stays reachable")
    return check(
        "nothing that blocks canonical output can still earn full reward",
        not problems,
        "\n".join(problems),
    )


TESTS = [
    test_the_correct_solution_validates,
    test_every_violation_code_has_a_disclosed_consequence,
    test_an_unknown_code_raises_rather_than_defaulting,
    test_blocking_render_also_caps_the_reward,
    test_the_opening_world_validates,
    test_validation_is_total,
    test_each_malformed_case_is_actually_caught,
    test_agreement_with_beancount_on_the_overlap,
]


def run() -> int:
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
