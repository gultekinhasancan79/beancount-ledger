"""Date lag: the day the bank saw it is not the day it happened.

Contract change B says an entry the books do not carry at all is posted on
the date the STATEMENT shows, because the transaction date went missing with
the entry and nothing public reveals it. That claim is only worth anything
where the two dates DIFFER, and the shipped world's two omissions happen to
be zero-lag: `rec:si-1044-receipt` and `rec:fee-2025-11` are recognised on
the day the bank saw them, so every one of Alpine's fixtures would pass
under the old contract too (Codex T43 §1, §8).

This suite builds the cases the shipped world does not have, as hand-authored
variants of Alpine's facts and nothing else — no literal posting, no literal
balance, no authored golden:

    positive-lag ACH receipt    recognised 24 Nov, credited 26 Nov
    positive-lag cheque debit   issued 18 Nov, presented 21 Nov
    zero lag                    a card payment and a bank charge, which pin
                                the ordinary case so "use the bank's date"
                                cannot be satisfied by ignoring dates
    month boundary              recognised 30 OCTOBER, credited 3 November —
                                the case `project.ledger()`'s omission branch
                                exists for and that 270 generated worlds
                                never produced

For each of them, three things are checked through the REAL loop
(`load_environment` -> `write_ledger` -> `score_core`): the bank-dated repair
scores 1.0, is COMPLETE and delivers a rendered file; the recognition-dated
repair does not resolve the item; and the expected balances and the golden
still come from the graph rather than from this file.

    python tests/test_lag.py
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:                                        # the dataset "Map:" bar is noise in a test log
    import datasets as _datasets
    _datasets.disable_progress_bar()
except Exception:                           # noqa: BLE001 - never a reason to fail the suite
    pass

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.graph import derive as DV  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402
from beancount_ledger.graph import project as PJ  # noqa: E402
from beancount_ledger.graph import schema as S  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402
from beancount_ledger.graph.worlds import alpine_2025_11 as A  # noqa: E402
from repair_keys import master_names, planted_key  # noqa: E402

BANK = "Assets:Bank:Checking"


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:20]:
            print(f"      {line}")
    return ok


# --------------------------------------------------------------------------
# world variants: Alpine's facts, with one settlement date moved
# --------------------------------------------------------------------------

def _replace_event(world, event_id, **fields):
    events = tuple(dataclasses.replace(e, **fields) if e.id == event_id else e for e in world.events)
    if events == world.events:
        raise AssertionError(f"fixture drift: {event_id} is not in the world")
    return dataclasses.replace(world, events=events)


def lagged_ach_receipt():
    """Harbor Freight's SI-1044 payment, received 24 Nov, credited 26 Nov."""
    world = _replace_event(A.WORLD, "event:si-1044-receipt", date="2025-11-24")
    return world, PJ.OmitRecognition(
        "unrecorded_customer_deposit", "rec:si-1044-receipt",
        "the 26 November statement row names the payer and the invoice; the books record nothing")


def lagged_cheque_debit():
    """The November office payment made by cheque on 18 Nov, presented 21 Nov."""
    world = _replace_event(A.WORLD, "event:office-2025-11",
                           settlement=S.Settlement(S.Rail.CHEQUE, "2025-11-21", "doc:chq-1040"),
                           memo="Stationery and printer supplies, check 1040")
    world = dataclasses.replace(world, documents=world.documents + (
        S.Document("doc:chq-1040", S.DocumentKind.CHEQUE, "1040", "party:office-depot", "2025-11-18"),))
    return world, PJ.OmitRecognition(
        "unrecorded_supplier_payment", "rec:office-2025-11",
        "the 21 November statement row names check 1040 and the supplier; the books record nothing")


def zero_lag_card():
    """The ordinary case: a card payment the bank saw the day it was made."""
    return A.WORLD, PJ.OmitRecognition(
        "unrecorded_card_payment", "rec:office-2025-11",
        "the 18 November card row names the supplier; the books record nothing")


def zero_lag_fee():
    """The other ordinary case: a charge the bank dates itself."""
    return A.WORLD, A.BANK_RECON_001.plan.mutations[1]


