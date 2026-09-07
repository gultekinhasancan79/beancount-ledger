"""The accounting policy: facts in, recognitions and bank movements out.

This is the only place a debit/credit vector is ever formed. The world
authors "a sale of 4,000 net at 20% tax with cost 2,600"; this module says
that means AR 4,800 / Sales −4,000 / Tax −800 and COGS 2,600 / Inventory
−2,600, on the authority of the policy document the agent also reads
(`POLICY_SECTIONS` names the section each rule implements, and the world
check asserts those sections exist in the text the agent is given).

Every rule is total over its event kind and pure. Nothing here reads a
target, a mutation or a view: the policy does not know which recognitions
the task will omit, so it cannot shape them to fit.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from decimal import Decimal

from .schema import (
    BankFee,
    CustomerReceipt,
    ExpensePayment,
    Prepayment,
    Purchase,
    Rail,
    Sale,
    VendorPayment,
    World,
)

ACCOUNTING_POLICY_VERSION = 1

# Which section of the policy document each rule rests on. Checked against
# the world's policy text so a rule cannot outlive its stated authority.
POLICY_SECTIONS = {
    "bank_fee": "## Bank service charges",
    "customer_receipt": "## Customer receipts",
    # One section governs both money-out rules, because the section is what
    # tells them apart: a supplier whose purchases are booked to an asset
    # raised a payable when the goods arrived, so `vendor_payment` settles
    # `payables`; a supplier whose purchases are booked to an expense raised
    # none, so `expense_payment` posts to that supplier's own account. The
    # master file's `default_account` is the input to that test, never the
    # answer to "where does the payment land".
    "vendor_payment": "## Payments to suppliers",
    "expense_payment": "## Payments to suppliers",
    "outstanding_cheque": "## Outstanding checks",
    "prepayment": "## Prepayments",
    "sale": "## Sales tax",
    "plug": "## Suspense accounts",
}

# Account roles the policy needs by name. A world declares which chart
# account plays each role; the policy never hard-codes a chart name.
ROLES = ("receivables", "inventory", "prepayments", "payables", "sales_tax", "sales", "cogs", "bank_fees", "opening_equity")


@dataclass(frozen=True)
class Leg:
    account: str
    amount: Decimal


@dataclass(frozen=True)
class AccountingRecognition:
    """What the books should say about one event. `sequence` orders the
    recognitions of one event (a sale's revenue before its cost); across
    events the date orders them and nothing else does."""

    id: str
    event_id: str
    date: str
    payee: str
    narration: str
    legs: tuple             # (Leg, ...) debit first, as the books print them
    rule: str
    sequence: int = 0

    @property
    def balanced(self) -> bool:
        return sum((l.amount for l in self.legs), Decimal("0")) == 0

    def net_on(self, account: str) -> Decimal:
        return sum((l.amount for l in self.legs if l.account == account), Decimal("0"))


@dataclass(frozen=True)
class BankMovement:
    """What the bank saw about one event, on the day it saw it."""

    id: str
    event_id: str
    bank_account: str
    cleared_on: str
    amount: Decimal         # signed on the bank account
    description: str
    reference: str
    rail: Rail


@dataclass(frozen=True)
class Roles:
    receivables: str
    inventory: str
    prepayments: str
    payables: str
    sales_tax: str
    sales: str
    cogs: str
    bank_fees: str
    opening_equity: str


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


# --------------------------------------------------------------------------
# recognitions
# --------------------------------------------------------------------------

def recognitions_of(world: World, roles: Roles, event) -> tuple[AccountingRecognition, ...]:
    bank = world.bank_account
    if isinstance(event, Sale):
        party = world.party(event.party_id)
        tax = _q(event.net * event.tax_rate)
        gross = _q(event.net + tax)
        sale = AccountingRecognition(
            f"rec:{event.id.split(':', 1)[1]}", event.id, event.date, party.name, event.memo,
            (Leg(roles.receivables, gross), Leg(roles.sales, -event.net), Leg(roles.sales_tax, -tax)), "sale", 0)
        cost = AccountingRecognition(
            f"rec:{event.id.split(':', 1)[1]}-cost", event.id, event.date, party.name, event.cost_memo,
            (Leg(roles.cogs, event.cost), Leg(roles.inventory, -event.cost)), "sale", 1)
        return (sale, cost)
    if isinstance(event, Purchase):
        party = world.party(event.party_id)
        return (AccountingRecognition(
            f"rec:{event.id.split(':', 1)[1]}", event.id, event.date, party.name, event.memo,
            (Leg(roles.inventory, event.amount), Leg(roles.payables, -event.amount)), "purchase"),)
    if isinstance(event, CustomerReceipt):
        party = world.party(event.party_id)
        return (AccountingRecognition(
            f"rec:{event.id.split(':', 1)[1]}", event.id, event.date, party.name, event.memo,
            (Leg(bank, event.amount), Leg(roles.receivables, -event.amount)), "customer_receipt"),)
    if isinstance(event, VendorPayment):
        party = world.party(event.party_id)
        return (AccountingRecognition(
            f"rec:{event.id.split(':', 1)[1]}", event.id, event.date, party.name, event.memo,
            (Leg(roles.payables, event.amount), Leg(bank, -event.amount)), "vendor_payment"),)
    if isinstance(event, ExpensePayment):
        party = world.party(event.party_id)
        return (AccountingRecognition(
            f"rec:{event.id.split(':', 1)[1]}", event.id, event.date, party.name, event.memo,
            (Leg(party.default_account, event.amount), Leg(bank, -event.amount)), "expense_payment"),)
    if isinstance(event, Prepayment):
        party = world.party(event.party_id)
        return (AccountingRecognition(
            f"rec:{event.id.split(':', 1)[1]}", event.id, event.date, party.name, event.memo,
            (Leg(roles.prepayments, event.amount), Leg(bank, -event.amount)), "prepayment"),)
    if isinstance(event, BankFee):
        party = world.party(world.bank_party_id)
        return (AccountingRecognition(
            f"rec:{event.id.split(':', 1)[1]}", event.id, event.date, party.name, event.memo,
            (Leg(roles.bank_fees, event.amount), Leg(bank, -event.amount)), "bank_fee"),)
    raise TypeError(f"no accounting rule for {type(event).__name__}")


def opening_recognition(world: World, roles: Roles, bank_opening_balance: Decimal) -> AccountingRecognition:
    """The carry-forward entry. The bank leg is the prior period's derived
    close; the equity leg balances; nothing is authored twice."""
    carried = tuple(Leg(a, v) for a, v in world.opening.carried)
    legs = (Leg(world.bank_account, bank_opening_balance),) + carried
    equity = -sum((l.amount for l in legs), Decimal("0"))
    legs = legs + (Leg(roles.opening_equity, equity),)
    year, month = (int(x) for x in world.opening.as_of.split("-")[:2])
    prior = calendar.month_name[12 if month == 1 else month - 1]
    return AccountingRecognition(
        "rec:opening", "event:opening", world.opening.as_of, "Opening balance",
        f"Carried forward from {prior} close", legs, "opening")


# --------------------------------------------------------------------------
# bank movements
# --------------------------------------------------------------------------

def movement_of(world: World, event) -> BankMovement | None:
    """The bank's row for an event, or None when the bank saw nothing."""
    if isinstance(event, BankFee):
        # The bank prints its own description of its own charge: the memo in
        # capitals (a wire fee is not a "monthly account service charge").
        return BankMovement(f"mov:{event.id.split(':', 1)[1]}", event.id, world.bank_account, event.date,
                            -event.amount, event.memo.upper(), "", Rail.BANK_INITIATED)
    settlement = getattr(event, "settlement", None)
    if settlement is None:
        return None
    party = world.party(event.party_id).name.upper()
    reference = ""
    # An ACH row quotes the invoice it settles; an event with no invoice
    # (ExpensePayment, Prepayment) is a plain transfer and quotes nothing,
    # exactly as a card row does. Reading `event.invoice_id` unconditionally
    # here refused a schema-valid event at movement time.
    invoice_id = getattr(event, "invoice_id", None)
    if settlement.rail is Rail.ACH_IN:
        description = f"ACH IN {party}"
        reference = world.document(invoice_id).number if invoice_id else ""
        amount = event.amount
    elif settlement.rail is Rail.ACH_OUT:
        description = f"ACH OUT {party}"
        reference = world.document(invoice_id).number if invoice_id else ""
        amount = -event.amount
    elif settlement.rail is Rail.CHEQUE:
        number = world.document(settlement.cheque_id).number
        description = f"CHECK {number} {party}"
        reference = number
        amount = event.amount if isinstance(event, CustomerReceipt) else -event.amount
    elif settlement.rail is Rail.CARD:
        description = f"DEBIT CARD {party}"
        amount = -event.amount
    else:
        raise TypeError(f"no bank wording for rail {settlement.rail}")
    return BankMovement(f"mov:{event.id.split(':', 1)[1]}", event.id, world.bank_account, settlement.cleared_on,
                        amount, description, reference, settlement.rail)
