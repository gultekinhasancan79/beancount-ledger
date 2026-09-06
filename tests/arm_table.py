"""The decision table — reads
archived `reviews/budget_*_*.json` rows and reports, per stratum, TWO
pre-registered delivery estimands, a four-bucket failure classification, and
cost both conditional and operational.

    python tests/arm_table.py --label confirm1v2 --schedule reviews/schedule_confirm1v2.json
    python tests/arm_table.py --tag-prefix Ap_ B1p_ B2p_ --label pilot-2026-08-30 --pilot

WHAT CHANGED AND WHY

1. **No stored string is trusted**. `is_actually_valid`
   used to check that the status string said VALID and that a few fields
   were present. Every row now goes through ONE pure validator,
   `measure_budget.validate_row`, which re-derives every predicate — integer
   types, per-turn caps, cumulative equality, the episode ceiling, exact
   wire cardinality, request/turn cardinality, attempt identity, artifact
   consistency — from the row's own archived fields. The writer runs the
   same function on the row it produces.

2. **`VALID/derived` is diagnostic only**. A row missing
   the corrected native cap/usage capture enters a `--pilot` table and never
   a confirmatory one.

3. **Contracts are refused, not warned about**. Rows with
   different `replay_contract_digest` or different `episode_contract_digest`
   inside one condition are an ERROR: the table is not produced. Two rows
   can share a world, a prompt and a ceiling and still not be comparable
   because the client replayed the conversation differently.

4. **Two estimands**, never one:
     - CONDITIONAL model-delivery rate: correct deliveries among accounting-
       valid, provider-completed attempts. Answers "when the configuration
       ran to completion, did the model deliver?"
     - SCHEDULED operational-delivery rate: correct deliveries over every
       scheduled cell, with arm-induced failures counted as NON-delivery.
       Answers "if I schedule this arm, what fraction delivers?" — the
       question an arm that fails more often would otherwise win by, since
       excluding its failures makes it look both cheaper and better.

5. **Four failure buckets, applied blind**. `classify_error`
   sees only the recorded error text and the observed request size — never
   the arm, never the reward — so a classification cannot be steered by the
   outcome it is about to explain.

6. **Suspicious is not invalid**. The characters-per-token
   heuristic can fire differently across arms (a replay arm changes the
   shape of emitted content), so it never invalidates a row. Every table is
   printed twice, with and without suspicious rows.

7. **Tokens are never pooled across providers**. One provider's token is
   not another's. Ratios are computed
   WITHIN (provider, model); the cross-model section reports wall time,
   request counts and provider-specific tokens side by side and computes no
   pooled ratio at all.

Four more things changed later, all of them refusals:

8. **The confirmatory dataset is the schedule's exact cell map**. No
   tag-substring globbing, exactly one exactly-matching row per cell, and a
   hard refusal for a duplicate, a partial identity or an unregistered file
   carrying the schedule's label. Every denominator comes from that map.
   Completion is DERIVED from it; `--schedule-complete` is refused.

9. **The 429 rule is an observation, not a thought experiment**. The
   retired rule asked whether one request, repeated every `min_interval`
   seconds, WOULD saturate the provider's minute. The rule now reads the
   trailing-60-second window `measure_budget` archived on the rejected
   attempt itself, and distinguishes "this cell filled the window" from
   "the cell before it did" — the carry-over case the old rule could not
   express. Structured HTTP status and provider error codes feed the blind
   map ahead of any free text.

10. **Capability incompatibility excludes a CONFIGURATION**, whole and
    by name, never the individual blocks that happened to fail.

11. **The primary contrast is printed TWICE** — all eligible rows and
    excluding suspicious rows, whole triplets dropped after each filter —
    with the blocks lost and any sign/ranking change stated; and the
    effective-cost ratio carries bootstrapped uncertainty: P(zero
    correct) per arm, P(dominance), and a labelled CONDITIONAL interval,
    never an unconditional one built by silently dropping the undefined
    resamples.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import measure_budget as mb  # noqa: E402 -- the ONE row validator lives there
import schedule_arms as SA  # noqa: E402 -- the schedule and the balance census

FILENAME_RE = re.compile(r"^budget_(?P<slug>.+)_(?P<date>\d{4}-\d{2}-\d{2})(?:_(?P<tag>.+))?\.json$")

# ---------------------------------------------------------------------------
# Failure classification (hardened after an adversarial
# verification). A FIXED map to four buckets plus an explicit ambiguous set,
# applied BLIND: nothing here ever sees the arm, the reward or the delivery
# outcome.
#
# WHAT THE VERIFIER BROKE, AND THE STRUCTURAL FIX. The map used to be a list
# of substrings scanned over one flat blob, and the blob had grown to include
# the archived RATE-LIMIT HEADER VALUES. Numeric needles ("413", "500", "401")
# then matched digits that were never a status code:
#
#     429 + `ratelimitbysize-limit: 937500`  -> "500" hit  -> exogenous/server_error
#     429 + `retry-after: 413`               -> "413" hit  -> arm_induced/request_too_large
#     a transient 500 EARLIER in the same row outranked the fatal 429
#
# Two of the four panel models publish a TPM containing "500" (937,500 and
# 625,000... and 356,250 contains none, but 1,000,000 does not save you
# either: `retry-after` is a small integer that can BE 413 or 503). The
# misclassification is decision-bearing in both directions: `exogenous` drops
# the row AND its whole triplet from the paired contrast, while a fabricated
# `arm_induced` charges the arm with a failure it did not cause.
#
# The fix is structural, not another needle:
#
#   1. a numeric HTTP class may ONLY ever match an archived STATUS FIELD
#      (`http_status`), never a substring of any text (`HTTP_STATUS_RULES`);
#   2. classification reads the FATAL attempt — the LAST non-ok entry in the
#      request log, the one that actually ended the rollout — not a blob of
#      every attempt's text;
#   3. header VALUES never enter any scanned text. Their KEYS are archived
#      and displayed as evidence, and that is all;
#   4. the free-text scan is a FALLBACK, used only when no structured status
#      exists, and it now carries no numeric needles at all.
# ---------------------------------------------------------------------------

FAILURE_BUCKETS = ("exogenous", "capability_incompatible", "arm_induced", "instrument_invalid", "ambiguous")

# NUMERIC classes, matched ONLY against an archived `http_status` integer.
# 429 is deliberately absent: it is decided by the observed rolling window
# (`window_verdict`), never by the status alone. 400/422 are absent too —
# they are the codes a capability incompatibility and a context overflow
# share, and only the message distinguishes them.
HTTP_STATUS_RULES = {
    413: ("arm_induced", "request_too_large"),
    401: ("exogenous", "auth"),
    403: ("exogenous", "auth"),
    500: ("exogenous", "server_error"),
    502: ("exogenous", "server_error"),
    503: ("exogenous", "server_error"),
    504: ("exogenous", "server_error"),
}

# (bucket, rule, substrings) over the FATAL attempt's message (or, with no
# structured status at all, the rollout-level prose). FIRST match in this
# order wins, and a capability incompatibility is recognised BEFORE any
# status class — that ordering is part of the pre-registration
# (reviews/confirmatory_design.md §8). NO NEEDLE HERE IS A NUMBER.
CAPABILITY_RULES = (
    ("capability_incompatible", "missing_continuation_field",
     ("thought_signature", "thought signature", "functioncall parts")),
    ("capability_incompatible", "replayed_field_rejected",
     ("extra_forbidden", "extra fields not permitted", "unexpected keyword", "unrecognized field")),
)
ERROR_CLASS_RULES = CAPABILITY_RULES + (
    ("arm_induced", "request_too_large",
     ("request entity too large", "payload too large", "request too large", "body too large")),
    ("arm_induced", "context_overflow",
     ("context length", "context_length", "maximum context", "too many tokens", "input is too long",
      "prompt is too long", "reduce the length")),
    ("arm_induced", "invalid_model_response",
     ("invalidmodelresponse", "invalid model response", "empty response", "empty completion",
      "no completion", "malformed tool call")),
    ("arm_induced", "quota_request_size", ("insufficient_quota", "quota exceeded for tokens")),
    ("exogenous", "auth", ("unauthorized", "invalid api key", "authentication")),
    ("exogenous", "server_error",
     ("internal server error", "bad gateway", "service unavailable", "overloaded",
      "server had an error")),
    ("exogenous", "connection",
     ("apiconnectionerror", "connection error", "connection reset", "connectionerror", "ssl",
      "remote end closed")),
)

# THE OBSERVED ROLLING-WINDOW RULE. What it replaced, and
# why:
#
#   the retired rule:  S >= TPM * I / 60
#
# asked whether the largest request, HYPOTHETICALLY repeated once every `I`
# seconds for a minute, would reach the provider's tokens-per-minute limit.
# That is a thought experiment, not a measurement. A single 120K request does
# not consume a 356K minute; the rule called it `arm_induced` because ten
# copies of it would have. And the converse error is worse: a SMALL request
# rejected right after a large one from the PREVIOUS CELL was called
# `exogenous`, although the experiment's own traffic is exactly what filled
# the window. Each scheduled cell is a fresh subprocess, so nothing in the
# old instrument could even see the previous cell's requests.
#
# The rule is now an observation. `measure_budget` maintains a shared
# provider-window LEDGER across cells; at the instant a 429 is received it
# archives the trailing-60 s window on the attempt: how many tokens (and
# requests) the experiment sent to this (provider, model), and how many of
# them were THIS cell's. The classification is then:
#
#   window unknown (no snapshot)                   -> ambiguous/rate_limit_window_unknown
#   quota unknown (no TPM and no RPM for the model)-> ambiguous/rate_limit_quota_unknown
#   every established dimension below quota        -> exogenous/rate_limit_window_not_saturated
#   a dimension saturated, this cell the MAJORITY  -> arm_induced/rate_limit_window_saturated_*
#   a dimension saturated, this cell a MINORITY    -> ambiguous/rate_limit_carryover_*
#   saturated dimensions DISAGREE                  -> ambiguous/rate_limit_dimensions_disagree
#   only rejected/current requests could cross it  -> ambiguous/rate_limit_current_request_uncertain_*
#
# The carry-over line is the case the retired rule could not express at all:
# the window was genuinely exhausted, but mostly by the arm that ran BEFORE
# this one, so charging the failure to this arm would be an attribution the
# evidence does not support.
#
# TWO LATER CORRECTIONS, both decision-bearing:
#
#   (a) BILLED USAGE, REJECTED ESTIMATES AND THE CURRENT REQUEST ARE THREE
#       DIFFERENT CLAIMS. `window_snapshot` used to fold a rejected request's
#       chars/4 estimate into the same number as the provider's own billed
#       usage (`if not billed: billed = estimated_request_tokens`). Repeated
#       backoffs could then manufacture a "saturated" window out of estimates
#       alone and charge an external rate limit to an arm. They are separate
#       fields now, and `dimension_verdict` treats billed usage as the
#       established quantity and everything else as an upper bound, because
#       whether a rejected request consumes quota is UNDOCUMENTED
#       (`ADMISSION_SEMANTICS`). The snapshot on the fatal attempt also
#       excluded the request being refused, so a window below quota that the
#       current request would have crossed was called `exogenous`; both the
#       pre-request and the prospective window are archived now, and the
#       uncertainty produces `ambiguous`, not `exogenous`.
#
#   (b) TPM AND RPM ARE EVALUATED INDEPENDENTLY. The retired code asked about
#       tokens first and never looked at requests when tokens saturated, so a
#       token window this cell was a minority of could hide a request window
#       it was the majority of (and the reverse). Both dimensions are now
#       decided on their own evidence, both verdicts are recorded on the
#       attempt, and the combination is conservative: disagreement is
#       ambiguous, not a silent preference for one dimension.
RATE_LIMIT_WINDOW_SECONDS = 60
WINDOW_RULE_VERSION = 3
#: How much of the saturating window this cell must itself have sent before
#: the 429 is charged to its arm. A strict majority: "the arm's own traffic is
#: the rate limit" is a causal claim, and half the window is the weakest
#: threshold that supports it.
ARM_INDUCED_MAJORITY_SHARE = 0.5

#: The version of the CLASSIFICATION ALGORITHM itself — not of the tuples it
#: reads. The free-text fallback lived outside every hashed
#: constant, so a change to it (such as the bare three-digit rate-limit needle
#: this version removes) moved no digest and invalidated no schedule.
#: `failure_map_digest`
#: now hashes this string and the needles below, so the fallback BEHAVIOUR is
#: bound to `schedule_id` like everything else.
CLASSIFIER_ALGORITHM_VERSION = "T50.3-window-bounds-two-dimensions"

#: The ONLY needles that may reach the rate-limit rule from free text, used
#: when the row archived no structured `http_status` at all. Every one of them
#: is a TYPED name or an English phrase; NOT ONE CONTAINS A DIGIT. The retired
#: needle this version removes is exactly the class of bug the header-value
#: finding was meant to end: a provider request id, a quota number or a header
#: value containing those digits is not a status code, and free text is not a
#: status field.
RATE_LIMIT_TEXT_NEEDLES = ("ratelimiterror", "ratelimit", "rate limit", "rate_limit",
                           "too many requests")

#: Mistral's console publishes the LIMITS; it does not
#: document whether a request the gateway rejects with a 429 consumes token or
#: request quota, nor whether admission is decided on a tokenizer estimate of
#: the request about to be sent. That is sealed as an explicit UNKNOWN, and it
#: is what forbids treating a rejected request's estimate as consumed quota.
ADMISSION_SEMANTICS = "undocumented"

#: The separated evidence a window snapshot must carry before any attribution
#: may be read from it. A snapshot that carries only the old
#: conflated `window_tokens_total` cannot support a causal claim and is
#: classified `ambiguous/rate_limit_window_evidence_unseparated`.
WINDOW_EVIDENCE_FIELDS = ("billed_tokens_total", "billed_tokens_this_cell",
                          "rejected_estimate_tokens_total", "rejected_estimate_tokens_this_cell",
                          "accepted_requests_total", "accepted_requests_this_cell",
                          "rejected_requests_total", "rejected_requests_this_cell",
                          "current_request_present", "current_request_estimate_tokens")
#: The snapshot taken BEFORE the rejected request was appended to the ledger,
#: and the one that includes it — archived together on the fatal attempt and
#: labelled, so the report can show both without either standing in for the
#: other.
WINDOW_KIND_PRE_REQUEST = "pre_request"
WINDOW_KIND_PROSPECTIVE = "prospective_including_current_request"

#: The provider's own published limits, read from the user's Mistral console
#: on this date. `rps` is what the console names; `rpm` is `rps * 60`, the
#: unit a 429 window is counted in. A model absent from this table has NO
#: established quota and its 429s stay `ambiguous` — never guessed.
QUOTA_SOURCE = "Mistral provider console, read 2026-08-30"
MODEL_QUOTAS = {
    ("mistral", "devstral-2512"): {"tpm": 1_000_000, "rps": 0.83},
    ("mistral", "ministral-14b-2512"): {"tpm": 937_500, "rps": 0.50},
    ("mistral", "ministral-8b-2512"): {"tpm": 625_000, "rps": 3.13},
    ("mistral", "mistral-medium-2508"): {"tpm": 356_250, "rps": 0.38},
    ("gemini", "gemini-2.5-flash"): {"tpm": 250_000, "rps": 10.0 / 60.0},
}
# Fallbacks for a provider whose per-model limits were never read from a
# console. `None` means "not established" and forces AMBIGUOUS.
PROVIDER_TPM_DEFAULTS = {"mistral": None, "gemini": 250_000, "nvidia": None,
                         "groq": 8_000, "zai": None, "cohere": None}


def tpm_limit(provider, model):
    quota = MODEL_QUOTAS.get((provider, model))
    if quota and quota.get("tpm"):
        return quota["tpm"]
    return PROVIDER_TPM_DEFAULTS.get(provider)


def rpm_limit(provider, model):
    """Requests per minute — `rps × 60` from the console table (a 429 is
    classified against BOTH the token and the request window, because
    either can produce it). `None` when unestablished."""
    quota = MODEL_QUOTAS.get((provider, model))
    if not quota or not quota.get("rps"):
        return None
    return quota["rps"] * 60.0


def _number(value, default=None):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def dimension_verdict(window: dict, dimension: str, quota) -> dict:
    """What ONE quota dimension (tokens or requests) establishes about this
    429, as BOUNDS rather than as a single number.

    Two different claims used to be added together: what the provider BILLED
    for requests it accepted, and an estimate of the size of requests it
    REFUSED. Only the first is established consumption. Whether a rejected
    request consumes quota at all is `ADMISSION_SEMANTICS` — undocumented —
    so it may widen an upper bound and can never raise the established one.

      established (`lo`)  billed tokens / accepted requests: fact
      upper bound (`hi`)  `lo` + rejected estimates + the CURRENT request,
                          i.e. what consumption could be if every rejected
                          attempt and the request being refused right now all
                          counted against the quota

    and the state is then:

      `unestablished`  no quota is pinned for this model — nothing to say
      `saturated`      `lo >= quota`: the quota is reached on billed fact alone
      `uncertain`      `lo < quota <= hi`: it could have been crossed only if
                       rejected/current attempts count, which is undocumented
      `below`          `hi < quota`: below the quota even under the widest
                       admission rule
    """
    if dimension == "tokens":
        lo = _number(window.get("billed_tokens_total"))
        mine = _number(window.get("billed_tokens_this_cell"), 0)
        rejected = _number(window.get("rejected_estimate_tokens_total"), 0) or 0
        mine_rejected = _number(window.get("rejected_estimate_tokens_this_cell"), 0) or 0
        current = (_number(window.get("current_request_estimate_tokens"), 0) or 0
                   if window.get("current_request_present") else 0)
        unit = "tokens"
    else:
        lo = _number(window.get("accepted_requests_total"))
        mine = _number(window.get("accepted_requests_this_cell"), 0)
        rejected = _number(window.get("rejected_requests_total"), 0) or 0
        mine_rejected = _number(window.get("rejected_requests_this_cell"), 0) or 0
        # Its OWN boolean (adversarial review, INFO). Deriving "a request is
        # in flight" from the presence of a TOKEN ESTIMATE conflates two
        # facts: a request whose size could not be estimated is still a
        # request, and would silently have lost its +1 against the RPM bound.
        current = 1 if window.get("current_request_present") else 0
        unit = "requests"
    # A PROSPECTIVE snapshot already carries the current request inside its
    # own totals; adding it again would double count it.
    if window.get("window_kind") == WINDOW_KIND_PROSPECTIVE:
        current = 0
    out = {"dimension": dimension, "unit": unit, "quota": quota,
           "established": lo, "this_cell_established": mine,
           "rejected_estimate": rejected, "rejected_estimate_this_cell": mine_rejected,
           "current_request": current, "upper_bound": None, "share": None,
           "state": "unestablished", "attribution": None, "verdict": None}
    if lo is None:
        out["note"] = "the snapshot does not carry this dimension's established consumption"
        return out
    out["upper_bound"] = lo + rejected + current
    if not quota:
        out["note"] = "no quota is established for this (provider, model) — nothing may be read from it"
        return out
    if lo >= quota:
        out["state"] = "saturated"
        out["share"] = (mine / lo) if lo else None
        majority = bool(lo) and mine > ARM_INDUCED_MAJORITY_SHARE * lo
        out["attribution"] = "this_cell_majority" if majority else "carryover"
        out["verdict"] = (("arm_induced", f"rate_limit_window_saturated_{dimension}") if majority
                          else ("ambiguous", f"rate_limit_carryover_{dimension}"))
        out["note"] = (f"billed/accepted {unit} alone reach the quota ({lo} >= {quota}); this cell sent "
                       f"{mine} of them")
    elif out["upper_bound"] >= quota:
        out["state"] = "uncertain"
        out["verdict"] = ("ambiguous", f"rate_limit_current_request_uncertain_{dimension}")
        out["note"] = (f"established {unit} {lo} are below the quota {quota}, but {lo} + rejected "
                       f"{rejected} + current {current} = {out['upper_bound']} could cross it, and "
                       f"whether a rejected request consumes quota is {ADMISSION_SEMANTICS}")
    else:
        out["state"] = "below"
        out["note"] = (f"even counting every rejected attempt and the current request, {unit} reach at "
                       f"most {out['upper_bound']} against a quota of {quota}")
    return out


def combine_dimension_verdicts(dimensions: list[dict]) -> tuple[str, str]:
    """The CONSERVATIVE combination of the per-dimension verdicts. The
    retired rule looked at tokens first and, if tokens saturated,
    never looked at requests at all — so a token window this cell was a
    minority of could hide a request window it was the majority of, and the
    reverse.

      * `arm_induced` only when a SATURATED dimension is majority-this-cell
        and no OTHER saturated dimension contradicts it;
      * `ambiguous` when saturated dimensions disagree, or when the only way
        a quota could have been crossed is through undocumented admission of
        rejected/current requests;
      * `exogenous` only when EVERY established dimension is demonstrably
        below its quota after the current-request uncertainty is handled.
    """
    established = [d for d in dimensions if d["state"] != "unestablished"]
    if not established:
        return "ambiguous", "rate_limit_quota_unknown"
    saturated = [d for d in established if d["state"] == "saturated"]
    if saturated:
        attributions = {d["attribution"] for d in saturated}
        names = "+".join(d["dimension"] for d in saturated)
        if attributions == {"this_cell_majority"}:
            return "arm_induced", f"rate_limit_window_saturated_{names}"
        if attributions == {"carryover"}:
            return "ambiguous", f"rate_limit_carryover_{names}"
        return "ambiguous", "rate_limit_dimensions_disagree"
    uncertain = [d for d in established if d["state"] == "uncertain"]
    if uncertain:
        return "ambiguous", ("rate_limit_current_request_uncertain_"
                             + "+".join(d["dimension"] for d in uncertain))
    return "exogenous", "rate_limit_window_not_saturated"


def window_dimension_verdicts(window: dict | None, tpm=None, rpm=None) -> dict:
    """Everything the observed window establishes, per dimension AND combined
    — the structure the evidence table renders and the classifier reads.

    Nothing here consults the arm, the reward or the delivery outcome."""
    out = {"tokens": None, "requests": None, "combined": ("ambiguous", "rate_limit_window_unknown"),
           "window_kind": None, "evidence": "no window snapshot was archived on the attempt"}
    if not isinstance(window, dict):
        return out
    out["window_kind"] = window.get("window_kind")
    if window.get("evidence_incomplete"):
        # The shared ledger was recovered after malformed evidence: entries
        # are missing from this window by construction, so no
        # attribution may be read from it at all.
        out["combined"] = ("ambiguous", "rate_limit_evidence_incomplete")
        out["evidence"] = ("the window ledger was recovered inside this window, so its evidence is "
                           "incomplete by construction")
        return out
    if not any(field in window for field in WINDOW_EVIDENCE_FIELDS):
        out["combined"] = ("ambiguous", "rate_limit_window_evidence_unseparated")
        out["evidence"] = ("the snapshot conflates billed usage with rejected-request estimates "
                           "(pre-T50 shape); no causal attribution may be read from it")
        return out
    tokens = dimension_verdict(window, "tokens", tpm)
    requests = dimension_verdict(window, "requests", rpm)
    out["tokens"], out["requests"] = tokens, requests
    if tokens["established"] is None and requests["established"] is None:
        out["combined"] = ("ambiguous", "rate_limit_window_unknown")
        out["evidence"] = "the snapshot carries neither billed tokens nor accepted requests"
        return out
    out["combined"] = combine_dimension_verdicts([tokens, requests])
    out["evidence"] = " | ".join(f"{d['dimension']}: {d['state']} ({d.get('note', '')})"
                                 for d in (tokens, requests))
    return out


def window_verdict(window: dict | None, tpm=None, rpm=None) -> tuple[str, str]:
    """`(bucket, rule)` for a 429 — the conservative combination of the token
    and request dimensions, each evaluated independently on bounds."""
    return window_dimension_verdicts(window, tpm, rpm)["combined"]


def classify_error(text: str, request_tokens=None, tpm=None, min_interval=None,
                   window=None, rpm=None, http_status=None) -> tuple[str, str]:
    """`(bucket, rule)` from the recorded error text and the OBSERVED provider
    window. BLIND by construction: this function is never given the arm, the
    reward or the delivery outcome, so no classification can be steered by
    what it is about to explain.

    `request_tokens` and `min_interval` are retained for the audit trail and
    for callers written against the old signature; the 429 decision no longer
    reads them, because a request's own size never was evidence about a
    rolling window (see the module comment above).

    `http_status` is the ONLY input a numeric class may be decided from. Text
    is scanned for PHRASES only — the numeric needles are gone, because a
    number found in free text is not a status code (see the module comment:
    `retry-after: 413` is not a 413)."""
    blob = (text or "").lower()
    if not blob.strip() and http_status is None:
        return "ambiguous", "no_error_text"
    # 1. Capability incompatibility outranks every status class: a 400 or a
    #    422 that names a replayed or a required continuation field is a
    #    client/provider incompatibility, not a generic 4xx.
    for bucket, rule, needles in CAPABILITY_RULES:
        if any(needle in blob for needle in needles):
            return bucket, rule
    # 2. The archived STATUS, when there is one. 429 goes to the observed
    #    window; the rest come from the numeric table, which no text can
    #    reach.
    if http_status == 429:
        return window_verdict(window, tpm, rpm)
    if isinstance(http_status, int) and http_status in HTTP_STATUS_RULES:
        return HTTP_STATUS_RULES[http_status]
    # 3. Phrases, for a status this table does not name (400/422) and for a
    #    row that archived no status at all.
    for bucket, rule, needles in ERROR_CLASS_RULES:
        if any(needle in blob for needle in needles):
            return bucket, rule
    if any(needle in blob for needle in RATE_LIMIT_TEXT_NEEDLES):
        # NONNUMERIC TYPED EVIDENCE ONLY. The retired form of
        # this line tested the bare rate-limit status digits as a substring of
        # the blob. That test sat outside `ERROR_CLASS_RULES` and therefore
        # outside the "no digit in any map needle" witness, so a row with no
        # structured status whose free text merely CONTAINED those digits — a
        # request id, a quota, a header value the provider chose — could reach
        # the rate-limit rule, which is the identical bug to the one the
        # header-value finding closed.
        return window_verdict(window, tpm, rpm)
    if "timeout" in blob or "timed out" in blob:
        # A single timeout cannot demonstrate the "deterministic timeout
        # caused by an arm's growing context" that would make it arm-induced,
        # and calling it exogenous asserts an absence of arm cause that is
        # equally unverified. It goes to the sensitivity set, by name.
        return "ambiguous", "timeout_unverifiable"
    if isinstance(http_status, int):
        return "ambiguous", f"http_{http_status}_unmatched"
    return "ambiguous", "unmatched"


def observed_request_tokens(row: dict):
    """The largest provider request this row is known to have made, in input
    tokens — from the per-HTTP-attempt log first (present even on a row that
    never produced a trajectory, and carrying an ESTIMATE for the attempts the
    provider refused, which bill nothing), then from the per-turn
    accounting."""
    sizes = []
    for request in row.get("requests") or []:
        for key in ("billed_input_tokens", "estimated_request_tokens"):
            value = request.get(key)
            if isinstance(value, int):
                sizes.append(value)
    for turn in row.get("per_turn") or []:
        value = turn.get("input_tokens")
        if isinstance(value, int):
            sizes.append(value)
    return max(sizes) if sizes else None


def rate_limit_window(row: dict):
    """The observed trailing window archived on this row's LAST rate-limited
    attempt, or `None`. Structured evidence, recorded at the moment of the
    refusal — never recomputed later from a ledger file that has since grown
    past the minute in question."""
    fatal = fatal_attempt(row)
    if isinstance(fatal, dict) and isinstance(fatal.get("provider_window"), dict):
        return fatal["provider_window"]        # the window of the failure that ENDED the rollout
    latest = None
    for request in row.get("requests") or []:
        if not isinstance(request, dict) or request.get("status") != "rate_limited":
            continue
        window = request.get("provider_window")
        if isinstance(window, dict):
            latest = window
    return latest


def rate_limit_window_prospective(row: dict):
    """The PROSPECTIVE window archived beside the pre-request one on the fatal
    attempt: the same trailing minute INCLUDING the
    request the provider is refusing right now, labelled as such so it can be
    shown without ever being read as billed usage."""
    fatal = fatal_attempt(row)
    if isinstance(fatal, dict) and isinstance(fatal.get("provider_window_prospective"), dict):
        return fatal["provider_window_prospective"]
    latest = None
    for request in row.get("requests") or []:
        if not isinstance(request, dict) or request.get("status") != "rate_limited":
            continue
        window = request.get("provider_window_prospective")
        if isinstance(window, dict):
            latest = window
    return latest


def fatal_attempt(row: dict) -> dict | None:
    """The LAST non-`ok` entry in the request log — the attempt that actually
    ended the rollout — or `None` when the log holds no failure.

    The previous version folded EVERY failed attempt's text into one blob, so
    a transient 500 that the pacing loop retried past outranked the fatal 429
    that followed it, purely because `server_error` sat earlier in the rule
    order. A rollout is ended by one failure; that one is the evidence."""
    fatal = None
    for request in row.get("requests") or []:
        if not isinstance(request, dict) or request.get("status") == "ok":
            continue
        fatal = request
    return fatal


def attempt_message(request: dict | None) -> str:
    """The scannable text of ONE attempt: the provider's message, its error
    code/type and the exception class.

    `rate_limit_headers` is deliberately NOT here. Header VALUES are numbers
    the provider chose — a token limit of 937,500, a `retry-after` of 413 —
    and letting them into a text scan is exactly how `429` became
    `exogenous/server_error` and `arm_induced/request_too_large`. The keys
    are archived and displayed as evidence (`rate_limit_header_keys`); no
    value is ever matched against anything."""
    if not isinstance(request, dict):
        return ""
    parts = []
    for key in ("error_message", "provider_error_code", "provider_error_type", "error_class"):
        value = request.get(key)
        if value not in (None, ""):
            parts.append(str(value))
    return " ".join(parts)


def rate_limit_header_keys(row: dict) -> list[str]:
    """Which rate-limit headers the provider sent on the fatal attempt —
    presence only, for the audit table. Values are never returned here."""
    headers = (fatal_attempt(row) or {}).get("rate_limit_headers")
    return sorted(headers) if isinstance(headers, dict) else []


def structured_error_text(row: dict) -> str:
    """The FATAL attempt's own structured message — a causal arm label is
    never inferred from a free-text substring when structured status is
    available. One attempt, no headers, no values."""
    return attempt_message(fatal_attempt(row))


def failure_text(row: dict) -> str:
    """Everything the row recorded about WHY it failed, and nothing about
    what it was trying to do. The fatal attempt's structured message comes
    FIRST; the rollout-level prose is the fallback behind it."""
    parts = [structured_error_text(row),
             str(row.get("status") or ""), str(row.get("error") or ""), str(row.get("reasons") or ""),
             str(row.get("batch_status") or "")]
    return " ".join(p for p in parts if p and p != "None")


def classify_row(row: dict) -> tuple[str, str]:
    """`(bucket, rule)` for a row that did NOT deliver cleanly, or
    `(None, None)` for one that ran to completion with valid accounting.
    `instrument_invalid` is decided by the validator, not by text.

    The evidence is, in order: the FATAL attempt's archived HTTP status, its
    structured message, and only then the rollout-level prose."""
    if row.get("quarantined") or row.get("error"):
        provider, model = row.get("provider"), row.get("model")
        fatal = fatal_attempt(row)
        status_code = (fatal or {}).get("http_status")
        if not isinstance(status_code, int):
            status_code = None
        # With a structured fatal attempt, the scanned text is THAT attempt's
        # message alone. Only a row that archived no structured failure at
        # all falls back to the rollout-level prose.
        text = attempt_message(fatal) if fatal is not None else failure_text(row)
        if fatal is not None and not text.strip() and status_code is None:
            text = failure_text(row)
        return classify_error(text, observed_request_tokens(row),
                              tpm_limit(provider, model), row.get("min_interval"),
                              window=rate_limit_window(row), rpm=rpm_limit(provider, model),
                              http_status=status_code)
    status, reasons = mb.validate_row(row)
    if status == "INVALID":
        return "instrument_invalid", ",".join(reasons) or "invalid"
    return None, None


# ---------------------------------------------------------------------------
# Row predicates
# ---------------------------------------------------------------------------

def correct_delivery(row: dict) -> bool:
    """THE correct-delivery predicate — defined ONCE,
    here, and used EVERYWHERE a "correct delivery" is counted in this file.

    All three must hold: `artifact == "BOUND"` (this rollout's own workspace
    and `delivery.json` bound the ledger the scorer actually delivered for
    THIS rollout), `reward == 1.0`, and `breakdown["complete"] is True` (the
    scorer's own semantic-completeness flag — independent of reward, and the
    conjunct that answers "was this the correct delivery" rather than "scored
    the maximum available under whatever this attempt tried").

    `submitted` is deliberately NOT a conjunct: under the episode contract an
    unsubmitted last committed revision that scores 1.0 and complete IS a
    delivery. The accepted-submit rate is reported as its own column. The
    prompt and the table should describe the same contract;
    the prompt is the package's, and the open question is recorded in
    `reviews/confirmatory_design.md` rather than silently resolved here.
    """
    if row.get("artifact") != "BOUND" or row.get("reward") != 1.0:
        return False
    breakdown = row.get("breakdown")
    return isinstance(breakdown, dict) and breakdown.get("complete") is True


def is_quarantined(row: dict) -> bool:
    return bool(row.get("quarantined"))


def row_status(row: dict) -> tuple[str, list]:
    return mb.validate_row(row)


def is_suspicious(row: dict) -> bool:
    """Re-derived, never read off the stored field."""
    return mb.row_suspicion(row) is not None


def provider_completed(row: dict) -> bool:
    """The provider ran the whole episode: not quarantined, no rollout-level
    error. The CONDITIONAL estimand's denominator lives here."""
    return not is_quarantined(row) and not row.get("error")


def derive_budget_accounting(row: dict) -> str:
    """Kept for `tests/stamp_contract_digest.py`, now expressed through the
    ONE validator so a stamped verdict and a freshly re-derived one can never
    disagree."""
    status, reasons = mb.validate_row(row)
    if status in ("VALID", "VALID/derived"):
        return status
    return "INVALID/" + (reasons[0] if reasons else "invalid")


def contract_identity(row: dict) -> tuple:
    """The (episode, replay) contract pair a row ran under. Rows whose pairs
    differ are never pooled in one condition."""
    episode = row.get("episode_contract_digest") or row.get("prompt_schema_digest")
    return episode, row.get("replay_contract_digest")


class PoolingRefused(Exception):
    """Raised, never warned: a condition containing rows from
    two different contracts is not a condition."""


class CensusInvariantViolation(Exception):
    """Raised, never warned: the header's derived census and a
    detail section's own recount of the same panel disagree. This is the
    exact defect the reviewer found — the header said "143 of 144 ... 1 unrun"
    while the old `### Scheduled but not run` section, which recomputed
    membership from a tag string that is NOT unique across models sharing
    one (arm, selector, replicate) triple, said "0 of 144". A renderer that
    CAN print a self-contradictory census is not a renderer to trust, so
    `render_table` fails closed on this rather than printing anything."""


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------

def conditional_cost_stats(valid_rows: list[dict]) -> dict:
    """Median and p75 TOTAL tokens among CORRECT DELIVERIES ONLY — the
    survivorship-biased quantity, reported alongside the effective cost and
    never alone. p75 with one data point is that point."""
    totals = [r["total_tokens"] for r in valid_rows if correct_delivery(r) and r.get("total_tokens") is not None]
    if not totals:
        return {"n": 0, "median": None, "p75": None}
    median = statistics.median(totals)
    p75 = statistics.quantiles(totals, n=4, method="inclusive")[2] if len(totals) >= 2 else totals[0]
    return {"n": len(totals), "median": median, "p75": p75}


def billed_tokens(row: dict) -> int:
    """What the provider was actually paid for by this attempt: the
    all-attempts billed totals when the client captured them (they include a
    discarded framework attempt's spend and a failed cell's spend), else the
    row's own reported total."""
    billed_in = row.get("billed_input_tokens_all_attempts")
    billed_out = row.get("billed_output_tokens_all_attempts")
    if isinstance(billed_in, int) or isinstance(billed_out, int):
        return (billed_in or 0) + (billed_out or 0)
    return row.get("total_tokens") or 0


def effective_cost(rows: list[dict], token_fn=lambda r: r.get("total_tokens") or 0) -> float:
    """Tokens spent per CORRECT DELIVERY over the rows handed in — `inf` when
    there are none (a zero-correct arm is DOMINATED,
    reported as `inf`, never stabilised by an undeclared pseudocount)."""
    n_correct = sum(1 for r in rows if correct_delivery(r))
    if n_correct == 0:
        return float("inf")
    return sum(token_fn(r) for r in rows) / n_correct


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def matching_files(reviews_dir: Path, tag_prefixes: list[str]) -> list[Path]:
    files = []
    for path in sorted(reviews_dir.glob("budget_*.json")):
        m = FILENAME_RE.match(path.name)
        if not m or not m.group("tag"):
            continue
        if any(prefix in m.group("tag") for prefix in tag_prefixes):
            files.append(path)
    return files


def load_rows(reviews_dir: Path, tag_prefixes: list[str]) -> tuple[list[dict], list[Path]]:
    """PILOT loading: every file whose tag contains one of the prefixes. Kept
    for pilot/diagnostic tables only — a confirmatory table derives its exact
    file set from the schedule instead (`load_scheduled_rows`), because a
    substring match can silently add a row nobody registered."""
    rows: list[dict] = []
    files = matching_files(reviews_dir, tag_prefixes)
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:                      # noqa: BLE001
            print(f"WARNING: could not read {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        if isinstance(data, list):
            rows.extend(data)
        else:
            print(f"WARNING: {path.name} is not a list of rows; skipped", file=sys.stderr)
    return rows, files


# ---------------------------------------------------------------------------
# CONFIRMATORY loading: the exact schedule-derived file set
# ---------------------------------------------------------------------------

def expected_cell_paths(reviews_dir: Path, schedule: dict) -> dict:
    """`{cell_key: (cell, path)}` — the exact file every scheduled cell must
    have written, derived from the schedule, never discovered by globbing."""
    out = {}
    for cell in schedule["cells"]:
        path = SA.output_path_for(reviews_dir, cell["model"], schedule["date_stamp"], cell["tag"])
        out[SA.cell_key(cell)] = (cell, path)
    return out


def load_scheduled_rows(reviews_dir: Path, schedule: dict) -> dict:
    """The confirmatory dataset: one row per scheduled cell, or none.

    Returns `{"rows", "files", "cell_rows", "unrun", "integrity", "unexpected"}`.

      * `cell_rows` maps every scheduled cell key to its single exact row, or
        to `None` when the cell has not run;
      * `integrity` lists cells whose file exists but does not contain
        EXACTLY ONE exactly-matching row — duplicates, partial identities,
        foreign rows, a missing `schedule_id`. These are hard refusals, not
        warnings: each is an observation the panel cannot interpret;
      * `unexpected` lists files that carry this schedule's label but are not
        one of the expected paths. Substring-glob discovery is how an
        unregistered row joins a registered experiment.

    Every denominator downstream is computed from this map, never from the
    raw row count.
    """
    expected = expected_cell_paths(reviews_dir, schedule)
    by_path: dict = {}
    for key, (cell, path) in expected.items():
        by_path.setdefault(path, []).append((key, cell))

    cell_rows: dict = {}
    integrity: list[str] = []
    files: list[Path] = []
    # Every dict row found in an expected cell file, exact or not. The
    # instrument refusal reads THIS: a panel whose rows are
    # ALL drifted admits none of them, and "no rows to read" is not the reason
    # a caller gating on the exit code needs to be told.
    file_rows: list[dict] = []
    for path, entries in sorted(by_path.items(), key=lambda kv: str(kv[0])):
        data = None
        if path.exists():
            files.append(path)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:                  # noqa: BLE001
                for key, cell in entries:
                    cell_rows[key] = None
                    integrity.append(f"{cell['tag']}: the file exists but does not parse "
                                     f"({type(exc).__name__})")
                continue
            if not isinstance(data, list):
                for key, cell in entries:
                    cell_rows[key] = None
                    integrity.append(f"{cell['tag']}: the file is not a list of rows")
                continue
            file_rows += [r for r in data if isinstance(r, dict)]
        for key, cell in entries:
            if data is None:
                cell_rows[key] = None
                continue
            exact = [r for r in data if isinstance(r, dict) and not SA.row_mismatches(r, schedule, cell)]
            near = [r for r in data if isinstance(r, dict) and SA.row_mismatches(r, schedule, cell)]
            if len(exact) == 1 and not near:
                cell_rows[key] = exact[0]
                continue
            cell_rows[key] = None
            if not exact and not near:
                integrity.append(f"{cell['tag']}: the file exists but is empty")
            elif len(exact) > 1:
                integrity.append(f"{cell['tag']}: {len(exact)} rows claim to be this cell")
            else:
                why = SA.row_mismatches(near[0], schedule, cell) if near else ["no row matches"]
                integrity.append(f"{cell['tag']}: {len(exact)} exact and {len(near)} non-matching row(s) "
                                 f"in one cell file — first mismatch: {'; '.join(why[:4])}")

    expected_paths = set(by_path)
    unexpected = []
    label = schedule["label"]
    for path in sorted(reviews_dir.glob("budget_*.json")):
        match = FILENAME_RE.match(path.name)
        if not match or not match.group("tag"):
            continue
        if label in match.group("tag") and path not in expected_paths:
            unexpected.append(path.name)

    rows = [r for r in cell_rows.values() if r is not None]
    unrun = [key for key, row in cell_rows.items() if row is None]
    return {"rows": rows, "files": files, "cell_rows": cell_rows, "unrun": unrun,
            "integrity": integrity, "unexpected": unexpected, "file_rows": file_rows}


def derive_run_closure(loaded: dict) -> dict:
    """Whether the panel is COMPLETE, derived from the exact cell map.
    There is no operator toggle: `--schedule-complete` let a run be
    declared finished after its results were visible, which is precisely the
    decision a pre-registration exists to remove."""
    total = len(loaded["cell_rows"])
    ran = sum(1 for row in loaded["cell_rows"].values() if row is not None)
    integrity = len(loaded["integrity"])
    # An execution-integrity cell is NEITHER run NOR unrun (the docstring
    # said so; the arithmetic used to count it in both places, so the three
    # numbers did not add up to the panel). It is its own third state.
    unrun = max(0, total - ran - integrity)
    return {"n_cells": total, "n_ran": ran, "n_unrun": unrun, "n_integrity": integrity,
            "accounted": ran + unrun + integrity,
            "complete": total > 0 and ran == total and not integrity}


# ---------------------------------------------------------------------------
# THE CENSUS INVARIANTS. The renderer used to print two
# numbers for "how many scheduled cells have no row" that were computed two
# different ways and were allowed to disagree — the header's `Run closure`
# line (derived from the exact per-file cell map) said "1 unrun", and the
# later `### Scheduled but not run` section (which recomputed its OWN
# membership test from a `tag` string) said "0 unrun", because confirm1v4's
# tags are NOT unique across models: `confirm1v4_Ap_eval5_r2` names one cell
# for EVERY one of the four models at that (arm, selector, replicate), so a
# different model's row satisfied the tag half of the old section's AND
# check and hid the truly unrun cell.
#
# `census_breakdown` computes BOTH identities — twice each,
# from independent code paths — and returns the agreed numbers only when
# every path agrees. Any disagreement is a `CensusInvariantViolation`,
# raised before a single line of the report is written: a renderer that CAN
# print a self-contradictory census is not one to trust at all.
# ---------------------------------------------------------------------------

def census_breakdown(scheduled: list[dict], loaded: dict, rows: list[dict]) -> dict:
    """The two census invariants, asserted:

        scheduled == exactly_matched_rows + unrun + execution_integrity
        exactly_matched_rows == valid + provider_failed + instrument_invalid + other_classified

    For confirm1v4: `144 == 143 + 1 + 0` and `143 == 138 + 5 + 0 + 0`.

    The FIRST identity is cross-checked against `derive_run_closure(loaded)`
    — the same closure the header's own "Run closure, DERIVED" line prints —
    rather than trusting `loaded` alone, so a caller that hands `render_table`
    a `loaded` map computed against a DIFFERENT `scheduled`/`rows` pair (a
    programming error, not a data one) is caught here too.

    The SECOND identity is computed twice: once the way the header's own
    "Rows loaded / Re-derived validity" line does (`is_quarantined` +
    `row_status`), and once by running every row (quarantined or not)
    through `classify_row` and bucketing `exogenous -> provider_failed`,
    `instrument_invalid -> instrument_invalid`, everything else non-`None`
    -> `other_classified`, `None` -> `valid`. Returns the agreed numbers;
    raises `CensusInvariantViolation` the instant the two derivations
    disagree.
    """
    closure = derive_run_closure(loaded)
    n_scheduled, exactly_matched = len(scheduled), len(rows)
    if closure["n_cells"] != n_scheduled or closure["n_ran"] != exactly_matched:
        raise CensusInvariantViolation(
            f"derive_run_closure's own n_cells/n_ran ({closure['n_cells']}/{closure['n_ran']}) does "
            f"not match the schedule/rows this render was handed ({n_scheduled}/{exactly_matched})")
    if n_scheduled != exactly_matched + closure["n_unrun"] + closure["n_integrity"]:
        raise CensusInvariantViolation(
            f"scheduled ({n_scheduled}) != exactly_matched_rows ({exactly_matched}) + unrun "
            f"({closure['n_unrun']}) + execution-integrity ({closure['n_integrity']})")

    counted = [r for r in rows if not is_quarantined(r)]
    statuses = Counter(row_status(r)[0] for r in counted)
    header_valid = statuses.get("VALID", 0) + statuses.get("VALID/derived", 0)
    header_instrument_invalid = statuses.get("INVALID", 0)
    header_quarantined = len(rows) - len(counted)

    valid = provider_failed = instrument_invalid = other_classified = 0
    for row in rows:
        bucket, _ = classify_row(row)
        if bucket is None:
            valid += 1
        elif bucket == "exogenous":
            provider_failed += 1
        elif bucket == "instrument_invalid":
            instrument_invalid += 1
        else:
            other_classified += 1

    if (valid, instrument_invalid, provider_failed + other_classified) != \
            (header_valid, header_instrument_invalid, header_quarantined):
        raise CensusInvariantViolation(
            f"row classification disagrees between the two independent derivations: valid={valid} "
            f"(header {header_valid}), instrument_invalid={instrument_invalid} (header "
            f"{header_instrument_invalid}), quarantined-bucketed={provider_failed + other_classified} "
            f"(header {header_quarantined})")
    if valid + provider_failed + instrument_invalid + other_classified != exactly_matched:
        raise CensusInvariantViolation(
            f"exactly_matched_rows ({exactly_matched}) != valid ({valid}) + provider_failed "
            f"({provider_failed}) + instrument_invalid ({instrument_invalid}) + other_classified "
            f"({other_classified})")
    return {"scheduled": n_scheduled, "exactly_matched": exactly_matched,
            "unrun": closure["n_unrun"], "integrity": closure["n_integrity"],
            "valid": valid, "provider_failed": provider_failed,
            "instrument_invalid": instrument_invalid, "other_classified": other_classified}


def render_unrun_section(scheduled: list[dict], loaded: dict | None, rows: list[dict]) -> list[str]:
    """The exact tuple of every scheduled cell with no exactly-matched row:
    provider, model, selector, arm, replicate, planned
    ordinal and block id.

    When `loaded` is available (the confirmatory path) the ONLY authority
    for "unrun" is `loaded["cell_rows"]` — the exact per-file, per-identity
    map `derive_run_closure` itself reads for the header's "Run closure"
    line. The retired version of this section recomputed its own membership
    test from `(key not in ran_keys) AND (tag not in ran_tags)`; `tag` is
    not unique across models sharing one (arm, selector, replicate) triple
    (confirm1v4's own `Ap_eval5_r2` names a cell for FOUR different models),
    so a different model's row satisfied the tag half of that AND and made
    a genuinely unrun cell disappear from this section while the header
    still (correctly) counted it. One map now, not two.

    Without `loaded` (pilot / non-schedule-tracked rendering, where no exact
    per-file map was ever built) the best available evidence is the
    scheduled key absent from the loaded rows — never mixed with the
    confirmatory map above."""
    if loaded is not None:
        cells_by_key = {SA.cell_key(c): c for c in scheduled}
        unrun_cells = [cells_by_key[key] for key in loaded["unrun"] if key in cells_by_key]
    else:
        ran_keys = {(r.get("provider"), r.get("model"), r.get("selector"), r.get("replicate"), r.get("arm"))
                    for r in rows}
        unrun_cells = [c for c in scheduled
                       if (c["provider"], c["model"], c["selector"], c["replicate"], c["arm"])
                       not in ran_keys]
    lines = ["### Scheduled but not run", "",
             f"{len(unrun_cells)} of {len(scheduled)} scheduled cells have no row.", ""]
    if unrun_cells:
        lines += ["| planned ordinal | provider | model | selector | replicate | arm | block id |",
                  "|---|---|---|---|---|---|---|"]
        for c in sorted(unrun_cells, key=lambda c: c["planned_ordinal"]):
            lines.append(f"| {c['planned_ordinal']} | {c['provider']} | {c['model']} | {c['selector']} | "
                         f"{c['replicate']} | {c['arm']} | {c.get('block_id')} |")
        lines.append("")
    return lines


def render_correction_audit(schedule: dict | None, rows: list[dict], census: dict) -> list[str]:
    """The post-run-correction audit block: strict
    pre-correction vs corrected classification, the code/test commit, the
    analysis-plan sha256, and the suspicion statement — naming the
    REDUNDANT environment-side witness explicitly rather than leaving "0
    suspicious" resting on the measurement-side field alone.

    `strict pre-correction`: before the writer fix, every
    live confirm1v4 row was missing per-turn `tool_call_chars`, and the
    pre-correction validator treated ANY missing validity-bearing field —
    including that one — as a demotion to `VALID/derived`; a row admitted to
    a `--pilot` table and refused from every confirmatory estimand, so the
    confirmatory tables above would have rendered with every estimand empty.
    `corrected`: the missing field alone, on a row that carries every OTHER
    validity-bearing field, no longer demotes — it feeds
    `compute_budget_suspicion` (a diagnostic), never
    `compute_budget_accounting` (validity) — so `census['valid']` rows are
    `VALID` outright.
    """
    valid_rows = [r for r in rows if not is_quarantined(r) and classify_row(r) == (None, None)]
    env_present = sum(1 for r in valid_rows if "budget_accounting_suspicious_env_code" in r)
    env_flagged = sum(1 for r in valid_rows if r.get("budget_accounting_suspicious_env_code"))
    re_derived_suspicious = sum(1 for r in valid_rows if is_suspicious(r))
    contract = (schedule or {}).get("experiment_contract") or {}
    analysis_plan_sha256 = contract.get("analysis_plan_sha256")
    return ["**Post-run correction audit** (dated 2026-09-01):", "",
            f"- strict pre-correction classification: all {census['valid']} live rows -> `VALID/derived` "
            f"(the writer omitted per-turn `tool_call_chars`; the pre-correction validator demotes a row "
            f"on ANY missing validity-bearing field, including that one); confirmatory estimands empty.",
            f"- corrected classification: {census['valid']} `VALID` — the sole absent field "
            f"(`tool_call_chars`) is diagnostic-only, so its absence alone no longer demotes a row that "
            f"carries every other validity-bearing field.",
            "- raw row files: UNCHANGED. Only the validator (`measure_budget.validate_row`) and this "
            "renderer moved.",
            f"- correction date 2026-09-01; code/test commit `d4ba5f1`; analysis-plan sha256 "
            f"`{analysis_plan_sha256}`.",
            "",
            f"{re_derived_suspicious} of {len(valid_rows)} rows were flagged suspicious by the archived "
            f"evidence. The environment's OWN suspicion check (`state['piv_budget_accounting_suspicious']`, "
            f"computed LIVE inside `beancount_ledger.py` from `_response_chars` = content + reasoning + "
            f"serialized tool-call characters — it never depended on the writer's field) is archived on "
            f"every row as `budget_accounting_suspicious_env_code`: present {env_present}/{len(valid_rows)}, "
            f"flagged {env_flagged}/{len(valid_rows)}. So the reported zero carries a REDUNDANT witness "
            f"independent of the measurement-side omission, not merely the absence of a signal that could "
            f"not fire.", ""]


# ---------------------------------------------------------------------------
# Configuration-wide capability exclusion
# ---------------------------------------------------------------------------

def load_execution_journal(path) -> dict:
    """The execution journal, read for the evidence table and
    for the confirmatory REFUSAL.

    `{"events", "malformed", "outstanding", "recoveries",
    "acknowledged_through_line", "unterminated_final_line", "line_count",
    "healthy", "exists", "detail", "path"}`, straight from
    `schedule_arms.journal_scan` — the SAME scan the executor fails closed on,
    so "healthy" cannot mean one thing to the writer and another to the reader.

    A malformed line an explicit recovery record ACKNOWLEDGES is
    clean-with-note: the segment boundary carries its own provenance and the
    audit trail is readable across it. A malformed line nothing acknowledges is
    not healthy, and `main()` refuses the confirmatory estimands over it."""
    scan = SA.journal_scan(path)
    outstanding = [m for m in scan["malformed"] if m["line"] > scan["acknowledged_through_line"]]
    return {"events": scan["events"],
            "malformed": [f"line {m['line']}: {m['preview'][:60]}" for m in scan["malformed"]],
            "outstanding": [f"line {m['line']}: {m['preview'][:60]}" for m in outstanding],
            "recoveries": scan["recoveries"],
            "acknowledged_through_line": scan["acknowledged_through_line"],
            "unterminated_final_line": scan["unterminated_final_line"],
            "line_count": scan["line_count"], "healthy": scan["healthy"],
            "exists": scan["exists"], "detail": scan["detail"], "path": path}


# ---------------------------------------------------------------------------
# INSTRUMENT ADMISSION. `arm_table` hard-refuses confirmatory estimands if
# any decision-bearing row has a different or missing instrument/environment
# digest; a warning paragraph is not sufficient.
#
# The digests are already part of exact row admission
# (`schedule_arms.contract_expectations`), so a drifted row never reaches
# `loaded["rows"]` in the first place. This is the SECOND belt and the one that
# produces the refusal by name: it also covers the non-schedule loading paths,
# and it is what makes the exit code say so.
# ---------------------------------------------------------------------------

INSTRUMENT_DIGEST_FIELDS = ("execution_tree_digest", "runtime_environment_digest",
                            "instrument_identity_version")


def instrument_drift_rows(rows: list[dict], schedule: dict | None) -> list[str]:
    """Every decision-bearing row whose instrument is not the sealed one, or
    that carries no instrument identity at all, named."""
    contract = (schedule or {}).get("experiment_contract") or {}
    if not contract:
        return []
    problems: list[str] = []
    for row in rows:
        differences = []
        for field in INSTRUMENT_DIGEST_FIELDS:
            want = contract.get(field)
            if want is None:
                continue
            got = row.get(field)
            if got is None:
                differences.append(f"{field} MISSING (sealed {want!r})")
            elif got != want:
                differences.append(f"{field}={got!r} (sealed {want!r})")
        if differences:
            problems.append(f"{row.get('tag') or row.get('selector')} "
                            f"[{row.get('provider')}/{row.get('model')} {row.get('arm')}]: "
                            + "; ".join(differences))
    return problems


def configuration_exclusions(schedule_path, schedule: dict | None = None) -> dict:
    """The immutable, content-bound configuration exclusions written beside
    the schedule. `arm_table` cannot infer a
    configuration-level exclusion from row-level failures alone, because the
    cells a mid-run exclusion blocks HAVE NO ROWS."""
    if not schedule_path:
        return {"records": [], "problems": [], "path": None}
    return SA.read_configuration_exclusions(Path(schedule_path), schedule)


def capability_incompatible_configurations(rows: list[dict], exclusion_records=()) -> dict:
    """`{(provider, model): [reasons]}` — every configuration in which ANY row
    was classified `capability_incompatible`.

    The design says such a configuration is excluded WHOLE, before
    comparison; the previous table classified individual rows and dropped
    only their triplets, which quietly turned a client/provider
    incompatibility into an arm-shaped hole in the panel. A configuration
    that cannot carry one arm's replayed payload cannot support ANY contrast
    among the three arms, so it leaves the comparison entirely and is
    reported by name.
    """
    offending: dict = {}
    for row in rows:
        bucket, rule = classify_row(row)
        if bucket == "capability_incompatible":
            offending.setdefault((row.get("provider"), row.get("model")), []).append(
                f"{row.get('arm')}/{row.get('selector')}: {rule}")
    # ... and the exclusions that NO row can express: a configuration whose
    # pre-run probe conclusively failed, or one stopped mid-run, whose blocked
    # cells were never executed at all.
    for record in exclusion_records or ():
        key = (record.get("provider"), record.get("model"))
        offending.setdefault(key, []).append(
            f"configuration_exclusion record {str(record.get('record_digest'))[:12]}...: "
            f"{record.get('reason')}")
    return offending


# ---------------------------------------------------------------------------
# Strata
# ---------------------------------------------------------------------------

def build_stratum(rows_for_stratum: list[dict], scheduled_cells: list[dict], pilot: bool,
                  schedule_complete: bool) -> dict:
    """Everything one stratum needs, under BOTH estimands.

    `scheduled_cells` are the schedule rows belonging to this stratum (empty
    when no schedule was given — the operational estimand is then reported as
    unavailable rather than silently computed over the rows that happen to
    exist, which would be the conditional estimand wearing another name).
    """
    accepted_statuses = ("VALID", "VALID/derived") if pilot else ("VALID",)
    validated = [(r, *row_status(r)) for r in rows_for_stratum]
    quarantined = [r for r in rows_for_stratum if is_quarantined(r)]
    valid = [r for r, status, _ in validated if status in accepted_statuses and provider_completed(r)]
    derived = [r for r, status, _ in validated if status == "VALID/derived"]
    invalid = [(r, reasons) for r, status, reasons in validated
               if status == "INVALID" and not is_quarantined(r)]

    buckets: Counter = Counter()
    rules: Counter = Counter()
    bucket_of: dict = {}
    for r in rows_for_stratum:
        bucket, rule = classify_row(r)
        if bucket:
            buckets[bucket] += 1
            rules[f"{bucket}/{rule}"] += 1
            bucket_of[id(r)] = bucket

    n = len(valid)
    n_correct = sum(1 for r in valid if correct_delivery(r))
    n_submitted = sum(1 for r in valid if r.get("submitted") is True)

    # OPERATIONAL denominator: every scheduled cell, minus the ones excluded
    # for reasons that are not about the arm (capability incompatibility and
    # exogenous censoring), minus unrun cells unless the schedule was
    # declared complete. `arm_induced` and `instrument_invalid` cells STAY in
    # the denominator: that is the whole point of the second estimand.
    # A `VALID/derived` row lacks the corrected capture (no wire caps, no
    # attempt identity, no per-turn tool-call characters). In a CONFIRMATORY
    # table it contributes NOTHING — not a delivery, not a denominator, not a
    # token of cost. It used to be excluded from `n` and from the conditional
    # cost while its billed tokens still entered the OPERATIONAL cost, so a
    # pilot-era row could move a confirmatory cost number. In `--pilot` mode
    # it contributes, labelled by `n_derived`.
    derived_ids = {id(r) for r, status, _ in validated if status == "VALID/derived"}
    admitted = [r for r in rows_for_stratum if pilot or id(r) not in derived_ids]

    n_scheduled = len(scheduled_cells)
    ran = len(rows_for_stratum)
    n_unrun = max(0, n_scheduled - ran)
    # Counted over the ADMITTED rows only: a derived row that also failed
    # exogenously has already left the denominator and must not be
    # subtracted from it a second time. `buckets` (every row) is what the
    # failure table reports.
    admitted_buckets: Counter = Counter(bucket_of[id(r)] for r in admitted if id(r) in bucket_of)
    n_excluded_exogenous = admitted_buckets["exogenous"] + admitted_buckets["capability_incompatible"]
    n_ambiguous = admitted_buckets["ambiguous"]
    operational_denominator = None
    operational_denominator_sensitivity = None
    if scheduled_cells:
        # A cell whose only row is `VALID/derived` DID run, so it is not
        # "unrun" — but a confirmatory table has no trustworthy observation
        # of it, so it leaves the denominator like any other censoring.
        base = len(admitted) - n_excluded_exogenous - n_ambiguous
        if schedule_complete:
            base += n_unrun
        operational_denominator = max(0, base)
        # Sensitivity: the ambiguous failures counted as non-delivery.
        operational_denominator_sensitivity = max(0, operational_denominator + n_ambiguous)

    # Rows in the operational DENOMINATOR: everything admitted except the
    # exclusions that are not about the arm. `instrument_invalid` stays — its
    # delivery outcome is known independently (artifact binding, reward, the
    # scorer's completeness flag) even though its accounting is not trusted.
    operational_rows = [r for r in admitted
                        if bucket_of.get(id(r)) not in ("exogenous", "capability_incompatible", "ambiguous")]
    # Rows in the operational COST: the same set MINUS `instrument_invalid`,
    # whose token accounting cannot be trusted (excluded from cost estimates
    # but still reporting the delivery outcome when it is independently
    # known).
    operational_cost_rows = [r for r in operational_rows
                             if bucket_of.get(id(r)) != "instrument_invalid"]
    n_correct_operational = sum(1 for r in operational_rows if correct_delivery(r))
    return {
        "n": n,
        "n_derived": len(derived),
        "n_correct": n_correct,
        "n_submitted": n_submitted,
        "n_suspicious": sum(1 for r in rows_for_stratum if is_suspicious(r)),
        "conditional_rate": (n_correct / n) if n else None,
        "submit_rate": (n_submitted / n) if n else None,
        "n_scheduled": n_scheduled,
        "n_ran": ran,
        "n_unrun": n_unrun,
        "operational_denominator": operational_denominator,
        "n_correct_operational": n_correct_operational,
        "operational_rate": ((n_correct_operational / operational_denominator)
                             if operational_denominator else (0.0 if operational_denominator == 0 else None)),
        "operational_rate_sensitivity": ((n_correct_operational / operational_denominator_sensitivity)
                                         if operational_denominator_sensitivity else None),
        "cost_stats": conditional_cost_stats(valid),
        "effective_cost_conditional": effective_cost(valid),
        "effective_cost_operational": effective_cost(operational_cost_rows, billed_tokens),
        "operational_seconds": sum(r.get("seconds") or 0 for r in operational_cost_rows),
        "operational_requests": sum(len(r.get("requests") or []) for r in operational_cost_rows),
        "median_output_tokens": statistics.median([r["completion_tokens"] for r in valid
                                                   if r.get("completion_tokens") is not None])
                                if any(r.get("completion_tokens") is not None for r in valid) else None,
        "median_turns": statistics.median([r["turns"] for r in valid if r.get("turns") is not None])
                        if any(r.get("turns") is not None for r in valid) else None,
        "stop_histogram": Counter(r.get("stop") for r in valid),
        "failure_buckets": buckets,
        "failure_rules": rules,
        "n_provider_failed": len(quarantined),
        "provider_failed_reasons": Counter(r.get("status") for r in quarantined),
        "n_invalid": len(invalid),
        "invalid_rows": invalid,
        "quarantined_rows": quarantined,
        "valid_rows": valid,
    }


def group_by(rows: list[dict], key_fields: tuple) -> dict:
    groups: dict = {}
    for r in rows:
        groups.setdefault(tuple(r.get(f) for f in key_fields), []).append(r)
    return groups


def check_pooling(rows: list[dict], key_fields: tuple) -> list[str]:
    """Every condition whose rows do not share one (episode, replay) contract
    pair. A non-empty result is an ERROR, not a warning."""
    offences = []
    for key, group in sorted(group_by(rows, key_fields).items(), key=str):
        identities = {contract_identity(r) for r in group if not is_quarantined(r)}
        if len(identities) > 1:
            offences.append(f"{key_fields} = {key}: {len(identities)} distinct (episode, replay) contract "
                            f"pairs — {sorted(str(i) for i in identities)}")
    return offences


# ---------------------------------------------------------------------------
# The fixed-panel bootstrap
# ---------------------------------------------------------------------------

BOOTSTRAP_SEED = 20260830
BOOTSTRAP_RESAMPLES = 2000


# Buckets whose rows may NOT enter a paired contrast. `arm_induced` is
# deliberately absent: a delivery that failed because of the arm's own
# request size or replay payload IS that arm's outcome and belongs in the
# contrast as a non-delivery. Everything here is a failure the arm did not
# cause, or a row whose numbers cannot be trusted.
BLOCK_EXCLUDED_BUCKETS = ("exogenous", "capability_incompatible", "ambiguous", "instrument_invalid")


def block_row_exclusion(row: dict, pilot: bool) -> str | None:
    """Why this row may not enter a paired contrast, or `None` if it may.

    The primary contrast used to receive the RAW row list: one exogenous
    429 — a provider rate limit that had nothing to do with the arm — sat in
    a B1′ cell as a failed delivery and printed "B1′ −50 pp, 17× cost" off a
    single censored attempt. The two estimand tables filtered such rows and
    the contrast did not, so the headline number was computed on a
    denominator the rest of the table had already rejected.
    """
    bucket, _ = classify_row(row)
    if bucket in BLOCK_EXCLUDED_BUCKETS:
        return bucket
    if bucket == "arm_induced":
        return None                      # the arm's own failed delivery: it belongs in the contrast
    status, _ = row_status(row)
    if status == "INVALID":
        return "instrument_invalid"
    if status == "VALID/derived" and not pilot:
        return "derived"
    return None


def arm_blocks(rows: list[dict], arms: tuple, pilot: bool = False) -> tuple[list[dict], Counter]:
    """`([{arm: row}], dropped)` — one entry per (provider, model, selector,
    replicate) block that has an ELIGIBLE row for EVERY arm.

    Whole triplets, never individual rows: resampling rows independently
    would break the pairing the design exists to create. And a PARTIAL
    triplet is dropped whole — a block missing one arm cannot support a
    paired contrast, and silently contrasting the two arms that survived
    would reintroduce exactly the censoring the filter just removed.
    `dropped` counts the blocks lost, by which arm went missing and why.
    """
    grouped: dict = {}
    for r in rows:
        key = (r.get("provider"), r.get("model"), r.get("selector"), r.get("replicate"))
        grouped.setdefault(key, []).append(r)
    blocks: list[dict] = []
    dropped: Counter = Counter()
    for key in sorted(grouped, key=str):
        by_arm: dict = {}
        excluded: Counter = Counter()
        duplicated: set = set()
        for r in grouped[key]:
            reason = block_row_exclusion(r, pilot)
            if reason:
                excluded[f"{r.get('arm')}:{reason}"] += 1
                continue
            if r.get("arm") in by_arm:
                # `setdefault` used to let the FIRST eligible duplicate win
                # silently. Two eligible rows for one arm of
                # one block are two observations of a cell that has exactly
                # one; which of them enters the contrast is not a choice this
                # code may make, so the block is dropped and said so.
                duplicated.add(r.get("arm"))
                continue
            by_arm[r.get("arm")] = r
        if duplicated:
            dropped[f"duplicate rows for {'/'.join(sorted(str(a) for a in duplicated))}"] += 1
            continue
        missing = [a for a in arms if a not in by_arm]
        if not missing:
            blocks.append(by_arm)
            continue
        why = ", ".join(f"{k}" for k in sorted(excluded)) or "no row at all"
        dropped[f"missing {'/'.join(str(m) for m in missing)} ({why})"] += 1
    return blocks, dropped


def _rate_delta(blocks: list[dict], arm: str, base: str) -> float:
    if not blocks:
        return float("nan")
    return statistics.mean(float(correct_delivery(b[arm])) - float(correct_delivery(b[base])) for b in blocks)


def _cost_ratio(blocks: list[dict], arm: str, base: str) -> float:
    numerator = effective_cost([b[arm] for b in blocks], billed_tokens)
    denominator = effective_cost([b[base] for b in blocks], billed_tokens)
    if denominator == float("inf"):
        return float("nan") if numerator == float("inf") else 0.0
    if denominator == 0:
        return float("nan")
    return numerator / denominator


def arm_totals(blocks: list[dict], arm: str) -> dict:
    """The raw material behind a cost ratio: how many correct deliveries this
    arm produced over these blocks and how many tokens the provider billed
    for them. Printed beside every ratio so the nonlinear statistic is
    auditable."""
    rows = [b[arm] for b in blocks if arm in b]
    correct = sum(1 for r in rows if correct_delivery(r))
    billed = sum(billed_tokens(r) for r in rows)
    return {"n_blocks": len(rows), "n_correct": correct, "billed_tokens": billed,
            "effective_cost": (billed / correct) if correct else float("inf")}


def cost_ratio_uncertainty(blocks: list[dict], arm: str, base: str,
                           resamples: int = None) -> dict:
    """Uncertainty for an EFFECTIVE-COST RATIO, bootstrapped over whole
    triplets exactly as the delivery contrast is.

    A cost ratio is `(billed_arm / correct_arm) / (billed_base / correct_base)`
    and is UNDEFINED whenever either arm produced no correct delivery in a
    resample — which, at twelve blocks per model, is not a rare event. Silently
    dropping those resamples and presenting the remainder as an ordinary 95%
    interval would report a conditional quantity as an unconditional one, and
    would hide the very outcome (an arm delivering nothing) that dominates the
    comparison. So four things are reported instead, and never one without the
    others:

      * `p_zero_correct[arm]`  — how often each arm delivered NOTHING in a
        resample. An arm with a high value has no meaningful cost per
        delivery, and its ratio interval means little whatever it says;
      * `p_dominates` — how often the arm's cost per correct delivery was
        strictly LOWER than the base's, counting a zero-correct base as
        infinitely expensive (the arm dominates it) and a zero-correct arm as
        losing. This is defined on EVERY resample and is the honest summary;
      * `interval_conditional` — the percentile interval over the resamples
        in which BOTH arms delivered at least once, labelled conditional and
        reported with the share of resamples it covers;
      * `totals` — raw successes and billed tokens per arm, so a reader can
        recompute the point estimate by hand.
    """
    resamples = BOOTSTRAP_RESAMPLES if resamples is None else resamples
    out = {"n_blocks": len(blocks), "resamples": resamples,
           "point_ratio": _cost_ratio(blocks, arm, base) if blocks else float("nan"),
           "totals": {arm: arm_totals(blocks, arm), base: arm_totals(blocks, base)},
           "p_zero_correct": {arm: None, base: None}, "p_dominates": None,
           "p_both_undefined": None, "interval_conditional": (None, None),
           "conditional_share": None}
    if not blocks:
        return out
    rng = random.Random(BOOTSTRAP_SEED)
    zero_arm = zero_base = dominates = both_zero = 0
    finite: list[float] = []
    for _ in range(resamples):
        sample = [blocks[rng.randrange(len(blocks))] for _ in blocks]
        ta, tb = arm_totals(sample, arm), arm_totals(sample, base)
        if not ta["n_correct"]:
            zero_arm += 1
        if not tb["n_correct"]:
            zero_base += 1
        if not ta["n_correct"] and not tb["n_correct"]:
            both_zero += 1
            continue                      # neither arm has a cost per delivery: no comparison exists
        if ta["effective_cost"] < tb["effective_cost"]:
            dominates += 1
        if ta["n_correct"] and tb["n_correct"]:
            finite.append(ta["effective_cost"] / tb["effective_cost"])
    out["p_zero_correct"] = {arm: zero_arm / resamples, base: zero_base / resamples}
    out["p_dominates"] = dominates / resamples
    out["p_both_undefined"] = both_zero / resamples
    out["conditional_share"] = len(finite) / resamples
    if len(finite) >= 20:
        finite.sort()
        out["interval_conditional"] = (finite[int(0.025 * (len(finite) - 1))],
                                       finite[int(0.975 * (len(finite) - 1))])
    return out


def bootstrap_interval(blocks: list[dict], statistic, cluster_fn=None) -> tuple:
    """A percentile interval over whole arm triplets, with a fixed seed so
    the same archive always yields the same interval. `cluster_fn`, when
    given, resamples CLUSTERS (selectors) instead of blocks — a sensitivity
    analysis whose few clusters make the interval
    very wide and purely descriptive."""
    if not blocks:
        return (None, None)
    rng = random.Random(BOOTSTRAP_SEED)
    draws = []
    if cluster_fn is None:
        for _ in range(BOOTSTRAP_RESAMPLES):
            sample = [blocks[rng.randrange(len(blocks))] for _ in blocks]
            value = statistic(sample)
            if value == value:                                    # skip NaN (undefined on this resample)
                draws.append(value)
    else:
        clusters: dict = {}
        for block in blocks:
            clusters.setdefault(cluster_fn(block), []).append(block)
        keys = list(clusters)
        for _ in range(BOOTSTRAP_RESAMPLES):
            sample = []
            for _ in keys:
                sample.extend(clusters[keys[rng.randrange(len(keys))]])
            value = statistic(sample)
            if value == value:
                draws.append(value)
    if len(draws) < 20:
        return (None, None)
    draws.sort()
    lo = draws[int(0.025 * (len(draws) - 1))]
    hi = draws[int(0.975 * (len(draws) - 1))]
    return (lo, hi)


def discordant_counts(blocks: list[dict], arm: str, base: str) -> tuple[int, int]:
    """`(b, c)` — the discordant pairs an exact paired sign/McNemar test
    reads: `b` = base failed and arm delivered, `c` = base
    delivered and arm failed. Reported BESIDE the preregistered bootstrap,
    never in place of it — at panel sizes this small an exact test can be
    far less decisive than a bootstrap interval that already excludes zero,
    and the reader needs both numbers, not one translated into the other."""
    b = c = 0
    for block in blocks:
        base_ok = correct_delivery(block[base])
        arm_ok = correct_delivery(block[arm])
        if arm_ok and not base_ok:
            b += 1
        elif base_ok and not arm_ok:
            c += 1
    return b, c


def sign_test_p(b: int, c: int) -> float | None:
    """The exact two-sided sign/McNemar test p-value for `b` vs `c`
    discordant pairs — `b + c` Bernoulli(0.5) trials under the null of no
    directional effect, doubling the smaller tail and capping at 1.0.
    `None` when there are no discordant pairs at all (nothing to test)."""
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def format_rate(numer, denom) -> str:
    if denom is None:
        return "n/a"
    if not denom:
        return "— (0)"
    return f"{100.0 * numer / denom:.0f}% ({numer}/{denom})"


def format_cost_cell(stats: dict) -> str:
    if stats["n"] < 3:
        return f"— (n={stats['n']}, diagnostic witness)"
    return f"median {stats['median']:,.0f} / p75 {stats['p75']:,.0f} (n={stats['n']})"


def format_cost(value: float) -> str:
    if value == float("inf"):
        return "inf (dominated)"
    return f"{value:,.0f}"


def format_num(value, nd=0) -> str:
    return "—" if value is None else f"{value:,.{nd}f}"


def format_hist(counter: Counter) -> str:
    if not counter:
        return "—"
    return ", ".join(f"{k}×{v}" for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0]))))


