"""Ironwood Furniture Works, October 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The month is one small furniture maker's October, seen whole: the supplier
payment run for lumber, hardware and fabric; three customers paying on
account, one of them in part and one by a check deposited too late for the
bank to show it; the running costs that go on the debit card and are booked
from the bank feed; two staff reimbursed for expense claims and a fleet fuel
card; three workshop staff paid net by check with September's withholdings
remitted to the revenue service; September's sales tax return paid to the
state; a planer and a dust extractor bought and paid on delivery and the saw
blades sent out for sharpening; two advances to the group's finishing
company; and the November insurance premium paid in advance, with two bank
charges on different days. Ironwood draws checks from two stocks - the
handwritten book (2089 onwards) for rent and for suppliers that do not take
ACH, and the system-printed stock (5082 onwards) for payroll, claims,
remittances and everything else - which is why the two number series run
side by side on one statement.

Ten tasks share this one month. Each names two or three recognitions by id
for its own workflow, drawn from never posted, keyed wrongly and posted twice.
Two timing differences are not mutations at all: the check to the fabric
supplier issued on 29 October, which the bank cleared on 4 November, and the
customer check received on 30 October, which the bank credited on
3 November. The October statement's projection classifies both
NOT_YET_SETTLED on its own.
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

POLICY_TEXT = """# Ironwood Furniture Works - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, ACH origination
fees, check printing fees, returned item fees) are recorded to
`Expenses:BankFees` on the date the bank applies them. Each charge the bank
applies is one entry, dated the day the bank shows; a charge posted twice is
corrected by removing one copy, and a charge posted with a mis-keyed amount
is re-posted with the amount the statement shows on its original date.

## Customer receipts
Cash received from a customer reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice.

## Collections
Customers buy on net 30 account and settle by ACH, quoting the sales invoice
number, or by check, which the bank prints with the customer's own check
number. A receipt is recorded on the day it is received: a debit to the
checking account and a credit to `Assets:AR`, applied to the invoice it
quotes. A customer may pay an invoice in part; the receipt is recorded for the
amount received and the balance stays open on the invoice. Nothing is written
off, netted or re-aged at the month-end.

The receivables ledger is tied to the bank statement at every close. Three
kinds of difference arise, and each has exactly one correction:

- A customer deposit that appears on the statement but was never posted is
  added to the ledger for the customer and the amount the statement shows,
  against `Assets:AR`, on the date the bank shows (see Dates below).
- A receipt that was posted twice is corrected by removing one of the two
  copies. The copy that remains is left exactly as it was.
- A receipt posted with a mis-keyed amount is corrected by re-posting the
  entry with the amount the statement shows, on the date the entry was
  originally posted. Only the amount changes; the date, the customer and the
  accounts stay as they were.

A customer check recorded as received that the bank has not credited by the
cut-off is a deposit in transit and is left as recorded.

## Payments to suppliers
The `default_account` a vendor carries in the vendor master is where that
vendor's purchases are booked when they arrive. It is not always where a
payment to that vendor lands, and the account itself says which it is.

Where a supplier's purchases are booked to `Assets:Inventory` - the lumber,
hardware and fabric suppliers - the goods were taken into that account when
they were received and a payable was raised for them at the same time, so
cash paid to that supplier afterwards settles the payable and is recorded to
`Liabilities:AP`. A supplier's invoice stays booked to `Assets:Inventory`; a
payment never touches it.

Where a vendor's purchases are booked to an expense account, no payable is
raised: the payment is the expense, and it is recorded to that vendor's own
`default_account` on the day it is paid, except where it is paid ahead of the
period it covers, which the prepayments section below governs.

Where a vendor's `default_account` is an asset account other than
`Assets:Inventory` - the equipment supplier, the group company, the insurer -
or a liability account - the revenue service, the state tax commission - the
vendor is not a trade supplier and no payable is raised for it. The payment
itself is recorded to that vendor's `default_account` on the day it is paid,
as the equipment, intercompany, prepayments, payroll and sales tax
remittance sections below set out.

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

## Check series
Ironwood draws checks on the operating account from two stocks. The
handwritten check book, numbered from 2089 upwards, is used for rent and for
the suppliers that do not accept ACH. Checks printed from the accounting
system, numbered from 5082 upwards, are used for payroll, expense claims,
tax remittances, equipment, insurance and advances to the group company. Both
series clear the same checking account and the bank prints the check number
and the payee on every check row, whichever stock it came from.

## Card spend
The workshop's running costs - the design software subscription, broadband
and phone lines, shop stationery, electricity and the fleet fuel card - are
paid on the business debit card and entered into the books from the bank
feed, so a card entry carries the date the bank shows. A card row on the
statement whose vendor is in the vendor master is booked to that vendor's
`default_account` on the bank's date. A card row the books do not carry is
added, on the bank's date, to that account. A card row the books carry with
an amount that differs from the statement's has been keyed wrongly: the
entry is re-posted with the statement's amount, on the date it was
originally entered, and the wrong figure is not left standing alongside it.
A card row whose vendor is not in the vendor master is queried with the
workshop manager before it is booked; it is never posted to a holding
account.

## Employee expense claims
Staff who visit clients and trade shows file expense claims for mileage,
lodging and meals. Each employee who files claims is set up in the vendor
master with terms `expense claim` and `Expenses:Travel` as the
`default_account`. No payable is raised for a claim: an approved claim is
reimbursed by a system-printed check and booked to the employee's
`default_account` on the date the check is issued, with the employee named as
payee exactly as the vendor master lists them; the check number is the
claim's reference on the bank statement.

A reimbursement check the statement shows that the books do not carry is
posted, on the date the bank shows, to that employee's `default_account`. A
claim the books carry twice against a single check on the statement has been
posted twice: one copy is removed and the other is left as it stands. A claim
is never split, netted against another employee's claim or held over to the
following month.

## Vehicle and fuel
The delivery van is fuelled on a fleet fuel card. The card issuer is in the
vendor master with `Expenses:Vehicle` as its `default_account` and draws the
monthly fuel bill from the operating account by debit card; the draw is
booked to `Expenses:Vehicle` on the day the bank shows it, and the card
spend section above governs a draw the books carry at the wrong amount.

## Payroll
Ironwood's workshop staff are paid monthly, on the fourth Friday of the month,
by a system-printed check for each employee's net pay. Each employee is
carried in the vendor master as a payee on `monthly payroll` terms with
`Expenses:Salaries` as the `default_account`. A net pay check is recorded as
one entry per employee, dated the day the check was written, with the
employee named as payee exactly as the vendor master lists them: a debit to
`Expenses:Salaries` and a credit to the checking account for the net amount.
No payable is raised for net pay ahead of the check.

