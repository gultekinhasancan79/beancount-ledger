"""From one bundle: the opening ledger, the repair predicates, the accepted
counterparties, the targets, the expected facts and the golden deliverable.

`ContractInputs` is a capability, not a record. It is minted here only,
after the projector's exhaustive classification, the accounting invariants
and the independent Beancount oracle have all passed, and it consumes its
mint token at construction: `dataclasses.replace`, a hand-built instance
and a dict with the same keys are all refused by `load_contract`. A literal
target balance or a hand-typed posting tuple therefore cannot enter the
contract — not because a runtime wrapper is a security boundary against
repository code (it is not), but because accidental dual authority should
fail loudly at composition rather than pass quietly as a fixture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..candidate.canonical import canonical_decimal
from ..candidate.normalise import Accepted, parse_once
from itertools import combinations

from .project import (
    ARCHIVE_VIEW,
    EXPECTED_LEDGER_VIEW,
    LEDGER_VIEW,
    STATEMENT_VIEW,
    AlterRecognition,
    Bundle,
    DuplicateRecognition,
    MutationPlan,
    OmitRecognition,
    Period,
    Reason,
    derive_mutant,
    project,
    check_bundle,
)
from .schema import DocumentKind, World

_DERIVED_TOKEN = object()


class DerivationError(Exception):
    """The world, the plan or the oracle refused. Ours, at composition."""


@dataclass(frozen=True)
class TaskSpec:
    """The authored half of a task: its identity, the instruction the agent
    reads, the period, and the mutation plan by recognition id. Nothing
    here is a number the scorer compares against."""

    id: str
    type: str
    prompt: str
    period: Period
    plan: MutationPlan


PUBLIC_KIND = {"omit": "missing_entry", "alter": "wrong_amount", "duplicate": "duplicate"}


def planted_key(spec, master_names, *, bank_account: str) -> tuple:
    """The TRUTH side of the shared repair key: the same
    tuple type `identify.repair_key` builds from a checker repair —

        (kind, date, postings, counterparty, booked bank amount, copies)

    — implemented here independently of the checker (no shared serializer:
    a common-mode fault in one projection must show up as a mismatch, not
    hide in both). `postings` is the sorted tuple of (account, amount to two
    places) of the entry the corrected books carry; `counterparty` is the
    accepted payee when it is a master-file name, else None (the bank is not
    a party); `booked` is the wrong bank leg of an altered entry; `copies`
    is the expected count of a duplicated occurrence. Narration, flags,
    metadata and posting order are not identity — the scorer's
    RETAINED_FIELDS says the same. CURRENCY is deliberately absent from
    `postings` because a single operating currency is an ENFORCED INVARIANT
    at the parse boundary (`posting.units.currency`, `posting.cost.unmodelled`,
    `posting.price.unmodelled`, `option.operating_currency.not_single`), not
    an oversight; the same paragraph stands on `identify.repair_key`."""
    if spec.kind not in PUBLIC_KIND:
        raise ValueError(f"unknown planted kind {spec.kind!r}")
    postings = tuple(sorted((account, f"{Decimal(value):.2f}") for account, value in spec.required))
    booked = None
    if spec.kind == "alter":
        legs = [f"{Decimal(value):.2f}" for account, value in spec.replaces if account == bank_account]
        if len(legs) != 1:
            raise ValueError(f"{spec.id}: the replaced shape must have exactly one leg on {bank_account}")
        booked = legs[0]
    payee = spec.must_be_payee[0] if spec.must_be_payee else None
    return (PUBLIC_KIND[spec.kind], spec.date, postings, payee if payee in master_names else None, booked,
            int(spec.expected_count))


@dataclass(frozen=True)
class PlantedSpec:
    id: str
    recognition_id: str
    date: str
    required: tuple            # ((account, canonical amount), ...) sorted — the recognition's legs
    must_be_payee: tuple       # accepted counterparties under the task's comparison policy
    narration: str             # the recognition's memo: what the canonical deliverable prints for this repair
    evidence: tuple            # public observation records that make the repair inferable
    identifiability_claim: str
    kind: str = "omit"         # omit | alter | duplicate
    replaces: tuple = ()       # alter: the WRONG shape as booked, ((account, canonical amount), ...) sorted
    expected_count: int = 1    # duplicate: how many copies the correct books carry
    residual: tuple = ()       # ((account, Decimal), ...): clean vector minus observed vector, non-zero entries only

    def __post_init__(self):
        # A sum type by validation: the field combinations that do not
        # belong to the kind fail here, not in a scorer branch.
        if self.kind == "omit" and (self.replaces or self.expected_count != 1):
            raise TypeError("an omitted item has no replaced shape and no count")
        if self.kind == "alter" and (not self.replaces or self.replaces == self.required or self.expected_count != 1):
            raise TypeError("an altered item names the wrong shape it replaces")
        if self.kind == "duplicate" and (self.replaces or self.expected_count != 1):
            raise TypeError("a duplicate item has no replaced shape and expects one copy")
        if self.kind not in ("omit", "alter", "duplicate"):
            raise TypeError(f"unknown planted kind {self.kind!r}")
        if not self.residual:
            raise TypeError("a planted item without a residual changes nothing")


@dataclass(frozen=True)
class TrapSpec:
    id: str
    recognition_id: str
    movement_id: str
    date: str
    cleared_on: str
    amount: Decimal
    narration: str


@dataclass(frozen=True)
class ContractInputs:
    task_id: str
    task_type: str
    prompt: str
    period: Period
    world_id: str
    currency: str
    scored_accounts: tuple
    expected_balances: tuple
    allowed_accounts: tuple
    planted: tuple
    traps: tuple
    original_text: str
    golden_text: str
    statement_closing: Decimal
    graph_digest: str
    mutation_plan_digest: str
    view_digests: tuple
    public_files: tuple        # ((name, bytes), ...)
    _mint: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self._mint is not _DERIVED_TOKEN:
            raise TypeError("ContractInputs are minted by derive_contract() only; literal values are refused")
        object.__setattr__(self, "_mint", None)

    def contract_view(self) -> dict:
        """The normative declared data the task contract digest binds."""
        return {
            "id": self.task_id, "type": self.task_type, "prompt": self.prompt,
            "period": {"start": self.period.start, "end": self.period.end},
            "world_id": self.world_id, "currency": self.currency,
            "scored_accounts": list(self.scored_accounts),
            "expected_balances": [[a, v] for a, v in self.expected_balances],
            "allowed_accounts": list(self.allowed_accounts),
            "planted": [{"id": p.id, "kind": p.kind, "date": p.date, "required": [list(r) for r in p.required],
                         "replaces": [list(r) for r in p.replaces], "expected_count": p.expected_count,
                         "residual": [[a, v] for a, v in p.residual],
                         "must_be_payee": list(p.must_be_payee)} for p in self.planted],
            "traps": [{"id": t.id, "date": t.date, "amount": t.amount} for t in self.traps],
            "statement_closing": self.statement_closing,
            "graph_digest": self.graph_digest, "mutation_plan_digest": self.mutation_plan_digest,
            "view_digests": [list(x) for x in self.view_digests],
        }

    def legacy_task_view(self) -> dict:
        """The shape of the archived task file's normative keys, for the
        old-versus-new comparison. Consumed by tests; never by production."""
        return {
            "id": self.task_id, "type": self.task_type, "period_end": self.period.end, "prompt": self.prompt,
            "statement_closing_balance": f"{self.statement_closing:.2f}",
            "scored_accounts": list(self.scored_accounts),
            "expected_balances": {a: f"{v:.2f}" for a, v in self.expected_balances},
            "planted": [{"id": p.id, "required_postings": [[a, f"{Decimal(v):.2f}"] for a, v in p.required],
                         "date": p.date, "must_be_payee": list(p.must_be_payee)} for p in self.planted],
            "traps": [{"id": t.id, "narration": t.narration} for t in self.traps],
            "allowed_accounts": list(self.allowed_accounts),
        }


def derive_contract(world: World, task: TaskSpec) -> tuple[Bundle, ContractInputs]:
    bundle = project(world, task.period, task.plan)
    problems = check_bundle(world, bundle)
    if problems:
        raise DerivationError("accounting invariants: " + "; ".join(problems))

    # The independent engine: Beancount books the rendered expected ledger
    # through the trust boundary, and its balances must equal a fold this
    # module performs itself over the recognitions — neither reads the
    # projector's balance helper.
    expected_text = bundle.view(EXPECTED_LEDGER_VIEW).text
    booked = parse_once(expected_text)
    if not isinstance(booked, Accepted) or not booked.domain_valid:
        raise DerivationError(f"the expected ledger is not accepted clean by the boundary: {booked}")
    present = {o.node_ids[0] for o in bundle.view(EXPECTED_LEDGER_VIEW).observations if o.node_ids[0].startswith("rec:")}
    fold: dict[str, Decimal] = {}
    for rec in bundle.recognitions:
        if rec.id in present:
            for leg in rec.legs:
                fold[leg.account] = fold.get(leg.account, Decimal("0")) + leg.amount
    for account, value in bundle.expected_balances:
        booked_value = booked.candidate.balances.get(account, Decimal("0"))
        if booked_value != value or fold.get(account, Decimal("0")) != value:
            raise DerivationError(f"oracle disagreement on {account}: beancount {booked_value}, fold {fold.get(account)}, "
                                  f"projection {value}")
    opening = parse_once(bundle.view(LEDGER_VIEW).text)
    if not isinstance(opening, Accepted) or not opening.domain_valid:
        raise DerivationError(f"the opening ledger is not accepted clean by the boundary: {opening}")

    # planted predicates: from the omitted recognitions and nothing else
    statement = bundle.view(STATEMENT_VIEW)
    planted = []
    ledger_view = bundle.view(LEDGER_VIEW)
    expected_view = bundle.view(EXPECTED_LEDGER_VIEW)
    # The complete retained-field identity of every recognition in the
    # expected period (date, payee, narration, sorted legs): key collisions
    # between a planted item and anything unrelated are UnsupportedTopology
    # at derivation, never resolved by allocation order.
    def full_key(r):
        # The date is the EFFECTIVE date — the one the expected ledger prints
        # — so an omitted item restated onto the bank's date is audited for
        # uniqueness where it actually lands, not where the graph drew it.
        return (bundle.effective_date(r), r.payee, r.narration,
                tuple(sorted((l.account, canonical_decimal(l.amount)) for l in r.legs)))
    expected_keys: dict = {}
    for r in bundle.recognitions:
        if r.id in expected_view.subjects():
            expected_keys.setdefault(full_key(r), []).append(r.id)
    events_used: set = set()
    for m in task.plan.mutations:
        rec = bundle.recognition(m.recognition_id)
        if rec.event_id in events_used:
            raise DerivationError(f"{m.mutation_id}: two planted items on one economic event")
        events_used.add(rec.event_id)
        required = tuple(sorted((l.account, canonical_decimal(l.amount)) for l in rec.legs))
        clean = {l.account: l.amount for l in rec.legs}
        evidence = tuple(o.record for o in statement.observations if rec.event_id in o.node_ids)
        if not evidence:
            raise DerivationError(f"{m.mutation_id}: no public evidence row for {rec.id}; the repair is not inferable")
        item_date = bundle.effective_date(rec)
        shape_twins = [ids for k, ids in expected_keys.items() if k[0] == item_date and k[3] == required and ids != [rec.id]]
        if len(expected_keys.get(full_key(rec), [])) != 1 or shape_twins:
            raise DerivationError(f"{m.mutation_id}: the recognition's occurrence key is not unique in the period; unsupported topology")
        if isinstance(m, OmitRecognition):
            if not any(a.node_id == rec.id and a.reason is Reason.PLANTED_MUTATION for a in ledger_view.absences):
                raise DerivationError(f"{m.mutation_id}: the projector did not omit {rec.id}")
            # Contract change B: the repair predicate carries the BANK's date.
            # Nothing public reveals the recognition date of an entry the books
            # do not carry, and `## Dates` tells the agent to post such an entry
            # on the date the statement shows; so the predicate, the expected
            # ledger and the golden deliverable all use that date, and it must
            # be exactly one statement row's date.
            rows = sorted({o.record[:10] for o in statement.observations if rec.event_id in o.node_ids})
            if len(rows) != 1:
                raise DerivationError(f"{m.mutation_id}: {len(rows)} statement dates evidence {rec.id}; the repair "
                                      f"date is not decidable from the public files")
            if rows[0] != item_date:
                raise DerivationError(f"{m.mutation_id}: the expected ledger dates {rec.id} {item_date} and the "
                                      f"statement shows {rows[0]}")
            residual = tuple((a, v) for a, v in clean.items() if v != 0)
            planted.append(PlantedSpec(m.mutation_id, rec.id, item_date, required, (rec.payee,), rec.narration, evidence,
                                       m.identifiability_claim, kind="omit", residual=residual))
        elif isinstance(m, AlterRecognition):
            wrong = derive_mutant(tuple((l.account, l.amount) for l in rec.legs), m.strategy, m.parameter)
            replaces = tuple(sorted((a, canonical_decimal(v)) for a, v in wrong))
            if not any(o.node_ids[0] == f"mut:{m.mutation_id}" for o in ledger_view.observations):
                raise DerivationError(f"{m.mutation_id}: the projector did not emit the altered entry")
            if any(k[0] == rec.date and k[3] == replaces for k in expected_keys):
                raise DerivationError(f"{m.mutation_id}: the wrong shape collides with a legitimate same-date entry")
            observed = {a: v for a, v in wrong}
            residual = tuple((a, clean[a] - observed.get(a, Decimal("0"))) for a in clean if clean[a] - observed.get(a, Decimal("0")) != 0)
            planted.append(PlantedSpec(m.mutation_id, rec.id, rec.date, required, (rec.payee,), rec.narration, evidence,
                                       m.identifiability_claim, kind="alter", replaces=replaces, residual=residual))
        elif isinstance(m, DuplicateRecognition):
            copies = sum(1 for o in ledger_view.observations if o.node_ids[0] == rec.id and o.record.endswith(rec.legs[0].account))
            if copies != 2:
                raise DerivationError(f"{m.mutation_id}: the projector emitted {copies} copies, not two")
            residual = tuple((a, -v) for a, v in clean.items() if v != 0)      # clean (one copy) minus observed (two)
            planted.append(PlantedSpec(m.mutation_id, rec.id, rec.date, required, (rec.payee,), rec.narration, evidence,
                                       m.identifiability_claim, kind="duplicate", expected_count=1, residual=residual))
        else:
            raise DerivationError(f"unknown mutation kind {type(m).__name__}")
    keys = [(p.date, p.required) for p in planted] + [(p.date, p.replaces) for p in planted if p.replaces]
    if len(set(keys)) != len(keys):
        raise DerivationError("two planted items share a repair predicate")
    chart = [a.name for a in sorted(world.accounts, key=lambda a: a.code)]
    # Targets are the RESIDUAL SUPPORT: accounts whose balance the planted
    # discrepancies actually move — not every account a recognition touches.
    support = {a for p in planted for a, _ in p.residual}
    scored = tuple(a for a in chart if a in support)
    # No unresolved subset may cancel on the targets: for every non-empty
    # subset of items, the summed residual must move at least one target.
    for n in range(1, len(planted) + 1):
        for subset in combinations(planted, n):
            total: dict = {}
            for p in subset:
                for a, v in p.residual:
                    total[a] = total.get(a, Decimal("0")) + v
            if all(total.get(a, Decimal("0")) == 0 for a in scored):
                raise DerivationError("planted residuals cancel on every target for the subset "
                                      + ", ".join(p.id for p in subset) + "; unsupported topology")

    traps = []
    for a in statement.absences:
        if a.reason is Reason.NOT_YET_SETTLED:
            mov = next(mv for mv in bundle.movements if mv.id == a.node_id)
            rec = next(r for r in bundle.recognitions if r.event_id == mov.event_id)
            number = ""
            settlement = getattr(world.event(mov.event_id), "settlement", None)
            if settlement is not None and settlement.cheque_id is not None:
                number = world.document(settlement.cheque_id).number
            traps.append(TrapSpec(f"outstanding_check_{number}" if number else f"outstanding_{mov.id.split(':', 1)[1]}",
                                  rec.id, mov.id, rec.date, mov.cleared_on, mov.amount, rec.narration))
    closing = Decimal(statement.text.splitlines()[-1].split(",")[-1])
    inputs = ContractInputs(
        task_id=task.id, task_type=task.type, prompt=task.prompt, period=task.period,
        world_id=world.id, currency=world.currency,
        scored_accounts=scored, expected_balances=bundle.expected_balances, allowed_accounts=tuple(chart),
        planted=tuple(planted), traps=tuple(traps),
        original_text=bundle.view(LEDGER_VIEW).text, golden_text=expected_text, statement_closing=closing,
        graph_digest=bundle.graph_digest, mutation_plan_digest=bundle.mutation_plan_digest,
        view_digests=bundle.view_digests(),
        public_files=tuple(sorted(bundle.public_files().items())),
        _mint=_DERIVED_TOKEN,
    )
    return bundle, inputs


def _archived_literal_inputs(**fields) -> ContractInputs:
    """The archived compatibility mint. Consumed only by
    `candidate.compat`, which production never imports (asserted by
    `test_entrypoints`); exists so the contract audits can be fed inputs the
    projector would refuse to derive."""
    return ContractInputs(**fields, _mint=_DERIVED_TOKEN)
