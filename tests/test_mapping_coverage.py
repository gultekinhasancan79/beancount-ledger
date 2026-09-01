"""Exhaustiveness: every field the parser can produce must be classified.

This is the test that turns "did we forget a field?" from something we hope
fuzzing finds into a property the build checks. Beancount exposes its directive
union as `data.ALL_DIRECTIVES`, and every directive is a NamedTuple carrying
`_fields`, so the parser's whole surface can be *discovered* rather than
transcribed. An unclassified field is a failure here, not a silent default.

Why this matters more than another attack case: the previous scorer accumulated
nineteen hand-written rules, one per review round, because it had no
classification and answered each new degree of freedom locally. Each fix taught
us the next attack rather than the last one. The set of presentation tricks is
unbounded and the set of AST fields is not, so classifying the finite thing
exhaustively closes the infinite one — including the members nobody has thought
of yet.

It also makes parser drift visible. If a beancount upgrade adds a field or a
directive, this test fails and someone has to decide what the new thing means
before it can silently become part of, or vanish from, the semantic type.

    python tests/test_mapping_coverage.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount.core import data  # noqa: E402

from beancount_ledger.candidate.mapping import (  # noqa: E402
    DIRECTIVES,
    FIELDS,
    POSTING_FIELDS,
    Disposition,
)


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines():
            print(f"      {line}")
    return ok


def test_every_directive_is_classified():
    """Every directive beancount can emit has an admission decision."""
    seen = {d.__name__ for d in data.ALL_DIRECTIVES}
    missing = sorted(seen - set(DIRECTIVES))
    extra = sorted(set(DIRECTIVES) - seen)
    return check(
        "every parser directive has an admission decision",
        not missing and not extra,
        f"unclassified: {missing}\nclassified but not in this parser: {extra}",
    )


def test_every_field_of_every_directive_is_classified():
    """Every field of every directive is classified, accepted or not.

    Fields of a rejected directive are classified too. In production the
    directive is refused before its fields are read, but leaving them blank
    would mean the table's coverage claim depended on today's admission list —
    so admitting a directive later would silently admit unclassified fields
    with it.
    """
    problems = []
    for directive in data.ALL_DIRECTIVES:
        name = directive.__name__
        parser_fields = set(getattr(directive, "_fields", ()))
        table = FIELDS.get(name)
        if table is None:
            problems.append(f"{name}: no field table at all")
            continue
        for field in sorted(parser_fields - set(table)):
            problems.append(f"{name}.{field}: in the parser, not in the table")
        for field in sorted(set(table) - parser_fields):
            problems.append(f"{name}.{field}: in the table, not in this parser")
    return check(
        "every field of every directive is classified",
        not problems,
        "\n".join(problems),
    )


def test_posting_fields_are_classified():
    parser_fields = set(data.Posting._fields)
    missing = sorted(parser_fields - set(POSTING_FIELDS))
    extra = sorted(set(POSTING_FIELDS) - parser_fields)
    return check(
        "every posting field is classified",
        not missing and not extra,
        f"unclassified: {missing}\nnot in this parser: {extra}",
    )


def test_accepted_directives_map_or_canonicalise_their_meaning():
    """An accepted directive may not reject its own fields.

    A directive admitted at the top level whose fields are all rejected is a
    contradiction that would only surface at runtime, on a submission.
    """
    problems = []
    for name, rule in DIRECTIVES.items():
        if rule.disposition is not Disposition.MAPPED:
            continue
        dispositions = {r.disposition for r in FIELDS[name].values()}
        if Disposition.MAPPED not in dispositions:
            problems.append(f"{name} is accepted but maps none of its fields")
    return check(
        "accepted directives map at least one field",
        not problems,
        "\n".join(problems),
    )


def test_every_rule_names_a_reason():
    """A rejection that cannot name itself is one nobody can act on.

    The reason identifier reaches the agent as a diagnostic and the perimeter
    tests as a class label, so an empty one is a real defect rather than a
    documentation lapse.
    """
    problems = []
    tables = [("directive", DIRECTIVES), ("posting", POSTING_FIELDS)]
    for directive, table in FIELDS.items():
        tables.append((directive, table))
    for scope, table in tables:
        for key, rule in table.items():
            if not rule.reason or not rule.reason.strip():
                problems.append(f"{scope}.{key} has no reason identifier")
    return check("every rule names a reason", not problems, "\n".join(problems))


def report_surface():
    """Not an assertion — a printed summary of what the boundary admits.

    Worth seeing on every run. The accepted surface should be small enough to
    read, and if it grows the person growing it should watch it happen.
    """
    accepted = sorted(n for n, r in DIRECTIVES.items()
                      if r.disposition is Disposition.MAPPED)
    refused = sorted(n for n, r in DIRECTIVES.items()
                     if r.disposition is Disposition.REJECTED)
    counts = {d: 0 for d in Disposition}
    for table in list(FIELDS.values()) + [POSTING_FIELDS]:
        for rule in table.values():
            counts[rule.disposition] += 1
    print(f"\n  accepted directives : {', '.join(accepted)}")
    print(f"  rejected directives : {', '.join(refused)}")
    print("  field dispositions  : " + ", ".join(
        f"{d.value}={counts[d]}" for d in Disposition))


def test_the_table_is_enforced_at_runtime():
    """A complete table and an enforced one are different claims.

    Every test above is static: it reads the table and the parser and compares
    them. None of them proves that a submission carrying a rejected construct
    is actually refused, which is the property anyone cares about.

    These are the booking-dependent shapes specifically, because they are the
    ones that would do damage silently. A cost or price annotation changes
    valuation, and dropping it rather than refusing it is the lossy mapping
    that makes a materially different ledger compare equal.

    Writing this test found a crash: the check deciding whether a rejected
    field was populated used `value in (None, (), [], "")`, which invokes
    `__eq__` on whatever the parser stored, and beancount's `Amount.__eq__`
    unpacks its operand without a type check. A price annotation raised
    AttributeError inside the library. A field we do not model is the last
    thing that should have methods called on it.
    """
    from beancount_ledger.candidate.normalise import ProtocolFailure, parse_once

    head = ('option "operating_currency" "USD"\n'
            "2025-11-01 open Assets:A USD\n2025-11-01 open Assets:B USD\n")
    expected = {
        "price annotation": (
            '2025-11-05 * "N" "x"\n  Assets:A  10.00 EUR @ 1.10 USD\n'
            "  Assets:B  -11.00 USD\n", "posting.price.unmodelled"),
        "total price": (
            '2025-11-05 * "N" "x"\n  Assets:A  10.00 EUR @@ 11.00 USD\n'
            "  Assets:B  -11.00 USD\n", "posting.price.unmodelled"),
        "cost basis": (
            '2025-11-05 * "N" "x"\n  Assets:A  10.00 XYZ {1.10 USD}\n'
            "  Assets:B  -11.00 USD\n", "posting.cost.unmodelled"),
        "foreign currency": (
            '2025-11-05 * "N" "x"\n  Assets:A  10.00 EUR\n'
            "  Assets:B  -10.00 EUR\n", "posting.units.currency"),
    }
    problems = []
    for label, (body, reason) in expected.items():
        result = parse_once(head + body)
        if not isinstance(result, ProtocolFailure):
            problems.append(f"{label}: ACCEPTED, expected {reason}")
        elif result.reason != reason:
            problems.append(f"{label}: refused as {result.reason}, expected {reason}")
    return check(
        "rejected constructs are actually refused, with their own reason",
        not problems,
        "\n".join(problems),
    )


def test_the_numeric_envelope_cuts_where_it_claims_to():
    """Exactness, not digit count, decides. Both sides pinned.

    Worth stating precisely because a review of the corpus spotted an apparent
    inconsistency: fifteen decimal places appears among the *presentation*
    equivalents, while padding and wide lines are *resource* rejections. Both
    are correct and it is one payload, not a case that changed class.

    The rule is that a value exactly representable at the money scale is the
    same money however it is spelled -- 85.000000000000000 is 85.00 -- so it
    canonicalises. A value that is not exactly representable is refused, no
    matter how few digits it uses. 85.005 is three decimal places and is
    rejected; 85.000000000000000 is fifteen and is accepted. Digit count is not
    the test and never was.
    """
    from beancount_ledger.candidate.normalise import ProtocolFailure, parse_once

    head = (
        'option "operating_currency" "USD"\n'
        "2025-11-01 open Assets:A USD\n"
        "2025-11-01 open Assets:B USD\n"
    )

    def classify(amount):
        body = (
            f'2025-11-05 * "Office Depot" "x"\n'
            f"  Assets:A  {amount} USD\n"
            f"  Assets:B  -{amount} USD\n"
        )
        result = parse_once(head + body)
        return "refused" if isinstance(result, ProtocolFailure) else "accepted"

    expected = {
        "85.00": "accepted",
        "85.0": "accepted",
        "85.000000000000000": "accepted",       # exact, however long
        "85.005": "refused",                     # sub-cent, however short
        "85.001": "refused",
        "9" * 40 + ".00": "refused",             # beyond the working precision
    }
    problems = [f"{amount}: expected {want}, got {classify(amount)}"
                for amount, want in expected.items() if classify(amount) != want]
    return check(
        "the numeric envelope cuts on exactness, not on digit count",
        not problems, "\n".join(problems))


TESTS = [
    test_every_directive_is_classified,
    test_the_numeric_envelope_cuts_where_it_claims_to,
    test_the_table_is_enforced_at_runtime,
    test_every_field_of_every_directive_is_classified,
    test_posting_fields_are_classified,
    test_accepted_directives_map_or_canonicalise_their_meaning,
    test_every_rule_names_a_reason,
]


def run() -> int:
    import beancount
    print(f"mapping coverage against beancount {beancount.__version__}\n")
    results = [t() for t in TESTS]
    report_surface()
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
