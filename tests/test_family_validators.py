"""Step 4 of the cash-application spec (section 8, implementation order):
identifiability and plant validation for the five Bowline cases.

The spec's declared open implementation risk was that gate (f) — the public
bank identifiability checker, `identify.check_identifiable` — might not
return one reading for the family: it read `GR PAYRUN 0428` and `SI-3104
SI-3102` as UNKNOWN references, which are never decisive, never a conflict
and never presented, so the mis-keyed R3 two days before the cut-off admitted
a second reading in which the row is an unrecorded receipt and the entry a
deposit in transit. The risk was real (the previous pin held Cases 1, 2, 4
and 5 at two readings). Of the two fixes the spec named — extend the
reference-syntax recognition for payment references, or carry the statement
reference into the receipt narration — step 4 implemented the FIRST:
`identify._payment_reference_words` recognises the addendum an ACH credit
carries (several words, one with a digit) and classifies it as an
INSTRUMENT, because a DOCUMENT role never prunes and the narrations already
quoted the reference to no effect. Its docstring records the choice in the
spec's terms.

What is witnessed here:

  * the ontology: a payment reference is an instrument; a lone invoice id,
    a cheque number, a trace id, an unknown code and a memo keep their
    roles; the declared role set and `IDENTIFY_VERSION` are unchanged; the
    quotation rule (`_mentions`) needs the addendum's words in order;
  * Cases 1 and 2 first, then all five: `check_identifiable` over the
    ACTUAL projected bytes is unique with one reading, and the reading is
    exactly the planted bank-evidenced repairs under the shared repair key;
    R3's row is an instrument, decisive, presented, and its alteration edge
    stands on the reference;
  * the mechanism and its limits: a narration that does not quote the
    addendum falls back to the counterparty basis and the in-transit
    reading returns (two readings) — the join gate (n) permits is
    load-bearing; a narration naming an invoice instead of the addendum is
    read as another movement (the instrument conflict) and the reading is
    not the planted one; an addendum the statement prints twice is not
    decisive and presents nothing, so the world stays ambiguous rather than
    being certified; the in-transit refusal names the presented reference;
  * the shipped population is out of the syntax's reach: no statement or
    archive row of the 95 legacy tasks prints a multi-word reference, which
    is why `IDENTIFY_VERSION` stays 7 (a bump would make `manifest.admit`
    refuse every promoted record for a change that reaches none of them);
  * the write-off plant is validated THROUGH THE PUBLIC FOLD (gate (m)):
    Case 3 as authored passes and its plant is covered; a re-dated
    expected entry, a narration naming the wrong invoice, a planted shape
    that is not the fold's, a compensating pair that ties closing AR (R3
    restated by 20.00 and the write-off at 40.00), and an advice edited on
    the public bytes so nothing is written off are each refused by name;
  * every plant is covered by an explicit validator: a planted item with no
    bank leg and no write-off is reported as uncovered;
  * `tests/verify_world.py` accepts the five modules, and
    `tests/test_worlds.py` holds the five to the registry gate.

    python tests/test_family_validators.py
"""

from __future__ import annotations

import copy
import csv
import dataclasses
import io
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from beancount_ledger.graph import cash_application as CA  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.worlds import (  # noqa: E402
    CASH_APPLICATION_MODULES,
    LEGACY_TASK_IDS,
    REGISTRY,
)

from repair_keys import master_names, planted_key  # noqa: E402
from world_checks import _family_gates, check_derived, check_world_task, decoded_public  # noqa: E402

WORLDS_DIR = ROOT / "beancount_ledger" / "graph" / "worlds"
BANK, AR, WRITE_OFFS = "Assets:Bank:Checking", "Assets:AR", "Expenses:SmallBalanceWriteOffs"
GANNET, SHEARWATER = "Gannet Rigging Inc", "Shearwater Bay Charters LLC"
R3_REFERENCE = {1: "GR PAYRUN 0428", 2: "SI-3104 SI-3102", 3: "GR PAYRUN 0428", 4: "GR PAYRUN 0428", 5: "GR PAYRUN 0428"}


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:40]:
            print(f"      {line}")
    return ok


_DERIVED: dict = {}


