"""Bluewater Marine Supply, October 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

Bluewater is a chandlery on one Pelican Point Bank checking account. It
collects 8% sales tax on what it sells to three trade customers, carries the
tax as a liability and remits it to the State Department of Revenue by check
the following month; the September return is paid in October, and
September's collected tax is carried into the period as the opening balance
of the liability. Around that cycle the month carries everything a small
firm's October carries: three inventory suppliers invoiced and paid by ACH
or trade check, three hourly staff paid net by check on the 27th with the
September withholdings deposited with the Federal Revenue Service on the
29th, two staff expense claims reimbursed by check, the delivery van's fuel
card and the store's software, telecom, office and lodging spend on the
debit card, an electric pallet stacker bought for the warehouse and a test
tank pump repaired, two funding checks to the sister company Bluewater
Marine Services LLC, and the November insurance premium paid in advance.
Bluewater draws two check books on the one account: the trade series
(11xx) for suppliers, rent and the tax return, and the disbursements series
(20xx) for wages, withholdings, claims, equipment, insurance and
intercompany funding. The bank opening balance is authored higher than the
single-task world carried, because September now also pays wages, funding
and card spend; no existing event's amount, date or id changed.

The one world serves ten tasks; every task sees the same statement and the
same golden facts, and only the prompt and the planted items differ. Each
task names recognitions by id in its plan. Two timing items are not
mutations at all: the trade check to the rigging supplier issued on 28
October cleared on 3 November, and the customer's check received on 30
October was deposited on 4 November; the October statement's projection
classifies both NOT_YET_SETTLED on its own.
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

POLICY_TEXT = """# Bluewater Marine Supply - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, check image fees,
account analysis fees, returned item fees) are recorded to `Expenses:BankFees`
on the date the bank applies them. A charge the bank applied once is recorded
once; a charge the bank applied on two dates is two charges.

## Customer receipts
Cash received from a customer reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice. Trade
customers pay by ACH quoting the invoice number or by check; a customer's
check is recorded on the day it is received, and the bank's deposit line for
it carries the customer's own check number. A customer that pays part of an
invoice on account is recorded for the amount received, against the invoice
the remittance names; the balance stays in `Assets:AR`.

A receipt that was posted with an amount different from the deposit the bank
shows for the same customer and invoice was mis-keyed. It is corrected by
re-posting the entry at the amount the statement shows, on the date the
entry was originally posted. Only the amount changes; the customer, the
invoice and the accounts stay as they were.

## Collections
The receivables ledger is tied to the bank statement at every close. Three
kinds of difference arise from that tie-out, and each has exactly one
correction:

- A deposit on the statement that names a customer and an invoice and has no
  entry in the books is added for the amount the statement shows, against
  `Assets:AR`, on the date the bank shows (see Dates below).
- A receipt posted at the wrong amount is re-posted at the statement's amount
  on its original date, as the customer-receipts section says.
- A receipt posted twice is corrected by removing one of the two copies; the
  copy that remains is left exactly as it was.

A customer's check recorded as received before the cut-off that the bank
deposits after it is a deposit in transit, not a difference to correct.

## Payments to suppliers
The `default_account` a supplier carries in the vendor master is where that
supplier's purchases are booked when they arrive. It is not always where a
payment to that supplier lands, and the account itself says which it is.

Where a supplier's purchases are booked to `Assets:Inventory` - the cordage,
electronics and paint suppliers - the goods were taken into that account when
they were received and a payable was raised for them at the same time, so
cash paid to that supplier afterwards settles the payable and is recorded to
`Liabilities:AP`.

Where a supplier's purchases are booked to `Assets:Equipment`, the supplier
sells equipment and Bluewater pays for it on delivery. No payable is raised
and nothing passes through `Liabilities:AP`: the payment is the purchase,
capitalised as the equipment section below describes. An equipment supplier
is not a stock supplier with an account, even though both carry an asset
account in the vendor master.

Where a supplier's purchases are booked to an expense account, no payable is
raised: the payment is the expense, and it is recorded to that supplier's own
`default_account` on the day it is paid, except where it is paid ahead of the
period it covers, which the prepayments section below governs.

The vendor master also carries payees that are not suppliers of goods or
services at all: the staff, the Federal Revenue Service, the State Department
of Revenue, the insurer and the sister company. The `default_account` each of
those carries is exactly where a payment to that payee lands, and the section
of this policy named for that payee governs the entry. No payable is ever
raised for any of them.

## Payment runs
The inventory suppliers (cordage and rigging, electronics, paint and
coatings) are carried in the vendor master with `Assets:Inventory` as their
default account; their invoices are booked to `Liabilities:AP` when the goods
arrive and are paid on terms, by ACH quoting the invoice number or by trade
check. Either way the payment settles the payable: a debit to `Liabilities:AP`
and a credit to the checking account, dated the day the payment was made.

The payables ledger is tied to the bank statement at every close, and each
kind of difference has exactly one correction: a supplier payment on the
statement that the books lack is added against `Liabilities:AP` for the
statement's amount on the date the bank shows; a payment posted at the wrong
amount is re-posted at the statement's amount on its original date, the
supplier and the invoice unchanged; a payment posted twice loses one copy and
keeps the other exactly as it was.

## Check series
Bluewater draws two check books on the one Pelican Point Bank checking
account: the trade series (11xx) for suppliers, rent and the sales tax
return, and the disbursements series (20xx) for wages, withholdings, staff
expense claims, equipment, insurance and intercompany funding. The bank
prints the check number and the payee on every check row, whichever book it
came from, and an entry for a check names its number.

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

## Card spend
Bluewater's debit card pays for the chart and inventory software
subscription, the store and warehouse phone and internet, office supplies,
lodging when staff travel to trade shows, the delivery van's fuel and small
repairs. Each card vendor is carried in the vendor master with the expense
account its charges belong to as its default account (`Expenses:Software`,
`Expenses:Telecom`, `Expenses:Office`, `Expenses:Travel`, `Expenses:Vehicle`,
`Expenses:Repairs`). A card charge is recorded to the vendor's default
account on the day of the charge, one entry per statement row, with the
vendor named as payee exactly as the vendor master lists it; no payable is
raised for card spend.

When the month is closed the card rows are tied to the bank feed. A card row
the books lack is added to the vendor's default account for the statement's
amount on the date the bank shows; a card charge posted at the wrong amount
is re-posted at the statement's amount on its original date; a card charge
posted twice loses one copy.

## Employee expense claims
Staff who travel for the business claim their mileage, ferry fares, meals
and lodging on an expense report, and the claim is reimbursed by a
disbursements check. Each claimant is carried in the vendor master as a
payee on "expense claim" terms with `Expenses:Travel` as the default
account. A reimbursement is recorded on the day the check is written, with
the claimant named as payee exactly as the vendor master lists them: a debit
to `Expenses:Travel` and a credit to the checking account for the amount of
the check. No payable is raised for a claim ahead of the check. The delivery
van's fuel is bought at Wavecrest Marine Fuel on the debit card - the staff
call it the fuel card, and the bank prints it as a DEBIT CARD row like any
other card charge - and is recorded to `Expenses:Vehicle` under the
card-spend rules.

