"""Phase D: the FROZEN DEVELOPMENT POPULATION, and the selector that serves it.

Round 16, decision 5 lists what must happen before any model call, in order:

    Freeze the generator, profile, catalogue, admission contract and runtime.
    Predeclare 96 development parent groups, 32 per mechanism stratum, and
    retain their complete minting census. Complete offline validation and
    signed-manifest serving checks.

This module is the first two of those three and the door the third one walks
through. `tests/preflight_cash_population.py` runs them; nothing here calls a
model, reads a score or looks at an outcome, and nothing here may.

THE FREEZE IS TWO LISTS, NOT ONE. Some of what decision 5 freezes is a
declaration — a version number, a profile bound, a gate name — and can be
pinned as a literal that a suite compares against the live modules, so that a
change fails loudly instead of moving the population underneath a census.
Some of it is RUNTIME-SCOPED: the baseline catalogue's digest binds compiled
predicate bytecode, and `cash_manifest.runtime_scope()` binds the Unicode
database and the native runtime, so a literal pin would fail on the next
interpreter and say "the catalogue changed" when nothing did. `cash_gate`
already says this of the catalogue digest in as many words. So
`DECLARED_FREEZE` holds what can be pinned, `runtime_freeze()` records what
can only be recorded, and `freeze_record()` publishes both under one digest
with the distinction visible rather than averaged away.

THE POPULATION IS A DECLARATION, NOT A DRAW. `development_identities()`
returns the same 96 construction identities on every machine, in a fixed
order, derived from the frozen split map: the development families of each
mechanism stratum, taking `GROUPS_PER_STRATUM` company-month indices each.
There is no sampling here and no secret here — the secret enters at
`parent_seed`, one layer down, and decides what each identity DRAWS, never
which identities exist. A population whose membership depended on the secret
could not be predeclared, which is the whole point of predeclaring it.

WHY THE ROSTER IS ALSO THE DOOR. `parse_selector` admits a selector only if
it names a declared member of a declared population. That single rule is what
keeps the evaluation split closed: `ar-coldharbour`, `cr-oysterbank` and
`fc-harrowfield` are sealed into `evaluation` by `cash_split.SPLIT_MAP`, no
released population declares them, and so no selector spells them. It is not
a separate prohibition that could be forgotten — it is the absence of a
roster entry, and adding one would be an edit to this file with a split
assignment visible on the same screen.

The selector itself is EVALUATOR-SIDE and carries private tokens (the
population, the template family, the company-month index). It never reaches
an agent: `load_environment` puts `inputs.task_id` — the keyed public id
minted by `cash_construct.public_task_stem` — in the dataset row, the prompt
and every tool reply, exactly as the bank family's selectors do.
"""

from __future__ import annotations

from ..candidate.canonical import canonical_bytes, domain_digest
from . import cash_application as CA
from . import cash_construct as CC
from . import cash_gate as G
from . import cash_manifest as FM
from .cash_identity import (
    BOUNDED_V1,
    FAMILY,
    FAMILY_GENERATOR_VERSION,
    MAX_LAYOUT_ATTEMPTS,
    MECHANISMS,
    VARIANTS,
    ConstructionIdentity,
    GenerationProfile,
    identity_leaks,
    parent_seed,
)
from .cash_split import SPLIT_MAP, SPLIT_MAP_SCHEMA, STRUCTURE_SCHEMA, SplitMap, structure_digest

#: This module's own schema: the shape of `freeze_record()` and of the
#: population declaration below.
POPULATION_SCHEMA = 1

_FREEZE_DOMAIN = b"piv:cash-application-freeze:v1\0"


class PopulationError(ValueError):
    """The declared population is not what it declares itself to be."""


class SelectorError(ValueError):
    """The selector names nothing in a released population."""


class ServingRefused(RuntimeError):
    """A declared member could not be served. Always names its reason, and
    none of the reasons says anything about the world."""


# --------------------------------------------------------------------------
# the freeze
# --------------------------------------------------------------------------

