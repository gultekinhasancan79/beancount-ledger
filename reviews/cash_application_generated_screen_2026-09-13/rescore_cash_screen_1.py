"""Rescore cash-application screen 1 from the recovered bytes, and execute the
two counterfactuals.

    .venv/Scripts/python.exe reviews/cash_application_generated_screen_2026-09-13/rescore_cash_screen_1.py

WHY. round18.answer.md:69-71: the earlier counterfactual record held only
missing ids, amounts and before/after totals, so "adding only these rows
changed nothing else and removed every penalty" could not be certified from
the archive. This script recovers the delivered bytes, writes the corrected
bytes and the exact diff, and runs the SHIPPED `application/1` over both,
publishing the whole decomposition rather than a total.

POST-RUN ANALYSIS. Every decomposition here was computed after the fact. The
live diagnostic capture failed on all nine rows with

    AttributeError: 'CompositeOutcome' object has no attribute 'components'

so no breakdown was archived, and nothing in this file is a live observation.
What IS live is each row's reward, `piv/ledger_score`, `piv/application_score`
and each workspace's delivery receipt; those are read, never rewritten.

THE PIN. The truth register is reconstructed by `tests/observed_truth.py`
from public evidence (see its docstring), because the generated population is
keyed and this analysis does not read the evaluator secret. The
reconstruction is not asked to be believed: `application/1` stamps each
outcome with a domain-separated digest over the ENTIRE decomposition, and
this script requires that digest to equal the one the live run wrote into the
workspace's delivery receipt, for all nine cells. It also requires each
recovered file's stored-bytes and logical-text digests to equal the ones the
result row recorded.

WHAT CANNOT BE DONE HERE. `candidate/1` needs the keyed golden ledger, so `L`
is NOT recomputed; the live figure is carried and labelled. The composite is
therefore reported as the shipped product rule applied to a live `L` and a
recomputed `A`, not as a full replay of `composite/1`.

Nothing observed is written. The corrected documents are NEW files beside the
delivered ones.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import observed_truth as OT                                        # noqa: E402
from beancount_ledger import beancount_ledger as env_mod           # noqa: E402
from beancount_ledger.candidate import composite as X              # noqa: E402
from beancount_ledger.candidate import application as A            # noqa: E402

ROWS = ROOT / "reviews/budget_qwen3.7-max-2026-05-20_2026-09-13_cash_screen_1.json"
SELECTION = ROOT / "reviews/cash_screen_1_selection_2026-09-13.json"
WORKSPACES = HERE / "workspaces"
COUNTERFACTUAL = HERE / "counterfactual"
OUT = HERE / "rescore_cash_screen_1.json"

#: The two application-only partials. Everything about the correction — which
#: rows, whose customer, at what basis — is read out of the reconstructed
#: truth register, so nothing is typed in here but the cells' names.
PARTIALS = ("ar-tenterhook_24_a", "ar-tenterhook_22_a")


def workspace_key(selector: str) -> str:
    _prefix, _population, template, index, variant = selector.split(":")
    return f"{template}_{index}_{variant}"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def missing_rows(outcome, truth) -> list[dict]:
    """The truth's own rows for the invoices the submission left out, in the
    delivered document's key order."""
    absent = sorted(i for i, state in outcome.invoice_states if state is A.INVOICE_MISSING)
    rows = []
    for invoice_id in absent:
        row = truth.row(invoice_id)
        rows.append({"invoice_id": row[0], "customer": row[1], "period_basis": str(row[2]),
                     "applied_total": str(row[3]), "credited": str(row[4]),
                     "written_off": str(row[5]), "remaining": str(row[6])})
    return rows


