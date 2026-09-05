"""Thistle & Quill Design Studio, January 2026: the irreducible facts.

This is the hand-reviewed layer. It states what happened — amounts, dates,
counterparties, documents, rails, clearing dates — and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

One month, ten tasks. The studio's January is a complete small-company
month — card spend keyed from the bank feed, two print-stock suppliers paid
on the fortnightly run, four clients collected from, the principals'
expense claims and the van's fuel, three staff paid net by check with
December's withholdings remitted, December's sales tax return paid, a
proofing printer capitalised and a workstation repaired, the Interiors
company funded twice, February's insurance premium prepaid and two bank
charges — and every task sees the same statement and the same golden
facts. Only the prompt and the planted recognitions differ from task to
task, so the workflow a task is about is the workflow whose entries it
plants.

The February rent check is not a mutation in any task: it is a check the
bank cleared on 3 February, and the January statement's projection
classifies it NOT_YET_SETTLED on its own. The client check received on
28 January and credited on 2 February is the same kind of timing
difference in the other direction.
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

POLICY_TEXT = """# Thistle & Quill Design Studio — Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, paper statement
fees, returned item fees) are recorded to `Expenses:BankFees` on the date the
bank applies them. A charge the statement shows that the books do not carry
is added on the bank's date; a charge the books carry twice for one statement
row is reduced to one entry; a charge keyed with a figure that differs from
the statement's is re-posted with the bank's figure.

## Customer receipts
Cash received from a client reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice. A deposit paid
on account of a job in progress is applied against the invoice it was raised
under in the same way, and a client who pays part of an invoice has the part
applied against that invoice, the balance staying on the account until it is
paid.

## Collections
Clients are invoiced on completion of a job and pay on their terms, by ACH
quoting the invoice number or by check. A client check is recorded on the day
it arrives at the studio, not the day the bank credits it; the studio banks
checks within a day or two of receipt. A receipt the statement shows that the
books do not carry is posted to the client's account on the bank's date. A
receipt the books carry with an amount that differs from the statement's is
re-posted with the statement's amount on its original date, and the wrong
figure is not left standing alongside it. A receipt the books carry twice for
one bank credit is reduced to one entry. Nothing is written off at the
monthly close; a short payment stays on the client's account.

## Payments to suppliers
The `default_account` a supplier carries in the vendor master is where that
supplier's purchases are booked when they arrive. It is not always where a
payment to that supplier lands, and the account itself says which it is.

Where a supplier's purchases are booked to `Assets:Inventory` — the print
stock suppliers, Linden Print Works and Wexcombe Fine Papers — the stock was
taken into that account when it was received and a payable was raised for it
at the same time, so cash paid to that supplier afterwards settles the
payable and is recorded to `Liabilities:AP`.

Where a supplier's purchases are booked to an expense account, no payable is
raised: the payment is the expense, and it is recorded to that supplier's own
`default_account` on the day it is paid, except where it is paid ahead of the
period it covers, which the prepayments section below governs.

The vendor master also carries payees that are not suppliers of goods or
services at all, and for those the `default_account` is exactly where the
payment lands: the equipment supplier (`Assets:Equipment`, the equipment
section), the group's Interiors company (the intercompany section), the
insurer (`Assets:Prepayments`, the prepayments section), the two tax
authorities (the payroll and sales tax remittance sections), the staff and
the principals (the payroll and expense claims sections). None of those
payees ever passes through `Liabilities:AP`.

## Payment runs
Print stock is bought on net 30 terms from Linden Print Works and Wexcombe
Fine Papers. Each purchase invoice is booked to `Assets:Inventory` with a
payable in `Liabilities:AP` on the invoice date. The studio settles supplier
invoices on a payment run twice a month, by ACH quoting the purchase invoice
number, or by check where the supplier has asked for one. The payment is
recorded to `Liabilities:AP` on the day it is made, one entry per invoice,
for the invoice amount. A supplier payment the statement shows that the books
do not carry is posted to `Liabilities:AP` on the bank's date; a payment the
books carry with an amount that differs from the statement's is re-posted
with the statement's amount on its original date; a payment the books carry
twice for one bank debit is reduced to one entry.

## Card spend
The studio's running costs — software subscriptions, staff travel booked
through Skylark Travel, the studio's broadband and phones, consumables, the
van's fuel and equipment repairs — are paid on the business debit card and
entered into the books from the bank feed, so a card entry carries the date
the bank shows. A card row on the statement whose vendor is in the vendor
master is booked to that vendor's `default_account` on the bank's date. A card
row the books do not carry is added, on the bank's date, to that account. A
card row the books carry with an amount that differs from the statement's has
been keyed wrongly: the entry is re-posted with the statement's amount, on the
date it was originally entered, and the wrong figure is not left standing
alongside it. A card row whose vendor is not in the vendor master is queried
with the studio manager before it is booked; it is never posted to a holding
account.

## Employee expense claims
The studio's two principals, Nell Faraday and Tobias Hartigan, are not on the
monthly payroll. They pay for client pitch travel and site visits personally
and file an expense claim with receipts at the end of each trip. Each
principal is carried in the vendor master with terms "expense claim" and
`Expenses:Travel` as the default account, which is where every claim that
principal files is booked. No payable is raised for a claim: an approved claim
is reimbursed by check and recorded to the claimant's default account on the
date the check is issued, with the claimant named as payee exactly as the
vendor master lists them. A reimbursement check the statement shows that the
books do not carry is posted to the claimant's default account on the bank's
date; a claim the books carry twice for one check is reduced to one entry;
a claim keyed with the wrong amount is re-posted with the check's amount on
its original date.

The studio van is fuelled on the business debit card at Kingfisher Fuel, and
each fill is booked from the bank feed to `Expenses:Vehicle` under the card
spend rule above. Staff on the monthly payroll do not file claims: their
travel is booked through Skylark Travel on the card.

## Payroll
The studio's three staff — Rowan Ashby, Imogen Talbot and Callum Reeve — are
paid monthly, in the last week of the month, by a check for each employee's
net pay drawn on the checking account. Each employee is carried in the vendor
master with terms "monthly payroll" and `Expenses:Salaries` as the default
account. A net pay check is recorded as one entry per employee, dated the day
the check is written, with the employee named as payee exactly as the vendor
master lists them: a debit to `Expenses:Salaries` and a credit to the
checking account for the net amount. No payable is raised for net pay ahead
of the check. A net pay check the statement shows that the books do not carry
is posted to `Expenses:Salaries` on the bank's date; a net pay check keyed
with the wrong amount is re-posted with the check's amount on its original
date; a net pay check the books carry twice is reduced to one entry.

