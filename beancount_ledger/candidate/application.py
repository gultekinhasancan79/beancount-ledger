"""`application/1`: the cash-application register's parse boundary and its
scorer (spec section 3, "cash_application.json", and section 4).

The cash-application family delivers two artifacts. The ledger is scored by
the frozen `candidate/1` (`committed.py`, byte-identical, engine id kept);
the register `cash_application.json` is scored HERE, against the truth
register `graph.derive.ApplicationInputs` mints from the authored facts.
`composite.py` multiplies the two. This module never reads the agent's
ledger: measured against the agent's own books, a ledger repair could fire
an application penalty and the composite would not be monotone.

THE PARSE BOUNDARY (`parse_application`). Schema `piv.cash-application/1`:
two-place decimal strings, every key required except `notes` (<= 200
characters), unknown keys refused, a duplicated JSON member name refused
anywhere in the document, two receipt records with one `receipt_id`, two
credit-note records with one `credit_note_id` and two `closing_open_items`
entries naming one `invoice_id` refused. Within one receipt or one credit
note, several `applied` (or `written_off`) entries naming the same invoice
are SUMMED before anything is compared or checked — splitting one
legitimate application into two entries is a formatting choice, never a
different accounting answer — and an entry that sums to zero applies
nothing (an informational zero-cash advice line, mirrored, is not a
defect). Then five accounting identities, each over every invoice or note:

    application.row_identity        remaining != period_basis - applied_total - credited - written_off,
                                    or any negative amount anywhere
    application.applied_identity    the receipts' cash applications to an invoice do not sum to that
                                    invoice's applied_total (an application naming an invoice with no
                                    row included)
    application.credit_identity     the credit applications to an invoice do not sum to its credited
    application.writeoff_identity   the receipts' write-offs against an invoice do not sum to its
                                    written_off, or a written_off item names an invoice with no row
    application.credit_conservation a credit note in the evidence has sum(applied) + unapplied_amount
                                    != its gross amount

An internally contradictory register is a REJECTED ARTIFACT, not a priced
one: `ApplicationRejected` carries the labels, the scorer answers
`APPLICATION_REJECTED` with `A = 0`, never an evaluator failure and never a
scored file carrying a label. The identities make each register column the
single quantity the scorer reads, so no accepted file can say one thing per
receipt and another per invoice. A credit-note id no evidence carries has
no gross to conserve; it is priced by `fabricated_credit_note` instead.
Every identity the truth register satisfies by construction is enforced on
the submission by this same boundary, and a violated identity rejects
rather than labels — the two sides are kept identical (spec section 8,
"Verification status").

THE SCORER (`score_application`). Inputs: the parsed application (or its
rejection, or None when nothing was delivered); the truth register `T`;
the expected closing receivables and the period's write-off movement from
the loaded environment's `expected_balances`. Three channels, summing to
1.00, each fraction quantised to six places half-even BEFORE weighting and
the total AFTER (candidate/1's order):

    receipts_exact  0.50   fraction of statement receipts whose canonical applied mapping, written_off
                           mapping and unapplied_amount all equal T; no record counts as inexact.
                           All-or-nothing per receipt: one wrong cent loses that receipt's
                           contribution, not the whole score.
    register_exact  0.30   fraction of invoices whose row equals T on customer, period_basis,
                           applied_total, credited, written_off and remaining
    credit_exact    0.20   fraction of credit notes whose canonical applied mapping and
                           unapplied_amount equal T

Penalties: `fabricated_invoice` / `fabricated_receipt` /
`fabricated_credit_note` -0.40 per id no evidence carries (one price, one
offence); `receipt_identity` -0.20 per statement receipt whose
sum(applied) + unapplied_amount is not the statement credit (write-offs
reduce receivables, not cash); `ar_tie_break` -0.30 once when
sum(remaining) - sum(unapplied_amount) over receipts and credit notes alike
is not the expected closing receivables; `writeoff_tie_break` -0.20 once
when the register rows' written_off column does not sum to the expected
write-off movement (the receipts' items are held equal to that column by
`writeoff_identity`, so the penalty never reads two numbers).
`A = clamp(sum(weighted channels) + sum(penalties), 0, 1)`. Absent or
rejected: `A = 0`. The 0.50 / 0.30 / 0.20 split and every price are
DECLARED ENGINEERING CHOICES: deterministic and reviewable, not
accountant-approved and not calibrated, carrying no claim of optimality.

THE STATE CATALOGUE is closed (`APPLICATION_STATES`), every member is
constructed once here and answered by a row of
`graph.state_contract.APPLICATION_STATE_CONTRACT`, and an inexact receipt
or credit note carries ONE reason state — named, not charged twice. A
receipt whose amount, write-off or unapplied residue is wrong is diagnosed
as such, not as "wrong invoices"; a credit note that is absent or split
wrongly is distinguished from one that names the wrong invoice.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from ..graph.derive import ApplicationInputs
from .canonical import canonical_bytes, domain_digest

# --------------------------------------------------------------------------
# identities and constants
# --------------------------------------------------------------------------

APPLICATION_ENGINE_ID = "application/1"
APPLICATION_SCHEMA = "piv.cash-application/1"

WEIGHT_RECEIPTS = Decimal("0.50")
WEIGHT_REGISTER = Decimal("0.30")
WEIGHT_CREDITS = Decimal("0.20")
PENALTY_FABRICATED_INVOICE = Decimal("-0.40")
PENALTY_FABRICATED_RECEIPT = Decimal("-0.40")
PENALTY_FABRICATED_CREDIT_NOTE = Decimal("-0.40")
PENALTY_RECEIPT_IDENTITY = Decimal("-0.20")
PENALTY_AR_TIE_BREAK = Decimal("-0.30")
PENALTY_WRITEOFF_TIE_BREAK = Decimal("-0.20")

CHANNEL_RECEIPTS = "receipts_exact"
CHANNEL_REGISTER = "register_exact"
CHANNEL_CREDITS = "credit_exact"
CHANNELS = (CHANNEL_RECEIPTS, CHANNEL_REGISTER, CHANNEL_CREDITS)

PENALTY_FABRICATED_INVOICE_LABEL = "fabricated_invoice"
PENALTY_FABRICATED_RECEIPT_LABEL = "fabricated_receipt"
PENALTY_FABRICATED_CREDIT_NOTE_LABEL = "fabricated_credit_note"
PENALTY_RECEIPT_IDENTITY_LABEL = "receipt_identity"
PENALTY_AR_TIE_BREAK_LABEL = "ar_tie_break"
PENALTY_WRITEOFF_TIE_BREAK_LABEL = "writeoff_tie_break"
PENALTY_LABELS = (
    PENALTY_FABRICATED_INVOICE_LABEL, PENALTY_FABRICATED_RECEIPT_LABEL, PENALTY_FABRICATED_CREDIT_NOTE_LABEL,
    PENALTY_RECEIPT_IDENTITY_LABEL, PENALTY_AR_TIE_BREAK_LABEL, PENALTY_WRITEOFF_TIE_BREAK_LABEL,
)
PENALTY_PRICES = {
    PENALTY_FABRICATED_INVOICE_LABEL: PENALTY_FABRICATED_INVOICE,
    PENALTY_FABRICATED_RECEIPT_LABEL: PENALTY_FABRICATED_RECEIPT,
    PENALTY_FABRICATED_CREDIT_NOTE_LABEL: PENALTY_FABRICATED_CREDIT_NOTE,
    PENALTY_RECEIPT_IDENTITY_LABEL: PENALTY_RECEIPT_IDENTITY,
    PENALTY_AR_TIE_BREAK_LABEL: PENALTY_AR_TIE_BREAK,
    PENALTY_WRITEOFF_TIE_BREAK_LABEL: PENALTY_WRITEOFF_TIE_BREAK,
}

# the parse-boundary rejection labels (spec section 3)
REJECT_SCHEMA = "application.schema"
REJECT_NOT_DECIMAL = "application.amount.not_decimal"
REJECT_DUPLICATE_MEMBER = "application.duplicate_member"
REJECT_RECEIPT_DUPLICATE_KEY = "application.receipt.duplicate_key"
REJECT_CREDIT_NOTE_DUPLICATE_KEY = "application.credit_note.duplicate_key"
REJECT_INVOICE_DUPLICATE_ROW = "application.invoice.duplicate_row"
REJECT_ROW_IDENTITY = "application.row_identity"
REJECT_APPLIED_IDENTITY = "application.applied_identity"
REJECT_CREDIT_IDENTITY = "application.credit_identity"
REJECT_WRITEOFF_IDENTITY = "application.writeoff_identity"
REJECT_CREDIT_CONSERVATION = "application.credit_conservation"
REJECTION_LABELS = (
    REJECT_SCHEMA, REJECT_NOT_DECIMAL, REJECT_DUPLICATE_MEMBER, REJECT_RECEIPT_DUPLICATE_KEY,
    REJECT_CREDIT_NOTE_DUPLICATE_KEY, REJECT_INVOICE_DUPLICATE_ROW, REJECT_ROW_IDENTITY, REJECT_APPLIED_IDENTITY,
    REJECT_CREDIT_IDENTITY, REJECT_WRITEOFF_IDENTITY, REJECT_CREDIT_CONSERVATION,
)
IDENTITY_LABELS = (REJECT_ROW_IDENTITY, REJECT_APPLIED_IDENTITY, REJECT_CREDIT_IDENTITY, REJECT_WRITEOFF_IDENTITY,
                   REJECT_CREDIT_CONSERVATION)

# what the scorer answered about the artifact as a whole
STATUS_DELIVERED = "delivered"
STATUS_ABSENT = "absent"
STATUS_REJECTED = "rejected"
STATUSES = (STATUS_DELIVERED, STATUS_ABSENT, STATUS_REJECTED)

MAX_NOTES_CHARS = 200
MAX_ID_CHARS = 120
MAX_TEXT_CHARS = 200
MAX_RECORDS = 500                      # per list; the tool's 16,000-byte envelope is far below this
MAX_REJECTION_LABELS = 5               # the tool's reply quotes at most this many

SCORE_SCALE = Decimal("0.000001")
_ZERO = Decimal("0.00")
_CENT = Decimal("0.01")
_AMOUNT = re.compile(r"^-?(?:0|[1-9][0-9]{0,11})\.[0-9]{2}$")
_INVOICE_TOKEN = re.compile(r"\bSI-\d+\b")

APPLICATION_DOMAIN = b"piv:application:v1\0"
APPLICATION_RESULT_DOMAIN = b"piv:application-result:v1\0"


def _scale(value: Decimal) -> Decimal:
    return value.quantize(SCORE_SCALE, rounding=ROUND_HALF_EVEN)


def _money(value: Decimal) -> str:
    return f"{value.quantize(_CENT):.2f}"


# --------------------------------------------------------------------------
# the state catalogue
# --------------------------------------------------------------------------

RECEIPT_SCOPE = "receipt"              # a state of one statement receipt (or of a record naming none)
INVOICE_SCOPE = "invoice"              # a state of one invoice row
CREDIT_SCOPE = "credit_note"           # a state of one credit note
TIE_SCOPE = "tie"                      # a state of a control total the register must tie to
APPLICATION_SCOPE = "application"      # a state of the artifact as a whole
STATE_SCOPES = (RECEIPT_SCOPE, INVOICE_SCOPE, CREDIT_SCOPE, TIE_SCOPE, APPLICATION_SCOPE)


class ApplicationState(str):
    """A member of the closed state universe: a `str` (so every surface
    compares, hashes and JSON-encodes it as its value) carrying the scope
    it applies to. Constructed once per member, below; a copy or a pickle
    is a plain `str` of the same value."""

    __slots__ = ("scope",)

    def __new__(cls, name: str, *, scope: str):
        if scope not in STATE_SCOPES:
            raise ValueError(f"{name}: scope {scope!r} is not one of {STATE_SCOPES}")
        self = super().__new__(cls, name)
        self.scope = scope
        return self

    def __repr__(self) -> str:
        return f"ApplicationState({str(self)!r}, scope={self.scope!r})"

    def __reduce__(self):
        return (str, (str(self),))


RECEIPT_EXACT = ApplicationState("RECEIPT_EXACT", scope=RECEIPT_SCOPE)
RECEIPT_CONTRADICTS_ADVICE = ApplicationState("RECEIPT_CONTRADICTS_ADVICE", scope=RECEIPT_SCOPE)
RECEIPT_CONTRADICTS_REFERENCE = ApplicationState("RECEIPT_CONTRADICTS_REFERENCE", scope=RECEIPT_SCOPE)
RECEIPT_WRONG_INVOICES = ApplicationState("RECEIPT_WRONG_INVOICES", scope=RECEIPT_SCOPE)
RECEIPT_WRONG_AMOUNT = ApplicationState("RECEIPT_WRONG_AMOUNT", scope=RECEIPT_SCOPE)
RECEIPT_WRONG_WRITEOFF = ApplicationState("RECEIPT_WRONG_WRITEOFF", scope=RECEIPT_SCOPE)
RECEIPT_WRONG_UNAPPLIED = ApplicationState("RECEIPT_WRONG_UNAPPLIED", scope=RECEIPT_SCOPE)
RECEIPT_MISSING = ApplicationState("RECEIPT_MISSING", scope=RECEIPT_SCOPE)
RECEIPT_FABRICATED = ApplicationState("RECEIPT_FABRICATED", scope=RECEIPT_SCOPE)
INVOICE_EXACT = ApplicationState("INVOICE_EXACT", scope=INVOICE_SCOPE)
INVOICE_WRONG_CUSTOMER = ApplicationState("INVOICE_WRONG_CUSTOMER", scope=INVOICE_SCOPE)
INVOICE_WRONG_BASIS = ApplicationState("INVOICE_WRONG_BASIS", scope=INVOICE_SCOPE)
INVOICE_INEXACT = ApplicationState("INVOICE_INEXACT", scope=INVOICE_SCOPE)
INVOICE_MISSING = ApplicationState("INVOICE_MISSING", scope=INVOICE_SCOPE)
INVOICE_FABRICATED = ApplicationState("INVOICE_FABRICATED", scope=INVOICE_SCOPE)
CREDIT_EXACT = ApplicationState("CREDIT_EXACT", scope=CREDIT_SCOPE)
CREDIT_WRONG_INVOICES = ApplicationState("CREDIT_WRONG_INVOICES", scope=CREDIT_SCOPE)
CREDIT_WRONG_SPLIT = ApplicationState("CREDIT_WRONG_SPLIT", scope=CREDIT_SCOPE)
CREDIT_MISSING = ApplicationState("CREDIT_MISSING", scope=CREDIT_SCOPE)
CREDIT_FABRICATED = ApplicationState("CREDIT_FABRICATED", scope=CREDIT_SCOPE)
AR_TIE_OK = ApplicationState("AR_TIE_OK", scope=TIE_SCOPE)
AR_TIE_CONTRADICTS = ApplicationState("AR_TIE_CONTRADICTS", scope=TIE_SCOPE)
WRITEOFF_TIE_OK = ApplicationState("WRITEOFF_TIE_OK", scope=TIE_SCOPE)
WRITEOFF_TIE_CONTRADICTS = ApplicationState("WRITEOFF_TIE_CONTRADICTS", scope=TIE_SCOPE)
APPLICATION_ABSENT = ApplicationState("APPLICATION_ABSENT", scope=APPLICATION_SCOPE)
APPLICATION_REJECTED = ApplicationState("APPLICATION_REJECTED", scope=APPLICATION_SCOPE)

APPLICATION_STATES = (
    RECEIPT_EXACT, RECEIPT_CONTRADICTS_ADVICE, RECEIPT_CONTRADICTS_REFERENCE, RECEIPT_WRONG_INVOICES,
    RECEIPT_WRONG_AMOUNT, RECEIPT_WRONG_WRITEOFF, RECEIPT_WRONG_UNAPPLIED, RECEIPT_MISSING, RECEIPT_FABRICATED,
    INVOICE_EXACT, INVOICE_WRONG_CUSTOMER, INVOICE_WRONG_BASIS, INVOICE_INEXACT, INVOICE_MISSING, INVOICE_FABRICATED,
    CREDIT_EXACT, CREDIT_WRONG_INVOICES, CREDIT_WRONG_SPLIT, CREDIT_MISSING, CREDIT_FABRICATED,
    AR_TIE_OK, AR_TIE_CONTRADICTS, WRITEOFF_TIE_OK, WRITEOFF_TIE_CONTRADICTS,
    APPLICATION_ABSENT, APPLICATION_REJECTED,
)
TIE_AR = "ar"
TIE_WRITEOFF = "writeoff"


# --------------------------------------------------------------------------
# the parsed artifact
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ReceiptRecord:
    receipt_id: str
    applied: tuple             # ((invoice_id, Decimal), ...) canonical: summed by invoice, zero dropped, by id
    written_off: tuple
    unapplied: Decimal
    notes: str | None = None

    @property
    def cash(self) -> Decimal:
        """What the record says the receipt was: sum(applied) + unapplied."""
        return sum((amount for _, amount in self.applied), _ZERO) + self.unapplied


@dataclass(frozen=True)
class CreditNoteRecord:
    credit_note_id: str
    applied: tuple
    unapplied: Decimal
    notes: str | None = None


@dataclass(frozen=True)
class InvoiceRow:
    invoice_id: str
    customer: str
    period_basis: Decimal
    applied_total: Decimal
    credited: Decimal
    written_off: Decimal
    remaining: Decimal
    notes: str | None = None

    @property
    def outcome(self) -> tuple:
        return (self.applied_total, self.credited, self.written_off, self.remaining)


@dataclass(frozen=True)
class ParsedApplication:
    """An accepted `piv.cash-application/1` document, canonicalised: every
    receipt, credit note and row in document order, applications summed by
    invoice. `canonical_digest` binds the canonical document."""

    receipts: tuple
    credit_notes: tuple
    register: tuple
    canonical_digest: str

    def receipt(self, receipt_id: str):
        return next((r for r in self.receipts if r.receipt_id == receipt_id), None)

    def credit_note(self, credit_note_id: str):
        return next((c for c in self.credit_notes if c.credit_note_id == credit_note_id), None)

    def row(self, invoice_id: str):
        return next((w for w in self.register if w.invoice_id == invoice_id), None)

    @property
    def counts(self) -> tuple:
        """(receipts, invoices, credit notes) — the accepted reply's figures."""
        return (len(self.receipts), len(self.register), len(self.credit_notes))

    def canonical_document(self) -> dict:
        return canonical_document(self.receipts, self.credit_notes, self.register)