A reimbursement check on the statement that the books lack is added against
`Expenses:Travel` for the statement's amount on the date the bank shows; a
reimbursement posted twice loses one copy; a fuel charge posted at the wrong
amount is re-posted at the statement's amount on its original date.

## Payroll
Bluewater's staff are paid monthly by disbursements check for each
employee's net pay. Each employee is carried in the vendor master as a payee
on "monthly payroll" terms with `Expenses:Salaries` as the default account.
A net pay check is recorded as one entry per employee, dated the day the
check was written, with the employee named as payee exactly as the vendor
master lists them: a debit to `Expenses:Salaries` and a credit to the
checking account for the net amount. No payable is raised for net pay ahead
of the check. Hours vary month to month, so net pay does too.

Tax withheld from wages is accrued to `Liabilities:PayrollTax` by the
payroll journal posted after each close; that journal is outside the bank
reconciliation. The amount accrued for a month is deposited with the Federal
Revenue Service by check in the following month. The revenue service is
carried in the vendor master on "payroll tax deposit" terms with
`Liabilities:PayrollTax` as the default account, and the deposit check
settles that liability: a debit to `Liabilities:PayrollTax` and a credit to
the checking account on the day the check is written. It is neither a
purchase nor an expense.

The payroll postings are tied to the bank statement at every close. A net
pay check or a withholdings deposit on the statement that the books lack is
added for the statement's amount, to the payee's default account, on the
date the bank shows; a check posted at the wrong amount is re-posted at the
statement's amount on its original date, the payee unchanged; a check posted
twice loses one copy.

## Prepayments
Amounts paid before the period they relate to are recorded to
`Assets:Prepayments` and released to expense in the period they cover. Rent
paid in one month for the following month is a prepayment, not an expense of
the month it was paid. The hull and liability policy with Lighthouse Mutual
Insurance renews on 1 November and each month's premium is paid in advance
in the month before, by disbursements check. A premium paid in October for
November is recorded to `Assets:Prepayments` on the day the check is written
and released to `Expenses:Insurance` in November by the close journal, which
is outside the bank reconciliation. The insurer is carried in the vendor
master on "premium in advance" terms with `Assets:Prepayments` as its
default account for exactly this reason: every payment to the insurer is a
payment in advance, and the vendor master and this section agree on where it
lands. No payable is raised for a premium. A premium check on the statement
that the books lack is added against `Assets:Prepayments` for the
statement's amount on the date the bank shows.

## Equipment
Gullwing Dock Equipment supplies the warehouse's stackers, hoists and dock
hardware and is carried in the vendor master with `Assets:Equipment` as its
default account. Bluewater pays equipment on delivery by disbursements
check, so no payable is raised: a payment to an equipment supplier is
capitalised on payment, a debit to `Assets:Equipment` and a credit to the
checking account, dated the day the check is written. Repairs and servicing
of equipment already owned are expensed: Cormorant Engine Repair is carried
with `Expenses:Repairs` as its default account and is paid on the debit card
under the card-spend rules.

An equipment check on the statement that the books lack is added against
`Assets:Equipment` for the statement's amount on the date the bank shows; a
repair charge posted at the wrong amount is re-posted at the statement's
amount on its original date.

## Intercompany balances
Bluewater Marine Services LLC is a sister company under common ownership
that runs the mobile rigging and engine service crews. It is carried in the
vendor master on "intercompany" terms with `Assets:Due-From-Bluewater-Svc`
as its default account. Bluewater funds it by disbursements check when its
own receipts run slow; a funding check is a loan to the sister company, not
a purchase and not an expense, and is recorded as a debit to
`Assets:Due-From-Bluewater-Svc` and a credit to the checking account on the
day the check is written. A repayment from the sister company would credit
the same account.

A funding check on the statement that the books lack is added against
`Assets:Due-From-Bluewater-Svc` for the statement's amount on the date the
bank shows; a funding check posted twice loses one copy and keeps the other
exactly as it was.

## Sales tax
Bluewater collects sales tax from customers at the state rate of 8% on
everything it sells, over the counter and on account, and owes that tax to
the state. The tax is credited to `Liabilities:SalesTax-Payable` on the day
the sale is invoiced; it is not revenue. The balance of that account at any
date is the tax collected and not yet remitted. Bluewater remits it to the
State Department of Revenue monthly, on the return for the month in which it
was collected. Goods bought for resale are exempt under the resale
certificate, so no tax is recoverable on the purchase side.

## Sales tax remittance
The State Department of Revenue is carried in the vendor master with
`Liabilities:SalesTax-Payable` as its default account and terms of "monthly
filing". It is not a supplier of goods or services: a payment to the
department is neither a purchase nor an expense. It settles the tax
liability for the month the return covers, so it is recorded as a debit to
`Liabilities:SalesTax-Payable` and a credit to the checking account, dated
the day it was paid. The return is paid by check in the month after the tax
was collected, for the amount the return reports.

When the month is closed, the tax ledger and the checking account are both
tied to the bank statement. Two kinds of difference arise from that tie-out,
and each has exactly one correction:

- A remittance to the department that appears on the statement but was never
  posted is added to the ledger for the amount the statement shows, against
  `Liabilities:SalesTax-Payable`, on the date the bank shows (see Dates
  above).
- A bank charge that was posted twice is corrected by removing one of the
  two copies. The copy that remains is left exactly as it was.

A remittance that is on both the statement and the ledger with the same
check number and amount is a match and is not touched.

