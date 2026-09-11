"""Cold adjudication of the cash-application evidence pack.

The rule is declared in `predeclared.md` beside this file, written before any
adjudicator was called. This script only executes it.

PUBLICATION NOTE: this is the runner AS EXECUTED on 2026-09-10, with exactly two
lines rewritten for publication and nothing else — this docstring's pointer to the
predeclared rule, and the `sys.path` line below, which named the author's absolute
working-tree path and now resolves the repository root from this file's own
location. No prompt, no comparison, no model id and no output changed.

An adjudicator sees exactly the eleven public files the agent sees and nothing else:
no specification, no scoring code, no truth, no hint that a register is scored or that
a unique answer exists. It is asked the bookkeeper's question and answers in JSON so
the comparison is mechanical.

Usage:
    python cash_adjudicate.py --dry-run          # build the prompts, call nothing
    python cash_adjudicate.py                    # call, one case at a time
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal

# the repository root: this file lives at reviews/<note dir>/ inside it
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

BASE = "https://ws-r76rtaa6sn7jqbcr.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
# Different lineages; neither is the screen's subject (kimi-k3), which cannot
# certify the pack it was measured on.
ADJUDICATORS = ("qwen3.7-max", "deepseek-v4-flash")
CASES = tuple(f"cash_application_{n:03d}" for n in range(1, 6))
OUT = pathlib.Path(__file__).with_name("cash_adjudication.jsonl")

SYSTEM = (
    "You are reviewing one month of a small company's books. You are given the "
    "documents the bookkeeper has and nothing else. Answer only from those documents "
    "and the company's written policy. Where the documents do not settle a question, "
    "say so in the notes rather than choosing. Reply with one JSON object and no other "
    "text."
)

QUESTION = """Here are the files.

{files}

For this period, answer the bookkeeper's question: where did the customers' money go?

Reply with exactly this JSON shape, amounts as strings with two decimals:

{{"receipts": [{{"date": "YYYY-MM-DD", "bank_reference": "<the statement's reference for this credit>",
    "amount": "<the amount the bank shows>",
    "applied": [{{"invoice_id": "SI-nnnn", "amount": "0.00"}}],
    "written_off": [{{"invoice_id": "SI-nnnn", "amount": "0.00"}}],
    "unapplied_amount": "0.00"}}],
 "credit_notes": [{{"credit_note_id": "CN-nnnn",
    "applied": [{{"invoice_id": "SI-nnnn", "amount": "0.00"}}],
    "unapplied_amount": "0.00"}}],
 "closing_open_items": [{{"invoice_id": "SI-nnnn", "remaining": "0.00"}}],
 "notes": "<anything the documents do not settle, or nothing>"}}

