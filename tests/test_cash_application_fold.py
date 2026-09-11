"""The public cash-application fold, against the specification's five cases,
its refusal table and its offline fixtures.

`graph/cash_application.py` reads the evidence pack — the eight legacy files
plus `open_items.csv`, `remittance_advice.csv`, `credit_notes.csv` — and
folds it into the register `cash_application.json` must state. Nothing here
comes from a world module: the five cases of spec section 7 are transcribed
as in-test fixtures (the shared company-month, varied in R3, the credit note
and the advice), so what is checked is the fold over bytes shaped exactly
like the projector's, before the projector exists. Step 3 compares the two.

What is witnessed:

  * the module holds the `identify.py` discipline: strings in, stdlib only,
    no route to `schema`, `policy`, `project`, `derive` or `worlds`, and a
    non-mapping input is refused rather than coerced;
  * the five cases fold to the applications, write-offs, credit
    applications, register rows and closing AR section 7 states, and
    Case 1's document is the spec's `piv.cash-application/1` example;
  * every refusal of the U-table the fold owns (U1, U2 in its four forms,
    U3 in its named forms, U4, U5, U6 in both forms, U7, U9 in both forms)
    fires on a minimal violating fixture built from Case 1 by one edit, with
    the spec's name; the two U12 conditions warn and do not refuse;
  * the offline fixtures section 7 requires, each with its expected result:
    a rung-(3) remainder after the reference's named invoices; a credit-note
    residue no other invoice absorbs; an advice residue while another
    invoice of that customer is open (unapplied; the rungs do not run); a
    credit note against a paid invoice (all of it excess); equal invoice
    dates at rung (2), at rung (3) and at the credit-note excess (the
    invoice-id tie-break); a reference whose invoices' date order and number
    order disagree (rung (2) is invoice-date order — printed order and
    number order both lose); deductions of 24.99, 25.00 and 25.01;
  * gate (o): every named baseline is a fixed function; for each case the
    ANY-reading-reaches-truth record matches the spec's narrative, the
    baselines the evidence does not admit are recorded as such, no case is
    refused, and Case 2's invoice-number-order coincidence is a diagnostic.

    python tests/test_cash_application_fold.py
"""

from __future__ import annotations

import ast
import inspect
import re
import sys
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from beancount_ledger.graph import cash_application as CA  # noqa: E402

STDLIB_ONLY = {"__future__", "csv", "io", "itertools", "json", "re", "dataclasses", "datetime", "decimal"}
FORBIDDEN = ("schema", "policy", "project", "derive", "worlds", "canonical", "beancount_ledger")


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:24]:
            print(f"      {line}")
    return ok


# --------------------------------------------------------------------------
# the pack builder: Bowline Marine Supply Co., April 2026
# --------------------------------------------------------------------------

GANNET = "Gannet Rigging Inc"
SHEARWATER = "Shearwater Bay Charters LLC"
BANK = "Assets:Bank:Checking"
AR = "Assets:AR"
CHART = (
    (BANK, "asset", "Primary operating checking account held at Marram Community Bank"),
    (AR, "asset", "Trade receivables from customers"),
    ("Assets:Inventory", "asset", "Goods held for resale"),
    ("Liabilities:AP", "liability", "Trade payables to suppliers"),
    ("Liabilities:SalesTax-Payable", "liability", "Sales tax collected from customers and owed to the state"),
    ("Income:Sales", "income", "Revenue from goods sold"),
    ("Expenses:COGS", "expense", "Cost of goods sold"),
    ("Expenses:BankFees", "expense", "Bank service charges and transaction fees"),
    ("Expenses:SmallBalanceWriteOffs", "expense",
     "Short payments within the cash application tolerance, written off on receipt"),
    ("Equity:Opening", "equity", "Opening balance equity"),
)
CUSTOMERS = ((GANNET, "net 30", AR), (SHEARWATER, "net 30", AR))

#: The opening register every case shares (spec section 2 / 7).
OPEN_ITEMS = (
    ("SI-3100", GANNET, "2026-02-26", "2026-03-28", "1080.00", "300.00"),
    ("SI-3101", GANNET, "2026-03-03", "2026-04-02", "2400.00", "2400.00"),
    ("SI-3102", GANNET, "2026-03-12", "2026-04-11", "3600.00", "3600.00"),
    ("SI-3103", SHEARWATER, "2026-03-18", "2026-04-17", "2970.00", "2970.00"),
)
#: The two in-month sales: (date, customer, number, net, tax, cost).
SALES = (
    ("2026-04-07", GANNET, "SI-3104", "1750.00", "140.00", "1050.00"),
    ("2026-04-14", SHEARWATER, "SI-3105", "2750.00", "220.00", "1650.00"),
)
#: R1 and R2's advices, identical in every case; RA-0428-GR varies.
RA_0410 = (
    ("RA-0410-GR", GANNET, "2026-04-10", "ACH", "GR PAYRUN 0410", "3900.00", "SI-3101", "2400.00", "yes", "0.00", ""),
    ("RA-0410-GR", GANNET, "2026-04-10", "ACH", "GR PAYRUN 0410", "3900.00", "SI-3102", "1500.00", "no", "0.00",
     "part payment; balance held pending credit for damaged crates"),
    ("RA-0410-GR", GANNET, "2026-04-10", "ACH", "GR PAYRUN 0410", "3900.00", "SI-3100", "0.00", "no", "0.00",
     "withheld; short shipment; credit requested"),
)
RA_0416 = (
    ("RA-0416-SB", SHEARWATER, "2026-04-16", "CHECK", "2291", "2970.00", "SI-3103", "2970.00", "yes", "0.00", ""),
)
CN_0412 = ("CN-0412", "2026-04-15", GANNET, "SI-3102", "250.00", "20.00", "270.00", "damaged crates")

R1 = "2026-04-10:GR PAYRUN 0410"
R2 = "2026-04-21:2291"
R3 = "2026-04-28:GR PAYRUN 0428"


def _csv(header, rows) -> str:
    return "\n".join([",".join(header)] + [",".join(r) for r in rows]) + "\n"


def statement_text(rows, opening="60000.00", start="2026-04-01"):
    """rows: (date, description, reference, debit, credit); the balance runs."""
    running = D(opening)
    out = [f"{start},Opening balance carried forward,,,,{running:.2f}"]
    for date, description, reference, debit, credit in rows:
        running += (D(credit) if credit else D(0)) - (D(debit) if debit else D(0))
        out.append(f"{date},{description},{reference},{debit},{credit},{running:.2f}")
    return _csv(CA.STATEMENT_COLUMNS, []) + "\n".join(out) + "\n"


def entry(date, payee, narration, *legs) -> str:
    lines = [f'{date} * "{payee}" "{narration}"']
    for account, amount in legs:
        lines.append(f"  {account:40s} {D(amount):>12.2f} USD")
    return "\n".join(lines) + "\n"


def sale_entries(date, customer, number, net, tax, cost) -> str:
    gross = D(net) + D(tax)
    return (entry(date, customer, f"Sale {number}", (AR, gross), ("Income:Sales", -D(net)),
                  ("Liabilities:SalesTax-Payable", -D(tax)))
            + "\n" + entry(date, customer, f"Cost of goods sold on {number}", ("Expenses:COGS", cost),
                           ("Assets:Inventory", -D(cost))))


def ledger_text(opening_ar, sales, entries, start="2026-04-01", bank_opening="60000.00"):
    head = ['option "title" "Bowline Marine Supply Co."', 'option "operating_currency" "USD"', "",
            "; Chart of accounts"]
    head += [f"2026-01-01 open {name:30s} USD" for name, _, _ in CHART]
    head += ["", f"; Opening balances as of {start}"]
    inventory, payables = D("24000.00"), D("12000.00")
    equity = -(D(bank_opening) + D(opening_ar) + inventory - payables)
    head.append(entry(start, "Opening balance", "Carried forward from March close",
                      (BANK, bank_opening), (AR, opening_ar), ("Assets:Inventory", inventory),
                      ("Liabilities:AP", -payables), ("Equity:Opening", equity)))
    head.append("; April 2026 activity")
    body = [sale_entries(*s) for s in sales] + list(entries)
    return "\n".join(head) + "\n" + "\n".join(body) + "\n"


def pack(*, open_items=OPEN_ITEMS, sales=SALES, statement=(), advice=(), credit_notes=(), entries=(),
         opening_ar=None, customers=CUSTOMERS, chart=CHART) -> dict:
    """The evidence pack as file name -> text, shaped like the projector's."""
    if opening_ar is None:
        opening_ar = sum((D(r[5]) for r in open_items), D(0))
    return {
        "accounts.csv": _csv(("account", "type", "description"), chart),
        "customers.csv": _csv(("customer", "terms", "default_account"), customers),
        "vendors.csv": _csv(("vendor", "terms", "default_account"),
                            (("Northshore Chandlery Supply", "net 30", "Assets:Inventory"),)),
        "open_items.csv": _csv(CA.OPEN_ITEMS_COLUMNS, open_items),
        "remittance_advice.csv": _csv(CA.REMITTANCE_COLUMNS, advice),
        "credit_notes.csv": _csv(CA.CREDIT_NOTE_COLUMNS, credit_notes),
        "bank_statement.csv": statement_text(statement),
        "ledger.beancount": ledger_text(opening_ar, sales, entries),
        "archive_prior_period.csv": _csv(CA.STATEMENT_COLUMNS, []),
        "policy.md": "# Bowline Marine Supply Co. — Bookkeeping Policy\n\n## Cash application\n(see the spec)\n",
        "manifest.md": "# File index\n",
    }


