# Maple Street Veterinary Clinic - Bookkeeping Policy

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
A net pay or remittance check the statement shows that the books lack is
added for the payee and the amount the statement shows, against that
payee's account in the vendor master, on the date the bank shows. A net
pay check posted with a mis-keyed amount is re-posted with the amount the
statement shows, on the date the entry was originally posted; only the
amount changes.

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
An equipment check the statement shows that the books do not carry is
capitalised to `Assets:Equipment` on the date the bank shows. A repair
charge the books carry at an amount that differs from the statement's is
re-posted with the statement's amount on its original date.

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