def month_boundary_receipt():
    """Recognised 30 OCTOBER, credited 3 NOVEMBER.

    Ridgeline Retail's SI-1029 payment moves from 9 October (received and
    cleared inside the prior period) to 30 October, cleared 3 November. The
    prior period's statement therefore shows it as an item still in flight at
    its own cut-off, the task period's statement carries the credit, and the
    opening receivables carry the 7,250.00 that had not arrived by 1 November.

    The recognition's OWN date is outside the task period, so an omission of
    it is `PLANTED_MUTATION` only because `project.ledger()` classifies the
    omission by the date the CORRECT books carry — the restated bank date —
    rather than by the date the graph drew. That is the branch this fixture
    exists to reach.
    """
    world = _replace_event(A.WORLD, "event:si-1029-receipt", date="2025-10-30",
                           settlement=S.Settlement(S.Rail.ACH_IN, "2025-11-03"))
    carried = tuple((account, value + Decimal("7250.00") if account == "Assets:AR" else value)
                    for account, value in world.opening.carried)
    world = dataclasses.replace(world, opening=S.OpeningPosition(world.opening.as_of, carried))
    return world, PJ.OmitRecognition(
        "unrecorded_customer_deposit", "rec:si-1029-receipt",
        "the 3 November statement row names the payer and last month's invoice; the books record nothing")


FIXTURES = {
    "ach receipt, +2 days": (lagged_ach_receipt, "2025-11-24", "2025-11-26"),
    "cheque debit, +3 days": (lagged_cheque_debit, "2025-11-18", "2025-11-21"),
    "card payment, no lag": (zero_lag_card, "2025-11-18", "2025-11-18"),
    "bank charge, no lag": (zero_lag_fee, "2025-11-30", "2025-11-30"),
    "ach receipt across the month boundary, +4 days": (month_boundary_receipt, "2025-10-30", "2025-11-03"),
}


def built(build):
    world, mutation = build()
    task = dataclasses.replace(A.BANK_RECON_001, id="bank_recon_lag_fixture",
                               plan=PJ.MutationPlan((mutation,)))
    bundle, inputs = DV.derive_contract(world, task)
    return world, task, bundle, inputs


# --------------------------------------------------------------------------
# the real loop, over a fixture world
# --------------------------------------------------------------------------

def loop(world, task):
    """`load_environment` over a fixture world, through the registry door the
    production composition root reads. Nothing else is stubbed: the contract,
    the parser, the allocation, the scorer, the renderer and the delivery are
    the production ones."""
    REGISTRY[task.id] = (world, task)
    try:
        env = env_mod.load_environment(task.id)
    finally:
        del REGISTRY[task.id]
    state = {}
    env._workspace(state)

    def write(text, call_id="c"):
        call = SimpleNamespace(id=call_id, name="write_ledger", arguments=json.dumps({"content": text}))
        return asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))
    return env, state, write


def entry_text(bundle, recognition_id, when):
    """The omitted entry as the projector would print it, on `when`. Built
    from the recognition's own legs so no posting is authored here."""
    rec = bundle.recognition(recognition_id)
    lines = [f'{when} * "{rec.payee}" "{rec.narration}"']
    for leg in rec.legs:
        lines.append(f"  {leg.account:<{PJ.POSTING_ACCOUNT_WIDTH}}"
                     f"{leg.amount:>{PJ.POSTING_AMOUNT_WIDTH}.2f} USD")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------

def test_the_repair_date_is_the_bank_date_at_every_lag():
    """One table, five rails and lags: the repair predicate, the expected
    ledger and the golden all carry the bank's date, and the graph says the
    recognition carries the other one."""
    problems = []
    seen_lags = set()
    for label, (build, recognised, banked) in FIXTURES.items():
        _world, _task, bundle, inputs = built(build)
        spec = inputs.planted[0]
        rec = bundle.recognition(spec.recognition_id)
        movement = next(m for m in bundle.movements if m.event_id == rec.event_id)
        seen_lags.add(banked != recognised)
        if rec.date != recognised or movement.cleared_on != banked:
            problems.append(f"{label}: fixture drift — recognised {rec.date}, banked {movement.cleared_on}")
            continue
        if spec.date != banked:
            problems.append(f"{label}: the planted repair is dated {spec.date}, not the bank's {banked}")
        if bundle.effective_date(rec) != banked:
            problems.append(f"{label}: the expected ledger dates it {bundle.effective_date(rec)}")
        if f"{banked} * " not in inputs.golden_text or (recognised != banked and f"{recognised} * " in inputs.golden_text):
            problems.append(f"{label}: the golden does not date the entry {banked}")
        restated = dict(bundle.restated)
        if (spec.recognition_id in restated) != (recognised != banked):
            problems.append(f"{label}: restated={restated} for recognised {recognised} banked {banked}")
    if seen_lags != {True, False}:
        problems.append("the fixture table does not cover both a positive lag and a zero lag")
    return check("at every rail and lag the planted repair, the expected ledger and the golden carry the "
                 "bank's date, and only a lagged item is restated", not problems, "\n".join(problems))


