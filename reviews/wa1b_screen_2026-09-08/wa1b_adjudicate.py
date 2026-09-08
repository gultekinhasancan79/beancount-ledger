"""WA-1b cold admissibility adjudication (Codex round 3 §4, round 5 §4).

For each pooled case, a strong model that is NOT the pilot subject and did not
design the pilot is given ONLY the treatment arm's eight public files and asked
to audit the one transaction — without being told it is wrong, what the
hypothesis is, or what account the policy requires. Two adjudicators from
different lineages; a case passes only if BOTH, independently:

    - derive the payables account as the required counter-account, unaided;
    - reject the account the books carry;
    - name no second defensible treatment;
    - cite the invoice/payable, the vendor classification and the policy.

The question is neutral and the verdict is machine-readable: the model is asked
to end with a JSON object naming the account it holds required, whether the
current one is permitted, and any alternatives it considers defensible. Nothing
in the prompt names Liabilities:AP, "wrong account", or the pilot.

Adjudicators are burned as future subjects. Neither Codex nor Claude may sit
here. API calls are stateless, so having run other episodes does not taint a
model; circular certification (subject certifying its own case) is the hazard.

    python wa1b_adjudicate.py [--limit N] [--pool relaxed|strict]
"""
import json
import re
import sys
import time
import urllib.request
import winreg
from pathlib import Path

SCRATCH = r"C:/Users/gulte/AppData/Local/Temp/claude/C--Users-gulte-Desktop-PIV/e5af9fd8-5589-401a-8521-18264e0703e0/scratchpad"
sys.path.insert(0, SCRATCH)
sys.path.insert(0, r"C:/Users/gulte/Desktop/PIV/beancount-ledger-workflows")

from beancount_ledger.graph.worlds import WORLD_MODULES   # noqa: E402
from wa1_build import build_pair                          # noqa: E402
from wa_checker import wrong_account_repairs              # noqa: E402

BASE = "https://ws-r76rtaa6sn7jqbcr.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions"
# two lineages, neither the subject (MiniMax M3), neither a designer
ADJUDICATORS = ("qwen3.7-max", "deepseek-v4-flash")
FILE_ORDER = ("manifest.md", "policy.md", "accounts.csv", "customers.csv", "vendors.csv",
              "archive_prior_period.csv", "ledger.beancount", "bank_statement.csv")

SYSTEM = ("You are an independent bookkeeping reviewer. You will be given a small company's month "
          "as eight files and asked to audit ONE transaction in its ledger. Reason only from the "
          "supplied records. Do not assume the transaction is wrong, and do not assume it is right.")

QUESTION = """Audit the ledger transaction dated {date}, with payee "{payee}", for {amount} {currency}.

Without assuming that it is erroneous, enumerate every posting treatment the supplied records support for this transaction. State whether the counter-account it currently carries is permitted under the bookkeeping policy and the master files, and cite the specific evidence (file and line or sentence) for each conclusion.

End your answer with exactly one JSON object on its own line, of this shape and nothing else after it:
{{"current_counter_account": "<the non-bank account the ledger carries for this transaction>",
  "current_is_permitted": true or false,
  "required_counter_account": "<the account the records require, or null if the current one is permitted>",
  "other_defensible_treatments": ["<any other account the records would equally support>", ...],
  "evidence": ["<file: quoted sentence or line>", ...]}}"""


def key():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
        return winreg.QueryValueEx(h, "DASHSCOPE_API_KEY")[0]


def ask(model, system, user, k, retries=3):
    body = json.dumps({"model": model, "messages": [{"role": "system", "content": system},
                                                     {"role": "user", "content": user}],
                       "max_tokens": 16000, "temperature": 0}).encode()
    req = urllib.request.Request(BASE, data=body, headers={"Authorization": "Bearer " + k,
                                                            "Content-Type": "application/json"})
    for attempt in range(1, retries + 1):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=900))
            msg = d["choices"][0]["message"]
            content = msg.get("content") or ""
            # a reasoning model may return its answer only in reasoning_content when the
            # visible reply is empty; take it, and record that we did
            if not content.strip() and msg.get("reasoning_content"):
                content = "[from reasoning_content]" + chr(10) + msg["reasoning_content"]
            return content, (d.get("usage") or {}), None
        except urllib.error.HTTPError as exc:
            err = f"{exc.code} {exc.read().decode()[:160]}"
            if exc.code in (403, 401):
                return None, {}, err
        except Exception as exc:                                        # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"[:160]
        time.sleep(20 * attempt)
    return None, {}, err


