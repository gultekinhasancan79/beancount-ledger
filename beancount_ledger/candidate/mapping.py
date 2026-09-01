"""The AST mapping table: what every Beancount field means to us, if anything.

This is the piece that makes "semantic trust boundary" a thing rather than a
name for Beancount's behaviour. Beancount is a syntax front end. Its parser
output is a large, version-dependent structure with degrees of freedom we did
not choose and do not all model. Treating that structure as our semantic type
means inheriting every liberty it takes.

So: every field of every directive the parser can produce is classified here,
exactly once, into one of four dispositions. A field with no entry is a build
failure, not a default. That is the whole point — the scorer this replaces
accumulated nineteen hand-written rules because it had no classification and
had to answer each new degree of freedom locally, one attack at a time. The
list of presentation channels is unbounded; the list of AST fields is not.

The four dispositions:

    MAPPED          carries meaning; becomes part of LedgerCandidate
    CANONICALISED   alternative spellings of one meaning; normalised on entry
    DROPPED         carries no meaning here; discarded at the boundary
    REJECTED        would carry meaning we do not model; fails closed

DROPPED and REJECTED are not the same and the difference is load-bearing. A
dropped field is noise: a tag, a narration wording, a flag. Discarding it is
correct and the submission is scored as though it were absent. A rejected field
is something we cannot safely ignore: a cost lot changes valuation, an include
pulls in entries we never see. Silently dropping those would let a materially
different ledger compare equal — the failure mode where a sanitiser becomes a
forger. Rejection is epistemic. It does not say the books are wrong; it says no
supported candidate could be obtained.

Everything DROPPED here was, in the previous design, a rule. Tag stamping, flag
rewriting, narration blanking, comment injection and payee casing each cost a
review round and a hand-written check. Under a boundary that admits only the
mapped fields, they are not attacks that are caught. They are not expressible.
"""

from __future__ import annotations

from enum import Enum


class Disposition(Enum):
    MAPPED = "mapped"
    CANONICALISED = "canonicalised"
    DROPPED = "dropped"
    REJECTED = "rejected"


class Rule:
    """One classification, with the reason attached to it rather than to a
    comment somewhere else.

    `reason` is an identifier, not prose, because it ends up in the diagnostic
    an agent sees and in the class label a perimeter test asserts against. A
    rejection that cannot name itself is a rejection nobody can act on.
    """

    __slots__ = ("disposition", "reason", "note")

    def __init__(self, disposition: Disposition, reason: str, note: str = ""):
        self.disposition = disposition
        self.reason = reason
        self.note = note

    def __repr__(self) -> str:
        return f"Rule({self.disposition.value}, {self.reason!r})"


def mapped(reason, note=""):
    return Rule(Disposition.MAPPED, reason, note)


def canonicalised(reason, note=""):
    return Rule(Disposition.CANONICALISED, reason, note)


def dropped(reason, note=""):
    return Rule(Disposition.DROPPED, reason, note)


def rejected(reason, note=""):
    return Rule(Disposition.REJECTED, reason, note)


# --------------------------------------------------------------------------
# directive-level admission
# --------------------------------------------------------------------------

# v1 accepts three directive types. That is deliberately small. Every accepted
# construct needs a model, a canonical rendering, and a preservation rule, and
# the two tasks in the first slice — bank reconciliation and period close —
# need exactly these three.
#
# `Balance` is the closest call. It is ordinary bookkeeping and beancount
# supports it well, but it is an assertion rather than an economic event, so
# accepting it means modelling assertion dates and tolerances. The source
# ledger does not use it and neither task needs it, so it is rejected in v1
# and can be admitted later by adding a model rather than by relaxing a check.
#
# `Note` is rejected as *input* for a different reason. A free-form note would
# put arbitrary agent-authored prose back inside the candidate, which is the
# channel the whole boundary exists to close. Canonical notes still appear in
# rendered output — they are emitted from typed facts in the event graph — but
# they are written by us and never read back as semantics.