def test_the_bank_dated_repair_scores_one_and_the_recognition_dated_one_does_not():
    """The claim that matters, through the production loop.

    Writing the missing entry on the STATEMENT's date closes the month: 1.0,
    RESOLVED, complete, renderable, and a file is delivered. Writing the very
    same postings with the very same payee on the RECOGNITION's date does not
    resolve the item — the allocation's eligibility predicate is the date and
    the exact posting multiset — so it scores strictly less and the item is
    still MISSING. For a zero-lag fixture the two are the same submission and
    the second half is skipped, which is what "zero lag pins the ordinary
    case" means.
    """
    problems = []
    for label, (build, recognised, banked) in FIXTURES.items():
        world, task, bundle, inputs = built(build)
        spec = inputs.planted[0]
        env, state, write = loop(world, task)
        workspace = Path(state["workspace"])
        write(inputs.golden_text)
        score = env_mod.score_core(state)
        result = state["piv_result"]
        if score != 1.0 or not result.complete or not result.renderable or result.unresolved_planted:
            problems.append(f"{label}: the bank-dated golden scored {score} "
                            f"complete={result.complete} unresolved={result.unresolved_planted}")
        if not (workspace / env_mod.LEDGER).exists():
            problems.append(f"{label}: no deliverable was rendered for the bank-dated repair")
        if dict(result.allocation.item_states).get(spec.id) != "RESOLVED":
            problems.append(f"{label}: states {result.allocation.item_states}")
        if recognised == banked:
            continue
        wrong = inputs.original_text.rstrip("\n") + "\n\n" + entry_text(bundle, spec.recognition_id, recognised)
        write(wrong)
        score = env_mod.score_core(state)
        result = state["piv_result"]
        if score >= 1.0 or spec.id not in result.unresolved_planted \
                or dict(result.allocation.item_states).get(spec.id) != "MISSING":
            problems.append(f"{label}: the recognition-dated entry scored {score} with states "
                            f"{result.allocation.item_states}")
        # the entry on the wrong date matches no planted predicate and no
        # pre-existing occurrence, so it is an unexplained addition
        if not result.fabricated:
            problems.append(f"{label}: an entry on the wrong date was not reported as unexplained")
    return check("the bank-dated repair scores 1.0 and renders at every lag; the recognition-dated repair "
                 "resolves nothing and is unexplained", not problems, "\n".join(problems))


