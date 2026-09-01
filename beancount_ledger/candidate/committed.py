"""The committed state: what a rollout has submitted, bound to the environment
that gives it meaning, and the one scorer that reads it.

    SubmissionSnapshot (bytes, three digests)
      -> SafeParsedSubmission + LedgerCandidate + FindingSummary   (parse_once)
      -> CommittedSubmission(candidate, environment, allocation,
                             identities, private receipt)          (commit)
      -> ScoreOutcome                                               (score_committed)

Three properties this module exists to hold:

**Environment-bound.** A candidate's bytes prove where it came from; they do
not prove which task made its allocation or its findings meaningful. The
mint takes a `LoadedEnvironment` resolved by the composition root — never
caller-supplied digests — computes and freezes the allocation there, and
`score_committed` takes the committed object alone: there is no second task
or environment argument whose contents could disagree with the committed
identity. A commitment minted for task A cannot be scored, cached or
replayed as task B.

**Initialisation is its own failure.** Every audit a task must pass — planted
predicates pairwise disjoint and disjoint from the original ledger, the
original ledger accepted clean, comparison policies well-formed, policy
requirements satisfiable by the summary schema, the derived maximum finding
count below the summary's saturation, the engine's cache recipe — runs
before any submission is accepted, and a failure is a typed
`InitializationFailure`: no candidate score, no cache entry, no trajectory.
A raw `ValueError` would have looked like the evaluator-crash class the
rest of the system eliminates.

**One shared allocation.** Which submitted occurrence explains what is
computed once, in canonical occurrence order (never source or parser
order), frozen into the commitment, and read by every component and
penalty. No component rescans.

This is the `candidate/1` scoring contract. It is deliberately not
numerically identical to `raw-text/1`: the text-only channels (comments,
layout, amount spelling) are inexpressible here, and flags are renderer-
owned. The calibration corpus in `tests/test_calibration.py` asserts the
rankings the contract promises rather than parity with the old numbers.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal

from .canonical import (
    CANDIDATE_ENGINE,
    COMPARISON_POLICIES,
    MAX_FINDING_COUNT,
    FindingSummary,
    ScoringEngine,
    canonical_bytes,
    canonical_decimal,
    domain_digest,
    evaluation_receipt_digest,
    finding_sample_payload,
    parse_policy_digest,
    reduce_findings,
    score_result_digest,
    rejection_payload,
    reward_input_digest,
    score_cache_key,
    scorer_contract_digest,
    strict_payee_match,
    task_contract_digest,
)
from ..graph.derive import ContractInputs
from .canonical import DELIVERY_RECEIPT_DOMAIN, RENDERER_VERSION
from .normalise import MAX_BYTES, Accepted, EvaluationFailure, ProtocolFailure, parse_once
from .policy import POLICIES, PolicySnapshot, apply_policy, freeze_policy, payee_matches, validate_policy_requirements
from .schema import LedgerCandidate, ParsedLifecycle, ParsedTransaction, SafeParsedSubmission
from .validate import VALIDATOR_VERSION, iter_violations, max_possible_findings

_COMMIT_TOKEN = object()

ENVIRONMENT_DOMAIN = b"piv:environment:v1\0"

# The published weights and penalties: unchanged from the raw contract where
# the channel survives, absent where it does not (prose, padding, spelling).
WEIGHT_TARGETS = Decimal("0.70")
WEIGHT_RESOLVED = Decimal("0.30")
PENALTY_COLLATERAL = Decimal("-0.40")
PENALTY_TAMPER = Decimal("-0.40")
PENALTY_MERGE = Decimal("-0.40")
PENALTY_UNDOCUMENTED = Decimal("-0.20")
PENALTY_FABRICATION = Decimal("-0.40")
PENALTY_PLUG = Decimal("-1.00")
# The official reward of a file-delivery task whose outcome delivers no
# file. Structural, not a policy row that every consequence must remember:
# a non-renderable result is never success-equivalent, whatever its
# components say. Diagnostic components stay in the outcome.
NON_RENDERABLE_CAP = Decimal("0")
# The reduction's declared rounding: every component and the total are
# quantised to six places (half-even) before they are compared, recorded or
# digested. Part of SCORE_REDUCTION_VERSION.
SCORE_SCALE = Decimal("0.000001")


def _scale(value: Decimal) -> Decimal:
    return value.quantize(SCORE_SCALE, rounding=ROUND_HALF_EVEN)


class InitializationFailure(Exception):
    """The environment could not be built. Nothing was scored."""

    def __init__(self, reasons):
        self.reasons = tuple(reasons)
        super().__init__("environment initialisation failed: " + "; ".join(self.reasons))


@dataclass(frozen=True)
class PlantedItem:
    id: str
    date: str | None
    required: tuple            # ((account, canonical amount), ...) sorted
    must_be_payee: tuple
    payee: str                 # the graph's counterparty: what the deliverable prints for this repair
    narration: str             # the graph's memo: likewise — authored decoration on a repair never survives
    kind: str = "omit"         # omit: record the entry | alter: replace the wrong entry | duplicate: remove one copy
    replaces: tuple = ()       # alter: the wrong entry's shape, ((account, canonical amount), ...) sorted
    expected_count: int = 1    # duplicate: copies the correct books carry


@dataclass(frozen=True)
class LoadedEnvironment:
    """The immutable environment snapshot every commitment refers to.

    Minted only by `load_contract`, after every audit passed. `verify()`
    recomputes the environment digest from the declared data, so a mutated
    snapshot is detected at score time rather than trusted.
    """

    task_id: str
    policy_name: str
    world_id: str
    graph_digest: str
    mutation_plan_digest: str
    view_digests: tuple            # ((view name, digest), ...) every projected view, public and private
    scored_accounts: tuple
    expected_balances: tuple       # ((account, Decimal), ...) sorted
    allowed_accounts: tuple
    planted: tuple                 # (PlantedItem, ...) in task order
    original: Accepted             # the pre-existing ledger, parsed once, clean
    task_contract_digest: str
    scorer_contract_digest: str
    parse_policy_digest: str
    validator_version: int
    engine: ScoringEngine
    policy: PolicySnapshot         # the frozen registries the scorer consults; never the live module dicts
    environment_digest: str
    _mint: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self._mint is not _COMMIT_TOKEN:
            raise TypeError("LoadedEnvironment is minted by load_contract() only")
        # The token is consumed at construction, so `dataclasses.replace`
        # (which re-runs __init__ with the instance's fields) cannot re-point
        # or re-mint: the copy arrives without a token and is refused.
        object.__setattr__(self, "_mint", None)

    def material(self) -> dict:
        return {
            "task_id": self.task_id, "policy": self.policy_name, "world_id": self.world_id,
            "graph_digest": self.graph_digest, "mutation_plan_digest": self.mutation_plan_digest,
            "view_digests": [list(x) for x in self.view_digests],
            "scored_accounts": list(self.scored_accounts),
            "expected_balances": [[a, v] for a, v in self.expected_balances],
            "allowed_accounts": list(self.allowed_accounts),
            "planted": [{"id": p.id, "kind": p.kind, "date": p.date, "required": [list(r) for r in p.required],
                         "replaces": [list(r) for r in p.replaces], "expected_count": p.expected_count,
                         "must_be_payee": list(p.must_be_payee), "payee": p.payee, "narration": p.narration}
                        for p in self.planted],
            "policy": self.policy.as_canonical(),
            "original_candidate_digest": self.original.candidate_digest,
            "original_semantic_fingerprint": self.original.semantic_fingerprint,
            "task_contract_digest": self.task_contract_digest,
            "scorer_contract_digest": self.scorer_contract_digest,
            "parse_policy_digest": self.parse_policy_digest,
            "validator_version": self.validator_version,
            "engine": self.engine.id,
        }

    def versions(self) -> dict:
        """Every evaluator identity a result depends on: bound into the
        evaluation receipt so a replay under a changed evaluator is a
        different receipt, never a silent reinterpretation."""
        return {"engine": self.engine.id, "validator_version": self.validator_version,
                "scorer_contract_digest": self.scorer_contract_digest, "parse_policy_digest": self.parse_policy_digest,
                "task_contract_digest": self.task_contract_digest, "environment_digest": self.environment_digest,
                "renderer_version": RENDERER_VERSION}

    def verify(self) -> None:
        """Recompute, do not trust — SNAPSHOT semantics. The declared data
        (the frozen policy included) must still hash to the minted
        environment digest, and the scorer contract recomputed FROM THE
        SNAPSHOT must be the minted one. The live registries are not
        consulted: a module dict mutated after minting, or during scoring
        from another thread, is not something the scorer reads. The parse
        policy is checked at commit time, where the parse just happened."""
        if type(self.policy) is not PolicySnapshot:
            raise RuntimeError("the environment's policy is not a frozen snapshot")
        if domain_digest(ENVIRONMENT_DOMAIN, canonical_bytes(self.material())) != self.environment_digest:
            raise RuntimeError("the environment snapshot no longer matches its digest")
        if scorer_contract_digest(self.policy) != self.scorer_contract_digest:
            raise RuntimeError("the scorer contract of the snapshot is not the minted one")


def _planted_items(inputs: ContractInputs) -> list[PlantedItem]:
    return [PlantedItem(p.id, p.date, tuple(sorted((a, canonical_decimal(Decimal(v))) for a, v in p.required)),
                        tuple(p.must_be_payee), p.must_be_payee[0] if p.must_be_payee else "", p.narration,
                        kind=getattr(p, "kind", "omit"),
                        replaces=tuple(sorted((a, canonical_decimal(Decimal(v))) for a, v in getattr(p, "replaces", ()))),
                        expected_count=int(getattr(p, "expected_count", 1)))
            for p in inputs.planted]


def _retired_keys(env: "LoadedEnvironment") -> dict:
    """item id -> the ORIGINAL occurrence key the planted item retires: the
    wrong entry (alter) or one copy (duplicate). Audited at load: exactly
    one original occurrence matches an alter's wrong shape; a duplicate's
    shape occurs at least twice."""
    originals = [t for t in env.original.submission.directives if isinstance(t, ParsedTransaction)]
    out = {}
    for item in env.planted:
        if item.kind == "alter":
            shape = item.replaces
        elif item.kind == "duplicate":
            shape = item.required
        else:
            continue
        keys = [occurrence_key(t) for t in originals if t.date == item.date and _txn_shape(t) == shape]
        if keys:
            out[item.id] = keys[0]
    return out


def _expected_counts(env: "LoadedEnvironment") -> Counter:
    """The correct books' count per original occurrence key: the original
    minus what the planted alterations and duplicates retire."""
    counts = Counter(occurrence_key(t) for t in env.original.submission.directives if isinstance(t, ParsedTransaction))
    for key in _retired_keys(env).values():
        counts[key] -= 1
    return counts


def _txn_shape(txn: ParsedTransaction) -> tuple:
    """The posting multiset by (account, canonical value), sorted."""
    return tuple(sorted((p.account, canonical_decimal(p.amount)) for p in txn.postings))


def occurrence_key(txn: ParsedTransaction) -> str:
    """Identity of a transaction occurrence for allocation: its structural
    canonical form WITHOUT the parser position and WITHOUT posting order.
    Two identical entries tie, which is correct — they are interchangeable —
    and nothing about where they sat in the file, or which leg was written
    first, enters: leg order is presentation (Beancount ignores it), and
    the contract declares `pre_existing.posting.order: ignored`. The
    adversary pass found the key digesting authored order, so a reordered
    pre-existing entry was tampering; it is preserved now."""
    data = txn.as_canonical()
    data.pop("index", None)
    data["postings"] = sorted(data["postings"], key=lambda p: (p["account"], canonical_decimal(p["amount"]),
                                                               p["currency"], p["flag"] or ""))
    return domain_digest(b"piv:occurrence:v2\0", canonical_bytes(data))


def _lifecycle_key(item: ParsedLifecycle) -> str:
    data = item.as_canonical()
    data.pop("index", None)
    return domain_digest(b"piv:lifecycle:v1\0", canonical_bytes(data))


def load_contract(inputs: ContractInputs, engine: ScoringEngine = CANDIDATE_ENGINE) -> LoadedEnvironment:
    """Build the immutable environment from GRAPH-DERIVED inputs, or raise
    `InitializationFailure`. The one production door: a task dict, a literal
    balance or a hand-built posting tuple is refused by type before any
    audit runs — the projector is the only minter of `ContractInputs`."""
    if type(inputs) is not ContractInputs:
        raise TypeError(f"load_contract takes graph-derived ContractInputs, not {type(inputs).__name__}")
    reasons: list[str] = []
    policy_name = inputs.task_type
    if policy_name not in POLICIES:
        reasons.append(f"task type {policy_name!r} has no scoring policy")

    original = parse_once(inputs.original_text)
    if not isinstance(original, Accepted):
        reasons.append(f"the original ledger is not accepted: {original}")
    elif not original.domain_valid:
        reasons.append(f"the original ledger has domain findings: {original.finding_summary.codes}")

    planted = _planted_items(inputs)
    for p in planted:
        if p.kind not in ("omit", "alter", "duplicate"):
            reasons.append(f"planted item {p.id} has unknown kind {p.kind!r}")
        if p.kind == "alter" and not p.replaces:
            reasons.append(f"planted item {p.id} alters nothing")
        if p.kind == "duplicate" and p.expected_count != 1:
            reasons.append(f"planted item {p.id}: only expected_count 1 is supported")
    allowed_set = set(inputs.allowed_accounts)
    if not set(inputs.scored_accounts) <= allowed_set:
        reasons.append("a scored account is not an allowed account")
    if {a for a, _ in inputs.expected_balances} != allowed_set:
        reasons.append("expected balances do not cover exactly the allowed accounts")
    for p in planted:
        if not {a for a, _ in p.required} <= allowed_set:
            reasons.append(f"planted item {p.id} posts to an account outside the chart")
    keys = [(p.date, p.required) for p in planted]
    for i, key in enumerate(keys):
        if key in keys[:i]:
            reasons.append(f"planted items share a predicate: {planted[i].id}")
    if isinstance(original, Accepted):
        original_shapes = Counter((t.date, _txn_shape(t)) for t in original.submission.directives
                                  if isinstance(t, ParsedTransaction))
        for p, key in zip(planted, keys):
            if p.kind == "duplicate":
                if original_shapes[key] < 2:
                    reasons.append(f"planted duplicate {p.id} is not present twice in the original")
            elif key in original_shapes:
                reasons.append(f"planted item {p.id} coincides with a pre-existing transaction")
            if p.kind == "alter" and original_shapes[(p.date, p.replaces)] != 1:
                reasons.append(f"planted alteration {p.id}: the wrong entry occurs {original_shapes[(p.date, p.replaces)]} times, not once")
    for p in planted:
        if not p.required:
            reasons.append(f"planted item {p.id} has no required postings")

    snapshot = None
    try:
        snapshot = freeze_policy(policy_name) if policy_name in POLICIES else None
    except (ValueError, KeyError) as exc:
        reasons.append(str(exc))
    from . import canonical as _canonical   # read the live value, not an import-time copy

    maximum = max_possible_findings()
    if maximum >= _canonical.MAX_FINDING_COUNT:
        reasons.append(f"maximum possible findings {maximum} is not below the summary saturation "
                       f"{_canonical.MAX_FINDING_COUNT}")
    try:
        score_cache_key(engine, "probe", "probe", None if not engine.reads_text else "probe")
    except Exception as exc:
        reasons.append(f"engine {engine.id} cache recipe is unusable: {exc}")
    if engine.reads_text:
        reasons.append(f"engine {engine.id} reads text; the committed contract admits candidate engines only")

    if reasons or snapshot is None:
        raise InitializationFailure(reasons or ["no policy snapshot"])

    expected = tuple(sorted((a, Decimal(v)) for a, v in inputs.expected_balances))
    env = LoadedEnvironment(
        task_id=inputs.task_id, policy_name=policy_name, world_id=inputs.world_id,
        graph_digest=inputs.graph_digest, mutation_plan_digest=inputs.mutation_plan_digest,
        view_digests=tuple(tuple(x) for x in inputs.view_digests),
        scored_accounts=tuple(inputs.scored_accounts), expected_balances=expected,
        allowed_accounts=tuple(inputs.allowed_accounts), planted=tuple(planted),
        original=original,
        task_contract_digest=task_contract_digest(inputs.contract_view()),
        scorer_contract_digest=scorer_contract_digest(snapshot),
        parse_policy_digest=parse_policy_digest(), validator_version=VALIDATOR_VERSION,
        engine=engine, policy=snapshot, environment_digest="", _mint=_COMMIT_TOKEN,
    )
    digest = domain_digest(ENVIRONMENT_DOMAIN, canonical_bytes(env.material()))
    object.__setattr__(env, "environment_digest", digest)
    return env


# --------------------------------------------------------------------------
# allocation
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Allocation:
    """One shared fact, in canonical occurrence order.

        keys                   occurrence keys, sorted (the canonical order)
        preserved              indices consumed by a pre-existing occurrence
        planted_to_occurrence  (planted id, index | None), task order
        unexplained            indices neither preserved nor allocated
        unmatched_planted      planted ids with no eligible occurrence
    """

    keys: tuple
    preserved: tuple
    planted_to_occurrence: tuple
    unexplained: tuple
    unmatched_planted: tuple           # planted ids NOT resolved (any kind)
    stale: tuple = ()                  # indices of retired original content still present: explained, unresolved
    stale_items: tuple = ()            # (planted id, index) for each stale occurrence
    item_states: tuple = ()            # (planted id, ScorerState) per item — ITEM_STATES, from the closed universe

    def as_canonical(self) -> dict:
        return {"keys": list(self.keys), "preserved": list(self.preserved),
                "planted": [[pid, idx] for pid, idx in self.planted_to_occurrence],
                "unexplained": list(self.unexplained), "unmatched": list(self.unmatched_planted),
                "stale": list(self.stale), "stale_items": [[pid, idx] for pid, idx in self.stale_items],
                "item_states": [[pid, state] for pid, state in self.item_states]}


# --------------------------------------------------------------------------
# the closed state universe (Codex T44 §4, Q5)
# --------------------------------------------------------------------------

# Every classification this scorer can reach is a member of ONE enumerable
# tuple, `SCORER_STATES`: seven per-item states, five occurrence states,
# three penalty labels and two account states. Before this existed they were
# bare string literals written at the sites that computed them — the
# per-kind item states in `allocate`, the four allocation buckets, and, in
# `score_committed`, every priced channel: the merge and fabrication labels,
# the lost original content, the unaccepted payee, the plug and the
# collateral balance — so "what can a candidate occurrence be?" had no
# answer a test could walk, and a new literal cost nothing. The rule is that
# EVERY PRICED CHANNEL NAMES ITS STATE: if `score_committed` charges for it,
# a member of this universe labels it and a helper here emits it.
# `tests/test_state_conformance.py` walks this tuple against
# `graph/state_contract.py` and demands, for every member, either a public
# reading class an ORIGINAL ledger entry or statement row can occupy or a
# documented exclusion.
#
# A `str` SUBCLASS rather than an `enum.Enum`, deliberately. Every existing
# surface treats a state as a string: `as_canonical()` puts it in the digest
# material, `as_dict()` hands it to `tests/score_payload.py`, and suites
# compare with `==`, with `in`, and by set and dict equality. `enum.Enum`
# hashes by member NAME, so `{ItemState.RESOLVED} == {"RESOLVED"}` is false
# and `json.dumps` refuses the member; a `str` subclass keeps equality,
# hashing, ordering and JSON encoding exactly as they were, so this change
# is a naming of what the code already did and not a change of behaviour.

ITEM_SCOPE = "item"                    # a state of one PLANTED ITEM (per kind)
OCCURRENCE_SCOPE = "occurrence"        # a state of one OCCURRENCE: which bucket of the allocation explains a
                                       # submitted entry, or that an original one is gone (TAMPER)
PENALTY_SCOPE = "penalty"              # a label something is PRICED under
ACCOUNT_SCOPE = "account"              # a state of an account the submission names or moves
STATE_SCOPES = (ITEM_SCOPE, OCCURRENCE_SCOPE, PENALTY_SCOPE, ACCOUNT_SCOPE)
PLANTED_KINDS = ("omit", "alter", "duplicate")


class ScorerState(str):
    """One member of the closed universe, carrying its own metadata.

        scope               item | occurrence | penalty | account
        kinds               the planted kinds an ITEM state can arise for
        credits_resolution  does this state credit `errors_resolved`?
        meaning             one sentence, for the conformance table
    """

    def __new__(cls, name: str, *, scope: str, kinds: tuple = (), credits_resolution: bool = False,
                meaning: str = ""):
        if scope not in STATE_SCOPES:
            raise ValueError(f"unknown state scope {scope!r}")
        if (scope == ITEM_SCOPE) != bool(kinds):
            raise ValueError(f"{name}: an item state names its kinds and nothing else does")
        if any(k not in PLANTED_KINDS for k in kinds):
            raise ValueError(f"{name}: unknown planted kind in {kinds!r}")
        state = super().__new__(cls, name)
        state.scope = scope
        state.kinds = tuple(kinds)
        state.credits_resolution = bool(credits_resolution)
        state.meaning = meaning
        return state

    def __repr__(self) -> str:                  # a diagnostic that says which type it is
        return f"ScorerState({str.__repr__(self)})"

    def __reduce__(self):
        """A copy of a state is a plain `str` of the same value.

        `__new__` takes keyword-only metadata, so the default `str` reduction
        (`(ScorerState, (value,))`) would raise on every `pickle.dumps` and
        every `copy.deepcopy` — a latent failure in any consumer that
        snapshots an `Allocation` or a `ScoreOutcome`, which carry these in
        `item_states`. Reducing to `str` is the right answer rather than a
        workaround: a state's identity IS its string (that is why it is a
        `str` subclass), the metadata is a property of the MEMBER, and a copy
        is not a member — `SCORER_STATES` is the closed universe, and a
        deep-copied `"RESOLVED"` must not pass for one."""
        return (str, (str(self),))


# item states (Codex T40): meaning is named, not derived from optional
# counters. Only RESOLVED credits `errors_resolved`.
STATE_MISSING = ScorerState(
    "MISSING", scope=ITEM_SCOPE, kinds=("omit",),
    meaning="the books still lack the entry: no submitted occurrence satisfies the repair predicate")
STATE_STALE_ONLY = ScorerState(
    "STALE_ONLY", scope=ITEM_SCOPE, kinds=("alter",),
    meaning="the wrongly-booked entry is still there and no corrected entry was supplied")
STATE_REMOVED_WITHOUT_REPAIR = ScorerState(
    "REMOVED_WITHOUT_REPAIR", scope=ITEM_SCOPE, kinds=("alter",),
    meaning="the wrongly-booked entry was deleted and nothing was posted in its place")
STATE_REPAIR_PLUS_STALE = ScorerState(
    "REPAIR_PLUS_STALE", scope=ITEM_SCOPE, kinds=("alter",),
    meaning="the corrected entry was supplied but the wrongly-booked one was left beside it")
STATE_EXTRA_PRESENT = ScorerState(
    "EXTRA_PRESENT", scope=ITEM_SCOPE, kinds=("duplicate",),
    meaning="the surplus copy is still in the books")
STATE_OVER_REMOVED = ScorerState(
    "OVER_REMOVED", scope=ITEM_SCOPE, kinds=("duplicate",),
    meaning="both copies went: the surplus AND the occurrence the correct books keep")
STATE_RESOLVED = ScorerState(
    "RESOLVED", scope=ITEM_SCOPE, kinds=PLANTED_KINDS, credits_resolution=True,
    meaning="the correct books' treatment of the item: the one state that credits errors_resolved")

# occurrence buckets: what explains a submitted transaction. Exactly one
# per occurrence, in canonical occurrence order — `occurrence_states`.
STATE_PRESERVED = ScorerState(
    "PRESERVED", scope=OCCURRENCE_SCOPE,
    meaning="consumed by a pre-existing occurrence the correct books also carry")
STATE_PLANTED_REPAIR = ScorerState(
    "PLANTED_REPAIR", scope=OCCURRENCE_SCOPE,
    meaning="satisfies a planted item's repair predicate (date and exact posting multiset)")
STATE_STALE = ScorerState(
    "STALE", scope=OCCURRENCE_SCOPE,
    meaning="retired original content the agent left in place: explained, never labelled, item unresolved")
STATE_UNEXPLAINED = ScorerState(
    "UNEXPLAINED", scope=OCCURRENCE_SCOPE,
    meaning="neither preserved, nor a repair, nor retired content: nothing in the task explains it")
# The fifth occurrence state, and the only one that is NOT a bucket of the
# submitted record: it is read off the ORIGINAL, against the submission.
# `occurrence_states` therefore does not emit it and its conservation
# identity does not cover it — `tamper_states` does, from the same shared
# allocation, and the two together are the whole occurrence scope.
STATE_TAMPER = ScorerState(
    "TAMPER", scope=OCCURRENCE_SCOPE,
    meaning="original content the submission no longer carries — an occurrence the correct books keep, a "
            "lifecycle directive or an option value: the complement of PRESERVED")

# penalty labels. NOT a refinement of the buckets: `merged` is computed over
# every submitted transaction, so an occurrence of any bucket can straddle
# two planted shapes. One label per occurrence, as the contract declares —
# a rule that binds MERGED and FABRICATED, the two `penalty_states` assigns.
STATE_MERGED = ScorerState(
    "MERGED", scope=PENALTY_SCOPE,
    meaning="one entry straddling two or more planted repair shapes: priced as a merge, never also as a fabrication")
STATE_FABRICATED = ScorerState(
    "FABRICATED", scope=PENALTY_SCOPE,
    meaning="an UNEXPLAINED occurrence that is not merged, or a lifecycle directive the original did not carry")
# The third penalty label is ORTHOGONAL to those two, the way MERGED is
# orthogonal to the buckets: it is charged per resolved ITEM, not per
# occurrence, and the occurrence it reads is a PLANTED_REPAIR and stays one.
# An exact repair attributed to the wrong party is priced here and nowhere
# else, so `penalty_states`' one-label-per-occurrence rule is untouched.
STATE_UNDOCUMENTED = ScorerState(
    "UNDOCUMENTED", scope=PENALTY_SCOPE,
    meaning="a resolved planted repair whose payee is not one the item accepts: the right movement, "
            "attributed to a party the task does not accept for it")

# accounts
STATE_PLUG = ScorerState(
    "PLUG", scope=ACCOUNT_SCOPE,
    meaning="an account the submission posts to or merely opens that the published chart does not carry")
STATE_COLLATERAL = ScorerState(
    "COLLATERAL", scope=ACCOUNT_SCOPE,
    meaning="an account of the published chart the task does not score whose balance the submission moved "
            "off the correct books' figure")

SCORER_STATES = (
    STATE_MISSING, STATE_STALE_ONLY, STATE_REMOVED_WITHOUT_REPAIR, STATE_REPAIR_PLUS_STALE,
    STATE_EXTRA_PRESENT, STATE_OVER_REMOVED, STATE_RESOLVED,
    STATE_PRESERVED, STATE_PLANTED_REPAIR, STATE_STALE, STATE_UNEXPLAINED, STATE_TAMPER,
    STATE_MERGED, STATE_FABRICATED, STATE_UNDOCUMENTED,
    STATE_PLUG, STATE_COLLATERAL,
)

if len(set(SCORER_STATES)) != len(SCORER_STATES):
    raise RuntimeError("the scorer state universe carries a duplicate member")

# Per-kind item states, DERIVED from the universe rather than restated: a
# member whose `kinds` nobody declares is a member no kind admits, and the
# assert in `allocate` then fails loudly instead of widening quietly.
ITEM_STATES = {kind: tuple(s for s in SCORER_STATES if s.scope == ITEM_SCOPE and kind in s.kinds)
               for kind in PLANTED_KINDS}


def occurrence_states(allocation: "Allocation") -> tuple:
    """The bucket of every submitted occurrence, in canonical occurrence
    order. Also the conservation identity: an index in two buckets, or in
    none, raises here rather than reaching a component."""
    out: dict = {}

    def claim(index: int, state: ScorerState) -> None:
        if index in out:
            raise RuntimeError("allocation conservation identity violated")
        out[index] = state

    for index in allocation.preserved:
        claim(index, STATE_PRESERVED)
    for _pid, index in allocation.planted_to_occurrence:
        if index is not None:
            claim(index, STATE_PLANTED_REPAIR)
    for index in allocation.stale:
        claim(index, STATE_STALE)
    for index in allocation.unexplained:
        claim(index, STATE_UNEXPLAINED)
    if len(out) != len(allocation.keys) or set(out) != set(range(len(allocation.keys))):
        raise RuntimeError("allocation conservation identity violated")
    return tuple(out[index] for index in range(len(allocation.keys)))


def penalty_states(allocation: "Allocation", merged_at) -> tuple:
    """`((occurrence index, label), ...)`: the label each priced occurrence
    is charged under. MERGED wins over FABRICATED so an entry is charged
    once, which is what `score_committed` has always done — named here so
    the labels are members of the closed universe rather than two literals
    inside a scoring branch."""
    labelled = {index: STATE_MERGED for index in merged_at}
    for index in allocation.unexplained:
        labelled.setdefault(index, STATE_FABRICATED)
    return tuple(sorted(labelled.items()))


def undocumented_states(env: LoadedEnvironment, allocation: "Allocation", txns) -> tuple:
    """`((label, UNDOCUMENTED), ...)`: every resolved planted repair whose
    payee is not one the item accepts under the frozen comparison policy.

    Charged per ITEM, not per occurrence, which is why it does not go through
    `penalty_states`: the occurrence is a PLANTED_REPAIR and remains one, and
    what is priced is the attribution the agent wrote on it. `txns` is the
    submission's transactions in canonical occurrence order — the order the
    allocation indexes."""
    out = []
    for pid, index in allocation.planted_to_occurrence:
        if index is None:
            continue
        item = next(p for p in env.planted if p.id == pid)
        if item.must_be_payee and not any(payee_matches(env.policy, txns[index].payee, a) for a in item.must_be_payee):
            out.append((f"{pid}: payee={txns[index].payee!r}", STATE_UNDOCUMENTED))
    return tuple(out)


def _lifecycle_index(original: SafeParsedSubmission, submission: SafeParsedSubmission) -> tuple:
    """`(original counts, submitted counts, key -> directive)`: the one read
    of the two lifecycle multisets, shared by TAMPER (what the submission
    lost) and FABRICATED (what it added)."""
    original_life = Counter(_lifecycle_key(i) for i in original.directives if isinstance(i, ParsedLifecycle))
    submitted_life = Counter(_lifecycle_key(i) for i in submission.directives if isinstance(i, ParsedLifecycle))
    by_key = {_lifecycle_key(i): i for i in list(original.directives) + list(submission.directives)
              if isinstance(i, ParsedLifecycle)}
    return original_life, submitted_life, by_key


def _lifecycle_label(item: ParsedLifecycle) -> str:
    return f"{item.date} | {item.kind} | {item.account}"


def tamper_states(env: LoadedEnvironment, submission: SafeParsedSubmission, allocation: "Allocation") -> tuple:
    """`((label, TAMPER), ...)`: the complement of PRESERVED — original
    content the submission no longer carries.

    Three ways to lose it, priced identically: an occurrence the CORRECT
    books keep that the allocation could not find (the original minus what a
    planted alteration or duplicate retires, so removing retired content is
    the repair and not a loss), a lifecycle directive, and an option value.
    The order is the priced order: occurrences in canonical original order,
    then lifecycle, then the currency, then the title."""
    original = env.original.submission
    lost_keys = _expected_counts(env) - Counter(allocation.keys[i] for i in allocation.preserved)
    by_key = {occurrence_key(t): t for t in original.directives if isinstance(t, ParsedTransaction)}
    lost = [_label(by_key[k]) for k, n in lost_keys.items() for _ in range(n)]
    original_life, submitted_life, life_by_key = _lifecycle_index(original, submission)
    for k, n in (original_life - submitted_life).items():
        lost += [_lifecycle_label(life_by_key[k])] * n
    if submission.operating_currency != original.operating_currency:
        lost.append(f"option operating_currency: {original.operating_currency} -> {submission.operating_currency}")
    if submission.title != original.title:
        lost.append("option title changed")
    return tuple((label, STATE_TAMPER) for label in lost)


def account_states(balances, declared, allowed) -> tuple:
    """`((account, PLUG), ...)`: every account the submission names that the
    published chart does not. An account outside the chart is a plug whether
    it was posted to or merely OPENED."""
    return tuple((account, STATE_PLUG) for account in sorted((set(balances) | set(declared)) - set(allowed)))


def collateral_states(balances, expected, targets) -> tuple:
    """`((account, COLLATERAL), ...)`: every account of the published chart
    that the task does NOT score whose balance the submission moved off the
    correct books' figure. Account-scoped like PLUG — a state of a balance,
    not of an occurrence — and priced once per account. `expected` is the
    environment's expected balances as a mapping, so the order is the
    environment's own (sorted) account order."""
    return tuple((account, STATE_COLLATERAL) for account in expected
                 if account not in targets and balances.get(account, Decimal("0")) != expected[account])


