"""The cash-application family on the world machinery: Bowline April 2026 and
its five variants, and the three matched pairs of 2026-09 that carry six more
(spec section 8, implementation order step 3).

Bowline Marine Supply Co., April 2026, is authored once (`worlds/_bowline.py`)
and varied five times (`bowline_2026_04_c1.py` .. `_c5.py`): the third
receipt, the credit note and the mutation plan differ, nothing else. Each
variant projects the eight legacy files plus `open_items.csv`,
`remittance_advice.csv` and `credit_notes.csv`, and derives — beside the
ledger contract — the TRUTH register `application/1` will score against,
folded from the authored `AppliedReceipt` lines and `CreditNote` through the
policy in `graph/derive.py`.

What is witnessed:

  * the family is five variants of one company-month, inferred from the
    events (no field on `World` or `TaskSpec`), with the world and task ids
    the spec names, one shared prompt, and — since step 6 put them in
    `REGISTRY` beside the shipped ids — none of them DISPLACING a legacy
    one: the legacy surface is `LEGACY_TASK_IDS`, still 95, disjoint from
    the five, and `REGISTRY` is exactly the union. The 95 shipped tasks are
    untouched and the ten shipped worlds' graph digests are the frozen ones,
    while dropping a role pair from a family world moves its digest;
  * the projected pack is the spec's, byte for byte where the spec prints
    it: Case 1's three files, Case 5's credit note, Case 2's absent advice,
    the manifest rows, the write-off account, the addendum in the statement
    reference, the cheque row that identifies the remitter. Case 2's
    reference departs from the spec's printed text on purpose: it reads
    `TRC0428442 SI-3104 SI-3102`, the bank's own trace ahead of the payer's
    invoice list, because the corrected identity rule admits no identity in a
    list of invoice ids and that case has no advice to declare one. TWO
    THINGS STILL CARRY THE OLD TEXT and are named rather than left to be
    found: `cash_application_spec.md` still prints the reference as `SI-3104
    SI-3102` (sections 1 and 7) and awaits the amendment the reviewer's
    decision 6 already requires, and `tests/test_cash_application_fold.py`
    builds its own spec-shaped fixtures, which are internally consistent and
    now describe a pack this repository does not ship;
  * the consequence for an already-archived measurement: Case 2's receipt key
    moved with its reference, so the delivered artifact in the screen
    workspace `cash_screen_evidence/workspaces/cash_application_002` is no
    longer reproducible against this source. Pinned, with the superseded key
    and the disclosures that name it, rather than described;
  * gate (m): for each of the five bundles the PUBLIC fold
    (`graph/cash_application.py`, over the ACTUAL projected bytes) equals
    the truth derived from the authored facts, under an application key
    built independently on each side, and both close at the expected
    ledger's `Assets:AR`; the truth is section 7's tables, receipt by
    receipt and row by row; every write-off is a separate entry of the
    expected ledger with the register's amount, invoice, date, customer and
    shape;
  * gate (l): the register entering the period ties to the opening entry on
    the public bytes and the truth alike, and refuses when it does not;
  * gate (n): a receipt narration may carry the genuine payment reference;
    an application instruction — with or without an amount — an invoice no
    PUBLIC document ties to the payment (an advice-less receipt's authored
    lines are not one, even when rung (3) reaches them) and an invented
    credit note are refused, in narrations and advice notes;
  * U12 is a warning, not a gate: a deduction of exactly 25.00 and an
    advice line on a zero-balance invoice pass every world gate and carry a
    `WARN:` line, so a world at the spec's own boundary passes verify_world;
  * every other world gate (`world_checks`: schema, derivation, golden 1.0,
    original unresolved, the merged trap, leaked ids, derived literals, name
    pools, policy headings, plant coverage) passes for all five; gate (f),
    scoped to the bank-evidenced plants, reads every case uniquely as the
    planted repairs — the spec's open implementation risk (section 8) is
    resolved by an EVIDENCED payment identity in `identify.py`
    (`_identity_reference`: the advice declares the ACH addendum, the bank
    declares its own trace), which `tests/test_family_validators.py` pins
    mechanism by mechanism;
  * the plants are the spec's: R2 omitted in every case on the bank's date,
    R3 transposed with the stated parameters to the stated as-found amounts,
    the write-off omitted alone in Case 3 and booked in Case 4;
  * the bank-date posting rule holds independently of the plant: with
    nothing planted the ledger still posts the cheque receipt on the bank's
    date while the advice keeps the cheque date as evidence;
  * the cheque-sign extension: an applied receipt settled by cheque is
    money IN; an ACH one prints its addendum; the receipt validators and
    the cumulative per-invoice check refuse what the spec says they refuse;
    the write-off rule at 24.99 / 25.00 / 25.01; the optional role;
  * gate (o) on the actual bytes: no named baseline reaches any case.

    python tests/test_cash_application_worlds.py
"""

from __future__ import annotations

import ast
import dataclasses
import json
import sys
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from beancount_ledger.candidate.canonical import canonical_bytes, domain_digest  # noqa: E402
from beancount_ledger.candidate.normalise import Accepted, parse_once  # noqa: E402
from beancount_ledger.candidate.schema import ParsedTransaction  # noqa: E402
from beancount_ledger.graph import cash_application as CA  # noqa: E402
from beancount_ledger.graph import derive as DV  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402
from beancount_ledger.graph import policy as P  # noqa: E402
from beancount_ledger.graph import project as PJ  # noqa: E402
from beancount_ledger.graph import schema as S  # noqa: E402
from beancount_ledger.graph.derive import DerivationError, TaskSpec, derive_contract  # noqa: E402
from beancount_ledger.graph.project import MutationPlan, project  # noqa: E402
from beancount_ledger.graph.worlds import (  # noqa: E402
    CASH_APPLICATION_MODULES,
    CASH_APPLICATION_PAIR_MODULES,
    CASH_APPLICATION_REGISTRY,
    LEGACY_TASK_IDS,
    REGISTRY,
    WORLD_MODULES,
    _bowline as B,
    _variant_pack as VP,
)

from world_checks import check_world_task, narration_problems, public_ties  # noqa: E402

FREEZE = ROOT / "tests" / "legacy_freeze.json"
WORLDS_DIR = ROOT / "beancount_ledger" / "graph" / "worlds"
GANNET, SHEARWATER = "Gannet Rigging Inc", "Shearwater Bay Charters LLC"
AR, BANK = "Assets:AR", "Assets:Bank:Checking"
WRITE_OFFS = "Expenses:SmallBalanceWriteOffs"
R1, R2, R3 = "2026-04-10:GR PAYRUN 0410", "2026-04-21:2291", "2026-04-28:GR PAYRUN 0428"
#: Case 2 has no advice for R3, so its identity is the bank's own trace,
#: printed ahead of the invoice list rung (2) reads.
R3_CASE_2 = "2026-04-28:TRC0428442 SI-3104 SI-3102"
#: What Case 2's R3 keyed to BEFORE the identity rule was corrected, and what
#: the archived screen workspace `cash_application_002` was measured against.
#: Kept as a constant so the divergence is a pinned fact rather than prose.
R3_CASE_2_SUPERSEDED = "2026-04-28:SI-3104 SI-3102"
SCREEN_WORKSPACE = "cash_screen_evidence/workspaces/cash_application_002"
#: The published screen: a note plus a self-contained evidence directory of the
#: same basename. Named here because the disclosure above has to reach a reader
#: who has only these two, and because the sidecar's provenance fields have to
#: describe the revision the run was MEASURED at, not the one they were written
#: at — the two differ for exactly this case.
SCREEN_NOTE = ROOT / "reviews" / "cash_application_screen_2026-09-10.md"
SCREEN_EVIDENCE = ROOT / "reviews" / "cash_application_screen_2026-09-10"
SCREEN_SIDECAR = SCREEN_EVIDENCE / "provenance.json"
PUBLISHED_WORKSPACE = "workspaces/cash_application_002"
FAMILY_FILES = ("open_items.csv", "remittance_advice.csv", "credit_notes.csv")
LEGACY_FILES = ("manifest.md", "policy.md", "accounts.csv", "customers.csv", "vendors.csv",
                "archive_prior_period.csv", "ledger.beancount", "bank_statement.csv")


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:40]:
            print(f"      {line}")
    return ok


# --------------------------------------------------------------------------
# the five cases, derived once
# --------------------------------------------------------------------------

_DERIVED: dict = {}


def case(n: int):
    """(module, world, task, bundle, inputs, public) for case n."""
    if n not in _DERIVED:
        module = CASH_APPLICATION_MODULES[n - 1]
        task = module.TASKS[f"cash_application_{n:03d}"]
        bundle, inputs = derive_contract(module.WORLD, task)
        public = {name: data.decode("utf-8") for name, data in inputs.public_files}
        _DERIVED[n] = (module, module.WORLD, task, bundle, inputs, public)
    return _DERIVED[n]


def kw(task):
    return dict(bank_account=BANK, period_start=task.period.start, period_end=task.period.end)


def pairs(*items):
    return tuple((invoice_id, D(amount)) for invoice_id, amount in items)


def txns(text):
    parsed = parse_once(text)
    assert isinstance(parsed, Accepted), parsed
    return [t for t in parsed.submission.directives if isinstance(t, ParsedTransaction)]


def shape(t):
    return tuple(sorted((p.account, D(p.amount)) for p in t.postings))


# --------------------------------------------------------------------------
# section 7, transcribed
# --------------------------------------------------------------------------

def row(invoice_id, customer, basis, applied, credited, written_off, remaining):
    return (invoice_id, customer, D(basis), D(applied), D(credited), D(written_off), D(remaining))


CASE_1_REGISTER = (
    row("SI-3100", GANNET, "300.00", "0.00", "0.00", "0.00", "300.00"),
    row("SI-3101", GANNET, "2400.00", "2400.00", "0.00", "0.00", "0.00"),
    row("SI-3102", GANNET, "3600.00", "3330.00", "270.00", "0.00", "0.00"),
    row("SI-3103", SHEARWATER, "2970.00", "2970.00", "0.00", "0.00", "0.00"),
    row("SI-3104", GANNET, "1890.00", "1890.00", "0.00", "0.00", "0.00"),
    row("SI-3105", SHEARWATER, "2970.00", "0.00", "0.00", "0.00", "2970.00"),
)


def register(*changes):
    rows = {r[0]: r for r in CASE_1_REGISTER}
    for r in changes:
        rows[r[0]] = r
    return tuple(rows[k] for k in sorted(rows))


R1_APPLIED = pairs(("SI-3101", "2400.00"), ("SI-3102", "1500.00"))
R2_APPLIED = pairs(("SI-3103", "2970.00"))
CN_ON_3102 = {"CN-0412": (pairs(("SI-3102", "270.00")), D("0.00"))}

#: receipts: receipt_id -> (applied, written_off, unapplied); credits; register; closing AR;
#: statement closing; R3's amount as found in the opening ledger; the plants (id -> kind)
EXPECTED = {
    1: dict(receipts={R1: (R1_APPLIED, (), "0.00"), R2: (R2_APPLIED, (), "0.00"),
                      R3: (pairs(("SI-3102", "1830.00"), ("SI-3104", "1890.00")), (), "0.00")},
            credits=CN_ON_3102, register=CASE_1_REGISTER, closing="3270.00", statement="66370.00",
            r3_found="3702.00", plants={"unrecorded_customer_check": "omit", "transposed_payrun_receipt": "alter"}),
    2: dict(receipts={R1: (R1_APPLIED, (), "0.00"), R2: (R2_APPLIED, (), "0.00"),
                      R3_CASE_2: (pairs(("SI-3102", "1830.00"), ("SI-3104", "300.00")), (), "0.00")},
            credits=CN_ON_3102, register=register(row("SI-3104", GANNET, "1890.00", "300.00", "0.00", "0.00", "1590.00")),
            closing="4860.00", statement="64780.00", r3_found="2310.00",
            plants={"unrecorded_customer_check": "omit", "transposed_payrun_receipt": "alter"}),
    3: dict(receipts={R1: (R1_APPLIED, (), "0.00"), R2: (R2_APPLIED, (), "0.00"),
                      R3: (pairs(("SI-3102", "1790.00"), ("SI-3104", "1870.00")), pairs(("SI-3104", "20.00")), "0.00")},
            credits=CN_ON_3102,
            register=register(row("SI-3102", GANNET, "3600.00", "3290.00", "270.00", "0.00", "40.00"),
                              row("SI-3104", GANNET, "1890.00", "1870.00", "0.00", "20.00", "0.00")),
            closing="3310.00", statement="66310.00", r3_found="3660.00",
            plants={"unrecorded_customer_check": "omit", "omitted_short_payment_write_off": "omit"}),
    4: dict(receipts={R1: (R1_APPLIED, (), "0.00"), R2: (R2_APPLIED, (), "0.00"),
                      R3: (pairs(("SI-3102", "1820.00"), ("SI-3104", "1790.00")), pairs(("SI-3102", "10.00")), "0.00")},
            credits=CN_ON_3102,
            register=register(row("SI-3102", GANNET, "3600.00", "3320.00", "270.00", "10.00", "0.00"),
                              row("SI-3104", GANNET, "1890.00", "1790.00", "0.00", "0.00", "100.00")),
            closing="3370.00", statement="66260.00", r3_found="3160.00",
            plants={"unrecorded_customer_check": "omit", "transposed_payrun_receipt": "alter"}),
    5: dict(receipts={R1: (R1_APPLIED, (), "0.00"), R2: (R2_APPLIED, (), "0.00"),
                      R3: (pairs(("SI-3102", "1860.00"), ("SI-3104", "1890.00")), (), "30.00")},
            credits={"CN-0412": (pairs(("SI-3100", "300.00"), ("SI-3102", "240.00")), D("0.00"))},
            register=register(row("SI-3100", GANNET, "300.00", "0.00", "300.00", "0.00", "0.00"),
                              row("SI-3102", GANNET, "3600.00", "3360.00", "240.00", "0.00", "0.00")),
            closing="2940.00", statement="66430.00", r3_found="3870.00",
            plants={"unrecorded_customer_check": "omit", "transposed_payrun_receipt": "alter"}),
}

#: Section 2's three files, Case 1, byte for byte.
SPEC_OPEN_ITEMS = """invoice_id,customer,invoice_date,due_date,original_amount,open_balance
SI-3100,Gannet Rigging Inc,2026-02-26,2026-03-28,1080.00,300.00
SI-3101,Gannet Rigging Inc,2026-03-03,2026-04-02,2400.00,2400.00
SI-3102,Gannet Rigging Inc,2026-03-12,2026-04-11,3600.00,3600.00
SI-3103,Shearwater Bay Charters LLC,2026-03-18,2026-04-17,2970.00,2970.00
"""
SPEC_REMITTANCE = """remittance_id,customer,remittance_date,payment_method,payment_reference,payment_amount,invoice_id,amount_paid,settles_invoice,deduction_amount,note
RA-0410-GR,Gannet Rigging Inc,2026-04-10,ACH,GR PAYRUN 0410,3900.00,SI-3101,2400.00,yes,0.00,
RA-0410-GR,Gannet Rigging Inc,2026-04-10,ACH,GR PAYRUN 0410,3900.00,SI-3102,1500.00,no,0.00,part payment; balance held pending credit for damaged crates
RA-0410-GR,Gannet Rigging Inc,2026-04-10,ACH,GR PAYRUN 0410,3900.00,SI-3100,0.00,no,0.00,withheld; short shipment; credit requested
RA-0416-SB,Shearwater Bay Charters LLC,2026-04-16,CHECK,2291,2970.00,SI-3103,2970.00,yes,0.00,
RA-0428-GR,Gannet Rigging Inc,2026-04-28,ACH,GR PAYRUN 0428,3720.00,SI-3102,1830.00,yes,0.00,Cash amount after application of CN-0412; do not deduct the credit again.
RA-0428-GR,Gannet Rigging Inc,2026-04-28,ACH,GR PAYRUN 0428,3720.00,SI-3104,1890.00,yes,0.00,
"""
SPEC_CREDIT_NOTES = """credit_note_id,date,customer,invoice_id,net_amount,tax_amount,gross_amount,reason
CN-0412,2026-04-15,Gannet Rigging Inc,SI-3102,250.00,20.00,270.00,damaged crates
"""
SPEC_CREDIT_NOTE_CASE_5 = "CN-0412,2026-04-15,Gannet Rigging Inc,SI-3100,500.00,40.00,540.00,agreed price allowance on goods retained"
SPEC_MANIFEST_ROWS = (
    "| `open_items.csv` | Open sales-invoice register at 2026-04-01. 4 rows. Columns: invoice_id, customer, "
    "invoice_date, due_date, original_amount, open_balance. |",
    "| `remittance_advice.csv` | Customer remittance advices, one row per advice line. 6 rows. Columns: "
    "remittance_id, customer, remittance_date, payment_method, payment_reference, payment_amount, invoice_id, "
    "amount_paid, settles_invoice, deduction_amount, note. |",
    "| `credit_notes.csv` | Credit notes issued in the period. 1 row. Columns: credit_note_id, date, customer, "
    "invoice_id, net_amount, tax_amount, gross_amount, reason. |",
)
WRITE_OFF_ENTRY_CASE_3 = ('2026-04-28 * "Gannet Rigging Inc" "Short payment on SI-3104 written off under the cash '
                          'application policy"')


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------

