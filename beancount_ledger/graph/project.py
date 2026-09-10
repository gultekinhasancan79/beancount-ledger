"""Projections: every document, public or private, derived from the graph
with a typed reason for every row that is NOT there.

The projector walks every consequence (recognition, bank movement) against
every view that could show it and classifies each pair exhaustively:

    PRESENT                      emitted, once, with private provenance
    OUTSIDE_PERIOD               before or after the view's period
    NOT_YET_SETTLED              the bank had not seen it by the cut-off
    NOT_APPLICABLE_TO_VIEW       a recognition in a bank view, or vice versa
    REDACTED_BY_PUBLIC_POLICY    known to the books, not published (invoices)
    PLANTED_MUTATION(id)         removed from the opening ledger for the task

An unclassified pair is a projection failure, so the view-consistency
witness can tell the outstanding cheque (NOT_YET_SETTLED on the statement,
PRESENT in the ledger) from the missing receipt (PRESENT on the statement,
PLANTED_MUTATION in the ledger) from a redacted invoice, although all three
are "missing somewhere".

Public views omit every private id; the bundle keeps them for audit.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date as _date, timedelta
from decimal import Decimal
from enum import Enum

from ..candidate.canonical import canonical_bytes, domain_digest
from .policy import (
    ACCOUNTING_POLICY_VERSION,
    POLICY_SECTIONS,
    ROLES,
    AccountingRecognition,
    BankMovement,
    Roles,
    credit_note_amounts,
    is_cash_application_world,
    movement_of,
    opening_recognition,
    recognitions_of,
    required_sections,
    write_offs_of,
)
from .schema import (
    GRAPH_SCHEMA_VERSION,
    AppliedReceipt,
    CreditNote,
    CustomerReceipt,
    DocumentKind,
    PartyRole,
    Purchase,
    Rail,
    Sale,
    VendorPayment,
    World,
    check_world,
    world_canonical,
)

PROJECTION_VERSION = 1
MUTATION_VERSION = 1

GRAPH_DOMAIN = b"piv:graph:v1\0"
VIEW_DOMAIN = b"piv:view:v1\0"
MUTATION_PLAN_DOMAIN = b"piv:mutation-plan:v1\0"

LEDGER_VIEW = "ledger.beancount"
STATEMENT_VIEW = "bank_statement.csv"
ARCHIVE_VIEW = "archive_prior_period.csv"
ACCOUNTS_VIEW = "accounts.csv"
CUSTOMERS_VIEW = "customers.csv"
VENDORS_VIEW = "vendors.csv"
POLICY_VIEW = "policy.md"
MANIFEST_VIEW = "manifest.md"
EXPECTED_LEDGER_VIEW = "expected_ledger"          # private: the books as they should be
EXPECTED_BALANCES_VIEW = "expected_balances"      # private

PUBLIC_VIEWS = (LEDGER_VIEW, STATEMENT_VIEW, ACCOUNTS_VIEW, CUSTOMERS_VIEW, VENDORS_VIEW, POLICY_VIEW,
                ARCHIVE_VIEW, MANIFEST_VIEW)
CONSEQUENCE_VIEWS = (LEDGER_VIEW, EXPECTED_LEDGER_VIEW, STATEMENT_VIEW, ARCHIVE_VIEW)

# The cash-application family's evidence pack: three master-data-style views
# (observations, no absences — they are not consequence views) emitted ONLY
# for a world the family is inferred from. A legacy world keeps exactly the
# eight above, byte for byte.
OPEN_ITEMS_VIEW = "open_items.csv"
REMITTANCE_VIEW = "remittance_advice.csv"
CREDIT_NOTES_VIEW = "credit_notes.csv"
FAMILY_VIEWS = (OPEN_ITEMS_VIEW, REMITTANCE_VIEW, CREDIT_NOTES_VIEW)
OPEN_ITEMS_COLUMNS = ("invoice_id", "customer", "invoice_date", "due_date", "original_amount", "open_balance")
REMITTANCE_COLUMNS = ("remittance_id", "customer", "remittance_date", "payment_method", "payment_reference",
                      "payment_amount", "invoice_id", "amount_paid", "settles_invoice", "deduction_amount", "note")
CREDIT_NOTE_COLUMNS = ("credit_note_id", "date", "customer", "invoice_id", "net_amount", "tax_amount",
                       "gross_amount", "reason")

# Fixed layout of the rendered ledger. Contractual: the byte comparison
# against the shipped world holds these constants to the file.
OPEN_ACCOUNT_WIDTH = 30
POSTING_ACCOUNT_WIDTH = 40
POSTING_AMOUNT_WIDTH = 9
BANNER = "; " + "-" * 75


def _padded(name: str, width: int) -> int:
    """The column an account name is padded to: the fixed width, or one more
    than the name when the name has reached it. `f"{name:<30}USD"` prints no
    separator at all for a 30-character name, and Beancount then reads
    `...-LtdUSD` as the account — a silently wrong chart, not an error. Every
    account the shipped worlds carry is shorter than both widths, so for them
    this is the fixed width and no shipped byte moves."""
    return max(width, len(name) + 1)


class ProjectionError(Exception):
    """A world the projector could not render exhaustively. Ours."""


class Reason(Enum):
    PRESENT = "present"
    OUTSIDE_PERIOD = "outside_period"
    NOT_YET_SETTLED = "not_yet_settled"
    NOT_APPLICABLE_TO_VIEW = "not_applicable_to_view"
    REDACTED_BY_PUBLIC_POLICY = "redacted_by_public_policy"
    PLANTED_MUTATION = "planted_mutation"


@dataclass(frozen=True)
class Period:
    start: str
    end: str
    label: str

    def contains(self, date: str) -> bool:
        return self.start <= date <= self.end


@dataclass(frozen=True)
class OmitRecognition:
    """The one mutation kind: remove a derived recognition from the opening
    ledger. It names the recognition and nothing else — no date, no
    postings, no payee, no delta; all of those are derived from the
    recognition it names."""

    mutation_id: str
    recognition_id: str
    identifiability_claim: str


ALTER_STRATEGIES = ("transpose_digits", "drop_digit", "decimal_shift")


@dataclass(frozen=True)
class AlterRecognition:
    """The books carry the entry with a WRONG amount produced by a typed,
    plausible bookkeeping error — never an authored vector:

        transpose_digits(i)   swap the digits at positions i and i+1 of the
                              absolute amount in cents
        drop_digit(i)         delete the digit at position i
        decimal_shift(k)      multiply by 10**k, k in {-1, +1}

    `derive_mutant` applies the strategy to a two-sided settlement
    recognition (one bank leg, one counter leg), keeps the schema, currency
    and signs, and refuses a result that is zero, equal to the truth, out
    of realistic bounds, or fewer digits than the strategy needs."""

    mutation_id: str
    recognition_id: str
    strategy: str
    parameter: int
    identifiability_claim: str


def derive_mutant(true_legs: tuple, strategy: str, parameter: int) -> tuple:
    """The wrong legs for an alteration, from the truth and a typed error.
    Returns ((account, Decimal), ...) in the truth's leg order."""
    if strategy not in ALTER_STRATEGIES:
        raise ProjectionError(f"unknown alter strategy {strategy!r}")
    if len(true_legs) != 2:
        raise ProjectionError("an alteration applies to a two-sided recognition only")
    (a1, v1), (a2, v2) = true_legs
    if v1 + v2 != 0 or v1 == 0:
        raise ProjectionError("an alteration applies to a balanced two-sided recognition only")
    cents = int((abs(v1) * 100).to_integral_value())
    digits = list(str(cents))
    if strategy == "transpose_digits":
        if not 0 <= parameter < len(digits) - 1:
            raise ProjectionError("transpose position out of range")
        digits[parameter], digits[parameter + 1] = digits[parameter + 1], digits[parameter]
        wrong = int("".join(digits))
    elif strategy == "drop_digit":
        if len(digits) < 3 or not 0 <= parameter < len(digits):
            raise ProjectionError("drop position out of range")
        del digits[parameter]
        wrong = int("".join(digits)) if digits else 0
    else:
        if parameter not in (-1, 1):
            raise ProjectionError("decimal shift is one place either way")
        wrong = cents * 10 if parameter == 1 else cents // 10
    if wrong == 0 or wrong == cents:
        raise ProjectionError("the strategy produced no error or a zero amount")
    if not (Decimal("0.01") <= Decimal(wrong) / 100 <= Decimal("10000000")):
        raise ProjectionError("the mutant amount is outside realistic bounds")
    amount = Decimal(wrong) / 100
    sign1 = 1 if v1 > 0 else -1
    return ((a1, sign1 * amount), (a2, -sign1 * amount))