def main() -> int:
    problems: list[str] = []
    rows = json.loads(ROWS.read_text(encoding="utf-8"))
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    order = selection["execution_order"]
    if [r["selector"] for r in rows] != order[:9]:
        problems.append("the nine rows are not the first nine of the frozen execution order")

    cells, counterfactuals = [], []
    for index, row in enumerate(rows):
        selector = row["selector"]
        key = workspace_key(selector)
        workspace = WORKSPACES / key
        application_raw = (workspace / "cash_application.json").read_bytes()
        ledger_raw = (workspace / "ledger.beancount").read_bytes()
        receipt = json.loads((workspace / "delivery.json").read_text(encoding="utf-8"))

        # 1. the recovered bytes ARE the delivered bytes
        app_d, led_d = env_mod.digests_of(application_raw), env_mod.digests_of(ledger_raw)
        bindings = {
            "application_stored_bytes_digest": app_d["stored_bytes_digest"] == row["application_stored_bytes_digest"],
            "application_logical_text_digest": app_d["logical_text_digest"] == row["application_logical_text_digest"],
            "ledger_stored_bytes_digest": led_d["stored_bytes_digest"] == row["artifact_stored_bytes_digest"],
            "ledger_logical_text_digest": led_d["logical_text_digest"] == row["artifact_logical_text_digest"],
            "receipt_agrees_with_row": (receipt["application"]["artifact_stored_bytes_digest"]
                                        == row["application_stored_bytes_digest"]),
        }
        for name, ok in bindings.items():
            if not ok:
                problems.append(f"{key}: {name} does not bind")

        # 2. the shipped scorer, over the reconstructed truth
        _parsed, outcome, truth, expected_balances, provenance = OT.score(workspace)
        pinned = {
            "application_result_digest": outcome.result_digest == receipt["application"]["application_result_digest"],
            "canonical_digest": outcome.application_digest == receipt["application"]["canonical_digest"],
            "application_score": str(outcome.total).rstrip("0").rstrip(".")
            == receipt["application"]["application_score"].rstrip("0").rstrip("."),
        }
        for name, ok in pinned.items():
            if not ok:
                problems.append(f"{key}: the rescore does not reproduce the live {name}")

        live_ledger = row["metrics"]["piv/ledger_score"]
        live_application = row["metrics"]["piv/application_score"]
        composite_total = X._scale(Decimal(str(live_ledger)) * outcome.total)
        if composite_total != Decimal(str(row["reward"])):
            problems.append(f"{key}: L x A = {composite_total}, the row's reward {row['reward']}")

        cells.append({
            "planned_ordinal": index + 1,
            "selector": selector,
            "workspace": f"workspaces/{key}",
            "task_id": row["task_id"],
            "bindings": bindings,
            "pinned_against_live_delivery_receipt": pinned,
            "live": {"reward": row["reward"], "piv/ledger_score": live_ledger,
                     "piv/application_score": live_application,
                     "breakdown": row["breakdown"],
                     "note": "the live breakdown is the failure the ruling names; it is quoted, not repaired"},
            "application_decomposition": OT.decomposition(outcome),
            "ledger_decomposition": {
                "recomputed": False,
                "L": str(Decimal(str(live_ledger)).quantize(Decimal("0.000001"))),
                "source": "the live row's piv/ledger_score metric",
                "why_not": "candidate/1 scores against the task's golden ledger, which for a generated task is "
                           "minted under the evaluator key; this analysis does not read it. The ledger BYTES are "
                           "published and bound above, so the replay is possible on a machine that holds the key.",
            },
            "composite": {
                "recomputed": "product only",
                "total": str(composite_total),
                "rule": "composite/1: quantise(L x A, 6 places, half-even), executed through the shipped module",
                "L": "live", "A": "recomputed",
            },
            "truth_provenance": provenance,
        })

        if key in PARTIALS:
            counterfactuals.append(build_counterfactual(key, workspace, outcome, truth, expected_balances,
                                                        row, receipt, problems))

    consumption = token_arithmetic(rows, problems)
    attribution = service_attribution(rows, problems)

    record = {
        "schema": "piv.post-run-rescore/1",
        "record_type": "POST-RUN ANALYSIS -- computed after the run, not a live observation",
        "why": ("round18.answer.md:69-71 -- the counterfactual had to be made independently reproducible: the "
                "delivered and corrected application bytes, the exact diff, and an executable rescore carrying "
                "both decompositions rather than totals. The decomposition is labelled post-run because the live "
                "breakdown capture failed on all nine rows."),
        "written_at": datetime.now().isoformat(timespec="seconds"),
        "built_by": {"script": "reviews/cash_application_generated_screen_2026-09-13/rescore_cash_screen_1.py",
                     "truth_reconstruction": "tests/observed_truth.py",
                     "scorer": "beancount_ledger/candidate/application.py (shipped, unmodified)",
                     "composite": "beancount_ledger/candidate/composite.py (shipped, unmodified)"},
        "screen": selection["screen"],
        "selection_digest": selection["self_digest"],
        "subject_requested_id": selection["subject"]["requested_id"],
        "split": selection["split"],
        "method": {
            "truth": "reconstructed from public evidence; see tests/observed_truth.py",
            "pin": ("every cell's recomputed application outcome reproduces the application_result_digest the LIVE "
                    "run wrote into that workspace's delivery receipt. That digest covers the total, all three "
                    "channel fractions, every penalty and one state per receipt, invoice, credit note and tie, so "
                    "the published decomposition is the one the live scorer computed."),
            "not_recomputed": "L (the keyed golden is out of reach here); the composite is the shipped product rule "
                              "applied to a live L and a recomputed A.",
            "observed_bytes": "read-only. The corrected documents are new files; no delivered file is rewritten.",
        },
        "cells": cells,
        "counterfactual": counterfactuals,
        "consumption": consumption,
        "service_attribution": attribution,
        "problems": problems,
    }
    OUT.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")

    for cell in cells:
        print(f"{cell['planned_ordinal']:2d}. {cell['selector'].split(':', 1)[1]:<46} "
              f"A={cell['application_decomposition']['total']} "
              f"pinned={all(cell['pinned_against_live_delivery_receipt'].values())} "
              f"bound={all(cell['bindings'].values())}")
    for cf in counterfactuals:
        print(f"\ncounterfactual {cf['cell']}: A {cf['delivered']['total']} -> {cf['corrected']['total']}, "
              f"penalties {cf['delivered']['penalties']} -> {cf['corrected']['penalties']}, "
              f"diff +{cf['diff']['added_lines']}/-{cf['diff']['removed_lines']} lines")
    print(f"\nconsumption: {consumption['input_tokens']} + {consumption['output_tokens']} = "
          f"{consumption['total_tokens']}, mean {consumption['mean_per_scored_episode']}")
    print(f"written: {OUT}")
    print(f"problems: {problems or 'none'}")
    return 1 if problems else 0


