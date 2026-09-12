"""Phase B of the generated cash-application population: `bounded-v1`
enforced, and the construction path that renders a candidate pair.

Round 16, decision 4. What is witnessed here:

  * the roster and the recipes agree in BOTH directions — a family cannot be
    sealed into the split map without a recipe, nor drawn without a split —
    and every declared shape already sits inside `bounded-v1`;
  * every one of the fifteen families renders a PAIR from its identity, with
    the eleven public files, the private truth register, the golden ledger
    and the golden register for each variant, inside the bounded attempt
    loop, and the census of attempts is retained;
  * the pair differs in exactly ONE declared authored fact, every other
    difference is a consequence of it, and the files that move are only the
    ones that fact reaches — for the advice-residue stratum that is a single
    cell of `remittance_advice.csv`, with the statement, the ledger and the
    golden ledger byte-identical across the pair;
  * both polarities appear in every stratum, so "always report a residue" is
    never a winning habit;
  * decision 4's whole table holds on every rendered variant, and the
    measurements are structural: no field of a `Measurement` is a difficulty,
    and neither module claims one;
  * manufactured difficulty is VALIDATED absent, with a NEGATIVE CONTROL for
    each of the eight conditions — a check that cannot speak is a check that
    proves nothing;
  * the public fold equals the private truth, and both goldens score complete
    through the ACTUAL `candidate/1`, `application/1` and `composite/1`;
  * no binding gate-(o) baseline reaches the truth and the 256-reading bound
    holds, with the diagnostic reading recorded rather than refused;
  * construction is deterministic in the identity and the secret, and no
    private selector or seed reaches the agent's surface;
  * exhaustion is a NAMED failed group, and an out-of-range attempt is
    refused;
  * the population has no public-content collision and no cross-split
    structural sibling, and the eleven authored variants stay outside it.

    python tests/test_cash_construction.py
"""

from __future__ import annotations

import dataclasses
import sys
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from beancount_ledger.candidate import application as APP  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate import composite as X  # noqa: E402
from beancount_ledger.graph import cash_application as CA  # noqa: E402
from beancount_ledger.graph import cash_construct as CC  # noqa: E402
from beancount_ledger.graph import cash_profile as PROFILE  # noqa: E402
from beancount_ledger.graph.cash_identity import (  # noqa: E402
    BOUNDED_V1,
    MAX_LAYOUT_ATTEMPTS,
    MECHANISMS,
    VARIANTS,
    identity_leaks,
    parent_seed,
    private_tokens,
)
from beancount_ledger.graph.cash_manifest import public_content_digest  # noqa: E402
from beancount_ledger.graph.cash_split import (  # noqa: E402
    SPLIT_MAP,
    TEMPLATE_ROSTER,
    StructuralAliasError,
    StructureLedger,
)
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.schema import AppliedReceipt, Sale  # noqa: E402
from beancount_ledger.graph.worlds import CASH_APPLICATION_REGISTRY, REGISTRY  # noqa: E402

from world_checks import check_world_task  # noqa: E402

#: A fixed secret, so the suite draws the same population on every machine and
#: never depends on — or touches — the evaluator's provisioned key.
SECRET = b"cash-application-phase-b-test-secret-0123456789"
OTHER_SECRET = b"a-quite-different-phase-b-test-secret-98765432"

POPULATION = "phase-b-suite"
ONE, ZERO = D("1.000000"), D("0.000000")

#: The files a pair's ONE declared fact reaches, per mechanism. Anything else
#: moving would mean the two variants are two company-months rather than two
#: readings of one.
CONSEQUENCES = {
    "fallback_continuation": {"bank_statement.csv", "ledger.beancount"},
    "credit_residue": {"credit_notes.csv", "ledger.beancount"},
    "advice_residue": {"remittance_advice.csv"},
}

_PAIRS: dict = {}


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


def pair(family: str, index: int = 0, secret: bytes = SECRET):
    """One parent group, cached: the suite reads each pair many times and
    `candidate_pair` is a pure function of the identity and the secret."""
    key = (family, index, secret)
    if key not in _PAIRS:
        ident = CC.identity_of(POPULATION, family, index)
        _PAIRS[key] = CC.candidate_pair(ident, secret=secret)
    return _PAIRS[key]


def every_pair(index: int = 0):
    return [pair(shape.family, index) for shape in CC.SHAPES]


def every_variant(index: int = 0):
    for group in every_pair(index):
        for name in VARIANTS:
            yield group, group.variant(name)


# --------------------------------------------------------------------------
# 1. the roster, the recipes and the declared shapes
# --------------------------------------------------------------------------