## Suspense accounts
Bluewater does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
"""

OPENED = "2025-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Pelican Point Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Trade receivables from customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Chandlery stock held for resale", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Assets:Equipment", K.ASSET, "Warehouse and dock equipment at cost", OPENED, 1400),
    Account("Assets:Due-From-Bluewater-Svc", K.ASSET, "Intercompany balance due from Bluewater Marine Services LLC", OPENED, 1500),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Liabilities:PayrollTax", K.LIABILITY, "Tax withheld from wages and owed to the Federal Revenue Service", OPENED, 2200),
    Account("Income:Sales", K.INCOME, "Revenue from goods sold", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:Salaries", K.EXPENSE, "Net wages paid to staff", OPENED, 5100),
    Account("Expenses:Rent", K.EXPENSE, "Store, warehouse and dock frontage rent for the period", OPENED, 5200),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Expenses:Travel", K.EXPENSE, "Staff travel, mileage, ferry fares and lodging", OPENED, 5400),
    Account("Expenses:Software", K.EXPENSE, "Chart and inventory software subscriptions", OPENED, 5500),
    Account("Expenses:Telecom", K.EXPENSE, "Store and warehouse phone and internet", OPENED, 5600),
    Account("Expenses:Office", K.EXPENSE, "Office supplies and printed forms", OPENED, 5700),
    Account("Expenses:Repairs", K.EXPENSE, "Repairs and servicing of equipment owned", OPENED, 5800),
    Account("Expenses:Vehicle", K.EXPENSE, "Delivery van fuel and running costs", OPENED, 5900),
    Account("Expenses:Insurance", K.EXPENSE, "Hull and liability insurance for the period", OPENED, 6000),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:kittiwake", "Kittiwake Charters", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:osprey-cove", "Osprey Cove Marina", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:tidewater", "Tidewater Boatworks", R.CUSTOMER, 3, "net 15", "Assets:AR"),
    Party("party:seaforth", "Seaforth Cordage and Rigging", R.VENDOR, 4, "net 30", "Assets:Inventory"),
    Party("party:northstar", "Northstar Marine Electronics", R.VENDOR, 5, "net 30", "Assets:Inventory"),
    Party("party:revenue-dept", "State Department of Revenue", R.VENDOR, 6, "monthly filing", "Liabilities:SalesTax-Payable"),
    Party("party:quayside", "Quayside Holdings", R.VENDOR, 7, "due on receipt", "Expenses:Rent"),
    Party("party:pelican-point-bank", "Pelican Point Bank", R.BANK, 8),
    Party("party:petrel", "Petrel Paint and Coatings", R.VENDOR, 9, "net 15", "Assets:Inventory"),
    Party("party:pellerin", "Marcus Pellerin", R.VENDOR, 10, "monthly payroll", "Expenses:Salaries"),
    Party("party:solvang", "Ingrid Solvang", R.VENDOR, 11, "monthly payroll", "Expenses:Salaries"),
    Party("party:barrowman", "Theo Barrowman", R.VENDOR, 12, "monthly payroll", "Expenses:Salaries"),
    Party("party:federal-revenue", "Federal Revenue Service", R.VENDOR, 13, "payroll tax deposit", "Liabilities:PayrollTax"),
    Party("party:okonkwo", "Nadia Okonkwo", R.VENDOR, 14, "expense claim", "Expenses:Travel"),
    Party("party:ferrier", "Callum Ferrier", R.VENDOR, 15, "expense claim", "Expenses:Travel"),
    Party("party:wavecrest", "Wavecrest Marine Fuel", R.VENDOR, 16, "fuel card", "Expenses:Vehicle"),
    Party("party:helmsight", "Helmsight Software", R.VENDOR, 17, "card on file", "Expenses:Software"),
    Party("party:shearwater", "Shearwater Telecom", R.VENDOR, 18, "card on file", "Expenses:Telecom"),
    Party("party:dockside", "Dockside Office Supply", R.VENDOR, 19, "card on file", "Expenses:Office"),
    Party("party:puffin", "Puffin Inn and Suites", R.VENDOR, 20, "card on file", "Expenses:Travel"),
    Party("party:gullwing", "Gullwing Dock Equipment", R.VENDOR, 21, "due on delivery", "Assets:Equipment"),
    Party("party:cormorant", "Cormorant Engine Repair", R.VENDOR, 22, "card on file", "Expenses:Repairs"),
    Party("party:bluewater-services", "Bluewater Marine Services LLC", R.VENDOR, 23, "intercompany", "Assets:Due-From-Bluewater-Svc"),
    Party("party:lighthouse", "Lighthouse Mutual Insurance", R.VENDOR, 24, "premium in advance", "Assets:Prepayments"),
)

DOCUMENTS = (
    Document("doc:si-2187", DK.SALES_INVOICE, "SI-2187", "party:tidewater", "2025-08-21", D("5289.30")),
    Document("doc:si-2190", DK.SALES_INVOICE, "SI-2190", "party:osprey-cove", "2025-08-27", D("3844.80")),
    Document("doc:si-2198", DK.SALES_INVOICE, "SI-2198", "party:kittiwake", "2025-09-09", D("6069.60")),
    Document("doc:si-2203", DK.SALES_INVOICE, "SI-2203", "party:osprey-cove", "2025-09-23", D("5266.08")),
    Document("doc:si-2206", DK.SALES_INVOICE, "SI-2206", "party:tidewater", "2025-09-26", D("1370.67")),
    Document("doc:si-2211", DK.SALES_INVOICE, "SI-2211", "party:tidewater", "2025-10-07", D("4225.77")),
    Document("doc:si-2216", DK.SALES_INVOICE, "SI-2216", "party:kittiwake", "2025-10-16", D("7866.72")),
    Document("doc:si-2219", DK.SALES_INVOICE, "SI-2219", "party:osprey-cove", "2025-10-24", D("2859.84")),
    Document("doc:pi-7731", DK.PURCHASE_INVOICE, "PI-7731", "party:seaforth", "2025-08-05", D("3864.20")),
    Document("doc:pi-7740", DK.PURCHASE_INVOICE, "PI-7740", "party:northstar", "2025-08-19", D("2972.15")),
    Document("doc:pi-7752", DK.PURCHASE_INVOICE, "PI-7752", "party:seaforth", "2025-09-16", D("4618.30")),
    Document("doc:pi-7758", DK.PURCHASE_INVOICE, "PI-7758", "party:northstar", "2025-09-25", D("2689.45")),
    Document("doc:pi-7761", DK.PURCHASE_INVOICE, "PI-7761", "party:seaforth", "2025-09-29", D("3377.85")),
    Document("doc:pi-7766", DK.PURCHASE_INVOICE, "PI-7766", "party:petrel", "2025-10-06", D("2475.40")),
    Document("doc:pi-7769", DK.PURCHASE_INVOICE, "PI-7769", "party:northstar", "2025-10-15", D("3146.90")),
    Document("doc:pi-7773", DK.PURCHASE_INVOICE, "PI-7773", "party:seaforth", "2025-10-22", D("2914.60")),
    # the trade check book: suppliers, rent and the sales tax return
    Document("doc:chq-1141", DK.CHEQUE, "1141", "party:quayside", "2025-09-02"),
    Document("doc:chq-1142", DK.CHEQUE, "1142", "party:seaforth", "2025-09-04"),
    Document("doc:chq-1143", DK.CHEQUE, "1143", "party:revenue-dept", "2025-09-12"),
    Document("doc:chq-1144", DK.CHEQUE, "1144", "party:quayside", "2025-10-02"),
    Document("doc:chq-1145", DK.CHEQUE, "1145", "party:seaforth", "2025-10-03"),
    Document("doc:chq-1146", DK.CHEQUE, "1146", "party:revenue-dept", "2025-10-14"),
    Document("doc:chq-1147", DK.CHEQUE, "1147", "party:seaforth", "2025-10-28"),
    # the disbursements check book: wages, withholdings, claims, equipment, insurance, intercompany
    Document("doc:chq-2038", DK.CHEQUE, "2038", "party:okonkwo", "2025-09-09"),
    Document("doc:chq-2039", DK.CHEQUE, "2039", "party:bluewater-services", "2025-09-15"),
    Document("doc:chq-2040", DK.CHEQUE, "2040", "party:pellerin", "2025-09-26"),
    Document("doc:chq-2041", DK.CHEQUE, "2041", "party:solvang", "2025-09-26"),
    Document("doc:chq-2042", DK.CHEQUE, "2042", "party:barrowman", "2025-09-26"),
    Document("doc:chq-2043", DK.CHEQUE, "2043", "party:federal-revenue", "2025-09-29"),
    Document("doc:chq-2044", DK.CHEQUE, "2044", "party:bluewater-services", "2025-10-06"),
    Document("doc:chq-2045", DK.CHEQUE, "2045", "party:okonkwo", "2025-10-08"),
    Document("doc:chq-2046", DK.CHEQUE, "2046", "party:gullwing", "2025-10-10"),
    Document("doc:chq-2047", DK.CHEQUE, "2047", "party:lighthouse", "2025-10-15"),
    Document("doc:chq-2048", DK.CHEQUE, "2048", "party:ferrier", "2025-10-17"),
    Document("doc:chq-2049", DK.CHEQUE, "2049", "party:bluewater-services", "2025-10-21"),
    Document("doc:chq-2050", DK.CHEQUE, "2050", "party:pellerin", "2025-10-27"),
    Document("doc:chq-2051", DK.CHEQUE, "2051", "party:solvang", "2025-10-27"),
    Document("doc:chq-2052", DK.CHEQUE, "2052", "party:barrowman", "2025-10-27"),
    Document("doc:chq-2053", DK.CHEQUE, "2053", "party:federal-revenue", "2025-10-29"),
    # the customers' own checks, deposited on receipt
    Document("doc:chq-5528", DK.CHEQUE, "5528", "party:osprey-cove", "2025-10-20"),
    Document("doc:chq-5531", DK.CHEQUE, "5531", "party:osprey-cove", "2025-10-30"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # September 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-09", "2025-09-02", "party:quayside", D("4150.00"),
                   cheque("doc:chq-1141", "2025-09-05"), "September rent, store, warehouse and dock frontage"),
    VendorPayment("event:pi-7731-payment", "2025-09-04", "party:seaforth", "doc:pi-7731", D("3864.20"),
                  cheque("doc:chq-1142", "2025-09-09"), "Payment of purchase invoice PI-7731, check 1142"),
    ExpensePayment("event:helmsight-2025-09", "2025-09-06", "party:helmsight", D("218.90"),
                   card("2025-09-08"), "Chart and inventory software subscription, September"),
    ExpensePayment("event:claim-okonkwo-2025-09", "2025-09-09", "party:okonkwo", D("356.20"),
                   cheque("doc:chq-2038", "2025-09-12"), "Expense claim, August customer visits, mileage and ferry fares, check 2038"),
    CustomerReceipt("event:si-2187-receipt", "2025-09-10", "party:tidewater", "doc:si-2187", D("5289.30"),
                    ach_in("2025-09-10"), "Customer payment for SI-2187"),
    ExpensePayment("event:cormorant-2025-09", "2025-09-11", "party:cormorant", D("191.20"),
                   card("2025-09-12"), "Forklift hydraulic hose replaced"),
    ExpensePayment("event:salestax-2025-08-remit", "2025-09-12", "party:revenue-dept", D("2104.38"),
                   cheque("doc:chq-1143", "2025-09-16"), "August sales tax return, check 1143"),
    ExpensePayment("event:shearwater-2025-09", "2025-09-13", "party:shearwater", D("298.40"),
                   card("2025-09-15"), "Store and warehouse phone and internet, September"),
    ExpensePayment("event:ic-funding-2025-09", "2025-09-15", "party:bluewater-services", D("2500.00"),
                   cheque("doc:chq-2039", "2025-09-18"), "Intercompany funding to Bluewater Marine Services LLC, check 2039"),
    Purchase("event:pi-7752-purchase", "2025-09-16", "party:seaforth", "doc:pi-7752", D("4618.30"),
             "Purchase invoice PI-7752 received, anchor rode and three-strand dock line"),
    VendorPayment("event:pi-7740-payment", "2025-09-18", "party:northstar", "doc:pi-7740", D("2972.15"),
                  ach_out("2025-09-18"), "Payment of purchase invoice PI-7740"),
    ExpensePayment("event:wavecrest-2025-09", "2025-09-19", "party:wavecrest", D("158.44"),
                   card("2025-09-20"), "Fuel card, delivery van"),
    CustomerReceipt("event:si-2190-receipt", "2025-09-24", "party:osprey-cove", "doc:si-2190", D("3844.80"),
                    ach_in("2025-09-24"), "Customer payment for SI-2190"),
    Purchase("event:pi-7758-purchase", "2025-09-25", "party:northstar", "doc:pi-7758", D("2689.45"),
             "Purchase invoice PI-7758 received, VHF radios and masthead antennas"),
    ExpensePayment("event:payroll-pellerin-2025-09", "2025-09-26", "party:pellerin", D("2913.40"),
                   cheque("doc:chq-2040", "2025-09-30"), "September net pay, check 2040"),
    ExpensePayment("event:payroll-solvang-2025-09", "2025-09-26", "party:solvang", D("2590.25"),
                   cheque("doc:chq-2041", "2025-09-29"), "September net pay, check 2041"),
    ExpensePayment("event:payroll-barrowman-2025-09", "2025-09-26", "party:barrowman", D("2255.70"),
                   cheque("doc:chq-2042", "2025-09-30"), "September net pay, check 2042"),
    Purchase("event:pi-7761-purchase", "2025-09-29", "party:seaforth", "doc:pi-7761", D("3377.85"),
             "Purchase invoice PI-7761 received, shackles, blocks and fenders"),
    ExpensePayment("event:payrolltax-2025-08-remit", "2025-09-29", "party:federal-revenue", D("1398.75"),
                   cheque("doc:chq-2043", "2025-09-30"), "August payroll withholdings deposit, check 2043"),
    BankFee("event:fee-2025-09", "2025-09-30", D("48.00"), "Monthly service charge and check image fees"),
    # October 2025: the task period
    ExpensePayment("event:rent-2025-10", "2025-10-02", "party:quayside", D("4275.00"),
                   cheque("doc:chq-1144", "2025-10-06"),
                   "October rent, store, warehouse and dock frontage, rent review from 1 October"),
    VendorPayment("event:pi-7752-payment", "2025-10-03", "party:seaforth", "doc:pi-7752", D("4618.30"),
                  cheque("doc:chq-1145", "2025-10-08"), "Payment of purchase invoice PI-7752, check 1145"),
    ExpensePayment("event:helmsight-2025-10", "2025-10-06", "party:helmsight", D("236.40"),
                   card("2025-10-07"), "Chart and inventory software subscription, October, two seats added"),
    ExpensePayment("event:ic-funding-2025-10-06", "2025-10-06", "party:bluewater-services", D("2400.00"),
                   cheque("doc:chq-2044", "2025-10-09"), "Intercompany funding to Bluewater Marine Services LLC, check 2044"),
    Purchase("event:pi-7766-purchase", "2025-10-06", "party:petrel", "doc:pi-7766", D("2475.40"),
             "Purchase invoice PI-7766 received, antifouling and topside paint"),
    Sale("event:si-2211-sale", "2025-10-07", "party:tidewater", "doc:si-2211", D("3912.75"), D("0.08"), D("2540.00"),
         "Sale SI-2211, anchor rode, fenders and dock lines", "Cost of goods sold on SI-2211"),
    ExpensePayment("event:claim-okonkwo-2025-10", "2025-10-08", "party:okonkwo", D("412.36"),
                   cheque("doc:chq-2045", "2025-10-14"), "Expense claim, September customer visits, mileage and ferry fares, check 2045"),
    CustomerReceipt("event:si-2198-receipt", "2025-10-09", "party:kittiwake", "doc:si-2198", D("6069.60"),
                    ach_in("2025-10-09"), "Customer payment for SI-2198"),
    ExpensePayment("event:gullwing-2025-10", "2025-10-10", "party:gullwing", D("3685.40"),
                   cheque("doc:chq-2046", "2025-10-16"), "Electric pallet stacker for the warehouse, check 2046"),
    ExpensePayment("event:shearwater-2025-10", "2025-10-10", "party:shearwater", D("312.75"),
                   card("2025-10-11"), "Store and warehouse phone and internet, October"),
    BankFee("event:fee-2025-10-analysis", "2025-10-13", D("35.00"), "Account analysis fee for September"),
    ExpensePayment("event:wavecrest-2025-10", "2025-10-13", "party:wavecrest", D("173.62"),
                   card("2025-10-14"), "Fuel card, delivery van"),
    ExpensePayment("event:salestax-2025-09-remit", "2025-10-14", "party:revenue-dept", D("2318.46"),
                   cheque("doc:chq-1146", "2025-10-17"), "September sales tax return, check 1146"),
    Purchase("event:pi-7769-purchase", "2025-10-15", "party:northstar", "doc:pi-7769", D("3146.90"),
             "Purchase invoice PI-7769 received, chartplotters and transducers"),
    Prepayment("event:insurance-2025-11-prepaid", "2025-10-15", "party:lighthouse", D("1962.50"),
               cheque("doc:chq-2047", "2025-10-20"), "2025-11",
               "November hull and liability premium paid in advance, check 2047"),
    Sale("event:si-2216-sale", "2025-10-16", "party:kittiwake", "doc:si-2216", D("7284.00"), D("0.08"), D("4690.00"),
         "Sale SI-2216, outboard spares and safety gear for the charter fleet", "Cost of goods sold on SI-2216"),
    CustomerReceipt("event:si-2206-receipt", "2025-10-16", "party:tidewater", "doc:si-2206", D("1370.67"),
                    ach_in("2025-10-16"), "Customer payment for SI-2206"),
    ExpensePayment("event:dockside-2025-10", "2025-10-16", "party:dockside", D("148.29"),
                   card("2025-10-17"), "Printer toner and invoice forms"),
    ExpensePayment("event:claim-ferrier-2025-10", "2025-10-17", "party:ferrier", D("287.90"),
                   cheque("doc:chq-2048", "2025-10-22"), "Expense claim, rigging course travel and lodging, check 2048"),
    VendorPayment("event:pi-7766-payment", "2025-10-17", "party:petrel", "doc:pi-7766", D("2475.40"),
                  ach_out("2025-10-17"), "Payment of purchase invoice PI-7766"),
    CustomerReceipt("event:si-2203-receipt", "2025-10-20", "party:osprey-cove", "doc:si-2203", D("5266.08"),
                    cheque("doc:chq-5528", "2025-10-23"), "Customer check 5528 received for SI-2203"),
    ExpensePayment("event:cormorant-2025-10", "2025-10-20", "party:cormorant", D("264.85"),
                   card("2025-10-21"), "Test tank pump repaired, outboard service bay"),
    VendorPayment("event:pi-7758-payment", "2025-10-21", "party:northstar", "doc:pi-7758", D("2689.45"),
                  ach_out("2025-10-21"), "Payment of purchase invoice PI-7758"),
    ExpensePayment("event:ic-funding-2025-10-21", "2025-10-21", "party:bluewater-services", D("3500.00"),
                   cheque("doc:chq-2049", "2025-10-24"), "Intercompany funding to Bluewater Marine Services LLC, check 2049"),
    Purchase("event:pi-7773-purchase", "2025-10-22", "party:seaforth", "doc:pi-7773", D("2914.60"),
             "Purchase invoice PI-7773 received, braided dock line and mooring pennants"),
    ExpensePayment("event:puffin-2025-10", "2025-10-22", "party:puffin", D("486.15"),
                   card("2025-10-23"), "Two nights lodging, regional marine trade show"),
    Sale("event:si-2219-sale", "2025-10-24", "party:osprey-cove", "doc:si-2219", D("2648.00"), D("0.08"), D("1680.00"),
         "Sale SI-2219, antifouling paint and anodes for the winter haul-out", "Cost of goods sold on SI-2219"),
    CustomerReceipt("event:si-2211-receipt", "2025-10-27", "party:tidewater", "doc:si-2211", D("4225.77"),
                    ach_in("2025-10-27"), "Customer payment settling SI-2211"),
    ExpensePayment("event:payroll-pellerin-2025-10", "2025-10-27", "party:pellerin", D("2984.15"),
                   cheque("doc:chq-2050", "2025-10-30"), "October net pay, check 2050"),
    ExpensePayment("event:payroll-solvang-2025-10", "2025-10-27", "party:solvang", D("2647.80"),
                   cheque("doc:chq-2051", "2025-10-29"), "October net pay, check 2051"),
    ExpensePayment("event:payroll-barrowman-2025-10", "2025-10-27", "party:barrowman", D("2312.55"),
                   cheque("doc:chq-2052", "2025-10-31"), "October net pay, check 2052"),
    # issued in October, cleared by the bank in November: the timing difference
    VendorPayment("event:pi-7761-payment", "2025-10-28", "party:seaforth", "doc:pi-7761", D("3377.85"),
                  cheque("doc:chq-1147", "2025-11-03"), "Payment of purchase invoice PI-7761, check 1147"),
    ExpensePayment("event:payrolltax-2025-09-remit", "2025-10-29", "party:federal-revenue", D("1476.30"),
                   cheque("doc:chq-2053", "2025-10-31"), "September payroll withholdings deposit, check 2053"),
    CustomerReceipt("event:si-2216-partial", "2025-10-30", "party:kittiwake", "doc:si-2216", D("3950.00"),
                    ach_in("2025-10-30"), "Partial payment against SI-2216"),
    # received on the last business day, deposited by the bank in November: the deposit in transit
    CustomerReceipt("event:si-2219-receipt", "2025-10-30", "party:osprey-cove", "doc:si-2219", D("2859.84"),
                    cheque("doc:chq-5531", "2025-11-04"), "Customer check 5531 received for SI-2219"),
    BankFee("event:fee-2025-10", "2025-10-31", D("54.00"), "Monthly service charge and check image fees"),
)

WORLD = World(
    id="bluewater-2025-10",
    title="Bluewater Marine Supply - FY2025",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:pelican-point-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-09-01", D("63915.47")),
    opening=OpeningPosition("2025-10-01", (("Assets:AR", D("12706.35")), ("Assets:Inventory", D("41230.00")),
                                           ("Assets:Equipment", D("18650.00")),
                                           ("Assets:Due-From-Bluewater-Svc", D("9500.00")),
                                           ("Liabilities:AP", D("-12140.85")),
                                           ("Liabilities:SalesTax-Payable", D("-2318.46")),
                                           ("Liabilities:PayrollTax", D("-1476.30")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

PERIOD = Period("2025-10-01", "2025-10-31", "October 2025")

SALES_TAX_REMITTANCE_001 = TaskSpec(
    id="sales_tax_remittance_001",
    type="bank_reconciliation",
    prompt=("The September sales tax return was filed and remitted to the State Department of Revenue in October, "
            "and October now needs closing. The sales tax ledger and the checking account do not agree with the "
            "Pelican Point Bank statement for October. Reconcile the checking account against the statement, "
            "correct the books under the bookkeeping policy, and write the corrected ledger back to "
            "ledger.beancount."),
    period=Period("2025-10-01", "2025-10-31", "October 2025"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_sales_tax_remittance", "rec:salestax-2025-09-remit",
                        "the statement row names the department and the check number (CHECK 1146 STATE DEPARTMENT "
                        "OF REVENUE) and no ledger entry matches it; vendors.csv lists the department with default "
                        "account Liabilities:SalesTax-Payable and terms of monthly filing, so under the sales-tax "
                        "and sales-tax-remittance sections the check settles that liability, the dates section "
                        "puts it on the bank's date, and the September archive shows the same pattern (CHECK 1143 "
                        "STATE DEPARTMENT OF REVENUE for the August return)"),
        AlterRecognition("transposed_customer_receipt", "rec:si-2198-receipt", "transpose_digits", 2,
                         "the ledger carries the 9 October receipt of SI-2198 from Kittiwake Charters at 6096.60 "
                         "while the statement row of the same date, payer and reference (ACH IN KITTIWAKE "
                         "CHARTERS, SI-2198) shows 6069.60, which is also the invoice gross in the open receivable; "
                         "the customer-receipts section says to re-post the entry at the statement's amount on the "
                         "original date, against Assets:AR"),
        DuplicateRecognition("duplicated_bank_fee", "rec:fee-2025-10",
                             "the ledger carries the 31 October monthly service charge of 54.00 twice and the "
                             "statement shows one bank-initiated row of that amount; the bank-service-charges and "
                             "sales-tax-remittance sections say a charge applied once is recorded once and one "
                             "copy is removed, the other left as it was"),
    )),
)

BANK_RECON_BLUEWATER = TaskSpec(
    id="bank_recon_bluewater",
    type="bank_reconciliation",
    prompt=("The Pelican Point Bank statement for October 2025 is in and the checking account has to be closed. "
            "Tie the ledger out to the statement row by row: the customers' deposits, the rent and supplier "
            "checks, the card rows and the bank's own charges. Whatever differs, correct under the bookkeeping "
            "policy - a deposit the bank shows that the books lack, an amount that was keyed wrongly, an entry "
            "booked more than once - and leave the timing items alone. Write the corrected ledger back to "
            "ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_deposit", "rec:si-2211-receipt",
                        "the statement row of 27 October names the payer and the invoice (ACH IN TIDEWATER "
                        "BOATWORKS, SI-2211) and no ledger entry matches it; customers.csv maps Tidewater "
                        "Boatworks to Assets:AR, the ledger carries the open sale SI-2211 for the same gross, and "
                        "the collections and dates sections put the added entry against Assets:AR on the bank's "
                        "date"),
        AlterRecognition("transposed_supplier_check", "rec:pi-7752-payment", "transpose_digits", 3,
                         "the ledger carries the 3 October payment of PI-7752 to Seaforth Cordage and Rigging by "
                         "check 1145 at 4613.80 while the statement row naming the same check (CHECK 1145 SEAFORTH "
                         "CORDAGE AND RIGGING, 8 October) shows 4618.30, which is also the invoice gross in the "
                         "opening payable; vendors.csv books Seaforth to Assets:Inventory so the check settles "
                         "Liabilities:AP, and the payment-runs section says to re-post it at the statement's "
                         "amount on the original date, the supplier and the invoice unchanged"),
        DuplicateRecognition("duplicated_analysis_fee", "rec:fee-2025-10-analysis",
                             "the ledger carries the 13 October account analysis fee of 35.00 twice and the "
                             "statement shows one bank-initiated row of that amount on that date; the "
                             "bank-service-charges section says a charge applied once is recorded once, so one "
                             "copy is removed and the other left as it was"),
    )),
)

AP_PAYMENT_RUN_BLUEWATER = TaskSpec(
    id="ap_payment_run_bluewater",
    type="bank_reconciliation",
    prompt=("October's supplier payments have all gone out - the trade check to Seaforth early in the month, the "
            "ACH payments to Petrel and Northstar in the second half, and a second Seaforth check on the 28th - "
            "and the payables ledger no longer agrees with the Pelican Point Bank statement. Work through the "
            "purchase invoices, the ACH payments and the trade checks against the statement, correct the books "
            "under the bookkeeping policy, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_supplier_check", "rec:pi-7752-payment",
                        "the statement row of 8 October names the check and the supplier (CHECK 1145 SEAFORTH "
                        "CORDAGE AND RIGGING) and no ledger entry names check 1145; vendors.csv books Seaforth to "
                        "Assets:Inventory, so under the payments-to-suppliers and payment-runs sections the check "
                        "settles Liabilities:AP, and the dates section puts it on the bank's date; the September "
                        "archive shows the same pattern (CHECK 1142 SEAFORTH CORDAGE AND RIGGING for PI-7731)"),
        AlterRecognition("transposed_ach_payment", "rec:pi-7766-payment", "transpose_digits", 2,
                         "the ledger carries the 17 October ACH payment of PI-7766 to Petrel Paint and Coatings "
                         "at 2457.40 while the statement row of the same date, payee and reference (ACH OUT PETREL "
                         "PAINT AND COATINGS, PI-7766) shows 2475.40, which is also the amount of the purchase "
                         "PI-7766 booked on 6 October; the payment-runs section says to re-post it at the "
                         "statement's amount on the original date, the supplier and invoice unchanged"),
        DuplicateRecognition("duplicated_ach_payment", "rec:pi-7758-payment",
                             "the ledger carries the 21 October ACH payment of PI-7758 to Northstar Marine "
                             "Electronics (2689.45) twice and the statement shows one row (ACH OUT NORTHSTAR "
                             "MARINE ELECTRONICS, PI-7758) of that amount; the payment-runs section says a "
                             "payment posted twice loses one copy and keeps the other exactly as it was"),
    )),
)

AR_COLLECTIONS_BLUEWATER = TaskSpec(
    id="ar_collections_bluewater",
    type="bank_reconciliation",
    prompt=("Collections for October 2025 need closing. The three trade customers paid by ACH and by check during "
            "the month, Kittiwake Charters paid part of its October invoice on account, and a check that came in "
            "on the last business day has not yet reached the bank. Bring the receivables and the checking "
            "account into agreement with the Pelican Point Bank statement under the bookkeeping policy, and "
            "write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_partial_receipt", "rec:si-2216-partial",
                        "the statement row of 30 October names the payer and the invoice (ACH IN KITTIWAKE "
                        "CHARTERS, SI-2216) for 3950.00 and no ledger entry matches it; customers.csv maps "
                        "Kittiwake Charters to Assets:AR, the ledger carries the open sale SI-2216 for a larger "
                        "gross, and the customer-receipts and collections sections record a payment on account "
                        "for the amount received against Assets:AR on the bank's date"),
        AlterRecognition("transposed_check_receipt", "rec:si-2203-receipt", "transpose_digits", 1,
                         "the ledger carries the 20 October receipt of customer check 5528 from Osprey Cove "
                         "Marina for SI-2203 at 5626.08 while the statement's deposit row of 23 October naming "
                         "the same check (CHECK 5528 OSPREY COVE MARINA) shows 5266.08, which is also the "
                         "invoice gross in the open receivable; the customer-receipts section says to re-post "
                         "the entry at the statement's amount on the original date, against Assets:AR"),
        DuplicateRecognition("duplicated_ach_receipt", "rec:si-2211-receipt",
                             "the ledger carries the 27 October receipt of SI-2211 from Tidewater Boatworks "
                             "(4225.77) twice and the statement shows one row (ACH IN TIDEWATER BOATWORKS, "
                             "SI-2211) of that amount; the collections section says a receipt posted twice "
                             "loses one copy and keeps the other exactly as it was"),
    )),
)

BANK_FEED_CATEGORISATION_BLUEWATER = TaskSpec(
    id="bank_feed_categorisation_bluewater",
    type="bank_reconciliation",
    prompt=("The October 2025 debit card spend has come through on the Pelican Point Bank feed: the software "
            "subscription, phone and internet, office supplies, trade show lodging, the van's fuel and a repair. "
            "Categorise each card row to the account the vendor master gives its vendor, reconcile the card "
            "spend and the rest of the checking account against the statement under the bookkeeping policy, "
            "and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_software_charge", "rec:helmsight-2025-10",
                        "the statement row of 7 October (DEBIT CARD HELMSIGHT SOFTWARE, 236.40) has no ledger "
                        "entry; vendors.csv lists Helmsight Software with default account Expenses:Software and "
                        "terms card on file, so the card-spend section records the row to Expenses:Software on "
                        "the bank's date; the September archive shows the same vendor's subscription"),
        OmitRecognition("unrecorded_lodging_charge", "rec:puffin-2025-10",
                        "the statement row of 23 October (DEBIT CARD PUFFIN INN AND SUITES, 486.15) has no "
                        "ledger entry; vendors.csv lists Puffin Inn and Suites with default account "
                        "Expenses:Travel and terms card on file, so the card-spend section records the row to "
                        "Expenses:Travel on the bank's date"),
        AlterRecognition("transposed_telecom_charge", "rec:shearwater-2025-10", "transpose_digits", 2,
                         "the ledger carries the 10 October card charge from Shearwater Telecom at 317.25 while "
                         "the statement row of 11 October for the same vendor (DEBIT CARD SHEARWATER TELECOM) "
                         "shows 312.75 and no other Shearwater row is near it; the card-spend section says to "
                         "re-post the charge at the statement's amount on its original date, against "
                         "Expenses:Telecom per vendors.csv"),
    )),
)

EXPENSE_REPORTS_BLUEWATER = TaskSpec(
    id="expense_reports_bluewater",
    type="bank_reconciliation",
    prompt=("Two staff expense claims were reimbursed by disbursements check in October 2025 - Nadia Okonkwo's "
            "September customer visits and Callum Ferrier's rigging course - and the delivery van's fuel card "
            "ran as usual. The claims register does not tie to the Pelican Point Bank statement. Reconcile the "
            "reimbursement checks, the fuel card and the rest of the checking account against the statement, "
            "correct the books under the bookkeeping policy, and write the corrected ledger back to "
            "ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_claim_reimbursement", "rec:claim-okonkwo-2025-10",
                        "the statement row of 14 October names the check and the claimant (CHECK 2045 NADIA "
                        "OKONKWO, 412.36) and no ledger entry names check 2045; vendors.csv lists Nadia Okonkwo "
                        "on expense claim terms with default account Expenses:Travel, so the employee-expense-"
                        "claims section records the reimbursement to Expenses:Travel on the bank's date; the "
                        "September archive shows the same claimant's check 2038"),
        DuplicateRecognition("duplicated_claim_reimbursement", "rec:claim-ferrier-2025-10",
                             "the ledger carries the 17 October reimbursement to Callum Ferrier by check 2048 "
                             "(287.90) twice and the statement shows one row (CHECK 2048 CALLUM FERRIER) of that "
                             "amount; the employee-expense-claims section says a reimbursement posted twice "
                             "loses one copy and keeps the other exactly as it was"),
        AlterRecognition("transposed_fuel_charge", "rec:wavecrest-2025-10", "transpose_digits", 1,
                         "the ledger carries the 13 October fuel card charge from Wavecrest Marine Fuel at "
                         "137.62 while the statement row of 14 October for the same vendor (DEBIT CARD WAVECREST "
                         "MARINE FUEL) shows 173.62 and no other Wavecrest row is near it; vendors.csv books "
                         "Wavecrest to Expenses:Vehicle and the employee-expense-claims section says to re-post "
                         "the charge at the statement's amount on its original date"),
    )),
)

PAYROLL_BLUEWATER = TaskSpec(
    id="payroll_bluewater",
    type="bank_reconciliation",
    prompt=("October 2025 payroll was paid by disbursements check on the 27th - one net pay check per employee - "
            "and the September withholdings were deposited with the Federal Revenue Service by check on the "
            "29th. The payroll ledger does not agree with the Pelican Point Bank statement for October. Reconcile "
            "the net pay checks and the withholdings deposit against the statement, correct the books under the "
            "bookkeeping policy, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_net_pay_check", "rec:payroll-solvang-2025-10",
                        "the statement row of 29 October names the check and the employee (CHECK 2051 INGRID "
                        "SOLVANG, 2647.80) and no ledger entry names check 2051; vendors.csv lists Ingrid Solvang "
                        "on monthly payroll terms with default account Expenses:Salaries, so the payroll section "
                        "records the net pay to Expenses:Salaries on the bank's date; the September archive "
                        "shows the same employee's check 2041"),
        AlterRecognition("transposed_net_pay_check", "rec:payroll-barrowman-2025-10", "transpose_digits", 1,
                         "the ledger carries the 27 October net pay check 2052 to Theo Barrowman at 2132.55 "
                         "while the statement row naming the same check (CHECK 2052 THEO BARROWMAN, 31 October) "
                         "shows 2312.55; the payroll section says to re-post the check at the statement's amount "
                         "on its original date, against Expenses:Salaries per vendors.csv"),
        OmitRecognition("unrecorded_withholdings_deposit", "rec:payrolltax-2025-09-remit",
                        "the statement row of 31 October names the check and the payee (CHECK 2053 FEDERAL "
                        "REVENUE SERVICE, 1476.30) and no ledger entry names check 2053; vendors.csv lists the "
                        "Federal Revenue Service on payroll tax deposit terms with default account "
                        "Liabilities:PayrollTax, so under the payroll section the check settles that liability, "
                        "whose opening balance is the same figure, on the bank's date; the September archive "
                        "shows the same pattern (CHECK 2043 FEDERAL REVENUE SERVICE for the August deposit)"),
    )),
)

FIXED_ASSETS_BLUEWATER = TaskSpec(
    id="fixed_assets_bluewater",
    type="bank_reconciliation",
    prompt=("Bluewater bought an electric pallet stacker for the warehouse from Gullwing Dock Equipment in October "
            "2025, paid on delivery by disbursements check, and had the outboard test tank pump repaired by "
            "Cormorant Engine Repair on the card. The equipment register and the checking account do not agree "
            "with the Pelican Point Bank statement. Reconcile the equipment check, the repair charge and the rest "
            "of the account against the statement, capitalising or expensing each as the bookkeeping policy "
            "directs, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_equipment_check", "rec:gullwing-2025-10",
                        "the statement row of 16 October names the check and the supplier (CHECK 2046 GULLWING "
                        "DOCK EQUIPMENT, 3685.40) and no ledger entry names check 2046; vendors.csv lists "
                        "Gullwing with default account Assets:Equipment and due on delivery terms, so the "
                        "equipment section capitalises the payment to Assets:Equipment on the bank's date"),
        AlterRecognition("transposed_repair_charge", "rec:cormorant-2025-10", "transpose_digits", 1,
                         "the ledger carries the 20 October card charge from Cormorant Engine Repair at 246.85 "
                         "while the statement row of 21 October for the same vendor (DEBIT CARD CORMORANT ENGINE "
                         "REPAIR) shows 264.85 and no other Cormorant row is near it; vendors.csv books "
                         "Cormorant to Expenses:Repairs and the equipment section says to re-post the charge at "
                         "the statement's amount on its original date"),
        OmitRecognition("unrecorded_analysis_fee", "rec:fee-2025-10-analysis",
                        "the statement row of 13 October is a bank-initiated charge with no counterparty "
                        "(ACCOUNT ANALYSIS FEE FOR SEPTEMBER, 35.00) and no ledger entry matches it; the "
                        "bank-service-charges section records it to Expenses:BankFees on the date the bank "
                        "applied it"),
    )),
)

INTERCOMPANY_TRANSFERS_BLUEWATER = TaskSpec(
    id="intercompany_transfers_bluewater",
    type="bank_reconciliation",
    prompt=("Bluewater funded its sister company Bluewater Marine Services LLC twice in October 2025 by "
            "disbursements check while the service crews' own receipts ran slow, and the intercompany balance "
            "does not agree with the Pelican Point Bank statement. Reconcile the funding checks, the customer "
            "receipts and the rest of the checking account against the statement, correct the books under the "
            "bookkeeping policy, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_funding_check", "rec:ic-funding-2025-10-21",
                        "the statement row of 24 October names the check and the sister company (CHECK 2049 "
                        "BLUEWATER MARINE SERVICES LLC, 3500.00) and no ledger entry names check 2049; "
                        "vendors.csv lists the sister company on intercompany terms with default account "
                        "Assets:Due-From-Bluewater-Svc, so the intercompany-balances section records the "
                        "funding to that account on the bank's date; the September archive shows the same "
                        "pattern (CHECK 2039 BLUEWATER MARINE SERVICES LLC)"),
        DuplicateRecognition("duplicated_funding_check", "rec:ic-funding-2025-10-06",
                             "the ledger carries the 6 October funding check 2044 to Bluewater Marine Services "
                             "LLC (2400.00) twice and the statement shows one row (CHECK 2044 BLUEWATER MARINE "
                             "SERVICES LLC) of that amount; the intercompany-balances section says a funding "
                             "check posted twice loses one copy and keeps the other exactly as it was"),
        AlterRecognition("transposed_customer_receipt", "rec:si-2206-receipt", "transpose_digits", 1,
                         "the ledger carries the 16 October receipt of SI-2206 from Tidewater Boatworks at "
                         "1730.67 while the statement row of the same date, payer and reference (ACH IN "
                         "TIDEWATER BOATWORKS, SI-2206) shows 1370.67, which is also that invoice's share of the "
                         "opening receivable; the customer-receipts section says to re-post the entry at the "
                         "statement's amount on the original date, against Assets:AR"),
    )),
)

MONTH_END_CLOSE_BLUEWATER = TaskSpec(
    id="month_end_close_bluewater",
    type="bank_reconciliation",
    prompt=("October 2025 is being closed at Bluewater Marine Supply. The November hull and liability premium was "
            "paid to Lighthouse Mutual Insurance in advance by disbursements check, the bank levied two charges "
            "during the month and the customers' receipts have all come in. Close the month against the Pelican "
            "Point Bank statement: reconcile the checking account, correct the books under the bookkeeping "
            "policy - the premium belongs in prepayments, not in expense - and write the corrected ledger back "
            "to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_insurance_prepayment", "rec:insurance-2025-11-prepaid",
                        "the statement row of 20 October names the check and the insurer (CHECK 2047 LIGHTHOUSE "
                        "MUTUAL INSURANCE, 1962.50) and no ledger entry names check 2047; vendors.csv lists the "
                        "insurer on premium in advance terms, and the prepayments section says a premium paid "
                        "in October for November is recorded to Assets:Prepayments, on the bank's date"),
        AlterRecognition("transposed_service_charge", "rec:fee-2025-10", "transpose_digits", 0,
                         "the ledger carries the 31 October monthly service charge at 45.00 while the "
                         "bank-initiated statement row of the same date and wording (MONTHLY SERVICE CHARGE AND "
                         "CHECK IMAGE FEES) shows 54.00; the bank-service-charges section records the charge "
                         "at the amount the bank applied, on that date, to Expenses:BankFees"),
        DuplicateRecognition("duplicated_customer_receipt", "rec:si-2198-receipt",
                             "the ledger carries the 9 October receipt of SI-2198 from Kittiwake Charters "
                             "(6069.60) twice and the statement shows one row (ACH IN KITTIWAKE CHARTERS, "
                             "SI-2198) of that amount; the collections section says a receipt posted twice "
                             "loses one copy and keeps the other exactly as it was"),
    )),
)

TASKS = {
    SALES_TAX_REMITTANCE_001.id: SALES_TAX_REMITTANCE_001,
    BANK_RECON_BLUEWATER.id: BANK_RECON_BLUEWATER,
    AP_PAYMENT_RUN_BLUEWATER.id: AP_PAYMENT_RUN_BLUEWATER,
    AR_COLLECTIONS_BLUEWATER.id: AR_COLLECTIONS_BLUEWATER,
    BANK_FEED_CATEGORISATION_BLUEWATER.id: BANK_FEED_CATEGORISATION_BLUEWATER,
    EXPENSE_REPORTS_BLUEWATER.id: EXPENSE_REPORTS_BLUEWATER,
    PAYROLL_BLUEWATER.id: PAYROLL_BLUEWATER,
    FIXED_ASSETS_BLUEWATER.id: FIXED_ASSETS_BLUEWATER,
    INTERCOMPANY_TRANSFERS_BLUEWATER.id: INTERCOMPANY_TRANSFERS_BLUEWATER,
    MONTH_END_CLOSE_BLUEWATER.id: MONTH_END_CLOSE_BLUEWATER,
}