Employee withholdings are accrued to `Liabilities:PayrollTax` by the monthly
payroll journal that the payroll bureau supplies after each close; that
journal is outside the bank reconciliation. The amount accrued for a month is
remitted to the Federal Revenue Service by check around the 15th of the
following month. The revenue service is carried in the vendor master on
`monthly remittance` terms with `Liabilities:PayrollTax` as its
`default_account`, and the remittance check settles that liability: a debit
to `Liabilities:PayrollTax` and a credit to the checking account on the day
the check is written.

The payroll postings are tied to the bank statement at every close. Two kinds
of difference arise, and each has exactly one correction:

- A net pay or remittance check that appears on the statement but that the
  books lack is added for the payee and the amount the statement shows,
  against the payee's `default_account`, on the date the bank shows (see
  Dates below).
- A net pay check posted with a mis-keyed amount is corrected by re-posting
  the entry with the amount the statement shows, on the date the entry was
  originally posted. Only the amount changes; the date, the payee and the
  accounts stay as they were.

A payroll check the books carry that the bank has not cleared at the cut-off
is an outstanding check and is left as it is.

## Equipment
Machinery for the workshop is bought from the supplier the vendor master
carries with `Assets:Equipment` as its `default_account`. Ironwood pays for a
machine by system-printed check on the day it is delivered, so the check is
the whole transaction: its amount is capitalised to `Assets:Equipment` on the
date it is paid, and depreciation is dealt with at year end, outside the
monthly close. No payable is raised and nothing passes through
`Liabilities:AP`. The vendor the master carries with `Expenses:Repairs` as
its `default_account` sharpens blades and services the machines; its charges
are maintenance, not improvements, and are expensed to `Expenses:Repairs` on
the day the card is charged.

An equipment or repair payment the statement shows and the books lack is
posted to that vendor's `default_account` on the date the bank shows. An
equipment check the books carry twice against a single check on the
statement has been posted twice: one copy is removed and the other is left as
it stands. A repair payment the books carry with an amount that differs from
the statement's has been keyed wrongly: the entry is re-posted with the
statement's amount, on the date it was originally entered.

## Intercompany balances
Ironwood Furniture Works funds its sister company, Ironwood Finishing LLC,
by system-printed check whenever the finishing shop's own collections will not
cover its wages and materials. The group company is carried in the vendor
master only so that checks can be drawn to it, and its terms read
`intercompany`. Nothing is purchased from it, no invoice is received from it
and no payable is ever raised for it. Every advance is a debit to
`Assets:Due-From-Finishing`, the `default_account` the vendor master lists
for it, and a credit to the checking account, dated the day the check was
issued, with the group company as payee. The advance is repayable and stays
on that account until it is repaid; it is never expensed, never treated as a
payable and never netted against anything else.

The intercompany balance is agreed with the finishing shop's own books at
every month-end, so `Assets:Due-From-Finishing` must carry each advance
exactly once. Three kinds of difference arise against the bank statement,
and each has exactly one correction:

- An advance that appears on the statement but that the books lack is added
  for the group company and the amount the statement shows, to
  `Assets:Due-From-Finishing`, on the date the bank shows (see Dates below).
- An advance that was posted twice is corrected by removing one of the two
  copies. The copy that remains is left exactly as it was.
- An advance posted with a mis-keyed amount is corrected by re-posting the
  entry with the amount the statement shows, on the date the entry was
  originally posted.

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
customer, vendor, employee or group-company movement the ledger date is never
later than the statement's date for the same item.

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

The workshop insurance premium is invoiced by the insurer a month in advance
and is paid by system-printed check in the month before the cover month. A
premium paid in October for November cover is booked to `Assets:Prepayments`
on the date the check is issued and released to `Expenses:Insurance` by the
November close journal, which is outside the bank reconciliation. The insurer
carries `Assets:Prepayments` as its `default_account` in the vendor master
for exactly this reason: every payment to the insurer is a payment in
advance, and the vendor master and this section agree on where it lands. No
payable is raised for a premium. A premium check the statement shows and the
books lack is added to `Assets:Prepayments` on the date the bank shows.

## Month-end close
At the close the checking account is tied to the statement in full: every
row the bank printed either matches one ledger entry or is added, and every
ledger entry the bank has not seen is either an outstanding check or a
deposit in transit. The prepayment release, the payroll accrual and
depreciation are posted by the close journal after the tie-out and are not
part of it.

## Utilities
Workshop electricity is paid by the company debit card when the bill falls
due. The utility is a supplier whose purchases are booked to an expense
account, so the card payment is the expense and is recorded to
`Expenses:Utilities` on the day the card is charged.

## Sales tax
Ironwood collects sales tax from customers at the state rate of 7% on sales of
finished furniture and owes it to the state. The tax is credited to
`Liabilities:SalesTax-Payable` on the day the sale is invoiced; it is not
revenue. The balance of that account at any date is the tax collected and not
yet remitted. Lumber, hardware and fabric bought for manufacture are exempt
under the resale certificate, so no tax is recoverable on the purchase side.

## Sales tax remittance
The State Tax Commission is carried in the vendor master with
`Liabilities:SalesTax-Payable` as its `default_account` and terms of
`monthly filing`. It is not a supplier of goods or services: a payment to the
commission is neither a purchase nor an expense. It settles the tax liability
for the month the return covers, so it is recorded as a debit to
`Liabilities:SalesTax-Payable` and a credit to the checking account, dated
the day the check was written. The return is paid by system-printed check in
the month after the tax was collected, for the amount the return reports.

