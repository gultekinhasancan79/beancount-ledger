"""The cash-application family through the REAL evaluate door, end to end.

Step 6 of the specification's implementation order (`v10-codex/
cash_application_spec.md` §3, §4, §8) put the second deliverable into the
live environment: a seventh tool, contract 5, a register with its own phase
machine and revisions, and a composite reward `total = L x A`. Every other
suite in this package stops one step short of that object. The world suite
checks the projection and the truth; the scoring suite checks
`application/1` and `composite/1` on documents built in the test; the
episode-contract suite checks the two resolved contract views. None of them
proves the chain

    write_ledger + write_cash_application -> attestation -> commitment
        -> submit binds both -> score_core composes -> _publish

as one thing, on a task id a caller actually asks for. This does.
`load_environment("cash_application_001")` is called, a deterministic client
plays the assistant's part, and the framework runs its own rollout, its own
rubric group and its own output builder.

The four routes the specification and round 12 §2 name, plus what they imply:

  golden       golden ledger + golden register  -> total 1.0, complete
  ledger only  golden ledger, no register       -> total 0, L reported, ABSENT
  superseded   valid register then an invalid   -> A = 0, REJECTED, no fallback
  over-envelope a request refused before store  -> previous revision intact

and then the machinery each of them rides on: a non-protocol ending scoring
the last committed revision of EACH artifact, `score_core` composing, and
`_publish` writing the canonical register and both digests into
`delivery.json` while the legacy manifest stays exactly what it was.

    python tests/test_cash_application_route.py
"""

import asyncio
import json
import sys
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import verifiers as vf  # noqa: E402
from verifiers.legacy.types import Response, ResponseMessage, ToolCall  # noqa: E402

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.beancount_ledger import load_environment  # noqa: E402
from beancount_ledger.candidate import application as A  # noqa: E402
from beancount_ledger.candidate.canonical import canonical_decimal  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.worlds import CASH_APPLICATION_REGISTRY  # noqa: E402

import test_cash_application_scoring as CA  # noqa: E402

TASK = "cash_application_001"


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:12]:
            print(f"      {line}")
    return ok


# --------------------------------------------------------------------------
# the case, derived once through the production door
# --------------------------------------------------------------------------

_CASE: dict = {}


def case() -> dict:
    """The golden ledger and the golden register of `cash_application_001`,
    plus the documents the routes below perturb."""
    if not _CASE:
        world, task = CASH_APPLICATION_REGISTRY[TASK]
        _bundle, inputs = derive_contract(world, task)
        golden = CA.golden_document(inputs.application)
        # An internally CONTRADICTORY register: one row's `remaining` no
        # longer equals basis - applied - credited - written_off, which
        # `application.row_identity` REJECTS at the parse boundary. It is
        # well-formed JSON and well-formed schema: what makes it invalid is
        # the accounting, which is the case the lifecycle rule is about.
        invalid = json.loads(json.dumps(golden))
        invalid["closing_open_items"][0]["remaining"] = "1.00"
        _CASE.update(ledger=inputs.golden_text, truth=inputs.application,
                     register=json.dumps(golden), invalid=json.dumps(invalid))
        # Over the 16,000-byte envelope and nothing else wrong: the same
        # golden document, padded with insignificant JSON whitespace, so the
        # only reason it can be refused is its size.
        _CASE["oversize"] = json.dumps(golden) + " " * (env_mod.APPLICATION_ENVELOPE_BYTES + 1)
    return _CASE


# --------------------------------------------------------------------------
# a scripted client, as in test_episode_contract.py
# --------------------------------------------------------------------------

def calls(*specs) -> ResponseMessage:
    return ResponseMessage(
        content="", finish_reason="tool_calls", is_truncated=False,
        tool_calls=[ToolCall(id=i, name=n, arguments=a if isinstance(a, str) else json.dumps(a))
                    for i, n, a in specs])


def narrated(text: str = "Working through the open items.") -> ResponseMessage:
    return ResponseMessage(content=text, tool_calls=None, finish_reason="stop", is_truncated=False)


def write_ledger(tag: str = "w", text: str | None = None) -> ResponseMessage:
    return calls((tag, "write_ledger", {"content": case()["ledger"] if text is None else text}))