def bowline(case: int, **overrides) -> dict:
    """Section 7's five variants of one company-month."""
    r3_amount = {1: "3720.00", 2: "2130.00", 3: "3660.00", 4: "3610.00", 5: "3780.00"}[case]
    r3_found = {1: "3702.00", 2: "2310.00", 3: "3660.00", 4: "3160.00", 5: "3870.00"}[case]
    r3_reference = "SI-3104 SI-3102" if case == 2 else "GR PAYRUN 0428"
    ra_0428 = {
        1: (("SI-3102", "1830.00", "yes", "0.00", "Cash amount after application of CN-0412; do not deduct the credit again."),
            ("SI-3104", "1890.00", "yes", "0.00", "")),
        2: (),
        3: (("SI-3102", "1790.00", "yes", "40.00", "damaged crates; further allowance claimed"),
            ("SI-3104", "1870.00", "yes", "20.00", "freight overcharge")),
        4: (("SI-3102", "1820.00", "yes", "10.00", "minor remittance discrepancy; customer claims invoice settled"),
            ("SI-3104", "1790.00", "yes", "100.00", "freight overcharge; credit requested")),
        5: (("SI-3102", "1860.00", "yes", "0.00", ""), ("SI-3104", "1890.00", "yes", "0.00", "")),
    }[case]
    ra_0410 = RA_0410 if case != 5 else RA_0410[:2] + (
        RA_0410[2][:10] + ("remaining balance withheld pending the agreed price allowance",),)
    advice = ra_0410 + RA_0416 + tuple(
        ("RA-0428-GR", GANNET, "2026-04-28", "ACH", "GR PAYRUN 0428", r3_amount) + line for line in ra_0428)
    credit = (CN_0412,) if case != 5 else (
        ("CN-0412", "2026-04-15", GANNET, "SI-3100", "500.00", "40.00", "540.00",
         "agreed price allowance on goods retained"),)
    cn_net, cn_tax, cn_gross = credit[0][4], credit[0][5], credit[0][6]
    statement = (
        ("2026-04-09", "ACH OUT NORTHSHORE CHANDLERY SUPPLY", "PI-8813", "4175.00", ""),
        ("2026-04-10", "ACH IN GANNET RIGGING INC", "GR PAYRUN 0410", "", "3900.00"),
        ("2026-04-21", "CHECK 2291 SHEARWATER BAY CHARTERS LLC", "2291", "", "2970.00"),
        ("2026-04-28", "ACH IN GANNET RIGGING INC", r3_reference, "", r3_amount),
        ("2026-04-30", "MONTHLY ACCOUNT SERVICE CHARGE", "", "45.00", ""),
    )
    entries = [
        entry("2026-04-09", "Northshore Chandlery Supply", "Payment of PI-8813", ("Liabilities:AP", "4175.00"),
              (BANK, "-4175.00")),
        entry("2026-04-10", GANNET, "Customer payment, GR PAYRUN 0410", (BANK, "3900.00"), (AR, "-3900.00")),
        entry("2026-04-15", GANNET, "Credit note CN-0412", ("Income:Sales", cn_net),
              ("Liabilities:SalesTax-Payable", cn_tax), (AR, f"-{cn_gross}")),
        entry("2026-04-28", GANNET, "Customer payment, GR PAYRUN 0428", (BANK, r3_found), (AR, f"-{r3_found}")),
    ]
    if case == 4:
        entries.append(entry("2026-04-28", GANNET, "Short payment on SI-3102 written off under the cash "
                             "application policy", ("Expenses:SmallBalanceWriteOffs", "10.00"), (AR, "-10.00")))
    entries.append(entry("2026-04-30", "Marram Community Bank", "Monthly account service charge",
                         ("Expenses:BankFees", "45.00"), (BANK, "-45.00")))
    args = dict(statement=statement, advice=advice, credit_notes=credit, entries=entries)
    args.update(overrides)
    return pack(**args)


def _edit(public: dict, name: str, old: str, new: str, count: int = 1) -> dict:
    """One textual edit to one file; the edit must actually hit."""
    assert public[name].count(old) == count, f"{name}: {old!r} occurs {public[name].count(old)}x, not {count}"
    out = dict(public)
    out[name] = public[name].replace(old, new)
    return out


def _append(public: dict, name: str, line: str) -> dict:
    out = dict(public)
    out[name] = public[name] + line.rstrip("\n") + "\n"
    return out


# --------------------------------------------------------------------------
# expectations, transcribed from section 7
# --------------------------------------------------------------------------

def _pairs(items):
    return tuple((invoice_id, D(amount)) for invoice_id, amount in items)


def _row(invoice_id, customer, basis, applied, credited, written_off, remaining):
    return CA.InvoiceRow(invoice_id, customer, D(basis), D(applied), D(credited), D(written_off), D(remaining))


CASE_1_REGISTER = (
    _row("SI-3100", GANNET, "300.00", "0.00", "0.00", "0.00", "300.00"),
    _row("SI-3101", GANNET, "2400.00", "2400.00", "0.00", "0.00", "0.00"),
    _row("SI-3102", GANNET, "3600.00", "3330.00", "270.00", "0.00", "0.00"),
    _row("SI-3103", SHEARWATER, "2970.00", "2970.00", "0.00", "0.00", "0.00"),
    _row("SI-3104", GANNET, "1890.00", "1890.00", "0.00", "0.00", "0.00"),
    _row("SI-3105", SHEARWATER, "2970.00", "0.00", "0.00", "0.00", "2970.00"),
)


def _register(*changes):
    rows = {r.invoice_id: r for r in CASE_1_REGISTER}
    for row in changes:
        rows[row.invoice_id] = row
    return tuple(rows[k] for k in sorted(rows))


R1_APPLIED = _pairs((("SI-3101", "2400.00"), ("SI-3102", "1500.00")))
R2_APPLIED = _pairs((("SI-3103", "2970.00"),))

#: receipts: receipt_id -> (applied, written_off, unapplied); credits; register; closing AR
EXPECTED = {
    1: dict(
        receipts={R1: (R1_APPLIED, (), "0.00"), R2: (R2_APPLIED, (), "0.00"),
                  R3: (_pairs((("SI-3102", "1830.00"), ("SI-3104", "1890.00"))), (), "0.00")},
        credits={"CN-0412": (_pairs((("SI-3102", "270.00"),)), "0.00")},
        register=CASE_1_REGISTER, closing="3270.00"),
    2: dict(
        receipts={R1: (R1_APPLIED, (), "0.00"), R2: (R2_APPLIED, (), "0.00"),
                  "2026-04-28:SI-3104 SI-3102": (_pairs((("SI-3102", "1830.00"), ("SI-3104", "300.00"))), (), "0.00")},
        credits={"CN-0412": (_pairs((("SI-3102", "270.00"),)), "0.00")},
        register=_register(_row("SI-3104", GANNET, "1890.00", "300.00", "0.00", "0.00", "1590.00")),
        closing="4860.00"),
    3: dict(
        receipts={R1: (R1_APPLIED, (), "0.00"), R2: (R2_APPLIED, (), "0.00"),
                  R3: (_pairs((("SI-3102", "1790.00"), ("SI-3104", "1870.00"))), _pairs((("SI-3104", "20.00"),)),
                       "0.00")},
        credits={"CN-0412": (_pairs((("SI-3102", "270.00"),)), "0.00")},
        register=_register(_row("SI-3102", GANNET, "3600.00", "3290.00", "270.00", "0.00", "40.00"),
                           _row("SI-3104", GANNET, "1890.00", "1870.00", "0.00", "20.00", "0.00")),
        closing="3310.00"),
    4: dict(
        receipts={R1: (R1_APPLIED, (), "0.00"), R2: (R2_APPLIED, (), "0.00"),
                  R3: (_pairs((("SI-3102", "1820.00"), ("SI-3104", "1790.00"))), _pairs((("SI-3102", "10.00"),)),
                       "0.00")},
        credits={"CN-0412": (_pairs((("SI-3102", "270.00"),)), "0.00")},
        register=_register(_row("SI-3102", GANNET, "3600.00", "3320.00", "270.00", "10.00", "0.00"),
                           _row("SI-3104", GANNET, "1890.00", "1790.00", "0.00", "0.00", "100.00")),
        closing="3370.00"),
    5: dict(
        receipts={R1: (R1_APPLIED, (), "0.00"), R2: (R2_APPLIED, (), "0.00"),
                  R3: (_pairs((("SI-3102", "1860.00"), ("SI-3104", "1890.00"))), (), "30.00")},
        credits={"CN-0412": (_pairs((("SI-3100", "300.00"), ("SI-3102", "240.00"))), "0.00")},
        register=_register(_row("SI-3100", GANNET, "300.00", "0.00", "300.00", "0.00", "0.00"),
                           _row("SI-3102", GANNET, "3600.00", "3360.00", "240.00", "0.00", "0.00")),
        closing="2940.00"),
}


MARROWBONE, PINEFALL = "Marrowbone Construction Group", "Pinefall Hospitality Partners"
MARCHMONT, CORVID, ASHGROVE = ("Marchmont Grocers Co-operative", "Corvid Coffee Houses LLC",
                               "Ashgrove Halt Refreshments Ltd")
QUILLHAVEN, BROADMARSH, PELLOW = ("Quillhaven Publishing House", "Broadmarsh Academy Trust",
                                  "Pellow & Dunge Stationers")


def _sorted_rows(*rows):
    return tuple(sorted((_row(*r) for r in rows), key=lambda r: r.invoice_id))


