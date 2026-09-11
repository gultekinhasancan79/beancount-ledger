"""Thornbury Glassworks LLC, June 2026 — the POLICY FALLBACK pair.

Two variants of ONE company-month (`six_variant_packs.md`, pair 1 of 3):
architectural glazing fabricator, two contract customers on different terms,
one glazing-hardware supplier, Trellis State Bank, sales tax 6%, eight
invoices open at 1 June and no deduction and no write-off anywhere in the
month.

THE ONE STRUCTURAL DIFFERENCE is R3's amount — 26,868.00 in variant A,
21,000.00 in variant B — and nothing else: same parties, same chart, same
opening register, same in-month sales, same credit note, same advice, same
statement references, same plants, one authored `transpose_digits(1)` for
both. The pair asks one question: does the fold continue past the invoices
the statement reference names?

  * A — 26,868.00 exceeds the 23,968.00 the three named invoices are open
    for, so rung (2) closes all three and the 2,900.00 remainder falls to
    rung (3), oldest first, onto SI-4371, which the reference never names.
  * B — 21,000.00 runs out inside the third named invoice, SI-4402 takes
    4,452.00 and stays open, and rung (3) never runs.

A rung-(3) remainder makes the target receipt's OWN ordering unobservable —
a receipt reaches rung (3) only after closing every named invoice, and
closing all of them is the same set of applications in any order. So the
month carries a SECOND un-adviced multi-invoice receipt, R2 on the other
customer, identical in both variants, whose cash is short of its named
total; the published order (invoice date, then invoice number) decides it,
and the `printed_order` and `number_order` readings are defeated in both
variants there. Each customer's invoice numbers run against its invoice
dates, which `## Sales invoice numbering` states as a fact of the business
without restating the ordering rule.

The two plants sit on customer receipts with a bank posting, so neither is
visible to the cash-application fold: R2 is omitted (the books carry no
entry for it; the repair posts on the bank's date) and R3 is booked with two
digits transposed. Nothing derived is typed here — the register, the
applications and the closing balances are folds of these facts.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..derive import TaskSpec
from ..project import AlterRecognition, MutationPlan, OmitRecognition, Period
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

TITLE = "Thornbury Glassworks LLC - FY2026"
CURRENCY = "USD"
BANK_ACCOUNT = "Assets:Bank:Checking"
AR = V.AR
WRITE_OFFS = V.WRITE_OFFS
TAX = D("0.06")

PERIOD = Period("2026-06-01", "2026-06-30", "June 2026")
PROMPT = V.prompt(PERIOD.label.split()[0])

MARROWBONE = "party:marrowbone-construction"
PINEFALL = "party:pinefall-hospitality"
RIDGEWAY = "party:ridgeway-sash"
BANK = "party:trellis-bank"

POLICY_TEXT = V.policy_text("Thornbury Glassworks LLC", "Thornbury", "6", numbering=V.NUMBERING_SECTION)

OPENED = "2026-01-01"

ACCOUNTS = (
    Account(BANK_ACCOUNT, K.ASSET, "Primary operating checking account held at Trellis State Bank", OPENED, 1000),
    Account(AR, K.ASSET, "Trade receivables from customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Fabricated glazing units and stock materials held for contracts", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Revenue from fabricated glazing supplied to contracts", OPENED, 4100),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account(WRITE_OFFS, K.EXPENSE, "Short payments within the cash application tolerance written off on receipt", OPENED, 5400),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party(MARROWBONE, "Marrowbone Construction Group", R.CUSTOMER, 1, "net 30", AR),
    Party(PINEFALL, "Pinefall Hospitality Partners", R.CUSTOMER, 2, "net 45", AR),
    Party(RIDGEWAY, "Ridgeway Sash & Hardware Co", R.VENDOR, 3, "net 30", "Assets:Inventory"),
    Party(BANK, "Trellis State Bank", R.BANK, 4),
)

DOCUMENTS = (
    # settled before June, so carried by the archive and not by the register
    Document("doc:si-4368", DK.SALES_INVOICE, "SI-4368", PINEFALL, "2026-03-12", D("11240.00")),
    Document("doc:si-4380", DK.SALES_INVOICE, "SI-4380", MARROWBONE, "2026-04-25", D("7600.00")),
    # the eight invoices open at 1 June, in (issued, number) order; SI-4371
    # was part-paid in May, which is what parts its face value from its
    # period basis
    Document("doc:si-4386", DK.SALES_INVOICE, "SI-4386", PINEFALL, "2026-03-24", D("4240.00")),
    Document("doc:si-4371", DK.SALES_INVOICE, "SI-4371", MARROWBONE, "2026-03-30", D("18550.00")),
    Document("doc:si-4390", DK.SALES_INVOICE, "SI-4390", PINEFALL, "2026-04-03", D("8480.00")),
    Document("doc:si-4377", DK.SALES_INVOICE, "SI-4377", PINEFALL, "2026-04-14", D("6890.00")),
    Document("doc:si-4408", DK.SALES_INVOICE, "SI-4408", MARROWBONE, "2026-04-22", D("9540.00")),
    Document("doc:si-4383", DK.SALES_INVOICE, "SI-4383", PINEFALL, "2026-04-28", D("5300.00")),
    Document("doc:si-4396", DK.SALES_INVOICE, "SI-4396", MARROWBONE, "2026-05-06", D("12720.00")),
    Document("doc:si-4402", DK.SALES_INVOICE, "SI-4402", MARROWBONE, "2026-05-19", D("7420.00")),
    # the two raised in June
    Document("doc:si-4415", DK.SALES_INVOICE, "SI-4415", MARROWBONE, "2026-06-11", D("6360.00")),
    Document("doc:si-4419", DK.SALES_INVOICE, "SI-4419", PINEFALL, "2026-06-16", D("10600.00")),
    # purchase invoices
    Document("doc:pi-9188", DK.PURCHASE_INVOICE, "PI-9188", RIDGEWAY, "2026-04-10", D("9880.00")),
    Document("doc:pi-9214", DK.PURCHASE_INVOICE, "PI-9214", RIDGEWAY, "2026-05-15", D("12640.00")),
)

ROLES = (("receivables", AR), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
         ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
         ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening"),
         ("small_balance_write_offs", WRITE_OFFS))

BANK_OPENING = BankOpening("2026-05-01", D("110275.00"))
OPENING = OpeningPosition("2026-06-01", ((AR, D("63890.00")), ("Assets:Inventory", D("41800.00")),
                                         ("Liabilities:AP", D("-18250.00"))))


def ach_in(on):
    return Settlement(Rail.ACH_IN, on)


def ach_out(on):
    return Settlement(Rail.ACH_OUT, on)


#: May 2026: the prior period, known to the bank archive only. The 20 May
#: receipt is what leaves SI-4371 at a balance below its face value.
MAY_EVENTS = (
    VendorPayment("event:pi-9188-payment", "2026-05-04", RIDGEWAY, "doc:pi-9188", D("9880.00"),
                  ach_out("2026-05-04"), "Payment of purchase invoice PI-9188"),
    CustomerReceipt("event:si-4368-receipt", "2026-05-12", PINEFALL, "doc:si-4368", D("11240.00"),
                    ach_in("2026-05-12"), "Customer payment for SI-4368"),
    CustomerReceipt("event:si-4371-part-receipt", "2026-05-20", MARROWBONE, "doc:si-4371", D("9250.00"),
                    ach_in("2026-05-20"), "Part payment against SI-4371"),
    CustomerReceipt("event:si-4380-receipt", "2026-05-29", MARROWBONE, "doc:si-4380", D("7600.00"),
                    ach_in("2026-05-29"), "Customer payment for SI-4380"),
    BankFee("event:fee-2026-05", "2026-05-31", D("85.00"), "Monthly account service charge"),
)

PI_9214_PAYMENT = VendorPayment("event:pi-9214-payment", "2026-06-05", RIDGEWAY, "doc:pi-9214", D("12640.00"),
                                ach_out("2026-06-05"), "Payment of purchase invoice PI-9214")

#: R1: Marrowbone's ACH remittance of 5 June, banked on the 8th, with advice
#: RA-0605-MCG. Three lines accounting for the payment in full; the third is
#: a zero-cash statement of dispute, validated against the register and then
#: skipped. The SI-4371 line states a plain part payment — the accounting
#: review of 2026-09-11 struck the earlier retention-to-practical-completion
#: wording, a continuing commercial condition this pack never models.
R1 = AppliedReceipt(
    "event:mcg-remit-0605", "2026-06-05", MARROWBONE, D("9540.00"), ach_in("2026-06-08"),
    "Customer payment, MCG REMIT 0605", "MCG REMIT 0605",
    (ReceiptLine("doc:si-4371", D("5100.00"), False, D("0.00"),
                 "Partial payment of the invoiced work; the remaining balance is outstanding and is not "
                 "subject to retention or a completion condition."),
     ReceiptLine("doc:si-4396", D("4440.00"), False, D("0.00"),
                 "part payment on account; balance to follow on the next payment run"),
     ReceiptLine("doc:si-4402", D("0.00"), False, D("0.00"), "withheld; site access charge disputed")),
    "RA-0605-MCG")

#: CN-0609: a price allowance on glazing the customer kept. No unit is
#: remade, nothing comes back and no replacement is supplied, so the month
#: owes no inventory or cost-of-sales consequence for it. Its 1,200.00 net
#: and 72.00 tax sit inside SI-4408's own original sale (9,540.00 gross is
#: 9,000.00 net plus 540.00 of tax at 6%), which is what makes it a reversal
#: of that sale rather than an unsupported allowance.
CN_0609 = CreditNote("event:cn-0609", "2026-06-09", MARROWBONE, "doc:si-4408", "CN-0609", D("1200.00"), TAX,
                     "Agreed price allowance for site-damaged glazing retained by the customer; no return or "
                     "replacement goods.")

SALE_4415 = Sale("event:si-4415-sale", "2026-06-11", MARROWBONE, "doc:si-4415", D("6000.00"), TAX, D("3720.00"),
                 "Sale SI-4415", "Cost of goods sold on SI-4415")
SALE_4419 = Sale("event:si-4419-sale", "2026-06-16", PINEFALL, "doc:si-4419", D("10000.00"), TAX, D("6200.00"),
                 "Sale SI-4419", "Cost of goods sold on SI-4419")

#: R2: Pinefall's un-adviced pay run of 17 June. The bank prints its own
#: seven-digit trace ahead of the payer's invoice list, so the row carries a
#: declared payment identity and the invoice list stays what it is —
#: document evidence naming which invoices the payment reaches. The cash is
#: short of the three named balances by 2,650.00, so the published order
#: (invoice date, then invoice number) decides the split and the printed and
#: number orders are both defeated. Identical in both variants.
R2 = AppliedReceipt(
    "event:php-payrun-0617", "2026-06-17", PINEFALL, D("18020.00"), ach_in("2026-06-17"),
    "Customer payment, TRC0617318 SI-4383 SI-4390 SI-4377", "TRC0617318 SI-4383 SI-4390 SI-4377",
    (ReceiptLine("doc:si-4390", D("8480.00"), False),
     ReceiptLine("doc:si-4377", D("6890.00"), False),
     ReceiptLine("doc:si-4383", D("2650.00"), False)),
    "")

FEE_JUNE = BankFee("event:fee-2026-06", "2026-06-30", D("85.00"), "Monthly account service charge")


def r3(amount, lines) -> AppliedReceipt:
    """R3: Marrowbone's un-adviced pay run of 25 June, the receipt the pair
    turns on. Same payer, same date, same trace, same invoice list in both
    variants; only the cash differs, and with it whether rung (2) has a
    remainder for rung (3)."""
    return AppliedReceipt(
        "event:mcg-payrun-0625", "2026-06-25", MARROWBONE, amount, ach_in("2026-06-25"),
        "Customer payment, TRC0625704 SI-4402 SI-4408 SI-4396", "TRC0625704 SI-4402 SI-4408 SI-4396",
        lines, "")


R3_A = r3(D("26868.00"),
          (ReceiptLine("doc:si-4408", D("8268.00"), False),
           ReceiptLine("doc:si-4396", D("8280.00"), False),
           ReceiptLine("doc:si-4402", D("7420.00"), False),
           ReceiptLine("doc:si-4371", D("2900.00"), False)))

R3_B = r3(D("21000.00"),
          (ReceiptLine("doc:si-4408", D("8268.00"), False),
           ReceiptLine("doc:si-4396", D("8280.00"), False),
           ReceiptLine("doc:si-4402", D("4452.00"), False)))


def world(world_id: str, r3_event: AppliedReceipt) -> World:
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
        events=MAY_EVENTS + (PI_9214_PAYMENT, R1, CN_0609, SALE_4415, SALE_4419, R2, r3_event, FEE_JUNE),
        roles=ROLES,
        policy_text=POLICY_TEXT,
    )


OMITTED_R2 = OmitRecognition(
    "unrecorded_customer_receipt", "rec:php-payrun-0617",
    "the statement row ACH IN PINEFALL HOSPITALITY PARTNERS of 17 June names the remitter and prints the bank's "
    "own trace TRC0617318 ahead of the payer's invoice list; customers.csv maps the customer to Assets:AR; the "
    "dates section posts an entry the books lack on the bank's date")


def alter_r3(booked: str, shown: str) -> AlterRecognition:
    return AlterRecognition(
        "transposed_payrun_receipt", "rec:mcg-payrun-0625", "transpose_digits", 1,
        f"the ledger carries the 25 June ACH receipt from Marrowbone Construction Group at {booked} while the "
        f"statement row ACH IN MARROWBONE CONSTRUCTION GROUP of the same date with reference TRC0625704 SI-4402 "
        f"SI-4408 SI-4396 shows {shown}; the entry is re-posted at the statement's amount on the bank's date")


WORLD_A = world("thornbury-2026-06-pf-a", R3_A)
WORLD_B = world("thornbury-2026-06-pf-b", R3_B)

CASH_APPLICATION_006 = TaskSpec(
    id="cash_application_006",
    type="bank_reconciliation",
    prompt=PROMPT,
    period=PERIOD,
    plan=MutationPlan((OMITTED_R2, alter_r3("28668.00", "26868.00"))),
)

CASH_APPLICATION_007 = TaskSpec(
    id="cash_application_007",
    type="bank_reconciliation",
    prompt=PROMPT,
    period=PERIOD,
    plan=MutationPlan((OMITTED_R2, alter_r3("20100.00", "21000.00"))),
)

TASKS = {CASH_APPLICATION_006.id: CASH_APPLICATION_006, CASH_APPLICATION_007.id: CASH_APPLICATION_007}

#: One module, two worlds: the registry and `tests/verify_world.py` read this
#: rather than a single `WORLD`, because the pair is two variants of one
#: company-month and the facts they share are stated once above.
WORLD_BY_TASK = {CASH_APPLICATION_006.id: WORLD_A, CASH_APPLICATION_007.id: WORLD_B}