def write_register(tag: str, text: str) -> ResponseMessage:
    return calls((tag, "write_cash_application", {"content": text}))


def deliver(tag: str = "d", register: str | None = None) -> ResponseMessage:
    """One turn writing both artifacts — legal, because the per-turn rule is
    one call per WRITE TOOL, not one write call."""
    specs = [(tag + "l", "write_ledger", {"content": case()["ledger"]})]
    if register is not None:
        specs.append((tag + "a", "write_cash_application", {"content": register}))
    return calls(*specs)


def submit(tag: str = "s") -> ResponseMessage:
    return calls((tag, "submit", {}))


class TurnScript(vf.Client):
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
        message = self.turns[self.turn - 1] if self.turn <= len(self.turns) else narrated()
        return Response(id=f"scripted-{self.turn}", created=0, model=model, usage=None, message=message)

    async def raise_from_native_response(self, response):
        return None

    async def from_native_response(self, response):
        return response

    async def close(self):
        return None


COLUMNS = ["workspace", "piv_application_phase", "piv_application_revision",
           "piv_submitted_application_phase", "piv_submitted_application_digest",
           "piv_application_digest", "piv_score"]


def run(turns, task_id: str = TASK):
    """(output row, raised). One rollout through the real evaluate door."""
    env = load_environment(task_id)
    client = TurnScript(turns)
    try:
        results = asyncio.run(env.evaluate(
            client=client, model="scripted", num_examples=1, rollouts_per_example=1,
            max_concurrent=1, save_results=False, state_columns=list(COLUMNS)))
        return (results["outputs"] or [{}])[0], None
    except env_mod.PIVEvaluationBatchInvalid as exc:
        return {}, exc


def tool_replies(out) -> list:
    texts = []
    for message in out.get("completion") or []:
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        if role == "tool":
            content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
            texts.append(str(content))
    return texts


def publication(out) -> tuple:
    """(DeliveryReceipt, ApplicationDelivery | None) read back off disk."""
    manifest = Path(out["workspace"]) / env_mod.PUBLICATION_FILE
    return env_mod._read_publication(manifest.read_text(encoding="utf-8"))


def metric(out, name) -> float | None:
    return (out.get("metrics") or {}).get(name)


# --------------------------------------------------------------------------
# 1. the four routes
# --------------------------------------------------------------------------

def test_the_golden_ledger_and_register_score_one_and_complete():
    """Case 1 delivered whole: `L = 1`, `A = 1`, `total = 1.0`, complete.

    The register the model writes is the truth's own, in the delivered
    schema, so nothing here depends on the test's arithmetic: it is the
    document `tests/test_cash_application_scoring.py` scores 1.0 offline,
    now arriving through the tool door.
    """
    out, raised = run([deliver(register=case()["register"]), submit()])
    problems = []
    if raised is not None:
        return check("golden route raised", False, str(raised))
    if out.get("reward") != 1.0 or out.get("error") is not None:
        problems.append(f"reward={out.get('reward')} error={out.get('error')}")
    if metric(out, env_mod.METRIC_LEDGER_SCORE) != 1.0:
        problems.append(f"piv/ledger_score {metric(out, env_mod.METRIC_LEDGER_SCORE)}")
    if metric(out, env_mod.METRIC_APPLICATION_SCORE) != 1.0:
        problems.append(f"piv/application_score {metric(out, env_mod.METRIC_APPLICATION_SCORE)}")
    if out.get("stop_condition") != "piv_submitted":
        problems.append(f"stop_condition {out.get('stop_condition')!r}")
    delivery, application = publication(out)
    one = canonical_decimal(D("1.000000"))
    if delivery.completion != "complete" or delivery.score != one:
        problems.append(f"delivery says {delivery.completion} / {delivery.score}")
    if application is None:
        problems.append("the publication carries no register block")
    else:
        if application.status != A.STATUS_DELIVERED or application.application_score != one:
            problems.append(f"the register block says {application.status} / {application.application_score}")
        if application.composite_score != one:
            problems.append(f"the composite in the register block is {application.composite_score}")
    # the receipt names BOTH bindings, and the register's is the accepted one
    if not any("cash application bound at" in t for t in tool_replies(out)):
        problems.append("the submit receipt does not name the bound register")
    if not any(t.endswith("cash application accepted: 3 receipts, 6 invoices, 1 credit notes")
               for t in tool_replies(out)):
        problems.append(f"the write reply is not the accepted one: {[t[-90:] for t in tool_replies(out)]}")
    return check("cash_application_001: golden ledger + golden register through evaluate -> reward 1.0, "
                 "complete, L = A = 1, and delivery.json says so", not problems, "\n".join(problems))


