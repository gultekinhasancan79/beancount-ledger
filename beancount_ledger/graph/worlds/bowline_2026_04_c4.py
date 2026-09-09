"""Bowline Marine Supply Co., April 2026 — Case 4, short-pays on both sides of
the tolerance; R3 transposed.

R3 is 3,610.00 with advice RA-0428-GR: SI-3102 1,820.00 settled with a
10.00 deduction claimed, SI-3104 1,790.00 settled with 100.00 claimed. The
10.00 is written off; the 100.00 is not, and SI-3104 stays open despite the
customer's claim. As found, R3 is booked with two digits transposed, the
10.00 write-off is booked, and R2 is absent.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..derive import TaskSpec
from ..project import AlterRecognition, MutationPlan, OmitRecognition
from ..schema import AppliedReceipt, CreditNote, ReceiptLine
from . import _bowline as B

CN_0412 = CreditNote("event:cn-0412", "2026-04-15", B.GANNET, "doc:si-3102", "CN-0412", D("250.00"), D("0.08"),
                     "damaged crates")

R3 = AppliedReceipt(
    "event:gr-payrun-0428", "2026-04-28", B.GANNET, D("3610.00"), B.ach_in("2026-04-28"),
    "Customer payment, GR PAYRUN 0428", "GR PAYRUN 0428",
    (ReceiptLine("doc:si-3102", D("1820.00"), True, D("10.00"),
                 "minor remittance discrepancy; customer claims invoice settled"),
     ReceiptLine("doc:si-3104", D("1790.00"), True, D("100.00"), "freight overcharge; credit requested")),
    "RA-0428-GR")

WORLD = B.world("bowline-2026-04-c4", B.april_events(B.r1(), CN_0412, R3))

CASH_APPLICATION_004 = TaskSpec(
    id="cash_application_004",
    type="bank_reconciliation",
    prompt=B.PROMPT,
    period=B.PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_check", "rec:sb-check-2291",
                        "the statement row CHECK 2291 SHEARWATER BAY CHARTERS LLC of 21 April names the remitter "
                        "and the check; customers.csv maps the customer to Assets:AR; the dates section posts an "
                        "entry the books lack on the bank's date"),
        AlterRecognition("transposed_payrun_receipt", "rec:gr-payrun-0428", "transpose_digits", 1,
                         "the ledger carries the 28 April ACH receipt from Gannet Rigging Inc at 3160.00 while the "
                         "statement row ACH IN GANNET RIGGING INC of the same date with reference GR PAYRUN 0428 "
                         "shows 3610.00, the amount its remittance advice states; the entry is re-posted at the "
                         "statement's amount on the bank's date"),
    )),
)

TASKS = {CASH_APPLICATION_004.id: CASH_APPLICATION_004}
