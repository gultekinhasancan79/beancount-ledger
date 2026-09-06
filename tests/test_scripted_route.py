"""The full route, end to end, with a scripted model: no network, no fabricated state.

Every other witness in this package stops one step short of the object a
consumer actually receives. The composition-root test drives the tool loop
and calls the bound reward on state; the quarantine test feeds a synthetic
framework result into our `generate` override. Both are real code on real
paths, and neither proves the chain

    tool call -> write -> score -> state["error"] -> error_data
              -> RolloutOutput -> partition -> GenerateOutputs

as one thing. This does. `Environment.evaluate` is called through the public
factory with a deterministic client that plays the assistant's part: turn one
writes a ledger through the registered tool, turn two calls `submit`. Only the
model is scripted; the framework runs its own rollout, its own rubric group,
its own output builder.

The episode contract itself — `submit`, the answered no-tool-call turn, the
consecutive-no-tool-call limit and the post-submit freeze — has its own
witnesses in `test_episode_contract.py`.

Three runs:

  control    correct ledger        -> reward 1.0, no error, status VALID
  hostile    plugin directive      -> reward 0.0, no error, counted (a protocol
                                      rejection is the agent's outcome)
  fault      correct ledger, but   -> quarantined under PIVEvaluatorFailed,
             score_core raises        status INVALID, aggregates NaN

The fault run is the one that matters: it is the first time the placeholder
zero is shown to be excluded on the object a trainer would consume, rather
than on a state dict a test happened to hold.

    python tests/test_scripted_route.py
"""

import asyncio
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import verifiers as vf  # noqa: E402
from verifiers.legacy.types import Response, ResponseMessage, ToolCall  # noqa: E402

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.beancount_ledger import load_environment  # noqa: E402

GOLDEN = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")
HOSTILE = (
    'option "operating_currency" "USD"\n'
    ' plugin "colorsys"\n'
    "2025-11-01 open Assets:A USD\n"
    "2025-11-01 open Assets:B USD\n"
    '2025-11-05 * "Office Depot" "x"\n'
    "  Assets:A   1.00 USD\n"
    "  Assets:B  -1.00 USD\n"
)


def submit_turn(tag: str) -> "ResponseMessage":
    """How a scripted model ends an episode under the PLAN §6 contract.

    It used to be a bare assistant message ("Done.") with no tool call,
    because the framework's `ToolEnv.no_tools_called` ended the rollout
    there. That default is gone — a turn with no tool call is now answered
    with a fixed nudge and counted — so the scripted model says the same
    thing it always meant, in the way the contract now spells it: it calls
    `submit`. Every route below keeps its turn count and its assertions.
    """
    return ResponseMessage(
        content="", finish_reason="tool_calls", is_truncated=False,
        tool_calls=[ToolCall(id=f"submit-{tag}", name="submit", arguments="{}")],
    )


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:10]:
            print(f"      {line}")
    return ok


class ScriptedClient(vf.Client):
    """A model that always does the same thing: write one ledger, then submit.

    Implements the framework's client adapter rather than imitating an HTTP
    API, so the framework's own prompt conversion, tool handling and response
    parsing all run. The only scripted part is what the assistant "says".
    """

    def __init__(self, ledger_text: str):
        super().__init__(object())
        self.ledger_text = ledger_text
        self.turn = 0
        self.prompts_seen = []

    def setup_client(self, config):
        return object()

    async def to_native_tool(self, tool):
        return tool

    async def to_native_prompt(self, messages):
        return messages, {}

    async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
        self.turn += 1
        self.prompts_seen.append(len(prompt))
        if self.turn == 1:
            message = ResponseMessage(
                content="",
                tool_calls=[ToolCall(
                    id="call-write-1", name="write_ledger",
                    arguments=json.dumps({"content": self.ledger_text}),
                )],
                finish_reason="tool_calls", is_truncated=False,
            )
        else:
            message = submit_turn(str(self.turn))
        return Response(id=f"scripted-{self.turn}", created=0, model=model,
                        usage=None, message=message)

    async def raise_from_native_response(self, response):
        return None

    async def from_native_response(self, response):
        return response

    async def close(self):
        return None