def test_the_roster_and_the_recipes_agree_in_both_directions():
    """A family sealed into the split map with no recipe could never be
    drawn; a recipe with no seal could be drawn into no split. Both are
    silent failures, so both are checked."""
    problems = []
    sealed = {entry.name: entry.mechanism for entry in TEMPLATE_ROSTER}
    declared = {shape.family: shape.mechanism for shape in CC.SHAPES}
    for name in sorted(set(sealed) - set(declared)):
        problems.append(f"{name} is sealed into the split map and `cash_construct` has no recipe for it")
    for name in sorted(set(declared) - set(sealed)):
        problems.append(f"{name} has a recipe and the split map does not carry it, so it can be drawn into "
                        f"no split")
    for name in sorted(set(sealed) & set(declared)):
        if sealed[name] != declared[name]:
            problems.append(f"{name} is sealed under {sealed[name]!r} and its shape declares {declared[name]!r}")
    counts = {mechanism: 0 for mechanism in MECHANISMS}
    for shape in CC.SHAPES:
        counts[shape.mechanism] += 1
    if set(counts.values()) != {5}:
        problems.append(f"the strata carry {counts} families, not five each")
    for shape in CC.SHAPES:
        if not BOUNDED_V1.invoices[0] <= shape.invoices <= BOUNDED_V1.invoices[1]:
            problems.append(f"{shape.family} declares {shape.invoices} invoices, outside bounded-v1")
        if not BOUNDED_V1.customers[0] <= shape.customers <= BOUNDED_V1.customers[1]:
            problems.append(f"{shape.family} declares {shape.customers} customers, outside bounded-v1")
        if not BOUNDED_V1.receipts[0] <= shape.receipts <= BOUNDED_V1.receipts[1]:
            problems.append(f"{shape.family} declares {shape.receipts} receipts, outside bounded-v1")
        if not BOUNDED_V1.invoices_raised_in_period[0] <= sum(shape.raised) \
                <= BOUNDED_V1.invoices_raised_in_period[1]:
            problems.append(f"{shape.family} raises {sum(shape.raised)} invoices in the month, outside bounded-v1")
        if len(shape.plants) != BOUNDED_V1.ledger_plants[0]:
            problems.append(f"{shape.family} declares {len(shape.plants)} plants, not two")
        for _kind, slot in shape.plants:
            if not 0 <= slot < shape.receipts:
                problems.append(f"{shape.family} plants on receipt slot {slot}, which it does not build")
    # A family the map does not carry cannot produce an identity at all.
    if raises(Exception, CC.identity_of, POPULATION, "no-such-family", 0) is None:
        problems.append("an identity was minted for a family the roster does not declare")
    return check("the fifteen sealed families and the fifteen recipes are the same fifteen, agree on their "
                 "mechanism, declare shapes already inside bounded-v1, and carry two plants on receipts they "
                 "actually build", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 2. rendering a pair
# --------------------------------------------------------------------------

def test_every_family_renders_a_pair_with_the_four_artifacts():
    problems = []
    for group in every_pair():
        if set(group.variants) != set(VARIANTS):
            problems.append(f"{group.family}: variants {sorted(group.variants)}")
        if not 0 <= group.attempt < MAX_LAYOUT_ATTEMPTS:
            problems.append(f"{group.family}: attempt {group.attempt} outside the bounded range")
        if not group.census or group.census[-1].outcome != "accepted":
            problems.append(f"{group.family}: the census does not end in the accepted attempt")
        if [record.ordinal for record in group.census] != list(range(len(group.census))):
            problems.append(f"{group.family}: the census skips an attempt ordinal")
        for name in VARIANTS:
            variant = group.variant(name)
            if len(variant.public_files) != 11:
                problems.append(f"{group.family}/{name}: {len(variant.public_files)} public files, not eleven")
            if variant.truth is None or not variant.truth.register:
                problems.append(f"{group.family}/{name}: no private truth register")
            if not variant.golden_ledger.strip() or not variant.golden_register.strip():
                problems.append(f"{group.family}/{name}: a golden artifact is empty")
            stem = CC.public_stem(parent_seed(group.identity, SECRET))
            if variant.task.id != f"cash_application_g{stem}{name}":
                problems.append(f"{group.family}/{name}: the public id is {variant.task.id}, not the keyed "
                                f"stem's cash_application_g{stem}{name}")
            if group.identity.digest()[:8] in variant.task.id or group.identity.digest()[:8] in variant.world.id:
                problems.append(f"{group.family}/{name}: a public name carries the identity digest, which is "
                                f"an unkeyed function of an enumerable selector")
        # the whole world checker, every gate a hand-authored world must pass
        for name in VARIANTS:
            variant = group.variant(name)
            found, _warnings = check_world_task(variant.world, variant.task)
            problems += [f"{group.family}/{name}: {line}" for line in found]
    return check("every family renders a pair from its identity — eleven public files, a private truth "
                 "register, a golden ledger and a golden register per variant — inside the bounded attempt "
                 "loop, with the attempt census retained, and every gate the world checker runs passes",
                 not problems, "\n".join(problems))


def test_the_pair_differs_in_exactly_one_declared_fact():
    problems = []
    for group in every_pair():
        fact = group.declared_fact
        if not fact.differs():
            problems.append(f"{group.family}: the declared fact {fact.name} reads {fact.values}")
        a, b = group.variant("a"), group.variant("b")
        moved = {name for name in a.public_files if a.public_files[name] != b.public_files[name]}
        expected = CONSEQUENCES[group.mechanism]
        if moved != expected:
            problems.append(f"{group.family}: the files that move are {sorted(moved)}, not {sorted(expected)}")
        if a.truth.application_key() == b.truth.application_key():
            problems.append(f"{group.family}: the intended accounting distinction does not change the register")
        if group.mechanism == "advice_residue" and a.golden_ledger != b.golden_ledger:
            problems.append(f"{group.family}: an advice cell moved the ledger; the money the bank showed did not "
                            f"change, so the books must not either")
        if a.golden_register == b.golden_register:
            problems.append(f"{group.family}: both variants deliver the same register")
    return check("a pair differs in exactly one declared authored fact, the public files that move are only "
                 "the ones that fact reaches, the register really changes, and an advice-residue pair leaves "
                 "the statement, the ledger and the golden ledger byte-identical",
                 not problems, "\n".join(problems))


def test_both_polarities_appear_in_every_stratum():
    problems = []
    seen = {mechanism: set() for mechanism in MECHANISMS}
    for group in every_pair():
        shown = {}
        for name in VARIANTS:
            shown[name] = PROFILE.polarity_of(group.mechanism, group.variant(name).measurement)
        seen[group.mechanism] |= set(shown.values())
        if set(shown.values()) != {True, False}:
            problems.append(f"{group.family}: the pair shows polarities {shown}")
        problems += PROFILE.polarity_problems(group.mechanism,
                                              {n: group.variant(n).measurement for n in VARIANTS})
    for mechanism, polarities in seen.items():
        if polarities != {True, False}:
            problems.append(f"{mechanism} only ever shows {polarities}")
    return check("each mechanism stratum carries both its positive condition and its zero-residue or "
                 "no-continuation counterpart, so always reporting a residue is never a winning habit",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3. decision 4's table, and what a measurement is not
# --------------------------------------------------------------------------

def test_decision_fours_bounds_hold_on_every_rendered_variant():
    problems = []
    for group, variant in every_variant():
        problems += [f"{group.family}/{variant.variant}: {line}"
                     for line in PROFILE.bound_problems(variant.measurement)]
        problems += [f"{group.family}/{variant.variant}: {line}"
                     for line in PROFILE.excluded_accounting_problems(variant.world)]
        measurement = variant.measurement
        if measurement.unpaid_in_period_invoices < 1:
            problems.append(f"{group.family}/{variant.variant}: no in-period invoice is left unpaid")
        if measurement.dependency_depth < 2:
            problems.append(f"{group.family}/{variant.variant}: dependency depth {measurement.dependency_depth}; "
                            f"no invoice is settled across two evidenced events, so the month exercises no "
                            f"customer-specific balance at all")
    # A bound that cannot fail is not a bound: move one and watch it speak.
    sample = pair("fc-sedgewick").variant("a").measurement
    for field, value in (("invoices", 20), ("receipts", 9), ("dependency_depth", 7),
                         ("golden_register_bytes", 99_000), ("unpaid_in_period_invoices", 0),
                         ("max_allocations_per_receipt", 9), ("currency", "EUR")):
        if not PROFILE.bound_problems(dataclasses.replace(sample, **{field: value})):
            problems.append(f"bounded-v1 admits a variant whose {field} is {value!r}")
    return check("every rendered variant satisfies decision 4's whole table — period, currency, customers, "
                 "invoice universe, in-period invoices, receipts, credit notes, plants, allocations, "
                 "dependency depth and both golden envelopes — keeps the retained accounting exclusions, "
                 "leaves an in-period invoice unpaid, and each bound refuses a variant that breaks it",
                 not problems, "\n".join(problems))


def test_a_measurement_describes_what_was_generated_and_claims_nothing_else():
    """Decision 4: "Structural measurements describe what was generated.
    'Harder for model X' requires a comparison under fixed measurement
    conditions; it cannot be assigned by invoice count." So: no difficulty
    field, no ordering by one, and no prose asserting one."""
    problems = []
    fields = set(PROFILE.Measurement.__dataclass_fields__)
    for word in ("difficulty", "hardness", "score", "rank", "harder"):
        leaked = sorted(name for name in fields if word in name)
        if leaked:
            problems.append(f"a Measurement carries {leaked}, which is not a structural quantity")
    # Decision 3 dictates the minting docstring word for word. It is the one
    # place the no-model-influence rule is stated, so it is checked verbatim
    # rather than paraphrased.
    ruled = ("Candidate construction, attempt order, acceptance, rejection, profile assignment and split "
             "membership are determined solely by the frozen generation specification and declared "
             "model-independent checks. No learned-model output, score, success or failure label, token usage "
             "or trajectory may influence those decisions. All bounded attempts and evaluated rejection "
             "reasons are retained. Model observations may motivate a separately versioned future "
             "specification; they may not select or alter members of this version.")
    flattened = " ".join((CC.__doc__ or "").split())
    if ruled not in flattened:
        problems.append("the minting docstring does not carry decision 3's paragraph verbatim")
    # Nothing scores an instance: `measure` returns structural values only,
    # and the one function named after difficulty is a VALIDATOR that returns
    # the ways a candidate is manufactured, never a number.
    sample_variant = pair("fc-lintelgate").variant("a")
    values = PROFILE.measure(sample_variant.world, sample_variant.task, sample_variant.inputs).view()
    for key, value in values.items():
        if not isinstance(value, (int, bool, str)):
            problems.append(f"Measurement.{key} is a {type(value).__name__}, not a structural quantity")
    verdict = PROFILE.difficulty_problems(sample_variant.world, sample_variant.task, sample_variant.inputs)
    if not isinstance(verdict, list):
        problems.append(f"difficulty_problems returns a {type(verdict).__name__}; it is a validator, and a "
                        f"number here would be a difficulty score by another name")
    if BOUNDED_V1.name != "bounded-v1" or "hard" in BOUNDED_V1.name:
        problems.append(f"the profile is named {BOUNDED_V1.name!r}")
    for shape in CC.SHAPES:
        if "hard" in shape.family:
            problems.append(f"{shape.family} names itself hard")
    # Every quantity a Measurement reports is reproducible from the rendered
    # artifacts alone, so it describes them rather than the recipe.
    group = pair("cr-gallowtree")
    variant = group.variant("a")
    again = PROFILE.measure(variant.world, variant.task, variant.inputs)
    if again != variant.measurement:
        problems.append("measuring the same rendered variant twice gave two answers")
    return check("a Measurement is counts, sizes and depths taken from the rendered artifacts; it carries no "
                 "difficulty, no score and no ordering, neither module claims an instance is harder for any "
                 "model, and the profile is not called hard", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 4. manufactured difficulty, validated absent
# --------------------------------------------------------------------------

def test_manufactured_difficulty_is_absent_on_every_variant():
    problems = []
    for group, variant in every_variant():
        problems += [f"{group.family}/{variant.variant}: {line}"
                     for line in PROFILE.difficulty_problems(variant.world, variant.task, variant.inputs)]
    # a condition the profile forbids and nothing validates is itself refused
    tweaked = dataclasses.replace(BOUNDED_V1,
                                  forbidden_difficulty=BOUNDED_V1.forbidden_difficulty + ("invented_condition",))
    group = pair("ar-quillmarsh")
    variant = group.variant("a")
    spoken = PROFILE.difficulty_problems(variant.world, variant.task, variant.inputs, tweaked)
    if not any("invented_condition" in line for line in spoken):
        problems.append("a forbidden condition with no check passed silently, which is the assumption the "
                        "requirement to VALIDATE exists to prevent")
    return check("no rendered variant carries any of decision 4's eight manufactured-difficulty conditions, "
                 "and a condition the profile forbids that nothing validates is refused rather than assumed "
                 "absent", not problems, "\n".join(problems))


def test_each_manufactured_difficulty_check_can_actually_speak():
    """A negative control per condition. A check that never fires proves
    nothing about the world it was run on, so each one is shown refusing a
    pack that really carries its condition."""
    problems = []
    group = pair("ar-quillmarsh")
    variant = group.variant("a")
    world, task, inputs = variant.world, variant.task, variant.inputs
    public = dict(variant.public_files)

    def spoke(condition, *, world=world, task=task, inputs=inputs, public=public) -> bool:
        return bool(PROFILE._CHECKS[condition](world, task, inputs, public))

    # missing_authority: the policy loses the section a rule cites.
    stripped = dataclasses.replace(world, policy_text=world.policy_text.replace("## Cash application", "## Cash"))
    if not spoke("missing_authority", world=stripped):
        problems.append("missing_authority did not speak when the policy lost the section its rule cites")

    # ambiguous_identity: two customer-credit rows with one key.
    rows = public["bank_statement.csv"].splitlines()
    credit = next(i for i, row in enumerate(rows) if row.split(",")[1].startswith("ACH IN"))
    doubled = dict(public)
    doubled["bank_statement.csv"] = "\n".join(rows[:credit + 1] + [rows[credit]] + rows[credit + 1:]) + "\n"
    if not spoke("ambiguous_identity", public=doubled):
        problems.append("ambiguous_identity did not speak on two credit rows sharing one receipt key")

    # unsupported_deduction: a deduction with no reason in its own row.
    silent = []
    for event in world.events:
        if isinstance(event, AppliedReceipt) and any(line.deduction > 0 for line in event.lines):
            lines = tuple(dataclasses.replace(line, note="") if line.deduction > 0 else line
                          for line in event.lines)
            silent.append(dataclasses.replace(event, lines=lines))
        else:
            silent.append(event)
    if not spoke("unsupported_deduction", world=dataclasses.replace(world, events=tuple(silent))):
        problems.append("unsupported_deduction did not speak on a deduction that states no reason")

    # hidden_historical_fact: a row of the opening register withheld.
    withheld = dict(public)
    lines = withheld["open_items.csv"].splitlines()
    withheld["open_items.csv"] = "\n".join(lines[:-1]) + "\n"
    if not spoke("hidden_historical_fact", public=withheld):
        problems.append("hidden_historical_fact did not speak when a register row was withheld")

    # unexplained_tax_change: exactly one sale moved to another rate, so the
    # world's sales no longer speak with one voice.
    moved, done = [], False
    for event in world.events:
        if isinstance(event, Sale) and not done:
            moved.append(dataclasses.replace(event, tax_rate=event.tax_rate + D("0.01")))
            done = True
        else:
            moved.append(event)
    if not done:
        problems.append("the probe world raises no in-period sale, so the tax check cannot be controlled")
    elif not spoke("unexplained_tax_change", world=dataclasses.replace(world, events=tuple(moved))):
        problems.append("unexplained_tax_change did not speak on two sales-tax rates in one world")

    # answer_bearing_narration: a narration that instructs.
    numbers = [d.number for d in world.documents if d.number.startswith("SI-")]
    instructed, done = [], False
    for event in world.events:
        if isinstance(event, AppliedReceipt) and not done:
            instructed.append(dataclasses.replace(event, memo=f"apply 100.00 to {numbers[0]}"))
            done = True
        else:
            instructed.append(event)
    if not done:
        problems.append("the probe world carries no applied receipt to instruct with")
    elif not spoke("answer_bearing_narration", world=dataclasses.replace(world, events=tuple(instructed))):
        problems.append("answer_bearing_narration did not speak on an application instruction")

    # document_truncation: a row that loses a field.
    cut = dict(public)
    rows = cut["open_items.csv"].splitlines()
    cut["open_items.csv"] = "\n".join([rows[0]] + [rows[1].rsplit(",", 1)[0]] + rows[2:]) + "\n"
    if not spoke("document_truncation", public=cut):
        problems.append("document_truncation did not speak on a row with a field missing")

    # budget_consuming_padding: a row no authored fact produced.
    padded = dict(public)
    padded["credit_notes.csv"] = padded["credit_notes.csv"] + padded["credit_notes.csv"].splitlines()[-1] + "\n"
    if not spoke("budget_consuming_padding", public=padded):
        problems.append("budget_consuming_padding did not speak on a row no authored fact produced")

    return check("each of the eight manufactured-difficulty checks refuses a pack that really carries its "
                 "condition — a missing authority, a duplicated payment identity, a deduction with no stated "
                 "reason, a withheld register row, a second tax rate, an instructing narration, a truncated "
                 "row and a row no fact produced", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 5. independent correctness
# --------------------------------------------------------------------------

def test_the_public_fold_equals_the_truth_and_both_goldens_score_complete():
    problems = []
    for group, variant in every_variant():
        label = f"{group.family}/{variant.variant}"
        kw = dict(bank_account=variant.world.bank_account, period_start=variant.task.period.start,
                  period_end=variant.task.period.end)
        application = CA.fold(variant.public_files, **kw)
        if CA.application_key(application) != variant.truth.application_key():
            problems.append(f"{label}: the public fold and the private truth disagree")
        if application.closing_ar != variant.truth.closing_ar:
            problems.append(f"{label}: closing AR public {application.closing_ar} / truth "
                            f"{variant.truth.closing_ar}")
        if CA.document_text(application) != variant.golden_register:
            problems.append(f"{label}: the golden register is not the public fold's own document")
        env = K.load_contract(variant.inputs)
        from world_checks import score_text
        L, problem = score_text(variant.golden_ledger, env, label)
        if problem:
            problems.append(problem)
            continue
        parsed = APP.parse_application(variant.golden_register, variant.truth)
        if not isinstance(parsed, APP.ParsedApplication):
            problems.append(f"{label}: the golden register is rejected at the parse boundary: {parsed}")
            continue
        outcome = APP.score_application(parsed, variant.truth, expected_balances=env.expected_balances)
        composite = X.compose(L, outcome)
        if L.total != ONE or not L.complete:
            problems.append(f"{label}: the golden ledger scores L={L.total} complete={L.complete}")
        if outcome.total != ONE or outcome.penalties:
            problems.append(f"{label}: the golden register scores A={outcome.total} {outcome.penalties}")
        if composite.total != ONE or not composite.complete:
            problems.append(f"{label}: the composite is {composite.total} complete={composite.complete}")
        composite.verify()
        outcome.verify()
    return check("for every rendered variant the private derivation equals the public fold over the actual "
                 "bytes, the golden register IS that fold's document, and both goldens score complete through "
                 "the actual candidate/1, application/1 and composite/1",
                 not problems, "\n".join(problems))


def test_no_binding_baseline_reaches_the_truth_and_the_reading_bound_holds():
    problems = []
    diagnostics = 0
    for group, variant in every_variant():
        label = f"{group.family}/{variant.variant}"
        kw = dict(bank_account=variant.world.bank_account, period_start=variant.task.period.start,
                  period_end=variant.task.period.end)
        try:
            report = CA.baseline_report(variant.public_files, CA.fold(variant.public_files, **kw), **kw)
        except ValueError as exc:
            problems.append(f"{label}: the baselines exceeded the reading bound: {exc}")
            continue
        if set(report) != {baseline.name for baseline in CA.BASELINES}:
            problems.append(f"{label}: the catalogue reported {sorted(report)}")
        reached = CA.refused_by(report)
        if reached:
            problems.append(f"{label}: binding baselines reach the whole truth: {reached}")
        for name, result in report.items():
            if len(result.readings) > CA.MAX_BASELINE_READINGS:
                problems.append(f"{label}: {name} enumerated {len(result.readings)} readings")
            if result.diagnostic and result.admitted and result.reaches_truth is None:
                problems.append(f"{label}: the diagnostic baseline's result was not recorded")
            if result.diagnostic and result.reaches_truth:
                diagnostics += 1
    if diagnostics == 0:
        print("      (the diagnostic number-order reading reached no truth in this population; it is recorded "
              "either way and never refuses)")
    return check("no admitted binding baseline reaches the entire truth of any rendered variant through any "
                 "enumerated reading, every baseline stays inside the 256-reading bound, and the diagnostic "
                 "reading is recorded rather than promoted into an admission rule",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 6. determinism, leakage, the attempt loop
# --------------------------------------------------------------------------

def test_construction_is_deterministic_in_the_identity_and_the_secret():
    problems = []
    family = "cr-pikestaff"
    ident = CC.identity_of(POPULATION, family, 0)
    first = CC.candidate_pair(ident, secret=SECRET)
    again = CC.candidate_pair(ident, secret=SECRET)
    for name in VARIANTS:
        if first.variant(name).public_files != again.variant(name).public_files:
            problems.append(f"{family}/{name}: the same identity rendered different bytes")
        if first.variant(name).golden_ledger != again.variant(name).golden_ledger:
            problems.append(f"{family}/{name}: the same identity rendered a different golden ledger")
    other = CC.candidate_pair(ident, secret=OTHER_SECRET)
    if other.variant("a").public_files == first.variant("a").public_files:
        problems.append("another evaluator secret drew the same world; the seed is not keyed")
    neighbour = CC.candidate_pair(CC.identity_of(POPULATION, family, 1), secret=SECRET)
    if neighbour.variant("a").public_files == first.variant("a").public_files:
        problems.append("the next company-month index drew the same world")
    elsewhere = CC.candidate_pair(CC.identity_of("another-population", family, 0), secret=SECRET)
    if elsewhere.variant("a").public_files == first.variant("a").public_files:
        problems.append("another population drew the same world, so a predeclared census could be reused")
    # the identity's profile digest is part of construction, not a render-time argument
    tweaked = dataclasses.replace(BOUNDED_V1, max_dependency_depth=2)
    if raises(CC.ConstructionRefused, CC.construct, ident, 0, tweaked, SECRET) is None:
        problems.append("a pair was rendered under a profile the identity was not minted for")
    return check("construction is a function of the construction identity and the evaluator secret alone: the "
                 "same identity renders the same bytes, another secret, another index and another population "
                 "each render different ones, and a profile the identity was not minted under is refused",
                 not problems, "\n".join(problems))


def test_no_private_selector_or_seed_reaches_the_agent_surface():
    problems = []
    for group, variant in every_variant():
        seed = parent_seed(group.identity, SECRET)
        surfaces = dict(variant.public_files)
        surfaces["<prompt>"] = variant.task.prompt
        surfaces["<task id>"] = variant.task.id
        surfaces["<world id>"] = variant.world.id
        found = identity_leaks(surfaces, group.identity, seed)
        problems += [f"{group.family}/{variant.variant}: {line}" for line in found]
    # the check can speak: plant a token and watch it
    group = pair("fc-sedgewick")
    variant = group.variant("a")
    seed = parent_seed(group.identity, SECRET)
    token = private_tokens(group.identity, seed)[0]
    if not identity_leaks({"<probe>": f"a file mentioning {token}"}, group.identity, seed):
        problems.append("the leakage check did not see a planted private token")
    return check("no public file, prompt, task id or world id of any rendered variant carries a private "
                 "construction token — the identity digest, its label, the population, the template family, "
                 "the company-month index or the seed — and the check speaks when one is planted",
                 not problems, "\n".join(problems))


def test_the_attempt_loop_is_bounded_and_exhaustion_is_a_named_failed_group():
    problems = []
    ident = CC.identity_of(POPULATION, "fc-sedgewick", 0)
    for attempt in (-1, MAX_LAYOUT_ATTEMPTS, MAX_LAYOUT_ATTEMPTS + 10, 1.5):
        if raises(CC.ConstructionRefused, CC.construct, ident, attempt, BOUNDED_V1, SECRET) is None:
            problems.append(f"attempt {attempt!r} was accepted; decision 3 fixes {MAX_LAYOUT_ATTEMPTS} "
                            f"deterministic attempts per parent pair")
    # Exhaustion: a profile no layout can satisfy. Every attempt is refused,
    # the group is NAMED, and nothing advances to a replacement selector.
    impossible = dataclasses.replace(BOUNDED_V1, max_golden_ledger_bytes=10)
    blocked = CC.identity_of(POPULATION, "fc-sedgewick", 0, impossible)
    message = raises(CC.ConstructionRefused, CC.candidate_pair, blocked, impossible, SECRET)
    if message is None:
        problems.append("a profile no layout can satisfy still produced a pair")
    elif blocked.label() not in message or "EXHAUSTED" not in message:
        problems.append(f"exhaustion did not name the failed group: {message}")
    # Both variants are rejected when either fails: the pair is the unit.
    group = pair("ar-tenterhook")
    if len(group.variants) != 2:
        problems.append("a pair was admitted with one variant")
    return check(f"the attempt loop is bounded at {MAX_LAYOUT_ATTEMPTS} deterministic attempts per parent "
                 f"pair, an ordinal outside that range is refused, and exhaustion raises a NAMED failed group "
                 f"rather than advancing to a replacement selector", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 7. population integrity
# --------------------------------------------------------------------------

def test_the_population_has_no_collision_and_no_cross_split_sibling():
    problems = []
    ledger = StructureLedger()
    contents: dict = {}
    ids: dict = {}
    for index in (0, 1):
        for group in every_pair(index):
            try:
                ledger.admit(group.template)
            except StructuralAliasError as exc:
                problems.append(f"{group.family}#{index}: {exc}")
            for name in VARIANTS:
                variant = group.variant(name)
                digest = public_content_digest(variant.public_files, variant.task.prompt)
                if digest in contents:
                    problems.append(f"{group.family}#{index}/{name} collides with {contents[digest]}")
                contents[digest] = f"{group.family}#{index}/{name}"
                if variant.task.id in ids:
                    problems.append(f"the public id {variant.task.id} is claimed twice")
                ids[variant.task.id] = True
                if variant.task.id in REGISTRY:
                    problems.append(f"the generated id {variant.task.id} collides with a shipped task")
                if variant.world.id in {world.id for world, _task in REGISTRY.values()}:
                    problems.append(f"the generated world id {variant.world.id} collides with a shipped one")
    # the alias check can speak: the same structure declared under two splits
    train = next(entry.name for entry in TEMPLATE_ROSTER if SPLIT_MAP.split_of(entry.name) == "train")
    held = next(entry.name for entry in TEMPLATE_ROSTER
                if SPLIT_MAP.split_of(entry.name) == "evaluation"
                and SPLIT_MAP.mechanism_of(entry.name) == SPLIT_MAP.mechanism_of(train))
    borrowed = pair(train).template
    twin = dataclasses.replace(borrowed, family=held)
    probe = StructureLedger()
    probe.admit(borrowed)
    if raises(StructuralAliasError, probe.admit, twin) is None:
        problems.append("a renamed sibling of a train template was admitted into the evaluation split")
    return check("no two rendered variants of the population share public content, no generated id collides "
                 "with a shipped task or world, every template is admitted without a cross-split structural "
                 "sibling, and a renamed sibling really is refused",
                 not problems, "\n".join(problems))


def test_the_authored_eleven_stay_outside_the_generated_population():
    """Decision 2: "Keep the authored eleven entirely outside this
    population, as public demonstrations and regression tests." So they are
    not drawn, their names are not in the generator's pools, and their bytes
    do not move because a generator exists."""
    problems = []
    authored = sorted(CASH_APPLICATION_REGISTRY)
    if len(authored) != 11:
        problems.append(f"the registry carries {len(authored)} authored cash tasks, not eleven")
    generated = {variant.task.id for _group, variant in every_variant()}
    if generated & set(authored):
        problems.append(f"a generated id is an authored one: {sorted(generated & set(authored))}")
    pools = {name for name, _short, _bank in CC.COMPANIES} | set(CC.CUSTOMER_NAMES) | set(CC.VENDOR_NAMES)
    for task_id in authored:
        world, task = CASH_APPLICATION_REGISTRY[task_id]
        names = {party.name for party in world.parties} | {world.title}
        if names & pools:
            problems.append(f"{task_id} shares a name with the generator's pools: {sorted(names & pools)}")
        # and all eleven still project through the production door
        _bundle, inputs = derive_contract(world, task)
        if len(inputs.public_files) != 11:
            problems.append(f"{task_id}: {len(inputs.public_files)} public files")
        if inputs.application is None:
            problems.append(f"{task_id}: no truth register")
    return check("the eleven authored variants stay outside the generated population: no id, no company name "
                 "and no customer name is shared, and all eleven still project their eleven public files and "
                 "their truth register through the production door",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 8. legitimate complexity
# --------------------------------------------------------------------------

def test_every_dependency_has_an_accounting_reason_and_a_witness():
    """Decision 4: "Each additional dependency must have an accounting reason
    and a checkable witness in the facts." A dependency here is one event
    leaving a balance a later event reads, and the witness is that both name
    the invoice in a public row."""
    problems = []
    for group, variant in every_variant():
        label = f"{group.family}/{variant.variant}"
        truth = variant.truth
        touched: dict = {}
        for row in truth.receipts:
            touched[row[0]] = ({invoice for invoice, amount in tuple(row[4]) + tuple(row[5]) if amount > 0},
                               row[1], "receipt")
        for row in truth.credit_notes:
            touched[row[0]] = ({invoice for invoice, amount in row[4] if amount > 0}, row[1], "credit note")
        statement = variant.public_files["bank_statement.csv"]
        advice = variant.public_files["remittance_advice.csv"]
        notes = variant.public_files["credit_notes.csv"]
        for key, (invoices, _when, kind) in touched.items():
            for invoice in invoices:
                witnessed = invoice in advice or invoice in notes or invoice in statement \
                    or invoice in variant.public_files["open_items.csv"] \
                    or invoice in variant.public_files["ledger.beancount"]
                if not witnessed:
                    problems.append(f"{label}: the {kind} {key} reaches {invoice}, which no public file names")
        if PROFILE.dependency_depth(truth) > BOUNDED_V1.max_dependency_depth:
            problems.append(f"{label}: dependency depth above the profile")
    # the depth measure is a real longest path, not a count
    group = pair("cr-gallowtree")
    if PROFILE.dependency_depth(group.variant("a").truth) < 2:
        problems.append("the credit-residue recipe leaves no invoice touched by two events, so its dependency "
                        "measure is describing nothing")
    return check("every invoice a receipt or a credit note reaches is named by a public document, so each "
                 "dependency has a checkable witness in the facts, and the dependency depth stays inside "
                 "bounded-v1", not problems, "\n".join(problems))


TESTS = [
    test_the_roster_and_the_recipes_agree_in_both_directions,
    test_every_family_renders_a_pair_with_the_four_artifacts,
    test_the_pair_differs_in_exactly_one_declared_fact,
    test_both_polarities_appear_in_every_stratum,
    test_decision_fours_bounds_hold_on_every_rendered_variant,
    test_a_measurement_describes_what_was_generated_and_claims_nothing_else,
    test_manufactured_difficulty_is_absent_on_every_variant,
    test_each_manufactured_difficulty_check_can_actually_speak,
    test_the_public_fold_equals_the_truth_and_both_goldens_score_complete,
    test_no_binding_baseline_reaches_the_truth_and_the_reading_bound_holds,
    test_construction_is_deterministic_in_the_identity_and_the_secret,
    test_no_private_selector_or_seed_reaches_the_agent_surface,
    test_the_attempt_loop_is_bounded_and_exhaustion_is_a_named_failed_group,
    test_the_population_has_no_collision_and_no_cross_split_sibling,
    test_the_authored_eleven_stay_outside_the_generated_population,
    test_every_dependency_has_an_accounting_reason_and_a_witness,
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
