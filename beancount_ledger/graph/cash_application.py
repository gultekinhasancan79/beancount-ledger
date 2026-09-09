"""The PUBLIC cash-application fold: the register a reader reconstructs from
the evidence pack alone (spec section 5).

Receivables stay in one control account, so the ledger cannot say which
invoice a dollar settled. This module answers that question the way the
bookkeeper does — from the documents — and it answers it under the
`identify.py` discipline: the signature takes `dict[str, str]`, file name to
text, and the module imports nothing from `schema`, `policy`, `project`,
`derive` or `worlds`. It never sees the mutation plan, the authored
`AppliedReceipt` lines or the truth register. Gate (m) compares what is
folded here with the truth folded from the authored facts; if this module
could read those facts the comparison would prove nothing.

What is read, and from where:

    invoices      `open_items.csv` (face value AND the balance entering the
                  period — `period_basis` is the latter) plus every in-period
                  sale entry of the original ledger: a positive receivables
                  posting, no bank posting, exactly one `SI-nnnn` token in the
                  narration, customer = payee, `period_basis` = the debit;
    receipts      statement credit rows described `ACH IN <C>` or
                  `CHECK <n> <C>`, `<C>` an upper-cased `customers.csv` name;
                  `receipt_id = <date>:<reference>`;
    advices       `remittance_advice.csv`, one advice per `remittance_id`,
                  bound to a receipt iff customer, payment reference and
                  amount all agree, injectively both ways;
    credit notes  `credit_notes.csv`.

The fold runs in `(date, credit notes before receipts, statement order)`:

    credit note      `min(gross, open)` to the invoice it names (a paid
                     invoice takes none of it), the excess to the customer's
                     other open invoices by `(invoice_date, invoice_id)`, the
                     residue that customer's unapplied credit;
    adviced receipt  each line validated, then applied to the invoice it
                     names for the amount it states; a write-off iff the
                     advice marks the invoice settled and the shortfall,
                     after combining that advice's lines for that invoice, is
                     more than zero and at most `SHORT_PAY_TOLERANCE`; the
                     residue the advice does not name is unapplied — the
                     fallback rungs are NOT run for it;
    un-adviced       rung (2): the invoices the statement reference names, by
                     `(invoice_date, invoice_id)`, each up to its open
                     balance; rung (3): the customer's open invoices oldest
                     first by the same key; the residue unapplied.

Every authoring slip the spec's U-table names raises a `Refusal` carrying
the spec's code (`REFUSE_*`); the two U12 conditions are warnings on the
result. The fold is a total function of the public text where it does not
refuse. That is determinism, and nothing more: it does not show the rules
represent the evidence faithfully, which is what the refusal fixtures, gate
(m) and the domain review carry separately.

Gate (o) lives here too, because a baseline is a reading of the same public
text. Each named baseline runs as a chain from the opening register through
the same engine under a different strategy, enumerating every reading it
admits (amount-only branches on every exact subset); `baseline_report`
records for each whether ANY reading reaches the truth on every receipt
line, credit application and register row. Invoice-number order over the
reference is reported as a DIAGNOSTIC, never a refusal: it coincides with
invoice-date order whenever the named invoices' numbers and dates agree, so
it cannot separate the two orders (Case 2), and the implementation is pinned
by a fixture whose named invoices disagree instead.
"""

from __future__ import annotations

import csv
import io
import itertools
import json
import re
from dataclasses import dataclass, field
from datetime import date as _date, timedelta
from decimal import Decimal, InvalidOperation

CASH_APPLICATION_VERSION = 1
APPLICATION_SCHEMA = "piv.cash-application/1"

OPEN_ITEMS_FILE = "open_items.csv"
REMITTANCE_FILE = "remittance_advice.csv"
CREDIT_NOTES_FILE = "credit_notes.csv"
LEDGER_FILE = "ledger.beancount"
STATEMENT_FILE = "bank_statement.csv"
ACCOUNTS_FILE = "accounts.csv"
CUSTOMERS_FILE = "customers.csv"

#: The three files this family adds to the eight every task mounts.
EXTRA_PUBLIC_FILES = (OPEN_ITEMS_FILE, REMITTANCE_FILE, CREDIT_NOTES_FILE)

OPEN_ITEMS_COLUMNS = ("invoice_id", "customer", "invoice_date", "due_date", "original_amount", "open_balance")
REMITTANCE_COLUMNS = ("remittance_id", "customer", "remittance_date", "payment_method", "payment_reference",
                      "payment_amount", "invoice_id", "amount_paid", "settles_invoice", "deduction_amount", "note")
CREDIT_NOTE_COLUMNS = ("credit_note_id", "date", "customer", "invoice_id", "net_amount", "tax_amount",
                       "gross_amount", "reason")
STATEMENT_COLUMNS = ("date", "description", "reference", "debit", "credit", "balance")

#: `policy.md`'s tolerance: a settled invoice's shortfall at or under this is
#: written off; above it nothing is, and the shortfall stays open.
SHORT_PAY_TOLERANCE = Decimal("25.00")

