"""WA-1 pilot builder: one pair from one registered world."""
import sys
from decimal import Decimal
from itertools import combinations
sys.path.insert(0, r"C:/Users/gulte/AppData/Local/Temp/claude/C--Users-gulte-Desktop-PIV/e5af9fd8-5589-401a-8521-18264e0703e0/scratchpad")
sys.path.insert(0, r"C:/Users/gulte/Desktop/PIV/beancount-ledger-workflows")
from beancount_ledger.graph.project import (AlterRecognition, MutationPlan, LEDGER_VIEW,
                                            POSTING_ACCOUNT_WIDTH, POSTING_AMOUNT_WIDTH,
                                            VIEW_DOMAIN, PROJECTION_VERSION)
from beancount_ledger.graph.policy import ACCOUNTING_POLICY_VERSION
from beancount_ledger.graph.derive import TaskSpec, derive_contract, PlantedSpec, _archived_literal_inputs
from beancount_ledger.candidate.canonical import canonical_decimal, canonical_bytes, domain_digest
from beancount_ledger.candidate import committed as K
from beancount_ledger.candidate.normalise import parse_once, Accepted
from beancount_ledger import beancount_ledger as env_mod


class PilotRefused(Exception):
    pass


def _posting_line(account, value, currency):
    return "  {0:<{1}}{2:>{3}.2f} {4}".format(account, POSTING_ACCOUNT_WIDTH, value, POSTING_AMOUNT_WIDTH, currency)


def _view_digest(name, text):
    return domain_digest(VIEW_DOMAIN, canonical_bytes({"name": name, "text": text,
        "projection_version": PROJECTION_VERSION, "accounting_policy_version": ACCOUNTING_POLICY_VERSION}))


def _remint(base, task_id, prompt, planted, scored, original_text, public_files, tag):
    vd = tuple(sorted((n, _view_digest(n, b.decode("utf-8"))) for n, b in public_files))
    return _archived_literal_inputs(
        task_id=task_id, task_type=base.task_type, prompt=prompt, period=base.period,
        world_id=base.world_id, currency=base.currency,
        scored_accounts=tuple(scored), expected_balances=base.expected_balances,
        allowed_accounts=base.allowed_accounts, planted=tuple(planted), traps=base.traps,
        original_text=original_text, golden_text=base.golden_text,
        statement_closing=base.statement_closing,
        graph_digest=base.graph_digest, mutation_plan_digest="wa1-pilot/" + tag, view_digests=vd,
        public_files=public_files)


def _cancellation_ok(planted, scored):
    for n in range(1, len(planted) + 1):
        for subset in combinations(planted, n):
            total = {}
            for p in subset:
                for a, v in p.residual:
                    total[a] = total.get(a, Decimal("0")) + v
            if all(total.get(a, Decimal("0")) == 0 for a in scored):
                return False, [p.id for p in subset]
    return True, None