_THORNBURY_BASE = (
    ("SI-4377", PINEFALL, "6890.00", "6890.00", "0.00", "0.00", "0.00"),
    ("SI-4383", PINEFALL, "5300.00", "2650.00", "0.00", "0.00", "2650.00"),
    ("SI-4386", PINEFALL, "4240.00", "0.00", "0.00", "0.00", "4240.00"),
    ("SI-4390", PINEFALL, "8480.00", "8480.00", "0.00", "0.00", "0.00"),
    ("SI-4396", MARROWBONE, "12720.00", "12720.00", "0.00", "0.00", "0.00"),
    ("SI-4408", MARROWBONE, "9540.00", "8268.00", "1272.00", "0.00", "0.00"),
    ("SI-4415", MARROWBONE, "6360.00", "0.00", "0.00", "0.00", "6360.00"),
    ("SI-4419", PINEFALL, "10600.00", "0.00", "0.00", "0.00", "10600.00"),
)
_TALLOW_BASE = (
    ("SI-7218", QUILLHAVEN, "1620.00", "0.00", "0.00", "0.00", "1620.00"),
    ("SI-7222", BROADMARSH, "3780.00", "3150.00", "630.00", "0.00", "0.00"),
    ("SI-7226", QUILLHAVEN, "5250.00", "5250.00", "0.00", "0.00", "0.00"),
    ("SI-7229", BROADMARSH, "4410.00", "4395.00", "0.00", "15.00", "0.00"),
    ("SI-7231", QUILLHAVEN, "7920.00", "7920.00", "0.00", "0.00", "0.00"),
    ("SI-7234", PELLOW, "2835.00", "2745.00", "0.00", "0.00", "90.00"),
    ("SI-7242", PELLOW, "3360.00", "0.00", "0.00", "0.00", "3360.00"),
)
_PENNY_REGISTER = _sorted_rows(
    ("SI-5188", MARCHMONT, "1260.00", "0.00", "1260.00", "0.00", "0.00"),
    ("SI-5196", CORVID, "5250.00", "5250.00", "0.00", "0.00", "0.00"),
    ("SI-5203", MARCHMONT, "3780.00", "3780.00", "0.00", "0.00", "0.00"),
    ("SI-5211", ASHGROVE, "1995.00", "0.00", "0.00", "0.00", "1995.00"),
    ("SI-5219", MARCHMONT, "2940.00", "1260.00", "1680.00", "0.00", "0.00"),
    ("SI-5227", CORVID, "3150.00", "0.00", "0.00", "0.00", "3150.00"),
    ("SI-5236", CORVID, "4200.00", "2100.00", "0.00", "0.00", "2100.00"),
    ("SI-5244", MARCHMONT, "2625.00", "0.00", "0.00", "0.00", "2625.00"),
)
_PENNY_RECEIPTS = {
    "2026-06-10:MG PAYRUN 0610": (_pairs((("SI-5203", "3780.00"), ("SI-5219", "1260.00"))), (), "0.00"),
    "2026-06-15:6153": (_pairs((("SI-5196", "5250.00"),)), (), "0.00"),
    "2026-06-26:CC ACH 0626": (_pairs((("SI-5236", "2100.00"),)), (), "0.00"),
}
_THORNBURY_HEAD = {
    "2026-06-08:MCG REMIT 0605": (_pairs((("SI-4371", "5100.00"), ("SI-4396", "4440.00"))), (), "0.00"),
    "2026-06-17:TRC0617318 SI-4383 SI-4390 SI-4377":
        (_pairs((("SI-4390", "8480.00"), ("SI-4377", "6890.00"), ("SI-4383", "2650.00"))), (), "0.00"),
}
_TALLOW_HEAD = {
    "2026-07-09:QPH SETTLEMENT 0709": (_pairs((("SI-7231", "7920.00"), ("SI-7226", "1620.00"))), (), "0.00"),
    "2026-07-20:4417": (_pairs((("SI-7222", "3150.00"),)), (), "0.00"),
    "2026-07-22:BAT REMIT 0722": (_pairs((("SI-7229", "4395.00"),)), _pairs((("SI-7229", "15.00"),)), "0.00"),
    "2026-07-24:PDS PAYRUN 0724": (_pairs((("SI-7234", "2745.00"),)), (), "0.00"),
}

#: `v10-codex/six_variant_packs.md`'s three "correct application" sections,
#: transcribed. `residue` is Σ unapplied over receipts and credit notes: the
#: one number each pair exists to price.
VARIANT_PACKS = {
    "cash_application_006": dict(
        receipts=dict(_THORNBURY_HEAD, **{
            "2026-06-25:TRC0625704 SI-4402 SI-4408 SI-4396":
                (_pairs((("SI-4408", "8268.00"), ("SI-4396", "8280.00"), ("SI-4402", "7420.00"),
                         ("SI-4371", "2900.00"))), (), "0.00")}),
        credits={"CN-0609": (_pairs((("SI-4408", "1272.00"),)), "0.00")},
        register=_sorted_rows(*_THORNBURY_BASE,
                              ("SI-4371", MARROWBONE, "9300.00", "8000.00", "0.00", "0.00", "1300.00"),
                              ("SI-4402", MARROWBONE, "7420.00", "7420.00", "0.00", "0.00", "0.00")),
        opening="63890.00", closing="25150.00", residue="0.00"),
    "cash_application_007": dict(
        receipts=dict(_THORNBURY_HEAD, **{
            "2026-06-25:TRC0625704 SI-4402 SI-4408 SI-4396":
                (_pairs((("SI-4408", "8268.00"), ("SI-4396", "8280.00"), ("SI-4402", "4452.00"))), (), "0.00")}),
        credits={"CN-0609": (_pairs((("SI-4408", "1272.00"),)), "0.00")},
        register=_sorted_rows(*_THORNBURY_BASE,
                              ("SI-4371", MARROWBONE, "9300.00", "5100.00", "0.00", "0.00", "4200.00"),
                              ("SI-4402", MARROWBONE, "7420.00", "4452.00", "0.00", "0.00", "2968.00")),
        opening="63890.00", closing="31018.00", residue="0.00"),
    "cash_application_008": dict(
        receipts=_PENNY_RECEIPTS,
        credits={"CN-0618": (_pairs((("SI-5219", "1680.00"), ("SI-5188", "1260.00"))), "210.00")},
        register=_PENNY_REGISTER, opening="18375.00", closing="9660.00", residue="210.00"),
    "cash_application_009": dict(
        receipts=_PENNY_RECEIPTS,
        credits={"CN-0618": (_pairs((("SI-5219", "1680.00"), ("SI-5188", "1260.00"))), "0.00")},
        register=_PENNY_REGISTER, opening="18375.00", closing="9870.00", residue="0.00"),
    "cash_application_010": dict(
        receipts=dict(_TALLOW_HEAD, **{
            "2026-07-29:QPH SETTLEMENT 0729":
                (_pairs((("SI-7226", "3630.00"), ("SI-7239", "4020.00"))), (), "540.00")}),
        credits={"CN-0714": (_pairs((("SI-7222", "630.00"),)), "0.00")},
        register=_sorted_rows(*_TALLOW_BASE,
                              ("SI-7239", QUILLHAVEN, "4620.00", "4020.00", "0.00", "0.00", "600.00")),
        opening="25815.00", closing="5130.00", residue="540.00"),
    "cash_application_011": dict(
        receipts=dict(_TALLOW_HEAD, **{
            "2026-07-29:QPH SETTLEMENT 0729":
                (_pairs((("SI-7226", "3630.00"), ("SI-7239", "4560.00"))), (), "0.00")}),
        credits={"CN-0714": (_pairs((("SI-7222", "630.00"),)), "0.00")},
        register=_sorted_rows(*_TALLOW_BASE,
                              ("SI-7239", QUILLHAVEN, "4620.00", "4560.00", "0.00", "0.00", "60.00")),
        opening="25815.00", closing="5130.00", residue="0.00"),
}


def _compare(app: CA.Application, expected: dict, label: str, opening: str = "9270.00") -> list:
    problems = []
    got_receipts = {r.receipt_id: (r.applied, r.written_off, r.unapplied) for r in app.receipts}
    for receipt_id, (applied, written_off, unapplied) in expected["receipts"].items():
        got = got_receipts.get(receipt_id)
        if got is None:
            problems.append(f"{label}: receipt {receipt_id} missing; have {sorted(got_receipts)}")
        elif got != (applied, written_off, D(unapplied)):
            problems.append(f"{label}: receipt {receipt_id} folded {got}, expected "
                            f"{(applied, written_off, D(unapplied))}")
    if set(got_receipts) != set(expected["receipts"]):
        problems.append(f"{label}: receipts {sorted(got_receipts)} != {sorted(expected['receipts'])}")
    got_credits = {c.credit_note_id: (c.applied, c.unapplied) for c in app.credit_notes}
    for credit_note_id, (applied, unapplied) in expected["credits"].items():
        got = got_credits.get(credit_note_id)
        if got != (applied, D(unapplied)):
            problems.append(f"{label}: credit note {credit_note_id} folded {got}, expected {(applied, D(unapplied))}")
    if set(got_credits) != set(expected["credits"]):
        problems.append(f"{label}: credit notes {sorted(got_credits)} != {sorted(expected['credits'])}")
    if app.register != expected["register"]:
        for got, want in zip(app.register, expected["register"]):
            if got != want:
                problems.append(f"{label}: row {got} != {want}")
        if len(app.register) != len(expected["register"]):
            problems.append(f"{label}: {len(app.register)} rows, expected {len(expected['register'])}")
    if app.closing_ar != D(expected["closing"]):
        problems.append(f"{label}: closing AR {app.closing_ar}, expected {expected['closing']}")
    if app.opening_ar != D(opening):
        problems.append(f"{label}: opening AR {app.opening_ar}, expected {opening}")
    return problems


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------