@dataclass(frozen=True)
class ApplicationRejected:
    """The parse boundary's refusal: the labels in the order they were
    found, unique, and one human-readable detail per finding."""

    labels: tuple
    details: tuple

    def __str__(self) -> str:
        return "; ".join(self.details[:MAX_REJECTION_LABELS])


def canonical_document(receipts, credit_notes, register) -> dict:
    """The canonical `piv.cash-application/1` document: records by id,
    applications by invoice, two-place strings, `notes` kept where given."""
    def pairs(items):
        return [{"invoice_id": invoice_id, "amount": _money(amount)} for invoice_id, amount in sorted(items)]

    def with_notes(record: dict, notes) -> dict:
        if notes is not None:
            record["notes"] = notes
        return record

    return {
        "schema": APPLICATION_SCHEMA,
        "receipts": [
            with_notes({"receipt_id": r.receipt_id, "applied": pairs(r.applied), "written_off": pairs(r.written_off),
                        "unapplied_amount": _money(r.unapplied)}, r.notes)
            for r in sorted(receipts, key=lambda r: r.receipt_id)],
        "credit_notes": [
            with_notes({"credit_note_id": c.credit_note_id, "applied": pairs(c.applied),
                        "unapplied_amount": _money(c.unapplied)}, c.notes)
            for c in sorted(credit_notes, key=lambda c: c.credit_note_id)],
        "closing_open_items": [
            with_notes({"invoice_id": w.invoice_id, "customer": w.customer, "period_basis": _money(w.period_basis),
                        "applied_total": _money(w.applied_total), "credited": _money(w.credited),
                        "written_off": _money(w.written_off), "remaining": _money(w.remaining)}, w.notes)
            for w in sorted(register, key=lambda w: w.invoice_id)],
    }


