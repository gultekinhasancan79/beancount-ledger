"""Phase D of the generated cash-application population: the FROZEN
DEVELOPMENT POPULATION and its SERVING DOOR.

Round 16, decision 5. What is witnessed here:

  * the FREEZE is declared as literals and matches the live modules in both
    directions, and a moved declaration is reported by name — a freeze that
    cannot notice a change is not a freeze;
  * the population is 96 predeclared parent groups, 32 per mechanism stratum,
    every one of them in the DEVELOPMENT split, in a fixed order, with no
    repeated label or identity digest, and identical on two calls;
  * the EVALUATION SPLIT IS NOT OPENED, and it is not opened by the absence
    of a roster entry rather than by a prohibition: the three sealed
    evaluation families are in no released population, so no selector spells
    them and the door refuses them by name;
  * the selector round-trips, and refuses an undeclared index, an unreleased
    population, a non-ASCII index, an unknown variant, a bank-family
    selector and an authored task id;
  * an instance SERVES FROM THE SIGNED MANIFEST EXACTLY AS THE AUTHORED TASKS
    DO: same episode profile, same public file manifest, same tool surface
    and the same episode-contract digest as `cash_application_001`, compared
    against that task rather than against a literal;
  * the door is the manifest: a declared member that was never signed is
    refused, a record whose gate flag was flipped is refused, and a record
    whose public id was edited is refused — all without a development bypass,
    which this family does not have;
  * the offline validation gates all pass on the bounded slice, and the
    census retains every attempt with the nine fields decision 3 names while
    the aggregates carry acceptance rate, exhaustion count and rejection
    distribution PER STRATUM;
  * NO MODEL IS CALLED: the phase-D modules import no provider, no HTTP
    client and no measurement instrument;
  * no shipped task's public bytes moved, and GENERATOR_VERSION 9 and its
    manifest are untouched;
  * ROUND 17, DECISION 4 — the REPLACEMENT population. The population
    selected under the incorrect opening-balance cap is retired and
    unspellable, the freeze pins the population identifier as a literal so
    that it cannot move again unnoticed, and both records are published: the
    superseded one unaltered under the rule it was minted under, the
    replacement one a census of THIS generator, each note linking to the
    other, with the paired replay showing every refusal the removed clause
    caused is now admitted.

    python tests/test_cash_population.py
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# The suite mints and serves under ITS OWN secret and rotation, in its own
# process, and writes its manifest to a temporary directory. It never reads,
# prints, copies or hashes the evaluator's provisioned key, and it never sets
# a development bypass — this family has none, so the only way to serve here
# is to sign a real manifest and admit through it.
SECRET_HEX = ("cash-application-phase-d-test-secret-0123456789".encode("utf-8")).hex()
_TMP = tempfile.mkdtemp(prefix="cash_population_suite_")
os.environ["PIV_EVAL_SECRET"] = SECRET_HEX
os.environ["PIV_KEY_ID"] = "phase-d-suite-rotation"
os.environ["PIV_CASH_APPLICATION_MANIFEST"] = str(Path(_TMP) / "cash_application_manifest.json")

import preflight_cash_population as PF  # noqa: E402
from beancount_ledger import beancount_ledger as ENV  # noqa: E402
from beancount_ledger.graph import cash_construct as CC  # noqa: E402
from beancount_ledger.graph import cash_manifest as FM  # noqa: E402
from beancount_ledger.graph import cash_population as CP  # noqa: E402
from beancount_ledger.graph import mint as BANK_MINT  # noqa: E402
from beancount_ledger.graph.cash_identity import MECHANISMS, VARIANTS  # noqa: E402
from beancount_ledger.graph.cash_split import SPLIT_MAP  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402

AUTHORED = PF.AUTHORED_REFERENCE

_RUN: dict = {}


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


def secret() -> bytes:
    """The suite's own secret, through the one provisioning door the family
    uses, so the suite exercises that door rather than a second one."""
    return BANK_MINT.evaluator_secret()


def run() -> dict:
    """The bounded preflight: ONE declared group of each mechanism stratum,
    both phases, cached because it mints, validates and serves.

    A prefix of the declared roster, not a sample: nothing here chooses a
    group by anything it drew.
    """
    if not _RUN:
        identities = PF.stratified_prefix(CP.development_identities(), 1)
        _RUN["run"] = PF.preflight(identities, secret(), Path(os.environ["PIV_CASH_APPLICATION_MANIFEST"]))
        _RUN["identities"] = identities
    return _RUN["run"]


def serve(selector: str):
    """`load_environment` with the suite's manifest in place. Returns the
    environment or the InitializationFailure's reasons as a string."""
    try:
        return ENV.load_environment(selector)
    except ENV.InitializationFailure as exc:
        return "; ".join(getattr(exc, "reasons", []) or [str(exc)])


