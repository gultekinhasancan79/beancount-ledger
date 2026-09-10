"""Bowline Marine Supply Co., April 2026 — Case 2, advice missing for R3; the
statement reference names the invoices.

As Case 1 except that no advice accompanies R3: the pay run is 2,130.00 and
the ACH addendum the bank prints reads `SI-3104 SI-3102`. Policy rung (2)
applies it to the named invoices in invoice-date order, then invoice number
— SI-3102 (open 1,830.00 after R1 and CN-0412) first, then 300.00 to
SI-3104, which stays open — not in the order the reference prints them. The
lines authored below are what that rule reaches; gate (m) holds them to it.
As found, R3 is booked with two digits transposed and R2 is absent.
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
    "event:gr-payrun-0428", "2026-04-28", B.GANNET, D("2130.00"), B.ach_in("2026-04-28"),
    "Customer payment, SI-3104 SI-3102", "SI-3104 SI-3102",
    (ReceiptLine("doc:si-3102", D("1830.00"), True),
     ReceiptLine("doc:si-3104", D("300.00"), False)),
    "")

WORLD = B.world("bowline-2026-04-c2", B.april_events(B.r1(), CN_0412, R3))

CASH_APPLICATION_002 = TaskSpec(
    id="cash_application_002",
    type="bank_reconciliation",
    prompt=B.PROMPT,
    period=B.PERIOD,
    plan=MutationPlan((
        OmitRecognition("unrecorded_customer_check", "rec:sb-check-2291",
                        "the statement row CHECK 2291 SHEARWATER BAY CHARTERS LLC of 21 April names the remitter "
                        "and the check; customers.csv maps the customer to Assets:AR; the dates section posts an "
                        "entry the books lack on the bank's date"),
        AlterRecognition("transposed_payrun_receipt", "rec:gr-payrun-0428", "transpose_digits", 1,
                         "the ledger carries the 28 April ACH receipt from Gannet Rigging Inc at 2310.00 while the "
                         "statement row ACH IN GANNET RIGGING INC of the same date with reference SI-3104 SI-3102 "
                         "shows 2130.00; the entry is re-posted at the statement's amount on the bank's date"),
    )),
)

TASKS = {CASH_APPLICATION_002.id: CASH_APPLICATION_002}
