"""Oakridge Machining, March 2026: the irreducible facts.

This is the hand-reviewed layer. It states what happened — amounts, dates,
counterparties, documents, rails, clearing dates — and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

One month of one small machine shop, seen from ten desks. The shop buys its
machine tools outright and pays the equipment supplier by check on the day
the machine is delivered; it pays its stock suppliers on a monthly payment
run; it invoices machined parts to three customers who pay by ACH or by
check; its three salaried staff are paid net by check on the 25th and their
withholdings remitted to the state payroll tax bureau in the following
month; its two travelling staff file expense claims reimbursed by check and
fuel the service van on a fleet card; its running costs go on the debit
card; it remits the sales tax it collected last month; it funds a sister
company by check; and it pays the shop insurance a month ahead of cover.
Every task below sees the same statement and the same golden facts; the
tasks differ only in the controller's brief and in which recognitions the
opening ledger has lost, keyed wrongly or entered twice.

The bandsaw check of 27 March and Corbett Hydraulics' check received on 31
March are not mutations at all: the bank cleared them in April, and the
March statement's projection classifies both NOT_YET_SETTLED on its own.
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

POLICY_TEXT = """# Oakridge Machining — Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, positive pay and
other service fees, wire fees, returned item fees) are recorded to
`Expenses:BankFees` on the date the bank applies them. Each charge is its own
entry: two charges in one month are two entries, each for the amount and on
the date the statement shows, and a charge is never rolled into another.

## Customer receipts
Cash received from a customer reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice. A customer may
pay by ACH, in which case the bank prints the invoice number as the reference,
or by check, in which case the bank prints the customer's check number and the
customer's name. A receipt is booked for the amount actually received, whether
or not it settles the invoice in full.

## Collections
Oakridge invoices machined parts and fabrication on net 30 terms and ties the
receivables ledger to the bank at every close. Three kinds of difference arise
and each has exactly one correction:

- A deposit the statement shows that the books do not carry is added as a
  receipt from the customer the row names, for the amount the row shows, to
  `Assets:AR`, on the date the bank shows (see Dates below).
- A receipt the books carry with an amount that differs from the statement's
  has been keyed wrongly: it is re-posted with the statement's amount, on the
  date it was originally entered, and the wrong figure is not left standing
  alongside it. A receipt keyed at a tenth of the deposit is the commonest
  case; the deposit row is the authority for the amount.
- A receipt the books carry twice against a single deposit has been posted
  twice: one copy is removed and the other is left exactly as it was.

A partial payment is applied to the invoice it references and the balance
stays open on `Assets:AR`; it is never written off, held in a holding account
or netted against another invoice. A customer's check received and recorded
before the cut-off that the bank clears after it is a deposit in transit,
governed by the section below.

## Payments to suppliers
The `default_account` a supplier carries in the vendor master is where that
supplier's purchases are booked when they arrive. It is not always where a
payment to that supplier lands, and the account itself says which it is.

Where a supplier's purchases are booked to `Assets:Inventory` — the steel and
bar stock suppliers — the material was taken into that account when it was
received and a payable was raised for it at the same time, so cash paid to
that supplier afterwards settles the payable and is recorded to
`Liabilities:AP`.

Where a supplier's purchases are booked to `Assets:Equipment`, the supplier
sells capital equipment, and Oakridge pays for equipment on delivery. No
payable is raised and nothing passes through `Liabilities:AP`: the payment
is the purchase, capitalised as the equipment section below describes. An
equipment supplier is not a stock supplier with an account, even though both
carry an asset account in the vendor master.

Where a supplier's purchases are booked to an expense account, no payable is
raised: the payment is the expense, and it is recorded to that supplier's own
`default_account` on the day it is paid, except where it is paid ahead of the
period it covers, which the prepayments section below governs.

The vendor master also carries payees that are not suppliers of goods or
services at all: the shop's employees, the state payroll tax bureau, the
state sales tax commission, the insurer and the sister company. The
`default_account` each of those carries is exactly where a payment to that
payee lands, and the section of this policy named for that payee governs the
entry. No payable is ever raised for any of them.

## Payment runs
Stock suppliers are paid on a monthly payment run against their purchase
invoices. Each payment is one entry per invoice, dated the day it was
released, with the supplier as payee and the invoice number in the narration:
a debit to `Liabilities:AP` and a credit to the checking account for the
invoice amount. A run may pay by ACH, in which case the bank prints the
invoice number as the reference, or by check drawn on the operating check
stock, in which case the bank prints the check number. Three kinds of
difference arise against the statement and each has exactly one correction:

- A supplier payment the statement shows that the books lack is added for the
  supplier and the amount the row shows, to `Liabilities:AP`, on the date the
  bank shows (see Dates below).
- A supplier payment the books carry with an amount that differs from the
  statement's has been keyed wrongly: it is re-posted with the statement's
  amount, on the date it was originally entered, and the wrong figure is not
  left standing alongside it.
- A supplier payment the books carry twice against a single statement row has
  been posted twice: one copy is removed and the other is left exactly as it
  was.

A payment is never split across invoices, netted against a credit or held in
a holding account.

## Equipment
Machine tools and shop equipment are bought from the suppliers the vendor
master carries with `Assets:Equipment` as their default account. Oakridge
pays for a machine by check on the day it is delivered, so the check is the
whole transaction: its amount is capitalised to `Assets:Equipment` on the
date it is paid, and depreciation is dealt with at year end, outside the
monthly close. Suppliers the vendor master carries with `Expenses:Repairs`
as their default account service and repair the machines; their charges are
maintenance, not improvements, and are expensed to `Expenses:Repairs` on the
day they are paid.

An equipment or repair payment the statement shows and the books lack is
posted to that supplier's default account on the date the bank shows. An
equipment or repair payment the books carry with an amount that differs from
the statement's has been keyed wrongly: the entry is re-posted with the
statement's amount, on the date it was originally entered, and the wrong
figure is not left standing alongside it. A check to an equipment supplier
that has not cleared by the cut-off is an outstanding check, governed by the
section below, and is left exactly as recorded.

## Card spend
The shop's running costs — the CAM software subscription, the shop's phones
and broadband, office consumables, fuel for the service van — are paid on the
business debit card and entered into the books from the bank feed, so a card
entry carries the date the bank shows. A card row on the statement whose
vendor is in the vendor master is booked to that vendor's `default_account`
on the bank's date: `Expenses:Software`, `Expenses:Telecom`, `Expenses:Office`
and `Expenses:Vehicle` are the accounts the card vendors carry. A card row
the books do not carry is added, on the bank's date, to that account. A card
row the books carry with an amount that differs from the statement's has been
keyed wrongly: the entry is re-posted with the statement's amount, on the
date it was originally entered, and the wrong figure is not left standing
alongside it. A card row the books carry twice has been entered from the feed
twice: one copy is removed and the other is left as it was. A card row whose
vendor is not in the vendor master is queried with the shop manager before it
is booked; it is never posted to a holding account.

## Employee expense claims
The outside sales engineer and the field service technician travel to
customers' plants and file expense claims for mileage, lodging and meals.
Each employee who files claims is carried in the vendor master with terms
`expense claim` and `Expenses:Travel` as the default account. No payable is
raised for a claim: an approved claim is reimbursed by check drawn on the
payroll and disbursement check stock and booked to `Expenses:Travel` on the
date the check is issued, with the employee as payee exactly as the vendor
master names them, and the check number is the claim's reference on the bank
statement.

