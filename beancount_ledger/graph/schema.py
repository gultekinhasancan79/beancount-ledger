"""The canonical world graph: irreducible economic facts, typed.

Everything the agent reads, everything the scorer expects and everything the
tests compare against is a *derivation* of the nodes in this module. Nothing
here is an answer: no closing balance, no posting vector, no target delta.
What is authored is what a bookkeeper would have to be told — a sale of a
given net amount at a given tax rate, a receipt of a given amount against a
given invoice on a given rail, a cheque that the bank cleared on a given
day — and the accounting policy (`policy.py`) turns those facts into
recognitions, the bank's view into movements, and the projector
(`project.py`) into documents.

Three concepts are kept structurally apart, because the outstanding-check
policy proves they are different things:

    EconomicEvent          something happened (a typed fact)
    AccountingRecognition  what the books should say about it (derived)
    BankMovement           what the bank saw about it, and when (derived)

A cheque issued on the 28th is an accounting recognition on the 28th and a
bank movement on the day it clears; that the statement does not show it by
the cut-off is a timing difference, not an omission. A fee the bank applied
is a bank movement on the 30th and a recognition the books owe; that the
opening ledger lacks it is the task. Neither is a Boolean visibility flag,
and no single "transaction node" appears or disappears from every view.

Identity is explicit (`id` fields), never positional, and node order in the
world is not semantic: the canonical form sorts by id, and two worlds built
in different insertion orders have one digest. Where order IS semantic
(chart order, master-file order, the two recognitions of one sale) it is a
declared field, not a list position.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from enum import Enum

from ..task import PLUG_PATTERNS

GRAPH_SCHEMA_VERSION = 1

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID = re.compile(r"^[a-z]+:[a-z0-9][a-z0-9\-]*$")


class AccountKind(Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    INCOME = "income"
    EXPENSE = "expense"
    EQUITY = "equity"


class PartyRole(Enum):
    CUSTOMER = "customer"
    VENDOR = "vendor"
    BANK = "bank"


class DocumentKind(Enum):
    SALES_INVOICE = "sales_invoice"
    PURCHASE_INVOICE = "purchase_invoice"
    CHEQUE = "cheque"


class Rail(Enum):
    """How money moved, which decides what the bank can print about it."""

    ACH_IN = "ach_in"
    ACH_OUT = "ach_out"
    CHEQUE = "cheque"
    CARD = "card"
    BANK_INITIATED = "bank_initiated"


# --------------------------------------------------------------------------
# entities
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Account:
    name: str
    kind: AccountKind
    description: str
    opened: str
    code: int                     # chart order: semantic, therefore declared


@dataclass(frozen=True)
class Party:
    id: str
    name: str
    role: PartyRole
    number: int                   # master-file order: semantic, therefore declared
    terms: str | None = None
    default_account: str | None = None


@dataclass(frozen=True)
class Document:
    id: str
    kind: DocumentKind
    number: str
    party_id: str
    issued: str
    gross: Decimal | None = None  # invoices carry a gross; cheques carry none


@dataclass(frozen=True)
class Settlement:
    """How and when the bank saw the money. `cleared_on` is a fact the bank
    supplies; there is no default, because an unstated clearing date is how
    a cheque silently becomes cleared-on-issue."""

    rail: Rail
    cleared_on: str
    cheque_id: str | None = None


# --------------------------------------------------------------------------
# economic events: the authored facts
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Sale:
    id: str
    date: str
    party_id: str
    invoice_id: str
    net: Decimal
    tax_rate: Decimal
    cost: Decimal
    memo: str
    cost_memo: str


@dataclass(frozen=True)
class Purchase:
    """Goods for resale received on credit."""

    id: str
    date: str
    party_id: str
    invoice_id: str
    amount: Decimal
    memo: str


@dataclass(frozen=True)
class CustomerReceipt:
    id: str
    date: str
    party_id: str
    invoice_id: str
    amount: Decimal
    settlement: Settlement
    memo: str


@dataclass(frozen=True)
class VendorPayment:
    id: str
    date: str
    party_id: str
    invoice_id: str
    amount: Decimal
    settlement: Settlement
    memo: str


@dataclass(frozen=True)
class ExpensePayment:
    """A payment to a vendor whose default account is an expense."""

    id: str
    date: str
    party_id: str
    amount: Decimal
    settlement: Settlement
    memo: str


@dataclass(frozen=True)
class Prepayment:
    """A payment for a later period: an asset until that period, by policy."""

    id: str
    date: str
    party_id: str
    amount: Decimal
    settlement: Settlement
    covers: str                   # the period the payment relates to, YYYY-MM
    memo: str


@dataclass(frozen=True)
class BankFee:
    id: str
    date: str
    amount: Decimal
    memo: str


Event = Sale | Purchase | CustomerReceipt | VendorPayment | ExpensePayment | Prepayment | BankFee
EVENT_KINDS = (Sale, Purchase, CustomerReceipt, VendorPayment, ExpensePayment, Prepayment, BankFee)


@dataclass(frozen=True)
class BankOpening:
    """The bank's balance at the start of the earliest modelled period. The
    one authored bank figure; every later opening is a fold of movements."""

    as_of: str
    balance: Decimal


@dataclass(frozen=True)
class OpeningPosition:
    """Non-bank balances carried into the task period. Authored, because
    the history that produced them is not modelled; the bank balance is
    NOT here — it is derived from the prior period's movements — and the
    equity figure is the balancing amount, never written down."""

    as_of: str
    carried: tuple               # ((account, Decimal), ...)


@dataclass(frozen=True)
class World:
    id: str
    title: str
    currency: str
    bank_account: str
    bank_party_id: str
    accounts: tuple
    parties: tuple
    documents: tuple
    bank_opening: BankOpening
    opening: OpeningPosition
    events: tuple
    roles: tuple                  # ((role, account name), ...): which chart account plays each policy role
    policy_text: str
    schema_version: int = GRAPH_SCHEMA_VERSION

    # lookups ----------------------------------------------------------
    def account(self, name: str) -> Account:
        return next(a for a in self.accounts if a.name == name)

    def party(self, party_id: str) -> Party:
        return next(p for p in self.parties if p.id == party_id)

    def document(self, document_id: str) -> Document:
        return next(d for d in self.documents if d.id == document_id)

    def event(self, event_id: str):
        return next(e for e in self.events if e.id == event_id)


# --------------------------------------------------------------------------
# canonical form
# --------------------------------------------------------------------------

def _plain(value):
    """A dataclass/enum/Decimal tree as canonical-encodable data. Node
    tuples whose order is not semantic are sorted by id here, so the graph
    digest is a function of the facts and not of insertion order."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        out = {"__type__": type(value).__name__}
        for f in fields(value):
            out[f.name] = _plain(getattr(value, f.name))
        return out
    if isinstance(value, (list, tuple)):
        items = [_plain(v) for v in value]
        if items and all(isinstance(i, dict) and ("id" in i or "name" in i) for i in items):
            items.sort(key=lambda i: str(i.get("id", i.get("name"))))
        elif items and all(isinstance(i, list) and i and isinstance(i[0], str) for i in items):
            items.sort(key=lambda i: i[0])          # (key, value) pairs: roles, carried positions
        return items
    return value


