"""Thistle & Quill Design Studio, January 2026: the irreducible facts.

This is the hand-reviewed layer. It states what happened — amounts, dates,
counterparties, documents, rails, clearing dates — and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The studio pays its running costs on the business debit card and keys the
card spend into the books from the bank feed, so a card entry carries the
bank's date. The task's three mutations name recognitions by id: two card
rows the feed shows and the books never received, and one card row keyed
with a dropped digit. The February rent cheque is not a mutation at all: it
is a cheque the bank cleared on 3 February, and the January statement's
projection classifies it NOT_YET_SETTLED on its own.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..project import AlterRecognition, MutationPlan, OmitRecognition, Period
from ..derive import TaskSpec
from ..schema import (
    Account,
    AccountKind as K,
    BankFee,
    BankOpening,
    CustomerReceipt,
    Document,
    DocumentKind as DK,
    ExpensePayment,
    OpeningPosition,
    Party,
    PartyRole as R,
    Prepayment,
    Purchase,
    Rail,
    Sale,
    Settlement,
    VendorPayment,
    World,
)

POLICY_TEXT = """# Thistle & Quill Design Studio — Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, wire fees, returned
item fees) are recorded to `Expenses:BankFees` on the date the bank applies them.

## Customer receipts
Cash received from a client reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice. A deposit paid
on account of a job in progress is applied against the invoice it was raised
under in the same way.

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

## Card spend
The studio's running costs — software subscriptions, travel, the studio's
broadband and phones, consumables — are paid on the business debit card and
entered into the books from the bank feed, so a card entry carries the date
the bank shows. A card row on the statement whose vendor is in the vendor
master is booked to that vendor's `default_account` on the bank's date. A card
row the books do not carry is added, on the bank's date, to that account. A
card row the books carry with an amount that differs from the statement's has
been keyed wrongly: the entry is re-posted with the statement's amount, on the
date it was originally entered, and the wrong figure is not left standing
alongside it. A card row whose vendor is not in the vendor master is queried
with the studio manager before it is booked; it is never posted to a holding
account.

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
An entry carries the date of the transaction — the day a check was issued, a
receipt was received or an invoice was raised — never the date the bank
processed it. A ledger date that differs from the statement's date for the
same item is not an error and is not to be changed.

The bank processes a transaction on or after the day it happens, so for a
client or supplier movement the ledger date is never later than the
statement's date for the same item.

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
Thistle & Quill collects sales tax from clients on design fees and on the
printed goods it supplies, and owes it to the state. Print stock bought for
resale is exempt, so no tax is recoverable on the purchase side.