# Refusals, named as the spec's U-table names them (each an error at
# verify_world). U8, U10 and U11 need the truth and are gates elsewhere.
REFUSE_AMBIGUOUS_REMITTANCE_JOIN = "REFUSE_AMBIGUOUS_REMITTANCE_JOIN"     # U1
REFUSE_LINE_CONTRADICTS_REGISTER = "REFUSE_LINE_CONTRADICTS_REGISTER"     # U2
REFUSE_FOREIGN_OR_UNKNOWN_INVOICE = "REFUSE_FOREIGN_OR_UNKNOWN_INVOICE"   # U3
REFUSE_ADVICE_AMOUNT_DISAGREES = "REFUSE_ADVICE_AMOUNT_DISAGREES"         # U4
REFUSE_ORDER_SENSITIVE = "REFUSE_ORDER_SENSITIVE"                         # U5
REFUSE_DUPLICATE_RECEIPT_KEY = "REFUSE_DUPLICATE_RECEIPT_KEY"             # U6
REFUSE_REGISTER_DOES_NOT_TIE = "REFUSE_REGISTER_DOES_NOT_TIE"             # U7, gate (l)
REFUSE_SALE_WITHOUT_UNIQUE_NUMBER = "REFUSE_SALE_WITHOUT_UNIQUE_NUMBER"   # U9
REFUSALS = (
    REFUSE_AMBIGUOUS_REMITTANCE_JOIN, REFUSE_LINE_CONTRADICTS_REGISTER, REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
    REFUSE_ADVICE_AMOUNT_DISAGREES, REFUSE_ORDER_SENSITIVE, REFUSE_DUPLICATE_RECEIPT_KEY,
    REFUSE_REGISTER_DOES_NOT_TIE, REFUSE_SALE_WITHOUT_UNIQUE_NUMBER,
)

# U12: warned, never refused.
WARN_DEDUCTION_AT_TOLERANCE = "WARN_DEDUCTION_AT_TOLERANCE"
WARN_LINE_ON_ZERO_BALANCE = "WARN_LINE_ON_ZERO_BALANCE"
#: An advice that binds no receipt is "evidence for no payment" (policy
#: text) — it is ignored, and reported so an author sees it.
WARN_UNBOUND_ADVICE = "WARN_UNBOUND_ADVICE"

_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")
_ENTRY = re.compile(r'^(\d{4}-\d{2}-\d{2})\s+[*!]\s+"([^"]*)"(?:\s+"([^"]*)")?\s*$')
_POSTING = re.compile(r'^\s{2,}([A-Z][A-Za-z0-9:_-]*)\s+(-?[\d,]+\.\d{2})\s+[A-Z]{3}\s*$')
_INVOICE_TOKEN = re.compile(r"\bSI-\d+\b")
_ACH_IN = re.compile(r"^ACH IN\s+(.+?)\s*$")
_CHEQUE_IN = re.compile(r"^CHECK\s+(\S+)\s+(.+?)\s*$")
_BANK_PREFIX = "Assets:Bank"

#: A baseline that branches more than this is a fixture problem, not a reading.
MAX_BASELINE_READINGS = 256


class PublicOnly(TypeError):
    """Raised when the input is not a mapping of file name to text."""


