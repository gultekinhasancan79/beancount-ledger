# Bowline Marine Supply Co. — Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, wire fees, returned
item fees) are recorded to `Expenses:BankFees` on the date the bank applies them.

## Customer receipts
Cash received from a customer reduces `Assets:AR`, for the amount and on the date
the bank shows. Which invoices the cash settled is not a question the ledger
answers: Bowline keeps one receivables control account and an open-item
register outside it, and the cash application section below says how a receipt
is applied in that register.

## Cash application
Bowline keeps one receivables control account, `Assets:AR`, and an open-item register
by invoice outside the ledger. A receipt is posted to `Assets:AR` for the amount and
on the date the bank shows, and applied in the register to invoices of the
paying customer in this order of authority: (1) the customer's remittance
advice, where one belongs to the payment — each line to the invoice it names
for the amount it states, and any part of the payment the advice does not name
is left unapplied rather than carried on to the rules below; (2) otherwise the
invoice numbers quoted in the statement reference, in invoice-date order, then
invoice number, each up to its open balance, any remainder following (3);
(3) otherwise the customer's open invoices oldest first by invoice date, then
invoice number, each up to its open balance. An advice belongs to a payment
when customer, payment reference and amount all agree; an advice that belongs
to no payment is not evidence for any payment. Cash that no open invoice
absorbs stays in `Assets:AR` as an unapplied credit **of that customer**, whose
ownership the register records; it is never income. That is this
reconciliation's convention for an aggregate control account, not a
financial-statement presentation rule. Applications run in date order; on one
date credit notes before receipts, receipts in statement order.

A receipt smaller than the invoice it is applied to leaves the balance open.
Where the advice marks an invoice settled and the shortfall — after combining
that advice's lines for that invoice — is `25.00` or less **for that
invoice on that receipt**, the shortfall is written off to `Expenses:SmallBalanceWriteOffs` in a
separate entry dated with the receipt, payee the customer, and the invoice is
closed; above `25.00` nothing is written off and the shortfall remains
open. Nothing is written off without an advice marking the invoice settled.
This exercise authorises those expense write-offs **without a sales-tax
adjustment**; determining the tax treatment of a settlement discount is not
asked of the agent.

## Credit notes
A credit note reverses the sale and its tax on its date: `Income:Sales` net,
`Liabilities:SalesTax-Payable` tax, `Assets:AR` gross. It is applied to the invoice
it references up to that invoice's open balance on that date — if that invoice
is already paid, none of it lands there — any excess to the same customer's
other open invoices in invoice-date order, then invoice number, any remainder
held as an unapplied credit of that customer.

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
A customer receipt carries the date the bank shows the money moved, as the
cash application section says; the date on a customer's remittance advice or
check is evidence of what was paid and when the customer sent it, never the
posting date. Every other entry carries the date of the transaction — the day
a check was issued, an invoice was raised or a credit note was issued — never
the date the bank processed it. A ledger date that differs from the
statement's date for the same item is not an error and is not to be changed.

The bank processes a transaction on or after the day it happens, so for a
supplier movement the ledger date is never later than the statement's date for
the same item.

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

## Sales tax
Bowline collects sales tax from customers at 8% on sales and owes it to the
state. Purchases of goods for resale are exempt, so no tax is recoverable on
the purchase side.

## Suspense accounts
Bowline does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
