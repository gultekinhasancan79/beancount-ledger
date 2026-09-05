"""Falcon Ridge Surveying, February 2026: the irreducible facts.

This is the hand-reviewed layer. It states what happened — amounts, dates,
counterparties, documents, rails, clearing dates — and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The firm's field engineers file expense claims for travel on out-of-town
jobs and for small field supplies bought on site; each employee is a vendor
party whose default account says which expense the claims they file are
booked to, and an approved claim is reimbursed by check. The task's three
mutations name recognitions by id: one reimbursement check the bank cleared
and the books never received, one reimbursement check the books carry
twice, and the month's fleet-fuel card draw keyed with two digits
transposed. Check 2048 is not a mutation at all: it is a check the bank
cleared on 3 March, and the February statement's projection classifies it
NOT_YET_SETTLED on its own.
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

POLICY_TEXT = """# Falcon Ridge Surveying — Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, wire fees, returned
item fees, check printing) are recorded to `Expenses:BankFees` on the date the
bank applies them.

## Customer receipts
Cash received from a client reduces `Assets:AR`. Where the deposit reference
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

## Employee expense claims
Field engineers file expense claims for mileage, lodging and meals on
out-of-town jobs and for small field supplies bought on site. Each employee
who files claims is set up in the vendor master with terms `expense claim` and
a `default_account` that says which expense the claims that employee files are
booked to. No payable is raised for a claim: an approved claim is reimbursed by
check and booked to the employee's `default_account` on the date the check is
issued, and the check number is the claim's reference on the bank statement.

A reimbursement check the statement shows that the books do not carry is
posted, on the date the bank shows, to that employee's `default_account`. A
claim the books carry twice against a single check on the statement has been
posted twice: one copy is removed and the other is left as it stands. A claim
is never split, netted against another employee's claim or held over to the
following month.

## Vehicle and fuel
The survey trucks are fuelled on a fleet fuel card. The card issuer is in the
vendor master with `default_account` `Expenses:Vehicle` and draws the monthly
fuel bill from the operating account by debit card; the draw is booked to
`Expenses:Vehicle` on the day the bank shows it. Where the books carry the
draw at an amount that differs from the statement's, the entry has been keyed
wrongly: it is re-posted with the statement's amount on the date it was
originally entered, and the wrong figure is not left standing alongside it.

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
`Assets:Prepayments` and released to expense in the period they cover. An
annual instrument service contract or software licence paid up front is a
prepayment, not an expense of the month it was paid.

## Sales tax
Falcon Ridge collects sales tax from clients on surveying fees and owes it to
the state. Field consumables bought for use on client jobs are exempt, so no
tax is recoverable on the purchase side.

