"""Maple Street Veterinary Clinic, December 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

One month, ten tasks. The clinic invoices its kennel, stable and
rescue-society clients on terms and collects by ACH or by check; it buys
drugs and consumables from one supplier on net 30 and pays by ACH quoting
the purchase invoice, and laboratory reagents from a second supplier on
net 15 paid by printed check; it pays rent by handwritten check to its
landlord and its practice insurance premium by check to the insurer, a
month ahead of the cover. Three employees are paid net by printed check
once a month and the withholdings are remitted to the Federal Revenue
Service the month after; the sales tax collected in a month is filed and
paid online the month after. Relief staff and the practice manager claim
mileage and conference travel and are reimbursed by printed check; the
practice vehicle runs on a fuel card. Software, phone lines, stationery and
autoclave servicing go on the debit card. A dental radiography set was
bought for cash in December, and the sister company set up in the autumn,
Maple Street Equine Services LLC, was advanced working capital twice.

Every task sees the same statement and the same golden facts; the tasks
differ in the instruction and in what is planted. The rent check issued on
29 December for January and the client check taken at the front desk on
30 December are not mutations: the bank cleared them on 6 and 5 January,
and the December statement's projection classifies both NOT_YET_SETTLED on
its own. The handwritten check book (41xx) and the printed check run (62xx)
are two numbering series on the one checking account.
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

POLICY_TEXT = """# Maple Street Veterinary Clinic - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, per-item fees,
returned item fees) are recorded to `Expenses:BankFees` on the date the bank
applies them, for the amount the bank shows. A returned item fee is a charge
of the bank's own and is booked as a bank fee; it is not netted against the
client receipt it relates to.

## Customer receipts
Cash received from a client reduces `Assets:AR`. Where the deposit reference
or the check identifies a sales invoice, it is applied against that invoice.
Client checks are recorded on the day they are received at the front desk,
not the day the bank clears them.

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

Drugs, vaccines and surgical consumables are bought from the veterinary
supplier on net 30 terms and are booked to `Assets:Inventory` on the invoice
date; the payment that follows, by ACH quoting the purchase invoice number,
settles `Liabilities:AP`. Laboratory reagents and test kits are bought from
the laboratory supplier on net 15 terms, booked to `Assets:Inventory` on the
invoice date and paid by printed check; that check also settles
`Liabilities:AP`.

Some payees in the vendor master are not suppliers of goods at all: the
revenue services, the employees, the equipment supplier and the sister
company. For those payees no payable is ever raised, and the payment is
recorded on the day it is made directly to the account the vendor master
gives as the payee's `default_account`, whether that account is an expense,
a liability or an asset. The payroll, sales tax remittance, employee expense
claims, equipment and intercompany sections below say why in each case.

## Payment runs
Supplier invoices are booked to `Liabilities:AP` when they arrive. The
clinic runs its supplier payments in the middle and at the end of the
month: the veterinary supplier is paid by ACH quoting the purchase invoice
number, the laboratory supplier by printed check with the invoice on the
stub. Every supplier payment settles `Liabilities:AP` for the amount paid
and is never booked to inventory a second time. A supplier payment on the
statement that the ledger does not carry is added to `Liabilities:AP` for
the payee and the amount shown, on the bank's date; a supplier payment
keyed with a wrong amount is re-posted at the statement's amount on its
original date; a supplier payment posted twice loses one copy.

## Collections
Clients on account are invoiced on the day of treatment and pay by ACH
quoting the invoice number or by check handed in at the front desk. A part
payment is applied to the invoice it quotes for the amount received, and the
balance of the invoice stays in `Assets:AR` until the next remittance. A
receipt on the statement that the ledger does not carry is added to
`Assets:AR` for the client and the amount shown, on the bank's date; a
receipt keyed with a wrong amount is re-posted at the statement's amount on
its original date; a receipt posted twice loses one copy.

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
client or supplier movement the ledger date is never later than the
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
`Assets:Prepayments` and released to expense in the month they cover. Rent
paid in one month for the following month is a prepayment, not an expense of
the month it was paid.

The practice insurance premium is invoiced by the insurer a month in advance
and is paid by check in the month before the cover month. A premium paid in
December for January cover is booked to `Assets:Prepayments` on the date the
check is issued and released to `Expenses:Insurance` in January. The insurer
carries `Assets:Prepayments` as its `default_account` in the vendor master
for exactly this reason: every payment to the insurer is a payment in
advance, and the vendor master and this section agree on where it lands. No
payable is raised for a premium.

## Card spend
The clinic's debit card is used for the practice management software
subscription, the phone lines and internet, reception stationery, fuel for
the practice vehicle and the servicing of the autoclave. A card row on the
statement is booked on the bank's date to the `default_account` the vendor
master gives for the vendor the row names: the software vendor to
`Expenses:Software`, the telecom vendor to `Expenses:Telecom`, the
stationer to `Expenses:Office`, the fuel card to `Expenses:Vehicle` and
the repairer to `Expenses:Repairs`. No payable is raised for card spend, and
the online sales tax filing paid by card is governed by the sales tax
remittance section, not by this one.

## Employee expense claims
Relief veterinarians and staff claim mileage, travel and subsistence on an
expense claim form; an approved claim is reimbursed by printed check. Each
claimant is in the vendor master with the terms "expense claim" and
`Expenses:Travel` as the `default_account`, and the reimbursement is booked
to that account on the day the check is issued, for the amount of the check.
No payable is raised for a claim. Fuel drawn on the practice fuel card is not
a claim; it is card spend to `Expenses:Vehicle`.

## Payroll
Salaries are paid once a month by printed check for the net amount on each
payslip. Each employee is in the vendor master with the terms "monthly
payroll" and `Expenses:Salaries` as the `default_account`, and the net pay
check is booked to that account on the day it is issued, for the amount of
the check. The withholdings deducted from pay are owed to the Federal
Revenue Service and are carried in `Liabilities:PayrollTax`; they are
remitted by printed check in the month after the payroll they relate to,
and the remittance is booked to `Liabilities:PayrollTax`, the revenue
service's `default_account`, reducing the liability. The gross-up journal
that raises the withholdings for a month is posted from the payroll
bureau's register in the following month, after the bank reconciliation.
No payable is raised for payroll or for a remittance.

## Sales tax
The clinic collects sales tax from clients on treatment fees and dispensed
medicines and owes it to the state. Drugs and consumables bought for use in
treatment are exempt under the resale certificate, so no tax is recoverable
on the purchase side.

