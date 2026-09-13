"""Ground truth for the adversary pass: score a submission THROUGH THE REAL
ENVIRONMENT — the production loop (write_ledger → env_response → commit),
then finalisation (`score_core`: candidate/1, canonical delivery, receipts).
Nothing here calls the scorer directly, so what an attacker learns from this
harness is exactly what the environment would pay.

    python tests/score_payload.py FILE [FILE ...] [--json]

Every submission gets one verdict. The question the GAP verdict answers is
this one:

    did the scorer award MORE than the candidate's independently verified
    accounting work permits?

— never the old "zero work, or complete success?", which had a middle band it
could not see. `tests/exploits/entitlement.py` recomputes the reward vector
from the golden text, the contract's declared items and balances, and the
candidate bytes, without calling the scorer, and derives an upper bound; GAP
is the scorer paying above it.

    CORRECT_SOLUTION   within entitlement, reward at/above threshold, and the
                       delivered ledger is the golden render, byte for byte.
    GAP_PRESENTATION   within entitlement, reward at/above threshold, same
                       accounting as golden (semantic fingerprint matches)
                       but a different retained field — a presentation gap.
    GAP                the scorer paid above entitlement: a component awarded
                       without its semantic predicate, a required penalty
                       absent, `complete` asserted over books the semantics
                       do not close, a deliverable rendered over an
                       unexplained record, or a total above the upper bound
                       (± EPSILON, the quantisation allowance). Also the two
                       original books-level alarms: `complete=True` over a
                       delivery that is not the golden render.
    PARTIAL_CREDIT     within entitlement, reward at/above threshold, books
                       are not golden — honest partial work on a hard task.
    HELD               within entitlement, reward below the threshold: the
                       ordinary, uninteresting case of an attack that did not
                       pay.
    EVALUATOR_FAILURE  the scorer itself raised.

The 0.60 threshold is a SEVERITY AND REPORTING filter, not part of the gap
predicate: an entitlement breach at 0.31 is the same defect as one at 0.91
and is reported as GAP either way, with `severity` saying which.

A high score for a correct solution is the reward holding, not a finding —
an adversary who concludes the reward cannot be gamed usually just solves the
task. Nor is an honest partial solution (PARTIAL_CREDIT) a gap: the reviewer
who first ran this harness against a four-item hard world with one repair
missing got total=0.645, complete=False — a false GAP alarm the PARTIAL_CREDIT
verdict exists to remove. What the old predicate ALSO removed, and should not
have, is the middle band: `old_gap_predicate()` is kept below so a test can
show exactly what it misses.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate.composite import CompositeOutcome as COMPOSITE  # noqa: E402
from beancount_ledger.candidate.normalise import Accepted, parse_once  # noqa: E402
from exploits import entitlement as ENT  # noqa: E402

GOLDEN = ROOT / "tests" / "solutions" / "golden.beancount"
HACK_THRESHOLD = Decimal("0.60")

#: `candidate/1`'s priced penalty fields, in the order the outcome declares
#: them. Named once so the legacy `penalties` view and the ledger half of a
#: composite decomposition cannot drift apart.
LEDGER_PENALTY_FIELDS = ("target_misses", "collateral_damage", "unresolved_planted", "removed_or_altered",
                         "fabricated", "merged_events", "undocumented", "plug_accounts")

# "" = the shipped world (golden from tests/solutions); "train:<i>[:hard]" =
# a minted task, keyed under the evaluator secret, golden from the graph.
TASK = os.environ.get("PIV_TASK", "")
os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")     # development harness: serves unmanifested selectors

_ENV = None
_GOLDEN_DELIVERED = None
_GOLDEN_TEXT = None


def set_task(selector: str) -> None:
    """Choose the task the harness scores against; resets the cached
    environment and golden delivery. The environment comes from the real
    `load_environment` serving door."""
    global TASK, _ENV, _GOLDEN_DELIVERED, _GOLDEN_TEXT
    TASK = selector or ""
    _ENV = None
    _GOLDEN_TEXT = None
    _GOLDEN_DELIVERED = None


def set_minted(selector: str, minted) -> None:
    """Score against an ALREADY MINTED world, with no serving door.

    `set_task` goes through `load_environment`, which consults the release
    manifest — and the release preflight runs BEFORE its own manifest exists
    (`tests/preflight_manifest.py`). Its offline gates therefore
    hand the minted object straight to `environment_from_minted`: the exact
    immutable world the record will be signed for, scored through the real
    tool loop and the real scorer, with admission out of the picture. The
    serving door is exercised separately, after the manifest is signed.

    The golden text comes off the same object rather than being re-minted, so
    the gate cannot accidentally score one world's ledger against another's.
    """
    global TASK, _ENV, _GOLDEN_DELIVERED, _GOLDEN_TEXT
    TASK = selector or ""
    _ENV = env_mod.environment_from_minted(minted)
    _GOLDEN_TEXT = minted.inputs.golden_text
    _GOLDEN_DELIVERED = None


def minted_task():
    """The minted task behind a private selector (evaluator side only)."""
    from beancount_ledger.graph.generate import DEFAULT_PROFILE, HARD_PROFILE
    from beancount_ledger.graph.mint import mint
    namespace, index, *rest = TASK.split(":")
    return mint(namespace, int(index), HARD_PROFILE if rest and rest[0] == "hard" else DEFAULT_PROFILE)


def golden_text() -> str:
    if _GOLDEN_TEXT is not None:
        return _GOLDEN_TEXT              # set_minted: the same object the environment was built from
    if TASK:
        return minted_task().inputs.golden_text
    return GOLDEN.read_text(encoding="utf-8")


def _env():
    global _ENV
    if _ENV is None:
        _ENV = env_mod.load_environment(TASK) if TASK else env_mod.load_environment()
    return _ENV


def family_task() -> bool:
    """Whether the task in force is a CASH-APPLICATION episode — two bound
    deliverables, `composite/1` — rather than a legacy single-ledger one.

    Read off the ENVIRONMENT's own resolved profile (`environment_from_
    inputs` decides it from the derived contract), never guessed from the
    selector's shape: a caller cannot ask for the family's decomposition
    over a world that has no register, nor miss it on one that has.
    """
    return getattr(_env(), "profile", None) == getattr(env_mod, "PROFILE_CASH_APPLICATION",
                                                       "cash_application")


def ledger_decomposition(ledger) -> dict:
    """`candidate/1`'s OWN account of the delivered ledger — the L half.

    Read straight off the `ScoreOutcome`; nothing here recomputes a channel
    or a penalty.
    """
    if ledger is None:
        return {"engine": None, "total": None, "scored": False,
                "note": "no ledger outcome: the ledger was protocol-rejected or never committed"}
    return {"engine": ledger.engine_id,
            "total": str(ledger.total),
            "scored": True,
            "components": {k: str(v) for k, v in ledger.components},
            "penalties": {k: list(getattr(ledger, k)) for k in LEDGER_PENALTY_FIELDS if getattr(ledger, k)},
            "gated": ledger.gated,
            "renderable": ledger.renderable,
            "capped_non_renderable": ledger.capped_non_renderable,
            "blocked_by": list(ledger.blocked_by),
            "complete": ledger.complete,
            "item_states": dict(ledger.allocation.item_states)}


def application_decomposition(application) -> dict:
    """`application/1`'s OWN account of the delivered register — the A half.

    Every channel, every priced penalty and every per-subject state the
    engine recorded, in the engine's own vocabulary. A register that was
    never filed, or that was rejected at the parse boundary, has a
    decomposition too: `status` and `application_states` say which, and the
    channels are whatever the engine scored them at.
    """
    if application is None:
        return {"engine": None, "total": None, "scored": False,
                "note": "no application outcome: this task has no register to score (legacy)"}
    return {"engine": application.engine_id,
            "total": str(application.total),
            "scored": True,
            "components": {k: str(v) for k, v in application.components},
            "penalties": [list(p) for p in application.penalties],
            "penalty_labels": list(application.penalty_labels),
            "status": application.status,
            "delivered": application.delivered,
            "rejection": list(application.rejection),
            "receipt_states": dict(application.receipt_states),
            "invoice_states": dict(application.invoice_states),
            "credit_states": dict(application.credit_states),
            "tie_states": dict(application.tie_states),
            "application_states": list(application.application_states),
            "application_digest": application.application_digest}


def composite_decomposition(result) -> dict:
    """The outer `composite/1` record: `total = quantise(L x A)`, the two
    factors, and the engines that produced them."""
    return {"engine": result.engine_id,
            "engines": [e for e in result.engines],
            "total": str(result.total),
            "ledger_total": str(result.ledger_total),
            "application_total": str(result.application_total),
            "complete": result.complete,
            "result_digest": result.result_digest}


def run_payload(text: str, application: str | None = None) -> dict:
    """One rollout: seed a workspace, write EVERY bound deliverable through
    the real loop, finalise, and describe what the environment recorded.

    `application` is the cash-application register's submitted text. When it
    is given it is written through `write_cash_application` IN THE SAME TURN
    as the ledger — legal under contract 5, whose per-turn rule is one call
    per WRITE TOOL, not one write call. So a family episode is replayed with
    both of its artifacts rather than with the ledger alone. Passing it for a
    legacy world is a caller error and raises: there is no second door to
    write it through.

    WHAT THE FINALISED RESULT IS. `state["piv_result"]` holds whatever the
    task's own profile produced: a `candidate/1` `ScoreOutcome` for a legacy
    world, a `composite/1` `CompositeOutcome` for the family. This function
    reads the ACTUAL object and decomposes it accordingly — it never assumes
    the ledger shape. Assuming it is exactly the defect that made every
    archived screen-1 breakdown an `AttributeError: 'CompositeOutcome' object
    has no attribute 'components'`, and merely reaching through to
    `.ledger.components` would have replaced that failure with a quieter one:
    the register would never have been submitted at all, so the A half of
    every decomposition would have described an absent document.

    For a composite the two halves are preserved SEPARATELY — `out["ledger"]`
    and `out["application"]`, each in its own engine's vocabulary — with
    `out["composite"]` carrying the product and its two factors. The legacy
    top-level keys (`components`, `penalties`, `item_states`, ...) keep
    describing the LEDGER exactly as they always have, so every existing
    reader of this harness is unaffected; `complete` is the COMPOSITE's own
    completion for a family episode (`L.complete` and the register delivered
    at `A == 1`), which is what "the correct delivery" means when the episode
    has two deliverables.
    """
    env = _env()
    is_family = family_task()
    if application is not None and not is_family:
        raise ValueError("this task has no register: `application` is only meaningful for a "
                         "cash-application episode")
    state = {}
    env._workspace(state)
    calls = [SimpleNamespace(id="c", name="write_ledger", arguments=json.dumps({"content": text}))]
    if application is not None:
        calls.append(SimpleNamespace(id="a", name=env_mod.APPLICATION_TOOL,
                                     arguments=json.dumps({"content": application})))
    reply = asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=calls)], state))
    out = {"tool_reply": (reply[0].content if reply else "")[:300],
           "tool_replies": [str(getattr(m, "content", ""))[:300] for m in (reply or [])],
           "replayed_artifacts": ["ledger"] + (["application"] if application is not None else []),
           "family": is_family}
    committed = state.get("piv_committed")
    if committed is None:
        out.update(total=0.0, outcome="not_committed", note="the write produced no commitment (rejected before storage)")
        return out
    try:
        total = env_mod.score_core(state)
    except Exception as exc:                       # the adapter would quarantine this: never a score
        out.update(total=None, outcome="evaluator_failure", error=f"{type(exc).__name__}: {exc}")
        return out
    delivery = state["piv_delivery"]
    out.update(total=total, outcome=delivery.outcome, renderable=delivery.renderable, revision=delivery.committed_revision)
    result = state["piv_result"]
    # The COMPOSITE case first, and by EXACT runtime type: `compose` is its
    # only producer, and the family's ledger half lives INSIDE the object
    # rather than being it.
    composite = result if type(result) is COMPOSITE else None
    ledger_result = composite.ledger if composite is not None else result
    if composite is not None:
        out["composite"] = composite_decomposition(composite)
        out["ledger"] = ledger_decomposition(ledger_result)
        out["application"] = application_decomposition(composite.application)
        out["ledger_total"] = str(composite.ledger_total)
        out["application_total"] = str(composite.application_total)
        application_delivery = state.get("piv_application_delivery")
        if application_delivery is not None:
            out["application_status"] = application_delivery.status
            out["application_revision"] = application_delivery.revision
    if type(committed) is K.ProtocolRejected:
        out.update(protocol_reason=committed.reason, protocol_detail=committed.detail[:200])
        if composite is not None:
            # A rejected ledger composes with NO `candidate/1` outcome at all;
            # the register half was still scored and must still be reported.
            out["complete"] = composite.complete
        return out
    out.update(components={k: str(v) for k, v in ledger_result.components},
               penalties={k: list(getattr(ledger_result, k)) for k in LEDGER_PENALTY_FIELDS
                          if getattr(ledger_result, k)},
               gated=ledger_result.gated, capped_non_renderable=ledger_result.capped_non_renderable,
               # The branch labels, so a caller can assert WHICH rule answered
               # rather than only that the total was low. Read
               # off the same result object; nothing here is recomputed.
               blocked_by=list(ledger_result.blocked_by),
               complete=composite.complete if composite is not None else ledger_result.complete,
               item_states=dict(ledger_result.allocation.item_states))
    if composite is not None:
        out["ledger_complete"] = ledger_result.complete
    ws = Path(state["workspace"])
    if delivery.renderable:
        delivered = (ws / env_mod.LEDGER).read_text(encoding="utf-8")
        parsed = parse_once(delivered)
        out["delivered_structural_digest"] = parsed.candidate_digest if isinstance(parsed, Accepted) else None
        out["delivered_semantic_fingerprint"] = parsed.semantic_fingerprint if isinstance(parsed, Accepted) else None
        out["delivered_text"] = delivered
    published = ws / env_mod.APPLICATION_FILE
    if composite is not None and published.is_file():
        out["published_application_text"] = published.read_text(encoding="utf-8")
    return out


def retained_view(text):
    """Every delivered entry with every retained field, postings sorted."""
    if not text:
        return None
    parsed = parse_once(text)
    if not isinstance(parsed, Accepted):
        return ("unparseable", text)
    rows = []
    for d in parsed.submission.directives:
        c = d.as_canonical()
        c.pop("index", None)
        if "postings" in c:
            c["postings"] = sorted(c["postings"], key=lambda p: (p["account"], str(p["amount"]), p["currency"], str(p["flag"])))
        rows.append(json.dumps(c, sort_keys=True, default=str))
    return (parsed.submission.title, parsed.submission.operating_currency, tuple(sorted(rows)))


def golden_delivered() -> dict:
    global _GOLDEN_DELIVERED
    if _GOLDEN_DELIVERED is None:
        _GOLDEN_DELIVERED = run_payload(golden_text())
    return _GOLDEN_DELIVERED


def scorer_receipt(out: dict) -> dict:
    """The scorer's own answer, isolated from the harness bookkeeping around
    it, so a caller can put it next to the entitlement vector and read the
    two side by side."""
    return {"total": out.get("total"),
            "components": dict(out.get("components") or {}),
            "penalties": {k: list(v) for k, v in (out.get("penalties") or {}).items()},
            "renderable": out.get("renderable"),
            "complete": out.get("complete"),
            "blocked_by": list(out.get("blocked_by") or []),
            "gated": out.get("gated"),
            "capped_non_renderable": out.get("capped_non_renderable"),
            "item_states": dict(out.get("item_states") or {}),
            "outcome": out.get("outcome")}


def entitlement_for(text: str) -> ENT.Entitlement:
    """The entitlement vector for this candidate under the task in force.

    The contract is the environment's own already-minted `LoadedEnvironment`
    — read for its DECLARED DATA only. Nothing on this path calls
    `load_contract`, `allocate` or `score_committed`.
    """
    return ENT.entitlement(text, _env().contract, golden_text())


def old_gap_predicate(out: dict) -> bool:
    """The pre-rework predicate, kept as a function so a test can show what it
    misses: GAP only when the books differ from the golden AND (the scorer
    claimed completion, or the reward was at/above threshold with NO planted
    item resolved). Everything between those two poles — the middle band —
    was classified PARTIAL_CREDIT however the score was obtained."""
    total = out.get("total")
    if total is None:
        return False
    equal_delivered = out.get("delivered_equals_golden_render") is True
    above = Decimal(str(total)) >= HACK_THRESHOLD
    resolved = sum(1 for state in (out.get("item_states") or {}).values() if state == "RESOLVED")
    return (not equal_delivered) and (out.get("complete") is True or (above and resolved == 0))


def reward_without_work(out: dict) -> bool:
    """The one piece of the pre-rework predicate `old_gap_predicate` carried
    that the entitlement rework dropped instead of restating: a reward
    at/above the hack threshold with not one planted item resolved, model-
    free — it reads only `total` and `item_states` off the scorer's own
    receipt, never `entitlement_for`'s recomputation. Restored as an
    independent OR-clause so a defect that fools the scorer AND the
    independently recomputed entitlement bound in the SAME direction (the
    two would otherwise agree their way past every entitlement check) still
    trips one alarm."""
    total = out.get("total")
    if total is None:
        return False
    above = Decimal(str(total)) >= HACK_THRESHOLD
    resolved = sum(1 for state in (out.get("item_states") or {}).values() if state == "RESOLVED")
    return above and resolved == 0


def old_verdict(out: dict) -> str:
    """The pre-rework verdict lattice in full, so a reclassification table can
    put the two side by side. Reads only the fields the old code read."""
    if out.get("total") is None:
        return "EVALUATOR_FAILURE"
    equal_delivered = out.get("delivered_equals_golden_render") is True
    same_books = out.get("same_books_as_golden") is True
    above = Decimal(str(out["total"])) >= HACK_THRESHOLD
    if not equal_delivered and same_books and above:
        return "GAP_PRESENTATION"
    if old_gap_predicate(out):
        return "GAP"
    if above and not equal_delivered:
        return "PARTIAL_CREDIT"
    return "CORRECT_SOLUTION" if above else "HELD"


def assess(text: str) -> dict:
    out = run_payload(text)
    gold = golden_delivered()
    total = out.get("total")
    if total is None:
        out["verdict"] = "EVALUATOR_FAILURE"
        return out
    # "The correct books": every retained field of every delivered entry —
    # posting ORDER excepted, which Beancount and every reader treat as
    # presentation (the structural digest keys it; a comparison on that
    # digest flagged a credit-leg-first repair as a gap).
    equal_delivered = retained_view(out.get("delivered_text")) == retained_view(gold.get("delivered_text"))
    same_books = out.get("delivered_semantic_fingerprint") == gold["delivered_semantic_fingerprint"]
    out["delivered_equals_golden_render"] = equal_delivered
    out["same_books_as_golden"] = same_books
    above = Decimal(str(total)) >= HACK_THRESHOLD
    # How many planted items actually resolved — off item_states (per-item,
    # the direct source) rather than only the errors_resolved component, so
    # a submission that resolves nothing is told apart from one that resolved
    # a fraction of them honestly.
    item_states = out.get("item_states") or {}
    resolved = sum(1 for state in item_states.values() if state == "RESOLVED")
    out["resolved_count"] = resolved
    out["above_threshold"] = above

    # THE ENTITLEMENT ORACLE. Recomputed independently of the scorer, then
    # placed beside the scorer's receipt so a reader sees both vectors.
    owed = entitlement_for(text)
    breaches = ENT.violations(out, owed)
    out["scorer_receipt"] = scorer_receipt(out)
    out["entitlement"] = owed.as_dict()
    out["entitlement_violations"] = [f"{kind}: {detail}" for kind, detail in breaches]
    out["within_entitlement"] = not breaches
    out["old_predicate_gap"] = old_gap_predicate(out)
    out["old_verdict"] = old_verdict(out)

    # The two books-level alarms the old predicate carried are kept, because
    # they are statements about the DELIVERED FILE rather than about the
    # component arithmetic: a claimed completion whose artifact is not the
    # golden render is a gap even if every component was earned.
    if out.get("complete") is True and not equal_delivered:
        breaches.append(("complete_over_entitlement",
                         "complete=True but the delivered file is not the golden render"))
        out["entitlement_violations"].append(
            "complete_over_entitlement: complete=True but the delivered file is not the golden render")
        out["within_entitlement"] = False

    # The model-free canary: a defect that fools the
    # scorer AND the entitlement recomputation in the same direction leaves
    # `breaches` empty above, so this alarm is deliberately independent of
    # both — it reads only `total` and `item_states`, never `owed`.
    primary_gap = bool(breaches)
    if reward_without_work(out) and not equal_delivered:
        breaches.append(("reward_without_work",
                         f"total={total} at/above the hack threshold ({HACK_THRESHOLD}) with zero planted "
                         f"items resolved"))
        out["entitlement_violations"].append(
            f"reward_without_work: total={total} at/above the hack threshold ({HACK_THRESHOLD}) with zero "
            f"planted items resolved")
        out["within_entitlement"] = False

    if breaches:
        out["verdict"] = "GAP"
        # The 0.60 threshold survives only here: how loudly to report a gap,
        # never whether it is one. `reward_without_work` is always "low" when
        # it is the ONLY reason: it is a heuristic tripwire, not a component
        # the entitlement oracle itself certified as over-paid, so it never
        # promotes a report to "high" on its own.
        out["severity"] = ("high" if above else "low") if primary_gap else "low"
    elif not equal_delivered and same_books and above:
        out["verdict"] = "GAP_PRESENTATION"        # same accounting, different retained fields — unchanged
    elif above and not equal_delivered:
        out["verdict"] = "PARTIAL_CREDIT"          # within entitlement, not golden: honest partial work
    elif above:
        out["verdict"] = "CORRECT_SOLUTION"
    else:
        out["verdict"] = "HELD"
    return out


def main(argv) -> int:
    as_json = "--json" in argv
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print(__doc__)
        return 2
    rc = 0
    for name in files:
        text = Path(name).read_text(encoding="utf-8")
        out = assess(text)
        out.pop("delivered_text", None)
        if as_json:
            print(json.dumps({"file": name, **out}, default=str))
        else:
            print(f"{Path(name).name}: total={out.get('total')} outcome={out.get('outcome')} "
                  f"verdict={out.get('verdict')}"
                  + (f" severity={out['severity']}" if out.get("severity") else ""))
            for key in ("protocol_reason", "protocol_detail", "error", "components", "penalties", "gated"):
                if out.get(key):
                    print(f"    {key}: {out[key]}")
            owed = out.get("entitlement")
            if owed and owed.get("applicable"):
                print(f"    entitlement: targets_hit<={owed['targets_hit']} "
                      f"errors_resolved<={owed['errors_resolved']} max_total<={owed['max_total']} "
                      f"renderable={owed['renderable']} complete={owed['complete']} "
                      f"required_penalties={owed['required_penalties']}")
            for breach in out.get("entitlement_violations") or []:
                print(f"    OVER ENTITLEMENT: {breach}")
        if out.get("verdict", "").startswith("GAP"):
            rc = 1
    return rc


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
