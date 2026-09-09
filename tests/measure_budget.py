"""M2: the token budget, measured — real model, real environment, generated tasks.

    python tests/measure_budget.py --model nvidia/nemotron-3-ultra-550b-a55b --arm A \
        --selectors train:0 train:1 train:2 train:0:hard train:1:hard train:2:hard

One rollout per selector, sequentially, through `load_environment(selector)`
(keyed: the evaluator secret must be configured), through the environment's
real `evaluate()` door. For each rollout the framework's own accounting is
reported — prompt and completion tokens summed over every turn
(`token_usage`), a per-turn breakdown, turns, tool calls by name, reward, stop
condition — and the run is written to reviews/budget_<model>_<date>.json with
a markdown summary beside it. Nothing here scores anything itself; the reward
is the environment's.

The contract (PLAN §6) says ~50K tokens a rollout and 25 turns. The prompt
side of a tool loop grows with every turn because the whole conversation is
re-sent, so the number that matters is the SUM over turns, which is what the
framework's `Usage` carries.

ARMS: `--arm {A,B1,B2,B3}` sets a preset (per-turn
max_tokens, reasoning replay) — A=8000/on, B1=16000/on, B2=8000/off,
B3=16000/off — that `--max-tokens`/`--no-reasoning-replay` still override.
Reasoning replay is a client-side history-serialization policy: the
ORIGINAL trajectory kept in rollout state always carries every
model's `reasoning_content` (audit evidence, untouched); only the PROJECTION
sent to the provider on later turns can omit it (`make_client_cls`'s
`to_native_prompt`).

ARTIFACT BINDING: the delivered ledger is bound from THIS
rollout's own state — `out["workspace"]`, `out["piv_phase"]` and the
`delivery.json` the scorer published inside that same workspace — never by
scanning `%TEMP%` for the newest `beancount_env_*` directory. See
`bind_artifact()`.

THE MEASUREMENT SIDE:

  - `tool_call_chars()` — the plausibility floor now counts the SERIALIZED
    TOOL-CALL ARGUMENTS, not only visible content and reasoning. A tool-only
    turn carrying a 48,000-character `write_ledger` argument and reporting
    one completion token used to pass; it is `INVALID/usage_implausible`
    now.
  - EXACT wire cardinality: `len(wire_caps) == len(per_turn) ==
    len(request_caps)` for the SURVIVING attempt. A LONGER wire sequence is
    `INVALID/extra_wire_request` — potentially unaccounted spend, not
    harmless surplus evidence. And `ClientConfig(..., max_retries=0)`: the
    library's own default is TEN SDK retries inside `AsyncOpenAI`
    (`verifiers.legacy.utils.client_utils.setup_openai_client` passes
    `config.max_retries` straight into the SDK constructor, and
    `ClientConfig.max_retries` defaults to 10) — a late 200 the SDK
    discards is billed by the provider and invisible to every layer above
    it. `PacedClient` additionally records EVERY attempt of its own 429
    pacing loop in `row["requests"]`.
  - `validate_row()` — ONE pure validator that re-derives every
    predicate from an ARCHIVED row's own fields. `one_rollout` runs it on
    the row it just wrote; `tests/arm_table.py` runs it on every row it
    reads and never trusts a stored `budget_accounting` string.
THE EVIDENCE SIDE:

  - the shared PROVIDER-WINDOW LEDGER (`--window-ledger`): every HTTP attempt
    is appended to one file per schedule, the 6-second pacing interval is
    enforced against ITS last entry for the provider rather than against this
    process's own memory (each scheduled cell is a fresh subprocess, so that
    memory is always empty at the boundary that matters), and a 429 archives
    the OBSERVED trailing-60-second window it was refused in — split into
    this cell's own contribution and the carry-over from the cell before.
  - structured provider errors (`provider_error_fields`): HTTP status, the
    provider's own error code/type, the redacted message and the rate-limit
    headers `openai.APIStatusError.response` exposes, on every failed
    attempt, plus `estimated_request_tokens` (chars/4 over the exact native
    payload) — the only size evidence a rejected request has, since a 429
    bills nothing.
  - `capability_probe` / `probe_configuration`: one two-turn tool-call
    exchange per replay policy, whose SECOND request replays the assistant
    tool call — the payload shape that produces Mistral's 422
    `extra_forbidden` and Gemini 3.x's missing `thought_signature`. Run
    before a schedule starts, so an incompatible configuration is refused
    whole rather than discovered as an arm-shaped hole in the panel.

  - `replay_contract_digest()` — the provider-bound REPLAY policy
    (retained/dropped assistant fields, the None-as-absent rule, continuation
    fields, tool-call ordering, reasoning replay on/off, the provider
    projection, the concrete client/library versions) has its own identity,
    separate from `episode_contract_digest()`. Rows carrying different
    replay digests are never pooled in one condition.

The API key is read from HKCU\\Environment (NVIDIA_API_KEY) into this
process's environment for the framework client to pick up by name; it is
never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import re
import statistics
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")     # development: a test secret has no release manifest

# Providers are OpenAI-compatible chat-completions endpoints. The key is
# read from the environment or from HKCU\Environment (never printed) and
# handed to the client only. `configure_provider` selects one; the module
# globals BASE_URL / KEY_VAR / PROVIDER are what every caller reads.
PROVIDERS = {
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),            # free tier: 8K tokens/min PER REQUEST -> rollouts impossible
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),           # Experiment plan: ~500K TPM, 1B/month, 1 rps (verify in console)
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),  # free: 2.5 Flash 10 RPM / 250K TPM / 500 RPD
    "zai": ("https://api.z.ai/api/paas/v4", "ZAI_API_KEY"),                 # GLM-4.5/4.7-Flash free, 1 concurrent, 128-200K context
    "cohere": ("https://api.cohere.ai/compatibility/v1", "COHERE_API_KEY"), # trial key: 20 req/min, 1,000 calls/month
}
PROVIDER = "nvidia"
NVIDIA_BASE_URL = PROVIDERS["nvidia"][0]      # kept for older imports
BASE_URL = NVIDIA_BASE_URL
KEY_VAR = PROVIDERS["nvidia"][1]


def configure_provider(name: str | None = None, base_url: str | None = None,
                       key_var: str | None = None) -> tuple[str, str, str]:
    """Select the endpoint: a named preset, optionally overridden by an explicit
    base URL and/or key variable name. Returns (provider, base_url, key_var)
    and sets the module globals the scripts read."""
    global PROVIDER, BASE_URL, KEY_VAR
    name = name or PROVIDER
    if name not in PROVIDERS and base_url is None:
        raise SystemExit(f"unknown provider {name!r}; known: {sorted(PROVIDERS)} (or pass --base-url)")
    preset_url, preset_key = PROVIDERS.get(name, (None, None))
    PROVIDER = name
    BASE_URL = base_url or preset_url
    KEY_VAR = key_var or preset_key or f"{name.upper()}_API_KEY"
    return PROVIDER, BASE_URL, KEY_VAR
BUDGET_TOKENS = 50_000
BUDGET_TURNS = 25

# Arm presets: (per-turn max_tokens, reasoning replay).
ARM_PRESETS = {
    "A": (8000, True),
    "B1": (16000, True),
    "B2": (8000, False),
    "B3": (16000, False),
}

# The state fields a rollout needs to bind its own artifact and account for
# every turn, requested from `env.evaluate(..., state_columns=...)`. All are
# JSON-primitive (str/int/float/StrEnum/list) except `trajectory`, which the
# framework's own `state_to_output` exempts from the JSON gate (it carries
# live `Response`/`Usage` objects, read in-process here — never serialized by
# us until the whole row is archived). `piv_committed` / `piv_delivery` /
# `piv_result` are deliberately NOT requested: they are plain dataclasses
# (`CommittedSubmission`, `DeliveryReceipt`, `ScoreOutcome`), not Pydantic
# models, so `state_to_output`'s JSON gate rejects them outright — asking for
# them would raise on every rollout. What is needed from `piv_delivery` (the
# artifact's own digests) is read straight from the `delivery.json` the
# scorer already publishes inside `out["workspace"]` — the same file
# `bind_artifact()` uses instead of scanning temp directories.
#
# `piv_request_max_tokens` is MANDATORY now (the transitional "optional
# column" fallback this file used to carry for it is gone). It already
# exists in the package (committed before
# this rewrite), so no fallback is needed for it: a rollout whose state
# somehow lacks the sequence, or whose sequence does not cover every turn,
# is not silently archived as an otherwise-valid row with `None` — it gets
# `budget_accounting = "INVALID/no_request_caps"` and is excluded from any
# equal-budget table (`compute_budget_accounting` below), though it stays in
# the archive, labelled.
BASE_STATE_COLUMNS = [
    "workspace", "piv_rollout_id", "piv_revision", "piv_phase",
    "piv_turns_rejected", "piv_submit_refused", "piv_score",
    "piv_logical_text_digest", "piv_stored_bytes_digest", "piv_submitted_text_digest",
    "piv_candidate_digest", "piv_submitted_digest",
    "piv_request_max_tokens",
    "trajectory",
]
# Owned by the OTHER builder's concurrent edit to beancount_ledger.py
# (`piv_budget_accounting_invalid`,
# `piv_episode_contract_digest`, `episode_contract_digest()`,
# `EPISODE_CONTRACT_VERSION`). Requested best-effort: `state_to_output` only
# raises `ValueError` when a requested column EXISTS in state but is not yet
# JSON-serializable — a column that is simply ABSENT comes back as plain
# `None` with no exception (verified against `verifiers.legacy.utils.
# save_utils.state_to_output`) — so `_run_evaluate` only needs to retry
# without these two names in that transitional not-yet-serializable case,
# never merely because they have not landed yet. Every field sourced from
# them is read with `.get()` below and recorded as `None` until the merge.
#
# The T48 additions are owned by the package side too and are requested the
# same way, read with `.get()` and recorded as `None` until they land:
# `piv_budget_accounting_suspicious` (the env's own SUSPICION code, the
# counterpart of the split between a hard-invalid theorem and an
# anomaly band), `piv_complete_reads` and `piv_observation_bytes` (the
# repeated-whole-read and aggregate-observation counters the reviewer
# asked for -- the measurement side can only bound them from the archive, the
# package can count them exactly), and `piv_library_versions` (the serving
# host's own view of the packages the replay contract is bound to; recorded
# beside this process's `library_versions()` so a mismatch between the two is
# visible rather than assumed away).
OPTIONAL_STATE_COLUMNS = ["piv_budget_accounting_invalid", "piv_budget_accounting_detail",
                          "piv_episode_contract_digest", "piv_budget_accounting_suspicious",
                          "piv_complete_reads", "piv_observation_bytes", "piv_library_versions",
                          # episode contract 4: the calls whose `arguments` were not a JSON object,
                          # raw and bounded. Before the contract-4 rewrite these episodes did not
                          # reach the archive at all -- the provider refused every later request and
                          # the rollout was recorded as a provider failure.
                          "piv_rejected_calls"]

# The CLOSED set of `budget_accounting` status codes (adversarial-review
# follow-up): `compute_budget_accounting` returns "VALID" or
# "INVALID/<code>" where <code> is one of these OUR-OWN structural/usage
# codes, or `env_<code>` where <code> is one of ENV_BUDGET_ACCOUNTING_CODES
# verbatim from the OTHER builder's `state["piv_budget_accounting_invalid"]`
# (a code now, not a bool/free string), or the fixed fallback
# `env_unrecognized` for a code that package version does not know about —
# never an arbitrary interpolated string. See `compute_budget_accounting`'s
# docstring for what each code means and the exact check order.
BUDGET_ACCOUNTING_CODES = (
    "no_request_caps", "caps_turns_mismatch", "no_turns", "framework_retry",
    "usage_missing", "usage_not_integer", "usage_total_missing",
    "completion_exceeds_cap", "ceiling_exceeded", "cumulative_mismatch",
    "wire_caps_incomplete", "extra_wire_request", "wire_cap_mismatch",
    "request_count_mismatch",
)
# SUSPICIOUS is not INVALID. A generic characters-per-
# token heuristic is not a validity theorem: character/token ratios depend
# on the tokenizer, the language, Unicode, code, serialized tool calls and
# repetition, and a REPLAY ARM changes the shape of emitted content — so a
# heuristic hard-invalidation would exclude one arm more often than another
# and bias the very comparison it guards. `usage_implausible` therefore
# names a SUSPICIOUS row (`row["budget_accounting_suspicious"]`), never an
# invalid one, and `tests/arm_table.py` prints every table twice, with and
# without the suspicious rows. It would become a HARD check only against a
# verified provider/model tokenizer over the exact provider-bound payload,
# which no endpoint in this experiment's reach exposes.
BUDGET_SUSPICION_CODES = ("usage_implausible", "window_ledger_gap")
# The env's own closed set (state["piv_budget_accounting_invalid"], a code
# now rather than a bool/free string) -- verbatim from the coordinator.
# `usage_implausible` is the env's own name for the SAME heuristic and is
# routed to the suspicion bucket here rather than to INVALID, so the two
# sides agree about what is a theorem and what is an anomaly band.
ENV_BUDGET_ACCOUNTING_CODES = (
    "usage_absent", "usage_not_integer", "completion_exceeds_cap",
    "cumulative_decreased", "usage_zero_on_spoken_turn",
)
ENV_BUDGET_SUSPICION_CODES = ("usage_implausible",)
ENV_UNRECOGNIZED_CODE = "unrecognized"
# Every string `compute_budget_accounting` can ever return -- pinned so a
# test can assert "no other status leaked out" over a battery of scenarios.
ALL_BUDGET_ACCOUNTING_STATUSES = (
    ("VALID",)
    + tuple(f"INVALID/{c}" for c in BUDGET_ACCOUNTING_CODES)
    + tuple(f"INVALID/env_{c}" for c in ENV_BUDGET_ACCOUNTING_CODES)
    + (f"INVALID/env_{ENV_UNRECOGNIZED_CODE}",)
)
ALL_BUDGET_SUSPICION_CODES = (
    BUDGET_SUSPICION_CODES
    + tuple(f"env_{c}" for c in ENV_BUDGET_SUSPICION_CODES)
    + (f"env_{ENV_UNRECOGNIZED_CODE}",)
)
# The conservative characters-per-completion-token floor behind
# `usage_implausible`: twice the cheapest plausible encoding. Diagnostic,
# never a validity gate (see BUDGET_SUSPICION_CODES).
CHARS_PER_TOKEN_FLOOR = 8

# The instrument's own attempt nonce, stamped into the rollout state by
# `PacedClient`. NOT model-facing: it is never a requested
# state column, never rendered into a prompt, and never leaves the row's
# `requests` log. `Environment.run_rollout` builds a FRESH state dict per
# framework attempt, so one nonce == one attempt, by construction.
ATTEMPT_NONCE_KEY = "piv_measurement_attempt_nonce"


def load_key_from_registry(key_var: str | None = None) -> None:
    """Put the provider key into the environment for the client. Never
    printed or included in an exception message — only the VARIABLE NAME
    (never a secret itself) appears, and the phrase "variable <name> is not
    set" appears exactly once."""
    key_var = key_var or KEY_VAR
    if os.environ.get(key_var):
        return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
            value, _ = winreg.QueryValueEx(handle, key_var)
    except OSError:
        raise SystemExit(f"variable {key_var} is not set (checked the environment and HKCU\\Environment) — "
                         f"run `setx {key_var} <key>` in a terminal, then open a new one")
    os.environ[key_var] = value


# Redacts anything that looks like a live API key before it reaches a repo
# log file (adversarial-review follow-up): `run_arms.py` writes a failed
# subprocess's stderr tail into `reviews/arms_<date>.log`, which is
# committed to the repo -- a key echoed into a traceback (a misconfigured
# client, a provider error page) must never land there literally. Matches
# the common live-key prefixes across the providers this file's own
# PROVIDERS preset table and provider_probe.py know about (groq, nvidia,
# google/gemini, any openai-shaped sk- key) plus enough trailing characters
# that a partial/truncated key is still caught.
SECRET_PATTERN = re.compile(r"(gsk_|nvapi-|AIza|sk-)[A-Za-z0-9_-]{8,}")


def redact_secrets(text: str) -> str:
    if not text:
        return text
    return SECRET_PATTERN.sub(lambda m: m.group(1) + "***REDACTED***", text)


def write_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write `text` to `path` so that a reader NEVER sees a partial file.

    The row file is rewritten after every selector, and `tests/run_arms.py`
    decides a scheduled cell is done by looking at it. A process killed
    mid-`write_text` used to leave truncated JSON behind: `run_arms` saw a
    file and skipped the cell forever, while `arm_table.load_rows` could not
    parse it and dropped it with a warning — the cell was neither re-run nor
    counted, and the panel silently lost it. Writing to a sibling temporary
    file and `os.replace`-ing it makes the swap atomic on Windows and POSIX
    alike, so the destination is always either the previous complete file or
    the new complete one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# THE PROVIDER WINDOW LEDGER. One file, shared by every cell of
# a schedule, recording every HTTP attempt this experiment makes against a
# provider: when it was made, how large the request was, and what the provider
# billed. Two things depend on it, and neither can be answered from inside one
# cell's own process:
#
#   1. PACING ACROSS CELLS. Every scheduled cell is a fresh subprocess, so
#      `PacedClient._last` resets to 0 at its start and the first request of
#      cell n+1 could follow the last request of cell n by milliseconds. The
#      provider's rolling window does not reset between our processes. Pacing
#      is therefore enforced against the LEDGER's last entry for the provider,
#      not against this process's own memory.
#   2. WHAT ACTUALLY EXHAUSTED THE WINDOW. The previous 429 rule asked whether
#      the largest request, HYPOTHETICALLY repeated every `min_interval`
#      seconds for a minute, would reach the provider's tokens-per-minute
#      limit. That is not a measurement of anything: a single 120K request
#      does not consume a 356K minute, and a small request arriving after
#      several large ones may well be the one the arm's own traffic pushed
#      over. The ledger answers the real question — in the sixty seconds
#      before this rejection, how many tokens did the experiment send to this
#      provider, and how many of them were THIS cell's?
#
# The file is JSON Lines, appended under an exclusive lock, and tolerant of a
# truncated final line (a killed process). It carries NO prompt content and no
# secret: timestamps, model ids, token counts, a cell tag and a session id.
# ---------------------------------------------------------------------------

WINDOW_SECONDS = 60.0
#: Bytes per token for the ESTIMATE of a request the provider rejected. A 429
#: carries no usage, so the only size evidence for the rejected request is the
#: payload the client was about to send. Four characters per token is the
#: conventional English/JSON floor; it is an ESTIMATE and every field computed
#: from it is named `estimated_*` so no reader mistakes it for billed usage.
CHARS_PER_ESTIMATED_TOKEN = 4
_LEDGER_LOCK_TIMEOUT = 10.0
_LEDGER_LOCK_STALE = 60.0


_RUNTIME_IDENTITY: dict | None = None


def runtime_identity() -> dict:
    """`{runtime_head, execution_tree_digest, instrument_identity_version,
    runtime_environment_digest, runtime_environment_identity_version}` for the
    checkout AND the interpreter that are EXECUTING, stamped on every archived
    row. The sealed `instrument_commit` says what was
    registered; this says what ran, and the two are deliberately separate
    fields — under the git-path contract a run may legitimately happen at a
    later commit, as long as nothing under the execution paths changed.

    Computed once per process and cached: a row-level fact must not cost a
    site-packages walk per row. The per-cell VERIFICATION below deliberately
    does NOT use this cache."""
    global _RUNTIME_IDENTITY                                              # noqa: PLW0603
    if _RUNTIME_IDENTITY is None:
        try:
            import schedule_arms as _SA                                    # noqa: PLC0415 -- lazy, no cycle
            _RUNTIME_IDENTITY = _SA.instrument_identity()
        except Exception as exc:                                           # noqa: BLE001
            _RUNTIME_IDENTITY = {"runtime_head": None, "execution_tree_digest": None,
                                 "instrument_identity_version": None,
                                 "runtime_environment_digest": None,
                                 "runtime_environment_identity_version": None,
                                 "note": f"unavailable: {type(exc).__name__}"}
    return dict(_RUNTIME_IDENTITY)