def run_route(ledger_text: str, client=None):
    """Returns (results_or_None, client, raised_exception_or_None)."""
    env = load_environment()
    client = client or ScriptedClient(ledger_text)
    try:
        results = asyncio.run(env.evaluate(
            client=client, model="scripted", num_examples=1, rollouts_per_example=1,
            max_concurrent=1, save_results=False,
        ))
        return results, client, None
    except env_mod.PIVEvaluationBatchInvalid as exc:
        return None, client, exc


def test_control_route():
    results, client, raised = run_route(GOLDEN)
    problems = []
    if raised is None:
        split = env_mod.training_partition(results)
        if len(split["trajectories"]) != 1 or split["protocol_failure_artifacts"]:
            problems.append("a clean rollout is not a training trajectory by default")
        if (results["outputs"][0].get("metrics") or {}).get("piv/training_eligible") != 1.0:
            problems.append("a clean rollout is not projected as training-eligible")
    if raised is not None:
        return check("control raised unexpectedly", False, str(raised))
    meta, outputs = results["metadata"], results["outputs"]
    if len(outputs) != 1:
        problems.append(f"{len(outputs)} outputs, expected 1")
    elif outputs[0].get("reward") != 1.0 or outputs[0].get("error") is not None:
        problems.append(f"reward={outputs[0].get('reward')} error={outputs[0].get('error')}")
    if meta.get("piv_status") != "VALID":
        problems.append(f"status {meta.get('piv_status')}, expected VALID")
    if meta.get("avg_reward") != 1.0:
        problems.append(f"avg_reward {meta.get('avg_reward')!r}, expected 1.0 untouched")
    if client.turn != 2:
        problems.append(f"the scripted model was asked {client.turn} time(s); write then submit is two turns")
    if outputs and outputs[0].get("stop_condition") != "piv_submitted":
        problems.append(f"stop_condition {outputs[0].get('stop_condition')!r}, expected piv_submitted")
    if outputs and (outputs[0].get("metrics") or {}).get("piv/submitted") != 1.0:
        problems.append("piv/submitted was not projected for an episode the agent ended itself")
    return check(f"control: correct ledger through evaluate -> 1.0, VALID ({client.turn} turns)",
                 not problems, "\n".join(problems))


def test_hostile_route():
    """A protocol-rejected ledger is a counted zero — and cannot be submitted.

    The scripted model writes the hostile ledger and then calls `submit` on
    every later turn. Under the episode state machine that write leaves the
    rollout in ACTIVE_REJECTED, so each `submit` is refused ("the last
    write_ledger was refused") and the rollout runs to the turn cap, ending
    under `piv_turn_cap_no_submit`. The score is unchanged and is the point of
    this route: the last committed revision — a `ProtocolRejected` one — is
    the agent's plain 0.0, never an error and never a quarantine.
    """
    results, _, raised = run_route(HOSTILE)
    problems = []
    if raised is not None:
        return check("hostile raised unexpectedly", False, str(raised))
    meta, outputs = results["metadata"], results["outputs"]
    if len(outputs) != 1 or outputs[0].get("reward") != 0.0:
        problems.append(f"expected one counted 0.0, got {[(o.get('reward'), o.get('error')) for o in outputs]}")
    elif outputs[0].get("error") is not None:
        problems.append("a protocol rejection carried an error; it must be the agent's plain zero")
    if meta.get("piv_status") != "VALID" or meta.get("piv_quarantined_count") != 0:
        problems.append(f"protocol rejection changed batch status: {meta.get('piv_status')}")
    metrics = (outputs[0].get("metrics") or {}) if outputs else {}
    if metrics.get(env_mod.METRIC_SUBMITTED) != 0.0:
        problems.append("an unparseable candidate was accepted for delivery")
    if not metrics.get(env_mod.METRIC_SUBMIT_REFUSED):
        problems.append(f"piv/submit_refused {metrics.get(env_mod.METRIC_SUBMIT_REFUSED)}; "
                        "submit after a refused write must be refused")
    if outputs and outputs[0].get("stop_condition") != "piv_turn_cap_no_submit":
        problems.append(f"stop_condition {outputs[0].get('stop_condition')!r}")
    return check("hostile: plugin directive through evaluate -> 0.0, counted, nothing quarantined; "
                 "submit refused throughout, ending at piv_turn_cap_no_submit",
                 not problems, "\n".join(problems))