Employee withholdings and the employer's payroll taxes are accrued to
`Liabilities:PayrollTax` by the monthly payroll journal that the payroll
bureau supplies after each close; that journal is outside the bank
reconciliation. The accrued amount is remitted to the Federal Revenue Service
by check in the following month. The Federal Revenue Service is carried in the
vendor master with terms "monthly remittance" and `Liabilities:PayrollTax` as
its default account: a payment to it is neither a purchase nor an expense, it
settles the accrued liability, and it is recorded as a debit to
`Liabilities:PayrollTax` and a credit to the checking account on the date the
check is issued.

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
client or supplier movement the ledger date is never later than the
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

The studio's contents and liability insurance is invoiced by Brackenfield
Mutual Insurance a month in advance and paid by check in the month before the
cover month. A premium paid in January for February cover is booked to
`Assets:Prepayments` on the date the check is issued and released to
`Expenses:Insurance` in February by the close journal. The insurer carries
`Assets:Prepayments` as its default account in the vendor master for exactly
this reason: every payment to the insurer is a payment in advance. No payable
is raised for a premium. A premium check the statement shows that the books
do not carry is posted to `Assets:Prepayments` on the bank's date.

## Equipment
Workstations, the proofing printer and the mounting press are bought from
Halcyon Imaging Systems, which the vendor master carries with
`Assets:Equipment` as its default account. The studio pays for equipment by
check on delivery, so the check is the whole transaction: its amount is
capitalised to `Assets:Equipment` on the date it is paid, with the supplier
as payee, and depreciation is dealt with at year end, outside the monthly
close. No payable is raised and nothing passes through `Liabilities:AP`. An
equipment check the statement shows that the books do not carry is
capitalised on the bank's date.

Ferngate Technical Services, which the vendor master carries with
`Expenses:Repairs` as its default account, services and repairs that
equipment. Its charges are maintenance, not improvements: they are paid on
the debit card and expensed to `Expenses:Repairs` on the bank's date under
the card spend rule. A repair the books carry with an amount that differs
from the statement's is re-posted with the statement's amount on its
original date.

## Intercompany balances
Thistle & Quill Interiors LLC, the group's interior fit-out company, shares
the studio's owners and is funded by the studio by check whenever its own
collections will not cover its wages and suppliers. The Interiors company is
carried in the vendor master with terms "intercompany" and
`Assets:Due-From-TQ-Interiors` as its default account. Every advance is a
debit to that account and a credit to the checking account, dated the day the
check is issued, with the Interiors company as payee. The advance is
repayable and stays on that account until it is repaid; it is never expensed,
never treated as a payable and never netted against anything else. An
advance the statement shows that the books do not carry is posted to
`Assets:Due-From-TQ-Interiors` on the bank's date; an advance the books
carry twice for one check is reduced to one entry. The balance is agreed
with the Interiors company's own books at every month end.

## Sales tax
Thistle & Quill collects sales tax from clients on design fees and on the
printed goods it supplies, and owes it to the state. Print stock bought for
resale is exempt, so no tax is recoverable on the purchase side.

## Sales tax remittance
The State Revenue Department is carried in the vendor master with terms
"monthly filing" and `Liabilities:SalesTax-Payable` as its default account.
It is not a supplier of goods or services: a payment to the department is
neither a purchase nor an expense. The return for each month is filed and
paid by check in the month that follows, for the tax collected in the month
the return covers, and the payment is recorded as a debit to
`Liabilities:SalesTax-Payable` and a credit to the checking account on the
date the check is issued. A remittance check the statement shows that the
books do not carry is posted to `Liabilities:SalesTax-Payable` on the bank's
date.