DATA_COLUMNS = ("n valid", "n derived", "n suspicious",
                "CONDITIONAL delivery (correct / valid completed)",
                "SCHEDULED operational delivery (correct / scheduled eligible)",
                "accepted-submit rate",
                "conditional cost (median/p75 total tokens, correct deliveries)",
                "effective cost / correct delivery (conditional)",
                "effective cost / correct delivery (operational, billed)",
                "median output tokens", "median turns", "terminal-status histogram",
                "failure buckets", "n_provider_failed")


def stratum_row(label_cells: list[str], stats: dict) -> str:
    cells = [
        str(stats["n"]), str(stats["n_derived"]), str(stats["n_suspicious"]),
        format_rate(stats["n_correct"], stats["n"]),
        format_rate(stats["n_correct_operational"], stats["operational_denominator"]),
        format_rate(stats["n_submitted"], stats["n"]),
        format_cost_cell(stats["cost_stats"]),
        format_cost(stats["effective_cost_conditional"]),
        format_cost(stats["effective_cost_operational"]),
        format_num(stats["median_output_tokens"]), format_num(stats["median_turns"], 1),
        format_hist(stats["stop_histogram"]), format_hist(stats["failure_buckets"]),
        str(stats["n_provider_failed"]),
    ]
    return "| " + " | ".join(label_cells + cells) + " |"


