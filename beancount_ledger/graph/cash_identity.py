"""The `cash_application` family's PRIVATE construction identity, generator
version 1 — a separate versioned implementation, not a bump of the
bank-reconciliation generator.

Round 16, decision 2 rules this module's shape. The bank family's
`GENERATOR_VERSION` is 9 and must not move; `mint.private_seed` and
`mint.sub_seed` both fold that global number into their material, so reusing
either of them unchanged would couple the two populations — a future bank
generator version would silently restream every cash-application world, and a
cash-application change would have nowhere to go but the bank family's number.
So this module reuses the cryptographic PRIMITIVES (HMAC-SHA-256 under the
evaluator secret, SHA-256 substreams, `canonical_bytes` framing) and the
evaluator-secret PROVISIONING path (`mint.evaluator_secret`, which reads the
environment or `~/.piv/eval_secret` and is the only door to the key), and
nothing else from `mint`.

    seed domain        piv:cash-application:private-seed:v1
    substream domain   piv:cash-application:substream:v1
    identity domain    piv:cash-application:construction-identity:v1

Every one of them is disjoint from `piv:private-seed:v2` and
`piv:substream:v1`, so no material minted here can collide with, or be
confused for, material minted by the bank family under the same secret.

WHAT THE IDENTITY BINDS (decision 2, in its words):

    family and family-generator version; population identifier; split;
    structural-template family and version; base company-month index; and
    the complete generation-profile digest.

Layout attempts and purpose-specific randomness derive from that identity and
from nothing else. The key set is CLOSED — `ConstructionIdentity.view()` emits
exactly those eight keys — so a component that is not on the list cannot enter
a world's construction by accident.

WHAT IT DELIBERATELY DOES NOT BIND:

  * **the variant.** Both contrast variants of a pair derive from the SAME
    parent world, because a variant changes its DECLARED FACT, not the whole
    random stream. There is therefore no variant field here: `parent_seed`
    is the pair's seed, and `variant_fact_stream` is the narrow door for the
    randomness that genuinely belongs to one variant's declared fact (its
    document wording, say) rather than to the company-month.
  * **episode settings.** Token budgets, turn caps, temperature and the
    episode-contract digest belong to the EXPERIMENT RECORD, never to
    population identity: a different budget must never generate a different
    accounting world. `refuse_episode_settings` is the enforcement, and
    `tests/test_cash_family_identity.py` pins it.
  * **the evaluator secret itself, or anything derived from it that a public
    surface could carry.** `identity_leaks` is the literal check; the keyed
    seed is what defeats enumeration.

No private selector or seed may reach the agent's workspace or observations.
`identity_leaks` checks that literally over whatever surfaces it is handed,
the way `mint.literal_provenance_leaks` does for the bank family.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, replace

from ..candidate.canonical import canonical_bytes, domain_digest
from .mint import MIN_SECRET_BYTES, evaluator_secret

FAMILY = "cash_application"
#: The FAMILY generator's version. Independent of `mint.GENERATOR_VERSION`
#: (9, bank reconciliation), which this module never reads.
FAMILY_GENERATOR_VERSION = 1

#: The split map's three names. `development` and `evaluation` are spelled in
#: full rather than as the bank family's `train`/`eval` pair, so a selector
#: from one population can never be typed at the other by accident.
SPLITS = ("train", "development", "evaluation")

#: The three mechanism strata the scope is frozen at (decision 1).
MECHANISMS = ("fallback_continuation", "credit_residue", "advice_residue")

#: A contrast pair's two members. The variant names its DECLARED FACT's
#: polarity; it is not part of the construction identity.
VARIANTS = ("a", "b")

_SEED_DOMAIN = b"piv:cash-application:private-seed:v1\0"
_SUBSTREAM_DOMAIN = b"piv:cash-application:substream:v1\0"
_IDENTITY_DOMAIN = b"piv:cash-application:construction-identity:v1\0"
_PROFILE_DOMAIN = b"piv:cash-application:generation-profile:v1\0"

#: Decision 3: 64 deterministic attempts per parent PAIR, matching the
#: existing bounded-attempt policy. Exhaustion is a named failed group.
MAX_LAYOUT_ATTEMPTS = 64

#: Keys that identify an EPISODE, not a population. Any of them appearing in
#: construction material is a defect, not a configuration.
EPISODE_SETTING_KEYS = (
    "episode_contract",
    "episode_contract_digest",
    "episode_contract_version",
    "max_episode_output_tokens",
    "max_total_completion_tokens",
    "max_turns",
    "per_turn_output_clamp",
    "temperature",
    "token_budget",
    "turn_cap",
)


class IdentityError(ValueError):
    """A construction identity that may not exist."""


# --------------------------------------------------------------------------
# the generation profile
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class GenerationProfile:
    """The bounded composition profile of decision 4, as declared data.

    Named `bounded-v1` and not "hard": decision 4 is explicit that structural
    measurements describe what was generated, and that "harder for model X"
    requires a comparison under fixed measurement conditions rather than an
    invoice count. Every bound below is the reviewer's table verbatim; the
    prose limits (what legitimate complexity is, what manufactured difficulty
    is, which accounting policy stays out of scope) are declared here too,
    because the profile digest binds the COMPLETE profile and a limit that
    lives only in a docstring is not bound by anything.
    """

    name: str = "bounded-v1"
    #: Period and currency.
    months: int = 1
    currency: str = "USD"
    #: Inclusive population bounds, `(low, high)`.
    customers: tuple = (2, 3)
    invoices: tuple = (8, 14)
    invoices_raised_in_period: tuple = (2, 4)
    receipts: tuple = (3, 6)
    credit_notes: tuple = (1, 1)
    ledger_plants: tuple = (2, 2)
    #: Positive allocations per evidence document.
    max_allocations_per_receipt: int = 4
    max_allocations_per_credit_note: int = 3
    #: At most three sequential cash/credit events affecting a later allocation.
    max_dependency_depth: int = 3
    #: Golden artifact envelopes, in bytes.
    max_golden_ledger_bytes: int = 24_000
    max_golden_register_bytes: int = 8_000
    #: Every case must include an in-period invoice left unpaid.
    requires_unpaid_in_period_invoice: bool = True
    #: Each mechanism stratum must contain BOTH the positive condition and
    #: its zero-residue / no-continuation counterpart: "always report a
    #: residue" must not be a winning habit.
    requires_both_polarities_per_mechanism: bool = True
    #: Conditions that must be validated ABSENT. Manufactured difficulty.
    forbidden_difficulty: tuple = (
        "missing_authority",
        "ambiguous_identity",
        "unsupported_deduction",
        "hidden_historical_fact",
        "unexplained_tax_change",
        "answer_bearing_narration",
        "document_truncation",
        "budget_consuming_padding",
    )
    #: Accounting limits retained from the reviewed policy. More steps within
    #: it are acceptable; introducing an unreviewed policy is a scope change.
    excluded_accounting: tuple = (
        "foreign_exchange",
        "refunds",
        "retention_accounting",
        "cross_customer_application",
        "multi_period_editing",
    )
    #: The mechanism strata this profile draws from.
    mechanisms: tuple = MECHANISMS

    def view(self) -> dict:
        """The profile as declared data — the COMPLETE profile, which is what
        the identity's `profile_digest` is a digest of."""
        return {f: getattr(self, f) for f in self.__dataclass_fields__}

    def digest(self) -> str:
        return domain_digest(_PROFILE_DOMAIN, canonical_bytes(self.view()))[:32]