def test_the_family_is_five_variants_of_one_company_month():
    problems = []
    if [m.WORLD.id for m in CASH_APPLICATION_MODULES] != [f"bowline-2026-04-c{n}" for n in range(1, 6)]:
        problems.append(f"world ids {[m.WORLD.id for m in CASH_APPLICATION_MODULES]}")
    if sorted(CASH_APPLICATION_REGISTRY) != [f"cash_application_{n:03d}" for n in range(1, 12)]:
        problems.append(f"task ids {sorted(CASH_APPLICATION_REGISTRY)}")
    if [m.TASKS and sorted(m.TASKS) for m in CASH_APPLICATION_MODULES] != [[f"cash_application_{n:03d}"]
                                                                           for n in range(1, 6)]:
        problems.append(f"the Bowline modules no longer carry 001..005: "
                        f"{[sorted(m.TASKS) for m in CASH_APPLICATION_MODULES]}")
    # The five are served ids like any other now, so what has to hold is
    # that they did not DISPLACE any of the 95: the legacy surface is
    # `LEGACY_TASK_IDS` (the registry as it stood before the family joined),
    # it still holds 95 ids, and none of them is a family id.
    if len(LEGACY_TASK_IDS) != 95 or set(CASH_APPLICATION_REGISTRY) & set(LEGACY_TASK_IDS):
        problems.append(f"the legacy surface carries {len(LEGACY_TASK_IDS)} tasks and shares "
                        f"{sorted(set(CASH_APPLICATION_REGISTRY) & set(LEGACY_TASK_IDS))}")
    if set(REGISTRY) != set(LEGACY_TASK_IDS) | set(CASH_APPLICATION_REGISTRY):
        problems.append("REGISTRY is not the 95 legacy ids plus the eleven family ids")
    worlds = [m.WORLD for m in CASH_APPLICATION_MODULES]
    tasks = [m.TASKS[f"cash_application_{n:03d}"] for n, m in enumerate(CASH_APPLICATION_MODULES, start=1)]
    shared = ("title", "currency", "bank_account", "bank_party_id", "accounts", "parties", "documents",
              "bank_opening", "opening", "roles", "policy_text")
    for attr in shared:
        if len({repr(getattr(w, attr)) for w in worlds}) != 1:
            problems.append(f"the five worlds differ in {attr}")
    if len({t.prompt for t in tasks}) != 1 or {t.type for t in tasks} != {"bank_reconciliation"} \
            or len({(t.period.start, t.period.end) for t in tasks}) != 1:
        problems.append("the five tasks do not share one prompt, one type and one period")
    for w in worlds:
        if not P.is_cash_application_world(w):
            problems.append(f"{w.id}: the family is not inferred from the events")
        events = {e.id: e for e in w.events}
        for shared_event in B.MARCH_EVENTS + (B.SALE_3104, B.SALE_3105, B.PI_8813_PAYMENT, B.FEE_APRIL, B.R2):
            if events.get(shared_event.id) != shared_event:
                problems.append(f"{w.id}: {shared_event.id} differs from the shared fact")
        r1 = events["event:gr-payrun-0410"]
        if dataclasses.replace(r1, lines=r1.lines[:2]) != dataclasses.replace(B.r1(), lines=B.r1().lines[:2]) \
                or r1.lines[2].invoice_id != "doc:si-3100" or r1.lines[2].amount != 0:
            problems.append(f"{w.id}: R1 differs from the shared fact beyond its withheld line's note")
    if {f.name for f in dataclasses.fields(S.World)} != {"id", "title", "currency", "bank_account", "bank_party_id",
                                                          "accounts", "parties", "documents", "bank_opening",
                                                          "opening", "events", "roles", "policy_text",
                                                          "schema_version"} \
            or {f.name for f in dataclasses.fields(TaskSpec)} != {"id", "type", "prompt", "period", "plan"}:
        problems.append("a family field was added to World or TaskSpec")
    prompt = tasks[0].prompt
    for word in ("write-off", "written off", "transpos", "missing", "unapplied cash", "SI-31", "3,7", "R3"):
        if word.lower() in prompt.lower() and word not in ("written off",):
            problems.append(f"the prompt reveals {word!r}")
    for name in ("Bowline", "Gannet", "Shearwater", "Marram", "Northshore"):
        for pool, values in __import__("world_checks").generator_name_pools().items():
            if any(name.casefold() in v.casefold() for v in values):
                problems.append(f"{name!r} is drawn by the generator's {pool}")
    return check("five worlds bowline-2026-04-c1..c5 / tasks cash_application_001..005: one chart, one set of "
                 "parties, documents, March, R1, R2 and sales, one prompt, family inferred from the events, no "
                 "field added, none in the legacy registry of 95, and the family registry is those five plus the "
                 "six variant-pack ids", not problems, "\n".join(problems))


def test_every_gate_passes_for_all_five():
    problems = []
    for n in range(1, 6):
        module, world, task, *_ = case(n)
        found, warnings = check_world_task(world, task, source_path=WORLDS_DIR / f"{module.__name__.rsplit('.', 1)[1]}.py")
        problems += [f"case {n}: {p}" for p in found]
        for w in warnings:
            print(f"      case {n}: {w[:200]}")
        # the shared module is scanned for derived literals too
        found_shared, _ = check_world_task(world, task, source_path=WORLDS_DIR / "_bowline.py")
        problems += [f"case {n} (_bowline.py): {p}" for p in found_shared
                     if "appears as" in p and "literal" in p]
    return check("every world gate — schema, derivation, golden 1.0, original unresolved, merged trap, scoped (f), "
                 "private ids, derived literals (the case module and _bowline.py), name pools, headings, the "
                 "family's (l), (m), (n) and plant coverage — passes for all five", not problems, "\n".join(problems))


def test_gate_f_reads_every_case_as_the_planted_repairs():
    """Gate (f), scoped to the bank-evidenced plants. The spec's open
    implementation risk (section 8) was real: with `GR PAYRUN 0428` and
    `SI-3104 SI-3102` read as UNKNOWN references, the mis-keyed R3 two days
    before the cut-off admitted a second reading — the row an unrecorded
    receipt, the entry a deposit in transit — in Cases 1, 2, 4 and 5.

    Step 4 closed that with a SHAPE rule (any multi-word reference with a
    digit is an instrument), and a reviewer refused it: the shape admits an
    invoice list and a dated memo, and one sighting on each side excludes
    neither competing history. The rule now in force asks the evidence
    instead — `identify._identity_reference`: a cheque number the wording
    introduces, a bank trace id, or a reference a mounted
    `remittance_advice.csv` declares, unique across the advices and the bank
    rows. Cases 1, 3, 4 and 5 have RA-0428-GR, which declares `GR PAYRUN
    0428`. Case 2 has no advice for R3 by design, so it was given a genuine
    public identity rather than a looser rule: the bank's own trace
    `TRC0428442`, printed on the row and quoted by the entry, ahead of the
    invoice list rung (2) still reads.

    Every case reads uniquely as exactly its planted bank-evidenced repairs;
    the mechanism and its counterexamples are pinned in
    `tests/test_family_validators.py` and `tests/test_identify.py`."""
    problems = []
    for n in range(1, 6):
        _, world, task, _, inputs, public = case(n)
        verdict = ID.check_identifiable(public, **kw(task))
        planted = sorted(DV.planted_key(p, frozenset({GANNET, SHEARWATER, "Northshore Chandlery Supply"}),
                                        bank_account=BANK)
                         for p in inputs.planted if any(a == BANK for a, _ in p.required))
        read = sorted(ID.repair_key(r) for r in verdict.repairs)
        if not verdict.unique or verdict.readings != 1 or planted != read:
            problems.append(f"case {n}: unique {verdict.unique}, {verdict.readings} readings, planted {planted}, "
                            f"read {read}: {verdict.reason[:300]}")
        if verdict.matched != (4 if n == 3 else 3):
            problems.append(f"case {n}: {verdict.matched} rows matched, not {4 if n == 3 else 3}")
        kinds = sorted(r.kind for r in verdict.repairs)
        if kinds != (["missing_entry"] if n == 3 else ["missing_entry", "wrong_amount"]):
            problems.append(f"case {n}: repair kinds {kinds}")
    return check("gate (f): every case reads uniquely, with one reading, as exactly its planted bank-evidenced "
                 "repairs — R2 missing on the bank's date in all five, R3 mis-keyed in Cases 1, 2, 4 and 5 — "
                 "the spec's open risk resolved by an EVIDENCED payment identity: the advice's declared "
                 "reference in four cases, the bank's own trace in Case 2", not problems, "\n".join(problems))


def test_the_projected_pack_is_the_spec_s():
    problems = []
    _, _, _, _, inputs1, public1 = case(1)
    for name, want in (("open_items.csv", SPEC_OPEN_ITEMS), ("remittance_advice.csv", SPEC_REMITTANCE),
                       ("credit_notes.csv", SPEC_CREDIT_NOTES)):
        if public1.get(name) != want:
            problems.append(f"case 1 {name}:\n{public1.get(name)}\nis not the spec's\n{want}")
    for line in SPEC_MANIFEST_ROWS:
        if line not in public1["manifest.md"]:
            problems.append(f"case 1 manifest lacks {line!r}")
    if ("Expenses:SmallBalanceWriteOffs,expense,Short payments within the cash application tolerance written off "
            "on receipt") not in public1["accounts.csv"]:
        problems.append("accounts.csv lacks the write-off account")
    if f"{GANNET},net 30,Assets:AR" not in public1["customers.csv"] \
            or f"{SHEARWATER},net 30,Assets:AR" not in public1["customers.csv"]:
        problems.append("customers.csv does not print both customers with Assets:AR")
    if "2026-04-10,ACH IN GANNET RIGGING INC,GR PAYRUN 0410,,3900.00," not in public1["bank_statement.csv"]:
        problems.append("the ACH row does not carry the addendum as its reference")
    if "2026-04-21,CHECK 2291 SHEARWATER BAY CHARTERS LLC,2291,,2970.00," not in public1["bank_statement.csv"]:
        problems.append("the cheque row does not identify the remitter on the bank's date")
    for n in range(1, 6):
        _, _, _, bundle, inputs, public = case(n)
        if tuple(sorted(public)) != tuple(sorted(LEGACY_FILES + FAMILY_FILES)):
            problems.append(f"case {n}: public files {sorted(public)}")
        if sorted(bundle.public_files()) != sorted(public):
            problems.append(f"case {n}: Bundle.public_files() disagrees with the contract inputs")
        if public["bank_statement.csv"].splitlines()[-1].split(",")[-1] != EXPECTED[n]["statement"]:
            problems.append(f"case {n}: statement closes {public['bank_statement.csv'].splitlines()[-1]}")
        if public["bank_statement.csv"].splitlines()[1] != "2026-04-01,Opening balance carried forward,,,,60000.00":
            problems.append(f"case {n}: April does not open at 60,000.00 derived from March")
        if "## Cash application" not in public["policy.md"] or "## Credit notes" not in public["policy.md"] \
                or "`25.00`" not in public["policy.md"]:
            problems.append(f"case {n}: policy.md lacks the family's sections or the tolerance")
        if n != 5 and public["credit_notes.csv"] != SPEC_CREDIT_NOTES:
            problems.append(f"case {n}: credit_notes.csv is not Case 1's")
        if n in (1, 2, 3, 4) and public["open_items.csv"] != SPEC_OPEN_ITEMS:
            problems.append(f"case {n}: open_items.csv is not the shared register")
    _, _, _, _, _, public2 = case(2)
    if "RA-0428-GR" in public2["remittance_advice.csv"] \
            or "TRC0428442 SI-3104 SI-3102" not in public2["bank_statement.csv"]:
        problems.append("case 2: RA-0428-GR must be absent and the reference must read "
                        "TRC0428442 SI-3104 SI-3102 — the bank's trace, then the invoices rung (2) reads")
    if public2["remittance_advice.csv"] != "".join(SPEC_REMITTANCE.splitlines(True)[:5]):
        problems.append("case 2: remittance_advice.csv is not Case 1's first two advices")
    _, _, _, _, _, public5 = case(5)
    if public5["credit_notes.csv"].splitlines()[1] != SPEC_CREDIT_NOTE_CASE_5:
        problems.append(f"case 5: credit note row {public5['credit_notes.csv'].splitlines()[1]!r}")
    if "remaining balance withheld pending the agreed price allowance" not in public5["remittance_advice.csv"]:
        problems.append("case 5: R1's zero-payment line does not state the withholding")
    if public5["open_items.csv"] != SPEC_OPEN_ITEMS:
        problems.append("case 5: open_items.csv must report SI-3100's face value 1080.00 and open balance 300.00")
    return check("the projected pack is the spec's: Case 1's three files byte for byte, the manifest rows, the "
                 "write-off account, both customers on Assets:AR, the addendum in the ACH reference, the cheque row "
                 "naming the remitter, Case 2 without RA-0428-GR, Case 5's credit note; eleven files per bundle, "
                 "April opening at 60,000.00, statement closings per case", not problems, "\n".join(problems))


def test_case_2_s_inputs_moved_after_the_screen_and_the_repository_says_where():
    """An archived measurement whose inputs changed, made loud.

    Correcting the identity rule moved Case 2's 28 April statement reference
    from `SI-3104 SI-3102` to `TRC0428442 SI-3104 SI-3102`, and the receipt
    key moves with the reference column. The archived screen workspace
    `cash_screen_evidence/workspaces/cash_application_002` was measured
    against the OLD bytes: its delivered `cash_application.json` keys R3 as
    `2026-04-28:SI-3104 SI-3102`, which this source can no longer produce, so
    that delivery would not re-score as delivered. The phase brief sanctioned
    moving family bytes; it did not sanction letting an archived result quietly
    stop being reproducible.

    So this pins three things together: the key the current bytes fold to, the
    key they no longer fold to, and the fact that both the world module and
    the release attestation name the divergence. Deleting the disclosure fails
    here rather than in a reader's diff, and re-keying the case again fails
    here too, which is the point — the next person to move these bytes has to
    come back and say so.
    """
    problems = []
    module, _, _, _, _, public = case(2)
    keys = [receipt.receipt_id for receipt in CA.fold(public).receipts]
    if R3_CASE_2 not in keys:
        problems.append(f"case 2's receipts key as {keys}, without {R3_CASE_2!r}")
    if R3_CASE_2_SUPERSEDED in keys:
        problems.append(f"case 2 still folds to the superseded key {R3_CASE_2_SUPERSEDED!r}; if the reference "
                        f"moved back, the archived screen is reproducible again and this note has to be redrawn")
    disclosures = ((f"the world module {module.__name__}", Path(module.__file__).read_text(encoding="utf-8"),
                    SCREEN_WORKSPACE),
                   ("reviews/RELEASE_ATTESTATION.md",
                    (ROOT / "reviews" / "RELEASE_ATTESTATION.md").read_text(encoding="utf-8"),
                    SCREEN_WORKSPACE),
                   # The published pair has to carry it too. A reader who has only the note and the
                   # evidence directory beside it is exactly the reader who cannot check the source,
                   # so dropping the disclosure there is the one place it actually costs something.
                   ("the published note reviews/cash_application_screen_2026-09-10.md",
                    SCREEN_NOTE.read_text(encoding="utf-8"), PUBLISHED_WORKSPACE),
                   ("the published sidecar reviews/cash_application_screen_2026-09-10/provenance.json",
                    SCREEN_SIDECAR.read_text(encoding="utf-8"), "cash_application_002"))
    for label, raw, workspace in disclosures:
        text = " ".join(raw.split())
        if R3_CASE_2_SUPERSEDED not in text:
            problems.append(f"{label} does not name the superseded key {R3_CASE_2_SUPERSEDED!r}")
        if R3_CASE_2 not in text:
            problems.append(f"{label} does not name the key this source folds to, {R3_CASE_2!r}")
        if workspace not in text:
            problems.append(f"{label} does not name the archived workspace {workspace!r}")
    # Re-wrapping a paragraph must not be able to break a claim check, so the
    # prose is compared with its whitespace flattened.
    note = " ".join(SCREEN_NOTE.read_text(encoding="utf-8").split())
    if "not reproducible against this source" not in note:
        problems.append("the published note does not say the archived Case 2 delivery is not reproducible "
                        "against this source")
    return check("Case 2's inputs moved after the archived screen was measured, and the repository says so where "
                 "the change lives: the current bytes fold to the trace key, the screen's key is unreachable from "
                 "this source, and the world module, the attestation, the published note and the published "
                 "provenance sidecar all name the workspace and the key it was measured against",
                 not problems, "\n".join(problems))