When the month is closed, the tax ledger and the checking account are both
tied to the bank statement. A remittance to the commission that appears on
the statement but was never posted is added to the ledger for the amount the
statement shows, against `Liabilities:SalesTax-Payable`, on the date the bank
shows. A remittance that is on both the statement and the ledger with the
same check number and amount is a match and is not touched.

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
    Account("Assets:Due-From-Finishing", K.ASSET, "Cash advanced to Ironwood Finishing LLC and not yet repaid", OPENED, 1400),
    Account("Assets:Equipment", K.ASSET, "Workshop machinery and equipment, at cost", OPENED, 1500),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Liabilities:PayrollTax", K.LIABILITY, "Employee withholdings accrued on the payroll journal and not yet remitted", OPENED, 2200),
    Account("Income:Sales", K.INCOME, "Revenue from furniture sold", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:Salaries", K.EXPENSE, "Net pay to workshop staff", OPENED, 5100),
    Account("Expenses:Travel", K.EXPENSE, "Mileage, lodging and meals on client visits and trade shows, reimbursed on expense claims", OPENED, 5150),
    Account("Expenses:Vehicle", K.EXPENSE, "Fuel and running costs of the delivery van", OPENED, 5160),
    Account("Expenses:Rent", K.EXPENSE, "Workshop and showroom rent for the period", OPENED, 5200),
    Account("Expenses:Insurance", K.EXPENSE, "Workshop insurance premium for the month of cover", OPENED, 5210),
    Account("Expenses:Utilities", K.EXPENSE, "Workshop electricity", OPENED, 5250),
    Account("Expenses:Software", K.EXPENSE, "Design software subscriptions", OPENED, 5260),
    Account("Expenses:Telecom", K.EXPENSE, "Workshop broadband and phone lines", OPENED, 5270),
    Account("Expenses:Office", K.EXPENSE, "Shop stationery and showroom consumables", OPENED, 5280),
    Account("Expenses:Repairs", K.EXPENSE, "Blade sharpening and machine servicing", OPENED, 5290),
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
    Party("party:brackenford", "Brackenford Architects", R.CUSTOMER, 9, "net 30", "Assets:AR"),
    Party("party:kesterline", "Kesterline Woodworking Machinery", R.VENDOR, 10, "due on receipt", "Assets:Equipment"),
    Party("party:ardent-saw", "Ardent Saw and Blade Service", R.VENDOR, 11, "due on receipt", "Expenses:Repairs"),
    Party("party:ironwood-finishing", "Ironwood Finishing LLC", R.VENDOR, 12, "intercompany", "Assets:Due-From-Finishing"),
    Party("party:millhaven-mutual", "Millhaven Mutual Insurance", R.VENDOR, 13, "due on receipt", "Assets:Prepayments"),
    Party("party:sketchline", "Sketchline Design Software", R.VENDOR, 14, "due on receipt", "Expenses:Software"),
    Party("party:larchmont-telecom", "Larchmont Telecom", R.VENDOR, 15, "due on receipt", "Expenses:Telecom"),
    Party("party:hartsfield", "Hartsfield Office Products", R.VENDOR, 16, "due on receipt", "Expenses:Office"),
    Party("party:roadmark", "Roadmark Fuel Card", R.VENDOR, 17, "due on receipt", "Expenses:Vehicle"),
    Party("party:rosalind-achebe", "Rosalind Achebe", R.VENDOR, 18, "expense claim", "Expenses:Travel"),
    Party("party:tobias-lindgren", "Tobias Lindgren", R.VENDOR, 19, "expense claim", "Expenses:Travel"),
    Party("party:marguerite-okonkwo", "Marguerite Okonkwo", R.VENDOR, 20, "monthly payroll", "Expenses:Salaries"),
    Party("party:silas-brandvold", "Silas Brandvold", R.VENDOR, 21, "monthly payroll", "Expenses:Salaries"),
    Party("party:ines-carvalho", "Ines Carvalho", R.VENDOR, 22, "monthly payroll", "Expenses:Salaries"),
    Party("party:federal-revenue", "Federal Revenue Service", R.VENDOR, 23, "monthly remittance", "Liabilities:PayrollTax"),
    Party("party:state-tax-commission", "State Tax Commission", R.VENDOR, 24, "monthly filing", "Liabilities:SalesTax-Payable"),
)