def test_the_month_boundary_case_reaches_the_omission_branch():
    """`project.ledger()`'s omission branch, and why nothing else reaches it.

    The branch classifies an omitted recognition by the date the CORRECT
    books carry it — `restated.get(rec.id, rec.date)` — rather than by the
    date the graph drew, so an entry recognised on 30 October and credited on
    3 November is absent from the opening ledger for the PLANTED reason and
    not for being out of period. This fixture is the only thing in the
    repository that reaches it: with the raw recognition date the same world
    classifies the omission `OUTSIDE_PERIOD`, `derive_contract` refuses it
    ("the projector did not omit"), and there would be no planted item at all.
    """
    world, task, bundle, inputs = built(month_boundary_receipt)
    spec = inputs.planted[0]
    rec = bundle.recognition(spec.recognition_id)
    absences = {a.node_id: (a.reason, a.mutation_id) for a in bundle.view(PJ.LEDGER_VIEW).absences}
    problems = []
    if task.period.contains(rec.date):
        problems.append(f"fixture drift: {rec.date} is inside the task period")
    if absences.get(rec.id) != (PJ.Reason.PLANTED_MUTATION, spec.id):
        problems.append(f"the omission is absent as {absences.get(rec.id)}, not for the planted reason")
    if rec.id not in dict(bundle.restated):
        problems.append("the recognition was not restated onto the bank's date")
    # the counterfactual: without the restatement the branch takes the other
    # arm, and the derivation refuses the plan outright
    if PJ.Period(task.period.start, task.period.end, "").contains(rec.date):
        problems.append("the counterfactual is vacuous: the raw date is in period")
    # the prior statement shows it as an item still in flight at ITS cut-off
    archive = bundle.view(PJ.ARCHIVE_VIEW)
    movement = next(m for m in bundle.movements if m.event_id == rec.event_id)
    if not any(a.node_id == movement.id and a.reason is PJ.Reason.NOT_YET_SETTLED for a in archive.absences):
        problems.append("the prior statement does not classify the movement as not yet settled")
    if "2025-11-03" not in bundle.view(PJ.STATEMENT_VIEW).text:
        problems.append("the task period's statement does not carry the credit")
    # the books still balance, from both sides, and the public reading is unique
    if DV.derive_contract(world, task)[1].expected_balances != inputs.expected_balances:
        problems.append("the derivation is not deterministic")
    if PJ.check_bundle(world, bundle):
        problems.append(f"accounting invariants: {PJ.check_bundle(world, bundle)}")
    public = {name: data.decode("utf-8") for name, data in inputs.public_files}
    verdict = ID.check_identifiable(public, bank_account=BANK,
                                    period_start=task.period.start, period_end=task.period.end)
    want = sorted(planted_key(p, master_names(public), bank_account=BANK) for p in inputs.planted)
    got = sorted(ID.repair_key(r) for r in verdict.repairs)
    if not verdict.unique or want != got:
        problems.append(f"public reading: unique={verdict.unique} planted={want} checker={got}\n{verdict.reason[:300]}")
    return check("a recognition in the prior period whose bank row is in the task period is omitted for the "
                 "planted reason, keeps the accounting invariants, and reads back uniquely",
                 not problems, "\n".join(problems))


def test_the_generator_cannot_draw_a_month_boundary_omission():
    """Why 270 generated worlds never reached that branch — structurally.

    `generate._facts` clamps every settlement to its own period: a prior
    period event clears at `_clears(rng, when, q_end)` or on its own day, so
    it never reaches the task period; a task period event is issued at
    `_business_day(rng, p_start, ...)`, so it never starts before it. The one
    settlement that crosses a month boundary is the prepayment cheque, which
    clears AFTER the cut-off and therefore has no statement row to be omitted
    from — `_plan` skips it because `Prepayment` is not in `_OMIT_ID` and
    because `period.contains(movement.cleared_on)` is false.

    Asserted over a sample rather than by reading the source: no event in a
    generated world has its own date and its bank row in different periods on
    the side that matters, so no plan can ever produce the case above.
    """
    import os
    os.environ.setdefault("PIV_EVAL_SECRET", "5f1c7b9e2a4d6c8b0e1f3a5c7d9b2e4f6a8c0d2e4f6a8b0c1d3e5f7a9b1c3d5e")
    os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")
    from beancount_ledger.graph.generate import DEFAULT_PROFILE, HARD_PROFILE
    from beancount_ledger.graph.mint import mint

    problems = []
    crossings = 0
    checked = 0
    for index in range(12):
        for profile in (DEFAULT_PROFILE, HARD_PROFILE):
            minted = mint("train", index, profile)
            period = minted.task.period
            checked += 1
            for movement in minted.bundle.movements:
                event_date = minted.world.event(movement.event_id).date
                if period.contains(movement.cleared_on) and not period.contains(event_date):
                    crossings += 1
            for spec in minted.inputs.planted:
                rec = minted.bundle.recognition(spec.recognition_id)
                if not period.contains(rec.date):
                    problems.append(f"train:{index}: {spec.id} is planted on a recognition dated {rec.date}, "
                                    f"outside {period.start}..{period.end}")
    if crossings:
        problems.append(f"{crossings} generated movements cleared in the period for an event dated outside it; "
                        f"the branch IS reachable from the generator and the fixture is no longer the only route")
    return check(f"no generated world ({checked} minted) draws an event dated in one period and cleared in "
                 f"the next, so the month-boundary branch is unreachable from the generator and the hand-built "
                 f"fixture is what covers it", not problems, "\n".join(problems))


TESTS = [
    test_the_repair_date_is_the_bank_date_at_every_lag,
    test_the_bank_dated_repair_scores_one_and_the_recognition_dated_one_does_not,
    test_the_month_boundary_case_reaches_the_omission_branch,
    test_the_generator_cannot_draw_a_month_boundary_omission,
]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
