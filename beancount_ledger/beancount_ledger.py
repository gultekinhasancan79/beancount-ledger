"""Beancount ledger environment — bank reconciliation and month-end close.

The agent is dropped into a small trading company's books with the source
documents an accountant would actually have: a ledger, a bank statement, master
data, a policy note, and a prior-period file that is not relevant. It reads its
way to the discrepancies, posts them, and writes the ledger back.

Scoring is entirely deterministic — see `reward.py`. Nothing is judged.

The world is explored through tools rather than pasted into context: the agent
lists, greps and reads. That keeps a rollout inside its token budget while
leaving the world as wide as it needs to be to feel real. The ledger is the
exception it has to be — the task is to write the COMPLETE file back, so
`read_file` returns it whole, exactly as the scorer sees it (`logical_text`:
strict UTF-8, line endings normalised to LF), and an envelope enforced before
the episode is what keeps that affordable.
"""

from __future__ import annotations

import contextvars
import enum
import hashlib
import inspect
import json
import math
import os
import re
import shutil
import stat
import tempfile
import threading
import time
import typing
import traceback
import uuid
from decimal import Decimal
from pathlib import Path

import verifiers as vf
from datasets import Dataset

from .candidate.committed import (
    AUDIT_DIR,
    MAX_AUDIT_FILE_BYTES,
    MAX_AUDIT_REVISIONS,
    MAX_AUDIT_TOTAL_BYTES,
    NO_ARTIFACT,
    OUTCOME_DELIVERED,
    OUTCOME_POLICY_BLOCKED,
    OUTCOME_PROTOCOL_REJECTED,
    PUBLICATION_FILE,
    ScoreOutcome,
    rejection_result_digest,
    CommittedSubmission,
    DeliveryReceipt,
    InitializationFailure,
    ProtocolRejected,
    commit,
    load_contract,
    new_receipt,
    reject,
    render_committed,
    score_committed,
)
from .candidate.normalise import Accepted, EvaluationFailure, ProtocolFailure, parse_once
from .candidate.canonical import canonical_decimal
from .candidate.normalise import MAX_BYTES
from .graph.derive import DerivationError, derive_contract
from .graph.project import ProjectionError
from .graph.worlds import REGISTRY

HERE = Path(__file__).resolve().parent
WORLD_DIR = HERE / "world"
TASK_DIR = HERE / "tasks"

#: The distributions the MODEL-FACING contract is generated from, pinned
#: exactly in `pyproject.toml` (Codex T48 §8, T47 answer 7).
#:
#: `episode_contract_digest()` binds the tool schemas, and we do not write
#: them: `verifiers` calls `openai-agents`' `function_schema`, which parses the
#: docstrings with `griffelib` and emits the JSON schema through `pydantic` /
#: `pydantic-core`. A minor bump in any of those can change a title, a
#: `required` array, an enum form or the description text — the digest moves
#: and no line of ours changed. `openai` is the client that puts that schema
#: on the wire, `datasets` carries the prompt rows, and `beancount` is the
#: loader the scorer's verdict comes from.
#:
#: The pins do NOT enter the digest. Binding them there would refuse every
#: manifested world on a patch bump that changed nothing the model can see,
#: which is the wrong loudness; instead every rollout carries
#: `state["piv_library_versions"]` as provenance and a test compares the
#: installed set to `pyproject.toml`, so a bump fails the battery rather than
#: drifting through it. `griffe` is imported under that name but ships in the
#: `griffelib` distribution, which is what `importlib.metadata` knows.
PINNED_LIBRARIES = ("verifiers", "openai", "openai-agents", "griffelib", "pydantic",
                    "pydantic-core", "datasets", "beancount")


_LIBRARY_VERSIONS: dict | None = None


def library_versions() -> dict:
    """`{distribution: version}` for `PINNED_LIBRARIES`, as installed.

    A missing distribution is recorded as None rather than raising: this rides
    on every rollout, and an environment that can still serve a task must not
    die because a provenance lookup failed. The pin test is what makes an
    unexpected value loud.

    Memoised, and returned as a fresh dict. Installed versions cannot change
    inside a process, `importlib.metadata` walks the whole path to answer, and
    this is asked once per rollout; the copy is so a caller that mutates the
    dict it was handed cannot poison the next rollout's provenance.
    """
    global _LIBRARY_VERSIONS
    if _LIBRARY_VERSIONS is None:
        import importlib.metadata as _metadata

        versions = {}
        for name in PINNED_LIBRARIES:
            try:
                versions[name] = _metadata.version(name)
            except Exception:                      # noqa: BLE001 — provenance, never a serving failure
                versions[name] = None
        _LIBRARY_VERSIONS = versions
    return dict(_LIBRARY_VERSIONS)


LEDGER = "ledger.beancount"
MAX_TOOL_OUTPUT_LINES = 120
MAX_READ_LINES = 200
MAX_GREP_PATTERN = 128
MAX_GREP_HITS = 200

# --------------------------------------------------------------------------
# THE INPUT SIDE OF THE BUDGET (Codex T48 §7, Q9)
#
# The episode's output ceiling prices what the model EMITS. Nothing priced
# what it is SENT, and the ledger is agent-controlled, so the two doors that
# echo it had to be bounded as well as the whole read.
#
# MAX_TOOL_OUTPUT_BYTES bounds ONE bounded reply. The line caps above were not
# a byte bound: a legal in-envelope ledger of 119 lines x 400 bytes is under
# MAX_TOOL_OUTPUT_LINES and under MAX_GREP_HITS, and one `grep` over it
# returned 49,990 bytes — MORE than a whole ledger read — with twenty such
# calls representable in a single turn. Measured honest use over the shipped
# world and 50 generated ones (train:0-24, both profiles): the largest sliced
# read is 3,728 bytes and the largest broad grep ("2025-" over every file) is
# 10,478. 16,000 is 1.5x that grep, 4x that slice and a third of the
# observation envelope, so it truncates nothing an honest reading does.
#
# NOT applied to the whole ledger read: that one observation is deliberately
# privileged and has its own envelope, and truncating it would hand back a
# file the agent cannot round-trip — the defect the whole read exists to fix.
MAX_TOOL_OUTPUT_BYTES = 16_000

# MAX_EPISODE_OBSERVATION_BYTES bounds the AGGREGATE. A per-reply cap alone
# still leaves `calls per turn x turns` copies, so the two closures Codex
# offered are both taken: the idempotent full read (one ledger per revision)
# and an aggregate observation budget with a public, digest-bound refusal.
# Once `state["piv_observation_bytes"]` reaches this, every OBSERVING tool
# (list_files, read_file, grep, run_beancount) is answered
# OBSERVATION_BUDGET_SPENT and no file is read; `write_ledger` and `submit`
# still run, because an agent must always be able to deliver what it has.
#
# 16 envelopes. A thorough honest episode measures around 110 KB (every public
# file read, three whole ledger reads, five broad greps) and the worst legal
# one — a 48,000-byte written ledger re-read on every revision — around 380 KB,
# so this is roughly 2x the worst honest case and 7x a realistic one, while it
# turns the 23 MB grep amplification into 768 KB. Counted per REPLY, as each
# is produced, so the bound holds inside one turn's call list too; the true
# maximum is this plus the one reply that crosses it.
MAX_EPISODE_OBSERVATION_BYTES = 16 * 48_000

# The ledger is observed WHOLE, in one call (Codex T46 §4), so the envelope
# that makes that safe is a property of the world rather than a hope about
# the generator. Measured over 231 minted worlds under the test secret (the
# 18 CI sentinels plus train:0-99 standard, train:0-59 hard, eval:0-59
# standard, GENERATOR_VERSION 8): MAXIMUM 13,630 bytes / 303 logical lines;
# minimum 7,102 bytes / 157 lines; the shipped hand-authored world is 3,314
# bytes / 74 lines. The envelope is >= 3x that maximum (3.52x on bytes,
# 3.30x on lines), which leaves room for the generator to grow a world
# without a silent contract change and still keeps one read around 12K
# tokens in the worst admissible case.
#
# Enforced at FOUR doors, all with this one predicate
# (`ledger_envelope_breach`): `_verify_public_world` and `load_environment`
# before the episode (a breach there is an evaluator failure, never a partial
# view); `write_ledger`, which refuses an over-envelope candidate publicly and
# stores nothing; and `_whole_ledger_reply`, which refuses to SEND an
# over-envelope stored ledger (Codex T48 §6, Q9). The last two are public
# refusals rather than raises — a tool argument must never become our failure
# — and because both use the same predicate over the same bytes, the read
# refusal is unreachable through anything the agent was allowed to write.
LEDGER_ENVELOPE_BYTES = 48_000
LEDGER_ENVELOPE_LINES = 1_000

# The observation contract, as an exact list. "Inside the workspace" is a
# containment property; readability is a CAPABILITY, and the two are not the
# same set: a private receipt, the temp file of an atomic write, a debug log
# or a misplaced answer key inside the workspace would all be readable under
# containment alone. The read tools accept only these names — not paths — and
# a test pins the list to the world directory, so a new world file must be
# declared here on purpose.
PUBLIC_FILES = (
    "manifest.md", "policy.md", "accounts.csv", "customers.csv", "vendors.csv",
    "archive_prior_period.csv", "ledger.beancount", "bank_statement.csv",
)
MUTABLE_PUBLIC_FILE = LEDGER

# The two names the episode contract turns on, as constants rather than
# literals scattered through the loop: exactly one tool mutates the world and
# exactly one tool ends the episode. A test pins both against `tool_map`, so
# a second write door or a second terminal door cannot appear by accident.
WRITE_TOOL = "write_ledger"
TERMINAL_TOOL = "submit"


class EpisodePhase(enum.StrEnum):
    """The episode's state, as one named value in `state["piv_phase"]`.

    Every tool handler and every stop condition reads this instead of its own
    boolean, so "is the episode over?" and "is there anything to deliver?"
    have exactly one answer apiece. The state machine is spelled out in
    `BeancountLedgerEnv`'s docstring; the transitions are made in exactly
    two places — `write_ledger` and `submit` — and nowhere else.

    A `StrEnum` because rollout state is carried through the framework and
    serialised in outputs: the value is its own name, and a comparison
    against the string still works if it survives a round trip.
    """

    #: ACTIVE, nothing successfully stored yet — the untouched original is
    #: what is on disk. `submit` is refused here.
    NO_CANDIDATE = "ACTIVE_NO_CANDIDATE"
    #: ACTIVE, a candidate is stored and the protocol boundary accepted it.
    #: The only phase from which `submit` is accepted.
    CANDIDATE = "ACTIVE_CANDIDATE"
    #: ACTIVE, a candidate is stored and the protocol boundary REFUSED it
    #: (unparseable, or a construct the contract forbids). `submit` is
    #: refused, naming the refusal, and the agent may write again.
    REJECTED = "ACTIVE_REJECTED"
    #: The agent called `submit` and it was accepted. The workspace is frozen
    #: and the delivered content hash is bound. Nothing executes afterwards.
    TERMINAL = "TERMINAL"


ACTIVE_PHASES = frozenset({EpisodePhase.NO_CANDIDATE, EpisodePhase.CANDIDATE, EpisodePhase.REJECTED})


def episode_phase(state) -> EpisodePhase:
    """The rollout's current phase. Absent state reads as the initial phase."""
    if state is None:
        return EpisodePhase.NO_CANDIDATE
    return EpisodePhase(state.get("piv_phase", EpisodePhase.NO_CANDIDATE))


# --------------------------------------------------------------------------
# the episode's terminal budgets
#
# Declared here, above `SYSTEM_PROMPT`, because the prompt DISCLOSES them and
# is built from them: Codex T47 §6 asked for the ceiling and the no-tool limit
# to be public, and a prompt that repeats a number instead of deriving it is
# one edit away from lying to the agent about its own contract.
# --------------------------------------------------------------------------

#: The turn budget (PLAN §6). The framework checks stop conditions at the top
#: of an iteration and executes a turn's calls at the top of the NEXT one, so
#: the calls of the turn that reaches `MAX_TURNS` are never run: the budget for
#: an EXECUTED call is `MAX_TURNS - 1`, and the prompt says so.
MAX_TURNS = 25
# How many assistant turns in a row without a tool call end the episode. Three
# is enough to distinguish "the model was cut off once and recovered" from
# "the model has stopped calling tools"; the turn cap (25) would end it anyway,
# so this only bounds how much of the budget the nudge itself may consume.
MAX_CONSECUTIVE_NO_TOOL_TURNS = 3
# The truncation bound (Codex T44 §9 item 4). A turn cut off at the completion
# cap is a no-tool turn, so this K rides the SAME run of consecutive no-tool
# turns and is deliberately equal to it: a larger K could not fire (the no-tool
# limit would end the episode first) and a smaller one would be the effective
# bound for every failure mode, not just truncation. What is separate is the
# COUNTER — `piv_consecutive_truncated_turns` advances only while every turn in
# the run was truncated — so an unbroken run of truncated turns ends under
# `piv_truncation_limit` ("looping at the completion cap") while a mixed run
# ends under `piv_no_tool_call_limit` ("stopped calling tools"). Same budget,
# two distinguishable diagnoses.
MAX_CONSECUTIVE_TRUNCATED_TURNS = MAX_CONSECUTIVE_NO_TOOL_TURNS
# The per-episode output ceiling (Codex T46 §6), in completion tokens summed
# over every turn. The M2 measurement arms differ in their PER-TURN cap
# (8K vs 16K) and must be compared at EQUAL total output, or the comparison
# measures the budget rather than the policy. The framework's own
# `max_total_completion_tokens_reached` only notices the ceiling after an
# overshooting turn — a 16K arm could end 16K over it — so the ceiling is
# also enforced on the REQUEST, by `BeancountLedgerEnv.get_model_response`
# clamping each turn's completion cap to what is left. A value <= 0 disables
# both the clamp and the stop.
MAX_EPISODE_OUTPUT_TOKENS = 40_000
# The pending-call-at-budget rule as one sentence, so the episode contract
# digest binds a statement of it. It is DOCUMENTATION, not the mechanism: the
# behaviour lives in `piv_output_budget_exhausted`'s one-shot deferral and
# `_seal_if_budget_spent`, and the prompt says the same thing in the agent's
# words. Changing either without changing this sentence leaves the digest
# unmoved, so the three are kept in step by hand, not by construction.
PENDING_CALL_AT_BUDGET = (
    "tool calls emitted on the turn that exhausts the output ceiling are executed once, in call "
    "order, and the episode is then sealed without another model request; calls emitted on the "
    "turn that reaches max_turns are never executed"
)

#: The ONE sampling field a clamped request carries, and the only spelling
#: every client in verifiers 0.3.1 understands. Measured across the library:
#:
#:   chat completions (and the token/NeMoRL variants) — `max_tokens` is RENAMED
#:       to `max_completion_tokens`, overwriting any value already there, so
#:       the request body carries exactly one field, ours;
#:   responses — both are popped and mapped to `max_output_tokens` (`max_tokens`
#:       winning) ONLY `if "max_output_tokens" not in sampling_args`: a caller
#:       who states that third spelling keeps it, and would keep it unclamped.
#:       So all three are read and removed here — see `TOKEN_CAP_SPELLINGS`;
#:   renderer — `max_tokens or max_completion_tokens`;
#:   anthropic messages — ONLY `max_tokens` is understood; it is popped and
#:       anything left over is forwarded verbatim into `messages.create(**…)`,
#:       so emitting `max_completion_tokens` there both loses the clamp (a
#:       warning and a 4096 fallback) and hands the SDK a keyword it has no
#:       parameter for;
#:   completions — passes everything through to the legacy `completions.create`,
#:       which knows `max_tokens` and not the other.
#:
#: So `max_tokens` it is: one field out, one field on the wire, every client.
TOKEN_CAP_FIELD = "max_tokens"


def _token_cap(field: str, value) -> int | None:
    """A caller's per-turn cap as a positive int, None when absent, or raise.

    ABSENT is `None` — the ordinary "this caller states no per-turn cap" — and
    the remaining episode budget then applies on its own.

    MALFORMED is everything else: `"8000"` out of an untyped YAML config,
    `8000.5`, `8000.0`, `True`, `0`, `-1`. Those used to be swallowed as "not
    a cap", which silently RAISED the request to the whole remaining ceiling —
    a caller asking for 8,000 tokens got 40,000 on a paid call, an order of
    magnitude the other way from what it typed. A malformed cap must never
    become a bigger budget, so it is a `TypeError` at the first request of the
    batch: loud, immediate, and impossible to mistake for a policy result.

    EVERY float is malformed, integral or not (Codex T48 §9, Q7). `8000.0` used
    to be accepted as "a cap a JSON round-trip produced", which is a guess
    about the caller's intent made at the one place where guessing costs money;
    a client that means 8,000 tokens can type an int. `True` is malformed too,
    even though `bool` is an `int` subclass — `max_tokens=True` is a bug
    wearing the number 1.

    The exact answers, pinned by `test_episode_contract`:

        None      -> absent (the remaining ceiling applies)
        8000      -> 8000
        0, -5     -> TypeError
        True      -> TypeError
        8000.0    -> TypeError            (a float is not an int)
        "8000"    -> TypeError
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError(f"{field} must be a positive integer, not the boolean {value!r}")
    if isinstance(value, float):
        raise TypeError(f"{field} must be a positive integer, not the float {value!r}")
    if not isinstance(value, int):
        raise TypeError(f"{field} must be a positive integer, not {type(value).__name__} {value!r}")
    if value <= 0:
        raise TypeError(f"{field} must be a positive integer, not {value!r}")
    return value


#: EVERY spelling of a per-turn completion cap that any client in the library
#: reads. Two were enough until the responses client turned out to prefer a
#: THIRD: `normalize_sampling_args` maps `max_tokens`/`max_completion_tokens`
#: onto `max_output_tokens` only `if "max_output_tokens" not in sampling_args`,
#: so a caller who states that one keeps it — unvalidated and, worse,
#: unclamped by the episode ceiling. All three are read, validated and
#: replaced by the single `TOKEN_CAP_FIELD` the environment emits.
#:
#: BOUND BY THE DIGEST (`episode_contract()["budgets"]["token_cap_spellings"]`)
#: and pinned per spelling by `test_episode_contract`. It was neither at first,
#: and that is a silent-regression trap rather than a cosmetic gap: dropping a
#: spelling from this tuple left the contract digest byte-identical and turned
#: `{"max_output_tokens": "8000"}` from a `TypeError` back into "no cap
#: stated" — the whole remaining ceiling, on a paid call, with nothing to
#: notice it. A cap field that is not in the tuple is not validated, so the
#: tuple is part of the contract.
TOKEN_CAP_SPELLINGS = ("max_tokens", "max_completion_tokens", "max_output_tokens")


def caller_token_caps(sampling_args) -> list:
    """Every per-turn cap the caller stated, validated, as a list of ints.

    EVERY spelling is read and EVERY one is validated, so one valid and one
    malformed field REJECTS the request rather than quietly using the valid
    one (Codex T48 §9): an operator who typed `max_completion_tokens="8000"`
    beside a good `max_tokens` asked for something we cannot honour, and
    honouring half of it is the silent-budget-inflation defect one field over.

    Called on every request, ceiling enabled or not — a malformed cap must
    never reach a provider, and with the ceiling disabled the environment adds
    no clamp of its own to catch it later.
    """
    args = sampling_args or {}
    caps = [_token_cap(field, args.get(field)) for field in TOKEN_CAP_SPELLINGS]
    return [c for c in caps if c is not None]


# --------------------------------------------------------------------------
# the budget-accounting vocabulary (Codex T47 §4, Q3)
#
# A CLOSED set of codes, not prose. `state["piv_budget_accounting_invalid"]`
# is one of these and nothing else, so a histogram over it has as many
# buckets as there are failure modes; the numbers go in
# `state["piv_budget_accounting_detail"]`, which nothing keys on. The first
# version put the prose in the flag itself and a measurement grouping by it
# got one bucket per rollout.
# --------------------------------------------------------------------------

BUDGET_USAGE_ABSENT = "usage_absent"                          # no usage object at all
BUDGET_USAGE_NOT_INTEGER = "usage_not_integer"                # completion_tokens is not a non-negative int
BUDGET_COMPLETION_EXCEEDS_CAP = "completion_exceeds_cap"      # the provider ignored the clamp
BUDGET_CUMULATIVE_DECREASED = "cumulative_decreased"          # the accumulator went backwards
BUDGET_USAGE_ZERO_ON_SPOKEN_TURN = "usage_zero_on_spoken_turn"  # 0 tokens for a turn that spoke
BUDGET_ACCOUNTING_CODES = (
    BUDGET_USAGE_ABSENT, BUDGET_USAGE_NOT_INTEGER, BUDGET_COMPLETION_EXCEEDS_CAP,
    BUDGET_CUMULATIVE_DECREASED, BUDGET_USAGE_ZERO_ON_SPOKEN_TURN,
)

# --------------------------------------------------------------------------
# SUSPICIOUS is not INVALID (Codex T48 §3, Q2)
#
# Every code above is a THEOREM about the provider's arithmetic: no usage
# object, a count that is not a non-negative integer, a count above the cap the
# request carried, an accumulator that went backwards, zero tokens for a turn
# that demonstrably spoke. None of them depends on a guess about tokenizers.
#
# The characters-per-token floor is not of that kind. It is an empirical
# heuristic over an unknown tokenizer, and Codex refused it as a hard validity
# gate: long whitespace, repeated symbols, non-Latin scripts and serialized
# tool arguments all tokenize at ratios a universal constant cannot bound, and
# a replay ARM changes the shape of the emitted text — so a heuristic
# invalidation can exclude one arm more often than another and bias the very
# comparison it is protecting. It therefore names a SEPARATE, softer outcome:
# `state["piv_budget_accounting_suspicious"]` and `piv/budget_accounting_
# suspicious`, which a measurement reports with and without rather than
# excluding silently. A row can be VALID and suspicious at once; the two keys
# are independent and neither reads the other.
# --------------------------------------------------------------------------

BUDGET_USAGE_IMPLAUSIBLE = "usage_implausible"                # far too few tokens for the text produced
BUDGET_SUSPICIOUS_CODES = (BUDGET_USAGE_IMPLAUSIBLE,)

#: The floor a provider's token count is judged against: fewer than one token
#: per this many characters of text is not under-counting, it is not counting.
#: Real tokenizers run about 3 (code, JSON) to 4 (prose) characters per token,
#: so 8 is a factor of two of slack in the provider's favour — the check fires
#: only on a claim at least twice as cheap as the cheapest plausible encoding.
#: Deliberately lenient: a false accusation would put an honest rollout in the
#: suspicious bucket, and a run of identical characters does compress unusually
#: well under BPE. The denominator counts visible content, reasoning content
#: AND the tool-call payload (`tool_call_chars`): a tool-only turn carrying a
#: 48,000-character `write_ledger` argument used to have a denominator of zero
#: and passed at one reported token (Codex T48 §3.1, Q3).
CHARS_PER_TOKEN_FLOOR = 8


def system_prompt(max_episode_output_tokens: int = MAX_EPISODE_OUTPUT_TOKENS) -> str:
    """The prompt for an episode served under THIS output ceiling.

    A function rather than a constant because the ceiling is not a constant:
    `load_environment(max_episode_output_tokens=…)` and
    `set_max_total_completion_tokens` both change it, and the measurement arms
    use the setter. A prompt built from `MAX_EPISODE_OUTPUT_TOKENS` would then
    tell an 8,000-token arm it had 40,000 — a disclosure that is false in
    exactly the runs the disclosure was added for. Every number here comes
    from the argument or from the turn constants, so nothing can be typed
    twice and drift.

    With the ceiling disabled (<= 0) there IS no token budget to disclose, so
    the ceiling sentences are dropped rather than stated as zero; the turn
    budget is unconditional.
    """
    # THE DELIVERY RULE, in the agent's words (Codex T48 §11, Q10). The old
    # wording — "submit by turn 24" — reads as a precondition for delivery,
    # and it is not one: every non-protocol ending scores the last committed
    # revision, so a model that wrote a good ledger and ran out of turns is
    # scored on it. A prompt that implies otherwise makes an agent spend its
    # last tokens on a ritual instead of on the books, and it describes a
    # different contract from the one the results table reports.
    finish = (f"Call submit by turn {MAX_TURNS - 1} to finish early. If the episode limit is "
              "reached first, the latest successfully written ledger is scored.")
    if max_episode_output_tokens > 0:
        budget = (
            f"You have {MAX_TURNS} turns. The episode has a total ceiling of "
            f"{max_episode_output_tokens:,} completion tokens, including hidden reasoning. You "
            "will not receive an exact remaining-token counter, so keep responses concise and use "
            "tools early. Tool calls emitted on the turn that exhausts this token ceiling are "
            f"executed; calls emitted on turn {MAX_TURNS} are not. {finish}"
        )
    else:
        budget = (
            f"You have {MAX_TURNS} turns. Keep responses concise and use tools early. Tool calls "
            f"emitted on turn {MAX_TURNS} are not executed. {finish}"
        )
    return f"""You are keeping the books for a small trading company.

You have a set of files to work from. Start with the manifest, then read what \
you need. Read `{LEDGER}` in one complete call before editing it — it \
returns the complete ledger exactly as the scorer sees it; line endings are \
normalized to LF. Preserve every existing transaction. Use sliced reads or \
grep only for the other files when you need them.

{LEDGER} is sent to you ONCE per revision: a second complete read of a \
revision you have already been given returns a short receipt instead of the \
file, so keep the content of your last complete read. A successful \
write_ledger makes a new revision, and the next complete read returns it.