A reimbursement check the statement shows that the books do not carry is
posted, on the date the bank shows, to `Expenses:Travel`. A claim the books
carry twice against a single check on the statement has been posted twice:
one copy is removed and the other is left as it stands. A claim is never
split, netted against another employee's claim or held over to the following
month.

The service van is fuelled on a fleet fuel card. The card issuer is in the
vendor master with `Expenses:Vehicle` as its default account and draws the
monthly fuel bill from the checking account by debit card; the draw is booked
to `Expenses:Vehicle` on the day the bank shows it. Where the books carry the
draw at an amount that differs from the statement's, the entry has been keyed
wrongly: it is re-posted with the statement's amount on the date it was
originally entered, and the wrong figure is not left standing alongside it.

## Payroll
Oakridge's three salaried staff are paid monthly, on the 25th, by check drawn
on the payroll and disbursement check stock for each employee's net pay. Each
employee is carried in the vendor master on `monthly payroll` terms with
`Expenses:Salaries` as the default account. A net pay check is recorded as
one entry per employee, dated the day the check was written, with the
employee named as payee exactly as the vendor master lists them: a debit to
`Expenses:Salaries` and a credit to the checking account for the net amount.
No payable is raised for net pay ahead of the check.

Employee withholdings and the employer's payroll taxes are accrued to
`Liabilities:PayrollTax` by the monthly payroll journal that the payroll
bureau supplies after each close; that journal is outside the bank
reconciliation. The amount accrued for a month is remitted to the State
Payroll Tax Bureau by check on or before the 15th of the following month. The
bureau is carried in the vendor master on `monthly remittance` terms with
`Liabilities:PayrollTax` as the default account, and the remittance check
settles that liability: a debit to `Liabilities:PayrollTax` and a credit to
the checking account on the day the check is written.

The payroll postings are tied to the bank statement at every close. The bank
prints the check number and the payee on each check row. Two kinds of
difference arise, and each has exactly one correction:

- A net pay or remittance check that appears on the statement but that the
  books lack is added for the payee and the amount the statement shows,
  against the payee's default account, on the date the bank shows (see Dates
  below).
- A net pay check posted with a mis-keyed amount is corrected by re-posting
  the entry with the amount the statement shows, on the date the entry was
  originally posted. Only the amount changes; the date, the payee and the
  accounts stay as they were.

A check that is on both the statement and the ledger with the same payee and
amount is a match and is not touched. A payroll check the books carry that
the bank has not cleared at the cut-off is an outstanding check and is left
as it is.

## Intercompany balances
Oakridge Machining funds its sister company, Oakridge Coatings LLC, by check
whenever the coatings shop's own collections will not cover its payroll and
suppliers. Every advance is a debit to `Assets:Due-From-Coatings-LLC`, the
default account the vendor master lists for the sister company, and a credit
to the checking account, dated the day the check was issued, with the sister
company as payee. The advance is repayable and stays on that account until it
is repaid; it is never expensed, never treated as a payable and never netted
against anything else.

The intercompany balance is agreed with the coatings shop's own books at
every month-end, so `Assets:Due-From-Coatings-LLC` must carry each advance
exactly once. Three kinds of difference arise against the bank statement, and
each has exactly one correction:

- An advance that appears on the statement but that the books lack is added
  for the sister company and the amount the statement shows, to
  `Assets:Due-From-Coatings-LLC`, on the date the bank shows (see Dates
  below).
- An advance that was posted twice is corrected by removing one of the two
  copies. The copy that remains is left exactly as it was.
- An advance posted with a mis-keyed amount is corrected by re-posting the
  entry with the amount the statement shows, on the date the entry was
  originally posted.

An advance that is on both the statement and the ledger with the same payee,
check number and amount is a match and is not touched.

## Check stocks
Two check stocks are drawn on the one checking account. The operating stock
(2100 series) pays stock suppliers, equipment suppliers and the landlord. The
payroll and disbursement stock (5000 series) pays net pay, expense claims,
tax remittances, the insurer and intercompany advances. The bank prints the
check number and the payee on every check row whichever stock it came from,
and the stock a check came from never changes where its entry is posted: the
payee's section of this policy does.

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
customer or supplier movement the ledger date is never later than the
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

The shop's property and liability insurance is invoiced by the insurer a
month in advance and is paid by check in the month before the cover month. A
premium paid in March for April cover is booked to `Assets:Prepayments` on
the date the check is issued and released to `Expenses:Insurance` in April by
the close journal, which is outside the bank reconciliation. The insurer
carries `Assets:Prepayments` as its `default_account` in the vendor master
for exactly this reason: every payment to the insurer is a payment in
advance, and the vendor master and this section agree on where it lands. No
payable is raised for a premium. A premium check the statement shows that
the books do not carry is added to `Assets:Prepayments` for the amount the
row shows, on the date the bank shows.

## Sales tax
Oakridge collects sales tax from customers at the state rate of 7% on
machined parts and fabrication work and owes it to the state. The tax is
credited to `Liabilities:SalesTax-Payable` on the day the sale is invoiced;
it is not revenue. The balance of that account at any date is the tax
collected and not yet remitted. Steel and bar stock bought for jobs is exempt
under the shop's resale certificate, so no tax is recoverable on the purchase
side.

## Sales tax remittance
The State Sales Tax Commission is carried in the vendor master with
`Liabilities:SalesTax-Payable` as its default account and terms of `monthly
filing`. It is not a supplier of goods or services: a payment to the
commission is neither a purchase nor an expense. It settles the tax
liability for the month the return covers, so it is recorded as a debit to
`Liabilities:SalesTax-Payable` and a credit to the checking account, dated
the day it was paid. The return for a month is filed and paid by the 20th of
the following month, for the amount the return reports, by check or by debit
card through the commission's filing portal. A remittance the statement shows
that the books do not carry is added to `Liabilities:SalesTax-Payable` for
the amount the row shows, on the date the bank shows.

## Month-end close checklist
The checking account is agreed to the bank statement before the month is
closed, and each difference has exactly one correction:

- Bank charges are agreed to the statement line by line. A charge on the
  statement that the ledger does not carry is added to `Expenses:BankFees`
  for the statement's amount on the statement's date. A bank charge posted
  with a mis-keyed amount is corrected by re-posting the entry with the
  amount the statement shows, on the date the entry was originally posted;
  only the amount changes.
- Customer receipts are applied to invoices. A receipt that was posted twice
  is corrected by removing one of the two copies; the copy that remains is
  left exactly as it was.
- A payment on the statement that the ledger does not carry is added for the
  payee and the amount the statement shows, to the account the vendor master
  and this policy give for that payee, on the date the bank shows.
- Checks issued before the cut-off that clear after it, and customer checks
  received before the cut-off that the bank clears after it, are listed as
  outstanding items and are not touched.

