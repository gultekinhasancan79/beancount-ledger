"""Falcon Ridge Surveying, February 2026: the irreducible facts.

This is the hand-reviewed layer. It states what happened — amounts, dates,
counterparties, documents, rails, clearing dates — and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The firm's field engineers file expense claims for travel on out-of-town
jobs and for small field supplies bought on site; each employee is a vendor
party whose default account says which expense the claims they file are
booked to, and an approved claim is reimbursed by check. The task's three
mutations name recognitions by id: one reimbursement check the bank cleared
and the books never received, one reimbursement check the books carry
twice, and the month's fleet-fuel card draw keyed with two digits
transposed. Check 2048 is not a mutation at all: it is a check the bank
cleared on 3 March, and the February statement's projection classifies it
NOT_YET_SETTLED on its own.

The same month carries the rest of a small firm's close, so that any of the
ten workflow tasks can be run against one statement and one set of golden
facts. The firm writes two check series on the one operating account: the
office manager's manual checkbook (2000 series) is used only for expense
claim reimbursements, and everything else — payroll, tax remittances, the
equipment supplier, the insurer, the sister company, the odd supplier
invoice — goes out on system-printed checks in the 3100 series. Three
office and crew staff are paid net by check on the 25th and the previous
month's withholdings are remitted to the revenue agency mid-month; January's
sales tax is filed and paid to the state by check; a GNSS rover and a data
collector are bought outright from the equipment supplier and capitalised
on payment while instrument servicing goes on the card; the sister company
Falcon Ridge Geomatics LLC is funded twice by check; March's fleet insurance
premium is prepaid mid-February; a second consumables supplier is paid by
ACH and by check; a third client pays part of one invoice by check and
mails a second check on the 27th that the bank does not credit until 4
March — the deposit in transit. Every task in `TASKS` sees exactly this
month; only the prompt and the planted items differ.
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

POLICY_TEXT = """# Falcon Ridge Surveying — Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, wire fees, returned
item fees, check printing, ACH batch fees) are recorded to `Expenses:BankFees`
on the date the bank applies them. A charge the books carry at a figure that
differs from the statement's has been keyed wrongly: it is re-posted with the
statement's amount on its original date, and the wrong figure is not left
standing alongside it. A charge the books carry twice against one statement
row has been posted twice: one copy is removed.

## Customer receipts
Cash received from a client reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice.

## Collections
Clients are invoiced on completion of fieldwork and pay by ACH, quoting the
invoice number, or by check. A check received from a client is recorded to
`Assets:AR` on the day it is received and banked the same day; the bank
credits it a few days later, and until it does the receipt is a deposit in
transit. A client may pay part of an invoice; a part payment is applied to
the invoice it names and the balance stays open in `Assets:AR`. A receipt the
statement shows that the books do not carry is posted to `Assets:AR` on the
date the bank shows; a receipt the books carry at the wrong figure is
re-posted with the statement's amount on its original date; a receipt the
books carry twice against one statement row is reduced to one copy. Receipts
are never netted against each other or against a payment.

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

Three vendors carry an asset `default_account` that is not a stock account,
and none of them is a trade supplier for whom a payable is raised. The
equipment supplier's `default_account` is `Assets:Equipment`: nothing is
booked when the instrument arrives, the check that pays for it is the
capitalisation, and it is booked to `Assets:Equipment`, never to
`Liabilities:AP`. The insurer's `default_account` is `Assets:Prepayments`:
the premium check is booked there, as the prepayments section governs. The
sister company's `default_account` is `Assets:Due-From-Geomatics` and its
terms read `intercompany`: nothing is purchased from it, no invoice is
received from it, and a check drawn to it is an advance booked to
`Assets:Due-From-Geomatics`, as the intercompany balances section governs.

## Payment runs
Consumables suppliers (those whose `default_account` is `Assets:Inventory`)
invoice on net 30 terms and are paid in a payment run, by ACH quoting the
invoice number or by a system-printed check. Each payment settles one
invoice in full and is recorded to `Liabilities:AP` on the day it is
released. A supplier payment the statement shows that the books do not carry
is posted to `Liabilities:AP` on the date the bank shows; one the books carry
at the wrong figure is re-posted with the statement's amount on its original
date; one the books carry twice against a single statement row is reduced to
one copy. A payment is never split across invoices or netted against a
credit.

## Employee expense claims
Field engineers file expense claims for mileage, lodging and meals on
out-of-town jobs and for small field supplies bought on site. Each employee
who files claims is set up in the vendor master with terms `expense claim` and
a `default_account` that says which expense the claims that employee files are
booked to. No payable is raised for a claim: an approved claim is reimbursed by
check from the manual checkbook (2000 series) and booked to the employee's
`default_account` on the date the check is issued, and the check number is the
claim's reference on the bank statement.

A reimbursement check the statement shows that the books do not carry is
posted, on the date the bank shows, to that employee's `default_account`. A
claim the books carry twice against a single check on the statement has been
posted twice: one copy is removed and the other is left as it stands. A claim
is never split, netted against another employee's claim or held over to the
following month.

## Payroll
Office and crew staff on salary are carried in the vendor master with terms
`monthly payroll` and `default_account` `Expenses:Salaries`. Each is paid net
pay by a system-printed check on the 25th of the month, and the check is
booked to `Expenses:Salaries` on the date it is issued; no payable is raised
for pay. Net pay varies with hours and overtime, so no two payroll checks in
a month carry the same figure. The withholdings deducted from a month's pay
are accrued in `Liabilities:PayrollTax` by the payroll journal and
remitted in the following month by check to the revenue agency, which is in
the vendor master with terms `monthly remittance` and `default_account`
`Liabilities:PayrollTax`; the remittance check is booked to that
liability on the date it is issued.

A payroll check the statement shows that the books do not carry is posted to
`Expenses:Salaries` on the date the bank shows, and a missing remittance
check to `Liabilities:PayrollTax` likewise. A payroll check the books
carry at a figure that differs from the statement's has been keyed wrongly:
it is re-posted with the statement's amount on its original date. Pay is
never netted between employees or against a reimbursement.

## Vehicle and fuel
The survey trucks are fuelled on a fleet fuel card. The card issuer is in the
vendor master with `default_account` `Expenses:Vehicle` and draws the monthly
fuel bill from the operating account by debit card; the draw is booked to
`Expenses:Vehicle` on the day the bank shows it. Where the books carry the
draw at an amount that differs from the statement's, the entry has been keyed
wrongly: it is re-posted with the statement's amount on the date it was
originally entered, and the wrong figure is not left standing alongside it.

