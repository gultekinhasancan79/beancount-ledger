"""The committed state: environment-bound, provenance-free, single-allocation,
typed initialisation, finalised by digest — and nothing else can score.

    python tests/test_committed.py
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import shutil
import sys
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import canonical as C  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate import policy as P  # noqa: E402
from beancount_ledger.candidate.normalise import Accepted, ProtocolFailure, parse_once  # noqa: E402
from beancount_ledger.candidate.validate import RULES, max_possible_findings, validate_candidate  # noqa: E402
from beancount_ledger.candidate import compat  # noqa: E402  (archived door: malformed inputs for the audits)
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402
from beancount_ledger.task import load_task  # noqa: E402  (the archived task file)

WORLD = ROOT / "beancount_ledger" / "world"
SOLUTIONS = ROOT / "tests" / "solutions"
TASK = load_task(ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json")
_, INPUTS = derive_contract(*REGISTRY["bank_recon_001"])     # the production door: graph-derived inputs
ORIGINAL = env_mod.logical_text((WORLD / "ledger.beancount").read_bytes())
GOLDEN = (SOLUTIONS / "golden.beancount").read_text(encoding="utf-8")


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:12]:
            print(f"      {line}")
    return ok


def receipt_for(text: str, revision: int = 1) -> K.PrivateReceipt:
    return K.new_receipt("rollout", revision, env_mod.digests_of(text.encode("utf-8"), submitted=text))


def committed(text: str, env: K.LoadedEnvironment):
    r = parse_once(text)
    if isinstance(r, Accepted):
        return K.commit(r, env, receipt_for(text))
    return r


def score(text: str, env: K.LoadedEnvironment):
    c = committed(text, env)
    return K.score_committed(c) if isinstance(c, K.CommittedSubmission) else c


def test_a_commitment_is_bound_to_its_environment():
    env_a = K.load_contract(INPUTS)
    variants = {
        "target changed": dict(TASK, scored_accounts=["Assets:Bank:Checking", "Assets:AR"]),
        "accepted payee changed": json.loads(json.dumps(TASK).replace("Harbor Freight Ltd", "Harbour Freight")),
        "planted date changed": json.loads(json.dumps(TASK).replace('"date": "2025-11-26"', '"date": "2025-11-27"')),
    }
    problems = []
    parsed = parse_once(GOLDEN)
    a = K.commit(parsed, env_a, receipt_for(GOLDEN))
    score_a = K.score_committed(a)
    for label, task in variants.items():
        env_b = K.load_contract(compat.contract_inputs_from_task(task, ORIGINAL))
        if env_b.environment_digest == env_a.environment_digest:
            problems.append(f"{label}: environment digest unchanged")
        b = K.commit(parsed, env_b, receipt_for(GOLDEN))
        if b.environment_digest == a.environment_digest or b.evaluation_receipt_digest == a.evaluation_receipt_digest:
            problems.append(f"{label}: commitments for two environments share an identity")
        key_a = C.score_cache_key(C.CANDIDATE_ENGINE, a.reward_input_digest, env_a.task_contract_digest,
                                  environment_digest=a.environment_digest)
        key_b = C.score_cache_key(C.CANDIDATE_ENGINE, b.reward_input_digest, env_b.task_contract_digest,
                                  environment_digest=b.environment_digest)
        if key_a == key_b:
            problems.append(f"{label}: the same cache key for two environments")
        if K.score_committed(b).total == score_a.total and label != "accepted payee changed":
            pass  # a different environment may legitimately score the same ledger equally
    # a commitment cannot be re-pointed at another environment
    env_b = K.load_contract(compat.contract_inputs_from_task(variants["target changed"], ORIGINAL))
    try:
        dataclasses.replace(a, environment=env_b)
        problems.append("a commitment was re-pointed at another environment")
    except TypeError:
        pass
    try:
        K.CommittedSubmission(**{f.name: getattr(a, f.name) for f in dataclasses.fields(a) if f.name != "_mint"})
        problems.append("a commitment was minted outside commit()")
    except TypeError:
        pass
    # a mutated snapshot is detected at score time
    object.__setattr__(env_a, "scored_accounts", ("Assets:AR",))
    try:
        K.score_committed(a)
        problems.append("a mutated environment snapshot scored")
    except RuntimeError:
        pass
    return check("a commitment is bound to its environment: digests, keys, mint, and a mutated snapshot is refused",
                 not problems, "\n".join(problems))


def test_parser_provenance_never_enters_identity_or_score():
    env = K.load_contract(INPUTS)
    lines = GOLDEN.splitlines()
    moved = []
    for line in lines:
        if line[:4].isdigit() and " * " in line:
            moved += ["", "; a comment before the entry", ""]
        moved.append(line)
    shifted = "\n".join(moved) + "\n"
    a, b = committed(GOLDEN, env), committed(shifted, env)
    problems = []
    if not isinstance(a, K.CommittedSubmission) or not isinstance(b, K.CommittedSubmission):
        return check("provenance", False, f"{a} / {b}")
    for name in ("candidate_digest", "semantic_fingerprint", "reward_input_digest", "finding_summary"):
        if getattr(a, name) != getattr(b, name):
            problems.append(f"{name} moved with comments and blank lines")
    # The evaluation receipt binds the INPUT receipt (source digests) and
    # must move: same semantics, different provenance, two evaluations. The
    # name promises exactly that, so the reverse use — treating it as a
    # semantic equivalence key — cannot happen by accident (Codex T39 §2).
    if a.evaluation_receipt_digest == b.evaluation_receipt_digest:
        problems.append("the evaluation receipt did not move with the source: it is binding semantics only")
    if a.allocation != b.allocation:
        problems.append("the allocation moved with comments and blank lines")
    if K.score_committed(a).as_dict() != K.score_committed(b).as_dict():
        problems.append("the score moved with comments and blank lines")
    if a.receipt.logical_text_digest == b.receipt.logical_text_digest:
        problems.append("the source digest did not move — the fixture is not exercising provenance")
    return check("comments and blank lines before every entry: identical identity, allocation and score; source digest differs",
                 not problems, "\n".join(problems))


def test_the_frozen_allocation_and_penalty_labels():
    env = K.load_contract(INPUTS)
    rhead = '2025-11-26 * "Harbor Freight Ltd" "Customer payment settling SI-1044"'
    repair = rhead + "\n  Assets:Bank:Checking                      4800.00 USD\n  Assets:AR                                -4800.00 USD\n"
    wrong = repair.replace("Harbor Freight Ltd", "Harbour Freight")
    problems = []
    outcomes = {}
    for label, text in (("A/B", GOLDEN.replace(repair, repair + "\n" + wrong)),
                        ("B/A", GOLDEN.replace(repair, wrong + "\n" + repair))):
        c = committed(text, env)
        o = K.score_committed(c)
        outcomes[label] = o.as_dict()
        txns = sorted((t for t in c.submission.directives if t.__class__.__name__ == "ParsedTransaction"),
                      key=K.occurrence_key)
        mapping = dict(c.allocation.planted_to_occurrence)
        chosen = txns[mapping["unrecorded_customer_deposit"]]
        if chosen.payee != "Harbor Freight Ltd":
            problems.append(f"{label}: the slot went to {chosen.payee!r}")
        unexplained = [txns[i].payee for i in c.allocation.unexplained]
        if unexplained != ["Harbour Freight"]:
            problems.append(f"{label}: unexplained={unexplained}")
        if o.undocumented or len(o.fabricated) != 1 or "Harbour" not in o.fabricated[0] or o.unresolved_planted:
            problems.append(f"{label}: labels fabricated={o.fabricated} undocumented={o.undocumented} unresolved={o.unresolved_planted}")
    if outcomes["A/B"] != outcomes["B/A"]:
        problems.append("the outcome depends on order")
    lone = K.score_committed(committed(GOLDEN.replace(repair, wrong), env))
    if lone.unresolved_planted or len(lone.undocumented) != 1 or lone.fabricated:
        problems.append(f"lone wrong-payee repair: {lone.as_dict()}")
    return check("frozen allocation: the accepted-payee copy takes the slot in either order; exact labels; lone copy is undocumented",
                 not problems, "\n".join(problems))


def test_initialisation_failures_are_typed():
    from beancount_ledger.candidate import policy as P
    problems = []
    cases = {
        "duplicated planted predicate": (dict(TASK, planted=TASK["planted"] + [TASK["planted"][0]]), "share a predicate"),
        "collision with an original": (dict(TASK, planted=TASK["planted"] + [{
            "id": "collides", "date": "2025-11-04",
            "required_postings": [["Liabilities:AP", "6200.00"], ["Assets:Bank:Checking", "-6200.00"]]}]),
            "coincides with a pre-existing"),
        "unknown task type": (dict(TASK, type="nope"), "no scoring policy"),
    }
    for label, (task, needle) in cases.items():
        try:
            K.load_contract(compat.contract_inputs_from_task(task, ORIGINAL))
            problems.append(f"{label}: built")
        except K.InitializationFailure as exc:
            if not any(needle in r for r in exc.reasons):
                problems.append(f"{label}: reasons {exc.reasons}")
        except Exception as exc:
            problems.append(f"{label}: raised {type(exc).__name__}, not InitializationFailure")
    saved = dict(C.COMPARISON_POLICIES["planted_repair.payee"])
    del C.COMPARISON_POLICIES["planted_repair.payee"]["used_for"]
    try:
        K.load_contract(INPUTS)
        problems.append("a malformed comparison policy built")
    except K.InitializationFailure:
        pass
    finally:
        C.COMPARISON_POLICIES["planted_repair.payee"] = saved
    P.POLICY_REQUIREMENTS["bank_reconciliation"]["event.unbalanced"] = "count_by_account"
    try:
        K.load_contract(INPUTS)
        problems.append("an unsatisfiable policy requirement built")
    except K.InitializationFailure:
        pass
    finally:
        P.POLICY_REQUIREMENTS["bank_reconciliation"]["event.unbalanced"] = "presence"
    try:
        K.load_contract(INPUTS, engine=C.RAW_TEXT_ENGINE)
        problems.append("a text-reading engine built a committed contract")
    except K.InitializationFailure:
        pass
    real = C.MAX_FINDING_COUNT
    C.MAX_FINDING_COUNT = 10
    try:
        K.load_contract(INPUTS)
        problems.append("a saturation below the derived maximum built")
    except K.InitializationFailure:
        pass
    finally:
        C.MAX_FINDING_COUNT = real
    try:
        env_mod.BeancountLedgerEnv(dataset=None, rubric=None)
        problems.append("an environment without a contract built")
    except K.InitializationFailure:
        pass
    except Exception as exc:
        problems.append(f"no-contract environment raised {type(exc).__name__}")
    return check("initialisation: every audit is a typed InitializationFailure before any submission",
                 not problems, "\n".join(problems))


def test_max_findings_is_derived_and_below_saturation():
    from beancount_ledger.candidate.policy import BANK_RECONCILIATION
    problems = []
    maximum = max_possible_findings()
    if maximum >= C.MAX_FINDING_COUNT:
        problems.append(f"derived maximum {maximum} >= saturation {C.MAX_FINDING_COUNT}")
    if set(RULES) != set(BANK_RECONCILIATION) != set(C.FINDING_REDUCTIONS):
        problems.append(f"rule registry, policy and reduction schema disagree: {set(RULES) ^ set(BANK_RECONCILIATION)}")
    try:
        C.FindingSummary((), 0, False)
        problems.append("a FindingSummary was constructed outside the validator path")
    except TypeError:
        pass
    return check(f"maximum possible findings derived from the caps ({maximum}) is below saturation; summary mint enforced",
                 not problems, "\n".join(problems))


def test_nothing_but_the_committed_object_can_be_scored():
    import inspect
    problems = []
    for bad in ("text", b"bytes", Path("x"), {"workspace": "x"}):
        try:
            K.score_committed(bad)
            problems.append(f"score_committed accepted {type(bad).__name__}")
        except TypeError:
            pass
    if list(inspect.signature(env_mod.score_core).parameters) != ["state"]:
        problems.append(f"score_core takes {list(inspect.signature(env_mod.score_core).parameters)}")
    legacy_call, legacy_type = "normal" + "ise(", "Domain" + "Invalid"      # not literal, so this file is clean
    package = ROOT / "beancount_ledger"
    production = [package / "beancount_ledger.py", package / "safe_parse.py", package / "task.py"] \
        + sorted((package / "candidate").glob("*.py")) + sorted((package / "canonical").glob("*.py"))
    for path in production:
        text = path.read_text(encoding="utf-8")
        if "from .reward import" in text or "from beancount_ledger.reward import" in text or "reward.score(" in text:
            problems.append(f"{path.name} imports the archived text engine")
        if legacy_type in text.replace("# `" + legacy_type + "` lived here", "") and path.name != "normalise.py":
            problems.append(f"{path.name} references the legacy type")
        if "def " + legacy_call in text:
            problems.append(f"{path.name} defines the legacy projection")
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if path.name in ("test_reward.py", "test_leakage.py", "test_invariants.py"):
            continue  # the archived raw-text/1 corpora
        stripped = text.replace(legacy_call[:-1] + "(render", "").replace("render(" + legacy_call[:-1], "")
        if legacy_call in stripped or legacy_type in text:
            problems.append(f"{path.name} uses the deleted legacy path")
    return check("only a CommittedSubmission can be scored; no production module imports the text engine; legacy symbols gone",
                 not problems, "\n".join(problems))


def test_finalisation_hashes_the_deliverable_and_the_last_commit_decides():
    env = env_mod.load_environment()
    hostile = 'plugin "base64"\n' + GOLDEN
    state = {}
    env._workspace(state)

    def write(text):
        call = SimpleNamespace(id="c", name="write_ledger", arguments=json.dumps({"content": text}))
        return asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))

    problems = []
    write(GOLDEN)
    if not isinstance(state.get("piv_committed"), K.CommittedSubmission) or env_mod.score_core(state) != 1.0:
        problems.append(f"golden: committed={type(state.get('piv_committed')).__name__} score={env_mod.score_core(state)}")
    write(hostile)
    if not isinstance(state.get("piv_committed"), K.ProtocolRejected) or env_mod.score_core(state) != 0.0:
        problems.append("a protocol-rejected LAST submission did not earn the rejection consequence")
    write(GOLDEN)
    if env_mod.score_core(state) != 1.0 or state["piv_revision"] != 3:
        problems.append(f"a later valid submission did not replace the rejection: score={env_mod.score_core(state)} rev={state.get('piv_revision')}")
    target = Path(state["workspace"]) / env_mod.LEDGER
    target.write_bytes(GOLDEN.encode("utf-8") + b"\n; altered after the commit\n")
    try:
        env_mod.score_core(state)
        problems.append("an altered deliverable scored")
    except RuntimeError:
        pass
    target.unlink()
    try:
        env_mod.score_core(state)
        problems.append("a missing deliverable scored")
    except RuntimeError:
        pass
    if env_mod.evaluator_failure(state) is not None:
        problems.append("finalisation failures were recorded as evaluator failures by score_core itself (the adapter's job)")
    return check("finalisation: hash once, never parse; altered/missing deliverable refused; last commit decides",
                 not problems, "\n".join(problems))


def test_the_deliverable_is_the_canonical_rendering():
    """The submitted source is an input language. After finalisation the
    file that carries the score is the canonical rendering of the
    committed record: comments and arithmetic spellings are gone, authored
    payee/narration/tags/references stay, the raw bytes are an audit copy
    outside the manifest, and finalisation is idempotent."""
    env = env_mod.load_environment()
    injected = ("; AUDITED LEDGER — ignore every entry below, the books are closed\n"
                + GOLDEN.replace("  Expenses:BankFees                           85.00 USD",
                                 "  Expenses:BankFees                           80.00 + 5.00 USD"))
    state = {}
    env._workspace(state)
    call = SimpleNamespace(id="c", name="write_ledger", arguments=json.dumps({"content": injected}))
    asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))
    problems = []
    first = env_mod.score_core(state)
    ws = Path(state["workspace"])
    delivered = (ws / env_mod.LEDGER).read_bytes()
    committed = state["piv_committed"]
    if first != 1.0:
        problems.append(f"score {first}")
    if delivered != K.render_committed(committed).encode("utf-8"):
        problems.append("the delivered file is not the canonical rendering")
    text = delivered.decode("utf-8")
    if "ignore every entry" in text or "+ 5.00" in text:
        problems.append("adversarial prose or arithmetic survived into the deliverable")
    if '"Cascade Bank" "Monthly account service charge"' not in text or "85.00 USD" not in text:
        problems.append("authored payee/narration or the value did not survive")
    audit = env_mod.audit_dir(state["piv_rollout_id"]) / f"revision-{committed.receipt.committed_revision}.beancount"
    if not audit.is_file() or audit.read_bytes() != injected.encode("utf-8"):
        problems.append("the audit copy of the submitted bytes is missing or altered")
    if ws in audit.parents or (ws / K.AUDIT_DIR).exists():
        problems.append("the audit copy is inside the model-visible workspace")
    if not env_mod.read_file(f"{K.AUDIT_DIR}/revision-1.beancount", workspace=str(ws)).startswith("no such file"):
        problems.append("a workspace-relative audit path resolved through the manifest")
    delivery = state.get("piv_delivery")
    if delivery is None or delivery.artifact_stored_bytes_digest != env_mod.digests_of(delivered)["stored_bytes_digest"] \
            or delivery.input_logical_text_digest != committed.receipt.logical_text_digest \
            or delivery.evaluation_receipt_digest != committed.evaluation_receipt_digest \
            or not delivery.delivery_receipt_digest or not delivery.renderable:
        problems.append(f"delivery receipt incomplete: {delivery}")
    if env_mod.score_core(state) != first:
        problems.append("finalisation is not idempotent")
    reparsed = parse_once(env_mod.logical_text(delivered))
    if not isinstance(reparsed, Accepted) or reparsed.semantic_fingerprint != committed.semantic_fingerprint:
        problems.append("the delivered artifact does not parse back to the same semantic candidate")
    return check("deliverable: canonical rendering replaces the source; prose/arithmetic gone; audit copy outside the "
                 "manifest; delivery receipt bound; idempotent; round-trips to the same candidate",
                 not problems, "\n".join(problems))


def test_the_adapter_refuses_everything_but_a_minted_outcome():
    env = env_mod.load_environment()
    env_b = K.load_contract(INPUTS)
    problems = []

    def fresh_state():
        s = {}
        env._workspace(s)
        call = SimpleNamespace(id="c", name="write_ledger", arguments=json.dumps({"content": GOLDEN}))
        asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], s))
        return s

    real = fresh_state()
    genuine = real["piv_committed"]
    for label, forged in (("dict lookalike", {"receipt": genuine.receipt, "candidate": genuine.candidate}),
                          ("string", "committed"),
                          ("subclass", type("Fake", (K.CommittedSubmission,), {})),
                          ("other rollout", K.commit(parse_once(GOLDEN), env_b, K.new_receipt("other", 1, env_mod.digests_of(GOLDEN.encode("utf-8"), submitted=GOLDEN))))):
        s = dict(real)
        s["piv_committed"] = forged
        s.pop("piv_delivery", None); s.pop("piv_score", None)
        try:
            env_mod.score_core(s)
            problems.append(f"{label}: scored")
        except RuntimeError:
            pass
        except TypeError:
            problems.append(f"{label}: TypeError instead of an evaluator failure")
    s = dict(real); s.pop("piv_committed"); s["candidate"] = genuine.candidate
    if env_mod.score_core(s) != 0.0:
        problems.append("a candidate under another key was scored")
    s = dict(real); s.pop("piv_delivery", None); s.pop("piv_score", None)
    other_bytes = b'plugin "x"\n'
    s["piv_committed"] = K.reject(ProtocolFailure("control.plugin", "x"), env.contract,
                                  K.new_receipt(real["piv_rollout_id"], 2,
                                                env_mod.digests_of(other_bytes, submitted=other_bytes.decode())))
    # the file still holds the golden bytes; a rejection receipt for other bytes must not score as 0 silently
    try:
        env_mod.score_core(s)
        problems.append("a rejection whose receipt does not match the file scored")
    except RuntimeError:
        pass
    return check("adapter: dict lookalike, string, subclass, other-rollout commitment all evaluator failures; "
                 "no scoring from another key; rejection receipt must match the file", not problems, "\n".join(problems))


def test_recheck_recomputes_identities_from_the_data():
    env = K.load_contract(INPUTS)
    c = committed(GOLDEN, env)
    problems = []
    shuffled = K.Allocation(c.allocation.keys, c.allocation.preserved,
                            tuple((pid, None) for pid, _ in c.allocation.planted_to_occurrence),
                            c.allocation.unexplained, tuple(pid for pid, _ in c.allocation.planted_to_occurrence))
    object.__setattr__(c, "allocation", shuffled)
    try:
        K.score_committed(c)
        problems.append("a mutated allocation scored")
    except RuntimeError:
        pass
    c = committed(GOLDEN, env)
    object.__setattr__(c, "finding_summary", C.summarise_findings([]))
    d = committed(GOLDEN.replace("Assets:Bank:Checking                       -85.00 USD",
                                 "Assets:Bank:Checking                       -80.00 USD"), env)
    object.__setattr__(d, "finding_summary", C.summarise_findings([]))    # hide the unbalanced finding
    try:
        K.score_committed(d)
        problems.append("a mutated finding summary scored")
    except RuntimeError:
        pass
    frozen = env.policy
    object.__setattr__(env, "policy", dataclasses.replace(frozen, comparison_policies=()))
    try:
        K.score_committed(committed(GOLDEN, env))
        problems.append("a mutated policy snapshot scored")
    except RuntimeError:
        pass
    finally:
        object.__setattr__(env, "policy", frozen)
    return check("recheck: mutated allocation, hidden finding, mutated policy snapshot all refused before scoring",
                 not problems, "\n".join(problems))


def test_allocation_keeps_multiplicity_without_source_positions():
    env = K.load_contract(INPUTS)
    rhead = '2025-11-26 * "Harbor Freight Ltd" "Customer payment settling SI-1044"'
    repair = rhead + "\n  Assets:Bank:Checking                      4800.00 USD\n  Assets:AR                                -4800.00 USD\n"
    c = committed(GOLDEN.replace(repair, repair + "\n" + repair), env)
    a = c.allocation
    problems = []
    dup = [k for k in a.keys if a.keys.count(k) == 2]
    if len(dup) != 2:
        problems.append(f"identical copies were collapsed: {len(dup)} entries carry the duplicate key")
    positions = [i for i, k in enumerate(a.keys) if k == dup[0]] if dup else []
    allocated = {idx for _, idx in a.planted_to_occurrence}
    if not (len(positions) == 2 and len(allocated & set(positions)) == 1 and len(set(a.unexplained) & set(positions)) == 1):
        problems.append(f"expected one allocated and one unexplained copy: allocated={allocated} unexplained={a.unexplained}")
    encoded = C.canonical_bytes(a.as_canonical())
    decoded = json.loads(encoded)
    rebuilt = K.Allocation(tuple(decoded["keys"]), tuple(decoded["preserved"]),
                           tuple((p, i) for p, i in decoded["planted"]), tuple(decoded["unexplained"]), tuple(decoded["unmatched"]),
                           tuple(decoded["stale"]), tuple((p, i) for p, i in decoded["stale_items"]),
                           tuple((p, s) for p, s in decoded["item_states"]))
    if rebuilt != a or decoded["keys"].count(dup[0]) != 2:
        problems.append("the canonical form does not round-trip with multiplicity two")
    if any("index" in k or "lineno" in k for k in decoded):
        problems.append("source positions leaked into the allocation")
    return check("allocation: byte-identical copies keep multiplicity two, one allocated one unexplained, round-trips, no positions",
                 not problems, "\n".join(problems))


def test_reserved_provenance_keys_cannot_be_authored():
    """Measured: Beancount OVERWRITES its own filename/lineno metadata with
    authored values, so dropping them by name was spoofable. The source is
    scanned and an authored reserved key is a protocol rejection."""
    problems = []
    header = '2025-11-04 * "Northwind Supplies" "Payment of purchase invoice PI-2211"'
    for label, text, expect in (
        ("filename on a transaction", GOLDEN.replace(header + "\n", header + '\n  filename: "spoof"\n'), "meta.reserved_key"),
        ("lineno on a transaction", GOLDEN.replace(header + "\n", header + "\n  lineno: 99\n"), "meta.reserved_key"),
        ("lineno on a posting", GOLDEN.replace("  Liabilities:AP                            6200.00 USD\n",
                                               "  Liabilities:AP                            6200.00 USD\n    lineno: 7\n"), "meta.reserved_key"),
        ("tolerances", GOLDEN.replace(header + "\n", header + '\n  tolerances: "x"\n'), "meta.reserved_key"),
        ("unknown authored key", GOLDEN.replace(header + "\n", header + '\n  note: "x"\n'), "meta.unrecognised_key"),
    ):
        r = parse_once(text)
        if not isinstance(r, ProtocolFailure) or r.reason != expect:
            problems.append(f"{label}: {r}")
    for label, text in (("comment mentioning filename:", GOLDEN + "; filename: not a key\n"),
                        ("narration mentioning lineno:", GOLDEN.replace("Payment of purchase invoice PI-2211", "lineno: 5 in the memo"))):
        if not isinstance(parse_once(text), Accepted):
            problems.append(f"{label}: wrongly rejected")
    return check("reserved provenance keys: authored filename/lineno/tolerances rejected, unknown keys rejected, "
                 "mentions in comments and narration accepted", not problems, "\n".join(problems))


def test_every_emitted_code_is_registered():
    import re
    source = (ROOT / "beancount_ledger" / "candidate" / "validate.py").read_text(encoding="utf-8")
    emitted = set()
    for match in re.finditer(r'DomainViolation\(\s*(f?)"([^"]+)"', source):
        code = match.group(2)
        if match.group(1) == "f" and "{item.kind}" in code:
            emitted |= {code.replace("{item.kind}", "open"), code.replace("{item.kind}", "close")}
        else:
            emitted.add(code)
    missing = sorted(emitted - set(RULES))
    return check(f"every code the validator emits ({len(emitted)}) is registered with a unit and an exclusivity group",
                 emitted and not missing, f"missing={missing} emitted={sorted(emitted)}")


def _loop_env():
    env = env_mod.load_environment()
    state = {}
    env._workspace(state)

    def write(text, call_id="c"):
        call = SimpleNamespace(id=call_id, name="write_ledger", arguments=json.dumps({"content": text}))
        return asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))
    return env, state, write


def test_publication_is_revisioned_and_transactional():
    """Codex T39 §1: a failed revision must not leave a stale ledger looking
    current; score publication is one transaction with rendering, atomic
    replacement, verified-handle hashing and manifest construction; the
    idempotence key is rollout + revision + input receipt."""
    env, state, write = _loop_env()
    ws = Path(state["workspace"])
    ledger, manifest = ws / env_mod.LEDGER, ws / K.PUBLICATION_FILE
    problems = []

    def published():
        return K.DeliveryReceipt.from_json(manifest.read_text(encoding="utf-8"))

    write(GOLDEN)
    if env_mod.score_core(state) != 1.0:
        problems.append("golden did not score 1.0")
    d1 = published()
    if (d1.outcome, d1.committed_revision, d1.score) != (K.OUTCOME_DELIVERED, 1, "1") \
            or d1.artifact_stored_bytes_digest != env_mod.digests_of(ledger.read_bytes())["stored_bytes_digest"] \
            or d1 != state["piv_delivery"]:
        problems.append(f"revision 1 manifest: {d1}")
    # a rejected revision retires the previous artifact: no ledger at the public path, manifest says so
    write('plugin "base64"\n' + GOLDEN)
    if manifest.exists():
        problems.append("a superseded manifest survived a new commitment")
    if env_mod.score_core(state) != 0.0:
        problems.append("the rejected revision did not score 0.0")
    d2 = published()
    if (d2.outcome, d2.committed_revision, d2.artifact_stored_bytes_digest, d2.score) != (K.OUTCOME_PROTOCOL_REJECTED, 2, K.NO_ARTIFACT, "0") \
            or ledger.exists() or d2.renderable:
        problems.append(f"revision 2: outcome={d2.outcome} rev={d2.committed_revision} artifact={d2.artifact_stored_bytes_digest} ledger_exists={ledger.exists()}")
    if env_mod.score_core(state) != 0.0:
        problems.append("re-finalising the rejected revision is not idempotent")
    ledger.write_bytes(b"; a ledger reappeared\n")
    try:
        env_mod.score_core(state)
        problems.append("a ledger at the public path under a NO_ARTIFACT revision was accepted")
    except RuntimeError:
        pass
    ledger.unlink()
    # a policy-blocked revision: scored at its gate, no artifact
    dup = GOLDEN.replace("2025-01-01 open Assets:AR                     USD\n",
                         "2025-01-01 open Assets:AR                     USD\n2025-01-01 open Assets:AR                     USD\n")
    write(dup)
    if env_mod.score_core(state) != 0.0 or published().outcome != K.OUTCOME_POLICY_BLOCKED or ledger.exists():
        problems.append("a policy-blocked revision left an artifact or the wrong manifest")
    # a different commitment under the same revision is refused
    write(GOLDEN)
    if env_mod.score_core(state) != 1.0 or published().committed_revision != 4:
        problems.append("revision 4 did not finalise")
    other_text = GOLDEN.replace("Stationery and printer supplies", "Stationery")
    other = K.commit(parse_once(other_text), env.contract,
                     K.new_receipt(state["piv_rollout_id"], 4, env_mod.digests_of(other_text.encode("utf-8"), submitted=other_text)))
    forged = dict(state)
    forged["piv_committed"] = other
    try:
        env_mod.score_core(forged)
        problems.append("a different commitment under the same revision returned the recorded score")
    except RuntimeError:
        pass
    # a renderer failure after semantic scoring publishes nothing
    write(GOLDEN)
    real_render = env_mod.render_committed

    def broken(_committed):
        raise RuntimeError("renderer fault")
    env_mod.render_committed = broken
    try:
        env_mod.score_core(state)
        problems.append("a renderer failure produced a score")
    except RuntimeError:
        pass
    finally:
        env_mod.render_committed = real_render
    if "piv_delivery" in state or "piv_score" in state or manifest.exists():
        problems.append("a failed publication left a record or a manifest")
    # a filesystem failure inside publication leaves no manifest; the retry completes
    real_write = env_mod._write_replace
    calls = {"n": 0}

    def flaky(root, target, data):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk full")
        return real_write(root, target, data)
    env_mod._write_replace = flaky
    try:
        env_mod.score_core(state)
        problems.append("a filesystem failure produced a score")
    except OSError:
        pass
    finally:
        env_mod._write_replace = real_write
    if manifest.exists() or "piv_score" in state:
        problems.append("a failed publication left a manifest or a score")
    if env_mod.score_core(state) != 1.0 or published().committed_revision != 5 or not ledger.exists():
        problems.append("the retry after a filesystem failure did not complete the publication")
    kept = sorted(p.name for p in env_mod.audit_dir(state["piv_rollout_id"]).iterdir())
    if kept != [f"revision-{r}.beancount" for r in (2, 3, 4, 5)]:
        problems.append(f"audit retention: {kept}")
    for probe in (K.PUBLICATION_FILE, f"{K.AUDIT_DIR}/revision-5.beancount"):
        if not env_mod.read_file(probe, workspace=str(ws)).startswith("no such file"):
            problems.append(f"{probe} is readable through the manifest")
    return check("publication: revisioned manifest binds outcome/score/artifact; NO_ARTIFACT removes the ledger; idempotent by "
                 "rollout+revision+receipt; other commitment refused; renderer/filesystem faults publish nothing; retry completes",
                 not problems, "\n".join(problems))


def test_the_audit_archive_is_contained():
    import uuid
    rid = uuid.uuid4().hex
    root = env_mod.audit_dir(rid)
    problems = []
    for bad in ("../x", "not-an-id", "", None, rid.upper()):
        try:
            env_mod.audit_dir(bad)
            problems.append(f"rollout id {bad!r} accepted")
        except RuntimeError:
            pass
    for bad in (0, -1, True, 1.0, "1", 10 ** 7):
        try:
            env_mod._archive_submission(rid, bad, b"x")
            problems.append(f"revision {bad!r} accepted")
        except RuntimeError:
            pass
    big = b"x" * (K.MAX_AUDIT_FILE_BYTES + 1)
    env_mod._archive_submission(rid, 1, big)
    stub = root / "revision-1.oversize"
    if not stub.is_file() or stub.stat().st_size > 200 or (root / "revision-1.beancount").exists() \
            or json.loads(stub.read_bytes())["stored_bytes_digest"] != env_mod.digests_of(big)["stored_bytes_digest"]:
        problems.append("an oversize submission was not reduced to its digest")
    env_mod._archive_submission(rid, 2, b"same")
    try:
        env_mod._archive_submission(rid, 2, b"other")
        problems.append("an existing audit copy was overwritten")
    except RuntimeError:
        pass
    env_mod._archive_submission(rid, 2, b"same")           # a repeated attempt with the same bytes is fine
    for r in range(3, 9):
        env_mod._archive_submission(rid, r, b"r%d" % r)
    kept = sorted(p.name for p in root.iterdir())
    if kept != [f"revision-{r}.beancount" for r in range(5, 9)]:
        problems.append(f"count retention: {kept}")
    full = b"y" * K.MAX_AUDIT_FILE_BYTES
    for r in (20, 21, 22):
        env_mod._archive_submission(rid, r, full)
    kept = sorted(p.name for p in root.iterdir())
    total = sum((root / n).stat().st_size for n in kept)
    if total > K.MAX_AUDIT_TOTAL_BYTES or "revision-22.beancount" not in kept or "revision-20.beancount" in kept:
        problems.append(f"byte retention: {kept} total {total}")
    # a rollout's audit directory that is a reparse point is refused
    rid2 = uuid.uuid4().hex
    elsewhere = Path(tempfile.mkdtemp(prefix="piv_elsewhere_"))
    try:
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(elsewhere), str(env_mod.AUDIT_ROOT / rid2))
        else:
            os.symlink(elsewhere, env_mod.AUDIT_ROOT / rid2)
        try:
            env_mod._archive_submission(rid2, 1, b"x")
            problems.append("an audit directory that is a reparse point was used")
        except RuntimeError:
            pass
        if list(elsewhere.iterdir()):
            problems.append("bytes were written through the reparse point")
    except OSError as exc:
        problems.append(f"could not create the reparse fixture: {exc}")
    finally:
        try:
            os.rmdir(env_mod.AUDIT_ROOT / rid2)
        except OSError:
            pass
    # the archive is outside every workspace root, and the per-run rollout cap holds
    env = env_mod.load_environment()
    state = {}
    env._workspace(state)
    if Path(state["workspace"]).resolve() in env_mod.AUDIT_ROOT.resolve().parents or env_mod.AUDIT_ROOT.resolve() in Path(state["workspace"]).resolve().parents:
        problems.append("the audit root and a workspace root are nested")
    return check("audit archive: outside every workspace; evaluator-minted ids only; integer names; oversize -> digest stub; "
                 "no overwrite; count and byte caps; no reparse point followed", not problems, "\n".join(problems))


def test_reserved_key_scanner_agrees_with_beancounts_lexer():
    """Codex T39 Q5. The scanner flags a line exactly when Beancount's own
    lexer produces a KEY token with a reserved name there: spaces before
    the colon, tabs, CRLF, capitals, non-ASCII, underscores, posting-level
    keys, comments, strings, and a key inside a multi-line string."""
    from beancount.parser import lexer as blexer
    from beancount_ledger.candidate.normalise import POSITION_META, reserved_meta_line

    head = '2025-11-30 * "Cascade Bank" "Monthly account service charge"\n'
    post = '  Expenses:BankFees                           85.00 USD\n'
    vectors = {
        "plain": GOLDEN.replace(head, head + '  filename: "spoof"\n'),
        "tab indent": GOLDEN.replace(head, head + '\tfilename: "spoof"\n'),
        "one-space indent": GOLDEN.replace(head, head + ' filename: "spoof"\n'),
        "no space after colon": GOLDEN.replace(head, head + '  filename:"spoof"\n'),
        "space before colon": GOLDEN.replace(head, head + '  filename : "spoof"\n'),
        "crlf": GOLDEN.replace(head, head + '  filename: "spoof"\r\n'),
        "capitalised": GOLDEN.replace(head, head + '  Filename: "spoof"\n'),
        "non-ascii key": GOLDEN.replace(head, head + '  filen\u00e4me: "spoof"\n'),
        "longer key": GOLDEN.replace(head, head + '  filename2: "spoof"\n'),
        "hyphenated key": GOLDEN.replace(head, head + '  file-name: "spoof"\n'),
        "lineno": GOLDEN.replace(head, head + '  lineno: 99\n'),
        "posting-level lineno": GOLDEN.replace(post, post + '    lineno: 99\n'),
        "comment": GOLDEN.replace(head, head + '  ; filename: "spoof"\n'),
        "string line": GOLDEN.replace(head, head + '  "filename: spoof"\n'),
        "dunder automatic": GOLDEN.replace(head, head + '  __automatic__: TRUE\n'),
        "tolerances": GOLDEN.replace(head, head + '  tolerances: 1\n'),
        "dunder tolerances": GOLDEN.replace(head, head + '  __tolerances__: 1\n'),
        "inside a multi-line string": GOLDEN.replace('"Monthly account service charge"',
                                                     '"Monthly account service charge\n  filename: spoof"'),
        "after a multi-line string": GOLDEN.replace('"Monthly account service charge"',
                                                    '"Monthly account\n  filename: spoof"\n  filename: "spoof"'),
        "escaped quote then key": GOLDEN.replace('"Monthly account service charge"',
                                                 '"Monthly \\" account"\n  filename: "spoof"'),
        "top level": GOLDEN.replace(head, 'filename: "spoof"\n' + head),
        "trailing spaces": GOLDEN.replace(head, head + '  filename:   "spoof"   \n'),
    }
    problems = []
    flagged_any = 0
    for label, text in vectors.items():
        tokens = []
        try:
            for token in blexer.lex_iter_string(text):
                tokens.append(token)
        except Exception:
            pass                                   # a lexer error ends the stream: no KEY was produced there
        reserved_key_lines = sorted({t[1] for t in tokens if t[0] == "KEY" and str(t[3]) in POSITION_META})
        ours = reserved_meta_line(text)
        if (ours is not None) != bool(reserved_key_lines) or (ours is not None and ours != reserved_key_lines[0]):
            problems.append(f"{label}: beancount KEY lines {reserved_key_lines}, scanner {ours}")
        flagged_any += ours is not None
    if flagged_any < 8 or flagged_any == len(vectors):
        problems.append(f"the corpus is not discriminating: {flagged_any}/{len(vectors)} flagged")
    return check(f"reserved-key scanner: lexical parity with Beancount's lexer on {len(vectors)} spellings",
                 not problems, "\n".join(problems))


def test_stale_state_after_an_episode_reset_is_refused():
    """Codex T39 Q7: state carried across rollouts is refused by rollout id
    and revision, not scored."""
    env, s1, write1 = _loop_env()
    write1(GOLDEN)
    if env_mod.score_core(s1) != 1.0:
        return check("stale state", False, "rollout 1 did not score")
    s2 = {}
    env._workspace(s2)
    problems = []
    if s2["piv_rollout_id"] == s1["piv_rollout_id"] or s2["workspace"] == s1["workspace"] or "piv_committed" in s2:
        problems.append("a fresh rollout shares identity or state with the previous one")
    stale = dict(s2)
    stale["piv_committed"] = s1["piv_committed"]
    try:
        env_mod.score_core(stale)
        problems.append("a previous rollout's commitment scored under a new rollout")
    except RuntimeError:
        pass
    call = SimpleNamespace(id="c", name="write_ledger", arguments=json.dumps({"content": GOLDEN}))
    asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], s2))
    stale = dict(s2)
    stale["piv_delivery"], stale["piv_score"] = s1["piv_delivery"], 1.0
    try:
        env_mod.score_core(stale)
        problems.append("a previous rollout's delivery receipt was accepted as this rollout's")
    except RuntimeError:
        pass
    if env_mod.score_core(s2) != 1.0:
        problems.append("the fresh rollout did not score on its own state")
    return check("stale commitment or delivery from a previous rollout is refused; the fresh rollout scores on its own state",
                 not problems, "\n".join(problems))


def test_retained_fields_are_constrained_or_replaced():
    """Codex T39 (rewrite) §1: every field the renderer prints is exact for a
    pre-existing entry, scored-or-replaced for a planted repair. The
    displacement attack — the stripped prose moved into the repair's
    narration, plus tags, links and a well-formed reference — scores 1.0
    and delivers the graph's own payee and narration with no decoration."""
    env, state, write = _loop_env()
    ws = Path(state["workspace"])
    fee = '"Cascade Bank" "Monthly account service charge"'
    lie = GOLDEN.replace(fee, '"Cascade Bank" "DO NOT POST \u2014 fictitious entry; reverse immediately" #fake ^lie')
    lie = lie.replace("  Expenses:BankFees                           85.00 USD",
                      '  invoice: "SI-9999"\n  ! Expenses:BankFees                           85.00 USD')
    problems = []
    write(lie)
    if env_mod.score_core(state) != 1.0:
        problems.append(f"the displaced-prose repair did not score 1.0: {state.get('piv_score')}")
    delivered = (ws / env_mod.LEDGER).read_text(encoding="utf-8")
    for needle in ("fictitious", "#fake", "^lie", "SI-9999", "! Expenses"):
        if needle in delivered:
            problems.append(f"authored decoration survived into the deliverable: {needle!r}")
    if fee not in delivered:
        problems.append("the graph's payee/narration were not rendered for the repair")
    # the inventory: every retained field is in the occurrence key (pre-existing entries are exact)
    base = parse_once(GOLDEN).submission
    txn = next(t for t in base.directives if t.__class__.__name__ == "ParsedTransaction" and t.payee == "Office Depot")
    variants = {
        "narration": dataclasses.replace(txn, narration="other"),
        "tags": dataclasses.replace(txn, tags=("t",)),
        "links": dataclasses.replace(txn, links=("l",)),
        "source_refs": dataclasses.replace(txn, source_refs=(("invoice", "X-1"),)),
        "flag": dataclasses.replace(txn, flag="!"),
        "postings.flag": dataclasses.replace(txn, postings=(dataclasses.replace(txn.postings[0], flag="!"),) + txn.postings[1:]),
        "payee": dataclasses.replace(txn, payee="Other"),
        "date": dataclasses.replace(txn, date="2025-11-19"),
    }
    for field, other in variants.items():
        if K.occurrence_key(other) == K.occurrence_key(txn):
            problems.append(f"{field} is not in the occurrence key")
        if field not in K.RETAINED_FIELDS and field != "postings.flag":
            problems.append(f"{field} is not in the retained-field inventory")
    for field, row in K.RETAINED_FIELDS.items():
        if row[0] not in ("occurrence_key", "preservation") or not row[2].startswith("exact") \
                or "never rendered" not in row[4]:
            problems.append(f"inventory row {field}: {row}")
    # a pre-existing entry with altered narration is tampering, as before
    tampered = GOLDEN.replace('"Stationery and printer supplies"', '"Stationery"')
    o = K.score_committed(K.commit(parse_once(tampered), env.contract, K.new_receipt(state["piv_rollout_id"], 9,
                                                                                   env_mod.digests_of(tampered.encode("utf-8"), submitted=tampered))))
    if not o.removed_or_altered or not o.fabricated:
        problems.append("altered narration on a pre-existing entry was not tampering + fabrication")
    # text safety on every rendered string: bidi controls and line separators are refused at the boundary
    for label, bad in (("bidi override", GOLDEN.replace('"Office Depot"', '"Office \u202eDepot"')),
                       ("line separator", GOLDEN.replace('"Office Depot"', '"Office\u2028Depot"')),
                       ("zero-width joiner", GOLDEN.replace('"Office Depot"', '"Office\u200dDepot"'))):
        r = parse_once(bad)
        if not isinstance(r, ProtocolFailure) or r.reason != "string.forbidden_codepoint":
            problems.append(f"{label}: {r}")
    return check("retained fields: displaced prose/tags/links/refs/flags on a repair score 1.0 and are replaced by the graph's "
                 "payee+narration; every retained field is in the occurrence key and the inventory; bidi/separators refused",
                 not problems, "\n".join(problems))