def render_strata(rows: list[dict], scheduled: list[dict], pilot: bool, schedule_complete: bool,
                  title: str) -> list[str]:
    lines = [f"## {title}", "",
             "The delivery rates below are a **capability-sensitive, non-degenerate reward signal on the "
             "fixed panel**: stronger models deliver substantially more, smaller models "
             "mostly do not, and partial reward occupies the middle. That is evidence the panel's reward "
             "is neither trivially always-1 nor always-0 for this roster — it is NOT evidence that "
             "reinforcement learning can learn the gradient (no policy was trained against this reward "
             "and no learning curve was measured), so \"learnable gradient\" is reserved for an actual "
             "training/optimization experiment and is never used here.", ""]
    header = " | ".join(DATA_COLUMNS)
    sep = "|".join(["---"] * len(DATA_COLUMNS))

    for label, key_fields in (("Per (provider, model, selector, arm)", ("provider", "model", "selector", "arm")),
                              ("Per (provider, model, arm), pooled over selector",
                               ("provider", "model", "arm"))):
        lines += [f"### {label}", "",
                  "| " + " | ".join(key_fields) + f" | {header} |",
                  "|" + "---|" * len(key_fields) + sep + "|"]
        grouped = group_by(rows, key_fields)
        scheduled_grouped = group_by(scheduled, key_fields) if scheduled else {}
        for key in sorted(grouped, key=str):
            stats = build_stratum(grouped[key], scheduled_grouped.get(key, []), pilot, schedule_complete)
            lines.append(stratum_row([str(k) for k in key], stats))
        # A scheduled stratum with no rows at all is still a scheduled
        # stratum: it must appear, as unrun, rather than vanish.
        for key in sorted(set(scheduled_grouped) - set(grouped), key=str):
            cells = scheduled_grouped[key]
            lines.append("| " + " | ".join(str(k) for k in key) + " | " +
                         " | ".join(["0"] * 3 + [f"n/a (0 of {len(cells)} scheduled cells run)"] +
                                    ["n/a"] * (len(DATA_COLUMNS) - 4)) + " |")
        lines.append("")
    return lines