When you have worked out what is wrong, write the corrected ledger back with \
write_ledger. Post what is genuinely missing; do not remove or rewrite entries \
that are already there, and do not invent accounts that are not in the chart.

You may call run_beancount at any time to check that the ledger still loads.

{budget}

The episode also ends after {MAX_CONSECUTIVE_NO_TOOL_TURNS} consecutive turns \
without a tool call — including an unbroken run of turns cut off at the \
completion cap. If a reply is cut off, make the next one shorter and call a \
tool.

When you are finished, call submit to end the episode: the ledger as last \
written is final. submit needs a ledger that was written and loaded — with \
nothing written, or with the last write refused, it is refused too and the \
episode carries on."""


#: The prompt at the DEFAULT ceiling: what the release serves and what a
#: reader should quote. An environment constructed with another ceiling
#: carries its own (`env.system_prompt`), and says so in its own digest.
SYSTEM_PROMPT = system_prompt()


# --------------------------------------------------------------------------
# tools
# --------------------------------------------------------------------------

def _clip_bytes(text: str, limit: int = MAX_TOOL_OUTPUT_BYTES) -> str:
    """`text` cut to at most `limit` UTF-8 bytes, with a public marker.

    A LINE cap is not a byte cap, and the agent writes the ledger: 119 lines
    of 400 bytes fits every line limit and returns more than a whole read
    (Codex T48 §7, Q9). Cut on the encoded bytes and decode with `ignore`, so
    a multibyte character straddling the limit is dropped rather than split
    into an invalid sequence the provider would have to repair.
    """
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    return raw[:limit].decode("utf-8", errors="ignore") + CLIP_MORE_BYTES.format(limit=limit)


def _clip(text: str, limit: int = MAX_TOOL_OUTPUT_LINES) -> str:
    """A bounded reply: at most `limit` lines AND MAX_TOOL_OUTPUT_BYTES bytes."""
    lines = text.splitlines()
    if len(lines) > limit:
        text = "\n".join(lines[:limit]) + CLIP_MORE_LINES.format(remaining=len(lines) - limit)
    return _clip_bytes(text)


def list_files(workspace: str = "") -> str:
    """List the files available to you, with their size in lines."""
    rows = []
    for name in PUBLIC_FILES:
        raw = _read_public(workspace, name)
        if raw is None:
            # A declared public file that is missing or not plain is a
            # world we did not construct — an evaluator failure, never a
            # silently narrower observation.
            raise RuntimeError(f"declared public file is not readable: {name}")
        rows.append(LIST_FILES_ROW.format(name=name, lines=len(logical_text(raw).splitlines())))
    return "\n".join(rows)


def ledger_envelope_breach(raw: bytes) -> str | None:
    """Why this ledger is outside the observation envelope, or None.

    ONE definition, consulted by all four doors — `_verify_public_world` and
    `load_environment` before the episode, `write_ledger` on the candidate and
    `_whole_ledger_reply` on the stored file — so "the world we serve", "the
    world we mount", "what the agent may write" and "what we will send back"
    cannot drift apart on the number that makes a single whole read safe.

    UTF-8 BYTES of the stored file and LOGICAL LINES of its logical text,
    never Python characters: 16,000 three-byte characters is a 48,000-byte
    file, and what the next request pays for is bytes.
    """
    if len(raw) > LEDGER_ENVELOPE_BYTES:
        return f"{len(raw)} bytes > LEDGER_ENVELOPE_BYTES {LEDGER_ENVELOPE_BYTES}"
    lines = len(logical_text(raw).splitlines())
    if lines > LEDGER_ENVELOPE_LINES:
        return f"{lines} lines > LEDGER_ENVELOPE_LINES {LEDGER_ENVELOPE_LINES}"
    return None


def _verify_public_world(workspace: str) -> None:
    """Every declared public file must exist as a plain readable file, and
    the ledger must fit the envelope a single whole read is sized for.

    An over-envelope ledger is a world we should not have built: the read
    tool would hand the whole thing back. Refusing here makes that an
    evaluator failure at workspace construction — never a rollout that
    silently observed a narrower or an unaffordable world.
    """
    for name in PUBLIC_FILES:
        raw = _read_public(workspace, name)
        if raw is None:
            raise RuntimeError(f"declared public file is not readable: {name}")
        if name == LEDGER:
            breach = ledger_envelope_breach(raw)
            if breach is not None:
                raise RuntimeError(f"the mounted ledger is outside the observation envelope: {breach}")


def _whole_ledger_reply(raw: bytes) -> str:
    """The ledger's complete text, or a bounded receipt, or a bounded refusal.

    THE FILE ITSELF, when this is the first complete read of this revision:
    byte-for-byte the text the scorer reads — no line numbers, no tail, no
    header, nothing the agent would have to strip before writing it back. The
    task is "replace the COMPLETE file and preserve every original entry", and
    a live rollout that rebuilt the ledger from 200-line slices dropped most
    of them (Codex T46 §4).

    A RECEIPT, when the same revision has already been sent (Codex T48 §7,
    Q9). The envelope bounds ONE observation; it does not bound repetition,
    and a single assistant turn may carry many `read_file(ledger)` calls. At
    48,000 bytes each, twenty of them in one call list put a megabyte into the
    next request for one turn's completion tokens — input the episode's output
    ceiling does not price. So the full read is IDEMPOTENT PER REVISION: the
    first complete read of a given logical text returns it, every later
    complete read of the same logical text returns `LEDGER_UNCHANGED_RECEIPT`
    with no ledger content at all, and an accepted `write_ledger` that changes
    the logical text makes the next complete read return the new content once.
    Within one turn's call list the rule is the same, because the framework
    runs a turn's calls in order through this door: content, then receipts.

    THE BOUND this buys, per episode, on COMPLETE READS:

        LEDGER_ENVELOPE_BYTES x (stored revisions + 1)

    — the mounted revision plus one per stored write, each sent at most once,
    and a stored write is itself bounded by the envelope and by one write per
    turn. It holds because the logical text can only change through
    `write_ledger`, and a read returns content only when the text differs from
    the one last sent.

    In practice it is far tighter than `MAX_TURNS + 1` envelopes, because the
    only way to earn another content-returning read is to EMIT another whole
    ledger — and emitting is priced: 48,000 characters is roughly 12K
    completion tokens, so the 40,000-token episode ceiling pays for about
    three of them. The output budget and the read rule close the loop
    together; before the rule, one completion token bought another 48 KB.

    STATED EXACTLY: this bounds the WHOLE-FILE channel, which is the one that
    carries 48 KB in a single call. `grep` and the sliced `read_file` can also
    show ledger lines and are bounded per call instead — MAX_GREP_HITS,
    MAX_TOOL_OUTPUT_LINES, MAX_READ_LINES — each costing a tool call out of
    `MAX_TURNS`. `state["piv_observation_bytes"]` measures the real total over
    every reply, so what an episode actually cost is a number rather than an
    argument.

    A REFUSAL, when the stored ledger is outside the envelope
    (`READ_OVER_ENVELOPE`). Unreachable in normal operation — the mounted
    world is verified at `_workspace` and `write_ledger` refuses anything
    larger — so this is defence in depth against state corruption, a
    migration or a future bypass restoring the amplification (Codex T48 §6,
    Q9). It is a BOUNDED PUBLIC message and never the content: making it an
    evaluator failure would hand the agent a quarantine button, and returning
    the content would defeat the envelope.

    Identity is the LOGICAL TEXT digest, not the revision counter: two writes
    that store the same text are one observation, and the agent is told the
    truth ("unchanged") rather than sent 48 KB it already has. The digest is
    the same `logical_text_digest` the write attestation already handed the
    agent, so the receipt names nothing the transcript does not already carry.
    """
    breach = ledger_envelope_breach(raw)
    if breach is not None:
        return READ_OVER_ENVELOPE
    text = logical_text(raw)
    state = _PIV_STATE.get()
    if state is None:
        # A direct call with no rollout context (a test, a probe, the
        # evaluator's own tooling): there is no episode to bound, and
        # inventing one would make the tool's answer depend on a global.
        return text
    digest = _domain_digest("logical_text_digest", text.encode("utf-8"))
    sent = state.get("piv_ledger_sent")
    if isinstance(sent, dict) and sent.get("digest") == digest:
        state["piv_ledger_receipts"] = state.get("piv_ledger_receipts", 0) + 1
        return LEDGER_UNCHANGED_RECEIPT.format(turn=sent.get("turn", 0),
                                               revision=sent.get("revision", 0))
    # The revision the content BEING SENT will carry. `piv_revision` advances
    # in `env_response`, after the whole turn's calls have run, so a call list
    # of `write_ledger -> read_file` reads a revision the counter has not
    # reached yet: naming `piv_revision` there would tell the agent it had
    # been sent revision 0 when it had just been sent revision 1. A stored
    # write leaves `piv_pending`, and that is exactly the +1.
    revision = int(state.get("piv_revision", 0)) + (1 if state.get("piv_pending") else 0)
    state["piv_ledger_sent"] = {"digest": digest, "turn": int(state.get("piv_turn", 0)),
                                "revision": revision}
    state["piv_complete_reads"] = state.get("piv_complete_reads", 0) + 1
    return text


def read_file(path: str, offset: int = 0, limit: int = MAX_READ_LINES,
              workspace: str = "") -> str:
    """Read a file. ledger.beancount returns the complete ledger exactly as the
    scorer sees it, with no line numbers; line endings are normalized to LF —
    once per revision: a second complete read of a revision you already have
    returns a short receipt instead of the file. The other files come in
    numbered slices of up to 200 lines (offset/limit).

    Args:
        path: File name, as shown by list_files.
        offset: First line to return, zero-based. Ignored for ledger.beancount.
        limit: How many lines to return. Ignored for ledger.beancount.
    """
    raw = _read_public(workspace, path)
    if raw is None:
        return READ_NO_SUCH_FILE.format(path=path)
    if path == LEDGER:
        return _whole_ledger_reply(raw)
    text = logical_text(raw)
    lines = text.splitlines()
    limit = max(1, min(limit, MAX_READ_LINES))
    # Clamped by a check, not by slice semantics: a negative offset must not
    # count from the end, and 10**40 must be "past the end", explicitly
    # (round-2 adversary: the body's safety rested on list slicing clamping).
    offset = min(max(offset, 0), len(lines))
    window = lines[offset:offset + limit]
    body = "\n".join(READ_SLICE_LINE.format(number=offset + i + 1, line=line)
                     for i, line in enumerate(window))
    tail = ""
    if offset + limit < len(lines):
        tail = READ_MORE_LINES.format(remaining=len(lines) - offset - limit)
    # Bytes, not only lines: MAX_READ_LINES lines of arbitrary width is not a
    # bounded reply. The LINE cap is deliberately not applied here — a slice
    # is allowed its full MAX_READ_LINES, which is more than `_clip` permits.
    return _clip_bytes(body) + tail


def _plain(st: os.stat_result) -> bool:
    """A regular file that is not a link of any kind: not a symlink, junction
    or other reparse point, and with exactly one hard link."""
    if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
        return False
    attrs = getattr(st, "st_file_attributes", 0)
    return not (attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _is_plain_file(path: Path) -> bool:
    try:
        return _plain(os.lstat(path))
    except OSError:
        return False


def _public_file(workspace: str, name: str) -> Path | None:
    """The public file `name` names, or None.

    The first version of the read tools took any path, and `Path(workspace)
    / "C:/abs"` is the absolute path unchanged: the task file with the answer
    key was one guessed path away. Resolving under the workspace closed that
    and was still the wrong shape — containment is broader than the
    observation contract. So: an exact manifest NAME, not a path (no
    separators, no `.`/`..`, no drive, no stream suffix, no case variant —
    none of those is in the manifest, and nothing is ever stat'ed for a name
    that is not); then the entry under the resolved workspace must be a plain
    regular file (`_plain`) that still resolves inside the workspace. The
    caller opens the returned path and re-checks the open handle.
    """
    if not isinstance(name, str) or name not in PUBLIC_FILES:
        return None
    root = Path(workspace).resolve()
    target = root / name
    if not _is_plain_file(target):
        return None
    try:
        if not target.resolve().is_relative_to(root):
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return target


def _same_object(before: os.stat_result, after: os.stat_result) -> bool:
    """Identity, not regularity.

    Regularity alone does not reveal a substitution: swap the directory
    entry for a symlink to an outside, ordinary, single-link file between
    the check and the open, and `fstat` sees a perfectly plain file. The
    volume and file index of the checked entry must be those of the opened
    handle; an unknown index (0) never matches.
    """
    return bool(before.st_ino) and (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)


def _swap_seam(target: Path) -> None:
    """Between the pre-open check and the open. A no-op; a test replaces
    the file here to prove that identity, not just type, is compared."""


def _read_public(workspace: str, name: str) -> bytes | None:
    """Bytes of a public file, or None. The one verified-handle door.

    Check the entry (`lstat`), open, then prove the handle IS that entry
    (`fstat`: plain, and the same volume + file index) before consuming a
    byte. Every read path — the tools, the scorer, the post-commit
    snapshot — comes through here.
    """
    target = _public_file(workspace, name)
    if target is None:
        return None
    try:
        before = os.lstat(target)
        if not _plain(before):
            return None
        _swap_seam(target)
        with open(target, "rb") as handle:
            after = os.fstat(handle.fileno())
            if not _plain(after) or not _same_object(before, after):
                return None
            return handle.read()
    except OSError:
        return None


def grep(pattern: str, path: str = "", workspace: str = "") -> str:
    """Search the files for a literal piece of text (not a regular expression).

    Args:
        pattern: The exact text to look for, case-sensitive.
        path: Limit the search to one file. Omit to search all of them.
    """
    if not isinstance(pattern, str) or not pattern or len(pattern) > MAX_GREP_PATTERN:
        return GREP_BAD_PATTERN.format(max_pattern=MAX_GREP_PATTERN)
    # Literal search, by contract. A backtracking regex engine was a
    # liveness hole the agent could trigger today: it controls the ledger,
    # a valid Beancount comment can hold thousands of `a`s within the size
    # limits, and a short `(a+)+$` then holds the worker before any reward
    # is computed — the pattern cap bounds the pattern, not the matching
    # time, and CPython's `re` cannot be interrupted while it holds the GIL.
    # `in` is linear, in-process, no shell. Only the declared public set is
    # searched — never a directory tree — and matches and output are capped.
    if path:
        if _public_file(workspace, path) is None:
            return READ_NO_SUCH_FILE.format(path=path)
        names = [path]
    else:
        names = list(PUBLIC_FILES)
    hits = []
    for name in names:
        raw = _read_public(workspace, name)
        if raw is None:
            continue
        for number, line in enumerate(logical_text(raw).splitlines(), 1):
            if pattern in line:
                hits.append(GREP_HIT.format(name=name, number=number, line=line.strip()))
                if len(hits) >= MAX_GREP_HITS:
                    return _clip("\n".join(hits)) + GREP_STOPPED.format(limit=MAX_GREP_HITS)
    return _clip("\n".join(hits)) if hits else GREP_NO_MATCHES


def _public_report(outcome) -> str:
    """What the model is told about a parse: the boundary's public outcome,
    never a parser's exception text or an evaluator's diagnostics."""
    if isinstance(outcome, ProtocolFailure):
        return REPORT_REJECTED.format(reason=outcome.reason, detail=outcome.detail)
    if isinstance(outcome, Accepted):
        if outcome.domain_valid:
            return REPORT_LOADS_CLEANLY.format(events=len(outcome.candidate.events))
        lines = [REPORT_FINDING.format(code=f.code, message=f.message)
                 for f in outcome.domain_findings[:MAX_REPORTED_FINDINGS]]
        return REPORT_FINDINGS_HEADER + "\n".join(lines)
    # An evaluator failure inside the boundary is ours: raise, so the tool
    # phase records the marker and the rollout is quarantined.
    raise RuntimeError(f"parse boundary failed: {outcome}")


def run_beancount(workspace: str = "") -> str:
    """Read the current ledger through the boundary and report."""
    raw = _read_public(workspace, LEDGER)
    if raw is None:
        raise RuntimeError("ledger is not a readable public file")
    return _public_report(parse_once(logical_text(raw)))


def write_ledger(content: str, workspace: str = "") -> str:
    """Write the full corrected ledger and check that it loads.

    Args:
        content: The complete ledger file. This replaces the existing one.
    """
    # The workspace is frozen the moment `submit` is answered — in the SAME
    # turn as well, because the framework runs a turn's calls in order and
    # `submit` first, `write_ledger` second is a representable turn. "The
    # ledger as last written is final" has to mean the ledger at the instant
    # submit ran, not whatever a later call in the same list left behind.
    #
    # Through the tool door this branch is now unreachable: `call_tool` refuses
    # every call after an accepted submit with TURN_AFTER_SUBMIT before any
    # body runs (Codex T47 §5). It stays as the direct-call safety net — the
    # tool is importable, and "the ledger cannot move after submit" should not
    # depend on which door was used.
    state = _PIV_STATE.get()
    if episode_phase(state) is EpisodePhase.TERMINAL:
        return WRITE_AFTER_SUBMIT
    if not isinstance(content, str):
        return WRITE_NOT_TEXT  # bound, but not text: the agent's, counted
    try:
        raw_in = content.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        # A lone surrogate from a JSON escape is not text and cannot be stored
        # under the strict profile. A public rejection, counted: no receipt,
        # no revision, nothing written.
        return WRITE_NOT_TEXT
    if ledger_envelope_breach(raw_in) is not None:
        # Never stored, and judged in UTF-8 BYTES (and logical lines) —
        # `raw_in`, not `len(content)`: a Python character count would let
        # 48,000 three-byte characters through as a 144,000-byte file (Codex
        # T48 §6, Q9). The cap IS the observation envelope, the very predicate
        # `_verify_public_world`, `load_environment` and the read door use, so
        # the read-side refusal cannot fire on anything the agent was allowed
        # to write. `read_file` returns the ledger whole on every later turn,
        # so an oversized write would buy unbounded INPUT for one completion
        # token a turn — a cost the episode's output ceiling does not price.
        #
        # ATOMIC: this returns before `mkstemp`, so a refused write leaves the
        # bytes on disk, `piv_pending`, `piv_phase` and `piv_candidate_digest`
        # exactly as they were — the previous candidate and its digest are
        # still what `submit` would deliver. A public refusal, counted as the
        # agent's outcome, with nothing written.
        return WRITE_TOO_LARGE
    root = Path(workspace).resolve()
    target = root / MUTABLE_PUBLIC_FILE
    # The compatibility file is REPLACED, never opened for writing in place:
    # an exclusive temporary regular file in the resolved workspace, then an
    # atomic rename over the target. The existing target must be a plain
    # regular file or absent — a symlink, junction, reparse point or second
    # hard link is a workspace we did not create, an evaluator failure, and
    # nothing outside the workspace is ever opened for writing.
    if os.path.lexists(target) and not _is_plain_file(target):
        raise RuntimeError("ledger target is not a plain regular file")
    # Bytes exactly as submitted: no newline translation, no locale. The
    # first version used `write_text`, which on Windows stored CRLF for LF,
    # so the bytes on disk and the text the scorer read were different
    # objects and one digest was attesting to the other.
    fd, tmp = tempfile.mkstemp(prefix=".ledger-", suffix=".tmp", dir=root)  # O_EXCL
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw_in)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    raw = _read_public(workspace, MUTABLE_PUBLIC_FILE)  # one snapshot; both file digests derive from it
    if raw is None:
        raise RuntimeError("ledger is not a readable public file after commit")
    digests = digests_of(raw, submitted=content)
    attestation = {
        "schema": WRITE_ATTESTATION_SCHEMA,
        "profiles": DIGEST_PROFILES,
        "committed": True,
        **digests,
    }
    # Parse ONCE, from the same snapshot the digests describe. The outcome
    # is handed to `env_response` as pending state, keyed by those digests;
    # it installs the commitment only after recomputing the digests itself.
    outcome = parse_once(logical_text(raw))
    if state is not None:                        # bound at the top of the tool
        state["piv_pending"] = {"digests": digests, "outcome": outcome}
        # The phase transition, made here rather than after the turn: `submit`
        # may run later in this SAME call list, and it has to see the
        # candidate this call just stored. `piv_committed` is installed by
        # `env_response` once it has re-derived the digests, which is after
        # the whole turn's calls have run — too late to answer submit with.
        # The two agree by construction: both are keyed to `digests` here.
        state["piv_phase"] = (EpisodePhase.CANDIDATE if isinstance(outcome, Accepted)
                              else EpisodePhase.REJECTED)
        state["piv_candidate_digest"] = digests["logical_text_digest"]
    # First line is the machine-readable attestation, validated by exact
    # schema in `env_response`; the rest is the report the model reads.
    return json.dumps(attestation, sort_keys=True) + "\n" + _public_report(outcome)


def submit(workspace: str = "") -> str:
    """End the episode. The ledger as last written is final.

    Call this once you have written a ledger with write_ledger and it loaded.
    Nothing is read or changed afterwards; the ledger on disk at this moment
    is what is delivered, and its content hash is fixed here.

    If nothing has been stored, or if the last write_ledger was refused by the
    ledger protocol, submit is refused and the episode carries on.
    """
    # The only agent-driven termination (PLAN §6), and the one transition into
    # TERMINAL. It has no score path of its own: it stops the loop, and the
    # ordinary scorer runs over the last committed revision.
    #
    # It used to accept unconditionally, so a model that had stored nothing —
    # or whose one attempt the boundary had refused — ended its own episode on
    # the untouched original. That is a termination the agent almost certainly
    # did not mean, and it is indistinguishable in the metrics from a
    # deliberate empty delivery. Refusing it costs a turn and says why.
    state = _PIV_STATE.get()
    phase = episode_phase(state)
    if phase is EpisodePhase.TERMINAL:
        # Idempotent: the same receipt, naming the same bound content hash.
        # The binding below happens once, so a repeated call can neither
        # rebind a later candidate nor name a different one.
        #
        # Unreachable through the tool door since Codex T47 §5: a second
        # `submit` in the same call list is refused by `call_tool` with
        # TURN_AFTER_SUBMIT, because a receipt would assert an acceptance that
        # did not happen. Kept for the direct-call door, where idempotence is
        # the property that matters.
        return submit_receipt(state.get("piv_submitted_digest"))
    if phase in (EpisodePhase.NO_CANDIDATE, EpisodePhase.REJECTED):
        if state is not None:
            state["piv_submit_refused"] = state.get("piv_submit_refused", 0) + 1
        return (SUBMIT_NOTHING_STORED if phase is EpisodePhase.NO_CANDIDATE
                else SUBMIT_LAST_CANDIDATE_REFUSED)
    # ACTIVE_CANDIDATE. One assignment binds the phase and the content hash of
    # the candidate as it stands now; from here the workspace is frozen, so
    # the hash cannot go stale and no later candidate can be scored.
    digest = state.get("piv_candidate_digest")
    state["piv_phase"] = EpisodePhase.TERMINAL
    state["piv_submitted_digest"] = digest
    return submit_receipt(digest)


def submit_receipt(digest) -> str:
    """The accepted-submit reply: the fixed sentence plus the bound hash.

    The digest is of the agent's OWN candidate text — the same
    `logical_text_digest` the commit attestation already handed back — so
    naming it leaks nothing and makes the binding checkable from the
    transcript alone.
    """
    return SUBMIT_DELIVERING.format(accepted=SUBMIT_ACCEPTED, digest=digest_short(digest))


#: The tool surface, in the order the environment adds it, and the argument
#: every tool takes and no agent ever sees. Declared once so the environment's
#: constructor and `public_tool_defs()` (which the episode contract digest
#: binds) cannot advertise different surfaces.
PUBLIC_TOOLS = (list_files, read_file, grep, run_beancount, write_ledger, submit)
HIDDEN_TOOL_ARGS = ("workspace",)

#: The tools that SEND the agent world content, and so spend the observation
#: budget: everything that is not the one write door or the one terminal door.
#: Derived rather than typed, so a seventh tool is an observing tool by
#: default — the fail-closed direction for a cost bound.
OBSERVING_TOOLS = tuple(t.__name__ for t in PUBLIC_TOOLS
                        if t.__name__ not in (WRITE_TOOL, TERMINAL_TOOL))


WRITE_ATTESTATION_SCHEMA = "piv.write/2"
PARTITION_SCHEMA = "piv.partition/1"

# Three digests, three domains. `piv.write/1` carried one `algorithm` label,
# "sha256/utf-8/universal-newlines", which was true of the logical text and
# false of the other two: the submitted string is hashed as strict UTF-8 with
# no normalisation, and stored bytes have no text semantics at all. Each
# field names its own profile, and each preimage is prefixed with its domain
# so equal bytes in different representations never share an identity — the
# LF-only case, where submitted, stored and logical are byte-identical, would
# otherwise produce three equal digests and call them three facts.
DIGEST_PROFILES = {
    "submitted_text_digest": "sha256:utf8-strict:no-normalisation:v1",
    "stored_bytes_digest": "sha256:raw-bytes:v1",
    "logical_text_digest": "sha256:utf8-strict:universal-newlines:v1",
}
_DIGEST_DOMAINS = {
    "submitted_text_digest": b"piv:submitted-text:v1\0",
    "stored_bytes_digest": b"piv:stored-bytes:v1\0",
    "logical_text_digest": b"piv:logical-text:v1\0",
}


def logical_text(raw: bytes) -> str:
    """The one definition of the text the scorer reads.

    Strict UTF-8 (invalid bytes raise — we wrote the bytes, so that is our
    failure, never the agent's), CRLF and CR mapped to LF, nothing else: no
    BOM stripping (a BOM is content and the parser gate sees it), no locale,
    no dependence on Python's UTF-8 mode. `Path.read_text()` with ambient
    defaults was the protocol before; a protocol should not be whatever the
    platform does.
    """
    return raw.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n")


def _domain_digest(field: str, payload: bytes) -> str:
    """Full SHA-256 over a domain-prefixed preimage, 64 lowercase hex.

    Never truncated in trusted state. Twelve characters was the first
    version: 48 bits, birthday collisions around 2^24 artifacts, and every
    statement of "bound by SHA-256" false at the one place the comparison
    happened. Abbreviate only for display, with `digest_short`, and never
    compare, key, or authorise on the short form.
    """
    return hashlib.sha256(_DIGEST_DOMAINS[field] + payload).hexdigest()


def digests_of(raw: bytes, submitted: str | None = None) -> dict:
    """Both file digests from ONE bytes snapshot; the submitted digest if given.

    Reading the file twice — once as bytes, once as text — left a race
    between the two observations. One `read_bytes`; the logical text is
    derived from it.
    """
    digests = {
        "stored_bytes_digest": _domain_digest("stored_bytes_digest", raw),
        "logical_text_digest": _domain_digest(
            "logical_text_digest", logical_text(raw).encode("utf-8")),
    }
    if submitted is not None:
        digests["submitted_text_digest"] = _domain_digest(
            "submitted_text_digest", submitted.encode("utf-8", errors="strict"))
    return digests


def digest_short(full: str) -> str:
    return full[:12]


_HEX64 = frozenset("0123456789abcdef")


def is_full_digest(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX64


def parse_attestation(content) -> dict | None:
    """The attestation, or None if the reply is not a valid one.

    Strict: exact schema string, the exact per-field digest profiles,
    `committed is True`, all three digests present as full 64-hex SHA-256
    strings. A reply that merely starts with a familiar word is not an
    attestation — text-prefix matching was itself a lenient parser.
    """
    if not isinstance(content, str):
        return None
    first = content.split("\n", 1)[0]
    try:
        data = json.loads(first)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("schema") != WRITE_ATTESTATION_SCHEMA:
        return None
    if data.get("committed") is not True:
        return None
    if data.get("profiles") != DIGEST_PROFILES:
        return None
    for key in ("submitted_text_digest", "stored_bytes_digest", "logical_text_digest"):
        if not is_full_digest(data.get(key)):
            return None
    return data


# --------------------------------------------------------------------------
# the episode contract's own identity (Codex T47 §2, Q5)
# --------------------------------------------------------------------------

#: The observation and termination contract's version. Bumped whenever
#: `episode_contract_digest()` changes — the prompt, a tool description or
#: schema, an observation mode, a phase transition, a stop name or priority, a
#: budget, or a public nudge/refusal message. NOT `GENERATOR_VERSION`: the
#: generated accounting world is untouched by any of those, and conflating the
#: two would invalidate every world for a wording change.
#: 2: every model-facing reply template hoisted into the view (Codex T48 §4),
#: the idempotent whole-read rule and its receipt (§7), the read-side envelope
#: refusal (§6), and the submit-is-not-required delivery sentence in the
#: prompt (§11). 1: the original observation-and-termination contract.
EPISODE_CONTRACT_VERSION = 2
#: /2: the view gained the hoisted reply templates, the repeated-read and
#: observation-budget semantics and the envelope units — a reader of /1 would
#: find keys it does not know, so the SHAPE has a new name as well as the
#: content having a new version.
EPISODE_CONTRACT_SCHEMA = "piv.episode-contract/2"

#: The phase machine as DATA, so the digest binds the transitions rather than a
#: prose table that can drift from the code. `(from, event, to, reply)`; the
#: reply names the module constant the agent is answered with, or the receipt.
#: `BeancountLedgerEnv`'s docstring is the same table in prose and
#: `test_episode_contract` walks the machine through the real tools.
#: THREE write events, not two. A write that is never STORED — content that is
#: not text, or over `MAX_WRITE_BYTES` — answers with its own refusal string
#: and leaves the phase exactly where it was; only a write that reached disk
#: moves the phase, to CANDIDATE or REJECTED according to what the protocol
#: boundary made of it. The first version of this table collapsed the two and
#: claimed an unstored write reached ACTIVE_REJECTED, which is false for every
#: starting phase — `test_episode_contract` now walks every row through the
#: real tools rather than only checking that the phase names exist.
PHASE_TRANSITIONS = (
    ("ACTIVE_NO_CANDIDATE", "write_ledger:stored,boundary accepted", "ACTIVE_CANDIDATE", "write attestation"),
    ("ACTIVE_NO_CANDIDATE", "write_ledger:stored,boundary refused", "ACTIVE_REJECTED", "write attestation"),
    ("ACTIVE_NO_CANDIDATE", "write_ledger:not stored", "ACTIVE_NO_CANDIDATE", "WRITE_NOT_TEXT | WRITE_TOO_LARGE"),
    ("ACTIVE_NO_CANDIDATE", "submit", "ACTIVE_NO_CANDIDATE", "SUBMIT_NOTHING_STORED"),
    ("ACTIVE_CANDIDATE", "write_ledger:stored,boundary accepted", "ACTIVE_CANDIDATE", "write attestation"),
    ("ACTIVE_CANDIDATE", "write_ledger:stored,boundary refused", "ACTIVE_REJECTED", "write attestation"),
    ("ACTIVE_CANDIDATE", "write_ledger:not stored", "ACTIVE_CANDIDATE", "WRITE_NOT_TEXT | WRITE_TOO_LARGE"),
    ("ACTIVE_CANDIDATE", "submit", "TERMINAL", "SUBMIT_ACCEPTED + bound logical digest"),
    ("ACTIVE_REJECTED", "write_ledger:stored,boundary accepted", "ACTIVE_CANDIDATE", "write attestation"),
    ("ACTIVE_REJECTED", "write_ledger:stored,boundary refused", "ACTIVE_REJECTED", "write attestation"),
    ("ACTIVE_REJECTED", "write_ledger:not stored", "ACTIVE_REJECTED", "WRITE_NOT_TEXT | WRITE_TOO_LARGE"),
    ("ACTIVE_REJECTED", "submit", "ACTIVE_REJECTED", "SUBMIT_LAST_CANDIDATE_REFUSED"),
    ("TERMINAL", "any call, later turn", "TERMINAL", "TURN_AFTER_SUBMIT"),
    ("TERMINAL", "any call, same list after submit", "TERMINAL", "TURN_AFTER_SUBMIT"),
)

#: Every stop condition the rollout can end under, highest priority first, with
#: the priority `@vf.stop` recorded — ours and the framework's alike.
#: `test_episode_contract` asserts this equals the live `_stop_conditions`
#: NAMES **and** their `stop_priority` attributes, so the digest binds what
#: actually decides an ending rather than a wish: an edited priority that
#: happens to preserve the order is still a contract change and still fails.
STOP_CONDITION_PRIORITY = (
    ("has_error", 100),
    ("piv_protocol_terminated", 55),
    ("piv_submitted", 50),
    ("piv_output_budget_exhausted", 48),
    ("piv_truncation_limit", 45),
    ("piv_no_tool_call_limit", 40),
    ("piv_turn_cap_submit_unexecuted", 36),
    ("piv_turn_cap_no_submit", 35),
    ("has_final_env_response", 0),
    ("max_turns_reached", 0),
    ("prompt_too_long", 0),
)


def public_tool_defs() -> list:
    """The tool definitions AS THE FRAMEWORK GENERATES THEM, without an
    environment instance.

    `StatefulToolEnv.add_tool` builds each `vf.Tool` from
    `convert_func_to_tool_def(filter_signature(tool, args_to_skip))` and then
    prunes the hidden argument out of `properties`/`required`/`$defs`. Both
    halves are the framework's own code, called here rather than reimplemented,
    and `test_episode_contract` asserts the result equals a live environment's
    `tool_defs` — so the digest binds the schema the model is actually shown,
    including anything a `verifiers` upgrade changes about it.

    Memoised, and returned as fresh dicts. Building six schemas costs ~10 ms
    (griffe parses the docstrings, pydantic emits the JSON schema) and this is
    called once per rollout and once per `episode_contract()`. The tool
    functions are module-level and cannot change within a process; a caller
    that mutates a returned `parameters` dict must not be able to poison the
    cache, hence the copy.
    """
    global _PUBLIC_TOOL_DEFS
    if _PUBLIC_TOOL_DEFS is not None:
        return [t.model_copy(deep=True) for t in _PUBLIC_TOOL_DEFS]
    from verifiers.legacy.envs.stateful_tool_env import filter_signature
    from verifiers.legacy.utils.tool_utils import convert_func_to_tool_def

    defs = []
    for tool in PUBLIC_TOOLS:
        tool_def = convert_func_to_tool_def(filter_signature(tool, list(HIDDEN_TOOL_ARGS)))
        params = tool_def.parameters
        for arg in HIDDEN_TOOL_ARGS:
            properties = params.get("properties")
            if isinstance(properties, dict) and arg in properties:
                arg_properties = properties.pop(arg)
                if isinstance(arg_properties, dict) and "$ref" in arg_properties:
                    ref_type = str(arg_properties["$ref"]).split("/")[-1]
                    if isinstance(params.get("$defs"), dict) and ref_type in params["$defs"]:
                        params["$defs"].pop(ref_type)
            required = params.get("required")
            if isinstance(required, list) and arg in required:
                required.remove(arg)
        if "$defs" in params and not params["$defs"]:
            params.pop("$defs")
        defs.append(tool_def)
    _PUBLIC_TOOL_DEFS = defs
    return [t.model_copy(deep=True) for t in defs]


_PUBLIC_TOOL_DEFS: list | None = None


def episode_contract(max_episode_output_tokens: int = MAX_EPISODE_OUTPUT_TOKENS) -> dict:
    """The complete observation-and-termination contract, as plain data.

    Everything here is PUBLIC — it is either shown to the model or derivable
    from what is shown — so the view carries no world, no task and no secret,
    and two evaluators running the same code produce the same bytes.

    What it binds, and why each is here (Codex T47 §2): the exact system
    prompt; the tool names, descriptions and JSON argument schemas the
    framework generates; how each public file is observed, including the
    whole-ledger logical-text rule and the envelope that makes it affordable;
    the phase machine and accepted-submit semantics; the stop conditions with
    their priorities; the turn, no-tool, truncation and output budgets with the
    pending-call rule; and the public nudge and refusal messages HELD AS NAMED
    CONSTANTS, because a changed refusal changes the next model request.

    EVERY model-facing reply is in here now (Codex T48 §4). The earlier
    version bound the fixed refusals and nudges only and said so: the strings
    `read_file`, `grep` and `_public_report` built — "no such file", the
    numbered-slice format, the continuation tail, the hit line, the
    stopped-at-N tail, the parse headings — were outside it and relied on
    someone remembering to bump `EPISODE_CONTRACT_VERSION`. They are module
    constants now, the tool bodies format them, and the whole set is in
    `messages` below, so a changed reply moves the digest by construction.
    `test_episode_contract` walks the source of every model-facing function to
    prove no literal escaped the hoist.

    The OUTPUT CEILING is an argument, not the module constant: a caller can
    serve any ceiling (`load_environment(max_episode_output_tokens=…)`,
    `set_max_total_completion_tokens`) and the prompt discloses whichever one
    is in force, so two environments differing only in ceiling are two
    conditions and must not share a digest.
    """
    return {
        "schema": EPISODE_CONTRACT_SCHEMA,
        "version": EPISODE_CONTRACT_VERSION,
        "system_prompt": system_prompt(max_episode_output_tokens),
        "tools": [
            {"name": t.name, "description": t.description or "",
             "parameters": t.parameters, "strict": bool(t.strict)}
            for t in public_tool_defs()
        ],
        "observation": {
            "public_files": list(PUBLIC_FILES),
            "mutable_public_file": MUTABLE_PUBLIC_FILE,
            "whole_read_file": LEDGER,
            "whole_read_semantics": (
                "the complete file as the scorer sees it: logical text (strict UTF-8, CRLF and CR "
                "mapped to LF), no line numbers, no continuation tail, no marker; offset and limit "
                "are ignored"
            ),
            "repeated_whole_read_semantics": (
                "the complete file is sent once per revision: the first complete read of a given "
                "logical text returns it, a later complete read of the SAME logical text returns "
                "LEDGER_UNCHANGED_RECEIPT and no content, and an accepted write_ledger that changes "
                "the logical text makes the next complete read return the new content once — within "
                "one turn's call list as well, in call order"
            ),
            "whole_read_bound": (
                "COMPLETE READS deliver at most LEDGER_ENVELOPE_BYTES x (stored revisions + 1) "
                "bytes of ledger content in an episode; every OTHER reply is bounded at "
                "max_tool_output_bytes, and the episode as a whole at "
                "max_episode_observation_bytes. state['piv_complete_reads'] counts the "
                "content-returning complete reads and state['piv_observation_bytes'] measures every "
                "reply the environment returns"
            ),
            "observation_budget_semantics": (
                "each reply is counted in UTF-8 bytes as it is produced; once the episode total "
                "reaches max_episode_observation_bytes every observing tool "
                "(list_files, read_file, grep, run_beancount) is answered OBSERVATION_BUDGET_SPENT "
                "and reads nothing, while write_ledger and submit continue to work"
            ),
            "observing_tools": list(OBSERVING_TOOLS),
            "max_tool_output_bytes": MAX_TOOL_OUTPUT_BYTES,
            "max_episode_observation_bytes": MAX_EPISODE_OBSERVATION_BYTES,
            "over_envelope_read_semantics": (
                "a stored ledger outside the envelope is refused with READ_OVER_ENVELOPE and its "
                "content is never returned; unreachable through write_ledger, which refuses the "
                "same predicate in UTF-8 bytes and logical lines"
            ),
            "sliced_read_semantics": (
                "numbered slices of at most MAX_READ_LINES logical lines; offset clamped into "
                "range; a continuation tail when lines remain"
            ),
            "max_read_lines": MAX_READ_LINES,
            "max_tool_output_lines": MAX_TOOL_OUTPUT_LINES,
            "max_reported_findings": MAX_REPORTED_FINDINGS,
            "grep_semantics": "literal, case-sensitive substring search over the declared public files",
            "max_grep_pattern": MAX_GREP_PATTERN,
            "max_grep_hits": MAX_GREP_HITS,
            "ledger_envelope_bytes": LEDGER_ENVELOPE_BYTES,
            "ledger_envelope_lines": LEDGER_ENVELOPE_LINES,
            "envelope_units": "UTF-8 bytes of the stored file and logical lines of its logical text",
            "max_write_bytes": MAX_WRITE_BYTES,
            "write_attestation_schema": WRITE_ATTESTATION_SCHEMA,
            "digest_profiles": dict(DIGEST_PROFILES),
        },
        "episode": {
            "phases": [p.value for p in EpisodePhase],
            "active_phases": sorted(p.value for p in ACTIVE_PHASES),
            "write_tool": WRITE_TOOL,
            "terminal_tool": TERMINAL_TOOL,
            "transitions": [list(row) for row in PHASE_TRANSITIONS],
            "accepted_submit": (
                "submit is accepted only from ACTIVE_CANDIDATE; it binds the stored candidate's "
                "logical_text_digest once, freezes the workspace, and every later call — in a "
                "later turn OR later in the same call list — is answered TURN_AFTER_SUBMIT with "
                "no tool body executed"
            ),
            "stop_conditions": [list(row) for row in STOP_CONDITION_PRIORITY],
        },
        "budgets": {
            "max_turns": MAX_TURNS,
            "last_executable_turn": MAX_TURNS - 1,
            "max_consecutive_no_tool_turns": MAX_CONSECUTIVE_NO_TOOL_TURNS,
            "max_consecutive_truncated_turns": MAX_CONSECUTIVE_TRUNCATED_TURNS,
            "max_episode_output_tokens": int(max_episode_output_tokens),
            "pending_call_at_budget": PENDING_CALL_AT_BUDGET,
            "token_cap_field": TOKEN_CAP_FIELD,
            "token_cap_spellings": list(TOKEN_CAP_SPELLINGS),
        },
        "messages": {name: value for name, value in model_facing_messages()},
    }


def model_facing_messages() -> tuple:
    """Every model-facing string this module can emit, as (name, value).

    ONE list, consulted by `episode_contract()` and by the test that walks the
    tool sources: a template that is not here is a reply the digest cannot
    see, and a template here that no function formats is a claim the contract
    makes and the code does not keep. Both halves are checked.
    """
    return (
        ("PUBLIC_TOOL_ERROR", PUBLIC_TOOL_ERROR),
        ("TURN_MULTI_WRITE", TURN_MULTI_WRITE),
        ("TURN_DUPLICATE_ID", TURN_DUPLICATE_ID),
        ("TURN_NO_TOOL", TURN_NO_TOOL),
        ("TURN_TRUNCATED_NO_TOOL", TURN_TRUNCATED_NO_TOOL),
        ("TURN_AFTER_SUBMIT", TURN_AFTER_SUBMIT),
        ("SUBMIT_ACCEPTED", SUBMIT_ACCEPTED),
        ("SUBMIT_DELIVERING", SUBMIT_DELIVERING),
        ("SUBMIT_NOTHING_STORED", SUBMIT_NOTHING_STORED),
        ("SUBMIT_LAST_CANDIDATE_REFUSED", SUBMIT_LAST_CANDIDATE_REFUSED),
        ("WRITE_AFTER_SUBMIT", WRITE_AFTER_SUBMIT),
        ("WRITE_NOT_TEXT", WRITE_NOT_TEXT),
        ("WRITE_TOO_LARGE", WRITE_TOO_LARGE),
        ("LIST_FILES_ROW", LIST_FILES_ROW),
        ("READ_NO_SUCH_FILE", READ_NO_SUCH_FILE),
        ("READ_SLICE_LINE", READ_SLICE_LINE),
        ("READ_MORE_LINES", READ_MORE_LINES),
        ("READ_OVER_ENVELOPE", READ_OVER_ENVELOPE),
        ("LEDGER_UNCHANGED_RECEIPT", LEDGER_UNCHANGED_RECEIPT),
        ("CLIP_MORE_LINES", CLIP_MORE_LINES),
        ("CLIP_MORE_BYTES", CLIP_MORE_BYTES),
        ("OBSERVATION_BUDGET_SPENT", OBSERVATION_BUDGET_SPENT),
        ("GREP_BAD_PATTERN", GREP_BAD_PATTERN),
        ("GREP_HIT", GREP_HIT),
        ("GREP_STOPPED", GREP_STOPPED),
        ("GREP_NO_MATCHES", GREP_NO_MATCHES),
        ("REPORT_REJECTED", REPORT_REJECTED),
        ("REPORT_LOADS_CLEANLY", REPORT_LOADS_CLEANLY),
        ("REPORT_FINDINGS_HEADER", REPORT_FINDINGS_HEADER),
        ("REPORT_FINDING", REPORT_FINDING),
    )


def _response_says_something(response) -> bool:
    """Did this turn produce anything a provider could have billed for?

    Content, reasoning content, or a tool call. A genuinely empty turn (some
    providers return one) may honestly cost 0 completion tokens; a turn that
    spoke may not.
    """
    message = getattr(response, "message", None)
    if message is None:
        return False
    for field in ("content", "reasoning_content"):
        value = getattr(message, field, None)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and value:
            return True
    return bool(getattr(message, "tool_calls", None))


def tool_call_chars(message) -> int:
    """Characters of the canonical serialization of one assistant message's
    tool calls: every call's NAME, ID and ARGUMENTS, in wire order.

    The largest completion payload this task can carry is a `write_ledger`
    argument, up to `MAX_WRITE_BYTES`. The plausibility floor used to ignore
    it entirely, so a tool-only turn carrying 48,000 characters of argument
    had a denominator of zero and passed at one reported completion token
    (Codex T48 §3.1, Q3) — "omitting the body is not fail-closed".

    CONSERVATIVE BY CONSTRUCTION. Only the three fields are counted: no JSON
    wrapper, no separators, no quoting or escaping, no `type`/`function`
    envelope. Every provider adds some of those and no two add the same ones,
    so counting a wrapper we did not see would be inventing characters the
    provider may not have billed for — and this number is the DENOMINATOR of
    an accusation. What is returned is therefore a strict lower bound on any
    real wire encoding of the same calls, which is the direction a floor has
    to err in. A non-string `arguments` (some clients hand back a parsed dict)
    is measured through canonical JSON, so the count does not depend on which
    client produced the message.

    Characters, not bytes: `CHARS_PER_TOKEN_FLOOR` is a per-character floor
    and `_response_chars` counts characters, so both sides of the comparison
    use one unit.

    TWO INDEPENDENT IMPLEMENTATIONS, DELIBERATELY. The measurement side
    (`tests/measure_budget.py`) keeps its own counter rather than importing
    this one, and that is the design, not drift: it reads ARCHIVED rows, where
    a tool call may arrive in shapes this function never sees live — a nested
    `{"function": {"name": …, "arguments": …}}`, or the whole call as a JSON
    string — and it handles them. This one returns 0 for those, which keeps it
    a conservative lower bound rather than making it wrong. Two implementations
    of a fail-closed floor that disagree only in the lenient direction are a
    cheap differential; one shared helper would have one blind spot in both.
    Exported so the instrument CAN cross-check against it.
    """
    total = 0
    for call in getattr(message, "tool_calls", None) or []:
        for field in ("name", "id", "arguments"):
            value = getattr(call, field, None)
            if isinstance(value, str):
                total += len(value)
            elif value is not None:
                total += len(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":"), default=str))
    return total


def _response_chars(response) -> int:
    """Characters of visible content, reasoning content and the tool-call
    payload in this turn.

    The denominator of the plausibility check below. All three are billed, and
    the tool-call payload is the biggest of them in this task, so leaving it
    out was not leniency but a hole: `usage_implausible` could not see the one
    turn where under-reporting pays.
    """
    message = getattr(response, "message", None)
    if message is None:
        return 0
    total = 0
    for field in ("content", "reasoning_content"):
        value = getattr(message, field, None)
        if isinstance(value, str):
            total += len(value)
        elif isinstance(value, list):
            for part in value:
                text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                if isinstance(text, str):
                    total += len(text)
    return total + tool_call_chars(message)


def _restated(prompt, previous: str, current: str):
    """A dataset row's prompt with the leading system message restated.

    Only a system message whose content is EXACTLY the prompt being replaced
    is touched: an operator who supplied their own system prompt keeps it, and
    a row with no system message is left alone rather than gaining one.
    """
    if not isinstance(prompt, list) or not prompt:
        return prompt
    head = prompt[0]
    if not isinstance(head, dict) or head.get("role") != "system" or head.get("content") != previous:
        return prompt
    return [{**head, "content": current}, *prompt[1:]]


def episode_contract_digest(max_episode_output_tokens: int = MAX_EPISODE_OUTPUT_TOKENS) -> str:
    """SHA-256 over the canonical JSON of `episode_contract()`, 64 hex.

    One value that answers "which observation and termination rules did this
    rollout run under?". `public_task_id` binds the public FILES and the
    task-specific prompt, `task_contract_digest` binds the scorer's normative
    view — neither notices that the system prompt, the whole-read rule or the
    output ceiling changed, so the same task id could be served under
    materially different rules and compared as if it were one condition. It is
    recorded on every rollout (`state["piv_episode_contract_digest"]`, for the
    ceiling THAT rollout ran under), in a batch's metadata, and on every
    measurement row.

    DELIBERATELY NOT in the release manifest's `versions()` (Codex T48 §6,
    Q8). It was, and that binding could not hold: `load_environment` admits
    BEFORE it constructs the environment and then accepts
    `max_episode_output_tokens`, so a world admitted under the default digest
    could be served under another one with no second check — the manifest
    attesting a contract nobody preflighted. Golden bookkeeping validity does
    not depend on whether the model got 8K or 40K completion tokens;
    experiment comparability does. So the manifest identifies the WORLD and
    this identifies the EPISODE, per rollout, where the ceiling is known.
    """
    payload = json.dumps(episode_contract(max_episode_output_tokens), sort_keys=True,
                         ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(b"piv:episode-contract:v1\0" + payload).hexdigest()


# --------------------------------------------------------------------------
# environment
# --------------------------------------------------------------------------

class BeancountLedgerEnv(vf.StatefulToolEnv):
    """Gives each rollout its own scratch copy of the world.

    THE EPISODE STATE MACHINE (PLAN §6, Codex T44 §9)
    ------------------------------------------------
    One value, `state["piv_phase"]`, an `EpisodePhase`. Two tools move it and
    nothing else does; every other handler reads it. Three of the four phases
    are ACTIVE (`ACTIVE_PHASES`); the fourth is terminal and irreversible.

        phase                 write_ledger stores        submit
                              & the boundary...
        --------------------- -------------------------- ----------------------
        ACTIVE_NO_CANDIDATE   accepts -> ACTIVE_CANDIDATE  refused, stays here
        (start)               refuses -> ACTIVE_REJECTED   (SUBMIT_NOTHING_STORED)

        ACTIVE_CANDIDATE      accepts -> ACTIVE_CANDIDATE  ACCEPTED -> TERMINAL
                              refuses -> ACTIVE_REJECTED   (binds the hash once)

        ACTIVE_REJECTED       accepts -> ACTIVE_CANDIDATE  refused, stays here
                              refuses -> ACTIVE_REJECTED   (SUBMIT_LAST_CANDIDATE_REFUSED)

        TERMINAL              refused, nothing stored      refused, nothing bound
        (frozen)              (TURN_AFTER_SUBMIT)          (TURN_AFTER_SUBMIT)

    So: ACTIVE, zero or more candidates written or replaced, one accepted
    submit, TERMINAL. A refused write (not text, over the cap) stores nothing
    and leaves the phase alone. A refused TURN (two writes, duplicate ids)
    executes nothing and leaves the phase alone.

    TERMINAL is terminal at the instant submit is accepted, not merely from
    the next turn: `call_tool` refuses every later call occurrence — the rest
    of submit's own call list included — before any tool body runs, so a
    `submit -> read_file` list reads nothing (Codex T47 §5). The direct-call
    refusals `WRITE_AFTER_SUBMIT` and the idempotent receipt survive as safety
    nets on the importable functions.

    Termination, and what each ending is worth:

        piv_submitted           the agent ended it            last committed revision
        piv_output_budget_...   the output ceiling is spent   last committed revision
        piv_truncation_limit    K truncated turns in a row    last committed revision
        piv_no_tool_call_limit  K no-tool turns in a row      last committed revision
        piv_turn_cap_no_submit  max_turns, never submitted    last committed revision
        piv_protocol_terminated duplicate tool call ids       0.0, whatever is on disk

    The non-protocol endings are one rule: THE LAST COMMITTED REVISION IS
    ALWAYS SCORED. Only the status differs, and it differs so a policy that
    never submits can be seen doing it. Zeroing a legitimately committed
    ledger because the agent forgot the last call would punish the books for
    a protocol slip — the opposite of what the scorer is for, and it would
    hide the slip inside an ordinary bad score instead of naming it.
    """

    def __init__(self, partial_batches: bool = False, contract=None, public_files=None, **kwargs):
        # `stop_errors` defaults to [] in the framework, which means an
        # exception inside a tool is formatted with `str(e)` back to the model
        # and the rollout simply continues — no error state, the final reward
        # computed on whatever is on disk. An internal tool bug would be
        # invisible. Our marker is the stop error, and the formatter never
        # leaks exception text to the model.
        if contract is None:
            raise InitializationFailure(["the environment requires a LoadedEnvironment contract"])
        if not isinstance(public_files, dict) or set(public_files) != set(PUBLIC_FILES) \
                or not all(isinstance(v, bytes) for v in public_files.values()):
            raise InitializationFailure(["the environment requires the projected public files, exactly the manifest"])
        kwargs.setdefault("stop_errors", [PIVEvaluatorFailed])
        kwargs.setdefault("error_formatter", lambda e: PUBLIC_TOOL_ERROR)
        super().__init__(tools=[], **kwargs)
        self.partial_batches = partial_batches
        self.contract = contract
        self.public_files = dict(public_files)
        for tool in PUBLIC_TOOLS:
            self.add_tool(tool, args_to_skip=list(HIDDEN_TOOL_ARGS))
        # The episode contract's two named doors, checked here rather than
        # only in a test: `env_response` recognises a commit by WRITE_TOOL and
        # the rollout ends on TERMINAL_TOOL, so a tool renamed out from under
        # either name would silently stop ending episodes or stop advancing
        # revisions. Refuse to build such an environment at all.
        missing = [n for n in (WRITE_TOOL, TERMINAL_TOOL) if n not in self.tool_map]
        if missing:
            raise InitializationFailure([f"the tool surface is missing {missing}"])

    async def call_tool(self, tool_name, tool_args, tool_call_id, **kwargs):
        """Owned tools: reclassify before the framework can mislabel, and
        refuse everything after an accepted `submit` — including the SUFFIX of
        the very call list submit rode in on.

        Two outcomes the framework would otherwise collapse:

          - the agent's misuse (wrong or missing arguments): a bounded public
            message back to the model, no error state, the rollout continues
            — a counted outcome;
          - our bug (anything else raised inside the tool): the marker is
            recorded on the rollout and RAISED, so the framework stops the
            rollout and re-raises `ToolCallError from marker`. The marker is
            in the chain; the partition sees it.

        TERMINALITY AT THE PRECISE INSTANT (Codex T47 §5, Q8). `env_response`
        refuses a whole post-submit TURN, and `write_ledger` checked the phase
        itself — but `read_file`, `grep`, `list_files` and `run_beancount` did
        not, so a same-turn list `submit -> read_file` executed the read after
        the accepted submit, against a contract that says "Nothing is read or
        changed afterwards". The base loop runs a turn's calls in order, and
        this is the per-call door it runs them through: from the instant the
        phase is TERMINAL, every LATER call occurrence gets one bounded
        `TURN_AFTER_SUBMIT` and no tool body runs at all. Ids are unique by
        pre-turn validation, so that is one reply per call, which is what the
        provider requires.

        A repeated `submit` in the suffix is refused with the same message
        rather than answered with the idempotent receipt: the receipt asserts
        an accepted termination, and the second call did not perform one. The
        receipt branch inside `submit` stays as the direct-call safety net (it
        is unreachable through this door).

        Pre-turn validation — duplicate ids, two writes — still happens in
        `env_response` before anything here runs, so a rejected turn executes
        nothing at all.

        ONE EXCEPTION to the wording above, stated rather than glossed: the
        base loop parses `tool_call.arguments` as JSON BEFORE calling this, so
        a post-submit call whose arguments are malformed is answered by
        `error_formatter` with `PUBLIC_TOOL_ERROR` and never reaches this
        door. No tool body runs either way — the safety property holds — but
        such a call is not counted in `piv_calls_refused_after_submit` and its
        reply is the malformed-arguments one. Closing that would mean
        reimplementing the base loop, which costs more than it buys.
        """
        from verifiers.legacy.types import ToolMessage

        state = _PIV_STATE.get()

        def answer(text: str):
            """One bounded reply, counted against the observation budget."""
            return self._count_reply(state, ToolMessage(role="tool", content=text,
                                                        tool_call_id=tool_call_id))

        if episode_phase(state) is EpisodePhase.TERMINAL:
            state["piv_calls_refused_after_submit"] = state.get("piv_calls_refused_after_submit", 0) + 1
            return answer(TURN_AFTER_SUBMIT)
        tool = self.tool_map.get(tool_name)
        if tool is None:
            return answer(PUBLIC_TOOL_ERROR)
        # THE AGGREGATE OBSERVATION BUDGET (Codex T48 §7, Q9). Asked here,
        # per call, against the running total — not once a turn — because a
        # single call list may hold twenty reads. Only the OBSERVING tools are
        # refused: `write_ledger` and `submit` must keep working, or an agent
        # that read too much could no longer deliver the books it has, which
        # would turn a cost bound into a reward penalty.
        if tool_name in OBSERVING_TOOLS and state is not None \
                and state.get("piv_observation_bytes", 0) >= MAX_EPISODE_OBSERVATION_BYTES:
            state["piv_observation_refused"] = state.get("piv_observation_refused", 0) + 1
            return answer(OBSERVATION_BUDGET_SPENT)

        # Phase 1 — bind the public arguments, and nothing else. This is the
        # only place where a failure is the agent's: the catch surrounds an
        # explicit bind that completes before the body runs. Classifying a
        # `TypeError` raised from inside the body as "argument misuse" would
        # recreate the invisible-tool-bug path for one common exception class.
        try:
            bound = inspect.signature(tool).bind(**tool_args)
        except TypeError:
            return answer(PUBLIC_TOOL_ERROR)
        # Types, too. The annotations are the public contract; `bind` checks
        # names and arity only, so `read_file(limit=1.5)` or `offset=null`
        # reached the body, raised there, and was recorded as OUR failure —
        # a quarantine button the adversary pass pressed at will. A value of
        # the wrong type is the agent's misuse, counted, never ours.
        if not _arguments_well_typed(tool, bound.arguments):
            return answer(PUBLIC_TOOL_ERROR)

        # Phase 2 — invoke. Every exception here is ours, whatever its type.
        try:
            return self._count_reply(
                state, await super().call_tool(tool_name, tool_args, tool_call_id, **kwargs))
        except PIVEvaluatorFailed:
            raise
        except Exception as exc:
            if state is None:
                # Out-of-band invocation with no rollout context: still never
                # the agent's outcome and never raw text. A marker with no
                # rollout id is in `stop_errors`, so the framework stops and
                # wraps it; the top-level code quarantines on its own.
                raise PIVEvaluatorFailed(f"tool:{tool_name}", "?", 0, exc)
            raise record_evaluator_failure(state, f"tool:{tool_name}", exc)

    def set_max_total_completion_tokens(self, max_total_completion_tokens: int) -> None:
        """Change the output ceiling — and RESTATE the prompt that discloses it.

        The prompt now names the ceiling (Codex T47 §6), and the ceiling is not
        a constant: `load_environment(max_episode_output_tokens=…)` sets it
        through this door and `tests/measure_budget.py` calls this door
        directly for each arm. Leaving the prompt alone would tell an
        8,000-token arm it had 40,000 — a false disclosure in exactly the runs
        the disclosure exists for.

        `Environment.__init__` PREPENDS the system message to every dataset
        row, so reassigning `self.system_prompt` alone changes nothing that
        reaches a model; the rows themselves are restated. The environment's
        contract digest is recomputed here too, so a rollout records the
        contract it actually ran under rather than the default one.
        """
        super().set_max_total_completion_tokens(max_total_completion_tokens)
        prompt = system_prompt(max_total_completion_tokens)
        self._episode_contract_digest = episode_contract_digest(max_total_completion_tokens)
        previous, self.system_prompt = self.system_prompt, prompt
        if previous != prompt:
            for name in ("dataset", "eval_dataset"):
                data = getattr(self, name, None)
                if data is None:
                    continue
                setattr(self, name,
                        data.map(lambda row: {"prompt": _restated(row["prompt"], previous, prompt)}))
        # FAIL CLOSED on the restatement, every time — including when the
        # prompt did not change. `_restated` deliberately touches only a
        # leading system message whose content is exactly the prompt it is
        # replacing, so an environment built with `system_prompt=None`, or one
        # whose rows carry someone else's system message, silently keeps rows
        # that do NOT state the budget the contract digest then attests. That
        # is the disclosure defect again, one layer down: an agent told
        # nothing, and a digest saying it was told.
        stale = self._rows_missing_prompt(prompt)
        if stale:
            raise InitializationFailure([
                f"the served dataset does not carry the disclosed system prompt in {len(stale)} row(s): "
                "the episode contract digest attests a prompt the model would never be sent"])

    def _rows_missing_prompt(self, prompt: str) -> list:
        """Dataset rows whose leading system message is not `prompt`."""
        bad = []
        for name in ("dataset", "eval_dataset"):
            data = getattr(self, name, None)
            if data is None:
                continue
            for row in data:
                messages = row.get("prompt") if isinstance(row, dict) else None
                head = messages[0] if isinstance(messages, list) and messages else None
                if not isinstance(head, dict) or head.get("role") != "system" \
                        or head.get("content") != prompt:
                    bad.append(name)
        return bad

    async def setup_state(self, state):
        """Stamp the episode contract on the rollout before its first turn.

        The digest answers "under which observation and termination rules did
        this rollout run?" and a measurement row that cannot answer it is not
        a comparable condition (Codex T47 §2). Set here rather than only in
        `_workspace` because a rollout that never calls a tool never builds a
        workspace and would otherwise carry no contract identity at all.
        """
        state = await super().setup_state(state) or state
        self._stamp_identity(state)
        return state

    def _stamp_identity(self, state) -> None:
        """The identity and the observation counters every rollout carries.

        `setup_state` normally does this; `_workspace` repeats the call for a
        state dict built by hand (a test, a direct `env_response`), guarded so
        neither recomputes what the other set.

        `piv_library_versions` is here rather than in the contract digest on
        purpose (Codex T48 §8): the model-facing tool schemas are GENERATED by
        `openai-agents`/`griffelib`/`pydantic`, so a dependency bump can move
        the digest without a line of ours changing. Binding the versions INTO
        the digest would instead move the digest on every bump whether or not
        the schema changed, which is the wrong loudness. So the versions ride
        every row as provenance, `pyproject.toml` pins them exactly, and a
        test fails when the installed set drifts from the pins — a bump is
        loud in one place and invisible in none.
        """
        if "piv_episode_contract_digest" not in state:
            state["piv_episode_contract_version"] = EPISODE_CONTRACT_VERSION
            state["piv_episode_contract_digest"] = self.episode_contract_digest()
        state.setdefault("piv_library_versions", library_versions())
        state.setdefault("piv_turn", 0)
        state.setdefault("piv_complete_reads", 0)
        state.setdefault("piv_observation_bytes", 0)

    def episode_contract_digest(self) -> str:
        """THIS environment's contract digest — its own ceiling, not the
        module default. Computed once per ceiling change and cached, because
        it is asked for on every rollout."""
        digest = getattr(self, "_episode_contract_digest", None)
        if digest is None:
            digest = self._episode_contract_digest = episode_contract_digest(
                self.max_total_completion_tokens)
        return digest

    def _workspace(self, state) -> str:
        # `setup_state` normally stamps the identity; a test (or any direct
        # `env_response` call) that builds its own state dict never goes
        # through it, and the digest, the library versions and the observation
        # counters must be on every rollout that touched a tool.
        self._stamp_identity(state)
        workspace = state.get("workspace")
        if not workspace:
            workspace = tempfile.mkdtemp(prefix="beancount_env_")
            try:
                # Seeded from the graph's projection, never from a directory:
                # the bytes the agent reads are the bytes the contract was
                # derived from, by construction.
                for name, data in self.public_files.items():
                    (Path(workspace) / name).write_bytes(data)
                _verify_public_world(workspace)
            except Exception as exc:  # a world we could not construct is ours, not the agent's
                raise record_evaluator_failure(state, "world", exc)
            state["workspace"] = workspace
            # ATTEMPT identity, minted here and nowhere else. A workspace path
            # is an adequate correlation key but not an identity: paths get
            # reused, canonicalised, and outlive rollouts. The UUID is what
            # failure records and diagnostics are keyed by.
            #
            # PER ATTEMPT, not per rollout (Codex T48 §10). The framework
            # builds a FRESH state dict for each attempt of a rollout — a
            # retry does not resume the old one — so `workspace` is absent
            # again and a new id is minted here. The measurement client
            # receives the same dict (`get_response(..., state=state)`) and
            # can therefore bind every provider request it makes to the
            # attempt that made it, instead of inferring an attempt boundary
            # from the shape of the prompt. That heuristic stays as an alarm;
            # this is the identity. Nothing model-facing ever carries it.
            state["piv_rollout_id"] = uuid.uuid4().hex
            state["piv_revision"] = 0
            state["piv_phase"] = EpisodePhase.NO_CANDIDATE
        return workspace

    def update_tool_args(self, tool_name, tool_args, messages, state, **kwargs) -> dict:
        tool_args["workspace"] = self._workspace(state)
        return tool_args

    async def get_model_response(self, state, prompt, client=None, model=None,
                                 tool_defs=None, sampling_args=None):
        """Ask for at most what is LEFT of the episode's output ceiling.

        `MultiTurnEnv` enforces `max_total_completion_tokens` only as a stop
        condition, which is checked after a turn has already been generated:
        an arm with a 16K per-turn cap can finish 16K past a 40K ceiling and
        an 8K arm 8K past it, so two arms nominally given "the same budget"
        are measured at different totals — the one thing the M2 comparison
        cannot afford (Codex T46 §6). Clamping the REQUEST makes the ceiling
        exact: each turn asks for `min(per-turn cap, ceiling - used)`, so the
        provider itself cannot return more than the remainder, and every arm
        stops at exactly the ceiling.

        The per-turn cap the caller set is never RAISED — only lowered — so a
        measurement arm keeps its own shape until the remainder is the
        smaller number. The clamp is written into a COPY: `sampling_args` is
        the caller's dict (`state["sampling_args"]` when the caller passed
        none), shared across every turn and every rollout of the batch, and
        mutating it would ratchet the cap down for all of them.

        THE TWO SPELLINGS ARE ONE FIELD ON THE WIRE (Codex T47 §4, Q1). The
        first version clamped whichever key it FOUND —
        `max_completion_tokens` if present, else `max_tokens` — and a caller
        passing both left the other untouched. Measured in the legacy client:
        `OpenAIChatCompletionsClient.get_native_response` normalises with

            if "max_tokens" in sampling_args:
                sampling_args["max_completion_tokens"] = sampling_args.pop("max_tokens")

        so `max_tokens` OVERWRITES `max_completion_tokens` and exactly one
        field, `max_completion_tokens`, reaches the provider. With both
        present the old code therefore clamped the value the client then threw
        away and shipped the UNCLAMPED one — the clamp was not weakened, it
        was defeated. So WHEN THE CEILING IS ON every spelling in
        `TOKEN_CAP_SPELLINGS` is removed before the base call and exactly one
        field is emitted: `TOKEN_CAP_FIELD` (`max_tokens`), the one every
        client in the library understands and the one the chat client renames
        on its way out. With the ceiling OFF nothing is normalised — there is
        no clamp to protect — and the caller's args go through untouched;
        only the validation below still runs.

        A MALFORMED CAP IS NOT AN ABSENT CAP (Codex T48 §9, Q7). `None` is
        absent and the remainder applies; a positive non-boolean int is a cap;
        `0`, a negative, a bool, ANY float and any string raise before a
        provider is called. Both spellings are validated even when only one is
        used, so `{"max_tokens": 8000, "max_completion_tokens": "x"}` is
        rejected rather than silently honoured at 8,000 — a caller who typed
        something we cannot honour did not ask for the half we understood. The
        validation also runs with the ceiling DISABLED, where the environment
        adds no clamp of its own that would catch it later.

        `state["piv_request_max_tokens"]` records the environment's INTENDED
        cap per request. That is our arithmetic; the wire assertion in
        `test_episode_contract` is the independent second witness that the
        native request body carries the same number.
        """
        ceiling = self.max_total_completion_tokens
        request_max = None
        before = (self.get_state_usage(state) or {}).get("output_tokens", 0)
        # Validated on EVERY request, ceiling or no ceiling: a malformed cap
        # must never reach a provider, and with the ceiling off nothing below
        # would look at it.
        stated = caller_token_caps(sampling_args or state.get("sampling_args") or {})
        if ceiling > 0:
            # The base resolves `sampling_args or state["sampling_args"] or {}`;
            # resolving it the same way here keeps one meaning of "the caller's
            # sampling args" on both sides of the super() call. Written into a
            # COPY: the caller's dict is shared across every turn and every
            # rollout of the batch, and mutating it would ratchet the cap down
            # for all of them.
            resolved = dict(sampling_args or state.get("sampling_args") or {})
            for field in TOKEN_CAP_SPELLINGS:
                resolved.pop(field, None)
            remaining = int(ceiling - before)
            request_max = min(stated + [remaining]) if stated else remaining
            # Never 0 or negative: a provider reads those as "no limit" or an
            # error, and the stop below is what ends an exhausted episode.
            request_max = max(1, request_max)
            resolved[TOKEN_CAP_FIELD] = request_max
            state.setdefault("piv_request_max_tokens", []).append(request_max)
            sampling_args = resolved
        try:
            response = await super().get_model_response(state, prompt, client=client, model=model,
                                                        tool_defs=tool_defs, sampling_args=sampling_args)
        except ValueError as exc:
            # The framework's OWN accounting refused this response before the
            # guard below could see it: `usage_utils.usage_tokens` raises on a
            # negative `prompt_tokens`/`completion_tokens`. That is a plain
            # `ValueError`, not a `vf.Error`, so the rollout loop does not
            # catch it and it escapes `rollout()` — one malformed usage object
            # takes the whole BATCH down. Recorded and re-raised as the
            # framework's own `ModelError`, which the loop does catch and
            # `ERROR_CONSEQUENCES` already quarantines as "model client, not
            # the policy's answer": the rollout is excluded rather than
            # crashed, and `piv_budget_accounting_invalid` says why.
            self._flag_budget_accounting(state, BUDGET_USAGE_NOT_INTEGER,
                                         f"the framework's usage accounting refused this response: {exc}")
            raise vf.ModelError("provider usage could not be accounted") from exc
        self._check_budget_accounting(state, response, request_max, before)
        return response

    @staticmethod
    def _flag_budget_accounting(state, code: str, detail: str) -> None:
        """Record ONE closed-vocabulary code and its prose, first violation wins.

        The code is what a measurement groups by; the detail carries the
        numbers and nothing keys on it. Sticky, because the earliest violation
        explains the ones after it.
        """
        if state.get("piv_budget_accounting_invalid"):
            return
        state["piv_budget_accounting_invalid"] = code
        state["piv_budget_accounting_detail"] = detail

    @staticmethod
    def _flag_budget_suspicious(state, code: str, detail: str) -> None:
        """The SOFT channel (Codex T48 §3, Q2): a heuristic anomaly, recorded
        under its own key so it never decides validity.

        Same shape as the hard one — a code from `BUDGET_SUSPICIOUS_CODES`, its
        prose in a separate key, first one wins — and deliberately independent
        of it: a rollout can be VALID and suspicious, INVALID and suspicious,
        or either alone, and a measurement reports the table with and without
        the suspicious rows rather than excluding them silently.
        """
        if state.get("piv_budget_accounting_suspicious"):
            return
        state["piv_budget_accounting_suspicious"] = code
        state["piv_budget_accounting_suspicious_detail"] = detail

    def _check_budget_accounting(self, state, response, request_max, before) -> None:
        """Fail closed on provider usage that cannot support a budget claim.

        The ceiling is metered from `response.usage.completion_tokens`. FIVE
        ways that meter can be untrustworthy as a matter of arithmetic, each
        recorded as ONE code from `BUDGET_ACCOUNTING_CODES` with the numbers
        in a separate detail key (Codex T47 §4, Q3):

          usage_absent
            No usage object. The tracker adds nothing, so "output tokens
            spent" reads 0 for the whole rollout and the ceiling never bites.
            The PER-TURN cap still bounds every turn — the request carried it,
            whatever the provider reported — so the episode is still bounded
            by `max_turns x cap`; what is NOT true of such a rollout is that
            it was measured at exactly the ceiling, and no equal-budget claim
            may include it. The scripted clients that drive most of the
            battery report no usage and are flagged on purpose.
          usage_not_integer
            `completion_tokens` is not a non-negative integer.
          usage_zero_on_spoken_turn
            0 tokens for a turn that produced content, reasoning or a tool
            call — absent usage wearing a number: 0 keeps the tracker at 0 and
            passes every other check here.
          completion_exceeds_cap
            More tokens than the cap this very request carried: the provider
            ignored the clamp, so the ceiling did not hold.
          cumulative_decreased
            The accumulator went backwards.

        AND ONE SUSPICION, which is NOT one of them (Codex T48 §3, Q2):

          usage_implausible
            Fewer than one token per `CHARS_PER_TOKEN_FLOOR` characters of
            content, reasoning and tool-call payload. A provider that
            under-reports by a large factor (the measured attack: one token a
            turn for thousands of characters) never trips the zero check and
            never exhausts the ceiling either — but the ratio itself is an
            empirical heuristic over an unknown tokenizer, and whitespace,
            repeated symbols, non-Latin text and serialized tool arguments all
            tokenize outside what one universal constant can bound. Worse, a
            replay ARM changes the shape of the emitted text, so a heuristic
            invalidation would exclude one arm more often than another and
            bias the comparison it exists to protect. It is therefore recorded
            in `state["piv_budget_accounting_suspicious"]` (prose in
            `…_suspicious_detail`, metric `piv/budget_accounting_suspicious`)
            and leaves validity alone; a measurement reports its table with
            and without the suspicious rows.

        WHAT THIS CAN AND CANNOT SEE. Two of the five cannot arise through the
        framework as it stands, and saying so is the point of listing them:
        `usage_utils.usage_tokens` raises on a NEGATIVE token count before
        this runs, and `StateUsageTracker` only ever increments, so a decrease
        cannot come from it. The negative case is converted in
        `get_model_response` (the raise is a plain `ValueError` that would
        otherwise take the batch down) and both are witnessed against this
        guard directly. They stay because this is the layer that must hold
        when the layer beneath it changes.

        None of this is an evaluator failure and none of it changes the
        reward: the agent did nothing wrong in any of the six cases. The
        consequence is a sticky code in
        `state["piv_budget_accounting_invalid"]`, its prose in
        `state["piv_budget_accounting_detail"]`, and the zero-weight metric
        `piv/budget_accounting_invalid`, which the measurement excludes from
        every budget analysis. First violation wins — and because the hard
        flag short-circuits this whole method, a rollout already diagnosed
        invalid is not re-examined for suspicion on later turns.
        """
        if state.get("piv_budget_accounting_invalid"):
            return                                   # sticky: the first code is the diagnosis
        usage = getattr(response, "usage", None)
        if usage is None:
            return self._flag_budget_accounting(
                state, BUDGET_USAGE_ABSENT, "no usage object: completion tokens cannot be metered")
        completion = getattr(usage, "completion_tokens", None)
        if not isinstance(completion, int) or isinstance(completion, bool) or completion < 0:
            return self._flag_budget_accounting(
                state, BUDGET_USAGE_NOT_INTEGER,
                f"completion_tokens is not a non-negative integer: {completion!r}")
        chars = _response_chars(response)
        # SUSPICIOUS, not invalid, and asked FIRST so it is recorded even on a
        # turn that also fails a hard check (the two keys are independent).
        if completion * CHARS_PER_TOKEN_FLOOR < chars:
            ratio = chars / completion if completion else float("inf")
            self._flag_budget_suspicious(
                state, BUDGET_USAGE_IMPLAUSIBLE,
                f"completion_tokens {completion} for {chars} characters of content, reasoning and "
                f"tool-call payload is {ratio:.1f} characters per token, below the floor of "
                f"{CHARS_PER_TOKEN_FLOOR}")
        if completion == 0 and _response_says_something(response):
            return self._flag_budget_accounting(
                state, BUDGET_USAGE_ZERO_ON_SPOKEN_TURN,
                f"completion_tokens is 0 for a turn carrying {chars} characters or a tool call")
        if request_max is not None and completion > request_max:
            return self._flag_budget_accounting(
                state, BUDGET_COMPLETION_EXCEEDS_CAP,
                f"completion_tokens {completion} exceeds the request cap {request_max}")
        after = (self.get_state_usage(state) or {}).get("output_tokens", before)
        if after < before:
            return self._flag_budget_accounting(
                state, BUDGET_CUMULATIVE_DECREASED,
                f"cumulative output decreased: {after} < {before}")

    @vf.stop(priority=48)
    async def piv_output_budget_exhausted(self, state) -> bool:
        """The episode spent its whole output ceiling.

        Named here rather than left to the framework's
        `max_total_completion_tokens_reached` (priority 0) so a batch can
        tell "ran out of tokens" apart from "ran out of turns" — the two
        endings the M2 arms are meant to distinguish, and the reason the
        ceiling is enforced on the request at all.

        Priority 48 places it below `piv_submitted` (50) and above
        `piv_truncation_limit` (45) and the rest: a run of truncated turns
        that ends at the ceiling was ended by the ceiling — the cap is the
        cause, the truncation the symptom.

        PRIORITY ALONE IS NOT ENOUGH to let a `submit` on the exhausting turn
        win, and this is where the ceiling differs from the turn cap. The
        framework checks stop conditions at the TOP of an iteration and runs
        a turn's tool calls at the top of the NEXT one, so the calls that
        rode the exhausting turn have not executed yet when this is asked:
        the phase is still ACTIVE_CANDIDATE and `piv_submitted` cannot be
        true. At `max_turns` the honest answer is that the call never ran
        (`piv_turn_cap_submit_unexecuted`) — running it would exceed the
        budget the contract states. Here it would not: EXECUTING A PENDING
        TOOL CALL SPENDS NO OUTPUT TOKENS, and this budget is denominated in
        output tokens. So a turn that carries tool calls is deferred exactly
        once and the loop runs them — every call, not only a submit: a write
        the model paid for with its last tokens is committed and scored like
        any other. An accepted `submit` then sets `final_env_response` and
        the next check names `piv_submitted`; anything else is sealed by
        `env_response` (`_seal_if_budget_spent`) so the model is NOT asked
        again, and the next check names this ending. Calling a delivering
        turn "out of tokens" would understate every arm's submit rate for a
        policy that did what the contract asks.

        The seal is what keeps the accounting exact: without it a deferred
        turn whose submit was refused (or that only wrote) would leave
        `final_env_response` unset, the loop would ask the model again, and
        the episode would end a token past the ceiling — the very overshoot
        this stop exists to remove. A turn without calls is not deferred:
        there is nothing to run, and the nudge it would earn is a request
        the budget no longer covers.

        A terminal protocol violation on the exhausting turn stays
        `piv_protocol_terminated`: that ending carries the protocol score,
        not the last committed revision's, and its name must say so.

        An ordinary counted outcome, scored like every other non-protocol
        ending: THE LAST COMMITTED REVISION IS SCORED.
        """
        if not self._output_budget_spent(state):
            return False
        if state.get("piv_protocol_failure"):
            return False
        if not state.get("piv_output_budget_deferred") and _calls_in_last_turn(state):
            state["piv_output_budget_deferred"] = True
            return False
        state["piv_output_budget_exhausted"] = True
        return True

    def _output_budget_spent(self, state) -> bool:
        """The one predicate behind the stop and the seal: ceiling enabled and
        the episode's output tokens at or past it."""
        ceiling = self.max_total_completion_tokens
        if ceiling <= 0:
            return False
        usage = self.get_state_usage(state)
        return usage is not None and usage.get("output_tokens", 0) >= ceiling

    def _seal_if_budget_spent(self, state, replies: list) -> list:
        """After a deferred turn's calls have run: if the budget is spent and
        nothing else ended the episode, these replies are the final env
        response, so the framework re-checks the stops instead of asking the
        model for a turn the ceiling does not cover."""
        if state.get("final_env_response") is None and self._output_budget_spent(state):
            state["final_env_response"] = replies
        return replies

    async def max_total_completion_tokens_reached(self, state) -> bool:
        """NOT a stop condition here — `piv_output_budget_exhausted` is.

        Deliberately undecorated, exactly as `no_tools_called` below:
        overriding the base method without `@vf.stop` removes it from
        `_stop_conditions`. The framework's version is the same predicate at
        priority 0, which would be harmless most of the time and wrong at the
        one moment that matters: while the budget stop defers a turn carrying
        an accepted `submit`, this one is still true and would name the
        ending `max_total_completion_tokens_reached` — the mechanism instead
        of what the agent did. One stop for one property, under our name.
        """
        return False

    async def no_tools_called(self, state) -> bool:
        """NOT a stop condition here. Deliberately undecorated: overriding the
        base method without `@vf.stop` removes it from `_stop_conditions`,
        because `discover_decorated` looks for the attribute on the bound
        method the MRO resolves.

        `ToolEnv` ends the rollout on the first assistant turn that carries no
        tool call. Measured against six real rollouts (reviews/budget_*
        2026-08-30): every one of them died there — a model narrating the
        repairs it had "made" without calling `write_ledger`, a reasoning-only
        turn the client renders as empty content, and a turn cut off at the
        per-turn completion cap. Zero ledgers delivered, and none of the three
        is a decision by the agent to stop. PLAN §6 says the episode ends when
        the agent calls `submit` or the turn limit is reached; the
        implementation had inherited the framework's default instead.

        A turn with no tool call is now answered by `env_response` with a
        fixed nudge and counts toward `max_turns`; the loop hazard that
        creates is bounded twice below — by `piv_no_tool_call_limit` for a
        run of no-tool turns of any kind, and by `piv_truncation_limit` for
        an unbroken run of turns cut off at the completion cap.
        """
        return False

    @vf.stop(priority=50)
    async def piv_submitted(self, state) -> bool:
        """The agent called `submit`: the only agent-driven termination.

        Above `has_final_env_response` in priority so the recorded
        `stop_condition` names what the agent did rather than the mechanism
        `env_response` used to stop the loop.

        The phase is the authority. `submit` is refused unless a candidate is
        stored and the boundary accepted it, so this fires only for an episode
        the agent ended with something to deliver.
        """
        return episode_phase(state) is EpisodePhase.TERMINAL

    @vf.stop(priority=45)
    async def piv_truncation_limit(self, state) -> bool:
        """MAX_CONSECUTIVE_TRUNCATED_TURNS truncated no-tool turns in a row.

        A reasoning model that runs past the per-turn completion cap produces
        a turn with no tool call every time, and the nudge it gets back is
        one more thing to reason about — so without a bound it can sit at the
        cap for the whole turn budget. It ends here instead, under a name
        that says what happened. Above `piv_no_tool_call_limit` in priority
        because an unbroken truncated run trips both at the same turn and
        "cut off at the cap" is the more specific, more actionable diagnosis;
        a run with even one non-truncated turn in it trips only the other.

        Counted, never quarantined, scored over the last committed revision —
        the same consequence as the no-tool limit and the turn cap.
        """
        return bool(state.get("piv_truncation_limit_reached"))

    @vf.stop(priority=40)
    async def piv_no_tool_call_limit(self, state) -> bool:
        """MAX_CONSECUTIVE_NO_TOOL_TURNS turns in a row with no tool call.

        The nudge must not become its own loop hazard: a model that has
        stopped calling tools would otherwise burn the whole turn budget on
        being told the same sentence. The turn cap would end it anyway; this
        ends it sooner, under a name the metrics can see
        (`piv/no_tool_limit`). It is an ordinary counted outcome — the score
        is the last committed revision's, exactly as at the turn cap — and
        never a quarantine: not calling a tool is the agent's behaviour, not
        an evaluator fault.
        """
        return bool(state.get("piv_no_tool_limit_reached"))

    @vf.stop(priority=35)
    async def piv_turn_cap_no_submit(self, state) -> bool:
        """`max_turns` reached and the agent never got an accepted `submit` in.

        The turn-cap rule, stated once and in one place: THE LAST COMMITTED
        REVISION IS STILL SCORED. The books the agent actually delivered
        through the loop are worth what they are worth; what changes is the
        NAME of the ending. `max_turns_reached` cannot tell "worked to the
        cap and forgot to submit" from "submitted at turn 25", and the
        episode contract exists precisely to tell those apart.

        The alternative — zero at the cap — was considered and refused. It
        would throw away a legitimately committed ledger over a missing final
        call, and it would fold the protocol slip into an ordinary bad score
        where nothing could see it. A policy that never submits learns that
        submit matters from `piv/turn_cap_no_submit` and `piv/submitted`,
        which is where that lesson belongs.

        Above `max_turns_reached` (priority 0) so this name wins when both are
        true, and below `piv_no_tool_call_limit` so a run that already ended
        for a different reason keeps its own name. A terminal protocol
        violation is excluded outright: that ending has its own score.
        """
        if state.get("piv_protocol_failure") or episode_phase(state) is EpisodePhase.TERMINAL:
            return False
        if not (self.max_turns > 0 and len(state.get("trajectory") or []) >= self.max_turns):
            return False
        if TERMINAL_TOOL in _calls_in_last_turn(state) and episode_phase(state) is EpisodePhase.CANDIDATE:
            return False                  # `piv_turn_cap_submit_unexecuted` names that ending
        state["piv_turn_cap_no_submit"] = True
        return True

    @vf.stop(priority=36)
    async def piv_turn_cap_submit_unexecuted(self, state) -> bool:
        """`max_turns` reached and the LAST assistant turn carried a `submit`
        the framework never ran.

        The loop checks completion at the top of each iteration and executes
        a turn's tool calls at the top of the NEXT one, so the calls of the
        turn that brings the count to `max_turns` are discarded (measured by
        the second verifier: a good write on turn 1 and `submit` on turn 25
        ended as `piv_turn_cap_no_submit` — an affirmative false claim about
        a policy that did learn to submit, just one turn late). The effective
        budget for an executed `submit` is therefore `max_turns - 1`, the
        system prompt says so, and this ending has its own name and metric
        so it is never confused with never submitting. The last committed
        revision is scored, as at every cap.
        """
        if state.get("piv_protocol_failure") or episode_phase(state) is EpisodePhase.TERMINAL:
            return False
        if not (self.max_turns > 0 and len(state.get("trajectory") or []) >= self.max_turns):
            return False
        # Only a submit that WOULD have been accepted counts: with nothing
        # written, or the last write refused, the call would have been refused
        # anyway and the honest name stays `piv_turn_cap_no_submit`.
        if TERMINAL_TOOL not in _calls_in_last_turn(state) or episode_phase(state) is not EpisodePhase.CANDIDATE:
            return False
        state["piv_turn_cap_submit_unexecuted"] = True
        return True

    @vf.stop(priority=55)
    async def piv_protocol_terminated(self, state) -> bool:
        """Counted terminal protocol violation, set by `env_response`.

        Priority 55, above every other ending: a turn the protocol could not
        answer executed nothing, so no agent-driven ending can be true of it,
        and the score it carries is the protocol's, not the last revision's —
        the name must say which. At the framework's default priority the
        stop shared rank 0 with `has_final_env_response`, and the mechanism
        used to end the loop named the ending instead of the violation.

        A turn the tool protocol cannot answer well-formedly — duplicate
        call ids — ends the rollout here. No error is set, so the rollout is
        counted, not quarantined; but it is the AGENT's terminal violation
        and carries the task contract's terminal protocol score (0.0) rather
        than the last committed ledger's score. The first version inherited
        that score: a malformed, non-replayable final action after enough
        correct work cost nothing, which is a loophole, not a policy. The
        ledger stays on disk for audit. Ending is the honest option: "one
        reply per distinct id" left the assistant message with two calls
        under one id, which a provider requiring one result per call
        occurrence rejects on the next turn.
        """
        return bool(state.get("piv_protocol_failure"))

    async def env_response(self, messages, state, **kwargs):
        """The production tool loop, with the turn validated before any side effect.

        Public rule: at most one `write_ledger` per assistant turn, and every
        tool-call id unique. Checked over the complete call list BEFORE
        anything executes, because the framework runs calls sequentially in
        one loop and pairs replies by id — two writes in one turn would race
        for the same file and an id collision would let the wrong reply
        attest the commit. An ambiguous turn is refused whole, as the agent's
        outcome, with nothing written.

        Revision then advances only on a reply that parses as a strict
        attestation (`parse_attestation`), matched to a `write_ledger` call by
        id. The three digests it carries are recorded under their own names.

        Two turns never reach the tool loop at all:

          - a turn with NO tool call — narration, an empty reasoning-only
            reply, or a reply truncated at the completion cap — is answered
            with a fixed nudge and counted, instead of ending the episode
            (see `no_tools_called`);
          - any turn after `submit` has been answered, because the workspace
            is frozen from that instant.

        Two counters ride every turn, for the input side of the budget the
        output ceiling does not price (Codex T48 §7, Q9): `piv_turn`, so the
        whole-read receipt can name the turn the content was sent on, and
        `piv_observation_bytes`, the running total of everything this
        environment has handed back.
        """
        state["piv_turn"] = state.get("piv_turn", 0) + 1
        return await self._answer_turn(messages, state, **kwargs)

    @staticmethod
    def _count_reply(state, message):
        """Add ONE reply's bytes to `state["piv_observation_bytes"]`.

        Counted AS EACH REPLY IS PRODUCED, inside `call_tool`, rather than
        once at the end of a turn: a single call list may carry twenty reads,
        and a budget that only updates between turns is not a budget inside
        one. Every message the environment hands back is counted — tool
        replies, refusals and the no-tool nudge alike — in UTF-8 bytes of the
        content actually sent, because all of them are input the next request
        pays for.

        Exactly once each. `call_tool` counts what it returns (which is every
        tool reply, including the ones it refuses without running a body), and
        `_answer_turn` counts only the messages it builds itself — the frozen
        turn, the duplicate-id and multi-write refusals, and the nudge — which
        never pass through `call_tool`.
        """
        if state is None:
            return message
        content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
        if isinstance(content, str):
            state["piv_observation_bytes"] = (state.get("piv_observation_bytes", 0)
                                              + len(content.encode("utf-8", errors="replace")))
        return message

    @classmethod
    def _count_observation(cls, state, replies: list) -> list:
        """`_count_reply` over a list the environment built itself."""
        for message in replies or []:
            cls._count_reply(state, message)
        return replies

    async def _answer_turn(self, messages, state, **kwargs):
        """One turn's replies, before the observation counter sees them."""
        from verifiers.legacy.types import ToolMessage

        calls = list(getattr(messages[-1], "tool_calls", None) or []) if messages else []
        if episode_phase(state) is EpisodePhase.TERMINAL:
            # The episode is over. Structurally the framework does not ask for
            # another turn (`final_env_response` is set below), so this is the
            # belt to that braces: nothing executes, nothing is written, and
            # the ledger digest cannot move after the delivery was declared.
            return self._frozen_turn(calls, state)
        if not calls:
            return self._no_tool_call_turn(state)
        # A turn that calls a tool ends both runs: the agent is acting again,
        # whether or not this turn was also cut off at the completion cap.
        state["piv_consecutive_no_tool_turns"] = 0
        state["piv_consecutive_truncated_turns"] = 0
        ids = [getattr(c, "id", None) for c in calls]
        writes = [c for c in calls if getattr(c, "name", None) == WRITE_TOOL]
        if len(set(ids)) != len(ids):
            # Two calls sharing an id cannot be answered: providers require
            # one tool result per call occurrence, and one reply per distinct
            # id leaves the transcript short a result on the next turn. Not
            # representable, so not recoverable. Nothing executes; the
            # rollout ENDS through the counted stop condition above, scored
            # over the last committed revision.
            state["piv_turns_rejected"] = state.get("piv_turns_rejected", 0) + 1
            state["piv_protocol_failure"] = PROTOCOL_DUPLICATE_TOOL_CALL_ID
            seen = []
            for i in ids:
                if i not in seen:
                    seen.append(i)
            replies = [ToolMessage(role="tool", content=TURN_DUPLICATE_ID, tool_call_id=i or "") for i in seen]
            # Measured: the framework's loop calls `env_response` while
            # building the NEXT prompt and only re-checks stop conditions
            # before the model call if `final_env_response` is set. Without
            # this the model would be called once more, on the malformed
            # transcript, before our stop condition was consulted.
            state["final_env_response"] = self._count_observation(state, replies)
            return replies
        if len(writes) > 1:
            # Recoverable, by contract: ids are unique, so one bounded result
            # per call is representable; nothing was executed, so the ledger
            # on disk is still the agent's last committed revision and
            # scoring is over that. Recorded as rejected in trusted state.
            state["piv_turns_rejected"] = state.get("piv_turns_rejected", 0) + 1
            return self._seal_if_budget_spent(state, self._count_observation(
                state, [ToolMessage(role="tool", content=TURN_MULTI_WRITE, tool_call_id=i or "") for i in ids]))

        token = _PIV_STATE.set(state)
        try:
            tool_messages = await super().env_response(messages, state, **kwargs)
        finally:
            _PIV_STATE.reset(token)

        by_id = {getattr(c, "id", None): c for c in calls}
        for message in tool_messages:
            call = by_id.get(getattr(message, "tool_call_id", None))
            if call is None or getattr(call, "name", None) != WRITE_TOOL:
                continue
            attestation = parse_attestation(getattr(message, "content", ""))
            if attestation is None:
                continue  # not a commit (rejected call, tool error text)
            # A well-formed receipt proves the tool CLAIMED a commit. Recompute
            # every digest from trusted inputs before believing it: the
            # argument the framework actually passed, the bytes actually on
            # disk, the text the scorer will actually read. A mismatch is a
            # tool regression — an evaluator failure — not an agent outcome.
            try:
                submitted = json.loads(getattr(call, "arguments", "") or "{}").get("content", "")
                raw = (Path(state["workspace"]) / LEDGER).read_bytes()  # one snapshot
                expected = digests_of(raw, submitted=submitted)
            except Exception as exc:
                raise record_evaluator_failure(state, "attestation", exc)
            mismatch = {k: (attestation[k], v) for k, v in expected.items() if attestation[k] != v}
            if mismatch:
                raise record_evaluator_failure(
                    state, "attestation",
                    RuntimeError(f"receipt disagrees with trusted inputs on {sorted(mismatch)}"))
            # The parse outcome the tool produced from the SAME snapshot,
            # keyed by the digests we just recomputed. Absent or keyed to
            # different bytes, the tool did not parse what it stored.
            pending = state.pop("piv_pending", None)
            if pending is None or pending.get("digests") != expected:
                raise record_evaluator_failure(
                    state, "attestation", RuntimeError("no parse outcome for the committed bytes"))
            # Install atomically: the revision, the receipt and the committed
            # outcome are one assignment of one frozen object. An unexpected
            # boundary exception installs the sticky failure for the
            # attempted revision and leaves the previous commitment intact.
            revision = state.get("piv_revision", 0) + 1
            outcome = pending["outcome"]
            # The earlier commitment is invalidated before the new one is
            # installed: on a commit failure nothing stale can be scored
            # (the sticky evaluator record dominates anyway), and a delivery
            # from a previous finalisation cannot describe this revision.
            state.pop("piv_committed", None)
            state.pop("piv_delivery", None)
            state.pop("piv_score", None)
            state.pop("piv_result", None)
            try:
                manifest = Path(state["workspace"]) / PUBLICATION_FILE
                if os.path.lexists(manifest):
                    os.unlink(manifest)          # no manifest may describe a superseded revision
                receipt = new_receipt(state.get("piv_rollout_id", "?"), revision, expected)
                if isinstance(outcome, Accepted):
                    committed = commit(outcome, self.contract, receipt)
                elif isinstance(outcome, ProtocolFailure):
                    committed = reject(outcome, self.contract, receipt)
                else:
                    raise RuntimeError(f"boundary returned {type(outcome).__name__}: {outcome}")
            except Exception as exc:
                raise record_evaluator_failure(state, "commit", exc)
            state["piv_committed"] = committed
            state["piv_revision"] = revision
            for key in expected:
                state[f"piv_{key}"] = expected[key]
        if episode_phase(state) is EpisodePhase.TERMINAL:
            # `submit` ran inside this turn's call list and was accepted.
            # Measured: the
            # framework's loop calls `env_response` while building the NEXT
            # prompt and only re-checks stop conditions before the model call
            # if `final_env_response` is set. Without this the model would be
            # asked for one more turn after it had already finished — and
            # that turn's calls would meet the frozen-turn refusal above,
            # which is a worse transcript than simply stopping.
            state["final_env_response"] = tool_messages
        return self._seal_if_budget_spent(state, tool_messages)

    def _frozen_turn(self, calls, state) -> list:
        """Every call in a post-submit turn refused, nothing executed."""
        from verifiers.legacy.types import ToolMessage

        state["piv_turns_rejected"] = state.get("piv_turns_rejected", 0) + 1
        seen: list = []
        for call in calls:
            identifier = getattr(call, "id", None) or ""
            if identifier not in seen:
                seen.append(identifier)
        replies = self._count_observation(
            state, [ToolMessage(role="tool", content=TURN_AFTER_SUBMIT, tool_call_id=i) for i in seen])
        state["final_env_response"] = replies
        return replies

    def _no_tool_call_turn(self, state) -> list:
        """An assistant turn with no tool call: answered, counted, not fatal.

        One fixed sentence, chosen by code, carrying no information about the
        world and no hint about the task — the same text for a narration, an
        empty reasoning-only turn and a truncated one, except that a turn the
        framework marked truncated is told so. `is_truncated` on the last
        trajectory step is the framework's own flag, derived from the
        client's `finish_reason == "length"` and from the token accounting;
        it is a fact about the agent's own message, so saying it leaks
        nothing. The turn counts toward `max_turns` like any other.

        Two runs are kept, not one. `piv_consecutive_no_tool_turns` counts
        every no-tool turn in a row; `piv_consecutive_truncated_turns` counts
        only turns the framework marked truncated and is reset by a no-tool
        turn that was NOT truncated. They share a bound
        (MAX_CONSECUTIVE_TRUNCATED_TURNS == MAX_CONSECUTIVE_NO_TOOL_TURNS)
        and they name different endings, so "looping at the completion cap"
        and "stopped calling tools" are separable in the metrics.
        """
        from verifiers.legacy.types import UserMessage

        state["piv_no_tool_turns"] = state.get("piv_no_tool_turns", 0) + 1
        run = state.get("piv_consecutive_no_tool_turns", 0) + 1
        state["piv_consecutive_no_tool_turns"] = run
        truncated = _last_turn_truncated(state)
        if truncated:
            state["piv_no_tool_truncated_turns"] = state.get("piv_no_tool_truncated_turns", 0) + 1
            truncated_run = state.get("piv_consecutive_truncated_turns", 0) + 1
        else:
            # One turn that was NOT cut off breaks the truncated run: whatever
            # this model is doing, it is no longer "looping at the completion
            # cap". The no-tool run above keeps counting, and ends it.
            truncated_run = 0
        state["piv_consecutive_truncated_turns"] = truncated_run
        # Stop conditions, not returns: both flags end the loop through a
        # named stop. Neither sends a nudge nobody will read — an empty final
        # env response ends the loop without appending a dangling user
        # message to the transcript.
        if truncated_run >= MAX_CONSECUTIVE_TRUNCATED_TURNS:
            # Both flags: a run of truncated turns IS a run of no-tool turns,
            # so `piv/no_tool_limit` keeps counting these endings (it did
            # before the truncation limit existed; the second verifier found
            # it had silently dropped them). The stop-condition priority
            # picks the more specific NAME, `piv_truncation_limit`.
            state["piv_truncation_limit_reached"] = True
            state["piv_no_tool_limit_reached"] = True
            state["final_env_response"] = []
            return []
        if run >= MAX_CONSECUTIVE_NO_TOOL_TURNS:
            state["piv_no_tool_limit_reached"] = True
            state["final_env_response"] = []
            return []
        return self._count_observation(state, [UserMessage(
            role="user", content=TURN_TRUNCATED_NO_TOOL if truncated else TURN_NO_TOOL)])

    async def evaluate(self, *args, **kwargs):
        """Evaluation mode: any quarantine makes the batch INVALID.

        `evaluate` in the framework is a thin call to `generate`, so the
        partition happens there; this only records which mode we are in. The
        difference in consequence is the point — see `generate`.
        """
        token = _PIV_MODE.set("evaluate")
        try:
            return await super().evaluate(*args, **kwargs)
        finally:
            _PIV_MODE.reset(token)

    def evaluate_sync(self, *args, **kwargs):
        """The sync evaluation door does not pass through `evaluate`.

        Measured: `Environment.evaluate_sync` calls `generate_sync`, which
        calls `generate` — never `evaluate`. So the mode set above never
        reached this door: an evaluation run through it reported
        RESAMPLE_REQUIRED instead of INVALID, and with `partial_batches=True`
        it *returned* a partial batch from an evaluation call — the thing the
        constructor flag was documented never to do. The property had been
        hooked where it was defined, not at every entry point that reaches
        it (LESSONS 54, 55). The witness now runs this door for real.
        """
        token = _PIV_MODE.set("evaluate")
        try:
            return super().evaluate_sync(*args, **kwargs)
        finally:
            _PIV_MODE.reset(token)

    async def generate(self, *args, **kwargs):
        """Quarantine evaluator failures before results leave the environment.

        Measured: `generate` is not `@final` and `GenerateOutputs.outputs` is
        a plain list, so the split happens here, on the object every consumer
        receives. `evaluate` and both `_sync` variants route through this —
        but only `evaluate` and `evaluate_sync` set the mode, each at its own
        door, because `evaluate_sync` does not call `evaluate`.

        What this must NOT do is publish a survivor average as the score. An
        agent that finds an input crashing the evaluator only on tasks it
        would score badly on would have those rollouts quarantined and the
        average over the rest would rise — a high number the books did not
        earn. So when anything is quarantined, every reward-derived aggregate
        the framework computed (`avg_reward`, `avg_metrics`, `avg_error`,
        `pass_at_k`, `pass_all_k`) is moved to a raw namespace and replaced
        with NaN, which fails closed in any downstream arithmetic; the
        survivor mean is published only as `piv_conditional_avg_reward`, a
        diagnostic. Under `evaluate` the batch is INVALID; under `generate`
        it is RESAMPLE_REQUIRED. Only a batch with nothing quarantined keeps
        the ordinary comparable aggregates.

        Quarantined rollouts are moved, not dropped, with their original
        index, so scored and quarantined stay aligned with prompts, tasks and
        seeds. The pass is structurally idempotent: a second pass re-derives
        the bound set and rebuilds the same partition, and the raw aggregate
        namespace is written once — so dynamic dispatch between the public
        entry points can neither partition twice nor overwrite the
        framework's originals with the NaNs the first pass left.
        """
        results = await super().generate(*args, **kwargs)
        metadata = results.setdefault("metadata", {})

        # Structural idempotence. A prior marker is not trusted by itself: the
        # bound output set is re-derived (scored on the result plus anything
        # already quarantined), re-checked for quarantinable codes, and the
        # partition is rebuilt from that union. The marker cannot suppress a
        # scan, and a stale marker cannot hide a newly appended output.
        prior_q = [q.get("output") for q in metadata.get("piv_quarantined", []) if isinstance(q, dict)]
        prior_p = [a.get("output") for a in metadata.get("piv_protocol_failure_artifacts", []) if isinstance(a, dict)]
        attempted = (list(results.get("outputs", []))
                     + [o for o in prior_q if isinstance(o, dict)]
                     + [o for o in prior_p if isinstance(o, dict)])
        if metadata.get("piv_partition_schema") == PARTITION_SCHEMA and all(
            isinstance(o, dict) and "piv_index" in o for o in attempted
        ):
            attempted.sort(key=lambda o: o["piv_index"])
        else:
            for index, out in enumerate(attempted):
                if isinstance(out, dict):
                    out["piv_index"] = index
        scored, quarantined = partition_rollouts(attempted)
        results["outputs"] = scored
        metadata["piv_partition_schema"] = PARTITION_SCHEMA

        metadata["piv_attempted"] = len(attempted)
        metadata["piv_scored"] = len(scored)
        metadata["piv_training_eligible"] = sum(1 for o in scored if training_eligible(o))
        metadata["piv_protocol_failures"] = len(scored) - metadata["piv_training_eligible"]
        metadata["piv_status_semantics"] = STATUS_SEMANTICS
        # Which observation and termination rules this batch ran under: two
        # batches sharing a task id but not this pair are not one condition
        # (Codex T47 §2).
        metadata["piv_episode_contract"] = {
            "version": EPISODE_CONTRACT_VERSION,
            "digest": self.episode_contract_digest(),
            "max_episode_output_tokens": self.max_total_completion_tokens,
        }
        # The package's training door enforces the default partition, not
        # merely exposes it: outside evaluation, `outputs` are the replayable
        # trajectories and counted protocol failures move to an artifact list
        # with their original index and stratum. Evaluation keeps every
        # counted outcome in `outputs` for score reporting; the framework's
        # aggregates are over all counted outcomes in both modes.
        if _PIV_MODE.get() != "evaluate":
            kept, moved = [], []
            for o in scored:
                (kept if training_eligible(o) else moved).append(o)
            results["outputs"] = kept
            # Bounded like every trajectory-bearing artifact: a batch of long
            # malformed terminal trajectories is agent failure, not evaluator
            # failure, and it must not bypass the artifact memory policy for
            # that reason. Count-capped, then size-capped via the same
            # truncation the quarantine store uses.
            records = [
                {"original_index": o.get("piv_index"), "example_id": o.get("example_id"), "output": o}
                for o in moved[:MAX_PROTOCOL_ARTIFACTS]
            ]
            records, _, truncated = _bounded_records(records)
            metadata["piv_protocol_failure_artifacts"] = records
            metadata["piv_protocol_artifacts_truncated"] = truncated or len(moved) > MAX_PROTOCOL_ARTIFACTS
        # Two denominators, labelled, so nobody recomputes a survivor-only
        # mean from the replayable list and calls it performance.
        metadata["piv_denominators"] = {
            "aggregates_over": "every counted outcome (piv_scored), protocol failures at 0.0 included",
            "counted_outcomes": len(scored),
            "training_trajectories": metadata["piv_training_eligible"],
            "protocol_failures": metadata["piv_protocol_failures"],
        }
        metadata["piv_quarantined"] = [
            {
                "original_index": o.get("piv_index"),
                # piv_code is set by classify_output from the typed record's
                # projection (`metrics["evaluator_failed"]`) — a tool-phase
                # failure arrives wrapped as ToolCallError, and the code names
                # what the failure IS, not how the framework packaged it. No
                # chain is searched.
                "code": ((o.get("error") or {}).get("piv_code")
                         or (o.get("error") or {}).get("error") or "unknown"),
                "message": ((o.get("error") or {}).get("message") or "")[:200],
                "output": o,
            }
            for o in quarantined
        ]
        metadata["piv_quarantined_count"] = len(quarantined)
        batch_id = uuid.uuid4().hex
        metadata["piv_batch_id"] = batch_id
        if quarantined:
            _store_artifact(batch_id, list(metadata["piv_quarantined"]))
        reasons: dict[str, int] = {}
        for q in metadata["piv_quarantined"]:
            reasons[q["code"]] = reasons.get(q["code"], 0) + 1
        metadata["piv_quarantine_reason_counts"] = reasons
        metadata["piv_failure_rate"] = (
            len(quarantined) / len(attempted) if attempted else 0.0
        )
        rewards = [o.get("reward", 0.0) for o in scored if isinstance(o, dict)]
        metadata["piv_conditional_avg_reward"] = (
            sum(rewards) / len(rewards) if rewards else None
        )

        indices = [o.get("piv_index") for o in attempted if isinstance(o, dict)]
        if len(set(indices)) != len(indices) or len(scored) + len(quarantined) != len(attempted):
            raise PIVEvaluationBatchInvalid({**metadata, "piv_status": "PARTITION_INCONSISTENT"})

        if not quarantined:
            metadata["piv_status"] = "VALID"
            return results

        evaluating = _PIV_MODE.get() == "evaluate"
        metadata["piv_status"] = "INVALID" if evaluating else "RESAMPLE_REQUIRED"
        raw = {}
        for key in REWARD_DERIVED_AGGREGATES:
            if key in metadata:
                raw[key] = metadata[key]
                metadata[key] = _invalidated(metadata[key])
        # Written once. A second pass over an already-partitioned result sees
        # the NaNs it wrote and would have replaced the framework's originals
        # with them — the idempotence witness compared indices, not this.
        metadata.setdefault("piv_raw_including_placeholders", raw)

        # Fail closed by raising, not by returning a sentinel. This runs after
        # the framework has returned and outside the rubric layer that turns
        # exceptions into zeros, so it reaches the caller of the public API.
        # Evaluation never returns; training returns only on explicit opt-in.
        # `partial_batches` is constructor-only operator configuration and
        # it never touches evaluation: a diagnostic training run may accept a
        # partial batch; a comparison score may not.
        if evaluating:
            raise PIVEvaluationBatchInvalid(metadata)
        if not self.partial_batches:
            raise PIVResampleRequired(metadata)
        return results


