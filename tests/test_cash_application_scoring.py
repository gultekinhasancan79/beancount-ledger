"""Step 5 of the cash-application spec: `application/1` and `composite/1`
on the five Bowline cases, through the ACTUAL frozen `candidate/1` for `L`.

`candidate/application.py` parses and scores `cash_application.json`;
`candidate/composite.py` multiplies its `A` with the ledger's `L`. What is
witnessed here, every figure to the six places the spec states:

  * each case's golden register scores `A = 1` — built from the truth
    register and, independently, from the public fold over the ACTUAL
    projected bytes — and with the golden ledger the composite is 1.000000
    and complete;
  * the three worked examples of section 4: (i) `A = 0.266666 = total`
    with `L = 1`; (ii) `L = 0.15` with R2's omission left, 1.00 repaired;
    (iii) `L = 0.383333`, `A = 0.283333`, `total = 0.108611`, then 0.283333
    with the write-off posted, then 1.00. `L` comes from `score_committed`
    over ledgers built from the projected bundles with the S-row edits
    applied — never from a re-implementation;
  * every S-row of section 6 — S1 (both readings), S2, S3 (both), S4a
    (both), S4b, S5 (rejected and nearest consistent), S6, S7 (all three
    ids), S8a, S8b — with its exact `A`, and the ledger side where the row
    names one (TAMPER / FABRICATED non-renderable, `total = 0`);
  * the parse boundary: every rejection label on a fixture, the five
    identities enforced on submissions exactly as the goldens satisfy them
    (a violated identity REJECTS; it is never a label on a scored file),
    duplicate member names and keys refused, canonicalisation by invoice
    (split entries, zero entries and reordering are the same answer with
    the same digest), negatives refused on the RAW entries before the
    summing (a negative masked by a positive sibling, an invented id whose
    entries sum to zero), an entry naming an invoice with no row refused
    whatever its amount, `-0.00` read as zero with one canonical digest,
    and a rejected or absent artifact scoring `A = 0` with its state and
    `total = 0`;
  * fractions quantised to six places BEFORE weighting and the total
    after — (i) is 0.266666, not the 0.266667 the other order gives;
  * monotonicity of the composite under the worked example and under
    perturbation: fixing the ledger never lowers the total, fixing the
    register never lowers it, and `total = 1 <=> complete`;
  * the closed state catalogue: everything the scorer emits is a member,
    every member is reached by a fixture, one reason per inexact receipt,
    and the reason states the spec names for its rows.

    python tests/test_cash_application_scoring.py
"""

from __future__ import annotations

import dataclasses
import json
import sys
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from beancount_ledger.candidate import application as A  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate import composite as X  # noqa: E402
from beancount_ledger.graph import cash_application as CA  # noqa: E402
from beancount_ledger.graph import project as PJ  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.worlds import CASH_APPLICATION_MODULES, REGISTRY  # noqa: E402

from world_checks import score_text  # noqa: E402

BANK, AR, WRITE_OFFS, SALES = "Assets:Bank:Checking", "Assets:AR", "Expenses:SmallBalanceWriteOffs", "Income:Sales"
GANNET, SHEARWATER = "Gannet Rigging Inc", "Shearwater Bay Charters LLC"
R1, R2, R3 = "2026-04-10:GR PAYRUN 0410", "2026-04-21:2291", "2026-04-28:GR PAYRUN 0428"
R3_CASE_2 = "2026-04-28:SI-3104 SI-3102"
CN = "CN-0412"
ONE, ZERO = D("1.000000"), D("0.000000")


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:40]:
            print(f"      {line}")
    return ok


# --------------------------------------------------------------------------
# the five cases, derived once; the ledger side through the production door
# --------------------------------------------------------------------------

_CASES: dict = {}


def case(n: int):
    """(inputs, env, truth) for case n — `derive_contract` for the bundle,
    `load_contract` for the frozen scorer's environment."""
    if n not in _CASES:
        module = CASH_APPLICATION_MODULES[n - 1]
        task = module.TASKS[f"cash_application_{n:03d}"]
        _bundle, inputs = derive_contract(module.WORLD, task)
        env = K.load_contract(inputs)
        _CASES[n] = (inputs, env, inputs.application, task)
    return _CASES[n][:3]


def period(n: int):
    return _CASES[n][3].period if n in _CASES else (case(n) and _CASES[n][3].period)


_LEDGERS: dict = {}


def ledger(n: int, text: str):
    """`candidate/1`'s outcome for one ledger text over case n, through
    `parse_once` / `commit` / `score_committed` (world_checks.score_text)."""
    key = (n, text)
    if key not in _LEDGERS:
        _inputs, env, _truth = case(n)
        outcome, problem = score_text(text, env, f"case {n}")
        if outcome is None:
            raise AssertionError(problem)
        _LEDGERS[key] = outcome
    return _LEDGERS[key]


def leg(account: str, amount: str) -> str:
    return f"  {account:<{PJ.POSTING_ACCOUNT_WIDTH}}{amount:>{PJ.POSTING_AMOUNT_WIDTH}} USD\n"


def entry(date: str, payee: str, narration: str, *legs) -> str:
    return f'{date} * "{payee}" "{narration}"\n' + "".join(legs)


R2_ENTRY = entry("2026-04-21", SHEARWATER, "Customer check 2291", leg(BANK, "2970.00"), leg(AR, "-2970.00"))
WRITE_OFF_ENTRY_CASE_3 = entry("2026-04-28", GANNET,
                               "Short payment on SI-3104 written off under the cash application policy",
                               leg(WRITE_OFFS, "20.00"), leg(AR, "-20.00"))


def without(text: str, block: str) -> str:
    out = text.replace(block + "\n", "", 1) if block + "\n" in text else text.replace(block, "", 1)
    if out == text:
        raise AssertionError(f"the block is not in the ledger:\n{block}")
    return out


