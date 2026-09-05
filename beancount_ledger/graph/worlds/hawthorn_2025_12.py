"""Hawthorn Bakery, December 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The month is a payroll close. Five hourly bakery staff are carried in the
vendor master as payees whose purchases book to `Expenses:Salaries`; each is
paid net pay by check on the last working day of the month, and the
withholdings the payroll journal accrued for the previous month are remitted
to the revenue service by check around the 15th. Net pay varies with hours,
so no two checks in either month carry the same figure. The task's three
mutations name recognitions by id: one net pay check was never posted, one
was keyed with two digits transposed, and the withholdings remittance was
never posted. The check to the delivery driver issued on 30 December is not
a mutation at all: the bank cleared it on 5 January, and the December
statement's projection classifies it NOT_YET_SETTLED on its own.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..project import AlterRecognition, MutationPlan, OmitRecognition, Period
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

POLICY_TEXT = """# Hawthorn Bakery - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, check printing,
returned item fees) are recorded to `Expenses:BankFees` on the date the bank
applies them.

## Customer receipts
Cash received from a wholesale customer reduces `Assets:AR`. Where the deposit
reference identifies a sales invoice, it is applied against that invoice.

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
settles the liability; the payroll section below sets out the one such case.

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
customer, supplier or payroll movement the ledger date is never later than the
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
    Account("Assets:Inventory", K.ASSET, "Flour, sugar, dairy and other ingredients on hand", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Liabilities:PayrollTax", K.LIABILITY, "Employee withholdings and employer payroll taxes accrued and not yet remitted", OPENED, 2200),
    Account("Income:Sales", K.INCOME, "Revenue from wholesale sales of baked goods", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of ingredients consumed in goods sold", OPENED, 5000),
    Account("Expenses:Salaries", K.EXPENSE, "Net pay to bakery staff", OPENED, 5100),
    Account("Expenses:Rent", K.EXPENSE, "Bakery premises rent and lease recharges for the period", OPENED, 5200),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
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
)

DOCUMENTS = (
    Document("doc:si-4102", DK.SALES_INVOICE, "SI-4102", "party:fennimore-street", "2025-10-30", D("8742.60")),
    Document("doc:si-4118", DK.SALES_INVOICE, "SI-4118", "party:tidewell", "2025-11-03", D("4193.15")),
    Document("doc:si-4127", DK.SALES_INVOICE, "SI-4127", "party:tidewell", "2025-11-17", D("4367.40")),
    Document("doc:si-4131", DK.SALES_INVOICE, "SI-4131", "party:fennimore-street", "2025-11-28", D("9126.90")),
    Document("doc:si-4139", DK.SALES_INVOICE, "SI-4139", "party:tidewell", "2025-12-01", D("4330.10")),
    Document("doc:si-4146", DK.SALES_INVOICE, "SI-4146", "party:tidewell", "2025-12-15", D("4176.40")),
    Document("doc:si-4152", DK.SALES_INVOICE, "SI-4152", "party:fennimore-street", "2025-12-30", D("9831.50")),
    Document("doc:pi-7712", DK.PURCHASE_INVOICE, "PI-7712", "party:bramblewood", "2025-10-10", D("4218.75")),
    Document("doc:pi-7728", DK.PURCHASE_INVOICE, "PI-7728", "party:bramblewood", "2025-10-24", D("3671.30")),
    Document("doc:pi-7745", DK.PURCHASE_INVOICE, "PI-7745", "party:bramblewood", "2025-11-06", D("3864.20")),
    Document("doc:pi-7781", DK.PURCHASE_INVOICE, "PI-7781", "party:bramblewood", "2025-11-20", D("4507.90")),
    Document("doc:pi-7809", DK.PURCHASE_INVOICE, "PI-7809", "party:bramblewood", "2025-12-04", D("4932.15")),
    Document("doc:pi-7838", DK.PURCHASE_INVOICE, "PI-7838", "party:bramblewood", "2025-12-18", D("3395.60")),
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
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # November 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-11", "2025-11-03", "party:ashgrove", D("2850.00"),
                   cheque("doc:chq-2071", "2025-11-05"), "November rent, bakery premises, check 2071"),
    VendorPayment("event:pi-7712-payment", "2025-11-10", "party:bramblewood", "doc:pi-7712", D("4218.75"),
                  ach_out("2025-11-10"), "Payment of purchase invoice PI-7712"),
    ExpensePayment("event:payroll-tax-2025-11", "2025-11-14", "party:commonwealth-revenue", D("5312.94"),
                   cheque("doc:chq-2072", "2025-11-18"), "October payroll withholdings, monthly deposit, check 2072"),
    CustomerReceipt("event:si-4118-receipt", "2025-11-17", "party:tidewell", "doc:si-4118", D("4193.15"),
                    ach_in("2025-11-17"), "Customer payment for SI-4118"),
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
    BankFee("event:fee-2025-11", "2025-11-28", D("42.50"), "Monthly account service charge"),
    # December 2025: the task period
    ExpensePayment("event:rent-2025-12", "2025-12-01", "party:ashgrove", D("2987.50"),
                   cheque("doc:chq-2078", "2025-12-03"), "December rent and common-area heating recharge, check 2078"),
    Sale("event:si-4139-sale", "2025-12-01", "party:tidewell", "doc:si-4139", D("4085.00"), D("0.06"), D("1838.25"),
         "Sale SI-4139, pastries and loaves delivered 17-30 November", "Cost of goods sold on SI-4139"),
    CustomerReceipt("event:si-4127-receipt", "2025-12-02", "party:tidewell", "doc:si-4127", D("4367.40"),
                    ach_in("2025-12-02"), "Customer payment for SI-4127"),
    Purchase("event:pi-7809-purchase", "2025-12-04", "party:bramblewood", "doc:pi-7809", D("4932.15"),
             "Purchase invoice PI-7809 received, bread flour and rye"),
    VendorPayment("event:pi-7745-payment", "2025-12-08", "party:bramblewood", "doc:pi-7745", D("3864.20"),
                  ach_out("2025-12-08"), "Payment of purchase invoice PI-7745"),
    ExpensePayment("event:payroll-tax-2025-12", "2025-12-15", "party:commonwealth-revenue", D("5487.62"),
                   cheque("doc:chq-2079", "2025-12-17"), "November payroll withholdings, monthly deposit, check 2079"),
    Sale("event:si-4146-sale", "2025-12-15", "party:tidewell", "doc:si-4146", D("3940.00"), D("0.06"), D("1773.00"),
         "Sale SI-4146, pastries and loaves delivered 1-14 December", "Cost of goods sold on SI-4146"),
    CustomerReceipt("event:si-4139-receipt", "2025-12-16", "party:tidewell", "doc:si-4139", D("4330.10"),
                    ach_in("2025-12-16"), "Customer payment for SI-4139"),
    Purchase("event:pi-7838-purchase", "2025-12-18", "party:bramblewood", "doc:pi-7838", D("3395.60"),
             "Purchase invoice PI-7838 received, pastry flour, sugar and butter"),
    VendorPayment("event:pi-7781-payment", "2025-12-22", "party:bramblewood", "doc:pi-7781", D("4507.90"),
                  ach_out("2025-12-22"), "Payment of purchase invoice PI-7781"),
    CustomerReceipt("event:si-4131-receipt", "2025-12-23", "party:fennimore-street", "doc:si-4131", D("9126.90"),
                    ach_in("2025-12-23"), "Customer payment for SI-4131"),
    Sale("event:si-4152-sale", "2025-12-30", "party:fennimore-street", "doc:si-4152", D("9275.00"), D("0.06"), D("4173.75"),
         "Sale SI-4152, December standing order, bread and morning goods", "Cost of goods sold on SI-4152"),
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
    opening=OpeningPosition("2025-12-01", (("Assets:AR", D("13494.30")), ("Assets:Inventory", D("6840.00")),
                                           ("Liabilities:AP", D("-8372.10")),
                                           ("Liabilities:PayrollTax", D("-5487.62")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

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

TASKS = {PAYROLL_001.id: PAYROLL_001}
