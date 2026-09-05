"""Redwood Analytics Group, November 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The month is an intercompany funding month. Redwood Analytics Group is a
consulting parent that draws checks to its wholly owned subsidiary, Redwood
Analytics Europe Ltd, whenever the subsidiary's own collections will not
cover its payroll and suppliers; the subsidiary sits in the vendor master
with terms `intercompany` and `Assets:Due-From-Subsidiary` as its default
account, so each advance is a two-legged expense-style payment that lands on
an asset. Around the advances the group has an ordinary month: three
consulting clients invoiced with sales tax and paying by ACH, a
subcontracted data engineer whose invoices go to work in progress and are
settled through payables, the analytics platform charged to the card, the
landlord paid by check and the bank's own service charge. The task's three
mutations name recognitions by id: the first November advance was never
posted, the second was posted twice, and one client receipt was keyed with
two digits transposed. The check to the landlord issued on 27 November is
not a mutation at all: the bank cleared it on 3 December, and the November
statement's projection classifies it NOT_YET_SETTLED on its own.
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
    Prepayment,
    Purchase,
    Rail,
    Sale,
    Settlement,
    VendorPayment,
    World,
)

POLICY_TEXT = """# Redwood Analytics Group - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, ACH origination
fees, returned item fees) are recorded to `Expenses:BankFees` on the date the
bank applies them.

## Customer receipts
Cash received from a client reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice.

The receivables ledger is agreed to the bank statement at every month-end. A
receipt that the statement shows and the ledger carries for the same client
and invoice but for a different amount was mis-keyed: it is re-posted with
the amount the statement shows, on the date the entry was originally posted.
Only the amount changes; the client, the invoice and the accounts stay as
they were.

## Payments to suppliers
The `default_account` a supplier carries in the vendor master is where that
supplier's purchases are booked when they arrive. It is not where a payment to
that supplier lands. Where a trade supplier's purchases are booked to an asset
account, the work was taken into that account when the supplier's invoice
arrived and a payable was raised for it at the same time, so cash paid to that
supplier afterwards settles the payable and is recorded to `Liabilities:AP`.
Where a supplier's purchases are booked to an expense account, no payable is
raised: the payment is the expense, and it is recorded to that supplier's own
`default_account` on the day it is paid, except where it is paid ahead of the
period it covers, which the prepayments section below governs.

A group company is carried in the vendor master only so that checks can be
drawn to it, and its terms read `intercompany`. It is not a trade supplier:
nothing is purchased from it, no invoice is received from it and no payable is
ever raised for it. Cash sent to it is an advance, not a payment for goods or
services: it is booked to `Assets:Due-From-Subsidiary`, the account the vendor
master lists for it, and never to `Liabilities:AP`. The intercompany balances
section below governs it.

## Intercompany balances
Redwood Analytics Group funds its wholly owned subsidiary, Redwood Analytics
Europe Ltd, by check whenever the subsidiary's own collections will not cover
its payroll and suppliers. Every advance is a debit to
`Assets:Due-From-Subsidiary`, the default account the vendor master lists for
the subsidiary, and a credit to the checking account, dated the day the check
was issued, with the subsidiary as payee. The advance is repayable and stays on
that account until the subsidiary repays it; it is never expensed, never
treated as a payable and never netted against anything else.

The intercompany balance is agreed with the subsidiary's own books at every
month-end, so `Assets:Due-From-Subsidiary` must carry each advance exactly
once. Three kinds of difference arise against the bank statement, and each has
exactly one correction:

- An advance that appears on the statement but that the books lack is added
  for the subsidiary and the amount the statement shows, to
  `Assets:Due-From-Subsidiary`, on the date the bank shows (see Dates below).
- An advance that was posted twice is corrected by removing one of the two
  copies. The copy that remains is left exactly as it was.
- An advance posted with a mis-keyed amount is corrected by re-posting the
  entry with the amount the statement shows, on the date the entry was
  originally posted.

An advance that is on both the statement and the ledger with the same payee,
check number and amount is a match and is not touched.