def allocate(env: LoadedEnvironment, submission: SafeParsedSubmission) -> Allocation:
    """Preservation, then planted allocation, then the rest — as the scorer
    contract declares (`scorer_contract_view()["allocation"]`).

    Occurrences are ordered by `occurrence_key`, a function of canonical
    candidate state; the eligibility predicate is the date and the exact
    posting multiset by value (flags are renderer-owned in this contract);
    the quality key prefers an occurrence whose payee satisfies the strict
    reward predicate; ties are identical entries.
    """
    txns = sorted((t for t in submission.directives if isinstance(t, ParsedTransaction)), key=occurrence_key)
    keys = tuple(occurrence_key(t) for t in txns)
    # Preservation is against the CORRECT books' counts: the original minus
    # what a planted alteration (its wrong entry) or duplicate (one copy)
    # retires. Removing retired content is the repair, not tampering.
    remaining = _expected_counts(env)
    retired_by_item = _retired_keys(env)
    preserved = []
    for index, key in enumerate(keys):
        if remaining[key] > 0:
            remaining[key] -= 1
            preserved.append(index)
    taken = set(preserved)
    # Stale: retired original content the agent left in place. Explained
    # (it is the original's own record, rendered from the original), never
    # labelled — but the item that retired it stays unresolved.
    stale, stale_items = [], []
    retired_slots: dict = {}
    for pid, key in retired_by_item.items():
        retired_slots.setdefault(key, []).append(pid)
    for index, key in enumerate(keys):
        if index in taken or not retired_slots.get(key):
            continue
        pid = retired_slots[key].pop(0)
        taken.add(index)
        stale.append(index)
        stale_items.append((pid, index))
    stale_for = {pid for pid, _ in stale_items}
    mapping, unmatched, states = [], [], []
    for item in env.planted:
        if item.kind == "duplicate":
            mapping.append((item.id, None))
            key = retired_by_item.get(item.id)
            kept = key is not None and any(keys[i] == key for i in preserved)
            state = STATE_EXTRA_PRESENT if item.id in stale_for else (STATE_RESOLVED if kept else STATE_OVER_REMOVED)
        else:
            eligible = [i for i, t in enumerate(txns)
                        if i not in taken and (item.date is None or t.date == item.date) and _txn_shape(t) == item.required]
            eligible.sort(key=lambda i: (
                0 if not item.must_be_payee or any(payee_matches(env.policy, txns[i].payee, a) for a in item.must_be_payee) else 1, i))
            if eligible:
                taken.add(eligible[0])
                mapping.append((item.id, eligible[0]))
                if item.kind == "alter":
                    state = STATE_REPAIR_PLUS_STALE if item.id in stale_for else STATE_RESOLVED
                else:
                    state = STATE_RESOLVED
            else:
                mapping.append((item.id, None))
                if item.kind == "alter":
                    state = STATE_STALE_ONLY if item.id in stale_for else STATE_REMOVED_WITHOUT_REPAIR
                else:
                    state = STATE_MISSING
        assert state in ITEM_STATES[item.kind]
        states.append((item.id, state))
        if state is not STATE_RESOLVED:
            unmatched.append(item.id)
    unexplained = tuple(i for i in range(len(txns)) if i not in taken)
    allocation = Allocation(keys, tuple(preserved), tuple(mapping), unexplained, tuple(unmatched), tuple(stale),
                            tuple(stale_items), tuple(states))
    # Conservation: every submitted occurrence in exactly one bucket of the
    # CLOSED universe. `occurrence_states` is the one place that walks the
    # four buckets, so a bucket added without a member raises here.
    occurrence_states(allocation)
    return allocation


