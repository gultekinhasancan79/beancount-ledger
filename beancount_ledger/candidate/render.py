"""Canonical rendering: a LedgerCandidate back to bytes.

The last stage of the boundary, and the one that makes the submitted file safe
to pass downstream:

    bytes -> parse -> candidate -> validate -> RENDER THE CANDIDATE

**From the candidate, never from gold.** Rendering from hidden truth would make
the scorer repair the submission before judging it — the sanitiser placed on
the wrong side of a comparison becomes a corrector. What comes out here is what
the agent actually said, spelled the one way this system spells things.

That is what retires the injection attack rather than catching it. A submission
once prepended a block headed as the audited ledger telling the reader to
ignore the entries below, and the parser did not see it, so it scored full
marks while carrying a payload for whatever model read the file next. Under
this pipeline the comment is not in the candidate type, so it is not in the
output. Nothing detects it; there is nowhere for it to be.

The same applies to everything else that needed its own rule: tags, flags,
narration wording, blank-line padding, fifty-thousand-character lines,
arithmetic amounts, fifteen decimal places. Two submissions that mean the same
thing render to identical bytes, which is the property the whole redesign was
for and is directly testable:

    normalise(render(c)) == c            round trip
    render(normalise(render(c))) == render(c)    byte idempotence
"""

from __future__ import annotations

from .schema import LedgerCandidate

# One flag, chosen here rather than read from the submission. Scoring the
# agent's spelling of a flag it was never told about was one of the four
# undisclosed rules the M0 review found, and the fix was not to disclose it.
FLAG = "*"

ACCOUNT_WIDTH = 38
AMOUNT_WIDTH = 14


class NotRenderable:
    """A typed refusal, returned instead of bytes.

    Some candidates are intentionally non-renderable — a ledger with a
    duplicated `open` directive describes intelligible bookkeeping but cannot
    be written out as a canonical file. Returning bytes anyway would emit an
    artifact the environment has decided is unusable; raising would make a
    predictable outcome look like a crash.
    """

    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return f"not renderable ({self.reason}): {self.detail}"


class RenderableCandidate:
    """A candidate the policy has cleared for canonical output, under a task.

    Only obtainable from `prepare_render`. Two earlier versions of this gate
    were bypassable and the second bypass is the more interesting one.

    The first took optional violations and returned a falsey refusal, so
    `render(c)` reached bytes without the policy being consulted at all — a
    gate the caller could decline to invoke.

    The second required violations but let the *caller supply them*. So
    `prepare_render(bad_candidate, violations=[])` cleared anything: the gate
    trusted the caller to have run validation honestly and completely. A
    capability has to be issued from authoritative inputs, never from a
    caller's claim about them, so `prepare_render` now runs the validator
    itself and there is no parameter to lie with.

    `task` is bound into the capability because renderability is a decision
    *under a policy*. A candidate cleared under one task's lenient rules must
    not be renderable by another task's renderer, and the binding is checked at
    render time rather than trusted.

    The third bypass was time-of-check to time-of-use. The capability held a
    reference in a writable slot, so this worked:

        cap = prepare_render(good_candidate)
        cap.candidate = malformed_candidate
        render(cap)

    A capability that can be repointed after issuance certifies whatever it is
    holding at the moment it is read, which is not what it was issued for. So
    the fields are read-only and the capability carries a digest of the exact
    semantics it cleared, verified again at render time.

    `LedgerCandidate` is deeply immutable already — frozen dataclasses all the
    way down, with tuples rather than lists — so the digest is belt and braces
    against a future field that is not. Which is the point: the check should
    not depend on someone remembering that invariant.
    """

    __slots__ = ("_candidate", "_task", "_digest")

    def __init__(self, candidate: LedgerCandidate, task: str, _token: object):
        if _token is not _PREPARED:
            raise TypeError(
                "RenderableCandidate is obtained from prepare_render(), not "
                "constructed; building one directly would bypass the policy "
                "gate it exists to enforce"
            )
        object.__setattr__(self, "_candidate", candidate)
        object.__setattr__(self, "_task", task)
        object.__setattr__(self, "_digest", digest_of(candidate))

    def __setattr__(self, name, value):
        raise AttributeError(
            "a render capability is immutable; repointing it after issuance "
            "would certify semantics the policy never saw"
        )

    def __delattr__(self, name):
        raise AttributeError("a render capability is immutable")

    @property
    def task(self) -> str:
        return self._task

    @property
    def digest(self) -> str:
        return self._digest

    def release(self, task: str) -> LedgerCandidate:
        """Hand back the cleared semantics, re-checking both bindings."""
        if self._task != task:
            raise ValueError(
                f"this candidate was cleared under {self._task!r} and is being "
                f"rendered under {task!r}; renderability is a decision under a "
                f"policy, so a capability from one task does not transfer"
            )
        if digest_of(self._candidate) != self._digest:
            raise ValueError(
                "the candidate changed after the capability was issued; what "
                "the policy cleared is not what is being rendered"
            )
        return self._candidate