def test_fault_route():
    """The witness this file exists for."""
    real_core = env_mod.score_core

    def broken(state):
        raise RuntimeError("injected scorer bug")

    env_mod.score_core = broken
    try:
        results, _, raised = run_route(GOLDEN)
    finally:
        env_mod.score_core = real_core

    problems = []
    if raised is None:
        return check("fault: evaluate must RAISE PIVEvaluationBatchInvalid", False,
                     f"it returned a result with status {results['metadata'].get('piv_status')}")
    meta = raised.metadata
    outputs = []
    q = env_mod.quarantine_artifact(raised.batch_id)
    if len(q) != 1:
        problems.append(f"{len(q)} quarantined, expected 1")
    else:
        rec = q[0]
        if rec.get("code") != "PIVEvaluatorFailed":
            problems.append(f"quarantine code {rec.get('code')}")
        if "PIV_EVALUATOR_FAILED" not in rec.get("message", "") or "score_core" not in rec.get("message", ""):
            problems.append(f"bounded message missing phase: {rec.get('message')!r}")
        if "injected scorer bug" in json.dumps(rec.get("output", {}), default=str):
            problems.append("the scorer's exception text leaked into the rollout output")
        if rec.get("output", {}).get("reward") != 0.0:
            problems.append("quarantined rollout does not carry the placeholder 0.0")
    if meta.get("piv_status") != "INVALID":
        problems.append(f"status {meta.get('piv_status')}, expected INVALID under evaluate")
    if not (isinstance(meta.get("avg_reward"), float) and math.isnan(meta["avg_reward"])):
        problems.append(f"avg_reward {meta.get('avg_reward')!r} should be NaN")
    if meta.get("piv_conditional_avg_reward") is not None:
        problems.append("conditional average should be None with nothing scored")
    return check("fault: injected score_core failure through evaluate -> RAISES, quarantined, INVALID",
                 not problems, "\n".join(problems))


def test_framework_error_route():
    """A real framework error, through the real chain, lands in quarantine.

    Found by accident: the first version of the scripted client built an
    invalid Response, the framework wrapped it as ModelError, wrote
    state["error"], serialised it, and our partition quarantined it with
    status INVALID — the fail-closed table working on an error we did not
    author. Kept as the witness for the "unknown/infra -> quarantine" rule
    on a genuine framework path rather than a synthetic dict.
    """
    class BrokenClient(ScriptedClient):
        async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
            self.turn += 1
            return Response(id="x", created=0, model=model, usage=None,
                            message={"role": "assistant"})  # invalid: not a ResponseMessage

    _, _, raised = run_route(GOLDEN, client=BrokenClient(GOLDEN))
    ok = (raised is not None and raised.status == "INVALID"
          and [q.get("code") for q in raised.quarantined] == ["ModelError"])
    return check("framework error: ModelError through evaluate -> RAISES, quarantined, INVALID",
                 ok, f"raised={type(raised).__name__ if raised else None} q={[q.get('code') for q in (raised.quarantined if raised else [])]}")


def test_tool_bug_route():
    """A bug inside an owned tool is OUR failure, through the real loop.

    Measured: the framework's `stop_errors` defaults to [], so an exception
    inside a tool is formatted back to the model as text and the rollout
    simply continues — no error state, the final reward computed on whatever
    is on disk. Invisible. Our `call_tool` records the marker and raises it,
    the framework re-raises `ToolCallError from marker`, and the partition
    recognises the marker in the chain. The scorer's exception text must not
    reach the output.
    """
    real = env_mod.write_ledger

    def broken_write(content, workspace=""):
        raise RuntimeError("internal write bug with a secret path C:/private")

    env = load_environment()
    env.tool_map["write_ledger"] = broken_write
    client = ScriptedClient(GOLDEN)
    try:
        results = asyncio.run(env.evaluate(
            client=client, model="scripted", num_examples=1, rollouts_per_example=1,
            max_concurrent=1, save_results=False))
        return check("tool bug: must RAISE", False, f"returned status {results['metadata'].get('piv_status')}")
    except env_mod.PIVEvaluationBatchInvalid as exc:
        codes = [q.get("code") for q in exc.quarantined]
        artifact = env_mod.quarantine_artifact(exc.batch_id)
        leaked = "secret path" in json.dumps(artifact, default=str) or "secret path" in repr(exc)
        projected = bool(artifact) and (artifact[0].get("output") or {}).get("metrics", {}).get("piv/evaluator_failed") == 1.0
        ok = exc.status == "INVALID" and codes == ["PIVEvaluatorFailed"] and not leaked and projected
        return check("tool bug: internal write_ledger exception -> typed record projected, quarantined, no leak",
                     ok, f"status={exc.status} codes={codes} leaked={leaked} projected={projected}")
    finally:
        env.tool_map["write_ledger"] = real


