"""Canonical bytes, bounded numbers, a string policy, and the digests over them.

Three identities, kept apart on purpose:

    source digests        identity of the submitted TEXT (three domains, in
                          `beancount_ledger.digests_of`): what was sent, what
                          was stored, what the scorer read
    candidate_digest      identity of the closed PARSED submission, structural:
                          directives in parser order (the pinned parser sorts
                          by date and keeps source position within a date —
                          measured: swapping two transactions of different
                          dates in the text yields the same parsed submission,
                          swapping two of the same date does not), postings in
                          authored order, narration and payee as written under
                          the string policy. Provenance, immutability checks,
                          exact cache keys. Unequal candidate digests do NOT
                          imply unequal accounting.
    semantic_fingerprint  the task-contract-defined equivalence: events as a
                          sorted multiset, postings sorted, narration and flags
                          erased, payee resolved to an entity. Matching,
                          preservation, identifiability. Never a certificate
                          identity, because it deliberately forgets things
                          provenance must keep.

Everything hashed here goes through ONE encoder, `canonical_bytes`, which is
package-owned rather than "json.dumps with options": key order by code point,
declared list order, semantic sets sorted by their encoded bytes (never by
Python object ordering), Decimals as context-independent plain numbers, no
floats, no NaN, controls and U+2028/2029 escaped, everything else raw UTF-8,
no trailing newline, a byte cap enforced before hashing. Golden vectors pin
the exact bytes.

Numbers are bounded BEFORE any plain expansion. Beancount's grammar refuses
exponent notation (`1E+5` is a syntax error, measured on 3.2.3), but it accepts
a 75-digit literal happily, and a Decimal can be built cheaply from a token
that then costs a lot to expand; so a lexical digit-run cap runs before the
parser and `bounded_decimal` runs again on every parsed number: significant
digits, magnitude, scale, canonical byte length, finite only, signed zero
canonicalised to 0. The canonical form is computed from `as_tuple()` and never
depends on the active Decimal context.

Strings: identifiers with an ASCII grammar (accounts, currencies, dates, tags,
links, flags) are validated exactly and never normalised — a near-match is a
rejection, not a repair. Human text (payee, narration, source references,
title) is NFC for storage identity, with code-point and byte caps and with
controls, format/bidi characters, surrogates, private-use and unassigned code
points refused. The candidate stores the normalised value and the scorer and
renderer consume that same value; the source digests still distinguish the
composed and decomposed spellings.
"""

from __future__ import annotations

import hashlib
import heapq
import re
import unicodedata
from dataclasses import dataclass, field, fields, is_dataclass
from decimal import Decimal
from typing import Any

# --------------------------------------------------------------------------
# versions — declared behavioural contracts, never code hashes
# --------------------------------------------------------------------------

CANONICAL_ENCODING_VERSION = 1
PARSE_POLICY_VERSION = 1
CANDIDATE_SCHEMA_VERSION = 1
SEMANTIC_FINGERPRINT_VERSION = 1
TASK_CONTRACT_VERSION = 1
SCORER_CONTRACT_VERSION = 1
RENDERER_VERSION = 1

# Which declared version invalidates what. A parse certificate depends on the
# parse policy and the candidate schema; a rendered public bundle on the
# renderer and the task contract. Separate scopes, not one build hash.
#
# A SCORE CACHE is keyed conservatively and is NOT keyed by the semantic
# fingerprint. The fingerprint erases narration, and this task's preservation
# rule observes narration: a correct ledger cached under fingerprint F and a
# narration-tampered ledger with the same F would hit the cache and skip the
# tamper penalty. Economic equivalence and reward-observation equivalence are
# different relations. No score cache exists today; the key that would be safe
# is `score_cache_key` below — and while the live scorer still reads TEXT
# (comments, layout, amount spelling), not even the structural candidate
# identity is enough, so that key includes the logical source digest.
ENTITY_MATCHING_VERSION = 1

INVALIDATION_SCOPES = {
    "parse_certificate": ("PARSE_POLICY_VERSION", "CANDIDATE_SCHEMA_VERSION"),
    # The eventual key binds the FULL committed outcome — candidate identity
    # plus the canonical domain findings the policy prices — never the
    # candidate alone (two analyses with one candidate and different
    # findings score differently), and during migration the logical source
    # digest as well, because the live scorer still reads text.
    # Semantic equality only: `reward_input_digest` (candidate + finding
    # summary) with the environment and engine identity. Never the
    # evaluation receipt, which binds source provenance and would turn a
    # comment edit into a cache miss and, worse, invite the reverse use.
    "score_cache": ("reward_input_digest", "environment_digest", "engine.id", "SCORER_CONTRACT_VERSION",
                    "ENTITY_MATCHING_VERSION", "logical_text_digest (raw-text engine only)"),
    "rendered_bundle": ("RENDERER_VERSION", "TASK_CONTRACT_VERSION"),
}
def score_cache_key(engine, reward_input: str, task_contract: str, logical_text_digest: str | None = None,
                    environment_digest: str | None = None) -> str:
    """The conservative key, per engine: every channel that engine reads.

    `reward_input` is `reward_input_digest` (candidate + finding summary);
    evaluator failures have none and are never cacheable. The raw-text
    engine must bind the logical source digest (it reads comments, layout,
    spellings) and refuses a key without it; the candidate engine must not
    (the metamorphic witness proves no source-only channel moves it, and a
    stale source digest would only manufacture misses). The environment
    digest binds the loaded environment — targets, accepted payees, planted
    events — so a commitment for task A can never hit as task B. The engine
    id is in the domain, so the two namespaces cannot collide.
    File-integrity finalisation must succeed before any lookup.
    """
    if engine.reads_text and not logical_text_digest:
        raise CanonicalError(f"engine {engine.id} reads text; its cache key needs the logical source digest")
    if not engine.reads_text and logical_text_digest is not None:
        raise CanonicalError(f"engine {engine.id} does not read text; a source digest in its key is a recipe mix-up")
    return domain_digest(f"piv:score-input:{engine.id}\0".encode("utf-8"), canonical_bytes({
        "reward_input_digest": reward_input,
        "task_contract_digest": task_contract,
        "environment_digest": environment_digest,
        "scorer_contract_version": SCORER_CONTRACT_VERSION,
        "entity_matching_version": ENTITY_MATCHING_VERSION,
        "logical_text_digest": logical_text_digest,
    }))

