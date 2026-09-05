"""Bluewater Marine Supply, October 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The month is a sales-tax remittance cycle. Bluewater is a chandlery that
collects 8% sales tax on what it sells to three trade customers, carries
the tax as a liability and remits it to the State Department of Revenue by
check the following month; the September return is paid in October, and
September's collected tax is carried into the period as the opening balance
of the liability. The task's three mutations name recognitions by id: the
remittance check was never posted, one customer receipt was keyed with two
digits transposed, and the October bank charge was posted twice. The check
to the rigging supplier issued on 28 October is not a mutation at all: the
bank cleared it on 3 November, and the October statement's projection
classifies it NOT_YET_SETTLED on its own.
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
    Purchase,
    Rail,
    Sale,
    Settlement,
    VendorPayment,
    World,
)

POLICY_TEXT = """# Bluewater Marine Supply - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, check image fees,
returned item fees) are recorded to `Expenses:BankFees` on the date the bank
applies them. A charge the bank applied once is recorded once.

## Customer receipts
Cash received from a customer reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice. Trade
customers pay by ACH quoting the invoice number or by check; a customer's
check is recorded on the day it is received, and the bank's deposit line for
it carries the customer's own check number.

A receipt that was posted with an amount different from the deposit the bank
shows for the same customer and invoice was mis-keyed. It is corrected by
re-posting the entry at the amount the statement shows, on the date the
entry was originally posted. Only the amount changes; the customer, the
invoice and the accounts stay as they were.

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

## Prepayments
Amounts paid before the period they relate to are recorded to
`Assets:Prepayments` and released to expense in the period they cover. Rent
paid in one month for the following month is a prepayment, not an expense of
the month it was paid.

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