def ratio_stats(rows: list[dict], arms: tuple, base_arm: str, pilot: bool = False) -> dict:
    """`{(provider, model, arm): {...}}` plus `{"_blocks": {...}, "_dropped": {...}}`
    — the numbers the primary-contrast table renders, computed once so the
    two sensitivities (all rows / excluding suspicious rows) can be COMPARED
    rather than merely printed twice."""
    stats: dict = {"_blocks": {}, "_dropped": {}}
    for (provider, model), group in sorted(group_by(rows, ("provider", "model")).items(), key=str):
        blocks, dropped = arm_blocks(group, arms, pilot)
        stats["_blocks"][(provider, model)] = blocks
        stats["_dropped"][(provider, model)] = dropped
        for arm in arms:
            if arm == base_arm:
                continue
            delta = _rate_delta(blocks, arm, base_arm) if blocks else float("nan")
            lo, hi = bootstrap_interval(blocks, lambda s, a=arm: _rate_delta(s, a, base_arm))
            clo, chi = bootstrap_interval(blocks, lambda s, a=arm: _rate_delta(s, a, base_arm),
                                          cluster_fn=lambda b, a=arm: b[a].get("selector"))
            stats[(provider, model, arm)] = {
                "n_blocks": len(blocks), "delta": delta, "interval": (lo, hi),
                "cluster_interval": (clo, chi),
                "ratio": _cost_ratio(blocks, arm, base_arm) if blocks else float("nan"),
                "uncertainty": cost_ratio_uncertainty(blocks, arm, base_arm),
            }
    return stats


