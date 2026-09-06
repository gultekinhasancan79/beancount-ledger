"""Silverbrook Dental Supply, November 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

One month, ten tasks. The company, the bank, the statement and the golden
facts are the same for every task; only the instruction and the planted
items differ. The month carries every workflow a small distributor runs:
four dental practices buy on net 30 / net 45 terms and remit by ACH quoting
the sales invoice number, or by check, one practice paying an invoice in two
parts (collections); three stock suppliers are paid by ACH and check against
purchase invoices (the payment run); the practice-ordering portal, phones,
office consumables, van fuel and a forklift repair are paid by debit card
(the bank feed); two field representatives are reimbursed by check for
expense claims; three staff are paid net by check and October's
withholdings are deposited with the federal depository (payroll); October's
sales tax is remitted on the state portal; an electric pallet jack is bought
for the warehouse and capitalised on payment; the group's laboratory company
is advanced cash twice; December's insurance premium is prepaid; the bank
charges a positive-pay fee and its monthly service charge.

The check received from Maple Row on 28 November and the net pay check
written to Priya Raghunathan on 24 November are not mutations at all: the
bank saw both on 2 December, and the November statement's projection
classifies them NOT_YET_SETTLED on its own - a deposit in transit and an
outstanding check.
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

POLICY_TEXT = """# Silverbrook Dental Supply - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, positive pay and
remote deposit fees, returned item fees) are recorded to `Expenses:BankFees`
on the date the bank applies them.

## Customer receipts
Cash received from a customer reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice.

## Collections
Silverbrook sells to dental practices on net 30 and net 45 terms and invoices
every shipment. A practice remits by ACH, quoting the sales invoice number as
the payment reference, or by check. Every receipt is applied to the invoice
the reference names and is recorded as a debit to the checking account and a
credit to `Assets:AR`, dated the day the remittance was received. A partial
payment reduces the balance of the invoice it names; the remainder stays open
in `Assets:AR` until the practice pays it.

The receivables ledger is tied to the bank statement at every month-end.
Three kinds of difference arise, and each has exactly one correction:

- A customer receipt that appears on the statement but was never posted is
  added to the ledger for the customer and the amount the statement shows,
  against `Assets:AR`, on the date the bank shows (see Dates below).
- A customer receipt that was posted twice is corrected by removing one of
  the two copies. The copy that remains is left exactly as it was.
- A customer receipt posted with a mis-keyed amount is corrected by
  re-posting the entry with the amount the statement shows, on the date the
  entry was originally posted. Only the amount changes; the date, the
  customer and the accounts stay as they were.

A receipt that is on both the statement and the ledger with the same
customer, amount and reference is a match and is not touched. A check
received from a practice and recorded in the ledger that the bank has not yet
credited at the cut-off is a deposit in transit, governed by its own section
below; it is not a difference to correct.

## Payments to suppliers
The `default_account` a supplier carries in the vendor master is where that
supplier's trade with Silverbrook is booked. Whether it is also where a
payment to that supplier lands depends on what that account holds, and the
vendor master and the sections below say which it is.

Where a supplier's purchases are booked to `Assets:Inventory` - the dental
consumables, instruments and orthodontic suppliers - the goods were taken
into stock when they were received and a payable was raised for them at the
same time, so cash paid to that supplier afterwards settles the payable and
is recorded to `Liabilities:AP`, never to stock a second time. The payment
runs section below governs these payments.

Where a supplier's purchases are booked to an expense account, no payable is
raised: the payment is the expense, and it is recorded to that supplier's own
`default_account` on the day it is paid, except where it is paid ahead of the
period it covers, which the prepayments section below governs.

Four kinds of payee are carried in the vendor master although nothing is
bought from them on credit, and for each the payment lands on the payee's
own `default_account` on the day it is paid, with no payable in between: an
equipment supplier, whose account is `Assets:Equipment` (see Equipment); the
group's laboratory company, whose account is `Assets:Due-From-Dental-Labs`
(see Intercompany balances); the insurer, whose account is
`Assets:Prepayments` because every premium is paid in advance (see
Prepayments); and a tax authority, whose account is the liability the
remittance discharges (see Payroll and Sales tax remittance).

## Payment runs
Stock suppliers invoice on net 30 or net 45 terms and each purchase invoice
is booked to `Assets:Inventory` and `Liabilities:AP` on its date. Invoices
falling due are paid in a payment run by ACH, quoting the purchase invoice
number as the reference, or by check where the supplier does not take ACH.
Each payment is recorded on the day it is released as a debit to
`Liabilities:AP` and a credit to the checking account for the invoice amount,
with the supplier named as payee exactly as the vendor master lists it.

The payables ledger is tied to the bank statement at every close, and the
same three corrections apply as for collections: a supplier payment the
statement shows and the books lack is added against `Liabilities:AP` for the
supplier and amount the statement shows, on the date the bank shows; a
supplier payment posted twice loses one copy; a supplier payment posted with
a mis-keyed amount is re-posted with the statement's amount on its original
date, everything else unchanged.

## Card spend
Silverbrook holds a debit card on the checking account for recurring
services and small purchases: the practice-ordering portal subscription,
office phones and internet, packing and office consumables, van fuel on the
fleet card, and service calls on warehouse equipment. Each card vendor
other than the tax authority is
carried in the vendor master with the expense account its charges belong to
as its `default_account`, and every card charge is recorded on the day the
bank shows it as a debit to that account and a credit to the checking
account, the vendor named as payee exactly as the vendor master lists it.
Nothing bought on the card is stock and no payable is raised for any of it.

A card charge on the statement that the books do not carry is categorised
from the bank feed: it is added for the vendor the row names, to that
vendor's default account, for the amount the statement shows, on the date
the bank shows. A card charge the books carry with an amount that differs
from the statement's is re-posted with the statement's amount on its
original date; the vendor, the account and the date stay as they were.

The sales tax filing paid by card is governed by the sales tax remittance
section, not by this one.
## Employee expense claims
Field representatives submit expense claims for travel, mileage, lodging and
conference costs and are reimbursed by check drawn on the checking account.
Each representative is carried in the vendor master as a payee on "expense
claim" terms with `Expenses:Travel` as the default account. A reimbursement
check is recorded on the day it is written as a debit to `Expenses:Travel`
and a credit to the checking account for the amount of the claim, the
employee named as payee exactly as the vendor master lists them. No payable
is raised for a claim ahead of the check. Fuel drawn on the fleet card is
not a claim: it is card spend to `Expenses:Vehicle`, governed by the card
spend section above.