def test_the_screen_sidecar_records_the_measured_revision_not_the_revision_it_was_written_at():
    """A provenance sidecar may not quietly present now-values as the run's.

    The sidecar was written at a later revision than the screen was measured
    at, and between the two, correcting the identity rule re-authored Case 2's
    world module. A world module is a MEASURED INPUT: re-deriving Case 2 at the
    later revision yields a different `bank_statement.csv` view, a different
    graph, mutation-plan, environment and task-contract digest. Recording those
    under `task_digests` would be a fixture row derived afterwards and presented
    as observed — the one case where recomputation is not recovery.

    So this pins the discipline rather than the numbers: every archived public
    input file must reproduce the view digest the sidecar records for it, which
    is only true if those digests are the measured revision's; the sidecar must
    say which revision each block was recomputed at; it must name the world
    module among what moved, and must not claim the change missed the measured
    inputs; and it must carry the later values separately for the one case that
    moved and declare none for the two that did not.
    """
    problems = []
    sidecar = json.loads(SCREEN_SIDECAR.read_text(encoding="utf-8"))
    measured = sidecar["source_revision"]["measured_at"]["short"]
    changes = sidecar["source_revision"]["changes_between"]
    worlds = "beancount_ledger/graph/worlds/bowline_2026_04_c2.py"

    if worlds not in changes["package_files_changed"]:
        problems.append(f"the sidecar's list of what moved between the revisions omits {worlds}")
    if changes["measured_input_files_changed"] != [worlds]:
        problems.append(f"the sidecar calls {changes['measured_input_files_changed']} the measured inputs "
                        f"that moved; the world module is the one that did")
    if changes["scoring_engine_files_changed"]:
        problems.append(f"the sidecar says a scoring engine moved: {changes['scoring_engine_files_changed']}")
    if sidecar["inputs_moved_after_measurement"]["tasks_whose_inputs_moved"] != ["cash_application_002"]:
        problems.append("the sidecar does not name cash_application_002, and only it, as the task whose "
                        "inputs moved")

    for task_id, block in sidecar["tasks"].items():
        for field in ("task_digests", "scorer_digests"):
            if block[field].get("recomputed_at_revision") != measured:
                problems.append(f"{task_id}: {field} does not declare it was recomputed at the measured "
                                f"revision {measured}")
        recorded = dict(map(tuple, block["task_digests"]["view_digests"]))
        workspace = SCREEN_EVIDENCE / "workspaces" / task_id
        # The delivered artifacts are outputs, not input views; everything else
        # in the workspace is a public input file and must reproduce.
        for path in sorted(workspace.iterdir()):
            if path.name in ("ledger.beancount", "cash_application.json", "delivery.json"):
                continue
            digest = PJ._view(path.name, path.read_text(encoding="utf-8"), (), (), True).digest
            if digest != recorded.get(path.name):
                problems.append(f"{task_id}: the archived {path.name} digests to {digest[:16]}… but the "
                                f"sidecar records {str(recorded.get(path.name))[:16]}… — the recorded value "
                                f"describes bytes this archive does not contain")
        differs = block["differs_at_sidecar_revision"]
        moved_here = task_id == "cash_application_002"
        if moved_here and not differs:
            problems.append(f"{task_id}: its inputs moved, but the sidecar records no later values for it")
        if differs and not moved_here:
            problems.append(f"{task_id}: its inputs did not move, but the sidecar records later values for it")
        if moved_here and differs:
            later = dict(map(lambda row: (row[0], row[2]), differs["view_digests_measured_then_sidecar"]))
            if "bank_statement.csv" not in later:
                problems.append(f"{task_id}: the sidecar does not record the later bank_statement.csv digest")
            if later.get("bank_statement.csv") == recorded.get("bank_statement.csv"):
                problems.append(f"{task_id}: the sidecar records the same digest as measured and as later; "
                                f"if the bytes moved back, this note has to be redrawn")
            if "task_contract_digest" not in differs["scalars_measured_then_sidecar"]:
                problems.append(f"{task_id}: the task contract binds the view digests, so it moved too, and "
                                f"the sidecar does not record its later value")
    return check("the screen's provenance sidecar records the measured revision's digests, corroborated file by "
                 "file against the archived bytes, and names the world module and the one task whose inputs "
                 "moved instead of presenting the later values as the run's",
                 not problems, "\n".join(problems))