def canonical_text(parsed: ParsedApplication) -> str:
    """The canonical document as the bytes `_publish` writes."""
    return json.dumps(parsed.canonical_document(), indent=1, ensure_ascii=False) + "\n"


def application_digest(document: dict) -> str:
    return domain_digest(APPLICATION_DOMAIN, canonical_bytes(document))


# --------------------------------------------------------------------------
# the parse boundary
# --------------------------------------------------------------------------

class _DuplicateMember(ValueError):
    pass


def _pairs_hook(pairs):
    seen = set()
    for key, _value in pairs:
        if key in seen:
            raise _DuplicateMember(key)
        seen.add(key)
    return dict(pairs)


def _refuse_constant(name):
    raise ValueError(f"{name} is not a JSON value this schema admits")


class _Findings:
    """Collects (label, detail) in the order found; labels are unique."""

    def __init__(self):
        self.labels: list = []
        self.details: list = []

    def fail(self, label: str, detail: str) -> None:
        if label not in self.labels:
            self.labels.append(label)
        self.details.append(f"{label}: {detail}")

    def __bool__(self) -> bool:
        return bool(self.labels)

    def rejection(self) -> ApplicationRejected:
        return ApplicationRejected(tuple(self.labels), tuple(self.details))


_TOP_KEYS = ("schema", "receipts", "credit_notes", "closing_open_items")
_RECEIPT_KEYS = ("receipt_id", "applied", "written_off", "unapplied_amount")
_CREDIT_KEYS = ("credit_note_id", "applied", "unapplied_amount")
_ROW_KEYS = ("invoice_id", "customer", "period_basis", "applied_total", "credited", "written_off", "remaining")
_ITEM_KEYS = ("invoice_id", "amount")
_NOTES = ("notes",)