def build_pair(world, case_id, prompt, period, shared, target_rec, wrong_account,
               control_strategy="transpose_digits", control_parameter=2,
               wa_item_id="misbooked_supplier_payment", claim=""):
    control_task = TaskSpec(id=case_id + "_control", type="bank_reconciliation", prompt=prompt, period=period,
                            plan=MutationPlan(tuple(shared) + (AlterRecognition(
                                wa_item_id, target_rec, control_strategy, control_parameter, claim),)))
    base_task = TaskSpec(id=case_id + "_treatment", type="bank_reconciliation", prompt=prompt, period=period,
                         plan=MutationPlan(tuple(shared)))
    cb, cin = derive_contract(world, control_task)
    tb, tin = derive_contract(world, base_task)

    if cin.golden_text != tin.golden_text:
        raise PilotRefused("the arms do not share a golden")
    if cin.expected_balances != tin.expected_balances:
        raise PilotRefused("the arms do not share expected balances")

    rec = tb.recognition(target_rec)
    date = tb.effective_date(rec)
    right = [l for l in rec.legs if l.account != world.bank_account]
    if len(right) != 1 or len(rec.legs) != 2:
        raise PilotRefused("the target recognition is not a two-legged bank settlement")
    right_account, amount = right[0].account, right[0].amount
    header = '{0} * "{1}" "{2}"'.format(date, rec.payee, rec.narration)
    right_line = _posting_line(right_account, amount, world.currency)
    wrong_line = _posting_line(wrong_account, amount, world.currency)
    if len(right_line) != len(wrong_line):
        raise PilotRefused("the substituted posting line changes length")
    lines = tin.original_text.split("\n")
    hits = [i for i, l in enumerate(lines) if l == header]
    if len(hits) != 1:
        raise PilotRefused("the target entry header occurs {0} times".format(len(hits)))
    h = hits[0]
    block = lines[h + 1:h + 1 + len(rec.legs)]
    if block.count(right_line) != 1:
        raise PilotRefused("the target posting line is not unique inside its entry")
    lines[h + 1 + block.index(right_line)] = wrong_line
    spliced = "\n".join(lines)
    changed = sum(1 for a, b in zip(tin.original_text.split("\n"), lines) if a != b)
    if changed != 1:
        raise PilotRefused("the splice changed {0} lines".format(changed))

    tpub = dict(tin.public_files)
    tpub[LEDGER_VIEW] = spliced.encode("utf-8")
    tpub = tuple(sorted(tpub.items()))
    cpub = tuple(sorted(dict(cin.public_files).items()))
    differing = [n for (n, a), (_m, b) in zip(cpub, tpub) if a != b]
    if differing != [LEDGER_VIEW]:
        raise PilotRefused("the arms differ in {0}, not only the ledger".format(differing))

    required = tuple(sorted((l.account, canonical_decimal(l.amount)) for l in rec.legs))
    replaces = tuple(sorted(((wrong_account if a == right_account else a), v) for a, v in required))
    clean = dict((l.account, l.amount) for l in rec.legs)
    observed = dict(((wrong_account if a == right_account else a), v) for a, v in clean.items())
    accounts = list(clean) + [a for a in observed if a not in clean]
    residual = tuple((a, clean.get(a, Decimal("0")) - observed.get(a, Decimal("0"))) for a in accounts
                     if clean.get(a, Decimal("0")) - observed.get(a, Decimal("0")) != 0)
    statement = tb.view("bank_statement.csv")
    evidence = tuple(o.record for o in statement.observations if rec.event_id in o.node_ids)
    if not evidence:
        raise PilotRefused("no statement row evidences the target payment")
    wa = PlantedSpec(wa_item_id, rec.id, date, required, (rec.payee,), rec.narration, evidence, claim,
                     kind="alter", replaces=replaces, residual=residual)

    c_planted = tuple(cin.planted)
    t_planted = tuple(tin.planted) + (wa,)
    support = set(a for p in c_planted for a, _ in p.residual) | set(a for p in t_planted for a, _ in p.residual)
    scored = tuple(a for a in cin.allowed_accounts if a in support)
    for planted, label in ((c_planted, "control"), (t_planted, "treatment")):
        ok, subset = _cancellation_ok(planted, scored)
        if not ok:
            raise PilotRefused(label + ": planted residuals cancel on every target for " + str(subset))
        keys = [(p.date, p.required) for p in planted] + [(p.date, p.replaces) for p in planted if p.replaces]
        if len(set(keys)) != len(keys):
            raise PilotRefused(label + ": two planted items share a repair predicate")
        legs = [(a, v) for p in planted for a, v in p.required]
        for i, leg in enumerate(legs):
            if leg in legs[:i]:
                raise PilotRefused(label + ": two planted items share the leg " + str(leg))

    C = _remint(cin, control_task.id, prompt, c_planted, scored, cin.original_text, cpub, case_id + "/control")
    T = _remint(tin, base_task.id, prompt, t_planted, scored, spliced, tpub, case_id + "/treatment")
    report = {"case": case_id, "world": world.id, "target": target_rec, "payee": rec.payee,
              "date": date, "amount": str(amount), "right": right_account, "wrong": wrong_account,
              "scored": scored, "header": header, "was": right_line, "now": wrong_line,
              "wa_required": required, "wa_replaces": replaces, "wa_residual": residual}
    return C, T, report


def receipt_for(text, revision=1):
    return K.new_receipt("wa1", revision, env_mod.digests_of(text.encode("utf-8"), submitted=text))


def score(text, env):
    r = parse_once(text)
    if not isinstance(r, Accepted):
        return None, r
    return K.score_committed(K.commit(r, env, receipt_for(text))), None
