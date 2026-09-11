"""The corrected comparison: the archived answers, re-compared under the
SHIPPED scorer's pre-existing zero-application normalisation.

`cash_adjudicate.py` compared each adjudicator's applied and written-off sets
to the truth literally. `application/1` does not: `_canonical_items` sums a
receipt's items by invoice, DROPS what sums to zero and orders by invoice id
(`beancount_ledger/candidate/application.py`). That normalisation is
pre-existing — it landed on 2026-09-09, the day before this adjudication ran —
so a zero-amount advice line the comparator counted as a difference is not a
difference under the contract the pack is scored by.

This script imports that function from the installed package rather than
re-implementing it, re-runs the same comparison, and prints the predeclared
rule's FOUR outcomes rather than the runner's two. It calls no model: it reads
`cash_adjudication.jsonl` and nothing else.

    python corrected_comparison.py                 # print, and write corrected_comparison.json
"""
from __future__ import annotations

import json
import pathlib
import sys
from decimal import Decimal

HERE = pathlib.Path(__file__).resolve().parent
# the repository root: this file lives at reviews/<note dir>/ inside it
sys.path.insert(0, str(HERE.parents[1]))

from beancount_ledger.candidate.application import _canonical_items   # the SHIPPED normalisation

ANSWERS = HERE / "cash_adjudication.jsonl"
OUT = HERE / "corrected_comparison.json"


def money(x) -> str:
    try:
        return str(Decimal(str(x)).quantize(Decimal("0.01")))
    except Exception:                                   # noqa: BLE001
        return f"?{x!r}"


def pairs(rows, key="invoice_id", val="amount"):
    """The runner's reading of an item list: (invoice id, amount) sorted."""
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            return None
        out.append((str(r.get(key, "")).strip().upper(), money(r.get(val))))
    return sorted(out)


def normalised(rows, key="invoice_id", val="amount"):
    """The same list through `application/1`'s own `_canonical_items`."""
    read = pairs(rows, key, val)
    if read is None:
        return None
    canonical = _canonical_items([(i, Decimal(a)) for i, a in read if not a.startswith("?")])
    return sorted((i, money(a)) for i, a in canonical)


def compare(answer, truth, normalise: bool) -> list:
    """The predeclared rule's four fields. `normalise=False` reproduces the
    runner's comparison exactly; `normalise=True` is the corrected one."""
    read = normalised if normalise else pairs
    problems = []
    if not isinstance(answer, dict):
        return ["no JSON object in the answer"]

    got = {}
    for r in answer.get("receipts") or []:
        if isinstance(r, dict):
            got[money(r.get("amount"))] = r
    for t in truth["receipts"]:
        cash = money(Decimal(t["amount"]))
        r = got.get(cash)
        if r is None:
            problems.append(f"no receipt answered for the bank credit {cash}")
            continue
        # the truth's own sets are already canonical: it is the golden register
        if read(r.get("applied")) != [tuple(x) for x in t["applied"]]:
            problems.append(f"{cash}: applied {read(r.get('applied'))} != {t['applied']}")
        if read(r.get("written_off")) != [tuple(x) for x in t["written_off"]]:
            problems.append(f"{cash}: written_off {read(r.get('written_off'))} != {t['written_off']}")
        if "unapplied_amount" not in r:
            problems.append(f"{cash}: unapplied_amount missing")
        elif money(r.get("unapplied_amount")) != t["unapplied"]:
            problems.append(f"{cash}: unapplied {money(r.get('unapplied_amount'))} != {t['unapplied']}")

    gc = {str(c.get("credit_note_id", "")).strip().upper(): c
          for c in (answer.get("credit_notes") or []) if isinstance(c, dict)}
    for t in truth["credit_notes"]:
        c = gc.get(t["id"].upper())
        if c is None:
            problems.append(f"no answer for credit note {t['id']}")
            continue
        if read(c.get("applied")) != [tuple(x) for x in t["applied"]]:
            problems.append(f"{t['id']}: applied {read(c.get('applied'))} != {t['applied']}")
        if "unapplied_amount" not in c:
            problems.append(f"{t['id']}: unapplied_amount missing")
        elif money(c.get("unapplied_amount")) != t["unapplied"]:
            problems.append(f"{t['id']}: unapplied {money(c.get('unapplied_amount'))} != {t['unapplied']}")

    closing = pairs(answer.get("closing_open_items"), key="invoice_id", val="remaining")
    if closing != [tuple(x) for x in truth["closing"]]:
        problems.append(f"closing {closing} != {truth['closing']}")
    return problems


