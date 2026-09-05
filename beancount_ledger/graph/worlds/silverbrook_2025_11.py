"""Silverbrook Dental Supply, November 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The month is a receivables and collections cycle. Four dental practices buy
on net 30 / net 45 terms and remit by ACH quoting the sales invoice number,
or by check; one practice pays an invoice in two parts. The task's three
mutations name recognitions by id: one ACH receipt was never posted, one
was keyed with two digits transposed, one was posted twice. The check
received from Maple Row on 28 November is not a mutation at all: the bank
credited it on 2 December, and the November statement's projection
classifies it NOT_YET_SETTLED on its own - a deposit in transit.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..project import AlterRecognition, DuplicateRecognition, MutationPlan, OmitRecognition, Period
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
    Purchase,
    Rail,
    Sale,
    Settlement,
    VendorPayment,
    World,
)

POLICY_TEXT = """# Silverbrook Dental Supply - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, remote deposit
fees, returned item fees) are recorded to `Expenses:BankFees` on the date the
bank applies them.

## Customer receipts
Cash received from a customer reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice.

## Collections
Silverbrook sells to dental practices on net 30 and net 45 terms and invoices
every shipment. A practice remits by ACH, quoting the sales invoice number as
the payment reference, or by check. Every receipt is applied to the invoice
the reference names and is recorded as a debit to the checking account and a
credit to `Assets:AR`, dated the day the remittance was received. A partial
payment reduces the balance of the invoice it names; the remainder stays open
in `Assets:AR` until the practice pays it.

The receivables ledger is tied to the bank statement at every month-end.
Three kinds of difference arise, and each has exactly one correction:

- A customer receipt that appears on the statement but was never posted is
  added to the ledger for the customer and the amount the statement shows,
  against `Assets:AR`, on the date the bank shows (see Dates below).
- A customer receipt that was posted twice is corrected by removing one of
  the two copies. The copy that remains is left exactly as it was.
- A customer receipt posted with a mis-keyed amount is corrected by
  re-posting the entry with the amount the statement shows, on the date the
  entry was originally posted. Only the amount changes; the date, the
  customer and the accounts stay as they were.

A receipt that is on both the statement and the ledger with the same
customer, amount and reference is a match and is not touched. A check
received from a practice and recorded in the ledger that the bank has not yet
credited at the cut-off is a deposit in transit, governed by its own section
below; it is not a difference to correct.

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
listed as an outstanding item. A customer's check taken into the ledger on the
day it was received and credited by the bank in the following month is the
usual case. It is never removed or adjusted.

## Dates
An entry carries the date of the transaction - the day a check was issued, a
receipt was received or an invoice was raised - never the date the bank
processed it. A ledger date that differs from the statement's date for the
same item is not an error and is not to be changed.

The bank processes a transaction on or after the day it happens, so for a
customer or vendor movement the ledger date is never later than the
statement's date for the same item.

An item the books do not carry at all has no transaction date to keep. The
statement's date is then the only date in evidence, so an entry added for a
statement row the ledger is missing is posted on the date the bank shows.

## Matching the statement to the ledger
A statement row and a ledger entry of the same amount and the same
counterparty, dated within the clearing window for the rail the row names,
are the same transaction and are treated as one item - not as two that
happen to agree.

## Prepayments
Amounts paid before the period they relate to are recorded to
`Assets:Prepayments` and released to expense in the period they cover. Rent
paid in one month for the following month is a prepayment, not an expense of
the month it was paid.

## Sales tax
Silverbrook collects sales tax at 8% from its customers on sales of supplies
and equipment and owes it to the state. Goods bought for resale are exempt
under the resale certificate, so no tax is recoverable on the purchase side.