DOCUMENTS = (
    # sales invoices
    Document("doc:si-3412", DK.SALES_INVOICE, "SI-3412", "party:mercer-street", "2025-08-19", D("5976.00")),
    Document("doc:si-3414", DK.SALES_INVOICE, "SI-3414", "party:mercer-street", "2025-08-25", D("7318.40")),
    Document("doc:si-3415", DK.SALES_INVOICE, "SI-3415", "party:seabright", "2025-08-28", D("8460.15")),
    Document("doc:si-3416", DK.SALES_INVOICE, "SI-3416", "party:brackenford", "2025-08-30", D("6231.90")),
    Document("doc:si-3418", DK.SALES_INVOICE, "SI-3418", "party:seabright", "2025-09-12", D("11287.50")),
    Document("doc:si-3421", DK.SALES_INVOICE, "SI-3421", "party:brackenford", "2025-09-23", D("4368.81")),
    Document("doc:si-3425", DK.SALES_INVOICE, "SI-3425", "party:mercer-street", "2025-10-09", D("9041.50")),
    Document("doc:si-3427", DK.SALES_INVOICE, "SI-3427", "party:brackenford", "2025-10-03", D("6719.60")),
    Document("doc:si-3431", DK.SALES_INVOICE, "SI-3431", "party:seabright", "2025-10-17", D("13535.50")),
    # purchase invoices
    Document("doc:pi-4458", DK.PURCHASE_INVOICE, "PI-4458", "party:pellston", "2025-08-07", D("5318.20")),
    Document("doc:pi-4461", DK.PURCHASE_INVOICE, "PI-4461", "party:wexcombe", "2025-08-13", D("2746.85")),
    Document("doc:pi-4463", DK.PURCHASE_INVOICE, "PI-4463", "party:norquist", "2025-08-12", D("3318.75")),
    Document("doc:pi-4466", DK.PURCHASE_INVOICE, "PI-4466", "party:norquist", "2025-08-26", D("1836.40")),
    Document("doc:pi-4471", DK.PURCHASE_INVOICE, "PI-4471", "party:pellston", "2025-09-04", D("6842.50")),
    Document("doc:pi-4474", DK.PURCHASE_INVOICE, "PI-4474", "party:pellston", "2025-09-18", D("2375.80")),
    Document("doc:pi-4476", DK.PURCHASE_INVOICE, "PI-4476", "party:norquist", "2025-09-11", D("2964.30")),
    Document("doc:pi-4482", DK.PURCHASE_INVOICE, "PI-4482", "party:wexcombe", "2025-09-17", D("4187.90")),
    Document("doc:pi-4485", DK.PURCHASE_INVOICE, "PI-4485", "party:wexcombe", "2025-09-29", D("3940.25")),
    Document("doc:pi-4490", DK.PURCHASE_INVOICE, "PI-4490", "party:pellston", "2025-10-08", D("5604.75")),
    Document("doc:pi-4496", DK.PURCHASE_INVOICE, "PI-4496", "party:norquist", "2025-10-15", D("3472.10")),
    Document("doc:pi-4501", DK.PURCHASE_INVOICE, "PI-4501", "party:wexcombe", "2025-10-22", D("2318.60")),
    # the handwritten check book: rent and suppliers that do not take ACH
    Document("doc:chq-2089", DK.CHEQUE, "2089", "party:sawyer-lane", "2025-09-02"),
    Document("doc:chq-2090", DK.CHEQUE, "2090", "party:wexcombe", "2025-09-12"),
    Document("doc:chq-2091", DK.CHEQUE, "2091", "party:sawyer-lane", "2025-10-02"),
    Document("doc:chq-2092", DK.CHEQUE, "2092", "party:wexcombe", "2025-10-16"),
    Document("doc:chq-2093", DK.CHEQUE, "2093", "party:wexcombe", "2025-10-29"),
    # the system-printed check stock: payroll, claims, remittances, equipment, insurance, advances
    Document("doc:chq-5082", DK.CHEQUE, "5082", "party:ironwood-finishing", "2025-09-03"),
    Document("doc:chq-5083", DK.CHEQUE, "5083", "party:rosalind-achebe", "2025-09-10"),
    Document("doc:chq-5084", DK.CHEQUE, "5084", "party:federal-revenue", "2025-09-15"),
    Document("doc:chq-5085", DK.CHEQUE, "5085", "party:state-tax-commission", "2025-09-16"),
    Document("doc:chq-5086", DK.CHEQUE, "5086", "party:millhaven-mutual", "2025-09-24"),
    Document("doc:chq-5087", DK.CHEQUE, "5087", "party:marguerite-okonkwo", "2025-09-26"),
    Document("doc:chq-5088", DK.CHEQUE, "5088", "party:silas-brandvold", "2025-09-26"),
    Document("doc:chq-5089", DK.CHEQUE, "5089", "party:ines-carvalho", "2025-09-26"),
    Document("doc:chq-5090", DK.CHEQUE, "5090", "party:kesterline", "2025-10-01"),
    Document("doc:chq-5091", DK.CHEQUE, "5091", "party:rosalind-achebe", "2025-10-06"),
    Document("doc:chq-5092", DK.CHEQUE, "5092", "party:ironwood-finishing", "2025-10-07"),
    Document("doc:chq-5093", DK.CHEQUE, "5093", "party:state-tax-commission", "2025-10-10"),
    Document("doc:chq-5094", DK.CHEQUE, "5094", "party:federal-revenue", "2025-10-14"),
    Document("doc:chq-5095", DK.CHEQUE, "5095", "party:tobias-lindgren", "2025-10-20"),
    Document("doc:chq-5096", DK.CHEQUE, "5096", "party:millhaven-mutual", "2025-10-20"),
    Document("doc:chq-5097", DK.CHEQUE, "5097", "party:kesterline", "2025-10-21"),
    Document("doc:chq-5098", DK.CHEQUE, "5098", "party:marguerite-okonkwo", "2025-10-24"),
    Document("doc:chq-5099", DK.CHEQUE, "5099", "party:silas-brandvold", "2025-10-24"),
    Document("doc:chq-5100", DK.CHEQUE, "5100", "party:ines-carvalho", "2025-10-24"),
    Document("doc:chq-5101", DK.CHEQUE, "5101", "party:ironwood-finishing", "2025-10-27"),
    # customers' own checks, deposited to the operating account
    Document("doc:chq-7690", DK.CHEQUE, "7690", "party:brackenford", "2025-09-16"),
    Document("doc:chq-7712", DK.CHEQUE, "7712", "party:brackenford", "2025-10-09"),
    Document("doc:chq-7738", DK.CHEQUE, "7738", "party:brackenford", "2025-10-30"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # September 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-09", "2025-09-02", "party:sawyer-lane", D("4250.00"),
                   cheque("doc:chq-2089", "2025-09-05"), "September rent, workshop and showroom"),
    ExpensePayment("event:ic-5082-advance", "2025-09-03", "party:ironwood-finishing", D("5000.00"),
                   cheque("doc:chq-5082", "2025-09-08"), "Intercompany advance to Ironwood Finishing LLC, check 5082"),
    Purchase("event:pi-4471-purchase", "2025-09-04", "party:pellston", "doc:pi-4471", D("6842.50"),
             "Purchase invoice PI-4471 received, white oak and walnut boards"),
    ExpensePayment("event:software-2025-09", "2025-09-05", "party:sketchline", D("149.00"),
                   card("2025-09-05"), "Design software subscription, September"),
    VendorPayment("event:pi-4458-payment", "2025-09-08", "party:pellston", "doc:pi-4458", D("5318.20"),
                  ach_out("2025-09-08"), "Payment of purchase invoice PI-4458"),
    ExpensePayment("event:telecom-2025-09", "2025-09-08", "party:larchmont-telecom", D("218.37"),
                   card("2025-09-08"), "Workshop broadband and phone lines, September"),
    ExpensePayment("event:claim-5083-achebe", "2025-09-10", "party:rosalind-achebe", D("412.60"),
                   cheque("doc:chq-5083", "2025-09-15"), "Expense claim, August showroom visits, check 5083"),
    CustomerReceipt("event:si-3412-receipt", "2025-09-11", "party:mercer-street", "doc:si-3412", D("5976.00"),
                    ach_in("2025-09-11"), "Customer payment for SI-3412"),
    Purchase("event:pi-4476-purchase", "2025-09-11", "party:norquist", "doc:pi-4476", D("2964.30"),
             "Purchase invoice PI-4476 received, drawer slides and hinges"),
    VendorPayment("event:pi-4461-payment", "2025-09-12", "party:wexcombe", "doc:pi-4461", D("2746.85"),
                  cheque("doc:chq-2090", "2025-09-17"), "Payment of purchase invoice PI-4461, check 2090"),
    ExpensePayment("event:repairs-2025-09", "2025-09-12", "party:ardent-saw", D("264.80"),
                   card("2025-09-12"), "Blade sharpening, table saw and jointer knives"),
    ExpensePayment("event:payrolltax-2025-08-remit", "2025-09-15", "party:federal-revenue", D("2286.40"),
                   cheque("doc:chq-5084", "2025-09-18"), "August payroll withholdings remitted, check 5084"),
    CustomerReceipt("event:si-3416-receipt", "2025-09-16", "party:brackenford", "doc:si-3416", D("6231.90"),
                    cheque("doc:chq-7690", "2025-09-16"), "Customer check 7690 settling SI-3416"),
    ExpensePayment("event:salestax-2025-08-remit", "2025-09-16", "party:state-tax-commission", D("964.25"),
                   cheque("doc:chq-5085", "2025-09-22"), "August sales tax return, check 5085"),
    Purchase("event:pi-4482-purchase", "2025-09-17", "party:wexcombe", "doc:pi-4482", D("4187.90"),
             "Purchase invoice PI-4482 received, upholstery fabric and webbing"),
    Purchase("event:pi-4474-purchase", "2025-09-18", "party:pellston", "doc:pi-4474", D("2375.80"),
             "Purchase invoice PI-4474 received, maple boards"),
    ExpensePayment("event:utilities-2025-09", "2025-09-19", "party:cottonwood", D("612.44"),
                   card("2025-09-20"), "Workshop electricity, September"),
    ExpensePayment("event:fuel-2025-09", "2025-09-08", "party:roadmark", D("336.18"),
                   card("2025-09-08"), "Fleet fuel card, August fuel"),
    CustomerReceipt("event:si-3415-receipt", "2025-09-23", "party:seabright", "doc:si-3415", D("8460.15"),
                    ach_in("2025-09-23"), "Customer payment for SI-3415"),
    Prepayment("event:insurance-2025-10-prepaid", "2025-09-24", "party:millhaven-mutual", D("738.50"),
               cheque("doc:chq-5086", "2025-09-29"), "2025-10", "October workshop insurance premium, paid in advance, check 5086"),
    CustomerReceipt("event:si-3414-receipt", "2025-09-25", "party:mercer-street", "doc:si-3414", D("7318.40"),
                    ach_in("2025-09-25"), "Customer payment for SI-3414"),
    ExpensePayment("event:office-2025-09", "2025-09-25", "party:hartsfield", D("187.42"),
                   card("2025-09-25"), "Showroom price cards and shop stationery"),
    VendorPayment("event:pi-4463-payment", "2025-09-26", "party:norquist", "doc:pi-4463", D("3318.75"),
                  ach_out("2025-09-26"), "Payment of purchase invoice PI-4463"),
    ExpensePayment("event:pay-2025-09-okonkwo", "2025-09-26", "party:marguerite-okonkwo", D("3184.27"),
                   cheque("doc:chq-5087", "2025-09-29"), "September net pay, check 5087"),
    ExpensePayment("event:pay-2025-09-brandvold", "2025-09-26", "party:silas-brandvold", D("2871.53"),
                   cheque("doc:chq-5088", "2025-09-30"), "September net pay, check 5088"),
    ExpensePayment("event:pay-2025-09-carvalho", "2025-09-26", "party:ines-carvalho", D("2456.09"),
                   cheque("doc:chq-5089", "2025-09-30"), "September net pay, check 5089"),
    Purchase("event:pi-4485-purchase", "2025-09-29", "party:wexcombe", "doc:pi-4485", D("3940.25"),
             "Purchase invoice PI-4485 received, leather hides"),
    BankFee("event:fee-2025-09", "2025-09-30", D("61.50"), "Monthly service charge and ACH origination fees"),
    # October 2025: the task period
    ExpensePayment("event:planer-2025-10", "2025-10-01", "party:kesterline", D("8740.00"),
                   cheque("doc:chq-5090", "2025-10-03"), "Thickness planer, paid on delivery, check 5090"),
    ExpensePayment("event:rent-2025-10", "2025-10-02", "party:sawyer-lane", D("4377.50"),
                   cheque("doc:chq-2091", "2025-10-07"), "October rent, lease escalation from 1 October"),
    ExpensePayment("event:software-2025-10", "2025-10-02", "party:sketchline", D("154.00"),
                   card("2025-10-02"), "Design software subscription, October"),
    Sale("event:si-3427-sale", "2025-10-03", "party:brackenford", "doc:si-3427", D("6280.00"), D("0.07"), D("3890.00"),
         "Sale SI-3427, reception desk and credenza", "Cost of goods sold on SI-3427"),
    VendorPayment("event:pi-4471-payment", "2025-10-06", "party:pellston", "doc:pi-4471", D("6842.50"),
                  ach_out("2025-10-06"), "Payment of purchase invoice PI-4471"),
    ExpensePayment("event:claim-5091-achebe", "2025-10-06", "party:rosalind-achebe", D("386.15"),
                   cheque("doc:chq-5091", "2025-10-08"), "Expense claim, September client visits, check 5091"),
    ExpensePayment("event:ic-5092-advance", "2025-10-07", "party:ironwood-finishing", D("4200.00"),
                   cheque("doc:chq-5092", "2025-10-10"), "Intercompany advance to Ironwood Finishing LLC, check 5092"),
    VendorPayment("event:pi-4466-payment", "2025-10-07", "party:norquist", "doc:pi-4466", D("1836.40"),
                  ach_out("2025-10-07"), "Payment of purchase invoice PI-4466"),
    ExpensePayment("event:repairs-2025-10", "2025-10-07", "party:ardent-saw", D("296.45"),
                   card("2025-10-07"), "Blade sharpening and bandsaw guide replacement"),
    Purchase("event:pi-4490-purchase", "2025-10-08", "party:pellston", "doc:pi-4490", D("5604.75"),
             "Purchase invoice PI-4490 received, cherry and ash boards"),
    Sale("event:si-3425-sale", "2025-10-09", "party:mercer-street", "doc:si-3425", D("8450.00"), D("0.07"), D("5215.00"),
         "Sale SI-3425, dining table and eight chairs", "Cost of goods sold on SI-3425"),
    CustomerReceipt("event:si-3421-receipt", "2025-10-09", "party:brackenford", "doc:si-3421", D("4368.81"),
                    cheque("doc:chq-7712", "2025-10-09"), "Customer check 7712 settling SI-3421"),
    ExpensePayment("event:salestax-2025-09-remit", "2025-10-10", "party:state-tax-commission", D("1130.95"),
                   cheque("doc:chq-5093", "2025-10-15"), "September sales tax return, check 5093"),
    ExpensePayment("event:telecom-2025-10", "2025-10-13", "party:larchmont-telecom", D("221.84"),
                   card("2025-10-13"), "Workshop broadband and phone lines, October"),
    CustomerReceipt("event:si-3418-receipt", "2025-10-14", "party:seabright", "doc:si-3418", D("11287.50"),
                    ach_in("2025-10-14"), "Customer payment for SI-3418"),
    ExpensePayment("event:payrolltax-2025-09-remit", "2025-10-14", "party:federal-revenue", D("2415.60"),
                   cheque("doc:chq-5094", "2025-10-16"), "September payroll withholdings remitted, check 5094"),
    Purchase("event:pi-4496-purchase", "2025-10-15", "party:norquist", "doc:pi-4496", D("3472.10"),
             "Purchase invoice PI-4496 received, brass pulls and levelers"),
    VendorPayment("event:pi-4482-payment", "2025-10-16", "party:wexcombe", "doc:pi-4482", D("4187.90"),
                  cheque("doc:chq-2092", "2025-10-21"), "Payment of purchase invoice PI-4482, check 2092"),
    BankFee("event:fee-2025-10-printing", "2025-10-17", D("48.75"), "Check printing fee"),
    Sale("event:si-3431-sale", "2025-10-17", "party:seabright", "doc:si-3431", D("12650.00"), D("0.07"), D("7960.00"),
         "Sale SI-3431, guest room casegoods, first delivery", "Cost of goods sold on SI-3431"),
    VendorPayment("event:pi-4474-payment", "2025-10-20", "party:pellston", "doc:pi-4474", D("2375.80"),
                  ach_out("2025-10-20"), "Payment of purchase invoice PI-4474"),
    ExpensePayment("event:claim-5095-lindgren", "2025-10-20", "party:tobias-lindgren", D("529.40"),
                   cheque("doc:chq-5095", "2025-10-22"), "Expense claim, trade show travel and lodging, check 5095"),
    Prepayment("event:insurance-2025-11-prepaid", "2025-10-20", "party:millhaven-mutual", D("742.10"),
               cheque("doc:chq-5096", "2025-10-23"), "2025-11", "November workshop insurance premium, paid in advance, check 5096"),
    ExpensePayment("event:utilities-2025-10", "2025-10-21", "party:cottonwood", D("587.19"),
                   card("2025-10-22"), "Workshop electricity, October"),
    ExpensePayment("event:fuel-2025-10", "2025-10-06", "party:roadmark", D("348.62"),
                   card("2025-10-06"), "Fleet fuel card, September fuel"),
    ExpensePayment("event:extractor-2025-10", "2025-10-21", "party:kesterline", D("2385.00"),
                   cheque("doc:chq-5097", "2025-10-24"), "Dust extraction unit, paid on delivery, check 5097"),
    Purchase("event:pi-4501-purchase", "2025-10-22", "party:wexcombe", "doc:pi-4501", D("2318.60"),
             "Purchase invoice PI-4501 received, linen and foam"),
    ExpensePayment("event:office-2025-10", "2025-10-14", "party:hartsfield", D("173.29"),
                   card("2025-10-14"), "Finish sample binders and shop stationery"),
    ExpensePayment("event:pay-2025-10-okonkwo", "2025-10-24", "party:marguerite-okonkwo", D("3207.64"),
                   cheque("doc:chq-5098", "2025-10-29"), "October net pay, check 5098"),
    ExpensePayment("event:pay-2025-10-brandvold", "2025-10-24", "party:silas-brandvold", D("2893.18"),
                   cheque("doc:chq-5099", "2025-10-30"), "October net pay, check 5099"),
    ExpensePayment("event:pay-2025-10-carvalho", "2025-10-24", "party:ines-carvalho", D("2461.75"),
                   cheque("doc:chq-5100", "2025-10-31"), "October net pay, check 5100"),
    VendorPayment("event:pi-4476-payment", "2025-10-27", "party:norquist", "doc:pi-4476", D("2964.30"),
                  ach_out("2025-10-27"), "Payment of purchase invoice PI-4476"),
    ExpensePayment("event:ic-5101-advance", "2025-10-27", "party:ironwood-finishing", D("2750.00"),
                   cheque("doc:chq-5101", "2025-10-30"), "Intercompany advance to Ironwood Finishing LLC, check 5101"),
    CustomerReceipt("event:si-3425-receipt", "2025-10-28", "party:mercer-street", "doc:si-3425", D("9041.50"),
                    ach_in("2025-10-28"), "Customer payment settling SI-3425"),
    # issued in October, cleared by the bank in November: the timing difference
    VendorPayment("event:pi-4485-payment", "2025-10-29", "party:wexcombe", "doc:pi-4485", D("3940.25"),
                  cheque("doc:chq-2093", "2025-11-04"), "Payment of purchase invoice PI-4485, check 2093"),
    CustomerReceipt("event:si-3431-receipt-part", "2025-10-30", "party:seabright", "doc:si-3431", D("8100.00"),
                    ach_in("2025-10-30"), "Partial payment against SI-3431"),
    # received in October, credited by the bank in November: the deposit in transit
    CustomerReceipt("event:si-3427-receipt", "2025-10-30", "party:brackenford", "doc:si-3427", D("6719.60"),
                    cheque("doc:chq-7738", "2025-11-03"), "Customer check 7738 settling SI-3427"),
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
    opening=OpeningPosition("2025-10-01", (("Assets:AR", D("18981.56")), ("Assets:Inventory", D("38450.00")),
                                           ("Assets:Due-From-Finishing", D("5000.00")),
                                           ("Assets:Equipment", D("58620.00")),
                                           ("Liabilities:AP", D("-22147.15")),
                                           ("Liabilities:SalesTax-Payable", D("-1130.95")),
                                           ("Liabilities:PayrollTax", D("-2415.60")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

OCTOBER = Period("2025-10-01", "2025-10-31", "October 2025")

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

BANK_RECON_IRONWOOD = TaskSpec(
    id="bank_recon_ironwood",
    type="bank_reconciliation",
    prompt=("The October statement for the Tamarack Valley Bank checking account is in and the month-end tie-out "
            "does not balance: the difference is spread across a customer deposit, a supplier check and a bank "
            "charge. Reconcile the checking account to the statement line by line, correct the ledger under the "
            "bookkeeping policy, leave the timing differences as they are, and write the corrected ledger back "
            "to ledger.beancount."),
    period=OCTOBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_check", "rec:si-3421-receipt",
                        "the statement row CHECK 7712 BRACKENFORD ARCHITECTS credits 4368.81 on 2025-10-09 and no "
                        "ledger entry matches it; customers.csv maps Brackenford Architects to Assets:AR and the "
                        "customer-receipts and collections sections post a missing deposit against Assets:AR on the "
                        "bank's date"),
        AlterRecognition("transposed_supplier_check", "rec:pi-4482-payment", "transpose_digits", 2,
                         "the ledger carries check 2092 to Wexcombe Upholstery Fabrics for PI-4482 at 4178.90 on "
                         "16 October while the statement row CHECK 2092 WEXCOMBE UPHOLSTERY FABRICS on 2025-10-21 "
                         "shows 4187.90; the check number ties the two, and the payment-runs section re-posts the "
                         "entry with the statement's amount on the original date, against Liabilities:AP"),
        OmitRecognition("unrecorded_check_printing_fee", "rec:fee-2025-10-printing",
                        "the statement row CHECK PRINTING FEE of 48.75 on 2025-10-17 is a bank-initiated charge with "
                        "no counterparty and no ledger entry matches it; policy.md's bank service charges section "
                        "records bank fees to Expenses:BankFees on the date applied"),
    )),
)

AR_COLLECTIONS_IRONWOOD = TaskSpec(
    id="ar_collections_ironwood",
    type="bank_reconciliation",
    prompt=("October's collections have been posted from the remittance advices, and the receivables ledger does "
            "not agree with the Tamarack Valley Bank statement for October. Three customers paid on account this "
            "month, one of them in part, and a customer check received on 30 October had not reached the bank by "
            "the cut-off. Reconcile the customer receipts against the statement, correct the ledger under the "
            "bookkeeping policy, and write the corrected ledger back to ledger.beancount."),
    period=OCTOBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_ach", "rec:si-3425-receipt",
                        "the statement row ACH IN MERCER STREET INTERIORS quoting SI-3425 credits 9041.50 on "
                        "2025-10-28 and no ledger entry matches it; customers.csv maps Mercer Street Interiors to "
                        "Assets:AR, the ledger carries the open sale SI-3425, and the collections section posts a "
                        "missing deposit against Assets:AR on the bank's date"),
        AlterRecognition("transposed_customer_ach", "rec:si-3418-receipt", "transpose_digits", 1,
                         "the ledger carries the 14 October receipt from Seabright Hospitality Group for SI-3418 at "
                         "12187.50 while the statement row ACH IN SEABRIGHT HOSPITALITY GROUP of the same date and "
                         "reference shows 11287.50; the collections section re-posts the entry with the statement's "
                         "amount on the original date, against Assets:AR"),
        DuplicateRecognition("duplicated_partial_receipt", "rec:si-3431-receipt-part",
                             "the ledger carries the 30 October partial payment of 8100.00 from Seabright Hospitality "
                             "Group against SI-3431 twice and the statement shows one ACH IN row of that amount; the "
                             "collections section removes one copy and leaves the other as it was"),
    )),
)