# ---------------------------------------------------------------------------
# PER-CELL AND PER-REQUEST INSTRUMENT VERIFICATION
#
# "The startup witness authenticates the tree before the session. It does not
# freeze the tree. The schedule lock serializes executors; it does not prevent
# a file edit. Every cell is a new subprocess, so a file changed after startup
# can affect later cells."
#
# His concrete bad execution: pass startup, change an executable file before a
# later cell, let that fresh subprocess write a row bearing the changed digest,
# and render the table. So the digests are re-checked HERE, in the process that
# is about to spend the provider call:
#
#   BEFORE REQUEST 1 OF THE CELL   both digests. Measured on this machine:
#                                  execution tree ~79 ms (320 files, 4.6 MB);
#                                  runtime environment (17,607 files, 405 MB,
#                                  112 distributions) ~2 s with the venv fully
#                                  in the page cache, ~15-20 s when it is
#                                  partly evicted, and ~400-450 s on the first
#                                  cold read, when Defender scans every file.
#   BEFORE EVERY PROVIDER REQUEST  the execution tree, ~79 ms — negligible
#                                  against a model call, and re-walked for
#                                  every attempt of the pacing loop.
#   AFTER THE LAST WRITE           both digests again, before the cell is
#                                  allowed to be complete.
#
# His closure 3 asks for BOTH digests before every provider call. An
# environment walk per REQUEST is 2 s at the very best and 15-20 s in ordinary
# conditions — 50 s to 8 minutes per 25-turn rollout, and days over a 144-cell
# panel — so the environment is verified per CELL (two walks a cell: 10 minutes
# to 1.2 hours over the panel, against a 6-7 hour experiment) and the tree per
# REQUEST. THE RESIDUAL, stated narrowly: a site-packages
# byte edit landing between this cell's opening and closing environment checks
# can affect the requests of THAT ONE CELL. It cannot escape detection — the
# closing check refuses the cell, the row is never written and the executor
# stops the session — and it cannot reach any later cell, whose own opening
# check runs first. Repository content has no such window at all.
#
# A mismatch means: NO provider call, no row, exit `INSTRUMENT_DRIFT_EXIT`.
# `tests/run_arms.py` journals `instrument_drift` fail-closed and stops the
# session, because a drifted instrument invalidates everything after it.
# ---------------------------------------------------------------------------

#: The exit code a cell uses to tell the executor that the instrument it was
#: about to run on is not the sealed one.
INSTRUMENT_DRIFT_EXIT = 6

#: What the executor passed down from the sealed contract. Empty for a bare,
#: unscheduled `measure_budget.py` run, which verifies nothing because it
#: registered nothing.
_SEALED_INSTRUMENT: dict = {}


class InstrumentDrift(BaseException):
    """The executing instrument is not the sealed one.

    A `BaseException`, deliberately: it is raised immediately before a provider
    request, and the framework's own `except Exception` handlers — including
    this module's attempt logger — must not be able to turn it into a recorded
    provider failure, a retry, or a row. Nothing after it may run.
    """


def set_sealed_instrument(execution_tree_digest=None, runtime_environment_digest=None,
                          instrument_identity_version=None,
                          runtime_environment_identity_version=None) -> dict:
    """Arm the per-cell/per-request verification from the sealed contract.
    Called once by `main()` from the values `tests/run_arms.py` passes down."""
    global _SEALED_INSTRUMENT                                              # noqa: PLW0603
    _SEALED_INSTRUMENT = {k: v for k, v in {
        "execution_tree_digest": execution_tree_digest,
        "runtime_environment_digest": runtime_environment_digest,
        "instrument_identity_version": instrument_identity_version,
        "runtime_environment_identity_version": runtime_environment_identity_version,
    }.items() if v is not None}
    return dict(_SEALED_INSTRUMENT)


def sealed_instrument() -> dict:
    return dict(_SEALED_INSTRUMENT)


def verify_instrument(scope: str = "request", sealed: dict | None = None) -> list[str]:
    """Every way the instrument executing RIGHT NOW differs from the sealed
    one, named. Empty means it is the sealed instrument.

    `scope="request"` re-walks the execution tree only; `scope="cell"` also
    re-walks the runtime environment, with the cache DISABLED — a cached
    environment digest would make the closing check of a cell agree with its
    own opening check by construction.

    An unarmed process (no sealed values) returns no mismatch: a bare
    `measure_budget.py` run registered nothing and has nothing to betray.
    """
    sealed = _SEALED_INSTRUMENT if sealed is None else sealed
    if not sealed:
        return []
    problems: list[str] = []
    try:
        import schedule_arms as _SA                                        # noqa: PLC0415 -- lazy, no cycle
    except Exception as exc:                                               # noqa: BLE001
        return [f"the instrument identity module could not be imported: {type(exc).__name__}: {exc}"]

    want_version = sealed.get("instrument_identity_version")
    if want_version is not None and want_version != _SA.INSTRUMENT_IDENTITY_VERSION:
        problems.append(f"instrument_identity_version={_SA.INSTRUMENT_IDENTITY_VERSION!r} "
                        f"(sealed {want_version!r})")
    want_tree = sealed.get("execution_tree_digest")
    if want_tree is not None:
        actual = _SA.execution_tree_digest()
        if actual != want_tree:
            problems.append(f"execution_tree_digest={actual!r} (sealed {want_tree!r}) — the repository "
                            f"content executing now is not the content that was sealed")
    if scope == "cell":
        want_env_version = sealed.get("runtime_environment_identity_version")
        if want_env_version is not None and want_env_version != _SA.RUNTIME_ENVIRONMENT_IDENTITY_VERSION:
            problems.append(f"runtime_environment_identity_version="
                            f"{_SA.RUNTIME_ENVIRONMENT_IDENTITY_VERSION!r} (sealed {want_env_version!r})")
        want_env = sealed.get("runtime_environment_digest")
        if want_env is not None:
            actual = _SA.runtime_environment_digest(use_cache=False)
            if actual != want_env:
                problems.append(f"runtime_environment_digest={actual!r} (sealed {want_env!r}) — the "
                                f"installed distributions or the interpreter executing now are not the "
                                f"bytes that were sealed")
    return problems


def require_instrument(scope: str, where: str) -> None:
    """Verify, or raise `InstrumentDrift` — the form every caller on the
    request path uses, so that a mismatch can never be a logged warning."""
    problems = verify_instrument(scope)
    if problems:
        raise InstrumentDrift(f"INSTRUMENT DRIFT ({where}): " + "; ".join(problems))


def estimate_request_tokens(prompt, tools=None, sampling_args=None) -> int:
    """A conservative size estimate, in tokens, for the request ABOUT TO BE
    SENT — `len(serialized) // 4` over the native prompt plus the tool schema.

    The 429 that rejects a request bills nothing, so `billed_input_tokens` is
    `None` for exactly the attempt whose size the rolling-window question
    needs. The client holds the native payload at that moment; this is the
    only place it can be measured at all."""
    try:
        blob = json.dumps([prompt, tools, sampling_args], sort_keys=True, default=str, ensure_ascii=False)
    except (TypeError, ValueError):                                        # noqa: BLE001
        blob = str(prompt) + str(tools) + str(sampling_args)
    return len(blob) // CHARS_PER_ESTIMATED_TOKEN


#: Whether a request the provider REFUSES consumes token or
#: request quota is not documented by Mistral, and neither is the admission
#: estimate it would be judged against. Sealed as an explicit unknown, and
#: read by `arm_table` (which re-exports it) so one string governs both the
#: evidence a snapshot carries and the inference drawn from it.
ADMISSION_SEMANTICS = "undocumented"

#: The record type an operator recovery appends to the shared ledger. It is a
#: SEGMENT BOUNDARY, not a repair: the damaged bytes stay exactly where they
#: are, and every window that spans this record is marked incomplete.
LEDGER_RECOVERY_RECORD = "window_ledger_recovery"


class WindowLedgerUnavailable(RuntimeError):
    """The shared window ledger could not be written or locked.

    This is a FAULT, not a case to survive (adversarial-review finding F5).
    The ledger is the sole evidence behind the pacing interval and behind
    every 429 classification; a run that silently continues without it
    produces rows whose failures cannot be classified at all, and the gap is
    invisible afterwards. The single-executor design also makes lock
    contention impossible in a healthy run, so a timeout is a symptom of a
    second executor or a wedged filesystem — both of which must stop the
    request, not be waited out.
    """


class _LedgerLock:
    """An `O_CREAT | O_EXCL` lock beside the ledger file. Atomic at the
    filesystem, so exactly one of any number of processes holds it. A lock
    older than `_LEDGER_LOCK_STALE` belonged to a process that died and is
    broken — the alternative is an experiment that stops because one cell was
    killed while appending one line."""

    def __init__(self, path: Path):
        self.path = Path(str(path) + ".lock")
        self.acquired = False

    def __enter__(self):
        deadline = time.monotonic() + _LEDGER_LOCK_TIMEOUT
        while True:
            try:
                handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(handle, str(os.getpid()).encode("ascii"))
                os.close(handle)
                self.acquired = True
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except OSError:
                    age = 0.0
                if age > _LEDGER_LOCK_STALE:
                    try:
                        self.path.unlink()
                    except OSError:
                        pass
                    continue
                if time.monotonic() > deadline:
                    # NOT "proceed unlocked and hope" (F5). One executor runs
                    # a schedule, so contention here means a second executor
                    # or a wedged filesystem; either way the window evidence
                    # is already compromised and the request must not go out
                    # believing it is paced.
                    raise WindowLedgerUnavailable(
                        f"could not acquire the window-ledger lock within {_LEDGER_LOCK_TIMEOUT:.0f}s "
                        f"({self.path.name} is held). One executor runs a schedule, so this is a fault: "
                        f"the provider window cannot be paced or reconstructed while it persists.")
                time.sleep(0.05)

    def __exit__(self, *exc):
        if self.acquired:
            try:
                self.path.unlink()
            except OSError:
                pass
        return False


class WindowLedgerUnhealthy(WindowLedgerUnavailable):
    """The shared ledger contains evidence that cannot be read.

    `window_ledger_read` used to skip every JSON parse failure in silence. A
    killed process leaves a TRUNCATED final line; the next append concatenates
    onto it, so the damaged record becomes a malformed MIDDLE line and takes
    the following record with it. The reader then undercounts the rolling
    window, paces from an older request, attaches no suspicion, and continues
    as though the evidence were complete — which is the one thing a
    measurement instrument may never do.

    Any malformed or non-dict line therefore makes the ledger UNHEALTHY, and
    an unhealthy ledger refuses the next provider request. The bytes are never
    repaired and never deleted: recovery is an explicit operator act
    (`run_arms.py --recover-window-ledger`) that appends a segment boundary,
    is journalled, and marks every affected rate-limit classification
    ambiguous.
    """