def last_json(text):
    """The final JSON object in the reply, or None."""
    for m in reversed(list(re.finditer(r"\{[\s\S]*\}", text))):
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            # try the tightest closing brace
            chunk = m.group(0)
            for end in range(len(chunk), 0, -1):
                if chunk[end - 1] == "}":
                    try:
                        return json.loads(chunk[:end])
                    except json.JSONDecodeError:
                        continue
    return None


def rebuild_treatment(row, prompt):
    module = next(m for m in WORLD_MODULES if m.WORLD.id == row["world"])
    world, task = module.WORLD, module.TASKS[row["task"]]
    if row["target_mode"] == "replaced":
        shared = tuple(mu for mu in task.plan.mutations if mu.recognition_id != row["rec"])
    else:
        shared = tuple(task.plan.mutations)
    C, T, rep = build_pair(world, f"wa1b_{world.id}_{row['rec'].split(':', 1)[1]}", prompt, task.period,
                           shared, row["rec"], row["wrong"], control_strategy=row["strategy"],
                           control_parameter=row["parameter"], claim="wa1b")
    return world, task, T, rep


def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    which = args[args.index("--pool") + 1] if "--pool" in args else "relaxed"
    pool_file = Path(SCRATCH) / ("wa1b_pool_relaxed.json" if which == "relaxed" else "wa1b_pool.json")
    d = json.loads(pool_file.read_text(encoding="utf-8"))
    pool = d["pool"][:limit] if limit else d["pool"]
    if "--cases" in args:
        wanted = set(args[args.index("--cases") + 1].split(","))
        pool = [r for r in pool if f"{r['world']}/{r['rec']}" in wanted]
    out_path = Path(SCRATCH) / f"wa1b_adjudication_{which}.jsonl"
    k = key()
    print(f"adjudicating {len(pool)} cases with {ADJUDICATORS} -> {out_path.name}", flush=True)
    passed = 0
    with out_path.open("a", encoding="utf-8") as sink:
        for i, row in enumerate(pool, 1):
            world, task, T, rep = rebuild_treatment(row, d["prompt"])
            public = {n: b.decode("utf-8") for n, b in T.public_files}
            missing = [n for n in FILE_ORDER if n not in public]
            if missing or len(public) != len(FILE_ORDER):
                raise SystemExit(f"{rep['case']}: public files {sorted(public)} != the eight expected; missing {missing}")
            payables = wrong_account_repairs(public, bank_account=world.bank_account,
                                             period_start=task.period.start, period_end=task.period.end)[2]
            files = "\n\n".join(f"===== {n} =====\n{public[n]}" for n in FILE_ORDER)
            user = (files + "\n\n===== QUESTION =====\n"
                    + QUESTION.format(date=rep["date"], payee=rep["payee"], amount=rep["amount"],
                                      currency=world.currency))
            verdicts = {}
            for model in ADJUDICATORS:
                t0 = time.time()
                text, usage, err = ask(model, SYSTEM, user, k)
                js = last_json(text) if text else None
                req = (js or {}).get("required_counter_account")
                cur_ok = (js or {}).get("current_is_permitted")
                others = [a for a in ((js or {}).get("other_defensible_treatments") or []) if a and a != req]
                cur = (js or {}).get("current_counter_account")
                ok = bool(js) and cur_ok is False and req == payables and not others
                verdicts[model] = dict(ok=ok, current=cur, current_is_permitted=cur_ok, required=req,
                                       others=others, evidence=(js or {}).get("evidence"),
                                       parsed=bool(js), error=err, prompt_tokens=usage.get("prompt_tokens"),
                                       completion_tokens=usage.get("completion_tokens"),
                                       secs=round(time.time() - t0), raw=text)
                print(f"  [{i:2d}/{len(pool)}] {row['world']:<20} {row['rec']:<22} {row['wrong'].split(':')[1]:<12} "
                      f"{model:<18} {'PASS' if ok else 'fail'}  req={req} cur_ok={cur_ok} others={others} "
                      f"{'ERR ' + err if err else ''}", flush=True)
            case_pass = all(v["ok"] for v in verdicts.values())
            passed += case_pass
            sink.write(json.dumps(dict(case=rep["case"], world=row["world"], task=row["task"], rec=row["rec"],
                                       wrong=row["wrong"], target_mode=row["target_mode"],
                                       stratum_sibling=row["stratum_sibling"], booked=rep["now"].strip(),
                                       payables=payables, date=rep["date"], payee=rep["payee"],
                                       amount=rep["amount"], verdicts=verdicts, case_pass=case_pass),
                                  default=str) + "\n")
            sink.flush()
    print(f"\n{passed}/{len(pool)} cases pass both adjudicators")


if __name__ == "__main__":
    main()