## Suspense accounts
Oakridge does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
"""

OPENED = "2023-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Shop operating checking account held at Sawmill Creek Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Machining and fabrication charges receivable from customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Steel, bar stock and plate held for jobs", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Assets:Due-From-Coatings-LLC", K.ASSET, "Advances to Oakridge Coatings LLC, repayable", OPENED, 1400),
    Account("Assets:Equipment", K.ASSET, "Machine tools and shop equipment, at cost", OPENED, 1500),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to stock suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Liabilities:PayrollTax", K.LIABILITY, "Employee withholdings and employer payroll taxes accrued and not yet remitted", OPENED, 2200),
    Account("Income:Sales", K.INCOME, "Machining and fabrication revenue", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Material consumed on jobs", OPENED, 5000),
    Account("Expenses:Repairs", K.EXPENSE, "Machine repairs and maintenance", OPENED, 5100),
    Account("Expenses:Rent", K.EXPENSE, "Shop premises rent for the period", OPENED, 5200),
    Account("Expenses:Insurance", K.EXPENSE, "Shop property and liability insurance for the month of cover", OPENED, 5250),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Expenses:Salaries", K.EXPENSE, "Net salaries paid to the shop's staff", OPENED, 5400),
    Account("Expenses:Travel", K.EXPENSE, "Mileage, lodging and meals on customer visits, reimbursed on claim", OPENED, 5500),
    Account("Expenses:Vehicle", K.EXPENSE, "Fuel and running costs of the service van", OPENED, 5510),
    Account("Expenses:Software", K.EXPENSE, "CAM and shop software subscriptions", OPENED, 5600),
    Account("Expenses:Telecom", K.EXPENSE, "Shop phones and broadband", OPENED, 5610),
    Account("Expenses:Office", K.EXPENSE, "Office consumables and printing", OPENED, 5620),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:corbett-hydraulics", "Corbett Hydraulics", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:stellan-aero", "Stellan Aero Components", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:penrose-metals", "Penrose Metals", R.VENDOR, 3, "net 30", "Assets:Inventory"),
    Party("party:haldane-machine-tool", "Haldane Machine Tool", R.VENDOR, 4, "due on receipt", "Assets:Equipment"),
    Party("party:brixworth-equipment", "Brixworth Industrial Equipment", R.VENDOR, 5, "due on receipt", "Assets:Equipment"),
    Party("party:wyvern-spindle", "Wyvern Spindle Services", R.VENDOR, 6, "due on receipt", "Expenses:Repairs"),
    Party("party:kilbride-properties", "Kilbride Properties", R.VENDOR, 7, "due on receipt", "Expenses:Rent"),
    Party("party:sawmill-creek-bank", "Sawmill Creek Bank", R.BANK, 8),
    Party("party:tolhurst-marine", "Tolhurst Marine Drives", R.CUSTOMER, 9, "net 30", "Assets:AR"),
    Party("party:tarrant-alloys", "Tarrant Alloys Inc", R.VENDOR, 10, "net 30", "Assets:Inventory"),
    Party("party:vellum-cam", "Vellum CAM Software", R.VENDOR, 11, "due on receipt", "Expenses:Software"),
    Party("party:tessaline-telecom", "Tessaline Telecom", R.VENDOR, 12, "due on receipt", "Expenses:Telecom"),
    Party("party:pennant-office", "Pennant Office Supply", R.VENDOR, 13, "due on receipt", "Expenses:Office"),
    Party("party:fleetline-fuel", "Fleetline Fuel Card", R.VENDOR, 14, "due on receipt", "Expenses:Vehicle"),
    Party("party:dana-whitfield", "Dana Whitfield", R.VENDOR, 15, "monthly payroll", "Expenses:Salaries"),
    Party("party:tomas-reinholt", "Tomas Reinholt", R.VENDOR, 16, "monthly payroll", "Expenses:Salaries"),
    Party("party:priyanka-sethuraman", "Priyanka Sethuraman", R.VENDOR, 17, "monthly payroll", "Expenses:Salaries"),
    Party("party:elliot-marchbank", "Elliot Marchbank", R.VENDOR, 18, "expense claim", "Expenses:Travel"),
    Party("party:hana-vosburgh", "Hana Vosburgh", R.VENDOR, 19, "expense claim", "Expenses:Travel"),
    Party("party:state-payroll-tax", "State Payroll Tax Bureau", R.VENDOR, 20, "monthly remittance", "Liabilities:PayrollTax"),
    Party("party:state-sales-tax", "State Sales Tax Commission", R.VENDOR, 21, "monthly filing", "Liabilities:SalesTax-Payable"),
    Party("party:oakridge-coatings", "Oakridge Coatings LLC", R.VENDOR, 22, "intercompany", "Assets:Due-From-Coatings-LLC"),
    Party("party:brackenridge-mutual", "Brackenridge Mutual Insurance", R.VENDOR, 23, "due on receipt", "Assets:Prepayments"),
)

DOCUMENTS = (
    # sales invoices
    Document("doc:si-2087", DK.SALES_INVOICE, "SI-2087", "party:corbett-hydraulics", "2026-01-16", D("11384.80")),
    Document("doc:si-2091", DK.SALES_INVOICE, "SI-2091", "party:stellan-aero", "2026-01-23", D("7720.05")),
    Document("doc:si-2095", DK.SALES_INVOICE, "SI-2095", "party:stellan-aero", "2026-02-10", D("6612.60")),
    Document("doc:si-2098", DK.SALES_INVOICE, "SI-2098", "party:corbett-hydraulics", "2026-02-17", D("9603.25")),
    Document("doc:si-2100", DK.SALES_INVOICE, "SI-2100", "party:tolhurst-marine", "2026-02-24", D("8137.45")),
    Document("doc:si-2102", DK.SALES_INVOICE, "SI-2102", "party:tolhurst-marine", "2026-03-05", D("11556.00")),
    Document("doc:si-2104", DK.SALES_INVOICE, "SI-2104", "party:stellan-aero", "2026-03-11", D("9009.40")),
    Document("doc:si-2105", DK.SALES_INVOICE, "SI-2105", "party:corbett-hydraulics", "2026-03-20", D("5644.25")),
    # purchase invoices
    Document("doc:pi-3306", DK.PURCHASE_INVOICE, "PI-3306", "party:penrose-metals", "2026-01-14", D("6842.50")),
    Document("doc:pi-3315", DK.PURCHASE_INVOICE, "PI-3315", "party:tarrant-alloys", "2026-01-29", D("3876.90")),
    Document("doc:pi-3321", DK.PURCHASE_INVOICE, "PI-3321", "party:penrose-metals", "2026-02-06", D("5318.40")),
    Document("doc:pi-3329", DK.PURCHASE_INVOICE, "PI-3329", "party:tarrant-alloys", "2026-02-20", D("2954.30")),
    Document("doc:pi-3338", DK.PURCHASE_INVOICE, "PI-3338", "party:penrose-metals", "2026-03-16", D("4762.15")),
    Document("doc:pi-3345", DK.PURCHASE_INVOICE, "PI-3345", "party:tarrant-alloys", "2026-03-24", D("3312.70")),
    # operating check stock, 2100 series
    Document("doc:chq-2101", DK.CHEQUE, "2101", "party:kilbride-properties", "2026-02-02"),
    Document("doc:chq-2102", DK.CHEQUE, "2102", "party:haldane-machine-tool", "2026-02-18"),
    Document("doc:chq-2103", DK.CHEQUE, "2103", "party:kilbride-properties", "2026-03-02"),
    Document("doc:chq-2104", DK.CHEQUE, "2104", "party:brixworth-equipment", "2026-03-05"),
    Document("doc:chq-2105", DK.CHEQUE, "2105", "party:haldane-machine-tool", "2026-03-19"),
    Document("doc:chq-2106", DK.CHEQUE, "2106", "party:brixworth-equipment", "2026-03-27"),
    Document("doc:chq-2107", DK.CHEQUE, "2107", "party:tarrant-alloys", "2026-03-27"),
    # payroll and disbursement check stock, 5000 series
    Document("doc:chq-5041", DK.CHEQUE, "5041", "party:oakridge-coatings", "2026-02-11"),
    Document("doc:chq-5042", DK.CHEQUE, "5042", "party:state-payroll-tax", "2026-02-12"),
    Document("doc:chq-5043", DK.CHEQUE, "5043", "party:elliot-marchbank", "2026-02-13"),
    Document("doc:chq-5044", DK.CHEQUE, "5044", "party:brackenridge-mutual", "2026-02-16"),
    Document("doc:chq-5045", DK.CHEQUE, "5045", "party:state-sales-tax", "2026-02-18"),
    Document("doc:chq-5046", DK.CHEQUE, "5046", "party:dana-whitfield", "2026-02-25"),
    Document("doc:chq-5047", DK.CHEQUE, "5047", "party:tomas-reinholt", "2026-02-25"),
    Document("doc:chq-5048", DK.CHEQUE, "5048", "party:priyanka-sethuraman", "2026-02-25"),
    Document("doc:chq-5049", DK.CHEQUE, "5049", "party:oakridge-coatings", "2026-03-02"),
    Document("doc:chq-5050", DK.CHEQUE, "5050", "party:state-payroll-tax", "2026-03-09"),
    Document("doc:chq-5051", DK.CHEQUE, "5051", "party:hana-vosburgh", "2026-03-10"),
    Document("doc:chq-5052", DK.CHEQUE, "5052", "party:brackenridge-mutual", "2026-03-12"),
    Document("doc:chq-5053", DK.CHEQUE, "5053", "party:elliot-marchbank", "2026-03-16"),
    Document("doc:chq-5054", DK.CHEQUE, "5054", "party:oakridge-coatings", "2026-03-17"),
    Document("doc:chq-5055", DK.CHEQUE, "5055", "party:dana-whitfield", "2026-03-25"),
    Document("doc:chq-5056", DK.CHEQUE, "5056", "party:tomas-reinholt", "2026-03-25"),
    Document("doc:chq-5057", DK.CHEQUE, "5057", "party:priyanka-sethuraman", "2026-03-25"),
    # customers' own checks, numbered by the customer
    Document("doc:chq-tolhurst-4471", DK.CHEQUE, "4471", "party:tolhurst-marine", "2026-03-10"),
    Document("doc:chq-corbett-10388", DK.CHEQUE, "10388", "party:corbett-hydraulics", "2026-03-31"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # February 2026: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2026-02", "2026-02-02", "party:kilbride-properties", D("4250.00"),
                   cheque("doc:chq-2101", "2026-02-05"), "February shop rent"),
    ExpensePayment("event:software-2026-02", "2026-02-03", "party:vellum-cam", D("189.00"),
                   card("2026-02-03"), "CAM software subscription, February"),
    VendorPayment("event:pi-3306-payment", "2026-02-04", "party:penrose-metals", "doc:pi-3306", D("6842.50"),
                  ach_out("2026-02-04"), "Payment of purchase invoice PI-3306"),
    ExpensePayment("event:telecom-2026-02", "2026-02-05", "party:tessaline-telecom", D("214.35"),
                   card("2026-02-05"), "Shop phones and broadband, February"),
    CustomerReceipt("event:si-2087-receipt", "2026-02-10", "party:corbett-hydraulics", "doc:si-2087", D("11384.80"),
                    ach_in("2026-02-10"), "Customer payment for SI-2087"),
    ExpensePayment("event:coatings-advance-2026-02", "2026-02-11", "party:oakridge-coatings", D("5200.00"),
                   cheque("doc:chq-5041", "2026-02-16"), "Advance to Oakridge Coatings LLC, check 5041"),
    ExpensePayment("event:repairs-2026-02-vmc", "2026-02-12", "party:wyvern-spindle", D("612.75"),
                   card("2026-02-12"), "Spindle bearing replacement, VMC-2"),
    ExpensePayment("event:payroll-tax-2026-02", "2026-02-12", "party:state-payroll-tax", D("2591.40"),
                   cheque("doc:chq-5042", "2026-02-17"), "January withholdings remitted, check 5042"),
    ExpensePayment("event:claim-marchbank-2026-02", "2026-02-13", "party:elliot-marchbank", D("438.95"),
                   cheque("doc:chq-5043", "2026-02-19"), "Expense claim, customer visits week of 2 February, check 5043"),
    Prepayment("event:insurance-2026-03-prepaid", "2026-02-16", "party:brackenridge-mutual", D("1118.30"),
               cheque("doc:chq-5044", "2026-02-20"), "2026-03", "March shop insurance premium prepaid, check 5044"),
    ExpensePayment("event:lathe-2026-02", "2026-02-18", "party:haldane-machine-tool", D("18900.00"),
                   cheque("doc:chq-2102", "2026-02-23"), "Toolroom lathe, delivered and commissioned, check 2102"),
    ExpensePayment("event:sales-tax-2026-02", "2026-02-18", "party:state-sales-tax", D("984.70"),
                   cheque("doc:chq-5045", "2026-02-24"), "January sales tax return remitted, check 5045"),
    ExpensePayment("event:fuel-2026-02", "2026-02-20", "party:fleetline-fuel", D("342.18"),
                   card("2026-02-20"), "Service van fuel, February statement"),
    CustomerReceipt("event:si-2091-receipt", "2026-02-24", "party:stellan-aero", "doc:si-2091", D("7720.05"),
                    ach_in("2026-02-24"), "Customer payment for SI-2091"),
    ExpensePayment("event:office-2026-02", "2026-02-24", "party:pennant-office", D("96.40"),
                   card("2026-02-24"), "Toner and job travelers"),
    ExpensePayment("event:payroll-whitfield-2026-02", "2026-02-25", "party:dana-whitfield", D("3391.62"),
                   cheque("doc:chq-5046", "2026-02-26"), "February net pay, check 5046"),
    ExpensePayment("event:payroll-reinholt-2026-02", "2026-02-25", "party:tomas-reinholt", D("2958.11"),
                   cheque("doc:chq-5047", "2026-02-26"), "February net pay, check 5047"),
    ExpensePayment("event:payroll-sethuraman-2026-02", "2026-02-25", "party:priyanka-sethuraman", D("3077.45"),
                   cheque("doc:chq-5048", "2026-02-27"), "February net pay, check 5048"),
    BankFee("event:fee-2026-02", "2026-02-27", D("28.00"), "Monthly account service charge"),
    # March 2026: the task period
    ExpensePayment("event:rent-2026-03", "2026-03-02", "party:kilbride-properties", D("4412.50"),
                   cheque("doc:chq-2103", "2026-03-05"), "March shop rent at the reviewed lease rate"),
    ExpensePayment("event:software-2026-03", "2026-03-02", "party:vellum-cam", D("236.25"),
                   card("2026-03-02"), "CAM software subscription, March, second seat added"),
    ExpensePayment("event:coatings-advance-2026-03a", "2026-03-02", "party:oakridge-coatings", D("6500.00"),
                   cheque("doc:chq-5049", "2026-03-04"), "Advance to Oakridge Coatings LLC, check 5049"),
    VendorPayment("event:pi-3315-payment", "2026-03-03", "party:tarrant-alloys", "doc:pi-3315", D("3876.90"),
                  ach_out("2026-03-03"), "Payment of purchase invoice PI-3315"),
    VendorPayment("event:pi-3321-payment", "2026-03-04", "party:penrose-metals", "doc:pi-3321", D("5318.40"),
                  ach_out("2026-03-04"), "Payment of purchase invoice PI-3321"),
    ExpensePayment("event:grinder-2026-03", "2026-03-05", "party:brixworth-equipment", D("12485.00"),
                   cheque("doc:chq-2104", "2026-03-10"), "Surface grinder, paid on delivery, check 2104"),
    Sale("event:si-2102-sale", "2026-03-05", "party:tolhurst-marine", "doc:si-2102", D("10800.00"), D("0.07"), D("4120.00"),
         "Propeller shaft couplings, machined and keyed, SI-2102", "Bar stock consumed on SI-2102"),
    ExpensePayment("event:office-2026-03", "2026-03-05", "party:pennant-office", D("143.75"),
                   card("2026-03-05"), "Copier paper and inspection tags"),
    ExpensePayment("event:telecom-2026-03", "2026-03-06", "party:tessaline-telecom", D("227.90"),
                   card("2026-03-06"), "Shop phones and broadband, March"),
    CustomerReceipt("event:si-2098-receipt", "2026-03-09", "party:corbett-hydraulics", "doc:si-2098", D("9603.25"),
                    ach_in("2026-03-09"), "Customer payment for SI-2098"),
    ExpensePayment("event:payroll-tax-2026-03", "2026-03-09", "party:state-payroll-tax", D("2684.55"),
                   cheque("doc:chq-5050", "2026-03-11"), "February withholdings remitted, check 5050"),
    CustomerReceipt("event:si-2100-receipt", "2026-03-10", "party:tolhurst-marine", "doc:si-2100", D("8137.45"),
                    cheque("doc:chq-tolhurst-4471", "2026-03-12"), "Customer check 4471 for SI-2100"),
    ExpensePayment("event:claim-vosburgh-2026-03", "2026-03-10", "party:hana-vosburgh", D("587.40"),
                   cheque("doc:chq-5051", "2026-03-13"), "Expense claim, service call at Stellan Aero, check 5051"),
    Sale("event:si-2104-sale", "2026-03-11", "party:stellan-aero", "doc:si-2104", D("8420.00"), D("0.07"), D("3165.00"),
         "Machined actuator housings, 40 off, SI-2104", "Bar stock consumed on SI-2104"),
    ExpensePayment("event:repairs-2026-03-lathe", "2026-03-12", "party:wyvern-spindle", D("1384.20"),
                   card("2026-03-12"), "Coolant pump and way cover repair, CNC lathe"),
    Prepayment("event:insurance-2026-04-prepaid", "2026-03-12", "party:brackenridge-mutual", D("1142.60"),
               cheque("doc:chq-5052", "2026-03-16"), "2026-04", "April shop insurance premium prepaid, check 5052"),
    Purchase("event:pi-3338-receipt", "2026-03-16", "party:penrose-metals", "doc:pi-3338", D("4762.15"),
             "Purchase invoice PI-3338 received - 4140 bar and plate"),
    ExpensePayment("event:claim-marchbank-2026-03", "2026-03-16", "party:elliot-marchbank", D("926.85"),
                   cheque("doc:chq-5053", "2026-03-18"), "Expense claim, two-day visit to Tolhurst Marine Drives, check 5053"),
    CustomerReceipt("event:si-2095-receipt", "2026-03-17", "party:stellan-aero", "doc:si-2095", D("6612.60"),
                    ach_in("2026-03-17"), "Customer payment for SI-2095"),
    ExpensePayment("event:coatings-advance-2026-03b", "2026-03-17", "party:oakridge-coatings", D("4850.00"),
                   cheque("doc:chq-5054", "2026-03-19"), "Advance to Oakridge Coatings LLC, check 5054"),
    BankFee("event:fee-2026-03-pospay", "2026-03-18", D("18.50"), "Positive pay service fee"),
    ExpensePayment("event:fuel-2026-03", "2026-03-18", "party:fleetline-fuel", D("418.62"),
                   card("2026-03-18"), "Service van fuel, March statement"),
    ExpensePayment("event:vmc-2026-03", "2026-03-19", "party:haldane-machine-tool", D("23750.00"),
                   cheque("doc:chq-2105", "2026-03-24"), "CNC vertical machining centre, paid on delivery, check 2105"),
    Sale("event:si-2105-sale", "2026-03-20", "party:corbett-hydraulics", "doc:si-2105", D("5275.00"), D("0.07"), D("1980.00"),
         "Manifold blocks, machined and deburred, SI-2105", "Plate consumed on SI-2105"),
    ExpensePayment("event:sales-tax-2026-03", "2026-03-20", "party:state-sales-tax", D("1060.85"),
                   card("2026-03-20"), "February sales tax return, paid on the filing portal"),
    CustomerReceipt("event:si-2104-receipt", "2026-03-24", "party:stellan-aero", "doc:si-2104", D("9009.40"),
                    ach_in("2026-03-24"), "Customer payment settling SI-2104"),
    Purchase("event:pi-3345-receipt", "2026-03-24", "party:tarrant-alloys", "doc:pi-3345", D("3312.70"),
             "Purchase invoice PI-3345 received - 17-4 stainless bar"),
    CustomerReceipt("event:si-2102-partial-receipt", "2026-03-25", "party:tolhurst-marine", "doc:si-2102", D("6000.00"),
                    ach_in("2026-03-25"), "Partial payment against SI-2102, balance to follow"),
    ExpensePayment("event:payroll-whitfield-2026-03", "2026-03-25", "party:dana-whitfield", D("3418.27"),
                   cheque("doc:chq-5055", "2026-03-27"), "March net pay, check 5055"),
    ExpensePayment("event:payroll-reinholt-2026-03", "2026-03-25", "party:tomas-reinholt", D("2976.54"),
                   cheque("doc:chq-5056", "2026-03-30"), "March net pay, check 5056"),
    ExpensePayment("event:payroll-sethuraman-2026-03", "2026-03-25", "party:priyanka-sethuraman", D("3104.88"),
                   cheque("doc:chq-5057", "2026-03-30"), "March net pay, check 5057"),
    ExpensePayment("event:repairs-2026-03-press", "2026-03-26", "party:wyvern-spindle", D("297.60"),
                   card("2026-03-26"), "Hydraulic hose replacement, press brake"),
    # issued in March, cleared by the bank in April: the timing difference
    ExpensePayment("event:bandsaw-2026-03", "2026-03-27", "party:brixworth-equipment", D("7962.50"),
                   cheque("doc:chq-2106", "2026-04-02"), "Horizontal bandsaw, paid on delivery, check 2106"),
    VendorPayment("event:pi-3329-payment", "2026-03-27", "party:tarrant-alloys", "doc:pi-3329", D("2954.30"),
                  cheque("doc:chq-2107", "2026-03-30"), "Payment of purchase invoice PI-3329, check 2107"),
    # received on the last day of March, cleared by the bank in April: the deposit in transit
    CustomerReceipt("event:si-2105-receipt", "2026-03-31", "party:corbett-hydraulics", "doc:si-2105", D("5644.25"),
                    cheque("doc:chq-corbett-10388", "2026-04-03"), "Customer check 10388 for SI-2105"),
    BankFee("event:fee-2026-03", "2026-03-31", D("32.00"), "Monthly account service charge"),
)

WORLD = World(
    id="oakridge-2026-03",
    title="Oakridge Machining - FY2026",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:sawmill-creek-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2026-02-01", D("124500.00")),
    opening=OpeningPosition("2026-03-01", (("Assets:AR", D("24353.30")), ("Assets:Inventory", D("28640.00")),
                                           ("Assets:Prepayments", D("1118.30")),
                                           ("Assets:Due-From-Coatings-LLC", D("9700.00")),
                                           ("Assets:Equipment", D("164300.00")), ("Liabilities:AP", D("-12149.60")),
                                           ("Liabilities:SalesTax-Payable", D("-1060.85")),
                                           ("Liabilities:PayrollTax", D("-2684.55")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

MARCH = Period("2026-03-01", "2026-03-31", "March 2026")

FIXED_ASSETS_001 = TaskSpec(
    id="fixed_assets_001",
    type="bank_reconciliation",
    prompt=("The March statement for the shop checking account has arrived. March's equipment purchases were paid by "
            "check on delivery, and neither the fixed-asset ledger nor the bank ledger agrees with the statement. "
            "Work through the differences under the bookkeeping policy, correct the books, and write the corrected "
            "ledger back to ledger.beancount."),
    period=Period("2026-03-01", "2026-03-31", "March 2026"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_equipment_check", "rec:grinder-2026-03",
                        "the statement row CHECK 2104 BRIXWORTH INDUSTRIAL EQUIPMENT of 12,485.00 on 2026-03-10 "
                        "answers no ledger entry; vendors.csv maps Brixworth Industrial Equipment to Assets:Equipment "
                        "and policy.md's Equipment section capitalises a missing equipment check to that account on "
                        "the bank's date"),
        AlterRecognition("miskeyed_repair_card", "rec:repairs-2026-03-lathe", "transpose_digits", 2,
                         "the statement row DEBIT CARD WYVERN SPINDLE SERVICES of 1,384.20 on 2026-03-12 answers the "
                         "ledger's same-day Wyvern Spindle Services entry of 1,348.20 and no other; vendors.csv maps "
                         "Wyvern Spindle Services to Expenses:Repairs and policy.md's Equipment section re-posts a "
                         "mis-keyed repair payment with the statement's amount on its original date"),
        OmitRecognition("unrecorded_bank_fee", "rec:fee-2026-03",
                        "the statement row is a bank-initiated charge with no counterparty; policy.md records bank "
                        "fees to Expenses:BankFees on the date applied"),
    )),
)

BANK_RECON_OAKRIDGE = TaskSpec(
    id="bank_recon_oakridge",
    type="bank_reconciliation",
    prompt=("The March statement for the shop checking account at Sawmill Creek Bank is in and the month is to be "
            "closed. Tie the ledger out to the statement line by line: the customer deposits, the March payment run "
            "to the stock suppliers and the bank's own charges are the usual sources of difference, and the checks "
            "still in the mail at the cut-off are timing items, not errors. Apply the bookkeeping policy to whatever "
            "differs and write the corrected ledger back to ledger.beancount."),
    period=MARCH,
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_deposit", "rec:si-2098-receipt",
                        "the statement row ACH IN CORBETT HYDRAULICS with reference SI-2098 of 9,603.25 on 2026-03-09 "
                        "answers no ledger entry; customers.csv maps Corbett Hydraulics to Assets:AR and policy.md's "
                        "Customer receipts section applies a referenced deposit against the invoice on the bank's date"),
        AlterRecognition("miskeyed_supplier_payment", "rec:pi-3321-payment", "transpose_digits", 1,
                         "the statement row ACH OUT PENROSE METALS with reference PI-3321 of 5,318.40 on 2026-03-04 "
                         "answers the ledger's same-day Penrose Metals entry of 5,138.40 and no other; vendors.csv maps "
                         "Penrose Metals to Assets:Inventory, so policy.md's Payments to suppliers section lands the "
                         "payment on Liabilities:AP and the Payment runs section re-posts it with the statement's amount "
                         "on its original date"),
        DuplicateRecognition("duplicated_bank_fee", "rec:fee-2026-03",
                             "the statement row MONTHLY ACCOUNT SERVICE CHARGE of 32.00 on 2026-03-31 answers two "
                             "identical ledger entries to Expenses:BankFees; policy.md's Bank service charges section "
                             "makes each charge one entry, so one copy is removed"),
    )),
)

AP_PAYMENT_RUN_OAKRIDGE = TaskSpec(
    id="ap_payment_run_oakridge",
    type="bank_reconciliation",
    prompt=("March's payment run to the stock suppliers went out in two batches: ACH releases against the February "
            "invoices in the first week, and a check to Tarrant Alloys on the 27th. The payables sub-ledger does not "
            "agree with what Sawmill Creek Bank cleared, and the supplier statements are due back next week. Reconcile "
            "the payment run against the March bank statement under the bookkeeping policy, put the payables right, "
            "and write the corrected ledger back to ledger.beancount."),
    period=MARCH,
    plan=MutationPlan((
        OmitRecognition("unrecorded_supplier_payment", "rec:pi-3315-payment",
                        "the statement row ACH OUT TARRANT ALLOYS INC with reference PI-3315 of 3,876.90 on 2026-03-03 "
                        "answers no ledger entry; vendors.csv maps Tarrant Alloys Inc to Assets:Inventory and "
                        "policy.md's Payment runs section adds a missing supplier payment to Liabilities:AP on the "
                        "bank's date"),
        AlterRecognition("miskeyed_supplier_check", "rec:pi-3329-payment", "transpose_digits", 1,
                         "the statement row CHECK 2107 TARRANT ALLOYS INC of 2,954.30 on 2026-03-30 answers the "
                         "ledger's check 2107 entry of 2,594.30 dated 2026-03-27 and no other; policy.md's Payment runs "
                         "section re-posts a mis-keyed supplier payment with the statement's amount on its original date"),
        DuplicateRecognition("duplicated_supplier_payment", "rec:pi-3321-payment",
                             "the statement row ACH OUT PENROSE METALS with reference PI-3321 of 5,318.40 on 2026-03-04 "
                             "answers two identical ledger entries; policy.md's Payment runs section makes each payment "
                             "one entry per invoice, so one copy is removed"),
    )),
)

AR_COLLECTIONS_OAKRIDGE = TaskSpec(
    id="ar_collections_oakridge",
    type="bank_reconciliation",
    prompt=("Collections for March need to be agreed before the aged receivables go to the owner. Stellan Aero paid "
            "twice by ACH, Tolhurst Marine Drives sent a check for SI-2100 and then a part payment on SI-2102, and "
            "Corbett Hydraulics' check for SI-2105 arrived on the 31st, too late for the bank to clear it in March. "
            "Reconcile the receipts against the March statement from Sawmill Creek Bank under the bookkeeping policy "
            "so that Assets:AR carries exactly what is still owed, and write the corrected ledger back to "
            "ledger.beancount."),
    period=MARCH,
    plan=MutationPlan((
        OmitRecognition("unrecorded_ach_receipt", "rec:si-2095-receipt",
                        "the statement row ACH IN STELLAN AERO COMPONENTS with reference SI-2095 of 6,612.60 on "
                        "2026-03-17 answers no ledger entry; customers.csv maps Stellan Aero Components to Assets:AR "
                        "and policy.md's Collections section adds a missing deposit on the bank's date"),
        AlterRecognition("miskeyed_check_receipt", "rec:si-2100-receipt", "transpose_digits", 2,
                         "the statement row CHECK 4471 TOLHURST MARINE DRIVES of 8,137.45 on 2026-03-12 answers the "
                         "ledger's Tolhurst Marine Drives entry of 8,173.45 dated 2026-03-10 and no other; customers.csv "
                         "maps Tolhurst Marine Drives to Assets:AR and policy.md's Collections section re-posts a "
                         "mis-keyed receipt with the statement's amount on its original date"),
        DuplicateRecognition("duplicated_ach_receipt", "rec:si-2104-receipt",
                             "the statement row ACH IN STELLAN AERO COMPONENTS with reference SI-2104 of 9,009.40 on "
                             "2026-03-24 answers two identical ledger entries; policy.md's Collections section removes "
                             "one copy of a receipt posted twice against a single deposit"),
    )),
)

BANK_FEED_CATEGORISATION_OAKRIDGE = TaskSpec(
    id="bank_feed_categorisation_oakridge",
    type="bank_reconciliation",
    prompt=("The debit card rows on the March statement from Sawmill Creek Bank were keyed into the books from the "
            "bank feed by the shop manager, and the expense accounts do not agree with the statement. Every card "
            "vendor is in the vendor master with the account its spend belongs to. Categorise and agree the March "
            "card spend under the bookkeeping policy, fix what the feed entry got wrong, and write the corrected "
            "ledger back to ledger.beancount."),
    period=MARCH,
    plan=MutationPlan((
        OmitRecognition("unrecorded_telecom_card", "rec:telecom-2026-03",
                        "the statement row DEBIT CARD TESSALINE TELECOM of 227.90 on 2026-03-06 answers no ledger "
                        "entry; vendors.csv maps Tessaline Telecom to Expenses:Telecom and policy.md's Card spend "
                        "section adds a missing card row to that account on the bank's date"),
        AlterRecognition("miskeyed_office_card", "rec:office-2026-03", "transpose_digits", 1,
                         "the statement row DEBIT CARD PENNANT OFFICE SUPPLY of 143.75 on 2026-03-05 answers the "
                         "ledger's same-day Pennant Office Supply entry of 134.75 and no other; vendors.csv maps "
                         "Pennant Office Supply to Expenses:Office and policy.md's Card spend section re-posts a "
                         "mis-keyed card row with the statement's amount on its original date"),
        DuplicateRecognition("duplicated_software_card", "rec:software-2026-03",
                             "the statement row DEBIT CARD VELLUM CAM SOFTWARE of 236.25 on 2026-03-02 answers two "
                             "identical ledger entries to Expenses:Software; policy.md's Card spend section removes one "
                             "copy of a card row entered from the feed twice"),
    )),
)

EXPENSE_REPORTS_OAKRIDGE = TaskSpec(
    id="expense_reports_oakridge",
    type="bank_reconciliation",
    prompt=("Two expense claims were approved and reimbursed by check in March, Hana Vosburgh's for the service "
            "call at Stellan Aero and Elliot Marchbank's for the two days at Tolhurst Marine Drives, and the fleet "
            "card drew the van's March fuel. The travel and vehicle accounts do not agree with the March statement "
            "from Sawmill Creek Bank. Agree the claims and the fuel draw to the statement under the bookkeeping policy, "
            "correct the books, and write the corrected ledger back to ledger.beancount."),
    period=MARCH,
    plan=MutationPlan((
        OmitRecognition("unrecorded_claim_check", "rec:claim-vosburgh-2026-03",
                        "the statement row CHECK 5051 HANA VOSBURGH of 587.40 on 2026-03-13 answers no ledger entry; "
                        "vendors.csv carries Hana Vosburgh on expense claim terms with Expenses:Travel as the default "
                        "account and policy.md's Employee expense claims section adds a missing reimbursement check to "
                        "that account on the bank's date"),
        DuplicateRecognition("duplicated_claim_check", "rec:claim-marchbank-2026-03",
                             "the statement row CHECK 5053 ELLIOT MARCHBANK of 926.85 on 2026-03-18 answers two "
                             "identical ledger entries dated 2026-03-16; policy.md's Employee expense claims section "
                             "removes one copy of a claim posted twice against a single check"),
        AlterRecognition("miskeyed_fuel_card", "rec:fuel-2026-03", "transpose_digits", 1,
                         "the statement row DEBIT CARD FLEETLINE FUEL CARD of 418.62 on 2026-03-18 answers the ledger's "
                         "same-day Fleetline Fuel Card entry of 481.62 and no other; vendors.csv maps Fleetline Fuel "
                         "Card to Expenses:Vehicle and policy.md's Employee expense claims section re-posts a mis-keyed "
                         "fuel draw with the statement's amount on its original date"),
    )),
)

PAYROLL_OAKRIDGE = TaskSpec(
    id="payroll_oakridge",
    type="bank_reconciliation",
    prompt=("March payroll was paid by check on the 25th, three net pay checks on the payroll stock, and February's "
            "withholdings went to the State Payroll Tax Bureau on check 5050 earlier in the month. The payroll bureau's "
            "register does not agree with Expenses:Salaries and Liabilities:PayrollTax as the books stand. Agree the "
            "payroll checks and the remittance to the March statement from Sawmill Creek Bank under the bookkeeping "
            "policy, correct the books, and write the corrected ledger back to ledger.beancount."),
    period=MARCH,
    plan=MutationPlan((
        OmitRecognition("unrecorded_net_pay_check", "rec:payroll-whitfield-2026-03",
                        "the statement row CHECK 5055 DANA WHITFIELD of 3,418.27 on 2026-03-27 answers no ledger entry; "
                        "vendors.csv carries Dana Whitfield on monthly payroll terms with Expenses:Salaries as the "
                        "default account and policy.md's Payroll section adds a missing net pay check to that account "
                        "on the bank's date"),
        AlterRecognition("miskeyed_net_pay_check", "rec:payroll-reinholt-2026-03", "transpose_digits", 2,
                         "the statement row CHECK 5056 TOMAS REINHOLT of 2,976.54 on 2026-03-30 answers the ledger's "
                         "check 5056 entry of 2,967.54 dated 2026-03-25 and no other; policy.md's Payroll section "
                         "re-posts a mis-keyed net pay check with the statement's amount on its original date"),
        OmitRecognition("unrecorded_payroll_tax_remittance", "rec:payroll-tax-2026-03",
                        "the statement row CHECK 5050 STATE PAYROLL TAX BUREAU of 2,684.55 on 2026-03-11 answers no "
                        "ledger entry; vendors.csv carries the State Payroll Tax Bureau on monthly remittance terms with "
                        "Liabilities:PayrollTax as the default account and policy.md's Payroll section settles that "
                        "liability with the remittance check on the bank's date"),
    )),
)

SALES_TAX_REMITTANCE_OAKRIDGE = TaskSpec(
    id="sales_tax_remittance_oakridge",
    type="bank_reconciliation",
    prompt=("The February sales tax return was filed on the State Sales Tax Commission's portal and paid by debit "
            "card on 20 March, and the March return is due next month, so Liabilities:SalesTax-Payable has to be "
            "right at the close. The March statement from Sawmill Creek Bank does not agree with the tax account or "
            "with the customer receipts that carried the tax in. Reconcile the remittance and the receipts under the "
            "bookkeeping policy and write the corrected ledger back to ledger.beancount."),
    period=MARCH,
    plan=MutationPlan((
        OmitRecognition("unrecorded_tax_remittance", "rec:sales-tax-2026-03",
                        "the statement row DEBIT CARD STATE SALES TAX COMMISSION of 1,060.85 on 2026-03-20 answers no "
                        "ledger entry; vendors.csv carries the State Sales Tax Commission on monthly filing terms with "
                        "Liabilities:SalesTax-Payable as the default account and policy.md's Sales tax remittance "
                        "section settles that liability on the bank's date"),
        AlterRecognition("miskeyed_customer_receipt", "rec:si-2098-receipt", "transpose_digits", 1,
                         "the statement row ACH IN CORBETT HYDRAULICS with reference SI-2098 of 9,603.25 on 2026-03-09 "
                         "answers the ledger's same-day Corbett Hydraulics entry of 9,063.25 and no other; customers.csv "
                         "maps Corbett Hydraulics to Assets:AR and policy.md's Collections section re-posts a mis-keyed "
                         "receipt with the statement's amount on its original date"),
        DuplicateRecognition("duplicated_service_fee", "rec:fee-2026-03-pospay",
                             "the statement row POSITIVE PAY SERVICE FEE of 18.50 on 2026-03-18 answers two identical "
                             "ledger entries to Expenses:BankFees; policy.md's Bank service charges section makes each "
                             "charge one entry, so one copy is removed"),
    )),
)

INTERCOMPANY_TRANSFERS_OAKRIDGE = TaskSpec(
    id="intercompany_transfers_oakridge",
    type="bank_reconciliation",
    prompt=("Oakridge Coatings LLC was funded twice in March, on checks 5049 and 5054, and the coatings shop's "
            "bookkeeper has sent over their intercompany balance for agreement. Assets:Due-From-Coatings-LLC does "
            "not agree with it, and the March statement from Sawmill Creek Bank does not agree with the customer "
            "receipts either. Reconcile the advances and the receipts under the bookkeeping policy so that the "
            "intercompany balance carries each advance exactly once, and write the corrected ledger back to "
            "ledger.beancount."),
    period=MARCH,
    plan=MutationPlan((
        OmitRecognition("unrecorded_intercompany_advance", "rec:coatings-advance-2026-03b",
                        "the statement row CHECK 5054 OAKRIDGE COATINGS LLC of 4,850.00 on 2026-03-19 answers no ledger "
                        "entry; vendors.csv carries Oakridge Coatings LLC on intercompany terms with "
                        "Assets:Due-From-Coatings-LLC as the default account and policy.md's Intercompany balances "
                        "section adds a missing advance to that account on the bank's date"),
        DuplicateRecognition("duplicated_intercompany_advance", "rec:coatings-advance-2026-03a",
                             "the statement row CHECK 5049 OAKRIDGE COATINGS LLC of 6,500.00 on 2026-03-04 answers two "
                             "identical ledger entries dated 2026-03-02; policy.md's Intercompany balances section "
                             "removes one copy of an advance posted twice"),
        AlterRecognition("miskeyed_customer_receipt", "rec:si-2098-receipt", "transpose_digits", 3,
                         "the statement row ACH IN CORBETT HYDRAULICS with reference SI-2098 of 9,603.25 on 2026-03-09 "
                         "answers the ledger's same-day Corbett Hydraulics entry of 9,602.35 and no other; customers.csv "
                         "maps Corbett Hydraulics to Assets:AR and policy.md's Collections section re-posts a mis-keyed "
                         "receipt with the statement's amount on its original date"),
    )),
)

MONTH_END_CLOSE_OAKRIDGE = TaskSpec(
    id="month_end_close_oakridge",
    type="bank_reconciliation",
    prompt=("March is being closed. Work the close checklist against the March statement from Sawmill Creek Bank: "
            "the April insurance premium was paid ahead on check 5052 and belongs in prepayments, the bank charged "
            "two separate fees this month, and the customer receipts have to be applied once each. Bring the ledger "
            "into agreement with the statement under the bookkeeping policy, leave the timing items as they are, and "
            "write the corrected ledger back to ledger.beancount."),
    period=MARCH,
    plan=MutationPlan((
        OmitRecognition("unrecorded_prepaid_insurance", "rec:insurance-2026-04-prepaid",
                        "the statement row CHECK 5052 BRACKENRIDGE MUTUAL INSURANCE of 1,142.60 on 2026-03-16 answers "
                        "no ledger entry; vendors.csv maps Brackenridge Mutual Insurance to Assets:Prepayments and "
                        "policy.md's Prepayments section books a missing premium check to that account on the bank's "
                        "date"),
        AlterRecognition("miskeyed_bank_fee", "rec:fee-2026-03", "transpose_digits", 0,
                         "the statement row MONTHLY ACCOUNT SERVICE CHARGE of 32.00 on 2026-03-31 answers the ledger's "
                         "same-day bank fee entry of 23.00 and no other; policy.md's Month-end close checklist re-posts "
                         "a mis-keyed bank charge with the statement's amount on its original date"),
        DuplicateRecognition("duplicated_partial_receipt", "rec:si-2102-partial-receipt",
                             "the statement row ACH IN TOLHURST MARINE DRIVES with reference SI-2102 of 6,000.00 on "
                             "2026-03-25 answers two identical ledger entries; policy.md's Month-end close checklist "
                             "removes one copy of a receipt posted twice"),
    )),
)

TASKS = {
    FIXED_ASSETS_001.id: FIXED_ASSETS_001,
    BANK_RECON_OAKRIDGE.id: BANK_RECON_OAKRIDGE,
    AP_PAYMENT_RUN_OAKRIDGE.id: AP_PAYMENT_RUN_OAKRIDGE,
    AR_COLLECTIONS_OAKRIDGE.id: AR_COLLECTIONS_OAKRIDGE,
    BANK_FEED_CATEGORISATION_OAKRIDGE.id: BANK_FEED_CATEGORISATION_OAKRIDGE,
    EXPENSE_REPORTS_OAKRIDGE.id: EXPENSE_REPORTS_OAKRIDGE,
    PAYROLL_OAKRIDGE.id: PAYROLL_OAKRIDGE,
    SALES_TAX_REMITTANCE_OAKRIDGE.id: SALES_TAX_REMITTANCE_OAKRIDGE,
    INTERCOMPANY_TRANSFERS_OAKRIDGE.id: INTERCOMPANY_TRANSFERS_OAKRIDGE,
    MONTH_END_CLOSE_OAKRIDGE.id: MONTH_END_CLOSE_OAKRIDGE,
}
