"""The world graph as production authority.

What is proved here, in order: the shipped public files ARE the graph's
projection (byte for byte); the golden solution IS the expected-ledger
projection (structurally); the archived task file IS derived (normative
key for key); the three ways a record can be "missing somewhere" are three
typed reasons; identity is order-free and one fact moves only the views it
touches; literal contract inputs are refused; no private id reaches
anything public; the hand-reviewed facts catch a policy the projector and
the Beancount oracle would agree with; and the accounting invariants refuse
a generator that gets the books wrong.

    python tests/test_graph.py
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate.canonical import canonical_decimal  # noqa: E402
from beancount_ledger.candidate.normalise import parse_once  # noqa: E402
from beancount_ledger.graph import derive as DV  # noqa: E402
from beancount_ledger.graph import policy as PL  # noqa: E402
from beancount_ledger.graph import project as PJ  # noqa: E402
from beancount_ledger.graph import schema as S  # noqa: E402
from beancount_ledger.graph.worlds import alpine_2025_11 as A  # noqa: E402

WORLD_DIR = ROOT / "beancount_ledger" / "world"
ARCHIVED_TASK = ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json"
GOLDEN = ROOT / "tests" / "solutions" / "golden.beancount"
PRIVATE_ID = re.compile(r"\b(rec|mov|event|party|doc):[a-z0-9][a-z0-9\-]*\b")


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:20]:
            print(f"      {line}")
    return ok


def derive(world=A.WORLD, task=A.BANK_RECON_001):
    return DV.derive_contract(world, task)


def test_the_shipped_world_is_the_projection():
    bundle, inputs = derive()
    problems = []
    files = dict(inputs.public_files)
    if set(files) != set(env_mod.PUBLIC_FILES):
        problems.append(f"manifest mismatch: {set(files) ^ set(env_mod.PUBLIC_FILES)}")
    for name, data in files.items():
        if (WORLD_DIR / name).read_bytes() != data:
            problems.append(f"{name}: the shipped file differs from the projection")
    return check("every shipped public file is byte-identical to the graph's projection (the directory is a cache)",
                 not problems, "\n".join(problems))


def test_the_golden_solution_is_the_expected_projection():
    _, inputs = derive()
    g = parse_once(GOLDEN.read_text(encoding="utf-8"))
    e = parse_once(inputs.golden_text)
    ok = (g.candidate_digest == e.candidate_digest and g.semantic_fingerprint == e.semantic_fingerprint
          and inputs.golden_text != GOLDEN.read_text(encoding="utf-8"))
    return check("the golden solution is structurally the expected-ledger projection (text differs: entry order)",
                 ok, f"structural {g.candidate_digest == e.candidate_digest} semantic {g.semantic_fingerprint == e.semantic_fingerprint}")


def test_the_archived_task_file_is_derived():
    _, inputs = derive()
    archived = json.loads(ARCHIVED_TASK.read_text(encoding="utf-8"))
    normative = {k: v for k, v in archived.items() if not k.startswith("_")}
    for item in normative["planted"]:
        item.pop("description", None)
    for item in normative["traps"]:
        item.pop("description", None)
    derived = inputs.legacy_task_view()
    for view in (normative, derived):      # posting order inside a predicate is not semantic; the scorer sorts
        for item in view["planted"]:
            item["required_postings"] = sorted(item["required_postings"])
    problems = [f"{k}: archived {normative.get(k)!r} vs derived {derived.get(k)!r}"
                for k in sorted(set(normative) | set(derived)) if normative.get(k) != derived.get(k)]
    return check("every normative key of the archived task file is reproduced from the graph", not problems, "\n".join(problems))


def test_three_kinds_of_missing_are_three_reasons():
    bundle, _ = derive()
    ledger, statement = bundle.view(PJ.LEDGER_VIEW), bundle.view(PJ.STATEMENT_VIEW)

    def reason(view, node_id):
        if node_id in view.subjects():
            return PJ.Reason.PRESENT
        return next((a.reason, a.mutation_id) for a in view.absences if a.node_id == node_id)

    problems = []
    cases = {
        ("rec:rent-2025-12-prepaid", ledger): PJ.Reason.PRESENT,
        ("mov:rent-2025-12-prepaid", statement): (PJ.Reason.NOT_YET_SETTLED, None),
        ("rec:si-1044-receipt", ledger): (PJ.Reason.PLANTED_MUTATION, "unrecorded_customer_deposit"),
        ("mov:si-1044-receipt", statement): PJ.Reason.PRESENT,
        ("rec:fee-2025-11", ledger): (PJ.Reason.PLANTED_MUTATION, "unrecorded_bank_fee"),
        ("mov:fee-2025-11", statement): PJ.Reason.PRESENT,
        ("rec:fee-2025-10", ledger): (PJ.Reason.OUTSIDE_PERIOD, None),
        ("mov:fee-2025-10", statement): (PJ.Reason.OUTSIDE_PERIOD, None),
        ("mov:fee-2025-10", bundle.view(PJ.ARCHIVE_VIEW)): PJ.Reason.PRESENT,
        ("mov:si-1043-receipt", ledger): (PJ.Reason.NOT_APPLICABLE_TO_VIEW, None),
        ("rec:si-1043-receipt", statement): (PJ.Reason.NOT_APPLICABLE_TO_VIEW, None),
        ("doc:si-1044", ledger): (PJ.Reason.REDACTED_BY_PUBLIC_POLICY, None),
        ("doc:si-1044", bundle.view(PJ.CUSTOMERS_VIEW)): (PJ.Reason.REDACTED_BY_PUBLIC_POLICY, None),
        ("party:cascade-bank", bundle.view(PJ.VENDORS_VIEW)): (PJ.Reason.NOT_APPLICABLE_TO_VIEW, None),
    }
    for (node, view), want in cases.items():
        got = reason(view, node)
        if got != want:
            problems.append(f"{view.name} / {node}: {got} != {want}")
    expected = bundle.view(PJ.EXPECTED_LEDGER_VIEW)
    if "mov:fee-2025-10" not in statement.sources():
        problems.append("the statement's opening row does not carry the prior movements as provenance")
    if "rec:si-1044-receipt" not in expected.subjects() or "rec:fee-2025-11" not in expected.subjects():
        problems.append("the expected ledger lacks an omitted recognition")
    return check("outstanding cheque / planted omission / redacted invoice / out-of-period / wrong view: five typed reasons",
                 not problems, "\n".join(problems))


def test_an_unclassified_record_fails_the_projection():
    bundle, _ = derive()
    ledger = bundle.view(PJ.LEDGER_VIEW)
    hole = dataclasses.replace(ledger, absences=tuple(a for a in ledger.absences if a.node_id != "mov:fee-2025-11"))
    views = tuple(hole if v.name == PJ.LEDGER_VIEW else v for v in bundle.views)
    problems = []
    try:
        PJ._assert_exhaustive(views, bundle.recognitions, bundle.movements)
        problems.append("a view with an unclassified movement passed")
    except PJ.ProjectionError as exc:
        if "unclassified" not in str(exc):
            problems.append(f"wrong reason: {exc}")
    twice = dataclasses.replace(ledger, absences=ledger.absences + (PJ.Absence(PJ.LEDGER_VIEW, "rec:si-1043-receipt",
                                                                               PJ.Reason.OUTSIDE_PERIOD),))
    try:
        PJ._assert_exhaustive(tuple(twice if v.name == PJ.LEDGER_VIEW else v for v in bundle.views),
                              bundle.recognitions, bundle.movements)
        problems.append("a record both emitted and absent passed")
    except PJ.ProjectionError:
        pass
    return check("an unclassified or doubly-classified consequence is a projection failure", not problems, "\n".join(problems))


def test_identity_is_free_of_insertion_order():
    reordered = dataclasses.replace(
        A.WORLD, accounts=tuple(reversed(A.WORLD.accounts)), parties=tuple(reversed(A.WORLD.parties)),
        documents=tuple(reversed(A.WORLD.documents)), events=tuple(reversed(A.WORLD.events)),
        roles=tuple(reversed(A.WORLD.roles)))
    a, ia = derive()
    b, ib = derive(reordered)
    problems = []
    if a.graph_digest != b.graph_digest:
        problems.append("graph digest depends on insertion order")
    if a.view_digests() != b.view_digests():
        problems.append("a view digest depends on insertion order")
    if ia.contract_view() != ib.contract_view():
        problems.append("the contract inputs depend on insertion order")
    if dict(ia.public_files) != dict(ib.public_files):
        problems.append("a public file depends on insertion order")
    return check("reversing every node tuple leaves graph, view and contract identity unchanged", not problems, "\n".join(problems))


def test_one_fact_moves_only_the_views_it_touches():
    base, _ = derive()

    def replaced(event_id, **changes):
        events = tuple(dataclasses.replace(e, **changes) if e.id == event_id else e for e in A.WORLD.events)
        return derive(dataclasses.replace(A.WORLD, events=events))[0]

    problems = []
    office = replaced("event:office-2025-11", amount=Decimal("425.00"))
    moved = {n for (n, d), (_, d2) in zip(base.view_digests(), office.view_digests()) if d != d2}
    want = {PJ.LEDGER_VIEW, PJ.EXPECTED_LEDGER_VIEW, PJ.STATEMENT_VIEW, PJ.EXPECTED_BALANCES_VIEW}
    if moved != want:
        problems.append(f"office supplies 420->425 moved {sorted(moved)}, expected {sorted(want)}")
    if office.graph_digest == base.graph_digest:
        problems.append("a changed fact left the graph digest unchanged")
    fee = replaced("event:fee-2025-10", amount=Decimal("120.00"))
    moved = {n for (n, d), (_, d2) in zip(base.view_digests(), fee.view_digests()) if d != d2}
    want = {PJ.LEDGER_VIEW, PJ.EXPECTED_LEDGER_VIEW, PJ.STATEMENT_VIEW, PJ.ARCHIVE_VIEW, PJ.EXPECTED_BALANCES_VIEW}
    if moved != want:
        problems.append(f"October fee 115->120 moved {sorted(moved)}, expected {sorted(want)} (carry-forward)")
    if fee.opening_bank_balance != base.opening_bank_balance - Decimal("5"):
        problems.append("the prior-period fee did not flow into the opening bank balance")
    if fee.plan is not base.plan or fee.mutation_plan_digest != base.mutation_plan_digest:
        problems.append("a fact change moved the mutation plan digest")
    return check("one changed fact moves exactly its views; a prior-period fee moves the archive, the carry-forward and nothing else",
                 not problems, "\n".join(problems))


def test_literal_contract_inputs_are_refused():
    _, inputs = derive()
    problems = []
    fields = {f.name: getattr(inputs, f.name) for f in dataclasses.fields(inputs) if f.name != "_mint"}
    try:
        DV.ContractInputs(**fields)
        problems.append("a hand-built ContractInputs was minted")
    except TypeError:
        pass
    try:
        dataclasses.replace(inputs, expected_balances=tuple((a, v + 1) for a, v in inputs.expected_balances))
        problems.append("replace() re-minted with a literal balance")
    except TypeError:
        pass
    for bad in (fields, inputs.legacy_task_view(), "inputs", None):
        try:
            K.load_contract(bad)
            problems.append(f"load_contract accepted {type(bad).__name__}")
        except TypeError:
            pass
    env = K.load_contract(inputs)
    if env.graph_digest != inputs.graph_digest or env.world_id != "alpine-2025-11":
        problems.append("the loaded environment does not carry the graph identity")
    if env.environment_digest == K.load_contract(derive(A.WORLD, dataclasses.replace(
            A.BANK_RECON_001, plan=PJ.MutationPlan(A.BANK_RECON_001.plan.mutations[:1])))[1]).environment_digest:
        problems.append("a different mutation plan produced the same environment")
    return check("literal ContractInputs, replace(), dicts and strings are refused; the minted inputs load and carry graph identity",
                 not problems, "\n".join(problems))


def test_no_private_id_reaches_anything_public():
    bundle, inputs = derive()
    texts = {name: data.decode("utf-8") for name, data in inputs.public_files}
    texts["prompt"] = inputs.prompt
    texts["system_prompt"] = env_mod.SYSTEM_PROMPT
    ids = {r.id for r in bundle.recognitions} | {m.id for m in bundle.movements} | {e.id for e in A.WORLD.events} \
        | {p.id for p in A.WORLD.parties} | {d.id for d in A.WORLD.documents}
    problems = []
    for name, text in texts.items():
        for hit in sorted(i for i in ids if i in text):
            problems.append(f"{name}: contains private id {hit}")
        for hit in PRIVATE_ID.findall(text):
            problems.append(f"{name}: id-shaped token {hit}")
        for m in A.BANK_RECON_001.plan.mutations:
            if m.mutation_id in text:
                problems.append(f"{name}: names the mutation {m.mutation_id}")
    return check("no recognition, movement, event, party, document or mutation id appears in any public text",
                 not problems, "\n".join(problems))


# Hand-reviewed economic facts. Amounts, dates, counterparties and where the
# policy says they land — never a posting vector or a closing balance of
# the books. The bank's own closing figure is an external observation, not
# an answer, and belongs here.
SCENARIO_FACTS = [
    ("SI-1044 gross receipt of 4,800 on 2025-11-26 applies to Harbor Freight's receivable",
     lambda b: b.recognition("rec:si-1044-receipt").date == "2025-11-26"
     and b.recognition("rec:si-1044-receipt").net_on("Assets:AR") == Decimal("-4800.00")
     and b.recognition("rec:si-1044-receipt").payee == "Harbor Freight Ltd"),
    ("the November service charge of 85 lands in Expenses:BankFees on 2025-11-30",
     lambda b: b.recognition("rec:fee-2025-11").net_on("Expenses:BankFees") == Decimal("85.00")
     and b.recognition("rec:fee-2025-11").date == "2025-11-30"),
    ("cheque 1038 for 3,500 recorded 2025-11-28 is a prepayment and the bank cleared it on 2025-12-03",
     lambda b: b.recognition("rec:rent-2025-12-prepaid").net_on("Assets:Prepayments") == Decimal("3500.00")
     and next(m for m in b.movements if m.id == "mov:rent-2025-12-prepaid").cleared_on == "2025-12-03"),
    ("the bank's November statement closes at 54,545.00 and opens at October's close of 42,150.00",
     lambda b: b.view(PJ.STATEMENT_VIEW).text.splitlines()[-1].endswith(",54545.00")
     and b.view(PJ.STATEMENT_VIEW).text.splitlines()[1].endswith(",42150.00")
     and b.view(PJ.ARCHIVE_VIEW).text.splitlines()[-1].endswith(",42150.00")),
    ("SI-1051 is a 12,000 sale taxed at 20% with 7,800 cost, of which 8,000 was received on 2025-11-25",
     lambda b: b.recognition("rec:si-1051-sale").net_on("Liabilities:SalesTax-Payable") == Decimal("-2400.00")
     and b.recognition("rec:si-1051-sale-cost").net_on("Expenses:COGS") == Decimal("7800.00")
     and b.recognition("rec:si-1051-receipt").net_on("Assets:Bank:Checking") == Decimal("8000.00")),
]


def test_hand_reviewed_facts_hold():
    bundle, _ = derive()
    failed = [label for label, holds in SCENARIO_FACTS if not holds(bundle)]
    return check(f"{len(SCENARIO_FACTS)} hand-reviewed economic facts hold against the projection", not failed, "\n".join(failed))


def test_the_facts_catch_what_the_oracle_cannot():
    """A consistently wrong policy: fees to Expenses:Office. The projector
    renders it, Beancount books it, every balance refolds, the invariants
    pass — and only the hand-reviewed fact says no."""
    real = PL.recognitions_of

    def wrong(world, roles, event):
        recs = real(world, roles, event)
        if isinstance(event, S.BankFee):
            rec = recs[0]
            legs = tuple(PL.Leg("Expenses:Office", l.amount) if l.account == roles.bank_fees else l for l in rec.legs)
            return (dataclasses.replace(rec, legs=legs),)
        return recs

    PJ.recognitions_of = wrong
    try:
        bundle, inputs = derive()
        oracle_agreed = dict(inputs.expected_balances)["Expenses:Office"] == Decimal("505.00")
        failed = [label for label, holds in SCENARIO_FACTS if not holds(bundle)]
    finally:
        PJ.recognitions_of = real
    ok = oracle_agreed and any("BankFees" in f for f in failed)
    return check("a self-consistent wrong policy passes the projector and the Beancount oracle and fails the hand-reviewed facts",
                 ok, f"oracle agreed: {oracle_agreed}; facts failed: {failed}")


def test_planted_predicates_are_the_recognitions():
    bundle, inputs = derive()
    problems = []
    for p in inputs.planted:
        rec = bundle.recognition(p.recognition_id)
        if p.date != rec.date or set(p.required) != {(l.account, canonical_decimal(l.amount)) for l in rec.legs}:
            problems.append(f"{p.id}: predicate is not the recognition's legs/date")
        if p.must_be_payee != (rec.payee,):
            problems.append(f"{p.id}: accepted counterparty is not the recognition's payee")
        for record in p.evidence:
            date, _, description = record.partition(" ")
            if f"{date},{description}," not in bundle.view(PJ.STATEMENT_VIEW).text:
                problems.append(f"{p.id}: evidence {record!r} is not a statement row")
    if inputs.scored_accounts != ("Assets:Bank:Checking", "Assets:AR", "Expenses:BankFees"):
        problems.append(f"scored accounts derived as {inputs.scored_accounts}")
    if [t.id for t in inputs.traps] != ["outstanding_check_1038"]:
        problems.append(f"traps derived as {[t.id for t in inputs.traps]}")
    return check("planted date/postings/payee/evidence, scored accounts and traps are read off the graph", not problems, "\n".join(problems))


def test_malformed_plans_and_worlds_are_refused():
    problems = []
    plans = {
        "unknown recognition": PJ.MutationPlan((PJ.OmitRecognition("x", "rec:nope", "?"),)),
        "one recognition twice": PJ.MutationPlan((PJ.OmitRecognition("a", "rec:fee-2025-11", "?"),
                                                  PJ.OmitRecognition("b", "rec:fee-2025-11", "?"))),
    }
    for label, plan in plans.items():
        try:
            derive(A.WORLD, dataclasses.replace(A.BANK_RECON_001, plan=plan))
            problems.append(f"{label}: derived")
        except PJ.ProjectionError:
            pass
    try:   # omit a recognition the statement never evidences: not inferable
        derive(A.WORLD, dataclasses.replace(A.BANK_RECON_001, plan=PJ.MutationPlan(
            (PJ.OmitRecognition("hidden", "rec:pi-2240-receipt", "?"),))))
        problems.append("an omission with no public evidence derived")
    except DV.DerivationError as exc:
        if "inferable" not in str(exc):
            problems.append(f"wrong reason: {exc}")

    def world(**changes):
        return dataclasses.replace(A.WORLD, **changes)

    def event(event_id, **changes):
        return tuple(dataclasses.replace(e, **changes) if e.id == event_id else e for e in A.WORLD.events)

    def doc(doc_id, **changes):
        return tuple(dataclasses.replace(d, **changes) if d.id == doc_id else d for d in A.WORLD.documents)

    worlds = {
        "invoice gross disagrees with net+tax": (world(documents=doc("doc:si-1044", gross=Decimal("4800.01"))), DV.DerivationError, "gross"),
        "receipt exceeds the invoice": (world(events=event("event:si-1044-receipt", amount=Decimal("4900.00"))), DV.DerivationError, "exceed"),
        "opening receivables below prior invoices settled": (world(opening=S.OpeningPosition("2025-11-01", (
            ("Assets:AR", Decimal("9000.00")), ("Assets:Inventory", Decimal("26000.00")), ("Liabilities:AP", Decimal("-11300.00"))))),
            DV.DerivationError, "receivables"),
        "a cheque without its number": (world(events=event("event:rent-2025-11", settlement=S.Settlement(S.Rail.CHEQUE, "2025-11-10"))),
                                        PJ.ProjectionError, "cheque"),
        "a receipt by card": (world(events=event("event:si-1043-receipt", settlement=S.Settlement(S.Rail.CARD, "2025-11-06"))),
                              PJ.ProjectionError, "cannot arrive"),
        "a three-place amount": (world(events=event("event:office-2025-11", amount=Decimal("420.005"))), PJ.ProjectionError, "two-place"),
        "a non-NFC string": (world(events=event("event:office-2025-11", memo="Café supplies")), PJ.ProjectionError, "NFC"),
        "the bank balance authored in the opening position": (world(opening=S.OpeningPosition("2025-11-01", (
            ("Assets:Bank:Checking", Decimal("42150.00")), ("Assets:AR", Decimal("18400.00"))))), PJ.ProjectionError, "derived"),
        "a plug-named account": (world(accounts=A.WORLD.accounts + (S.Account("Expenses:Misc", S.AccountKind.EXPENSE, "?", "2025-01-01", 5400),)),
                                 PJ.ProjectionError, "plug"),
        "cleared before it happened": (world(events=event("event:office-2025-11", settlement=S.Settlement(S.Rail.CARD, "2025-11-17"))),
                                       PJ.ProjectionError, "cleared before"),
    }
    for label, (w, kind, needle) in worlds.items():
        try:
            derive(w)
            problems.append(f"{label}: derived")
        except kind as exc:
            if needle not in str(exc):
                problems.append(f"{label}: refused for another reason: {str(exc)[:120]}")
        except Exception as exc:
            problems.append(f"{label}: raised {type(exc).__name__}: {str(exc)[:120]}")
    return check(f"{len(plans) + 1 + len(worlds)} malformed plans and worlds are refused, each for its stated reason",
                 not problems, "\n".join(problems))


def test_the_reconciliation_identity_from_both_sides():
    bundle, inputs = derive()
    books = dict(inputs.expected_balances)["Assets:Bank:Checking"]
    unsettled = sum((m.amount for m in bundle.movements
                     if any(a.node_id == m.id and a.reason is PJ.Reason.NOT_YET_SETTLED for a in bundle.view(PJ.STATEMENT_VIEW).absences)),
                    Decimal("0"))
    opening_ledger = parse_once(inputs.original_text).candidate.balances["Assets:Bank:Checking"]
    omitted = sum((bundle.recognition(p.recognition_id).net_on("Assets:Bank:Checking") for p in inputs.planted), Decimal("0"))
    from_statement = inputs.statement_closing + unsettled
    from_ledger = opening_ledger + omitted
    ok = from_statement == books == from_ledger
    return check("statement close + unsettled == books == opening ledger + omitted recognitions", ok,
                 f"statement {inputs.statement_closing} + {unsettled} = {from_statement}; ledger {opening_ledger} + {omitted} = {from_ledger}; books {books}")


def test_the_production_root_is_graph_backed():
    env = env_mod.load_environment()
    _, inputs = derive()
    problems = []
    if env.contract.graph_digest != inputs.graph_digest or env.public_files != dict(inputs.public_files):
        problems.append("the production environment does not carry the graph's contract and files")
    src = (ROOT / "beancount_ledger" / "beancount_ledger.py").read_text(encoding="utf-8")
    for needle in ("load_task(", "candidate.compat", "import compat", "_archived_literal_inputs", "copytree(WORLD_DIR"):
        if needle in src:
            problems.append(f"production module references {needle}")
    # the first graph prototype is archived outside the package: nothing imports it, and it is not importable
    if (ROOT / "beancount_ledger" / "canonical").exists():
        problems.append("the archived canonical/ prototype is still inside the package")
    for py in (ROOT / "beancount_ledger").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "beancount_ledger.canonical" in text or "from ..canonical" in text or "from .canonical import" in text and "candidate" not in str(py):
            problems.append(f"{py.name} references the archived canonical package")
    state = {}
    env._workspace(state)
    ws = Path(state["workspace"])
    for name, data in inputs.public_files:
        if (ws / name).read_bytes() != data:
            problems.append(f"workspace {name} is not the projection")
    return check("load_environment derives from the graph, seeds the workspace from the projection, never reads a task file",
                 not problems, "\n".join(problems))


def test_the_named_inverse_returns_the_clean_fingerprint():
    """clean projection -> planted mutation -> inverse (append the omitted
    recognitions, rendered by the same rules) == the expected ledger,
    by semantic fingerprint and by candidate balances."""
    bundle, inputs = derive()
    repaired = inputs.original_text
    for p in inputs.planted:
        rec = bundle.recognition(p.recognition_id)
        entry = [f'{rec.date} * "{rec.payee}" "{rec.narration}"'] + [
            f"  {l.account:<40}{l.amount:>9.2f} {inputs.currency}" for l in rec.legs]
        repaired += "\n" + "\n".join(entry) + "\n"
    a, b = parse_once(repaired), parse_once(inputs.golden_text)
    ok = a.semantic_fingerprint == b.semantic_fingerprint and a.candidate.balances == b.candidate.balances \
        and parse_once(inputs.original_text).semantic_fingerprint != b.semantic_fingerprint
    return check("opening ledger + omitted recognitions == expected ledger (fingerprint and balances); opening alone differs",
                 ok, f"{a.semantic_fingerprint[:12]} vs {b.semantic_fingerprint[:12]}")


def test_derived_answers_are_unrepresentable_in_the_authored_layer():
    """Codex T39 (rewrite) §7/§10: overrides are impossible by type — an
    alias field on any authored node is a construction error — and no
    derived number (a closing balance, the opening bank balance, the equity
    plug, the statement close) appears as a literal in the world module."""
    problems = []
    for label, build in {
        "TaskSpec.expected_balance_override": lambda: DV.TaskSpec(id="t", type="bank_reconciliation", prompt="p", period=A.BANK_RECON_001.period,
                                                                  plan=A.BANK_RECON_001.plan, expected_balance_override={"Assets:AR": "1"}),
        "OmitRecognition.accepted_payees": lambda: PJ.OmitRecognition("m", "rec:fee-2025-11", "c", accepted_payees=("X",)),
        "World.target_hint": lambda: dataclasses.replace(A.WORLD, target_hint="51045.00"),
        "MutationPlan.required_postings": lambda: PJ.MutationPlan((), required_postings=[]),
        "Sale.gross": lambda: S.Sale("event:x", "2025-11-01", "party:harbor-freight", "doc:si-1044", Decimal("1"), Decimal("0"), Decimal("0"), "m", "c", gross=Decimal("1")),
    }.items():
        try:
            build()
            problems.append(f"{label}: constructed")
        except TypeError:
            pass
    _, inputs = derive()
    derived_numbers = {f"{abs(v):.2f}" for _, v in inputs.expected_balances if v != 0}
    derived_numbers |= {f"{inputs.statement_closing:.2f}", "42150.00"}
    authored = {f"{abs(getattr(e, a)):.2f}" for e in A.WORLD.events for a in ("amount", "net", "cost") if hasattr(e, a)}
    authored |= {f"{abs(v):.2f}" for _, v in A.WORLD.opening.carried} | {f"{A.WORLD.bank_opening.balance:.2f}"}
    authored |= {f"{d.gross:.2f}" for d in A.WORLD.documents if d.gross is not None}
    src = (ROOT / "beancount_ledger" / "graph" / "worlds" / "alpine_2025_11.py").read_text(encoding="utf-8")
    for number in sorted(derived_numbers - authored):
        if number in src:
            problems.append(f"derived number {number} appears as a literal in the authored world")
    if not (derived_numbers - authored):
        problems.append("the scan is vacuous: every derived number is also an authored fact")
    return check("alias/override fields fail by type on every authored node; no derived number is a literal in the world module",
                 not problems, "\n".join(problems))


def _plan(*mutations):
    return dataclasses.replace(A.BANK_RECON_001, plan=PJ.MutationPlan(tuple(mutations)))


ALTER_OFFICE = PJ.AlterRecognition("office_transposed", "rec:office-2025-11", "transpose_digits", 0,
                                   "the statement shows DEBIT CARD OFFICE DEPOT 420.00; the books say 240.00")
DUP_RENT = PJ.DuplicateRecognition("rent_booked_twice", "rec:rent-2025-11",
                                   "the statement shows CHECK 1037 once; the books carry November rent twice")


def test_alter_and_duplicate_project_and_derive():
    """M1: two more mutation kinds over derived recognitions. The opening
    ledger carries the wrong vector (alter) or two copies (duplicate); the
    expected ledger is unchanged; the planted spec names the truth, the
    wrong shape it replaces, and the evidence row."""
    problems = []
    bundle, inputs = derive(A.WORLD, _plan(ALTER_OFFICE, DUP_RENT))
    ledger = bundle.view(PJ.LEDGER_VIEW).text
    if ledger.count("240.00 USD") != 2 or "420.00 USD" in ledger:
        problems.append("the altered entry is not what the opening ledger shows")
    if ledger.count('"Cedar Property Group" "November office rent"') != 2:
        problems.append("the duplicated entry does not appear twice")
    expected = bundle.view(PJ.EXPECTED_LEDGER_VIEW).text
    if "240.00 USD" in expected or expected.count('"November office rent"') != 1:
        problems.append("the expected ledger was mutated")
    reasons = {a.node_id: (a.reason, a.mutation_id) for a in bundle.view(PJ.LEDGER_VIEW).absences}
    if reasons.get("rec:office-2025-11") != (PJ.Reason.PLANTED_MUTATION, "office_transposed"):
        problems.append(f"the altered recognition is not absent for the planted reason: {reasons.get('rec:office-2025-11')}")
    mutant_rows = [o for o in bundle.view(PJ.LEDGER_VIEW).observations if o.node_ids[0] == "mut:office_transposed"]
    if len(mutant_rows) != 2 or any("rec:office-2025-11" not in o.node_ids for o in mutant_rows):
        problems.append("the altered rows do not carry provenance to the recognition")
    specs = {p.id: p for p in inputs.planted}
    a, d = specs["office_transposed"], specs["rent_booked_twice"]
    if a.kind != "alter" or a.required != (("Assets:Bank:Checking", "-420"), ("Expenses:Office", "420")) \
            or a.replaces != (("Assets:Bank:Checking", "-240"), ("Expenses:Office", "240")) or not a.evidence:
        problems.append(f"alter spec: {a}")
    if d.kind != "duplicate" or d.expected_count != 1 or d.required != (("Assets:Bank:Checking", "-3500"), ("Expenses:Rent", "3500")):
        problems.append(f"duplicate spec: {d}")
    if inputs.scored_accounts != ("Assets:Bank:Checking", "Expenses:Office", "Expenses:Rent"):
        problems.append(f"scored accounts: {inputs.scored_accounts}")
    if a.residual != (("Expenses:Office", Decimal("180.00")), ("Assets:Bank:Checking", Decimal("-180.00"))) \
            or d.residual != (("Expenses:Rent", Decimal("-3500.00")), ("Assets:Bank:Checking", Decimal("3500.00"))):
        problems.append(f"residuals: alter {a.residual} duplicate {d.residual}")
    if dict(inputs.expected_balances)["Expenses:Office"] != Decimal("420.00"):
        problems.append("expected balances moved with the mutation")
    base, _ = derive()
    if bundle.graph_digest != base.graph_digest or bundle.mutation_plan_digest == base.mutation_plan_digest:
        problems.append("the plan digest did not move / the graph digest did")
    if bundle.view(PJ.STATEMENT_VIEW).digest != base.view(PJ.STATEMENT_VIEW).digest:
        problems.append("a mutation moved the bank statement")
    # refusals: unbalanced alteration, alteration equal to the truth, other accounts, opening entry, twin ambiguity
    bad = {
        "unknown strategy": PJ.AlterRecognition("x", "rec:office-2025-11", "authored_legs", 0, "?"),
        "transpose out of range": PJ.AlterRecognition("x", "rec:office-2025-11", "transpose_digits", 9, "?"),
        "transpose of equal digits (no error)": PJ.AlterRecognition("x", "rec:rent-2025-11", "transpose_digits", 3, "?"),   # 350000 -> pos 3,4 are 0,0
        "decimal shift of two places": PJ.AlterRecognition("x", "rec:office-2025-11", "decimal_shift", 2, "?"),
        "a sale (not settlement-derived)": PJ.AlterRecognition("x", "rec:si-1044-sale", "transpose_digits", 0, "?"),
        "a purchase on credit (no bank row)": PJ.DuplicateRecognition("x", "rec:pi-2240-receipt", "?"),
        "opening entry": PJ.DuplicateRecognition("x", "rec:opening", "?"),
        "same recognition twice": None,
    }
    for label, m in bad.items():
        try:
            if m is None:
                derive(A.WORLD, _plan(ALTER_OFFICE, PJ.DuplicateRecognition("y", "rec:office-2025-11", "?")))
            else:
                derive(A.WORLD, _plan(m))
            problems.append(f"{label}: derived")
        except (PJ.ProjectionError, DV.DerivationError):
            pass
    # residual cancellation: a pair whose residuals cancel on every target is an unsupported topology.
    # Alpine has no such pair, so build one: a second November rent cheque of the same amount.
    second_rent = S.ExpensePayment("event:rent-2025-11b", "2025-11-12", "party:cedar", Decimal("3500.00"),
                                   S.Settlement(S.Rail.CHEQUE, "2025-11-12", "doc:chq-1039"), "Storage unit rent, check 1039")
    world2 = dataclasses.replace(A.WORLD, events=A.WORLD.events + (second_rent,),
                                 documents=A.WORLD.documents + (S.Document("doc:chq-1039", S.DocumentKind.CHEQUE, "1039", "party:cedar", "2025-11-12"),))
    try:
        derive(world2, _plan(PJ.OmitRecognition("a", "rec:rent-2025-11", "?"), PJ.DuplicateRecognition("b", "rec:rent-2025-11b", "?")))
        problems.append("an omit and a duplicate whose residuals cancel on every target were derived")
    except DV.DerivationError as exc:
        if "cancel" not in str(exc):
            problems.append(f"cancelling pair refused for another reason: {exc}")
    try:
        derive(world2, _plan(PJ.OmitRecognition("a", "rec:rent-2025-11", "?"), PJ.OmitRecognition("b", "rec:rent-2025-11b", "?")))
    except DV.DerivationError as exc:
        problems.append(f"a non-cancelling pair (two omissions) was refused: {exc}")
    try:
        DV.PlantedSpec("p", "r1", "2025-11-01", (("A", "1"),), ("x",), "", ("e",), "?", kind="omit", replaces=(("A", "2"),),
                       residual=(("A", Decimal("1")),))
        problems.append("an omitted item with a replaced shape was constructed")
    except TypeError:
        pass
    return check("alter/duplicate: opening ledger mutated, expected ledger not; provenance and typed absence; specs carry truth, "
                 "wrong shape, residual and evidence; plan digest moves, graph and statement do not; malformed mutations, "
                 "non-settlement targets and impossible field combinations refused",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_shipped_world_is_the_projection,
    test_the_golden_solution_is_the_expected_projection,
    test_the_archived_task_file_is_derived,
    test_three_kinds_of_missing_are_three_reasons,
    test_an_unclassified_record_fails_the_projection,
    test_identity_is_free_of_insertion_order,
    test_one_fact_moves_only_the_views_it_touches,
    test_literal_contract_inputs_are_refused,
    test_no_private_id_reaches_anything_public,
    test_hand_reviewed_facts_hold,
    test_the_facts_catch_what_the_oracle_cannot,
    test_planted_predicates_are_the_recognitions,
    test_malformed_plans_and_worlds_are_refused,
    test_the_reconciliation_identity_from_both_sides,
    test_the_production_root_is_graph_backed,
    test_the_named_inverse_returns_the_clean_fingerprint,
    test_derived_answers_are_unrepresentable_in_the_authored_layer,
    test_alter_and_duplicate_project_and_derive,
]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
