"""Hawthorn Bakery, December 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The month is one small wholesale bakery's December, authored once and read
ten ways. Five hourly bakery staff are carried in the vendor master as
payees whose purchases book to `Expenses:Salaries`; each is paid net pay by
check on the last working day of the month, and the withholdings the payroll
journal accrued for the previous month are remitted to the revenue service by
check around the 15th. Around that payroll sit the rest of a bakery's month:
flour, dairy and packaging suppliers invoiced on terms and settled in a
payment run (ACH quoting the invoice, one check); three wholesale customers
collected by ACH and by their own checks, one of them part-paying a December
invoice and posting its last check too late for the bank to credit it in
December; card spend to the ordering platform, the telecom, the office
supplier, a travel booking, the van's fuel card and the oven repairer; two
employee expense claims reimbursed by check; the November sales tax return
remitted by check; a spiral mixer and a proofing cabinet capitalised on the
check that paid for them; two cash advances to the sister cafe; the January
insurance premium prepaid; and two bank charges on different dates.

Two check books draw on the one account: the 20xx book for net pay, rent and
payroll withholdings, the 31xx book for everything else. Net pay varies with
hours, so no two checks in either month carry the same figure, and no two
statement rows in either month carry the same absolute amount.

Every task sees the same statement and the same golden facts; only the
prompt and the planted items differ. The check to the delivery driver
issued on 30 December is not a mutation in any task: the bank cleared it on
5 January, and the December statement's projection classifies it
NOT_YET_SETTLED on its own. The hotel's check of 29 December is likewise a
deposit in transit the bank credited on 2 January.
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

POLICY_TEXT = """# Hawthorn Bakery - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, check printing,
returned item fees) are recorded to `Expenses:BankFees` on the date the bank
applies them. A month may carry more than one such charge; each is its own
entry, in the bank's own wording, on the bank's own date. A bank charge posted
with a mis-keyed amount is re-posted with the amount the statement shows, on
its original date; one posted twice has the second copy removed.

## Check books
Hawthorn draws on two books of pre-numbered checks against the one operating
account at Sable River Bank. Net pay, rent and payroll withholdings are written
from the 20xx book; supplier settlements, expense claims, insurance premiums,
equipment, sales tax and advances to the cafe are written from the 31xx book.
The bank prints the check number and the payee on every check row, whichever
book the check came from, and a check is identified by that number.

## Customer receipts
Cash received from a wholesale customer reduces `Assets:AR`. Where the deposit
reference identifies a sales invoice, it is applied against that invoice.

## Collections
Wholesale customers pay by ACH transfer quoting the invoice number, or by their
own check, which the bank prints with the customer's check number and name. A
receipt is recorded on the day the money is received, as a debit to the
checking account and a credit to `Assets:AR` for the amount received, whether
or not it settles the invoice in full: a part payment leaves the balance of the
invoice open in `Assets:AR` and is never grossed up to the invoice. A customer
check banked before the cut-off that the bank has not yet credited is a deposit
in transit and is left as it is. A receipt on the statement that the books
lack is added for the customer and the amount the statement shows, on the
bank's date; a receipt keyed with the wrong amount is re-posted with the
statement's amount on its original date; a receipt posted twice has the second
copy removed and the other left as it was. The sales invoice itself is never
altered to fit a receipt.

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
period it covers, which the prepayments section below governs. Where a
supplier's `default_account` is a liability account, the supplier is a body to
which Hawthorn remits amounts already accrued in that account, and the payment
settles the liability; the payroll and sales tax remittance sections below set
out the two such cases. Three suppliers stand outside the inventory rule and
each has its own section below: the equipment supplier, whose default account
is `Assets:Equipment`; the insurer, whose default account is
`Assets:Prepayments`; and the sister cafe, whose default account is
`Assets:Due-From-Hawthorn-Cafe`. In every case the vendor master's default
account and the section that names it agree on where the payment lands.

## Payment runs
The ingredient and packaging suppliers - the flour mill, the dairy cooperative
and the packaging house - carry `Assets:Inventory` as their default account.
Their invoices are booked to `Assets:Inventory` and `Liabilities:AP` on the
day the goods arrive, for the invoice number and gross shown, and are settled
on terms in the payment run by ACH quoting the invoice number, or occasionally
by check from the 31xx book. Each settlement is its own entry on the day it is
released: a debit to `Liabilities:AP` and a credit to the checking account for
the amount paid, with the supplier as payee and the invoice number in the
narration. A run payment on the statement that the books lack is added against
`Liabilities:AP` for the supplier and the amount the statement shows, on the
bank's date; one keyed with the wrong amount is re-posted with the statement's
amount on its original date; one posted twice has the second copy removed. The
purchase invoice itself is never re-posted or altered to fit a payment, and an
invoice not yet due at the cut-off stays open in `Liabilities:AP`.

## Card spend
Subscriptions, telephone and internet, office consumables, travel bookings,
van fuel and equipment servicing are paid on the bakery's debit card. Each such
vendor is carried in the vendor master on "card on file" terms with an expense
account as its default account, and the bank prints the vendor's name on the
card row. A card payment is the expense: it is recorded on the day of the
charge as a debit to the vendor's `default_account` and a credit to the
checking account, one entry per card row. The bank feed is the source for card
spend, so a card row that the books lack is added for the vendor and the
amount the statement shows, against the vendor's default account, on the
bank's date; a card entry keyed with the wrong amount is re-posted with the
statement's amount on its original date. No payable is raised for card spend.

## Employee expense claims
Staff who travel on bakery business - customer visits, trade fairs, the trip
to the mill - claim mileage, fares, meals and lodging on an expense claim,
which is approved and reimbursed by check from the 31xx book. A claimant is
carried in the vendor master on "expense claim" terms with `Expenses:Travel`
as the default account, separately from the payroll master. A reimbursement
check is the expense: one entry per check, dated the day the check is written,
with the claimant named as payee exactly as the vendor master lists them, a
debit to `Expenses:Travel` and a credit to the checking account for the amount
of the claim. No payable is raised for a claim ahead of the check. A
reimbursement check on the statement that the books lack is added for the
claimant and the amount shown, on the bank's date; one posted twice has the
second copy removed. Fuel for the delivery van goes on the fuel card and is
recorded under the card spend section, to `Expenses:Vehicle`.

## Payroll
Hawthorn's bakery staff are paid monthly, on the last working day of the
month, by check drawn on the operating account for each employee's net pay.
Each employee is carried in the vendor master as a payee on "monthly payroll"
terms with `Expenses:Salaries` as the default account. A net pay check is
recorded as one entry per employee, dated the day the check was written, with
the employee named as payee exactly as the vendor master lists them: a debit
to `Expenses:Salaries` and a credit to the checking account for the net
amount. No payable is raised for net pay ahead of the check.

Employee withholdings and the employer's payroll taxes are accrued to
`Liabilities:PayrollTax` by the monthly payroll journal that the payroll
bureau supplies after each close; that journal is outside the bank
reconciliation. The amount accrued for a month is remitted to the Commonwealth
Revenue Service by check on or before the 15th of the following month. The
revenue service is carried in the vendor master on "monthly remittance" terms
with `Liabilities:PayrollTax` as the default account, and the remittance
check settles that liability: a debit to `Liabilities:PayrollTax` and a
credit to the checking account on the day the check is written.

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
amount is a match and is not touched. A payroll check the books carry that the
bank has not cleared at the cut-off is an outstanding check and is left as it
is.

