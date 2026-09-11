"""Pennywhistle Bakehouse Co., June 2026 — the CREDIT-NOTE RESIDUE pair.

Two variants of ONE company-month (`six_variant_packs.md`, pair 2 of 3):
wholesale bakery, three trade customers, two suppliers, Fenland Mutual Bank,
sales tax 5%, six invoices open at 1 June, two raised in the month, three
receipts each carrying a bound advice, one credit note, and no deduction
claimed anywhere — so nothing is written off and
`Expenses:SmallBalanceWriteOffs` moves by 0.00 on a zero opening balance.

THE ONE STRUCTURAL DIFFERENCE is CN-0618's amount: gross 3,150.00 in
variant A, 2,940.00 in variant B. Everything else — chart, customers,
register, both sales, all three receipts and their advices, every statement
and archive row, the policy and both plants — is identical. The note moves
no cash, so the statement does not move either; only `credit_notes.csv` and
the three legs of the credit-note entry differ.

2,940.00 is exactly what Marchmont's eligible open invoices absorb on 18
June (SI-5219 at 1,680.00 after the 10 June receipt, then SI-5188 at
1,260.00 as excess). Variant B lands to the cent; variant A overshoots by
210.00, which no open invoice of that customer can take, and that 210.00 is
Marchmont's unapplied credit. The pair asks one question: what happens to
credit that nothing absorbs? The residue may not go anywhere else — SI-5203
is closed by the 10 June receipt, SI-5244 is not raised until 22 June and so
is not open on the note's date, and the other two customers' open invoices
belong to other customers.

WHY SI-5219'S FACE VALUE IS 4,200.00 AND ITS PERIOD BASIS 2,940.00. The
accounting review of 2026-09-11 found that a note described solely as a
spoilage allowance against that one sale must be supported by that sale's
own net and tax. Before the review the invoice's face value was 2,940.00 and
variant A therefore reversed 200.00 of sales value and 10.00 of tax the
named invoice never carried. The correction is made on the SALE, not on the
note: the invoice is raised at 4,200.00 (4,000.00 net and 200.00 of tax) and
part-paid 1,260.00 on 22 May, three days after it was issued. The credit
amounts, the three June receipts, every application and every closing
balance are unchanged, so variant A still leaves 210.00 and variant B leaves
none. Exceeding an invoice's UNPAID BALANCE stays legitimate — that is what
Bowline's shipped Case 5 does — but exceeding the ORIGINAL SALE is not, and
`schema.check_world` now refuses it.

The two plants are this month's own recipe — no omission at all: the 15 June
cheque receipt is carried TWICE and the repair removes one copy, and the 10
June ACH receipt of 5,040.00 is booked at 5,400.00. Both sit on entries with
a bank posting, so neither is visible to the cash-application fold.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..derive import TaskSpec
from ..project import AlterRecognition, DuplicateRecognition, MutationPlan, Period
from ..schema import (
    Account,
    AccountKind as K,
    AppliedReceipt,
    BankFee,
    BankOpening,
    CreditNote,
    CustomerReceipt,
    Document,
    DocumentKind as DK,
    OpeningPosition,
    Party,
    PartyRole as R,
    Rail,
    ReceiptLine,
    Sale,
    Settlement,
    VendorPayment,
    World,
)
from . import _variant_pack as V

TITLE = "Pennywhistle Bakehouse Co. - FY2026"
CURRENCY = "USD"
BANK_ACCOUNT = "Assets:Bank:Checking"
AR = V.AR
WRITE_OFFS = V.WRITE_OFFS
TAX = D("0.05")

PERIOD = Period("2026-06-01", "2026-06-30", "June 2026")
PROMPT = V.prompt(PERIOD.label.split()[0])

MARCHMONT = "party:marchmont-grocers"
CORVID = "party:corvid-coffee"
ASHGROVE = "party:ashgrove-halt"
KIRTLE = "party:kirtle-mill"
REDGATE = "party:redgate-packaging"
BANK = "party:fenland-mutual"

POLICY_TEXT = V.policy_text("Pennywhistle Bakehouse Co.", "Pennywhistle", "5")

OPENED = "2026-01-01"

ACCOUNTS = (
    Account(BANK_ACCOUNT, K.ASSET, "Operating checking account held at Fenland Mutual Bank", OPENED, 1000),
    Account(AR, K.ASSET, "Trade receivables from wholesale customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Ingredients and finished goods held for sale", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Revenue from wholesale bakery sales", OPENED, 4100),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account(WRITE_OFFS, K.EXPENSE, "Short payments within the cash application tolerance written off on receipt", OPENED, 5400),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party(MARCHMONT, "Marchmont Grocers Co-operative", R.CUSTOMER, 1, "net 45", AR),
    Party(CORVID, "Corvid Coffee Houses LLC", R.CUSTOMER, 2, "net 30", AR),
    Party(ASHGROVE, "Ashgrove Halt Refreshments Ltd", R.CUSTOMER, 3, "net 30", AR),
    Party(KIRTLE, "Kirtle Mill Flour Company", R.VENDOR, 4, "net 30", "Assets:Inventory"),
    Party(REDGATE, "Redgate Packaging Supply", R.VENDOR, 5, "net 30", "Assets:Inventory"),
    Party(BANK, "Fenland Mutual Bank", R.BANK, 6),
)

DOCUMENTS = (
    # settled before June, so carried by the archive and not by the register
    Document("doc:si-5174", DK.SALES_INVOICE, "SI-5174", CORVID, "2026-04-08", D("4725.00")),
    Document("doc:si-5182", DK.SALES_INVOICE, "SI-5182", ASHGROVE, "2026-04-27", D("2730.00")),
    # the six invoices open at 1 June; SI-5188 and SI-5219 were part-paid in
    # May, which is what parts their face values from their period bases
    Document("doc:si-5188", DK.SALES_INVOICE, "SI-5188", MARCHMONT, "2026-04-22", D("4410.00")),
    Document("doc:si-5196", DK.SALES_INVOICE, "SI-5196", CORVID, "2026-04-29", D("5250.00")),
    Document("doc:si-5203", DK.SALES_INVOICE, "SI-5203", MARCHMONT, "2026-05-06", D("3780.00")),
    Document("doc:si-5211", DK.SALES_INVOICE, "SI-5211", ASHGROVE, "2026-05-12", D("1995.00")),
    Document("doc:si-5219", DK.SALES_INVOICE, "SI-5219", MARCHMONT, "2026-05-19", D("4200.00")),
    Document("doc:si-5227", DK.SALES_INVOICE, "SI-5227", CORVID, "2026-05-26", D("3150.00")),
    # the two raised in June
    Document("doc:si-5236", DK.SALES_INVOICE, "SI-5236", CORVID, "2026-06-17", D("4200.00")),
    Document("doc:si-5244", DK.SALES_INVOICE, "SI-5244", MARCHMONT, "2026-06-22", D("2625.00")),
    # purchase invoices
    Document("doc:pi-2402", DK.PURCHASE_INVOICE, "PI-2402", KIRTLE, "2026-04-20", D("5940.00")),
    Document("doc:pi-2417", DK.PURCHASE_INVOICE, "PI-2417", KIRTLE, "2026-05-18", D("6480.00")),
    Document("doc:pi-2426", DK.PURCHASE_INVOICE, "PI-2426", REDGATE, "2026-05-26", D("2315.00")),
    # the customer's cheque
    Document("doc:chq-6153", DK.CHEQUE, "6153", CORVID, "2026-06-11"),
)

ROLES = (("receivables", AR), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
         ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
         ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening"),
         ("small_balance_write_offs", WRITE_OFFS))

BANK_OPENING = BankOpening("2026-05-01", D("35360.00"))
OPENING = OpeningPosition("2026-06-01", ((AR, D("18375.00")), ("Assets:Inventory", D("31600.00")),
                                         ("Liabilities:AP", D("-14900.00"))))


def ach_in(on):
    return Settlement(Rail.ACH_IN, on)


def ach_out(on):
    return Settlement(Rail.ACH_OUT, on)


def cheque(doc, on):
    return Settlement(Rail.CHEQUE, on, doc)


#: May 2026: the prior period, known to the bank archive only. Two of its
#: rows are part payments, and the 22 May one — three days after SI-5219 was
#: raised — is what the review of 2026-09-11 required as evidence that the
#: invoice CN-0618 names was originally a 4,200.00 sale.
MAY_EVENTS = (
    CustomerReceipt("event:si-5174-receipt", "2026-05-04", CORVID, "doc:si-5174", D("4725.00"),
                    ach_in("2026-05-04"), "Customer payment for SI-5174"),
    VendorPayment("event:pi-2402-payment", "2026-05-13", KIRTLE, "doc:pi-2402", D("5940.00"),
                  ach_out("2026-05-13"), "Payment of purchase invoice PI-2402"),
    CustomerReceipt("event:si-5188-part-receipt", "2026-05-20", MARCHMONT, "doc:si-5188", D("3150.00"),
                    ach_in("2026-05-20"), "Part payment against SI-5188"),
    CustomerReceipt("event:si-5219-part-receipt", "2026-05-22", MARCHMONT, "doc:si-5219", D("1260.00"),
                    ach_in("2026-05-22"), "Part payment against SI-5219"),
    CustomerReceipt("event:si-5182-receipt", "2026-05-27", ASHGROVE, "doc:si-5182", D("2730.00"),
                    ach_in("2026-05-27"), "Customer payment for SI-5182"),
    BankFee("event:fee-2026-05", "2026-05-29", D("35.00"), "Monthly account service charge"),
)

PI_2417_PAYMENT = VendorPayment("event:pi-2417-payment", "2026-06-05", KIRTLE, "doc:pi-2417", D("6480.00"),
                                ach_out("2026-06-05"), "Payment of purchase invoice PI-2417")

#: R1: Marchmont's ACH pay run of 10 June with advice RA-0610-MG. It settles
#: SI-5203 and puts an explicit part payment against SI-5219, leaving the
#: OLDEST invoice SI-5188 untouched — which is what the amount-matching and
#: oldest-first readings both get wrong.
R1 = AppliedReceipt(
    "event:mg-payrun-0610", "2026-06-10", MARCHMONT, D("5040.00"), ach_in("2026-06-10"),
    "Customer payment, MG PAYRUN 0610", "MG PAYRUN 0610",
    (ReceiptLine("doc:si-5203", D("3780.00"), True),
     ReceiptLine("doc:si-5219", D("1260.00"), False, D("0.00"),
                 "part payment; balance held pending the agreed spoilage allowance")),
    "RA-0610-MG")

#: R2: Corvid's cheque 6153, written on 11 June and shown by the bank on the
#: 15th, with advice RA-0611-CC.
R2 = AppliedReceipt(
    "event:cc-check-6153", "2026-06-11", CORVID, D("5250.00"), cheque("doc:chq-6153", "2026-06-15"),
    "Customer check 6153", "",
    (ReceiptLine("doc:si-5196", D("5250.00"), True),),
    "RA-0611-CC")

SALE_5236 = Sale("event:si-5236-sale", "2026-06-17", CORVID, "doc:si-5236", D("4000.00"), TAX, D("2520.00"),
                 "Sale SI-5236", "Cost of goods sold on SI-5236")
SALE_5244 = Sale("event:si-5244-sale", "2026-06-22", MARCHMONT, "doc:si-5244", D("2500.00"), TAX, D("1500.00"),
                 "Sale SI-5244", "Cost of goods sold on SI-5244")

PI_2426_PAYMENT = VendorPayment("event:pi-2426-payment", "2026-06-19", REDGATE, "doc:pi-2426", D("2315.00"),
                                ach_out("2026-06-19"), "Payment of purchase invoice PI-2426")

#: R3: Corvid's ACH of 26 June with advice RA-0626-CC, an instalment against
#: the NEWEST Corvid invoice while an older one stays open — the second
#: place a fallback reading goes wrong.
R3 = AppliedReceipt(
    "event:cc-ach-0626", "2026-06-26", CORVID, D("2100.00"), ach_in("2026-06-26"),
    "Customer payment, CC ACH 0626", "CC ACH 0626",
    (ReceiptLine("doc:si-5236", D("2100.00"), False, D("0.00"),
                 "instalment on the June delivery; balance to follow"),),
    "RA-0626-CC")

FEE_JUNE = BankFee("event:fee-2026-06", "2026-06-30", D("38.00"), "Monthly account service charge")


def credit_note(net) -> CreditNote:
    """CN-0618, the note the pair turns on. Same date, same customer, same
    invoice, same stated reason in both variants; only the amount differs,
    and with it whether the customer's open invoices absorb it."""
    return CreditNote("event:cn-0618", "2026-06-18", MARCHMONT, "doc:si-5219", "CN-0618", net, TAX,
                      "spoilage allowance on the chilled range")