@dataclass(frozen=True)
class DuplicateRecognition:
    """The books carry the entry twice. The repair is to remove one."""

    mutation_id: str
    recognition_id: str
    identifiability_claim: str


MUTATION_KINDS = (OmitRecognition, AlterRecognition, DuplicateRecognition)


@dataclass(frozen=True)
class MutationPlan:
    mutations: tuple
    version: int = MUTATION_VERSION


def _mutation_canonical(m) -> dict:
    out = {"__type__": type(m).__name__, "mutation_id": m.mutation_id, "recognition_id": m.recognition_id,
           "identifiability_claim": m.identifiability_claim}
    if isinstance(m, AlterRecognition):
        out["strategy"], out["parameter"] = m.strategy, m.parameter
    return out


# Recognitions an alteration or duplicate may target in M1: settlement-derived,
# two-sided, with a direct bank row. Sale, COGS, purchase and the
# opening entry are not mutable this way — their truth is only indirectly
# evidenced.
MUTABLE_RULES = ("customer_receipt", "vendor_payment", "expense_payment", "prepayment", "bank_fee")


@dataclass(frozen=True)
class Observation:
    """One emitted row and where it came from."""

    view: str
    record: str
    node_ids: tuple
    value: Decimal | None = None


@dataclass(frozen=True)
class Absence:
    view: str
    node_id: str
    reason: Reason
    mutation_id: str | None = None


@dataclass(frozen=True)
class View:
    name: str
    text: str
    observations: tuple
    absences: tuple
    digest: str
    public: bool

    def subjects(self) -> set:
        """The nodes this view EMITS a row for (`node_ids[0]` of each row)."""
        return {o.node_ids[0] for o in self.observations if o.node_ids}

    def sources(self) -> set:
        """Every node that contributed to any row — subjects plus the
        provenance behind derived rows (the statement's opening balance
        names the prior movements it folds)."""
        return {i for o in self.observations for i in o.node_ids}


