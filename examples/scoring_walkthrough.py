"""Inspect the current scorer on a reference solution, without calling a model.

Run from an installed repository checkout:
    python examples/scoring_walkthrough.py
    python examples/scoring_walkthrough.py --task cash_application_001 --json

The ledger comes from the task's reference solution. The application register
is reconstructed from its public input files. This is an evaluator walkthrough,
not an agent rollout, benchmark result, or independent accounting validation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from beancount_ledger import beancount_ledger as environment_module
from beancount_ledger.candidate import application, committed, composite
from beancount_ledger.candidate.normalise import Accepted, parse_once
from beancount_ledger.graph import cash_application
from beancount_ledger.graph.derive import derive_contract
from beancount_ledger.graph.worlds import CASH_APPLICATION_REGISTRY


def evaluate(task_id: str) -> dict:
    world, task = CASH_APPLICATION_REGISTRY[task_id]
    _bundle, inputs = derive_contract(world, task)
    environment = committed.load_contract(inputs)

    reference_text = inputs.golden_text
    parsed = parse_once(reference_text)
    if not isinstance(parsed, Accepted) or not parsed.domain_valid:
        raise RuntimeError("The reference ledger did not pass the parse boundary.")
    receipt = committed.new_receipt(
        "scoring-walkthrough", 1,
        environment_module.digests_of(reference_text.encode("utf-8"), submitted=reference_text),
    )
    ledger = committed.score_committed(committed.commit(parsed, environment, receipt))

    public = {name: data.decode("utf-8") for name, data in inputs.public_files}
    register_text = cash_application.document_text(cash_application.fold(
        public, period_start=task.period.start, period_end=task.period.end,
    ))
    register = application.score_application(
        application.parse_application(register_text, inputs.application),
        inputs.application, expected_balances=environment.expected_balances,
    )
    result = composite.compose(ledger, register)
    for outcome in (ledger, register, result):
        outcome.verify()
    if not result.complete or result.total != 1:
        raise RuntimeError("The reference solution did not complete the task.")

    return {
        "kind": "reference-solution walkthrough; no agent or model run",
        "task": task_id,
        "public_files": sorted(public),
        "engines": list(result.engines),
        "ledger": {
            "score": str(ledger.total),
            "criteria": {name: str(value) for name, value in ledger.components},
            "findings": {name: len(getattr(ledger, name)) for name in (
                "target_misses", "unresolved_planted", "collateral_damage",
                "removed_or_altered", "fabricated", "merged_events",
                "undocumented", "plug_accounts", "blocked_by",
            )},
            "complete": ledger.complete,
        },
        "application": {
            "score": str(register.total),
            "criteria": {name: str(value) for name, value in register.components},
            "penalties": [list(item) for item in register.penalties],
            "ties": dict(register.tie_states),
        },
        "total": str(result.total),
        "complete": result.complete,
        "result_digest": result.result_digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=sorted(CASH_APPLICATION_REGISTRY), default="cash_application_006")
    parser.add_argument("--json", action="store_true", help="print the full structured result")
    args = parser.parse_args()
    result = evaluate(args.task)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"beancount-ledger | {result['task']}")
    print("Reference-solution walkthrough. No model call or agent rollout.\n")
    print(f"INPUT: {len(result['public_files'])} public accounting files")
    print("DELIVERABLES: reference ledger + register folded from public evidence\n")
    print("LEDGER CRITERIA")
    for name, value in result["ledger"]["criteria"].items():
        print(f"  {name:24s} {value}")
    for name, value in result["ledger"]["findings"].items():
        print(f"  {name:24s} {value} findings")
    print("\nAPPLICATION CRITERIA")
    for name, value in result["application"]["criteria"].items():
        print(f"  {name:24s} {value}")
    for name, value in result["application"]["ties"].items():
        print(f"  {name:24s} {value}")
    print(f"  penalties                {len(result['application']['penalties'])}")
    print(f"\nRESULT: L={result['ledger']['score']} x A={result['application']['score']}")
    print(f"        total={result['total']} | complete={result['complete']}")
    print("\nScoring executed locally; all result digests verified.")
    print("A reference acceptance check is not a model-performance measurement.")


if __name__ == "__main__":
    main()