def test_a_submission_without_a_register_scores_zero_and_reports_the_ledger():
    """Legal, zero, and diagnostic — round 12 §2's ruling.

    The submission is accepted (the ledger is perfect), the composite reward
    is 0 because `A = 0`, `L` is reported on its own metric rather than
    credited, and the register's state is recorded as ABSENT rather than as
    a rejected artifact or an evaluator failure.
    """
    out, raised = run([deliver(register=None), submit()])
    problems = []
    if raised is not None:
        return check("ledger-only route raised", False, str(raised))
    if out.get("reward") != 0.0 or out.get("error") is not None:
        problems.append(f"reward={out.get('reward')} error={out.get('error')}")
    if metric(out, env_mod.METRIC_LEDGER_SCORE) != 1.0:
        problems.append(f"L was not reported diagnostically: {metric(out, env_mod.METRIC_LEDGER_SCORE)}")
    if metric(out, env_mod.METRIC_APPLICATION_SCORE) != 0.0:
        problems.append(f"piv/application_score {metric(out, env_mod.METRIC_APPLICATION_SCORE)}")
    if metric(out, env_mod.METRIC_SUBMITTED) != 1.0:
        problems.append("a submission without a register was not accepted")
    if metric(out, env_mod.METRIC_EVALUATOR_FAILED) != 0.0:
        problems.append("an absent register was recorded as an evaluator failure")
    if out.get("piv_submitted_application_phase") != env_mod.ApplicationPhase.NONE.value:
        problems.append(f"submit bound phase {out.get('piv_submitted_application_phase')!r}")
    if env_mod.APPLICATION_BOUND_ABSENT not in " ".join(tool_replies(out)):
        problems.append("the receipt does not say that no register was filed")
    delivery, application = publication(out)
    if delivery.completion != "incomplete":
        problems.append(f"delivery completion {delivery.completion!r}: the composite is not complete")
    if application is None or application.status != A.STATUS_ABSENT:
        problems.append(f"the register block is {application}")
    elif application.revision != 0 or application.artifact_stored_bytes_digest != env_mod.NO_ARTIFACT:
        problems.append(f"an absent register named a revision or an artifact: {application}")
    if (Path(out["workspace"]) / env_mod.APPLICATION_FILE).exists():
        problems.append("a register file exists although none was filed")
    return check("a submission with no register is legal: submitted, reward 0, A = 0 and APPLICATION_ABSENT, "
                 "with L reported diagnostically and no composite credit",
                 not problems, "\n".join(problems))


