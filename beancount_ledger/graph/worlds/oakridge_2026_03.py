"""Oakridge Machining, March 2026: the irreducible facts.

This is the hand-reviewed layer. It states what happened — amounts, dates,
counterparties, documents, rails, clearing dates — and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The shop buys its machine tools outright and pays the equipment supplier by
check on the day the machine is delivered, so an equipment check is the
whole transaction: no payable, no invoice to settle later. The task's three
mutations name recognitions by id: one equipment check the bank cleared and
the books never received, one repair card payment keyed with two digits
transposed, and the month's bank charge. The bandsaw check of 27 March is
not a mutation at all: it is a check the bank cleared on 2 April, and the
March statement's projection classifies it NOT_YET_SETTLED on its own.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..project import AlterRecognition, MutationPlan, OmitRecognition, Period
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

POLICY_TEXT = """# Oakridge Machining — Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, wire fees, returned
item fees) are recorded to `Expenses:BankFees` on the date the bank applies them.

## Customer receipts
Cash received from a customer reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice.

## Payments to suppliers
The `default_account` a supplier carries in the vendor master is where that
supplier's purchases are booked when they arrive. It is not always where a
payment to that supplier lands, and the account itself says which it is.

Where a supplier's purchases are booked to `Assets:Inventory` — the steel and
bar stock suppliers — the material was taken into that account when it was
received and a payable was raised for it at the same time, so cash paid to
that supplier afterwards settles the payable and is recorded to
`Liabilities:AP`.

Where a supplier's purchases are booked to `Assets:Equipment`, the supplier
sells capital equipment, and Oakridge pays for equipment on delivery. No
payable is raised and nothing passes through `Liabilities:AP`: the payment
is the purchase, capitalised as the equipment section below describes. An
equipment supplier is not a stock supplier with an account, even though both
carry an asset account in the vendor master.

Where a supplier's purchases are booked to an expense account, no payable is
raised: the payment is the expense, and it is recorded to that supplier's own
`default_account` on the day it is paid, except where it is paid ahead of the
period it covers, which the prepayments section below governs.

## Equipment
Machine tools and shop equipment are bought from the suppliers the vendor
master carries with `Assets:Equipment` as their default account. Oakridge
pays for a machine by check on the day it is delivered, so the check is the
whole transaction: its amount is capitalised to `Assets:Equipment` on the
date it is paid, and depreciation is dealt with at year end, outside the
monthly close. Suppliers the vendor master carries with `Expenses:Repairs`
as their default account service and repair the machines; their charges are
maintenance, not improvements, and are expensed to `Expenses:Repairs` on the
day they are paid.

An equipment or repair payment the statement shows and the books lack is
posted to that supplier's default account on the date the bank shows. An
equipment or repair payment the books carry with an amount that differs from
the statement's has been keyed wrongly: the entry is re-posted with the
statement's amount, on the date it was originally entered, and the wrong
figure is not left standing alongside it. A check to an equipment supplier
that has not cleared by the cut-off is an outstanding check, governed by the
section below, and is left exactly as recorded.

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
customer or supplier movement the ledger date is never later than the
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
Oakridge collects sales tax from customers on machined parts and fabrication
work and owes it to the state. Steel and bar stock bought for jobs is exempt
under the shop's resale certificate, so no tax is recoverable on the purchase
side.