def test_gate_m_the_public_fold_over_actual_bytes_equals_the_truth():
    problems = []
    for n in range(1, 6):
        _, world, task, bundle, inputs, public = case(n)
        truth = inputs.application
        try:
            app = CA.fold(public, **kw(task))
        except Exception as exc:
            problems.append(f"case {n}: the public fold refused the projected bytes: {exc}")
            continue
        if CA.application_key(app) != truth.application_key():
            problems.append(f"case {n}: public {CA.application_key(app)}\n  truth {truth.application_key()}")
        expected_ar = dict(inputs.expected_balances)[AR]
        if not (app.closing_ar == truth.closing_ar == expected_ar == D(EXPECTED[n]["closing"])):
            problems.append(f"case {n}: closing AR public {app.closing_ar} truth {truth.closing_ar} ledger "
                            f"{expected_ar} spec {EXPECTED[n]['closing']}")
        if app.opening_ar != truth.opening_ar != D("9270.00"):
            problems.append(f"case {n}: opening AR {app.opening_ar} / {truth.opening_ar}")
        # the truth is section 7's tables
        got = {r[0]: (r[4], r[5], r[6]) for r in truth.receipts}
        for receipt_id, (applied, written_off, unapplied) in EXPECTED[n]["receipts"].items():
            if got.get(receipt_id) != (applied, written_off, D(unapplied)):
                problems.append(f"case {n}: truth receipt {receipt_id} {got.get(receipt_id)} != "
                                f"{(applied, written_off, D(unapplied))}")
        if set(got) != set(EXPECTED[n]["receipts"]):
            problems.append(f"case {n}: receipts {sorted(got)}")
        credits = {c[0]: (c[4], c[5]) for c in truth.credit_notes}
        if credits != EXPECTED[n]["credits"]:
            problems.append(f"case {n}: credit applications {credits} != {EXPECTED[n]['credits']}")
        if truth.register != EXPECTED[n]["register"]:
            for a, b in zip(truth.register, EXPECTED[n]["register"]):
                if a != b:
                    problems.append(f"case {n}: row {a} != {b}")
        # the document the fold would deliver is the spec's shape
        doc = CA.document(app)
        if doc["schema"] != "piv.cash-application/1" or len(doc["closing_open_items"]) != 6:
            problems.append(f"case {n}: document {doc['schema']} with {len(doc['closing_open_items'])} rows")
    # the two keys are built independently: derive.py never imports the public fold
    tree = ast.parse((ROOT / "beancount_ledger" / "graph" / "derive.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and "cash_application" in (node.module or ""):
            problems.append("derive.py imports the public fold; the truth side is not independent")
        if isinstance(node, ast.Import) and any("cash_application" in a.name for a in node.names):
            problems.append("derive.py imports the public fold; the truth side is not independent")
    return check("gate (m): for all five bundles the public fold over the projected bytes equals the truth folded "
                 "from the authored facts under independently built keys, both close at the expected ledger's AR, "
                 "and the truth is section 7's receipts, write-offs, credit applications, unapplied residues and "
                 "register rows", not problems, "\n".join(problems))


def test_gate_l_the_register_ties_to_the_opening_entry():
    problems = []
    _, world, task, _, inputs, public = case(1)
    ev = CA.read_evidence(public, **kw(task))
    if ev.opening_ar != D("9270.00") or inputs.application.opening_ar != D("9270.00") \
            or dict(world.opening.carried)[AR] != D("9270.00"):
        problems.append("the register, the truth and the opening entry do not all say 9,270.00")
    if sum((r[5] for r in inputs.application.opening_register), D(0)) != D("9270.00"):
        problems.append("the truth's opening register does not sum to the opening entry")
    # public side: a register that does not tie is refused with the spec's name
    edited = dict(public)
    edited["open_items.csv"] = public["open_items.csv"].replace("2400.00,2400.00", "2400.00,2300.00")
    try:
        CA.read_evidence(edited, **kw(task))
        problems.append("the public fold accepted a register 100.00 short of the opening entry")
    except CA.Refusal as exc:
        if exc.code != "REFUSE_REGISTER_DOES_NOT_TIE":
            problems.append(f"public refusal {exc.code}")
    # truth side: the opening position and the invoices disagree
    world_short = dataclasses.replace(world, opening=S.OpeningPosition(
        "2026-04-01", ((AR, D("9170.00")), ("Assets:Inventory", D("23400.00")), ("Liabilities:AP", D("-11600.00")))))
    try:
        derive_contract(world_short, task)
        problems.append("derivation accepted an opening entry 100.00 short of the register")
    except DerivationError as exc:
        if "REFUSE_REGISTER_DOES_NOT_TIE" not in str(exc):
            problems.append(f"derivation refused for another reason: {str(exc)[:200]}")
    # the family gate in world_checks names it too
    found, _ = check_world_task(world_short, task)
    if not any("REFUSE_REGISTER_DOES_NOT_TIE" in p for p in found):
        problems.append(f"world_checks did not name the tie: {found[:3]}")
    return check("gate (l): open_items.csv sums to the opening entry's Assets:AR on the public bytes and in the "
                 "truth; a register that does not tie is REFUSE_REGISTER_DOES_NOT_TIE on both sides",
                 not problems, "\n".join(problems))


def test_gate_n_the_narration_rule():
    problems = []
    tied = frozenset({"SI-3102", "SI-3104"})
    notes = frozenset({"CN-0412"})
    allowed = ("Customer payment, GR PAYRUN 0428",
               "Cash amount after application of CN-0412; do not deduct the credit again.",
               "Short payment on SI-3104 written off under the cash application policy",
               "Short payments on SI-3102 and SI-3104 written off under the cash application policy",
               "Customer payment, TRC0428442 SI-3104 SI-3102", "Customer payment for SI-3102",
               "part payment; balance held pending credit for damaged crates",
               "minor remittance discrepancy; customer claims invoice settled",
               "Cash amount on SI-3102 after application of CN-0412")
    for text in allowed:
        found = narration_problems(text, tied, notes, "t")
        if found:
            problems.append(f"{text!r} refused: {found}")
    # a cheque, pay-run or reference NUMBER beside an invoice id is a genuine
    # payment reference, not an amount directed at the id; a date is not an
    # amount either, and "credit requested" is a noun, not a directive
    referenced = frozenset({"SI-3100", "SI-3102", "SI-3103"})
    for text in ("Customer check 2291 for SI-3103", "Customer payment, GR PAYRUN 0428 for SI-3102",
                 "Customer payment ref 0428, SI-3102", "Customer payment 2026-04-28 for SI-3102",
                 "SI-3100 withheld, credit requested"):
        found = narration_problems(text, referenced, notes, "t")
        if found:
            problems.append(f"{text!r} refused: {found}")
    # an APPLICATION INSTRUCTION directs money to an id, with or without an
    # amount: the spec's "apply 1,830.00 to SI-3102" is an instance, not the
    # definition. Every id below is tied, so the instruction is the only
    # refusal each can earn.
    all_tied = frozenset({"SI-3101", "SI-3102", "SI-3104"})
    instructions = ("apply 1,830.00 to SI-3102", "1830.00 to SI-3102 and 1890.00 to SI-3104",
                    "SI-3102 is to be posted at 1830.00", "allocate 1830.00 against SI-3102",
                    "SI-3102 at 1830.00 is to be posted",
                    "Applied to SI-3101 in full and the balance to SI-3102",
                    "Customer payment, apply to SI-3101 then SI-3102",
                    "2400 to SI-3101 and 1500 to SI-3102", "$1,830 against SI-3102",
                    "the remainder to SI-3104", "SI-3104 in full", "post SI-3102", "SI-3102 matched",
                    # an amount beside an id, in any punctuation or through one connecting word
                    "Customer payment SI-3102 1830.00 SI-3104 300.00",
                    "Customer payment, SI-3102: 1830.00; SI-3104: 300.00",
                    "SI-3102 (1830.00) and SI-3104 (1890.00)", "1830.00 for SI-3102", "1,830.00 SI-3102",
                    "credit SI-3102 with 1830.00", "SI-3102 - 1830.00", "SI-3102 = 1830.00", "SI-3102 1830",
                    "$1,830 SI-3102", "SI-3102 at 1830.00", "Customer payment SI-3102 1830.00.",
                    # a sequence over invoices
                    "Customer payment, SI-3102 then SI-3104", "SI-3102 first, then SI-3104", "SI-3104 first",
                    "SI-3104 before SI-3102", "SI-3102, followed by SI-3104", "Customer payment, then SI-3104",
                    # a verb of settlement
                    "settle SI-3102", "pay SI-3102", "clear SI-3102", "credited SI-3102",
                    "SI-3102 paid in full", "SI-3102 settled")
    for text in instructions:
        found = narration_problems(text, all_tied, notes, "t")
        if not any("application instruction" in p for p in found):
            problems.append(f"{text!r} not refused as an instruction: {found}")
    for text, why in (("Customer payment for SI-3100", "no public document ties"),
                      ("after application of CN-9999", "not a credit note")):
        if not any(why in p for p in narration_problems(text, tied, notes, "t")):
            problems.append(f"{text!r} allowed")
    # through the world gate: an instruction in R3's memo fails Case 1 with gate (n)
    module, world, task, *_ = case(1)
    for memo in ("Customer payment; apply 1830.00 to SI-3102 and 1890.00 to SI-3104",
                 "Customer payment, apply to SI-3102 then SI-3104"):
        r3 = dataclasses.replace(module.R3, memo=memo)
        bad = B.world("bowline-2026-04-c1", B.april_events(B.r1(), module.CN_0412, r3))
        found, _ = check_world_task(bad, task)
        if not any("gate (n)" in p and "application instruction" in p for p in found):
            problems.append(f"an instruction in the receipt narration passed the world gate: {memo!r} {found[:2]}")
    r3 = dataclasses.replace(module.R3, memo="Customer payment for SI-3100")
    bad = B.world("bowline-2026-04-c1", B.april_events(B.r1(), module.CN_0412, r3))
    found, _ = check_world_task(bad, task)
    if not any("gate (n)" in p and "SI-3100" in p for p in found):
        problems.append(f"an untied invoice in the receipt narration passed the world gate: {found[:2]}")
    lines = module.R3.lines[:1] + (dataclasses.replace(module.R3.lines[1], note="post 1890.00 to SI-3104"),)
    r3 = dataclasses.replace(module.R3, lines=lines)
    bad = B.world("bowline-2026-04-c1", B.april_events(B.r1(), module.CN_0412, r3))
    found, _ = check_world_task(bad, task)
    if not any("gate (n)" in p and "advice note" in p for p in found):
        problems.append(f"an instruction in an advice note passed the world gate: {found[:2]}")
    # `tied` is what the PUBLIC documents tie: a receipt with no advice ties
    # nothing beyond its statement reference, whatever the authored lines
    # say. Case 2's R3 re-referenced to a pay-run number, its lines exactly
    # what rung (3) reaches (SI-3100 300.00, SI-3102 1,830.00), so gate (m)
    # passes — and its narration naming SI-3102 is refused all the same.
    module2, _, task2, *_ = case(2)
    r3 = dataclasses.replace(module2.R3, bank_reference="GR PAYRUN 0428", memo="Customer payment for SI-3102",
                             lines=(S.ReceiptLine("doc:si-3100", D("300.00"), True),
                                    S.ReceiptLine("doc:si-3102", D("1830.00"), False)))
    unadviced = B.world("bowline-2026-04-c2", B.april_events(B.r1(), module2.CN_0412, r3))
    found, _ = check_world_task(unadviced, task2)
    if any("gate (m)" in p for p in found):
        problems.append(f"rung (3) does not reach the re-referenced R3; the fixture is wrong: {found[:2]}")
    if not any("gate (n)" in p and "SI-3102" in p and "no public document ties" in p for p in found):
        problems.append(f"an invoice only the authored lines of an advice-less receipt name passed the world "
                        f"gate: {found[:3]}")
    # the same receipt with the reference naming the invoice is allowed
    r3 = dataclasses.replace(r3, bank_reference="SI-3102 SI-3100")
    referenced = B.world("bowline-2026-04-c2", B.april_events(B.r1(), module2.CN_0412, r3))
    found, _ = check_world_task(referenced, task2)
    if any("gate (n)" in p for p in found):
        problems.append(f"a narration naming an invoice the statement reference quotes was refused: {found[:2]}")
    # Case 2's reference ties both invoices, so only the instruction clause
    # can refuse a memo there: the rung-(2) split written beside the ids, or
    # the order between them, is the answer the case exists to withhold
    for memo in ("Customer payment SI-3102 1830.00 SI-3104 300.00",
                 "Customer payment, SI-3102: 1830.00; SI-3104: 300.00",
                 "Customer payment, SI-3102 then SI-3104"):
        r3 = dataclasses.replace(module2.R3, memo=memo)
        split = B.world("bowline-2026-04-c2", B.april_events(B.r1(), module2.CN_0412, r3))
        found, _ = check_world_task(split, task2)
        if any("gate (m)" in p for p in found):
            problems.append(f"the memo alone moved gate (m); the fixture is wrong: {found[:2]}")
        if not any("gate (n)" in p and "application instruction" in p for p in found):
            problems.append(f"an id-adjacent split or a sequence in Case 2's memo passed the world gate: {memo!r} "
                            f"{found[:2]}")
    return check("gate (n): a genuine payment reference, the credit-note note and the write-off narration are "
                 "allowed; an application instruction with or without an amount, an untied invoice and an "
                 "invented credit note are refused in narrations and advice notes, the world gate names them, "
                 "and an advice-less receipt's authored lines tie nothing", not problems, "\n".join(problems))


def test_u12_warnings_are_warnings_not_gates():
    """Spec section 5, U12: a deduction of exactly 25.00 and an advice line
    on a zero-balance invoice are WARN, not refusals, and section 7 has
    25.00 "written off with the U12 warning". A world at the spec's own
    boundary passes every world gate and carries the warning; the truth
    writes the 25.00 off and closes where Case 3 closes."""
    problems = []
    module, _, task, *_ = case(3)
    # Case 3 with SI-3104's deduction at the tolerance: R3 3,655.00
    lines = (module.R3.lines[0], dataclasses.replace(module.R3.lines[1], amount=D("1865.00"), deduction=D("25.00")))
    r3 = dataclasses.replace(module.R3, amount=D("3655.00"), lines=lines)
    boundary = B.world("bowline-2026-04-c3", B.april_events(B.r1(), module.CN_0412, r3))
    found, warnings = check_world_task(boundary, task)
    if found:
        problems.append(f"the 25.00 boundary world does not pass verify_world: {found[:3]}")
    if not any(w.startswith("WARN:") and "WARN_DEDUCTION_AT_TOLERANCE" in w for w in warnings):
        problems.append(f"no U12 warning for the deduction of exactly 25.00: {warnings}")
    _, inputs = derive_contract(boundary, task)
    r3_truth = inputs.application.receipt("2026-04-28:GR PAYRUN 0428")
    if r3_truth[5] != (("SI-3104", D("25.00")),) or inputs.application.closing_ar != D("3310.00"):
        problems.append(f"the truth does not write 25.00 off: {r3_truth[5]}, closing {inputs.application.closing_ar}")
    public = {k: v.decode("utf-8") if isinstance(v, bytes) else v for k, v in inputs.public_files}
    app = CA.fold(public, **kw(task))
    if app.receipt("2026-04-28:GR PAYRUN 0428").written_off != (("SI-3104", D("25.00")),):
        problems.append(f"the public fold does not write 25.00 off: {app.receipt('2026-04-28:GR PAYRUN 0428')}")
    # a zero-cash line on an invoice R1 already closed: informational, warned, moves nothing
    module1, _, task1, *_ = case(1)
    lines = module1.R3.lines + (S.ReceiptLine("doc:si-3101", D("0.00"), False, D("0.00"), "settled on the 10 April run"),)
    r3 = dataclasses.replace(module1.R3, lines=lines)
    zero = B.world("bowline-2026-04-c1", B.april_events(B.r1(), module1.CN_0412, r3))
    found, warnings = check_world_task(zero, task1)
    if found:
        problems.append(f"the zero-balance line world fails a world gate: {found[:3]}")
    if not any(w.startswith("WARN:") and "WARN_LINE_ON_ZERO_BALANCE" in w for w in warnings):
        problems.append(f"no U12 warning for the advice line on a zero-balance invoice: {warnings}")
    _, inputs = derive_contract(zero, task1)
    if inputs.application.application_key() != case(1)[4].application.application_key():
        problems.append("the informational zero line moved the truth")
    return check("U12 is WARN, not a gate: the 25.00 deduction and the zero-balance advice line pass every world "
                 "gate with a WARN: line, the truth and the public fold write the 25.00 off, and the zero line "
                 "moves nothing", not problems, "\n".join(problems))


def test_the_plants_are_the_spec_s():
    problems = []
    for n in range(1, 6):
        module, world, task, bundle, inputs, public = case(n)
        plants = {p.id: p for p in inputs.planted}
        if {p.id: p.kind for p in inputs.planted} != EXPECTED[n]["plants"]:
            problems.append(f"case {n}: plants {[(p.id, p.kind) for p in inputs.planted]}")
        r2 = plants["unrecorded_customer_check"]
        if r2.date != "2026-04-21" or r2.must_be_payee != (SHEARWATER,) \
                or dict(r2.required) != {BANK: "2970", AR: "-2970"}:
            problems.append(f"case {n}: the R2 plant is {r2.date} {r2.must_be_payee} {r2.required}")
        original = txns(inputs.original_text)
        golden = txns(inputs.golden_text)
        r3_entries = [t for t in original if t.date == "2026-04-28" and t.payee == GANNET
                      and any(p.account == BANK for p in t.postings)]
        if len(r3_entries) != 1 or D(next(p.amount for p in r3_entries[0].postings if p.account == BANK)) \
                != D(EXPECTED[n]["r3_found"]):
            problems.append(f"case {n}: R3 as found {[shape(t) for t in r3_entries]}, spec {EXPECTED[n]['r3_found']}")
        if any(t.date == "2026-04-21" or (t.payee == SHEARWATER and any(p.account == BANK for p in t.postings))
               for t in original):
            problems.append(f"case {n}: R2 is not absent from the opening ledger")
        if not any(t.date == "2026-04-21" and t.payee == SHEARWATER and dict(shape(t)) == {BANK: D("2970"), AR: D("-2970")}
                   for t in golden):
            problems.append(f"case {n}: the expected ledger does not carry R2 on the bank's date")
        write_offs_orig = [t for t in original if any(p.account == B.WRITE_OFFS for p in t.postings)]
        write_offs_gold = [t for t in golden if any(p.account == B.WRITE_OFFS for p in t.postings)]
        if n == 3:
            if write_offs_orig or len(write_offs_gold) != 1:
                problems.append(f"case 3: write-off entries original {len(write_offs_orig)} golden {len(write_offs_gold)}")
            elif WRITE_OFF_ENTRY_CASE_3 not in inputs.golden_text \
                    or dict(shape(write_offs_gold[0])) != {B.WRITE_OFFS: D("20"), AR: D("-20")}:
                problems.append(f"case 3: the write-off entry is {WRITE_OFF_ENTRY_CASE_3!r} in the spec; got "
                                f"{write_offs_gold[0].narration!r} {shape(write_offs_gold[0])}")
            p = plants["omitted_short_payment_write_off"]
            if p.date != "2026-04-28" or dict(p.required) != {B.WRITE_OFFS: "20", AR: "-20"} \
                    or p.must_be_payee != (GANNET,) or p.recognition_id != "rec:gr-payrun-0428-writeoff":
                problems.append(f"case 3: the write-off plant is {p}")
        elif n == 4:
            if len(write_offs_orig) != 1 or len(write_offs_gold) != 1 \
                    or dict(shape(write_offs_orig[0])) != {B.WRITE_OFFS: D("10"), AR: D("-10")} \
                    or "SI-3102" not in write_offs_orig[0].narration:
                problems.append(f"case 4: the 10.00 write-off is not booked as found: {[shape(t) for t in write_offs_orig]}")
        elif write_offs_orig or write_offs_gold:
            problems.append(f"case {n}: a write-off entry where the spec has none")
        alter = plants.get("transposed_payrun_receipt")
        if alter is not None:
            m = next(m for m in task.plan.mutations if m.mutation_id == alter.id)
            want_param = 2 if n == 1 else 1
            if m.strategy != "transpose_digits" or m.parameter != want_param:
                problems.append(f"case {n}: R3 is altered by {m.strategy}({m.parameter}), spec transpose_digits({want_param})")
            if D(dict(alter.replaces)[BANK]) != D(EXPECTED[n]["r3_found"]):
                problems.append(f"case {n}: the alteration replaces {alter.replaces}")
        if inputs.statement_closing != D(EXPECTED[n]["statement"]):
            problems.append(f"case {n}: statement closing {inputs.statement_closing}")
        # no as-found amount coincides with a balance or a face value of its case
        figures = {D(r[2]) for r in inputs.application.register} | {D(r[6]) for r in inputs.application.register} \
            | {d.gross for d in world.documents if d.gross is not None}
        if D(EXPECTED[n]["r3_found"]) in figures and n != 3:
            problems.append(f"case {n}: the as-found R3 coincides with a balance or face value")
    return check("the plants are the spec's: R2 omitted in every case on the bank's date 2026-04-21, R3 transposed "
                 "with transpose_digits(2) in Case 1 and (1) elsewhere to 3702 / 2310 / 3160 / 3870, booked correctly "
                 "in Case 3, the 20.00 write-off omitted alone in Case 3 with the spec's entry in the golden, the "
                 "10.00 write-off booked in Case 4, statement closings per case", not problems, "\n".join(problems))


def test_bank_date_posting_holds_independently_of_the_plant():
    problems = []
    module, world, task, *_ = case(1)
    clean = project(world, task.period, MutationPlan(()))
    ledger = clean.view("ledger.beancount").text
    if '2026-04-21 * "Shearwater Bay Charters LLC" "Customer check 2291"' not in ledger:
        problems.append("with nothing planted the ledger does not post R2 on the bank's date 2026-04-21")
    if "2026-04-16 *" in ledger:
        problems.append("the ledger posts something on the cheque's date")
    if "RA-0416-SB,Shearwater Bay Charters LLC,2026-04-16,CHECK,2291,2970.00" not in clean.view("remittance_advice.csv").text:
        problems.append("the advice does not preserve the cheque date as evidence")
    if clean.view("ledger.beancount").text != clean.view("expected_ledger").text:
        problems.append("with nothing planted the opening ledger is not the expected ledger")
    if clean.restated:
        problems.append(f"the family restates {clean.restated}; every receipt is already on the bank's date")
    _, _, _, bundle3, inputs3, _ = case(3)
    rec = bundle3.recognition("rec:gr-payrun-0428-writeoff")
    if rec.date != "2026-04-28" or rec.payee != GANNET or rec.sequence != 1 or rec.rule != "small_balance_write_offs":
        problems.append(f"the write-off recognition is {rec}")
    rec = bundle3.recognition("rec:sb-check-2291")
    if rec.date != "2026-04-21":
        problems.append(f"R2's recognition is dated {rec.date}, not the bank's date")
    return check("the bank-date posting rule holds with nothing planted: the cheque receipt posts on 2026-04-21, the "
                 "advice keeps 2026-04-16 as evidence, nothing is restated, and the write-off is a separate "
                 "recognition of the receipt's event on the receipt's date", not problems, "\n".join(problems))


def test_cheque_sign_and_movement_extensions():
    problems = []
    _, world, *_ = case(1)
    m = P.movement_of(world, B.R2)
    if m is None or m.amount != D("2970.00") or m.description != "CHECK 2291 SHEARWATER BAY CHARTERS LLC" \
            or m.reference != "2291" or m.cleared_on != "2026-04-21":
        problems.append(f"the cheque-settled applied receipt moves {m}")
    m = P.movement_of(world, CASH_APPLICATION_MODULES[0].R3)
    if m is None or m.amount != D("3720.00") or m.reference != "GR PAYRUN 0428" \
            or m.description != "ACH IN GANNET RIGGING INC":
        problems.append(f"the ACH applied receipt moves {m}")
    m = P.movement_of(world, CASH_APPLICATION_MODULES[1].R3)
    if m is None or m.reference != "TRC0428442 SI-3104 SI-3102":
        problems.append(f"Case 2's addendum prints as {m}")
    legacy = P.movement_of(world, B.MARCH_EVENTS[1])
    if legacy.amount != D("-2860.00"):
        problems.append("a vendor payment lost its outgoing sign")
    return check("the cheque-sign extension: an applied receipt by cheque is money in and names the remitter; an ACH "
                 "one prints its addendum verbatim; a vendor payment keeps the outgoing sign",
                 not problems, "\n".join(problems))


def test_receipt_validation_and_cumulative_checks():
    problems = []
    module, world, task, *_ = case(1)
    R3_ = module.R3

    def world_with(r3, r1=None):
        return B.world("bowline-2026-04-c1", B.april_events(r1 or B.r1(), module.CN_0412, r3))

    def refused(w, needle, label):
        found = S.check_world(w)
        if not any(needle in p for p in found):
            problems.append(f"{label}: check_world did not say {needle!r}: {found[:2]}")

    refused(world_with(dataclasses.replace(R3_, lines=(S.ReceiptLine("doc:si-3103", D("1830.00"), True),))),
            "belongs to another party", "a line on the other customer's invoice")
    refused(world_with(dataclasses.replace(R3_, lines=(S.ReceiptLine("doc:si-3102", D("1830.00"), False, D("5.00")),))),
            "without settling", "a deduction without a settlement")
    refused(world_with(dataclasses.replace(R3_, lines=(S.ReceiptLine("doc:si-3102", D("1830.00"), True),
                                                        S.ReceiptLine("doc:si-3104", D("1900.00"), True)))),
            "above the receipt", "lines above the payment")
    refused(world_with(dataclasses.replace(R3_, lines=(S.ReceiptLine("doc:si-3105", D("100.00")),))),
            "belongs to another party", "a line on the other customer's in-month invoice")
    early = dataclasses.replace(R3_, date="2026-04-06", settlement=B.ach_in("2026-04-06"))
    refused(world_with(early), "raised 2026-04-07, after", "a line on an invoice raised after the receipt")
    refused(world_with(dataclasses.replace(R3_, bank_reference="")), "bank reference", "an ACH receipt without an addendum")
    refused(world_with(dataclasses.replace(R3_, settlement=S.Settlement(S.Rail.CARD, "2026-04-28"))),
            "cannot arrive by card", "an applied receipt by card")
    # cumulative: two receipts' lines on one invoice above what it can absorb
    over = dataclasses.replace(R3_, lines=(S.ReceiptLine("doc:si-3101", D("100.00")), S.ReceiptLine("doc:si-3104", D("1890.00"))))
    w = world_with(over)
    bundle = project(w, task.period, MutationPlan(()))
    found = PJ.check_bundle(w, bundle)
    if not any("SI-3101" in p or "doc:si-3101" in p for p in found if "exceed" in p):
        problems.append(f"check_bundle did not refuse the cumulative over-application: {found[:3]}")
    try:
        derive_contract(w, task)
        problems.append("derive_contract accepted a receipt whose lines exceed the invoice's balance")
    except DerivationError:
        pass
    # the truth fold: a line above the open balance at its date, a settled line that does not close
    for lines, needle, label in (
            ((S.ReceiptLine("doc:si-3102", D("1900.00"), True), S.ReceiptLine("doc:si-3104", D("1820.00"), True)),
             "REFUSE_LINE_CONTRADICTS_REGISTER", "a line above the open balance at its date"),
            ((S.ReceiptLine("doc:si-3102", D("1800.00"), True), S.ReceiptLine("doc:si-3104", D("1890.00"), True)),
             "REFUSE_LINE_CONTRADICTS_REGISTER", "a settled line whose cash and deduction do not close the invoice")):
        w = world_with(dataclasses.replace(R3_, amount=D("3720.00"), lines=lines))
        try:
            derive_contract(w, dataclasses.replace(task, plan=MutationPlan(())))
            problems.append(f"{label}: derivation accepted it")
        except DerivationError as exc:
            if needle not in str(exc):
                problems.append(f"{label}: refused as {str(exc)[:160]}")
        except Exception as exc:
            problems.append(f"{label}: {type(exc).__name__}: {str(exc)[:160]}")
    # a line on an invoice the credit note closed at its date (Case 5's SI-3100:
    # under its face value, so only the dated fold can see that it is closed)
    m5 = CASH_APPLICATION_MODULES[4]
    r3 = dataclasses.replace(m5.R3, amount=D("3880.00"),
                             lines=(S.ReceiptLine("doc:si-3100", D("100.00"), False),) + m5.R3.lines)
    w = B.world("bowline-2026-04-c5", B.april_events(B.r1(), m5.CN_0412, r3))
    try:
        derive_contract(w, dataclasses.replace(task, plan=MutationPlan(())))
        problems.append("a line on an invoice the credit note closed was accepted")
    except DerivationError as exc:
        if "REFUSE_FOREIGN_OR_UNKNOWN_INVOICE" not in str(exc) or "already closed" not in str(exc):
            problems.append(f"a line on a closed invoice: refused as {str(exc)[:160]}")
    # an in-period single-invoice CustomerReceipt is refused in a family world
    stray = S.CustomerReceipt("event:stray", "2026-04-22", B.GANNET, "doc:si-3104", D("100.00"),
                              B.ach_in("2026-04-22"), "Customer payment for SI-3104")
    w = B.world("bowline-2026-04-c1", B.april_events(B.r1(), module.CN_0412, R3_) + (stray,))
    try:
        derive_contract(w, dataclasses.replace(task, plan=MutationPlan(())))
        problems.append("a single-invoice CustomerReceipt in the period was accepted in a family world")
    except DerivationError:
        pass
    # the credit note against a paid invoice routes as excess, not a refusal
    cn = dataclasses.replace(module.CN_0412, invoice_id="doc:si-3101")
    w = B.world("bowline-2026-04-c1", B.april_events(B.r1(), cn, dataclasses.replace(
        R3_, amount=D("3990.00"), lines=(S.ReceiptLine("doc:si-3102", D("2100.00"), True),
                                         S.ReceiptLine("doc:si-3104", D("1890.00"), True)))))
    try:
        _, inputs = derive_contract(w, dataclasses.replace(task, plan=MutationPlan(())))
        credit = inputs.application.credit_notes[0]
        # SI-3101 takes none of it; the excess goes to Gannet's oldest other
        # open invoice by (invoice_date, invoice_id): SI-3100 (open 300.00)
        if credit[4] != pairs(("SI-3100", "270.00")) or credit[5] != 0:
            problems.append(f"a credit note against a paid invoice applied {credit[4]} unapplied {credit[5]}")
    except Exception as exc:
        problems.append(f"a credit note against a paid invoice was refused: {str(exc)[:200]}")
    return check("receipt validation: check_world refuses a foreign, not-yet-raised or card-settled line, a "
                 "deduction without a settlement, lines above the payment and an ACH receipt without an addendum; "
                 "check_bundle refuses cumulative over-application; the truth fold refuses a line above the open "
                 "balance, a settled line that does not close, a line on a closed invoice and a stray single-invoice "
                 "receipt; a credit against a paid invoice routes as excess", not problems, "\n".join(problems))


def test_the_write_off_rule_and_the_optional_role():
    problems = []
    module, world, task, *_ = case(3)
    R3_ = module.R3

    def offs(deduction, settles=True):
        r = dataclasses.replace(R3_, lines=(S.ReceiptLine("doc:si-3102", D("1830.00"), True),
                                            S.ReceiptLine("doc:si-3104", D("1890.00") - deduction, settles, deduction)))
        return P.write_offs_of(r)

    for deduction, want in ((D("24.99"), (("doc:si-3104", D("24.99")),)), (D("25.00"), (("doc:si-3104", D("25.00")),)),
                            (D("25.01"), ()), (D("0.00"), ())):
        if offs(deduction) != want:
            problems.append(f"deduction {deduction}: write-offs {offs(deduction)}, want {want}")
    if offs(D("10.00"), settles=False) != ():
        problems.append("an unsettled line's deduction was written off")
    # combined lines for one invoice on one receipt
    r = dataclasses.replace(R3_, lines=(S.ReceiptLine("doc:si-3104", D("1000.00"), False, D("0.00")),
                                        S.ReceiptLine("doc:si-3104", D("870.00"), True, D("20.00"))))
    if P.write_offs_of(r) != (("doc:si-3104", D("20.00")),):
        problems.append(f"combined lines: {P.write_offs_of(r)}")
    roles = P.Roles(**dict(world.roles))
    recs = P.recognitions_of(world, roles, R3_)
    if [r.id for r in recs] != ["rec:gr-payrun-0428", "rec:gr-payrun-0428-writeoff"]:
        problems.append(f"Case 3's R3 recognises {[r.id for r in recs]}")
    else:
        wo = recs[1]
        if wo.narration != "Short payment on SI-3104 written off under the cash application policy" \
                or tuple((l.account, l.amount) for l in wo.legs) != ((B.WRITE_OFFS, D("20.00")), (AR, D("-20.00"))) \
                or wo.date != "2026-04-28" or wo.payee != GANNET:
            problems.append(f"the write-off recognition is {wo}")
        receipt = recs[0]
        if tuple((l.account, l.amount) for l in receipt.legs) != ((BANK, D("3660.00")), (AR, D("-3660.00"))) \
                or receipt.rule != "customer_receipt":
            problems.append(f"the receipt recognition is {receipt}")
    if len(P.recognitions_of(world, roles, CASH_APPLICATION_MODULES[0].R3)) != 1:
        problems.append("Case 1's R3 recognises a write-off")
    if "small_balance_write_offs" not in P.ROLES or P.OPTIONAL_ROLES != ("small_balance_write_offs",):
        problems.append(f"ROLES {P.ROLES} OPTIONAL_ROLES {P.OPTIONAL_ROLES}")
    # the role is required only of a world whose advice lines claim a deduction
    without = tuple(pair for pair in world.roles if pair[0] != "small_balance_write_offs")
    w1 = dataclasses.replace(CASH_APPLICATION_MODULES[0].WORLD, roles=without)
    if S.check_world(w1):
        problems.append(f"Case 1's world without the role is refused: {S.check_world(w1)[:2]}")
    w3 = dataclasses.replace(world, roles=without)
    if not any("small_balance_write_offs" in p for p in S.check_world(w3)):
        problems.append("Case 3's world without the role passed check_world")
    try:
        P.recognitions_of(world, P.Roles(**dict(without)), R3_)
        problems.append("the policy wrote off to an undeclared role")
    except TypeError:
        pass
    if P.SHORT_PAY_TOLERANCE != CA.SHORT_PAY_TOLERANCE != D("25.00"):
        problems.append("the tolerance differs between the policy and the public fold")
    return check("the write-off rule: 24.99 and 25.00 written off, 25.01 and an unsettled claim not, lines combined "
                 "per invoice per receipt; Case 3's R3 yields the receipt and the spec's separate write-off entry; "
                 "the role is required only where a deduction is claimed", not problems, "\n".join(problems))


def test_roles_and_digests_of_the_shipped_worlds():
    problems = []
    fixture = json.loads(FREEZE.read_text(encoding="utf-8"))
    by_world = {}
    for task_id, row_ in fixture["tasks"].items():
        by_world.setdefault(row_["world_id"], set()).add(row_["graph_digest"])
    for module in WORLD_MODULES:
        world = module.WORLD
        digest = domain_digest(PJ.GRAPH_DOMAIN, canonical_bytes({"schema_version": S.GRAPH_SCHEMA_VERSION,
                                                                  "world": S.world_canonical(world)}))
        if by_world.get(world.id) != {digest}:
            problems.append(f"{world.id}: graph digest {digest[:12]} is not the frozen {by_world.get(world.id)}")
        if P.is_cash_application_world(world) or len(world.roles) != 9:
            problems.append(f"{world.id}: read as a family world, or declares {len(world.roles)} roles")
        task = next(iter(module.TASKS.values()))
        bundle, inputs = derive_contract(world, task)
        if sorted(bundle.public_files()) != sorted(LEGACY_FILES) or inputs.application is not None \
                or "application" in inputs.contract_view():
            problems.append(f"{world.id}: projects {sorted(bundle.public_files())} / application {inputs.application}")
        if sorted(P.required_sections(world)) != sorted(P.LEGACY_RULES):
            problems.append(f"{world.id}: required sections {sorted(P.required_sections(world))}")
    _, world1, task1, bundle1, inputs1, _ = case(1)
    dropped = dataclasses.replace(world1, roles=tuple(p for p in world1.roles if p[0] != "small_balance_write_offs"))
    if project(dropped, task1.period, task1.plan).graph_digest == bundle1.graph_digest:
        problems.append("dropping a role pair leaves the graph digest unchanged")
    if "application" not in inputs1.contract_view() or inputs1.contract_view()["application"]["schema"] != DV.APPLICATION_TRUTH_SCHEMA:
        problems.append("the family's contract view carries no application block")
    if sorted(P.required_sections(world1)) != sorted(P.LEGACY_RULES + ("small_balance_write_offs", "credit_note")):
        problems.append(f"the family's required sections are {sorted(P.required_sections(world1))}")
    return check("the ten shipped worlds keep their frozen graph digests, nine roles, eight public files, no "
                 "application block and the legacy sections; dropping the write-off role pair from a family world "
                 "moves its digest; the family's contract view carries the truth register",
                 not problems, "\n".join(problems))


def test_gate_o_on_the_actual_bytes():
    problems = []
    for n in range(1, 6):
        _, _, task, _, _, public = case(n)
        report = CA.baseline_report(public, **kw(task))
        reached = CA.refused_by(report)
        if reached:
            problems.append(f"case {n}: reached by {reached}")
        print(f"      case {n}: " + ", ".join(
            f"{name}={'-' if r.reaches_truth is None else ('REACHES' if r.reaches_truth else 'no')}"
            for name, r in report.items()))
    return check("gate (o) over the projected bytes: no admitted baseline reaches any of the five cases",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# the three variant packs of 2026-09: six variants, three matched pairs
#
# `v10-codex/six_variant_packs.md`, corrected after the accounting review of
# 2026-09-11, is the specification; the tables below are its section 3 / 2 /
# "the correct application" transcribed, and the gates the five Bowline
# cases pass above are re-run over the six here rather than in a parallel
# suite.
# --------------------------------------------------------------------------

MARROWBONE, PINEFALL = "Marrowbone Construction Group", "Pinefall Hospitality Partners"
MARCHMONT, CORVID, ASHGROVE = ("Marchmont Grocers Co-operative", "Corvid Coffee Houses LLC",
                               "Ashgrove Halt Refreshments Ltd")
QUILLHAVEN, BROADMARSH, PELLOW = ("Quillhaven Publishing House", "Broadmarsh Academy Trust",
                                  "Pellow & Dunge Stationers")

#: task id -> (module, world, pair label, variant letter)
VARIANT_MODULE = {task_id: (module, module.WORLD_BY_TASK[task_id])
                  for module in CASH_APPLICATION_PAIR_MODULES for task_id in module.TASKS}
PAIR_IDS = (("cash_application_006", "cash_application_007"),
            ("cash_application_008", "cash_application_009"),
            ("cash_application_010", "cash_application_011"))
VARIANT_IDS = tuple(task_id for pair in PAIR_IDS for task_id in pair)

_VARIANTS: dict = {}


def variant(task_id: str):
    """(module, world, task, bundle, inputs, public) for one variant."""
    if task_id not in _VARIANTS:
        module, world = VARIANT_MODULE[task_id]
        task = module.TASKS[task_id]
        bundle, inputs = derive_contract(world, task)
        public = {name: data.decode("utf-8") for name, data in inputs.public_files}
        _VARIANTS[task_id] = (module, world, task, bundle, inputs, public)
    return _VARIANTS[task_id]


THORNBURY_R = ("2026-06-08:MCG REMIT 0605", "2026-06-17:TRC0617318 SI-4383 SI-4390 SI-4377",
               "2026-06-25:TRC0625704 SI-4402 SI-4408 SI-4396")
PENNY_R = ("2026-06-10:MG PAYRUN 0610", "2026-06-15:6153", "2026-06-26:CC ACH 0626")
TALLOW_R = ("2026-07-09:QPH SETTLEMENT 0709", "2026-07-20:4417", "2026-07-22:BAT REMIT 0722",
            "2026-07-24:PDS PAYRUN 0724", "2026-07-29:QPH SETTLEMENT 0729")


def _register(*rows):
    return tuple(sorted(row(*r) for r in rows))


THORNBURY_BASE = (
    ("SI-4377", PINEFALL, "6890.00", "6890.00", "0.00", "0.00", "0.00"),
    ("SI-4383", PINEFALL, "5300.00", "2650.00", "0.00", "0.00", "2650.00"),
    ("SI-4386", PINEFALL, "4240.00", "0.00", "0.00", "0.00", "4240.00"),
    ("SI-4390", PINEFALL, "8480.00", "8480.00", "0.00", "0.00", "0.00"),
    ("SI-4396", MARROWBONE, "12720.00", "12720.00", "0.00", "0.00", "0.00"),
    ("SI-4408", MARROWBONE, "9540.00", "8268.00", "1272.00", "0.00", "0.00"),
    ("SI-4415", MARROWBONE, "6360.00", "0.00", "0.00", "0.00", "6360.00"),
    ("SI-4419", PINEFALL, "10600.00", "0.00", "0.00", "0.00", "10600.00"),
)
PENNY_REGISTER = _register(
    ("SI-5188", MARCHMONT, "1260.00", "0.00", "1260.00", "0.00", "0.00"),
    ("SI-5196", CORVID, "5250.00", "5250.00", "0.00", "0.00", "0.00"),
    ("SI-5203", MARCHMONT, "3780.00", "3780.00", "0.00", "0.00", "0.00"),
    ("SI-5211", ASHGROVE, "1995.00", "0.00", "0.00", "0.00", "1995.00"),
    ("SI-5219", MARCHMONT, "2940.00", "1260.00", "1680.00", "0.00", "0.00"),
    ("SI-5227", CORVID, "3150.00", "0.00", "0.00", "0.00", "3150.00"),
    ("SI-5236", CORVID, "4200.00", "2100.00", "0.00", "0.00", "2100.00"),
    ("SI-5244", MARCHMONT, "2625.00", "0.00", "0.00", "0.00", "2625.00"),
)
TALLOW_BASE = (
    ("SI-7218", QUILLHAVEN, "1620.00", "0.00", "0.00", "0.00", "1620.00"),
    ("SI-7222", BROADMARSH, "3780.00", "3150.00", "630.00", "0.00", "0.00"),
    ("SI-7226", QUILLHAVEN, "5250.00", "5250.00", "0.00", "0.00", "0.00"),
    ("SI-7229", BROADMARSH, "4410.00", "4395.00", "0.00", "15.00", "0.00"),
    ("SI-7231", QUILLHAVEN, "7920.00", "7920.00", "0.00", "0.00", "0.00"),
    ("SI-7234", PELLOW, "2835.00", "2745.00", "0.00", "0.00", "90.00"),
    ("SI-7242", PELLOW, "3360.00", "0.00", "0.00", "0.00", "3360.00"),
)
PENNY_CREDIT = pairs(("SI-5219", "1680.00"), ("SI-5188", "1260.00"))

#: Per variant: the receipts, the credit note, the closing register, the
#: closing `Assets:AR`, the opening `Assets:AR`, the statement's close and
#: the `Expenses:SmallBalanceWriteOffs` MOVEMENT (which equals its closing
#: balance, because the account opens at zero in all three months).
PACK = {
    "cash_application_006": dict(
        receipts={THORNBURY_R[0]: (pairs(("SI-4371", "5100.00"), ("SI-4396", "4440.00")), (), "0.00"),
                  THORNBURY_R[1]: (pairs(("SI-4390", "8480.00"), ("SI-4377", "6890.00"),
                                         ("SI-4383", "2650.00")), (), "0.00"),
                  THORNBURY_R[2]: (pairs(("SI-4408", "8268.00"), ("SI-4396", "8280.00"), ("SI-4402", "7420.00"),
                                         ("SI-4371", "2900.00")), (), "0.00")},
        credits={"CN-0609": (pairs(("SI-4408", "1272.00")), D("0.00"))},
        register=_register(*THORNBURY_BASE,
                           ("SI-4371", MARROWBONE, "9300.00", "8000.00", "0.00", "0.00", "1300.00"),
                           ("SI-4402", MARROWBONE, "7420.00", "7420.00", "0.00", "0.00", "0.00")),
        opening="63890.00", closing="25150.00", statement="170103.00", written_off="0.00"),
    "cash_application_007": dict(
        receipts={THORNBURY_R[0]: (pairs(("SI-4371", "5100.00"), ("SI-4396", "4440.00")), (), "0.00"),
                  THORNBURY_R[1]: (pairs(("SI-4390", "8480.00"), ("SI-4377", "6890.00"),
                                         ("SI-4383", "2650.00")), (), "0.00"),
                  THORNBURY_R[2]: (pairs(("SI-4408", "8268.00"), ("SI-4396", "8280.00"),
                                         ("SI-4402", "4452.00")), (), "0.00")},
        credits={"CN-0609": (pairs(("SI-4408", "1272.00")), D("0.00"))},
        register=_register(*THORNBURY_BASE,
                           ("SI-4371", MARROWBONE, "9300.00", "5100.00", "0.00", "0.00", "4200.00"),
                           ("SI-4402", MARROWBONE, "7420.00", "4452.00", "0.00", "0.00", "2968.00")),
        opening="63890.00", closing="31018.00", statement="164235.00", written_off="0.00"),
    "cash_application_008": dict(
        receipts={PENNY_R[0]: (pairs(("SI-5203", "3780.00"), ("SI-5219", "1260.00")), (), "0.00"),
                  PENNY_R[1]: (pairs(("SI-5196", "5250.00")), (), "0.00"),
                  PENNY_R[2]: (pairs(("SI-5236", "2100.00")), (), "0.00")},
        credits={"CN-0618": (PENNY_CREDIT, D("210.00"))},
        register=PENNY_REGISTER,
        opening="18375.00", closing="9660.00", statement="44807.00", written_off="0.00"),
    "cash_application_009": dict(
        receipts={PENNY_R[0]: (pairs(("SI-5203", "3780.00"), ("SI-5219", "1260.00")), (), "0.00"),
                  PENNY_R[1]: (pairs(("SI-5196", "5250.00")), (), "0.00"),
                  PENNY_R[2]: (pairs(("SI-5236", "2100.00")), (), "0.00")},
        credits={"CN-0618": (PENNY_CREDIT, D("0.00"))},
        register=PENNY_REGISTER,
        opening="18375.00", closing="9870.00", statement="44807.00", written_off="0.00"),
    "cash_application_010": dict(
        receipts={TALLOW_R[0]: (pairs(("SI-7231", "7920.00"), ("SI-7226", "1620.00")), (), "0.00"),
                  TALLOW_R[1]: (pairs(("SI-7222", "3150.00")), (), "0.00"),
                  TALLOW_R[2]: (pairs(("SI-7229", "4395.00")), pairs(("SI-7229", "15.00")), "0.00"),
                  TALLOW_R[3]: (pairs(("SI-7234", "2745.00")), (), "0.00"),
                  TALLOW_R[4]: (pairs(("SI-7226", "3630.00"), ("SI-7239", "4020.00")), (), "540.00")},
        credits={"CN-0714": (pairs(("SI-7222", "630.00")), D("0.00"))},
        register=_register(*TALLOW_BASE,
                           ("SI-7239", QUILLHAVEN, "4620.00", "4020.00", "0.00", "0.00", "600.00")),
        opening="25815.00", closing="5130.00", statement="116368.00", written_off="15.00"),
    "cash_application_011": dict(
        receipts={TALLOW_R[0]: (pairs(("SI-7231", "7920.00"), ("SI-7226", "1620.00")), (), "0.00"),
                  TALLOW_R[1]: (pairs(("SI-7222", "3150.00")), (), "0.00"),
                  TALLOW_R[2]: (pairs(("SI-7229", "4395.00")), pairs(("SI-7229", "15.00")), "0.00"),
                  TALLOW_R[3]: (pairs(("SI-7234", "2745.00")), (), "0.00"),
                  TALLOW_R[4]: (pairs(("SI-7226", "3630.00"), ("SI-7239", "4560.00")), (), "0.00")},
        credits={"CN-0714": (pairs(("SI-7222", "630.00")), D("0.00"))},
        register=_register(*TALLOW_BASE,
                           ("SI-7239", QUILLHAVEN, "4620.00", "4560.00", "0.00", "0.00", "60.00")),
        opening="25815.00", closing="5130.00", statement="116368.00", written_off="0.00"),
}
#: variant B of the advice-residue pair still writes off SI-7229's 15.00 —
#: only R5's residue moves — so its write-off movement is 15.00 too.
PACK["cash_application_011"]["written_off"] = "15.00"

#: What a pair is allowed to differ in, as the pack states it: the FILES,
#: and for the one-cell pairs the number of differing lines.
PAIR_DIFFERS = {
    ("cash_application_006", "cash_application_007"): {"bank_statement.csv": 2, "ledger.beancount": 2},
    ("cash_application_008", "cash_application_009"): {"credit_notes.csv": 1, "ledger.beancount": 3},
    ("cash_application_010", "cash_application_011"): {"remittance_advice.csv": 1},
}


#: `six_variant_packs.md`'s three EVIDENCE files per variant, byte for byte,
#: and the three manifest rows that count them. The document is the
#: specification and lives outside the wheel, so the bytes it renders are
#: pinned HERE: a projector change that moved one of them would otherwise be
#: invisible to the battery and visible only to a scratch run.
PACK_FAMILY_FILES = {
    "cash_application_006": {
        "open_items.csv": """invoice_id,customer,invoice_date,due_date,original_amount,open_balance
SI-4386,Pinefall Hospitality Partners,2026-03-24,2026-05-08,4240.00,4240.00
SI-4371,Marrowbone Construction Group,2026-03-30,2026-04-29,18550.00,9300.00
SI-4390,Pinefall Hospitality Partners,2026-04-03,2026-05-18,8480.00,8480.00
SI-4377,Pinefall Hospitality Partners,2026-04-14,2026-05-29,6890.00,6890.00
SI-4408,Marrowbone Construction Group,2026-04-22,2026-05-22,9540.00,9540.00
SI-4383,Pinefall Hospitality Partners,2026-04-28,2026-06-12,5300.00,5300.00
SI-4396,Marrowbone Construction Group,2026-05-06,2026-06-05,12720.00,12720.00
SI-4402,Marrowbone Construction Group,2026-05-19,2026-06-18,7420.00,7420.00
""",
        "remittance_advice.csv": """remittance_id,customer,remittance_date,payment_method,payment_reference,payment_amount,invoice_id,amount_paid,settles_invoice,deduction_amount,note
RA-0605-MCG,Marrowbone Construction Group,2026-06-05,ACH,MCG REMIT 0605,9540.00,SI-4371,5100.00,no,0.00,Partial payment of the invoiced work; the remaining balance is outstanding and is not subject to retention or a completion condition.
RA-0605-MCG,Marrowbone Construction Group,2026-06-05,ACH,MCG REMIT 0605,9540.00,SI-4396,4440.00,no,0.00,part payment on account; balance to follow on the next payment run
RA-0605-MCG,Marrowbone Construction Group,2026-06-05,ACH,MCG REMIT 0605,9540.00,SI-4402,0.00,no,0.00,withheld; site access charge disputed
""",
        "credit_notes.csv": """credit_note_id,date,customer,invoice_id,net_amount,tax_amount,gross_amount,reason
CN-0609,2026-06-09,Marrowbone Construction Group,SI-4408,1200.00,72.00,1272.00,Agreed price allowance for site-damaged glazing retained by the customer; no return or replacement goods.
""",
    },
    "cash_application_007": {
        "open_items.csv": """invoice_id,customer,invoice_date,due_date,original_amount,open_balance
SI-4386,Pinefall Hospitality Partners,2026-03-24,2026-05-08,4240.00,4240.00
SI-4371,Marrowbone Construction Group,2026-03-30,2026-04-29,18550.00,9300.00
SI-4390,Pinefall Hospitality Partners,2026-04-03,2026-05-18,8480.00,8480.00
SI-4377,Pinefall Hospitality Partners,2026-04-14,2026-05-29,6890.00,6890.00
SI-4408,Marrowbone Construction Group,2026-04-22,2026-05-22,9540.00,9540.00
SI-4383,Pinefall Hospitality Partners,2026-04-28,2026-06-12,5300.00,5300.00
SI-4396,Marrowbone Construction Group,2026-05-06,2026-06-05,12720.00,12720.00
SI-4402,Marrowbone Construction Group,2026-05-19,2026-06-18,7420.00,7420.00
""",
        "remittance_advice.csv": """remittance_id,customer,remittance_date,payment_method,payment_reference,payment_amount,invoice_id,amount_paid,settles_invoice,deduction_amount,note
RA-0605-MCG,Marrowbone Construction Group,2026-06-05,ACH,MCG REMIT 0605,9540.00,SI-4371,5100.00,no,0.00,Partial payment of the invoiced work; the remaining balance is outstanding and is not subject to retention or a completion condition.
RA-0605-MCG,Marrowbone Construction Group,2026-06-05,ACH,MCG REMIT 0605,9540.00,SI-4396,4440.00,no,0.00,part payment on account; balance to follow on the next payment run
RA-0605-MCG,Marrowbone Construction Group,2026-06-05,ACH,MCG REMIT 0605,9540.00,SI-4402,0.00,no,0.00,withheld; site access charge disputed
""",
        "credit_notes.csv": """credit_note_id,date,customer,invoice_id,net_amount,tax_amount,gross_amount,reason
CN-0609,2026-06-09,Marrowbone Construction Group,SI-4408,1200.00,72.00,1272.00,Agreed price allowance for site-damaged glazing retained by the customer; no return or replacement goods.
""",
    },
    "cash_application_008": {
        "open_items.csv": """invoice_id,customer,invoice_date,due_date,original_amount,open_balance
SI-5188,Marchmont Grocers Co-operative,2026-04-22,2026-06-06,4410.00,1260.00
SI-5196,Corvid Coffee Houses LLC,2026-04-29,2026-05-29,5250.00,5250.00
SI-5203,Marchmont Grocers Co-operative,2026-05-06,2026-06-20,3780.00,3780.00
SI-5211,Ashgrove Halt Refreshments Ltd,2026-05-12,2026-06-11,1995.00,1995.00
SI-5219,Marchmont Grocers Co-operative,2026-05-19,2026-07-03,4200.00,2940.00
SI-5227,Corvid Coffee Houses LLC,2026-05-26,2026-06-25,3150.00,3150.00
""",
        "remittance_advice.csv": """remittance_id,customer,remittance_date,payment_method,payment_reference,payment_amount,invoice_id,amount_paid,settles_invoice,deduction_amount,note
RA-0610-MG,Marchmont Grocers Co-operative,2026-06-10,ACH,MG PAYRUN 0610,5040.00,SI-5203,3780.00,yes,0.00,
RA-0610-MG,Marchmont Grocers Co-operative,2026-06-10,ACH,MG PAYRUN 0610,5040.00,SI-5219,1260.00,no,0.00,part payment; balance held pending the agreed spoilage allowance
RA-0611-CC,Corvid Coffee Houses LLC,2026-06-11,CHECK,6153,5250.00,SI-5196,5250.00,yes,0.00,
RA-0626-CC,Corvid Coffee Houses LLC,2026-06-26,ACH,CC ACH 0626,2100.00,SI-5236,2100.00,no,0.00,instalment on the June delivery; balance to follow
""",
        "credit_notes.csv": """credit_note_id,date,customer,invoice_id,net_amount,tax_amount,gross_amount,reason
CN-0618,2026-06-18,Marchmont Grocers Co-operative,SI-5219,3000.00,150.00,3150.00,spoilage allowance on the chilled range
""",
    },
    "cash_application_009": {
        "open_items.csv": """invoice_id,customer,invoice_date,due_date,original_amount,open_balance
SI-5188,Marchmont Grocers Co-operative,2026-04-22,2026-06-06,4410.00,1260.00
SI-5196,Corvid Coffee Houses LLC,2026-04-29,2026-05-29,5250.00,5250.00
SI-5203,Marchmont Grocers Co-operative,2026-05-06,2026-06-20,3780.00,3780.00
SI-5211,Ashgrove Halt Refreshments Ltd,2026-05-12,2026-06-11,1995.00,1995.00
SI-5219,Marchmont Grocers Co-operative,2026-05-19,2026-07-03,4200.00,2940.00
SI-5227,Corvid Coffee Houses LLC,2026-05-26,2026-06-25,3150.00,3150.00
""",
        "remittance_advice.csv": """remittance_id,customer,remittance_date,payment_method,payment_reference,payment_amount,invoice_id,amount_paid,settles_invoice,deduction_amount,note
RA-0610-MG,Marchmont Grocers Co-operative,2026-06-10,ACH,MG PAYRUN 0610,5040.00,SI-5203,3780.00,yes,0.00,
RA-0610-MG,Marchmont Grocers Co-operative,2026-06-10,ACH,MG PAYRUN 0610,5040.00,SI-5219,1260.00,no,0.00,part payment; balance held pending the agreed spoilage allowance
RA-0611-CC,Corvid Coffee Houses LLC,2026-06-11,CHECK,6153,5250.00,SI-5196,5250.00,yes,0.00,
RA-0626-CC,Corvid Coffee Houses LLC,2026-06-26,ACH,CC ACH 0626,2100.00,SI-5236,2100.00,no,0.00,instalment on the June delivery; balance to follow
""",
        "credit_notes.csv": """credit_note_id,date,customer,invoice_id,net_amount,tax_amount,gross_amount,reason
CN-0618,2026-06-18,Marchmont Grocers Co-operative,SI-5219,2800.00,140.00,2940.00,spoilage allowance on the chilled range
""",
    },
    "cash_application_010": {
        "open_items.csv": """invoice_id,customer,invoice_date,due_date,original_amount,open_balance
SI-7218,Quillhaven Publishing House,2026-05-19,2026-06-18,6480.00,1620.00
SI-7222,Broadmarsh Academy Trust,2026-05-27,2026-07-11,3780.00,3780.00
SI-7226,Quillhaven Publishing House,2026-06-04,2026-07-04,5250.00,5250.00
SI-7229,Broadmarsh Academy Trust,2026-06-11,2026-07-26,4410.00,4410.00
SI-7231,Quillhaven Publishing House,2026-06-16,2026-07-16,7920.00,7920.00
SI-7234,Pellow & Dunge Stationers,2026-06-23,2026-07-23,2835.00,2835.00
""",
        "remittance_advice.csv": """remittance_id,customer,remittance_date,payment_method,payment_reference,payment_amount,invoice_id,amount_paid,settles_invoice,deduction_amount,note
RA-0709-QP,Quillhaven Publishing House,2026-07-09,ACH,QPH SETTLEMENT 0709,9540.00,SI-7231,7920.00,yes,0.00,
RA-0709-QP,Quillhaven Publishing House,2026-07-09,ACH,QPH SETTLEMENT 0709,9540.00,SI-7226,1620.00,no,0.00,part payment; balance held pending the reprint reconciliation
RA-0716-BA,Broadmarsh Academy Trust,2026-07-16,CHECK,4417,3150.00,SI-7222,3150.00,yes,0.00,net of credit note CN-0714
RA-0722-BA,Broadmarsh Academy Trust,2026-07-22,ACH,BAT REMIT 0722,4395.00,SI-7229,4395.00,yes,15.00,Customer claims a minor carriage discrepancy; the seller has not approved a price reduction.
RA-0724-PD,Pellow & Dunge Stationers,2026-07-24,ACH,PDS PAYRUN 0724,2745.00,SI-7234,2745.00,yes,90.00,damaged spines claimed; credit requested
RA-0729-QP,Quillhaven Publishing House,2026-07-29,ACH,QPH SETTLEMENT 0729,8190.00,SI-7226,3630.00,yes,0.00,balance of the reprint reconciliation
RA-0729-QP,Quillhaven Publishing House,2026-07-29,ACH,QPH SETTLEMENT 0729,8190.00,SI-7239,4020.00,no,0.00,on account against the July binding run
RA-0729-QP,Quillhaven Publishing House,2026-07-29,ACH,QPH SETTLEMENT 0729,8190.00,SI-7218,0.00,no,0.00,withheld; disputed trimming charge; credit requested
""",
        "credit_notes.csv": """credit_note_id,date,customer,invoice_id,net_amount,tax_amount,gross_amount,reason
CN-0714,2026-07-14,Broadmarsh Academy Trust,SI-7222,600.00,30.00,630.00,agreed allowance; returned custom-printed units received 14 July were unusable and had no recoverable resale or salvage value; no replacement goods were supplied
""",
    },
    "cash_application_011": {
        "open_items.csv": """invoice_id,customer,invoice_date,due_date,original_amount,open_balance
SI-7218,Quillhaven Publishing House,2026-05-19,2026-06-18,6480.00,1620.00
SI-7222,Broadmarsh Academy Trust,2026-05-27,2026-07-11,3780.00,3780.00
SI-7226,Quillhaven Publishing House,2026-06-04,2026-07-04,5250.00,5250.00
SI-7229,Broadmarsh Academy Trust,2026-06-11,2026-07-26,4410.00,4410.00
SI-7231,Quillhaven Publishing House,2026-06-16,2026-07-16,7920.00,7920.00
SI-7234,Pellow & Dunge Stationers,2026-06-23,2026-07-23,2835.00,2835.00
""",
        "remittance_advice.csv": """remittance_id,customer,remittance_date,payment_method,payment_reference,payment_amount,invoice_id,amount_paid,settles_invoice,deduction_amount,note
RA-0709-QP,Quillhaven Publishing House,2026-07-09,ACH,QPH SETTLEMENT 0709,9540.00,SI-7231,7920.00,yes,0.00,
RA-0709-QP,Quillhaven Publishing House,2026-07-09,ACH,QPH SETTLEMENT 0709,9540.00,SI-7226,1620.00,no,0.00,part payment; balance held pending the reprint reconciliation
RA-0716-BA,Broadmarsh Academy Trust,2026-07-16,CHECK,4417,3150.00,SI-7222,3150.00,yes,0.00,net of credit note CN-0714
RA-0722-BA,Broadmarsh Academy Trust,2026-07-22,ACH,BAT REMIT 0722,4395.00,SI-7229,4395.00,yes,15.00,Customer claims a minor carriage discrepancy; the seller has not approved a price reduction.
RA-0724-PD,Pellow & Dunge Stationers,2026-07-24,ACH,PDS PAYRUN 0724,2745.00,SI-7234,2745.00,yes,90.00,damaged spines claimed; credit requested
RA-0729-QP,Quillhaven Publishing House,2026-07-29,ACH,QPH SETTLEMENT 0729,8190.00,SI-7226,3630.00,yes,0.00,balance of the reprint reconciliation
RA-0729-QP,Quillhaven Publishing House,2026-07-29,ACH,QPH SETTLEMENT 0729,8190.00,SI-7239,4560.00,no,0.00,on account against the July binding run
RA-0729-QP,Quillhaven Publishing House,2026-07-29,ACH,QPH SETTLEMENT 0729,8190.00,SI-7218,0.00,no,0.00,withheld; disputed trimming charge; credit requested
""",
        "credit_notes.csv": """credit_note_id,date,customer,invoice_id,net_amount,tax_amount,gross_amount,reason
CN-0714,2026-07-14,Broadmarsh Academy Trust,SI-7222,600.00,30.00,630.00,agreed allowance; returned custom-printed units received 14 July were unusable and had no recoverable resale or salvage value; no replacement goods were supplied
""",
    },
}

PACK_MANIFEST_ROWS = {
    "cash_application_006": (
        "| `open_items.csv` | Open sales-invoice register at 2026-06-01. 8 rows. Columns: invoice_id, customer, invoice_date, due_date, original_amount, open_balance. |",
        "| `remittance_advice.csv` | Customer remittance advices, one row per advice line. 3 rows. Columns: remittance_id, customer, remittance_date, payment_method, payment_reference, payment_amount, invoice_id, amount_paid, settles_invoice, deduction_amount, note. |",
        "| `credit_notes.csv` | Credit notes issued in the period. 1 row. Columns: credit_note_id, date, customer, invoice_id, net_amount, tax_amount, gross_amount, reason. |",
    ),
    "cash_application_007": (
        "| `open_items.csv` | Open sales-invoice register at 2026-06-01. 8 rows. Columns: invoice_id, customer, invoice_date, due_date, original_amount, open_balance. |",
        "| `remittance_advice.csv` | Customer remittance advices, one row per advice line. 3 rows. Columns: remittance_id, customer, remittance_date, payment_method, payment_reference, payment_amount, invoice_id, amount_paid, settles_invoice, deduction_amount, note. |",
        "| `credit_notes.csv` | Credit notes issued in the period. 1 row. Columns: credit_note_id, date, customer, invoice_id, net_amount, tax_amount, gross_amount, reason. |",
    ),
    "cash_application_008": (
        "| `open_items.csv` | Open sales-invoice register at 2026-06-01. 6 rows. Columns: invoice_id, customer, invoice_date, due_date, original_amount, open_balance. |",
        "| `remittance_advice.csv` | Customer remittance advices, one row per advice line. 4 rows. Columns: remittance_id, customer, remittance_date, payment_method, payment_reference, payment_amount, invoice_id, amount_paid, settles_invoice, deduction_amount, note. |",
        "| `credit_notes.csv` | Credit notes issued in the period. 1 row. Columns: credit_note_id, date, customer, invoice_id, net_amount, tax_amount, gross_amount, reason. |",
    ),
    "cash_application_009": (
        "| `open_items.csv` | Open sales-invoice register at 2026-06-01. 6 rows. Columns: invoice_id, customer, invoice_date, due_date, original_amount, open_balance. |",
        "| `remittance_advice.csv` | Customer remittance advices, one row per advice line. 4 rows. Columns: remittance_id, customer, remittance_date, payment_method, payment_reference, payment_amount, invoice_id, amount_paid, settles_invoice, deduction_amount, note. |",
        "| `credit_notes.csv` | Credit notes issued in the period. 1 row. Columns: credit_note_id, date, customer, invoice_id, net_amount, tax_amount, gross_amount, reason. |",
    ),
    "cash_application_010": (
        "| `open_items.csv` | Open sales-invoice register at 2026-07-01. 6 rows. Columns: invoice_id, customer, invoice_date, due_date, original_amount, open_balance. |",
        "| `remittance_advice.csv` | Customer remittance advices, one row per advice line. 8 rows. Columns: remittance_id, customer, remittance_date, payment_method, payment_reference, payment_amount, invoice_id, amount_paid, settles_invoice, deduction_amount, note. |",
        "| `credit_notes.csv` | Credit notes issued in the period. 1 row. Columns: credit_note_id, date, customer, invoice_id, net_amount, tax_amount, gross_amount, reason. |",
    ),
    "cash_application_011": (
        "| `open_items.csv` | Open sales-invoice register at 2026-07-01. 6 rows. Columns: invoice_id, customer, invoice_date, due_date, original_amount, open_balance. |",
        "| `remittance_advice.csv` | Customer remittance advices, one row per advice line. 8 rows. Columns: remittance_id, customer, remittance_date, payment_method, payment_reference, payment_amount, invoice_id, amount_paid, settles_invoice, deduction_amount, note. |",
        "| `credit_notes.csv` | Credit notes issued in the period. 1 row. Columns: credit_note_id, date, customer, invoice_id, net_amount, tax_amount, gross_amount, reason. |",
    ),
}


def test_each_variant_pack_is_two_variants_of_one_company_month():
    problems = []
    if [m.__name__.rsplit(".", 1)[1] for m in CASH_APPLICATION_PAIR_MODULES] != \
            ["thornbury_2026_06", "pennywhistle_2026_06", "tallowmere_2026_07"]:
        problems.append(f"pair modules {[m.__name__ for m in CASH_APPLICATION_PAIR_MODULES]}")
    want_worlds = {("cash_application_006", "cash_application_007"): ("thornbury-2026-06-pf-a", "thornbury-2026-06-pf-b"),
                   ("cash_application_008", "cash_application_009"): ("pennywhistle-2026-06-cr-a", "pennywhistle-2026-06-cr-b"),
                   ("cash_application_010", "cash_application_011"): ("tallowmere-2026-07-ar-a", "tallowmere-2026-07-ar-b")}
    shared = ("title", "currency", "bank_account", "bank_party_id", "accounts", "parties", "documents",
              "bank_opening", "opening", "roles", "policy_text")
    for pair in PAIR_IDS:
        a, b = (variant(task_id) for task_id in pair)
        (_, world_a, task_a, _, _, public_a) = a
        (_, world_b, task_b, _, _, public_b) = b
        if (world_a.id, world_b.id) != want_worlds[pair]:
            problems.append(f"{pair}: world ids {(world_a.id, world_b.id)}")
        for attr in shared:
            if repr(getattr(world_a, attr)) != repr(getattr(world_b, attr)):
                problems.append(f"{pair}: the two variants differ in {attr}, which the pair holds identical")
        if task_a.prompt != task_b.prompt or task_a.type != task_b.type != "bank_reconciliation" \
                or task_a.period != task_b.period:
            problems.append(f"{pair}: the two tasks do not share one prompt, one type and one period")
        if not P.is_cash_application_world(world_a) or not P.is_cash_application_world(world_b):
            problems.append(f"{pair}: the family is not inferred from the events")
        # exactly one authored fact moves, and exactly the pack's files with it
        differ = {name: sum(1 for x, y in zip(public_a[name].splitlines(), public_b[name].splitlines()) if x != y)
                  for name in public_a if public_a[name] != public_b[name]}
        if differ != PAIR_DIFFERS[pair]:
            problems.append(f"{pair}: the variants differ in {differ}, not {PAIR_DIFFERS[pair]}")
        if len(public_a) != 11 or set(public_a) != set(public_b):
            problems.append(f"{pair}: {len(public_a)} public files")
        # the pack's own evidence files, byte for byte
        for task_id, public in zip(pair, (public_a, public_b)):
            for name, want in PACK_FAMILY_FILES[task_id].items():
                if public[name] != want:
                    problems.append(f"{task_id}: {name} is not the pack's bytes")
            manifest = public["manifest.md"]
            for line in PACK_MANIFEST_ROWS[task_id]:
                if line not in manifest:
                    problems.append(f"{task_id}: manifest row absent: {line}")
    # the instruction is Bowline's, month for month, and nothing else
    for task_id in VARIANT_IDS:
        _, _, task, *_ = variant(task_id)
        month = task.period.label.split()[0]
        if task.prompt != VP.prompt(month) or VP.prompt("April") != B.PROMPT:
            problems.append(f"{task_id}: the prompt is not the shared instruction for {month}")
        for word in ("write-off", "written off", "transpos", "missing", "duplicat", "unapplied cash", "rung",
                     "SI-4", "SI-5", "SI-7", "residue"):
            if word.lower() in task.prompt.lower() and word not in ("written off",):
                problems.append(f"{task_id}: the prompt reveals {word!r}")
    return check("the three variant packs: six worlds thornbury/pennywhistle/tallowmere -a and -b, tasks "
                 "cash_application_006..011, each pair one chart, one set of parties, documents, opening and "
                 "policy, one prompt (Bowline's, month for month), eleven public files, exactly the pack's "
                 "files differing, and open_items.csv, remittance_advice.csv and credit_notes.csv the pack's "
                 "bytes", not problems, "\n".join(problems))


def test_every_gate_passes_for_all_six_variants():
    problems = []
    for task_id in VARIANT_IDS:
        module, world, task, *_ = variant(task_id)
        source = WORLDS_DIR / f"{module.__name__.rsplit('.', 1)[1]}.py"
        siblings = tuple(w for tid, w in module.WORLD_BY_TASK.items() if tid != task_id)
        found, warnings = check_world_task(world, task, source_path=source, co_authored=siblings)
        problems += [f"{task_id}: {p}" for p in found]
        for w in warnings:
            print(f"      {task_id}: {w[:200]}")
        # the shared policy/instruction module is scanned for derived literals too
        found_shared, _ = check_world_task(world, task, source_path=WORLDS_DIR / "_variant_pack.py",
                                           co_authored=siblings)
        problems += [f"{task_id} (_variant_pack.py): {p}" for p in found_shared
                     if "appears as" in p and "literal" in p]
    return check("every world gate — schema, derivation, golden 1.0, original unresolved, merged trap, scoped (f), "
                 "private ids, derived literals (the pair module and _variant_pack.py), name pools, headings, the "
                 "family's (l), (m), (n) and plant coverage — passes for all six variants",
                 not problems, "\n".join(problems))


def test_gate_m_and_l_over_the_six_variants():
    problems = []
    for task_id in VARIANT_IDS:
        _, world, task, _, inputs, public = variant(task_id)
        want = PACK[task_id]
        truth = inputs.application
        try:
            app = CA.fold(public, **kw(task))
        except Exception as exc:
            problems.append(f"{task_id}: the public fold refused the projected bytes: {exc}")
            continue
        if CA.application_key(app) != truth.application_key():
            problems.append(f"{task_id}: public {CA.application_key(app)}\n  truth {truth.application_key()}")
        # gate (m): the truth is the pack's tables, receipt by receipt
        got = {r[0]: (r[4], r[5], r[6]) for r in truth.receipts}
        for receipt_id, (applied, written_off, unapplied) in want["receipts"].items():
            if got.get(receipt_id) != (applied, written_off, D(unapplied)):
                problems.append(f"{task_id}: receipt {receipt_id} {got.get(receipt_id)} != "
                                f"{(applied, written_off, D(unapplied))}")
        if set(got) != set(want["receipts"]):
            problems.append(f"{task_id}: receipts {sorted(got)} != {sorted(want['receipts'])}")
        credits = {c[0]: (c[4], c[5]) for c in truth.credit_notes}
        if credits != want["credits"]:
            problems.append(f"{task_id}: credit applications {credits} != {want['credits']}")
        if tuple(truth.register) != want["register"]:
            for a, b in zip(truth.register, want["register"]):
                if a != b:
                    problems.append(f"{task_id}: row {a} != {b}")
            if len(truth.register) != len(want["register"]):
                problems.append(f"{task_id}: {len(truth.register)} register rows, not {len(want['register'])}")
        expected_ar = dict(inputs.expected_balances)[AR]
        if not (app.closing_ar == truth.closing_ar == expected_ar == D(want["closing"])):
            problems.append(f"{task_id}: closing AR public {app.closing_ar} truth {truth.closing_ar} ledger "
                            f"{expected_ar} pack {want['closing']}")
        if D(inputs.statement_closing) != D(want["statement"]):
            problems.append(f"{task_id}: statement closes {inputs.statement_closing}, not {want['statement']}")
        # gate (l): the register ties to the opening entry on both sides
        ev = CA.read_evidence(public, **kw(task))
        opening = D(want["opening"])
        if not (ev.opening_ar == truth.opening_ar == dict(world.opening.carried)[AR] == opening):
            problems.append(f"{task_id}: opening AR public {ev.opening_ar} truth {truth.opening_ar} "
                            f"entry {dict(world.opening.carried)[AR]} pack {opening}")
        if sum((r[5] for r in truth.opening_register), D(0)) != opening:
            problems.append(f"{task_id}: the truth's opening register does not sum to the opening entry")
        doc = CA.document(app)
        if doc["schema"] != "piv.cash-application/1" or len(doc["closing_open_items"]) != len(want["register"]):
            problems.append(f"{task_id}: document {doc['schema']} with {len(doc['closing_open_items'])} rows")
    return check("gates (m) and (l) over the six variants: the public fold over the projected bytes equals the "
                 "truth folded from the authored facts, both close at the expected ledger's AR, the truth is the "
                 "pack's receipts, write-offs, credit applications, residues and register rows, and the register "
                 "ties to the opening entry", not problems, "\n".join(problems))


def test_the_write_off_account_opens_at_zero_in_all_three_months():
    problems = []
    for task_id in VARIANT_IDS:
        _, world, task, bundle, inputs, public = variant(task_id)
        want = D(PACK[task_id]["written_off"])
        write_offs = dict(world.roles)["small_balance_write_offs"]
        if write_offs != WRITE_OFFS:
            problems.append(f"{task_id}: the write-off role names {write_offs}")
        # nothing carried into the period on that account, so its expected
        # CLOSING balance is also its period movement — which is what
        # `candidate/application.py` reads for `writeoff_tie_break`.
        if any(account == write_offs for account, _ in world.opening.carried):
            problems.append(f"{task_id}: the opening position carries a leg for {write_offs}")
        opening = next(r for r in bundle.recognitions if r.rule == "opening")
        if any(leg.account == write_offs for leg in opening.legs):
            problems.append(f"{task_id}: the opening entry carries a leg for {write_offs}")
        carry_forward = public["ledger.beancount"].split(PJ.BANNER)[0]
        if f"\n  {write_offs}" in carry_forward:
            problems.append(f"{task_id}: the opening ledger's carry-forward names {write_offs}")
        closing = dict(inputs.expected_balances)[write_offs]
        movement = sum((amount for r in inputs.application.receipts for _, amount in r[5]), D(0))
        if not (closing == movement == want):
            problems.append(f"{task_id}: write-off closing {closing}, movement {movement}, pack {want}")
        if sum((r[5] for r in inputs.application.register), D(0)) != want:
            problems.append(f"{task_id}: the register's written_off column does not sum to {want}")
    return check("the write-off account opens at ZERO in all three months — no opening leg, no carry-forward "
                 "row — so its expected closing balance is its period movement: 0.00 / 0.00 / 15.00, and the "
                 "register's written_off column sums to the same", not problems, "\n".join(problems))


#: Gate (o), pinned per variant: the baselines the EVIDENCE admits, read off
#: `six_variant_packs.md` section 4 against `cash_application.BASELINES`.
#: Thornbury admits EIGHT of the ten, not all ten: `write_off_everything` and
#: `write_off_nothing` are not admitted there, because no bound advice claims
#: a deduction anywhere in that month. An empty `refused_by` would not catch
#: an admitted set that silently grew or shrank, so the set itself is pinned.
ADMITTED_BASELINES = {
    "cash_application_006": ("amount_only", "credit_ignored", "hold_on_account", "mixed_amount_only",
                             "mixed_oldest_first", "number_order", "oldest_first", "printed_order"),
    "cash_application_008": ("amount_only", "credit_ignored", "oldest_first"),
    "cash_application_010": ("amount_only", "credit_ignored", "oldest_first",
                             "write_off_everything", "write_off_nothing"),
}
#: each pair's two variants differ in one authored fact, never in what the
#: evidence admits.
ADMITTED_BASELINES["cash_application_007"] = ADMITTED_BASELINES["cash_application_006"]
ADMITTED_BASELINES["cash_application_009"] = ADMITTED_BASELINES["cash_application_008"]
ADMITTED_BASELINES["cash_application_011"] = ADMITTED_BASELINES["cash_application_010"]


def test_gate_n_and_gate_o_over_the_six_variants():
    problems = []
    # every shipped baseline is admitted by at least one of the three months,
    # so a baseline added or renamed upstream cannot slip past the pins below.
    pinned = set().union(*(set(names) for names in ADMITTED_BASELINES.values()))
    shipped = set(CA.BASELINE_NAMES) | set(CA.DIAGNOSTIC_BASELINE_NAMES)
    if pinned != shipped:
        problems.append(f"the shipped baselines are {sorted(shipped)}; the pinned admitted sets name "
                        f"{sorted(pinned)}, so a baseline was added or renamed without pinning it here")
    for task_id in VARIANT_IDS:
        _, world, task, _, inputs, public = variant(task_id)
        # (n) the narration rule, over every receipt and write-off narration
        # the expected ledger carries, and every advice note and credit memo
        notes = frozenset(c[0] for c in inputs.application.credit_notes)
        for event in world.events:
            if not isinstance(event, (S.AppliedReceipt, S.CreditNote)):
                continue
            if isinstance(event, S.CreditNote):
                tied = frozenset({world.document(event.invoice_id).number})
                texts = [f"Credit note {event.number} against {world.document(event.invoice_id).number}: "
                         f"{event.memo}", event.memo]
            else:
                receipt_id = f"{event.settlement.cleared_on}:" + (
                    world.document(event.settlement.cheque_id).number
                    if event.settlement.rail is S.Rail.CHEQUE else event.bank_reference)
                tied = public_ties(CA.read_evidence(public, **kw(task)), receipt_id)
                texts = [event.memo] + [line.note for line in event.lines if line.note]
                texts += [r.narration for r in derive_contract(world, task)[0].recognitions
                          if r.event_id == event.id]
            for text in texts:
                problems += [f"{task_id}: gate (n): {p}" for p in narration_problems(text, tied, notes, task_id)]
        # (o) no admitted baseline reaches the truth — the DIAGNOSTIC one
        # included, which `refused_by` ignores by construction — and the
        # admitted SET is the pack's, name for name.
        report = CA.baseline_report(public, **kw(task))
        reached = CA.refused_by(report)
        if reached:
            problems.append(f"{task_id}: gate (o): reached by {reached}")
        diagnostic_reach = tuple(name for name, r in report.items()
                                 if r.admitted and r.diagnostic and r.reaches_truth)
        if diagnostic_reach:
            problems.append(f"{task_id}: gate (o): diagnostic baseline(s) {diagnostic_reach} reach the truth")
        admitted = tuple(sorted(name for name, r in report.items() if r.admitted))
        if admitted != tuple(sorted(ADMITTED_BASELINES[task_id])):
            problems.append(f"{task_id}: gate (o): the evidence admits {admitted}, not the pack's "
                            f"{tuple(sorted(ADMITTED_BASELINES[task_id]))}")
        print(f"      {task_id}: " + ", ".join(
            f"{name}={'-' if r.reaches_truth is None else ('REACHES' if r.reaches_truth else 'no')}"
            for name, r in report.items()))
    return check("gates (n) and (o) over the six variants: no narration, advice note or credit memo names an "
                 "invoice the payment's own public documents do not tie to it or instructs an application, no "
                 "admitted baseline (the diagnostic one included) reaches any of the six truths, and the admitted "
                 "SETS are the pack's — eight of the ten at Thornbury, three at Pennywhistle, five at "
                 "Tallowmere", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# the credit note's original-sale basis (round 15, decision 6)
# --------------------------------------------------------------------------

def test_the_credit_basis_guard_reads_an_independently_established_original_sale():
    """`schema.original_sale_basis` establishes an invoice's original net and
    tax from the WORLD — the sale it authors, or, for an invoice carried in
    from the prior period, its gross split at the world's own single authored
    sales rate — and never from the credit note being checked. The negative
    control is round 15's own example, which the superseded derivation
    (`gross / (1 + credit_note.tax_rate)`) admitted."""
    problems = []
    worlds = [m.WORLD for m in CASH_APPLICATION_MODULES]
    for module in CASH_APPLICATION_PAIR_MODULES:
        worlds += list(dict.fromkeys(module.WORLD_BY_TASK.values()))

    # 1. nothing shipped moved: every world still passes, and every note still
    #    fits a basis that is now READ rather than manufactured.
    notes = 0
    for world in worlds:
        found = S.check_world(world)
        if found:
            problems.append(f"{world.id}: check_world now refuses it: {found[:2]}")
        for event in world.events:
            if not isinstance(event, S.CreditNote):
                continue
            notes += 1
            net, tax_basis, source = S.original_sale_basis(world, event.invoice_id)
            note_tax, _gross = P.credit_note_amounts(event)
            if net is None:
                problems.append(f"{world.id}: no basis for {event.number}: {source}")
            elif event.net > net or note_tax > tax_basis:
                problems.append(f"{world.id}: {event.number} {event.net}+{note_tax} exceeds its basis "
                                f"{net}+{tax_basis}")
            # the basis is a fact of the world: re-authoring the note at a
            # rate its sale never used leaves the basis where it was
            elsewhere = S.original_sale_basis(
                dataclasses.replace(world, events=tuple(
                    dataclasses.replace(e, tax_rate=D("0.00")) if e is event else e for e in world.events)),
                event.invoice_id)
            if elsewhere[:2] != (net, tax_basis):
                problems.append(f"{world.id}: {event.number} at a zero rate moves its own basis to {elsewhere[:2]}")
    if notes != 11:
        problems.append(f"{notes} credit notes across the eleven worlds, not 11")

    # 2. the basis does not move when the NOTE's rate does. Pennywhistle's
    #    SI-5219 is round 15's invoice: 4,200.00 gross, a 4,000.00 + 200.00
    #    sale at the world's 5%.
    penny = VARIANT_MODULE["cash_application_008"][1]
    note = next(e for e in penny.events if isinstance(e, S.CreditNote))
    basis = S.original_sale_basis(penny, note.invoice_id)
    if basis[:2] != (D("4000.00"), D("200.00")):
        problems.append(f"SI-5219's basis reads {basis}, not 4000.00 + 200.00")
    for rate in ("0.00", "0.05", "0.20", "1.00"):
        moved = S.original_sale_basis(
            dataclasses.replace(penny, events=tuple(
                dataclasses.replace(e, tax_rate=D(rate)) if e is note else e for e in penny.events)),
            note.invoice_id)
        if moved[:2] != basis[:2]:
            problems.append(f"a note at {rate} moved the basis to {moved[:2]}")

    # 3. THE NEGATIVE CONTROL: a 4,100.00 net credit at zero tax against that
    #    invoice. `gross / (1 + 0.00)` called the original net 4,200.00 and
    #    admitted it; the sale was 4,000.00.
    gross = penny.document(note.invoice_id).gross
    if gross != D("4200.00") or not D("4100.00") <= (gross / (D(1) + D("0.00"))).quantize(D("0.01")):
        problems.append("the superseded derivation would not have admitted the control; it is not a control")
    mismatched = dataclasses.replace(penny, events=tuple(
        dataclasses.replace(e, net=D("4100.00"), tax_rate=D("0.00")) if e is note else e for e in penny.events))
    found = S.check_world(mismatched)
    if not any("reverses 4100.00 of sales value" in p and "original sale is 4000.00" in p for p in found):
        problems.append(f"the mismatched-rate credit was not refused: {found[:3]}")

    # 4. a note whose TAX alone exceeds the sale's tax is refused on that leg,
    #    and the bound is the SALE, never the unpaid balance: Bowline's Case 5
    #    credits 540.00 against SI-3100, which has 300.00 outstanding.
    over_tax = dataclasses.replace(penny, events=tuple(
        dataclasses.replace(e, net=D("4000.00"), tax_rate=D("0.10")) if e is note else e for e in penny.events))
    if not any("of tax against" in p and "original tax is 200.00" in p for p in S.check_world(over_tax)):
        problems.append(f"a 400.00 tax credit against a 200.00 tax sale passed: {S.check_world(over_tax)[:3]}")
    _m5, world5, *_ = case(5)
    case_5_note = next(e for e in world5.events if isinstance(e, S.CreditNote))
    _net5, _tax5, source5 = S.original_sale_basis(world5, case_5_note.invoice_id)
    if S.check_world(world5) or _net5 != D("1000.00"):
        problems.append(f"Case 5's 540.00 credit against a 300.00 balance is refused: {S.check_world(world5)[:2]}")

    # 5. an invoice raised INSIDE the period is read off its own sale, not off
    #    any rate arithmetic — Thornbury's SI-4415 is 6,000.00 at 6%.
    thornbury = VARIANT_MODULE["cash_application_007"][1]
    net, tax_basis, source = S.original_sale_basis(thornbury, "doc:si-4415")
    if (net, tax_basis) != (D("6000.00"), D("360.00")) or "event:si-4415-sale" not in source:
        problems.append(f"SI-4415's basis reads {net} + {tax_basis} from {source}")

    # 6. a world that establishes NO basis may not carry a note against the
    #    invoice: two authored sales rates leave the prior-period gross with
    #    nothing to split at.
    sales = [e for e in penny.events if isinstance(e, S.Sale)]
    two_rates = dataclasses.replace(penny, events=tuple(
        dataclasses.replace(e, tax_rate=D("0.07")) if e is sales[0] else e for e in penny.events))
    if not any("no original sale is established" in p for p in S.check_world(two_rates)):
        problems.append(f"a note against an unestablished basis passed: {S.check_world(two_rates)[:3]}")
    return check("the credit-basis guard bounds a note against an INDEPENDENTLY established original sale — the "
                 "world's authored sale, or a prior-period invoice's gross split at the world's own single sales "
                 "rate — so the note's own rate cannot move its bound; round 15's 4,100.00-at-zero-tax control "
                 "against a 4,200.00 gross invoice whose sale was 4,000.00 + 200.00 is refused, an over-credited "
                 "tax leg is refused, a world with no established basis may not carry a note, and all eleven "
                 "shipped notes still pass with the bound at the SALE and not the unpaid balance",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_family_is_five_variants_of_one_company_month,
    test_every_gate_passes_for_all_five,
    test_gate_f_reads_every_case_as_the_planted_repairs,
    test_the_projected_pack_is_the_spec_s,
    test_case_2_s_inputs_moved_after_the_screen_and_the_repository_says_where,
    test_the_screen_sidecar_records_the_measured_revision_not_the_revision_it_was_written_at,
    test_gate_m_the_public_fold_over_actual_bytes_equals_the_truth,
    test_gate_l_the_register_ties_to_the_opening_entry,
    test_gate_n_the_narration_rule,
    test_u12_warnings_are_warnings_not_gates,
    test_the_plants_are_the_spec_s,
    test_bank_date_posting_holds_independently_of_the_plant,
    test_cheque_sign_and_movement_extensions,
    test_receipt_validation_and_cumulative_checks,
    test_the_write_off_rule_and_the_optional_role,
    test_roles_and_digests_of_the_shipped_worlds,
    test_gate_o_on_the_actual_bytes,
    test_each_variant_pack_is_two_variants_of_one_company_month,
    test_every_gate_passes_for_all_six_variants,
    test_gate_m_and_l_over_the_six_variants,
    test_the_write_off_account_opens_at_zero_in_all_three_months,
    test_gate_n_and_gate_o_over_the_six_variants,
    test_the_credit_basis_guard_reads_an_independently_established_original_sale,
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