#: WHAT WAS FROZEN, as literals. Every value here is compared against the
#: live modules by `freeze_problems()`, which `tests/test_cash_population.py`
#: runs: a version bump, a profile bound, a gate added to a group, a family
#: moved between splits or a change in the binding/diagnostic baseline split
#: moves one of these and fails the suite. That is the point — the census
#: published under `reviews/` is a census OF THIS, and a generator that
#: quietly moved would make the record describe a population that no longer
#: exists.
#:
#: The three digests are the three that are NOT runtime-scoped:
#: `GenerationProfile.digest()` is over the declared bounds,
#: `gate_set_digest()` over gate names, their groups and the preflight
#: contract version, and `SplitMap.digest()` over the sealed assignments.
#: None of them binds compiled code, so all three are the same on every
#: interpreter. The baseline catalogue's digest is not here for exactly the
#: opposite reason; it is in `runtime_freeze()`.
#:
#: ROUND 17, DECISION 4 — THIS DECLARATION MOVED, AND THE 2026-09-13 RECORD
#: DID NOT. `gate_version` is now 2, `family_preflight_contract` 2 and
#: `gate_set_digest` `2491e97f97b48cee`, because the admission rule
#: `cumulative_reversal_bounded` was corrected: it no longer caps a credit
#: note at the invoice's OPENING BALANCE, only at the ORIGINAL SALE it
#: reverses. `cash_gate._cumulative_reversal_bounded` carries the accounting
#: and the two false rejections that measured it.
#:
#: The published census under
#: `reviews/cash_application_development_population_2026-09-13/` declares
#: `gate_version` 1, `family_preflight_contract` 1 and gate set
#: `6b246422badd05a6`. It is therefore NO LONGER a census of this generator,
#: and it is deliberately left untouched: it is the historical artifact of
#: the superseded rule, and it records which groups that rule refused.
#: Admission under contract 2 is strictly wider, so the old population's
#: groups remain admissible — but its REFUSALS do not stand, and its
#: acceptance ordinals were drawn against a rule that no longer applies.
#:
#: The replacement population REQUIRED by that finding is
#: `cash-application-development-2`, declared below and minted, censused,
#: validated and served under these values. Its record is
#: `reviews/cash_application_development_population_2026-09-13_replacement/`.
DECLARED_FREEZE: dict = {
    # The population's own NAME is frozen, as a literal rather than as
    # `DEVELOPMENT_POPULATION` — a declaration that read the constant it is
    # meant to pin would agree with every future value of it. Round 17,
    # decision 4 is the reason the key exists: the identifier moved, and the
    # freeze must be the thing that notices it moving again.
    "development_population": "cash-application-development-2",
    "superseded_populations": ("cash-application-development-1",),
    "family": "cash_application",
    "family_generator_version": 1,
    "construction_version": 1,
    "template_version": 1,
    "gate_version": 2,
    "profile": "bounded-v1",
    "profile_digest": "310e96729061410467f0e4285976743f",
    "baseline_catalogue": "cash_application_baselines/1",
    "binding_baselines": 9,
    "diagnostic_baselines": 1,
    "family_manifest_schema": 1,
    "family_preflight_contract": 2,
    "gate_count": 31,
    "gate_set_digest": "2491e97f97b48cee",
    "split_map_schema": 1,
    "split_map_digest": "c41f5d150aec53ccce514f7123206ac5",
    "structure_schema": 1,
    "max_layout_attempts": 64,
    "max_baseline_readings": 256,
    "population_schema": 1,
}


def live_freeze(split_map: SplitMap = SPLIT_MAP) -> dict:
    """The same keys, read from the live modules rather than declared."""
    roles = FM.declared_role_counts()
    return {
        "development_population": DEVELOPMENT_POPULATION,
        "superseded_populations": tuple(sorted(SUPERSEDED_POPULATIONS)),
        "family": FAMILY,
        "family_generator_version": FAMILY_GENERATOR_VERSION,
        "construction_version": CC.CONSTRUCTION_VERSION,
        "template_version": CC.TEMPLATE_VERSION,
        "gate_version": G.GATE_VERSION,
        "profile": BOUNDED_V1.name,
        "profile_digest": BOUNDED_V1.digest(),
        "baseline_catalogue": FM.BASELINE_CATALOGUE_ID,
        "binding_baselines": roles.get("binding", 0),
        "diagnostic_baselines": roles.get("diagnostic", 0),
        "family_manifest_schema": FM.FAMILY_MANIFEST_SCHEMA,
        "family_preflight_contract": FM.FAMILY_PREFLIGHT_CONTRACT,
        "gate_count": len(FM.family_gates()),
        "gate_set_digest": FM.gate_set_digest(),
        "split_map_schema": SPLIT_MAP_SCHEMA,
        "split_map_digest": split_map.digest(),
        "structure_schema": STRUCTURE_SCHEMA,
        "max_layout_attempts": MAX_LAYOUT_ATTEMPTS,
        "max_baseline_readings": CA.MAX_BASELINE_READINGS,
        "population_schema": POPULATION_SCHEMA,
    }