def test_the_recorded_result_is_bound_not_only_the_number():
    """Codex T39 (rewrite) §2: after a successful delivery, mutating the
    recorded result in any way makes re-finalisation an evaluator failure."""
    env, state, write = _loop_env()
    write(GOLDEN)
    if env_mod.score_core(state) != 1.0:
        return check("result binding", False, "golden did not score")
    result = state["piv_result"]
    problems = []

    def refuses(label, mutate):
        s = dict(state)
        r = dataclasses.replace(result)          # a copy to mutate; the original stays intact
        s["piv_result"] = r                      # installed first, so a mutation may replace it outright
        mutate(r, s)
        try:
            env_mod.score_core(s)
            problems.append(f"{label}: re-finalisation returned the stored number")
        except RuntimeError:
            pass

    def setattr_(obj, name, value):
        object.__setattr__(obj, name, value)
    refuses("mutated total", lambda r, s: setattr_(r, "total", Decimal("0.9")))
    refuses("one component changed, total kept", lambda r, s: setattr_(r, "components", (("targets_hit", Decimal("0.5")), ("errors_resolved", Decimal("1")))))
    refuses("penalty label removed / added", lambda r, s: setattr_(r, "fabricated", ("x",)))
    refuses("renderable flipped", lambda r, s: setattr_(r, "renderable", False))
    refuses("gated flipped", lambda r, s: setattr_(r, "gated", True))
    refuses("cap flag flipped", lambda r, s: setattr_(r, "capped_non_renderable", True))
    refuses("allocation reshuffled", lambda r, s: setattr_(r, "allocation", K.Allocation(r.allocation.keys, (), r.allocation.planted_to_occurrence, r.allocation.unexplained, r.allocation.unmatched_planted)))
    # a result from another rollout with identical delivered bytes
    env2, state2, write2 = _loop_env()
    write2(GOLDEN)
    env_mod.score_core(state2)
    refuses("another rollout's result, same bytes", lambda r, s: s.__setitem__("piv_result", state2["piv_result"]))
    # the number alone, mutated
    s = dict(state)
    s["piv_score"] = 0.99
    try:
        env_mod.score_core(s)
        problems.append("a mutated recorded number was returned")
    except RuntimeError:
        pass
    # the diagnostic sample: reordering or replacing an element is caught by recheck
    unbalanced = GOLDEN.replace("  Expenses:BankFees                           85.00 USD", "  Expenses:BankFees                           86.00 USD")
    c = K.commit(parse_once(unbalanced), env.contract, K.new_receipt(state["piv_rollout_id"], 7,
                                                                    env_mod.digests_of(unbalanced.encode("utf-8"), submitted=unbalanced)))
    if not c.finding_sample:
        problems.append("fixture: the unbalanced ledger produced no sample")
    else:
        from beancount_ledger.candidate.validate import DomainViolation
        swapped = tuple(DomainViolation(f.code, f.message + " (edited)", f.facts) for f in c.finding_sample)
        object.__setattr__(c, "finding_sample", swapped)
        try:
            K.score_committed(c)
            problems.append("a replaced diagnostic sample was scored")
        except RuntimeError:
            pass
    # the untouched state still re-finalises
    if env_mod.score_core(state) != 1.0:
        problems.append("the intact state no longer re-finalises")
    return check("recorded result bound: total, component, penalty, renderable/gated/cap, allocation, another rollout's result, "
                 "the bare number and a replaced sample are all refused; the intact state re-finalises",
                 not problems, "\n".join(problems))


