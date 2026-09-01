"""Canonical rendering: the algebraic properties, and the injection retirement.

Three claims, in order of how much they prove.

**Round trip.** `normalise(render(c)) == c`. The canonical form of a candidate
parses back to that candidate, so rendering loses nothing the type carries.

**Byte idempotence.** `render(normalise(render(c))) == render(c)`. There is one
spelling and passing through it again does not move.

**One meaning, one file.** Six submissions that differ wildly as text — one
carrying a fabricated audit block, one stamping every entry with tags, one
flagging everything unverified, one writing amounts as arithmetic, one padding
to fifteen decimal places, one naming the counterparty in mocking case — render
to bytes identical to the correct solution's.

That third one is the redesign stated as a measurement. Each of those six cost
a review round and a hand-written rule under the old scorer. None is detected
here. They are the same file.

The injection case is worth stating separately because it was the most
dangerous and the fix is the least like a fix. A submission prepended a block
headed as the audited ledger, telling the reader to ignore the entries below,
and the parser did not see it — full marks, with a payload for whatever model
read the file downstream. The test asserts the payload is in the submitted
bytes and absent from the rendered output. Nothing detects it. Comments are not
in the candidate type, so there is nowhere for it to be.

    python tests/test_render.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.candidate.entities import build_resolver  # noqa: E402
from beancount_ledger.candidate.normalise import (  # noqa: E402
    EvaluationFailure,
    ProtocolFailure,
    parse_once,
)
from beancount_ledger.candidate.schema import LedgerCandidate  # noqa: E402
from beancount_ledger.candidate.render import (  # noqa: E402
    NotRenderable,
    prepare_render,
    render,
)

SOLUTIONS = Path(__file__).resolve().parent / "solutions"
WORLD = ROOT / "beancount_ledger" / "world"
TITLE = "Alpine Trading Co."

# Payloads that say the same thing as the correct solution in different bytes.
EQUIVALENT = [
    "bad_comment_injection",
    "bad_tagged_entries",
    "bad_pending_flags",
    "bad_computed_amounts",
    "bad_overprecise_amounts",
    "bad_mocking_case",
]


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:10]:
            print(f"      {line}")
    return ok


_RESOLVER = None


def resolver():
    global _RESOLVER
    if _RESOLVER is None:
        _RESOLVER = build_resolver(WORLD).resolve
    return _RESOLVER


def candidate(text):
    """Parse, tolerating domain findings — this file tests rendering."""
    result = parse_once(text, entity_resolver=resolver())
    if isinstance(result, (ProtocolFailure, EvaluationFailure)):
        return None
    return result.candidate


def golden():
    return candidate((SOLUTIONS / "golden.beancount").read_text(encoding="utf-8"))


def canonical(c, title=None):
    """Render a candidate known to have no violations.

    Goes through `prepare_render` rather than passing `violations=[]`, because
    the point of the gate is that clearing a candidate is an explicit step. A
    test that skips it would be testing a path production does not use.
    """
    prepared = prepare_render(c)
    assert not isinstance(prepared, NotRenderable), prepared
    return render(prepared, title=TITLE if title is None else title)


def test_round_trip():
    """A rendered candidate parses back to the same candidate."""
    original = golden()
    back = candidate(canonical(original))
    return check("normalise(render(c)) == c", back == original,
                 "the canonical form does not parse back to itself")


def test_render_is_byte_idempotent():
    once = canonical(golden())
    twice = canonical(candidate(once))
    return check("render(normalise(render(c))) is byte-identical to render(c)",
                 once == twice)


def test_equivalent_submissions_render_identically():
    """Six hostile payloads, one output.

    If any of these ever differs, a presentation channel has leaked into the
    candidate type and the corresponding hand-written rule will be needed
    again.
    """
    target = canonical(golden())
    differs = []
    for name in EQUIVALENT:
        text = (SOLUTIONS / f"{name}.beancount").read_text(encoding="utf-8")
        produced = candidate(text)
        if produced is None:
            differs.append(f"{name}: did not produce a candidate at all")
        elif canonical(produced) != target:
            differs.append(f"{name}: renders differently from the correct solution")
    return check(
        f"{len(EQUIVALENT)} equivalent submissions render to identical bytes",
        not differs, "\n".join(differs))


def test_the_injection_payload_does_not_survive():
    """Present in the submission, absent from the canonical output."""
    text = (SOLUTIONS / "bad_comment_injection.beancount").read_text(encoding="utf-8")
    in_submission = "IGNORE" in text.upper()
    output = canonical(candidate(text))
    in_output = "IGNORE" in output.upper() or ";" in output
    return check(
        "the injected block is in the submission and not in the rendered output",
        in_submission and not in_output,
        f"in submission: {in_submission}, in output: {in_output}")


def test_a_semantic_difference_does_survive():
    """The other half of the pair, and the one that matters most.

    Every test above says two different files produce one output. On its own
    that is equally consistent with a renderer that discards everything — the
    strongest possible presentation-equivalence result would be produced by a
    function returning the empty string.

    So: a submission that genuinely differs must render differently.
    """
    target = canonical(golden())
    same = []
    for name in ("bad_merged_events", "bad_deleted_check", "bad_wash_transaction",
                 "baseline_untouched"):
        produced = candidate((SOLUTIONS / f"{name}.beancount").read_text(encoding="utf-8"))
        if produced is not None and canonical(produced) == target:
            same.append(f"{name}: renders identically to the correct solution")
    return check("semantically different submissions render differently",
                 not same, "\n".join(same))


def test_the_output_is_a_ledger_beancount_accepts():
    """Integration: the canonical artifact must itself be valid.

    An output that only our own parser accepts would be a private dialect, and
    the point of emitting a canonical file is that something else can read it.
    """
    from beancount.parser import parser

    output = canonical(golden())
    entries, errors, _ = parser.parse_string(output)
    return check("the canonical output parses cleanly as beancount",
                 not errors and entries,
                 f"{len(errors)} error(s), {len(entries)} entries")


def test_a_non_renderable_candidate_gets_a_typed_refusal():
    """The algebra's domain, made explicit.

    Round trip and idempotence are quantified over candidates the policy
    permits rendering. A duplicate `open` is intentionally outside that domain,
    and the tests above simply never reach it — which is the kind of silent
    precondition someone later widens `render()` past without noticing.

    So the excluded case is asserted rather than skipped: it must come back as
    a typed refusal, not as bytes and not as an exception. Bytes would emit an
    artifact the environment has already decided is unusable; an exception
    would make a predictable outcome look like a crash.
    """
    from beancount_ledger.candidate.schema import AccountLifecycle

    # A candidate the policy blocks: the same account opened twice.
    clean = golden()
    duplicated = LedgerCandidate(
        clean.operating_currency,
        clean.lifecycle + (AccountLifecycle("open", "2025-06-01",
                                            clean.lifecycle[0].account),),
        clean.events)

    result = prepare_render(duplicated)
    refused = isinstance(result, NotRenderable) and not result
    still_renders_clean = isinstance(canonical(clean), str)
    return check(
        "a policy-blocked candidate returns a typed refusal, not bytes",
        refused and still_renders_clean,
        f"refused: {refused} ({result}), clean still renders: {still_renders_clean}")


def test_the_caller_cannot_vouch_for_a_bad_candidate():
    """The gate must compute violations, not accept them.

    The previous version took a violation list from the caller, so
    `prepare_render(bad, violations=[])` cleared anything — the gate trusted
    the caller to have run validation honestly and completely. A capability has
    to be issued from authoritative inputs, never from a claim about them.

    There is now no parameter to lie with; this asserts the malformed candidate
    is refused however it is presented.
    """
    from beancount_ledger.candidate.schema import AccountLifecycle

    clean = golden()
    duplicated = LedgerCandidate(
        clean.operating_currency,
        clean.lifecycle + (AccountLifecycle("open", "2025-06-01",
                                            clean.lifecycle[0].account),),
        clean.events)
    import inspect

    refused = isinstance(prepare_render(duplicated), NotRenderable)
    # Parameters only. `violations` is a local inside the function now, which
    # is exactly the point — it is computed there rather than received.
    no_such_argument = "violations" not in inspect.signature(prepare_render).parameters
    return check(
        "the gate computes violations itself and takes none from the caller",
        refused and no_such_argument,
        f"refused: {refused}, no violations parameter: {no_such_argument}")


def test_a_capability_cannot_be_repointed_after_issuance():
    """Time of check is not time of use.

    The capability held its candidate in a writable slot, so this worked:

        cap = prepare_render(good)
        cap.candidate = malformed
        render(cap)

    A capability that can be repointed certifies whatever it happens to be
    holding when it is read, which is not what it was issued for. The fields
    are read-only now and the capability carries a digest of the exact
    semantics it cleared, rechecked at render time.
    """
    from beancount_ledger.candidate.schema import AccountLifecycle

    clean = golden()
    duplicated = LedgerCandidate(
        clean.operating_currency,
        clean.lifecycle + (AccountLifecycle("open", "2025-06-01",
                                            clean.lifecycle[0].account),),
        clean.events)

    cap = prepare_render(clean)
    problems = []
    for attribute in ("candidate", "_candidate", "task", "_task"):
        try:
            setattr(cap, attribute, duplicated)
            problems.append(f"{attribute} was reassignable")
        except AttributeError:
            pass

    # And the semantics it holds are still the ones that were cleared.
    still_clean = cap.release("bank_reconciliation") == clean
    return check(
        "a capability cannot be repointed after it is issued",
        not problems and still_clean,
        "\n".join(problems) or f"released the cleared candidate: {still_clean}")


def test_a_capability_does_not_transfer_between_tasks():
    """Renderability is a decision under a policy, so it is bound to one.

    A candidate cleared under a lenient task must not be renderable by a
    stricter task's renderer. Without the binding, a capability is a claim that
    some policy somewhere permitted this — which is not the same as the policy
    now in force permitting it.
    """
    prepared = prepare_render(golden(), task="bank_reconciliation")
    try:
        render(prepared, title=TITLE, task="period_close")
        return check("a capability does not transfer between tasks", False,
                     "it rendered under a different task")
    except ValueError as exc:
        return check("a capability does not transfer between tasks",
                     "does not transfer" in str(exc), str(exc))


def test_a_bare_candidate_without_violations_is_refused():
    """The gate must not be skippable by omitting an argument.

    The earlier API took optional violations and returned a falsey refusal, so
    `render(c, title=...)` reached bytes without consulting the policy at all.
    A policy gate that a caller can decline to invoke is not a gate.
    """
    try:
        render(golden(), title=TITLE)
        return check("a bare candidate is refused by render()", False,
                     "it rendered without consulting the policy")
    except TypeError as exc:
        return check("a bare candidate is refused by render()",
                     "policy gate" in str(exc), str(exc))


def test_a_renderable_candidate_cannot_be_forged():
    """Only `prepare_render` may mint one."""
    from beancount_ledger.candidate.render import RenderableCandidate

    try:
        RenderableCandidate(golden(), 'bank_reconciliation', object())
        return check("RenderableCandidate cannot be constructed directly", False,
                     "it was constructed without the gate")
    except TypeError as exc:
        return check("RenderableCandidate cannot be constructed directly",
                     "prepare_render" in str(exc), str(exc))


TESTS = [
    test_round_trip,
    test_a_bare_candidate_without_violations_is_refused,
    test_the_caller_cannot_vouch_for_a_bad_candidate,
    test_a_capability_does_not_transfer_between_tasks,
    test_a_capability_cannot_be_repointed_after_issuance,
    test_a_renderable_candidate_cannot_be_forged,
    test_a_non_renderable_candidate_gets_a_typed_refusal,
    test_render_is_byte_idempotent,
    test_equivalent_submissions_render_identically,
    test_a_semantic_difference_does_survive,
    test_the_injection_payload_does_not_survive,
    test_the_output_is_a_ledger_beancount_accepts,
]


def run() -> int:
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
