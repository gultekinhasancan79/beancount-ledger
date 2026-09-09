"""Bowline Marine Supply Co., April 2026 — Case 5, a credit exceeding the
invoice's remaining balance.

SI-3100 originally totalled 1,080.00; the March part payment leaves 300.00
entering April, and `open_items.csv` reports both figures. On 15 April
Bowline issues CN-0412 for an agreed price allowance on goods the customer
retained: 500.00 net, 8% tax, 540.00 gross. No goods are returned and no
inventory moves. The credit policy applies 300.00 to SI-3100 and the 240.00
excess to Gannet's next open invoice by date, SI-3102. R1's zero-payment line
states that SI-3100's balance is withheld pending this allowance.

R3 is 3,780.00 with advice RA-0428-GR applying 1,860.00 to SI-3102 and
1,890.00 to SI-3104: 30.00 is named by nothing, no Gannet invoice is open
after the advice, and the residue is Gannet's unapplied credit inside
Assets:AR. As found, R3 is booked with two digits transposed and R2 is
absent.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..derive import TaskSpec
from ..project import AlterRecognition, MutationPlan, OmitRecognition
from ..schema import AppliedReceipt, CreditNote, ReceiptLine
from . import _bowline as B

CN_0412 = CreditNote("event:cn-0412", "2026-04-15", B.GANNET, "doc:si-3100", "CN-0412", D("500.00"), D("0.08"),
                     "agreed price allowance on goods retained")

R3 = AppliedReceipt(
    "event:gr-payrun-0428", "2026-04-28", B.GANNET, D("3780.00"), B.ach_in("2026-04-28"),
    "Customer payment, GR PAYRUN 0428", "GR PAYRUN 0428",
    (ReceiptLine("doc:si-3102", D("1860.00"), True),
     ReceiptLine("doc:si-3104", D("1890.00"), True)),
    "RA-0428-GR")

WORLD = B.world("bowline-2026-04-c5", B.april_events(
    B.r1("remaining balance withheld pending the agreed price allowance"), CN_0412, R3))

CASH_APPLICATION_005 = TaskSpec(
    id="cash_application_005",
    type="bank_reconciliation",
    prompt=B.PROMPT,
    period=B.PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_check", "rec:sb-check-2291",
                        "the statement row CHECK 2291 SHEARWATER BAY CHARTERS LLC of 21 April names the remitter "
                        "and the check; customers.csv maps the customer to Assets:AR; the dates section posts an "
                        "entry the books lack on the bank's date"),
        AlterRecognition("transposed_payrun_receipt", "rec:gr-payrun-0428", "transpose_digits", 1,
                         "the ledger carries the 28 April ACH receipt from Gannet Rigging Inc at 3870.00 while the "
                         "statement row ACH IN GANNET RIGGING INC of the same date with reference GR PAYRUN 0428 "
                         "shows 3780.00, the amount its remittance advice states; the entry is re-posted at the "
                         "statement's amount on the bank's date"),
    )),
)

TASKS = {CASH_APPLICATION_005.id: CASH_APPLICATION_005}