## Sales tax remittance
The tax collected in a month is filed with the State Revenue Department and
paid online by card in the following month. The department is in the vendor
master with the terms "monthly filing" and `Liabilities:SalesTax-Payable` as
its `default_account`; the payment is booked to that account on the bank's
date, for the amount the statement shows, and reduces the liability. A
remittance is never an expense and never a payable.

## Equipment
Clinical and surgical equipment is bought from equipment suppliers who carry
`Assets:Equipment` as their `default_account` in the vendor master and is
paid by printed check on delivery. The purchase is capitalised on payment:
the check is booked to `Assets:Equipment` on the day it is issued, for the
amount of the check, and no payable is raised. Servicing, calibration and
repair of equipment the clinic already owns is not capitalised; it is card
spend to `Expenses:Repairs`, the repairer's `default_account`. Depreciation
is a year-end journal outside the monthly reconciliation.

## Intercompany balances
Maple Street Equine Services LLC is a sister company under common
ownership. The clinic advances it working capital by printed check; each
advance is booked to `Assets:Due-From-Maple-Equine`, the `default_account`
the sister company carries in the vendor master under the terms
"intercompany", on the day the check is issued and for the amount of the
check. An advance is a loan, not an expense; a repayment from the sister
company reduces the same balance. No payable is raised for an advance.

## Month-end close checklist
The checking account is agreed to the bank statement before the month is
closed, and each difference has exactly one correction:

- Bank charges are agreed to the statement line by line. A charge on the
  statement that the ledger does not carry is added to `Expenses:BankFees`
  for the statement's amount on the statement's date. A bank charge posted
  with a mis-keyed amount is corrected by re-posting the entry with the
  amount the statement shows, on the date the entry was originally posted;
  only the amount changes.
- Client receipts are applied to invoices. A receipt that was posted twice is
  corrected by removing one of the two copies; the copy that remains is left
  exactly as it was.
- A payment on the statement that the ledger does not carry is added for the
  payee and the amount the statement shows, to the account the vendor master
  and this policy give for that payee, on the date the bank shows.
- Checks issued before the cut-off that clear after it are listed as
  outstanding and are not touched.