BANK_FEED_CATEGORISATION_IRONWOOD = TaskSpec(
    id="bank_feed_categorisation_ironwood",
    type="bank_reconciliation",
    prompt=("The debit card spend for October was keyed from the Tamarack Valley Bank feed and the card entries do "
            "not agree with the October statement. Go through every DEBIT CARD row, book each one to the vendor's "
            "default account from the vendor master as the card spend policy requires, correct the entries that "
            "were keyed wrongly or not at all, and write the corrected ledger back to ledger.beancount."),
    period=OCTOBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_software_card", "rec:software-2025-10",
                        "the statement row DEBIT CARD SKETCHLINE DESIGN SOFTWARE of 154.00 on 2025-10-02 answers no "
                        "ledger entry; vendors.csv maps Sketchline Design Software to Expenses:Software and policy.md's "
                        "card spend section books a missing card row to that account on the bank's date"),
        OmitRecognition("unrecorded_telecom_card", "rec:telecom-2025-10",
                        "the statement row DEBIT CARD LARCHMONT TELECOM of 221.84 on 2025-10-13 answers no ledger "
                        "entry; vendors.csv maps Larchmont Telecom to Expenses:Telecom and policy.md's card spend "
                        "section books a missing card row to that account on the bank's date"),
        AlterRecognition("miskeyed_office_card", "rec:office-2025-10", "drop_digit", 2,
                         "the statement row DEBIT CARD HARTSFIELD OFFICE PRODUCTS of 173.29 on 2025-10-14 answers the "
                         "ledger's same-day Hartsfield Office Products entry of 17.29 and no other; vendors.csv maps "
                         "Hartsfield Office Products to Expenses:Office and the card spend section re-posts a "
                         "mis-keyed card row with the statement's amount on its original date"),
    )),
)

