"""Phase A of the cash-application build: the family manifest schema and
preflight contract, both version 1 (round 16, decision 2).

What has to be true before a single instance is drawn:

  * the family manifest is SEPARATE from `manifest.py` all the way down — its
    own signing domain, its own file, its own component dict — so the bank
    family's v9 records keep serving whatever moves here, and nothing that
    moves there invalidates a record here;
  * a record binds the construction identity, the public-content digest, the
    parent/variant relationship, the split-map digest, the profile, the
    baseline catalogue, the exact gate set and every semantic component:
    public fold, reference identity, checker, parser, renderer and all three
    scoring engines;
  * `admit` reads TODAY's gate set, never the record's own `passed` flag —
    the failure `manifest.py` documents at length, not repeated here;
  * runtime-dependent evidence is scoped by Unicode database and native
    runtime, through the single convention in `tests/unicode_pins.py` rather
    than a third bespoke table;
  * episode settings never enter a record, and two records built under
    different token budgets are byte-identical;
  * `GENERATOR_VERSION` 9 and the bank manifest's own identity are untouched.

    python tests/test_cash_family_manifest.py
"""

from __future__ import annotations

import copy
import dataclasses
import json
import os
import sys
import tempfile
import unicodedata
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from beancount_ledger.candidate.canonical import canonical_bytes, domain_digest  # noqa: E402
from beancount_ledger.graph import cash_application as CA  # noqa: E402
from beancount_ledger.graph import cash_manifest as FM  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402
from beancount_ledger.graph import manifest as BANK  # noqa: E402
from beancount_ledger.graph import mint as MINT  # noqa: E402
from beancount_ledger.graph.cash_identity import BOUNDED_V1, IdentityError, identity  # noqa: E402
from beancount_ledger.graph.cash_split import MECHANISMS, SplitMap, TemplateFamily  # noqa: E402

from unicode_pins import (  # noqa: E402
    NATIVE_UNICODE_VERSION,
    UnicodeScopedPins,
    derived,
    observed,
    substituted_unicode_version,
)

SECRET = b"cash-application-phase-a-manifest-secret-012345"
OTHER_SECRET = b"a-quite-different-evaluator-secret-9876543210!!"
ROTATION = "phase-a-rotation-0001"

#: A sealed probe map. The shipped `SPLIT_MAP` is empty at phase A by design,
#: so the manifest is exercised against a map with families in it.
PROBE_ROSTER = tuple(TemplateFamily(f"probe_{mechanism}_{n}", mechanism)
                     for mechanism in MECHANISMS for n in range(5))
PROBE_MAP = SplitMap.seal(PROBE_ROSTER)
PROBE_FAMILY = PROBE_MAP.families()[0]

PUBLIC = {"ledger.beancount": '2026-04-10 * "Gannet Rigging Inc" "Customer receipt"\n',
          "open_items.csv": "invoice_id,customer\nSI-3100,Gannet Rigging Inc\n"}
PROMPT = "Correct the ledger and deliver the application register."
#: `admit` requires this now. An optional comparison at the serving door is
#: enforced only when the caller remembers to pass it.
CONTENT = FM.public_content_digest(PUBLIC, PROMPT)
#: A well-formed structure digest for the probes — the width
#: `cash_split.structure_digest` produces.
STRUCTURE = "0" * FM.STRUCTURE_DIGEST_WIDTH

#: The family manifest's runtime-scoped evidence, under the ONE convention.
#: `parse_policy_view()` records `unicodedata.unidata_version`, so the parser
#: component legitimately moves with the interpreter's Unicode database and
#: nothing else moves at all. The rows live here; the scope key is published
#: by `cash_manifest.runtime_scope_key()`.
RUNTIME_SCOPED = UnicodeScopedPins(
    name="the cash-application family manifest's runtime-scoped components",
    source="tests/test_cash_family_manifest.py (RUNTIME_SCOPED)",
    rows={
        "14.0.0": {                                                   # CPython 3.11
            "parser": "f06b3513de395193cb0eb437be28ca63b6fd4830c9cb79689e440d21d84950bd",
            "provenance": derived(
                "CPython 3.12.12 (Windows, unicode 15.0.0), by substituting the version string",
                cross_check="equals the 14.0.0 parse_policy_digest that tests/legacy_freeze.json's "
                            "unicode_scoped map pins (f06b3513…), a row the ubuntu 3.11 CI job confirms "
                            "natively; the parser component IS parse_policy_digest()"),
        },
        "15.0.0": {                                                   # CPython 3.12
            "parser": "623ebaf29e32250d4d7f4aee98e30da6feea015ce6d3daa8ac4f1a3814dbc6a0",
            "provenance": observed(
                "CPython 3.12.12 (Windows, unicode 15.0.0)",
                "observed natively on CPython 3.12.12 (Windows), which ships unicode 15.0.0"),
        },
        "15.1.0": {                                                   # CPython 3.13
            "parser": "9f39ade4bcf5bc9ee174995bd7a2765e0009894d90167fbaee5a5b3c1d0a70ca",
            "provenance": derived(
                "CPython 3.12.12 (Windows, unicode 15.0.0), by substituting the version string",
                cross_check="equals the 15.1.0 parse_policy_digest that tests/legacy_freeze.json's "
                            "unicode_scoped map pins (9f39ade4…), a row the ubuntu 3.13 CI job confirms "
                            "natively; the parser component IS parse_policy_digest()"),
        },
    },
    value_keys=("parser",),
    how_to_add=("read `cash_manifest.semantic_components()['parser']` on a runtime that really ships unicode "
                "{version} and add the row with `native` provenance"),
)


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