def test_a_stored_invalid_register_supersedes_an_accepted_one():
    """The lifecycle rule, exactly as specified: a STORED replacement
    supersedes unconditionally, an invalid one included. No fallback to the
    earlier accepted revision, phase REJECTED, `A = 0`."""
    out, raised = run([write_ledger(), write_register("a1", case()["register"]),
                       write_register("a2", case()["invalid"]), submit()])
    problems = []
    if raised is not None:
        return check("superseding route raised", False, str(raised))
    if out.get("reward") != 0.0 or out.get("error") is not None:
        problems.append(f"reward={out.get('reward')} error={out.get('error')}")
    if metric(out, env_mod.METRIC_LEDGER_SCORE) != 1.0 or metric(out, env_mod.METRIC_APPLICATION_SCORE) != 0.0:
        problems.append(f"L={metric(out, env_mod.METRIC_LEDGER_SCORE)} "
                        f"A={metric(out, env_mod.METRIC_APPLICATION_SCORE)}")
    if out.get("piv_application_revision") != 2:
        problems.append(f"the register is at revision {out.get('piv_application_revision')}, not 2")
    if out.get("piv_submitted_application_phase") != env_mod.ApplicationPhase.REJECTED.value:
        problems.append(f"submit bound phase {out.get('piv_submitted_application_phase')!r}")
    replies = tool_replies(out)
    if not any("\ncash application refused: application.row_identity" in t for t in replies):
        problems.append(f"the invalid write was not refused in words: {[t[-90:] for t in replies]}")
    if not any("refused by the register protocol" in t for t in replies):
        problems.append("the receipt does not say the bound register was refused")
    delivery, application = publication(out)
    if application is None or application.status != A.STATUS_REJECTED:
        problems.append(f"the register block is {application}")
    elif application.submitted_logical_text_digest != out.get("piv_application_digest"):
        problems.append("the published register block does not bind the rejected bytes")
    elif application.artifact_stored_bytes_digest != env_mod.NO_ARTIFACT:
        problems.append("a rejected register was published as an artifact")
    if (Path(out["workspace"]) / env_mod.APPLICATION_FILE).exists():
        problems.append("the rejected register was left at the public path")
    return check("a stored invalid register supersedes an accepted one: revision 2, phase REJECTED, A = 0, "
                 "reward 0, no fallback to the earlier accepted revision",
                 not problems, "\n".join(problems))