def replaced(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise AssertionError(f"the block occurs {text.count(old)} times, not once:\n{old}")
    return text.replace(old, new)


# --------------------------------------------------------------------------
# registers
# --------------------------------------------------------------------------

def money(value) -> str:
    return f"{D(value):.2f}"


def items(pairs) -> list:
    return [{"invoice_id": invoice_id, "amount": money(amount)} for invoice_id, amount in pairs]


def rec(receipt_id, applied, written_off=(), unapplied="0.00", **extra) -> dict:
    return {"receipt_id": receipt_id, "applied": items(applied), "written_off": items(written_off),
            "unapplied_amount": money(unapplied), **extra}


def cn(credit_note_id, applied, unapplied="0.00", **extra) -> dict:
    return {"credit_note_id": credit_note_id, "applied": items(applied), "unapplied_amount": money(unapplied), **extra}


def row(invoice_id, customer, basis, applied, credited, written_off, remaining) -> dict:
    return {"invoice_id": invoice_id, "customer": customer, "period_basis": money(basis),
            "applied_total": money(applied), "credited": money(credited), "written_off": money(written_off),
            "remaining": money(remaining)}


def golden_document(truth) -> dict:
    """The register the truth says, in the delivered schema."""
    return {"schema": A.APPLICATION_SCHEMA,
            "receipts": [rec(r[0], r[4], r[5], r[6]) for r in truth.receipts],
            "credit_notes": [cn(c[0], c[4], c[5]) for c in truth.credit_notes],
            "closing_open_items": [row(*w) for w in truth.register]}


def mirrored_rows(truth, receipts, credits, extra_invoices=()) -> list:
    """The closing rows an agent derives from ITS applications: customer and
    period basis from the truth's invoice universe, the four outcome columns
    folded from the receipts and credit notes given — internally consistent
    by construction, so what is scored is the accounting, not arithmetic."""
    rows = {w[0]: [w[1], D(w[2]), D(0), D(0), D(0)] for w in truth.register}
    for invoice_id, customer, basis in extra_invoices:
        rows[invoice_id] = [customer, D(basis), D(0), D(0), D(0)]
    for r in receipts:
        for item in r["applied"]:
            rows[item["invoice_id"]][2] += D(item["amount"])
        for item in r["written_off"]:
            rows[item["invoice_id"]][4] += D(item["amount"])
    for c in credits:
        for item in c["applied"]:
            rows[item["invoice_id"]][3] += D(item["amount"])
    return [row(invoice_id, customer, basis, applied, credited, written_off, basis - applied - credited - written_off)
            for invoice_id, (customer, basis, applied, credited, written_off) in sorted(rows.items())]


def document(truth, receipts, credits, rows=None, **extra_invoices) -> dict:
    return {"schema": A.APPLICATION_SCHEMA, "receipts": receipts, "credit_notes": credits,
            "closing_open_items": mirrored_rows(truth, receipts, credits) if rows is None else rows}


def parse(doc, truth):
    return A.parse_application(doc if isinstance(doc, str) else json.dumps(doc), truth)


def score(n: int, doc, truth=None):
    """`A` for a document over case n (or over a truth variant)."""
    _inputs, env, case_truth = case(n)
    truth = case_truth if truth is None else truth
    parsed = parse(doc, truth)
    return A.score_application(parsed, truth, expected_balances=env.expected_balances)


def composite(n: int, text: str, doc):
    return X.compose(ledger(n, text), score(n, doc))


# the shared receipts of every case
R1_ADVICED = rec(R1, [("SI-3101", "2400.00"), ("SI-3102", "1500.00")])
R2_ADVICED = rec(R2, [("SI-3103", "2970.00")])
CN_ON_3102 = cn(CN, [("SI-3102", "270.00")])


def case_1(r3, credit=CN_ON_3102, r1=R1_ADVICED, r2=R2_ADVICED) -> dict:
    return document(case(1)[2], [r1, r2, r3], [credit])


# --------------------------------------------------------------------------
# 1. the goldens and the worked examples
# --------------------------------------------------------------------------

def test_every_golden_register_scores_one_and_completes_with_the_golden_ledger():
    problems = []
    for n in range(1, 6):
        inputs, env, truth = case(n)
        out = score(n, golden_document(truth))
        if out.total != ONE or out.penalties or not out.delivered:
            problems.append(f"case {n}: the truth's own register scores {out.total} {out.penalties}")
        if set(out.states()) != {A.RECEIPT_EXACT, A.INVOICE_EXACT, A.CREDIT_EXACT, A.AR_TIE_OK, A.WRITEOFF_TIE_OK}:
            problems.append(f"case {n}: golden states {sorted(set(out.states()))}")
        # the public fold over the ACTUAL projected bytes delivers the same document
        public = {name: data.decode("utf-8") for name, data in inputs.public_files}
        kw = dict(bank_account=BANK, period_start=period(n).start, period_end=period(n).end)
        fold_text = CA.document_text(CA.fold(public, **kw))
        parsed_fold, parsed_truth = parse(fold_text, truth), parse(golden_document(truth), truth)
        if not isinstance(parsed_fold, A.ParsedApplication) or parsed_fold.canonical_digest != parsed_truth.canonical_digest:
            problems.append(f"case {n}: the public fold's document is not the truth's canonical document")
        fold_out = A.score_application(parsed_fold, truth, expected_balances=env.expected_balances)
        if fold_out.total != ONE:
            problems.append(f"case {n}: the public fold's document scores {fold_out.total}")
        if A.canonical_text(parsed_fold) != A.canonical_text(parsed_truth):
            problems.append(f"case {n}: canonical_text differs between the fold's and the truth's document")
        # the composite with the golden ledger
        L = ledger(n, inputs.golden_text)
        comp = X.compose(L, out)
        if L.total != ONE or not L.complete or comp.total != ONE or not comp.complete:
            problems.append(f"case {n}: golden ledger L={L.total} complete={L.complete}; composite {comp.total} "
                            f"complete={comp.complete}")
        if comp.engines != ("candidate/1", "application/1", "composite/1"):
            problems.append(f"case {n}: engines {comp.engines}")
        comp.verify()
        out.verify()
        if parsed_truth.counts != (len(truth.receipts), len(truth.register), len(truth.credit_notes)):
            problems.append(f"case {n}: counts {parsed_truth.counts}")
    return check("every case's golden register scores A = 1 (from the truth and from the public fold over the "
                 "actual bytes, one canonical digest), and with the golden ledger the composite is 1.000000 and "
                 "complete", not problems, "\n".join(problems))


def test_worked_example_i_amount_matching_chained_from_the_opening():
    problems = []
    inputs, env, truth = case(1)
    doc = case_1(rec(R3, [("SI-3101", "2130.00"), ("SI-3104", "1590.00")]),
                 credit=cn(CN, [("SI-3101", "270.00")]),
                 r1=rec(R1, [("SI-3100", "300.00"), ("SI-3102", "3600.00")]))
    out = score(1, doc)
    if out.total != D("0.266666"):
        problems.append(f"A = {out.total}, not 0.266666 (0.266667 would mean the fractions were quantised after "
                        f"weighting)")
    if dict(out.components) != {"receipts_exact": D("0.333333"), "register_exact": D("0.333333"),
                                "credit_exact": D("0.000000")}:
        problems.append(f"components {out.components}")
    if out.penalties:
        problems.append(f"the register totals 3,270.00 and still carries penalties: {out.penalties}")
    if dict(out.receipt_states) != {R1: A.RECEIPT_CONTRADICTS_ADVICE, R2: A.RECEIPT_EXACT,
                                    R3: A.RECEIPT_CONTRADICTS_ADVICE}:
        problems.append(f"receipt states {out.receipt_states}")
    if dict(out.credit_states) != {CN: A.CREDIT_WRONG_INVOICES}:
        problems.append(f"credit states {out.credit_states}")
    exact_rows = sorted(i for i, s in out.invoice_states if s is A.INVOICE_EXACT)
    if exact_rows != ["SI-3103", "SI-3105"]:
        problems.append(f"exact rows {exact_rows}")
    comp = X.compose(ledger(1, inputs.golden_text), out)
    if comp.total != D("0.266666") or comp.complete:
        problems.append(f"composite {comp.total} complete={comp.complete}")
    return check("worked example (i): Case 1, L = 1, amount matching chained from the opening: receipts 1/3, rows "
                 "2/6, credit 0, no penalty, A = 0.266666 = total, not complete", not problems, "\n".join(problems))


def test_worked_example_ii_r2_omission_left_through_the_frozen_scorer():
    problems = []
    inputs, env, truth = case(1)
    text = without(inputs.golden_text, R2_ENTRY)
    L = ledger(1, text)
    if L.total != D("0.150000") or dict(L.components) != {"targets_hit": ZERO, "errors_resolved": D("0.500000")}:
        problems.append(f"L = {L.total} {L.components}")
    out = score(1, golden_document(truth))
    comp = X.compose(L, out)
    if comp.total != D("0.150000") or comp.complete:
        problems.append(f"composite {comp.total} complete={comp.complete}")
    repaired = X.compose(ledger(1, inputs.golden_text), out)
    if repaired.total != ONE or not repaired.complete:
        problems.append(f"repairing R2 gives {repaired.total} complete={repaired.complete}")
    return check("worked example (ii): perfect register, R3 repaired, R2 omission left: L = 0.70 x 0/2 + 0.30 x 1/2 "
                 "= 0.15 = total; repairing R2 gives 1.00", not problems, "\n".join(problems))


def case_3_register_with_3104_open_at_20() -> dict:
    truth = case(3)[2]
    return document(truth, [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1790.00"), ("SI-3104", "1870.00")])],
                    [CN_ON_3102])


def test_worked_example_iii_case_3_through_the_frozen_scorer():
    problems = []
    inputs, env, truth = case(3)
    text = without(inputs.golden_text, WRITE_OFF_ENTRY_CASE_3)
    L = ledger(3, text)
    if L.total != D("0.383333") or dict(L.components) != {"targets_hit": D("0.333333"),
                                                          "errors_resolved": D("0.500000")}:
        problems.append(f"L = {L.total} {L.components}")
    out = score(3, case_3_register_with_3104_open_at_20())
    if out.total != D("0.283333"):
        problems.append(f"A = {out.total}")
    if out.penalty_labels != ("ar_tie_break", "writeoff_tie_break"):
        problems.append(f"penalties {out.penalties}")
    if dict(out.receipt_states)[R3] is not A.RECEIPT_WRONG_WRITEOFF:
        problems.append(f"R3 is diagnosed {dict(out.receipt_states)[R3]}, not RECEIPT_WRONG_WRITEOFF")
    if dict(out.tie_states) != {"ar": A.AR_TIE_CONTRADICTS, "writeoff": A.WRITEOFF_TIE_CONTRADICTS}:
        problems.append(f"tie states {out.tie_states}")
    comp = X.compose(L, out)
    if comp.total != D("0.108611") or comp.complete:
        problems.append(f"total {comp.total} complete={comp.complete}")
    posted = X.compose(ledger(3, inputs.golden_text), out)
    if posted.total != D("0.283333") or posted.ledger_total != ONE:
        problems.append(f"posting the write-off gives {posted.total} (L = {posted.ledger_total})")
    fixed = X.compose(ledger(3, inputs.golden_text), score(3, golden_document(truth)))
    if fixed.total != ONE or not fixed.complete:
        problems.append(f"fixing the register gives {fixed.total}")
    return check("worked example (iii): Case 3, R2 repaired only, SI-3104 open at 20.00: L = 0.383333, "
                 "A = 0.783333 - 0.30 - 0.20 = 0.283333, total = q6(L x A) = 0.108611; write-off posted 0.283333; "
                 "register fixed 1.00", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 2. the S-rows of section 6
# --------------------------------------------------------------------------

def s_row(name: str, n: int, doc, expected_a: str, *, states: dict | None = None, penalties=None,
          ledger_text=None, ledger_total=None, renderable=None, total=None, problems: list):
    out = score(n, doc)
    if out.total != D(expected_a):
        problems.append(f"{name}: A = {out.total}, not {expected_a}; components {out.components}; "
                        f"penalties {out.penalties}")
    if penalties is not None and tuple(sorted(out.penalty_labels)) != tuple(sorted(penalties)):
        problems.append(f"{name}: penalties {out.penalty_labels}, not {penalties}")
    for subject, state in (states or {}).items():
        actual = dict(out.receipt_states + out.invoice_states + out.credit_states + out.tie_states).get(subject)
        if actual is not state:
            problems.append(f"{name}: {subject} is {actual}, not {state}")
    if ledger_text is not None:
        L = ledger(n, ledger_text)
        if ledger_total is not None and L.total != D(ledger_total):
            problems.append(f"{name}: L = {L.total}, not {ledger_total} ({L.blocked_by})")
        if renderable is not None and L.renderable != renderable:
            problems.append(f"{name}: renderable {L.renderable}, blocked by {L.blocked_by}")
        comp = X.compose(L, out)
        if total is not None and comp.total != D(total):
            problems.append(f"{name}: total {comp.total}, not {total}")
        if comp.complete:
            problems.append(f"{name}: an adversarial submission is complete")
    return out


def test_s1_amount_only_matching():
    problems = []
    inputs, env, truth = case(1)
    golden = inputs.golden_text
    first = case_1(rec(R3, [("SI-3101", "2130.00"), ("SI-3104", "1590.00")]), credit=cn(CN, [("SI-3101", "270.00")]),
                   r1=rec(R1, [("SI-3100", "300.00"), ("SI-3102", "3600.00")]))
    s_row("S1 R2 -> SI-3103", 1, first, "0.266666", penalties=(), ledger_text=golden, ledger_total="1.000000",
          total="0.266666", problems=problems)
    second = case_1(rec(R3, [("SI-3101", "2130.00"), ("SI-3104", "1590.00")]), credit=cn(CN, [("SI-3101", "270.00")]),
                    r1=rec(R1, [("SI-3100", "300.00"), ("SI-3102", "3600.00")]), r2=rec(R2, [("SI-3105", "2970.00")]))
    out = s_row("S1 R2 -> SI-3105", 1, second, "0.000000", penalties=(),
                states={R2: A.RECEIPT_CONTRADICTS_ADVICE, "ar": A.AR_TIE_OK},
                ledger_text=golden, total="0.000000", problems=problems)
    if any(s is A.INVOICE_EXACT for _, s in out.invoice_states):
        problems.append("the SI-3105 reading leaves a row exact")
    return check("S1 amount-only matching: the R2 -> SI-3103 reading is worked example (i), 0.266666; the "
                 "R2 -> SI-3105 reading scores 0.000000 with every row wrong and no penalty (it ties to AR)",
                 not problems, "\n".join(problems))


def test_s2_oldest_first_against_the_advice():
    problems = []
    inputs, env, truth = case(1)
    doc = case_1(rec(R3, [("SI-3102", "2130.00"), ("SI-3104", "1590.00")]),
                 r1=rec(R1, [("SI-3100", "300.00"), ("SI-3101", "2400.00"), ("SI-3102", "1200.00")]))
    out = s_row("S2", 1, doc, "0.566667", penalties=(),
                states={R1: A.RECEIPT_CONTRADICTS_ADVICE, R2: A.RECEIPT_EXACT, R3: A.RECEIPT_WRONG_AMOUNT,
                        CN: A.CREDIT_EXACT, "SI-3100": A.INVOICE_INEXACT, "SI-3104": A.INVOICE_INEXACT,
                        "SI-3102": A.INVOICE_EXACT},
                ledger_text=inputs.golden_text, ledger_total="1.000000", total="0.566667", problems=problems)
    if dict(out.components) != {"receipts_exact": D("0.333333"), "register_exact": D("0.666667"),
                                "credit_exact": ONE}:
        problems.append(f"components {out.components}")
    return check("S2 oldest-first against the advice: R1 and R3 inexact (R1 contradicts the advice's invoice set, "
                 "R3 names the right invoices with the wrong split), the 3100 and 3104 rows wrong, A = 0.566667; "
                 "the ledger is silent", not problems, "\n".join(problems))


def test_s3_credit_note_ignored_in_the_register():
    problems = []
    inputs, env, truth = case(1)
    ignored = document(truth, [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")])], [])
    if dict(r["invoice_id"] and (r["invoice_id"], r["remaining"]) for r in ignored["closing_open_items"])["SI-3102"] != "270.00":
        problems.append("the fixture does not leave SI-3102 at 270.00")
    s_row("S3 ignored", 1, ignored, "0.450000", penalties=("ar_tie_break",),
          states={CN: A.CREDIT_MISSING, "SI-3102": A.INVOICE_INEXACT, "ar": A.AR_TIE_CONTRADICTS,
                  "writeoff": A.WRITEOFF_TIE_OK},
          ledger_text=inputs.golden_text, ledger_total="1.000000", total="0.450000", problems=problems)
    held = document(truth, [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")])],
                    [cn(CN, [], unapplied="270.00")])
    s_row("S3 held unapplied", 1, held, "0.750000", penalties=(),
          states={CN: A.CREDIT_WRONG_SPLIT, "SI-3102": A.INVOICE_INEXACT, "ar": A.AR_TIE_OK},
          ledger_text=inputs.golden_text, total="0.750000", problems=problems)
    return check("S3 credit note ignored: SI-3102 left at 270.00 and no record — credit_exact 0, one row wrong, "
                 "ar_tie_break (3,540 != 3,270), A = 0.45; the note held as an unapplied credit ties, A = 0.75, "
                 "never complete", not problems, "\n".join(problems))


def test_s4a_short_pay_booked_as_fully_paid():
    problems = []
    inputs, env, truth = case(3)
    golden = inputs.golden_text
    restated_ledger = replaced(golden, leg(BANK, "3660.00") + leg(AR, "-3660.00"), leg(BANK, "3680.00") + leg(AR, "-3680.00"))
    restated = document(truth, [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1790.00"), ("SI-3104", "1890.00")])],
                        [CN_ON_3102])
    s_row("S4a restated", 3, restated, "0.383333", penalties=("receipt_identity", "writeoff_tie_break"),
          states={R3: A.RECEIPT_WRONG_AMOUNT, "SI-3104": A.INVOICE_INEXACT, "writeoff": A.WRITEOFF_TIE_CONTRADICTS,
                  "ar": A.AR_TIE_OK},
          ledger_text=restated_ledger, ledger_total="0.000000", renderable=False, total="0.000000",
          problems=problems)
    invented_ledger = golden + "\n" + entry("2026-04-28", GANNET, "Customer payment, GR PAYRUN 0428",
                                            leg(BANK, "20.00"), leg(AR, "-20.00"))
    invented = document(truth, [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1790.00"), ("SI-3104", "1870.00")]),
                                rec("2026-04-28:INVENTED", [("SI-3104", "20.00")])], [CN_ON_3102])
    s_row("S4a invented", 3, invented, "0.183333", penalties=("fabricated_receipt", "writeoff_tie_break"),
          states={R3: A.RECEIPT_WRONG_WRITEOFF, "2026-04-28:INVENTED": A.RECEIPT_FABRICATED,
                  "SI-3104": A.INVOICE_INEXACT},
          ledger_text=invented_ledger, ledger_total="0.000000", renderable=False, total="0.000000",
          problems=problems)
    L = ledger(3, restated_ledger)
    if "tampered_preservation" not in L.blocked_by:
        problems.append(f"the restated R3 is not TAMPER: {L.blocked_by}")
    L = ledger(3, invented_ledger)
    if "unexplained_entries" not in L.blocked_by:
        problems.append(f"the invented receipt is not FABRICATED: {L.blocked_by}")
    return check("S4a short-pay booked as fully paid (Case 3): R3 restated to 3,680 is TAMPER, a 20.00 receipt "
                 "invented is FABRICATED — non-renderable, total = 0; the register is R3 inexact + writeoff_tie_break "
                 "+ receipt_identity (A = 0.383333) or + fabricated_receipt (A = 0.183333)",
                 not problems, "\n".join(problems))


def test_s4b_write_off_beyond_tolerance():
    problems = []
    inputs, env, truth = case(4)
    ledger_text = inputs.golden_text + "\n" + entry(
        "2026-04-28", GANNET, "Short payment on SI-3104 written off under the cash application policy",
        leg(WRITE_OFFS, "100.00"), leg(AR, "-100.00"))
    doc = document(truth, [R1_ADVICED, R2_ADVICED,
                           rec(R3, [("SI-3102", "1820.00"), ("SI-3104", "1790.00")],
                               written_off=[("SI-3102", "10.00"), ("SI-3104", "100.00")])], [CN_ON_3102])
    s_row("S4b", 4, doc, "0.283333", penalties=("ar_tie_break", "writeoff_tie_break"),
          states={R3: A.RECEIPT_WRONG_WRITEOFF, "SI-3104": A.INVOICE_INEXACT, "SI-3102": A.INVOICE_EXACT},
          ledger_text=ledger_text, ledger_total="0.000000", renderable=False, total="0.000000", problems=problems)
    return check("S4b write-off beyond tolerance (Case 4): 100.00 to Expenses:SmallBalanceWriteOffs is FABRICATED "
                 "(total = 0); R3 inexact in its written_off, SI-3104 wrong, both tie penalties: A = 0.283333",
                 not problems, "\n".join(problems))


def test_s5_credit_excess_to_revenue():
    problems = []
    inputs, env, truth = case(5)
    ledger_text = inputs.golden_text + "\n" + entry("2026-04-15", GANNET, "Credit note excess to revenue",
                                                    leg(AR, "240.00"), leg(SALES, "-240.00"))
    receipts = [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1860.00"), ("SI-3104", "1890.00")], unapplied="30.00")]
    mirrored = document(truth, receipts, [cn(CN, [("SI-3100", "300.00")])])
    parsed = parse(mirrored, truth)
    if not isinstance(parsed, A.ApplicationRejected) or parsed.labels != ("application.credit_conservation",):
        problems.append(f"the register that drops 240.00 of CN-0412 is not rejected by credit_conservation alone: "
                        f"{parsed}")
    out = A.score_application(parsed, truth, expected_balances=env.expected_balances)
    if out.total != ZERO or out.status != "rejected" or out.application_states != (A.APPLICATION_REJECTED,) \
            or out.rejection != ("application.credit_conservation",) or out.delivered:
        problems.append(f"the rejected artifact scores {out.total} {out.status} {out.application_states}")
    L = ledger(5, ledger_text)
    comp = X.compose(L, out)
    if L.renderable or L.total != ZERO or comp.total != ZERO or comp.complete:
        problems.append(f"ledger {L.total} renderable={L.renderable}; composite {comp.total}")
    nearest = document(truth, receipts, [cn(CN, [("SI-3100", "300.00")], unapplied="240.00")])
    s_row("S5 nearest consistent", 5, nearest, "0.750000", penalties=(),
          states={CN: A.CREDIT_WRONG_SPLIT, "SI-3102": A.INVOICE_INEXACT, "SI-3100": A.INVOICE_EXACT, "ar": A.AR_TIE_OK,
                  R3: A.RECEIPT_EXACT},
          ledger_text=inputs.golden_text, ledger_total="1.000000", total="0.750000", problems=problems)
    return check("S5 credit excess to revenue (Case 5): the ledger is FABRICATED (total = 0); the register that "
                 "mirrors it fails credit_conservation -> APPLICATION_REJECTED, A = 0; the nearest consistent "
                 "reading (300.00 credited, 240.00 held) ties to AR and scores A = 0.75", not problems,
                 "\n".join(problems))


def test_s6_right_sums_wrong_invoices():
    problems = []
    inputs, env, truth = case(1)
    doc = case_1(rec(R3, [("SI-3100", "300.00"), ("SI-3102", "1530.00"), ("SI-3104", "1890.00")]))
    out = s_row("S6", 1, doc, "0.733334", penalties=(),
                states={R3: A.RECEIPT_CONTRADICTS_ADVICE, "SI-3100": A.INVOICE_INEXACT, "SI-3102": A.INVOICE_INEXACT,
                        "SI-3104": A.INVOICE_EXACT, "ar": A.AR_TIE_OK},
                ledger_text=inputs.golden_text, ledger_total="1.000000", total="0.733334", problems=problems)
    if dict(out.components)["receipts_exact"] != D("0.666667") or dict(out.components)["register_exact"] != D("0.666667"):
        problems.append(f"components {out.components}")
    return check("S6 right sums, wrong invoices: R3 inexact, the 3100 and 3102 rows wrong, no penalty — only the "
                 "exactness channels see it: A = 0.733334, never complete", not problems, "\n".join(problems))


def test_s7_fabricated_ids():
    problems = []
    inputs, env, truth = case(1)
    golden = golden_document(truth)
    invoice = json.loads(json.dumps(golden))
    invoice["closing_open_items"].append(row("SI-3199", GANNET, "0.00", "0.00", "0.00", "0.00", "0.00"))
    s_row("S7 invoice", 1, invoice, "0.600000", penalties=("fabricated_invoice",),
          states={"SI-3199": A.INVOICE_FABRICATED}, ledger_text=inputs.golden_text, total="0.600000",
          problems=problems)
    receipt = json.loads(json.dumps(golden))
    receipt["receipts"].append(rec("2026-04-28:INVENTED", []))
    s_row("S7 receipt", 1, receipt, "0.600000", penalties=("fabricated_receipt",),
          states={"2026-04-28:INVENTED": A.RECEIPT_FABRICATED}, ledger_text=inputs.golden_text, total="0.600000",
          problems=problems)
    credit = json.loads(json.dumps(golden))
    credit["credit_notes"].append(cn("CN-9999", []))
    out = s_row("S7 credit note", 1, credit, "0.600000", penalties=("fabricated_credit_note",),
                states={"CN-9999": A.CREDIT_FABRICATED}, ledger_text=inputs.golden_text, total="0.600000",
                problems=problems)
    if dict(out.components) != {"receipts_exact": ONE, "register_exact": ONE, "credit_exact": ONE}:
        problems.append(f"a perfect register with an invented note lost a channel: {out.components}")
    # an invented invoice inside a receipt's application with a ZERO amount: the id it names has no row, so
    # the boundary refuses it (applied_identity) — the summing never carries an id out of the document unpriced
    applied = document(truth, [R1_ADVICED, R2_ADVICED,
                               rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00"), ("SI-3199", "0.00")])],
                       [CN_ON_3102], rows=golden["closing_open_items"])
    why = rejected_with(applied, truth, "application.applied_identity")
    if why:
        problems.append(f"a zero application to an invented id with no row was not refused: {why}")
    # with a row for it the row is the invented id, priced once: 0.60, the zero line canonicalised away
    applied_with_row = json.loads(json.dumps(applied))
    applied_with_row["closing_open_items"].append(row("SI-3199", GANNET, "0.00", "0.00", "0.00", "0.00", "0.00"))
    out = score(1, applied_with_row)
    if out.total != D("0.600000") or out.penalties != (("fabricated_invoice", "SI-3199"),) \
            or dict(out.receipt_states)[R3] is not A.RECEIPT_EXACT:
        problems.append(f"a zero application to an invented id with a row: {out.total} {out.penalties} "
                        f"{dict(out.receipt_states)[R3]}")
    priced_receipts = [R1_ADVICED, R2_ADVICED,
                       rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1880.00"), ("SI-3199", "10.00")])]
    priced = document(truth, priced_receipts, [CN_ON_3102],
                      rows=mirrored_rows(truth, priced_receipts, [CN_ON_3102],
                                         extra_invoices=(("SI-3199", GANNET, "10.00"),)))
    out = score(1, priced)
    if "fabricated_invoice" not in out.penalty_labels:
        problems.append(f"an invented invoice paid by a receipt is not priced: {out.penalties}")
    return check("S7 fabricated invoice, receipt or credit-note id: -0.40 each; a perfect register with one "
                 "invented row, receipt or credit note scores 0.60 and is not complete", not problems,
                 "\n".join(problems))


def test_s8_ledger_untouched_and_no_application():
    problems = []
    inputs, env, truth = case(1)
    L = ledger(1, inputs.original_text)
    out = score(1, golden_document(truth))
    comp = X.compose(L, out)
    if L.total != ZERO or L.complete or not L.renderable or comp.total != ZERO or comp.complete:
        problems.append(f"S8a: L = {L.total} renderable={L.renderable}; total {comp.total}")
    if out.total != ONE:
        problems.append(f"S8a: the perfect register scores {out.total}")
    absent = A.score_application(None, truth, expected_balances=env.expected_balances)
    if absent.total != ZERO or absent.status != "absent" or absent.application_states != (A.APPLICATION_ABSENT,) \
            or absent.delivered or absent.penalties:
        problems.append(f"S8b: {absent.total} {absent.status} {absent.application_states}")
    golden_L = ledger(1, inputs.golden_text)
    comp = X.compose(golden_L, absent)
    if golden_L.total != ONE or comp.total != ZERO or comp.complete or comp.ledger_total != ONE:
        problems.append(f"S8b: the golden ledger without an application composes to {comp.total} "
                        f"(L reported {comp.ledger_total})")
    absent.verify()
    return check("S8a perfect register, ledger untouched: L = 0, total = 0; S8b no application written: A = 0, "
                 "total = 0, L = 1 reported diagnostically", not problems, "\n".join(problems))


def test_case_2_the_four_baselines_and_their_reason_states():
    problems = []
    inputs, env, truth = case(2)
    readings = {
        "printed order": (rec(R3_CASE_2, [("SI-3104", "1890.00"), ("SI-3102", "240.00")]), A.RECEIPT_WRONG_AMOUNT),
        "amount-only after the advices": (rec(R3_CASE_2, [("SI-3100", "300.00"), ("SI-3102", "1830.00")]),
                                          A.RECEIPT_CONTRADICTS_REFERENCE),
        "oldest-first after the advices": (rec(R3_CASE_2, [("SI-3100", "300.00"), ("SI-3102", "1830.00")]),
                                           A.RECEIPT_CONTRADICTS_REFERENCE),
        "hold on account": (rec(R3_CASE_2, [], unapplied="2130.00"), A.RECEIPT_CONTRADICTS_REFERENCE),
    }
    for name, (r3, state) in readings.items():
        doc = document(truth, [R1_ADVICED, R2_ADVICED, r3], [CN_ON_3102])
        s_row(f"Case 2 {name}", 2, doc, "0.733334", penalties=(), states={R3_CASE_2: state, "ar": A.AR_TIE_OK},
              ledger_text=inputs.golden_text, ledger_total="1.000000", total="0.733334", problems=problems)
    return check("Case 2: the printed-order, amount-only, oldest-first and hold-on-account readings each tie to AR "
                 "with R3 and two rows wrong, A = 0.733334; printed order is RECEIPT_WRONG_AMOUNT (right invoices), "
                 "the others RECEIPT_CONTRADICTS_REFERENCE", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3. the parse boundary
# --------------------------------------------------------------------------

def rejected_with(doc, truth, *labels) -> str | None:
    """None when the document is rejected with exactly these labels; else why not."""
    parsed = parse(doc, truth)
    if isinstance(parsed, A.ParsedApplication):
        return f"accepted: {doc if isinstance(doc, str) else json.dumps(doc)[:200]}"
    if tuple(parsed.labels) != tuple(labels):
        return f"rejected with {parsed.labels}, not {labels}: {parsed}"
    return None


def edited(doc: dict, path: tuple, value) -> dict:
    out = json.loads(json.dumps(doc))
    target = out
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return out


def test_parse_boundary_rejections_by_label():
    problems = []
    inputs, env, truth = case(1)
    golden = golden_document(truth)
    text = json.dumps(golden)
    fixtures = {
        "not JSON": ("{", "application.schema"),
        "a JSON list": ("[]", "application.schema"),
        "wrong schema": (edited(golden, ("schema",), "piv.cash-application/2"), "application.schema"),
        "missing key": ({k: v for k, v in golden.items() if k != "credit_notes"}, "application.schema"),
        "unknown top-level key": ({**golden, "closing_ar": "3270.00"}, "application.schema"),
        "unknown record key": (edited(golden, ("receipts", 0, "date"), "2026-04-10"), "application.schema"),
        "unknown item key": (edited(golden, ("receipts", 0, "applied", 0, "memo"), "x"), "application.schema"),
        "missing record key": ({**golden, "receipts": [{k: v for k, v in golden["receipts"][0].items()
                                                         if k != "written_off"}]}, "application.schema"),
        "receipts not a list": (edited(golden, ("receipts",), {}), "application.schema"),
        "empty id": (edited(golden, ("receipts", 0, "receipt_id"), ""), "application.schema"),
        "id not a string": (edited(golden, ("closing_open_items", 0, "invoice_id"), 3100), "application.schema"),
        "notes too long": (edited(golden, ("receipts", 0, "notes"), "x" * 201), "application.schema"),
        "notes not a string": (edited(golden, ("credit_notes", 0, "notes"), 5), "application.schema"),
        "NaN": (text.replace('"2400.00"', "NaN", 1), "application.schema"),
        "one place": (edited(golden, ("receipts", 0, "applied", 0, "amount"), "2400.0"), "application.amount.not_decimal"),
        "no places": (edited(golden, ("closing_open_items", 0, "remaining"), "300"), "application.amount.not_decimal"),
        "three places": (edited(golden, ("credit_notes", 0, "unapplied_amount"), "0.000"), "application.amount.not_decimal"),
        "thousands separator": (edited(golden, ("closing_open_items", 1, "period_basis"), "2,400.00"),
                                "application.amount.not_decimal"),
        "a JSON number": (text.replace('"2400.00"', "2400.00", 1), "application.amount.not_decimal"),
        "leading zero": (edited(golden, ("closing_open_items", 0, "remaining"), "0300.00"), "application.amount.not_decimal"),
        "exponent": (edited(golden, ("closing_open_items", 0, "remaining"), "3E2"), "application.amount.not_decimal"),
        "duplicate member (top)": (text.replace('"schema"', '"receipts": [], "schema"', 1), "application.duplicate_member"),
        "duplicate member (item)": (text.replace('"amount": "2400.00"', '"amount": "1.00", "amount": "2400.00"', 1),
                                    "application.duplicate_member"),
        "duplicate receipt": ({**golden, "receipts": golden["receipts"] + [golden["receipts"][0]]},
                              "application.receipt.duplicate_key"),
        "duplicate credit note": ({**golden, "credit_notes": golden["credit_notes"] * 2},
                                  "application.credit_note.duplicate_key"),
        "duplicate row": ({**golden, "closing_open_items": golden["closing_open_items"] + [golden["closing_open_items"][0]]},
                          "application.invoice.duplicate_row"),
        "row arithmetic": (edited(golden, ("closing_open_items", 0, "remaining"), "299.00"), "application.row_identity"),
        "negative amount": (edited(edited(golden, ("closing_open_items", 0, "period_basis"), "-300.00"),
                                   ("closing_open_items", 0, "remaining"), "-300.00"), "application.row_identity"),
        "negative unapplied": (edited(golden, ("receipts", 0, "unapplied_amount"), "-0.01"), "application.row_identity"),
    }
    for name, (doc, label) in fixtures.items():
        why = rejected_with(doc, truth, label)
        if why:
            problems.append(f"{name}: {why}")
    # several labels at once, in the order found, unique
    many = edited(edited(golden, ("receipts", 0, "applied", 0, "amount"), "1"), ("receipts", 1, "extra"), 1)
    parsed = parse(many, truth)
    if not isinstance(parsed, A.ApplicationRejected) or set(parsed.labels) != {"application.schema",
                                                                                "application.amount.not_decimal"}:
        problems.append(f"two structural findings are not both reported: {parsed}")
    # the golden is accepted, with notes
    noted = edited(golden, ("receipts", 0, "notes"), "per RA-0410-GR; SI-3100 withheld by customer")
    parsed = parse(noted, truth)
    if not isinstance(parsed, A.ParsedApplication) or parsed.receipts[0].notes != "per RA-0410-GR; SI-3100 withheld by customer":
        problems.append(f"the golden with a note is not accepted: {parsed}")
    elif parsed.canonical_document()["receipts"][0].get("notes") != "per RA-0410-GR; SI-3100 withheld by customer":
        problems.append("the canonical document drops the note")
    # notes are the spec's rule and nothing stricter: any JSON string of at most 200 characters, a newline included
    multiline = edited(golden, ("credit_notes", 0, "notes"), "line one\nline two\ttabbed")
    parsed = parse(multiline, truth)
    if not isinstance(parsed, A.ParsedApplication) or parsed.credit_notes[0].notes != "line one\nline two\ttabbed":
        problems.append(f"a note with a newline is refused: {parsed}")
    exact = edited(golden, ("receipts", 0, "notes"), "x" * 200)
    if not isinstance(parse(exact, truth), A.ParsedApplication):
        problems.append("a 200-character note is refused")
    covered = {label for _doc, label in fixtures.values()}
    for label in A.REJECTION_LABELS:
        if label not in covered and label not in A.IDENTITY_LABELS:     # the identities have their own test
            problems.append(f"{label}: no fixture reaches it")
    return check("the parse boundary refuses by label: schema (JSON, keys, types, ids, notes), amount.not_decimal "
                 "(every non-two-place form), duplicate_member, the three duplicate keys and row_identity "
                 "(arithmetic, negatives); the golden with a note is accepted", not problems, "\n".join(problems))


def test_the_five_identities_are_enforced_on_submissions_as_on_goldens():
    """Every consistency identity the truth register satisfies by
    construction is enforced on a submission by the same boundary, and a
    violated identity REJECTS: `A = 0`, `APPLICATION_REJECTED`, never a
    label on a scored file."""
    problems = []
    for n in range(1, 6):
        inputs, env, truth = case(n)
        golden = golden_document(truth)
        parsed = parse(golden, truth)
        if not isinstance(parsed, A.ParsedApplication):
            problems.append(f"case {n}: the golden fails the boundary: {parsed}")
            continue
        r3 = next(i for i, r in enumerate(golden["receipts"]) if r["receipt_id"] in (R3, R3_CASE_2))
        rows = {w["invoice_id"]: i for i, w in enumerate(golden["closing_open_items"])}
        # applied: shift one cent inside the receipt, keep the row
        note = golden["credit_notes"][0]
        gross = sum((D(item["amount"]) for item in note["applied"]), D(0)) + D(note["unapplied_amount"])
        violations = {
            "application.applied_identity": edited(golden, ("receipts", r3, "applied", 0, "amount"),
                                                   money(D(golden["receipts"][r3]["applied"][0]["amount"]) - D("0.01"))),
            # one cent moved from applied to unapplied: the note still conserves its gross, the row does not agree
            "application.credit_identity": edited(edited(golden, ("credit_notes", 0, "applied", 0, "amount"),
                                                         money(D(note["applied"][0]["amount"]) - D("0.01"))),
                                                  ("credit_notes", 0, "unapplied_amount"),
                                                  money(D(note["unapplied_amount"]) + D("0.01"))),
            "application.credit_conservation": edited(golden, ("credit_notes", 0, "unapplied_amount"), "0.01"),
        }
        # write-off: a receipt item the rows do not carry (Case 1 has none; add one and adjust the row's
        # remaining so row_identity holds and only the write-off identity fails)
        with_writeoff = json.loads(json.dumps(golden))
        with_writeoff["receipts"][r3]["written_off"] = items([("SI-3105", "1.00")])
        violations["application.writeoff_identity"] = with_writeoff
        # a written_off item naming an invoice with no row
        orphan = json.loads(json.dumps(golden))
        orphan["receipts"][r3]["written_off"] = items([("SI-3199", "1.00")])
        violations["application.writeoff_identity (no row)"] = orphan
        # an application naming an invoice with no row
        orphan_applied = json.loads(json.dumps(golden))
        orphan_applied["receipts"][r3]["applied"] = orphan_applied["receipts"][r3]["applied"] + items([("SI-3199", "1.00")])
        violations["application.applied_identity (no row)"] = orphan_applied
        orphan_credit = json.loads(json.dumps(golden))
        orphan_credit["credit_notes"][0]["applied"] = items([("SI-3199", money(gross))])   # conserved, no row
        orphan_credit["credit_notes"][0]["unapplied_amount"] = "0.00"
        violations["application.credit_identity (no row)"] = orphan_credit
        # a row whose column disagrees with the receipts, remaining adjusted so the row itself is consistent
        w = rows["SI-3103"]
        row_3103 = golden["closing_open_items"][w]
        disagreeing = edited(edited(golden, ("closing_open_items", w, "applied_total"), "2969.00"),
                             ("closing_open_items", w, "remaining"), money(D(row_3103["remaining"]) + D("1.00")))
        violations["application.applied_identity (row side)"] = disagreeing
        for name, doc in violations.items():
            label = name.split(" ")[0]
            why = rejected_with(doc, truth, label)
            if why:
                problems.append(f"case {n} {name}: {why}")
                continue
            out = A.score_application(parse(doc, truth), truth, expected_balances=env.expected_balances)
            if out.total != ZERO or out.application_states != (A.APPLICATION_REJECTED,) or out.rejection != (label,) \
                    or out.status != "rejected" or out.penalties or out.receipt_states:
                problems.append(f"case {n} {name}: the rejected file was priced: {out.as_dict()}")
            comp = X.compose(ledger(n, inputs.golden_text), out)
            if comp.total != ZERO or comp.complete:
                problems.append(f"case {n} {name}: composite {comp.total}")
    for label in A.IDENTITY_LABELS:
        if label not in ("application.row_identity", "application.applied_identity", "application.credit_identity",
                         "application.writeoff_identity", "application.credit_conservation"):
            problems.append(f"{label}: an identity this test does not know")
    return check("the five identities (row, applied, credit, write-off, credit conservation) hold on every golden "
                 "and each violation on a submission REJECTS with exactly its label — A = 0, APPLICATION_REJECTED, "
                 "nothing priced, composite 0", not problems, "\n".join(problems))


def test_canonicalisation_by_invoice():
    problems = []
    inputs, env, truth = case(1)
    golden = golden_document(truth)
    reference = parse(golden, truth)
    variants = {
        "one application split in two": document(
            truth, [rec(R1, [("SI-3101", "2400.00"), ("SI-3102", "1000.00"), ("SI-3102", "500.00")]), R2_ADVICED,
                    rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")])], [CN_ON_3102]),
        "an informational zero line mirrored": document(
            truth, [rec(R1, [("SI-3101", "2400.00"), ("SI-3102", "1500.00"), ("SI-3100", "0.00")]), R2_ADVICED,
                    rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")])], [CN_ON_3102]),
        "records and items reordered": {
            **golden, "receipts": list(reversed(golden["receipts"])),
            "closing_open_items": list(reversed(golden["closing_open_items"]))},
        "a credit split in two": document(
            truth, [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")])],
            [cn(CN, [("SI-3102", "200.00"), ("SI-3102", "70.00")])]),
        "an empty write-off that sums to zero": document(
            truth, [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")],
                                                written_off=[("SI-3104", "0.00")])], [CN_ON_3102]),
    }
    for name, doc in variants.items():
        parsed = parse(doc, truth)
        if not isinstance(parsed, A.ParsedApplication):
            problems.append(f"{name}: rejected {parsed}")
            continue
        if parsed.canonical_digest != reference.canonical_digest or A.canonical_text(parsed) != A.canonical_text(reference):
            problems.append(f"{name}: a different canonical document")
        out = A.score_application(parsed, truth, expected_balances=env.expected_balances)
        if out.total != ONE or out.application_digest != reference.canonical_digest:
            problems.append(f"{name}: A = {out.total}")
    # duplicates INSIDE one receipt's list are canonicalised; duplicate ROWS are rejected — the spec's definition
    split_then_row = document(truth, [rec(R1, [("SI-3101", "2400.00"), ("SI-3102", "1000.00"), ("SI-3102", "500.00")]),
                                      R2_ADVICED, rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")])],
                              [CN_ON_3102])
    split_then_row["closing_open_items"].append(split_then_row["closing_open_items"][0])
    if rejected_with(split_then_row, truth, "application.invoice.duplicate_row"):
        problems.append("a duplicate invoice line is not rejected while a split application is canonicalised")
    # canonicalisation happens BEFORE the identities: the summed amount is what the row must carry
    summed = document(truth, [rec(R1, [("SI-3101", "2400.00"), ("SI-3102", "1000.00"), ("SI-3102", "500.00")]),
                              R2_ADVICED, rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")])], [CN_ON_3102])
    summed = edited(edited(summed, ("closing_open_items", 2, "applied_total"), "2830.00"),
                    ("closing_open_items", 2, "remaining"), "500.00")
    if rejected_with(summed, truth, "application.applied_identity"):
        problems.append("a row carrying only one of two split entries passes the applied identity")
    return check("canonicalisation by invoice: split applications, mirrored zero lines, reordered records and a split "
                 "credit are one canonical document with one digest and A = 1; a duplicate invoice LINE is still "
                 "rejected; the identities read the summed amounts", not problems, "\n".join(problems))


def test_negatives_are_refused_before_the_summing_and_negative_zero_is_zero():
    """Spec section 3: `row_identity` rejects on "any negative amount". The
    summing by invoice must not launder one — [1600.00, -100.00] against
    one invoice is a negative amount, never a 1500.00 application — and an
    invented id whose entries sum to zero does not vanish. An entry naming
    an invoice with no row is refused whatever its amount, a zero included.
    "-0.00" is a two-place decimal equal to zero: read as zero, rendered
    0.00, one canonical digest for two accounting-identical documents."""
    problems = []
    inputs, env, truth = case(1)
    golden = golden_document(truth)
    reference = parse(golden, truth)
    r1 = next(i for i, r in enumerate(golden["receipts"]) if r["receipt_id"] == R1)
    r3 = next(i for i, r in enumerate(golden["receipts"]) if r["receipt_id"] == R3)
    masked = {
        "applied 1600.00 + -100.00 (sums to the row's 1500.00)": (
            edited(golden, ("receipts", r1, "applied"),
                   items([("SI-3101", "2400.00"), ("SI-3102", "1600.00"), ("SI-3102", "-100.00")])),
            ("application.row_identity",)),
        "written_off 5.00 + -5.00 (sums to zero)": (
            edited(golden, ("receipts", r1, "written_off"), items([("SI-3102", "5.00"), ("SI-3102", "-5.00")])),
            ("application.row_identity",)),
        "credit applied 300.00 + -30.00 (sums to the row's 270.00 and conserves the gross)": (
            edited(golden, ("credit_notes", 0, "applied"), items([("SI-3102", "300.00"), ("SI-3102", "-30.00")])),
            ("application.row_identity",)),
        "an invented id whose entries sum to zero (5.00 + -5.00 on SI-3199)": (
            edited(golden, ("receipts", r3, "applied"),
                   golden["receipts"][r3]["applied"] + items([("SI-3199", "5.00"), ("SI-3199", "-5.00")])),
            ("application.row_identity", "application.applied_identity")),
        "a single negative entry": (
            edited(golden, ("receipts", r1, "applied"), golden["receipts"][r1]["applied"] + items([("SI-3100", "-1.00")])),
            ("application.row_identity", "application.applied_identity")),
        "a negative row column": (
            edited(edited(golden, ("closing_open_items", 0, "credited"), "-1.00"), ("closing_open_items", 0, "remaining"),
                   "301.00"),
            ("application.row_identity", "application.credit_identity")),
    }
    for name, (doc, labels) in masked.items():
        why = rejected_with(doc, truth, *labels)
        if why:
            problems.append(f"{name}: {why}")
            continue
        out = A.score_application(parse(doc, truth), truth, expected_balances=env.expected_balances)
        if out.total != ZERO or out.application_states != (A.APPLICATION_REJECTED,) or out.penalties:
            problems.append(f"{name}: the rejected file was priced: {out.as_dict()}")
    # a zero-amount entry naming an invoice with no row: refused by the column's identity, never dropped
    orphans = {
        "a zero applied entry naming an invoice with no row": (
            edited(golden, ("receipts", r3, "applied"), golden["receipts"][r3]["applied"] + items([("SI-3199", "0.00")])),
            "application.applied_identity"),
        "a zero written_off item naming an invoice with no row": (
            edited(golden, ("receipts", r3, "written_off"), items([("SI-3199", "0.00")])),
            "application.writeoff_identity"),
        "a zero credit application naming an invoice with no row": (
            edited(golden, ("credit_notes", 0, "applied"), golden["credit_notes"][0]["applied"] + items([("SI-3199", "0.00")])),
            "application.credit_identity"),
    }
    for name, (doc, label) in orphans.items():
        why = rejected_with(doc, truth, label)
        if why:
            problems.append(f"{name}: {why}")
    # negative zero: accepted, read as zero, rendered 0.00, the golden's digest, A = 1
    zeros = {
        "-0.00 as a row's applied_total": edited(golden, ("closing_open_items", 0, "applied_total"), "-0.00"),
        "-0.00 as a receipt's unapplied_amount": edited(golden, ("receipts", r1, "unapplied_amount"), "-0.00"),
        "-0.00 as a credit note's unapplied_amount": edited(golden, ("credit_notes", 0, "unapplied_amount"), "-0.00"),
        "-0.00 as a zero line against a rowed invoice": edited(
            golden, ("receipts", r1, "applied"), golden["receipts"][r1]["applied"] + items([("SI-3100", "-0.00")])),
    }
    for name, doc in zeros.items():
        parsed = parse(doc, truth)
        if not isinstance(parsed, A.ParsedApplication):
            problems.append(f"{name}: rejected {parsed}")
            continue
        if parsed.canonical_digest != reference.canonical_digest or A.canonical_text(parsed) != A.canonical_text(reference):
            problems.append(f"{name}: a different canonical document")
        if "-0.00" in A.canonical_text(parsed):
            problems.append(f"{name}: the canonical text renders a negative zero")
        out = A.score_application(parsed, truth, expected_balances=env.expected_balances)
        if out.total != ONE or out.application_digest != reference.canonical_digest:
            problems.append(f"{name}: A = {out.total}")
    if "-0.00" in A.canonical_text(reference):
        problems.append("the golden's canonical text renders a negative zero")
    return check("negatives are refused on the RAW entries before the summing (masked in applied, written_off and a "
                 "credit's applied; an invented id summing to zero; a single entry; a row column), a zero entry "
                 "naming an invoice with no row is refused by its column's identity, and -0.00 is zero: accepted, "
                 "rendered 0.00, the golden's digest, A = 1", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 4. composition
# --------------------------------------------------------------------------

def test_the_composite_is_monotone_and_complete_iff_one():
    problems = []
    inputs, env, truth = case(3)
    golden_register = golden_document(truth)
    wrong_register = case_3_register_with_3104_open_at_20()
    ledgers = {"R2 repaired only": without(inputs.golden_text, WRITE_OFF_ENTRY_CASE_3),
               "untouched": inputs.original_text, "golden": inputs.golden_text}
    registers = {"SI-3104 open at 20.00": wrong_register, "golden": golden_register, "absent": None}

    def total(l_name, r_name):
        L = ledger(3, ledgers[l_name])
        doc = registers[r_name]
        a = (A.score_application(None, truth, expected_balances=env.expected_balances) if doc is None
             else score(3, doc))
        return X.compose(L, a)

    grid = {(l, r): total(l, r) for l in ledgers for r in registers}
    for (l, r), comp in grid.items():
        L, a = comp.ledger_total, comp.application_total
        if comp.total != (L * a).quantize(D("0.000001")):
            problems.append(f"{l} / {r}: total {comp.total} is not q6({L} x {a})")
        if (comp.total == ONE) != comp.complete:
            problems.append(f"{l} / {r}: total {comp.total} and complete={comp.complete} disagree")
    # monotone in L for every register, monotone in A for every ledger
    order_l = ["untouched", "R2 repaired only", "golden"]
    order_r = ["absent", "SI-3104 open at 20.00", "golden"]
    for r in registers:
        totals = [grid[(l, r)].total for l in order_l]
        if totals != sorted(totals):
            problems.append(f"register {r}: totals over the ledgers {totals} are not non-decreasing")
    for l in ledgers:
        totals = [grid[(l, r)].total for r in order_r]
        if totals != sorted(totals):
            problems.append(f"ledger {l}: totals over the registers {totals} are not non-decreasing")
    if grid[("R2 repaired only", "SI-3104 open at 20.00")].total != D("0.108611") \
            or grid[("golden", "SI-3104 open at 20.00")].total != D("0.283333") \
            or grid[("golden", "golden")].total != ONE or grid[("untouched", "golden")].total != ZERO:
        problems.append("the worked-example corners are not 0.108611 / 0.283333 / 1.000000 / 0.000000")
    # a perturbation of a perfect register strictly lowers the total while the ledger is positive
    for n in range(1, 6):
        i, e, t = case(n)
        perfect = golden_document(t)
        for k, w in enumerate(perfect["closing_open_items"]):
            hurt = edited(perfect, ("closing_open_items", k, "customer"), "Nobody")
            if X.compose(ledger(n, i.golden_text), score(n, hurt)).total >= ONE:
                problems.append(f"case {n}: a wrong customer on {w['invoice_id']} did not lower the total")
    # complete requires every clause
    out = score(1, {**golden_document(case(1)[2]), "credit_notes": golden_document(case(1)[2])["credit_notes"]
                    + [cn("CN-9999", [])]})
    comp = X.compose(ledger(1, case(1)[0].golden_text), out)
    if comp.total != D("0.600000") or comp.complete:
        problems.append(f"a perfect register with an invented note composes to {comp.total} complete={comp.complete}")
    return check("composite/1: total = q6(L x A) after the product, monotone in L for every register and in A for "
                 "every ledger, total = 1 <=> complete, a perturbed register strictly lowers a perfect total",
                 not problems, "\n".join(problems))


def test_a_legacy_task_composes_to_its_ledger_score():
    problems = []
    world, task = REGISTRY["bank_recon_001"]
    _bundle, inputs = derive_contract(world, task)
    if inputs.application is not None:
        problems.append("a legacy task carries ApplicationInputs")
    env = K.load_contract(inputs)
    for name, text in (("golden", inputs.golden_text), ("untouched", inputs.original_text)):
        L, problem = score_text(text, env, name)
        if L is None:
            problems.append(problem)
            continue
        comp = X.compose(L, None)
        if comp.total != L.total or comp.complete != L.complete or comp.application_total != D(1) \
                or comp.application is not None or comp.engines != ("candidate/1", "composite/1"):
            problems.append(f"{name}: composite {comp.total} complete={comp.complete} vs L {L.total} {L.complete}")
        comp.verify()
    try:
        X.compose("not an outcome", None)
    except TypeError:
        pass
    else:
        problems.append("compose accepted a non-ScoreOutcome ledger")
    try:
        A.score_application(None, None, expected_balances=())
    except TypeError:
        pass
    else:
        problems.append("score_application accepted a task without ApplicationInputs")
    return check("without ApplicationInputs A == 1: a legacy task's composite is its candidate/1 total and "
                 "completeness, and the doors refuse the wrong types", not problems, "\n".join(problems))


def test_the_scorer_reads_expected_balances_and_refuses_a_truth_that_disagrees():
    problems = []
    inputs, env, truth = case(3)
    doc = golden_document(truth)
    balances = dict(env.expected_balances)
    for account, delta, what in ((AR, D("1.00"), "closing receivables"), (WRITE_OFFS, D("1.00"), "write-off movement")):
        moved = {**balances, account: balances[account] + delta}
        try:
            A.score_application(parse(doc, truth), truth, expected_balances=tuple(sorted(moved.items())))
        except RuntimeError:
            pass
        else:
            problems.append(f"a truth register disagreeing with the expected {what} was scored")
    return check("the expected closing receivables and write-off movement are read from expected_balances, and a "
                 "truth register that disagrees with them is an evaluator failure, not a score", not problems,
                 "\n".join(problems))


# --------------------------------------------------------------------------
# 5. the state catalogue
# --------------------------------------------------------------------------

def test_every_state_is_reached_and_everything_reached_is_a_state():
    problems = []
    reached: dict = {}

    def note(name, out):
        for state in out.states():
            if not isinstance(state, A.ApplicationState) or state not in A.APPLICATION_STATES:
                problems.append(f"{name}: {state!r} is not a member of APPLICATION_STATES")
            reached.setdefault(str(state), name)

    inputs, env, truth = case(1)
    golden = golden_document(truth)
    note("golden", score(1, golden))
    note("S1", score(1, case_1(rec(R3, [("SI-3101", "2130.00"), ("SI-3104", "1590.00")]),
                                credit=cn(CN, [("SI-3101", "270.00")]),
                                r1=rec(R1, [("SI-3100", "300.00"), ("SI-3102", "3600.00")]))))
    note("S3", score(1, document(truth, [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")])], [])))
    note("S3 held", score(1, document(truth, [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")])],
                                      [cn(CN, [], unapplied="270.00")])))
    fabricated = json.loads(json.dumps(golden))
    fabricated["closing_open_items"].append(row("SI-3199", GANNET, "0.00", "0.00", "0.00", "0.00", "0.00"))
    fabricated["receipts"].append(rec("2026-04-28:INVENTED", []))
    fabricated["credit_notes"].append(cn("CN-9999", []))
    note("S7", score(1, fabricated))
    note("wrong customer", score(1, edited(golden, ("closing_open_items", 5, "customer"), GANNET)))
    note("missing row", score(1, {**golden, "closing_open_items": golden["closing_open_items"][:5]}))
    note("missing receipt", score(1, document(truth, [R1_ADVICED, rec(R3, [("SI-3102", "1830.00"), ("SI-3104", "1890.00")])],
                                              [CN_ON_3102])))
    note("S8b", A.score_application(None, truth, expected_balances=env.expected_balances))
    note("S5 rejected", A.score_application(A.ApplicationRejected(("application.credit_conservation",), ("x",)), truth,
                                            expected_balances=env.expected_balances))
    # Case 2: the reference decides; Case 3: the write-off; Case 5: the basis and the residue
    i2, e2, t2 = case(2)
    note("Case 2 printed order", score(2, document(t2, [R1_ADVICED, R2_ADVICED,
                                                        rec(R3_CASE_2, [("SI-3104", "1890.00"), ("SI-3102", "240.00")])],
                                                   [CN_ON_3102])))
    note("Case 2 amount-only", score(2, document(t2, [R1_ADVICED, R2_ADVICED,
                                                      rec(R3_CASE_2, [("SI-3100", "300.00"), ("SI-3102", "1830.00")])],
                                                 [CN_ON_3102])))
    note("(iii)", score(3, case_3_register_with_3104_open_at_20()))
    i5, e5, t5 = case(5)
    basis = golden_document(t5)
    basis = edited(edited(basis, ("closing_open_items", 0, "period_basis"), "1080.00"),
                   ("closing_open_items", 0, "remaining"), "780.00")
    note("face value as basis", score(5, basis))
    note("residue dropped", score(5, document(t5, [R1_ADVICED, R2_ADVICED,
                                                   rec(R3, [("SI-3102", "1860.00"), ("SI-3104", "1890.00")])],
                                              [cn(CN, [("SI-3100", "300.00"), ("SI-3102", "240.00")])])))
    # rung (3): no advice and no reference naming invoices — a truth variant of Case 1 in which R3's advice is
    # withdrawn (no case exercises rung (3); the fold's fixture does, and the diagnosis is pinned here)
    r3_truth = next(r for r in truth.receipts if r[0] == R3)
    variant = dataclasses.replace(truth, receipts=tuple(
        (r[:7] + ("",) + r[8:]) if r[0] == R3 else r for r in truth.receipts))
    if variant.receipt(R3)[7] != "" or r3_truth[7] != "RA-0428-GR":
        problems.append("the rung-(3) variant did not withdraw R3's advice")
    note("rung (3) wrong invoices", score(1, case_1(rec(R3, [("SI-3100", "300.00"), ("SI-3102", "1530.00"),
                                                            ("SI-3104", "1890.00")])), truth=variant))

    for state in A.APPLICATION_STATES:
        if str(state) not in reached:
            problems.append(f"{state}: no fixture reaches it")
    expected = {
        "S1": {R1: "RECEIPT_CONTRADICTS_ADVICE", CN: "CREDIT_WRONG_INVOICES"},
        "S3": {CN: "CREDIT_MISSING", "ar": "AR_TIE_CONTRADICTS"},
        "S3 held": {CN: "CREDIT_WRONG_SPLIT"},
        "S7": {"SI-3199": "INVOICE_FABRICATED", "2026-04-28:INVENTED": "RECEIPT_FABRICATED", "CN-9999": "CREDIT_FABRICATED"},
        "wrong customer": {"SI-3105": "INVOICE_WRONG_CUSTOMER"},
        "missing row": {"SI-3105": "INVOICE_MISSING"},
        "missing receipt": {R2: "RECEIPT_MISSING"},
        "Case 2 printed order": {R3_CASE_2: "RECEIPT_WRONG_AMOUNT"},
        "Case 2 amount-only": {R3_CASE_2: "RECEIPT_CONTRADICTS_REFERENCE"},
        "(iii)": {R3: "RECEIPT_WRONG_WRITEOFF", "writeoff": "WRITEOFF_TIE_CONTRADICTS"},
        "face value as basis": {"SI-3100": "INVOICE_WRONG_BASIS"},
        "residue dropped": {R3: "RECEIPT_WRONG_UNAPPLIED"},
        "rung (3) wrong invoices": {R3: "RECEIPT_WRONG_INVOICES"},
    }
    for name, wanted in expected.items():
        for subject, state in wanted.items():
            if reached.get(state) is None:
                problems.append(f"{name}: {state} was never reached")
    # the residue-dropped receipt also fails the receipt identity (3,750 != 3,780) and, since the 30.00 is Gannet's
    # unapplied credit inside receivables, the AR tie (2,970 - 0 != 2,940)
    out = score(5, document(t5, [R1_ADVICED, R2_ADVICED, rec(R3, [("SI-3102", "1860.00"), ("SI-3104", "1890.00")])],
                            [cn(CN, [("SI-3100", "300.00"), ("SI-3102", "240.00")])]))
    if sorted(out.penalty_labels) != ["ar_tie_break", "receipt_identity"] \
            or dict(out.receipt_states)[R3] is not A.RECEIPT_WRONG_UNAPPLIED:
        problems.append(f"the dropped residue: {out.penalties} {dict(out.receipt_states)[R3]}")
    # one reason per inexact receipt, credit note and invoice
    for name, out in (("S1", score(1, case_1(rec(R3, [("SI-3101", "2130.00"), ("SI-3104", "1590.00")]),
                                              credit=cn(CN, [("SI-3101", "270.00")]),
                                              r1=rec(R1, [("SI-3100", "300.00"), ("SI-3102", "3600.00")])))),):
        ids = [s for s, _ in out.receipt_states] + [s for s, _ in out.credit_states] + [s for s, _ in out.invoice_states]
        if len(ids) != len(set(ids)):
            problems.append(f"{name}: a subject carries two states")
    # the scopes are the declared ones and a copy is a plain str
    import copy
    import pickle
    if {s.scope for s in A.APPLICATION_STATES} != set(A.STATE_SCOPES):
        problems.append("a scope is declared and unused, or used and undeclared")
    if type(copy.deepcopy(A.RECEIPT_EXACT)) is not str or pickle.loads(pickle.dumps(A.AR_TIE_OK)) != "AR_TIE_OK":
        problems.append("an ApplicationState does not copy to a plain str")
    if len(set(A.APPLICATION_STATES)) != 26:
        problems.append(f"{len(set(A.APPLICATION_STATES))} states, not the catalogue's 26")
    return check("the state catalogue is closed: every state the scorer emits is a member, every member is reached "
                 "by a fixture, one reason per inexact receipt / credit note / invoice, and the spec's named "
                 "diagnoses hold (advice, reference, rung (3), amount, write-off, unapplied, split, missing, "
                 "fabricated, basis, customer)", not problems, "\n".join(problems))


def test_penalty_vocabulary_and_prices_are_the_declared_ones():
    problems = []
    if A.PENALTY_LABELS != ("fabricated_invoice", "fabricated_receipt", "fabricated_credit_note", "receipt_identity",
                            "ar_tie_break", "writeoff_tie_break"):
        problems.append(f"labels {A.PENALTY_LABELS}")
    prices = {label: str(A.PENALTY_PRICES[label]) for label in A.PENALTY_LABELS}
    if prices != {"fabricated_invoice": "-0.40", "fabricated_receipt": "-0.40", "fabricated_credit_note": "-0.40",
                  "receipt_identity": "-0.20", "ar_tie_break": "-0.30", "writeoff_tie_break": "-0.20"}:
        problems.append(f"prices {prices}")
    if (A.WEIGHT_RECEIPTS, A.WEIGHT_REGISTER, A.WEIGHT_CREDITS) != (D("0.50"), D("0.30"), D("0.20")) \
            or A.WEIGHT_RECEIPTS + A.WEIGHT_REGISTER + A.WEIGHT_CREDITS != D("1.00"):
        problems.append("the channel weights are not 0.50 / 0.30 / 0.20")
    if A.APPLICATION_ENGINE_ID != "application/1" or X.COMPOSITE_ENGINE_ID != "composite/1" \
            or A.APPLICATION_SCHEMA != "piv.cash-application/1":
        problems.append("engine ids or schema moved")
    if A.MAX_NOTES_CHARS != 200 or A.STATUSES != ("delivered", "absent", "rejected"):
        problems.append("notes limit or status vocabulary moved")
    if (A.MAX_ID_CHARS, A.MAX_TEXT_CHARS, A.MAX_RECORDS) != (120, 200, 500):
        problems.append("the declared bounds (ids 120, customer 200, 500 records per list) moved")
    return check("the declared engineering choices: channels 0.50 / 0.30 / 0.20, three fabrications at -0.40, "
                 "receipt_identity -0.20, ar_tie_break -0.30, writeoff_tie_break -0.20; engine ids application/1 "
                 "and composite/1; schema piv.cash-application/1", not problems, "\n".join(problems))


TESTS = [
    test_every_golden_register_scores_one_and_completes_with_the_golden_ledger,
    test_worked_example_i_amount_matching_chained_from_the_opening,
    test_worked_example_ii_r2_omission_left_through_the_frozen_scorer,
    test_worked_example_iii_case_3_through_the_frozen_scorer,
    test_s1_amount_only_matching,
    test_s2_oldest_first_against_the_advice,
    test_s3_credit_note_ignored_in_the_register,
    test_s4a_short_pay_booked_as_fully_paid,
    test_s4b_write_off_beyond_tolerance,
    test_s5_credit_excess_to_revenue,
    test_s6_right_sums_wrong_invoices,
    test_s7_fabricated_ids,
    test_s8_ledger_untouched_and_no_application,
    test_case_2_the_four_baselines_and_their_reason_states,
    test_parse_boundary_rejections_by_label,
    test_the_five_identities_are_enforced_on_submissions_as_on_goldens,
    test_canonicalisation_by_invoice,
    test_negatives_are_refused_before_the_summing_and_negative_zero_is_zero,
    test_the_composite_is_monotone_and_complete_iff_one,
    test_a_legacy_task_composes_to_its_ledger_score,
    test_the_scorer_reads_expected_balances_and_refuses_a_truth_that_disagrees,
    test_every_state_is_reached_and_everything_reached_is_a_state,
    test_penalty_vocabulary_and_prices_are_the_declared_ones,
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