# --------------------------------------------------------------------------
# the committed object
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PrivateReceipt:
    rollout_id: str
    attempt_id: str
    committed_revision: int
    submitted_text_digest: str
    stored_bytes_digest: str
    logical_text_digest: str


@dataclass(frozen=True)
class CommittedSubmission:
    """Minted only by `commit`, from an accepted parse and the environment."""

    candidate: LedgerCandidate
    submission: SafeParsedSubmission
    environment: LoadedEnvironment
    allocation: Allocation
    finding_summary: FindingSummary
    finding_sample: tuple
    candidate_digest: str
    semantic_fingerprint: str
    reward_input_digest: str              # score-relevant semantic state only: the cache/equivalence key
    evaluation_receipt_digest: str        # reward input + sample + input receipt identity + evaluator versions: what was EVALUATED
    environment_digest: str
    receipt: PrivateReceipt               # the input receipt: what was RECEIVED
    oracle_unmapped: int
    _mint: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self._mint is not _COMMIT_TOKEN:
            raise TypeError("CommittedSubmission is minted by commit() only")
        object.__setattr__(self, "_mint", None)   # consumed: no replace(), no re-mint

    def recheck(self) -> None:
        """Recompute every identity from the deeply immutable data and
        compare to what was minted. Referential consistency is not enough:
        a well-shaped but mutated allocation could direct the planted slot;
        a mutated summary could hide a finding. Runs immediately before
        scoring, and any cache insertion would come only after it."""
        env = self.environment
        env.verify()
        if self.environment_digest != env.environment_digest:
            raise RuntimeError("the commitment does not belong to this environment")
        from .canonical import candidate_digest as _cd, semantic_fingerprint as _sf, summarise_findings
        from .validate import validate_candidate
        if _cd(self.submission) != self.candidate_digest:
            raise RuntimeError("the structural record no longer matches its digest")
        if _sf(self.candidate) != self.semantic_fingerprint:
            raise RuntimeError("the candidate no longer matches its fingerprint")
        if canonical_bytes(allocate(env, self.submission).as_canonical()) != canonical_bytes(self.allocation.as_canonical()):
            raise RuntimeError("the frozen allocation is not the allocation of this submission under this environment")
        summary, sample = reduce_findings(iter_violations(self.candidate))
        if summary != self.finding_summary:
            raise RuntimeError("the finding summary no longer matches the candidate")
        if sample != self.finding_sample:
            raise RuntimeError("the diagnostic sample is not the deterministic sample of this candidate")
        if reward_input_digest(self.candidate_digest, self.finding_summary) != self.reward_input_digest:
            raise RuntimeError("the reward input no longer matches")
        if evaluation_receipt_digest("Accepted", self.reward_input_digest, finding_sample_payload(self.finding_sample),
                                     receipt_identity(self.receipt), env.versions()) != self.evaluation_receipt_digest:
            raise RuntimeError("the evaluation receipt no longer matches what was evaluated")