def freeze_problems(split_map: SplitMap = SPLIT_MAP) -> list:
    """Every declared value that no longer matches the live module.

    Both directions: a key declared and gone, a key live and undeclared, and
    a key whose value moved. An undeclared key is as much a freeze failure as
    a moved one, because it is a thing the record does not say was frozen.
    """
    live = live_freeze(split_map)
    problems = []
    for key in sorted(set(DECLARED_FREEZE) | set(live)):
        if key not in DECLARED_FREEZE:
            problems.append(f"{key} is live at {live[key]!r} and is not declared frozen")
        elif key not in live:
            problems.append(f"{key} is declared frozen at {DECLARED_FREEZE[key]!r} and no longer exists")
        elif DECLARED_FREEZE[key] != live[key]:
            problems.append(f"{key} was frozen at {DECLARED_FREEZE[key]!r} and is now {live[key]!r}")
    return problems


def runtime_freeze() -> dict:
    """What can only be RECORDED: the parts of the freeze whose value is a
    function of the interpreter that computed it.

    The baseline catalogue's digest binds compiled predicate bytecode; the
    semantic components bind the shipped parser's own source digest; the
    runtime scope names the Unicode database and the native runtime. A record
    signed under one runtime and read under another cannot tell a recompile
    from a change — which is why `cash_manifest.admit` re-reads all three at
    the serving door rather than trusting the record's copy, and why they are
    recorded here rather than pinned above.
    """
    return {
        "baseline_catalogue_digest": FM.baseline_catalogue_digest(),
        "semantic_components": FM.semantic_components(),
        "runtime_scope": FM.runtime_scope(),
        "census_components": G.component_versions(),
    }


def freeze_record(split_map: SplitMap = SPLIT_MAP) -> dict:
    """The whole freeze, declared part and runtime part, under one digest.

    `digest` covers BOTH parts: it answers "was this census taken under the
    same everything?", which is the question a later reader of the published
    record actually has. `freeze_problems()` answers the narrower "did a
    declaration move?", which is the one a suite can enforce.
    """
    body = {
        "schema": POPULATION_SCHEMA,
        "declared": dict(DECLARED_FREEZE),
        "runtime_scoped": runtime_freeze(),
        "declared_matches_live": not freeze_problems(split_map),
    }
    body["digest"] = domain_digest(_FREEZE_DOMAIN, canonical_bytes(body))[:32]
    return body


def freeze_digest(split_map: SplitMap = SPLIT_MAP) -> str:
    return freeze_record(split_map)["digest"]


# --------------------------------------------------------------------------
# the declared populations
# --------------------------------------------------------------------------

#: The development population predeclared by decision 5. The name is part of
#: the construction identity, so a later evaluation batch over the same
#: templates and the same company-month indices is a DIFFERENT world — which
#: is what stops a predeclared census from being quietly reused.
#:
#: ROUND 17, DECISION 4 MOVED THIS NAME, AND THAT IS THE POINT. The
#: population minted on 2026-09-13 was selected under an admission rule that
#: additionally capped a credit note at the invoice's opening balance. The
#: cap was wrong accounting, so passing it could not establish conformity to
#: the intended specification — and the finding's instruction is not "re-run
#: the same population", it is "declare a replacement population". Because
#: the name enters `parent_seed` through the construction identity, a new
#: name is a new DRAW: `cash-application-development-2` is 96 different
#: company-months over the same 96 declared (family, index) slots, selected
#: under contract 2 from the first attempt onward. A re-mint under the old
#: name would have inherited attempt ordinals that the corrected rule no
#: longer produces.
DEVELOPMENT_POPULATION = "cash-application-development-2"