## Sales tax remittance
The tax collected on a month's sales sits in `Liabilities:SalesTax-Payable`
until it is remitted with the monthly return, which is filed and paid by the
20th of the following month by check from the 31xx book to the Commonwealth
Sales Tax Bureau. The bureau is carried in the vendor master on "monthly
filing" terms with `Liabilities:SalesTax-Payable` as the default account, and
the remittance check settles the liability: a debit to
`Liabilities:SalesTax-Payable` and a credit to the checking account on the day
the check is written, for the amount of the return. A remittance check on the
statement that the books lack is added against `Liabilities:SalesTax-Payable`
on the bank's date for the amount shown. The tax on the month's own sales is
left where the sales entries put it; it is the next return's business.

## Equipment
Ovens, mixers, proofing cabinets and other bakery equipment are bought from
the equipment supplier and paid by check from the 31xx book on delivery. The
equipment supplier is carried in the vendor master with `Assets:Equipment` as
the default account, and a payment to it is capitalised on the day the check
is written: a debit to `Assets:Equipment` and a credit to the checking account
for the amount paid. No payable is raised ahead of the check, and depreciation
is a year-end journal outside this reconciliation. Servicing, parts and repairs
to equipment are not capitalised: the repairs contractor is carried with
`Expenses:Repairs` as the default account and is paid on the debit card, so
each repair charge is recorded to `Expenses:Repairs` under the card spend
section. Whether a payment is capitalised or expensed is decided by the
vendor's default account, never by the size of the payment. An equipment check
on the statement that the books lack is added against `Assets:Equipment` on
the bank's date for the amount shown.

## Intercompany balances
Hawthorn Cafe LLC is a sister company under common ownership. Hawthorn Bakery
advances cash to the cafe by check from the 31xx book as its fit-out and wages
require, and the advances are repayable on demand. The cafe is carried in the
vendor master on "intercompany" terms with `Assets:Due-From-Hawthorn-Cafe` as
the default account, and an advance is recorded on the day the check is
written as a debit to `Assets:Due-From-Hawthorn-Cafe` and a credit to the
checking account for the amount advanced. An advance is never an expense and
never a payable. An advance check on the statement that the books lack is
added against `Assets:Due-From-Hawthorn-Cafe` on the bank's date for the
amount shown; one posted twice has the second copy removed. The two companies
agree the balance at each close.

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
customer, supplier, employee or payroll movement the ledger date is never
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

The bakery's contents and liability cover is invoiced by Stillwater Mutual
Insurance a month in advance, and the premium is paid by check from the 31xx
book in the month before the cover month. A premium paid in December for
January cover is booked to `Assets:Prepayments` on the date the check is
written and released to expense in January by the close journal, which is
outside this reconciliation. The insurer carries `Assets:Prepayments` as its
default account in the vendor master for exactly this reason: every payment to
the insurer is a payment in advance, and the vendor master and this section
agree on where it lands. No payable is raised for a premium. A premium check on
the statement that the books lack is added against `Assets:Prepayments` on the
bank's date for the amount shown.

## Rent
The bakery premises are leased from Ashgrove Commercial Properties and the
rent is paid by check on the first working day of the month it covers. The
landlord is a supplier whose purchases are booked to an expense account, so
the check is the expense and is recorded to `Expenses:Rent` on the day it is
written. Common-area heating recharged under the lease is billed with the rent
and is booked with it.

## Sales tax
Hawthorn collects sales tax from its wholesale customers on sales of baked
goods and owes it to the state. Flour, sugar, dairy and other ingredients
bought for production are exempt under the resale certificate, so no tax is
recoverable on the purchase side.