@dataclass(frozen=True)
class ProtocolRejected:
    """A stored but unaccepted submission: the public rejection consequence."""

    reason: str
    detail: str
    evaluation_receipt_digest: str
    environment_digest: str
    receipt: PrivateReceipt


def commit(accepted: Accepted, env: LoadedEnvironment, receipt: PrivateReceipt) -> CommittedSubmission:
    if not isinstance(accepted, Accepted):
        raise TypeError("commit() takes an Accepted parse")
    env.verify()
    if parse_policy_digest() != env.parse_policy_digest:
        raise RuntimeError("the parse policy changed after the environment was minted; this parse is not under the contract")
    allocation = allocate(env, accepted.submission)
    reward_input = reward_input_digest(accepted.candidate_digest, accepted.finding_summary)
    evaluation = evaluation_receipt_digest("Accepted", reward_input, finding_sample_payload(accepted.domain_findings),
                                           receipt_identity(receipt), env.versions())
    return CommittedSubmission(
        candidate=accepted.candidate, submission=accepted.submission, environment=env,
        allocation=allocation, finding_summary=accepted.finding_summary, finding_sample=accepted.domain_findings,
        candidate_digest=accepted.candidate_digest, semantic_fingerprint=accepted.semantic_fingerprint,
        reward_input_digest=reward_input, evaluation_receipt_digest=evaluation,
        environment_digest=env.environment_digest,
        receipt=receipt, oracle_unmapped=accepted.oracle_unmapped, _mint=_COMMIT_TOKEN,
    )