def _sign(value) -> str:
    if value is None or value != value:                                    # NaN
        return "undefined"
    if value > 0:
        return "+"
    if value < 0:
        return "-"
    return "0"


def compare_ratio_stats(all_stats: dict, clean_stats: dict, arms: tuple, base_arm: str) -> list[str]:
    """What the suspicious-row sensitivity did to the DECISION-BEARING
    numbers: how many blocks each configuration lost, and
    whether any sign or ranking changed. A conclusion that holds in only one
    of the two sensitivities is reported as sensitive to the heuristic —
    which requires actually comparing them, not printing them next to each
    other."""
    lines = ["### Suspicious-row sensitivity: what changed", "",
             "| provider | model | arm | blocks (all) | blocks (excl. suspicious) | Δ sign | ratio ranking |",
             "|---|---|---|---|---|---|---|"]
    changed = []
    for key in sorted([k for k in all_stats if isinstance(k, tuple) and len(k) == 3], key=str):
        provider, model, arm = key
        a = all_stats[key]
        c = clean_stats.get(key)
        if c is None:
            lines.append(f"| {provider} | {model} | {arm}' | {a['n_blocks']} | 0 (no eligible block) | "
                         f"— | — |")
            changed.append(f"{provider}/{model} {arm}': every block was suspicious")
            continue
        sign_a, sign_c = _sign(a["delta"]), _sign(c["delta"])
        rank_a = ("cheaper" if a["ratio"] == a["ratio"] and a["ratio"] < 1 else
                  "costlier" if a["ratio"] == a["ratio"] and a["ratio"] > 1 else "undefined")
        rank_c = ("cheaper" if c["ratio"] == c["ratio"] and c["ratio"] < 1 else
                  "costlier" if c["ratio"] == c["ratio"] and c["ratio"] > 1 else "undefined")
        sign_cell = sign_a if sign_a == sign_c else f"**{sign_a} -> {sign_c}**"
        rank_cell = rank_a if rank_a == rank_c else f"**{rank_a} -> {rank_c}**"
        if sign_a != sign_c:
            changed.append(f"{provider}/{model} {arm}': delivery-delta sign {sign_a} -> {sign_c}")
        if rank_a != rank_c:
            changed.append(f"{provider}/{model} {arm}': cost ranking {rank_a} -> {rank_c}")
        lines.append(f"| {provider} | {model} | {arm}' | {a['n_blocks']} | {c['n_blocks']} | "
                     f"{sign_cell} | {rank_cell} |")
    lines.append("")
    if changed:
        lines += ["**The primary contrast is SENSITIVE to the characters-per-token heuristic**: "
                  + "; ".join(changed) + ". No arm conclusion may be stated without saying which "
                                         "sensitivity it holds in.", ""]
    else:
        lines += ["No sign and no cost ranking changed between the two sensitivities.", ""]
    return lines


