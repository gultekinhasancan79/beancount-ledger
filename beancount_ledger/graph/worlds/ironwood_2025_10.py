"""Ironwood Furniture Works, October 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The month is an accounts-payable payment run. Three inventory suppliers
invoice on net 30 / net 45 terms; the September invoices are carried in the
opening payables and paid on the October run, by ACH quoting the purchase
invoice number or by check where the supplier does not take ACH. The task's
three mutations name recognitions by id: one run payment was never posted,
one was keyed with two digits transposed, one was posted twice. The check
to the fabric supplier issued on 29 October is not a mutation at all: the
bank cleared it on 4 November, and the October statement's projection
classifies it NOT_YET_SETTLED on its own.
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

POLICY_TEXT = """# Ironwood Furniture Works - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, ACH origination
fees, returned item fees) are recorded to `Expenses:BankFees` on the date the
bank applies them.

## Customer receipts
Cash received from a customer reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice.

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

## Payment runs
Ironwood pays its lumber, hardware and fabric suppliers on a payment run. The
payables clerk selects the purchase invoices that have fallen due under each
supplier's terms and releases them by ACH, quoting the purchase invoice number
as the payment reference, or by check where the supplier does not accept ACH.
Every payment released on a run settles a payable that was raised when the
goods arrived, so it is recorded as a debit to `Liabilities:AP` and a credit
to the checking account, dated the day the run was released. The supplier's
invoice stays booked to `Assets:Inventory`; a payment never touches it.

The payables ledger is tied to the bank statement after every run. Three
kinds of difference arise, and each has exactly one correction:

- A supplier payment that appears on the statement but was never posted is
  added to the ledger for the supplier and the amount the statement shows,
  against `Liabilities:AP`, on the date the bank shows (see Dates below).
- A supplier payment that was posted twice is corrected by removing one of
  the two copies. The copy that remains is left exactly as it was.
- A supplier payment posted with a mis-keyed amount is corrected by
  re-posting the entry with the amount the statement shows, on the date the
  entry was originally posted. Only the amount changes; the date, the
  supplier and the accounts stay as they were.

A payment that is on both the statement and the ledger with the same
supplier, amount and reference is a match and is not touched.

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
An entry carries the date of the transaction - the day a check was issued, a
payment run was released, a receipt was received or an invoice was raised -
never the date the bank processed it. A ledger date that differs from the
statement's date for the same item is not an error and is not to be changed.

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

## Utilities
Workshop electricity is paid by the company debit card when the bill falls
due. The utility is a supplier whose purchases are booked to an expense
account, so the card payment is the expense and is recorded to
`Expenses:Utilities` on the day the card is charged.

## Sales tax
Ironwood collects sales tax from customers on sales of finished furniture and
owes it to the state. Lumber, hardware and fabric bought for manufacture are
exempt under the resale certificate, so no tax is recoverable on the purchase
side.

