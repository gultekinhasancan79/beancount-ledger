"""Alpine Trading Co., November 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened — amounts, dates,
counterparties, documents, rails, clearing dates — and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The task's two omissions name recognitions by id. The outstanding cheque is
not a mutation at all: it is a cheque the bank cleared on 3 December, and
the November statement's projection classifies it NOT_YET_SETTLED on its
own.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..project import MutationPlan, OmitRecognition, Period
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

POLICY_TEXT = """# Alpine Trading Co. — Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, wire fees, returned
item fees) are recorded to `Expenses:BankFees` on the date the bank applies them.

## Customer receipts
Cash received from a customer reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice.

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
An entry carries the date of the transaction — the day a check was issued, a
receipt was received or an invoice was raised — never the date the bank
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
are the same transaction and are treated as one item — not as two that
happen to agree.

## Prepayments
Amounts paid before the period they relate to are recorded to
`Assets:Prepayments` and released to expense in the period they cover. Rent
paid in one month for the following month is a prepayment, not an expense of
the month it was paid.

## Sales tax
Alpine collects sales tax from customers on sales and owes it to the state.
Purchases of goods for resale are exempt, so no tax is recoverable on the
purchase side.

## Suspense accounts
Alpine does not operate a suspense or plug account. Every posting is made to the
account that reflects the underlying transaction.
"""

OPENED = "2025-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Primary operating checking account held at Cascade Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Trade receivables from customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Goods held for resale", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Revenue from goods sold", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:Office", K.EXPENSE, "Office supplies and consumables", OPENED, 5100),
    Account("Expenses:Rent", K.EXPENSE, "Premises rent for the period", OPENED, 5200),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:harbor-freight", "Harbor Freight Ltd", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:summit-wholesale", "Summit Wholesale", R.CUSTOMER, 2, "net 45", "Assets:AR"),
    Party("party:ridgeline-retail", "Ridgeline Retail", R.CUSTOMER, 3, "net 30", "Assets:AR"),
    Party("party:northwind", "Northwind Supplies", R.VENDOR, 4, "net 30", "Assets:Inventory"),
    Party("party:cedar", "Cedar Property Group", R.VENDOR, 5, "due on receipt", "Expenses:Rent"),
    Party("party:office-depot", "Office Depot", R.VENDOR, 6, "due on receipt", "Expenses:Office"),
    Party("party:cascade-bank", "Cascade Bank", R.BANK, 7),
)

DOCUMENTS = (
    Document("doc:si-1029", DK.SALES_INVOICE, "SI-1029", "party:ridgeline-retail", "2025-09-12", D("7250.00")),
    Document("doc:si-1043", DK.SALES_INVOICE, "SI-1043", "party:harbor-freight", "2025-10-17", D("9800.00")),
    Document("doc:si-1044", DK.SALES_INVOICE, "SI-1044", "party:harbor-freight", "2025-11-07", D("4800.00")),
    Document("doc:si-1051", DK.SALES_INVOICE, "SI-1051", "party:summit-wholesale", "2025-11-13", D("14400.00")),
    Document("doc:pi-2180", DK.PURCHASE_INVOICE, "PI-2180", "party:northwind", "2025-09-08", D("4100.00")),
    Document("doc:pi-2211", DK.PURCHASE_INVOICE, "PI-2211", "party:northwind", "2025-10-14", D("6200.00")),
    Document("doc:pi-2240", DK.PURCHASE_INVOICE, "PI-2240", "party:northwind", "2025-11-21", D("5100.00")),
    Document("doc:chq-1036", DK.CHEQUE, "1036", "party:cedar", "2025-10-15"),
    Document("doc:chq-1037", DK.CHEQUE, "1037", "party:cedar", "2025-11-10"),
    Document("doc:chq-1038", DK.CHEQUE, "1038", "party:cedar", "2025-11-28"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # October 2025: the prior period, known to the bank archive only
    VendorPayment("event:pi-2180-payment", "2025-10-02", "party:northwind", "doc:pi-2180", D("4100.00"),
                  ach_out("2025-10-02"), "Payment of purchase invoice PI-2180"),
    CustomerReceipt("event:si-1029-receipt", "2025-10-09", "party:ridgeline-retail", "doc:si-1029", D("7250.00"),
                    ach_in("2025-10-09"), "Customer payment for SI-1029"),
    ExpensePayment("event:rent-2025-10", "2025-10-15", "party:cedar", D("3500.00"),
                   cheque("doc:chq-1036", "2025-10-15"), "October office rent"),
    ExpensePayment("event:office-2025-10", "2025-10-22", "party:office-depot", D("385.00"),
                   card("2025-10-22"), "Office supplies"),
    BankFee("event:fee-2025-10", "2025-10-29", D("115.00"), "Monthly account service charge"),
    # November 2025: the task period
    VendorPayment("event:pi-2211-payment", "2025-11-04", "party:northwind", "doc:pi-2211", D("6200.00"),
                  ach_out("2025-11-04"), "Payment of purchase invoice PI-2211"),
    CustomerReceipt("event:si-1043-receipt", "2025-11-06", "party:harbor-freight", "doc:si-1043", D("9800.00"),
                    ach_in("2025-11-06"), "Customer payment for SI-1043"),
    Sale("event:si-1044-sale", "2025-11-07", "party:harbor-freight", "doc:si-1044", D("4000.00"), D("0.20"), D("2600.00"),
         "Sale SI-1044", "Cost of goods sold on SI-1044"),
    ExpensePayment("event:rent-2025-11", "2025-11-10", "party:cedar", D("3500.00"),
                   cheque("doc:chq-1037", "2025-11-10"), "November office rent"),
    Sale("event:si-1051-sale", "2025-11-13", "party:summit-wholesale", "doc:si-1051", D("12000.00"), D("0.20"), D("7800.00"),
         "Sale SI-1051", "Cost of goods sold on SI-1051"),
    ExpensePayment("event:office-2025-11", "2025-11-18", "party:office-depot", D("420.00"),
                   card("2025-11-18"), "Stationery and printer supplies"),
    Purchase("event:pi-2240-receipt", "2025-11-21", "party:northwind", "doc:pi-2240", D("5100.00"),
             "Purchase invoice PI-2240 received"),
    CustomerReceipt("event:si-1051-receipt", "2025-11-25", "party:summit-wholesale", "doc:si-1051", D("8000.00"),
                    ach_in("2025-11-25"), "Partial payment against SI-1051"),
    CustomerReceipt("event:si-1044-receipt", "2025-11-26", "party:harbor-freight", "doc:si-1044", D("4800.00"),
                    ach_in("2025-11-26"), "Customer payment settling SI-1044"),
    # issued in November, cleared by the bank in December: the timing difference
    Prepayment("event:rent-2025-12-prepaid", "2025-11-28", "party:cedar", D("3500.00"),
               cheque("doc:chq-1038", "2025-12-03"), "2025-12", "December rent prepaid, check 1038"),
    BankFee("event:fee-2025-11", "2025-11-30", D("85.00"), "Monthly account service charge"),
)

WORLD = World(
    id="alpine-2025-11",
    title="Alpine Trading Co. - FY2025",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:cascade-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-10-01", D("43000.00")),
    opening=OpeningPosition("2025-11-01", (("Assets:AR", D("18400.00")), ("Assets:Inventory", D("26000.00")),
                                           ("Liabilities:AP", D("-11300.00")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

BANK_RECON_001 = TaskSpec(
    id="bank_recon_001",
    type="bank_reconciliation",
    prompt=("The November checking account statement has arrived and the month needs to be closed. Bring the ledger "
            "into agreement with the statement, following the bookkeeping policy. Write the corrected ledger back to "
            "ledger.beancount."),
    period=Period("2025-11-01", "2025-11-30", "November 2025"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_deposit", "rec:si-1044-receipt",
                        "the statement row names the payer and the invoice (ACH IN HARBOR FREIGHT LTD, SI-1044); "
                        "customers.csv maps the customer to Assets:AR; the ledger carries the open sale SI-1044"),
        OmitRecognition("unrecorded_bank_fee", "rec:fee-2025-11",
                        "the statement row is a bank-initiated charge with no counterparty; policy.md records bank "
                        "fees to Expenses:BankFees on the date applied"),
    )),
)

TASKS = {BANK_RECON_001.id: BANK_RECON_001}