# --------------------------------------------------------------------------
# numeric bounds
# --------------------------------------------------------------------------

MAX_SIGNIFICANT_DIGITS = 20
MAX_ADJUSTED_EXPONENT = 15        # |value| < 10^16: generous for a small company's books
MIN_EXPONENT = -8                 # no digit finer than 1e-8 anywhere; money() then requires 0.01
MAX_DIGIT_RUN = 40                # lexical: a longer run of digits never reaches the parser
MAX_CANONICAL_AMOUNT_BYTES = 40
MAX_CANONICAL_BYTES = 1024 * 1024
MAX_OUTCOME_DIAGNOSTICS = 50
MAX_TOTAL_DIAGNOSTICS = 10_000       # the reported total saturates here


class NumberOutOfBounds(ValueError):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def _reduced(value: Decimal) -> tuple[int, tuple[int, ...], int]:
    """`as_tuple()` with trailing zero digits folded into the exponent.

    The bounds are on the VALUE, not on the spelling: `85.000000000000000`
    is the number 85 written badly, which the boundary's own contract says
    is presentation and must be accepted (it cuts on exactness, not on digit
    count). The spelling's cost is bounded elsewhere — the lexical digit-run
    cap and the line length — so what is bounded here is the domain: how
    many digits the number actually has, how large and how fine it is.
    """
    sign, digits, exponent = value.as_tuple()
    digits = list(digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    return sign, tuple(digits), exponent


def bounded_decimal(value: Any) -> Decimal:
    """The value, if it is a finite Decimal within the declared domain.

    Signed zero and zero at any exponent are the same number here and become
    plain 0; the scorer's arithmetic treats them as zero, so identity does too.
    """
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise NumberOutOfBounds("number.type", type(value).__name__)
    value = Decimal(value)
    if not value.is_finite():
        raise NumberOutOfBounds("number.not_finite", str(value))
    if value == 0:
        return Decimal(0)
    sign, digits, exponent = _reduced(value)
    if len(digits) > MAX_SIGNIFICANT_DIGITS:
        raise NumberOutOfBounds("number.precision", f"{len(digits)} > {MAX_SIGNIFICANT_DIGITS} significant digits")
    if exponent < MIN_EXPONENT:
        raise NumberOutOfBounds("number.scale", f"a digit finer than 1E{MIN_EXPONENT}")
    if value.adjusted() > MAX_ADJUSTED_EXPONENT:
        raise NumberOutOfBounds("number.magnitude", f"adjusted exponent {value.adjusted()} > {MAX_ADJUSTED_EXPONENT}")
    return value


def canonical_decimal(value: Any) -> str:
    """Shortest plain decimal string of the exact value, from `as_tuple()`.

    `85`, `85.0`, `85.00` -> `85`; `0.10` -> `0.1`; `1E+5` -> `100000`;
    `-0`, `-0.00`, `0E+9` -> `0`. Independent of the Decimal context: no
    `normalize()`, no `quantize()`, no formatting call that consults it.
    """
    value = bounded_decimal(value)
    if value == 0:
        return "0"
    sign, digits, exponent = value.as_tuple()
    ds = "".join(str(d) for d in digits)
    if exponent >= 0:
        integer, fraction = ds + "0" * exponent, ""
    else:
        point = len(ds) + exponent
        if point <= 0:
            integer, fraction = "0", "0" * (-point) + ds
        else:
            integer, fraction = ds[:point], ds[point:]
    integer = integer.lstrip("0") or "0"
    fraction = fraction.rstrip("0")
    out = ("-" if sign else "") + integer + (("." + fraction) if fraction else "")
    if len(out) > MAX_CANONICAL_AMOUNT_BYTES:
        raise NumberOutOfBounds("number.canonical_bytes", f"{len(out)} > {MAX_CANONICAL_AMOUNT_BYTES}")
    return out


class LexicalError(ValueError):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def longest_numeric_digit_run(text: str) -> int:
    """The longest run of ASCII digits OUTSIDE quoted strings and comments.

    Token-aware, bounded, deterministic, no regex, no parser. The first
    version scanned the whole text and so refused a 41-digit invoice
    reference inside a quoted string that the string matrix allows up to 64
    code points, and a 41-digit comment while accepting a 20,000-letter one
    — a numeric limit applied to non-numeric text. Quoted strings (with
    backslash escapes, newlines allowed as Beancount allows them) and `;`
    comments are skipped; what remains is keywords, dates, accounts, tags,
    currencies and numbers, and there a run longer than MAX_DIGIT_RUN is a
    number nobody wrote by hand. An unclosed string at end of input is a
    lexical refusal in its own right.
    """
    longest = run = 0
    in_string = escaped = in_comment = False
    line = 1
    for ch in text:
        if ch == "\n":
            line += 1
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if in_comment:
            if ch == "\n":
                in_comment = False
            continue
        if ch == '"':
            in_string = True
            run = 0
        elif ch == ";":
            in_comment = True
            run = 0
        elif "0" <= ch <= "9":
            run += 1
            longest = max(longest, run)
        elif ch in ",." and run:
            continue
        else:
            run = 0
    if in_string:
        raise LexicalError("lexical.unclosed_string", f"a quoted string is not closed by line {line}")
    return longest


# --------------------------------------------------------------------------
# string policy
# --------------------------------------------------------------------------

TEXT_MAX_CODEPOINTS = 200
REF_MAX_CODEPOINTS = 64
TEXT_MAX_BYTES = 800

# Beancount's own grammars, pinned here so a near-match is refused rather than
# repaired. Exact ASCII; nothing is normalised before matching.
ACCOUNT_GRAMMAR = re.compile(r"^(Assets|Liabilities|Equity|Income|Expenses)(:[A-Z0-9][A-Za-z0-9\-]*)+$")
CURRENCY_GRAMMAR = re.compile(r"^[A-Z][A-Z0-9'._\-]{0,22}[A-Z0-9]$")
DATE_GRAMMAR = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
TAG_GRAMMAR = re.compile(r"^[A-Za-z0-9\-_/.]{1,64}$")
FLAG_GRAMMAR = re.compile(r"^[*!&#?%PSTCURM]$")

# Categories refused in human text: controls, format (including every bidi
# control and zero-width joiner), surrogates, private use, unassigned (which
# covers the noncharacters) — and the line/paragraph separators (U+2028,
# U+2029), which are not controls by category but break a line the way one
# does, which a rendered ledger must never allow a string to do.
FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})