def reject(failure: ProtocolFailure, env: LoadedEnvironment, receipt: PrivateReceipt) -> ProtocolRejected:
    payload = rejection_payload([(failure.reason, -1, -1)])
    return ProtocolRejected(failure.reason, failure.detail,
                            evaluation_receipt_digest("ProtocolRejected", None, payload, receipt_identity(receipt),
                                                      env.versions()),
                            env.environment_digest, receipt)


def receipt_identity(receipt: PrivateReceipt) -> dict:
    """The input receipt minus the attempt id: a replay of the same bytes
    for the same revision of the same rollout is the same evaluation."""
    return {"rollout_id": receipt.rollout_id, "committed_revision": receipt.committed_revision,
            "submitted_text_digest": receipt.submitted_text_digest, "stored_bytes_digest": receipt.stored_bytes_digest,
            "logical_text_digest": receipt.logical_text_digest}


def new_receipt(rollout_id: str, revision: int, digests: dict) -> PrivateReceipt:
    return PrivateReceipt(rollout_id, uuid.uuid4().hex, revision,
                          digests["submitted_text_digest"], digests["stored_bytes_digest"], digests["logical_text_digest"])


# --------------------------------------------------------------------------
# the candidate/1 scorer
# --------------------------------------------------------------------------

# The closed vocabulary of `ScoreOutcome.blocked_by`: why no deliverable was
# produced. Lower-case, like the delivery `OUTCOMES` below, and closed for
# the same reason `SCORER_STATES` is — a reason invented inside a branch is a
# reason no consumer can enumerate, and `tests/exploits` builds payloads that
# claim one by name. Written here, referenced by name at the branch.
BLOCKED_POLICY = "policy"                       # the policy gate refused the finding summary
BLOCKED_UNEXPLAINED = "unexplained_entries"     # a FABRICATED or MERGED occurrence
BLOCKED_TAMPERED = "tampered_preservation"      # original content lost (TAMPER)
BLOCKED_PLUGS = "plug_accounts"                 # an account outside the published chart (PLUG)
BLOCKED_BY = (BLOCKED_POLICY, BLOCKED_UNEXPLAINED, BLOCKED_TAMPERED, BLOCKED_PLUGS)