DIRECTIVES = {
    "Open": mapped("directive.open", "account lifecycle"),
    "Close": mapped("directive.close", "account lifecycle"),
    "Transaction": mapped("directive.transaction", "the economic events"),

    "Balance": rejected(
        "directive.balance.unmodelled",
        "an assertion, not an event; needs date and tolerance semantics that "
        "v1 does not have and neither task requires",
    ),
    "Note": rejected(
        "directive.note.free_prose",
        "would readmit arbitrary agent-authored prose into the candidate; "
        "canonical notes are rendered from typed facts, never parsed back in",
    ),
    "Pad": rejected(
        "directive.pad.manufactures_entries",
        "creates entries as a booking side effect, which is a mechanism we do "
        "not model and an agent could use to reach balances without posting",
    ),
    "Price": rejected("directive.price.unmodelled", "no valuation model in v1"),
    "Commodity": rejected("directive.commodity.unmodelled", "single currency in v1"),
    "Event": rejected("directive.event.unmodelled", "no non-financial event model"),
    "Query": rejected("directive.query.not_data", "an embedded query, not a fact"),
    "Document": rejected("directive.document.external_ref", "points outside the world"),
    "Custom": rejected("directive.custom.unbounded", "arbitrary typed payload"),
}


# --------------------------------------------------------------------------
# field-level classification
# --------------------------------------------------------------------------

# Every field of every directive above, accepted or not. Fields of a rejected
# directive are still classified: the directive never reaches field mapping in
# production, but the coverage test walks the whole parser surface, and an
# unclassified field is exactly the blind spot this table exists to remove.

_SOURCE_META = mapped(
    "meta.source_reference",
    "only the keys we render ourselves for source references — check and "
    "invoice numbers a real document actually carries. Everything else in "
    "meta, including the parser's own filename and lineno, is position or "
    "annotation and is dropped.",
)

FIELDS = {
    "Open": {
        "meta": _SOURCE_META,
        "date": mapped("open.date"),
        "account": mapped("open.account"),
        "currencies": mapped(
            "open.currencies",
            "validated against the contract's operating currency; a second "
            "currency is a rejection, not a silent difference",
        ),
        "booking": rejected(
            "open.booking.unmodelled",
            "booking methods select lots, which v1 has no model for",
        ),
    },
    "Close": {
        "meta": _SOURCE_META,
        "date": mapped("close.date"),
        "account": mapped("close.account"),
    },
    "Transaction": {
        "meta": _SOURCE_META,
        "date": mapped("txn.date"),
        "postings": mapped("txn.postings", "the multiset of (account, amount)"),
        "payee": canonicalised(
            "txn.payee.entity_resolution",
            "resolved to an entity in the counterparty register and rendered "
            "from the register afterwards. Byte-identical casing was a scored "
            "rule for nineteen rounds; it is presentation wearing the clothes "
            "of semantics, and it trained transcription rather than judgement.",
        ),
        "flag": dropped(
            "txn.flag.renderer_owned",
            "the canonical renderer chooses it. Scoring the agent's spelling "
            "of a flag it was never told about was one of the four undisclosed "
            "rules the M0 review found.",
        ),
        "narration": dropped(
            "txn.narration.free_prose",
            "the entity and the source reference carry what the narration was "
            "being asked to prove; the wording itself proves nothing, and "
            "every check that read it lost to a sentence that denied itself",
        ),
        "tags": dropped("txn.tags.no_semantics", "no tag carries meaning in v1"),
        "links": dropped("txn.links.no_semantics", "no link carries meaning in v1"),
    },
    "Balance": {
        "meta": _SOURCE_META,
        "date": rejected("balance.unmodelled"),
        "account": rejected("balance.unmodelled"),
        "amount": rejected("balance.unmodelled"),
        "tolerance": rejected("balance.unmodelled"),
        "diff_amount": rejected("balance.unmodelled"),
    },
    "Note": {
        "meta": _SOURCE_META,
        "date": rejected("note.free_prose"),
        "account": rejected("note.free_prose"),
        "comment": rejected("note.free_prose"),
        "tags": rejected("note.free_prose"),
        "links": rejected("note.free_prose"),
    },
    "Pad": {
        "meta": _SOURCE_META,
        "date": rejected("pad.manufactures_entries"),
        "account": rejected("pad.manufactures_entries"),
        "source_account": rejected("pad.manufactures_entries"),
    },
    "Price": {
        "meta": _SOURCE_META,
        "date": rejected("price.unmodelled"),
        "currency": rejected("price.unmodelled"),
        "amount": rejected("price.unmodelled"),
    },
    "Commodity": {
        "meta": _SOURCE_META,
        "date": rejected("commodity.unmodelled"),
        "currency": rejected("commodity.unmodelled"),
    },
    "Event": {
        "meta": _SOURCE_META,
        "date": rejected("event.unmodelled"),
        "type": rejected("event.unmodelled"),
        "description": rejected("event.unmodelled"),
    },
    "Query": {
        "meta": _SOURCE_META,
        "date": rejected("query.not_data"),
        "name": rejected("query.not_data"),
        "query_string": rejected("query.not_data"),
    },
    "Document": {
        "meta": _SOURCE_META,
        "date": rejected("document.external_ref"),
        "account": rejected("document.external_ref"),
        "filename": rejected("document.external_ref"),
        "tags": rejected("document.external_ref"),
        "links": rejected("document.external_ref"),
    },
    "Custom": {
        "meta": _SOURCE_META,
        "date": rejected("custom.unbounded"),
        "type": rejected("custom.unbounded"),
        "values": rejected("custom.unbounded"),
    },
}

