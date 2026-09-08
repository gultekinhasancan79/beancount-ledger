"""WA-1b case selection: the revised construction, enumerated and gated.

What changed from WA-1, and why each rule is here:

  wrong account   Assets:Equipment or Assets:Prepayments, never Assets:Inventory.
                  Inventory is bank-paired zero times in every shipped ledger, so a
                  mis-posting to it was the unique account-pair shape in the file and
                  a singleton search solved the arm with no accounting. Each case also
                  requires >= 1 legitimate two-legged bank/<wrong> entry in its own
                  ledger, so the planted entry hides among real ones.
  control error   the SHIPPED strategy/parameter when the task's mutation on the
                  target was an alteration; otherwise a non-leading transposition or
                  drop (parameter >= 1). Leading-digit and decimal-shift errors are
                  10-300x the production distribution and inflate the contrast.
  prompt          ONE full task prompt for every case and both arms. The inherited
                  prompts scope the work to statement disagreement, which a wrong
                  account never produces.
  Tier A          excluded: an in-period purchase from the same vendor at the SAME
                  amount is a duplicate decoy (deleting the purchase scores 0).
  siblings        excluded: another correctly booked AP payment to the same vendor
                  in the period is a precedent the agent can imitate.
  collision       excluded: the WA payee must not be the counterparty of any other
                  planted item.
  gates           control identifiable with matching keys; treatment identifiable on
                  the N-1 other items with matching keys; the public-only prototype
                  checker finds exactly the WA repair and nothing in the control;
                  both goldens score 1.0; residual cancellation, predicate and leg
                  uniqueness (inside build_pair).

Emits wa1b_pool.json: every candidate with its verdict, and an ORDERED pool of up
to 14 admissible cases, at most two per world, balanced between the two wrong
accounts, for the cold admissibility adjudication to take the first ten from.
"""
import csv
import io
import json
import re
import sys
from decimal import Decimal

SCRATCH = r"C:/Users/gulte/AppData/Local/Temp/claude/C--Users-gulte-Desktop-PIV/e5af9fd8-5589-401a-8521-18264e0703e0/scratchpad"
sys.path.insert(0, SCRATCH)
sys.path.insert(0, r"C:/Users/gulte/Desktop/PIV/beancount-ledger-workflows")

from beancount_ledger.graph.worlds import WORLD_MODULES               # noqa: E402
from beancount_ledger.graph.derive import derive_contract, planted_key  # noqa: E402
from beancount_ledger.graph.identify import check_identifiable, repair_key, CUSTOMERS_FILE, VENDORS_FILE  # noqa: E402
from beancount_ledger.candidate import committed as K                 # noqa: E402
from wa1_build import build_pair, score                               # noqa: E402
from wa_checker import wrong_account_repairs                          # noqa: E402

WA_ID = "misbooked_supplier_payment"
WRONG_ACCOUNTS = ("Assets:Equipment", "Assets:Prepayments")
NON_LEADING = (("transpose_digits", 1), ("transpose_digits", 2), ("drop_digit", 1),
               ("transpose_digits", 3), ("drop_digit", 2))
POOL_SIZE, PER_WORLD = 14, 2
# Two relaxations, OFF by default so the strict run stays reproducible. Each is
# recorded on the row as a stratum, never silently folded in.
#   --allow-siblings   a correctly booked AP payment to the same vendor in the
#                      period is a precedent the agent could imitate; keep the
#                      case but tag it, and analyse the stratum separately.
#   --any-target       let any in-period stock-vendor payment be the target, not
#                      only one the shipped task already planted. Both arms then
#                      carry the shipped plan PLUS the one differing item (k+1),
#                      still paired, still differing in exactly one item.
ALLOW_SIBLINGS = "--allow-siblings" in sys.argv
ANY_TARGET = "--any-target" in sys.argv

# Codex round 5, section 2: one complete prompt, identical in both arms, naming
# neither the error kind nor the treatment transaction.
PROMPT = ("You are closing the month. Audit the complete ledger under the bank statement, "
          "referenced documents, master files, and bookkeeping policy. Correct every discrepancy "
          "that the supplied evidence establishes, and leave timing differences and anything not "
          "provably wrong unchanged. Write the corrected ledger back to ledger.beancount.")

ENTRY = re.compile(r'^(\d{4}-\d{2}-\d{2})\s+[*!]\s+"[^"]*"\s+"[^"]*"\s*$')
LEG = re.compile(r'^\s{2,}([A-Za-z][\w:.\-]*)\s+-?[\d,]+\.\d{2}\s+[A-Z]{3}\s*$')


def names_of(public):
    out = set()
    for fn, col in ((CUSTOMERS_FILE, "customer"), (VENDORS_FILE, "vendor")):
        for r in csv.DictReader(io.StringIO(public.get(fn, ""))):
            if (r.get(col) or "").strip():
                out.add(r[col].strip())
    return frozenset(out)