def case(n: int):
    """(module, world, task, bundle, inputs, public) for case n."""
    if n not in _DERIVED:
        module = CASH_APPLICATION_MODULES[n - 1]
        task = module.TASKS[f"cash_application_{n:03d}"]
        bundle, inputs = derive_contract(module.WORLD, task)
        _DERIVED[n] = (module, module.WORLD, task, bundle, inputs, decoded_public(inputs))
    return _DERIVED[n]


def kw(task):
    return dict(bank_account=BANK, period_start=task.period.start, period_end=task.period.end)


def planted_bank_keys(inputs, public):
    names = master_names(public)
    return sorted(planted_key(p, names, bank_account=BANK) for p in inputs.planted
                  if any(a == BANK for a, _ in p.required))


def read_keys(verdict):
    return sorted(ID.repair_key(r) for r in verdict.repairs)


def with_row(public: dict, date: str, description: str, reference: str, debit: str, credit: str) -> dict:
    """The statement with one more row, in date order, the balance column
    walked forward again from the opening row."""
    lines = public[ID.STATEMENT_FILE].splitlines()
    header, opening = lines[0], lines[1]
    rows = [line.split(",") for line in lines[2:] if line.strip()]
    rows.append([date, description, reference, debit, credit, ""])
    rows.sort(key=lambda r: (r[0], r[1]))
    balance = D(opening.rsplit(",", 1)[1])
    out = [header, opening]
    for r in rows:
        balance += (D(r[4]) if r[4] else D(0)) - (D(r[3]) if r[3] else D(0))
        out.append(",".join(r[:5] + [f"{balance:.2f}"]))
    return {**public, ID.STATEMENT_FILE: "\n".join(out) + "\n"}


def tampered(inputs, **changes):
    """`inputs` with some fields replaced, for the gates that own them.

    `ContractInputs` refuses literal construction (`derive_contract` mints
    it), so `dataclasses.replace` cannot build a tampered copy; the copy is
    made behind the mint guard on purpose — the whole point of these
    fixtures is a derived artefact that no longer agrees with its evidence,
    which no authored world can produce and no serving path ever sees.
    """
    out = copy.copy(inputs)
    for name, value in changes.items():
        object.__setattr__(out, name, value)
    return out


def r3_facts(public, task):
    ev = ID._evidence(public, BANK, task.period.start, task.period.end)
    rows = [r for r in ev.rows if r.date == "2026-04-28" and r.amount > 0]
    assert len(rows) == 1, rows
    return ev, rows[0], ev.facts_by_row[rows[0].index]


# --------------------------------------------------------------------------