# Full quarantined rollouts live here, capped by batches AND bytes, keyed by
# batch id. The exception carries codes and the batch id — never the
# trajectories. Attaching agent-controlled content to an exception retains it
# in memory and leaks it through any logger that prints `repr(exc)`.
#
# A just-stored batch is PINNED until its caller retrieves it: eviction by a
# concurrent batch must never turn an advertised `batch_id` into a dangling
# handle. Pins are themselves bounded (oldest released first), and a batch
# larger than its own cap is stored without trajectories, so pinned memory is
# bounded by MAX_PINNED_BATCHES × MAX_ARTIFACT_BATCH_BYTES.
QUARANTINE_ARTIFACTS: dict[str, dict] = {}
QUARANTINE_PINNED: dict[str, float] = {}      # batch id -> pinned at (monotonic)
QUARANTINE_EVICTED: dict[str, None] = {}      # ids evicted before retrieval, bounded, so a lost handle says so
MAX_EVICTED_IDS = 1000
MAX_QUARANTINE_BATCHES = 50
MAX_QUARANTINE_BYTES = 8 * 1024 * 1024
MAX_ARTIFACT_BATCH_BYTES = 2 * 1024 * 1024
MAX_PINNED_BATCHES = 8
MAX_PROTOCOL_ARTIFACTS = 200                  # per batch, before the byte cap
PIN_TTL_SECONDS = 600.0                       # a caller that never retrieves cannot hold capacity forever
# The true maximum: the store's byte cap plus every pin at the per-batch cap,
# since pinned batches are exempt from eviction. Measured as serialised JSON
# bytes; the dict holds the same output objects the returned results hold
# (references, not copies, unless truncated), so this bounds retention, not
# the process's total footprint.
MAX_RESIDENT_BYTES = MAX_QUARANTINE_BYTES + MAX_PINNED_BATCHES * MAX_ARTIFACT_BATCH_BYTES
_ARTIFACT_LOCK = threading.Lock()
_ARTIFACT_BULK_KEYS = ("completion", "trajectory", "prompt")