def bank_pairs(ledger_text: str, bank: str):
    """How many two-legged entries pair the bank with each other account."""
    counts, legs, inside = {}, [], False
    for raw in ledger_text.splitlines() + [""]:
        if ENTRY.match(raw):
            inside, legs = True, []
            continue
        m = LEG.match(raw)
        if m and inside:
            legs.append(m.group(1))
            continue
        if raw.strip() == "" and inside:
            s = set(legs)
            if len(legs) == 2 and bank in s:
                other = next(a for a in s if a != bank)
                counts[other] = counts.get(other, 0) + 1
            inside, legs = False, []
    return counts


rows = []
for m in WORLD_MODULES:
    w = m.WORLD
    parties = {p.id: p for p in w.parties}
    for tid, task in sorted(m.TASKS.items()):
        _b, base = derive_contract(w, task)
        public = {n: d.decode("utf-8") for n, d in base.public_files}
        try:
            _r, _n, payables, stock = wrong_account_repairs(
                public, bank_account=w.bank_account, period_start=task.period.start, period_end=task.period.end)
        except Exception as exc:                                       # noqa: BLE001
            rows.append(dict(world=w.id, task=tid, rejected=f"checker: {type(exc).__name__}: {exc}"[:160]))
            continue
        pairs = bank_pairs(public["ledger.beancount"], w.bank_account)
        chart = set(base.allowed_accounts)
        plan_payees = {mu.mutation_id: _b.recognition(mu.recognition_id).payee for mu in task.plan.mutations}
        for e in w.events:
            if type(e).__name__ != "VendorPayment":
                continue
            p = parties[e.party_id]
            if p.name not in stock:
                continue
            st = getattr(e, "settlement", None)
            if st is None or not task.period.contains(st.cleared_on):
                continue
            rec_id = "rec:" + e.id.split(":", 1)[1]
            shipped = next((mu for mu in task.plan.mutations if mu.recognition_id == rec_id), None)
            if shipped is None and not ANY_TARGET:
                continue                      # the target must be one of this task's own planted items
            if shipped is None:
                shared, target_mode = tuple(task.plan.mutations), "added"
            else:
                shared, target_mode = tuple(mu for mu in task.plan.mutations if mu.recognition_id != rec_id), "replaced"
            reasons = []
            if any(plan_payees[mu.mutation_id] == p.name for mu in shared):
                reasons.append("collision")
            same_amount_purchase = any(type(x).__name__ == "Purchase" and x.party_id == e.party_id
                                       and task.period.contains(x.date) and x.amount == e.amount for x in w.events)
            if same_amount_purchase:
                reasons.append("tierA_same_amount_purchase")
            siblings = sum(1 for x in w.events if type(x).__name__ == "VendorPayment" and x.party_id == e.party_id
                           and getattr(x, "settlement", None) is not None
                           and task.period.contains(x.settlement.cleared_on)) - 1
            if siblings and not ALLOW_SIBLINGS:
                reasons.append(f"siblings={siblings}")
            if shipped is not None and type(shipped).__name__ == "AlterRecognition":
                controls = [(shipped.strategy, shipped.parameter)]
                control_source = "shipped"
            else:
                controls = list(NON_LEADING)
                control_source = "drawn_non_leading"
            for wrong in WRONG_ACCOUNTS:
                row = dict(world=w.id, task=tid, rec=rec_id, payee=p.name, amount=str(e.amount), rail=st.rail.value,
                           wrong=wrong, shipped_kind=type(shipped).__name__ if shipped else None,
                           control_source=control_source, target_mode=target_mode,
                           siblings=siblings, stratum_sibling=bool(siblings),
                           kinds=sorted(type(mu).__name__ for mu in shared), k=len(shared) + 1,
                           legit_bank_pairs_with_wrong=pairs.get(wrong, 0), rejected=None)
                why = list(reasons)
                if wrong not in chart:
                    why.append("wrong_not_in_chart")
                elif pairs.get(wrong, 0) < 1:
                    why.append("wrong_is_unique_shape")
                if why:
                    row["rejected"] = ",".join(why)
                    rows.append(row)
                    continue
                verdict = None
                for strat, param in controls:
                    try:
                        C, T, rep = build_pair(w, f"wa1b_{w.id}_{rec_id.split(':', 1)[1]}", PROMPT, task.period,
                                               shared, rec_id, wrong, control_strategy=strat,
                                               control_parameter=param, claim="wa1b")
                        cenv, tenv = K.load_contract(C), K.load_contract(T)
                    except Exception as exc:                           # noqa: BLE001
                        verdict = f"build: {type(exc).__name__}: {exc}"[:120]
                        continue
                    if rep["right"] != payables:
                        verdict = f"right account {rep['right']} != payables {payables}"
                        continue
                    cpub = {n: b.decode("utf-8") for n, b in C.public_files}
                    tpub = {n: b.decode("utf-8") for n, b in T.public_files}
                    nm = names_of(cpub)
                    kw = dict(bank_account=w.bank_account, period_start=task.period.start, period_end=task.period.end)
                    cv = check_identifiable(cpub, **kw)
                    if not (cv.unique and sorted(planted_key(x, nm, bank_account=w.bank_account) for x in C.planted)
                            == sorted(repair_key(r) for r in cv.repairs)):
                        verdict = "control not identifiable / keys differ"
                        continue
                    tv = check_identifiable(tpub, **kw)
                    twant = sorted(planted_key(x, nm, bank_account=w.bank_account) for x in T.planted if x.id != WA_ID)
                    if not (tv.unique and twant == sorted(repair_key(r) for r in tv.repairs)):
                        verdict = "treatment: other items not identifiable"
                        continue
                    creps = wrong_account_repairs(cpub, **kw)[0]
                    treps = wrong_account_repairs(tpub, **kw)[0]
                    wa = next(x for x in T.planted if x.id == WA_ID)
                    wakey = ("wrong_account", wa.date,
                             tuple(sorted((a, "%.2f" % Decimal(v)) for a, v in wa.required)), wa.must_be_payee[0],
                             tuple(sorted((a, "%.2f" % Decimal(v)) for a, v in wa.replaces)), 1)
                    if creps or len(treps) != 1 or treps[0].key() != wakey:
                        verdict = f"prototype checker: control={len(creps)} treatment={[r.key()[0] for r in treps]}"
                        continue
                    cg, _ = score(C.golden_text, cenv)
                    tg, _ = score(T.golden_text, tenv)
                    if cg is None or tg is None or cg.total != 1 or tg.total != 1:
                        verdict = f"golden scores control={getattr(cg, 'total', None)} treatment={getattr(tg, 'total', None)}"
                        continue
                    row.update(strategy=strat, parameter=param, scored=list(C.scored_accounts),
                               control_id=C.task_id, treatment_id=T.task_id, was=rep["was"].strip(),
                               now=rep["now"].strip(), rejected=None)
                    verdict = None
                    break
                if verdict:
                    row["rejected"] = verdict
                rows.append(row)