## Suspense accounts
Silverbrook does not operate a suspense or plug account. Every posting is made
to the account that reflects the underlying transaction.
"""

OPENED = "2025-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Harlow Creek Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Trade receivables from dental practices", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Dental consumables and equipment held for resale", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Revenue from dental supplies and equipment sold", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:Rent", K.EXPENSE, "Warehouse and office rent for the period", OPENED, 5200),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:maple-row", "Maple Row Family Dentistry", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:ellery-park", "Ellery Park Orthodontics", R.CUSTOMER, 2, "net 45", "Assets:AR"),
    Party("party:sycamore", "Sycamore Pediatric Dental", R.CUSTOMER, 3, "net 30", "Assets:AR"),
    Party("party:kessler", "Kessler Family Dental", R.CUSTOMER, 4, "net 45", "Assets:AR"),
    Party("party:deverell", "Deverell Dental Products", R.VENDOR, 5, "net 30", "Assets:Inventory"),
    Party("party:talbot-street", "Talbot Street Realty", R.VENDOR, 6, "due on receipt", "Expenses:Rent"),
    Party("party:harlow-creek-bank", "Harlow Creek Bank", R.BANK, 7),
)

DOCUMENTS = (
    Document("doc:si-2198", DK.SALES_INVOICE, "SI-2198", "party:kessler", "2025-09-24", D("3942.00")),
    Document("doc:si-2203", DK.SALES_INVOICE, "SI-2203", "party:sycamore", "2025-09-30", D("1512.00")),
    Document("doc:si-2207", DK.SALES_INVOICE, "SI-2207", "party:ellery-park", "2025-10-09", D("3002.40")),
    Document("doc:si-2211", DK.SALES_INVOICE, "SI-2211", "party:maple-row", "2025-10-16", D("4374.00")),
    Document("doc:si-2218", DK.SALES_INVOICE, "SI-2218", "party:sycamore", "2025-11-10", D("2494.80")),
    Document("doc:si-2223", DK.SALES_INVOICE, "SI-2223", "party:kessler", "2025-11-13", D("6615.00")),
    Document("doc:si-2229", DK.SALES_INVOICE, "SI-2229", "party:maple-row", "2025-11-14", D("1992.60")),
    Document("doc:si-2234", DK.SALES_INVOICE, "SI-2234", "party:ellery-park", "2025-11-24", D("3736.80")),
    Document("doc:pi-5182", DK.PURCHASE_INVOICE, "PI-5182", "party:deverell", "2025-09-19", D("6218.40")),
    Document("doc:pi-5196", DK.PURCHASE_INVOICE, "PI-5196", "party:deverell", "2025-10-14", D("5637.25")),
    Document("doc:pi-5210", DK.PURCHASE_INVOICE, "PI-5210", "party:deverell", "2025-11-18", D("4286.90")),
    Document("doc:chq-3051", DK.CHEQUE, "3051", "party:talbot-street", "2025-10-01"),
    Document("doc:chq-3052", DK.CHEQUE, "3052", "party:talbot-street", "2025-11-03"),
    Document("doc:chq-4471", DK.CHEQUE, "4471", "party:kessler", "2025-11-17"),
    Document("doc:chq-10388", DK.CHEQUE, "10388", "party:maple-row", "2025-11-28"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # October 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-10", "2025-10-01", "party:talbot-street", D("2850.00"),
                   cheque("doc:chq-3051", "2025-10-06"), "October rent, warehouse and office, check 3051"),
    VendorPayment("event:pi-5182-payment", "2025-10-03", "party:deverell", "doc:pi-5182", D("6218.40"),
                  ach_out("2025-10-03"), "Payment of purchase invoice PI-5182"),
    CustomerReceipt("event:si-2198-receipt", "2025-10-08", "party:kessler", "doc:si-2198", D("3942.00"),
                    ach_in("2025-10-08"), "Customer payment settling SI-2198"),
    CustomerReceipt("event:si-2203-receipt", "2025-10-22", "party:sycamore", "doc:si-2203", D("1512.00"),
                    ach_in("2025-10-22"), "Customer payment settling SI-2203"),
    BankFee("event:fee-2025-10", "2025-10-31", D("42.00"), "Monthly account service charge"),
    # November 2025: the task period
    ExpensePayment("event:rent-2025-11", "2025-11-03", "party:talbot-street", D("2987.50"),
                   cheque("doc:chq-3052", "2025-11-06"), "November rent and annual CAM reconciliation charge, check 3052"),
    CustomerReceipt("event:si-2211-receipt", "2025-11-05", "party:maple-row", "doc:si-2211", D("4374.00"),
                    ach_in("2025-11-05"), "Customer payment settling SI-2211"),
    VendorPayment("event:pi-5196-payment", "2025-11-07", "party:deverell", "doc:pi-5196", D("5637.25"),
                  ach_out("2025-11-07"), "Payment of purchase invoice PI-5196"),
    Sale("event:si-2218-sale", "2025-11-10", "party:sycamore", "doc:si-2218", D("2310.00"), D("0.08"), D("1386.00"),
         "Sale SI-2218, hygiene consumables and exam gloves", "Cost of goods sold on SI-2218"),
    CustomerReceipt("event:si-2207-receipt", "2025-11-12", "party:ellery-park", "doc:si-2207", D("3002.40"),
                    ach_in("2025-11-12"), "Customer payment settling SI-2207"),
    Sale("event:si-2223-sale", "2025-11-13", "party:kessler", "doc:si-2223", D("6125.00"), D("0.08"), D("3675.00"),
         "Sale SI-2223, intraoral sensor and restorative consumables", "Cost of goods sold on SI-2223"),
    Sale("event:si-2229-sale", "2025-11-14", "party:maple-row", "doc:si-2229", D("1845.00"), D("0.08"), D("1107.00"),
         "Sale SI-2229, impression material and prophy supplies", "Cost of goods sold on SI-2229"),
    CustomerReceipt("event:si-2223-part-receipt", "2025-11-17", "party:kessler", "doc:si-2223", D("3500.00"),
                    cheque("doc:chq-4471", "2025-11-20"), "Partial payment against SI-2223, check 4471"),
    Purchase("event:pi-5210-purchase", "2025-11-18", "party:deverell", "doc:pi-5210", D("4286.90"),
             "Purchase invoice PI-5210 received, composite kits and carbide burs"),
    CustomerReceipt("event:si-2218-receipt", "2025-11-19", "party:sycamore", "doc:si-2218", D("2494.80"),
                    ach_in("2025-11-19"), "Customer payment settling SI-2218"),
    Sale("event:si-2234-sale", "2025-11-24", "party:ellery-park", "doc:si-2234", D("3460.00"), D("0.08"), D("2076.00"),
         "Sale SI-2234, orthodontic archwire and brackets", "Cost of goods sold on SI-2234"),
    # received in November, credited by the bank in December: the deposit in transit
    CustomerReceipt("event:si-2229-receipt", "2025-11-28", "party:maple-row", "doc:si-2229", D("1992.60"),
                    cheque("doc:chq-10388", "2025-12-02"), "Customer payment settling SI-2229, check 10388"),
    BankFee("event:fee-2025-11", "2025-11-28", D("47.50"), "Monthly account service charge and remote deposit fee"),
)

WORLD = World(
    id="silverbrook-2025-11",
    title="Silverbrook Dental Supply - FY2025",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:harlow-creek-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-10-01", D("38472.19")),
    opening=OpeningPosition("2025-11-01", (("Assets:AR", D("8916.40")), ("Assets:Inventory", D("31480.00")),
                                           ("Liabilities:AP", D("-6891.75")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

AR_COLLECTIONS_001 = TaskSpec(
    id="ar_collections_001",
    type="bank_reconciliation",
    prompt=("The November statement from Harlow Creek Bank is in, and the month-end collections review has found "
            "that the receivables ledger does not agree with it. Reconcile the checking account against the "
            "statement, bring the books into agreement under the bookkeeping policy, and write the corrected "
            "ledger back to ledger.beancount."),
    period=Period("2025-11-01", "2025-11-30", "November 2025"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_receipt", "rec:si-2218-receipt",
                        "the statement row names the payer and the invoice (ACH IN SYCAMORE PEDIATRIC DENTAL, "
                        "SI-2218) and no ledger entry matches it; customers.csv maps the practice to Assets:AR and "
                        "the ledger carries the open sale SI-2218; the collections section posts a receipt the "
                        "books lack against Assets:AR, and the dates section puts it on the bank's date"),
        AlterRecognition("transposed_customer_receipt", "rec:si-2211-receipt", "transpose_digits", 1,
                         "the ledger carries the 5 November receipt from Maple Row Family Dentistry for SI-2211 at "
                         "4734.00 while the statement row of the same date, payer and reference shows 4374.00; the "
                         "collections section says to re-post the entry with the statement's amount on the "
                         "original date, against Assets:AR"),
        DuplicateRecognition("duplicated_customer_receipt", "rec:si-2207-receipt",
                             "the ledger carries the 12 November receipt from Ellery Park Orthodontics for SI-2207 "
                             "twice and the statement shows one ACH IN row of 3002.40 with that reference; the "
                             "collections section says to remove one copy and leave the other as it was"),
    )),
)

TASKS = {AR_COLLECTIONS_001.id: AR_COLLECTIONS_001}