A reimbursement check the statement shows and the books lack is added for
the employee and the amount the statement shows, against `Expenses:Travel`,
on the date the bank shows. A reimbursement check posted twice loses one
copy. A reimbursement check the books carry that the bank has not cleared at
the cut-off is an outstanding check and is left as it is.

## Payroll
Staff are paid monthly, by check drawn on the checking account for each
employee's net pay, in the last week of the month. Each employee is carried
in the vendor master as a payee on "monthly payroll" terms with
`Expenses:Salaries` as the default account. A net pay check is recorded as
one entry per employee, dated the day the check is written, with the
employee named as payee exactly as the vendor master lists them: a debit to
`Expenses:Salaries` and a credit to the checking account for the net amount.
No payable is raised for net pay ahead of the check.

Amounts withheld from employees' pay are held in
`Liabilities:PayrollTax-Due` by the payroll journal the payroll bureau
supplies after each close, which is outside the bank reconciliation. The
withholdings of a month are deposited with the Federal Payroll Tax
Depository by check in the following month. The depository is carried in the
vendor master on "monthly deposit" terms with
`Liabilities:PayrollTax-Due` as its default account, and the deposit
check settles that liability: a debit to `Liabilities:PayrollTax-Due`
and a credit to the checking account on the day the check is written.

A net pay or withholding deposit check that appears on the statement but
that the books lack is added for the payee and the amount the statement
shows, against the payee's default account, on the date the bank shows. A
net pay check posted with a mis-keyed amount is re-posted with the amount
the statement shows on the date it was originally posted; only the amount
changes. A payroll check the bank has not cleared at the cut-off is an
outstanding check and is left as it is.

## Sales tax remittance
The sales tax collected in a month is reported on the state portal and paid
by the twentieth of the following month, by debit card on the portal or by
check. The State Sales Tax Division is carried in the vendor master on
"monthly filing" terms with `Liabilities:SalesTax-Payable` as its default
account, and the remittance settles that liability: a debit to
`Liabilities:SalesTax-Payable` and a credit to the checking account on the
day the payment is made, for the tax of the month being filed. A remittance
the statement shows and the books lack is added for the amount the
statement shows, against `Liabilities:SalesTax-Payable`, on the date the
bank shows.

## Equipment
Warehouse and delivery equipment for Silverbrook's own use - racking,
pallet jacks, the forklift, packing benches - is bought from suppliers the
vendor master carries with `Assets:Equipment` as their default account, and
is paid for by check on delivery. The check is the whole transaction: its
amount is capitalised to `Assets:Equipment` on the date it is written, and
depreciation is dealt with at year end, outside the monthly close. Equipment
for Silverbrook's own use is never stock and never passes through
`Liabilities:AP` or `Assets:Inventory`. Suppliers the vendor master carries
with `Expenses:Repairs` as their default account service and repair that
equipment; their charges are maintenance, not improvements, and are
expensed to `Expenses:Repairs` on the day they are paid.

An equipment or repair payment the statement shows and the books lack is
posted to that supplier's default account on the date the bank shows. A
repair charge the books carry with an amount that differs from the
statement's is re-posted with the statement's amount on its original date.

## Intercompany balances
Silverbrook Dental Labs LLC, the group's crown and bridge laboratory, is a
company under common ownership. It is carried in the vendor master only so
that checks can be drawn to it, and its terms read "intercompany". It is not
a trade supplier: nothing is purchased from it, no invoice is received from
it and no payable is ever raised for it. Cash sent to it is an advance, not
a payment for goods or services: it is recorded on the day the check is
written as a debit to `Assets:Due-From-Dental-Labs`, the account the vendor
master lists for it, and a credit to the checking account, and never to
`Liabilities:AP`. The balance is settled between the companies at year end.

An advance the statement shows and the books lack is added for the amount
the statement shows, against `Assets:Due-From-Dental-Labs`, on the date the
bank shows. An advance posted twice loses one copy; the copy that remains is
left exactly as it was.

## Outstanding checks
A check that has been issued and recorded in the ledger but has not cleared the
bank as at the statement cut-off date remains recorded. It is a timing
difference and is listed as an outstanding item in the reconciliation. It is
never removed or adjusted.

## Deposits in transit
Cash recorded as received in the ledger that does not appear on the bank
statement until after the cut-off date is likewise a timing difference and is
listed as an outstanding item. A customer's check taken into the ledger on the
day it was received and credited by the bank in the following month is the
usual case. It is never removed or adjusted.

## Dates
An entry carries the date of the transaction - the day a check was issued, a
receipt was received or an invoice was raised - never the date the bank
processed it. A ledger date that differs from the statement's date for the
same item is not an error and is not to be changed.

The bank processes a transaction on or after the day it happens, so for a
customer, supplier, employee or card movement the ledger date is never later
than the statement's date for the same item.

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

The commercial package insurance premium is invoiced by the insurer a month
in advance and is paid by check in the month before the cover month. A
premium paid in November for December cover is recorded to
`Assets:Prepayments` on the date the check is written and released to
`Expenses:Insurance` in December. The insurer carries `Assets:Prepayments`
as its `default_account` in the vendor master for exactly this reason: every
payment to the insurer is a payment in advance, and the vendor master and
this section agree on where it lands. No payable is raised for a premium. A
premium check the statement shows and the books lack is added against
`Assets:Prepayments` for the amount the statement shows, on the date the
bank shows.

## Sales tax
Silverbrook collects sales tax at 8% from its customers on sales of supplies
and equipment and owes it to the state. Goods bought for resale are exempt
under the resale certificate, so no tax is recoverable on the purchase side.

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
- Checks issued before the cut-off that clear after it are listed as
  outstanding and are not touched.

