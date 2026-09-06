"""The DETERMINISTIC LIVENESS WITNESS.

    python tests/liveness_witness.py                       # the six confirm1 panel selectors
    python tests/liveness_witness.py --sentinels           # + the pinned structural sentinel set
    python tests/liveness_witness.py --selectors train:1 eval:5

A stochastic model rollout measures DELIVERY BEHAVIOUR: whether a particular
model, on a particular day, finds the repairs. It is a bad instrument for the
question "does the environment work at all" — a run of zeros is equally
consistent with a broken episode contract and with four models that cannot do
bookkeeping, and the pilot's zero-delivery cells could not tell those apart.

This witness answers only the environment question, and answers it
deterministically. For each selector it drives a SCRIPTED CONFORMING AGENT
through the real `env.evaluate()` door:

    list_files -> read_file(ledger) -> write_ledger(golden) -> submit

and asserts, from the environment's own state and the scorer's own receipt:

  * reward 1.0 and the scorer's `complete` flag — the golden text scores;
  * `piv_submitted` (the TERMINAL phase) — submit really ends the episode;
  * the delivered artifact's digests match `delivery.json`, bound from THIS
    rollout's own workspace (`measure_budget.bind_artifact`);
  * turns, output tokens, observation bytes and the write payload are all
    inside the contract's DECLARED envelopes, each compared against the
    package's own constant rather than a number repeated here;
  * two runs of the same script produce the SAME artifact digests — the
    environment is deterministic given a deterministic agent.

The golden text comes from the graph exactly as `tests/score_payload.py`
takes it (`mint(namespace, index, profile).inputs.golden_text`), so no ledger
is authored here.

NO LIVE API CALL. No provider, no key, no network. By default the witness
runs under the suites' own fixed test secret, which is what makes it part of
`tests/run_all.py`; `--production` leaves the secret to the evaluator's own
resolution so the same script can witness the worlds a release actually
serves.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

#: The suites' own fixed development secret (never the evaluator's). Set
#: BEFORE the package is imported: `load_environment` resolves the secret at
#: call time, but the rotation/manifest logic reads the environment early.
TEST_SECRET = "5f1c7b9e2a4d6c8b0e1f3a5c7d9b2e4f6a8c0d2e4f6a8b0c1d3e5f7a9b1c3d5e"  # gitleaks:allow  (a public test constant, not a credential: determinism compares runs under one key)

#: The `confirm1` panel — the six selectors the confirmatory schedule runs.
PANEL_SELECTORS = ("train:1", "train:12", "train:30", "eval:5", "train:3:hard", "train:107:hard")


def _configure_secret(production: bool) -> None:
    if production:
        # A witness that says PRODUCTION must run under the evaluator's own key
        # and the release manifest. Anything already in the environment would
        # silently make it something else, so it is refused rather than ignored.
        loud = [name for name in ("PIV_EVAL_SECRET", "PIV_DEV_UNMANIFESTED") if os.environ.get(name)]
        if loud:
            raise SystemExit(f"--production with {', '.join(loud)} set: unset them, or drop --production. "
                             "A witness cannot claim the production door while a test key or the development "
                             "route is in force.")
        return
    os.environ.setdefault("PIV_EVAL_SECRET", TEST_SECRET)
    os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")


def pinned_sentinels() -> list:
    """The pinned structural sentinels, READ from tests/test_sentinels.py rather
    than imported: importing that module installs the suites' test secret and
    the development route at import time, which would turn a --production run
    into a test-secret run without saying so."""
    import ast

    source = (Path(__file__).resolve().parent / "test_sentinels.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "SENTINELS" for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise SystemExit("tests/test_sentinels.py no longer defines SENTINELS")


def golden_text_for(selector: str) -> str:
    """The golden ledger for a generated selector, taken from the graph the
    way `tests/score_payload.py` takes it — minted, never authored."""
    from beancount_ledger.graph.generate import DEFAULT_PROFILE, HARD_PROFILE
    from beancount_ledger.graph.mint import mint
    namespace, index, *rest = selector.split(":")
    profile = HARD_PROFILE if rest and rest[0] == "hard" else DEFAULT_PROFILE
    return mint(namespace, int(index), profile).inputs.golden_text


def conforming_script(env_mod, golden: str):
    """`list_files -> read_file(ledger) -> write_ledger(golden) -> submit` as
    scripted assistant turns. The tool NAMES come from the package's own
    public tool tuple, so a renamed tool breaks this witness rather than
    silently making it test nothing."""
    import test_episode_contract as tec
    names = {tool.__name__ for tool in env_mod.PUBLIC_TOOLS}
    for required in ("list_files", "read_file", "write_ledger", "submit"):
        if required not in names:
            raise SystemExit(f"the package no longer exposes a {required!r} tool: {sorted(names)}")
    return [tec.calls(("l1", "list_files", {})),
            tec.calls(("r1", "read_file", {"path": env_mod.LEDGER})),
            tec.calls(("w1", "write_ledger", {"content": golden})),
            tec.calls(("s1", "submit", {}))]


STATE_COLUMNS = ["workspace", "piv_rollout_id", "piv_revision", "piv_phase", "piv_score",
                 "piv_submitted_text_digest", "piv_logical_text_digest", "piv_stored_bytes_digest",
                 "piv_complete_reads", "piv_observation_bytes", "piv_episode_contract_digest"]

#: Completion tokens the scripted agent REPORTS per turn. `TurnScript` alone
#: reports `usage=None`, so the framework summed zero and the output-token
#: envelope check compared 0 against 40,000 — a bound that could never fail
#: is not a bound (adversarial-review finding F3). A conforming agent's four
#: turns are dominated by the `write_ledger` argument, so a per-turn figure
#: in the low thousands is the realistic shape; the assertion is that the
#: SUM lands inside the package's own declared ceiling, and the witness's own
#: test tightens the ceiling to prove the comparison bites.
SCRIPTED_COMPLETION_TOKENS = 2_000


def usage_reporting_script(turns, completion_tokens: int = SCRIPTED_COMPLETION_TOKENS):
    """`TurnScript` that reports a real `Usage` per turn, so `token_usage`
    carries a non-zero output-token sum for the envelope check to bind on."""
    import test_episode_contract as tec
    from verifiers.legacy.types import Response, Usage

    class _UsageScript(tec.TurnScript):
        async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
            self.turn += 1
            message = (self.turns[self.turn - 1] if self.turn <= len(self.turns) else tec.empty())
            usage = Usage(prompt_tokens=10, reasoning_tokens=0, completion_tokens=completion_tokens,
                          total_tokens=10 + completion_tokens)
            return Response(id=f"scripted-{self.turn}", created=0, model=model, usage=usage,
                            message=message)

    return _UsageScript(turns)


def one_witness(selector: str, env_mod) -> dict:
    """One scripted rollout through the real door. Returns the observed
    facts; the assertions live in `check_envelopes` so the two runs of a
    determinism pair are compared on identical evidence."""
    import measure_budget as mb

    golden = golden_text_for(selector)
    env = env_mod.load_environment(selector)
    client = usage_reporting_script(conforming_script(env_mod, golden))
    results = asyncio.run(env.evaluate(client=client, model="scripted-conforming", num_examples=1,
                                       rollouts_per_example=1, max_concurrent=1, save_results=False,
                                       state_columns=list(STATE_COLUMNS)))
    out = results["outputs"][0]
    metrics = out.get("metrics") or {}
    usage = out.get("token_usage") or {}
    artifact = mb.bind_artifact(out, env_mod)
    tools = mb.tool_names(out.get("completion") or [])
    return {
        "selector": selector,
        "task_id": env.dataset[0]["info"]["task_id"] if len(env.dataset) else None,
        "reward": out.get("reward"),
        "stop": out.get("stop_condition"),
        "error": out.get("error"),
        "phase": out.get("piv_phase"),
        "submitted": artifact.get("submitted"),
        "artifact": artifact.get("artifact"),
        "artifact_reason": artifact.get("artifact_reason"),
        "artifact_stored_bytes_digest": artifact.get("artifact_stored_bytes_digest"),
        "artifact_logical_text_digest": artifact.get("artifact_logical_text_digest"),
        "episode_contract_digest": out.get("piv_episode_contract_digest"),
        "turns": metrics.get("num_turns", len(out.get("trajectory") or [])),
        "tools": tools,
        "output_tokens": usage.get("output_tokens", usage.get("completion_tokens")) or 0,
        "observation_bytes": out.get("piv_observation_bytes"),
        "complete_reads": out.get("piv_complete_reads"),
        "golden_bytes": len(golden.encode("utf-8")),
        "score": out.get("piv_score"),
    }


def check_envelopes(observed: dict, env_mod) -> list[str]:
    """Every declared envelope, each compared against the PACKAGE's own
    constant. A number repeated in a test is a second source of truth that
    can drift; these cannot."""
    problems = []
    if observed["reward"] != 1.0:
        problems.append(f"reward {observed['reward']!r}, expected 1.0 — the golden text must score")
    if observed["error"]:
        problems.append(f"the rollout recorded an error: {observed['error']}")
    if not observed["submitted"] or observed["phase"] != env_mod.EpisodePhase.TERMINAL.value:
        problems.append(f"phase {observed['phase']!r} / submitted {observed['submitted']!r} — submit must "
                        f"end the episode in the TERMINAL phase")
    if observed["stop"] != "piv_submitted":
        problems.append(f"stop condition {observed['stop']!r}, expected piv_submitted")
    if observed["artifact"] != "BOUND":
        problems.append(f"artifact {observed['artifact']}/{observed['artifact_reason']}, expected BOUND — "
                        f"the delivered ledger must match delivery.json's own digests")
    for field in ("artifact_stored_bytes_digest", "artifact_logical_text_digest"):
        if not observed.get(field):
            problems.append(f"{field} is missing from the bound artifact")
    if observed["tools"] != ["list_files", "read_file", "write_ledger", "submit"]:
        problems.append(f"the executed tool sequence was {observed['tools']}, not the conforming script")
    if observed["turns"] > env_mod.MAX_TURNS - 1:
        problems.append(f"turns {observed['turns']} exceeds the last executable turn "
                        f"{env_mod.MAX_TURNS - 1}")
    if not observed["output_tokens"]:
        # A bound that cannot fail is not a bound: `TurnScript` reported no
        # usage at all, so the framework summed zero and this check compared
        # 0 against 40,000 forever (F3). The scripted client reports a real
        # `Usage`; a zero here means it stopped doing so.
        problems.append(f"output tokens {observed['output_tokens']!r} — the scripted client reported no "
                        f"usage, so the output-token envelope is vacuous")
    elif observed["output_tokens"] > env_mod.MAX_EPISODE_OUTPUT_TOKENS:
        problems.append(f"output tokens {observed['output_tokens']} exceed the episode ceiling "
                        f"{env_mod.MAX_EPISODE_OUTPUT_TOKENS}")
    observation = observed["observation_bytes"]
    if not isinstance(observation, int):
        # Silence used to pass: an absent counter skipped the check entirely.
        # The package counts observation bytes on every episode, so `None` is
        # a package/instrument failure, not an exemption from the envelope.
        problems.append(f"observation bytes are {observation!r}: the aggregate observation counter is "
                        f"missing, so its envelope was never checked")
    elif observation > env_mod.MAX_EPISODE_OBSERVATION_BYTES:
        problems.append(f"observation bytes {observation} exceed the aggregate budget "
                        f"{env_mod.MAX_EPISODE_OBSERVATION_BYTES}")
    if not isinstance(observed.get("complete_reads"), int) or observed["complete_reads"] < 1:
        problems.append(f"complete ledger reads {observed.get('complete_reads')!r}: the conforming script "
                        f"reads the ledger once, so the counter must record at least one")
    if observed["golden_bytes"] > env_mod.MAX_WRITE_BYTES:
        problems.append(f"the golden text is {observed['golden_bytes']} bytes, over MAX_WRITE_BYTES "
                        f"{env_mod.MAX_WRITE_BYTES} — this world cannot be delivered at all")
    return problems


DETERMINISTIC_FIELDS = ("task_id", "reward", "stop", "phase", "artifact",
                        "artifact_stored_bytes_digest", "artifact_logical_text_digest",
                        "episode_contract_digest", "turns", "tools", "score")


def compare_runs(first: dict, second: dict) -> list[str]:
    """The environment must answer a deterministic agent identically twice.
    Workspace paths and rollout ids differ by construction and are excluded;
    everything the experiment reads is compared."""
    problems = []
    for field in DETERMINISTIC_FIELDS:
        if first.get(field) != second.get(field):
            problems.append(f"{field}: {first.get(field)!r} then {second.get(field)!r}")
    return problems


def witness_selector(selector: str, env_mod, runs: int = 2) -> dict:
    observations = [one_witness(selector, env_mod) for _ in range(runs)]
    problems = []
    for index, observed in enumerate(observations):
        problems += [f"run {index + 1}: {p}" for p in check_envelopes(observed, env_mod)]
    if len(observations) > 1:
        problems += [f"NOT DETERMINISTIC — {p}" for p in compare_runs(observations[0], observations[1])]
    return {"selector": selector, "ok": not problems, "problems": problems,
            "observed": observations[0], "runs": len(observations)}


def main() -> int:
    parser = argparse.ArgumentParser(description="deterministic conforming-agent liveness witness")
    parser.add_argument("--selectors", nargs="+", default=None,
                        help=f"defaults to the confirm1 panel: {' '.join(PANEL_SELECTORS)}")
    parser.add_argument("--sentinels", action="store_true",
                        help="also witness the pinned structural sentinel set (tests/test_sentinels.py)")
    parser.add_argument("--runs", type=int, default=2,
                        help="rollouts per selector; 2 (the default) is what proves determinism")
    parser.add_argument("--production", action="store_true",
                        help="do NOT set the suites' test secret: witness the worlds the evaluator's own "
                             "key and release manifest actually serve")
    parser.add_argument("--json", default=None, help="also write the observations to this path")
    args = parser.parse_args()

    _configure_secret(args.production)
    from beancount_ledger import beancount_ledger as env_mod

    selectors = list(args.selectors or PANEL_SELECTORS)
    if args.sentinels:
        sentinels = [s for s in pinned_sentinels() if s not in selectors]
        if args.production:
            # The sentinels are chosen under the SUITES' key, from a pool wider
            # than the released population; under the evaluator's key they name
            # other worlds, and one outside the preflighted range is not in the
            # manifest at all. Witnessing them here would witness nothing.
            print(f"--production: the {len(sentinels)} pinned sentinels are chosen under the test key and "
                  f"are not part of the released population; they are skipped. Run without --production to "
                  f"witness them, or pass them to --selectors deliberately.\n")
        else:
            selectors += sentinels

    print(f"deterministic liveness witness: {len(selectors)} selector(s) x {args.runs} run(s), "
          f"{'PRODUCTION' if args.production else 'test'} secret, no live API call")
    print(f"envelopes: MAX_TURNS {env_mod.MAX_TURNS}, output ceiling "
          f"{env_mod.MAX_EPISODE_OUTPUT_TOKENS:,}, observation budget "
          f"{env_mod.MAX_EPISODE_OBSERVATION_BYTES:,} bytes, write cap {env_mod.MAX_WRITE_BYTES:,} bytes\n")

    results = []
    for selector in selectors:
        result = witness_selector(selector, env_mod, args.runs)
        results.append(result)
        observed = result["observed"]
        print(f"{'PASS' if result['ok'] else 'FAIL'}  {selector:18s} reward {observed['reward']} "
              f"turns {observed['turns']} obs {observed['observation_bytes']} "
              f"artifact {observed['artifact']} digest "
              f"{str(observed['artifact_logical_text_digest'])[:12]}...")
        for problem in result["problems"]:
            print(f"        {problem}")

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
        print(f"\nwrote {args.json}")

    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)} of {len(results)} selectors witnessed: a conforming agent "
          f"reads, writes the golden ledger, submits, scores 1.0 and terminates inside every declared "
          f"envelope, identically across {args.runs} runs")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