# The matrix, by field. "grammar" fields are validated exactly and never
# normalised; "text" fields are NFC with caps; "rejected" fields never reach a
# candidate; "whitelist" keys are enumerated in `normalise.SOURCE_META`.
STRING_POLICY = {
    "account": "grammar:account",
    "currency": "grammar:currency",
    "date": "grammar:iso-date",
    "flag": "grammar:flag",
    "tag": "grammar:tag",
    "link": "grammar:tag",
    "payee": f"text:nfc:{TEXT_MAX_CODEPOINTS}",
    "narration": f"text:nfc:{TEXT_MAX_CODEPOINTS}",
    "meta.key": "whitelist:source-reference",
    "meta.value": f"text:nfc:{REF_MAX_CODEPOINTS}",
    "option.title": f"text:nfc:{TEXT_MAX_CODEPOINTS}",
    "option.operating_currency": "grammar:currency",
    "cost.label": "rejected",
    "cost.*": "rejected",
    "price.*": "rejected",
}


# Each semantic predicate has its OWN named comparison policy. There is no
# universal entity matcher for reward: the planted-repair payee predicate is
# the contract that closed the mocking-case exploit — case-sensitive,
# whitespace runs collapsed, nothing else normalised after the parser's NFC
# storage — and a lookup that folds case and compatibility characters is a
# DIAGNOSTIC (register lookup, identifiability, confusable detection), never
# a way to turn a confusable spelling into an accepted counterparty.
COMPARISON_POLICIES = {
    "planted_repair.payee": {
        "case_sensitive": True, "whitespace": "collapse_runs",
        "unicode": "none_after_parser_storage (NFC)", "punctuation": "preserve", "suffixes": "preserve",
        "used_for": "reward",
    },
    "customer_lookup_for_diagnostics": {
        "case_sensitive": False, "whitespace": "collapse_runs",
        "unicode": "NFKC", "punctuation": "to_space", "suffixes": "strip_corporate",
        "used_for": "diagnostics only (register lookup, identifiability, confusable reports)",
    },
}


def strict_payee_match(submitted: str | None, accepted: str) -> bool:
    """The reward predicate `planted_repair.payee`: whole-string equality
    after collapsing whitespace runs, case-sensitive, no other normalisation.
    Both sides are NFC already (the candidate stores NFC; task data is
    normalised on load). A lookalike, a case variant, a ligature or a
    dotted/dotless I is not the accepted counterparty."""
    if not isinstance(submitted, str):
        return False
    return " ".join(submitted.split()) == " ".join(accepted.split())


