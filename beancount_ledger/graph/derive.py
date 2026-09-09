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

from .policy import SHORT_PAY_TOLERANCE, credit_note_amounts, is_cash_application_world
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
from .schema import AppliedReceipt, CreditNote, CustomerReceipt, DocumentKind, Sale, World

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


APPLICATION_TRUTH_SCHEMA = "piv.application-truth/1"


@dataclass(frozen=True)
class ApplicationInputs:
    """The TRUTH register of the cash-application family, folded from the
    authored `AppliedReceipt` lines and `CreditNote`s through the policy's
    rules — the register `application/1` scores against. Minted beside
    `ContractInputs` by `derive_contract` for a family world and absent
    otherwise, so a legacy task's contract view does not change.

    Everything here is a fold of authored facts under the published policy;
    nothing is typed. `application_key()` is the truth side of gate (m): the
    same order-free tuple `graph.cash_application.application_key` builds
    from the PUBLIC fold, implemented here independently (the `planted_key`
    / `repair_key` pattern) so a common-mode fault in either projection
    shows up as a mismatch rather than hiding in both.
    """

    receivables_account: str
    write_off_account: str
    tolerance: Decimal
    opening_ar: Decimal
    closing_ar: Decimal
    opening_register: tuple      # ((invoice_id, customer, invoice_date, due_date, face_value, open_balance), ...)
    invoices: tuple              # ((invoice_id, customer, invoice_date, period_basis, source), ...)
    receipts: tuple              # ((receipt_id, date, customer, amount, applied, written_off, unapplied,
                                 #   remittance_id, event_id, recognition_id), ...) in fold order
    credit_notes: tuple          # ((credit_note_id, date, customer, gross, applied, unapplied, event_id), ...)
    register: tuple              # ((invoice_id, customer, period_basis, applied_total, credited, written_off,
                                 #   remaining), ...) by invoice_id

    def application_key(self) -> tuple:
        receipts = tuple(sorted((r[0], tuple(sorted(r[4])), tuple(sorted(r[5])), r[6]) for r in self.receipts))
        credits = tuple(sorted((c[0], tuple(sorted(c[4])), c[5]) for c in self.credit_notes))
        rows = tuple(sorted(self.register))
        return (("receipts", receipts), ("credit_notes", credits), ("register", rows))

    def receipt(self, receipt_id: str) -> tuple:
        return next(r for r in self.receipts if r[0] == receipt_id)

    def row(self, invoice_id: str) -> tuple:
        return next(r for r in self.register if r[0] == invoice_id)

    def view(self) -> dict:
        """The normative declared data the task contract digest binds for
        the family: every quantity `application/1` reads."""
        def pairs(items):
            return [[invoice_id, amount] for invoice_id, amount in items]
        return {
            "schema": APPLICATION_TRUTH_SCHEMA,
            "receivables_account": self.receivables_account, "write_off_account": self.write_off_account,
            "tolerance": self.tolerance, "opening_ar": self.opening_ar, "closing_ar": self.closing_ar,
            "opening_register": [list(r) for r in self.opening_register],
            "invoices": [list(r) for r in self.invoices],
            "receipts": [{"receipt_id": r[0], "date": r[1], "customer": r[2], "amount": r[3],
                          "applied": pairs(r[4]), "written_off": pairs(r[5]), "unapplied_amount": r[6],
                          "remittance_id": r[7]} for r in self.receipts],
            "credit_notes": [{"credit_note_id": c[0], "date": c[1], "customer": c[2], "gross": c[3],
                              "applied": pairs(c[4]), "unapplied_amount": c[5]} for c in self.credit_notes],
            "closing_open_items": [{"invoice_id": w[0], "customer": w[1], "period_basis": w[2],
                                    "applied_total": w[3], "credited": w[4], "written_off": w[5],
                                    "remaining": w[6]} for w in self.register],
        }


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
    application: object = None    # ApplicationInputs for the cash-application family; None otherwise

    def __post_init__(self):
        if self._mint is not _DERIVED_TOKEN:
            raise TypeError("ContractInputs are minted by derive_contract() only; literal values are refused")
        object.__setattr__(self, "_mint", None)

    def contract_view(self) -> dict:
        """The normative declared data the task contract digest binds."""
        view = {
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
        # Present only for the family: a legacy task's view — and therefore
        # its pinned task-contract digest — does not move.
        if self.application is not None:
            view["application"] = self.application.view()
        return view

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


# --------------------------------------------------------------------------
# the truth register of the cash-application family
# --------------------------------------------------------------------------

_ZERO = Decimal("0.00")


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _terms_days(terms) -> int:
    import re
    match = re.search(r"net\s+(\d+)", terms or "", re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _due(issued: str, terms) -> str:
    from datetime import date, timedelta
    return (date.fromisoformat(issued) + timedelta(days=_terms_days(terms))).isoformat()


def derive_application(world: World, bundle: Bundle, roles) -> ApplicationInputs:
    """Fold the authored facts into the truth register, independently of the
    projector's helpers and of the public fold. Refuses, as a
    `DerivationError`, every authoring slip the spec's U-table puts on the
    truth side: a line on a closed, foreign, unknown or not-yet-raised
    invoice, a line above the open balance, a settled line whose cash and
    deduction do not close the invoice, a deduction without a settlement, an
    advice whose lines exceed its payment; and the two ties — the register
    entering the period to the opening entry (gate (l), U7) and the register
    leaving it to the expected ledger's receivables (U8)."""
    period = bundle.period
    receivables = roles.receivables
    tolerance = SHORT_PAY_TOLERANCE

    def posting_date(e) -> str:
        return e.settlement.cleared_on if isinstance(e, AppliedReceipt) else e.date

    # the balance each sales invoice carries into the period ---------------
    prior: dict = {}
    for e in world.events:
        if posting_date(e) >= period.start:
            continue
        if isinstance(e, CustomerReceipt):
            prior[e.invoice_id] = prior.get(e.invoice_id, _ZERO) + e.amount
        elif isinstance(e, AppliedReceipt):
            claimed: dict = {}
            for line in e.lines:
                prior[line.invoice_id] = prior.get(line.invoice_id, _ZERO) + line.amount
                settles, deduction = claimed.get(line.invoice_id, (False, _ZERO))
                claimed[line.invoice_id] = (settles or line.settles, deduction + line.deduction)
            for invoice_id, (settles, deduction) in claimed.items():
                if settles and _ZERO < deduction <= tolerance:
                    prior[invoice_id] = prior.get(invoice_id, _ZERO) + deduction
        elif isinstance(e, CreditNote):
            prior[e.invoice_id] = prior.get(e.invoice_id, _ZERO) + credit_note_amounts(e)[1]

    invoices: dict = {}          # number -> (customer, invoice_date, basis, doc id)
    opening_register = []
    for d in sorted(world.documents, key=lambda d: (d.issued, d.number)):
        if d.kind is not DocumentKind.SALES_INVOICE or d.issued >= period.start:
            continue
        open_balance = _q2(d.gross - prior.get(d.id, _ZERO))
        if open_balance < 0:
            raise DerivationError(f"{d.number}: applications before the period exceed its face value")
        if open_balance == 0:
            continue
        party = world.party(d.party_id)
        opening_register.append((d.number, party.name, d.issued, _due(d.issued, party.terms), _q2(d.gross),
                                 open_balance))
        invoices[d.number] = (party.name, d.issued, open_balance, d.id)
    opening_ar = sum((row[5] for row in opening_register), _ZERO)
    carried = dict(world.opening.carried).get(receivables, _ZERO)
    if opening_ar != carried:
        raise DerivationError(f"REFUSE_REGISTER_DOES_NOT_TIE: the register entering the period totals "
                              f"{opening_ar}, the opening entry's {receivables} {carried}")
    for e in sorted((e for e in world.events if isinstance(e, Sale) and period.contains(e.date)),
                    key=lambda e: (e.date, e.id)):
        d = world.document(e.invoice_id)
        if d.number in invoices:
            raise DerivationError(f"REFUSE_SALE_WITHOUT_UNIQUE_NUMBER: {d.number} is raised in the period and "
                                  f"already in the register")
        invoices[d.number] = (world.party(e.party_id).name, e.date, _q2(d.gross), d.id)
    by_doc = {doc_id: number for number, (_, _, _, doc_id) in invoices.items()}

    remaining = {n: basis for n, (_, _, basis, _) in invoices.items()}
    applied = {n: _ZERO for n in invoices}
    credited = {n: _ZERO for n in invoices}
    written_off = {n: _ZERO for n in invoices}

    def open_by_date(customer: str, date: str, exclude=()) -> list:
        return sorted((n for n, (c, invoice_date, _, _) in invoices.items()
                       if c == customer and invoice_date <= date and remaining[n] > 0 and n not in exclude),
                      key=lambda n: (invoices[n][1], n))

    # the period's events, in application order ------------------------------
    movements = {m.event_id: m for m in bundle.movements}
    events = []
    for e in world.events:
        if isinstance(e, CustomerReceipt) and period.contains(e.date):
            raise DerivationError(f"{e.id}: a cash-application world applies every in-period receipt through "
                                  f"an AppliedReceipt; a single-invoice CustomerReceipt has no register row")
        if isinstance(e, CreditNote) and period.contains(e.date):
            events.append((e.date, 0, e.number, e))
        if isinstance(e, AppliedReceipt) and period.contains(e.settlement.cleared_on):
            events.append((e.settlement.cleared_on, 1, e.id, e))      # statement order: (cleared_on, event id)
    events.sort(key=lambda t: t[:3])

    receipts, credits = [], []
    for date, kind, _, e in events:
        customer = world.party(e.party_id).name
        if kind == 0:
            named = by_doc.get(e.invoice_id)
            if named is None or invoices[named][0] != customer:
                raise DerivationError(f"REFUSE_FOREIGN_OR_UNKNOWN_INVOICE: {e.number} names {e.invoice_id}")
            if invoices[named][1] > date:
                raise DerivationError(f"REFUSE_FOREIGN_OR_UNKNOWN_INVOICE: {e.number} is dated before {named}")
            tax, gross = credit_note_amounts(e)
            left = gross
            lines = []
            take = min(left, remaining[named])       # a paid invoice takes none: all of it routes as excess
            if take > 0:
                lines.append((named, take))
                remaining[named] -= take
                credited[named] += take
                left -= take
            for other in open_by_date(customer, date, exclude=(named,)):
                if left <= 0:
                    break
                take = min(left, remaining[other])
                lines.append((other, take))
                remaining[other] -= take
                credited[other] += take
                left -= take
            credits.append((e.number, date, customer, gross, tuple(lines), _q2(left), e.id))
            continue
        movement = movements[e.id]
        receipt_id = f"{movement.cleared_on}:{movement.reference}"
        groups: dict = {}
        for line in e.lines:
            groups.setdefault(line.invoice_id, []).append(line)
        lines, offs = [], []
        paid_total = _ZERO
        for doc_id, group in groups.items():
            number = by_doc.get(doc_id)
            label = f"{e.id} line on {doc_id}"
            if number is None or invoices[number][0] != customer:
                raise DerivationError(f"REFUSE_FOREIGN_OR_UNKNOWN_INVOICE: {label} names an invoice that is not "
                                      f"{customer}'s or not in the register")
            if invoices[number][1] > date:
                raise DerivationError(f"REFUSE_FOREIGN_OR_UNKNOWN_INVOICE: {label}: {number} is raised after the "
                                      f"application date {date}")
            paid = sum((l.amount for l in group), _ZERO)
            deduction = sum((l.deduction for l in group), _ZERO)
            settles = any(l.settles for l in group)
            if any(l.deduction > 0 and not l.settles for l in group):
                raise DerivationError(f"REFUSE_LINE_CONTRADICTS_REGISTER: {label} claims a deduction without settling")
            open_ = remaining[number]
            if open_ == 0 and (paid > 0 or deduction > 0):
                raise DerivationError(f"REFUSE_FOREIGN_OR_UNKNOWN_INVOICE: {label}: {number} is already closed")
            if paid > open_:
                raise DerivationError(f"REFUSE_LINE_CONTRADICTS_REGISTER: {label} pays {paid} against {open_}")
            if settles and paid + deduction != open_:
                raise DerivationError(f"REFUSE_LINE_CONTRADICTS_REGISTER: {label} settles with {paid} + {deduction} "
                                      f"against an open balance of {open_}")
            paid_total += paid
            if paid == 0 and deduction == 0 and not settles:
                continue                              # an informational statement of dispute
            if paid > 0:
                lines.append((number, paid))
                remaining[number] -= paid
                applied[number] += paid
            if settles and _ZERO < deduction <= tolerance:
                offs.append((number, deduction))
                remaining[number] -= deduction
                written_off[number] += deduction
        if paid_total > e.amount:
            raise DerivationError(f"REFUSE_LINE_CONTRADICTS_REGISTER: {e.id}'s lines total {paid_total}, above "
                                  f"its payment of {e.amount}")
        receipts.append((receipt_id, date, customer, _q2(e.amount), tuple(lines), tuple(offs),
                         _q2(e.amount - paid_total), e.remittance_id, e.id, f"rec:{e.id.split(':', 1)[1]}"))

    register = tuple((n, invoices[n][0], invoices[n][2], _q2(applied[n]), _q2(credited[n]), _q2(written_off[n]),
                      _q2(remaining[n])) for n in sorted(invoices))
    unapplied = sum((r[6] for r in receipts), _ZERO) + sum((c[5] for c in credits), _ZERO)
    closing_ar = _q2(sum((row[6] for row in register), _ZERO) - unapplied)
    expected_ar = dict(bundle.expected_balances).get(receivables, _ZERO)
    if closing_ar != expected_ar:
        raise DerivationError(f"the truth register closes at {closing_ar}, the expected ledger's {receivables} at "
                              f"{expected_ar}; a projector or derivation defect (U8)")
    # The policy's write-off recognitions must be exactly the register's
    # write-offs: one per receipt that writes something off, on the receipt's
    # date, payee the customer, legs (write-off account +d, receivables -d)
    # with d the receipt's written-off total.
    for r in receipts:
        rec_id = r[9] + "-writeoff"
        matching = [rec for rec in bundle.recognitions if rec.id == rec_id]
        total = sum((amount for _, amount in r[5]), _ZERO)
        if not r[5]:
            if matching:
                raise DerivationError(f"{rec_id}: the policy writes off {matching[0].net_on(receivables)} and the "
                                      f"register nothing")
            continue
        if not matching:
            raise DerivationError(f"{rec_id}: the register writes off {total} and the policy has no recognition")
        rec = matching[0]
        legs = tuple(sorted((l.account, _q2(l.amount)) for l in rec.legs))
        want = tuple(sorted(((roles.small_balance_write_offs, total), (receivables, -total))))
        if rec.date != r[1] or rec.payee != r[2] or legs != want:
            raise DerivationError(f"{rec_id}: the policy's write-off ({rec.date}, {rec.payee}, {legs}) is not the "
                                  f"register's ({r[1]}, {r[2]}, {want})")
    return ApplicationInputs(
        receivables_account=receivables, write_off_account=roles.small_balance_write_offs, tolerance=tolerance,
        opening_ar=_q2(opening_ar), closing_ar=closing_ar, opening_register=tuple(opening_register),
        invoices=tuple((n, c, d, basis, "register" if n in {row[0] for row in opening_register} else "sale")
                       for n, (c, d, basis, _) in sorted(invoices.items())),
        receipts=tuple(receipts), credit_notes=tuple(credits), register=register)


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
    application = None
    if is_cash_application_world(world):
        from .policy import Roles
        application = derive_application(world, bundle, Roles(**dict(world.roles)))
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
        application=application,
    )
    return bundle, inputs


def _archived_literal_inputs(**fields) -> ContractInputs:
    """The archived compatibility mint. Consumed only by
    `candidate.compat`, which production never imports (asserted by
    `test_entrypoints`); exists so the contract audits can be fed inputs the
    projector would refuse to derive."""
    return ContractInputs(**fields, _mint=_DERIVED_TOKEN)