def world_canonical(world: World) -> dict:
    return _plain(world)


# --------------------------------------------------------------------------
# structural checks: a generator defect, never a submission defect
# --------------------------------------------------------------------------

def _is_nfc(s: str) -> bool:
    return unicodedata.normalize("NFC", s) == s


def _money(value) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value == value.quantize(Decimal("0.01"))


def check_world(world: World) -> list[str]:
    """Referential integrity, canonical strings and numbers, kind requirements.
    Returns every problem; an empty list is the only acceptable answer."""
    problems: list[str] = []
    ids: dict[str, str] = {}

    def claim(node_id: str, what: str):
        if not isinstance(node_id, str) or not _ID.match(node_id):
            problems.append(f"{what}: id {node_id!r} is not of the form kind:slug")
        elif node_id in ids:
            problems.append(f"{what}: id {node_id} already names a {ids[node_id]}")
        else:
            ids[node_id] = what

    def strings(node, what: str):
        for f in fields(node):
            v = getattr(node, f.name)
            if isinstance(v, str) and not _is_nfc(v):
                problems.append(f"{what}.{f.name}: string is not NFC")
            if isinstance(v, str) and f.name in ("date", "opened", "issued", "as_of", "cleared_on") and not _DATE.match(v):
                problems.append(f"{what}.{f.name}: {v!r} is not an ISO date")
            if isinstance(v, Decimal) and not _money(v):
                problems.append(f"{what}.{f.name}: {v} is not a finite two-place amount")

    names = {a.name for a in world.accounts}
    if len(names) != len(world.accounts):
        problems.append("duplicate account names")
    if len({a.code for a in world.accounts}) != len(world.accounts):
        problems.append("duplicate account codes")
    for a in world.accounts:
        strings(a, f"account {a.name}")
        if PLUG_PATTERNS.search(a.name):
            problems.append(f"account {a.name} reads like a plug")
    if world.bank_account not in names:
        problems.append(f"bank account {world.bank_account} is not in the chart")
    elif world.account(world.bank_account).kind is not AccountKind.ASSET:
        problems.append("the bank account is not an asset")
    roles = dict(world.roles)
    from .policy import ROLES   # the policy declares what it needs; the world says which account plays it
    for role in ROLES:
        if role not in roles:
            problems.append(f"role {role!r} has no account")
        elif roles[role] not in names:
            problems.append(f"role {role!r} names {roles[role]}, which is not in the chart")
    if set(roles) - set(ROLES):
        problems.append(f"unknown roles {sorted(set(roles) - set(ROLES))}")
    if len(set(roles.values())) != len(roles):
        problems.append("two roles share one account")
    if roles.get("opening_equity") in names and world.account(roles["opening_equity"]).kind is not AccountKind.EQUITY:
        problems.append("the opening equity role is not an equity account")

    if len({p.number for p in world.parties}) != len(world.parties):
        problems.append("duplicate party numbers")
    for p in world.parties:
        claim(p.id, f"party {p.name}")
        strings(p, f"party {p.id}")
        if p.default_account is not None and p.default_account not in names:
            problems.append(f"party {p.id}: default account {p.default_account} is not in the chart")
    party_ids = {p.id for p in world.parties}
    if world.bank_party_id not in party_ids:
        problems.append("bank party is not a party")
    elif world.party(world.bank_party_id).role is not PartyRole.BANK:
        problems.append("bank party is not a bank")

    for d in world.documents:
        claim(d.id, f"document {d.number}")
        strings(d, f"document {d.id}")
        if d.party_id not in party_ids:
            problems.append(f"document {d.id}: party {d.party_id} unknown")
        if d.kind is DocumentKind.CHEQUE and d.gross is not None:
            problems.append(f"document {d.id}: a cheque carries no gross")
        if d.kind is not DocumentKind.CHEQUE and d.gross is None:
            problems.append(f"document {d.id}: an invoice needs a gross")
    doc_ids = {d.id for d in world.documents}

    strings(world.bank_opening, "bank opening")
    strings(world.opening, "opening position")
    for account, amount in world.opening.carried:
        if account not in names:
            problems.append(f"opening position: {account} is not in the chart")
        if account == world.bank_account:
            problems.append("opening position authors the bank balance; it is derived from the prior period")
        if not _money(amount):
            problems.append(f"opening position: {account} amount {amount} is not money")

    for e in world.events:
        what = f"event {getattr(e, 'id', '?')}"
        if not isinstance(e, EVENT_KINDS):
            problems.append(f"{what}: {type(e).__name__} is not an event kind")
            continue
        claim(e.id, what)
        strings(e, what)
        party_id = getattr(e, "party_id", None)
        if party_id is not None and party_id not in party_ids:
            problems.append(f"{what}: party {party_id} unknown")
        for attr in ("invoice_id",):
            doc = getattr(e, attr, None)
            if doc is not None:
                if doc not in doc_ids:
                    problems.append(f"{what}: document {doc} unknown")
                elif world.document(doc).party_id != party_id:
                    problems.append(f"{what}: document {doc} belongs to another party")
        amount = getattr(e, "amount", None)
        if amount is not None and amount <= 0:
            problems.append(f"{what}: amount must be positive; sign is the policy's job")
        settlement = getattr(e, "settlement", None)
        if settlement is not None:
            strings(settlement, f"{what}.settlement")
            if settlement.rail is Rail.CHEQUE and settlement.cheque_id is None:
                problems.append(f"{what}: a cheque settlement names its cheque")
            if settlement.rail is not Rail.CHEQUE and settlement.cheque_id is not None:
                problems.append(f"{what}: only a cheque settlement names a cheque")
            if settlement.cheque_id is not None:
                if settlement.cheque_id not in doc_ids:
                    problems.append(f"{what}: cheque {settlement.cheque_id} unknown")
                elif world.document(settlement.cheque_id).kind is not DocumentKind.CHEQUE:
                    problems.append(f"{what}: {settlement.cheque_id} is not a cheque")
            if settlement.cleared_on < e.date:
                problems.append(f"{what}: cleared before it happened")
            if isinstance(e, CustomerReceipt) and settlement.rail not in (Rail.ACH_IN, Rail.CHEQUE):
                problems.append(f"{what}: a customer receipt cannot arrive by {settlement.rail.value}")
            if isinstance(e, (VendorPayment, ExpensePayment, Prepayment)) and settlement.rail not in (Rail.ACH_OUT, Rail.CHEQUE, Rail.CARD):
                problems.append(f"{what}: a payment cannot leave by {settlement.rail.value}")
        if isinstance(e, Sale):
            if not (Decimal("0") <= e.tax_rate <= Decimal("1")):
                problems.append(f"{what}: tax rate {e.tax_rate} is not a rate")
            if e.net <= 0 or e.cost < 0:
                problems.append(f"{what}: net must be positive and cost non-negative")
            if world.document(e.invoice_id).kind is not DocumentKind.SALES_INVOICE if e.invoice_id in doc_ids else False:
                problems.append(f"{what}: {e.invoice_id} is not a sales invoice")
        if isinstance(e, (Purchase, VendorPayment)) and e.invoice_id in doc_ids \
                and world.document(e.invoice_id).kind is not DocumentKind.PURCHASE_INVOICE:
            problems.append(f"{what}: {e.invoice_id} is not a purchase invoice")
        if isinstance(e, CustomerReceipt) and e.invoice_id in doc_ids \
                and world.document(e.invoice_id).kind is not DocumentKind.SALES_INVOICE:
            problems.append(f"{what}: {e.invoice_id} is not a sales invoice")
        if isinstance(e, (ExpensePayment, Prepayment)) and party_id in party_ids:
            party = world.party(party_id)
            if party.role is not PartyRole.VENDOR or party.default_account is None:
                problems.append(f"{what}: {party_id} is not a vendor with a default account")
        if isinstance(e, Prepayment) and not re.match(r"^\d{4}-\d{2}$", e.covers):
            problems.append(f"{what}: covers {e.covers!r} is not YYYY-MM")
    return problems