def classify(per_model: dict) -> str:
    """The PREDECLARED rule's four outcomes, which the runner did not
    implement: it printed every case without two passes as `contested`."""
    passing = [m for m, v in per_model.items() if not v["problems"]]
    if len(passing) == len(per_model):
        return "both pass - admissible"
    if len(passing) == len(per_model) - 1:
        return "one passes, one differs - contested"
    shapes = {json.dumps(v["problems"], sort_keys=True) for v in per_model.values()}
    if len(shapes) == 1:
        return "both differ the same way - defective pending examination of the evidence"
    return "both differ, differently - ambiguous, defective"


def main() -> int:
    cases = [json.loads(line) for line in ANSWERS.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = {
        "schema": "piv.cash-adjudication-corrected/1",
        "what_this_is": ("The archived adjudication answers re-compared under `application/1`'s pre-existing "
                         "zero-application normalisation (`_canonical_items`, imported from the shipped "
                         "package). No model is called. The `as_executed` column reproduces the original "
                         "runner's verdicts from the same archived answers, so the two readings are "
                         "comparable line by line."),
        "normalisation": ("beancount_ledger.candidate.application._canonical_items — sum by invoice, drop "
                          "what sums to zero, order by invoice id; applied to every receipt's applied and "
                          "written-off sets and to every credit note's applied set"),
        "cases": [],
    }
    totals = {"as_executed_passes": 0, "corrected_passes": 0, "answers": 0}
    for case in cases:
        row = {"case": case["case"], "models": {}}
        as_exec, corrected = {}, {}
        for model, verdict in case["verdicts"].items():
            answer = verdict.get("answer")
            as_exec[model] = {"problems": compare(answer, case["truth"], normalise=False)}
            corrected[model] = {"problems": compare(answer, case["truth"], normalise=True)}
            row["models"][model] = {
                "as_executed": "pass" if not as_exec[model]["problems"] else "differs",
                "as_executed_problems": as_exec[model]["problems"],
                "archived_runner_verdict": "pass" if verdict.get("ok") else "differs",
                "corrected": "pass" if not corrected[model]["problems"] else "differs",
                "corrected_problems": corrected[model]["problems"],
            }
            totals["answers"] += 1
            totals["as_executed_passes"] += 0 if as_exec[model]["problems"] else 1
            totals["corrected_passes"] += 0 if corrected[model]["problems"] else 1
        row["predeclared_classification_of_the_disagreements"] = classify(as_exec)
        row["corrected_classification"] = classify(corrected)
        row["reproduces_the_archived_runner"] = all(
            v["as_executed"] == v["archived_runner_verdict"] for v in row["models"].values())
        report["cases"].append(row)
    report["totals"] = totals
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="")

    print(f"{'case':<24} {'model':<20} {'as executed':<12} corrected")
    for row in report["cases"]:
        for model, v in row["models"].items():
            print(f"  {row['case']:<22} {model:<20} {v['as_executed']:<12} {v['corrected']}")
        print(f"  {'':<22} {'-> predeclared:':<20} {row['predeclared_classification_of_the_disagreements']}")
        print(f"  {'':<22} {'-> corrected:':<20} {row['corrected_classification']}")
    print(f"\nas executed: {totals['as_executed_passes']}/{totals['answers']} answers pass; "
          f"corrected: {totals['corrected_passes']}/{totals['answers']}")
    bad = [r["case"] for r in report["cases"] if not r["reproduces_the_archived_runner"]]
    if bad:
        print(f"WARNING: the as-executed column does not reproduce the archived verdicts on {bad}")
        return 1
    print("the as-executed column reproduces every archived verdict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