def test_the_payment_reference_is_an_instrument_and_nothing_else_moved():
    problems = []
    table = [
        ("GR PAYRUN 0428", "ACH IN GANNET RIGGING INC GR PAYRUN 0428", ID.REF_INSTRUMENT),
        ("SI-3104 SI-3102", "ACH IN GANNET RIGGING INC SI-3104 SI-3102", ID.REF_INSTRUMENT),
        ("GR PAYRUN 0428", "", ID.REF_INSTRUMENT),              # the syntax alone, whatever the surface
        ("SI-3104", "ACH IN GANNET RIGGING INC SI-3104", ID.REF_DOCUMENT),
        ("PI-8813", "ACH OUT NORTHSHORE CHANDLERY SUPPLY PI-8813", ID.REF_DOCUMENT),
        ("2291", "CHECK 2291 SHEARWATER BAY CHARTERS LLC", ID.REF_INSTRUMENT),
        ("TRACE0284471", "ACH IN TRACE0284471", ID.REF_INSTRUMENT),
        ("PAY RUN", "ACH IN GANNET RIGGING INC PAY RUN", ID.REF_UNKNOWN),   # no digit: not a payment reference
        ("GRPAYRUN0428", "ACH IN GANNET RIGGING INC GRPAYRUN0428", ID.REF_UNKNOWN),  # one word: the column as printed decides
        ("SL-1162", "ACH OUT STAKELINE SURVEY SUPPLY", ID.REF_UNKNOWN),
        ("BX-99", "Batch BX-99", ID.REF_UNKNOWN),
        ("", "Office supplies", ID.REF_MEMO),
    ]
    for token, text, want in table:
        got = ID.reference_role(token, text)
        if got != want:
            problems.append(f"reference_role({token!r}, {text!r}) = {got}, want {want}")
    if set(ID.REFERENCE_ROLES) != {ID.REF_INSTRUMENT, ID.REF_DOCUMENT, ID.REF_MEMO, ID.REF_UNKNOWN}:
        problems.append(f"the role set moved: {ID.REFERENCE_ROLES}")
    if ID.IDENTIFY_VERSION != 7:
        problems.append(f"IDENTIFY_VERSION is {ID.IDENTIFY_VERSION}; the syntax extension keeps 7 (see its changelog)")
    words = {"GR PAYRUN 0428": ("GR", "PAYRUN", "0428"), "SI-3104 SI-3102": ("SI3104", "SI3102"),
             "gr payrun 0428": ("GR", "PAYRUN", "0428"), "SI-3104": (), "2291": (), "": (), "PAY RUN": ()}
    for reference, want in words.items():
        if ID._payment_reference_words(reference) != want:
            problems.append(f"_payment_reference_words({reference!r}) = {ID._payment_reference_words(reference)}")
    quotes = [
        ("Gannet Rigging Inc Customer payment, GR PAYRUN 0428", "GR PAYRUN 0428", True),
        ("Gannet Rigging Inc Customer payment, gr payrun 0428", "GR PAYRUN 0428", True),
        ("Gannet Rigging Inc Customer payment, PAYRUN 0428 GR", "GR PAYRUN 0428", False),
        ("Gannet Rigging Inc Customer payment, GR PAYRUN 0410", "GR PAYRUN 0428", False),
        ("Gannet Rigging Inc Customer payment, SI-3104 SI-3102", "SI-3104 SI-3102", True),
        ("Gannet Rigging Inc Customer payment for SI-3102", "SI-3104 SI-3102", False),
        ("Gannet Rigging Inc Customer payment, SI-3102 SI-3104", "SI-3104 SI-3102", False),
        ("November office rent, check 1037", "1037", True),
        ("Customer payment settling SI-1052", "SI-1052", True),
    ]
    for haystack, token, want in quotes:
        if ID._mentions(haystack, token) != want:
            problems.append(f"_mentions({haystack!r}, {token!r}) != {want}")
    return check("the payment reference (several words, one with a digit) is an instrument; a lone invoice id, "
                 "cheque number, trace id, unknown code and memo keep their roles; the role set and "
                 "IDENTIFY_VERSION 7 are unchanged; the addendum is quoted only by its words in order",
                 not problems, "\n".join(problems))


def test_cases_1_and_2_first_then_all_five_read_uniquely_as_planted():
    problems = []
    for n in (1, 2, 1, 2, 3, 4, 5):                # Cases 1 and 2 first, as the spec asks, then all five
        _, world, task, _, inputs, public = case(n)
        verdict = ID.check_identifiable(public, **kw(task))
        want, got = planted_bank_keys(inputs, public), read_keys(verdict)
        if not verdict.unique or verdict.readings != 1:
            problems.append(f"case {n}: {verdict.readings} readings: {verdict.reason[:300]}")
        if want != got:
            problems.append(f"case {n}: planted {want}\n  read {got}")
        ev, row, facts = r3_facts(public, task)
        if row.reference != R3_REFERENCE[n] or facts.ref_role != ID.REF_INSTRUMENT or not facts.decisive \
                or row.reference not in facts.presents:
            problems.append(f"case {n}: R3's row {row} is {facts.ref_role}, decisive {facts.decisive}, presents "
                            f"{facts.presents}")
        edges = ID._build_edges(ev.rows, ev.movements, ev.facts_by_row, parties=ev.parties, fee_account=ev.fee_account)
        r3_edges = [(e.kind, e.basis) for e in edges if e.row == row.index]
        want_edges = [("settle", "reference")] if n == 3 else [("alter", "reference")]
        if r3_edges != want_edges:
            problems.append(f"case {n}: R3's edges are {r3_edges}, not {want_edges}")
        if n in (1, 2):
            print(f"      case {n} first: unique={verdict.unique} readings={verdict.readings} "
                  f"matched={verdict.matched} repairs={[r.kind for r in verdict.repairs]}")
    return check("Cases 1 and 2 first, then all five: check_identifiable over the projected bytes is unique with "
                 "one reading and reads exactly the planted bank-evidenced repairs; R3's row is a decisive, "
                 "presented instrument and its edge stands on the reference", not problems, "\n".join(problems))