def test_tool_body_typeerror_is_ours():
    """A correctly bound body that raises TypeError is OUR failure.

    The first `call_tool` caught `TypeError` around the whole invocation, so
    an implementation bug of that one common class would have been returned
    as an agent-misuse message with no marker — the invisible path again, one
    exception type wide. The bind step is separate now; this is the witness.
    """
    real = env_mod.write_ledger

    def body_typeerror(content, workspace=""):
        return None + 1  # TypeError inside a correctly bound body

    env = load_environment()
    env.tool_map["write_ledger"] = body_typeerror
    try:
        asyncio.run(env.evaluate(client=ScriptedClient(GOLDEN), model="scripted", num_examples=1,
                                 rollouts_per_example=1, max_concurrent=1, save_results=False))
        return check("tool-body TypeError must RAISE", False, "returned")
    except env_mod.PIVEvaluationBatchInvalid as exc:
        codes = [q.get("code") for q in exc.quarantined]
        return check("tool-body TypeError -> our marker, quarantined (not agent misuse)",
                     codes == ["PIVEvaluatorFailed"], f"codes={codes}")
    finally:
        env.tool_map["write_ledger"] = real


def test_false_attestation_is_an_evaluator_failure():
    """A tool that claims a commit it did not make is quarantined.

    The receipt is recomputed from the argument, the file bytes and the
    scorer's text before a revision advances. A regressed tool emitting a
    plausible but false receipt is exactly the disagreement the receipt
    exists to detect.
    """
    real = env_mod.write_ledger

    def lying_write(content, workspace=""):
        reply = real(content, workspace=workspace)      # commits correctly...
        (Path(workspace) / env_mod.LEDGER).write_text("2025-01-01 open Assets:X USD\n", encoding="utf-8")
        return reply                                     # ...then the file changes behind the receipt

    env = load_environment()
    env.tool_map["write_ledger"] = lying_write
    try:
        asyncio.run(env.evaluate(client=ScriptedClient(GOLDEN), model="scripted", num_examples=1,
                                 rollouts_per_example=1, max_concurrent=1, save_results=False))
        return check("false attestation must RAISE", False, "returned")
    except env_mod.PIVEvaluationBatchInvalid as exc:
        # The phase lives in the trusted artifact; the exception says only
        # owned allowlisted text.
        artifact = env_mod.quarantine_artifact(exc.batch_id)
        msgs = " ".join(q.get("message", "") for q in artifact)
        ok = [q.get("code") for q in exc.quarantined] == ["PIVEvaluatorFailed"] and "phase=attestation" in msgs
        return check("false attestation -> receipt recomputed, mismatch quarantined as ours",
                     ok, f"q={exc.quarantined} artifact_msgs={msgs[:200]}")
    finally:
        env.tool_map["write_ledger"] = real


def test_concurrent_rollouts_do_not_share_failure_state():
    """Two rollouts in one event loop; one tool fails; nothing crosses over.

    The rollout state reaches `call_tool` through a context variable. This
    runs two `env_response` calls concurrently on one environment with
    distinct states and a tool that fails only for one of them, then checks
    marker, revision and digest stayed with their own rollout.
    """
    import json as _json
    from types import SimpleNamespace

    real = env_mod.write_ledger
    env = load_environment()

    def selective(content, workspace=""):
        if "POISON" in content:
            raise RuntimeError("fails for this rollout only")
        return real(content, workspace=workspace)

    env.tool_map["write_ledger"] = selective
    a, b = {}, {}
    env._workspace(a); env._workspace(b)

    def turn(content):
        call = SimpleNamespace(id="c", name="write_ledger", arguments=_json.dumps({"content": content}))
        return [SimpleNamespace(role="assistant", content="", tool_calls=[call])]

    async def both():
        async def run_one(state, content):
            try:
                return await env.env_response(turn(content), state)
            except Exception as exc:  # the framework would wrap; here we see the raw marker
                return exc
        return await asyncio.gather(run_one(a, GOLDEN + "; POISON\n"), run_one(b, GOLDEN))

    try:
        ra, rb = asyncio.run(both())
    finally:
        env.tool_map["write_ledger"] = real

    ok = (env_mod.evaluator_failure(a) is not None and env_mod.evaluator_failure(b) is None
          and a.get("piv_revision", 0) == 0 and b.get("piv_revision") == 1
          and a["piv_rollout_id"] != b["piv_rollout_id"])
    return check("concurrent rollouts: failure state, revision and digest stay with their own rollout",
                 ok, f"a_failed={env_mod.evaluator_failure(a) is not None} b_failed={env_mod.evaluator_failure(b) is not None} "
                     f"rev_a={a.get('piv_revision')} rev_b={b.get('piv_revision')}")