## Suspense accounts
Hawthorn does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
"""

OPENED = "2025-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Sable River Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Trade receivables from wholesale customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Flour, sugar, dairy, packaging and other ingredients on hand", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Assets:Equipment", K.ASSET, "Ovens, mixers and other bakery equipment at cost", OPENED, 1400),
    Account("Assets:Due-From-Hawthorn-Cafe", K.ASSET, "Cash advanced to Hawthorn Cafe LLC, the sister company, repayable on demand", OPENED, 1500),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Liabilities:PayrollTax", K.LIABILITY, "Employee withholdings and employer payroll taxes accrued and not yet remitted", OPENED, 2200),
    Account("Income:Sales", K.INCOME, "Revenue from wholesale sales of baked goods", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of ingredients consumed in goods sold", OPENED, 5000),
    Account("Expenses:Salaries", K.EXPENSE, "Net pay to bakery staff", OPENED, 5100),
    Account("Expenses:Rent", K.EXPENSE, "Bakery premises rent and lease recharges for the period", OPENED, 5200),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Expenses:Software", K.EXPENSE, "Ordering platform and other subscriptions", OPENED, 5400),
    Account("Expenses:Telecom", K.EXPENSE, "Telephone and internet service", OPENED, 5410),
    Account("Expenses:Office", K.EXPENSE, "Office supplies and consumables", OPENED, 5420),
    Account("Expenses:Travel", K.EXPENSE, "Staff travel, mileage, fares and meals on bakery business", OPENED, 5430),
    Account("Expenses:Vehicle", K.EXPENSE, "Fuel and running costs of the delivery van", OPENED, 5440),
    Account("Expenses:Repairs", K.EXPENSE, "Servicing, parts and repairs to bakery equipment", OPENED, 5450),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:fennimore-street", "Fennimore Street Grocers", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:tidewell", "Tidewell Coffee Roasters", R.CUSTOMER, 2, "net 15", "Assets:AR"),
    Party("party:bramblewood", "Bramblewood Flour Mills", R.VENDOR, 3, "net 30", "Assets:Inventory"),
    Party("party:ashgrove", "Ashgrove Commercial Properties", R.VENDOR, 4, "due on receipt", "Expenses:Rent"),
    Party("party:marisol-fentress", "Marisol Fentress", R.VENDOR, 5, "monthly payroll", "Expenses:Salaries"),
    Party("party:declan-oyelaran", "Declan Oyelaran", R.VENDOR, 6, "monthly payroll", "Expenses:Salaries"),
    Party("party:teodora-vukovic", "Teodora Vukovic", R.VENDOR, 7, "monthly payroll", "Expenses:Salaries"),
    Party("party:hamish-abernathy", "Hamish Abernathy", R.VENDOR, 8, "monthly payroll", "Expenses:Salaries"),
    Party("party:priya-sundaram", "Priya Sundaram", R.VENDOR, 9, "monthly payroll", "Expenses:Salaries"),
    Party("party:commonwealth-revenue", "Commonwealth Revenue Service", R.VENDOR, 10, "monthly remittance",
          "Liabilities:PayrollTax"),
    Party("party:sable-river-bank", "Sable River Bank", R.BANK, 11),
    Party("party:wintergreen-hotel", "Wintergreen Hotel Kitchens", R.CUSTOMER, 12, "net 30", "Assets:AR"),
    Party("party:fallowfield-dairy", "Fallowfield Dairy Cooperative", R.VENDOR, 13, "net 15", "Assets:Inventory"),
    Party("party:tessaly-packaging", "Tessaly Box and Packaging", R.VENDOR, 14, "net 30", "Assets:Inventory"),
    Party("party:kettleworth", "Kettleworth Bakery Equipment", R.VENDOR, 15, "due on receipt", "Assets:Equipment"),
    Party("party:millstone-mechanical", "Millstone Mechanical Services", R.VENDOR, 16, "card on file", "Expenses:Repairs"),
    Party("party:stillwater-mutual", "Stillwater Mutual Insurance", R.VENDOR, 17, "premium in advance",
          "Assets:Prepayments"),
    Party("party:hawthorn-cafe", "Hawthorn Cafe LLC", R.VENDOR, 18, "intercompany", "Assets:Due-From-Hawthorn-Cafe"),
    Party("party:sales-tax-bureau", "Commonwealth Sales Tax Bureau", R.VENDOR, 19, "monthly filing",
          "Liabilities:SalesTax-Payable"),
    Party("party:rosalind-achterberg", "Rosalind Achterberg", R.VENDOR, 20, "expense claim", "Expenses:Travel"),
    Party("party:callum-petrakis", "Callum Petrakis", R.VENDOR, 21, "expense claim", "Expenses:Travel"),
    Party("party:fleetfuel", "Fleetfuel Card Services", R.VENDOR, 22, "card on file", "Expenses:Vehicle"),
    Party("party:loafline", "Loafline Software", R.VENDOR, 23, "card on file", "Expenses:Software"),
    Party("party:skylark-telecom", "Skylark Telecom", R.VENDOR, 24, "card on file", "Expenses:Telecom"),
    Party("party:paperbark", "Paperbark Office Supply", R.VENDOR, 25, "card on file", "Expenses:Office"),
    Party("party:tollgate-travel", "Tollgate Travel", R.VENDOR, 26, "card on file", "Expenses:Travel"),
)

DOCUMENTS = (
    # sales invoices
    Document("doc:si-4102", DK.SALES_INVOICE, "SI-4102", "party:fennimore-street", "2025-10-30", D("8742.60")),
    Document("doc:si-4109", DK.SALES_INVOICE, "SI-4109", "party:wintergreen-hotel", "2025-10-24", D("2874.35")),
    Document("doc:si-4118", DK.SALES_INVOICE, "SI-4118", "party:tidewell", "2025-11-03", D("4193.15")),
    Document("doc:si-4123", DK.SALES_INVOICE, "SI-4123", "party:wintergreen-hotel", "2025-11-10", D("3218.60")),
    Document("doc:si-4127", DK.SALES_INVOICE, "SI-4127", "party:tidewell", "2025-11-17", D("4367.40")),
    Document("doc:si-4131", DK.SALES_INVOICE, "SI-4131", "party:fennimore-street", "2025-11-28", D("9126.90")),
    Document("doc:si-4139", DK.SALES_INVOICE, "SI-4139", "party:tidewell", "2025-12-01", D("4330.10")),
    Document("doc:si-4143", DK.SALES_INVOICE, "SI-4143", "party:wintergreen-hotel", "2025-12-08", D("3455.60")),
    Document("doc:si-4146", DK.SALES_INVOICE, "SI-4146", "party:tidewell", "2025-12-15", D("4176.40")),
    Document("doc:si-4152", DK.SALES_INVOICE, "SI-4152", "party:fennimore-street", "2025-12-30", D("9831.50")),
    # purchase invoices
    Document("doc:pi-7712", DK.PURCHASE_INVOICE, "PI-7712", "party:bramblewood", "2025-10-10", D("4218.75")),
    Document("doc:pi-7728", DK.PURCHASE_INVOICE, "PI-7728", "party:bramblewood", "2025-10-24", D("3671.30")),
    Document("doc:pi-7745", DK.PURCHASE_INVOICE, "PI-7745", "party:bramblewood", "2025-11-06", D("3864.20")),
    Document("doc:pi-7756", DK.PURCHASE_INVOICE, "PI-7756", "party:fallowfield-dairy", "2025-11-11", D("1864.30")),
    Document("doc:pi-7769", DK.PURCHASE_INVOICE, "PI-7769", "party:tessaly-packaging", "2025-11-14", D("1148.25")),
    Document("doc:pi-7781", DK.PURCHASE_INVOICE, "PI-7781", "party:bramblewood", "2025-11-20", D("4507.90")),
    Document("doc:pi-7793", DK.PURCHASE_INVOICE, "PI-7793", "party:fallowfield-dairy", "2025-11-25", D("1782.60")),
    Document("doc:pi-7809", DK.PURCHASE_INVOICE, "PI-7809", "party:bramblewood", "2025-12-04", D("4932.15")),
    Document("doc:pi-7816", DK.PURCHASE_INVOICE, "PI-7816", "party:fallowfield-dairy", "2025-12-09", D("1937.45")),
    Document("doc:pi-7824", DK.PURCHASE_INVOICE, "PI-7824", "party:tessaly-packaging", "2025-12-12", D("1296.80")),
    Document("doc:pi-7838", DK.PURCHASE_INVOICE, "PI-7838", "party:bramblewood", "2025-12-18", D("3395.60")),
    Document("doc:pi-7851", DK.PURCHASE_INVOICE, "PI-7851", "party:fallowfield-dairy", "2025-12-23", D("2041.15")),
    # the 20xx check book: net pay, rent, payroll withholdings
    Document("doc:chq-2071", DK.CHEQUE, "2071", "party:ashgrove", "2025-11-03"),
    Document("doc:chq-2072", DK.CHEQUE, "2072", "party:commonwealth-revenue", "2025-11-14"),
    Document("doc:chq-2073", DK.CHEQUE, "2073", "party:marisol-fentress", "2025-11-26"),
    Document("doc:chq-2074", DK.CHEQUE, "2074", "party:declan-oyelaran", "2025-11-26"),
    Document("doc:chq-2075", DK.CHEQUE, "2075", "party:teodora-vukovic", "2025-11-26"),
    Document("doc:chq-2076", DK.CHEQUE, "2076", "party:hamish-abernathy", "2025-11-26"),
    Document("doc:chq-2077", DK.CHEQUE, "2077", "party:priya-sundaram", "2025-11-26"),
    Document("doc:chq-2078", DK.CHEQUE, "2078", "party:ashgrove", "2025-12-01"),
    Document("doc:chq-2079", DK.CHEQUE, "2079", "party:commonwealth-revenue", "2025-12-15"),
    Document("doc:chq-2080", DK.CHEQUE, "2080", "party:marisol-fentress", "2025-12-30"),
    Document("doc:chq-2081", DK.CHEQUE, "2081", "party:declan-oyelaran", "2025-12-30"),
    Document("doc:chq-2082", DK.CHEQUE, "2082", "party:teodora-vukovic", "2025-12-30"),
    Document("doc:chq-2083", DK.CHEQUE, "2083", "party:hamish-abernathy", "2025-12-30"),
    Document("doc:chq-2084", DK.CHEQUE, "2084", "party:priya-sundaram", "2025-12-30"),
    # the 31xx check book: suppliers, claims, insurance, equipment, sales tax, the cafe
    Document("doc:chq-3138", DK.CHEQUE, "3138", "party:rosalind-achterberg", "2025-11-07"),
    Document("doc:chq-3139", DK.CHEQUE, "3139", "party:stillwater-mutual", "2025-11-13"),
    Document("doc:chq-3140", DK.CHEQUE, "3140", "party:sales-tax-bureau", "2025-11-19"),
    Document("doc:chq-3141", DK.CHEQUE, "3141", "party:hawthorn-cafe", "2025-11-21"),
    Document("doc:chq-3142", DK.CHEQUE, "3142", "party:rosalind-achterberg", "2025-12-05"),
    Document("doc:chq-3143", DK.CHEQUE, "3143", "party:hawthorn-cafe", "2025-12-05"),
    Document("doc:chq-3144", DK.CHEQUE, "3144", "party:kettleworth", "2025-12-09"),
    Document("doc:chq-3145", DK.CHEQUE, "3145", "party:stillwater-mutual", "2025-12-12"),
    Document("doc:chq-3146", DK.CHEQUE, "3146", "party:tessaly-packaging", "2025-12-15"),
    Document("doc:chq-3147", DK.CHEQUE, "3147", "party:sales-tax-bureau", "2025-12-19"),
    Document("doc:chq-3148", DK.CHEQUE, "3148", "party:hawthorn-cafe", "2025-12-19"),
    Document("doc:chq-3149", DK.CHEQUE, "3149", "party:callum-petrakis", "2025-12-22"),
    Document("doc:chq-3150", DK.CHEQUE, "3150", "party:kettleworth", "2025-12-23"),
    # the hotel's own checks, numbered by the hotel
    Document("doc:chq-wh-5488", DK.CHEQUE, "5488", "party:wintergreen-hotel", "2025-11-20"),
    Document("doc:chq-wh-5517", DK.CHEQUE, "5517", "party:wintergreen-hotel", "2025-12-04"),
    Document("doc:chq-wh-5533", DK.CHEQUE, "5533", "party:wintergreen-hotel", "2025-12-18"),
    Document("doc:chq-wh-5541", DK.CHEQUE, "5541", "party:wintergreen-hotel", "2025-12-29"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # November 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-11", "2025-11-03", "party:ashgrove", D("2850.00"),
                   cheque("doc:chq-2071", "2025-11-05"), "November rent, bakery premises, check 2071"),
    ExpensePayment("event:software-2025-11", "2025-11-04", "party:loafline", D("129.00"),
                   card("2025-11-04"), "Loafline ordering platform, November subscription"),
    ExpensePayment("event:telecom-2025-11", "2025-11-06", "party:skylark-telecom", D("158.77"),
                   card("2025-11-07"), "Telephone and internet, November"),
    ExpensePayment("event:claim-2025-11-achterberg", "2025-11-07", "party:rosalind-achterberg", D("276.80"),
                   cheque("doc:chq-3138", "2025-11-12"),
                   "Expense claim, October customer visits, mileage and meals, check 3138"),
    VendorPayment("event:pi-7712-payment", "2025-11-10", "party:bramblewood", "doc:pi-7712", D("4218.75"),
                  ach_out("2025-11-10"), "Payment of purchase invoice PI-7712"),
    ExpensePayment("event:fuel-2025-11a", "2025-11-12", "party:fleetfuel", D("205.90"),
                   card("2025-11-13"), "Delivery van fuel, first half of November"),
    Prepayment("event:insurance-2025-12-prepaid", "2025-11-13", "party:stillwater-mutual", D("718.25"),
               cheque("doc:chq-3139", "2025-11-17"), "2025-12",
               "December premium, bakery contents and liability cover, check 3139"),
    ExpensePayment("event:payroll-tax-2025-11", "2025-11-14", "party:commonwealth-revenue", D("5312.94"),
                   cheque("doc:chq-2072", "2025-11-18"), "October payroll withholdings, monthly deposit, check 2072"),
    CustomerReceipt("event:si-4118-receipt", "2025-11-17", "party:tidewell", "doc:si-4118", D("4193.15"),
                    ach_in("2025-11-17"), "Customer payment for SI-4118"),
    ExpensePayment("event:repairs-2025-11", "2025-11-18", "party:millstone-mechanical", D("372.40"),
                   card("2025-11-19"), "Deck oven thermostat replaced"),
    ExpensePayment("event:office-2025-11", "2025-11-19", "party:paperbark", D("64.28"),
                   card("2025-11-20"), "Till rolls and shelf labels"),
    ExpensePayment("event:sales-tax-2025-11", "2025-11-19", "party:sales-tax-bureau", D("968.44"),
                   cheque("doc:chq-3140", "2025-11-21"), "October sales tax return, check 3140"),
    CustomerReceipt("event:si-4109-receipt", "2025-11-20", "party:wintergreen-hotel", "doc:si-4109", D("2874.35"),
                    cheque("doc:chq-wh-5488", "2025-11-24"), "Customer check 5488 for SI-4109"),
    ExpensePayment("event:cafe-funding-2025-11", "2025-11-21", "party:hawthorn-cafe", D("3800.00"),
                   cheque("doc:chq-3141", "2025-11-25"), "Working capital advance to Hawthorn Cafe LLC, check 3141"),
    VendorPayment("event:pi-7728-payment", "2025-11-24", "party:bramblewood", "doc:pi-7728", D("3671.30"),
                  ach_out("2025-11-24"), "Payment of purchase invoice PI-7728"),
    CustomerReceipt("event:si-4102-receipt", "2025-11-25", "party:fennimore-street", "doc:si-4102", D("8742.60"),
                    ach_in("2025-11-25"), "Customer payment for SI-4102"),
    ExpensePayment("event:pay-2025-11-fentress", "2025-11-26", "party:marisol-fentress", D("3412.60"),
                   cheque("doc:chq-2073", "2025-11-26"), "November net pay, head baker, check 2073"),
    ExpensePayment("event:pay-2025-11-oyelaran", "2025-11-26", "party:declan-oyelaran", D("2948.35"),
                   cheque("doc:chq-2074", "2025-11-28"), "November net pay, baker, check 2074"),
    ExpensePayment("event:pay-2025-11-vukovic", "2025-11-26", "party:teodora-vukovic", D("2731.90"),
                   cheque("doc:chq-2075", "2025-11-28"), "November net pay, pastry cook, check 2075"),
    ExpensePayment("event:pay-2025-11-abernathy", "2025-11-26", "party:hamish-abernathy", D("2186.20"),
                   cheque("doc:chq-2076", "2025-11-26"), "November net pay, delivery driver, check 2076"),
    ExpensePayment("event:pay-2025-11-sundaram", "2025-11-26", "party:priya-sundaram", D("1573.85"),
                   cheque("doc:chq-2077", "2025-11-28"), "November net pay, counter assistant, check 2077"),
    VendorPayment("event:pi-7756-payment", "2025-11-26", "party:fallowfield-dairy", "doc:pi-7756", D("1864.30"),
                  ach_out("2025-11-26"), "Payment of purchase invoice PI-7756"),
    ExpensePayment("event:fuel-2025-11b", "2025-11-26", "party:fleetfuel", D("189.15"),
                   card("2025-11-27"), "Delivery van fuel, second half of November"),
    BankFee("event:fee-2025-11", "2025-11-28", D("42.50"), "Monthly account service charge"),
    # December 2025: the task period
    ExpensePayment("event:rent-2025-12", "2025-12-01", "party:ashgrove", D("2987.50"),
                   cheque("doc:chq-2078", "2025-12-03"), "December rent and common-area heating recharge, check 2078"),
    Sale("event:si-4139-sale", "2025-12-01", "party:tidewell", "doc:si-4139", D("4085.00"), D("0.06"), D("1838.25"),
         "Sale SI-4139, pastries and loaves delivered 17-30 November", "Cost of goods sold on SI-4139"),
    CustomerReceipt("event:si-4127-receipt", "2025-12-02", "party:tidewell", "doc:si-4127", D("4367.40"),
                    ach_in("2025-12-02"), "Customer payment for SI-4127"),
    ExpensePayment("event:software-2025-12", "2025-12-02", "party:loafline", D("149.00"),
                   card("2025-12-02"), "Loafline ordering platform, December subscription with the extra user seat"),
    ExpensePayment("event:fuel-2025-12a", "2025-12-03", "party:fleetfuel", D("214.60"),
                   card("2025-12-04"), "Delivery van fuel, first half of December"),
    Purchase("event:pi-7809-purchase", "2025-12-04", "party:bramblewood", "doc:pi-7809", D("4932.15"),
             "Purchase invoice PI-7809 received, bread flour and rye"),
    CustomerReceipt("event:si-4123-receipt", "2025-12-04", "party:wintergreen-hotel", "doc:si-4123", D("3218.60"),
                    cheque("doc:chq-wh-5517", "2025-12-08"), "Customer check 5517 for SI-4123"),
    ExpensePayment("event:claim-2025-12-achterberg", "2025-12-05", "party:rosalind-achterberg", D("312.45"),
                   cheque("doc:chq-3142", "2025-12-09"),
                   "Expense claim, November customer visits, mileage and meals, check 3142"),
    ExpensePayment("event:cafe-funding-2025-12a", "2025-12-05", "party:hawthorn-cafe", D("4250.00"),
                   cheque("doc:chq-3143", "2025-12-09"),
                   "Advance to Hawthorn Cafe LLC, fit-out progress payment, check 3143"),
    ExpensePayment("event:telecom-2025-12", "2025-12-06", "party:skylark-telecom", D("163.42"),
                   card("2025-12-08"), "Telephone and internet, December"),
    VendorPayment("event:pi-7745-payment", "2025-12-08", "party:bramblewood", "doc:pi-7745", D("3864.20"),
                  ach_out("2025-12-08"), "Payment of purchase invoice PI-7745"),
    Sale("event:si-4143-sale", "2025-12-08", "party:wintergreen-hotel", "doc:si-4143", D("3260.00"), D("0.06"),
         D("1467.00"), "Sale SI-4143, banquet breads and pastries delivered 24 November-7 December",
         "Cost of goods sold on SI-4143"),
    BankFee("event:fee-2025-12-checks", "2025-12-08", D("36.80"), "Check printing charge"),
    ExpensePayment("event:mixer-2025-12", "2025-12-09", "party:kettleworth", D("6480.00"),
                   cheque("doc:chq-3144", "2025-12-12"), "Spiral mixer, 60 quart, capitalised, check 3144"),
    Purchase("event:pi-7816-purchase", "2025-12-09", "party:fallowfield-dairy", "doc:pi-7816", D("1937.45"),
             "Purchase invoice PI-7816 received, butter, cream and eggs"),
    VendorPayment("event:pi-7793-payment", "2025-12-10", "party:fallowfield-dairy", "doc:pi-7793", D("1782.60"),
                  ach_out("2025-12-10"), "Payment of purchase invoice PI-7793"),
    ExpensePayment("event:office-2025-12", "2025-12-10", "party:paperbark", D("87.36"),
                   card("2025-12-11"), "Printer toner and order pads"),
    ExpensePayment("event:repairs-2025-12", "2025-12-11", "party:millstone-mechanical", D("486.90"),
                   card("2025-12-12"), "Deck oven door gasket and burner service"),
    Prepayment("event:insurance-2026-01-prepaid", "2025-12-12", "party:stillwater-mutual", D("734.60"),
               cheque("doc:chq-3145", "2025-12-16"), "2026-01",
               "January premium, bakery contents and liability cover, check 3145"),
    Purchase("event:pi-7824-purchase", "2025-12-12", "party:tessaly-packaging", "doc:pi-7824", D("1296.80"),
             "Purchase invoice PI-7824 received, bread bags and cake boxes"),
    ExpensePayment("event:payroll-tax-2025-12", "2025-12-15", "party:commonwealth-revenue", D("5487.62"),
                   cheque("doc:chq-2079", "2025-12-17"), "November payroll withholdings, monthly deposit, check 2079"),
    Sale("event:si-4146-sale", "2025-12-15", "party:tidewell", "doc:si-4146", D("3940.00"), D("0.06"), D("1773.00"),
         "Sale SI-4146, pastries and loaves delivered 1-14 December", "Cost of goods sold on SI-4146"),
    VendorPayment("event:pi-7769-payment", "2025-12-15", "party:tessaly-packaging", "doc:pi-7769", D("1148.25"),
                  cheque("doc:chq-3146", "2025-12-19"), "Payment of purchase invoice PI-7769, check 3146"),
    CustomerReceipt("event:si-4139-receipt", "2025-12-16", "party:tidewell", "doc:si-4139", D("4330.10"),
                    ach_in("2025-12-16"), "Customer payment for SI-4139"),
    ExpensePayment("event:travel-2025-12", "2025-12-16", "party:tollgate-travel", D("342.80"),
                   card("2025-12-17"), "Rail fare and one night's lodging, regional bakery trade fair"),
    ExpensePayment("event:fuel-2025-12b", "2025-12-17", "party:fleetfuel", D("198.35"),
                   card("2025-12-18"), "Delivery van fuel, second half of December"),
    Purchase("event:pi-7838-purchase", "2025-12-18", "party:bramblewood", "doc:pi-7838", D("3395.60"),
             "Purchase invoice PI-7838 received, pastry flour, sugar and butter"),
    CustomerReceipt("event:si-4143-receipt-part", "2025-12-18", "party:wintergreen-hotel", "doc:si-4143", D("2000.00"),
                    cheque("doc:chq-wh-5533", "2025-12-22"), "Customer check 5533, part payment against SI-4143"),
    ExpensePayment("event:sales-tax-2025-12", "2025-12-19", "party:sales-tax-bureau", D("1001.18"),
                   cheque("doc:chq-3147", "2025-12-23"), "November sales tax return, check 3147"),
    ExpensePayment("event:cafe-funding-2025-12b", "2025-12-19", "party:hawthorn-cafe", D("3175.00"),
                   cheque("doc:chq-3148", "2025-12-23"), "Advance to Hawthorn Cafe LLC, December wages funding, check 3148"),
    VendorPayment("event:pi-7781-payment", "2025-12-22", "party:bramblewood", "doc:pi-7781", D("4507.90"),
                  ach_out("2025-12-22"), "Payment of purchase invoice PI-7781"),
    ExpensePayment("event:claim-2025-12-petrakis", "2025-12-22", "party:callum-petrakis", D("587.30"),
                   cheque("doc:chq-3149", "2025-12-24"), "Expense claim, milling trade show travel and lodging, check 3149"),
    CustomerReceipt("event:si-4131-receipt", "2025-12-23", "party:fennimore-street", "doc:si-4131", D("9126.90"),
                    ach_in("2025-12-23"), "Customer payment for SI-4131"),
    ExpensePayment("event:proofer-2025-12", "2025-12-23", "party:kettleworth", D("2915.75"),
                   cheque("doc:chq-3150", "2025-12-30"), "Proofing cabinet, capitalised, check 3150"),
    Purchase("event:pi-7851-purchase", "2025-12-23", "party:fallowfield-dairy", "doc:pi-7851", D("2041.15"),
             "Purchase invoice PI-7851 received, butter, cream and eggs for the holiday run"),
    VendorPayment("event:pi-7816-payment", "2025-12-24", "party:fallowfield-dairy", "doc:pi-7816", D("1937.45"),
                  ach_out("2025-12-24"), "Payment of purchase invoice PI-7816"),
    # banked on 29 December, credited by the bank on 2 January: the deposit in transit
    CustomerReceipt("event:si-4143-receipt-balance", "2025-12-29", "party:wintergreen-hotel", "doc:si-4143", D("1455.60"),
                    cheque("doc:chq-wh-5541", "2026-01-02"), "Customer check 5541 settling SI-4143"),
    Sale("event:si-4152-sale", "2025-12-30", "party:fennimore-street", "doc:si-4152", D("9275.00"), D("0.06"), D("4173.75"),
         "Sale SI-4152, December standing order, bread and morning goods", "Cost of goods sold on SI-4152"),
    CustomerReceipt("event:si-4146-receipt", "2025-12-30", "party:tidewell", "doc:si-4146", D("4176.40"),
                    ach_in("2025-12-30"), "Customer payment for SI-4146"),
    ExpensePayment("event:pay-2025-12-fentress", "2025-12-30", "party:marisol-fentress", D("3587.15"),
                   cheque("doc:chq-2080", "2025-12-30"), "December net pay, head baker, check 2080"),
    ExpensePayment("event:pay-2025-12-oyelaran", "2025-12-30", "party:declan-oyelaran", D("3064.80"),
                   cheque("doc:chq-2081", "2025-12-30"), "December net pay, baker, check 2081"),
    ExpensePayment("event:pay-2025-12-vukovic", "2025-12-30", "party:teodora-vukovic", D("2876.45"),
                   cheque("doc:chq-2082", "2025-12-31"), "December net pay, pastry cook, check 2082"),
    # issued in December, cleared by the bank in January: the timing difference
    ExpensePayment("event:pay-2025-12-abernathy", "2025-12-30", "party:hamish-abernathy", D("2309.70"),
                   cheque("doc:chq-2083", "2026-01-05"), "December net pay, delivery driver, check 2083"),
    ExpensePayment("event:pay-2025-12-sundaram", "2025-12-30", "party:priya-sundaram", D("1642.30"),
                   cheque("doc:chq-2084", "2025-12-31"), "December net pay, counter assistant, check 2084"),
    BankFee("event:fee-2025-12", "2025-12-31", D("47.25"), "Monthly account service charge"),
)

WORLD = World(
    id="hawthorn-2025-12",
    title="Hawthorn Bakery - FY2025",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:sable-river-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-11-01", D("61208.47")),
    opening=OpeningPosition("2025-12-01", (("Assets:AR", D("16712.90")), ("Assets:Inventory", D("6840.00")),
                                           ("Liabilities:AP", D("-11302.95")),
                                           ("Liabilities:SalesTax-Payable", D("-1001.18")),
                                           ("Liabilities:PayrollTax", D("-5487.62")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

PERIOD = Period("2025-12-01", "2025-12-31", "December 2025")

PAYROLL_001 = TaskSpec(
    id="payroll_001",
    type="bank_reconciliation",
    prompt=("December payroll was paid by check and the November withholdings were remitted, but the payroll "
            "postings do not agree with the Sable River Bank statement for December. Reconcile the checking "
            "account against the statement, correct the books under the bookkeeping policy, and write the "
            "corrected ledger back to ledger.beancount."),
    period=Period("2025-12-01", "2025-12-31", "December 2025"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_net_pay_check", "rec:pay-2025-12-vukovic",
                        "the statement row names the check and the payee (CHECK 2082 TEODORA VUKOVIC, 2876.45 on "
                        "31 December) and no ledger entry matches it; vendors.csv lists Teodora Vukovic on monthly "
                        "payroll terms with Expenses:Salaries as the default account, so under the payroll section "
                        "the net pay check is the expense, and the dates section puts it on the bank's date"),
        AlterRecognition("transposed_net_pay_check", "rec:pay-2025-12-oyelaran", "transpose_digits", 2,
                         "the ledger carries the 30 December net pay check to Declan Oyelaran at 3046.80 while the "
                         "statement row of the same date and payee (CHECK 2081 DECLAN OYELARAN) shows 3064.80; the "
                         "payroll section says to re-post the entry with the statement's amount on the original "
                         "date, against Expenses:Salaries"),
        OmitRecognition("unrecorded_withholdings_remittance", "rec:payroll-tax-2025-12",
                        "the statement row names the check and the payee (CHECK 2079 COMMONWEALTH REVENUE SERVICE, "
                        "5487.62 on 17 December) and no ledger entry matches it; vendors.csv lists the revenue "
                        "service on monthly remittance terms with Liabilities:PayrollTax as the default "
                        "account, the ledger's opening balances carry that liability, and the payroll section says "
                        "the remittance check settles it; the dates section puts the entry on the bank's date"),
    )),
)

BANK_RECON_HAWTHORN = TaskSpec(
    id="bank_recon_hawthorn",
    type="bank_reconciliation",
    prompt=("The Sable River Bank statement for December is in and the checking account has to be reconciled "
            "before the year-end figures go to the owners. The differences look routine - a wholesale customer's "
            "transfer, a settlement to the dairy cooperative and the bank's own charge are among the items that "
            "do not agree - but every row has to be accounted for. Compare the statement with the ledger line by "
            "line, correct whatever the books have wrong under the bookkeeping policy, leave the timing "
            "differences as they are, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_service_charge", "rec:fee-2025-12",
                        "the statement row is a bank-initiated charge with no counterparty (MONTHLY ACCOUNT SERVICE "
                        "CHARGE, 47.25 on 31 December) and no ledger entry matches it; the bank service charges "
                        "section records such a charge to Expenses:BankFees on the date the bank applies it"),
        AlterRecognition("transposed_mill_settlement", "rec:pi-7745-payment", "transpose_digits", 2,
                         "the ledger carries the 8 December ACH settlement of PI-7745 to Bramblewood Flour Mills at "
                         "3846.20 while the statement row of the same date and reference (ACH OUT BRAMBLEWOOD FLOUR "
                         "MILLS, PI-7745) shows 3864.20, which is also the invoice gross; the payment runs section "
                         "says to re-post the entry with the statement's amount on the original date, against "
                         "Liabilities:AP"),
        DuplicateRecognition("duplicated_customer_receipt", "rec:si-4146-receipt",
                             "the ledger carries the 30 December ACH receipt of 4176.40 from Tidewell Coffee Roasters "
                             "for SI-4146 twice and the statement shows one ACH IN row with that reference; the "
                             "collections section says to remove one copy and leave the other as it was"),
    )),
)

AP_PAYMENT_RUN_HAWTHORN = TaskSpec(
    id="ap_payment_run_hawthorn",
    type="bank_reconciliation",
    prompt=("The December payment run to the ingredient and packaging suppliers has gone out - ACH transfers to "
            "Bramblewood Flour Mills and Fallowfield Dairy Cooperative quoting the invoice numbers, and one check "
            "to Tessaly Box and Packaging - but the payables ledger does not tie to the Sable River Bank "
            "statement. Work through each supplier settlement on the statement against the entries in the "
            "ledger, put right the ones the books have missed, mis-keyed or posted twice under the bookkeeping "
            "policy, leave the December purchase invoices themselves as they are, and write the corrected ledger "
            "back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_run_payment", "rec:pi-7745-payment",
                        "the statement row names the supplier and the invoice (ACH OUT BRAMBLEWOOD FLOUR MILLS, "
                        "PI-7745, 3864.20 on 8 December) and no ledger entry matches it; vendors.csv books the mill "
                        "to Assets:Inventory, the ledger's opening payables carry the invoice, and the payment runs "
                        "section says the settlement is recorded to Liabilities:AP on the bank's date"),
        AlterRecognition("transposed_run_payment", "rec:pi-7793-payment", "transpose_digits", 1,
                         "the ledger carries the 10 December ACH settlement of PI-7793 to Fallowfield Dairy "
                         "Cooperative at 1872.60 while the statement row of the same date and reference (ACH OUT "
                         "FALLOWFIELD DAIRY COOPERATIVE, PI-7793) shows 1782.60, which is also the invoice gross; "
                         "the payment runs section says to re-post the entry with the statement's amount on the "
                         "original date, against Liabilities:AP"),
        DuplicateRecognition("duplicated_supplier_check", "rec:pi-7769-payment",
                             "the ledger carries the 15 December check settling PI-7769 to Tessaly Box and Packaging "
                             "(1148.25) twice and the statement shows one CHECK 3146 TESSALY BOX AND PACKAGING row; "
                             "the payment runs section says to remove one copy and leave the other as it was"),
    )),
)

AR_COLLECTIONS_HAWTHORN = TaskSpec(
    id="ar_collections_hawthorn",
    type="bank_reconciliation",
    prompt=("December collections have to be posted before the receivables aging goes to the owners. Fennimore "
            "Street Grocers and Tidewell Coffee Roasters paid by ACH, Wintergreen Hotel Kitchens paid by its own "
            "checks including a part payment against its December invoice, and the hotel's last check of the "
            "month was banked on the 29th and had not been credited at the cut-off. Agree the receipts in the "
            "ledger to the Sable River Bank statement, correct the receivables entries under the bookkeeping "
            "policy without touching the sales invoices or the deposit in transit, and write the corrected "
            "ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_hotel_check", "rec:si-4123-receipt",
                        "the statement row names the customer's check and the payer as a credit (CHECK 5517 "
                        "WINTERGREEN HOTEL KITCHENS, 3218.60 on 8 December) and no ledger entry matches it; "
                        "customers.csv maps the hotel to Assets:AR, the ledger's opening receivables carry its "
                        "November invoice, and the collections section puts the added receipt on the bank's date"),
        AlterRecognition("transposed_roaster_receipt", "rec:si-4139-receipt", "transpose_digits", 0,
                         "the ledger carries the 16 December ACH receipt from Tidewell Coffee Roasters for SI-4139 "
                         "at 3430.10 while the statement row of the same date and reference (ACH IN TIDEWELL "
                         "COFFEE ROASTERS, SI-4139) shows 4330.10, which is also the invoice gross; the collections "
                         "section says to re-post the receipt with the statement's amount on the original date"),
        DuplicateRecognition("duplicated_part_payment", "rec:si-4143-receipt-part",
                             "the ledger carries the 18 December part payment of 2000.00 from Wintergreen Hotel "
                             "Kitchens against SI-4143 twice and the statement shows one CHECK 5533 WINTERGREEN "
                             "HOTEL KITCHENS credit; the collections section says to remove one copy and leave the "
                             "other as it was"),
    )),
)

BANK_FEED_CATEGORISATION_HAWTHORN = TaskSpec(
    id="bank_feed_categorisation_hawthorn",
    type="bank_reconciliation",
    prompt=("The December card spend has come through on the Sable River Bank feed - the Loafline ordering "
            "platform, Skylark Telecom, Paperbark office supplies, the Tollgate booking for the trade fair, the "
            "Fleetfuel card and the Millstone oven service - and it has to be categorised in the ledger from the "
            "vendor master before the month can close. Match each DEBIT CARD row to its entry, add the charges "
            "the books do not carry against the vendor's default account, correct any that were keyed wrongly, "
            "and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_software_charge", "rec:software-2025-12",
                        "the statement row names the vendor (DEBIT CARD LOAFLINE SOFTWARE, 149.00 on 2 December) "
                        "and no ledger entry matches it; vendors.csv lists Loafline Software on card on file terms "
                        "with Expenses:Software as the default account, and the card spend section records the "
                        "charge there on the bank's date"),
        OmitRecognition("unrecorded_travel_charge", "rec:travel-2025-12",
                        "the statement row names the vendor (DEBIT CARD TOLLGATE TRAVEL, 342.80 on 17 December) "
                        "and no ledger entry matches it; vendors.csv lists Tollgate Travel on card on file terms "
                        "with Expenses:Travel as the default account, and the card spend section records the "
                        "charge there on the bank's date"),
        AlterRecognition("transposed_telecom_charge", "rec:telecom-2025-12", "transpose_digits", 1,
                         "the ledger carries the 6 December card charge to Skylark Telecom at 136.42 while the "
                         "statement row two days later for the same vendor (DEBIT CARD SKYLARK TELECOM) shows "
                         "163.42; the card spend section says to re-post the entry with the statement's amount on "
                         "the original date, against Expenses:Telecom"),
    )),
)

EXPENSE_REPORTS_HAWTHORN = TaskSpec(
    id="expense_reports_hawthorn",
    type="bank_reconciliation",
    prompt=("Two expense claims were approved and reimbursed by check in December - Rosalind Achterberg's "
            "November customer visits and Callum Petrakis's trade show travel - and the delivery van's Fleetfuel "
            "card was charged twice in the month. The claims and fuel postings do not agree with the Sable River "
            "Bank statement. Tie the reimbursement checks and the fuel card rows to the ledger, correct what is "
            "missing, doubled or mis-keyed under the bookkeeping policy, leave the payroll checks alone, and "
            "write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_reimbursement_check", "rec:claim-2025-12-achterberg",
                        "the statement row names the check and the payee (CHECK 3142 ROSALIND ACHTERBERG, 312.45 "
                        "on 9 December) and no ledger entry matches it; vendors.csv lists Rosalind Achterberg on "
                        "expense claim terms with Expenses:Travel as the default account, so under the employee "
                        "expense claims section the check is the expense, and the dates section puts it on the "
                        "bank's date"),
        DuplicateRecognition("duplicated_reimbursement_check", "rec:claim-2025-12-petrakis",
                             "the ledger carries the 22 December reimbursement check to Callum Petrakis (587.30) "
                             "twice and the statement shows one CHECK 3149 CALLUM PETRAKIS row; the employee "
                             "expense claims section says to remove one copy and leave the other as it was"),
        AlterRecognition("transposed_fuel_charge", "rec:fuel-2025-12b", "transpose_digits", 2,
                         "the ledger carries the 17 December card charge to Fleetfuel Card Services at 193.85 "
                         "while the statement row of the next day for the same vendor (DEBIT CARD FLEETFUEL CARD "
                         "SERVICES) shows 198.35; the card spend section says to re-post the entry with the "
                         "statement's amount on the original date, against Expenses:Vehicle"),
    )),
)

SALES_TAX_REMITTANCE_HAWTHORN = TaskSpec(
    id="sales_tax_remittance_hawthorn",
    type="bank_reconciliation",
    prompt=("The November sales tax return was filed and paid by check to the Commonwealth Sales Tax Bureau in "
            "December, and the December sales carry their own tax. The December return cannot be prepared until "
            "the sales tax liability is right, and it is not: the ledger does not tie to the Sable River Bank "
            "statement. Reconcile the checking account, make sure the remittance and the wholesale customers' "
            "receipts are posted as the bookkeeping policy requires, correct whatever else the statement shows "
            "differently, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_tax_remittance", "rec:sales-tax-2025-12",
                        "the statement row names the check and the payee (CHECK 3147 COMMONWEALTH SALES TAX BUREAU, "
                        "1001.18 on 23 December) and no ledger entry matches it; vendors.csv lists the bureau on "
                        "monthly filing terms with Liabilities:SalesTax-Payable as the default account, the "
                        "ledger's opening balances carry that liability, and the sales tax remittance section says "
                        "the check settles it on the bank's date"),
        AlterRecognition("transposed_roaster_receipt", "rec:si-4139-receipt", "transpose_digits", 2,
                         "the ledger carries the 16 December ACH receipt from Tidewell Coffee Roasters for SI-4139 "
                         "at 4303.10 while the statement row of the same date and reference (ACH IN TIDEWELL "
                         "COFFEE ROASTERS, SI-4139) shows 4330.10, which is also the invoice gross; the collections "
                         "section says to re-post the receipt with the statement's amount on the original date"),
        DuplicateRecognition("duplicated_check_printing_charge", "rec:fee-2025-12-checks",
                             "the ledger carries the 8 December check printing charge of 36.80 twice and the "
                             "statement shows one CHECK PRINTING CHARGE row; the bank service charges section says "
                             "to remove one copy and leave the other as it was"),
    )),
)

FIXED_ASSETS_HAWTHORN = TaskSpec(
    id="fixed_assets_hawthorn",
    type="bank_reconciliation",
    prompt=("Two pieces of bakery equipment were bought from Kettleworth Bakery Equipment in December, a spiral "
            "mixer and a proofing cabinet, both paid by check, and Millstone Mechanical serviced the deck oven "
            "on the card. The fixed asset register is being brought up to date for the year end and the "
            "equipment postings have to agree with the Sable River Bank statement. Reconcile the checking "
            "account, capitalise or expense each payment as the bookkeeping policy and the vendor master direct, "
            "correct the other differences the statement shows, and write the corrected ledger back to "
            "ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_mixer_check", "rec:mixer-2025-12",
                        "the statement row names the check and the payee (CHECK 3144 KETTLEWORTH BAKERY EQUIPMENT, "
                        "6480.00 on 12 December) and no ledger entry matches it; vendors.csv lists the equipment "
                        "supplier with Assets:Equipment as the default account, and the equipment section says a "
                        "payment to it is capitalised there on the bank's date"),
        AlterRecognition("transposed_repair_charge", "rec:repairs-2025-12", "transpose_digits", 0,
                         "the ledger carries the 11 December card charge to Millstone Mechanical Services at 846.90 "
                         "while the statement row of the next day for the same vendor (DEBIT CARD MILLSTONE "
                         "MECHANICAL SERVICES) shows 486.90; the equipment section expenses repairs to "
                         "Expenses:Repairs and the card spend section says to re-post the entry with the "
                         "statement's amount on the original date"),
        OmitRecognition("unrecorded_check_printing_charge", "rec:fee-2025-12-checks",
                        "the statement row is a bank-initiated charge with no counterparty (CHECK PRINTING CHARGE, "
                        "36.80 on 8 December) and no ledger entry matches it; the bank service charges section "
                        "records it to Expenses:BankFees on the date the bank applies it"),
    )),
)

INTERCOMPANY_TRANSFERS_HAWTHORN = TaskSpec(
    id="intercompany_transfers_hawthorn",
    type="bank_reconciliation",
    prompt=("Hawthorn Bakery advanced cash to Hawthorn Cafe LLC twice in December, once for the fit-out and once "
            "to fund the cafe's December wages, and the intercompany balance has to be agreed with the cafe's "
            "books at the close. The advances in the ledger do not tie to the Sable River Bank statement, and "
            "the hotel's check receipts need a look as well. Reconcile the checking account, post each advance "
            "to the due-from account as the bookkeeping policy requires, correct the other differences, and "
            "write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_fitout_advance", "rec:cafe-funding-2025-12a",
                        "the statement row names the check and the payee (CHECK 3143 HAWTHORN CAFE LLC, 4250.00 on "
                        "9 December) and no ledger entry matches it; vendors.csv lists the cafe on intercompany "
                        "terms with Assets:Due-From-Hawthorn-Cafe as the default account, and the intercompany "
                        "balances section says an advance is recorded there on the bank's date"),
        DuplicateRecognition("duplicated_wages_advance", "rec:cafe-funding-2025-12b",
                             "the ledger carries the 19 December advance check to Hawthorn Cafe LLC (3175.00) twice "
                             "and the statement shows one CHECK 3148 HAWTHORN CAFE LLC row; the intercompany "
                             "balances section says to remove one copy and leave the other as it was"),
        AlterRecognition("transposed_hotel_check", "rec:si-4123-receipt", "transpose_digits", 2,
                         "the ledger carries the 4 December receipt of the hotel's check 5517 for SI-4123 at "
                         "3281.60 while the statement credit four days later naming the same check (CHECK 5517 "
                         "WINTERGREEN HOTEL KITCHENS) shows 3218.60, which is also the invoice gross; the "
                         "collections section says to re-post the receipt with the statement's amount on the "
                         "original date, against Assets:AR"),
    )),
)

MONTH_END_CLOSE_HAWTHORN = TaskSpec(
    id="month_end_close_hawthorn",
    type="bank_reconciliation",
    prompt=("December is being closed. The January insurance premium was paid to Stillwater Mutual Insurance in "
            "December, the bank applied two separate charges during the month, and the wholesale customers' "
            "transfers have all cleared. The ledger does not yet agree with the Sable River Bank statement. "
            "Work through the differences under the bookkeeping policy - the prepayment, the bank charges and "
            "the receipts - leave the outstanding payroll check and the deposit in transit as the timing items "
            "they are, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_insurance_prepayment", "rec:insurance-2026-01-prepaid",
                        "the statement row names the check and the insurer (CHECK 3145 STILLWATER MUTUAL INSURANCE, "
                        "734.60 on 16 December) and no ledger entry matches it; vendors.csv books the insurer to "
                        "Assets:Prepayments and the prepayments section says a premium paid in December for January "
                        "cover is a prepayment, added on the bank's date"),
        AlterRecognition("transposed_service_charge", "rec:fee-2025-12", "transpose_digits", 0,
                         "the ledger carries the 31 December monthly service charge at 74.25 while the statement "
                         "row of the same date and wording shows 47.25; the bank service charges section says a "
                         "mis-keyed bank charge is re-posted with the statement's amount on the original date, to "
                         "Expenses:BankFees"),
        DuplicateRecognition("duplicated_roaster_receipt", "rec:si-4127-receipt",
                             "the ledger carries the 2 December ACH receipt of 4367.40 from Tidewell Coffee Roasters "
                             "for SI-4127 twice and the statement shows one ACH IN row with that reference; the "
                             "collections section says to remove one copy and leave the other as it was"),
    )),
)

TASKS = {task.id: task for task in (
    PAYROLL_001,
    BANK_RECON_HAWTHORN,
    AP_PAYMENT_RUN_HAWTHORN,
    AR_COLLECTIONS_HAWTHORN,
    BANK_FEED_CATEGORISATION_HAWTHORN,
    EXPENSE_REPORTS_HAWTHORN,
    SALES_TAX_REMITTANCE_HAWTHORN,
    FIXED_ASSETS_HAWTHORN,
    INTERCOMPANY_TRANSFERS_HAWTHORN,
    MONTH_END_CLOSE_HAWTHORN,
)}
