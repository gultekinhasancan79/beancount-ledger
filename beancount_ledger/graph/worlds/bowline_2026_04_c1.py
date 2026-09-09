"""Bowline Marine Supply Co., April 2026 — Case 1, the canonical minimum.

R3 is Gannet's pay run of 28 April, 3,720.00, with advice RA-0428-GR applying
1,830.00 to SI-3102 (the cash amount after CN-0412) and 1,890.00 to SI-3104;
CN-0412 of 15 April credits SI-3102 with 250.00 net. SI-3102 is therefore
settled across R1, the credit note and R3. As found, R3 is booked with two
digits transposed and R2 is absent.

The shared facts are in `_bowline.py`; this module states only what varies.
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
    "event:gr-payrun-0428", "2026-04-28", B.GANNET, D("3720.00"), B.ach_in("2026-04-28"),
    "Customer payment, GR PAYRUN 0428", "GR PAYRUN 0428",
    (ReceiptLine("doc:si-3102", D("1830.00"), True, D("0.00"),
                 "Cash amount after application of CN-0412; do not deduct the credit again."),
     ReceiptLine("doc:si-3104", D("1890.00"), True)),
    "RA-0428-GR")

WORLD = B.world("bowline-2026-04-c1", B.april_events(B.r1(), CN_0412, R3))

CASH_APPLICATION_001 = TaskSpec(
    id="cash_application_001",
    type="bank_reconciliation",
    prompt=B.PROMPT,
    period=B.PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_check", "rec:sb-check-2291",
                        "the statement row CHECK 2291 SHEARWATER BAY CHARTERS LLC of 21 April names the remitter "
                        "and the check; customers.csv maps the customer to Assets:AR; the dates section posts an "
                        "entry the books lack on the bank's date"),
        AlterRecognition("transposed_payrun_receipt", "rec:gr-payrun-0428", "transpose_digits", 2,
                         "the ledger carries the 28 April ACH receipt from Gannet Rigging Inc at 3702.00 while the "
                         "statement row ACH IN GANNET RIGGING INC of the same date with reference GR PAYRUN 0428 "
                         "shows 3720.00, the amount its remittance advice states; the entry is re-posted at the "
                         "statement's amount on the bank's date"),
    )),
)

TASKS = {CASH_APPLICATION_001.id: CASH_APPLICATION_001}