# The differential oracle's messages, projected onto a shared taxonomy. Our
# validator's codes on the right; the substring the pinned Beancount (3.2.3)
# emits on the left. Compared per category by PRESENCE, not multiplicity:
# the two count differently (we report close-before-open AND the posting
# after the close; Beancount reports one "unopened account closed") and
# Beancount's messages carry no entry identity to align occurrences on.
#
# The comparison is asymmetric on purpose: an overlap category the oracle
# reports and our validator does NOT is a gap in the reward authority and is
# an evaluator failure (quarantine, never a score); a category only we
# report is our validator being stricter, which the golden-solution test
# bounds and which cannot be exploited — and a symmetric rule would let an
# agent buy exclusion by writing a ledger our validator over-reports on.
ORACLE_PROJECTION = {
    "balance": ("Transaction does not balance", {"event.unbalanced", "event.too_few_postings"}),
    "unknown_account": ("Invalid reference to unknown account", {"posting.account_not_open"}),
    "inactive_account": ("Invalid reference to inactive account",
                         {"posting.before_account_opened", "posting.after_account_closed"}),
    "duplicate_open": ("Duplicate open directive", {"lifecycle.duplicate_open"}),
    "duplicate_close": ("Duplicate close directive", {"lifecycle.duplicate_close"}),
    "close_unopened": ("is being closed", {"lifecycle.close_without_open", "lifecycle.close_before_open"}),
}


def _beancount_version() -> str:
    import beancount

    return str(beancount.__version__)


def oracle_unmapped(oracle_diagnostics) -> int:
    """Lines no needle maps: telemetry. A growing bucket after an upgrade
    means the coverage alarm was silently destroyed."""
    return sum(1 for line in oracle_diagnostics
               if not any(needle in line for needle, _ in ORACLE_PROJECTION.values()))


def oracle_disagreement(oracle_diagnostics, findings) -> list[str]:
    """Overlap categories the oracle reports and the normative validator does
    not. Empty means agreement on everything both are claimed to cover;
    oracle lines outside every category are diagnostic-only."""
    ours = {getattr(f, "code", f) for f in findings}      # findings, or their codes (from the summary)
    missing = []
    for category, (needle, codes) in ORACLE_PROJECTION.items():
        if any(needle in line for line in oracle_diagnostics) and not (ours & codes):
            missing.append(category)
    return missing


class StringPolicyViolation(ValueError):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def canonical_text(value: Any, *, field: str, max_codepoints: int = TEXT_MAX_CODEPOINTS) -> str:
    """Human text under the policy: bounded, no forbidden code points, NFC."""
    if not isinstance(value, str):
        raise StringPolicyViolation("string.type", f"{field}: {type(value).__name__}")
    if len(value) > max_codepoints:
        raise StringPolicyViolation("string.too_long", f"{field}: {len(value)} > {max_codepoints} code points")
    for index, ch in enumerate(value):
        if unicodedata.category(ch) in FORBIDDEN_CATEGORIES:
            raise StringPolicyViolation(
                "string.forbidden_codepoint", f"{field}: U+{ord(ch):04X} ({unicodedata.category(ch)}) at {index}")
    # Caps before normalisation bound the work; caps after normalisation bound
    # what is stored (NFC can lengthen or shorten a string).
    out = unicodedata.normalize("NFC", value)
    if len(out) > max_codepoints:
        raise StringPolicyViolation("string.too_long", f"{field}: {len(out)} > {max_codepoints} code points after NFC")
    if len(out.encode("utf-8")) > TEXT_MAX_BYTES:
        raise StringPolicyViolation("string.too_long", f"{field}: > {TEXT_MAX_BYTES} bytes")
    return out


def canonical_identifier(value: Any, grammar: re.Pattern, *, field: str) -> str:
    """An identifier with an ASCII grammar: exact match, never normalised."""
    if not isinstance(value, str):
        raise StringPolicyViolation("string.type", f"{field}: {type(value).__name__}")
    if len(value) > 256 or not value.isascii() or grammar.match(value) is None:
        raise StringPolicyViolation("string.grammar", f"{field}: {value[:40]!r}")
    return value


# --------------------------------------------------------------------------
# the encoder
# --------------------------------------------------------------------------

class CanonicalError(ValueError):
    pass


def canonical_bytes(obj: Any) -> bytes:
    """The one canonical serialisation. Deterministic across processes and
    construction order; refuses anything whose identity would be ambient."""
    parts: list[str] = []
    _encode(obj, parts)
    data = "".join(parts).encode("utf-8")
    if len(data) > MAX_CANONICAL_BYTES:
        raise CanonicalError(f"canonical form is {len(data)} bytes > {MAX_CANONICAL_BYTES}")
    return data


def canonical_sorted(items) -> list:
    """A semantic set as a list, sorted by canonical encoded bytes — never by
    Python object ordering, which is ambient."""
    return sorted(items, key=canonical_bytes)


def _encode(o: Any, out: list[str]) -> None:
    if o is None:
        out.append("null")
    elif o is True:
        out.append("true")
    elif o is False:
        out.append("false")
    elif isinstance(o, int):
        out.append(str(o))
    elif isinstance(o, Decimal):
        out.append(canonical_decimal(o))
    elif isinstance(o, float):
        raise CanonicalError("floats have no canonical identity; use Decimal")
    elif isinstance(o, str):
        out.append(_quote(o))
    elif isinstance(o, (list, tuple)):
        out.append("[")
        for i, item in enumerate(o):
            if i:
                out.append(",")
            _encode(item, out)
        out.append("]")
    elif isinstance(o, dict):
        if not all(isinstance(k, str) for k in o):
            raise CanonicalError("mapping keys must be strings")
        out.append("{")
        for i, key in enumerate(sorted(o)):          # str order == code point order
            if i:
                out.append(",")
            out.append(_quote(key))
            out.append(":")
            _encode(o[key], out)
        out.append("}")
    elif is_dataclass(o) and not isinstance(o, type):
        _encode({f.name: getattr(o, f.name) for f in fields(o) if not f.name.startswith("_")}, out)
    elif isinstance(o, (set, frozenset)):
        raise CanonicalError("unordered collection; pass canonical_sorted(items)")
    else:
        raise CanonicalError(f"no canonical form for {type(o).__name__}")