## Suspense accounts
The clinic does not operate a suspense or plug account. Every posting is made
to the account that reflects the underlying transaction.
"""

OPENED = "2025-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Wattle Creek Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Fees receivable from clients on account", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Drugs, vaccines and surgical consumables held for treatment and dispensing", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Assets:Equipment", K.ASSET, "Clinical and surgical equipment at cost", OPENED, 1500),
    Account("Assets:Due-From-Maple-Equine", K.ASSET, "Working capital advanced to Maple Street Equine Services LLC", OPENED, 1600),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from clients and owed to the state", OPENED, 2100),
    Account("Liabilities:PayrollTax", K.LIABILITY, "Employee withholdings owed to the Federal Revenue Service", OPENED, 2200),
    Account("Income:Sales", K.INCOME, "Fees for treatments, procedures and dispensed medicines", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of drugs and consumables used on treatments", OPENED, 5000),
    Account("Expenses:Office", K.EXPENSE, "Reception stationery, record cards and printer consumables", OPENED, 5100),
    Account("Expenses:Rent", K.EXPENSE, "Clinic premises rent for the period", OPENED, 5200),
    Account("Expenses:Insurance", K.EXPENSE, "Practice insurance premium for the month of cover", OPENED, 5250),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Expenses:Salaries", K.EXPENSE, "Net salaries paid to employees", OPENED, 5400),
    Account("Expenses:Travel", K.EXPENSE, "Mileage, travel and subsistence reimbursed on expense claims", OPENED, 5410),
    Account("Expenses:Vehicle", K.EXPENSE, "Fuel and running costs of the practice vehicle", OPENED, 5420),
    Account("Expenses:Software", K.EXPENSE, "Practice management software subscription", OPENED, 5500),
    Account("Expenses:Telecom", K.EXPENSE, "Clinic phone lines and internet", OPENED, 5510),
    Account("Expenses:Repairs", K.EXPENSE, "Servicing and repair of clinical equipment", OPENED, 5600),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:tallgrass", "Tallgrass Equestrian Centre", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:hollybrook", "Hollybrook Boarding Kennels", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:bramblewood", "Bramblewood Animal Rescue", R.CUSTOMER, 3, "net 15", "Assets:AR"),
    Party("party:corbett", "Corbett Veterinary Supplies", R.VENDOR, 4, "net 30", "Assets:Inventory"),
    Party("party:shieldstone", "Shieldstone Mutual Insurance", R.VENDOR, 5, "due on receipt", "Assets:Prepayments"),
    Party("party:kilbride", "Kilbride Property Holdings", R.VENDOR, 6, "due on receipt", "Expenses:Rent"),
    Party("party:wattle-creek-bank", "Wattle Creek Bank", R.BANK, 7),
    Party("party:fernleigh", "Fernleigh Laboratory Supplies", R.VENDOR, 8, "net 15", "Assets:Inventory"),
    Party("party:achterberg", "Rosalind Achterberg", R.VENDOR, 9, "monthly payroll", "Expenses:Salaries"),
    Party("party:oyelaran", "Marcus Oyelaran", R.VENDOR, 10, "monthly payroll", "Expenses:Salaries"),
    Party("party:tremblay", "Fiona Tremblay", R.VENDOR, 11, "monthly payroll", "Expenses:Salaries"),
    Party("party:federal-revenue", "Federal Revenue Service", R.VENDOR, 12, "monthly remittance", "Liabilities:PayrollTax"),
    Party("party:state-revenue", "State Revenue Department", R.VENDOR, 13, "monthly filing", "Liabilities:SalesTax-Payable"),
    Party("party:broderick", "Hamish Broderick", R.VENDOR, 14, "expense claim", "Expenses:Travel"),
    Party("party:solvang", "Ingrid Solvang", R.VENDOR, 15, "expense claim", "Expenses:Travel"),
    Party("party:summerlee", "Summerlee Fuel Cards", R.VENDOR, 16, "due on receipt", "Expenses:Vehicle"),
    Party("party:cloudpaw", "Cloudpaw Practice Software", R.VENDOR, 17, "due on receipt", "Expenses:Software"),
    Party("party:orbitline", "Orbitline Telecom", R.VENDOR, 18, "due on receipt", "Expenses:Telecom"),
    Party("party:paperbark", "Paperbark Stationery Co", R.VENDOR, 19, "due on receipt", "Expenses:Office"),
    Party("party:lumenvet", "Lumenvet Imaging Systems", R.VENDOR, 20, "due on receipt", "Assets:Equipment"),
    Party("party:ashgrove", "Ashgrove Autoclave Repairs", R.VENDOR, 21, "due on receipt", "Expenses:Repairs"),
    Party("party:maple-equine", "Maple Street Equine Services LLC", R.VENDOR, 22, "intercompany", "Assets:Due-From-Maple-Equine"),
)

DOCUMENTS = (
    Document("doc:si-7304", DK.SALES_INVOICE, "SI-7304", "party:hollybrook", "2025-10-09", D("2675.00")),
    Document("doc:si-7311", DK.SALES_INVOICE, "SI-7311", "party:tallgrass", "2025-11-18", D("3402.60")),
    Document("doc:si-7313", DK.SALES_INVOICE, "SI-7313", "party:bramblewood", "2025-11-24", D("1027.20")),
    Document("doc:si-7318", DK.SALES_INVOICE, "SI-7318", "party:hollybrook", "2025-12-02", D("2075.80")),
    Document("doc:si-7319", DK.SALES_INVOICE, "SI-7319", "party:tallgrass", "2025-12-05", D("4879.20")),
    Document("doc:si-7320", DK.SALES_INVOICE, "SI-7320", "party:bramblewood", "2025-12-17", D("1353.55")),
    Document("doc:si-7321", DK.SALES_INVOICE, "SI-7321", "party:hollybrook", "2025-12-18", D("1690.60")),
    Document("doc:pi-5117", DK.PURCHASE_INVOICE, "PI-5117", "party:corbett", "2025-10-14", D("2913.40")),
    Document("doc:pi-5128", DK.PURCHASE_INVOICE, "PI-5128", "party:fernleigh", "2025-11-04", D("1156.30")),
    Document("doc:pi-5131", DK.PURCHASE_INVOICE, "PI-5131", "party:corbett", "2025-11-12", D("2486.35")),
    Document("doc:pi-5136", DK.PURCHASE_INVOICE, "PI-5136", "party:corbett", "2025-11-26", D("1742.60")),
    Document("doc:pi-5142", DK.PURCHASE_INVOICE, "PI-5142", "party:corbett", "2025-12-10", D("3118.72")),
    Document("doc:pi-5145", DK.PURCHASE_INVOICE, "PI-5145", "party:fernleigh", "2025-12-04", D("2264.75")),
    Document("doc:pi-5148", DK.PURCHASE_INVOICE, "PI-5148", "party:fernleigh", "2025-12-22", D("1917.30")),
    # the handwritten check book: rent and insurance
    Document("doc:chq-4171", DK.CHEQUE, "4171", "party:kilbride", "2025-11-03"),
    Document("doc:chq-4172", DK.CHEQUE, "4172", "party:shieldstone", "2025-11-14"),
    Document("doc:chq-4173", DK.CHEQUE, "4173", "party:kilbride", "2025-12-01"),
    Document("doc:chq-4174", DK.CHEQUE, "4174", "party:shieldstone", "2025-12-15"),
    Document("doc:chq-4175", DK.CHEQUE, "4175", "party:kilbride", "2025-12-29"),
    # the printed check run: payroll, remittances, suppliers, claims, equipment, the sister company
    Document("doc:chq-6201", DK.CHEQUE, "6201", "party:maple-equine", "2025-11-07"),
    Document("doc:chq-6202", DK.CHEQUE, "6202", "party:broderick", "2025-11-11"),
    Document("doc:chq-6203", DK.CHEQUE, "6203", "party:federal-revenue", "2025-11-14"),
    Document("doc:chq-6204", DK.CHEQUE, "6204", "party:fernleigh", "2025-11-19"),
    Document("doc:chq-6205", DK.CHEQUE, "6205", "party:achterberg", "2025-11-25"),
    Document("doc:chq-6206", DK.CHEQUE, "6206", "party:oyelaran", "2025-11-25"),
    Document("doc:chq-6207", DK.CHEQUE, "6207", "party:tremblay", "2025-11-25"),
    Document("doc:chq-6208", DK.CHEQUE, "6208", "party:maple-equine", "2025-12-03"),
    Document("doc:chq-6209", DK.CHEQUE, "6209", "party:broderick", "2025-12-09"),
    Document("doc:chq-6210", DK.CHEQUE, "6210", "party:lumenvet", "2025-12-10"),
    Document("doc:chq-6211", DK.CHEQUE, "6211", "party:federal-revenue", "2025-12-15"),
    Document("doc:chq-6212", DK.CHEQUE, "6212", "party:solvang", "2025-12-16"),
    Document("doc:chq-6213", DK.CHEQUE, "6213", "party:fernleigh", "2025-12-18"),
    Document("doc:chq-6214", DK.CHEQUE, "6214", "party:maple-equine", "2025-12-23"),
    Document("doc:chq-6215", DK.CHEQUE, "6215", "party:achterberg", "2025-12-24"),
    Document("doc:chq-6216", DK.CHEQUE, "6216", "party:oyelaran", "2025-12-24"),
    Document("doc:chq-6217", DK.CHEQUE, "6217", "party:tremblay", "2025-12-24"),
    # the clients' own checks, taken at the front desk
    Document("doc:chq-2218", DK.CHEQUE, "2218", "party:bramblewood", "2025-12-09"),
    Document("doc:chq-2287", DK.CHEQUE, "2287", "party:hollybrook", "2025-12-30"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # November 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-11", "2025-11-03", "party:kilbride", D("2850.00"),
                   cheque("doc:chq-4171", "2025-11-06"), "November rent, check 4171"),
    ExpensePayment("event:software-2025-11", "2025-11-04", "party:cloudpaw", D("178.50"),
                   card("2025-11-04"), "Practice management software subscription, November"),
    Purchase("event:pi-5128-purchase", "2025-11-04", "party:fernleigh", "doc:pi-5128", D("1156.30"),
             "Purchase invoice PI-5128 received, haematology reagents and test kits"),
    CustomerReceipt("event:si-7304-receipt", "2025-11-06", "party:hollybrook", "doc:si-7304", D("2675.00"),
                    ach_in("2025-11-06"), "Client payment settling SI-7304"),
    ExpensePayment("event:repairs-2025-11", "2025-11-06", "party:ashgrove", D("142.90"),
                   card("2025-11-06"), "Autoclave door gasket replacement"),
    ExpensePayment("event:ic-funding-2025-11", "2025-11-07", "party:maple-equine", D("6000.00"),
                   cheque("doc:chq-6201", "2025-11-12"),
                   "Working capital advance to Maple Street Equine Services LLC, check 6201"),
    ExpensePayment("event:telecom-2025-11", "2025-11-10", "party:orbitline", D("149.83"),
                   card("2025-11-10"), "Clinic phone lines and internet, November"),
    ExpensePayment("event:claim-broderick-2025-11", "2025-11-11", "party:broderick", D("358.20"),
                   cheque("doc:chq-6202", "2025-11-14"), "Expense claim, relief cover mileage for October farm visits, check 6202"),
    Purchase("event:pi-5131-purchase", "2025-11-12", "party:corbett", "doc:pi-5131", D("2486.35"),
             "Purchase invoice PI-5131 received, vaccines and dispensary stock"),
    ExpensePayment("event:fuel-2025-11", "2025-11-12", "party:summerlee", D("188.14"),
                   card("2025-11-12"), "Fuel for the practice vehicle"),
    VendorPayment("event:pi-5117-payment", "2025-11-13", "party:corbett", "doc:pi-5117", D("2913.40"),
                  ach_out("2025-11-13"), "Payment of purchase invoice PI-5117"),
    ExpensePayment("event:payroll-tax-2025-11", "2025-11-14", "party:federal-revenue", D("2087.55"),
                   cheque("doc:chq-6203", "2025-11-18"), "Remittance of October payroll withholdings, check 6203"),
    Prepayment("event:insurance-2025-12-prepaid", "2025-11-14", "party:shieldstone", D("612.40"),
               cheque("doc:chq-4172", "2025-11-19"), "2025-12", "Practice insurance premium for December, check 4172"),
    ExpensePayment("event:office-2025-11", "2025-11-17", "party:paperbark", D("63.29"),
                   card("2025-11-17"), "Reception stationery and printer paper"),
    Sale("event:si-7311-sale", "2025-11-18", "party:tallgrass", "doc:si-7311", D("3180.00"), D("0.07"), D("1030.00"),
         "Sale SI-7311, autumn herd health visit and dispensed wormers", "Cost of drugs and consumables on SI-7311"),
    VendorPayment("event:pi-5128-payment", "2025-11-19", "party:fernleigh", "doc:pi-5128", D("1156.30"),
                  cheque("doc:chq-6204", "2025-11-24"), "Payment of purchase invoice PI-5128, check 6204"),
    ExpensePayment("event:sales-tax-2025-10-filing", "2025-11-20", "party:state-revenue", D("611.45"),
                   card("2025-11-20"), "October sales tax return, paid online"),
    Sale("event:si-7313-sale", "2025-11-24", "party:bramblewood", "doc:si-7313", D("960.00"), D("0.07"), D("305.00"),
         "Sale SI-7313, intake examinations and vaccinations", "Cost of drugs and consumables on SI-7313"),
    ExpensePayment("event:payroll-achterberg-2025-11", "2025-11-25", "party:achterberg", D("4862.17"),
                   cheque("doc:chq-6205", "2025-11-26"), "November net pay, check 6205"),
    ExpensePayment("event:payroll-oyelaran-2025-11", "2025-11-25", "party:oyelaran", D("3115.48"),
                   cheque("doc:chq-6206", "2025-11-27"), "November net pay, check 6206"),
    ExpensePayment("event:payroll-tremblay-2025-11", "2025-11-25", "party:tremblay", D("2471.93"),
                   cheque("doc:chq-6207", "2025-11-28"), "November net pay, check 6207"),
    Purchase("event:pi-5136-purchase", "2025-11-26", "party:corbett", "doc:pi-5136", D("1742.60"),
             "Purchase invoice PI-5136 received, anaesthetics and suture stock"),
    BankFee("event:fee-2025-11", "2025-11-28", D("46.50"), "Monthly service charge and item fees"),
    # December 2025: the task period
    ExpensePayment("event:rent-2025-12", "2025-12-01", "party:kilbride", D("3187.25"),
                   cheque("doc:chq-4173", "2025-12-04"), "December rent and 2025 common-area charge true-up, check 4173"),
    ExpensePayment("event:software-2025-12", "2025-12-02", "party:cloudpaw", D("214.20"),
                   card("2025-12-02"), "Practice management software subscription, December, third user added"),
    Sale("event:si-7318-sale", "2025-12-02", "party:hollybrook", "doc:si-7318", D("1940.00"), D("0.07"), D("610.00"),
         "Sale SI-7318, kennel vaccination round and flea treatments", "Cost of drugs and consumables on SI-7318"),
    ExpensePayment("event:ic-funding-2025-12-03", "2025-12-03", "party:maple-equine", D("5000.00"),
                   cheque("doc:chq-6208", "2025-12-08"),
                   "Working capital advance to Maple Street Equine Services LLC, check 6208"),
    CustomerReceipt("event:si-7311-receipt", "2025-12-03", "party:tallgrass", "doc:si-7311", D("3402.60"),
                    ach_in("2025-12-03"), "Client payment settling SI-7311"),
    Purchase("event:pi-5145-purchase", "2025-12-04", "party:fernleigh", "doc:pi-5145", D("2264.75"),
             "Purchase invoice PI-5145 received, biochemistry reagents and blood tubes"),
    ExpensePayment("event:repairs-2025-12", "2025-12-04", "party:ashgrove", D("386.75"),
                   card("2025-12-04"), "Autoclave annual service and pressure test"),
    ExpensePayment("event:fuel-2025-12-05", "2025-12-05", "party:summerlee", D("173.28"),
                   card("2025-12-05"), "Fuel for the practice vehicle"),
    Sale("event:si-7319-sale", "2025-12-05", "party:tallgrass", "doc:si-7319", D("4560.00"), D("0.07"), D("1480.00"),
         "Sale SI-7319, colic surgery and post-operative care", "Cost of drugs and consumables on SI-7319"),
    ExpensePayment("event:telecom-2025-12", "2025-12-08", "party:orbitline", D("151.09"),
                   card("2025-12-08"), "Clinic phone lines and internet, December"),
    ExpensePayment("event:claim-broderick-2025-12", "2025-12-09", "party:broderick", D("412.85"),
                   cheque("doc:chq-6209", "2025-12-12"), "Expense claim, relief cover mileage for November farm visits, check 6209"),
    CustomerReceipt("event:si-7313-receipt", "2025-12-09", "party:bramblewood", "doc:si-7313", D("1027.20"),
                    cheque("doc:chq-2218", "2025-12-17"), "Client check 2218 settling SI-7313"),
    ExpensePayment("event:equipment-2025-12", "2025-12-10", "party:lumenvet", D("7850.00"),
                   cheque("doc:chq-6210", "2025-12-16"), "Dental radiography sensor and generator, check 6210"),
    Purchase("event:pi-5142-purchase", "2025-12-10", "party:corbett", "doc:pi-5142", D("3118.72"),
             "Purchase invoice PI-5142 received, vaccines, anaesthetics and surgical consumables"),
    ExpensePayment("event:office-2025-12", "2025-12-11", "party:paperbark", D("87.42"),
                   card("2025-12-11"), "Vaccination record cards and printer toner"),
    VendorPayment("event:pi-5131-payment", "2025-12-11", "party:corbett", "doc:pi-5131", D("2486.35"),
                  ach_out("2025-12-11"), "Payment of purchase invoice PI-5131"),
    BankFee("event:fee-returned-item-2025-12", "2025-12-12", D("35.00"), "Returned item fee"),
    ExpensePayment("event:payroll-tax-2025-12", "2025-12-15", "party:federal-revenue", D("2214.36"),
                   cheque("doc:chq-6211", "2025-12-18"), "Remittance of November payroll withholdings, check 6211"),
    Prepayment("event:insurance-2026-01-prepaid", "2025-12-15", "party:shieldstone", D("648.90"),
               cheque("doc:chq-4174", "2025-12-18"), "2026-01",
               "Practice insurance premium for January at the renewal rate, check 4174"),
    ExpensePayment("event:claim-solvang-2025-12", "2025-12-16", "party:solvang", D("736.40"),
                   cheque("doc:chq-6212", "2025-12-19"), "Expense claim, practice managers conference travel and hotel, check 6212"),
    Sale("event:si-7320-sale", "2025-12-17", "party:bramblewood", "doc:si-7320", D("1265.00"), D("0.07"), D("410.00"),
         "Sale SI-7320, neutering clinic and microchipping", "Cost of drugs and consumables on SI-7320"),
    VendorPayment("event:pi-5145-payment", "2025-12-18", "party:fernleigh", "doc:pi-5145", D("2264.75"),
                  cheque("doc:chq-6213", "2025-12-23"), "Payment of purchase invoice PI-5145, check 6213"),
    Sale("event:si-7321-sale", "2025-12-18", "party:hollybrook", "doc:si-7321", D("1580.00"), D("0.07"), D("495.00"),
         "Sale SI-7321, kennel cough boosters and dental scaling", "Cost of drugs and consumables on SI-7321"),
    ExpensePayment("event:sales-tax-2025-11-filing", "2025-12-19", "party:state-revenue", D("289.80"),
                   card("2025-12-19"), "November sales tax return, paid online"),
    CustomerReceipt("event:si-7319-partial", "2025-12-19", "party:tallgrass", "doc:si-7319", D("2500.00"),
                    ach_in("2025-12-19"), "Part payment on account against SI-7319"),
    CustomerReceipt("event:si-7318-receipt", "2025-12-22", "party:hollybrook", "doc:si-7318", D("2075.80"),
                    ach_in("2025-12-22"), "Client payment settling SI-7318"),
    ExpensePayment("event:fuel-2025-12-22", "2025-12-22", "party:summerlee", D("204.61"),
                   card("2025-12-22"), "Fuel for the practice vehicle"),
    Purchase("event:pi-5148-purchase", "2025-12-22", "party:fernleigh", "doc:pi-5148", D("1917.30"),
             "Purchase invoice PI-5148 received, urinalysis strips and culture media"),
    ExpensePayment("event:ic-funding-2025-12-23", "2025-12-23", "party:maple-equine", D("4750.00"),
                   cheque("doc:chq-6214", "2025-12-29"),
                   "Working capital advance to Maple Street Equine Services LLC, check 6214"),
    VendorPayment("event:pi-5136-payment", "2025-12-23", "party:corbett", "doc:pi-5136", D("1742.60"),
                  ach_out("2025-12-23"), "Payment of purchase invoice PI-5136"),
    ExpensePayment("event:payroll-achterberg-2025-12", "2025-12-24", "party:achterberg", D("4917.62"),
                   cheque("doc:chq-6215", "2025-12-29"), "December net pay, check 6215"),
    ExpensePayment("event:payroll-oyelaran-2025-12", "2025-12-24", "party:oyelaran", D("3188.04"),
                   cheque("doc:chq-6216", "2025-12-30"), "December net pay, check 6216"),
    ExpensePayment("event:payroll-tremblay-2025-12", "2025-12-24", "party:tremblay", D("2506.31"),
                   cheque("doc:chq-6217", "2025-12-31"), "December net pay, check 6217"),
    # issued in December, cleared by the bank in January: the timing difference
    Prepayment("event:rent-2026-01-prepaid", "2025-12-29", "party:kilbride", D("2935.50"),
               cheque("doc:chq-4175", "2026-01-06"), "2026-01", "January rent prepaid at the renewed lease rate, check 4175"),
    CustomerReceipt("event:si-7320-receipt", "2025-12-30", "party:bramblewood", "doc:si-7320", D("1353.55"),
                    ach_in("2025-12-30"), "Client payment settling SI-7320"),
    # taken at the front desk in December, banked by the bank in January: the deposit in transit
    CustomerReceipt("event:si-7321-receipt", "2025-12-30", "party:hollybrook", "doc:si-7321", D("1690.60"),
                    cheque("doc:chq-2287", "2026-01-05"), "Client check 2287 settling SI-7321"),
    BankFee("event:fee-2025-12", "2025-12-31", D("51.25"), "Monthly service charge and item fees"),
)

WORLD = World(
    id="maple-2025-12",
    title="Maple Street Veterinary Clinic - FY2025",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:wattle-creek-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-11-01", D("91846.29")),
    opening=OpeningPosition("2025-12-01", (("Assets:AR", D("4429.80")), ("Assets:Inventory", D("21640.00")),
                                           ("Assets:Equipment", D("48750.00")),
                                           ("Assets:Due-From-Maple-Equine", D("6000.00")),
                                           ("Liabilities:AP", D("-4228.95")),
                                           ("Liabilities:SalesTax-Payable", D("-289.80")),
                                           ("Liabilities:PayrollTax", D("-2214.36")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

DECEMBER = Period("2025-12-01", "2025-12-31", "December 2025")

MONTH_END_CLOSE_001 = TaskSpec(
    id="month_end_close_001",
    type="bank_reconciliation",
    prompt=("December 2025 is being closed and the Wattle Creek Bank statement for the month is in. The ledger does "
            "not agree with it: the prepaid insurance, the bank charges and the client receipts all differ from "
            "what the statement shows. Correct the books under the bookkeeping policy and write the corrected "
            "ledger back to ledger.beancount."),
    period=Period("2025-12-01", "2025-12-31", "December 2025"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_insurance_prepayment", "rec:insurance-2026-01-prepaid",
                        "the statement row names the check and the insurer (CHECK 4174 SHIELDSTONE MUTUAL INSURANCE, "
                        "648.90 on 18 December) and no ledger entry matches it; vendors.csv books the insurer to "
                        "Assets:Prepayments and the prepayments section says a premium paid in December for January "
                        "cover is a prepayment, and the dates section puts the added entry on the bank's date"),
        AlterRecognition("transposed_service_charge", "rec:fee-2025-12", "transpose_digits", 1,
                         "the ledger carries the 31 December monthly service charge at 52.15 while the statement row "
                         "of the same date shows 51.25; the month-end close checklist says a mis-keyed bank charge "
                         "is re-posted with the statement's amount on the original date, to Expenses:BankFees"),
        DuplicateRecognition("duplicated_client_receipt", "rec:si-7311-receipt",
                             "the ledger carries the 3 December ACH receipt of 3402.60 from Tallgrass Equestrian "
                             "Centre for SI-7311 twice and the statement shows one ACH IN row with that reference; "
                             "the month-end close checklist says to remove one copy and leave the other as it was"),
    )),
)

BANK_RECON_MAPLE = TaskSpec(
    id="bank_recon_maple",
    type="bank_reconciliation",
    prompt=("Please reconcile the clinic's Wattle Creek Bank checking account for December 2025. The statement "
            "is in the bundle with the November archive. Tie the ledger out to the statement's closing balance: "
            "a client receipt, one of the ACH payments to the veterinary supplier and a bank charge do not agree "
            "with what the bank shows, and the rent check written on 29 December and the client check taken on "
            "30 December are timing items, not errors. Apply the bookkeeping policy to every difference and "
            "write the corrected ledger back to ledger.beancount."),
    period=DECEMBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_client_receipt", "rec:si-7318-receipt",
                        "the statement row names the payer and the invoice (ACH IN HOLLYBROOK BOARDING KENNELS, "
                        "SI-7318, 2075.80 on 22 December) and no ledger entry matches it; customers.csv maps the "
                        "kennels to Assets:AR, the ledger carries the open sale SI-7318, and the dates section puts "
                        "the added entry on the bank's date"),
        AlterRecognition("mis_keyed_supplier_payment", "rec:pi-5131-payment", "transpose_digits", 1,
                         "the ledger carries the 11 December ACH payment of PI-5131 to Corbett Veterinary Supplies "
                         "at 2846.35 while the statement row ACH OUT CORBETT VETERINARY SUPPLIES with that invoice "
                         "reference shows 2486.35, the invoice's own amount; the payment runs section says a "
                         "supplier payment keyed with a wrong amount is re-posted at the statement's amount on its "
                         "original date, to Liabilities:AP"),
        DuplicateRecognition("duplicated_returned_item_fee", "rec:fee-returned-item-2025-12",
                             "the ledger carries the 12 December returned item fee of 35.00 twice and the statement "
                             "shows one RETURNED ITEM FEE row on that date; the month-end close checklist says a "
                             "charge is agreed line by line and one copy of a doubled entry is removed"),
    )),
)

AP_PAYMENT_RUN_MAPLE = TaskSpec(
    id="ap_payment_run_maple",
    type="bank_reconciliation",
    prompt=("The December 2025 payment runs went out as planned: the two November invoices from Corbett Veterinary "
            "Supplies by ACH on the 11th and the 23rd, and the December invoice from Fernleigh Laboratory Supplies "
            "by printed check in the mid-month run. The Wattle Creek Bank statement is in and the payables ledger "
            "does not agree with it - one supplier payment is missing from the books, one was keyed with the "
            "wrong amount and one was entered twice. Agree every supplier payment on the statement to "
            "Liabilities:AP and the invoice it settles, following the payment runs section of the bookkeeping "
            "policy, and write the corrected ledger back to ledger.beancount."),
    period=DECEMBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_pi_5136_payment", "rec:pi-5136-payment",
                        "the statement row ACH OUT CORBETT VETERINARY SUPPLIES with reference PI-5136, 1742.60 on "
                        "23 December, has no ledger entry; vendors.csv books the veterinary supplier to "
                        "Assets:Inventory, the ledger carries the open purchase invoice PI-5136 for the same "
                        "amount, and the payments to suppliers and payment runs sections put a payment to an "
                        "inventory supplier to Liabilities:AP on the bank's date"),
        AlterRecognition("mis_keyed_pi_5131_payment", "rec:pi-5131-payment", "transpose_digits", 3,
                         "the ledger carries the 11 December ACH payment of PI-5131 to Corbett Veterinary Supplies "
                         "at 2483.65 while the statement row ACH OUT CORBETT VETERINARY SUPPLIES with reference "
                         "PI-5131 shows 2486.35, the invoice's own amount; the payment runs section re-posts it at "
                         "the statement's amount on the original date"),
        DuplicateRecognition("duplicated_lab_supplier_check", "rec:pi-5145-payment",
                             "the ledger carries the 18 December check 6213 to Fernleigh Laboratory Supplies for "
                             "PI-5145 (2264.75) twice and the statement shows one CHECK 6213 FERNLEIGH LABORATORY "
                             "SUPPLIES row, on 23 December; the payment runs section says a supplier payment "
                             "posted twice loses one copy"),
    )),
)

AR_COLLECTIONS_MAPLE = TaskSpec(
    id="ar_collections_maple",
    type="bank_reconciliation",
    prompt=("Collections review for December 2025. The Wattle Creek Bank statement is in and the receivables "
            "ledger does not agree with it: Tallgrass Equestrian Centre sent a part payment on account against "
            "the colic surgery invoice that nobody applied and its remittance for the November herd health "
            "invoice was keyed with the wrong amount, and the Bramblewood Animal Rescue payment at the end of "
            "the month went in twice. The Hollybrook Boarding Kennels check handed in at the front desk on 30 "
            "December is a deposit in transit and "
            "stays as it is. Apply every receipt on the statement to the invoice it quotes under the collections "
            "section of the bookkeeping policy and write the corrected ledger back to ledger.beancount."),
    period=DECEMBER,
    plan=MutationPlan((
        OmitRecognition("unapplied_part_payment", "rec:si-7319-partial",
                        "the statement row ACH IN TALLGRASS EQUESTRIAN CENTRE with reference SI-7319, 2500.00 on "
                        "19 December, has no ledger entry; customers.csv maps the centre to Assets:AR, the ledger "
                        "carries the open sale SI-7319 for 4879.20, and the collections section applies a part "
                        "payment to the invoice it quotes for the amount received, on the bank's date"),
        AlterRecognition("mis_keyed_equestrian_remittance", "rec:si-7311-receipt", "transpose_digits", 3,
                         "the ledger carries the 3 December ACH receipt from Tallgrass Equestrian Centre for "
                         "SI-7311 at 3406.20 while the statement row with that reference shows 3402.60, the "
                         "invoice's own amount; the collections section re-posts it at the statement's amount on "
                         "the original date"),
        DuplicateRecognition("duplicated_rescue_receipt", "rec:si-7320-receipt",
                             "the ledger carries the 30 December ACH receipt of 1353.55 from Bramblewood Animal "
                             "Rescue for SI-7320 twice and the statement shows one ACH IN row with that reference; "
                             "the collections section says a receipt posted twice loses one copy"),
    )),
)

BANK_FEED_CATEGORISATION_MAPLE = TaskSpec(
    id="bank_feed_categorisation_maple",
    type="bank_reconciliation",
    prompt=("The December 2025 card spend needs categorising from the Wattle Creek Bank statement. The bookkeeper "
            "entered the fuel and the autoclave service but the software subscription and the phone bill never "
            "made it into the ledger, and the stationery purchase was keyed with the wrong amount. Book every "
            "DEBIT CARD row to the expense account the vendor master gives for that vendor, following the card "
            "spend section of the bookkeeping policy, leave the checks and ACH items alone, and write the "
            "corrected ledger back to ledger.beancount."),
    period=DECEMBER,
    plan=MutationPlan((
        OmitRecognition("uncategorised_software_subscription", "rec:software-2025-12",
                        "the statement row DEBIT CARD CLOUDPAW PRACTICE SOFTWARE, 214.20 on 2 December, has no "
                        "ledger entry; vendors.csv gives the vendor Expenses:Software as its default account and "
                        "the card spend section books a card row to that account on the bank's date"),
        OmitRecognition("uncategorised_phone_bill", "rec:telecom-2025-12",
                        "the statement row DEBIT CARD ORBITLINE TELECOM, 151.09 on 8 December, has no ledger entry; "
                        "vendors.csv gives the vendor Expenses:Telecom as its default account and the card spend "
                        "section books a card row to that account on the bank's date"),
        AlterRecognition("mis_keyed_stationery", "rec:office-2025-12", "transpose_digits", 0,
                         "the ledger carries the 11 December card payment to Paperbark Stationery Co at 78.42 "
                         "while the statement row DEBIT CARD PAPERBARK STATIONERY CO of the same date shows 87.42; "
                         "vendors.csv books the stationer to Expenses:Office and the entry is re-posted at the "
                         "statement's amount on the original date"),
    )),
)

EXPENSE_REPORTS_MAPLE = TaskSpec(
    id="expense_reports_maple",
    type="bank_reconciliation",
    prompt=("Two expense claims were approved and paid by printed check in December 2025: Hamish Broderick's "
            "mileage for his November relief cover and Ingrid Solvang's practice managers conference. The fuel "
            "card was used twice. The Wattle Creek Bank statement is in and the claims do not agree with it: one "
            "reimbursement check is not in the ledger, the other was entered twice, and one of the fuel card "
            "rows was keyed with the digits transposed. Bring the reimbursements and the fuel card spend into "
            "line with the statement under the employee expense claims and card spend sections of the "
            "bookkeeping policy and write the corrected ledger back to ledger.beancount."),
    period=DECEMBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_mileage_reimbursement", "rec:claim-broderick-2025-12",
                        "the statement row CHECK 6209 HAMISH BRODERICK, 412.85 on 12 December, has no ledger entry; "
                        "vendors.csv carries the claimant with the terms expense claim and Expenses:Travel as the "
                        "default account, and the employee expense claims section books a reimbursement check to "
                        "that account, on the bank's date when the books do not carry it"),
        DuplicateRecognition("duplicated_conference_reimbursement", "rec:claim-solvang-2025-12",
                             "the ledger carries the 16 December reimbursement check 6212 to Ingrid Solvang for "
                             "736.40 twice and the statement shows one CHECK 6212 INGRID SOLVANG row; one copy is "
                             "removed and the other left as it was"),
        AlterRecognition("transposed_fuel_card_row", "rec:fuel-2025-12-05", "transpose_digits", 1,
                         "the ledger carries the 5 December card payment to Summerlee Fuel Cards at 137.28 while "
                         "the statement row DEBIT CARD SUMMERLEE FUEL CARDS of the same date shows 173.28; "
                         "vendors.csv books the fuel card to Expenses:Vehicle and the entry is re-posted at the "
                         "statement's amount on the original date"),
    )),
)

PAYROLL_MAPLE = TaskSpec(
    id="payroll_maple",
    type="bank_reconciliation",
    prompt=("December 2025 payroll reconciliation. The three net pay checks were printed on 24 December and the "
            "November withholdings were remitted to the Federal Revenue Service by check on the 15th. The Wattle "
            "Creek Bank statement is in and the payroll entries do not agree with it: one employee's net pay "
            "check and the remittance check are missing from the ledger, and another employee's check was keyed "
            "with the wrong amount. Agree every payroll check on the statement to Expenses:Salaries and the "
            "remittance to Liabilities:PayrollTax under the payroll section of the bookkeeping policy, and write "
            "the corrected ledger back to ledger.beancount."),
    period=DECEMBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_net_pay_check", "rec:payroll-tremblay-2025-12",
                        "the statement row CHECK 6217 FIONA TREMBLAY, 2506.31 on 31 December, has no ledger entry; "
                        "vendors.csv carries the employee with the terms monthly payroll and Expenses:Salaries as "
                        "the default account, and the payroll section books a net pay check to that account, on "
                        "the bank's date when the books do not carry it"),
        AlterRecognition("mis_keyed_net_pay_check", "rec:payroll-oyelaran-2025-12", "transpose_digits", 1,
                         "the ledger carries the 24 December net pay check 6216 to Marcus Oyelaran at 3818.04 "
                         "while the statement row CHECK 6216 MARCUS OYELARAN shows 3188.04; the payroll section "
                         "books the check to Expenses:Salaries and the entry is re-posted at the statement's "
                         "amount on the original date"),
        OmitRecognition("unrecorded_withholdings_remittance", "rec:payroll-tax-2025-12",
                        "the statement row CHECK 6211 FEDERAL REVENUE SERVICE, 2214.36 on 18 December, has no "
                        "ledger entry; vendors.csv gives the revenue service Liabilities:PayrollTax as its default "
                        "account and the payroll section books a remittance to that account, on the bank's date "
                        "when the books do not carry it"),
    )),
)

SALES_TAX_REMITTANCE_MAPLE = TaskSpec(
    id="sales_tax_remittance_maple",
    type="bank_reconciliation",
    prompt=("The November sales tax return was filed with the State Revenue Department and paid online by card "
            "on 19 December 2025, and the December statement from Wattle Creek Bank is now in. The remittance "
            "was never booked against Liabilities:SalesTax-Payable, one of the client receipts is in the ledger "
            "at the wrong amount and the December service charge was entered twice. Correct the tax liability, "
            "the receipt and the charge under the sales tax remittance section and the rest of the bookkeeping "
            "policy, and write the corrected ledger back to ledger.beancount."),
    period=DECEMBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_sales_tax_remittance", "rec:sales-tax-2025-11-filing",
                        "the statement row DEBIT CARD STATE REVENUE DEPARTMENT, 289.80 on 19 December, has no "
                        "ledger entry; vendors.csv carries the department with the terms monthly filing and "
                        "Liabilities:SalesTax-Payable as its default account, and the sales tax remittance section "
                        "books the payment to that account on the bank's date"),
        AlterRecognition("mis_keyed_equestrian_receipt", "rec:si-7311-receipt", "transpose_digits", 0,
                         "the ledger carries the 3 December ACH receipt from Tallgrass Equestrian Centre for "
                         "SI-7311 at 4302.60 while the statement row with that reference shows 3402.60, the "
                         "invoice's own amount; the collections section re-posts it at the statement's amount on "
                         "the original date"),
        DuplicateRecognition("duplicated_service_charge", "rec:fee-2025-12",
                             "the ledger carries the 31 December monthly service charge of 51.25 twice and the "
                             "statement shows one MONTHLY SERVICE CHARGE AND ITEM FEES row on that date; the "
                             "month-end close checklist removes one copy"),
    )),
)

FIXED_ASSETS_MAPLE = TaskSpec(
    id="fixed_assets_maple",
    type="bank_reconciliation",
    prompt=("The dental radiography sensor and generator from Lumenvet Imaging Systems were delivered and paid "
            "for by printed check in December 2025, and the autoclave had its annual service on the card. The "
            "Wattle Creek Bank statement is in and the equipment side of the ledger does not agree with it: the "
            "equipment check was never capitalised, the autoclave service was keyed with the wrong amount, and "
            "the returned item fee the bank charged on the 12th is not in the books. Capitalise what the "
            "equipment section of the bookkeeping policy says to capitalise, expense what it says to expense, "
            "and write the corrected ledger back to ledger.beancount."),
    period=DECEMBER,
    plan=MutationPlan((
        OmitRecognition("uncapitalised_equipment_check", "rec:equipment-2025-12",
                        "the statement row CHECK 6210 LUMENVET IMAGING SYSTEMS, 7850.00 on 16 December, has no "
                        "ledger entry; vendors.csv gives the equipment supplier Assets:Equipment as its default "
                        "account and the equipment section capitalises the check to that account, on the bank's "
                        "date when the books do not carry it"),
        AlterRecognition("mis_keyed_autoclave_service", "rec:repairs-2025-12", "transpose_digits", 2,
                         "the ledger carries the 4 December card payment to Ashgrove Autoclave Repairs at 387.65 "
                         "while the statement row DEBIT CARD ASHGROVE AUTOCLAVE REPAIRS of the same date shows "
                         "386.75; vendors.csv books the repairer to Expenses:Repairs and the equipment section "
                         "says servicing is expensed, re-posted at the statement's amount on the original date"),
        OmitRecognition("unrecorded_returned_item_fee", "rec:fee-returned-item-2025-12",
                        "the statement row RETURNED ITEM FEE, 35.00 on 12 December, is a bank-initiated charge "
                        "with no counterparty and no ledger entry; the bank service charges section records it to "
                        "Expenses:BankFees on the date the bank applied it"),
    )),
)

INTERCOMPANY_TRANSFERS_MAPLE = TaskSpec(
    id="intercompany_transfers_maple",
    type="bank_reconciliation",
    prompt=("Maple Street Equine Services LLC was advanced working capital twice in December 2025, by printed "
            "checks on the 3rd and the 23rd. The Wattle Creek Bank statement is in and the intercompany balance "
            "does not agree with it: the first advance was never booked to Assets:Due-From-Maple-Equine, the "
            "second was entered twice, and the Bramblewood Animal Rescue check taken at the front desk on the "
            "9th is in the ledger at the wrong amount. Agree the due-from balance and the receipt to the "
            "statement under the intercompany balances and collections sections of the bookkeeping policy, and "
            "write the corrected ledger back to ledger.beancount."),
    period=DECEMBER,
    plan=MutationPlan((
        OmitRecognition("unrecorded_intercompany_advance", "rec:ic-funding-2025-12-03",
                        "the statement row CHECK 6208 MAPLE STREET EQUINE SERVICES LLC, 5000.00 on 8 December, has "
                        "no ledger entry; vendors.csv carries the sister company with the terms intercompany and "
                        "Assets:Due-From-Maple-Equine as its default account, and the intercompany balances "
                        "section books an advance to that account, on the bank's date when the books do not "
                        "carry it"),
        DuplicateRecognition("duplicated_intercompany_advance", "rec:ic-funding-2025-12-23",
                             "the ledger carries the 23 December advance check 6214 of 4750.00 to Maple Street "
                             "Equine Services LLC twice and the statement shows one CHECK 6214 row; one copy is "
                             "removed and the other left as it was"),
        AlterRecognition("mis_keyed_rescue_check", "rec:si-7313-receipt", "transpose_digits", 1,
                         "the ledger carries the client check 2218 from Bramblewood Animal Rescue for SI-7313, "
                         "received 9 December, at 1207.20 while the statement row CHECK 2218 BRAMBLEWOOD ANIMAL "
                         "RESCUE of 17 December shows 1027.20, the invoice's own amount; the collections section "
                         "re-posts it at the statement's amount on the original date"),
    )),
)

TASKS = {task.id: task for task in (
    MONTH_END_CLOSE_001,
    BANK_RECON_MAPLE,
    AP_PAYMENT_RUN_MAPLE,
    AR_COLLECTIONS_MAPLE,
    BANK_FEED_CATEGORISATION_MAPLE,
    EXPENSE_REPORTS_MAPLE,
    PAYROLL_MAPLE,
    SALES_TAX_REMITTANCE_MAPLE,
    FIXED_ASSETS_MAPLE,
    INTERCOMPANY_TRANSFERS_MAPLE,
)}