def _serialised_size(records) -> int:
    return len(json.dumps(records, default=str).encode("utf-8"))


def _bounded_records(records: list) -> tuple[list, int, bool]:
    size = _serialised_size(records)
    if size <= MAX_ARTIFACT_BATCH_BYTES:
        return records, size, False
    slim = []
    for record in records:
        out = record.get("output") if isinstance(record, dict) else None
        if isinstance(out, dict):
            out = {k: v for k, v in out.items() if k not in _ARTIFACT_BULK_KEYS}
            out["piv_artifact_truncated"] = True
            record = {**record, "output": out}
        slim.append(record)
    return slim, _serialised_size(slim), True


def _store_artifact(batch_id: str, records: list) -> None:
    records, size, truncated = _bounded_records(records)
    with _ARTIFACT_LOCK:
        QUARANTINE_ARTIFACTS[batch_id] = {"records": records, "bytes": size, "truncated": truncated}
        _pin_locked(batch_id)
        _evict_locked()


def _pin_locked(batch_id: str) -> None:
    QUARANTINE_PINNED[batch_id] = time.monotonic()
    while len(QUARANTINE_PINNED) > MAX_PINNED_BATCHES:
        QUARANTINE_PINNED.pop(next(iter(QUARANTINE_PINNED)))


def _expire_pins_locked() -> None:
    now = time.monotonic()
    for bid, pinned_at in list(QUARANTINE_PINNED.items()):
        if now - pinned_at > PIN_TTL_SECONDS:
            QUARANTINE_PINNED.pop(bid)