def test_prior_correct_write_survives_a_refused_double_write_turn():
    """Contract: a refused turn has no side effect; scoring is over the last
    committed revision. So a correct first write followed by a refused
    double-write turn scores 1.0 — by decision, not by stale-state accident."""
    class WriteThenDouble(ScriptedClient):
        async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
            self.turn += 1
            if self.turn == 1:
                calls = [ToolCall(id="a", name="write_ledger", arguments=json.dumps({"content": GOLDEN}))]
            elif self.turn == 2:
                calls = [ToolCall(id="b", name="write_ledger", arguments=json.dumps({"content": HOSTILE})),
                         ToolCall(id="c", name="write_ledger", arguments=json.dumps({"content": HOSTILE}))]
            else:
                return Response(id=f"s{self.turn}", created=0, model=model, usage=None,
                                message=submit_turn(str(self.turn)))
            return Response(id=f"s{self.turn}", created=0, model=model, usage=None,
                            message=ResponseMessage(content="", tool_calls=calls, finish_reason="tool_calls", is_truncated=False))

    results, client, raised = run_route(GOLDEN, client=WriteThenDouble(GOLDEN))
    if raised is not None:
        return check("refused turn after a correct write must not raise", False, str(raised))
    out = results["outputs"][0]
    ok = out.get("reward") == 1.0 and out.get("error") is None and client.turn >= 3
    return check("correct write, then refused double-write turn -> 1.0 over the last committed revision",
                 ok, f"reward={out.get('reward')} turns={client.turn}")


def test_duplicate_ids_are_a_counted_terminal_protocol_failure():
    """Duplicate call ids end the rollout AND cost the agent the score.

    "One reply per distinct id" answered the environment's side and not the
    provider's: the assistant message still carries two calls under one id,
    which a provider requiring one result per call occurrence rejects on the
    next turn. So nothing executes and the rollout ends. The first terminal
    version then scored the last committed ledger — 1.0 after a correct
    write — which rewarded a malformed, non-replayable final action with the
    maximum score: an agent could terminate through invalid protocol after
    enough work and lose nothing. Now it is the agent's
    terminal protocol violation: counted, never quarantined, scored at the
    task contract's terminal protocol score (0.0) regardless of what is on
    disk, and projected as `piv/protocol_failed` so replay can drop it. The
    ledger stays for audit. Paired: correct prior ledger and hostile prior
    ledger get the same consequence; the recoverable multi-write route
    (unique ids) still earns its ordinary score, witnessed separately.
    """
    def client_for(first):
        class WriteThenDuplicate(ScriptedClient):
            async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
                self.turn += 1
                if self.turn == 1:
                    calls = [ToolCall(id="a", name="write_ledger", arguments=json.dumps({"content": first}))]
                else:
                    calls = [ToolCall(id="dup", name="read_file", arguments=json.dumps({"path": "ledger.beancount"})),
                             ToolCall(id="dup", name="run_beancount", arguments="{}")]
                return Response(id=f"s{self.turn}", created=0, model=model, usage=None,
                                message=ResponseMessage(content="", tool_calls=calls,
                                                        finish_reason="tool_calls", is_truncated=False))
        return WriteThenDuplicate(first)

    problems = []
    for label, ledger in (("correct prior ledger", GOLDEN), ("hostile prior ledger", HOSTILE)):
        results, client, raised = run_route(ledger, client=client_for(ledger))
        if raised is not None:
            problems.append(f"{label}: raised {type(raised).__name__} — must be counted, not quarantined")
            continue
        out = results["outputs"][0]
        meta = results["metadata"]
        metrics = out.get("metrics") or {}
        if out.get("reward") != 0.0:
            problems.append(f"{label}: reward {out.get('reward')}, expected the terminal protocol score 0.0")
        if out.get("error") is not None:
            problems.append(f"{label}: error set: {out.get('error')}")
        if client.turn != 2:
            problems.append(f"{label}: model called {client.turn} times, expected 2")
        # `piv_protocol_terminated` outranks the framework's `has_final_env_response`
        # (priority 55): the violation names the ending, not the mechanism.
        if out.get("stop_condition") != "piv_protocol_terminated":
            problems.append(f"{label}: stop_condition {out.get('stop_condition')}")
        if metrics.get("piv/protocol_failed") != 1.0:
            problems.append(f"{label}: protocol_failed metric {metrics.get('piv/protocol_failed')}")
        if metrics.get("piv/training_eligible") != 0.0:
            problems.append(f"{label}: training_eligible metric {metrics.get('piv/training_eligible')}")
        if meta.get("piv_status") != "VALID" or meta.get("piv_quarantined_count") != 0:
            problems.append(f"{label}: status={meta.get('piv_status')} quarantined={meta.get('piv_quarantined_count')}")
        # the package default keeps it out of replay and in the artifacts
        split = env_mod.training_partition(results)
        if split["trajectories"] or len(split["protocol_failure_artifacts"]) != 1 or meta.get("piv_training_eligible") != 0:
            problems.append(f"{label}: training_partition kept an unreplayable trajectory: "
                            f"{len(split['trajectories'])}/{len(split['protocol_failure_artifacts'])} eligible={meta.get('piv_training_eligible')}")
    return check("duplicate ids -> counted terminal protocol failure: 0.0 for correct AND hostile prior ledgers, "
                 "VALID, never quarantined, no third model turn, piv/protocol_failed=1.0",
                 not problems, "\n".join(problems))