@dataclass(frozen=True)
class ScoreOutcome:
    total: Decimal
    components: tuple            # ((name, Decimal), ...)
    target_misses: tuple
    collateral_damage: tuple
    unresolved_planted: tuple
    removed_or_altered: tuple
    fabricated: tuple
    merged_events: tuple
    undocumented: tuple
    plug_accounts: tuple
    gated: bool
    renderable: bool
    engine_id: str
    reward_input_digest: str
    environment_digest: str
    allocation: Allocation
    capped_non_renderable: bool = False
    evaluation_receipt_digest: str = ""     # the evaluation this result answers: rollout, revision, input bytes
    blocked_by: tuple = ()                   # why no deliverable: policy findings, unexplained entries, altered originals
    complete: bool = False                   # RENDERABLE + COMPLETE is the only successful month close
    result_digest: str = ""

    def as_canonical(self) -> dict:
        """Everything the result asserts, as canonical data: the digest
        material. `result_digest` itself is excluded."""
        return {
            "total": canonical_decimal(self.total),
            "components": [[name, canonical_decimal(value)] for name, value in self.components],
            "target_misses": list(self.target_misses), "collateral_damage": list(self.collateral_damage),
            "unresolved_planted": list(self.unresolved_planted), "removed_or_altered": list(self.removed_or_altered),
            "fabricated": list(self.fabricated), "merged_events": list(self.merged_events),
            "undocumented": list(self.undocumented), "plug_accounts": list(self.plug_accounts),
            "gated": self.gated, "renderable": self.renderable, "capped_non_renderable": self.capped_non_renderable,
            "blocked_by": list(self.blocked_by), "complete": self.complete,
            "item_states": [list(x) for x in self.allocation.item_states],
            "engine": self.engine_id, "reward_input_digest": self.reward_input_digest,
            "environment_digest": self.environment_digest, "allocation": self.allocation.as_canonical(),
            "evaluation_receipt_digest": self.evaluation_receipt_digest,
        }

    def verify(self) -> None:
        if type(self) is not ScoreOutcome:
            raise RuntimeError("the recorded result is not a ScoreOutcome")
        if score_result_digest(self.as_canonical()) != self.result_digest:
            raise RuntimeError("the recorded score result no longer reproduces its digest")

    def as_dict(self) -> dict:
        out = {"total": self.total, "components": dict(self.components), "engine": self.engine_id,
               "gated": self.gated, "renderable": self.renderable, "blocked_by": list(self.blocked_by),
               "complete": self.complete, "item_states": dict(self.allocation.item_states)}
        for key in ("target_misses", "collateral_damage", "unresolved_planted", "removed_or_altered",
                    "fabricated", "merged_events", "undocumented", "plug_accounts"):
            out[key] = list(getattr(self, key))
        return out


def _label(txn: ParsedTransaction) -> str:
    return f"{txn.date} | {txn.payee or ''} | {txn.narration[:40]}"


# --------------------------------------------------------------------------
# the delivered artifact
# --------------------------------------------------------------------------

# The submitted source is an INPUT LANGUAGE, not the deliverable. Scoring
# ignores comments, arithmetic spellings and layout because they are not
# bookkeeping; that is only safe if they cannot survive into the file that
# receives the score. So the authoritative deliverable is a deterministic
# canonical rendering of the committed structural record — authored payee,
# narration, tags, links, references and postings kept; comments, spacing and
# spellings gone — written atomically over `ledger.beancount` at
# finalisation, with the raw submission retained beside it as an audit
# artifact outside the public manifest. Two receipts: the input receipt
# proves what was evaluated, the delivery receipt proves what was delivered.