## Suspense accounts
Oakridge does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
"""

OPENED = "2023-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Shop operating checking account held at Sawmill Creek Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Machining and fabrication charges receivable from customers", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Steel, bar stock and plate held for jobs", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Assets:Equipment", K.ASSET, "Machine tools and shop equipment, at cost", OPENED, 1500),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to stock suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from customers and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Machining and fabrication revenue", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Material consumed on jobs", OPENED, 5000),
    Account("Expenses:Repairs", K.EXPENSE, "Machine repairs and maintenance", OPENED, 5100),
    Account("Expenses:Rent", K.EXPENSE, "Shop premises rent for the period", OPENED, 5200),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:corbett-hydraulics", "Corbett Hydraulics", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:stellan-aero", "Stellan Aero Components", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:penrose-metals", "Penrose Metals", R.VENDOR, 3, "net 30", "Assets:Inventory"),
    Party("party:haldane-machine-tool", "Haldane Machine Tool", R.VENDOR, 4, "due on receipt", "Assets:Equipment"),
    Party("party:brixworth-equipment", "Brixworth Industrial Equipment", R.VENDOR, 5, "due on receipt", "Assets:Equipment"),
    Party("party:wyvern-spindle", "Wyvern Spindle Services", R.VENDOR, 6, "due on receipt", "Expenses:Repairs"),
    Party("party:kilbride-properties", "Kilbride Properties", R.VENDOR, 7, "due on receipt", "Expenses:Rent"),
    Party("party:sawmill-creek-bank", "Sawmill Creek Bank", R.BANK, 8),
)

DOCUMENTS = (
    Document("doc:si-2087", DK.SALES_INVOICE, "SI-2087", "party:corbett-hydraulics", "2026-01-16", D("11384.80")),
    Document("doc:si-2091", DK.SALES_INVOICE, "SI-2091", "party:stellan-aero", "2026-01-23", D("7720.05")),
    Document("doc:si-2095", DK.SALES_INVOICE, "SI-2095", "party:stellan-aero", "2026-02-10", D("6612.60")),
    Document("doc:si-2098", DK.SALES_INVOICE, "SI-2098", "party:corbett-hydraulics", "2026-02-17", D("9603.25")),
    Document("doc:si-2104", DK.SALES_INVOICE, "SI-2104", "party:stellan-aero", "2026-03-11", D("9009.40")),
    Document("doc:si-2105", DK.SALES_INVOICE, "SI-2105", "party:corbett-hydraulics", "2026-03-20", D("5644.25")),
    Document("doc:pi-3306", DK.PURCHASE_INVOICE, "PI-3306", "party:penrose-metals", "2026-01-14", D("6842.50")),
    Document("doc:pi-3321", DK.PURCHASE_INVOICE, "PI-3321", "party:penrose-metals", "2026-02-06", D("5318.40")),
    Document("doc:pi-3338", DK.PURCHASE_INVOICE, "PI-3338", "party:penrose-metals", "2026-03-16", D("4762.15")),
    Document("doc:chq-2101", DK.CHEQUE, "2101", "party:kilbride-properties", "2026-02-02"),
    Document("doc:chq-2102", DK.CHEQUE, "2102", "party:haldane-machine-tool", "2026-02-18"),
    Document("doc:chq-2103", DK.CHEQUE, "2103", "party:kilbride-properties", "2026-03-02"),
    Document("doc:chq-2104", DK.CHEQUE, "2104", "party:brixworth-equipment", "2026-03-05"),
    Document("doc:chq-2105", DK.CHEQUE, "2105", "party:haldane-machine-tool", "2026-03-19"),
    Document("doc:chq-2106", DK.CHEQUE, "2106", "party:brixworth-equipment", "2026-03-27"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # February 2026: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2026-02", "2026-02-02", "party:kilbride-properties", D("4250.00"),
                   cheque("doc:chq-2101", "2026-02-05"), "February shop rent"),
    VendorPayment("event:pi-3306-payment", "2026-02-04", "party:penrose-metals", "doc:pi-3306", D("6842.50"),
                  ach_out("2026-02-04"), "Payment of purchase invoice PI-3306"),
    CustomerReceipt("event:si-2087-receipt", "2026-02-10", "party:corbett-hydraulics", "doc:si-2087", D("11384.80"),
                    ach_in("2026-02-10"), "Customer payment for SI-2087"),
    ExpensePayment("event:repairs-2026-02-vmc", "2026-02-12", "party:wyvern-spindle", D("612.75"),
                   card("2026-02-12"), "Spindle bearing replacement, VMC-2"),
    ExpensePayment("event:lathe-2026-02", "2026-02-18", "party:haldane-machine-tool", D("18900.00"),
                   cheque("doc:chq-2102", "2026-02-23"), "Toolroom lathe, delivered and commissioned, check 2102"),
    CustomerReceipt("event:si-2091-receipt", "2026-02-24", "party:stellan-aero", "doc:si-2091", D("7720.05"),
                    ach_in("2026-02-24"), "Customer payment for SI-2091"),
    BankFee("event:fee-2026-02", "2026-02-27", D("28.00"), "Monthly account service charge"),
    # March 2026: the task period
    ExpensePayment("event:rent-2026-03", "2026-03-02", "party:kilbride-properties", D("4412.50"),
                   cheque("doc:chq-2103", "2026-03-05"), "March shop rent at the reviewed lease rate"),
    VendorPayment("event:pi-3321-payment", "2026-03-04", "party:penrose-metals", "doc:pi-3321", D("5318.40"),
                  ach_out("2026-03-04"), "Payment of purchase invoice PI-3321"),
    ExpensePayment("event:grinder-2026-03", "2026-03-05", "party:brixworth-equipment", D("12485.00"),
                   cheque("doc:chq-2104", "2026-03-10"), "Surface grinder, paid on delivery, check 2104"),
    CustomerReceipt("event:si-2098-receipt", "2026-03-09", "party:corbett-hydraulics", "doc:si-2098", D("9603.25"),
                    ach_in("2026-03-09"), "Customer payment for SI-2098"),
    Sale("event:si-2104-sale", "2026-03-11", "party:stellan-aero", "doc:si-2104", D("8420.00"), D("0.07"), D("3165.00"),
         "Machined actuator housings, 40 off, SI-2104", "Bar stock consumed on SI-2104"),
    ExpensePayment("event:repairs-2026-03-lathe", "2026-03-12", "party:wyvern-spindle", D("1384.20"),
                   card("2026-03-12"), "Coolant pump and way cover repair, CNC lathe"),
    Purchase("event:pi-3338-receipt", "2026-03-16", "party:penrose-metals", "doc:pi-3338", D("4762.15"),
             "Purchase invoice PI-3338 received - 4140 bar and plate"),
    CustomerReceipt("event:si-2095-receipt", "2026-03-17", "party:stellan-aero", "doc:si-2095", D("6612.60"),
                    ach_in("2026-03-17"), "Customer payment for SI-2095"),
    ExpensePayment("event:vmc-2026-03", "2026-03-19", "party:haldane-machine-tool", D("23750.00"),
                   cheque("doc:chq-2105", "2026-03-24"), "CNC vertical machining centre, paid on delivery, check 2105"),
    Sale("event:si-2105-sale", "2026-03-20", "party:corbett-hydraulics", "doc:si-2105", D("5275.00"), D("0.07"), D("1980.00"),
         "Manifold blocks, machined and deburred, SI-2105", "Plate consumed on SI-2105"),
    CustomerReceipt("event:si-2104-receipt", "2026-03-24", "party:stellan-aero", "doc:si-2104", D("9009.40"),
                    ach_in("2026-03-24"), "Customer payment settling SI-2104"),
    ExpensePayment("event:repairs-2026-03-press", "2026-03-26", "party:wyvern-spindle", D("297.60"),
                   card("2026-03-26"), "Hydraulic hose replacement, press brake"),
    # issued in March, cleared by the bank in April: the timing difference
    ExpensePayment("event:bandsaw-2026-03", "2026-03-27", "party:brixworth-equipment", D("7962.50"),
                   cheque("doc:chq-2106", "2026-04-02"), "Horizontal bandsaw, paid on delivery, check 2106"),
    BankFee("event:fee-2026-03", "2026-03-31", D("32.00"), "Monthly account service charge"),
)

WORLD = World(
    id="oakridge-2026-03",
    title="Oakridge Machining - FY2026",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:sawmill-creek-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2026-02-01", D("64800.00")),
    opening=OpeningPosition("2026-03-01", (("Assets:AR", D("16215.85")), ("Assets:Inventory", D("28640.00")),
                                           ("Assets:Equipment", D("164300.00")), ("Liabilities:AP", D("-5318.40")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

FIXED_ASSETS_001 = TaskSpec(
    id="fixed_assets_001",
    type="bank_reconciliation",
    prompt=("The March statement for the shop checking account has arrived. March's equipment purchases were paid by "
            "check on delivery, and neither the fixed-asset ledger nor the bank ledger agrees with the statement. "
            "Work through the differences under the bookkeeping policy, correct the books, and write the corrected "
            "ledger back to ledger.beancount."),
    period=Period("2026-03-01", "2026-03-31", "March 2026"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_equipment_check", "rec:grinder-2026-03",
                        "the statement row CHECK 2104 BRIXWORTH INDUSTRIAL EQUIPMENT of 12,485.00 on 2026-03-10 "
                        "answers no ledger entry; vendors.csv maps Brixworth Industrial Equipment to Assets:Equipment "
                        "and policy.md's Equipment section capitalises a missing equipment check to that account on "
                        "the bank's date"),
        AlterRecognition("miskeyed_repair_card", "rec:repairs-2026-03-lathe", "transpose_digits", 2,
                         "the statement row DEBIT CARD WYVERN SPINDLE SERVICES of 1,384.20 on 2026-03-12 answers the "
                         "ledger's same-day Wyvern Spindle Services entry of 1,348.20 and no other; vendors.csv maps "
                         "Wyvern Spindle Services to Expenses:Repairs and policy.md's Equipment section re-posts a "
                         "mis-keyed repair payment with the statement's amount on its original date"),
        OmitRecognition("unrecorded_bank_fee", "rec:fee-2026-03",
                        "the statement row is a bank-initiated charge with no counterparty; policy.md records bank "
                        "fees to Expenses:BankFees on the date applied"),
    )),
)

TASKS = {FIXED_ASSETS_001.id: FIXED_ASSETS_001}