def _evict_locked() -> None:
    _expire_pins_locked()
    total = sum(v["bytes"] for v in QUARANTINE_ARTIFACTS.values())
    for bid in list(QUARANTINE_ARTIFACTS):  # insertion order: oldest first
        if len(QUARANTINE_ARTIFACTS) <= MAX_QUARANTINE_BATCHES and total <= MAX_QUARANTINE_BYTES:
            return
        if bid in QUARANTINE_PINNED:
            continue
        total -= QUARANTINE_ARTIFACTS.pop(bid)["bytes"]
        QUARANTINE_EVICTED[bid] = None
        while len(QUARANTINE_EVICTED) > MAX_EVICTED_IDS:
            QUARANTINE_EVICTED.pop(next(iter(QUARANTINE_EVICTED)))


class ArtifactEvicted(LookupError):
    """The batch existed and was evicted before retrieval (pin released by
    TTL or pin pressure). Distinct from an unknown id: the exception's
    bounded summary is still valid for incident correlation, the full
    records are gone, and the caller is told so rather than shown `[]`."""


def quarantine_artifact(batch_id: str, release: bool = True) -> list:
    """The full records for a batch. Retrieval releases the pin by default.

    "Pinned until retrieval" is bounded: a pin also ends by TTL or when
    more than MAX_PINNED_BATCHES newer batches are pinned. After that the
    batch is evictable, and retrieving an evicted id raises
    `ArtifactEvicted` instead of returning an empty list. Expired pins are
    also released here, on the read boundary, so an idle process does not
    keep them.
    """
    with _ARTIFACT_LOCK:
        _expire_pins_locked()
        entry = QUARANTINE_ARTIFACTS.get(batch_id)
        if release:
            QUARANTINE_PINNED.pop(batch_id, None)
        if entry is None:
            if batch_id in QUARANTINE_EVICTED:
                raise ArtifactEvicted(batch_id)
            return []
        return list(entry["records"])


