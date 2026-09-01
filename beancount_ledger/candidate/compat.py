"""ARCHIVED COMPATIBILITY DOOR. Not production.

Builds `ContractInputs` from the archived task-file shape (a dict of
literal balances and posting tuples plus the original ledger text) so the
initialisation audits in `load_contract` can be exercised with malformed
inputs the projector would refuse to mint, and so the old-versus-new
comparison can run the archived fixture through the same scorer.

`test_entrypoints` asserts that no production module imports this module
or the literal mint it calls. If you find yourself wanting it outside a
test, the graph is missing a fact and this is the wrong fix.
"""

from __future__ import annotations

from decimal import Decimal

from ..graph.derive import ContractInputs, PlantedSpec, TrapSpec, _archived_literal_inputs
from ..graph.project import Period
from .canonical import canonical_decimal


def contract_inputs_from_task(task: dict, original_text: str) -> ContractInputs:
    planted = tuple(PlantedSpec(
        str(item["id"]), f"archived:{item['id']}", item.get("date"),
        tuple(sorted((a, canonical_decimal(Decimal(v))) for a, v in item["required_postings"])),
        tuple(item.get("must_be_payee", [])), str(item.get("narration", "")), ("archived",), "archived task file",
        residual=tuple((a, Decimal(v)) for a, v in item["required_postings"]))
        for item in task.get("planted", []))
    traps = tuple(TrapSpec(str(t["id"]), "archived", "archived", "", "", Decimal("0"), t.get("narration", ""))
                  for t in task.get("traps", []))
    return _archived_literal_inputs(
        task_id=str(task.get("id", "")), task_type=str(task.get("type", "")), prompt=str(task.get("prompt", "")),
        period=Period("", str(task.get("period_end", "")), ""), world_id="archived", currency="USD",
        scored_accounts=tuple(task.get("scored_accounts", [])),
        expected_balances=tuple((a, Decimal(v)) for a, v in task.get("expected_balances", {}).items()),
        allowed_accounts=tuple(task.get("allowed_accounts", [])),
        planted=planted, traps=traps, original_text=original_text, golden_text="",
        statement_closing=Decimal(task.get("statement_closing_balance", "0")),
        graph_digest="archived", mutation_plan_digest="archived", view_digests=(), public_files=(),
    )
