# Falcon Ridge Surveying — Bookkeeping Policy

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
pay by a system-printed check on or about the 25th of the month, and the check is
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
check banked is either credited or listed as in transit, the bank charges
the bank applies in a month (an ACH batch fee mid-month and the service
charge at month end) are all booked, the insurer's check for next month's
premium sits in `Assets:Prepayments`, and the ledger's bank balance agrees
with the statement after the timing items. Nothing is posted to close a gap
that the statement does not explain.

## Suspense accounts
Falcon Ridge does not operate a suspense or plug account. Every posting is
made to the account that reflects the underlying transaction.