def test_the_mechanism_and_its_limits():
    problems = []
    _, world, task, _, inputs, public = case(1)
    ledger = public[ID.LEDGER_FILE]
    if ledger.count('"Customer payment, GR PAYRUN 0428"') != 1:
        problems.append("the fixture expects R3's narration to quote the addendum exactly once")
    # (a) a narration that does not quote the addendum: the alteration falls
    # back to the counterparty basis and the in-transit reading returns
    unquoted = {**public, ID.LEDGER_FILE: ledger.replace('"Customer payment, GR PAYRUN 0428"', '"Customer payment"')}
    verdict = ID.check_identifiable(unquoted, **kw(task))
    if verdict.unique or verdict.readings != 2 or "timing difference" not in verdict.reason:
        problems.append(f"(a) unquoted addendum: unique {verdict.unique}, {verdict.readings} readings: "
                        f"{verdict.reason[:200]}")
    ev, row, _ = r3_facts(unquoted, task)
    edges = ID._build_edges(ev.rows, ev.movements, ev.facts_by_row, parties=ev.parties, fee_account=ev.fee_account)
    if [(e.kind, e.basis) for e in edges if e.row == row.index] != [("alter", "counterparty")]:
        problems.append(f"(a) the unquoted entry's edge is {[(e.kind, e.basis) for e in edges if e.row == row.index]}")
    # (b) a narration naming an invoice instead: the entry names another
    # document, which an instrument row conflicts with — the reading is
    # unique but it is not the planted one, and gate (f) says so
    conflicting = {**public, ID.LEDGER_FILE: ledger.replace('"Customer payment, GR PAYRUN 0428"',
                                                            '"Customer payment for SI-3102"')}
    verdict = ID.check_identifiable(conflicting, **kw(task))
    if verdict.unique and read_keys(verdict) == planted_bank_keys(inputs, public):
        problems.append("(b) an entry naming SI-3102 instead of the addendum was read as the addendum's alteration")
    if any(r.kind == "wrong_amount" for r in verdict.repairs):
        problems.append(f"(b) the conflicting entry founded an alteration: {[str(r) for r in verdict.repairs]}")
    # (c) the addendum printed on a second statement row: not decisive, not
    # presented, and the reading stays open rather than being certified
    reused = with_row(public, "2026-04-29", "ACH IN GANNET RIGGING INC", "GR PAYRUN 0428", "", "100.00")
    ev, row, facts = r3_facts(reused, task)
    if facts.decisive or "GR PAYRUN 0428" in facts.presents or facts.ref_role != ID.REF_INSTRUMENT:
        problems.append(f"(c) a reused addendum is decisive {facts.decisive} / presents {facts.presents}")
    verdict = ID.check_identifiable(reused, **kw(task))
    if verdict.unique:
        problems.append(f"(c) the reused addendum certified the world: {[str(r) for r in verdict.repairs]}")
    # (d) the in-transit refusal names the presented reference; another
    # addendum presents nothing for this entry
    ev, row, facts = r3_facts(public, task)
    r3_entry = next(m for m in ev.movements if m.date == "2026-04-28" and m.payee == GANNET)
    refused = ID._outstanding_eligible(r3_entry, task.period.end, ev.fee_account, [("GR PAYRUN 0428", "2026-04-28")])
    if not refused or "GR PAYRUN 0428" not in refused or "presented" not in refused:
        problems.append(f"(d) the entry quoting the presented addendum was not refused as in transit: {refused!r}")
    if ID._outstanding_eligible(r3_entry, task.period.end, ev.fee_account, [("GR PAYRUN 0410", "2026-04-10")]) is not None:
        problems.append("(d) another addendum refused the entry")
    if ID._outstanding_eligible(r3_entry, task.period.end, ev.fee_account, []) is not None:
        problems.append("(d) with nothing presented the entry near the cut-off is not a timing difference")
    return check("the mechanism and its limits: an unquoted addendum leaves two readings (the join gate (n) "
                 "permits is load-bearing); an entry naming an invoice instead conflicts and is not the planted "
                 "reading; a reused addendum is not decisive, presents nothing and keeps the world ambiguous; the "
                 "in-transit refusal names the presented reference", not problems, "\n".join(problems))