#: The populations that WERE released and no longer are, with the reason. A
#: name in here is not in `RELEASED_POPULATIONS`, so `parse_selector` refuses
#: it and nothing can be served under it — which is the honest state for a
#: population whose selection rule has been found wrong. Its published record
#: is preserved; the record is history, not a roster.
#:
#: This is a declaration, not a deletion: a reader who finds
#: `cash-application-development-1` in the 2026-09-13 census can see here,
#: in source, why no selector spells it any more.
SUPERSEDED_POPULATIONS: dict = {
    "cash-application-development-1": {
        "split": "development",
        "superseded_by": DEVELOPMENT_POPULATION,
        "on": "2026-09-13",
        "record": "reviews/cash_application_development_population_2026-09-13/",
        "reason": ("minted under family preflight contract 1, whose "
                   "`cumulative_reversal_bounded` additionally capped a credit note at the "
                   "invoice's opening balance. Round 17, decision 4 found that cap to be an "
                   "incorrect additional accounting restriction; passing it cannot establish "
                   "conformity to the intended specification."),
    },
}

#: 32 parent groups per mechanism stratum; 96 in all. Decision 5's number,
#: not a tunable.
GROUPS_PER_STRATUM = 32

#: population -> the split it draws from. One entry today. The evaluation
#: split has no entry and this phase does not add one: "Keep the evaluation
#: split unopened."
#:
#: The superseded population is NOT here. Leaving it released would have kept
#: its selectors spellable, and a selector that parses is a claim that the
#: thing it names may be served.
RELEASED_POPULATIONS: dict = {DEVELOPMENT_POPULATION: "development"}


def stratum_families(split: str, split_map: SplitMap = SPLIT_MAP) -> dict:
    """mechanism -> the template families sealed into `split`, in the map's
    canonical family order.

    Read from the frozen map, never restated: a family's split is inherited
    by every descendant, and a population that listed its own families could
    disagree with the seal.
    """
    return {mechanism: tuple(name for name, _m, s in split_map.stratum(mechanism) if s == split)
            for mechanism in MECHANISMS}


