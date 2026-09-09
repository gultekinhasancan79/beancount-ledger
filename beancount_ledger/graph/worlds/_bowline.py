"""Bowline Marine Supply Co., April 2026: the facts the five cash-application
variants share.

The cash-application family (spec `cash_application_spec.md`) is FIVE
VARIANTS OF ONE COMPANY-MONTH, not five accounting environments: the chart,
the parties, the March archive, the open-item register the month opens on,
the first two receipts, the two in-month sales and the statement's non-target
rows are one set of facts, stated here once. Each `bowline_2026_04_cN.py`
adds the third receipt, the credit note and the mutation plan that make its
case, and nothing else.

This is the hand-reviewed layer: amounts, dates, counterparties, documents,
rails, clearing dates, remittance-advice lines as the customer wrote them.
Nothing derived is typed. No open balance, no register row, no write-off, no
closing balance appears here — the open-item register is a fold of the
invoices and the March receipts, the write-off is a consequence of an advice
line and the policy's tolerance, and the truth register `application/1`
scores against is derived in `graph/derive.py` from these facts alone.

The prompt is shared too, and deliberately says nothing about whether a
write-off is due, which invoices a receipt settled or how much cash is left
unapplied — the `_assurance.py` pattern: one instruction over five months
that differ only in their books.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..policy import SHORT_PAY_TOLERANCE
from ..project import Period
from ..schema import (
    Account,
    AccountKind as K,
    AppliedReceipt,
    BankFee,
    BankOpening,
    CustomerReceipt,
    Document,
    DocumentKind as DK,
    OpeningPosition,
    Party,
    PartyRole as R,
    Rail,
    ReceiptLine,
    Sale,
    Settlement,
    VendorPayment,
    World,
)

TITLE = "Bowline Marine Supply Co. - FY2026"
CURRENCY = "USD"
BANK_ACCOUNT = "Assets:Bank:Checking"
AR = "Assets:AR"
WRITE_OFFS = "Expenses:SmallBalanceWriteOffs"
TOLERANCE = f"{SHORT_PAY_TOLERANCE:.2f}"

PERIOD = Period("2026-04-01", "2026-04-30", "April 2026")

GANNET = "party:gannet-rigging"
SHEARWATER = "party:shearwater-bay"
NORTHSHORE = "party:northshore-chandlery"
BANK = "party:marram-bank"

POLICY_TEXT = f"""# Bowline Marine Supply Co. — Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, wire fees, returned
item fees) are recorded to `Expenses:BankFees` on the date the bank applies them.

## Customer receipts
Cash received from a customer reduces `{AR}`, for the amount and on the date
the bank shows. Which invoices the cash settled is not a question the ledger
answers: Bowline keeps one receivables control account and an open-item
register outside it, and the cash application section below says how a receipt
is applied in that register.

## Cash application
Bowline keeps one receivables control account, `{AR}`, and an open-item register
by invoice outside the ledger. A receipt is posted to `{AR}` for the amount and
on the date the bank shows, and applied in the register to invoices of the
paying customer in this order of authority: (1) the customer's remittance
advice, where one belongs to the payment — each line to the invoice it names
for the amount it states, and any part of the payment the advice does not name
is left unapplied rather than carried on to the rules below; (2) otherwise the
invoice numbers quoted in the statement reference, in invoice-date order, then
invoice number, each up to its open balance, any remainder following (3);
(3) otherwise the customer's open invoices oldest first by invoice date, then
invoice number, each up to its open balance. An advice belongs to a payment
when customer, payment reference and amount all agree; an advice that belongs
to no payment is not evidence for any payment. Cash that no open invoice
absorbs stays in `{AR}` as an unapplied credit **of that customer**, whose
ownership the register records; it is never income. That is this
reconciliation's convention for an aggregate control account, not a
financial-statement presentation rule. Applications run in date order; on one
date credit notes before receipts, receipts in statement order.