def render_ratios(rows: list[dict], arms: tuple, base_arm: str, pilot: bool = False,
                  title: str = "Primary contrasts, within (provider, model)",
                  stats: dict | None = None) -> list[str]:
    """Primary cost/delivery contrasts, WITHIN (provider, model) — never
    across providers, whose tokens are not the same unit."""
    lines = [f"## {title}", "",
             f"Paired within (provider, model, selector, replicate); base arm {base_arm}'. Bootstrap: "
             f"{BOOTSTRAP_RESAMPLES} resamples of WHOLE arm triplets (seed {BOOTSTRAP_SEED}); the cluster "
             f"column resamples SELECTORS instead, which with a handful of clusters is descriptive only.",
             "",
             "Blocks are filtered before they are paired: a row excluded by the failure classification for a "
             "reason the arm did not cause (`exogenous`, `capability_incompatible`, `ambiguous`) or whose "
             "accounting cannot be trusted (`instrument_invalid`"
             + ("" if pilot else ", and `VALID/derived` in a confirmatory table")
             + ") cannot enter a contrast, and a block that loses ANY of its three arm cells is dropped "
               "WHOLE — contrasting the two arms that survived would reintroduce the censoring the filter "
               "just removed. `arm_induced` failures STAY: a delivery that failed because of the arm's own "
               "request size or replay payload is that arm's outcome.", "",
             "**How to read the intervals below**: the correct statement for a 95% block "
             "interval that does not contain zero is \"the preregistered whole-block bootstrap interval "
             "excludes zero on this fixed panel\" — never \"statistically clean\" or \"significant\" "
             "unqualified. The matching statement for the cost-ratio table further down is \"the "
             "conditional bootstrap ratio interval excludes one\". `P(arm dominates)` there is a bootstrap "
             "resample frequency, not a Bayesian posterior probability that the arm is superior.", "",
             "| provider | model | arm | complete blocks | Δ delivery rate vs base | 95% (blocks) | "
             "95% (selector clusters) | effective-cost ratio vs base (billed) |",
             "|---|---|---|---|---|---|---|---|"]
    stats = stats if stats is not None else ratio_stats(rows, arms, base_arm, pilot)
    dropped_report: list[str] = []
    uncertainty_rows: list[str] = []
    sign_test_rows: list[str] = []
    for (provider, model) in sorted(stats["_dropped"], key=str):
        for reason, count in sorted(stats["_dropped"][(provider, model)].items()):
            dropped_report.append(f"| {provider} | {model} | {reason} | {count} |")
    for key in sorted([k for k in stats if isinstance(k, tuple) and len(k) == 3], key=str):
        provider, model, arm = key
        entry = stats[key]
        delta, (lo, hi), (clo, chi) = entry["delta"], entry["interval"], entry["cluster_interval"]
        ratio = entry["ratio"]
        lines.append(
            f"| {provider} | {model} | {arm}' | {entry['n_blocks']} | "
            f"{'—' if delta != delta else f'{delta:+.2f}'} | "
            f"{'—' if lo is None else f'[{lo:+.2f}, {hi:+.2f}]'} | "
            f"{'—' if clo is None else f'[{clo:+.2f}, {chi:+.2f}]'} | "
            f"{'undefined (both arms zero-correct)' if ratio != ratio else f'{ratio:.2f}'} |")
        # THE EXACT PAIRED SIGN TEST, beside the bootstrap —
        # informational only, never a replacement for the preregistered
        # bootstrap analysis above.
        blocks = stats["_blocks"].get((provider, model), [])
        if blocks:
            b, c = discordant_counts(blocks, arm, base_arm)
            p = sign_test_p(b, c)
            p_text = "undefined (no discordant pairs)" if p is None else f"p = {p:.3f}"
            sign_test_rows.append(
                f"- {provider}/{model} {arm}': paired discordants over {len(blocks)} complete blocks: "
                f"{b} vs {c}; an exact two-sided sign test at this size is {p_text} — the bootstrap is "
                f"the preregistered analysis and is reported as such, not translated into a universal "
                f"significance claim.")
        u = entry["uncertainty"]
        base_totals = u["totals"][base_arm]
        arm_totals_ = u["totals"][arm]
        lo_r, hi_r = u["interval_conditional"]
        p_zero_arm = u["p_zero_correct"][arm]
        p_zero_base = u["p_zero_correct"][base_arm]
        p_dom = u["p_dominates"]
        share = u["conditional_share"]
        arm_raw = f"{arm_totals_['n_correct']}/{arm_totals_['n_blocks']} correct, " \
                  f"{arm_totals_['billed_tokens']:,} billed"
        base_raw = f"{base_totals['n_correct']}/{base_totals['n_blocks']} correct, " \
                   f"{base_totals['billed_tokens']:,} billed"
        zero_cell = (f"{p_zero_arm:.2f} / {p_zero_base:.2f}"
                     if p_zero_arm is not None and p_zero_base is not None else "—")
        dom_cell = "—" if p_dom is None else f"{p_dom:.2f}"
        if lo_r is None:
            interval_cell = f"undefined ({'0%' if share is None else format(share, '.0%')} of resamples had both)"
        else:
            interval_cell = f"[{lo_r:.2f}, {hi_r:.2f}] conditional (on {share:.0%} of resamples)"
        uncertainty_rows.append(f"| {provider} | {model} | {arm}' | {arm_raw} | {base_raw} | "
                                f"{zero_cell} | {dom_cell} | {interval_cell} |")
    lines += ["", "### Paired sign test (exact, informational — the bootstrap above is the "
                  "preregistered analysis)", "",
              "The whole-block bootstrap above is the preregistered analysis. The exact two-sided "
              "sign/McNemar test below is reported beside it, never in place of it, so a reader can see "
              "how decisive an exact test is at this panel size — a percentile bootstrap can exclude "
              "zero at eleven blocks while the exact paired test cannot reject at 5%.", ""]
    lines += sign_test_rows or ["- no complete block for any contrast."]
    lines.append("")
    lines += ["### Cost-ratio uncertainty (bootstrapped over whole triplets, "
                  f"{BOOTSTRAP_RESAMPLES} resamples, seed {BOOTSTRAP_SEED})", "",
              "A ratio of two effective costs is undefined whenever either arm delivered nothing in a "
              "resample, and at this panel size that is not rare. The undefined resamples are NOT dropped "
              "silently: the probability of each arm delivering nothing, the probability that the arm "
              "dominates the base (a zero-correct base counts as infinitely expensive), and the interval "
              "CONDITIONAL on both arms delivering are all reported, with the raw successes and billed "
              "totals behind them.", "",
              "| provider | model | arm | arm raw | base raw | P(zero-correct) arm / base | "
              "P(arm dominates) [bootstrap resample frequency, NOT a posterior probability] | "
              "conditional 95% ratio interval |",
              "|---|---|---|---|---|---|---|---|"]
    lines += uncertainty_rows or ["| — | | | | | | | no complete blocks |"]
    lines += ["",
              f"Ratio convention: a value above 1 means the arm costs MORE billed tokens per correct delivery "
              f"than {base_arm}'. `0.00` means {base_arm}' delivered nothing at all in these blocks (its own "
              f"effective cost is `inf`), so the arm dominates it rather than beating it by that factor; "
              f"`undefined` means NEITHER arm delivered. The cost here is OPERATIONAL (billed tokens over "
              f"every attempt in the block, failures included), not conditional on delivering.", ""]
    lines += ["### Blocks dropped from the contrast", ""]
    if dropped_report:
        lines += ["| provider | model | why the block was dropped | blocks |", "|---|---|---|---|"]
        lines += dropped_report
        lines += ["", "A dropped block contributes to NEITHER arm. It is a censored observation, not evidence "
                      "for or against the arm whose cell survived.", ""]
    else:
        lines += ["None: every block had an eligible row for all three arms.", ""]
    return lines


def render_cross_model(rows: list[dict],
                       title: str = "Cross-model operational summary (no pooled token statistic)") -> list[str]:
    """Wall time, request counts and PROVIDER-SPECIFIC tokens, side by side.
    No pooled token statistic appears here: one provider's token is not
    another's, and a cross-model mean of them would be a number with no
    unit."""
    lines = [f"## {title}", "",
             "| provider | model | rows | wall-clock minutes | provider requests | billed input tokens | "
             "billed output tokens |", "|---|---|---|---|---|---|---|"]
    for (provider, model), group in sorted(group_by(rows, ("provider", "model")).items(), key=str):
        seconds = sum(r.get("seconds") or 0 for r in group)
        requests = sum(len(r.get("requests") or []) for r in group)
        billed_in = sum(r.get("billed_input_tokens_all_attempts") or r.get("prompt_tokens") or 0 for r in group)
        billed_out = sum(r.get("billed_output_tokens_all_attempts") or r.get("completion_tokens") or 0
                         for r in group)
        lines.append(f"| {provider} | {model} | {len(group)} | {seconds / 60:,.1f} | {requests} | "
                     f"{billed_in:,} | {billed_out:,} |")
    lines.append("")
    return lines


def render_failures(rows: list[dict]) -> list[str]:
    lines = ["## Failure classification (fixed map, applied blind to the arm's outcome)", "",
             "`classify_error` sees the recorded error text and the observed request size only. "
             "`capability_incompatible` excludes the whole configuration before comparison and is never "
             "counted against an arm; `arm_induced` is a failed delivery FOR that arm, its billed tokens "
             "included in operational cost; `instrument_invalid` is excluded from cost but keeps its delivery "
             "outcome; `ambiguous` is reported here and enters the sensitivity denominator, never a silent "
             "exclusion.", "",
             "| provider | model | arm | bucket / rule | rows |", "|---|---|---|---|---|"]
    any_row = False
    counts: dict = {}
    for r in rows:
        bucket, rule = classify_row(r)
        if not bucket:
            continue
        key = (r.get("provider"), r.get("model"), r.get("arm"), f"{bucket}/{rule}")
        counts[key] = counts.get(key, 0) + 1
    for key in sorted(counts, key=str):
        any_row = True
        lines.append("| " + " | ".join(str(k) for k in key) + f" | {counts[key]} |")
    if not any_row:
        lines.append("| — | | | none | 0 |")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# THE EXECUTION-EVIDENCE RENDERINGS. No new outcome metric and
# no new decision threshold — the estimands are final. These are the AUDIT
# EVIDENCE for the estimands already pre-registered, and every one of them
# exists because a review-found defect made the corresponding fact unreadable
# from the archive.
# ---------------------------------------------------------------------------

def render_instrument_identity(rows: list[dict], schedule: dict | None) -> list[str]:
    """The runtime HEAD and the runtime ENVIRONMENT beside the sealed
    instrument identity.

    Under the git-path contract the executing commit may legitimately differ
    from the sealed one, so the report must say BOTH. What it may NOT do any
    more is report a difference and compute the estimands
    anyway: a row whose digests differ from the seal is refused from exact
    admission, and `main()` exits 4 naming it. This section is the evidence for
    that refusal, not a substitute for it."""
    contract = (schedule or {}).get("experiment_contract") or {}
    lines = ["## Instrument identity: what was sealed, and what ran", "",
             f"- sealed instrument commit `{contract.get('instrument_commit')}`",
             f"- sealed execution paths `{contract.get('execution_paths')}`",
             f"- sealed execution-tree digest `{contract.get('execution_tree_digest')}` "
             f"({contract.get('execution_tree_file_count')} files)",
             f"- sealed runtime-environment digest `{contract.get('runtime_environment_digest')}` "
             f"({contract.get('runtime_environment_file_count')} files, "
             f"{contract.get('runtime_environment_bytes')} bytes, "
             f"{contract.get('runtime_environment_distribution_count')} distributions, "
             f"{contract.get('runtime_environment_extra_file_count')} referenced by no RECORD)",
             f"- sealed interpreter `{str(contract.get('python_version') or '').splitlines()[:1]}`",
             "",
             "A row's instrument digests are part of EXACT admission, not of this paragraph: a row whose "
             "execution-tree or runtime-environment digest differs from the seal — or that carries none — "
             "is not this cell's row, enters no estimand, and makes this table exit 4.", ""]
    heads = Counter((r.get("runtime_head"), r.get("execution_tree_digest"),
                     r.get("runtime_environment_digest"))
                    for r in rows if r.get("runtime_head") or r.get("execution_tree_digest")
                    or r.get("runtime_environment_digest"))
    if not heads:
        lines += ["No row carries a runtime identity: these rows predate the instrument contract, so "
                  "neither the checkout nor the interpreter that produced them can be verified from the "
                  "archive. Such a row is REFUSED from a confirmatory estimand.", ""]
        return lines
    lines += ["| runtime HEAD | execution-tree digest | runtime-environment digest | rows | verdict |",
              "|---|---|---|---|---|"]
    sealed_tree = contract.get("execution_tree_digest")
    sealed_env = contract.get("runtime_environment_digest")
    for (head, tree, environment), count in sorted(heads.items(), key=str):
        if sealed_tree is None and sealed_env is None:
            verdict = "no sealed digest to compare"
        elif tree == sealed_tree and environment == sealed_env:
            verdict = "VERIFIED — identical instrument content"
        else:
            differing = [name for name, got, want in
                         (("tree", tree, sealed_tree), ("environment", environment, sealed_env))
                         if want is not None and got != want]
            verdict = f"**REFUSED — {', '.join(differing)} DIFFERENT from the sealed instrument**"
        lines.append(f"| `{head}` | `{tree}` | `{environment}` | {count} | {verdict} |")
    if len(heads) > 1:
        lines += ["", "**More than one runtime identity produced these rows.** That is permitted only "
                      "while every execution-tree AND runtime-environment digest equals the sealed one; "
                      "any row above whose digest differs was produced by a different instrument and is "
                      "refused."]
    lines.append("")
    return lines


def render_probe_outcomes(journal: dict, exclusions: dict) -> list[str]:
    """The capability-probe outcome per configuration, with
    INCONCLUSIVE distinguished from INCOMPATIBLE. Unknown is not incompatible,
    and the table must never present it as though it were."""
    lines = ["## Capability-probe outcome per configuration", "",
             "`probe_passed` established the configuration; `capability_failed` is a CONCLUSIVE "
             "incompatibility and carries an immutable exclusion record; `probe_inconclusive` established "
             "NOTHING (unreachable endpoint, or the model would not call a tool) and leaves the "
             "configuration unrun and UNKNOWN; `inconclusive_accepted` is an explicit, journalled operator "
             "decision to start one anyway.", "",
             "| provider | model | outcome | when | evidence |", "|---|---|---|---|---|"]
    seen = False
    for event in journal.get("events") or []:
        if event.get("event") not in ("probe_passed", "capability_failed", "probe_inconclusive",
                                      "inconclusive_accepted"):
            continue
        seen = True
        policies = ((event.get("result") or {}).get("policies") or {})
        lines.append(f"| {event.get('provider')} | {event.get('model')} | `{event.get('event')}` | "
                     f"{event.get('at')} | {sorted(policies)} |")
    if not seen:
        lines.append("| — | | no probe events in the execution journal | | |")
    lines.append("")
    records = exclusions.get("records") or []
    lines += ["### Configuration-level exclusion records (immutable, content-bound)", ""]
    if records:
        lines += ["| provider | model | reason | recorded | record digest |", "|---|---|---|---|---|"]
        for record in records:
            lines.append(f"| {record.get('provider')} | {record.get('model')} | {record.get('reason')} | "
                         f"{record.get('at')} | `{str(record.get('record_digest'))[:16]}...` |")
    else:
        lines.append("None: no configuration was conclusively excluded.")
    for problem in exclusions.get("problems") or []:
        lines.append(f"- **REFUSED EXCLUSION RECORD**: {problem}")
    lines.append("")
    return lines


def render_journal_health(journal: dict) -> list[str]:
    """Journal health plus every takeover / recovery / integrity event.
    The journal is fail-closed on the write side, so a gap here is a finding
    about the run, not about the file."""
    lines = ["## Execution-journal health", ""]
    if not journal.get("exists"):
        lines += ["No execution journal was found. A confirmatory run writes one fail-closed, so its "
                  "absence means either that no session ran or that the journal is not where this table "
                  "looked.", ""]
        return lines
    events = journal.get("events") or []
    counts = Counter(str(e.get("event")) for e in events)
    recoveries = journal.get("recoveries") or []
    if journal.get("healthy") and not recoveries:
        state = "no malformed lines."
    elif journal.get("healthy"):
        # CLEAN WITH A NOTE: damaged bytes that an explicit,
        # provenance-carrying segment boundary acknowledges do not refuse the
        # table — they are read as a boundary the audit trail spans.
        state = (f"CLEAN WITH A NOTE: {len(journal.get('malformed') or [])} malformed line(s) are "
                 f"acknowledged through line {journal.get('acknowledged_through_line')} by "
                 f"{len(recoveries)} explicit recovery segment(s); the damaged bytes are preserved.")
    else:
        state = (f"**UNHEALTHY — {len(journal.get('outstanding') or [])} MALFORMED line(s) that no "
                 f"recovery acknowledges**: {(journal.get('outstanding') or [])[:4]}. "
                 f"{journal.get('detail')}")
    lines.append(f"{len(events)} entries over {journal.get('line_count')} line(s), " + state)
    lines += ["", "| event | count |", "|---|---|"]
    for name, count in sorted(counts.items()):
        lines.append(f"| `{name}` | {count} |")
    lines.append("")
    if recoveries:
        lines += ["### Audit segment boundaries (immutable, bytes preserved)", "",
                  "| segment | at | acknowledged through line | malformed lines | session | operator |",
                  "|---|---|---|---|---|---|"]
        for record in recoveries:
            lines.append(f"| {record.get('segment')} | {record.get('at')} | "
                         f"{record.get('acknowledged_through_line')} | "
                         f"{record.get('malformed_lines')} | {record.get('session_id')} | "
                         f"{record.get('operator')} |")
        lines.append("")
    notable = [e for e in events
               if e.get("event") in ("schedule_lock_taken_over", "window_ledger_recovered",
                                     "execution_journal_recovered", "instrument_drift",
                                     "execution_integrity", "configuration_stopped",
                                     "inconclusive_accepted")]
    lines += ["### Takeover, recovery and integrity events", ""]
    if notable:
        for event in notable:
            lines.append(f"- `{event.get('event')}` at {event.get('at')} by session "
                         f"{event.get('session_id')} (runtime HEAD `{event.get('runtime_head')}`): "
                         f"{event.get('detail') or event.get('note') or event.get('tag') or ''}")
    else:
        lines.append("None: no lock takeover, no ledger recovery, no integrity quarantine, no "
                     "mid-run configuration stop, no inconclusive probe admitted.")
    lines.append("")
    return lines