@dataclass(frozen=True)
class Bundle:
    world_id: str
    title: str
    currency: str
    period: Period
    prior: Period
    plan: MutationPlan
    graph_digest: str
    mutation_plan_digest: str
    recognitions: tuple           # every recognition, opening included
    movements: tuple
    opening_bank_balance: Decimal
    views: tuple
    expected_balances: tuple      # ((account, Decimal), ...) every chart account, chart order
    restated: tuple = ()          # ((recognition id, bank date), ...): omitted items, dated by the bank

    def view(self, name: str) -> View:
        return next(v for v in self.views if v.name == name)

    def effective_date(self, rec) -> str:
        """The date the CORRECT books carry this recognition.

        Its own transaction date, except for a recognition the opening ledger
        does not carry at all: nothing public reveals that date, and the
        policy's `## Dates` section says such an entry is posted on the date
        the bank shows, so the expected ledger, the repair predicate and the
        golden deliverable all use the bank's date for it (contract change B).
        """
        return dict(self.restated).get(rec.id, rec.date)

    def recognition(self, recognition_id: str) -> AccountingRecognition:
        return next(r for r in self.recognitions if r.id == recognition_id)

    def public_files(self) -> dict:
        return {v.name: v.text.encode("utf-8") for v in self.views if v.public}

    def view_digests(self) -> tuple:
        return tuple((v.name, v.digest) for v in sorted(self.views, key=lambda v: v.name))


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def prior_period(period: Period) -> Period:
    year, month = int(period.start[:4]), int(period.start[5:7])
    year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    last = calendar.monthrange(year, month)[1]
    return Period(f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}",
                  f"{calendar.month_name[month]} {year}")


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _view(name: str, text: str, observations, absences, public: bool) -> View:
    digest = domain_digest(VIEW_DOMAIN, canonical_bytes({
        "name": name, "text": text, "projection_version": PROJECTION_VERSION,
        "accounting_policy_version": ACCOUNTING_POLICY_VERSION}))
    return View(name, text, tuple(observations), tuple(absences), digest, public)


def _roles(world: World) -> Roles:
    return Roles(**dict(world.roles))