# Postings are not a directive but carry the fields that decide what a
# transaction means, so they are classified the same way.
POSTING_FIELDS = {
    "account": mapped("posting.account"),
    "units": mapped(
        "posting.units",
        "an explicit, exact Decimal. Arithmetic that evaluates exactly to the "
        "same value is equivalent syntax and is accepted; elision is rejected "
        "in v1 because resolving it needs a booking model we do not have and "
        "the agent can always write the number.",
    ),
    "cost": rejected("posting.cost.unmodelled", "lots change valuation"),
    "price": rejected("posting.price.unmodelled", "no valuation model in v1"),
    "flag": dropped("posting.flag.renderer_owned"),
    "meta": _SOURCE_META,
}


# --------------------------------------------------------------------------
# options
# --------------------------------------------------------------------------

# Options split three ways rather than two. `operating_currency` is contract
# semantics and is validated against the contract. Display options are
# contract-owned presentation: whatever the submission says is ignored and the
# contract's value is rendered. Everything else is rejected, because an option
# we do not model may change how the parser itself behaves.

OPTIONS = {
    "operating_currency": mapped(
        "option.operating_currency",
        "validated against the task contract, not read from the submission",
    ),
    "title": dropped("option.title.contract_owned", "rendered from the contract"),
}

OPTION_DEFAULT = rejected(
    "option.unmodelled",
    "an unrecognised option may change parser behaviour; rewriting the ledger "
    "header and currency was a real submission, and it has to fail closed "
    "rather than be ignored",
)


# --------------------------------------------------------------------------
# four dimensions per field
# --------------------------------------------------------------------------

