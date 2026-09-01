"""LedgerCandidate: our semantic type, and the only thing scoring ever sees.

The old scorer compared source text and it compared parsed entries. Both are
artifacts, so there was no representation in the system in which "the same
reconciliation, differently spelled" could be stated — which meant every
question about spelling had to be answered by a rule about spelling. Nineteen
review rounds produced nineteen such rules, and the supply was not running out.

A candidate is what a submission *means*. Two submissions that mean the same
thing are the same candidate, byte-for-byte, whatever they looked like on the
way in. Everything that survives into these types is something a bookkeeper
could be wrong about; everything that does not is something they could only
have typed differently.

Three things are deliberately absent, and their absence is the design:

    narration wording   an entry saying "x" and one saying "Bank fee for
                        November" are the same event. What the old scorer was
                        reaching for through narration -- can a reader tell
                        what this was -- lives in `entity` and `source_ref`,
                        which are facts rather than prose.

    flags and tags      no flag or tag carries meaning in v1, so the canonical
                        renderer chooses them. Stamping every entry
                        "#unreviewed" was a real submission that needed its own
                        check; here it is not a thing that can be said.

    order and layout    events are held in a canonical order derived from their
                        content, so reordering, blank lines and line width are
                        not expressible rather than not permitted.

The types are frozen and hashable so that equality is structural and a
comparison cannot accidentally be identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


# The exact scale every amount is held at. Beancount will happily carry fifteen
# decimal places, and a submission once used them: amounts that render as the
# right number, compare unequal, and are not money. Money in this world has two
# decimal places, so the type says so rather than a check catching it later.
MONEY_SCALE = Decimal("0.01")


def money(value) -> Decimal:
    """Coerce to the canonical money scale, refusing anything that would round.

    Quantising silently would make 85.001 and 85.00 the same candidate, which
    is the lossy-mapping failure: a materially different ledger comparing
    equal. An amount that does not sit exactly on the scale is not a rounding
    problem to solve here, it is a protocol failure to report upstream.
    """
    d = Decimal(value)
    if d != d.quantize(MONEY_SCALE):
        raise ValueError(f"amount {d} is finer than the {MONEY_SCALE} scale")
    return d.quantize(MONEY_SCALE)


@dataclass(frozen=True, order=True)
class Posting:
    """One leg. Account and exact amount, and nothing else.

    Beancount's posting also carries a cost, a price, a flag and metadata.
    Cost and price are rejected at the boundary because they change valuation
    and v1 has no valuation model; flag and metadata are dropped because they
    do not change what happened.
    """

    account: str
    amount: Decimal

    def __post_init__(self):
        object.__setattr__(self, "amount", money(self.amount))


@dataclass(frozen=True)
class Event:
    """One economic event: what happened, when, with whom, and against what.

    Ordered by an explicit key, not by dataclass field comparison: `entity`
    and `source_ref` may be None, and comparing None with a string raised
    inside the candidate constructor on a perfectly valid ledger — one
    payee-less entry on the same date as a named one. A crash in the
    constructor is an evaluator failure on the agent's clock; an explicit key
    with a presence flag cannot raise.

    `postings` is a sorted tuple rather than a set. Counted, not set-based:
    two identical legs are two legs. The same reasoning applies one level up,
    where two genuinely identical events are two events and deleting one is
    damage even though nothing distinguishes them -- a set comparison made the
    second copy free to delete, which is ordinary in real books where the same
    rent is paid twice.

    `entity` is the counterparty resolved against the register, not the string
    the submission typed. `source_ref` is the identifier a real document
    carries -- a check or invoice number -- and is None where the real world
    has none. We never invent one: reproducing an identifier we made up is not
    bookkeeping, and failing to reproduce it is not a defect.
    """

    date: str
    entity: str | None
    source_ref: str | None
    postings: tuple[Posting, ...]

    def __post_init__(self):
        object.__setattr__(self, "postings", tuple(sorted(self.postings)))

    def sort_key(self) -> tuple:
        return (self.date, self.entity is not None, self.entity or "",
                self.source_ref is not None, self.source_ref or "", self.postings)

    def __lt__(self, other: "Event") -> bool:
        return self.sort_key() < other.sort_key()

    @property
    def balanced(self) -> bool:
        return sum((p.amount for p in self.postings), Decimal("0")) == 0

    @property
    def accounts(self) -> frozenset[str]:
        return frozenset(p.account for p in self.postings)


@dataclass(frozen=True, order=True)
class AccountLifecycle:
    """An account opening or closing.

    Lifecycle is semantics, not bookkeeping decoration. A submission once
    reconciled the month correctly and then closed all twelve accounts, dated
    the day after period end: books that balance and a business that no longer
    exists. Nothing in the old reward looked at directives other than
    transactions, so it scored full marks.
    """

    kind: str  # "open" | "close"
    date: str
    account: str
    currencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class LedgerCandidate:
    """A whole submission, as meaning.

    Equality is structural and total: two candidates are equal exactly when
    they say the same thing. That is the property the entire boundary exists to
    provide, and it is what lets a presentation-equivalence test be written as
    `normalise(a) == normalise(b)` rather than as a list of tricks that must
    not work.
    """

    operating_currency: str
    lifecycle: tuple[AccountLifecycle, ...]
    events: tuple[Event, ...]

    def __post_init__(self):
        object.__setattr__(self, "lifecycle", tuple(sorted(self.lifecycle)))
        object.__setattr__(self, "events", tuple(sorted(self.events, key=Event.sort_key)))

    @property
    def balances(self) -> dict[str, Decimal]:
        """Account balances implied by the events.

        Derived, never stored. The task file currently carries a hand-authored
        expected balance of 51045.00 for the checking account, a number the
        ledger already implies. Storing it makes it authoritative, so a
        generator that computes events correctly and balances incorrectly
        produces a task where the right answer is marked wrong and the verifier
        agrees with the wrong number -- because the wrong number is the spec.
        """
        out: dict[str, Decimal] = {}
        for event in self.events:
            for posting in event.postings:
                out[posting.account] = out.get(posting.account, Decimal("0")) + posting.amount
        return out

    @property
    def open_accounts(self) -> frozenset[str]:
        opened = {a.account for a in self.lifecycle if a.kind == "open"}
        closed = {a.account for a in self.lifecycle if a.kind == "close"}
        return frozenset(opened - closed)


# --------------------------------------------------------------------------
# the structural record: what was parsed, as it was written
# --------------------------------------------------------------------------

# `LedgerCandidate` above is meaning: order erased, narration erased, payee
# resolved. That is the right object to score and the wrong object to hold
# provenance over, because it deliberately forgets things a certificate must
# keep. `SafeParsedSubmission` is the closed parsed submission as written —
# directives in parser order (date, then source position: the pinned parser
# sorts, so source order across dates is not observable and is not claimed),
# postings in authored order, payee and narration under the string policy,
# flags, tags and links retained — and
# `candidate_digest` is its identity. Dropped fields live here, not in the
# candidate; rejected fields live nowhere. Unequal structural identities do
# not imply unequal accounting; that question belongs to the semantic
# fingerprint.

_MINT = object()   # constructor token: only the parse boundary builds these


@dataclass(frozen=True)
class ParsedPosting:
    account: str
    amount: Decimal          # bounded; identity by value (85 == 85.00)
    currency: str
    flag: str | None = None  # dropped from the candidate, retained here: reward-visible

    def as_canonical(self) -> dict:
        return {"account": self.account, "amount": self.amount, "currency": self.currency, "flag": self.flag}


@dataclass(frozen=True)
class ParsedTransaction:
    index: int               # position in parser order (date, then source position)
    date: str
    flag: str
    payee: str | None        # NFC, as written; None when absent
    narration: str           # NFC; "" when written empty
    tags: tuple[str, ...]    # a set in Beancount's semantics: sorted, unique
    links: tuple[str, ...]
    source_refs: tuple[tuple[str, str], ...]   # whitelisted (key, value), sorted
    postings: tuple[ParsedPosting, ...]        # authored order

    def as_canonical(self) -> dict:
        return {
            "kind": "transaction", "index": self.index, "date": self.date, "flag": self.flag,
            "payee": self.payee, "narration": self.narration,
            "tags": list(self.tags), "links": list(self.links),
            "source_refs": [list(pair) for pair in self.source_refs],
            "postings": [p.as_canonical() for p in self.postings],
        }


@dataclass(frozen=True)
class ParsedLifecycle:
    index: int
    kind: str                # "open" | "close"
    date: str
    account: str
    currencies: tuple[str, ...]

    def as_canonical(self) -> dict:
        return {"kind": self.kind, "index": self.index, "date": self.date,
                "account": self.account, "currencies": list(self.currencies)}


@dataclass(frozen=True)
class SafeParsedSubmission:
    """The closed parsed submission. Constructed only inside the boundary."""

    operating_currency: str
    title: str | None
    directives: tuple                          # ParsedLifecycle | ParsedTransaction, source order
    _mint: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self._mint is not _MINT:
            raise TypeError("SafeParsedSubmission is constructed only by the parse boundary")
        for d in self.directives:
            if not isinstance(d, (ParsedLifecycle, ParsedTransaction)):
                raise TypeError(f"not a parsed directive: {type(d).__name__}")
        object.__setattr__(self, "directives", tuple(self.directives))

    def as_canonical(self) -> dict:
        from .canonical import CANDIDATE_SCHEMA_VERSION

        return {
            "schema": CANDIDATE_SCHEMA_VERSION,
            "currency": self.operating_currency,
            "title": self.title,
            "directives": [d.as_canonical() for d in self.directives],
        }