def _quote(s: str) -> str:
    out = ['"']
    for ch in s:
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif code < 0x20 or code in (0x2028, 0x2029):
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


# --------------------------------------------------------------------------
# digests
# --------------------------------------------------------------------------

CANDIDATE_DOMAIN = b"piv:candidate:v1\0"
SEMANTIC_DOMAIN = b"piv:semantic:v1\0"
OUTCOME_DOMAIN = b"piv:outcome:v1\0"
PARSE_POLICY_DOMAIN = b"piv:parse-policy:v1\0"
TASK_CONTRACT_DOMAIN = b"piv:task-contract:v1\0"


def domain_digest(domain: bytes, payload: bytes) -> str:
    return hashlib.sha256(domain + payload).hexdigest()


def candidate_digest(submission) -> str:
    """Structural identity of a `SafeParsedSubmission`."""
    return domain_digest(CANDIDATE_DOMAIN, canonical_bytes(submission.as_canonical()))


def semantic_view(candidate) -> dict:
    """The task-contract equivalence view of a `LedgerCandidate`: sorted
    multisets, resolved entities, no narration, no flags, no order."""
    return {
        "schema": SEMANTIC_FINGERPRINT_VERSION,
        "currency": candidate.operating_currency,
        "lifecycle": [
            {"kind": a.kind, "date": a.date, "account": a.account, "currencies": list(a.currencies)}
            for a in candidate.lifecycle
        ],
        "events": [
            {"date": e.date, "entity": e.entity, "source_ref": e.source_ref,
             "postings": [{"account": p.account, "amount": p.amount} for p in e.postings]}
            for e in candidate.events
        ],
    }


def semantic_fingerprint(candidate) -> str:
    return domain_digest(SEMANTIC_DOMAIN, canonical_bytes(semantic_view(candidate)))


def rejection_payload(diagnostics: list) -> dict:
    """Stable codes plus canonical bounded locations; no messages.

    Capped in source order BEFORE sorting, so an attacker cannot amplify the
    outcome bytes with thousands of redundant findings; sorted by (code, line,
    column); multiplicity kept, since repeated findings at distinct locations
    are distinct. Unknown line/column is the sentinel -1.
    """
    rows = []
    for item in list(diagnostics)[:MAX_OUTCOME_DIAGNOSTICS]:
        code, line, column = (tuple(item) + (-1, -1))[:3]
        rows.append({"code": str(code), "line": int(line) if line is not None else -1,
                     "column": int(column) if column is not None else -1})
    rows.sort(key=lambda r: (r["code"], r["line"], r["column"]))
    total = len(diagnostics)
    return {"schema": PARSE_POLICY_VERSION, "diagnostics": rows,
            "truncated": total > MAX_OUTCOME_DIAGNOSTICS,
            # bound and saturated, so the count itself cannot grow the bytes
            "total": min(total, MAX_TOTAL_DIAGNOSTICS)}


def outcome_digest(variant: str, payload: Any, task_contract: str, parse_policy: str) -> str:
    """Binds the variant tag, the canonical payload and both provenance digests."""
    return domain_digest(OUTCOME_DOMAIN, canonical_bytes({
        "variant": variant, "payload": payload,
        "task_contract_digest": task_contract, "parse_policy_digest": parse_policy,
    }))


MAX_FINDING_SAMPLE = 500            # diagnostics shown; NEVER the policy's information
MAX_FINDING_COUNT = 1_000_000       # per-code counts saturate here (declared; policy reads presence)

# The closed aggregation schema: what the summary PRESERVES per finding code.
# Every policy declares what it reads (`policy.POLICY_REQUIREMENTS`) and
# contract construction fails if it asks for a reduction not listed here. A
# future rule needing a count by account, a monetary aggregate or an
# occurrence set adds the reduction to the schema first, versioned.
FINDING_REDUCTIONS = {
    code: ("presence", "saturated_count")
    for code in (
        "event.unbalanced", "event.too_few_postings",
        "posting.account_not_open", "posting.before_account_opened", "posting.after_account_closed",
        "lifecycle.duplicate_open", "lifecycle.duplicate_close",
        "lifecycle.close_without_open", "lifecycle.close_before_open",
    )
}


@dataclass(frozen=True)
class FindingSummary:
    """What the policy consumes: the whole candidate's findings, as exact
    (saturated) counts by code, with an overflow bit for the sample.

    A capped finding LIST was an attack surface: manufacture 500 cheap
    findings and put the expensive one after them, and a policy reading the
    list never sees it. The candidate caps do not bound findings below 500
    (2,000 events × 64 postings can each miss an account), so the summary is
    computed over the entire bounded candidate and the sample is only for
    reading. `codes` is what the policy prices; `counts` is what a per-entry
    rule would price; `truncated` says the sample is shorter than the truth.
    """

    counts: tuple            # ((code, count), ...) sorted by code
    total: int
    truncated: bool          # the diagnostic sample omits findings
    _mint: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        # Constructed only on the validator path (`summarise_findings`), so
        # application code cannot hand the policy a structurally valid but
        # false summary. The threat model is files, not Python objects; this
        # is composition-root discipline, not cryptography.
        if self._mint is not _SUMMARY_TOKEN:
            raise TypeError("FindingSummary is produced by summarise_findings() only")

    @property
    def codes(self) -> tuple:
        return tuple(code for code, _ in self.counts)

    def as_canonical(self) -> dict:
        return {"counts": [[code, count] for code, count in self.counts],
                "total": self.total, "truncated": self.truncated}