def _object(value, required: tuple, optional: tuple, where: str, findings: _Findings) -> bool:
    if not isinstance(value, dict):
        findings.fail(REJECT_SCHEMA, f"{where} is not a JSON object")
        return False
    ok = True
    for key in required:
        if key not in value:
            findings.fail(REJECT_SCHEMA, f"{where} lacks the required key {key!r}")
            ok = False
    for key in value:
        if key not in required and key not in optional:
            findings.fail(REJECT_SCHEMA, f"{where} carries the unknown key {key!r}")
            ok = False
    return ok


def _clean_text(value) -> bool:
    return isinstance(value, str) and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def _identifier(value, where: str, findings: _Findings):
    if not _clean_text(value) or not value.strip() or len(value) > MAX_ID_CHARS:
        findings.fail(REJECT_SCHEMA, f"{where} is not a non-empty printable string of at most {MAX_ID_CHARS} "
                                     f"characters")
        return None
    return value


def _text(value, where: str, findings: _Findings, limit: int):
    if not _clean_text(value) or not value.strip() or len(value) > limit:
        findings.fail(REJECT_SCHEMA, f"{where} is not a non-empty printable string of at most {limit} characters")
        return None
    return value


def _notes(record: dict, where: str, findings: _Findings):
    if "notes" not in record:
        return None
    value = record["notes"]
    if not _clean_text(value) or len(value) > MAX_NOTES_CHARS:
        findings.fail(REJECT_SCHEMA, f"{where}: notes must be a printable string of at most {MAX_NOTES_CHARS} "
                                     f"characters")
        return None
    return value


