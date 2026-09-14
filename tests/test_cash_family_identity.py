"""Phase A of the cash-application build: the private construction identity
and the frozen split map (round 16, decision 2).

What has to be true before a single instance is drawn:

  * the family is a SEPARATE versioned implementation — `cash_application`
    generator 1 — with its own seed and substream domains, so moving the bank
    family's `GENERATOR_VERSION` (9) cannot restream it and moving this
    family cannot disturb v9;
  * the identity binds exactly decision 2's eight components, and every one
    of them moves the seed;
  * the seed is keyed under the evaluator secret, through the existing
    provisioning door, and refuses to exist without one;
  * both contrast variants derive from the SAME parent world: a variant
    changes its declared fact, not the random stream;
  * no private selector or seed reaches an agent surface;
  * episode settings — token budgets, turn caps — are not population
    identity, and a different budget generates the same accounting world;
  * the split map is 60/20/20 by structural-template FAMILY, stratified
    across the three mechanisms, frozen before instances, inherited by every
    descendant, and unmoved by key rotation;
  * the canonical structural description strips cosmetic names, absolute
    dates and scale while preserving settlement relationships and ordering,
    and a cross-split structural sibling is refused.

    python tests/test_cash_family_identity.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.graph import cash_identity as CI  # noqa: E402
from beancount_ledger.graph import cash_split as CS  # noqa: E402
from beancount_ledger.graph import mint as MINT  # noqa: E402
from beancount_ledger.graph.cash_identity import (  # noqa: E402
    BOUNDED_V1,
    FAMILY,
    FAMILY_GENERATOR_VERSION,
    MAX_LAYOUT_ATTEMPTS,
    MECHANISMS,
    SPLITS,
    VARIANTS,
    VIEW_KEYS,
    ConstructionIdentity,
    IdentityError,
    identity,
    identity_leaks,
    layout_attempt_stream,
    parent_seed,
    refuse_episode_settings,
    stream,
    variant_fact_stream,
)
from beancount_ledger.graph.cash_split import (  # noqa: E402
    SPLIT_WEIGHTS,
    AdviceLineShape,
    CreditNoteShape,
    InvoiceShape,
    PlantShape,
    ReceiptShape,
    SplitMap,
    SplitMapError,
    StructuralAliasError,
    StructuralTemplate,
    StructureLedger,
    StructureTooAmbiguous,
    TemplateFamily,
    canonical_structure,
    identity_for,
    structure_digest,
)

SECRET = b"cash-application-phase-a-test-secret-0123456789"
OTHER_SECRET = b"a-quite-different-evaluator-secret-9876543210!!"

#: The checked-in freeze of the template-to-split map, in the shape
#: `tests/legacy_freeze.json` uses. `cash_split.FROZEN_ASSIGNMENTS` holds the
#: same rows and the shipped `SPLIT_MAP` is sealed against them; this file is
#: the external evidence, and the battery fails if the two diverge.
FREEZE_PATH = Path(__file__).resolve().parent / "cash_split_freeze.json"


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:30]:
            print(f"      {line}")
    return ok


def an_identity(**changes) -> ConstructionIdentity:
    base = dict(population="dev-96", split="train", template_family="rung_two_continuation",
                template_version=1, company_month_index=0)
    base.update(changes)
    return identity(**base)


def raises(exc, call, *args, **kwargs):
    try:
        call(*args, **kwargs)
    except exc as error:
        return str(error)
    except Exception as error:                                  # noqa: BLE001
        return f"!! {type(error).__name__}: {error}"
    return None


# --------------------------------------------------------------------------
# a separate versioned implementation
# --------------------------------------------------------------------------

def test_the_family_is_a_separate_versioned_implementation():
    problems = []
    if (FAMILY, FAMILY_GENERATOR_VERSION) != ("cash_application", 1):
        problems.append(f"family is {FAMILY!r}/{FAMILY_GENERATOR_VERSION}, not 'cash_application'/1")
    if MINT.GENERATOR_VERSION != 9:
        problems.append(f"the bank family's GENERATOR_VERSION is {MINT.GENERATOR_VERSION}, not 9: "
                        f"decision 2 says preserve it exactly")
    domains = {"family seed": CI._SEED_DOMAIN, "family substream": CI._SUBSTREAM_DOMAIN,
               "bank seed": MINT._SEED_DOMAIN, "bank substream": MINT._SUBSTREAM_DOMAIN}
    if len(set(domains.values())) != len(domains):
        problems.append(f"the seed/substream domains are not disjoint: {domains}")
    for label, domain in domains.items():
        if not domain.endswith(b"\0"):
            problems.append(f"the {label} domain is not null-framed: {domain!r}")

    # The real coupling test: move the BANK family's global number and watch
    # the bank derivations move while the family's stand still. That is the
    # property decision 2 asks for — "reusing those functions unchanged would
    # couple the two populations" — and nothing but this demonstrates it.
    ident = an_identity()
    before_seed = parent_seed(ident, SECRET)
    before_stream = stream(before_seed, "layout")
    bank_before = (MINT.private_seed("train", 3, SECRET), MINT.sub_seed(11, "layout"))
    original = MINT.GENERATOR_VERSION
    try:
        MINT.GENERATOR_VERSION = original + 1
        bank_after = (MINT.private_seed("train", 3, SECRET), MINT.sub_seed(11, "layout"))
        after_seed = parent_seed(ident, SECRET)
        after_stream = stream(after_seed, "layout")
    finally:
        MINT.GENERATOR_VERSION = original
    if bank_before == bank_after:
        problems.append("moving GENERATOR_VERSION did not move the bank family's own derivations: this test "
                        "cannot show the two populations are uncoupled")
    if (before_seed, before_stream) != (after_seed, after_stream):
        problems.append("moving the bank family's GENERATOR_VERSION restreamed the cash-application family: "
                        "it is reusing mint's seed functions rather than its own")
    if parent_seed(ident, SECRET) == MINT.private_seed("train", 0, SECRET):
        problems.append("the family seed collides with a bank seed under the same secret")
    return check("cash_application/1 is a separate versioned implementation: its own seed and substream "
                 "domains, and moving GENERATOR_VERSION 9 leaves every family derivation where it was",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# what the identity binds
# --------------------------------------------------------------------------

def test_the_identity_binds_exactly_decision_twos_eight_components():
    problems = []
    ident = an_identity()
    view = ident.view()
    if tuple(sorted(view)) != VIEW_KEYS:
        problems.append(f"the identity view carries {sorted(view)}, not {list(VIEW_KEYS)}")
    if tuple(sorted(ConstructionIdentity.__dataclass_fields__)) != VIEW_KEYS:
        problems.append(f"the dataclass carries fields {sorted(ConstructionIdentity.__dataclass_fields__)} "
                        f"but the view emits {list(VIEW_KEYS)}: a component that is not in the view cannot "
                        f"reach the seed, so the two must agree")
    for forbidden in ("variant", "attempt", "secret", "rotation_id", "seed"):
        if forbidden in view:
            problems.append(f"the identity binds {forbidden!r}, which is not one of decision 2's components")
    # Every component moves both the name and the seed.
    seed = parent_seed(ident, SECRET)
    moves = {
        "population": an_identity(population="dev-97"),
        "split": an_identity(split="evaluation"),
        "template_family": an_identity(template_family="credit_excess"),
        "template_version": an_identity(template_version=2),
        "company_month_index": an_identity(company_month_index=1),
    }
    for name, other in moves.items():
        if other.digest() == ident.digest():
            problems.append(f"changing {name} did not move the identity digest")
        if parent_seed(other, SECRET) == seed:
            problems.append(f"changing {name} did not move the private seed")
    # The profile enters as its COMPLETE digest, so a bound is a component.
    loose = BOUNDED_V1.__class__(invoices=(8, 20))
    if identity(population="dev-96", split="train", template_family="rung_two_continuation",
                template_version=1, company_month_index=0, profile=loose).digest() == ident.digest():
        problems.append("a profile differing only in a bound produced the same identity: the profile is "
                        "entering by name rather than by its complete digest")
    # Refusals.
    for label, call in (("an unknown split", lambda: an_identity(split="holdout")),
                        ("a negative index", lambda: an_identity(company_month_index=-1)),
                        ("an empty population", lambda: an_identity(population="  "))):
        if raises(IdentityError, call) is None:
            problems.append(f"{label} was accepted as a construction identity")
    if raises(IdentityError, ConstructionIdentity, "p", "train", "f", 1, 0, "d", "other_family", 1) is None:
        problems.append("an identity claiming another family was accepted")
    return check("the construction identity binds exactly family, family-generator version, population, split, "
                 "structural-template family and version, base company-month index and the complete "
                 "generation-profile digest, and every one of them moves the seed",
                 not problems, "\n".join(problems))


def test_the_seed_is_keyed_through_the_existing_provisioning_door():
    problems = []
    ident = an_identity()
    if parent_seed(ident, SECRET) == parent_seed(ident, OTHER_SECRET):
        problems.append("two evaluator secrets produced the same seed: the derivation is not keyed")
    if parent_seed(ident, SECRET) != parent_seed(an_identity(), SECRET):
        problems.append("the seed is not a function of the identity and the secret alone")
    if raises(IdentityError, parent_seed, ident, b"short") is None:
        problems.append("a secret below the minimum width was accepted")
    if raises(IdentityError, parent_seed, ident.view(), SECRET) is None:
        problems.append("a bare dict was accepted where a ConstructionIdentity is required")
    # The no-secret refusal, WITHOUT reading the evaluator's real secret: the
    # provisioning door is stubbed, never called for its value.
    real = CI.evaluator_secret
    try:
        CI.evaluator_secret = lambda: None
        message = raises(IdentityError, parent_seed, ident)
    finally:
        CI.evaluator_secret = real
    if message is None or "keyed" not in message:
        problems.append(f"an unkeyed construction was not refused by name: {message}")
    if CI.evaluator_secret is not MINT.evaluator_secret:
        problems.append("the family does not read the secret through mint.evaluator_secret: decision 2 says "
                        "reuse the evaluator-secret provisioning, not reimplement it")
    if parent_seed(ident, SECRET).bit_length() > 128:
        problems.append("the private seed is wider than 128 bits")
    return check("the private seed is HMAC-keyed under the evaluator secret read through the one provisioning "
                 "door, refuses a missing or short secret, and has no unkeyed fallback",
                 not problems, "\n".join(problems))


def test_substreams_are_purpose_separated_and_never_ambient():
    problems = []
    seed = parent_seed(an_identity(), SECRET)
    purposes = ("parties", "chart", "opening_register", "statement_rows", "advice_wording")
    values = {p: stream(seed, p) for p in purposes}
    if len(set(values.values())) != len(values):
        problems.append(f"two purposes share a substream: {values}")
    # Adding a purpose never reshuffles another.
    if {p: stream(seed, p) for p in purposes + ("a_sixth_purpose",)} | values != \
            {p: stream(seed, p) for p in purposes + ("a_sixth_purpose",)}:
        problems.append("adding a purpose moved an existing substream")
    if raises(IdentityError, stream, seed, "") is None:
        problems.append("an empty purpose was accepted")
    if raises(IdentityError, stream, -1, "parties") is None:
        problems.append("a negative seed was accepted")
    # Stable across processes and PYTHONHASHSEED: a substream built on
    # Python's salted hash() would not be, and the whole population would
    # depend on the interpreter's start-up entropy.
    script = ("import sys; sys.path.insert(0, r'%s');"
              "from beancount_ledger.graph.cash_identity import stream;"
              "print(stream(%d, 'parties'), stream(%d, 'chart'))" % (ROOT, seed, seed))
    seen = set()
    for salt in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=salt)
        out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env)
        seen.add(out.stdout.strip())
        if out.returncode != 0:
            problems.append(f"PYTHONHASHSEED={salt}: {out.stderr.strip()[:200]}")
    if len(seen) != 1:
        problems.append(f"the substreams are ambient: PYTHONHASHSEED changed them ({seen})")
    if seen and str(values["parties"]) not in next(iter(seen)):
        problems.append("a subprocess derived a different substream from the same seed")
    return check("substreams are domain-separated by purpose, adding one never reshuffles another, and every "
                 "value is stable across processes and PYTHONHASHSEED",
                 not problems, "\n".join(problems))


def test_both_contrast_variants_derive_from_the_same_parent_world():
    problems = []
    ident = an_identity()
    seed = parent_seed(ident, SECRET)
    shared = {p: stream(seed, p) for p in ("parties", "chart", "opening_register", "layout_attempt/0")}
    # There is nothing to vary: the identity has no variant axis, so the two
    # variants cannot have different parent seeds.
    if "variant" in ident.view():
        problems.append("the identity carries a variant: the pair would not share a parent world")
    for variant in VARIANTS:
        if parent_seed(ident, SECRET) != seed:
            problems.append(f"variant {variant} derived a different parent seed")
        if {p: stream(seed, p) for p in shared} != shared:
            problems.append(f"variant {variant} moved a shared substream")
    a = variant_fact_stream(seed, "a", "declared_amount")
    b = variant_fact_stream(seed, "b", "declared_amount")
    if a == b:
        problems.append("the two variants' declared-fact streams are identical: the variant changes nothing")
    if a in shared.values() or b in shared.values():
        problems.append("a declared-fact stream collides with a shared stream")
    if variant_fact_stream(seed, "a", "x") == variant_fact_stream(seed, "a", "y"):
        problems.append("the declared-fact stream ignores its purpose")
    if raises(IdentityError, variant_fact_stream, seed, "c", "x") is None:
        problems.append("an unknown variant was accepted")
    return check("both contrast variants derive from the SAME parent world — the identity has no variant axis, "
                 "every shared substream is byte-identical across the pair, and only the declared fact has a "
                 "stream of its own", not problems, "\n".join(problems))


def test_layout_attempts_derive_from_the_identity_and_are_bounded():
    problems = []
    seed = parent_seed(an_identity(), SECRET)
    if MAX_LAYOUT_ATTEMPTS != 64:
        problems.append(f"MAX_LAYOUT_ATTEMPTS is {MAX_LAYOUT_ATTEMPTS}, not the 64 decision 3 sets")
    attempts = [layout_attempt_stream(seed, i) for i in range(MAX_LAYOUT_ATTEMPTS)]
    if len(set(attempts)) != len(attempts):
        problems.append("two layout attempts share a substream")
    if layout_attempt_stream(seed, 0) == layout_attempt_stream(parent_seed(an_identity(company_month_index=1),
                                                                          SECRET), 0):
        problems.append("the layout attempt does not depend on the identity")
    for bad in (-1, MAX_LAYOUT_ATTEMPTS, "0"):
        if raises(IdentityError, layout_attempt_stream, seed, bad) is None:
            problems.append(f"attempt {bad!r} was accepted")
    return check(f"the {MAX_LAYOUT_ATTEMPTS} bounded layout attempts derive from the parent identity, are "
                 f"pairwise distinct, and refuse an out-of-range ordinal",
                 not problems, "\n".join(problems))


def test_no_private_selector_or_seed_reaches_an_agent_surface():
    problems = []
    ident = an_identity()
    seed = parent_seed(ident, SECRET)
    clean = {
        "ledger.beancount": '2026-04-10 * "Gannet Rigging Inc" "Customer receipt"\n',
        "open_items.csv": "invoice_id,customer\nSI-3100,Gannet Rigging Inc\n",
        "prompt": "Correct the ledger and deliver the application register.",
        "task_id": "task-8a6f2c1d",
    }
    found = identity_leaks(clean, ident, seed)
    if found:
        problems.append(f"a clean workspace was reported as leaking: {found}")
    leaks = {
        "the decimal seed": str(seed),
        "the hex seed": f"{seed:x}",
        "the identity digest": ident.digest(),
        "the selector label": ident.label(),
        "the population": ident.population,
        "the template family": ident.template_family,
        "the profile digest": ident.profile_digest,
    }
    for label, token in leaks.items():
        surfaces = dict(clean, **{"notes.md": f"generated from {token} on 2026-04-30"})
        if not identity_leaks(surfaces, ident, seed):
            problems.append(f"{label} on a public surface was not caught")
    if not identity_leaks({"prompt": clean["prompt"] + f" cm-{ident.company_month_index}"}, ident, seed):
        problems.append("an interpolated company-month selector was not caught")

    # THE SHAPE THE CODEBASE ACTUALLY SERVES. A check exercised only over
    # `str` proves the rule over the representation that happens to work:
    # `derive_contract(...).public_files` is (name, BYTES) pairs, and that is
    # what reaches the agent's workspace. So the same claim is made again over
    # a real projection through the production door.
    from beancount_ledger.graph.derive import derive_contract
    from beancount_ledger.graph.worlds import REGISTRY
    world, task = REGISTRY["cash_application_001"]
    shipped = dict(derive_contract(world, task)[1].public_files)
    kinds = sorted({type(v).__name__ for v in shipped.values()})
    if kinds != ["bytes"]:
        problems.append(f"the shipped public projection is {kinds}, not bytes: this probe is no longer "
                        f"exercising the representation the agent is served")
    found = identity_leaks(shipped, ident, seed)
    if found:
        problems.append(f"a real public projection was reported as leaking: {found}")
    target = sorted(shipped)[0]
    for label, token in leaks.items():
        poisoned = dict(shipped)
        poisoned[target] = shipped[target] + f"\n; generated from {token}\n".encode("utf-8")
        if not identity_leaks(poisoned, ident, seed):
            problems.append(f"{label} in the BYTES a public file is actually served as was not caught")
    # And a surface it cannot read is named, not skipped: skipping is how the
    # bytes hole reported "no leaks" about every file it never looked at.
    unreadable = identity_leaks({"ledger.beancount": 17, "open_items.csv": None}, ident, seed)
    if len(unreadable) != 2 or not all("UNCHECKED" in problem for problem in unreadable):
        problems.append(f"surfaces the check cannot read were not refused by name: {unreadable}")
    return check("no private selector or seed reaches the agent's workspace or observations: the literal check "
                 "passes a clean pack and a real bytes projection through derive_contract, catches the seed in "
                 "both bases, the identity digest, the selector label, the population, the template family and "
                 "the profile digest in BOTH str and bytes surfaces, and refuses a surface it cannot read "
                 "rather than skipping it", not problems, "\n".join(problems))


def test_episode_settings_are_not_population_identity():
    problems = []
    for key in CI.EPISODE_SETTING_KEYS:
        if raises(IdentityError, refuse_episode_settings, "a probe", {key: 1}) is None:
            problems.append(f"{key} was accepted into construction material")
    nested = {"record": {"experiment": [{"max_total_completion_tokens": 40_000}]}}
    if raises(IdentityError, refuse_episode_settings, "a probe", nested) is None:
        problems.append("a nested episode setting was not found")
    if raises(IdentityError, refuse_episode_settings, "a probe", {"invoices": 12}) is not None:
        problems.append("an ordinary construction key was refused as an episode setting")

    # The claim decision 2 actually makes: a different token budget must never
    # generate a different accounting world. Driven through the REAL knob —
    # `episode_contract(max_episode_output_tokens=...)` for the explicit form
    # and the module global `MAX_EPISODE_OUTPUT_TOKENS` for the ambient one,
    # which `load_environment` reads at call time. A probe environment
    # variable nothing reads would recompute a constant three times.
    import beancount_ledger.beancount_ledger as env_mod
    budgets = (8_000, 24_000, 40_000)
    episodes = {budget: env_mod.episode_contract_digest(budget) for budget in budgets}
    if len(set(episodes.values())) != len(episodes):
        problems.append(f"the episode digests did not separate the budgets, so this probe moved nothing: "
                        f"{episodes}")
    for budget, digest in episodes.items():
        if env_mod.episode_contract(budget)["budgets"]["max_episode_output_tokens"] != budget:
            problems.append(f"the episode contract did not take the {budget} ceiling")
    ident = an_identity()
    worlds, ambient = set(), set()
    ceiling = env_mod.MAX_EPISODE_OUTPUT_TOKENS
    try:
        for budget in budgets:
            env_mod.MAX_EPISODE_OUTPUT_TOKENS = budget
            ambient.add(env_mod.MAX_EPISODE_OUTPUT_TOKENS)
            seed = parent_seed(an_identity(), SECRET)
            worlds.add((an_identity().digest(), seed, stream(seed, "parties"),
                        layout_attempt_stream(seed, 0), variant_fact_stream(seed, "a", "wording")))
    finally:
        env_mod.MAX_EPISODE_OUTPUT_TOKENS = ceiling
    if ambient != set(budgets):
        problems.append(f"the ambient ceiling did not move: {sorted(ambient)}")
    if len(worlds) != 1:
        problems.append(f"a token budget moved the accounting world: {len(worlds)} distinct constructions")
    if env_mod.MAX_EPISODE_OUTPUT_TOKENS != ceiling:
        problems.append("the probe left the episode ceiling moved")
    # And the episode contract itself cannot be smuggled in as material.
    if raises(IdentityError, refuse_episode_settings, "a probe",
              {"episode_contract": env_mod.episode_contract(8_000)}) is None:
        problems.append("an episode contract pasted into construction material was accepted")
    return check("episode settings belong to the experiment record, not to population identity: every budget "
                 "and turn cap is refused inside construction material, and three budgets that really move "
                 "the episode-contract digest — through the contract's own argument and the ambient ceiling "
                 "load_environment reads — leave the identity, the seed and every substream identical",
                 not problems, "\n".join(problems))


def test_the_bounded_v1_profile_is_decision_fours_table():
    problems = []
    p = BOUNDED_V1
    table = {"name": "bounded-v1", "months": 1, "currency": "USD", "customers": (2, 3),
             "invoices": (8, 14), "invoices_raised_in_period": (2, 4), "receipts": (3, 6),
             "credit_notes": (1, 1), "ledger_plants": (2, 2), "max_allocations_per_receipt": 4,
             "max_allocations_per_credit_note": 3, "max_dependency_depth": 3,
             "max_golden_ledger_bytes": 24_000, "max_golden_register_bytes": 8_000,
             "requires_unpaid_in_period_invoice": True, "mechanisms": MECHANISMS}
    for key, want in table.items():
        got = getattr(p, key)
        if got != want:
            problems.append(f"profile.{key} is {got!r}, not decision 4's {want!r}")
    for forbidden in ("missing_authority", "ambiguous_identity", "unsupported_deduction",
                      "hidden_historical_fact", "unexplained_tax_change", "answer_bearing_narration",
                      "document_truncation", "budget_consuming_padding"):
        if forbidden not in p.forbidden_difficulty:
            problems.append(f"the profile does not declare {forbidden} as manufactured difficulty")
    for excluded in ("foreign_exchange", "refunds", "retention_accounting",
                     "cross_customer_application", "multi_period_editing"):
        if excluded not in p.excluded_accounting:
            problems.append(f"the profile does not retain the accounting limit {excluded}")
    if "hard" in p.name:
        problems.append("the profile is called hard: decision 4 says do not call the first profile hard")
    if set(p.view()) != set(p.__dataclass_fields__):
        problems.append("the profile digest is taken over less than the complete profile")
    if p.digest() != BOUNDED_V1.digest():
        problems.append("the profile digest is not stable")
    for change in ({"invoices": (8, 15)}, {"max_dependency_depth": 4}, {"currency": "EUR"},
                   {"requires_both_polarities_per_mechanism": False},
                   {"forbidden_difficulty": p.forbidden_difficulty[:-1]}):
        if p.__class__(**{**p.view(), **change}).digest() == p.digest():
            problems.append(f"changing {list(change)[0]} did not move the profile digest")
    return check("bounded-v1 declares decision 4's table exactly — bounds, the unpaid in-period invoice, both "
                 "polarities per mechanism, the manufactured-difficulty conditions and the retained accounting "
                 "limits — and its digest covers the complete profile",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# the split map
# --------------------------------------------------------------------------

def a_roster(per_stratum: int, prefix: str = "t") -> tuple:
    return tuple(TemplateFamily(f"{prefix}_{mechanism}_{n:02d}", mechanism)
                 for mechanism in MECHANISMS for n in range(per_stratum))


def test_the_split_map_is_sixty_twenty_twenty_within_every_mechanism():
    problems = []
    if dict(SPLIT_WEIGHTS) != {"train": 3, "development": 1, "evaluation": 1}:
        problems.append(f"the weights are {dict(SPLIT_WEIGHTS)}, not 60/20/20 as 3:1:1")
    if tuple(SPLITS) != ("train", "development", "evaluation"):
        problems.append(f"the splits are {SPLITS}")
    exact = SplitMap.seal(a_roster(5))
    for mechanism, counts in exact.counts().items():
        if counts != {"train": 3, "development": 1, "evaluation": 1}:
            problems.append(f"five families in {mechanism} split {counts}, not 3/1/1")
    for per in (1, 2, 7, 11, 32, 97):
        sealed = SplitMap.seal(a_roster(per))
        for mechanism, counts in sealed.counts().items():
            if sum(counts.values()) != per:
                problems.append(f"{mechanism}: {sum(counts.values())} families sealed, not {per}")
            for split, weight in SPLIT_WEIGHTS:
                share = weight * per / 5
                if abs(counts[split] - share) >= 1:
                    problems.append(f"{per} families in {mechanism}: {split} got {counts[split]}, more than "
                                    f"one away from its exact share {share}")
    # Against the checked-in freeze, not against a freshly constructed empty
    # map: pinning the code to itself asserts what the code does.
    if json.loads(FREEZE_PATH.read_text(encoding="utf-8"))["digest"] != CS.SPLIT_MAP.digest():
        problems.append("the shipped split map is no longer the map tests/cash_split_freeze.json froze")
    # Phase B declares the roster: fifteen families, five per stratum, which
    # is the one roster size that apportions to 3/1/1 exactly.
    if len(CS.TEMPLATE_ROSTER) != 15:
        problems.append(f"the roster declares {len(CS.TEMPLATE_ROSTER)} families, not the fifteen phase B seals")
    for mechanism, counts in CS.SPLIT_MAP.counts().items():
        if counts != {"train": 3, "development": 1, "evaluation": 1}:
            problems.append(f"the shipped map splits {mechanism} {counts}, not 3/1/1")
    return check("the split map is 60/20/20 by structural-template family, stratified across the three "
                 "mechanisms, each stratum within one family of its exact share, and the shipped roster of "
                 "fifteen seals to exactly 3/1/1 in every stratum",
                 not problems, "\n".join(problems))


def test_the_split_map_survives_key_rotation_and_descendant_versions():
    problems = []
    sealed = SplitMap.seal(a_roster(7))
    baseline = sealed.digest()
    saved = {k: os.environ.get(k) for k in ("PIV_KEY_ID", "PIV_EVAL_SECRET")}
    try:
        for rotation in ("rotation-one", "rotation-two"):
            os.environ["PIV_KEY_ID"] = rotation
            os.environ["PIV_EVAL_SECRET"] = SECRET.hex() if rotation == "rotation-one" else OTHER_SECRET.hex()
            if SplitMap.seal(a_roster(7)).digest() != baseline:
                problems.append(f"key rotation {rotation} moved the split-map digest")
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    original = CI.FAMILY_GENERATOR_VERSION
    try:
        CI.FAMILY_GENERATOR_VERSION = original + 1
        if SplitMap.seal(a_roster(7)).digest() != baseline:
            problems.append("a descendant generator version moved the split-map digest")
    finally:
        CI.FAMILY_GENERATOR_VERSION = original
    # Descendant TEMPLATE versions inherit, because the key is the family name.
    family = sealed.families()[0]
    template = a_template(family=family)
    splits = {version: identity_for("dev-96", a_template(family=family, version=version), n,
                                    split_map=sealed).split
              for version in (1, 2, 9) for n in (0, 1, 41)}
    if len(set(splits.values())) != 1 or splits[1] != sealed.split_of(family):
        problems.append(f"descendants of {family} did not inherit its split: {splits}")
    if structure_digest(template) is None:
        problems.append("the template has no structure digest")
    return check("the frozen map survives key rotation and descendant versions — no secret, rotation id or "
                 "generator version enters its digest — and every company-month, variant and later template "
                 "version inherits its family's split", not problems, "\n".join(problems))


def test_a_sealed_assignment_is_frozen_for_the_life_of_the_family():
    problems = []
    first = SplitMap.seal(a_roster(4))
    grown = SplitMap.seal(a_roster(4) + a_roster(3, prefix="u"), previous=first)
    for name, _, split in first.assignments:
        if grown.split_of(name) != split:
            problems.append(f"extending the roster moved {name} from {split} to {grown.split_of(name)}")
    if len(grown.assignments) != len(first.assignments) + 9:
        problems.append(f"the extension sealed {len(grown.assignments)} families, not "
                        f"{len(first.assignments) + 9}")
    if first.digest() == grown.digest():
        problems.append("extending the roster did not move the split-map digest: a record minted under the "
                        "old map would keep admitting under the new one")
    dropped = raises(SplitMapError, SplitMap.seal, a_roster(3), first)
    if dropped is None or "never removed" not in dropped:
        problems.append(f"dropping a sealed family was not refused by name: {dropped}")
    restratified = tuple(TemplateFamily(e.name, "credit_residue") for e in a_roster(4))
    if raises(SplitMapError, SplitMap.seal, restratified, first) is None:
        problems.append("moving a sealed family to another mechanism stratum was accepted")
    twice = a_roster(2) + (TemplateFamily(a_roster(2)[0].name, a_roster(2)[0].mechanism),)
    if raises(SplitMapError, SplitMap.seal, twice) is None:
        problems.append("a roster declaring a family twice was accepted")
    if raises(SplitMapError, first.split_of, "never_declared") is None:
        problems.append("a family absent from the frozen map resolved to a split")
    return check("a sealed assignment is frozen for the life of the family: extension carries every prior "
                 "assignment verbatim and moves the map digest, and dropping, re-stratifying or duplicating "
                 "a family is refused by name", not problems, "\n".join(problems))


def test_the_frozen_map_has_a_checked_in_anchor():
    """`seal` is monotone only against a `previous` map, so "frozen for the
    life of the family" needs something checked in to be previous TO.

    Without one, a roster edit that both adds and reorders families silently
    reassigns the old ones and the only alarm is a moved digest after the
    fact. `cash_split.FROZEN_ASSIGNMENTS` is that anchor and
    `tests/cash_split_freeze.json` is its external evidence, in the shape
    `tests/legacy_freeze.json` uses."""
    problems = []
    frozen = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if frozen["map"] != CS.SPLIT_MAP.view():
        problems.append(f"the checked-in freeze and the shipped split map disagree: {frozen['map']} vs "
                        f"{CS.SPLIT_MAP.view()}")
    if frozen["digest"] != CS.SPLIT_MAP.digest():
        problems.append(f"the checked-in freeze pins digest {frozen['digest']} and the shipped map is "
                        f"{CS.SPLIT_MAP.digest()}")
    if SplitMap.from_view(frozen["map"]).assignments != CS.SPLIT_MAP.assignments:
        problems.append("the freeze does not round-trip through SplitMap.from_view")
    if tuple(CS.FROZEN_ASSIGNMENTS) != CS.SPLIT_MAP.assignments:
        problems.append(f"FROZEN_ASSIGNMENTS {CS.FROZEN_ASSIGNMENTS} is not what the shipped map carries: the "
                        f"anchor is not what the seal is anchored to")
    for bad in ({"schema": 2, "weights": frozen["map"]["weights"], "assignments": []},
                {"schema": 1, "weights": [["train", 1], ["development", 1], ["evaluation", 1]],
                 "assignments": []},
                {"schema": 1, "weights": frozen["map"]["weights"], "assignments": [["f", "credit_residue"]]}):
        if raises(SplitMapError, SplitMap.from_view, bad) is None:
            problems.append(f"a freeze declaring {bad['schema']}/{bad['weights']} was adopted unchecked")

    # The property the anchor buys, demonstrated on a roster that has families
    # in it: reordering a roster REASSIGNS without a previous map, and does
    # not with one.
    roster = tuple(TemplateFamily(f"anchor_{n}", "credit_residue") for n in range(5))
    sealed = SplitMap.seal(roster)
    reversed_roster = tuple(reversed(roster))
    if SplitMap.seal(reversed_roster).assignments == sealed.assignments:
        problems.append("reordering this roster did not reassign it even without a previous map, so it does "
                        "not demonstrate what the anchor is for: pick a roster that does")
    carried = SplitMap.seal(reversed_roster, previous=SplitMap.from_view(json.loads(json.dumps(sealed.view()))))
    if carried.assignments != sealed.assignments:
        problems.append(f"a reordered roster sealed against the checked-in map still moved assignments: "
                        f"{carried.assignments} vs {sealed.assignments}")
    # An anchor naming a family the roster no longer declares is refused, not
    # dropped: that is the other way a frozen assignment disappears.
    if raises(SplitMapError, SplitMap.seal, roster[:3], sealed) is None:
        problems.append("a roster that drops an anchored family was accepted")
    return check("the frozen split map has a checked-in anchor: FROZEN_ASSIGNMENTS is what the shipped seal "
                 "carries as `previous`, tests/cash_split_freeze.json pins the same map and digest, a freeze "
                 "under another schema or other weights is refused, and a reordered roster that would be "
                 "reassigned without the anchor keeps every assignment with it",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# the canonical structural description
# --------------------------------------------------------------------------

def a_template(*, family="rung_two_continuation", version=1, mechanism="fallback_continuation",
               scale=Decimal(1), names=("Gannet Rigging Inc", "Shearwater Bay Charters LLC"),
               prefix="SI", days=0, reference=("SI-3104", "SI-3102")) -> StructuralTemplate:
    """One structural template, with every cosmetic axis exposed as an
    argument: the party names, the invoice prefix, a uniform monetary scale
    and a uniform date shift. None of them is structure."""
    def m(value):
        return f"{Decimal(value) * scale:.2f}"

    def d(iso):
        return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()

    def inv(number):
        return f"{prefix}-{number}"

    g, s = names
    ref = tuple(f"{prefix}-{r.split('-')[1]}" for r in reference)
    return StructuralTemplate(
        family=family, version=version, mechanism=mechanism,
        invoices=(
            InvoiceShape(inv(3100), g, d("2026-02-26"), d("2026-03-28"), m(1080), m(300)),
            InvoiceShape(inv(3101), g, d("2026-03-03"), d("2026-04-02"), m(2400), m(2400)),
            InvoiceShape(inv(3102), g, d("2026-03-12"), d("2026-04-11"), m(3600), m(3600)),
            InvoiceShape(inv(3103), s, d("2026-03-18"), d("2026-04-17"), m(2970), m(2970)),
            InvoiceShape(inv(3104), g, d("2026-04-07"), d("2026-05-07"), m(1890), m(0), True),
            InvoiceShape(inv(3105), s, d("2026-04-14"), d("2026-05-14"), m(2970), m(0), True),
        ),
        receipts=(
            ReceiptShape("R1", g, d("2026-04-10"), m(3900), "advice", (),
                         (AdviceLineShape(inv(3101), m(2400)), AdviceLineShape(inv(3102), m(1500)))),
            ReceiptShape("R2", s, d("2026-04-21"), m(2970), "advice", (),
                         (AdviceLineShape(inv(3103), m(2970)),)),
            ReceiptShape("R3", g, d("2026-04-28"), m(2130), "reference", ref, ()),
        ),
        credit_notes=(CreditNoteShape("CN-0412", g, d("2026-04-15"), inv(3102), m(270)),),
        plants=(PlantShape("omission", "R2"), PlantShape("transposition", "R3")),
    )


def test_the_canonical_description_strips_names_dates_and_scale():
    problems = []
    base = structure_digest(a_template())
    same = {
        "renamed parties and invoices": a_template(names=("Alpha Marine Co", "Beta Charters LLC"), prefix="INV"),
        "uniformly rescaled amounts": a_template(scale=Decimal(3)),
        "uniformly shifted dates": a_template(days=365),
        "a different family name": a_template(family="something_else"),
        "a later template version": a_template(version=7),
        "a relabelled mechanism": a_template(mechanism="credit_residue"),
    }
    for label, template in same.items():
        if structure_digest(template) != base:
            problems.append(f"{label} produced a different canonical structure: it is not stripped")
    swapped = a_template(reference=("SI-3102", "SI-3104"))
    if structure_digest(swapped) == base:
        problems.append("reversing the statement reference's PRINTED order did not change the structure: "
                        "ordering is not preserved")
    original = a_template()
    moved = StructuralTemplate(
        original.family, original.version, original.mechanism, original.invoices,
        original.receipts[:2] + (ReceiptShape("R3", original.receipts[2].customer,
                                              original.receipts[2].bank_date, original.receipts[2].amount,
                                              "reference", ("SI-3101", "SI-3102"), ()),),
        original.credit_notes, original.plants)
    if structure_digest(moved) == base:
        problems.append("moving a settlement edge did not change the structure")
    repainted = StructuralTemplate(
        original.family, original.version, original.mechanism, original.invoices, original.receipts,
        original.credit_notes, (PlantShape("omission", "R3"), PlantShape("transposition", "R2")))
    if structure_digest(repainted) == base:
        problems.append("swapping which receipt carries which plant did not change the structure")
    form = canonical_structure(a_template())
    text = repr(form)
    for cosmetic in ("Gannet", "SI-3100", "2026-04-10", "3600.00", "rung_two_continuation",
                     "fallback_continuation"):
        if cosmetic in text:
            problems.append(f"the canonical structure still carries {cosmetic!r}")
    if structure_digest(a_template()) != base:
        problems.append("the canonical structure is not deterministic")
    return check("the canonical structural description strips cosmetic names, absolute dates, scale, the "
                 "family name, the template version and the declared mechanism, and preserves settlement "
                 "relationships, printed order and the plants", not problems, "\n".join(problems))


def test_the_canonical_form_does_not_preserve_subset_sums():
    """The counterexample the module docstring now states, as a measurement.

    Rank encoding preserves the ORDER of amounts and equality between two
    individual amounts. It does not preserve SUMS — so the exact-subset-sum
    coincidence gate (o)'s amount-only branching enumerates is NOT part of the
    canonical form, and the file whose job is saying what "alias" means must
    not claim otherwise. The error runs coarse (the two templates below count
    as aliases), which over-refuses; that is the safe direction, and it is
    pinned here so the docstring describes the code that exists."""
    problems = []

    def money_template(balances, receipt_amount, family="sums_probe"):
        return StructuralTemplate(
            family=family, version=1, mechanism="credit_residue",
            invoices=tuple(InvoiceShape(f"SI-{n}", "Acme Marine Co", "2026-04-01", "2026-05-01", value, value)
                           for n, value in enumerate(balances)),
            receipts=(ReceiptShape("R1", "Acme Marine Co", "2026-04-10", receipt_amount, "bare", (), ()),))

    # 300 IS an exact subset sum of {100, 200, 300}; 999 is not a subset sum of
    # {100, 201, 999} beyond itself — and both canonicalise to the same bytes.
    coincidence = money_template(["100.00", "200.00", "300.00"], "300.00")
    plain = money_template(["100.00", "201.00", "999.00"], "999.00")
    if structure_digest(coincidence) != structure_digest(plain):
        problems.append("the canonical form now separates a subset-sum coincidence from a non-coincidence: "
                        "cash_split.py's docstring says it does NOT, and one of the two is wrong")
    # What rank encoding DOES preserve, and the reason the claim was tempting:
    # equality between two individual amounts.
    equal_pair = money_template(["100.00", "100.00", "300.00"], "300.00")
    if structure_digest(equal_pair) == structure_digest(coincidence):
        problems.append("two equal open balances canonicalised the same as two distinct ones: rank encoding "
                        "does preserve equality between individual amounts, and that is now lost too")
    # And ordering still survives, which is what the rest of the module leans on.
    reordered = money_template(["300.00", "200.00", "100.00"], "300.00")
    if structure_digest(reordered) != structure_digest(coincidence):
        problems.append("reordering the declaration of equal-ranked invoices moved the structure")
    return check("rank-encoded amounts preserve order and individual equality and NOT sums: a receipt equal "
                 "to an exact subset of the open balances canonicalises identically to one that is not, so "
                 "the alias check over-refuses rather than claiming an arithmetic it does not have",
                 not problems, "\n".join(problems))


def test_a_cross_split_structural_sibling_cannot_become_held_out():
    problems = []
    roster = (TemplateFamily("trained_month", "fallback_continuation"),
              TemplateFamily("held_out_month", "fallback_continuation"),
              TemplateFamily("second_trained", "fallback_continuation"))
    sealed = SplitMap.seal(roster)
    splits = {name: sealed.split_of(name) for name in sealed.families()}
    trained = [n for n, s in splits.items() if s == "train"]
    held = [n for n, s in splits.items() if s != "train"]
    if not trained or not held:
        problems.append(f"the probe roster did not straddle two splits: {splits}")
        return check("a cross-split structural sibling is refused", False, "\n".join(problems))
    ledger = StructureLedger(sealed)
    ledger.admit(a_template(family=trained[0]))
    # The same structure again, in the same split: a second company-month or
    # the pair's other variant. Expected, and admitted.
    if raises(StructuralAliasError, ledger.admit, a_template(family=trained[0], version=2)) is not None:
        problems.append("a descendant version of the same family in the same split was refused")
    # A renamed, rescaled, re-dated twin in another split: refused.
    twin = a_template(family=held[0], names=("Quite Other Co", "Another Charters LLC"),
                      prefix="INV", scale=Decimal(7), days=120)
    message = raises(StructuralAliasError, ledger.admit, twin)
    if message is None:
        problems.append("a renamed, rescaled and re-dated sibling became held out")
    elif "renamed or rescaled sibling" not in message:
        problems.append(f"the refusal does not name what it caught: {message}")
    # A genuinely different structure in the held-out split is fine.
    different = a_template(family=held[0], reference=("SI-3102", "SI-3104"))
    if raises(StructuralAliasError, ledger.admit, different) is not None:
        problems.append("a genuinely different structure was refused as an alias")
    if raises(SplitMapError, ledger.admit, a_template(family="undeclared_family")) is None:
        problems.append("a template whose family is not in the frozen map was admitted")
    return check("a candidate whose canonical structure already appears in another split is refused as a "
                 "renamed or rescaled sibling, while the same structure inside one split — a descendant "
                 "version, a second company-month, the pair's other variant — is admitted",
                 not problems, "\n".join(problems))


def test_the_labelling_search_refuses_rather_than_guessing():
    problems = []
    eight = StructuralTemplate(
        family="too_symmetric", version=1, mechanism="advice_residue",
        invoices=tuple(InvoiceShape(f"SI-{n}", f"Customer {n}", "2026-04-01", "2026-05-01", "100.00", "100.00")
                       for n in range(8)))
    message = raises(StructureTooAmbiguous, structure_digest, eight)
    if message is None:
        problems.append("a template whose tied classes exceed the bounded search produced a digest anyway")
    elif "INCOMPLETE" not in message:
        problems.append(f"the refusal does not say the check was incomplete: {message}")
    # Under the bound, the search still resolves ties deterministically.
    four = StructuralTemplate(
        family="symmetric_enough", version=1, mechanism="advice_residue",
        invoices=tuple(InvoiceShape(f"SI-{n}", f"Customer {n}", "2026-04-01", "2026-05-01", "100.00", "100.00")
                       for n in range(4)))
    digests = {structure_digest(four) for _ in range(3)}
    if len(digests) != 1:
        problems.append(f"a tied template canonicalised inconsistently: {digests}")
    shuffled = StructuralTemplate(four.family, four.version, four.mechanism, tuple(reversed(four.invoices)))
    if structure_digest(shuffled) != structure_digest(four):
        problems.append("declaration order changed the canonical structure of a tied template")
    return check("the tie-breaking search is bounded: beyond it the description refuses and says the "
                 "cross-split check was INCOMPLETE, and within it declaration order does not reach the answer",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_family_is_a_separate_versioned_implementation,
    test_the_identity_binds_exactly_decision_twos_eight_components,
    test_the_seed_is_keyed_through_the_existing_provisioning_door,
    test_substreams_are_purpose_separated_and_never_ambient,
    test_both_contrast_variants_derive_from_the_same_parent_world,
    test_layout_attempts_derive_from_the_identity_and_are_bounded,
    test_no_private_selector_or_seed_reaches_an_agent_surface,
    test_episode_settings_are_not_population_identity,
    test_the_bounded_v1_profile_is_decision_fours_table,
    test_the_split_map_is_sixty_twenty_twenty_within_every_mechanism,
    test_the_split_map_survives_key_rotation_and_descendant_versions,
    test_a_sealed_assignment_is_frozen_for_the_life_of_the_family,
    test_the_frozen_map_has_a_checked_in_anchor,
    test_the_canonical_description_strips_names_dates_and_scale,
    test_the_canonical_form_does_not_preserve_subset_sums,
    test_a_cross_split_structural_sibling_cannot_become_held_out,
    test_the_labelling_search_refuses_rather_than_guessing,
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