CN_0618_A = credit_note(D("3000.00"))
CN_0618_B = credit_note(D("2800.00"))


def world(world_id: str, note: CreditNote) -> World:
    return World(
        id=world_id,
        title=TITLE,
        currency=CURRENCY,
        bank_account=BANK_ACCOUNT,
        bank_party_id=BANK,
        accounts=ACCOUNTS,
        parties=PARTIES,
        documents=DOCUMENTS,
        bank_opening=BANK_OPENING,
        opening=OPENING,
        events=MAY_EVENTS + (PI_2417_PAYMENT, R1, R2, SALE_5236, note, PI_2426_PAYMENT, SALE_5244, R3, FEE_JUNE),
        roles=ROLES,
        policy_text=POLICY_TEXT,
    )


PLAN = MutationPlan((
    DuplicateRecognition(
        "duplicated_customer_check", "rec:cc-check-6153",
        "the statement row CHECK 6153 CORVID COFFEE HOUSES LLC of 15 June is one deposit of the cheque the "
        "advice RA-0611-CC declares, and the books carry the entry twice against it; the matching section "
        "treats one statement row and one ledger entry of the same amount and counterparty as one item, so "
        "the second copy is removed"),
    AlterRecognition(
        "transposed_payrun_receipt", "rec:mg-payrun-0610", "transpose_digits", 1,
        "the ledger carries the 10 June ACH receipt from Marchmont Grocers Co-operative at 5400.00 while the "
        "statement row ACH IN MARCHMONT GROCERS CO-OPERATIVE of the same date with reference MG PAYRUN 0610 "
        "shows 5040.00, the amount its remittance advice states; the entry is re-posted at the statement's "
        "amount on the bank's date"),
))

WORLD_A = world("pennywhistle-2026-06-cr-a", CN_0618_A)
WORLD_B = world("pennywhistle-2026-06-cr-b", CN_0618_B)

CASH_APPLICATION_008 = TaskSpec(
    id="cash_application_008",
    type="bank_reconciliation",
    prompt=PROMPT,
    period=PERIOD,
    plan=PLAN,
)

CASH_APPLICATION_009 = TaskSpec(
    id="cash_application_009",
    type="bank_reconciliation",
    prompt=PROMPT,
    period=PERIOD,
    plan=PLAN,
)

TASKS = {CASH_APPLICATION_008.id: CASH_APPLICATION_008, CASH_APPLICATION_009.id: CASH_APPLICATION_009}

#: One module, two worlds: the registry and `tests/verify_world.py` read this
#: rather than a single `WORLD`, because the pair is two variants of one
#: company-month and the facts they share are stated once above.
WORLD_BY_TASK = {CASH_APPLICATION_008.id: WORLD_A, CASH_APPLICATION_009.id: WORLD_B}
