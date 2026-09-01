"""What a domain violation costs. Owned by the task, not by the validator.

`validate_candidate` produces *facts*: this event does not balance, this
account is opened twice, this posting lands in an account the chart does not
declare. Those are universal — they are true of the ledger regardless of what
anyone was asked to do with it.

What they should cost is not universal, and putting the answer in the validator
was a mistake made immediately after catching the same mistake elsewhere. A
"every event must name a known counterparty" rule had just been removed from
universal validation because it was a *task* requirement in disguise; fixed
severities were the same thing one layer up. The same fact reads differently
per task:

    unbalanced event    fatal when the deliverable is a financial report;
                        zeroes one disclosed component in an unbalanced-entry
                        repair task, where preservation and target balances
                        remain perfectly measurable

    duplicate open      collateral modification in a full-ledger repair task;
                        irrelevant in a task whose submission is a set of
                        duplicate-payment identifiers

So the policy lives here, keyed by task, and it is disclosed with the task
rather than discovered from a score. `test_policy_is_exhaustive` fails if the
validator can emit a code no policy names, which is what stops this file
drifting behind the validator and silently defaulting.

**This is a placeholder for the task contract.** The contract does not exist
yet. When it does, this table moves into it and becomes versioned along with
the observation manifest and the prompt. The shape is meant to survive that
move; the location is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Consequence:
    """What one violation does to the outcome.

    Three independent axes rather than one severity level, because they really
    are independent and collapsing them caused a bug. Duplicate `open` was
    classified "render only", which meant a submission could earn full marks
    with a ledger the environment refuses to emit — the high-score-unusable-
    output pattern this whole redesign exists to remove, rebuilt by accident.

    `caps_reward` is what prevents that. A candidate that cannot be rendered
    cannot also be a complete success, so anything blocking render must cap the
    score below the maximum even when it zeroes no particular component.
    """

    zeroes: tuple[str, ...] = ()      # named components set to zero
    gates_all: bool = False           # no component may contribute
    blocks_render: bool = False       # no canonical artifact may be emitted
    caps_reward: float | None = None  # ceiling on the total

    def __str__(self) -> str:
        parts = []
        if self.gates_all:
            parts.append("gates all reward")
        if self.zeroes:
            parts.append(f"zeroes {', '.join(self.zeroes)}")
        if self.blocks_render:
            parts.append("blocks render")
        if self.caps_reward is not None:
            parts.append(f"caps reward at {self.caps_reward}")
        return "; ".join(parts) or "no consequence"


# The policy for the bank-reconciliation task, whose submission is a complete
# replacement ledger. Every entry here is a claim about *this* task, and each
# one should be derivable from something the agent can read.
BANK_RECONCILIATION = {
    # Double entry is stated in the policy document and is the first thing any
    # bookkeeper checks. A ledger that does not balance is not a ledger.
    "event.unbalanced": Consequence(gates_all=True, blocks_render=True),
    "event.too_few_postings": Consequence(gates_all=True, blocks_render=True),

    # The chart of accounts is an observation. Posting outside it, or outside
    # an account's lifetime, contradicts a document the agent was given.
    "posting.account_not_open": Consequence(gates_all=True, blocks_render=True),
    "posting.before_account_opened": Consequence(gates_all=True, blocks_render=True),
    "posting.after_account_closed": Consequence(gates_all=True, blocks_render=True),

    # Lifecycle directives are pre-existing facts outside the permitted edit
    # set, so damaging them is collateral modification. It also makes the
    # canonical render impossible.
    #
    # `caps_reward` is the part that matters and the part that was missing:
    # without it, duplicating every `open` directive blocked the render while
    # leaving the score untouched, so the maximum was reachable with a ledger
    # nothing downstream could use.
    "lifecycle.duplicate_open": Consequence(
        zeroes=("preservation",), blocks_render=True, caps_reward=0.0),
    "lifecycle.duplicate_close": Consequence(
        zeroes=("preservation",), blocks_render=True, caps_reward=0.0),
    "lifecycle.close_without_open": Consequence(gates_all=True, blocks_render=True),
    "lifecycle.close_before_open": Consequence(gates_all=True, blocks_render=True),
}

POLICIES = {
    "bank_reconciliation": BANK_RECONCILIATION,
}


# What each policy READS from the summary, per finding code — the closed
# aggregation schema. Today every rule depends on presence only, so the
# saturated count is reward-equivalent to any larger count by construction;
# a future rule that needs a count by account, a monetary aggregate or an
# occurrence set must declare it here, and contract construction fails if the
# summary schema does not preserve that reduction (`validate_policy_requirements`).
POLICY_REQUIREMENTS = {
    "bank_reconciliation": {code: "presence" for code in BANK_RECONCILIATION},
}


def validate_policy_requirements() -> None:
    from .canonical import FINDING_REDUCTIONS

    for task, needs in POLICY_REQUIREMENTS.items():
        for code, reduction in needs.items():
            preserved = FINDING_REDUCTIONS.get(code)
            if preserved is None or reduction not in preserved:
                raise ValueError(
                    f"policy {task!r} reads {reduction!r} of {code!r}, which the finding "
                    f"summary schema does not preserve ({preserved})"
                )


@dataclass(frozen=True)
class PolicySnapshot:
    """The registries, frozen at environment construction: every task's
    consequences and requirements, every comparison policy, every finding
    reduction — as sorted tuples of tuples, deeply immutable. The scorer
    consults this and never a module dict, so there is no window between
    a recheck and a reduction in which a live registry can change what is
    read; a mutated snapshot is caught by the environment digest."""

    task: str
    consequences: tuple        # ((task, ((code, Consequence), ...)), ...)
    requirements: tuple        # ((task, ((code, reduction), ...)), ...)
    comparison_policies: tuple # ((name, ((key, value), ...)), ...)
    reductions: tuple          # ((code, (reduction, ...)), ...)

    def table(self) -> dict:
        return dict(dict(self.consequences)[self.task])

    def comparison(self, name: str) -> dict:
        return dict(dict(self.comparison_policies)[name])

    def requirements_view(self) -> dict:
        return {task: dict(needs) for task, needs in self.requirements}

    def comparison_view(self) -> dict:
        return {name: dict(spec) for name, spec in self.comparison_policies}

    def reductions_view(self) -> dict:
        return {code: list(r) for code, r in self.reductions}

    def as_canonical(self) -> dict:
        return {
            "task": self.task,
            "consequences": {task: {code: {"zeroes": list(c.zeroes), "gates_all": c.gates_all,
                                           "blocks_render": c.blocks_render,
                                           "caps_reward": None if c.caps_reward is None else str(c.caps_reward)}
                                    for code, c in rows} for task, rows in self.consequences},
            "requirements": self.requirements_view(), "comparison_policies": self.comparison_view(),
            "reductions": self.reductions_view(),
        }


def freeze_policy(task: str) -> PolicySnapshot:
    """Snapshot the live registries for a task. The only place they are
    read on the scoring path; `load_contract` calls it once."""
    from .canonical import COMPARISON_POLICIES, FINDING_REDUCTIONS

    if task not in POLICIES:
        raise KeyError(f"task type {task!r} has no scoring policy")
    validate_policy_requirements()
    for name, spec in COMPARISON_POLICIES.items():
        missing = {"case_sensitive", "whitespace", "unicode", "punctuation", "suffixes", "used_for"} - set(spec)
        if missing:
            raise ValueError(f"comparison policy {name!r} is malformed: missing {sorted(missing)}")
    return PolicySnapshot(
        task=task,
        consequences=tuple((t, tuple(sorted(rows.items()))) for t, rows in sorted(POLICIES.items())),
        requirements=tuple((t, tuple(sorted(needs.items()))) for t, needs in sorted(POLICY_REQUIREMENTS.items())),
        comparison_policies=tuple((n, tuple(sorted(spec.items()))) for n, spec in sorted(COMPARISON_POLICIES.items())),
        reductions=tuple((c, tuple(r)) for c, r in sorted(FINDING_REDUCTIONS.items())),
    )


def payee_matches(snapshot: PolicySnapshot, submitted, accepted: str) -> bool:
    """The reward predicate `planted_repair.payee`, driven by the frozen
    comparison policy: whitespace runs collapsed when the policy says so,
    case folded only when the policy says so, nothing else normalised (both
    sides are NFC already). A lookalike, a ligature or a dotted/dotless I is
    not the accepted counterparty."""
    if not isinstance(submitted, str):
        return False
    spec = snapshot.comparison("planted_repair.payee")
    a, b = submitted, accepted
    if spec["whitespace"] == "collapse_runs":
        a, b = " ".join(a.split()), " ".join(b.split())
    if not spec["case_sensitive"]:
        a, b = a.casefold(), b.casefold()
    return a == b


def _codes(summary) -> list[str]:
    """The codes to price, from a `FindingSummary` ONLY — the whole
    candidate, as counts by code. A sequence of findings is refused: a
    capped list reaching here as the authority was the attack surface, and
    an overload that still accepted one would bring it back at the next
    call site."""
    if not (hasattr(summary, "codes") and hasattr(summary, "counts") and hasattr(summary, "truncated")):
        raise TypeError("the policy consumes a FindingSummary, never a finding sequence")
    return list(summary.codes)


def consequences(summary, task="bank_reconciliation") -> list[Consequence]:
    """Look up what these findings cost under a task. Never guesses.

    A code with no entry raises rather than defaulting. A default would be a
    scoring rule nobody wrote down and nobody disclosed, which is precisely
    what the exhaustiveness test exists to prevent — and a silent default is
    how the four undisclosed rules got in the first time.

    `task` is a `PolicySnapshot` on the scoring path (the frozen table) or a
    task name for construction-time and test use (the live table).
    """
    table = task.table() if isinstance(task, PolicySnapshot) else POLICIES[task]
    codes = _codes(summary)
    missing = sorted(set(codes) - set(table))
    if missing:
        raise KeyError(
            f"task {task!r} has no disposition for violation code(s) "
            f"{missing}; every code the validator can emit must have one"
        )
    return [table[code] for code in codes]


def apply_policy(score: float, summary, task="bank_reconciliation") -> dict:
    """Combine a raw score with the consequences of the finding summary."""
    found = consequences(summary, task)
    zeroed = sorted({c for cons in found for c in cons.zeroes})
    gated = any(c.gates_all for c in found)
    blocked = any(c.blocks_render for c in found)
    caps = [c.caps_reward for c in found if c.caps_reward is not None]

    total = 0.0 if gated else score
    if caps:
        total = min(total, min(caps))
    return {
        "total": total,
        "zeroed_components": zeroed,
        "gated": gated,
        "renderable": not blocked,
    }