## Suspense accounts
Silverbrook does not operate a suspense or plug account. Every posting is made
to the account that reflects the underlying transaction.
"""

OPENED = "2025-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Harlow Creek Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Trade receivables from dental practices", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Dental consumables and equipment held for resale", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Assets:Due-From-Dental-Labs", K.ASSET, "Cash advanced to Silverbrook Dental Labs LLC and not yet repaid", OPENED, 1400),
    Account("Assets:Equipment", K.ASSET, "Warehouse and delivery equipment for Silverbrook's own use at cost", OPENED, 1500),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to stock suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Liabilities:PayrollTax-Due", K.LIABILITY, "Amounts withheld from employees' pay and not yet deposited", OPENED, 2200),
    Account("Income:Sales", K.INCOME, "Revenue from dental supplies and equipment sold", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:Office", K.EXPENSE, "Office and packing consumables and shipping supplies", OPENED, 5100),
    Account("Expenses:Rent", K.EXPENSE, "Warehouse and office rent for the period", OPENED, 5200),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Expenses:Salaries", K.EXPENSE, "Net pay to staff", OPENED, 5400),
    Account("Expenses:Software", K.EXPENSE, "Ordering portal and software subscriptions", OPENED, 5500),
    Account("Expenses:Telecom", K.EXPENSE, "Office phones and internet", OPENED, 5510),
    Account("Expenses:Travel", K.EXPENSE, "Field representatives' travel and mileage and lodging costs", OPENED, 5600),
    Account("Expenses:Vehicle", K.EXPENSE, "Delivery van fuel and running costs", OPENED, 5610),
    Account("Expenses:Repairs", K.EXPENSE, "Warehouse equipment repairs and maintenance", OPENED, 5700),
    Account("Expenses:Insurance", K.EXPENSE, "Commercial package insurance for the period", OPENED, 5800),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:maple-row", "Maple Row Family Dentistry", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:ellery-park", "Ellery Park Orthodontics", R.CUSTOMER, 2, "net 45", "Assets:AR"),
    Party("party:sycamore", "Sycamore Pediatric Dental", R.CUSTOMER, 3, "net 30", "Assets:AR"),
    Party("party:kessler", "Kessler Family Dental", R.CUSTOMER, 4, "net 45", "Assets:AR"),
    Party("party:deverell", "Deverell Dental Products", R.VENDOR, 5, "net 30", "Assets:Inventory"),
    Party("party:talbot-street", "Talbot Street Realty", R.VENDOR, 6, "due on receipt", "Expenses:Rent"),
    Party("party:harlow-creek-bank", "Harlow Creek Bank", R.BANK, 7),
    Party("party:bramley", "Bramley Instruments Inc", R.VENDOR, 8, "net 30", "Assets:Inventory"),
    Party("party:loxley", "Loxley Orthodontic Products", R.VENDOR, 9, "net 45", "Assets:Inventory"),
    Party("party:cuspid-cloud", "Cuspid Cloud Software", R.VENDOR, 10, "due on receipt", "Expenses:Software"),
    Party("party:tessaline", "Tessaline Telecom", R.VENDOR, 11, "due on receipt", "Expenses:Telecom"),
    Party("party:paperclip", "Paperclip Office Outfitters", R.VENDOR, 12, "due on receipt", "Expenses:Office"),
    Party("party:fuelmark", "Fuelmark Fleet Card", R.VENDOR, 13, "due on receipt", "Expenses:Vehicle"),
    Party("party:lindgren", "Tomas Lindgren", R.VENDOR, 14, "expense claim", "Expenses:Travel"),
    Party("party:abernathy", "Renee Abernathy", R.VENDOR, 15, "expense claim", "Expenses:Travel"),
    Party("party:whitfield", "Dana Whitfield", R.VENDOR, 16, "monthly payroll", "Expenses:Salaries"),
    Party("party:oyelaran", "Marcus Oyewale", R.VENDOR, 17, "monthly payroll", "Expenses:Salaries"),
    Party("party:raghunathan", "Priya Raghunathan", R.VENDOR, 18, "monthly payroll", "Expenses:Salaries"),
    Party("party:payroll-depository", "Federal Payroll Tax Depository", R.VENDOR, 19, "monthly deposit",
          "Liabilities:PayrollTax-Due"),
    Party("party:sales-tax-division", "State Sales Tax Division", R.VENDOR, 20, "monthly filing",
          "Liabilities:SalesTax-Payable"),
    Party("party:arden", "Arden Warehouse Equipment", R.VENDOR, 21, "due on receipt", "Assets:Equipment"),
    Party("party:beckett", "Beckett Lift Service", R.VENDOR, 22, "due on receipt", "Expenses:Repairs"),
    Party("party:dental-labs", "Silverbrook Dental Labs LLC", R.VENDOR, 23, "intercompany", "Assets:Due-From-Dental-Labs"),
    Party("party:larkin", "Larkin Mutual Insurance", R.VENDOR, 24, "due on receipt", "Assets:Prepayments"),
)

DOCUMENTS = (
    Document("doc:si-2198", DK.SALES_INVOICE, "SI-2198", "party:kessler", "2025-09-24", D("3942.00")),
    Document("doc:si-2200", DK.SALES_INVOICE, "SI-2200", "party:ellery-park", "2025-09-26", D("9612.00")),
    Document("doc:si-2203", DK.SALES_INVOICE, "SI-2203", "party:sycamore", "2025-09-30", D("1512.00")),
    Document("doc:si-2205", DK.SALES_INVOICE, "SI-2205", "party:maple-row", "2025-10-02", D("12096.00")),
    Document("doc:si-2207", DK.SALES_INVOICE, "SI-2207", "party:ellery-park", "2025-10-09", D("3002.40")),
    Document("doc:si-2211", DK.SALES_INVOICE, "SI-2211", "party:maple-row", "2025-10-16", D("4374.00")),
    Document("doc:si-2218", DK.SALES_INVOICE, "SI-2218", "party:sycamore", "2025-11-10", D("2494.80")),
    Document("doc:si-2223", DK.SALES_INVOICE, "SI-2223", "party:kessler", "2025-11-13", D("6615.00")),
    Document("doc:si-2229", DK.SALES_INVOICE, "SI-2229", "party:maple-row", "2025-11-14", D("1992.60")),
    Document("doc:si-2234", DK.SALES_INVOICE, "SI-2234", "party:ellery-park", "2025-11-24", D("3736.80")),
    Document("doc:pi-5182", DK.PURCHASE_INVOICE, "PI-5182", "party:deverell", "2025-09-19", D("6218.40")),
    Document("doc:pi-5195", DK.PURCHASE_INVOICE, "PI-5195", "party:bramley", "2025-10-09", D("512.35")),
    Document("doc:pi-5196", DK.PURCHASE_INVOICE, "PI-5196", "party:deverell", "2025-10-14", D("5637.25")),
    Document("doc:pi-5199", DK.PURCHASE_INVOICE, "PI-5199", "party:loxley", "2025-10-23", D("742.15")),
    Document("doc:pi-5202", DK.PURCHASE_INVOICE, "PI-5202", "party:bramley", "2025-11-04", D("2178.60")),
    Document("doc:pi-5206", DK.PURCHASE_INVOICE, "PI-5206", "party:loxley", "2025-11-11", D("3319.75")),
    Document("doc:pi-5210", DK.PURCHASE_INVOICE, "PI-5210", "party:deverell", "2025-11-18", D("4286.90")),
    Document("doc:chq-3051", DK.CHEQUE, "3051", "party:talbot-street", "2025-10-01"),
    Document("doc:chq-3052", DK.CHEQUE, "3052", "party:talbot-street", "2025-11-03"),
    Document("doc:chq-3053", DK.CHEQUE, "3053", "party:bramley", "2025-11-03"),
    Document("doc:chq-3054", DK.CHEQUE, "3054", "party:dental-labs", "2025-11-05"),
    Document("doc:chq-3055", DK.CHEQUE, "3055", "party:abernathy", "2025-11-06"),
    Document("doc:chq-3056", DK.CHEQUE, "3056", "party:lindgren", "2025-11-10"),
    Document("doc:chq-3057", DK.CHEQUE, "3057", "party:arden", "2025-11-12"),
    Document("doc:chq-3058", DK.CHEQUE, "3058", "party:larkin", "2025-11-14"),
    Document("doc:chq-3059", DK.CHEQUE, "3059", "party:dental-labs", "2025-11-17"),
    Document("doc:chq-3060", DK.CHEQUE, "3060", "party:payroll-depository", "2025-11-18"),
    Document("doc:chq-3061", DK.CHEQUE, "3061", "party:whitfield", "2025-11-24"),
    Document("doc:chq-3062", DK.CHEQUE, "3062", "party:oyelaran", "2025-11-24"),
    Document("doc:chq-3063", DK.CHEQUE, "3063", "party:raghunathan", "2025-11-24"),
    Document("doc:chq-4471", DK.CHEQUE, "4471", "party:kessler", "2025-11-17"),
    Document("doc:chq-10388", DK.CHEQUE, "10388", "party:maple-row", "2025-11-28"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # October 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-10", "2025-10-01", "party:talbot-street", D("2850.00"),
                   cheque("doc:chq-3051", "2025-10-06"), "October rent, warehouse and office, check 3051"),
    VendorPayment("event:pi-5182-payment", "2025-10-03", "party:deverell", "doc:pi-5182", D("6218.40"),
                  ach_out("2025-10-03"), "Payment of purchase invoice PI-5182"),
    CustomerReceipt("event:si-2198-receipt", "2025-10-08", "party:kessler", "doc:si-2198", D("3942.00"),
                    ach_in("2025-10-08"), "Customer payment settling SI-2198"),
    CustomerReceipt("event:si-2200-receipt", "2025-10-15", "party:ellery-park", "doc:si-2200", D("9612.00"),
                    ach_in("2025-10-15"), "Customer payment settling SI-2200"),
    CustomerReceipt("event:si-2203-receipt", "2025-10-22", "party:sycamore", "doc:si-2203", D("1512.00"),
                    ach_in("2025-10-22"), "Customer payment settling SI-2203"),
    CustomerReceipt("event:si-2205-receipt", "2025-10-28", "party:maple-row", "doc:si-2205", D("12096.00"),
                    ach_in("2025-10-28"), "Customer payment settling SI-2205"),
    BankFee("event:fee-2025-10", "2025-10-31", D("42.00"), "Monthly account service charge"),
    # November 2025: the task period
    ExpensePayment("event:salestax-2025-10-remit", "2025-11-03", "party:sales-tax-division", D("1174.32"),
                   card("2025-11-03"), "October sales tax return, paid on the state portal"),
    ExpensePayment("event:rent-2025-11", "2025-11-03", "party:talbot-street", D("2987.50"),
                   cheque("doc:chq-3052", "2025-11-06"), "November rent and annual CAM reconciliation charge, check 3052"),
    VendorPayment("event:pi-5195-payment", "2025-11-03", "party:bramley", "doc:pi-5195", D("512.35"),
                  cheque("doc:chq-3053", "2025-11-06"), "Payment of purchase invoice PI-5195, check 3053"),
    Purchase("event:pi-5202-purchase", "2025-11-04", "party:bramley", "doc:pi-5202", D("2178.60"),
             "Purchase invoice PI-5202 received, hand instruments and sterilisation cassettes"),
    ExpensePayment("event:software-2025-11", "2025-11-04", "party:cuspid-cloud", D("289.00"),
                   card("2025-11-04"), "Practice ordering portal subscription, November"),
    CustomerReceipt("event:si-2211-receipt", "2025-11-05", "party:maple-row", "doc:si-2211", D("4374.00"),
                    ach_in("2025-11-05"), "Customer payment settling SI-2211"),
    ExpensePayment("event:office-2025-11", "2025-11-05", "party:paperclip", D("163.48"),
                   card("2025-11-05"), "Shipping labels, toner and packing tape"),
    ExpensePayment("event:ic-advance-2025-11-a", "2025-11-05", "party:dental-labs", D("7500.00"),
                   cheque("doc:chq-3054", "2025-11-10"), "Intercompany advance to Silverbrook Dental Labs LLC, check 3054"),
    ExpensePayment("event:claim-abernathy-2025-11", "2025-11-06", "party:abernathy", D("612.90"),
                   cheque("doc:chq-3055", "2025-11-12"), "Expense claim, October territory visits, mileage and lodging, check 3055"),
    ExpensePayment("event:repairs-2025-11", "2025-11-06", "party:beckett", D("385.70"),
                   card("2025-11-06"), "Forklift hydraulic hose replacement and service call"),
    VendorPayment("event:pi-5196-payment", "2025-11-07", "party:deverell", "doc:pi-5196", D("5637.25"),
                  ach_out("2025-11-07"), "Payment of purchase invoice PI-5196"),
    VendorPayment("event:pi-5199-payment", "2025-11-07", "party:loxley", "doc:pi-5199", D("742.15"),
                  ach_out("2025-11-07"), "Payment of purchase invoice PI-5199"),
    BankFee("event:fee-2025-11-positive-pay", "2025-11-07", D("22.75"), "Positive pay service fee"),
    Sale("event:si-2218-sale", "2025-11-10", "party:sycamore", "doc:si-2218", D("2310.00"), D("0.08"), D("1386.00"),
         "Sale SI-2218, hygiene consumables and exam gloves", "Cost of goods sold on SI-2218"),
    ExpensePayment("event:claim-lindgren-2025-11", "2025-11-10", "party:lindgren", D("748.55"),
                   cheque("doc:chq-3056", "2025-11-14"), "Expense claim, regional dental conference travel and lodging, check 3056"),
    Purchase("event:pi-5206-purchase", "2025-11-11", "party:loxley", "doc:pi-5206", D("3319.75"),
             "Purchase invoice PI-5206 received, archwire, brackets and elastics"),
    CustomerReceipt("event:si-2207-receipt", "2025-11-12", "party:ellery-park", "doc:si-2207", D("3002.40"),
                    ach_in("2025-11-12"), "Customer payment settling SI-2207"),
    ExpensePayment("event:fuel-2025-11", "2025-11-12", "party:fuelmark", D("418.36"),
                   card("2025-11-12"), "Delivery van fuel, fleet card statement"),
    ExpensePayment("event:equipment-2025-11", "2025-11-12", "party:arden", D("6480.00"),
                   cheque("doc:chq-3057", "2025-11-17"), "Electric pallet jack for the warehouse, check 3057"),
    Sale("event:si-2223-sale", "2025-11-13", "party:kessler", "doc:si-2223", D("6125.00"), D("0.08"), D("3675.00"),
         "Sale SI-2223, intraoral sensor and restorative consumables", "Cost of goods sold on SI-2223"),
    ExpensePayment("event:telecom-2025-11", "2025-11-13", "party:tessaline", D("236.19"),
                   card("2025-11-13"), "Office phones and internet, November"),
    Sale("event:si-2229-sale", "2025-11-14", "party:maple-row", "doc:si-2229", D("1845.00"), D("0.08"), D("1107.00"),
         "Sale SI-2229, impression material and prophy supplies", "Cost of goods sold on SI-2229"),
    Prepayment("event:insurance-2025-12-prepaid", "2025-11-14", "party:larkin", D("1365.00"),
               cheque("doc:chq-3058", "2025-11-18"), "2025-12", "December commercial package premium prepaid, check 3058"),
    CustomerReceipt("event:si-2223-part-receipt", "2025-11-17", "party:kessler", "doc:si-2223", D("3500.00"),
                    cheque("doc:chq-4471", "2025-11-20"), "Partial payment against SI-2223, check 4471"),
    ExpensePayment("event:ic-advance-2025-11-b", "2025-11-17", "party:dental-labs", D("4200.00"),
                   cheque("doc:chq-3059", "2025-11-20"), "Intercompany advance to Silverbrook Dental Labs LLC, check 3059"),
    Purchase("event:pi-5210-purchase", "2025-11-18", "party:deverell", "doc:pi-5210", D("4286.90"),
             "Purchase invoice PI-5210 received, composite kits and carbide burs"),
    ExpensePayment("event:payrolltax-2025-10-remit", "2025-11-18", "party:payroll-depository", D("2416.80"),
                   cheque("doc:chq-3060", "2025-11-24"), "October payroll withholdings deposited, check 3060"),
    CustomerReceipt("event:si-2218-receipt", "2025-11-19", "party:sycamore", "doc:si-2218", D("2494.80"),
                    ach_in("2025-11-19"), "Customer payment settling SI-2218"),
    VendorPayment("event:pi-5202-payment", "2025-11-21", "party:bramley", "doc:pi-5202", D("2178.60"),
                  ach_out("2025-11-21"), "Payment of purchase invoice PI-5202"),
    Sale("event:si-2234-sale", "2025-11-24", "party:ellery-park", "doc:si-2234", D("3460.00"), D("0.08"), D("2076.00"),
         "Sale SI-2234, orthodontic archwire and brackets", "Cost of goods sold on SI-2234"),
    ExpensePayment("event:payroll-2025-11-whitfield", "2025-11-24", "party:whitfield", D("3412.65"),
                   cheque("doc:chq-3061", "2025-11-26"), "November net pay, check 3061"),
    ExpensePayment("event:payroll-2025-11-oyelaran", "2025-11-24", "party:oyelaran", D("2958.40"),
                   cheque("doc:chq-3062", "2025-11-28"), "November net pay, check 3062"),
    # written in November, cleared by the bank in December: the outstanding check
    ExpensePayment("event:payroll-2025-11-raghunathan", "2025-11-24", "party:raghunathan", D("3187.20"),
                   cheque("doc:chq-3063", "2025-12-02"), "November net pay, check 3063"),
    VendorPayment("event:pi-5206-payment", "2025-11-25", "party:loxley", "doc:pi-5206", D("3319.75"),
                  ach_out("2025-11-25"), "Payment of purchase invoice PI-5206"),
    # received in November, credited by the bank in December: the deposit in transit
    CustomerReceipt("event:si-2229-receipt", "2025-11-28", "party:maple-row", "doc:si-2229", D("1992.60"),
                    cheque("doc:chq-10388", "2025-12-02"), "Customer payment settling SI-2229, check 10388"),
    BankFee("event:fee-2025-11", "2025-11-28", D("47.50"), "Monthly account service charge and remote deposit fee"),
)

WORLD = World(
    id="silverbrook-2025-11",
    title="Silverbrook Dental Supply - FY2025",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:harlow-creek-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-10-01", D("38472.19")),
    opening=OpeningPosition("2025-11-01", (("Assets:AR", D("8916.40")), ("Assets:Inventory", D("31480.00")),
                                           ("Assets:Equipment", D("21340.00")),
                                           ("Liabilities:AP", D("-6891.75")),
                                           ("Liabilities:SalesTax-Payable", D("-1174.32")),
                                           ("Liabilities:PayrollTax-Due", D("-2416.80")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

PERIOD = Period("2025-11-01", "2025-11-30", "November 2025")

AR_COLLECTIONS_001 = TaskSpec(
    id="ar_collections_001",
    type="bank_reconciliation",
    prompt=("The November statement from Harlow Creek Bank is in, and the month-end collections review has found "
            "that the receivables ledger does not agree with it. Reconcile the checking account against the "
            "statement, bring the books into agreement under the bookkeeping policy, and write the corrected "
            "ledger back to ledger.beancount."),
    period=Period("2025-11-01", "2025-11-30", "November 2025"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_receipt", "rec:si-2218-receipt",
                        "the statement row names the payer and the invoice (ACH IN SYCAMORE PEDIATRIC DENTAL, "
                        "SI-2218) and no ledger entry matches it; customers.csv maps the practice to Assets:AR and "
                        "the ledger carries the open sale SI-2218; the collections section posts a receipt the "
                        "books lack against Assets:AR, and the dates section puts it on the bank's date"),
        AlterRecognition("transposed_customer_receipt", "rec:si-2211-receipt", "transpose_digits", 1,
                         "the ledger carries the 5 November receipt from Maple Row Family Dentistry for SI-2211 at "
                         "4734.00 while the statement row of the same date, payer and reference shows 4374.00; the "
                         "collections section says to re-post the entry with the statement's amount on the "
                         "original date, against Assets:AR"),
        DuplicateRecognition("duplicated_customer_receipt", "rec:si-2207-receipt",
                             "the ledger carries the 12 November receipt from Ellery Park Orthodontics for SI-2207 "
                             "twice and the statement shows one ACH IN row of 3002.40 with that reference; the "
                             "collections section says to remove one copy and leave the other as it was"),
    )),
)

BANK_RECON_SILVERBROOK = TaskSpec(
    id="bank_recon_silverbrook",
    type="bank_reconciliation",
    prompt=("The November checking account statement from Harlow Creek Bank has arrived and the month needs to be "
            "closed. The book balance does not agree with the bank: work through the receipts, the supplier "
            "payments and the bank's own charges, tie the ledger out to the statement under the bookkeeping policy, "
            "list the timing items, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_supplier_payment", "rec:pi-5206-payment",
                        "the 25 November statement row reads ACH OUT LOXLEY ORTHODONTIC PRODUCTS with reference "
                        "PI-5206 and no ledger entry matches it; vendors.csv books Loxley to Assets:Inventory, the "
                        "ledger already books the 7 November payment to Loxley against Liabilities:AP and carries "
                        "the purchase PI-5206, and the payment runs section posts a supplier payment the books "
                        "lack against Liabilities:AP on the bank's date"),
        AlterRecognition("miskeyed_bank_fee", "rec:fee-2025-11", "transpose_digits", 0,
                         "the ledger carries the 28 November monthly service charge at 74.50 while the statement's "
                         "MONTHLY ACCOUNT SERVICE CHARGE AND REMOTE DEPOSIT FEE row of that date shows 47.50; the "
                         "bank service charges section names Expenses:BankFees and the entry is re-posted with the "
                         "statement's amount on its original date"),
        DuplicateRecognition("duplicated_customer_check", "rec:si-2223-part-receipt",
                             "the ledger carries the 17 November check 4471 from Kessler Family Dental for 3500.00 "
                             "twice while the statement shows one CHECK 4471 row of that amount on 20 November; "
                             "the collections section says to remove one copy and leave the other as it was"),
    )),
)

AP_PAYMENT_RUN_SILVERBROOK = TaskSpec(
    id="ap_payment_run_silverbrook",
    type="bank_reconciliation",
    prompt=("November's supplier payment runs went out to Deverell, Bramley and Loxley by ACH and by check against "
            "their purchase invoices, and the payables ledger no longer agrees with the Harlow Creek Bank statement. "
            "Reconcile the payment runs against the statement row by row, applying the payment runs section of the "
            "bookkeeping policy to every difference, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_supplier_ach", "rec:pi-5202-payment",
                        "the 21 November statement row reads ACH OUT BRAMLEY INSTRUMENTS INC with reference "
                        "PI-5202 and no ledger entry matches it; vendors.csv books Bramley to Assets:Inventory, the "
                        "ledger already books check 3053 to Bramley against Liabilities:AP and carries the purchase "
                        "PI-5202, and the payment runs section posts the missing payment against Liabilities:AP on "
                        "the bank's date"),
        AlterRecognition("transposed_supplier_payment", "rec:pi-5196-payment", "transpose_digits", 1,
                         "the ledger carries the 7 November ACH payment to Deverell Dental Products for PI-5196 at "
                         "5367.25 while the statement row of the same date, payee and reference shows 5637.25; the "
                         "payment runs section re-posts the entry with the statement's amount on its original date, "
                         "against Liabilities:AP"),
        DuplicateRecognition("duplicated_supplier_check", "rec:pi-5195-payment",
                             "the ledger carries the 3 November check 3053 to Bramley Instruments Inc for PI-5195 "
                             "twice while the statement shows one CHECK 3053 row of 512.35 on 6 November; the "
                             "payment runs section says to remove one copy and leave the other as it was"),
    )),
)

BANK_FEED_CATEGORISATION_SILVERBROOK = TaskSpec(
    id="bank_feed_categorisation_silverbrook",
    type="bank_reconciliation",
    prompt=("The debit card charges on the November Harlow Creek Bank feed have not all been categorised into the "
            "ledger: the ordering portal, the phone company, the office consumables, the fleet fuel and the forklift "
            "service call all went on the card this month. Go through every DEBIT CARD row on the statement, book "
            "each one to the account the vendor master gives that vendor under the card spend section of the "
            "bookkeeping policy, correct any card charge already booked at the wrong amount, and write the "
            "corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_software_card", "rec:software-2025-11",
                        "the 4 November statement row reads DEBIT CARD CUSPID CLOUD SOFTWARE for 289.00 and no "
                        "ledger entry matches it; vendors.csv gives Cuspid Cloud Software the account "
                        "Expenses:Software, which accounts.csv types as an expense, and the card spend section "
                        "books a card charge the books lack to that account on the bank's date"),
        OmitRecognition("unrecorded_telecom_card", "rec:telecom-2025-11",
                        "the 13 November statement row reads DEBIT CARD TESSALINE TELECOM for 236.19 and no ledger "
                        "entry matches it; vendors.csv gives Tessaline Telecom the account Expenses:Telecom, and "
                        "the card spend section books it there on the bank's date"),
        AlterRecognition("transposed_office_card", "rec:office-2025-11", "transpose_digits", 2,
                         "the ledger carries the 5 November card charge to Paperclip Office Outfitters at 164.38 "
                         "while the statement's DEBIT CARD PAPERCLIP OFFICE OUTFITTERS row of that date shows "
                         "163.48; the card spend section re-posts the entry with the statement's amount on its "
                         "original date, against Expenses:Office"),
    )),
)

EXPENSE_REPORTS_SILVERBROOK = TaskSpec(
    id="expense_reports_silverbrook",
    type="bank_reconciliation",
    prompt=("The field representatives' October expense claims were approved and paid by check in November, and the "
            "fleet fuel card was charged to the checking account as usual. The reimbursement checks and the fuel "
            "charge do not agree with the November Harlow Creek Bank statement. Reconcile the employee expense "
            "claims and the card fuel under the employee expense claims and card spend sections of the bookkeeping "
            "policy, leave any check the bank has not yet cleared as an outstanding item, and write the corrected "
            "ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_reimbursement_check", "rec:claim-lindgren-2025-11",
                        "the 14 November statement row reads CHECK 3056 TOMAS LINDGREN for 748.55 and no ledger "
                        "entry carries check 3056; vendors.csv carries Tomas Lindgren on expense claim terms with "
                        "Expenses:Travel, and the employee expense claims section adds a reimbursement check the "
                        "books lack against Expenses:Travel on the bank's date"),
        DuplicateRecognition("duplicated_reimbursement_check", "rec:claim-abernathy-2025-11",
                             "the ledger carries the 6 November check 3055 to Renee Abernathy for 612.90 twice "
                             "while the statement shows one CHECK 3055 row of that amount on 12 November; the "
                             "employee expense claims section says to remove one copy"),
        AlterRecognition("transposed_fuel_card", "rec:fuel-2025-11", "transpose_digits", 1,
                         "the ledger carries the 12 November fleet fuel charge to Fuelmark Fleet Card at 481.36 "
                         "while the statement's DEBIT CARD FUELMARK FLEET CARD row of that date shows 418.36; the "
                         "card spend section re-posts the entry with the statement's amount on its original date, "
                         "against Expenses:Vehicle"),
    )),
)

PAYROLL_SILVERBROOK = TaskSpec(
    id="payroll_silverbrook",
    type="bank_reconciliation",
    prompt=("November payroll was paid by check on the 24th, ahead of the Thanksgiving week, and October's "
            "withholdings were deposited with the Federal Payroll Tax Depository during the month. The payroll "
            "postings do not agree with the November Harlow Creek Bank statement. Reconcile the net pay checks and "
            "the withholding deposit under the payroll section of the bookkeeping policy, treat any net pay check "
            "the bank has not cleared by the cut-off as an outstanding check, and write the corrected ledger back "
            "to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_net_pay_check", "rec:payroll-2025-11-whitfield",
                        "the 26 November statement row reads CHECK 3061 DANA WHITFIELD for 3412.65 and no ledger "
                        "entry carries check 3061; vendors.csv carries Dana Whitfield on monthly payroll terms with "
                        "Expenses:Salaries, and the payroll section adds a net pay check the books lack against "
                        "Expenses:Salaries on the bank's date"),
        AlterRecognition("transposed_net_pay_check", "rec:payroll-2025-11-oyelaran", "transpose_digits", 1,
                         "the ledger carries the 24 November net pay check 3062 to Marcus Oyewale at 2598.40 while "
                         "the statement's CHECK 3062 MARCUS OYELARAN row of 28 November shows 2958.40; the payroll "
                         "section re-posts the entry with the statement's amount on its original date, against "
                         "Expenses:Salaries"),
        OmitRecognition("unrecorded_withholding_deposit", "rec:payrolltax-2025-10-remit",
                        "the 24 November statement row reads CHECK 3060 FEDERAL PAYROLL TAX DEPOSITORY for 2416.80 "
                        "and no ledger entry carries check 3060; vendors.csv carries the depository on monthly "
                        "deposit terms with Liabilities:PayrollTax-Due, and the payroll section settles that "
                        "liability with the deposit check, on the bank's date when the books lack it"),
    )),
)

SALES_TAX_REMITTANCE_SILVERBROOK = TaskSpec(
    id="sales_tax_remittance_silverbrook",
    type="bank_reconciliation",
    prompt=("October's sales tax return was filed on the state portal at the start of November and the tax "
            "collected in October was paid with it; November's sales carry tax at 8% that is due next month. The "
            "sales tax and receivables postings do not agree with the November Harlow Creek Bank statement. "
            "Reconcile the remittance, the customer receipts and the bank's charges under the sales tax remittance "
            "and collections sections of the bookkeeping policy, and write the corrected ledger back to "
            "ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_sales_tax_remittance", "rec:salestax-2025-10-remit",
                        "the 3 November statement row reads DEBIT CARD STATE SALES TAX DIVISION for 1174.32 and no "
                        "ledger entry matches it; vendors.csv carries the division on monthly filing terms with "
                        "Liabilities:SalesTax-Payable, the opening entry carries that liability, and the sales tax "
                        "remittance section settles it with the remittance, on the bank's date when the books "
                        "lack it"),
        AlterRecognition("transposed_customer_receipt", "rec:si-2207-receipt", "transpose_digits", 2,
                         "the ledger carries the 12 November receipt from Ellery Park Orthodontics for SI-2207 at "
                         "3020.40 while the statement row of the same date, payer and reference shows 3002.40; the "
                         "collections section re-posts the entry with the statement's amount on the original date, "
                         "against Assets:AR"),
        DuplicateRecognition("duplicated_bank_fee", "rec:fee-2025-11",
                             "the ledger carries the 28 November monthly account service charge of 47.50 twice while "
                             "the statement shows one MONTHLY ACCOUNT SERVICE CHARGE AND REMOTE DEPOSIT FEE row of "
                             "that amount; the bank service charges section names Expenses:BankFees and one copy "
                             "is removed"),
    )),
)

FIXED_ASSETS_SILVERBROOK = TaskSpec(
    id="fixed_assets_silverbrook",
    type="bank_reconciliation",
    prompt=("Silverbrook bought an electric pallet jack for the warehouse from Arden Warehouse Equipment this month "
            "and paid Beckett Lift Service on the card for a forklift repair. The equipment and repairs postings, "
            "and the bank's charges, do not agree with the November Harlow Creek Bank statement. Reconcile them "
            "under the equipment and bank service charges sections of the bookkeeping policy - capital equipment "
            "capitalised on payment, repairs expensed - and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_equipment_check", "rec:equipment-2025-11",
                        "the 17 November statement row reads CHECK 3057 ARDEN WAREHOUSE EQUIPMENT for 6480.00 and no "
                        "ledger entry carries check 3057; vendors.csv gives Arden Warehouse Equipment the account "
                        "Assets:Equipment, and the equipment section capitalises an equipment payment the books "
                        "lack to that account on the bank's date"),
        AlterRecognition("transposed_repair_card", "rec:repairs-2025-11", "transpose_digits", 0,
                         "the ledger carries the 6 November card charge to Beckett Lift Service at 835.70 while the "
                         "statement's DEBIT CARD BECKETT LIFT SERVICE row of that date shows 385.70; the equipment "
                         "section re-posts the repair with the statement's amount on its original date, against "
                         "Expenses:Repairs"),
        DuplicateRecognition("duplicated_bank_fee", "rec:fee-2025-11-positive-pay",
                             "the ledger carries the 7 November positive pay service fee of 22.75 twice while the "
                             "statement shows one POSITIVE PAY SERVICE FEE row of that amount; the bank service "
                             "charges section names Expenses:BankFees and one copy is removed"),
    )),
)

INTERCOMPANY_TRANSFERS_SILVERBROOK = TaskSpec(
    id="intercompany_transfers_silverbrook",
    type="bank_reconciliation",
    prompt=("Silverbrook advanced cash to its laboratory company, Silverbrook Dental Labs LLC, twice in November by "
            "check, and the intercompany balance in the ledger does not agree with what the Harlow Creek Bank "
            "statement shows leaving the account; the practice receipts need checking at the same time. Reconcile "
            "the intercompany advances and the receipts under the intercompany balances and collections sections of "
            "the bookkeeping policy, and write the corrected ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_intercompany_advance", "rec:ic-advance-2025-11-a",
                        "the 10 November statement row reads CHECK 3054 SILVERBROOK DENTAL LABS LLC for 7500.00 and "
                        "no ledger entry carries check 3054; vendors.csv carries the laboratory on intercompany "
                        "terms with Assets:Due-From-Dental-Labs, the ledger already books check 3059 to it there, "
                        "and the intercompany balances section adds an advance the books lack to that account on "
                        "the bank's date"),
        DuplicateRecognition("duplicated_intercompany_advance", "rec:ic-advance-2025-11-b",
                             "the ledger carries the 17 November check 3059 to Silverbrook Dental Labs LLC for "
                             "4200.00 twice while the statement shows one CHECK 3059 row of that amount on 20 "
                             "November; the intercompany balances section says to remove one copy"),
        AlterRecognition("transposed_customer_receipt", "rec:si-2218-receipt", "transpose_digits", 1,
                         "the ledger carries the 19 November receipt from Sycamore Pediatric Dental for SI-2218 at "
                         "2944.80 while the statement row of the same date, payer and reference shows 2494.80; the "
                         "collections section re-posts the entry with the statement's amount on the original date, "
                         "against Assets:AR"),
    )),
)

MONTH_END_CLOSE_SILVERBROOK = TaskSpec(
    id="month_end_close_silverbrook",
    type="bank_reconciliation",
    prompt=("Month-end close for November 2025. December's insurance premium was prepaid by check in the middle of "
            "the month, the bank charged a positive pay fee and its monthly service charge, and the practices paid "
            "their invoices through the month; the ledger does not close to the Harlow Creek Bank statement. Bring "
            "the prepayment, the bank charges and the customer receipts into agreement with the statement under the "
            "bookkeeping policy, note the deposit in transit and the outstanding check, and write the corrected "
            "ledger back to ledger.beancount."),
    period=PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_prepayment_check", "rec:insurance-2025-12-prepaid",
                        "the 18 November statement row reads CHECK 3058 LARKIN MUTUAL INSURANCE for 1365.00 and no "
                        "ledger entry carries check 3058; vendors.csv gives Larkin Mutual Insurance the account "
                        "Assets:Prepayments, and the prepayments section books a premium check the books lack to "
                        "Assets:Prepayments on the bank's date"),
        AlterRecognition("transposed_bank_fee", "rec:fee-2025-11-positive-pay", "transpose_digits", 1,
                         "the ledger carries the 7 November positive pay service fee at 27.25 while the statement's "
                         "POSITIVE PAY SERVICE FEE row of that date shows 22.75; the bank service charges section "
                         "names Expenses:BankFees and the entry is re-posted with the statement's amount on its "
                         "original date"),
        DuplicateRecognition("duplicated_customer_receipt", "rec:si-2211-receipt",
                             "the ledger carries the 5 November receipt from Maple Row Family Dentistry for SI-2211 "
                             "twice while the statement shows one ACH IN row of 4374.00 with that reference; the "
                             "collections section says to remove one copy and leave the other as it was"),
    )),
)

TASKS = {task.id: task for task in (
    AR_COLLECTIONS_001,
    BANK_RECON_SILVERBROOK,
    AP_PAYMENT_RUN_SILVERBROOK,
    BANK_FEED_CATEGORISATION_SILVERBROOK,
    EXPENSE_REPORTS_SILVERBROOK,
    PAYROLL_SILVERBROOK,
    SALES_TAX_REMITTANCE_SILVERBROOK,
    FIXED_ASSETS_SILVERBROOK,
    INTERCOMPANY_TRANSFERS_SILVERBROOK,
    MONTH_END_CLOSE_SILVERBROOK,
)}