def build_counterfactual(key, workspace, outcome, truth, expected_balances, row, receipt, problems) -> dict:
    """The corrected document, the exact diff, and the rescore of both arms."""
    directory = COUNTERFACTUAL / key
    directory.mkdir(parents=True, exist_ok=True)
    delivered_text = (workspace / "cash_application.json").read_text(encoding="utf-8")
    rows_to_add = missing_rows(outcome, truth)
    corrected = OT.corrected_text(delivered_text, rows_to_add)

    delivered_path = directory / "cash_application.delivered.json"
    corrected_path = directory / "cash_application.corrected.json"
    diff_path = directory / "cash_application.diff"
    delivered_path.write_text(delivered_text, encoding="utf-8", newline="\n")
    corrected_path.write_text(corrected, encoding="utf-8", newline="\n")
    diff = list(difflib.unified_diff(delivered_text.splitlines(keepends=True),
                                     corrected.splitlines(keepends=True),
                                     fromfile=f"{key}/cash_application.delivered.json",
                                     tofile=f"{key}/cash_application.corrected.json", n=3))
    diff_path.write_text("".join(diff), encoding="utf-8", newline="\n")

    if delivered_path.read_bytes() != (workspace / "cash_application.json").read_bytes():
        problems.append(f"{key}: the published delivered copy is not the delivered bytes")
    added = [line for line in diff if line.startswith("+") and not line.startswith("+++")]
    removed = [line for line in diff if line.startswith("-") and not line.startswith("---")]
    if removed:
        problems.append(f"{key}: the counterfactual REMOVES {len(removed)} lines; it is not additive")

    # the corrected arm, scored against the SAME reconstructed truth
    _p, corrected_outcome, _t, _e, _prov = OT.score(workspace, application_text=corrected)
    if str(corrected_outcome.total) != "1.000000" or corrected_outcome.penalties:
        problems.append(f"{key}: the corrected application scores {corrected_outcome.total} "
                        f"{corrected_outcome.penalties}")
    unchanged = {
        "receipt_states": dict(outcome.receipt_states) == dict(corrected_outcome.receipt_states),
        "credit_states": dict(outcome.credit_states) == dict(corrected_outcome.credit_states),
        "other_invoice_states": {i: s for i, s in outcome.invoice_states
                                 if s is not A.INVOICE_MISSING} == {
            i: s for i, s in corrected_outcome.invoice_states
            if i not in {r["invoice_id"] for r in rows_to_add}},
        "ledger_bytes": True,       # the counterfactual does not touch the ledger; the same file scores both arms
    }
    for name, ok in unchanged.items():
        if not ok:
            problems.append(f"{key}: the counterfactual changed {name}")

    live_ledger = Decimal(str(row["metrics"]["piv/ledger_score"]))
    return {
        "cell": key,
        "selector": row["selector"],
        "claim": ("adding ONLY the closing-register rows for the in-period invoices the submission omitted, at "
                  "their period basis with nothing applied, credited or written off, takes A to 1.000000 and "
                  "leaves every other state as delivered"),
        "rows_added": rows_to_add,
        "files": {
            "delivered": f"counterfactual/{key}/cash_application.delivered.json",
            "corrected": f"counterfactual/{key}/cash_application.corrected.json",
            "diff": f"counterfactual/{key}/cash_application.diff",
            "delivered_sha256": sha256(delivered_path.read_bytes()),
            "corrected_sha256": sha256(corrected_path.read_bytes()),
            "diff_sha256": sha256(diff_path.read_bytes()),
        },
        "diff": {"added_lines": len(added), "removed_lines": len(removed),
                 "additive_only": not removed,
                 "hunks": sum(1 for line in diff if line.startswith("@@"))},
        "delivered": OT.decomposition(outcome),
        "corrected": OT.decomposition(corrected_outcome),
        "everything_else_unchanged": unchanged,
        "composite": {
            "delivered": str(X._scale(live_ledger * outcome.total)),
            "corrected": str(X._scale(live_ledger * corrected_outcome.total)),
            "L": str(live_ledger.quantize(Decimal("0.000001"))) + " (live, not recomputed)",
            "complete_corrected": ("candidate/1 holds total == 1 <=> complete, so a live L of 1.000000 is a "
                                   "complete ledger; with A = 1.000000 and no penalty label the composite would "
                                   "be complete. Asserted from the shipped invariant, not replayed."),
        },
        "what_this_does_not_show": ("why the solver omitted the rows, any general variant-a effect, and any "
                                    "prevalence estimate"),
    }