def _amount(value, where: str, findings: _Findings):
    if not isinstance(value, str) or not _AMOUNT.match(value):
        findings.fail(REJECT_NOT_DECIMAL, f"{where} is not a two-place decimal string: {value!r}")
        return None
    return Decimal(value)


def _list(value, where: str, findings: _Findings):
    if not isinstance(value, list):
        findings.fail(REJECT_SCHEMA, f"{where} is not a list")
        return None
    if len(value) > MAX_RECORDS:
        findings.fail(REJECT_SCHEMA, f"{where} carries more than {MAX_RECORDS} entries")
        return None
    return value


def _items(value, where: str, findings: _Findings):
    """`applied` / `written_off`: a list of {invoice_id, amount}, canonicalised."""
    entries = _list(value, where, findings)
    if entries is None:
        return None
    out = []
    for i, item in enumerate(entries):
        label = f"{where}[{i}]"
        if not _object(item, _ITEM_KEYS, (), label, findings):
            continue
        invoice_id = _identifier(item["invoice_id"], f"{label}.invoice_id", findings)
        amount = _amount(item["amount"], f"{label}.amount", findings)
        if invoice_id is not None and amount is not None:
            out.append((invoice_id, amount))
    return _canonical_items(out)


def _canonical_items(items) -> tuple:
    """Sum by invoice, drop what sums to zero, order by invoice id."""
    totals: dict = {}
    for invoice_id, amount in items:
        totals[invoice_id] = totals.get(invoice_id, _ZERO) + amount
    return tuple((invoice_id, total) for invoice_id, total in sorted(totals.items()) if total != 0)