def test_an_over_envelope_request_leaves_the_previous_revision_intact():
    """Refused BEFORE storage, so nothing about the register moves: the
    revision, the phase and the bound digest are the accepted one's, and the
    episode still scores 1.0."""
    out, raised = run([write_ledger(), write_register("a1", case()["register"]),
                       write_register("a2", case()["oversize"]), submit()])
    problems = []
    if raised is not None:
        return check("over-envelope route raised", False, str(raised))
    if out.get("reward") != 1.0 or out.get("error") is not None:
        problems.append(f"reward={out.get('reward')} error={out.get('error')}")
    if env_mod.APPLICATION_TOO_LARGE not in tool_replies(out):
        problems.append(f"the oversize write was not refused: {tool_replies(out)[-2:]}")
    if out.get("piv_application_revision") != 1:
        problems.append(f"an unstored request advanced the revision to {out.get('piv_application_revision')}")
    if out.get("piv_submitted_application_phase") != env_mod.ApplicationPhase.CANDIDATE.value:
        problems.append(f"submit bound phase {out.get('piv_submitted_application_phase')!r}")
    if metric(out, env_mod.METRIC_APPLICATION_SCORE) != 1.0:
        problems.append(f"A={metric(out, env_mod.METRIC_APPLICATION_SCORE)} after an unstored request")
    stored = (Path(out["workspace"]) / env_mod.APPLICATION_FILE).read_bytes()
    if len(stored) > env_mod.APPLICATION_ENVELOPE_BYTES:
        problems.append("the oversize bytes reached the disk")
    return check("an over-envelope write_cash_application is refused before storage: the previous revision, "
                 "its phase and its digest are untouched and the episode still scores 1.0",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 2. the machinery those routes ride on
# --------------------------------------------------------------------------

def test_a_non_protocol_ending_scores_the_last_committed_revision_of_each():
    """The episode ends on the consecutive-no-tool limit, never on `submit`.

    Every non-protocol ending scores the LAST COMMITTED REVISION of each
    artifact — that is the ledger's rule, and the family has to hold it for
    two artifacts or an agent that runs out of turns loses a register it had
    already filed.
    """
    turns = [deliver(register=case()["register"])] + [narrated()] * env_mod.MAX_CONSECUTIVE_NO_TOOL_TURNS
    out, raised = run(turns)
    problems = []
    if raised is not None:
        return check("the no-tool-limit route raised", False, str(raised))
    if metric(out, env_mod.METRIC_NO_TOOL_LIMIT) != 1.0:
        problems.append("the episode did not end on the no-tool limit")
    if metric(out, env_mod.METRIC_SUBMITTED) != 0.0:
        problems.append("the episode ended by submit; the witness is about the other endings")
    if out.get("reward") != 1.0:
        problems.append(f"reward {out.get('reward')}: a non-protocol ending lost a committed artifact")
    if metric(out, env_mod.METRIC_LEDGER_SCORE) != 1.0 or metric(out, env_mod.METRIC_APPLICATION_SCORE) != 1.0:
        problems.append(f"L={metric(out, env_mod.METRIC_LEDGER_SCORE)} "
                        f"A={metric(out, env_mod.METRIC_APPLICATION_SCORE)}")
    delivery, application = publication(out)
    if delivery.completion != "complete" or application is None or application.status != A.STATUS_DELIVERED:
        problems.append(f"the publication is {delivery.completion} / {application}")
    return check("a non-protocol ending (the consecutive-no-tool limit) scores the last committed revision of "
                 "EACH artifact: reward 1.0 with no submit at all", not problems, "\n".join(problems))


def test_score_core_composes_and_publish_writes_the_canonical_register():
    """`score_core` returns `L x A`, and `_publish` writes the CANONICAL
    register plus both of its digests into `delivery.json`.

    Canonical, not the agent's bytes: the register on disk beside the score
    is the document `application/1` actually read — applications summed by
    invoice, records in id order — so a reader cannot be shown a formatting
    of the answer that differs from the scored one. The legacy manifest is
    unchanged, which the last arm asserts from the other side.
    """
    problems = []
    # the agent's own formatting: the same accounting, split into two
    # entries naming one invoice, which canonicalisation sums
    golden = json.loads(case()["register"])
    receipt = golden["receipts"][0]
    first = receipt["applied"][0]
    receipt["applied"] = ([{"invoice_id": first["invoice_id"], "amount": "1000.00"},
                           {"invoice_id": first["invoice_id"],
                            "amount": f"{float(first['amount']) - 1000:.2f}"}]
                          + receipt["applied"][1:])
    out, raised = run([deliver(register=json.dumps(golden)), submit()])
    if raised is not None:
        return check("the canonicalisation route raised", False, str(raised))
    if out.get("reward") != 1.0:
        problems.append(f"splitting one application into two changed the answer: reward {out.get('reward')}")
    workspace = Path(out["workspace"])
    stored = (workspace / env_mod.APPLICATION_FILE).read_bytes()
    parsed = A.parse_application(json.dumps(golden), case()["truth"])
    expected = A.canonical_text(parsed).encode("utf-8")
    if stored != expected:
        problems.append("the published register is not the canonical document the scorer read")
    delivery, application = publication(out)
    digests = env_mod.digests_of(stored)
    if application.artifact_stored_bytes_digest != digests["stored_bytes_digest"] \
            or application.artifact_logical_text_digest != digests["logical_text_digest"]:
        problems.append("delivery.json does not carry both digests of the published register")
    if application.canonical_digest != parsed.canonical_digest:
        problems.append("delivery.json does not carry application/1's canonical document digest")
    if application.submitted_logical_text_digest == application.artifact_logical_text_digest:
        problems.append("the submitted and canonical digests coincide; this fixture must differ in formatting")
    # score_core composes: the recorded result is the composite, and its two
    # halves are the engines the contract names
    if delivery.score != application.composite_score:
        problems.append("the receipt's score and the composite in the register block disagree")
    if delivery.score_result_digest != application.composite_result_digest:
        problems.append("the receipt's result digest is not the composite's")
    # ...and the LEGACY manifest is exactly what it was: no register member
    legacy_out, legacy_raised = run([calls(("w", "write_ledger",
                                            {"content": (ROOT / "tests" / "solutions" /
                                                         "golden.beancount").read_text(encoding="utf-8")})),
                                     submit()], task_id="bank_recon_001")
    if legacy_raised is not None:
        problems.append(f"the legacy route raised {type(legacy_raised).__name__}")
    else:
        text = (Path(legacy_out["workspace"]) / env_mod.PUBLICATION_FILE).read_text(encoding="utf-8")
        legacy_delivery, legacy_application = env_mod._read_publication(text)
        if legacy_application is not None:
            problems.append("a legacy rollout published a register block")
        if text != legacy_delivery.to_json():
            problems.append("the legacy publication manifest is no longer DeliveryReceipt.to_json() byte for byte")
    return check("score_core composes L x A and _publish writes the CANONICAL register with both its digests "
                 "into delivery.json; the legacy manifest keeps its exact bytes",
                 not problems, "\n".join(problems))


def test_the_malformed_call_path_covers_the_seventh_tool_unchanged():
    """Contract 4's malformed-call path — `bind`, the type check,
    `PUBLIC_TOOL_ERROR` — covers `write_cash_application` with no new code.

    Three misuses, one answer each, nothing stored and no revision: arguments
    that are not a JSON object at all, an unknown argument name (`bind`), and
    an argument of the wrong type (the annotation check). The fourth arm is
    the one that says the tool is genuinely off the legacy surface.
    """
    problems = []
    for label, arguments in (("not JSON", "{not json"),
                             ("unknown argument", {"register": "{}"}),
                             ("wrong type", {"content": 5})):
        out, raised = run([calls(("m", "write_cash_application", arguments)), submit()])
        if raised is not None:
            problems.append(f"{label}: raised {type(raised).__name__}")
            continue
        replies = tool_replies(out)
        if env_mod.PUBLIC_TOOL_ERROR not in replies:
            problems.append(f"{label}: answered {replies[:1]}, not PUBLIC_TOOL_ERROR")
        if out.get("piv_application_revision") != 0:
            problems.append(f"{label}: a malformed call advanced the register revision")
        if out.get("piv_application_phase") != env_mod.ApplicationPhase.NONE.value:
            problems.append(f"{label}: a malformed call moved the register phase")
        if out.get("error") is not None:
            problems.append(f"{label}: recorded as our failure: {out.get('error')}")
    # the seventh tool is not on the legacy surface, so a legacy episode that
    # names it gets the same refusal as any name the environment never had
    out, raised = run([calls(("m", "write_cash_application", {"content": "{}"}))],
                      task_id="bank_recon_001")
    if raised is not None:
        problems.append(f"legacy: raised {type(raised).__name__}")
    elif env_mod.PUBLIC_TOOL_ERROR not in tool_replies(out):
        problems.append(f"legacy: answered {tool_replies(out)[:1]}, not PUBLIC_TOOL_ERROR")
    return check("contract 4's malformed-call path covers the seventh tool unchanged: malformed arguments, an "
                 "unknown name and a wrong-typed value are each PUBLIC_TOOL_ERROR with nothing stored, and "
                 "the tool is absent from the legacy surface", not problems, "\n".join(problems))


def test_two_register_writes_in_one_turn_are_refused_per_tool():
    """One call per WRITE TOOL per turn, counted per tool: a doubled
    `write_cash_application` answers TURN_MULTI_APPLICATION (not the
    ledger's TURN_MULTI_WRITE) and the whole turn executes nothing."""
    out, raised = run([calls(("a1", "write_cash_application", {"content": case()["register"]}),
                             ("a2", "write_cash_application", {"content": case()["invalid"]})),
                       deliver(register=case()["register"]), submit()])
    problems = []
    if raised is not None:
        return check("the doubled-register route raised", False, str(raised))
    replies = tool_replies(out)
    if replies[:2] != [env_mod.TURN_MULTI_APPLICATION, env_mod.TURN_MULTI_APPLICATION]:
        problems.append(f"the doubled turn was answered {replies[:2]}")
    if env_mod.TURN_MULTI_WRITE in replies:
        problems.append("the register's double was answered with the ledger's refusal")
    if out.get("reward") != 1.0:
        problems.append(f"the recovery turn did not deliver: reward {out.get('reward')}")
    if out.get("piv_application_revision") != 1:
        problems.append(f"the refused turn stored something: revision {out.get('piv_application_revision')}")
    return check("two write_cash_application calls in one turn are refused with TURN_MULTI_APPLICATION, the "
                 "turn executes nothing, and the next turn delivers normally",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_golden_ledger_and_register_score_one_and_complete,
    test_a_submission_without_a_register_scores_zero_and_reports_the_ledger,
    test_a_stored_invalid_register_supersedes_an_accepted_one,
    test_an_over_envelope_request_leaves_the_previous_revision_intact,
    test_a_non_protocol_ending_scores_the_last_committed_revision_of_each,
    test_score_core_composes_and_publish_writes_the_canonical_register,
    test_the_malformed_call_path_covers_the_seventh_tool_unchanged,
    test_two_register_writes_in_one_turn_are_refused_per_tool,
]


def run_suite() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run_suite())