def _terms_days(terms) -> int:
    """`net 30` -> 30; `due on receipt` (or no terms) -> 0."""
    match = re.search(r"net\s+(\d+)", terms or "", re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _posting_date(event) -> str:
    """The date the books carry an event's recognition: the bank's date for
    an applied receipt (the family posts on the date the bank shows), the
    event's own date otherwise."""
    return event.settlement.cleared_on if isinstance(event, AppliedReceipt) else event.date


def invoice_applications(world: World, invoice_id: str, *, before: str | None = None) -> Decimal:
    """Everything applied against one sales invoice by the authored facts —
    single-invoice receipts, applied-receipt lines, the policy's write-offs
    on them and credit notes naming it — posted before `before` (every date
    when None). A credit note counts here for the amount it names; what its
    excess does is the register's business, not the invoice's."""
    total = Decimal("0")
    for e in world.events:
        if before is not None and _posting_date(e) >= before:
            continue
        if isinstance(e, CustomerReceipt) and e.invoice_id == invoice_id:
            total += e.amount
        elif isinstance(e, AppliedReceipt):
            total += sum((line.amount for line in e.lines if line.invoice_id == invoice_id), Decimal("0"))
            total += sum((amount for inv, amount in write_offs_of(e) if inv == invoice_id), Decimal("0"))
        elif isinstance(e, CreditNote) and e.invoice_id == invoice_id:
            total += credit_note_amounts(e)[1]
    return total


def open_items(world: World, period: Period) -> tuple:
    """The open sales-invoice register entering the period: every sales
    invoice issued before it whose face value exceeds what was applied
    against it before it, as `(document, due_date, open_balance)` in
    `(issued, number)` order. `open_balance`, never the face value, is the
    balance the period starts from."""
    rows = []
    for d in sorted(world.documents, key=lambda d: (d.issued, d.number)):
        if d.kind is not DocumentKind.SALES_INVOICE or d.issued >= period.start:
            continue
        open_balance = d.gross - invoice_applications(world, d.id, before=period.start)
        if open_balance > 0:
            issued = _date.fromisoformat(d.issued)
            due = issued + timedelta(days=_terms_days(world.party(d.party_id).terms))
            rows.append((d, due.isoformat(), open_balance))
    return tuple(rows)


# --------------------------------------------------------------------------
# the projector
# --------------------------------------------------------------------------

def project(world: World, period: Period, plan: MutationPlan) -> Bundle:
    problems = check_world(world)
    for role, section in required_sections(world).items():
        if section not in world.policy_text:
            problems.append(f"policy rule {role!r} cites {section!r}, which the policy text lacks")
    if problems:
        raise ProjectionError("; ".join(problems))
    roles = _roles(world)
    prior = prior_period(period)
    if world.bank_opening.as_of != prior.start:
        raise ProjectionError(f"the bank opening is dated {world.bank_opening.as_of}; the projector models one prior "
                              f"period starting {prior.start}")
    if world.opening.as_of != period.start:
        raise ProjectionError("the opening position is not dated at the period start")

    movements = tuple(m for m in (movement_of(world, e) for e in world.events) if m is not None)
    carried = sum((m.amount for m in movements if world.bank_opening.as_of <= m.cleared_on < period.start), Decimal("0"))
    opening_bank = world.bank_opening.balance + carried
    opening = opening_recognition(world, roles, opening_bank)
    recognitions = (opening,) + tuple(r for e in world.events for r in recognitions_of(world, roles, e))
    known = {r.id: r for r in recognitions}
    planned: dict = {}
    for m in plan.mutations:
        if not isinstance(m, MUTATION_KINDS):
            raise ProjectionError(f"unknown mutation kind {type(m).__name__}")
        if m.recognition_id not in known:
            raise ProjectionError(f"mutation names unknown recognition {m.recognition_id}")
        if m.recognition_id in planned:
            raise ProjectionError("two mutations name one recognition")
        if known[m.recognition_id].rule == "opening":
            raise ProjectionError("the opening entry cannot be mutated")
        if isinstance(m, (AlterRecognition, DuplicateRecognition)):
            rec = known[m.recognition_id]
            if rec.rule not in MUTABLE_RULES or len(rec.legs) != 2 or rec.event_id not in {mv.event_id for mv in movements}:
                raise ProjectionError(f"{m.mutation_id}: only a two-sided settlement recognition with a bank row "
                                      f"can be altered or duplicated ({rec.rule})")
        if isinstance(m, AlterRecognition):
            true = known[m.recognition_id]
            derive_mutant(tuple((l.account, l.amount) for l in true.legs), m.strategy, m.parameter)
        planned[m.recognition_id] = m
    if len({m.mutation_id for m in plan.mutations}) != len(plan.mutations):
        raise ProjectionError("duplicate mutation id")
    omitted = {rec_id: m.mutation_id for rec_id, m in planned.items() if isinstance(m, OmitRecognition)}
    by_event_movement = {m.event_id: m for m in movements}

    # Contract change B. An entry the opening ledger does not carry at all
    # has no public transaction date: the recognition's own date is hidden
    # with the entry, and only the statement row survives. `## Dates` in the
    # policy the agent reads says such an entry is posted on the date the
    # bank shows, so that is the date the CORRECT books carry — the expected
    # ledger below, the repair predicate the scorer compares against and the
    # golden deliverable all agree on it. An altered or duplicated entry is
    # public and keeps its own date; only an omission is restated.
    restated: dict[str, str] = {}
    for rec_id in omitted:
        rec = known[rec_id]
        rows = [m for m in movements if m.event_id == rec.event_id and period.contains(m.cleared_on)]
        if len(rows) == 1 and rows[0].cleared_on != rec.date:
            restated[rec_id] = rows[0].cleared_on

    def effective(rec: AccountingRecognition, apply_plan: bool) -> str:
        """The date a view prints this recognition on. The public ledger
        never prints an omitted recognition, so the restatement is only ever
        visible in the expected ledger."""
        return rec.date if apply_plan else restated.get(rec.id, rec.date)

    # ledger views -----------------------------------------------------
    def ledger(name: str, public: bool, apply_plan: bool) -> View:
        obs, abs_ = [], []
        lines = [f'option "title" "{world.title}"', f'option "operating_currency" "{world.currency}"', "",
                 "; Chart of accounts"]
        for a in sorted(world.accounts, key=lambda a: a.code):
            lines.append(f"{a.opened} open {a.name:<{_padded(a.name, OPEN_ACCOUNT_WIDTH)}}{world.currency}")
            obs.append(Observation(name, f"open {a.name}", (f"account:{a.name}",)))
        lines += ["", f"; Opening balances as of {period.start}"]
        body: list[str] = []
        for rec in sorted(recognitions, key=lambda r: (effective(r, apply_plan), r.event_id, r.sequence)):
            when = effective(rec, apply_plan)
            mutation = planned.get(rec.id) if apply_plan else None
            if isinstance(mutation, OmitRecognition):
                # Classified BEFORE the period filter, and by the date the
                # CORRECT books carry: a payment made on the last day of the
                # prior month and cleared in this one belongs to this month's
                # books once it is restated onto the bank's date, so the
                # opening ledger is missing it for the planted reason rather
                # than for being out of period.
                #
                # REACHABILITY. The generator cannot draw that case, and the
                # reason is structural rather than lucky: `generate._facts`
                # clamps every prior-period settlement to `q_end` (or clears
                # it on its own day) and issues every task-period event on or
                # after `p_start`, so no generated event has its own date in
                # one period and its bank row in the next. The one settlement
                # that does cross a month boundary is the prepayment cheque,
                # which clears AFTER the cut-off and therefore has no row to
                # be missing from — `_plan` skips it twice over, because
                # `Prepayment` is not in `_OMIT_ID` and because
                # `period.contains(movement.cleared_on)` is false. 270
                # generated worlds produced no crossing at all. The branch is
                # covered by `tests/test_lag.py`'s hand-authored fixture
                # instead, which also asserts that the generator still cannot
                # produce one (the verifier's dead-code report).
                abs_.append(Absence(name, rec.id, Reason.PLANTED_MUTATION, mutation.mutation_id)
                            if period.contains(restated.get(rec.id, rec.date))
                            else Absence(name, rec.id, Reason.OUTSIDE_PERIOD))
                continue
            if rec.rule != "opening" and not period.contains(when):
                abs_.append(Absence(name, rec.id, Reason.OUTSIDE_PERIOD))
                continue
            entry = [f'{when} * "{rec.payee}" "{rec.narration}"']
            if isinstance(mutation, AlterRecognition):
                # The wrong vector, as booked: a MUTANT node with provenance
                # to the recognition, the event and the mutation; the true
                # recognition is absent for the planted reason.
                wrong_legs = derive_mutant(tuple((l.account, l.amount) for l in rec.legs), mutation.strategy, mutation.parameter)
                for account, amount in wrong_legs:
                    entry.append(f"  {account:<{_padded(account, POSTING_ACCOUNT_WIDTH)}}{_money(Decimal(amount)):>{POSTING_AMOUNT_WIDTH}} {world.currency}")
                    obs.append(Observation(name, f"{when} {account}",
                                           (f"mut:{mutation.mutation_id}", rec.id, rec.event_id), Decimal(amount)))
                abs_.append(Absence(name, rec.id, Reason.PLANTED_MUTATION, mutation.mutation_id))
            else:
                for leg in rec.legs:
                    entry.append(f"  {leg.account:<{_padded(leg.account, POSTING_ACCOUNT_WIDTH)}}{_money(leg.amount):>{POSTING_AMOUNT_WIDTH}} {world.currency}")
                    obs.append(Observation(name, f"{when} {leg.account}", (rec.id, rec.event_id), leg.amount))
            if rec.rule == "opening":
                lines += entry + ["", BANNER, f"; {period.label} activity", BANNER]
            else:
                body += [""] + entry
                if isinstance(mutation, DuplicateRecognition):
                    body += [""] + entry                    # the second copy, tagged with the mutation
                    for leg in rec.legs:
                        obs.append(Observation(name, f"{when} {leg.account}",
                                               (rec.id, rec.event_id, f"mut:{mutation.mutation_id}"), leg.amount))
        for m in movements:
            abs_.append(Absence(name, m.id, Reason.NOT_APPLICABLE_TO_VIEW))
        for d in world.documents:
            abs_.append(Absence(name, d.id, Reason.REDACTED_BY_PUBLIC_POLICY))
        return _view(name, "\n".join(lines + body) + "\n", obs, abs_, public)

    # bank views -------------------------------------------------------
    def statement(name: str, span: Period, opening_row: bool) -> View:
        obs, abs_ = [], []
        rows = ["date,description,reference,debit,credit,balance"]
        before = [m for m in movements if world.bank_opening.as_of <= m.cleared_on < span.start]
        running = world.bank_opening.balance + sum((m.amount for m in before), Decimal("0"))
        if opening_row:
            rows.append(f"{span.start},Opening balance carried forward,,,,{_money(running)}")
            obs.append(Observation(name, f"{span.start} opening", ("bank_opening",) + tuple(m.id for m in before), running))
        for m in sorted(movements, key=lambda m: (m.cleared_on, m.event_id)):
            issued = world.event(m.event_id).date
            if span.contains(m.cleared_on):
                running += m.amount
                debit = _money(-m.amount) if m.amount < 0 else ""
                credit = _money(m.amount) if m.amount > 0 else ""
                rows.append(f"{m.cleared_on},{m.description},{m.reference},{debit},{credit},{_money(running)}")
                obs.append(Observation(name, f"{m.cleared_on} {m.description}", (m.id, m.event_id), m.amount))
            elif issued <= span.end < m.cleared_on:
                abs_.append(Absence(name, m.id, Reason.NOT_YET_SETTLED))
            else:
                abs_.append(Absence(name, m.id, Reason.OUTSIDE_PERIOD))
        for rec in recognitions:
            abs_.append(Absence(name, rec.id, Reason.NOT_APPLICABLE_TO_VIEW))
        for d in world.documents:
            abs_.append(Absence(name, d.id, Reason.REDACTED_BY_PUBLIC_POLICY))
        return _view(name, "\n".join(rows) + "\n", obs, abs_, True)

    # master views -----------------------------------------------------
    def accounts() -> View:
        rows = ["account,type,description"]
        obs = []
        for a in sorted(world.accounts, key=lambda a: a.code):
            rows.append(f"{a.name},{a.kind.value},{a.description}")
            obs.append(Observation(ACCOUNTS_VIEW, a.name, (f"account:{a.name}",)))
        return _view(ACCOUNTS_VIEW, "\n".join(rows) + "\n", obs, [], True)

    def parties(name: str, role: PartyRole, header: str) -> View:
        rows = [header]
        obs, abs_ = [], []
        for p in sorted(world.parties, key=lambda p: p.number):
            if p.role is role:
                rows.append(f"{p.name},{p.terms},{p.default_account}")
                obs.append(Observation(name, p.name, (p.id,)))
            else:
                abs_.append(Absence(name, p.id, Reason.NOT_APPLICABLE_TO_VIEW))
        for d in world.documents:
            abs_.append(Absence(name, d.id, Reason.REDACTED_BY_PUBLIC_POLICY))
        return _view(name, "\n".join(rows) + "\n", obs, abs_, True)

    ledger_view = ledger(LEDGER_VIEW, True, True)
    expected_view = ledger(EXPECTED_LEDGER_VIEW, False, False)
    statement_view = statement(STATEMENT_VIEW, period, True)
    archive_view = statement(ARCHIVE_VIEW, prior, False)
    accounts_view = accounts()
    customers_view = parties(CUSTOMERS_VIEW, PartyRole.CUSTOMER, "customer,terms,default_account")
    vendors_view = parties(VENDORS_VIEW, PartyRole.VENDOR, "vendor,terms,default_account")
    policy_view = _view(POLICY_VIEW, world.policy_text, [Observation(POLICY_VIEW, "policy", ("policy_text",))], [], True)

    # the cash-application family's evidence pack ----------------------
    family = is_cash_application_world(world)
    family_views: list = []
    if family:
        rows = [",".join(OPEN_ITEMS_COLUMNS)]
        obs = []
        for d, due, open_balance in open_items(world, period):
            customer = world.party(d.party_id).name
            rows.append(f"{d.number},{customer},{d.issued},{due},{_money(d.gross)},{_money(open_balance)}")
            obs.append(Observation(OPEN_ITEMS_VIEW, d.number, (d.id, d.party_id), open_balance))
        family_views.append(_view(OPEN_ITEMS_VIEW, "\n".join(rows) + "\n", obs, [], True))

        rows = [",".join(REMITTANCE_COLUMNS)]
        obs = []
        adviced = [e for e in world.events if isinstance(e, AppliedReceipt) and e.remittance_id
                   and period.contains(e.settlement.cleared_on)]
        for e in sorted(adviced, key=lambda e: (e.date, e.remittance_id)):
            customer = world.party(e.party_id).name
            if e.settlement.rail is Rail.CHEQUE:
                method, reference = "CHECK", world.document(e.settlement.cheque_id).number
            else:
                method, reference = "ACH", e.bank_reference
            for line in e.lines:
                number = world.document(line.invoice_id).number
                rows.append(f"{e.remittance_id},{customer},{e.date},{method},{reference},{_money(e.amount)},"
                            f"{number},{_money(line.amount)},{'yes' if line.settles else 'no'},"
                            f"{_money(line.deduction)},{line.note}")
                obs.append(Observation(REMITTANCE_VIEW, f"{e.remittance_id} {number}", (e.id, line.invoice_id),
                                       line.amount))
        family_views.append(_view(REMITTANCE_VIEW, "\n".join(rows) + "\n", obs, [], True))

        rows = [",".join(CREDIT_NOTE_COLUMNS)]
        obs = []
        notes = [e for e in world.events if isinstance(e, CreditNote) and period.contains(e.date)]
        for e in sorted(notes, key=lambda e: (e.date, e.number)):
            tax, gross = credit_note_amounts(e)
            rows.append(f"{e.number},{e.date},{world.party(e.party_id).name},{world.document(e.invoice_id).number},"
                        f"{_money(e.net)},{_money(tax)},{_money(gross)},{e.memo}")
            obs.append(Observation(CREDIT_NOTES_VIEW, e.number, (e.id, e.invoice_id), gross))
        family_views.append(_view(CREDIT_NOTES_VIEW, "\n".join(rows) + "\n", obs, [], True))

    bank_name = world.party(world.bank_party_id).name
    def rows_of(v: View) -> int:
        return len(v.text.splitlines()) - 1
    manifest_text = "\n".join([
        "# File index", "", "| File | Contents |", "|---|---|",
        f"| `{LEDGER_VIEW}` | Beancount ledger. Chart of accounts, opening balances at {period.start}, "
        f"and posted {period.label} entries. |",
        f"| `{STATEMENT_VIEW}` | {bank_name} checking account statement. Period {period.start} to {period.end}. "
        f"{rows_of(statement_view)} rows. Columns: date, description, reference, debit, credit, balance. |",
        f"| `{ACCOUNTS_VIEW}` | Chart of accounts. {rows_of(accounts_view)} rows. Columns: account, type, description. |",
        f"| `{CUSTOMERS_VIEW}` | Customer master. {rows_of(customers_view)} rows. Columns: customer, terms, default_account. |",
        f"| `{VENDORS_VIEW}` | Vendor master. {rows_of(vendors_view)} rows. Columns: vendor, terms, default_account. |",
        f"| `{POLICY_VIEW}` | Bookkeeping policy notes. |",
        f"| `{ARCHIVE_VIEW}` | Checking account statement. Period {prior.start} to {prior.end}. "
        f"{rows_of(archive_view)} rows. Same columns as `{STATEMENT_VIEW}`. |",
    ] + ([
        f"| `{OPEN_ITEMS_VIEW}` | Open sales-invoice register at {period.start}. "
        f"{_rows_phrase(rows_of(family_views[0]))}. Columns: {', '.join(OPEN_ITEMS_COLUMNS)}. |",
        f"| `{REMITTANCE_VIEW}` | Customer remittance advices, one row per advice line. "
        f"{_rows_phrase(rows_of(family_views[1]))}. Columns: {', '.join(REMITTANCE_COLUMNS)}. |",
        f"| `{CREDIT_NOTES_VIEW}` | Credit notes issued in the period. "
        f"{_rows_phrase(rows_of(family_views[2]))}. Columns: {', '.join(CREDIT_NOTE_COLUMNS)}. |",
    ] if family else [])) + "\n"
    manifest_view = _view(MANIFEST_VIEW, manifest_text,
                          [Observation(MANIFEST_VIEW, v.name, (f"view:{v.name}",))
                           for v in (ledger_view, statement_view, accounts_view, customers_view, vendors_view,
                                     policy_view, archive_view, *family_views)], [], True)

    # expected balances: a fold over the expected ledger's PRESENT rows ----
    present = {o.node_ids[0] for o in expected_view.observations if o.node_ids[0].startswith("rec:")}
    totals: dict[str, Decimal] = {a.name: Decimal("0") for a in world.accounts}
    for rec in recognitions:
        if rec.id in present:
            for leg in rec.legs:
                totals[leg.account] += leg.amount
    expected_balances = tuple((a.name, totals[a.name]) for a in sorted(world.accounts, key=lambda a: a.code))
    balances_text = "\n".join(f"{a},{_money(v)}" for a, v in expected_balances) + "\n"
    balances_view = _view(EXPECTED_BALANCES_VIEW, balances_text,
                          [Observation(EXPECTED_BALANCES_VIEW, a, tuple(sorted(r.id for r in recognitions
                                                                                  if r.id in present and r.net_on(a) != 0)), v)
                           for a, v in expected_balances], [], False)

    views = (ledger_view, expected_view, statement_view, archive_view, accounts_view, customers_view, vendors_view,
             policy_view, manifest_view, balances_view) + tuple(family_views)
    _assert_exhaustive(views, recognitions, movements)

    graph_digest = domain_digest(GRAPH_DOMAIN, canonical_bytes({
        "schema_version": GRAPH_SCHEMA_VERSION, "world": world_canonical(world)}))
    plan_digest = domain_digest(MUTATION_PLAN_DOMAIN, canonical_bytes({
        "version": plan.version,
        "mutations": sorted((_mutation_canonical(m) for m in plan.mutations), key=lambda m: m["mutation_id"])}))
    return Bundle(world.id, world.title, world.currency, period, prior, plan, graph_digest, plan_digest,
                  recognitions, movements, opening_bank, views, expected_balances,
                  tuple(sorted(restated.items())))


def _rows_phrase(count: int) -> str:
    return f"{count} row{'' if count == 1 else 's'}"


def _assert_exhaustive(views, recognitions, movements) -> None:
    """Every consequence is classified exactly once in every consequence
    view: emitted (possibly as several rows of one record) or absent for a
    typed reason. Anything else is a projection failure."""
    ids = [r.id for r in recognitions] + [m.id for m in movements]
    for v in views:
        if v.name not in CONSEQUENCE_VIEWS:
            continue
        emitted = {o.node_ids[0] for o in v.observations if o.node_ids and o.node_ids[0] in ids}
        absent = {}
        for a in v.absences:
            if a.node_id in absent:
                raise ProjectionError(f"{v.name}: {a.node_id} has two absence reasons")
            absent[a.node_id] = a.reason
        for node_id in ids:
            present, gone = node_id in emitted, node_id in absent
            if present == gone:
                raise ProjectionError(f"{v.name}: {node_id} is {'both emitted and absent' if present else 'unclassified'}")


# --------------------------------------------------------------------------
# accounting invariants: the checks that do not trust the projector
# --------------------------------------------------------------------------

def check_bundle(world: World, bundle: Bundle) -> list[str]:
    """Independent of the projector's own helpers wherever it can be:
    balances are re-folded from legs, the statement's running column is
    re-walked row by row from its own text, the reconciliation identity is
    computed from both sides, and receipts are checked against invoices."""
    problems: list[str] = []
    roles = _roles(world)
    kinds = {a.name: a.kind for a in world.accounts}
    opened = {a.name: a.opened for a in world.accounts}
    for rec in bundle.recognitions:
        if not rec.balanced:
            problems.append(f"{rec.id}: legs do not balance")
        if len(rec.legs) < 2:
            problems.append(f"{rec.id}: fewer than two legs")
        for leg in rec.legs:
            if leg.account not in kinds:
                problems.append(f"{rec.id}: {leg.account} not in chart")
            elif opened[leg.account] > rec.date:
                problems.append(f"{rec.id}: {leg.account} not yet open")
    # every recognition's leg vector, re-folded here, equals the declared balances
    present = {o.node_ids[0] for o in bundle.view(EXPECTED_LEDGER_VIEW).observations if o.node_ids[0].startswith("rec:")}
    fold: dict[str, Decimal] = {}
    for rec in bundle.recognitions:
        if rec.id in present:
            for leg in rec.legs:
                fold[leg.account] = fold.get(leg.account, Decimal("0")) + leg.amount
    for account, value in bundle.expected_balances:
        if fold.get(account, Decimal("0")) != value:
            problems.append(f"{account}: refold {fold.get(account)} != declared {value}")
    # the statement's running column, re-walked from the CSV text
    for name, span in ((STATEMENT_VIEW, bundle.period), (ARCHIVE_VIEW, bundle.prior)):
        rows = [line.split(",") for line in bundle.view(name).text.splitlines()[1:]]
        running = None
        for row in rows:
            date, _, _, debit, credit, balance = row
            if not span.contains(date):
                problems.append(f"{name}: row dated {date} outside {span.start}..{span.end}")
            delta = (Decimal(credit) if credit else Decimal("0")) - (Decimal(debit) if debit else Decimal("0"))
            if running is not None and running + delta != Decimal(balance):
                problems.append(f"{name}: running balance breaks at {date}")
            running = Decimal(balance)
    archive_close = Decimal(bundle.view(ARCHIVE_VIEW).text.splitlines()[-1].split(",")[-1])
    if archive_close != bundle.opening_bank_balance:
        problems.append(f"prior close {archive_close} != period opening {bundle.opening_bank_balance}")
    statement_close = Decimal(bundle.view(STATEMENT_VIEW).text.splitlines()[-1].split(",")[-1])
    unsettled = sum((m.amount for m in bundle.movements
                     if any(a.node_id == m.id and a.reason is Reason.NOT_YET_SETTLED
                            for a in bundle.view(STATEMENT_VIEW).absences)), Decimal("0"))
    books_bank = dict(bundle.expected_balances)[world.bank_account]
    if statement_close + unsettled != books_bank:
        problems.append(f"reconciliation identity fails: statement {statement_close} + unsettled {unsettled} != books {books_bank}")
    # receipts against invoices; sales against their invoice gross; tax arithmetic
    applied: dict[str, Decimal] = {}
    paid: dict[str, Decimal] = {}
    for e in world.events:
        if isinstance(e, CustomerReceipt):
            applied[e.invoice_id] = applied.get(e.invoice_id, Decimal("0")) + e.amount
        if isinstance(e, AppliedReceipt):
            # An applied receipt is checked line by line — each line against
            # its invoice's face value — and cumulatively below: an invoice's
            # applications across ALL receipts (cash and the policy's
            # write-offs) never exceed what the invoice can absorb.
            lines_total = Decimal("0")
            for line in e.lines:
                invoice = world.document(line.invoice_id)
                if line.amount > invoice.gross:
                    problems.append(f"{e.id}: line on {invoice.number} pays {line.amount} above its gross {invoice.gross}")
                applied[line.invoice_id] = applied.get(line.invoice_id, Decimal("0")) + line.amount
                lines_total += line.amount
            if lines_total > e.amount:
                problems.append(f"{e.id}: the advice lines total {lines_total}, above the receipt of {e.amount}")
            for invoice_id, amount in write_offs_of(e):
                applied[invoice_id] = applied.get(invoice_id, Decimal("0")) + amount
            if e.settlement.cleared_on < e.date:
                problems.append(f"{e.id}: the bank saw the receipt before the customer sent it")
        if isinstance(e, CreditNote):
            tax, gross = credit_note_amounts(e)
            if e.net + tax != gross or gross <= 0:
                problems.append(f"{e.id}: net {e.net} + tax {tax} is not gross {gross}")
        if isinstance(e, VendorPayment):
            # accumulated per invoice, as receipts are: the per-payment check below
            # refuses one payment above the gross but let two half-payments that
            # sum above it through, so an economically wrong world could be built
            paid[e.invoice_id] = paid.get(e.invoice_id, Decimal("0")) + e.amount
        if isinstance(e, Sale):
            gross = (e.net + (e.net * e.tax_rate).quantize(Decimal("0.01"))).quantize(Decimal("0.01"))
            if world.document(e.invoice_id).gross != gross:
                problems.append(f"{e.id}: invoice gross {world.document(e.invoice_id).gross} != net+tax {gross}")
        if isinstance(e, (Purchase,)) and world.document(e.invoice_id).gross != e.amount:
            problems.append(f"{e.id}: purchase invoice gross disagrees with the amount received")
        if isinstance(e, VendorPayment) and world.document(e.invoice_id).gross < e.amount:
            problems.append(f"{e.id}: pays more than the invoice gross")
    for invoice_id, total in applied.items():
        if total > world.document(invoice_id).gross:
            problems.append(f"{invoice_id}: receipts {total} exceed gross {world.document(invoice_id).gross}")
    for invoice_id, total in paid.items():
        if total > world.document(invoice_id).gross:
            problems.append(f"{invoice_id}: payments {total} exceed gross {world.document(invoice_id).gross}")
    # opening receivables/payables cover the prior invoices still open at the boundary
    carried = dict(world.opening.carried)
    # The balance ENTERING the period of every prior invoice something in the
    # period applies to — its face value less what was applied against it
    # before the period (a part-paid invoice enters at its remainder) — must
    # be covered by the carried receivables.
    def applied_in_period(d) -> bool:
        return invoice_applications(world, d.id) > invoice_applications(world, d.id, before=bundle.period.start)
    prior_open_ar = sum((d.gross - invoice_applications(world, d.id, before=bundle.period.start)
                         for d in world.documents if d.kind is DocumentKind.SALES_INVOICE
                         and d.issued < bundle.period.start and applied_in_period(d)), Decimal("0"))
    if carried.get(roles.receivables, Decimal("0")) < prior_open_ar:
        problems.append(f"opening receivables {carried.get(roles.receivables)} < prior invoices settled in period {prior_open_ar}")
    if is_cash_application_world(world):
        # Gate (l), the truth side: the register entering the period ties to
        # the opening entry's receivables (U7). The public fold checks the
        # same identity over the projected bytes.
        register_total = sum((open_balance for _, _, open_balance in open_items(world, bundle.period)), Decimal("0"))
        if register_total != carried.get(roles.receivables, Decimal("0")):
            problems.append(f"REFUSE_REGISTER_DOES_NOT_TIE: the open-item register entering the period totals "
                            f"{register_total}, the opening entry's receivables {carried.get(roles.receivables)}")
    prior_open_ap = sum((d.gross for d in world.documents if d.kind is DocumentKind.PURCHASE_INVOICE
                         and d.issued < bundle.period.start
                         and any(isinstance(e, VendorPayment) and e.invoice_id == d.id and e.date >= bundle.period.start
                                 for e in world.events)), Decimal("0"))
    if -carried.get(roles.payables, Decimal("0")) < prior_open_ap:
        problems.append(f"opening payables {carried.get(roles.payables)} do not cover prior invoices paid in period {prior_open_ap}")
    # the two views of every settled event agree on the amount
    by_id = {r.id: r for r in bundle.recognitions}
    for m in bundle.movements:
        recs = [r for r in bundle.recognitions if r.event_id == m.event_id]
        if sum((r.net_on(world.bank_account) for r in recs), Decimal("0")) != m.amount:
            problems.append(f"{m.id}: the bank saw {m.amount}, the books say {sum(r.net_on(world.bank_account) for r in recs)}")
    return problems
