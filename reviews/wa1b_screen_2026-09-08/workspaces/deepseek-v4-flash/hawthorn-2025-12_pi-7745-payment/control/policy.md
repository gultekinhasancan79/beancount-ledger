# Hawthorn Bakery - Bookkeeping Policy

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
Hawthorn's bakery staff are paid monthly, in the last week of the
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
Hawthorn does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
