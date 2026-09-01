"""Entity resolution: what counts as naming the same counterparty.

The old scorer compared the payee field to a fixed string, case sensitively.
That rule was undisclosed, it cost three review rounds to defend, and what it
trained was verbatim transcription rather than judgement about who the
counterparty was.

Resolution replaces it, and the tests here are deliberately paired, because a
normalisation rule can fail in two opposite directions and a single-sided test
suite will only ever catch one of them. Too strict and a correct submission is
punished for a spelling; too generous and two different companies become one.
Each pair below fixes one edge from both sides.

    python tests/test_entities.py
"""

import csv
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.candidate.entities import build_resolver  # noqa: E402
from beancount_ledger.candidate.normalise import (  # noqa: E402
    ProtocolFailure,
    parse_once,
)

WORLD = ROOT / "beancount_ledger" / "world"


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines():
            print(f"      {line}")
    return ok


def test_spellings_of_one_entity_resolve_together():
    """Case, punctuation, suffix and Unicode form do not change who was paid."""
    resolve = build_resolver(WORLD).resolve
    target = "Harbor Freight Ltd"
    spellings = [
        "Harbor Freight Ltd",
        "harbor freight ltd",
        "hArBoR fReIgHt lTd.",          # defeated a lenient case rule once
        "Harbor Freight",                # the suffix is not the identity
        "Harbor Freight, Ltd.",
        "Ｈａｒｂｏｒ Ｆｒｅｉｇｈｔ Ｌｔｄ",              # fullwidth lookalike
        "Harbor Freight Ltd",  # non-breaking spaces
    ]
    wrong = {s: resolve(s) for s in spellings if resolve(s) != target}
    return check(
        "every spelling of one entity resolves to it",
        not wrong,
        "\n".join(f"{k!r} -> {v!r}" for k, v in wrong.items()),
    )


def test_text_that_merely_contains_a_name_resolves_to_nobody():
    """Containment is not identity — the other side of the pair above.

    A substring test lasted exactly one review round: "Definitely not Harbor
    Freight or SI-1044" contains the accepted name and asserts its opposite.
    Resolution compares whole normalised values, so a sentence is not a name
    however many names it mentions.
    """
    resolve = build_resolver(WORLD).resolve
    resolved = {
        text: resolve(text)
        for text in (
            "Definitely not Harbor Freight or SI-1044",
            "Harbor Freight is not the counterparty here",
            "x",
            "",
            "Some Company That Does Not Exist",
        )
        if resolve(text) is not None
    }
    return check(
        "text that merely mentions a name resolves to nobody",
        not resolved,
        "\n".join(f"{k!r} -> {v!r}" for k, v in resolved.items()),
    )


def test_an_unresolved_entity_is_a_candidate_not_a_refusal():
    """Naming nobody is a bookkeeping defect, not an unreadable submission.

    The distinction matters for what the environment reports about itself. A
    protocol failure says "we could not read this"; an entry naming nobody is
    perfectly readable and simply cannot be tied to a document. Collapsing the
    second into the first would inflate the refusal rate, which is the health
    metric for whether our accepted subset is too narrow -- and would blame the
    contract for what is actually a wrong answer.
    """
    resolve = build_resolver(WORLD).resolve
    text = (
        'option "operating_currency" "USD"\n'
        "2025-11-01 open Assets:A USD\n"
        "2025-11-01 open Assets:B USD\n"
        '2025-11-05 * "Nobody At All" "N"\n'
        "  Assets:A   1.00 USD\n"
        "  Assets:B  -1.00 USD\n"
    )
    result = parse_once(text, entity_resolver=resolve)
    ok = not isinstance(result, ProtocolFailure) and result.candidate.events[0].entity is None
    return check(
        "an unidentifiable counterparty yields a candidate, not a protocol failure",
        ok,
        result if isinstance(result, ProtocolFailure) else f"entity={result.candidate.events[0].entity!r}",
    )


def test_a_colliding_register_is_refused_when_the_world_is_built():
    """Two entities sharing one key must fail at build time, not scoring time.

    Normalisation that makes more spellings equal is only safe while distinct
    entities stay distinct. If a generated register ever contains two companies
    that collapse together, a submission naming one resolves to the other and
    the lossy mapping becomes a wrong answer marked right. That is a defect in
    the world, discoverable when the world is made.
    """
    directory = Path(tempfile.mkdtemp())
    with (directory / "vendors.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["vendor", "terms", "default_account"])
        writer.writerow(["Acme Ltd", "net 30", "Expenses:Office"])
        writer.writerow(["ACME, LLC", "net 30", "Expenses:Office"])
    try:
        build_resolver(directory)
        return check("a colliding register is refused at build time", False,
                     "the ambiguous register was accepted")
    except ValueError as exc:
        return check("a colliding register is refused at build time",
                     "ambiguous" in str(exc), str(exc))


def test_the_shipped_world_has_no_collisions():
    """The world we actually ship must satisfy the invariant it declares."""
    try:
        register = build_resolver(WORLD)
    except ValueError as exc:
        return check("the shipped register is unambiguous", False, str(exc))
    return check(f"the shipped register is unambiguous ({len(register)} entities)", True)


TESTS = [
    test_spellings_of_one_entity_resolve_together,
    test_text_that_merely_contains_a_name_resolves_to_nobody,
    test_an_unresolved_entity_is_a_candidate_not_a_refusal,
    test_a_colliding_register_is_refused_when_the_world_is_built,
    test_the_shipped_world_has_no_collisions,
]


def run() -> int:
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