_SUMMARY_TOKEN = object()


def summarise_findings(findings) -> FindingSummary:
    counts: dict[str, int] = {}
    total = 0
    for f in findings:
        counts[f.code] = min(counts.get(f.code, 0) + 1, MAX_FINDING_COUNT)
        total += 1
    return FindingSummary(tuple(sorted(counts.items())), min(total, MAX_FINDING_COUNT),
                          total > MAX_FINDING_SAMPLE, _mint=_SUMMARY_TOKEN)


def _finding_key(f) -> bytes:
    """Exactly `canonical_bytes({"code", "facts", "message"})`, assembled
    directly: the general encoder's recursion cost ~45 µs a finding, which
    at the 258,000-finding maximum was the difference between a bounded
    stream and a ten-second one. The equality with the general encoder is
    asserted by the benchmark and by `test_canonical`."""
    parts = ['{"code":', _quote(f.code), ',"facts":']
    _encode([list(x) if isinstance(x, tuple) else x for x in f.facts], parts)
    parts += [',"message":', _quote(f.message), "}"]
    return "".join(parts).encode("utf-8")


def finding_sample(findings) -> tuple:
    """The diagnostic sample: a deterministic function of the canonical
    candidate, not of validator iteration. Findings are sorted by their
    canonical (code, facts, message) bytes and the lowest MAX_FINDING_SAMPLE
    are kept, so two semantically identical submissions produce the same
    sample and the same committed outcome digest."""
    return tuple(heapq.nsmallest(MAX_FINDING_SAMPLE, findings, key=_finding_key))


def reduce_findings(findings) -> tuple:
    """ONE pass over a finding STREAM into the two bounded reductions the
    system keeps — exact saturated counts by code and the deterministic
    sample (lowest MAX_FINDING_SAMPLE by canonical bytes) — retaining
    nothing else. `heapq.nsmallest` holds at most the sample; the counts
    are a dict by code; so the maximum legal candidate costs the sample in
    memory, not its finding count. Returns (FindingSummary, sample)."""
    counts: dict = {}
    seen = 0

    def counted():
        nonlocal seen
        for f in findings:
            counts[f.code] = min(counts.get(f.code, 0) + 1, MAX_FINDING_COUNT)
            seen += 1
            yield f
    sample = tuple(heapq.nsmallest(MAX_FINDING_SAMPLE, counted(), key=_finding_key))
    summary = FindingSummary(tuple(sorted(counts.items())), min(seen, MAX_FINDING_COUNT),
                             seen > MAX_FINDING_SAMPLE, _mint=_SUMMARY_TOKEN)
    return summary, sample


def finding_sample_payload(findings) -> list:
    """Diagnostic codes and facts of the sample — no messages, which are
    presentation and must not churn identity."""
    rows = [{"code": f.code, "facts": [list(x) if isinstance(x, tuple) else x for x in f.facts]} for f in findings]
    return canonical_sorted(rows)


# --------------------------------------------------------------------------
# two hashes: reward input and committed outcome
# --------------------------------------------------------------------------

REWARD_INPUT_DOMAIN = b"piv:reward-input:v1\0"


def reward_input_digest(candidate_digest_value: str, summary: FindingSummary) -> str:
    """Candidate semantics plus the policy-relevant finding summary — the
    complete policy input, pre-cap. Keys the score cache (with task, scorer
    and engine). A message edit cannot move it; a finding can."""
    return domain_digest(REWARD_INPUT_DOMAIN, canonical_bytes({
        "candidate_digest": candidate_digest_value, "findings": summary.as_canonical()}))


def committed_outcome_digest(variant: str, reward_input: str | None, payload: Any,
                             task_contract: str, parse_policy: str) -> str:
    """Variant tag, reward input, provenance, diagnostic sample codes/facts
    and the rendering contract: the identity of the returned object. A
    replay or artifact cache may key this; a score cache must not, or a
    renderer change reuses a stale reply while a wording edit churns scores."""
    return outcome_digest(variant, {"reward_input": reward_input, "diagnostics": payload,
                                    "renderer_version": RENDERER_VERSION}, task_contract, parse_policy)


EVALUATION_RECEIPT_DOMAIN = b"piv:evaluation-receipt:v1\0"
DELIVERY_RECEIPT_DOMAIN = b"piv:delivery-receipt:v1\0"


def evaluation_receipt_digest(variant: str, reward_input: str | None, payload: Any, receipt: dict,
                              versions: dict) -> str:
    """What was EVALUATED, for replay and audit: the variant, the semantic
    reward input (None for a rejection), the diagnostic sample, the input
    receipt's identity (rollout, revision, the three source digests) and
    every evaluator version the result depended on. Deliberately NOT a
    semantic equivalence key — two sources with one meaning and different
    bytes have one `reward_input_digest` and two of these."""
    return domain_digest(EVALUATION_RECEIPT_DOMAIN, canonical_bytes({
        "variant": variant, "reward_input": reward_input, "diagnostics": payload,
        "receipt": dict(receipt), "versions": dict(versions)}))