## Suspense accounts
Falcon Ridge does not operate a suspense or plug account. Every posting is
made to the account that reflects the underlying transaction.
"""

OPENED = "2024-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Tamarack Valley Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Surveying fees receivable from clients", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Field consumables held in stores - hubs, lath, rebar caps, flagging, paint", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from clients and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Surveying fees billed to clients", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Field consumables issued to client jobs", OPENED, 5000),
    Account("Expenses:Travel", K.EXPENSE, "Crew mileage, lodging and meals on out-of-town jobs, reimbursed on expense claims", OPENED, 5100),
    Account("Expenses:FieldSupplies", K.EXPENSE, "Small field supplies bought on site by crews, reimbursed on expense claims", OPENED, 5200),
    Account("Expenses:Vehicle", K.EXPENSE, "Fuel and running costs of the survey trucks", OPENED, 5300),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5400),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:wexford-homes", "Wexford Homes LLC", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:talbot-creek", "Talbot Creek Developments", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:plumbline", "Plumbline Instruments Inc", R.VENDOR, 3, "net 30", "Assets:Inventory"),
    Party("party:fuelwise", "Fuelwise Fleet Card", R.VENDOR, 4, "due on receipt", "Expenses:Vehicle"),
    Party("party:ruth-abernathy", "Ruth Abernathy", R.VENDOR, 5, "expense claim", "Expenses:Travel"),
    Party("party:dev-ramaswamy", "Dev Ramaswamy", R.VENDOR, 6, "expense claim", "Expenses:Travel"),
    Party("party:caleb-ostrowski", "Caleb Ostrowski", R.VENDOR, 7, "expense claim", "Expenses:FieldSupplies"),
    Party("party:marisol-fuentes", "Marisol Fuentes", R.VENDOR, 8, "expense claim", "Expenses:FieldSupplies"),
    Party("party:tamarack-valley-bank", "Tamarack Valley Bank", R.BANK, 9),
)

DOCUMENTS = (
    Document("doc:si-0871", DK.SALES_INVOICE, "SI-0871", "party:wexford-homes", "2025-12-15", D("6480.00")),
    Document("doc:si-0879", DK.SALES_INVOICE, "SI-0879", "party:wexford-homes", "2026-01-19", D("4815.50")),
    Document("doc:si-0881", DK.SALES_INVOICE, "SI-0881", "party:talbot-creek", "2026-01-26", D("7276.00")),
    Document("doc:si-0884", DK.SALES_INVOICE, "SI-0884", "party:wexford-homes", "2026-02-06", D("5778.00")),
    Document("doc:si-0886", DK.SALES_INVOICE, "SI-0886", "party:talbot-creek", "2026-02-17", D("8827.50")),
    Document("doc:pi-3302", DK.PURCHASE_INVOICE, "PI-3302", "party:plumbline", "2025-12-12", D("1725.60")),
    Document("doc:pi-3309", DK.PURCHASE_INVOICE, "PI-3309", "party:plumbline", "2026-01-15", D("2348.20")),
    Document("doc:pi-3318", DK.PURCHASE_INVOICE, "PI-3318", "party:plumbline", "2026-02-11", D("1964.80")),
    Document("doc:chq-2041", DK.CHEQUE, "2041", "party:ruth-abernathy", "2026-01-05"),
    Document("doc:chq-2042", DK.CHEQUE, "2042", "party:caleb-ostrowski", "2026-01-20"),
    Document("doc:chq-2043", DK.CHEQUE, "2043", "party:ruth-abernathy", "2026-02-03"),
    Document("doc:chq-2044", DK.CHEQUE, "2044", "party:dev-ramaswamy", "2026-02-05"),
    Document("doc:chq-2045", DK.CHEQUE, "2045", "party:caleb-ostrowski", "2026-02-09"),
    Document("doc:chq-2046", DK.CHEQUE, "2046", "party:marisol-fuentes", "2026-02-12"),
    Document("doc:chq-2047", DK.CHEQUE, "2047", "party:ruth-abernathy", "2026-02-19"),
    Document("doc:chq-2048", DK.CHEQUE, "2048", "party:caleb-ostrowski", "2026-02-26"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # January 2026: the prior period, known to the bank archive only
    ExpensePayment("event:claim-2041-abernathy", "2026-01-05", "party:ruth-abernathy", D("412.75"),
                   cheque("doc:chq-2041", "2026-01-08"), "Expense claim - mileage and lodging, Wexford boundary retracement"),
    CustomerReceipt("event:si-0871-receipt", "2026-01-07", "party:wexford-homes", "doc:si-0871", D("6480.00"),
                    ach_in("2026-01-07"), "Customer payment for SI-0871"),
    ExpensePayment("event:fuel-2026-01", "2026-01-09", "party:fuelwise", D("638.42"),
                   card("2026-01-09"), "Fleet fuel card - December statement"),
    VendorPayment("event:pi-3302-payment", "2026-01-14", "party:plumbline", "doc:pi-3302", D("1725.60"),
                  ach_out("2026-01-14"), "Payment of purchase invoice PI-3302"),
    ExpensePayment("event:claim-2042-ostrowski", "2026-01-20", "party:caleb-ostrowski", D("186.30"),
                   cheque("doc:chq-2042", "2026-01-23"), "Expense claim - lath, flagging and marking paint bought on site"),
    BankFee("event:fee-2026-01", "2026-01-30", D("18.00"), "Monthly account service charge"),
    # February 2026: the task period
    ExpensePayment("event:claim-2043-abernathy", "2026-02-03", "party:ruth-abernathy", D("547.90"),
                   cheque("doc:chq-2043", "2026-02-06"), "Expense claim - mileage and two nights lodging, Talbot Creek topo"),
    ExpensePayment("event:claim-2044-ramaswamy", "2026-02-05", "party:dev-ramaswamy", D("683.25"),
                   cheque("doc:chq-2044", "2026-02-10"), "Expense claim - mileage, lodging and meals, Wexford phase 2 layout"),
    Sale("event:si-0884-sale", "2026-02-06", "party:wexford-homes", "doc:si-0884", D("5400.00"), D("0.07"), D("142.50"),
         "Phase 2 construction staking SI-0884", "Hubs and lath issued on SI-0884"),
    ExpensePayment("event:claim-2045-ostrowski", "2026-02-09", "party:caleb-ostrowski", D("158.64"),
                   cheque("doc:chq-2045", "2026-02-13"), "Expense claim - rebar caps and flagging bought on site"),
    CustomerReceipt("event:si-0879-receipt", "2026-02-09", "party:wexford-homes", "doc:si-0879", D("4815.50"),
                    ach_in("2026-02-09"), "Customer payment for SI-0879"),
    ExpensePayment("event:fuel-2026-02", "2026-02-11", "party:fuelwise", D("712.86"),
                   card("2026-02-11"), "Fleet fuel card - January statement"),
    Purchase("event:pi-3318-receipt", "2026-02-11", "party:plumbline", "doc:pi-3318", D("1964.80"),
             "Purchase invoice PI-3318 received - hubs, lath and marking paint"),
    VendorPayment("event:pi-3309-payment", "2026-02-12", "party:plumbline", "doc:pi-3309", D("2348.20"),
                  ach_out("2026-02-12"), "Payment of purchase invoice PI-3309"),
    ExpensePayment("event:claim-2046-fuentes", "2026-02-12", "party:marisol-fuentes", D("231.48"),
                   cheque("doc:chq-2046", "2026-02-17"), "Expense claim - marking paint, nails and whiskers bought on site"),
    Sale("event:si-0886-sale", "2026-02-17", "party:talbot-creek", "doc:si-0886", D("8250.00"), D("0.07"), D("218.75"),
         "Topographic survey and ALTA update SI-0886", "Rebar caps and monuments issued on SI-0886"),
    CustomerReceipt("event:si-0881-receipt", "2026-02-19", "party:talbot-creek", "doc:si-0881", D("7276.00"),
                    ach_in("2026-02-19"), "Customer payment for SI-0881"),
    ExpensePayment("event:claim-2047-abernathy", "2026-02-19", "party:ruth-abernathy", D("396.10"),
                   cheque("doc:chq-2047", "2026-02-24"), "Expense claim - mileage and lodging, Talbot Creek ALTA fieldwork"),
    CustomerReceipt("event:si-0884-receipt", "2026-02-25", "party:wexford-homes", "doc:si-0884", D("5778.00"),
                    ach_in("2026-02-25"), "Customer payment settling SI-0884"),
    # issued in February, cleared by the bank in March: the timing difference
    ExpensePayment("event:claim-2048-ostrowski", "2026-02-26", "party:caleb-ostrowski", D("264.30"),
                   cheque("doc:chq-2048", "2026-03-03"), "Expense claim - flagging and hub stakes bought on site, check 2048"),
    BankFee("event:fee-2026-02", "2026-02-27", D("47.25"), "Monthly service charge and check printing order"),
)

WORLD = World(
    id="falcon-2026-02",
    title="Falcon Ridge Surveying - FY2026",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:tamarack-valley-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2026-01-01", D("31842.15")),
    opening=OpeningPosition("2026-02-01", (("Assets:AR", D("14360.25")), ("Assets:Inventory", D("3275.40")),
                                           ("Liabilities:AP", D("-2348.20")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

EXPENSE_REPORTS_001 = TaskSpec(
    id="expense_reports_001",
    type="bank_reconciliation",
    prompt=("February's employee expense claims were all reimbursed by check, and the claims register does not agree "
            "with the February statement for the operating checking account. Work through the differences under the "
            "bookkeeping policy, correct the books, and write the corrected ledger back to ledger.beancount."),
    period=Period("2026-02-01", "2026-02-28", "February 2026"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_reimbursement_check", "rec:claim-2046-fuentes",
                        "the statement row CHECK 2046 MARISOL FUENTES of 231.48 on 2026-02-17 answers no ledger "
                        "entry; vendors.csv maps Marisol Fuentes to Expenses:FieldSupplies with terms expense claim "
                        "and policy.md's Employee expense claims section posts a missing reimbursement check to the "
                        "employee's default account on the bank's date"),
        DuplicateRecognition("reimbursement_check_posted_twice", "rec:claim-2044-ramaswamy",
                             "the statement carries CHECK 2044 DEV RAMASWAMY of 683.25 once, on 2026-02-10, while "
                             "the ledger carries the 2026-02-05 Dev Ramaswamy reimbursement of 683.25 twice; "
                             "policy.md's Employee expense claims section removes one copy of a claim posted twice"),
        AlterRecognition("miskeyed_fuel_card_draw", "rec:fuel-2026-02", "transpose_digits", 1,
                         "the statement row DEBIT CARD FUELWISE FLEET CARD of 712.86 on 2026-02-11 answers the "
                         "ledger's same-day Fuelwise Fleet Card entry of 721.86 and no other; vendors.csv maps "
                         "Fuelwise Fleet Card to Expenses:Vehicle and policy.md's Vehicle and fuel section re-posts "
                         "a mis-keyed fuel draw with the statement's amount on its original date"),
    )),
)

TASKS = {EXPENSE_REPORTS_001.id: EXPENSE_REPORTS_001}