def roster(population: str, split_map: SplitMap = SPLIT_MAP) -> tuple:
    """The declared `(template_family, company_month_index)` members of
    `population`, in a fixed order: stratum by stratum in `MECHANISMS` order,
    and within a stratum by company-month index, round-robin over the
    stratum's families.

    Round-robin rather than "the first family takes them all" so that the
    declaration keeps its shape if a later phase seals a second development
    family into a stratum: the 32 groups would then be 16 and 16 rather than
    32 and 0, and the order of the first 16 would not move.
    """
    split = RELEASED_POPULATIONS.get(population)
    if split is None:
        raise PopulationError(f"{population!r} is not a released cash-application population "
                              f"{sorted(RELEASED_POPULATIONS)}")
    members = []
    for mechanism, families in stratum_families(split, split_map).items():
        if not families:
            raise PopulationError(f"the {split!r} split has no {mechanism!r} template family; the frozen map "
                                  f"assigns {split_map.counts()[mechanism]}")
        for position in range(GROUPS_PER_STRATUM):
            family = families[position % len(families)]
            members.append((family, position // len(families)))
    return tuple(members)


def identities_of(population: str, profile: GenerationProfile = BOUNDED_V1,
                  split_map: SplitMap = SPLIT_MAP) -> tuple:
    """The population's construction identities, in the roster's order.

    Each one takes its split FROM the map through `cash_construct.identity_of`
    — there is no argument here that could disagree with the seal.
    """
    if profile.digest() != BOUNDED_V1.digest():
        raise PopulationError(f"the released populations are declared under {BOUNDED_V1.name!r}; a profile "
                              f"with another digest is another population and needs its own declaration")
    return tuple(CC.identity_of(population, family, index, profile)
                 for family, index in roster(population, split_map))


def development_identities(profile: GenerationProfile = BOUNDED_V1,
                           split_map: SplitMap = SPLIT_MAP) -> tuple:
    """Decision 5's 96 predeclared development parent groups."""
    return identities_of(DEVELOPMENT_POPULATION, profile, split_map)


def population_problems(population: str, split_map: SplitMap = SPLIT_MAP) -> list:
    """Everything the declaration claims about itself, checked.

    Cheap, and it is the check that would have caught the mistake worth
    catching: a population that silently drew an evaluation family, or 31 of
    one stratum and 33 of another, would still mint, still validate and still
    publish a census — of the wrong thing.
    """
    problems = []
    split = RELEASED_POPULATIONS.get(population)
    if split is None:
        return [f"{population!r} is not a released population"]
    try:
        identities = identities_of(population, split_map=split_map)
    except PopulationError as exc:
        return [str(exc)]
    if len(identities) != GROUPS_PER_STRATUM * len(MECHANISMS):
        problems.append(f"the population declares {len(identities)} groups, not "
                        f"{GROUPS_PER_STRATUM * len(MECHANISMS)}")
    per_mechanism: dict = {}
    for ident in identities:
        mechanism = CC.shape_of(ident.template_family).mechanism
        per_mechanism[mechanism] = per_mechanism.get(mechanism, 0) + 1
        if ident.split != split:
            problems.append(f"{ident.label()} is in split {ident.split!r}, not the population's {split!r}")
        if split_map.split_of(ident.template_family) != split:
            problems.append(f"{ident.template_family} is sealed into "
                            f"{split_map.split_of(ident.template_family)!r} and the population draws {split!r}")
    for mechanism in MECHANISMS:
        if per_mechanism.get(mechanism, 0) != GROUPS_PER_STRATUM:
            problems.append(f"the {mechanism!r} stratum has {per_mechanism.get(mechanism, 0)} groups, "
                            f"not {GROUPS_PER_STRATUM}")
    labels = [i.label() for i in identities]
    digests = [i.digest() for i in identities]
    for what, values in (("label", labels), ("identity digest", digests)):
        repeated = sorted({v for v in values if values.count(v) > 1})
        if repeated:
            problems.append(f"the population repeats the {what} {repeated[:4]}")
    return problems


# --------------------------------------------------------------------------
# the selector
# --------------------------------------------------------------------------

#: The first field of a cash-application selector. Deliberately the family
#: name: `mint.NAMESPACES` holds the bank family's namespaces and none of
#: them is this, so `load_environment` can dispatch on the prefix alone
#: without either family's selector space growing into the other's.
SELECTOR_PREFIX = FAMILY

#: `cash_application:<population>:<template_family>:<company_month_index>:<variant>`
SELECTOR_FIELDS = 5


def selector_of(ident: ConstructionIdentity, variant: str) -> str:
    """The evaluator-side selector for one variant of one declared group.

    The SPLIT is not in it. A selector that restated the split could name a
    family under the wrong one, and `admit` would then be comparing a record
    against a claim rather than against the seal; the split is read from the
    map by `identity_of` on the way back.
    """
    if variant not in VARIANTS:
        raise SelectorError(f"variant is {variant!r}, not one of {list(VARIANTS)}")
    return (f"{SELECTOR_PREFIX}:{ident.population}:{ident.template_family}:"
            f"{ident.company_month_index}:{variant}")


def parse_selector(task_id: str, profile: GenerationProfile = BOUNDED_V1,
                   split_map: SplitMap = SPLIT_MAP) -> tuple:
    """`(identity, variant)` for a selector naming a DECLARED member of a
    RELEASED population, or `SelectorError`.

    Strict on every field, and strict in the same way `load_environment` is
    strict about the bank family's indices: ASCII decimal only, so that two
    spellings of one index cannot map to one world through `int()`; the
    member must be in the roster, so an index past the declared 32 is refused
    rather than minted; and the population must be released, which is what
    keeps the evaluation split — declared in no population — unspellable.
    """
    if not isinstance(task_id, str):
        raise SelectorError(f"unknown task {task_id!r}")
    parts = task_id.split(":")
    if len(parts) != SELECTOR_FIELDS or parts[0] != SELECTOR_PREFIX:
        raise SelectorError(f"unknown task {task_id!r}")
    _prefix, population, family, index, variant = parts
    if population not in RELEASED_POPULATIONS:
        raise SelectorError(f"unknown task {task_id!r}: {population!r} is not a released cash-application "
                            f"population")
    if variant not in VARIANTS:
        raise SelectorError(f"unknown task {task_id!r}: variant is not one of {list(VARIANTS)}")
    if not index or not index.isascii() or not index.isdigit() or len(index) > 6:
        raise SelectorError(f"unknown task {task_id!r}: the company-month index is ASCII decimal")
    member = (family, int(index))
    if member not in roster(population, split_map):
        raise SelectorError(f"unknown task {task_id!r}: {family}/{int(index)} is not a declared member of "
                            f"{population!r}")
    return CC.identity_of(population, family, int(index), profile), variant


# --------------------------------------------------------------------------
# serving
# --------------------------------------------------------------------------

def content_digest_of(member) -> str:
    """The public-content digest a family manifest record binds: exactly what
    the model is shown, and nothing else."""
    return FM.public_content_digest(member.public_files, member.task.prompt)


def serving_surfaces(variant: str, member) -> dict:
    """Every surface the agent can reach, named, for the leakage audit.

    The same set `cash_gate._no_evaluator_provenance_leak` builds, spelled
    here as well rather than reached into, because the serving door must
    audit whether or not the gate ran: a world whose private provenance
    reached a public byte would otherwise be caught only by a gate that a
    future refactor could move.
    """
    surfaces = {f"{variant}/{name}": text for name, text in member.public_files.items()}
    surfaces[f"{variant}/prompt"] = member.task.prompt
    surfaces[f"{variant}/task_id"] = member.task.id
    surfaces[f"{variant}/world_id"] = member.world.id
    return surfaces


def minted_member(ident: ConstructionIdentity, variant: str, secret: bytes,
                  profile: GenerationProfile = BOUNDED_V1):
    """`(minted group, the variant)` for one declared member, reminted.

    Deterministic in the identity, the profile and the secret, so the world
    served today is the world the census was taken over — `mint_group`'s own
    docstring is the rule, and this is the path that has to obey it.
    """
    try:
        group = G.mint_group(ident, profile, secret)
    except CC.ConstructionRefused as exc:
        raise ServingRefused(f"the declared group could not be minted: {exc}") from exc
    return group, group.pair.variant(variant)


def admitted_inputs(task_id: str, secret: bytes, profile: GenerationProfile = BOUNDED_V1,
                    split_map: SplitMap = SPLIT_MAP):
    """Selector in, derived contract inputs out — or a typed refusal.

    The whole serving decision for this family, kept here rather than in the
    composition root so that it can be exercised without building an
    environment, and so that the environment's only remaining job is the one
    it shares with every other door: `environment_from_inputs`.

    Three things in order, and the order matters. The selector must name a
    declared member (an undeclared one is refused before the secret is used
    for anything). The reminted world must carry no private construction
    token on a public surface. Only then is the family manifest consulted,
    and it is consulted with the public id and the public-content digest of
    the world THIS process just built — so a record signed for another world,
    another runtime, another gate set or another split map refuses here
    rather than serving something the census does not describe.
    """
    ident, variant = parse_selector(task_id, profile, split_map)
    group, member = minted_member(ident, variant, secret, profile)
    leaks = identity_leaks(serving_surfaces(variant, member), ident, parent_seed(ident, secret))
    if leaks:
        raise ServingRefused("private provenance reached a public surface: " + "; ".join(leaks))
    admitted, why = FM.admit(secret, ident, variant, member.task.id, content_digest_of(member),
                             split_map=split_map)
    if not admitted:
        raise ServingRefused(f"cash-application family manifest: {why}")
    del group
    return member.inputs


def records_for(minted, split_map: SplitMap = SPLIT_MAP) -> list:
    """The unsigned family-manifest records for one minted group: one per
    variant, both carrying the pair's gate results.

    Both or neither, because the pair is the unit of acceptance — decision 3
    rejects both variants when either fails an acceptance condition, and a
    manifest that served the surviving half would be a different rule.
    """
    ident = minted.pair.identity
    gates = {gate: bool(minted.report.gates[gate]) for gate in FM.family_gates()}
    out = []
    for variant in sorted(minted.pair.variants):
        member = minted.pair.variant(variant)
        out.append(FM.record(
            ident, variant,
            public_id=member.task.id,
            content_digest=content_digest_of(member),
            structure_digest=structure_digest(minted.pair.template),
            profile_name=BOUNDED_V1.name,
            attempt=minted.pair.attempt,
            gates=gates,
            split_map=split_map))
    return out


__all__ = [
    "POPULATION_SCHEMA", "PopulationError", "SelectorError", "ServingRefused",
    "DECLARED_FREEZE", "live_freeze", "freeze_problems", "runtime_freeze", "freeze_record", "freeze_digest",
    "DEVELOPMENT_POPULATION", "GROUPS_PER_STRATUM", "RELEASED_POPULATIONS", "SUPERSEDED_POPULATIONS",
    "stratum_families", "roster", "identities_of", "development_identities", "population_problems",
    "SELECTOR_PREFIX", "SELECTOR_FIELDS", "selector_of", "parse_selector",
    "content_digest_of", "serving_surfaces", "minted_member", "admitted_inputs", "records_for",
]
