"""`composite/1`: the cash-application family's reward, an outer
`CompositeOutcome` around the untouched `candidate/1` `ScoreOutcome` and
the `application/1` `ApplicationOutcome` (spec section 4, "Composition").

    total = quantise(L x A, 6 places, half-even)   -- AFTER the product

`L` is `candidate/1`'s total (0 when non-renderable; 0 when no ledger was
ever committed), `A` is `application/1`'s. The product is monotone in its
two component scores and preserves partial credit while both are positive;
a gate on `L.complete` would instead erase application progress whenever
the ledger stayed incomplete. It still has zero-reward edges and plateaus,
and that is not evidence of dense or useful learning feedback.

Without `ApplicationInputs` — a legacy task — there is no application to
score: `compose(ledger, None)` answers `A == 1`, `total == L` and
`complete == L.complete`, the reward as today. For the family a submission
without an application stays legal and scores `A = 0`: the reward is 0 and
`L` is reported diagnostically with no composite credit, otherwise the
deliverable that distinguishes the family would be optional in the reward.

COMPLETE := `L.complete` and the application delivered and `A == 1.000000`
with no penalty label. The label clause is redundant by construction — the
channels sum to at most 1.00, so any penalty drives `A` strictly below 1
and the clamp cannot lift it back — and is asserted anyway as a conformance
check. `total == 1 <=> complete`; an incomplete outcome at 1, or a complete
one below it, raises as `committed.py` does for the ledger.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from .application import APPLICATION_ENGINE_ID, ApplicationOutcome, SCORE_SCALE
from .canonical import canonical_bytes, domain_digest
from .committed import ScoreOutcome

COMPOSITE_ENGINE_ID = "composite/1"
COMPOSITE_RESULT_DOMAIN = b"piv:composite-result:v1\0"
_ONE = Decimal(1)


def _scale(value: Decimal) -> Decimal:
    return value.quantize(SCORE_SCALE, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class CompositeOutcome:
    total: Decimal
    ledger_total: Decimal           # L
    application_total: Decimal      # A (1 when the task has no application)
    complete: bool
    ledger: object                  # the candidate/1 ScoreOutcome, or None when no ledger was committed
    application: object             # the application/1 ApplicationOutcome, or None for a legacy task
    engine_id: str = COMPOSITE_ENGINE_ID
    result_digest: str = ""

    @property
    def engines(self) -> tuple:
        engines = [self.ledger.engine_id if self.ledger is not None else None]
        if self.application is not None:
            engines.append(self.application.engine_id)
        return tuple(engines) + (self.engine_id,)

    def as_canonical(self) -> dict:
        return {
            "total": str(self.total), "ledger_total": str(self.ledger_total),
            "application_total": str(self.application_total), "complete": self.complete,
            "ledger_result_digest": self.ledger.result_digest if self.ledger is not None else "",
            "application_result_digest": self.application.result_digest if self.application is not None else "",
            "application_engine": APPLICATION_ENGINE_ID if self.application is not None else "",
            "engine": self.engine_id,
        }

    def verify(self) -> None:
        if type(self) is not CompositeOutcome:
            raise RuntimeError("the recorded result is not a CompositeOutcome")
        if composite_result_digest(self.as_canonical()) != self.result_digest:
            raise RuntimeError("the recorded composite result no longer reproduces its digest")

    def as_dict(self) -> dict:
        return {"total": self.total, "ledger_total": self.ledger_total, "application_total": self.application_total,
                "complete": self.complete, "engine": self.engine_id,
                "ledger": self.ledger.as_dict() if self.ledger is not None else None,
                "application": self.application.as_dict() if self.application is not None else None}


def composite_result_digest(result_canonical: dict) -> str:
    return domain_digest(COMPOSITE_RESULT_DOMAIN, canonical_bytes(result_canonical))


def compose(ledger, application) -> CompositeOutcome:
    """`ledger` is the `candidate/1` outcome (or None when no ledger was
    committed); `application` the `application/1` outcome, or None for a
    task without `ApplicationInputs`."""
    if ledger is not None and type(ledger) is not ScoreOutcome:
        raise TypeError("compose takes the candidate/1 ScoreOutcome (or None)")
    if application is not None and type(application) is not ApplicationOutcome:
        raise TypeError("compose takes the application/1 ApplicationOutcome (or None for a legacy task)")
    ledger_total = Decimal(ledger.total) if ledger is not None else Decimal(0)
    if application is None:
        application_total = _ONE
        application_ok = True
    else:
        application_total = Decimal(application.total)
        application_ok = application.delivered and application_total == _ONE and not application.penalties
    total = _scale(ledger_total * application_total)
    complete = ledger is not None and bool(ledger.complete) and application_ok
    if not complete and total >= _ONE:
        raise RuntimeError("an incomplete composite outcome reached the maximum reward")
    if complete and total != _ONE:
        raise RuntimeError("a complete composite outcome is below the maximum reward")
    outcome = CompositeOutcome(total=total, ledger_total=ledger_total, application_total=application_total,
                               complete=complete, ledger=ledger, application=application)
    return dataclasses.replace(outcome, result_digest=composite_result_digest(outcome.as_canonical()))