def test_scoring_reads_the_frozen_policy_snapshot():
    """Codex T39 (rewrite) §5 — snapshot semantics, chosen and tested: the
    scorer consults the environment's frozen policy, never the live
    registries; a registry mutated after minting — or DURING scoring, from
    another thread — changes nothing; a mutated snapshot is refused."""
    import threading
    env = K.load_contract(INPUTS)
    text = GOLDEN.replace("Harbor Freight Ltd", "harbor freight ltd", 1).replace(
        '"Harbor Freight Ltd" "Customer payment settling SI-1044"', '"harbor freight ltd" "Customer payment settling SI-1044"')
    c = committed(text, env)
    before = K.score_committed(c).as_canonical()
    problems = []
    if not K.score_committed(c).undocumented:
        problems.append("fixture: the case-variant payee is not undocumented under the strict policy")
    saved = dict(C.COMPARISON_POLICIES["planted_repair.payee"])
    C.COMPARISON_POLICIES["planted_repair.payee"]["case_sensitive"] = False      # live mutation after minting
    P.POLICIES["bank_reconciliation"]["event.unbalanced"] = P.Consequence()      # and a consequence
    try:
        after = K.score_committed(c).as_canonical()
        if after != before:
            problems.append("a live registry mutation after minting changed the score")
        if env.policy.comparison("planted_repair.payee")["case_sensitive"] is not True:
            problems.append("the snapshot followed the live mutation")
        # concurrent: flip the registry continuously while scoring
        stop = threading.Event()

        def flipper():
            while not stop.is_set():
                C.COMPARISON_POLICIES["planted_repair.payee"]["case_sensitive"] = not C.COMPARISON_POLICIES["planted_repair.payee"]["case_sensitive"]
                P.POLICIES["bank_reconciliation"]["event.unbalanced"] = P.Consequence(gates_all=bool(stop.is_set()))
        t = threading.Thread(target=flipper, daemon=True)
        t.start()
        try:
            results = {canonical_bytes_of(K.score_committed(c).as_canonical()) for _ in range(20)}
        finally:
            stop.set()
            t.join(timeout=5)
        if len(results) != 1 or results != {canonical_bytes_of(before)}:
            problems.append(f"scoring under a concurrently mutated registry was not the snapshot's result ({len(results)} distinct)")
    finally:
        C.COMPARISON_POLICIES["planted_repair.payee"] = saved
        P.POLICIES["bank_reconciliation"]["event.unbalanced"] = P.Consequence(gates_all=True, blocks_render=True)
    # a fresh environment minted AFTER a registry change is a different environment
    C.COMPARISON_POLICIES["planted_repair.payee"]["case_sensitive"] = False
    try:
        env2 = K.load_contract(INPUTS)
        if env2.environment_digest == env.environment_digest or env2.scorer_contract_digest == env.scorer_contract_digest:
            problems.append("an environment minted under a changed registry shares the old identity")
        if not K.score_committed(committed(text, env2)).undocumented is False and K.score_committed(committed(text, env2)).undocumented:
            problems.append("the new environment did not apply its own (case-insensitive) policy")
    finally:
        C.COMPARISON_POLICIES["planted_repair.payee"] = saved
    # a mutated snapshot is refused by the environment digest
    frozen = env.policy
    object.__setattr__(env, "policy", dataclasses.replace(frozen, task="other"))
    try:
        K.score_committed(c)
        problems.append("a mutated policy snapshot scored")
    except RuntimeError:
        pass
    finally:
        object.__setattr__(env, "policy", frozen)
    return check("snapshot semantics: live mutation after minting and during scoring changes nothing; a new mint differs; "
                 "a mutated snapshot is refused", not problems, "\n".join(problems))