def parse_application(text: str, truth: ApplicationInputs) -> ParsedApplication | ApplicationRejected:
    """The one door: text in, an accepted canonical application or a
    rejection out. `truth` supplies the evidence's credit-note grosses for
    `credit_conservation` and nothing else; the parse boundary compares the
    document with itself, not with the answer."""
    if not isinstance(text, str):
        raise TypeError("parse_application takes the document's text")
    if not isinstance(truth, ApplicationInputs):
        raise TypeError("parse_application takes the family's ApplicationInputs")
    findings = _Findings()
    try:
        data = json.loads(text, object_pairs_hook=_pairs_hook, parse_constant=_refuse_constant)
    except _DuplicateMember as exc:
        findings.fail(REJECT_DUPLICATE_MEMBER, f"the member name {str(exc)!r} is written twice in one object")
        return findings.rejection()
    except (ValueError, RecursionError) as exc:
        findings.fail(REJECT_SCHEMA, f"not a JSON document: {str(exc)[:120]}")
        return findings.rejection()

    # ---- structure ---------------------------------------------------------
    if not _object(data, _TOP_KEYS, (), "the document", findings):
        return findings.rejection()
    if data["schema"] != APPLICATION_SCHEMA:
        findings.fail(REJECT_SCHEMA, f"schema is {data['schema']!r}, not {APPLICATION_SCHEMA!r}")
    receipts, credit_notes, register = [], [], []
    entries = _list(data["receipts"], "receipts", findings)
    for i, record in enumerate(entries or ()):
        where = f"receipts[{i}]"
        if not _object(record, _RECEIPT_KEYS, _NOTES, where, findings):
            continue
        receipt_id = _identifier(record["receipt_id"], f"{where}.receipt_id", findings)
        applied = _items(record["applied"], f"{where}.applied", findings)
        written_off = _items(record["written_off"], f"{where}.written_off", findings)
        unapplied = _amount(record["unapplied_amount"], f"{where}.unapplied_amount", findings)
        notes = _notes(record, where, findings)
        if None not in (receipt_id, applied, written_off, unapplied):
            receipts.append(ReceiptRecord(receipt_id, applied, written_off, unapplied, notes))
    entries = _list(data["credit_notes"], "credit_notes", findings)
    for i, record in enumerate(entries or ()):
        where = f"credit_notes[{i}]"
        if not _object(record, _CREDIT_KEYS, _NOTES, where, findings):
            continue
        credit_note_id = _identifier(record["credit_note_id"], f"{where}.credit_note_id", findings)
        applied = _items(record["applied"], f"{where}.applied", findings)
        unapplied = _amount(record["unapplied_amount"], f"{where}.unapplied_amount", findings)
        notes = _notes(record, where, findings)
        if None not in (credit_note_id, applied, unapplied):
            credit_notes.append(CreditNoteRecord(credit_note_id, applied, unapplied, notes))
    entries = _list(data["closing_open_items"], "closing_open_items", findings)
    for i, record in enumerate(entries or ()):
        where = f"closing_open_items[{i}]"
        if not _object(record, _ROW_KEYS, _NOTES, where, findings):
            continue
        invoice_id = _identifier(record["invoice_id"], f"{where}.invoice_id", findings)
        customer = _text(record["customer"], f"{where}.customer", findings, MAX_TEXT_CHARS)
        columns = [_amount(record[key], f"{where}.{key}", findings)
                   for key in ("period_basis", "applied_total", "credited", "written_off", "remaining")]
        notes = _notes(record, where, findings)
        if invoice_id is not None and customer is not None and None not in columns:
            register.append(InvoiceRow(invoice_id, customer, *columns, notes))
    if findings:
        return findings.rejection()

    # ---- duplicate keys ----------------------------------------------------
    for receipt_id, n in Counter(r.receipt_id for r in receipts).items():
        if n > 1:
            findings.fail(REJECT_RECEIPT_DUPLICATE_KEY, f"{n} receipt records carry receipt_id {receipt_id!r}")
    for credit_note_id, n in Counter(c.credit_note_id for c in credit_notes).items():
        if n > 1:
            findings.fail(REJECT_CREDIT_NOTE_DUPLICATE_KEY,
                          f"{n} credit-note records carry credit_note_id {credit_note_id!r}")
    for invoice_id, n in Counter(w.invoice_id for w in register).items():
        if n > 1:
            findings.fail(REJECT_INVOICE_DUPLICATE_ROW, f"{n} closing_open_items entries name {invoice_id!r}")
    if findings:
        return findings.rejection()

    # ---- the five identities -----------------------------------------------
    for r in receipts:
        for invoice_id, amount in r.applied + r.written_off:
            if amount < 0:
                findings.fail(REJECT_ROW_IDENTITY, f"{r.receipt_id}: {invoice_id} carries a negative amount {amount}")
        if r.unapplied < 0:
            findings.fail(REJECT_ROW_IDENTITY, f"{r.receipt_id}: unapplied_amount is negative")
    for c in credit_notes:
        for invoice_id, amount in c.applied:
            if amount < 0:
                findings.fail(REJECT_ROW_IDENTITY,
                              f"{c.credit_note_id}: {invoice_id} carries a negative amount {amount}")
        if c.unapplied < 0:
            findings.fail(REJECT_ROW_IDENTITY, f"{c.credit_note_id}: unapplied_amount is negative")
    rows = {w.invoice_id: w for w in register}
    for w in register:
        if any(v < 0 for v in (w.period_basis,) + w.outcome):
            findings.fail(REJECT_ROW_IDENTITY, f"{w.invoice_id}: a negative amount")
        if w.remaining != w.period_basis - w.applied_total - w.credited - w.written_off:
            findings.fail(REJECT_ROW_IDENTITY,
                          f"{w.invoice_id}: remaining {w.remaining} is not period_basis {w.period_basis} - "
                          f"applied_total {w.applied_total} - credited {w.credited} - written_off {w.written_off}")
    applied_by, written_off_by, credited_by = Counter(), Counter(), Counter()
    for r in receipts:
        for invoice_id, amount in r.applied:
            applied_by[invoice_id] += amount
        for invoice_id, amount in r.written_off:
            written_off_by[invoice_id] += amount
    for c in credit_notes:
        for invoice_id, amount in c.applied:
            credited_by[invoice_id] += amount
    for invoice_id in sorted(set(rows) | set(applied_by) | set(written_off_by) | set(credited_by)):
        w = rows.get(invoice_id)
        if w is None:
            if invoice_id in applied_by:
                findings.fail(REJECT_APPLIED_IDENTITY, f"a receipt applies cash to {invoice_id}, which has no row")
            if invoice_id in credited_by:
                findings.fail(REJECT_CREDIT_IDENTITY, f"a credit note is applied to {invoice_id}, which has no row")
            if invoice_id in written_off_by:
                findings.fail(REJECT_WRITEOFF_IDENTITY, f"a write-off names {invoice_id}, which has no row")
            continue
        if applied_by.get(invoice_id, _ZERO) != w.applied_total:
            findings.fail(REJECT_APPLIED_IDENTITY, f"{invoice_id}: the receipts apply {applied_by.get(invoice_id, _ZERO)}"
                                                   f", the row's applied_total is {w.applied_total}")
        if credited_by.get(invoice_id, _ZERO) != w.credited:
            findings.fail(REJECT_CREDIT_IDENTITY, f"{invoice_id}: the credit notes apply "
                                                  f"{credited_by.get(invoice_id, _ZERO)}, the row's credited is "
                                                  f"{w.credited}")
        if written_off_by.get(invoice_id, _ZERO) != w.written_off:
            findings.fail(REJECT_WRITEOFF_IDENTITY, f"{invoice_id}: the receipts write off "
                                                    f"{written_off_by.get(invoice_id, _ZERO)}, the row's written_off "
                                                    f"is {w.written_off}")
    gross_of = {c[0]: c[3] for c in truth.credit_notes}
    for c in credit_notes:
        if c.credit_note_id in gross_of:
            total = sum((amount for _, amount in c.applied), _ZERO) + c.unapplied
            if total != gross_of[c.credit_note_id]:
                findings.fail(REJECT_CREDIT_CONSERVATION,
                              f"{c.credit_note_id}: applied + unapplied is {total}, its gross amount "
                              f"{gross_of[c.credit_note_id]}")
    if findings:
        return findings.rejection()
    document = canonical_document(receipts, credit_notes, register)
    return ParsedApplication(tuple(receipts), tuple(credit_notes), tuple(register), application_digest(document))


