"""The measurement instrument itself, witnessed with scripted clients only.

No live model call, no NVIDIA key, no network. Everything here runs through
the real `env.evaluate()` door with a fake client (Codex T46 §7's own
recommendation) — the same `TurnScript` machinery `test_episode_contract.py`
uses, imported rather than duplicated.

`measure_budget.py` had four defects (Codex Turn 46, `design_chat/from_codex.md`
§2, §3, §6, §7), fixed in this rewrite and witnessed here:

  1. `newest_workspace()` — finding "the" workspace by scanning `%TEMP%` for
     the newest `beancount_env_*` directory — is GONE. Every artifact is now
     bound from THIS rollout's own state (`out["workspace"]`, `out["piv_phase"]`,
     the `delivery.json` the scorer publishes inside that exact workspace).
     Witnessed below: no write, a refused write, a committed-but-unsubmitted
     write, an accepted submit, and two rollouts running concurrently in two
     threads — each row must bind only its own artifact.
  2. Per-turn accounting (`per_turn_rows`) from `out["trajectory"]`.
  3. Arms (`--arm {A,B1,B2,B3}`) and the reasoning-replay projection, split
     out of `main()`'s closure into `make_client_cls` so a fake client can be
     injected without a live `args` object.
  4. This file.

Two framework-semantics findings are PINNED here rather than assumed:

  - `token_usage["final_output_tokens"]` / `["final_input_tokens"]`
    (`verifiers.legacy.utils.usage_utils.compute_context_token_metrics`) are
    NOT last-turn values despite the name. `final_output_tokens` is the SAME
    whole-rollout completion-token sum as `output_tokens`, computed a second
    way (`sum(completion_tokens over every step)`). `final_input_tokens` is
    `(last_step.prompt_tokens + last_step.completion_tokens) - total_completion`
    — for this client, whose `prompt_tokens` already includes every earlier
    turn's replayed output (a chat-completions client re-sends the whole
    conversation every turn), that is not any turn's actual input size; it
    is generally much SMALLER than both the true last-turn input and the
    cumulative `input_tokens`, because `total_completion` subtracts every
    turn's generated tokens, not just the ones already folded into the final
    prompt. This is exactly why the archived arm-A rows showed
    `final_output_tokens == completion_tokens` (both are the same sum) while
    `final_input_tokens` (26,257) was nowhere near `prompt_tokens` (592,577)
    — Codex T46 §7's own observation. `measure_budget.py` no longer presents
    those two fields as "final"/"last turn": `row["token_usage"]` carries
    them verbatim under their OWN framework names for audit, and
    `row["last_turn_input_tokens"]` / `["last_turn_output_tokens"]` are
    computed independently, directly, from the LAST trajectory step's own
    `Usage` — witnessed in `test_token_usage_final_fields_are_pinned...`
    below with an exact, hand-computed two-turn example.
  - The reasoning-replay projection (`make_client_cls`'s `to_native_prompt`)
    differs from full replay ONLY in `reasoning_content` on assistant
    messages — content, tool-call ids/names/arguments, tool replies and
    system/user messages are byte-identical — and it never mutates the
    caller's own `messages` (the rollout state's trajectory keeps its
    reasoning either way; only the wire projection drops it). Witnessed in
    `test_reasoning_replay_projection...` below with a structural diff.

    python tests/test_measure_budget.py
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
import threading
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

#: The generated tasks are KEYED, so `load_environment` refuses to build one
#: without a secret — and this file reaches it through
#: `build_experiment_contract` -> `expected_public_task_ids`, which every
#: contract-sealing witness below calls. `setdefault`, never assignment: a
#: machine that has a real `~/.piv` secret keeps it, and a machine that has
#: none (a fresh container, a CI runner) gets the SAME fixed test secret every
#: other keyed suite here uses — `test_exploits`, `test_sentinels`,
#: `test_generator`, `liveness_witness` and `test_lag` all pin this exact
#: value, and the sentinel/exploit fixtures are derived from it.
os.environ.setdefault("PIV_EVAL_SECRET", "5f1c7b9e2a4d6c8b0e1f3a5c7d9b2e4f6a8c0d2e4f6a8b0c1d3e5f7a9b1c3d5e")

import verifiers as vf  # noqa: E402
from verifiers.legacy.types import (  # noqa: E402
    AssistantMessage, ClientConfig, Response, SystemMessage, Tool, ToolCall, ToolMessage, Usage, UserMessage,
)

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402

import arm_table as AT  # noqa: E402
import measure_budget as mb  # noqa: E402
import run_arms as RA  # noqa: E402 -- imported so a broken schedule executor fails HERE
import schedule_arms as SA  # noqa: E402
import startup_witness as SW  # noqa: E402 -- the pre-request refusal
import test_episode_contract as tec  # noqa: E402

GOLDEN = tec.GOLDEN


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:12]:
            print(f"      {line}")
    return ok


# --------------------------------------------------------------------------
# fixtures: a scripted `env_mod` (no live credentials needed) and scripted
# clients that report a specific Usage per turn (TurnScript itself always
# reports usage=None)
# --------------------------------------------------------------------------

class _DefaultEnvModShim:
    """Forwards everything to the real package except `load_environment`,
    which always builds the default hand-authored task regardless of the
    selector — the same task `test_episode_contract.py` drives, which needs
    no evaluator secret and no live credentials. `one_rollout` otherwise
    takes `env_mod` completely at face value (`env_mod.PIVEvaluationBatchInvalid`,
    `env_mod.EpisodePhase`, `env_mod.DeliveryReceipt`, `env_mod.LEDGER`,
    `env_mod.digests_of`, ...), so everything but `load_environment` is
    forwarded rather than reimplemented."""

    PIVEvaluationBatchInvalid = env_mod.PIVEvaluationBatchInvalid

    def __getattr__(self, name):
        return getattr(env_mod, name)

    def load_environment(self, selector=None):
        return env_mod.load_environment()


class _PrebuiltEnvModShim:
    """Like `_DefaultEnvModShim`, but `load_environment` returns an ALREADY
    CONSTRUCTED environment rather than building one.

    `BeancountLedgerEnv.__post_init__` (via the framework's `Environment`)
    registers SIGINT/SIGTERM handlers, and `signal.signal` only works on the
    main thread — so `load_environment()` itself cannot run inside a worker
    thread. The concurrency witness therefore constructs both environments
    on the main thread first and hands each thread its own pre-built one;
    `one_rollout`'s call to `env_mod.load_environment(selector)` still runs
    (satisfying its real signature unchanged), it just returns the instance
    this shim was built with instead of constructing a fresh one."""

    PIVEvaluationBatchInvalid = env_mod.PIVEvaluationBatchInvalid

    def __init__(self, env):
        self._env = env

    def __getattr__(self, name):
        return getattr(env_mod, name)

    def load_environment(self, selector=None):
        return self._env


DEFAULT_SHIM = _DefaultEnvModShim()

# A dummy client config: an unreachable host and an api-key env var that is
# guaranteed not to be set, so client CONSTRUCTION (which only builds an
# `AsyncOpenAI`/httpx client object — no connection attempt) can never touch
# the real NVIDIA_API_KEY or the network. `TurnScript`/`UsageScript` below
# never call `get_native_response`'s real implementation, so this config is
# only ever read for its `.timeout`/`.api_base_url` attributes by `one_rollout`.
DUMMY_CONFIG = ClientConfig(client_type="openai_chat_completions", api_key_var="PIV_TEST_NO_SUCH_KEY_VAR",
                            api_base_url="https://example.invalid/v1", timeout=5.0, connect_timeout=5.0)


def scripted(turns):
    """A `client_cls` (as `one_rollout` wants: `client_cls(config)`) that
    plays `turns` — `ResponseMessage`s, via `test_episode_contract.TurnScript`
    — ignoring whatever `config` it is handed."""
    def factory(config):
        return tec.TurnScript(turns)
    return factory


class UsageScript(vf.Client):
    """Like `TurnScript`, but each turn also reports a specific `Usage` —
    needed to pin `token_usage["final_*"]` semantics, which TurnScript's
    always-`None` usage cannot exercise. `turns` is a list of
    `(ResponseMessage, Usage | None)` pairs; anything past the end is a bare
    empty turn with no usage, matching `TurnScript`'s own padding.

    `wire_caps`, when given, is set as `self.wire_caps` — the same shape
    `PacedClient.wire_caps` carries (Codex T47 §4/Q2) — so a test can inject
    a deliberately WRONG per-turn wire cap and witness `one_rollout` wiring
    it, end to end, into `budget_accounting = "INVALID/wire_cap_mismatch"`.
    Left unset (the default) `getattr(client, "wire_caps", None)` reads back
    `None`, exactly like a client that never captures wire caps at all —
    "not applicable", not a mismatch."""

    def __init__(self, turns, wire_caps=None):
        super().__init__(object())
        self.turns = list(turns)
        self.turn = 0
        if wire_caps is not None:
            self.wire_caps = wire_caps

    def setup_client(self, config):
        return object()

    async def to_native_tool(self, tool):
        return tool

    async def to_native_prompt(self, messages):
        return messages, {}

    async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
        self.turn += 1
        if self.turn <= len(self.turns):
            message, usage = self.turns[self.turn - 1]
        else:
            message, usage = tec.empty(), None
        return Response(id=f"scripted-{self.turn}", created=0, model=model, usage=usage, message=message)

    async def raise_from_native_response(self, response):
        return None

    async def from_native_response(self, response):
        return response

    async def close(self):
        return None


def usage_scripted(turns, wire_caps=None):
    def factory(config):
        return UsageScript(turns, wire_caps=wire_caps)
    return factory


def one(turns, selector="test:0", *, env_shim=None, archive=None, arm="A", max_tokens=4000) -> dict:
    """One rollout, through the real `env.evaluate()` door, with a scripted
    client and no live credentials."""
    return mb.one_rollout(env_shim or DEFAULT_SHIM, scripted(turns), DUMMY_CONFIG, selector, "scripted",
                          max_tokens, 0, 0, True, archive=archive, arm=arm)


# --------------------------------------------------------------------------
# 1. artifact binding — the delivered ledger comes from THIS rollout's own
#    state, never from scanning the temp directory (Codex T46 §7)
# --------------------------------------------------------------------------

def test_no_write_is_no_artifact_no_write():
    """The agent never wrote anything: NO_ARTIFACT/no_write, unsubmitted."""
    row = one([tec.submit("s1")])
    problems = []
    if row["artifact"] != "NO_ARTIFACT" or row["artifact_reason"] != "no_write":
        problems.append(f"artifact {row['artifact']}/{row.get('artifact_reason')}")
    if row["submitted"] is not False:
        problems.append(f"submitted {row['submitted']}")
    if row["phase"] != env_mod.EpisodePhase.NO_CANDIDATE.value:
        problems.append(f"phase {row['phase']}")
    if row.get("candidate_logical_text_digest") is not None:
        problems.append("a digest exists for a rollout that never wrote")
    return check("no write at all -> NO_ARTIFACT/no_write, unsubmitted", not problems, "\n".join(problems))


def test_refused_write_is_no_artifact_write_refused():
    """A stored candidate the protocol boundary refuses (a plugin directive,
    `test_episode_contract.HOSTILE`): a revision exists, but nothing is ever
    delivered — the scorer's own `_publish` REMOVES the public ledger for a
    protocol-rejected outcome, so there is nothing to bind even in principle."""
    row = one([tec.write("w", tec.HOSTILE), tec.submit("s1")])
    problems = []
    if row["artifact"] != "NO_ARTIFACT" or row["artifact_reason"] != "write_refused":
        problems.append(f"artifact {row['artifact']}/{row.get('artifact_reason')}")
    if row["submitted"] is not False:
        problems.append(f"submitted {row['submitted']}")
    if row["phase"] != env_mod.EpisodePhase.REJECTED.value:
        problems.append(f"phase {row['phase']}")
    if row.get("candidate_logical_text_digest") is None:
        problems.append("a revision was committed (the refused candidate) but no digest was recorded")
    if (Path(row["workspace"]) / env_mod.LEDGER).exists():
        problems.append("a refused write left a ledger.beancount on the public path")
    return check("a refused write -> NO_ARTIFACT/write_refused, a revision exists but nothing is delivered",
                 not problems, "\n".join(problems))


def test_committed_unsubmitted_write_is_bound_not_submitted():
    """An accepted write, then the episode runs to the turn cap without
    `submit`: the last committed revision is still scored and delivered
    (PLAN §6's turn-cap rule), so BOUND — but `submitted` is False, because
    the agent never ended the episode itself."""
    turns = [tec.write()] + [tec.calls((f"r{i}", "list_files", {})) for i in range(30)]
    row = one(turns)
    problems = []
    if row["artifact"] != "BOUND":
        problems.append(f"artifact {row['artifact']}/{row.get('artifact_reason')}")
    if row["submitted"] is not False:
        problems.append(f"submitted {row['submitted']}")
    if row["phase"] != env_mod.EpisodePhase.CANDIDATE.value:
        problems.append(f"phase {row['phase']}")
    if row["stop"] != "piv_turn_cap_no_submit":
        problems.append(f"stop {row['stop']}")
    if row["reward"] != 1.0:
        problems.append(f"reward {row['reward']}; the last committed revision must still score")
    return check("an accepted write, no submit, turn cap reached -> BOUND, submitted False",
                 not problems, "\n".join(problems))


def test_write_then_submit_is_bound_submitted_matches_delivery():
    """An accepted submit: BOUND, submitted True, and the bound digests are
    independently cross-checked against the `delivery.json` the scorer
    published inside this rollout's own workspace (not merely against
    `bind_artifact`'s own computation of the same thing)."""
    row = one([tec.write(), tec.submit()])
    problems = []
    if row["artifact"] != "BOUND" or row.get("artifact_reason") is not None:
        problems.append(f"artifact {row['artifact']}/{row.get('artifact_reason')}")
    if row["submitted"] is not True:
        problems.append(f"submitted {row['submitted']}")
    if row["phase"] != env_mod.EpisodePhase.TERMINAL.value:
        problems.append(f"phase {row['phase']}")
    if row["reward"] != 1.0:
        problems.append(f"reward {row['reward']}")
    delivery_path = Path(row["workspace"]) / "delivery.json"
    if not delivery_path.is_file():
        problems.append("no delivery.json in the rollout's own workspace")
    else:
        delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
        if row.get("artifact_stored_bytes_digest") != delivery["artifact_stored_bytes_digest"]:
            problems.append("row's bound stored-bytes digest disagrees with delivery.json")
        if row.get("artifact_logical_text_digest") != delivery["artifact_logical_text_digest"]:
            problems.append("row's bound logical-text digest disagrees with delivery.json")
    ledger_bytes = (Path(row["workspace"]) / env_mod.LEDGER).read_bytes()
    now = env_mod.digests_of(ledger_bytes)
    if row.get("artifact_logical_text_digest") != now["logical_text_digest"]:
        problems.append("row's bound digest disagrees with the ledger.beancount actually on disk")
    return check("write then submit -> BOUND, submitted True, digests match delivery.json AND the file on disk",
                 not problems, "\n".join(problems))


def test_two_concurrent_rollouts_each_bind_their_own_artifact():
    """Two rollouts, two threads, each writing a DIFFERENT valid ledger text
    (GOLDEN, and GOLDEN plus a trailing `; marker-B` comment). Each row must
    bind its OWN workspace's artifact — never the other's.

    A note on what "different" can mean here: `render_committed` (the
    scorer's own canonicalizer) prints planted repairs from the graph and
    preserved entries from the ORIGINAL file — never from what the agent
    actually typed — precisely so that decorating a submission cannot change
    the delivered bytes (the anti-narration-exploit property `test_committed.py`
    holds this environment to). A free-floating comment is not part of any
    directive at all, so it is dropped entirely. Empirically (verified
    before writing this test): `render_committed(GOLDEN)` and
    `render_committed(GOLDEN + "; marker-B\\n")` are BYTE-IDENTICAL, so the
    two rollouts' DELIVERED artifacts legitimately coincide — that is not a
    bug in this instrument, it is the environment refusing to let narration
    move the score. So the meaningful concurrency proof is not "the final
    bytes differ" (they correctly do not, here); it is:

      (a) each rollout gets its own workspace (proves thread isolation —
          nothing here still scans a shared temp directory for "the" newest
          one);
      (b) each rollout's own RAW commit digest (`candidate_logical_text_digest`,
          captured at write time, before any canonicalization) reflects what
          THAT rollout itself wrote, not the other's; and
      (c) each rollout's bound artifact digest is self-consistent against
          the ledger.beancount actually sitting in ITS OWN workspace and
          against ITS OWN delivery.json — proving the binding never drifted
          to a directory the code did not itself return from `evaluate()`.
    """
    marked = GOLDEN + "; marker-B\n"
    # `load_environment()` registers SIGINT/SIGTERM handlers at construction
    # (`Environment.__post_init__`), which only works on the main thread —
    # so both environments are built here, before the threads start.
    env_a = env_mod.load_environment()
    env_b = env_mod.load_environment()
    results: dict = {}

    def run_one(key, env, text):
        shim = _PrebuiltEnvModShim(env)
        turns = [tec.write("w", text), tec.submit("s")]
        results[key] = one(turns, selector=f"test:concurrent:{key}", env_shim=shim)

    ta = threading.Thread(target=run_one, args=("A", env_a, GOLDEN))
    tb = threading.Thread(target=run_one, args=("B", env_b, marked))
    ta.start(); tb.start()
    ta.join(timeout=60); tb.join(timeout=60)

    problems = []
    if ta.is_alive() or tb.is_alive():
        return check("two concurrent rollouts each bind their own artifact", False, "a thread did not finish in time")
    row_a, row_b = results.get("A"), results.get("B")
    if row_a is None or row_b is None:
        return check("two concurrent rollouts each bind their own artifact", False,
                     f"a thread raised: {results}")
    for label, row in (("A", row_a), ("B", row_b)):
        if row["artifact"] != "BOUND":
            problems.append(f"{label}: artifact {row['artifact']}/{row.get('artifact_reason')}")
        if row["submitted"] is not True:
            problems.append(f"{label}: submitted {row['submitted']}")
    if problems:
        return check("two concurrent rollouts each bind their own artifact", False, "\n".join(problems))
    if row_a["workspace"] == row_b["workspace"]:
        problems.append("both rollouts share a workspace path; the witness is vacuous")
    if row_a["rollout_id"] == row_b["rollout_id"]:
        problems.append("both rollouts share a rollout id")
    if row_a["candidate_logical_text_digest"] == row_b["candidate_logical_text_digest"]:
        problems.append("both rollouts' raw commit digests are equal; GOLDEN and GOLDEN+marker-B must differ "
                        "before canonicalization")
    # self-consistency: each row's bound digest matches the file actually
    # sitting in ITS OWN workspace, and ITS OWN delivery.json
    for label, row in (("A", row_a), ("B", row_b)):
        raw = (Path(row["workspace"]) / env_mod.LEDGER).read_bytes()
        now = env_mod.digests_of(raw)
        if now["logical_text_digest"] != row["artifact_logical_text_digest"]:
            problems.append(f"{label}: bound digest disagrees with the file in its own workspace")
        delivery = json.loads((Path(row["workspace"]) / "delivery.json").read_text(encoding="utf-8"))
        if delivery["artifact_logical_text_digest"] != row["artifact_logical_text_digest"]:
            problems.append(f"{label}: bound digest disagrees with its own delivery.json")
        if delivery["rollout_id"] != row["rollout_id"]:
            problems.append(f"{label}: delivery.json in its own workspace names a different rollout id")
    # and, as documented above: the DELIVERED bytes legitimately coincide,
    # by the environment's own anti-narration-exploit design — asserted
    # explicitly so a change in that design shows up here rather than as a
    # silently-vacuous "differ" assumption elsewhere in this test.
    if row_a["artifact_logical_text_digest"] != row_b["artifact_logical_text_digest"]:
        problems.append("the delivered artifacts differ; the render_committed canonicalization assumption "
                        "this test's docstring documents no longer holds — update the docstring, not this check")
    return check("two concurrent rollouts (GOLDEN vs GOLDEN+comment) each bind their own workspace, own raw "
                 "commit digest and own delivery.json — self-consistently, never the other's",
                 not problems, "\n".join(problems))


def test_bind_artifact_defaults_when_state_is_sparse():
    """`bind_artifact` alone, over hand-built `out` dicts, pinning its
    defaults: no workspace at all, and a workspace with no phase recorded,
    both read the same as an explicit ACTIVE_NO_CANDIDATE (`episode_phase`'s
    own default), rather than raising or guessing."""
    problems = []
    r1 = mb.bind_artifact({}, env_mod)
    if (r1["artifact"], r1["artifact_reason"]) != ("NO_ARTIFACT", "no_write"):
        problems.append(f"empty out: {r1}")
    r2 = mb.bind_artifact({"workspace": "C:\\nonexistent\\path\\for\\sure"}, env_mod)
    if (r2["artifact"], r2["artifact_reason"]) != ("NO_ARTIFACT", "no_write"):
        problems.append(f"workspace with no phase: {r2}")
    r3 = mb.bind_artifact({"workspace": "C:\\nonexistent\\path\\for\\sure",
                           "piv_phase": env_mod.EpisodePhase.CANDIDATE.value}, env_mod)
    if (r3["artifact"], r3["artifact_reason"]) != ("NO_ARTIFACT", "not_scored"):
        problems.append(f"accepted phase but no delivery.json on disk: {r3}")
    return check("bind_artifact defaults a missing workspace/phase to no_write, and an accepted phase with no "
                 "delivery.json on disk to not_scored, rather than raising", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 2. token_usage["final_*"] semantics, pinned
# --------------------------------------------------------------------------

def test_token_usage_final_fields_are_pinned_and_row_names_them_truthfully():
    """A two-turn scripted client: turn 1 reports Usage(prompt=1000,
    completion=100), turn 2 reports Usage(prompt=2000, completion=50).

    Pinning `verifiers.legacy.utils.usage_utils.compute_context_token_metrics`:
    `final_output_tokens` is the SUM of completion_tokens over every step —
    100 + 50 = 150 — the same number `output_tokens` already carries, computed
    a second way. `final_input_tokens` is
    `(last_step.prompt_tokens + last_step.completion_tokens) - total_completion`
    = (2000 + 50) - 150 = 1900 — NOT turn 2's actual prompt_tokens (2000).
    Both are hand-computed here and asserted exactly, so a change to that
    function's formula fails this test rather than surfacing as an
    unexplained number in an archived row.

    `measure_budget.py` therefore never labels those two fields "final" in
    its own row: `last_turn_input_tokens`/`last_turn_output_tokens` are
    computed independently from the LAST trajectory step's own `Usage`
    (2000, 50 — the true last-turn values), and `token_usage` carries the
    framework's fields verbatim, under their own name, for audit.
    """
    turns = [
        (tec.write(), Usage(prompt_tokens=1000, reasoning_tokens=0, completion_tokens=100, total_tokens=1100)),
        (tec.submit(), Usage(prompt_tokens=2000, reasoning_tokens=0, completion_tokens=50, total_tokens=2050)),
    ]
    row = mb.one_rollout(DEFAULT_SHIM, usage_scripted(turns), DUMMY_CONFIG, "test:usage", "scripted",
                         4000, 0, 0, True)
    problems = []
    usage = row.get("token_usage") or {}
    if usage.get("input_tokens") != 3000.0 or usage.get("output_tokens") != 150.0:
        problems.append(f"cumulative input/output: {usage.get('input_tokens')}/{usage.get('output_tokens')}")
    if usage.get("final_output_tokens") != 150:
        problems.append(f"final_output_tokens {usage.get('final_output_tokens')}, expected 150 "
                        "(the SAME cumulative sum as output_tokens, not a last-turn value)")
    if usage.get("final_input_tokens") != 1900:
        problems.append(f"final_input_tokens {usage.get('final_input_tokens')}, expected 1900 "
                        "((2000+50)-150) -- pinned formula, not turn 2's real prompt_tokens of 2000")
    if row.get("last_turn_input_tokens") != 2000:
        problems.append(f"last_turn_input_tokens {row.get('last_turn_input_tokens')}, expected 2000 "
                        "(turn 2's OWN prompt_tokens -- the truthful last-turn value)")
    if row.get("last_turn_output_tokens") != 50:
        problems.append(f"last_turn_output_tokens {row.get('last_turn_output_tokens')}")
    if row.get("prompt_tokens") != 3000.0 or row.get("completion_tokens") != 150.0:
        problems.append(f"row's cumulative prompt/completion tokens: {row.get('prompt_tokens')}/{row.get('completion_tokens')}")
    per_turn = row.get("per_turn") or []
    if len(per_turn) != 2 or per_turn[0]["input_tokens"] != 1000 or per_turn[1]["input_tokens"] != 2000:
        problems.append(f"per_turn input tokens: {[t.get('input_tokens') for t in per_turn]}")
    if per_turn[-1:] and per_turn[-1]["cumulative_input_tokens"] != 3000:
        problems.append(f"final cumulative_input_tokens {per_turn[-1]['cumulative_input_tokens']}, expected 3000")
    if any("final_output_tokens" in t or "final_input_tokens" in t for t in per_turn):
        problems.append("per_turn rows carry a 'final_*' key; the misleading name must not spread there")
    return check('token_usage["final_output_tokens"]/["final_input_tokens"] pinned exactly (150, 1900 -- neither '
                 "is a last-turn value); last_turn_input_tokens/last_turn_output_tokens are the truthful ones (2000, 50)",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3. the reasoning-replay projection
# --------------------------------------------------------------------------

def _fake_post_capturing_bodies(bodies: list):
    """A drop-in replacement for `post_chat_completion_with_routed_experts_
    sidecar` that records the exact `body` dict it was called with (the SAME
    dict the real function would POST) and returns an inert placeholder —
    used to inspect what a client's `get_native_response` actually
    constructed without any network call and without needing a fully valid
    fake `ChatCompletion` to satisfy downstream parsing, because the caller
    inspects `bodies` directly rather than the return value."""
    async def _fake(client, path, *, body, extra_headers=None):
        bodies.append(body)
        return object()
    return _fake


def test_reasoning_replay_projection_diffs_only_reasoning_content_and_does_not_mutate_input():
    """A 3-turn-shaped history built the way the real client does (system,
    user, an assistant turn with `reasoning_content` + `tool_calls`, a tool
    reply, a second assistant turn with reasoning + content, a second tool
    reply) run through `make_client_cls(0, reasoning_replay=True)` and
    `(0, reasoning_replay=False)` instances' `to_native_prompt`.

    Proves by structural diff (`json.dumps(..., sort_keys=True)` per message,
    `reasoning_content` excluded) that content, tool-call ids/names/arguments,
    tool replies and the system/user messages are byte-identical between the
    two projections — the ONLY difference is `reasoning_content` on assistant
    messages, present under full replay and absent under the projection.

    Also proves the caller's own `messages` objects are unchanged after both
    calls: `to_native_prompt`'s no-replay branch only mutates the FRESH
    native dict list `super().to_native_prompt` just built (see
    `make_client_cls`'s docstring), never the rollout state's own trajectory
    — so a client running under the no-replay policy still leaves full
    reasoning in the recorded trajectory for audit (Codex T46 §2's
    requirement).

    Codex T47 §8 asks the "only difference" assertion to cover the COMPLETE
    native request material, not just the prompt-message list. Extended
    here to also prove, between the SAME two `replay_on`/`replay_off`
    instances:

      - the `extra` dict `to_native_prompt` returns is identical (both are
        `{}` for this client, asserted rather than assumed);
      - the native TOOL SCHEMA (`to_native_tool`) is identical — reasoning
        replay has no business touching tool schema at all, and this is the
        regression guard that keeps it that way;
      - the PROCESSED SAMPLING FIELDS actually placed in the wire body
        (`get_native_response`'s own `normalize_sampling_args`, captured via
        the same `post_chat_completion_with_routed_experts_sidecar`
        monkeypatch `PacedClient` itself uses for `wire_caps` — see
        `make_client_cls`) are byte-identical between the two arms for the
        SAME `sampling_args` input, and the two wire `messages` lists differ
        from each other in EXACTLY the same way `prompt_on`/`prompt_off` do
        (`reasoning_content` only) — i.e. the "only difference" property
        holds all the way to what would actually go out on the wire, not
        only at the `to_native_prompt` layer.
    """
    messages = [
        SystemMessage(content="you are a bookkeeper"),
        UserMessage(content="fix the ledger"),
        AssistantMessage(content="", reasoning_content="I should read the ledger first.",
                         tool_calls=[ToolCall(id="c1", name="read_file",
                                              arguments='{"name":"ledger.beancount"}')]),
        ToolMessage(tool_call_id="c1", content="...ledger contents..."),
        AssistantMessage(content="Now I will write the fix.", reasoning_content="The bank shows an extra 40 fee.",
                         tool_calls=[ToolCall(id="c2", name="write_ledger", arguments='{"content":"..."}')]),
        ToolMessage(tool_call_id="c2", content="committed:true"),
    ]
    snapshot = copy.deepcopy(messages)

    replay_on = mb.make_client_cls(0.0, True)(DUMMY_CONFIG)
    replay_off = mb.make_client_cls(0.0, False)(DUMMY_CONFIG)

    problems = []
    prompt_on, extra_on = asyncio.run(replay_on.to_native_prompt(messages))
    prompt_off, extra_off = asyncio.run(replay_off.to_native_prompt(messages))

    if messages != snapshot:
        problems.append("the caller's own `messages` were mutated by to_native_prompt")

    if len(prompt_on) != len(prompt_off) or len(prompt_on) != len(messages):
        problems.append(f"message counts: on={len(prompt_on)} off={len(prompt_off)} input={len(messages)}")
    else:
        for i, (a, b) in enumerate(zip(prompt_on, prompt_off)):
            keys = set(a) | set(b)
            for key in sorted(keys):
                if key == "reasoning_content":
                    continue
                av, bv = a.get(key), b.get(key)
                if json.dumps(av, sort_keys=True, default=str) != json.dumps(bv, sort_keys=True, default=str):
                    problems.append(f"message {i} field {key!r} differs: {av!r} vs {bv!r}")

    reasoning_on = [m.get("reasoning_content") if isinstance(m, dict) else None for m in prompt_on]
    reasoning_off = [m.get("reasoning_content") if isinstance(m, dict) else None for m in prompt_off]
    expected_on = [None, None, "I should read the ledger first.", None, "The bank shows an extra 40 fee.", None]
    if reasoning_on != expected_on:
        problems.append(f"full replay reasoning_content: {reasoning_on}, expected {expected_on}")
    if any(v is not None for v in reasoning_off):
        problems.append(f"no-replay projection still carries reasoning_content: {reasoning_off}")

    # and the original AssistantMessage objects still carry their reasoning —
    # the audit record the environment's own state.trajectory keeps
    for m in messages:
        if isinstance(m, AssistantMessage) and m.tool_calls:
            if m.reasoning_content is None:
                problems.append("an original assistant message lost its reasoning_content")

    # Codex T47 §8: extend the "only difference" assertion to the `extra`
    # dict, the native tool schema, and the actual wire body.
    if extra_on != extra_off:
        problems.append(f"to_native_prompt's `extra` dict differs: {extra_on!r} vs {extra_off!r}")

    tool = Tool(name="read_file", description="Read a public file.",
               parameters={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]})
    native_tool_on = asyncio.run(replay_on.to_native_tool(tool))
    native_tool_off = asyncio.run(replay_off.to_native_tool(tool))
    if json.dumps(native_tool_on, sort_keys=True, default=str) != json.dumps(native_tool_off, sort_keys=True, default=str):
        problems.append(f"native tool schema differs between arms: {native_tool_on!r} vs {native_tool_off!r}")

    # The actual wire body each arm's `get_native_response` would send for
    # the SAME sampling_args/tools -- captured through the exact monkeypatch
    # seam `PacedClient` uses in production, never re-implemented.
    sampling_args = {"max_tokens": 4000, "temperature": 0.0, "top_p": 1.0, "seed": 1234}
    bodies_on: list = []
    bodies_off: list = []
    import verifiers.legacy.clients.openai_chat_completions_client as oai_mod
    original_post = oai_mod.post_chat_completion_with_routed_experts_sidecar
    try:
        oai_mod.post_chat_completion_with_routed_experts_sidecar = _fake_post_capturing_bodies(bodies_on)
        asyncio.run(replay_on.get_native_response(prompt_on, "scripted-model", dict(sampling_args), [native_tool_on]))
        oai_mod.post_chat_completion_with_routed_experts_sidecar = _fake_post_capturing_bodies(bodies_off)
        asyncio.run(replay_off.get_native_response(prompt_off, "scripted-model", dict(sampling_args), [native_tool_off]))
    finally:
        oai_mod.post_chat_completion_with_routed_experts_sidecar = original_post

    if len(bodies_on) != 1 or len(bodies_off) != 1:
        problems.append(f"expected exactly one captured wire body per arm: {len(bodies_on)} vs {len(bodies_off)}")
    else:
        body_on, body_off = bodies_on[0], bodies_off[0]
        wire_messages_on, wire_messages_off = body_on.pop("messages"), body_off.pop("messages")
        for key in sorted(set(body_on) | set(body_off)):
            if json.dumps(body_on.get(key), sort_keys=True, default=str) != json.dumps(body_off.get(key), sort_keys=True, default=str):
                problems.append(f"wire body field {key!r} differs between arms: {body_on.get(key)!r} vs {body_off.get(key)!r}")
        # the wire-level messages must differ EXACTLY the way prompt_on/prompt_off already do
        if json.dumps(wire_messages_on, sort_keys=True, default=str) != json.dumps(prompt_on, sort_keys=True, default=str):
            problems.append("the wire body's messages for the full-replay arm are not the SAME prompt_on that was sent in")
        if json.dumps(wire_messages_off, sort_keys=True, default=str) != json.dumps(prompt_off, sort_keys=True, default=str):
            problems.append("the wire body's messages for the no-replay arm are not the SAME prompt_off that was sent in")

    return check("the no-replay projection differs from full replay ONLY in reasoning_content on assistant "
                 "messages -- proven at the to_native_prompt layer AND all the way to the wire body -- and "
                 "mutates neither projection's own list nor the caller's original messages; extra dict and "
                 "native tool schema are identical between arms",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 5. budget accounting: fail closed (Codex T47 §4/§11, Q3/Q4)
# --------------------------------------------------------------------------

def test_compute_budget_accounting_reasons_pure():
    """`compute_budget_accounting` (the pure function, adversarial-review
    follow-up to Codex T47) over hand-built inputs — EVERY code in the
    CLOSED set (`BUDGET_ACCOUNTING_CODES`, `ENV_BUDGET_ACCOUNTING_CODES`
    verbatim, the `env_unrecognized` fallback), checked exactly, in the
    documented check order (a priority case proves our own checks win over
    the env's own code when both would apply), without going through a live
    rollout. Also pins that it never raises on strings/floats/negatives/
    bools where an int is expected, and that `reported_output_tokens` being
    a FLOAT (the framework's own real shape, e.g. `150.0`) still compares
    correctly rather than being flagged `usage_not_integer` itself."""
    problems = []
    seen: list[str] = []

    def turn(cap, out, in_tok=10, content_chars=0, reasoning_chars=0, tool_chars=0):
        return {"input_tokens": in_tok, "output_tokens": out, "request_max_tokens": cap,
               "assistant_content_chars": content_chars, "assistant_reasoning_chars": reasoning_chars,
               "tool_call_chars": tool_chars}

    def expect(label, request_caps, per_turn, wire_caps, env_code, reported, ceiling, attempts, want,
               requests=None, rollout_id=None):
        got = mb.compute_budget_accounting(request_caps, per_turn, wire_caps, env_code, reported, ceiling,
                                           attempts, requests=requests, rollout_id=rollout_id)
        seen.append(got)
        if got != want:
            problems.append(f"{label}: got {got!r}, want {want!r}")

    # 1. no_request_caps
    expect("caps absent", None, [turn(100, 50)], None, None, 50, 0, None, "INVALID/no_request_caps")

    # 2. caps_turns_mismatch -- BOTH directions
    expect("caps shorter than per_turn", [100], [turn(100, 50), turn(50, 20)], None, None, 70, 0, None,
          "INVALID/caps_turns_mismatch")
    expect("caps longer than per_turn", [100, 50, 25], [turn(100, 50)], None, None, 50, 0, None,
          "INVALID/caps_turns_mismatch")

    # 3. no_turns
    expect("no turns", [], [], None, None, 0, 0, None, "INVALID/no_turns")

    # 4. framework_retry
    expect("framework retry (attempts=2)", [100], [turn(100, 50)], None, None, 50, 0, 2, "INVALID/framework_retry")
    expect("single attempt (attempts=1) is fine", [100], [turn(100, 50)], None, None, 50, 0, 1, "VALID")
    expect("attempts=None is not-applicable, not a retry", [100], [turn(100, 50)], None, None, 50, 0, None, "VALID")

    # 5. usage_missing
    empty_extra = {"assistant_content_chars": 0, "assistant_reasoning_chars": 0}
    expect("usage missing (input)", [100], [{"input_tokens": None, "output_tokens": 50, "request_max_tokens": 100,
                                             **empty_extra}], None, None, 50, 0, None, "INVALID/usage_missing")
    expect("usage missing (output)", [100], [{"input_tokens": 10, "output_tokens": None, "request_max_tokens": 100,
                                              **empty_extra}], None, None, 50, 0, None, "INVALID/usage_missing")

    # 6. usage_not_integer -- never raises on strings/floats/negatives/bools
    for bad in ("50", 50.0, -5, True):
        expect(f"usage not integer (output_tokens={bad!r})", [100], [turn(100, bad)], None, None, 50, 0, None,
              "INVALID/usage_not_integer")

    # 7. usage_total_missing
    expect("usage total missing", [100], [turn(100, 50)], None, None, None, 0, None, "INVALID/usage_total_missing")

    # 8. completion_exceeds_cap
    expect("completion exceeds cap", [100], [turn(100, 150)], None, None, 150, 0, None,
          "INVALID/completion_exceeds_cap")

    # 9. ceiling_exceeded -- sum of completion over the ROW's max_total_completion_tokens
    expect("ceiling exceeded", [1000, 1000], [turn(1000, 600), turn(1000, 600)], None, None, 1200, 1000, None,
          "INVALID/ceiling_exceeded")
    expect("ceiling not checked when disabled (0)", [1000, 1000], [turn(1000, 600), turn(1000, 600)], None, None,
          1200, 0, None, "VALID")

    # 10. cumulative_mismatch -- exact integer equality; the framework's own
    # sums come back as FLOATS (e.g. 150.0) and must compare correctly, not
    # be flagged usage_not_integer themselves (unreachable through a real
    # rollout -- both derive from the same Usage stream there -- so this is
    # a pure-function-only witness, deliberately, per its own docstring)
    expect("cumulative mismatch", [100, 50], [turn(100, 50), turn(50, 50)], None, None, 999, 0, None,
          "INVALID/cumulative_mismatch")
    expect("cumulative match, reported as a float", [100, 50], [turn(100, 50), turn(50, 50)], None, None, 100.0,
          0, None, "VALID")

    # 11. wire_caps_incomplete -- shorter than per_turn, or containing a gap
    expect("wire caps too short", [100, 50], [turn(100, 50), turn(50, 50)], [{"max_completion_tokens": 100}],
          None, 100, 0, None, "INVALID/wire_caps_incomplete")
    expect("wire caps has a gap", [100, 50], [turn(100, 50), turn(50, 50)],
          [{"max_completion_tokens": 100}, None], None, 100, 0, None, "INVALID/wire_caps_incomplete")

    # 12. extra_wire_request -- Codex T48a §3.2: one SURPLUS provider request
    # the trajectory's usage never accounts for. The previous code examined
    # only the first len(per_turn) entries and returned VALID here.
    expect("one surplus wire request", [100], [turn(100, 50)],
          [{"max_completion_tokens": 100}, {"max_completion_tokens": 100}], None, 50, 0, None,
          "INVALID/extra_wire_request")
    expect("two surplus wire requests", [100, 50], [turn(100, 50), turn(50, 50)],
          [{"max_completion_tokens": 100}, {"max_completion_tokens": 50}, {"max_completion_tokens": 50},
           {"max_completion_tokens": 50}], None, 100, 0, None, "INVALID/extra_wire_request")

    # 12. wire_cap_mismatch -- only checked when wire_caps is COMPLETE
    expect("wire_caps None is not-applicable, not a mismatch", [100, 50], [turn(100, 50), turn(50, 50)], None,
          None, 100, 0, None, "VALID")
    expect("wire cap mismatch", [100, 50], [turn(100, 50), turn(50, 50)],
          [{"max_completion_tokens": 100}, {"max_completion_tokens": 999}], None, 100, 0, None,
          "INVALID/wire_cap_mismatch")
    expect("wire cap agrees", [100, 50], [turn(100, 50), turn(50, 50)],
          [{"max_completion_tokens": 100}, {"max_completion_tokens": 50}], None, 100, 0, None, "VALID")
    expect("wire cap agrees, max_tokens spelling", [100], [turn(100, 50)], [{"max_tokens": 100}], None, 50, 0,
          None, "VALID")

    # 14. request_count_mismatch -- the client's own per-HTTP-attempt log
    # disagrees with the number of turns. A 429 attempt is NOT a turn.
    ok_request = {"turn": 1, "attempt": 1, "status": "ok", "seconds": 1.0, "attempt_id": "a", "rollout_id": "r"}
    expect("one ok request, one turn", [100], [turn(100, 50)], None, None, 50, 0, None, "VALID",
          requests=[ok_request], rollout_id="r")
    expect("a 429 attempt is not a turn", [100], [turn(100, 50)], None, None, 50, 0, None, "VALID",
          requests=[{**ok_request, "status": "rate_limited"}, ok_request], rollout_id="r")
    expect("two ok requests, one turn", [100], [turn(100, 50)], None, None, 50, 0, None,
          "INVALID/request_count_mismatch", requests=[ok_request, {**ok_request, "turn": 2}], rollout_id="r")
    # Attempt identity (Codex T48b §10): a billed request bound to ANOTHER
    # rollout id, or to a second attempt nonce, is a discarded attempt's spend.
    expect("a request from another rollout id", [100], [turn(100, 50)], None, None, 50, 0, None,
          "INVALID/framework_retry", requests=[ok_request, {**ok_request, "rollout_id": "other"}],
          rollout_id="r")
    expect("two attempt nonces", [100], [turn(100, 50)], None, None, 50, 0, None, "INVALID/framework_retry",
          requests=[ok_request, {**ok_request, "attempt_id": "b"}], rollout_id="r")

    # usage_implausible is NOT an accounting code any more (Codex T48b §3): a
    # generic characters-per-token heuristic is a SUSPICION, not a validity
    # theorem -- it can fire differently across arms (a replay arm changes
    # the shape of emitted content) and would bias the comparison it guards.
    expect("an implausible chars/token ratio is VALID here, not INVALID", [1000],
          [turn(1000, 10, content_chars=200)], None, None, 10, 0, None, "VALID")

    # 15. env_<code> -- verbatim, checked LAST (only when nothing else failed)
    for env_code in mb.ENV_BUDGET_ACCOUNTING_CODES:
        expect(f"env code {env_code!r}", [100], [turn(100, 50)], None, env_code, 50, 0, None,
              f"INVALID/env_{env_code}")
    expect("unrecognized env code falls back to env_unrecognized, not interpolated verbatim", [100],
          [turn(100, 50)], None, "some_future_code_this_file_does_not_know_about", 50, 0, None,
          "INVALID/env_unrecognized")
    expect("our own check wins over the env's code when both would apply", [100], [turn(100, 150)], None,
          "usage_absent", 150, 0, None, "INVALID/completion_exceeds_cap")

    # VALID: every check passes
    expect("valid", [100, 50], [turn(100, 50), turn(50, 50)], None, None, 100, 0, None, "VALID")

    leaked = sorted(set(seen) - set(mb.ALL_BUDGET_ACCOUNTING_STATUSES))
    if leaked:
        problems.append(f"statuses outside the pinned closed set: {leaked}")

    return check("compute_budget_accounting names every code in the closed set exactly, in the documented "
                 "check order, and never returns a status outside that set", not problems, "\n".join(problems))


def test_no_request_caps_end_to_end_when_ceiling_disabled():
    """The REAL end-to-end path (Codex T47 §4/Q4's headline change): when
    the episode-output ceiling is 0 (disabled), the clamp in
    `get_model_response` never runs (`if ceiling > 0:`), so
    `state["piv_request_max_tokens"]` is never populated at all -- exactly
    the "state lacks it" case, produced by the REAL package, not simulated.

    `one_rollout` now sets `max_total_completion_tokens` on the environment
    UNCONDITIONALLY (see `one_rollout`'s own comment): a PRIOR version of
    this file only called `set_max_total_completion_tokens` when the
    argument was `> 0`, which made this file's own "0 disables it" CLI help
    text false in practice (0 silently left the package's nonzero default in
    effect instead). `one()` always passes `max_total_completion_tokens=0`,
    so every OTHER test in this file already exercises this same disabled-
    ceiling path; this test names it explicitly rather than leaving it
    implicit.
    """
    row = one([tec.write(), tec.submit()])
    problems = []
    if row["budget_accounting"] != "INVALID/no_request_caps":
        problems.append(f"budget_accounting {row['budget_accounting']!r}, expected INVALID/no_request_caps "
                        f"(per_turn: {row.get('per_turn')})")
    return check("a rollout whose environment has the episode-output ceiling disabled (no per-request cap "
                 "sequence at all) is INVALID/no_request_caps, excluded from the equal-budget table, kept in "
                 "the archive", not problems, "\n".join(problems))


def test_usage_missing_end_to_end_with_plain_turnscript():
    """`TurnScript` (the ordinary scripted client every artifact-binding
    witness above uses) always reports `usage=None` per turn. With the
    episode-output ceiling ENABLED (so `piv_request_max_tokens` IS
    populated by the real environment and the first check passes), every
    turn's missing provider usage must still fail closed rather than being
    archived as a silently-valid row."""
    row = mb.one_rollout(DEFAULT_SHIM, scripted([tec.write(), tec.submit()]), DUMMY_CONFIG, "test:usage_missing",
                         "scripted", 4000, 0, 100, True)
    problems = []
    if row["budget_accounting"] != "INVALID/usage_missing":
        problems.append(f"budget_accounting {row['budget_accounting']!r}, expected INVALID/usage_missing "
                        f"(per_turn: {row.get('per_turn')})")
    return check("a scripted client that never reports provider usage is INVALID/usage_missing even when the "
                 "per-request cap sequence itself is present and well-formed", not problems, "\n".join(problems))


def test_valid_completion_exceeds_cap_and_wire_cap_mismatch_end_to_end():
    """`UsageScript`, with the episode-output ceiling enabled so the
    environment's own clamp populates real per-turn caps: `[100, 50]` for a
    2-turn rollout (`max_tokens=4000` per-turn cap, `max_total_completion_
    tokens=100` ceiling — turn 1 asks for `min(4000, 100-0)=100`, turn 2 for
    `min(4000, 100-50)=50`). Three end-to-end scenarios over the SAME shape:

      1. both turns report completion_tokens at or under their own cap,
         wire_caps unset (not applicable) -> VALID.
      2. turn 2 reports completion_tokens (999) OVER its own cap (50) ->
         INVALID/completion_exceeds_cap.
      3. scenario 1's usage again, but `wire_caps` (as `PacedClient` would
         capture it) disagrees with the declared cap on turn 2 ->
         INVALID/wire_cap_mismatch, and `row["wire_caps"]` round-trips the
         exact list the client reported.
    """
    problems = []

    def two_turns(t1_out, t2_out):
        return [
            (tec.write(), Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=t1_out, total_tokens=10 + t1_out)),
            (tec.submit(), Usage(prompt_tokens=20, reasoning_tokens=0, completion_tokens=t2_out, total_tokens=20 + t2_out)),
        ]

    row_valid = mb.one_rollout(DEFAULT_SHIM, usage_scripted(two_turns(50, 50)), DUMMY_CONFIG, "test:budget_valid",
                               "scripted", 4000, 0, 100, True)
    if row_valid["budget_accounting"] != "VALID":
        problems.append(f"scenario 1 (valid): budget_accounting {row_valid['budget_accounting']!r}, "
                        f"per_turn {row_valid.get('per_turn')}")

    row_exceeds = mb.one_rollout(DEFAULT_SHIM, usage_scripted(two_turns(50, 999)), DUMMY_CONFIG,
                                 "test:budget_exceeds", "scripted", 4000, 0, 100, True)
    if row_exceeds["budget_accounting"] != "INVALID/completion_exceeds_cap":
        problems.append(f"scenario 2 (exceeds cap): budget_accounting {row_exceeds['budget_accounting']!r}, "
                        f"per_turn {row_exceeds.get('per_turn')}")

    mismatched_wire = [{"max_completion_tokens": 100}, {"max_completion_tokens": 999}]
    row_mismatch = mb.one_rollout(DEFAULT_SHIM, usage_scripted(two_turns(50, 50), wire_caps=mismatched_wire),
                                  DUMMY_CONFIG, "test:budget_wire_mismatch", "scripted", 4000, 0, 100, True)
    if row_mismatch["budget_accounting"] != "INVALID/wire_cap_mismatch":
        problems.append(f"scenario 3 (wire mismatch): budget_accounting {row_mismatch['budget_accounting']!r}, "
                        f"per_turn {row_mismatch.get('per_turn')}")
    if row_mismatch.get("wire_caps") != mismatched_wire:
        problems.append(f"row['wire_caps'] did not round-trip the client's own wire_caps: "
                        f"{row_mismatch.get('wire_caps')!r} vs {mismatched_wire!r}")

    return check("VALID, completion_exceeds_cap and wire_cap_mismatch, each witnessed end to end through "
                 "one_rollout with a scripted client under a real, enabled episode-output ceiling",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 6. arm_table.py's three quantities (Codex T47 §9): correct-delivery rate,
#    conditional cost, effective cost per correct delivery
# --------------------------------------------------------------------------

def _row(model="m", selector="train:1", arm="A", *, budget_accounting="VALID", artifact="BOUND",
        reward=1.0, complete=True, total_tokens=1000, completion_tokens=200, turns=5,
        stop="piv_submitted", submitted=True, quarantined=False, status=None, provider="mistral",
        replicate=1, error=None, tool_call_chars=0, **extra) -> dict:
    """A COMPLETE hand-built row — everything `measure_budget.validate_row`
    re-derives from an archive — so it validates as plain `"VALID"` rather
    than `"VALID/derived"`, and a test that wants a DERIVED row has to say
    so by dropping fields explicitly (`_old_row` below).

    Every field here exists because the validator checks it: exact wire
    cardinality (`wire_caps` one per turn), attempt identity (`attempts`,
    `requests`, `rollout_id`), integer usage that sums to the reported
    total, the episode ceiling, and artifact/digest consistency.
    """
    if quarantined:
        return {"provider": provider, "model": model, "selector": selector, "arm": arm, "replicate": replicate,
               "quarantined": True, "status": status, "reasons": {}, "seconds": 1.0,
               "episode_contract_digest": "ep", "replay_contract_digest": "rp", **extra}
    row = {
        "provider": provider, "model": model, "selector": selector, "arm": arm, "replicate": replicate,
        "budget_accounting": budget_accounting, "artifact": artifact, "reward": reward,
        "breakdown": {"complete": complete} if artifact == "BOUND" else None,
        "total_tokens": total_tokens, "completion_tokens": completion_tokens, "turns": turns,
        "stop": stop, "submitted": submitted, "error": error, "seconds": 1.0,
        "max_total_completion_tokens": 40_000, "rollout_id": "r1", "attempts": 1,
        "episode_contract_digest": "ep", "replay_contract_digest": "rp",
        "per_turn": [{"request_max_tokens": completion_tokens, "input_tokens": 10,
                     "output_tokens": completion_tokens, "assistant_content_chars": 0,
                     "assistant_reasoning_chars": 0, "tool_call_chars": tool_call_chars}],
        "wire_caps": [{"max_tokens": completion_tokens}],
        "requests": [{"turn": 1, "attempt": 1, "status": "ok", "seconds": 1.0,
                     "attempt_id": "a1", "rollout_id": "r1"}],
    }
    if artifact == "BOUND":
        row["artifact_reason"] = None
        row["artifact_stored_bytes_digest"] = "sd"
        row["artifact_logical_text_digest"] = "ld"
    else:
        row["artifact_reason"] = "no_write"
    row.update(extra)
    return row


def _old_row(**kwargs) -> dict:
    """The same row as written by an instrument that predates the corrected
    capture: no `budget_accounting`, no `wire_caps`, no `attempts`, no
    `requests`, no per-turn `tool_call_chars`. `validate_row` must call it
    `VALID/derived` — admissible in a `--pilot` table and nowhere else."""
    row = _row(**kwargs)
    for field in ("budget_accounting", "wire_caps", "attempts", "requests",
                  "episode_contract_digest", "replay_contract_digest"):
        row.pop(field, None)
    for turn in row["per_turn"]:
        turn.pop("tool_call_chars", None)
    return row


def _window(*, billed=0, billed_mine=0, accepted=0, accepted_mine=0,
            rejected_estimate=0, rejected_estimate_mine=0,
            rejected_requests=0, rejected_requests_mine=0,
            current=None, kind=None, **extra) -> dict:
    """A provider-window snapshot in the SEPARATED shape Codex T50 §3
    requires: `billed_*` is the provider's own number for requests it SERVED,
    `rejected_estimate_*` is a chars/4 estimate for attempts it refused, and
    `current_request_estimate_tokens` is the request being refused right now.
    They are never added together into a single "consumed" figure — that
    conflation is what let repeated backoffs manufacture a saturated window."""
    window = {"window_kind": kind or AT.WINDOW_KIND_PRE_REQUEST,
              "admission_semantics": AT.ADMISSION_SEMANTICS,
              "billed_tokens_total": billed, "billed_tokens_this_cell": billed_mine,
              "rejected_estimate_tokens_total": rejected_estimate,
              "rejected_estimate_tokens_this_cell": rejected_estimate_mine,
              "accepted_requests_total": accepted, "accepted_requests_this_cell": accepted_mine,
              "rejected_requests_total": rejected_requests,
              "rejected_requests_this_cell": rejected_requests_mine,
              "current_request_present": current is not None,
              "current_request_estimate_tokens": current}
    window.update(extra)
    return window


def test_correct_delivery_predicate():
    """`arm_table.correct_delivery` is exactly the conjunction of three
    things — BOUND artifact, reward 1.0, scorer's own `complete` flag —
    checked one at a time so a future change to any single conjunct's
    wiring is caught here rather than only in an aggregate rate."""
    problems = []
    base = _row()
    if not AT.correct_delivery(base):
        problems.append("a BOUND, reward==1.0, complete==True row is not a correct delivery")
    if AT.correct_delivery(_row(artifact="NO_ARTIFACT")):
        problems.append("a non-BOUND artifact still counted as a correct delivery")
    if AT.correct_delivery(_row(reward=0.7)):
        problems.append("reward != 1.0 still counted as a correct delivery")
    if AT.correct_delivery(_row(complete=False)):
        problems.append("breakdown.complete == False still counted as a correct delivery")
    if AT.correct_delivery({"model": "m", "artifact": "BOUND", "reward": 1.0, "breakdown": None}):
        problems.append("a missing breakdown dict still counted as a correct delivery")
    return check("correct_delivery is the exact conjunction of artifact==BOUND, reward==1.0 and "
                 "breakdown['complete'] is True — no more, no less", not problems, "\n".join(problems))


def test_arm_table_three_quantities_survivorship_example():
    """Codex T47 §9's own worked example, pinned exactly: one correct
    delivery at 40,000 total tokens, and nine failures at 39,000 total
    tokens each (all VALID, non-correct attempts in the same stratum).

      - conditional cost (median/p75 among CORRECT deliveries only): 40,000
        — the number that made the old delivered-only metric look cheap.
        `n == 1`, so the TABLE would render "—" (diagnostic witness) even
        though the raw statistic is exactly 40,000.
      - effective cost per correct delivery: `(40000 + 9*39000) / 1 ==
        391000` — what it actually cost to land the one correct delivery,
        the quantity Q10's economic decision is supposed to use.
    """
    rows = [_row(total_tokens=40_000, completion_tokens=8_000, reward=1.0, complete=True, submitted=True,
                stop="piv_submitted")]
    rows += [_row(total_tokens=39_000, completion_tokens=8_000, reward=0.0, artifact="NO_ARTIFACT", complete=False,
                  submitted=False, stop="piv_turn_cap_no_submit") for _ in range(9)]

    problems = []
    cost = AT.conditional_cost_stats(rows)
    if cost != {"n": 1, "median": 40_000, "p75": 40_000}:
        problems.append(f"conditional_cost_stats: {cost}, expected n=1 median=40000 p75=40000")
    effective = AT.effective_cost(rows)
    if effective != 391_000:
        problems.append(f"effective_cost: {effective}, expected 391000")
    if AT.format_cost_cell(cost) != "— (n=1, diagnostic witness)":
        problems.append(f"format_cost_cell should show '—' for n<3, got {AT.format_cost_cell(cost)!r}")

    stratum = AT.build_stratum(rows, [], pilot=False, schedule_complete=False)
    if stratum["n"] != 10 or stratum["n_correct"] != 1:
        problems.append(f"build_stratum n/n_correct: {stratum['n']}/{stratum['n_correct']}, expected 10/1")
    if stratum["conditional_rate"] != 0.1:
        problems.append(f"conditional_rate: {stratum['conditional_rate']}, expected 0.1")
    # The SECOND estimand needs the schedule. Without one it is `None` —
    # deliberately not approximated from the rows that happen to exist.
    if stratum["operational_denominator"] is not None:
        problems.append("with no schedule the operational denominator must be None, not guessed")
    scheduled = [{"provider": "mistral", "model": "m", "selector": "train:1", "arm": "A",
                 "replicate": 1, "block_id": "b", "arm_position": 0, "planned_ordinal": 1} for _ in range(12)]
    with_schedule = AT.build_stratum(rows, scheduled, pilot=False, schedule_complete=True)
    # 12 scheduled, 10 ran, 2 unrun; the schedule is DECLARED COMPLETE, so
    # the unrun cells are non-deliveries: 1/12, not 1/10.
    if with_schedule["operational_denominator"] != 12 or with_schedule["n_unrun"] != 2:
        problems.append(f"operational denominator {with_schedule['operational_denominator']} / unrun "
                        f"{with_schedule['n_unrun']}, expected 12 / 2")
    incomplete = AT.build_stratum(rows, scheduled, pilot=False, schedule_complete=False)
    if incomplete["operational_denominator"] != 10:
        problems.append(f"an UNDECLARED schedule must leave unrun cells out of the denominator, got "
                        f"{incomplete['operational_denominator']}, expected 10")

    return check("the survivorship example (Codex T47 §9): conditional cost 40K, effective cost 391K per correct "
                 "delivery — the SAME ten attempts read two different, both-correct ways",
                 not problems, "\n".join(problems))


def test_effective_cost_is_inf_with_zero_correct_deliveries():
    """No correct deliveries in the stratum at all: `effective_cost_per_
    correct_delivery` is `float("inf")`, never a `ZeroDivisionError` and
    never silently `0` (which would look like a FREE arm rather than an
    arm that never once delivered correctly)."""
    rows = [_row(reward=0.0, artifact="NO_ARTIFACT", complete=False, submitted=False, total_tokens=20_000)
           for _ in range(5)]
    problems = []
    effective = AT.effective_cost(rows)
    if effective != float("inf"):
        problems.append(f"effective_cost: {effective}, expected inf")
    if AT.format_cost(effective) != "inf (dominated)":
        problems.append(f"a zero-correct arm must render as dominated, got {AT.format_cost(effective)!r}")
    cost = AT.conditional_cost_stats(rows)
    if cost != {"n": 0, "median": None, "p75": None}:
        problems.append(f"conditional_cost_stats over zero correct deliveries: {cost}")
    return check("zero correct deliveries -> effective cost is inf, conditional cost stats are n=0/None/None",
                 not problems, "\n".join(problems))


def test_stratum_excludes_quarantined_and_invalid_from_n_and_cost():
    """Provider-failed (quarantined) and budget_accounting-invalid rows are
    both counted separately and EXCLUDED from `n`, from the correct-
    delivery rate's denominator, and from cost — never silently pulled into
    an equal-budget comparison."""
    rows = [
        _row(total_tokens=1000, reward=1.0, complete=True),                       # 1 valid, correct
        _row(budget_accounting="INVALID/no_request_caps", total_tokens=999999),   # excluded: invalid accounting
        _row(quarantined=True, status="PIVEvaluationBatchInvalidReason.OTHER"),   # excluded: provider-failed
    ]
    stratum = AT.build_stratum(rows, [], pilot=False, schedule_complete=False)
    problems = []
    if stratum["n"] != 1:
        problems.append(f"n: {stratum['n']}, expected 1 (only the VALID, non-quarantined row)")
    if stratum["n_provider_failed"] != 1:
        problems.append(f"n_provider_failed: {stratum['n_provider_failed']}, expected 1")
    if stratum["n_invalid"] != 1:
        problems.append(f"n_invalid: {stratum['n_invalid']}, expected 1 — the quarantined row belongs to "
                        "n_provider_failed and must not be counted twice")
    if stratum["effective_cost_conditional"] != 1000:
        problems.append(f"effective_cost_conditional: {stratum['effective_cost_conditional']}, expected 1000 — "
                        "computed over the single VALID row's total_tokens only, never the 999999 from the "
                        "invalid-accounting row")
    # The invalid row IS classified: instrument_invalid, so it stays in the
    # operational denominator (its delivery outcome is independently known)
    # while contributing nothing to the conditional cost.
    if stratum["failure_buckets"].get("instrument_invalid") != 1:
        problems.append(f"failure buckets {dict(stratum['failure_buckets'])}, expected one instrument_invalid")
    return check("quarantined and budget_accounting-invalid rows are excluded from n/cost and counted "
                 "separately, named, never silently folded into the equal-budget table",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 7. adversarial-review follow-up: attempt boundaries, summary gating,
#    old-instrument derivation, Williams-design balance
# --------------------------------------------------------------------------

def test_attempt_boundary_detection_and_billed_totals_all_attempts():
    """`PacedClient` (finding 1) detects a framework-level rollout retry —
    `Environment.run_rollout` calling `run_rollout_attempt()` again with a
    FRESH state while the SAME client instance keeps being reused — as a
    request whose prompt is back down to "system + user only" (<= 2
    messages) after a STRICTLY LONGER one. Simulated here with three direct
    `get_native_response` calls (no network — the same
    `post_chat_completion_with_routed_experts_sidecar` substitution
    technique the wire-cap witnesses above use) shaped as: segment 1 turn 1
    (2 messages), segment 1 turn 2 (4 messages), segment 2 turn 1 (2
    messages again — the reset). Proves `attempts == 2`, `wire_caps` keeps
    ALL THREE calls, `last_segment_wire_caps` keeps ONLY the third
    (surviving) one, and the billed-token totals sum across EVERY call,
    including the discarded first segment's."""
    import verifiers.legacy.clients.openai_chat_completions_client as oai_mod

    class _FakeUsage:
        def __init__(self, prompt_tokens, completion_tokens):
            self.prompt_tokens = prompt_tokens
            self.completion_tokens = completion_tokens

    class _FakeResponse:
        def __init__(self, prompt_tokens, completion_tokens):
            self.usage = _FakeUsage(prompt_tokens, completion_tokens)
            self.model = "scripted-model"

    call_usages = iter([(100, 50), (150, 60), (90, 40)])

    async def fake_post(client, path, *, body, extra_headers=None):
        p, c = next(call_usages)
        return _FakeResponse(p, c)

    client_cls = mb.make_client_cls(0.0, True)
    client = client_cls(DUMMY_CONFIG)

    two_messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    four_messages = two_messages + [{"role": "assistant", "content": "a"}, {"role": "tool", "content": "t"}]

    original_post = oai_mod.post_chat_completion_with_routed_experts_sidecar
    oai_mod.post_chat_completion_with_routed_experts_sidecar = fake_post
    try:
        asyncio.run(client.get_native_response(two_messages, "m", {"max_tokens": 100}, None))
        asyncio.run(client.get_native_response(four_messages, "m", {"max_tokens": 100}, None))
        asyncio.run(client.get_native_response(two_messages, "m", {"max_tokens": 100}, None))
    finally:
        oai_mod.post_chat_completion_with_routed_experts_sidecar = original_post

    problems = []
    if client.attempts != 2:
        problems.append(f"attempts: {client.attempts}, expected 2")
    if len(client.wire_caps) != 3:
        problems.append(f"wire_caps length: {len(client.wire_caps)}, expected 3 (every attempt)")
    if len(client.last_segment_wire_caps) != 1:
        problems.append(f"last_segment_wire_caps length: {len(client.last_segment_wire_caps)}, expected 1 "
                        "(only the surviving segment's own call)")
    if client.billed_input_tokens_all_attempts != 100 + 150 + 90:
        problems.append(f"billed_input_tokens_all_attempts: {client.billed_input_tokens_all_attempts}, "
                        "expected 340 (every attempt's own prompt_tokens, including the discarded first segment)")
    if client.billed_output_tokens_all_attempts != 50 + 60 + 40:
        problems.append(f"billed_output_tokens_all_attempts: {client.billed_output_tokens_all_attempts}, "
                        "expected 150")

    return check("PacedClient detects a framework attempt boundary (prompt back to system+user only after a "
                 "longer one), counts every attempt, aligns last_segment_wire_caps to only the surviving one, "
                 "and sums billed tokens across EVERY attempt including discarded ones",
                 not problems, "\n".join(problems))


def test_framework_retry_row_end_to_end_via_client_attempts_property():
    """`one_rollout` reads `attempts` off the client via `getattr` and feeds
    it to `compute_budget_accounting`: a scripted client claiming
    `attempts > 1` (as `PacedClient` would after a real framework retry)
    produces `INVALID/framework_retry` on the row, end to end, even though
    every other check on that row's own per-turn data would otherwise pass."""
    class _RetriedUsageScript(UsageScript):
        attempts = 2

    def factory(config):
        return _RetriedUsageScript([
            (tec.write(), Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=50, total_tokens=60)),
            (tec.submit(), Usage(prompt_tokens=20, reasoning_tokens=0, completion_tokens=50, total_tokens=70)),
        ])
    row = mb.one_rollout(DEFAULT_SHIM, factory, DUMMY_CONFIG, "test:framework_retry", "scripted", 4000, 0, 100, True)
    ok = check("a client reporting attempts > 1 produces INVALID/framework_retry on the row end to end",
              row["budget_accounting"] == "INVALID/framework_retry",
              f"budget_accounting {row['budget_accounting']!r}")
    return ok


def test_partition_rows_for_summary_gates_on_budget_accounting():
    """`partition_rows_for_summary` (finding 2): every printed/`.md`
    summary statistic must be computed over rows whose `budget_accounting`
    is `"VALID"` AND that are not quarantined — never merely "not
    quarantined", which the summary used to filter on alone."""
    rows = [
        {"quarantined": True, "status": "PIVEvaluationBatchInvalidReason.OTHER"},
        {"budget_accounting": "INVALID/no_request_caps", "total_tokens": 999999},
        {"budget_accounting": "VALID", "total_tokens": 1000},
        {"budget_accounting": "VALID", "total_tokens": 2000},
    ]
    valid_scored, quarantined, budget_invalid = mb.partition_rows_for_summary(rows)
    problems = []
    if {r["total_tokens"] for r in valid_scored} != {1000, 2000}:
        problems.append(f"valid_scored total_tokens: {[r.get('total_tokens') for r in valid_scored]}, "
                        "expected {1000, 2000}")
    if len(quarantined) != 1:
        problems.append(f"quarantined: {len(quarantined)}, expected 1")
    if len(budget_invalid) != 1 or budget_invalid[0]["budget_accounting"] != "INVALID/no_request_caps":
        problems.append(f"budget_invalid: {budget_invalid}")
    if len(valid_scored) + len(quarantined) + len(budget_invalid) != len(rows):
        problems.append("partition does not account for every row exactly once")
    return check("partition_rows_for_summary excludes quarantined and budget_accounting-invalid rows from the "
                 "valid/scored bucket every printed and .md summary statistic is computed over",
                 not problems, "\n".join(problems))


def test_arm_table_derives_budget_accounting_for_old_instrument_rows():
    """A row with NO `budget_accounting` field at all (an old-instrument
    row — adversarial-review finding 3, e.g. the archived `Ap_train1`/
    `B1p_train1` rows) gets a best-effort `"VALID/derived"` (or the
    matching `INVALID/<code>`) from its OWN `per_turn`, is counted in `n`
    (never silently reported as n=0 for the whole set), and is flagged via
    `is_derived`/`n_derived`. `complete` stays UNKNOWN on such a row
    (`breakdown` has no `"complete"` key at all), so it is never counted as
    a correct delivery even when everything else about it looks correct —
    `correct_delivery` already treats a missing key the same as `False`, no
    special-casing needed."""
    good_old_row = _old_row()
    good_old_row["breakdown"] = {"total": 1.0}          # no "complete" key: an old instrument never recorded it
    bad_old_row = _old_row()
    bad_old_row["per_turn"] = [{"request_max_tokens": None, "input_tokens": 10, "output_tokens": 200}]
    problems = []
    status, reasons = mb.validate_row(good_old_row)
    if status != "VALID/derived":
        problems.append(f"good old row validated as {status!r} ({reasons})")
    if set(reasons) != {"no_recorded_status", "no_wire_caps", "no_attempts", "no_requests", "no_tool_call_chars"}:
        problems.append(f"the derivation GAPS must be named, got {reasons}")
    if any(gap not in mb.ROW_DERIVATION_GAPS for gap in reasons):
        problems.append(f"a gap outside the closed set leaked out: {reasons}")
    bad_status, bad_reasons = mb.validate_row(bad_old_row)
    if bad_status != "INVALID" or "no_request_caps" not in bad_reasons:
        problems.append(f"bad old row validated as {bad_status!r} ({bad_reasons})")
    if AT.derive_budget_accounting(good_old_row) != "VALID/derived":
        problems.append(f"derive_budget_accounting: {AT.derive_budget_accounting(good_old_row)!r}")
    if AT.correct_delivery(good_old_row):
        problems.append("an old row with no breakdown['complete'] key must not count as a correct delivery")
    # The whole point of the split: a derived row is admitted by a --pilot
    # table and REFUSED by a confirmatory one.
    pilot = AT.build_stratum([good_old_row], [], pilot=True, schedule_complete=False)
    confirmatory = AT.build_stratum([good_old_row], [], pilot=False, schedule_complete=False)
    if pilot["n"] != 1 or pilot["n_derived"] != 1:
        problems.append(f"pilot stratum n/n_derived: {pilot['n']}/{pilot['n_derived']}, expected 1/1")
    if confirmatory["n"] != 0:
        problems.append(f"a confirmatory stratum must REFUSE a VALID/derived row, got n={confirmatory['n']}")
    return check("an old-instrument row is VALID/derived with its gaps NAMED, is admitted only by a --pilot "
                 "table, and is refused by a confirmatory one",
                 not problems, "\n".join(problems))


def test_redact_secrets_blanks_live_key_shaped_strings():
    """`redact_secrets` (finding 7): `run_arms.py` writes a failed
    subprocess's stdout/stderr tail into a repo-tracked log file — a key
    echoed into a traceback must never land there literally."""
    problems = []
    samples = {
        "nvapi-abcdEFGH12345678": "nvidia",
        "gsk_1234567890abcdefGHIJ": "groq",
        "sk-abcdefghijklmnop1234": "openai-shaped",
        "AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz1234": "google/gemini",
    }
    for key, label in samples.items():
        text = f"request failed with Authorization: Bearer {key} (401)"
        redacted = mb.redact_secrets(text)
        if key in redacted:
            problems.append(f"{label} key still present after redaction: {redacted!r}")
        if "REDACTED" not in redacted:
            problems.append(f"{label}: no redaction marker in output: {redacted!r}")
    if mb.redact_secrets("") != "":
        problems.append("redact_secrets should pass an empty string through unchanged")
    if mb.redact_secrets(None) is not None:
        problems.append("redact_secrets should pass None through unchanged, never raise")
    plain = "ordinary traceback line with no secret in it"
    if mb.redact_secrets(plain) != plain:
        problems.append("redact_secrets must not alter text that contains no key-shaped substring")
    return check("redact_secrets blanks every common live-key prefix before text reaches a repo log",
                 not problems, "\n".join(problems))


ROSTER = [{"provider": "mistral", "model": m} for m in
          ("devstral-2512", "ministral-14b-2512", "ministral-8b-2512", "mistral-medium-2508")]
SELECTORS_6 = ["train:1", "train:12", "train:30", "eval:5", "train:3:hard", "train:107:hard"]
SAMPLING = {"temperature": 0.0, "top_p": 1.0, "seed": None}


def _schedule(selectors=None, replicates=2, label="t"):
    return SA.build_schedule(label, ROSTER, selectors or SELECTORS_6, ["A", "B1", "B2"], replicates,
                             "2026-08-30", SAMPLING, 40_000, 600.0, 0, 6.0)


def test_schedule_balance_is_exact_within_provider_model_and_claimed_no_higher():
    """Six selectors is one complete Williams cycle per (provider, model,
    replicate): every arm occupies every position exactly equally often AND
    every ordered adjacent pair of distinct arms occurs exactly equally
    often — including a REVERSE step like B1->A, which a bare cyclic Latin
    square never produces, leaving carry-over unbalanced.

    The claim is verified from the DEALT cells, not from the construction,
    and is never made at a level it does not hold: a single selector's own
    blocks each run exactly ONE of the six sequences, so no order claim is
    made within a selector."""
    problems = []
    schedule = _schedule()
    balance = schedule["balance"]
    for flag in ("position_balance_within_provider_model_replicate",
                 "adjacency_balance_within_provider_model_replicate",
                 "position_balance_within_provider_model", "adjacency_balance_within_provider_model"):
        if balance[flag] is not True:
            problems.append(f"{flag} should hold for 6 selectors, got {balance[flag]}")
    if balance["balance_within_selector"] is not False:
        problems.append("no balance may be claimed WITHIN a selector")
    per_layer = SA.census(schedule["cells"], ("provider", "model", "replicate"))
    for key, stats in per_layer.items():
        if set(stats["position_counts"].values()) != {2}:
            problems.append(f"{key}: position counts {dict(stats['position_counts'])}, expected all 2")
        if set(stats["pair_counts"].values()) != {2}:
            problems.append(f"{key}: adjacent-pair counts {dict(stats['pair_counts'])}, expected all 2")
        if ("B1", "A") not in stats["pair_counts"]:
            problems.append(f"{key}: no B1->A step — still forward rotations only, not a Williams design")

    # THREE selectors: position balance survives, adjacency does NOT, and
    # the schedule says exactly that instead of claiming a Williams cycle.
    three = _schedule(selectors=["train:1", "train:12", "train:30"], label="t3")
    if three["balance"]["position_balance_within_provider_model_replicate"] is not True:
        problems.append("3 selectors should still be position-balanced (a whole Latin square per layer)")
    if three["balance"]["adjacency_balance_within_provider_model_replicate"] is not False:
        problems.append("3 selectors must NOT claim adjacency balance")
    if "does NOT" not in three["balance"]["statement"]:
        problems.append(f"the 3-selector statement must say what fails: {three['balance']['statement']!r}")

    # FOUR selectors: neither.
    four = _schedule(selectors=SELECTORS_6[:4], label="t4")
    if four["balance"]["position_balance_within_provider_model_replicate"] is not False:
        problems.append("4 selectors must not claim position balance")
    if "NEITHER" not in four["balance"]["statement"]:
        problems.append(f"the 4-selector statement must claim neither: {four['balance']['statement']!r}")
    return check("the schedule's balance claim is exact within (provider, model, replicate) for a complete "
                 "Williams cycle, weakens honestly to position-only for 3 selectors and to nothing for 4, "
                 "and is never claimed within a selector", not problems, "\n".join(problems))


def test_schedule_ordinals_do_not_depend_on_the_replicate_count():
    """The defect Codex T48a §2 named: `build_blocks` indexed blocks by
    looping `selector -> replicate 1..N -> model`, so the index a cell
    received DEPENDED ON THE MAXIMUM N passed today — staged
    `--replicate 1`, then `2`, then `3` silently produced a different design
    from one `--replicate 3` invocation while "skipping existing cells"
    looked like an orderly resumption.

    Replicate-major indexing over a FIXED roster fixes it: every replicate-1
    cell keeps its planned ordinal, block index, permutation and arm
    position no matter how many replicates the schedule was cut for."""
    problems = []
    def fingerprint(schedule, replicate):
        return {(c["provider"], c["model"], c["selector"], c["arm"]):
                (c["planned_ordinal"], c["block_index"], c["permutation_index"], c["arm_position"])
                for c in schedule["cells"] if c["replicate"] == replicate}
    one = _schedule(replicates=1, label="r1")
    three = _schedule(replicates=3, label="r3")
    if fingerprint(one, 1) != fingerprint(three, 1):
        problems.append("replicate 1's ordinals/blocks/permutations changed when the schedule was cut for 3 "
                        "replicates instead of 1 — the old staged-replication defect")
    if len(three["cells"]) != 3 * len(one["cells"]):
        problems.append(f"cell count: {len(three['cells'])} vs 3×{len(one['cells'])}")
    # Every block's three arms are consecutive in the planned order.
    for _, (cell, order) in SA.block_sequences(three["cells"]).items():
        ordinals = sorted(c["planned_ordinal"] for c in three["cells"] if c["block_id"] == cell["block_id"])
        if ordinals != list(range(ordinals[0], ordinals[0] + len(order))):
            problems.append(f"block {cell['block_id']} is not contiguous in the planned order: {ordinals}")
    return check("planned ordinals are replicate-major over a fixed roster, so a replicate-1 cell's position "
                 "never depends on how many replicates were requested, and each block's arms run consecutively",
                 not problems, "\n".join(problems))


def test_schedule_id_is_content_bound_and_an_edited_schedule_is_refused(tmp=None):
    """`schedule_id` is the sha256 of the canonical content (everything but
    `created_at` and the id itself). Editing a cell after the fact and
    loading the file must FAIL — an immutable schedule that can be quietly
    patched is not immutable."""
    import tempfile
    problems = []
    schedule = _schedule()
    if SA.schedule_digest(schedule) != schedule["schedule_id"]:
        problems.append("a freshly built schedule does not hash to its own id")
    # `created_at` is excluded, so two schedules of the SAME design agree.
    again = _schedule()
    if again["schedule_id"] != schedule["schedule_id"]:
        problems.append("the same design produced two different schedule ids")
    if _schedule(replicates=3, label="t")["schedule_id"] == schedule["schedule_id"]:
        problems.append("a different replicate count must produce a different schedule id")
    if _schedule(label="other")["schedule_id"] == schedule["schedule_id"]:
        problems.append("a different label must produce a different schedule id (it names the output files)")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "schedule_t.json"
        path.write_text(json.dumps(schedule), encoding="utf-8")
        if SA.load_schedule(path)["schedule_id"] != schedule["schedule_id"]:
            problems.append("a clean schedule failed to load")
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["cells"][0]["arm"] = "B2"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        try:
            SA.load_schedule(path)
            problems.append("an EDITED schedule was accepted")
        except SystemExit:
            pass
    return check("schedule_id binds the content, the same design reproduces the same id, and an edited "
                 "schedule file is refused on load", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 4. the refactor is what the spec asked for: a stable factory/signature
# --------------------------------------------------------------------------

def test_arms_and_signature_are_stable():
    """`--arm` presets (Codex T46 §5/§6) and `one_rollout`'s signature,
    pinned so a refactor that quietly drops the fake-client injection seam
    fails here rather than only showing up as an untestable live script."""
    import inspect
    problems = []
    if mb.ARM_PRESETS != {"A": (8000, True), "B1": (16000, True), "B2": (8000, False), "B3": (16000, False)}:
        problems.append(f"ARM_PRESETS moved: {mb.ARM_PRESETS}")
    params = list(inspect.signature(mb.one_rollout).parameters)
    expected = ["env_mod", "client_cls", "config", "selector", "model", "max_tokens", "retries",
               "max_total_completion_tokens", "reasoning_replay", "archive", "arm",
               "temperature", "top_p", "seed", "replicate", "prompt_schema_digest",
               "schedule_id", "planned_ordinal", "actual_ordinal", "session_id", "block_id",
               "permutation_index", "arm_position", "window_ledger"]
    if params != expected:
        problems.append(f"one_rollout signature: {params}")
    # The schedule owns replicates and arm order now (Codex T48a §2): the
    # flags that used to let a caller invent a design on the fly are gone.
    run_arms_flags = Path(RA.__file__).read_text(encoding="utf-8")
    for gone in ('add_argument("--replicate"', 'add_argument("--order-seed"'):
        if gone in run_arms_flags:
            problems.append(f"run_arms.py still offers {gone} — the schedule file owns the design now")
    if 'add_argument("--schedule"' not in run_arms_flags:
        problems.append("run_arms.py must take --schedule")
    if not callable(mb.make_client_cls(0.0, True)):
        problems.append("make_client_cls does not return a callable class")
    if mb.make_client_cls(0.0, True) is mb.make_client_cls(0.0, True):
        problems.append("make_client_cls returns the SAME class object on every call; it must be a fresh "
                        "closure per (min_interval, reasoning_replay) so two arms cannot share pacing state")
    return check("ARM_PRESETS and one_rollout's signature are pinned; make_client_cls is a fresh factory",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 8. Codex Turn 48: tool-call arguments, exact wire cardinality, the one row
#    validator, replay-contract identity, failure classification
# --------------------------------------------------------------------------

def test_tool_call_arguments_enter_the_plausibility_floor():
    """Codex T48a §3.1's own example, end to end: a tool-only turn carrying
    a 48,000-character `write_ledger` argument and reporting ONE completion
    token.

    Before, `_response_chars` counted `content + reasoning_content` only, so
    the denominator was ZERO on a tool-only turn and no completion count,
    however absurd, could fail. Now the canonical serialized tool call is
    counted — and, per Codex T48b §3, it lands on the SUSPICIOUS flag rather
    than on INVALID, because a characters-per-token heuristic can fire
    differently across replay arms and must not decide a confirmatory
    denominator."""
    problems = []
    huge = "x" * 48_000
    message = AssistantMessage(role="assistant", content=None,
                               tool_calls=[ToolCall(id="c1", name="write_ledger",
                                                    arguments=json.dumps({"content": huge}))])
    chars = mb.tool_call_chars(message)
    if chars < 48_000:
        problems.append(f"tool_call_chars {chars} does not even reach the 48,000-character argument")
    if mb.tool_call_chars(AssistantMessage(role="assistant", content="hi")) != 0:
        problems.append("a message with NO tool calls must measure 0, not len('[]')")

    turn = {"input_tokens": 10, "output_tokens": 1, "request_max_tokens": 8000,
            "assistant_content_chars": 0, "assistant_reasoning_chars": 0, "tool_call_chars": chars}
    status = mb.compute_budget_accounting([8000], [turn], None, None, 1, 40_000, 1)
    if status != "VALID":
        problems.append(f"the heuristic must not INVALIDATE the row: {status}")
    suspicion = mb.compute_budget_suspicion([turn])
    if suspicion != "usage_implausible":
        problems.append(f"48,000 characters at 1 completion token must be SUSPICIOUS, got {suspicion!r}")
    # Without the tool-call term the same turn looks perfectly ordinary --
    # which is exactly the hole.
    blind = dict(turn, tool_call_chars=0)
    if mb.compute_budget_suspicion([blind]) is not None:
        problems.append("the pre-T48 denominator (content+reasoning only) should NOT flag this turn — if it "
                        "does, this witness is no longer demonstrating the hole it was written for")
    if mb.compute_budget_suspicion([dict(turn, output_tokens=12_000)]) is not None:
        problems.append("a plausible ratio (48K characters at 12K completion tokens) must not be flagged")
    for code in mb.ALL_BUDGET_SUSPICION_CODES:
        if code.startswith("env_") and code != "env_unrecognized":
            got = mb.compute_budget_suspicion([], code[len("env_"):])
            if got != code:
                problems.append(f"env suspicion code {code} came back as {got!r}")
    if mb.compute_budget_suspicion([], "a_code_from_the_future") != "env_unrecognized":
        problems.append("an unknown env suspicion code must fall back to env_unrecognized, never interpolate")
    return check("tool-call arguments enter the plausibility denominator, a 48,000-character write at one "
                 "completion token is SUSPICIOUS (not INVALID), and the same turn is invisible without the "
                 "tool-call term", not problems, "\n".join(problems))


def test_surplus_wire_request_is_invalid_end_to_end():
    """Codex T48a §3.2, through `one_rollout`: a client that made ONE more
    provider request than the trajectory has turns. The old code compared
    only the first `len(per_turn)` entries and returned VALID, so a
    client/SDK retry could bill a request no layer above it ever saw."""
    problems = []

    def two_turns():
        return [(tec.write(), Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=50, total_tokens=60)),
                (tec.submit(), Usage(prompt_tokens=20, reasoning_tokens=0, completion_tokens=50, total_tokens=70))]

    exact = [{"max_completion_tokens": 100}, {"max_completion_tokens": 50}]
    row_ok = mb.one_rollout(DEFAULT_SHIM, usage_scripted(two_turns(), wire_caps=list(exact)), DUMMY_CONFIG,
                            "test:wire_exact", "scripted", 4000, 0, 100, True)
    if row_ok["budget_accounting"] != "VALID":
        problems.append(f"exact cardinality should be VALID, got {row_ok['budget_accounting']!r}")
    surplus = exact + [{"max_completion_tokens": 50}]
    row_surplus = mb.one_rollout(DEFAULT_SHIM, usage_scripted(two_turns(), wire_caps=surplus), DUMMY_CONFIG,
                                 "test:wire_surplus", "scripted", 4000, 0, 100, True)
    if row_surplus["budget_accounting"] != "INVALID/extra_wire_request":
        problems.append(f"one surplus wire request should be INVALID/extra_wire_request, got "
                        f"{row_surplus['budget_accounting']!r}")
    if row_surplus["row_validation"]["status"] != "INVALID":
        problems.append(f"the row validator must agree: {row_surplus['row_validation']}")
    # And the SDK's own retries are off, so the surplus cannot come from a
    # layer this instrument does not see.
    if mb.SDK_MAX_RETRIES != 0:
        problems.append(f"SDK_MAX_RETRIES is {mb.SDK_MAX_RETRIES}, must be 0")
    config = mb.client_config("PIV_TEST_NO_SUCH_KEY_VAR", "https://example.invalid/v1", 30.0)
    if config.max_retries != 0:
        problems.append(f"ClientConfig.max_retries is {config.max_retries}; the library default is 10 and "
                        "setup_openai_client passes it straight into AsyncOpenAI, below get_native_response")
    from verifiers.legacy.types import ClientConfig as _CC
    if _CC(client_type="openai_chat_completions", api_key_var="X", api_base_url="https://x.invalid/v1"
           ).max_retries == 0:
        problems.append("the library default is no longer 10 — this witness has stopped demonstrating "
                        "anything; re-read setup_openai_client")
    return check("exact wire cardinality is required end to end (one surplus request is INVALID) and the SDK's "
                 "own retry layer is disabled", not problems, "\n".join(problems))


def test_validate_row_rederives_every_predicate_from_literal_adversarial_rows():
    """ONE pure archived-row validator (Codex T48a §3.3/Q5). Each row below
    CLAIMS `budget_accounting == "VALID"` and carries exactly one
    present-but-impossible fact; the validator must refuse each on its own
    re-derivation, never on the claim."""
    problems = []

    def expect(label, row, want_status, want_reason=None):
        status, reasons = mb.validate_row(row)
        if status != want_status or (want_reason is not None and want_reason not in reasons):
            problems.append(f"{label}: got {status} {reasons}, wanted {want_status} containing {want_reason}")

    expect("a complete, honest row", _row(), "VALID")
    expect("a claim of VALID over no turns at all",
           _row(**{"per_turn": [], "wire_caps": [], "requests": []}), "INVALID", "no_turns")
    bad_cap = _row()
    bad_cap["per_turn"][0]["request_max_tokens"] = None
    expect("a turn with no cap", bad_cap, "INVALID", "no_request_caps")
    over_cap = _row()
    over_cap["per_turn"][0]["output_tokens"] = 9_999
    expect("completion over the turn's own cap", over_cap, "INVALID", "completion_exceeds_cap")
    float_total = _row(completion_tokens=200)
    float_total["completion_tokens"] = 200.9
    expect("a non-integral reported total (200.9 used to TRUNCATE to 200)", float_total,
           "INVALID", "usage_not_integer")
    bool_usage = _row()
    bool_usage["per_turn"][0]["output_tokens"] = True
    expect("a boolean usage value (isinstance(True, int) is True)", bool_usage, "INVALID", "usage_not_integer")
    mismatch = _row()
    mismatch["completion_tokens"] = 201
    expect("a reported total that does not equal the per-turn sum", mismatch, "INVALID", "cumulative_mismatch")
    ceiling = _row(completion_tokens=200)
    ceiling["max_total_completion_tokens"] = 100
    expect("a rollout over its own episode ceiling", ceiling, "INVALID", "ceiling_exceeded")
    wire = _row()
    wire["wire_caps"] = [{"max_tokens": 999}]
    expect("a wire cap that disagrees with the declared cap", wire, "INVALID", "wire_cap_mismatch")
    surplus = _row()
    surplus["wire_caps"] = surplus["wire_caps"] + [{"max_tokens": 200}]
    expect("a surplus provider request", surplus, "INVALID", "extra_wire_request")
    retried = _row(attempts=2)
    expect("more than one framework attempt", retried, "INVALID", "framework_retry")
    foreign = _row()
    foreign["requests"] = foreign["requests"] + [{"turn": 1, "attempt": 1, "status": "ok", "seconds": 1.0,
                                                  "attempt_id": "a2", "rollout_id": "OTHER"}]
    expect("a billed request bound to another rollout", foreign, "INVALID", "framework_retry")
    counts = _row()
    counts["requests"] = counts["requests"] + [{"turn": 2, "attempt": 1, "status": "ok", "seconds": 1.0,
                                                "attempt_id": "a1", "rollout_id": "r1"}]
    expect("two succeeded requests for one turn", counts, "INVALID", "request_count_mismatch")
    no_digests = _row()
    no_digests["artifact_stored_bytes_digest"] = None
    expect("a BOUND artifact with no digests", no_digests, "INVALID", "artifact_bound_without_digests")
    unbound = _row(artifact="NO_ARTIFACT")
    unbound["artifact_reason"] = None
    expect("an unbound artifact with no reason", unbound, "INVALID", "artifact_unbound_without_reason")
    stored = _row(budget_accounting="INVALID/env_usage_absent")
    expect("a row the LIVE instrument called invalid for a reason the archive cannot reproduce",
           stored, "INVALID", "stored_status_invalid")
    expect("a quarantined row", _row(quarantined=True, status="s"), "INVALID", "quarantined")
    expect("an old-instrument row", _old_row(), "VALID/derived", "no_wire_caps")
    # Post-run correction (2026-09-01, Codex T51 §12): the confirm1v4 writer
    # computed but omitted per-turn `tool_call_chars`. The field feeds the
    # plausibility floor (suspicion, never validity), so its absence ALONE —
    # on a row carrying every validity evidence — must NOT demote to derived;
    # with any other gap present it still does (a genuinely old row).
    writer_bug = _row()
    for t in writer_bug["per_turn"]:
        t.pop("tool_call_chars", None)
    expect("a new-instrument row missing ONLY tool_call_chars (the confirm1v4 writer bug)",
           writer_bug, "VALID")
    # And the WRITER records the key (the bug itself, pinned): the real
    # `per_turn_rows` must carry `tool_call_chars` counting this turn's own
    # serialized tool-call arguments.
    from types import SimpleNamespace as NS
    call = NS(id="c1", name="write_ledger", arguments="x" * 500)
    step = NS(prompt=[NS(role="user", content="go")],
              response=NS(usage=NS(prompt_tokens=10, completion_tokens=20, reasoning_tokens=0),
                          message=NS(content="", reasoning_content=None, tool_calls=[call],
                                     finish_reason="tool_calls")),
              is_truncated=False)
    written = mb.per_turn_rows([step], True, [8000], None)
    if not written or "tool_call_chars" not in written[0]:
        problems.append("per_turn_rows does not record tool_call_chars (the confirm1v4 writer bug is back)")
    elif written[0]["tool_call_chars"] < 500:
        problems.append(f"per_turn_rows tool_call_chars {written[0]['tool_call_chars']} misses the 500-char argument")

    # Every reason code comes from a closed set.
    known = set(mb.BUDGET_ACCOUNTING_CODES) | set(mb.ROW_VALIDATION_EXTRA_CODES) | set(mb.ROW_DERIVATION_GAPS)
    known |= {f"env_{c}" for c in mb.ENV_BUDGET_ACCOUNTING_CODES} | {"env_unrecognized"}
    for label, row in (("valid", _row()), ("derived", _old_row()), ("retried", _row(attempts=2))):
        _, reasons = mb.validate_row(row)
        leaked = set(reasons) - known
        if leaked:
            problems.append(f"{label}: reasons outside the closed set: {leaked}")
    # The writer runs the SAME validator on the row it writes.
    live = mb.one_rollout(DEFAULT_SHIM, usage_scripted([
        (tec.write(), Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=50, total_tokens=60)),
        (tec.submit(), Usage(prompt_tokens=20, reasoning_tokens=0, completion_tokens=50, total_tokens=70)),
    ]), DUMMY_CONFIG, "test:validator_on_write", "scripted", 4000, 0, 100, True)
    if "row_validation" not in live or live["row_validation"]["status"] not in mb.ROW_VALIDATION_STATUSES:
        problems.append(f"one_rollout did not record a row_validation: {live.get('row_validation')}")
    if live.get("row_validation_agrees") is not True:
        problems.append(f"the live status and the re-derivation disagree on a clean row: "
                        f"{live['budget_accounting']} vs {live['row_validation']}")
    return check("validate_row re-derives every predicate from literal adversarial archived rows, refusing "
                 "each claim of VALID on its own evidence, and the writer runs the same function",
                 not problems, "\n".join(problems))


def test_replay_contract_digest_moves_with_every_declared_clause():
    """The replay policy has its own identity (Codex T48a §4/Q7, T48b §1):
    the two arms' digests differ, the declared clauses are all present, and
    the concrete client/library versions are inside the digest so a
    dependency bump becomes a NEW condition rather than invisible drift."""
    problems = []
    contract = mb.replay_contract(True)
    for clause in ("assistant_fields_retained", "assistant_fields_dropped", "none_as_absent_fields",
                   "continuation_fields_retained_verbatim", "continuation_fields_unsupported",
                   "tool_call_ordering", "tool_result_association", "reasoning_replay",
                   "provider_projection", "library_versions", "replay_contract_version"):
        if clause not in contract:
            problems.append(f"the replay contract does not declare {clause}")
    if contract["none_as_absent_fields"] != ["reasoning_content"]:
        problems.append(f"None-as-absent must be pinned FIELD BY FIELD, not generalised: "
                        f"{contract['none_as_absent_fields']}")
    if "thought_signature" not in contract["continuation_fields_unsupported"]:
        problems.append("thought_signature must be declared UNSUPPORTED — a family requiring it is a "
                        "provider/client incompatibility, never a model failure")
    if mb.replay_contract(False)["assistant_fields_dropped"] != ["reasoning_content"]:
        problems.append("B2' must declare that it drops reasoning_content")
    if mb.replay_contract_digest(True) == mb.replay_contract_digest(False):
        problems.append("the two replay policies share a digest")
    if mb.replay_contract_digest(True, {"verifiers": "0.0.0"}) == mb.replay_contract_digest(True):
        problems.append("a library version change did not move the digest")
    if mb.replay_contract_digest(True) != mb.replay_contract_digest(True):
        problems.append("the digest is not deterministic")
    row = mb.one_rollout(DEFAULT_SHIM, scripted([tec.submit("s")]), DUMMY_CONFIG, "test:replay", "scripted",
                         4000, 0, 0, True)
    if row.get("replay_contract_digest") != mb.replay_contract_digest(True) \
            or row.get("replay_contract_version") != mb.REPLAY_CONTRACT_VERSION:
        problems.append(f"the row does not carry the replay contract identity: "
                        f"{row.get('replay_contract_version')}/{row.get('replay_contract_digest')}")
    return check("the replay contract declares every clause, distinguishes the arms, moves with the client "
                 "library versions, and lands on every row", not problems, "\n".join(problems))


def test_arm_table_refuses_to_pool_across_contracts_and_schedules():
    """Codex T48a §4: rows with different replay or episode digests inside
    ONE condition are an error, not a warning — they can share a world, a
    prompt and a ceiling and still not be comparable."""
    problems = []
    same = [_row(), _row()]
    if AT.check_pooling(same, ("provider", "model", "selector", "arm")):
        problems.append("two rows from the same contract were refused")
    mixed_replay = [_row(), _row(replay_contract_digest="OTHER")]
    if not AT.check_pooling(mixed_replay, ("provider", "model", "selector", "arm")):
        problems.append("two different REPLAY contracts were pooled into one condition")
    mixed_episode = [_row(), _row(episode_contract_digest="OTHER")]
    if not AT.check_pooling(mixed_episode, ("provider", "model", "selector", "arm")):
        problems.append("two different EPISODE contracts were pooled into one condition")
    # A pilot row (no replay digest at all) beside a corrected row is
    # exactly the mixture that must never happen silently.
    if not AT.check_pooling([_row(), _old_row()], ("provider", "model", "arm")):
        problems.append("a pilot row with no replay digest was pooled with a corrected one")
    # Different models are different conditions, not a violation.
    if AT.check_pooling([_row(model="a"), _row(model="b", replay_contract_digest="OTHER")],
                        ("provider", "model", "arm")):
        problems.append("two different models were treated as one condition")
    return check("arm_table refuses (never merely warns about) a condition containing more than one "
                 "(episode, replay) contract", not problems, "\n".join(problems))


def test_failure_classification_is_a_fixed_map_applied_blind():
    """Four buckets (Codex T48b §5), decided from the error text and the
    observed request size only — never from the arm or the outcome. The
    size-dependent cases (429, timeout) go to AMBIGUOUS when the provider's
    tokens-per-minute limit or the request size is unknown, so they land in
    a sensitivity section rather than silently in whichever bucket suits."""
    problems = []

    def saturated(mine, total=1_000_000, requests=(60, 60)):
        """BILLED tokens and ACCEPTED requests — the established quantities.
        Never a rejected attempt's estimate (Codex T50 §3)."""
        return _window(billed=total, billed_mine=mine,
                       accepted=requests[0], accepted_mine=requests[1])

    # (text, window, expected bucket). The 429 cases use the OBSERVED
    # trailing-window evidence, never a hypothetical repetition of one
    # request's size (Codex T49 §6).
    cases = [
        ("400 Function call is missing a thought_signature in functionCall parts", None,
         "capability_incompatible"),
        ("422 extra_forbidden messages.3.assistant.reasoning_content", None, "capability_incompatible"),
        ("413 Request entity too large", None, "arm_induced"),
        ("400 This model's maximum context length is 128000 tokens", None, "arm_induced"),
        ("InvalidModelResponseError: empty response", None, "arm_induced"),
        ("500 Internal Server Error", None, "exogenous"),
        ("APIConnectionError: connection error", None, "exogenous"),
        ("401 Unauthorized", None, "exogenous"),
        # the window is full and this cell sent most of it
        ("429 Too Many Requests", saturated(900_000), "arm_induced"),
        # the window is full but this cell sent a minority: CARRY-OVER
        # (the request dimension is left quiet so this case is purely about
        # tokens; the two dimensions DISAGREEING is its own case, in
        # test_tpm_and_rpm_are_evaluated_independently)
        ("429 Too Many Requests", saturated(100_000, requests=(6, 2)), "ambiguous"),
        # the window was nowhere near the quota
        ("429 Too Many Requests", saturated(9_000, total=50_000, requests=(3, 1)), "exogenous"),
        # no window evidence at all -> the sensitivity set, never a guess
        ("429 Too Many Requests", None, "ambiguous"),
        ("APITimeoutError: request timed out", None, "ambiguous"),
        ("APITimeoutError: request timed out", saturated(900_000), "ambiguous"),
        ("something nobody has seen before", None, "ambiguous"),
        ("", None, "ambiguous"),
    ]
    for text, window, want in cases:
        bucket, rule = AT.classify_error(text, None, 1_000_000, 6.0, window=window, rpm=49.8)
        if bucket != want:
            problems.append(f"{text[:48]!r} (window {window}) -> {bucket}/{rule}, wanted {want}")
        if bucket not in AT.FAILURE_BUCKETS:
            problems.append(f"{text[:32]!r} produced a bucket outside the closed set: {bucket}")
    # A quota nobody established keeps a saturating-looking window ambiguous.
    # The evidence is a TYPED name, not the digits "429": free text carries no
    # numeric needle at all any more (Codex T50 §2).
    if AT.classify_error("RateLimitError", None, None, None, window=saturated(900_000), rpm=None)[1] != \
            "rate_limit_quota_unknown":
        problems.append("a 429 with no established TPM/RPM must be ambiguous/rate_limit_quota_unknown")
    # BLINDNESS: the classifier's signature cannot see the arm or the reward.
    import inspect
    params = list(inspect.signature(AT.classify_error).parameters)
    if params != ["text", "request_tokens", "tpm", "min_interval", "window", "rpm", "http_status"]:
        problems.append(f"classify_error must only ever see the error text, the request size, the quota, "
                        f"the observed window and the archived HTTP status: {params}")
    # Two rows with the SAME error and different arms classify identically.
    a = AT.classify_row(_row(arm="A", quarantined=True, status="429 Too Many Requests"))
    b = AT.classify_row(_row(arm="B2", quarantined=True, status="429 Too Many Requests"))
    if a != b:
        problems.append(f"the same failure classified differently by arm: {a} vs {b}")
    # An accounting-invalid row is instrument_invalid, by the VALIDATOR.
    bucket, _ = AT.classify_row(_row(attempts=2))
    if bucket != "instrument_invalid":
        problems.append(f"an accounting-invalid row should be instrument_invalid, got {bucket}")
    if AT.classify_row(_row()) != (None, None):
        problems.append("a clean, delivered row must not be classified as a failure at all")
    return check("failure classification is a fixed, ordered map into four buckets plus an explicit ambiguous "
                 "set, applied blind to the arm and the outcome", not problems, "\n".join(problems))


def test_none_as_absent_is_narrow_and_falsey_values_survive():
    """Codex T48b §2: `None` means absent for `reasoning_content`, and for
    nothing else. `0`, `False`, `""`, an empty tool-arguments object and a
    real reasoning payload must all survive the projection byte for byte,
    under BOTH replay policies."""
    problems = []

    async def project(replay, messages):
        client = mb.make_client_cls(0.0, replay)(DUMMY_CONFIG)
        prompt, _ = await client.to_native_prompt(messages)
        return prompt

    messages = [
        SystemMessage(role="system", content="s"),
        UserMessage(role="user", content="u"),
        AssistantMessage(role="assistant", content="", reasoning_content=None,
                         tool_calls=[ToolCall(id="c0", name="list_files", arguments="{}")]),
        ToolMessage(role="tool", content="", tool_call_id="c0"),
        AssistantMessage(role="assistant", content="visible", reasoning_content="thought"),
    ]
    for replay in (True, False):
        prompt = asyncio.run(project(replay, copy.deepcopy(messages)))
        assistants = [m for m in prompt if m.get("role") == "assistant"]
        if "reasoning_content" in assistants[0]:
            problems.append(f"replay={replay}: a None reasoning_content was not dropped")
        if assistants[0].get("content") != "":
            problems.append(f"replay={replay}: an EMPTY-STRING content was altered: "
                            f"{assistants[0].get('content')!r}")
        arguments = assistants[0]["tool_calls"][0]["function"]["arguments"]
        if arguments != "{}":
            problems.append(f"replay={replay}: an EMPTY tool-arguments object was altered: {arguments!r}")
        tool_reply = [m for m in prompt if m.get("role") == "tool"][0]
        if tool_reply.get("content") != "":
            problems.append(f"replay={replay}: an empty tool reply was altered: {tool_reply.get('content')!r}")
        present = assistants[1].get("reasoning_content", "ABSENT")
        if replay and present != "thought":
            problems.append("a real reasoning payload was dropped under full replay")
        if not replay and present != "ABSENT":
            problems.append("B2' did not drop a real reasoning payload")
    # And the rule is declared, field by field, in the replay contract.
    if mb.NONE_AS_ABSENT_FIELDS != ("reasoning_content",):
        problems.append(f"the None-as-absent rule must name exactly one field: {mb.NONE_AS_ABSENT_FIELDS}")
    return check("None-as-absent applies to reasoning_content and nothing else: empty strings, empty "
                 "tool-argument objects and real reasoning payloads all survive the projection",
                 not problems, "\n".join(problems))


def test_attempt_identity_binds_every_request_to_one_attempt():
    """Codex T48b §10: the prompt-shape detector is an alarm; the
    authoritative attempt boundary is an explicit identity bound to every
    provider request. `run_rollout` builds a FRESH state dict per attempt,
    so a nonce stamped into the state is unique to that attempt — including
    the case the heuristic CANNOT see, where a retried attempt's first
    prompt is not back down to system+user."""
    import verifiers.legacy.clients.openai_chat_completions_client as oai_mod

    class _FakeResponse:
        def __init__(self):
            self.usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 5})()
            self.model = "scripted-model"

    async def fake_post(client, path, *, body, extra_headers=None):
        return _FakeResponse()

    client = mb.make_client_cls(0.0, True)(DUMMY_CONFIG)
    state_a = {"piv_rollout_id": "rollout-a"}
    state_b = {"piv_rollout_id": "rollout-b"}          # a FRESH state: the retry
    long_prompt = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"},
                   {"role": "assistant", "content": "a"}, {"role": "tool", "content": "t"}]

    original = oai_mod.post_chat_completion_with_routed_experts_sidecar
    oai_mod.post_chat_completion_with_routed_experts_sidecar = fake_post
    try:
        asyncio.run(client.get_native_response(long_prompt, "m", {"max_tokens": 100}, None, state=state_a))
        asyncio.run(client.get_native_response(long_prompt, "m", {"max_tokens": 100}, None, state=state_a))
        # The retry: a fresh state, but a prompt the heuristic reads as a
        # continuation (four messages, never back down to two).
        asyncio.run(client.get_native_response(long_prompt, "m", {"max_tokens": 100}, None, state=state_b))
    finally:
        oai_mod.post_chat_completion_with_routed_experts_sidecar = original

    problems = []
    if client.attempts != 2:
        problems.append(f"attempts by IDENTITY: {client.attempts}, expected 2")
    if client.attempts_prompt_shape != 1:
        problems.append(f"the prompt-shape alarm should see only ONE segment here ({client.attempts_prompt_shape}) "
                        "— that disagreement is exactly why identity is authoritative")
    if len(client.requests) != 3:
        problems.append(f"requests logged: {len(client.requests)}, expected 3")
    if {r["rollout_id"] for r in client.requests} != {"rollout-a", "rollout-b"}:
        problems.append(f"requests did not record their rollout ids: {client.requests}")
    if len({r["attempt_id"] for r in client.requests}) != 2:
        problems.append("the two attempts share one nonce")
    if len(client.last_segment_wire_caps) != 1:
        problems.append(f"the surviving attempt has one call, got {len(client.last_segment_wire_caps)}")
    if mb.ATTEMPT_NONCE_KEY not in state_a or state_a[mb.ATTEMPT_NONCE_KEY] == state_b[mb.ATTEMPT_NONCE_KEY]:
        problems.append("the nonce is not per-state")
    turns = [r["turn"] for r in client.requests]
    if turns != [1, 2, 1]:
        problems.append(f"per-attempt turn numbering: {turns}, expected [1, 2, 1]")
    status = mb.compute_budget_accounting(
        [100], [{"input_tokens": 10, "output_tokens": 5, "request_max_tokens": 100}], None, None, 5, 0,
        client.attempts, requests=client.requests, rollout_id="rollout-b")
    if status != "INVALID/framework_retry":
        problems.append(f"a row whose requests span two attempts must be INVALID/framework_retry, got {status}")
    return check("every provider request is bound to an explicit attempt identity, the prompt-shape detector "
                 "is kept as an independent alarm, and a row whose billed requests span two attempts is "
                 "refused", not problems, "\n".join(problems))


def test_requests_log_records_every_attempt_including_rate_limited_ones():
    """Codex T48a §3.2: `PacedClient`'s own 429 pacing loop records EVERY
    attempt in `row["requests"]`, and a 429 carries no billed tokens."""
    import openai
    import verifiers.legacy.clients.openai_chat_completions_client as oai_mod

    class _FakeResponse:
        def __init__(self):
            self.usage = type("U", (), {"prompt_tokens": 11, "completion_tokens": 7})()
            self.model = "scripted-model"

    calls = {"n": 0}

    async def flaky_post(client, path, *, body, extra_headers=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise openai.RateLimitError("429 Too Many Requests", response=_FakeHTTPResponse(), body=None)
        return _FakeResponse()

    class _FakeHTTPResponse:
        status_code = 429
        headers: dict = {}
        request = None

    client = mb.make_client_cls(0.0, True)(DUMMY_CONFIG)
    original = oai_mod.post_chat_completion_with_routed_experts_sidecar
    oai_mod.post_chat_completion_with_routed_experts_sidecar = flaky_post
    original_sleep = asyncio.sleep

    async def no_sleep(_seconds):                       # the 20 s back-off, not actually waited out
        return await original_sleep(0)

    asyncio.sleep = no_sleep
    try:
        asyncio.run(client.get_native_response([{"role": "system", "content": "s"}], "m",
                                               {"max_tokens": 100}, None, state={"piv_rollout_id": "r"}))
    finally:
        oai_mod.post_chat_completion_with_routed_experts_sidecar = original
        asyncio.sleep = original_sleep

    problems = []
    if len(client.requests) != 2:
        problems.append(f"requests: {client.requests} — the 429 attempt must be recorded too")
    statuses = [r["status"] for r in client.requests]
    if statuses != ["rate_limited", "ok"]:
        problems.append(f"statuses: {statuses}, expected ['rate_limited', 'ok']")
    rate_limited = client.requests[0]
    if rate_limited["billed_input_tokens"] is not None or rate_limited["billed_output_tokens"] is not None:
        problems.append(f"a 429 must carry no billed tokens: {rate_limited}")
    if client.billed_input_tokens_all_attempts != 11 or client.billed_output_tokens_all_attempts != 7:
        problems.append(f"billed totals counted the 429: {client.billed_input_tokens_all_attempts}/"
                        f"{client.billed_output_tokens_all_attempts}")
    if len(client.wire_caps) != 1:
        problems.append(f"only the SUCCEEDED request may add a wire cap: {client.wire_caps}")
    for key in ("turn", "attempt", "status", "seconds"):
        if any(key not in r for r in client.requests):
            problems.append(f"every request record must carry {key}")
    return check("PacedClient's 429 pacing loop records every attempt, a rate-limited attempt carries no "
                 "billed tokens, and only a succeeded request contributes a wire cap",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 9. the adversarial verifier's findings on this branch
# --------------------------------------------------------------------------

def test_primary_contrast_drops_a_block_whose_arm_cell_was_censored():
    """F1 — the verifier's own fixture. Six rows, two selectors, three arms;
    the B1′/train:12 cell is a QUARANTINED exogenous 429, a provider rate
    limit that had nothing to do with the arm.

    The two estimand tables already filtered such a row. The primary
    contrast did not: it received the RAW list, read the censored cell as a
    failed delivery, and printed "B1′ −50 pp, 17× cost" off one attempt
    nobody had made. The block must be dropped WHOLE — contrasting the A′
    and B2′ cells that survived would reintroduce the same censoring — and
    the drop must be reported, not silent."""
    problems = []
    arms = ("A", "B1", "B2")
    model = "mistral-medium-2508"                 # a model whose quota is pre-registered
    rows = []
    for selector in ("train:1", "train:12"):
        for arm in arms:
            rows.append(_row(model=model, selector=selector, arm=arm, reward=1.0, complete=True,
                             total_tokens=40_000))
    # The censored cell: B1' on train:12, killed by a rate limit while the
    # OBSERVED provider window was nowhere near the quota — whatever
    # exhausted it, this experiment's own traffic did not.
    rows = [r for r in rows if not (r["selector"] == "train:12" and r["arm"] == "B1")]
    rows.append(_row(model=model, selector="train:12", arm="B1", quarantined=True,
                     status="429 Too Many Requests", min_interval=6.0,
                     requests=[{"turn": 1, "attempt": 1, "status": "rate_limited", "seconds": 1.0,
                                "attempt_id": "a", "rollout_id": "r", "billed_input_tokens": None,
                                "estimated_request_tokens": 9_000, "billed_output_tokens": None,
                                "provider_window": _window(billed=40_000, billed_mine=9_000,
                                                           accepted=4, accepted_mine=1,
                                                           current=9_000)}]))

    bucket, rule = AT.classify_row(rows[-1])
    if (bucket, rule) != ("exogenous", "rate_limit_window_not_saturated"):
        problems.append(f"the censored row classified as {bucket}/{rule}, expected exogenous")
    blocks, dropped = AT.arm_blocks(rows, arms)
    if len(blocks) != 1:
        problems.append(f"complete blocks: {len(blocks)}, expected 1 (train:1 only)")
    if sum(dropped.values()) != 1:
        problems.append(f"dropped blocks: {dict(dropped)}, expected exactly 1")
    if not any("B1" in reason and "exogenous" in reason for reason in dropped):
        problems.append(f"the drop must name the missing arm and why: {dict(dropped)}")
    if blocks and blocks[0]["A"].get("selector") != "train:1":
        problems.append("the surviving block is not the uncensored one")
    # The headline number the bug produced must be gone.
    delta = AT._rate_delta(blocks, "B1", "A")
    if delta != 0.0:
        problems.append(f"Δ delivery rate vs A': {delta:+.2f}, expected 0.00 — every surviving cell delivered")
    text = "\n".join(AT.render_ratios(rows, arms, "A"))
    if "-0.50" in text or "−0.50" in text:
        problems.append("the −50 pp row is still printed")
    if "Blocks dropped from the contrast" not in text or "missing B1" not in text:
        problems.append("the dropped block is not reported in the table")
    # An ARM-INDUCED failure is a different matter: it IS the arm's outcome
    # and must stay in the contrast as a non-delivery.
    arm_induced = [r for r in rows if not (r["selector"] == "train:12" and r["arm"] == "B1")]
    arm_induced.append(_row(model=model, selector="train:12", arm="B1", quarantined=True,
                            status="413 Request entity too large"))
    kept, dropped_ai = AT.arm_blocks(arm_induced, arms)
    if len(kept) != 2 or dropped_ai:
        problems.append(f"an arm_induced failure must STAY in the contrast: {len(kept)} blocks, "
                        f"dropped {dict(dropped_ai)}")
    if AT._rate_delta(kept, "B1", "A") != -0.5:
        problems.append("an arm_induced failure must count against its own arm (−0.50 here)")
    return check("a block whose arm cell was censored for a reason the arm did not cause is dropped WHOLE "
                 "from the primary contrast and reported, while an arm_induced failure stays in it",
                 not problems, "\n".join(problems))


def test_derived_rows_contribute_nothing_to_a_confirmatory_table():
    """F2 — `build_stratum` stripped `instrument_invalid` from the
    operational cost but not `VALID/derived`: a pilot-era row's billed
    tokens were entering a CONFIRMATORY operational cost even though the
    same row was refused everywhere else. In a confirmatory table a derived
    row contributes nothing — not a delivery, not a denominator, not a
    token. In `--pilot` mode it contributes, labelled by `n_derived`."""
    problems = []
    good = _row(total_tokens=10_000, billed_input_tokens_all_attempts=10_000,
                billed_output_tokens_all_attempts=0)
    derived = _old_row(total_tokens=990_000, billed_input_tokens_all_attempts=990_000,
                       billed_output_tokens_all_attempts=0, reward=0.0, artifact="NO_ARTIFACT",
                       complete=False, submitted=False)
    scheduled = [{"provider": "mistral", "model": "m", "selector": "train:1", "arm": "A",
                  "replicate": 1, "block_id": "b", "arm_position": 0, "planned_ordinal": 1}
                 for _ in range(2)]

    confirmatory = AT.build_stratum([good, derived], scheduled, pilot=False, schedule_complete=True)
    if confirmatory["n"] != 1 or confirmatory["n_derived"] != 1:
        problems.append(f"n/n_derived: {confirmatory['n']}/{confirmatory['n_derived']}, expected 1/1")
    if confirmatory["effective_cost_operational"] != 10_000:
        problems.append(f"operational cost {confirmatory['effective_cost_operational']}, expected 10000 — "
                        "the derived row's 990,000 billed tokens must not enter a confirmatory cost")
    if confirmatory["operational_denominator"] != 1:
        problems.append(f"operational denominator {confirmatory['operational_denominator']}, expected 1 — "
                        "a derived row is not a trustworthy observation of a scheduled cell either")
    if confirmatory["effective_cost_conditional"] != 10_000:
        problems.append(f"conditional cost {confirmatory['effective_cost_conditional']}, expected 10000")

    pilot = AT.build_stratum([good, derived], scheduled, pilot=True, schedule_complete=True)
    if pilot["n"] != 2:
        problems.append(f"pilot n: {pilot['n']}, expected 2 (a derived row is admitted, labelled)")
    if pilot["effective_cost_operational"] != 1_000_000:
        problems.append(f"pilot operational cost {pilot['effective_cost_operational']}, expected 1,000,000 — "
                        "in a pilot table the derived row's spend DOES count, labelled")
    if pilot["n_derived"] != 1:
        problems.append(f"pilot n_derived: {pilot['n_derived']}, expected 1")
    # And it may not enter a confirmatory contrast either.
    blocks, dropped = AT.arm_blocks([_row(arm=a) for a in ("A", "B1")] + [_old_row(arm="B2")],
                                    ("A", "B1", "B2"), pilot=False)
    if blocks or "derived" not in str(dict(dropped)):
        problems.append(f"a derived arm cell must drop its whole block in a confirmatory contrast: "
                        f"{len(blocks)} blocks, {dict(dropped)}")
    blocks_pilot, _ = AT.arm_blocks([_row(arm=a) for a in ("A", "B1")] + [_old_row(arm="B2")],
                                    ("A", "B1", "B2"), pilot=True)
    if len(blocks_pilot) != 1:
        problems.append("a --pilot contrast should accept the derived cell")
    return check("a VALID/derived row contributes nothing to a confirmatory table — not delivery, not "
                 "denominator, not cost, not a contrast block — and contributes, labelled, to a pilot one",
                 not problems, "\n".join(problems))


def test_a_partial_output_file_is_re_run_and_rows_are_written_atomically():
    """F3 — existence was the done-test, so a process killed mid-write left
    truncated JSON that `run_arms` skipped forever and `arm_table` dropped
    with a warning: the cell was neither re-run nor counted. Fixed at both
    ends — `measure_budget.write_atomic` (temp file + `os.replace`, so a
    reader never sees a partial file) and a done-test that requires the file
    to PARSE and to carry a row for this cell."""
    import tempfile
    problems = []
    schedule = _schedule(label="f3")
    cell = schedule["cells"][0]

    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        out_path = SA.output_path_for(reviews, cell["model"], schedule["date_stamp"], cell["tag"])

        done, why = RA.cell_is_done(out_path, schedule, cell)
        if done:
            problems.append("a missing file was reported done")

        # The planted truncated file: what a kill mid-write used to leave.
        out_path.write_text('[{"selector": "train:1", "arm": "A", "budget_acc', encoding="utf-8")
        done, why = RA.cell_is_done(out_path, schedule, cell)
        if done:
            problems.append("a TRUNCATED output file was reported done — the cell would never re-run")
        if "unreadable" not in why:
            problems.append(f"the reason must name the corruption: {why!r}")
        # And the reader agrees it is unusable, which is the other half of
        # the bug: neither tool counted it.
        rows, _ = AT.load_rows(reviews, [cell["tag"]])
        if rows:
            problems.append("arm_table read rows out of a truncated file")

        # A well-formed file for a DIFFERENT cell does not mark this one done.
        out_path.write_text(json.dumps([{"schedule_id": schedule["schedule_id"], "tag": "someone_else",
                                         "model": cell["model"], "selector": "train:99", "arm": "B2",
                                         "replicate": 9}]), encoding="utf-8")
        done, why = RA.cell_is_done(out_path, schedule, cell)
        if done:
            problems.append("a file carrying another cell's row marked this cell done")

        # The real thing.
        mb.write_atomic(out_path, json.dumps([{"schedule_id": schedule["schedule_id"], "tag": cell["tag"],
                                               "model": cell["model"], "selector": cell["selector"],
                                               "arm": cell["arm"], "replicate": cell["replicate"]}]))
        done, why = RA.cell_is_done(out_path, schedule, cell)
        if not done:
            problems.append(f"a complete row file was not recognised: {why}")
        # write_atomic leaves no temporary behind and replaces in one step.
        leftovers = [p.name for p in reviews.iterdir() if ".tmp" in p.name]
        if leftovers:
            problems.append(f"write_atomic left temporary files behind: {leftovers}")
        previous = out_path.read_text(encoding="utf-8")
        mb.write_atomic(out_path, json.dumps([{"schedule_id": schedule["schedule_id"], "tag": cell["tag"],
                                               "model": cell["model"], "selector": cell["selector"],
                                               "arm": cell["arm"], "replicate": cell["replicate"],
                                               "reward": 1.0}]))
        if out_path.read_text(encoding="utf-8") == previous:
            problems.append("write_atomic did not replace the file")
        if not json.loads(out_path.read_text(encoding="utf-8")):
            problems.append("the replaced file does not parse")
    return check("a truncated or foreign output file is re-run rather than skipped forever, and rows are "
                 "written atomically so a reader never sees a partial file",
                 not problems, "\n".join(problems))


def test_two_executors_on_one_cell_and_exactly_one_runs():
    """F4 — nothing stopped two executors pointed at one schedule from both
    seeing a missing output file, both paying the provider for the same
    cell, and one overwriting the other. The claim is an `O_CREAT | O_EXCL`
    create, atomic at the filesystem, so exactly one of any number of racing
    processes wins.

    Codex T49 §5 removed the automatic stale TAKEOVER that used to sit here:
    a read-then-`os.replace` is not atomic, so two contenders could both
    complete it and both believe they had won. A stale claim is now
    REPORTED, with instructions; and `release_cell` verifies ownership before
    unlinking, so a late old owner can no longer delete a new owner's claim.
    """
    import tempfile
    problems = []
    schedule = _schedule(label="f4")
    cell = schedule["cells"][0]

    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        out_path = SA.output_path_for(reviews, cell["model"], schedule["date_stamp"], cell["tag"])
        claim_path = out_path.with_name(out_path.name + ".claim")

        winners = [RA.claim_cell(out_path, f"session-{i}", cell, RA.DEFAULT_CLAIM_TTL_SECONDS)
                   for i in range(5)]
        if sum(1 for ok, _ in winners if ok) != 1:
            problems.append(f"exactly one executor must win the cell, got {[w[0] for w in winners]}")
        if not winners[0][0]:
            problems.append("the FIRST claimer should be the winner")
        for ok, note in winners[1:]:
            if ok or "session-0" not in note:
                problems.append(f"a loser must be told who holds the cell: {(ok, note)}")
        held = json.loads(claim_path.read_text(encoding="utf-8"))
        if held.get("session_id") != "session-0" or held.get("tag") != cell["tag"]:
            problems.append(f"the claim does not carry its holder and cell: {held}")
        if "claimed_at" not in held:
            problems.append("the claim carries no timestamp, so a stale one cannot be detected")

        # A STALE claim (ttl 0) is REPORTED, never taken over automatically.
        ok, note = RA.claim_cell(out_path, "session-late", cell, 0.0)
        if ok:
            problems.append("a stale claim must NOT be taken over automatically (Codex T49 §5)")
        if "STALE" not in note or "deliberately" not in note:
            problems.append(f"a stale claim must be reported with instructions: {note!r}")
        if json.loads(claim_path.read_text(encoding="utf-8")).get("session_id") != "session-0":
            problems.append("the stale claim's holder was rewritten by a process that did not own it")

        # A NON-OWNER may not release someone else's claim.
        RA.release_cell(out_path, "session-late")
        if not claim_path.exists():
            problems.append("release_cell let a non-owner delete another session's claim")

        # The owner releases, and the cell is free for the next session.
        RA.release_cell(out_path, "session-0")
        if claim_path.exists():
            problems.append("release_cell left the owner's own claim behind")
        if not RA.claim_cell(out_path, "session-next", cell, RA.DEFAULT_CLAIM_TTL_SECONDS)[0]:
            problems.append("a released cell could not be claimed again")
        RA.release_cell(out_path, "session-next")
        RA.release_cell(out_path, "session-next")    # idempotent: releasing twice must not raise
        RA.release_cell(out_path)                    # no session given: unconditional, still safe
    return check("exactly one of five racing executors claims a cell, a loser is told who holds it, a stale "
                 "claim is REPORTED rather than silently taken over, only the owner can release, and "
                 "releasing is idempotent", not problems, "\n".join(problems))


def test_rate_limit_classification_uses_the_observed_rolling_window():
    """Codex T49 §6 — the RETIRED rule asked whether the largest request,
    hypothetically repeated every `I` seconds for a minute, would reach the
    provider's TPM (`S >= TPM * I / 60`). That is a thought experiment: a
    single 120K request does not consume a 356K minute, and a small request
    rejected right after a large one from the PREVIOUS CELL was called
    exogenous although the experiment's own traffic had filled the window.

    The rule is now an observation. `measure_budget` keeps a shared
    provider-window ledger across cells and archives the trailing-60 s window
    on the rejected attempt itself; the classifier reads that."""
    problems = []
    if hasattr(AT, "saturates_rate_window"):
        problems.append("the retired hypothetical-rate rule is still exported")

    def window(mine, total, requests_total=5, requests_mine=2):
        """BILLED tokens and ACCEPTED requests only."""
        return _window(billed=total, billed_mine=mine,
                       accepted=requests_total, accepted_mine=requests_mine)

    tpm = AT.tpm_limit("mistral", "mistral-medium-2508")
    rpm = AT.rpm_limit("mistral", "mistral-medium-2508")
    if tpm != 356_250:
        problems.append(f"the console TPM for mistral-medium-2508 is not pinned: {tpm}")
    if rpm is None or abs(rpm - 0.38 * 60) > 1e-9:
        problems.append(f"the console RPM for mistral-medium-2508 is not pinned: {rpm}")
    cases = [
        # window full, this cell sent the majority: the arm's own traffic
        ("majority", window(300_000, 360_000), ("arm_induced", "rate_limit_window_saturated_tokens")),
        # window full, this cell a minority: CARRY-OVER from the cell before
        ("carryover", window(60_000, 360_000), ("ambiguous", "rate_limit_carryover_tokens")),
        # exactly half is not a majority: the threshold is strict
        ("exactly half", window(180_000, 360_000), ("ambiguous", "rate_limit_carryover_tokens")),
        # window nowhere near either quota
        ("quiet window", window(9_000, 40_000, 3, 1), ("exogenous", "rate_limit_window_not_saturated")),
        # the REQUEST window can saturate on its own, tokens or not
        ("requests", window(1_000, 1_000, 40, 39), ("arm_induced", "rate_limit_window_saturated_requests")),
        ("no evidence", None, ("ambiguous", "rate_limit_window_unknown")),
        # the PRE-T50 conflated shape establishes nothing at all
        ("legacy conflated snapshot",
         {"window_tokens_total": 360_000, "window_tokens_this_cell": 300_000,
          "window_requests_total": 5, "window_requests_this_cell": 2},
         ("ambiguous", "rate_limit_window_evidence_unseparated")),
    ]
    for label, w, want in cases:
        got = AT.classify_error("429 Too Many Requests", None, tpm, 6.0, window=w, rpm=rpm)
        if got != want:
            problems.append(f"{label}: {got}, expected {want}")
    # A request size ALONE — the retired rule's only input — decides nothing.
    if AT.classify_error("429 Too Many Requests", 120_000, tpm, 6.0)[0] != "ambiguous":
        problems.append("a 429 with no observed window must be ambiguous however large the request was")
    # The row carries the window, and `classify_row` finds it there.
    row = _row(quarantined=True, status="429 Too Many Requests", model="mistral-medium-2508",
               min_interval=6.0,
               requests=[{"status": "ok", "billed_input_tokens": 1_000},
                         {"status": "rate_limited", "provider_window": window(300_000, 360_000)}])
    if AT.classify_row(row) != ("arm_induced", "rate_limit_window_saturated_tokens"):
        problems.append(f"classify_row did not read the archived window: {AT.classify_row(row)}")
    if AT.rate_limit_window(row) is None:
        problems.append("rate_limit_window did not find the snapshot on the rate-limited attempt")
    return check("a 429 is arm_induced only when the OBSERVED trailing provider window was saturated AND "
                 "this cell sent the majority of it; a saturated window this cell did not fill is "
                 "carry-over (ambiguous), a quiet window is exogenous, and no evidence is ambiguous",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# Codex T49: the pre-start checklist
# --------------------------------------------------------------------------

def _sealed_schedule(label="sealed", selectors=None, contract=None, replicates=1):
    """A schedule with an experiment contract, built WITHOUT touching the
    package or the evaluator: the contract's values are fixtures here, so the
    identity/refusal witnesses are fast and hermetic. The contract SHAPE is
    the one `schedule_arms.build_experiment_contract` produces — witnessed
    against the real builder in `test_schedule_v2_seals_the_experiment_contract`.
    """
    selectors = selectors or ["train:1", "train:12", "train:30"]
    contract = contract or {
        "experiment_contract_version": 2,
        "instrument_commit": "0" * 40,
        "instrument_identity_version": SA.INSTRUMENT_IDENTITY_VERSION,
        "execution_paths": list(SA.EXECUTION_PATHS),
        "execution_excludes": list(SA.EXECUTION_EXCLUDES),
        "execution_tree_digest": "e" * 64,
        "execution_tree_file_count": 7,
        # Codex T51 §1: the interpreter's own bytes, sealed beside the
        # repository's. Fixture values here — the REAL builder is witnessed in
        # `test_schedule_v2_seals_the_experiment_contract` and the real walk in
        # `test_the_runtime_environment_is_sealed_as_bytes_not_versions`.
        "runtime_environment_identity_version": SA.RUNTIME_ENVIRONMENT_IDENTITY_VERSION,
        "runtime_environment_digest": "v" * 64,
        "runtime_environment_file_count": 11,
        "runtime_environment_bytes": 1234,
        "runtime_environment_distribution_count": 3,
        "runtime_environment_extra_file_count": 0,
        "runtime_environment_stdlib_file_count": 5,
        "runtime_environment_uncovered_sys_path": [],
        "python_version": "3.12.12 (fixture)",
        "analysis_plan": "confirmatory_design.md",
        "analysis_plan_sha256": "a" * 64,
        "arm_contract": {"A": {"per_turn_max_tokens": 8000, "reasoning_replay": True},
                         "B1": {"per_turn_max_tokens": 16000, "reasoning_replay": True},
                         "B2": {"per_turn_max_tokens": 8000, "reasoning_replay": False}},
        "expected_episode_contract_digest": "ep",
        "max_episode_output_tokens": 40_000,
        "expected_replay_contract_digest_by_arm": {"A": "rp_on", "B1": "rp_on", "B2": "rp_off"},
        "package_lock": {"replay_libraries": {"verifiers": "0.3.1", "openai": "3.5.0"},
                         "python": "3.12.12"},
        "failure_map_digest": "f" * 64,
        "manifest": {"rotation_id": "rot", "manifest_content_digest": "m" * 64, "manifest_present": True},
        "expected_public_task_id_by_selector": {s: f"task-{s}" for s in selectors},
        "provider_quotas": {"source": "fixture", "models": {}},
    }
    return SA.build_schedule(label, ROSTER, selectors, ["A", "B1", "B2"], replicates,
                             "2026-08-31", {"temperature": 0.0, "top_p": 1.0, "seed": None},
                             40_000, 600.0, 0, 6.0, contract)


def _cell_row(schedule, cell, **overrides):
    """A row that IS this sealed cell — every identity field and every
    contract expectation satisfied."""
    contract = schedule["experiment_contract"]
    arm = contract["arm_contract"][cell["arm"]]
    row = _row(model=cell["model"], selector=cell["selector"], arm=cell["arm"],
               provider=cell["provider"], replicate=cell["replicate"])
    row.update({
        "schedule_id": schedule["schedule_id"], "tag": cell["tag"],
        "planned_ordinal": cell["planned_ordinal"], "block_id": cell["block_id"],
        "permutation_index": cell["permutation_index"], "arm_position": cell["arm_position"],
        "task_id": contract["expected_public_task_id_by_selector"][cell["selector"]],
        "episode_contract_digest": contract["expected_episode_contract_digest"],
        "replay_contract_digest": contract["expected_replay_contract_digest_by_arm"][cell["arm"]],
        "per_turn_cap": arm["per_turn_max_tokens"], "reasoning_replay": arm["reasoning_replay"],
        "library_versions": contract["package_lock"]["replay_libraries"],
        # THE INSTRUMENT (Codex T51 §2): part of exact admission, so a row that
        # IS this cell carries the sealed digests. A row that does not is what
        # `test_a_row_from_a_foreign_instrument_is_refused_from_every_estimand`
        # builds deliberately.
        "instrument_identity_version": contract["instrument_identity_version"],
        "execution_tree_digest": contract["execution_tree_digest"],
        "runtime_environment_digest": contract["runtime_environment_digest"],
    })
    row.update(overrides)
    return row


def test_schedule_v2_seals_the_experiment_contract():
    """Codex T49 §2/Q2 — v1's `schedule_id` hashed the roster, the selectors,
    the arm LABELS and the order, but not what those labels MEAN:
    `run_arms` passes `--arm A` and `measure_budget.ARM_PRESETS` supplies the
    treatment at execution time, so `A` could become 16,000 tokens with the
    id unchanged. The same for the world (a manifest rotation makes `train:1`
    a different public task), the code and the analysis plan.

    Here the REAL builder runs against the package, and every field it must
    bind is checked to be (a) present, (b) computed from an authority rather
    than repeated, and (c) INSIDE the hash — mutate any one of them and
    `schedule_id` moves."""
    problems = []
    contract = SA.build_experiment_contract(["A", "B1", "B2"], ["train:1"], 40_000, SA.ANALYSIS_PLAN)

    required = ("instrument_commit", "analysis_plan_sha256", "arm_contract",
                "expected_episode_contract_digest", "expected_replay_contract_digest_by_arm",
                "package_lock", "failure_map_digest", "manifest",
                "expected_public_task_id_by_selector", "provider_quotas")
    for field in required:
        if not contract.get(field):
            problems.append(f"the sealed contract has no {field}")
    # Every value comes from its own authority, not from a literal here.
    if contract["arm_contract"] != {a: {"per_turn_max_tokens": mb.ARM_PRESETS[a][0],
                                        "reasoning_replay": mb.ARM_PRESETS[a][1]}
                                    for a in ("A", "B1", "B2")}:
        problems.append(f"arm_contract is not the literal ARM_PRESETS mapping: {contract['arm_contract']}")
    if contract["expected_episode_contract_digest"] != env_mod.episode_contract_digest(40_000):
        problems.append("the sealed episode digest is not the package's own at the pinned ceiling")
    for arm, digest in contract["expected_replay_contract_digest_by_arm"].items():
        want = mb.replay_contract_digest(mb.ARM_PRESETS[arm][1], mb.library_versions())
        if digest != want:
            problems.append(f"replay digest for {arm} is not measure_budget's own")
    if contract["expected_replay_contract_digest_by_arm"]["A"] == \
            contract["expected_replay_contract_digest_by_arm"]["B2"]:
        problems.append("A' and B2' must not share a replay digest — the replay policy IS the treatment")
    if contract["package_lock"]["replay_libraries"] != mb.library_versions():
        problems.append("package_lock does not carry the installed replay libraries")
    if not contract["expected_public_task_id_by_selector"].get("train:1"):
        problems.append("the serving door produced no public task id for train:1")
    if contract["analysis_plan_sha256"] != SA.sha256_file(SA.ANALYSIS_PLAN):
        problems.append("the analysis-plan digest is not the plan's own bytes")

    # THE HASH. Mutating any single contract field must move `schedule_id`.
    base = _sealed_schedule(contract=dict(contract))
    if not SA.is_confirmatory(base):
        problems.append("a schedule carrying an experiment contract is not recognised as confirmatory")
    if base["schedule_version"] != SA.SEALED_SCHEDULE_VERSION:
        problems.append(f"a sealed schedule must be v{SA.SEALED_SCHEDULE_VERSION}")
    for field in required + ("experiment_contract_version", "max_episode_output_tokens"):
        mutated = json.loads(json.dumps(contract, default=str))
        mutated[field] = "MUTATED" if not isinstance(mutated.get(field), dict) else {"mutated": True}
        if _sealed_schedule(contract=mutated)["schedule_id"] == base["schedule_id"]:
            problems.append(f"schedule_id did not move when {field} changed — it is not inside the hash")
    # And an unsealed schedule is NOT confirmatory, so every permissive path
    # stays open for the pilot.
    if SA.is_confirmatory(_schedule(label="pilot")):
        problems.append("an unsealed v1 schedule must not be treated as confirmatory")
    return check("schedule v2 seals the treatment, the world, the code, the libraries, the failure map, the "
                 "manifest rotation and the analysis plan INSIDE schedule_id — every field computed from its "
                 "own authority, and mutating any one of them moves the id",
                 not problems, "\n".join(problems))


def test_exact_cell_identity_refuses_partials_duplicates_and_missing_schedule_ids():
    """Codex T49 §3/Q3 — `cell_is_done` accepted `schedule_id is None`, a tag
    match OR a partial identity match, and ANY matching row in a list even
    when the file held duplicates or conflicting rows. For a confirmatory
    cell "done" means EXACTLY ONE row with every identity field and every
    contract expectation equal; anything else is `execution_integrity`,
    quarantined by name — never silently skipped and never re-run over."""
    import tempfile
    problems = []
    schedule = _sealed_schedule()
    cell = schedule["cells"][0]
    good = _cell_row(schedule, cell)

    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        out_path = SA.output_path_for(reviews, cell["model"], schedule["date_stamp"], cell["tag"])

        def status(rows):
            mb.write_atomic(out_path, json.dumps(rows, default=str))
            return RA.cell_status(out_path, schedule, cell)

        if RA.cell_status(out_path, schedule, cell)[0] != "unrun":
            problems.append("a missing file must be unrun")
        if status([good])[0] != "done":
            problems.append(f"the exact row was not accepted: {status([good])}")

        # Each of these is an INTEGRITY failure, not "done" and not "unrun".
        cases = {
            "schedule_id absent": [{**good, "schedule_id": None}],
            "another schedule's id": [{**good, "schedule_id": "other"}],
            "tag matches, ordinal does not": [{**good, "planned_ordinal": 999}],
            "identity matches, block does not": [{**good, "block_id": "elsewhere"}],
            "arm position rewritten": [{**good, "arm_position": 2}],
            "permutation rewritten": [{**good, "permutation_index": 5}],
            "a different served world": [{**good, "task_id": "task-somewhere-else"}],
            "another episode contract": [{**good, "episode_contract_digest": "ep2"}],
            "another replay contract": [{**good, "replay_contract_digest": "rp_off"}],
            "the wrong per-turn cap": [{**good, "per_turn_cap": 16000}],
            "different libraries": [{**good, "library_versions": {"verifiers": "0.3.2"}}],
            "duplicated": [good, good],
            "one exact row plus a foreign one": [good, {**good, "tag": "someone_else"}],
        }
        for label, rows in cases.items():
            state, why = status(rows)
            if state != "integrity":
                problems.append(f"{label}: status {state!r} ({why}) — expected an integrity quarantine")
            if RA.cell_is_done(out_path, schedule, cell)[0]:
                problems.append(f"{label}: reported DONE")

        # A PILOT schedule keeps the permissive paths, and only there.
        pilot = _schedule(label="pilot")
        pilot_cell = pilot["cells"][0]
        pilot_path = SA.output_path_for(reviews, pilot_cell["model"], pilot["date_stamp"],
                                        pilot_cell["tag"])
        mb.write_atomic(pilot_path, json.dumps([{"tag": pilot_cell["tag"], "schedule_id": None}]))
        if RA.cell_status(pilot_path, pilot, pilot_cell)[0] != "done":
            problems.append("a pilot row without a schedule_id must still count as run")
    return check("a confirmatory cell is done only on EXACTLY ONE row matching every identity field and "
                 "every sealed contract expectation; a missing schedule_id, a partial match, a duplicate or "
                 "a foreign row is an execution-integrity quarantine, while pilot files keep the old paths",
                 not problems, "\n".join(problems))


def test_force_and_manual_completion_are_refused_for_a_sealed_schedule():
    """Codex T49 §4/Q4 — `--force` re-runs and overwrites an observed cell,
    which is outcome-dependent replacement of a bad draw; `--schedule-complete`
    let an operator declare the panel finished after seeing the results. Both
    are refused for a sealed schedule, and completion is DERIVED instead."""
    import contextlib
    import io
    import tempfile
    problems = []
    schedule = _sealed_schedule()

    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        path = reviews / "schedule_sealed.json"
        path.write_text(json.dumps(schedule, default=str), encoding="utf-8")

        def run(module, argv):
            err, out = io.StringIO(), io.StringIO()
            saved = sys.argv
            sys.argv = argv
            try:
                with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                    code = module.main()
            except SystemExit as exc:                                      # schedule_arms raises
                code = exc.code if isinstance(exc.code, int) else str(exc.code)
            finally:
                sys.argv = saved
            return code, err.getvalue() + out.getvalue()

        # `--dry-run` is a SAFETY BELT, not part of the assertion: correct
        # code refuses `--force` before it ever reaches the dry-run branch,
        # and a regression that did not refuse would still make no provider
        # call from a test process. (It once did, before this belt existed.)
        code, text = run(RA, ["run_arms.py", "--schedule", str(path), "--force", "--dry-run",
                              "--no-probe-capabilities", "--reviews-dir", str(reviews)])
        if code == 0 or "REFUSED" not in text or "--force" not in text:
            problems.append(f"run_arms --force must be refused for a sealed schedule: {code} {text[:200]}")

        code, text = run(AT, ["arm_table.py", "--label", "x", "--schedule", str(path),
                              "--schedule-complete", "--reviews-dir", str(reviews)])
        if code == 0 or "REFUSED" not in text:
            problems.append(f"--schedule-complete must be refused for a sealed schedule: {code} "
                            f"{text[:200]}")

        # `schedule_arms --force` may not replace a SEALED file either.
        code, text = run(SA, ["schedule_arms.py", "--label", "sealed", "--provider", "mistral",
                              "--models", "devstral-2512", "--selectors", "train:1", "--force",
                              "--reviews-dir", str(reviews)])
        if "REFUSED" not in str(text) + str(code):
            problems.append(f"schedule_arms --force must refuse a sealed schedule file: {code} {text[:200]}")
        if json.loads(path.read_text(encoding="utf-8"))["schedule_id"] != schedule["schedule_id"]:
            problems.append("the sealed schedule file was replaced")

        # Completion is DERIVED from the exact cell map, never declared.
        cells = schedule["cells"]
        for cell in cells[:-1]:
            out_path = SA.output_path_for(reviews, cell["model"], schedule["date_stamp"], cell["tag"])
            mb.write_atomic(out_path, json.dumps([_cell_row(schedule, cell)], default=str))
        loaded = AT.load_scheduled_rows(reviews, schedule)
        closure = AT.derive_run_closure(loaded)
        if closure["complete"] or closure["n_unrun"] != 1:
            problems.append(f"an incomplete panel must derive as incomplete: {closure}")
        last = cells[-1]
        mb.write_atomic(SA.output_path_for(reviews, last["model"], schedule["date_stamp"], last["tag"]),
                        json.dumps([_cell_row(schedule, last)], default=str))
        closure = AT.derive_run_closure(AT.load_scheduled_rows(reviews, schedule))
        if not closure["complete"] or closure["n_unrun"]:
            problems.append(f"a full panel must derive as complete: {closure}")
        # An integrity quarantine keeps the panel INCOMPLETE, whatever the count says.
        mb.write_atomic(SA.output_path_for(reviews, last["model"], schedule["date_stamp"], last["tag"]),
                        json.dumps([_cell_row(schedule, last), _cell_row(schedule, last)], default=str))
        closure = AT.derive_run_closure(AT.load_scheduled_rows(reviews, schedule))
        if closure["complete"] or not closure["n_integrity"]:
            problems.append(f"a duplicated cell row must leave the panel incomplete: {closure}")
    return check("--force and --schedule-complete are refused for a sealed schedule, a sealed schedule file "
                 "cannot be replaced, and run closure is derived from the exact cell map",
                 not problems, "\n".join(problems))


def test_one_schedule_level_executor_lock_without_automatic_takeover():
    """Codex T49 §5/Q5 — two executors invalidate the planned temporal order
    even when they never duplicate a cell, so the lock is at the SCHEDULE
    level and there is no automatic stale takeover. `--limit` counts whole
    three-arm blocks, never arbitrary cells."""
    import tempfile
    problems = []
    schedule = _sealed_schedule()

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "schedule_sealed.json"
        path.write_text(json.dumps(schedule, default=str), encoding="utf-8")
        lock = RA.lock_path_for(path)

        first = RA.acquire_schedule_lock(path, "session-A")
        if not first[0]:
            problems.append(f"the first executor could not take the lock: {first[1]}")
        if not (first[3] or {}).get("nonce"):
            problems.append("the acquired lock record carries no nonce to prove ownership with")
        for _ in range(3):
            ok, note, held, ours = RA.acquire_schedule_lock(path, "session-B")
            if ok:
                problems.append("a second executor took the lock while the first held it")
            if "session-A" not in note or "--take-over-lock" not in note:
                problems.append(f"the refusal must name the holder and the deliberate remedy: {note!r}")
            if (held or {}).get("session_id") != "session-A":
                problems.append(f"the refusal must return the holder's record: {held}")
            if ours is not None:
                problems.append("a refused acquisition must return no ownership record")
        # A non-owner may not release it.
        RA.release_schedule_lock(path, "session-B")
        if not lock.exists():
            problems.append("a non-owner released the schedule lock")
        # A LIVE lock is not a corpse: --take-over-lock refuses one younger than
        # TAKEOVER_MIN_LOCK_AGE_SECONDS, because the flag's contract is "I have
        # verified that process is dead" (Codex T51 §3).
        ok, note, _, _ = RA.acquire_schedule_lock(path, "session-C", take_over=True)
        if ok or "younger than" not in note:
            problems.append(f"--take-over-lock must refuse a freshly created lock: {(ok, note)}")
        # Age it, and the explicit takeover is allowed — atomically.
        old = time.time() - 3600
        os.utime(lock, (old, old))
        displaced_bytes = lock.read_bytes()
        ok, note, held, ours = RA.acquire_schedule_lock(path, "session-C", take_over=True)
        if not ok or "TOOK OVER" not in note:
            problems.append(f"--take-over-lock must succeed on a stale lock and say so: {(ok, note)}")
        if json.loads(lock.read_text(encoding="utf-8"))["session_id"] != "session-C":
            problems.append("the takeover did not rewrite the lock holder")
        proved, proof = RA.prove_lock_ownership(path, ours)
        if not proved:
            problems.append(f"the taker could not prove ownership after acquisition: {proof}")
        # The displaced bytes are ARCHIVED, exactly (Codex T51 §3).
        archive = RA.takeover_archive_path_for(path, "session-C")
        if not archive.exists() or archive.read_bytes() != displaced_bytes:
            problems.append("the displaced lock's exact bytes were not archived")
        if RA.takeover_guard_path_for(path).exists():
            problems.append("the takeover guard was not released in a finally")
        # A LATE contender that still holds the OLD bytes must refuse: the
        # corpse it was authorised to take over is not the lock now present.
        if RA.prove_lock_ownership(path, json.loads(displaced_bytes))[0]:
            problems.append("the displaced session can still prove ownership of the lock")
        # A stale-lock nonce mismatch must not let a foreign session release it.
        RA.release_schedule_lock(path, "session-C", {"session_id": "session-C", "nonce": "0" * 32})
        if not lock.exists():
            problems.append("a session with the wrong nonce released the lock")
        RA.release_schedule_lock(path, "session-C", ours)
        if lock.exists():
            problems.append("the owner could not release the lock")

    # ---- THE TWO-CONTENDER TAKEOVER WITNESS (Codex T51 §3) ---------------
    #      Both contenders observe the SAME stale lock and both are told to
    #      take it over. Exactly one may proceed. The old implementation was
    #      `path.write_text(...)`: both would have returned as owners and then
    #      executed different cells concurrently.
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "schedule_race.json"
        path.write_text(json.dumps(schedule, default=str), encoding="utf-8")
        lock = RA.lock_path_for(path)
        RA.acquire_schedule_lock(path, "dead-session")
        old = time.time() - 3600
        os.utime(lock, (old, old))
        results: list = []
        barrier = threading.Barrier(4)

        def contend(name):
            barrier.wait()
            results.append((name, RA.acquire_schedule_lock(path, name, take_over=True)))

        threads = [threading.Thread(target=contend, args=(f"contender-{i}",)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        winners = [name for name, (ok, *_rest) in results if ok]
        if len(winners) != 1:
            problems.append(f"exactly one contender may take over a stale lock, {len(winners)} did: "
                            f"{[(n, r[1][:80]) for n, r in results]}")
        if len(results) != 4:
            problems.append(f"a contender never returned: {len(results)} of 4")
        holder = json.loads(lock.read_text(encoding="utf-8"))
        if winners and holder.get("session_id") != winners[0]:
            problems.append(f"the lock on disk names {holder.get('session_id')}, not the winner "
                            f"{winners[0]}")
        for name, (ok, note, _held, ours) in results:
            if ok and not RA.prove_lock_ownership(path, ours)[0]:
                problems.append(f"the winner {name} cannot prove ownership on disk")
            if not ok and "REFUSED to take over" not in note:
                problems.append(f"a loser must be told a takeover is already under way: {note[:120]!r}")
        if RA.takeover_guard_path_for(path).exists():
            problems.append("the takeover guard survived the race")

    # --limit takes WHOLE blocks.
    pending = [(cell, Path(cell["tag"])) for cell in sorted(schedule["cells"],
                                                            key=lambda c: c["planned_ordinal"])]
    for limit, want_cells in ((1, 3), (2, 6), (None, len(pending))):
        selected, n_blocks = RA.limit_to_whole_blocks(list(pending), limit)
        if len(selected) != want_cells:
            problems.append(f"--limit {limit} selected {len(selected)} cells, expected {want_cells}")
        blocks = {c["block_id"] for c, _ in selected}
        for block in blocks:
            in_block = sum(1 for c, _ in selected if c["block_id"] == block)
            if in_block != 3:
                problems.append(f"--limit {limit} split block {block}: {in_block} of 3 arms")
        if limit is not None and n_blocks != limit:
            problems.append(f"--limit {limit} reported {n_blocks} blocks")
    return check("one schedule-level lock admits exactly one executor, never takes a stale lock over "
                 "automatically, names the holder and the deliberate remedy, refuses a non-owner's release, "
                 "and --limit only ever takes whole three-arm blocks", not problems, "\n".join(problems))


def test_window_ledger_paces_across_cells_and_carries_the_429_evidence():
    """Codex T49 §6/Q7 — every scheduled cell is a fresh subprocess, so
    `PacedClient._last` was always 0 at the one boundary that matters and the
    provider's rolling window was invisible to the classifier. The shared
    ledger fixes both: pacing is measured from the LEDGER's last entry for
    the provider, and the trailing-60 s window is archived on the rejected
    attempt itself."""
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as directory:
        ledger = Path(directory) / "w.jsonl"
        now = 1_000_000.0
        entries = [
            {"t": now - 90, "provider": "mistral", "model": "m", "cell": "old", "status": "ok",
             "billed_input_tokens": 500_000, "billed_output_tokens": 0},      # outside the window
            {"t": now - 40, "provider": "mistral", "model": "m", "cell": "cellA", "status": "ok",
             "billed_input_tokens": 200_000, "billed_output_tokens": 1_000},
            {"t": now - 20, "provider": "mistral", "model": "m", "cell": "cellB", "status": "ok",
             "billed_input_tokens": 50_000, "billed_output_tokens": 500},
            {"t": now - 10, "provider": "mistral", "model": "m", "cell": "cellB", "status": "rate_limited",
             "estimated_request_tokens": 9_000},
            {"t": now - 5, "provider": "mistral", "model": "other", "cell": "cellB", "status": "ok",
             "billed_input_tokens": 999_999},                                 # another model's window
        ]
        for entry in entries:
            mb.window_ledger_append(ledger, entry)
        read_back = mb.window_ledger_read(ledger)
        if len(read_back) != len(entries):
            problems.append(f"the ledger read back {len(read_back)} of {len(entries)} entries")
        # A truncated final line is now a REFUSAL, not a silent drop (Codex
        # T50 §5) — its own witness is
        # test_a_malformed_window_ledger_line_is_unhealthy_until_recovery.
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write('{"t": 1, "provider": "mist')                            # a killed process
        try:
            mb.window_ledger_read(ledger)
            problems.append("a truncated final line must make the ledger UNHEALTHY, not be dropped")
        except mb.WindowLedgerUnhealthy:
            pass
        mb.window_ledger_recover(ledger, reason="witness", session_id="s")
        if len(mb.window_ledger_read(ledger)) != len(entries) + 1:
            problems.append("after recovery the ledger reads back its entries plus the segment boundary")
        if mb.window_ledger_last_time(read_back, "mistral") != now - 5:
            problems.append("pacing must measure from the provider's LAST entry, whichever cell wrote it")
        if mb.window_ledger_last_time(read_back, "gemini") is not None:
            problems.append("another provider's entries must not pace this one")

        snapshot = mb.window_snapshot(read_back, now, "mistral", "m", "cellB",
                                      current_request_estimate=1_500)
        # BILLED is the provider's own number for requests it SERVED; the
        # rejected attempt's 9,000-token estimate is a SEPARATE field and is
        # never added to it (Codex T50 §3).
        if snapshot["billed_tokens_total"] != 200_000 + 1_000 + 50_000 + 500:
            problems.append(f"the billed window total is wrong: {snapshot}")
        if snapshot["billed_tokens_this_cell"] != 50_000 + 500:
            problems.append(f"this cell's billed share is wrong: {snapshot}")
        if snapshot["rejected_estimate_tokens_total"] != 9_000:
            problems.append(f"the rejected estimate must be its own field: {snapshot}")
        if snapshot["accepted_requests_total"] != 2 or snapshot["accepted_requests_this_cell"] != 1:
            problems.append(f"the accepted request counts are wrong: {snapshot}")
        if snapshot["rejected_requests_total"] != 1:
            problems.append(f"the rejected request count is wrong: {snapshot}")
        if snapshot["current_request_estimate_tokens"] != 1_500:
            problems.append("the current request's estimate must be carried, separately, on the snapshot")
        if snapshot["window_kind"] != AT.WINDOW_KIND_PRE_REQUEST:
            problems.append("the pre-request window must be labelled as such")
        # The 90-s-old 500K entry is OUTSIDE the minute and must not count.
        if snapshot["billed_tokens_total"] >= 500_000:
            problems.append("an entry older than the window entered the window")
        # CARRY-OVER: the window is saturated but mostly by the cell before.
        verdict = AT.window_verdict(snapshot, tpm=200_000, rpm=None)
        if verdict != ("ambiguous", "rate_limit_carryover_tokens"):
            problems.append(f"a window this cell did not fill must be carry-over: {verdict}")

    # The rejected request's OWN size is estimated from the payload, since a
    # 429 bills nothing at all.
    estimate = mb.estimate_request_tokens([{"role": "user", "content": "x" * 4_000}])
    if not 900 <= estimate <= 1_200:
        problems.append(f"the chars/4 estimate for a 4,000-character prompt is {estimate}")
    if mb.estimate_request_tokens([{"role": "user", "content": "x" * 40_000}]) <= estimate:
        problems.append("the estimate must grow with the payload")
    # The client threads the ledger, the provider and the cell through.
    import inspect
    params = list(inspect.signature(mb.make_client_cls).parameters)
    for needed in ("window_ledger", "provider", "cell", "session_id"):
        if needed not in params:
            problems.append(f"make_client_cls does not accept {needed}: {params}")
    return check("the shared provider-window ledger survives a truncated write, paces from the provider's "
                 "own last entry across cells, sums only the trailing minute for this (provider, model), "
                 "splits this cell's share from the carry-over, and estimates the size of the request the "
                 "provider refused", not problems, "\n".join(problems))


def test_structured_provider_error_feeds_the_classifier():
    """Codex T49 §6/Q6 — "do not infer a causal arm label from a free-text
    substring when structured status is available". The request log now
    carries the HTTP status, the provider's own error code/type, the redacted
    message and the rate-limit headers, and `failure_text` puts them FIRST."""
    problems = []

    class _Response:
        headers = {"x-ratelimit-limit-tokens": "356250", "retry-after": "12",
                   "authorization": "Bearer sk-abcdefghijklmnop", "content-type": "application/json"}
        status_code = 429

    class _Err(Exception):
        status_code = 429
        code = "rate_limit_exceeded"
        body = {"error": {"code": "rate_limit_exceeded", "type": "requests"}}
        response = _Response()

    fields = mb.provider_error_fields(_Err("429 slow down, key sk-abcdefghijklmnop"))
    if fields["http_status"] != 429 or fields["provider_error_code"] != "rate_limit_exceeded":
        problems.append(f"the structured status was not captured: {fields}")
    if fields["provider_error_type"] != "requests":
        problems.append(f"the provider error type was not captured: {fields}")
    if "sk-abcdefghijklmnop" in json.dumps(fields):
        problems.append("a key-shaped string survived into the archived error")
    headers = fields["rate_limit_headers"] or {}
    if "x-ratelimit-limit-tokens" not in headers or "retry-after" not in headers:
        problems.append(f"the rate-limit headers were not captured: {headers}")
    if "authorization" in headers or "content-type" in headers:
        problems.append(f"only rate-limit headers may be archived: {headers}")

    row = _row(quarantined=True, status="rollout failed", model="mistral-medium-2508",
               requests=[{"status": "error:RateLimitError", "http_status": 429,
                          "provider_error_code": "rate_limit_exceeded",
                          "error_message": "429 Too Many Requests"}])
    text = AT.failure_text(row)
    if "429" not in text or "rate_limit_exceeded" not in text:
        problems.append(f"failure_text does not carry the structured evidence: {text!r}")
    if not text.startswith("429"):
        problems.append("the structured status must come before the free-text prose")
    return check("provider errors are archived with HTTP status, provider code/type, redacted message and "
                 "rate-limit headers only, and the blind classifier reads that structured evidence first",
                 not problems, "\n".join(problems))


def test_primary_contrasts_are_rendered_twice_with_a_sensitivity_comparison():
    """Codex T49 §8/Q10 — `render_table` called `render_strata` twice but
    `render_ratios` ONCE, so the decision-bearing paired contrast and the
    effective-cost ratio never received the promised suspicious-row
    sensitivity. Both are printed twice now, whole triplets are dropped AFTER
    each filter, and the two are COMPARED: blocks lost, and whether any sign
    or ranking changed."""
    problems = []
    arms = ("A", "B1", "B2")
    model = "mistral-medium-2508"
    rows = []
    for selector in ("train:1", "train:12"):
        for arm in arms:
            # B1' delivers only on train:1; on train:12 it fails.
            delivered = not (arm == "B1" and selector == "train:12")
            rows.append(_row(model=model, selector=selector, arm=arm,
                             reward=1.0 if delivered else 0.0, complete=delivered,
                             artifact="BOUND", total_tokens=10_000,
                             billed_input_tokens_all_attempts=10_000,
                             billed_output_tokens_all_attempts=0))
    # Make the train:12 A' cell SUSPICIOUS: excluding it drops that whole
    # block, which removes B1's only failure and flips the contrast.
    for row in rows:
        if row["selector"] == "train:12" and row["arm"] == "A":
            # 5,000 characters at 200 completion tokens is 25 per token,
            # over the floor of 8: SUSPICIOUS, not invalid.
            row["per_turn"] = [{"request_max_tokens": 200, "input_tokens": 10, "output_tokens": 200,
                                "assistant_content_chars": 5_000, "assistant_reasoning_chars": 0,
                                "tool_call_chars": 0}]
    if not AT.is_suspicious([r for r in rows if r["selector"] == "train:12" and r["arm"] == "A"][0]):
        problems.append("the fixture's suspicious row is not suspicious")

    all_stats = AT.ratio_stats(rows, arms, "A")
    clean_stats = AT.ratio_stats([r for r in rows if not AT.is_suspicious(r)], arms, "A")
    key = ("mistral", model, "B1")
    if all_stats[key]["n_blocks"] != 2 or clean_stats[key]["n_blocks"] != 1:
        problems.append(f"blocks: all {all_stats[key]['n_blocks']}, clean {clean_stats[key]['n_blocks']}, "
                        f"expected 2 and 1 — the whole triplet must drop after the filter")
    if all_stats[key]["delta"] == clean_stats[key]["delta"]:
        problems.append("the fixture no longer demonstrates a sensitivity")
    comparison = "\n".join(AT.compare_ratio_stats(all_stats, clean_stats, arms, "A"))
    if "SENSITIVE" not in comparison:
        problems.append(f"a changed sign must be reported as sensitive:\n{comparison}")
    if "| 2 | 1 |" not in comparison:
        problems.append(f"the blocks lost per sensitivity must be printed:\n{comparison}")

    # A DUPLICATE eligible row for one arm of one block used to be resolved by
    # `setdefault` — the first one silently won. Which observation enters the
    # contrast is not a choice this code may make: the block drops, by name.
    duplicated = list(rows) + [_row(model=model, selector="train:1", arm="B2", reward=0.0,
                                    complete=False, artifact="NO_ARTIFACT")]
    blocks_dup, dropped_dup = AT.arm_blocks(duplicated, arms)
    if len(blocks_dup) != len(AT.arm_blocks(rows, arms)[0]) - 1:
        problems.append(f"a duplicated arm row must drop its whole block: {len(blocks_dup)} blocks")
    if not any("duplicate" in reason for reason in dropped_dup):
        problems.append(f"the duplicate drop must be reported by name: {dict(dropped_dup)}")

    text = AT.render_table(rows, "t", [], None, False, False, arms, "A")
    if text.count("Primary contrasts, within (provider, model)") != 2:
        problems.append("the primary contrast is not printed twice")
    if "ALL eligible rows" not in text or "EXCLUDING" not in text:
        problems.append("the two sensitivities are not labelled")
    if text.count("Cross-model operational summary") != 2:
        problems.append("the operational cost columns are not printed twice")
    if "Failure classification" not in text or text.count("Failure classification") != 1:
        problems.append("the failure census must stay a single complete audit table")
    return check("the primary paired contrast and the effective-cost ratio are printed with and without "
                 "suspicious rows, whole triplets dropped after each filter, with the blocks lost and any "
                 "sign/ranking change stated, while the failure census stays single",
                 not problems, "\n".join(problems))


def test_cost_ratio_uncertainty_reports_zero_correct_dominance_and_a_conditional_interval():
    """Codex T49 §9/Q11 — the effective-cost ratio was a bare point estimate.
    It is now bootstrapped over whole triplets exactly as delivery is, and
    the undefined resamples (an arm with zero correct deliveries) are never
    silently dropped: the probability of each arm delivering nothing, the
    probability of dominance and the CONDITIONAL interval are all reported,
    with the raw successes and billed totals behind them."""
    problems = []
    arms = ("A", "B1", "B2")
    # A' delivers everywhere and is cheap; B1' never delivers at all.
    blocks = []
    for selector in ("train:1", "train:12", "train:30", "eval:5"):
        blocks.append({
            "A": _row(selector=selector, arm="A", reward=1.0, complete=True,
                      billed_input_tokens_all_attempts=10_000, billed_output_tokens_all_attempts=0),
            "B1": _row(selector=selector, arm="B1", reward=0.0, complete=False, artifact="NO_ARTIFACT",
                       billed_input_tokens_all_attempts=30_000, billed_output_tokens_all_attempts=0),
            "B2": _row(selector=selector, arm="B2", reward=1.0, complete=True,
                       billed_input_tokens_all_attempts=20_000, billed_output_tokens_all_attempts=0),
        })
    u = AT.cost_ratio_uncertainty(blocks, "B1", "A", resamples=400)
    if u["p_zero_correct"]["B1"] != 1.0:
        problems.append(f"an arm that never delivers must have P(zero-correct)=1: {u['p_zero_correct']}")
    if u["p_zero_correct"]["A"] != 0.0:
        problems.append(f"an arm that always delivers must have P(zero-correct)=0: {u['p_zero_correct']}")
    if u["p_dominates"] != 0.0:
        problems.append(f"a zero-correct arm never dominates: {u['p_dominates']}")
    if u["interval_conditional"] != (None, None) or u["conditional_share"] != 0.0:
        problems.append(f"with no resample in which both delivered, the conditional interval must be "
                        f"undefined and say so: {u['interval_conditional']} {u['conditional_share']}")
    if u["totals"]["B1"]["n_correct"] != 0 or u["totals"]["A"]["billed_tokens"] != 40_000:
        problems.append(f"the raw successes and billed totals must be reported: {u['totals']}")

    # B2' delivers as often as A' and costs twice as much: a finite ratio,
    # a conditional interval covering every resample, and no dominance.
    u2 = AT.cost_ratio_uncertainty(blocks, "B2", "A", resamples=400)
    if abs(u2["point_ratio"] - 2.0) > 1e-9:
        problems.append(f"the point ratio should be 2.00: {u2['point_ratio']}")
    if u2["conditional_share"] != 1.0:
        problems.append(f"every resample has both arms delivering: {u2['conditional_share']}")
    lo, hi = u2["interval_conditional"]
    if lo is None or not (lo <= 2.0 <= hi):
        problems.append(f"the conditional interval must cover the point estimate: {(lo, hi)}")
    if u2["p_dominates"] != 0.0:
        problems.append(f"the costlier arm must not dominate: {u2['p_dominates']}")
    # A' against B2' is the mirror: it dominates on every resample.
    if AT.cost_ratio_uncertainty(blocks, "A", "B2", resamples=400)["p_dominates"] != 1.0:
        problems.append("the cheaper arm must dominate on every resample")
    # It is reachable from the rendered table, not merely computable.
    rendered = "\n".join(AT.render_ratios([r for b in blocks for r in b.values()], arms, "A"))
    for needle in ("P(zero-correct)", "P(arm dominates)", "conditional", "billed"):
        if needle not in rendered:
            problems.append(f"the rendered contrast does not report {needle!r}")
    return check("the cost ratio is bootstrapped over whole triplets and reports P(zero-correct) per arm, "
                 "P(dominance), a labelled conditional interval with the share of resamples it covers, and "
                 "the raw successes and billed totals", not problems, "\n".join(problems))


def test_startup_witness_refuses_on_every_mismatched_field():
    """Codex T49 §14.12 — a sealed contract nobody re-checks is a promise.
    The witness recomputes every field from this checkout, these libraries,
    the package and the active manifest, and names each disagreement. Each
    field is mutated one at a time: a witness that passed a mutated schedule
    would be checking nothing."""
    problems = []
    contract = SA.build_experiment_contract(["A", "B1", "B2"], ["train:1"], 40_000, SA.ANALYSIS_PLAN)
    schedule = _sealed_schedule(selectors=["train:1"], contract=dict(contract))

    clean = SW.witness(schedule, check_task_ids=True, check_tree=False)
    bad = SW.failures(clean)
    if bad:
        problems.append(f"the witness rejects a schedule sealed from this very checkout: "
                        f"{[r['field'] for r in bad]}")
    if len(clean) < 10:
        problems.append(f"the witness checks only {len(clean)} fields")

    # Each mutation names the witness FIELD it must surface as. Under the
    # git-path contract (Codex T50 §1) a wrong `instrument_commit` is no
    # longer an equality mismatch — it surfaces as broken ancestry, which is
    # the property that actually matters.
    mutations = {
        "instrument_commit": ("f" * 40, "instrument_commit_ancestry"),
        "execution_tree_digest": ("0" * 64, "execution_tree_digest"),
        "execution_tree_file_count": (999_999, "execution_tree_file_count"),
        "execution_paths": (["environments/beancount_ledger/tests/**"], "execution_paths"),
        "execution_excludes": (["reviews/**"], "execution_excludes"),
        "instrument_identity_version": (999, "instrument_identity_version"),
        # Codex T51 §1: the interpreter's bytes are sealed fields too, and the
        # witness must name each of them on its own.
        "runtime_environment_digest": ("0" * 64, "runtime_environment_digest"),
        "runtime_environment_file_count": (999_999, "runtime_environment_file_count"),
        "runtime_environment_extra_file_count": (999_999, "runtime_environment_extra_file_count"),
        "runtime_environment_stdlib_file_count": (999_999, "runtime_environment_stdlib_file_count"),
        # C1(b), the adversarial review of the T51 closures: the import
        # environment is a sealed field of its own, so a sys.path entry that
        # nothing covers is NAMED rather than surfacing as an opaque digest
        # mismatch the operator cannot act on.
        "runtime_environment_uncovered_sys_path": (["abs/C:/not/sealed"],
                                                   "runtime_environment_uncovered_sys_path"),
        "runtime_environment_identity_version": (999, "runtime_environment_identity_version"),
        "python_version": ("3.0.0 (not this interpreter)", "python_version"),
        "analysis_plan_sha256": ("0" * 64, "analysis_plan_sha256"),
        "expected_episode_contract_digest": ("0" * 64, "expected_episode_contract_digest"),
        "failure_map_digest": ("0" * 64, "failure_map_digest"),
    }
    for field, (value, expect) in mutations.items():
        mutated = json.loads(json.dumps(contract, default=str))
        mutated[field] = value
        results = SW.witness(_sealed_schedule(selectors=["train:1"], contract=mutated),
                             check_task_ids=False, check_tree=False)
        named = [r["field"] for r in SW.failures(results)]
        if expect not in named:
            problems.append(f"mutating {field} was not caught as {expect!r} (failures: {named})")
    # Nested mutations, one per structure, each naming the witness field it
    # must appear as.
    for field, path_, value, expect in (
            ("arm_contract", ("A", "per_turn_max_tokens"), 999, "arm_contract"),
            ("expected_replay_contract_digest_by_arm", ("B2",), "0" * 64,
             "expected_replay_contract_digest[B2]"),
            ("package_lock", ("replay_libraries",), {"verifiers": "0.0.0"}, "package_lock"),
            ("manifest", ("rotation_id",), "not-the-active-rotation", "manifest.rotation_id"),
            ("expected_public_task_id_by_selector", ("train:1",), "task-elsewhere",
             "public_task_id[train:1]")):
        mutated = json.loads(json.dumps(contract, default=str))
        target = mutated[field]
        for key in path_[:-1]:
            target = target[key]
        target[path_[-1]] = value
        results = SW.witness(_sealed_schedule(selectors=["train:1"], contract=mutated),
                             check_task_ids=True, check_tree=False)
        named = [r["field"] for r in SW.failures(results)]
        if expect not in named:
            problems.append(f"mutating {field}{path_} was not caught as {expect!r} (failures: {named})")
    # A dirty EXECUTION path is itself a refusal (a dirty evidence file is
    # not — that distinction has its own witness,
    # test_instrument_identity_is_a_git_path_contract).
    tree_checked = SW.witness(schedule, check_task_ids=False, check_tree=True)
    if not any(r["field"] == "clean_execution_tree" for r in tree_checked):
        problems.append("the witness does not check the working tree over the execution paths at all")
    if not any(r["field"] == "runtime_head" for r in tree_checked):
        problems.append("the witness does not record the RUNTIME head separately from the sealed commit")
    # An unsealed schedule has nothing to witness, and says so by returning
    # nothing rather than by inventing expectations.
    if SW.witness(_schedule(label="pilot")):
        problems.append("a pilot schedule must produce no sealed-contract checks")
    return check("the startup witness recomputes every sealed field from this checkout, the package and the "
                 "active manifest, names each mismatch, and catches a one-field mutation of each",
                 not problems, "\n".join(problems))


def test_capability_incompatibility_excludes_the_whole_configuration():
    """Codex T49 §7 — the table classified capability rows individually and
    dropped only their triplets, so a client/provider incompatibility became
    an arm-shaped hole in the panel. A configuration that cannot carry one
    arm's replayed payload leaves the comparison WHOLE, before any contrast."""
    problems = []
    arms = ("A", "B1", "B2")
    rows = []
    for model in ("mistral-medium-2508", "devstral-2512"):
        for selector in ("train:1", "train:12"):
            for arm in arms:
                rows.append(_row(model=model, selector=selector, arm=arm, reward=1.0, complete=True))
    # ONE cell of devstral is a replayed-field rejection: 422 extra_forbidden.
    rows = [r for r in rows
            if not (r["model"] == "devstral-2512" and r["selector"] == "train:1" and r["arm"] == "B2")]
    rows.append(_row(model="devstral-2512", selector="train:1", arm="B2", quarantined=True,
                     status="422 extra_forbidden messages.3.assistant.reasoning_content"))

    offending = AT.capability_incompatible_configurations(rows)
    if list(offending) != [("mistral", "devstral-2512")]:
        problems.append(f"the offending configuration was not identified whole: {list(offending)}")
    text = AT.render_table(rows, "t", [], None, False, False, arms, "A")
    if "excluded WHOLE for capability incompatibility" not in text:
        problems.append("the exclusion is not reported")
    contrast_section = text.split("Primary contrasts")[1] if "Primary contrasts" in text else ""
    if "devstral-2512" in contrast_section:
        problems.append("the incompatible configuration still appears in the primary contrast")
    if "mistral-medium-2508" not in contrast_section:
        problems.append("the compatible configuration was excluded too")
    return check("a capability incompatibility excludes its whole (provider, model) configuration from every "
                 "contrast, by name, instead of dropping the individual blocks that happened to fail",
                 not problems, "\n".join(problems))


def test_executed_order_census_is_reconstructed_and_disagrees_when_it_should():
    """Codex T49 §5 — `render_census` used the SCHEDULED cells whenever a
    schedule was present, so it never proved the executed order followed the
    plan. The actual temporal census is reconstructed from the rows' own
    timestamps and session ids, and a block run split or out of order is
    flagged."""
    problems = []
    schedule = _sealed_schedule(selectors=["train:1"])
    first_block = schedule["cells"][0]["block_id"]
    cells = sorted([c for c in schedule["cells"] if c["block_id"] == first_block],
                   key=lambda c: c["planned_ordinal"])
    ordered = [_cell_row(schedule, cell, session_id="s1", actual_ordinal=i + 1,
                         started_at=f"2026-08-31T10:0{i}:00")
               for i, cell in enumerate(cells)]
    if AT.order_integrity(ordered):
        problems.append(f"a block executed in the planned order must be clean: {AT.order_integrity(ordered)}")
    executed = AT.executed_cells(ordered)
    if [c["arm"] for c in executed] != [c["arm"] for c in cells]:
        problems.append("the reconstructed order does not match the executed order")

    # The same rows, executed in REVERSE, in two sessions, non-consecutively.
    scrambled = [_cell_row(schedule, cell, session_id="s1" if i else "s2",
                           actual_ordinal=(i + 1) * 7, started_at=f"2026-08-31T10:0{2 - i}:00")
                 for i, cell in enumerate(cells)]
    findings = AT.order_integrity(scrambled)
    if not any("SPLIT" in f for f in findings):
        problems.append(f"a block split across sessions must be flagged: {findings}")
    if not any("OUT OF" in f for f in findings):
        problems.append(f"a block executed out of the scheduled arm order must be flagged: {findings}")
    reordered = AT.executed_cells(scrambled)
    if [c["arm"] for c in reordered] == [c["arm"] for c in cells]:
        problems.append("the executed census repeated the scheduled order instead of the actual one")
    text = AT.render_table(scrambled, "t", [], schedule, False, False, ("A", "B1", "B2"), "A")
    if "as EXECUTED" not in text or "Executed-order integrity" not in text:
        problems.append("the table does not render both censuses")
    return check("the actual temporal census is reconstructed from timestamps and session ids, printed "
                 "beside the scheduled one, and a block executed split or out of order is named",
                 not problems, "\n".join(problems))


def test_a_numeric_class_only_ever_matches_a_status_field_never_a_substring():
    """F1 (adversarial review) — `structured_error_text` folded the archived
    RATE-LIMIT HEADER VALUES into the blob the fixed map scanned, and the map
    carried bare numeric needles. Two of the four panel models publish a TPM
    containing "500", and `retry-after` is a small integer that can BE 413 or
    503, so:

        429 + `ratelimitbysize-limit: 937500` -> exogenous/server_error
        429 + `retry-after: 413`              -> arm_induced/request_too_large
        a transient 500 EARLIER in the row    -> outranked the fatal 429

    Both directions are decision-bearing: `exogenous` drops the row AND its
    whole triplet from the paired contrast, while a fabricated `arm_induced`
    charges an arm with a failure it did not cause.

    The fix is structural: a numeric class matches only an archived
    `http_status`; classification reads the FATAL (last non-ok) attempt;
    header VALUES never enter any scanned text; free text is a fallback and
    carries no numbers at all."""
    problems = []
    model = "ministral-14b-2512"                            # published TPM 937,500
    tpm, rpm = AT.tpm_limit("mistral", model), AT.rpm_limit("mistral", model)

    def window(mine, total, req_total=6, req_mine=6):
        return _window(billed=total, billed_mine=mine, accepted=req_total, accepted_mine=req_mine)

    def attempt(headers=None, status="rate_limited", http=429, msg="429 Too Many Requests",
                code="rate_limit_exceeded", typ="tokens", win=None):
        entry = {"status": status, "http_status": http, "provider_error_code": code,
                 "provider_error_type": typ, "error_class": "RateLimitError", "error_message": msg,
                 "rate_limit_headers": headers, "estimated_request_tokens": 150_000}
        if win is not None:
            entry["provider_window"] = win
        return entry

    def rl_row(requests):
        return _row(model=model, provider="mistral", arm="B1", quarantined=True,
                    status="rollout failed", min_interval=6.0, requests=requests)

    saturating = window(900_000, 950_000)                   # this cell sent 900K of 950K
    carryover = window(50_000, 950_000)                     # the cell BEFORE sent it

    # The verifier's three cases, verbatim in shape.
    cases = [
        ("429 + the provider's own limit header (937500 contains '500')",
         rl_row([attempt(headers={"ratelimitbysize-limit": "937500", "ratelimitbysize-remaining": "0"},
                         win=saturating)]),
         ("arm_induced", "rate_limit_window_saturated_tokens")),
        ("429 + retry-after: 413",
         rl_row([attempt(headers={"retry-after": "413"}, win=carryover)]),
         ("ambiguous", "rate_limit_carryover_tokens")),
        ("a transient 500 EARLIER, the FATAL failure is the 429",
         rl_row([attempt(status="error:APIStatusError", http=500, msg="500 Internal Server Error",
                         code=None, typ=None),
                 attempt(win=saturating)]),
         ("arm_induced", "rate_limit_window_saturated_tokens")),
    ]
    for label, row, want in cases:
        got = AT.classify_row(row)
        if got != want:
            problems.append(f"{label}: {got}, expected {want}")

    # FATAL-LAST-ATTEMPT PRECEDENCE, the other way round: a 429 the pacing
    # loop survived, followed by a fatal 413, is the 413's failure.
    mixed = rl_row([attempt(win=saturating),
                    attempt(status="error:APIStatusError", http=413, code=None, typ=None,
                            msg="request entity too large")])
    if AT.classify_row(mixed) != ("arm_induced", "request_too_large"):
        problems.append(f"the LAST non-ok attempt must decide: {AT.classify_row(mixed)}")
    if AT.fatal_attempt(mixed) is not mixed["requests"][-1]:
        problems.append("fatal_attempt did not pick the last non-ok attempt")
    # An `ok` attempt after the failure does not change which one was fatal.
    trailing_ok = rl_row([attempt(win=saturating), {"status": "ok", "billed_input_tokens": 10}])
    if AT.classify_row(trailing_ok) != ("arm_induced", "rate_limit_window_saturated_tokens"):
        problems.append(f"a trailing ok attempt changed the verdict: {AT.classify_row(trailing_ok)}")

    # HEADER VALUES ARE NOT SCANNED, and no numeric needle survives anywhere.
    blob = AT.failure_text(cases[1][1])
    for leaked in ("413", "937500", "retry-after"):
        if leaked in blob:
            problems.append(f"the scanned text still carries header material: {leaked!r} in {blob!r}")
    if AT.rate_limit_header_keys(cases[0][1]) != ["ratelimitbysize-limit", "ratelimitbysize-remaining"]:
        problems.append("the header KEYS must stay available as evidence")
    for _bucket, rule, needles in AT.ERROR_CLASS_RULES + AT.CAPABILITY_RULES:
        for needle in needles:
            if any(ch.isdigit() for ch in needle):
                problems.append(f"a numeric needle survives in the text map: {rule}/{needle!r}")
    # A numeric class is still reachable — from the STATUS field only.
    for status_code, want in sorted(AT.HTTP_STATUS_RULES.items()):
        if AT.classify_error("", http_status=status_code) != want:
            problems.append(f"http {status_code} must classify as {want}")
        # ... and the same digits in text classify as nothing.
        if AT.classify_error(f"the limit is {status_code}0000 tokens")[0] != "ambiguous":
            problems.append(f"the digits {status_code} in free text must not reach the numeric class")
    # Capability still outranks a status class (the pre-registered order).
    cap = rl_row([attempt(status="error:APIStatusError", http=500, code=None, typ=None,
                          msg="422 extra_forbidden messages.3.assistant.reasoning_content")])
    if AT.classify_row(cap) != ("capability_incompatible", "replayed_field_rejected"):
        problems.append(f"capability must outrank the status class: {AT.classify_row(cap)}")
    return check("a numeric failure class is decided ONLY by an archived http_status, the FATAL (last "
                 "non-ok) attempt is the evidence, rate-limit header VALUES never enter a scanned text, "
                 "and capability still outranks every status class",
                 not problems, "\n".join(problems))


def test_the_writer_refuses_to_overwrite_an_observed_scheduled_cell():
    """F2 — `run_arms` refuses `--force`, but nothing stopped a hand-typed
    `measure_budget.py --tag confirm1v2_B1p_train1_r1 --stamp-date ...` from
    writing the same filename and replacing an observed cell with a fresh
    draw, atomically and undetectably. The guarantee belongs in the WRITER,
    where every caller passes through it."""
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory) / "budget_devstral-2512_2026-08-31_confirm1v2_B1p_train1_r1.json"

        # Nothing there yet: any write is fine.
        mb.refuse_scheduled_overwrite(out, [{"schedule_id": "sched-1"}])
        mb.write_atomic(out, json.dumps([{"schedule_id": "sched-1", "reward": 1.0}]))

        # The file now holds a SCHEDULED observation. Every re-write refuses,
        # whether or not the new run claims a schedule.
        for label, rows in (("same schedule", [{"schedule_id": "sched-1"}]),
                            ("another schedule", [{"schedule_id": "sched-2"}]),
                            ("no schedule at all", [{"reward": 0.0}])):
            try:
                mb.refuse_scheduled_overwrite(out, rows)
                problems.append(f"{label}: the overwrite was allowed")
            except SystemExit as exc:
                if "REFUSED" not in str(exc) or out.name not in str(exc):
                    problems.append(f"{label}: the refusal must name the file: {exc}")
        if json.loads(out.read_text(encoding="utf-8"))[0]["reward"] != 1.0:
            problems.append("the observed row was modified")

        # An UNREADABLE existing file is not "absent" either.
        corrupt = Path(directory) / "budget_x_2026-08-31_t.json"
        corrupt.write_text("{ truncated", encoding="utf-8")
        try:
            mb.refuse_scheduled_overwrite(corrupt, [{"schedule_id": "sched-1"}])
            problems.append("an unreadable file did not stop a scheduled write")
        except SystemExit:
            pass

        # A PLAIN PILOT overwrite (neither side scheduled) still works.
        pilot = Path(directory) / "budget_x_2026-08-31_Ap_train1.json"
        mb.write_atomic(pilot, json.dumps([{"reward": 0.0}]))
        try:
            mb.refuse_scheduled_overwrite(pilot, [{"reward": 1.0}])
        except SystemExit as exc:
            problems.append(f"a pilot re-run must still be allowed: {exc}")

        # No flag overrides it: the refusal takes no options at all.
        import inspect
        if list(inspect.signature(mb.refuse_scheduled_overwrite).parameters) != ["path", "rows"]:
            problems.append("refuse_scheduled_overwrite grew an override parameter")

    # And the stamper refuses a SEALED schedule's rows whatever the flag says.
    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        sealed = _sealed_schedule(label="sealed")
        (reviews / "schedule_sealed.json").write_text(json.dumps(sealed, default=str), encoding="utf-8")
        pilot_schedule = _schedule(label="pilotsched")
        (reviews / "schedule_pilotsched.json").write_text(json.dumps(pilot_schedule, default=str),
                                                          encoding="utf-8")
        import stamp_contract_digest as SC
        sealed_ids, unknown = SC.sealed_schedule_ids([sealed["schedule_id"]], reviews)
        if sealed_ids != [sealed["schedule_id"]] or unknown:
            problems.append(f"a sealed schedule id must be recognised: {sealed_ids} {unknown}")
        pilot_ids, unknown = SC.sealed_schedule_ids([pilot_schedule["schedule_id"]], reviews)
        if pilot_ids or unknown:
            problems.append(f"a pilot schedule id is not sealed: {pilot_ids} {unknown}")
        _, unknown = SC.sealed_schedule_ids(["an-id-with-no-file"], reviews)
        if unknown != ["an-id-with-no-file"]:
            problems.append("an id whose schedule file is absent must be UNLOCATABLE, not assumed safe")
    return check("the writer itself refuses to replace a row file that holds — or would hold — a scheduled "
                 "observation, with no flag to override it, while a plain pilot overwrite still works; and "
                 "the stamper refuses a sealed schedule's rows and any id it cannot locate",
                 not problems, "\n".join(problems))


def test_the_window_ledger_fails_loud_and_marks_the_row():
    """F5 — the append swallowed `OSError` and the lock proceeded UNLOCKED
    after a timeout. Both hid the loss of the only evidence behind pacing and
    every 429 classification: the run continued, and afterwards nothing on
    the row distinguished "the window was quiet" from "the window was never
    recorded"."""
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as directory:
        ledger = Path(directory) / "sub" / "w.jsonl"
        mb.window_ledger_append(ledger, {"t": 1.0, "provider": "mistral", "status": "ok"})
        if len(mb.window_ledger_read(ledger)) != 1:
            problems.append("a healthy append did not land")
        mb.window_ledger_precheck(ledger)                  # healthy: must not raise

        # A HELD lock: the single-executor design makes this a fault, and the
        # request must be refused rather than made unpaced.
        lock = Path(str(ledger) + ".lock")
        lock.write_text("held by someone", encoding="utf-8")
        saved = mb._LEDGER_LOCK_TIMEOUT
        mb._LEDGER_LOCK_TIMEOUT = 0.05
        try:
            for label, call in (("precheck", lambda: mb.window_ledger_precheck(ledger)),
                                ("append", lambda: mb.window_ledger_append(ledger, {"t": 2.0}))):
                try:
                    call()
                    problems.append(f"{label}: a held lock did not raise — the old code proceeded "
                                    f"unlocked")
                except mb.WindowLedgerUnavailable as exc:
                    if "lock" not in str(exc).lower():
                        problems.append(f"{label}: the refusal must name the lock: {exc}")
        finally:
            mb._LEDGER_LOCK_TIMEOUT = saved
            lock.unlink()

        # A directory that cannot be created at all.
        blocked = Path(directory) / "afile"
        blocked.write_text("x", encoding="utf-8")
        try:
            mb.window_ledger_precheck(blocked / "under" / "w.jsonl")
            problems.append("an unwritable ledger path did not raise")
        except mb.WindowLedgerUnavailable:
            pass

    # The GAP is on the row, and re-derives as a SUSPICION (never INVALID:
    # a bookkeeping failure does not touch the token accounting).
    gap_row = _row(requests=[{"turn": 1, "attempt": 1, "status": "ok", "seconds": 1.0,
                              "attempt_id": "a1", "rollout_id": "r1",
                              "ledger_write_failed": "disk full"}])
    if mb.row_suspicion(gap_row) != "window_ledger_gap":
        problems.append(f"a row with a lost ledger line must be suspicious: {mb.row_suspicion(gap_row)}")
    if mb.validate_row(gap_row)[0] != "VALID":
        problems.append(f"a ledger gap must not invalidate the row: {mb.validate_row(gap_row)}")
    if not AT.is_suspicious(gap_row):
        problems.append("arm_table must see the gap through its own re-derivation")
    if mb.row_suspicion(_row()) is not None:
        problems.append("a healthy row must not be suspicious")
    if "window_ledger_gap" not in mb.ALL_BUDGET_SUSPICION_CODES:
        problems.append("the new code is not in the closed suspicion set")
    return check("a window-ledger append that fails and a lock that cannot be taken both RAISE, the "
                 "pre-request check refuses before anything is spent, and a lost line is stamped on the "
                 "attempt so the row re-derives as window_ledger_gap — suspicious, not invalid",
                 not problems, "\n".join(problems))


def test_a_corrupt_lock_or_claim_is_owned_by_someone_unknown():
    """F4 — the ownership check read the file with a bare `except: held = {}`,
    and `{}.get("session_id")` is `None`, which passed
    `not in (None, session_id)`. So a corrupt lock could be unlinked by any
    process, including one that never held it. A file that EXISTS is a claim
    by someone; failing to parse it is a reason to refuse."""
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as directory:
        schedule_path = Path(directory) / "schedule_x.json"
        schedule_path.write_text("{}", encoding="utf-8")
        lock = RA.lock_path_for(schedule_path)

        for label, content in (("truncated JSON", '{"session_id": "s1"'),
                               ("not JSON at all", "garbage"),
                               ("JSON without a session", '{"pid": 4}'),
                               ("a JSON list", '["s1"]')):
            lock.write_text(content, encoding="utf-8")
            held, state = RA.lock_holder(lock)
            if state != "unknown":
                problems.append(f"{label}: lock_holder said {state!r}, expected 'unknown'")
            RA.release_schedule_lock(schedule_path, "some-session")
            if not lock.exists():
                problems.append(f"{label}: an unreadable lock was unlinked by a non-owner")
            ok, note, _, _ = RA.acquire_schedule_lock(schedule_path, "s2")
            if ok or "UNREADABLE" not in note:
                problems.append(f"{label}: acquire must refuse and say the holder is unknown: {note!r}")
            # Only the deliberate act clears it — and only once the lock is old
            # enough to be called a corpse (Codex T51 §3).
            ok, note, _, _ = RA.acquire_schedule_lock(schedule_path, "s2", take_over=True)
            if ok or "younger than" not in note:
                problems.append(f"{label}: a fresh unreadable lock must not be taken over: {note!r}")
            old = time.time() - 3600
            os.utime(lock, (old, old))
            ok, note, _, ours = RA.acquire_schedule_lock(schedule_path, "s2", take_over=True)
            if not ok:
                problems.append(f"{label}: --take-over-lock could not clear a stale unreadable lock: "
                                f"{note!r}")
            elif not RA.prove_lock_ownership(schedule_path, ours)[0]:
                problems.append(f"{label}: the taker could not prove ownership afterwards")
            lock.unlink()
            RA.takeover_archive_path_for(schedule_path, "s2").unlink(missing_ok=True)

        # The same for a per-cell claim, and a release with NO session id
        # cannot prove ownership, so it refuses.
        out_path = Path(directory) / "budget_m_2026-08-31_t.json"
        claim = out_path.with_name(out_path.name + ".claim")
        cell = {"planned_ordinal": 1, "tag": "t"}
        RA.claim_cell(out_path, "owner", cell, 3600)
        RA.release_cell(out_path)                       # no session: must NOT release
        if not claim.exists():
            problems.append("release_cell with no session id released another process's claim")
        claim.write_text("corrupt", encoding="utf-8")
        RA.release_cell(out_path, "owner")
        if not claim.exists():
            problems.append("an unreadable claim was unlinked by a session that cannot prove ownership")
        claim.unlink()
        RA.claim_cell(out_path, "owner", cell, 3600)
        RA.release_cell(out_path, "owner")
        if claim.exists():
            problems.append("the real owner could not release its own claim")
    return check("an unreadable lock or claim file is treated as held by an UNKNOWN session: it is never "
                 "unlinked by a release, acquiring says so by name, only --take-over-lock clears it, and a "
                 "release without a session id refuses", not problems, "\n".join(problems))


def test_run_closure_integrity_cells_are_a_third_state_and_the_table_exits_nonzero():
    """F6 — an execution-integrity cell was counted BOTH as unrun and as a
    quarantine, so the three numbers did not add up to the panel; and
    `arm_table` exited 0 with unresolved quarantines, so a caller gating on
    the exit code saw a clean run."""
    import contextlib
    import io
    import tempfile
    problems = []
    schedule = _sealed_schedule()
    cells = schedule["cells"]
    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        (reviews / "schedule_sealed.json").write_text(json.dumps(schedule, default=str), encoding="utf-8")
        # One good cell, one duplicated (integrity), the rest unrun.
        good = cells[0]
        mb.write_atomic(SA.output_path_for(reviews, good["model"], schedule["date_stamp"], good["tag"]),
                        json.dumps([_cell_row(schedule, good)], default=str))
        bad = cells[1]
        mb.write_atomic(SA.output_path_for(reviews, bad["model"], schedule["date_stamp"], bad["tag"]),
                        json.dumps([_cell_row(schedule, bad), _cell_row(schedule, bad)], default=str))
        loaded = AT.load_scheduled_rows(reviews, schedule)
        closure = AT.derive_run_closure(loaded)
        if closure["n_ran"] != 1 or closure["n_integrity"] != 1:
            problems.append(f"ran/integrity: {closure['n_ran']}/{closure['n_integrity']}, expected 1/1")
        if closure["n_unrun"] != closure["n_cells"] - 2:
            problems.append(f"an integrity cell must be NEITHER run nor unrun: {closure}")
        if closure["accounted"] != closure["n_cells"]:
            problems.append(f"the three states must account for every cell exactly once: {closure}")
        if closure["complete"]:
            problems.append("a panel with an integrity quarantine is not complete")

        err, out = io.StringIO(), io.StringIO()
        saved = sys.argv
        sys.argv = ["arm_table.py", "--label", "x", "--schedule", str(reviews / "schedule_sealed.json"),
                    "--reviews-dir", str(reviews)]
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                code = AT.main()
        finally:
            sys.argv = saved
        if code != 4:
            problems.append(f"arm_table must exit 4 with an unresolved integrity quarantine, got {code}")
        if "EXIT 4" not in err.getvalue():
            problems.append("the nonzero exit must say why on stderr")
        if not (reviews / "arms_x.md").is_file():
            problems.append("the table must still be WRITTEN — suppressing it would hide the quarantines")
        if "EXECUTION INTEGRITY REFUSALS" not in (reviews / "arms_x.md").read_text(encoding="utf-8"):
            problems.append("the written table does not list the quarantines")

    # A timestampless row is MARKED as unordered rather than silently sorted.
    block = [c for c in cells if c["block_id"] == cells[0]["block_id"]]
    undated = [_cell_row(schedule, c, session_id="s1", actual_ordinal=i + 1) for i, c in enumerate(block)]
    findings = AT.order_integrity(undated)
    if not any("UNORDERED" in f for f in findings):
        problems.append(f"rows with no started_at must be marked unordered: {findings}")
    return check("an execution-integrity cell is a third state that is neither run nor unrun, the three "
                 "states account for every scheduled cell exactly once, arm_table exits 4 while still "
                 "writing the table, and a timestampless block is marked UNORDERED",
                 not problems, "\n".join(problems))


def test_an_inconclusive_capability_probe_refuses_the_configuration():
    """F6 — an INCONCLUSIVE probe (endpoint unreachable, or the model would
    not call a tool) established nothing, and the executor admitted the
    configuration anyway. Starting untested is exactly what §7 forbids: it
    must be re-run, or admitted by an explicit recorded operator act."""
    problems = []
    schedule = _sealed_schedule()
    calls = []

    def fake_probe(provider, model, policies, **kwargs):
        calls.append((provider, model, tuple(policies)))
        if model == "devstral-2512":
            return {"provider": provider, "model": model, "admissible": True, "conclusive": True,
                    "policies": {}}
        if model == "ministral-14b-2512":
            return {"provider": provider, "model": model, "admissible": True, "conclusive": False,
                    "policies": {"reasoning_replay=on": {"ok": None, "stage": "no_tool_call"}}}
        return {"provider": provider, "model": model, "admissible": False, "conclusive": True,
                "policies": {"reasoning_replay=on": {"ok": False, "stage": "replay_request"}}}

    results = RA.run_capability_probes(schedule, [("mistral", "devstral-2512"),
                                                  ("mistral", "ministral-14b-2512"),
                                                  ("mistral", "ministral-8b-2512")], probe_fn=fake_probe)
    if len(calls) != 3:
        problems.append(f"one probe per configuration: {calls}")
    for _p, _m, policies in calls:
        if set(policies) != {True, False}:
            problems.append(f"every replay policy the schedule uses must be probed: {policies}")
    admitted = {key: RA.probe_admits(r)[0] for key, r in results.items()}
    if admitted[("mistral", "ministral-14b-2512")]:
        problems.append("an inconclusive probe must not admit the configuration by default")
    if not RA.probe_admits(results[("mistral", "ministral-14b-2512")])[1]:
        problems.append("the inconclusive verdict must be reported as such")
    if not admitted[("mistral", "devstral-2512")]:
        problems.append("a conclusive, passing probe must admit")
    if admitted[("mistral", "ministral-8b-2512")]:
        problems.append("a failing probe must refuse")
    # The override is EXPLICIT: only the flag admits an inconclusive probe,
    # and it can never rescue a probe that actually failed.
    if not RA.probe_admits(results[("mistral", "ministral-14b-2512")], True)[0]:
        problems.append("--accept-inconclusive-probe must be able to admit deliberately")
    if RA.probe_admits(results[("mistral", "ministral-8b-2512")], True)[0]:
        problems.append("the override must never admit a probe that FAILED")
    source = Path(RA.__file__).read_text(encoding="utf-8")
    for needed in ("--accept-inconclusive-probe", '"accept_inconclusive_probe"'):
        if needed not in source:
            problems.append(f"run_arms does not carry {needed}")
    return check("an inconclusive capability probe REFUSES its configuration rather than starting it "
                 "untested, every replay policy is probed once per configuration, and the deliberate "
                 "override is recorded in the execution journal",
                 not problems, "\n".join(problems))


def test_liveness_witness_envelopes_are_the_packages_own_constants():
    """Codex T49 §13.6/Q14 — the deterministic witness must actually FAIL on
    each envelope it claims to check, and must compare against the package's
    own constants rather than numbers repeated in the test."""
    problems = []
    import liveness_witness as LW

    good = {"selector": "train:1", "task_id": "t", "reward": 1.0, "stop": "piv_submitted", "error": None,
            "phase": env_mod.EpisodePhase.TERMINAL.value, "submitted": True, "artifact": "BOUND",
            "artifact_reason": None, "artifact_stored_bytes_digest": "sd",
            "artifact_logical_text_digest": "ld", "episode_contract_digest": "ep", "turns": 4,
            "tools": ["list_files", "read_file", "write_ledger", "submit"], "output_tokens": 100,
            "observation_bytes": 12_000, "complete_reads": 1, "golden_bytes": 9_000, "score": 1.0}
    if LW.check_envelopes(good, env_mod):
        problems.append(f"the conforming observation was rejected: {LW.check_envelopes(good, env_mod)}")

    violations = {
        "reward": {"reward": 0.9},
        "phase": {"phase": "ACTIVE_CANDIDATE", "submitted": False},
        "stop": {"stop": "max_turns_reached"},
        "artifact": {"artifact": "ARTIFACT_MISMATCH"},
        "digest": {"artifact_logical_text_digest": None},
        "tools": {"tools": ["write_ledger", "submit"]},
        "turns": {"turns": env_mod.MAX_TURNS + 1},
        "output ceiling": {"output_tokens": env_mod.MAX_EPISODE_OUTPUT_TOKENS + 1},
        "observation budget": {"observation_bytes": env_mod.MAX_EPISODE_OBSERVATION_BYTES + 1},
        "write cap": {"golden_bytes": env_mod.MAX_WRITE_BYTES + 1},
        "error": {"error": "InfraError"},
    }
    for label, override in violations.items():
        if not LW.check_envelopes({**good, **override}, env_mod):
            problems.append(f"a violated {label} envelope was not caught")
    # Determinism is a comparison of the digests, not of the workspace.
    if LW.compare_runs(good, {**good, "artifact_logical_text_digest": "other"}) == []:
        problems.append("two runs with different artifact digests must not compare equal")
    if LW.compare_runs(good, {**good, "workspace": "/somewhere/else"}) != []:
        problems.append("a different workspace path is not a determinism failure")
    if set(LW.PANEL_SELECTORS) != {"train:1", "train:12", "train:30", "eval:5", "train:3:hard",
                                   "train:107:hard"}:
        problems.append(f"the witness panel is not the confirm1 panel: {LW.PANEL_SELECTORS}")
    return check("the liveness witness checks reward, submission, artifact digests, the tool sequence and "
                 "every declared envelope against the package's own constants, and each violation is caught",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# Codex T50 (HOLD): the seven defects, each with its own mutation witness.
# Reverting any one of the fixes must fail the witness that names it.
# --------------------------------------------------------------------------

def _git_repo(directory: Path) -> callable:
    """A throwaway git repository laid out like this one, with a `run(*args)`
    helper. Identity is passed per-command so the witness does not depend on
    the machine's git configuration."""
    import subprocess

    def run(*args, check=True):
        result = subprocess.run(["git", "-c", "user.name=witness", "-c", "user.email=w@example.invalid",
                                 *args], cwd=str(directory), capture_output=True, text=True)
        if check and result.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    run("init", "-q")
    return run


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_instrument_identity_is_the_bytes_on_disk_not_gits_index():
    """Codex T50 §1 — the DETERMINISTIC BLOCKER — and the adversarial review
    of the first fix, attack 1(h).

    T50: `startup_witness` compared `git rev-parse HEAD` to the sealed
    `instrument_commit` for exact equality, while the sealed schedule is itself
    stored in the repository. Committing it MOVES HEAD, so the schedule could
    never be executed from the commit it names — Codex found exactly that, with
    the diff confined to `DURUM.md`, `GECE.md`, `design_chat/to_codex.md` and
    the schedule file.

    The review then broke the first replacement, which asked git three
    questions (`status`, `diff`, `ls-tree`). All three answer about the INDEX,
    not about the bytes the interpreter imports, and three attacks passed the
    witness fully green:

      (A) `git update-index --assume-unchanged <file>`, then edit it;
      (B) MODULE SHADOWING: a new `.py` beside the package, outside the three
          sealed subtrees but `sys.path[0]` for every cell process;
      (C) a file inside `tests/` hidden by a `.gitignore` line committed on an
          EVIDENCE path.

    So the identity is now the bytes ON DISK over the whole package directory
    minus a named exclusion list, with the relative file SET in the digest
    material. Git stays as secondary evidence. Every case below is witnessed,
    and for (A) and (C) the git rows are asserted GREEN — which is the point:
    they are exactly the rows that used to carry the identity."""
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        run = _git_repo(root)
        instrument = root / "environments" / "beancount_ledger"
        _write(instrument / "tests" / "measure_budget.py", "VERSION = 1\n")
        _write(instrument / "beancount_ledger" / "__init__.py", "x = 1\n")
        _write(instrument / "pyproject.toml", "[project]\nname='x'\n")
        _write(instrument / "reviews" / "notes.md", "evidence\n")           # EXCLUDED from the walk
        _write(root / "design_chat" / "to_codex.md", "turn 50\n")           # outside the execution root
        _write(root / "DURUM.md", "state\n")                                # outside the execution root
        _write(root / ".gitignore", "*.pyc\n")                              # an EVIDENCE path
        run("add", "-A")
        run("commit", "-qm", "instrument")
        sealed_commit = run("rev-parse", "HEAD")
        sealed_tree = SA.execution_tree_manifest(root)
        sealed_digest = SA.manifest_digest(sealed_tree)
        sealed_count = len(sealed_tree["files"])
        if sealed_count != 3:
            problems.append(f"the walk must see exactly the 3 non-excluded files, saw {sealed_count}: "
                            f"{[f for f, _ in sealed_tree['files']]}")
        if any(f.startswith("reviews/") for f, _ in sealed_tree["files"]):
            problems.append("the evidence directory must be excluded from the instrument identity")

        # The runtime-environment rows are checked against the REAL interpreter
        # (Codex T51 §1) — this witness is about the repository half of the
        # identity, so the environment half is sealed at its true value and
        # must stay green throughout. Its own mutation witness is
        # `test_the_runtime_environment_is_sealed_as_bytes_not_versions`.
        real_environment = SA.runtime_environment_manifest()

        def schedule_for(commit=None, digest=None, count=None, paths=None, excludes=None):
            return {"experiment_contract": {
                "instrument_commit": sealed_commit if commit is None else commit,
                "execution_paths": list(SA.EXECUTION_PATHS) if paths is None else paths,
                "execution_excludes": list(SA.EXECUTION_EXCLUDES) if excludes is None else excludes,
                "execution_tree_digest": sealed_digest if digest is None else digest,
                "execution_tree_file_count": sealed_count if count is None else count,
                "instrument_identity_version": SA.INSTRUMENT_IDENTITY_VERSION,
                "runtime_environment_identity_version": SA.RUNTIME_ENVIRONMENT_IDENTITY_VERSION,
                "runtime_environment_digest": SA.environment_manifest_digest(real_environment),
                "runtime_environment_file_count": len(real_environment["files"]),
                "runtime_environment_extra_file_count": len(real_environment["extra_files"]),
                "runtime_environment_stdlib_file_count": real_environment["stdlib_file_count"],
                "runtime_environment_uncovered_sys_path":
                    list(real_environment["uncovered_sys_path"]),
                "python_version": real_environment["python_version"]}}

        def identity(**kwargs):
            check_tree = kwargs.pop("check_tree", True)
            results = SW.identity_checks(schedule_for(**kwargs), root=root, check_tree=check_tree)
            return {r["field"]: r for r in results}

        GIT_ROWS = ("instrument_commit_ancestry", "execution_tree_unchanged", "clean_execution_tree")
        DISK_ROWS = ("execution_tree_digest", "execution_tree_file_count")

        def red(state):
            return sorted(f for f, r in state.items() if not r["ok"])

        # 1. EVIDENCE COMMITS ONLY after the seal — the exact situation that
        #    made the equality rule unsatisfiable. It must PASS.
        _write(instrument / "reviews" / "schedule_x.json", '{"sealed": true}\n')
        _write(root / "GECE.md", "night log\n")
        run("add", "-A")
        run("commit", "-qm", "evidence: the schedule and the logs")
        _write(root / "design_chat" / "from_codex.md", "turn 50 as received\n")
        run("add", "-A")
        run("commit", "-qm", "evidence: the reviewer's turn")
        after = identity()
        if red(after):
            problems.append(f"two evidence commits after the seal must NOT refuse the run: {red(after)}")
        if after["runtime_head"]["actual"] == sealed_commit:
            problems.append("the witness did not actually move HEAD past the instrument commit")

        # 2. ONE CHANGED LINE in an execution path, committed. Red on BOTH the
        #    on-disk digest and the git diff, and the diff NAMES the file.
        _write(instrument / "tests" / "measure_budget.py", "VERSION = 2\n")
        run("add", "-A")
        run("commit", "-qm", "an instrument change dressed as evidence")
        changed = identity()
        if changed["execution_tree_digest"]["ok"]:
            problems.append("a committed instrument change did not move the on-disk digest")
        if changed["execution_tree_unchanged"]["ok"]:
            problems.append("the secondary git diff did not see a committed instrument change")
        if "tests/measure_budget.py" not in str(changed["execution_tree_unchanged"]["note"]):
            problems.append("the git-diff refusal must name the changed file")
        if not changed["execution_tree_file_count"]["ok"]:
            problems.append("an EDITED file must not change the file COUNT — the two rows say "
                            "different things")
        run("revert", "--no-edit", "HEAD")
        if red(identity()):
            problems.append(f"reverting the instrument change must restore the identity: "
                            f"{red(identity())}")

        # 3. A DIRTY EXECUTION PATH (uncommitted).
        _write(instrument / "tests" / "measure_budget.py", "VERSION = 3  # uncommitted\n")
        dirty = identity()
        if dirty["clean_execution_tree"]["ok"] or dirty["execution_tree_digest"]["ok"]:
            problems.append("an uncommitted change under the execution paths was not caught")
        _write(instrument / "tests" / "measure_budget.py", "VERSION = 1\n")

        # 4. A DIRTY EVIDENCE FILE must PASS.
        _write(instrument / "reviews" / "arms_x.log", "session started\n")
        _write(root / "DURUM.md", "state, edited mid-run\n")
        if red(identity()):
            problems.append(f"a dirty EVIDENCE file must not refuse the run: {red(identity())}")

        # ---- ATTACK (A): --assume-unchanged, then edit -------------------
        #      Every git row stays GREEN. Only the bytes on disk say so.
        run("update-index", "--assume-unchanged",
            "environments/beancount_ledger/tests/measure_budget.py")
        _write(instrument / "tests" / "measure_budget.py", "VERSION = 1\nimport os  # exfiltrate\n")
        assumed = identity()
        for field in GIT_ROWS:
            if not assumed[field]["ok"]:
                problems.append(f"attack (A): {field} went red, so this is not a witness that the "
                                f"ON-DISK digest is what catches --assume-unchanged")
        if assumed["execution_tree_digest"]["ok"]:
            problems.append("attack (A) SURVIVED: --assume-unchanged plus an edit left the witness green")
        if not assumed["execution_tree_file_count"]["ok"]:
            problems.append("attack (A) edits a file, it does not add one — the count must hold")
        run("update-index", "--no-assume-unchanged",
            "environments/beancount_ledger/tests/measure_budget.py")
        _write(instrument / "tests" / "measure_budget.py", "VERSION = 1\n")
        if red(identity()):
            problems.append(f"restoring the file must restore the identity: {red(identity())}")

        # ---- ATTACK (B): module shadowing beside the package -------------
        #      `measure_budget.py` inserts the package ROOT at sys.path[0], so
        #      an unsealed `openai.py` HERE is imported before the real one.
        _write(instrument / "openai.py", "# not the real openai\n")
        shadow = identity()
        for field in DISK_ROWS:
            if shadow[field]["ok"]:
                problems.append(f"attack (B) SURVIVED: a shadowing module beside the package left "
                                f"{field} green")
        (instrument / "openai.py").unlink()
        if red(identity()):
            problems.append("removing the shadow must restore the identity")

        # ---- ATTACK (C): a tests/ file hidden by a committed .gitignore ---
        #      `.gitignore` is an EVIDENCE path, so committing the line is
        #      permitted; the file it hides is invisible to status AND ls-tree
        #      while `tests/` is sys.path[0] of every cell process.
        _write(root / ".gitignore", "*.pyc\nenvironments/beancount_ledger/tests/shadow_helper.py\n")
        run("add", "-A")
        run("commit", "-qm", "evidence: a .gitignore line")
        _write(instrument / "tests" / "shadow_helper.py", "# invisible to git, first on sys.path\n")
        hidden = identity()
        for field in GIT_ROWS:
            if not hidden[field]["ok"]:
                problems.append(f"attack (C): {field} went red, so this is not a witness that the "
                                f"ON-DISK walk is what sees a gitignored file")
        for field in DISK_ROWS:
            if hidden[field]["ok"]:
                problems.append(f"attack (C) SURVIVED: a gitignore-hidden file in tests/ left {field} "
                                f"green")
        (instrument / "tests" / "shadow_helper.py").unlink()

        # 5. An unrelated repository is not a continuation of the sealed one,
        #    and a schedule sealed with a different path set or exclusion list
        #    does not get to run under this instrument.
        if identity(commit="0" * 40)["instrument_commit_ancestry"]["ok"]:
            problems.append("a sealed commit that is not in this history must refuse")
        if identity(paths=["environments/beancount_ledger/tests/**"])["execution_paths"]["ok"]:
            problems.append("a schedule sealed with a different execution-path set must refuse")
        if identity(excludes=["reviews/**"])["execution_excludes"]["ok"]:
            problems.append("a schedule sealed with a different exclusion list must refuse")

    # The sealed set is the WHOLE package directory minus named exclusions,
    # and the contract binds every part of it.
    #
    # THE EXECUTION ROOT IS ASSERTED AS A RESOLVED DIRECTORY, not as a
    # hardcoded string. The package is vendored at
    # `environments/beancount_ledger` in the development monorepo and IS the
    # repository top level in a standalone checkout; a name pinned to one
    # layout resolves to NOTHING in the other, and a walk over nothing yields
    # `None`, which compares equal to the sealed `None` on both sides of every
    # check. So the property witnessed here is the one that actually matters:
    # the sealed root resolves to the very package directory this process is
    # importing from, and the path set is that directory's whole subtree.
    resolved = SA.execution_root_for()
    package = Path(SA.__file__).resolve().parents[1]
    base = SA.repo_root() if resolved == "." else SA.repo_root() / resolved
    if base.resolve() != package:
        problems.append(f"the sealed execution root {resolved!r} resolves to {base} — not to the package "
                        f"directory {package} that is executing, so the digest would seal other bytes "
                        f"(or, resolving to nothing, no bytes at all)")
    if list(SA.EXECUTION_PATHS) != ["**" if resolved == "." else f"{resolved}/**"]:
        problems.append(f"the execution set is not the whole package directory: {SA.EXECUTION_PATHS}")
    if set(SA.EXECUTION_EXCLUDES) != {"reviews/**", ".venv/**", ".git/**", "**/__pycache__/**", "*.pyc"}:
        problems.append(f"the exclusion list is not the sealed one: {SA.EXECUTION_EXCLUDES}")
    for relative, excluded in (("reviews/schedule_x.json", True), (".venv/Lib/site-packages/x.py", True),
                               (".git/objects/ab/cdef", True), (".git/index", True),
                               ("tests/__pycache__/x.pyc", True), ("tests/x.pyc", True),
                               ("openai.py", False), ("tests/x.py", False),
                               ("beancount_ledger/graph/policy.py", False),
                               ("tests/gitignore_helper.py", False),
                               ("tests/reviews_of_x.py", False)):
        if SA._excluded(relative) is not excluded:
            problems.append(f"the exclusion matcher is wrong for {relative!r}")
    contract = SA.build_experiment_contract(["A"], [], 40_000, SA.ANALYSIS_PLAN)
    for field in ("execution_paths", "execution_excludes", "execution_tree_digest",
                  "execution_tree_file_count", "instrument_identity_version"):
        if not contract.get(field):
            problems.append(f"the sealed contract does not bind {field}")
    if SA.execution_tree_digest(execution_root="nothing/here") is not None:
        problems.append("an EMPTY execution set must produce NO digest — one over nothing compares "
                        "equal to one over nothing")
    return check("the instrument identity is the BYTES ON DISK under the whole package directory minus "
                 "named exclusions, with the file set in the digest: --assume-unchanged, a shadowing "
                 "module beside the package and a gitignore-hidden tests/ file each turn it red while the "
                 "git rows stay green, an evidence commit or a dirty evidence file stays green, and the "
                 "runtime HEAD is recorded separately",
                 not problems, "\n".join(problems))


def test_free_text_429_is_never_a_rate_limit_needle():
    """Codex T50 §2 — the literal `if "429" in blob` survived the "no digit in
    any map needle" witness because it sat OUTSIDE `ERROR_CLASS_RULES`. A row
    with no structured status whose free text merely CONTAINS 429 — a request
    id, a quota, a header value — could still be classified a rate limit,
    which is the identical bug the header-value finding closed."""
    problems = []
    saturating = _window(billed=1_000_000, billed_mine=900_000, accepted=60, accepted_mine=60)

    # THE MUTATION WITNESS: 429 as an unrelated id, no structured status.
    for text in ("upstream request id req-4290011 was dropped",
                 "the account quota is 429000 tokens per minute",
                 "worker 429 exited"):
        bucket, rule = AT.classify_error(text, None, 1_000_000, 6.0, window=saturating, rpm=49.8)
        if str(rule).startswith("rate_limit"):
            problems.append(f"free text {text!r} reached the rate-limit rule as {bucket}/{rule}")
        if (bucket, rule) != ("ambiguous", "unmatched"):
            problems.append(f"{text!r} -> {bucket}/{rule}, expected ambiguous/unmatched")
    # NONNUMERIC TYPED EVIDENCE still reaches it, which is the whole point of
    # keeping a fallback at all.
    for text in ("RateLimitError", "429 Too Many Requests", "provider says: rate limit exceeded",
                 "rate_limit_exceeded"):
        bucket, rule = AT.classify_error(text, None, 1_000_000, 6.0, window=saturating, rpm=49.8)
        if not str(rule).startswith("rate_limit"):
            problems.append(f"typed evidence {text!r} must still reach the window rule: {bucket}/{rule}")
    # The structured path is untouched: a 429 STATUS always goes to the window.
    if not AT.classify_error("", http_status=429, window=saturating, tpm=1_000_000, rpm=49.8)[1] \
            .startswith("rate_limit"):
        problems.append("an archived http_status of 429 must still reach the window rule")
    # No needle anywhere carries a digit — the map AND the fallback.
    for needle in AT.RATE_LIMIT_TEXT_NEEDLES:
        if any(ch.isdigit() for ch in needle):
            problems.append(f"a numeric needle survives in the fallback: {needle!r}")
    source = Path(AT.__file__).read_text(encoding="utf-8")
    for banned in ('"429" in blob', "'429' in blob"):
        if banned in source:
            problems.append(f"the retired free-text needle is still in the source: {banned}")
    # THE FALLBACK IS BOUND TO schedule_id. Mutating either the needles or the
    # algorithm version must move `failure_map_digest` — the T50 §2 complaint
    # that the fallback lived outside every hashed constant.
    before = SA.failure_map_digest()
    saved_needles, saved_version = AT.RATE_LIMIT_TEXT_NEEDLES, AT.CLASSIFIER_ALGORITHM_VERSION
    try:
        AT.RATE_LIMIT_TEXT_NEEDLES = saved_needles + ("429",)
        if SA.failure_map_digest() == before:
            problems.append("adding a needle to the free-text fallback did not move failure_map_digest")
        AT.RATE_LIMIT_TEXT_NEEDLES = saved_needles
        AT.CLASSIFIER_ALGORITHM_VERSION = "mutated"
        if SA.failure_map_digest() == before:
            problems.append("changing the classifier algorithm version did not move failure_map_digest")
    finally:
        AT.RATE_LIMIT_TEXT_NEEDLES, AT.CLASSIFIER_ALGORITHM_VERSION = saved_needles, saved_version
    if SA.failure_map_digest() != before:
        problems.append("the digest did not return to its value after the mutation was undone")
    return check("no numeric substring can reach the rate-limit rule from free text: only nonnumeric typed "
                 "evidence does, an archived http_status still decides directly, and the fallback's own "
                 "needles and algorithm version are hashed into failure_map_digest",
                 not problems, "\n".join(problems))


def test_window_evidence_separates_billed_rejected_and_current_request():
    """Codex T50 §3 — the most important analysis defect. `window_snapshot`
    folded three different claims into one number:

        if not billed: billed = estimated_request_tokens

    so a rejected request's chars/4 ESTIMATE counted as consumed TPM, and
    repeated backoffs could manufacture a saturated, majority-this-cell window
    out of estimates alone. Meanwhile the snapshot on the fatal attempt
    EXCLUDED the request being refused, so a window below quota that the
    current request would have crossed was called `exogenous`.

    Both archived windows are witnessed here (his Q4), and the bounds rule
    with them."""
    problems = []
    tpm, rpm = 356_250, 22.8

    # 1. REJECTED ESTIMATES ALONE NEVER SATURATE. This is the manufactured
    #    arm_induced the old code could produce.
    estimates_only = _window(billed=1_000, billed_mine=1_000, accepted=1, accepted_mine=1,
                             rejected_estimate=900_000, rejected_estimate_mine=900_000,
                             rejected_requests=6, rejected_requests_mine=6)
    bucket, rule = AT.window_verdict(estimates_only, tpm, rpm)
    if bucket == "arm_induced":
        problems.append(f"rejected estimates alone must never establish an arm-induced rate limit: {rule}")
    if (bucket, rule) != ("ambiguous", "rate_limit_current_request_uncertain_tokens"):
        problems.append(f"estimates-only -> {bucket}/{rule}, expected the uncertain-bound ambiguity")

    # 2. BILLED BELOW QUOTA, BUT BILLED + CURRENT COULD CROSS: at least
    #    ambiguous, never exogenous.
    could_cross = _window(billed=350_000, billed_mine=350_000, accepted=5, accepted_mine=5,
                          current=20_000)
    bucket, rule = AT.window_verdict(could_cross, tpm, rpm)
    if bucket == "exogenous":
        problems.append("a pre-request window below quota that the CURRENT request could cross must not be "
                        "called exogenous")
    if (bucket, rule) != ("ambiguous", "rate_limit_current_request_uncertain_tokens"):
        problems.append(f"could-cross -> {bucket}/{rule}")

    # 3. BILLED ALONE SATURATES: attribution by BILLED shares.
    billed_saturates = _window(billed=400_000, billed_mine=300_000, accepted=5, accepted_mine=4,
                               rejected_estimate=999_999, rejected_estimate_mine=0, current=1_000)
    if AT.window_verdict(billed_saturates, tpm, rpm) != \
            ("arm_induced", "rate_limit_window_saturated_tokens"):
        problems.append(f"billed saturation must attribute by billed share: "
                        f"{AT.window_verdict(billed_saturates, tpm, rpm)}")
    minority = _window(billed=400_000, billed_mine=100_000, accepted=5, accepted_mine=1)
    if AT.window_verdict(minority, tpm, rpm) != ("ambiguous", "rate_limit_carryover_tokens"):
        problems.append(f"a saturating window this cell did not fill is carry-over: "
                        f"{AT.window_verdict(minority, tpm, rpm)}")

    # 4. TRULY BELOW under the WIDEST admission rule: exogenous.
    quiet = _window(billed=40_000, billed_mine=9_000, accepted=4, accepted_mine=1,
                    rejected_estimate=1_000, rejected_requests=1, current=9_000)
    if AT.window_verdict(quiet, tpm, rpm) != ("exogenous", "rate_limit_window_not_saturated"):
        problems.append(f"a window below quota even counting everything is exogenous: "
                        f"{AT.window_verdict(quiet, tpm, rpm)}")

    # 4b. THE SNAPSHOT ITSELF keeps them apart. This is the exact line the
    #     retired code ran — `if not billed: billed = estimated_request_tokens`
    #     — and it is what let a pile of refusals look like consumed TPM.
    ledger_entries = [
        {"t": 100.0, "provider": "mistral", "model": "m", "cell": "mine", "status": "ok",
         "billed_input_tokens": 30_000, "billed_output_tokens": 500,
         "estimated_request_tokens": 29_000},
        {"t": 110.0, "provider": "mistral", "model": "m", "cell": "mine", "status": "rate_limited",
         "estimated_request_tokens": 120_000},
        {"t": 115.0, "provider": "mistral", "model": "m", "cell": "other",
         "status": "error:APIConnectionError", "estimated_request_tokens": 7_000},
        {"t": 120.0, "provider": "mistral", "model": "m", "cell": "other", "status": "ok",
         "billed_input_tokens": None, "billed_output_tokens": None,
         "estimated_request_tokens": 4_000},
    ]
    snap = mb.window_snapshot(ledger_entries, 150.0, "mistral", "m", "mine",
                              current_request_estimate=8_000)
    if snap["billed_tokens_total"] != 30_500:
        problems.append(f"a refused request's estimate entered BILLED usage: {snap['billed_tokens_total']} "
                        f"(expected 30,500 — only what the provider reported for what it served)")
    if snap["billed_tokens_this_cell"] != 30_500:
        problems.append(f"this cell's billed share is wrong: {snap['billed_tokens_this_cell']}")
    if snap["rejected_estimate_tokens_total"] != 127_000:
        problems.append(f"the refused attempts' estimates must be their own total: "
                        f"{snap['rejected_estimate_tokens_total']}")
    if snap["rejected_estimate_tokens_this_cell"] != 120_000:
        problems.append("this cell's own refused estimate must be separable from another cell's")
    if snap["unbilled_accepted_estimate_tokens_total"] != 4_000:
        problems.append("a SERVED request that reported no usage is evidence, not billed fact, and has "
                        "its own field")
    if snap["accepted_requests_total"] != 2 or snap["rejected_requests_total"] != 2:
        problems.append(f"accepted and rejected request counts must be separate: {snap}")
    # Those 127,000 rejected tokens must not be able to saturate anything.
    if AT.dimension_verdict(snap, "tokens", 100_000)["state"] != "uncertain":
        problems.append("billed 30,500 against a 100,000 quota is not saturation, whatever the refused "
                        "attempts estimate")
    if AT.dimension_verdict(snap, "tokens", 20_000)["state"] != "saturated":
        problems.append("billed 30,500 against a 20,000 quota IS established saturation")

    # 5. The ADMISSION SEMANTICS are sealed as an explicit unknown (his Q3).
    if AT.ADMISSION_SEMANTICS != "undocumented":
        problems.append(f"the admission semantics must be sealed as undocumented: {AT.ADMISSION_SEMANTICS}")
    quotas = SA.provider_quota_table()
    if quotas.get("admission_semantics") != "undocumented":
        problems.append("the quota table must seal the admission semantics beside the numbers")

    # 6. BOTH WINDOWS ARE ARCHIVED AND LABELLED (his Q4), through the real
    #    client path, with a real shared ledger.
    import tempfile

    import openai
    import verifiers.legacy.clients.openai_chat_completions_client as oai_mod

    class _FakeHTTPResponse:
        status_code = 429
        headers: dict = {}
        request = None

    class _FakeResponse:
        def __init__(self):
            self.usage = type("U", (), {"prompt_tokens": 11, "completion_tokens": 7})()
            self.model = "scripted-model"

    calls = {"n": 0}

    async def flaky_post(client, path, *, body, extra_headers=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise openai.RateLimitError("429 Too Many Requests", response=_FakeHTTPResponse(), body=None)
        return _FakeResponse()

    with tempfile.TemporaryDirectory() as directory:
        ledger = Path(directory) / "w.jsonl"
        mb.window_ledger_append(ledger, {"t": time.time(), "provider": "mistral", "model": "m",
                                         "cell": "earlier", "status": "ok",
                                         "billed_input_tokens": 120_000, "billed_output_tokens": 400})
        client_cls = mb.make_client_cls(0.0, True, window_ledger=ledger, provider="mistral",
                                        cell="thiscell", session_id="s1")
        client = client_cls(DUMMY_CONFIG)
        original = oai_mod.post_chat_completion_with_routed_experts_sidecar
        oai_mod.post_chat_completion_with_routed_experts_sidecar = flaky_post
        original_sleep = asyncio.sleep

        async def no_sleep(_seconds):
            return await original_sleep(0)

        asyncio.sleep = no_sleep
        try:
            asyncio.run(client.get_native_response([{"role": "system", "content": "s"}], "m",
                                                   {"max_tokens": 100}, None,
                                                   state={"piv_rollout_id": "r"}))
        finally:
            oai_mod.post_chat_completion_with_routed_experts_sidecar = original
            asyncio.sleep = original_sleep

        attempt = client.requests[0]
        pre, prospective = attempt.get("provider_window"), attempt.get("provider_window_prospective")
        if not isinstance(pre, dict) or not isinstance(prospective, dict):
            problems.append(f"the fatal attempt must archive BOTH windows: {sorted(attempt)}")
        else:
            if pre["window_kind"] != AT.WINDOW_KIND_PRE_REQUEST:
                problems.append("the pre-request window is not labelled")
            if prospective["window_kind"] != AT.WINDOW_KIND_PROSPECTIVE:
                problems.append("the prospective window is not labelled")
            if pre["billed_tokens_total"] != 120_400:
                problems.append(f"the pre-request billed window is wrong: {pre['billed_tokens_total']}")
            if prospective["billed_tokens_total"] != pre["billed_tokens_total"]:
                problems.append("the prospective window changed BILLED usage — the estimate is being "
                                "presented as billed, which is exactly the conflation §3 forbids")
            if prospective["rejected_estimate_tokens_total"] <= pre["rejected_estimate_tokens_total"]:
                problems.append("the prospective window must add the current request as a REJECTED "
                                "estimate")
            if not pre.get("current_request_estimate_tokens"):
                problems.append("the pre-request window must still name the current request's estimate")
            if pre.get("admission_semantics") != "undocumented":
                problems.append("every snapshot must carry the admission semantics it was read under")
        row = {"quarantined": True, "status": "rollout failed", "provider": "mistral",
               "model": "mistral-medium-2508", "requests": client.requests}
        if AT.rate_limit_window(row) is not pre:
            problems.append("rate_limit_window must return the PRE-REQUEST window")
        if AT.rate_limit_window_prospective(row) is not prospective:
            problems.append("rate_limit_window_prospective must return the prospective one")
    return check("billed usage, rejected-attempt estimates and the current request are three separate "
                 "fields: estimates alone never saturate a quota, a window the current request could cross "
                 "is ambiguous rather than exogenous, attribution uses billed shares, and the fatal attempt "
                 "archives BOTH the pre-request and the prospective window, labelled",
                 not problems, "\n".join(problems))


def test_tpm_and_rpm_are_evaluated_independently():
    """Codex T50 §4 — `window_verdict` asked about tokens FIRST and never
    looked at requests when tokens saturated, so a token window this cell was
    a minority of could hide a request window it was the majority of, and the
    reverse. His four cases are pinned here."""
    problems = []
    tpm, rpm = 356_250, 22.8

    def window(billed, billed_mine, accepted, accepted_mine):
        return _window(billed=billed, billed_mine=billed_mine,
                       accepted=accepted, accepted_mine=accepted_mine)

    cases = [
        # tokens-only: the request window is quiet
        ("tokens only, majority", window(400_000, 300_000, 5, 5),
         ("arm_induced", "rate_limit_window_saturated_tokens")),
        # requests-only: the token window is quiet
        ("requests only, majority", window(1_000, 900, 40, 39),
         ("arm_induced", "rate_limit_window_saturated_requests")),
        # both saturated, both majority: they AGREE
        ("both agree, majority", window(400_000, 300_000, 40, 39),
         ("arm_induced", "rate_limit_window_saturated_tokens+requests")),
        # both saturated, both minority: they agree the other way
        ("both agree, carryover", window(400_000, 10_000, 40, 2),
         ("ambiguous", "rate_limit_carryover_tokens+requests")),
        # THE CASE THE FIXED PRIORITY HID: tokens saturated and a minority,
        # requests saturated and a majority. The retired code returned
        # ambiguous/rate_limit_carryover_tokens and never mentioned that its
        # own declared rule called the request dimension arm-induced.
        ("opposing: tokens minority, requests majority", window(400_000, 10_000, 40, 39),
         ("ambiguous", "rate_limit_dimensions_disagree")),
        # ... and the reverse combination
        ("opposing: tokens majority, requests minority", window(400_000, 300_000, 40, 2),
         ("ambiguous", "rate_limit_dimensions_disagree")),
    ]
    for label, w, want in cases:
        got = AT.window_verdict(w, tpm, rpm)
        if got != want:
            problems.append(f"{label}: {got}, expected {want}")

    # BOTH verdicts are recorded, not just the winning one.
    verdicts = AT.window_dimension_verdicts(window(400_000, 10_000, 40, 39), tpm, rpm)
    if verdicts["tokens"]["state"] != "saturated" or verdicts["requests"]["state"] != "saturated":
        problems.append(f"both dimensions must be evaluated: {verdicts}")
    if verdicts["tokens"]["attribution"] != "carryover" or \
            verdicts["requests"]["attribution"] != "this_cell_majority":
        problems.append(f"each dimension must carry its OWN attribution: {verdicts}")
    if verdicts["combined"] != ("ambiguous", "rate_limit_dimensions_disagree"):
        problems.append("the combination must be conservative when the dimensions disagree")
    # An UNESTABLISHED dimension neither saturates nor contradicts.
    one_sided = AT.window_dimension_verdicts(window(400_000, 300_000, 40, 39), tpm, None)
    if one_sided["requests"]["state"] != "unestablished":
        problems.append("a dimension with no quota must be reported as unestablished, not as below")
    if one_sided["combined"] != ("arm_induced", "rate_limit_window_saturated_tokens"):
        problems.append(f"an unestablished dimension must not block a saturated one: {one_sided}")
    if AT.window_verdict(window(1_000, 900, 2, 2), None, None) != \
            ("ambiguous", "rate_limit_quota_unknown"):
        problems.append("with NO established quota at all the verdict is quota_unknown")
    # A REQUEST IS A REQUEST WHATEVER ITS SIZE (adversarial review, INFO). The
    # request dimension used to derive "there is a request in flight" from the
    # presence of a TOKEN estimate, so a request whose size could not be
    # estimated silently lost its +1 against the RPM bound.
    unsized = _window(billed=10, billed_mine=10, accepted=22, accepted_mine=22,
                      current=None, current_request_present=True)
    dimension = AT.dimension_verdict(unsized, "requests", 22.8)
    if dimension["current_request"] != 1:
        problems.append("a current request with no size estimate must still count as one request")
    if dimension["state"] != "uncertain":
        problems.append(f"22 accepted requests plus the one in flight reach a 22.8 RPM bound: "
                        f"{dimension}")
    sized_out = AT.dimension_verdict(_window(billed=10, accepted=22, current=5_000,
                                             current_request_present=False), "requests", 22.8)
    if sized_out["current_request"] != 0:
        problems.append("with no request in flight the bound must not invent one")
    return check("the token and request windows are evaluated independently on their own bounds, both "
                 "verdicts are recorded, agreement gives a single bucket, and disagreement is AMBIGUOUS "
                 "rather than silently decided by a fixed priority",
                 not problems, "\n".join(problems))


def test_a_malformed_window_ledger_line_is_unhealthy_until_an_operator_recovers_it():
    """Codex T50 §5 — `window_ledger_read` silently skipped every JSON parse
    failure. A killed process leaves a truncated final line; the next append
    concatenates onto it, so the damaged record becomes a malformed MIDDLE
    line and takes the following record with it. The reader then undercounts
    the window, paces from an older request, attaches no suspicion, and
    continues as if the evidence were complete.

    The witness Codex asked for: "truncated final line, then resume and
    append"."""
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as directory:
        ledger = Path(directory) / "w.jsonl"
        now = time.time()          # the recovery boundary is stamped with the real clock
        for offset in (50, 40, 30):
            mb.window_ledger_append(ledger, {"t": now - offset, "provider": "mistral", "model": "m",
                                             "cell": "cellA", "status": "ok",
                                             "billed_input_tokens": 1_000, "billed_output_tokens": 10})
        healthy_bytes = ledger.read_bytes()

        # A KILLED PROCESS: a final line with no newline.
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write('{"t": 2000000.0, "provider": "mistral", "model": "m", "cell": "cel')
        damaged_bytes = ledger.read_bytes()
        health = mb.window_ledger_health(ledger)
        if health["healthy"]:
            problems.append("a truncated final line must make the ledger UNHEALTHY")
        if not health["unterminated_final_line"]:
            problems.append("the health report must name the unterminated final line")

        # EVERY door refuses, BEFORE the next provider request.
        for label, call in (("read", lambda: mb.window_ledger_read(ledger)),
                            ("precheck", lambda: mb.window_ledger_precheck(ledger)),
                            ("append", lambda: mb.window_ledger_append(ledger, {"t": now}))):
            try:
                call()
                problems.append(f"{label}: an unhealthy ledger must refuse, not proceed")
            except mb.WindowLedgerUnhealthy:
                pass
        if not issubclass(mb.WindowLedgerUnhealthy, mb.WindowLedgerUnavailable):
            problems.append("an unhealthy ledger must be a kind of unavailable ledger, so every existing "
                            "handler already treats it as a fault")
        if ledger.read_bytes() != damaged_bytes:
            problems.append("the damaged bytes were altered by a refusal — they are audit evidence")
        # A non-strict read is available for the tools that DESCRIBE damage.
        if len(mb.window_ledger_read(ledger, strict=False)) != 3:
            problems.append("a non-strict read must still return the readable entries")

        # RECOVERY is an explicit operator act. It never repairs or deletes.
        record = mb.window_ledger_recover(ledger, reason="a killed cell", session_id="s1",
                                          operator="witness")
        if not record.get("recovered"):
            problems.append("recovery did not report itself as having acted")
        if record.get("acknowledged_through_line") != 4:
            problems.append(f"the boundary must acknowledge the damaged lines by number: {record}")
        after = ledger.read_bytes()
        if not after.startswith(damaged_bytes):
            problems.append("recovery rewrote or removed preserved bytes instead of appending to them")
        if not mb.window_ledger_health(ledger)["healthy"]:
            problems.append("after recovery the ledger must be healthy again")

        # RESUME AND APPEND — the witness Codex named.
        mb.window_ledger_append(ledger, {"t": now + 1, "provider": "mistral", "model": "m",
                                         "cell": "cellB", "status": "ok",
                                         "billed_input_tokens": 5_000, "billed_output_tokens": 50})
        entries = mb.window_ledger_read(ledger)
        if len(entries) != 5:                    # 3 good + the boundary + the resumed append
            problems.append(f"resume-and-append after recovery read back {len(entries)} entries")
        if not any(e.get("cell") == "cellB" for e in entries):
            problems.append("the appended record after recovery did not land")

        # THE AFFECTED CLASSIFICATIONS ARE AMBIGUOUS: a window spanning the
        # boundary is incomplete BY CONSTRUCTION.
        snapshot = mb.window_snapshot(entries, now + 2, "mistral", "m", "cellB")
        if not snapshot.get("evidence_incomplete"):
            problems.append("a window spanning a recovery boundary must be marked incomplete")
        if AT.window_verdict(snapshot, 1_000, 1.0) != ("ambiguous", "rate_limit_evidence_incomplete"):
            problems.append(f"a 429 in a recovered segment must classify ambiguous: "
                            f"{AT.window_verdict(snapshot, 1_000, 1.0)}")
        # A window entirely AFTER the boundary is clean again.
        later = mb.window_snapshot(entries, now + 400, "mistral", "m", "cellB", seconds=10)
        if later.get("evidence_incomplete"):
            problems.append("a window that does not span the boundary must not be marked incomplete")

        # A NEW malformed line after the recovery is unhealthy again: the
        # boundary acknowledges the PAST, never the future.
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write("not json at all\n")
        if mb.window_ledger_health(ledger)["healthy"]:
            problems.append("a NEW malformed line after a recovery must make the ledger unhealthy again")

        # Recovery is refused when there is nothing to recover.
        fresh = Path(directory) / "clean.jsonl"
        fresh.write_bytes(healthy_bytes)
        if mb.window_ledger_recover(fresh, reason="none")["recovered"]:
            problems.append("recovering a HEALTHY ledger must do nothing and say so")

        # THE TOCTOU (adversarial review, C2). The scan used to run OUTSIDE
        # the append lock, so a writer that truncated the file between the
        # scan and the lock got its damage appended onto: two records merged
        # into one malformed line, which is the exact failure the scan exists
        # to prevent. The scan is inside the lock now — witnessed by injecting
        # the truncation at the moment the lock is taken.
        race = Path(directory) / "race.jsonl"
        race.write_text('{"t": 1.0, "provider": "mistral", "status": "ok"}\n', encoding="utf-8")
        original_lock_enter = mb._LedgerLock.__enter__
        injected = {"n": 0}

        def truncating_enter(self):
            handle = original_lock_enter(self)
            if injected["n"] == 0 and str(self.path).startswith(str(race)):
                injected["n"] += 1
                # a concurrent writer dies mid-append, AFTER any check that
                # happened before the lock was taken
                with open(race, "a", encoding="utf-8") as fh:
                    fh.write('{"t": 2.0, "provider": "mist')
            return handle

        mb._LedgerLock.__enter__ = truncating_enter
        try:
            mb.window_ledger_append(race, {"t": 3.0, "provider": "mistral", "status": "ok"})
            problems.append("C2: an append landed on evidence that was damaged after the pre-lock scan "
                            "— the health check is still outside the lock")
        except mb.WindowLedgerUnhealthy:
            pass
        finally:
            mb._LedgerLock.__enter__ = original_lock_enter
        if not injected["n"]:
            problems.append("C2: the truncation was never injected, so nothing was witnessed")
        tail = race.read_text(encoding="utf-8").splitlines()[-1]
        if '"t": 3.0' in tail:
            problems.append(f"C2: the new record was merged onto the truncated one: {tail!r}")
        if mb.window_ledger_health(race)["healthy"]:
            problems.append("C2: the injected truncation left the ledger looking healthy")
    if "--recover-window-ledger" not in Path(RA.__file__).read_text(encoding="utf-8"):
        problems.append("run_arms does not offer the explicit operator recovery")
    return check("ANY malformed or unterminated ledger line makes the shared window ledger unhealthy and "
                 "refuses the next provider request; the bytes are preserved; recovery is an explicit "
                 "operator act that appends a segment boundary, lets the run resume and append, and makes "
                 "every classification whose window spans it ambiguous",
                 not problems, "\n".join(problems))


def test_the_execution_journal_fails_closed_in_confirmatory_mode():
    """Codex T50 §6 — `journal()` was `except OSError: pass`, while the
    schedule claimed that a takeover is journalled BEFORE the probe, that a
    crashed cell stays visible through `cell_started`, that the actual order
    can be reconstructed and that exclusions and split sessions are recorded.
    Every one of those claims was conditional on nothing having gone wrong."""
    import tempfile
    problems = []
    with tempfile.TemporaryDirectory() as directory:
        good = Path(directory) / "reviews" / "arms_x_execution.jsonl"
        if not RA.journal(good, {"event": "cell_started", "tag": "t"}, required=True):
            problems.append("a healthy append did not report success")
        written = json.loads(good.read_text(encoding="utf-8").splitlines()[0])
        if "runtime_head" not in written:
            problems.append("every journal entry must carry the RUNTIME head (Codex T50 §1)")

        # An unwritable path: a FILE where the directory must be.
        blocker = Path(directory) / "afile"
        blocker.write_text("x", encoding="utf-8")
        bad = blocker / "under" / "arms_y_execution.jsonl"
        if RA.journal(bad, {"event": "cell_started"}, required=False):
            problems.append("a failing append must report failure even in the lenient mode")
        try:
            RA.journal(bad, {"event": "cell_started"}, required=True)
            problems.append("a failing append must RAISE when the entry is required")
        except RA.JournalUnavailable as exc:
            if "cell_started" not in str(exc):
                problems.append(f"the refusal must name the event it could not record: {exc}")

        # The CREATE / APPEND / READ-BACK probe, before any provider request.
        ok, detail = RA.journal_probe(Path(directory) / "reviews" / "probe.jsonl")
        if not ok:
            problems.append(f"the journal probe failed on a healthy path: {detail}")
        ok, _ = RA.journal_probe(bad)
        if ok:
            problems.append("the journal probe passed on an unwritable path")

        # The probe is part of the STARTUP WITNESS, on the executor's own path.
        schedule = _sealed_schedule(label="journalw")
        results = RA.startup_results(schedule, Path(directory) / "reviews")
        fields = {r["field"]: r for r in results}
        if "execution_journal" not in fields:
            problems.append("the startup witness does not probe the execution journal")
        elif not fields["execution_journal"]["ok"]:
            problems.append(f"the journal probe failed in the witness: {fields['execution_journal']}")
        broken = RA.startup_results(schedule, blocker / "nowhere")
        broken_fields = {r["field"]: r for r in broken}
        if broken_fields.get("execution_journal", {}).get("ok", True):
            problems.append("the startup witness passed with an unwritable execution journal")

    # CONFIRMATORY callers pass `required`; the pilot keeps the lenient path,
    # labelled. Every event the schedule claims to record is covered.
    import inspect
    source = Path(RA.__file__).read_text(encoding="utf-8")
    journal_source = inspect.getsource(RA.journal)
    if "raise JournalUnavailable" not in journal_source:
        problems.append("the journal append cannot raise at all — it is still fail-open")
    if "return False" not in journal_source or "required" not in journal_source:
        problems.append("the journal append does not report failure to its caller")
    for durability in ("flush()", "fsync"):
        if durability not in journal_source:
            problems.append(f"the journal append does not {durability}")
    for event in ("cell_started", "cell_finished", "schedule_lock_taken_over", "execution_integrity",
                  "configuration_stopped"):
        index = source.find(f'"event": "{event}"')
        if index < 0:
            problems.append(f"{event} is not journalled at all")
        elif "required=confirmatory" not in source[index:index + 1400]:
            problems.append(f"{event} is journalled but not fail-closed in confirmatory mode")
    if "def main() -> int:" not in source or "except JournalUnavailable" not in source:
        problems.append("a journal failure does not become an exit code")
    return check("the execution journal is locked, flushed, fsync'd and CHECKED: in confirmatory mode a "
                 "failed append raises and aborts the action it authorizes, every entry carries the "
                 "runtime HEAD, and the startup witness proves create/append/read-back before request 1",
                 not problems, "\n".join(problems))


def test_a_sealed_schedule_refuses_the_probe_bypass_and_records_four_distinct_outcomes():
    """Codex T50 §7 and §8/Q9 — `--no-probe-capabilities` was still accepted
    for a sealed schedule, so rows created through it satisfied the same exact
    cell identity and entered the confirmatory table without the
    configuration-wide fact the analysis plan registers; and every non-admitted
    probe was journalled `capability_incompatible`, including an INCONCLUSIVE
    one. Unknown is not incompatible.

    Q9: the table learns about a configuration-level exclusion from an
    immutable, content-bound RECORD, because the cells it blocks have no
    rows."""
    import contextlib
    import io
    import tempfile
    problems = []

    # 1. THE BYPASS IS REFUSED, before anything runs.
    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        schedule = _sealed_schedule(label="probew")
        path = reviews / "schedule_probew.json"
        path.write_text(json.dumps(schedule, default=str), encoding="utf-8")
        err, out = io.StringIO(), io.StringIO()
        saved = sys.argv
        sys.argv = ["run_arms.py", "--schedule", str(path), "--no-probe-capabilities",
                    "--reviews-dir", str(reviews), "--dry-run"]
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                code = RA.main()
        finally:
            sys.argv = saved
        if code != 2:
            problems.append(f"--no-probe-capabilities on a sealed schedule must exit 2, got {code}")
        if "no-probe-capabilities" not in err.getvalue():
            problems.append("the refusal must name the flag it refuses")
        # A PILOT schedule keeps the flag: the refusal is gated on the seal.
        pilot = _schedule(label="pilotprobe")
        pilot_path = reviews / "schedule_pilotprobe.json"
        pilot_path.write_text(json.dumps(pilot, default=str), encoding="utf-8")
        sys.argv = ["run_arms.py", "--schedule", str(pilot_path), "--no-probe-capabilities",
                    "--reviews-dir", str(reviews), "--dry-run"]
        try:
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                pilot_code = RA.main()
        finally:
            sys.argv = saved
        if pilot_code == 2:
            problems.append("the refusal must be gated on the SEAL, not applied to pilot schedules")

    # 2. FOUR DISTINCT OUTCOMES; an inconclusive probe is never an
    #    incompatibility.
    outcomes = {
        "probe_passed": {"admissible": True, "conclusive": True},
        "capability_failed": {"admissible": False, "conclusive": True},
        "probe_inconclusive": {"admissible": True, "conclusive": False},
    }
    for expected, result in outcomes.items():
        if RA.probe_event(result) != expected:
            problems.append(f"{result} -> {RA.probe_event(result)}, expected {expected}")
    if RA.probe_event({"admissible": True, "conclusive": False}, True) != "inconclusive_accepted":
        problems.append("an explicitly accepted inconclusive probe needs its own event type")
    if RA.probe_event({"admissible": False, "conclusive": True}, True) != "capability_failed":
        problems.append("the override must never turn a conclusive failure into an accepted one")
    if RA.probe_conclusively_failed({"admissible": True, "conclusive": False}):
        problems.append("an INCONCLUSIVE probe must never be treated as a conclusive failure")
    if set(RA.PROBE_EVENTS) != set(outcomes) | {"inconclusive_accepted"}:
        problems.append(f"the closed probe-event set is wrong: {RA.PROBE_EVENTS}")

    # 3. THE EXCLUSION RECORD: immutable, content-bound, consumed by the table
    #    for cells that have NO rows.
    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        schedule = _sealed_schedule(label="exclw")
        path = reviews / "schedule_exclw.json"
        path.write_text(json.dumps(schedule, default=str), encoding="utf-8")
        record = SA.write_configuration_exclusion(path, schedule, "mistral", "devstral-2512",
                                                  reason="capability_probe_failed",
                                                  evidence={"policies": {"reasoning_replay=on": "failed"}},
                                                  session_id="s1")
        again = SA.write_configuration_exclusion(path, schedule, "mistral", "devstral-2512",
                                                 reason="something else", session_id="s2")
        if again.get("record_digest") != record.get("record_digest"):
            problems.append("an exclusion record must be immutable: a second write returns the first")
        loaded = SA.read_configuration_exclusions(path, schedule)
        if len(loaded["records"]) != 1 or loaded["problems"]:
            problems.append(f"the record did not round-trip: {loaded}")
        if not record.get("runtime_head"):
            problems.append("an exclusion record must name the runtime HEAD that wrote it")

        # A TAMPERED record is refused, not believed.
        excl_path = SA.exclusion_record_path_for(path)
        tampered = dict(record)
        tampered["provider"] = "someone-else"
        excl_path.write_text(json.dumps(tampered, sort_keys=True, default=str) + "\n", encoding="utf-8")
        checked = SA.read_configuration_exclusions(path, schedule)
        if checked["records"] or not checked["problems"]:
            problems.append("an edited exclusion record must be refused, not consumed")
        # A record naming ANOTHER schedule is not this experiment's.
        foreign = dict(record)
        foreign["schedule_id"] = "0" * 64
        foreign["record_digest"] = SA.exclusion_digest(foreign)
        excl_path.write_text(json.dumps(foreign, sort_keys=True, default=str) + "\n", encoding="utf-8")
        if SA.read_configuration_exclusions(path, schedule)["records"]:
            problems.append("an exclusion record for a different schedule must not be consumed")

        # THE TABLE CONSUMES IT for a configuration with ZERO rows.
        excl_path.write_text(json.dumps(record, sort_keys=True, default=str) + "\n", encoding="utf-8")
        rows = [_row(model="mistral-medium-2508", selector="train:1", arm=arm, reward=1.0, complete=True)
                for arm in ("A", "B1", "B2")]
        if AT.capability_incompatible_configurations(rows):
            problems.append("no row here is a capability failure, so rows alone must exclude nothing")
        evidence = {"exclusions": AT.configuration_exclusions(path, schedule)}
        excluded = AT.capability_incompatible_configurations(rows, evidence["exclusions"]["records"])
        if list(excluded) != [("mistral", "devstral-2512")]:
            problems.append(f"the record-based exclusion was not learned: {list(excluded)}")
        text = AT.render_table(rows, "t", [], schedule, False, False, ("A", "B1", "B2"), "A",
                               None, evidence)
        if "excluded WHOLE for capability incompatibility" not in text:
            problems.append("the record-based exclusion is not reported in the table")
        if "devstral-2512" not in text.split("Configurations excluded WHOLE")[1][:600]:
            problems.append("the excluded configuration is not named")

        # A TAMPERED record on a panel with NO ROWS AT ALL must still exit 2
        # (adversarial review, INFO). `if not rows: return 1` used to run
        # first, so "nothing has been executed yet" — the state every resumed
        # confirmatory run starts in — masked an unauthenticatable exclusion.
        tampered = dict(record)
        tampered["reason"] = "edited after the fact"
        excl_path.write_text(json.dumps(tampered, sort_keys=True, default=str) + "\n", encoding="utf-8")
        err = io.StringIO()
        saved = sys.argv
        sys.argv = ["arm_table.py", "--label", "zero", "--schedule", str(path),
                    "--reviews-dir", str(reviews)]
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = AT.main()
        finally:
            sys.argv = saved
        if code != 2:
            problems.append(f"a tampered exclusion record on a zero-row panel must exit 2, got {code}")
        if "cannot be authenticated" not in err.getvalue():
            problems.append("the zero-row refusal must say the record could not be authenticated")
    # 4. C3 (adversarial review): `--recover-window-ledger` is the ONE mutating
    #    operation a sealed schedule permits, and it used to run and journal
    #    BEFORE the startup witness — writing to the ledger from a checkout the
    #    witness was about to refuse. Witnessed behaviourally: a sealed
    #    schedule whose contract does not describe this checkout, plus a
    #    damaged ledger, must exit 3 with the damaged bytes UNTOUCHED.
    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        schedule = _sealed_schedule(label="c3w")          # a fixture contract: the witness will refuse
        path = reviews / "schedule_c3w.json"
        path.write_text(json.dumps(schedule, default=str), encoding="utf-8")
        ledger = Path(str(path) + ".window.jsonl")
        ledger.write_text('{"t": 1.0, "provider": "mistral", "status": "ok"}\n'
                          '{"t": 2.0, "provider": "mist', encoding="utf-8")
        damaged = ledger.read_bytes()
        err, out = io.StringIO(), io.StringIO()
        saved = sys.argv
        sys.argv = ["run_arms.py", "--schedule", str(path), "--recover-window-ledger",
                    "--reviews-dir", str(reviews), "--dry-run"]
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                code = RA.main()
        finally:
            sys.argv = saved
        if code != 3:
            problems.append(f"C3: a refusing startup witness must stop the run before recovery, got exit "
                            f"{code}")
        if ledger.read_bytes() != damaged:
            problems.append("C3: the ledger was RECOVERED from a checkout the startup witness refused — "
                            "the one mutating operation ran before the witness")
        if mb.window_ledger_health(ledger)["healthy"]:
            problems.append("C3: the damaged ledger was repaired despite the refusal")
        if "REFUSED before request 1" not in err.getvalue():
            problems.append("C3: the refusal did not come from the startup witness")
    return check("--no-probe-capabilities is refused outright for a sealed schedule (and kept for a pilot), "
                 "the four probe outcomes are distinct event types with inconclusive never recorded as "
                 "incompatible, and a conclusive exclusion is an immutable content-bound record the table "
                 "consumes for cells that have no rows",
                 not problems, "\n".join(problems))


def test_the_table_renders_the_T50_execution_evidence():
    """Codex T50 §9 — no new outcome metric and no new decision threshold; the
    estimands are final. These are the six audit renderings he asks for before
    resealing, each of which a T50 defect had made unreadable from the
    archive."""
    import tempfile
    problems = []
    schedule = _sealed_schedule(label="evidw")
    cells = [c for c in schedule["cells"] if c["block_id"] == schedule["cells"][0]["block_id"]]
    rows = [_cell_row(schedule, cell, session_id="s1", actual_ordinal=i + 1,
                      started_at=f"2026-08-31T10:0{i}:00",
                      runtime_head="a" * 40,
                      execution_tree_digest=schedule["experiment_contract"]["execution_tree_digest"])
            for i, cell in enumerate(cells)]
    # One 429 with the separated evidence and both windows.
    pre = _window(billed=400_000, billed_mine=300_000, accepted=5, accepted_mine=4, current=12_000)
    rows.append(_row(model="mistral-medium-2508", provider="mistral", arm="B1", selector="train:1",
                     quarantined=True, status="rollout failed", min_interval=6.0,
                     runtime_head="a" * 40,
                     requests=[{"status": "rate_limited", "http_status": 429,
                                "error_class": "RateLimitError", "error_message": "429 Too Many Requests",
                                "estimated_request_tokens": 12_000,
                                "provider_window": pre,
                                "provider_window_prospective": mb.prospective_window(pre, 12_000),
                                "ledger_write_failed": "disk full"}]))
    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        journal_path = SA.journal_path_for(reviews, schedule)
        for event in ({"event": "probe_passed", "provider": "mistral", "model": "mistral-medium-2508",
                       "at": "2026-08-31T09:00:00", "result": {"policies": {"reasoning_replay=on": {}}}},
                      {"event": "probe_inconclusive", "provider": "mistral", "model": "devstral-2512",
                       "at": "2026-08-31T09:01:00", "result": {"policies": {}}},
                      {"event": "schedule_lock_taken_over", "session_id": "s1",
                       "at": "2026-08-31T09:02:00", "note": "verified dead"},
                      {"event": "window_ledger_recovered", "session_id": "s1",
                       "at": "2026-08-31T09:03:00", "detail": "a killed cell"}):
            RA.journal(journal_path, event, required=True)
        evidence = {"journal": AT.load_execution_journal(journal_path),
                    "exclusions": {"records": [], "problems": []},
                    "ledger_health": {"exists": True, "healthy": True, "line_count": 12, "recoveries": []}}
        text = AT.render_table(rows, "evidw", [], schedule, False, False, ("A", "B1", "B2"), "A",
                               None, evidence)
    required = [
        ("§9.1 runtime identity", "Instrument identity: what was sealed, and what ran"),
        ("§9.1 verified tree", "VERIFIED — identical instrument content"),
        ("§9.2 probe outcome", "Capability-probe outcome per configuration"),
        ("§9.2 inconclusive distinguished", "probe_inconclusive"),
        ("§9.3 journal health", "Execution-journal health"),
        ("§9.3 takeover", "schedule_lock_taken_over"),
        ("§9.3 recovery", "window_ledger_recovered"),
        ("§9.4 per-429 evidence", "Rate-limit (429) evidence, per attempt"),
        ("§9.4 both dimensions", "TPM verdict"),
        ("§9.4 prospective window", "prospective"),
        ("§9.5 ledger status", "Provider-window ledger status"),
        ("§9.5 gap", "window_ledger_gap"),
        ("§9.6 scheduled census", "Order balance census (as scheduled)"),
        ("§9.6 executed census", "as EXECUTED"),
    ]
    for label, needle in required:
        if needle not in text:
            problems.append(f"{label}: the table does not render {needle!r}")
    if "rate_limit_window_saturated_tokens" not in text:
        problems.append("the combined per-429 bucket is not rendered")
    if "arm_induced" not in text.split("Rate-limit (429) evidence")[1][:2000]:
        problems.append("the 429 evidence table does not carry the combined verdict")
    # NO NEW OUTCOME (Codex T50 §9 opening): the evidence section adds no
    # estimand, no contrast and no threshold — it says so, and contains none.
    section = text.split("# Execution evidence")[1]
    if "No new outcome metric and no new decision threshold" not in section:
        problems.append("the evidence section does not state that it adds no outcome")
    for banned in ("Primary contrasts", "Δ delivery rate", "cost ratio", "bootstrap"):
        if banned in section:
            problems.append(f"the evidence section carries a decision-bearing table ({banned!r}) — it is "
                            f"audit evidence only")
    return check("the table renders the runtime HEAD and verified tree identity, the probe outcome per "
                 "configuration with inconclusive distinguished, journal health with takeover/recovery "
                 "events, the per-429 billed/rejected/current evidence with both dimension verdicts and the "
                 "combined bucket, the ledger gap/health status, and both censuses",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# Codex T51 (the second HOLD): the four START blockers, each with its own
# mutation witness. Reverting any one of the fixes must fail the witness that
# names it. NO LIVE PROVIDER CALL is made by any of them.
# --------------------------------------------------------------------------

def test_the_runtime_environment_is_sealed_as_bytes_not_versions():
    """Codex T51 §1 — the site-packages analogue of the module-shadow attack.

    `package_lock()` obtained `importlib.metadata.version()` for `openai` and
    `verifiers` plus the Python version; the startup witness recomputed the
    same version-level values. So an in-place edit to a file under
    `.venv/Lib/site-packages/openai/` could change request construction,
    retries, response interpretation or token accounting while `METADATA` still
    reported the sealed version — and the transitive packages were even less
    covered than the two named ones.

    THE MUTATION WITNESS he asks for (§1.4): append one comment byte to a real
    installed `.py`, WITHOUT touching its version metadata, and prove the
    witness goes red while `importlib.metadata.version` still reports the
    sealed version. The file's exact bytes are copied first and restored in a
    `finally`: this venv is shared by every process on the machine, and a
    witness that leaves it dirty is worse than no witness.
    """
    problems = []
    manifest = SA.runtime_environment_manifest(use_cache=False)
    sealed = SA.environment_manifest_digest(manifest)

    # 1. THE ROOTS COME FROM THE RUNNING INTERPRETER, never from a path
    #    relative to this checkout — a worktree has no `.venv` at all, and the
    #    digest must describe the interpreter that will execute cells.
    roots = SA.site_package_roots()
    if not roots:
        problems.append("the runtime-environment walk found no site-package root at all")
    for root in roots:
        if Path(sys.prefix).resolve() not in list(root.parents) + [root]:
            problems.append(f"a site-package root {root} is not under the running sys.prefix")
    # ... and they cover the STANDARD LIBRARY, which is what the instrument
    # imports on every request and what `python312.dll` does NOT contain.
    walked = SA.environment_roots()
    import sysconfig as _sysconfig
    stdlib = Path(_sysconfig.get_paths()["stdlib"]).resolve()
    if not any(root == stdlib or root in stdlib.parents for root in walked):
        problems.append(f"the standard library {stdlib} is outside the walked roots {walked}")
    for root in walked:
        # A root nested inside another would hash every installed file twice
        # under the same key and double the byte total.
        if any(other != root and other in root.parents for other in walked):
            problems.append(f"the walked roots are not maximal: {root} sits inside another")
    if manifest["stdlib_file_count"] < 100:
        problems.append(f"only {manifest['stdlib_file_count']} stdlib file(s) were hashed")
    # The stdlib directory is `Lib/` on Windows and `lib/python3.12/` on POSIX,
    # so the key is taken from `sysconfig`'s OWN stdlib path — the same source
    # the manifest uses — rather than from a hardcoded `/Lib/`. A hardcoded one
    # does not merely misreport: on the platform it does not match it turns
    # this row into a check of nothing at all.
    stdlib_key = SA._environment_key(stdlib)
    hashed = {key for key, _ in manifest["files"]}
    for module in ("json/encoder.py", "ssl.py", "subprocess.py"):
        if f"{stdlib_key}/{module}" not in hashed:
            problems.append(f"the stdlib's {module} — which shapes every provider request — is not "
                            f"hashed under {stdlib_key}/")
    site_prefixes = tuple(f"{SA._environment_key(r)}/" for r in SA.site_package_roots())
    if any(key.startswith(site_prefixes) for key in manifest["extra_files"]) and \
            len(manifest["extra_files"]) > 50:
        problems.append("the stdlib leaked into the no-RECORD-reference count and drowned its signal")
    source = Path(SA.__file__).read_text(encoding="utf-8")
    for banned in ('ROOT / ".venv"', "ROOT/'.venv'", 'Path(__file__).parent / ".venv"'):
        if banned in source:
            problems.append(f"the environment walk resolves the venv from the repository: {banned}")

    # 2. WHAT IS WALKED. Every installed distribution, its RECORD entries, the
    #    files no RECORD references, and the interpreter as bytes.
    if len(manifest["distributions"]) < 50:
        problems.append(f"only {len(manifest['distributions'])} distributions were enumerated — the "
                        f"seal must cover the transitives, not only openai and verifiers")
    if len(manifest["files"]) < 1000 or manifest["bytes"] < 10_000_000:
        problems.append(f"the walk is implausibly small: {len(manifest['files'])} files, "
                        f"{manifest['bytes']} bytes")
    if not any(d["record_present"] and d["record_entries"] for d in manifest["distributions"]):
        problems.append("no distribution's RECORD was enumerated at all")
    labels = {label for label, _key, _digest in manifest["interpreter"]}
    if "executable" not in labels:
        problems.append(f"the interpreter's own bytes are not in the manifest: {manifest['interpreter']}")
    if not any(label.startswith("runtime_library:") for label in labels):
        problems.append(f"no pythonXY runtime library was hashed: {manifest['interpreter']}")
    if manifest["python_version"] != sys.version:
        problems.append("sys.version is not carried in the manifest")
    for name in ("openai", "verifiers"):
        if not any(key.endswith("/RECORD") and f"/{name}-" in key for key, _ in manifest["files"]):
            problems.append(f"{name}'s own RECORD file is not hashed as bytes")
        if not any(f"/site-packages/{name}/" in key for key, _ in manifest["files"]):
            problems.append(f"no file of the installed {name} package was hashed")
    # `__pycache__` and `*.pyc` are excluded BY NAME (bytecode is written by
    # the act of importing, so a strict set would not be stationary across the
    # run it authenticates); everything else under the roots is in.
    for key, _digest in manifest["files"]:
        if "/__pycache__/" in key or key.endswith(".pyc"):
            problems.append(f"an excluded bytecode path entered the manifest: {key}")

    # 3. THE DIGEST IS BOUND EVERYWHERE (§1.3): schedule, startup witness, row
    #    provenance, table admission contract.
    identity = SA.instrument_identity()
    if identity.get("runtime_environment_digest") != sealed:
        problems.append("instrument_identity does not carry the runtime-environment digest")
    if mb.runtime_identity().get("runtime_environment_digest") != sealed:
        problems.append("measure_budget.runtime_identity does not carry it, so no row can")
    fixture = _sealed_schedule(label="envw")
    cell = fixture["cells"][0]
    expectations = SA.contract_expectations(fixture, cell)
    for field in ("runtime_environment_digest", "execution_tree_digest", "instrument_identity_version"):
        if field not in expectations:
            problems.append(f"{field} is not part of exact row admission")
    row = _cell_row(fixture, cell)
    if SA.row_mismatches(row, fixture, cell):
        problems.append(f"a row carrying the sealed instrument must be admitted: "
                        f"{SA.row_mismatches(row, fixture, cell)}")

    # 4. THE MUTATION WITNESS: one appended comment byte in a real installed
    #    `.py`, with the distribution's version metadata untouched.
    import importlib.metadata as importlib_metadata
    victim = None
    for key, _digest in manifest["files"]:
        if "/site-packages/openai/" in key and key.endswith(".py") and "__init__" not in key:
            victim = Path(sys.prefix) / Path(key.split("prefix/", 1)[1])
            break
    # The venv is shared by every process on this machine. Two batteries running
    # at once would each read the other's appended byte as "the original" and
    # restore it, leaving the file dirty for good (seen on 2026-09-05: the
    # startup witness then refused every later run with record_hash[openai]).
    # So: never mutate a file that already fails its wheel's RECORD hash, and
    # hold an O_EXCL lock beside it while the witness runs.
    already_dirty = [d for d in manifest["distributions"] if d["name"] == "openai" and d["declared_hash_mismatch"]]
    witness_lock = None
    if victim is not None and victim.is_file() and not already_dirty:
        # The lock lives OUTSIDE site-packages: a file beside the victim would itself be an
        # "extra file" in the environment walk and change the count the witness compares.
        import hashlib as _hashlib  # noqa: PLC0415
        import tempfile as _tempfile  # noqa: PLC0415
        witness_lock = Path(_tempfile.gettempdir()) / f"piv-venv-witness-{_hashlib.sha256(sys.prefix.encode('utf-8')).hexdigest()[:12]}.lock"
        for _attempt in range(120):                       # another witness holds it for a few seconds at most
            try:
                fd = os.open(str(witness_lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                time.sleep(0.5)
        else:
            witness_lock = None
            problems.append(f"could not take the witness lock {victim.name}.witness-lock within 60 s; "
                            "another battery is holding it or a crashed one left it behind")
    if victim is None or not victim.is_file():
        problems.append(f"no installed openai/*.py could be found to mutate: {victim}")
    elif already_dirty:
        problems.append("the shared venv is ALREADY dirty (openai RECORD hash mismatch: "
                        f"{already_dirty[0]['declared_hash_mismatch'][:3]}) — refusing to mutate on top of it; "
                        "restore the file from the wheel (uv cache) and rerun")
    elif witness_lock is None:
        pass                                              # the lock problem is already recorded
    else:
        version_before = importlib_metadata.version("openai")
        lock_before = SA.package_lock()
        original = victim.read_bytes()
        try:
            victim.write_bytes(original + b"\n#  one appended comment byte\n")
            after = SA.runtime_environment_manifest(use_cache=False)
            mutated_digest = SA.environment_manifest_digest(after)
            if mutated_digest == sealed:
                problems.append("A BYTE EDIT TO AN INSTALLED openai/*.py LEFT THE ENVIRONMENT DIGEST "
                                "UNCHANGED — this is exactly the T51 §1 attack, and the digest does not "
                                "see it")
            if len(after["files"]) != len(manifest["files"]):
                problems.append("an EDITED file must not change the file COUNT — the two rows say "
                                "different things")
            # The wheel's own RECORD declares a sha256 for this file, so the
            # per-distribution verdict names it too.
            openai_record = [d for d in after["distributions"] if d["name"] == "openai"]
            if openai_record and not openai_record[0]["declared_hash_mismatch"]:
                problems.append("the wheel's RECORD-declared sha256 no longer matches, and the manifest "
                                "does not say so")
            # ... while EVERY version-level fact is unchanged. This is the
            # whole point: "same package versions" cannot support "same
            # executable instrument".
            if importlib_metadata.version("openai") != version_before:
                problems.append("the mutation changed the distribution version — then it is not a "
                                "witness for the version-only identity")
            if SA.package_lock() != lock_before:
                problems.append("package_lock moved, so this witness does not isolate the byte edit")
            # THE STARTUP WITNESS GOES RED, by name.
            contract = dict(fixture["experiment_contract"])
            contract.update({
                "runtime_environment_identity_version": SA.RUNTIME_ENVIRONMENT_IDENTITY_VERSION,
                "runtime_environment_digest": sealed,
                "runtime_environment_file_count": len(manifest["files"]),
                "runtime_environment_extra_file_count": len(manifest["extra_files"]),
                "runtime_environment_stdlib_file_count": manifest["stdlib_file_count"],
                "runtime_environment_uncovered_sys_path": list(manifest["uncovered_sys_path"]),
                "python_version": manifest["python_version"],
                "execution_tree_digest": SA.execution_tree_digest(),
                "execution_tree_file_count": len(SA.execution_tree_manifest()["files"]),
                "instrument_commit": SA.git_head()})
            SA._ENVIRONMENT_MANIFEST = None                # the witness must re-walk
            red = {r["field"] for r in SW.failures(
                SW.identity_checks({"experiment_contract": contract}, check_tree=False))}
            if "runtime_environment_digest" not in red:
                problems.append(f"the startup witness stayed green through the byte edit: {sorted(red)}")
            if not any(f.startswith("record_hash[") for f in red):
                problems.append(f"the witness does not name the RECORD-declared hash mismatch: "
                                f"{sorted(red)}")
            # The per-CELL verification refuses too, and makes no provider call.
            if not mb.verify_instrument("cell", {"runtime_environment_digest": sealed}):
                problems.append("verify_instrument('cell') did not see the byte edit")
            if mb.verify_instrument("request", {"runtime_environment_digest": sealed}):
                problems.append("verify_instrument('request') must not walk the environment — it is "
                                "the per-CELL check that owns that cost")
        finally:
            victim.write_bytes(original)
            SA._ENVIRONMENT_MANIFEST = None
            try:
                witness_lock.unlink()
            except OSError:
                pass
        # 5. RESTORED: green again. A witness that cannot come back is not a
        #    witness, and this venv is shared by every process on the machine.
        if victim.read_bytes() != original:
            problems.append("the witness left the shared venv dirty")
        if SA.runtime_environment_digest(use_cache=False) != sealed:
            problems.append("restoring the exact bytes did not restore the environment digest")
        contract = dict(fixture["experiment_contract"])
        contract.update({
            "runtime_environment_identity_version": SA.RUNTIME_ENVIRONMENT_IDENTITY_VERSION,
            "runtime_environment_digest": sealed,
            "runtime_environment_file_count": len(manifest["files"]),
            "runtime_environment_extra_file_count": len(manifest["extra_files"]),
            "runtime_environment_stdlib_file_count": manifest["stdlib_file_count"],
            "runtime_environment_uncovered_sys_path": list(manifest["uncovered_sys_path"]),
            "python_version": manifest["python_version"],
            "execution_tree_digest": SA.execution_tree_digest(),
            "execution_tree_file_count": len(SA.execution_tree_manifest()["files"]),
            "instrument_commit": SA.git_head()})
        green = SW.failures(SW.identity_checks({"experiment_contract": contract}, check_tree=False))
        if green:
            problems.append(f"the witness is not green after restoring the bytes: "
                            f"{[r['field'] for r in green]}")

    # 6. AN EMPTY ENVIRONMENT PRODUCES NO DIGEST: one over nothing compares
    #    equal to one over nothing, so it would witness itself green forever.
    if SA.environment_manifest_digest({"files": []}) is not None:
        problems.append("an empty environment manifest must produce NO digest")
    return check("the runtime environment is sealed as BYTES — every installed distribution's RECORD "
                 "enumerated and its files hashed, the RECORD-declared sha256 verified, the files no "
                 "RECORD references included, the interpreter itself hashed, the roots taken from the "
                 "running interpreter — and one appended comment byte in an installed openai/*.py turns "
                 "the witness red while importlib.metadata.version and package_lock stay identical",
                 not problems, "\n".join(problems))


def test_the_instrument_is_verified_per_cell_and_per_request_and_drift_makes_no_call():
    """Codex T51 §2 — "the execution-tree seal is checked once, but the
    experiment lasts 6–7 hours".

    His concrete bad execution: pass startup, change an executable file before
    a later cell, let that fresh subprocess write a row bearing the changed
    digest, and render the table. The old `render_instrument_identity` reported
    "DIFFERENT from the sealed instrument tree" and computed the confirmatory
    estimates anyway.

    Four things are witnessed here, none of them with a live provider call:

      1. the digests are re-verified IMMEDIATELY BEFORE every provider request,
         and a drifted instrument raises before the request function is ever
         reached — the wire hook counts zero calls;
      2. the executor hands the sealed digests down to the cell subprocess, and
         that subprocess refuses END TO END: exit 6, no row file, nothing spent;
      3. a mid-session tree change before cell N stops the SESSION, journalled
         `instrument_drift` fail-closed, with no further cell attempted;
      4. a row from a foreign instrument — or one carrying no instrument
         identity at all — is refused from exact admission AND makes the table
         exit 4. A warning paragraph is not sufficient.
    """
    import contextlib
    import io
    import subprocess
    import tempfile
    import verifiers.legacy.clients.openai_chat_completions_client as oai_mod
    problems = []
    sealed_tree = SA.execution_tree_digest()
    sealed_env = SA.runtime_environment_digest()

    # ---- 1. BEFORE EVERY PROVIDER REQUEST -------------------------------
    calls: list = []

    async def fake_post(client, path, *, body, extra_headers=None):
        calls.append(body)
        raise AssertionError("a provider request was made under a drifted instrument")

    client = mb.make_client_cls(0.0, True)(DUMMY_CONFIG)
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    original_post = oai_mod.post_chat_completion_with_routed_experts_sidecar
    oai_mod.post_chat_completion_with_routed_experts_sidecar = fake_post
    saved_seal = mb.sealed_instrument()
    try:
        mb.set_sealed_instrument(execution_tree_digest="0" * 64)
        try:
            asyncio.run(client.get_native_response(messages, "m", {"max_tokens": 10}, None))
            problems.append("a drifted execution tree did not stop the request")
        except mb.InstrumentDrift as exc:
            if "execution_tree_digest" not in str(exc):
                problems.append(f"the refusal must name the digest that moved: {exc}")
        if calls:
            problems.append(f"{len(calls)} provider request(s) went out under a drifted instrument")
        # The check is the LAST thing before the request, and it is a
        # BaseException so no `except Exception` can log it as an attempt.
        if client.requests:
            problems.append(f"a drifted request was recorded as a provider attempt: {client.requests}")
        if not issubclass(mb.InstrumentDrift, BaseException) or issubclass(mb.InstrumentDrift, Exception):
            problems.append("InstrumentDrift must be a BaseException: an `except Exception` in the "
                            "framework would otherwise turn a drifted instrument into a logged attempt")
        # The per-REQUEST scope walks the tree only; the per-CELL scope walks
        # both. That is the measured cost split, and it is a real difference.
        if mb.verify_instrument("request", {"runtime_environment_digest": "0" * 64}):
            problems.append("the per-request check walks the environment — 3.3 s per request is 80 s a "
                            "rollout and 3.3 h over the panel")
        if not mb.verify_instrument("cell", {"runtime_environment_digest": "0" * 64}):
            problems.append("the per-cell check does not walk the environment")
        if mb.verify_instrument("cell", {"execution_tree_digest": sealed_tree,
                                         "runtime_environment_digest": sealed_env}):
            problems.append("the sealed instrument does not verify against itself")
        if mb.verify_instrument("cell", {}):
            problems.append("an UNARMED process must verify nothing — a bare measure_budget.py run "
                            "registered nothing and has nothing to betray")
        # The environment digest is re-walked, never taken from the process
        # cache: a cached value would make a cell's closing check agree with
        # its own opening check by construction.
        source = Path(mb.__file__).read_text(encoding="utf-8")
        if "runtime_environment_digest(use_cache=False)" not in source:
            problems.append("the per-cell environment check reuses the process cache")
        if 'require_instrument("request"' not in source:
            problems.append("no per-request verification is wired into the pacing path")
    finally:
        oai_mod.post_chat_completion_with_routed_experts_sidecar = original_post
        mb.set_sealed_instrument(**saved_seal) if saved_seal else mb.set_sealed_instrument()

    # ---- 2. THE CELL SUBPROCESS REFUSES END TO END ----------------------
    #        A real process, a wrong sealed digest, and no provider call: the
    #        check runs before `configure_provider`, before the key is read and
    #        before the world is minted.
    with tempfile.TemporaryDirectory() as directory:
        proc = subprocess.run(
            [sys.executable, str(Path(mb.__file__)), "--model", "no/such-model",
             "--provider", "mistral", "--selectors", "train:1", "--arm", "A",
             "--tag", "t51driftwitness", "--stamp-date", "2026-08-31",
             "--sealed-execution-tree-digest", "0" * 64,
             "--sealed-runtime-environment-digest", sealed_env,
             "--sealed-instrument-identity-version", str(SA.INSTRUMENT_IDENTITY_VERSION)],
            cwd=str(Path(mb.__file__).resolve().parents[1]), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600)
        if proc.returncode != mb.INSTRUMENT_DRIFT_EXIT:
            problems.append(f"a drifted cell must exit {mb.INSTRUMENT_DRIFT_EXIT}, got {proc.returncode}: "
                            f"{(proc.stderr or '')[-400:]}")
        if "INSTRUMENT DRIFT" not in (proc.stderr or ""):
            problems.append(f"the cell's refusal must name instrument drift: {(proc.stderr or '')[-300:]}")
        leaked = sorted((Path(mb.__file__).resolve().parents[1] / "reviews")
                        .glob("budget_*t51driftwitness*"))
        if leaked:
            problems.append(f"a drifted cell wrote output: {[p.name for p in leaked]}")
            for path in leaked:
                path.unlink()
        _ = directory

    # ---- 3. THE EXECUTOR STOPS THE SESSION ------------------------------
    #        Real `run_arms._main`, real startup witness, real journal — only
    #        the cell subprocess and the capability probe are scripted.
    contract = SA.build_experiment_contract(["A", "B1", "B2"], ["train:1"], 40_000, SA.ANALYSIS_PLAN)
    schedule = _sealed_schedule(label="t51drift", selectors=["train:1"], contract=dict(contract))
    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        path = reviews / "schedule_t51drift.json"
        path.write_text(json.dumps(schedule, default=str), encoding="utf-8")
        commands: list = []

        class _Fake:
            def __init__(self, code):
                self.returncode, self.stdout, self.stderr = code, "", "INSTRUMENT DRIFT (scripted)"

        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            return _Fake(mb.INSTRUMENT_DRIFT_EXIT if len(commands) == 2 else 0)

        # The shim replaces run_arms' OWN `subprocess` name, never the module's
        # `run` attribute: `schedule_arms._git` shares that module object, and
        # patching it globally makes every `git` call return the fake — which
        # is how this witness first "proved" that a startup witness refuses a
        # checkout it was sealed from.
        saved = (RA.subprocess, mb.probe_configuration, SA.git_execution_tree_status)
        RA.subprocess = types.SimpleNamespace(run=fake_run)
        mb.probe_configuration = lambda *a, **k: {"admissible": True, "conclusive": True, "policies": {}}
        # The git working tree is EVIDENCE-dirty while this suite runs; that
        # row has its own witness, and this one is about the drift branch.
        SA.git_execution_tree_status = lambda *a, **k: (True, "clean (scripted for this witness)")
        err, out = io.StringIO(), io.StringIO()
        saved_argv = sys.argv
        sys.argv = ["run_arms.py", "--schedule", str(path), "--reviews-dir", str(reviews)]
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                code = RA.main()
        finally:
            sys.argv = saved_argv
            RA.subprocess, mb.probe_configuration, SA.git_execution_tree_status = saved
            # `run_arms` arms THIS process for its own capability-probe calls;
            # disarm so the module state does not leak into a later witness.
            mb.set_sealed_instrument()
        if "REFUSED before request 1" in err.getvalue():
            problems.append(f"the startup witness refused this witness's own checkout: "
                            f"{err.getvalue()[:400]}")
        if code != mb.INSTRUMENT_DRIFT_EXIT:
            problems.append(f"a drifted cell must stop the session with exit "
                            f"{mb.INSTRUMENT_DRIFT_EXIT}, got {code}: {err.getvalue()[-300:]}")
        if len(commands) != 2:
            problems.append(f"the session must stop AT the drifted cell: {len(commands)} of "
                            f"{schedule['n_cells']} cells were attempted")
        # The sealed digests are handed down to every cell.
        #
        # A session that REFUSED before cell 1 builds no command at all, and a
        # flag whose value is missing leaves it as the last element: indexing
        # `commands[0]` or `index(flag) + 1` blind crashes the whole file and
        # takes every witness after this one down with it. Both absences are
        # reported the same way every other disagreement here is.
        first = commands[0] if commands else []
        for flag, want in (("--sealed-execution-tree-digest", contract["execution_tree_digest"]),
                           ("--sealed-runtime-environment-digest", contract["runtime_environment_digest"])):
            carried = first[first.index(flag) + 1] if flag in first[:-1] else None
            if carried != want:
                problems.append(f"the cell command does not carry {flag}: {carried!r} (sealed {want!r}; "
                                f"{len(commands)} command(s) were built)")
        journal = AT.load_execution_journal(SA.journal_path_for(reviews, schedule))
        events = [e.get("event") for e in journal["events"]]
        if "instrument_drift" not in events:
            problems.append(f"the drift was not journalled: {sorted(set(events))}")
        if not any(e.get("event") == "execution_integrity" and e.get("reason") == "instrument_drift"
                   for e in journal["events"]):
            problems.append("the drifted cell was not quarantined as execution_integrity/instrument_drift")
        for entry in journal["events"]:
            if entry.get("event") == "cell_started" and "runtime_environment_digest" not in entry:
                problems.append("journal entries do not carry the runtime environment identity")
                break

    # ---- 4. HARD ADMISSION, NOT A WARNING -------------------------------
    fixture = _sealed_schedule(label="t51admit")
    cell = fixture["cells"][0]
    good = _cell_row(fixture, cell)
    for label, mutation in (("a foreign execution tree", {"execution_tree_digest": "0" * 64}),
                            ("a foreign environment", {"runtime_environment_digest": "0" * 64}),
                            ("no instrument identity at all",
                             {"execution_tree_digest": None, "runtime_environment_digest": None,
                              "instrument_identity_version": None})):
        row = dict(good)
        row.update(mutation)
        if not SA.row_mismatches(row, fixture, cell):
            problems.append(f"{label}: the row was admitted as this cell's row")
        if not AT.instrument_drift_rows([row], fixture):
            problems.append(f"{label}: arm_table does not name the drift")
        rendered = AT.render_table([row], "t", [], fixture, False, False, ("A", "B1", "B2"), "A")
        if "CONFIRMATORY ESTIMANDS REFUSED" not in rendered:
            problems.append(f"{label}: the table does not state the refusal")
    if AT.instrument_drift_rows([good], fixture):
        problems.append("a row carrying the sealed instrument must not be called drifted")

    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        path = reviews / "schedule_t51admit.json"
        path.write_text(json.dumps(fixture, default=str), encoding="utf-8")
        # One cell file whose row is exactly the cell except for the tree
        # digest: the panel must refuse, not annotate.
        drifted = dict(good)
        drifted["execution_tree_digest"] = "0" * 64
        out_path = SA.output_path_for(reviews, cell["model"], fixture["date_stamp"], cell["tag"])
        out_path.write_text(json.dumps([drifted], default=str), encoding="utf-8")
        loaded = AT.load_scheduled_rows(reviews, fixture)
        if drifted in loaded["rows"]:
            problems.append("a drifted row entered the confirmatory dataset")
        if not any("execution_tree_digest" in item for item in loaded["integrity"]):
            problems.append(f"the drifted row is not quarantined by name: {loaded['integrity']}")
        err = io.StringIO()
        saved_argv = sys.argv
        sys.argv = ["arm_table.py", "--label", "t51admit", "--schedule", str(path),
                    "--reviews-dir", str(reviews)]
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = AT.main()
        finally:
            sys.argv = saved_argv
        if code != 4:
            problems.append(f"a panel whose only row is drifted must exit 4 NAMING the drift, not merely "
                            f"report 'no rows to read': got {code}")
        if "instrument/environment digest" not in err.getvalue():
            problems.append(f"the refusal does not name the instrument: {err.getvalue()[-200:]}")
    return check("both digests are verified before request 1 of every cell, the execution tree before "
                 "EVERY provider request and both again after the last write; a drifted instrument makes "
                 "no provider call, writes no row, exits 6 and STOPS the session with a fail-closed "
                 "instrument_drift journal entry; and a row carrying a foreign or missing instrument "
                 "digest is refused from exact admission and from every estimand, not annotated",
                 not problems, "\n".join(problems))


def test_a_corrupt_execution_journal_fails_closed_and_recovers_only_after_rows_exist():
    """Codex T51 §4 — the execution journal was append-only in INTENT but not
    fail-closed on corruption.

    `journal()` appended under the lock without validating the existing
    records; `journal_probe()` appended a token and checked that its OWN token
    came back, which an already-truncated line does not disturb. So a crash
    during an append left a malformed TAIL, the next startup appended a
    successful probe after it, and the malformed tail became a malformed
    MIDDLE — the audit events that explain takeover, recovery, inconclusive
    classification and integrity state stopped being a complete
    machine-readable sequence, while the confirmatory table still rendered.

    Both damage shapes are witnessed, neither may reach a provider call or an
    ordinary confirmatory table, and the recovery policy is his own Q4 answer:
    abort-and-reseal BEFORE the first real row, explicit segment recovery only
    after rows exist.
    """
    import contextlib
    import io
    import tempfile
    problems = []
    healthy_line = json.dumps({"event": "cell_started", "tag": "t", "at": "2026-08-31T10:00:00"}) + "\n"

    def damaged(directory, shape):
        """A journal with a malformed TAIL or a malformed MIDDLE. The middle
        case is exactly what the old probe MANUFACTURED out of the tail case."""
        path = Path(directory) / "arms_x_execution.jsonl"
        if shape == "tail":
            path.write_text(healthy_line + '{"event": "cell_fini', encoding="utf-8")
        else:
            path.write_text(healthy_line + '{"event": "cell_fini' + healthy_line + healthy_line,
                            encoding="utf-8")
        return path

    for shape in ("tail", "middle"):
        with tempfile.TemporaryDirectory() as directory:
            path = damaged(directory, shape)
            before = path.read_bytes()
            health = RA.journal_health(path)
            if health["healthy"]:
                problems.append(f"{shape}: a malformed line left the journal 'healthy': {health}")
            # 1. NO APPEND. Not in confirmatory mode, and not in the pilot's
            #    lenient mode either: damaged evidence is not a condition a
            #    pilot gets to shrug off.
            for required in (True, False):
                try:
                    RA.journal(path, {"event": "cell_started"}, required=required)
                    problems.append(f"{shape}: an append landed on a corrupt journal "
                                    f"(required={required})")
                except RA.JournalCorrupt:
                    pass
            if path.read_bytes() != before:
                problems.append(f"{shape}: the corrupt journal's bytes were modified by a refused append")
            # 2. THE PROBE FAILS. The old probe passed here — its own token
            #    came back — and the append it made turned the tail into a
            #    middle.
            ok, detail = RA.journal_probe(path)
            if ok:
                problems.append(f"{shape}: the pre-request probe passed on a corrupt journal")
            if "CORRUPT" not in detail:
                problems.append(f"{shape}: the probe's refusal does not say the journal is corrupt: "
                                f"{detail[:120]}")
            if path.read_bytes() != before:
                problems.append(f"{shape}: the probe WROTE to a corrupt journal — this is precisely how "
                                f"a malformed tail becomes a malformed middle")
            # 3. THE STARTUP WITNESS GOES RED, so no provider call is reached.
            schedule = _sealed_schedule(label="x")
            results = RA.startup_results(schedule, Path(directory))
            row = {r["field"]: r for r in results}.get("execution_journal")
            if row is None or row["ok"]:
                problems.append(f"{shape}: the startup witness admits a corrupt execution journal: {row}")

    # 4. THE EXECUTOR REFUSES BEFORE REQUEST 1, end to end, and the bytes are
    #    untouched — the same C3 ordering the ledger recovery follows.
    contract = SA.build_experiment_contract(["A", "B1", "B2"], ["train:1"], 40_000, SA.ANALYSIS_PLAN)
    schedule = _sealed_schedule(label="t51journal", selectors=["train:1"], contract=dict(contract))
    for shape in ("tail", "middle"):
        with tempfile.TemporaryDirectory() as directory:
            reviews = Path(directory)
            path = reviews / "schedule_t51journal.json"
            path.write_text(json.dumps(schedule, default=str), encoding="utf-8")
            journal_file = SA.journal_path_for(reviews, schedule)
            if shape == "tail":
                journal_file.write_text(healthy_line + '{"event": "cell_fini', encoding="utf-8")
            else:
                journal_file.write_text(healthy_line + '{"event": "x' + healthy_line, encoding="utf-8")
            before = journal_file.read_bytes()
            calls: list = []
            saved = (RA.subprocess, mb.probe_configuration, SA.git_execution_tree_status)
            RA.subprocess = types.SimpleNamespace(run=lambda cmd, **k: calls.append(cmd))
            mb.probe_configuration = lambda *a, **k: calls.append("probe")
            SA.git_execution_tree_status = lambda *a, **k: (True, "clean (scripted for this witness)")
            err, saved_argv = io.StringIO(), sys.argv
            sys.argv = ["run_arms.py", "--schedule", str(path), "--reviews-dir", str(reviews)]
            try:
                with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                    code = RA.main()
            finally:
                sys.argv = saved_argv
                RA.subprocess, mb.probe_configuration, SA.git_execution_tree_status = saved
                mb.set_sealed_instrument()          # do not leak the armed state
            if code != 3:
                problems.append(f"{shape}: a corrupt journal must refuse the session at the startup "
                                f"witness (exit 3), got {code}")
            if calls:
                problems.append(f"{shape}: {len(calls)} provider-touching call(s) were made anyway")
            if journal_file.read_bytes() != before:
                problems.append(f"{shape}: the damaged bytes were modified by the refused session")
            if "execution_journal" not in err.getvalue():
                problems.append(f"{shape}: the refusal does not name the execution journal")

            # 5. RECOVERY IS REFUSED BEFORE THE FIRST REAL ROW (his Q4): there
            #    is no recovery path there — abort and RESEAL.
            err, saved_argv = io.StringIO(), sys.argv
            sys.argv = ["run_arms.py", "--schedule", str(path), "--reviews-dir", str(reviews),
                        "--recover-execution-journal"]
            saved = SA.git_execution_tree_status
            SA.git_execution_tree_status = lambda *a, **k: (True, "clean (scripted for this witness)")
            try:
                with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                    code = RA.main()
            finally:
                sys.argv = saved_argv
                SA.git_execution_tree_status = saved
            if code != 2:
                problems.append(f"{shape}: recovery before the first row must be refused (exit 2), "
                                f"got {code}")
            if "ABORT AND RESEAL" not in err.getvalue():
                problems.append(f"{shape}: the refusal must name the policy: {err.getvalue()[-200:]}")
            if journal_file.read_bytes() != before:
                problems.append(f"{shape}: a refused recovery still wrote to the journal")

            # 6. AFTER A REAL ROW EXISTS, the segment recovery runs: an
            #    immutable boundary, a provenance record, the bytes preserved.
            cell = schedule["cells"][0]
            out_path = SA.output_path_for(reviews, cell["model"], schedule["date_stamp"], cell["tag"])
            out_path.write_text(json.dumps([_cell_row(schedule, cell)], default=str), encoding="utf-8")
            if RA.cell_status(out_path, schedule, cell)[0] != "done":
                problems.append(f"{shape}: the witness could not make one real row: "
                                f"{RA.cell_status(out_path, schedule, cell)}")
            calls = []
            saved = (RA.subprocess, mb.probe_configuration, SA.git_execution_tree_status)
            RA.subprocess = types.SimpleNamespace(run=lambda cmd, **k: calls.append(cmd))
            mb.probe_configuration = lambda *a, **k: {"admissible": True, "conclusive": True,
                                                      "policies": {}}
            SA.git_execution_tree_status = lambda *a, **k: (True, "clean (scripted for this witness)")
            err, out, saved_argv = io.StringIO(), io.StringIO(), sys.argv
            sys.argv = ["run_arms.py", "--schedule", str(path), "--reviews-dir", str(reviews),
                        "--recover-execution-journal", "--dry-run"]
            try:
                with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                    code = RA.main()
            finally:
                sys.argv = saved_argv
                RA.subprocess, mb.probe_configuration, SA.git_execution_tree_status = saved
                mb.set_sealed_instrument()          # do not leak the armed state
            if code != 0:
                problems.append(f"{shape}: recovery after a real row must succeed, got {code}: "
                                f"{err.getvalue()[-300:]}")
            if "EXECUTION JOURNAL RECOVERED" not in out.getvalue():
                problems.append(f"{shape}: the recovery is not announced")
            recovered = journal_file.read_bytes()
            if not recovered.startswith(before):
                problems.append(f"{shape}: the damaged bytes were not PRESERVED — recovery is a segment "
                                f"boundary, never a repair")
            scan = SA.journal_scan(journal_file)
            if not scan["healthy"]:
                problems.append(f"{shape}: the journal is still unhealthy after recovery: "
                                f"{scan['detail']}")
            if not scan["malformed"]:
                problems.append(f"{shape}: recovery must ACKNOWLEDGE the malformed lines, not erase the "
                                f"record of them")
            if len(scan["recoveries"]) != 1:
                problems.append(f"{shape}: expected exactly one segment boundary: {scan['recoveries']}")
            boundary = scan["recoveries"][0]
            for field in ("segment", "acknowledged_through_line", "malformed_lines", "reason",
                          "session_id", "operator", "runtime_head", "execution_tree_digest",
                          "runtime_environment_digest"):
                if field not in boundary:
                    problems.append(f"{shape}: the provenance record has no {field}")
            # An append works again, and the table reads CLEAN WITH A NOTE.
            if not RA.journal(journal_file, {"event": "cell_started", "tag": "after"}, required=True):
                problems.append(f"{shape}: the journal is not appendable after recovery")
            loaded = AT.load_execution_journal(journal_file)
            if not loaded["healthy"] or loaded["outstanding"]:
                problems.append(f"{shape}: the table does not read the recovered journal as clean")
            rendered = "\n".join(AT.render_journal_health(loaded))
            if "CLEAN WITH A NOTE" not in rendered or "Audit segment boundaries" not in rendered:
                problems.append(f"{shape}: the recovered segment is not rendered as clean-with-a-note")

    # 7. THE TABLE REFUSES CONFIRMATORY ESTIMANDS on an unrecovered journal.
    fixture = _sealed_schedule(label="t51tab")
    with tempfile.TemporaryDirectory() as directory:
        reviews = Path(directory)
        path = reviews / "schedule_t51tab.json"
        path.write_text(json.dumps(fixture, default=str), encoding="utf-8")
        journal_file = SA.journal_path_for(reviews, fixture)
        journal_file.write_text(healthy_line + '{"event": "cell_fini', encoding="utf-8")
        for cell in fixture["cells"]:
            out_path = SA.output_path_for(reviews, cell["model"], fixture["date_stamp"], cell["tag"])
            out_path.write_text(json.dumps([_cell_row(fixture, cell)], default=str), encoding="utf-8")
        err, out, saved_argv = io.StringIO(), io.StringIO(), sys.argv
        sys.argv = ["arm_table.py", "--label", "t51tab", "--schedule", str(path),
                    "--reviews-dir", str(reviews)]
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                code = AT.main()
        finally:
            sys.argv = saved_argv
        if code != 4:
            problems.append(f"an unhealthy execution journal must refuse the confirmatory estimands "
                            f"(exit 4), got {code}")
        if "execution journal is UNHEALTHY" not in err.getvalue():
            problems.append(f"the refusal does not name the journal: {err.getvalue()[-200:]}")
        if "CONFIRMATORY ESTIMANDS REFUSED" not in out.getvalue():
            problems.append("the written table does not state the refusal")
        # ... and admits it once the damage is acknowledged by a boundary.
        RA.journal_recover(journal_file, reason="witness", session_id="s", operator="witness")
        err, saved_argv = io.StringIO(), sys.argv
        sys.argv = ["arm_table.py", "--label", "t51tab", "--schedule", str(path),
                    "--reviews-dir", str(reviews)]
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = AT.main()
        finally:
            sys.argv = saved_argv
        if code != 0:
            problems.append(f"a journal with an acknowledged segment boundary is clean-with-a-note and "
                            f"must not refuse: exit {code}, {err.getvalue()[-300:]}")
    # 8. Recovery on a HEALTHY journal is refused: it is not a routine flag.
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "clean.jsonl"
        RA.journal(path, {"event": "cell_started"}, required=True)
        record = RA.journal_recover(path, reason="nothing wrong", session_id="s")
        if record.get("recovered") is not False:
            problems.append("recovery of a healthy journal must be a no-op")
    return check("the whole execution journal is parsed under the lock before every append and before the "
                 "probe; a malformed TAIL and a malformed MIDDLE each fail closed with the bytes "
                 "untouched, neither reaches a provider call, and neither renders an ordinary "
                 "confirmatory table; recovery is refused before the first real row (abort and reseal) "
                 "and after rows exist is an immutable segment boundary with a provenance record that "
                 "the table reads as clean-with-a-note",
                 not problems, "\n".join(problems))


def _environment_contract(manifest, fixture):
    """The sealed-contract fields the identity rows are checked against, taken
    from an already-computed manifest so a witness call is a comparison and
    not a second walk."""
    contract = dict(fixture["experiment_contract"])
    contract.update({
        "runtime_environment_identity_version": SA.RUNTIME_ENVIRONMENT_IDENTITY_VERSION,
        "runtime_environment_digest": SA.environment_manifest_digest(manifest),
        "runtime_environment_file_count": len(manifest["files"]),
        "runtime_environment_extra_file_count": len(manifest["extra_files"]),
        "runtime_environment_stdlib_file_count": manifest["stdlib_file_count"],
        "runtime_environment_uncovered_sys_path": list(manifest["uncovered_sys_path"]),
        "python_version": manifest["python_version"],
        "execution_tree_digest": SA.execution_tree_digest(),
        "execution_tree_file_count": len(SA.execution_tree_manifest()["files"]),
        "instrument_commit": SA.git_head()})
    return contract


def test_the_import_environment_and_the_bytecode_cache_are_sealed():
    """The three perimeter bypasses the adversarial review of the T51 closures
    found, each with its own witness. All three change what the interpreter
    EXECUTES without changing one byte the T51 manifest hashed.

    C1  `PYTHONPATH` was not in the walk. A directory named there is prepended
        to `sys.path`, so it shadows any sealed module — `openai/`, `json/`,
        `ssl.py` — while every hashed byte, and therefore the digest, stays
        identical; and `run_arms` handed `os.environ` to every cell subprocess
        whole. Closed on both sides: the manifest surveys `sys.path` and
        reports what nothing covers, so the startup witness refuses BEFORE the
        strip could hide an injection that was live at startup; and the
        executor strips the injecting variables from every confirmatory cell
        and journals that it did.

    C2  An existing `.pyc` edited IN PLACE keeps the source mtime and size
        recorded in its own header, so timestamp validation accepts it
        forever: the tampered body executes, the sealed `.py` is never read,
        and `*.pyc` is excluded from the manifest by name. Closed by
        redirecting `PYTHONPYCACHEPREFIX` to a FRESH per-session directory for
        this process and every cell, so no pre-existing cache is on the path
        at all. The witness below is end-to-end: a real tampered `.pyc` that a
        plain subprocess DOES execute, and that the same subprocess under a
        fresh prefix does not.

    C3  Four real `sys.path` members were outside the walk — the EXTENSION
        MODULE directory (37 modules, `_ssl` among them), the `pythonXY.zip`
        slot, `prefix/pyvenv.cfg`, and every file in the CONSOLE SCRIPT
        directory that no RECORD references. Closed by taking the roots from
        `sys.path` itself.

        The first, second and fourth of those have a different NAME on every
        platform — `base_prefix/DLLs/*.pyd` and `prefix/Scripts/` and
        `base_prefix/pythonXY.zip` on Windows, `<stdlib>/lib-dynload/*.so` and
        `prefix/bin/` and `base_prefix/lib/pythonXY.zip` on POSIX — so this
        witness asks `SA.interpreter_layout()` (which asks `sysconfig`) what
        they are called here rather than spelling one platform's answer. A
        witness that names `DLLs/` literally is green on Windows and red
        everywhere else while the seal it is about is perfectly sound.

    THE SHARED-VENV RULE. This interpreter is shared by every process on the
    machine. The two files this test adds are uniquely named, removed in a
    `finally`, and the restoration is VERIFIED by recomputing the digest and
    demanding the sealed value back.
    """
    problems = []
    import importlib.util as importlib_util
    import marshal
    import subprocess as _subprocess
    import tempfile as _tempfile
    import uuid as _uuid
    manifest = SA.runtime_environment_manifest(use_cache=False)
    sealed = SA.environment_manifest_digest(manifest)
    fixture = _sealed_schedule(label="perim")
    keys = {key for key, _digest in manifest["files"]}

    # ---------------------------------------------------------------- C3 --
    # What the walk now covers, by name — under THIS platform's names for the
    # four members, resolved from `sysconfig` by `SA.interpreter_layout()`.
    # Each of them was outside the walk.
    survey = {key: status for key, status in manifest["sys_path"]}
    layout = SA.interpreter_layout()
    extension_prefix = SA._environment_key(layout["extension_dir"]) + "/"
    scripts_prefix = SA._environment_key(layout["scripts_dir"]) + "/"
    zip_key = SA._environment_key(layout["zip_slot"])
    if "prefix/pyvenv.cfg" not in keys:
        problems.append("C3: prefix/pyvenv.cfg — which names the interpreter this venv points at and "
                        "whether the system site-packages are visible — is not hashed")
    extensions = sorted(k for k in keys if k.startswith(extension_prefix)
                        and k.endswith(layout["extension_suffix"]))
    if len(extensions) < 10:
        problems.append(f"C3: {extension_prefix.rstrip('/')} holds the extension modules every provider "
                        f"request runs through (_ssl, _socket, select) and only {len(extensions)} "
                        f"{layout['extension_suffix']} are hashed")
    scripts = sorted(k for k in keys if k.startswith(scripts_prefix))
    if not any(k.rsplit("/", 1)[-1].startswith("activate") for k in scripts):
        problems.append(f"C3: {scripts_prefix.rstrip('/')} is hashed only where a RECORD references it "
                        f"— the activate shims are not in the manifest: {scripts[:8]}")
    zip_slots = [k for k, status in survey.items() if k.endswith(".zip")]
    if zip_key not in survey:
        problems.append(f"C3: the pythonXY.zip sys.path slot {zip_key} is not surveyed at all — it "
                        f"PRECEDES the standard library, so creating it shadows every module in it: "
                        f"{sorted(survey)}")
    for slot in zip_slots:
        if survey[slot] not in ("absent", "file"):
            problems.append(f"C3: the {slot} slot is recorded as {survey[slot]!r}; it must be sealed "
                            f"either as bytes or as ABSENT — creating it shadows the whole stdlib")
    if not any(status == "execution_tree" for status in survey.values()):
        problems.append(f"C3: the package directory and tests/ are sys.path[0] and sys.path[1] for "
                        f"every process here and must be recorded as sealed by the EXECUTION TREE, "
                        f"not left unclassified: {survey}")

    # ... and a file ADDED where nothing referenced one moves both the digest
    # and the count. Two additions, one walk: the CONSOLE SCRIPT directory
    # (where only RECORD entries used to be seen) and the EXTENSION MODULE
    # directory (not walked at all) — `Scripts/` and `base_prefix/DLLs` on
    # Windows, `prefix/bin` and `<stdlib>/lib-dynload` on POSIX.
    nonce = _uuid.uuid4().hex[:12]
    added = [layout["scripts_dir"] / f"_piv_c3_witness_{nonce}{layout['script_suffix']}",
             layout["extension_dir"] / f"_piv_c3_witness_{nonce}{layout['extension_suffix']}"]
    written = []
    try:
        for path in added:
            try:
                path.write_bytes(b"; piv C3 witness, removed by the finally below\n")
                written.append(path)
            except OSError as exc:                                         # noqa: BLE001, PERF203
                problems.append(f"C3: could not write the witness file {path}: {exc}")
        if written:
            after = SA.runtime_environment_manifest(use_cache=False)
            if SA.environment_manifest_digest(after) == sealed:
                problems.append(f"C3: {len(written)} NEW file(s) under {scripts_prefix.rstrip('/')} "
                                f"and {extension_prefix.rstrip('/')} left the environment digest "
                                f"unchanged — the perimeter is still open")
            if len(after["files"]) != len(manifest["files"]) + len(written):
                problems.append(f"C3: the file COUNT did not move by {len(written)}: "
                                f"{len(manifest['files'])} -> {len(after['files'])}")
            # The witness reads the same walk (the documented one-walk-per-
            # process cache) rather than paying for a second one.
            SA._ENVIRONMENT_MANIFEST = after
            red = {r["field"] for r in SW.failures(SW.identity_checks(
                {"experiment_contract": _environment_contract(manifest, fixture)}, check_tree=False))}
            if "runtime_environment_file_count" not in red or "runtime_environment_digest" not in red:
                problems.append(f"C3: the startup witness stayed green through the added files: "
                                f"{sorted(red)}")
    finally:
        for path in written:
            try:
                path.unlink()
            except OSError:                                                # noqa: BLE001, PERF203
                pass
        SA._ENVIRONMENT_MANIFEST = None
    for path in added:
        if path.exists():
            problems.append(f"C3: the witness left {path} behind in the SHARED interpreter")
    restored = SA.runtime_environment_manifest(use_cache=False)
    if SA.environment_manifest_digest(restored) != sealed:
        problems.append("C3: removing the added files did not restore the sealed digest — the witness "
                        "did not put the shared interpreter back")

    # ---------------------------------------------------------------- C1 --
    shadow = Path(_tempfile.mkdtemp(prefix="piv_c1_shadow_"))
    try:
        # A concrete shadow, named after the library whose request construction
        # it would replace. Harmless here: `openai` is already in
        # `sys.modules` (measure_budget imported it at module load), so a later
        # `import openai` returns the real one from the cache.
        (shadow / "openai.py").write_text("SHADOW = 'an unsealed module on sys.path'\n",
                                          encoding="utf-8")

        # (i) A `PYTHONPATH` set at process start really does put an unsealed
        #     directory on `sys.path`, and the survey names it. Run as a real
        #     subprocess, because reading the variable is the only way to
        #     witness that half at all.
        env = dict(os.environ)
        env["PYTHONPATH"] = str(shadow)
        env.pop("PYTHONPYCACHEPREFIX", None)
        probe = _subprocess.run(
            [sys.executable, "-c",
             "import json, sys; sys.path.insert(0, r'" + str(ROOT / "tests") + "'); "
             "import schedule_arms as SA; "
             "print(json.dumps(SA.sys_path_survey()['uncovered']))"],
            cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300)
        reported = None
        if probe.returncode == 0 and (probe.stdout or "").strip():
            reported = json.loads((probe.stdout or "").strip().splitlines()[-1])
        if reported is None:
            problems.append(f"C1: the PYTHONPATH probe subprocess failed: "
                            f"{(probe.stderr or '')[-400:]}")
        elif not any(shadow.resolve().as_posix() in entry for entry in reported):
            problems.append(f"C1: PYTHONPATH={shadow} put a shadowing directory on the child's "
                            f"sys.path and the survey did not name it: {reported}")

        # (ii) An uncovered entry turns the STARTUP WITNESS red, by name, with
        #      the path in the row. Driven in-process by putting the same
        #      directory on `sys.path` — which is exactly what `PYTHONPATH`
        #      writes to.
        sys.path.insert(0, str(shadow))
        try:
            SA._ENVIRONMENT_MANIFEST = None
            bad = SW.failures(SW.identity_checks(
                {"experiment_contract": _environment_contract(manifest, fixture)}, check_tree=False))
            named = {r["field"] for r in bad}
            if "runtime_environment_uncovered_sys_path" not in named:
                problems.append(f"C1: an unsealed sys.path directory did not turn the witness red: "
                                f"{sorted(named)}")
            note = " ".join(f"{r.get('actual')} {r.get('note')}" for r in bad
                            if r["field"] == "runtime_environment_uncovered_sys_path")
            if shadow.resolve().as_posix() not in note:
                problems.append(f"C1: the refusal does not NAME the offending path: {note[:300]}")
            if "runtime_environment_digest" not in named:
                problems.append("C1: the shadow directory's own bytes must reach the digest too, so "
                                "that a reader comparing only the digest still refuses")
        finally:
            sys.path.remove(str(shadow))
            SA._ENVIRONMENT_MANIFEST = None
    finally:
        for leaf in sorted(shadow.rglob("*"), reverse=True):
            try:
                leaf.unlink()
            except OSError:                                                # noqa: BLE001, PERF203
                pass
        try:
            shadow.rmdir()
        except OSError:                                                    # noqa: BLE001
            pass

    # (iii) A sys.path entry that is ALREADY covered is not an accusation: the
    #       healthy state is an empty list, an unmoved digest and a green
    #       witness. Without this the closure would just be a tripwire that
    #       fires on the normal case.
    #
    #       THE ENTRY MUST BE THE REAL SITE-PACKAGES DIRECTORY, asked of the
    #       running interpreter. `sys.prefix/Lib/site-packages` is its name on
    #       Windows only; on POSIX it is `prefix/lib/pythonX.Y/site-packages`,
    #       and inserting the Windows spelling there adds a sys.path slot that
    #       does not exist — which the survey correctly seals as `absent`, so
    #       the digest moves and this check reports a stationarity failure that
    #       is really a typo in the check.
    already = str(SA.site_package_roots()[0])
    sys.path.insert(0, already)
    try:
        benign = SA.runtime_environment_manifest(use_cache=False)
        if benign["uncovered_sys_path"]:
            problems.append(f"C1: a benign, already-walked sys.path entry was reported as uncovered: "
                            f"{benign['uncovered_sys_path']}")
        if SA.environment_manifest_digest(benign) != sealed:
            problems.append("C1: re-adding an already-covered sys.path entry moved the digest, so the "
                            "seal is not stationary across the processes that have to agree on it")
        SA._ENVIRONMENT_MANIFEST = benign
        green = SW.failures(SW.identity_checks(
            {"experiment_contract": _environment_contract(manifest, fixture)}, check_tree=False))
        if green:
            problems.append(f"C1: the witness is red on a healthy import environment: "
                            f"{[r['field'] for r in green]}")
    finally:
        sys.path.remove(already)
        SA._ENVIRONMENT_MANIFEST = manifest        # the true state: everything above was restored

    # (iv) THE EXECUTOR'S HALF: the injecting variables are stripped from every
    #      confirmatory cell, and the journal records that they were.
    polluted = dict(os.environ)
    polluted.update({"PYTHONPATH": str(shadow), "PYTHONHOME": str(shadow),
                     "PYTHONSTARTUP": str(shadow / "startup.py")})
    cell_env, record = RA.sanitized_cell_environment(True, base=polluted)
    for name in SA.IMPORT_INJECTING_ENVIRONMENT_VARS:
        if name in cell_env:
            problems.append(f"C1: {name} survived into the confirmatory cell environment")
    if sorted(record["stripped"]) != sorted(SA.IMPORT_INJECTING_ENVIRONMENT_VARS):
        problems.append(f"C1: the journal record does not name every stripped variable: {record}")
    pilot_env, pilot_record = RA.sanitized_cell_environment(False, base=polluted)
    if pilot_record["stripped"] or "PYTHONPATH" not in pilot_env:
        problems.append("C1: sanitization belongs to the CONFIRMATORY contract; a pilot schedule must "
                        "be left alone and must say so in its record")
    run_arms_source = Path(RA.__file__).read_text(encoding="utf-8")
    if "env=cell_environment" not in run_arms_source:
        problems.append("C1: the cell subprocess is still launched with this process's own environment")
    if "cell_environment_sealed" not in run_arms_source:
        problems.append("C1: the executor does not journal what environment it handed the cells")
    with _tempfile.TemporaryDirectory() as tmp:
        journal_file = Path(tmp) / "journal.jsonl"
        RA.journal(journal_file, {"event": "cell_environment_sealed", "session_id": "s", **record},
                   required=True)
        entries = [json.loads(line) for line in
                   journal_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        sealed_entries = [e for e in entries if e.get("event") == "cell_environment_sealed"]
        if not sealed_entries:
            problems.append("C1: the sanitization record does not survive a journal round trip")
        elif sorted(sealed_entries[-1].get("stripped") or []) != \
                sorted(SA.IMPORT_INJECTING_ENVIRONMENT_VARS):
            problems.append(f"C1: the journalled record lost the stripped names: {sealed_entries[-1]}")
        elif not sealed_entries[-1].get("pycache_prefix"):
            problems.append(f"C1/C2: the journalled record does not name the fresh bytecode cache: "
                            f"{sealed_entries[-1]}")

    # ---------------------------------------------------------------- C2 --
    prefix = RA.fresh_bytecode_cache_prefix()
    if prefix != RA.fresh_bytecode_cache_prefix():
        problems.append("C2: the bytecode-cache prefix must be ONE fresh directory per session, not a "
                        "new one per call")
    if not prefix.is_dir() or Path(_tempfile.gettempdir()).resolve() not in prefix.resolve().parents:
        problems.append(f"C2: the fresh bytecode cache {prefix} is not a directory under the OS temp")
    if str(getattr(sys, "pycache_prefix", None) or "") != str(prefix):
        problems.append(f"C2: importing run_arms must redirect THIS process's cache too — "
                        f"sys.pycache_prefix is {getattr(sys, 'pycache_prefix', None)!r}")
    if cell_env.get("PYTHONPYCACHEPREFIX") != str(prefix):
        problems.append(f"C2: the cell subprocess does not carry PYTHONPYCACHEPREFIX to the fresh "
                        f"directory: {cell_env.get('PYTHONPYCACHEPREFIX')!r}")

    # THE END-TO-END WITNESS. A real `.pyc`, edited in place with the source
    # mtime and size in its own header left alone, IS executed by a plain
    # subprocess — and is not consulted at all under a fresh cache prefix,
    # which recompiles from the source bytes the manifest hashed.
    with _tempfile.TemporaryDirectory() as tmp:
        module = Path(tmp) / "piv_c2_victim.py"
        module.write_text("VALUE = 'from the sealed source'\n", encoding="utf-8")
        base_env = dict(os.environ)
        for name in ("PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH"):
            base_env.pop(name, None)
        command = [sys.executable, "-c", "import piv_c2_victim; print(piv_c2_victim.VALUE)"]

        def _say(environment):
            done = _subprocess.run(command, cwd=tmp, env=environment, capture_output=True,
                                   text=True, timeout=300)
            lines = (done.stdout or "").strip().splitlines()
            return lines[-1] if done.returncode == 0 and lines \
                else f"FAILED: {(done.stderr or '')[-200:]}"

        if _say(base_env) != "from the sealed source":
            problems.append("C2: the victim module did not import cleanly, so the witness proves "
                            "nothing")
        # THE DEFAULT cache location — the `__pycache__` beside the source.
        # `cache_from_source` honours THIS process's `sys.pycache_prefix`,
        # which importing `run_arms` has already redirected, so it has to be
        # asked with the redirect off or it answers about the wrong tree.
        _saved_prefix = getattr(sys, "pycache_prefix", None)
        sys.pycache_prefix = None
        try:
            cache = Path(importlib_util.cache_from_source(str(module)))
        finally:
            sys.pycache_prefix = _saved_prefix
        if not cache.is_file():
            problems.append(f"C2: no bytecode cache was written at {cache}, so the in-place edit "
                            f"cannot be witnessed")
        else:
            header = cache.read_bytes()[:16]     # magic, flags, SOURCE mtime, SOURCE size — untouched
            tampered = marshal.dumps(compile("VALUE = 'from the tampered bytecode'\n",
                                             str(module), "exec"))
            cache.write_bytes(header + tampered)
            if _say(base_env) != "from the tampered bytecode":
                problems.append("C2: the in-place .pyc edit was not executed by a plain subprocess — "
                                "then this witness does not exercise the hole it is about")
            fresh = Path(tmp) / "freshcache"
            redirected = dict(base_env)
            redirected["PYTHONPYCACHEPREFIX"] = str(fresh)
            said = _say(redirected)
            if said != "from the sealed source":
                problems.append(f"C2: under a FRESH PYTHONPYCACHEPREFIX the tampered cache was still "
                                f"consulted: {said!r}")
            if not fresh.exists():
                problems.append("C2: the fresh cache tree was never written, so nothing shows the "
                                "bytecode was regenerated from source rather than merely skipped")
            if cache.read_bytes()[16:] != tampered:
                problems.append("C2: the redirected run rewrote the DEFAULT cache; the whole point is "
                                "that it never touches it")

    return check("the import environment and the bytecode cache are sealed: every sys.path entry is "
                 "classified and an uncovered one is named by the witness and refused, the executor "
                 "strips PYTHONPATH/PYTHONHOME/PYTHONSTARTUP from every confirmatory cell and journals "
                 "it, a fresh PYTHONPYCACHEPREFIX makes an in-place .pyc edit unreachable (witnessed "
                 "end-to-end against a real tampered cache), and this platform's extension-module "
                 "directory, console-script directory, pyvenv.cfg and pythonXY.zip slot are inside "
                 "the walk",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# Codex T52 — the two report-only corrections before the M3 release
# artefacts freeze: the census invariant (§2) and the wording softening
# (§3/§4), plus the T51 §12 audit block (§1).
# --------------------------------------------------------------------------

def test_census_invariant_fails_closed_on_a_crafted_disagreement():
    """`AT.census_breakdown` (Codex T52 §2) must raise `CensusInvariantViolation`
    — never merely print — the instant the two independently-derived census
    identities disagree, and must NOT raise on a genuinely consistent map.

    The second fixture reproduces the EXACT class of bug Codex found, not a
    contrived one: a row that is non-quarantined (so the header's own
    `is_quarantined` + `row_status` view calls it VALID, since
    `measure_budget.validate_row` never looks at an `error` field) but
    carries a truthy `error` (so `classify_row` — which `census_breakdown`'s
    second identity is built from — routes it through the failure classifier
    instead, via the SAME `if row.get("quarantined") or row.get("error"):`
    branch `arm_table.classify_row` has always used). Two independent views
    of the same row disagreeing is exactly the shape of the "143 of 144 ...
    1 unrun" vs "0 of 144" contradiction he named."""
    problems = []
    schedule = _sealed_schedule(selectors=["train:1"], replicates=1)
    cells = schedule["cells"]                                     # 4 models x 1 x 1 x 3 arms = 12
    good_rows = [_cell_row(schedule, c) for c in cells]
    cell_rows = {SA.cell_key(c): r for c, r in zip(cells, good_rows)}
    loaded = {"cell_rows": cell_rows, "integrity": []}

    try:
        census = AT.census_breakdown(cells, loaded, good_rows)
    except AT.CensusInvariantViolation as exc:
        problems.append(f"a genuinely consistent map must NOT raise: {exc}")
        census = None
    if census is not None:
        want = {"scheduled": 12, "exactly_matched": 12, "unrun": 0, "integrity": 0,
                "valid": 12, "provider_failed": 0, "instrument_invalid": 0, "other_classified": 0}
        if census != want:
            problems.append(f"unexpected census on a clean fixture: {census} != {want}")

    # DISAGREEMENT 1: `loaded["cell_rows"]` claims fewer cells than `scheduled`
    # actually has (a stale/mismatched `loaded` handed to a different render).
    lying_cell_rows = dict(cell_rows)
    lying_cell_rows.pop(SA.cell_key(cells[0]))
    try:
        AT.census_breakdown(cells, {"cell_rows": lying_cell_rows, "integrity": []}, good_rows)
        problems.append("a loaded map whose cell count disagrees with `scheduled` must raise")
    except AT.CensusInvariantViolation:
        pass

    # DISAGREEMENT 2: the real-shaped bug — a non-quarantined row that
    # `row_status` calls VALID but `classify_row` calls a failure, because
    # only the latter looks at `error`.
    sneaky_rows = list(good_rows)
    sneaky_rows[0] = dict(sneaky_rows[0])
    sneaky_rows[0]["error"] = "ModelError: overloaded"
    if mb.validate_row(sneaky_rows[0])[0] != "VALID":
        problems.append("fixture error: the sneaky row must still validate as VALID by row_status")
    if AT.classify_row(sneaky_rows[0])[0] is None:
        problems.append("fixture error: classify_row must treat a truthy `error` as a failure")
    try:
        AT.census_breakdown(cells, loaded, sneaky_rows)
        problems.append("a row whose two independent classifications disagree must raise")
    except AT.CensusInvariantViolation:
        pass

    return check("census_breakdown raises CensusInvariantViolation the instant the two independent "
                 "derivations of the panel census disagree (a stale cell-count map, and a row whose "
                 "row_status/classify_row views disagree), and does not raise on a consistent one",
                 not problems, "\n".join(problems))


def test_confirm1v4_real_archive_census_unrun_tuple_and_wording():
    """Against the REAL sealed confirm1v4 archive (Codex T52 §1-§4) — not a
    fixture: the exact defect he found and the exact corrections he asked
    for, verified over the 143 rows actually written under
    `reviews/schedule_confirm1v4.json`.

      §2 census: `census_breakdown` must not raise over the real archive,
      and must report EXACTLY 144 = 143 + 1 unrun + 0 integrity; 143 = 138
      valid + 5 provider_failed + 0 instrument_invalid + 0 other_classified.
      The corrected `### Scheduled but not run` section must list EXACTLY
      the one known-missing cell (mistral/ministral-14b-2512/eval:5/A/r2,
      planned ordinal 101, block `mistral|ministral-14b-2512|eval:5|r2`),
      and the old contradiction ("0 of 144 scheduled cells have no row")
      must not reappear.

      §3/§4 wording: `P(arm dominates)` is labelled a bootstrap resample
      frequency; the exact "excludes zero"/"excludes one" phrasing is
      present; the devstral B2' paired discordant counts render as the
      real data gives them (4 vs 0, p = 0.125); the reward-spread caption
      says "capability-sensitive, non-degenerate reward signal" and never
      claims a "learnable gradient".

      §1 audit: the post-run-correction block names 138 VALID rows, commit
      `d4ba5f1`, the schedule's own `analysis_plan_sha256`, and the
      redundant environment-side suspicion witness (138/138 present, 0
      flagged) — this run's own archived data, not an assertion.
    """
    problems = []
    reviews_dir = ROOT / "reviews"
    schedule_path = reviews_dir / "schedule_confirm1v4.json"
    if not schedule_path.is_file():
        return check("confirm1v4 real-archive census/unrun/wording witnesses", True,
                     "(skipped: schedule_confirm1v4.json is not present in this checkout)")
    schedule = SA.load_schedule(schedule_path)
    loaded = AT.load_scheduled_rows(reviews_dir, schedule)
    rows = loaded["rows"]

    try:
        census = AT.census_breakdown(schedule["cells"], loaded, rows)
    except AT.CensusInvariantViolation as exc:
        problems.append(f"the real archive must satisfy its own census invariant: {exc}")
        census = None
    if census is not None:
        want = {"scheduled": 144, "exactly_matched": 143, "unrun": 1, "integrity": 0,
                "valid": 138, "provider_failed": 5, "instrument_invalid": 0, "other_classified": 0}
        if census != want:
            problems.append(f"confirm1v4 census mismatch: {census} != {want}")

    text = AT.render_table(rows, "test_confirm1v4_t52", loaded["files"], schedule, False, False,
                           ("A", "B1", "B2"), "A", loaded, None)

    if "0 of 144 scheduled cells have no row" in text:
        problems.append("the old contradiction ('0 of 144') must not reappear")
    if "1 of 144 scheduled cells have no row" not in text:
        problems.append("the corrected section must say '1 of 144 scheduled cells have no row'")
    want_row = ("| 101 | mistral | ministral-14b-2512 | eval:5 | 2 | A | "
               "mistral|ministral-14b-2512|eval:5|r2 |")
    if want_row not in text:
        problems.append(f"the unrun table must list the exact missing tuple: {want_row!r} not found")
    if "ran to completion" in text:
        problems.append("no panel-completion claim may use 'ran to completion' phrasing")

    for needle in ("P(arm dominates) [bootstrap resample frequency, NOT a posterior probability]",
                  "the preregistered whole-block bootstrap interval excludes zero on this fixed panel",
                  "the conditional bootstrap ratio interval excludes one",
                  "capability-sensitive, non-degenerate reward signal on the fixed panel",
                  "mistral/devstral-2512 B2': paired discordants over 11 complete blocks: 4 vs 0; "
                  "an exact two-sided sign test at this size is p = 0.125"):
        if needle not in text:
            problems.append(f"missing required wording: {needle!r}")

    for needle in ("138 live rows -> `VALID/derived`", "138 `VALID`", "code/test commit `d4ba5f1`",
                  f"analysis-plan sha256 `{schedule['experiment_contract']['analysis_plan_sha256']}`",
                  "present 138/138, flagged 0/138"):
        if needle not in text:
            problems.append(f"missing audit-block wording: {needle!r}")

    return check("the real confirm1v4 archive's census invariants hold, the corrected 'Scheduled but "
                 "not run' section lists the exact missing tuple with no contradiction, the softened "
                 "bootstrap/discordant-count wording renders with the real numbers, and the T51 §12 "
                 "audit block names the real commit/sha/witness counts",
                 not problems, "\n".join(problems))


TESTS = [
    test_no_write_is_no_artifact_no_write,
    test_refused_write_is_no_artifact_write_refused,
    test_committed_unsubmitted_write_is_bound_not_submitted,
    test_write_then_submit_is_bound_submitted_matches_delivery,
    test_two_concurrent_rollouts_each_bind_their_own_artifact,
    test_bind_artifact_defaults_when_state_is_sparse,
    test_token_usage_final_fields_are_pinned_and_row_names_them_truthfully,
    test_reasoning_replay_projection_diffs_only_reasoning_content_and_does_not_mutate_input,
    test_compute_budget_accounting_reasons_pure,
    test_no_request_caps_end_to_end_when_ceiling_disabled,
    test_usage_missing_end_to_end_with_plain_turnscript,
    test_valid_completion_exceeds_cap_and_wire_cap_mismatch_end_to_end,
    test_correct_delivery_predicate,
    test_arm_table_three_quantities_survivorship_example,
    test_effective_cost_is_inf_with_zero_correct_deliveries,
    test_stratum_excludes_quarantined_and_invalid_from_n_and_cost,
    test_attempt_boundary_detection_and_billed_totals_all_attempts,
    test_framework_retry_row_end_to_end_via_client_attempts_property,
    test_partition_rows_for_summary_gates_on_budget_accounting,
    test_arm_table_derives_budget_accounting_for_old_instrument_rows,
    test_redact_secrets_blanks_live_key_shaped_strings,
    test_schedule_balance_is_exact_within_provider_model_and_claimed_no_higher,
    test_schedule_ordinals_do_not_depend_on_the_replicate_count,
    test_schedule_id_is_content_bound_and_an_edited_schedule_is_refused,
    test_arms_and_signature_are_stable,
    test_tool_call_arguments_enter_the_plausibility_floor,
    test_surplus_wire_request_is_invalid_end_to_end,
    test_validate_row_rederives_every_predicate_from_literal_adversarial_rows,
    test_replay_contract_digest_moves_with_every_declared_clause,
    test_arm_table_refuses_to_pool_across_contracts_and_schedules,
    test_failure_classification_is_a_fixed_map_applied_blind,
    test_none_as_absent_is_narrow_and_falsey_values_survive,
    test_attempt_identity_binds_every_request_to_one_attempt,
    test_requests_log_records_every_attempt_including_rate_limited_ones,
    test_primary_contrast_drops_a_block_whose_arm_cell_was_censored,
    test_derived_rows_contribute_nothing_to_a_confirmatory_table,
    test_a_partial_output_file_is_re_run_and_rows_are_written_atomically,
    test_two_executors_on_one_cell_and_exactly_one_runs,
    test_rate_limit_classification_uses_the_observed_rolling_window,
    # Codex T49's pre-start checklist
    test_schedule_v2_seals_the_experiment_contract,
    test_exact_cell_identity_refuses_partials_duplicates_and_missing_schedule_ids,
    test_force_and_manual_completion_are_refused_for_a_sealed_schedule,
    test_one_schedule_level_executor_lock_without_automatic_takeover,
    test_window_ledger_paces_across_cells_and_carries_the_429_evidence,
    test_structured_provider_error_feeds_the_classifier,
    test_primary_contrasts_are_rendered_twice_with_a_sensitivity_comparison,
    test_cost_ratio_uncertainty_reports_zero_correct_dominance_and_a_conditional_interval,
    test_startup_witness_refuses_on_every_mismatched_field,
    test_capability_incompatibility_excludes_the_whole_configuration,
    test_executed_order_census_is_reconstructed_and_disagrees_when_it_should,
    test_liveness_witness_envelopes_are_the_packages_own_constants,
    # the T49 adversarial review's own findings
    test_a_numeric_class_only_ever_matches_a_status_field_never_a_substring,
    test_the_writer_refuses_to_overwrite_an_observed_scheduled_cell,
    test_the_window_ledger_fails_loud_and_marks_the_row,
    test_a_corrupt_lock_or_claim_is_owned_by_someone_unknown,
    test_run_closure_integrity_cells_are_a_third_state_and_the_table_exits_nonzero,
    test_an_inconclusive_capability_probe_refuses_the_configuration,
    # Codex T50's seven defects, each with its own mutation witness
    test_instrument_identity_is_the_bytes_on_disk_not_gits_index,
    test_free_text_429_is_never_a_rate_limit_needle,
    test_window_evidence_separates_billed_rejected_and_current_request,
    test_tpm_and_rpm_are_evaluated_independently,
    test_a_malformed_window_ledger_line_is_unhealthy_until_an_operator_recovers_it,
    test_the_execution_journal_fails_closed_in_confirmatory_mode,
    test_a_sealed_schedule_refuses_the_probe_bypass_and_records_four_distinct_outcomes,
    test_the_table_renders_the_T50_execution_evidence,
    # Codex T51's four START blockers, each with its own mutation witness
    test_the_runtime_environment_is_sealed_as_bytes_not_versions,
    test_the_instrument_is_verified_per_cell_and_per_request_and_drift_makes_no_call,
    test_a_corrupt_execution_journal_fails_closed_and_recovers_only_after_rows_exist,
    # the adversarial review of the T51 closures: the three perimeter bypasses
    test_the_import_environment_and_the_bytecode_cache_are_sealed,
    # Codex T52's two report-only corrections before the M3 freeze
    test_census_invariant_fails_closed_on_a_crafted_disagreement,
    test_confirm1v4_real_archive_census_unrun_tuple_and_wording,
]


def run_all() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run_all())