def accepted_reward_input(accepted) -> str:
    return reward_input_digest(accepted.candidate_digest, accepted.finding_summary)


def accepted_outcome_digest(accepted, task_contract: str, parse_policy: str) -> str:
    return committed_outcome_digest("Accepted", accepted_reward_input(accepted),
                                    finding_sample_payload(accepted.domain_findings), task_contract, parse_policy)


@dataclass(frozen=True)
class ScoringEngine:
    """Which scorer produced a score, and what it reads. Two engines coexist
    during migration and must never share a cache namespace: the raw-text
    engine's key REQUIRES the logical source digest, the candidate engine's
    key forbids it — the key builder derives that from the engine, so the raw
    scorer cannot be instantiated with the candidate recipe."""

    id: str
    reads_text: bool


RAW_TEXT_ENGINE = ScoringEngine("raw-text/1", reads_text=True)
CANDIDATE_ENGINE = ScoringEngine("candidate/1", reads_text=False)


def parse_policy_view() -> dict:
    """Everything that decides what is accepted and how it is read, as
    declared data: versions, the pinned parser, the disposition tables, the
    limits, the numeric bounds, the string policy. No repr, no callables, no
    paths."""
    import beancount

    from ..safe_parse import SIDE_EFFECTING_CONTROLS
    from . import mapping, normalise

    def table(rules: dict) -> dict:
        return {name: [rule.disposition.value, rule.reason] for name, rule in rules.items()}

    return {
        "parse_policy_version": PARSE_POLICY_VERSION,
        "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
        "canonical_encoding_version": CANONICAL_ENCODING_VERSION,
        "parser": {"library": "beancount", "version": str(beancount.__version__)},
        "controls": sorted(SIDE_EFFECTING_CONTROLS),
        "directives": table(mapping.DIRECTIVES),
        "fields": {name: table(rules) for name, rules in mapping.FIELDS.items()},
        "posting_fields": table(mapping.POSTING_FIELDS),
        "options": table(mapping.OPTIONS),
        "option_default": [mapping.OPTION_DEFAULT.disposition.value, mapping.OPTION_DEFAULT.reason],
        "source_meta": sorted(normalise.SOURCE_META),
        "position_meta": sorted(normalise.POSITION_META),
        "limits": {
            "max_bytes": normalise.MAX_BYTES, "max_lines": normalise.MAX_LINES,
            "max_line_length": normalise.MAX_LINE_LENGTH, "max_events": normalise.MAX_EVENTS,
            "max_postings_per_event": normalise.MAX_POSTINGS_PER_EVENT,
        },
        "numeric": {
            "max_significant_digits": MAX_SIGNIFICANT_DIGITS, "max_adjusted_exponent": MAX_ADJUSTED_EXPONENT,
            "min_exponent": MIN_EXPONENT, "max_digit_run": MAX_DIGIT_RUN,
            "max_canonical_amount_bytes": MAX_CANONICAL_AMOUNT_BYTES, "money_scale": "0.01",
            "signed_zero": "canonicalises to 0",
        },
        "strings": dict(STRING_POLICY),
        "text_limits": {"max_codepoints": TEXT_MAX_CODEPOINTS, "ref_max_codepoints": REF_MAX_CODEPOINTS,
                        "max_bytes": TEXT_MAX_BYTES, "forbidden_categories": sorted(FORBIDDEN_CATEGORIES),
                        "caps_checked": "code points before NFC; code points and UTF-8 bytes after NFC"},
        # NFC and the general categories come from the runtime's Unicode
        # database; a Python upgrade can change what is accepted and how it
        # canonicalises, so the database is part of the policy's identity.
        "unicode": {"database_version": unicodedata.unidata_version,
                    "normaliser": "stdlib unicodedata", "storage_identity": "NFC"},
        "outcome": {"max_diagnostics": MAX_OUTCOME_DIAGNOSTICS, "max_total": MAX_TOTAL_DIAGNOSTICS,
                    "location_sentinel": -1},
    }