## Suspense accounts
Thistle & Quill does not operate a suspense or plug account. Every posting is
made to the account that reflects the underlying transaction.
"""

OPENED = "2024-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Studio operating checking account held at Heronsgate Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Fees and print charges receivable from clients", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Print stock and blanks held for client jobs", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Assets:Equipment", K.ASSET, "Workstations, proofing printer and mounting press at cost", OPENED, 1400),
    Account("Assets:Due-From-TQ-Interiors", K.ASSET, "Cash advanced to Thistle & Quill Interiors LLC and repayable by it", OPENED, 1500),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from clients and owed to the state", OPENED, 2100),
    Account("Liabilities:PayrollTax", K.LIABILITY, "Employee withholdings and employer payroll taxes owed to the Federal Revenue Service", OPENED, 2200),
    Account("Income:Sales", K.INCOME, "Design fees and printed goods billed to clients", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Print stock consumed on client jobs", OPENED, 5000),
    Account("Expenses:Software", K.EXPENSE, "Design software subscriptions and licences", OPENED, 5100),
    Account("Expenses:Travel", K.EXPENSE, "Travel to client sites and pitches", OPENED, 5200),
    Account("Expenses:Telecom", K.EXPENSE, "Studio broadband and phone lines", OPENED, 5300),
    Account("Expenses:Office", K.EXPENSE, "Studio consumables and presentation supplies", OPENED, 5400),
    Account("Expenses:Rent", K.EXPENSE, "Studio rent for the period", OPENED, 5500),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5600),
    Account("Expenses:Salaries", K.EXPENSE, "Net pay of the studio's staff", OPENED, 5700),
    Account("Expenses:Vehicle", K.EXPENSE, "Fuel and running costs of the studio van", OPENED, 5800),
    Account("Expenses:Repairs", K.EXPENSE, "Servicing and repair of studio equipment", OPENED, 5900),
    Account("Expenses:Insurance", K.EXPENSE, "Studio contents and liability insurance for the period", OPENED, 6000),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:marram-hotels", "Marram Coastal Hotels", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:harrowgate-brewing", "Harrowgate Brewing Co", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:linden-print", "Linden Print Works", R.VENDOR, 3, "net 30", "Assets:Inventory"),
    Party("party:mossgate", "Mossgate Properties", R.VENDOR, 4, "due on receipt", "Expenses:Rent"),
    Party("party:pixelforge", "Pixelforge Software", R.VENDOR, 5, "due on receipt", "Expenses:Software"),
    Party("party:skylark-travel", "Skylark Travel", R.VENDOR, 6, "due on receipt", "Expenses:Travel"),
    Party("party:corvid-telecom", "Corvid Telecom", R.VENDOR, 7, "due on receipt", "Expenses:Telecom"),
    Party("party:paperbark", "Paperbark Stationery", R.VENDOR, 8, "due on receipt", "Expenses:Office"),
    Party("party:heronsgate-bank", "Heronsgate Bank", R.BANK, 9),
    Party("party:saltire-coffee", "Saltire Coffee Roasters", R.CUSTOMER, 10, "net 30", "Assets:AR"),
    Party("party:fenwick-garden", "Fenwick Garden Centre", R.CUSTOMER, 11, "net 45", "Assets:AR"),
    Party("party:wexcombe-papers", "Wexcombe Fine Papers", R.VENDOR, 12, "net 30", "Assets:Inventory"),
    Party("party:rowan-ashby", "Rowan Ashby", R.VENDOR, 13, "monthly payroll", "Expenses:Salaries"),
    Party("party:imogen-talbot", "Imogen Talbot", R.VENDOR, 14, "monthly payroll", "Expenses:Salaries"),
    Party("party:callum-reeve", "Callum Reeve", R.VENDOR, 15, "monthly payroll", "Expenses:Salaries"),
    Party("party:federal-revenue", "Federal Revenue Service", R.VENDOR, 16, "monthly remittance", "Liabilities:PayrollTax"),
    Party("party:state-revenue", "State Revenue Department", R.VENDOR, 17, "monthly filing", "Liabilities:SalesTax-Payable"),
    Party("party:nell-faraday", "Nell Faraday", R.VENDOR, 18, "expense claim", "Expenses:Travel"),
    Party("party:tobias-hartigan", "Tobias Hartigan", R.VENDOR, 19, "expense claim", "Expenses:Travel"),
    Party("party:kingfisher-fuel", "Kingfisher Fuel", R.VENDOR, 20, "due on receipt", "Expenses:Vehicle"),
    Party("party:halcyon-imaging", "Halcyon Imaging Systems", R.VENDOR, 21, "due on receipt", "Assets:Equipment"),
    Party("party:ferngate-technical", "Ferngate Technical Services", R.VENDOR, 22, "due on receipt", "Expenses:Repairs"),
    Party("party:tq-interiors", "Thistle & Quill Interiors LLC", R.VENDOR, 23, "intercompany", "Assets:Due-From-TQ-Interiors"),
    Party("party:brackenfield-insurance", "Brackenfield Mutual Insurance", R.VENDOR, 24, "due on receipt", "Assets:Prepayments"),
)

DOCUMENTS = (
    # sales invoices
    Document("doc:si-0414", DK.SALES_INVOICE, "SI-0414", "party:harrowgate-brewing", "2025-10-28", D("3780.00")),
    Document("doc:si-0419", DK.SALES_INVOICE, "SI-0419", "party:marram-hotels", "2025-11-20", D("5940.00")),
    Document("doc:si-0421", DK.SALES_INVOICE, "SI-0421", "party:saltire-coffee", "2025-11-24", D("2268.00")),
    Document("doc:si-0423", DK.SALES_INVOICE, "SI-0423", "party:fenwick-garden", "2025-11-26", D("1944.00")),
    Document("doc:si-0424", DK.SALES_INVOICE, "SI-0424", "party:fenwick-garden", "2025-12-09", D("3456.00")),
    Document("doc:si-0425", DK.SALES_INVOICE, "SI-0425", "party:saltire-coffee", "2025-12-18", D("2700.00")),
    Document("doc:si-0426", DK.SALES_INVOICE, "SI-0426", "party:saltire-coffee", "2026-01-05", D("1998.00")),
    Document("doc:si-0427", DK.SALES_INVOICE, "SI-0427", "party:harrowgate-brewing", "2026-01-12", D("4590.00")),
    Document("doc:si-0428", DK.SALES_INVOICE, "SI-0428", "party:marram-hotels", "2026-01-19", D("7344.00")),
    Document("doc:si-0429", DK.SALES_INVOICE, "SI-0429", "party:fenwick-garden", "2026-01-27", D("3186.00")),
    # purchase invoices (the studio's own register numbers, one series across suppliers)
    Document("doc:pi-0772", DK.PURCHASE_INVOICE, "PI-0772", "party:linden-print", "2025-11-18", D("1260.00")),
    Document("doc:pi-0776", DK.PURCHASE_INVOICE, "PI-0776", "party:wexcombe-papers", "2025-11-24", D("842.30")),
    Document("doc:pi-0781", DK.PURCHASE_INVOICE, "PI-0781", "party:linden-print", "2025-12-15", D("1485.00")),
    Document("doc:pi-0785", DK.PURCHASE_INVOICE, "PI-0785", "party:wexcombe-papers", "2025-12-19", D("1138.75")),
    Document("doc:pi-0787", DK.PURCHASE_INVOICE, "PI-0787", "party:linden-print", "2025-12-22", D("1732.50")),
    Document("doc:pi-0788", DK.PURCHASE_INVOICE, "PI-0788", "party:wexcombe-papers", "2025-12-30", D("964.15")),
    Document("doc:pi-0790", DK.PURCHASE_INVOICE, "PI-0790", "party:linden-print", "2026-01-21", D("940.00")),
    Document("doc:pi-0793", DK.PURCHASE_INVOICE, "PI-0793", "party:wexcombe-papers", "2026-01-27", D("655.80")),
    # the studio's checks, one book, in the order they were written
    Document("doc:chq-1039", DK.CHEQUE, "1039", "party:mossgate", "2025-12-01"),
    Document("doc:chq-1040", DK.CHEQUE, "1040", "party:nell-faraday", "2025-12-12"),
    Document("doc:chq-1041", DK.CHEQUE, "1041", "party:brackenfield-insurance", "2025-12-15"),
    Document("doc:chq-1042", DK.CHEQUE, "1042", "party:federal-revenue", "2025-12-16"),
    Document("doc:chq-1043", DK.CHEQUE, "1043", "party:state-revenue", "2025-12-18"),
    Document("doc:chq-1044", DK.CHEQUE, "1044", "party:tq-interiors", "2025-12-22"),
    Document("doc:chq-1045", DK.CHEQUE, "1045", "party:rowan-ashby", "2025-12-29"),
    Document("doc:chq-1046", DK.CHEQUE, "1046", "party:imogen-talbot", "2025-12-29"),
    Document("doc:chq-1047", DK.CHEQUE, "1047", "party:callum-reeve", "2025-12-29"),
    Document("doc:chq-1048", DK.CHEQUE, "1048", "party:mossgate", "2026-01-02"),
    Document("doc:chq-1049", DK.CHEQUE, "1049", "party:wexcombe-papers", "2026-01-06"),
    Document("doc:chq-1050", DK.CHEQUE, "1050", "party:tq-interiors", "2026-01-08"),
    Document("doc:chq-1051", DK.CHEQUE, "1051", "party:halcyon-imaging", "2026-01-09"),
    Document("doc:chq-1052", DK.CHEQUE, "1052", "party:nell-faraday", "2026-01-13"),
    Document("doc:chq-1053", DK.CHEQUE, "1053", "party:federal-revenue", "2026-01-14"),
    Document("doc:chq-1054", DK.CHEQUE, "1054", "party:state-revenue", "2026-01-16"),
    Document("doc:chq-1055", DK.CHEQUE, "1055", "party:tq-interiors", "2026-01-20"),
    Document("doc:chq-1056", DK.CHEQUE, "1056", "party:brackenfield-insurance", "2026-01-22"),
    Document("doc:chq-1057", DK.CHEQUE, "1057", "party:tobias-hartigan", "2026-01-23"),
    Document("doc:chq-1058", DK.CHEQUE, "1058", "party:rowan-ashby", "2026-01-28"),
    Document("doc:chq-1059", DK.CHEQUE, "1059", "party:imogen-talbot", "2026-01-28"),
    Document("doc:chq-1060", DK.CHEQUE, "1060", "party:callum-reeve", "2026-01-28"),
    Document("doc:chq-1061", DK.CHEQUE, "1061", "party:mossgate", "2026-01-29"),
    # a client's own check, numbered from the client's book
    Document("doc:chq-saltire-20417", DK.CHEQUE, "20417", "party:saltire-coffee", "2026-01-28"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # December 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-12", "2025-12-01", "party:mossgate", D("2400.00"),
                   cheque("doc:chq-1039", "2025-12-04"), "December studio rent"),
    VendorPayment("event:pi-0772-payment", "2025-12-03", "party:linden-print", "doc:pi-0772", D("1260.00"),
                  ach_out("2025-12-03"), "Payment of purchase invoice PI-0772"),
    ExpensePayment("event:office-2025-12", "2025-12-04", "party:paperbark", D("87.45"),
                   card("2025-12-04"), "Printer toner and copier paper"),
    CustomerReceipt("event:si-0414-receipt", "2025-12-05", "party:harrowgate-brewing", "doc:si-0414", D("3780.00"),
                    ach_in("2025-12-05"), "Customer payment for SI-0414"),
    ExpensePayment("event:fuel-2025-12", "2025-12-08", "party:kingfisher-fuel", D("61.70"),
                   card("2025-12-08"), "Van fuel"),
    ExpensePayment("event:software-2025-12", "2025-12-09", "party:pixelforge", D("189.00"),
                   card("2025-12-09"), "Design suite subscription - December"),
    CustomerReceipt("event:si-0421-receipt", "2025-12-10", "party:saltire-coffee", "doc:si-0421", D("2268.00"),
                    ach_in("2025-12-10"), "Customer payment for SI-0421"),
    VendorPayment("event:pi-0776-payment", "2025-12-11", "party:wexcombe-papers", "doc:pi-0776", D("842.30"),
                  ach_out("2025-12-11"), "Payment of purchase invoice PI-0776"),
    ExpensePayment("event:faraday-claim-2025-12", "2025-12-12", "party:nell-faraday", D("212.80"),
                   cheque("doc:chq-1040", "2025-12-16"), "Expense claim - Harrowgate label press check, check 1040"),
    Prepayment("event:insurance-2026-01-prepaid", "2025-12-15", "party:brackenfield-insurance", D("472.50"),
               cheque("doc:chq-1041", "2025-12-18"), "2026-01", "Studio insurance premium for January, check 1041"),
    ExpensePayment("event:withholding-2025-11", "2025-12-16", "party:federal-revenue", D("1842.60"),
                   cheque("doc:chq-1042", "2025-12-19"), "November payroll withholdings remitted, check 1042"),
    ExpensePayment("event:telecom-2025-12", "2025-12-17", "party:corvid-telecom", D("148.20"),
                   card("2025-12-17"), "Studio broadband and phones - December"),
    ExpensePayment("event:sales-tax-2025-11-remit", "2025-12-18", "party:state-revenue", D("664.40"),
                   cheque("doc:chq-1043", "2025-12-22"), "November sales tax return, check 1043"),
    ExpensePayment("event:repairs-2025-12", "2025-12-19", "party:ferngate-technical", D("145.75"),
                   card("2025-12-19"), "Annual service of the mounting press"),
    ExpensePayment("event:interco-2025-12", "2025-12-22", "party:tq-interiors", D("4000.00"),
                   cheque("doc:chq-1044", "2025-12-24"), "Advance to Interiors for December wages, check 1044"),
    CustomerReceipt("event:si-0423-receipt", "2025-12-23", "party:fenwick-garden", "doc:si-0423", D("1944.00"),
                    ach_in("2025-12-23"), "Customer payment for SI-0423"),
    ExpensePayment("event:pay-ashby-2025-12", "2025-12-29", "party:rowan-ashby", D("3184.20"),
                   cheque("doc:chq-1045", "2025-12-31"), "December net pay, check 1045"),
    ExpensePayment("event:pay-talbot-2025-12", "2025-12-29", "party:imogen-talbot", D("2736.45"),
                   cheque("doc:chq-1046", "2025-12-31"), "December net pay, check 1046"),
    ExpensePayment("event:pay-reeve-2025-12", "2025-12-29", "party:callum-reeve", D("2418.90"),
                   cheque("doc:chq-1047", "2025-12-31"), "December net pay, check 1047"),
    BankFee("event:fee-2025-12", "2025-12-31", D("22.00"), "Monthly account service charge"),
    # January 2026: the task period
    ExpensePayment("event:rent-2026-01", "2026-01-02", "party:mossgate", D("2520.00"),
                   cheque("doc:chq-1048", "2026-01-07"), "January studio rent at the uplifted lease rate"),
    Sale("event:si-0426-sale", "2026-01-05", "party:saltire-coffee", "doc:si-0426", D("1850.00"), D("0.08"), D("410.00"),
         "Seasonal blend packaging and shelf talkers SI-0426", "Print stock issued on SI-0426"),
    VendorPayment("event:pi-0785-payment", "2026-01-06", "party:wexcombe-papers", "doc:pi-0785", D("1138.75"),
                  cheque("doc:chq-1049", "2026-01-12"), "Payment of purchase invoice PI-0785, check 1049"),
    ExpensePayment("event:software-2026-01", "2026-01-07", "party:pixelforge", D("283.50"),
                   card("2026-01-07"), "Design suite subscription - January (third seat added)"),
    ExpensePayment("event:fuel-2026-01-a", "2026-01-08", "party:kingfisher-fuel", D("68.40"),
                   card("2026-01-08"), "Van fuel"),
    CustomerReceipt("event:si-0419-receipt", "2026-01-08", "party:marram-hotels", "doc:si-0419", D("5940.00"),
                    ach_in("2026-01-08"), "Customer payment for SI-0419"),
    ExpensePayment("event:interco-2026-01-a", "2026-01-08", "party:tq-interiors", D("1250.00"),
                   cheque("doc:chq-1050", "2026-01-12"), "Advance to Interiors for the Marram fit-out deposit, check 1050"),
    ExpensePayment("event:equipment-2026-01", "2026-01-09", "party:halcyon-imaging", D("3865.00"),
                   cheque("doc:chq-1051", "2026-01-14"), "Large-format proofing printer, check 1051"),
    BankFee("event:fee-statement-2026-01", "2026-01-12", D("31.50"), "Paper statement fee"),
    Sale("event:si-0427-sale", "2026-01-12", "party:harrowgate-brewing", "doc:si-0427", D("4250.00"), D("0.08"), D("380.00"),
         "Brand identity and label range SI-0427", "Print stock issued on SI-0427"),
    ExpensePayment("event:faraday-claim-2026-01", "2026-01-13", "party:nell-faraday", D("341.60"),
                   cheque("doc:chq-1052", "2026-01-16"), "Expense claim - Fenwick pitch travel and hotel, check 1052"),
    ExpensePayment("event:office-2026-01", "2026-01-14", "party:paperbark", D("264.90"),
                   card("2026-01-14"), "Presentation boards and mounting supplies"),
    ExpensePayment("event:withholding-2025-12", "2026-01-14", "party:federal-revenue", D("1927.35"),
                   cheque("doc:chq-1053", "2026-01-20"), "December payroll withholdings remitted, check 1053"),
    CustomerReceipt("event:si-0424-receipt", "2026-01-14", "party:fenwick-garden", "doc:si-0424", D("1728.00"),
                    ach_in("2026-01-14"), "Part payment against SI-0424"),
    ExpensePayment("event:travel-2026-01", "2026-01-15", "party:skylark-travel", D("527.40"),
                   card("2026-01-15"), "Rail fares and hotel - Marram site visit"),
    VendorPayment("event:pi-0781-payment", "2026-01-15", "party:linden-print", "doc:pi-0781", D("1485.00"),
                  ach_out("2026-01-15"), "Payment of purchase invoice PI-0781"),
    ExpensePayment("event:sales-tax-2025-12-remit", "2026-01-16", "party:state-revenue", D("712.80"),
                   cheque("doc:chq-1054", "2026-01-21"), "December sales tax return, check 1054"),
    CustomerReceipt("event:si-0425-receipt", "2026-01-16", "party:saltire-coffee", "doc:si-0425", D("2700.00"),
                    ach_in("2026-01-16"), "Customer payment settling SI-0425"),
    ExpensePayment("event:telecom-2026-01", "2026-01-19", "party:corvid-telecom", D("151.35"),
                   card("2026-01-19"), "Studio broadband and phones - January"),
    Sale("event:si-0428-sale", "2026-01-19", "party:marram-hotels", "doc:si-0428", D("6800.00"), D("0.08"), D("910.00"),
         "Spring campaign design and print SI-0428", "Print stock issued on SI-0428"),
    ExpensePayment("event:interco-2026-01-b", "2026-01-20", "party:tq-interiors", D("3500.00"),
                   cheque("doc:chq-1055", "2026-01-23"), "Advance to Interiors for January wages, check 1055"),
    VendorPayment("event:pi-0787-payment", "2026-01-20", "party:linden-print", "doc:pi-0787", D("1732.50"),
                  ach_out("2026-01-20"), "Payment of purchase invoice PI-0787"),
    ExpensePayment("event:repairs-2026-01", "2026-01-20", "party:ferngate-technical", D("218.40"),
                   card("2026-01-20"), "Workstation repair - replacement power supply"),
    Purchase("event:pi-0790-receipt", "2026-01-21", "party:linden-print", "doc:pi-0790", D("940.00"),
             "Purchase invoice PI-0790 received - print stock"),
    ExpensePayment("event:fuel-2026-01-b", "2026-01-21", "party:kingfisher-fuel", D("74.15"),
                   card("2026-01-21"), "Van fuel"),
    Prepayment("event:insurance-2026-02-prepaid", "2026-01-22", "party:brackenfield-insurance", D("486.25"),
               cheque("doc:chq-1056", "2026-01-27"), "2026-02",
               "Studio insurance premium for February at the renewal rate, check 1056"),
    VendorPayment("event:pi-0788-payment", "2026-01-22", "party:wexcombe-papers", "doc:pi-0788", D("964.15"),
                  ach_out("2026-01-22"), "Payment of purchase invoice PI-0788"),
    ExpensePayment("event:software-licence-2026-01", "2026-01-23", "party:pixelforge", D("96.00"),
                   card("2026-01-23"), "Stock image licence pack"),
    CustomerReceipt("event:si-0428-deposit", "2026-01-23", "party:marram-hotels", "doc:si-0428", D("3672.00"),
                    ach_in("2026-01-23"), "Deposit of half the invoice against SI-0428"),
    ExpensePayment("event:hartigan-claim-2026-01", "2026-01-23", "party:tobias-hartigan", D("278.15"),
                   cheque("doc:chq-1057", "2026-01-28"), "Expense claim - Saltire roastery visit mileage and meals, check 1057"),
    CustomerReceipt("event:si-0427-receipt", "2026-01-26", "party:harrowgate-brewing", "doc:si-0427", D("4590.00"),
                    ach_in("2026-01-26"), "Customer payment settling SI-0427"),
    Sale("event:si-0429-sale", "2026-01-27", "party:fenwick-garden", "doc:si-0429", D("2950.00"), D("0.08"), D("780.00"),
         "Spring catalogue and plant labels SI-0429", "Print stock issued on SI-0429"),
    Purchase("event:pi-0793-receipt", "2026-01-27", "party:wexcombe-papers", "doc:pi-0793", D("655.80"),
             "Purchase invoice PI-0793 received - coated stock"),
    ExpensePayment("event:pay-ashby-2026-01", "2026-01-28", "party:rowan-ashby", D("3247.60"),
                   cheque("doc:chq-1058", "2026-01-30"), "January net pay after the new-year review, check 1058"),
    ExpensePayment("event:pay-talbot-2026-01", "2026-01-28", "party:imogen-talbot", D("2791.30"),
                   cheque("doc:chq-1059", "2026-01-30"), "January net pay after the new-year review, check 1059"),
    ExpensePayment("event:pay-reeve-2026-01", "2026-01-28", "party:callum-reeve", D("2466.85"),
                   cheque("doc:chq-1060", "2026-01-30"), "January net pay after the new-year review, check 1060"),
    # received in January, credited by the bank in February: the deposit in transit
    CustomerReceipt("event:si-0426-receipt", "2026-01-28", "party:saltire-coffee", "doc:si-0426", D("1998.00"),
                    cheque("doc:chq-saltire-20417", "2026-02-02"), "Client check 20417 settling SI-0426"),
    # issued in January, cleared by the bank in February: the timing difference
    Prepayment("event:rent-2026-02-prepaid", "2026-01-29", "party:mossgate", D("2520.00"),
               cheque("doc:chq-1061", "2026-02-03"), "2026-02", "February rent prepaid, check 1061"),
    BankFee("event:fee-2026-01", "2026-01-30", D("25.00"), "Monthly account service charge"),
)

WORLD = World(
    id="thistle-2026-01",
    title="Thistle & Quill Design Studio - FY2026",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:heronsgate-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-12-01", D("44800.00")),
    opening=OpeningPosition("2026-01-01", (("Assets:AR", D("13650.00")), ("Assets:Inventory", D("6800.00")),
                                           ("Assets:Prepayments", D("472.50")),
                                           ("Assets:Equipment", D("18650.00")),
                                           ("Assets:Due-From-TQ-Interiors", D("4000.00")),
                                           ("Liabilities:AP", D("-5320.40")),
                                           ("Liabilities:SalesTax-Payable", D("-712.80")),
                                           ("Liabilities:PayrollTax", D("-1927.35")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

PERIOD = Period("2026-01-01", "2026-01-31", "January 2026")

BANK_FEED_CATEGORISATION_001 = TaskSpec(
    id="bank_feed_categorisation_001",
    type="bank_reconciliation",
    prompt=("The January bank feed for the studio checking account has been downloaded. Several card transactions "
            "never reached the books and one was keyed wrongly. Categorise every feed line under the bookkeeping "
            "policy, bring the ledger into agreement with the statement, and write the corrected ledger back to "
            "ledger.beancount."),
    period=Period("2026-01-01", "2026-01-31", "January 2026"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_software_card", "rec:software-2026-01",
                        "the statement row DEBIT CARD PIXELFORGE SOFTWARE of 283.50 on 2026-01-07 answers no ledger "
                        "entry; vendors.csv maps Pixelforge Software to Expenses:Software and policy.md's Card spend "
                        "section adds a missing card row to the vendor's default account on the bank's date"),
        OmitRecognition("unrecorded_travel_card", "rec:travel-2026-01",
                        "the statement row DEBIT CARD SKYLARK TRAVEL of 527.40 on 2026-01-15 answers no ledger "
                        "entry; vendors.csv maps Skylark Travel to Expenses:Travel and policy.md's Card spend "
                        "section adds a missing card row to the vendor's default account on the bank's date"),
        AlterRecognition("miskeyed_office_card", "rec:office-2026-01", "drop_digit", 1,
                         "the statement row DEBIT CARD PAPERBARK STATIONERY of 264.90 on 2026-01-14 answers the "
                         "ledger's same-day Paperbark Stationery entry of 24.90 and no other; vendors.csv maps "
                         "Paperbark Stationery to Expenses:Office and policy.md's Card spend section re-posts a "
                         "mis-keyed card row with the statement's amount on its original date"),
    )),
)

BANK_RECON_THISTLE = TaskSpec(
    id="bank_recon_thistle",
    type="bank_reconciliation",
    prompt=("The January statement for the studio checking account at Heronsgate Bank has arrived and the month "
            "needs to be closed. A client deposit, a print-stock supplier payment and a bank charge do not agree "
            "between the statement and the books. Reconcile the account under the bookkeeping policy, leaving the "
            "genuine timing differences as they are, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_client_deposit", "rec:si-0425-receipt",
                        "the statement row ACH IN SALTIRE COFFEE ROASTERS quoting SI-0425 of 2700.00 on 2026-01-16 "
                        "answers no ledger entry; customers.csv maps Saltire Coffee Roasters to Assets:AR and "
                        "policy.md's Customer receipts and Collections sections post a missing receipt to the "
                        "client's account on the bank's date"),
        AlterRecognition("miskeyed_supplier_payment", "rec:pi-0787-payment", "transpose_digits", 1,
                         "the statement row ACH OUT LINDEN PRINT WORKS quoting PI-0787 of 1732.50 on 2026-01-20 "
                         "answers the ledger's same-day Linden Print Works entry of 1372.50 and no other; "
                         "vendors.csv maps Linden Print Works to Assets:Inventory, the ledger books its other "
                         "January payment to Liabilities:AP, and policy.md's Payment runs section re-posts a "
                         "mis-keyed supplier payment with the statement's amount on its original date"),
        DuplicateRecognition("duplicated_statement_fee", "rec:fee-statement-2026-01",
                             "the statement row PAPER STATEMENT FEE of 31.50 on 2026-01-12 is answered by two "
                             "identical ledger entries to Expenses:BankFees on that date; policy.md's Bank service "
                             "charges section reduces a charge carried twice for one statement row to one entry"),
    )),
)

AP_PAYMENT_RUN_THISTLE = TaskSpec(
    id="ap_payment_run_thistle",
    type="bank_reconciliation",
    prompt=("January's payment runs to the print-stock suppliers have gone out: Wexcombe Fine Papers asked for a "
            "check for PI-0785 on the 6th, and Linden Print Works and Wexcombe were paid by ACH on the 15th, 20th "
            "and 22nd. The payables ledger does not agree with what Heronsgate Bank actually paid out. Tie every "
            "supplier payment on the January statement to its invoice and its ledger entry under the bookkeeping "
            "policy, correct the books, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_supplier_check", "rec:pi-0785-payment",
                        "the statement row CHECK 1049 WEXCOMBE FINE PAPERS of 1138.75 on 2026-01-12 answers no "
                        "ledger entry; vendors.csv maps Wexcombe Fine Papers to Assets:Inventory, the ledger books "
                        "the 22 January ACH payment to Wexcombe to Liabilities:AP, and policy.md's Payment runs "
                        "section posts a missing supplier payment to Liabilities:AP on the bank's date"),
        AlterRecognition("miskeyed_ach_payment", "rec:pi-0781-payment", "transpose_digits", 2,
                         "the statement row ACH OUT LINDEN PRINT WORKS quoting PI-0781 of 1485.00 on 2026-01-15 "
                         "answers the ledger's same-day Linden Print Works entry of 1458.00 and no other; "
                         "policy.md's Payment runs section re-posts a mis-keyed supplier payment with the "
                         "statement's amount on its original date"),
        DuplicateRecognition("duplicated_ach_payment", "rec:pi-0787-payment",
                             "the statement row ACH OUT LINDEN PRINT WORKS quoting PI-0787 of 1732.50 on 2026-01-20 "
                             "is answered by two identical ledger entries to Liabilities:AP on that date; "
                             "policy.md's Payment runs section reduces a payment carried twice for one bank "
                             "debit to one entry"),
    )),
)

AR_COLLECTIONS_THISTLE = TaskSpec(
    id="ar_collections_thistle",
    type="bank_reconciliation",
    prompt=("Collections for January: Marram Coastal Hotels settled SI-0419 and put down a deposit on SI-0428, "
            "Harrowgate Brewing paid SI-0427, Fenwick Garden Centre paid part of SI-0424, Saltire Coffee Roasters "
            "settled SI-0425 by ACH and handed over a check for SI-0426 on the 28th. The receivables ledger does "
            "not agree with the deposits on the Heronsgate Bank statement. Apply every January receipt to its "
            "invoice under the bookkeeping policy, correct the client accounts, and write the corrected ledger "
            "back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_part_payment", "rec:si-0424-receipt",
                        "the statement row ACH IN FENWICK GARDEN CENTRE quoting SI-0424 of 1728.00 on 2026-01-14 "
                        "answers no ledger entry; customers.csv maps Fenwick Garden Centre to Assets:AR and "
                        "policy.md's Collections section posts a missing receipt to the client's account on the "
                        "bank's date"),
        AlterRecognition("miskeyed_client_receipt", "rec:si-0419-receipt", "transpose_digits", 1,
                         "the statement row ACH IN MARRAM COASTAL HOTELS quoting SI-0419 of 5940.00 on 2026-01-08 "
                         "answers the ledger's same-day Marram Coastal Hotels entry of 5490.00 and no other; "
                         "policy.md's Collections section re-posts a mis-keyed receipt with the statement's "
                         "amount on its original date"),
        DuplicateRecognition("duplicated_client_receipt", "rec:si-0427-receipt",
                             "the statement row ACH IN HARROWGATE BREWING CO quoting SI-0427 of 4590.00 on "
                             "2026-01-26 is answered by two identical ledger entries to Assets:AR on that date; "
                             "policy.md's Collections section reduces a receipt carried twice for one bank credit "
                             "to one entry"),
    )),
)

EXPENSE_REPORTS_THISTLE = TaskSpec(
    id="expense_reports_thistle",
    type="bank_reconciliation",
    prompt=("The principals' January expense claims have been paid: Nell Faraday's Fenwick pitch trip by check on "
            "the 13th and Tobias Hartigan's Saltire visit by check on the 23rd, and the van was fuelled twice on "
            "the debit card. The travel and vehicle accounts do not agree with the Heronsgate Bank statement. "
            "Reconcile every reimbursement check and fuel card row under the bookkeeping policy, correct the "
            "books, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_claim_check", "rec:faraday-claim-2026-01",
                        "the statement row CHECK 1052 NELL FARADAY of 341.60 on 2026-01-16 answers no ledger entry; "
                        "vendors.csv maps Nell Faraday to Expenses:Travel on expense claim terms and policy.md's "
                        "Employee expense claims section posts a missing reimbursement check to the claimant's "
                        "default account on the bank's date"),
        DuplicateRecognition("duplicated_claim_check", "rec:hartigan-claim-2026-01",
                             "the statement row CHECK 1057 TOBIAS HARTIGAN of 278.15 on 2026-01-28 is answered by "
                             "two identical ledger entries to Expenses:Travel dated 2026-01-23; policy.md's "
                             "Employee expense claims section reduces a claim carried twice for one check to one "
                             "entry"),
        AlterRecognition("miskeyed_fuel_card", "rec:fuel-2026-01-a", "transpose_digits", 1,
                         "the statement row DEBIT CARD KINGFISHER FUEL of 68.40 on 2026-01-08 answers the ledger's "
                         "same-day Kingfisher Fuel entry of 64.80 and no other; vendors.csv maps Kingfisher Fuel to "
                         "Expenses:Vehicle and policy.md's Card spend section re-posts a mis-keyed card row with "
                         "the statement's amount on its original date"),
    )),
)

PAYROLL_THISTLE = TaskSpec(
    id="payroll_thistle",
    type="bank_reconciliation",
    prompt=("January payroll was run on the 28th: net pay checks to Rowan Ashby, Imogen Talbot and Callum Reeve at "
            "the new-year rates, and December's withholdings went to the Federal Revenue Service by check on the "
            "14th. The salaries and payroll tax accounts do not agree with the checks that cleared Heronsgate Bank. "
            "Reconcile every payroll check and the remittance under the bookkeeping policy, correct the books, "
            "and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_net_pay_check", "rec:pay-ashby-2026-01",
                        "the statement row CHECK 1058 ROWAN ASHBY of 3247.60 on 2026-01-30 answers no ledger entry; "
                        "vendors.csv maps Rowan Ashby to Expenses:Salaries on monthly payroll terms and policy.md's "
                        "Payroll section posts a missing net pay check to Expenses:Salaries on the bank's date"),
        AlterRecognition("miskeyed_net_pay_check", "rec:pay-talbot-2026-01", "transpose_digits", 1,
                         "the statement row CHECK 1059 IMOGEN TALBOT of 2791.30 on 2026-01-30 answers the ledger's "
                         "Imogen Talbot entry of 2971.30 dated 2026-01-28 and no other; policy.md's Payroll section "
                         "re-posts a net pay check keyed with the wrong amount with the check's amount on its "
                         "original date"),
        OmitRecognition("unrecorded_withholding_remittance", "rec:withholding-2025-12",
                        "the statement row CHECK 1053 FEDERAL REVENUE SERVICE of 1927.35 on 2026-01-20 answers no "
                        "ledger entry; vendors.csv maps Federal Revenue Service to Liabilities:PayrollTax on monthly "
                        "remittance terms and policy.md's Payroll section debits a remittance to that liability on "
                        "the bank's date"),
    )),
)

SALES_TAX_REMITTANCE_THISTLE = TaskSpec(
    id="sales_tax_remittance_thistle",
    type="bank_reconciliation",
    prompt=("The December sales tax return was filed and paid to the State Revenue Department by check on 16 "
            "January, and January's own tax has been collected on the Harrowgate, Marram, Saltire and Fenwick "
            "invoices. Before January's return is prepared the sales tax payable account and the client receipts "
            "that carried the tax must agree with the Heronsgate Bank statement. Reconcile the remittance, the "
            "January deposits and the bank charges under the bookkeeping policy, correct the books, and write the "
            "corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_tax_remittance", "rec:sales-tax-2025-12-remit",
                        "the statement row CHECK 1054 STATE REVENUE DEPARTMENT of 712.80 on 2026-01-21 answers no "
                        "ledger entry; vendors.csv maps State Revenue Department to Liabilities:SalesTax-Payable on "
                        "monthly filing terms and policy.md's Sales tax remittance section debits a remittance to "
                        "that liability on the bank's date"),
        AlterRecognition("miskeyed_invoice_receipt", "rec:si-0425-receipt", "transpose_digits", 1,
                         "the statement row ACH IN SALTIRE COFFEE ROASTERS quoting SI-0425 of 2700.00 on 2026-01-16 "
                         "answers the ledger's same-day Saltire Coffee Roasters entry of 2070.00 and no other; "
                         "policy.md's Collections section re-posts a mis-keyed receipt with the statement's "
                         "amount on its original date"),
        DuplicateRecognition("duplicated_service_charge", "rec:fee-2026-01",
                             "the statement row MONTHLY ACCOUNT SERVICE CHARGE of 25.00 on 2026-01-30 is answered "
                             "by two identical ledger entries to Expenses:BankFees on that date; policy.md's Bank "
                             "service charges section reduces a charge carried twice for one statement row to one "
                             "entry"),
    )),
)

FIXED_ASSETS_THISTLE = TaskSpec(
    id="fixed_assets_thistle",
    type="bank_reconciliation",
    prompt=("The studio bought a large-format proofing printer from Halcyon Imaging Systems this month, paid by "
            "check on delivery, and Ferngate Technical Services replaced a workstation power supply on the card. "
            "The equipment and repairs accounts must tie to what Heronsgate Bank paid before the fixed asset "
            "register is updated. Reconcile the equipment check, the repair and the month's bank charges under "
            "the bookkeeping policy, correct the books, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_equipment_check", "rec:equipment-2026-01",
                        "the statement row CHECK 1051 HALCYON IMAGING SYSTEMS of 3865.00 on 2026-01-14 answers no "
                        "ledger entry; vendors.csv maps Halcyon Imaging Systems to Assets:Equipment and policy.md's "
                        "Equipment section capitalises a missing equipment check to that account on the bank's "
                        "date"),
        AlterRecognition("miskeyed_repair_card", "rec:repairs-2026-01", "transpose_digits", 1,
                         "the statement row DEBIT CARD FERNGATE TECHNICAL SERVICES of 218.40 on 2026-01-20 answers "
                         "the ledger's same-day Ferngate Technical Services entry of 281.40 and no other; "
                         "vendors.csv maps Ferngate Technical Services to Expenses:Repairs and policy.md's "
                         "Equipment section re-posts a mis-keyed repair with the statement's amount on its "
                         "original date"),
        OmitRecognition("unrecorded_service_charge", "rec:fee-2026-01",
                        "the statement row MONTHLY ACCOUNT SERVICE CHARGE of 25.00 on 2026-01-30 is a bank-initiated "
                        "charge with no counterparty; policy.md's Bank service charges section records bank fees to "
                        "Expenses:BankFees on the date applied"),
    )),
)

INTERCOMPANY_TRANSFERS_THISTLE = TaskSpec(
    id="intercompany_transfers_thistle",
    type="bank_reconciliation",
    prompt=("Thistle & Quill Interiors LLC was funded twice in January, by check on the 8th for the Marram fit-out "
            "deposit and on the 20th for its January wages, and the intercompany balance has to be agreed with "
            "Interiors' own books before the group figures are put together. The due-from account does not agree "
            "with the checks that cleared Heronsgate Bank, and one client receipt is also out. Reconcile the "
            "advances and the January deposits under the bookkeeping policy, correct the books, and write the "
            "corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_funding_check", "rec:interco-2026-01-b",
                        "the statement row CHECK 1055 THISTLE & QUILL INTERIORS LLC of 3500.00 on 2026-01-23 answers "
                        "no ledger entry; vendors.csv maps Thistle & Quill Interiors LLC to "
                        "Assets:Due-From-TQ-Interiors on intercompany terms, the ledger books the 8 January advance "
                        "there, and policy.md's Intercompany balances section posts a missing advance to that "
                        "account on the bank's date"),
        DuplicateRecognition("duplicated_funding_check", "rec:interco-2026-01-a",
                             "the statement row CHECK 1050 THISTLE & QUILL INTERIORS LLC of 1250.00 on 2026-01-12 is "
                             "answered by two identical ledger entries to Assets:Due-From-TQ-Interiors dated "
                             "2026-01-08; policy.md's Intercompany balances section reduces an advance carried "
                             "twice for one check to one entry"),
        AlterRecognition("miskeyed_part_payment", "rec:si-0424-receipt", "transpose_digits", 1,
                         "the statement row ACH IN FENWICK GARDEN CENTRE quoting SI-0424 of 1728.00 on 2026-01-14 "
                         "answers the ledger's same-day Fenwick Garden Centre entry of 1278.00 and no other; "
                         "policy.md's Collections section re-posts a mis-keyed receipt with the statement's "
                         "amount on its original date"),
    )),
)

MONTH_END_CLOSE_THISTLE = TaskSpec(
    id="month_end_close_thistle",
    type="bank_reconciliation",
    prompt=("Month-end close for January 2026. The February insurance premium went to Brackenfield Mutual "
            "Insurance by check on the 22nd and cleared before the cut-off, Heronsgate Bank charged the account "
            "twice this month, and the client deposits need to be agreed before the prepayments and receivables "
            "are rolled forward. Work through every difference between the statement and the ledger under the "
            "bookkeeping policy, leave the timing differences standing, and write the corrected ledger back to "
            "ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_insurance_prepayment", "rec:insurance-2026-02-prepaid",
                        "the statement row CHECK 1056 BRACKENFIELD MUTUAL INSURANCE of 486.25 on 2026-01-27 answers "
                        "no ledger entry; vendors.csv maps Brackenfield Mutual Insurance to Assets:Prepayments and "
                        "policy.md's Prepayments section posts a missing premium check to that account on the "
                        "bank's date"),
        AlterRecognition("miskeyed_statement_fee", "rec:fee-statement-2026-01", "transpose_digits", 0,
                         "the statement row PAPER STATEMENT FEE of 31.50 on 2026-01-12 answers the ledger's same-day "
                         "Heronsgate Bank entry of 13.50 to Expenses:BankFees and no other; policy.md's Bank service "
                         "charges section re-posts a charge keyed with the wrong figure with the bank's figure"),
        DuplicateRecognition("duplicated_client_deposit", "rec:si-0425-receipt",
                             "the statement row ACH IN SALTIRE COFFEE ROASTERS quoting SI-0425 of 2700.00 on "
                             "2026-01-16 is answered by two identical ledger entries to Assets:AR on that date; "
                             "policy.md's Collections section reduces a receipt carried twice for one bank credit "
                             "to one entry"),
    )),
)

TASKS = {task.id: task for task in (
    BANK_FEED_CATEGORISATION_001,
    BANK_RECON_THISTLE,
    AP_PAYMENT_RUN_THISTLE,
    AR_COLLECTIONS_THISTLE,
    EXPENSE_REPORTS_THISTLE,
    PAYROLL_THISTLE,
    SALES_TAX_REMITTANCE_THISTLE,
    FIXED_ASSETS_THISTLE,
    INTERCOMPANY_TRANSFERS_THISTLE,
    MONTH_END_CLOSE_THISTLE,
)}
