"""The three variant packs of 2026-09: what their six worlds share.

`six_variant_packs.md` in `v10-codex/` is the specification for three matched
PAIRS — Thornbury Glassworks LLC June 2026, Pennywhistle Bakehouse Co. June
2026 and Tallowmere Print & Bindery Co. July 2026 — and every one of the
eleven public files it renders is the byte the projector must emit. Each pair
is two variants of ONE company-month differing in exactly one authored fact,
so a solver's failure localises to the question that fact asks.

Two things are identical across all three months and are therefore stated
here once rather than three times: the bookkeeping policy, which differs only
in the company's short name, its sales-tax rate and whether the month needs
the invoice-numbering paragraph; and the instruction, which is Bowline's word
for word with the month's name substituted (`tests/test_cash_application_worlds.py`
pins that equality, so the six new tasks cannot drift into a different
register from the five shipped ones).

The policy text carries the three clarifications the accounting review of
2026-09-11 (`v10-codex/accounting_review_2026-09-11.md`) dictated — the
management-authorised settlement tolerance, what happens to cash or credit
once it is held unapplied, and that reported receivables totals are net
operational control-account balances — and the credit-note paragraph that
bounds a credit described only as the reversal of one sale by that sale's own
net and tax rather than by what remains unpaid on it. Bowline's shipped
`policy.md` predates the review and is NOT reworded here: its public bytes
are frozen, and the archived measurement evidence taken against them has to
stay valid.

Nothing derived is typed anywhere in this family. The company modules state
facts; the register, the applications, the write-offs and the closing
balances are folds of them.
"""

from __future__ import annotations

from ..policy import SHORT_PAY_TOLERANCE

AR = "Assets:AR"
WRITE_OFFS = "Expenses:SmallBalanceWriteOffs"
TOLERANCE = f"{SHORT_PAY_TOLERANCE:.2f}"

#: The paragraph a month needs only when its invoice numbers run against its
#: invoice dates, so that a solver reading rung (2) cannot mistake the
#: numbering for a chronology. Thornbury needs it; the other two do not.
NUMBERING_SECTION = """## Sales invoice numbering
Invoice numbers are drawn from the job book of the contract an invoice belongs
to rather than from a single chronological series, so an invoice raised later
may carry a lower number than one raised earlier. A number identifies the
document; it is not evidence of the order in which invoices were raised.

"""

_POLICY = """# {title} — Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, wire fees, returned
item fees) are recorded to `Expenses:BankFees` on the date the bank applies them.

## Customer receipts
Cash received from a customer reduces `{ar}`, for the amount and on the date
the bank shows. Which invoices the cash settled is not a question the ledger
answers: {company} keeps one receivables control account and an open-item
register outside it, and the cash application section below says how a receipt
is applied in that register.

## Cash application
{company} keeps one receivables control account, `{ar}`, and an open-item register
by invoice outside the ledger. A receipt is posted to `{ar}` for the amount and
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
absorbs stays in `{ar}` as an unapplied credit **of that customer**, whose
ownership the register records; it is never income. That is this
reconciliation's convention for an aggregate control account, not a
financial-statement presentation rule. Applications run in date order; on one
date credit notes before receipts, receipts in statement order.

A receipt smaller than the invoice it is applied to leaves the balance open.
Where the advice marks an invoice settled and the shortfall — after combining
that advice's lines for that invoice — is `{tolerance}` or less **for that
invoice on that receipt**, the shortfall is written off to `{write_offs}` in a
separate entry dated with the receipt, payee the customer, and the invoice is
closed; above `{tolerance}` nothing is written off and the shortfall remains
open. Nothing is written off without an advice marking the invoice settled.
This exercise authorises those expense write-offs **without a sales-tax
adjustment**; determining the tax treatment of a settlement discount is not
asked of the agent.

Management authorises administrative settlement write-offs of qualifying
shortfalls up to {tolerance} per invoice per receipt, after combining that receipt's
lines for the invoice. A customer's "settled" indication is a claim, not
approval of a credit note. These examples prescribe expense treatment without a
sales-tax adjustment; confirmed price corrections are represented by issued
credit notes.

Once cash or credit is held unapplied, it remains separately recorded for that
customer until a subsequent authorised application or refund is documented.
Issuing another invoice does not automatically apply it. No such subsequent
instruction occurs in these examples.

Reported receivables totals are net operational control-account balances.
Customer debit and credit balances remain separately identifiable;
financial-statement presentation is outside this exercise.

## Credit notes
A credit note reverses the sale and its tax on its date: `Income:Sales` net,
`Liabilities:SalesTax-Payable` tax, `{ar}` gross. It is applied to the invoice
it references up to that invoice's open balance on that date — if that invoice
is already paid, none of it lands there — any excess to the same customer's
other open invoices in invoice-date order, then invoice number, any remainder
held as an unapplied credit of that customer.

The reversal of the sale and its tax belongs to the invoice the note names.
Moving the excess on to another of that customer's open invoices is settlement
of the customer's account, not a further sales or tax reversal against the
invoice that receives it. A credit described only as the reversal of one sale
is limited by that sale's own net and tax amounts, not by what remains unpaid
on it.

{numbering}## Payments to suppliers
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
{company} collects sales tax from customers at {rate}% on sales and owes it to the
state. Purchases of goods for resale are exempt, so no tax is recoverable on
the purchase side.

## Suspense accounts
{company} does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
"""


def policy_text(title: str, company: str, rate: str, *, numbering: str = "") -> str:
    """`policy.md` for one company-month. `title` is the full registered name
    in the heading, `company` the short name the prose uses, `rate` the sales
    tax percentage as it is printed, and `numbering` either
    `NUMBERING_SECTION` or the empty string."""
    return _POLICY.format(title=title, company=company, rate=rate, ar=AR,
                          write_offs=WRITE_OFFS, tolerance=TOLERANCE, numbering=numbering)


def prompt(month: str) -> str:
    """The one instruction, per month. It names the deliverables and the
    evidence and says nothing about what the books will turn out to need:
    not whether a receipt is missing, mis-keyed or booked twice, not whether
    anything is written off, not how much cash or credit is left unapplied."""
    return (
        f"The {month} checking account statement has arrived, together with the remittance advices the customers "
        "sent with their payments, the credit notes issued in the month and the open-item register the month "
        "opened on, and the month needs to be closed. Bring the ledger into agreement with the statement, "
        "following the bookkeeping policy, and write the corrected ledger back to ledger.beancount. Then record "
        "how the period's receipts and credit notes were applied under the policy — which invoices each one "
        "settled and for how much, whatever the policy writes off, whatever is left unapplied, and what each "
        "invoice has remaining — as cash_application.json through write_cash_application."
    )