def an_identity(family=PROBE_FAMILY, index=0, population="dev-96"):
    return identity(population=population, split=PROBE_MAP.split_of(family), template_family=family,
                    template_version=1, company_month_index=index, profile=BOUNDED_V1)


def all_gates(value=True) -> dict:
    return {gate: value for gate in FM.FAMILY_GATES}


def a_record(ident=None, variant="a", gates=None, **changes) -> dict:
    ident = ident or an_identity()
    return FM.record(ident, variant, public_id="task-cash-0001", content_digest=CONTENT,
                     structure_digest=STRUCTURE, profile_name=BOUNDED_V1.name, attempt=0,
                     gates=gates if gates is not None else all_gates(), split_map=PROBE_MAP, **changes)


@contextmanager
def a_manifest(records, secret=SECRET, rotation=ROTATION):
    """A family manifest in a temporary directory, never in ~/.piv."""
    saved = {k: os.environ.get(k) for k in ("PIV_KEY_ID", FM.FAMILY_MANIFEST_ENV, "PIV_EVAL_SECRET")}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "cash_application_manifest.json"
        try:
            os.environ["PIV_KEY_ID"] = rotation
            os.environ[FM.FAMILY_MANIFEST_ENV] = str(path)
            os.environ.pop("PIV_EVAL_SECRET", None)
            FM.write(records, secret, path, rotation=rotation)
            yield path
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def rewrite(path, mutate):
    body = json.loads(path.read_text(encoding="utf-8"))
    mutate(body)
    path.write_text(json.dumps(body, indent=1, sort_keys=True), encoding="utf-8")


# --------------------------------------------------------------------------
# separation from the bank family
# --------------------------------------------------------------------------

def test_the_family_manifest_is_separate_all_the_way_down():
    problems = []
    # Round 17, decision 4: the admission contract moved to 2 when
    # `cumulative_reversal_bounded` stopped capping a credit at the opening
    # balance. The manifest SCHEMA did not move — the record's shape is
    # unchanged, only what admission means.
    if (FM.FAMILY_MANIFEST_SCHEMA, FM.FAMILY_PREFLIGHT_CONTRACT) != (1, 2):
        problems.append(f"schema/preflight contract are {FM.FAMILY_MANIFEST_SCHEMA}/"
                        f"{FM.FAMILY_PREFLIGHT_CONTRACT}, not 1/2")
    if FM._FAMILY_SIGNING_DOMAIN == BANK._SIGNING_DOMAIN:
        problems.append("the family signs under the bank family's domain")
    if FM._signing_key(SECRET) == BANK._signing_key(SECRET):
        problems.append("the same evaluator secret yields the same signing key for both populations")
    if FM.FAMILY_MANIFEST_ENV == BANK.MANIFEST_ENV:
        problems.append("the two manifests share an environment variable")
    if FM.manifest_path() == BANK.manifest_path():
        problems.append("the two manifests share a default path")
    # A record signed for one population must not verify for the other.
    bank_record = BANK.sign(BANK.record("train", 1, "standard", "task-x", 0,
                                        {g: True for g in BANK.GATES}), SECRET)
    if FM.verify(bank_record, SECRET):
        problems.append("a bank record verifies under the family signing key")
    family_record = FM.sign(a_record(), SECRET)
    if BANK.verify(family_record, SECRET):
        problems.append("a family record verifies under the bank signing key")
    if "generator" in FM.semantic_components():
        problems.append("the family's semantic components carry the bank generator version")
    if str(MINT.GENERATOR_VERSION) in json.dumps(FM.semantic_components()):
        # A coincidental "9" would be a false alarm; check the KEY instead.
        if any(v == MINT.GENERATOR_VERSION for k, v in FM.semantic_components().items()
               if isinstance(v, int) and "generator" in k):
            problems.append("the family binds GENERATOR_VERSION under another name")
    return check("the family manifest is separate from manifest.py all the way down: its own signing domain "
                 "and key, its own environment variable and path, and neither population's records verify "
                 "under the other's key", not problems, "\n".join(problems))


