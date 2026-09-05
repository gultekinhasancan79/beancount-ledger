"""Maple Street Veterinary Clinic, December 2025: the irreducible facts.

This is the hand-reviewed layer. It states what happened - amounts, dates,
counterparties, documents, rails, clearing dates - and nothing that follows
from it. No posting vector, no closing balance, no target delta, no
statement row appears here; if one of those is wrong, the place to look is
`policy.py` or `project.py`, never this file.

The month is a month-end close. The clinic invoices its kennel, stable and
rescue-society clients on terms and collects by ACH or by check; it buys
drugs and consumables from one supplier on net 30 and pays by ACH quoting
the purchase invoice; it pays rent by check to its landlord and its practice
insurance premium by check to the insurer, a month ahead of the cover. The
task's three mutations name recognitions by id: the January premium check
was never posted, the December service charge was keyed with two digits
transposed, and one client receipt was posted twice. The rent check issued
on 29 December for January is not a mutation at all: the bank cleared it on
6 January, and the December statement's projection classifies it
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
    Prepayment,
    Purchase,
    Rail,
    Sale,
    Settlement,
    VendorPayment,
    World,
)

POLICY_TEXT = """# Maple Street Veterinary Clinic - Bookkeeping Policy

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
settles `Liabilities:AP`.

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