def test_no_shipped_task_prints_a_payment_reference():
    problems = []
    roles: dict = {}
    # The 95 SHIPPED ids, which is `LEGACY_TASK_IDS` now that the family is
    # served out of the same `REGISTRY`: the claim is about the manifested
    # worlds, and the five cases print the payment-reference syntax by
    # design (that is what makes them identifiable).
    for task_id in sorted(LEGACY_TASK_IDS):
        world, task = REGISTRY[task_id]
        _, inputs = derive_contract(world, task)
        public = decoded_public(inputs)
        for name in (ID.STATEMENT_FILE, ID.ARCHIVE_FILE):
            for record in csv.DictReader(io.StringIO(public.get(name, ""))):
                reference = (record.get("reference") or "").strip()
                if ID._payment_reference_words(reference):
                    problems.append(f"{task_id} {name}: {reference!r} reads as a payment reference")
                role = ID.reference_role(reference, f"{record.get('description', '')} {reference}")
                roles[role] = roles.get(role, 0) + 1
    print(f"      reference roles over the 95 legacy tasks' statement and archive rows: {roles}")
    if set(roles) - set(ID.REFERENCE_ROLES):
        problems.append(f"an undeclared role: {roles}")
    return check("no statement or archive row of the 95 shipped tasks prints a multi-word reference: the "
                 "payment-reference syntax reaches no manifested world, which is why IDENTIFY_VERSION stays 7",
                 not problems, "\n".join(problems))