admissible = [r for r in rows if r.get("rejected") is None and "strategy" in r]
# ordered pool: deterministic; <= PER_WORLD per world; one row per (world, target);
# the wrong account is whichever of the two admissible variants is less used so
# far, so the pool stays balanced; replaced-and-sibling-free targets come first.
# keyed by (world, task, target): the same payment under two tasks is two
# different shared plans, and one payment may only enter the pool once
by_target = {}
for r in admissible:
    by_target.setdefault((r["world"], r["task"], r["rec"]), {})[r["wrong"]] = r
order = sorted(by_target, key=lambda k: (
    0 if any(v["target_mode"] == "replaced" for v in by_target[k].values()) else 1,
    0 if not any(v["stratum_sibling"] for v in by_target[k].values()) else 1, k))
pool, per_world, per_wrong, used_payment = [], {}, {a: 0 for a in WRONG_ACCOUNTS}, set()
for key in order:
    world, _task, rec = key
    if len(pool) >= POOL_SIZE or per_world.get(world, 0) >= PER_WORLD or (world, rec) in used_payment:
        continue
    choices = sorted(by_target[key].values(), key=lambda v: (per_wrong[v["wrong"]], v["wrong"]))
    r = choices[0]
    if per_wrong[r["wrong"]] >= POOL_SIZE // 2:
        continue
    pool.append(r)
    used_payment.add((world, rec))
    per_world[world] = per_world.get(world, 0) + 1
    per_wrong[r["wrong"]] += 1

print(f"candidates: {len(rows)}   admissible: {len(admissible)}   pool: {len(pool)} "
      f"({per_wrong})")
print()
print("POOL (ordered):")
for i, r in enumerate(pool, 1):
    print(f"  {i:2d}. {r['world']:<20} {r['task'][:26]:<26} {r['rec']:<22} {r['payee'][:24]:<24} {r['amount']:>8} "
          f"{r['wrong']:<19} ctl={r['strategy']}/{r['parameter']} ({r['control_source'][:7]}) "
          f"{r['target_mode']:<8} sib={int(r['stratum_sibling'])} k={r['k']} pairs={r['legit_bank_pairs_with_wrong']}")
print()
print("admissible but not pooled:", len(admissible) - len(pool))
print()
reject_counts = {}
for r in rows:
    if r.get("rejected"):
        key = r["rejected"].split(":")[0].split(",")[0]
        reject_counts[key] = reject_counts.get(key, 0) + 1
print("rejections by first reason:", dict(sorted(reject_counts.items(), key=lambda kv: -kv[1])))
json.dump({"prompt": PROMPT, "wrong_accounts": WRONG_ACCOUNTS, "pool": pool, "rows": rows},
          open(SCRATCH + ("/wa1b_pool_relaxed.json" if (ALLOW_SIBLINGS or ANY_TARGET) else "/wa1b_pool.json"), "w", encoding="utf-8"), indent=1, default=str)
print("->", "wa1b_pool_relaxed.json" if (ALLOW_SIBLINGS or ANY_TARGET) else "wa1b_pool.json")
