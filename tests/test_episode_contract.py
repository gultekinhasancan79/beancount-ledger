"""The episode contract (PLAN §6), witnessed end to end with a scripted model.

Termination is the agent calling `submit`, or the turn limit. Nothing else.

The contract had been the framework's default instead, and the price was
measured: in six real rollouts across two model families (reviews/budget_*
2026-08-30 and a private notes file) not one ledger was
delivered. Every rollout died on `ToolEnv.no_tools_called` — the first
assistant turn without a tool call ends the episode — and a reasoning model
produces such a turn three different ways:

  narrated     a long final message describing repairs it never wrote
  empty        a reasoning-only reply the client renders as empty content
  truncated    a reply cut off at the per-turn completion cap

None of the three is a decision to stop. All three are answered here with one
fixed nudge and counted against `max_turns`; the episode ends when the agent
says so, when the turn cap is reached, or — so the nudge cannot become its own
loop — after MAX_CONSECUTIVE_NO_TOOL_TURNS turns in a row without a tool call,
or MAX_CONSECUTIVE_TRUNCATED_TURNS of them in a row cut off at the completion
cap.

The contract is an explicit state machine, one named value in
`state["piv_phase"]`:

    ACTIVE_NO_CANDIDATE --write accepted--> ACTIVE_CANDIDATE --submit--> TERMINAL
                        --write refused --> ACTIVE_REJECTED

`submit` is accepted only from ACTIVE_CANDIDATE; from the other two ACTIVE
phases it is refused, says why, costs a turn and leaves the episode running.
Every ending except the terminal protocol violation scores the LAST COMMITTED
REVISION; what changes is the name of the ending, which is the whole point.

Every route below runs the real framework loop through `env.evaluate`, with
only the assistant's messages scripted. Scoring, allocation, publication,
quarantine and the audit archive are untouched by any of it, and the witnesses
say so: the narrated / empty / truncated routes all end at the same reward the
same ledger earned before, and no route here is ever quarantined.

    python tests/test_episode_contract.py
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import verifiers as vf  # noqa: E402
from verifiers.legacy.types import Response, ResponseMessage, ToolCall, Usage  # noqa: E402

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.beancount_ledger import load_environment  # noqa: E402

GOLDEN = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")
# A candidate the protocol boundary REFUSES (a plugin directive is a control
# construct the contract forbids). It is stored — a revision exists — but it
# is not a deliverable, which is the ACTIVE_REJECTED phase.
HOSTILE = (
    'option "operating_currency" "USD"\n'
    ' plugin "colorsys"\n'
    "2025-11-01 open Assets:A USD\n"
    "2025-11-01 open Assets:B USD\n"
    '2025-11-05 * "Office Depot" "x"\n'
    "  Assets:A   1.00 USD\n"
    "  Assets:B  -1.00 USD\n"
)


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:12]:
            print(f"      {line}")
    return ok


# --------------------------------------------------------------------------
# a scripted client that plays an explicit list of turns
# --------------------------------------------------------------------------

def calls(*specs) -> ResponseMessage:
    """An assistant turn that calls tools."""
    return ResponseMessage(
        content="", finish_reason="tool_calls", is_truncated=False,
        tool_calls=[ToolCall(id=i, name=n, arguments=json.dumps(a)) for i, n, a in specs],
    )


def write(tag: str = "w", text: str = GOLDEN) -> ResponseMessage:
    return calls((tag, "write_ledger", {"content": text}))


def submit(tag: str = "s") -> ResponseMessage:
    return calls((tag, "submit", {}))


def narrated(text: str = "I have reconciled the ledger and it now loads cleanly.") -> ResponseMessage:
    """What gpt-oss-120b actually did on train:1: a long prose turn, no call."""
    return ResponseMessage(content=text, tool_calls=None, finish_reason="stop", is_truncated=False)


def empty() -> ResponseMessage:
    """A reasoning-only turn: the client renders content as empty, no call."""
    return ResponseMessage(content="", tool_calls=None, finish_reason="stop", is_truncated=False)


def truncated() -> ResponseMessage:
    """What the framework builds for a completion cut off at the token cap.

    `MultiTurnEnv.add_model_response` reads `response.message.is_truncated`
    (the client's `finish_reason == "length"`) and puts it on the
    `TrajectoryStep`. That is the only truncation signal in the rollout while
    it is running: `state["is_truncated"]` is written when a stop condition
    fires, which is too late to answer the turn.
    """
    return ResponseMessage(content="Let me work through the state", tool_calls=None,
                           finish_reason="length", is_truncated=True)


class TurnScript(vf.Client):
    """Plays `turns` in order; anything past the end is a bare empty turn."""

    def __init__(self, turns):
        super().__init__(object())
        self.turns = list(turns)
        self.turn = 0

    def setup_client(self, config):
        return object()

    async def to_native_tool(self, tool):
        return tool

    async def to_native_prompt(self, messages):
        return messages, {}

    async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
        self.turn += 1
        message = self.turns[self.turn - 1] if self.turn <= len(self.turns) else empty()
        return Response(id=f"scripted-{self.turn}", created=0, model=model, usage=None, message=message)

    async def raise_from_native_response(self, response):
        return None

    async def from_native_response(self, response):
        return response

    async def close(self):
        return None


def run(turns, env=None, state_columns=None):
    """(results, client, raised). One rollout through the real evaluate door."""
    env = env or load_environment()
    client = TurnScript(turns)
    extra = {"state_columns": list(state_columns)} if state_columns else {}
    try:
        results = asyncio.run(env.evaluate(
            client=client, model="scripted", num_examples=1, rollouts_per_example=1,
            max_concurrent=1, save_results=False, **extra))
        return results, client, None
    except env_mod.PIVEvaluationBatchInvalid as exc:
        return None, client, exc


def user_texts(completion) -> list:
    out = []
    for message in completion or []:
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        if role == "user":
            content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
            out.append(str(content))
    return out


def one(results):
    return (results["outputs"] or [{}])[0]


# --------------------------------------------------------------------------
# 1. a turn with no tool call is answered, not fatal
# --------------------------------------------------------------------------

def _no_tool_then_deliver(label, bare, expect_nudge):
    """<bare turn> -> write -> submit must score exactly as write -> submit."""
    results, client, raised = run([bare, write(), submit()])
    problems = []
    if raised is not None:
        return [f"{label}: evaluate raised {type(raised).__name__}: {raised}"]
    out = one(results)
    metrics = out.get("metrics") or {}
    if out.get("reward") != 1.0:
        problems.append(f"{label}: reward {out.get('reward')}, expected the same 1.0 the ledger earned before")
    if out.get("error") is not None:
        problems.append(f"{label}: error {out.get('error')}")
    if client.turn != 3:
        problems.append(f"{label}: the model was asked {client.turn} times, expected 3")
    if metrics.get("num_turns") != 3:
        problems.append(f"{label}: num_turns {metrics.get('num_turns')}, the bare turn must be counted")
    if metrics.get(env_mod.METRIC_NO_TOOL_TURNS) != 1.0:
        problems.append(f"{label}: piv/no_tool_turns {metrics.get(env_mod.METRIC_NO_TOOL_TURNS)}")
    if metrics.get(env_mod.METRIC_NO_TOOL_LIMIT) != 0.0:
        problems.append(f"{label}: the limit fired on a single bare turn")
    if out.get("stop_condition") != "piv_submitted":
        problems.append(f"{label}: stop_condition {out.get('stop_condition')!r}")
    if metrics.get("piv/training_eligible") != 1.0:
        problems.append(f"{label}: not training-eligible")
    if results["metadata"].get("piv_status") != "VALID" or results["metadata"].get("piv_quarantined_count"):
        problems.append(f"{label}: batch status {results['metadata'].get('piv_status')}")
    nudges = [t for t in user_texts(out.get("completion")) if t == expect_nudge]
    if len(nudges) != 1:
        problems.append(f"{label}: expected exactly one {expect_nudge!r}, saw {user_texts(out.get('completion'))}")
    return problems


def test_a_narrated_turn_does_not_end_the_episode():
    problems = _no_tool_then_deliver("narrated", narrated(), env_mod.TURN_NO_TOOL)
    return check("narration turn -> nudged and counted -> write -> submit -> 1.0, num_turns 3",
                 not problems, "\n".join(problems))


def test_an_empty_turn_does_not_end_the_episode():
    problems = _no_tool_then_deliver("empty", empty(), env_mod.TURN_NO_TOOL)
    return check("empty reasoning-only turn -> nudged and counted -> write -> submit -> 1.0, num_turns 3",
                 not problems, "\n".join(problems))


def test_a_truncated_turn_does_not_end_the_episode():
    """...and it is the framework's own flag that selects the truncated wording.

    Not vacuous in either direction: the truncated route's output carries
    `is_truncated` True (the framework saw `finish_reason == "length"` and
    put it on the trajectory step), and the narrated route's does not — so
    the two wordings are separated by a real signal rather than by which
    branch the test happened to take.
    """
    problems = _no_tool_then_deliver("truncated", truncated(), env_mod.TURN_TRUNCATED_NO_TOOL)
    for label, bare, expected in (("truncated", truncated(), True), ("narrated", narrated(), False)):
        results, _, raised = run([bare, write(), submit()])
        if raised is not None:
            problems.append(f"{label}: raised {raised}")
            continue
        if bool(one(results).get("is_truncated")) is not expected:
            problems.append(f"{label}: is_truncated {one(results).get('is_truncated')!r}, expected {expected}")
    return check("truncated turn (finish_reason length) -> nudged as truncated and counted -> write -> submit -> 1.0",
                 not problems, "\n".join(problems))


def test_the_nudge_carries_no_task_information():
    """A fixed sentence chosen by code: no world bytes, no hint, no state.

    Both nudge texts are module constants, so this is a pin on their content
    rather than an inspection of one rollout: no digit, no account name, no
    workspace path, no file content, and nothing that varies by task.
    """
    problems = []
    world = {name: data.decode("utf-8", "replace")
             for name, data in load_environment().public_files.items()}
    for name, text in (("TURN_NO_TOOL", env_mod.TURN_NO_TOOL),
                       ("TURN_TRUNCATED_NO_TOOL", env_mod.TURN_TRUNCATED_NO_TOOL)):
        if any(ch.isdigit() for ch in text):
            problems.append(f"{name} carries a digit")
        if len(text) > 240:
            problems.append(f"{name} is {len(text)} characters; the nudge is meant to be short")
        for word in text.replace("/", " ").replace(",", " ").replace(".", " ").split():
            if len(word) > 6 and any(word in body for body in world.values()):
                problems.append(f"{name} echoes {word!r} out of the world files")
        for tool in ("read_file", "grep", "write_ledger", "submit"):
            if tool not in text:
                problems.append(f"{name} does not name {tool}")
    return check("the nudge is fixed, short, names only the tools, and echoes nothing from the world",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 2. submit
# --------------------------------------------------------------------------

def call_turn(*specs):
    """One scripted assistant turn, as `env_response` receives it."""
    from types import SimpleNamespace

    return [SimpleNamespace(role="assistant", content="", tool_calls=[
        SimpleNamespace(id=i, name=n, arguments=json.dumps(a)) for i, n, a in specs])]


def bare_turn(text=""):
    """One scripted assistant turn with NO tool call."""
    from types import SimpleNamespace

    return [SimpleNamespace(role="assistant", content=text, tool_calls=None)]


def drive(env, state, *specs):
    """Run one tool-calling turn through the real `env_response`."""
    return asyncio.run(env.env_response(call_turn(*specs), state))


def replies(messages):
    return [getattr(m, "content", None) for m in messages]


def fresh(env=None):
    """(env, state, workspace Path). A rollout at ACTIVE_NO_CANDIDATE."""
    env = env or load_environment()
    state = {}
    return env, state, Path(env._workspace(state))


def phase(state):
    return env_mod.episode_phase(state)


# --------------------------------------------------------------------------
# 2. the state machine
# --------------------------------------------------------------------------

def test_the_episode_is_an_explicit_named_state_machine():
    """One value decides, and the tool handlers read it rather than flags.

    The witness walks every edge of the machine through the real tools and
    the real `env_response`, asserting the phase after each one:

        NO_CANDIDATE --refused write--> REJECTED --accepted write--> CANDIDATE
                     --submit--> TERMINAL --anything--> TERMINAL

    and it pins the shape of the enum itself, so a fifth phase or a renamed
    one is a failing test rather than a silent change of contract. The old
    boolean `state["piv_submitted"]` must be gone: two authorities for "is
    the episode over?" is exactly the drift this delta removes.
    """
    problems = []
    P = env_mod.EpisodePhase
    if [x.value for x in P] != ["ACTIVE_NO_CANDIDATE", "ACTIVE_CANDIDATE", "ACTIVE_REJECTED", "TERMINAL"]:
        problems.append(f"the phases moved: {[x.value for x in P]}")
    if env_mod.ACTIVE_PHASES != frozenset({P.NO_CANDIDATE, P.CANDIDATE, P.REJECTED}):
        problems.append(f"ACTIVE_PHASES {sorted(env_mod.ACTIVE_PHASES)}")
    if P.TERMINAL in env_mod.ACTIVE_PHASES:
        problems.append("TERMINAL is an active phase")

    env, state, workspace = fresh()
    ledger = workspace / env_mod.LEDGER
    original = ledger.read_bytes()
    if phase(state) is not P.NO_CANDIDATE:
        problems.append(f"a fresh rollout starts at {phase(state)}")

    # a refused submit does not move the phase, and does not end anything
    out = drive(env, state, ("s0", "submit", {}))
    if replies(out) != [env_mod.SUBMIT_NOTHING_STORED]:
        problems.append(f"submit at NO_CANDIDATE: {replies(out)}")
    if phase(state) is not P.NO_CANDIDATE or state.get("final_env_response") is not None:
        problems.append(f"a refused submit moved the episode: {phase(state)}")
    if ledger.read_bytes() != original:
        problems.append("a refused submit touched the ledger")

    # a stored-but-refused candidate: REJECTED, and submit still refuses
    drive(env, state, ("w1", "write_ledger", {"content": HOSTILE}))
    if phase(state) is not P.REJECTED:
        problems.append(f"after a protocol-refused write: {phase(state)}")
    if state.get("piv_revision") != 1:
        problems.append(f"a refused candidate did not commit a revision: {state.get('piv_revision')}")
    out = drive(env, state, ("s1", "submit", {}))
    if replies(out) != [env_mod.SUBMIT_LAST_CANDIDATE_REFUSED]:
        problems.append(f"submit at REJECTED: {replies(out)}")
    if phase(state) is not P.REJECTED:
        problems.append(f"a refused submit moved the phase: {phase(state)}")

    # an accepted candidate: CANDIDATE, and submit is taken
    drive(env, state, ("w2", "write_ledger", {"content": GOLDEN}))
    if phase(state) is not P.CANDIDATE:
        problems.append(f"after an accepted write: {phase(state)}")
    out = drive(env, state, ("s2", "submit", {}))
    if not str(replies(out)[0]).startswith(env_mod.SUBMIT_ACCEPTED):
        problems.append(f"submit at CANDIDATE: {replies(out)}")
    if phase(state) is not P.TERMINAL:
        problems.append(f"an accepted submit did not reach TERMINAL: {phase(state)}")

    # TERMINAL absorbs everything
    out = drive(env, state, ("w3", "write_ledger", {"content": HOSTILE}))
    if replies(out) != [env_mod.TURN_AFTER_SUBMIT] or phase(state) is not P.TERMINAL:
        problems.append(f"a post-submit turn: {replies(out)} phase {phase(state)}")

    if "piv_submitted" in state:
        problems.append("the old boolean flag is still written; the phase must be the only authority")
    if env_mod.score_core(state) != 1.0:
        problems.append("the delivered candidate did not score")
    return check("the episode is one named phase: NO_CANDIDATE -> REJECTED -> CANDIDATE -> TERMINAL, "
                 "walked through the real tools, with no second authority",
                 not problems, "\n".join(problems))


def test_submit_with_nothing_written_is_refused_and_the_episode_continues():
    """The delta: a bare `submit` no longer ends the episode.

    It used to be accepted unconditionally, so a model that had written
    nothing terminated itself on the untouched original — a decision it
    almost certainly did not make, and indistinguishable afterwards from a
    deliberate empty delivery. Now it is answered "nothing to submit", costs
    a turn, and the rollout carries on with every turn it had left.

    The scripted model here only ever calls `submit`, so the route ends the
    way a model that never acts is supposed to end: at the no-tool-call
    limit, once the padding turns run out. `piv/submitted` stays 0.0 — the
    agent never ended anything — and `piv/submit_refused` counts the calls.
    """
    results, client, raised = run([submit("s1"), submit("s2"), submit("s3")])
    if raised is not None:
        return check("a refused submit must not raise", False, str(raised))
    out = one(results)
    metrics = out.get("metrics") or {}
    problems = []
    if out.get("reward") != 0.0:
        problems.append(f"reward {out.get('reward')}, expected the untouched original's 0.0")
    if out.get("error") is not None:
        problems.append(f"error {out.get('error')}")
    if client.turn <= 3:
        problems.append(f"the model was asked {client.turn} times; a refused submit must not end the episode")
    if metrics.get(env_mod.METRIC_SUBMIT_REFUSED) != 3.0:
        problems.append(f"piv/submit_refused {metrics.get(env_mod.METRIC_SUBMIT_REFUSED)}, expected 3")
    if metrics.get(env_mod.METRIC_SUBMITTED) != 0.0:
        problems.append("piv/submitted set on an episode nobody ended")
    if out.get("stop_condition") != "piv_no_tool_call_limit":
        problems.append(f"stop_condition {out.get('stop_condition')!r}")
    if metrics.get("piv/training_eligible") != 1.0:
        problems.append("a refused submit is not training-eligible")
    if results["metadata"].get("piv_status") != "VALID" or results["metadata"].get("piv_quarantined_count"):
        problems.append(f"batch status {results['metadata'].get('piv_status')}")

    # and the state-level claim on the real object: nothing committed,
    # nothing delivered, nothing published, and the exact sentence.
    env, state, workspace = fresh()
    token = env_mod._PIV_STATE.set(state)
    try:
        reply = env_mod.submit(workspace=str(workspace))
    finally:
        env_mod._PIV_STATE.reset(token)
    if reply != "nothing to submit: write the corrected ledger with write_ledger first":
        problems.append(f"submit replied {reply!r}")
    if phase(state) is not env_mod.EpisodePhase.NO_CANDIDATE:
        problems.append(f"a refused submit moved the phase to {phase(state)}")
    if "piv_committed" in state or state.get("piv_revision"):
        problems.append("a refused submit installed a commitment")
    if env_mod.score_core(state) != 0.0:
        problems.append("score_core did not take the never-committed branch")
    if (workspace / "delivery.json").exists():
        problems.append("a refused submit published a delivery manifest")
    return check('submit with nothing written -> "nothing to submit", counted, the episode continues, '
                 "nothing committed or published", not problems, "\n".join(problems))


def test_submit_after_a_refused_write_names_the_refusal_and_continues():
    """The second half of the delta: a stored candidate the boundary refused.

    A revision exists — the bytes are on disk and `ProtocolRejected` is
    committed — so this is not the "nothing written" case, and the reply has
    to say something different: the last write was refused, write one that
    loads. The episode stays ACTIVE, and the model recovers inside the same
    rollout by writing a ledger that parses.
    """
    turns = [write("w1", HOSTILE), submit("s1"), write("w2", GOLDEN), submit("s2")]
    results, client, raised = run(turns)
    if raised is not None:
        return check("a refused submit after a refused write must not raise", False, str(raised))
    out = one(results)
    metrics = out.get("metrics") or {}
    problems = []
    if client.turn != 4:
        problems.append(f"the model was asked {client.turn} times, expected 4")
    if out.get("reward") != 1.0:
        problems.append(f"reward {out.get('reward')}; the recovered ledger must score")
    if metrics.get(env_mod.METRIC_SUBMIT_REFUSED) != 1.0:
        problems.append(f"piv/submit_refused {metrics.get(env_mod.METRIC_SUBMIT_REFUSED)}")
    if out.get("stop_condition") != "piv_submitted":
        problems.append(f"stop_condition {out.get('stop_condition')!r}")

    # the exact sentence, and that it is NOT the nothing-written one
    env, state, workspace = fresh()
    drive(env, state, ("w", "write_ledger", {"content": HOSTILE}))
    out2 = drive(env, state, ("s", "submit", {}))
    expected = ("nothing to submit: the last write_ledger was refused by the ledger protocol; "
                "write a ledger that loads, then submit")
    if replies(out2) != [expected]:
        problems.append(f"reply {replies(out2)}")
    if env_mod.SUBMIT_LAST_CANDIDATE_REFUSED == env_mod.SUBMIT_NOTHING_STORED:
        problems.append("the two refusals are the same sentence")
    if phase(state) is not env_mod.EpisodePhase.REJECTED:
        problems.append(f"phase {phase(state)}")
    return check("submit after a protocol-refused write -> names the refusal, episode stays active, "
                 "the model recovers and scores 1.0", not problems, "\n".join(problems))


def test_an_accepted_submit_binds_the_latest_candidate_hash_once():
    """Atomic, idempotent, and provably about the candidate that was there.

    The receipt names the `logical_text_digest` of the candidate as it stood
    when submit ran — the same digest the write attestation handed back and
    the same one the commitment carries. Three claims:

      - it binds the LATEST candidate (two writes, the second one delivered);
      - it binds ONCE: a second `submit` returns the identical receipt, and
        no later write can move it, because the workspace is frozen;
      - a candidate that changes underneath is REFUSED, not rescored — the
        finalisation compares the bytes to the receipt and raises.
    """
    problems = []
    env, state, workspace = fresh()
    ledger = workspace / env_mod.LEDGER

    drive(env, state, ("w1", "write_ledger", {"content": HOSTILE}))
    first = state["piv_logical_text_digest"]
    drive(env, state, ("w2", "write_ledger", {"content": GOLDEN}))
    latest = state["piv_logical_text_digest"]
    if first == latest:
        problems.append("the two candidates hash the same; the witness would be vacuous")

    out = drive(env, state, ("s", "submit", {}))
    receipt = str(replies(out)[0])
    if state.get("piv_submitted_digest") != latest:
        problems.append(f"bound {state.get('piv_submitted_digest')!r}, expected the latest {latest!r}")
    if env_mod.digest_short(latest) not in receipt:
        problems.append(f"the receipt does not carry the bound digest: {receipt!r}")
    if env_mod.digest_short(first) in receipt:
        problems.append("the receipt names the superseded candidate")
    if state["piv_committed"].receipt.logical_text_digest != latest:
        problems.append("the commitment and the submit binding disagree")

    # idempotent: the tool called again returns the identical receipt
    token = env_mod._PIV_STATE.set(state)
    try:
        again = env_mod.submit(workspace=str(workspace))
        refused = env_mod.write_ledger(content=HOSTILE, workspace=str(workspace))
    finally:
        env_mod._PIV_STATE.reset(token)
    if again != receipt:
        problems.append(f"a repeated submit returned a different receipt: {again!r} vs {receipt!r}")
    if refused != env_mod.WRITE_AFTER_SUBMIT:
        problems.append(f"a post-submit write was not refused: {refused!r}")
    if state.get("piv_submitted_digest") != latest:
        problems.append("the binding moved after submit")
    if env_mod.score_core(state) != 1.0:
        problems.append("the bound candidate did not score")
    if not ledger.exists():
        problems.append("the deliverable vanished")

    # a candidate changed underneath is refused, not rescored
    env2, state2, workspace2 = fresh()
    drive(env2, state2, ("w", "write_ledger", {"content": GOLDEN}))
    drive(env2, state2, ("s", "submit", {}))
    (workspace2 / env_mod.LEDGER).write_bytes(HOSTILE.encode("utf-8"))
    try:
        scored = env_mod.score_core(state2)
        problems.append(f"a changed candidate was rescored at {scored}")
    except RuntimeError as exc:
        if "receipt" not in str(exc):
            problems.append(f"finalisation raised the wrong thing: {exc}")
    return check("an accepted submit binds the latest candidate's hash once: named in the receipt, idempotent, "
                 "immovable by a later write, and a changed candidate is refused rather than rescored",
                 not problems, "\n".join(problems))


def test_narration_claiming_success_has_no_effect():
    """"I have written the ledger" is a sentence, not a transition.

    The one thing the six recorded rollouts all did (reviews/budget_*
    2026-08-30): a long final message describing repairs that were never
    written. It is answered with the nudge — and this pins the other half,
    that nothing about the world or the episode moved: same bytes on disk,
    same phase, no revision, no commitment, and the score is still the
    untouched original's.
    """
    problems = []
    env, state, workspace = fresh()
    ledger = workspace / env_mod.LEDGER
    before = ledger.read_bytes()
    claim = ("I have written the corrected ledger with write_ledger. The books now reconcile "
             "and the file loads without errors.")

    answer = asyncio.run(env.env_response(bare_turn(claim), state))
    if replies(answer) != [env_mod.TURN_NO_TOOL]:
        problems.append(f"the claim was not answered with the nudge: {replies(answer)}")
    if ledger.read_bytes() != before:
        problems.append("a narrated claim changed the ledger on disk")
    if phase(state) is not env_mod.EpisodePhase.NO_CANDIDATE:
        problems.append(f"a narrated claim moved the phase to {phase(state)}")
    if "piv_committed" in state or state.get("piv_revision") or "piv_pending" in state:
        problems.append(f"a narrated claim committed something: revision {state.get('piv_revision')}")
    if state.get("final_env_response") is not None:
        problems.append("a narrated claim ended the episode")
    if env_mod.score_core(state) != 0.0:
        problems.append("a narrated claim earned a score")

    # and submit right after it is still refused: narration is not a candidate
    out = drive(env, state, ("s", "submit", {}))
    if replies(out) != [env_mod.SUBMIT_NOTHING_STORED]:
        problems.append(f"submit after the claim: {replies(out)}")
    return check("a turn that CLAIMS the ledger was written leaves the bytes, the phase, the revision and the "
                 "score exactly as they were, and submit still refuses",
                 not problems, "\n".join(problems))


def test_submit_freezes_the_workspace():
    """write -> submit -> a further tool call: nothing is written after submit.

    Two halves, because the loop ending is not by itself a freeze. First: the
    framework is never asked for a fourth turn, so the scripted write that
    follows the submit is never even requested. Second: `env_response` is
    called directly with that write anyway — the shape a framework change
    could produce — and the ledger digest on disk does not move.
    """
    from types import SimpleNamespace

    hostile = "2025-11-01 open Assets:Wrong USD\n"
    results, client, raised = run([write(), submit(), write("w2", hostile)])
    if raised is not None:
        return check("write then submit must not raise", False, str(raised))
    out = one(results)
    problems = []
    if out.get("reward") != 1.0:
        problems.append(f"reward {out.get('reward')}, expected 1.0 over the ledger as last written")
    if client.turn != 2:
        problems.append(f"the model was asked {client.turn} times; the episode ended at submit, so 2")

    env = load_environment()
    state = {}
    workspace = Path(env._workspace(state))
    ledger = workspace / env_mod.LEDGER

    def digest():
        return hashlib.sha256(ledger.read_bytes()).hexdigest()

    def turn(*specs):
        return [SimpleNamespace(role="assistant", content="", tool_calls=[
            SimpleNamespace(id=i, name=n, arguments=json.dumps(a)) for i, n, a in specs])]

    asyncio.run(env.env_response(turn(("w", "write_ledger", {"content": GOLDEN})), state))
    committed_digest, committed_revision = digest(), state.get("piv_revision")
    asyncio.run(env.env_response(turn(("s", "submit", {})), state))
    if env_mod.episode_phase(state) is not env_mod.EpisodePhase.TERMINAL:
        problems.append(f"submit did not reach TERMINAL: {env_mod.episode_phase(state)}")

    # a later turn: refused whole, nothing executed
    replies = asyncio.run(env.env_response(turn(("w2", "write_ledger", {"content": hostile})), state))
    if [getattr(r, "content", None) for r in replies] != [env_mod.TURN_AFTER_SUBMIT]:
        problems.append(f"a post-submit turn was not refused: {[getattr(r, 'content', None) for r in replies]}")
    if digest() != committed_digest:
        problems.append("the ledger changed after submit")
    if state.get("piv_revision") != committed_revision:
        problems.append(f"the revision moved after submit: {state.get('piv_revision')}")

    # and the same-turn ordering: submit first, write second in ONE call list
    # is representable, so the SUFFIX is refused before the tool body runs
    # (terminality is true at the instant submit is accepted,
    # not merely from the next turn).
    state2 = {}
    workspace2 = Path(env._workspace(state2))
    asyncio.run(env.env_response(turn(("w", "write_ledger", {"content": GOLDEN})), state2))
    before = hashlib.sha256((workspace2 / env_mod.LEDGER).read_bytes()).hexdigest()
    replies = asyncio.run(env.env_response(
        turn(("s", "submit", {}), ("w2", "write_ledger", {"content": hostile})), state2))
    contents = [getattr(r, "content", None) for r in replies]
    # The accepted receipt names the bound hash, so it is compared by prefix
    # and then by the digest it must carry — the constant alone is no longer
    # the whole reply.
    if (len(contents) != 2 or not str(contents[0]).startswith(env_mod.SUBMIT_ACCEPTED)
            or env_mod.digest_short(state2["piv_logical_text_digest"]) not in str(contents[0])
            or contents[1] != env_mod.TURN_AFTER_SUBMIT):
        problems.append(f"submit-then-write in one turn: {contents}")
    # the direct-call door keeps its own, more specific refusal
    token = env_mod._PIV_STATE.set(state2)
    try:
        direct = env_mod.write_ledger(content=hostile, workspace=str(workspace2))
    finally:
        env_mod._PIV_STATE.reset(token)
    if direct != env_mod.WRITE_AFTER_SUBMIT:
        problems.append(f"a direct post-submit write was not refused: {direct!r}")
    if hashlib.sha256((workspace2 / env_mod.LEDGER).read_bytes()).hexdigest() != before:
        problems.append("a write after submit in the same turn reached the disk")
    return check("submit freezes the workspace: no fourth turn, a later write refused, a same-turn write refused, "
                 "the ledger digest never moves", not problems, "\n".join(problems))


def test_submit_is_the_only_agent_driven_termination():
    """The framework's `no_tools_called` is gone, deliberately and provably."""
    env = load_environment()
    names = [c.__name__ for c in env._stop_conditions]
    problems = []
    if "no_tools_called" in names:
        problems.append(f"no_tools_called is still a stop condition: {names}")
    # The framework's own token-ceiling stop is overridden away for the same
    # reason: `piv_output_budget_exhausted` is the one authority on that
    # property, and the framework's would name the mechanism during the
    # one-shot deferral that lets an accepted submit win.
    if "max_total_completion_tokens_reached" in names:
        problems.append(f"the framework's token-ceiling stop is still registered: {names}")
    for required in ("piv_submitted", "piv_output_budget_exhausted", "piv_no_tool_call_limit",
                     "piv_truncation_limit", "piv_turn_cap_no_submit"):
        if required not in names:
            problems.append(f"the episode contract's stop condition {required} is missing: {names}")
    # Order matters and is asserted, not assumed: a terminal protocol
    # violation names itself above everything (nothing executed, and it pays
    # the protocol score), an agent-driven end outranks every
    # environment-driven one, the spent output budget outranks the
    # truncation it causes, the specific truncation diagnosis outranks the
    # general no-tool one, and all of them outrank the turn cap, which in turn
    # outranks the framework's own `max_turns_reached`.
    order = [n for n in names if n in ("piv_protocol_terminated", "piv_submitted",
                                       "piv_output_budget_exhausted", "piv_truncation_limit",
                                       "piv_no_tool_call_limit", "piv_turn_cap_no_submit",
                                       "max_turns_reached")]
    if order != ["piv_protocol_terminated", "piv_submitted", "piv_output_budget_exhausted",
                 "piv_truncation_limit", "piv_no_tool_call_limit", "piv_turn_cap_no_submit",
                 "max_turns_reached"]:
        problems.append(f"stop-condition order: {order}")
    if asyncio.run(env.no_tools_called({"trajectory": [1]})):
        problems.append("the overridden no_tools_called still reports a stop")
    if asyncio.run(env.max_total_completion_tokens_reached({})):
        problems.append("the overridden max_total_completion_tokens_reached still reports a stop")
    if env.max_total_completion_tokens != env_mod.MAX_EPISODE_OUTPUT_TOKENS:
        problems.append(f"the served ceiling is {env.max_total_completion_tokens}, not "
                        f"MAX_EPISODE_OUTPUT_TOKENS {env_mod.MAX_EPISODE_OUTPUT_TOKENS}")
    if env.max_turns != 25:
        problems.append(f"max_turns {env.max_turns}, PLAN §6 says 25")
    if env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS != 3:
        problems.append(f"MAX_CONSECUTIVE_NO_TOOL_TURNS {env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS}")
    if env_mod.MAX_CONSECUTIVE_TRUNCATED_TURNS != env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS:
        problems.append("the truncation bound no longer rides the no-tool run; say so on purpose "
                        f"({env_mod.MAX_CONSECUTIVE_TRUNCATED_TURNS} vs "
                        f"{env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS})")
    return check("no_tools_called is not a stop condition; piv_submitted and piv_no_tool_call_limit are; max_turns 25",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3. the nudge is bounded
# --------------------------------------------------------------------------

def test_three_consecutive_no_tool_turns_end_the_episode():
    """The nudge must not become a loop hazard. Named, counted, never quarantined."""
    results, client, raised = run([narrated(), empty(), truncated(), write(), submit()])
    if raised is not None:
        return check("the no-tool-call limit must not raise", False, str(raised))
    out = one(results)
    metrics = out.get("metrics") or {}
    problems = []
    if client.turn != env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS:
        problems.append(f"the model was asked {client.turn} times, expected "
                        f"{env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS}")
    if out.get("stop_condition") != "piv_no_tool_call_limit":
        problems.append(f"stop_condition {out.get('stop_condition')!r}")
    if metrics.get(env_mod.METRIC_NO_TOOL_LIMIT) != 1.0:
        problems.append(f"piv/no_tool_limit {metrics.get(env_mod.METRIC_NO_TOOL_LIMIT)}")
    if metrics.get(env_mod.METRIC_NO_TOOL_TURNS) != float(env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS):
        problems.append(f"piv/no_tool_turns {metrics.get(env_mod.METRIC_NO_TOOL_TURNS)}")
    if metrics.get(env_mod.METRIC_SUBMITTED) != 0.0:
        problems.append("piv/submitted set on an episode the agent did not end")
    if out.get("reward") != 0.0 or out.get("error") is not None:
        problems.append(f"reward {out.get('reward')} error {out.get('error')}; expected a counted 0.0")
    if metrics.get("piv/evaluator_failed") != 0.0 or metrics.get("piv/training_eligible") != 1.0:
        problems.append("the limit was treated as a failure rather than an agent outcome")
    meta = results["metadata"]
    if meta.get("piv_status") != "VALID" or meta.get("piv_quarantined_count") != 0:
        problems.append(f"quarantined: status={meta.get('piv_status')} n={meta.get('piv_quarantined_count')}")
    # exactly two nudges: the third bare turn stops instead of nudging again
    nudges = [t for t in user_texts(out.get("completion"))
              if t in (env_mod.TURN_NO_TOOL, env_mod.TURN_TRUNCATED_NO_TOOL)]
    if len(nudges) != env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS - 1:
        problems.append(f"{len(nudges)} nudges in the transcript: {nudges}")
    return check("three consecutive no-tool turns -> piv_no_tool_call_limit, counted 0.0, never quarantined, "
                 "no nudge after the last one", not problems, "\n".join(problems))


def test_a_tool_call_resets_the_no_tool_run():
    """The limit is CONSECUTIVE turns, so working models are never cut short."""
    turns = []
    for _ in range(4):
        turns += [narrated(), narrated(), calls(("g", "list_files", {}))]
    turns += [write(), submit()]
    results, client, raised = run(turns, env=load_environment())
    if raised is not None:
        return check("interleaved bare turns must not raise", False, str(raised))
    out = one(results)
    metrics = out.get("metrics") or {}
    problems = []
    if out.get("stop_condition") != "piv_submitted":
        problems.append(f"stop_condition {out.get('stop_condition')!r}; a tool call must reset the run")
    if out.get("reward") != 1.0:
        problems.append(f"reward {out.get('reward')}")
    if metrics.get(env_mod.METRIC_NO_TOOL_TURNS) != 8.0:
        problems.append(f"piv/no_tool_turns {metrics.get(env_mod.METRIC_NO_TOOL_TURNS)}, expected 8")
    if client.turn != len(turns):
        problems.append(f"the model was asked {client.turn} times, expected {len(turns)}")
    return check("a tool call resets the consecutive no-tool-call run; eight bare turns interleaved still deliver 1.0",
                 not problems, "\n".join(problems))


def test_an_unbroken_run_of_truncated_turns_ends_under_the_truncation_limit():
    """The bounded truncation recovery, and its separation from the nudge limit.

    Three of the six recorded rollouts (nemotron-3-ultra on train:1/12/30) were
    cut off at the per-turn completion cap with no tool call. Answering that
    with a nudge is right once or twice; a model that reasons past the cap
    will do it again, and the nudge is one more thing for it to reason about.
    So an unbroken run of MAX_CONSECUTIVE_TRUNCATED_TURNS truncated no-tool
    turns ends the episode under its own name.

    Not vacuous: the counter is separate from the no-tool run, so the same
    number of bare turns ends under a DIFFERENT name when even one of them was
    not truncated. Both routes are ordinary counted outcomes over the last
    committed revision, and neither is ever quarantined.
    """
    problems = []
    routes = (
        ("all truncated", [truncated(), truncated(), truncated()],
         "piv_truncation_limit", 1.0, 1.0),          # both flags: piv/no_tool_limit keeps counting these endings
        ("one narration in the run", [narrated(), truncated(), truncated()],
         "piv_no_tool_call_limit", 0.0, 1.0),
    )
    for label, turns, expected_stop, expect_trunc, expect_no_tool in routes:
        results, client, raised = run(turns)
        if raised is not None:
            problems.append(f"{label}: raised {type(raised).__name__}: {raised}")
            continue
        out = one(results)
        metrics = out.get("metrics") or {}
        if out.get("stop_condition") != expected_stop:
            problems.append(f"{label}: stop_condition {out.get('stop_condition')!r}, expected {expected_stop}")
        if metrics.get(env_mod.METRIC_TRUNCATION_LIMIT) != expect_trunc:
            problems.append(f"{label}: piv/truncation_limit {metrics.get(env_mod.METRIC_TRUNCATION_LIMIT)}")
        if metrics.get(env_mod.METRIC_NO_TOOL_LIMIT) != expect_no_tool:
            problems.append(f"{label}: piv/no_tool_limit {metrics.get(env_mod.METRIC_NO_TOOL_LIMIT)}")
        if client.turn != env_mod.MAX_CONSECUTIVE_TRUNCATED_TURNS:
            problems.append(f"{label}: the model was asked {client.turn} times, expected "
                            f"{env_mod.MAX_CONSECUTIVE_TRUNCATED_TURNS}")
        if out.get("reward") != 0.0 or out.get("error") is not None:
            problems.append(f"{label}: reward {out.get('reward')} error {out.get('error')}")
        if metrics.get("piv/evaluator_failed") != 0.0 or metrics.get("piv/training_eligible") != 1.0:
            problems.append(f"{label}: treated as a failure rather than an agent outcome")
        if metrics.get(env_mod.METRIC_SUBMITTED) != 0.0:
            problems.append(f"{label}: piv/submitted set")
        meta = results["metadata"]
        if meta.get("piv_status") != "VALID" or meta.get("piv_quarantined_count") != 0:
            problems.append(f"{label}: quarantined: {meta.get('piv_status')}")
        nudges = [t for t in user_texts(out.get("completion"))
                  if t in (env_mod.TURN_NO_TOOL, env_mod.TURN_TRUNCATED_NO_TOOL)]
        if len(nudges) != env_mod.MAX_CONSECUTIVE_TRUNCATED_TURNS - 1:
            problems.append(f"{label}: {len(nudges)} nudges: {nudges}")

    # and a tool call clears the truncated run, so a model that recovers is
    # never cut short by it
    results, client, raised = run([truncated(), truncated(), calls(("g", "list_files", {})),
                                   truncated(), truncated(), write(), submit()])
    if raised is not None:
        problems.append(f"recovery route raised {raised}")
    else:
        out = one(results)
        if out.get("stop_condition") != "piv_submitted" or out.get("reward") != 1.0:
            problems.append(f"a tool call did not clear the truncated run: "
                            f"{out.get('stop_condition')!r} reward {out.get('reward')}")
        if (out.get("metrics") or {}).get(env_mod.METRIC_TRUNCATION_LIMIT) != 0.0:
            problems.append("the truncation limit fired on a route that recovered")
    return check("three truncated turns in a row -> piv_truncation_limit; the same three with one narration "
                 "in them -> piv_no_tool_call_limit; a tool call clears the run",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3b. the per-episode output ceiling, enforced on the REQUEST
# --------------------------------------------------------------------------

class BudgetScript(TurnScript):
    """A scripted client that SPENDS tokens, and is cut off by the cap it is given.

    Each turn "wants" `wanted` completion tokens and reports
    `min(wanted, max_tokens)` — the provider behaviour the ceiling has to
    reckon with, and the reason the framework's own stop is not enough: it
    notices the ceiling only after a turn has already overshot it.

    Records what every request actually carried (`caps`) and what every turn
    actually spent (`spent`), so a test can compare the two.
    """

    def __init__(self, turns, wanted):
        super().__init__(turns)
        self.wanted = wanted
        self.caps = []
        self.spent = []

    async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
        cap = sampling_args.get("max_tokens", sampling_args.get("max_completion_tokens"))
        spent = min(self.wanted, cap) if isinstance(cap, int) else self.wanted
        self.caps.append(cap)
        self.spent.append(spent)
        self.turn += 1
        message = self.turns[self.turn - 1] if self.turn <= len(self.turns) else empty()
        return Response(id=f"scripted-{self.turn}", created=0, model=model, message=message,
                        usage=Usage(prompt_tokens=1000, reasoning_tokens=0,
                                    completion_tokens=spent, total_tokens=1000 + spent))


def run_budgeted(turns, wanted, per_turn_cap, env=None, ceiling=None):
    """One rollout with a per-turn cap, the way the measurement script sets it.

    `piv_request_max_tokens` is asked for as a state column because that is
    how `tests/measure_budget.py` reads the per-turn caps back out of a live
    arm; pinning it here keeps that read from being the first place a change
    to the key is noticed.
    """
    env = env or (load_environment() if ceiling is None
                  else load_environment(max_episode_output_tokens=ceiling))
    client = BudgetScript(turns, wanted)
    sampling_args = {"max_tokens": per_turn_cap}
    try:
        results = asyncio.run(env.evaluate(
            client=client, model="scripted", num_examples=1, rollouts_per_example=1,
            max_concurrent=1, save_results=False, sampling_args=sampling_args,
            state_columns=["piv_request_max_tokens"]))
        return results, client, sampling_args, None
    except env_mod.PIVEvaluationBatchInvalid as exc:
        return None, client, sampling_args, exc


def read_turn(tag="g"):
    """A turn that calls a tool, so no no-tool run ever starts."""
    return calls((tag, "list_files", {}))


def test_two_per_turn_caps_are_measured_at_exactly_the_same_output_budget():
    """The M2 arms differ in per-turn cap and must still be compared at equal total.

    `MultiTurnEnv.set_max_total_completion_tokens` alone cannot do that: the
    framework's `max_total_completion_tokens_reached` is a stop condition, so
    it is consulted only after a turn has been generated. An arm capped at
    16K per turn would end up to 16K past a 40K ceiling and an 8K arm up to
    8K past it — a 20 % difference in the budget between two arms whose
    comparison is supposed to be about the policy.

    So the ceiling is enforced on the REQUEST: each turn asks for
    `min(per-turn cap, ceiling - spent)`. Both arms below run to exhaustion
    from long turns and land on exactly MAX_EPISODE_OUTPUT_TOKENS — equal
    maximum accounting — under a stop condition that names the budget rather
    than the turn cap. The request sequence itself is pinned, because "never
    asked for more than was left" is the property that makes the equality
    hold at the provider rather than in our arithmetic.
    """
    problems = []
    ceiling = env_mod.MAX_EPISODE_OUTPUT_TOKENS
    arms = (
        # per-turn cap, tokens each turn wants, the request caps we expect
        ("8K arm", 8_000, 7_000, [8_000, 8_000, 8_000, 8_000, 8_000, 5_000]),
        ("16K arm", 16_000, 15_000, [16_000, 16_000, 10_000]),
    )
    for label, cap, wanted, expected_requests in arms:
        turns = [read_turn(f"g{i}") for i in range(len(expected_requests) + 2)]
        results, client, sampling_args, raised = run_budgeted(turns, wanted, cap)
        if raised is not None:
            problems.append(f"{label}: evaluate raised {type(raised).__name__}: {raised}")
            continue
        out = one(results)
        metrics = out.get("metrics") or {}
        spent = sum(client.spent)
        if spent != ceiling:
            problems.append(f"{label}: spent {spent} output tokens, expected exactly {ceiling}")
        if out.get("stop_condition") != "piv_output_budget_exhausted":
            problems.append(f"{label}: stop_condition {out.get('stop_condition')!r}")
        if metrics.get(env_mod.METRIC_OUTPUT_BUDGET_EXHAUSTED) != 1.0:
            problems.append(f"{label}: {env_mod.METRIC_OUTPUT_BUDGET_EXHAUSTED} "
                            f"{metrics.get(env_mod.METRIC_OUTPUT_BUDGET_EXHAUSTED)}")
        if client.caps != expected_requests:
            problems.append(f"{label}: request caps {client.caps}, expected {expected_requests}")
        if client.turn != len(expected_requests):
            problems.append(f"{label}: the model was asked {client.turn} times, "
                            f"expected {len(expected_requests)}")
        # the same sequence, as the environment recorded it for the measurement
        recorded = out.get("piv_request_max_tokens")
        if recorded is None or list(recorded) != expected_requests:
            problems.append(f"{label}: piv_request_max_tokens {recorded}, expected {expected_requests}")
        # never more than was left, and the last request is exactly the remainder
        left = ceiling
        for asked, used in zip(client.caps, client.spent):
            if asked > left:
                problems.append(f"{label}: asked for {asked} with {left} left")
            left -= used
        if client.caps[-1] != ceiling - sum(client.spent[:-1]):
            problems.append(f"{label}: the last request was {client.caps[-1]}, "
                            f"not the remainder {ceiling - sum(client.spent[:-1])}")
        if metrics.get("piv/evaluator_failed") != 0.0 or metrics.get("piv/training_eligible") != 1.0:
            problems.append(f"{label}: treated as a failure rather than an agent outcome")
        if results["metadata"].get("piv_status") != "VALID" or results["metadata"].get("piv_quarantined_count"):
            problems.append(f"{label}: batch status {results['metadata'].get('piv_status')}")
        # the caller's dict is shared by every rollout of a batch: never mutated
        if sampling_args != {"max_tokens": cap}:
            problems.append(f"{label}: the caller's sampling_args was mutated to {sampling_args}")
    return check(f"an 8K-per-turn arm and a 16K-per-turn arm both stop at exactly "
                 f"{env_mod.MAX_EPISODE_OUTPUT_TOKENS} output tokens, never asking for more than is left",
                 not problems, "\n".join(problems))


def test_a_submit_on_the_exhausting_turn_is_still_the_agent_ending_the_episode():
    """Priority 48: below `piv_submitted` (50), above the truncation limit (45).

    The turn that spends the last of the budget may also be the turn that
    delivers. Naming that ending "out of tokens" would understate every arm's
    submit rate and hide a policy that did exactly what the contract asks;
    the agent's own termination wins, and the ledger it delivered is scored
    as at any other submit.

    Priority alone does not produce that, and the difference from
    `piv_turn_cap_submit_unexecuted` is the point: stop conditions are
    checked before the turn's calls are executed, so the `submit` is still
    pending when the budget stop is asked. Running it costs no OUTPUT tokens
    — which is the only currency this ceiling is denominated in — so the
    budget stop defers once, the call runs, and the ending is named for what
    the agent did. The total spent is still exactly the ceiling, which is
    what the deferral must not break.
    """
    problems = []
    # turn 1 spends 25,000 of the 40,000; turn 2 is clamped to the 15,000
    # remainder, spends all of it, and carries the accepted submit
    results, client, _args, raised = run_budgeted([write(), submit()], 25_000, 25_000)
    if raised is not None:
        return check("a submit on the exhausting turn names piv_submitted", False,
                     f"evaluate raised {type(raised).__name__}: {raised}")
    out = one(results)
    metrics = out.get("metrics") or {}
    if sum(client.spent) != env_mod.MAX_EPISODE_OUTPUT_TOKENS:
        problems.append(f"spent {sum(client.spent)}, expected exactly {env_mod.MAX_EPISODE_OUTPUT_TOKENS}")
    if client.caps != [25_000, 15_000] or client.turn != 2:
        problems.append(f"the deferral cost an extra request: caps {client.caps}, {client.turn} turns")
    if out.get("stop_condition") != "piv_submitted":
        problems.append(f"stop_condition {out.get('stop_condition')!r}, expected piv_submitted")
    if metrics.get(env_mod.METRIC_SUBMITTED) != 1.0:
        problems.append(f"piv/submitted {metrics.get(env_mod.METRIC_SUBMITTED)}")
    if metrics.get(env_mod.METRIC_OUTPUT_BUDGET_EXHAUSTED) != 0.0:
        problems.append("the budget stop claimed an ending the agent made itself")
    if out.get("reward") != 1.0:
        problems.append(f"reward {out.get('reward')}: the delivered ledger was not scored")
    if out.get("error") is not None:
        problems.append(f"error {out.get('error')}")
    return check("a submit accepted on the turn that exhausts the budget still ends as piv_submitted, "
                 "and the ledger it delivered is scored", not problems, "\n".join(problems))


def test_pending_calls_on_the_exhausting_turn_run_and_never_buy_another_request():
    """The deferral is for EVERY pending call, and it is sealed.

    Executing a pending tool call spends no output tokens, so the calls the
    model paid for with its last tokens run: a write is committed and scored,
    a refused submit is answered. What must not happen is a further model
    request — the deferral only makes sense if `env_response` then seals the
    episode when the budget is spent, otherwise a deferred turn whose submit
    was refused (or that only wrote) would be asked for one more turn and the
    arm would be measured a token past the ceiling. Each case pins: exactly
    two requests, exactly the ceiling spent, the ending named for the budget.

    A terminal protocol violation on the exhausting turn keeps its own name:
    that ending carries the protocol score, not the last revision's.
    """
    problems = []
    ceiling = env_mod.MAX_EPISODE_OUTPUT_TOKENS
    cases = (
        # label, second turn, expected stop, expected reward, extra metric expectations
        ("write on the exhausting turn", write(), "piv_output_budget_exhausted", 1.0,
         {env_mod.METRIC_OUTPUT_BUDGET_EXHAUSTED: 1.0, env_mod.METRIC_SUBMITTED: 0.0}),
        ("refused submit (nothing written)", submit(), "piv_output_budget_exhausted", 0.0,
         {env_mod.METRIC_OUTPUT_BUDGET_EXHAUSTED: 1.0, env_mod.METRIC_SUBMIT_REFUSED: 1.0}),
        ("refused write and a submit in one turn",
         calls(("w", "write_ledger", {"content": "2025-13-45 * garbage\n"}), ("s", "submit", {})),
         "piv_output_budget_exhausted", 0.0,
         {env_mod.METRIC_OUTPUT_BUDGET_EXHAUSTED: 1.0, env_mod.METRIC_SUBMITTED: 0.0}),
        ("duplicate call ids", calls(("dup", "list_files", {}), ("dup", "list_files", {})),
         "piv_protocol_terminated", 0.0,
         {env_mod.METRIC_OUTPUT_BUDGET_EXHAUSTED: 0.0}),
    )
    for label, second, expected_stop, expected_reward, expected_metrics in cases:
        # turn 1 spends 25,000; turn 2 is clamped to the 15,000 remainder and carries the calls
        results, client, _args, raised = run_budgeted([read_turn("g1"), second], 25_000, 25_000)
        if raised is not None:
            problems.append(f"{label}: evaluate raised {type(raised).__name__}: {raised}")
            continue
        out = one(results)
        metrics = out.get("metrics") or {}
        if sum(client.spent) != ceiling:
            problems.append(f"{label}: spent {sum(client.spent)}, expected exactly {ceiling}")
        if client.caps != [25_000, 15_000] or client.turn != 2:
            problems.append(f"{label}: an extra request was made: caps {client.caps}, {client.turn} turns")
        if out.get("stop_condition") != expected_stop:
            problems.append(f"{label}: stop_condition {out.get('stop_condition')!r}, expected {expected_stop}")
        if out.get("reward") != expected_reward:
            problems.append(f"{label}: reward {out.get('reward')}, expected {expected_reward}")
        for key, value in expected_metrics.items():
            if metrics.get(key) != value:
                problems.append(f"{label}: {key} {metrics.get(key)}, expected {value}")
        if out.get("error") is not None:
            problems.append(f"{label}: error {out.get('error')}")
        if results["metadata"].get("piv_status") != "VALID" or results["metadata"].get("piv_quarantined_count"):
            problems.append(f"{label}: batch status {results['metadata'].get('piv_status')}")
    return check("every pending call on the exhausting turn runs (a write is committed and scored), "
                 "the episode is sealed without another request, and a protocol violation keeps its name",
                 not problems, "\n".join(problems))


def test_the_ceiling_is_configurable_and_defaults_to_the_constant():
    """Zero disables both halves — no clamp, no stop — and the default is the
    constant the measurement arms are specified in.

    The disabled route is the control: without it, "the request was clamped"
    could be true of a run that simply never asked for much, and the equality
    above would not be evidence of anything.
    """
    problems = []
    if env_mod.MAX_EPISODE_OUTPUT_TOKENS != 40_000:
        problems.append(f"MAX_EPISODE_OUTPUT_TOKENS is {env_mod.MAX_EPISODE_OUTPUT_TOKENS}, not 40000")
    default_env = load_environment()
    if default_env.max_total_completion_tokens != env_mod.MAX_EPISODE_OUTPUT_TOKENS:
        problems.append(f"load_environment() ceiling {default_env.max_total_completion_tokens}")
    if load_environment(max_episode_output_tokens=12_345).max_total_completion_tokens != 12_345:
        problems.append("load_environment ignored max_episode_output_tokens")
    off = load_environment(max_episode_output_tokens=0)
    if off.max_total_completion_tokens != 0:
        problems.append(f"a disabled ceiling is {off.max_total_completion_tokens}")
    turns = [read_turn(f"g{i}") for i in range(7)] + [write(), submit()]
    results, client, _args, raised = run_budgeted(turns, 7_000, 8_000, env=off)
    if raised is not None:
        problems.append(f"disabled: evaluate raised {type(raised).__name__}: {raised}")
    else:
        out = one(results)
        metrics = out.get("metrics") or {}
        if set(client.caps) != {8_000}:
            problems.append(f"disabled: the per-turn cap was clamped anyway: {client.caps}")
        if sum(client.spent) <= env_mod.MAX_EPISODE_OUTPUT_TOKENS:
            problems.append(f"disabled: only {sum(client.spent)} tokens spent — the route does not "
                            f"pass {env_mod.MAX_EPISODE_OUTPUT_TOKENS}, so nothing is witnessed")
        if out.get("stop_condition") != "piv_submitted":
            problems.append(f"disabled: stop_condition {out.get('stop_condition')!r}")
        if metrics.get(env_mod.METRIC_OUTPUT_BUDGET_EXHAUSTED) != 0.0:
            problems.append("disabled: the budget stop fired with the ceiling off")
        if out.get("piv_request_max_tokens"):
            problems.append(f"disabled: requests were recorded ({out.get('piv_request_max_tokens')}), "
                            "so something clamped")
    return check("the ceiling is a load_environment kwarg defaulting to MAX_EPISODE_OUTPUT_TOKENS; "
                 "0 disables the clamp and the stop", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 4. the turn cap is unchanged
# --------------------------------------------------------------------------

def test_max_turns_without_submit_scores_the_last_committed_revision():
    """No submit, 25 turns of work: the last committed revision decides.

    The write lands on turn one and every later turn is a read, so the run of
    consecutive no-tool turns never starts and the episode can only end at the
    cap — which is exactly the "or the turn limit" half of PLAN §6.

    THE TURN-CAP RULE, pinned here: reaching `max_turns`
    without an accepted `submit` scores the LAST COMMITTED REVISION exactly as
    before — this route's ledger is the golden one and it is worth 1.0 — and
    the only thing that changes is the NAME of the ending,
    `piv_turn_cap_no_submit`, projected as its own metric. The rejected
    alternative was reward 0 at the cap: it would discard a ledger the agent
    genuinely delivered through the loop over one missing final call, and it
    would bury the missing call inside an ordinary bad score where no
    aggregate could find it. `piv/submitted` is 0.0 and
    `piv/turn_cap_no_submit` is 1.0, which is how a policy that never submits
    learns that submitting is part of the task.
    """
    turns = [write()] + [calls((f"r{i}", "list_files", {})) for i in range(40)]
    results, client, raised = run(turns)
    if raised is not None:
        return check("the turn cap must not raise", False, str(raised))
    out = one(results)
    metrics = out.get("metrics") or {}
    problems = []
    if out.get("stop_condition") != "piv_turn_cap_no_submit":
        problems.append(f"stop_condition {out.get('stop_condition')!r}")
    if metrics.get(env_mod.METRIC_TURN_CAP_NO_SUBMIT) != 1.0:
        problems.append(f"piv/turn_cap_no_submit {metrics.get(env_mod.METRIC_TURN_CAP_NO_SUBMIT)}")
    if metrics.get("num_turns") != 25:
        problems.append(f"num_turns {metrics.get('num_turns')}, expected the unchanged cap of 25")
    if client.turn != 25:
        problems.append(f"the model was asked {client.turn} times")
    if out.get("reward") != 1.0:
        problems.append(f"reward {out.get('reward')}; the last committed revision must still decide")
    if metrics.get(env_mod.METRIC_SUBMITTED) != 0.0:
        problems.append("piv/submitted set without a submit")
    if results["metadata"].get("piv_status") != "VALID":
        problems.append(f"batch status {results['metadata'].get('piv_status')}")
    return check("max_turns reached without submit -> 25 turns, last committed revision decides, VALID",
                 not problems, "\n".join(problems))


def test_a_submit_on_the_last_turn_is_named_unexecuted_not_never_submitted():
    """The second verifier's finding. The framework executes a turn's tool
    calls at the top of the NEXT iteration and checks completion first, so
    a `submit` on turn 25 is never run. That ending must not be labelled
    `piv_turn_cap_no_submit` — the policy did submit, one turn late — and
    the agent is told the executed budget is 24 turns. The last committed
    revision is scored, as at every cap."""
    turns = [write()] + [calls((f"r{i}", "list_files", {})) for i in range(23)] + [calls(("s", "submit", {}))]
    results, client, raised = run(turns)
    if raised is not None:
        return check("a submit on the last turn must not raise", False, str(raised))
    out = one(results)
    metrics = out.get("metrics") or {}
    problems = []
    if out.get("stop_condition") != "piv_turn_cap_submit_unexecuted":
        problems.append(f"stop_condition {out.get('stop_condition')!r}")
    if metrics.get(env_mod.METRIC_TURN_CAP_SUBMIT_UNEXECUTED) != 1.0:
        problems.append(f"piv/turn_cap_submit_unexecuted {metrics.get(env_mod.METRIC_TURN_CAP_SUBMIT_UNEXECUTED)}")
    if metrics.get(env_mod.METRIC_TURN_CAP_NO_SUBMIT) != 0.0:
        problems.append("piv/turn_cap_no_submit claims the agent never submitted")
    if metrics.get(env_mod.METRIC_SUBMITTED) != 0.0:
        problems.append("piv/submitted set although the submit was never executed")
    if out.get("reward") != 1.0:
        problems.append(f"reward {out.get('reward')}; the last committed revision must still decide")
    if client.turn != 25:
        problems.append(f"the model was asked {client.turn} times")
    if "turn 24" not in env_mod.SYSTEM_PROMPT:
        problems.append("the system prompt does not state the executed budget")
    # control: the same submit one turn earlier is executed and accepted
    turns = [write()] + [calls((f"r{i}", "list_files", {})) for i in range(22)] + [calls(("s", "submit", {}))]
    results, client, raised = run(turns)
    out = one(results) if raised is None else {}
    if raised is not None or out.get("stop_condition") != "piv_submitted":
        problems.append(f"submit on turn 24: {raised or out.get('stop_condition')!r}")
    return check("a submit on the last turn ends as piv_turn_cap_submit_unexecuted (not never-submitted), scores the "
                 "last committed revision, and the prompt names the executed budget; one turn earlier it is accepted",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3c. the two token-limit spellings are ONE field on the wire
# --------------------------------------------------------------------------

class SamplingScript(TurnScript):
    """Records the sampling args of every request, unmodified.

    `vf.Client.get_response` performs NO sampling-arg transformation — the
    rename lives inside `OpenAIChatCompletionsClient.get_native_response` —
    so what this sees is exactly what the environment handed the client, and
    the wire assertion below has to be made separately, against the real
    client's own normalisation.
    """

    def __init__(self, turns, completion_tokens=None):
        super().__init__(turns)
        self.seen = []
        self.completion_tokens = completion_tokens

    async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
        self.seen.append(dict(sampling_args))
        self.turn += 1
        message = self.turns[self.turn - 1] if self.turn <= len(self.turns) else empty()
        usage = None
        if self.completion_tokens is not None:
            usage = Usage(prompt_tokens=10, reasoning_tokens=0,
                          completion_tokens=self.completion_tokens,
                          total_tokens=10 + self.completion_tokens)
        return Response(id=f"scripted-{self.turn}", created=0, model=model, usage=usage, message=message)


def run_sampling(sampling_args, turns=None, env=None, completion_tokens=None):
    """One rollout with an arbitrary caller sampling_args dict."""
    env = env or load_environment()
    client = SamplingScript(turns or [submit()], completion_tokens=completion_tokens)
    try:
        results = asyncio.run(env.evaluate(
            client=client, model="scripted", num_examples=1, rollouts_per_example=1,
            max_concurrent=1, save_results=False, sampling_args=sampling_args,
            state_columns=["piv_request_max_tokens", "piv_budget_accounting_invalid"]))
        return results, client, None
    except env_mod.PIVEvaluationBatchInvalid as exc:
        return None, client, exc


def test_both_token_limit_spellings_are_clamped_into_one_field():
    """The two-key bug: with both present the clamp was DEFEATED, not weakened.

    Measured in verifiers 0.3.1
    (`OpenAIChatCompletionsClient.get_native_response.normalize_sampling_args`):

        if "max_tokens" in sampling_args:
            sampling_args["max_completion_tokens"] = sampling_args.pop("max_tokens")

    `max_tokens` OVERWRITES `max_completion_tokens`, and the request body
    carries exactly one field, `max_completion_tokens`. The old environment
    clamped whichever key it found first — `max_completion_tokens` when
    present — so a caller passing both had the clamped value thrown away by
    that rename and the UNCLAMPED `max_tokens` shipped to the provider.

    The normalisation is now the environment's: whatever the caller passed,
    exactly one field leaves, `TOKEN_CAP_FIELD`, carrying
    `min(every valid caller cap, remaining ceiling)`.

    AND A MALFORMED CAP IS NOT AN ABSENT CAP. The exact
    answers are pinned below, because "minimum of every valid cap" left one
    ambiguity that costs money in the wrong direction: a caller who typed one
    good spelling and one bad one asked for something we cannot honour, and
    honouring the half we understood is a guess. The table:

        None                       absent; the remaining ceiling applies
        positive non-bool int      a cap
        0, -5, True, 8000.0,
        "8000", [8000]             TypeError, before any provider request
        one valid + one invalid    TypeError; the valid half is NOT used
        both valid                 min(both, remainder)
        neither                    the remainder

    `8000.0` was accepted before, as "a whole number a JSON round-trip
    produced". That is a guess about intent made at the one place where
    guessing is expensive, so an integral float now raises like every other
    float; a caller that means 8,000 tokens can type an int.
    """
    problems = []
    ceiling = env_mod.MAX_EPISODE_OUTPUT_TOKENS
    cases = (
        ("both, max_tokens larger", {"max_tokens": 8_000, "max_completion_tokens": 3_000}, 3_000),
        ("both, reversed", {"max_completion_tokens": 8_000, "max_tokens": 3_000}, 3_000),
        ("max_tokens only", {"max_tokens": 5_000}, 5_000),
        ("max_completion_tokens only", {"max_completion_tokens": 5_000}, 5_000),
        ("neither", {"temperature": 0.0}, ceiling),
        ("both above the ceiling", {"max_tokens": 90_000, "max_completion_tokens": 80_000}, ceiling),
        ("None means no cap stated", {"max_tokens": None, "max_completion_tokens": 4_000}, 4_000),
    )
    for label, caller_args, expected in cases:
        original = dict(caller_args)
        results, client, raised = run_sampling(dict(caller_args))
        if raised is not None:
            problems.append(f"{label}: evaluate raised {type(raised).__name__}: {raised}")
            continue
        if not client.seen:
            problems.append(f"{label}: no request was made")
            continue
        sent = client.seen[0]
        others = [k for k in ("max_tokens", "max_completion_tokens") if k != env_mod.TOKEN_CAP_FIELD]
        for other in others:
            if other in sent:
                problems.append(f"{label}: {other} still reached the client: {sent}")
        if sent.get(env_mod.TOKEN_CAP_FIELD) != expected:
            problems.append(f"{label}: {env_mod.TOKEN_CAP_FIELD} {sent.get(env_mod.TOKEN_CAP_FIELD)}, "
                            f"expected {expected}")
        recorded = one(results).get("piv_request_max_tokens")
        if not recorded or recorded[0] != expected:
            problems.append(f"{label}: piv_request_max_tokens {recorded}, expected [{expected}, ...]")
        # every other sampling field the caller set survives untouched
        for key, value in original.items():
            if key in ("max_tokens", "max_completion_tokens"):
                continue
            if sent.get(key) != value:
                problems.append(f"{label}: the caller's {key} was dropped or changed: {sent.get(key)!r}")

    # THE NORMALIZER'S EXACT ANSWERS. A malformed cap is a
    # TypeError, not a bigger budget: it used to be swallowed as "not a cap",
    # so `{"max_tokens": "8000"}` out of an untyped config asked the provider
    # for the whole 40,000-token remainder — five times what the caller typed,
    # on a paid call. Every case the reviewer named is pinned by value.
    for bad in ("8000", 3_000.5, 8_000.0, True, False, 0, -5, -1, [8_000], {"n": 8_000}):
        try:
            env_mod._token_cap("max_tokens", bad)
            problems.append(f"a cap of {bad!r} was accepted or silently ignored")
        except TypeError:
            pass
    if env_mod._token_cap("max_tokens", None) is not None:
        problems.append("an absent cap must stay absent, not raise")
    if env_mod._token_cap("max_tokens", 8_000) != 8_000:
        problems.append("a positive int is a cap")

    # EVERY SPELLING, ONE BY ONE. THREE, not two: the responses client's
    # `normalize_sampling_args` maps `max_tokens`/`max_completion_tokens` onto
    # `max_output_tokens` only `if "max_output_tokens" not in sampling_args`,
    # so a caller who states that third field KEEPS it — unvalidated and
    # unclamped by the episode ceiling. It had no witness at all, and the
    # adversarial pass named the trap: deleting it from TOKEN_CAP_SPELLINGS
    # left the contract digest byte-identical and turned
    # `{"max_output_tokens": "8000"}` from a TypeError back into "no cap
    # stated" — the whole 40,000-token remainder, on a paid call. So each
    # spelling is pinned on its own, and the tuple is in the digest below.
    # The three are written out HERE, as literals, and the loop below walks
    # THESE rather than `env_mod.TOKEN_CAP_SPELLINGS`. Walking the tuple would
    # make the whole loop shrink with it: delete a spelling and every
    # per-spelling witness quietly stops being asked. The literal list is what
    # makes a deletion fail on the behaviour, not only on the pin.
    SPELLINGS = ("max_tokens", "max_completion_tokens", "max_output_tokens")
    if env_mod.TOKEN_CAP_SPELLINGS != SPELLINGS:
        problems.append(f"TOKEN_CAP_SPELLINGS moved: {env_mod.TOKEN_CAP_SPELLINGS}")
    if env_mod.TOKEN_CAP_FIELD not in SPELLINGS:
        problems.append("the field the environment emits is not one of the spellings it reads")
    for field in SPELLINGS:
        # valid on its own
        if env_mod.caller_token_caps({field: 8_000}) != [8_000]:
            problems.append(f"{field}: a valid cap on its own was not read")
        # absent means absent
        if env_mod.caller_token_caps({field: None}) != []:
            problems.append(f"{field}: None is not absent")
        # malformed raises — and this is the assertion that fails if the
        # spelling is ever dropped from the tuple, because an unread field is
        # silently "no cap stated" rather than an error
        for bad in ("8000", 0, -5, True, 8_000.0):
            try:
                env_mod.caller_token_caps({field: bad})
                problems.append(f"{field}={bad!r} was accepted or silently ignored; is {field} still "
                                f"in TOKEN_CAP_SPELLINGS?")
            except TypeError:
                pass
        # ...and mixed with a VALID other spelling it still rejects: the good
        # half must not be honoured on its own
        other = next(f for f in SPELLINGS if f != field)
        try:
            env_mod.caller_token_caps({field: "x", other: 8_000})
            problems.append(f"{field} invalid beside a valid {other}: the request was accepted")
        except TypeError:
            pass
        try:
            env_mod.caller_token_caps({field: 8_000, other: 0})
            problems.append(f"{field} valid beside an invalid {other}: the request was accepted")
        except TypeError:
            pass
    if env_mod.caller_token_caps({"max_tokens": 8_000, "max_completion_tokens": 3_000,
                                  "max_output_tokens": 5_000}) != [8_000, 3_000, 5_000]:
        problems.append("the three valid spellings are not all returned")
    if env_mod.caller_token_caps({"temperature": 0.0}) != []:
        problems.append("no spelling present should state no cap at all")
    # the tuple is BOUND: dropping a spelling must move the digest, not pass
    # unnoticed
    view_spellings = ((env_mod.episode_contract().get("budgets") or {}).get("token_cap_spellings"))
    if view_spellings != list(env_mod.TOKEN_CAP_SPELLINGS):
        problems.append(f"the contract view does not carry the spellings: {view_spellings!r}")
    baseline = env_mod.episode_contract_digest()
    original = env_mod.TOKEN_CAP_SPELLINGS
    try:
        env_mod.TOKEN_CAP_SPELLINGS = original[:-1]
        if env_mod.episode_contract_digest() == baseline:
            problems.append("dropping a cap spelling leaves the episode contract digest unchanged")
    finally:
        env_mod.TOKEN_CAP_SPELLINGS = original
    if env_mod.episode_contract_digest() != baseline:
        problems.append("the digest did not come back after the spelling mutation")
    # every spelling is REMOVED from the request when the ceiling clamps, so
    # exactly one field reaches the client whichever one the caller typed
    for field in SPELLINGS:
        _results, client, raised = run_sampling({field: 6_000})
        if raised is not None or not client.seen:
            problems.append(f"{field}: no request was made ({raised})")
            continue
        sent = client.seen[0]
        leftover = [f for f in SPELLINGS
                    if f != env_mod.TOKEN_CAP_FIELD and f in sent]
        if leftover:
            problems.append(f"{field}: {leftover} still reached the client: {sent}")
        if sent.get(env_mod.TOKEN_CAP_FIELD) != 6_000:
            problems.append(f"{field}: the clamped field is {sent.get(env_mod.TOKEN_CAP_FIELD)}, not 6000")

    # ...and the rejection happens BEFORE a provider is called, on the real
    # door, with the ceiling both ON and OFF — with the ceiling disabled the
    # environment adds no clamp of its own that would catch it later.
    for label, env in (("ceiling on", load_environment()),
                       ("ceiling off", load_environment(max_episode_output_tokens=0))):
        client = TurnScript([write(), submit()])
        try:
            asyncio.run(env.evaluate(client=client, model="scripted", num_examples=1,
                                     rollouts_per_example=1, max_concurrent=1, save_results=False,
                                     sampling_args={"max_tokens": "8000"}))
            problems.append(f"{label}: a string cap reached a request")
        except (TypeError, env_mod.PIVEvaluationBatchInvalid):
            pass
        if client.turn:
            problems.append(f"{label}: {client.turn} request(s) were made with a malformed cap")
    return check("all THREE cap spellings (max_tokens, max_completion_tokens, max_output_tokens) are "
                 f"read, validated and normalised into exactly one clamped {env_mod.TOKEN_CAP_FIELD}; "
                 "None is absent, 0/-5/True/8000.0/'8000' raise for each, one valid spelling beside an "
                 "invalid one rejects before any provider call, and the tuple is bound by the digest",
                 not problems, "\n".join(problems))


def test_the_native_request_body_carries_the_intended_cap():
    """The WIRE assertion, through the real client's own transformation.

    `state["piv_request_max_tokens"]` is our arithmetic; it cannot witness
    what the provider was actually asked for. The scripted
    clients above override `get_response`/`get_native_response` and so never
    execute the rename at all — so this drives the REAL
    `OpenAIChatCompletionsClient.get_native_response` over the environment's
    clamped dict and captures the request body it posts, with the HTTP call
    itself replaced.

    Two claims: the body carries exactly one token-limit field with the
    intended cap, and the pre-normalised pair (the shape the old code could
    emit) would have shipped the UNCLAMPED number — which is why emitting one
    field is not cosmetic.
    """
    import verifiers.legacy.clients.openai_chat_completions_client as occ

    problems = []
    captured = {}

    async def fake_post(client, path, *, body, extra_headers=None):
        captured.clear()
        captured.update(body)
        raise _Captured()

    class _Captured(Exception):
        pass

    client = occ.OpenAIChatCompletionsClient.__new__(occ.OpenAIChatCompletionsClient)
    client._client = SimpleNamespace(base_url="https://integrate.api.nvidia.com/v1")
    client._config = None

    def body_for(sampling_args):
        original = occ.post_chat_completion_with_routed_experts_sidecar
        occ.post_chat_completion_with_routed_experts_sidecar = fake_post
        try:
            asyncio.run(occ.OpenAIChatCompletionsClient.get_native_response(
                client, [{"role": "user", "content": "hi"}], "scripted", dict(sampling_args)))
        except _Captured:
            pass
        except Exception as exc:                       # noqa: BLE001
            problems.append(f"the real client raised before posting: {type(exc).__name__}: {exc}")
        finally:
            occ.post_chat_completion_with_routed_experts_sidecar = original
        return dict(captured)

    # what the environment now emits: exactly one field, already clamped
    emitted = body_for({env_mod.TOKEN_CAP_FIELD: 3_000, "temperature": 0.0})
    limits = {k: v for k, v in emitted.items() if k in ("max_tokens", "max_completion_tokens")}
    if limits != {"max_completion_tokens": 3_000}:
        problems.append(f"the native body carried {limits}, expected one clamped max_completion_tokens")
    if emitted.get("temperature") != 0.0:
        problems.append(f"the native body lost the caller's temperature: {emitted.get('temperature')!r}")

    # the shape the two-key bug produced: the clamped field is overwritten by
    # the unclamped one, and the provider is asked for 8,000 after a 3,000 clamp
    defeated = body_for({"max_completion_tokens": 3_000, "max_tokens": 8_000})
    if defeated.get("max_completion_tokens") != 8_000 or "max_tokens" in defeated:
        problems.append(f"the client's rename does not behave as documented: {defeated}")

    # ...and the OTHER clients. `max_completion_tokens` is understood by the
    # chat clients, the responses client and the renderer, but the Anthropic
    # messages client pops only `max_tokens`, warns, falls back to 4096, and
    # forwards whatever is left verbatim into `messages.create(**…)` — so
    # emitting the chat spelling there loses the clamp AND hands the SDK a
    # keyword it has no parameter for. The field we emit must be the one EVERY
    # client understands.
    import verifiers.legacy.clients.anthropic_messages_client as amc

    sent = {}

    class _Messages:
        async def create(self, **kwargs):
            sent.clear()
            sent.update(kwargs)
            raise _Captured()

    anthropic = amc.AnthropicMessagesClient.__new__(amc.AnthropicMessagesClient)
    anthropic._client = SimpleNamespace(messages=_Messages())
    anthropic._config = None
    anthropic.logger = logging.getLogger("piv-test-anthropic")
    try:
        asyncio.run(amc.AnthropicMessagesClient.get_native_response(
            anthropic, [{"role": "user", "content": "hi"}], "claude-x",
            {env_mod.TOKEN_CAP_FIELD: 3_000}))
    except _Captured:
        pass
    except Exception as exc:                           # noqa: BLE001
        problems.append(f"the anthropic client raised before sending: {type(exc).__name__}: {exc}")
    if sent.get("max_tokens") != 3_000:
        problems.append(f"the anthropic request lost the clamp: max_tokens {sent.get('max_tokens')!r}")
    if "max_completion_tokens" in sent:
        problems.append(f"an unknown keyword reached the anthropic SDK: {sorted(sent)}")
    return check("the REAL legacy client's request body carries exactly one max_completion_tokens equal to "
                 "the environment's intended cap; the un-normalised pair would have shipped the unclamped "
                 "number; and the field the environment emits still clamps the anthropic client",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3d. provider usage that cannot meter the ceiling fails CLOSED
# --------------------------------------------------------------------------

class BadUsageScript(TurnScript):
    """Reports a usage object the budget accounting must refuse to trust.

    `Response.model_construct` because the point is a usage the framework's
    validation would reject: a provider adapter that builds its response the
    same way, or a `Usage` subclass, is exactly the case the guard exists for.
    """

    def __init__(self, turns, usages):
        super().__init__(turns)
        self.usages = list(usages)

    async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
        self.turn += 1
        message = self.turns[self.turn - 1] if self.turn <= len(self.turns) else empty()
        usage = self.usages[min(self.turn, len(self.usages)) - 1]
        return Response.model_construct(id=f"scripted-{self.turn}", created=0, model=model,
                                        usage=usage, message=message)


def test_provider_usage_that_cannot_meter_the_ceiling_is_flagged_not_scored():
    """Missing or impossible usage is recorded, never treated as zero.

    The ceiling is metered from `completion_tokens`. Absent usage silently
    reads as "spent nothing", so the ceiling never bites and the rollout's
    equal-budget claim is fiction; a `completion_tokens` above the cap the
    request carried says the provider ignored the clamp. Neither is an
    evaluator failure and neither is the agent's fault, so neither may change
    the reward or quarantine anything: the consequence is a sticky reason in
    `piv_budget_accounting_invalid` and the zero-weight metric, which the
    measurement excludes from budget analyses.

    The battery depends on this being SILENT: `TurnScript` reports no usage at
    all and drives most of the routes above.

    Two of the four violation kinds cannot be produced through the loop at
    all, because the framework's own accumulator refuses them first —
    `usage_utils.usage_tokens` raises on a negative `completion_tokens`, and
    `StateUsageTracker` only ever increments, so a cumulative total cannot
    decrease. They are witnessed against the guard directly below: the guard
    is fail-closed defence, and defence that only works while the layer under
    it is correct is not defence.
    """
    problems = []
    good = Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=100, total_tokens=110)
    cases = (
        ("usage absent", [None], env_mod.BUDGET_USAGE_ABSENT, empty()),
        ("non-integer completion_tokens",
         [SimpleNamespace(prompt_tokens=10, completion_tokens=5.5, reasoning_tokens=0, total_tokens=15)],
         env_mod.BUDGET_USAGE_NOT_INTEGER, empty()),
        ("more than the request cap",
         [Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=9_000, total_tokens=9_010)],
         env_mod.BUDGET_COMPLETION_EXCEEDS_CAP, empty()),
        # absent usage wearing a number: 0 every turn keeps the tracker at 0,
        # so the ceiling never bites, and 0 passes every other check here
        ("zero tokens for a turn that spoke",
         [Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=0, total_tokens=10)],
         env_mod.BUDGET_USAGE_ZERO_ON_SPOKEN_TURN, narrated("I am thinking about the ledger.")),
    )
    for label, usages, needle, first in cases:
        env = load_environment()
        client = BadUsageScript([first, write(), submit()], usages)
        try:
            results = asyncio.run(env.evaluate(
                client=client, model="scripted", num_examples=1, rollouts_per_example=1,
                max_concurrent=1, save_results=False, sampling_args={"max_tokens": 5_000},
                state_columns=["piv_budget_accounting_invalid", "piv_budget_accounting_detail"]))
        except env_mod.PIVEvaluationBatchInvalid as exc:
            problems.append(f"{label}: evaluate raised {type(exc).__name__}: {exc}")
            continue
        out = one(results)
        metrics = out.get("metrics") or {}
        code = out.get("piv_budget_accounting_invalid")
        if code != needle:
            problems.append(f"{label}: code {code!r}, expected {needle!r}")
        detail = out.get("piv_budget_accounting_detail")
        if not detail or detail == code:
            problems.append(f"{label}: no separate detail: {detail!r}")
        if metrics.get(env_mod.METRIC_BUDGET_ACCOUNTING_INVALID) != 1.0:
            problems.append(f"{label}: {env_mod.METRIC_BUDGET_ACCOUNTING_INVALID} "
                            f"{metrics.get(env_mod.METRIC_BUDGET_ACCOUNTING_INVALID)}")
        if out.get("error") is not None:
            problems.append(f"{label}: flagged accounting became an evaluator failure: {out.get('error')}")
        if metrics.get("piv/evaluator_failed") != 0.0 or metrics.get("piv/training_eligible") != 1.0:
            problems.append(f"{label}: the rollout was treated as a failure")
        if results["metadata"].get("piv_status") != "VALID":
            problems.append(f"{label}: batch status {results['metadata'].get('piv_status')}")
        if out.get("reward") != 1.0:
            problems.append(f"{label}: reward {out.get('reward')}, expected the delivered ledger's 1.0")

    # sticky: the FIRST violation is the diagnosis, and a later good turn does
    # not wash it away
    env = load_environment()
    client = BadUsageScript([read_turn("g1"), write(), submit()], [None, good, good])
    results = asyncio.run(env.evaluate(
        client=client, model="scripted", num_examples=1, rollouts_per_example=1,
        max_concurrent=1, save_results=False, sampling_args={"max_tokens": 5_000},
        state_columns=["piv_budget_accounting_invalid"]))
    if one(results).get("piv_budget_accounting_invalid") != env_mod.BUDGET_USAGE_ABSENT:
        problems.append(f"the first violation was overwritten: {one(results).get('piv_budget_accounting_invalid')!r}")

    # the flag is a CODE from a closed vocabulary, not prose: a measurement
    # groups by it, and the first version put the numbers in the flag itself
    # so every rollout landed in its own histogram bucket
    if len(set(env_mod.BUDGET_ACCOUNTING_CODES)) != len(env_mod.BUDGET_ACCOUNTING_CODES):
        problems.append("the code vocabulary has duplicates")
    # SUSPICIOUS IS NOT INVALID. The five codes above are
    # theorems about the provider's arithmetic; the chars/token floor is a
    # heuristic over an unknown tokenizer, and a replay arm changes the shape
    # of the emitted text — so letting it decide validity would exclude one
    # arm more often than another and bias the very comparison it protects.
    if set(env_mod.BUDGET_ACCOUNTING_CODES) != {
            "usage_absent", "usage_not_integer", "completion_exceeds_cap",
            "cumulative_decreased", "usage_zero_on_spoken_turn"}:
        problems.append(f"the hard-invalid vocabulary moved: {env_mod.BUDGET_ACCOUNTING_CODES}")
    if set(env_mod.BUDGET_SUSPICIOUS_CODES) != {"usage_implausible"}:
        problems.append(f"the suspicious vocabulary moved: {env_mod.BUDGET_SUSPICIOUS_CODES}")
    if env_mod.BUDGET_USAGE_IMPLAUSIBLE in env_mod.BUDGET_ACCOUNTING_CODES:
        problems.append("usage_implausible is still a hard-invalid code")

    # ...and the under-reporting provider — one token a turn for thousands of
    # characters, never zero, never over the cap, never decreasing, a ceiling
    # that would not bite in a hundred turns — lands in the SOFT channel, on
    # its own keys and its own metric, with validity untouched.
    env = load_environment()
    client = BadUsageScript(
        [narrated("reconciling. " * 400), write(), submit()],
        [Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=1, total_tokens=11), good, good])
    results = asyncio.run(env.evaluate(
        client=client, model="scripted", num_examples=1, rollouts_per_example=1,
        max_concurrent=1, save_results=False, sampling_args={"max_tokens": 5_000},
        state_columns=["piv_budget_accounting_invalid", "piv_budget_accounting_suspicious",
                       "piv_budget_accounting_suspicious_detail"]))
    out = one(results)
    metrics = out.get("metrics") or {}
    if out.get("piv_budget_accounting_suspicious") != env_mod.BUDGET_USAGE_IMPLAUSIBLE:
        problems.append(f"the implausible turn was not flagged suspicious: "
                        f"{out.get('piv_budget_accounting_suspicious')!r}")
    if not out.get("piv_budget_accounting_suspicious_detail"):
        problems.append("the suspicion carries no detail with the numbers")
    if out.get("piv_budget_accounting_invalid") is not None:
        problems.append(f"the heuristic invalidated the row: {out.get('piv_budget_accounting_invalid')!r}")
    if metrics.get(env_mod.METRIC_BUDGET_ACCOUNTING_SUSPICIOUS) != 1.0:
        problems.append(f"{env_mod.METRIC_BUDGET_ACCOUNTING_SUSPICIOUS} "
                        f"{metrics.get(env_mod.METRIC_BUDGET_ACCOUNTING_SUSPICIOUS)}")
    if metrics.get(env_mod.METRIC_BUDGET_ACCOUNTING_INVALID) != 0.0:
        problems.append("a suspicious row was counted as accounting-invalid")
    if out.get("reward") != 1.0:
        problems.append(f"the suspicious rollout scored {out.get('reward')}, expected the ledger's 1.0")

    # the one kind the framework's accumulator makes unreachable — it only
    # ever increments — put to the guard directly
    env = load_environment()
    state = {"usage": {"input_tokens": 0.0, "output_tokens": 100.0}}
    env._check_budget_accounting(
        state, Response.model_construct(id="x", created=0, model="m", usage=good, message=empty()),
        5_000, 10_000)
    if state.get("piv_budget_accounting_invalid") != env_mod.BUDGET_CUMULATIVE_DECREASED:
        problems.append(f"a decreasing total: {state.get('piv_budget_accounting_invalid')!r}")

    # a NEGATIVE completion count is refused by the framework's own accounting
    # (`usage_utils.usage_tokens` raises a plain ValueError) before the guard
    # can see it — and a plain ValueError is not a `vf.Error`, so the rollout
    # loop does not catch it and one bad usage object would take the whole
    # BATCH down. It is converted to the framework's ModelError, which
    # ERROR_CONSEQUENCES already quarantines, with the code recorded.
    env = load_environment()
    negative = Usage.model_construct(prompt_tokens=10, reasoning_tokens=0,
                                     completion_tokens=-5, total_tokens=5)
    client = BadUsageScript([read_turn("g1"), write(), submit()], [negative])
    try:
        asyncio.run(env.evaluate(
            client=client, model="scripted", num_examples=1, rollouts_per_example=1,
            max_concurrent=1, save_results=False, sampling_args={"max_tokens": 5_000},
            state_columns=["piv_budget_accounting_invalid"]))
        problems.append("a negative completion count did not fail the batch closed")
    except env_mod.PIVEvaluationBatchInvalid as exc:
        if "ModelError" not in str(exc):
            problems.append(f"a negative completion count was not quarantined as a model error: {exc}")
    except ValueError as exc:
        problems.append(f"a negative completion count escaped as a bare ValueError: {exc}")

    # the control: valid usage all the way through is NOT flagged
    results, client, _args, raised = run_budgeted([read_turn("g1"), write(), submit()], 7_000, 8_000)
    if raised is not None:
        problems.append(f"valid usage: evaluate raised {type(raised).__name__}: {raised}")
    else:
        out = one(results)
        if (out.get("metrics") or {}).get(env_mod.METRIC_BUDGET_ACCOUNTING_INVALID) != 0.0:
            problems.append("a BudgetScript rollout with valid usage was flagged")
    return check("every budget-accounting failure is one code from the closed hard vocabulary with its "
                 "prose in a separate key: absent / non-integer / zero-on-a-spoken-turn / over-cap / "
                 "decreasing; the chars-per-token heuristic is SUSPICIOUS on its own keys and metric and "
                 "never invalidates; no reward changes; a negative count is quarantined, not crashed",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3e. the episode contract has its own identity
# --------------------------------------------------------------------------

#: The pinned episode-contract digest. It covers the system prompt, the tool
#: names/descriptions/schemas the framework generates, the observation modes
#: and envelope, the phase machine, the stop conditions in priority order, the
#: budgets and the pending-call rule, and every public nudge or refusal.
EPISODE_CONTRACT_DIGEST = "152dbbaf80a1f761d42d5b94139fd64c320f0810cbbe4855c7cb1cc0766fea59"


def test_the_episode_contract_digest_is_pinned():
    """A rollout's observation and termination rules have an identity.

    `public_task_id` binds the public files and the task prompt;
    `task_contract_digest` binds the scorer's normative view. Neither notices
    that the SYSTEM prompt, the whole-read rule, the output ceiling or a stop
    priority changed — so the same task id could be served under materially
    different rules and two batches compared as if they were one condition.
    This is the pin that makes such a change loud.
    """
    problems = []
    if env_mod.episode_contract_digest() != EPISODE_CONTRACT_DIGEST:
        problems.append(f"the episode contract changed: bump EPISODE_CONTRACT_VERSION and re-pin "
                        f"(now {env_mod.episode_contract_digest()}, pinned {EPISODE_CONTRACT_DIGEST})")
    if env_mod.EPISODE_CONTRACT_VERSION != 2:
        problems.append(f"EPISODE_CONTRACT_VERSION is {env_mod.EPISODE_CONTRACT_VERSION}; re-pin the digest")
    view = env_mod.episode_contract()
    if view.get("system_prompt") != env_mod.SYSTEM_PROMPT:
        problems.append("the contract view does not carry the exact system prompt")

    # the tool schemas are the framework's, not a hand-kept copy: the view's
    # tools must equal a live environment's advertised tool_defs
    env = load_environment()
    live = [{"name": t.name, "description": t.description or "", "parameters": t.parameters,
             "strict": bool(t.strict)} for t in env.tool_defs]
    if view.get("tools") != live:
        problems.append("the contract's tool definitions are not the ones the environment advertises")

    # the stop conditions, with the priorities `@vf.stop` recorded — names
    # alone would let an edited priority that preserves the order pass
    live_stops = [(c.__name__, getattr(c, "stop_priority", 0)) for c in env._stop_conditions]
    if [tuple(row) for row in env_mod.STOP_CONDITION_PRIORITY] != live_stops:
        problems.append(f"STOP_CONDITION_PRIORITY {list(env_mod.STOP_CONDITION_PRIORITY)} "
                        f"is not the live order/priority {live_stops}")

    # every rollout and every batch carries it
    state = {}
    env._workspace(state)
    if state.get("piv_episode_contract_digest") != EPISODE_CONTRACT_DIGEST:
        problems.append(f"the rollout does not carry the digest: {state.get('piv_episode_contract_digest')!r}")
    # ...including a rollout that never calls a tool and so never builds a
    # workspace: that is `setup_state`'s whole job, and without this witness
    # the override could be deleted with every other test still passing
    bare, _client, raised = run([narrated(), narrated(), narrated()],
                                state_columns=["piv_episode_contract_digest", "workspace"])
    if raised is not None:
        problems.append(f"the no-tool route raised {type(raised).__name__}")
    else:
        out = (bare["outputs"] or [{}])[0]
        if out.get("workspace"):
            problems.append("the no-tool route built a workspace; the witness is not about setup_state")
        if out.get("piv_episode_contract_digest") != EPISODE_CONTRACT_DIGEST:
            problems.append("a rollout that never called a tool carries no contract digest: "
                            f"{out.get('piv_episode_contract_digest')!r}")
    results, _client, raised = run([write(), submit()])
    if raised is not None:
        problems.append(f"evaluate raised {type(raised).__name__}")
    else:
        stamped = (results["metadata"] or {}).get("piv_episode_contract")
        if stamped != {"version": env_mod.EPISODE_CONTRACT_VERSION, "digest": EPISODE_CONTRACT_DIGEST,
                       "max_episode_output_tokens": env_mod.MAX_EPISODE_OUTPUT_TOKENS}:
            problems.append(f"the batch metadata does not carry the contract: {stamped}")

    # ...and the RELEASE MANIFEST is deliberately NOT bound to it. It was,
    # and the binding was unsound: `load_environment` admits
    # BEFORE it constructs the environment, and then takes
    # `max_episode_output_tokens` — so a world admitted under the 40,000-token
    # digest could be served at 8,000 with no second check, the manifest
    # attesting a contract nobody preflighted. Separation was preferred over
    # strict binding, because golden bookkeeping validity does not depend on
    # the ceiling and experiment comparability does. So the manifest binds the
    # WORLD; the episode contract is bound on every rollout and every batch,
    # which the three witnesses above are.
    from beancount_ledger.graph import manifest as MF
    versions = MF.versions()
    if set(versions) != {"generator", "identify", "scorer_contract", "renderer", "task_contract",
                         "manifest_schema", "preflight_contract", "gate_set"}:
        problems.append(f"manifest versions() keys moved: {sorted(versions)}")
    for leaked in ("episode_contract", "episode_contract_digest"):
        if leaked in versions:
            problems.append(f"the release manifest binds {leaked} again; it cannot preflight a ceiling "
                            "it does not choose")
    if EPISODE_CONTRACT_DIGEST in {str(v) for v in versions.values()}:
        problems.append("the episode digest reached the manifest under another key")
    return check("the episode contract digest is pinned, equals the framework's own tool schemas and the "
                 "live stop order, is carried by every rollout and every batch — and is NOT in the "
                 "release manifest's versions(), which binds world semantics only",
                 not problems, "\n".join(problems))


def test_the_bound_transition_table_is_walked_through_the_real_tools():
    """A digest over a table nobody walks binds whatever the table says.

    The first version of `PHASE_TRANSITIONS` had `write_ledger:refused` going
    to ACTIVE_REJECTED from every phase, and the only test on it checked that
    the phase NAMES existed — so the digest cryptographically bound a wrong
    table. It is wrong because a write has three outcomes, not two: content
    that is not text or is over `MAX_WRITE_BYTES` is never STORED, answers
    with its own refusal, and leaves the phase exactly where it was.

    Every row is now driven through the real tools and `env_response`: reach
    the `from` phase, fire the event, assert the `to` phase.
    """
    P = env_mod.EpisodePhase
    problems = []
    oversize = "x" * (env_mod.MAX_WRITE_BYTES + 1)

    def reach(phase):
        """A rollout sitting in `phase`, built only from real tool calls."""
        env, state, workspace = fresh()
        if phase == "ACTIVE_CANDIDATE":
            drive(env, state, ("wc", "write_ledger", {"content": GOLDEN}))
        elif phase == "ACTIVE_REJECTED":
            drive(env, state, ("wr", "write_ledger", {"content": HOSTILE}))
        elif phase == "TERMINAL":
            drive(env, state, ("wc", "write_ledger", {"content": GOLDEN}))
            drive(env, state, ("st", "submit", {}))
        return env, state, workspace

    EVENTS = {
        "write_ledger:stored,boundary accepted": ("w", "write_ledger", {"content": GOLDEN}),
        "write_ledger:stored,boundary refused": ("w", "write_ledger", {"content": HOSTILE}),
        "write_ledger:not stored": ("w", "write_ledger", {"content": oversize}),
        "submit": ("s", "submit", {}),
        "any call, later turn": ("r", "read_file", {"path": env_mod.LEDGER}),
        "any call, same list after submit": None,        # covered by its own witness above
    }
    phases = {p.value for p in P}
    for source, event, target, _reply in env_mod.PHASE_TRANSITIONS:
        if source not in phases or target not in phases:
            problems.append(f"the table names a phase that does not exist: {source} -> {target}")
            continue
        spec = EVENTS.get(event)
        if spec is None:
            if event not in EVENTS:
                problems.append(f"the table names an event this walk cannot fire: {event!r}")
            continue
        env, state, _workspace = reach(source)
        if env_mod.episode_phase(state).value != source:
            problems.append(f"could not reach {source}: at {env_mod.episode_phase(state)}")
            continue
        drive(env, state, spec)
        got = env_mod.episode_phase(state).value
        if got != target:
            problems.append(f"{source} --{event}--> {got}, the table says {target}")

    # and the reply column for the one row the old table got wrong
    env, state, workspace = reach("ACTIVE_CANDIDATE")
    before = (workspace / env_mod.LEDGER).read_bytes()
    out = drive(env, state, ("w", "write_ledger", {"content": oversize}))
    if replies(out) != [env_mod.WRITE_TOO_LARGE]:
        problems.append(f"an over-cap write: {replies(out)}")

    # THE WRITE CAP IS THE OBSERVATION ENVELOPE. `read_file` returns the
    # ledger whole every later turn, so an oversized write buys unbounded
    # INPUT for one completion token a turn — a cost the output ceiling does
    # not price. Capping the write at the same envelope the mounted world must
    # fit closes it at the only place a tool argument can be refused publicly.
    if env_mod.MAX_WRITE_BYTES != env_mod.LEDGER_ENVELOPE_BYTES:
        problems.append(f"the write cap {env_mod.MAX_WRITE_BYTES} is not the observation envelope "
                        f"{env_mod.LEDGER_ENVELOPE_BYTES}")
    if str(env_mod.MAX_WRITE_BYTES) not in env_mod.WRITE_TOO_LARGE:
        problems.append(f"the refusal does not name the envelope: {env_mod.WRITE_TOO_LARGE!r}")
    if (workspace / env_mod.LEDGER).read_bytes() != before:
        problems.append("an over-envelope write reached the disk")
    if env_mod.evaluator_failure(state) is not None:
        problems.append("an over-envelope write became an evaluator failure rather than a refusal")
    # a corrected ledger still fits comfortably: the golden one plus room
    if len(GOLDEN.encode("utf-8")) > env_mod.MAX_WRITE_BYTES // 2:
        problems.append(f"the golden ledger ({len(GOLDEN.encode('utf-8'))} bytes) leaves no headroom "
                        f"under a {env_mod.MAX_WRITE_BYTES}-byte write cap")
    ok = drive(env, state, ("w2", "write_ledger", {"content": GOLDEN}))
    if env_mod.parse_attestation(str(replies(ok)[0])) is None:
        problems.append("a normal corrected ledger was refused by the new write cap")
    return check("every row of PHASE_TRANSITIONS is walked through the real tools: an unstored write "
                 "(not text, over the cap) leaves the phase alone, only a stored one moves it",
                 not problems, "\n".join(problems))


def test_the_prompt_and_the_digest_follow_the_ceiling_actually_served():
    """A disclosed budget must be the budget in force.

    The ceiling is NOT a constant: `load_environment(max_episode_output_tokens=…)`
    and `set_max_total_completion_tokens` both change it, and
    `tests/measure_budget.py` calls the setter for each arm. A prompt built
    from `MAX_EPISODE_OUTPUT_TOKENS` would tell an 8,000-token arm it had
    40,000 — false in exactly the runs the disclosure was added for. And the
    contract digest must part company with it, or two batches differing in
    the only budget a caller can change would claim to be one condition.

    `Environment.__init__` prepends the system message to every dataset row,
    so the row itself is checked, not just `env.system_prompt`.
    """
    problems = []
    default = load_environment()
    small = load_environment(max_episode_output_tokens=8_000)

    def row_prompt(env):
        return env.dataset[0]["prompt"][0]["content"]

    for label, env, needle, absent in (
        ("default", default, "ceiling of 40,000 completion tokens", "8,000 completion tokens"),
        ("8K", small, "ceiling of 8,000 completion tokens", "40,000 completion tokens"),
    ):
        if needle not in env.system_prompt:
            problems.append(f"{label}: env.system_prompt does not state {needle!r}")
        if needle not in row_prompt(env):
            problems.append(f"{label}: the dataset row the model is sent does not state {needle!r}")
        if absent in row_prompt(env):
            problems.append(f"{label}: the prompt still states {absent!r}")
    if default.episode_contract_digest() == small.episode_contract_digest():
        problems.append("two ceilings share one contract digest")
    if default.episode_contract_digest() != EPISODE_CONTRACT_DIGEST:
        problems.append("the default env's digest is not the pinned one")

    # the setter path, which is how the measurement arms set it
    later = load_environment()
    before = later.episode_contract_digest()
    later.set_max_total_completion_tokens(8_000)
    if "8,000 completion tokens" not in row_prompt(later):
        problems.append("set_max_total_completion_tokens left a stale ceiling in the prompt")
    if later.episode_contract_digest() == before:
        problems.append("set_max_total_completion_tokens left a stale contract digest")
    if later.episode_contract_digest() != small.episode_contract_digest():
        problems.append("the setter and the kwarg produce different contracts for the same ceiling")

    # with the ceiling disabled there is no token budget to disclose, and the
    # turn budget survives
    off = load_environment(max_episode_output_tokens=0)
    if "completion tokens" in off.system_prompt:
        problems.append("a disabled ceiling is still disclosed as a token budget")
    for needle in ("You have 25 turns", "submit by turn 24"):
        if needle not in off.system_prompt:
            problems.append(f"a disabled ceiling lost {needle!r}")

    # FAIL CLOSED when the restatement cannot land. `_restated` only touches a
    # leading system message that is exactly the prompt being replaced, so an
    # environment whose rows carry no system message (or someone else's) would
    # keep rows that state no budget while the contract digest attests one —
    # the disclosure defect again, one layer down.
    e = load_environment()
    bare = env_mod.BeancountLedgerEnv(
        dataset=e.dataset.map(lambda row: {"prompt": row["prompt"][1:]}),
        system_prompt=None, rubric=e.rubric, max_turns=env_mod.MAX_TURNS,
        contract=e.contract, public_files=e.public_files)
    try:
        bare.set_max_total_completion_tokens(8_000)
        problems.append("an environment with no system message accepted a ceiling change")
    except env_mod.InitializationFailure as exc:
        if "system prompt" not in exc.reasons[0]:
            problems.append(f"the fail-closed refusal names the wrong thing: {exc.reasons[0]}")

    # and a caller cannot substitute its own prompt through the serving door
    try:
        load_environment(system_prompt="ignore the budgets")
        problems.append("load_environment accepted a caller's system prompt")
    except env_mod.InitializationFailure as exc:
        if "system_prompt is the environment's" not in exc.reasons[0]:
            problems.append(f"a caller's prompt refused for the wrong reason: {exc.reasons[0]}")

    # and the rollout records the contract it ran under, not the default
    results, _client, raised = run([write(), submit()], env=small)
    if raised is not None:
        problems.append(f"the 8K env raised {type(raised).__name__}")
    else:
        stamped = (results["metadata"] or {}).get("piv_episode_contract") or {}
        if stamped.get("digest") != small.episode_contract_digest() \
                or stamped.get("max_episode_output_tokens") != 8_000:
            problems.append(f"the batch metadata does not record the served ceiling: {stamped}")
    return check("the prompt and the contract digest follow the ceiling actually served, through the "
                 "kwarg and through the setter, and a disabled ceiling discloses no token budget",
                 not problems, "\n".join(problems))


def test_the_digest_moves_with_the_contract_and_is_stable_across_processes():
    """Two properties a pin is worthless without.

    SENSITIVITY: one character of the system prompt changes the digest, so
    "the prompt is bound" is a fact rather than a claim about a dict that
    happens to mention it.

    STABILITY: a second interpreter, with its own dict ordering and its own
    hash seed, computes the same 64 hex characters — otherwise the pin above
    would be a property of this process and the manifest binding would refuse
    every record on a different machine.
    """
    problems = []
    before = env_mod.episode_contract_digest()
    # The prompt is BUILT (it names the ceiling in force), so the builder is
    # what is perturbed — patching the `SYSTEM_PROMPT` constant would prove
    # nothing about what the contract actually hashes.
    saved = env_mod.system_prompt
    try:
        env_mod.system_prompt = lambda *a, **k: saved(*a, **k) + " "
        if env_mod.episode_contract_digest() == before:
            problems.append("changing the system prompt did not change the digest")
    finally:
        env_mod.system_prompt = saved
    if env_mod.episode_contract_digest() != before:
        problems.append("the digest did not come back after the prompt was restored")

    import subprocess
    code = ("import sys; sys.path.insert(0, %r);"
            "from beancount_ledger import beancount_ledger as e;"
            "print(e.episode_contract_digest())" % str(ROOT))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONHASHSEED": "1"})
    if proc.returncode != 0 or proc.stdout.strip() != before:
        problems.append(f"a second process computed {proc.stdout.strip()!r} (rc {proc.returncode}) "
                        f"{proc.stderr.strip()[-300:]}")
    return check("the digest moves when the prompt does and is identical in a second process",
                 not problems, "\n".join(problems))


def test_the_prompt_discloses_the_terminal_budgets():
    """A budget the agent cannot see is one it cannot act on.

    The prompt already stated the turn cap. It said nothing about the 40,000
    completion-token ceiling or about the three-consecutive-no-tool-turns
    ending, both of which can end an episode well before turn 25 — so a model
    reasoning at length was being ended by rules it had not been told. The
    numbers are DERIVED from the constants, so a changed constant cannot leave
    a stale number in the prompt.
    """
    problems = []
    prompt = env_mod.SYSTEM_PROMPT
    required = (
        f"total ceiling of {env_mod.MAX_EPISODE_OUTPUT_TOKENS:,} completion tokens",
        "including hidden reasoning",
        "You will not receive an exact remaining-token counter",
        "keep responses concise and use tools early",
        "Tool calls emitted on the turn that exhausts this token ceiling are executed",
        f"calls emitted on turn {env_mod.MAX_TURNS} are not",
        # THE DELIVERY RULE. "submit by turn 24" alone
        # reads as a precondition for delivery, and it is not one: every
        # non-protocol ending scores the last committed revision. The agent
        # and the results table have to describe the same contract, so the
        # prompt says both halves.
        f"Call submit by turn {env_mod.MAX_TURNS - 1} to finish early",
        "If the episode limit is reached first, the latest successfully written ledger is scored",
        f"{env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS} consecutive turns without a tool call",
        "unbroken run of turns cut off at the completion cap",
        f"You have {env_mod.MAX_TURNS} turns",
        "returns the complete ledger exactly as the scorer sees it",
        "line endings are normalized to LF",
    )
    for needle in required:
        if needle not in prompt:
            problems.append(f"the prompt does not say {needle!r}")
    if "exactly as stored" in prompt:
        problems.append("the prompt still claims the ledger comes back exactly as stored")
    # derived, not typed: the constants are the source
    for value in (str(env_mod.MAX_TURNS), f"{env_mod.MAX_EPISODE_OUTPUT_TOKENS:,}",
                  str(env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS)):
        if value not in prompt:
            problems.append(f"the prompt lost the constant {value}")
    return check("the system prompt states the output ceiling, the pending-call rule, the executed-turn "
                 "budget and the no-tool limit, all derived from the constants",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3f. terminality cuts off the same-turn suffix
# --------------------------------------------------------------------------

def test_an_accepted_submit_cuts_off_the_rest_of_its_own_call_list():
    """`submit -> read_file` must not read.

    `submit` set TERMINAL and `write_ledger` checked the phase, but
    `read_file`, `grep`, `list_files` and `run_beancount` did not — so the
    suffix of submit's OWN call list executed against a workspace the contract
    calls frozen ("Nothing is read or changed afterwards"). `_frozen_turn`
    protected later turns, not this.

    The rule, witnessed through the real `env_response` door: calls run in
    order until an accepted submit; every later occurrence gets one bounded
    `TURN_AFTER_SUBMIT` and no tool body runs — a repeated `submit` included,
    because a second receipt would assert an acceptance that did not happen.
    A read BEFORE the submit in the same list still executes, which is what
    makes the refusal about terminality rather than about the tool.
    """
    problems = []
    golden_on_disk = hashlib.sha256(GOLDEN.encode("utf-8")).hexdigest()

    # the reviewer's headline shape, all three calls in ONE list: the write
    # commits, the submit is accepted, and the read does not happen
    env, state, workspace = fresh()
    out = drive(env, state,
                ("w1", "write_ledger", {"content": GOLDEN}),
                ("s1", "submit", {}),
                ("r1", "read_file", {"path": env_mod.LEDGER}))
    contents = [str(c) for c in replies(out)]
    if len(contents) != 3:
        problems.append(f"write -> submit -> read_file gave {len(contents)} replies: {contents}")
    else:
        if env_mod.parse_attestation(contents[0]) is None:
            problems.append(f"the write before submit did not commit: {contents[0][:80]!r}")
        if not contents[1].startswith(env_mod.SUBMIT_ACCEPTED):
            problems.append(f"submit was not accepted: {contents[1][:80]!r}")
        if contents[2] != env_mod.TURN_AFTER_SUBMIT:
            problems.append(f"the read after submit executed: {contents[2][:120]!r}")
    if hashlib.sha256((workspace / env_mod.LEDGER).read_bytes()).hexdigest() != golden_on_disk:
        problems.append("the workspace digest moved on the submit turn")

    # every tool, one at a time. The write is its own earlier turn, because
    # two writes in one list is a REJECTED turn (nothing executes at all) and
    # that pre-turn rule must keep running before any of this.
    suffixes = (
        ("read_file", ("r2", "read_file", {"path": env_mod.LEDGER})),
        ("run_beancount", ("b2", "run_beancount", {})),
        ("grep", ("g2", "grep", {"pattern": "Assets"})),
        ("list_files", ("l2", "list_files", {})),
        ("submit", ("s2", "submit", {})),
        ("write_ledger", ("w2", "write_ledger", {"content": HOSTILE})),
    )
    for label, suffix in suffixes:
        env, state, workspace = fresh()
        ledger = workspace / env_mod.LEDGER
        drive(env, state, ("w1", "write_ledger", {"content": GOLDEN}))
        revision = state.get("piv_revision")
        out = drive(env, state, ("s1", "submit", {}), suffix)
        contents = [str(c) for c in replies(out)]
        if len(contents) != 2:
            problems.append(f"{label}: {len(contents)} replies for 2 calls: {contents}")
            continue
        if not contents[0].startswith(env_mod.SUBMIT_ACCEPTED):
            problems.append(f"{label}: submit was not accepted: {contents[0][:80]!r}")
        if contents[1] != env_mod.TURN_AFTER_SUBMIT:
            problems.append(f"{label}: the suffix executed: {contents[1][:120]!r}")
        if hashlib.sha256(ledger.read_bytes()).hexdigest() != golden_on_disk:
            problems.append(f"{label}: the workspace digest moved after submit")
        if state.get("piv_revision") != revision:
            problems.append(f"{label}: the revision moved after submit: {state.get('piv_revision')}")
        if env_mod.episode_phase(state) is not env_mod.EpisodePhase.TERMINAL:
            problems.append(f"{label}: phase {env_mod.episode_phase(state)}")
        if env_mod.evaluator_failure(state) is not None:
            problems.append(f"{label}: a refused suffix call quarantined the rollout")
        if state.get("piv_calls_refused_after_submit") != 1:
            problems.append(f"{label}: refusal not counted: {state.get('piv_calls_refused_after_submit')}")

    # the control: the same read BEFORE the submit executes normally
    env, state, workspace = fresh()
    out = drive(env, state,
                ("w1", "write_ledger", {"content": GOLDEN}),
                ("r1", "read_file", {"path": env_mod.LEDGER}),
                ("s1", "submit", {}))
    contents = [str(c) for c in replies(out)]
    if len(contents) != 3 or contents[1] != GOLDEN:
        problems.append(f"a read before the submit did not execute: {contents[1][:80]!r}")
    if not contents[2].startswith(env_mod.SUBMIT_ACCEPTED):
        problems.append(f"the submit after the read was not accepted: {contents[2][:80]!r}")

    # ...and a whole LATER turn on that same rollout is still refused as it
    # always was, one reply per id
    out = drive(env, state, ("x1", "read_file", {"path": env_mod.LEDGER}), ("x2", "grep", {"pattern": "a"}))
    if [str(c) for c in replies(out)] != [env_mod.TURN_AFTER_SUBMIT, env_mod.TURN_AFTER_SUBMIT]:
        problems.append(f"a later post-submit turn: {replies(out)}")

    # and the pre-turn rules still run before any side effect: two writes with
    # a submit between them is a rejected TURN, not a partial execution
    env, state, workspace = fresh()
    drive(env, state, ("w0", "write_ledger", {"content": GOLDEN}))
    out = drive(env, state, ("wa", "write_ledger", {"content": HOSTILE}),
                ("s", "submit", {}), ("wb", "write_ledger", {"content": HOSTILE}))
    if [str(c) for c in replies(out)] != [env_mod.TURN_MULTI_WRITE] * 3:
        problems.append(f"two writes around a submit was not refused whole: {replies(out)}")
    if env_mod.episode_phase(state) is not env_mod.EpisodePhase.CANDIDATE:
        problems.append(f"a rejected turn moved the phase to {env_mod.episode_phase(state)}")
    return check("an accepted submit refuses every later call in its OWN list (read_file, run_beancount, "
                 "grep, list_files, a repeated submit, a write) with TURN_AFTER_SUBMIT and no tool body; "
                 "a call before the submit still runs", not problems, "\n".join(problems))


def test_the_tool_surface_is_six_tools_one_write_one_terminal():
    """The pin the severity claim rests on, updated for the sixth tool."""
    env = load_environment()
    problems = []
    expected = {"list_files", "read_file", "grep", "run_beancount", "write_ledger", "submit"}
    if set(env.tool_map) != expected:
        problems.append(f"tool surface: {sorted(env.tool_map)}")
    if len(env.tool_defs) != 6:
        problems.append(f"{len(env.tool_defs)} tool definitions advertised")
    if env_mod.WRITE_TOOL != "write_ledger" or env_mod.TERMINAL_TOOL != "submit":
        problems.append(f"names moved: write={env_mod.WRITE_TOOL} terminal={env_mod.TERMINAL_TOOL}")
    if env_mod.MUTABLE_PUBLIC_FILE != env_mod.LEDGER:
        problems.append("the single mutable file moved")
    # the terminal tool mutates nothing and reads nothing
    import inspect
    body = inspect.getsource(env_mod.submit)
    for needle in ("open(", "write", "_read_public", "mkstemp", "replace("):
        if needle in body.split('"""')[-1]:
            problems.append(f"submit's body touches {needle}")
    definition = next(d for d in env.tool_defs if d.name == "submit")
    if definition.parameters.get("properties"):
        problems.append(f"submit takes agent-visible arguments: {definition.parameters}")
    if "final" not in (definition.description or ""):
        problems.append(f"submit's docstring does not state the contract: {definition.description!r}")
    if "submit" not in env_mod.SYSTEM_PROMPT or "as last written is final" not in env_mod.SYSTEM_PROMPT:
        problems.append("SYSTEM_PROMPT does not state how the episode ends")
    return check("six tools, one fixed write name, one fixed terminal name; submit takes no arguments, "
                 "touches no file, and is documented in the prompt and its docstring",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 4. the tool-call payload is part of the plausibility floor
# --------------------------------------------------------------------------

def write_of_exactly(chars: int, tag: str = "w1") -> ResponseMessage:
    """A `write_ledger` turn whose COUNTED tool-call payload is `chars`.

    The counted quantity is `tool_call_chars`: name + id + arguments, no
    wrapper. The content is solved for rather than guessed, so the witnesses
    below sit exactly on the floor instead of near it.
    """
    overhead = len(tag) + len("write_ledger") + len(json.dumps({"content": ""}))
    body = "x" * (chars - overhead)
    message = calls((tag, "write_ledger", {"content": body}))
    assert env_mod.tool_call_chars(message) == chars, env_mod.tool_call_chars(message)
    return message


def test_tool_call_arguments_are_counted_in_the_plausibility_floor():
    """A tool-only turn used to have a denominator of zero.

    `_response_chars` counted visible content and reasoning content, and the
    docstring called the omission "lenient". It was not: the LARGEST
    completion payload this task can produce is a `write_ledger` argument, up
    to MAX_WRITE_BYTES, and a turn carrying 48,000 characters of it with no
    prose at all had `chars == 0`, so `completion_tokens=1` passed the floor
    trivially. The one turn where under-reporting pays
    was the one turn the check could not see.

    Two witnesses at exactly 48,000 counted characters — the write envelope:

        completion_tokens=1       -> usage_implausible (8 << 48,000)
        completion_tokens=6,000   -> nothing (6,000 x 8 == 48,000, the floor)

    and the regression itself: content+reasoning alone would be 0 for both.

    The count is CONSERVATIVE on purpose. Only name, id and arguments are
    counted — no JSON wrapper, no separators, no quoting — because every
    provider frames tool calls differently and this number is the denominator
    of an accusation. Whatever the wire adds, the real payload is larger than
    what is counted here, never smaller.
    """
    problems = []
    payload = 48_000
    turn = write_of_exactly(payload)
    if env_mod.tool_call_chars(turn) != payload:
        problems.append(f"tool_call_chars {env_mod.tool_call_chars(turn)}, expected {payload}")
    response = Response.model_construct(id="x", created=0, model="m", usage=None, message=turn)
    if env_mod._response_chars(response) != payload:
        problems.append(f"_response_chars {env_mod._response_chars(response)} does not include the "
                        f"tool-call payload ({payload})")
    # the shape of the old defect: no visible content and no reasoning at all
    if (turn.content or "").strip() or getattr(turn, "reasoning_content", None):
        problems.append("the witness turn is not tool-only, so it does not witness the old hole")
    # ...and a turn with no tool calls is unaffected
    if env_mod.tool_call_chars(narrated("hello")) != 0:
        problems.append("a turn with no tool calls counted a payload")

    for label, tokens, expected in (("1 token", 1, env_mod.BUDGET_USAGE_IMPLAUSIBLE),
                                    (f"{payload // env_mod.CHARS_PER_TOKEN_FLOOR} tokens",
                                     payload // env_mod.CHARS_PER_TOKEN_FLOOR, None)):
        state = {}
        env = load_environment()
        usage = Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=tokens,
                      total_tokens=10 + tokens)
        env._check_budget_accounting(
            state, Response.model_construct(id="x", created=0, model="m", usage=usage, message=turn),
            None, 0)
        if state.get("piv_budget_accounting_suspicious") != expected:
            problems.append(f"{label}: suspicious {state.get('piv_budget_accounting_suspicious')!r}, "
                            f"expected {expected!r}")
        if state.get("piv_budget_accounting_invalid") is not None:
            problems.append(f"{label}: the heuristic invalidated the row: "
                            f"{state.get('piv_budget_accounting_invalid')!r}")
    # through the real loop, end to end: the 48,000-character write at one
    # reported token is flagged, and the reward is untouched
    env = load_environment()
    client = BadUsageScript([write_of_exactly(payload, "w9"), write(), submit()],
                            [Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=1, total_tokens=11),
                             Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=9_000, total_tokens=9_010)])
    results = asyncio.run(env.evaluate(
        client=client, model="scripted", num_examples=1, rollouts_per_example=1, max_concurrent=1,
        save_results=False, sampling_args={"max_tokens": 40_000},
        state_columns=["piv_budget_accounting_suspicious"]))
    if one(results).get("piv_budget_accounting_suspicious") != env_mod.BUDGET_USAGE_IMPLAUSIBLE:
        problems.append("through the real loop, a 48,000-character write at one token was not flagged: "
                        f"{one(results).get('piv_budget_accounting_suspicious')!r}")
    return check("the canonical tool-call payload (name, id, arguments — no wrapper) is in the "
                 "plausibility denominator: a 48,000-character write at 1 token is flagged, the same "
                 "write at 6,000 tokens is not, and a tool-only turn is no longer free",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 5. every model-facing reply is a bound constant
# --------------------------------------------------------------------------

#: The functions that talk to the model, and every string literal each one is
#: allowed to carry. A literal outside this set is a reply the digest cannot
#: see — the reviewer's exact seam — so adding one FAILS until it is hoisted
#: into a constant in `model_facing_messages()`. Every entry here is either a
#: structural separator or a non-model-facing key/encoding, and is justified.
MODEL_FACING_FUNCTIONS = ("_clip", "_clip_bytes", "list_files", "read_file", "_whole_ledger_reply",
                          "grep", "_public_report", "run_beancount", "write_ledger", "submit",
                          "submit_receipt")
#: The environment METHODS that also emit model-facing text. They were left
#: out of the first version of this scan, and that was a hole with the same
#: shape as the one the hoist closed: a reply written inline in
#: `_no_tool_call_turn` or `_frozen_turn` would not be in the digest and
#: nothing would say so.
MODEL_FACING_METHODS = ("call_tool", "_answer_turn", "_frozen_turn", "_no_tool_call_turn")
ALLOWED_LITERALS = {
    "",                       # empty tail / empty accumulator
    "\n",                     # the join between lines of one reply
    "utf-8", "strict", "wb",  # encodings and file modes, never text the model reads
    "ignore", "replace",      # codec error policies
    ".ledger-", ".tmp",       # the temporary file's name parts, never sent
    "content",                # write_ledger's own argument name and the message field
    "digests", "outcome",     # the keys of `piv_pending`, internal state
    "tool", "user",           # protocol ROLES on a message, not text
    "id", "name", "arguments", "tool_calls", "tool_call_id",  # framework attribute names
    "{}", "piv_",             # an empty JSON object and a state-key prefix
    "piv_rollout_id",
    # the write attestation's JSON keys — machine-readable, and already bound
    # by WRITE_ATTESTATION_SCHEMA and DIGEST_PROFILES in the contract view
    "schema", "profiles", "committed",
    # rollout state keys, never text
    "piv_pending", "piv_phase", "piv_candidate_digest", "piv_submitted_digest",
    "piv_submit_refused", "piv_revision", "piv_turn", "piv_ledger_sent", "piv_ledger_receipts",
    "piv_complete_reads", "piv_observation_bytes", "piv_observation_refused",
    "piv_calls_refused_after_submit", "piv_turns_rejected", "piv_no_tool_turns",
    "piv_consecutive_no_tool_turns", "piv_consecutive_truncated_turns",
    "piv_no_tool_truncated_turns", "piv_truncation_limit_reached", "piv_no_tool_limit_reached",
    "piv_protocol_failure", "piv_committed", "piv_delivery", "piv_score", "piv_result",
    "final_env_response", "workspace",
    "digest", "turn", "revision", "?", "logical_text_digest",
}


def _literals_of(function) -> set:
    """Every string literal in `function`'s body except its docstring and
    anything under a `raise` — raised text reaches the marker, never the
    model (`error_formatter` answers with PUBLIC_TOOL_ERROR)."""
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    body = tree.body[0]
    raised = set()
    docstrings = set()
    for node in ast.walk(body):
        if isinstance(node, ast.Raise):
            raised.update(id(n) for n in ast.walk(node))
        # EVERY docstring, nested helpers included — `clean=True` dedents and
        # would never match the raw literal, and a nested `def` inside a tool
        # has a docstring of its own that is not model-facing either.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            text = ast.get_docstring(node, clean=False)
            if text is not None:
                docstrings.add(text)
    found = set()
    for node in ast.walk(body):
        if id(node) in raised:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in docstrings:
                continue
            found.add(node.value)
        elif isinstance(node, ast.JoinedStr):
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str) and part.value:
                    found.add(part.value)
    return found


def test_every_model_facing_reply_is_a_bound_constant():
    """The digest binds what the model is told, or it binds a subset and says so.

    `episode_contract_digest()` used to bind the fixed refusals and nudges
    only, and its own docstring listed what it missed: the strings `read_file`,
    `grep` and `_public_report` BUILT — "no such file", the numbered slice, the
    continuation tail, the hit line, the stopped-at-N tail, the parse headings.
    Those change the next model request exactly as much as a refusal does, and
    the remedy on offer was "remember to bump the integer". The reviewer called
    that the same generous seam earlier rounds kept exploiting.

    Two halves, both checked, because either alone is defeatable:

      1. every constant in `model_facing_messages()` is IN the canonical view,
         and mutating any one of them MOVES the digest — so the contract
         cannot silently stop covering one;
      2. the source of every model-facing function carries NO string literal
         of its own beyond an enumerated structural set — so a new reply
         cannot be written inline and skip the view.
    """
    import ast
    import inspect

    problems = []
    view = env_mod.episode_contract()
    messages = view.get("messages") or {}
    named = dict(env_mod.model_facing_messages())
    if set(messages) != set(named):
        problems.append(f"the view's messages are not model_facing_messages(): "
                        f"{sorted(set(messages) ^ set(named))}")
    for name, value in named.items():
        if messages.get(name) != value:
            problems.append(f"{name} in the view is not the constant: {messages.get(name)!r}")

    # 1. mutating ANY of them moves the digest — one at a time, restored after
    baseline = env_mod.episode_contract_digest()
    for name in named:
        original = getattr(env_mod, name)
        try:
            setattr(env_mod, name, original + " ")
            if env_mod.episode_contract_digest() == baseline:
                problems.append(f"changing {name} does not move the episode contract digest")
        finally:
            setattr(env_mod, name, original)
    if env_mod.episode_contract_digest() != baseline:
        problems.append("the digest did not come back after the mutations")

    # ...and the SCAN ITSELF is not vacuous: a function that inlines a reply
    # must be caught (as an f-string part, which is how one would be written),
    # while a docstring and a `raise` must not be. Without this, an
    # `_literals_of` that returned nothing would pass the loop below forever.
    def _inlined(path):
        """A docstring that must be ignored."""
        if path is None:
            raise RuntimeError("evaluator text that must be ignored")
        return f"no such file: {path}"

    if not (_literals_of(_inlined) - ALLOWED_LITERALS):
        problems.append("the literal scan does not catch an inlined model-facing reply")
    if {"A docstring that must be ignored.", "evaluator text that must be ignored"} \
            & _literals_of(_inlined):
        problems.append("the literal scan flags a docstring or raised text")

    # 2. no model-facing function or METHOD writes a reply inline
    for name in MODEL_FACING_FUNCTIONS:
        function = getattr(env_mod, name)
        stray = {lit for lit in _literals_of(function) if lit not in ALLOWED_LITERALS}
        if stray:
            problems.append(f"{name} carries model-facing literal(s) outside the constants: "
                            f"{sorted(stray)!r}")
    for name in MODEL_FACING_METHODS:
        method = getattr(env_mod.BeancountLedgerEnv, name)
        stray = {lit for lit in _literals_of(method) if lit not in ALLOWED_LITERALS}
        if stray:
            problems.append(f"BeancountLedgerEnv.{name} carries model-facing literal(s) outside the "
                            f"constants: {sorted(stray)!r}")

    # ...and every constant is actually USED somewhere OTHER than its own
    # assignment and the `model_facing_messages()` listing. A plain
    # `ast.Name` walk cannot see that: it collects Store targets too, so the
    # assignment alone satisfied it and this half could never fail — the same
    # "checked in name only" shape the hoist was fixing.
    source = inspect.getsource(env_mod)
    tree = ast.parse(source)
    listing = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                    and n.name == "model_facing_messages"), None)
    if listing is None:
        problems.append("model_facing_messages() is gone; the contract view has no single list")
    inside_listing = {id(n) for n in ast.walk(listing)} if listing is not None else set()
    used = {n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in inside_listing}
    for name in named:
        if name not in used:
            problems.append(f"{name} is in the contract view but no code outside the listing uses it")
    # the check itself is not vacuous: a name that exists only as an
    # assignment plus the listing must be reported
    probe = ast.parse("DEAD_TEMPLATE = 'x'\ndef model_facing_messages():\n"
                      "    return (('DEAD_TEMPLATE', DEAD_TEMPLATE),)\n")
    probe_listing = next(n for n in ast.walk(probe) if isinstance(n, ast.FunctionDef))
    probe_inside = {id(n) for n in ast.walk(probe_listing)}
    probe_used = {n.id for n in ast.walk(probe) if isinstance(n, ast.Name)
                  and isinstance(n.ctx, ast.Load) and id(n) not in probe_inside}
    if "DEAD_TEMPLATE" in probe_used:
        problems.append("the 'constant is used' check still passes for a template nothing formats")

    # the new templates specifically: each must be reachable text, not prose
    for name in ("READ_NO_SUCH_FILE", "READ_SLICE_LINE", "READ_MORE_LINES", "CLIP_MORE_LINES",
                 "GREP_BAD_PATTERN", "GREP_HIT", "GREP_STOPPED", "GREP_NO_MATCHES",
                 "REPORT_REJECTED", "REPORT_LOADS_CLEANLY", "REPORT_FINDINGS_HEADER", "REPORT_FINDING",
                 "LIST_FILES_ROW", "SUBMIT_DELIVERING", "LEDGER_UNCHANGED_RECEIPT",
                 "READ_OVER_ENVELOPE"):
        if name not in named:
            problems.append(f"{name} is not in model_facing_messages()")
    return check("every model-facing reply is a named constant, every constant is in the canonical "
                 "contract view (mutating one moves the digest), and no model-facing function carries a "
                 "reply literal of its own", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 6. the ledger is sent once per revision
# --------------------------------------------------------------------------

def test_the_ledger_is_sent_once_per_revision():
    """The envelope bounds one observation; it did not bound repetition.

    `MAX_WRITE_BYTES = LEDGER_ENVELOPE_BYTES` closes single-read amplification,
    but one assistant turn may carry many `read_file(ledger)` calls, and each
    one used to put another 48 KB into the next request for the same handful
    of completion tokens — input the episode's output ceiling does not price.

    The rule is idempotence per REVISION: the first complete read of a logical
    text returns it, a later complete read of the SAME logical text returns
    LEDGER_UNCHANGED_RECEIPT and no content, and an accepted write that
    changes the text makes the next complete read return the new content once.
    Everything below goes through the real tool door, because that is where
    the ordering inside one call list is decided.

    The bound this buys, and what is asserted here:

        ledger content per episode <= LEDGER_ENVELOPE_BYTES x (revisions + 1)
    """
    problems = []
    env, state, workspace = fresh()
    original = env_mod.logical_text(env.public_files[env_mod.LEDGER])

    # read -> content; read again -> receipt, and not one byte of the ledger
    first = replies(drive(env, state, ("r1", "read_file", {"path": env_mod.LEDGER})))[0]
    if first != original:
        problems.append("the first complete read is not the ledger's logical text")
    second = replies(drive(env, state, ("r2", "read_file", {"path": env_mod.LEDGER})))[0]
    if "unchanged since your complete read" not in second:
        problems.append(f"the second complete read is not a receipt: {second[:120]!r}")
    if original[:200] in second or len(second) > 300:
        problems.append(f"the receipt carries ledger content or is not bounded ({len(second)} chars)")
    if state.get("piv_complete_reads") != 1:
        problems.append(f"piv_complete_reads {state.get('piv_complete_reads')}, expected 1")

    # a write that CHANGES the text makes the next complete read content again
    drive(env, state, ("w1", "write_ledger", {"content": GOLDEN}))
    third = replies(drive(env, state, ("r3", "read_file", {"path": env_mod.LEDGER})))[0]
    if third != env_mod.logical_text(GOLDEN.encode("utf-8")):
        problems.append("after an accepted write the complete read did not return the new revision")
    fourth = replies(drive(env, state, ("r4", "read_file", {"path": env_mod.LEDGER})))[0]
    if "unchanged since your complete read" not in fourth:
        problems.append(f"the new revision was re-sent: {fourth[:120]!r}")
    if state.get("piv_complete_reads") != 2:
        problems.append(f"piv_complete_reads {state.get('piv_complete_reads')}, expected 2")

    # THREE READS IN ONE CALL LIST: content, receipt, receipt — the framework
    # runs a turn's calls in order and every one still gets its own reply
    env2, state2, _ = fresh()
    out = replies(drive(env2, state2,
                        ("a", "read_file", {"path": env_mod.LEDGER}),
                        ("b", "read_file", {"path": env_mod.LEDGER}),
                        ("c", "read_file", {"path": env_mod.LEDGER})))
    if len(out) != 3:
        problems.append(f"three calls got {len(out)} replies")
    elif out[0] != original or "unchanged" not in out[1] or "unchanged" not in out[2]:
        problems.append(f"in-list order is not content/receipt/receipt: "
                        f"{[len(o) for o in out]}")
    if state2.get("piv_complete_reads") != 1:
        problems.append(f"one call list returned {state2.get('piv_complete_reads')} ledger contents")

    # OTHER FILES ARE UNAFFECTED: the rule is about the whole-file read
    env3, state3, _ = fresh()
    slices = replies(drive(env3, state3,
                           ("p1", "read_file", {"path": "policy.md"}),
                           ("p2", "read_file", {"path": "policy.md"})))
    if len(slices) != 2 or slices[0] != slices[1] or not slices[0].startswith("    1  "):
        problems.append("a sliced read of another file was deduplicated or decorated")
    if state3.get("piv_complete_reads") != 0:
        problems.append("a sliced read counted as a complete ledger read")

    # THE REVISION THE RECEIPT NAMES is the one that was SENT, including in a
    # `write_ledger -> read_file` call list, where `piv_revision` has not
    # advanced yet when the read runs: naming the counter there would tell the
    # agent it had been given revision 0 when it had just been given 1.
    env4, state4, _ = fresh()
    same_list = replies(drive(env4, state4,
                              ("s1", "write_ledger", {"content": GOLDEN}),
                              ("s2", "read_file", {"path": env_mod.LEDGER})))
    if len(same_list) != 2 or same_list[1] != env_mod.logical_text(GOLDEN.encode("utf-8")):
        problems.append("a same-list write -> read did not return the new revision")
    if state4.get("piv_revision") != 1:
        problems.append(f"the same-list write did not commit: revision {state4.get('piv_revision')}")
    echo = replies(drive(env4, state4, ("s3", "read_file", {"path": env_mod.LEDGER})))[0]
    if echo != env_mod.LEDGER_UNCHANGED_RECEIPT.format(turn=1, revision=1):
        problems.append(f"the receipt after a same-list write names the wrong turn/revision: {echo!r}")

    # THE RECEIPT'S TEXT is the constant, formatted — turn and revision named
    if env_mod.LEDGER_UNCHANGED_RECEIPT.format(turn=1, revision=0) != second:
        problems.append(f"the receipt is not LEDGER_UNCHANGED_RECEIPT.format(turn=1, revision=0): "
                        f"{second!r}")
    for forbidden in (str(env_mod.MAX_TURNS), "workspace"):
        if forbidden in second and forbidden != "1":
            problems.append(f"the receipt leaks {forbidden!r}")

    # THE BOUND, measured. The claim is about COMPLETE READS: at most one
    # content-returning read per stored revision plus the mounted one. That is
    # the countable form of `LEDGER_ENVELOPE_BYTES x (revisions + 1)`, since
    # every complete read that returns content is bounded by the envelope.
    # (`grep` and sliced reads can also show ledger lines; they are bounded
    # per call by MAX_GREP_HITS / MAX_TOOL_OUTPUT_LINES / MAX_READ_LINES, and
    # the contract view says so rather than claiming they are in this bound.)
    revisions = state.get("piv_revision", 0)
    ledger_bound = env_mod.LEDGER_ENVELOPE_BYTES * (revisions + 1)
    if state.get("piv_complete_reads", 0) > revisions + 1:
        problems.append(f"{state.get('piv_complete_reads')} contents for {revisions} revision(s)")
    if state.get("piv_observation_bytes", 0) > ledger_bound:
        problems.append(f"this rollout's observation bytes {state.get('piv_observation_bytes')} "
                        f"exceed the complete-read bound {ledger_bound} it stays within")
    if not state.get("piv_observation_bytes"):
        problems.append("piv_observation_bytes was never counted")
    # ...and the rule survives a write that RESTORES an earlier text: the
    # digest is the identity, so writing the original back and reading gives
    # content once more (a new revision), never twice.
    drive(env, state, ("w2", "write_ledger", {"content": original}))
    back = replies(drive(env, state, ("r5", "read_file", {"path": env_mod.LEDGER})))[0]
    again = replies(drive(env, state, ("r6", "read_file", {"path": env_mod.LEDGER})))[0]
    if back != original or "unchanged" not in again:
        problems.append("a write that restores an earlier text did not give content exactly once")
    if state.get("piv_complete_reads", 0) > state.get("piv_revision", 0) + 1:
        problems.append(f"{state.get('piv_complete_reads')} contents for "
                        f"{state.get('piv_revision')} revision(s) after a restoring write")

    # ...and the whole thing survives the real evaluate door, with the metrics
    results, _client, raised = run([calls(("q1", "read_file", {"path": env_mod.LEDGER}),
                                          ("q2", "read_file", {"path": env_mod.LEDGER})),
                                    write(), submit()],
                                   state_columns=["piv_complete_reads", "piv_observation_bytes"])
    if raised is not None:
        problems.append(f"the repeated-read route raised {type(raised).__name__}: {raised}")
    else:
        out = one(results)
        metrics = out.get("metrics") or {}
        if out.get("reward") != 1.0:
            problems.append(f"the repeated-read route scored {out.get('reward')}")
        if out.get("piv_complete_reads") != 1:
            problems.append(f"two reads in one list returned {out.get('piv_complete_reads')} contents")
        if metrics.get(env_mod.METRIC_COMPLETE_READS) != 1.0:
            problems.append(f"{env_mod.METRIC_COMPLETE_READS} {metrics.get(env_mod.METRIC_COMPLETE_READS)}")
        if not metrics.get(env_mod.METRIC_OBSERVATION_BYTES):
            problems.append(f"{env_mod.METRIC_OBSERVATION_BYTES} is 0")
        if metrics.get(env_mod.METRIC_OBSERVATION_BYTES) != float(out.get("piv_observation_bytes")):
            problems.append("the metric and the state disagree on observation bytes")

    # the model is TOLD, in the prompt, out of the constants
    for needle in (f"{env_mod.LEDGER} is sent to you ONCE per revision",
                   "returns a short receipt instead of the file"):
        if needle not in env_mod.SYSTEM_PROMPT:
            problems.append(f"the prompt does not disclose the rule: {needle!r}")
    return check("the ledger is sent once per revision: read -> receipt; write -> content -> receipt; "
                 "three reads in one call list give content/receipt/receipt; other files unaffected; the "
                 "counters, the metrics and the envelope x (revisions + 1) bound hold",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 7. the envelope is UTF-8 bytes, at both doors
# --------------------------------------------------------------------------

def test_the_envelope_is_utf8_bytes_and_both_doors_enforce_it():
    """48,000 BYTES, not 48,000 characters, and refused on read as well.

    A Python character count would let 16,000 three-byte characters through as
    a 48,000-byte file, and the whole point of the number is what the next
    request pays for. `write_ledger` therefore measures `content.encode(
    "utf-8")`, and this pins the boundary exactly — at the limit and one byte
    past it — with a multibyte character straddling the limit.

    The read door refuses the same predicate INDEPENDENTLY. That is
    unreachable through anything the agent can write, which is the point: it
    is defence against state corruption, a migration or a future bypass
    restoring the amplification, and it returns a bounded public message
    rather than the content or an evaluator failure.

    A refused write is ATOMIC: the previous candidate, its digest and the
    bytes on disk are exactly what they were.
    """
    problems = []
    env, state, workspace = fresh()
    ledger = workspace / env_mod.LEDGER
    limit = env_mod.MAX_WRITE_BYTES
    if limit != env_mod.LEDGER_ENVELOPE_BYTES:
        problems.append(f"the write cap {limit} is not the observation envelope "
                        f"{env_mod.LEDGER_ENVELOPE_BYTES}")

    # a real candidate first, so "the previous candidate is unchanged" has
    # something to be about
    drive(env, state, ("w0", "write_ledger", {"content": GOLDEN}))
    before_digest = state.get("piv_candidate_digest")
    before_bytes = ledger.read_bytes()
    before_phase = phase(state)

    # EXACT BOUNDARY, in bytes, with a 3-byte character straddling the limit.
    # "€" is 3 bytes; a text of (limit - 3) ASCII characters plus one euro
    # sign is exactly `limit` bytes and 1 character SHORT of `limit`.
    at_limit = "; " + "a" * (limit - 3 - 2) + "€"
    over_limit = at_limit + "a"
    if len(at_limit.encode("utf-8")) != limit or len(at_limit) != limit - 2:
        problems.append(f"the boundary fixture is {len(at_limit.encode('utf-8'))} bytes / "
                        f"{len(at_limit)} characters, not {limit} / {limit - 2}")
    if len(over_limit.encode("utf-8")) != limit + 1:
        problems.append("the boundary+1 fixture is not one byte over")

    over = replies(drive(env, state, ("w1", "write_ledger", {"content": over_limit})))[0]
    if over != env_mod.WRITE_TOO_LARGE:
        problems.append(f"boundary+1 bytes was not refused: {over[:120]!r}")
    # ATOMIC: nothing about the previous candidate moved
    if ledger.read_bytes() != before_bytes:
        problems.append("a refused write reached the disk")
    if state.get("piv_candidate_digest") != before_digest or phase(state) is not before_phase:
        problems.append("a refused write moved the candidate digest or the phase")
    if env_mod.evaluator_failure(state) is not None:
        problems.append("an over-envelope write became an evaluator failure rather than a refusal")

    # exactly at the limit is ACCEPTED as a write (the boundary is `>`), even
    # though the protocol boundary will refuse the content as a ledger
    at = replies(drive(env, state, ("w2", "write_ledger", {"content": at_limit})))[0]
    if at == env_mod.WRITE_TOO_LARGE:
        problems.append("a write of exactly MAX_WRITE_BYTES bytes was refused")
    if env_mod.evaluator_failure(state) is not None:
        problems.append("a boundary-size write quarantined the rollout")

    # THE ENVELOPE PREDICATE ITSELF, in bytes and lines
    if env_mod.ledger_envelope_breach(b"a" * limit) is not None:
        problems.append("exactly the envelope is a breach")
    if env_mod.ledger_envelope_breach(b"a" * (limit + 1)) is None:
        problems.append("one byte over the envelope is not a breach")
    if env_mod.ledger_envelope_breach("€".encode("utf-8") * (limit // 3 + 1)) is None:
        problems.append("a multibyte ledger under the CHARACTER count but over the BYTE count passed")
    if env_mod.ledger_envelope_breach(b"\n" * (env_mod.LEDGER_ENVELOPE_LINES + 1)) is None:
        problems.append("the line envelope does not bite")
    # ...and write_ledger refuses a line breach too, so the read-side refusal
    # can never fire on something the agent was allowed to write
    many_lines = replies(drive(env, state, ("w3", "write_ledger",
                                            {"content": "\n" * (env_mod.LEDGER_ENVELOPE_LINES + 1)})))[0]
    if many_lines != env_mod.WRITE_TOO_LARGE:
        problems.append(f"a ledger over the LINE envelope was stored: {many_lines[:80]!r}")

    # THE READ DOOR, independently: corrupt the stored file behind the tools
    # (state corruption is exactly what this defends against) and read it
    env2, state2, workspace2 = fresh()
    (workspace2 / env_mod.LEDGER).write_bytes(b"; " + b"a" * limit + b"\n")
    corrupted = replies(drive(env2, state2, ("r1", "read_file", {"path": env_mod.LEDGER})))[0]
    if corrupted != env_mod.READ_OVER_ENVELOPE:
        problems.append(f"an over-envelope stored ledger was not refused on read: {corrupted[:120]!r}")
    if len(corrupted) > 300:
        problems.append("the read refusal is not bounded")
    if env_mod.evaluator_failure(state2) is not None:
        problems.append("the read refusal quarantined the rollout instead of answering publicly")
    if state2.get("piv_complete_reads"):
        problems.append("a refused read was counted as a complete read")
    # the refusal is in the contract view, so it has an identity
    if "READ_OVER_ENVELOPE" not in (env_mod.episode_contract().get("messages") or {}):
        problems.append("READ_OVER_ENVELOPE is not bound by the contract digest")
    return check("the envelope is UTF-8 bytes and logical lines, pinned at the boundary and boundary+1 "
                 "with a multibyte character; a refused write is atomic; and the read door independently "
                 "refuses an over-envelope stored ledger with a bounded public message, never content",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 8. dependency pins and attempt identity
# --------------------------------------------------------------------------

def test_bounded_replies_are_bounded_in_bytes_and_the_episode_in_aggregate():
    """A LINE cap is not a byte cap, and `grep` echoes the agent's own ledger.

    The idempotent full read closes the whole-file door. It does not close
    `grep`, and the adversarial pass measured the hole: a LEGAL in-envelope
    ledger of 119 comment lines x ~400 bytes is under MAX_TOOL_OUTPUT_LINES
    and under MAX_GREP_HITS, so ONE grep returned 49,990 bytes — more than a
    whole ledger read — and twenty of them are representable in a single turn.
    Extrapolated over the turn budget that is tens of megabytes of input for a
    handful of completion tokens: exactly the amplification the read rule was
    added to remove, through a different door.

    The reviewer offered two closures and both are taken here:

      - MAX_TOOL_OUTPUT_BYTES bounds ONE bounded reply. Measured honest use
        over the shipped world and 50 generated ones: largest sliced read
        3,728 bytes, largest broad grep 10,478. 16,000 truncates neither.
      - MAX_EPISODE_OBSERVATION_BYTES bounds the AGGREGATE, counted as each
        reply is produced so the bound holds inside one call list too. Once
        spent, every observing tool is answered OBSERVATION_BUDGET_SPENT —
        and `write_ledger` and `submit` keep working, because a cost bound
        must never become a reward penalty.
    """
    problems = []
    if env_mod.MAX_TOOL_OUTPUT_BYTES >= env_mod.LEDGER_ENVELOPE_BYTES:
        problems.append("a bounded reply may be as large as a whole ledger read")

    env, state, workspace = fresh()
    # a LEGAL ledger the envelope admits, built to beat a line cap
    line = "; QQ " + "z" * 394
    payload = "\n".join(line for _ in range(119)) + "\n"
    if env_mod.ledger_envelope_breach(payload.encode("utf-8")) is not None:
        problems.append("the attack fixture is not inside the envelope; it witnesses nothing")
    drive(env, state, ("w", "write_ledger", {"content": payload}))
    one_grep = replies(drive(env, state, ("g", "grep", {"pattern": "QQ", "path": env_mod.LEDGER})))[0]
    grep_bytes = len(one_grep.encode("utf-8"))
    if grep_bytes > env_mod.MAX_TOOL_OUTPUT_BYTES + len(env_mod.CLIP_MORE_BYTES) + 64:
        problems.append(f"one grep returned {grep_bytes} bytes against a cap of "
                        f"{env_mod.MAX_TOOL_OUTPUT_BYTES}")
    if env_mod.CLIP_MORE_BYTES.format(limit=env_mod.MAX_TOOL_OUTPUT_BYTES) not in one_grep:
        problems.append("a truncated reply does not say it was truncated")
    # ...and the truncation is valid UTF-8 even when a multibyte character
    # straddles the cut
    wide = ("€" * (env_mod.MAX_TOOL_OUTPUT_BYTES // 3 + 10))
    cut = env_mod._clip_bytes(wide)
    if len(cut.encode("utf-8")) > env_mod.MAX_TOOL_OUTPUT_BYTES + len(env_mod.CLIP_MORE_BYTES) + 16:
        problems.append("the byte clip does not bound a multibyte reply")
    if "�" in cut:
        problems.append("the byte clip split a character")

    # HONEST USE IS NOT TRUNCATED: every shipped public file, read and grepped
    env2, state2, _ = fresh()
    for name in env_mod.PUBLIC_FILES:
        if name == env_mod.LEDGER:
            continue
        reply = replies(drive(env2, state2, ("r", "read_file", {"path": name})))[0]
        if env_mod.CLIP_MORE_BYTES.format(limit=env_mod.MAX_TOOL_OUTPUT_BYTES) in reply:
            problems.append(f"an honest read of {name} was truncated by the byte cap")
    broad = replies(drive(env2, state2, ("g2", "grep", {"pattern": "2025-"})))[0]
    if env_mod.CLIP_MORE_BYTES.format(limit=env_mod.MAX_TOOL_OUTPUT_BYTES) in broad:
        problems.append("an honest broad grep was truncated by the byte cap")

    # THE AGGREGATE, driven to exhaustion through the real tool door
    turns = 0
    refused = None
    while turns < 80 and refused is None:
        out = replies(drive(env, state, *[(f"h{turns}_{i}", "grep",
                                           {"pattern": "QQ", "path": env_mod.LEDGER})
                                          for i in range(20)]))
        refused = next((r for r in out if r == env_mod.OBSERVATION_BUDGET_SPENT), None)
        turns += 1
    if refused is None:
        problems.append("the observation budget never bit")
    ceiling = env_mod.MAX_EPISODE_OBSERVATION_BYTES + env_mod.LEDGER_ENVELOPE_BYTES
    if state.get("piv_observation_bytes", 0) > ceiling:
        problems.append(f"observation bytes {state.get('piv_observation_bytes')} exceed the budget "
                        f"plus one reply ({ceiling})")
    if not state.get("piv_observation_refused"):
        problems.append("refused observing calls were not counted")
    # ...within ONE call list, not merely between turns
    spent_before = state["piv_observation_bytes"]
    out = replies(drive(env, state, *[(f"z{i}", "grep", {"pattern": "QQ", "path": env_mod.LEDGER})
                                      for i in range(20)]))
    if any(r != env_mod.OBSERVATION_BUDGET_SPENT for r in out):
        problems.append("a call list after the budget was spent still returned content")
    if state["piv_observation_bytes"] - spent_before > 20 * len(env_mod.OBSERVATION_BUDGET_SPENT) + 64:
        problems.append("the refusals themselves were not the only bytes spent")

    # DELIVERY STILL WORKS with the budget spent: a cost bound, not a penalty
    accepted = replies(drive(env, state, ("wG", "write_ledger", {"content": GOLDEN})))[0]
    if env_mod.parse_attestation(accepted) is None:
        problems.append(f"write_ledger was refused with the observation budget spent: {accepted[:80]!r}")
    ended = replies(drive(env, state, ("sG", "submit", {})))[0]
    if not ended.startswith(env_mod.SUBMIT_ACCEPTED):
        problems.append(f"submit was refused with the observation budget spent: {ended[:80]!r}")
    if env_mod.evaluator_failure(state) is not None:
        problems.append("the observation budget quarantined the rollout")

    # the refusal and the truncation marker are BOUND by the digest
    messages = env_mod.episode_contract().get("messages") or {}
    for name in ("OBSERVATION_BUDGET_SPENT", "CLIP_MORE_BYTES"):
        if name not in messages:
            problems.append(f"{name} is not in the contract view")
    observation = env_mod.episode_contract()["observation"]
    if observation.get("max_tool_output_bytes") != env_mod.MAX_TOOL_OUTPUT_BYTES \
            or observation.get("max_episode_observation_bytes") != env_mod.MAX_EPISODE_OBSERVATION_BYTES:
        problems.append("the contract view does not state the two byte bounds")
    if set(env_mod.OBSERVING_TOOLS) != {"list_files", "read_file", "grep", "run_beancount"}:
        problems.append(f"OBSERVING_TOOLS moved: {env_mod.OBSERVING_TOOLS}")
    return check("a bounded reply is capped in BYTES (a legal 119x400-byte ledger no longer returns "
                 "50 KB through grep) and the episode has an aggregate observation budget enforced per "
                 "reply; honest reads and greps are untouched, and write_ledger and submit keep working",
                 not problems, "\n".join(problems))


def test_the_generated_schema_dependencies_are_pinned_exactly():
    """The digest binds schemas we do not write; a bump must be loud.

    `episode_contract_digest()` covers the tool names, descriptions and JSON
    schemas AS THE FRAMEWORK GENERATES THEM: `verifiers` calls
    `openai-agents`' `function_schema`, which parses our docstrings with
    `griffelib` and emits the schema through `pydantic`/`pydantic-core`. A
    minor bump in any of those can move the digest with no change of ours.

    The reviewer asked for pins AND for the strict digest. The pins are in
    `pyproject.toml`, the same set is `PINNED_LIBRARIES`, every rollout
    carries `state["piv_library_versions"]` as provenance, and this test is
    what makes an upgrade fail the battery instead of drifting through it. The
    versions are deliberately NOT in the digest: that would refuse every
    manifested world on a patch bump that changed nothing the model sees.
    """
    import tomllib

    problems = []
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pins = {}
    for spec in pyproject["project"]["dependencies"]:
        if "==" not in spec:
            problems.append(f"dependency {spec!r} is not pinned exactly")
            continue
        name, version = spec.split("==", 1)
        pins[name.strip()] = version.strip()
    installed = env_mod.library_versions()
    if set(pins) != set(env_mod.PINNED_LIBRARIES):
        problems.append(f"pyproject pins and PINNED_LIBRARIES differ: "
                        f"{sorted(set(pins) ^ set(env_mod.PINNED_LIBRARIES))}")
    for name in env_mod.PINNED_LIBRARIES:
        if installed.get(name) != pins.get(name):
            problems.append(f"{name} is installed at {installed.get(name)!r}, pinned at "
                            f"{pins.get(name)!r}: re-pin, re-run the battery and treat any moved "
                            f"episode digest as a new measurement condition")
    # every rollout carries them, including one that never calls a tool
    results, _client, raised = run([write(), submit()], state_columns=["piv_library_versions"])
    if raised is not None:
        problems.append(f"evaluate raised {type(raised).__name__}")
    elif one(results).get("piv_library_versions") != installed:
        problems.append(f"the rollout does not carry the library versions: "
                        f"{one(results).get('piv_library_versions')!r}")
    bare, _client, raised = run([narrated(), narrated(), narrated()],
                                state_columns=["piv_library_versions"])
    if raised is None and (bare["outputs"] or [{}])[0].get("piv_library_versions") != installed:
        problems.append("a rollout that never called a tool carries no library versions")
    # and they are NOT in the contract digest: that is provenance, not identity
    payload = json.dumps(env_mod.episode_contract(), sort_keys=True)
    for version in installed.values():
        if version and f'"{version}"' in payload:
            problems.append(f"a library version ({version}) reached the contract view")
    return check("verifiers/openai/openai-agents/griffelib/pydantic/pydantic-core/datasets/beancount are "
                 "pinned exactly in pyproject.toml, equal to what is installed, carried on every rollout "
                 "as provenance, and absent from the contract digest",
                 not problems, "\n".join(problems))


def test_the_rollout_id_is_an_attempt_identity():
    """One id per ATTEMPT, so billed requests can be bound to one of them.

    `Environment.run_rollout` wraps `run_rollout_attempt` in `maybe_retry`,
    and that closure re-enters `rollout(input, …)`, which builds a FRESH state
    through `init_state`. So a retried attempt has no `workspace`, mints a new
    `piv_rollout_id` here, and the measurement client — which receives the
    same dict as `state` — can bind every provider request it makes to the
    attempt that made it rather than inferring an attempt boundary from the
    shape of the prompt. Nothing model-facing carries it.
    """
    problems = []
    env = load_environment()
    ids = []
    for _ in range(3):
        state = {}                                # what a fresh attempt gets
        env._workspace(state)
        ids.append(state.get("piv_rollout_id"))
    if len(set(ids)) != 3 or not all(ids):
        problems.append(f"three attempts produced {ids}")
    # stable WITHIN an attempt: a second tool call must not re-mint it
    state = {}
    env._workspace(state)
    once = state["piv_rollout_id"]
    env._workspace(state)
    if state["piv_rollout_id"] != once:
        problems.append("the id was re-minted inside one attempt")
    # the framework really does build a fresh state per attempt: `run_rollout`
    # wraps `run_rollout_attempt` in `maybe_retry`, and that closure re-enters
    # `rollout(input, …)`, whose first line is `await self.init_state(...)`.
    # Pinned by source rather than assumed, so a framework change that made a
    # retry reuse the previous attempt's state fails here.
    import inspect
    from verifiers.legacy.envs.multiturn_env import MultiTurnEnv
    source = inspect.getsource(MultiTurnEnv.rollout)
    if "init_state" not in source:
        problems.append("MultiTurnEnv.rollout no longer builds its state from init_state; "
                        "re-verify that a retry does not reuse the previous attempt's state")
    # it never reaches the model
    results, _client, raised = run([write(), submit()], state_columns=["piv_rollout_id"])
    if raised is not None:
        problems.append(f"evaluate raised {type(raised).__name__}")
    else:
        out = one(results)
        rollout_id = out.get("piv_rollout_id")
        if not rollout_id:
            problems.append("the rollout carries no attempt id")
        else:
            transcript = json.dumps(out.get("completion"), default=str) + json.dumps(out.get("prompt"), default=str)
            if rollout_id in transcript:
                problems.append("the attempt id reached the transcript")
    return check("piv_rollout_id is minted once per attempt (a fresh state mints a new one, a second "
                 "tool call does not) and never reaches the model",
                 not problems, "\n".join(problems))


TESTS = [
    test_a_narrated_turn_does_not_end_the_episode,
    test_an_empty_turn_does_not_end_the_episode,
    test_a_truncated_turn_does_not_end_the_episode,
    test_the_nudge_carries_no_task_information,
    test_the_episode_is_an_explicit_named_state_machine,
    test_submit_with_nothing_written_is_refused_and_the_episode_continues,
    test_submit_after_a_refused_write_names_the_refusal_and_continues,
    test_an_accepted_submit_binds_the_latest_candidate_hash_once,
    test_narration_claiming_success_has_no_effect,
    test_submit_freezes_the_workspace,
    test_submit_is_the_only_agent_driven_termination,
    test_three_consecutive_no_tool_turns_end_the_episode,
    test_a_tool_call_resets_the_no_tool_run,
    test_an_unbroken_run_of_truncated_turns_ends_under_the_truncation_limit,
    test_two_per_turn_caps_are_measured_at_exactly_the_same_output_budget,
    test_a_submit_on_the_exhausting_turn_is_still_the_agent_ending_the_episode,
    test_pending_calls_on_the_exhausting_turn_run_and_never_buy_another_request,
    test_the_ceiling_is_configurable_and_defaults_to_the_constant,
    test_both_token_limit_spellings_are_clamped_into_one_field,
    test_the_native_request_body_carries_the_intended_cap,
    test_provider_usage_that_cannot_meter_the_ceiling_is_flagged_not_scored,
    test_the_episode_contract_digest_is_pinned,
    test_the_bound_transition_table_is_walked_through_the_real_tools,
    test_the_prompt_and_the_digest_follow_the_ceiling_actually_served,
    test_the_digest_moves_with_the_contract_and_is_stable_across_processes,
    test_the_prompt_discloses_the_terminal_budgets,
    test_an_accepted_submit_cuts_off_the_rest_of_its_own_call_list,
    test_max_turns_without_submit_scores_the_last_committed_revision,
    test_a_submit_on_the_last_turn_is_named_unexecuted_not_never_submitted,
    test_the_tool_surface_is_six_tools_one_write_one_terminal,
    test_tool_call_arguments_are_counted_in_the_plausibility_floor,
    test_every_model_facing_reply_is_a_bound_constant,
    test_the_ledger_is_sent_once_per_revision,
    test_the_envelope_is_utf8_bytes_and_both_doors_enforce_it,
    test_bounded_replies_are_bounded_in_bytes_and_the_episode_in_aggregate,
    test_the_generated_schema_dependencies_are_pinned_exactly,
    test_the_rollout_id_is_an_attempt_identity,
]


def run_all() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run_all())
