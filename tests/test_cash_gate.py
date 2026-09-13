"""Phase C of the generated cash-application population: the MINTING GATE and
its CENSUS.

Round 16, decision 3. What is witnessed here:

  * the declared gate set and the implementations agree in BOTH directions —
    a declared gate with no implementation and an implementation the gate set
    does not declare each stop admission rather than passing silently — and
    every gate carries its own rejection code, with the reading bound
    carrying the ruling's own word, `VERIFICATION-LIMIT`;
  * every family mints through the gate with all thirty-one gates True, and
    gate (o) is RUN AT MINT TIME on both variants: nine binding baselines,
    one diagnostic, every reading inside the 256-reading bound;
  * EVERY GATE SPEAKS. Each of the thirty-one has a negative control that
    makes it, and it, fail — a check that cannot fail proves nothing, and
    thirty-one checks that have never failed prove nothing thirty-one times;
  * the census retains every attempt's ordinal, stage, evaluated rejection
    codes, relevant baseline and witness, reading count, component versions
    and content digest, and `aggregate` publishes acceptance rates,
    exhaustion counts and rejection distributions;
  * exhaustion is a NAMED failed group carrying `GROUP-EXHAUSTED`, and no
    replacement selector is drawn; a defect is not drawn past;
  * the DIAGNOSTIC STAYS DIAGNOSTIC against the catalogue version's own
    declared roles rather than against the shipped tuple: a swap that
    promotes `number_order` into the binding set while demoting another to
    keep the counts is rejected, where a self-comparison admitted it;
  * an attempt whose enumeration crossed the reading bound still retains
    every baseline's observation and reading count, names the baseline that
    crossed it and the count it reached, and carries VERIFICATION-LIMIT as
    gate (o)'s only code — no second, untrue reason in the distribution;
  * a population declaring one construction identity twice is a DEFECT,
    refused before anything is minted;
  * the minting docstring is the ruling's paragraph VERBATIM;
  * the baseline catalogue is `cash_application_baselines/1` and its digest
    moves when an admission predicate's BODY changes under an unchanged name;
  * the population ledger sees a second pair publishing the first's bytes and
    a renamed cross-split structural sibling;
  * no shipped task's public bytes moved, and GENERATOR_VERSION 9 and its
    manifest are untouched.

Round 17, decision 4 adds one correction to the above. The gate
`cumulative_reversal_bounded` used to cap a credit note at its invoice's
OPENING BALANCE as well as at the original sale. That was wrong accounting —
a credit reverses a SALE, and part payment of that sale does not shrink what
may be credited — and it falsely refused two parent attempts in the census
published on 2026-09-13. The clause is removed; the original-sale bound, its
cumulative reach and the positive-net requirement stay. Because the gate kept
its name and its group, `gate_set_digest()` could not notice on its own, so
GATE_VERSION and the admission contract FAMILY_PREFLIGHT_CONTRACT are both
bumped to 2 and the digest moves off `6b246422badd05a6`. The 2026-09-13
record is preserved unaltered as the historical artifact of the superseded
rule, and NO replacement population is minted here.

    python tests/test_cash_gate.py
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import sys
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from beancount_ledger.graph import cash_admit as ADMIT  # noqa: E402
from beancount_ledger.graph import cash_application as CA  # noqa: E402
from beancount_ledger.graph import cash_construct as CC  # noqa: E402
from beancount_ledger.graph import cash_gate as G  # noqa: E402
from beancount_ledger.graph import cash_manifest as FM  # noqa: E402
from beancount_ledger.graph import mint as BANK_MINT  # noqa: E402
from beancount_ledger.graph.cash_identity import (  # noqa: E402
    BOUNDED_V1,
    MAX_LAYOUT_ATTEMPTS,
    VARIANTS,
    parent_seed,
    private_tokens,
)
from beancount_ledger.graph.cash_split import SPLIT_MAP  # noqa: E402

#: A fixed secret, so the suite draws the same population on every machine and
#: never depends on — or touches — the evaluator's provisioned key.
SECRET = b"cash-application-phase-c-test-secret-0123456789"
POPULATION = "phase-c-suite"

#: The three families the negative controls are built on — one per mechanism
#: stratum, so a control that only works where there is an advice, or only
#: where there is a continuation, is not silently skipped. Minting a group
#: runs the whole gate, so the controls take the pairs from here rather than
#: minting fifteen of them again.
CONTROL_FAMILIES = ("fc-sedgewick", "cr-brindlecote", "ar-tenterhook")

_GROUPS: dict = {}
_LEDGER = G.PopulationLedger()


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:30]:
            print(f"      {line}")
    return ok


def raises(exc, call, *args, **kwargs):
    try:
        call(*args, **kwargs)
    except exc as error:
        return str(error)
    except Exception as error:                                  # noqa: BLE001
        return f"!! {type(error).__name__}: {error}"
    return None


def group(family: str, index: int = 0):
    """One minted parent group, cached: minting runs the whole gate, and the
    suite reads each group many times."""
    key = (family, index)
    if key not in _GROUPS:
        ident = CC.identity_of(POPULATION, family, index)
        _GROUPS[key] = G.mint_group(ident, secret=SECRET, ledger=_LEDGER)
    return _GROUPS[key]


def candidate(family: str = CONTROL_FAMILIES[0], index: int = 0) -> G.Candidate:
    """The admitted attempt again, as a `Candidate` the controls can doctor.

    Rebuilt rather than kept from the mint, because `mint_group` returns the
    pair and not the candidate; rebuilding it from the same rendered variants
    is the same object by construction.
    """
    minted = group(family, index)
    pair = minted.pair
    seed = parent_seed(pair.identity, SECRET)
    return G.candidate_of(pair.identity, BOUNDED_V1, pair.attempt, dict(pair.variants),
                          pair.declared_fact, pair.template, seed)


def evaluate(c: G.Candidate, ledger=None) -> G.GateReport:
    return G.evaluate(c, ledger if ledger is not None else G.PopulationLedger())


def failed(report: G.GateReport) -> set:
    return {gate for gate, ok in report.gates.items() if not ok}


# --------------------------------------------------------------------------
# 1. the gate set, its codes and its fail-closed behaviour
# --------------------------------------------------------------------------

def test_every_declared_gate_is_implemented_and_carries_its_own_code():
    problems = []
    declared = FM.family_gates()
    if G.unimplemented_gates():
        problems.append(f"declared gates with no implementation: {list(G.unimplemented_gates())}")
    if G.undeclared_checks():
        problems.append(f"implementations the gate set does not declare: {list(G.undeclared_checks())}")
    codes = G.rejection_codes()
    if set(codes) != set(declared):
        problems.append(f"the code map covers {sorted(set(codes) ^ set(declared))} differently from the "
                        f"gate set")
    if len(set(codes.values())) != len(codes):
        duplicated = sorted({c for c in codes.values() if list(codes.values()).count(c) > 1})
        problems.append(f"two gates share a rejection code: {duplicated}")
    if codes.get("reading_bound_respected") != "VERIFICATION-LIMIT":
        problems.append(f"the reading bound's code is {codes.get('reading_bound_respected')!r}, not the "
                        f"ruling's VERIFICATION-LIMIT")
    for group_name, gates in FM.GATE_GROUPS:
        for gate in gates:
            if G.group_of(gate) != group_name:
                problems.append(f"{gate} is in {group_name} and reports {G.group_of(gate)}")
            if gate != "reading_bound_respected" and not codes[gate].startswith(G.GROUP_PREFIX[group_name]):
                problems.append(f"{gate}'s code {codes[gate]} does not name its group")

    # Fail closed in both directions, and by REFUSING rather than by passing.
    c = candidate()
    original_groups = FM.GATE_GROUPS
    try:
        FM.GATE_GROUPS = original_groups + (("accounting_integrity", ("a_gate_nobody_wrote",)),)
        if raises(G.GateUnavailable, evaluate, c) is None:
            problems.append("a declared gate with no implementation was admitted rather than refused")
    finally:
        FM.GATE_GROUPS = original_groups
    original_checks = dict(G.VARIANT_CHECKS)
    try:
        G.VARIANT_CHECKS["a_check_nobody_declared"] = lambda _c, _n: []
        if raises(G.GateUnavailable, evaluate, c) is None:
            problems.append("an undeclared implementation ran without the gate set knowing about it")
    finally:
        G.VARIANT_CHECKS.clear()
        G.VARIANT_CHECKS.update(original_checks)
    return check(f"all {len(declared)} declared gates have an implementation, every implementation is "
                 f"declared, each gate carries its own rejection code with the reading bound carrying the "
                 f"ruling's VERIFICATION-LIMIT, and a disagreement between the two REFUSES to evaluate",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 2. every family mints, and gate (o) runs at mint time
# --------------------------------------------------------------------------

def test_every_family_mints_with_every_gate_true():
    problems = []
    declared = set(FM.family_gates())
    for shape in CC.SHAPES:
        minted = group(shape.family)
        report, census = minted.report, minted.census
        if set(report.gates) != declared:
            problems.append(f"{shape.family}: the report covers {sorted(set(report.gates) ^ declared)} "
                            f"differently from the gate set")
        if not report.passed:
            problems.append(f"{shape.family}: {sorted(failed(report))} — {report.witness()[:200]}")
        if census.outcome != "admitted" or census.accepted_attempt is None:
            problems.append(f"{shape.family}: the census says {census.outcome}")
        if set(minted.pair.variants) != set(VARIANTS):
            problems.append(f"{shape.family}: the pair carries {sorted(minted.pair.variants)}")
        if report.catalogue != "cash_application_baselines/1":
            problems.append(f"{shape.family}: minted against catalogue {report.catalogue!r}")
        if report.gate_set != FM.gate_set_digest():
            problems.append(f"{shape.family}: minted against another gate set")
    return check("every one of the fifteen structural-template families mints a pair through the gate, with "
                 "all thirty-one declared gates True, both variants present, and the catalogue and gate set "
                 "the record binds", not problems, "\n".join(problems))


def test_gate_o_runs_at_mint_time_on_both_variants():
    problems = []
    binding = {b.name for b in CA.BASELINES if not b.diagnostic}
    diagnostic = {b.name for b in CA.BASELINES if b.diagnostic}
    if (len(binding), diagnostic) != (9, {"number_order"}):
        problems.append(f"the catalogue holds {len(binding)} binding baselines and diagnostics {diagnostic}")
    recorded_diagnostic = 0
    for shape in CC.SHAPES:
        report = group(shape.family).report
        for name in VARIANTS:
            seen = [o for o in report.baselines if o.variant == name]
            if {o.name for o in seen} != binding | diagnostic:
                problems.append(f"{shape.family}/{name}: gate (o) recorded {sorted(o.name for o in seen)}")
            for o in seen:
                if o.role == "binding" and o.admitted and o.reaches_truth:
                    problems.append(f"{shape.family}/{name}: the binding baseline {o.name} reaches the whole "
                                    f"truth through one of {o.readings} readings")
                if o.readings > CA.MAX_BASELINE_READINGS:
                    problems.append(f"{shape.family}/{name}: {o.name} enumerated {o.readings} readings")
                if o.role == "diagnostic" and o.admitted:
                    recorded_diagnostic += 1
                    if o.reaches_truth is None:
                        problems.append(f"{shape.family}/{name}: the diagnostic result was not recorded")
        if report.verification_limited:
            problems.append(f"{shape.family}: a verification limit was recorded on an admitted pair")
    print(f"      (the diagnostic number-order reading was admitted and recorded on {recorded_diagnostic} "
          f"variant(s); it is never an admission rule)")
    return check("gate (o) runs in the MINTING PATH on both variants of every family: nine binding baselines "
                 "and one diagnostic, no admitted binding baseline reaching the entire truth through any "
                 "enumerated reading, every enumeration inside the 256-reading bound, and the diagnostic "
                 "recorded rather than promoted", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3. every gate speaks
# --------------------------------------------------------------------------

def _doctor_application(c: G.Candidate, name: str, **changes) -> G.Candidate:
    application = dict(c.application)
    application[name] = dataclasses.replace(application[name], **changes)
    return dataclasses.replace(c, application=application)


def _doctor_evidence(c: G.Candidate, name: str, **changes) -> G.Candidate:
    evidence = dict(c.evidence)
    evidence[name] = dataclasses.replace(evidence[name], **changes)
    return dataclasses.replace(c, evidence=evidence)


def _doctor_files(c: G.Candidate, name: str, file_name: str, text: str) -> G.Candidate:
    variants = dict(c.variants)
    public = dict(variants[name].public_files)
    public[file_name] = text
    variants[name] = dataclasses.replace(variants[name], public_files=public)
    return dataclasses.replace(c, variants=variants)


def _doctor_variant(c: G.Candidate, name: str, **changes) -> G.Candidate:
    variants = dict(c.variants)
    variants[name] = dataclasses.replace(variants[name], **changes)
    return dataclasses.replace(c, variants=variants)


def _controls(c: G.Candidate) -> list:
    """(gate, description, a candidate the gate must reject). One per
    declared gate; the ones that cannot be expressed as a doctored candidate
    are run as monkeypatches in `test_every_gate_speaks` instead."""
    a = "a"
    app = c.application[a]
    ev = c.evidence[a]
    out = []

    # accounting integrity
    out.append(("invoice_universe_complete", "a register row dropped",
                _doctor_application(c, a, register=app.register[1:])))
    out.append(("customer_ownership", "a receipt credited to a stranger",
                _doctor_application(c, a, receipts=(dataclasses.replace(app.receipts[0], customer="Nobody Ltd"),)
                                    + app.receipts[1:])))
    out.append(("receipt_and_credit_conservation", "a receipt's residue moved off its total",
                _doctor_application(c, a, receipts=(dataclasses.replace(
                    app.receipts[0], unapplied=app.receipts[0].unapplied + D("1.00")),) + app.receipts[1:])))
    out.append(("row_identities", "a register row that does not add up",
                _doctor_application(c, a, register=(dataclasses.replace(
                    app.register[0], remaining=app.register[0].remaining + D("1.00")),) + app.register[1:])))
    out.append(("ar_reconciles", "a closing AR that is not the fold's",
                _doctor_application(c, a, closing_ar=app.closing_ar + D("1.00"))))
    out.append(("consistent_sale_and_credit_tax_bases", "a credit note whose net and tax are not its gross",
                _doctor_evidence(c, a, credit_notes=(dataclasses.replace(
                    ev.credit_notes[0], net=ev.credit_notes[0].net + D("1.00")),) + ev.credit_notes[1:])))
    out.append(("cumulative_reversal_bounded", "a note reversing more than the sale it names",
                _doctor_evidence(c, a, credit_notes=(dataclasses.replace(
                    ev.credit_notes[0], gross=ev.credit_notes[0].gross + D("100000.00")),)
                    + ev.credit_notes[1:])))

    # evidence integrity
    out.append(("genuine_payment_identity", "a receipt of nothing",
                _doctor_evidence(c, a, receipts=(dataclasses.replace(ev.receipts[0], amount=D("0.00")),)
                                 + ev.receipts[1:])))
    out.append(("unambiguous_advice_binding", "an advice that binds no payment",
                _doctor_evidence(c, a, bindings={})))
    out.append(("chronology_consistent_with_policy", "a receipt dated before the world began",
                _doctor_evidence(c, a, receipts=(dataclasses.replace(ev.receipts[0], date="1999-01-01"),)
                                 + ev.receipts[1:])))
    out.append(("no_refusal_relaxed_by_layout", "a candidate carrying a threshold warning",
                _doctor_application(c, a, warnings=app.warnings + (f"{CA.WARN_UNBOUND_ADVICE}: probe",))))

    # representation integrity
    out.append(("renders_and_parses_through_shipped_boundaries", "a golden register that is not the fold's",
                _doctor_variant(c, a, golden_register="{}\n")))
    out.append(("csv_columns_declared", "an open-items file with a renamed column",
                _doctor_files(c, a, CA.OPEN_ITEMS_FILE,
                              c.public(a)[CA.OPEN_ITEMS_FILE].replace("open_balance", "balance_open", 1))))
    out.append(("string_limits_respected", "a cell over the shipped codepoint limit",
                _doctor_files(c, a, CA.CUSTOMERS_FILE,
                              c.public(a)[CA.CUSTOMERS_FILE] + "x" * 400 + "\n")))
    out.append(("delivery_envelope_respected", "a register over the delivery envelope",
                _doctor_variant(c, a, golden_register="x" * 20000)))

    # independent correctness
    other = c.application["b"]
    out.append(("private_derivation_equals_public_fold", "the other variant's fold under this variant's truth",
                _doctor_application(c, a, receipts=other.receipts, register=other.register,
                                    credit_notes=other.credit_notes)))
    out.append(("planted_repairs_match_public_reading", "a statement with no receipts on it",
                _doctor_evidence(c, a, receipts=())))

    # contrast integrity
    same = CC.DeclaredFact(name=c.declared_fact.name,
                           values={n: next(iter(c.declared_fact.values.values())) for n in VARIANTS})
    out.append(("variants_differ_in_declared_fact", "a pair declaring one value twice",
                dataclasses.replace(c, declared_fact=same)))
    out.append(("consequences_derived_not_authored", "a file the declared fact does not reach, moved",
                _doctor_files(c, "b", CA.ACCOUNTS_FILE, c.public("b")[CA.ACCOUNTS_FILE] + "# moved\n")))
    twins = dict(c.variants)
    twins["b"] = dataclasses.replace(twins[a], variant="b")
    out.append(("intended_distinction_changes", "a pair whose two variants are one world",
                dataclasses.replace(c, variants=twins,
                                    application={n: app for n in VARIANTS},
                                    evidence={n: ev for n in VARIANTS},
                                    content_digests={n: c.content_digests[a] for n in VARIANTS})))

    # population integrity
    out.append(("no_evaluator_provenance_leak", "a public file carrying the identity's label",
                _doctor_files(c, a, CA.CUSTOMERS_FILE,
                              c.public(a)[CA.CUSTOMERS_FILE] + f"# {c.identity.label()}\n")))
    return out


def test_every_gate_speaks():
    """A check that cannot fail proves nothing, and thirty-one of them prove
    nothing thirty-one times. Every declared gate gets a control that ought
    to make IT fail, and the control is required to name that gate among the
    failures — not merely to make something fail."""
    problems = []
    spoke = set()
    c = candidate()
    for gate, description, doctored in _controls(c):
        report = evaluate(doctored)
        if gate not in failed(report):
            problems.append(f"{gate}: {description} was admitted (failed: {sorted(failed(report))})")
        else:
            spoke.add(gate)
            code = G.rejection_codes()[gate]
            if code not in report.codes:
                problems.append(f"{gate}: the report does not carry its code {code}")

    # The controls that are a change to the ENGINES rather than to a
    # candidate: each one is the mistake the gate exists to catch.
    def with_patch(owner, attribute, value, gate):
        # The candidate is built BEFORE the patch, because some of these
        # patches (the reading bound) would stop it being buildable at all,
        # and what is under test is the gate's answer, not the constructor's.
        original = getattr(owner, attribute)
        try:
            setattr(owner, attribute, value)
            report = evaluate(c)
        finally:
            setattr(owner, attribute, original)
        if gate not in failed(report):
            problems.append(f"{gate}: patching {attribute} was admitted (failed: {sorted(failed(report))})")
        else:
            spoke.add(gate)
        return report

    with_patch(ADMIT, "golden_ledger_problems", lambda *a, **k: (["probe"], None),
               "golden_ledger_scores_complete")
    with_patch(ADMIT, "golden_register_problems", lambda *a, **k: ["probe"],
               "golden_register_scores_complete")
    with_patch(CA, "REFUSALS", tuple(r for r in CA.REFUSALS if r != CA.REFUSE_ORDER_SENSITIVE),
               "order_insensitive")
    # A baseline that IS the policy reaches the whole truth by definition.
    with_patch(CA, "BASELINES", CA.BASELINES + (
        CA.Baseline("probe_policy", CA.POLICY, lambda ev: True, False, "the policy itself, as a baseline"),),
        "no_binding_baseline_reaches_truth")
    # A promotion of the one diagnostic into an admission rule.
    with_patch(CA, "BASELINES", tuple(
        CA.Baseline(b.name, b.strategy, b.admitted_when, False, b.description) if b.diagnostic else b
        for b in CA.BASELINES), "diagnostic_baseline_recorded")
    # The reading bound: a VERIFICATION-LIMIT rejection, never evidence that
    # the candidate resisted anything.
    #
    # The bound is dropped to ZERO rather than to one because in this
    # population every baseline enumerates exactly one reading — the
    # amount-only branch has a single exact subset on every drawn month — so
    # a bound of one is a bound nothing crosses. Dropping it to zero forces
    # the condition without fabricating a monstrous world to cross 256 with.
    report = with_patch(CA, "MAX_BASELINE_READINGS", 0, "reading_bound_respected")
    if "VERIFICATION-LIMIT" not in report.codes:
        problems.append(f"an over-bound enumeration was recorded as {report.codes}, not VERIFICATION-LIMIT")
    if not report.verification_limited:
        problems.append("an over-bound enumeration did not mark the report verification-limited")
    if "no_binding_baseline_reaches_truth" in failed(report):
        problems.append("an over-bound enumeration was ALSO reported as a baseline reaching the truth; "
                        "decision 3 says exceeding the bound is not evidence the candidate resisted")

    # The two population gates need a POPULATION, not a candidate.
    ledger = G.PopulationLedger()
    ledger.record(c)
    if "no_public_content_collision" not in failed(evaluate(c, ledger)):
        problems.append("a pair republishing bytes already in the population was admitted")
    else:
        spoke.add("no_public_content_collision")
    elsewhere = next(name for name in SPLIT_MAP.families() if SPLIT_MAP.split_of(name) != c.identity.split)
    sibling = G.PopulationLedger()
    sibling.record(dataclasses.replace(c, template=dataclasses.replace(c.template, family=elsewhere)))
    if "no_cross_split_structural_sibling" not in failed(evaluate(c, sibling)):
        problems.append(f"a candidate whose canonical structure already appears in "
                        f"{SPLIT_MAP.split_of(elsewhere)!r} was admitted")
    else:
        spoke.add("no_cross_split_structural_sibling")

    # The one gate a doctored candidate cannot reach without also breaking
    # everything above it: the opening ledger's write-off balance.
    truth = c.truth("a")
    ledger_text = c.public("a")[CA.LEDGER_FILE]
    before = (_dt.date.fromisoformat(c.evidence["a"].period_start) - _dt.timedelta(days=1)).isoformat()
    entry = (f'\n{before} * "Probe" "A write-off carried into the period"\n'
             f'  {truth.write_off_account}  10.00 USD\n'
             f'  {truth.receivables_account}  -10.00 USD\n')
    if "zero_opening_write_off_balance" not in failed(
            evaluate(_doctor_files(c, "a", CA.LEDGER_FILE, ledger_text + entry))):
        problems.append("an opening ledger already carrying a write-off was admitted")
    else:
        spoke.add("zero_opening_write_off_balance")

    # memo/narration agreement: a statement reference naming an invoice the
    # universe does not carry.
    statement = c.public("a")[CA.STATEMENT_FILE]
    token = next((t for t in ("SI-4101", "SI-4102") if t not in statement), "SI-9999")
    doctored = _doctor_evidence(c, "a", receipts=(dataclasses.replace(
        c.evidence["a"].receipts[0], reference=f"{token} PAYMENT"),) + c.evidence["a"].receipts[1:])
    if "memo_narration_agreement" not in failed(evaluate(doctored)):
        problems.append("a statement reference naming an invoice outside the universe was admitted")
    else:
        spoke.add("memo_narration_agreement")

    silent = sorted(set(FM.family_gates()) - spoke)
    if silent:
        problems.append(f"these gates have no control that makes them speak: {silent}")
    return check(f"every one of the {len(FM.family_gates())} declared gates has a negative control that makes "
                 f"THAT gate fail and puts its own rejection code on the report, and an over-bound "
                 f"enumeration is a VERIFICATION-LIMIT rejection rather than evidence of resistance",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3b. the credit bound is the SALE, not the balance entering the period
# --------------------------------------------------------------------------
#
# Round 17, decision 4. Until preflight contract 1 the gate
# `cumulative_reversal_bounded` carried a second, wrong clause that ALSO
# rejected any credit note exceeding its invoice's OPENING BALANCE. A credit
# reverses a SALE: the customer having already paid part of that sale is not
# a reason the sale may not be credited in full. The accounting review says
# it outright — "Do not cap the credit at the unpaid balance" — and
# `cash_construct._shape_the_target_customer` was always built on the same
# rule: "The bound is the original sale, never the unpaid balance."
#
# The clause falsely refused real candidates. The census published on
# 2026-09-13 refused two parent attempts for it ALONE, neither witness naming
# any original-sale excess: 2,332.00 against an opening balance of 2,173.00,
# and 2,415.00 against 2,362.50.

#: Bowline Marine Supply Co., April 2026 — CASE 5, a SHIPPED authored task.
#: SI-3100 is an original sale of 1,080.00 which a March part payment has
#: reduced to 300.00 open, and CN-0412 credits 540.00 against it: over the
#: balance entering the period, well inside the sale. The numbers are taken
#: from that world deliberately, so that the legitimacy of the admitted case
#: here and the legitimacy of the shipped case are visibly the same fact.
BOWLINE_SALE = D("1080.00")          # SI-3100's original gross
BOWLINE_OPEN = D("300.00")           # what the March part payment left open
BOWLINE_CREDIT_NET = D("500.00")     # CN-0412, at the world's 0.08 rate
BOWLINE_CREDIT_TAX = D("40.00")
BOWLINE_CREDIT_GROSS = D("540.00")


def _one_note_against_one_sale(c, name, *, face, basis, net, tax, gross):
    """The candidate rewritten so that exactly ONE credit note names exactly
    one invoice, that invoice carrying the given original sale and opening
    balance and the note the given amounts."""
    ev = c.evidence[name]
    note = dataclasses.replace(ev.credit_notes[0], net=net, tax=tax, gross=gross)
    invoices = tuple(dataclasses.replace(inv, face_value=face, period_basis=basis)
                     if inv.invoice_id == note.invoice_id else inv
                     for inv in ev.invoices)
    return _doctor_evidence(c, name, credit_notes=(note,), invoices=invoices)


def test_a_credit_above_the_opening_balance_is_admitted():
    """The correction, both ways round: a properly supported credit ABOVE the
    opening balance is admitted, and a reversal exceeding the ORIGINAL SALE
    is still rejected under its own code."""
    problems = []
    c = candidate("cr-brindlecote")
    ev = c.evidence["a"]
    if not ev.credit_notes:
        return check("the credit bound is the sale, not the opening balance", False,
                     "the credit-residue control family drew no credit note to doctor")
    if ev.invoice(ev.credit_notes[0].invoice_id) is None:
        problems.append(f"the drawn note names {ev.credit_notes[0].invoice_id}, which is not an invoice")

    # The fixture must be the case actually at issue. A "credit above the
    # opening balance" that does not exceed the opening balance would pass
    # under the OLD rule too, and would witness nothing at all.
    if not BOWLINE_OPEN < BOWLINE_CREDIT_GROSS <= BOWLINE_SALE:
        problems.append(f"the fixture {BOWLINE_CREDIT_GROSS} is not above the opening balance "
                        f"{BOWLINE_OPEN} and within the sale {BOWLINE_SALE}")
    if BOWLINE_CREDIT_NET + BOWLINE_CREDIT_TAX != BOWLINE_CREDIT_GROSS:
        problems.append("the fixture note's net and tax are not its gross")

    # (1) ADMITTED: Bowline case 5's shape — 540.00 credited against a
    #     1,080.00 sale showing 300.00 open.
    admitted = _one_note_against_one_sale(c, "a", face=BOWLINE_SALE, basis=BOWLINE_OPEN,
                                          net=BOWLINE_CREDIT_NET, tax=BOWLINE_CREDIT_TAX,
                                          gross=BOWLINE_CREDIT_GROSS)
    findings = G._cumulative_reversal_bounded(admitted, "a")
    if findings:
        problems.append(f"a credit of {BOWLINE_CREDIT_GROSS} against an opening balance of {BOWLINE_OPEN} "
                        f"and an original sale of {BOWLINE_SALE} — the shipped Bowline case 5 — was "
                        f"rejected: {findings}")

    # (2) THE BOUND IS THE SALE, and it is inclusive. Every credit from just
    #     over the opening balance up to the sale itself is admitted; the
    #     first cent above the sale is not. This is behaviour rather than a
    #     reading of the source, so a cap reintroduced under any spelling
    #     fails here.
    for gross in (BOWLINE_OPEN + D("0.01"), BOWLINE_CREDIT_GROSS, BOWLINE_SALE):
        probe = _one_note_against_one_sale(c, "a", face=BOWLINE_SALE, basis=BOWLINE_OPEN,
                                           net=gross - BOWLINE_CREDIT_TAX, tax=BOWLINE_CREDIT_TAX,
                                           gross=gross)
        if G._cumulative_reversal_bounded(probe, "a"):
            problems.append(f"a credit of {gross} within the sale {BOWLINE_SALE} was rejected")
    over = BOWLINE_SALE + D("0.01")
    probe = _one_note_against_one_sale(c, "a", face=BOWLINE_SALE, basis=BOWLINE_OPEN,
                                       net=over - BOWLINE_CREDIT_TAX, tax=BOWLINE_CREDIT_TAX, gross=over)
    if not G._cumulative_reversal_bounded(probe, "a"):
        problems.append(f"a credit of {over} exceeding the sale {BOWLINE_SALE} was admitted")

    # (3) CUMULATIVE still means cumulative: two notes that each fit the sale
    #     but together exceed it are rejected. Removing the balance clause
    #     must not have loosened this.
    note = dataclasses.replace(ev.credit_notes[0], net=D("600.00"), tax=D("48.00"), gross=D("648.00"))
    invoices = tuple(dataclasses.replace(inv, face_value=BOWLINE_SALE, period_basis=BOWLINE_OPEN)
                     if inv.invoice_id == note.invoice_id else inv for inv in ev.invoices)
    twice = _doctor_evidence(c, "a", invoices=invoices, credit_notes=(
        note, dataclasses.replace(note, credit_note_id=note.credit_note_id + "-B", index=note.index + 1)))
    if not G._cumulative_reversal_bounded(twice, "a"):
        problems.append(f"two notes of 648.00 against one sale of {BOWLINE_SALE} were admitted: the bound "
                        f"is no longer cumulative")

    # (4) REJECTED, through the WHOLE gate and under its EXISTING code: a
    #     reversal the original sale does not support.
    code = G.rejection_codes()["cumulative_reversal_bounded"]
    if code != "ACC-CUMULATIVE-REVERSAL-BOUNDED":
        problems.append(f"the gate's rejection code moved to {code}")
    unsupported = _doctor_evidence(c, "a", credit_notes=(dataclasses.replace(
        ev.credit_notes[0], gross=ev.credit_notes[0].gross + D("100000.00")),) + ev.credit_notes[1:])
    report = evaluate(unsupported)
    if "cumulative_reversal_bounded" not in failed(report):
        problems.append(f"a note reversing more than the sale it names was admitted "
                        f"(failed: {sorted(failed(report))})")
    if code not in report.codes:
        problems.append(f"the rejection does not carry {code}: {sorted(report.codes)}")
    witness = " ".join(f.witness for f in report.findings
                       if f.gate == "cumulative_reversal_bounded")
    if not witness:
        problems.append("the rejection recorded no witness for the gate")
    if "opening balance" in witness:
        problems.append(f"a rejection still speaks of an opening balance: {witness[:200]}")

    return check("a credit note is bounded by the ORIGINAL SALE and not by the balance entering the period: "
                 "the shipped Bowline case 5's shape (540.00 against a 1,080.00 sale showing 300.00 open) is "
                 "admitted, the bound is inclusive and still cumulative, and a reversal the sale does not "
                 "support is rejected under ACC-CUMULATIVE-REVERSAL-BOUNDED",
                 not problems, "\n".join(problems))


def test_the_corrected_admission_semantics_are_versioned():
    """A population minted under the capped rule must not be confusable with
    one minted under the corrected rule. The gate implementation's version,
    the ADMISSION CONTRACT and the digest that binds the gate set all move."""
    problems = []
    if G.GATE_VERSION != 2:
        problems.append(f"GATE_VERSION is {G.GATE_VERSION}, not 2")
    if FM.FAMILY_PREFLIGHT_CONTRACT != 2:
        problems.append(f"the admission contract is {FM.FAMILY_PREFLIGHT_CONTRACT}, not 2")
    # The superseded gate set, as the 2026-09-13 record declares it. The
    # digest MUST no longer be this, or a census minted under either rule
    # could be read as the other.
    if FM.gate_set_digest() == "6b246422badd05a6":
        problems.append("the gate-set digest is still the superseded 6b246422badd05a6")
    # `gate_set_digest` cannot see a predicate's body, so only the contract
    # bump can carry this change into it. Witness that directly.
    original = FM.FAMILY_PREFLIGHT_CONTRACT
    try:
        FM.FAMILY_PREFLIGHT_CONTRACT = 1
        if FM.gate_set_digest() != "6b246422badd05a6":
            problems.append("restoring contract 1 does not restore the superseded digest, so the digest "
                            "moved for some reason other than the contract bump")
    finally:
        FM.FAMILY_PREFLIGHT_CONTRACT = original
    # The gate kept its NAME and its GROUP: this is a changed meaning under an
    # unchanged name, which is exactly why the contract had to be bumped by
    # hand rather than being noticed by the digest.
    if G.group_of("cumulative_reversal_bounded") != "accounting_integrity":
        problems.append("the gate changed group")
    if len(FM.family_gates()) != 31:
        problems.append(f"the gate set is {len(FM.family_gates())} gates, not 31")
    # The published record is preserved and NOT re-minted by this phase.
    record = ROOT / "reviews" / "cash_application_development_population_2026-09-13" / "freeze.json"
    if not record.exists():
        problems.append("the 2026-09-13 record is missing; it is the historical artifact")
    else:
        import json as _json
        declared = _json.loads(record.read_text(encoding="utf-8"))["freeze"]["declared"]
        if declared.get("gate_set_digest") != "6b246422badd05a6" or declared.get("gate_version") != 1:
            problems.append("the published 2026-09-13 record was altered; it must stay as minted")
        if declared.get("gate_set_digest") == FM.gate_set_digest():
            problems.append("the published record still matches the live gate set")
    return check("the corrected admission semantics are versioned: GATE_VERSION 2, admission contract 2, a "
                 "gate-set digest off the superseded 6b246422badd05a6, and the 2026-09-13 record preserved "
                 "unaltered as the historical artifact of the rule it was minted under",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 4. the census
# --------------------------------------------------------------------------

def test_the_census_retains_everything_decision_three_names():
    problems = []
    for shape in CC.SHAPES:
        minted = group(shape.family)
        census = minted.census
        if [a.ordinal for a in census.attempts] != list(range(len(census.attempts))):
            problems.append(f"{shape.family}: the census skips an attempt ordinal")
        if census.attempts[-1].outcome != "accepted":
            problems.append(f"{shape.family}: the census does not end in the accepted attempt")
        if census.group != minted.pair.identity.label():
            problems.append(f"{shape.family}: the census does not name its group")
        for attempt in census.attempts:
            if attempt.stage not in ("attempt", "draw", "render", "pair", "gate"):
                problems.append(f"{shape.family}: attempt {attempt.ordinal} has stage {attempt.stage!r}")
            if attempt.outcome == "refused" and not attempt.codes:
                problems.append(f"{shape.family}: refused attempt {attempt.ordinal} carries no rejection code")
            if attempt.outcome == "refused" and not attempt.witness:
                problems.append(f"{shape.family}: refused attempt {attempt.ordinal} carries no witness")
            if not attempt.components:
                problems.append(f"{shape.family}: attempt {attempt.ordinal} records no component versions")
            if attempt.stage == "gate":
                if not attempt.reading_counts:
                    problems.append(f"{shape.family}: gate attempt {attempt.ordinal} records no reading count")
                if len(attempt.content_digests) != 2:
                    problems.append(f"{shape.family}: gate attempt {attempt.ordinal} records "
                                    f"{len(attempt.content_digests)} content digests")
        accepted = census.attempts[-1]
        if accepted.readings < 1:
            problems.append(f"{shape.family}: the accepted attempt records no readings")
        if census.components.get("gate") != G.GATE_VERSION:
            problems.append(f"{shape.family}: the census does not record this gate's version")
        if census.components.get("baseline_catalogue") != "cash_application_baselines/1":
            problems.append(f"{shape.family}: the census does not record the catalogue")
        if census.split != SPLIT_MAP.split_of(shape.family):
            problems.append(f"{shape.family}: the census records split {census.split!r}")
        view = census.view()
        if set(view) < {"group", "attempts", "rejection_distribution", "components", "outcome"}:
            problems.append(f"{shape.family}: the census view is missing fields: {sorted(view)}")
    return check("every attempt's ordinal, stage, evaluated rejection codes, witness, reading count, "
                 "component versions and content digests are retained, the census names its group, and the "
                 "accepted attempt is the last row", not problems, "\n".join(problems))


def test_aggregates_are_published():
    problems = []
    censuses = [group(shape.family).census for shape in CC.SHAPES]
    figures = G.aggregate(censuses)
    for key in ("groups", "admitted_groups", "exhausted_groups", "group_acceptance_rate",
                "attempts", "accepted_attempts", "attempt_acceptance_rate", "rejection_distribution",
                "attempts_by_stage", "by_mechanism", "components"):
        if key not in figures:
            problems.append(f"the aggregate does not publish {key}")
    if figures["groups"] != len(CC.SHAPES) or figures["admitted_groups"] != len(CC.SHAPES):
        problems.append(f"the aggregate counts {figures['admitted_groups']} of {figures['groups']} admitted")
    if figures["exhausted_groups"] != 0:
        problems.append(f"{figures['exhausted_groups']} group(s) exhausted in this population")
    if figures["accepted_attempts"] != len(CC.SHAPES):
        problems.append(f"{figures['accepted_attempts']} accepted attempts over {len(CC.SHAPES)} groups")
    if set(figures["by_mechanism"]) != {shape.mechanism for shape in CC.SHAPES}:
        problems.append(f"the aggregate is not stratified by mechanism: {sorted(figures['by_mechanism'])}")

    # An exhausted group is counted, and its code is in the distribution.
    impossible = dataclasses.replace(BOUNDED_V1, max_golden_ledger_bytes=10)
    blocked = CC.identity_of(POPULATION, "fc-sedgewick", 0, impossible)
    _minted, exhausted = G.mint_population([blocked], impossible, SECRET)
    mixed = G.aggregate(censuses + list(exhausted))
    if mixed["exhausted_groups"] != 1:
        problems.append(f"an exhausted group was counted {mixed['exhausted_groups']} times")
    if G.EXHAUSTION_CODE not in mixed["rejection_distribution"]:
        problems.append(f"the rejection distribution does not carry {G.EXHAUSTION_CODE}: "
                        f"{sorted(mixed['rejection_distribution'])}")
    if not 0 < mixed["group_acceptance_rate"] < 1:
        problems.append(f"the group acceptance rate is {mixed['group_acceptance_rate']}")
    print(f"      (attempt acceptance {figures['attempt_acceptance_rate']:.3f} over {figures['attempts']} "
          f"attempts; rejections {figures['rejection_distribution']})")
    return check("aggregate acceptance rates, exhaustion counts and rejection distributions are published, "
                 "stratified by mechanism, and an exhausted group is counted rather than dropped",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 5. bounded attempts, named exhaustion, defects not drawn past
# --------------------------------------------------------------------------

def test_exhaustion_is_a_named_failed_group_and_defects_are_not_drawn_past():
    problems = []
    impossible = dataclasses.replace(BOUNDED_V1, max_golden_ledger_bytes=10)
    blocked = CC.identity_of(POPULATION, "fc-sedgewick", 0, impossible)
    message = raises(G.GroupExhausted, G.mint_group, blocked, impossible, SECRET)
    if message is None:
        problems.append("a profile no layout can satisfy still minted a group")
    else:
        if blocked.label() not in message or "EXHAUSTED" not in message:
            problems.append(f"exhaustion did not name the failed group: {message}")
        if "replacement selector" not in message:
            problems.append("exhaustion did not say that no replacement selector is drawn")
    if not issubclass(G.GroupExhausted, CC.ConstructionRefused):
        problems.append("GroupExhausted is not a ConstructionRefused, so existing callers stop seeing it")

    # The whole bounded population is retained, not just the last exception.
    _minted, censuses = G.mint_population([blocked], impossible, SECRET)
    exhausted = censuses[0]
    if exhausted.outcome != "exhausted" or exhausted.accepted_attempt is not None:
        problems.append(f"the exhausted group's census reads {exhausted.outcome}")
    if G.EXHAUSTION_CODE not in exhausted.distribution():
        problems.append(f"the exhausted census carries codes {sorted(exhausted.distribution())}")

    # Decision 3's other line: a defect is investigated, not drawn past.
    original = CC.derive_contract
    calls = []

    def boom(world, task):
        calls.append(task.id)
        raise TypeError("an unexpected exception")
    try:
        CC.derive_contract = boom
        message = raises(TypeError, G.mint_group, CC.identity_of(POPULATION, "fc-sedgewick", 0),
                         BOUNDED_V1, SECRET)
    finally:
        CC.derive_contract = original
    if message is None or message.startswith("!!"):
        problems.append(f"an unexpected exception did not reach the caller: {message}")
    if len(calls) != 1:
        problems.append(f"an unexpected exception produced {len(calls)} derivation calls, not 1: it was "
                        f"reclassified as expected and drawn past")

    # A gate that cannot be evaluated stops the mint rather than admitting.
    original_checks = dict(G.VARIANT_CHECKS)
    try:
        G.VARIANT_CHECKS.pop("ar_reconciles")
        if raises(G.GateUnavailable, G.mint_group, CC.identity_of(POPULATION, "fc-sedgewick", 0),
                  BOUNDED_V1, SECRET) is None:
            problems.append("a group was minted while a declared gate had no implementation")
    finally:
        G.VARIANT_CHECKS.clear()
        G.VARIANT_CHECKS.update(original_checks)
    return check(f"the attempt loop is bounded at {MAX_LAYOUT_ATTEMPTS}, exhaustion is a NAMED failed group "
                 f"that draws no replacement selector and is retained in the census, an unexpected exception "
                 f"reaches the caller after one attempt, and an unevaluable gate stops the mint",
                 not problems, "\n".join(problems))


def test_the_declared_roles_are_what_the_diagnostic_gate_compares_against():
    """Decision 3: "`number_order` is diagnostic in the shipped catalogue; do
    not silently promote it into an admission rule."

    The gate that says so must not take both of its sides from
    `CA.BASELINES`: that compares the tuple with itself and admits whatever
    it says. The probe here is the one a self-comparison passes — a SWAP,
    `number_order` promoted into the binding set and a binding baseline
    demoted to keep a diagnostic in the catalogue, leaving the counts intact
    and the shape plausible.
    """
    problems = []
    declared = dict(FM.BASELINE_CATALOGUE_ROLES)
    if declared.get("number_order") != "diagnostic" or FM.declared_role_counts() != {"binding": 9,
                                                                                     "diagnostic": 1}:
        problems.append(f"{FM.BASELINE_CATALOGUE_ID} declares {FM.declared_role_counts()} with "
                        f"number_order {declared.get('number_order')!r}, not nine binding and "
                        f"number_order diagnostic")
    if FM.catalogue_role_findings():
        problems.append(f"the shipped catalogue already disagrees with its declaration: "
                        f"{FM.catalogue_role_findings()}")
    c = candidate()
    original = CA.BASELINES

    def with_roles(swap: dict, what: str):
        try:
            CA.BASELINES = tuple(
                CA.Baseline(b.name, b.strategy, b.admitted_when, swap[b.name] == "diagnostic", b.description)
                if b.name in swap else b for b in original)
            if not FM.catalogue_role_findings():
                problems.append(f"{what}: catalogue_role_findings() saw nothing")
            report = evaluate(c)
            if "diagnostic_baseline_recorded" not in failed(report):
                problems.append(f"{what} was admitted by the gate (failed: {sorted(failed(report))})")
            if "BAS-DIAGNOSTIC-BASELINE-RECORDED" not in report.codes:
                problems.append(f"{what} carries codes {report.codes}")
        finally:
            CA.BASELINES = original

    with_roles({"number_order": "binding", "write_off_nothing": "diagnostic"},
               "number_order promoted into the binding set, write_off_nothing demoted to keep the counts")
    with_roles({"credit_ignored": "diagnostic"}, "a binding baseline quietly made diagnostic")
    if FM.catalogue_role_findings():
        problems.append("the shipped catalogue did not return to its declared roles after the probes")
    if evaluate(c).passed is False:
        problems.append("the undoctored candidate no longer passes after the probes")
    return check("the diagnostic gate compares the recorded roles and the binding/diagnostic COUNTS against "
                 "cash_application_baselines/1's own declaration, so a swap that promotes number_order into "
                 "an admission rule while keeping one diagnostic is rejected rather than admitted",
                 not problems, "\n".join(problems))


def test_the_verification_limit_records_the_count_it_exists_to_record():
    """Decision 3 gives the reading bound "its own code" and requires every
    attempt's READING COUNT retained. The attempt that exceeded the bound is
    the one whose count is the finding, so it may not be the one attempt that
    records no baselines, no counts and a second untrue rejection reason."""
    problems = []
    c = candidate()
    original = CA.MAX_BASELINE_READINGS
    try:
        CA.MAX_BASELINE_READINGS = 0
        report = evaluate(c)
    finally:
        CA.MAX_BASELINE_READINGS = original
    if not report.verification_limited or "VERIFICATION-LIMIT" not in report.codes:
        problems.append(f"an over-bound enumeration recorded {report.codes}")
    if "BAS-DIAGNOSTIC-BASELINE-RECORDED" in report.codes:
        problems.append("an over-bound enumeration ALSO reported the diagnostic as unrecorded: a census "
                        "reader counting rejections sees a second, untrue reason")
    if "no_binding_baseline_reaches_truth" in failed(report):
        problems.append("an over-bound enumeration was reported as a baseline reaching the truth")
    # Gate (o)'s OWN codes are the claim here. The probe drops a global to
    # zero, so the fold itself cannot run either and `order_insensitive` also
    # speaks — an artifact of patching the bound rather than a property of an
    # over-bound candidate, and the census would not carry it on a real one,
    # since the policy fold does not branch. Said plainly rather than hidden
    # by asserting only what suits.
    stray = [code for code in report.codes if code.startswith("BAS-") or code == "VERIFICATION-LIMIT"]
    if stray != ["VERIFICATION-LIMIT"]:
        problems.append(f"gate (o) recorded {stray}, not the verification limit alone")
    if set(failed(report)) - {"reading_bound_respected", "order_insensitive"}:
        problems.append(f"the probe failed gates beyond the bound and the fold it also disables: "
                        f"{sorted(failed(report))}")
    for name in VARIANTS:
        seen = [o for o in report.baselines if o.variant == name]
        if {o.name for o in seen} != {b.name for b in CA.BASELINES}:
            problems.append(f"{name}: the limited attempt observed {sorted(o.name for o in seen)}")
        if not any(o.limited for o in seen):
            problems.append(f"{name}: no baseline was marked as having crossed the bound")
        for o in seen:
            if o.limited and o.readings < 1:
                problems.append(f"{name}: {o.name} crossed the bound and recorded {o.readings} readings")
        if not report.reading_counts.get(name):
            problems.append(f"{name}: the limited attempt retained no reading counts")
    witness = report.baseline_witness()
    if "reading-bound" not in witness or not any(b.name in witness for b in CA.BASELINES):
        problems.append(f"the verification-limit witness names no baseline: {witness!r}")
    attempt = G._attempt_from_report(0, c, report, "probe")
    if attempt.outcome != "refused" or "VERIFICATION-LIMIT" not in attempt.codes:
        problems.append(f"the census row reads {attempt.outcome} with codes {attempt.codes}")
    if not attempt.reading_counts or attempt.readings < 1:
        problems.append(f"the census row retained {len(attempt.reading_counts)} reading counts and "
                        f"{attempt.readings} readings")
    return check("an attempt whose enumeration crossed the reading bound still retains every baseline's "
                 "observation and reading count, names the baseline that crossed it and the count it "
                 "reached, and carries VERIFICATION-LIMIT as gate (o)'s ONLY code — no second, untrue "
                 "reason in the census's rejection distribution", not problems, "\n".join(problems))


def test_a_population_may_not_declare_one_identity_twice():
    """Two admitted pairs under one construction identity would bind one
    identity digest to two family-manifest records, name two groups the same
    thing, and overwrite each other in a census keyed by that name."""
    problems = []
    ident = CC.identity_of(POPULATION, "cr-brindlecote", 0)
    ledger = G.PopulationLedger()
    message = raises(G.PopulationDefect, G.mint_population, [ident, ident], BOUNDED_V1, SECRET, ledger)
    if message is None or message.startswith("!!"):
        problems.append(f"a population declaring one identity twice was minted: {message}")
    else:
        if ident.label() not in message:
            problems.append(f"the refusal does not name the repeated group: {message}")
        if ledger.groups():
            problems.append(f"the repeated identity was refused only after {len(ledger.groups())} group(s) "
                            f"were already minted into the population")
    if not issubclass(G.PopulationDefect, G.GateUnavailable):
        problems.append("PopulationDefect is not a GateUnavailable, so a caller failing closed on one does "
                        "not fail closed on the other")
    minted, censuses = G.mint_population([ident, CC.identity_of(POPULATION, "cr-brindlecote", 1)],
                                         BOUNDED_V1, SECRET, G.PopulationLedger())
    if len(minted) != 2 or len({m.census.group for m in minted}) != 2:
        problems.append(f"two distinct identities minted {len(minted)} group(s): {[c.group for c in censuses]}")
    return check("a population that declares one construction identity twice is refused as a defect before "
                 "anything is minted, and two distinct identities still mint two named groups",
                 not problems, "\n".join(problems))


def test_one_ledger_may_not_admit_one_identity_twice():
    """`mint_population` pre-checks a DECLARED list. A caller minting group by
    group has no list to pre-check, so the population ledger — which IS the
    population for everything minted through `mint_group` — has to be the
    register that refuses. Without this, the second mint's attempt 0 is
    refused for republishing the first pair's bytes and its attempt 1 is
    ADMITTED, leaving two pairs under one group name and one identity digest:
    exactly what `PopulationDefect` says must never happen.
    """
    problems = []
    ident = CC.identity_of(POPULATION, "fc-sedgewick", 1)
    ledger = G.PopulationLedger()
    first = G.mint_group(ident, BOUNDED_V1, SECRET, ledger)
    if first.census.outcome != "admitted" or len(ledger.groups()) != 1:
        problems.append(f"the first mint was {first.census.outcome} and left {len(ledger.groups())} "
                        f"group(s) in the ledger")
    message = raises(G.PopulationDefect, G.mint_group, ident, BOUNDED_V1, SECRET, ledger)
    if message is None or message.startswith("!!"):
        problems.append(f"the same construction identity was admitted into one ledger twice: {message}")
    else:
        if ident.label() not in message:
            problems.append(f"the refusal does not name the repeated group: {message}")
        if "positions 0 and 1" not in message:
            problems.append(f"the refusal does not name both positions: {message}")
    if [g[0] for g in ledger.groups()] != [ident.label()]:
        problems.append(f"the refused repeat still reached the population: {[g[0] for g in ledger.groups()]}")

    # The register said no to the REPEAT, not to everything after it, and it
    # mutated nothing on the way out: a distinct identity still goes in.
    other = CC.identity_of(POPULATION, "fc-sedgewick", 2)
    G.mint_group(other, BOUNDED_V1, SECRET, ledger)
    if [g[0] for g in ledger.groups()] != [ident.label(), other.label()]:
        problems.append(f"after the refusal the ledger holds {[g[0] for g in ledger.groups()]}, not the "
                        f"first pair and the next distinct one")
    return check("minting one construction identity twice into one population ledger is refused as a "
                 "PopulationDefect naming both positions, the refused repeat leaves the population "
                 "unchanged, and a distinct identity still mints after it", not problems,
                 "\n".join(problems))


def test_the_pair_is_the_unit_of_rejection():
    """Decision 3: "Reject BOTH variants when either fails any acceptance
    condition." A finding on one variant must reject the pair, not the
    variant."""
    problems = []
    c = candidate()
    for name in VARIANTS:
        doctored = _doctor_application(c, name, closing_ar=c.application[name].closing_ar + D("1.00"))
        report = evaluate(doctored)
        if report.passed:
            problems.append(f"a finding on variant {name} left the pair admitted")
        variants = {f.variant for f in report.findings if f.gate == "ar_reconciles"}
        if variants != {name}:
            problems.append(f"a finding on variant {name} was attributed to {variants}")
    return check("a finding on either variant rejects the PAIR, and the census records which variant it was "
                 "found on", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 6. the ruling's own words
# --------------------------------------------------------------------------

MINTING_DOCSTRING = (
    "Candidate construction, attempt order, acceptance, rejection, profile assignment and split membership "
    "are determined solely by the frozen generation specification and declared model-independent checks. No "
    "learned-model output, score, success or failure label, token usage or trajectory may influence those "
    "decisions. All bounded attempts and evaluated rejection reasons are retained. Model observations may "
    "motivate a separately versioned future specification; they may not select or alter members of this "
    "version."
)


def test_the_minting_docstring_is_verbatim():
    problems = []
    doc = G.mint_group.__doc__ or ""
    head = doc.split("\n\n    ---", 1)[0]
    flattened = " ".join(head.split())
    if flattened != MINTING_DOCSTRING:
        problems.append(f"the minting docstring reads:\n{flattened}\n\nand the ruling's paragraph is:\n"
                        f"{MINTING_DOCSTRING}")
    return check("the ruling's minting paragraph is in the minting function's docstring, verbatim",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 7. the baseline catalogue, versioned independently
# --------------------------------------------------------------------------

def test_the_catalogue_digest_binds_predicate_bodies_not_names():
    problems = []
    if FM.BASELINE_CATALOGUE_ID != "cash_application_baselines/1":
        problems.append(f"the catalogue is {FM.BASELINE_CATALOGUE_ID!r}")
    view = FM.baseline_catalogue_view()
    if any(not b.get("admitted_when_code") for b in view["baselines"]):
        problems.append("a baseline records no digest of its admission predicate")
    before = FM.baseline_catalogue_digest()

    # The mistake the name-only digest could not see: an admission predicate
    # edited under an UNCHANGED name, so the baseline is admitted against a
    # different set of candidates and every record still verifies.
    target = next(b for b in CA.BASELINES if b.name == "credit_ignored")

    def probe(ev):                                           # the same NAME, a different predicate
        return len(ev.credit_notes) > 1
    probe.__name__ = target.admitted_when.__name__
    original = CA.BASELINES
    try:
        CA.BASELINES = tuple(CA.Baseline(b.name, b.strategy, probe, b.diagnostic, b.description)
                             if b.name == "credit_ignored" else b for b in original)
        if FM.baseline_catalogue_digest() == before:
            problems.append("editing an admission predicate's BODY under an unchanged name did not move the "
                            "catalogue digest")
        names = {b["admitted_when"] for b in FM.baseline_catalogue_view()["baselines"]}
        if target.admitted_when.__name__ not in names:
            problems.append("the probe changed the predicate's name, so it does not witness what it claims")
    finally:
        CA.BASELINES = original
    if FM.baseline_catalogue_digest() != before:
        problems.append("the catalogue digest did not return to its value after the probe")
    return check("the baseline catalogue is versioned as cash_application_baselines/1 and its digest binds "
                 "the admission predicates THEMSELVES: editing one's body under an unchanged name moves it",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 8. determinism, and the frozen neighbours
# --------------------------------------------------------------------------

def test_minting_is_deterministic_in_the_identity_and_the_secret():
    problems = []
    ident = CC.identity_of(POPULATION, "cr-brindlecote", 0)
    first = G.mint_group(ident, BOUNDED_V1, SECRET)
    again = G.mint_group(ident, BOUNDED_V1, SECRET)
    if first.pair.variants["a"].public_files != again.pair.variants["a"].public_files:
        problems.append("two mints of one identity under one secret produced different public bytes")
    if [a.view() for a in first.census.attempts] != [a.view() for a in again.census.attempts]:
        problems.append("two mints of one identity under one secret produced different censuses")
    other = G.mint_group(ident, BOUNDED_V1, b"a-quite-different-phase-c-secret-000000000000")
    if other.pair.variants["a"].public_files == first.pair.variants["a"].public_files:
        problems.append("the secret does not reach the drawn world")
    seed = parent_seed(ident, SECRET)
    surfaces = {}
    for name in VARIANTS:
        variant = first.pair.variants[name]
        surfaces.update({f"{name}/{k}": v for k, v in variant.public_files.items()})
        surfaces[f"{name}/task_id"] = variant.task.id
    leaks = [token for token in private_tokens(ident, seed)
             if any(token in text for text in surfaces.values())]
    if leaks:
        problems.append(f"a private construction token reached a surface: {leaks}")
    return check("minting is a pure function of the construction identity, the profile and the secret — the "
                 "same world and the same census every time, a different world under another secret, and no "
                 "private selector on any surface", not problems, "\n".join(problems))


def test_the_frozen_neighbours_did_not_move():
    problems = []
    if BANK_MINT.GENERATOR_VERSION != 9:
        problems.append(f"the bank generator is at version {BANK_MINT.GENERATOR_VERSION}, not 9")
    components = FM.semantic_components()
    if "generator_version" in components or any("GENERATOR" in str(k) for k in components):
        problems.append("the cash family's semantic components name the bank generator's version")
    from beancount_ledger.graph.worlds import CASH_APPLICATION_REGISTRY
    if len(CASH_APPLICATION_REGISTRY) != 11:
        problems.append(f"the authored population holds {len(CASH_APPLICATION_REGISTRY)} tasks, not eleven")
    authored = set(CASH_APPLICATION_REGISTRY)
    generated = {group(shape.family).pair.variants[name].task.id
                 for shape in CC.SHAPES for name in VARIANTS}
    if authored & generated:
        problems.append(f"a generated task took an authored id: {sorted(authored & generated)}")
    for family in SPLIT_MAP.families():
        if family in authored:
            problems.append(f"the authored task {family} is inside the generated population's split map")
    return check("GENERATOR_VERSION 9 is untouched and uncoupled, the eleven authored cash tasks stay outside "
                 "the generated population, and no generated task takes an authored id",
                 not problems, "\n".join(problems))


TESTS = [
    test_every_declared_gate_is_implemented_and_carries_its_own_code,
    test_every_family_mints_with_every_gate_true,
    test_gate_o_runs_at_mint_time_on_both_variants,
    test_every_gate_speaks,
    test_a_credit_above_the_opening_balance_is_admitted,
    test_the_corrected_admission_semantics_are_versioned,
    test_the_census_retains_everything_decision_three_names,
    test_aggregates_are_published,
    test_exhaustion_is_a_named_failed_group_and_defects_are_not_drawn_past,
    test_the_declared_roles_are_what_the_diagnostic_gate_compares_against,
    test_the_verification_limit_records_the_count_it_exists_to_record,
    test_a_population_may_not_declare_one_identity_twice,
    test_one_ledger_may_not_admit_one_identity_twice,
    test_the_pair_is_the_unit_of_rejection,
    test_the_minting_docstring_is_verbatim,
    test_the_catalogue_digest_binds_predicate_bodies_not_names,
    test_minting_is_deterministic_in_the_identity_and_the_secret,
    test_the_frozen_neighbours_did_not_move,
]


def main() -> int:
    results = [test() for test in TESTS]
    passed = sum(1 for r in results if r)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