def canonical_bytes_of(data) -> bytes:
    return C.canonical_bytes(data)


def test_one_penalised_item_is_not_a_deliverable():
    """The adversary pass (round 1): a perfect solution plus ONE penalised
    item scored exactly 0.60 and the renderer printed the item verbatim —
    a wash entry, a zero-net fiction, a 200-character notice with tags and
    links, a changed title, a `close` on the live bank or AR account, an
    `open` of a ghost account. Each now has no deliverable: non-renderable,
    official 0, nothing at the public path, components kept as diagnostics."""
    env, state, write = _loop_env()
    ws = Path(state["workspace"])
    notice = "N" * 190
    spellings = {
        "same-account wash": GOLDEN + '\n2025-11-15 * "Nobody" "wash"\n  Assets:Bank:Checking   100.00 USD\n  Assets:Bank:Checking  -100.00 USD\n',
        "zero-net four-leg fiction": GOLDEN + '\n2025-11-30 * "Cascade Bank" "Reversal of the fee - refunded on appeal"\n'
                                     '  Assets:Bank:Checking   85.00 USD\n  Expenses:BankFees     -85.00 USD\n'
                                     '  Expenses:BankFees      85.00 USD\n  Assets:Bank:Checking  -85.00 USD\n',
        "zero-amount notice with decoration": GOLDEN + f'\n2025-11-30 ! "AUDIT NOTICE" "{notice}" #do-not-file ^hold\n'
                                              '  ref: "TR-441"\n  Assets:AR  0.00 USD\n  Equity:Opening  0.00 USD\n',
        "title changed": GOLDEN.replace('"Alpine Trading Co. - FY2025"', '"Alpine Trading Co. - FY2025 (UNAUDITED - do not file)"'),
        "close the bank account on the cut-off": GOLDEN + "\n2025-11-30 close Assets:Bank:Checking\n",
        "close receivables after period": GOLDEN + "\n2025-12-31 close Assets:AR\n",
        "ghost account opened, never posted": GOLDEN + "\n2025-01-01 open Equity:Suspense USD\n",
        "pre-existing narration edited": GOLDEN.replace('"Stationery and printer supplies"', '"Stationery"'),
    }
    problems = []
    for label, text in spellings.items():
        write(text)
        total = env_mod.score_core(state)
        result, delivery = state["piv_result"], state["piv_delivery"]
        if total != 0.0 or result.renderable or delivery.outcome != K.OUTCOME_POLICY_BLOCKED \
                or (ws / env_mod.LEDGER).exists() or not result.blocked_by:
            problems.append(f"{label}: total={total} renderable={result.renderable} outcome={delivery.outcome} "
                            f"ledger={(ws / env_mod.LEDGER).exists()} blocked_by={result.blocked_by}")
        if dict(result.components).get("targets_hit") != Decimal("1") and label != "ghost account opened, never posted":
            problems.append(f"{label}: diagnostic components were not retained: {result.components}")
    if "plug_accounts" not in state["piv_result"].blocked_by and False:
        pass
    write(GOLDEN + "\n2025-01-01 open Equity:Suspense USD\n")
    env_mod.score_core(state)
    if "Equity:Suspense" not in state["piv_result"].plug_accounts:
        problems.append("an opened-but-unposted account outside the chart is not a plug")
    return check(f"{len(spellings)} one-item spellings: non-renderable, official 0, no ledger at the public path, "
                 "components kept; an opened ghost account is a plug", not problems, "\n".join(problems))