def window_ledger_scan(path) -> dict:
    """Read the ledger and REPORT its health rather than silently repairing it.

    Returns `{"entries", "malformed", "unterminated_final_line",
    "acknowledged_through_line", "recoveries", "line_count", "healthy",
    "detail"}`. Never raises, never writes: this is the honest description of
    the file, and every caller decides what to do about it."""
    empty = {"entries": [], "malformed": [], "unterminated_final_line": False,
             "acknowledged_through_line": 0, "recoveries": [], "line_count": 0,
             "healthy": True, "detail": "", "exists": False}
    if not path:
        return empty
    path = Path(path)
    try:
        raw = path.read_bytes().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return empty
    except OSError as exc:                                                 # noqa: BLE001
        bad = dict(empty)
        bad.update({"healthy": False, "exists": True,
                    "detail": f"the ledger cannot be read: {type(exc).__name__}: {exc}"})
        return bad
    pieces = raw.split("\n")
    unterminated = bool(raw) and not raw.endswith("\n")
    line_count = len(pieces) if unterminated else len(pieces) - 1
    entries: list[dict] = []
    malformed: list[dict] = []
    recoveries: list[dict] = []
    acknowledged = 0
    for index, line in enumerate(pieces[:line_count], start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError:
            malformed.append({"line": index, "chars": len(line),
                              "preview": redact_secrets(line[:80])})
            continue
        if not isinstance(value, dict):
            malformed.append({"line": index, "chars": len(line), "preview": "a non-object JSON line"})
            continue
        entries.append(value)
        if value.get("record") == LEDGER_RECOVERY_RECORD:
            recoveries.append(value)
            through = value.get("acknowledged_through_line")
            if isinstance(through, int):
                acknowledged = max(acknowledged, through)
    outstanding = [m for m in malformed if m["line"] > acknowledged]
    healthy = not outstanding and not unterminated
    detail = ""
    if outstanding:
        detail = (f"{len(outstanding)} malformed line(s) at "
                  f"{[m['line'] for m in outstanding][:8]} that no recovery record acknowledges")
    elif unterminated:
        detail = (f"the final line (line {line_count}) has no terminating newline: a process was killed "
                  f"mid-append, and the next append would concatenate onto it and destroy both records")
    return {"entries": entries, "malformed": malformed, "unterminated_final_line": unterminated,
            "acknowledged_through_line": acknowledged, "recoveries": recoveries,
            "line_count": line_count, "healthy": healthy, "detail": detail, "exists": True}


def window_ledger_health(path) -> dict:
    """The scan without its entries — what the table renders and what the
    startup witness checks."""
    scan = window_ledger_scan(path)
    return {k: v for k, v in scan.items() if k != "entries"}


def window_ledger_recover(path, *, reason: str, session_id: str | None = None,
                          operator: str | None = None) -> dict:
    """The EXPLICIT operator recovery. Appends a segment
    boundary that ACKNOWLEDGES the damaged lines by number; it never rewrites
    or removes a byte of them.

    The one write it makes to existing content is a terminating newline when
    the file ends mid-record — without it the very next append would
    concatenate onto the partial record and destroy the following one too.
    Nothing is removed or altered, and the boundary record says it did this.

    Returns the record (with `"recovered": False` when the ledger was already
    healthy and nothing was written)."""
    path = Path(path)
    scan = window_ledger_scan(path)
    if scan["healthy"]:
        return {"recovered": False, "reason": "the ledger is healthy; nothing to recover",
                "health": {k: v for k, v in scan.items() if k != "entries"}}
    segment = len(scan["recoveries"]) + 1
    record = {"record": LEDGER_RECOVERY_RECORD, "t": time.time(),
              "at": datetime.now(timezone.utc).isoformat(), "segment": segment,
              "acknowledged_through_line": scan["line_count"],
              "malformed_lines": [m["line"] for m in scan["malformed"]],
              "terminated_partial_line": bool(scan["unterminated_final_line"]),
              "reason": str(reason)[:300], "session_id": session_id,
              "operator": operator, "bytes_preserved": True}
    line = json.dumps(record, sort_keys=True, default=str) + "\n"
    with _LedgerLock(path):
        with open(path, "ab") as handle:
            if scan["unterminated_final_line"]:
                handle.write(b"\n")
            handle.write(line.encode("utf-8"))
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
    record["recovered"] = True
    return record


def window_ledger_append(path, entry: dict) -> None:
    """Append one attempt to the shared provider-window ledger.

    RAISES `WindowLedgerUnavailable` when it cannot (F5). The previous
    version swallowed `OSError` so that "a measurement instrument must not
    lose a rollout because a bookkeeping file could not be written" — but
    this bookkeeping file IS the measurement: without it the pacing interval
    is unenforced and every 429 in the run classifies as
    `ambiguous/rate_limit_window_unknown`, with nothing on the row to say the
    evidence was lost rather than absent. A loud failure costs one cell; a
    silent one costs the failure census."""
    if not path:
        return
    path = Path(path)
    line = json.dumps(entry, sort_keys=True, default=str) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LedgerLock(path):
            # Never append ONTO damaged evidence. A file whose
            # final line has no newline is a process killed mid-write;
            # appending here is what turns one truncated record into a
            # malformed middle line and loses the next record as well.
            #
            # The scan is INSIDE the lock (adversarial review, C2). Outside it
            # the check was a TOCTOU window: the verifier interleaved a
            # truncating writer between the scan and the lock, and this append
            # then landed on the damaged record and merged two records into one
            # malformed line — the precise failure the scan exists to prevent.
            scan = window_ledger_scan(path)
            if not scan["healthy"]:
                raise WindowLedgerUnhealthy(
                    f"the provider-window ledger {path} is UNHEALTHY and must not be appended to: "
                    f"{scan['detail']}. The bytes are preserved for audit; recover deliberately with "
                    f"tests/run_arms.py --recover-window-ledger, which journals the act, starts a new "
                    f"evidence segment and makes the affected rate-limit classifications ambiguous.")
            with open(path, "a", encoding="utf-8", newline="") as handle:
                handle.write(line)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:              # best-effort durability; the append itself succeeded
                    pass
    except OSError as exc:                                                 # noqa: BLE001
        raise WindowLedgerUnavailable(
            f"could not append to the provider-window ledger {path}: {type(exc).__name__}: {exc}. "
            f"The window evidence behind pacing and every 429 classification would be incomplete "
            f"from here on.") from exc


def window_ledger_precheck(path) -> None:
    """Prove, BEFORE a request is sent, that the shared ledger can still be
    locked and written (F5). Raises `WindowLedgerUnavailable` otherwise, so
    the request is refused rather than made without pacing evidence.

    Acquiring and immediately releasing the same lock the append uses is the
    cheapest honest test: it detects a held lock (a second executor, which
    the single-executor design forbids), a read-only directory and a missing
    parent, and it costs one file create/unlink."""
    if not path:
        return
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:                                                 # noqa: BLE001
        raise WindowLedgerUnavailable(
            f"the window-ledger directory {path.parent} is not writable: "
            f"{type(exc).__name__}: {exc}") from exc
    # The HEALTH of the evidence is checked BEFORE the request,
    # not after it. A malformed line means the trailing window this request
    # would be paced and classified against cannot be reconstructed, and a
    # request made on evidence that is already known to be incomplete cannot
    # be classified afterwards either.
    scan = window_ledger_scan(path)
    if not scan["healthy"]:
        raise WindowLedgerUnhealthy(
            f"the provider-window ledger {path} is UNHEALTHY: {scan['detail']}. The next provider "
            f"request is REFUSED — its trailing window could not be reconstructed and its 429s could "
            f"not be classified. The damaged bytes are preserved; recover deliberately with "
            f"tests/run_arms.py --recover-window-ledger.")
    with _LedgerLock(path):                     # raises on timeout; releases immediately
        pass


def window_ledger_read(path, strict: bool = True) -> list[dict]:
    """Every entry in the ledger, oldest first.

    STRICT by default: a malformed or non-dict line RAISES
    `WindowLedgerUnhealthy` rather than being skipped. The previous version
    dropped every parse failure in silence, so a truncated record — and the
    record an append then concatenated onto it — simply vanished from the
    rolling window with nothing on any row to say so.

    `strict=False` is for the readers that must describe a damaged ledger
    rather than refuse it: the recovery tool and the evidence table."""
    scan = window_ledger_scan(path)
    if strict and not scan["healthy"]:
        raise WindowLedgerUnhealthy(
            f"the provider-window ledger {path} is UNHEALTHY: {scan['detail']}. Its bytes are preserved "
            f"for audit and are never repaired automatically; recover deliberately with "
            f"tests/run_arms.py --recover-window-ledger.")
    return scan["entries"]


def window_ledger_last_time(entries: list[dict], provider: str):
    """The epoch time of the last attempt against `provider`, or `None`. This
    is what the pacing interval is measured from — the PROVIDER's last
    request, whichever cell made it, not this process's."""
    times = [e.get("t") for e in entries
             if e.get("provider") == provider and isinstance(e.get("t"), (int, float))]
    return max(times) if times else None


WINDOW_KIND_PRE_REQUEST = "pre_request"
WINDOW_KIND_PROSPECTIVE = "prospective_including_current_request"


def window_snapshot(entries: list[dict], now: float, provider: str, model: str,
                    cell: str | None, seconds: float = WINDOW_SECONDS,
                    current_request_estimate: int | None = None,
                    kind: str = WINDOW_KIND_PRE_REQUEST) -> dict:
    """What the experiment actually sent to `(provider, model)` in the
    `seconds` before `now`, with BILLED USAGE, REJECTED-ATTEMPT ESTIMATES and
    THE CURRENT REQUEST kept strictly apart.

    The retired version folded them into one number:

        if not billed: billed = estimated_request_tokens

    which asserts that a request the provider REFUSED consumed exactly the
    tokens we estimate it would have consumed. Nothing establishes that — see
    `ADMISSION_SEMANTICS` — and repeated backoffs could manufacture a
    "saturated" window out of estimates alone, turning an external rate limit
    into an arm-induced one. The fields are therefore:

      `billed_*`                  what the provider itself reported for
                                  requests it SERVED. The only established
                                  consumption.
      `unbilled_accepted_*`       estimates for served requests that reported
                                  no usage. Evidence, not fact.
      `rejected_estimate_*`       estimates for attempts that returned no
                                  completion (429s and errors). Evidence that
                                  may only ever WIDEN an upper bound.
      `current_request_estimate_tokens`
                                  the size of the request being made (or
                                  refused) right now — the one the pre-request
                                  window necessarily excludes.

    `kind` labels which of the two archived windows this is: the pre-request
    one, or the prospective one that includes the current request (his Q4).
    """
    floor = now - seconds
    billed_in = billed_out = mine_billed = 0
    unbilled_accepted = mine_unbilled_accepted = 0
    rejected_estimate = mine_rejected_estimate = 0
    accepted = mine_accepted = 0
    rejected = mine_rejected = 0
    rate_limited = failed = 0
    counted = 0
    incomplete_segments = []
    for entry in entries:
        t = entry.get("t")
        if not isinstance(t, (int, float)) or t < floor or t > now:
            continue
        if entry.get("record") == LEDGER_RECOVERY_RECORD:
            # A recovery boundary INSIDE this window: entries are missing from
            # it by construction, and no attribution may be read from it.
            incomplete_segments.append(entry.get("segment"))
            continue
        if entry.get("provider") != provider or entry.get("model") != model:
            continue
        counted += 1
        mine = cell is not None and entry.get("cell") == cell
        status = str(entry.get("status") or "")
        served = status == "ok"
        row_billed = 0
        for key in ("billed_input_tokens", "billed_output_tokens"):
            value = entry.get(key)
            if isinstance(value, int):
                row_billed += value
                if key == "billed_input_tokens":
                    billed_in += value
                else:
                    billed_out += value
        estimate = entry.get("estimated_request_tokens")
        estimate = estimate if isinstance(estimate, int) else 0
        if served:
            accepted += 1
            mine_accepted += 1 if mine else 0
            if row_billed:
                mine_billed += row_billed if mine else 0
            else:
                unbilled_accepted += estimate
                mine_unbilled_accepted += estimate if mine else 0
        else:
            rejected += 1
            mine_rejected += 1 if mine else 0
            rejected_estimate += estimate
            mine_rejected_estimate += estimate if mine else 0
            if status.startswith("rate_limited"):
                rate_limited += 1
            else:
                failed += 1
    return {"window_seconds": seconds, "provider": provider, "model": model, "cell": cell,
            "window_kind": kind, "entries_in_window": counted,
            "admission_semantics": ADMISSION_SEMANTICS,
            # established consumption — the provider's own numbers
            "billed_tokens_total": billed_in + billed_out,
            "billed_tokens_this_cell": mine_billed,
            "billed_input_tokens_total": billed_in, "billed_output_tokens_total": billed_out,
            # served requests that reported no usage: evidence, not fact
            "unbilled_accepted_estimate_tokens_total": unbilled_accepted,
            "unbilled_accepted_estimate_tokens_this_cell": mine_unbilled_accepted,
            # attempts that returned no completion: NEVER added to consumed quota
            "rejected_estimate_tokens_total": rejected_estimate,
            "rejected_estimate_tokens_this_cell": mine_rejected_estimate,
            "accepted_requests_total": accepted, "accepted_requests_this_cell": mine_accepted,
            "rejected_requests_total": rejected, "rejected_requests_this_cell": mine_rejected,
            "rate_limited_requests_total": rate_limited, "failed_requests_total": failed,
            "requests_total": accepted + rejected, "requests_this_cell": mine_accepted + mine_rejected,
            # Adversarial review (INFO): whether there IS a
            # current request is its OWN fact, not something to infer from the
            # presence of a token estimate. The request dimension needs the
            # boolean (a request counts as one request whatever its size), and
            # deriving it from the estimate would silently drop the +1 for any
            # request whose size could not be estimated.
            "current_request_present": current_request_estimate is not None,
            "current_request_estimate_tokens": current_request_estimate,
            "evidence_incomplete": bool(incomplete_segments),
            "recovered_segments": sorted(s for s in incomplete_segments if s is not None)}


def prospective_window(pre: dict, estimate: int | None, this_cell: bool = True) -> dict:
    """The SAME trailing minute, INCLUDING the request the provider is
    refusing right now.

    Both windows are archived on the fatal attempt and both are labelled. The
    current request enters as what it is — a rejected attempt whose size is an
    ESTIMATE — so the prospective window widens the upper bound and never
    touches `billed_tokens_*`. Presenting the estimate as billed usage is the
    conflation this whole section exists to end."""
    out = dict(pre)
    out["window_kind"] = WINDOW_KIND_PROSPECTIVE
    size = estimate if isinstance(estimate, int) else 0
    out["rejected_estimate_tokens_total"] = (out.get("rejected_estimate_tokens_total") or 0) + size
    out["rejected_requests_total"] = (out.get("rejected_requests_total") or 0) + 1
    out["rate_limited_requests_total"] = (out.get("rate_limited_requests_total") or 0) + 1
    out["requests_total"] = (out.get("requests_total") or 0) + 1
    out["entries_in_window"] = (out.get("entries_in_window") or 0) + 1
    if this_cell:
        out["rejected_estimate_tokens_this_cell"] = (out.get("rejected_estimate_tokens_this_cell") or 0) + size
        out["rejected_requests_this_cell"] = (out.get("rejected_requests_this_cell") or 0) + 1
        out["requests_this_cell"] = (out.get("requests_this_cell") or 0) + 1
    out["current_request_estimate_tokens"] = estimate
    out["current_request_present"] = True          # it is inside this window now
    return out


# ---------------------------------------------------------------------------
# Structured provider-error capture. The blind failure map
# must be fed STATUS, not prose: `openai.APIStatusError` carries the HTTP
# status, the provider's own error code/type, and (on the raw response) the
# rate-limit headers. All of it is redacted before it is archived.
# ---------------------------------------------------------------------------

RATE_LIMIT_HEADER_PREFIXES = ("x-ratelimit", "ratelimit", "retry-after", "x-rate-limit")
MAX_ERROR_MESSAGE_CHARS = 600


def provider_error_fields(exc) -> dict:
    """`{http_status, provider_error_code, provider_error_type, error_message,
    rate_limit_headers}` from an exception, all redacted, none guessed.

    The legacy client does not use `with_raw_response`, so the response object
    is only reachable through the raised `openai.APIStatusError`; what it
    offers is what we archive. Every field is `None` when the exception does
    not carry it — never a placeholder that would look like evidence."""
    out = {"error_class": type(exc).__name__, "http_status": None, "provider_error_code": None,
           "provider_error_type": None, "error_message": None, "rate_limit_headers": None}
    out["error_message"] = redact_secrets(str(exc))[:MAX_ERROR_MESSAGE_CHARS] or None
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        out["http_status"] = status
    code = getattr(exc, "code", None)
    if isinstance(code, (str, int)):
        out["provider_error_code"] = str(code)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error") if isinstance(body.get("error"), dict) else body
        for key, field in (("code", "provider_error_code"), ("type", "provider_error_type")):
            value = error.get(key) if isinstance(error, dict) else None
            if isinstance(value, (str, int)) and out[field] is None:
                out[field] = str(value)
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        collected = {}
        try:
            items = headers.items()
        except (AttributeError, TypeError):                                # noqa: BLE001
            items = []
        for name, value in items:
            lowered = str(name).lower()
            if any(lowered.startswith(prefix) for prefix in RATE_LIMIT_HEADER_PREFIXES):
                collected[lowered] = redact_secrets(str(value))[:120]
        out["rate_limit_headers"] = collected or None
        if out["http_status"] is None:
            code = getattr(response, "status_code", None)
            if isinstance(code, int):
                out["http_status"] = code
    return out


class ScheduledRowOverwrite(SystemExit):
    """Refusal: this write would replace an observed SCHEDULED cell."""


def refuse_scheduled_overwrite(path: Path, rows: list[dict]) -> None:
    """The WRITER's own immutability check (adversarial-review
    finding F2).

    `tests/run_arms.py` refuses `--force` for a sealed schedule — but nothing
    stopped a hand-typed `measure_budget.py --tag confirm1v2_B1p_train1_r1
    --stamp-date 2026-08-31 ...` from writing the same filename and replacing
    an observed cell with a fresh draw, undetectably: the file is rewritten
    atomically, so not even a truncation would show. The executor is the
    wrong layer for that guarantee. It belongs HERE, at the only code that
    writes the file, where every caller passes through it.

    The rule: if the target file already exists AND either the existing rows
    or the rows about to be written carry a `schedule_id`, REFUSE. No flag
    overrides it — a flag would be the same operator promise the sealed
    schedule already refuses. A plain pilot overwrite (neither side
    scheduled) keeps today's behaviour, because a diagnostic re-run is not an
    observation of a registered cell.
    """
    if not path.exists():
        return
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Unreadable is not "absent": something is there, and a confirmatory
        # write must not decide what it was.
        existing = []
    existing_ids = sorted({r.get("schedule_id") for r in existing
                           if isinstance(r, dict) and r.get("schedule_id")})
    new_ids = sorted({r.get("schedule_id") for r in rows
                      if isinstance(r, dict) and r.get("schedule_id")})
    if not existing_ids and not new_ids:
        return
    raise ScheduledRowOverwrite(
        f"REFUSED to overwrite {path}: it already exists and "
        + (f"carries rows from schedule(s) {existing_ids}" if existing_ids
           else f"this run belongs to schedule(s) {new_ids}")
        + ". An observation of a registered experiment cell is immutable, and no flag overrides "
          "that — a replacement decided after seeing the first outcome is exactly what the "
          "pre-registration exists to prevent. Use a NEW schedule label, or a predeclared "
          "replacement record that preserves the original row.")


def _field(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _client_version() -> str:
    try:
        return importlib.metadata.version("verifiers")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


# The CONCRETE client/library versions the replay contract is bound to
# (the client/library versions that implement it). A bump in
# either package can change the provider-native projection without a single
# line of this repository changing, so it is part of the replay identity and
# a bumped host makes a NEW experimental condition rather than drifting
# invisibly into an old one.
REPLAY_LIBRARIES = ("verifiers", "openai")


def library_versions(names=REPLAY_LIBRARIES) -> dict:
    versions = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "unknown"
    return versions


def tool_call_chars(message) -> int:
    """The CANONICAL serialized size, in characters, of one assistant
    message's tool calls — `json.dumps(sort_keys=True)` of
    `[{"id", "name", "arguments"}, ...]` in call order, measured in UTF-8
    CHARACTERS (`ensure_ascii=False`, so a non-ASCII character counts once,
    not as its six-character `\\uXXXX` escape).

    This is a deliberately CONSERVATIVE lower bound on what the provider
    actually billed for the turn: every provider wraps the same call list in
    a different wire envelope (`function.name`/`function.arguments`,
    `type: "function"`, indices, per-provider id formats), so no single
    serialization is "the" true size. What must never happen is the previous
    behaviour — counting the body as ZERO, which let the largest completion
    payload in the whole task (a 48,000-character `write_ledger` argument)
    be reported as one completion token and still pass the plausibility
    floor.

    Zero when the message carries no tool calls at all — NOT `len("[]")`, so
    an ordinary prose turn's plausibility arithmetic is untouched.

    Accepts every shape this repository's clients dump a call in: a
    `ToolCall` object, a plain dict, a nested `{"function": {...}}` dict, or
    the JSON STRING the legacy client sometimes writes. `arguments` that is
    not already a string is itself canonicalised with `sort_keys=True`, so
    two clients that ordered the same argument dict differently measure the
    same.

    A NOTE ON THE PACKAGE'S OWN `beancount_ledger.tool_call_chars`: the
    environment side computes the same quantity for its own fail-closed
    check. This implementation is deliberately INDEPENDENT (a second
    implementation, not an import) so the environment's check and the
    measurement's check cannot fail together through one shared bug.

    DELIBERATE DIVERGENCE — do not "unify" these two: the package's version
    measures only the shapes IT can ever produce, and returns 0 for a nested
    `{"function": {...}}` call or a call dumped as a JSON string. This one
    accepts both, because it reads an ARCHIVE written by whichever client
    served the row, including older ones. Making this side agree with the
    package's narrower reading would silently return 0 for exactly the
    payload the plausibility floor exists to catch.
    """
    calls = _field(message, "tool_calls") or []
    canonical = []
    for call in calls:
        if isinstance(call, str):                          # the legacy client dumps calls as JSON strings
            try:
                call = json.loads(call)
            except ValueError:
                canonical.append({"id": "", "name": "", "arguments": call})
                continue
        function = _field(call, "function")
        name = _field(call, "name")
        if name is None and function is not None:
            name = _field(function, "name")
        arguments = _field(call, "arguments")
        if arguments is None and function is not None:
            arguments = _field(function, "arguments")
        if arguments is None:
            arguments = ""
        elif not isinstance(arguments, str):
            arguments = json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str)
        canonical.append({"id": str(_field(call, "id") or ""), "name": str(name or ""), "arguments": arguments})
    if not canonical:
        return 0
    return len(json.dumps(canonical, sort_keys=True, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# The REPLAY contract — the provider-bound transcript
# policy, with its own version and digest, separate from the world/episode
# contract. Two rows may share an `episode_contract_digest` (same prompt,
# same tools, same ceiling) and still not be comparable, because the CLIENT
# replayed the conversation differently.
# ---------------------------------------------------------------------------

REPLAY_CONTRACT_VERSION = 1

# Provider continuation items this client CANNOT carry. Gemini 3.x returns an
# opaque `thought_signature` with a tool call and rejects turn 2 with
# 400 "Function call is missing a thought_signature in functionCall parts"
# when it is not replayed; the legacy chat-completions client has no field
# for it under ANY replay policy. Such a family is
# `arm_induced/incompatible` — a provider/client incompatibility — and is
# NEVER recorded as a model failure.
UNSUPPORTED_CONTINUATION_FIELDS = ("thought_signature",)

# `None` means ABSENT for THIS field and only this
# field. The legacy client writes `reasoning_content` into every replayed
# assistant message even when the model returned none, and Mistral rejects
# the bare key (422 `extra_forbidden`). Do NOT generalise to "drop every
# None in every payload" — an explicit JSON null is meaningful elsewhere —
# so the rule is pinned field by field, here.
NONE_AS_ABSENT_FIELDS = ("reasoning_content",)

PROVIDER_PROJECTION = "verifiers.legacy.clients.openai_chat_completions_client.OpenAIChatCompletionsClient"


def replay_contract(reasoning_replay: bool, versions: dict | None = None) -> dict:
    """The canonical dict the replay digest is taken over. Everything that
    decides what the PROVIDER sees on turn n given turns 1..n-1, and nothing
    that does not.

    `reasoning_replay=True` is arm A′/B1′ (the client replays
    `reasoning_content` as the framework does); `False` is B2′ (the
    projection drops it from the wire copy only — the rollout state's own
    trajectory keeps every model's reasoning as audit evidence either way).
    """
    return {
        "replay_contract_version": REPLAY_CONTRACT_VERSION,
        "provider_projection": PROVIDER_PROJECTION,
        "reasoning_replay": bool(reasoning_replay),
        # What survives onto a replayed ASSISTANT message, and what does not.
        "assistant_fields_retained": ["role", "content", "tool_calls"]
                                     + (["reasoning_content"] if reasoning_replay else []),
        "assistant_fields_dropped": [] if reasoning_replay else ["reasoning_content"],
        # None-as-absent: FIELD BY FIELD, never "every None everywhere".
        "none_as_absent_fields": list(NONE_AS_ABSENT_FIELDS),
        # Opaque provider continuation items received WITH a tool call are
        # replayed verbatim, attached to the same call, in the same order —
        # except the ones this client structurally cannot carry, which are
        # declared here rather than discovered as a 400 mid-run.
        "continuation_fields_retained_verbatim": [],
        "continuation_fields_unsupported": list(UNSUPPORTED_CONTINUATION_FIELDS),
        # Ordering / association: the tool REPLY for call `c` is a `tool`
        # message carrying `tool_call_id == c.id`, emitted in the same order
        # as the calls on the assistant message that produced them, directly
        # after that assistant message and before the next one.
        "tool_call_ordering": "assistant tool_calls replayed in emission order, ids preserved verbatim",
        "tool_result_association": "one tool message per call, tool_call_id == the call's own id, "
                                   "in call order, immediately after the assistant message",
        "library_versions": versions if versions is not None else library_versions(),
    }


def replay_contract_digest(reasoning_replay: bool, versions: dict | None = None) -> str:
    payload = json.dumps(replay_contract(reasoning_replay, versions), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def tool_names(completion) -> list:
    """Tool names in call order, whatever shape the client dumps them in
    (dict / object, `name` on the call or on its `function`)."""
    names = []
    for message in completion or []:
        for call in _field(message, "tool_calls") or []:
            if isinstance(call, str):                       # the legacy client dumps calls as JSON strings
                try:
                    call = json.loads(call)
                except ValueError:
                    pass
            function = _field(call, "function")
            name = _field(call, "name") or (_field(function, "name") if function is not None else None)
            names.append(name or f"?{type(call).__name__}")
    return names


def message_volume(completion) -> dict:
    """Characters per message kind: content, reasoning (if the client keeps
    it in the transcript — it is re-sent every turn), tool replies."""
    vol = {"assistant_content": 0, "assistant_reasoning": 0, "tool_replies": 0, "assistant_messages": 0, "tool_messages": 0}
    for message in completion or []:
        role = _field(message, "role")
        if role == "assistant":
            vol["assistant_messages"] += 1
            vol["assistant_content"] += len(str(_field(message, "content") or ""))
            for key in ("reasoning_content", "reasoning"):
                vol["assistant_reasoning"] += len(str(_field(message, key) or ""))
        elif role == "tool":
            vol["tool_messages"] += 1
            vol["tool_replies"] += len(str(_field(message, "content") or ""))
    return vol


def last_assistant_text(completion) -> str:
    for message in reversed(completion or []):
        if _field(message, "role") == "assistant":
            return str(_field(message, "content") or "")
    return ""


def _content_chars(content) -> int:
    """Visible characters in a message's `content`, whatever shape it is:
    a plain string, or a list of content parts (`{"type": "text", "text": ...}`)."""
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    if isinstance(content, (list, tuple)):
        total = 0
        for part in content:
            if isinstance(part, str):
                total += len(part)
                continue
            text = _field(part, "text")
            if isinstance(text, str):
                total += len(text)
        return total
    return len(str(content))


def per_turn_rows(trajectory, reasoning_replay: bool, request_caps, wire_caps=None) -> list[dict]:
    """One dict per `TrajectoryStep`: this turn's own usage, plus what was
    IN the prompt the model saw this turn (the whole replayed history) —
    reasoning characters (what a full-replay client resends every later
    turn), visible characters (content, tool-call arguments, tool replies,
    user messages — replayed regardless of the reasoning policy), and the
    per-turn/cumulative token counts the budget is measured against.

    `reasoning_chars_sent` is `reasoning_chars_in_history` under full replay
    and 0 under the no-reasoning-content projection: what
    the CLIENT actually put on the wire this turn, as opposed to what the
    ORIGINAL trajectory (kept for audit either way) carries.

    `wire_caps`, when given, is the client's OWN
    `PacedClient.wire_caps` list (`make_client_cls`): the `max_tokens`/
    `max_completion_tokens` fields the legacy client's `normalize_sampling_
    args` actually put in the request body for that turn, AFTER its own
    rename/precedence handling — as opposed to `request_max_tokens`, which
    is the environment's own DECLARED cap (`state["piv_request_max_tokens"]`)
    before it ever reaches the client. `wire_max_tokens`/
    `wire_max_completion_tokens` are `None` for every turn when the caller's
    client does not expose `wire_caps` at all (a scripted test client, never
    the real `OpenAIChatCompletionsClient` family) — that is "not applicable",
    not a mismatch; `compute_budget_accounting` only compares them when the
    list is present. `provider_model`/`system_fingerprint` come from the RAW
    provider response the wire-capturing wrapper saw, captured before the
    legacy client's `from_native_response` discards both (verified: neither
    survives onto `verifiers.legacy.types.Response`).
    """
    rows: list[dict] = []
    cum_in = cum_out = 0
    for index, step in enumerate(trajectory or []):
        response = _field(step, "response")
        usage = _field(response, "usage") if response is not None else None
        message = _field(response, "message") if response is not None else None
        prompt = _field(step, "prompt") or []
        reasoning_chars = 0
        visible_chars = 0
        for m in prompt:
            role = _field(m, "role")
            if role == "assistant":
                reasoning_chars += len(str(_field(m, "reasoning_content") or ""))
                visible_chars += _content_chars(_field(m, "content"))
                for call in _field(m, "tool_calls") or []:
                    visible_chars += len(str(_field(call, "arguments") or ""))
            elif role in ("tool", "user"):
                visible_chars += _content_chars(_field(m, "content"))
        in_tok = _field(usage, "prompt_tokens") if usage is not None else None
        out_tok = _field(usage, "completion_tokens") if usage is not None else None
        reasoning_tok = _field(usage, "reasoning_tokens") if usage is not None else None
        if in_tok is not None:
            cum_in += in_tok
        if out_tok is not None:
            cum_out += out_tok
        wire = wire_caps[index] if wire_caps is not None and index < len(wire_caps) else None
        # THIS turn's OWN generated text -- from the RESPONSE message, not
        # the prompt (which only carries EARLIER turns' text, replayed).
        # Needed for `usage_implausible` (adversarial-review follow-up):
        # a turn cannot plausibly have generated more visible+reasoning
        # characters than roughly 8x its reported completion_tokens.
        assistant_content_chars = _content_chars(_field(message, "content")) if message is not None else 0
        assistant_reasoning_chars = len(str(_field(message, "reasoning_content") or "")) if message is not None else 0
        # The tool-call ARGUMENTS this turn generated. The
        # largest completion payload in this task (a whole `write_ledger`
        # body, up to the 48,000-character envelope) lives here and nowhere
        # else -- omitting it from the plausibility denominator made a
        # 48,000-character write reporting one completion token pass.
        turn_tool_call_chars = tool_call_chars(message) if message is not None else 0
        rows.append({
            "turn": index + 1,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "reasoning_tokens": reasoning_tok,
            "prompt_messages": len(prompt),
            "reasoning_chars_in_history": reasoning_chars,
            "reasoning_chars_sent": reasoning_chars if reasoning_replay else 0,
            "visible_chars_in_history": visible_chars,
            "assistant_content_chars": assistant_content_chars,
            "assistant_reasoning_chars": assistant_reasoning_chars,
            "tool_call_chars": turn_tool_call_chars,
            "request_max_tokens": request_caps[index] if request_caps and index < len(request_caps) else None,
            "wire_max_tokens": (wire or {}).get("max_tokens"),
            "wire_max_completion_tokens": (wire or {}).get("max_completion_tokens"),
            "provider_model": (wire or {}).get("provider_model"),
            "system_fingerprint": (wire or {}).get("system_fingerprint"),
            "finish_reason": _field(message, "finish_reason") if message is not None else None,
            "truncated": bool(_field(step, "is_truncated")),
            "tools": [_field(call, "name") for call in (_field(message, "tool_calls") or [])] if message is not None else [],
            "cumulative_input_tokens": cum_in,
            "cumulative_output_tokens": cum_out,
        })
    return rows


def _valid_nonneg_int(value) -> bool:
    """`True` only for an actual non-negative `int` (bools excluded --
    `isinstance(True, int)` is `True` in Python, which would otherwise let a
    stray boolean usage value slip through as "valid"). Strings, floats and
    negative numbers are all `False` -- exactly the "no crash on strings/
    floats/negatives" inputs `compute_budget_accounting` must survive."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def compute_budget_suspicion(per_turn: list[dict], env_suspicious_code=None,
                             window_ledger_gap: bool = False) -> str | None:
    """The SUSPICION bucket — a named diagnostic, never a
    validity gate. Returns a code from `ALL_BUDGET_SUSPICION_CODES` or
    `None`.

    `usage_implausible`: some turn produced more than
    `CHARS_PER_TOKEN_FLOOR` (8) characters per reported completion token,
    counting visible content, replayed reasoning AND the canonical
    serialized tool-call arguments (`tool_call_chars` —
    omitting the tool-call body let a 48,000-character `write_ledger`
    argument reporting one completion token look fine). A turn whose row
    predates `tool_call_chars` contributes only the two character fields it
    does carry, which is conservative in the safe direction (fewer
    characters => less suspicion), never a false alarm.

    `env_<code>`: the environment's own suspicion signal
    (`state["piv_budget_accounting_suspicious"]`), verbatim when it is one
    of `ENV_BUDGET_SUSPICION_CODES`, else the fixed `env_unrecognized`.
    Our own check is reported first when both fire.
    """
    if window_ledger_gap:
        # Reported FIRST: a row whose provider-window evidence is incomplete
        # cannot have its rate limits classified at all, which is a stronger
        # caveat than a characters-per-token anomaly.
        return "window_ledger_gap"
    for turn in per_turn or []:
        out_tok = turn.get("output_tokens")
        if not _valid_nonneg_int(out_tok):
            continue                       # a non-integer count is an INVALID matter, not a suspicion
        chars = ((turn.get("assistant_content_chars") or 0)
                 + (turn.get("assistant_reasoning_chars") or 0)
                 + (turn.get("tool_call_chars") or 0))
        if out_tok * CHARS_PER_TOKEN_FLOOR < chars:
            return "usage_implausible"
    if env_suspicious_code:
        code = (env_suspicious_code if env_suspicious_code in ENV_BUDGET_SUSPICION_CODES
                else ENV_UNRECOGNIZED_CODE)
        return f"env_{code}"
    return None


def compute_budget_accounting(request_caps, per_turn: list[dict], wire_caps, env_code,
                              reported_output_tokens, max_total_completion_tokens, attempts,
                              requests=None, rollout_id=None) -> str:
    """`"VALID"` iff every check below passes, else `"INVALID/<code>"` with
    `<code>` from the CLOSED set `BUDGET_ACCOUNTING_CODES` (our own checks)
    or `env_<code>` from `ENV_BUDGET_ACCOUNTING_CODES` (the OTHER builder's
    own `state["piv_budget_accounting_invalid"]`, now a code rather than a
    bool/free string) — never any other string. Fail CLOSED, never a
    silently archived row that merely looks valid. Checks run in this EXACT
    order — the first one that fails wins, so two simultaneous defects are
    reported by whichever is listed first here, deterministically:

      1. no_request_caps        `request_caps` is `None`.
      2. caps_turns_mismatch    `request_caps` exists but its length differs
                                from `len(per_turn)` in EITHER direction
                                (longer or shorter) — a caller cannot claim
                                one cap per turn when the two sequences do
                                not even have the same length.
      3. no_turns                `per_turn` is empty (zero turns at all).
      4. framework_retry          `attempts` (the CLIENT's own attempt-
                                segment count — `PacedClient.attempts`,
                                `None` for a client that does not track it)
                                is `> 1`: `Environment.run_rollout` retried
                                (InfraError/InvalidModelResponseError) with
                                a FRESH state while the SAME client kept
                                billing the provider — the row's own
                                `trajectory`/`per_turn` reflect only the
                                LAST attempt, so its accounting cannot be
                                trusted as "the whole rollout's spend".
      5. usage_missing            some turn's `input_tokens`/`output_tokens`
                                is `None`.
      6. usage_not_integer        some turn's usage value is present but not
                                a real non-negative `int` (a bool, a string,
                                a float, a negative number) — checked with
                                `_valid_nonneg_int`, which never raises.
      7. usage_total_missing      `reported_output_tokens` is `None`.
      8. completion_exceeds_cap   some turn's `output_tokens` is more than
                                that SAME turn's own `request_max_tokens`.
      9. ceiling_exceeded         the SUM of every turn's `output_tokens`
                                is more than `max_total_completion_tokens`
                                (only checked when that ceiling is `> 0`;
                                an unset/disabled ceiling has no bound to
                                exceed).
      10. cumulative_mismatch     `reported_output_tokens` (coerced to `int`
                                 — the framework's own sums come back as
                                 floats, e.g. `150.0`; a non-numeric value
                                 here is `usage_not_integer` instead, never
                                 an uncaught `ValueError`) does not EXACTLY
                                 equal the independently-summed per-turn
                                 `output_tokens`.
      11. wire_caps_incomplete    `wire_caps` is not `None` (the real
                                 `OpenAIChatCompletionsClient` family always
                                 supplies it; a scripted test client that
                                 never sets it makes checks 11-13 not-
                                 applicable rather than failing) but is
                                 SHORTER than `per_turn`, or contains a
                                 `None` entry within the first `len(per_turn)`
                                 slots — a gap the per-turn wire check below
                                 cannot reliably interpret.
      12. extra_wire_request      `wire_caps` is LONGER than `per_turn`
                                 — the client made
                                 provider requests the trajectory's usage
                                 never accounts for. The previous code
                                 examined only the first `len(per_turn)`
                                 entries and let the surplus pass — but a
                                 surplus request is billed, so it is
                                 potentially unaccounted SPEND, not
                                 harmless extra evidence. The requirement
                                 is exact equality for the surviving
                                 attempt: `len(wire_caps) == len(per_turn)
                                 == len(request_caps)` (the third equality
                                 is check 2).
      13. wire_cap_mismatch       (only reached with an EXACTLY-sized
                                 `wire_caps`) some turn's actual wire-level
                                 cap (the legacy client's own `normalize_
                                 sampling_args` result, `max_completion_
                                 tokens` else `max_tokens`) disagrees with
                                 that SAME turn's declared
                                 `request_max_tokens`.
      14. request_count_mismatch  `requests` (the client's own per-HTTP-
                                 attempt log, `None` for a client that does
                                 not keep one) is present and the number of
                                 SUCCEEDED requests belonging to the
                                 surviving attempt is not `len(per_turn)`.
                                 429/error attempts are not counted: they
                                 carry no billed completion and no turn.
      15. env_<code>              (checked LAST, only if nothing above
                                 already found a problem): `env_code`
                                 (`out.get("piv_budget_accounting_invalid")`)
                                 is truthy — the OTHER builder's own
                                 package-level fail-closed signal, reported
                                 VERBATIM as `env_<code>` when `<code>` is
                                 one of `ENV_BUDGET_ACCOUNTING_CODES`, else
                                 the fixed `env_unrecognized` fallback (never
                                 an arbitrary interpolated string — the
                                 prose lives in `row["budget_accounting_
                                 detail"]`, set separately in `one_rollout`,
                                 never inside this status string).

    `framework_retry` (check 4) is now decided by ATTEMPT IDENTITY, not only
    by the prompt-shape heuristic: `attempts` counts the
    distinct attempt nonces the client bound each provider request to, and
    `requests`/`rollout_id`, when given, additionally require every billed
    request to belong to the surviving attempt's own rollout id. The
    prompt-shape detector remains as an alarm on the row.

    The characters-per-token heuristic is NOT here any more:
    see `compute_budget_suspicion`.

    Never raises on a short/ragged `per_turn`, on non-integer usage, or on a
    non-numeric `reported_output_tokens` — every access is bounds/type-
    checked — because a rollout that ended early or oddly (a provider
    error inside a turn, a protocol termination, a malformed hand-built
    test row) is exactly the kind of row this function exists to flag
    rather than crash on.
    """
    if request_caps is None:
        return "INVALID/no_request_caps"
    if len(request_caps) != len(per_turn):
        return "INVALID/caps_turns_mismatch"
    if not per_turn:
        return "INVALID/no_turns"
    if attempts is not None and attempts > 1:
        return "INVALID/framework_retry"
    # Attempt identity: every BILLED request must belong to
    # the attempt whose trajectory this row carries. A request bound to a
    # different rollout id is a discarded attempt's spend.
    if requests is not None and rollout_id is not None:
        foreign = {r.get("rollout_id") for r in requests
                   if r.get("rollout_id") is not None and r.get("rollout_id") != rollout_id}
        if foreign:
            return "INVALID/framework_retry"
        if len({r.get("attempt_id") for r in requests if r.get("attempt_id") is not None}) > 1:
            return "INVALID/framework_retry"

    for turn in per_turn:
        if turn.get("input_tokens") is None or turn.get("output_tokens") is None:
            return "INVALID/usage_missing"
    for turn in per_turn:
        if not _valid_nonneg_int(turn.get("input_tokens")) or not _valid_nonneg_int(turn.get("output_tokens")):
            return "INVALID/usage_not_integer"
    if reported_output_tokens is None:
        return "INVALID/usage_total_missing"
    for turn in per_turn:
        cap = turn.get("request_max_tokens")
        if cap is not None and turn["output_tokens"] > cap:
            return "INVALID/completion_exceeds_cap"

    cumulative_completion = sum(turn["output_tokens"] for turn in per_turn)
    if max_total_completion_tokens is not None and max_total_completion_tokens > 0 \
            and cumulative_completion > max_total_completion_tokens:
        return "INVALID/ceiling_exceeded"
    # `int(...)` TRUNCATED a non-integral
    # float, so a reported total of 150.9 compared equal to a true sum of
    # 150. Accept integers and EXACTLY integral numeric representations
    # only; reject bools (`isinstance(True, int)` is `True`) and strings.
    if isinstance(reported_output_tokens, bool):
        return "INVALID/usage_not_integer"
    if isinstance(reported_output_tokens, int):
        reported_int = reported_output_tokens
    elif isinstance(reported_output_tokens, float) and reported_output_tokens.is_integer():
        reported_int = int(reported_output_tokens)
    else:
        return "INVALID/usage_not_integer"
    if reported_int != cumulative_completion:
        return "INVALID/cumulative_mismatch"

    if wire_caps is not None:
        if len(wire_caps) < len(per_turn) or any(w is None for w in wire_caps[:len(per_turn)]):
            return "INVALID/wire_caps_incomplete"
        if len(wire_caps) > len(per_turn):
            return "INVALID/extra_wire_request"
        for index, turn in enumerate(per_turn):
            wire = wire_caps[index] or {}
            wire_cap = wire.get("max_completion_tokens")
            if wire_cap is None:
                wire_cap = wire.get("max_tokens")
            if wire_cap != turn.get("request_max_tokens"):
                return "INVALID/wire_cap_mismatch"

    if requests is not None:
        attempt_ids = [r.get("attempt_id") for r in requests if r.get("attempt_id") is not None]
        surviving = attempt_ids[-1] if attempt_ids else None
        succeeded = [r for r in requests if r.get("status") == "ok"
                     and (surviving is None or r.get("attempt_id") == surviving)]
        if len(succeeded) != len(per_turn):
            return "INVALID/request_count_mismatch"

    if env_code:
        code = env_code if env_code in ENV_BUDGET_ACCOUNTING_CODES else ENV_UNRECOGNIZED_CODE
        return f"INVALID/env_{code}"

    return "VALID"


# ---------------------------------------------------------------------------
# ONE pure archived-row validator. The writer runs it on
# the row it just produced; `tests/arm_table.py` runs it on every row it
# reads and NEVER trusts a stored `budget_accounting` string. A malformed or
# tampered archive row that merely CLAIMS "VALID" while carrying present-but-
# impossible numbers does not enter any table.
# ---------------------------------------------------------------------------

ROW_VALIDATION_STATUSES = ("VALID", "VALID/derived", "INVALID")

# Reasons a row is INVALID. The accounting codes are reported verbatim from
# `compute_budget_accounting` (without the "INVALID/" prefix); these are the
# additional predicates only an ARCHIVED row can be checked for.
ROW_VALIDATION_EXTRA_CODES = (
    "quarantined",                 # a provider-failed row: never an accounting-valid attempt
    "artifact_bound_without_digests",
    "artifact_bound_with_reason",
    "artifact_unbound_without_reason",
    "submitted_not_boolean",
    "stored_status_invalid",       # the LIVE instrument recorded an INVALID status we cannot re-derive
                                   # (the env's own code path) -- believed, never overridden
)

# Why a row can only be VALID/**derived**: a predicate this row carries no
# evidence for. Diagnostic rows may carry these; a CONFIRMATORY table may not
# (primary estimates require the corrected native cap/usage capture).
ROW_DERIVATION_GAPS = (
    "no_recorded_status",      # written before `budget_accounting` existed
    "no_wire_caps",            # no provider-bound cap capture to compare against
    "no_attempts",             # no attempt-identity/segment count
    "no_requests",             # no per-HTTP-attempt log
    "no_tool_call_chars",      # per-turn rows predate the tool-call character count
)


def _derivation_gaps(row: dict) -> list[str]:
    per_turn = row.get("per_turn") or []
    gaps = []
    if "budget_accounting" not in row:
        gaps.append("no_recorded_status")
    if row.get("wire_caps") is None:
        gaps.append("no_wire_caps")
    if row.get("attempts") is None:
        gaps.append("no_attempts")
    if row.get("requests") is None:
        gaps.append("no_requests")
    if per_turn and any("tool_call_chars" not in t for t in per_turn):
        # Post-run correction, 2026-09-01 (reclassify under
        # corrected rules rather than re-spend provider calls). The confirm1v4
        # writer COMPUTED the tool-call character count but omitted the key
        # from the per-turn dict — a writer bug found at analysis, symmetric
        # across arms and outcome-independent. The field feeds the
        # PLAUSIBILITY floor (suspicion, never validity), so
        # its absence cannot demote a row that carries every VALIDITY
        # evidence: on such a row the floor simply counts fewer characters,
        # which only makes suspicion LESS likely to fire (conservative for
        # exclusion, lenient only for a diagnostic label). It remains a
        # derivation gap when any other gap is present (a genuinely
        # old-instrument row).
        if gaps:
            gaps.append("no_tool_call_chars")
    return gaps


def validate_row(row: dict) -> tuple[str, list[str]]:
    """`(status, reasons)` — re-derives EVERY validity predicate from the
    archived row's OWN fields. `status` is one of
    `ROW_VALIDATION_STATUSES`; `reasons` is a list of codes (accounting codes
    from `BUDGET_ACCOUNTING_CODES`, plus `ROW_VALIDATION_EXTRA_CODES`) for an
    INVALID row, or the `ROW_DERIVATION_GAPS` that forced `VALID/derived`.

    Re-derived here, from the archive, not read off the row's own verdict:

      - integer types, including `completion_tokens` as the reported total
        (bools and non-integral floats rejected);
      - per-turn completion <= that turn's own cap;
      - cumulative equality between the reported total and the per-turn sum;
      - the episode output ceiling;
      - exact wire cardinality and per-turn wire-cap equality;
      - request/turn cardinality and single-attempt identity;
      - artifact/digest consistency where the fields are present.

    Character-per-token plausibility is NOT a validity predicate:
    `compute_budget_suspicion` reports it separately and `arm_table`
    shows every table with and without suspicious rows.

    A row whose LIVE status was `INVALID/...` stays INVALID even when the
    archive alone cannot reproduce the reason — the env's own fail-closed
    codes (`INVALID/env_*`) are evidence this validator has no access to, so
    they are believed rather than overridden. The converse never holds: a
    stored "VALID" proves nothing here.
    """
    reasons: list[str] = []
    if row.get("quarantined"):
        return "INVALID", ["quarantined"]

    per_turn = row.get("per_turn") or []
    caps = [t.get("request_max_tokens") for t in per_turn]
    request_caps = None if (not per_turn or any(c is None for c in caps)) else caps
    status = compute_budget_accounting(
        request_caps if per_turn else [],
        per_turn,
        row.get("wire_caps"),
        row.get("budget_accounting_env_code"),
        row.get("completion_tokens"),
        row.get("max_total_completion_tokens"),
        row.get("attempts"),
        requests=row.get("requests"),
        rollout_id=row.get("rollout_id"),
    )
    if status != "VALID":
        reasons.append(status.split("/", 1)[1] if "/" in status else status)

    # The live instrument's own verdict is believed when it says INVALID.
    stored = row.get("budget_accounting")
    if isinstance(stored, str) and stored.startswith("INVALID/"):
        reasons.append("stored_status_invalid")

    # Artifact / digest consistency, where the fields are present at all.
    artifact = row.get("artifact")
    if artifact == "BOUND":
        if not row.get("artifact_stored_bytes_digest") or not row.get("artifact_logical_text_digest"):
            reasons.append("artifact_bound_without_digests")
        if row.get("artifact_reason") is not None:
            reasons.append("artifact_bound_with_reason")
    elif artifact in ("NO_ARTIFACT", "ARTIFACT_MISMATCH"):
        if not row.get("artifact_reason"):
            reasons.append("artifact_unbound_without_reason")
    if "submitted" in row and not isinstance(row.get("submitted"), bool):
        reasons.append("submitted_not_boolean")

    if reasons:
        return "INVALID", sorted(set(reasons))
    gaps = _derivation_gaps(row)
    if gaps:
        return "VALID/derived", gaps
    return "VALID", []


def row_suspicion(row: dict) -> str | None:
    """The archived row's suspicion code, re-derived (never read off the
    stored field) so `arm_table` can split every table with and without
    suspicious rows without trusting the writer.

    `window_ledger_gap` is re-derived the same way: from the archived
    attempts themselves, each of which records `ledger_write_failed` when its
    line could not reach the shared provider-window ledger (F5). A row whose
    window evidence is incomplete is SUSPICIOUS — its 429s cannot be
    classified from an observation that was never recorded — but it is not
    INVALID: a bookkeeping failure does not touch its token accounting."""
    gap = any(isinstance(r, dict) and r.get("ledger_write_failed")
              for r in row.get("requests") or [])
    return compute_budget_suspicion(row.get("per_turn") or [],
                                    row.get("budget_accounting_suspicious_env_code"),
                                    window_ledger_gap=gap)


SDK_MAX_RETRIES = 0


def client_config(key_var: str, base_url: str, timeout: float, connect_timeout: float = 15.0):
    """THE client configuration this instrument uses — `max_retries=0`.

    `ClientConfig.max_retries` defaults to **10**, and
    `verifiers.legacy.utils.client_utils.setup_openai_client` passes it
    straight into `AsyncOpenAI(max_retries=...)`, i.e. BELOW
    `get_native_response`. Those retries are invisible to the wire capture,
    to `wire_caps`, to `requests` and to the trajectory — while a late 200
    that the SDK discards after its own timeout has still been generated and
    BILLED by the provider. That is exactly the unaccounted spend the exact
    wire-cardinality rule exists to catch, so the retries are turned off
    rather than merely measured: retrying is a decision this instrument makes
    explicitly, in `PacedClient`'s own 429 loop, where every attempt is
    recorded on the row.
    """
    from verifiers.legacy.types import ClientConfig
    return ClientConfig(client_type="openai_chat_completions", api_key_var=key_var,
                        api_base_url=base_url, timeout=timeout, connect_timeout=connect_timeout,
                        max_retries=SDK_MAX_RETRIES)


def compute_prompt_schema_digest(env_mod) -> str:
    """sha256 over `SYSTEM_PROMPT` plus the JSON of the native tool
    definitions the client would actually send — `env.tool_defs` (the
    framework's own provider-agnostic `vf.Tool` list `StatefulToolEnv.
    add_tool` built) run through `to_native_tool`, the SAME door the real
    client uses to build the wire tool schema. This is an INDEPENDENT
    stand-in for `episode_contract_
    digest()` — a literal hash of the exact system prompt and native tool
    schema THIS checkout serves — computed at load time from THIS package,
    not from state, so it exists even before `piv_episode_contract_digest`
    lands.

    `env.tool_defs` does not depend on which selector/world is loaded (the
    tool surface is fixed: `list_files, read_file, grep, run_beancount,
    write_ledger, submit`), so the unselected default environment is
    representative. Building a client from a dummy, unreachable config and
    calling `to_native_tools` never touches the network — `to_native_tool`
    is pure local dict construction (verified against `OpenAIChatCompletions
    Client.to_native_tool`/`setup_openai_client`).
    """
    from verifiers.legacy.types import ClientConfig

    env = env_mod.load_environment()
    client_cls = make_client_cls(0.0, True)
    dummy = ClientConfig(client_type="openai_chat_completions", api_key_var="PIV_PROMPT_DIGEST_NO_SUCH_KEY_VAR",
                         api_base_url="https://example.invalid/v1", timeout=5.0, connect_timeout=5.0,
                         max_retries=0)
    client = client_cls(dummy)
    native_tools = asyncio.run(client.to_native_tools(env.tool_defs))
    payload = json.dumps({"system_prompt": env_mod.SYSTEM_PROMPT, "native_tools": native_tools},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def bind_register(workspace, delivery_path, env_mod) -> dict:
    """The SECOND deliverable's binding, on the same footing as the ledger's
    and under its own key names, for a cash-application rollout.

    Returns `{}` — no keys at all — unless `delivery.json` exists, parses and
    carries the `application` member the scorer writes only for the family.
    So a legacy row is byte-for-byte the row it was before the family
    existed, and a family row always says what became of the register.

    Keys: `application` in {"BOUND", "ARTIFACT_MISMATCH", "NO_ARTIFACT"},
    `application_reason` (None when BOUND; the receipt's own status word
    when NO_ARTIFACT), `application_status` and `application_revision` from
    the receipt, and the register's own digests when BOUND.

    Like the ledger's half, this compares what is ON DISK at the public path
    against the digests the SCORER recorded — it never re-derives, re-parses
    or re-canonicalises the register. `_publish` writes the canonical
    register at `APPLICATION_FILE` and removes the path when there is
    nothing to publish, so a file present with a NO_ARTIFACT receipt (or
    absent with a published one) is a real inconsistency and is reported as
    a mismatch rather than smoothed over.

    The one thing it cannot see: a manifest that exists but does not parse
    is `{}` here, because nothing in it says whether the rollout was a
    family rollout at all. `bind_artifact` reports that manifest loudly on
    its own arm for every phase except REJECTED, where it has never read the
    manifest.
    """
    if not workspace or not Path(delivery_path).is_file():
        return {}
    try:
        _delivery, application = env_mod._read_publication(
            Path(delivery_path).read_text(encoding="utf-8"))
    except Exception:                                                            # noqa: BLE001
        return {}
    if application is None:
        return {}
    row = {"application_status": application.status, "application_revision": application.revision}
    path = Path(workspace) / env_mod.APPLICATION_FILE
    if application.artifact_stored_bytes_digest == env_mod.NO_ARTIFACT:
        if path.exists():
            return {**row, "application": "ARTIFACT_MISMATCH",
                    "application_reason": f"{env_mod.APPLICATION_FILE} is on disk but the receipt "
                                          f"published no register"}
        return {**row, "application": "NO_ARTIFACT", "application_reason": application.status}
    if not path.is_file():
        return {**row, "application": "ARTIFACT_MISMATCH",
                "application_reason": f"the receipt published a register but {env_mod.APPLICATION_FILE} "
                                      f"is missing"}
    now = env_mod.digests_of(path.read_bytes())                                  # the env's own digest function
    if (now["stored_bytes_digest"], now["logical_text_digest"]) != (
            application.artifact_stored_bytes_digest, application.artifact_logical_text_digest):
        return {**row, "application": "ARTIFACT_MISMATCH",
                "application_reason": f"{env_mod.APPLICATION_FILE} does not match the receipt's register digests"}
    return {**row, "application": "BOUND", "application_reason": None,
            "application_stored_bytes_digest": now["stored_bytes_digest"],
            "application_logical_text_digest": now["logical_text_digest"]}


def bind_artifact(out: dict, env_mod) -> dict:
    """Bind THIS rollout's delivered artifact from its own state — never by
    scanning the temp directory (`newest_workspace()` is gone).

    `out` must come from `evaluate(..., state_columns=BASE_STATE_COLUMNS)`
    (or a superset). The workspace, the phase and the delivery receipt are
    all this rollout's own: the workspace path is the one THIS `env.evaluate`
    call minted (returned in THIS call's own `out`, never a global lookup),
    and `delivery.json` is read from inside that exact directory, written
    there by the scorer for THIS rollout's own commitment
    (`_publish`/`DeliveryReceipt` in beancount_ledger.py) — so two rollouts
    running concurrently, each with their own `env` and their own workspace,
    cannot cross-contaminate: there is no shared state to scan.

    Returns `artifact` in {"BOUND", "ARTIFACT_MISMATCH", "NO_ARTIFACT"} plus
    `artifact_reason` (None when BOUND), `rollout_id`, `revision`, `phase`,
    `submitted`, `workspace`, and — when BOUND — the artifact's own digests
    (equal to `piv_delivery`'s by construction of the match).

    `artifact` is the LEDGER's binding, under contract 4 and contract 5
    alike. A cash-application rollout has a second deliverable, and its
    binding rides along in the `application*` keys `bind_register` above
    builds — absent entirely on a legacy row.

    NO_ARTIFACT reasons: `no_write` (phase ACTIVE_NO_CANDIDATE — nothing was
    ever stored), `write_refused` (phase ACTIVE_REJECTED — the last stored
    candidate did not parse/load, so the scorer's own `_publish` removes the
    public ledger entirely; there is nothing to read even in principle), or
    `policy_blocked` (an ACCEPTED, loadable candidate that the scorer still
    would not render — unexplained entries, a changed option, a dropped
    lifecycle directive; `_publish` removes the artifact for this outcome
    too). The spec that commissioned this rewrite named only the first two;
    `policy_blocked` is a real third NO_ARTIFACT case the scorer's own
    outcome vocabulary distinguishes (`OUTCOME_POLICY_BLOCKED`), so it is
    reported rather than folded into one of the other two names. `not_scored`
    covers the residual case where a candidate was accepted but the rubric
    never got to score it at all (an earlier evaluator failure) — `piv_score`
    absent and no `delivery.json` on disk.
    """
    workspace = out.get("workspace")
    phase = str(out.get("piv_phase") or env_mod.EpisodePhase.NO_CANDIDATE.value)
    result = {
        "rollout_id": out.get("piv_rollout_id"),
        "revision": out.get("piv_revision", 0) or 0,
        "phase": phase,
        "submitted": phase == env_mod.EpisodePhase.TERMINAL.value,
        "workspace": workspace,
    }
    if not workspace or phase == env_mod.EpisodePhase.NO_CANDIDATE.value:
        return {**result, "artifact": "NO_ARTIFACT", "artifact_reason": "no_write"}
    delivery_path = Path(workspace) / "delivery.json"
    # The register's binding is computed from the SAME manifest, before the
    # ledger's phase can short-circuit, so a family rollout whose ledger was
    # refused still says what became of its second deliverable.
    result = {**result, **bind_register(workspace, delivery_path, env_mod)}
    if phase == env_mod.EpisodePhase.REJECTED.value:
        return {**result, "artifact": "NO_ARTIFACT", "artifact_reason": "write_refused"}
    # ACTIVE_CANDIDATE or TERMINAL: the last stored write was accepted. What,
    # if anything, was delivered is read from the scorer's OWN receipt, never
    # re-derived here.
    if not delivery_path.is_file():
        return {**result, "artifact": "NO_ARTIFACT", "artifact_reason": "not_scored"}
    try:
        # Through the SCORER'S OWN reader, never `DeliveryReceipt.from_json`
        # directly. A cash-application manifest carries an extra top-level
        # `application` member and `DeliveryReceipt` (frozen with
        # `candidate/1`) reads the top level by EXACT KEY SET, so the frozen
        # reader raises on every family manifest — which this function then
        # swallowed into "ARTIFACT_MISMATCH: delivery.json unreadable",
        # recording a perfect 1.0 family rollout as a failed binding.
        # `_read_publication` pops that member first and hands back both
        # halves; a legacy manifest reads identically either way.
        delivery, _application = env_mod._read_publication(delivery_path.read_text(encoding="utf-8"))
        delivery.verify()
    except Exception as exc:                                                     # noqa: BLE001
        return {**result, "artifact": "ARTIFACT_MISMATCH",
                "artifact_reason": f"delivery.json unreadable: {type(exc).__name__}: {exc}"[:200]}
    if delivery.rollout_id != result["rollout_id"]:
        return {**result, "artifact": "ARTIFACT_MISMATCH",
                "artifact_reason": "delivery.json inside this rollout's own workspace names another rollout id"}
    if not delivery.renderable:
        return {**result, "artifact": "NO_ARTIFACT", "artifact_reason": f"policy_blocked ({delivery.outcome})"}
    ledger_path = Path(workspace) / env_mod.LEDGER
    if not ledger_path.is_file():
        return {**result, "artifact": "ARTIFACT_MISMATCH",
                "artifact_reason": "delivered outcome but ledger.beancount is missing"}
    raw = ledger_path.read_bytes()
    now = env_mod.digests_of(raw)                                                # the same digest function the env uses
    if (now["stored_bytes_digest"], now["logical_text_digest"]) == (
            delivery.artifact_stored_bytes_digest, delivery.artifact_logical_text_digest):
        return {**result, "artifact": "BOUND", "artifact_reason": None,
                "artifact_stored_bytes_digest": now["stored_bytes_digest"],
                "artifact_logical_text_digest": now["logical_text_digest"]}
    return {**result, "artifact": "ARTIFACT_MISMATCH",
            "artifact_reason": "ledger.beancount does not match the delivery receipt's artifact digests"}


def candidate_vs_original(candidate_logical_digest, original_raw: bytes, env_mod) -> dict:
    """Whether the last ACCEPTED candidate is textually identical to the
    UNTOUCHED original ledger this episode was served — the question an
    undelivered episode otherwise leaves unanswerable: `bind_artifact` above
    reports NO_ARTIFACT (nothing on the public path, no `delivery.json`) for
    every one of `no_write`, `write_refused`, `policy_blocked` and
    `not_scored`, and none of those carries what the accepted candidate's
    CONTENT actually was — so "the agent preserved the books" and "the agent
    altered the books but never got to submit" were, until this function,
    the same row.

    `original_raw` must be the SERVED public ledger bytes — `env.public_
    files[env_mod.LEDGER]`, fixed at world construction, the same bytes
    `Environment._workspace` writes into a fresh workspace before any tool
    call runs — hashed through `env_mod.digests_of`, the ONE digest function
    the environment itself uses for both the original mount and every
    `write_ledger`/`submit` receipt (`beancount_ledger.py`'s `digests_of`,
    `logical_text`, `_domain_digest`). Never a bespoke hash here: a
    from-scratch digest would not be comparable to `candidate_logical_
    digest`, which the environment computed with that same function.

    `candidate_logical_digest` is the caller's own `piv_logical_text_digest`
    (installed by `env_response` from the raw bytes on disk at the moment of
    the last ACCEPTED write, after independently re-deriving and matching
    the tool's own attestation — see `beancount_ledger.py`'s `env_response`,
    `for key in expected: state[f"piv_{key}"] = expected[key]`), or `None`
    when no write was ever accepted.

    `candidate_equals_original` is `None` exactly when there is no candidate
    to compare — an episode that never wrote anything must never report a
    false "no" for a comparison it cannot make.
    """
    original_logical_digest = env_mod.digests_of(original_raw)["logical_text_digest"]
    equals = None if candidate_logical_digest is None else (candidate_logical_digest == original_logical_digest)
    return {"original_logical_digest": original_logical_digest, "candidate_equals_original": equals}


def breakdown(selector: str, delivered: str) -> dict:
    """The scorer's own account of the delivered ledger, through the harness
    that the adversary pass uses (real loop, real contract). Only ever
    called over a BOUND artifact (never a mismatched one — that would be
    scoring bytes we cannot prove this rollout delivered)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import score_payload as SP
    SP.set_task(selector)
    out = SP.assess(delivered)
    # `complete` (`state["piv_result"].complete`, via `score_payload.
    # run_payload`/`assess`) is the scorer's own semantic-completeness flag —
    # distinct from `reward`/`verdict` — and is the third conjunct of
    # `CORRECT_DELIVERY` in `arm_table.py`: `artifact ==
    # "BOUND"` and `reward == 1.0` and `breakdown["complete"] is True`.
    return {k: out.get(k) for k in ("total", "verdict", "outcome", "renderable", "components", "penalties",
                                    "protocol_reason", "protocol_detail", "gated", "same_books_as_golden",
                                    "complete")}


def make_client_cls(min_interval: float, reasoning_replay: bool, window_ledger=None,
                    provider: str | None = None, cell: str | None = None,
                    session_id: str | None = None):
    """A `Client` subclass factory: provider pacing/retry plus the reasoning-
    replay projection, both bound to this run's settings rather than closed
    over `argparse` `Namespace` — so a fake client under test can inject the
    same class shape without a live `args` object.

    `window_ledger` is the path of the SHARED provider-window
    ledger. When it is given, every HTTP attempt is appended to it and the
    pacing interval is enforced against the LEDGER's last entry for this
    provider rather than against this process's own `_last` — a scheduled
    cell is a fresh subprocess, so the process's memory of "when did we last
    call" is always zero at the moment it matters most, while the provider's
    rolling window is not. `cell` is the output tag, so a 429's trailing
    window can be split into this cell's own contribution and the carry-over
    from the cell that ran before it.

    The projection lives ONLY in `to_native_prompt`, and only on the copy of
    the messages built for the wire: `super().to_native_prompt(messages)`
    already returns a FRESH list of freshly-constructed native dicts (the
    base client builds one `ChatCompletionAssistantMessageParam` per message,
    from scratch, every call) — so popping `reasoning_content` off that list
    cannot touch the caller's `messages` argument, which is the rollout
    state's own trajectory. That is asserted directly in
    `test_measure_budget.py`'s projection witness (item 4c): the ORIGINAL
    messages objects are unchanged after the call, so `reasoning_content`
    stripped from the wire is never stripped from the audit record.
    """
    import openai
    import verifiers.legacy.clients.openai_chat_completions_client as _oai_client_mod
    from verifiers.legacy.clients.openai_chat_completions_client import OpenAIChatCompletionsClient

    # The ledger is a PROVIDER-wide record; a cell that did not name its
    # provider still writes under whichever one `configure_provider` selected.
    provider = provider or PROVIDER

    class PacedClient(OpenAIChatCompletionsClient):
        _last = 0.0
        # Serializes the module-level monkeypatch window below across
        # concurrent calls on the SAME event loop. `measure_budget.py`
        # always runs with `max_concurrent=1`, so this never actually
        # contends in practice; it exists so the wire-capture mechanism is
        # correct even if that assumption is ever relaxed, rather than
        # silently racing two calls' captured bodies together.
        _patch_lock = asyncio.Lock()

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            # One entry per successful `get_native_response` call, in call
            # order, spanning EVERY framework attempt (not just the last) —
            # so `wire_caps[i]` lines up with trajectory step `i` WITHIN one
            # attempt: the `max_tokens`/`max_completion_
            # tokens` field(s) the legacy client's OWN `normalize_sampling_
            # args` (inside `get_native_response`, this module's nested
            # function — not `Client.get_response`, which passes
            # `sampling_args` through untouched) put on the wire, captured
            # by monkeypatching `post_chat_completion_with_routed_experts_
            # sidecar` — the last function this client calls before the
            # HTTP POST — for the duration of exactly one call, restored in
            # a `finally` whether the call succeeded, retried or raised.
            # `provider_model`/`system_fingerprint` are read off the RAW
            # parsed response this wrapper sees, before `from_native_
            # response` discards both.
            self.wire_caps: list[dict] = []
            # Adversarial-review follow-up: `Environment.run_rollout`
            # retries a WHOLE rollout attempt on InfraError/
            # InvalidModelResponseError with a FRESH state, but the SAME
            # `client` instance keeps being reused across attempts — so a
            # provider call from a DISCARDED earlier attempt still bills
            # real tokens that never show up in the FINAL (surviving)
            # attempt's own `trajectory`. Detected here, at the ONLY layer
            # that sees every attempt: a request whose prompt is back down
            # to "system + user only" (<= 2 messages) after a STRICTLY
            # LONGER one starts a new segment. `_segment_starts` records the
            # `wire_caps` index where each detected segment begins;
            # `attempts` (a property) is simply how many segments were
            # seen; `last_segment_wire_caps` (a property) is the slice of
            # `wire_caps` belonging to the LAST (surviving) segment only —
            # what `one_rollout` must actually zip against `per_turn`,
            # since `out["trajectory"]` only ever reflects that last
            # attempt. `billed_input_tokens_all_attempts`/
            # `billed_output_tokens_all_attempts` sum EVERY attempt's own
            # provider usage, including discarded ones — the TRUE cost of
            # this rollout, as opposed to `token_usage`'s cumulative sum
            # (which the framework computes from the final state's
            # trajectory alone and therefore UNDERCOUNTS whenever a retry
            # happened).
            self._segment_starts: list[int] = []
            self._last_prompt_len: int | None = None
            self.billed_input_tokens_all_attempts: int = 0
            self.billed_output_tokens_all_attempts: int = 0
            # ATTEMPT IDENTITY. The prompt-shape detector
            # above is a heuristic alarm; the authoritative boundary is an
            # explicit identity bound to every provider request. The
            # framework passes the rollout `state` down to
            # `get_native_response` (`Environment.get_model_response` ->
            # `Client.get_response(..., state=state)` -> `**kwargs`), and
            # `run_rollout` retries with a FRESH state dict, so a nonce
            # stamped into the state on the first request of an attempt is
            # unique to that attempt by construction. It is stamped under an
            # instrument-only key that is never requested as a state column
            # and never rendered into a prompt, so it is not model-facing.
            # `state["piv_rollout_id"]` is recorded alongside it, but it
            # cannot BE the identity: the package mints it lazily in
            # `_workspace()`, so the FIRST request of every attempt is made
            # before it exists.
            self.requests: list[dict] = []
            self._attempt_ids: list[str] = []
            self._turn_in_attempt: dict = {}

        @property
        def attempts(self) -> int:
            """How many distinct framework attempts billed the provider —
            by ATTEMPT IDENTITY, falling back to the prompt-shape segments
            for a caller that supplied no state at all."""
            if self._attempt_ids:
                return len(self._attempt_ids)
            return len(self._segment_starts)

        @property
        def attempts_prompt_shape(self) -> int:
            """The heuristic detector's own count, kept as an ALARM: a
            disagreement with `attempts` means one of the two assumptions
            (state freshness per attempt, or "the prompt returns to
            system+user") no longer holds."""
            return len(self._segment_starts)

        @property
        def last_segment_wire_caps(self) -> list[dict]:
            if self._attempt_ids:
                surviving = self._attempt_ids[-1]
                return [w for w in self.wire_caps if w.get("attempt_id") == surviving]
            if not self._segment_starts:
                return list(self.wire_caps)
            return self.wire_caps[self._segment_starts[-1]:]

        def _attempt_identity(self, state) -> tuple:
            """`(attempt_id, rollout_id)` for the request about to be made.
            `attempt_id` is `None` only when the caller passed no state
            (a scripted client in a unit test)."""
            if not isinstance(state, dict):
                return None, None
            attempt_id = state.get(ATTEMPT_NONCE_KEY)
            if attempt_id is None:
                attempt_id = state[ATTEMPT_NONCE_KEY] = uuid.uuid4().hex
            if attempt_id not in self._attempt_ids:
                self._attempt_ids.append(attempt_id)
            return attempt_id, state.get("piv_rollout_id")

        async def get_native_response(self, *a, **k):
            prompt = a[0] if a else k.get("prompt")
            current_len = len(prompt) if prompt is not None else 0
            is_new_segment = self._last_prompt_len is None or (current_len <= 2 and self._last_prompt_len > 2)
            self._last_prompt_len = current_len
            # The two detectors are kept INDEPENDENT on purpose: the
            # prompt-shape segments are an alarm that must be able to
            # DISAGREE with the attempt identity, and would be worthless if
            # the identity fed them.
            if is_new_segment:
                self._segment_starts.append(len(self.wire_caps))
            attempt_id, rollout_id = self._attempt_identity(k.get("state"))
            turn = self._turn_in_attempt[attempt_id] = self._turn_in_attempt.get(attempt_id, 0) + 1
            # The size of the request ABOUT TO BE SENT, estimated from the
            # native payload the client holds right now. This is the ONLY
            # size evidence a rejected request ever has: a 429 bills nothing.
            estimated = estimate_request_tokens(prompt, k.get("tools") or (a[3] if len(a) > 3 else None),
                                                k.get("sampling_args") or (a[2] if len(a) > 2 else None))

            def _log(status: str, seconds: float, billed_in=None, billed_out=None, attempt_no=1,
                     error: dict | None = None, window: dict | None = None, sent_at: float | None = None,
                     sent_monotonic: float | None = None, prospective: dict | None = None,
                     ledger_unhealthy: str | None = None) -> None:
                ledger_failure = None
                entry = {"turn": turn, "attempt": attempt_no, "status": status,
                         "seconds": round(seconds, 3), "attempt_id": attempt_id,
                         "rollout_id": rollout_id,
                         "billed_input_tokens": billed_in, "billed_output_tokens": billed_out,
                         # Absolute AND monotonic time on every
                         # attempt. The absolute clock is what lines two cells'
                         # requests up in one provider window; the monotonic one
                         # is what measures a duration across a clock change.
                         "t": sent_at, "t_monotonic": sent_monotonic,
                         "estimated_request_tokens": estimated}
                if error:
                    entry.update(error)
                if window is not None:
                    # The observed rolling window AS IT WAS when the provider
                    # refused: computed at the moment of the failure, archived
                    # on the row, and never recomputed later from a file that
                    # has since grown.
                    entry["provider_window"] = window
                if prospective is not None:
                    # ... and the same window INCLUDING the request being
                    # refused, labelled. Two archived
                    # windows, neither standing in for the other.
                    entry["provider_window_prospective"] = prospective
                if ledger_unhealthy is not None:
                    entry["window_ledger_unhealthy"] = ledger_unhealthy
                try:
                    window_ledger_append(window_ledger, {
                        "t": sent_at, "provider": provider,
                        "model": k.get("model") or (a[1] if len(a) > 1 else None),
                        "status": status, "cell": cell, "session_id": session_id,
                        "attempt_id": attempt_id, "estimated_request_tokens": estimated,
                        "billed_input_tokens": billed_in, "billed_output_tokens": billed_out})
                except WindowLedgerUnavailable as exc:
                    # The request has already been made; killing the rollout
                    # here would lose a paid-for observation. The GAP is what
                    # must not be silent, so it is stamped on the attempt and
                    # the row's suspicion re-derives from it. A ledger that
                    # cannot be locked at all refuses the NEXT request, in
                    # `_pace` below, before anything is spent.
                    ledger_failure = str(exc)[:300]
                    self.window_ledger_failed = True
                    print(f"  WINDOW LEDGER GAP: {ledger_failure}", flush=True)
                if ledger_failure is not None:
                    # The window evidence for THIS attempt never reached the
                    # shared ledger. Recorded on the attempt so the row's
                    # `window_ledger_gap` suspicion is re-derivable from the
                    # archive, rather than the gap being invisible (F5).
                    entry["ledger_write_failed"] = ledger_failure
                self.requests.append(entry)

            async with PacedClient._patch_lock:
                original_post = _oai_client_mod.post_chat_completion_with_routed_experts_sidecar
                captured: dict = {}

                async def _capturing_post(client, path, *, body, extra_headers=None):
                    captured["max_tokens"] = body.get("max_tokens")
                    captured["max_completion_tokens"] = body.get("max_completion_tokens")
                    response = await original_post(client, path, body=body, extra_headers=extra_headers)
                    captured["provider_model"] = getattr(response, "model", None)
                    captured["system_fingerprint"] = getattr(response, "system_fingerprint", None)
                    usage = getattr(response, "usage", None)
                    captured["usage_prompt_tokens"] = getattr(usage, "prompt_tokens", None)
                    captured["usage_completion_tokens"] = getattr(usage, "completion_tokens", None)
                    return response

                def _record(captured: dict) -> None:
                    self.wire_caps.append({**captured, "attempt_id": attempt_id})
                    self.billed_input_tokens_all_attempts += captured.get("usage_prompt_tokens") or 0
                    self.billed_output_tokens_all_attempts += captured.get("usage_completion_tokens") or 0

                _oai_client_mod.post_chat_completion_with_routed_experts_sidecar = _capturing_post
                try:
                    # EVERY attempt of this pacing loop is recorded in
                    # `self.requests`: a 429 that we then
                    # backed off from is a real provider request, and the
                    # row must be able to say so. A 429 carries no billed
                    # tokens (`billed_*` stay None); only a request that
                    # actually returned a completion adds to the billed
                    # totals, through `_record`.
                    model_id = k.get("model") or (a[1] if len(a) > 1 else None)

                    async def _pace() -> tuple[float, float]:
                        """Sleep until this provider may be called again, then
                        return `(epoch, monotonic)` for the request.

                        The interval is measured from the later of this
                        PROCESS's last call and the LEDGER's last entry for the
                        provider — the second is what survives the process
                        boundary between two scheduled cells."""
                        wait = PacedClient._last + min_interval - time.monotonic()
                        if window_ledger:
                            # BEFORE spending anything: prove the ledger can
                            # still be locked and read. A ledger that cannot
                            # be reached is a fault, and the request must not
                            # go out believing it was paced (F5).
                            window_ledger_precheck(window_ledger)
                            last = window_ledger_last_time(window_ledger_read(window_ledger), provider)
                            if last is not None:
                                wait = max(wait, last + min_interval - time.time())
                        if wait > 0:
                            await asyncio.sleep(wait)
                        # THE LAST THING BEFORE THE REQUEST.
                        # After the pacing sleep, not before it: the sleep can
                        # be a minute long, and the check must describe the
                        # instrument at the instant the request leaves. It
                        # raises `InstrumentDrift`, which is a BaseException,
                        # so neither the `except Exception` below nor the
                        # framework's own handlers can turn a drifted
                        # instrument into a logged attempt.
                        require_instrument("request", "immediately before a provider request")
                        PacedClient._last = time.monotonic()
                        return time.time(), time.monotonic()

                    for attempt in range(6):
                        sent_at, sent_mono = await _pace()
                        t0 = time.monotonic()
                        try:
                            response = await super(PacedClient, self).get_native_response(*a, **k)
                        except openai.RateLimitError as exc:
                            # The evidence a rate limit needs, gathered where
                            # it exists: the provider's own status/code/headers
                            # and the observed trailing window at this instant.
                            snapshot = prospective = None
                            unhealthy = None
                            if window_ledger:
                                try:
                                    at = time.time()
                                    snapshot = window_snapshot(
                                        window_ledger_read(window_ledger), at, provider, model_id, cell,
                                        current_request_estimate=estimated,
                                        kind=WINDOW_KIND_PRE_REQUEST)
                                    prospective = prospective_window(snapshot, estimated, True)
                                except WindowLedgerUnavailable as ledger_exc:
                                    # Damaged or unlockable evidence does not
                                    # get to masquerade as a quiet window: the
                                    # attempt records that the window could not
                                    # be reconstructed, and the NEXT request is
                                    # refused by `window_ledger_precheck`.
                                    unhealthy = str(ledger_exc)[:300]
                            _log("rate_limited", time.monotonic() - t0, attempt_no=attempt + 1,
                                 error=provider_error_fields(exc), window=snapshot,
                                 prospective=prospective, ledger_unhealthy=unhealthy,
                                 sent_at=sent_at, sent_monotonic=sent_mono)
                            pause = 20.0 * (attempt + 1)
                            print(f"  429; pausing {pause:.0f}s (attempt {attempt + 1}/6)", flush=True)
                            await asyncio.sleep(pause)
                            continue
                        except Exception as exc:                    # noqa: BLE001 -- recorded, then re-raised
                            _log(f"error:{type(exc).__name__}", time.monotonic() - t0, attempt_no=attempt + 1,
                                 error=provider_error_fields(exc), sent_at=sent_at, sent_monotonic=sent_mono)
                            raise
                        _record(captured)
                        _log("ok", time.monotonic() - t0, captured.get("usage_prompt_tokens"),
                             captured.get("usage_completion_tokens"), attempt_no=attempt + 1,
                             sent_at=sent_at, sent_monotonic=sent_mono)
                        return response
                    sent_at, sent_mono = await _pace()
                    t0 = time.monotonic()
                    try:
                        response = await super(PacedClient, self).get_native_response(*a, **k)
                    except Exception as exc:                        # noqa: BLE001 -- recorded, then re-raised
                        _log(f"error:{type(exc).__name__}", time.monotonic() - t0, attempt_no=7,
                             error=provider_error_fields(exc), sent_at=sent_at, sent_monotonic=sent_mono)
                        raise
                    _record(captured)
                    _log("ok", time.monotonic() - t0, captured.get("usage_prompt_tokens"),
                         captured.get("usage_completion_tokens"), attempt_no=7,
                         sent_at=sent_at, sent_monotonic=sent_mono)
                    return response
                finally:
                    _oai_client_mod.post_chat_completion_with_routed_experts_sidecar = original_post

        async def to_native_prompt(self, messages):
            # The assistant-message conversion the base client uses to replay
            # the WHOLE conversation into every later request (openai_chat_
            # completions_client.py:191 to_native_prompt / from_chat_message,
            # ~line 236: ChatCompletionAssistantMessageParam(...,
            # reasoning_content=message.reasoning_content)). Under the
            # no-reasoning-replay policy, drop reasoning_content from every
            # replayed assistant message in the PROJECTION only (content and
            # tool_calls untouched) so earlier turns' reasoning is not
            # re-sent on every later call; the state's own trajectory (this
            # method's `messages` argument) is never mutated.
            #
            # Provider hygiene, under EVERY policy: the base client writes the
            # key even when the model returned no reasoning
            # (`reasoning_content: None`), and a strict provider rejects the
            # bare key outright (Mistral: 422 `extra_forbidden` on
            # `messages[i].assistant.reasoning_content`, 2026-08-30). A None
            # field is an absent field, so dropping it changes nothing the
            # model sees and is NOT the B2 projection; the projection is the
            # `not reasoning_replay` branch, which also drops reasoning that
            # is actually there.
            prompt, extra = await super().to_native_prompt(messages)
            for msg in prompt:
                if isinstance(msg, dict) and msg.get("role") == "assistant" and "reasoning_content" in msg:
                    if not reasoning_replay or msg["reasoning_content"] is None:
                        msg.pop("reasoning_content")
            return prompt, extra

    return PacedClient


# ---------------------------------------------------------------------------
# THE CONFIGURATION-WIDE CAPABILITY PROBE. A provider/model
# family that cannot carry the payload one replay policy produces is a
# CONFIGURATION property, not a row property: it must be established BEFORE
# the schedule runs and exclude the whole configuration, never discovered
# mid-run and applied to whichever blocks happen to have failed.
#
# The probe is the smallest exchange that exercises the thing that breaks: a
# first request that produces an assistant TOOL CALL, then a second request
# that REPLAYS that assistant message (with the policy's projection applied)
# plus its tool reply. That second request is where Mistral answers 422
# `extra_forbidden` on a bare `reasoning_content`, and where Gemini 3.x
# answers 400 "missing a thought_signature" — the two failures the replay
# contract declares. Two requests per (provider, model, replay policy).
# ---------------------------------------------------------------------------

PROBE_TOOL_NAME = "piv_probe_echo"


def capability_probe(client_cls, config, model: str, timeout: float = 60.0) -> dict:
    """One two-turn tool-call exchange through the real client. Returns
    `{"ok", "detail", "turns", "tool_called"}`; `ok` is False ONLY when the
    SECOND (replaying) request failed, which is the request the replay policy
    is responsible for. A first-request failure is reported as `ok: None`
    (inconclusive — the endpoint was unreachable, which is not a statement
    about the replay contract), and a model that simply declines to call the
    tool is `ok: None` too: it proves nothing about carrying a replayed call.
    """
    from verifiers.legacy.types import Tool, ToolMessage, UserMessage

    tool = Tool(name=PROBE_TOOL_NAME, description="Echo the given text back.",
                parameters={"type": "object", "properties": {"text": {"type": "string"}},
                            "required": ["text"]})
    prompt = [UserMessage(content=f"Call {PROBE_TOOL_NAME} with text='ping'. Call the tool, do not answer "
                                  f"in prose.")]
    sampling_args = {"max_tokens": 128, "temperature": 0.0, "top_p": 1.0}
    client = client_cls(config)

    async def _exchange() -> dict:
        try:
            first = await client.get_response(prompt, model, sampling_args, tools=[tool])
        except Exception as exc:                                           # noqa: BLE001
            return {"ok": None, "stage": "first_request", "tool_called": False,
                    **provider_error_fields(exc)}
        assistant = getattr(first, "message", None)
        calls = getattr(assistant, "tool_calls", None) or []
        if not calls:
            return {"ok": None, "stage": "no_tool_call", "tool_called": False,
                    "error_message": "the model answered without calling a tool; the replay payload "
                                     "this probe exists to exercise was never produced"}
        replayed = list(prompt) + [assistant,
                                   ToolMessage(tool_call_id=str(getattr(calls[0], "id", "0")), content="pong")]
        try:
            await client.get_response(replayed, model, sampling_args, tools=[tool])
        except Exception as exc:                                           # noqa: BLE001
            return {"ok": False, "stage": "replay_request", "tool_called": True,
                    **provider_error_fields(exc)}
        return {"ok": True, "stage": "replay_request", "tool_called": True, "error_message": None}

    try:
        result = asyncio.run(_exchange())
    finally:
        try:
            asyncio.run(client.close())
        except Exception:                                                  # noqa: BLE001
            pass
    return result


def probe_configuration(provider: str, model: str, replay_policies=(True, False),
                        timeout: float = 60.0, min_interval: float = 6.0,
                        window_ledger=None, base_url: str | None = None,
                        key_var: str | None = None) -> dict:
    """Probe one (provider, model) under EVERY replay policy the schedule
    uses. The configuration is admissible only when every policy's replaying
    request succeeded; a policy that fails deterministically is the reason,
    named, and `run_arms` refuses to start that configuration's cells.

    An INCONCLUSIVE probe (endpoint unreachable, model would not call a tool)
    is not a capability verdict and does not exclude anything — it is
    reported so the operator decides, rather than the instrument deciding by
    outcome."""
    configure_provider(provider, base_url, key_var)
    load_key_from_registry()
    config = client_config(KEY_VAR, BASE_URL, timeout)
    results = {}
    for replay in replay_policies:
        client_cls = make_client_cls(min_interval, replay, window_ledger=window_ledger,
                                     provider=provider, cell=f"probe:{model}:{'on' if replay else 'off'}")
        results["reasoning_replay=" + ("on" if replay else "off")] = capability_probe(
            client_cls, config, model, timeout)
    verdicts = [r.get("ok") for r in results.values()]
    return {"provider": provider, "model": model,
            "admissible": all(v is not False for v in verdicts),
            "conclusive": all(v is True for v in verdicts),
            "policies": results}


def _run_evaluate(env, **eval_kwargs):
    """`env.evaluate(...)`, requesting the optional other-builder-owned
    columns (`piv_budget_accounting_invalid`, `piv_budget_accounting_detail`,
    `piv_episode_contract_digest`) first and falling back to the mandatory
    base set alone if they turn out to exist but not be JSON-serializable
    yet (a column that simply does not exist yet never raises — see
    `OPTIONAL_STATE_COLUMNS` above — so this only tolerates a transitional
    wrong shape, never mere absence, without failing every rollout on a
    column this file does not own)."""
    try:
        results = asyncio.run(env.evaluate(state_columns=BASE_STATE_COLUMNS + OPTIONAL_STATE_COLUMNS, **eval_kwargs))
        return results, True
    except ValueError as exc:
        if not any(col in str(exc) for col in OPTIONAL_STATE_COLUMNS):
            raise
        results = asyncio.run(env.evaluate(state_columns=list(BASE_STATE_COLUMNS), **eval_kwargs))
        return results, False


def one_rollout(env_mod, client_cls, config, selector: str, model: str, max_tokens: int, retries: int,
                max_total_completion_tokens: int, reasoning_replay: bool,
                archive: Path | None = None, arm: str = "A",
                temperature: float = 0.0, top_p: float = 1.0, seed: int | None = None,
                replicate: int = 1, prompt_schema_digest: str | None = None,
                schedule_id: str | None = None, planned_ordinal: int | None = None,
                actual_ordinal: int | None = None, session_id: str | None = None,
                block_id: str | None = None, permutation_index: int | None = None,
                arm_position: int | None = None, window_ledger=None) -> dict:
    env = env_mod.load_environment(selector)
    # The UNTOUCHED original ledger this episode was served, fixed at world
    # construction and unaffected by anything the agent does later --
    # captured here, once, so `candidate_vs_original` below can answer
    # "did the agent preserve the books" even for an episode that never
    # delivered anything.
    original_ledger_raw = env.public_files[env_mod.LEDGER]
    # The SERVED public task id, read from the serving door's own dataset
    # BEFORE the rollout runs, so it is on the row even when the provider
    # fails and the row is quarantined (the exact-cell check
    # compares the served id against the schedule's expectation, and a
    # quarantined cell that served a DIFFERENT world than the schedule
    # registered must be visible as such, not invisible because it failed).
    public_task_id = env.dataset[0]["info"]["task_id"] if len(env.dataset) else None
    # The episode contract THIS process pinned, computed from the package at
    # the ceiling this cell will run under. `state["piv_episode_contract_
    # digest"]` is the authority for a rollout that completed; a QUARANTINED
    # cell never produces one, and the exact-cell check must
    # still be able to say which episode contract that cell ran under.
    try:
        declared_episode_digest = env_mod.episode_contract_digest(max_total_completion_tokens)
    except Exception:                                                      # noqa: BLE001
        declared_episode_digest = None
    # MultiTurnEnv's own episode-output ceiling. Set UNCONDITIONALLY --
    # `set_max_total_completion_tokens` accepts any int with no validation,
    # and both the framework's own `max_total_completion_tokens_reached`
    # stop and the environment's `get_model_response` clamp already treat
    # `<= 0` as disabled (`multiturn_env.py`'s own default is `-1`). The
    # PREVIOUS `if max_total_completion_tokens > 0:` guard made "0 disables
    # it" (this file's own --max-total-completion-tokens help text) false in
    # practice: passing 0 skipped the call entirely and silently left
    # whichever nonzero ceiling `load_environment` itself defaults to (the
    # package's own MAX_EPISODE_OUTPUT_TOKENS) in effect, so a caller asking
    # for "no ceiling" got a real, un-disclosed one instead -- exactly the
    # kind of silent mismatch this milestone's budget_accounting work exists
    # to catch.
    env.set_max_total_completion_tokens(max_total_completion_tokens)
    client = client_cls(config)
    started = time.monotonic()
    started_at = datetime.now().isoformat()
    # Sampling pins: temperature and top_p are ALWAYS
    # sent explicitly (default 0.0/1.0 rather than left to the provider's
    # own default) so every row states what it actually asked for; `seed`
    # is only sent when the caller passed one — `tests/seed_probe.py`
    # answers whether the endpoint actually HONOURS it, which a 200
    # response alone does not prove.
    sampling_args = {"max_tokens": max_tokens, "temperature": temperature, "top_p": top_p}
    if seed is not None:
        sampling_args["seed"] = seed
    common = {
        "selector": selector, "arm": arm, "replicate": replicate, "per_turn_cap": max_tokens,
        "reasoning_replay": reasoning_replay,
        "replay_policy": "full" if reasoning_replay else "no_reasoning_content",
        "max_total_completion_tokens": max_total_completion_tokens,
        "timeout": getattr(config, "timeout", None), "retries": retries,
        "provider": PROVIDER, "endpoint": getattr(config, "api_base_url", BASE_URL), "model": model,
        "client_version": _client_version(), "started_at": started_at,
        "temperature": temperature, "top_p": top_p, "seed": seed,
        "prompt_schema_digest": prompt_schema_digest,
        "episode_contract_version": getattr(env_mod, "EPISODE_CONTRACT_VERSION", None),
        # The REPLAY contract this row ran under — its own
        # identity, separate from the episode contract: two rows can share a
        # prompt, a tool schema and a ceiling and still not be comparable
        # because the client replayed the conversation differently.
        # `arm_table.py` REFUSES to pool rows whose replay digests differ.
        "replay_contract_version": REPLAY_CONTRACT_VERSION,
        "replay_contract_digest": replay_contract_digest(reasoning_replay),
        "library_versions": library_versions(),
        # SCHEDULE provenance. The schedule file is written
        # BEFORE any rollout and owns the order; these fields let a row prove
        # which schedule row it executed and when it actually ran, so an
        # interruption can never pretend the planned temporal order held.
        # `None` for a bare `measure_budget.py` run not driven by a schedule.
        "schedule_id": schedule_id, "planned_ordinal": planned_ordinal,
        "actual_ordinal": actual_ordinal, "session_id": session_id,
        "block_id": block_id, "permutation_index": permutation_index,
        "arm_position": arm_position,
        # The served world's public id, on EVERY row including a quarantined
        # one, and the shared window ledger this cell paced against.
        "task_id": public_task_id,
        "window_ledger": str(window_ledger) if window_ledger else None,
        "episode_contract_digest": declared_episode_digest,
        "episode_contract_digest_declared": declared_episode_digest,
        # THE RUNTIME IDENTITY, recorded SEPARATELY from the sealed
        # `instrument_commit`. The git-path contract permits a
        # run at a later commit precisely while nothing under the execution
        # paths changed, so the report must be able to state both: what was
        # sealed, and what actually executed this row.
        # ... and the two digests are part of EXACT row
        # ADMISSION (`schedule_arms.contract_expectations`), not of a reporting
        # paragraph: a row whose instrument differs from the seal is not this
        # cell's row and enters no estimand.
        "runtime_head": runtime_identity().get("runtime_head"),
        "execution_tree_digest": runtime_identity().get("execution_tree_digest"),
        "instrument_identity_version": runtime_identity().get("instrument_identity_version"),
        "runtime_environment_digest": runtime_identity().get("runtime_environment_digest"),
        "runtime_environment_identity_version":
            runtime_identity().get("runtime_environment_identity_version"),
    }
    try:
        results, got_optional = _run_evaluate(
            env, client=client, model=model, sampling_args=sampling_args,
            num_examples=1, rollouts_per_example=1, max_concurrent=1,
            max_retries=retries, save_results=False)
    except env_mod.PIVEvaluationBatchInvalid as exc:
        # A quarantined (provider-failed) cell still SPENT: the requests it
        # made before failing were billed. Those tokens and that wall time
        # belong in the OPERATIONAL cost of the arm whose own
        # request size or replay payload caused the failure, so they are
        # archived here rather than lost with the exception.
        return {**common, "quarantined": True, "status": str(exc.status),
                "reasons": {str(k): v for k, v in exc.reason_counts.items()},
                "requests": getattr(client, "requests", None),
                "billed_input_tokens_all_attempts": getattr(client, "billed_input_tokens_all_attempts", None),
                "billed_output_tokens_all_attempts": getattr(client, "billed_output_tokens_all_attempts", None),
                "finished_at": datetime.now().isoformat(),
                "seconds": round(time.monotonic() - started, 1)}
    out = results["outputs"][0]
    metrics = out.get("metrics") or {}
    usage = out.get("token_usage") or {}
    completion = out.get("completion") or []
    trajectory = out.get("trajectory") or []
    tools = tool_names(completion)
    # `piv_request_max_tokens` is now MANDATORY (in BASE_STATE_COLUMNS, not
    # gated on `got_optional`, which only tracks the two OTHER-BUILDER-owned
    # columns below); a row whose state somehow still lacks it is caught by
    # `compute_budget_accounting`, not silently treated as `None` here.
    request_caps = out.get("piv_request_max_tokens")
    # `wire_caps` (per-call, all attempts) vs `last_segment_wire_caps`
    # (adversarial-review follow-up, item 1): the REAL
    # `PacedClient` always exposes `last_segment_wire_caps`, aligned to the
    # LAST (surviving) framework attempt -- what `per_turn` must be zipped
    # against, since `out["trajectory"]` only ever reflects that attempt. A
    # scripted test client that sets a plain `.wire_caps` attribute (no
    # `.last_segment_wire_caps` property) falls back to using it directly,
    # treated as already-aligned -- correct because a scripted rollout never
    # simulates more than one attempt.
    wire_caps_all_attempts = getattr(client, "wire_caps", None)
    wire_caps = getattr(client, "last_segment_wire_caps", wire_caps_all_attempts)
    attempts = getattr(client, "attempts", None)       # None for a client that does not track it -- not a retry, not applicable
    billed_input_all = getattr(client, "billed_input_tokens_all_attempts", None)
    billed_output_all = getattr(client, "billed_output_tokens_all_attempts", None)
    per_turn = per_turn_rows(trajectory, reasoning_replay, request_caps, wire_caps)
    # The framework's own SUM over turns (`input_tokens`/`output_tokens`) is
    # what the budget is measured against. Its `final_input_tokens` /
    # `final_output_tokens` are NOT last-turn values despite the name (pinned
    # in test_measure_budget.py, item 4b): `final_output_tokens` is the same
    # whole-rollout completion-token sum computed a second way, and
    # `final_input_tokens` is `last_step_total - total_completion`, which for
    # this client (whose `prompt_tokens` already includes every earlier
    # turn's replayed output) is not any turn's actual input size. So this
    # row never presents those two framework fields as "final"/"last turn" —
    # `token_usage` below carries them verbatim, under their own framework
    # names, for audit; `last_turn_input_tokens`/`last_turn_output_tokens`
    # are computed here, directly, from the LAST trajectory step's own Usage.
    prompt = usage.get("input_tokens", usage.get("prompt_tokens"))
    done = usage.get("output_tokens", usage.get("completion_tokens"))
    total = int((prompt or 0) + (done or 0)) if usage else None
    last = last_assistant_text(completion)
    artifact_info = bind_artifact(out, env_mod)
    # `got_optional` is False only in the transitional not-yet-serializable
    # case, in which BOTH optional columns are dropped from `out` together —
    # so a plain `.get()` already reads back `None` for either one when that
    # happens; nothing here needs to branch on `got_optional` itself.
    requests = getattr(client, "requests", None)
    rollout_id = out.get("piv_rollout_id")
    surviving_requests = None
    if requests is not None:
        attempt_ids = [r.get("attempt_id") for r in requests if r.get("attempt_id") is not None]
        surviving = attempt_ids[-1] if attempt_ids else None
        surviving_requests = [r for r in requests
                              if surviving is None or r.get("attempt_id") == surviving]
    env_code = out.get("piv_budget_accounting_invalid")
    # Owned by the package (read with `.get()`, `None` until it lands): the
    # environment's own SUSPICION signal, the counterpart of the
    # split between a hard-invalid theorem and an anomaly band.
    env_suspicious_code = out.get("piv_budget_accounting_suspicious")
    budget_accounting = compute_budget_accounting(
        request_caps, per_turn, wire_caps, env_code,
        done, max_total_completion_tokens, attempts,
        requests=surviving_requests, rollout_id=rollout_id)
    budget_accounting_suspicious = compute_budget_suspicion(per_turn, env_suspicious_code)
    row = {
        **common,
        "reward": out.get("reward"),
        "stop": out.get("stop_condition"),
        "truncated": out.get("is_truncated"),
        "error": out.get("error"),
        "batch_status": (results.get("metadata") or {}).get("piv_status"),
        "turns": metrics.get("num_turns", len(trajectory)),
        "tools": tools,
        "wrote_ledger": "write_ledger" in tools,
        # Fail-closed budget accounting. "VALID" or
        # "INVALID/<reason>" — see `compute_budget_accounting`'s docstring
        # for the exact predicate. `wire_caps` is the client's own per-turn
        # capture (`None` for a scripted test client), archived verbatim
        # alongside the per-turn detail in `per_turn` for audit either way.
        "budget_accounting": budget_accounting,
        # The env's own prose for its code, kept OUT of the status string
        # itself (never interpolated) so `budget_accounting` stays a value
        # from the closed set every time.
        "budget_accounting_detail": out.get("piv_budget_accounting_detail"),
        # The env's RAW codes, archived so `validate_row` can re-derive the
        # whole verdict from the row alone rather than believing a string.
        "budget_accounting_env_code": env_code,
        "budget_accounting_suspicious_env_code": env_suspicious_code,
        # SUSPICIOUS is not INVALID: a named diagnostic that
        # `arm_table.py` shows every table with AND without.
        "budget_accounting_suspicious": budget_accounting_suspicious,
        "wire_caps": wire_caps,                        # aligned to the LAST framework attempt -- matches per_turn
        "wire_caps_all_attempts": wire_caps_all_attempts,   # every attempt, unaligned, for audit
        # Every provider request this rollout made, including the 429s the
        # pacing loop backed off from (which carry no billed tokens) and the
        # requests of any discarded framework attempt.
        "requests": requests,
        "attempts": attempts,
        "attempts_prompt_shape": getattr(client, "attempts_prompt_shape", None),
        "billed_input_tokens_all_attempts": billed_input_all,
        "billed_output_tokens_all_attempts": billed_output_all,
        # `None` until the other builder's
        # `state["piv_episode_contract_digest"]` lands (`got_optional` is
        # only False on the transitional not-yet-serializable case; a
        # column that simply does not exist yet is already `None` via
        # `.get()` regardless of `got_optional`).
        "episode_contract_digest": out.get("piv_episode_contract_digest") or declared_episode_digest,
        # Package-side counters, `None` until they land:
        # how many COMPLETE ledger reads this episode issued and how many
        # observation bytes those replies carried. The archive can only
        # BOUND both (see tests/pilot_facts.py); the package counts them.
        "complete_reads": out.get("piv_complete_reads"),
        "observation_bytes": out.get("piv_observation_bytes"),
        # Episode contract 4: tool calls this episode emitted whose arguments
        # were not a JSON object -- refused, never executed, stored replayable.
        "rejected_calls": out.get("piv_rejected_calls"),
        # The SERVING host's own view of the packages the replay contract is
        # bound to, beside this process's own — a disagreement means the row
        # was produced under a different projection than its digest claims.
        "env_library_versions": out.get("piv_library_versions"),
        # True unless `piv_budget_accounting_invalid`/`piv_episode_contract_
        # digest` had to be dropped from THIS request because at least one
        # of them existed but was not yet JSON-serializable (a transitional
        # state during the other builder's own edit, not "column absent").
        "optional_columns_present": got_optional,
        # The LAST commit's own digests, from the raw bytes as written — set
        # at write time, before any canonical re-rendering the scorer does at
        # publication. Distinct from `artifact_*_digest` above (the DELIVERED
        # bytes' digest): two different valid resubmissions of the same
        # repair set render to byte-identical canonical output by design
        # (`render_committed` prints planted repairs from the graph and
        # preserved entries from the original, never from what was
        # submitted — the anti-narration-exploit property witnessed in
        # `test_committed.py`), so this is the field that actually
        # distinguishes "what this rollout wrote" across concurrent rollouts.
        "candidate_logical_text_digest": out.get("piv_logical_text_digest"),
        "candidate_stored_bytes_digest": out.get("piv_stored_bytes_digest"),
        # `original_logical_digest`/`candidate_equals_original`: whether the
        # last accepted candidate above is textually the untouched original
        # this episode was served -- the one thing NO_ARTIFACT/not_scored
        # rows (an accepted write, no delivery) could not say before. See
        # `candidate_vs_original`'s own docstring for why the comparison is
        # safe (same digest function on both sides) and why it is `None`
        # rather than `False` when nothing was ever written.
        **candidate_vs_original(out.get("piv_logical_text_digest"), original_ledger_raw, env_mod),
        "prompt_tokens": prompt,
        "completion_tokens": done,
        "total_tokens": total,
        "token_usage": usage,                                       # framework's own names, verbatim, for audit
        "last_turn_input_tokens": per_turn[-1]["input_tokens"] if per_turn else None,
        "last_turn_output_tokens": per_turn[-1]["output_tokens"] if per_turn else None,
        "last_assistant_chars": len(last),
        "volume": message_volume(completion),
        "last_assistant_tail": last[-300:],
        "metrics": {k: v for k, v in metrics.items() if str(k).startswith("piv")},
        "seconds": round(time.monotonic() - started, 1),
        "finished_at": datetime.now().isoformat(),
        "per_turn": per_turn,
        **artifact_info,
    }
    if artifact_info["artifact"] == "BOUND":
        ledger_path = Path(artifact_info["workspace"]) / env_mod.LEDGER
        delivered = ledger_path.read_text(encoding="utf-8")
        if archive is not None:
            archive.mkdir(parents=True, exist_ok=True)
            write_atomic(archive / f"{selector.replace(':', '_')}.beancount", delivered)
        try:
            row["breakdown"] = breakdown(selector, delivered)
        except Exception as exc:                # noqa: BLE001 — the instrument must not hide a rollout
            row["breakdown"] = {"error": f"{type(exc).__name__}: {exc}"[:200]}
    # ONE validator, both ends: the writer runs the same
    # pure archived-row check `tests/arm_table.py` will run when it reads the
    # file back, so a row that the table would refuse is refused HERE, at
    # the moment it is written, with its reasons recorded beside it.
    validation_status, validation_reasons = validate_row(row)
    row["row_validation"] = {"status": validation_status, "reasons": validation_reasons}
    # A live row whose two verdicts disagree is itself a finding: the
    # accounting string and the re-derivation come from the same data, so a
    # divergence means one of them is reading it wrong.
    row["row_validation_agrees"] = (
        (validation_status in ("VALID", "VALID/derived")) == (budget_accounting == "VALID"))
    return row


def _fmt(value):
    return "?" if value is None else value


def partition_rows_for_summary(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """`(valid_scored, quarantined, budget_invalid)` — every summary
    statistic (the printed console summary, the `.md` bullets) must be
    computed over `valid_scored` ONLY (adversarial-review finding 2): a row
    is quarantined (a named provider failure, never scored), OR its
    `budget_accounting` is not `"VALID"` (excluded — an equal-budget claim
    over it cannot be trusted), OR it is a valid, scored attempt. Every row
    lands in exactly one bucket; `quarantined + budget_invalid + valid_scored
    == rows` in length, always."""
    quarantined = [r for r in rows if r.get("quarantined")]
    remaining = [r for r in rows if not r.get("quarantined")]
    budget_invalid = [r for r in remaining if r.get("budget_accounting") != "VALID"]
    valid_scored = [r for r in remaining if r.get("budget_accounting") == "VALID" and r.get("total_tokens")]
    return valid_scored, quarantined, budget_invalid


def format_per_turn_line(t: dict) -> str:
    tools = ",".join(t["tools"]) if t["tools"] else "-"
    return (f"  turn {t['turn']:02d}  in={_fmt(t['input_tokens'])} out={_fmt(t['output_tokens'])} "
           f"reasoning_tok={_fmt(t['reasoning_tokens'])} cum_in={t['cumulative_input_tokens']} "
           f"cum_out={t['cumulative_output_tokens']} msgs={t['prompt_messages']} "
           f"reasoning_chars={t['reasoning_chars_in_history']} sent={t['reasoning_chars_sent']} "
           f"visible_chars={t['visible_chars_in_history']} "
           f"gen_chars={(t.get('assistant_content_chars') or 0) + (t.get('assistant_reasoning_chars') or 0)}"
           f"+tool_args={_fmt(t.get('tool_call_chars'))} req_cap={_fmt(t['request_max_tokens'])} "
           f"wire_cap={_fmt(t['wire_max_completion_tokens'] if t.get('wire_max_completion_tokens') is not None else t.get('wire_max_tokens'))} "
           f"provider_model={_fmt(t.get('provider_model'))} "
           f"finish={t['finish_reason']} trunc={t['truncated']} tools=[{tools}]")


def abandon_cell_on_drift(detail: str, row_path: Path, markdown_path: Path,
                          row_file_existed: bool) -> int:
    """Withdraw whatever this process wrote for a cell whose instrument
    drifted, and exit `INSTRUMENT_DRIFT_EXIT`.

    A row produced under an unsealed instrument must not survive: leaving it
    would make the cell look `done` to `run_arms.cell_status` and — before the
    digests entered exact admission — could have entered a confirmatory
    estimate. Bytes that existed BEFORE this process are never touched: they
    are somebody else's observation, and destroying them would be the same
    class of error in the other direction.
    """
    withdrawn: list[str] = []
    kept: list[str] = []
    for path in (row_path, markdown_path):
        if path is None:
            continue
        if row_file_existed:
            # An observation was already here when this process opened the
            # file, and the markdown beside it renders that observation. Both
            # are somebody else's bytes.
            kept.append(path.name)
            continue
        try:
            if path.exists():
                path.unlink()
                withdrawn.append(path.name)
        except OSError as exc:                                             # noqa: BLE001
            kept.append(f"{path.name} ({type(exc).__name__})")
    print(f"REFUSED — {detail}\n"
          f"  No further provider call was made. "
          + (f"Withdrawn: {', '.join(withdrawn)}. " if withdrawn else "Nothing was written. ")
          + (f"PRESERVED (not written by this process): {', '.join(kept)}. " if kept else "")
          + f"\n  The executor must journal this fail-closed and stop the session: a drifted instrument "
            f"invalidates everything after it.", file=sys.stderr)
    return INSTRUMENT_DRIFT_EXIT


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", default="nvidia", help=f"endpoint preset: {sorted(PROVIDERS)}")
    parser.add_argument("--base-url", default=None, help="explicit OpenAI-compatible base URL (overrides the preset)")
    parser.add_argument("--api-key-var", default=None, help="environment / HKCU variable holding the key (overrides the preset)")
    parser.add_argument("--selectors", nargs="+", required=True)
    parser.add_argument("--arm", choices=sorted(ARM_PRESETS), default=None,
                        help="preset (per-turn max_tokens, reasoning replay): A=8000/on B1=16000/on "
                             "B2=8000/off B3=16000/off; --max-tokens/--no-reasoning-replay still override it")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help="per-turn completion cap; default 4000, or the --arm's cap")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--retries", type=int, default=0,
                        help="framework-level rollout retries on InfraError/InvalidModelResponseError "
                             "(verifiers.legacy.utils.async_utils.maybe_retry). DEFAULT 0 (adversarial-review "
                             "finding 1): `Environment.run_rollout` retries with a FRESH state on the SAME "
                             "client, which keeps billing the provider across attempts that the final state's "
                             "own trajectory never records (18,000 tokens billed vs 8,000 reported, observed "
                             "with the previous default of 1) -- a provider failure should be a NAMED "
                             "provider-failed/quarantined row, not a silent retry this instrument cannot fully "
                             "account for. Raise it only if you also read `row['attempts']`/`row['billed_*_"
                             "all_attempts']` and treat attempts > 1 as INVALID/framework_retry, which "
                             "compute_budget_accounting already does.")
    parser.add_argument("--min-interval", type=float, default=6.0, help="seconds between model calls (provider pacing)")
    parser.add_argument("--tag", default="", help="suffix for the output files (one run per selector keeps earlier rows)")
    parser.add_argument("--no-reasoning-replay", action="store_true",
                        help="strip reasoning_content from replayed assistant messages before every request "
                             "(content and tool_calls are kept); default follows --arm, or replays it as the "
                             "framework does when no arm is given")
    parser.add_argument("--max-total-completion-tokens", type=int, default=40_000,
                        help="per-episode output-token ceiling (summed over turns). The environment enforces it "
                             "on every REQUEST (max_tokens is clamped to the remainder) and names the ending "
                             "piv_output_budget_exhausted; this only overrides the environment's default "
                             "MAX_EPISODE_OUTPUT_TOKENS. 0 disables it")
    parser.add_argument("--temperature", type=float, default=0.0, help="sampling pin, sent explicitly and recorded")
    parser.add_argument("--top-p", type=float, default=1.0, help="sampling pin, sent explicitly and recorded")
    parser.add_argument("--seed", type=int, default=None,
                        help="sampling pin, sent only when given; tests/seed_probe.py tells you whether the "
                             "endpoint actually honours it before you rely on it for replication")
    parser.add_argument("--replicate", type=int, default=1,
                        help="replicate index recorded on every row (tests/run_arms.py sets this from the "
                             "schedule; a bare measure_budget.py run defaults to 1)")
    parser.add_argument("--stamp-date", default=None,
                        help="the YYYY-MM-DD part of the output filename; defaults to TODAY. "
                             "tests/run_arms.py passes the SCHEDULE's own date so that resuming a schedule "
                             "on a later day finds the cells it already ran instead of re-running them")
    # Schedule provenance -- set by tests/run_arms.py from
    # the immutable schedule file; provenance only, no effect on THIS
    # process's own single cell.
    parser.add_argument("--schedule-id", default=None, help="the schedule file's own content digest")
    parser.add_argument("--planned-ordinal", type=int, default=None,
                        help="this cell's position in the schedule's PLANNED order")
    parser.add_argument("--actual-ordinal", type=int, default=None,
                        help="this cell's position in the executing session's ACTUAL order (skipped cells "
                             "are not counted) -- an interruption must never pretend the planned order held")
    parser.add_argument("--session-id", default=None, help="the run_arms.py process that executed this cell")
    parser.add_argument("--block-id", default=None,
                        help="the (provider, model, selector, replicate) block whose three arms run together")
    parser.add_argument("--permutation-index", type=int, default=None,
                        help="which of the six arm-order permutations this block used")
    parser.add_argument("--arm-position", type=int, default=None,
                        help="this arm's position within its block's arm order, recorded on the row")
    parser.add_argument("--window-ledger", default=None,
                        help="path of the SHARED provider-window ledger: every HTTP attempt "
                             "is appended to it, the pacing interval is enforced against ITS last entry for "
                             "this provider rather than against this process's memory (each scheduled cell "
                             "is a fresh subprocess, so that memory is always empty at the boundary that "
                             "matters), and a 429 archives the observed trailing-60 s window it was refused "
                             "in. tests/run_arms.py passes one per schedule")
    # THE SEALED INSTRUMENT. Passed down by tests/run_arms.py
    # from the sealed experiment contract, so that this process — the one that
    # actually spends the provider call — can refuse to make it.
    parser.add_argument("--sealed-execution-tree-digest", default=None,
                        help="the schedule's sealed execution-tree digest. Re-verified before request 1 "
                             "of this cell, before EVERY provider request, and after the last write; a "
                             "mismatch makes no provider call and exits "
                             f"{INSTRUMENT_DRIFT_EXIT}")
    parser.add_argument("--sealed-runtime-environment-digest", default=None,
                        help="the schedule's sealed runtime-environment digest (every installed "
                             "distribution's bytes, the files no RECORD references, and the "
                             "interpreter). Re-verified at the cell's opening and closing checks")
    parser.add_argument("--sealed-instrument-identity-version", type=int, default=None)
    parser.add_argument("--sealed-runtime-environment-identity-version", type=int, default=None)
    args = parser.parse_args()

    # ARMED BEFORE ANYTHING ELSE, and checked before the world is even minted:
    # "a mismatch -> no provider call" has to mean no provider call, and the
    # capability probe and the serving door both come after this point.
    set_sealed_instrument(args.sealed_execution_tree_digest,
                          args.sealed_runtime_environment_digest,
                          args.sealed_instrument_identity_version,
                          args.sealed_runtime_environment_identity_version)
    drift = verify_instrument("cell")
    if drift:
        print(f"REFUSED before request 1 of this cell — INSTRUMENT DRIFT:\n  " + "\n  ".join(drift)
              + "\n  The sealed schedule does not describe the code or the interpreter that would run "
                "this cell. No provider call was made and no row was written.", file=sys.stderr)
        return INSTRUMENT_DRIFT_EXIT

    configure_provider(args.provider, args.base_url, args.api_key_var)
    load_key_from_registry()

    from beancount_ledger import beancount_ledger as env_mod

    arm_cap, arm_replay = ARM_PRESETS[args.arm] if args.arm else (4000, True)
    max_tokens = args.max_tokens if args.max_tokens is not None else arm_cap
    reasoning_replay = False if args.no_reasoning_replay else arm_replay
    arm_label = args.arm or "custom"
    client_cls = make_client_cls(args.min_interval, reasoning_replay,
                                 window_ledger=args.window_ledger, provider=PROVIDER,
                                 cell=args.tag or None, session_id=args.session_id)
    # A literal hash of the exact system prompt and native tool schema THIS
    # checkout serves, computed once, up
    # front, from the package under `sys.path[0]` — recorded on every row of
    # this run even before `piv_episode_contract_digest` lands.
    prompt_schema_digest = compute_prompt_schema_digest(env_mod)

    config = client_config(KEY_VAR, BASE_URL, args.timeout)
    out_dir = ROOT / "reviews"
    out_dir.mkdir(exist_ok=True)
    stamp = (args.stamp_date or datetime.now().strftime("%Y-%m-%d")) + (f"_{args.tag}" if args.tag else "")
    slug = args.model.split("/")[-1]
    row_path = out_dir / f"budget_{slug}_{stamp}.json"
    # BEFORE the first provider call, and once — not per write: the row file
    # is rewritten after every selector, so a per-write check would refuse
    # this run's own second selector. Checked here, it refuses a hand-typed
    # invocation that would replace an observed scheduled cell (F2).
    refuse_scheduled_overwrite(row_path, [{"schedule_id": args.schedule_id}])
    # Whether an OBSERVATION already existed here before this process opened
    # the file: a drift refusal below deletes only what THIS process wrote, and
    # never someone else's archived bytes.
    row_file_existed = row_path.exists()
    rows = []
    print(f"model {args.model}; arm {arm_label} ({max_tokens} tok/turn, reasoning replay "
          f"{'on' if reasoning_replay else 'off'}); {len(args.selectors)} selectors; "
          f"budget {BUDGET_TOKENS:,} tokens / {BUDGET_TURNS} turns; "
          f"max total completion tokens {args.max_total_completion_tokens or 'unset'}; "
          f"sampling temperature={args.temperature} top_p={args.top_p} seed={args.seed}; "
          f"replicate {args.replicate}; prompt_schema_digest {prompt_schema_digest[:12]}...; "
          f"replay_contract v{REPLAY_CONTRACT_VERSION} {replay_contract_digest(reasoning_replay)[:12]}...; "
          f"SDK retries 0\n", flush=True)
    markdown_path = out_dir / f"budget_{slug}_{stamp}.md"
    try:
        for selector in args.selectors:
            row = one_rollout(env_mod, client_cls, config, selector, args.model, max_tokens, args.retries,
                              args.max_total_completion_tokens, reasoning_replay,
                              archive=out_dir / f"budget_{slug}_{stamp}", arm=arm_label,
                              temperature=args.temperature, top_p=args.top_p, seed=args.seed,
                              replicate=args.replicate, prompt_schema_digest=prompt_schema_digest,
                              schedule_id=args.schedule_id, planned_ordinal=args.planned_ordinal,
                              actual_ordinal=args.actual_ordinal, session_id=args.session_id,
                              block_id=args.block_id, permutation_index=args.permutation_index,
                              arm_position=args.arm_position, window_ledger=args.window_ledger)
            # Set here rather than inside `one_rollout`: `--tag` names the
            # output file, so `tests/run_arms.py` can decide a scheduled cell
            # is done only by finding a row that says so; `--min-interval` is
            # the pacing this run used, which `arm_table.classify_error` needs
            # to tell a 429 the arm's own request rate caused from one it did
            # not.
            row["tag"] = args.tag
            row["min_interval"] = args.min_interval
            rows.append(row)
            if row.get("quarantined"):
                print(f"{selector:16s} QUARANTINED {row['status']} {row['reasons']}", flush=True)
            else:
                print(f"{selector:16s} reward {row['reward']!s:6s} turns {row['turns']!s:>4}  tokens {row['total_tokens'] or '?':>7} "
                      f"(in {row['prompt_tokens']}, out {row['completion_tokens']}, last turn in/out "
                      f"{row['last_turn_input_tokens']}/{row['last_turn_output_tokens']})  "
                      f"stop {row['stop']} truncated {row['truncated']}  {row['seconds']}s  "
                      f"artifact {row['artifact']}{'/' + row['artifact_reason'] if row.get('artifact_reason') else ''} "
                      f"submitted {row['submitted']}  budget_accounting {row['budget_accounting']}"
                      f"{'  SUSPICIOUS/' + row['budget_accounting_suspicious'] if row.get('budget_accounting_suspicious') else ''}"
                      f"  row_validation {row['row_validation']['status']}  tools {row['tools']}",
                      flush=True)
                if row.get("breakdown"):
                    b = row["breakdown"]
                    print(f"{'':16s} scorer: total {b.get('total')} outcome {b.get('outcome')} renderable {b.get('renderable')} "
                          f"components {b.get('components')} penalties {list((b.get('penalties') or {}).keys())} "
                          f"{('protocol: ' + str(b.get('protocol_reason'))) if b.get('protocol_reason') else ''}", flush=True)
            write_atomic(row_path, json.dumps(rows, indent=1, default=str))
    except InstrumentDrift as exc:
        # Raised immediately before a provider request, so the request was
        # never made. Anything this process had already written for the cell is
        # withdrawn: a partially observed cell under a drifted instrument is
        # not an observation.
        return abandon_cell_on_drift(str(exc), row_path, markdown_path, row_file_existed)

    # `budget_accounting` gates every summary statistic (adversarial-review
    # finding 2): `scored` is now ONLY rows whose accounting is `"VALID"`,
    # never merely "not quarantined". `excluded_invalid` (budget_accounting
    # != VALID) is reported by count and by reason, never silently folded
    # in as though it supported an equal-budget comparison.
    scored, quarantined_rows, excluded_invalid = partition_rows_for_summary(rows)
    lines = [f"# Token budget — {args.model}, {stamp}", "",
             f"Budget: {BUDGET_TOKENS:,} tokens, {BUDGET_TURNS} turns a rollout (PLAN §6). One rollout per selector.",
             f"Arm: {arm_label} ({max_tokens} tokens/turn, reasoning replay "
             f"{'on' if reasoning_replay else 'off'}). "
             f"Max total completion tokens: {args.max_total_completion_tokens or 'unset'}. "
             f"Timeout {args.timeout:.0f}s, retries {args.retries}. Replicate {args.replicate}.",
             f"Sampling pins: temperature={args.temperature}, top_p={args.top_p}, seed={args.seed}. "
             f"prompt_schema_digest {prompt_schema_digest}.",
             f"replay_contract v{REPLAY_CONTRACT_VERSION}, digest "
             f"{replay_contract_digest(reasoning_replay)}, libraries {library_versions()}. "
             f"SDK retries 0 (ClientConfig.max_retries), framework retries {args.retries}."
             + (f" Schedule {args.schedule_id}." if args.schedule_id else ""), "",
             # `over_plan_budget` compares TOTAL tokens (input + output)
             # against PLAN §6's 50,000-token BUDGET; `ceiling_hit` names
             # the DIFFERENT thing — the enforced 40,000-OUTPUT-token
             # episode ceiling actually being spent (stop ==
             # piv_output_budget_exhausted). The two are not the same
             # number and were conflated under the old "over budget" column
             # name (adversarial-review finding 6).
             "| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | "
             "stop | tools | arm | artifact | submitted | budget_accounting |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("quarantined"):
            cells = [r["selector"], "quarantined", "", "", "", "", "", "", r["status"], "", str(r.get("arm") or ""),
                    "", "", ""]
            lines.append("| " + " | ".join(cells) + " |")
            continue
        over_plan_budget = "**yes**" if (r["total_tokens"] or 0) > BUDGET_TOKENS else "no"
        ceiling_hit = "yes" if r.get("stop") == "piv_output_budget_exhausted" else "no"
        artifact_cell = r["artifact"] + (f"/{r['artifact_reason']}" if r.get("artifact_reason") else "")
        tools_cell = f"{len(r['tools'])}{' incl. write_ledger' if r['wrote_ledger'] else ' NO write'}"
        cells = [r["selector"], str(r["reward"]), str(r["turns"]), str(r["prompt_tokens"]), str(r["completion_tokens"]),
                str(r["total_tokens"]), over_plan_budget, ceiling_hit,
                f"{r['stop']}{' (truncated)' if r['truncated'] else ''}", tools_cell, r["arm"], artifact_cell,
                str(r["submitted"]), r["budget_accounting"]]
        lines.append("| " + " | ".join(cells) + " |")
    summary_bullets: list[str] = []
    if excluded_invalid or quarantined_rows:
        excluded_reasons: dict = {}
        for r in excluded_invalid:
            key = r.get("budget_accounting")
            excluded_reasons[key] = excluded_reasons.get(key, 0) + 1
        summary_bullets.append(f"- excluded from this summary: {len(excluded_invalid)} budget_accounting != VALID "
                               f"({dict(sorted(excluded_reasons.items(), key=lambda kv: -kv[1]))}), "
                               f"{len(quarantined_rows)} quarantined (provider-failed)")
    if scored:
        totals = [r["total_tokens"] for r in scored]
        turns = [r["turns"] for r in scored]
        rewards = [r["reward"] for r in scored if isinstance(r["reward"], (int, float))]
        # `over_plan_budget`: TOTAL tokens vs PLAN §6's 50,000-token budget.
        # `ceiling_hit`: the DIFFERENT, enforced 40,000-OUTPUT-token episode
        # ceiling actually being spent -- the two numbers answer different
        # questions and were conflated under one "over budget" bullet
        # before (adversarial-review finding 6).
        summary_bullets += [f"- total tokens: median {statistics.median(totals):,.0f}, max {max(totals):,}, "
                            f"over_plan_budget {sum(t > BUDGET_TOKENS for t in totals)}/{len(totals)}",
                            f"- ceiling_hit (stop == piv_output_budget_exhausted): "
                            f"{sum(r.get('stop') == 'piv_output_budget_exhausted' for r in scored)}/{len(scored)}",
                            f"- turns: median {statistics.median(turns):.0f}, max {max(turns)}",
                            f"- reward: mean {statistics.mean(rewards):.3f} over {len(rewards)} scored, "
                            f"{sum(r == 1.0 for r in rewards)} at 1.0" if rewards else "- reward: none scored"]
        by_tool: dict = {}
        for r in scored:
            for t in r["tools"]:
                by_tool[t] = by_tool.get(t, 0) + 1
        summary_bullets.append(f"- tool calls over all rollouts: {dict(sorted(by_tool.items(), key=lambda kv: -kv[1]))}")
        by_artifact: dict = {}
        for r in rows:
            if r.get("quarantined"):
                continue
            key = r["artifact"] + (f"/{r['artifact_reason']}" if r.get("artifact_reason") else "")
            by_artifact[key] = by_artifact.get(key, 0) + 1
        summary_bullets.append(f"- artifact binding over all rollouts: "
                               f"{dict(sorted(by_artifact.items(), key=lambda kv: -kv[1]))}")
        by_budget_accounting: dict = {}
        for r in rows:
            if r.get("quarantined"):
                continue
            key = r.get("budget_accounting")
            by_budget_accounting[key] = by_budget_accounting.get(key, 0) + 1
        summary_bullets.append(f"- budget_accounting over all rollouts: "
                               f"{dict(sorted(by_budget_accounting.items(), key=lambda kv: -kv[1]))}")
        suspicious = [r for r in rows if not r.get("quarantined") and r.get("budget_accounting_suspicious")]
        summary_bullets.append(
            f"- SUSPICIOUS (a diagnostic, NOT invalid): {len(suspicious)}/"
            f"{sum(1 for r in rows if not r.get('quarantined'))} rows, "
            f"{dict(Counter(r['budget_accounting_suspicious'] for r in suspicious))}"
            if suspicious else "- SUSPICIOUS: none")
    lines += [""] + summary_bullets

    lines += ["", "## Per-turn detail", ""]
    for r in rows:
        if r.get("quarantined"):
            continue
        artifact_cell = r["artifact"] + (f"/{r['artifact_reason']}" if r.get("artifact_reason") else "")
        lines.append(f"### {r['selector']} (arm {r['arm']}, {artifact_cell}, submitted {r['submitted']})")
        for t in r.get("per_turn") or []:
            lines.append(format_per_turn_line(t))
        lines.append("")

    write_atomic(markdown_path, "\n".join(lines) + "\n")

    # THE CLOSING CHECK: after the LAST write, before this
    # cell is allowed to be complete. It is what bounds the residual race the
    # per-cell environment interval leaves open — a site-packages edit that
    # landed while this cell was running is caught HERE, the cell's own bytes
    # are withdrawn, and the executor stops the session rather than carrying a
    # row produced by an instrument nobody sealed.
    drift = verify_instrument("cell")
    if drift:
        return abandon_cell_on_drift("INSTRUMENT DRIFT (after the last write of this cell): "
                                     + "; ".join(drift), row_path, markdown_path, row_file_existed)
    if summary_bullets:
        print("\n" + "\n".join(summary_bullets))
    print(f"wrote reviews/budget_{slug}_{stamp}.md")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        raise SystemExit(main())
    except InstrumentDrift as exc:
        # The last line of defence: an `InstrumentDrift` raised anywhere this
        # module did not already handle must still leave the process with the
        # code the executor reads as "stop the session", never with a traceback
        # and a generic exit 1.
        print(f"REFUSED — {exc}", file=sys.stderr)
        raise SystemExit(INSTRUMENT_DRIFT_EXIT) from exc