def token_arithmetic(rows, problems) -> dict:
    """The consumption statement's arithmetic, done from the rows."""
    per_episode = [int(row["total_tokens"]) for row in rows]
    inputs = sum(int(row["billed_input_tokens_all_attempts"]) for row in rows)
    outputs = sum(int(row["billed_output_tokens_all_attempts"]) for row in rows)
    responses = sum(len(row["wire_caps_all_attempts"]) for row in rows)
    total = inputs + outputs
    mean = round(total / len(rows), 1)
    if (inputs, outputs, total) != (926855, 157237, 1084092):
        problems.append(f"consumption: {inputs} + {outputs} = {total}, not 926855 + 157237 = 1084092")
    if mean != 120454.7:
        problems.append(f"consumption: mean {mean}, not 120454.7")
    if sum(per_episode) != total:
        problems.append(f"consumption: the per-episode totals sum to {sum(per_episode)}, not {total}")
    return {
        "scored_episodes": len(rows),
        "input_tokens": inputs,
        "output_tokens": outputs,
        "total_tokens": total,
        "captured_responses": responses,
        "mean_per_scored_episode": mean,
        "range_per_episode": [min(per_episode), max(per_episode)],
        "per_episode": {row["selector"].split(":", 1)[1]: int(row["total_tokens"]) for row in rows},
        "statement": ("The nine scored episodes recorded 1,084,092 provider-reported tokens. The next scheduled "
                      "cell encountered a quota-exhaustion 403; its usage was not preserved in a result row. "
                      "These records do not reconcile provider-reported usage to the console's quota debits."),
        "cell_10_usage": "UNKNOWN -- attempted, never recorded; not zero",
    }


def service_attribution(rows, problems) -> dict:
    """`provider` says `nvidia` on every row while the endpoint recorded is
    Alibaba's. The rows are NOT edited; the correction lives here."""
    providers = sorted({row["provider"] for row in rows})
    endpoints = sorted({row["endpoint"] for row in rows})
    models = sorted({row["model"] for row in rows})
    returned = sorted({cap["provider_model"] for row in rows for cap in row["wire_caps_all_attempts"]})
    fingerprints = {cap["system_fingerprint"] for row in rows for cap in row["wire_caps_all_attempts"]}
    if providers != ["nvidia"] or len(endpoints) != 1 or "aliyuncs.com" not in endpoints[0]:
        problems.append(f"attribution: providers {providers}, endpoints {endpoints}")
    if returned != models:
        problems.append(f"attribution: returned model names {returned} are not the requested {models}")
    return {
        "raw_records": "unedited: every row still says provider 'nvidia'",
        "recorded_provider_field": providers,
        "recorded_endpoint": endpoints,
        "serving_service": "Alibaba Cloud Model Studio (ap-southeast-1 maas endpoint)",
        "correction": ("The `provider` column is a DRIVER / PACING label inside measure_budget, not the identity of "
                       "the service that served these episodes. The nine episodes were served by the Alibaba "
                       "endpoint recorded on every row. Read the column as the client path taken, never as the "
                       "provider."),
        "requested_model": models,
        "returned_model_names": returned,
        "returned_matches_requested": returned == models,
        "system_fingerprints": "all null" if fingerprints == {None} else sorted(str(f) for f in fingerprints),
        "captured_responses": sum(len(row["wire_caps_all_attempts"]) for row in rows),
    }


if __name__ == "__main__":
    raise SystemExit(main())