def test_agent_input_never_quarantines():
    """Two quarantine buttons the adversary pass pressed: a tool argument of
    the wrong TYPE raised inside the tool body (our failure, by
    classification); a duplicate later `close` hid an inactivity from our
    validator while Beancount reported it (oracle disagreement = our
    failure). Both are the agent's now: a public tool error, a gated score."""
    env, state, write = _loop_env()
    problems = []
    for label, args in (("float limit", {"path": "ledger.beancount", "limit": 1.5}),
                        ("string offset", {"path": "ledger.beancount", "offset": "0"}),
                        ("null limit", {"path": "ledger.beancount", "limit": None}),
                        ("list offset", {"path": "ledger.beancount", "offset": [0]}),
                        ("bool limit", {"path": "ledger.beancount", "limit": True}),
                        ("int path", {"path": 42}),
                        ("dict pattern", {"pattern": {"a": 1}})):
        name = "grep" if "pattern" in args else "read_file"
        call = SimpleNamespace(id="c", name=name, arguments=json.dumps(args))
        replies = asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))
        if env_mod.evaluator_failure(state) is not None:
            problems.append(f"{label}: quarantined")
            break
        if not replies or replies[0].content != env_mod.PUBLIC_TOOL_ERROR:
            problems.append(f"{label}: reply {replies[0].content[:60] if replies else None!r}")
    ws = str(Path(state["workspace"]))
    # Offset clamping is pinned on a SLICED file: `ledger.beancount` is
    # returned whole and ignores offset/limit by contract, so it can no
    # longer witness the clamp. `policy.md` is bounded and numbered, which is
    # exactly the surface the clamp protects.
    huge = env_mod.read_file("policy.md", offset=10 ** 40, workspace=ws)
    negative = env_mod.read_file("policy.md", offset=-7, limit=1, workspace=ws)
    if huge.strip() or not negative.startswith("    1  "):
        problems.append(f"offset clamping: huge={huge[:40]!r} negative={negative[:20]!r}")
    padded = GOLDEN.replace("; Chart of accounts", "; " + ("x" * 300 + "\x0b") * 400)     # one physical 120 KB line
    r = parse_once(padded)
    if not isinstance(r, ProtocolFailure) or r.reason != "envelope.line_length":
        problems.append(f"a VT-padded physical line evaded the line-length cap: {r}")
    for label, text in (("duplicate close, later hides", GOLDEN + "\n2025-11-05 close Expenses:Office\n2025-12-31 close Expenses:Office\n"),
                        ("duplicate close, earlier hides", GOLDEN + "\n2025-12-31 close Expenses:Office\n2025-11-05 close Expenses:Office\n"),
                        ("duplicate open, later", GOLDEN.replace("2025-01-01 open Expenses:Office               USD\n",
                                                                 "2025-01-01 open Expenses:Office               USD\n2025-11-20 open Expenses:Office USD\n"))):
        r = parse_once(text)
        if not isinstance(r, Accepted):
            problems.append(f"{label}: {type(r).__name__} {r}")
            continue
        write(text)
        total = env_mod.score_core(state)
        if env_mod.evaluator_failure(state) is not None or total != 0.0 or state["piv_result"].renderable:
            problems.append(f"{label}: total={total} renderable={state['piv_result'].renderable} codes={r.finding_summary.codes}")
    return check("wrong-typed tool arguments are public tool errors; duplicate close/open are gated findings; nothing quarantines",
                 not problems, "\n".join(problems))