## Sales tax
The clinic collects sales tax from clients on treatment fees and dispensed
medicines and owes it to the state. Drugs and consumables bought for use in
treatment are exempt under the resale certificate, so no tax is recoverable
on the purchase side.

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
"""

OPENED = "2025-01-01"

ACCOUNTS = (
    Account("Assets:Bank:Checking", K.ASSET, "Operating checking account held at Wattle Creek Bank", OPENED, 1000),
    Account("Assets:AR", K.ASSET, "Fees receivable from clients on account", OPENED, 1100),
    Account("Assets:Inventory", K.ASSET, "Drugs, vaccines and surgical consumables held for treatment and dispensing", OPENED, 1200),
    Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
    Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
    Account("Liabilities:SalesTax-Payable", K.LIABILITY, "Sales tax collected from clients and owed to the state", OPENED, 2100),
    Account("Income:Sales", K.INCOME, "Fees for treatments, procedures and dispensed medicines", OPENED, 4000),
    Account("Expenses:COGS", K.EXPENSE, "Cost of drugs and consumables used on treatments", OPENED, 5000),
    Account("Expenses:Rent", K.EXPENSE, "Clinic premises rent for the period", OPENED, 5200),
    Account("Expenses:Insurance", K.EXPENSE, "Practice insurance premium for the month of cover", OPENED, 5250),
    Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
    Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
)

PARTIES = (
    Party("party:tallgrass", "Tallgrass Equestrian Centre", R.CUSTOMER, 1, "net 30", "Assets:AR"),
    Party("party:hollybrook", "Hollybrook Boarding Kennels", R.CUSTOMER, 2, "net 30", "Assets:AR"),
    Party("party:bramblewood", "Bramblewood Animal Rescue", R.CUSTOMER, 3, "net 15", "Assets:AR"),
    Party("party:corbett", "Corbett Veterinary Supplies", R.VENDOR, 4, "net 30", "Assets:Inventory"),
    Party("party:shieldstone", "Shieldstone Mutual Insurance", R.VENDOR, 5, "due on receipt", "Assets:Prepayments"),
    Party("party:kilbride", "Kilbride Property Holdings", R.VENDOR, 6, "due on receipt", "Expenses:Rent"),
    Party("party:wattle-creek-bank", "Wattle Creek Bank", R.BANK, 7),
)

DOCUMENTS = (
    Document("doc:si-7304", DK.SALES_INVOICE, "SI-7304", "party:hollybrook", "2025-10-09", D("2675.00")),
    Document("doc:si-7311", DK.SALES_INVOICE, "SI-7311", "party:tallgrass", "2025-11-18", D("3402.60")),
    Document("doc:si-7313", DK.SALES_INVOICE, "SI-7313", "party:bramblewood", "2025-11-24", D("1027.20")),
    Document("doc:si-7318", DK.SALES_INVOICE, "SI-7318", "party:hollybrook", "2025-12-02", D("2075.80")),
    Document("doc:si-7319", DK.SALES_INVOICE, "SI-7319", "party:tallgrass", "2025-12-05", D("4879.20")),
    Document("doc:si-7320", DK.SALES_INVOICE, "SI-7320", "party:bramblewood", "2025-12-17", D("1353.55")),
    Document("doc:pi-5117", DK.PURCHASE_INVOICE, "PI-5117", "party:corbett", "2025-10-14", D("2913.40")),
    Document("doc:pi-5131", DK.PURCHASE_INVOICE, "PI-5131", "party:corbett", "2025-11-12", D("2486.35")),
    Document("doc:pi-5136", DK.PURCHASE_INVOICE, "PI-5136", "party:corbett", "2025-11-26", D("1742.60")),
    Document("doc:pi-5142", DK.PURCHASE_INVOICE, "PI-5142", "party:corbett", "2025-12-10", D("3118.72")),
    Document("doc:chq-4171", DK.CHEQUE, "4171", "party:kilbride", "2025-11-03"),
    Document("doc:chq-4172", DK.CHEQUE, "4172", "party:shieldstone", "2025-11-14"),
    Document("doc:chq-4173", DK.CHEQUE, "4173", "party:kilbride", "2025-12-01"),
    Document("doc:chq-4174", DK.CHEQUE, "4174", "party:shieldstone", "2025-12-15"),
    Document("doc:chq-4175", DK.CHEQUE, "4175", "party:kilbride", "2025-12-29"),
    # the client's own check, taken at the front desk
    Document("doc:chq-2218", DK.CHEQUE, "2218", "party:bramblewood", "2025-12-09"),
)


def ach_in(on): return Settlement(Rail.ACH_IN, on)
def ach_out(on): return Settlement(Rail.ACH_OUT, on)
def card(on): return Settlement(Rail.CARD, on)
def cheque(doc, on): return Settlement(Rail.CHEQUE, on, doc)


EVENTS = (
    # November 2025: the prior period, known to the bank archive only
    ExpensePayment("event:rent-2025-11", "2025-11-03", "party:kilbride", D("2850.00"),
                   cheque("doc:chq-4171", "2025-11-06"), "November rent, check 4171"),
    CustomerReceipt("event:si-7304-receipt", "2025-11-06", "party:hollybrook", "doc:si-7304", D("2675.00"),
                    ach_in("2025-11-06"), "Client payment settling SI-7304"),
    Purchase("event:pi-5131-purchase", "2025-11-12", "party:corbett", "doc:pi-5131", D("2486.35"),
             "Purchase invoice PI-5131 received, vaccines and dispensary stock"),
    VendorPayment("event:pi-5117-payment", "2025-11-13", "party:corbett", "doc:pi-5117", D("2913.40"),
                  ach_out("2025-11-13"), "Payment of purchase invoice PI-5117"),
    Prepayment("event:insurance-2025-12-prepaid", "2025-11-14", "party:shieldstone", D("612.40"),
               cheque("doc:chq-4172", "2025-11-19"), "2025-12", "Practice insurance premium for December, check 4172"),
    Sale("event:si-7311-sale", "2025-11-18", "party:tallgrass", "doc:si-7311", D("3180.00"), D("0.07"), D("1030.00"),
         "Sale SI-7311, autumn herd health visit and dispensed wormers", "Cost of drugs and consumables on SI-7311"),
    Sale("event:si-7313-sale", "2025-11-24", "party:bramblewood", "doc:si-7313", D("960.00"), D("0.07"), D("305.00"),
         "Sale SI-7313, intake examinations and vaccinations", "Cost of drugs and consumables on SI-7313"),
    Purchase("event:pi-5136-purchase", "2025-11-26", "party:corbett", "doc:pi-5136", D("1742.60"),
             "Purchase invoice PI-5136 received, anaesthetics and suture stock"),
    BankFee("event:fee-2025-11", "2025-11-28", D("46.50"), "Monthly service charge and item fees"),
    # December 2025: the task period
    ExpensePayment("event:rent-2025-12", "2025-12-01", "party:kilbride", D("3187.25"),
                   cheque("doc:chq-4173", "2025-12-04"), "December rent and 2025 common-area charge true-up, check 4173"),
    Sale("event:si-7318-sale", "2025-12-02", "party:hollybrook", "doc:si-7318", D("1940.00"), D("0.07"), D("610.00"),
         "Sale SI-7318, kennel vaccination round and flea treatments", "Cost of drugs and consumables on SI-7318"),
    CustomerReceipt("event:si-7311-receipt", "2025-12-03", "party:tallgrass", "doc:si-7311", D("3402.60"),
                    ach_in("2025-12-03"), "Client payment settling SI-7311"),
    Sale("event:si-7319-sale", "2025-12-05", "party:tallgrass", "doc:si-7319", D("4560.00"), D("0.07"), D("1480.00"),
         "Sale SI-7319, colic surgery and post-operative care", "Cost of drugs and consumables on SI-7319"),
    CustomerReceipt("event:si-7313-receipt", "2025-12-09", "party:bramblewood", "doc:si-7313", D("1027.20"),
                    cheque("doc:chq-2218", "2025-12-17"), "Client check 2218 settling SI-7313"),
    Purchase("event:pi-5142-purchase", "2025-12-10", "party:corbett", "doc:pi-5142", D("3118.72"),
             "Purchase invoice PI-5142 received, vaccines, anaesthetics and surgical consumables"),
    VendorPayment("event:pi-5131-payment", "2025-12-11", "party:corbett", "doc:pi-5131", D("2486.35"),
                  ach_out("2025-12-11"), "Payment of purchase invoice PI-5131"),
    BankFee("event:fee-returned-item-2025-12", "2025-12-12", D("35.00"), "Returned item fee"),
    Prepayment("event:insurance-2026-01-prepaid", "2025-12-15", "party:shieldstone", D("648.90"),
               cheque("doc:chq-4174", "2025-12-18"), "2026-01",
               "Practice insurance premium for January at the renewal rate, check 4174"),
    Sale("event:si-7320-sale", "2025-12-17", "party:bramblewood", "doc:si-7320", D("1265.00"), D("0.07"), D("410.00"),
         "Sale SI-7320, neutering clinic and microchipping", "Cost of drugs and consumables on SI-7320"),
    CustomerReceipt("event:si-7318-receipt", "2025-12-22", "party:hollybrook", "doc:si-7318", D("2075.80"),
                    ach_in("2025-12-22"), "Client payment settling SI-7318"),
    VendorPayment("event:pi-5136-payment", "2025-12-23", "party:corbett", "doc:pi-5136", D("1742.60"),
                  ach_out("2025-12-23"), "Payment of purchase invoice PI-5136"),
    # issued in December, cleared by the bank in January: the timing difference
    Prepayment("event:rent-2026-01-prepaid", "2025-12-29", "party:kilbride", D("2935.50"),
               cheque("doc:chq-4175", "2026-01-06"), "2026-01", "January rent prepaid at the renewed lease rate, check 4175"),
    BankFee("event:fee-2025-12", "2025-12-31", D("51.25"), "Monthly service charge and item fees"),
)

WORLD = World(
    id="maple-2025-12",
    title="Maple Street Veterinary Clinic - FY2025",
    currency="USD",
    bank_account="Assets:Bank:Checking",
    bank_party_id="party:wattle-creek-bank",
    accounts=ACCOUNTS,
    parties=PARTIES,
    documents=DOCUMENTS,
    bank_opening=BankOpening("2025-11-01", D("38412.67")),
    opening=OpeningPosition("2025-12-01", (("Assets:AR", D("4429.80")), ("Assets:Inventory", D("21640.00")),
                                           ("Liabilities:AP", D("-4228.95")))),
    events=EVENTS,
    roles=(("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"), ("prepayments", "Assets:Prepayments"),
           ("payables", "Liabilities:AP"), ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
           ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"), ("opening_equity", "Equity:Opening")),
    policy_text=POLICY_TEXT,
)

MONTH_END_CLOSE_001 = TaskSpec(
    id="month_end_close_001",
    type="bank_reconciliation",
    prompt=("December 2025 is being closed and the Wattle Creek Bank statement for the month is in. The ledger does "
            "not agree with it: the prepaid insurance, the bank charges and the client receipts all differ from "
            "what the statement shows. Correct the books under the bookkeeping policy and write the corrected "
            "ledger back to ledger.beancount."),
    period=Period("2025-12-01", "2025-12-31", "December 2025"),
    plan=MutationPlan((
        OmitRecognition("unrecorded_insurance_prepayment", "rec:insurance-2026-01-prepaid",
                        "the statement row names the check and the insurer (CHECK 4174 SHIELDSTONE MUTUAL INSURANCE, "
                        "648.90 on 18 December) and no ledger entry matches it; vendors.csv books the insurer to "
                        "Assets:Prepayments and the prepayments section says a premium paid in December for January "
                        "cover is a prepayment, and the dates section puts the added entry on the bank's date"),
        AlterRecognition("transposed_service_charge", "rec:fee-2025-12", "transpose_digits", 1,
                         "the ledger carries the 31 December monthly service charge at 52.15 while the statement row "
                         "of the same date shows 51.25; the month-end close checklist says a mis-keyed bank charge "
                         "is re-posted with the statement's amount on the original date, to Expenses:BankFees"),
        DuplicateRecognition("duplicated_client_receipt", "rec:si-7311-receipt",
                             "the ledger carries the 3 December ACH receipt of 3402.60 from Tallgrass Equestrian "
                             "Centre for SI-7311 twice and the statement shows one ACH IN row with that reference; "
                             "the month-end close checklist says to remove one copy and leave the other as it was"),
    )),
)

TASKS = {MONTH_END_CLOSE_001.id: MONTH_END_CLOSE_001}