## Card spend
Recurring services — the CAD and survey software subscription, the crew's
mobile phones, printing and plan copying, instrument servicing — are paid on
the firm's debit card. Each card vendor is in the vendor master with terms
`due on receipt` and a `default_account` naming the expense its charges are
booked to, and a card charge is booked to that account on the day the bank
shows it. A card row on the statement that the books do not carry is posted
to the vendor's `default_account` on the date the bank shows; a card charge
the books carry at a figure that differs from the statement's is re-posted
with the statement's amount on its original date. Card charges are never
combined into one entry or split between accounts.

## Equipment
Survey instruments and field equipment — GNSS receivers, total stations,
data collectors, tripods — are bought outright from the equipment supplier,
which is in the vendor master with `default_account` `Assets:Equipment`. No
payable is raised: the purchase is capitalised on payment, so the check to
the equipment supplier is booked to `Assets:Equipment` on the date it is
issued. Instrument calibration, servicing and repairs are not capitalised:
the service vendor carries `default_account` `Expenses:Repairs` and its card
charges are booked there on the day the bank shows them. An equipment check
the statement shows that the books do not carry is posted to
`Assets:Equipment` on the date the bank shows; one the books carry twice
against one check on the statement is reduced to one copy; a repairs charge
the books carry at the wrong figure is re-posted with the statement's amount
on its original date.

## Intercompany balances
Falcon Ridge Geomatics LLC is a sister company under common ownership that
does drone mapping and processing. It is carried in the vendor master with
terms `intercompany` and `default_account` `Assets:Due-From-Geomatics`. Cash
advanced to it by check is a loan, not an expense: the check is booked to
`Assets:Due-From-Geomatics` on the date it is issued, and the balance is
settled between the companies at year end. A funding check the statement
shows that the books do not carry is posted to `Assets:Due-From-Geomatics`
on the date the bank shows; a funding check the books carry twice against
one check on the statement is reduced to one copy. Advances are never netted
against work the sister company bills.

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
client, supplier or employee movement the ledger date is never later than the
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
`Assets:Prepayments` and released to expense in the period they cover. The
fleet and instrument insurance premium is billed monthly by the insurer,
which is in the vendor master with `default_account` `Assets:Prepayments`,
and is paid by check in the month before the month it covers; the check is
booked to `Assets:Prepayments` on the date it is issued and released to
expense the following month. An annual instrument service contract or
software licence paid up front is likewise a prepayment, not an expense of
the month it was paid. A premium check the statement shows that the books do
not carry is posted to `Assets:Prepayments` on the date the bank shows.

## Sales tax
Falcon Ridge collects sales tax from clients on surveying fees and owes it to
the state. Field consumables bought for use on client jobs are exempt, so no
tax is recoverable on the purchase side.

## Sales tax remittance
Tax collected in a month is accrued in `Liabilities:SalesTax-Payable` when
the invoice is raised and is filed and paid to the state in the following
month. The state revenue department is in the vendor master with terms
`monthly filing` and `default_account` `Liabilities:SalesTax-Payable`; the
remittance check is booked to that liability on the date it is issued, and
never to an expense. A remittance the statement shows that the books do not
carry is posted to `Liabilities:SalesTax-Payable` on the date the bank shows.

## Month-end close checklist
At each month end the controller ties the operating account to the statement:
every check issued is either cleared or listed as outstanding, every client
check banked is either credited or listed as in transit, the two bank charges
the bank applies in a month (the ACH batch fee mid-month and the service
charge at month end) are both booked, the insurer's check for next month's
premium sits in `Assets:Prepayments`, and the ledger's bank balance agrees
with the statement after the timing items. Nothing is posted to close a gap
that the statement does not explain.