_PREPARED = object()


def digest_of(candidate: LedgerCandidate) -> str:
    """A stable fingerprint of a candidate's semantics.

    Over the semantic content only, so it is the same question the comparison
    asks: two candidates that mean the same thing have the same digest, and
    anything that would change the rendered file changes it.
    """
    import hashlib

    parts = [candidate.operating_currency]
    for item in candidate.lifecycle:
        parts.append(f"{item.kind}|{item.date}|{item.account}|{','.join(item.currencies)}")
    for event in candidate.events:
        legs = ";".join(f"{p.account}={p.amount}" for p in event.postings)
        parts.append(f"{event.date}|{event.entity}|{event.source_ref}|{legs}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def prepare_render(candidate: LedgerCandidate, task: str = "bank_reconciliation"):
    """Ask the task policy whether this candidate may be written out.

    Violations are **computed here**, not accepted from the caller. That is the
    whole point of the function: the capability is issued from the candidate
    itself, so there is no argument through which a caller can assert that a
    malformed ledger is clean.

    Returns `RenderableCandidate` or `NotRenderable`, and the caller has to
    handle both.
    """
    from .policy import consequences
    from .validate import validate_candidate

    violations = validate_candidate(candidate)
    if violations:
        from .canonical import summarise_findings
        blocked = [c for c in consequences(summarise_findings(violations), task) if c.blocks_render]
        if blocked:
            return NotRenderable(
                "policy",
                f"{len(blocked)} violation(s) block canonical output under "
                f"{task}: {violations[0]}",
            )
    return RenderableCandidate(candidate, task, _PREPARED)


def render(candidate, *, title: str = "",
           task: str = "bank_reconciliation") -> str:
    """The one spelling of this candidate.

    Ordering is derived from content, not preserved from input: lifecycle
    directives then events, each sorted by their own fields. Entry order was a
    presentation channel like any other, and a canonical form that preserved it
    would let two identical ledgers render differently.

    **The algebra holds only over renderable candidates.** That precondition is
    stated here rather than left implicit, because the round-trip and
    idempotence tests silently skip non-renderable values, and a later widening
    of this function would inherit an algebra nobody had checked:

        for c where policy permits render:  normalise(render(c)) == c

    Accepts only a `RenderableCandidate`, and verifies that its capability was
    issued under the task now rendering it. A bare `LedgerCandidate` is refused
    outright: there is no path to bytes that does not pass through the gate,
    and no argument a caller can use to assert their way past it.
    """
    if not isinstance(candidate, RenderableCandidate):
        raise TypeError(
            "render() takes a RenderableCandidate from prepare_render(); a bare "
            "candidate would skip the policy gate, and an argument saying it is "
            "already clean would be the caller vouching for itself"
        )
    candidate = candidate.release(task)
    lines: list[str] = []
    if title:
        lines.append(f'option "title" "{_escape(title)}"')
    lines.append(f'option "operating_currency" "{candidate.operating_currency}"')
    lines.append("")

    for item in candidate.lifecycle:
        if item.kind == "open":
            currencies = " ".join(item.currencies) or candidate.operating_currency
            lines.append(f"{item.date} open {item.account:<{ACCOUNT_WIDTH}} {currencies}")
        else:
            lines.append(f"{item.date} close {item.account}")
    if candidate.lifecycle:
        lines.append("")

    for event in candidate.events:
        payee = _escape(event.entity) if event.entity else ""
        lines.append(f'{event.date} {FLAG} "{payee}" ""')
        if event.source_ref:
            key, _, value = event.source_ref.partition(":")
            lines.append(f'  {key}: "{_escape(value)}"')
        for posting in event.postings:
            amount = f"{posting.amount:.2f}"
            lines.append(
                f"  {posting.account:<{ACCOUNT_WIDTH}} {amount:>{AMOUNT_WIDTH}} "
                f"{candidate.operating_currency}"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _escape(value: str) -> str:
    """Quote-safe, without inventing an escaping language.

    Beancount strings are double-quoted with no escape sequence we rely on, so
    an embedded quote is removed rather than escaped. That is lossy and it is
    the right kind of lossy: the field is a name resolved against a register,
    and no registered entity contains a quote. If one ever does, the collision
    check in the register is where it should surface, not here.
    """
    return (value or "").replace('"', "").replace("\n", " ").strip()
