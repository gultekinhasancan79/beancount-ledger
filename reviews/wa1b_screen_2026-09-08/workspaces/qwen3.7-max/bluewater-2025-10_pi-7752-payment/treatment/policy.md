# Bluewater Marine Supply - Bookkeeping Policy

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
Bluewater does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