def test_the_training_door_returns_only_replayable_trajectories():
    """Enforced, not exposed: the package's training entry point keeps
    counted protocol failures out of `outputs` and in an artifact list with
    their original index; the evaluation entry point keeps them in
    `outputs` at 0.0 for score reporting. Isolated from parse-once so an
    output-selection regression is attributable on its own.
    """
    class WriteThenDuplicate(ScriptedClient):
        async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
            self.turn += 1
            if self.turn == 1:
                calls = [ToolCall(id="a", name="write_ledger", arguments=json.dumps({"content": GOLDEN}))]
            else:
                calls = [ToolCall(id="dup", name="read_file", arguments=json.dumps({"path": "ledger.beancount"})),
                         ToolCall(id="dup", name="run_beancount", arguments="{}")]
            return Response(id=f"s{self.turn}", created=0, model=model, usage=None,
                            message=ResponseMessage(content="", tool_calls=calls,
                                                    finish_reason="tool_calls", is_truncated=False))

    problems = []
    env = load_environment()
    inputs = env._get_eval_inputs(1, 1)
    training = asyncio.run(env.generate(inputs, client=WriteThenDuplicate(GOLDEN), model="scripted", max_concurrent=1))
    meta = training["metadata"]
    artifacts = meta.get("piv_protocol_failure_artifacts", [])
    if training["outputs"]:
        problems.append(f"training outputs kept an unreplayable trajectory: {len(training['outputs'])}")
    if len(artifacts) != 1 or artifacts[0].get("original_index") != 0 or "output" not in artifacts[0]:
        problems.append(f"protocol failure artifacts: {[(a.get('original_index'), sorted(a)) for a in artifacts]}")
    if meta.get("piv_scored") != 1 or meta.get("piv_status") != "VALID" or meta.get("piv_protocol_failures") != 1:
        problems.append(f"counts: scored={meta.get('piv_scored')} status={meta.get('piv_status')} pf={meta.get('piv_protocol_failures')}")
    denominators = meta.get("piv_denominators") or {}
    if denominators.get("counted_outcomes") != 1 or denominators.get("training_trajectories") != 0 \
            or "protocol failures at 0.0 included" not in denominators.get("aggregates_over", ""):
        problems.append(f"denominators not labelled: {denominators}")
    if meta.get("piv_protocol_artifacts_truncated") is not False:
        problems.append("artifact truncation flag missing")

    results, client, raised = run_route(GOLDEN, client=WriteThenDuplicate(GOLDEN))
    if raised is not None:
        problems.append(f"evaluate raised {raised}")
    elif len(results["outputs"]) != 1 or results["outputs"][0].get("reward") != 0.0 \
            or results["metadata"].get("piv_protocol_failure_artifacts"):
        problems.append("evaluate did not keep the counted protocol failure in outputs at 0.0")
    return check("training door: protocol failure moved to artifacts with its index; evaluation keeps it in outputs at 0.0",
                 not problems, "\n".join(problems))