BOUNDED_V1 = GenerationProfile()
PROFILES = {BOUNDED_V1.name: BOUNDED_V1}


# --------------------------------------------------------------------------
# the construction identity
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ConstructionIdentity:
    """The eight components decision 2 binds, and nothing else.

    `population` is the identifier of the population being drawn (the
    reviewer's "population identifier"): a development batch and a later
    evaluation batch of the same template and the same company-month index
    are different populations and therefore different worlds, which is what
    keeps a predeclared census from being quietly reused.

    `company_month_index` is the BASE company-month index: the ordinal of the
    company-month within its template family, before any variant. Both
    variants of a pair share it, because they share the parent world.
    """

    population: str
    split: str
    template_family: str
    template_version: int
    company_month_index: int
    profile_digest: str
    family: str = FAMILY
    family_generator_version: int = FAMILY_GENERATOR_VERSION

    def __post_init__(self):
        if self.family != FAMILY:
            raise IdentityError(f"family is {self.family!r}, not {FAMILY!r}")
        if self.family_generator_version != FAMILY_GENERATOR_VERSION:
            raise IdentityError(f"family generator version is {self.family_generator_version!r}, "
                                f"not {FAMILY_GENERATOR_VERSION}")
        if self.split not in SPLITS:
            raise IdentityError(f"split is {self.split!r}, not one of {list(SPLITS)}")
        for name in ("population", "template_family", "profile_digest"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise IdentityError(f"{name} is {value!r}: a non-empty string with no surrounding space")
        for name in ("template_version", "company_month_index"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise IdentityError(f"{name} is {value!r}: a non-negative int")
        refuse_episode_settings("the construction identity", self.view())

    # -- the closed view ---------------------------------------------------
    def view(self) -> dict:
        """Exactly decision 2's eight components. The key set is CLOSED: a
        test asserts it, so a ninth component cannot enter construction by
        being added to the dataclass and forgotten here."""
        return {
            "family": self.family,
            "family_generator_version": self.family_generator_version,
            "population": self.population,
            "split": self.split,
            "template_family": self.template_family,
            "template_version": self.template_version,
            "company_month_index": self.company_month_index,
            "profile_digest": self.profile_digest,
        }

    def digest(self) -> str:
        """A public-safe 32-hex NAME for this identity. It is not a seed: it
        carries no secret, so it may appear in an evaluator-side record and
        must still never appear on an agent surface (an enumerable selector
        is exactly what the keyed seed defends against)."""
        return domain_digest(_IDENTITY_DOMAIN, canonical_bytes(self.view()))[:32]

    def label(self) -> str:
        """The evaluator-side selector key. Private."""
        return (f"{self.family}/{self.family_generator_version}/{self.population}/{self.split}/"
                f"{self.template_family}/{self.template_version}/{self.company_month_index}")

    def with_(self, **changes) -> "ConstructionIdentity":
        return replace(self, **changes)


VIEW_KEYS = ("company_month_index", "family", "family_generator_version", "population",
             "profile_digest", "split", "template_family", "template_version")


def identity(population: str, split: str, template_family: str, template_version: int,
             company_month_index: int, profile: GenerationProfile = BOUNDED_V1) -> ConstructionIdentity:
    """The constructor callers use: the profile enters as its COMPLETE
    digest, never as a name, so two profiles that share a name and differ in
    a bound are different identities."""
    return ConstructionIdentity(population=population, split=split, template_family=template_family,
                                template_version=int(template_version),
                                company_month_index=int(company_month_index),
                                profile_digest=profile.digest())


# --------------------------------------------------------------------------
# episode settings are not population identity
# --------------------------------------------------------------------------

def refuse_episode_settings(where: str, payload) -> None:
    """Raise when anything that identifies an EPISODE appears in `payload`.

    Decision 2: "Keep episode settings in the experiment record, separate
    from population identity. A different token budget must not silently
    generate a different accounting world." The bank family learned this the
    expensive way — `manifest.versions()` bound the episode contract once,
    and the binding could not hold because `load_environment` admitted
    before it constructed the environment. Here the rule is enforced at
    construction: a budget cannot reach the seed because it cannot reach the
    identity.

    Checked on nested mappings too, since a record is a nested mapping.
    """
    found = sorted(_episode_keys(payload))
    if found:
        raise IdentityError(
            f"{where} carries episode settings {found}: token budgets, turn caps and the episode-contract "
            f"digest identify an EPISODE and belong to the experiment record. A different budget must never "
            f"generate a different accounting world.")


def _episode_keys(payload, seen=None) -> set:
    seen = set() if seen is None else seen
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(key, str) and key in EPISODE_SETTING_KEYS:
                seen.add(key)
            _episode_keys(value, seen)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            _episode_keys(item, seen)
    return seen


# --------------------------------------------------------------------------
# seeds
# --------------------------------------------------------------------------

def parent_seed(ident: ConstructionIdentity, secret: bytes | None = None) -> int:
    """The PAIR's 128-bit private seed: HMAC-SHA-256 under the evaluator's
    secret over the canonically framed construction identity.

    Keyed, for the reason `mint.private_seed` is keyed: an unkeyed digest of
    an enumerable selector has the entropy of the selector, and with the
    generator code and the public id as an equality oracle an agent walks
    the index range and regenerates the answer. The secret is MANDATORY;
    there is no unkeyed fallback on this path.

    `secret` defaults to the evaluator's provisioned secret, through
    `mint.evaluator_secret` — the single provisioning door, reused rather
    than reimplemented. The secret itself is never read, printed, copied or
    hashed anywhere but here.

    Note what is NOT in the material: the variant. Both contrast variants of
    a pair are grown from this one seed.
    """
    if not isinstance(ident, ConstructionIdentity):
        raise IdentityError(f"parent_seed needs a ConstructionIdentity, not {type(ident).__name__}")
    if secret is None:
        secret = evaluator_secret()
    if secret is None:
        raise IdentityError("no evaluator secret: set PIV_EVAL_SECRET (hex) or ~/.piv/eval_secret; "
                            "cash-application worlds are keyed")
    if not isinstance(secret, (bytes, bytearray)) or len(secret) < MIN_SECRET_BYTES:
        raise IdentityError(f"an evaluator secret of at least {MIN_SECRET_BYTES} bytes is required")
    material = _SEED_DOMAIN + canonical_bytes(ident.view())
    return int.from_bytes(hmac.new(bytes(secret), material, hashlib.sha256).digest()[:16], "big")


def stream(seed: int, purpose: str) -> int:
    """The substream seed for one purpose: SHA-256, domain-separated by the
    FAMILY domain and the FAMILY generator version — never Python's salted
    `hash()`, and never `mint.sub_seed`, which folds in the bank family's
    `GENERATOR_VERSION`. Adding a purpose never reshuffles another."""
    if type(seed) is not int or seed < 0:
        raise IdentityError("seed is a non-negative int")
    if not isinstance(purpose, str) or not purpose:
        raise IdentityError("purpose is a non-empty string")
    material = _SUBSTREAM_DOMAIN + canonical_bytes({"family": FAMILY,
                                                    "family_generator_version": FAMILY_GENERATOR_VERSION,
                                                    "seed": seed, "purpose": purpose})
    return int.from_bytes(hashlib.sha256(material).digest()[:16], "big")


def layout_attempt_stream(seed: int, attempt: int) -> int:
    """The substream for one bounded layout attempt of a parent PAIR.

    Decision 3 sets 64 deterministic attempts per parent pair and requires
    that both variants be rejected when either fails an acceptance
    condition — so the attempt belongs to the pair, above the variant axis,
    and is derived here from the parent seed alone."""
    if type(attempt) is not int or not 0 <= attempt < MAX_LAYOUT_ATTEMPTS:
        raise IdentityError(f"attempt is an int in [0, {MAX_LAYOUT_ATTEMPTS})")
    return stream(seed, f"layout_attempt/{attempt}")


def variant_fact_stream(seed: int, variant: str, purpose: str) -> int:
    """The narrow door for randomness that belongs to ONE variant's declared
    fact rather than to the company-month.

    Deliberately narrow. Decision 2: "Derive both contrast variants from the
    same parent world; the variant changes its declared fact, not the entire
    random stream." Everything a pair shares — parties, chart, opening
    register, the non-target statement rows, the layout attempt — comes from
    `stream(parent_seed, ...)` and is therefore byte-identical across the
    pair. Only the declared fact's own presentation may come from here, and a
    caller reaching for this to draw a shared element is reintroducing the
    thing the rule forbids."""
    if variant not in VARIANTS:
        raise IdentityError(f"variant is {variant!r}, not one of {list(VARIANTS)}")
    return stream(seed, f"variant/{variant}/declared_fact/{purpose}")


# --------------------------------------------------------------------------
# leakage
# --------------------------------------------------------------------------

def private_tokens(ident: ConstructionIdentity, seed: int | None = None) -> tuple:
    """Every private selector token, as text, that must never appear on an
    agent-visible surface: the seed in both bases, the identity digest and
    label, the population, template family and index in the spellings a
    generator might casually interpolate."""
    tokens = [
        ident.digest(), ident.label(), ident.population, ident.template_family,
        f"{ident.template_family}/{ident.template_version}",
        f"{ident.template_family}:{ident.company_month_index}",
        f"cm-{ident.company_month_index}", f"{FAMILY}/{FAMILY_GENERATOR_VERSION}",
        ident.profile_digest,
    ]
    if seed is not None:
        tokens += [str(seed), f"{seed:x}", f"{seed:X}"]
    return tuple(t for t in tokens if isinstance(t, str) and len(t) >= 3)


def identity_leaks(surfaces: dict, ident: ConstructionIdentity, seed: int | None = None) -> list:
    """LITERAL leakage only, over `surfaces` (name -> text): the workspace
    files, the prompt, the task id, any observation the agent can read.

    It cannot see an enumeration attack — that is what the keyed
    `parent_seed` is for. It catches the ordinary way a private selector
    reaches a public file, which is somebody interpolating it into a
    filename, a narration or a document reference."""
    problems = []
    tokens = private_tokens(ident, seed)
    for name in sorted(surfaces):
        text = surfaces[name]
        if not isinstance(text, str):
            continue
        for token in tokens:
            if token in text:
                problems.append(f"{name} carries the private construction token {token[:16]}…")
    return problems


__all__ = [
    "FAMILY", "FAMILY_GENERATOR_VERSION", "SPLITS", "MECHANISMS", "VARIANTS",
    "MAX_LAYOUT_ATTEMPTS", "EPISODE_SETTING_KEYS", "IdentityError",
    "GenerationProfile", "BOUNDED_V1", "PROFILES",
    "ConstructionIdentity", "VIEW_KEYS", "identity", "refuse_episode_settings",
    "parent_seed", "stream", "layout_attempt_stream", "variant_fact_stream",
    "private_tokens", "identity_leaks",
]
