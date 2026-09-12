"""The `cash_application` family's OWN manifest schema and preflight contract,
both version 1.

Decision 2:

    Create a separate family manifest schema and preflight contract, both
    version 1. Bind the construction identity, public-content digest,
    parent/variant relationship, split-map digest, profile, baseline
    catalogue, exact gate set and relevant semantic components: public fold,
    reference identity, checker, parser, renderer and all three scoring
    engines. Scope runtime-dependent evidence by Unicode database and native
    runtime.

SEPARATE FROM `manifest.py`, ALL THE WAY DOWN. A different schema number
would not be enough: the bank family's records are signed under
`piv:manifest-signing-key:v1` and bound to `manifest.versions()`, whose
`generator` key is `GENERATOR_VERSION` (9). Anything this family bound into
that dict would invalidate every v9 record still serving, and a v9 bump would
invalidate every record here. So this module has:

    signing domain     piv:cash-application-manifest-signing-key:v1
    manifest file      PIV_CASH_APPLICATION_MANIFEST, else
                       ~/.piv/cash_application_manifest.json
    versions           `semantic_components()`, which never reads
                       `GENERATOR_VERSION`

and shares with `manifest.py` only the rotation id (which travels with the
secret and labels the key, not the population) and the evaluator secret
itself, read through `mint.evaluator_secret`.

WHAT THE RECORD BINDS, and why each one is here rather than assumed:

    construction identity     `cash_identity.ConstructionIdentity.view()`, the
                              closed eight-key set, plus its digest;
    parent/variant            the parent identity digest and which variant
                              this record is — the pair is the unit of
                              acceptance (decision 3: reject BOTH variants
                              when either fails), so a record names its
                              sibling's parent and cannot be served alone;
    public-content digest     what the model is shown, and nothing else;
    split-map digest          the frozen template-to-split map this world was
                              drawn under, so a re-sealed map re-preflights;
    profile                   name AND complete digest — two profiles sharing
                              a name and differing in a bound are different;
    baseline catalogue        `cash_application_baselines/1` and a digest over
                              strategies, admission predicates, diagnostic
                              roles, enumeration semantics and bounds, not
                              merely names (decision 3);
    exact gate set            every gate NAME and its group, digested, plus
                              each gate's real bool. `admit` compares against
                              today's set, never against the record's own
                              `passed` flag — the lesson `manifest.py` records
                              at length;
    semantic components       public fold, reference identity, checker,
                              parser, renderer, and all three scoring engines
                              (`candidate/1`, `application/1`, `composite/1`);
    runtime scope             the Unicode database and the native runtime the
                              record's runtime-dependent evidence was taken
                              under.

WHAT IT REFUSES TO BIND: episode settings. Token budgets, turn caps and the
episode-contract digest identify an EPISODE and live in the experiment record.
`cash_identity.refuse_episode_settings` runs over every record built here, so
a budget cannot reach a world's identity even by being pasted into a record.
`tests/test_cash_family_manifest.py` pins that.

RUNTIME-DEPENDENT EVIDENCE. `parse_policy_view()` records
`unicodedata.unidata_version`, so `parse_policy_digest()` — the parser
component below — legitimately moves when the interpreter's Unicode database
changes with nothing else moving. That is the same fact `tests/unicode_pins.py`
exists for, and this module does NOT introduce a third table for it: it
publishes the SCOPE (`runtime_scope()`, keyed by `unicodedata.unidata_version`
exactly as the interpreter reports it) and the suite pins the scoped values
through the shared `UnicodeScopedPins`, with the same provenance discipline —
`native` versus `derived-by-substitution`, and a refusal rather than a
fallback on a database nobody has reviewed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import unicodedata
from dataclasses import asdict
from pathlib import Path

from ..candidate.canonical import canonical_bytes, domain_digest
from .cash_identity import (
    FAMILY,
    FAMILY_GENERATOR_VERSION,
    VARIANTS,
    ConstructionIdentity,
    refuse_episode_settings,
)
from .cash_split import SPLIT_MAP, SplitMap
from .manifest import rotation_id

FAMILY_MANIFEST_SCHEMA = 1
FAMILY_PREFLIGHT_CONTRACT = 1
FAMILY_MANIFEST_ENV = "PIV_CASH_APPLICATION_MANIFEST"
_FAMILY_SIGNING_DOMAIN = b"piv:cash-application-manifest-signing-key:v1\0"
_GATE_SET_DOMAIN = b"piv:cash-application-preflight-gates:v1\0"
_BASELINE_CATALOGUE_DOMAIN = b"piv:cash-application-baselines:v1\0"
_PUBLIC_CONTENT_DOMAIN = b"piv:cash-application-public-content:v1\0"

#: Decision 3: version the baseline catalogue independently.
BASELINE_CATALOGUE_ID = "cash_application_baselines/1"


class FamilyManifestError(ValueError):
    """A family manifest record that may not exist."""


# --------------------------------------------------------------------------
# the exact gate set
# --------------------------------------------------------------------------

#: Decision 3's six admissibility headings, plus gate (o) as its own group,
#: each expanded into the named gates a candidate pair must satisfy.
#:
#: DECLARED HERE, IMPLEMENTED BY THE PREFLIGHT. This module does not run a
#: gate; it fixes what the set IS, so that a record cannot be signed while a
#: gate is missing and cannot be admitted while a gate is anything but `True`.
#: A gate that no preflight implements yet therefore blocks admission rather
#: than passing silently, which is the correct direction for the mistake.
GATE_GROUPS = (
    # complete opening-plus-in-period invoice universe; customer ownership;
    # receipt and credit conservation; row identities; AR reconciliation; zero
    # opening write-off balance; consistent original-sale and credit-tax
    # bases; bounded cumulative reversal where several notes hit one sale.
    ("accounting_integrity", (
        "invoice_universe_complete",
        "customer_ownership",
        "receipt_and_credit_conservation",
        "row_identities",
        "ar_reconciles",
        "zero_opening_write_off_balance",
        "consistent_sale_and_credit_tax_bases",
        "cumulative_reversal_bounded",
    )),
    # genuine payment identity, unambiguous advice binding, dates and
    # chronology consistent with policy, the existing order-sensitivity
    # checks, and no refusal relaxed merely because a layout meets it.
    ("evidence_integrity", (
        "genuine_payment_identity",
        "unambiguous_advice_binding",
        "chronology_consistent_with_policy",
        "order_insensitive",
        "no_refusal_relaxed_by_layout",
    )),
    # parse the rendered files through the shipped boundaries; CSV columns,
    # memo/narration agreement, string limits, delivery envelopes.
    ("representation_integrity", (
        "renders_and_parses_through_shipped_boundaries",
        "csv_columns_declared",
        "memo_narration_agreement",
        "string_limits_respected",
        "delivery_envelope_respected",
    )),
    # private derivation equals the public fold; every planted repair matches
    # the independent public reading; both golden artifacts score complete
    # through the actual engines.
    ("independent_correctness", (
        "private_derivation_equals_public_fold",
        "planted_repairs_match_public_reading",
        "golden_ledger_scores_complete",
        "golden_register_scores_complete",
    )),
    # the pair differs in its declared authored fact, with all consequent
    # changes derived, and the intended accounting distinction really changes.
    ("contrast_integrity", (
        "variants_differ_in_declared_fact",
        "consequences_derived_not_authored",
        "intended_distinction_changes",
    )),
    # no public-content collisions, no cross-split structural siblings, no
    # evaluator provenance leakage.
    ("population_integrity", (
        "no_public_content_collision",
        "no_cross_split_structural_sibling",
        "no_evaluator_provenance_leak",
    )),
    # gate (o): nine binding baselines and one diagnostic. An admitted binding
    # baseline reaching the entire truth through ANY enumerated reading
    # rejects the candidate; exceeding the 256-reading bound is a
    # VERIFICATION-LIMIT rejection, not resistance; `number_order` stays
    # diagnostic and its result is recorded regardless.
    ("baseline_resistance", (
        "no_binding_baseline_reaches_truth",
        "reading_bound_respected",
        "diagnostic_baseline_recorded",
    )),
)

def family_gates() -> tuple:
    """The flat gate set, derived from `GATE_GROUPS` at call time. Everything
    that enforces the set reads THIS rather than the module-level tuple, so a
    gate added to a group cannot be enforced by one half of the module and
    ignored by the other."""
    return tuple(name for _, names in GATE_GROUPS for name in names)


#: The same tuple, for readers. `family_gates()` is the authority.
FAMILY_GATES = family_gates()


def gate_set_digest() -> str:
    """A canonical digest of the gate names AND the group each belongs to,
    plus the preflight contract version — so renaming a group, moving a gate
    between groups, or changing a gate's meaning under an unchanged name all
    invalidate every record that bound this."""
    payload = canonical_bytes({"preflight_contract": FAMILY_PREFLIGHT_CONTRACT,
                               "groups": [[group, list(names)] for group, names in GATE_GROUPS]})
    return domain_digest(_GATE_SET_DOMAIN, payload)[:16]


# --------------------------------------------------------------------------
# the baseline catalogue
# --------------------------------------------------------------------------

def baseline_catalogue_view() -> dict:
    """The catalogue as declared data: strategies, admission predicates,
    diagnostic roles, enumeration semantics and bounds — not merely names.

    Decision 3: "Changing any of those requires a new catalogue version and
    re-preflight." The digest below is what makes that true rather than
    aspirational."""
    from .cash_application import (
        BASELINES,
        MAX_BASELINE_READINGS,
        POLICY,
        SHORT_PAY_TOLERANCE,
    )
    return {
        "catalogue": BASELINE_CATALOGUE_ID,
        "truth_strategy": asdict(POLICY),
        "short_pay_tolerance": str(SHORT_PAY_TOLERANCE),
        "bounds": {"max_readings": MAX_BASELINE_READINGS},
        "enumeration": {
            "rejects_when": "any enumerated reading of an admitted binding baseline reaches the entire truth",
            "compared_on": ["every receipt line", "every credit application", "every register row"],
            "amount_only_branching": "every exact subset of the payer's open balances",
            "over_bound": "verification-limit rejection: the candidate was not shown to resist the baseline",
        },
        "baselines": [
            {"name": b.name, "strategy": asdict(b.strategy),
             "admitted_when": getattr(b.admitted_when, "__name__", repr(b.admitted_when)),
             "role": "diagnostic" if b.diagnostic else "binding",
             "description": b.description}
            for b in BASELINES
        ],
    }


def baseline_catalogue_digest() -> str:
    return domain_digest(_BASELINE_CATALOGUE_DOMAIN, canonical_bytes(baseline_catalogue_view()))[:32]


# --------------------------------------------------------------------------
# semantic components and runtime scope
# --------------------------------------------------------------------------

def semantic_components() -> dict:
    """Every semantic component a family record is bound to: the public fold,
    the reference identity, the checker, the parser, the renderer and all
    three scoring engines.

    `mint.GENERATOR_VERSION` is deliberately absent. The bank family's
    generator built no world here, and coupling the two numbers is exactly
    what decision 2 forbids.
    """
    from ..candidate.application import APPLICATION_ENGINE_ID, APPLICATION_SCHEMA
    from ..candidate.canonical import (
        CANDIDATE_ENGINE,
        RENDERER_VERSION,
        SCORE_REDUCTION_VERSION,
        SCORER_CONTRACT_VERSION,
        TASK_CONTRACT_VERSION,
        parse_policy_digest,
    )
    from ..candidate.composite import COMPOSITE_ENGINE_ID
    from .cash_application import CASH_APPLICATION_VERSION
    from .identify import IDENTIFY_VERSION, REFERENCE_IDENTITY_VERSION
    return {
        "public_fold": {"version": CASH_APPLICATION_VERSION, "schema": APPLICATION_SCHEMA},
        "reference_identity": REFERENCE_IDENTITY_VERSION,
        "checker": IDENTIFY_VERSION,
        # The parser's identity, Unicode-scoped: `parse_policy_view()` records
        # `unicodedata.unidata_version`, which is why `runtime_scope()` below
        # exists and why the suite pins this per database rather than
        # recomputing it and calling that agreement.
        "parser": parse_policy_digest(),
        "renderer": RENDERER_VERSION,
        "ledger_engine": {"id": CANDIDATE_ENGINE.id, "scorer_contract": SCORER_CONTRACT_VERSION,
                          "task_contract": TASK_CONTRACT_VERSION,
                          "score_reduction": SCORE_REDUCTION_VERSION},
        "application_engine": APPLICATION_ENGINE_ID,
        "composite_engine": COMPOSITE_ENGINE_ID,
        "family_manifest_schema": FAMILY_MANIFEST_SCHEMA,
        "family_preflight_contract": FAMILY_PREFLIGHT_CONTRACT,
        "gate_set": gate_set_digest(),
    }


def runtime_scope() -> dict:
    """The scope runtime-dependent evidence is filed under: the Unicode
    database, keyed exactly as the interpreter reports it, and the native
    runtime that observed it.

    Same convention as `tests/unicode_pins.py`, not a second copy of it: the
    KEY is `unicodedata.unidata_version`, and the suite holds the pinned rows
    in a `UnicodeScopedPins` table with the `native` /
    `derived-by-substitution` provenance the convention requires. Shipped code
    publishes the scope; the table that says which scopes have been reviewed
    lives in `tests/`, which is excluded from both artifacts."""
    return {
        "unicode_database": unicodedata.unidata_version,
        "native_runtime": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
        },
    }


def runtime_scope_key() -> str:
    """The one key a runtime-scoped pin is filed under."""
    return unicodedata.unidata_version


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------

REQUIRED_RECORD_FIELDS = (
    "attempt", "baseline_catalogue", "baseline_catalogue_digest", "family", "family_generator_version",
    "gate_set", "gates", "identity", "identity_digest", "parent_digest", "passed", "profile",
    "profile_digest", "public_content_digest", "public_id", "runtime_scope", "schema",
    "semantic_components", "split", "split_map_digest", "structure_digest", "variant",
)


def public_content_digest(public_files: dict, prompt: str) -> str:
    """A digest of exactly what the model is shown: the public files and the
    instruction. Never the seed, the identity, the truth register or the
    plants — each of which a generator could be run against."""
    if not isinstance(public_files, dict) or not all(isinstance(k, str) for k in public_files):
        raise FamilyManifestError("public_files is a mapping of file name to text")
    return domain_digest(_PUBLIC_CONTENT_DOMAIN,
                         canonical_bytes({"files": dict(public_files), "prompt": prompt}))


def parent_digest(ident: ConstructionIdentity) -> str:
    """The pair's identity. Both variants share it, because they share the
    parent world; a record naming a variant therefore names its sibling too,
    and the pair is the unit of acceptance."""
    return ident.digest()


def family_selector_key(ident: ConstructionIdentity, variant: str) -> str:
    if variant not in VARIANTS:
        raise FamilyManifestError(f"variant is {variant!r}, not one of {list(VARIANTS)}")
    return f"{ident.digest()}:{variant}"


def record(ident: ConstructionIdentity, variant: str, *, public_id: str, content_digest: str,
           structure_digest: str, profile_name: str, attempt: int, gates: dict,
           split_map: SplitMap = SPLIT_MAP) -> dict:
    """An unsigned family record.

    `gates` must map every name in `FAMILY_GATES` to a real bool.
    `is True` / `is False`, not truthiness: a gate whose result is `1`, `"ok"`
    or a diagnostics object is a preflight that did not answer the question
    asked, and coercing it here would sign the coercion — `admit` compares the
    same way."""
    if not isinstance(ident, ConstructionIdentity):
        raise FamilyManifestError(f"record needs a ConstructionIdentity, not {type(ident).__name__}")
    if variant not in VARIANTS:
        raise FamilyManifestError(f"variant is {variant!r}, not one of {list(VARIANTS)}")
    declared = family_gates()
    if set(gates) != set(declared):
        missing = sorted(set(declared) - set(gates))
        extra = sorted(set(gates) - set(declared))
        raise FamilyManifestError(f"gates must be exactly the {len(declared)} declared family gates; "
                                  f"missing {missing}, unexpected {extra}")
    wrong = {g: gates[g] for g in declared if gates[g] is not True and gates[g] is not False}
    if wrong:
        raise FamilyManifestError(f"gate results must be True or False, not {wrong}")
    if split_map.split_of(ident.template_family) != ident.split:
        raise FamilyManifestError(
            f"the construction identity says split {ident.split!r} and the frozen split map assigns "
            f"{ident.template_family!r} to {split_map.split_of(ident.template_family)!r}: a template family's "
            f"split is inherited, never restated")
    body = {
        "schema": FAMILY_MANIFEST_SCHEMA,
        "family": FAMILY,
        "family_generator_version": FAMILY_GENERATOR_VERSION,
        "identity": ident.view(),
        "identity_digest": ident.digest(),
        "parent_digest": parent_digest(ident),
        "variant": variant,
        "split": ident.split,
        "split_map_digest": split_map.digest(),
        "structure_digest": structure_digest,
        "public_id": public_id,
        "public_content_digest": content_digest,
        "profile": profile_name,
        "profile_digest": ident.profile_digest,
        "baseline_catalogue": BASELINE_CATALOGUE_ID,
        "baseline_catalogue_digest": baseline_catalogue_digest(),
        "gate_set": gate_set_digest(),
        "gates": {g: gates[g] for g in declared},
        "semantic_components": semantic_components(),
        "runtime_scope": runtime_scope(),
        "attempt": int(attempt),
        "passed": all(gates[g] is True for g in declared),
    }
    refuse_episode_settings("a family manifest record", body)
    missing = sorted(set(REQUIRED_RECORD_FIELDS) - set(body))
    if missing:
        raise FamilyManifestError(f"the record is missing required fields {missing}")
    return body


def _material(rec: dict) -> bytes:
    return canonical_bytes({k: v for k, v in rec.items() if k != "signature"})


def _signing_key(secret: bytes) -> bytes:
    """The family's signing key. A DIFFERENT domain from `manifest.py`'s, so
    the same evaluator secret yields a different key and a record cannot be
    moved between the two populations."""
    return hmac.new(bytes(secret), _FAMILY_SIGNING_DOMAIN, hashlib.sha256).digest()


def sign(rec: dict, secret: bytes) -> dict:
    signed = dict(rec)
    signed["signature"] = hmac.new(_signing_key(secret), _material(rec), hashlib.sha256).hexdigest()
    return signed


def verify(rec: dict, secret: bytes) -> bool:
    signature = rec.get("signature")
    if not isinstance(signature, str):
        return False
    expected = hmac.new(_signing_key(secret), _material(rec), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def manifest_path() -> Path:
    raw = os.environ.get(FAMILY_MANIFEST_ENV)
    if raw:
        return Path(raw)
    return Path(os.path.expanduser("~")) / ".piv" / "cash_application_manifest.json"


def write(records: list, secret: bytes, path: Path | None = None, *, rotation: str | None = None) -> Path:
    """Write a family manifest for this rotation."""
    rotation = rotation or rotation_id()
    if not rotation:
        raise FamilyManifestError("no rotation id provisioned: set PIV_KEY_ID or ~/.piv/key_id")
    path = path or manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema": FAMILY_MANIFEST_SCHEMA, "family": FAMILY,
            "family_generator_version": FAMILY_GENERATOR_VERSION, "rotation_id": rotation,
            "semantic_components": semantic_components(), "runtime_scope": runtime_scope(),
            "records": [sign(r, secret) for r in records]}
    path.write_text(json.dumps(body, indent=1, sort_keys=True), encoding="utf-8")
    return path


def load_active(secret: bytes, path: Path | None = None) -> dict | None:
    """The family manifest for THIS rotation, or None. A manifest for another
    rotation, another schema or another family is not an error; it is simply
    not the active one."""
    path = path or manifest_path()
    if not path.is_file():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    current = rotation_id()
    if (not isinstance(body, dict) or body.get("schema") != FAMILY_MANIFEST_SCHEMA
            or body.get("family") != FAMILY
            or body.get("family_generator_version") != FAMILY_GENERATOR_VERSION
            or not current or body.get("rotation_id") != current):
        return None
    records, duplicates = {}, []
    for rec in body.get("records", []):
        if isinstance(rec, dict) and isinstance(rec.get("identity_digest"), str) and rec.get("variant") in VARIANTS:
            key = f"{rec['identity_digest']}:{rec['variant']}"
            if key in records:
                # Two records for one selector attest nothing about it, and
                # last-write-wins would hide the disagreement.
                duplicates.append(key)
            records[key] = rec
    if duplicates:
        return {"path": path, "records": {}, "duplicates": sorted(set(duplicates))}
    return {"path": path, "records": records, "duplicates": []}


def admit(secret: bytes, ident: ConstructionIdentity, variant: str, public_id: str,
          content_digest: str | None = None, *, split_map: SplitMap = SPLIT_MAP) -> tuple[bool, str]:
    """May this freshly minted world be served? Every refusal names its
    reason; none of them reveals anything about the world.

    There is no development bypass here. `manifest.py` has one because the
    bank family's suites mint under a test secret and must run; this
    population has no instances yet, and when it has them the preflight will
    be the only door. Adding a bypass later would need its own argument."""
    active = load_active(secret)
    if active is None:
        return False, (f"no cash-application release manifest for this evaluator key: preflight one "
                       f"({FAMILY_MANIFEST_ENV} or ~/.piv/cash_application_manifest.json)")
    if active.get("duplicates"):
        return (False, f"the family manifest holds duplicate records for {active['duplicates']}: it attests "
                       f"nothing about any selector until it is re-preflighted")
    rec = active["records"].get(family_selector_key(ident, variant))
    if rec is None:
        return False, "selector absent from the family manifest"
    if not verify(rec, secret):
        return False, "family manifest record signature does not verify under this key"
    if rec.get("identity") != ident.view():
        return False, "family manifest record was minted under another construction identity"
    current = semantic_components()
    if rec.get("semantic_components") != current:
        was = rec.get("semantic_components") if isinstance(rec.get("semantic_components"), dict) else {}
        drifted = sorted(set(was) ^ set(current) | {k for k in current if k in was and was[k] != current[k]})
        return False, f"family manifest record was minted under other semantic components: {drifted}"
    scope = rec.get("runtime_scope")
    here = runtime_scope()
    if not isinstance(scope, dict) or scope.get("unicode_database") != here["unicode_database"]:
        return (False, f"family manifest record's runtime-dependent evidence was taken under Unicode database "
                       f"{(scope or {}).get('unicode_database')!r}, this runtime reports "
                       f"{here['unicode_database']!r}: re-preflight on this runtime rather than assuming the "
                       f"declared views carry over")
    if rec.get("split_map_digest") != split_map.digest():
        return False, "family manifest record was minted under another frozen split map"
    if rec.get("baseline_catalogue") != BASELINE_CATALOGUE_ID or \
            rec.get("baseline_catalogue_digest") != baseline_catalogue_digest():
        return False, "family manifest record was preflighted against another baseline catalogue"
    if rec.get("gate_set") != gate_set_digest():
        return False, "family manifest record was preflighted against another gate set"
    declared = family_gates()
    gates = rec.get("gates")
    if not isinstance(gates, dict) or set(gates) != set(declared):
        return (False, f"family manifest record was preflighted against another gate set "
                       f"{sorted(gates) if isinstance(gates, dict) else gates!r}")
    failed = [g for g in declared if gates.get(g) is not True]
    if failed:
        return False, f"selector failed preflight gates {failed}"
    if not rec.get("passed"):
        return False, "selector failed preflight gates: the record's gates and its passed flag disagree"
    if rec.get("public_id") != public_id:
        return False, "family manifest public id differs from the minted world"
    if content_digest is not None and rec.get("public_content_digest") != content_digest:
        return False, "family manifest public-content digest differs from the minted world"
    return True, "cash-application family manifest"


__all__ = [
    "FAMILY_MANIFEST_SCHEMA", "FAMILY_PREFLIGHT_CONTRACT", "FAMILY_MANIFEST_ENV",
    "BASELINE_CATALOGUE_ID", "FamilyManifestError",
    "GATE_GROUPS", "FAMILY_GATES", "family_gates", "gate_set_digest",
    "baseline_catalogue_view", "baseline_catalogue_digest",
    "semantic_components", "runtime_scope", "runtime_scope_key",
    "REQUIRED_RECORD_FIELDS", "public_content_digest", "parent_digest", "family_selector_key",
    "record", "sign", "verify", "manifest_path", "write", "load_active", "admit",
]