def test_the_raised_exception_carries_no_canary():
    """Truncation is not redaction: the exception says only owned text.

    Canaries at the head, middle and tail of a long tool exception, and one
    in the agent's own submitted text. None may appear in str/repr of the
    raised exception, its `.metadata`, `.args` or `.quarantined`; and the
    serialised `.quarantined` is capped. "The word `output` is absent" was
    never a confidentiality witness.
    """
    canaries = ("CANARY-HEAD-7f3a", "CANARY-MID-9c1e", "CANARY-TAIL-2b8d", "CANARY-LEDGER-5e4f")
    real = env_mod.write_ledger

    class CanaryToolBug(RuntimeError):
        """A defect type of this test's own.

        `EVALUATOR_DIAGNOSTICS` folds records by `_fingerprint` — (phase,
        exception type, top owned frame) — and a folded record keeps the
        FIRST message it saw. `test_tool_bug_route` already raised a plain
        `RuntimeError` from `write_ledger` earlier in this process, so a
        plain `RuntimeError` here lands on that record and the head canary is
        never stored: the non-vacuity probe below would read a store that had
        silently dropped the string it looks for. A distinct type is a
        distinct fingerprint, so this failure gets its own record.
        """

    def broken_write(content, workspace=""):
        raise CanaryToolBug(f"{canaries[0]} {'x' * 3000} {canaries[1]} {'y' * 3000} {canaries[2]}")

    env = load_environment()
    env.tool_map["write_ledger"] = broken_write
    poisoned = GOLDEN + f"\n; {canaries[3]}\n"
    try:
        asyncio.run(env.evaluate(client=ScriptedClient(poisoned), model="scripted", num_examples=1,
                                 rollouts_per_example=1, max_concurrent=1, save_results=False))
        return check("canary route must RAISE", False, "returned")
    except env_mod.PIVEvaluationBatchInvalid as exc:
        surfaces = {"str": str(exc), "repr": repr(exc), "args": json.dumps(exc.args, default=str),
                    "metadata": json.dumps(exc.metadata, default=str),
                    "quarantined": json.dumps(exc.quarantined, default=str)}
        leaks = [f"{name}: {c}" for name, text in surfaces.items() for c in canaries if c in text]
        cap_ok = len(surfaces["quarantined"]) <= 300 * max(1, len(exc.quarantined))
        # ...and the canaries DID exist somewhere trusted, so the test is not
        # vacuous: the exception head reaches the diagnostics store (capped
        # detail), the agent's own text reaches the artifact's trajectory.
        artifact = env_mod.quarantine_artifact(exc.batch_id)
        artifact_text = json.dumps(artifact, default=str)
        # This failure's OWN diagnostic record, not whatever else the store
        # holds: reading the whole store would pass on some other test's text.
        diagnostics_text = json.dumps([d for d in env_mod.EVALUATOR_DIAGNOSTICS.values()
                                       if d.get("type") == CanaryToolBug.__name__], default=str)
        planted = canaries[0] in diagnostics_text and canaries[3] in artifact_text
        return check("raised exception: no canary in str/repr/args/metadata/quarantined; size capped",
                     not leaks and cap_ok and planted,
                     "\n".join(leaks) + f"\nquarantined bytes={len(surfaces['quarantined'])} planted={planted} "
                     f"head_in_diag={canaries[0] in diagnostics_text} ledger_in_artifact={canaries[3] in artifact_text} "
                     f"artifact_keys={sorted((artifact[0].get('output') or {}).keys()) if artifact else None}")
    finally:
        env.tool_map["write_ledger"] = real