# --------------------------------------------------------------------------
# the scorer
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ApplicationOutcome:
    total: Decimal                  # A
    components: tuple               # ((channel, fraction), ...) each quantised to six places
    penalties: tuple                # ((label, subject), ...) one per priced offence
    receipt_states: tuple           # ((receipt_id, state), ...) statement receipts in fold order, then fabricated
    invoice_states: tuple           # ((invoice_id, state), ...) the truth's invoices, then fabricated
    credit_states: tuple            # ((credit_note_id, state), ...)
    tie_states: tuple               # ((TIE_AR, state), (TIE_WRITEOFF, state)) when delivered
    application_states: tuple       # () when delivered; (APPLICATION_ABSENT,) or (APPLICATION_REJECTED,)
    status: str                     # STATUSES
    rejection: tuple                # the parse boundary's labels when rejected
    delivered: bool
    engine_id: str
    application_digest: str         # canonical digest of the scored document; "" when none
    result_digest: str = ""

    def as_canonical(self) -> dict:
        return {
            "total": str(self.total),
            "components": [[name, str(value)] for name, value in self.components],
            "penalties": [list(p) for p in self.penalties],
            "receipt_states": [list(x) for x in self.receipt_states],
            "invoice_states": [list(x) for x in self.invoice_states],
            "credit_states": [list(x) for x in self.credit_states],
            "tie_states": [list(x) for x in self.tie_states],
            "application_states": list(self.application_states),
            "status": self.status, "rejection": list(self.rejection), "delivered": self.delivered,
            "engine": self.engine_id, "application_digest": self.application_digest,
        }

    def verify(self) -> None:
        if type(self) is not ApplicationOutcome:
            raise RuntimeError("the recorded result is not an ApplicationOutcome")
        if application_result_digest(self.as_canonical()) != self.result_digest:
            raise RuntimeError("the recorded application result no longer reproduces its digest")

    @property
    def penalty_labels(self) -> tuple:
        return tuple(label for label, _subject in self.penalties)

    def states(self) -> tuple:
        """Every state the outcome carries, flattened."""
        return tuple(state for _subject, state in
                     self.receipt_states + self.invoice_states + self.credit_states + self.tie_states) \
            + tuple(self.application_states)

    def as_dict(self) -> dict:
        return {"total": self.total, "components": dict(self.components), "penalties": list(self.penalties),
                "receipt_states": dict(self.receipt_states), "invoice_states": dict(self.invoice_states),
                "credit_states": dict(self.credit_states), "tie_states": dict(self.tie_states),
                "application_states": list(self.application_states), "status": self.status,
                "rejection": list(self.rejection), "delivered": self.delivered, "engine": self.engine_id}


def application_result_digest(result_canonical: dict) -> str:
    return domain_digest(APPLICATION_RESULT_DOMAIN, canonical_bytes(result_canonical))


def _finalise(outcome: ApplicationOutcome) -> ApplicationOutcome:
    return dataclasses.replace(outcome, result_digest=application_result_digest(outcome.as_canonical()))


def _fraction(hit: int, count: int) -> Decimal:
    return _scale(Decimal(hit) / Decimal(count)) if count else _scale(Decimal(1))


def _expected(expected_balances) -> dict:
    return dict(expected_balances)


def _undelivered(status: str, state: ApplicationState, rejection: tuple) -> ApplicationOutcome:
    return _finalise(ApplicationOutcome(
        total=_scale(Decimal(0)),
        components=tuple((name, _scale(Decimal(0))) for name in CHANNELS),
        penalties=(), receipt_states=(), invoice_states=(), credit_states=(), tie_states=(),
        application_states=(state,), status=status, rejection=rejection, delivered=False,
        engine_id=APPLICATION_ENGINE_ID, application_digest=""))


def _reference_names_invoices(receipt_id: str) -> bool:
    _date, _colon, reference = receipt_id.partition(":")
    return bool(_INVOICE_TOKEN.search(reference))


def receipt_state(record, truth_receipt: tuple) -> ApplicationState:
    """One reason per statement receipt. `truth_receipt` is an
    `ApplicationInputs.receipts` tuple: (receipt_id, date, customer, amount,
    applied, written_off, unapplied, remittance_id, ...)."""
    if record is None:
        return RECEIPT_MISSING
    receipt_id, applied, written_off, unapplied, remittance_id = (
        truth_receipt[0], tuple(sorted(truth_receipt[4])), tuple(sorted(truth_receipt[5])), truth_receipt[6],
        truth_receipt[7])
    if record.applied == applied and record.written_off == written_off and record.unapplied == unapplied:
        return RECEIPT_EXACT
    if {i for i, _ in record.applied} != {i for i, _ in applied}:
        # the invoice set is what the authority names; which authority says so
        if remittance_id:
            return RECEIPT_CONTRADICTS_ADVICE
        if _reference_names_invoices(receipt_id):
            return RECEIPT_CONTRADICTS_REFERENCE
        return RECEIPT_WRONG_INVOICES
    if record.applied != applied:
        return RECEIPT_WRONG_AMOUNT
    if record.written_off != written_off:
        return RECEIPT_WRONG_WRITEOFF
    return RECEIPT_WRONG_UNAPPLIED


def invoice_state(row, truth_row: tuple) -> ApplicationState:
    """`truth_row` is an `ApplicationInputs.register` tuple: (invoice_id,
    customer, period_basis, applied_total, credited, written_off, remaining)."""
    if row is None:
        return INVOICE_MISSING
    if row.customer != truth_row[1]:
        return INVOICE_WRONG_CUSTOMER
    if row.period_basis != truth_row[2]:
        return INVOICE_WRONG_BASIS
    if row.outcome != tuple(truth_row[3:7]):
        return INVOICE_INEXACT
    return INVOICE_EXACT


def credit_state(record, truth_credit: tuple) -> ApplicationState:
    """`truth_credit` is an `ApplicationInputs.credit_notes` tuple:
    (credit_note_id, date, customer, gross, applied, unapplied, ...)."""
    if record is None:
        return CREDIT_MISSING
    applied, unapplied = tuple(sorted(truth_credit[4])), truth_credit[5]
    if record.applied == applied and record.unapplied == unapplied:
        return CREDIT_EXACT
    if {i for i, _ in record.applied} - {i for i, _ in applied}:
        return CREDIT_WRONG_INVOICES
    return CREDIT_WRONG_SPLIT