Include every customer receipt the bank statement shows and every invoice that was open
during the period, including those that end at zero. `written_off` is for a shortfall
the company gives up on; leave it empty if there is none. `unapplied_amount` is money
received that no invoice absorbs."""


def public_pack(selector: str) -> dict:
    import beancount_ledger.beancount_ledger as bl
    env = bl.load_environment(selector)
    return {name: raw.decode("utf-8") for name, raw in env.public_files.items()}


def truth_register(selector: str) -> dict:
    """The authored truth, for comparison only. Never shown to an adjudicator."""
    from beancount_ledger.graph.derive import derive_contract
    from beancount_ledger.graph.worlds import REGISTRY
    world, task = REGISTRY[selector]
    _bundle, inputs = derive_contract(world, task)
    app = inputs.application
    # receipt  = (key, date, customer, amount, applied, written_off, unapplied, advice, event, rec)
    # credit   = (id, date, customer, gross, applied, unapplied, event)
    # register = (invoice_id, customer, period_basis, applied_total, credited, written_off, remaining)
    receipts = [{
        "key": r[0], "date": r[1], "customer": r[2], "amount": str(r[3]),
        "applied": sorted((i, str(a)) for i, a in r[4]),
        "written_off": sorted((i, str(a)) for i, a in r[5]),
        "unapplied": str(r[6]),
    } for r in app.receipts]
    credits = [{"id": c[0], "gross": str(c[3]),
                "applied": sorted((i, str(a)) for i, a in c[4]),
                "unapplied": str(c[5])} for c in app.credit_notes]
    closing = sorted((row[0], str(row[6])) for row in app.register)
    return {"receipts": receipts, "credit_notes": credits, "closing": closing,
            "closing_ar": str(app.closing_ar), "tolerance": str(app.tolerance)}


def ask(model: str, system: str, user: str, retries: int = 3):
    body = json.dumps({"model": model,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}],
                       "max_tokens": 16000, "temperature": 0}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(BASE + "/chat/completions", data=body, headers={
            "Authorization": "Bearer " + os.environ["DASHSCOPE_API_KEY"],
            "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as fh:
                payload = json.load(fh)
            msg = payload["choices"][0]["message"]
            content = msg.get("content") or ""
            # a reasoning model may return its answer only in reasoning_content
            if not content.strip() and msg.get("reasoning_content"):
                content = msg["reasoning_content"]
            return content, payload.get("usage", {}), None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            if exc.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(30 * (attempt + 1))
                continue
            return "", {}, f"HTTP {exc.code}: {detail}"
        except Exception as exc:                      # noqa: BLE001
            if attempt < retries - 1:
                time.sleep(15)
                continue
            return "", {}, f"{type(exc).__name__}: {exc}"
    return "", {}, "retries exhausted"


def first_json_object(text: str):
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        try:
            return json.loads(fence.group(1))
        except Exception:                              # noqa: BLE001
            pass
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:                  # noqa: BLE001
                        break
        start = text.find("{", start + 1)
    return None


def money(x) -> str:
    try:
        return str(Decimal(str(x)).quantize(Decimal("0.01")))
    except Exception:                                  # noqa: BLE001
        return f"?{x!r}"


def pairs(rows, key="invoice_id", val="amount"):
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            return None
        out.append((str(r.get(key, "")).strip().upper(), money(r.get(val))))
    return sorted(out)


def compare(answer, truth) -> tuple:
    """The declared rule: applied sets, write-offs, unapplied and the credit-note
    application must equal the truth, and closing remaining balances must equal it.
    A missing field is a failure, never agreement."""
    problems = []
    if not isinstance(answer, dict):
        return False, ["no JSON object in the answer"]

    got = {}
    for r in answer.get("receipts") or []:
        if not isinstance(r, dict):
            problems.append("a receipt is not an object")
            continue
        got[money(r.get("amount"))] = r
    for t in truth["receipts"]:
        # match on the bank amount, which every reader can see on the statement
        cash = Decimal(t["amount"])
        r = got.get(money(cash))
        if r is None:
            problems.append(f"no receipt answered for the bank credit {money(cash)}")
            continue
        if pairs(r.get("applied")) != t["applied"]:
            problems.append(f"{money(cash)}: applied {pairs(r.get('applied'))} != {t['applied']}")
        if pairs(r.get("written_off")) != t["written_off"]:
            problems.append(f"{money(cash)}: written_off {pairs(r.get('written_off'))} != {t['written_off']}")
        if "unapplied_amount" not in r:
            problems.append(f"{money(cash)}: unapplied_amount missing")
        elif money(r.get("unapplied_amount")) != t["unapplied"]:
            problems.append(f"{money(cash)}: unapplied {money(r.get('unapplied_amount'))} != {t['unapplied']}")

    gc = {str(c.get("credit_note_id", "")).strip().upper(): c
          for c in (answer.get("credit_notes") or []) if isinstance(c, dict)}
    for t in truth["credit_notes"]:
        c = gc.get(t["id"].upper())
        if c is None:
            problems.append(f"no answer for credit note {t['id']}")
            continue
        if pairs(c.get("applied")) != t["applied"]:
            problems.append(f"{t['id']}: applied {pairs(c.get('applied'))} != {t['applied']}")
        if "unapplied_amount" not in c:
            problems.append(f"{t['id']}: unapplied_amount missing")
        elif money(c.get("unapplied_amount")) != t["unapplied"]:
            problems.append(f"{t['id']}: unapplied {money(c.get('unapplied_amount'))} != {t['unapplied']}")

    closing = pairs(answer.get("closing_open_items"), key="invoice_id", val="remaining")
    if closing != truth["closing"]:
        problems.append(f"closing {closing} != {truth['closing']}")
    return not problems, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cases", nargs="*", default=list(CASES))
    ap.add_argument("--models", nargs="*", default=list(ADJUDICATORS))
    args = ap.parse_args()

    sink = None if args.dry_run else OUT.open("a", encoding="utf-8")
    admissible, contested = [], []
    for selector in args.cases:
        pack = public_pack(selector)
        truth = truth_register(selector)
        files = "\n\n".join(f"=== {name} ===\n{text}" for name, text in sorted(pack.items()))
        user = QUESTION.format(files=files)
        if args.dry_run:
            print(f"{selector}: {len(pack)} files, prompt {len(user):,} chars "
                  f"(~{len(user)//4:,} tokens); truth receipts={len(truth['receipts'])} "
                  f"credits={len(truth['credit_notes'])} rows={len(truth['closing'])}")
            continue
        verdicts = {}
        for model in args.models:
            t0 = time.time()
            text, usage, err = ask(model, SYSTEM, user)
            answer = first_json_object(text) if text else None
            ok, problems = (False, [err or "no answer"]) if answer is None else compare(answer, truth)
            verdicts[model] = {"ok": ok, "problems": problems, "answer": answer,
                               "raw_head": text[:400], "usage": usage, "secs": round(time.time() - t0)}
            print(f"  {selector:<22} {model:<18} {'PASS' if ok else 'differs'} "
                  f"{('| ' + '; '.join(problems)[:220]) if problems else ''}", flush=True)
        both = all(v["ok"] for v in verdicts.values())
        (admissible if both else contested).append(selector)
        sink.write(json.dumps({"case": selector, "admissible": both, "truth": truth,
                               "verdicts": verdicts}, default=str) + "\n")
        sink.flush()
    if sink:
        sink.close()
        print(f"\nadmissible (both pass): {admissible}")
        print(f"contested: {contested}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