def test_posting_order_and_merge_labels():
    env, state, write = _loop_env()
    ws = Path(state["workspace"])
    problems = []
    reordered = GOLDEN.replace("  Expenses:Office                            420.00 USD\n  Assets:Bank:Checking                      -420.00 USD\n",
                               "  Assets:Bank:Checking                      -420.00 USD\n  Expenses:Office                            420.00 USD\n")
    if reordered == GOLDEN:
        return check("posting order", False, "fixture drift")
    write(reordered)
    if env_mod.score_core(state) != 1.0 or state["piv_result"].removed_or_altered:
        problems.append(f"reordering the legs of a pre-existing entry was not preservation: {state['piv_result'].removed_or_altered}")
    delivered = (ws / env_mod.LEDGER).read_text(encoding="utf-8")
    write(GOLDEN)
    env_mod.score_core(state)
    if delivered != (ws / env_mod.LEDGER).read_text(encoding="utf-8"):
        problems.append("the deliverable depends on the submitted leg order")
    merged = GOLDEN.replace('2025-11-26 * "Harbor Freight Ltd" "Customer payment settling SI-1044"\n  Assets:Bank:Checking                      4800.00 USD\n  Assets:AR                                -4800.00 USD\n',
                            '2025-11-26 * "Harbor Freight Ltd" "Both at once"\n  Assets:Bank:Checking                      4800.00 USD\n  Assets:AR                                -4800.00 USD\n'
                            '  Expenses:BankFees                           85.00 USD\n  Assets:Bank:Checking                       -85.00 USD\n')
    merged = merged.replace('2025-11-30 * "Cascade Bank" "Monthly account service charge"\n  Expenses:BankFees                           85.00 USD\n  Assets:Bank:Checking                       -85.00 USD\n', "")
    c = K.commit(parse_once(merged), env.contract, K.new_receipt(state["piv_rollout_id"], 9, env_mod.digests_of(merged.encode("utf-8"), submitted=merged)))
    o = K.score_committed(c)
    if not o.merged_events or o.fabricated:
        problems.append(f"a merged entry carries two labels: merged={o.merged_events} fabricated={o.fabricated}")
    return check("leg order is presentation (preserved, deliverable canonical); a merged entry carries one label",
                 not problems, "\n".join(problems))