A receipt smaller than the invoice it is applied to leaves the balance open.
Where the advice marks an invoice settled and the shortfall — after combining
that advice's lines for that invoice — is `{TOLERANCE}` or less **for that
invoice on that receipt**, the shortfall is written off to `{WRITE_OFFS}` in a
separate entry dated with the receipt, payee the customer, and the invoice is
closed; above `{TOLERANCE}` nothing is written off and the shortfall remains
open. Nothing is written off without an advice marking the invoice settled.
This exercise authorises those expense write-offs **without a sales-tax
adjustment**; determining the tax treatment of a settlement discount is not
asked of the agent.

## Credit notes
A credit note reverses the sale and its tax on its date: `Income:Sales` net,
`Liabilities:SalesTax-Payable` tax, `{AR}` gross. It is applied to the invoice
it references up to that invoice's open balance on that date — if that invoice
is already paid, none of it lands there — any excess to the same customer's
other open invoices in invoice-date order, then invoice number, any remainder
held as an unapplied credit of that customer.

## Payments to suppliers
The `default_account` a supplier carries in the vendor master is where that
supplier's purchases are booked when they arrive. It is not where a payment to
that supplier lands. Where a supplier's purchases are booked to an asset
account, the goods were taken into that account when they were received and a
payable was raised for them at the same time, so cash paid to that supplier
afterwards settles the payable and is recorded to `Liabilities:AP`. Where a
supplier's purchases are booked to an expense account, no payable is raised:
the payment is the expense, and it is recorded to that supplier's own
`default_account` on the day it is paid, except where it is paid ahead of the
period it covers, which the prepayments section below governs.

## Outstanding checks
A check that has been issued and recorded in the ledger but has not cleared the
bank as at the statement cut-off date remains recorded. It is a timing
difference and is listed as an outstanding item in the reconciliation. It is
never removed or adjusted.

## Deposits in transit
Cash recorded as received in the ledger that does not appear on the bank
statement until after the cut-off date is likewise a timing difference and is
listed as an outstanding item.

## Dates
A customer receipt carries the date the bank shows the money moved, as the
cash application section says; the date on a customer's remittance advice or
check is evidence of what was paid and when the customer sent it, never the
posting date. Every other entry carries the date of the transaction — the day
a check was issued, an invoice was raised or a credit note was issued — never
the date the bank processed it. A ledger date that differs from the
statement's date for the same item is not an error and is not to be changed.

The bank processes a transaction on or after the day it happens, so for a
supplier movement the ledger date is never later than the statement's date for
the same item.

An item the books do not carry at all has no transaction date to keep. The
statement's date is then the only date in evidence, so an entry added for a
statement row the ledger is missing is posted on the date the bank shows.

## Matching the statement to the ledger
A statement row and a ledger entry of the same amount and the same
counterparty, dated within the clearing window for the rail the row names,
are the same transaction and are treated as one item — not as two that
happen to agree.

## Prepayments
Amounts paid before the period they relate to are recorded to
`Assets:Prepayments` and released to expense in the period they cover. Rent
paid in one month for the following month is a prepayment, not an expense of
the month it was paid.

## Sales tax
Bowline collects sales tax from customers at 8% on sales and owes it to the
state. Purchases of goods for resale are exempt, so no tax is recoverable on
the purchase side.