## Suspense accounts
Bluewater does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
"""

OPENED = "2025-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Pelican Point Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Trade receivables from customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Chandlery stock held for resale", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Revenue from goods sold", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:Rent", K.EXPENSE, "Store, warehouse and dock frontage rent for the period", OPENED, 5200),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:kittiwake", "Kittiwake Charters", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:osprey-cove", "Osprey Cove Marina", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:tidewater", "Tidewater Boatworks", R.CUSTOMER, 3, "net 15", "Assets:AR"),
    Party("party:seaforth", "Seaforth Cordage and Rigging", R.VENDOR, 4, "net 30", "Assets:Inventory"),
    Party("party:northstar", "Northstar Marine Electronics", R.VENDOR, 5, "net 30", "Assets:Inventory"),
    Party("party:revenue-dept", "State Department of Revenue", R.VENDOR, 6, "monthly filing", "Liabilities:SalesTax-Payable"),
    Party("party:quayside", "Quayside Holdings", R.VENDOR, 7, "due on receipt", "Expenses:Rent"),
    Party("party:pelican-point-bank", "Pelican Point Bank", R.BANK, 8),
)

DOCUMENTS = (
    Document("doc:si-2187", DK.SALES_INVOICE, "SI-2187", "party:tidewater", "2025-08-21", D("5289.30")),
    Document("doc:si-2190", DK.SALES_INVOICE, "SI-2190", "party:osprey-cove", "2025-08-27", D("3844.80")),
    Document("doc:si-2198", DK.SALES_INVOICE, "SI-2198", "party:kittiwake", "2025-09-09", D("6069.60")),
    Document("doc:si-2203", DK.SALES_INVOICE, "SI-2203", "party:osprey-cove", "2025-09-23", D("5266.08")),
    Document("doc:si-2211", DK.SALES_INVOICE, "SI-2211", "party:tidewater", "2025-10-07", D("4225.77")),
    Document("doc:si-2216", DK.SALES_INVOICE, "SI-2216", "party:kittiwake", "2025-10-16", D("7866.72")),
    Document("doc:si-2219", DK.SALES_INVOICE, "SI-2219", "party:osprey-cove", "2025-10-24", D("2859.84")),
    Document("doc:pi-7731", DK.PURCHASE_INVOICE, "PI-7731", "party:seaforth", "2025-08-05", D("3864.20")),
    Document("doc:pi-7740", DK.PURCHASE_INVOICE, "PI-7740", "party:northstar", "2025-08-19", D("2972.15")),
    Document("doc:pi-7752", DK.PURCHASE_INVOICE, "PI-7752", "party:seaforth", "2025-09-16", D("4618.30")),
    Document("doc:pi-7758", DK.PURCHASE_INVOICE, "PI-7758", "party:northstar", "2025-09-25", D("2689.45")),
    Document("doc:pi-7761", DK.PURCHASE_INVOICE, "PI-7761", "party:seaforth", "2025-09-29", D("3377.85")),
    Document("doc:pi-7769", DK.PURCHASE_INVOICE, "PI-7769", "party:northstar", "2025-10-15", D("3146.90")),
    Document("doc:pi-7773", DK.PURCHASE_INVOICE, "PI-7773", "party:seaforth", "2025-10-22", D("2914.60")),
    Document("doc:chq-1141", DK.CHEQUE, "1141", "party:quayside", "2025-09-02"),
    Document("doc:chq-1142", DK.CHEQUE, "1142", "party:seaforth", "2025-09-04"),
    Document("doc:chq-1143", DK.CHEQUE, "1143", "party:revenue-dept", "2025-09-12"),
    Document("doc:chq-1144", DK.CHEQUE, "1144", "party:quayside", "2025-10-02"),
    Document("doc:chq-1145", DK.CHEQUE, "1145", "party:seaforth", "2025-10-03"),
    Document("doc:chq-1146", DK.CHEQUE, "1146", "party:revenue-dept", "2025-10-14"),
    Document("doc:chq-1147", DK.CHEQUE, "1147", "party:seaforth", "2025-10-28"),
    # the customer's own check, deposited on receipt
    Document("doc:chq-5528", DK.CHEQUE, "5528", "party:osprey-cove", "2025-10-20"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # September 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-09", "2025-09-02", "party:quayside", D("4150.00"),
                   cheque("doc:chq-1141", "2025-09-05"), "September rent, store, warehouse and dock frontage"),
    VendorPayment("event:pi-7731-payment", "2025-09-04", "party:seaforth", "doc:pi-7731", D("3864.20"),
                  cheque("doc:chq-1142", "2025-09-09"), "Payment of purchase invoice PI-7731, check 1142"),
    CustomerReceipt("event:si-2187-receipt", "2025-09-10", "party:tidewater", "doc:si-2187", D("5289.30"),
                    ach_in("2025-09-10"), "Customer payment for SI-2187"),
    ExpensePayment("event:salestax-2025-08-remit", "2025-09-12", "party:revenue-dept", D("2104.38"),
                   cheque("doc:chq-1143", "2025-09-16"), "August sales tax return, check 1143"),
    Purchase("event:pi-7752-purchase", "2025-09-16", "party:seaforth", "doc:pi-7752", D("4618.30"),
             "Purchase invoice PI-7752 received, anchor rode and three-strand dock line"),
    VendorPayment("event:pi-7740-payment", "2025-09-18", "party:northstar", "doc:pi-7740", D("2972.15"),
                  ach_out("2025-09-18"), "Payment of purchase invoice PI-7740"),
    CustomerReceipt("event:si-2190-receipt", "2025-09-24", "party:osprey-cove", "doc:si-2190", D("3844.80"),
                    ach_in("2025-09-24"), "Customer payment for SI-2190"),
    Purchase("event:pi-7758-purchase", "2025-09-25", "party:northstar", "doc:pi-7758", D("2689.45"),
             "Purchase invoice PI-7758 received, VHF radios and masthead antennas"),
    Purchase("event:pi-7761-purchase", "2025-09-29", "party:seaforth", "doc:pi-7761", D("3377.85"),
             "Purchase invoice PI-7761 received, shackles, blocks and fenders"),
    BankFee("event:fee-2025-09", "2025-09-30", D("48.00"), "Monthly service charge and check image fees"),
    # October 2025: the task period
    ExpensePayment("event:rent-2025-10", "2025-10-02", "party:quayside", D("4275.00"),
                   cheque("doc:chq-1144", "2025-10-06"),
                   "October rent, store, warehouse and dock frontage, rent review from 1 October"),
    VendorPayment("event:pi-7752-payment", "2025-10-03", "party:seaforth", "doc:pi-7752", D("4618.30"),
                  cheque("doc:chq-1145", "2025-10-08"), "Payment of purchase invoice PI-7752, check 1145"),
    Sale("event:si-2211-sale", "2025-10-07", "party:tidewater", "doc:si-2211", D("3912.75"), D("0.08"), D("2540.00"),
         "Sale SI-2211, anchor rode, fenders and dock lines", "Cost of goods sold on SI-2211"),
    CustomerReceipt("event:si-2198-receipt", "2025-10-09", "party:kittiwake", "doc:si-2198", D("6069.60"),
                    ach_in("2025-10-09"), "Customer payment for SI-2198"),
    ExpensePayment("event:salestax-2025-09-remit", "2025-10-14", "party:revenue-dept", D("2318.46"),
                   cheque("doc:chq-1146", "2025-10-17"), "September sales tax return, check 1146"),
    Purchase("event:pi-7769-purchase", "2025-10-15", "party:northstar", "doc:pi-7769", D("3146.90"),
             "Purchase invoice PI-7769 received, chartplotters and transducers"),
    Sale("event:si-2216-sale", "2025-10-16", "party:kittiwake", "doc:si-2216", D("7284.00"), D("0.08"), D("4690.00"),
         "Sale SI-2216, outboard spares and safety gear for the charter fleet", "Cost of goods sold on SI-2216"),
    CustomerReceipt("event:si-2203-receipt", "2025-10-20", "party:osprey-cove", "doc:si-2203", D("5266.08"),
                    cheque("doc:chq-5528", "2025-10-23"), "Customer check 5528 received for SI-2203"),
    VendorPayment("event:pi-7758-payment", "2025-10-21", "party:northstar", "doc:pi-7758", D("2689.45"),
                  ach_out("2025-10-21"), "Payment of purchase invoice PI-7758"),
    Purchase("event:pi-7773-purchase", "2025-10-22", "party:seaforth", "doc:pi-7773", D("2914.60"),
             "Purchase invoice PI-7773 received, braided dock line and mooring pennants"),
    Sale("event:si-2219-sale", "2025-10-24", "party:osprey-cove", "doc:si-2219", D("2648.00"), D("0.08"), D("1680.00"),
         "Sale SI-2219, antifouling paint and anodes for the winter haul-out", "Cost of goods sold on SI-2219"),
    CustomerReceipt("event:si-2211-receipt", "2025-10-27", "party:tidewater", "doc:si-2211", D("4225.77"),
                    ach_in("2025-10-27"), "Customer payment settling SI-2211"),
    # issued in October, cleared by the bank in November: the timing difference
    VendorPayment("event:pi-7761-payment", "2025-10-28", "party:seaforth", "doc:pi-7761", D("3377.85"),
                  cheque("doc:chq-1147", "2025-11-03"), "Payment of purchase invoice PI-7761, check 1147"),
    BankFee("event:fee-2025-10", "2025-10-31", D("54.00"), "Monthly service charge and check image fees"),
)

WORLD = World(
    id="bluewater-2025-10",
    title="Bluewater Marine Supply - FY2025",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:pelican-point-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-09-01", D("38472.19")),
    opening=OpeningPosition("2025-10-01", (("Assets:AR", D("12706.35")), ("Assets:Inventory", D("41230.00")),
                                           ("Liabilities:AP", D("-12140.85")),
                                           ("Liabilities:SalesTax-Payable", D("-2318.46")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

SALES_TAX_REMITTANCE_001 = TaskSpec(
    id="sales_tax_remittance_001",
    type="bank_reconciliation",
    prompt=("The September sales tax return was filed and remitted to the State Department of Revenue in October, "
            "and October now needs closing. The sales tax ledger and the checking account do not agree with the "
            "Pelican Point Bank statement for October. Reconcile the checking account against the statement, "
            "correct the books under the bookkeeping policy, and write the corrected ledger back to "
            "ledger.beancount."),
    period=Period("2025-10-01", "2025-10-31", "October 2025"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_sales_tax_remittance", "rec:salestax-2025-09-remit",
                        "the statement row names the department and the check number (CHECK 1146 STATE DEPARTMENT "
                        "OF REVENUE) and no ledger entry matches it; vendors.csv lists the department with default "
                        "account Liabilities:SalesTax-Payable and terms of monthly filing, so under the sales-tax "
                        "and sales-tax-remittance sections the check settles that liability, the dates section "
                        "puts it on the bank's date, and the September archive shows the same pattern (CHECK 1143 "
                        "STATE DEPARTMENT OF REVENUE for the August return)"),
        AlterRecognition("transposed_customer_receipt", "rec:si-2198-receipt", "transpose_digits", 2,
                         "the ledger carries the 9 October receipt of SI-2198 from Kittiwake Charters at 6096.60 "
                         "while the statement row of the same date, payer and reference (ACH IN KITTIWAKE "
                         "CHARTERS, SI-2198) shows 6069.60, which is also the invoice gross in the open receivable; "
                         "the customer-receipts section says to re-post the entry at the statement's amount on the "
                         "original date, against Assets:AR"),
        DuplicateRecognition("duplicated_bank_fee", "rec:fee-2025-10",
                             "the ledger carries the 31 October monthly service charge of 54.00 twice and the "
                             "statement shows one bank-initiated row of that amount; the bank-service-charges and "
                             "sales-tax-remittance sections say a charge applied once is recorded once and one "
                             "copy is removed, the other left as it was"),
    )),
)

TASKS = {SALES_TAX_REMITTANCE_001.id: SALES_TAX_REMITTANCE_001}