class Refusal(ValueError):
    """An authoring slip the U-table names. `code` is the spec's name."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


# --------------------------------------------------------------------------
# evidence
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    customer: str
    invoice_date: str
    due_date: str
    face_value: Decimal
    period_basis: Decimal
    source: str                      # "register" | "sale"


@dataclass(frozen=True)
class AdviceLine:
    invoice_id: str
    amount_paid: Decimal
    settles: bool
    deduction: Decimal
    note: str


@dataclass(frozen=True)
class Advice:
    remittance_id: str
    customer: str
    remittance_date: str
    payment_method: str
    payment_reference: str
    payment_amount: Decimal
    lines: tuple


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    index: int                       # statement order
    date: str
    reference: str
    amount: Decimal
    customer: str
    method: str                      # "ACH" | "CHECK"
    cheque_number: str


@dataclass(frozen=True)
class CreditNote:
    credit_note_id: str
    index: int                       # file order
    date: str
    customer: str
    invoice_id: str
    net: Decimal
    tax: Decimal
    gross: Decimal
    reason: str


@dataclass(frozen=True)
class Evidence:
    period_start: str
    period_end: str
    customers: tuple                 # names, file order
    receivables_accounts: frozenset
    invoices: tuple                  # Invoice, register rows then sales
    receipts: tuple                  # Receipt, statement order
    advices: tuple                   # Advice, file order
    credit_notes: tuple              # CreditNote, file order
    opening_ar: Decimal
    bindings: dict                   # receipt_id -> remittance_id
    warnings: tuple

    def invoice(self, invoice_id: str):
        for inv in self.invoices:
            if inv.invoice_id == invoice_id:
                return inv
        return None

    def advice_for(self, receipt: Receipt):
        remittance_id = self.bindings.get(receipt.receipt_id)
        if remittance_id is None:
            return None
        return next(a for a in self.advices if a.remittance_id == remittance_id)


# --------------------------------------------------------------------------
# result
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ReceiptApplication:
    receipt_id: str
    date: str
    customer: str
    amount: Decimal
    applied: tuple                   # ((invoice_id, amount), ...) in application order, one per invoice
    written_off: tuple
    unapplied: Decimal
    rungs: tuple                     # diagnostic: which authorities decided it
    remittance_id: str


@dataclass(frozen=True)
class CreditApplication:
    credit_note_id: str
    date: str
    customer: str
    gross: Decimal
    applied: tuple
    unapplied: Decimal


@dataclass(frozen=True)
class InvoiceRow:
    invoice_id: str
    customer: str
    period_basis: Decimal
    applied_total: Decimal
    credited: Decimal
    written_off: Decimal
    remaining: Decimal


@dataclass(frozen=True)
class Application:
    receipts: tuple                  # fold order
    credit_notes: tuple              # fold order
    register: tuple                  # InvoiceRow, by invoice_id
    closing_ar: Decimal
    opening_ar: Decimal
    warnings: tuple

    def receipt(self, receipt_id: str) -> ReceiptApplication:
        return next(r for r in self.receipts if r.receipt_id == receipt_id)

    def credit_note(self, credit_note_id: str) -> CreditApplication:
        return next(c for c in self.credit_notes if c.credit_note_id == credit_note_id)

    def row(self, invoice_id: str) -> InvoiceRow:
        return next(r for r in self.register if r.invoice_id == invoice_id)


def application_key(app: Application) -> tuple:
    """The application as a canonical, order-free tuple: every receipt's
    applied and written-off mappings and unapplied residue, every credit
    note's mapping and residue, every register row. Built the same way on
    both sides of gate (m); `rungs` and dates are diagnostics, not answers."""
    receipts = tuple(sorted(
        (r.receipt_id, tuple(sorted(r.applied)), tuple(sorted(r.written_off)), r.unapplied) for r in app.receipts))
    credits = tuple(sorted((c.credit_note_id, tuple(sorted(c.applied)), c.unapplied) for c in app.credit_notes))
    rows = tuple(sorted((w.invoice_id, w.customer, w.period_basis, w.applied_total, w.credited, w.written_off,
                         w.remaining) for w in app.register))
    return (("receipts", receipts), ("credit_notes", credits), ("register", rows))


def document(app: Application) -> dict:
    """The `piv.cash-application/1` document the fold's answer would be
    delivered as: two-place decimal strings, no `notes`."""
    def pairs(items):
        return [{"invoice_id": invoice_id, "amount": _money(amount)} for invoice_id, amount in items]
    return {
        "schema": APPLICATION_SCHEMA,
        "receipts": [
            {"receipt_id": r.receipt_id, "applied": pairs(r.applied), "written_off": pairs(r.written_off),
             "unapplied_amount": _money(r.unapplied)} for r in app.receipts],
        "credit_notes": [
            {"credit_note_id": c.credit_note_id, "applied": pairs(c.applied), "unapplied_amount": _money(c.unapplied)}
            for c in app.credit_notes],
        "closing_open_items": [
            {"invoice_id": w.invoice_id, "customer": w.customer, "period_basis": _money(w.period_basis),
             "applied_total": _money(w.applied_total), "credited": _money(w.credited),
             "written_off": _money(w.written_off), "remaining": _money(w.remaining)} for w in app.register],
    }


def document_text(app: Application) -> str:
    return json.dumps(document(app), indent=1, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def _money(value: Decimal) -> str:
    return f"{value.quantize(_CENT):.2f}"


def _amount(text: str, where: str) -> Decimal:
    try:
        value = Decimal(text.strip().replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"{where}: {text!r} is not an amount") from exc
    if value != value.quantize(_CENT):
        raise ValueError(f"{where}: {text!r} is not a two-place amount")
    return value.quantize(_CENT)


def _iso(text: str, where: str) -> str:
    text = text.strip()
    try:
        _date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{where}: {text!r} is not an ISO date") from exc
    return text


def _month_end(period_start: str) -> str:
    first = _date.fromisoformat(period_start).replace(day=1)
    return ((first + timedelta(days=32)).replace(day=1) - timedelta(days=1)).isoformat()


def _rows(public: dict, name: str, columns: tuple) -> list:
    if name not in public:
        raise ValueError(f"{name} is not in the evidence pack")
    reader = csv.DictReader(io.StringIO(public[name]))
    header = tuple(h.strip() for h in (reader.fieldnames or ()))
    if header != columns:
        raise ValueError(f"{name}: columns {header} are not {columns}")
    out = []
    for record in reader:
        if not any((v or "").strip() for v in record.values()):
            continue
        out.append({k: (v or "").strip() for k, v in record.items()})
    return out


def _yes_no(text: str, where: str) -> bool:
    lowered = text.strip().lower()
    if lowered not in ("yes", "no"):
        raise ValueError(f"{where}: settles_invoice {text!r} is not yes/no")
    return lowered == "yes"


def _customers(public: dict) -> tuple:
    """(names in file order, name -> default account)."""
    names, accounts = [], {}
    for record in csv.DictReader(io.StringIO(public.get(CUSTOMERS_FILE, ""))):
        name = (record.get("customer") or "").strip()
        if not name:
            continue
        account = (record.get("default_account") or "").strip()
        if not account:
            raise ValueError(f"{CUSTOMERS_FILE}: {name} carries no default_account")
        names.append(name)
        accounts[name] = account
    if not names:
        raise ValueError(f"{CUSTOMERS_FILE}: no customers")
    return tuple(names), accounts


def _equity_accounts(public: dict) -> frozenset:
    out = set()
    for record in csv.DictReader(io.StringIO(public.get(ACCOUNTS_FILE, ""))):
        name = (record.get("account") or "").strip()
        if name and (record.get("type") or "").strip().lower() == "equity":
            out.add(name)
    return frozenset(out)


def _entries(ledger_text: str) -> list:
    """Every transaction as (date, payee, narration, [(account, amount)])."""
    entries, pending = [], None
    for line in ledger_text.splitlines():
        header = _ENTRY.match(line)
        if header:
            if pending:
                entries.append(pending)
            pending = [header.group(1), header.group(2), header.group(3) or "", []]
            continue
        posting = _POSTING.match(line)
        if posting and pending:
            pending[3].append((posting.group(1), _amount(posting.group(2), LEDGER_FILE)))
            continue
        if pending and (not line.strip() or not line.startswith(" ")):
            entries.append(pending)
            pending = None
    if pending:
        entries.append(pending)
    return [(d, p, n, tuple(legs)) for d, p, n, legs in entries]


def _is_bank(account: str, bank_account) -> bool:
    return account == bank_account if bank_account else account.startswith(_BANK_PREFIX)


def _period(public: dict, period_start, period_end) -> tuple:
    if period_start is None:
        for record in csv.DictReader(io.StringIO(public.get(STATEMENT_FILE, ""))):
            if not (record.get("debit") or "").strip() and not (record.get("credit") or "").strip():
                period_start = (record.get("date") or "").strip()
                break
        if not period_start:
            raise ValueError(f"{STATEMENT_FILE}: no opening row, and no period_start given")
    period_start = _iso(period_start, "period_start")
    period_end = _iso(period_end, "period_end") if period_end else _month_end(period_start)
    return period_start, period_end


def read_evidence(public: dict, *, bank_account: str | None = None, period_start: str | None = None,
                  period_end: str | None = None) -> Evidence:
    """Parse the pack and run the static refusals: U6 (receipt keys), U9
    (sale numbers), U7 (the register ties to the opening entry), U4 and U1
    (advice binding). The dynamic ones (U2, U3, U5) belong to `fold`."""
    if not isinstance(public, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in public.items()):
        raise PublicOnly("the fold takes a mapping of public file name to text, and nothing richer")
    period_start, period_end = _period(public, period_start, period_end)
    customers, accounts_of = _customers(public)
    receivables = frozenset(accounts_of.values())
    warnings: list[str] = []

    # invoices: the register --------------------------------------------
    invoices: list[Invoice] = []
    seen: set = set()
    for i, r in enumerate(_rows(public, OPEN_ITEMS_FILE, OPEN_ITEMS_COLUMNS), 1):
        where = f"{OPEN_ITEMS_FILE} row {i}"
        if r["invoice_id"] in seen:
            raise ValueError(f"{where}: {r['invoice_id']} is listed twice")
        if r["customer"] not in customers:
            raise ValueError(f"{where}: {r['customer']!r} is not in {CUSTOMERS_FILE}")
        seen.add(r["invoice_id"])
        invoices.append(Invoice(r["invoice_id"], r["customer"], _iso(r["invoice_date"], where),
                                _iso(r["due_date"], where), _amount(r["original_amount"], where),
                                _amount(r["open_balance"], where), "register"))
    register_ids = frozenset(seen)

    # invoices: in-period sales, and the opening entry ---------------------
    equity = _equity_accounts(public)
    opening_ar = _ZERO
    for date, payee, narration, legs in _entries(public.get(LEDGER_FILE, "")):
        is_opening = (any(a in equity for a, _ in legs) if equity
                      else any(a.startswith("Equity:") for a, _ in legs))
        if is_opening and date <= period_start:
            opening_ar += sum((v for a, v in legs if a in receivables), _ZERO)
            continue
        if not (period_start <= date <= period_end):
            continue
        ar = sum((v for a, v in legs if a in receivables), _ZERO)
        if ar <= 0 or any(_is_bank(a, bank_account) for a, _ in legs):
            continue
        tokens = _INVOICE_TOKEN.findall(narration)
        label = f'{date} "{payee}" "{narration}"'
        if len(tokens) != 1:
            raise Refusal(REFUSE_SALE_WITHOUT_UNIQUE_NUMBER,
                          f"sale {label} names {len(tokens)} invoice numbers, not one")
        number = tokens[0]
        if number in seen:
            raise Refusal(REFUSE_SALE_WITHOUT_UNIQUE_NUMBER,
                          f"sale {label} reuses {number}, which "
                          f"{'the register' if number in register_ids else 'another sale'} already carries")
        if payee not in customers:
            raise ValueError(f"sale {label}: payee is not in {CUSTOMERS_FILE}")
        seen.add(number)
        invoices.append(Invoice(number, payee, date, "", ar, ar, "sale"))

    # U7 / gate (l): the register ties to the opening entry -----------------
    register_total = sum((inv.period_basis for inv in invoices if inv.source == "register"), _ZERO)
    if register_total != opening_ar:
        raise Refusal(REFUSE_REGISTER_DOES_NOT_TIE,
                      f"sum of open_balance {_money(register_total)} is not the opening entry's receivables "
                      f"{_money(opening_ar)}")

    # receipts: statement customer-credit rows ------------------------------
    upper_names = {name.upper(): name for name in customers}
    receipts: list[Receipt] = []
    for record in _rows(public, STATEMENT_FILE, STATEMENT_COLUMNS):
        if not record["credit"] or record["debit"]:
            continue
        date = _iso(record["date"], STATEMENT_FILE)
        if not (period_start <= date <= period_end):
            continue
        description, reference = record["description"], record["reference"]
        ach, cheque = _ACH_IN.match(description), _CHEQUE_IN.match(description)
        if ach and ach.group(1).upper() in upper_names:
            customer, method, number = upper_names[ach.group(1).upper()], "ACH", ""
        elif cheque and cheque.group(2).upper() in upper_names:
            customer, method, number = upper_names[cheque.group(2).upper()], "CHECK", cheque.group(1)
        else:
            raise Refusal(REFUSE_DUPLICATE_RECEIPT_KEY,
                          f"credit row {date} {description!r} names no customer of {CUSTOMERS_FILE}")
        receipt_id = f"{date}:{reference}"
        if any(r.receipt_id == receipt_id for r in receipts):
            raise Refusal(REFUSE_DUPLICATE_RECEIPT_KEY, f"two customer-credit rows share {receipt_id!r}")
        receipts.append(Receipt(receipt_id, len(receipts), date, reference,
                                _amount(record["credit"], STATEMENT_FILE), customer, method, number))

    # advices ---------------------------------------------------------------
    grouped: dict = {}
    for i, r in enumerate(_rows(public, REMITTANCE_FILE, REMITTANCE_COLUMNS), 1):
        where = f"{REMITTANCE_FILE} row {i}"
        if r["customer"] not in customers:
            raise ValueError(f"{where}: {r['customer']!r} is not in {CUSTOMERS_FILE}")
        head = (r["customer"], _iso(r["remittance_date"], where), r["payment_method"], r["payment_reference"],
                _amount(r["payment_amount"], where))
        line = AdviceLine(r["invoice_id"], _amount(r["amount_paid"], where),
                          _yes_no(r["settles_invoice"], where), _amount(r["deduction_amount"], where), r["note"])
        if line.amount_paid < 0 or line.deduction < 0:
            raise ValueError(f"{where}: negative amount")
        entry = grouped.setdefault(r["remittance_id"], (head, []))
        if entry[0] != head:
            raise ValueError(f"{where}: {r['remittance_id']} changes its header fields between rows")
        entry[1].append(line)
    advices = tuple(Advice(rid, *head, tuple(lines)) for rid, (head, lines) in grouped.items())

    # binding: customer, reference and amount all agree; injective ---------
    bindings: dict = {}
    for advice in advices:
        same_reference = [r for r in receipts
                          if r.customer == advice.customer and r.reference == advice.payment_reference]
        matches = [r for r in same_reference if r.amount == advice.payment_amount]
        if same_reference and not matches:
            raise Refusal(REFUSE_ADVICE_AMOUNT_DISAGREES,
                          f"{advice.remittance_id} states {_money(advice.payment_amount)} but the statement row "
                          f"with reference {advice.payment_reference!r} carries "
                          f"{', '.join(_money(r.amount) for r in same_reference)}")
        if len(matches) > 1:
            raise Refusal(REFUSE_AMBIGUOUS_REMITTANCE_JOIN,
                          f"{advice.remittance_id} binds {len(matches)} statement rows: "
                          f"{', '.join(r.receipt_id for r in matches)}")
        if not matches:
            warnings.append(f"{WARN_UNBOUND_ADVICE}: {advice.remittance_id} belongs to no statement row and is "
                            f"evidence for no payment")
            continue
        receipt = matches[0]
        if receipt.receipt_id in bindings:
            raise Refusal(REFUSE_AMBIGUOUS_REMITTANCE_JOIN,
                          f"{bindings[receipt.receipt_id]} and {advice.remittance_id} both bind "
                          f"{receipt.receipt_id}")
        bindings[receipt.receipt_id] = advice.remittance_id

    # credit notes ----------------------------------------------------------
    credit_notes: list[CreditNote] = []
    for i, r in enumerate(_rows(public, CREDIT_NOTES_FILE, CREDIT_NOTE_COLUMNS), 1):
        where = f"{CREDIT_NOTES_FILE} row {i}"
        if any(c.credit_note_id == r["credit_note_id"] for c in credit_notes):
            raise ValueError(f"{where}: {r['credit_note_id']} is listed twice")
        if r["customer"] not in customers:
            raise ValueError(f"{where}: {r['customer']!r} is not in {CUSTOMERS_FILE}")
        net, tax, gross = (_amount(r[k], where) for k in ("net_amount", "tax_amount", "gross_amount"))
        if net + tax != gross or gross <= 0:
            raise ValueError(f"{where}: net {net} + tax {tax} is not gross {gross}")
        credit_notes.append(CreditNote(r["credit_note_id"], len(credit_notes), _iso(r["date"], where),
                                       r["customer"], r["invoice_id"], net, tax, gross, r["reason"]))

    return Evidence(period_start, period_end, customers, receivables, tuple(invoices), tuple(receipts), advices,
                    tuple(credit_notes), opening_ar, bindings, tuple(warnings))


# --------------------------------------------------------------------------
# the engine: one fold, several strategies
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Strategy:
    """How a reading decides. The truth is `POLICY`; every baseline is one
    field changed."""
    adviced: str = "advice"          # "advice" honours a bound advice | "ignore" treats every receipt as un-adviced
    unadviced: str = "policy"        # "policy" (rungs 2+3) | "amount" | "oldest" | "hold" | "printed" | "number"
    credit: str = "policy"           # "policy" | "ignore"
    writeoff: str = "tolerance"      # "tolerance" | "all" | "none"


POLICY = Strategy()


@dataclass
class _State:
    remaining: dict
    applied: dict
    credited: dict
    written_off: dict
    receipts: list = field(default_factory=list)
    credits: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def clone(self) -> "_State":
        return _State(dict(self.remaining), dict(self.applied), dict(self.credited), dict(self.written_off),
                      list(self.receipts), list(self.credits), list(self.warnings))


def _by_date(invoices) -> list:
    return sorted(invoices, key=lambda inv: (inv.invoice_date, inv.invoice_id))


def _open_invoices(state: _State, ev: Evidence, customer: str, date: str, exclude=()) -> list:
    """The customer's invoices that exist at `date` and carry a balance, by
    the published `(invoice_date, invoice_id)` key."""
    return _by_date(inv for inv in ev.invoices
                    if inv.customer == customer and inv.invoice_date <= date
                    and state.remaining[inv.invoice_id] > 0 and inv.invoice_id not in exclude)


def _reference_tokens(reference: str) -> list:
    out = []
    for token in _INVOICE_TOKEN.findall(reference):
        if token not in out:
            out.append(token)
    return out


def _credit(state: _State, cn: CreditNote, ev: Evidence, strategy: Strategy, validate: bool) -> None:
    if strategy.credit == "ignore":
        return
    inv = ev.invoice(cn.invoice_id)
    if validate:
        if inv is None:
            raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, f"{cn.credit_note_id} names unknown {cn.invoice_id}")
        if inv.customer != cn.customer:
            raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                          f"{cn.credit_note_id} ({cn.customer}) names {cn.invoice_id}, which is {inv.customer}'s")
        if inv.invoice_date > cn.date:
            raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                          f"{cn.credit_note_id} dated {cn.date} names {cn.invoice_id}, raised {inv.invoice_date}")
    applied: list = []
    left = cn.gross
    if inv is not None and inv.customer == cn.customer and inv.invoice_date <= cn.date:
        # A paid invoice takes none of it: its whole amount routes as excess.
        take = min(left, state.remaining[inv.invoice_id])
        if take > 0:
            applied.append((inv.invoice_id, take))
            state.remaining[inv.invoice_id] -= take
            state.credited[inv.invoice_id] += take
            left -= take
    for other in _open_invoices(state, ev, cn.customer, cn.date, exclude=(cn.invoice_id,)):
        if left <= 0:
            break
        take = min(left, state.remaining[other.invoice_id])
        applied.append((other.invoice_id, take))
        state.remaining[other.invoice_id] -= take
        state.credited[other.invoice_id] += take
        left -= take
    state.credits.append(CreditApplication(cn.credit_note_id, cn.date, cn.customer, cn.gross, tuple(applied), left))


def _pay(state: _State, invoice_id: str, amount: Decimal, applied: list) -> None:
    if amount <= 0:
        return
    applied.append((invoice_id, amount))
    state.remaining[invoice_id] -= amount
    state.applied[invoice_id] += amount


def _adviced(state: _State, receipt: Receipt, date: str, advice: Advice, ev: Evidence, strategy: Strategy,
             validate: bool) -> None:
    groups: dict = {}
    for line in advice.lines:
        groups.setdefault(line.invoice_id, []).append(line)
    applied: list = []
    written_off: list = []
    cash_left = receipt.amount
    paid_total = _ZERO
    for invoice_id, lines in groups.items():
        inv = ev.invoice(invoice_id)
        paid = sum((line.amount_paid for line in lines), _ZERO)
        deduction = sum((line.deduction for line in lines), _ZERO)
        settles = any(line.settles for line in lines)
        label = f"{advice.remittance_id} line on {invoice_id}"
        if validate:
            if inv is None:
                raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, f"{label}: unknown invoice")
            if inv.customer != receipt.customer:
                raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                              f"{label}: {invoice_id} is {inv.customer}'s, the payment is {receipt.customer}'s")
            if inv.invoice_date > date:
                raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                              f"{label}: {invoice_id} is raised {inv.invoice_date}, after the application date "
                              f"{date}")
            for line in lines:
                if line.deduction > 0 and not line.settles:
                    raise Refusal(REFUSE_LINE_CONTRADICTS_REGISTER,
                                  f"{label} claims a deduction of {_money(line.deduction)} without settling")
            open_ = state.remaining[invoice_id]
            if open_ == 0:
                if paid > 0 or deduction > 0:
                    raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, f"{label}: {invoice_id} is already closed")
                state.warnings.append(f"{WARN_LINE_ON_ZERO_BALANCE}: {label} names an invoice with no balance")
            if paid > open_:
                raise Refusal(REFUSE_LINE_CONTRADICTS_REGISTER,
                              f"{label} pays {_money(paid)} against an open balance of {_money(open_)} at {date}")
            if settles and paid + deduction != open_:
                raise Refusal(REFUSE_LINE_CONTRADICTS_REGISTER,
                              f"{label} settles with {_money(paid)} paid and {_money(deduction)} deducted, which is "
                              f"not the open balance {_money(open_)} at {date}")
        elif inv is None or inv.customer != receipt.customer or inv.invoice_date > date:
            continue
        paid_total += paid
        if paid == 0 and deduction == 0 and not settles:
            continue                                   # an informational statement of dispute
        take = paid if validate else min(paid, state.remaining[invoice_id], cash_left)
        _pay(state, invoice_id, take, applied)
        cash_left -= take
        if settles and deduction > 0:
            if strategy.writeoff == "tolerance":
                write = deduction <= SHORT_PAY_TOLERANCE
            else:
                write = strategy.writeoff == "all"
            if write:
                shortfall = min(deduction, state.remaining[invoice_id])
                if shortfall > 0:
                    written_off.append((invoice_id, shortfall))
                    state.remaining[invoice_id] -= shortfall
                    state.written_off[invoice_id] += shortfall
                if validate and deduction == SHORT_PAY_TOLERANCE:
                    state.warnings.append(f"{WARN_DEDUCTION_AT_TOLERANCE}: {label} claims exactly "
                                          f"{_money(SHORT_PAY_TOLERANCE)}")
    if validate and paid_total > advice.payment_amount:
        raise Refusal(REFUSE_LINE_CONTRADICTS_REGISTER,
                      f"{advice.remittance_id}'s lines total {_money(paid_total)}, above its payment of "
                      f"{_money(advice.payment_amount)}")
    # The residue the advice does not name is unapplied; rungs (2) and (3)
    # are not run for it.
    state.receipts.append(ReceiptApplication(receipt.receipt_id, date, receipt.customer, receipt.amount,
                                             tuple(applied), tuple(written_off), cash_left, ("advice",),
                                             advice.remittance_id))


def _unadviced(state: _State, receipt: Receipt, date: str, ev: Evidence, strategy: Strategy,
               validate: bool) -> list:
    """Returns the states this receipt leads to — several for amount-only."""
    mode = strategy.unadviced
    customer = receipt.customer
    if mode == "hold":
        state.receipts.append(ReceiptApplication(receipt.receipt_id, date, customer, receipt.amount, (), (),
                                                 receipt.amount, ("held",), ""))
        return [state]
    if mode == "amount":
        open_ = _open_invoices(state, ev, customer, date)
        subsets = [combo for size in range(1, len(open_) + 1) for combo in itertools.combinations(open_, size)
                   if sum((state.remaining[inv.invoice_id] for inv in combo), _ZERO) == receipt.amount]
        if subsets:
            out = []
            for combo in subsets:
                branch = state.clone()
                applied: list = []
                for inv in combo:
                    _pay(branch, inv.invoice_id, branch.remaining[inv.invoice_id], applied)
                branch.receipts.append(ReceiptApplication(receipt.receipt_id, date, customer, receipt.amount,
                                                          tuple(applied), (), _ZERO, ("exact_amount",), ""))
                out.append(branch)
            return out
        mode = "oldest"
    applied = []
    rungs: list = []
    cash_left = receipt.amount
    if mode in ("policy", "printed", "number"):
        named = []
        for token in _reference_tokens(receipt.reference):
            inv = ev.invoice(token)
            label = f"statement reference {receipt.reference!r} of {receipt.receipt_id}"
            if validate:
                if inv is None:
                    raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, f"{label} names unknown {token}")
                if inv.customer != customer:
                    raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                                  f"{label} names {token}, which is {inv.customer}'s")
                if inv.invoice_date > date:
                    raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                                  f"{label} names {token}, raised {inv.invoice_date}, after {date}")
                if state.remaining[token] <= 0:
                    raise Refusal(REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, f"{label} names {token}, already closed")
            elif inv is None or inv.customer != customer or inv.invoice_date > date:
                continue
            named.append(inv)
        if mode == "policy":
            named = _by_date(named)
        elif mode == "number":
            named = sorted(named, key=lambda inv: inv.invoice_id)
        if named:
            rungs.append("reference")
        for inv in named:
            take = min(cash_left, state.remaining[inv.invoice_id])
            _pay(state, inv.invoice_id, take, applied)
            cash_left -= take
    if cash_left > 0:
        remainder = _open_invoices(state, ev, customer, date)
        if remainder:
            rungs.append("oldest_first")
        for inv in remainder:
            if cash_left <= 0:
                break
            take = min(cash_left, state.remaining[inv.invoice_id])
            _pay(state, inv.invoice_id, take, applied)
            cash_left -= take
    state.receipts.append(ReceiptApplication(receipt.receipt_id, date, customer, receipt.amount, tuple(applied),
                                             (), cash_left, tuple(rungs) or ("none",), ""))
    return [state]


def _events(ev: Evidence, dates: dict) -> list:
    """(date, kind, order, item): credit notes before receipts on one date,
    receipts in statement order."""
    events = [(cn.date, 0, cn.index, cn) for cn in ev.credit_notes]
    events += [(dates.get(r.receipt_id, r.date), 1, r.index, r) for r in ev.receipts]
    return sorted(events, key=lambda e: e[:3])


def _finish(state: _State, ev: Evidence) -> Application:
    rows = tuple(InvoiceRow(inv.invoice_id, inv.customer, inv.period_basis, state.applied[inv.invoice_id],
                            state.credited[inv.invoice_id], state.written_off[inv.invoice_id],
                            state.remaining[inv.invoice_id])
                 for inv in sorted(ev.invoices, key=lambda inv: inv.invoice_id))
    unapplied = (sum((r.unapplied for r in state.receipts), _ZERO)
                 + sum((c.unapplied for c in state.credits), _ZERO))
    closing = sum((row.remaining for row in rows), _ZERO) - unapplied
    return Application(tuple(state.receipts), tuple(state.credits), rows, closing, ev.opening_ar,
                       ev.warnings + tuple(state.warnings))


def _run(ev: Evidence, strategy: Strategy, *, validate: bool, dates: dict | None = None) -> list:
    """Fold the evidence under a strategy; a list of readings, one for the
    policy and every non-branching baseline."""
    zero = {inv.invoice_id: _ZERO for inv in ev.invoices}
    states = [_State({inv.invoice_id: inv.period_basis for inv in ev.invoices}, dict(zero), dict(zero),
                     dict(zero))]
    for date, kind, _order, item in _events(ev, dates or {}):
        if kind == 0:
            for state in states:
                _credit(state, item, ev, strategy, validate)
            continue
        advice = ev.advice_for(item) if strategy.adviced == "advice" else None
        next_states = []
        for state in states:
            if advice is not None:
                _adviced(state, item, date, advice, ev, strategy, validate)
                next_states.append(state)
            else:
                next_states.extend(_unadviced(state, item, date, ev, strategy, validate))
        states = next_states
        if len(states) > MAX_BASELINE_READINGS:
            raise ValueError(f"more than {MAX_BASELINE_READINGS} readings; the evidence is not a fixture")
    return [_finish(state, ev) for state in states]


# --------------------------------------------------------------------------
# the fold
# --------------------------------------------------------------------------

def fold(public: dict, *, bank_account: str | None = None, period_start: str | None = None,
         period_end: str | None = None) -> Application:
    """The application the public evidence forces, or a `Refusal`.

    After the fold on the bank dates, the same fold is run once more with
    every adviced receipt on its advice's `remittance_date` (a cheque's
    advice carries the cheque date); a line that moves, or a refusal that
    appears only then, is U5 — the truth must not depend on which of two
    public dates a reader picks.
    """
    ev = read_evidence(public, bank_account=bank_account, period_start=period_start, period_end=period_end)
    app = _run(ev, POLICY, validate=True)[0]
    alternative = {}
    for receipt in ev.receipts:
        advice = ev.advice_for(receipt)
        if advice is not None and advice.remittance_date != receipt.date:
            alternative[receipt.receipt_id] = advice.remittance_date
    if alternative:
        try:
            redated = _run(ev, POLICY, validate=True, dates=alternative)[0]
        except Refusal as exc:
            raise Refusal(REFUSE_ORDER_SENSITIVE,
                          f"re-run with receipts on their remittance dates refuses: {exc}") from exc
        if application_key(redated) != application_key(app):
            moved = _differences(app, redated)
            raise Refusal(REFUSE_ORDER_SENSITIVE,
                          f"re-run with receipts on their remittance dates changes: {moved}")
    return app


def _differences(a: Application, b: Application) -> str:
    left = {k: v for k, v in _flat(a)}
    right = {k: v for k, v in _flat(b)}
    moved = sorted(k for k in set(left) | set(right) if left.get(k) != right.get(k))
    return ", ".join(f"{k} {left.get(k)} -> {right.get(k)}" for k in moved[:6])


def _flat(app: Application):
    for r in app.receipts:
        yield f"receipt {r.receipt_id}", (tuple(sorted(r.applied)), tuple(sorted(r.written_off)), r.unapplied)
    for c in app.credit_notes:
        yield f"credit note {c.credit_note_id}", (tuple(sorted(c.applied)), c.unapplied)
    for w in app.register:
        yield f"row {w.invoice_id}", (w.applied_total, w.credited, w.written_off, w.remaining)


# --------------------------------------------------------------------------
# gate (o): the named baselines
# --------------------------------------------------------------------------

def _any_unadviced(ev: Evidence) -> bool:
    return any(r.receipt_id not in ev.bindings for r in ev.receipts)


def _any_multi_reference(ev: Evidence) -> bool:
    return any(r.receipt_id not in ev.bindings and len(_reference_tokens(r.reference)) >= 2 for r in ev.receipts)


def _any_credit(ev: Evidence) -> bool:
    return bool(ev.credit_notes)


def _any_deduction(ev: Evidence) -> bool:
    bound = set(ev.bindings.values())
    return any(line.deduction > 0 for a in ev.advices if a.remittance_id in bound for line in a.lines)


def _always(ev: Evidence) -> bool:
    return True


@dataclass(frozen=True)
class Baseline:
    name: str
    strategy: Strategy
    admitted_when: object            # Evidence -> bool
    diagnostic: bool = False
    description: str = ""


#: The refusable set (spec section 5, gate (o)), in the order the spec names
#: them, then the one diagnostic reading.
BASELINES = (
    Baseline("amount_only", Strategy(adviced="ignore", unadviced="amount"), _always,
             description="every exact subset of the payer's open balances is a reading; none, oldest first; "
                         "advice and reference ignored"),
    Baseline("oldest_first", Strategy(adviced="ignore", unadviced="oldest"), _always,
             description="the payer's open invoices oldest first; advice and reference ignored"),
    Baseline("mixed_amount_only", Strategy(unadviced="amount"), _any_unadviced,
             description="advices honoured, then amount-only for the receipts without one"),
    Baseline("mixed_oldest_first", Strategy(unadviced="oldest"), _any_unadviced,
             description="advices honoured, then oldest-first for the receipts without one"),
    Baseline("hold_on_account", Strategy(unadviced="hold"), _any_unadviced,
             description="advices honoured; a receipt without one is held unapplied"),
    Baseline("printed_order", Strategy(unadviced="printed"), _any_multi_reference,
             description="advices honoured; the reference consumed in its printed order"),
    Baseline("credit_ignored", Strategy(credit="ignore"), _any_credit,
             description="the policy fold with credit notes left out of the register"),
    Baseline("write_off_everything", Strategy(writeoff="all"), _any_deduction,
             description="every claimed deduction written off, whatever its size"),
    Baseline("write_off_nothing", Strategy(writeoff="none"), _any_deduction,
             description="no deduction written off"),
    Baseline("number_order", Strategy(unadviced="number"), _any_multi_reference, diagnostic=True,
             description="advices honoured; the reference consumed in invoice-number order — coincides with "
                         "invoice-date order whenever the two agree, so it is reported, never refused"),
)
BASELINE_NAMES = tuple(b.name for b in BASELINES if not b.diagnostic)
DIAGNOSTIC_BASELINE_NAMES = tuple(b.name for b in BASELINES if b.diagnostic)


@dataclass(frozen=True)
class BaselineResult:
    name: str
    admitted: bool
    diagnostic: bool
    readings: tuple                  # every Application the baseline enumerates; the first is the fixed tie-break's
    reaches_truth: object            # True / False, None when not admitted


def baseline_readings(public: dict, name: str, **kw) -> tuple:
    """Every reading the named baseline enumerates, the first being what the
    fixed tie-breaking implementation answers (subsets by size, then the
    published invoice order; sibling branches after it)."""
    baseline = next(b for b in BASELINES if b.name == name)
    ev = read_evidence(public, **kw)
    return tuple(_run(ev, baseline.strategy, validate=False))


def baseline_report(public: dict, truth: Application | None = None, **kw) -> dict:
    """Gate (o): for each baseline the evidence admits, whether ANY of its
    readings equals `truth` (the policy fold by default) on every receipt
    line, credit application and register row."""
    ev = read_evidence(public, **kw)
    if truth is None:
        truth = fold(public, **kw)
    target = application_key(truth)
    report = {}
    for baseline in BASELINES:
        if not baseline.admitted_when(ev):
            report[baseline.name] = BaselineResult(baseline.name, False, baseline.diagnostic, (), None)
            continue
        readings = tuple(_run(ev, baseline.strategy, validate=False))
        reaches = any(application_key(reading) == target for reading in readings)
        report[baseline.name] = BaselineResult(baseline.name, True, baseline.diagnostic, readings, reaches)
    return report


def refused_by(report: dict) -> tuple:
    """The admitted, non-diagnostic baselines that reach the truth. A case
    any of them reaches is refused."""
    return tuple(name for name, result in report.items()
                 if result.admitted and not result.diagnostic and result.reaches_truth)


__all__ = [
    "APPLICATION_SCHEMA", "CASH_APPLICATION_VERSION", "EXTRA_PUBLIC_FILES", "SHORT_PAY_TOLERANCE",
    "REFUSALS", "Refusal", "PublicOnly",
    "Evidence", "Invoice", "Advice", "AdviceLine", "Receipt", "CreditNote",
    "Application", "ReceiptApplication", "CreditApplication", "InvoiceRow",
    "read_evidence", "fold", "application_key", "document", "document_text",
    "Strategy", "POLICY", "Baseline", "BASELINES", "BASELINE_NAMES", "DIAGNOSTIC_BASELINE_NAMES",
    "BaselineResult", "baseline_readings", "baseline_report", "refused_by",
]