def test_alter_and_duplicate_scoring_semantics():
    """The allocation contract for the two new kinds: retired original
    content is stale (explained, rendered from the original, unresolved),
    removing it is the repair, not tampering; both copies removed is
    tampering; the corrected entry beside the stale one is unresolved."""
    from beancount_ledger.graph import project as PJ
    from beancount_ledger.graph.worlds import alpine_2025_11 as A
    world, base_task = REGISTRY["bank_recon_001"]
    alter = PJ.AlterRecognition("office_transposed", "rec:office-2025-11", "transpose_digits", 0, "?")
    dup = PJ.DuplicateRecognition("rent_booked_twice", "rec:rent-2025-11", "?")
    fee = A.BANK_RECON_001.plan.mutations[1]                       # unrecorded_bank_fee
    task = dataclasses.replace(base_task, plan=PJ.MutationPlan((alter, dup, fee)))
    _, inputs = derive_contract(world, task)
    env = K.load_contract(inputs)
    original, golden = inputs.original_text, inputs.golden_text
    def leg(account, amount):                       # the projector's fixed layout
        return f"  {account:<{PJ.POSTING_ACCOUNT_WIDTH}}{amount:>{PJ.POSTING_AMOUNT_WIDTH}} USD\n"
    office_wrong = leg("Expenses:Office", "240.00") + leg("Assets:Bank:Checking", "-240.00")
    office_right = leg("Expenses:Office", "420.00") + leg("Assets:Bank:Checking", "-420.00")
    rent_entry = '2025-11-10 * "Cedar Property Group" "November office rent"\n' + leg("Expenses:Rent", "3500.00") + leg("Assets:Bank:Checking", "-3500.00")
    fee_entry = '2025-11-30 * "Cascade Bank" "Monthly account service charge"\n' + leg("Expenses:BankFees", "85.00") + leg("Assets:Bank:Checking", "-85.00")
    problems = []
    if office_wrong not in original or original.count(rent_entry) != 2 or fee_entry in original:
        return check("alter/duplicate scoring", False, "fixture drift: the opening ledger is not what the plan says")

    def outcome(text):
        c = committed(text, env)
        return K.score_committed(c) if isinstance(c, K.CommittedSubmission) else c

    g = outcome(golden)
    if g.total != Decimal("1") or g.unresolved_planted or g.removed_or_altered or not g.renderable or not g.complete:
        problems.append(f"golden: {g.as_dict()}")
    if dict(g.allocation.item_states) != {"office_transposed": "RESOLVED", "rent_booked_twice": "RESOLVED", "unrecorded_bank_fee": "RESOLVED"}:
        problems.append(f"golden states: {g.allocation.item_states}")
    untouched = outcome(original)
    if dict(untouched.allocation.item_states) != {"office_transposed": "STALE_ONLY", "rent_booked_twice": "EXTRA_PRESENT", "unrecorded_bank_fee": "MISSING"} \
            or untouched.complete:
        problems.append(f"untouched states: {untouched.allocation.item_states} complete={untouched.complete}")
    if untouched.total != Decimal("0") or set(untouched.unresolved_planted) != {"office_transposed", "rent_booked_twice", "unrecorded_bank_fee"} \
            or untouched.removed_or_altered or untouched.fabricated or not untouched.renderable or len(untouched.allocation.stale) != 2:
        problems.append(f"untouched: total={untouched.total} unresolved={untouched.unresolved_planted} stale={untouched.allocation.stale} "
                        f"removed={untouched.removed_or_altered} renderable={untouched.renderable}")
    # fix the fee only: partial, renderable, the two stale items remain
    fee_only = original + "\n" + fee_entry
    o = outcome(fee_only)
    if not (Decimal("0") < o.total < Decimal("1")) or set(o.unresolved_planted) != {"office_transposed", "rent_booked_twice"} or not o.renderable:
        problems.append(f"fee only: total={o.total} unresolved={o.unresolved_planted} renderable={o.renderable}")
    # corrected entry added but the wrong one left: unresolved, explained, renderable, no fabrication
    both = original.replace(office_wrong, office_wrong) + "\n" + '2025-11-18 * "Office Depot" "Stationery and printer supplies"\n' + office_right
    o = outcome(both)
    if "office_transposed" not in o.unresolved_planted or o.fabricated or not o.renderable or len(o.allocation.stale) != 2 \
            or dict(o.allocation.item_states)["office_transposed"] != "REPAIR_PLUS_STALE":
        problems.append(f"corrected beside stale: unresolved={o.unresolved_planted} fabricated={o.fabricated} renderable={o.renderable} states={o.allocation.item_states}")
    o = outcome(original.replace(office_wrong, "").replace('2025-11-18 * "Office Depot" "Stationery and printer supplies"\n', ""))
    if dict(o.allocation.item_states).get("office_transposed") != "REMOVED_WITHOUT_REPAIR":
        problems.append(f"wrong entry removed, no repair: {o.allocation.item_states}")
    # alter fixed properly: wrong entry replaced
    fixed_alter = original.replace(office_wrong, office_right)
    o = outcome(fixed_alter)
    if "office_transposed" in o.unresolved_planted or o.removed_or_altered:
        problems.append(f"alter repaired: unresolved={o.unresolved_planted} removed={o.removed_or_altered}")
    # duplicate fixed: one copy removed is the repair, not tampering
    fixed_dup = original.replace(rent_entry, "", 1)
    o = outcome(fixed_dup)
    if "rent_booked_twice" in o.unresolved_planted or o.removed_or_altered:
        problems.append(f"duplicate repaired: unresolved={o.unresolved_planted} removed={o.removed_or_altered}")
    # both copies removed: tampering, non-renderable
    o = outcome(original.replace(rent_entry, ""))
    if not o.removed_or_altered or o.renderable or "rent_booked_twice" not in o.unresolved_planted \
            or dict(o.allocation.item_states)["rent_booked_twice"] != "OVER_REMOVED" or "tampered_preservation" not in o.blocked_by:
        problems.append(f"both copies removed: removed={o.removed_or_altered} renderable={o.renderable} states={o.allocation.item_states} blocked={o.blocked_by}")
    # a third copy: surplus beyond the original is unexplained
    o = outcome(original + "\n" + rent_entry)
    if not o.fabricated or o.renderable:
        problems.append(f"third copy: fabricated={o.fabricated} renderable={o.renderable}")
    # the stale wrong amount renders from the ORIGINAL (the deliverable is honest about what the agent did)
    c = committed(fee_only, env)
    rendered = K.render_committed(c)
    if "240.00 USD" not in rendered or rendered.count('"November office rent"') != 2 or "85.00 USD" not in rendered:
        problems.append("the deliverable for partial work does not show the stale content and the repair")
    return check("alter/duplicate: golden 1.0; untouched 0 with two stale; fee-only partial and renderable; corrected beside stale "
                 "unresolved; proper repairs not tampering; both copies removed is tampering; a third copy is unexplained; "
                 "stale renders from the original", not problems, "\n".join(problems))