## Suspense accounts
Ironwood does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
"""

OPENED = "2025-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Tamarack Valley Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Trade receivables from customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Lumber, hardware, fabric and finished pieces held for sale", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Revenue from furniture sold", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:Rent", K.EXPENSE, "Workshop and showroom rent for the period", OPENED, 5200),
    Account("Expenses:Utilities", K.EXPENSE, "Workshop electricity", OPENED, 5250),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:mercer-street", "Mercer Street Interiors", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:seabright", "Seabright Hospitality Group", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:pellston", "Pellston Hardwood Mills", R.VENDOR, 3, "net 30", "Assets:Inventory"),
    Party("party:norquist", "Norquist Hardware and Fittings", R.VENDOR, 4, "net 45", "Assets:Inventory"),
    Party("party:wexcombe", "Wexcombe Upholstery Fabrics", R.VENDOR, 5, "net 30", "Assets:Inventory"),
    Party("party:sawyer-lane", "Sawyer Lane Properties", R.VENDOR, 6, "due on receipt", "Expenses:Rent"),
    Party("party:cottonwood", "Cottonwood Power and Light", R.VENDOR, 7, "due on receipt", "Expenses:Utilities"),
    Party("party:tamarack-valley-bank", "Tamarack Valley Bank", R.BANK, 8),
)

DOCUMENTS = (
    Document("doc:si-3412", DK.SALES_INVOICE, "SI-3412", "party:mercer-street", "2025-08-19", D("5976.00")),
    Document("doc:si-3418", DK.SALES_INVOICE, "SI-3418", "party:seabright", "2025-09-12", D("11287.50")),
    Document("doc:si-3425", DK.SALES_INVOICE, "SI-3425", "party:mercer-street", "2025-10-09", D("9041.50")),
    Document("doc:pi-4458", DK.PURCHASE_INVOICE, "PI-4458", "party:pellston", "2025-08-07", D("5318.20")),
    Document("doc:pi-4461", DK.PURCHASE_INVOICE, "PI-4461", "party:wexcombe", "2025-08-13", D("2746.85")),
    Document("doc:pi-4463", DK.PURCHASE_INVOICE, "PI-4463", "party:norquist", "2025-08-12", D("3318.75")),
    Document("doc:pi-4471", DK.PURCHASE_INVOICE, "PI-4471", "party:pellston", "2025-09-04", D("6842.50")),
    Document("doc:pi-4474", DK.PURCHASE_INVOICE, "PI-4474", "party:pellston", "2025-09-18", D("2375.80")),
    Document("doc:pi-4476", DK.PURCHASE_INVOICE, "PI-4476", "party:norquist", "2025-09-11", D("2964.30")),
    Document("doc:pi-4482", DK.PURCHASE_INVOICE, "PI-4482", "party:wexcombe", "2025-09-17", D("4187.90")),
    Document("doc:pi-4485", DK.PURCHASE_INVOICE, "PI-4485", "party:wexcombe", "2025-09-29", D("3940.25")),
    Document("doc:pi-4490", DK.PURCHASE_INVOICE, "PI-4490", "party:pellston", "2025-10-08", D("5604.75")),
    Document("doc:pi-4496", DK.PURCHASE_INVOICE, "PI-4496", "party:norquist", "2025-10-15", D("3472.10")),
    Document("doc:pi-4501", DK.PURCHASE_INVOICE, "PI-4501", "party:wexcombe", "2025-10-22", D("2318.60")),
    Document("doc:chq-2089", DK.CHEQUE, "2089", "party:sawyer-lane", "2025-09-02"),
    Document("doc:chq-2090", DK.CHEQUE, "2090", "party:wexcombe", "2025-09-12"),
    Document("doc:chq-2091", DK.CHEQUE, "2091", "party:sawyer-lane", "2025-10-02"),
    Document("doc:chq-2092", DK.CHEQUE, "2092", "party:wexcombe", "2025-10-16"),
    Document("doc:chq-2093", DK.CHEQUE, "2093", "party:wexcombe", "2025-10-29"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # September 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-09", "2025-09-02", "party:sawyer-lane", D("4250.00"),
                   cheque("doc:chq-2089", "2025-09-05"), "September rent, workshop and showroom"),
    Purchase("event:pi-4471-purchase", "2025-09-04", "party:pellston", "doc:pi-4471", D("6842.50"),
             "Purchase invoice PI-4471 received, white oak and walnut boards"),
    VendorPayment("event:pi-4458-payment", "2025-09-08", "party:pellston", "doc:pi-4458", D("5318.20"),
                  ach_out("2025-09-08"), "Payment of purchase invoice PI-4458"),
    CustomerReceipt("event:si-3412-receipt", "2025-09-11", "party:mercer-street", "doc:si-3412", D("5976.00"),
                    ach_in("2025-09-11"), "Customer payment for SI-3412"),
    Purchase("event:pi-4476-purchase", "2025-09-11", "party:norquist", "doc:pi-4476", D("2964.30"),
             "Purchase invoice PI-4476 received, drawer slides and hinges"),
    VendorPayment("event:pi-4461-payment", "2025-09-12", "party:wexcombe", "doc:pi-4461", D("2746.85"),
                  cheque("doc:chq-2090", "2025-09-17"), "Payment of purchase invoice PI-4461, check 2090"),
    Purchase("event:pi-4482-purchase", "2025-09-17", "party:wexcombe", "doc:pi-4482", D("4187.90"),
             "Purchase invoice PI-4482 received, upholstery fabric and webbing"),
    Purchase("event:pi-4474-purchase", "2025-09-18", "party:pellston", "doc:pi-4474", D("2375.80"),
             "Purchase invoice PI-4474 received, maple boards"),
    ExpensePayment("event:utilities-2025-09", "2025-09-19", "party:cottonwood", D("612.44"),
                   card("2025-09-20"), "Workshop electricity, September"),
    VendorPayment("event:pi-4463-payment", "2025-09-26", "party:norquist", "doc:pi-4463", D("3318.75"),
                  ach_out("2025-09-26"), "Payment of purchase invoice PI-4463"),
    Purchase("event:pi-4485-purchase", "2025-09-29", "party:wexcombe", "doc:pi-4485", D("3940.25"),
             "Purchase invoice PI-4485 received, leather hides"),
    BankFee("event:fee-2025-09", "2025-09-30", D("61.50"), "Monthly service charge and ACH origination fees"),
    # October 2025: the task period
    ExpensePayment("event:rent-2025-10", "2025-10-02", "party:sawyer-lane", D("4377.50"),
                   cheque("doc:chq-2091", "2025-10-07"), "October rent, lease escalation from 1 October"),
    VendorPayment("event:pi-4471-payment", "2025-10-06", "party:pellston", "doc:pi-4471", D("6842.50"),
                  ach_out("2025-10-06"), "Payment of purchase invoice PI-4471"),
    Purchase("event:pi-4490-purchase", "2025-10-08", "party:pellston", "doc:pi-4490", D("5604.75"),
             "Purchase invoice PI-4490 received, cherry and ash boards"),
    Sale("event:si-3425-sale", "2025-10-09", "party:mercer-street", "doc:si-3425", D("8450.00"), D("0.07"), D("5215.00"),
         "Sale SI-3425, dining table and eight chairs", "Cost of goods sold on SI-3425"),
    CustomerReceipt("event:si-3418-receipt", "2025-10-14", "party:seabright", "doc:si-3418", D("11287.50"),
                    ach_in("2025-10-14"), "Customer payment for SI-3418"),
    Purchase("event:pi-4496-purchase", "2025-10-15", "party:norquist", "doc:pi-4496", D("3472.10"),
             "Purchase invoice PI-4496 received, brass pulls and levelers"),
    VendorPayment("event:pi-4482-payment", "2025-10-16", "party:wexcombe", "doc:pi-4482", D("4187.90"),
                  cheque("doc:chq-2092", "2025-10-21"), "Payment of purchase invoice PI-4482, check 2092"),
    VendorPayment("event:pi-4474-payment", "2025-10-20", "party:pellston", "doc:pi-4474", D("2375.80"),
                  ach_out("2025-10-20"), "Payment of purchase invoice PI-4474"),
    ExpensePayment("event:utilities-2025-10", "2025-10-21", "party:cottonwood", D("587.19"),
                   card("2025-10-22"), "Workshop electricity, October"),
    Purchase("event:pi-4501-purchase", "2025-10-22", "party:wexcombe", "doc:pi-4501", D("2318.60"),
             "Purchase invoice PI-4501 received, linen and foam"),
    VendorPayment("event:pi-4476-payment", "2025-10-27", "party:norquist", "doc:pi-4476", D("2964.30"),
                  ach_out("2025-10-27"), "Payment of purchase invoice PI-4476"),
    CustomerReceipt("event:si-3425-receipt", "2025-10-28", "party:mercer-street", "doc:si-3425", D("9041.50"),
                    ach_in("2025-10-28"), "Customer payment settling SI-3425"),
    # issued in October, cleared by the bank in November: the timing difference
    VendorPayment("event:pi-4485-payment", "2025-10-29", "party:wexcombe", "doc:pi-4485", D("3940.25"),
                  cheque("doc:chq-2093", "2025-11-04"), "Payment of purchase invoice PI-4485, check 2093"),
    BankFee("event:fee-2025-10", "2025-10-31", D("72.00"), "Monthly service charge and ACH origination fees"),
)

WORLD = World(
    id="ironwood-2025-10",
    title="Ironwood Furniture Works - FY2025",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:tamarack-valley-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-09-01", D("47316.28")),
    opening=OpeningPosition("2025-10-01", (("Assets:AR", D("14612.75")), ("Assets:Inventory", D("38450.00")),
                                           ("Liabilities:AP", D("-20310.75")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

AP_PAYMENT_RUN_001 = TaskSpec(
    id="ap_payment_run_001",
    type="bank_reconciliation",
    prompt=("The October supplier payment run has been posted, but the payables ledger does not tie to the "
            "Tamarack Valley Bank statement for October. Reconcile the checking account against the statement, "
            "correct the books under the bookkeeping policy, and write the corrected ledger back to "
            "ledger.beancount."),
    period=Period("2025-10-01", "2025-10-31", "October 2025"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_supplier_payment", "rec:pi-4476-payment",
                        "the statement row names the supplier and the invoice (ACH OUT NORQUIST HARDWARE AND "
                        "FITTINGS, PI-4476) and no ledger entry matches it; vendors.csv books that supplier's "
                        "purchases to Assets:Inventory, so under the payments-to-suppliers and payment-runs sections "
                        "the payment settles Liabilities:AP, and the dates section puts it on the bank's date"),
        AlterRecognition("transposed_supplier_payment", "rec:pi-4471-payment", "transpose_digits", 1,
                         "the ledger carries the 6 October payment of PI-4471 to Pellston Hardwood Mills at 6482.50 "
                         "while the statement row of the same date, supplier and reference shows 6842.50; the "
                         "payment-runs section says to re-post the entry with the statement's amount on the "
                         "original date, against Liabilities:AP"),
        DuplicateRecognition("duplicated_supplier_payment", "rec:pi-4474-payment",
                             "the ledger carries the 20 October payment of PI-4474 to Pellston Hardwood Mills "
                             "twice and the statement shows one ACH OUT row of 2375.80 with that reference; the "
                             "payment-runs section says to remove one copy and leave the other as it was"),
    )),
)

TASKS = {AP_PAYMENT_RUN_001.id: AP_PAYMENT_RUN_001}
