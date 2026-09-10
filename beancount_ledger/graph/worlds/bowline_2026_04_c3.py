"""Bowline Marine Supply Co., April 2026 — Case 3, short-pays on both sides of
the tolerance; the write-off omitted.

R3 is 3,660.00 with advice RA-0428-GR: SI-3102 1,790.00 settled with a
40.00 deduction claimed, SI-3104 1,870.00 settled with 20.00 claimed. Under
the policy's tolerance the 20.00 is written off in a separate entry dated
with the receipt and the 40.00 stays open — neither always-write-off nor
never-write-off reproduces both. As found, R3 is booked correctly, R2 is
absent, and the write-off entry the policy makes is missing: the agent must
add it from the advice and the policy.
"""

from __future__ import annotations

from decimal import Decimal as D

from ..derive import TaskSpec
from ..project import MutationPlan, OmitRecognition
from ..schema import AppliedReceipt, CreditNote, ReceiptLine
from . import _bowline as B

CN_0412 = CreditNote("event:cn-0412", "2026-04-15", B.GANNET, "doc:si-3102", "CN-0412", D("250.00"), D("0.08"),
                     "damaged crates")

R3 = AppliedReceipt(
    "event:gr-payrun-0428", "2026-04-28", B.GANNET, D("3660.00"), B.ach_in("2026-04-28"),
    "Customer payment, GR PAYRUN 0428", "GR PAYRUN 0428",
    (ReceiptLine("doc:si-3102", D("1790.00"), True, D("40.00"), "damaged crates; further allowance claimed"),
     ReceiptLine("doc:si-3104", D("1870.00"), True, D("20.00"), "freight overcharge")),
    "RA-0428-GR")

WORLD = B.world("bowline-2026-04-c3", B.april_events(B.r1(), CN_0412, R3))

CASH_APPLICATION_003 = TaskSpec(
    id="cash_application_003",
    type="bank_reconciliation",
    prompt=B.PROMPT,
    period=B.PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_check", "rec:sb-check-2291",
                        "the statement row CHECK 2291 SHEARWATER BAY CHARTERS LLC of 21 April names the remitter "
                        "and the check; customers.csv maps the customer to Assets:AR; the dates section posts an "
                        "entry the books lack on the bank's date"),
        OmitRecognition("omitted_short_payment_write_off", "rec:gr-payrun-0428-writeoff",
                        "the statement row ACH IN GANNET RIGGING INC of 28 April establishes the receipt's amount "
                        "and date; its advice RA-0428-GR marks SI-3104 settled with a 20.00 deduction, and the cash "
                        "application section writes a settled shortfall of 25.00 or less off to "
                        "Expenses:SmallBalanceWriteOffs in a separate entry dated with the receipt"),
    )),
)

TASKS = {CASH_APPLICATION_003.id: CASH_APPLICATION_003}