def test_the_fold_holds_the_public_only_discipline():
    problems = []
    source = Path(CA.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                problems.append(f"relative import of {node.module!r} at line {node.lineno}")
            elif (node.module or "").split(".")[0] not in STDLIB_ONLY:
                problems.append(f"imports {node.module!r}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in STDLIB_ONLY:
                    problems.append(f"imports {alias.name!r}")
    for word in FORBIDDEN:
        if re.search(rf"^\s*(from|import)\s+\S*{word}", source, re.MULTILINE):
            problems.append(f"an import line mentions {word!r}")
    foreign = [name for name, value in vars(CA).items()
               if getattr(value, "__module__", "").startswith("beancount_ledger")
               and getattr(value, "__module__", "") != CA.__name__]
    if foreign:
        problems.append(f"module globals bound from the package: {foreign}")
    params = inspect.signature(CA.fold).parameters
    if list(params) != ["public", "bank_account", "period_start", "period_end"]:
        problems.append(f"fold's signature is {list(params)}")
    for bad, label in ((("a", "tuple", "of", "facts"), "a fact tuple"), (b"bytes", "bytes"), (None, "None"),
                       ({"ledger.beancount": b"bytes"}, "a mapping to bytes")):
        try:
            CA.fold(bad)
            problems.append(f"{label} was accepted")
        except CA.PublicOnly:
            pass
        except Exception as exc:
            problems.append(f"{label} raised {type(exc).__name__}, not PublicOnly")
    if tuple(CA.REFUSALS) != (
            "REFUSE_AMBIGUOUS_REMITTANCE_JOIN", "REFUSE_LINE_CONTRADICTS_REGISTER",
            "REFUSE_FOREIGN_OR_UNKNOWN_INVOICE", "REFUSE_ADVICE_AMOUNT_DISAGREES", "REFUSE_ORDER_SENSITIVE",
            "REFUSE_DUPLICATE_RECEIPT_KEY", "REFUSE_REGISTER_DOES_NOT_TIE", "REFUSE_SALE_WITHOUT_UNIQUE_NUMBER"):
        problems.append(f"the refusal names are {CA.REFUSALS}")
    if CA.SHORT_PAY_TOLERANCE != D("25.00"):
        problems.append(f"tolerance is {CA.SHORT_PAY_TOLERANCE}")
    return check("the fold takes strings only, imports stdlib only, has no route to the graph, and names the "
                 "U-table's refusals", not problems, "\n".join(problems))


def test_the_five_cases_fold_to_section_7():
    problems = []
    for case, expected in EXPECTED.items():
        try:
            app = CA.fold(bowline(case))
        except Exception as exc:
            problems.append(f"case {case}: {type(exc).__name__}: {exc}")
            continue
        problems += _compare(app, expected, f"case {case}")
        if any(w.startswith("WARN") for w in app.warnings):
            problems.append(f"case {case}: warnings {app.warnings}")
        if app.closing_ar != sum((r.remaining for r in app.register), D(0)) - sum(
                [r.unapplied for r in app.receipts] + [c.unapplied for c in app.credit_notes], D(0)):
            problems.append(f"case {case}: closing_ar is not sum(remaining) - sum(unapplied)")
    return check("the five cases fold to section 7's applications, write-offs, credit applications, register rows "
                 "and closing AR", not problems, "\n".join(problems))


def test_the_six_variant_packs_fold_to_their_documents():
    """The three matched pairs of `v10-codex/six_variant_packs.md`, folded
    from the bytes the projector actually emits.

    The fold still sees only strings — the projector is called here to
    PRODUCE those strings, exactly as the evaluator mounts them, and the
    import is local so this suite's module surface stays the fold's alone.
    What is asserted is the fold's own answer: the pack's applications,
    write-offs, credit applications, residues, register rows and closing AR,
    with no refusal and no WARN, on all six.
    """
    from beancount_ledger.graph.derive import derive_contract          # noqa: PLC0415  (see the docstring)
    from beancount_ledger.graph.worlds import CASH_APPLICATION_PAIR_MODULES  # noqa: PLC0415

    problems = []
    seen = []
    for module in CASH_APPLICATION_PAIR_MODULES:
        for task_id in sorted(module.TASKS):
            task = module.TASKS[task_id]
            _bundle, inputs = derive_contract(module.WORLD_BY_TASK[task_id], task)
            public = {name: data.decode("utf-8") for name, data in inputs.public_files}
            expected = VARIANT_PACKS[task_id]
            try:
                app = CA.fold(public, bank_account=BANK, period_start=task.period.start,
                              period_end=task.period.end)
            except Exception as exc:
                problems.append(f"{task_id}: {type(exc).__name__}: {exc}")
                continue
            seen.append(task_id)
            problems += _compare(app, expected, task_id, opening=expected["opening"])
            if any(w.startswith("WARN") for w in app.warnings):
                problems.append(f"{task_id}: warnings {app.warnings}")
            if app.closing_ar != sum((r.remaining for r in app.register), D(0)) - sum(
                    [r.unapplied for r in app.receipts] + [c.unapplied for c in app.credit_notes], D(0)):
                problems.append(f"{task_id}: closing_ar is not sum(remaining) - sum(unapplied)")
            residue = sum([r.unapplied for r in app.receipts] + [c.unapplied for c in app.credit_notes], D(0))
            if residue != D(expected["residue"]):
                problems.append(f"{task_id}: residue {residue}, expected {expected['residue']}")
    if seen != sorted(VARIANT_PACKS):
        problems.append(f"folded {seen}, expected {sorted(VARIANT_PACKS)}")
    return check("the six variant packs fold to their documents over the projector's own bytes: the policy "
                 "fallback's rung-(3) remainder and its absence, the credit note's 210.00 residue and its "
                 "absence, the advice's 540.00 residue and its absence — no refusal, no WARN",
                 not problems, "\n".join(problems))


def test_case_1_document_is_the_spec_example():
    problems = []
    doc = CA.document(CA.fold(bowline(1)))
    if doc["schema"] != "piv.cash-application/1":
        problems.append(f"schema {doc['schema']}")
    first = doc["receipts"][0]
    want = {"receipt_id": "2026-04-10:GR PAYRUN 0410",
            "applied": [{"invoice_id": "SI-3101", "amount": "2400.00"}, {"invoice_id": "SI-3102", "amount": "1500.00"}],
            "written_off": [], "unapplied_amount": "0.00"}
    if first != want:
        problems.append(f"first receipt {first}")
    if doc["credit_notes"] != [{"credit_note_id": "CN-0412",
                                "applied": [{"invoice_id": "SI-3102", "amount": "270.00"}],
                                "unapplied_amount": "0.00"}]:
        problems.append(f"credit notes {doc['credit_notes']}")
    if doc["closing_open_items"][0] != {"invoice_id": "SI-3100", "customer": GANNET, "period_basis": "300.00",
                                        "applied_total": "0.00", "credited": "0.00", "written_off": "0.00",
                                        "remaining": "300.00"}:
        problems.append(f"first row {doc['closing_open_items'][0]}")
    if len(doc["closing_open_items"]) != 6 or len(doc["receipts"]) != 3:
        problems.append("row or receipt count")
    if set(doc) != {"schema", "receipts", "credit_notes", "closing_open_items"}:
        problems.append(f"keys {sorted(doc)}")
    text = CA.document_text(CA.fold(bowline(1)))
    if not text.endswith("\n") or '"notes"' in text:
        problems.append("document text")
    return check("Case 1's document is the spec's piv.cash-application/1 example, byte-shaped and without notes",
                 not problems, "\n".join(problems))


def test_period_basis_is_the_balance_entering_the_period():
    """SI-3100's face value is 1,080.00 and its period basis 300.00; the
    register reports the latter, and Case 5's credit lands 300.00 on it."""
    problems = []
    app = CA.fold(bowline(5))
    row = app.row("SI-3100")
    if row.period_basis != D("300.00") or row.credited != D("300.00") or row.remaining != D("0.00"):
        problems.append(f"SI-3100 row {row}")
    ev = CA.read_evidence(bowline(5))
    inv = ev.invoice("SI-3100")
    if inv.face_value != D("1080.00") or inv.period_basis != D("300.00") or inv.source != "register":
        problems.append(f"SI-3100 evidence {inv}")
    sale = ev.invoice("SI-3104")
    if sale is None or sale.source != "sale" or sale.period_basis != D("1890.00") or sale.customer != GANNET \
            or sale.invoice_date != "2026-04-07":
        problems.append(f"SI-3104 evidence {sale}")
    if app.closing_ar != D("2940.00") or sum((r.remaining for r in app.register), D(0)) != D("2970.00"):
        problems.append("Case 5 is the one case where sum(remaining) 2,970.00 and closing AR 2,940.00 differ")
    return check("period_basis is the balance entering the period, never the face value; a sale's is its gross",
                 not problems, "\n".join(problems))


def _refusal_fixtures() -> list:
    """(label, code, pack). One edit from Case 1 each, and the edit is
    asserted to hit."""
    base = bowline(1)
    fixtures = []

    # U1: two advices bind one row
    dup = _append(base, "remittance_advice.csv",
                  f"RA-0410-GR-B,{GANNET},2026-04-10,ACH,GR PAYRUN 0410,3900.00,SI-3101,2400.00,yes,0.00,")
    fixtures.append(("U1 two advices bind one row", CA.REFUSE_AMBIGUOUS_REMITTANCE_JOIN, dup))
    # U1: one advice binds two rows (a second row, another date, same reference and amount)
    two_rows = bowline(1, statement=(
        ("2026-04-09", "ACH OUT NORTHSHORE CHANDLERY SUPPLY", "PI-8813", "4175.00", ""),
        ("2026-04-10", "ACH IN GANNET RIGGING INC", "GR PAYRUN 0410", "", "3900.00"),
        ("2026-04-11", "ACH IN GANNET RIGGING INC", "GR PAYRUN 0410", "", "3900.00"),
        ("2026-04-21", "CHECK 2291 SHEARWATER BAY CHARTERS LLC", "2291", "", "2970.00"),
        ("2026-04-28", "ACH IN GANNET RIGGING INC", "GR PAYRUN 0428", "", "3720.00"),
        ("2026-04-30", "MONTHLY ACCOUNT SERVICE CHARGE", "", "45.00", "")))
    fixtures.append(("U1 one advice binds two rows", CA.REFUSE_AMBIGUOUS_REMITTANCE_JOIN, two_rows))

    # U2: a line exceeds the open balance (2,500 on SI-3101's 2,400; the other line lowered to keep the total)
    over = _edit(_edit(base, "remittance_advice.csv", "SI-3101,2400.00,yes", "SI-3101,2500.00,no"),
                 "remittance_advice.csv", "SI-3102,1500.00,no", "SI-3102,1400.00,no")
    fixtures.append(("U2 a line exceeds the open balance", CA.REFUSE_LINE_CONTRADICTS_REGISTER, over))
    # U2: settles=yes with paid + deduction != balance (2,300 + 0 on 2,400; the other line raised)
    short = _edit(_edit(base, "remittance_advice.csv", "SI-3101,2400.00,yes", "SI-3101,2300.00,yes"),
                  "remittance_advice.csv", "SI-3102,1500.00,no", "SI-3102,1600.00,no")
    fixtures.append(("U2 a settling line's paid + deduction is not the balance", CA.REFUSE_LINE_CONTRADICTS_REGISTER,
                     short))
    # U2: a deduction claimed without settling
    claim = _edit(base, "remittance_advice.csv", "SI-3102,1500.00,no,0.00", "SI-3102,1500.00,no,10.00")
    fixtures.append(("U2 a deduction without settling", CA.REFUSE_LINE_CONTRADICTS_REGISTER, claim))
    # U2: the lines total above the payment (a negative residue)
    negative = _edit(base, "remittance_advice.csv", "SI-3102,1500.00,no", "SI-3102,1600.00,no")
    fixtures.append(("U2 lines above the payment amount", CA.REFUSE_LINE_CONTRADICTS_REGISTER, negative))

    # U3: an advice line names the other customer's invoice
    foreign = _edit(base, "remittance_advice.csv", "SI-3100,0.00,no,0.00,withheld", "SI-3103,0.00,no,0.00,withheld")
    fixtures.append(("U3 an advice line names the other customer's invoice", CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                     foreign))
    # U3: an advice line names an unknown id
    unknown = _edit(base, "remittance_advice.csv", "SI-3100,0.00,no,0.00,withheld", "SI-9999,0.00,no,0.00,withheld")
    fixtures.append(("U3 an advice line names an unknown invoice", CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, unknown))
    # U3: an advice line names an invoice not yet raised at the application date (SI-3104 moved to 04-12)
    later = bowline(1, sales=(("2026-04-12", GANNET, "SI-3104", "1750.00", "140.00", "1050.00"), SALES[1]))
    later = _edit(later, "remittance_advice.csv", "SI-3100,0.00,no,0.00,withheld", "SI-3104,0.00,no,0.00,withheld")
    fixtures.append(("U3 an advice line names an invoice raised after the application date",
                     CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, later))
    # U3: an advice line pays a closed invoice (SI-3101, closed by R1, on RA-0428-GR; totals kept)
    closed = _edit(_edit(base, "remittance_advice.csv", "SI-3102,1830.00,yes,0.00", "SI-3101,1830.00,no,0.00"),
                   "remittance_advice.csv", "SI-3104,1890.00,yes", "SI-3104,1890.00,yes")
    fixtures.append(("U3 an advice line pays a closed invoice", CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, closed))
    # U3: a statement reference names a closed invoice (Case 2's R3 quoting SI-3101)
    reference_closed = _edit(bowline(2), "bank_statement.csv", "SI-3104 SI-3102", "SI-3101 SI-3102")
    fixtures.append(("U3 a statement reference names a closed invoice", CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                     reference_closed))
    # U3: a statement reference names the other customer's invoice
    reference_foreign = _edit(bowline(2), "bank_statement.csv", "SI-3104 SI-3102", "SI-3105 SI-3102")
    fixtures.append(("U3 a statement reference names the other customer's invoice",
                     CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, reference_foreign))
    # U3: a statement reference names an unknown id
    reference_unknown = _edit(bowline(2), "bank_statement.csv", "SI-3104 SI-3102", "SI-3104 SI-3199")
    fixtures.append(("U3 a statement reference names an unknown invoice", CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                     reference_unknown))
    # U3: a statement reference names an invoice raised after the receipt (R3 moved before SI-3104? no —
    # SI-3104 moved after R3's date instead)
    reference_later = bowline(2, sales=(("2026-04-29", GANNET, "SI-3104", "1750.00", "140.00", "1050.00"), SALES[1]))
    fixtures.append(("U3 a statement reference names an invoice raised after the receipt",
                     CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, reference_later))
    # U3: a credit note names the other customer's invoice / an unknown id / an invoice dated after it
    fixtures.append(("U3 a credit note names the other customer's invoice", CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                     _edit(base, "credit_notes.csv", "SI-3102,250.00", "SI-3103,250.00")))
    fixtures.append(("U3 a credit note names an unknown invoice", CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                     _edit(base, "credit_notes.csv", "SI-3102,250.00", "SI-3199,250.00")))
    fixtures.append(("U3 a credit note names an invoice dated after it", CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE,
                     _edit(base, "credit_notes.csv", "2026-04-15,Gannet Rigging Inc,SI-3102",
                           "2026-04-05,Gannet Rigging Inc,SI-3104")))

    # U4: customer and reference agree, the amount does not
    amount = _edit(base, "remittance_advice.csv", "GR PAYRUN 0410,3900.00", "GR PAYRUN 0410,3950.00", count=3)
    fixtures.append(("U4 an advice matches on customer and reference but not amount",
                     CA.REFUSE_ADVICE_AMOUNT_DISAGREES, amount))

    # U5: RA-0428-GR dated before CN-0412 — on its remittance date the fold puts R3 before the note and its
    # 'after CN-0412' line no longer settles SI-3102
    early = _edit(base, "remittance_advice.csv", "RA-0428-GR,Gannet Rigging Inc,2026-04-28",
                  "RA-0428-GR,Gannet Rigging Inc,2026-04-14", count=2)
    fixtures.append(("U5 the remittance date moves the receipt across the credit note", CA.REFUSE_ORDER_SENSITIVE,
                     early))
    # U5 through the credit route: Case 5 with RA-0410-GR dated after CN-0412 — re-dated, the note's 240.00
    # excess lands on SI-3101 (still open) and R1's settling line no longer matches. There is no non-refusing
    # form of U5: a line that moves under re-dating is an advice line valid in one order and not the other,
    # so the re-dated run refuses, and the fold reports that as REFUSE_ORDER_SENSITIVE.
    excess = _edit(bowline(5), "remittance_advice.csv", "RA-0410-GR,Gannet Rigging Inc,2026-04-10",
                   "RA-0410-GR,Gannet Rigging Inc,2026-04-16", count=3)
    fixtures.append(("U5 the remittance date moves a credit-note excess", CA.REFUSE_ORDER_SENSITIVE, excess))

    # U6: two customer-credit rows share date:reference; a credit row naming no customer
    same_key = bowline(1, statement=(
        ("2026-04-10", "ACH IN GANNET RIGGING INC", "GR PAYRUN 0410", "", "3900.00"),
        ("2026-04-10", "ACH IN GANNET RIGGING INC", "GR PAYRUN 0410", "", "100.00"),
        ("2026-04-21", "CHECK 2291 SHEARWATER BAY CHARTERS LLC", "2291", "", "2970.00"),
        ("2026-04-28", "ACH IN GANNET RIGGING INC", "GR PAYRUN 0428", "", "3720.00")))
    fixtures.append(("U6 two customer-credit rows share date:reference", CA.REFUSE_DUPLICATE_RECEIPT_KEY, same_key))
    nobody = _edit(base, "bank_statement.csv", "ACH IN GANNET RIGGING INC,GR PAYRUN 0428",
                   "ACH IN SOMEBODY ELSE,GR PAYRUN 0428")
    fixtures.append(("U6 a credit row names no customer", CA.REFUSE_DUPLICATE_RECEIPT_KEY, nobody))

    # U7: the register does not tie to the opening entry
    untied = _edit(base, "open_items.csv", "1080.00,300.00", "1080.00,400.00")
    fixtures.append(("U7 sum of open_balance is not the opening entry's AR", CA.REFUSE_REGISTER_DOES_NOT_TIE, untied))

    # U9: a sale narration with no token, with two tokens, colliding with the register
    fixtures.append(("U9 a sale narration with no invoice number", CA.REFUSE_SALE_WITHOUT_UNIQUE_NUMBER,
                     _edit(base, "ledger.beancount", '"Sale SI-3104"', '"Sale"')))
    fixtures.append(("U9 a sale narration with two invoice numbers", CA.REFUSE_SALE_WITHOUT_UNIQUE_NUMBER,
                     _edit(base, "ledger.beancount", '"Sale SI-3104"', '"Sale SI-3104 SI-3106"')))
    fixtures.append(("U9 a sale whose number the register carries", CA.REFUSE_SALE_WITHOUT_UNIQUE_NUMBER,
                     _edit(base, "ledger.beancount", '"Sale SI-3104"', '"Sale SI-3100"')))
    return fixtures


def test_every_refusal_fires_on_a_minimal_fixture():
    problems, fired = [], set()
    for label, code, public in _refusal_fixtures():
        try:
            app = CA.fold(public)
            problems.append(f"{label}: folded without refusing; closing AR {app.closing_ar}")
        except CA.Refusal as exc:
            if exc.code != code:
                problems.append(f"{label}: refused {exc.code}, expected {code}: {exc.detail}")
            else:
                fired.add(code)
        except Exception as exc:
            problems.append(f"{label}: raised {type(exc).__name__} instead of a refusal: {exc}")
    missing = set(CA.REFUSALS) - fired
    if missing:
        problems.append(f"no fixture fired {sorted(missing)}")
    return check(f"each of the {len(CA.REFUSALS)} refusals fires, with the spec's name, on a minimal violating "
                 f"fixture ({len(_refusal_fixtures())} fixtures)", not problems, "\n".join(problems))


def test_u12_warns_and_does_not_refuse():
    problems = []
    # an advice line on a zero-balance invoice: an informational line of RA-0428-GR on SI-3101, closed by R1
    zero = _append(bowline(1), "remittance_advice.csv",
                   f"RA-0428-GR,{GANNET},2026-04-28,ACH,GR PAYRUN 0428,3720.00,SI-3101,0.00,no,0.00,disputed")
    try:
        app = CA.fold(zero)
        if not any(w.startswith(CA.WARN_LINE_ON_ZERO_BALANCE) for w in app.warnings):
            problems.append(f"zero-balance line: warnings {app.warnings}")
        problems += _compare(app, EXPECTED[1], "zero-balance line")
    except Exception as exc:
        problems.append(f"zero-balance line refused: {exc}")
    # a paid-invoice credit is not refused (U3's reconciliation with the credit policy)
    try:
        CA.fold(_paid_invoice_credit_pack())
    except Exception as exc:
        problems.append(f"credit against a paid invoice refused: {exc}")
    # an advice bound to no row is ignored with a warning, not refused
    unbound = _append(bowline(1), "remittance_advice.csv",
                      f"RA-0499-GR,{GANNET},2026-04-29,ACH,GR PAYRUN 0499,100.00,SI-3100,100.00,no,0.00,")
    try:
        app = CA.fold(unbound)
        if not any(w.startswith(CA.WARN_UNBOUND_ADVICE) for w in app.warnings):
            problems.append(f"unbound advice: warnings {app.warnings}")
        problems += _compare(app, EXPECTED[1], "unbound advice")
    except Exception as exc:
        problems.append(f"unbound advice refused: {exc}")
    return check("U12 warns — a line on a zero-balance invoice, a deduction of exactly 25.00 (below) — and a "
                 "paid-invoice credit or an unbound advice is not a refusal", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# the offline fixtures section 7 requires
# --------------------------------------------------------------------------

def _receipt(app, receipt_id):
    r = app.receipt(receipt_id)
    return (r.applied, r.written_off, r.unapplied)


def test_rung_3_remainder_after_the_named_invoices():
    """Case 2 with R3 = 2,430.00 quoting SI-3104 alone: 1,890.00 to the named
    invoice, the 540.00 remainder oldest first — SI-3100 300.00, then
    SI-3102 240.00 (SI-3101 is closed)."""
    public = _edit(bowline(2), "bank_statement.csv", "SI-3104 SI-3102,,2130.00", "SI-3104,,2430.00")
    app = CA.fold(public)
    got = _receipt(app, "2026-04-28:SI-3104")
    want = (_pairs((("SI-3104", "1890.00"), ("SI-3100", "300.00"), ("SI-3102", "240.00"))), (), D("0.00"))
    problems = [] if got == want else [f"R3 {got} != {want}"]
    if app.receipt("2026-04-28:SI-3104").rungs != ("reference", "oldest_first"):
        problems.append(f"rungs {app.receipt('2026-04-28:SI-3104').rungs}")
    if app.row("SI-3100").remaining != 0 or app.row("SI-3102").remaining != D("1590.00"):
        problems.append("rows")
    if app.closing_ar != D("4560.00"):
        problems.append(f"closing {app.closing_ar}")
    return check("rung (3): the remainder after the reference's named invoices goes oldest first",
                 not problems, "\n".join(problems))


def test_credit_note_residue_no_other_invoice_absorbs():
    """A Shearwater note of 6,000.00 on SI-3103 (04-15): 2,970.00 to it,
    2,970.00 to SI-3105, 60.00 held as Shearwater's unapplied credit; R2's
    advice then finds SI-3103 closed, so the fixture drops that advice and
    R2 falls to rung (3), which finds nothing open and holds all of it."""
    public = bowline(1, credit_notes=(CN_0412, ("CN-0413", "2026-04-15", SHEARWATER, "SI-3103", "5555.56", "444.44",
                                                "6000.00", "cancelled charter")))
    # drop R2's advice (its invoice is closed by the note): Gannet's advices only
    public["remittance_advice.csv"] = _csv(CA.REMITTANCE_COLUMNS, RA_0410 + tuple(
        ("RA-0428-GR", GANNET, "2026-04-28", "ACH", "GR PAYRUN 0428", "3720.00") + line for line in (
            ("SI-3102", "1830.00", "yes", "0.00", ""), ("SI-3104", "1890.00", "yes", "0.00", ""))))
    app = CA.fold(public)
    problems = []
    cn = app.credit_note("CN-0413")
    if (cn.applied, cn.unapplied) != (_pairs((("SI-3103", "2970.00"), ("SI-3105", "2970.00"))), D("60.00")):
        problems.append(f"CN-0413 {cn}")
    if _receipt(app, R2) != ((), (), D("2970.00")) or app.receipt(R2).rungs != ("none",):
        problems.append(f"R2 {app.receipt(R2)}")
    if app.closing_ar != D("300.00") - D("60.00") - D("2970.00"):
        problems.append(f"closing {app.closing_ar}")
    return check("a credit-note residue no other invoice absorbs stays that customer's unapplied credit",
                 not problems, "\n".join(problems))


def test_advice_residue_while_another_invoice_is_open():
    """R3 = 1,920.00 with an advice naming SI-3104 1,890.00 only: 30.00 is
    unapplied although SI-3102 is open at 1,830.00 — the fallback rungs do
    not run for an adviced receipt."""
    public = bowline(1)
    public = _edit(public, "bank_statement.csv", "GR PAYRUN 0428,,3720.00", "GR PAYRUN 0428,,1920.00")
    public["remittance_advice.csv"] = _csv(CA.REMITTANCE_COLUMNS, RA_0410 + RA_0416 + (
        ("RA-0428-GR", GANNET, "2026-04-28", "ACH", "GR PAYRUN 0428", "1920.00", "SI-3104", "1890.00", "yes", "0.00", ""),))
    app = CA.fold(public)
    problems = []
    if _receipt(app, R3) != (_pairs((("SI-3104", "1890.00"),)), (), D("30.00")):
        problems.append(f"R3 {app.receipt(R3)}")
    if app.row("SI-3102").remaining != D("1830.00") or app.row("SI-3102").applied_total != D("1500.00"):
        problems.append(f"SI-3102 {app.row('SI-3102')}")
    if app.closing_ar != D("300.00") + D("1830.00") + D("2970.00") - D("30.00"):
        problems.append(f"closing {app.closing_ar}")
    return check("an advice residue stays unapplied while another invoice of the customer is open",
                 not problems, "\n".join(problems))


def _paid_invoice_credit_pack() -> dict:
    """Case 1 with CN-0412 naming SI-3101, paid by R1 on 04-10. None of it
    lands there; all 270.00 routes as excess to Gannet's oldest other open
    invoice, SI-3100, so SI-3102 stays at 2,100.00 and R3's advice (3,990.00)
    settles it at that figure."""
    public = _edit(bowline(1), "credit_notes.csv", "SI-3102,250.00", "SI-3101,250.00")
    public = _edit(public, "bank_statement.csv", "GR PAYRUN 0428,,3720.00", "GR PAYRUN 0428,,3990.00")
    public = _edit(public, "remittance_advice.csv", "GR PAYRUN 0428,3720.00,SI-3102,1830.00",
                   "GR PAYRUN 0428,3990.00,SI-3102,2100.00")
    return _edit(public, "remittance_advice.csv", "GR PAYRUN 0428,3720.00,SI-3104", "GR PAYRUN 0428,3990.00,SI-3104")


def test_credit_note_against_a_paid_invoice_routes_as_excess():
    app = CA.fold(_paid_invoice_credit_pack())
    problems = []
    cn = app.credit_note("CN-0412")
    if (cn.applied, cn.unapplied) != (_pairs((("SI-3100", "270.00"),)), D("0.00")):
        problems.append(f"CN-0412 {cn}")
    want = _register(_row("SI-3100", GANNET, "300.00", "0.00", "270.00", "0.00", "30.00"),
                     _row("SI-3102", GANNET, "3600.00", "3600.00", "0.00", "0.00", "0.00"))
    if app.register != want:
        problems.append("; ".join(f"{got} != {w}" for got, w in zip(app.register, want) if got != w))
    if app.row("SI-3101").credited != 0 or app.closing_ar != D("3000.00"):
        problems.append(f"SI-3101 credited {app.row('SI-3101').credited}, closing {app.closing_ar}")
    return check("a credit note against an already paid invoice routes its whole amount as excess",
                 not problems, "\n".join(problems))


def _equal_dates_pack(reference: str, statement_amount: str = "1000.00", credit=()):
    """Gannet's SI-3101 and SI-3102 both dated 2026-03-03; an un-adviced
    receipt of `statement_amount` with `reference`; no in-month sales."""
    open_items = (
        ("SI-3100", GANNET, "2026-02-26", "2026-03-28", "1080.00", "300.00"),
        ("SI-3102", GANNET, "2026-03-03", "2026-04-02", "3600.00", "3600.00"),
        ("SI-3101", GANNET, "2026-03-03", "2026-04-02", "2400.00", "2400.00"),
        ("SI-3103", SHEARWATER, "2026-03-18", "2026-04-17", "2970.00", "2970.00"),
    )
    return pack(open_items=open_items, sales=(), credit_notes=credit,
                statement=(("2026-04-10", "ACH IN GANNET RIGGING INC", reference, "", statement_amount),),
                entries=(entry("2026-04-10", GANNET, "Customer payment", (BANK, statement_amount),
                               (AR, f"-{statement_amount}")),))


def test_equal_invoice_dates_resolve_by_invoice_id():
    problems = []
    # rung (2): both named, printed the other way round; the lower id first
    app = CA.fold(_equal_dates_pack("SI-3102 SI-3101"))
    if _receipt(app, "2026-04-10:SI-3102 SI-3101") != (_pairs((("SI-3101", "1000.00"),)), (), D("0.00")):
        problems.append(f"rung 2: {app.receipt('2026-04-10:SI-3102 SI-3101')}")
    # rung (3): nothing named; SI-3100 (older) first, then the lower id of the equal pair
    app = CA.fold(_equal_dates_pack("", statement_amount="1300.00"))
    if _receipt(app, "2026-04-10:") != (_pairs((("SI-3100", "300.00"), ("SI-3101", "1000.00"))), (), D("0.00")):
        problems.append(f"rung 3: {app.receipt('2026-04-10:')}")
    # the credit-note excess: a note on SI-3100 of 800.00 (04-05), 300.00 there, 500.00 to the lower id
    app = CA.fold(_equal_dates_pack("", statement_amount="100.00",
                                    credit=(("CN-1", "2026-04-05", GANNET, "SI-3100", "740.74", "59.26", "800.00", "x"),)))
    cn = app.credit_note("CN-1")
    if (cn.applied, cn.unapplied) != (_pairs((("SI-3100", "300.00"), ("SI-3101", "500.00"))), D("0.00")):
        problems.append(f"credit excess: {cn}")
    return check("equal invoice dates are not a refusal: the invoice-id tie-break decides at rung (2), rung (3) "
                 "and the credit-note excess", not problems, "\n".join(problems))


def test_rung_2_is_invoice_date_order_not_printed_or_number_order():
    """SI-3099 dated 03-20 and SI-3102 dated 03-12: number order and printed
    order both put SI-3099 first; the published invoice-date order pays
    SI-3102 first."""
    open_items = (
        ("SI-3102", GANNET, "2026-03-12", "2026-04-11", "3600.00", "3600.00"),
        ("SI-3099", GANNET, "2026-03-20", "2026-04-19", "2000.00", "2000.00"),
        ("SI-3103", SHEARWATER, "2026-03-18", "2026-04-17", "2970.00", "2970.00"),
    )
    public = pack(open_items=open_items, sales=(),
                  statement=(("2026-04-10", "ACH IN GANNET RIGGING INC", "SI-3099 SI-3102", "", "4000.00"),),
                  entries=(entry("2026-04-10", GANNET, "Customer payment", (BANK, "4000.00"), (AR, "-4000.00")),))
    app = CA.fold(public)
    receipt_id = "2026-04-10:SI-3099 SI-3102"
    problems = []
    if _receipt(app, receipt_id) != (_pairs((("SI-3102", "3600.00"), ("SI-3099", "400.00"))), (), D("0.00")):
        problems.append(f"policy: {app.receipt(receipt_id)}")
    printed = CA.baseline_readings(public, "printed_order")[0].receipt(receipt_id).applied
    number = CA.baseline_readings(public, "number_order")[0].receipt(receipt_id).applied
    if printed != _pairs((("SI-3099", "2000.00"), ("SI-3102", "2000.00"))):
        problems.append(f"printed order: {printed}")
    if number != printed:
        problems.append(f"number order: {number}")
    report = CA.baseline_report(public, app)
    if report["printed_order"].reaches_truth is not False or report["number_order"].reaches_truth is not False:
        problems.append("the fixture does not separate the orders")
    return check("rung (2) consumes the reference in invoice-date order; printed order and invoice-number order "
                 "both differ on a reference whose date order and number order disagree",
                 not problems, "\n".join(problems))


def test_deductions_around_the_tolerance():
    """Three Gannet invoices settled by one receipt with deductions of 24.99,
    25.00 and 25.01: the first two written off (the second with the U12
    warning), the third left open."""
    open_items = (
        ("SI-3101", GANNET, "2026-03-03", "2026-04-02", "1000.00", "1000.00"),
        ("SI-3102", GANNET, "2026-03-12", "2026-04-11", "1000.00", "1000.00"),
        ("SI-3103", GANNET, "2026-03-18", "2026-04-17", "1000.00", "1000.00"),
    )
    paid = D("3000.00") - D("24.99") - D("25.00") - D("25.01")   # 2925.00
    head = ("RA-1", GANNET, "2026-04-10", "ACH", "GR PAYRUN 0410", f"{paid:.2f}")
    advice = (head + ("SI-3101", "975.01", "yes", "24.99", ""),
              head + ("SI-3102", "975.00", "yes", "25.00", ""),
              head + ("SI-3103", "974.99", "yes", "25.01", ""))
    public = pack(open_items=open_items, sales=(), advice=advice,
                  statement=(("2026-04-10", "ACH IN GANNET RIGGING INC", "GR PAYRUN 0410", "", f"{paid:.2f}"),),
                  entries=(entry("2026-04-10", GANNET, "Customer payment", (BANK, paid), (AR, -paid)),))
    app = CA.fold(public)
    problems = []
    got = _receipt(app, "2026-04-10:GR PAYRUN 0410")
    want = (_pairs((("SI-3101", "975.01"), ("SI-3102", "975.00"), ("SI-3103", "974.99"))),
            _pairs((("SI-3101", "24.99"), ("SI-3102", "25.00"))), D("0.00"))
    if got != want:
        problems.append(f"receipt {got}")
    rows = {r.invoice_id: (r.written_off, r.remaining) for r in app.register}
    if rows != {"SI-3101": (D("24.99"), D("0.00")), "SI-3102": (D("25.00"), D("0.00")),
                "SI-3103": (D("0.00"), D("25.01"))}:
        problems.append(f"rows {rows}")
    if [w for w in app.warnings if w.startswith(CA.WARN_DEDUCTION_AT_TOLERANCE)] == []:
        problems.append(f"no tolerance warning: {app.warnings}")
    if app.closing_ar != D("25.01"):
        problems.append(f"closing {app.closing_ar}")
    # the baselines the deductions admit
    report = CA.baseline_report(public, app)
    everything = report["write_off_everything"].readings[0]
    nothing = report["write_off_nothing"].readings[0]
    if everything.row("SI-3103").written_off != D("25.01") or nothing.row("SI-3101").written_off != 0:
        problems.append("write-off baselines")
    if report["write_off_everything"].reaches_truth or report["write_off_nothing"].reaches_truth:
        problems.append("a write-off baseline reaches the truth")
    return check("deductions of 24.99 and 25.00 are written off (25.00 with the U12 warning), 25.01 is not",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# gate (o)
# --------------------------------------------------------------------------

def _applied(reading, receipt_id):
    return dict(reading.receipt(receipt_id).applied)


def test_gate_o_baselines_are_fixed_functions_and_none_reaches_a_case():
    problems = []
    names = tuple(b.name for b in CA.BASELINES)
    if names != ("amount_only", "oldest_first", "mixed_amount_only", "mixed_oldest_first", "hold_on_account",
                 "printed_order", "credit_ignored", "write_off_everything", "write_off_nothing", "number_order"):
        problems.append(f"baselines {names}")
    if CA.DIAGNOSTIC_BASELINE_NAMES != ("number_order",):
        problems.append(f"diagnostics {CA.DIAGNOSTIC_BASELINE_NAMES}")
    admitted_by_case = {
        1: {"amount_only", "oldest_first", "credit_ignored"},
        2: {"amount_only", "oldest_first", "mixed_amount_only", "mixed_oldest_first", "hold_on_account",
            "printed_order", "credit_ignored", "number_order"},
        3: {"amount_only", "oldest_first", "credit_ignored", "write_off_everything", "write_off_nothing"},
        4: {"amount_only", "oldest_first", "credit_ignored", "write_off_everything", "write_off_nothing"},
        5: {"amount_only", "oldest_first", "credit_ignored"},
    }
    reports = {}
    for case in EXPECTED:
        public = bowline(case)
        truth = CA.fold(public)
        report = CA.baseline_report(public, truth)
        reports[case] = report
        admitted = {name for name, r in report.items() if r.admitted}
        if admitted != admitted_by_case[case]:
            problems.append(f"case {case}: admitted {sorted(admitted)}, expected {sorted(admitted_by_case[case])}")
        for name, r in report.items():
            if r.admitted and r.reaches_truth and not r.diagnostic:
                problems.append(f"case {case}: {name} reaches the truth")
            if r.admitted and r.reaches_truth is None or (not r.admitted and r.reaches_truth is not None):
                problems.append(f"case {case}: {name} admitted={r.admitted} reaches={r.reaches_truth}")
            if not r.admitted and r.readings:
                problems.append(f"case {case}: {name} not admitted but enumerated")
        refused = CA.refused_by(report)
        if refused:
            problems.append(f"case {case}: refused by {refused}")
        # every reading is a different Application each time: determinism
        again = CA.baseline_report(public, truth)
        for name in report:
            if [CA.application_key(a) for a in report[name].readings] != \
                    [CA.application_key(a) for a in again[name].readings]:
                problems.append(f"case {case}: {name} is not deterministic")
    return check("gate (o): every baseline is admitted exactly where the evidence admits it, none reaches any of "
                 "the five cases, and no case is refused", not problems, "\n".join(problems))


def test_gate_o_narratives_case_1():
    """Section 4's worked example (i) and section 7's Case 1 baselines."""
    problems = []
    public = bowline(1)
    report = CA.baseline_report(public, CA.fold(public))
    amount = report["amount_only"]
    if len(amount.readings) != 2:
        problems.append(f"amount-only enumerates {len(amount.readings)} readings; R2 is SI-3103 or SI-3105")
    fixed = amount.readings[0]
    if _applied(fixed, R1) != {"SI-3100": D("300.00"), "SI-3102": D("3600.00")}:
        problems.append(f"amount-only R1 {_applied(fixed, R1)}")
    if dict(fixed.credit_note("CN-0412").applied) != {"SI-3101": D("270.00")}:
        problems.append(f"amount-only CN {fixed.credit_note('CN-0412').applied}")
    if _applied(fixed, R3) != {"SI-3101": D("2130.00"), "SI-3104": D("1590.00")}:
        problems.append(f"amount-only R3 {_applied(fixed, R3)}")
    if _applied(fixed, R2) != {"SI-3103": D("2970.00")} or _applied(amount.readings[1], R2) != {"SI-3105": D("2970.00")}:
        problems.append("amount-only R2 branches")
    if fixed.closing_ar != D("3270.00"):
        problems.append(f"amount-only ties to AR at {fixed.closing_ar}, expected 3270.00")
    rows = {r.invoice_id: r for r in fixed.register}
    exact_rows = sum(1 for r in CASE_1_REGISTER if rows[r.invoice_id] == r)
    if exact_rows != 2:
        problems.append(f"worked example (i): {exact_rows} exact rows, expected 2 of 6")
    oldest = report["oldest_first"].readings[0]
    if _applied(oldest, R1) != {"SI-3100": D("300.00"), "SI-3101": D("2400.00"), "SI-3102": D("1200.00")}:
        problems.append(f"oldest-first R1 {_applied(oldest, R1)}")
    if _applied(oldest, R3) != {"SI-3102": D("2130.00"), "SI-3104": D("1590.00")}:
        problems.append(f"oldest-first R3 {_applied(oldest, R3)}")
    if oldest.row("SI-3104").remaining != D("300.00") or oldest.row("SI-3100").remaining != 0:
        problems.append("oldest-first: SI-3104 open at 300.00 instead of SI-3100")
    ignored = report["credit_ignored"].readings[0]
    if ignored.row("SI-3102").remaining != D("270.00") or ignored.credit_notes:
        problems.append(f"credit-ignored {ignored.row('SI-3102')} {ignored.credit_notes}")
    return check("Case 1: amount-only finds the exact pair (worked example (i), 2 of 6 rows, ties to AR), "
                 "oldest-first leaves SI-3104 open at 300.00, credit-ignored leaves SI-3102 at 270.00",
                 not problems, "\n".join(problems))


def test_gate_o_narratives_case_2():
    problems = []
    public = bowline(2)
    truth = CA.fold(public)
    report = CA.baseline_report(public, truth)
    r3 = "2026-04-28:SI-3104 SI-3102"
    want = {
        "mixed_amount_only": {"SI-3100": D("300.00"), "SI-3102": D("1830.00")},
        "mixed_oldest_first": {"SI-3100": D("300.00"), "SI-3102": D("1830.00")},
        "hold_on_account": {},
        "printed_order": {"SI-3104": D("1890.00"), "SI-3102": D("240.00")},
        "number_order": {"SI-3102": D("1830.00"), "SI-3104": D("300.00")},
    }
    for name, applied in want.items():
        readings = report[name].readings
        if len(readings) != 1:
            problems.append(f"{name}: {len(readings)} readings")
            continue
        if _applied(readings[0], r3) != applied:
            problems.append(f"{name}: R3 {_applied(readings[0], r3)}, expected {applied}")
        if name != "number_order":
            if readings[0].closing_ar != D("4860.00"):
                problems.append(f"{name}: does not tie to AR ({readings[0].closing_ar})")
            wrong_rows = [r.invoice_id for r in readings[0].register if r != truth.row(r.invoice_id)]
            if len(wrong_rows) != 2:
                problems.append(f"{name}: wrong rows {wrong_rows}, expected two")
    if report["hold_on_account"].readings[0].receipt(r3).unapplied != D("2130.00"):
        problems.append("hold-on-account does not hold 2,130.00")
    if report["number_order"].reaches_truth is not True or not report["number_order"].diagnostic:
        problems.append("Case 2's invoice-number-order coincidence is not recorded as a diagnostic")
    if CA.refused_by(report):
        problems.append(f"refused by {CA.refused_by(report)}")
    if report["mixed_amount_only"].readings[0].receipt(r3).rungs != ("exact_amount",):
        problems.append("mixed amount-only did not find the exact subset SI-3100 + SI-3102")
    return check("Case 2: the mixed forms close SI-3100, hold-on-account holds 2,130.00, printed order gives "
                 "1,890/240 — each ties to AR with R3 and two rows wrong; number order coincides, as a diagnostic",
                 not problems, "\n".join(problems))


def test_gate_o_narratives_cases_3_4_5():
    problems = []
    for case, wo_all, wo_none_open in ((3, {"SI-3102": D("40.00"), "SI-3104": D("20.00")}, ("SI-3104", D("20.00"))),
                                       (4, {"SI-3102": D("10.00"), "SI-3104": D("100.00")}, ("SI-3102", D("10.00")))):
        public = bowline(case)
        report = CA.baseline_report(public, CA.fold(public))
        everything = report["write_off_everything"].readings[0]
        if dict(everything.receipt(R3).written_off) != wo_all or everything.closing_ar != D("3270.00"):
            problems.append(f"case {case}: write-off-everything {everything.receipt(R3).written_off} "
                            f"{everything.closing_ar}")
        nothing = report["write_off_nothing"].readings[0]
        invoice_id, open_ = wo_none_open
        if nothing.receipt(R3).written_off or nothing.row(invoice_id).remaining != open_:
            problems.append(f"case {case}: write-off-nothing {nothing.row(invoice_id)}")
        if report["write_off_everything"].reaches_truth or report["write_off_nothing"].reaches_truth:
            problems.append(f"case {case}: a write-off baseline reaches the truth")
    public = bowline(5)
    truth = CA.fold(public)
    report = CA.baseline_report(public, truth)
    oldest = report["oldest_first"].readings[0]
    if dict(oldest.credit_note("CN-0412").applied) != {"SI-3102": D("540.00")}:
        problems.append(f"case 5 oldest-first CN {oldest.credit_note('CN-0412').applied}")
    if (oldest.receipt(R3).applied, oldest.receipt(R3).unapplied) != (truth.receipt(R3).applied, D("30.00")):
        problems.append(f"case 5 oldest-first R3 {oldest.receipt(R3)}")
    if _applied(oldest, R1) == _applied(truth, R1) or report["oldest_first"].reaches_truth:
        problems.append("case 5 oldest-first R1 agrees with the truth")
    if oldest.closing_ar != D("2940.00"):
        problems.append(f"case 5 oldest-first closing {oldest.closing_ar}")
    return check("Cases 3 and 4: neither write-off reading matches (each ties to 3,270.00 or leaves the tolerance "
                 "side open); Case 5: oldest-first agrees on R3 and the residue and not on R1 or the credit",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_fold_holds_the_public_only_discipline,
    test_the_five_cases_fold_to_section_7,
    test_the_six_variant_packs_fold_to_their_documents,
    test_case_1_document_is_the_spec_example,
    test_period_basis_is_the_balance_entering_the_period,
    test_every_refusal_fires_on_a_minimal_fixture,
    test_u12_warns_and_does_not_refuse,
    test_rung_3_remainder_after_the_named_invoices,
    test_credit_note_residue_no_other_invoice_absorbs,
    test_advice_residue_while_another_invoice_is_open,
    test_credit_note_against_a_paid_invoice_routes_as_excess,
    test_equal_invoice_dates_resolve_by_invoice_id,
    test_rung_2_is_invoice_date_order_not_printed_or_number_order,
    test_deductions_around_the_tolerance,
    test_gate_o_baselines_are_fixed_functions_and_none_reaches_a_case,
    test_gate_o_narratives_case_1,
    test_gate_o_narratives_case_2,
    test_gate_o_narratives_cases_3_4_5,
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
