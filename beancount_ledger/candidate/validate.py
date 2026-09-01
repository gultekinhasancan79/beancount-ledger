"""Domain validity, as a total function over candidates.

`beancount.ops.validation.validate` was doing this job and should not be. Two
reasons, one discovered and one argued.

The discovered one: it assumes *booked* entries. Since the boundary moved to a
parser that does not book — because the one that books also imports modules
named by submitted content — an unbooked sentinel reaching it raises
AttributeError rather than reporting anything. Working around that meant
ordering our checks to protect a third-party function from inputs it was never
promised, which is a coupling that would have kept costing.

The argued one: it validates beancount's notion of a ledger, and what we need
validated is *ours*. The candidate schema is closed and small, so its
invariants are few and can be checked directly against it.

**Total** is the property that matters here, and it is asserted rather than
hoped: for every value constructible under the schema, this returns a list of
violations and does not raise. A validator that can throw is a validator that
turns a malformed submission into an evaluator crash, and an evaluator crash
must never be charged to the agent.

Beancount's validation keeps two safer jobs, both outside the reward path: a
differential oracle over the overlap between its semantics and ours, and an
integration assertion that a canonical render of a valid candidate is a ledger
beancount also accepts. If those disagree, that is our drift to fix, not a fact
about the submission.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .schema import LedgerCandidate


@dataclass(frozen=True)
class DomainViolation:
    """A fact about the bookkeeping. Not a verdict about the score.

    This carried a `gate` field -- total, component or render -- fixed on each
    violation code. That was the same mistake as the counterparty rule it was
    written right after, made one layer up: a *task* decision installed as a
    *universal* property.

    The fact "this event does not balance" is universal. What it should cost is
    not. Under report production an unbalanced ledger is fatal; under an
    unbalanced-entry repair task it zeroes the disclosed balance component
    while preservation and target balances stay perfectly measurable; under a
    task whose submission is a set of duplicate-payment IDs it may not arise at
    all. A severity baked in here would silently impose the first reading on
    every task that ever uses this validator.

    So violations carry the code, a human-readable message, and structured
    `facts` for a policy to dispatch on. The mapping from fact to consequence
    belongs to the task contract, which is disclosed, versioned, and tested for
    exhaustiveness -- see `policy.py`.
    """

    code: str
    message: str
    facts: tuple = ()

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


VALIDATOR_VERSION = 1

# Every code the validator can emit, with the most it can emit per unit of
# the bounded candidate. `max_possible_findings` derives the maximum from
# these and the parse caps, so the summary's saturation is proven, not
# documented, and a rule registered without a bound fails closed.
# Each rule declares the UNIT it fires per and an EXCLUSIVITY GROUP: codes in
# one (unit, group) are mutually exclusive on that unit and count once. The
# bound is then a sum over distinct groups per unit — executable, monotone
# under registration (a new rule with a new group adds a whole unit-count; a
# rule joining a group adds nothing), and never "clever" in a comment. A
# rule registered without a unit and group fails `max_possible_findings`.
RULES = {
    "event.too_few_postings": ("per_event", "balance"),      # an event with <2 postings is not also "unbalanced"
    "event.unbalanced": ("per_event", "balance"),
    "posting.account_not_open": ("per_posting", "open_state"),   # never opened: "before" is not evaluated
    "posting.before_account_opened": ("per_posting", "open_state"),
    "posting.after_account_closed": ("per_posting", "close_state"),  # can hold alongside "before" (close < open)
    "lifecycle.duplicate_open": ("per_lifecycle", "duplicate"),
    "lifecycle.duplicate_close": ("per_lifecycle", "duplicate"),
    "lifecycle.close_without_open": ("per_lifecycle", "close"),
    "lifecycle.close_before_open": ("per_lifecycle", "close"),
}
UNITS = ("per_event", "per_posting", "per_lifecycle")


def max_possible_findings() -> int:
    """An upper bound from the parse caps and the registered rules.

    Events are capped by MAX_EVENTS and postings per event by
    MAX_POSTINGS_PER_EVENT; lifecycle items are capped by MAX_LINES (each is
    a line). Per unit, the count is the number of distinct exclusivity
    groups — a conservative sum without any exclusivity would be larger and
    is preferred to an incorrect reduction, so a rule whose group claim is
    wrong can only be corrected by splitting the group (raising the bound).
    """
    from . import normalise

    groups: dict[str, set] = {unit: set() for unit in UNITS}
    for code, (unit, group) in RULES.items():
        if unit not in groups:
            raise ValueError(f"rule {code!r} declares unknown unit {unit!r}")
        groups[unit].add(group)
    per_event, per_posting, per_lifecycle = (len(groups[u]) for u in UNITS)
    return (normalise.MAX_EVENTS * (per_event + per_posting * normalise.MAX_POSTINGS_PER_EVENT)
            + normalise.MAX_LINES * per_lifecycle)


def iter_violations(candidate: LedgerCandidate):
    """Every domain invariant, checked, as a STREAM. Never raises.

    Deliberately written as independent passes that all run, rather than
    returning on the first problem. A submission with two defects should
    report two: the old scorer stopped at the first match in one check and a
    correctly-named entry ended up vouching for every later one.

    A generator, so the production reducer (`canonical.reduce_findings`)
    keeps counts and a bounded sample without ever holding the 268,000
    findings the maximum candidate can produce; `validate_candidate` below
    materialises the list for callers that want one.
    """
    yield from _check_events(candidate)
    yield from _check_lifecycle(candidate)
    yield from _check_accounts_open(candidate)


def validate_candidate(candidate: LedgerCandidate) -> list[DomainViolation]:
    return list(iter_violations(candidate))


def _check_events(candidate: LedgerCandidate):
    for event in candidate.events:
        where = f"{event.date} {event.entity or '(unnamed)'}"
        if len(event.postings) < 2:
            yield DomainViolation(
                "event.too_few_postings",
                f"{where}: {len(event.postings)} posting(s); an entry with one "
                f"leg records a movement with no counterparty",
            )
            continue
        total = sum((p.amount for p in event.postings), Decimal("0"))
        if total != 0:
            yield DomainViolation(
                "event.unbalanced",
                f"{where}: postings sum to {total}, not zero",
            )

# A check that was here and should not have been: "every event must name a
# counterparty the register knows".
#
# The correct solution failed it. The opening-balance entry carries the payee
# "Opening balance", which resolves to nobody -- correctly, because an opening
# balance has no counterparty. Neither does an internal transfer between two
# company accounts, nor a depreciation entry, nor most adjusting entries.
#
# The mistake was putting a *task* requirement into *universal* validation.
# That a resolving entry must name the party it settles with is a term of this
# task's contract, disclosed with the task; it is not a law of double-entry
# bookkeeping. Enforcing it here would have made an ordinary ledger invalid and
# every generated world unwinnable, and it would have been exactly the kind of
# undisclosed rule this architecture exists to remove -- reintroduced in the
# layer built to prevent them.
#
# Worth recording how it was caught, because it was cheap: the golden solution
# came back invalid. A validator that rejects the known-correct answer is
# wrong, whatever it says about everything else, and it is the one test that
# catches over-strictness for free.


def _check_lifecycle(candidate: LedgerCandidate):
    seen_open: dict[str, str] = {}
    seen_close: dict[str, str] = {}
    for item in candidate.lifecycle:
        table = seen_open if item.kind == "open" else seen_close
        if item.account in table:
            yield DomainViolation(
                f"lifecycle.duplicate_{item.kind}",
                f"{item.account} is {item.kind}ed twice "
                f"({table[item.account]} and {item.date})",
            )
        else:
            table[item.account] = item.date
    for account, closed_on in seen_close.items():
        opened_on = seen_open.get(account)
        if opened_on is None:
            yield DomainViolation(
                "lifecycle.close_without_open",
                f"{account} is closed on {closed_on} but never opened",
            )
        elif closed_on < opened_on:
            yield DomainViolation(
                "lifecycle.close_before_open",
                f"{account} closes {closed_on}, before it opens {opened_on}",
            )


def _check_accounts_open(candidate: LedgerCandidate):
    """Postings must land in accounts the chart declares, while they are open.

    The date comparison is a string comparison and that is safe rather than
    lazy: dates reach the candidate as ISO strings, where lexical and
    chronological order coincide. If the schema ever carries real dates this
    keeps working; if it ever carries some other format, it stops, which is
    the correct direction for a change nobody remembered to think about.
    """
    # The EARLIEST open and the EARLIEST close decide activity, as in
    # Beancount's sequential pass: a duplicate later `close` is a duplicate
    # finding, not a reopening. The first version built these maps
    # last-wins, so `close 11-05` + `close 12-31` hid the November
    # inactivity from us while Beancount reported it — an oracle
    # disagreement the agent could trigger at will (a quarantine button).
    opened: dict[str, str] = {}
    closed: dict[str, str] = {}
    for a in candidate.lifecycle:
        table = opened if a.kind == "open" else closed
        if a.account not in table or a.date < table[a.account]:
            table[a.account] = a.date
    for event in candidate.events:
        for posting in event.postings:
            opened_on = opened.get(posting.account)
            if opened_on is None:
                yield DomainViolation(
                    "posting.account_not_open",
                    f"{event.date}: {posting.account} is not declared in the chart",
                )
                continue
            if event.date < opened_on:
                yield DomainViolation(
                    "posting.before_account_opened",
                    f"{event.date}: {posting.account} does not open until {opened_on}",
                )
            closed_on = closed.get(posting.account)
            if closed_on is not None and event.date > closed_on:
                yield DomainViolation(
                    "posting.after_account_closed",
                    f"{event.date}: {posting.account} closed on {closed_on}",
                )