EXPENSE_REPORTS_IRONWOOD = TaskSpec(
    id="expense_reports_ironwood",
    type="bank_reconciliation",
    prompt=("Two expense claims were reimbursed by check in October and the fleet fuel card was drawn on the 6th, "
            "and the expense ledger does not agree with the Tamarack Valley Bank statement for October. Check each "
            "reimbursement check and the fuel card draw against the statement, correct the entries under the "
            "employee expense claims and vehicle policies, and write the corrected ledger back to "
            "ledger.beancount."),
    period=OCTOBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_claim_check", "rec:claim-5091-achebe",
                        "the statement row CHECK 5091 ROSALIND ACHEBE of 386.15 on 2025-10-08 answers no ledger "
                        "entry; vendors.csv carries Rosalind Achebe on expense claim terms with Expenses:Travel and "
                        "policy.md's employee expense claims section posts a missing reimbursement check to that "
                        "account on the bank's date"),
        DuplicateRecognition("duplicated_claim_check", "rec:claim-5095-lindgren",
                             "the ledger carries the 20 October reimbursement of Tobias Lindgren by check 5095 for "
                             "529.40 twice and the statement shows one CHECK 5095 TOBIAS LINDGREN row; the employee "
                             "expense claims section removes one copy and leaves the other as it stands"),
        AlterRecognition("transposed_fuel_card", "rec:fuel-2025-10", "transpose_digits", 1,
                         "the statement row DEBIT CARD ROADMARK FUEL CARD of 348.62 on 2025-10-06 answers the ledger's "
                         "same-day Roadmark Fuel Card entry of 384.62 and no other; vendors.csv maps Roadmark Fuel "
                         "Card to Expenses:Vehicle and the vehicle and fuel section re-posts a mis-keyed draw with the "
                         "statement's amount on its original date"),
    )),
)