# The tables above say what a field means to the ACCOUNTING candidate. That
# is one dimension of four, and "carries no meaning" in that dimension was
# being read as "carries no meaning" — narration demonstrably carries REWARD
# meaning through the preservation rule (changing a pre-existing entry's
# narration is an alteration) while carrying no debit/credit meaning. So each
# field is classified on every axis:
#
#     provenance   retained in the structural record (`SafeParsedSubmission`)?
#     accounting   the disposition above, for `LedgerCandidate`
#     reward       observed by the concrete bank-reconciliation scorer?
#                  `observed` through the candidate; `text_only` through the
#                  raw text (which the live scorer still reads); `ignored`
#     render       who decides how it appears in the canonical output
#
# The reward column is contract-specific and is verified against the real
# scorer by a field-mutation witness: a field marked observed must move the
# score when mutated on a pre-existing entry; a field marked ignored must not.
# It is what makes a reward-input projection — and any future cache key —
# auditable rather than remembered.
FIELD_DIMENSIONS = {
    "txn.date":            {"provenance": "retained", "accounting": "mapped",        "reward": "observed",  "render": "rendered"},
    "txn.flag":            {"provenance": "retained", "accounting": "dropped",       "reward": "observed",  "render": "renderer_owned"},
    "txn.payee":           {"provenance": "retained", "accounting": "canonicalised", "reward": "observed",  "render": "rendered"},
    "txn.narration":       {"provenance": "retained", "accounting": "dropped",       "reward": "observed",  "render": "renderer_owned"},
    "txn.tags":            {"provenance": "retained", "accounting": "dropped",       "reward": "observed",  "render": "renderer_owned"},
    "txn.links":           {"provenance": "retained", "accounting": "dropped",       "reward": "observed",  "render": "renderer_owned"},
    "txn.meta.source_ref": {"provenance": "retained", "accounting": "mapped",        "reward": "observed",  "render": "rendered"},
    "txn.meta.other":      {"provenance": "absent",   "accounting": "rejected",      "reward": "observed",  "render": "absent"},
    "posting.account":     {"provenance": "retained", "accounting": "mapped",        "reward": "observed",  "render": "rendered"},
    "posting.units":       {"provenance": "retained", "accounting": "mapped",        "reward": "observed",  "render": "rendered"},
    "posting.order":       {"provenance": "retained", "accounting": "dropped",       "reward": "ignored",   "render": "renderer_owned"},
    # Retained structurally BECAUSE it is reward-visible: the first table had
    # it absent, and the metamorphic witness showed a posting-flag change
    # moving the score with the candidate identity unmoved — a reward-visible
    # field the conservative key could not see.
    "posting.flag":        {"provenance": "retained", "accounting": "dropped",       "reward": "observed",  "render": "renderer_owned"},
    "posting.cost":        {"provenance": "absent",   "accounting": "rejected",      "reward": "observed",  "render": "absent"},
    "posting.price":       {"provenance": "absent",   "accounting": "rejected",      "reward": "observed",  "render": "absent"},
    "txn.order.same_date": {"provenance": "retained", "accounting": "dropped",       "reward": "ignored",   "render": "renderer_owned"},
    "txn.multiplicity":    {"provenance": "retained", "accounting": "mapped",        "reward": "observed",  "render": "rendered"},
    "open.date":           {"provenance": "retained", "accounting": "mapped",        "reward": "observed",  "render": "rendered"},
    "open.account":        {"provenance": "retained", "accounting": "mapped",        "reward": "observed",  "render": "rendered"},
    "open.currencies":     {"provenance": "retained", "accounting": "mapped",        "reward": "observed",  "render": "rendered"},
    "option.operating_currency": {"provenance": "retained", "accounting": "mapped",  "reward": "observed",  "render": "rendered"},
    "option.title":        {"provenance": "retained", "accounting": "dropped",       "reward": "observed",  "render": "renderer_owned"},
    # Channels that exist only in the text. The live scorer reads them
    # (comment prose, blank-line padding, arithmetic spellings), which is why
    # a score cache today must bind the source digest and not only the
    # candidate identity. Parse-once retires them.
    "text.comments":       {"provenance": "absent",   "accounting": "absent",        "reward": "text_only", "render": "absent"},
    "text.layout":         {"provenance": "absent",   "accounting": "absent",        "reward": "text_only", "render": "absent"},
    "text.amount_spelling": {"provenance": "absent",  "accounting": "absent",        "reward": "text_only", "render": "absent"},
    "text.trailing_whitespace": {"provenance": "absent", "accounting": "absent",     "reward": "ignored",   "render": "absent"},
}

# Reward disposition is CONTEXTUAL: the same field is observed on a
# pre-existing entry (the preservation rule hashes every field of it) and
# ignored on the agent's repair of a planted item (matched by date, payee and
# exact postings; its narration, tags, flag are not read). So the reward
# column above is the pre-existing role, and this table is the authority the
# scorer contract digests: (entry role, field) -> observed | ignored. The
# mutation matrix in `test_canonical` is generated from it and exercised
# against the real scorer per role, and a source-level audit of the scorer
# refuses any entry-field read that no role declares.
REWARD_DEPENDENCIES = {
    **{("pre_existing", field): dims["reward"] for field, dims in FIELD_DIMENSIONS.items()},
    ("planted_repair", "txn.date"): "observed",
    ("planted_repair", "txn.payee"): "observed",
    ("planted_repair", "txn.narration"): "ignored",
    # Declared ignored at first; the witness showed the raw scorer treating a
    # `!`-flagged repair as unresolved (the old "pending flag" rule). That is
    # the RAW scorer's contract and it is recorded as such; the candidate
    # scorer retires it — flags are renderer-owned there, so `!` and `*`
    # are one candidate and a pending repair is not a thing that can be said.
    ("planted_repair", "txn.flag"): "observed",
    ("planted_repair", "txn.tags"): "ignored",
    ("planted_repair", "txn.links"): "ignored",
    ("planted_repair", "txn.meta.source_ref"): "ignored",
    ("planted_repair", "posting.account"): "observed",
    ("planted_repair", "posting.units"): "observed",
    ("planted_repair", "posting.order"): "ignored",
    ("planted_repair", "txn.multiplicity"): "observed",
}