class PIVEvaluationBatchInvalid(Exception):
    """An evaluation batch contained an evaluator failure. No comparable score.

    Raised by the environment wrapper AFTER the framework has returned and
    AFTER the quarantine artifact is stored, outside the rubric layer that
    converts exceptions to zero. Carries a bounded summary and a handle; the
    full records are retrievable with `quarantine_artifact(exc.batch_id)`.

    What it SAYS about each quarantined rollout is owned text selected by
    code (`public_quarantine_message`) — never the framework's or a tool's
    exception message, not even truncated. The first version carried
    `message[:200]`: a size bound controls volume, not content, and 200
    characters hold a path, a secret, or the agent's own text comfortably.
    """

    def __init__(self, metadata: dict):
        self.status = metadata.get("piv_status")
        self.attempted = metadata.get("piv_attempted")
        self.scored = metadata.get("piv_scored")
        self.batch_id = metadata.get("piv_batch_id")
        self.reason_counts = metadata.get("piv_quarantine_reason_counts", {})
        self.quarantined = [
            {"original_index": q.get("original_index"), "code": q.get("code"),
             "message": public_quarantine_message(q.get("code"))}
            for q in metadata.get("piv_quarantined", [])
        ]
        self.failed_strata = sorted({
            str((q.get("output") or {}).get("example_id", "?"))
            for q in metadata.get("piv_quarantined", [])
        })
        self.attempt_budget = 3  # a naive retry of a deterministic failing seed must not loop forever
        # Scalars only. No outputs, no trajectories, no tool messages: the
        # full records are in the artifact store under `batch_id`.
        self.metadata = {
            k: metadata.get(k) for k in (
                "piv_status", "piv_attempted", "piv_scored", "piv_quarantined_count",
                "piv_failure_rate", "piv_conditional_avg_reward",
                "piv_quarantine_reason_counts", "piv_batch_id", "avg_reward",
            )
        }
        super().__init__(
            f"{self.status}: {len(self.quarantined)} of {self.attempted} rollouts "
            f"quarantined ({self.reason_counts}); batch {self.batch_id}; no comparable aggregate"
        )


class PIVResampleRequired(PIVEvaluationBatchInvalid):
    """A training batch contained an evaluator failure. Refill before use.

    The default for `generate`. A caller that can handle a partial batch opts
    in with `load_environment(partial_batches=True)` and receives the
    partitioned result instead; the opt-in is the acknowledgement.
    """


# Which mode the public entry point was called in. A context variable rather
# than an instance attribute so concurrent evaluations cannot see each other.
_PIV_MODE: contextvars.ContextVar = contextvars.ContextVar("piv_mode", default="generate")

# Every aggregate the framework derives from rewards or metrics. Measured
# against GenerateMetadata in verifiers 0.3.1; all are computed by the
# framework's outputs builder over ALL rollouts, placeholders included, so
# after a partition each is either untouched (nothing quarantined) or invalid.
REWARD_DERIVED_AGGREGATES = ("avg_reward", "avg_metrics", "avg_error", "pass_at_k", "pass_all_k")


def _invalidated(value):
    """NaN for numbers, NaN-valued for dicts of numbers: fails closed in
    arithmetic instead of quietly averaging a placeholder."""
    if isinstance(value, dict):
        return {k: _invalidated(v) for k, v in value.items()}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return math.nan
    return value


class PIVEvaluatorFailed(vf.InfraError):
    """The evaluator, not the agent, failed to produce a score.

    A `verifiers` error subclass on purpose. The framework serialises
    `state["error"]` into `RolloutOutput.error` as
    `{"error": type(e).__name__, "message": ..., "error_chain_repr": ...}`, so
    the class name *is* the stable code a collector keys on — no string
    parsing, no convention to remember. The chain repr preserves any earlier
    framework error we were layered on top of.

    Bounded by construction: the message carries a phase, the rollout id and
    revision, and the failure class. Stack traces and filesystem paths stay in
    evaluator-side logs; nothing here is agent-influenceable.
    """

    def __init__(self, phase: str, rollout_id: str, revision: int, cause: BaseException,
                 prior_error_code: str | None = None):
        self.phase = phase
        self.rollout_id = rollout_id
        self.revision = revision            # the revision that failed; sticky
        self.cause_type = type(cause).__name__
        self.prior_error_code = prior_error_code
        super().__init__(
            f"PIV_EVALUATOR_FAILED phase={phase} rollout={rollout_id} "
            f"revision={revision} cause={self.cause_type}"
            + (f" prior={prior_error_code}" if prior_error_code else "")
        )


# Diagnostics only. The authoritative record is the typed
# `state["piv_evaluator_failure"]`; this store holds detail that must not
# reach the rollout output, and nothing decides anything by reading it.
#
# Bounded, because an adversarial corpus that finds one evaluator bug can hit
# it thousands of times: at most MAX_DIAGNOSTICS records, each message capped,
# duplicates by `_fingerprint` — (phase, type, top owned frame) — folded into
# a count with first/last revision. Full tracebacks belong in a rotated
# evaluator log, not a process dict.
EVALUATOR_DIAGNOSTICS: dict[tuple, dict] = {}
MAX_DIAGNOSTICS = 200
MAX_DIAGNOSTIC_CHARS = 500
MAX_PER_FINGERPRINT = 50
_DIAGNOSTICS_LOCK = threading.Lock()


def _fingerprint(phase: str, exc: BaseException) -> tuple:
    """(phase, type, top owned frame). Not the message, not the input.

    Folding by (phase, type) alone merges unrelated defects; folding by input
    digest lets an adversary mint 200 distinct inputs and evict the record
    that matters. The top frame inside this package is stable across inputs
    and distinct across bugs.
    """
    frame = "?"
    for entry in reversed(traceback.extract_tb(exc.__traceback__) or []):
        if "beancount_ledger" in entry.filename.replace("\\", "/"):
            frame = f"{Path(entry.filename).name}:{entry.lineno}"
            break
    return (phase, type(exc).__name__, frame)


EVALUATOR_RECORD_KEY = "piv_evaluator_failure"
# The metric key the typed record projects to. Package-owned: a generic
# `evaluator_failed` collides the day another monitor or plugin in the rubric
# group picks the obvious name.
METRIC_EVALUATOR_FAILED = "piv/evaluator_failed"
# Terminal protocol violations by the agent: counted, scored 0.0, and
# projected so a replay/training filter can drop trajectories whose final
# assistant message is not answerable one-result-per-call.
METRIC_PROTOCOL_FAILED = "piv/protocol_failed"
PROTOCOL_DUPLICATE_TOOL_CALL_ID = "DUPLICATE_TOOL_CALL_ID"
# Structurally replayable: no terminal protocol violation and no evaluator
# failure. A counted evaluation outcome is not the same thing as a trainable
# transcript, and the package ships the default rather than leaving it to
# every consumer to remember.
METRIC_TRAINING_ELIGIBLE = "piv/training_eligible"
# The episode contract, made visible to whoever reads a batch. None of these
# is a reward or a failure: they say how the episode ENDED and how much of it
# the agent spent not calling tools, which is exactly the thing that was
# invisible when the framework's `no_tools_called` was ending rollouts.
METRIC_SUBMITTED = "piv/submitted"
METRIC_NO_TOOL_TURNS = "piv/no_tool_turns"
METRIC_NO_TOOL_LIMIT = "piv/no_tool_limit"
METRIC_NO_TOOL_TRUNCATED = "piv/no_tool_truncated"     # of the no-tool turns, how many the client marked truncated
METRIC_TRUNCATION_LIMIT = "piv/truncation_limit"       # ended on an unbroken run of truncated no-tool turns
METRIC_TURN_CAP_NO_SUBMIT = "piv/turn_cap_no_submit"   # ended at max_turns with no accepted submit
METRIC_TURN_CAP_SUBMIT_UNEXECUTED = "piv/turn_cap_submit_unexecuted"   # submit asked for on the last turn, never run
METRIC_SUBMIT_REFUSED = "piv/submit_refused"           # submit calls answered "nothing to submit"
METRIC_OUTPUT_BUDGET_EXHAUSTED = "piv/output_budget_exhausted"   # ended at MAX_EPISODE_OUTPUT_TOKENS
METRIC_BUDGET_ACCOUNTING_INVALID = "piv/budget_accounting_invalid"   # provider usage could not meter the ceiling
METRIC_BUDGET_ACCOUNTING_SUSPICIOUS = "piv/budget_accounting_suspicious"  # a heuristic anomaly, not a verdict
METRIC_OBSERVATION_BYTES = "piv/observation_bytes"     # every reply the environment returned, in UTF-8 bytes
METRIC_COMPLETE_READS = "piv/complete_reads"           # ledger reads that returned content, not a receipt
METRIC_LEDGER_RECEIPTS = "piv/ledger_receipts"         # complete reads answered "unchanged" instead
METRIC_OBSERVATION_REFUSED = "piv/observation_refused"  # calls refused with the observation budget spent

STATUS_SEMANTICS = (
    "piv_status is EVALUATOR validity: VALID means every attempted rollout was "
    "scored by a working evaluator. It says nothing about task success (a counted "
    "0.0 is VALID) and nothing about training eligibility (see piv/training_eligible "
    "and training_partition)."
)


def training_eligible(out) -> bool:
    """Whether a scored output is a replayable trajectory."""
    metrics = out.get("metrics") if isinstance(out, dict) else getattr(out, "metrics", None)
    if not isinstance(metrics, dict):
        return False
    return metrics.get(METRIC_PROTOCOL_FAILED) != 1.0 and metrics.get(METRIC_EVALUATOR_FAILED) != 1.0


def training_partition(results) -> dict:
    """The package default split of a scored batch.

        scored_evaluation_outcomes   results["outputs"] as returned (counted
                                     protocol failures included, at 0.0)
        trajectories                 the replayable subset, for replay / chat
                                     datasets
        protocol_failure_artifacts   the excluded outputs, kept for diagnosis
                                     or deliberate adversarial training

    An advanced trainer may take `results["outputs"]` raw on purpose; the
    default does not depend on remembering that a numeric reward and an
    evaluator-valid status do not imply a replayable transcript.
    """
    outputs = list(results.get("outputs", []))
    return {
        "scored_evaluation_outcomes": outputs,
        "trajectories": [o for o in outputs if training_eligible(o)],
        "protocol_failure_artifacts": [o for o in outputs if not training_eligible(o)],
    }


def evaluator_failure(state) -> "PIVEvaluatorFailed | None":
    """The authoritative record, if this rollout has one.

    A typed, evaluator-owned entry in trusted state — NOT the framework's
    `state["error"]`. That slot is the framework's projection and the
    framework rewrites it as it likes: a tool-phase marker arrives there as
    `ToolCallError` with our marker as its cause. Reading the chain back out
    of an exception, or worse out of its repr, is substring matching by
    another name. The record is installed before anything is raised and is
    what every decision reads.
    """
    record = state.get(EVALUATOR_RECORD_KEY)
    return record if isinstance(record, PIVEvaluatorFailed) else None


def record_evaluator_failure(state, phase: str, exc: BaseException) -> PIVEvaluatorFailed:
    """Make the rollout evaluator-failed. Sticky; never overwrites a prior cause.

    Order matters and is deliberate:

      1. the state marker is written first, so a failure while recording
         diagnostics cannot leave the rollout looking like an ordinary zero;
      2. a pre-existing framework error is preserved as the cause, not
         replaced — the collector sees both in the chain;
      3. once set, the marker is never cleared within the rollout. An agent
         that triggers an internal bug and then writes a valid ledger must not
         be able to wash the marker away; public protocol rejection is
         recoverable by a later write, evaluator failure is not.
    """
    existing = evaluator_failure(state)
    if existing is not None:
        return existing  # sticky
    failure = PIVEvaluatorFailed(
        phase, state.get("piv_rollout_id", "?"), state.get("piv_revision", 0), exc
    )
    prior = state.get("error")
    # The typed record is written FIRST and is the authority. The framework
    # slot below is a projection for consumers that only read the framework's
    # own fields; the framework may overwrite it and that must not matter.
    state[EVALUATOR_RECORD_KEY] = failure
    # A pre-existing framework error is preserved as a bounded CODE in the
    # marker, not chained as an object. Measured: chaining a prior error with
    # a 3,000-character message put 3,143 characters into `error_chain_repr`,
    # which is unbounded output from a field the rollout output serialises.
    # The object itself goes to diagnostics, referenced by rollout id.
    prior = state.get("error")
    if prior is not None and not isinstance(prior, PIVEvaluatorFailed):
        failure = PIVEvaluatorFailed(
            phase, failure.rollout_id, failure.revision, exc,
            prior_error_code=type(prior).__name__,
        )
        state[EVALUATOR_RECORD_KEY] = failure
    state["error"] = failure
    try:
        _record_diagnostic(state, phase, exc, prior)
    except Exception:  # diagnostics must never affect the verdict
        pass
    return failure