PAYROLL_IRONWOOD = TaskSpec(
    id="payroll_ironwood",
    type="bank_reconciliation",
    prompt=("October payroll was paid by check on Friday the 24th and September's withholdings were remitted to "
            "the Federal Revenue Service mid-month, but the payroll postings do not agree with the Tamarack Valley "
            "Bank statement for October. Tie each net pay check and the remittance check to the statement, correct "
            "the ledger under the payroll policy, and write the corrected ledger back to ledger.beancount."),
    period=OCTOBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_net_pay_check", "rec:pay-2025-10-okonkwo",
                        "the statement row CHECK 5098 MARGUERITE OKONKWO of 3207.64 on 2025-10-29 answers no ledger "
                        "entry; vendors.csv carries Marguerite Okonkwo on monthly payroll terms with "
                        "Expenses:Salaries and policy.md's payroll section posts a missing net pay check to that "
                        "account on the bank's date"),
        AlterRecognition("transposed_net_pay_check", "rec:pay-2025-10-brandvold", "transpose_digits", 2,
                         "the ledger carries check 5099 to Silas Brandvold for October net pay at 2839.18 on "
                         "24 October while the statement row CHECK 5099 SILAS BRANDVOLD on 2025-10-30 shows 2893.18; "
                         "the check number ties the two, and the payroll section re-posts the entry with the "
                         "statement's amount on the original date, against Expenses:Salaries"),
        OmitRecognition("unrecorded_withholdings_remittance", "rec:payrolltax-2025-09-remit",
                        "the statement row CHECK 5094 FEDERAL REVENUE SERVICE of 2415.60 on 2025-10-16 answers no "
                        "ledger entry; vendors.csv carries the Federal Revenue Service with Liabilities:PayrollTax "
                        "and policy.md's payroll section settles that liability with the remittance check on the "
                        "bank's date"),
    )),
)

SALES_TAX_REMITTANCE_IRONWOOD = TaskSpec(
    id="sales_tax_remittance_ironwood",
    type="bank_reconciliation",
    prompt=("September's sales tax return was filed and paid to the State Tax Commission in October, and the tax "
            "ledger does not agree with the Tamarack Valley Bank statement for October. Confirm the remittance "
            "check against the statement, check the October customer deposits and bank charges that sit alongside "
            "it, correct the ledger under the sales tax and remittance policies, and write the corrected ledger "
            "back to ledger.beancount."),
    period=OCTOBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_sales_tax_remittance", "rec:salestax-2025-09-remit",
                        "the statement row CHECK 5093 STATE TAX COMMISSION of 1130.95 on 2025-10-15 answers no ledger "
                        "entry; vendors.csv carries the State Tax Commission on monthly filing terms with "
                        "Liabilities:SalesTax-Payable and policy.md's sales tax remittance section settles that "
                        "liability with the remittance check on the bank's date"),
        AlterRecognition("transposed_customer_receipt", "rec:si-3418-receipt", "transpose_digits", 3,
                         "the ledger carries the 14 October receipt from Seabright Hospitality Group for SI-3418 at "
                         "11278.50 while the statement row ACH IN SEABRIGHT HOSPITALITY GROUP of the same date and "
                         "reference shows 11287.50; the collections section re-posts the entry with the statement's "
                         "amount on the original date, against Assets:AR"),
        DuplicateRecognition("duplicated_service_charge", "rec:fee-2025-10",
                             "the ledger carries the 31 October MONTHLY SERVICE CHARGE AND ACH ORIGINATION FEES of "
                             "72.00 twice and the statement shows one such row; the bank service charges section "
                             "removes one copy and leaves the other as it was"),
    )),
)