# --------------------------------------------------------------------------
# the freeze
# --------------------------------------------------------------------------

def test_the_freeze_is_declared_and_matches_the_live_modules():
    problems = list(CP.freeze_problems())
    declared, live = CP.DECLARED_FREEZE, CP.live_freeze()
    if set(declared) != set(live):
        problems.append(f"the declared and live freeze keys differ: {sorted(set(declared) ^ set(live))}")
    record = CP.freeze_record()
    if record["digest"] != CP.freeze_record()["digest"]:
        problems.append("the freeze digest is not stable across two calls in one process")
    if not record["declared_matches_live"]:
        problems.append("the freeze record says the declarations no longer match the live modules")
    # The runtime-scoped half is RECORDED, and it is recorded separately. A
    # freeze that pinned the catalogue digest as a literal would fail on the
    # next interpreter and call a recompile a change.
    runtime = record["runtime_scoped"]
    for key in ("baseline_catalogue_digest", "semantic_components", "runtime_scope", "census_components"):
        if key not in runtime:
            problems.append(f"the runtime-scoped freeze does not record {key}")
    if "baseline_catalogue_digest" in declared:
        problems.append("the baseline catalogue digest is pinned as a literal; it binds compiled predicate "
                        "bytecode and is runtime-scoped")
    if record["declared"]["gate_count"] != len(FM.family_gates()):
        problems.append("the frozen gate count is not the declared gate set's size")
    return check("the freeze is declared as literals, matches the live modules in both directions, and keeps "
                 "the runtime-scoped half recorded rather than pinned", not problems, "\n".join(problems))