## Subcontracted work
Redwood delivers part of its engagements through subcontracted data
engineers. A subcontractor's invoice is booked to `Assets:Work-In-Progress`
when it arrives and a payable is raised for it at the same time. The work
stays in that account until the engagement is billed, when it is released to
`Expenses:Cost-Of-Services` against the client invoice.

## Software subscriptions
The analytics platform is paid by the company debit card when the monthly
subscription falls due. The platform vendor is a supplier whose purchases are
booked to an expense account, so the card charge is the expense and is
recorded to `Expenses:Software` on the day the card is charged.

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
An entry carries the date of the transaction - the day a check was issued, an
advance was drawn to a group company, a receipt was received or an invoice was
raised - never the date the bank processed it. A ledger date that differs from
the statement's date for the same item is not an error and is not to be
changed.

The bank processes a transaction on or after the day it happens, so for a
client, supplier or group-company movement the ledger date is never later than
the statement's date for the same item.

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
Redwood collects sales tax from clients on its consulting and analytics fees,
which are taxable where its clients are billed, and owes it to the state.
Subcontracted work bought for delivery to a client is exempt under the resale
certificate, so no tax is recoverable on the purchase side.

## Suspense accounts
Redwood does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
"""

OPENED = "2025-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Sequoia Coast Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Trade receivables from clients", OPENED, 1100),
    Account("Assets:Work-In-Progress", K.ASSET, "Subcontracted consulting work taken in and not yet billed to a client", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Assets:Due-From-Subsidiary", K.ASSET, "Cash advanced to Redwood Analytics Europe Ltd and not yet repaid", OPENED, 1400),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from clients and owed to the state", OPENED, 2100),
    Account("Income:Consulting-Fees", K.INCOME, "Consulting and analytics fees billed to clients", OPENED, 4000),
    Account("Expenses:Cost-Of-Services", K.EXPENSE, "Subcontracted work released from work in progress when an engagement is billed", OPENED, 5000),
    Account("Expenses:Rent", K.EXPENSE, "Office rent and utilities recharge for the period", OPENED, 5200),
    Account("Expenses:Software", K.EXPENSE, "Analytics platform and software subscriptions", OPENED, 5250),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:carrowmore", "Carrowmore Logistics Inc", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:ostrander", "Ostrander Medical Group", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:fenwick", "Fenwick Retail Holdings", R.CUSTOMER, 3, "net 30", "Assets:AR"),
    Party("party:redwood-europe", "Redwood Analytics Europe Ltd", R.VENDOR, 4, "intercompany", "Assets:Due-From-Subsidiary"),
    Party("party:corvallis", "Corvallis Data Engineering LLC", R.VENDOR, 5, "net 30", "Assets:Work-In-Progress"),
    Party("party:cloudspire", "Cloudspire Software", R.VENDOR, 6, "due on receipt", "Expenses:Software"),
    Party("party:talcott", "Talcott Street Properties", R.VENDOR, 7, "due on receipt", "Expenses:Rent"),
    Party("party:sequoia-coast-bank", "Sequoia Coast Bank", R.BANK, 8),
)

DOCUMENTS = (
    Document("doc:si-2071", DK.SALES_INVOICE, "SI-2071", "party:carrowmore", "2025-09-15", D("13592.50")),
    Document("doc:si-2074", DK.SALES_INVOICE, "SI-2074", "party:fenwick", "2025-09-22", D("8427.60")),
    Document("doc:si-2078", DK.SALES_INVOICE, "SI-2078", "party:ostrander", "2025-10-16", D("18934.25")),
    Document("doc:si-2081", DK.SALES_INVOICE, "SI-2081", "party:carrowmore", "2025-10-28", D("23744.00")),
    Document("doc:si-2084", DK.SALES_INVOICE, "SI-2084", "party:fenwick", "2025-11-07", D("10441.00")),
    Document("doc:si-2087", DK.SALES_INVOICE, "SI-2087", "party:carrowmore", "2025-11-18", D("15052.00")),
    Document("doc:pi-5092", DK.PURCHASE_INVOICE, "PI-5092", "party:corvallis", "2025-09-19", D("3915.00")),
    Document("doc:pi-5107", DK.PURCHASE_INVOICE, "PI-5107", "party:corvallis", "2025-10-07", D("4380.00")),
    Document("doc:pi-5121", DK.PURCHASE_INVOICE, "PI-5121", "party:corvallis", "2025-11-10", D("5265.00")),
    Document("doc:chq-3101", DK.CHEQUE, "3101", "party:talcott", "2025-10-02"),
    Document("doc:chq-3102", DK.CHEQUE, "3102", "party:redwood-europe", "2025-10-14"),
    Document("doc:chq-3103", DK.CHEQUE, "3103", "party:talcott", "2025-11-03"),
    Document("doc:chq-3104", DK.CHEQUE, "3104", "party:redwood-europe", "2025-11-06"),
    Document("doc:chq-3105", DK.CHEQUE, "3105", "party:redwood-europe", "2025-11-19"),
    Document("doc:chq-3106", DK.CHEQUE, "3106", "party:talcott", "2025-11-27"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # October 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-10", "2025-10-02", "party:talcott", D("6493.20"),
                   cheque("doc:chq-3101", "2025-10-06"), "October rent and utilities recharge, check 3101"),
    CustomerReceipt("event:si-2071-receipt", "2025-10-03", "party:carrowmore", "doc:si-2071", D("13592.50"),
                    ach_in("2025-10-03"), "Customer payment for SI-2071"),
    Purchase("event:pi-5107-purchase", "2025-10-07", "party:corvallis", "doc:pi-5107", D("4380.00"),
             "Purchase invoice PI-5107 received, data pipeline build for the Ostrander engagement"),
    ExpensePayment("event:software-2025-10", "2025-10-09", "party:cloudspire", D("1149.00"),
                   card("2025-10-10"), "Analytics platform subscription, October"),
    ExpensePayment("event:ic-3102-advance", "2025-10-14", "party:redwood-europe", D("25000.00"),
                   cheque("doc:chq-3102", "2025-10-17"),
                   "Advance to Redwood Analytics Europe Ltd, October payroll funding, check 3102"),
    VendorPayment("event:pi-5092-payment", "2025-10-20", "party:corvallis", "doc:pi-5092", D("3915.00"),
                  ach_out("2025-10-20"), "Payment of purchase invoice PI-5092"),
    CustomerReceipt("event:si-2074-receipt", "2025-10-23", "party:fenwick", "doc:si-2074", D("8427.60"),
                    ach_in("2025-10-23"), "Customer payment for SI-2074"),
    BankFee("event:fee-2025-10", "2025-10-31", D("48.00"), "Monthly account service charge"),
    # November 2025: the task period
    ExpensePayment("event:rent-2025-11", "2025-11-03", "party:talcott", D("6511.85"),
                   cheque("doc:chq-3103", "2025-11-06"), "November rent and utilities recharge, check 3103"),
    CustomerReceipt("event:si-2078-receipt", "2025-11-05", "party:ostrander", "doc:si-2078", D("18934.25"),
                    ach_in("2025-11-05"), "Customer payment for SI-2078"),
    ExpensePayment("event:ic-3104-advance", "2025-11-06", "party:redwood-europe", D("30000.00"),
                   cheque("doc:chq-3104", "2025-11-10"),
                   "Advance to Redwood Analytics Europe Ltd, November payroll funding, check 3104"),
    Sale("event:si-2084-sale", "2025-11-07", "party:fenwick", "doc:si-2084", D("9850.00"), D("0.06"), D("5120.00"),
         "Invoice SI-2084, store network demand study", "Subcontracted work released from work in progress on SI-2084"),
    Purchase("event:pi-5121-purchase", "2025-11-10", "party:corvallis", "doc:pi-5121", D("5265.00"),
             "Purchase invoice PI-5121 received, warehouse migration hours for the Carrowmore engagement"),
    ExpensePayment("event:software-2025-11", "2025-11-10", "party:cloudspire", D("1298.00"),
                   card("2025-11-11"), "Analytics platform subscription, November, two seats added"),
    CustomerReceipt("event:si-2081-receipt", "2025-11-12", "party:carrowmore", "doc:si-2081", D("23744.00"),
                    ach_in("2025-11-12"), "Customer payment for SI-2081"),
    VendorPayment("event:pi-5107-payment", "2025-11-13", "party:corvallis", "doc:pi-5107", D("4380.00"),
                  ach_out("2025-11-13"), "Payment of purchase invoice PI-5107"),
    Sale("event:si-2087-sale", "2025-11-18", "party:carrowmore", "doc:si-2087", D("14200.00"), D("0.06"), D("7360.00"),
         "Invoice SI-2087, fleet routing analytics phase two", "Subcontracted work released from work in progress on SI-2087"),
    ExpensePayment("event:ic-3105-advance", "2025-11-19", "party:redwood-europe", D("18500.00"),
                   cheque("doc:chq-3105", "2025-11-24"),
                   "Advance to Redwood Analytics Europe Ltd, supplier settlements, check 3105"),
    CustomerReceipt("event:si-2084-receipt", "2025-11-26", "party:fenwick", "doc:si-2084", D("10441.00"),
                    ach_in("2025-11-26"), "Customer payment settling SI-2084"),
    # issued in November, cleared by the bank in December: the timing difference
    Prepayment("event:rent-2025-12-prepaid", "2025-11-27", "party:talcott", D("6250.00"),
               cheque("doc:chq-3106", "2025-12-03"), "2025-12", "December base rent prepaid, check 3106"),
    BankFee("event:fee-2025-11", "2025-11-28", D("52.00"), "Monthly account service charge"),
)

WORLD = World(
    id="redwood-2025-11",
    title="Redwood Analytics Group - FY2025",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:sequoia-coast-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-10-01", D("74318.62")),
    opening=OpeningPosition("2025-11-01", (("Assets:AR", D("42678.25")),
                                           ("Assets:Work-In-Progress", D("19875.00")),
                                           ("Assets:Due-From-Subsidiary", D("112500.00")),
                                           ("Liabilities:AP", D("-4380.00")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Work-In-Progress"),
           ("prepayments", "Assets:Prepayments"), ("payables", "Liabilities:AP"),
           ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Consulting-Fees"),
           ("cogs", "Expenses:Cost-Of-Services"), ("bank_fees", "Expenses:BankFees"),
           ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

INTERCOMPANY_TRANSFERS_001 = TaskSpec(
    id="intercompany_transfers_001",
    type="bank_reconciliation",
    prompt=("Redwood Analytics Group funded its European subsidiary twice in November, but the intercompany "
            "balance on Assets:Due-From-Subsidiary does not agree with the Sequoia Coast Bank statement for "
            "November. Reconcile the checking account against the statement, correct the books under the "
            "bookkeeping policy, and write the corrected ledger back to ledger.beancount."),
    period=Period("2025-11-01", "2025-11-30", "November 2025"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_intercompany_advance", "rec:ic-3104-advance",
                        "the statement row names the payee and the check (CHECK 3104 REDWOOD ANALYTICS EUROPE LTD, "
                        "30000.00) and no ledger entry matches it; vendors.csv lists the payee with terms "
                        "intercompany and Assets:Due-From-Subsidiary as its default account, so under the "
                        "intercompany-balances section the advance is posted to that account, and the dates "
                        "section puts it on the bank's date"),
        DuplicateRecognition("duplicated_intercompany_advance", "rec:ic-3105-advance",
                             "the ledger carries the 19 November advance of 18500.00 to Redwood Analytics Europe "
                             "Ltd twice and the statement shows one CHECK 3105 row of that amount; the "
                             "intercompany-balances section says to remove one copy and leave the other as it was"),
        AlterRecognition("transposed_customer_receipt", "rec:si-2078-receipt", "transpose_digits", 2,
                         "the ledger carries the 5 November receipt from Ostrander Medical Group against SI-2078 at "
                         "18394.25 while the statement row of the same date, payer and reference (ACH IN OSTRANDER "
                         "MEDICAL GROUP, SI-2078) shows 18934.25; the customer-receipts section says to re-post the "
                         "entry with the statement's amount on the original date, against Assets:AR"),
    )),
)

TASKS = {INTERCOMPANY_TRANSFERS_001.id: INTERCOMPANY_TRANSFERS_001}