def test_the_write_off_plant_is_validated_through_the_public_fold():
    problems = []
    module, world, task, bundle, inputs, public = case(3)
    where = f"{world.id}/{task.id}"
    golden = inputs.golden_text
    write_off_header = '2026-04-28 * "Gannet Rigging Inc" "Short payment on SI-3104 written off under the cash application policy"'
    if golden.count(write_off_header) != 1:
        problems.append("the fixture expects the spec's write-off entry once in Case 3's expected ledger")

    def gate_m(inputs_, public_=public):
        found, _, covered = _family_gates(world, task, bundle, inputs_, public_, where)
        return [p for p in found if "gate (m)" in p], covered

    # (i) as authored: gate (m) is silent and covers the write-off plant
    found, covered = gate_m(inputs)
    if found or covered != {"omitted_short_payment_write_off"}:
        problems.append(f"(i) Case 3 as authored: {found[:3]} covered {covered}")
    # (ii) the expected entry re-dated: the fold's date is the receipt's
    redated = tampered(inputs, golden_text=golden.replace(write_off_header, write_off_header.replace(
        "2026-04-28 *", "2026-04-29 *")))
    found, covered = gate_m(redated)
    if not any("carries 0 write-off entries" in p for p in found) \
            or not any("does not establish" in p and "2026-04-29" in p for p in found):
        problems.append(f"(ii) a re-dated write-off entry: {found[:3]}")
    # (iii) the expected entry naming the wrong invoice
    misnamed = tampered(inputs, golden_text=golden.replace(write_off_header, write_off_header.replace(
        "SI-3104", "SI-3102")))
    found, covered = gate_m(misnamed)
    if not any("names ['SI-3102'], the public fold writes off ['SI-3104']" in p for p in found):
        problems.append(f"(iii) a write-off entry naming SI-3102: {found[:3]}")
    # (iv) the planted shape is not the fold's: the plant is not established
    # and the fold's write-off is unplanted with the opening ledger lacking it
    plants = []
    for p in inputs.planted:
        if p.id == "omitted_short_payment_write_off":
            p = dataclasses.replace(p, required=((AR, "-40"), (WRITE_OFFS, "40")))
        plants.append(p)
    forty = tampered(inputs, planted=tuple(plants))
    found, covered = gate_m(forty)
    if not any("omitted_short_payment_write_off" in p and "not a write-off the public evidence establishes" in p
               for p in found) or not any("is not planted, yet the opening ledger lacks it" in p for p in found) \
            or covered:
        problems.append(f"(iv) a planted write-off at 40.00: {found[:3]} covered {covered}")
    # (v) a compensating pair that ties closing AR: R3 restated by 20.00 and
    # the write-off booked at 40.00 — the control account agrees, the gate does not
    r3_entry = ('2026-04-28 * "Gannet Rigging Inc" "Customer payment, GR PAYRUN 0428"\n'
                '  Assets:Bank:Checking                      3660.00 USD\n'
                '  Assets:AR                                -3660.00 USD\n')
    write_off_entry = (write_off_header + '\n'
                       '  Expenses:SmallBalanceWriteOffs              20.00 USD\n'
                       '  Assets:AR                                  -20.00 USD\n')
    if golden.count(r3_entry) != 1 or golden.count(write_off_entry) != 1:
        problems.append("the fixture expects R3 at 3660.00 and the write-off at 20.00 once each in the expected ledger")
    compensated = golden.replace(r3_entry, r3_entry.replace("3660.00", "3640.00")) \
                        .replace(write_off_entry, write_off_entry.replace("20.00", "40.00"))
    paired = tampered(inputs, golden_text=compensated)
    found, covered = gate_m(paired)
    if any("closing AR" in p for p in found):
        problems.append(f"(v) the compensating pair moved closing AR; the fixture is wrong: {found[:3]}")
    if not any("carries 0 write-off entries" in p for p in found) \
            or not any("does not establish" in p and "('Expenses:SmallBalanceWriteOffs', '40')" in p for p in found):
        problems.append(f"(v) the compensating pair passed gate (m): {found[:4]}")
    # (vi) the advice edited on the PUBLIC bytes so the claim is above the
    # tolerance: the fold writes nothing off, and the plant, the expected
    # entry and the truth are all held to that
    advice = public["remittance_advice.csv"]
    line = "RA-0428-GR,Gannet Rigging Inc,2026-04-28,ACH,GR PAYRUN 0428,3660.00,SI-3104,1870.00,yes,20.00,freight overcharge"
    if advice.count(line) != 1:
        problems.append("the fixture expects the spec's SI-3104 advice line once")
    edited = {**public, "remittance_advice.csv": advice.replace(line, line.replace("1870.00,yes,20.00", "1790.00,yes,100.00"))}
    if CA.fold(edited, **kw(task)).receipt("2026-04-28:GR PAYRUN 0428").written_off != ():
        problems.append("(vi) the edited advice still writes something off; the fixture is wrong")
    found, covered = gate_m(inputs, edited)
    if not any("omitted_short_payment_write_off" in p and "not a write-off the public evidence establishes" in p
               for p in found) or not any("does not establish" in p and "Short payment on SI-3104" in p for p in found) \
            or not any("public fold and the truth disagree" in p for p in found) or covered:
        problems.append(f"(vi) an advice with no write-off: {found[:4]} covered {covered}")
    # and the whole gate set through check_derived: the tampered inputs of
    # (v) fail the world, the authored ones pass it
    found, _ = check_derived(world, task, bundle, paired, source_path=WORLDS_DIR / "bowline_2026_04_c3.py")
    if not any("gate (m)" in p for p in found):
        problems.append(f"(v) check_derived did not report gate (m): {found[:3]}")
    found, _ = check_derived(world, task, bundle, inputs, source_path=WORLDS_DIR / "bowline_2026_04_c3.py")
    if found:
        problems.append(f"Case 3 as authored fails check_derived: {found[:3]}")
    return check("gate (m) validates the write-off through the public fold on amount, invoice, date, customer and "
                 "shape: Case 3 passes and its plant is covered; a re-dated entry, a wrong invoice, a planted "
                 "40.00, a compensating pair that ties closing AR and an advice with no write-off are refused by "
                 "name", not problems, "\n".join(problems))