def _record_diagnostic(state, phase, exc, prior) -> None:
    key = _fingerprint(phase, exc)
    with _DIAGNOSTICS_LOCK:
        entry = EVALUATOR_DIAGNOSTICS.get(key)
        if entry is None:
            if len(EVALUATOR_DIAGNOSTICS) >= MAX_DIAGNOSTICS:
                EVALUATOR_DIAGNOSTICS.pop(next(iter(EVALUATOR_DIAGNOSTICS)))  # drop oldest
            entry = EVALUATOR_DIAGNOSTICS[key] = {
                "phase": phase,
                "type": type(exc).__name__,
                "frame": key[2],
                "detail": str(exc)[:MAX_DIAGNOSTIC_CHARS],
                "prior": (type(prior).__name__ if prior is not None else None),
                "count": 0,
                "first_rollout": state.get("piv_rollout_id"),
                "first_revision": state.get("piv_revision"),
            }
        if entry["count"] < MAX_PER_FINGERPRINT:
            entry["last_rollout"] = state.get("piv_rollout_id")
            entry["last_revision"] = state.get("piv_revision")
        entry["count"] += 1


# What each error code in a rollout output means for the batch. Keyed by the
# serialised class name, which is what `ErrorData.error` carries.
#
# The rule that matters is the default: an UNKNOWN code is quarantined and
# flagged, never counted. The first version of this counted everything except
# our own marker, which is the same reward bug under a different class name —
# a model-client timeout or a framework aggregation bug is no more the agent's
# fault than a scorer exception, and its placeholder zero would have trained
# the agent as if it had submitted badly.
#
# Only errors that the public tool contract attributes to the agent are
# counted: malformed tool arguments and a tool call that raised. Everything
# in the pinned framework's error tree is classified explicitly; the
# exhaustiveness test fails if a framework upgrade adds a class this table
# does not name.
COUNTED = "counted"
QUARANTINED = "quarantined"
ERROR_CONSEQUENCES = {
    None: COUNTED,                        # no error: an ordinary scored rollout
    "ToolParseError": COUNTED,            # agent sent malformed tool arguments
    # The framework raises ToolCallError for ANY exception inside a tool
    # implementation — an agent misuse and an internal bug alike. Not
    # attributable by class name, so quarantined; our own tools reclassify
    # before the framework wraps (see `call_tool`), so a counted misuse never
    # reaches this code and an internal bug carries our marker in its chain.
    "ToolCallError": QUARANTINED,
    "PIVEvaluatorFailed": QUARANTINED,    # ours
    "Error": QUARANTINED,                 # bare framework error: unattributable
    "ModelError": QUARANTINED,            # model client, not the policy's answer
    "InvalidModelResponseError": QUARANTINED,
    "EmptyModelResponseError": QUARANTINED,
    "OverlongPromptError": QUARANTINED,   # a property of the task, not the agent
    "ToolError": QUARANTINED,             # base class: unattributable without a subclass
    "InfraError": QUARANTINED,
    "TunnelError": QUARANTINED,
    "SandboxError": QUARANTINED,
    "BrowserSandboxError": QUARANTINED,
}

# What the raised exception may SAY about a quarantined rollout: owned text
# selected by code. Never the framework's or a tool's exception message, not
# even truncated. Canary tests plant markers at the head, middle and tail of
# a long exception and in the agent's own submission and assert none reaches
# str/repr/metadata/quarantined of the raised exception.
QUARANTINE_PUBLIC_MESSAGES = {
    "PIVEvaluatorFailed": "evaluator failure recorded by the environment (full record in the artifact)",
    "ToolCallError": "a tool raised; not attributable to the agent by class, quarantined",
    "Error": "unattributable framework error",
    "ModelError": "model client failure; not the policy's answer",
    "InvalidModelResponseError": "model client returned an invalid response",
    "EmptyModelResponseError": "model client returned an empty response",
    "OverlongPromptError": "prompt exceeded the model's context; a property of the task",
    "ToolError": "unattributable tool-layer error",
    "InfraError": "infrastructure error",
    "TunnelError": "infrastructure error (tunnel)",
    "SandboxError": "infrastructure error (sandbox)",
    "BrowserSandboxError": "infrastructure error (browser sandbox)",
}
UNCLASSIFIED_PUBLIC_MESSAGE = "unclassified error code; quarantined fail-closed"


def public_quarantine_message(code) -> str:
    return QUARANTINE_PUBLIC_MESSAGES.get(code, UNCLASSIFIED_PUBLIC_MESSAGE)


def partition_rollouts(outputs) -> tuple[list, list]:
    """(scored, quarantined): the package-owned collector adapter.

    Keys on the stable code in `error.error`, through ERROR_CONSEQUENCES, and
    fails closed: a code the table does not name is quarantined and recorded
    on the rollout under `piv_unclassified_code` so that it is loud, not
    silent. A protocol rejection has no error at all and stays counted.
    """
    scored, quarantined = [], []
    for out in outputs:
        (scored if classify_output(out) == COUNTED else quarantined).append(out)
    return scored, quarantined


def classify_output(out) -> str:
    """COUNTED or QUARANTINED for one rollout output.

    Two inputs, in order of trust. First the typed projection: the
    zero-weight monitor reads the evaluator-owned state record and lands in
    `RolloutOutput.metrics` under the package-owned key
    `piv/evaluator_failed`, so a 1.0 there is our own record surviving
    serialisation — no exception chain, no repr. Then the framework's exact
    top-level code through the table. The projection REFINES attribution; it
    is not the guard: with the monitor broken (the framework swallows a
    throwing monitor to 0.0) our marker's top-level code and every
    infrastructure or tool-wrapper code still quarantine. A `ToolCallError`
    with no projected record stays quarantined as an unattributed tool
    failure; safety never requires guessing its nested cause.
    """
    metrics = out.get("metrics") if isinstance(out, dict) else getattr(out, "metrics", None)
    if isinstance(metrics, dict) and metrics.get(METRIC_EVALUATOR_FAILED) == 1.0:
        if isinstance(out, dict) and isinstance(out.get("error"), dict):
            out["error"]["piv_code"] = PIVEvaluatorFailed.__name__
        return QUARANTINED
    err = out.get("error") if isinstance(out, dict) else getattr(out, "error", None)
    code = err.get("error") if isinstance(err, dict) else None
    consequence = ERROR_CONSEQUENCES.get(code)
    if consequence is None:
        consequence = QUARANTINED
        if isinstance(out, dict):
            out["piv_unclassified_code"] = code
    return consequence


def score_core(state) -> float:
    """The scorer proper, over the COMMITTED state. May raise; the adapter
    decides what that means.

    Takes the rollout state and nothing else: no text, no path, no task
    argument that could disagree with the committed identity. The last
    committed revision decides — a protocol-rejected last submission earns
    the public rejection consequence even if an earlier revision was valid.
    Finalisation hashes the deliverable ONCE through the verified-handle
    door and compares to the private receipt; it never parses again. A
    missing, altered or non-plain deliverable is a workspace failure — ours.

    Publication is transactional: the audit copy, the canonical artifact (or
    its removal) and the current-revision manifest all succeed before the
    score is recorded; a renderer or filesystem failure after semantic
    scoring is an evaluator failure for the attempt, never a score without
    its ledger. A second call for the same revision verifies the manifest
    and the artifact against the commitment and returns the recorded score;
    a different commitment under the same revision is refused.

    Module-level so a test can inject a fault at exactly this seam through the
    real environment, rather than fabricating framework state.
    """
    if "piv_committed" not in state:
        return 0.0                                    # nothing was ever committed: the agent's outcome
    committed = state["piv_committed"]
    # The adapter is the narrowest remaining injection point: a mutable dict
    # key. So the value is checked by EXACT runtime type (no subclass, no
    # dict lookalike), by episode (the receipt's rollout id must be this
    # rollout's), and by recomputation (`recheck` inside `score_committed`).
    # Anything else is an evaluator failure — never a score, never a zero.
    if type(committed) not in (CommittedSubmission, ProtocolRejected):
        raise RuntimeError(f"piv_committed holds {type(committed).__name__}, not a minted outcome")
    if committed.receipt.rollout_id != state.get("piv_rollout_id"):
        raise RuntimeError("the commitment belongs to another rollout")
    workspace = state.get("workspace", "")
    delivery = state.get("piv_delivery")
    if delivery is not None:
        return _refinalise(workspace, committed, delivery, state)
    raw = _read_public(workspace, LEDGER)              # one verified snapshot of what was received
    if raw is None:
        raise RuntimeError("the deliverable is missing or not a plain public file at finalisation")
    now = digests_of(raw)
    receipt = committed.receipt
    if (now["stored_bytes_digest"], now["logical_text_digest"]) != (receipt.stored_bytes_digest, receipt.logical_text_digest):
        raise RuntimeError("the deliverable no longer matches the committed receipt")
    if type(committed) is ProtocolRejected:
        variant, total, rendered, result = OUTCOME_PROTOCOL_REJECTED, Decimal("0"), None, None
        result_digest, completion = rejection_result_digest(committed), "incomplete"   # the public rejection consequence, counted
    else:
        result = score_committed(committed)
        result.verify()                                          # the typed result reproduces its own digest
        total, result_digest = result.total, result.result_digest
        completion = "complete" if result.complete else "incomplete"
        if result.renderable:
            variant, rendered = OUTCOME_DELIVERED, render_committed(committed).encode("utf-8")
        else:
            variant, rendered = OUTCOME_POLICY_BLOCKED, None
    delivery = _publish(workspace, committed, raw, rendered, variant, total, result_digest, completion)
    state["piv_delivery"] = delivery
    state["piv_result"] = result
    state["piv_score"] = float(total)
    return state["piv_score"]


def _refinalise(workspace: str, committed, delivery, state) -> float:
    """Idempotence, keyed by rollout, revision, input receipt and evaluation
    receipt: the manifest on disk and the artifact (or its absence) must
    match the record and the commitment, or the call is refused."""
    if type(delivery) is not DeliveryReceipt:
        raise RuntimeError("piv_delivery is not a delivery receipt")
    delivery.verify()
    receipt = committed.receipt
    if (delivery.rollout_id, delivery.committed_revision) != (receipt.rollout_id, receipt.committed_revision):
        raise RuntimeError("the delivery receipt belongs to another revision")
    if (delivery.input_stored_bytes_digest, delivery.input_logical_text_digest) != (
            receipt.stored_bytes_digest, receipt.logical_text_digest):
        raise RuntimeError("the delivery receipt was made for different input bytes")
    if delivery.evaluation_receipt_digest != committed.evaluation_receipt_digest:
        raise RuntimeError("the delivery receipt does not belong to this commitment")
    manifest_path = Path(workspace).resolve() / PUBLICATION_FILE
    if not _is_plain_file(manifest_path):
        raise RuntimeError("the publication manifest is missing at re-finalisation")
    published = DeliveryReceipt.from_json(manifest_path.read_text(encoding="utf-8"))
    if published != delivery:
        raise RuntimeError("the publication manifest does not match the delivery receipt")
    if delivery.renderable:
        raw = _read_public(workspace, LEDGER)
        if raw is None:
            raise RuntimeError("the delivered artifact is missing at re-finalisation")
        now = digests_of(raw)
        if (now["stored_bytes_digest"], now["logical_text_digest"]) != (
                delivery.artifact_stored_bytes_digest, delivery.artifact_logical_text_digest):
            raise RuntimeError("the delivered artifact no longer matches the delivery receipt")
    elif os.path.lexists(Path(workspace).resolve() / MUTABLE_PUBLIC_FILE):
        raise RuntimeError("a ledger is at the public path although the current revision has no artifact")
    # The recorded RESULT, not only the number: a deeply immutable typed
    # outcome whose canonical bytes reproduce the digest the receipt binds.
    result = state.get("piv_result")
    if type(committed) is ProtocolRejected:
        if result is not None or rejection_result_digest(committed) != delivery.score_result_digest:
            raise RuntimeError("the recorded rejection result does not match the delivery receipt")
    else:
        if type(result) is not ScoreOutcome:
            raise RuntimeError("the recorded result is not a ScoreOutcome")
        result.verify()
        if result.result_digest != delivery.score_result_digest:
            raise RuntimeError("the recorded score result does not match the delivery receipt")
        if result.environment_digest != committed.environment_digest \
                or result.reward_input_digest != committed.reward_input_digest \
                or result.evaluation_receipt_digest != committed.evaluation_receipt_digest:
            raise RuntimeError("the recorded score result belongs to another commitment or another rollout")
        if canonical_decimal(result.total) != delivery.score:
            raise RuntimeError("the recorded total does not match the delivery receipt")
        if ("complete" if result.complete else "incomplete") != delivery.completion:
            raise RuntimeError("the recorded completion status does not match the delivery receipt")
    recorded = state.get("piv_score")
    if recorded is None or float(Decimal(delivery.score)) != recorded:
        raise RuntimeError("the recorded score does not match the delivery receipt")
    return recorded


def _publish(workspace: str, committed, submitted: bytes, rendered: bytes | None, variant: str, total: Decimal,
             result_digest: str, completion: str) -> DeliveryReceipt:
    """The publication transaction. Order: audit copy of the received bytes
    (bounded, exclusive), then the public path — the canonical artifact
    replaced atomically and re-hashed through the verified-handle door, or
    REMOVED when the revision has no artifact — then the current-revision
    manifest, atomically, as the commit point. Any failure before the
    manifest leaves no manifest, so no reader can pair a score with a file."""
    root = Path(workspace).resolve()
    receipt = committed.receipt
    _archive_submission(receipt.rollout_id, receipt.committed_revision, submitted)
    target = root / MUTABLE_PUBLIC_FILE
    if os.path.lexists(target) and not _is_plain_file(target):
        raise RuntimeError("ledger target is not a plain regular file at delivery")
    if rendered is not None:
        _write_replace(root, target, rendered)
        after = _read_public(workspace, LEDGER)      # hash the final handle, never parse it
        if after is None or after != rendered:
            raise RuntimeError("the delivered artifact does not match what was rendered")
        artifact = digests_of(after)
        stored, logical = artifact["stored_bytes_digest"], artifact["logical_text_digest"]
    else:
        if os.path.lexists(target):
            os.unlink(target)                        # no current ledger, and the public path says so
        stored = logical = NO_ARTIFACT
    delivery = DeliveryReceipt(
        rollout_id=receipt.rollout_id, committed_revision=receipt.committed_revision, outcome=variant,
        input_stored_bytes_digest=receipt.stored_bytes_digest, input_logical_text_digest=receipt.logical_text_digest,
        evaluation_receipt_digest=committed.evaluation_receipt_digest, score_result_digest=result_digest,
        completion=completion,
        artifact_stored_bytes_digest=stored, artifact_logical_text_digest=logical,
        score=canonical_decimal(total),
    ).with_digest()
    _write_replace(root, root / PUBLICATION_FILE, delivery.to_json().encode("utf-8"))
    return delivery