def scorer_contract_view(snapshot=None) -> dict:
    """What decides how an accepted candidate is SCORED, as declared data —
    separate from the parse policy, which owns only safety, representability,
    normalisation and the candidate schema. Reward disposition is contextual
    (an entry's role, then the field), and the entity matcher's policy lives
    here because it affects payee matching, not admissibility: a matcher
    change invalidates score caches without invalidating parse certificates.

    With a `PolicySnapshot`, the view is built from the FROZEN registries the
    environment was minted with, never from the live module dicts: the
    scorer consults the snapshot only, so a registry mutated after minting
    (or during scoring, from another thread) changes nothing it reads."""
    from . import mapping, policy

    if snapshot is None:
        policy.validate_policy_requirements()      # contract construction fails on an unpreserved reduction
        requirements = {task: dict(needs) for task, needs in policy.POLICY_REQUIREMENTS.items()}
        comparison = {name: dict(spec) for name, spec in COMPARISON_POLICIES.items()}
        reductions = {code: list(r) for code, r in FINDING_REDUCTIONS.items()}
    else:
        requirements = snapshot.requirements_view()
        comparison = snapshot.comparison_view()
        reductions = snapshot.reductions_view()
    return {
        "scorer_contract_version": SCORER_CONTRACT_VERSION,
        "semantic_fingerprint_version": SEMANTIC_FINGERPRINT_VERSION,
        "engines": [RAW_TEXT_ENGINE.id, CANDIDATE_ENGINE.id],
        "policy_requirements": requirements,
        "comparison_policies": comparison,
        "entity_matching_version": ENTITY_MATCHING_VERSION,
        "unicode_database_version": unicodedata.unidata_version,
        "finding_summary": {
            "reductions": reductions,
            "saturation": MAX_FINDING_COUNT, "sample": MAX_FINDING_SAMPLE,
            "sample_selection": "lowest canonical (code, facts, message) bytes",
            "policy_reads": "presence only (declared per task in policy.POLICY_REQUIREMENTS)",
        },
        "allocation": {
            "order": "canonical occurrence order: occurrences sorted by their structural canonical bytes "
                     "without parser position; identical entries tie and are interchangeable",
            "step_1_preservation": "consume min(original count, submitted count) per occurrence key, in order",
            "step_1b_expected_counts": "preservation counts are the CORRECT books': the original minus the wrong entry of a "
                                       "planted alteration and one copy of a planted duplicate; removing retired content is "
                                       "the repair, not tampering",
            "step_1c_stale": "retired original content still present is STALE: explained (rendered from the original), "
                             "never labelled; the item that retired it stays unresolved while any remains",
            "step_2_planted": "task order; each planted item takes at most one unconsumed eligible occurrence; "
                              "kinds: omit (record the entry), alter (record the corrected entry, retire the wrong one), "
                              "duplicate (remove one copy: resolved iff one copy is preserved and none is stale)",
            "eligibility": {"raw-text/1": ["date", "exact posting multiset by value", "flag *"],
                            "candidate/1": ["date", "exact posting multiset by value"]},
            "quality_key": "an occurrence whose payee satisfies planted_repair.payee first, then canonical order",
            "step_3_unexplained": "every remaining occurrence",
            "unallocated_repair_shaped": "unexplained addition (fabrication penalty), never also undocumented",
            "one_penalty_label_per_occurrence": True,
            "posting_order": "ignored everywhere: the occurrence key sorts postings",
            "deliverable": "rendered only for a FULLY EXPLAINED record (every occurrence preserved or planted; "
                           "lifecycle, title and operating currency unchanged; no account outside the chart); "
                           "otherwise the outcome is non-renderable, no artifact is delivered and the official "
                           "reward is the non-renderable cap (0); components remain as diagnostics",
            "rendering": "preserved entries and the chart print from the ORIGINAL; planted repairs print the graph's "
                         "payee and narration; nothing authored reaches the deliverable except by exact preservation",
            "disjointness": "planted predicates pairwise disjoint and disjoint from originals, audited at initialisation",
        },
        # A ONE-WAY coverage alarm over a declared overlap taxonomy, not
        # "validator agreement": green means Beancount reported no overlap
        # category our validator missed.
        "oracle_adapter": {
            "version": 1, "library": "beancount", "library_version": _beancount_version(),
            "locale": "en (Beancount emits English messages; no localisation)",
            "needles": {category: needle for category, (needle, _) in ORACLE_PROJECTION.items()},
            "projection": {category: sorted(codes) for category, (_, codes) in ORACLE_PROJECTION.items()},
            "semantics": "one-way coverage alarm: oracle-reported overlap category missing from the normative "
                         "validator is an evaluator failure; unmapped diagnostics are telemetry (counted)",
        },
        "reward_dependencies": {f"{role}.{field}": disposition
                                for (role, field), disposition in mapping.REWARD_DEPENDENCIES.items()},
        "text_only_channels_being_retired": sorted(
            name for name, dims in mapping.FIELD_DIMENSIONS.items() if dims["reward"] == "text_only"),
    }


def scorer_contract_digest(snapshot=None) -> str:
    return domain_digest(b"piv:scorer-contract:v1\0", canonical_bytes(scorer_contract_view(snapshot)))


SCORE_RESULT_DOMAIN = b"piv:score-result:v1\0"
SCORE_REDUCTION_VERSION = 1      # weights, penalties, cap, clamp and rounding of the candidate/1 reduction


def score_result_digest(result_canonical: dict) -> str:
    """What was RETURNED: the exact component vector, every penalty label,
    the total, gating and renderability, the cap, the allocation, the
    reduction version and the input digests. Bound into the delivery
    receipt so a recorded result that no longer reproduces this digest is
    refused at re-finalisation."""
    return domain_digest(SCORE_RESULT_DOMAIN, canonical_bytes({"reduction_version": SCORE_REDUCTION_VERSION,
                                                               **result_canonical}))


def parse_policy_digest() -> str:
    return domain_digest(PARSE_POLICY_DOMAIN, canonical_bytes(parse_policy_view()))


def task_contract_view(task: dict) -> dict:
    """The task's normative declared data. `_..._doc` keys are documentation
    and are excluded; everything else is the contract."""
    return {
        "task_contract_version": TASK_CONTRACT_VERSION,
        "scorer_contract": scorer_contract_view(),
        "task": {k: v for k, v in task.items() if not k.startswith("_")},
    }


def task_contract_digest(task: dict) -> str:
    return domain_digest(TASK_CONTRACT_DOMAIN, canonical_bytes(task_contract_view(task)))