## Suspense accounts
Bowline does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
"""

#: The one instruction, shared by the five cases. It names the deliverables
#: and the evidence, and says nothing about what the books will turn out to
#: need: not whether a receipt is missing or mis-keyed, not whether anything
#: is written off, not how much cash is left unapplied.
PROMPT = (
    "The April checking account statement has arrived, together with the remittance advices the customers "
    "sent with their payments, the credit notes issued in the month and the open-item register the month "
    "opened on, and the month needs to be closed. Bring the ledger into agreement with the statement, "
    "following the bookkeeping policy, and write the corrected ledger back to ledger.beancount. Then record "
    "how the period's receipts and credit notes were applied under the policy — which invoices each one "
    "settled and for how much, whatever the policy writes off, whatever is left unapplied, and what each "
    "invoice has remaining — as cash_application.json through write_cash_application."
)

OPENED = "2026-01-01"

ACCOUNTS = (
    Account(BANK_ACCOUNT, K.ASSET, "Primary operating checking account held at Marram Community Bank", OPENED, 1000),
    Account(AR, K.ASSET, "Trade receivables from customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Goods held for resale", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Revenue from goods sold", OPENED, 4100),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account(WRITE_OFFS, K.EXPENSE, "Short payments within the cash application tolerance written off on receipt", OPENED, 5400),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party(GANNET, "Gannet Rigging Inc", R.CUSTOMER, 1, "net 30", AR),
    Party(SHEARWATER, "Shearwater Bay Charters LLC", R.CUSTOMER, 2, "net 30", AR),
    Party(NORTHSHORE, "Northshore Chandlery Supply", R.VENDOR, 3, "net 30", "Assets:Inventory"),
    Party(BANK, "Marram Community Bank", R.BANK, 4),
)

DOCUMENTS = (
    # sales invoices settled in March: closed before the period, so not in the register
    Document("doc:si-3097", DK.SALES_INVOICE, "SI-3097", GANNET, "2026-02-05", D("3640.00")),
    Document("doc:si-3099", DK.SALES_INVOICE, "SI-3099", SHEARWATER, "2026-02-20", D("2215.00")),
    # the four invoices open at 1 April; SI-3100 part-paid in March
    Document("doc:si-3100", DK.SALES_INVOICE, "SI-3100", GANNET, "2026-02-26", D("1080.00")),
    Document("doc:si-3101", DK.SALES_INVOICE, "SI-3101", GANNET, "2026-03-03", D("2400.00")),
    Document("doc:si-3102", DK.SALES_INVOICE, "SI-3102", GANNET, "2026-03-12", D("3600.00")),
    Document("doc:si-3103", DK.SALES_INVOICE, "SI-3103", SHEARWATER, "2026-03-18", D("2970.00")),
    # the two raised in April
    Document("doc:si-3104", DK.SALES_INVOICE, "SI-3104", GANNET, "2026-04-07", D("1890.00")),
    Document("doc:si-3105", DK.SALES_INVOICE, "SI-3105", SHEARWATER, "2026-04-14", D("2970.00")),
    # purchase invoices
    Document("doc:pi-8802", DK.PURCHASE_INVOICE, "PI-8802", NORTHSHORE, "2026-02-12", D("2860.00")),
    Document("doc:pi-8813", DK.PURCHASE_INVOICE, "PI-8813", NORTHSHORE, "2026-03-20", D("4175.00")),
    # the customer's cheque
    Document("doc:chq-2291", DK.CHEQUE, "2291", SHEARWATER, "2026-04-16"),
)

ROLES = (("receivables", AR), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
         ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
         ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening"),
         ("small_balance_write_offs", WRITE_OFFS))

BANK_OPENING = BankOpening("2026-03-01", D("56265.00"))
OPENING = OpeningPosition("2026-04-01", ((AR, D("9270.00")), ("Assets:Inventory", D("23400.00")),
                                         ("Liabilities:AP", D("-11600.00"))))


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


#: March 2026: the prior period, known to the bank archive only. The part
#: payment of SI-3100 is what makes its balance entering April differ from
#: its face value; nothing types the difference.
MARCH_EVENTS = (
    CustomerReceipt("event:si-3097-receipt", "2026-03-05", GANNET, "doc:si-3097", D("3640.00"),
                    ach_in("2026-03-05"), "Customer payment for SI-3097"),
    VendorPayment("event:pi-8802-payment", "2026-03-11", NORTHSHORE, "doc:pi-8802", D("2860.00"),
                  ach_out("2026-03-11"), "Payment of purchase invoice PI-8802"),
    CustomerReceipt("event:si-3100-part-receipt", "2026-03-13", GANNET, "doc:si-3100", D("780.00"),
                    ach_in("2026-03-13"), "Part payment against SI-3100"),
    CustomerReceipt("event:si-3099-receipt", "2026-03-24", SHEARWATER, "doc:si-3099", D("2215.00"),
                    ach_in("2026-03-24"), "Customer payment for SI-3099"),
    BankFee("event:fee-2026-03", "2026-03-31", D("40.00"), "Monthly account service charge"),
)

#: April's non-target rows and sales, identical in every case.
SALE_3104 = Sale("event:si-3104-sale", "2026-04-07", GANNET, "doc:si-3104", D("1750.00"), D("0.08"), D("1050.00"),
                 "Sale SI-3104", "Cost of goods sold on SI-3104")
SALE_3105 = Sale("event:si-3105-sale", "2026-04-14", SHEARWATER, "doc:si-3105", D("2750.00"), D("0.08"), D("1650.00"),
                 "Sale SI-3105", "Cost of goods sold on SI-3105")
PI_8813_PAYMENT = VendorPayment("event:pi-8813-payment", "2026-04-09", NORTHSHORE, "doc:pi-8813", D("4175.00"),
                                ach_out("2026-04-09"), "Payment of purchase invoice PI-8813")
FEE_APRIL = BankFee("event:fee-2026-04", "2026-04-30", D("45.00"), "Monthly account service charge")

WITHHELD_NOTE = "withheld; short shipment; credit requested"


def r1(withheld_note: str = WITHHELD_NOTE) -> AppliedReceipt:
    """R1: Gannet's ACH pay run of 10 April with advice RA-0410-GR. The
    third line is a zero-cash statement of dispute over SI-3100; Case 5
    words it for its price allowance."""
    return AppliedReceipt(
        "event:gr-payrun-0410", "2026-04-10", GANNET, D("3900.00"), ach_in("2026-04-10"),
        "Customer payment, GR PAYRUN 0410", "GR PAYRUN 0410",
        (ReceiptLine("doc:si-3101", D("2400.00"), True),
         ReceiptLine("doc:si-3102", D("1500.00"), False, D("0.00"),
                     "part payment; balance held pending credit for damaged crates"),
         ReceiptLine("doc:si-3100", D("0.00"), False, D("0.00"), withheld_note)),
        "RA-0410-GR")


#: R2: Shearwater's cheque 2291 dated 16 April, banked on the 21st, with
#: advice RA-0416-SB. SI-3103 and SI-3105 share its amount; only the advice
#: says which it paid.
R2 = AppliedReceipt(
    "event:sb-check-2291", "2026-04-16", SHEARWATER, D("2970.00"), cheque("doc:chq-2291", "2026-04-21"),
    "Customer check 2291", "",
    (ReceiptLine("doc:si-3103", D("2970.00"), True),),
    "RA-0416-SB")


def april_events(r1_event: AppliedReceipt, credit_note, r3: AppliedReceipt) -> tuple:
    """The period's events in date order: the shared ones with a case's
    credit note and third receipt in their places."""
    return (SALE_3104, PI_8813_PAYMENT, r1_event, SALE_3105, credit_note, R2, r3, FEE_APRIL)


def world(world_id: str, events: tuple) -> World:
    return World(
        id=world_id,
        title=TITLE,
        currency=CURRENCY,
        bank_account=BANK_ACCOUNT,
        bank_party_id=BANK,
        accounts=ACCOUNTS,
        parties=PARTIES,
        documents=DOCUMENTS,
        bank_opening=BANK_OPENING,
        opening=OPENING,
        events=MARCH_EVENTS + events,
        roles=ROLES,
        policy_text=POLICY_TEXT,
    )