def test_the_bank_family_is_untouched():
    problems = []
    if MINT.GENERATOR_VERSION != 9:
        problems.append(f"GENERATOR_VERSION is {MINT.GENERATOR_VERSION}, not 9")
    pinned = {"gate_set": "e2f26ab5cdf60d53", "generator": 9, "identify": 7, "manifest_schema": 2,
              "preflight_contract": 1, "renderer": 1, "scorer_contract": 1, "task_contract": 1}
    if BANK.versions() != pinned:
        problems.append(f"manifest.versions() moved: {BANK.versions()} vs the pinned {pinned}")
    if BANK.gate_set_digest() != "e2f26ab5cdf60d53":
        problems.append(f"the bank gate-set digest moved to {BANK.gate_set_digest()}")
    if BANK.GATES != ("minted", "identifiable", "repair_key_equal", "golden_scores_one", "id_unique",
                      "ledger_within_envelope"):
        problems.append(f"the bank gate set moved: {BANK.GATES}")
    if (BANK.MANIFEST_SCHEMA, BANK.PREFLIGHT_CONTRACT_VERSION) != (2, 1):
        problems.append("the bank manifest schema or preflight contract moved")
    if BANK._SIGNING_DOMAIN != b"piv:manifest-signing-key:v1\0":
        problems.append("the bank signing domain moved")
    # The unsigned starting declaration is still exactly that, and still says so.
    declared = BANK.family_admission_versions()
    if set(declared) != {"cash_application", "reference_identity", "identify"}:
        problems.append(f"family_admission_versions() now declares {sorted(declared)}")
    doc = BANK.family_admission_versions.__doc__ or ""
    for phrase in ("UNSIGNED STARTING DECLARATION", "NOT AN ADMISSION MECHANISM", "cash_manifest.py"):
        if phrase not in doc:
            problems.append(f"family_admission_versions no longer says {phrase!r}: decision 2 requires the "
                            f"code to note that it is an unsigned starting declaration, not an admission "
                            f"mechanism")
    return check("GENERATOR_VERSION 9, the bank manifest's versions, gate set, schema and signing domain are "
                 "untouched, and its family version declaration is still the unsigned starting declaration "
                 "it says it is", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# what a record binds
# --------------------------------------------------------------------------

def test_a_record_binds_everything_decision_two_lists():
    problems = []
    ident = an_identity()
    rec = a_record(ident)
    missing = sorted(set(FM.REQUIRED_RECORD_FIELDS) - set(rec))
    if missing:
        problems.append(f"the record is missing {missing}")
    expected = {
        "schema": 1, "family": "cash_application", "family_generator_version": 1,
        "identity": ident.view(), "identity_digest": ident.digest(), "parent_digest": ident.digest(),
        "variant": "a", "split": ident.split, "split_map_digest": PROBE_MAP.digest(),
        "public_id": "task-cash-0001", "public_content_digest": FM.public_content_digest(PUBLIC, PROMPT),
        "profile": "bounded-v1", "profile_digest": BOUNDED_V1.digest(),
        "baseline_catalogue": "cash_application_baselines/1",
        "baseline_catalogue_digest": FM.baseline_catalogue_digest(),
        "gate_set": FM.gate_set_digest(), "semantic_components": FM.semantic_components(),
        "runtime_scope": FM.runtime_scope(), "passed": True,
    }
    for key, want in expected.items():
        if rec.get(key) != want:
            problems.append(f"record[{key!r}] is {rec.get(key)!r}, not {want!r}")
    # Both variants of a pair name the SAME parent.
    if a_record(ident, "b")["parent_digest"] != rec["parent_digest"]:
        problems.append("the two variants of a pair do not name the same parent")
    if a_record(ident, "b")["identity"] != rec["identity"]:
        problems.append("the two variants of a pair carry different construction identities")
    # Gate hygiene.
    if raises(FM.FamilyManifestError, a_record, ident, "a", {g: True for g in FM.FAMILY_GATES[:-1]}) is None:
        problems.append("a record missing a gate was accepted")
    if raises(FM.FamilyManifestError, a_record, ident, "a",
              dict(all_gates(), invented_gate=True)) is None:
        problems.append("a record carrying an unknown gate was accepted")
    for truthy in (1, "ok", [], {"diagnostics": 1}):
        if raises(FM.FamilyManifestError, a_record, ident, "a",
                  dict(all_gates(), ar_reconciles=truthy)) is None:
            problems.append(f"a gate recorded as {truthy!r} was accepted as an answer")
    if a_record(ident, "a", dict(all_gates(), ar_reconciles=False))["passed"] is not False:
        problems.append("a failing gate did not clear the passed flag")
    if raises(FM.FamilyManifestError, a_record, ident, "c") is None:
        problems.append("an unknown variant was accepted")
    # The split is inherited from the frozen map, never restated.
    other = [s for s in ("train", "development", "evaluation") if s != ident.split][0]
    mismatched = identity(population="dev-96", split=other, template_family=PROBE_FAMILY,
                          template_version=1, company_month_index=0)
    message = raises(FM.FamilyManifestError, a_record, mismatched)
    if message is None or "inherited" not in message:
        problems.append(f"a record whose split disagrees with the frozen map was not refused by name: {message}")
    return check("a family record binds the construction identity, the public id and public-content digest, "
                 "the parent/variant relationship, the split-map digest, the profile and its digest, the "
                 "baseline catalogue and its digest, the exact gate set with real bools, the semantic "
                 "components and the runtime scope", not problems, "\n".join(problems))


def test_the_gate_set_is_decision_threes_six_headings_plus_gate_o():
    problems = []
    groups = dict(FM.GATE_GROUPS)
    for heading in ("accounting_integrity", "evidence_integrity", "representation_integrity",
                    "independent_correctness", "contrast_integrity", "population_integrity",
                    "baseline_resistance"):
        if heading not in groups:
            problems.append(f"the gate set has no {heading} group")
    named = {
        "accounting_integrity": ("invoice_universe_complete", "customer_ownership",
                                 "receipt_and_credit_conservation", "row_identities", "ar_reconciles",
                                 "zero_opening_write_off_balance", "consistent_sale_and_credit_tax_bases",
                                 "cumulative_reversal_bounded"),
        "evidence_integrity": ("genuine_payment_identity", "unambiguous_advice_binding",
                               "chronology_consistent_with_policy", "order_insensitive",
                               "no_refusal_relaxed_by_layout"),
        "independent_correctness": ("private_derivation_equals_public_fold",
                                    "planted_repairs_match_public_reading", "golden_ledger_scores_complete",
                                    "golden_register_scores_complete"),
        "population_integrity": ("no_public_content_collision", "no_cross_split_structural_sibling",
                                 "no_evaluator_provenance_leak"),
        "baseline_resistance": ("no_binding_baseline_reaches_truth", "reading_bound_respected",
                                "diagnostic_baseline_recorded"),
    }
    for heading, gates in named.items():
        if groups.get(heading) != gates:
            problems.append(f"{heading} declares {groups.get(heading)}, not {gates}")
    if len(set(FM.FAMILY_GATES)) != len(FM.FAMILY_GATES):
        problems.append("a gate name appears in two groups")
    if FM.FAMILY_GATES != FM.family_gates():
        problems.append("the module-level gate tuple has drifted from the groups it is derived from")
    # The digest binds names AND their group AND the contract version.
    baseline = FM.gate_set_digest()
    moved = (("a renamed gate", (("accounting_integrity", ("ar_ties",)),)),
             ("a gate moved between groups", (("evidence_integrity", ("ar_reconciles",)),)),
             ("a renamed group", (("accounting_correctness", ("ar_reconciles",)),)))
    original_groups, original_contract = FM.GATE_GROUPS, FM.FAMILY_PREFLIGHT_CONTRACT
    try:
        for label, groups_value in moved:
            FM.GATE_GROUPS = groups_value
            if FM.gate_set_digest() == baseline:
                problems.append(f"{label} did not move the gate-set digest")
        FM.GATE_GROUPS = original_groups
        FM.FAMILY_PREFLIGHT_CONTRACT = original_contract + 1
        if FM.gate_set_digest() == baseline:
            problems.append("bumping the preflight contract did not move the gate-set digest")
        # And the LIMIT, measured rather than glossed. The digest's inputs are
        # exactly {preflight_contract, groups} — recomputed here from those two
        # alone. No predicate is among them, so a gate whose meaning changes
        # under an unchanged name moves nothing until a human bumps the
        # contract; `baseline_catalogue_digest` is the one that digests
        # strategies and predicates themselves.
        FM.FAMILY_PREFLIGHT_CONTRACT = original_contract
        recomputed = domain_digest(
            FM._GATE_SET_DOMAIN,
            canonical_bytes({"preflight_contract": FM.FAMILY_PREFLIGHT_CONTRACT,
                             "groups": [[group, list(names)] for group, names in FM.GATE_GROUPS]}))[:16]
        if recomputed != baseline:
            problems.append("the gate-set digest is no longer a digest of exactly the gate names, their "
                            "groups and the preflight contract version: whatever else it now binds, the "
                            "docstring's account of what invalidates a record is wrong")
    finally:
        FM.GATE_GROUPS, FM.FAMILY_PREFLIGHT_CONTRACT = original_groups, original_contract
    return check(f"the exact gate set is decision 3's six admissibility headings plus gate (o), "
                 f"{len(FM.FAMILY_GATES)} named gates, and its digest binds each gate's name, its group and "
                 f"the preflight contract version — those three and nothing else, so a changed predicate "
                 f"under an unchanged name needs a contract bump", not problems, "\n".join(problems))


def test_the_baseline_catalogue_binds_more_than_names():
    problems = []
    view = FM.baseline_catalogue_view()
    if view["catalogue"] != "cash_application_baselines/1":
        problems.append(f"the catalogue is {view['catalogue']!r}, not cash_application_baselines/1")
    roles = [b["role"] for b in view["baselines"]]
    if (roles.count("binding"), roles.count("diagnostic")) != (9, 1):
        problems.append(f"the catalogue holds {roles.count('binding')} binding and "
                        f"{roles.count('diagnostic')} diagnostic baselines, not 9 and 1")
    diagnostic = [b["name"] for b in view["baselines"] if b["role"] == "diagnostic"]
    if diagnostic != ["number_order"]:
        problems.append(f"the diagnostic baseline is {diagnostic}, not ['number_order']")
    if view["bounds"]["max_readings"] != 256:
        problems.append(f"the reading bound is {view['bounds']['max_readings']}, not the 256 decision 3 keeps")
    if "verification-limit" not in view["enumeration"]["over_bound"]:
        problems.append("the catalogue does not declare an over-bound result as a verification-limit rejection")
    if "any enumerated reading" not in view["enumeration"]["rejects_when"]:
        problems.append("the catalogue does not declare the whole-case ANY-reading rule")
    for baseline in view["baselines"]:
        if not baseline["admitted_when"] or baseline["admitted_when"].startswith("<"):
            problems.append(f"{baseline['name']} records no admission predicate: {baseline['admitted_when']}")
    # The catalogue's declared ROLES, which the minting gate compares the
    # shipped tuple against. Decision 3 names diagnostic roles among the
    # things this version binds, and a declaration nobody reads is not one.
    if dict(FM.BASELINE_CATALOGUE_ROLES).get("number_order") != "diagnostic":
        problems.append(f"{FM.BASELINE_CATALOGUE_ID} does not declare number_order diagnostic")
    if FM.declared_role_counts() != {"binding": 9, "diagnostic": 1}:
        problems.append(f"{FM.BASELINE_CATALOGUE_ID} declares {FM.declared_role_counts()}, not 9 and 1")
    if FM.catalogue_role_findings():
        problems.append(f"the shipped catalogue disagrees with its own declaration: "
                        f"{FM.catalogue_role_findings()}")

    # REPRODUCIBLE, or it is not an identity. `predicate_digest` reads the
    # predicate's code object, and a predicate holding a comprehension or a
    # generator expression — `_any_deduction` and `_any_multi_reference` both
    # do — carries a NESTED CODE OBJECT whose repr is
    # `<code object <genexpr> at 0x..., file "...", line N>`. Digesting that
    # repr put a memory address into the catalogue's identity: the digest
    # changed on every run, so a record signed in one process stopped
    # verifying in the next and "the catalogue changed" could not be told
    # from "the process restarted". Witnessed here by compiling one source
    # twice: two different code objects at two different addresses from two
    # different file names, one implementation, one digest.
    source = "def probe(ev):\n    return any(line.deduction > 0 for line in ev)\n"
    first, second = {}, {}
    exec(compile(source, "<probe-one>", "exec"), first)             # noqa: S102
    exec(compile(source, "<probe-two>", "exec"), second)            # noqa: S102
    if FM.predicate_digest(first["probe"]) != FM.predicate_digest(second["probe"]):
        problems.append("two compilations of one predicate source digest differently: the digest binds "
                        "something that is not the implementation")
    third: dict = {}
    exec(compile(source.replace("> 0", "> 1"), "<probe-three>", "exec"), third)      # noqa: S102
    if FM.predicate_digest(third["probe"]) == FM.predicate_digest(first["probe"]):
        problems.append("a changed comparison INSIDE the generator expression did not move the digest: "
                        "recursing into nested code lost what repr at least saw")
    rendered = json.dumps([FM.predicate_view(b.admitted_when) for b in CA.BASELINES], sort_keys=True)
    for leak in ("0x", "cash_application.py", "<code object"):
        if leak in rendered:
            problems.append(f"the digested predicate payload carries {leak!r}, which is not the "
                            f"implementation and does not survive a restart")

    baseline_digest = FM.baseline_catalogue_digest()
    original_baselines, original_bound = CA.BASELINES, CA.MAX_BASELINE_READINGS
    try:
        promoted = tuple(CA.Baseline(b.name, b.strategy, b.admitted_when, False, b.description)
                         if b.name == "number_order" else b for b in CA.BASELINES)
        CA.BASELINES = promoted
        if FM.baseline_catalogue_digest() == baseline_digest:
            problems.append("silently promoting number_order into an admission rule did not move the digest")
        CA.BASELINES = tuple(CA.Baseline(b.name, CA.Strategy(unadviced="hold"), b.admitted_when,
                                         b.diagnostic, b.description)
                             if b.name == "oldest_first" else b for b in original_baselines)
        if FM.baseline_catalogue_digest() == baseline_digest:
            problems.append("changing a baseline's strategy did not move the digest")
        CA.BASELINES = tuple(CA.Baseline(b.name, b.strategy, (lambda ev: True), b.diagnostic, b.description)
                             if b.name == "credit_ignored" else b for b in original_baselines)
        if FM.baseline_catalogue_digest() == baseline_digest:
            problems.append("changing a baseline's admission predicate did not move the digest")
        CA.BASELINES = original_baselines
        CA.MAX_BASELINE_READINGS = 512
        if FM.baseline_catalogue_digest() == baseline_digest:
            problems.append("changing the reading bound did not move the digest")
    finally:
        CA.BASELINES, CA.MAX_BASELINE_READINGS = original_baselines, original_bound
    if FM.baseline_catalogue_digest() != baseline_digest:
        problems.append("the catalogue digest did not return to its value after the probes")
    return check("the baseline catalogue is versioned as cash_application_baselines/1, declares its own nine "
                 "binding and one diagnostic roles, and its digest binds strategies, admission predicates, "
                 "diagnostic roles, enumeration semantics and the 256-reading bound — not merely names, and "
                 "not one byte of memory address, path or line number, so it is the same digest in the next "
                 "process", not problems, "\n".join(problems))


def test_semantic_components_name_every_declared_component():
    problems = []
    components = FM.semantic_components()
    for name in ("public_fold", "reference_identity", "checker", "parser", "renderer",
                 "ledger_engine", "application_engine", "composite_engine"):
        if name not in components:
            problems.append(f"the semantic components do not name {name}")
    if components.get("public_fold", {}).get("version") != CA.CASH_APPLICATION_VERSION:
        problems.append("the public fold's version is not bound")
    if components.get("reference_identity") != ID.REFERENCE_IDENTITY_VERSION:
        problems.append("the reference identity's version is not bound")
    if components.get("checker") != ID.IDENTIFY_VERSION:
        problems.append("the checker's version is not bound")
    engines = (components.get("ledger_engine", {}).get("id"), components.get("application_engine"),
               components.get("composite_engine"))
    if engines != ("candidate/1", "application/1", "composite/1"):
        problems.append(f"the three scoring engines are {engines}")
    # A bump in any of them refuses a record signed before it.
    with a_manifest([a_record()]) as _:
        ident = an_identity()
        ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
        if not ok:
            problems.append(f"a valid record was not admitted: {why}")
        original = CA.CASH_APPLICATION_VERSION
        try:
            CA.CASH_APPLICATION_VERSION = original + 1
            ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
            if ok or "semantic components" not in why:
                problems.append(f"a bumped public fold still admitted: {ok} / {why}")
        finally:
            CA.CASH_APPLICATION_VERSION = original
    return check("the semantic components name the public fold, reference identity, checker, parser, renderer "
                 "and all three scoring engines, and a bump in any of them refuses a record proved against the "
                 "old one", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# admission
# --------------------------------------------------------------------------

def test_admit_reads_todays_gate_set_and_not_the_records_own_flag():
    problems = []
    ident = an_identity()
    with a_manifest([a_record(ident)]):
        ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
        if not ok:
            problems.append(f"a fully passed record was not admitted: {why}")
        for variant, expect in (("b", "absent from the family manifest"),):
            ok, why = FM.admit(SECRET, ident, variant, "task-cash-0001", CONTENT, split_map=PROBE_MAP)
            if ok or expect not in why:
                problems.append(f"variant {variant} of an unpreflighted pair: {ok} / {why}")
        ok, why = FM.admit(SECRET, ident, "a", "task-other", CONTENT, split_map=PROBE_MAP)
        if ok or "public id" not in why:
            problems.append(f"another public id still admitted: {ok} / {why}")
        ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", "0" * 64, split_map=PROBE_MAP)
        if ok or "public-content digest" not in why:
            problems.append(f"another public-content digest still admitted: {ok} / {why}")
        ok, why = FM.admit(OTHER_SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
        if ok:
            problems.append("a record admitted under another evaluator key")
        ok, why = FM.admit(SECRET, an_identity(index=4), "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
        if ok or "absent" not in why:
            problems.append(f"a selector nobody preflighted admitted: {ok} / {why}")
    # A gate recorded False, and the "gates all true, passed false" disagreement.
    with a_manifest([a_record(ident, gates=dict(all_gates(), ar_reconciles=False))]):
        ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
        if ok or "ar_reconciles" not in why:
            problems.append(f"a failed gate still admitted: {ok} / {why}")
    with a_manifest([a_record(ident)]) as path:
        rewrite(path, lambda body: body["records"][0].__setitem__("passed", False))
        ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
        if ok:
            problems.append("a tampered record admitted despite an invalid signature")
        elif "signature" not in why:
            problems.append(f"the tamper was caught, but not as a signature failure: {why}")

    # The real point: a record signed against ANOTHER gate set, correctly, must
    # still be refused — the historical aggregate is never trusted on its own.
    original = FM.GATE_GROUPS
    try:
        FM.GATE_GROUPS = tuple((g, n) for g, n in original if g != "baseline_resistance")
        old_gates = tuple(n for _, names in FM.GATE_GROUPS for n in names)
        stale = FM.record(ident, "a", public_id="task-cash-0001", content_digest=CONTENT,
                          structure_digest=STRUCTURE, profile_name=BOUNDED_V1.name, attempt=0,
                          gates={g: True for g in old_gates}, split_map=PROBE_MAP)
    finally:
        FM.GATE_GROUPS = original
    with a_manifest([stale]):
        ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
        if ok:
            problems.append("a record preflighted against a SMALLER gate set kept admitting: the manifest "
                            "would be asserting gates the record was never tested against")
    return check("admission compares today's gate set and every gate's real bool, refuses another key, "
                 "another public id or content digest, an unpreflighted selector, a tampered record and a "
                 "record proved against a smaller gate set", not problems, "\n".join(problems))


def test_admit_refuses_a_moved_split_map_catalogue_or_rotation():
    problems = []
    ident = an_identity()
    with a_manifest([a_record(ident)]):
        grown = SplitMap.seal(PROBE_ROSTER + (TemplateFamily("probe_later", "credit_residue"),),
                              previous=PROBE_MAP)
        ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=grown)
        if ok or "split map" not in why:
            problems.append(f"a re-sealed split map still admitted: {ok} / {why}")
        original = CA.MAX_BASELINE_READINGS
        try:
            CA.MAX_BASELINE_READINGS = 512
            ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
            if ok or "baseline catalogue" not in why:
                problems.append(f"a changed baseline catalogue still admitted: {ok} / {why}")
        finally:
            CA.MAX_BASELINE_READINGS = original
    # Another rotation: the file is simply not the active one.
    with a_manifest([a_record(ident)], rotation="another-rotation-0002"):
        os.environ["PIV_KEY_ID"] = ROTATION
        ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
        if ok or "no cash-application release manifest" not in why:
            problems.append(f"a manifest for another rotation was treated as active: {ok} / {why}")
    # Duplicates refuse the WHOLE manifest.
    with a_manifest([a_record(ident), a_record(ident)]):
        ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
        if ok or "duplicate" not in why:
            problems.append(f"a manifest holding two records for one selector still admitted: {ok} / {why}")
    # A manifest for the wrong family or schema is not the active one either.
    for field, value in (("family", "bank_reconciliation"), ("schema", 2), ("family_generator_version", 2)):
        with a_manifest([a_record(ident)]) as path:
            rewrite(path, lambda body, f=field, v=value: body.__setitem__(f, v))
            ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
            if ok:
                problems.append(f"a manifest whose {field} is {value!r} was treated as active")
    return check("admission refuses a re-sealed split map, a changed baseline catalogue, a manifest for "
                 "another rotation, family, schema or generator version, and a manifest holding duplicate "
                 "records for one selector", not problems, "\n".join(problems))


def test_a_record_may_not_publish_a_field_nobody_checked():
    """The free-text fields, at both doors.

    A signature binds whatever it is handed. `record` once accepted
    `structure_digest=None` or `""`, a `public_id` of `None`, an `attempt` of
    9999 against decision 3's bounded 64, and a `profile` naming a profile the
    identity was never drawn under — each signing and verifying perfectly, and
    three of them never read by `admit` at all. The module docstring presents
    all of them as bound, so they are checked."""
    problems = []
    ident = an_identity()

    def make(**changes):
        kwargs = dict(public_id="task-cash-0001", content_digest=CONTENT, structure_digest=STRUCTURE,
                      profile_name=BOUNDED_V1.name, attempt=0, gates=all_gates(), split_map=PROBE_MAP)
        kwargs.update(changes)
        return FM.record(ident, "a", **kwargs)

    refused = {
        "a structure digest of None": dict(structure_digest=None),
        "an empty structure digest": dict(structure_digest=""),
        "a truncated structure digest": dict(structure_digest="0" * 31),
        "an upper-case structure digest": dict(structure_digest="A" * 32),
        "a public id of None": dict(public_id=None),
        "a blank public id": dict(public_id="   "),
        "a public id with surrounding space": dict(public_id=" task-cash-0001"),
        "a content digest of None": dict(content_digest=None),
        "a half-width content digest": dict(content_digest="0" * 32),
        "a profile name nobody declared": dict(profile_name="hard-v9"),
        "an attempt beyond the bounded 64": dict(attempt=FM.MAX_LAYOUT_ATTEMPTS),
        "a negative attempt": dict(attempt=-5),
        "an attempt that is not an int": dict(attempt="0"),
    }
    for label, change in refused.items():
        if raises(FM.FamilyManifestError, make, **change) is None:
            problems.append(f"record() signed {label}")
    if make() is None:
        problems.append("a well-formed record was refused")
    # The reviewer's exact case: a declared profile NAME whose bounds are not
    # the ones this identity was drawn under.
    tweaked = dataclasses.replace(BOUNDED_V1, max_dependency_depth=BOUNDED_V1.max_dependency_depth + 1)
    elsewhere = identity(population="dev-96", split=PROBE_MAP.split_of(PROBE_FAMILY),
                         template_family=PROBE_FAMILY, template_version=1, company_month_index=0,
                         profile=tweaked)
    message = raises(FM.FamilyManifestError, FM.record, elsewhere, "a", public_id="task-cash-0001",
                     content_digest=CONTENT, structure_digest=STRUCTURE, profile_name=BOUNDED_V1.name,
                     attempt=0, gates=all_gates(), split_map=PROBE_MAP)
    if message is None:
        problems.append("a record published the profile name 'bounded-v1' for a world drawn under other bounds")

    # And at the SERVING door, on records that are correctly signed: the
    # signature is not the check, because the signature binds the defect.
    for label, field, value in (("a structure digest that is not a digest", "structure_digest", None),
                                ("an attempt beyond the bounded 64", "attempt", 9999),
                                ("a profile the world was never drawn under", "profile", "hard-v9")):
        forged = copy.deepcopy(a_record(ident))
        forged[field] = value
        with a_manifest([forged]):
            ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
            if not FM.verify(FM.sign(forged, SECRET), SECRET):
                problems.append(f"the probe for {label} did not produce a signable record")
            if ok:
                problems.append(f"admit served a correctly signed record binding {label}")
            elif "binds" not in why:
                problems.append(f"{label} was refused for another reason: {why}")
    # The public-content digest is no longer something a caller can forget.
    with a_manifest([a_record(ident)]):
        if raises(TypeError, FM.admit, SECRET, ident, "a", "task-cash-0001") is None:
            problems.append("admit still accepts a call with no public-content digest: a comparison enforced "
                            "only when the caller remembers is not a binding at the serving door")
    return check("a record may not publish a field nobody checked: record() refuses a malformed structure or "
                 "content digest, an empty public id, an out-of-range attempt and a profile name the world "
                 "was not drawn under, admit refuses the same on a correctly signed record, and the "
                 "public-content digest is a required argument", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# runtime scope and episode settings
# --------------------------------------------------------------------------

def test_runtime_dependent_evidence_uses_the_one_unicode_convention():
    problems = []
    scope = FM.runtime_scope()
    if scope.get("unicode_database") != unicodedata.unidata_version:
        problems.append(f"the scope's Unicode key is {scope.get('unicode_database')!r}, not the interpreter's "
                        f"{unicodedata.unidata_version!r}")
    for field in ("implementation", "version", "system", "machine"):
        if not scope.get("native_runtime", {}).get(field):
            problems.append(f"the native runtime records no {field}")
    if FM.runtime_scope_key() != unicodedata.unidata_version:
        problems.append("the scope key is not the Unicode database version")
    with substituted_unicode_version("99.0.0"):
        if FM.runtime_scope_key() != "99.0.0":
            problems.append("the scope key does not follow what the interpreter reports")
    # The convention, not a third table: rows, shape and the refusal all come
    # from tests/unicode_pins.py.
    RUNTIME_SCOPED.check_shape(problems)
    RUNTIME_SCOPED.check_refuses_an_unpinned_version(
        problems, must_say=("is NOT pinned", "under review"))
    row = RUNTIME_SCOPED.resolve(NATIVE_UNICODE_VERSION, problems)
    if row is not None and row["parser"] != FM.semantic_components()["parser"]:
        problems.append(f"the parser component is {FM.semantic_components()['parser']}, not the pinned "
                        f"{row['parser']} for unicode {NATIVE_UNICODE_VERSION}")
    # And a record taken under another database is refused rather than reused.
    ident = an_identity()
    with a_manifest([a_record(ident)]) as path:
        rewrite(path, lambda body: body["records"][0]["runtime_scope"].__setitem__(
            "unicode_database", "16.0.0"))
        ok, why = FM.admit(SECRET, ident, "a", "task-cash-0001", CONTENT, split_map=PROBE_MAP)
        if ok:
            problems.append("a record whose runtime-dependent evidence came from another Unicode database "
                            "was admitted")
    return check("runtime-dependent evidence is scoped by Unicode database and native runtime through the one "
                 "convention in tests/unicode_pins.py — the shipped code publishes the key, the suite pins the "
                 "rows with their provenance, and an unpinned database is refused rather than believed",
                 not problems, "\n".join(problems))


def test_episode_settings_never_enter_a_family_record():
    problems = []
    rec = a_record()
    text = json.dumps(rec, sort_keys=True)
    for key in ("max_episode_output_tokens", "max_total_completion_tokens", "max_turns",
                "episode_contract_digest", "temperature"):
        if f'"{key}"' in text:
            problems.append(f"the record carries the episode setting {key}")
    injected = copy.deepcopy(rec)
    injected["experiment"] = {"max_total_completion_tokens": 40_000}
    if raises(IdentityError, FM.refuse_episode_settings, "a probe record", injected) is None:
        problems.append("an episode setting pasted into a record was not refused")
    # Records built under different budgets are byte-identical. Driven through
    # the REAL knob: the ambient `MAX_EPISODE_OUTPUT_TOKENS` that
    # `load_environment` reads at call time, with the moved episode digests
    # measured alongside so the probe cannot silently move nothing.
    import beancount_ledger.beancount_ledger as env_mod
    budgets = (8_000, 24_000, 40_000)
    episodes = {budget: env_mod.episode_contract_digest(budget) for budget in budgets}
    if len(set(episodes.values())) != len(episodes):
        problems.append(f"the episode digests did not separate the budgets, so nothing moved: {episodes}")
    built = set()
    ceiling = env_mod.MAX_EPISODE_OUTPUT_TOKENS
    try:
        for budget in budgets:
            env_mod.MAX_EPISODE_OUTPUT_TOKENS = budget
            built.add(json.dumps(a_record(), sort_keys=True))
    finally:
        env_mod.MAX_EPISODE_OUTPUT_TOKENS = ceiling
    if len(built) != 1:
        problems.append(f"a token budget changed the record: {len(built)} distinct bodies")
    # No record may carry any of those three digests either, under any key.
    body = json.dumps(a_record(), sort_keys=True)
    for budget, digest in episodes.items():
        if digest in body:
            problems.append(f"the record carries the episode-contract digest for the {budget} ceiling")
    return check("episode settings never enter a family record: none of the budget or turn-cap keys appears "
                 "in one, pasting one in is refused, no episode-contract digest appears under any key, and "
                 "three budgets that really move that digest produce byte-identical records",
                 not problems, "\n".join(problems))


def test_the_public_content_digest_binds_only_what_the_model_is_shown():
    problems = []
    base = FM.public_content_digest(PUBLIC, PROMPT)
    if FM.public_content_digest(dict(PUBLIC), PROMPT) != base:
        problems.append("the digest is not a pure function of the public bytes")
    if FM.public_content_digest(PUBLIC, PROMPT + " ") == base:
        problems.append("changing the instruction did not move the digest: the prompt is a public surface too")
    moved = dict(PUBLIC, **{"open_items.csv": PUBLIC["open_items.csv"] + "SI-3101,Gannet Rigging Inc\n"})
    if FM.public_content_digest(moved, PROMPT) == base:
        problems.append("changing a public file did not move the digest")
    if raises(FM.FamilyManifestError, FM.public_content_digest, ["not", "a", "mapping"], PROMPT) is None:
        problems.append("a non-mapping was accepted as the public files")
    return check("the public-content digest binds exactly the public files and the instruction — what the "
                 "model is shown — and nothing private", not problems, "\n".join(problems))


TESTS = [
    test_the_family_manifest_is_separate_all_the_way_down,
    test_the_bank_family_is_untouched,
    test_a_record_binds_everything_decision_two_lists,
    test_the_gate_set_is_decision_threes_six_headings_plus_gate_o,
    test_the_baseline_catalogue_binds_more_than_names,
    test_semantic_components_name_every_declared_component,
    test_admit_reads_todays_gate_set_and_not_the_records_own_flag,
    test_admit_refuses_a_moved_split_map_catalogue_or_rotation,
    test_a_record_may_not_publish_a_field_nobody_checked,
    test_runtime_dependent_evidence_uses_the_one_unicode_convention,
    test_episode_settings_never_enter_a_family_record,
    test_the_public_content_digest_binds_only_what_the_model_is_shown,
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