## Suspense accounts
Falcon Ridge does not operate a suspense or plug account. Every posting is
made to the account that reflects the underlying transaction.
"""

OPENED = "2024-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Tamarack Valley Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Surveying fees receivable from clients", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Field consumables held in stores - hubs, lath, rebar caps, flagging, paint", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Assets:Equipment", K.ASSET, "Survey instruments and field equipment, capitalised when paid for", OPENED, 1400),
    Account("Assets:Due-From-Geomatics", K.ASSET, "Cash advanced to Falcon Ridge Geomatics LLC, the sister company", OPENED, 1500),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from clients and owed to the state", OPENED, 2100),
    Account("Liabilities:PayrollTax", K.LIABILITY, "Withholdings deducted from pay and owed to the revenue agency", OPENED, 2200),
    Account("Income:Sales", K.INCOME, "Surveying fees billed to clients", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Field consumables issued to client jobs", OPENED, 5000),
    Account("Expenses:Travel", K.EXPENSE, "Crew mileage, lodging and meals on out-of-town jobs, reimbursed on expense claims", OPENED, 5100),
    Account("Expenses:FieldSupplies", K.EXPENSE, "Small field supplies bought on site by crews, reimbursed on expense claims", OPENED, 5200),
    Account("Expenses:Vehicle", K.EXPENSE, "Fuel and running costs of the survey trucks", OPENED, 5300),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5400),
    Account("Expenses:Salaries", K.EXPENSE, "Net pay of office and crew staff on salary", OPENED, 5500),
    Account("Expenses:Software", K.EXPENSE, "CAD and survey software subscriptions", OPENED, 5600),
    Account("Expenses:Telecom", K.EXPENSE, "Crew mobile phones and data plans", OPENED, 5700),
    Account("Expenses:Office", K.EXPENSE, "Printing, plan copying and office consumables", OPENED, 5800),
    Account("Expenses:Repairs", K.EXPENSE, "Instrument calibration, servicing and repairs", OPENED, 5900),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:wexford-homes", "Wexford Homes LLC", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:talbot-creek", "Talbot Creek Developments", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:plumbline", "Plumbline Instruments Inc", R.VENDOR, 3, "net 30", "Assets:Inventory"),
    Party("party:fuelwise", "Fuelwise Fleet Card", R.VENDOR, 4, "due on receipt", "Expenses:Vehicle"),
    Party("party:ruth-abernathy", "Ruth Abernathy", R.VENDOR, 5, "expense claim", "Expenses:Travel"),
    Party("party:dev-ramaswamy", "Dev Ramaswamy", R.VENDOR, 6, "expense claim", "Expenses:Travel"),
    Party("party:caleb-ostrowski", "Caleb Ostrowski", R.VENDOR, 7, "expense claim", "Expenses:FieldSupplies"),
    Party("party:marisol-fuentes", "Marisol Fuentes", R.VENDOR, 8, "expense claim", "Expenses:FieldSupplies"),
    Party("party:tamarack-valley-bank", "Tamarack Valley Bank", R.BANK, 9),
    Party("party:kestwick-farms", "Kestwick Farms LLC", R.CUSTOMER, 10, "net 30", "Assets:AR"),
    Party("party:stakeline", "Stakeline Survey Supply", R.VENDOR, 11, "net 30", "Assets:Inventory"),
    Party("party:lionel-garvey", "Lionel Garvey", R.VENDOR, 12, "monthly payroll", "Expenses:Salaries"),
    Party("party:nadia-petrakis", "Nadia Petrakis", R.VENDOR, 13, "monthly payroll", "Expenses:Salaries"),
    Party("party:tomas-reinholt", "Tomas Reinholt", R.VENDOR, 14, "monthly payroll", "Expenses:Salaries"),
    Party("party:national-revenue", "National Revenue Agency", R.VENDOR, 15, "monthly remittance",
          "Liabilities:PayrollTax"),
    Party("party:state-taxation", "State Department of Taxation", R.VENDOR, 16, "monthly filing",
          "Liabilities:SalesTax-Payable"),
    Party("party:gridline", "Gridline CAD Software", R.VENDOR, 17, "due on receipt", "Expenses:Software"),
    Party("party:northpoint-cellular", "Northpoint Cellular", R.VENDOR, 18, "due on receipt", "Expenses:Telecom"),
    Party("party:inkwell", "Inkwell Print and Copy", R.VENDOR, 19, "due on receipt", "Expenses:Office"),
    Party("party:benchmark-positioning", "Benchmark Positioning Systems", R.VENDOR, 20, "due on receipt",
          "Assets:Equipment"),
    Party("party:calibra", "Calibra Instrument Service", R.VENDOR, 21, "due on receipt", "Expenses:Repairs"),
    Party("party:falcon-geomatics", "Falcon Ridge Geomatics LLC", R.VENDOR, 22, "intercompany",
          "Assets:Due-From-Geomatics"),
    Party("party:sentinel-mutual", "Sentinel Mutual Insurance", R.VENDOR, 23, "due on receipt", "Assets:Prepayments"),
)

DOCUMENTS = (
    Document("doc:si-0871", DK.SALES_INVOICE, "SI-0871", "party:wexford-homes", "2025-12-15", D("6480.00")),
    Document("doc:si-0876", DK.SALES_INVOICE, "SI-0876", "party:talbot-creek", "2025-12-22", D("5136.00")),
    Document("doc:si-0879", DK.SALES_INVOICE, "SI-0879", "party:wexford-homes", "2026-01-19", D("4815.50")),
    Document("doc:si-0881", DK.SALES_INVOICE, "SI-0881", "party:talbot-creek", "2026-01-26", D("7276.00")),
    Document("doc:si-0883", DK.SALES_INVOICE, "SI-0883", "party:kestwick-farms", "2026-02-03", D("3916.20")),
    Document("doc:si-0884", DK.SALES_INVOICE, "SI-0884", "party:wexford-homes", "2026-02-06", D("5778.00")),
    Document("doc:si-0885", DK.SALES_INVOICE, "SI-0885", "party:kestwick-farms", "2026-02-12", D("1979.50")),
    Document("doc:si-0886", DK.SALES_INVOICE, "SI-0886", "party:talbot-creek", "2026-02-17", D("8827.50")),
    Document("doc:pi-3302", DK.PURCHASE_INVOICE, "PI-3302", "party:plumbline", "2025-12-12", D("1725.60")),
    Document("doc:pi-3309", DK.PURCHASE_INVOICE, "PI-3309", "party:plumbline", "2026-01-15", D("2348.20")),
    Document("doc:pi-3318", DK.PURCHASE_INVOICE, "PI-3318", "party:plumbline", "2026-02-11", D("1964.80")),
    Document("doc:sl-1162", DK.PURCHASE_INVOICE, "SL-1162", "party:stakeline", "2025-12-22", D("1188.45")),
    Document("doc:sl-1187", DK.PURCHASE_INVOICE, "SL-1187", "party:stakeline", "2026-02-02", D("1432.75")),
    Document("doc:sl-1203", DK.PURCHASE_INVOICE, "SL-1203", "party:stakeline", "2026-02-16", D("968.40")),
    # the manual checkbook: expense claim reimbursements only
    Document("doc:chq-2041", DK.CHEQUE, "2041", "party:ruth-abernathy", "2026-01-05"),
    Document("doc:chq-2042", DK.CHEQUE, "2042", "party:caleb-ostrowski", "2026-01-20"),
    Document("doc:chq-2043", DK.CHEQUE, "2043", "party:ruth-abernathy", "2026-02-03"),
    Document("doc:chq-2044", DK.CHEQUE, "2044", "party:dev-ramaswamy", "2026-02-05"),
    Document("doc:chq-2045", DK.CHEQUE, "2045", "party:caleb-ostrowski", "2026-02-09"),
    Document("doc:chq-2046", DK.CHEQUE, "2046", "party:marisol-fuentes", "2026-02-12"),
    Document("doc:chq-2047", DK.CHEQUE, "2047", "party:ruth-abernathy", "2026-02-19"),
    Document("doc:chq-2048", DK.CHEQUE, "2048", "party:caleb-ostrowski", "2026-02-26"),
    # system-printed checks: payroll, remittances, equipment, insurer, sister company, suppliers
    Document("doc:chq-3101", DK.CHEQUE, "3101", "party:sentinel-mutual", "2026-01-15"),
    Document("doc:chq-3102", DK.CHEQUE, "3102", "party:national-revenue", "2026-01-15"),
    Document("doc:chq-3103", DK.CHEQUE, "3103", "party:state-taxation", "2026-01-19"),
    Document("doc:chq-3104", DK.CHEQUE, "3104", "party:falcon-geomatics", "2026-01-22"),
    Document("doc:chq-3105", DK.CHEQUE, "3105", "party:lionel-garvey", "2026-01-28"),
    Document("doc:chq-3106", DK.CHEQUE, "3106", "party:nadia-petrakis", "2026-01-28"),
    Document("doc:chq-3107", DK.CHEQUE, "3107", "party:tomas-reinholt", "2026-01-28"),
    Document("doc:chq-3108", DK.CHEQUE, "3108", "party:benchmark-positioning", "2026-02-06"),
    Document("doc:chq-3109", DK.CHEQUE, "3109", "party:falcon-geomatics", "2026-02-09"),
    Document("doc:chq-3110", DK.CHEQUE, "3110", "party:national-revenue", "2026-02-13"),
    Document("doc:chq-3111", DK.CHEQUE, "3111", "party:sentinel-mutual", "2026-02-16"),
    Document("doc:chq-3112", DK.CHEQUE, "3112", "party:state-taxation", "2026-02-17"),
    Document("doc:chq-3113", DK.CHEQUE, "3113", "party:benchmark-positioning", "2026-02-20"),
    Document("doc:chq-3114", DK.CHEQUE, "3114", "party:falcon-geomatics", "2026-02-23"),
    Document("doc:chq-3115", DK.CHEQUE, "3115", "party:stakeline", "2026-02-24"),
    Document("doc:chq-3116", DK.CHEQUE, "3116", "party:lionel-garvey", "2026-02-25"),
    Document("doc:chq-3117", DK.CHEQUE, "3117", "party:nadia-petrakis", "2026-02-25"),
    Document("doc:chq-3118", DK.CHEQUE, "3118", "party:tomas-reinholt", "2026-02-25"),
    # clients' own checks, banked on receipt
    Document("doc:chq-5518", DK.CHEQUE, "5518", "party:kestwick-farms", "2026-02-13"),
    Document("doc:chq-5531", DK.CHEQUE, "5531", "party:kestwick-farms", "2026-02-27"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # January 2026: the prior period, known to the bank archive only
    ExpensePayment("event:claim-2041-abernathy", "2026-01-05", "party:ruth-abernathy", D("412.75"),
                   cheque("doc:chq-2041", "2026-01-08"), "Expense claim - mileage and lodging, Wexford boundary retracement"),
    ExpensePayment("event:software-2026-01", "2026-01-06", "party:gridline", D("174.00"),
                   card("2026-01-06"), "CAD and survey software subscription - January"),
    CustomerReceipt("event:si-0871-receipt", "2026-01-07", "party:wexford-homes", "doc:si-0871", D("6480.00"),
                    ach_in("2026-01-07"), "Customer payment for SI-0871"),
    ExpensePayment("event:telecom-2026-01", "2026-01-08", "party:northpoint-cellular", D("238.92"),
                   card("2026-01-08"), "Crew mobile phones - January"),
    ExpensePayment("event:fuel-2026-01", "2026-01-09", "party:fuelwise", D("638.42"),
                   card("2026-01-09"), "Fleet fuel card - December statement"),
    VendorPayment("event:pi-3302-payment", "2026-01-14", "party:plumbline", "doc:pi-3302", D("1725.60"),
                  ach_out("2026-01-14"), "Payment of purchase invoice PI-3302"),
    Prepayment("event:insurance-2026-02-prepaid", "2026-01-15", "party:sentinel-mutual", D("624.10"),
               cheque("doc:chq-3101", "2026-01-19"), "2026-02", "Fleet and instrument insurance - February premium prepaid"),
    ExpensePayment("event:withholdings-2025-12", "2026-01-15", "party:national-revenue", D("1842.30"),
                   cheque("doc:chq-3102", "2026-01-20"), "December payroll withholdings remitted"),
    ExpensePayment("event:sales-tax-2025-12", "2026-01-19", "party:state-taxation", D("702.35"),
                   cheque("doc:chq-3103", "2026-01-22"), "December sales tax filed and paid"),
    ExpensePayment("event:claim-2042-ostrowski", "2026-01-20", "party:caleb-ostrowski", D("186.30"),
                   cheque("doc:chq-2042", "2026-01-23"), "Expense claim - lath, flagging and marking paint bought on site"),
    VendorPayment("event:sl-1162-payment", "2026-01-21", "party:stakeline", "doc:sl-1162", D("1188.45"),
                  ach_out("2026-01-21"), "Payment of purchase invoice SL-1162"),
    CustomerReceipt("event:si-0876-receipt", "2026-01-21", "party:talbot-creek", "doc:si-0876", D("5136.00"),
                    ach_in("2026-01-21"), "Customer payment for SI-0876"),
    ExpensePayment("event:funding-2026-01-geomatics", "2026-01-22", "party:falcon-geomatics", D("4000.00"),
                   cheque("doc:chq-3104", "2026-01-27"), "Intercompany advance to Falcon Ridge Geomatics - January funding"),
    ExpensePayment("event:pay-2026-01-garvey", "2026-01-28", "party:lionel-garvey", D("3198.20"),
                   cheque("doc:chq-3105", "2026-01-29"), "January net pay"),
    ExpensePayment("event:pay-2026-01-petrakis", "2026-01-28", "party:nadia-petrakis", D("2860.75"),
                   cheque("doc:chq-3106", "2026-01-30"), "January net pay"),
    ExpensePayment("event:pay-2026-01-reinholt", "2026-01-28", "party:tomas-reinholt", D("2533.10"),
                   cheque("doc:chq-3107", "2026-01-30"), "January net pay"),
    BankFee("event:fee-2026-01", "2026-01-30", D("18.00"), "Monthly account service charge"),
    # February 2026: the task period
    Purchase("event:sl-1187-receipt", "2026-02-02", "party:stakeline", "doc:sl-1187", D("1432.75"),
             "Purchase invoice SL-1187 received - rebar, caps and survey flagging"),
    ExpensePayment("event:claim-2043-abernathy", "2026-02-03", "party:ruth-abernathy", D("547.90"),
                   cheque("doc:chq-2043", "2026-02-06"), "Expense claim - mileage and two nights lodging, Talbot Creek topo"),
    Sale("event:si-0883-sale", "2026-02-03", "party:kestwick-farms", "doc:si-0883", D("3660.00"), D("0.07"), D("118.40"),
         "Boundary survey of the north parcel SI-0883", "Monuments and flagging issued on SI-0883"),
    ExpensePayment("event:software-2026-02", "2026-02-04", "party:gridline", D("189.00"),
                   card("2026-02-04"), "CAD and survey software subscription - February"),
    ExpensePayment("event:claim-2044-ramaswamy", "2026-02-05", "party:dev-ramaswamy", D("683.25"),
                   cheque("doc:chq-2044", "2026-02-10"), "Expense claim - mileage, lodging and meals, Wexford phase 2 layout"),
    Sale("event:si-0884-sale", "2026-02-06", "party:wexford-homes", "doc:si-0884", D("5400.00"), D("0.07"), D("142.50"),
         "Phase 2 construction staking SI-0884", "Hubs and lath issued on SI-0884"),
    ExpensePayment("event:equipment-gnss-rover", "2026-02-06", "party:benchmark-positioning", D("6485.00"),
                   cheque("doc:chq-3108", "2026-02-11"), "GNSS rover receiver and pole, capitalised on payment"),
    ExpensePayment("event:claim-2045-ostrowski", "2026-02-09", "party:caleb-ostrowski", D("158.64"),
                   cheque("doc:chq-2045", "2026-02-13"), "Expense claim - rebar caps and flagging bought on site"),
    CustomerReceipt("event:si-0879-receipt", "2026-02-09", "party:wexford-homes", "doc:si-0879", D("4815.50"),
                    ach_in("2026-02-09"), "Customer payment for SI-0879"),
    ExpensePayment("event:funding-2026-02-geomatics-a", "2026-02-09", "party:falcon-geomatics", D("5250.00"),
                   cheque("doc:chq-3109", "2026-02-12"), "Intercompany advance to Falcon Ridge Geomatics - drone survey payroll"),
    ExpensePayment("event:telecom-2026-02", "2026-02-10", "party:northpoint-cellular", D("243.17"),
                   card("2026-02-10"), "Crew mobile phones - February"),
    ExpensePayment("event:fuel-2026-02", "2026-02-11", "party:fuelwise", D("712.86"),
                   card("2026-02-11"), "Fleet fuel card - January statement"),
    Purchase("event:pi-3318-receipt", "2026-02-11", "party:plumbline", "doc:pi-3318", D("1964.80"),
             "Purchase invoice PI-3318 received - hubs, lath and marking paint"),
    VendorPayment("event:pi-3309-payment", "2026-02-12", "party:plumbline", "doc:pi-3309", D("2348.20"),
                  ach_out("2026-02-12"), "Payment of purchase invoice PI-3309"),
    ExpensePayment("event:claim-2046-fuentes", "2026-02-12", "party:marisol-fuentes", D("231.48"),
                   cheque("doc:chq-2046", "2026-02-17"), "Expense claim - marking paint, nails and whiskers bought on site"),
    Sale("event:si-0885-sale", "2026-02-12", "party:kestwick-farms", "doc:si-0885", D("1850.00"), D("0.07"), D("64.20"),
         "Well site and easement staking SI-0885", "Hubs and whiskers issued on SI-0885"),
    ExpensePayment("event:repairs-2026-02", "2026-02-13", "party:calibra", D("385.60"),
                   card("2026-02-13"), "Total station collimation check and service"),
    BankFee("event:ach-fee-2026-02", "2026-02-13", D("12.50"), "Outgoing ACH batch fee"),
    ExpensePayment("event:withholdings-2026-01", "2026-02-13", "party:national-revenue", D("1867.45"),
                   cheque("doc:chq-3110", "2026-02-18"), "January payroll withholdings remitted"),
    CustomerReceipt("event:si-0883-part-receipt", "2026-02-13", "party:kestwick-farms", "doc:si-0883", D("2500.00"),
                    cheque("doc:chq-5518", "2026-02-17"), "Part payment on SI-0883, customer check 5518"),
    ExpensePayment("event:office-2026-02", "2026-02-16", "party:inkwell", D("96.44"),
                   card("2026-02-16"), "Plan copying and plat printing"),
    Prepayment("event:insurance-2026-03-prepaid", "2026-02-16", "party:sentinel-mutual", D("638.75"),
               cheque("doc:chq-3111", "2026-02-19"), "2026-03", "Fleet and instrument insurance - March premium prepaid"),
    Purchase("event:sl-1203-receipt", "2026-02-16", "party:stakeline", "doc:sl-1203", D("968.40"),
             "Purchase invoice SL-1203 received - iron pins, plastic caps and lath"),
    Sale("event:si-0886-sale", "2026-02-17", "party:talbot-creek", "doc:si-0886", D("8250.00"), D("0.07"), D("218.75"),
         "Topographic survey and ALTA update SI-0886", "Rebar caps and monuments issued on SI-0886"),
    ExpensePayment("event:sales-tax-2026-01", "2026-02-17", "party:state-taxation", D("791.50"),
                   cheque("doc:chq-3112", "2026-02-20"), "January sales tax filed and paid"),
    CustomerReceipt("event:si-0881-receipt", "2026-02-19", "party:talbot-creek", "doc:si-0881", D("7276.00"),
                    ach_in("2026-02-19"), "Customer payment for SI-0881"),
    ExpensePayment("event:claim-2047-abernathy", "2026-02-19", "party:ruth-abernathy", D("396.10"),
                   cheque("doc:chq-2047", "2026-02-24"), "Expense claim - mileage and lodging, Talbot Creek ALTA fieldwork"),
    VendorPayment("event:sl-1187-payment", "2026-02-20", "party:stakeline", "doc:sl-1187", D("1432.75"),
                  ach_out("2026-02-20"), "Payment of purchase invoice SL-1187"),
    ExpensePayment("event:equipment-data-collector", "2026-02-20", "party:benchmark-positioning", D("1248.75"),
                   cheque("doc:chq-3113", "2026-02-25"), "Field data collector and bracket, capitalised on payment"),
    ExpensePayment("event:funding-2026-02-geomatics-b", "2026-02-23", "party:falcon-geomatics", D("3175.00"),
                   cheque("doc:chq-3114", "2026-02-26"), "Intercompany advance to Falcon Ridge Geomatics - processing licence renewal"),
    VendorPayment("event:sl-1203-payment", "2026-02-24", "party:stakeline", "doc:sl-1203", D("968.40"),
                  cheque("doc:chq-3115", "2026-02-27"), "Payment of purchase invoice SL-1203, check 3115"),
    CustomerReceipt("event:si-0884-receipt", "2026-02-25", "party:wexford-homes", "doc:si-0884", D("5778.00"),
                    ach_in("2026-02-25"), "Customer payment settling SI-0884"),
    ExpensePayment("event:pay-2026-02-garvey", "2026-02-25", "party:lionel-garvey", D("3214.60"),
                   cheque("doc:chq-3116", "2026-02-26"), "February net pay, check 3116"),
    ExpensePayment("event:pay-2026-02-petrakis", "2026-02-25", "party:nadia-petrakis", D("2876.35"),
                   cheque("doc:chq-3117", "2026-02-27"), "February net pay, check 3117"),
    ExpensePayment("event:pay-2026-02-reinholt", "2026-02-25", "party:tomas-reinholt", D("2541.80"),
                   cheque("doc:chq-3118", "2026-02-27"), "February net pay, check 3118"),
    # issued in February, cleared by the bank in March: the timing difference
    ExpensePayment("event:claim-2048-ostrowski", "2026-02-26", "party:caleb-ostrowski", D("264.30"),
                   cheque("doc:chq-2048", "2026-03-03"), "Expense claim - flagging and hub stakes bought on site, check 2048"),
    # received and banked on the 27th, credited by the bank in March: the deposit in transit
    CustomerReceipt("event:si-0885-receipt", "2026-02-27", "party:kestwick-farms", "doc:si-0885", D("1979.50"),
                    cheque("doc:chq-5531", "2026-03-04"), "Customer check 5531 settling SI-0885"),
    BankFee("event:fee-2026-02", "2026-02-27", D("47.25"), "Monthly service charge and check printing order"),
)

WORLD = World(
    id="falcon-2026-02",
    title="Falcon Ridge Surveying - FY2026",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:tamarack-valley-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2026-01-01", D("31842.15")),
    opening=OpeningPosition("2026-02-01", (("Assets:AR", D("14360.25")), ("Assets:Inventory", D("3275.40")),
                                           ("Liabilities:AP", D("-2348.20")),
                                           ("Liabilities:SalesTax-Payable", D("-791.50")),
                                           ("Liabilities:PayrollTax", D("-1867.45")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

PERIOD = Period("2026-02-01", "2026-02-28", "February 2026")

EXPENSE_REPORTS_001 = TaskSpec(
    id="expense_reports_001",
    type="bank_reconciliation",
    prompt=("February's employee expense claims were all reimbursed by check, and the claims register does not agree "
            "with the February statement for the operating checking account. Work through the differences under the "
            "bookkeeping policy, correct the books, and write the corrected ledger back to ledger.beancount."),
    period=Period("2026-02-01", "2026-02-28", "February 2026"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_reimbursement_check", "rec:claim-2046-fuentes",
                        "the statement row CHECK 2046 MARISOL FUENTES of 231.48 on 2026-02-17 answers no ledger "
                        "entry; vendors.csv maps Marisol Fuentes to Expenses:FieldSupplies with terms expense claim "
                        "and policy.md's Employee expense claims section posts a missing reimbursement check to the "
                        "employee's default account on the bank's date"),
        DuplicateRecognition("reimbursement_check_posted_twice", "rec:claim-2044-ramaswamy",
                             "the statement carries CHECK 2044 DEV RAMASWAMY of 683.25 once, on 2026-02-10, while "
                             "the ledger carries the 2026-02-05 Dev Ramaswamy reimbursement of 683.25 twice; "
                             "policy.md's Employee expense claims section removes one copy of a claim posted twice"),
        AlterRecognition("miskeyed_fuel_card_draw", "rec:fuel-2026-02", "transpose_digits", 1,
                         "the statement row DEBIT CARD FUELWISE FLEET CARD of 712.86 on 2026-02-11 answers the "
                         "ledger's same-day Fuelwise Fleet Card entry of 721.86 and no other; vendors.csv maps "
                         "Fuelwise Fleet Card to Expenses:Vehicle and policy.md's Vehicle and fuel section re-posts "
                         "a mis-keyed fuel draw with the statement's amount on its original date"),
    )),
)

BANK_RECON_FALCON = TaskSpec(
    id="bank_recon_falcon",
    type="bank_reconciliation",
    prompt=("The February statement for the operating checking account at Tamarack Valley Bank is in and the ledger "
            "does not tie to it. Please do the month-end bank reconciliation: match every statement row to the "
            "ledger, treat check 2048 and the Kestwick check banked on the 27th as timing items, and fix whatever "
            "the books have missed, mis-keyed or duplicated under the bookkeeping policy. Write the corrected "
            "ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_client_deposit", "rec:si-0881-receipt",
                        "the statement row ACH IN TALBOT CREEK DEVELOPMENTS with reference SI-0881 of 7276.00 on "
                        "2026-02-19 answers no ledger entry; customers.csv maps Talbot Creek Developments to "
                        "Assets:AR and policy.md's Customer receipts section applies the deposit against the invoice "
                        "on the bank's date"),
        AlterRecognition("miskeyed_supplier_ach", "rec:pi-3309-payment", "transpose_digits", 1,
                         "the statement row ACH OUT PLUMBLINE INSTRUMENTS INC with reference PI-3309 of 2348.20 on "
                         "2026-02-12 answers the ledger's same-day Plumbline payment of 2438.20 and no other; "
                         "vendors.csv maps Plumbline to Assets:Inventory so policy.md's Payments to suppliers "
                         "section lands the payment on Liabilities:AP, re-posted with the statement's amount on "
                         "its original date"),
        OmitRecognition("unrecorded_service_charge", "rec:fee-2026-02",
                        "the statement row MONTHLY SERVICE CHARGE AND CHECK PRINTING ORDER of 47.25 on 2026-02-27 "
                        "is a bank-initiated charge with no counterparty; policy.md's Bank service charges section "
                        "records it to Expenses:BankFees on the date applied"),
    )),
)

AP_PAYMENT_RUN_FALCON = TaskSpec(
    id="ap_payment_run_falcon",
    type="bank_reconciliation",
    prompt=("Three supplier payments went out in February: Plumbline's PI-3309 by ACH on the 12th, Stakeline's "
            "SL-1187 by ACH on the 20th and SL-1203 by check 3115 on the 24th. The payables ledger does not "
            "agree with the bank statement afterwards. Check each supplier payment against the statement rows and "
            "the invoice numbers they quote, correct the payables entries under the bookkeeping policy, and write "
            "the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_supplier_ach", "rec:sl-1187-payment",
                        "the statement row ACH OUT STAKELINE SURVEY SUPPLY with reference SL-1187 of 1432.75 on "
                        "2026-02-20 answers no ledger entry; the ledger carries purchase invoice SL-1187 open in "
                        "Liabilities:AP, vendors.csv maps Stakeline Survey Supply to Assets:Inventory, and policy.md's "
                        "Payment runs section posts a missing supplier payment to Liabilities:AP on the bank's date"),
        AlterRecognition("miskeyed_supplier_ach", "rec:pi-3309-payment", "transpose_digits", 1,
                         "the statement row ACH OUT PLUMBLINE INSTRUMENTS INC with reference PI-3309 of 2348.20 on "
                         "2026-02-12 answers the ledger's same-day Plumbline payment of 2438.20 and no other; "
                         "policy.md's Payment runs section re-posts a mis-keyed supplier payment with the "
                         "statement's amount on its original date"),
        DuplicateRecognition("supplier_check_posted_twice", "rec:sl-1203-payment",
                             "the statement carries CHECK 3115 STAKELINE SURVEY SUPPLY of 968.40 once, on "
                             "2026-02-27, while the ledger carries the 2026-02-24 payment of SL-1203 twice; "
                             "policy.md's Payment runs section reduces a payment posted twice to one copy"),
    )),
)

AR_COLLECTIONS_FALCON = TaskSpec(
    id="ar_collections_falcon",
    type="bank_reconciliation",
    prompt=("Collections for February need to be tied out before I send the aged receivables to the partners. "
            "Wexford paid SI-0879 and SI-0884 by ACH, Talbot Creek paid SI-0881, and Kestwick Farms sent a check "
            "for part of SI-0883 and a second check on the 27th for SI-0885 that the bank has not credited yet. "
            "Reconcile the client receipts in the ledger against the statement under the bookkeeping policy, "
            "leave the deposit in transit as it stands, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_client_ach", "rec:si-0884-receipt",
                        "the statement row ACH IN WEXFORD HOMES LLC with reference SI-0884 of 5778.00 on 2026-02-25 "
                        "answers no ledger entry; customers.csv maps Wexford Homes LLC to Assets:AR, the ledger "
                        "carries the open sale SI-0884, and policy.md's Collections section posts a missing receipt "
                        "to Assets:AR on the bank's date"),
        AlterRecognition("miskeyed_client_ach", "rec:si-0879-receipt", "transpose_digits", 2,
                         "the statement row ACH IN WEXFORD HOMES LLC with reference SI-0879 of 4815.50 on 2026-02-09 "
                         "answers the ledger's same-day Wexford receipt of 4851.50 and no other, and the entry is "
                         "too far from the cut-off to be a deposit in transit; policy.md's Collections section "
                         "re-posts a mis-keyed receipt with the statement's amount on its original date"),
        DuplicateRecognition("part_payment_posted_twice", "rec:si-0883-part-receipt",
                             "the statement carries CHECK 5518 KESTWICK FARMS LLC of 2500.00 once, on 2026-02-17, "
                             "while the ledger carries the 2026-02-13 part payment on SI-0883 twice; policy.md's "
                             "Collections section reduces a receipt posted twice to one copy"),
    )),
)

BANK_FEED_CATEGORISATION_FALCON = TaskSpec(
    id="bank_feed_categorisation_falcon",
    type="bank_reconciliation",
    prompt=("The February card charges came through on the bank feed and not all of them were posted, and one that "
            "was posted looks wrong. Go through every DEBIT CARD row on the statement (software, phones, printing, "
            "instrument service and the fuel card), categorise each to the vendor's default account from the "
            "vendor master under the bookkeeping policy, fix the ledger, and write the corrected ledger back to "
            "ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_software_charge", "rec:software-2026-02",
                        "the statement row DEBIT CARD GRIDLINE CAD SOFTWARE of 189.00 on 2026-02-04 answers no "
                        "ledger entry; vendors.csv maps Gridline CAD Software to Expenses:Software and policy.md's "
                        "Card spend section posts a missing card charge to the vendor's default account on the "
                        "bank's date"),
        OmitRecognition("unrecorded_telecom_charge", "rec:telecom-2026-02",
                        "the statement row DEBIT CARD NORTHPOINT CELLULAR of 243.17 on 2026-02-10 answers no ledger "
                        "entry; vendors.csv maps Northpoint Cellular to Expenses:Telecom and policy.md's Card spend "
                        "section posts a missing card charge to the vendor's default account on the bank's date"),
        AlterRecognition("miskeyed_printing_charge", "rec:office-2026-02", "transpose_digits", 1,
                         "the statement row DEBIT CARD INKWELL PRINT AND COPY of 96.44 on 2026-02-16 answers the "
                         "ledger's same-day Inkwell entry of 94.64 and no other; vendors.csv maps Inkwell Print and "
                         "Copy to Expenses:Office and policy.md's Card spend section re-posts a mis-keyed charge "
                         "with the statement's amount on its original date"),
    )),
)

PAYROLL_FALCON = TaskSpec(
    id="payroll_falcon",
    type="bank_reconciliation",
    prompt=("February payroll went out on the 25th, net pay checks to Lionel Garvey, Nadia Petrakis and Tomas "
            "Reinholt, and January's withholdings were remitted to the National Revenue Agency by check 3110 on "
            "the 13th. The payroll register does not agree with the bank statement. Reconcile the payroll and "
            "remittance checks against the statement under the bookkeeping policy, correct the ledger, and write "
            "the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_net_pay_check", "rec:pay-2026-02-petrakis",
                        "the statement row CHECK 3117 NADIA PETRAKIS of 2876.35 on 2026-02-27 answers no ledger "
                        "entry; vendors.csv maps Nadia Petrakis to Expenses:Salaries with terms monthly payroll and "
                        "policy.md's Payroll section posts a missing payroll check to Expenses:Salaries on the "
                        "bank's date"),
        AlterRecognition("miskeyed_net_pay_check", "rec:pay-2026-02-garvey", "transpose_digits", 1,
                         "the statement row CHECK 3116 LIONEL GARVEY of 3214.60 on 2026-02-26 answers the ledger's "
                         "2026-02-25 Lionel Garvey net pay entry of 3124.60 and no other; policy.md's Payroll "
                         "section re-posts a mis-keyed payroll check with the statement's amount on its original "
                         "date"),
        OmitRecognition("unrecorded_withholdings_remittance", "rec:withholdings-2026-01",
                        "the statement row CHECK 3110 NATIONAL REVENUE AGENCY of 1867.45 on 2026-02-18 answers no "
                        "ledger entry; vendors.csv maps National Revenue Agency to Liabilities:PayrollTax "
                        "with terms monthly remittance and policy.md's Payroll section posts a missing remittance "
                        "check to that liability on the bank's date"),
    )),
)

SALES_TAX_REMITTANCE_FALCON = TaskSpec(
    id="sales_tax_remittance_falcon",
    type="bank_reconciliation",
    prompt=("The January sales tax return was filed and paid to the State Department of Taxation by check 3112 "
            "on 17 February, and the sales tax payable account has to be cleared down correctly before the "
            "February return is prepared. The statement also does not agree with the client receipts and the "
            "bank charges booked. Reconcile the remittance, the receipts and the charges against the February "
            "statement under the bookkeeping policy and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_sales_tax_remittance", "rec:sales-tax-2026-01",
                        "the statement row CHECK 3112 STATE DEPARTMENT OF TAXATION of 791.50 on 2026-02-20 answers "
                        "no ledger entry; vendors.csv maps State Department of Taxation to "
                        "Liabilities:SalesTax-Payable with terms monthly filing and policy.md's Sales tax remittance "
                        "section posts a missing remittance to that liability on the bank's date"),
        AlterRecognition("miskeyed_client_check", "rec:si-0883-part-receipt", "transpose_digits", 1,
                         "the statement row CHECK 5518 KESTWICK FARMS LLC of 2500.00 on 2026-02-17 answers the "
                         "ledger's 2026-02-13 Kestwick part payment of 2050.00, which names check 5518, and no "
                         "other; policy.md's Collections section re-posts a mis-keyed receipt with the statement's "
                         "amount on its original date"),
        DuplicateRecognition("service_charge_posted_twice", "rec:fee-2026-02",
                             "the statement carries MONTHLY SERVICE CHARGE AND CHECK PRINTING ORDER of 47.25 once, "
                             "on 2026-02-27, while the ledger carries that Tamarack Valley Bank charge twice on the "
                             "same date; policy.md's Bank service charges section removes one copy"),
    )),
)

FIXED_ASSETS_FALCON = TaskSpec(
    id="fixed_assets_falcon",
    type="bank_reconciliation",
    prompt=("We bought a GNSS rover and a field data collector outright from Benchmark Positioning Systems in "
            "February, both paid by check, and had the total station serviced by Calibra on the card. Make sure "
            "the equipment is capitalised and the servicing expensed as the bookkeeping policy requires, tie the "
            "equipment and repairs entries to the February statement, correct whatever the ledger has wrong, and "
            "write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_equipment_check", "rec:equipment-gnss-rover",
                        "the statement row CHECK 3108 BENCHMARK POSITIONING SYSTEMS of 6485.00 on 2026-02-11 "
                        "answers no ledger entry; vendors.csv maps Benchmark Positioning Systems to "
                        "Assets:Equipment and policy.md's Equipment section posts a missing equipment check to "
                        "Assets:Equipment on the bank's date"),
        AlterRecognition("miskeyed_repairs_charge", "rec:repairs-2026-02", "transpose_digits", 1,
                         "the statement row DEBIT CARD CALIBRA INSTRUMENT SERVICE of 385.60 on 2026-02-13 answers "
                         "the ledger's same-day Calibra entry of 358.60 and no other; vendors.csv maps Calibra "
                         "Instrument Service to Expenses:Repairs and policy.md's Equipment section re-posts a "
                         "mis-keyed repairs charge with the statement's amount on its original date"),
        DuplicateRecognition("equipment_check_posted_twice", "rec:equipment-data-collector",
                             "the statement carries CHECK 3113 BENCHMARK POSITIONING SYSTEMS of 1248.75 once, on "
                             "2026-02-25, while the ledger carries the 2026-02-20 data collector purchase twice; "
                             "policy.md's Equipment section reduces an equipment check posted twice to one copy"),
    )),
)

INTERCOMPANY_TRANSFERS_FALCON = TaskSpec(
    id="intercompany_transfers_falcon",
    type="bank_reconciliation",
    prompt=("Falcon Ridge Geomatics LLC, our sister company, was funded twice in February by check: one advance "
            "on the 9th for its drone survey payroll and one on the 23rd for a processing licence renewal. Now "
            "the intercompany balance the two companies are comparing does not agree. Reconcile the advances and "
            "the client receipts against the February statement under the bookkeeping policy, correct the ledger, "
            "and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_funding_check", "rec:funding-2026-02-geomatics-a",
                        "the statement row CHECK 3109 FALCON RIDGE GEOMATICS LLC of 5250.00 on 2026-02-12 answers "
                        "no ledger entry; vendors.csv maps Falcon Ridge Geomatics LLC to Assets:Due-From-Geomatics "
                        "with terms intercompany and policy.md's Intercompany balances section posts a missing "
                        "funding check to that account on the bank's date"),
        DuplicateRecognition("funding_check_posted_twice", "rec:funding-2026-02-geomatics-b",
                             "the statement carries CHECK 3114 FALCON RIDGE GEOMATICS LLC of 3175.00 once, on "
                             "2026-02-26, while the ledger carries the 2026-02-23 advance twice; policy.md's "
                             "Intercompany balances section reduces a funding check posted twice to one copy"),
        AlterRecognition("miskeyed_client_ach", "rec:si-0879-receipt", "transpose_digits", 2,
                         "the statement row ACH IN WEXFORD HOMES LLC with reference SI-0879 of 4815.50 on 2026-02-09 "
                         "answers the ledger's same-day Wexford receipt of 4851.50 and no other; policy.md's "
                         "Collections section re-posts a mis-keyed receipt with the statement's amount on its "
                         "original date"),
    )),
)

MONTH_END_CLOSE_FALCON = TaskSpec(
    id="month_end_close_falcon",
    type="bank_reconciliation",
    prompt=("Closing February. Run the month-end checklist against the operating account statement: the March "
            "insurance premium check to Sentinel Mutual should be sitting in prepayments, both of the bank's "
            "February charges should be booked at the bank's figures, every client receipt should be posted once, "
            "and check 2048 and the Kestwick check banked on the 27th are timing items to leave alone. Correct "
            "the ledger under the bookkeeping policy and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_premium_prepayment", "rec:insurance-2026-03-prepaid",
                        "the statement row CHECK 3111 SENTINEL MUTUAL INSURANCE of 638.75 on 2026-02-19 answers no "
                        "ledger entry; vendors.csv maps Sentinel Mutual Insurance to Assets:Prepayments and "
                        "policy.md's Prepayments section posts a missing premium check to Assets:Prepayments on the "
                        "bank's date"),
        AlterRecognition("miskeyed_ach_batch_fee", "rec:ach-fee-2026-02", "transpose_digits", 0,
                         "the statement row OUTGOING ACH BATCH FEE of 12.50 on 2026-02-13 answers the ledger's "
                         "same-day Tamarack Valley Bank fee entry of 21.50 and no other; policy.md's Bank service "
                         "charges section re-posts a mis-keyed charge with the statement's amount on its original "
                         "date"),
        DuplicateRecognition("client_receipt_posted_twice", "rec:si-0884-receipt",
                             "the statement carries ACH IN WEXFORD HOMES LLC with reference SI-0884 of 5778.00 once, "
                             "on 2026-02-25, while the ledger carries that receipt twice on the same date; "
                             "policy.md's Collections section reduces a receipt posted twice to one copy"),
    )),
)

TASKS = {
    EXPENSE_REPORTS_001.id: EXPENSE_REPORTS_001,
    BANK_RECON_FALCON.id: BANK_RECON_FALCON,
    AP_PAYMENT_RUN_FALCON.id: AP_PAYMENT_RUN_FALCON,
    AR_COLLECTIONS_FALCON.id: AR_COLLECTIONS_FALCON,
    BANK_FEED_CATEGORISATION_FALCON.id: BANK_FEED_CATEGORISATION_FALCON,
    PAYROLL_FALCON.id: PAYROLL_FALCON,
    SALES_TAX_REMITTANCE_FALCON.id: SALES_TAX_REMITTANCE_FALCON,
    FIXED_ASSETS_FALCON.id: FIXED_ASSETS_FALCON,
    INTERCOMPANY_TRANSFERS_FALCON.id: INTERCOMPANY_TRANSFERS_FALCON,
    MONTH_END_CLOSE_FALCON.id: MONTH_END_CLOSE_FALCON,
}