def test_the_four_identities_the_reward_key_composes():
    """Codex T43 §2: each component of item identity, shown separately.

    The full repair key is `(kind, date, postings, counterparty, booked bank
    amount, copies)`, and the sweep compares whole tuples. That is only
    trustworthy if each field can be shown to matter on its own, so this
    isolates four of them against the REAL allocation and scorer:

    RESOLUTION identity is the date and the exact posting multiset, and
    nothing else. `allocate()`'s eligibility predicate is literally
    `t.date == item.date and _txn_shape(t) == item.required`, so a repair
    with the correct date and postings but a WRONG PAYEE still resolves the
    item — and pays exactly `PENALTY_UNDOCUMENTED` for it, once, with the
    item named in `undocumented`.

    ATTRIBUTION identity is the payee, and it is a separate penalty rather
    than part of resolution. The converse therefore fails: the correct payee
    with a wrong date, or with wrong postings, resolves nothing.

    OCCURRENCE identity carries multiplicity and the booked amount: the
    duplicate's expected copy count and the alteration's wrong shape are what
    `_retired_keys` / `_expected_counts` retire from the preservable
    multiset, so one copy too many and one copy too few are different
    outcomes, and the altered entry's own figure is what makes the stale copy
    stale.
    """
    from beancount_ledger.graph import project as PJ
    world, base_task = REGISTRY["bank_recon_001"]
    fee = REGISTRY["bank_recon_001"][1].plan.mutations[1]              # unrecorded_bank_fee
    alter = PJ.AlterRecognition("office_transposed", "rec:office-2025-11", "transpose_digits", 0, "?")
    dup = PJ.DuplicateRecognition("rent_booked_twice", "rec:rent-2025-11", "?")
    task = dataclasses.replace(base_task, plan=PJ.MutationPlan((alter, dup, fee)))
    _, inputs = derive_contract(world, task)
    env = K.load_contract(inputs)
    original, golden = inputs.original_text, inputs.golden_text

    def leg(account, amount):
        return f"  {account:<{PJ.POSTING_ACCOUNT_WIDTH}}{amount:>{PJ.POSTING_AMOUNT_WIDTH}} USD\n"

    fee_right = '2025-11-30 * "Cascade Bank" "Monthly account service charge"\n' \
        + leg("Expenses:BankFees", "85.00") + leg("Assets:Bank:Checking", "-85.00")
    problems = []
    if fee_right in original:
        return check("the four identities", False, "fixture drift: the fee entry is already in the ledger")

    def outcome(text):
        c = committed(text, env)
        return K.score_committed(c) if isinstance(c, K.CommittedSubmission) else c

    def with_fee(date="2025-11-30", payee="Cascade Bank", amount="85.00"):
        entry = f'{date} * "{payee}" "Monthly account service charge"\n' \
            + leg("Expenses:BankFees", amount) + leg("Assets:Bank:Checking", f"-{amount}")
        return golden.replace(fee_right, entry)

    # 1. correct date + postings, WRONG payee: resolved, and undocumented once
    wrong_payee = outcome(with_fee(payee="Cascade Bnak"))
    right = outcome(golden)
    if dict(wrong_payee.allocation.item_states).get("unrecorded_bank_fee") != "RESOLVED" \
            or "unrecorded_bank_fee" in wrong_payee.unresolved_planted:
        problems.append(f"wrong payee did not resolve the item: {wrong_payee.allocation.item_states}")
    if len(wrong_payee.undocumented) != 1 or "unrecorded_bank_fee" not in wrong_payee.undocumented[0]:
        problems.append(f"wrong payee: undocumented={wrong_payee.undocumented}")
    if wrong_payee.fabricated or wrong_payee.removed_or_altered or wrong_payee.merged_events:
        problems.append(f"wrong payee carried a second label: {wrong_payee.as_dict()}")
    if dict(wrong_payee.components) != dict(right.components):
        problems.append(f"wrong payee moved a component: {wrong_payee.components} vs {right.components}")
    gap = right.total - wrong_payee.total
    if gap != -K.PENALTY_UNDOCUMENTED:
        problems.append(f"the payee cost {gap}, not PENALTY_UNDOCUMENTED ({-K.PENALTY_UNDOCUMENTED})")

    # 2. correct payee, WRONG date: not resolved
    wrong_date = outcome(with_fee(date="2025-11-29"))
    if dict(wrong_date.allocation.item_states).get("unrecorded_bank_fee") != "MISSING" \
            or "unrecorded_bank_fee" not in wrong_date.unresolved_planted or not wrong_date.fabricated:
        problems.append(f"wrong date: states={wrong_date.allocation.item_states} "
                        f"fabricated={wrong_date.fabricated}")

    # 3. correct payee and date, WRONG postings: not resolved
    wrong_shape = outcome(with_fee(amount="85.50"))
    if dict(wrong_shape.allocation.item_states).get("unrecorded_bank_fee") != "MISSING" \
            or "unrecorded_bank_fee" not in wrong_shape.unresolved_planted:
        problems.append(f"wrong postings: states={wrong_shape.allocation.item_states}")

    # 4. occurrence identity: the duplicate's copy count
    rent = '2025-11-10 * "Cedar Property Group" "November office rent"\n' \
        + leg("Expenses:Rent", "3500.00") + leg("Assets:Bank:Checking", "-3500.00")
    if original.count(rent) != 2 or golden.count(rent) != 1:
        problems.append("fixture drift: the duplicated entry is not two copies in the original and one in the golden")
    else:
        too_many = outcome(golden + "\n" + rent)                       # two copies again
        too_few = outcome(golden.replace(rent, "", 1))                 # none at all
        if dict(too_many.allocation.item_states).get("rent_booked_twice") != "EXTRA_PRESENT":
            problems.append(f"one copy too many: {too_many.allocation.item_states}")
        if dict(too_few.allocation.item_states).get("rent_booked_twice") != "OVER_REMOVED" \
                or not too_few.removed_or_altered:
            problems.append(f"one copy too few: states={too_few.allocation.item_states} "
                            f"removed={too_few.removed_or_altered}")

    # 5. occurrence identity: the altered entry's BOOKED amount is what is retired
    booked = {item.id: item.replaces for item in env.planted if item.kind == "alter"}
    retired = K._retired_keys(env)
    office_wrong = leg("Expenses:Office", "240.00") + leg("Assets:Bank:Checking", "-240.00")
    if booked.get("office_transposed") != (("Assets:Bank:Checking", "-240"), ("Expenses:Office", "240")) \
            or "office_transposed" not in retired:
        problems.append(f"the alteration does not retire its booked shape: replaces={booked} retired={sorted(retired)}")
    kept_wrong = outcome(golden.replace(leg("Expenses:Office", "420.00") + leg("Assets:Bank:Checking", "-420.00"),
                                        leg("Expenses:Office", "420.00") + leg("Assets:Bank:Checking", "-420.00"))
                         + "\n" + '2025-11-18 * "Office Depot" "Stationery and printer supplies"\n' + office_wrong)
    if dict(kept_wrong.allocation.item_states).get("office_transposed") != "REPAIR_PLUS_STALE" \
            or kept_wrong.fabricated:
        problems.append(f"the booked amount left beside the repair is stale, not fiction: "
                        f"states={kept_wrong.allocation.item_states} fabricated={kept_wrong.fabricated}")
    return check("resolution identity is date + posting multiset (a wrong payee resolves and costs exactly "
                 "PENALTY_UNDOCUMENTED); a wrong date or wrong postings resolve nothing however right the "
                 "payee; the duplicate's copy count and the alteration's booked amount are occurrence identity",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_four_identities_the_reward_key_composes,
    test_a_commitment_is_bound_to_its_environment,
    test_the_deliverable_is_the_canonical_rendering,
    test_the_adapter_refuses_everything_but_a_minted_outcome,
    test_recheck_recomputes_identities_from_the_data,
    test_allocation_keeps_multiplicity_without_source_positions,
    test_reserved_provenance_keys_cannot_be_authored,
    test_every_emitted_code_is_registered,
    test_parser_provenance_never_enters_identity_or_score,
    test_the_frozen_allocation_and_penalty_labels,
    test_initialisation_failures_are_typed,
    test_max_findings_is_derived_and_below_saturation,
    test_nothing_but_the_committed_object_can_be_scored,
    test_finalisation_hashes_the_deliverable_and_the_last_commit_decides,
    test_publication_is_revisioned_and_transactional,
    test_the_audit_archive_is_contained,
    test_reserved_key_scanner_agrees_with_beancounts_lexer,
    test_stale_state_after_an_episode_reset_is_refused,
    test_retained_fields_are_constrained_or_replaced,
    test_the_recorded_result_is_bound_not_only_the_number,
    test_scoring_reads_the_frozen_policy_snapshot,
    test_one_penalised_item_is_not_a_deliverable,
    test_agent_input_never_quarantines,
    test_posting_order_and_merge_labels,
    test_alter_and_duplicate_scoring_semantics,
]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