def _write_replace(root: Path, target: Path, data: bytes) -> None:
    """An exclusive temporary regular file in the resolved workspace, then an
    atomic rename over the target. Nothing outside the workspace is opened."""
    fd, tmp = tempfile.mkstemp(prefix=".piv-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


_AUDIT_NAME = re.compile(r"^revision-(\d+)\.(beancount|oversize)$")
_ROLLOUT_ID = re.compile(r"^[0-9a-f]{32}$")
# The audit archive lives OUTSIDE every model-visible workspace root, under
# an evaluator-owned directory keyed by the evaluator-minted rollout id: no
# read tool, traversal, case variant, link or future tool inside a workspace
# can reach it, by construction rather than by omission from a manifest.
AUDIT_ROOT = Path(tempfile.gettempdir()) / "piv_audit"
MAX_AUDIT_ROLLOUTS = 64            # per run: oldest rollout archives are evicted first


def audit_dir(rollout_id: str) -> Path:
    if not isinstance(rollout_id, str) or not _ROLLOUT_ID.match(rollout_id):
        raise RuntimeError("audit rollout id is not an evaluator-minted id")
    return AUDIT_ROOT / rollout_id


def _plain_dir(path: Path) -> None:
    """Create `path` as a plain directory or refuse anything else there."""
    if os.path.lexists(path):
        st = os.lstat(path)
        if not stat.S_ISDIR(st.st_mode) or (getattr(st, "st_file_attributes", 0) & _REPARSE):
            raise RuntimeError(f"{path.name}: not a plain directory")
    else:
        os.mkdir(path)


def _archive_submission(rollout_id: str, revision: int, data: bytes) -> None:
    """Retain the received bytes for audit, contained: outside the
    workspace, a validated integer names the file, creation is exclusive (an
    existing symlink or file is a failure, not a target), oversize
    submissions keep only their digest, the rollout's archive is evicted to
    its revision and byte caps (oldest first) and the run's archive to its
    rollout cap."""
    if type(revision) is not int or not 1 <= revision <= 1_000_000:
        raise RuntimeError("audit revision is not a small positive integer")
    audit = audit_dir(rollout_id)
    _plain_dir(AUDIT_ROOT)
    _plain_dir(audit)
    if len(data) <= MAX_AUDIT_FILE_BYTES:
        name, payload = f"revision-{revision}.beancount", data
    else:
        name = f"revision-{revision}.oversize"
        payload = json.dumps({"stored_bytes_digest": digests_of(data)["stored_bytes_digest"],
                              "size": len(data)}, sort_keys=True).encode("utf-8")
    path = audit / name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        if _is_plain_file(path) and path.read_bytes() == payload:
            return                                   # a repeated attempt after a crash: the same bytes, already kept
        raise RuntimeError("an audit copy for this revision already exists with other content")
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    kept = []
    for entry in os.scandir(audit):
        match = _AUDIT_NAME.match(entry.name)
        if match and entry.is_file(follow_symlinks=False):
            kept.append((int(match.group(1)), entry.name, entry.stat(follow_symlinks=False).st_size))
    kept.sort()
    total = sum(size for _, _, size in kept)
    while kept and (len(kept) > MAX_AUDIT_REVISIONS or total > MAX_AUDIT_TOTAL_BYTES) and kept[0][0] != revision:
        old_revision, old_name, size = kept.pop(0)
        os.unlink(audit / old_name)
        total -= size
    rollouts = [(e.stat(follow_symlinks=False).st_mtime_ns, e.name) for e in os.scandir(AUDIT_ROOT)
                if e.is_dir(follow_symlinks=False) and _ROLLOUT_ID.match(e.name)]
    rollouts.sort()
    while len(rollouts) > MAX_AUDIT_ROLLOUTS and rollouts[0][1] != rollout_id:
        _, old = rollouts.pop(0)
        shutil.rmtree(AUDIT_ROOT / old, ignore_errors=True)


def _arguments_well_typed(tool, arguments: dict) -> bool:
    """Every bound argument has the annotated type: exact `int` (a bool is
    not an int here), `str`, or an annotation this check does not know,
    which passes. Unknown annotations are not silently `int`."""
    try:
        hints = typing.get_type_hints(tool)
    except Exception:
        hints = {}
    for name, value in arguments.items():
        expected = hints.get(name)
        if expected is int and (type(value) is not int):
            return False
        if expected is str and not isinstance(value, str):
            return False
    return True


def _calls_in_last_turn(state) -> list:
    """Tool names the LAST assistant turn asked for — executed or not. At the
    turn cap the framework never runs them, which is what
    `piv_turn_cap_submit_unexecuted` needs to know."""
    trajectory = state.get("trajectory") or []
    if not trajectory:
        return []
    step = trajectory[-1]
    completion = step.get("completion") if isinstance(step, dict) else getattr(step, "completion", None)
    names = []
    for message in completion or []:
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        if role != "assistant":
            continue
        calls = message.get("tool_calls") if isinstance(message, dict) else getattr(message, "tool_calls", None)
        for call in calls or []:
            if isinstance(call, str):
                try:
                    call = json.loads(call)
                except ValueError:
                    continue
            function = call.get("function") if isinstance(call, dict) else getattr(call, "function", None)
            name = (call.get("name") if isinstance(call, dict) else getattr(call, "name", None)) or \
                   ((function.get("name") if isinstance(function, dict) else getattr(function, "name", None)) if function is not None else None)
            if name:
                names.append(name)
    return names


def _last_turn_truncated(state) -> bool:
    """Whether the framework marked the last assistant turn truncated.

    Measured in verifiers 0.3.1: `MultiTurnEnv.add_model_response` computes
    `is_truncated = response.message.is_truncated or tokens["is_truncated"]`
    — the client's `finish_reason == "length"`, or the token accounting
    running past `max_seq_len` — and stores it on the `TrajectoryStep`.
    `state["is_truncated"]` is only written when a stop condition fires, so
    the step is the flag to read while the rollout is still running.

    Nothing here is evaluator state: it is a property of the agent's own
    message, and it decides only which of two fixed sentences is sent back.
    """
    trajectory = state.get("trajectory") or []
    if not trajectory:
        return bool(state.get("is_truncated"))
    step = trajectory[-1]
    # The STEP, not `state["is_truncated"]`, whenever there is one: the state
    # flag is the OR over every step and is only written when a stop
    # condition fires, so it would make one truncated turn colour the wording
    # of every later turn. The fallback above exists for a direct
    # `env_response` call with no trajectory, which is how a test simulates
    # the framework's flag.
    value = step.get("is_truncated") if isinstance(step, dict) else getattr(step, "is_truncated", None)
    return bool(value)


def _seam():
    """Late-bound reference to `score_core`, so patching the module attribute
    takes effect inside the reward closure."""
    return score_core


def evaluator_failed_projection(state) -> float:
    """1.0 when this rollout's score is a placeholder. Derived from the
    authoritative typed record, never from the diagnostics store."""
    return 1.0 if evaluator_failure(state) is not None else 0.0


def _projection_seam():
    """Late-bound, so a test can break the projection and prove the
    quarantine does not depend on it."""
    return evaluator_failed_projection


# --------------------------------------------------------------------------
# EVERY MODEL-FACING REPLY, AS A NAMED CONSTANT (Codex T48 §4)
#
# The episode contract digest used to bind only the fixed refusals and nudges,
# and its own docstring admitted the rest: the strings `read_file`, `grep` and
# `_public_report` BUILT — "no such file", the numbered-slice format, the
# continuation tail, the hit line, the stopped-at-N tail, the parse headings —
# were model-facing text the digest could not see, "kept in step by a manual
# EPISODE_CONTRACT_VERSION bump". That is the same generous seam earlier rounds
# kept finding: a changed reply changes the next model request, and a contract
# identity that cannot see it is asserting something it did not check.
#
# So every model-facing string in this module is a constant here, the tool
# bodies FORMAT them rather than writing prose, and `episode_contract()` puts
# all of them in the canonical view. `test_episode_contract` proves both
# halves: mutating any one constant moves the digest, and no function that
# talks to the model carries a model-facing literal of its own (the source is
# walked for string constants; only raised — never model-facing — text and a
# short, enumerated set of structural literals are allowed).
#
# The framework's default error formatter is `str(e)`, which would hand the
# model exception text — paths included; ours is PUBLIC_TOOL_ERROR.
# --------------------------------------------------------------------------

PUBLIC_TOOL_ERROR = "tool call rejected: check the argument names and types in the tool description"

#: `list_files`: one row per declared public file.
LIST_FILES_ROW = "{name}  ({lines} lines)"
#: `read_file` / `grep`: a name that is not in the public manifest. One
#: constant for both doors — a different wording per tool would tell the agent
#: which door it hit, which is a fact about our code, not about the world.
READ_NO_SUCH_FILE = "no such file: {path}"
#: `read_file`, sliced mode: the numbered line and the continuation tail.
READ_SLICE_LINE = "{number:5d}  {line}"
READ_MORE_LINES = "\n... [{remaining} more lines; use offset to continue]"
#: `_clip`: the tail on any reply that hit MAX_TOOL_OUTPUT_LINES.
CLIP_MORE_LINES = "\n... [{remaining} more lines not shown]"
#: `_clip_bytes`: the tail on any bounded reply that hit MAX_TOOL_OUTPUT_BYTES.
#: The line caps bound how many lines come back; this bounds how much.
CLIP_MORE_BYTES = "\n... [reply truncated at {limit} bytes]"
#: The aggregate observation budget is spent: every OBSERVING tool is answered
#: with this and reads nothing. `write_ledger` and `submit` still work, so an
#: agent that read too much can still deliver the books it already has — the
#: budget is a cost bound, never a reward penalty.
OBSERVATION_BUDGET_SPENT = ("read rejected: this episode's observation budget is spent; no more file "
                            "content will be sent — write_ledger and submit still work, so finish "
                            "from what you already have")
#: `grep`: the pattern refusal, a hit, the match-cap tail, and no matches.
GREP_BAD_PATTERN = "bad pattern: 1 to {max_pattern} characters of literal text"
GREP_HIT = "{name}:{number}: {line}"
GREP_STOPPED = "\n... [stopped at {limit} matches]"
GREP_NO_MATCHES = "no matches"
#: `_public_report`: what the boundary made of a ledger, in the model's words.
#: Never a parser exception and never an evaluator diagnostic.
REPORT_REJECTED = "REJECTED: {reason}: {detail}"
REPORT_LOADS_CLEANLY = "ledger loads cleanly — {events} events"
REPORT_FINDINGS_HEADER = "LEDGER READ, BOOKKEEPING FINDINGS:\n"
REPORT_FINDING = "{code}: {message}"
#: How many domain findings one report may carry. A bound on the reply, not on
#: the parse: the boundary may find hundreds and the model needs a handful.
MAX_REPORTED_FINDINGS = 10
#: The accepted-submit receipt, built from SUBMIT_ACCEPTED and the bound hash.
SUBMIT_DELIVERING = "{accepted}; delivering logical text {digest}"
#: The idempotent full-read receipt (Codex T48 §7, Q9). Sent INSTEAD of the
#: ledger when the agent asks for a complete read of a revision it has already
#: been given: it carries no ledger content, names the turn and revision the
#: content was sent on, and points at the two ways forward — use what you have,
#: or change it. `read_file` still answers every call, so the provider's
#: one-result-per-call requirement holds.
LEDGER_UNCHANGED_RECEIPT = (
    "ledger.beancount is unchanged since your complete read on turn {turn} (revision {revision}); "
    "it is not re-sent — use the content you already have, or write_ledger to change it")
#: The read-side envelope refusal (Codex T48 §6, Q9): the stored ledger is
#: outside the envelope a single whole read is sized for. Unreachable in
#: normal operation — the mounted world is verified before the episode and
#: `write_ledger` refuses anything larger — so this is defence in depth
#: against state corruption or a future bypass, and it is a bounded PUBLIC
#: message rather than an evaluator failure, because a tool argument must
#: never become our failure.
READ_OVER_ENVELOPE = ("read rejected: the stored ledger is outside the observation envelope and was "
                      "not returned; write a ledger inside the envelope with write_ledger")
TURN_MULTI_WRITE = "turn rejected: at most one write_ledger call per turn; nothing was written"
TURN_DUPLICATE_ID = ("turn rejected: duplicate tool call ids cannot be answered; "
                     "nothing was executed and the rollout ends here")
# The nudge. Fixed text, selected by code, identical for every task: it names
# the tools that already appear in the tool schema and says nothing about the
# world, the books or what is wrong with them. A turn that carries it is an
# ordinary turn against `max_turns`.
TURN_NO_TOOL = ("No tool was called. Read files with read_file/grep, write the corrected ledger "
                "with write_ledger, then call submit to finish.")
TURN_TRUNCATED_NO_TOOL = ("Your reply was cut off before any tool call. Keep replies short. Read files "
                          "with read_file/grep, write the corrected ledger with write_ledger, then call "
                          "submit to finish.")
SUBMIT_ACCEPTED = "submitted: the ledger as last written is final; the episode ends here"
# The two refusals that keep `submit` from ending an episode with nothing to
# deliver. Both name the ONE recovery — write a ledger that loads — and
# neither says anything about the world or the books.
SUBMIT_NOTHING_STORED = "nothing to submit: write the corrected ledger with write_ledger first"
SUBMIT_LAST_CANDIDATE_REFUSED = ("nothing to submit: the last write_ledger was refused by the ledger "
                                 "protocol; write a ledger that loads, then submit")
TURN_AFTER_SUBMIT = "turn rejected: submit already ended the episode; nothing was executed"
WRITE_AFTER_SUBMIT = "write rejected: submit already ended the episode; nothing was written"
WRITE_NOT_TEXT = "write rejected: content is not valid Unicode text; nothing was written"
# What the agent may write, and it is the OBSERVATION envelope, not the
# parser's (Codex T47 follow-up). `read_file` returns the ledger whole, so
# whatever is on disk is re-read in full on every later turn — and the input
# side of that is not bounded by the output ceiling. With the old cap of
# 2 x MAX_BYTES (1 MiB) an agent could write a megabyte once and then spend
# one completion token a turn re-reading it: O(n x turns) input the episode
# contract does not price, from a single tool argument.
#
# The ledger the task asks for is the mounted one plus a handful of repair
# entries — a measured maximum of 13,216 bytes over 82 worlds — so the
# observation envelope the mounted world must already fit (48,000 bytes,
# 3.5x that maximum) is a generous ceiling for a corrected one too. Refusing
# above it is a PUBLIC tool refusal, counted as the agent's outcome, so the
# rule that a tool argument must never become our failure still holds.
#
# ONE PREDICATE ON BOTH DOORS (Codex T48 §6, Q9). `write_ledger` refuses
# exactly `ledger_envelope_breach(content.encode("utf-8"))` — UTF-8 BYTES and
# logical LINES, the same call `_verify_public_world` and `load_environment`
# make — and `read_file` refuses a stored ledger that breaches it. The read
# refusal is therefore unreachable through anything the agent was allowed to
# write: it exists for state corruption, a migration or a future bypass, and
# it returns READ_OVER_ENVELOPE rather than the content, which is what keeps
# it from being a quarantine button.
#
# One route is retired by this: bytes between MAX_WRITE_BYTES and MAX_BYTES
# used to be stored and then refused by the parser's `envelope.bytes`. That
# rejection is still reachable — and still tested — through the boundary
# directly; it is simply no longer reachable through `write_ledger`, because
# nothing that large reaches the disk any more.
MAX_WRITE_BYTES = LEDGER_ENVELOPE_BYTES
WRITE_TOO_LARGE = (f"write rejected: the ledger must stay within the {MAX_WRITE_BYTES}-byte, "
                   f"{LEDGER_ENVELOPE_LINES}-line observation envelope; nothing was written")

# The rollout state, visible to `call_tool` (which the framework calls without
# it) for the duration of one `env_response`. A context variable so concurrent
# rollouts cannot see each other's state.
_PIV_STATE: contextvars.ContextVar = contextvars.ContextVar("piv_state", default=None)


# The released selector population per namespace and profile: indices
# 0 .. MAX_SELECTOR_INDEX-1. Finite by declaration so that "bounded-retry
# with zero failures over the released population" is a checkable claim, and
# so a request for train:99999999999999 is refused rather than minted.
MAX_SELECTOR_INDEX = 100_000


def load_environment(task_id: str = "bank_recon_001", **kwargs) -> vf.Environment:
    """The production composition root: ADMIT a selector, then build.

    The world graph is the only authority: the public files the agent reads,
    the planted predicates, the targets and the golden deliverable are all
    derived from it here, and the contract is loaded through the graph-derived
    door only. Admission (the release manifest) is this function's own work;
    everything after it is `environment_from_inputs`, which the release
    preflight calls directly on a freshly minted world so its offline gates
    never need a serving bypass."""
    # Two doors, both evaluator-side. A hand-authored world by its id, or a
    # generated one by a PRIVATE selector `<namespace>:<index>[:<profile>]`
    # that never reaches the model: the dataset row, the prompt and every
    # tool reply carry only the public id derived from the public bytes
    # (`graph.mint`), so nothing an agent sees regenerates the answer.
    try:
        if task_id in REGISTRY:
            world, task = REGISTRY[task_id]
            _bundle, inputs = derive_contract(world, task)
        else:
            from .graph.generate import DEFAULT_PROFILE, HARD_PROFILE, GenerationError
            from .graph.mint import NAMESPACES, SECRET_ENV, evaluator_secret, literal_provenance_leaks, mint
            parts = task_id.split(":")
            # The released selector population is FINITE: ASCII decimal
            # indices below MAX_SELECTOR_INDEX. `str.isdigit()` alone admits
            # Arabic-Indic and fullwidth digits that `int()` maps onto the
            # same world, so the selector-to-world map would not be
            # injective (Codex T42 §2, Q6; the tool-surface review).
            if (len(parts) not in (2, 3) or parts[0] not in NAMESPACES or not parts[1]
                    or not parts[1].isascii() or not parts[1].isdigit() or len(parts[1]) > 6
                    or int(parts[1]) >= MAX_SELECTOR_INDEX):
                raise InitializationFailure([f"unknown task {task_id!r}"])
            profile = {"standard": DEFAULT_PROFILE, "hard": HARD_PROFILE}.get(parts[2] if len(parts) == 3 else "standard")
            if profile is None:
                raise InitializationFailure([f"unknown profile in {task_id!r}"])
            secret = evaluator_secret()
            if secret is None:
                raise InitializationFailure([f"generated tasks are keyed: set {SECRET_ENV} (hex, >= 16 bytes) or "
                                             f"~/.piv/eval_secret on the evaluator; no unkeyed fallback exists"])
            try:
                minted = mint(parts[0], int(parts[1]), profile, secret=secret)
            except (GenerationError, ValueError) as exc:
                raise InitializationFailure([str(exc)])
            leaks = literal_provenance_leaks(minted)
            if leaks:
                raise InitializationFailure(["private provenance reached a public surface: " + "; ".join(leaks)])
            # The release manifest (Codex T43 §5): only a selector preflighted
            # under THIS evaluator key, at these component versions, with this
            # public id, is served. Development under a test secret says so
            # explicitly with PIV_DEV_UNMANIFESTED=1.
            from .graph.manifest import admit
            admitted, why = admit(secret, parts[0], int(parts[1]), profile.name, minted.inputs.task_id)
            if not admitted:
                raise InitializationFailure([f"release manifest: {why}"])
            inputs = minted.inputs
    except (ProjectionError, DerivationError) as exc:
        raise InitializationFailure([str(exc)])
    return environment_from_inputs(inputs, **kwargs)


def environment_from_minted(minted, **kwargs) -> vf.Environment:
    """EVALUATOR-SIDE ONLY. An environment over an already-minted world, with
    no manifest consulted and no selector parsed.

    The release preflight needs this and nothing else needs it (Codex T48 §7,
    answer 6). A preflight PRECEDES its own manifest by definition, so gating
    `golden_scores_one` through `load_environment` had a chicken-and-egg to
    solve, and the old solution was to point the workers at a manifest path
    that does not exist so `admit` took the development route. That works and
    it mixes two claims: it gates the world through a bypass production must
    never honour, and it proves nothing about the serving door.

    Two claims, two phases, instead. Phase one scores THIS object — the exact
    immutable world the record will be signed for — through the real tool loop
    and the real scorer, with the manifest out of the picture entirely. Phase
    two, after the manifest is signed, calls the real `load_environment` for
    every record with the development override off. Neither phase can be
    mistaken for the other in a summary.

    NOT a serving door: it takes a minted world an evaluator already holds, so
    it grants nothing a caller did not have. `load_environment` remains the
    only route from a selector to an environment, and it still admits.

    The provenance-leak audit runs HERE too, not only on the serving path.
    Without it a world whose private provenance reached a public byte would
    pass every offline gate, be signed into the manifest, and only be caught
    in phase two as "not served" — a leaking world with a signature on it.
    """
    from .graph.mint import literal_provenance_leaks

    leaks = literal_provenance_leaks(minted)
    if leaks:
        raise InitializationFailure(["private provenance reached a public surface: " + "; ".join(leaks)])
    return environment_from_inputs(minted.inputs, **kwargs)


def environment_from_inputs(inputs, **kwargs) -> vf.Environment:
    """The environment over one derived contract: audits, dataset, rubric.

    Split out of `load_environment` so the ADMISSION decision and the
    CONSTRUCTION of an environment are separable — `load_environment` is
    admission plus this, and the preflight's offline phase is this alone.
    Every audit below is unconditional either way.
    """
    # Every audit runs here, once, before any submission is accepted, and a
    # failure is a typed InitializationFailure — never a candidate score, a
    # cache entry or a trajectory. Only after they pass is the immutable
    # environment snapshot minted.
    contract = load_contract(inputs)
    public_files = dict(inputs.public_files)
    if set(public_files) != set(PUBLIC_FILES):
        raise InitializationFailure([f"the projection does not produce exactly the public manifest: "
                                     f"{sorted(set(public_files) ^ set(PUBLIC_FILES))}"])
    # The observation envelope, checked BEFORE the environment exists. The
    # ledger is read whole in one call; a world whose ledger does not fit is
    # not served at all, rather than served and then failed per rollout at
    # `_verify_public_world`. `tests/preflight_manifest.py` gates the released
    # population on the same predicate.
    breach = ledger_envelope_breach(public_files[LEDGER])
    if breach is not None:
        raise InitializationFailure([f"the projected ledger is outside the observation envelope: {breach}"])

    dataset = Dataset.from_list([{
        "question": inputs.prompt,
        "answer": inputs.task_id,
        "info": {"task_id": inputs.task_id},
    }])

    def ledger_reward(state, **_kwargs) -> float:
        """Framework-facing adapter. Never raises; records why when it cannot score.

        `verifiers` 0.3.1 catches any exception a reward function raises, logs
        it, and returns 0.0. So a bug in *our* scorer would be recorded as the
        agent's zero — indistinguishable from a bad submission, and negative
        training data the agent did nothing to earn. That is the failure
        `EvaluationFailure` exists to prevent, reintroduced one layer up.

        The framework will not give us a channel to raise through, so the
        adapter owns the boundary: the core is allowed to fail loudly (keeping
        the stack in internal tests), and this wrapper converts a failure into
        a *recorded* placeholder rather than a silent one. Two records, both
        evaluator-owned:

          - `state["error"]`, the framework's own per-rollout error slot, which
            reaches `RolloutOutput.error` so a collector can exclude the
            rollout without knowing anything about us;
          - a sidecar keyed by the workspace path, which the agent cannot
            choose (it is a mkdtemp the environment creates and overwrites on
            every tool call), for the `evaluator_failed` monitor below.

        Only `Exception` is caught — the class the framework swallows.
        Process-control exceptions keep their normal meaning.
        """
        if evaluator_failure(state) is not None:
            return 0.0  # sticky: a later valid write does not wash the marker away
        if state.get("piv_protocol_failure"):
            # The agent's terminal protocol violation: counted, not
            # quarantined, and it does NOT inherit the last committed
            # ledger's score — the task contract's terminal protocol score
            # is 0.0 whatever is on disk. Evaluator failure above takes
            # precedence: ours is never counted.
            return 0.0
        if not state.get("workspace"):
            return 0.0  # never wrote anything: an agent outcome, not ours
        try:
            return _seam()(state)
        except Exception as exc:
            record_evaluator_failure(state, "score_core", exc)
            return 0.0  # placeholder; the marker is what makes it excludable

    def evaluator_failed(state, **_kwargs) -> float:
        """Zero-weight monitor: 1.0 when this rollout's score is a placeholder.

        Derived from the authoritative marker, never from the diagnostics
        store, so a diagnostics outage cannot erase the signal. Lands in
        `RolloutOutput.metrics` under `piv/evaluator_failed` as the typed
        record's projection; the marker's top-level code in
        `RolloutOutput.error` is what forces quarantine even if this monitor
        itself breaks (witnessed).
        """
        return _projection_seam()(state)

    # The rubric names the metric after the function; the key is ours.
    evaluator_failed.__name__ = METRIC_EVALUATOR_FAILED

    def protocol_failed(state, **_kwargs) -> float:
        """Zero-weight: 1.0 when the rollout ended by the agent's terminal
        protocol violation. Counted in every aggregate (it is the agent's
        outcome); projected so replay can exclude a trajectory whose final
        assistant message cannot be answered one-result-per-call."""
        return 1.0 if state.get("piv_protocol_failure") else 0.0

    protocol_failed.__name__ = METRIC_PROTOCOL_FAILED

    def training_eligible_monitor(state, **_kwargs) -> float:
        """Zero-weight: 1.0 when this trajectory is structurally replayable —
        no terminal protocol violation, no evaluator failure."""
        return 0.0 if (state.get("piv_protocol_failure") or evaluator_failure(state) is not None) else 1.0

    training_eligible_monitor.__name__ = METRIC_TRAINING_ELIGIBLE

    def submitted(state, **_kwargs) -> float:
        """Zero-weight: 1.0 when the agent ended the episode itself, by an
        ACCEPTED `submit` — which now means it had written a ledger the
        boundary took. The complement is "the environment stopped it" — the
        turn cap, the no-tool-call limit, the truncation limit, or a terminal
        protocol violation — and telling those apart is the whole point of
        the episode contract."""
        return 1.0 if episode_phase(state) is EpisodePhase.TERMINAL else 0.0

    submitted.__name__ = METRIC_SUBMITTED

    def no_tool_turns(state, **_kwargs) -> float:
        """Zero-weight: how many assistant turns carried no tool call and
        were answered with the nudge. Under the old contract this number
        could only ever be 0 or 1, and a 1 ended the rollout."""
        return float(state.get("piv_no_tool_turns", 0))

    no_tool_turns.__name__ = METRIC_NO_TOOL_TURNS

    def no_tool_limit(state, **_kwargs) -> float:
        """Zero-weight: 1.0 when the episode ended on
        MAX_CONSECUTIVE_NO_TOOL_TURNS turns in a row without a tool call. A
        counted outcome, never a quarantine."""
        return 1.0 if state.get("piv_no_tool_limit_reached") else 0.0

    no_tool_limit.__name__ = METRIC_NO_TOOL_LIMIT

    def no_tool_truncated(state, **_kwargs) -> float:
        """Zero-weight: how many of the no-tool turns were cut off at the
        completion cap (the client's finish_reason == "length" or the
        harness sequence limit). Separates "reasoned past the budget" from
        "narrated instead of acting" in a batch — the two failure modes the
        first live runs showed, which the same counter would otherwise hide."""
        return float(state.get("piv_no_tool_truncated_turns", 0))

    no_tool_truncated.__name__ = METRIC_NO_TOOL_TRUNCATED

    def truncation_limit(state, **_kwargs) -> float:
        """Zero-weight: 1.0 when the episode ended on
        MAX_CONSECUTIVE_TRUNCATED_TURNS turns in a row cut off at the
        completion cap. Separate from `piv/no_tool_limit` because the fix is
        different: a truncating model needs a bigger per-turn cap or shorter
        replies, a narrating one needs to be told to call the tool."""
        return 1.0 if state.get("piv_truncation_limit_reached") else 0.0

    truncation_limit.__name__ = METRIC_TRUNCATION_LIMIT

    def turn_cap_no_submit(state, **_kwargs) -> float:
        """Zero-weight: 1.0 when the episode ran to `max_turns` without an
        accepted `submit`. The reward is unaffected — the last committed
        revision is scored either way — so this is the ONLY place the
        difference is visible, and it is what teaches a policy that the final
        call is part of the task."""
        return 1.0 if state.get("piv_turn_cap_no_submit") else 0.0

    turn_cap_no_submit.__name__ = METRIC_TURN_CAP_NO_SUBMIT

    def turn_cap_submit_unexecuted(state, **_kwargs) -> float:
        """Zero-weight: 1.0 when the episode ended at the cap with a `submit`
        on the last turn that the framework never ran (the budget for an
        executed submit is max_turns - 1)."""
        return 1.0 if state.get("piv_turn_cap_submit_unexecuted") else 0.0

    turn_cap_submit_unexecuted.__name__ = METRIC_TURN_CAP_SUBMIT_UNEXECUTED

    def submit_refused(state, **_kwargs) -> float:
        """Zero-weight: how many `submit` calls were answered "nothing to
        submit" — no candidate stored, or the last one refused at the
        boundary. Under the old contract each of these ENDED the episode on
        the untouched original; a non-zero count here is a rollout the old
        contract would have thrown away."""
        return float(state.get("piv_submit_refused", 0))

    submit_refused.__name__ = METRIC_SUBMIT_REFUSED

    def output_budget_exhausted(state, **_kwargs) -> float:
        """Zero-weight: 1.0 when the episode ended because it had spent the
        whole per-episode output ceiling. Distinct from the turn cap and from
        the truncation limit: an arm that exhausts the budget was measured at
        exactly MAX_EPISODE_OUTPUT_TOKENS, which is what makes two arms with
        different per-turn caps comparable."""
        return 1.0 if state.get("piv_output_budget_exhausted") else 0.0

    output_budget_exhausted.__name__ = METRIC_OUTPUT_BUDGET_EXHAUSTED

    def budget_accounting_invalid(state, **_kwargs) -> float:
        """Zero-weight: 1.0 when the provider's usage could not meter the
        output ceiling for this rollout — no usage, a nonsensical
        `completion_tokens`, more tokens than the request carried, or a
        cumulative total that went backwards.

        NOT an evaluator failure and NOT the agent's outcome: it says the
        rollout's token accounting is untrustworthy, so it must be excluded
        from any equal-budget claim (the per-turn cap still bounded every
        turn). A scripted client that reports no usage at all sets it, which
        is exactly right — such a run measures nothing about budgets."""
        return 1.0 if state.get("piv_budget_accounting_invalid") else 0.0

    budget_accounting_invalid.__name__ = METRIC_BUDGET_ACCOUNTING_INVALID

    def budget_accounting_suspicious(state, **_kwargs) -> float:
        """Zero-weight: 1.0 when a heuristic said this rollout's usage looks
        implausibly cheap for the characters it emitted.

        Deliberately NOT `budget_accounting_invalid` (Codex T48 §3, Q2). The
        characters-per-token floor is an empirical rule over an unknown
        tokenizer, and a replay arm changes the shape of the emitted text, so
        letting it decide validity would exclude one arm more often than
        another and bias the comparison. A measurement reports its table with
        and without these rows; nothing here is excluded silently."""
        return 1.0 if state.get("piv_budget_accounting_suspicious") else 0.0

    budget_accounting_suspicious.__name__ = METRIC_BUDGET_ACCOUNTING_SUSPICIOUS

    def observation_bytes(state, **_kwargs) -> float:
        """Zero-weight: UTF-8 bytes of every reply this environment returned
        to the model across the episode.

        The input side of the budget the output ceiling does not price. One
        whole ledger read is bounded by `LEDGER_ENVELOPE_BYTES`, and the
        idempotent full-read rule bounds what COMPLETE READS deliver in an
        episode at `LEDGER_ENVELOPE_BYTES x (stored revisions + 1)`; the
        sliced and grep replies are bounded per call instead. This is the
        measured total over all of them (Codex T48 §7, Q9)."""
        return float(state.get("piv_observation_bytes", 0))

    observation_bytes.__name__ = METRIC_OBSERVATION_BYTES

    def complete_reads(state, **_kwargs) -> float:
        """Zero-weight: how many `read_file(ledger)` calls returned CONTENT.

        Repeats of a revision already sent return a receipt and are not
        counted here, so this is the number of ledger revisions the model was
        actually shown — at most `revisions + 1`."""
        return float(state.get("piv_complete_reads", 0))

    complete_reads.__name__ = METRIC_COMPLETE_READS

    def ledger_receipts(state, **_kwargs) -> float:
        """Zero-weight: complete reads answered "unchanged" instead of resent.

        The other half of `piv/complete_reads`: together they say how often
        the model asked for a ledger it already had, which is what the
        idempotent rule is for and what a prompt change to it should move."""
        return float(state.get("piv_ledger_receipts", 0))

    ledger_receipts.__name__ = METRIC_LEDGER_RECEIPTS

    def observation_refused(state, **_kwargs) -> float:
        """Zero-weight: observing calls refused because the episode's
        observation budget was spent. Non-zero is a rollout that hit the
        aggregate input bound — a cost outcome, never an evaluator failure and
        never a reward change; write_ledger and submit kept working."""
        return float(state.get("piv_observation_refused", 0))

    observation_refused.__name__ = METRIC_OBSERVATION_REFUSED

    rubric = vf.Rubric(
        funcs=[ledger_reward, evaluator_failed, protocol_failed, training_eligible_monitor,
               submitted, no_tool_turns, no_tool_limit, no_tool_truncated,
               truncation_limit, turn_cap_no_submit, turn_cap_submit_unexecuted, submit_refused,
               output_budget_exhausted, budget_accounting_invalid, budget_accounting_suspicious,
               observation_bytes, complete_reads, ledger_receipts, observation_refused],
        weights=[1.0] + [0.0] * 18,
    )

    # The per-episode output ceiling is the environment's, not the caller's
    # sampling args: the arms of a measurement differ in their per-turn cap
    # and must still be compared at equal total output. A caller may override
    # it here, or call the setter later (tests/measure_budget.py does).
    ceiling = kwargs.pop("max_episode_output_tokens", MAX_EPISODE_OUTPUT_TOKENS)
    # The prompt is the environment's, not the caller's: it DISCLOSES the
    # turn, no-tool and output budgets, and the episode contract digest
    # attests exactly that text. A caller's own system prompt would leave the
    # digest asserting something the model was never told — the same defect
    # the fail-closed check in `set_max_total_completion_tokens` catches one
    # layer down. Refused by name rather than by the "multiple values for
    # keyword argument" TypeError that used to come out of here.
    if "system_prompt" in kwargs:
        raise InitializationFailure([
            "system_prompt is the environment's: it discloses the episode budgets and the contract "
            "digest attests it. Change SYSTEM_PROMPT and bump EPISODE_CONTRACT_VERSION instead."])

    env = BeancountLedgerEnv(
        dataset=dataset,
        system_prompt=SYSTEM_PROMPT,
        rubric=rubric,
        max_turns=MAX_TURNS,
        contract=contract,
        public_files=public_files,
        **kwargs,
    )
    env.set_max_total_completion_tokens(int(ceiling))
    return env