def test_quarantine_survives_a_broken_projection_monitor():
    """The metric refines attribution; it is not the guard.

    If the `piv/evaluator_failed` monitor itself throws, the framework
    swallows it to 0.0 and the projection is gone. The typed marker still
    reaches `state["error"]`, the top-level code is ours, the table
    quarantines. A scorer fault must not escape as a counted zero because a
    monitor broke.
    """
    real_projection = env_mod.evaluator_failed_projection
    real_core = env_mod.score_core

    def broken_projection(state):
        raise RuntimeError("monitor bug")

    def faulty_core(state):
        raise RuntimeError("scorer fault")

    env_mod.evaluator_failed_projection = broken_projection
    env_mod.score_core = faulty_core
    try:
        results, client, raised = run_route(GOLDEN)
    finally:
        env_mod.evaluator_failed_projection = real_projection
        env_mod.score_core = real_core
    ok = raised is not None and [q.get("code") for q in raised.quarantined] == ["PIVEvaluatorFailed"]
    projected = None
    if raised is not None:
        artifact = env_mod.quarantine_artifact(raised.batch_id)
        projected = (artifact[0].get("output") or {}).get("metrics", {}).get("piv/evaluator_failed") if artifact else None
    return check("projection monitor throws -> the marker's top-level code still quarantines (projection 0.0)",
                 ok and projected == 0.0,
                 f"raised={type(raised).__name__ if raised else None} returned={results is not None} projected={projected}")


def test_agent_misuse_route():
    """The agent's malformed call is the agent's outcome, and the rollout continues.

    The scripted model calls write_ledger with the wrong argument name. Our
    `call_tool` returns a bounded public message instead of letting the
    framework format the exception; no error state; the reward is then
    computed on the untouched ledger: 0.0, counted, VALID batch.
    """
    class MisusingClient(ScriptedClient):
        async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
            self.turn += 1
            if self.turn == 1:
                message = ResponseMessage(
                    content="", finish_reason="tool_calls", is_truncated=False,
                    tool_calls=[ToolCall(id="c1", name="write_ledger",
                                         arguments=json.dumps({"contents_typo": "x"}))])
            else:
                message = submit_turn(str(self.turn))
            return Response(id=f"s{self.turn}", created=0, model=model, usage=None, message=message)

    results, client, raised = run_route(GOLDEN, client=MisusingClient(GOLDEN))
    if raised is not None:
        return check("agent misuse must not raise", False, str(raised))
    out = results["outputs"][0] if results["outputs"] else {}
    ok = (out.get("reward") == 0.0 and out.get("error") is None
          and results["metadata"].get("piv_status") == "VALID" and client.turn >= 2)
    return check("agent misuse: wrong argument name -> public message, rollout continues, counted 0.0",
                 ok, f"reward={out.get('reward')} error={out.get('error')} status={results['metadata'].get('piv_status')} turns={client.turn}")


def test_two_writes_in_one_turn_are_refused_before_any_side_effect():
    class DoubleWriter(ScriptedClient):
        async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
            self.turn += 1
            if self.turn == 1:
                message = ResponseMessage(
                    content="", finish_reason="tool_calls", is_truncated=False,
                    tool_calls=[
                        ToolCall(id="a", name="write_ledger", arguments=json.dumps({"content": GOLDEN})),
                        ToolCall(id="b", name="write_ledger", arguments=json.dumps({"content": HOSTILE})),
                    ])
            else:
                message = submit_turn(str(self.turn))
            return Response(id=f"s{self.turn}", created=0, model=model, usage=None, message=message)

    results, client, raised = run_route(GOLDEN, client=DoubleWriter(GOLDEN))
    if raised is not None:
        return check("double write must not raise", False, str(raised))
    out = results["outputs"][0] if results["outputs"] else {}
    # nothing was written: the untouched world ledger scores 0.0, revision stayed 0
    ok = out.get("reward") == 0.0 and out.get("error") is None and results["metadata"].get("piv_status") == "VALID"
    return check("two write_ledger calls in one turn -> turn refused, nothing written, counted 0.0",
                 ok, f"reward={out.get('reward')} error={out.get('error')}")


TESTS = [test_control_route, test_hostile_route, test_fault_route, test_framework_error_route,
         test_tool_bug_route, test_tool_body_typeerror_is_ours, test_false_attestation_is_an_evaluator_failure,
         test_concurrent_rollouts_do_not_share_failure_state,
         test_duplicate_ids_are_a_counted_terminal_protocol_failure,
         test_the_training_door_returns_only_replayable_trajectories, test_the_raised_exception_carries_no_canary,
         test_quarantine_survives_a_broken_projection_monitor, test_agent_misuse_route,
         test_two_writes_in_one_turn_are_refused_before_any_side_effect,
         test_prior_correct_write_survives_a_refused_double_write_turn]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