def test_the_freeze_notices_a_moved_declaration():
    """A freeze that cannot fail is not a freeze. Each of three declarations
    is moved in turn and the report must name THAT key."""
    problems = []
    for key, value in (("gate_version", 99), ("profile_digest", "0" * 32), ("max_layout_attempts", 8)):
        original = CP.DECLARED_FREEZE[key]
        CP.DECLARED_FREEZE[key] = value
        try:
            found = CP.freeze_problems()
        finally:
            CP.DECLARED_FREEZE[key] = original
        if not any(line.startswith(f"{key} was frozen at") for line in found):
            problems.append(f"moving {key} to {value!r} was not reported: {found}")
    # ... and a key that leaves the declaration entirely.
    original = CP.DECLARED_FREEZE.pop("gate_set_digest")
    try:
        found = CP.freeze_problems()
    finally:
        CP.DECLARED_FREEZE["gate_set_digest"] = original
    if not any("is live at" in line and "gate_set_digest" in line for line in found):
        problems.append(f"dropping gate_set_digest from the declaration was not reported: {found}")
    if CP.freeze_problems():
        problems.append("the declaration was not restored after the controls")
    return check("a moved or dropped freeze declaration is reported by name",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# the declared population
# --------------------------------------------------------------------------

def test_the_population_is_ninety_six_groups_thirty_two_per_stratum():
    problems = list(CP.population_problems(CP.DEVELOPMENT_POPULATION))
    identities = CP.development_identities()
    if len(identities) != 96:
        problems.append(f"the population declares {len(identities)} groups, not 96")
    per = {m: 0 for m in MECHANISMS}
    for ident in identities:
        per[CC.shape_of(ident.template_family).mechanism] += 1
        if ident.split != "development":
            problems.append(f"{ident.label()} is not in the development split")
    if set(per.values()) != {32}:
        problems.append(f"the strata are {per}, not 32 each")
    if [i.label() for i in identities] != [i.label() for i in CP.development_identities()]:
        problems.append("two calls declared different populations")
    if len({i.digest() for i in identities}) != len(identities):
        problems.append("two declared groups share an identity digest")
    if CP.GROUPS_PER_STRATUM != 32:
        problems.append(f"GROUPS_PER_STRATUM is {CP.GROUPS_PER_STRATUM}, not decision 5's 32")
    return check("96 predeclared development parent groups, 32 per mechanism stratum, in a fixed order with "
                 "no repeated identity", not problems, "\n".join(problems))


def test_the_evaluation_split_is_not_opened():
    problems = []
    evaluation = [name for name, _m, split in SPLIT_MAP.assignments if split == "evaluation"]
    if len(evaluation) != 3:
        problems.append(f"the frozen map seals {len(evaluation)} evaluation families, not three")
    for population, split in CP.RELEASED_POPULATIONS.items():
        if split == "evaluation":
            problems.append(f"the released population {population!r} draws the evaluation split")
        families = {family for family, _index in CP.roster(population)}
        if families & set(evaluation):
            problems.append(f"{population!r} declares the evaluation families {sorted(families & set(evaluation))}")
    for family in evaluation:
        selector = f"{CP.SELECTOR_PREFIX}:{CP.DEVELOPMENT_POPULATION}:{family}:0:a"
        message = raises(CP.SelectorError, CP.parse_selector, selector)
        if message is None or "not a declared member" not in message:
            problems.append(f"{selector} was not refused as undeclared: {message}")
        served = serve(selector)
        if not isinstance(served, str) or "unknown task" not in served:
            problems.append(f"the door served an evaluation-split selector: {served}")
    return check("the evaluation split stays unopened: no released population declares a sealed evaluation "
                 "family, so the selector does not exist rather than being forbidden",
                 not problems, "\n".join(problems))


def test_the_selector_round_trips_and_refuses_everything_else():
    problems = []
    for ident in (CP.development_identities()[0], CP.development_identities()[-1]):
        for variant in VARIANTS:
            selector = CP.selector_of(ident, variant)
            back, name = CP.parse_selector(selector)
            if back != ident or name != variant:
                problems.append(f"{selector} did not round-trip: {back.label()}/{name}")
            # No FIELD of the selector is the split: it is read from the
            # frozen map on the way back, never restated. (A substring test
            # would be wrong — the population's own name contains the word.)
            if ident.split in selector.split(":"):
                problems.append(f"{selector} restates the split, which is read from the frozen map")
    bad = {
        "an unreleased population": f"{CP.SELECTOR_PREFIX}:not-a-population:fc-quarrymill:0:a",
        "an undeclared index": f"{CP.SELECTOR_PREFIX}:{CP.DEVELOPMENT_POPULATION}:fc-quarrymill:32:a",
        "a non-ASCII index": f"{CP.SELECTOR_PREFIX}:{CP.DEVELOPMENT_POPULATION}:fc-quarrymill:０:a",
        "an unknown variant": f"{CP.SELECTOR_PREFIX}:{CP.DEVELOPMENT_POPULATION}:fc-quarrymill:0:c",
        "too few fields": f"{CP.SELECTOR_PREFIX}:{CP.DEVELOPMENT_POPULATION}:fc-quarrymill:0",
        "a bank-family selector": "train:5",
        "an authored task id": AUTHORED,
        "an unknown family": f"{CP.SELECTOR_PREFIX}:{CP.DEVELOPMENT_POPULATION}:not-a-family:0:a",
    }
    for what, selector in bad.items():
        message = raises(CP.SelectorError, CP.parse_selector, selector)
        if message is None:
            problems.append(f"{what} ({selector!r}) was parsed rather than refused")
        elif message.startswith("!!"):
            problems.append(f"{what} ({selector!r}) raised the wrong exception: {message}")
    if not ENV.CASH_SELECTOR_PREFIX == CP.SELECTOR_PREFIX + ":":
        problems.append(f"the composition root dispatches on {ENV.CASH_SELECTOR_PREFIX!r} and the family "
                        f"declares {CP.SELECTOR_PREFIX!r}")
    if CP.SELECTOR_PREFIX in BANK_MINT.NAMESPACES:
        problems.append("the cash selector prefix is also a bank namespace; the two selector spaces overlap")
    return check("the selector round-trips through the frozen roster and refuses an unreleased population, an "
                 "undeclared index, a non-ASCII index, an unknown variant, a bank selector and an authored id",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# serving
# --------------------------------------------------------------------------

def test_an_instance_serves_exactly_as_an_authored_task_does():
    result = run()
    problems = []
    if not result["ok"]:
        problems.append(f"the bounded preflight did not pass: {result['freeze_problems']} "
                        f"{[r['selector'] for r in result['failed_validation']]} "
                        f"{[r['note'] for r in result['not_served']]}")
    if len(result["records"]) != 6 or len(result["serving"]) != 6:
        problems.append(f"{len(result['records'])} records and {len(result['serving'])} serving rows, not six")
    reference = ENV.load_environment(AUTHORED)
    for row in result["serving"]:
        if not row["served"]:
            problems.append(f"{row['selector']}: {row['note']}")
            continue
        served = serve(row["selector"])
        if isinstance(served, str):
            problems.append(f"{row['selector']} refused on the second serve: {served}")
            continue
        if served.profile != reference.profile:
            problems.append(f"{row['selector']} serves profile {served.profile!r}, the authored task serves "
                            f"{reference.profile!r}")
        if served.episode_contract_digest() != reference.episode_contract_digest():
            problems.append(f"{row['selector']} serves episode contract {served.episode_contract_digest()[:16]}, "
                            f"the authored task {reference.episode_contract_digest()[:16]}")
        if sorted(ENV.public_file_names(served.profile)) != sorted(ENV.public_file_names(reference.profile)):
            problems.append(f"{row['selector']} observes a different public file manifest")
        if sorted(served.tool_map) != sorted(reference.tool_map):
            problems.append(f"{row['selector']} serves the tool surface {sorted(served.tool_map)}")
        first = served.dataset[0]
        public_id = (first.get("info") or {}).get("task_id")
        if public_id != row["expected_public_id"]:
            problems.append(f"{row['selector']} served {public_id!r}, the record binds "
                            f"{row['expected_public_id']!r}")
        # The selector is EVALUATOR-SIDE and carries private tokens; it may
        # not appear anywhere the agent can read.
        for surface, text in (("prompt", first.get("question")), ("answer", str(first.get("answer")))):
            if row["selector"] in (text or ""):
                problems.append(f"{row['selector']} appears in the served {surface}")
    return check("a generated instance serves from the signed manifest exactly as an authored cash task does: "
                 "same profile, public file manifest, tool surface and episode-contract digest, with the "
                 "record's public id and no selector on an agent surface", not problems, "\n".join(problems))


def test_the_manifest_is_the_door():
    """No development bypass, and three ways of not being admitted."""
    result = run()
    problems = []
    path = Path(os.environ["PIV_CASH_APPLICATION_MANIFEST"])
    original = path.read_text(encoding="utf-8")

    # (1) a DECLARED member that was never signed.
    signed = {row["selector"] for row in result["serving"]}
    unsigned = next(CP.selector_of(ident, "a") for ident in CP.development_identities()
                    if CP.selector_of(ident, "a") not in signed)
    served = serve(unsigned)
    if not isinstance(served, str) or "selector absent from the family manifest" not in served:
        problems.append(f"an unsigned declared member was not refused: {served}")

    # (2) a record whose gate flag was flipped, and (3) one whose public id
    # was edited. Both keep a VALID signature only if the tamperer re-signs;
    # these do not, so the first refusal is the signature — which is the
    # point: the record is bound, not merely carried.
    import json
    for what, edit in (
        ("a flipped gate", lambda rec: rec["gates"].__setitem__("ar_reconciles", False)),
        ("an edited public id", lambda rec: rec.__setitem__("public_id", "cash_application_g000000000000")),
    ):
        body = json.loads(original)
        edit(body["records"][0])
        path.write_text(json.dumps(body, indent=1, sort_keys=True), encoding="utf-8")
        selector = result["serving"][0]["selector"]
        served = serve(selector)
        if not isinstance(served, str) or "family manifest" not in served:
            problems.append(f"{what} was served anyway: {served}")
        path.write_text(original, encoding="utf-8")

    # The family has no development bypass at all.
    if "PIV_DEV_UNMANIFESTED" in Path(ROOT / "beancount_ledger" / "graph" / "cash_manifest.py").read_text(
            encoding="utf-8").replace("manifest.py", ""):
        problems.append("cash_manifest names a development bypass")
    served = serve(result["serving"][0]["selector"])
    if isinstance(served, str):
        problems.append(f"the manifest was not restored: {served}")
    return check("the signed manifest is the door: an unsigned declared member, a flipped gate and an edited "
                 "public id are all refused, and the family has no development bypass",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# the validation and the census
# --------------------------------------------------------------------------

def test_offline_validation_covers_what_decision_five_asks_for():
    result = run()
    problems = []
    expected = set(PF.VALIDATION_GATES)
    for row in result["rows"]:
        if set(row["gates"]) != expected:
            problems.append(f"{row['selector']} evaluated {sorted(row['gates'])}")
        if not row["passed"]:
            problems.append(f"{row['selector']}: {[g for g, ok in row['gates'].items() if not ok]} "
                            f"{' | '.join(row['notes'])[:200]}")
        for field, want in (("ledger_total", "1.000000"), ("register_total", "1.000000"),
                            ("composite_total", "1.000000")):
            if row.get(field) != want:
                problems.append(f"{row['selector']} recorded {field}={row.get(field)!r}, not {want!r}")
        if row.get("readings") != 1:
            problems.append(f"{row['selector']} is identifiable in {row.get('readings')!r} readings, not one")
        if not row.get("composite_complete"):
            problems.append(f"{row['selector']}'s composite does not complete")
    if len(result["rows"]) != 2 * result["groups_admitted"]:
        problems.append("the validation did not cover both variants of every admitted group")
    return check("every admitted variant serves, folds to its truth, is identifiable in ONE reading, and both "
                 "goldens and their composite score 1.0 through the actual frozen engines",
                 not problems, "\n".join(problems))


def test_the_census_and_the_aggregates_are_per_stratum():
    result = run()
    problems = []
    fields = ("ordinal", "stage", "outcome", "codes", "witness", "baseline", "reading_counts",
              "components", "content_digests")
    for census in result["censuses"]:
        if not census["attempts"]:
            problems.append(f"{census['group']} retained no attempt")
        for attempt in census["attempts"]:
            missing = [f for f in fields if f not in attempt]
            if missing:
                problems.append(f"{census['group']}#{attempt['ordinal']} does not retain {missing}")
        if census["outcome"] == "admitted" and census["accepted_attempt"] is None:
            problems.append(f"{census['group']} is admitted with no accepted attempt")
    strata = result["by_stratum"]
    if sorted(strata) != sorted(MECHANISMS):
        problems.append(f"the aggregates cover {sorted(strata)}")
    for mechanism, row in strata.items():
        for key in ("groups", "admitted_groups", "exhausted_groups", "group_acceptance_rate",
                    "attempt_acceptance_rate", "rejection_distribution"):
            if key not in row:
                problems.append(f"the {mechanism} aggregate does not publish {key}")
        if row.get("groups") != 1:
            problems.append(f"the bounded run declared {row.get('groups')} {mechanism} groups, not one")
    overall = result["aggregate"]
    if overall["groups"] != len(result["censuses"]):
        problems.append("the overall aggregate does not cover every census")
    return check("every attempt retains the nine fields decision 3 names, and the aggregates publish "
                 "acceptance rates, exhaustion counts and rejection distributions per stratum",
                 not problems, "\n".join(problems))


def test_no_model_is_called():
    """Decision 5: the first measurement is a separate, later step. Nothing in
    phase D may reach a provider, and the cheapest honest check is that the
    phase-D sources name none."""
    problems = []
    forbidden = re.compile(r"\b(openai|anthropic|requests|httpx|urllib|aiohttp|http_client|"
                           r"measure_budget|budget_calibration|provider_probe|run_live_rollout)\b")
    for path in (ROOT / "beancount_ledger" / "graph" / "cash_population.py",
                 ROOT / "tests" / "preflight_cash_population.py"):
        text = path.read_text(encoding="utf-8")
        hit = sorted({m.group(0) for m in forbidden.finditer(text)})
        if hit:
            problems.append(f"{path.name} names {hit}")
    return check("no phase-D source reaches a model provider, an HTTP client or a measurement instrument",
                 not problems, "\n".join(problems))


def test_the_authored_eleven_stay_outside_and_the_frozen_neighbours_did_not_move():
    problems = []
    authored = {task_id for task_id in REGISTRY if task_id.startswith("cash_application_")}
    if len(authored) != 11:
        problems.append(f"{len(authored)} authored cash tasks, not eleven")
    for task_id in sorted(authored):
        if raises(CP.SelectorError, CP.parse_selector, task_id) is None:
            problems.append(f"the authored task {task_id} parses as a generated selector")
    served = {row["expected_public_id"] for row in run()["serving"]}
    if served & authored:
        problems.append(f"a generated instance took an authored id: {sorted(served & authored)}")
    for family, _index in CP.roster(CP.DEVELOPMENT_POPULATION):
        if family in REGISTRY:
            problems.append(f"the declared family {family} is also an authored task id")
    # GENERATOR_VERSION 9 and the bank manifest, untouched by this phase.
    if BANK_MINT.GENERATOR_VERSION != 9:
        problems.append(f"GENERATOR_VERSION is {BANK_MINT.GENERATOR_VERSION}, not 9")
    from beancount_ledger.graph import manifest as BANK_MF
    if BANK_MF.versions().get("generator") != 9:
        problems.append(f"the bank manifest declares generator {BANK_MF.versions().get('generator')}")
    if BANK_MF.MANIFEST_ENV == FM.FAMILY_MANIFEST_ENV:
        problems.append("the two families read one manifest path")
    # The public bytes of the shipped 106, rolled up. `test_legacy_freeze`
    # pins them against a checked-in fixture; this is the same claim taken
    # from the same door phase D touched, so a serving-door change that moved
    # a shipped world fails HERE too rather than only there.
    from beancount_ledger.graph.derive import derive_contract
    roll = hashlib.sha256()
    for task_id in sorted(REGISTRY):
        world, task = REGISTRY[task_id]
        _bundle, inputs = derive_contract(world, task)
        digest = hashlib.sha256()
        for name, data in inputs.public_files:
            digest.update(name.encode("utf-8") + b"\0" + data + b"\0")
        roll.update(task_id.encode("utf-8") + b":" + digest.hexdigest().encode("ascii") + b"\n")
    if roll.hexdigest() != SHIPPED_PUBLIC_ROLL:
        problems.append(f"the 106 shipped tasks' public bytes roll to {roll.hexdigest()}, "
                        f"not {SHIPPED_PUBLIC_ROLL}")
    return check("the authored eleven stay outside the generated population, no generated instance takes an "
                 "authored id, the 106 shipped tasks' public bytes are unmoved, and GENERATOR_VERSION 9 and "
                 "its manifest are untouched", not problems, "\n".join(problems))


#: The roll-up of all 106 shipped tasks' public bytes, measured before phase D
#: touched the composition root and pinned here. `tests/legacy_freeze.json` is
#: the authority for the 95; this is the same claim over all 106 through the
#: door this phase edited.
SHIPPED_PUBLIC_ROLL = "dbac991578fcc6292af8d547c335e648c068d1d8320c538001dd9cc9cb500f0b"


# --------------------------------------------------------------------------
# the replacement population (round 17, decision 4)
# --------------------------------------------------------------------------

#: The superseded population, its record, and the gate set it was minted
#: under. Literals, because the whole point of the finding is that these two
#: rules must never be readable as each other.
SUPERSEDED = "cash-application-development-1"
SUPERSEDED_GATE_SET = "6b246422badd05a6"
SUPERSEDED_RECORD = "cash_application_development_population_2026-09-13"
REPLACEMENT_RECORD = SUPERSEDED_RECORD + "_replacement"


def test_the_superseded_population_is_retired_and_unspellable():
    """Decision 4 replaced a population, and a replaced population must not
    still be servable. Retirement here is the ABSENCE of a roster entry — the
    same mechanism that keeps the evaluation split closed — plus a declared
    reason a reader of the old census can find in source."""
    problems = []
    if CP.DEVELOPMENT_POPULATION == SUPERSEDED:
        problems.append(f"the development population is still {SUPERSEDED!r}")
    if SUPERSEDED in CP.RELEASED_POPULATIONS:
        problems.append(f"{SUPERSEDED!r} is still released and its selectors still parse")
    entry = CP.SUPERSEDED_POPULATIONS.get(SUPERSEDED)
    if not entry:
        problems.append(f"{SUPERSEDED!r} is not declared superseded, so nothing in source says why it went")
    else:
        if entry.get("superseded_by") != CP.DEVELOPMENT_POPULATION:
            problems.append(f"the supersession names {entry.get('superseded_by')!r}, not the live population")
        if "opening balance" not in entry.get("reason", ""):
            problems.append("the supersession does not name the incorrect restriction")
    if set(CP.SUPERSEDED_POPULATIONS) & set(CP.RELEASED_POPULATIONS):
        problems.append("a population is both released and superseded")
    for variant in sorted(VARIANTS):
        selector = f"{CP.SELECTOR_PREFIX}:{SUPERSEDED}:cr-pikestaff:0:{variant}"
        message = raises(CP.SelectorError, CP.parse_selector, selector)
        if message is None or "not a released" not in message:
            problems.append(f"a superseded selector was not refused as unreleased: {message}")
    if raises(CP.PopulationError, CP.identities_of, SUPERSEDED) is None:
        problems.append("the superseded population still yields identities through the roster")
    return check("the superseded population is retired: it is not released, no selector spells it, its roster "
                 "is gone, and source declares what replaced it and why",
                 not problems, "\n".join(problems))


def test_the_freeze_pins_the_population_identifier_as_a_literal():
    """A freeze that read `DEVELOPMENT_POPULATION` to check
    `DEVELOPMENT_POPULATION` would agree with every future value of it. The
    identifier moved once, deliberately; the freeze must notice it moving
    again."""
    problems = []
    if CP.DECLARED_FREEZE.get("development_population") != CP.DEVELOPMENT_POPULATION:
        problems.append("the declared population does not match the live one")
    source = (ROOT / "beancount_ledger" / "graph" / "cash_population.py").read_text(encoding="utf-8")
    declaration = source.split("DECLARED_FREEZE: dict = {", 1)[-1].split("\n}", 1)[0]
    # The VALUES only: a comment inside the declaration may name the constant
    # to say why it is not read, and that is the opposite of the defect.
    values = "\n".join(line.split("#", 1)[0] for line in declaration.splitlines())
    if "DEVELOPMENT_POPULATION" in values:
        problems.append("DECLARED_FREEZE reads the constant it is meant to pin")
    original = CP.DEVELOPMENT_POPULATION
    try:
        CP.DEVELOPMENT_POPULATION = "cash-application-development-99"
        found = CP.freeze_problems()
    finally:
        CP.DEVELOPMENT_POPULATION = original
    if not any(line.startswith("development_population was frozen at") for line in found):
        problems.append(f"moving the population identifier was not reported: {found}")
    if CP.freeze_problems():
        problems.append("the declaration was not restored after the control")
    if tuple(CP.DECLARED_FREEZE.get("superseded_populations", ())) != tuple(sorted(CP.SUPERSEDED_POPULATIONS)):
        problems.append("the frozen superseded list does not match the live one")
    return check("the freeze pins the population identifier as a literal and reports it moving",
                 not problems, "\n".join(problems))


def test_both_population_records_are_published_and_cross_linked():
    """The superseded record stays as minted; the replacement stands beside
    it; each note names the other. A reader who lands on either one must be
    able to get to the other without knowing this history."""
    import json as _json

    problems = []
    reviews = ROOT / "reviews"
    old_dir, new_dir = reviews / SUPERSEDED_RECORD, reviews / REPLACEMENT_RECORD
    old_note, new_note = reviews / f"{SUPERSEDED_RECORD}.md", reviews / f"{REPLACEMENT_RECORD}.md"

    for path in (old_dir, new_dir, old_note, new_note):
        if not path.exists():
            problems.append(f"{path.relative_to(ROOT)} is missing")
    if problems:
        return check("both population records are published and cross-linked", False, "\n".join(problems))

    # The superseded record's five artifacts stay as minted, under the old
    # rule, and must never be readable as a census of this generator.
    for name in ("freeze.json", "census.json", "aggregates.json", "validation.json", "serving.json"):
        if not (old_dir / name).is_file():
            problems.append(f"the superseded record lost {name}")
    old_freeze = _json.loads((old_dir / "freeze.json").read_text(encoding="utf-8"))["freeze"]["declared"]
    if old_freeze.get("gate_set_digest") != SUPERSEDED_GATE_SET or old_freeze.get("gate_version") != 1:
        problems.append("the superseded record was altered; it must stay as minted")
    old_census = _json.loads((old_dir / "census.json").read_text(encoding="utf-8"))
    if old_census.get("population") != SUPERSEDED:
        problems.append(f"the superseded census names {old_census.get('population')!r}")

    # The replacement record is a census of THIS generator.
    new_freeze = _json.loads((new_dir / "freeze.json").read_text(encoding="utf-8"))["freeze"]["declared"]
    for key, want in (("gate_set_digest", FM.gate_set_digest()),
                      ("gate_version", 2),
                      ("family_preflight_contract", FM.FAMILY_PREFLIGHT_CONTRACT),
                      ("development_population", CP.DEVELOPMENT_POPULATION)):
        if new_freeze.get(key) != want:
            problems.append(f"the replacement record declares {key} {new_freeze.get(key)!r}, not {want!r}")
    new_census = _json.loads((new_dir / "census.json").read_text(encoding="utf-8"))
    if new_census.get("population") != CP.DEVELOPMENT_POPULATION:
        problems.append(f"the replacement census names {new_census.get('population')!r}")
    if len(new_census.get("groups", [])) != CP.GROUPS_PER_STRATUM * len(MECHANISMS):
        problems.append(f"the replacement census holds {len(new_census.get('groups', []))} groups")

    # The paired replay: every attempt the old rule refused for the removed
    # clause, and what the corrected one does with it.
    replay_path = new_dir / "superseded_rejections.json"
    if not replay_path.is_file():
        problems.append("the replacement record carries no paired replay of the superseded refusals")
    else:
        replay = _json.loads(replay_path.read_text(encoding="utf-8"))
        refused = sum(1 for group in old_census.get("groups", []) for attempt in group["attempts"]
                      if "ACC-CUMULATIVE-REVERSAL-BOUNDED" in attempt["codes"])
        if replay.get("rejected_attempts_replayed") != refused:
            problems.append(f"the replay covers {replay.get('rejected_attempts_replayed')} of {refused} "
                            f"refusals the superseded census records")
        if replay.get("now_admitted") != refused or not refused:
            problems.append(f"{replay.get('now_admitted')} of {refused} superseded refusals are admitted "
                            f"under the corrected rule; decision 4 called them false rejections")

    # Cross-links, both directions, and the claim the finding turns on. Prose
    # is compared with its line breaks flattened: a sentence that a paragraph
    # wrapped is still that sentence, and the note must stay reflowable.
    def flat(text: str) -> str:
        return " ".join(text.replace("\n> ", "\n").split())

    old_text = old_note.read_text(encoding="utf-8")
    new_text = new_note.read_text(encoding="utf-8")
    if REPLACEMENT_RECORD + ".md" not in old_text:
        problems.append("the superseded note does not link forward to the replacement")
    if "SUPERSEDED" not in old_text[:2000].upper():
        problems.append("the superseded note does not say it is superseded")
    if SUPERSEDED_RECORD + ".md" not in new_text:
        problems.append("the replacement note does not link back to the superseded record")
    if "cannot establish conformity to the intended specification" not in flat(new_text):
        problems.append("the replacement note does not state why passing the old rule proved nothing")
    if flat(CLAIM_SENTENCE) not in flat(new_text):
        problems.append("the replacement note does not carry the ruling's claim sentence verbatim")
    return check("both population records are published, the superseded one unaltered, and each note links to "
                 "the other with the reason for the supersession stated",
                 not problems, "\n".join(problems))


#: Round 17, decision 4's claim for the shipped offline deliverable, verbatim.
#: The replacement note's limitations section must carry it exactly; it is the
#: sentence that bounds what any of this evidence may be cited for. Compared
#: with line breaks flattened, so the note may wrap it but may not reword it.
CLAIM_SENTENCE = (
    "A versioned, keyed cash-application generator with a frozen development population, "
    "deterministic accounting checks, golden-artifact validation and signed-manifest serving under "
    "the recorded repository runtime. No model performance, difficulty, training benefit or "
    "generalization beyond the development templates has been established."
)


TESTS = [
    test_the_freeze_is_declared_and_matches_the_live_modules,
    test_the_freeze_notices_a_moved_declaration,
    test_the_population_is_ninety_six_groups_thirty_two_per_stratum,
    test_the_evaluation_split_is_not_opened,
    test_the_selector_round_trips_and_refuses_everything_else,
    test_an_instance_serves_exactly_as_an_authored_task_does,
    test_the_manifest_is_the_door,
    test_offline_validation_covers_what_decision_five_asks_for,
    test_the_census_and_the_aggregates_are_per_stratum,
    test_no_model_is_called,
    test_the_authored_eleven_stay_outside_and_the_frozen_neighbours_did_not_move,
    test_the_superseded_population_is_retired_and_unspellable,
    test_the_freeze_pins_the_population_identifier_as_a_literal,
    test_both_population_records_are_published_and_cross_linked,
]


def main() -> int:
    results = [test() for test in TESTS]
    passed = sum(1 for r in results if r)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
