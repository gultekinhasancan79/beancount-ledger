"""Tallowmere Print & Bindery Co., July 2026 — the ADVICE RESIDUE pair.

Two variants of ONE company-month (`six_variant_packs.md`, pair 3 of 3):
trade bindery and short-run print finisher, three customers on two sets of
terms, one paper supplier, Alderwick Mutual Bank, sales tax 5%, six invoices
open at 1 July, two raised in the month, five receipts (four ACH, one
cheque) every one of which binds an advice, and one credit note.

THE ONE STRUCTURAL DIFFERENCE is a single advice cell: RA-0729-QP's SI-7239
line reads 4,020.00 in variant A and 4,560.00 in variant B — that is,
whether the advice's lines exhaust the 8,190.00 the bank shows. Every other
byte of every other public file is identical, and so are the statement's
closing balance, the expected closing `Assets:AR` (5,130.00) and the
expected `Expenses:SmallBalanceWriteOffs` movement (15.00) on a zero opening
balance.

Rung (1) says the part of a payment its advice does not name "is left
unapplied rather than carried on to the rules below". In A the advice names
7,650.00 of an 8,190.00 credit and the payer still has SI-7218 open at
1,620.00 and SI-7239 open at 600.00, so rung (3) had room for the 540.00 and
rung (1) forbids running it: the 540.00 is Quillhaven's unapplied credit
inside `Assets:AR`. In B the same line reads 4,560.00, the advice accounts
for the whole payment and nothing is unapplied. A solver that gets B right
and A wrong has told you exactly one thing: it continued past rung (1).

Two deductions sit on either side of the 25.00 tolerance — 15.00 on SI-7229
is written off (and the entry is already booked), 90.00 on SI-7234 is not
and that invoice stays open at 90.00 — so neither write-off-everything nor
write-off-nothing reproduces the month.

CN-0714's returned goods carry a VALUATION, which the accounting review of
2026-09-11 required: the units came back, were unusable and had no
recoverable resale or salvage value, so the month owes no inventory
reinstatement and no cost-of-sales reversal beside the credit. One field
carries that sentence into both files — `CreditNote.memo` is the `reason`
column of `credit_notes.csv` AND the tail of the ledger narration — so it
must be comma-free (the projector emits those rows unquoted) and short
enough that the narration fits the shipped candidate's 200-code-point cap.
The review's own sentence carries a comma and would have made the narration
242 points, which the parse boundary refuses as `string.too_long`; it is
recast here, not dropped.

The two plants are this month's own recipe — no alteration at all: the
cheque receipt of 20 July is omitted (the repair posts on the bank's date)
and the 24 July ACH receipt is carried twice (the repair removes one copy).
Both sit on entries with a bank posting, so neither is visible to the
cash-application fold.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..derive import TaskSpec
from ..project import DuplicateRecognition, MutationPlan, OmitRecognition, Period
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

TITLE = "Tallowmere Print & Bindery Co. - FY2026"
CURRENCY = "USD"
BANK_ACCOUNT = "Assets:Bank:Checking"
AR = V.AR
WRITE_OFFS = V.WRITE_OFFS
TAX = D("0.05")

PERIOD = Period("2026-07-01", "2026-07-31", "July 2026")
PROMPT = V.prompt(PERIOD.label.split()[0])

QUILLHAVEN = "party:quillhaven-publishing"
BROADMARSH = "party:broadmarsh-academy"
PELLOW = "party:pellow-dunge"
MERIDIAN = "party:meridian-paper"
BANK = "party:alderwick-mutual"

POLICY_TEXT = V.policy_text("Tallowmere Print & Bindery Co.", "Tallowmere", "5")

OPENED = "2026-01-01"

ACCOUNTS = (
    Account(BANK_ACCOUNT, K.ASSET, "Primary operating checking account held at Alderwick Mutual Bank", OPENED, 1000),
    Account(AR, K.ASSET, "Trade receivables from customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Goods held for resale", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Revenue from goods sold", OPENED, 4100),
    Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account(WRITE_OFFS, K.EXPENSE, "Short payments within the cash application tolerance written off on receipt", OPENED, 5400),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party(QUILLHAVEN, "Quillhaven Publishing House", R.CUSTOMER, 1, "net 30", AR),
    Party(BROADMARSH, "Broadmarsh Academy Trust", R.CUSTOMER, 2, "net 45", AR),
    Party(PELLOW, "Pellow & Dunge Stationers", R.CUSTOMER, 3, "net 30", AR),
    Party(MERIDIAN, "Meridian Paper Mills", R.VENDOR, 4, "net 30", "Assets:Inventory"),
    Party(BANK, "Alderwick Mutual Bank", R.BANK, 5),
)

DOCUMENTS = (
    # settled before July, so carried by the archive and not by the register
    Document("doc:si-7213", DK.SALES_INVOICE, "SI-7213", QUILLHAVEN, "2026-05-08", D("5880.00")),
    Document("doc:si-7220", DK.SALES_INVOICE, "SI-7220", BROADMARSH, "2026-05-11", D("3510.00")),
    # the six invoices open at 1 July; SI-7218 was part-paid in June
    Document("doc:si-7218", DK.SALES_INVOICE, "SI-7218", QUILLHAVEN, "2026-05-19", D("6480.00")),
    Document("doc:si-7222", DK.SALES_INVOICE, "SI-7222", BROADMARSH, "2026-05-27", D("3780.00")),
    Document("doc:si-7226", DK.SALES_INVOICE, "SI-7226", QUILLHAVEN, "2026-06-04", D("5250.00")),
    Document("doc:si-7229", DK.SALES_INVOICE, "SI-7229", BROADMARSH, "2026-06-11", D("4410.00")),
    Document("doc:si-7231", DK.SALES_INVOICE, "SI-7231", QUILLHAVEN, "2026-06-16", D("7920.00")),
    Document("doc:si-7234", DK.SALES_INVOICE, "SI-7234", PELLOW, "2026-06-23", D("2835.00")),
    # the two raised in July
    Document("doc:si-7239", DK.SALES_INVOICE, "SI-7239", QUILLHAVEN, "2026-07-08", D("4620.00")),
    Document("doc:si-7242", DK.SALES_INVOICE, "SI-7242", PELLOW, "2026-07-15", D("3360.00")),
    # purchase invoices
    Document("doc:pi-9430", DK.PURCHASE_INVOICE, "PI-9430", MERIDIAN, "2026-05-20", D("6420.00")),
    Document("doc:pi-9451", DK.PURCHASE_INVOICE, "PI-9451", MERIDIAN, "2026-06-15", D("7840.00")),
    # the customer's cheques
    Document("doc:chq-4392", DK.CHEQUE, "4392", BROADMARSH, "2026-06-20"),
    Document("doc:chq-4417", DK.CHEQUE, "4417", BROADMARSH, "2026-07-16"),
)

ROLES = (("receivables", AR), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
         ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
         ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening"),
         ("small_balance_write_offs", WRITE_OFFS))

BANK_OPENING = BankOpening("2026-06-01", D("88478.00"))
OPENING = OpeningPosition("2026-07-01", ((AR, D("25815.00")), ("Assets:Inventory", D("36480.00")),
                                         ("Liabilities:AP", D("-18900.00"))))


def ach_in(on):
    return Settlement(Rail.ACH_IN, on)


def ach_out(on):
    return Settlement(Rail.ACH_OUT, on)


def cheque(doc, on):
    return Settlement(Rail.CHEQUE, on, doc)


#: June 2026: the prior period, known to the bank archive only. The 18 June
#: receipt is what leaves SI-7218 at a balance below its face value.
JUNE_EVENTS = (
    CustomerReceipt("event:si-7213-receipt", "2026-06-05", QUILLHAVEN, "doc:si-7213", D("5880.00"),
                    ach_in("2026-06-05"), "Customer payment for SI-7213"),
    VendorPayment("event:pi-9430-payment", "2026-06-12", MERIDIAN, "doc:pi-9430", D("6420.00"),
                  ach_out("2026-06-12"), "Payment of purchase invoice PI-9430"),
    CustomerReceipt("event:si-7218-part-receipt", "2026-06-18", QUILLHAVEN, "doc:si-7218", D("4860.00"),
                    ach_in("2026-06-18"), "Part payment against SI-7218"),
    CustomerReceipt("event:si-7220-receipt", "2026-06-20", BROADMARSH, "doc:si-7220", D("3510.00"),
                    cheque("doc:chq-4392", "2026-06-24"), "Customer check 4392"),
    BankFee("event:fee-2026-06", "2026-06-30", D("58.00"), "Monthly account service charge"),
)

PI_9451_PAYMENT = VendorPayment("event:pi-9451-payment", "2026-07-06", MERIDIAN, "doc:pi-9451", D("7840.00"),
                                ach_out("2026-07-06"), "Payment of purchase invoice PI-9451")

SALE_7239 = Sale("event:si-7239-sale", "2026-07-08", QUILLHAVEN, "doc:si-7239", D("4400.00"), TAX, D("2640.00"),
                 "Sale SI-7239", "Cost of goods sold on SI-7239")

#: R1: Quillhaven's ACH settlement of 9 July with advice RA-0709-QP. It
#: settles SI-7231 and part-pays SI-7226; amount matching would instead have
#: found the exact pair SI-7218 + SI-7231, closing the invoice the payer's
#: later advice explicitly withholds.
R1 = AppliedReceipt(
    "event:qph-settlement-0709", "2026-07-09", QUILLHAVEN, D("9540.00"), ach_in("2026-07-09"),
    "Customer payment, QPH SETTLEMENT 0709", "QPH SETTLEMENT 0709",
    (ReceiptLine("doc:si-7231", D("7920.00"), True),
     ReceiptLine("doc:si-7226", D("1620.00"), False, D("0.00"),
                 "part payment; balance held pending the reprint reconciliation")),
    "RA-0709-QP")

#: CN-0714. Its 600.00 net and 30.00 tax are inside SI-7222's own original
#: sale — 3,780.00 gross is 3,600.00 net plus 180.00 of tax at 5% — and the
#: memo states what became of the returned units, which is why the month
#: carries no inventory reinstatement beside the credit. Comma-free, because
#: `credit_notes.csv` is emitted unquoted; 161 code points, so the ledger
#: narration is 198 and clears the shipped 200-point cap.
CN_0714 = CreditNote("event:cn-0714", "2026-07-14", BROADMARSH, "doc:si-7222", "CN-0714", D("600.00"), TAX,
                     "agreed allowance; returned custom-printed units received 14 July were unusable and had no "
                     "recoverable resale or salvage value; no replacement goods were supplied")

SALE_7242 = Sale("event:si-7242-sale", "2026-07-15", PELLOW, "doc:si-7242", D("3200.00"), TAX, D("1920.00"),
                 "Sale SI-7242", "Cost of goods sold on SI-7242")

#: R2: Broadmarsh's cheque 4417, written on 16 July and shown by the bank on
#: the 20th. It settles the CREDIT-REDUCED balance of SI-7222, and its advice
#: is dated after the note, so re-folding on advice dates changes nothing.
R2 = AppliedReceipt(
    "event:ba-check-4417", "2026-07-16", BROADMARSH, D("3150.00"), cheque("doc:chq-4417", "2026-07-20"),
    "Customer check 4417", "",
    (ReceiptLine("doc:si-7222", D("3150.00"), True, D("0.00"), "net of credit note CN-0714"),),
    "RA-0716-BA")

#: R3: 4,395.00 and a claimed 15.00 make SI-7229's 4,410.00, and the advice
#: marks it settled, so the shortfall is inside the tolerance and is written
#: off. What authorises the expense is management's own settlement
#: tolerance, not an agreed change to the selling price — a price correction
#: the seller had agreed would be represented by a credit note.
R3 = AppliedReceipt(
    "event:bat-remit-0722", "2026-07-22", BROADMARSH, D("4395.00"), ach_in("2026-07-22"),
    "Customer payment, BAT REMIT 0722", "BAT REMIT 0722",
    (ReceiptLine("doc:si-7229", D("4395.00"), True, D("15.00"),
                 "Customer claims a minor carriage discrepancy; the seller has not approved a price reduction."),),
    "RA-0722-BA")

#: R4: the same shape with a 90.00 claim, which is ABOVE the tolerance:
#: nothing is written off and SI-7234 stays open at 90.00.
R4 = AppliedReceipt(
    "event:pds-payrun-0724", "2026-07-24", PELLOW, D("2745.00"), ach_in("2026-07-24"),
    "Customer payment, PDS PAYRUN 0724", "PDS PAYRUN 0724",
    (ReceiptLine("doc:si-7234", D("2745.00"), True, D("90.00"), "damaged spines claimed; credit requested"),),
    "RA-0724-PD")

FEE_JULY = BankFee("event:fee-2026-07", "2026-07-31", D("62.00"), "Monthly account service charge")


def r5(on_account) -> AppliedReceipt:
    """R5: Quillhaven's settlement of 29 July, the receipt the pair turns on.
    Same payer, same date, same reference, same 8,190.00 of cash and the same
    third line — a zero-cash statement of dispute over SI-7218, validated
    then skipped. Only the SI-7239 line's cash differs, and with it whether
    the advice accounts for the whole payment."""
    return AppliedReceipt(
        "event:qph-settlement-0729", "2026-07-29", QUILLHAVEN, D("8190.00"), ach_in("2026-07-29"),
        "Customer payment, QPH SETTLEMENT 0729", "QPH SETTLEMENT 0729",
        (ReceiptLine("doc:si-7226", D("3630.00"), True, D("0.00"), "balance of the reprint reconciliation"),
         ReceiptLine("doc:si-7239", on_account, False, D("0.00"), "on account against the July binding run"),
         ReceiptLine("doc:si-7218", D("0.00"), False, D("0.00"),
                     "withheld; disputed trimming charge; credit requested")),
        "RA-0729-QP")


R5_A = r5(D("4020.00"))
R5_B = r5(D("4560.00"))


def world(world_id: str, r5_event: AppliedReceipt) -> World:
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
        events=JUNE_EVENTS + (PI_9451_PAYMENT, SALE_7239, R1, CN_0714, SALE_7242, R2, R3, R4, r5_event, FEE_JULY),
        roles=ROLES,
        policy_text=POLICY_TEXT,
    )


PLAN = MutationPlan((
    OmitRecognition(
        "unrecorded_customer_check", "rec:ba-check-4417",
        "the statement row CHECK 4417 BROADMARSH ACADEMY TRUST of 20 July names the remitter and the check, and "
        "the advice RA-0716-BA declares 4417 as the payment's reference; customers.csv maps the customer to "
        "Assets:AR; the dates section posts an entry the books lack on the bank's date"),
    DuplicateRecognition(
        "duplicated_payrun_receipt", "rec:pds-payrun-0724",
        "the statement row ACH IN PELLOW & DUNGE STATIONERS of 24 July with reference PDS PAYRUN 0724 is one "
        "receipt, and the books carry the entry twice against it; the matching section treats one statement row "
        "and one ledger entry of the same amount and counterparty as one item, so the second copy is removed"),
))

WORLD_A = world("tallowmere-2026-07-ar-a", R5_A)
WORLD_B = world("tallowmere-2026-07-ar-b", R5_B)

CASH_APPLICATION_010 = TaskSpec(
    id="cash_application_010",
    type="bank_reconciliation",
    prompt=PROMPT,
    period=PERIOD,
    plan=PLAN,
)

CASH_APPLICATION_011 = TaskSpec(
    id="cash_application_011",
    type="bank_reconciliation",
    prompt=PROMPT,
    period=PERIOD,
    plan=PLAN,
)

TASKS = {CASH_APPLICATION_010.id: CASH_APPLICATION_010, CASH_APPLICATION_011.id: CASH_APPLICATION_011}

#: One module, two worlds: the registry and `tests/verify_world.py` read this
#: rather than a single `WORLD`, because the pair is two variants of one
#: company-month and the facts they share are stated once above.
WORLD_BY_TASK = {CASH_APPLICATION_010.id: WORLD_A, CASH_APPLICATION_011.id: WORLD_B}