ACCOUNT_WIDTH = 38
AMOUNT_WIDTH = 14

# Publication is a revisioned transaction. The current-revision manifest
# (`delivery.json`, written last and atomically) binds rollout, revision,
# outcome variant, evaluation receipt, score and the artifact's identity —
# or NO_ARTIFACT, in which case nothing is at the public ledger path. A
# reader never pairs a score with a file the manifest does not name.
AUDIT_DIR = ".submitted"
PUBLICATION_FILE = "delivery.json"
PUBLICATION_SCHEMA = "piv.delivery/1"
NO_ARTIFACT = "NO_ARTIFACT"
OUTCOME_DELIVERED = "delivered"
OUTCOME_POLICY_BLOCKED = "policy_blocked"
OUTCOME_PROTOCOL_REJECTED = "protocol_rejected"
OUTCOMES = (OUTCOME_DELIVERED, OUTCOME_POLICY_BLOCKED, OUTCOME_PROTOCOL_REJECTED)

# The audit archive holds attacker-controlled bytes: bounded per file and in
# total, fixed names from a validated integer, exclusive creation (no
# symlink is ever followed), never in the manifest, never in a trajectory.
MAX_AUDIT_REVISIONS = 4
MAX_AUDIT_FILE_BYTES = MAX_BYTES
MAX_AUDIT_TOTAL_BYTES = 2 * MAX_BYTES        # bites before the count cap for full-size submissions


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


# The closed inventory of retained fields: what each one is, on the way from
# the source to the deliverable. Every field the renderer prints is either
# constrained by the scoring semantics for its role or replaced by the
# graph's own value; nothing authored is retained unconstrained. The witness
# in `test_committed` walks this table against the code.
RETAINED_FIELDS = {
    # field:            (structural key, semantic fingerprint, pre-existing entry, planted repair, unexplained entry)
    "date":             ("occurrence_key", "yes", "exact",   "eligibility (exact)",          "never rendered"),
    "postings":         ("occurrence_key", "yes", "exact multiset (order ignored)", "eligibility (exact multiset)", "never rendered"),
    "payee":            ("occurrence_key", "entity", "exact", "scored (planted_repair.payee); RENDERED FROM GRAPH", "never rendered"),
    "narration":        ("occurrence_key", "no",  "exact",   "ignored; RENDERED FROM GRAPH", "never rendered"),
    "tags":             ("occurrence_key", "no",  "exact",   "ignored; NOT RENDERED",        "never rendered"),
    "links":            ("occurrence_key", "no",  "exact",   "ignored; NOT RENDERED",        "never rendered"),
    "source_refs":      ("occurrence_key", "source_ref", "exact", "ignored; NOT RENDERED",   "never rendered"),
    "flag":             ("occurrence_key", "no",  "exact",   "ignored; rendered '*'",        "never rendered"),
    "postings.flag":    ("occurrence_key", "no",  "exact",   "ignored; NOT RENDERED",        "never rendered"),
    # An unexplained entry, an added or removed lifecycle directive or a
    # changed option makes the outcome NON-RENDERABLE: nothing authored can
    # reach the deliverable except through exact preservation. The title
    # and the chart are printed from the ORIGINAL, never from the submission.
    "option.title":     ("preservation", "no",  "exact",   "n/a",                          "never rendered; printed from the original"),
    "lifecycle":        ("preservation", "yes", "exact",   "n/a",                          "never rendered; printed from the original"),
}


def rejection_result_digest(committed: "ProtocolRejected") -> str:
    """The fixed result of a protocol rejection, bound like a score result."""
    return score_result_digest({"variant": "protocol_rejected", "total": "0", "reason": committed.reason,
                                "evaluation_receipt_digest": committed.evaluation_receipt_digest})


