"""Redwood Analytics Group, November 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

Redwood Analytics Group is a small consulting parent with one operating
checking account at Sequoia Coast Bank. Its November is one month seen from
ten desks, and every task in this module shares the same statement and the
same golden facts; only the instruction and the planted items differ.

The month itself: three consulting clients invoiced with sales tax and paying
by ACH, one of them on account and one by a check deposited on the last
business day; two subcontracted data engineering firms whose invoices go to
work in progress and are settled through payables by ACH and by check; a
wholly owned subsidiary, Redwood Analytics Europe Ltd, funded by check from
the office check book whenever its own collections fall short (it sits in the
vendor master with terms `intercompany` and `Assets:Due-From-Subsidiary` as
its default account, so each advance is a two-legged expense-style payment
that lands on an asset); three salaried staff paid net by check, with the
prior month's withholdings remitted by check to the payroll tax service; two
consultants reimbursed by check for expense claims and a fleet fuel card
charged to the debit card; the analytics platform, the phones, the office
supplies and the flights on the debit card; October's sales tax return paid
online by card; two analyst workstations bought outright from the equipment
supplier and a server repair expensed; December's professional indemnity
premium paid a month ahead; the landlord paid by check, December's rent
prepaid by a check that clears in December; and two bank charges on
different dates.

Checks come from two books. The office check book (3100 series) pays rent
and the advances to the subsidiary; the system-printed 7200 series pays
everything else. Two timing differences hold for every task: the rent check
issued on 27 November clears on 3 December, and the client's check deposited
on 28 November is credited on 2 December; the November statement's
projection classifies both NOT_YET_SETTLED on its own.

Each task's mutations name recognitions by id; the original task
(`intercompany_transfers_001`) plants the first November advance unposted,
the second posted twice and one client receipt keyed with two digits
transposed, and the nine workflow tasks plant their own workflow's events.
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
Fees levied directly by the bank (monthly service charges, outgoing payment
batch fees, returned item fees) are recorded to `Expenses:BankFees` on the date
the bank applies them. The bank prints its own wording for each charge and
names no counterparty; a charge row is never a payment to a supplier. A bank
charge the statement shows and the ledger lacks is added for the statement's
amount on the statement's date; a charge posted twice has one copy removed; a
charge posted with a mis-keyed amount is re-posted with the amount the
statement shows, on the date the entry was originally posted.

## Customer receipts
Cash received from a client reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice. A receipt for
less than the invoice is a payment on account and is applied to the same
invoice for the amount received; the balance stays on `Assets:AR`. A client's
check is recorded on the day it is received and banked, with the client as
payee and the check number in the narration.

The receivables ledger is agreed to the bank statement at every month-end. A
receipt that the statement shows and the ledger carries for the same client
and invoice but for a different amount was mis-keyed: it is re-posted with
the amount the statement shows, on the date the entry was originally posted.
Only the amount changes; the client, the invoice and the accounts stay as
they were.

## Collections
Three kinds of difference arise between the statement's credits and the
receivables ledger, and each has exactly one correction:

- A client deposit that appears on the statement but that the books lack is
  added for the client and the amount the statement shows, against
  `Assets:AR` and the invoice the reference names, on the date the bank
  shows (see Dates below).
- A receipt that was posted twice is corrected by removing one of the two
  copies. The copy that remains is left exactly as it was.
- A receipt posted with a mis-keyed amount is corrected as the customer
  receipts section says.

A deposit that is on both the statement and the ledger for the same client,
reference and amount is a match and is not touched. A client's check banked
before the cut-off that the bank credits after it is a deposit in transit and
is left as it is.

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

Not every payee in the vendor master is a trade supplier. The group company,
the employees, the payroll tax service, the sales tax board, the equipment
supplier and the insurer are carried there so that checks and card payments
can be drawn to them, and the sections below say where each payment lands.
In every such case the payment is recorded to the payee's own
`default_account`, never to `Liabilities:AP`.

A group company is carried in the vendor master only so that checks can be
drawn to it, and its terms read `intercompany`. It is not a trade supplier:
nothing is purchased from it, no invoice is received from it and no payable is
ever raised for it. Cash sent to it is an advance, not a payment for goods or
services: it is booked to `Assets:Due-From-Subsidiary`, the account the vendor
master lists for it, and never to `Liabilities:AP`. The intercompany balances
section below governs it.

Redwood draws checks from two books. The office check book (3100 series) is
used for rent and for advances to the group company. Supplier settlements,
payroll, expense reimbursements, insurance premiums and equipment are paid by
system-printed checks in the 7200 series. Both books draw on the one
operating checking account.

## Payment runs
Subcontractor invoices are approved on receipt and settled in a payment run
on or before their due date, by ACH where the subcontractor accepts it and
otherwise by a 7200-series check. The bank prints the payee and the invoice
reference on an ACH row and the check number and payee on a check row. The
payables ledger is agreed to the statement at every close, and each
difference has exactly one correction:

- A settlement that appears on the statement but that the books lack is
  added for the supplier and the amount the statement shows, to
  `Liabilities:AP` against the invoice the reference or the remittance names,
  on the date the bank shows (see Dates below).
- A settlement that was posted twice is corrected by removing one of the two
  copies. The copy that remains is left exactly as it was.
- A settlement posted with a mis-keyed amount is corrected by re-posting the
  entry with the amount the statement shows, on the date the entry was
  originally posted. Only the amount changes.

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
engineering firms. A subcontractor's invoice is booked to
`Assets:Work-In-Progress` when it arrives and a payable is raised for it at
the same time. The work stays in that account until the engagement is billed,
when it is released to `Expenses:Cost-Of-Services` against the client
invoice.

## Card spend
The company debit card pays the analytics platform subscription, the office
phones and internet, office consumables, flights for client visits and the
fleet fuel card statement. Each card vendor is a supplier whose purchases are
booked to an expense account, so the card charge is the expense: it is
recorded to that vendor's own `default_account` (`Expenses:Software`,
`Expenses:Telecom`, `Expenses:Office`, `Expenses:Travel` or
`Expenses:Vehicle`, as the vendor master lists) on the day the card is
charged, with the vendor named as payee. The bank prints the vendor's name on
a DEBIT CARD row and no reference. The card spend is categorised from the
statement at every close:

- A DEBIT CARD row the ledger does not carry is added for the vendor the row
  names and the amount the row shows, to that vendor's default account, on
  the date the bank shows (see Dates below).
- A card charge posted with a mis-keyed amount is re-posted with the amount
  the statement shows, on the date the entry was originally posted.
- A card charge posted twice has one copy removed.

## Employee expense claims
Consultants who travel to client sites submit an expense claim at the end of
each month and are reimbursed by a 7200-series check in the following month.
Each claimant is carried in the vendor master as a payee on `expense claim`
terms with `Expenses:Travel` as the default account. A reimbursement check is
recorded as one entry per claim, dated the day the check was written, with
the employee named as payee exactly as the vendor master lists them: a debit
to `Expenses:Travel` and a credit to the checking account for the amount of
the check. No payable is raised for a claim ahead of the check. A
reimbursement check that appears on the statement but that the books lack is
added for the payee and the amount the statement shows, to
`Expenses:Travel`, on the date the bank shows; one posted twice has one copy
removed; one posted with a mis-keyed amount is re-posted with the amount the
statement shows on the original date.

## Vehicle and fuel
The pool car runs on a fleet fuel card whose monthly statement is paid by the
company debit card. The fuel card provider is a supplier whose purchases are
booked to `Expenses:Vehicle`, so each card payment is the expense and is
recorded to `Expenses:Vehicle` on the day the card is charged.

## Payroll
Redwood's salaried staff are paid monthly, on or about the 21st, by a
7200-series check for each employee's net pay. Each employee is carried in
the vendor master as a payee on `monthly payroll` terms with
`Expenses:Salaries` as the default account. A net pay check is recorded as
one entry per employee, dated the day the check was written, with the
employee named as payee exactly as the vendor master lists them: a debit to
`Expenses:Salaries` and a credit to the checking account for the net amount.
No payable is raised for net pay ahead of the check.

Employee withholdings and the employer's payroll taxes are accrued to
`Liabilities:PayrollTax` by the monthly payroll journal that the payroll
bureau supplies after each close; that journal is outside the bank
reconciliation. The amount accrued for a month is remitted to the Federal
Payroll Tax Service by check by the 15th of the following month. The service
is carried in the vendor master on `monthly remittance` terms with
`Liabilities:PayrollTax` as the default account, and the remittance check
settles that liability: a debit to `Liabilities:PayrollTax` and a credit to
the checking account on the day the check is written.

The payroll postings are tied to the bank statement at every close. The bank
prints the check number and the payee on each check row. A net pay or
remittance check that appears on the statement but that the books lack is
added for the payee and the amount the statement shows, against the payee's
default account, on the date the bank shows (see Dates below). A net pay
check posted with a mis-keyed amount is re-posted with the amount the
statement shows, on the date the entry was originally posted; only the amount
changes. A check that is on both the statement and the ledger with the same
payee and amount is a match and is not touched.

## Sales tax remittance
The sales tax collected on the previous month's invoices is filed with the
State Sales Tax Board by the 20th of the following month and paid online with
the company debit card when the return is filed. The board is carried in the
vendor master on `monthly filing` terms with `Liabilities:SalesTax-Payable`
as the default account. Nothing is purchased from the board and no payable is
raised: the card payment settles the liability that the previous month's
sales built up, so it is recorded as a debit to `Liabilities:SalesTax-Payable`
and a credit to the checking account on the day the card is charged, with the
board named as payee. A remittance the statement shows and the ledger lacks is
added for the board and the amount the statement shows, to
`Liabilities:SalesTax-Payable`, on the date the bank shows.

## Equipment
Workstations, servers and office equipment are bought outright from the
equipment supplier and paid by 7200-series check on delivery. The supplier is
carried in the vendor master with `Assets:Equipment` as the default account.
Nothing is booked when the equipment is ordered and no payable is raised: the
payment capitalises the equipment, as a debit to `Assets:Equipment` and a
credit to the checking account on the day the check is written, with the
supplier named as payee. Depreciation is charged at the year-end and is
outside the bank reconciliation.

Repairs and maintenance of existing equipment are not capitalised. The
repairs vendor is carried with `Expenses:Repairs` as the default account and
is paid by the company debit card, so each repair charge is recorded to
`Expenses:Repairs` on the day the card is charged. An equipment check the
statement shows and the books lack is added for the supplier and the amount
the statement shows, to `Assets:Equipment`, on the date the bank shows; a
repair charge posted with a mis-keyed amount is re-posted with the amount the
statement shows on the original date.

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
advance was drawn to a group company, a card was charged, a receipt was
received or an invoice was raised - never the date the bank processed it. A
ledger date that differs from the statement's date for the same item is not
an error and is not to be changed.

The bank processes a transaction on or after the day it happens, so for a
client, supplier, employee, tax-office or group-company movement the ledger
date is never later than the statement's date for the same item.

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

The professional indemnity premium is invoiced by the insurer a month in
advance of the cover, and the check that pays it in November for December
cover is booked to `Assets:Prepayments` on the date the check is written,
with the insurer as payee. The insurer carries `Assets:Prepayments` as its
`default_account` in the vendor master for that reason. A premium check the
statement shows and the ledger lacks is added for the insurer and the amount
the statement shows, to `Assets:Prepayments`, on the date the bank shows.
The release to expense in the month of cover is a journal outside the bank
reconciliation.

## Month-end close
The checking account is agreed to the bank statement before the month is
closed. Every difference is one of the cases the sections above describe -
an item the books lack, an item posted twice, an item posted with a mis-keyed
amount, an outstanding check or a deposit in transit - and it is corrected
exactly as the section for that kind of item says, and in no other way.

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
    Account("Assets:Equipment", K.ASSET, "Workstations, servers and office equipment at cost", OPENED, 1500),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from clients and owed to the state", OPENED, 2100),
    Account("Liabilities:PayrollTax", K.LIABILITY, "Employee withholdings and employer payroll taxes owed to the payroll tax service", OPENED, 2200),
    Account("Income:Consulting-Fees", K.INCOME, "Consulting and analytics fees billed to clients", OPENED, 4000),
    Account("Expenses:Cost-Of-Services", K.EXPENSE, "Subcontracted work released from work in progress when an engagement is billed", OPENED, 5000),
    Account("Expenses:Salaries", K.EXPENSE, "Net salaries paid to staff", OPENED, 5100),
    Account("Expenses:Rent", K.EXPENSE, "Office rent and utilities recharge for the period", OPENED, 5200),
    Account("Expenses:Software", K.EXPENSE, "Analytics platform and software subscriptions", OPENED, 5250),
    Account("Expenses:Travel", K.EXPENSE, "Flights, hotels and mileage for client visits", OPENED, 5260),
    Account("Expenses:Telecom", K.EXPENSE, "Office phones and internet", OPENED, 5270),
    Account("Expenses:Office", K.EXPENSE, "Office consumables and stationery", OPENED, 5280),
    Account("Expenses:Vehicle", K.EXPENSE, "Pool car fuel and running costs", OPENED, 5290),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Expenses:Repairs", K.EXPENSE, "Repairs and maintenance of equipment", OPENED, 5310),
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
    Party("party:pelham", "Pelham Data Labs LLC", R.VENDOR, 9, "net 30", "Assets:Work-In-Progress"),
    Party("party:larkfield", "Larkfield Communications", R.VENDOR, 10, "due on receipt", "Expenses:Telecom"),
    Party("party:ashby", "Ashby Stationery and Print", R.VENDOR, 11, "due on receipt", "Expenses:Office"),
    Party("party:coastline-air", "Coastline Air", R.VENDOR, 12, "due on receipt", "Expenses:Travel"),
    Party("party:pacific-fleet-fuel", "Pacific Fleet Fuel Card", R.VENDOR, 13, "due on receipt", "Expenses:Vehicle"),
    Party("party:ingrid-solberg", "Ingrid Solberg", R.VENDOR, 14, "expense claim", "Expenses:Travel"),
    Party("party:marcus-adeyemi", "Marcus Adeyemi", R.VENDOR, 15, "expense claim", "Expenses:Travel"),
    Party("party:priyanka-raman", "Priyanka Raman", R.VENDOR, 16, "monthly payroll", "Expenses:Salaries"),
    Party("party:tobias-lindgren", "Tobias Lindgren", R.VENDOR, 17, "monthly payroll", "Expenses:Salaries"),
    Party("party:celeste-marchand", "Celeste Marchand", R.VENDOR, 18, "monthly payroll", "Expenses:Salaries"),
    Party("party:federal-payroll-tax", "Federal Payroll Tax Service", R.VENDOR, 19, "monthly remittance", "Liabilities:PayrollTax"),
    Party("party:state-sales-tax", "State Sales Tax Board", R.VENDOR, 20, "monthly filing", "Liabilities:SalesTax-Payable"),
    Party("party:tessaro", "Tessaro Technical Hardware", R.VENDOR, 21, "due on receipt", "Assets:Equipment"),
    Party("party:grafton", "Grafton Server Repairs", R.VENDOR, 22, "due on receipt", "Expenses:Repairs"),
    Party("party:westhaven", "Westhaven Insurance Agency", R.VENDOR, 23, "due on receipt", "Assets:Prepayments"),
)

DOCUMENTS = (
    Document("doc:si-2071", DK.SALES_INVOICE, "SI-2071", "party:carrowmore", "2025-09-15", D("13592.50")),
    Document("doc:si-2074", DK.SALES_INVOICE, "SI-2074", "party:fenwick", "2025-09-22", D("8427.60")),
    Document("doc:si-2078", DK.SALES_INVOICE, "SI-2078", "party:ostrander", "2025-10-16", D("18934.25")),
    Document("doc:si-2081", DK.SALES_INVOICE, "SI-2081", "party:carrowmore", "2025-10-28", D("23744.00")),
    Document("doc:si-2084", DK.SALES_INVOICE, "SI-2084", "party:fenwick", "2025-11-07", D("10441.00")),
    Document("doc:si-2087", DK.SALES_INVOICE, "SI-2087", "party:carrowmore", "2025-11-18", D("15052.00")),
    Document("doc:si-2089", DK.SALES_INVOICE, "SI-2089", "party:ostrander", "2025-11-11", D("7844.00")),
    Document("doc:pi-5092", DK.PURCHASE_INVOICE, "PI-5092", "party:corvallis", "2025-09-19", D("3915.00")),
    Document("doc:pi-5107", DK.PURCHASE_INVOICE, "PI-5107", "party:corvallis", "2025-10-07", D("4380.00")),
    Document("doc:pi-5113", DK.PURCHASE_INVOICE, "PI-5113", "party:pelham", "2025-10-21", D("2764.50")),
    Document("doc:pi-5118", DK.PURCHASE_INVOICE, "PI-5118", "party:pelham", "2025-10-29", D("1975.00")),
    Document("doc:pi-5121", DK.PURCHASE_INVOICE, "PI-5121", "party:corvallis", "2025-11-10", D("5265.00")),
    # office check book: rent and advances to the group company
    Document("doc:chq-3101", DK.CHEQUE, "3101", "party:talcott", "2025-10-02"),
    Document("doc:chq-3102", DK.CHEQUE, "3102", "party:redwood-europe", "2025-10-14"),
    Document("doc:chq-3103", DK.CHEQUE, "3103", "party:talcott", "2025-11-03"),
    Document("doc:chq-3104", DK.CHEQUE, "3104", "party:redwood-europe", "2025-11-06"),
    Document("doc:chq-3105", DK.CHEQUE, "3105", "party:redwood-europe", "2025-11-19"),
    Document("doc:chq-3106", DK.CHEQUE, "3106", "party:talcott", "2025-11-27"),
    # system-printed checks: suppliers, payroll, claims, premiums, equipment
    Document("doc:chq-7196", DK.CHEQUE, "7196", "party:federal-payroll-tax", "2025-10-14"),
    Document("doc:chq-7197", DK.CHEQUE, "7197", "party:ingrid-solberg", "2025-10-17"),
    Document("doc:chq-7198", DK.CHEQUE, "7198", "party:priyanka-raman", "2025-10-24"),
    Document("doc:chq-7199", DK.CHEQUE, "7199", "party:tobias-lindgren", "2025-10-24"),
    Document("doc:chq-7200", DK.CHEQUE, "7200", "party:celeste-marchand", "2025-10-24"),
    Document("doc:chq-7201", DK.CHEQUE, "7201", "party:ingrid-solberg", "2025-11-03"),
    Document("doc:chq-7202", DK.CHEQUE, "7202", "party:marcus-adeyemi", "2025-11-07"),
    Document("doc:chq-7203", DK.CHEQUE, "7203", "party:pelham", "2025-11-10"),
    Document("doc:chq-7204", DK.CHEQUE, "7204", "party:federal-payroll-tax", "2025-11-13"),
    Document("doc:chq-7205", DK.CHEQUE, "7205", "party:tessaro", "2025-11-14"),
    Document("doc:chq-7206", DK.CHEQUE, "7206", "party:westhaven", "2025-11-20"),
    Document("doc:chq-7207", DK.CHEQUE, "7207", "party:priyanka-raman", "2025-11-21"),
    Document("doc:chq-7208", DK.CHEQUE, "7208", "party:tobias-lindgren", "2025-11-21"),
    Document("doc:chq-7209", DK.CHEQUE, "7209", "party:celeste-marchand", "2025-11-21"),
    # a client's own check, banked on the last business day of November
    Document("doc:chq-48213", DK.CHEQUE, "48213", "party:carrowmore", "2025-11-28"),
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
    ExpensePayment("event:telecom-2025-10", "2025-10-06", "party:larkfield", D("372.15"),
                   card("2025-10-07"), "Office phones and internet, October"),
    Purchase("event:pi-5107-purchase", "2025-10-07", "party:corvallis", "doc:pi-5107", D("4380.00"),
             "Purchase invoice PI-5107 received, data pipeline build for the Ostrander engagement"),
    ExpensePayment("event:fuel-2025-10", "2025-10-08", "party:pacific-fleet-fuel", D("164.38"),
                   card("2025-10-09"), "Fuel card statement, September fills"),
    ExpensePayment("event:software-2025-10", "2025-10-09", "party:cloudspire", D("1149.00"),
                   card("2025-10-10"), "Analytics platform subscription, October"),
    ExpensePayment("event:ic-3102-advance", "2025-10-14", "party:redwood-europe", D("25000.00"),
                   cheque("doc:chq-3102", "2025-10-17"),
                   "Advance to Redwood Analytics Europe Ltd, October payroll funding, check 3102"),
    ExpensePayment("event:payroll-tax-2025-10", "2025-10-14", "party:federal-payroll-tax", D("3548.15"),
                   cheque("doc:chq-7196", "2025-10-16"), "September payroll withholdings, monthly deposit, check 7196"),
    ExpensePayment("event:office-2025-10", "2025-10-16", "party:ashby", D("208.94"),
                   card("2025-10-17"), "Printer toner and copier paper"),
    ExpensePayment("event:claim-7197-solberg", "2025-10-17", "party:ingrid-solberg", D("587.44"),
                   cheque("doc:chq-7197", "2025-10-21"), "Expense claim, September client-site travel, check 7197"),
    VendorPayment("event:pi-5092-payment", "2025-10-20", "party:corvallis", "doc:pi-5092", D("3915.00"),
                  ach_out("2025-10-20"), "Payment of purchase invoice PI-5092"),
    ExpensePayment("event:sales-tax-2025-10", "2025-10-20", "party:state-sales-tax", D("1988.30"),
                   card("2025-10-21"), "September sales tax return, paid online"),
    Purchase("event:pi-5113-purchase", "2025-10-21", "party:pelham", "doc:pi-5113", D("2764.50"),
             "Purchase invoice PI-5113 received, survey weighting model for the Fenwick engagement"),
    CustomerReceipt("event:si-2074-receipt", "2025-10-23", "party:fenwick", "doc:si-2074", D("8427.60"),
                    ach_in("2025-10-23"), "Customer payment for SI-2074"),
    ExpensePayment("event:pay-2025-10-raman", "2025-10-24", "party:priyanka-raman", D("4206.92"),
                   cheque("doc:chq-7198", "2025-10-28"), "October net pay, principal consultant, check 7198"),
    ExpensePayment("event:pay-2025-10-lindgren", "2025-10-24", "party:tobias-lindgren", D("3662.14"),
                   cheque("doc:chq-7199", "2025-10-28"), "October net pay, analytics lead, check 7199"),
    ExpensePayment("event:pay-2025-10-marchand", "2025-10-24", "party:celeste-marchand", D("2921.08"),
                   cheque("doc:chq-7200", "2025-10-29"), "October net pay, office manager, check 7200"),
    ExpensePayment("event:travel-2025-10", "2025-10-24", "party:coastline-air", D("612.40"),
                   card("2025-10-27"), "Return flights, Ostrander site visit"),
    Purchase("event:pi-5118-purchase", "2025-10-29", "party:pelham", "doc:pi-5118", D("1975.00"),
             "Purchase invoice PI-5118 received, data labelling batch for the Ostrander engagement"),
    BankFee("event:fee-2025-10", "2025-10-31", D("48.00"), "Monthly account service charge"),
    # November 2025: the task period
    ExpensePayment("event:rent-2025-11", "2025-11-03", "party:talcott", D("6511.85"),
                   cheque("doc:chq-3103", "2025-11-06"), "November rent and utilities recharge, check 3103"),
    ExpensePayment("event:telecom-2025-11", "2025-11-03", "party:larkfield", D("381.62"),
                   card("2025-11-04"), "Office phones and internet, November"),
    ExpensePayment("event:claim-7201-solberg", "2025-11-03", "party:ingrid-solberg", D("642.18"),
                   cheque("doc:chq-7201", "2025-11-07"), "Expense claim, October client-site travel, check 7201"),
    ExpensePayment("event:fuel-2025-11", "2025-11-04", "party:pacific-fleet-fuel", D("171.93"),
                   card("2025-11-05"), "Fuel card statement, October fills"),
    CustomerReceipt("event:si-2078-receipt", "2025-11-05", "party:ostrander", "doc:si-2078", D("18934.25"),
                    ach_in("2025-11-05"), "Customer payment for SI-2078"),
    ExpensePayment("event:office-2025-11", "2025-11-05", "party:ashby", D("146.27"),
                   card("2025-11-06"), "Copier paper and desk supplies"),
    VendorPayment("event:pi-5118-payment", "2025-11-06", "party:pelham", "doc:pi-5118", D("1975.00"),
                  ach_out("2025-11-06"), "Payment of purchase invoice PI-5118"),
    ExpensePayment("event:ic-3104-advance", "2025-11-06", "party:redwood-europe", D("30000.00"),
                   cheque("doc:chq-3104", "2025-11-10"),
                   "Advance to Redwood Analytics Europe Ltd, November payroll funding, check 3104"),
    Sale("event:si-2084-sale", "2025-11-07", "party:fenwick", "doc:si-2084", D("9850.00"), D("0.06"), D("5120.00"),
         "Invoice SI-2084, store network demand study", "Subcontracted work released from work in progress on SI-2084"),
    ExpensePayment("event:claim-7202-adeyemi", "2025-11-07", "party:marcus-adeyemi", D("418.66"),
                   cheque("doc:chq-7202", "2025-11-11"), "Expense claim, October mileage and hotel, check 7202"),
    Purchase("event:pi-5121-purchase", "2025-11-10", "party:corvallis", "doc:pi-5121", D("5265.00"),
             "Purchase invoice PI-5121 received, warehouse migration hours for the Carrowmore engagement"),
    ExpensePayment("event:software-2025-11", "2025-11-10", "party:cloudspire", D("1298.00"),
                   card("2025-11-11"), "Analytics platform subscription, November, two seats added"),
    VendorPayment("event:pi-5113-payment", "2025-11-10", "party:pelham", "doc:pi-5113", D("2764.50"),
                  cheque("doc:chq-7203", "2025-11-14"), "Payment of purchase invoice PI-5113, check 7203"),
    Sale("event:si-2089-sale", "2025-11-11", "party:ostrander", "doc:si-2089", D("7400.00"), D("0.06"), D("3980.00"),
         "Invoice SI-2089, patient flow dashboard build", "Subcontracted work released from work in progress on SI-2089"),
    ExpensePayment("event:repairs-2025-11", "2025-11-11", "party:grafton", D("312.80"),
                   card("2025-11-12"), "Rack server fan and power supply replacement"),
    CustomerReceipt("event:si-2081-receipt", "2025-11-12", "party:carrowmore", "doc:si-2081", D("23744.00"),
                    ach_in("2025-11-12"), "Customer payment for SI-2081"),
    VendorPayment("event:pi-5107-payment", "2025-11-13", "party:corvallis", "doc:pi-5107", D("4380.00"),
                  ach_out("2025-11-13"), "Payment of purchase invoice PI-5107"),
    BankFee("event:fee-ach-2025-11", "2025-11-13", D("15.00"), "Outgoing payment batch fee"),
    ExpensePayment("event:payroll-tax-2025-11", "2025-11-13", "party:federal-payroll-tax", D("3612.48"),
                   cheque("doc:chq-7204", "2025-11-17"), "October payroll withholdings, monthly deposit, check 7204"),
    ExpensePayment("event:equipment-7205", "2025-11-14", "party:tessaro", D("4862.50"),
                   cheque("doc:chq-7205", "2025-11-18"), "Two analyst workstations and monitors, check 7205"),
    Sale("event:si-2087-sale", "2025-11-18", "party:carrowmore", "doc:si-2087", D("14200.00"), D("0.06"), D("7360.00"),
         "Invoice SI-2087, fleet routing analytics phase two", "Subcontracted work released from work in progress on SI-2087"),
    ExpensePayment("event:ic-3105-advance", "2025-11-19", "party:redwood-europe", D("18500.00"),
                   cheque("doc:chq-3105", "2025-11-24"),
                   "Advance to Redwood Analytics Europe Ltd, supplier settlements, check 3105"),
    CustomerReceipt("event:si-2089-partial", "2025-11-19", "party:ostrander", "doc:si-2089", D("4150.00"),
                    ach_in("2025-11-19"), "Payment on account against SI-2089"),
    ExpensePayment("event:travel-2025-11", "2025-11-19", "party:coastline-air", D("874.30"),
                   card("2025-11-20"), "Return flights, Carrowmore routing workshop"),
    ExpensePayment("event:sales-tax-2025-11", "2025-11-20", "party:state-sales-tax", D("2415.75"),
                   card("2025-11-21"), "October sales tax return, paid online"),
    Prepayment("event:insurance-2025-12-prepaid", "2025-11-20", "party:westhaven", D("1738.60"),
               cheque("doc:chq-7206", "2025-11-27"), "2025-12",
               "December professional indemnity premium prepaid, check 7206"),
    ExpensePayment("event:pay-2025-11-raman", "2025-11-21", "party:priyanka-raman", D("4218.37"),
                   cheque("doc:chq-7207", "2025-11-25"), "November net pay, principal consultant, check 7207"),
    ExpensePayment("event:pay-2025-11-lindgren", "2025-11-21", "party:tobias-lindgren", D("3675.90"),
                   cheque("doc:chq-7208", "2025-11-24"), "November net pay, analytics lead, check 7208"),
    ExpensePayment("event:pay-2025-11-marchand", "2025-11-21", "party:celeste-marchand", D("2934.55"),
                   cheque("doc:chq-7209", "2025-11-24"), "November net pay, office manager, check 7209"),
    VendorPayment("event:pi-5121-payment", "2025-11-24", "party:corvallis", "doc:pi-5121", D("5265.00"),
                  ach_out("2025-11-24"), "Payment of purchase invoice PI-5121"),
    CustomerReceipt("event:si-2084-receipt", "2025-11-26", "party:fenwick", "doc:si-2084", D("10441.00"),
                    ach_in("2025-11-26"), "Customer payment settling SI-2084"),
    # issued in November, cleared by the bank in December: the timing differences
    Prepayment("event:rent-2025-12-prepaid", "2025-11-27", "party:talcott", D("6250.00"),
               cheque("doc:chq-3106", "2025-12-03"), "2025-12", "December base rent prepaid, check 3106"),
    BankFee("event:fee-2025-11", "2025-11-28", D("52.00"), "Monthly account service charge"),
    CustomerReceipt("event:si-2087-receipt", "2025-11-28", "party:carrowmore", "doc:si-2087", D("15052.00"),
                    cheque("doc:chq-48213", "2025-12-02"), "Customer check 48213 banked, settling SI-2087"),
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
    bank_opening=BankOpening("2025-10-01", D("109864.31")),
    opening=OpeningPosition("2025-11-01", (("Assets:AR", D("42678.25")),
                                           ("Assets:Work-In-Progress", D("19875.00")),
                                           ("Assets:Due-From-Subsidiary", D("112500.00")),
                                           ("Liabilities:AP", D("-9119.50")),
                                           ("Liabilities:SalesTax-Payable", D("-2415.75")),
                                           ("Liabilities:PayrollTax", D("-3612.48")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Work-In-Progress"),
           ("prepayments", "Assets:Prepayments"), ("payables", "Liabilities:AP"),
           ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Consulting-Fees"),
           ("cogs", "Expenses:Cost-Of-Services"), ("bank_fees", "Expenses:BankFees"),
           ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

PERIOD = Period("2025-11-01", "2025-11-30", "November 2025")

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

BANK_RECON_REDWOOD = TaskSpec(
    id="bank_recon_redwood",
    type="bank_reconciliation",
    prompt=("The Sequoia Coast Bank statement for November 2025 has arrived and Redwood Analytics Group's checking "
            "account does not agree with it. Work the statement against the ledger row by row: a client deposit, a "
            "subcontractor settlement and one of the bank's own charges are where the two differ, and the rent check "
            "drawn on the 27th and the client check banked on the 28th are timing items. Correct the ledger under the "
            "bookkeeping policy, note the outstanding items, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_client_deposit", "rec:si-2084-receipt",
                        "the statement row of 26 November names the payer and the invoice (ACH IN FENWICK RETAIL "
                        "HOLDINGS, SI-2084, 10441.00) and no ledger entry matches it; customers.csv maps the client "
                        "to Assets:AR, the ledger carries the open sale SI-2084, and the collections section posts "
                        "the deposit on the bank's date"),
        AlterRecognition("miskeyed_subcontractor_settlement", "rec:pi-5107-payment", "transpose_digits", 1,
                         "the ledger carries the 13 November ACH settlement of PI-5107 to Corvallis Data Engineering "
                         "LLC at 4830.00 while the statement row of the same date, payee and reference (ACH OUT "
                         "CORVALLIS DATA ENGINEERING LLC, PI-5107) shows 4380.00; vendors.csv books the "
                         "subcontractor's purchases to Assets:Work-In-Progress, so the payments-to-suppliers section "
                         "puts the settlement on Liabilities:AP and the payment-runs section re-posts it at the "
                         "statement's amount on the original date"),
        OmitRecognition("unrecorded_service_charge", "rec:fee-2025-11",
                        "the statement row of 28 November is a bank-initiated charge with no counterparty (MONTHLY "
                        "ACCOUNT SERVICE CHARGE, 52.00) and no ledger entry matches it; the bank-service-charges "
                        "section records it to Expenses:BankFees on the date the bank applied it"),
    )),
)

AP_PAYMENT_RUN_REDWOOD = TaskSpec(
    id="ap_payment_run_redwood",
    type="bank_reconciliation",
    prompt=("Redwood Analytics Group ran its November payment runs for the subcontractors: Corvallis Data "
            "Engineering LLC was settled by ACH for PI-5107 and PI-5121, and Pelham Data Labs LLC by ACH for PI-5118 "
            "and by check 7203 for PI-5113. The "
            "payables ledger does not agree with the Sequoia Coast Bank statement for November. Tie every settlement "
            "on the statement to its invoice and its ledger entry, correct Liabilities:AP and the checking account "
            "under the bookkeeping policy, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_supplier_check", "rec:pi-5113-payment",
                        "the statement row of 14 November names the check and the payee (CHECK 7203 PELHAM DATA LABS "
                        "LLC, 2764.50) and no ledger entry matches it; vendors.csv books Pelham's purchases to "
                        "Assets:Work-In-Progress, the ledger already settles Pelham's PI-5118 to Liabilities:AP on "
                        "6 November and the opening payables carry PI-5113 for that amount, so the payment-runs "
                        "section posts the settlement to Liabilities:AP on the bank's date"),
        AlterRecognition("miskeyed_ach_settlement", "rec:pi-5107-payment", "transpose_digits", 2,
                         "the ledger carries the 13 November ACH settlement of PI-5107 to Corvallis Data Engineering "
                         "LLC at 4308.00 while the statement row of the same date, payee and reference (ACH OUT "
                         "CORVALLIS DATA ENGINEERING LLC, PI-5107) shows 4380.00, the gross of the invoice the "
                         "opening payables carry; the payment-runs section re-posts it at the statement's amount on "
                         "the original date, against Liabilities:AP"),
        DuplicateRecognition("duplicated_ach_settlement", "rec:pi-5121-payment",
                             "the ledger carries the 24 November ACH settlement of PI-5121 to Corvallis Data "
                             "Engineering LLC (5265.00) twice and the statement shows one ACH OUT row of that amount "
                             "and reference; the payment-runs section says to remove one copy and leave the other"),
    )),
)

AR_COLLECTIONS_REDWOOD = TaskSpec(
    id="ar_collections_redwood",
    type="bank_reconciliation",
    prompt=("November collections at Redwood Analytics Group: Ostrander Medical Group paid SI-2078 and then paid "
            "on account against SI-2089, Carrowmore Logistics Inc paid SI-2081 by ACH and settled SI-2087 with a "
            "check banked on the 28th, and Fenwick Retail Holdings paid SI-2084. The receivables ledger does not "
            "agree with the Sequoia Coast Bank statement for November. Apply every deposit on the statement to its "
            "invoice, correct Assets:AR and the checking account under the bookkeeping policy, treat the check "
            "still to be credited as a deposit in transit, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_payment_on_account", "rec:si-2089-partial",
                        "the statement row of 19 November names the payer and the invoice (ACH IN OSTRANDER MEDICAL "
                        "GROUP, SI-2089, 4150.00) and no ledger entry matches it; customers.csv maps the client to "
                        "Assets:AR, the ledger carries the open sale SI-2089 for more than that amount, and the "
                        "customer-receipts section applies a receipt for less than the invoice on account, on the "
                        "bank's date"),
        AlterRecognition("miskeyed_client_receipt", "rec:si-2081-receipt", "transpose_digits", 1,
                         "the ledger carries the 12 November receipt from Carrowmore Logistics Inc against SI-2081 at "
                         "27344.00 while the statement row of the same date, payer and reference (ACH IN CARROWMORE "
                         "LOGISTICS INC, SI-2081) shows 23744.00, the gross of that invoice; the customer-receipts "
                         "section re-posts the entry with the statement's amount on the original date"),
        DuplicateRecognition("duplicated_client_receipt", "rec:si-2078-receipt",
                             "the ledger carries the 5 November receipt from Ostrander Medical Group against SI-2078 "
                             "(18934.25) twice and the statement shows one ACH IN row of that amount and reference; "
                             "the collections section says to remove one copy and leave the other as it was"),
    )),
)

BANK_FEED_CATEGORISATION_REDWOOD = TaskSpec(
    id="bank_feed_categorisation_redwood",
    type="bank_reconciliation",
    prompt=("The November 2025 card spend at Redwood Analytics Group needs categorising from the Sequoia Coast Bank "
            "statement: the analytics platform, the office phones, the office supplies, the flights and the fuel "
            "card all went on the company debit card. Take each DEBIT CARD row on the statement, find or add its "
            "entry in the ledger against the expense account the vendor master gives for that vendor, correct any "
            "charge that was keyed wrongly, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("uncategorised_telecom_charge", "rec:telecom-2025-11",
                        "the statement row of 4 November names the vendor (DEBIT CARD LARKFIELD COMMUNICATIONS, "
                        "381.62) and no ledger entry matches it; vendors.csv lists Larkfield with Expenses:Telecom as "
                        "its default account, and the card-spend section posts the charge there on the bank's date"),
        OmitRecognition("uncategorised_travel_charge", "rec:travel-2025-11",
                        "the statement row of 20 November names the vendor (DEBIT CARD COASTLINE AIR, 874.30) and no "
                        "ledger entry matches it; vendors.csv lists Coastline Air with Expenses:Travel as its default "
                        "account, and the card-spend section posts the charge there on the bank's date"),
        AlterRecognition("miskeyed_software_charge", "rec:software-2025-11", "transpose_digits", 1,
                         "the ledger carries the 10 November platform subscription to Cloudspire Software at 1928.00 "
                         "while the statement row of 11 November (DEBIT CARD CLOUDSPIRE SOFTWARE) shows 1298.00; the "
                         "card-spend section re-posts the charge at the statement's amount on the original date, "
                         "against Expenses:Software"),
    )),
)

EXPENSE_REPORTS_REDWOOD = TaskSpec(
    id="expense_reports_redwood",
    type="bank_reconciliation",
    prompt=("Redwood Analytics Group reimbursed two October expense claims in November, Ingrid Solberg by check 7201 "
            "and Marcus Adeyemi by check 7202, and the fleet fuel card statement was paid on the company debit card. "
            "The claims register does not agree with the Sequoia Coast Bank statement for November. Match each "
            "reimbursement check and the fuel card charge to the statement, correct Expenses:Travel, "
            "Expenses:Vehicle and the checking account under the bookkeeping policy, and write the corrected ledger "
            "back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_reimbursement_check", "rec:claim-7201-solberg",
                        "the statement row of 7 November names the check and the payee (CHECK 7201 INGRID SOLBERG, "
                        "642.18) and no ledger entry matches it; vendors.csv lists Ingrid Solberg on expense claim "
                        "terms with Expenses:Travel as her default account, and the employee-expense-claims section "
                        "posts the reimbursement there on the bank's date"),
        DuplicateRecognition("duplicated_reimbursement_check", "rec:claim-7202-adeyemi",
                             "the ledger carries the 7 November reimbursement to Marcus Adeyemi (check 7202, 418.66) "
                             "twice and the statement shows one CHECK 7202 row of that amount; the "
                             "employee-expense-claims section says to remove one copy and leave the other"),
        AlterRecognition("miskeyed_fuel_card_charge", "rec:fuel-2025-11", "transpose_digits", 1,
                         "the ledger carries the 4 November fuel card payment to Pacific Fleet Fuel Card at 117.93 "
                         "while the statement row of 5 November (DEBIT CARD PACIFIC FLEET FUEL CARD) shows 171.93; "
                         "vendors.csv books the fuel card to Expenses:Vehicle, and the vehicle-and-fuel and card-spend "
                         "sections re-post the charge at the statement's amount on the original date"),
    )),
)

PAYROLL_REDWOOD = TaskSpec(
    id="payroll_redwood",
    type="bank_reconciliation",
    prompt=("November payroll at Redwood Analytics Group: net pay checks 7207 to 7209 were written on the 21st to "
            "Priyanka Raman, Tobias Lindgren and Celeste Marchand, and check 7204 remitted October's withholdings to "
            "the Federal Payroll Tax Service. The payroll postings do not agree with the Sequoia Coast Bank statement "
            "for November. Tie each payroll check on the statement to the ledger, correct Expenses:Salaries, "
            "Liabilities:PayrollTax and the checking account under the bookkeeping policy, and write the corrected "
            "ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_net_pay_check", "rec:pay-2025-11-raman",
                        "the statement row of 25 November names the check and the payee (CHECK 7207 PRIYANKA RAMAN, "
                        "4218.37) and no ledger entry matches it; vendors.csv lists Priyanka Raman on monthly payroll "
                        "terms with Expenses:Salaries as her default account, and the payroll section posts the net "
                        "pay there on the bank's date"),
        AlterRecognition("miskeyed_net_pay_check", "rec:pay-2025-11-lindgren", "transpose_digits", 2,
                         "the ledger carries the 21 November net pay check 7208 to Tobias Lindgren at 3657.90 while "
                         "the statement row of 24 November (CHECK 7208 TOBIAS LINDGREN) shows 3675.90; the payroll "
                         "section re-posts the entry at the statement's amount on the original date, against "
                         "Expenses:Salaries"),
        OmitRecognition("unrecorded_withholdings_remittance", "rec:payroll-tax-2025-11",
                        "the statement row of 17 November names the check and the payee (CHECK 7204 FEDERAL PAYROLL "
                        "TAX SERVICE, 3612.48) and no ledger entry matches it; vendors.csv lists the service on "
                        "monthly remittance terms with Liabilities:PayrollTax as its default account, the opening "
                        "balance carries that liability for the same amount, and the payroll section posts the "
                        "remittance against it on the bank's date"),
    )),
)

SALES_TAX_REMITTANCE_REDWOOD = TaskSpec(
    id="sales_tax_remittance_redwood",
    type="bank_reconciliation",
    prompt=("Redwood Analytics Group filed its October sales tax return with the State Sales Tax Board on 20 November "
            "and paid it online with the company debit card, and the November invoices to Fenwick Retail Holdings, "
            "Ostrander Medical Group and Carrowmore Logistics Inc carried tax at six percent. "
            "Liabilities:SalesTax-Payable and the receivables do not agree with the Sequoia Coast Bank statement for "
            "November. Confirm the remittance against the statement, agree the client receipts and the bank charges, "
            "correct the books under the bookkeeping policy, and write the corrected ledger back to "
            "ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_sales_tax_remittance", "rec:sales-tax-2025-11",
                        "the statement row of 21 November names the payee (DEBIT CARD STATE SALES TAX BOARD, 2415.75) "
                        "and no ledger entry matches it; vendors.csv lists the board on monthly filing terms with "
                        "Liabilities:SalesTax-Payable as its default account, the opening balance carries that "
                        "liability for the same amount, and the sales-tax-remittance section posts the payment "
                        "against it on the bank's date"),
        AlterRecognition("miskeyed_payment_on_account", "rec:si-2089-partial", "transpose_digits", 1,
                         "the ledger carries the 19 November payment on account from Ostrander Medical Group against "
                         "SI-2089 at 4510.00 while the statement row of the same date, payer and reference (ACH IN "
                         "OSTRANDER MEDICAL GROUP, SI-2089) shows 4150.00; the customer-receipts section re-posts the "
                         "entry with the statement's amount on the original date, against Assets:AR"),
        DuplicateRecognition("duplicated_service_charge", "rec:fee-2025-11",
                             "the ledger carries the 28 November monthly account service charge (52.00) twice and the "
                             "statement shows one such row; the bank-service-charges section says to remove one copy"),
    )),
)

FIXED_ASSETS_REDWOOD = TaskSpec(
    id="fixed_assets_redwood",
    type="bank_reconciliation",
    prompt=("Redwood Analytics Group bought two analyst workstations from Tessaro Technical Hardware in November, "
            "paid by check 7205 on delivery, and had Grafton Server Repairs replace a fan and power supply in the "
            "rack server on the company debit card. The equipment register and the repairs account do not agree with "
            "the Sequoia Coast Bank statement for November. Capitalise what the policy capitalises, expense what it "
            "expenses, agree the bank's own charges, correct Assets:Equipment, Expenses:Repairs and the checking "
            "account under the bookkeeping policy, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_equipment_check", "rec:equipment-7205",
                        "the statement row of 18 November names the check and the payee (CHECK 7205 TESSARO TECHNICAL "
                        "HARDWARE, 4862.50) and no ledger entry matches it; vendors.csv lists the supplier with "
                        "Assets:Equipment as its default account, and the equipment section capitalises the payment "
                        "there on the bank's date"),
        AlterRecognition("miskeyed_repair_charge", "rec:repairs-2025-11", "transpose_digits", 0,
                         "the ledger carries the 11 November repair charge to Grafton Server Repairs at 132.80 while "
                         "the statement row of 12 November (DEBIT CARD GRAFTON SERVER REPAIRS) shows 312.80; "
                         "vendors.csv books the vendor to Expenses:Repairs, and the equipment section re-posts the "
                         "charge at the statement's amount on the original date"),
        DuplicateRecognition("duplicated_batch_fee", "rec:fee-ach-2025-11",
                             "the ledger carries the 13 November outgoing payment batch fee (15.00) twice and the "
                             "statement shows one such row; the bank-service-charges section says to remove one copy"),
    )),
)

MONTH_END_CLOSE_REDWOOD = TaskSpec(
    id="month_end_close_redwood",
    type="bank_reconciliation",
    prompt=("Close November 2025 for Redwood Analytics Group. The Sequoia Coast Bank statement is in and the ledger "
            "does not agree with it: the December professional indemnity premium paid to Westhaven Insurance Agency "
            "by check 7206, the two bank charges and the client receipts all need agreeing, and the rent check drawn "
            "on the 27th and the client check banked on the 28th are still to clear. Agree the checking account to "
            "the statement, correct the ledger under the bookkeeping policy, list the outstanding items, and write "
            "the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_premium_prepayment", "rec:insurance-2025-12-prepaid",
                        "the statement row of 27 November names the check and the payee (CHECK 7206 WESTHAVEN "
                        "INSURANCE AGENCY, 1738.60) and no ledger entry matches it; vendors.csv lists the insurer with "
                        "Assets:Prepayments as its default account and the prepayments section books a premium paid "
                        "in November for December cover there, on the bank's date"),
        AlterRecognition("miskeyed_service_charge", "rec:fee-2025-11", "transpose_digits", 0,
                         "the ledger carries the 28 November monthly account service charge at 25.00 while the "
                         "statement row of the same date (MONTHLY ACCOUNT SERVICE CHARGE) shows 52.00; the "
                         "bank-service-charges section re-posts it at the statement's amount on the original date, "
                         "against Expenses:BankFees"),
        DuplicateRecognition("duplicated_payment_on_account", "rec:si-2089-partial",
                             "the ledger carries the 19 November payment on account from Ostrander Medical Group "
                             "against SI-2089 (4150.00) twice and the statement shows one ACH IN row of that amount "
                             "and reference; the collections section says to remove one copy and leave the other"),
    )),
)

TASKS = {task.id: task for task in (
    INTERCOMPANY_TRANSFERS_001,
    BANK_RECON_REDWOOD,
    AP_PAYMENT_RUN_REDWOOD,
    AR_COLLECTIONS_REDWOOD,
    BANK_FEED_CATEGORISATION_REDWOOD,
    EXPENSE_REPORTS_REDWOOD,
    PAYROLL_REDWOOD,
    SALES_TAX_REMITTANCE_REDWOOD,
    FIXED_ASSETS_REDWOOD,
    MONTH_END_CLOSE_REDWOOD,
)}