def score_application(application, truth: ApplicationInputs, *, expected_balances) -> ApplicationOutcome:
    """The `application/1` engine. `application` is a `ParsedApplication`,
    an `ApplicationRejected`, or None when nothing was delivered; `truth` the
    family's `ApplicationInputs`; `expected_balances` the loaded
    environment's ((account, Decimal), ...) — the expected closing
    receivables and the write-off movement are read from it, and a truth
    register that does not agree with them is an evaluator failure."""
    if not isinstance(truth, ApplicationInputs):
        raise TypeError("score_application takes the family's ApplicationInputs")
    expected = _expected(expected_balances)
    if truth.receivables_account not in expected:
        raise RuntimeError(f"the expected balances carry no {truth.receivables_account}")
    expected_ar = Decimal(expected[truth.receivables_account])
    expected_writeoff = Decimal(expected.get(truth.write_off_account, _ZERO))
    if expected_ar != truth.closing_ar:
        raise RuntimeError(f"the truth register closes at {truth.closing_ar}, the expected ledger at {expected_ar}")
    truth_writeoff = sum((row[5] for row in truth.register), _ZERO)
    if truth_writeoff != expected_writeoff:
        raise RuntimeError(f"the truth register writes off {truth_writeoff}, the expected ledger's "
                           f"{truth.write_off_account} moves {expected_writeoff}")
    if application is None:
        return _undelivered(STATUS_ABSENT, APPLICATION_ABSENT, ())
    if isinstance(application, ApplicationRejected):
        return _undelivered(STATUS_REJECTED, APPLICATION_REJECTED, application.labels)
    if type(application) is not ParsedApplication:
        raise TypeError("score_application takes a ParsedApplication, an ApplicationRejected or None")

    # ---- receipts ----------------------------------------------------------
    receipt_states, penalties = [], []
    truth_receipts = {r[0]: r for r in truth.receipts}
    for r in truth.receipts:
        record = application.receipt(r[0])
        receipt_states.append((r[0], receipt_state(record, r)))
        if record is not None and record.cash != r[3]:
            penalties.append((PENALTY_RECEIPT_IDENTITY_LABEL,
                              f"{r[0]}: applied + unapplied {record.cash}, statement credit {r[3]}"))
    for record in application.receipts:
        if record.receipt_id not in truth_receipts:
            receipt_states.append((record.receipt_id, RECEIPT_FABRICATED))
            penalties.append((PENALTY_FABRICATED_RECEIPT_LABEL, record.receipt_id))
    receipts_hit = sum(1 for _, s in receipt_states if s is RECEIPT_EXACT)

    # ---- the register ------------------------------------------------------
    invoice_states = []
    truth_rows = {w[0]: w for w in truth.register}
    for w in truth.register:
        invoice_states.append((w[0], invoice_state(application.row(w[0]), w)))
    named = {row.invoice_id for row in application.register}
    for r in application.receipts:
        named |= {i for i, _ in r.applied} | {i for i, _ in r.written_off}
    for c in application.credit_notes:
        named |= {i for i, _ in c.applied}
    for invoice_id in sorted(named - set(truth_rows)):
        invoice_states.append((invoice_id, INVOICE_FABRICATED))
        penalties.append((PENALTY_FABRICATED_INVOICE_LABEL, invoice_id))
    register_hit = sum(1 for _, s in invoice_states if s is INVOICE_EXACT)

    # ---- credit notes ------------------------------------------------------
    credit_states = []
    truth_credits = {c[0]: c for c in truth.credit_notes}
    for c in truth.credit_notes:
        credit_states.append((c[0], credit_state(application.credit_note(c[0]), c)))
    for record in application.credit_notes:
        if record.credit_note_id not in truth_credits:
            credit_states.append((record.credit_note_id, CREDIT_FABRICATED))
            penalties.append((PENALTY_FABRICATED_CREDIT_NOTE_LABEL, record.credit_note_id))
    credits_hit = sum(1 for _, s in credit_states if s is CREDIT_EXACT)

    # ---- the two ties ------------------------------------------------------
    remaining = sum((w.remaining for w in application.register), _ZERO)
    unapplied = (sum((r.unapplied for r in application.receipts), _ZERO)
                 + sum((c.unapplied for c in application.credit_notes), _ZERO))
    written_off = sum((w.written_off for w in application.register), _ZERO)
    tie_states = []
    if remaining - unapplied != expected_ar:
        tie_states.append((TIE_AR, AR_TIE_CONTRADICTS))
        penalties.append((PENALTY_AR_TIE_BREAK_LABEL,
                          f"remaining {remaining} - unapplied {unapplied} != closing receivables {expected_ar}"))
    else:
        tie_states.append((TIE_AR, AR_TIE_OK))
    if written_off != expected_writeoff:
        tie_states.append((TIE_WRITEOFF, WRITEOFF_TIE_CONTRADICTS))
        penalties.append((PENALTY_WRITEOFF_TIE_BREAK_LABEL,
                          f"written_off {written_off} != {truth.write_off_account} movement {expected_writeoff}"))
    else:
        tie_states.append((TIE_WRITEOFF, WRITEOFF_TIE_OK))

    # ---- the score ---------------------------------------------------------
    fractions = (
        (CHANNEL_RECEIPTS, _fraction(receipts_hit, len(truth.receipts))),
        (CHANNEL_REGISTER, _fraction(register_hit, len(truth.register))),
        (CHANNEL_CREDITS, _fraction(credits_hit, len(truth.credit_notes))),
    )
    weights = dict(zip(CHANNELS, (WEIGHT_RECEIPTS, WEIGHT_REGISTER, WEIGHT_CREDITS)))
    total = sum((weights[name] * value for name, value in fractions), Decimal(0))
    total += sum((PENALTY_PRICES[label] for label, _subject in penalties), Decimal(0))
    total = _scale(max(Decimal(0), min(Decimal(1), total)))
    return _finalise(ApplicationOutcome(
        total=total, components=fractions, penalties=tuple(penalties),
        receipt_states=tuple(receipt_states), invoice_states=tuple(invoice_states),
        credit_states=tuple(credit_states), tie_states=tuple(tie_states), application_states=(),
        status=STATUS_DELIVERED, rejection=(), delivered=True, engine_id=APPLICATION_ENGINE_ID,
        application_digest=application.canonical_digest))