## Suspense accounts
Thistle & Quill does not operate a suspense or plug account. Every posting is
made to the account that reflects the underlying transaction.
"""

OPENED = "2024-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Studio operating checking account held at Heronsgate Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Fees and print charges receivable from clients", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Print stock and blanks held for client jobs", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from clients and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Design fees and printed goods billed to clients", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Print stock consumed on client jobs", OPENED, 5000),
    Account("Expenses:Software", K.EXPENSE, "Design software subscriptions and licences", OPENED, 5100),
    Account("Expenses:Travel", K.EXPENSE, "Travel to client sites and pitches", OPENED, 5200),
    Account("Expenses:Telecom", K.EXPENSE, "Studio broadband and phone lines", OPENED, 5300),
    Account("Expenses:Office", K.EXPENSE, "Studio consumables and presentation supplies", OPENED, 5400),
    Account("Expenses:Rent", K.EXPENSE, "Studio rent for the period", OPENED, 5500),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5600),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:marram-hotels", "Marram Coastal Hotels", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:harrowgate-brewing", "Harrowgate Brewing Co", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:linden-print", "Linden Print Works", R.VENDOR, 3, "net 30", "Assets:Inventory"),
    Party("party:mossgate", "Mossgate Properties", R.VENDOR, 4, "due on receipt", "Expenses:Rent"),
    Party("party:pixelforge", "Pixelforge Software", R.VENDOR, 5, "due on receipt", "Expenses:Software"),
    Party("party:skylark-travel", "Skylark Travel", R.VENDOR, 6, "due on receipt", "Expenses:Travel"),
    Party("party:corvid-telecom", "Corvid Telecom", R.VENDOR, 7, "due on receipt", "Expenses:Telecom"),
    Party("party:paperbark", "Paperbark Stationery", R.VENDOR, 8, "due on receipt", "Expenses:Office"),
    Party("party:heronsgate-bank", "Heronsgate Bank", R.BANK, 9),
)

DOCUMENTS = (
    Document("doc:si-0414", DK.SALES_INVOICE, "SI-0414", "party:harrowgate-brewing", "2025-10-28", D("3780.00")),
    Document("doc:si-0419", DK.SALES_INVOICE, "SI-0419", "party:marram-hotels", "2025-11-20", D("5940.00")),
    Document("doc:si-0427", DK.SALES_INVOICE, "SI-0427", "party:harrowgate-brewing", "2026-01-12", D("4590.00")),
    Document("doc:si-0428", DK.SALES_INVOICE, "SI-0428", "party:marram-hotels", "2026-01-19", D("7344.00")),
    Document("doc:pi-0772", DK.PURCHASE_INVOICE, "PI-0772", "party:linden-print", "2025-11-18", D("1260.00")),
    Document("doc:pi-0781", DK.PURCHASE_INVOICE, "PI-0781", "party:linden-print", "2025-12-15", D("1485.00")),
    Document("doc:pi-0790", DK.PURCHASE_INVOICE, "PI-0790", "party:linden-print", "2026-01-21", D("940.00")),
    Document("doc:chq-1039", DK.CHEQUE, "1039", "party:mossgate", "2025-12-01"),
    Document("doc:chq-1040", DK.CHEQUE, "1040", "party:mossgate", "2026-01-02"),
    Document("doc:chq-1041", DK.CHEQUE, "1041", "party:mossgate", "2026-01-29"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # December 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-12", "2025-12-01", "party:mossgate", D("2400.00"),
                   cheque("doc:chq-1039", "2025-12-04"), "December studio rent"),
    VendorPayment("event:pi-0772-payment", "2025-12-03", "party:linden-print", "doc:pi-0772", D("1260.00"),
                  ach_out("2025-12-03"), "Payment of purchase invoice PI-0772"),
    ExpensePayment("event:office-2025-12", "2025-12-04", "party:paperbark", D("87.45"),
                   card("2025-12-04"), "Printer toner and copier paper"),
    CustomerReceipt("event:si-0414-receipt", "2025-12-05", "party:harrowgate-brewing", "doc:si-0414", D("3780.00"),
                    ach_in("2025-12-05"), "Customer payment for SI-0414"),
    ExpensePayment("event:software-2025-12", "2025-12-09", "party:pixelforge", D("189.00"),
                   card("2025-12-09"), "Design suite subscription - December"),
    ExpensePayment("event:telecom-2025-12", "2025-12-17", "party:corvid-telecom", D("148.20"),
                   card("2025-12-17"), "Studio broadband and phones - December"),
    BankFee("event:fee-2025-12", "2025-12-31", D("22.00"), "Monthly account service charge"),
    # January 2026: the task period
    ExpensePayment("event:rent-2026-01", "2026-01-02", "party:mossgate", D("2520.00"),
                   cheque("doc:chq-1040", "2026-01-07"), "January studio rent at the uplifted lease rate"),
    ExpensePayment("event:software-2026-01", "2026-01-07", "party:pixelforge", D("283.50"),
                   card("2026-01-07"), "Design suite subscription - January (third seat added)"),
    CustomerReceipt("event:si-0419-receipt", "2026-01-08", "party:marram-hotels", "doc:si-0419", D("5940.00"),
                    ach_in("2026-01-08"), "Customer payment for SI-0419"),
    Sale("event:si-0427-sale", "2026-01-12", "party:harrowgate-brewing", "doc:si-0427", D("4250.00"), D("0.08"), D("380.00"),
         "Brand identity and label range SI-0427", "Print stock issued on SI-0427"),
    ExpensePayment("event:office-2026-01", "2026-01-14", "party:paperbark", D("264.90"),
                   card("2026-01-14"), "Presentation boards and mounting supplies"),
    ExpensePayment("event:travel-2026-01", "2026-01-15", "party:skylark-travel", D("527.40"),
                   card("2026-01-15"), "Rail fares and hotel - Marram site visit"),
    VendorPayment("event:pi-0781-payment", "2026-01-15", "party:linden-print", "doc:pi-0781", D("1485.00"),
                  ach_out("2026-01-15"), "Payment of purchase invoice PI-0781"),
    ExpensePayment("event:telecom-2026-01", "2026-01-19", "party:corvid-telecom", D("151.35"),
                   card("2026-01-19"), "Studio broadband and phones - January"),
    Sale("event:si-0428-sale", "2026-01-19", "party:marram-hotels", "doc:si-0428", D("6800.00"), D("0.08"), D("910.00"),
         "Spring campaign design and print SI-0428", "Print stock issued on SI-0428"),
    Purchase("event:pi-0790-receipt", "2026-01-21", "party:linden-print", "doc:pi-0790", D("940.00"),
             "Purchase invoice PI-0790 received - print stock"),
    ExpensePayment("event:software-licence-2026-01", "2026-01-23", "party:pixelforge", D("96.00"),
                   card("2026-01-23"), "Stock image licence pack"),
    CustomerReceipt("event:si-0428-deposit", "2026-01-23", "party:marram-hotels", "doc:si-0428", D("3672.00"),
                    ach_in("2026-01-23"), "Deposit of half the invoice against SI-0428"),
    CustomerReceipt("event:si-0427-receipt", "2026-01-26", "party:harrowgate-brewing", "doc:si-0427", D("4590.00"),
                    ach_in("2026-01-26"), "Customer payment settling SI-0427"),
    # issued in January, cleared by the bank in February: the timing difference
    Prepayment("event:rent-2026-02-prepaid", "2026-01-29", "party:mossgate", D("2520.00"),
               cheque("doc:chq-1041", "2026-02-03"), "2026-02", "February rent prepaid, check 1041"),
    BankFee("event:fee-2026-01", "2026-01-30", D("25.00"), "Monthly account service charge"),
)

WORLD = World(
    id="thistle-2026-01",
    title="Thistle & Quill Design Studio - FY2026",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:heronsgate-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-12-01", D("27640.00")),
    opening=OpeningPosition("2026-01-01", (("Assets:AR", D("9180.00")), ("Assets:Inventory", D("2150.00")),
                                           ("Liabilities:AP", D("-1485.00")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

BANK_FEED_CATEGORISATION_001 = TaskSpec(
    id="bank_feed_categorisation_001",
    type="bank_reconciliation",
    prompt=("The January bank feed for the studio checking account has been downloaded. Several card transactions "
            "never reached the books and one was keyed wrongly. Categorise every feed line under the bookkeeping "
            "policy, bring the ledger into agreement with the statement, and write the corrected ledger back to "
            "ledger.beancount."),
    period=Period("2026-01-01", "2026-01-31", "January 2026"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_software_card", "rec:software-2026-01",
                        "the statement row DEBIT CARD PIXELFORGE SOFTWARE of 283.50 on 2026-01-07 answers no ledger "
                        "entry; vendors.csv maps Pixelforge Software to Expenses:Software and policy.md's Card spend "
                        "section adds a missing card row to the vendor's default account on the bank's date"),
        OmitRecognition("unrecorded_travel_card", "rec:travel-2026-01",
                        "the statement row DEBIT CARD SKYLARK TRAVEL of 527.40 on 2026-01-15 answers no ledger "
                        "entry; vendors.csv maps Skylark Travel to Expenses:Travel and policy.md's Card spend "
                        "section adds a missing card row to the vendor's default account on the bank's date"),
        AlterRecognition("miskeyed_office_card", "rec:office-2026-01", "drop_digit", 1,
                         "the statement row DEBIT CARD PAPERBARK STATIONERY of 264.90 on 2026-01-14 answers the "
                         "ledger's same-day Paperbark Stationery entry of 24.90 and no other; vendors.csv maps "
                         "Paperbark Stationery to Expenses:Office and policy.md's Card spend section re-posts a "
                         "mis-keyed card row with the statement's amount on its original date"),
    )),
)

TASKS = {BANK_FEED_CATEGORISATION_001.id: BANK_FEED_CATEGORISATION_001}