def render_rate_limit_evidence(rows: list[dict]) -> list[str]:
    """For EVERY 429: the billed window, the rejected-attempt
    estimates, the current request's estimate, the TPM and RPM verdicts
    SEPARATELY, and the conservative combined bucket.

    This is the table that makes the two window-rule defects unrepeatable in
    reading: a reader can see that a "saturated" window was billed fact and
    not a pile of estimates, and can see the dimension that was previously
    discarded by the fixed priority."""
    lines = ["## Rate-limit (429) evidence, per attempt", "",
             "`billed` is the provider's own usage for requests it SERVED — the only established "
             "consumption. `rejected est.` is a chars/4 estimate for attempts it refused, and `current` is "
             "the request being refused; whether either consumes quota is "
             f"`{ADMISSION_SEMANTICS}`, so they widen an upper bound and never raise the established one. "
             "The token and request dimensions are evaluated INDEPENDENTLY and combined conservatively.", "",
             "| provider | model | selector | arm | billed (this cell) | rejected est. | current | "
             "TPM verdict | RPM verdict | combined |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    seen = False
    for row in rows:
        bucket, rule = classify_row(row)
        if not rule or not str(rule).startswith("rate_limit"):
            continue
        seen = True
        window = rate_limit_window(row)
        verdicts = window_dimension_verdicts(window, tpm_limit(row.get("provider"), row.get("model")),
                                             rpm_limit(row.get("provider"), row.get("model")))
        tokens, requests = verdicts["tokens"], verdicts["requests"]
        window = window if isinstance(window, dict) else {}

        def _dim(dim):
            if not dim:
                return "—"
            return (f"{dim['state']} ({dim['established']}/{dim['quota']}, ≤{dim['upper_bound']}"
                    + (f", share {dim['share']:.2f}" if dim.get("share") is not None else "") + ")")

        lines.append(
            f"| {row.get('provider')} | {row.get('model')} | {row.get('selector')} | {row.get('arm')} | "
            f"{window.get('billed_tokens_total')} ({window.get('billed_tokens_this_cell')}) | "
            f"{window.get('rejected_estimate_tokens_total')} | "
            f"{window.get('current_request_estimate_tokens')} | "
            f"{_dim(tokens)} | {_dim(requests)} | `{bucket}/{rule}` |")
        prospective = rate_limit_window_prospective(row)
        if isinstance(prospective, dict):
            lines.append(f"|  |  |  | *prospective* | "
                         f"{prospective.get('billed_tokens_total')} "
                         f"({prospective.get('billed_tokens_this_cell')}) | "
                         f"{prospective.get('rejected_estimate_tokens_total')} | "
                         f"{prospective.get('current_request_estimate_tokens')} | "
                         f"including the refused request | "
                         f"{prospective.get('requests_total')} requests | "
                         f"`{prospective.get('window_kind')}` |")
    if not seen:
        lines.append("| — | | | | | | | | | no 429 in this panel |")
    lines.append("")
    return lines


def render_ledger_status(rows: list[dict], ledger_health: dict | None) -> list[str]:
    """The window-ledger gap/health status: rows whose own attempt
    recorded a lost ledger line, and the health of the shared file itself."""
    lines = ["## Provider-window ledger status", ""]
    if ledger_health is None:
        lines.append("No window ledger was located for this schedule.")
    elif not ledger_health.get("exists"):
        lines.append("The shared window ledger does not exist: no provider request has been paced against "
                     "it, so no 429 in this panel could carry a window snapshot.")
    elif ledger_health.get("healthy"):
        lines.append(f"HEALTHY: {ledger_health.get('line_count')} line(s), no malformed evidence"
                     + (f", {len(ledger_health.get('recoveries') or [])} recovery segment(s)."
                        if ledger_health.get("recoveries") else "."))
    else:
        lines.append(f"**UNHEALTHY**: {ledger_health.get('detail')}. Rate-limit classifications whose "
                     f"window spans the damaged region are ambiguous by construction.")
    gaps = [r for r in rows
            if any(isinstance(q, dict) and q.get("ledger_write_failed") for q in (r.get("requests") or []))]
    unhealthy_attempts = [r for r in rows
                          if any(isinstance(q, dict) and q.get("window_ledger_unhealthy")
                                 for q in (r.get("requests") or []))]
    lines += ["", f"- rows carrying a `window_ledger_gap` (an append that did not land): {len(gaps)}",
              f"- rows whose 429 could not read the window at all: {len(unhealthy_attempts)}", ""]
    for row in gaps[:8]:
        lines.append(f"  - `{row.get('tag')}` {row.get('provider')}/{row.get('model')} {row.get('arm')}")
    if gaps:
        lines.append("")
    return lines


def render_execution_evidence(rows: list[dict], schedule: dict | None, evidence: dict | None) -> list[str]:
    """The execution evidence, RENDERED in a fixed order. Audit
    evidence for the existing estimands — never a new outcome."""
    evidence = evidence or {}
    lines = ["---", "", "# Execution evidence", "",
             "No new outcome metric and no new decision threshold: the two estimands, the suspicious-row "
             "sensitivity, the whole-triplet contrasts and the cost-ratio uncertainty are as "
             "pre-registered. What follows is the evidence a reader needs to believe the rows above "
             "describe the instrument that was sealed.", ""]
    lines += render_instrument_identity(rows, schedule)
    lines += render_probe_outcomes(evidence.get("journal") or {}, evidence.get("exclusions") or {})
    lines += render_journal_health(evidence.get("journal") or {})
    lines += render_rate_limit_evidence(rows)
    lines += render_ledger_status(rows, evidence.get("ledger_health"))
    return lines


def executed_cells(rows: list[dict]) -> list[dict]:
    """The ACTUAL temporal design, reconstructed from the rows' own execution
    record: each block's arms re-ordered by when they really
    ran, with `arm_position` re-derived from that order rather than copied
    from the schedule.

    `render_census` on the SCHEDULED cells says what was planned. It has
    never said what happened — and after an interruption the two can differ,
    which is exactly when an order claim needs checking. Rows without a
    timestamp keep their scheduled position and are marked, never guessed
    into an order.
    """
    def sort_key(row):
        return (str(row.get("started_at") or ""), str(row.get("session_id") or ""),
                row.get("actual_ordinal") if isinstance(row.get("actual_ordinal"), int) else 0)

    blocks: dict = {}
    for row in rows:
        if row.get("block_id") is None:
            continue
        blocks.setdefault(row["block_id"], []).append(row)
    out = []
    for block_id, group in sorted(blocks.items()):
        for position, row in enumerate(sorted(group, key=sort_key)):
            out.append({"provider": row.get("provider"), "model": row.get("model"),
                        "selector": row.get("selector"), "replicate": row.get("replicate"),
                        "arm": row.get("arm"), "block_id": block_id, "arm_position": position,
                        "session_id": row.get("session_id"), "started_at": row.get("started_at"),
                        "actual_ordinal": row.get("actual_ordinal"),
                        "planned_position": row.get("arm_position")})
    return out


def order_integrity(rows: list[dict]) -> list[str]:
    """Blocks whose three arms did NOT run consecutively in one session in
    the order the schedule dealt them. A finding, not a refusal — but never
    invisible: the Williams claim is about the executed sequence."""
    findings = []
    executed = executed_cells(rows)
    by_block: dict = {}
    for cell in executed:
        by_block.setdefault(cell["block_id"], []).append(cell)
    for block_id, group in sorted(by_block.items()):
        # A row with no `started_at` sorts as the empty string, i.e. FIRST,
        # and would silently invent an order for itself. Say so instead: an
        # unordered cell means this block's executed sequence is unknown,
        # not that it matched the plan.
        undated = [c["arm"] for c in group if not c.get("started_at")]
        if undated:
            findings.append(f"{block_id}: UNORDERED — no execution timestamp on arm(s) "
                            f"{sorted(str(a) for a in undated)}, so the executed sequence of this block "
                            f"cannot be reconstructed and no order claim covers it")
        sessions = {c["session_id"] for c in group}
        if len(sessions) > 1:
            findings.append(f"{block_id}: SPLIT across {len(sessions)} sessions {sorted(str(s) for s in sessions)}")
        planned = [c["planned_position"] for c in group]
        if any(p is None for p in planned):
            findings.append(f"{block_id}: at least one cell has no scheduled arm position")
        elif planned != sorted(planned):
            findings.append(f"{block_id}: executed OUT OF the scheduled arm order "
                            f"(scheduled positions ran as {planned})")
        ordinals = [c["actual_ordinal"] for c in group if isinstance(c["actual_ordinal"], int)]
        if len(ordinals) == len(group) and len(sessions) == 1 and ordinals:
            if max(ordinals) - min(ordinals) != len(ordinals) - 1:
                findings.append(f"{block_id}: its arms were NOT consecutive in the executing session "
                                f"(actual ordinals {sorted(ordinals)})")
    return findings


def render_census(cells: list[dict], source: str) -> list[str]:
    """The sequence / position / adjacency census, at the
    (provider, model), selector and (provider, model, selector) levels, with
    exact vs approximate stated per stratum rather than claimed once."""
    lines = [f"## Order balance census ({source})", ""]
    if not cells:
        return lines + ["No block/arm-position information on these rows — no order claim can be made.", ""]
    lines += SA.format_census(cells, ("provider", "model"), "Per (provider, model)")
    lines += SA.format_census(cells, ("selector",), "Per selector")
    lines += SA.format_census(cells, ("provider", "model", "selector"), "Per (provider, model, selector)")
    return lines


def render_table(rows: list[dict], label: str, files: list[Path], schedule: dict | None,
                 pilot: bool, schedule_complete: bool, arms: tuple, base_arm: str,
                 loaded: dict | None = None, evidence: dict | None = None) -> str:
    scheduled = schedule["cells"] if schedule else []
    confirmatory = bool(schedule) and SA.is_confirmatory(schedule)
    lines: list[str] = [f"# Arm table — {label}", ""]
    if pilot:
        lines += ["**INSTRUMENT SMOKE TEST / FIXED-PANEL PILOT** — this table answers \"did "
                  "the corrected machinery run, deliver artifacts and record the intended fields, and what "
                  "does it cost\", NOT \"which arm wins\". `VALID/derived` rows are admitted here and ONLY "
                  "here; they are excluded from every confirmatory estimate, and these rows are never pooled "
                  "with a confirmatory schedule's.", ""]
    else:
        lines += ["**CONFIRMATORY, FIXED PANEL** — the estimand is the average arm contrast over these exact "
                  "(provider, model, selector) strata. It is not an estimate for models in "
                  "general or for generated bookkeeping tasks in general: the roster and the selector panel are "
                  "FIXED factors, not a random sample. `VALID/derived` rows are refused.", ""]

    lines.append("Source files ({}): {}".format(len(files), ", ".join(p.name for p in files) if files else "none"))
    if schedule:
        lines.append(f"Schedule `{schedule['label']}` ({schedule['schedule_id']}), {schedule['n_cells']} cells, "
                     f"date stamp {schedule['date_stamp']}.")
        lines.append(f"Balance as scheduled: {schedule['balance']['statement']}")
        unrun_rule = ("NON-DELIVERY (the panel is complete)" if schedule_complete else
                      "OUT OF SCOPE (the panel is INCOMPLETE: they are reported as unrun and "
                      "left out of the operational denominator)")
        lines.append(f"Unrun scheduled cells are treated as {unrun_rule}.")
    if confirmatory:
        contract = schedule["experiment_contract"]
        lines += ["", "**Sealed experiment contract** (schedule v2). `schedule_id` hashes the "
                      "treatment, the world, the code and the analysis plan, not merely the order:", "",
                  f"- instrument commit `{contract.get('instrument_commit')}`",
                  f"- analysis plan `{contract.get('analysis_plan')}` sha256 "
                  f"`{contract.get('analysis_plan_sha256')}`",
                  f"- arm contract `{contract.get('arm_contract')}`",
                  f"- episode contract digest `{contract.get('expected_episode_contract_digest')}` at "
                  f"ceiling {contract.get('max_episode_output_tokens')}",
                  f"- replay contract digests `{contract.get('expected_replay_contract_digest_by_arm')}`",
                  f"- package lock `{contract.get('package_lock')}`",
                  f"- failure map digest `{contract.get('failure_map_digest')}`",
                  f"- manifest rotation `{(contract.get('manifest') or {}).get('rotation_id')}`, content "
                  f"digest `{(contract.get('manifest') or {}).get('manifest_content_digest')}`",
                  f"- provider quotas: {(contract.get('provider_quotas') or {}).get('source')}",
                  ""]
        if loaded is not None:
            closure = derive_run_closure(loaded)
            lines += [f"**Run closure, DERIVED** (never declared): {closure['n_ran']} of "
                      f"{closure['n_cells']} scheduled cells have exactly one exactly-matching row; "
                      f"{closure['n_unrun']} unrun, {closure['n_integrity']} quarantined for execution "
                      f"integrity. Panel "
                      f"{'COMPLETE' if closure['complete'] else 'INCOMPLETE'}.", ""]
            # THE CENSUS INVARIANTS, computed and ASSERTED
            # here — raises `CensusInvariantViolation` (fails the whole
            # render, never merely prints) the instant this and the
            # `### Scheduled but not run` section below could disagree.
            census = census_breakdown(scheduled, loaded, rows)
            lines += [f"**Census invariants, asserted**: {census['scheduled']} scheduled "
                      f"= {census['exactly_matched']} exactly-matched + {census['unrun']} unrun + "
                      f"{census['integrity']} execution-integrity; {census['exactly_matched']} "
                      f"exactly-matched = {census['valid']} valid + {census['provider_failed']} "
                      f"provider_failed + {census['instrument_invalid']} instrument_invalid + "
                      f"{census['other_classified']} other_classified. Either disagreeing with the "
                      f"header above would have failed this render rather than printed it.", ""]
            lines += render_correction_audit(schedule, rows, census)
            if loaded["integrity"]:
                lines += ["**EXECUTION INTEGRITY REFUSALS** — these cells have a file but not exactly one "
                          "exactly-matching row. They are counted as neither run nor unrun and enter no "
                          "estimate:", ""]
                lines += [f"- `{item}`" for item in loaded["integrity"]]
                lines.append("")
            if loaded["unexpected"]:
                lines += ["**UNEXPECTED FILES carrying this schedule's label** — refused, not loaded (a "
                          "substring match is how an unregistered row joins a registered experiment):", ""]
                lines += [f"- `{name}`" for name in loaded["unexpected"]]
                lines.append("")
        # THE INSTRUMENT REFUSAL, IN THE ARTEFACT. It is a
        # refusal, not an annotation: the exit code says 4 and no confirmatory
        # estimand below may be read.
        drift = instrument_drift_rows(rows, schedule)
        if drift:
            lines += ["**INSTRUMENT DRIFT — CONFIRMATORY ESTIMANDS REFUSED (exit 4)**. These rows carry "
                      "a different or MISSING instrument/environment digest. A row produced by an "
                      "instrument that is not the sealed one is not evidence about the sealed one:", ""]
            lines += [f"- `{item}`" for item in drift[:12]]
            lines.append("")
        journal_state = (evidence or {}).get("journal") or {}
        if journal_state.get("exists") and not journal_state.get("healthy"):
            lines += ["**EXECUTION JOURNAL UNHEALTHY — CONFIRMATORY ESTIMANDS REFUSED (exit 4)**: "
                      f"{journal_state.get('detail')}. The audit sequence that explains takeover, "
                      "recovery, inconclusive classification and integrity state is incomplete. The "
                      "damaged bytes are preserved; recovery is an explicit operator act with an "
                      "immutable segment boundary, and it is refused before the first real row exists.",
                      ""]
    if not schedule:
        lines.append("No schedule given: the SCHEDULED operational-delivery rate is reported as `n/a`. It is "
                     "deliberately not approximated from the rows that happen to exist — that would be the "
                     "conditional estimand under another name.")

    if schedule:
        ran_keys_header = {(r.get("provider"), r.get("model"), r.get("selector"), r.get("replicate"),
                            r.get("arm")) for r in rows}
        missing = sum(1 for c in scheduled
                      if (c["provider"], c["model"], c["selector"], c["replicate"], c["arm"])
                      not in ran_keys_header)
        if missing:
            lines.append(f"**INCOMPLETE PANEL**: {missing} of {len(scheduled)} scheduled cells have no row. "
                         f"An incomplete panel is reported as incomplete — it is never "
                         f"completed by dropping a model. The full roster panel is incomplete, so no "
                         f"pooled all-model arm decision is made; within-model contrasts use only "
                         f"complete eligible blocks and are reported as preregistered fixed-panel "
                         f"evidence, not as recommendations beyond those named model/task strata. "
                         f"The unrun cells are listed at the end of this table.")
        else:
            lines.append(f"Panel COMPLETE: all {len(scheduled)} scheduled cells have a row.")

    counted = [r for r in rows if not is_quarantined(r)]
    statuses = Counter(row_status(r)[0] for r in counted)
    lines.append(f"Rows loaded: {len(rows)} ({len(rows) - len(counted)} quarantined). "
                 f"Re-derived validity: {dict(sorted(statuses.items()))} "
                 f"(every predicate recomputed by `measure_budget.validate_row` from the archived fields; "
                 f"no stored `budget_accounting` string is trusted).")
    n_suspicious = sum(1 for r in counted if is_suspicious(r))
    lines.append(f"SUSPICIOUS rows (characters-per-token heuristic, a diagnostic and NOT an invalidation): "
                 f"{n_suspicious} of {len(counted)}. Every table below is printed twice, with "
                 f"and without them.")

    digests = {contract_identity(r) for r in counted}
    lines.append(f"(episode, replay) contract pairs present: {sorted(str(d) for d in digests)}")
    pins = {(r.get("temperature"), r.get("top_p"), r.get("seed")) for r in counted}
    lines.append(f"Sampling pins seen (temperature, top_p, seed): {sorted(pins, key=str)}")
    if len(pins) > 1:
        lines.append("  **WARNING**: more than one sampling configuration is present.")
    lines.append("")

    # CONFIGURATION-WIDE capability exclusion, applied BEFORE
    # any comparison: a provider/model that cannot carry one arm's replayed
    # payload cannot support a contrast among the three arms at all.
    incompatible = capability_incompatible_configurations(
        rows, ((evidence or {}).get("exclusions") or {}).get("records") or ())
    comparison_rows = rows
    if incompatible:
        comparison_rows = [r for r in rows if (r.get("provider"), r.get("model")) not in incompatible]
        lines += ["## Configurations excluded WHOLE for capability incompatibility", "",
                  "The client cannot carry a field this provider/model family requires (or the family "
                  "rejects a field the replay policy sends). That is a client/provider property, not an "
                  "arm outcome: the configuration leaves the comparison entirely, before any contrast, "
                  "rather than losing the individual blocks that happened to fail.", "",
                  "| provider | model | rows | evidence |", "|---|---|---|---|"]
        for (provider, model), reasons in sorted(incompatible.items(), key=str):
            lines.append(f"| {provider} | {model} | {len(reasons)} | {'; '.join(sorted(set(reasons))[:4])} |")
        lines.append("")

    lines += render_census(scheduled or [r for r in rows if r.get("block_id")],
                           "as scheduled" if scheduled else "as executed")
    # The ACTUAL temporal census, always beside the scheduled one.
    lines += render_census(executed_cells(rows), "as EXECUTED, reconstructed from timestamps/session ids")
    findings = order_integrity(rows)
    lines += ["### Executed-order integrity", ""]
    lines += ([f"- {f}" for f in findings] if findings else
              ["No block ran split across sessions or out of the scheduled arm order."])
    lines.append("")

    lines += render_strata(comparison_rows, scheduled, pilot, schedule_complete, "All rows")
    clean = [r for r in comparison_rows if not is_suspicious(r)]
    lines += render_strata(clean, scheduled, pilot, schedule_complete,
                           f"Excluding {len(comparison_rows) - len(clean)} SUSPICIOUS row(s)")
    # THE PRIMARY CONTRAST, TWICE. The decision-bearing table
    # used to receive the sensitivity treatment only in the two stratum
    # sections; the paired delivery contrast and the effective-cost ratio —
    # the numbers an arm decision is read off — were computed once, over all
    # rows. Whole triplets are dropped AFTER each filter, so the exclusion
    # cannot half-drop a block.
    all_stats = ratio_stats(comparison_rows, arms, base_arm, pilot)
    clean_stats = ratio_stats(clean, arms, base_arm, pilot)
    lines += render_ratios(comparison_rows, arms, base_arm, pilot,
                           title="Primary contrasts, within (provider, model) — ALL eligible rows",
                           stats=all_stats)
    lines += render_ratios(clean, arms, base_arm, pilot,
                           title=f"Primary contrasts, within (provider, model) — EXCLUDING "
                                 f"{len(comparison_rows) - len(clean)} suspicious row(s)",
                           stats=clean_stats)
    lines += compare_ratio_stats(all_stats, clean_stats, arms, base_arm)
    # The failure census stays SINGLE and complete: it is the audit of every
    # row, and excluding rows from an audit of exclusions makes no sense.
    lines += render_failures(rows)
    lines += render_cross_model(comparison_rows,
                                "Cross-model operational summary, ALL eligible rows "
                                "(no pooled token statistic)")
    lines += render_cross_model(clean,
                                f"Cross-model operational summary, EXCLUDING "
                                f"{len(comparison_rows) - len(clean)} suspicious row(s)")

    lines += ["## Excluded rows", "",
              "### Provider-failed / quarantined", "",
              "| provider | model | selector | arm | replicate | bucket / rule | status | reasons |",
              "|---|---|---|---|---|---|---|---|"]
    any_q = False
    for r in rows:
        if is_quarantined(r):
            any_q = True
            bucket, rule = classify_row(r)
            lines.append(f"| {r.get('provider')} | {r.get('model')} | {r.get('selector')} | {r.get('arm')} | "
                         f"{r.get('replicate')} | {bucket}/{rule} | {r.get('status')} | {r.get('reasons')} |")
    if not any_q:
        lines.append("| — | | | | | | none | |")
    lines += ["", "### Failed re-derived validation (excluded from cost)", "",
              "| provider | model | selector | arm | replicate | stored status | re-derived reasons |",
              "|---|---|---|---|---|---|---|"]
    any_i = False
    for r in rows:
        if is_quarantined(r):
            continue
        status, reasons = row_status(r)
        if status == "INVALID" or (status == "VALID/derived" and not pilot):
            any_i = True
            lines.append(f"| {r.get('provider')} | {r.get('model')} | {r.get('selector')} | {r.get('arm')} | "
                         f"{r.get('replicate')} | {r.get('budget_accounting')} | {status}: {reasons} |")
    if not any_i:
        lines.append("| — | | | | | none | |")
    lines.append("")

    if schedule:
        # ONE authority for "unrun" — `loaded["cell_rows"]`,
        # the exact per-file map `census_breakdown` and the header's own "Run
        # closure" line already read, never a second recomputation from a
        # `tag` string that is not unique across models.
        lines += render_unrun_section(scheduled, loaded, rows)
    lines += render_execution_evidence(rows, schedule, evidence)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag-prefix", nargs="+", default=None,
                        help="PILOT loading only: tag substrings to match against the part of each "
                             "budget_*.json filename after the date (e.g. Ap_ B1p_ B2p_). A confirmatory "
                             "table derives its exact file set from the schedule and ignores this")
    parser.add_argument("--label", required=True, help="table label; written to reviews/arms_<label>.md")
    parser.add_argument("--schedule", default=None,
                        help="the schedule file these rows execute. REQUIRED for the scheduled "
                             "operational-delivery rate; without it that estimand is reported n/a")
    parser.add_argument("--schedule-complete", action="store_true",
                        help="PILOT ONLY: declare the schedule finished, so unrun cells count as "
                             "NON-DELIVERY. REFUSED for a sealed confirmatory schedule, where completion is "
                             "DERIVED from the exact cell map — an operator must not be able "
                             "to declare a run finished after seeing its results")
    parser.add_argument("--pilot", action="store_true",
                        help="a pilot / instrument smoke-test table: VALID/derived rows are admitted and the "
                             "table is labelled as not decision-bearing")
    parser.add_argument("--arms", nargs="+", default=["A", "B1", "B2"])
    parser.add_argument("--base-arm", default="A")
    parser.add_argument("--reviews-dir", default=None, help="defaults to <checkout>/reviews")
    args = parser.parse_args()

    reviews_dir = Path(args.reviews_dir) if args.reviews_dir else ROOT / "reviews"
    schedule_path = Path(args.schedule) if args.schedule else None
    schedule = SA.load_schedule(schedule_path) if schedule_path else None
    confirmatory = bool(schedule) and SA.is_confirmatory(schedule)
    loaded = None
    schedule_complete = args.schedule_complete
    # The execution evidence, all of it addressed exactly as
    # the executor addresses it: the journal beside the reviews directory, the
    # exclusion records and the shared window ledger beside the schedule.
    evidence = None
    if schedule is not None:
        evidence = {
            "journal": load_execution_journal(SA.journal_path_for(reviews_dir, schedule)),
            "exclusions": configuration_exclusions(schedule_path, schedule),
            "ledger_health": mb.window_ledger_health(Path(str(schedule_path) + ".window.jsonl")),
        }

    if confirmatory:
        if args.schedule_complete:
            print("REFUSED: --schedule-complete on a SEALED confirmatory schedule. Completion is DERIVED "
                  "from the exact cell map: an operator who can toggle it after seeing the "
                  "results decides the denominator with the outcome in view.", file=sys.stderr)
            return 2
        # The exact schedule-derived file set: no tag-substring globbing, no
        # duplicate rows, no unregistered files.
        loaded = load_scheduled_rows(reviews_dir, schedule)
        rows, files = loaded["rows"], loaded["files"]
        if loaded["unexpected"]:
            print(f"REFUSED: {len(loaded['unexpected'])} file(s) carry this schedule's label but are not "
                  f"one of its {len(loaded['cell_rows'])} expected cell files: "
                  f"{loaded['unexpected'][:6]}. An unregistered row must not join a registered experiment.",
                  file=sys.stderr)
            return 2
        closure = derive_run_closure(loaded)
        schedule_complete = closure["complete"]
        print(f"exact cell map: {closure['n_ran']}/{closure['n_cells']} cells have exactly one matching "
              f"row; {closure['n_unrun']} unrun, {closure['n_integrity']} execution-integrity quarantines; "
              f"panel {'COMPLETE' if closure['complete'] else 'INCOMPLETE'}")
    else:
        if not args.tag_prefix:
            print("--tag-prefix is required unless --schedule names a sealed confirmatory schedule",
                  file=sys.stderr)
            return 2
        rows, files = load_rows(reviews_dir, args.tag_prefix)

    # BEFORE the zero-row early return (adversarial review, INFO): a tampered
    # exclusion record on a panel that has not run yet must still exit 2. The
    # old order let "no rows" mask an unauthenticatable exclusion, which is
    # exactly the state a resumed confirmatory run starts in.
    if evidence and evidence["exclusions"].get("problems"):
        print(f"REFUSED: {len(evidence['exclusions']['problems'])} configuration-exclusion record(s) "
              f"beside the schedule cannot be authenticated: {evidence['exclusions']['problems'][:4]}. "
              f"An exclusion whose content digest does not recompute is not an exclusion.", file=sys.stderr)
        return 2

    # THE INSTRUMENT REFUSAL, BEFORE the zero-row early return. A drifted
    # row never reaches `loaded["rows"]` — the digests are
    # part of exact admission — so a panel whose rows are ALL drifted would
    # otherwise report "no rows to read" and exit 1, which tells a caller
    # gating on the exit code nothing about why.
    if confirmatory and loaded is not None:
        drift = instrument_drift_rows(loaded["file_rows"], schedule)
        if drift:
            print(f"REFUSED (exit 4): {len(drift)} archived row(s) under this schedule's own cell files "
                  f"carry a different or MISSING instrument/environment digest. A row produced by an "
                  f"instrument that is not the sealed one is not evidence about the sealed one, and no "
                  f"confirmatory estimand may be read from this panel:\n  " + "\n  ".join(drift[:8]),
                  file=sys.stderr)
            return 4

    if not rows:
        print(f"no rows to read under {reviews_dir}"
              + (f" (tag-prefix {args.tag_prefix})" if args.tag_prefix else ""))
        return 1

    if schedule and not confirmatory:
        foreign = [r for r in rows if r.get("schedule_id") not in (None, schedule["schedule_id"])]
        if foreign:
            print(f"REFUSED: {len(foreign)} row(s) carry a different schedule_id than "
                  f"{schedule['schedule_id']}: {sorted({r.get('schedule_id') for r in foreign})}. "
                  f"Two schedules' rows are not one experiment — narrow --tag-prefix.", file=sys.stderr)
            return 2

    # REFUSE, do not warn.
    offences = (check_pooling(rows, ("provider", "model", "selector", "arm"))
                + check_pooling(rows, ("provider", "model", "arm")))
    if offences:
        print("REFUSED: a condition contains rows from more than one (episode, replay) contract. "
              "Rows can share a world, a prompt and a ceiling and still not be comparable because the client "
              "replayed the conversation differently.", file=sys.stderr)
        for offence in offences:
            print(f"  {offence}", file=sys.stderr)
        return 2

    # THE CENSUS INVARIANTS: a violation FAILS the render —
    # nothing is written, never a self-contradictory census printed instead.
    try:
        text = render_table(rows, args.label, files, schedule, args.pilot, schedule_complete,
                            tuple(args.arms), args.base_arm, loaded, evidence)
    except CensusInvariantViolation as exc:
        print(f"REFUSED (exit 5): the census invariant does not hold — {exc}. The renderer will not "
              f"print a self-contradictory census; the table is NOT written.",
              file=sys.stderr)
        return 5
    out_path = reviews_dir / f"arms_{args.label}.md"
    out_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {out_path}")

    # THE TWO HARD REFUSALS. The table is still
    # WRITTEN — suppressing the artefact would hide the very findings these
    # refusals are about — but the exit code must not say "fine", and a caller
    # that gates on it must not be able to read a confirmatory estimate off a
    # drifted instrument or an unreadable audit trail.
    if confirmatory:
        drift = instrument_drift_rows(rows, schedule)
        if drift:
            print(f"EXIT 4: {len(drift)} decision-bearing row(s) carry a different or MISSING "
                  f"instrument/environment digest. A row produced by an instrument that is not the "
                  f"sealed one is not evidence about the sealed one, and no confirmatory estimand may "
                  f"be read from this panel:\n  " + "\n  ".join(drift[:8]), file=sys.stderr)
            return 4
        journal_state = (evidence or {}).get("journal") or {}
        if journal_state.get("exists") and not journal_state.get("healthy"):
            print(f"EXIT 4: the execution journal is UNHEALTHY — {journal_state.get('detail')}. The "
                  f"audit events that explain takeover, recovery, inconclusive classification and "
                  f"integrity state are not a complete machine-readable sequence, so the confirmatory "
                  f"estimands are refused. The bytes are preserved; recover deliberately with "
                  f"tests/run_arms.py --recover-execution-journal (refused before the first real row "
                  f"exists — abort and reseal instead).", file=sys.stderr)
            return 4
        drift_events = [e for e in (journal_state.get("events") or [])
                        if e.get("event") == "instrument_drift"
                        or e.get("reason") == "instrument_drift"]
        if drift_events:
            print(f"EXIT 4: the execution journal records {len(drift_events)} instrument_drift "
                  f"quarantine(s): a cell of this schedule was refused because the code or the "
                  f"interpreter about to run it was not the sealed instrument. The panel cannot be read "
                  f"as complete until that is resolved by a new schedule or a predeclared replacement "
                  f"record. First: {drift_events[0].get('detail')}", file=sys.stderr)
            return 4
    if loaded is not None and loaded["integrity"]:
        # The table is still WRITTEN — the quarantines are listed in it, and
        # suppressing the artefact would hide them. But the exit code must
        # not say "fine": a confirmatory panel with an unresolved
        # execution-integrity cell is not a readable panel, and a caller that
        # gates on the exit code has to see that.
        print(f"EXIT 4: {len(loaded['integrity'])} execution-integrity quarantine(s) remain; the panel "
              f"cannot be read as complete until each is resolved by a new schedule or a predeclared "
              f"replacement record.", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