def render_committed(committed: CommittedSubmission) -> str:
    """The one spelling of the committed structural record.

    Pre-existing entries print as written (exact preservation constrains
    every retained field). A planted repair prints the GRAPH's payee and
    narration and no tags, links, references or posting flags: its authored
    decoration was never scored, so it cannot survive into the file that
    carries the score — the displacement attack ("DO NOT POST — fictitious"
    as narration on an exact repair) scores 1.0 and delivers a truthful
    ledger. Unexplained entries print as written; they are penalised."""
    sub = committed.submission
    original = committed.environment.original.submission
    allocation = committed.allocation
    canon = sorted((d for d in sub.directives if isinstance(d, ParsedTransaction)), key=occurrence_key)
    by_item = {p.id: p for p in committed.environment.planted}
    repairs = {id(canon[index]): by_item[pid] for pid, index in allocation.planted_to_occurrence if index is not None}
    # Preserved occurrences print from the ORIGINAL's record (its leg order,
    # its spelling) — the submission's copy is identical up to presentation.
    originals = {}
    for t in original.directives:
        if isinstance(t, ParsedTransaction):
            originals.setdefault(occurrence_key(t), t)
    preserved = {id(canon[index]): originals[allocation.keys[index]] for index in allocation.preserved}
    for _, index in allocation.stale_items:                 # retired original content the agent left: printed as the original wrote it
        preserved[id(canon[index])] = originals[allocation.keys[index]]
    if allocation.unexplained or any(id(t) not in preserved and id(t) not in repairs for t in canon):
        raise RuntimeError("only a fully explained record is rendered; this one has unexplained occurrences")
    lines: list[str] = []
    if original.title is not None:
        lines.append(f'option "title" {_quote(original.title)}')
    lines.append(f'option "operating_currency" "{original.operating_currency}"')
    lines.append("")
    life = sorted((d for d in original.directives if isinstance(d, ParsedLifecycle)),
                  key=lambda d: (d.date, d.kind != "open", d.account))
    for item in life:
        if item.kind == "open":
            currencies = ",".join(item.currencies) or original.operating_currency
            lines.append(f"{item.date} open {item.account:<{ACCOUNT_WIDTH}} {currencies}")
        else:
            lines.append(f"{item.date} close {item.account}")
    if life:
        lines.append("")
    txns = sorted((preserved.get(id(t), t) for t in canon), key=lambda t: (t.date, occurrence_key(t)))
    for t in txns:
        planted = repairs.get(id(t))
        if planted is not None:
            lines.append(f"{t.date} * {_quote(planted.payee)} {_quote(planted.narration)}")
        else:
            head = f"{t.date} {t.flag}"
            if t.payee is not None:
                head += f" {_quote(t.payee)}"
            head += f" {_quote(t.narration)}"
            head += "".join(f" #{tag}" for tag in t.tags) + "".join(f" ^{link}" for link in t.links)
            lines.append(head)
            for key, value in t.source_refs:
                lines.append(f"  {key}: {_quote(value)}")
        for p in t.postings:
            flag = f"{p.flag} " if p.flag and planted is None else ""
            amount = canonical_decimal(p.amount)
            if "." not in amount:
                amount += ".00"
            elif len(amount.split(".")[1]) == 1:
                amount += "0"
            lines.append(f"  {flag}{p.account:<{ACCOUNT_WIDTH}} {amount:>{AMOUNT_WIDTH}} {p.currency}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


@dataclass(frozen=True)
class DeliveryReceipt:
    """What was delivered, as one revisioned record: the evaluation receipt
    plus the artifact identity (or NO_ARTIFACT) and the recorded score."""

    rollout_id: str
    committed_revision: int
    outcome: str
    input_stored_bytes_digest: str
    input_logical_text_digest: str
    evaluation_receipt_digest: str
    score_result_digest: str         # what was RETURNED: the exact result, or the rejection's fixed result
    completion: str                  # complete | incomplete — separate from renderability
    artifact_stored_bytes_digest: str
    artifact_logical_text_digest: str
    score: str                       # canonical decimal
    delivery_receipt_digest: str = ""

    def __post_init__(self):
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {self.outcome!r}")
        if (self.artifact_stored_bytes_digest == NO_ARTIFACT) != (self.outcome != OUTCOME_DELIVERED):
            raise ValueError("a delivered outcome names its artifact; every other outcome has none")
        if (self.artifact_logical_text_digest == NO_ARTIFACT) != (self.artifact_stored_bytes_digest == NO_ARTIFACT):
            raise ValueError("artifact digests are both present or both absent")
        if self.completion not in ("complete", "incomplete"):
            raise ValueError("completion is complete or incomplete")
        if self.completion == "complete" and self.outcome != OUTCOME_DELIVERED:
            raise ValueError("only a delivered outcome can be complete")
        if not isinstance(self.committed_revision, int) or isinstance(self.committed_revision, bool):
            raise ValueError("revision is an integer")

    @property
    def renderable(self) -> bool:
        return self.outcome == OUTCOME_DELIVERED

    def material(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "delivery_receipt_digest"}

    def with_digest(self) -> "DeliveryReceipt":
        return dataclasses.replace(self, delivery_receipt_digest=domain_digest(DELIVERY_RECEIPT_DOMAIN,
                                                                                 canonical_bytes(self.material())))

    def verify(self) -> None:
        if self.with_digest().delivery_receipt_digest != self.delivery_receipt_digest:
            raise RuntimeError("the delivery receipt does not match its digest")

    def to_json(self) -> str:
        return json.dumps({"schema": PUBLICATION_SCHEMA, **self.__dict__}, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "DeliveryReceipt":
        data = json.loads(text)
        expected = {"schema"} | {f.name for f in dataclasses.fields(cls)}
        if not isinstance(data, dict) or set(data) != expected or data["schema"] != PUBLICATION_SCHEMA:
            raise RuntimeError("the publication manifest is not of the expected schema")
        data.pop("schema")
        receipt = cls(**data)
        receipt.verify()
        return receipt


def score_committed(committed: CommittedSubmission) -> ScoreOutcome:
    """The `candidate/1` engine. Reads the committed object and nothing else."""
    if type(committed) is not CommittedSubmission:
        raise TypeError("score_committed() takes a CommittedSubmission")
    committed.recheck()          # every identity recomputed from the data, immediately before scoring
    env = committed.environment
    candidate = committed.candidate
    submission = committed.submission
    allocation = committed.allocation
    txns = sorted((t for t in submission.directives if isinstance(t, ParsedTransaction)), key=occurrence_key)

    balances = candidate.balances
    expected = dict(env.expected_balances)
    targets = list(env.scored_accounts)

    def _miss(account) -> str:
        return f"{account}: expected {expected[account]}, got {balances.get(account, Decimal('0'))}"

    def compare(accounts):
        misses = [_miss(a) for a in accounts if balances.get(a, Decimal("0")) != expected[a]]
        hit = Decimal(len(accounts) - len(misses)) / Decimal(len(accounts)) if accounts else Decimal("1")
        return hit, tuple(misses)

    hit, target_misses = compare(targets)
    # The same comparison over the accounts the task does NOT score is the
    # COLLATERAL channel, and it is labelled where it is computed.
    collateral = tuple(_miss(account) for account, _state in collateral_states(balances, expected, targets))
    planted = env.planted
    resolved = (Decimal(len(planted) - len(allocation.unmatched_planted)) / Decimal(len(planted))
                if planted else Decimal("1"))

    # Preservation, the TAMPER channel: pre-existing occurrences the
    # allocation could not find, lifecycle directives lost, options changed.
    # Structural identity minus parser position — narration, payee, flags,
    # tags, links, references and postings all count; where the entry sat in
    # the file does not.
    original = env.original.submission
    removed = [label for label, _state in tamper_states(env, submission, allocation)]
    original_life, submitted_life, life_by_key = _lifecycle_index(original, submission)

    shapes = [set(item.required) for item in planted]
    merged_at = {i for i, t in enumerate(txns) if sum(1 for s in shapes if s & set(_txn_shape(t))) >= 2}
    labels = dict(penalty_states(allocation, merged_at))
    merged = [_label(txns[i]) for i in sorted(merged_at)]
    # One penalty label per occurrence, as the contract declares: a merged
    # entry is labelled merged, not also fabricated.
    fabricated = [_label(txns[i]) for i in allocation.unexplained if labels[i] is STATE_FABRICATED]
    for k, n in (submitted_life - original_life).items():
        fabricated += [_lifecycle_label(life_by_key[k])] * n

    undocumented = [label for label, _state in undocumented_states(env, allocation, txns)]

    allowed = set(env.allowed_accounts)
    # An account outside the chart is a plug whether it was posted to or
    # merely OPENED: the adversary pass opened `Equity:Suspense` with no
    # postings and the balance-keyed check never saw it.
    declared = {i.account for i in submission.directives if isinstance(i, ParsedLifecycle)}
    plugs = [account for account, _state in account_states(balances, declared, allowed)]

    hit, resolved = _scale(hit), _scale(resolved)
    components = (("targets_hit", hit), ("errors_resolved", resolved))
    total = WEIGHT_TARGETS * hit + WEIGHT_RESOLVED * resolved
    total += PENALTY_COLLATERAL * len(collateral)
    total += PENALTY_TAMPER * len(removed)
    total += PENALTY_MERGE * len(merged)
    total += PENALTY_UNDOCUMENTED * len(undocumented)
    total += PENALTY_FABRICATION * len(fabricated)
    if plugs:
        total += PENALTY_PLUG
    priced = apply_policy(float(total), committed.finding_summary, env.policy)   # the SNAPSHOT, never the registry
    total = _scale(max(Decimal("0"), min(Decimal("1"), Decimal(str(priced["total"])))))
    # The deliverable is rendered only for a FULLY EXPLAINED record: every
    # occurrence preserved or planted, lifecycle and options unchanged. One
    # unexplained entry, one added `close`, one changed title is a file that
    # is not the books — and the adversary pass showed that one such item
    # costs exactly the penalty budget (1.00 − 0.40 = 0.60) while the
    # renderer printed it verbatim: a wash entry, a zero-net fiction, a
    # 200-character notice, a closed bank account, a ghost account. So the
    # outcome is non-renderable, no artifact is delivered and the official
    # reward is the cap; the components stay as diagnostics.
    blocked = []
    if not priced["renderable"]:
        blocked.append(BLOCKED_POLICY)
    if fabricated or merged:
        blocked.append(BLOCKED_UNEXPLAINED)
    if removed:
        blocked.append(BLOCKED_TAMPERED)
    if plugs:
        blocked.append(BLOCKED_PLUGS)
    renderable = not blocked
    # Completion is separate from renderability: a renderable file with an
    # unresolved item or a wrong balance is INCOMPLETE — partial reward and
    # a canonical file, never success (Codex T40).
    complete = renderable and not allocation.unmatched_planted and not target_misses and not collateral and not undocumented
    capped = False
    if not renderable and total > NON_RENDERABLE_CAP:
        total, capped = NON_RENDERABLE_CAP, True       # no file, no official success
    if not complete and total >= Decimal("1"):
        raise RuntimeError("an incomplete outcome reached the maximum reward")
    outcome = ScoreOutcome(
        total=total, components=components, target_misses=target_misses, collateral_damage=collateral,
        unresolved_planted=tuple(allocation.unmatched_planted), removed_or_altered=tuple(removed),
        fabricated=tuple(fabricated), merged_events=tuple(merged), undocumented=tuple(undocumented),
        plug_accounts=tuple(plugs), gated=bool(priced["gated"]), renderable=renderable,
        engine_id=env.engine.id, reward_input_digest=committed.reward_input_digest,
        environment_digest=committed.environment_digest, allocation=allocation, capped_non_renderable=capped,
        evaluation_receipt_digest=committed.evaluation_receipt_digest, blocked_by=tuple(blocked), complete=complete,
    )
    return dataclasses.replace(outcome, result_digest=score_result_digest(outcome.as_canonical()))