def test_every_plant_is_covered_by_an_explicit_validator():
    problems = []
    for n in range(1, 6):
        _, world, task, bundle, inputs, public = case(n)
        found, _ = check_derived(world, task, bundle, inputs)
        if any("covered by no explicit validator" in p for p in found):
            problems.append(f"case {n}: {[p for p in found if 'covered by' in p]}")
        bank = {p.id for p in inputs.planted if any(a == BANK for a, _ in p.required)}
        offs = {p.id for p in inputs.planted if any(a == WRITE_OFFS for a, _ in p.required)}
        if bank | offs != {p.id for p in inputs.planted} or bank & offs:
            problems.append(f"case {n}: plants {[(p.id, p.required) for p in inputs.planted]} are not partitioned "
                            f"into bank-evidenced and write-off")
    # a planted item with no bank leg and no write-off is reported by name
    _, world, task, bundle, inputs, public = case(1)
    plants = []
    for p in inputs.planted:
        if p.id == "unrecorded_customer_check":
            p = dataclasses.replace(p, required=((AR, "-2970"), ("Income:Sales", "2970")))
        plants.append(p)
    stray = tampered(inputs, planted=tuple(plants))
    found, _ = check_derived(world, task, bundle, stray)
    if not any("unrecorded_customer_check" in p and "covered by no explicit validator" in p for p in found):
        problems.append(f"an uncovered plant passed: {found[:4]}")
    # the legacy worlds: every plant bank-evidenced, none uncovered (one
    # world of each kind mix; the whole registry is walked by test_worlds)
    for task_id in ("bank_recon_001", "ap_payment_run_001"):
        world, task = REGISTRY[task_id]
        bundle, inputs = derive_contract(world, task)
        if not all(any(a == world.bank_account for a, _ in p.required) for p in inputs.planted):
            problems.append(f"{task_id}: a legacy plant has no bank leg")
        found, _ = check_derived(world, task, bundle, inputs)
        if any("covered by" in p for p in found):
            problems.append(f"{task_id}: {found[:2]}")
    return check("every plant of the five cases is covered — bank-evidenced by gate (f) or a write-off by gate (m) "
                 "— and a plant that is neither is reported by name; legacy plants are all bank-evidenced",
                 not problems, "\n".join(problems))


def test_verify_world_and_the_world_battery_accept_the_five():
    problems = []

    def run(n):
        module = WORLDS_DIR / f"bowline_2026_04_c{n}.py"
        result = subprocess.run([sys.executable, str(ROOT / "tests" / "verify_world.py"), str(module)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        return n, result

    with ThreadPoolExecutor(max_workers=5) as pool:
        for n, result in pool.map(run, range(1, 6)):
            if result.returncode != 0 or f"PASS  bowline-2026-04-c{n}/cash_application_{n:03d}: no problems" not in result.stdout \
                    or "1 of 1 task(s) clean" not in result.stdout:
                problems.append(f"case {n}: verify_world exit {result.returncode}\n{result.stdout[-800:]}\n{result.stderr[-400:]}")
    source = (ROOT / "tests" / "test_worlds.py").read_text(encoding="utf-8")
    if "CASH_APPLICATION_REGISTRY" not in source or "registered = dict(REGISTRY)" not in source:
        problems.append("tests/test_worlds.py does not walk the family beside the legacy ids")
    # and through the same function the battery calls, with warnings only
    for n in range(1, 6):
        module, world, task, *_ = case(n)
        found, warnings = check_world_task(world, task, source_path=WORLDS_DIR / f"bowline_2026_04_c{n}.py")
        if found or not all(w.startswith("WARN:") for w in warnings):
            problems.append(f"case {n}: {found[:3]} {[w for w in warnings if not w.startswith('WARN:')]}")
    return check("tests/verify_world.py accepts each of the five modules (exit 0, no problems), test_worlds.py holds "
                 "CASH_APPLICATION_REGISTRY to the registry gate, and check_world_task passes all five with "
                 "warnings only", not problems, "\n".join(problems))


TESTS = [
    test_the_payment_reference_is_an_instrument_and_nothing_else_moved,
    test_cases_1_and_2_first_then_all_five_read_uniquely_as_planted,
    test_the_mechanism_and_its_limits,
    test_no_shipped_task_prints_a_payment_reference,
    test_the_write_off_plant_is_validated_through_the_public_fold,
    test_every_plant_is_covered_by_an_explicit_validator,
    test_verify_world_and_the_world_battery_accept_the_five,
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
