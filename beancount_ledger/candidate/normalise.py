"""The trust boundary: submitted bytes in, LedgerCandidate or refusal out.

    bytes -> resource envelope -> pinned parser -> AST consumption
          -> LedgerCandidate -> (scoring compares candidates)

Two things make this different from the checks it replaces.

**Nothing crosses that is not classified.** Every field of every parsed
directive is looked up in the mapping table and marked exactly once: mapped,
canonicalised, dropped, or rejected. The default branch refuses. So a construct
nobody anticipated does not slip through as noise -- it fails closed, and the
coverage test makes an unclassified field a build failure rather than a
runtime surprise.

**A refusal is not a score.** Returning a bookkeeping zero for a submission we
could not interpret would claim the books are wrong when what happened is that
no supported candidate was obtained. Once a construct is outside the model,
nothing here knows whether it was decorative or changed the valuation. The two
outcomes are different types, and the caller has to handle both.

The nineteen presentation attacks the old scorer collected -- comment
injection, tag stamping, mocking case, blank-line padding, arithmetic amounts,
fifty-thousand-character lines -- are not caught here. Most of them are not
expressible: the fields they lived in are dropped before a candidate exists, so
the hostile and the innocent version of the same submission are the same
object. That is the difference between a check that must anticipate an attack
and a type that has nowhere to put it.
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from beancount.core import data
from beancount.core.number import MISSING

from .mapping import (
    DIRECTIVES,
    FIELDS,
    OPTION_DEFAULT,
    OPTIONS,
    POSTING_FIELDS,
    Disposition,
)
from .canonical import (
    ACCOUNT_GRAMMAR,
    CURRENCY_GRAMMAR,
    DATE_GRAMMAR,
    FLAG_GRAMMAR,
    MAX_DIGIT_RUN,
    REF_MAX_CODEPOINTS,
    TAG_GRAMMAR,
    FindingSummary,
    LexicalError,
    NumberOutOfBounds,
    StringPolicyViolation,
    bounded_decimal,
    candidate_digest,
    canonical_identifier,
    canonical_text,
    finding_sample,
    reduce_findings,
    longest_numeric_digit_run,
    oracle_disagreement,
    oracle_unmapped,
    semantic_fingerprint,
    summarise_findings,
)
from .schema import (
    _MINT,
    AccountLifecycle,
    Event,
    LedgerCandidate,
    ParsedLifecycle,
    ParsedPosting,
    ParsedTransaction,
    Posting,
    SafeParsedSubmission,
    money,
)
from .validate import DomainViolation, iter_violations, validate_candidate


# --------------------------------------------------------------------------
# resource envelope
# --------------------------------------------------------------------------

# Bounds, not heuristics. Each one exists because a submission went past it:
# ten thousand lines of which sixty-eight carried anything, a single line of
# fifty thousand spaces, amounts padded to fifteen decimal places. Under the
# old design each needed its own detector and its own penalty, and a fix aimed
# at one shape invited the same attack in another -- padding by height was
# blocked, so the next one padded by width.
#
# Here they are protocol limits. Exceeding one is a refusal with a reason, not
# a deduction from a bookkeeping score.
MAX_BYTES = 512 * 1024
MAX_LINES = 5_000
MAX_LINE_LENGTH = 500
MAX_EVENTS = 2_000
MAX_POSTINGS_PER_EVENT = 64
MAX_ORACLE_DIAGNOSTICS = 500       # the oracle record is a bounded, deep-frozen tuple
MAX_ORACLE_CHARS = 300


# --------------------------------------------------------------------------
# lexical pre-gate
# --------------------------------------------------------------------------

# The lexical gate and the non-importing parse live in `safe_parse`, one level
# up, and both this boundary and the scorer import them from there.
#
# They were implemented here first and `reward.py` kept calling
# `loader.load_string` — so the hole was closed in the layer nothing called
# while the live scoring path still had it. A security property reimplemented
# per call site is one that will be missing from the next call site.
from ..safe_parse import (  # noqa: E402
    SIDE_EFFECTING_CONTROLS,
    check_controls,
    find_elided,
    safe_parse,
)


@dataclass
class ProtocolFailure:
    """No supported candidate could be obtained.

    Deliberately not a score. The semantic components are absent rather than
    zeroed, because they were never evaluated -- populating them with zeros
    would erase the distinction between "the books are wrong" and "we could not
    read the books", which are different facts about different parties. The
    episode reward is zero either way; the diagnosis is not.

    A high rate of these across plausible submissions is a health metric on the
    environment, not on the agent: it means the accepted subset is too narrow
    or too poorly disclosed.
    """

    reason: str
    detail: str = ""
    trace: "ConsumptionTrace | None" = None

    @property
    def ok(self) -> bool:
        return False

    def __str__(self) -> str:
        return f"{self.reason}: {self.detail}" if self.detail else self.reason


@dataclass
class EvaluationFailure:
    """Our bug, not theirs.

    A third result, and the one easiest to get wrong in the direction that
    matters. When a third-party validator or our own code raises on a
    submission that parsed and mapped cleanly, that is an evaluator defect. It
    is not evidence the agent violated anything.

    Reporting it as a protocol failure would do two bad things quietly: it
    would convert a bug in our code into a zero, which is negative training
    data the agent cannot learn from because it did nothing wrong; and it would
    inflate the protocol-rejection rate, which is the metric that tells us
    whether our accepted subset is too narrow.

    It also forecloses a perverse response. If a submission inside the declared
    subset finds a crash in our validator, that is still our defect even though
    an adversary found it. The fix is to contain it, keep the reproducer, and
    repair the validator -- not to redefine the input as malformed so the
    numbers look clean.

    The episode should be excluded from benchmark reporting rather than scored.
    """

    stage: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return False

    def __str__(self) -> str:
        return f"evaluator failed at {self.stage}: {self.detail}"


# `DomainInvalid` lived here: a candidate plus its violations, as a third
# result type. Its job — "we read the submission and the bookkeeping is
# malformed" is a fact about the ledger, not about whether we speak the same
# language — is carried by `Accepted` now, which is safe-and-representable
# with named findings the task policy prices. The old projection is gone in
# the same commit as the raw scorer, so no caller can route around the
# committed state through a legacy wrapper.


@dataclass
class ConsumptionTrace:
    """Where every part of the parsed input went.

    The mapping table is a claim; this is the enforcement. Each AST path is
    recorded exactly once against the disposition that consumed it, so the
    question "did we forget a field" becomes answerable after the fact rather
    than something fuzzing has to stumble into.

    Metadata is the one place the property weakens honestly. `meta` is an open
    dict, not a fixed field list, so "every key" is not a finite set the way
    fields are. Keys are therefore handled as a whitelisted keyspace with a
    fail-closed default: recognised source references are consumed, the
    parser's own position keys are dropped by name, and anything else is a
    refusal. That is a policy rather than an exhaustiveness proof, and it is
    marked as one below so nobody later mistakes it for one.
    """

    mapped: list[str] = field(default_factory=list)
    canonicalised: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

    def record(self, disposition: Disposition, path: str) -> None:
        getattr(self, disposition.value).append(path)

    @property
    def paths(self) -> list[str]:
        return self.mapped + self.canonicalised + self.dropped + self.rejected


# Metadata keys the parser attaches itself. They are position, not content.
# RESERVED: an author may not write them. Dropping them by name would be an
# origin boundary only if the name proved the origin, and it does not — an
# authored `filename:` on a pre-existing entry could be changed or removed
# without entering the preservation fingerprint. So the SOURCE is scanned
# for a metadata line under a reserved name (token-aware: outside strings
# and comments) and the submission is protocol-rejected, before the parser
# can conflate the two.
POSITION_META = frozenset({"filename", "lineno", "__tolerances__", "__automatic__", "tolerances"})


# Beancount's KEY token, exactly: at the start of a line (indented or not —
# the LEXER does not care, the parser refuses a top-level key later), a
# lowercase letter, then letters, digits, hyphen or underscore, then the
# colon with NO whitespace before it and anything at all after it.
# `Filename:`, `filenäme:`, `__automatic__:` and `filename :` are not keys
# to Beancount's lexer (they are syntax errors) and are not flagged here;
# the parser refuses them on its own and the boundary reports `parse.errors`.
_META_KEY = re.compile(r"^[ \t]*([a-z][a-zA-Z0-9\-_]*):")


def reserved_meta_line(text: str) -> int | None:
    """The first line that authors a reserved metadata key, or None.

    Lexical parity with Beancount, witnessed by the differential test in
    `test_committed` against Beancount's own lexer: a line is a metadata
    line only where that lexer would produce a KEY token — the key grammar
    above at the start of the line, OUTSIDE any quoted string, including a
    string that began on an earlier line — and only the key token is
    examined.
    Comments end at the line. The first version tested each line in
    isolation, which flagged `filename:` inside a multi-line narration
    that Beancount reads as text (and the string policy then refuses for
    its newline, under its own name)."""
    in_string = False
    for number, line in enumerate(text.split("\n"), 1):
        if not in_string:
            match = _META_KEY.match(line)
            if match and match.group(1) in POSITION_META:
                return number
        i = 0
        while i < len(line):
            ch = line[i]
            if in_string:
                if ch == "\\":
                    i += 1                          # an escaped character cannot close the string
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == ";":
                break                               # a comment runs to the end of the line
            i += 1
    return None

# Metadata keys we render ourselves, carrying identifiers a real document has.
SOURCE_META = frozenset({"check", "invoice", "ref"})


# --------------------------------------------------------------------------
# the boundary
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Accepted:
    """Safe and representable — not "deserves a perfect domain score".

    The structural record and the meaning, with the identity of each, plus
    every named domain violation found in the candidate. A ledger with an
    unbalanced entry, a posting to an undeclared account or a duplicate
    `open` is still read, still closed, still identified; what each violation
    costs is the task contract's decision (`policy.apply_policy`), and some
    of them leave other components perfectly computable. Only a syntax,
    safety or unsupported-shape failure is a protocol rejection; only a
    crash in our own code is an evaluator failure. Nothing here retains a
    parser object.
    """

    submission: SafeParsedSubmission
    candidate: LedgerCandidate
    candidate_digest: str
    semantic_fingerprint: str
    # The ONE reward authority, in two views: `finding_summary` is exact
    # (saturated) counts by code over the WHOLE candidate and is what
    # `policy.apply_policy` consumes; `domain_findings` is a bounded
    # diagnostic SAMPLE (at most MAX_FINDING_SAMPLE, in validator order) for
    # reading. A capped list fed to the policy was an attack surface.
    finding_summary: "FindingSummary | None" = None
    domain_findings: tuple = ()
    # Beancount's own validation over the same entries: evaluator evidence
    # for the differential oracle, never a score input. Where an overlap
    # category is reported by the oracle and not by the normative validator,
    # `parse_once` returns an evaluator failure, not an unreviewed penalty.
    oracle_diagnostics: tuple = ()
    oracle_unmapped: int = 0     # telemetry: oracle lines outside the overlap taxonomy

    @property
    def ok(self) -> bool:
        return True

    @property
    def domain_valid(self) -> bool:
        return self.finding_summary is None or self.finding_summary.total == 0


def parse_once(text: str, *, entity_resolver=None):
    """The boundary, once: text in; `Accepted`, `ProtocolFailure` or
    `EvaluationFailure` out.

    `entity_resolver` maps a submitted payee string to a stable entity ID. It
    is injected rather than imported so that the register is the task's, not a
    global: the counterparty register is an observation, and resolving against
    a register the agent cannot see would put an undisclosed rule back into the
    scorer through the back door. With no resolver, the payee is carried
    through as written and comparison falls back to string identity.

    Structural and semantic records are built in the same pass over the same
    parsed entries, so there is exactly one reading of the source: the
    `SafeParsedSubmission` (as written, under the string and number policy)
    and the `LedgerCandidate` (as meant) cannot disagree about what was
    parsed, and neither retains a parser object.
    """
    envelope = _check_envelope(text)
    if envelope is not None:
        return envelope

    # Parsing goes through the package's one door.
    #
    # This used to import `beancount.parser` directly, which was safe but was
    # the wrong shape: the rule that matters is "one module turns text into
    # entries", not "one module is forbidden from using the dangerous API". A
    # second call site importing the parser itself is how the property erodes
    # — and it is what let `reward.py` keep the loader while the boundary was
    # migrated. `safe_parse` runs the lexical gate, the non-importing parse,
    # the elision check and validation, in that order, once.
    entries, parse_errors, validation_errors, options_map = safe_parse(text)

    trace = ConsumptionTrace()

    # Syntax and unsupported-construct errors are protocol: no trustworthy
    # candidate exists, because the source was not understood. Any non-empty
    # list is fatal, including a type nobody has seen -- no allowlist of fatal
    # subclasses, which is exactly the bug the old loader had. It discarded
    # ValidationErrors on the reasoning that the interesting ones were covered
    # elsewhere, so twelve duplicated `open` directives produced twelve
    # validation errors and the reward saw a clean ledger.
    if parse_errors:
        first = parse_errors[0]
        reason = first.split(":", 1)[0] if ":" in first else "parse.errors"
        if reason.startswith("control.") or reason.startswith("posting."):
            return ProtocolFailure(reason, first.split(":", 1)[1].strip(), trace)
        return ProtocolFailure(
            "parse.errors", f"{len(parse_errors)} error(s); first: {first}", trace
        )

    # Beancount's own validation findings arrive from `safe_parse`. They are
    # the differential ORACLE — evaluator evidence, never a score input. Our
    # own invariants, checked after the candidate exists in
    # `validate.validate_candidate`, are the one reward authority.
    oracle: list[str] = [str(v)[:MAX_ORACLE_CHARS] for v in validation_errors[:MAX_ORACLE_DIAGNOSTICS]]
    violations: list[str] = []

    options = _consume_options(options_map, trace)
    if isinstance(options, ProtocolFailure):
        return options
    currency, title = options

    lifecycle: list[AccountLifecycle] = []
    events: list[Event] = []
    structural: list = []

    for index, entry in enumerate(entries):
        name = type(entry).__name__
        rule = DIRECTIVES.get(name)
        if rule is None:
            return ProtocolFailure(
                "directive.unclassified",
                f"{name} is not in the mapping table; the parser produced a "
                f"directive this boundary has never classified",
                trace,
            )
        if rule.disposition is Disposition.REJECTED:
            trace.record(Disposition.REJECTED, f"[{index}].{name}")
            return ProtocolFailure(rule.reason, rule.note, trace)

        try:
            built = _consume_directive(
                entry, index, currency, trace, entity_resolver, violations, structural
            )
        except (StringPolicyViolation, NumberOutOfBounds) as exc:
            # Policy refusals are protocol: the source was read and a value
            # in it is outside the declared domain. Named by their reason.
            trace.record(Disposition.REJECTED, f"[{index}].{name}")
            return ProtocolFailure(exc.reason, exc.detail, trace)
        if isinstance(built, ProtocolFailure):
            return built
        if isinstance(built, AccountLifecycle):
            lifecycle.append(built)
        elif isinstance(built, Event):
            events.append(built)

    if len(events) > MAX_EVENTS:
        return ProtocolFailure("envelope.events", f"{len(events)} > {MAX_EVENTS}", trace)

    candidate = LedgerCandidate(
        operating_currency=currency,
        lifecycle=tuple(lifecycle),
        events=tuple(events),
    )

    # The structural record and both identities. Built here, in the same
    # pass, from the same consumed values; the constructor token keeps any
    # other code from minting one.
    try:
        submission = SafeParsedSubmission(currency, title, tuple(structural), _mint=_MINT)
        structural_id = candidate_digest(submission)
        semantic_id = semantic_fingerprint(candidate)
    except Exception as exc:
        return EvaluationFailure("canonical", f"{type(exc).__name__}: {exc}")

    # Our own invariants, over our own schema, as a total function. Anything
    # it raises is our defect and is reported as one -- see EvaluationFailure.
    # `violations` gathered during consumption (unbalanced / too few postings,
    # found while building events) duplicate what the validator finds over
    # the finished candidate; the validator is the authority. The summary is
    # over EVERY finding; only the sample is capped — and the findings are
    # STREAMED into both, never materialised (the maximum candidate can
    # produce 268,000).
    try:
        summary, sample = reduce_findings(iter_violations(candidate))
    except Exception as exc:
        return EvaluationFailure("validate_candidate", f"{type(exc).__name__}: {exc}")
    # Differential oracle, per shared category, asymmetric: an overlap
    # category the oracle reports and we do not is a gap in the reward
    # authority — ours, not the agent's — and is an evaluator failure, not a
    # penalty nobody reviewed. Categories only we report are our validator
    # being stricter, bounded by the golden-solution test.
    missing = oracle_disagreement(oracle, summary.codes)
    if missing:
        return EvaluationFailure(
            "validator_disagreement",
            f"oracle reports {missing} and the normative validator does not; "
            f"first oracle: {oracle[0] if oracle else '-'}",
        )
    return Accepted(submission, candidate, structural_id, semantic_id,
                    finding_summary=summary, domain_findings=sample, oracle_diagnostics=tuple(oracle),
                    oracle_unmapped=oracle_unmapped(oracle))


def _is_absent(value) -> bool:
    """Is this field carrying nothing?

    Written out rather than `value in (None, (), [], "")`, which is what it was
    and which crashed. That form invokes `__eq__` on whatever the parser put in
    the field, and beancount's `Amount.__eq__` unpacks the other operand
    without checking its type -- so comparing a price annotation against an
    empty tuple raised AttributeError inside the library.

    A rejected field is by definition one we do not model, so the check that
    decides whether it is populated must never call methods on it. Type first,
    then length; nothing else touches the value.
    """
    if value is None:
        return True
    if isinstance(value, (tuple, list, set, frozenset, dict, str)):
        return len(value) == 0
    return False


def _check_envelope(text: str) -> ProtocolFailure | None:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) > MAX_BYTES:
        return ProtocolFailure("envelope.bytes", f"{len(raw)} > {MAX_BYTES}")
    # Physical lines as Beancount's lexer sees them: split on "\n" only.
    # `str.splitlines()` also splits on VT, FF, NEL, U+2028/2029, so a
    # single 100 KB physical line padded with "\x0b" measured as many short
    # lines — a cap that did not measure what it named (round-2 adversary).
    lines = [line.rstrip("\r") for line in text.split("\n")]
    if len(lines) > MAX_LINES:
        return ProtocolFailure("envelope.lines", f"{len(lines)} > {MAX_LINES}")
    for n, line in enumerate(lines, 1):
        if len(line) > MAX_LINE_LENGTH:
            return ProtocolFailure(
                "envelope.line_length", f"line {n} is {len(line)} > {MAX_LINE_LENGTH}"
            )
    # Numeric tokens are bounded before the parser sees them, not only after:
    # the parser builds a Decimal cheaply from any digit string and the cost
    # lands on whoever expands it. Token-aware — quoted strings and comments
    # are governed by their own declared limits, not by this one.
    try:
        run = longest_numeric_digit_run(text)
    except LexicalError as exc:
        return ProtocolFailure(exc.reason, exc.detail)
    if run > MAX_DIGIT_RUN:
        return ProtocolFailure("envelope.number_length", f"a numeric token with {run} digits > {MAX_DIGIT_RUN}")
    reserved = reserved_meta_line(text)
    if reserved is not None:
        return ProtocolFailure("meta.reserved_key",
                               f"line {reserved} authors a parser-reserved metadata key ({sorted(POSITION_META)})")
    return None


def _consume_options(options_map: dict, trace: ConsumptionTrace) -> str | ProtocolFailure:
    """Options split three ways: contract semantics, contract presentation, refusal.

    Only options the environment itself generates are recognised. An option we
    do not model may change how the parser behaves, so ignoring an unfamiliar
    one is not safe -- rewriting the ledger's header and operating currency was
    a real submission. Beancount fills in a large default option map, so the
    comparison is against the keys that differ from the defaults rather than
    against every key present.
    """
    currency = None
    title = None
    for key in sorted(_authored_options(options_map)):
        rule = OPTIONS.get(key, OPTION_DEFAULT)
        path = f"option.{key}"
        if rule.disposition is Disposition.REJECTED:
            trace.record(Disposition.REJECTED, path)
            return ProtocolFailure(rule.reason, f"option {key!r}: {rule.note}", trace)
        trace.record(rule.disposition, path)
        try:
            if key == "operating_currency":
                values = options_map.get(key) or []
                if len(values) != 1:
                    return ProtocolFailure(
                        "option.operating_currency.not_single",
                        f"v1 models one currency; found {values}",
                        trace,
                    )
                currency = canonical_identifier(values[0], CURRENCY_GRAMMAR, field="option.operating_currency")
            elif key == "title":
                # Dropped from the candidate (contract-owned presentation);
                # retained in the structural record under the text policy.
                title = canonical_text(options_map.get(key), field="option.title")
        except StringPolicyViolation as exc:
            return ProtocolFailure(exc.reason, exc.detail, trace)
    if currency is None:
        return ProtocolFailure(
            "option.operating_currency.missing", "no operating currency declared", trace
        )
    return currency, title


def _authored_options(options_map: dict) -> set[str]:
    """Options whose *effective value* differs from an empty document's.

    Be precise about what this proves, because it is less than it looks. It
    detects effective option changes. It does not detect an option authored
    with exactly the default value, or a repeated option reduced to a single
    result, because `options_map` stores the reduction rather than the source.

    That gap does not need closing so much as avoiding: the contract owns the
    envelope. Submitted options are allowlisted and then ignored, and the
    canonical renderer supplies them, so there is nothing for an agent to gain
    by declaring one that matches the default. Postings carry their currency
    explicitly, so single-currency semantics is established by validating the
    postings rather than by trusting a header line.

    Until the contract layer exists to supply them, this reads the declared
    currency from the submission -- so the claim held here today is "effective
    option changes are visible", not the stronger "only environment-generated
    options may appear". Source-level option observation would be needed for
    the stronger one, and it is not needed at all under the contract split.
    """
    baseline = _default_options()
    return {
        k for k, v in options_map.items()
        if k not in ("filename", "dcontext", "input_hash") and baseline.get(k) != v
    }


_DEFAULTS: dict | None = None


def _default_options() -> dict:
    global _DEFAULTS
    if _DEFAULTS is None:
        _, _, _, om = safe_parse("")
        _DEFAULTS = {k: v for k, v in om.items()}
    return _DEFAULTS


def _consume_directive(entry, index, currency, trace, entity_resolver, violations, structural):
    name = type(entry).__name__
    table = FIELDS[name]
    values = entry._asdict()
    kept: dict = {}

    for fname, value in values.items():
        rule = table.get(fname)
        path = f"[{index}].{name}.{fname}"
        if rule is None:
            return ProtocolFailure(
                "field.unclassified",
                f"{name}.{fname} has no entry in the mapping table",
                trace,
            )
        if fname == "meta":
            failure = _consume_meta(value, path, trace)
            if failure is not None:
                return failure
            refs = _source_refs(value)
            kept["meta"] = f"{refs[0][0]}:{refs[0][1]}" if refs else None
            kept["refs"] = refs
            continue
        if rule.disposition is Disposition.REJECTED:
            # A rejected field only refuses when it actually carries something.
            # `Open.booking` is None on every ordinary open directive, and
            # refusing on its mere presence would reject the whole language.
            if not _is_absent(value):
                trace.record(Disposition.REJECTED, path)
                return ProtocolFailure(rule.reason, f"{name}.{fname}: {rule.note}", trace)
            trace.record(Disposition.DROPPED, path)
            continue
        trace.record(rule.disposition, path)
        if rule.disposition in (Disposition.MAPPED, Disposition.CANONICALISED):
            kept[fname] = value

    if name in ("Open", "Close"):
        account = canonical_identifier(kept["account"], ACCOUNT_GRAMMAR, field=f"{name.lower()}.account")
        date = canonical_identifier(str(kept["date"]), DATE_GRAMMAR, field=f"{name.lower()}.date")
        currencies = tuple(
            canonical_identifier(c, CURRENCY_GRAMMAR, field="open.currencies")
            for c in (kept.get("currencies") or ())
        )
        if currencies and set(currencies) != {currency}:
            return ProtocolFailure(
                "open.currency_mismatch",
                f"{account} opened in {list(currencies)}, contract is {currency}",
                trace,
            )
        structural.append(ParsedLifecycle(index, name.lower(), date, account, currencies))
        return AccountLifecycle(name.lower(), date, account, currencies)

    return _build_event(entry, kept, index, currency, trace, entity_resolver, violations, structural)


def _consume_meta(meta, path, trace) -> ProtocolFailure | None:
    """Metadata keyspace: whitelist with a total fail-closed complement.

    Metadata is an open dict, so the exhaustiveness property here has a
    different shape from the field mapping -- but not a weaker one, which took
    a correction to see. The claim is not "every possible key is enumerated",
    which is impossible. It is:

        for every key present in a given finite input, exactly one total
        classifier branch runs

    Mapped for a recognised source reference, dropped by name for the parser's
    own position keys, rejected for everything else. The whitelist is finite
    and its complement is a single total rule, so every key is consumed exactly
    once -- the same guarantee the NamedTuple fields get, reached by covering
    the input rather than the keyspace.

    Where the claim does weaken is a construct the parser folds into entries
    without leaving an AST path to record. That is `pushtag` and `pushmeta`,
    which attach state to entries that do not carry it in source, and it is why
    they are refused at the lexical gate: no amount of AST coverage can see the
    construct that caused the state.
    """
    for key in sorted(meta or {}):
        if key in POSITION_META:
            trace.record(Disposition.DROPPED, f"{path}[{key}]")
        elif key in SOURCE_META:
            trace.record(Disposition.MAPPED, f"{path}[{key}]")
        else:
            trace.record(Disposition.REJECTED, f"{path}[{key}]")
            return ProtocolFailure(
                "meta.unrecognised_key",
                f"metadata key {key!r} is not in the source-reference whitelist",
                trace,
            )
    return None


def _source_refs(meta) -> list[tuple[str, str]]:
    """Whitelisted source references as (key, canonical value), sorted.

    Values go through the text policy, so the candidate, the scorer and the
    renderer all see one normalised value. A non-string value is a policy
    refusal: a reference is text a real document carries.
    """
    refs = []
    for key in sorted(SOURCE_META):
        if meta and key in meta:
            refs.append((key, canonical_text(meta[key], field=f"meta.{key}", max_codepoints=REF_MAX_CODEPOINTS)))
    return refs


def _build_event(entry, kept, index, currency, trace, entity_resolver, violations, structural):
    postings: list[Posting] = []
    parsed_postings: list[ParsedPosting] = []
    raw = kept.get("postings") or []
    if len(raw) > MAX_POSTINGS_PER_EVENT:
        return ProtocolFailure(
            "envelope.postings", f"{len(raw)} > {MAX_POSTINGS_PER_EVENT}", trace
        )

    for pindex, posting in enumerate(raw):
        for pname, pvalue in posting._asdict().items():
            rule = POSTING_FIELDS.get(pname)
            path = f"[{index}].posting[{pindex}].{pname}"
            if rule is None:
                return ProtocolFailure(
                    "field.unclassified", f"Posting.{pname} is not classified", trace
                )
            if pname == "meta":
                failure = _consume_meta(pvalue, path, trace)
                if failure is not None:
                    return failure
                continue
            if rule.disposition is Disposition.REJECTED:
                if not _is_absent(pvalue):
                    trace.record(Disposition.REJECTED, path)
                    return ProtocolFailure(rule.reason, f"posting.{pname}", trace)
                trace.record(Disposition.DROPPED, path)
                continue
            trace.record(rule.disposition, path)

        units = posting.units
        if units is None or units.number is None:
            # Elided amounts are rejected in v1. Beancount can often infer the
            # number, but inferring it needs a booking model this does not
            # have, and the agent can always write it. Accepting elision later
            # is one rule in the table; accepting it now and discovering the
            # inference is context-dependent is not cheap.
            return ProtocolFailure(
                "posting.units.elided",
                f"posting to {posting.account} has no explicit amount",
                trace,
            )
        if units.currency != currency:
            return ProtocolFailure(
                "posting.units.currency",
                f"{units.currency} is not the operating currency {currency}",
                trace,
            )
        account = canonical_identifier(posting.account, ACCOUNT_GRAMMAR, field="posting.account")
        bounded = bounded_decimal(units.number)          # domain bounds first, then the money scale
        try:
            amount = money(bounded)
        except (ValueError, InvalidOperation) as exc:
            return ProtocolFailure("posting.units.scale", str(exc), trace)
        postings.append(Posting(account, amount))
        pflag = (canonical_identifier(posting.flag, FLAG_GRAMMAR, field="posting.flag")
                 if posting.flag else None)
        parsed_postings.append(ParsedPosting(account, bounded, units.currency, pflag))

    # Malformed bookkeeping, not an unreadable submission. Both of these were
    # protocol failures until it was pointed out that a ledger which does not
    # balance is the single thing this task most exists to notice -- refusing
    # to score it would throw away the component that matters and would inflate
    # the protocol-rejection rate, which is supposed to measure whether *our*
    # accepted subset is too narrow.
    where = f"{kept['date']} {kept.get('payee') or ''}".strip()
    if len(postings) < 2:
        violations.append(f"transaction has {len(postings)} posting(s): {where}")
    elif sum((p.amount for p in postings), Decimal("0")) != 0:
        total = sum((p.amount for p in postings), Decimal("0"))
        violations.append(f"transaction does not balance (off by {total}): {where}")

    # Strings under the policy. Payee and narration are human text: NFC for
    # storage identity, and the SAME normalised payee is what the resolver
    # sees and what the structural record keeps. Flag, tags and links are
    # dropped from the candidate and retained structurally under their
    # grammars; a near-match is a refusal, not a repair.
    date = canonical_identifier(str(kept["date"]), DATE_GRAMMAR, field="txn.date")
    payee = kept.get("payee")
    payee = canonical_text(payee, field="payee") if payee is not None else None
    narration = canonical_text(entry.narration if entry.narration is not None else "", field="narration")
    flag = canonical_identifier(entry.flag, FLAG_GRAMMAR, field="txn.flag")
    tags = tuple(sorted({canonical_identifier(t, TAG_GRAMMAR, field="txn.tag") for t in (entry.tags or ())}))
    links = tuple(sorted({canonical_identifier(l, TAG_GRAMMAR, field="txn.link") for l in (entry.links or ())}))
    structural.append(ParsedTransaction(
        index=index, date=date, flag=flag, payee=payee, narration=narration,
        tags=tags, links=links, source_refs=tuple(kept.get("refs") or ()),
        postings=tuple(parsed_postings),
    ))

    entity = entity_resolver(payee) if entity_resolver else payee

    return Event(
        date=date,
        entity=entity,
        source_ref=kept.get("meta"),
        postings=tuple(postings),
    )