FIXED_ASSETS_IRONWOOD = TaskSpec(
    id="fixed_assets_ironwood",
    type="bank_reconciliation",
    prompt=("Two machines were delivered to the workshop in October and paid by check on delivery, and the saw "
            "blades went out for sharpening on the card; neither the equipment register nor the checking account "
            "agrees with the Tamarack Valley Bank statement for October. Reconcile the equipment checks and the "
            "repair charge against the statement, capitalise or expense each one as the equipment policy directs, "
            "and write the corrected ledger back to ledger.beancount."),
    period=OCTOBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_equipment_check", "rec:planer-2025-10",
                        "the statement row CHECK 5090 KESTERLINE WOODWORKING MACHINERY of 8740.00 on 2025-10-03 "
                        "answers no ledger entry; vendors.csv maps Kesterline Woodworking Machinery to "
                        "Assets:Equipment, the ledger already books the 21 October check to that supplier there, "
                        "and policy.md's equipment section capitalises a missing equipment check to that account on "
                        "the bank's date"),
        AlterRecognition("transposed_repair_card", "rec:repairs-2025-10", "transpose_digits", 2,
                         "the statement row DEBIT CARD ARDENT SAW AND BLADE SERVICE of 296.45 on 2025-10-07 answers "
                         "the ledger's same-day Ardent Saw and Blade Service entry of 294.65 and no other; "
                         "vendors.csv maps Ardent Saw and Blade Service to Expenses:Repairs and the equipment section "
                         "re-posts a mis-keyed repair payment with the statement's amount on its original date"),
        DuplicateRecognition("duplicated_equipment_check", "rec:extractor-2025-10",
                             "the ledger carries the 21 October check 5097 to Kesterline Woodworking Machinery for "
                             "2385.00 twice and the statement shows one CHECK 5097 KESTERLINE WOODWORKING MACHINERY "
                             "row; the equipment section removes one copy and leaves the other as it stands"),
    )),
)

INTERCOMPANY_TRANSFERS_IRONWOOD = TaskSpec(
    id="intercompany_transfers_ironwood",
    type="bank_reconciliation",
    prompt=("Ironwood Finishing LLC was funded twice in October by check from the operating account, and the "
            "intercompany balance the finishing shop reports does not agree with what the ledger carries in "
            "Assets:Due-From-Finishing or with the Tamarack Valley Bank statement for October. Reconcile the "
            "advances and the customer deposits against the statement, correct the ledger under the intercompany "
            "balances policy, and write the corrected ledger back to ledger.beancount."),
    period=OCTOBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_intercompany_advance", "rec:ic-5092-advance",
                        "the statement row CHECK 5092 IRONWOOD FINISHING LLC of 4200.00 on 2025-10-10 answers no "
                        "ledger entry; vendors.csv carries Ironwood Finishing LLC on intercompany terms with "
                        "Assets:Due-From-Finishing, the ledger already books the 27 October check to it there, and "
                        "policy.md's intercompany balances section posts a missing advance to that account on the "
                        "bank's date"),
        DuplicateRecognition("duplicated_intercompany_advance", "rec:ic-5101-advance",
                             "the ledger carries the 27 October advance to Ironwood Finishing LLC by check 5101 for "
                             "2750.00 twice and the statement shows one CHECK 5101 IRONWOOD FINISHING LLC row; the "
                             "intercompany balances section removes one copy and leaves the other as it was"),
        AlterRecognition("transposed_customer_check", "rec:si-3421-receipt", "transpose_digits", 1,
                         "the ledger carries the 9 October customer check 7712 from Brackenford Architects settling "
                         "SI-3421 at 4638.81 while the statement row CHECK 7712 BRACKENFORD ARCHITECTS of the same "
                         "date shows 4368.81; the check number ties the two, and the collections section re-posts "
                         "the entry with the statement's amount on the original date, against Assets:AR"),
    )),
)

MONTH_END_CLOSE_IRONWOOD = TaskSpec(
    id="month_end_close_ironwood",
    type="bank_reconciliation",
    prompt=("October is being closed. The November insurance premium was paid in advance by check on the 20th, the "
            "bank applied two charges on different days, and the Tamarack Valley Bank statement for October does "
            "not agree with the checking account in the ledger. Tie the account out in full under the month-end "
            "close policy: book the prepayment where the prepayments section puts it, correct the bank charges and "
            "customer receipts that differ, leave the outstanding check and the deposit in transit as they are, "
            "and write the corrected ledger back to ledger.beancount."),
    period=OCTOBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_insurance_prepayment", "rec:insurance-2025-11-prepaid",
                        "the statement row CHECK 5096 MILLHAVEN MUTUAL INSURANCE of 742.10 on 2025-10-23 answers no "
                        "ledger entry; vendors.csv maps Millhaven Mutual Insurance to Assets:Prepayments and "
                        "policy.md's prepayments section books a premium check to that account on the bank's date"),
        AlterRecognition("transposed_check_printing_fee", "rec:fee-2025-10-printing", "transpose_digits", 0,
                         "the statement row CHECK PRINTING FEE of 48.75 on 2025-10-17 answers the ledger's same-day "
                         "Check printing fee entry of 84.75 and no other; policy.md's bank service charges section "
                         "names Expenses:BankFees and re-posts a mis-keyed charge with the statement's amount on its "
                         "original date"),
        DuplicateRecognition("duplicated_customer_receipt", "rec:si-3418-receipt",
                             "the ledger carries the 14 October receipt of 11287.50 from Seabright Hospitality Group "
                             "for SI-3418 twice and the statement shows one ACH IN row of that amount and reference; "
                             "the collections section removes one copy and leaves the other as it was"),
    )),
)

TASKS = {
    AP_PAYMENT_RUN_001.id: AP_PAYMENT_RUN_001,
    BANK_RECON_IRONWOOD.id: BANK_RECON_IRONWOOD,
    AR_COLLECTIONS_IRONWOOD.id: AR_COLLECTIONS_IRONWOOD,
    BANK_FEED_CATEGORISATION_IRONWOOD.id: BANK_FEED_CATEGORISATION_IRONWOOD,
    EXPENSE_REPORTS_IRONWOOD.id: EXPENSE_REPORTS_IRONWOOD,
    PAYROLL_IRONWOOD.id: PAYROLL_IRONWOOD,
    SALES_TAX_REMITTANCE_IRONWOOD.id: SALES_TAX_REMITTANCE_IRONWOOD,
    FIXED_ASSETS_IRONWOOD.id: FIXED_ASSETS_IRONWOOD,
    INTERCOMPANY_TRANSFERS_IRONWOOD.id: INTERCOMPANY_TRANSFERS_IRONWOOD,
    MONTH_END_CLOSE_IRONWOOD.id: MONTH_END_CLOSE_IRONWOOD,
}
