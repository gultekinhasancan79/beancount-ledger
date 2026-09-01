"""Checker soundness, differentially, against the real scorer.

`check_identifiable` claims something about the WORLD: the public evidence
leaves a reader exactly one defensible repair. The scorer claims something
about a SUBMISSION: this ledger closes the month or it does not. Codex T41 §3
asks for the two to be pinned against each other, because each can be wrong
in a way its own test suite cannot see — a checker that certifies an
ambiguous world looks identical to a checker that is right, and a scorer that
accepts two unlike repairs looks identical to a scorer that accepts one.

    checker says unique  <=>  the scorer admits exactly one complete
                              semantic solution class

So, for a handful of generated worlds:

    enumerate the bounded repair grammar around every plausible pairing —
    the golden repair, each single planted item, each pair of them, the
    untouched original, and the WRONG readings a checker could plausibly
    admit: the repair entry carried at the transaction's own date instead of
    the bank's (which `## Dates` settles the other way for an item the books
    do not carry at all — contract change B), the repair attributed to another
    account or another party, an alteration corrected by a second adjusting
    entry instead of by restating the entry, and a doubled entry whose OTHER
    copy was the one removed;

    score every candidate through the real loop — workspace, `write_ledger`,
    `env_response` (which commits), `score_core` (which scores, renders and
    publishes). Nothing here calls the scorer directly, so what this test
    learns is what the environment would actually pay;

    quotient the winners by semantic equivalence. A candidate is a SOLUTION
    when the outcome is COMPLETE and the total is exactly 1; two solutions
    are the same solution when the delivered books have the same semantic
    fingerprint, so removing the first copy of a duplicate rather than the
    second is not a second answer;

    assert the equivalence above, and assert that when the checker says
    unique its repair multiset is the one that class actually required.

A disagreement is reported with the seed, the candidate that caused it and
both verdicts. It is never fixed by loosening the assertion: a checker
`unique` beside two solution classes is an identifiability bug, and a checker
ambiguity beside one solution class is a checker that refuses worlds the
environment can score.

What this file CANNOT reach, stated so the pass is not over-read: a generated
world is minted from the graph, so the public bytes and the scorer's contract
come from one derivation and cannot be pulled apart. Every seed here is
therefore a world the generator believes is unambiguous, and the equivalence
is exercised in one direction — unique, one class. The other direction, an
ambiguous world beside two readings, is only reachable by editing the public
text, which the scorer would then no longer be scoring; those cases live as
fixed fixtures in `test_identify.py`, where the two readings are named
instead of scored.

    python tests/test_identify_differential.py
"""

from __future__ import annotations

import asyncio
import collections
import json
import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate.normalise import Accepted, parse_once  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402

# The population and the text edits are the generator suite's, imported
# rather than re-written: a differential test that built its candidates from
# a second, subtly different notion of "the golden entry for this item" would
# be comparing its own bugs.
import test_generator as TG  # noqa: E402
from repair_keys import master_names, planted_key  # noqa: E402

BANK = "Assets:Bank:Checking"
# Eight standard worlds and two hard ones. The bound is wall clock: every
# candidate is a full rollout through the production loop.
SEEDS = [("train", i, "standard") for i in range(8)] + [("train", 0, "hard"), ("train", 2, "hard")]


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:60]:
            print(f"      {line}")
    return ok


def note(text):
    print(f"      · {text}")


# --------------------------------------------------------------------------
# one candidate, through the production loop
# --------------------------------------------------------------------------

def rollout(env, text: str) -> dict:
    """Workspace, write_ledger, env_response (commits), score_core (scores,
    renders, publishes). The delivered ledger is read back so two solutions
    can be compared on what the environment actually published."""
    state: dict = {}
    env._workspace(state)
    call = SimpleNamespace(id="call-1", name="write_ledger", arguments=json.dumps({"content": text}))
    asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))
    if state.get("piv_committed") is None:
        return {"committed": False, "complete": False, "total": None, "fingerprint": None}
    try:
        total = env_mod.score_core(state)
    except Exception as exc:                       # the adapter quarantines this: never a score
        return {"committed": True, "complete": False, "total": None, "fingerprint": None,
                "error": f"{type(exc).__name__}: {exc}"}
    delivery, result = state["piv_delivery"], state["piv_result"]
    out = {"committed": True, "total": Decimal(str(total)), "outcome": delivery.outcome,
           "renderable": delivery.renderable, "complete": bool(result and result.complete),
           "fingerprint": None}
    if delivery.renderable:
        delivered = (Path(state["workspace"]) / env_mod.LEDGER).read_text(encoding="utf-8")
        parsed = parse_once(delivered)
        out["fingerprint"] = parsed.semantic_fingerprint if isinstance(parsed, Accepted) else None
    return out


def is_solution(outcome: dict) -> bool:
    """The definition the specification names, and nothing looser: the month
    closed (COMPLETE) and the reward paid in full."""
    return bool(outcome.get("complete")) and outcome.get("total") == Decimal("1")


# --------------------------------------------------------------------------
# the bounded repair grammar
# --------------------------------------------------------------------------

def block_of(text: str, when: str, legs) -> tuple:
    """(lines, (start, stop)) for the one entry at `when` with these legs."""
    lines, records = TG.records(text)
    hits = [r for r in records if r[2] == when and r[3] == legs]
    return (lines, (hits[0][0], hits[0][1])) if len(hits) == 1 else (lines, None)


def apply_items(original: str, golden: str, items) -> str:
    """The original with exactly these planted items repaired."""
    text = original
    for item in items:
        text = TG.partial_repair(text, golden, item)
    return text


def recognition_dated(golden: str, item) -> str | None:
    """The repaired entry carried at the date the TRANSACTION happened rather
    than the date the bank shows.

    This is the wrong reading since contract change B, and it is the reading a
    careful bookkeeper is most likely to reach for: `## Dates` opens by saying
    an entry carries the transaction's own date. What it now goes on to say is
    that an item the books do not carry AT ALL has no such date in evidence,
    so the statement's date is the only one there is. Nothing public reveals
    the hidden recognition date, so this variant stands in for it with a date
    three days before the bank's — an ACH credited on the 22nd was authorised
    on the 19th — which is the shape of the gaps the generator actually draws.
    An altered or duplicated item's entry IS public and keeps its own date, so
    a two-day transposition stands in there instead: what the family is for is
    a defensible-looking date that is not the right one.
    """
    lines, span = block_of(golden, item.date, TG._legs(item.required))
    if span is None:
        return None
    when = (date.fromisoformat(item.date) + timedelta(days=-3 if item.kind == "omit" else 2)).isoformat()
    lines[span[0]] = when + lines[span[0]][10:]
    return "\n".join(lines) + "\n"


def reattributed(golden: str, item, allowed) -> str | None:
    """The repaired entry posted to a different account of the same class:
    the attribution the master files and the policy were supposed to fix."""
    lines, span = block_of(golden, item.date, TG._legs(item.required))
    if span is None:
        return None
    others = [a for a, _v in item.required if a != BANK]
    if len(others) != 1:
        return None
    was = others[0]
    swap = next((a for a in allowed
                 if a != was and a != BANK and a.split(":")[0] == was.split(":")[0]), None)
    if swap is None:
        return None
    for i in range(span[0] + 1, span[1]):
        if was in lines[i]:
            lines[i] = lines[i].replace(was, swap, 1)
            break
    else:
        return None
    return "\n".join(lines) + "\n"


def repayeed(golden: str, item, parties) -> str | None:
    """The repaired entry credited to a different counterparty."""
    lines, span = block_of(golden, item.date, TG._legs(item.required))
    if span is None or not item.must_be_payee:
        return None
    was = item.must_be_payee[0]
    swap = next((p for p in parties if p != was), None)
    if swap is None or f'"{was}"' not in lines[span[0]]:
        return None
    lines[span[0]] = lines[span[0]].replace(f'"{was}"', f'"{swap}"', 1)
    return "\n".join(lines) + "\n"


def adjusted(original: str, golden: str, item, rest) -> str | None:
    """An alteration corrected the other way a bookkeeper might: the wrong
    entry stays as booked and a second entry carries the difference. The
    balances land where the golden books land; the entries do not."""
    if item.kind != "alter" or not item.residual:
        return None
    text = apply_items(original, golden, rest)
    body = "".join(f"  {account:<40s} {value:>10} USD\n" for account, value in
                   sorted((a, f"{v:.2f}") for a, v in item.residual))
    return text.rstrip("\n") + "\n\n" + f'{item.date} * "{item.must_be_payee[0]}" "Correction of posted amount"\n{body}'


def other_copy_removed(original: str, golden: str, item, rest) -> str | None:
    """A doubled entry with the FIRST copy dropped rather than the second.

    The copies are identical, so this must land in the same solution class as
    the golden repair. It is the fixture that keeps the quotient honest: a
    comparison on delivered bytes rather than on semantics would call it a
    second answer and the equivalence would fail for a presentation reason.
    """
    if item.kind != "duplicate":
        return None
    text = apply_items(original, golden, rest)
    lines, records = TG.records(text)
    hits = [r for r in records if r[2] == item.date and r[3] == TG._legs(item.required)]
    if len(hits) != 2:
        return None
    start, stop = hits[0][0], hits[0][1]
    while stop < len(lines) and not lines[stop].strip():
        stop += 1
    return "\n".join(lines[:start] + lines[stop:]) + "\n"


def candidates(minted, verdict) -> list:
    """(label, text) for every reading the grammar admits around this world."""
    original, golden = minted.inputs.original_text, minted.inputs.golden_text
    planted = list(minted.inputs.planted)
    allowed = list(minted.inputs.allowed_accounts)
    parties = sorted({p for item in planted for p in item.must_be_payee}
                     | {r.counterparty for r in verdict.repairs if r.counterparty})
    out = [("golden", golden), ("original", original)]
    for item in planted:
        out.append((f"only:{item.kind}:{item.id}", apply_items(original, golden, [item])))
    for i in range(len(planted)):
        for j in range(i + 1, len(planted)):
            if len(planted) > 2:          # a pair IS the golden when only two were planted
                out.append((f"pair:{planted[i].id}+{planted[j].id}",
                            apply_items(original, golden, [planted[i], planted[j]])))
    # the wrong readings: same evidence, a different repair
    for item in planted:
        rest = [p for p in planted if p is not item]
        for label, text in (
            (f"recognition-dated:{item.id}", recognition_dated(golden, item)),
            (f"reaccounted:{item.id}", reattributed(golden, item, allowed)),
            (f"repayee:{item.id}", repayeed(golden, item, parties)),
            (f"adjusting-entry:{item.id}", adjusted(original, golden, item, rest)),
            (f"other-copy:{item.id}", other_copy_removed(original, golden, item, rest)),
        ):
            if text:
                out.append((label, text))
    return out


# --------------------------------------------------------------------------
# the property
# --------------------------------------------------------------------------

def selector(namespace, index, profile) -> str:
    return f"{namespace}:{index}" if profile == "standard" else f"{namespace}:{index}:{profile}"


WRONG_FAMILIES = ("recognition-dated", "reaccounted", "repayee", "adjusting-entry", "other-copy")


def test_checker_uniqueness_matches_the_scorer_solution_classes():
    problems, reported = [], []
    built = set()
    started = time.time()
    for namespace, index, profile in SEEDS:
        name = selector(namespace, index, profile)
        try:
            minted = TG.minted(namespace, index, profile)
            env = env_mod.load_environment(name)
        except Exception as exc:                    # a refused seed is not this test's subject
            note(f"{name}: skipped ({type(exc).__name__}: {exc})")
            continue
        public = {file_name: data.decode("utf-8") for file_name, data in minted.inputs.public_files}
        verdict = ID.check_identifiable(public, bank_account=minted.world.bank_account,
                                        period_start=minted.task.period.start,
                                        period_end=minted.task.period.end)

        classes: dict = {}
        enumerated = candidates(minted, verdict)
        built |= {label.split(":")[0] for label, _text in enumerated}
        for label, text in enumerated:
            outcome = rollout(env, text)
            if not is_solution(outcome):
                continue
            classes.setdefault(outcome["fingerprint"], []).append(label)
        one_class = len(classes) == 1

        if verdict.unique != one_class:
            problems.append(
                f"{name}: the checker says {'unique' if verdict.unique else 'AMBIGUOUS'} and the scorer admits "
                f"{len(classes)} complete solution class(es)")
            problems.append(f"          checker: {verdict.reason[:300]}")
            for fingerprint, labels in classes.items():
                problems.append(f"          class {str(fingerprint)[:16]}: {', '.join(labels)}")
            continue
        if not classes:
            problems.append(f"{name}: no enumerated candidate closed the month, so the grammar does not "
                            f"contain the answer and the comparison is vacuous")
            continue
        if "golden" not in next(iter(classes.values())):
            problems.append(f"{name}: the one solution class is {next(iter(classes.values()))}, which does not "
                            f"contain the golden repair")
        if verdict.unique:
            # The full shared repair key (Codex T42 §3), the same projection
            # the sweep and the generator's property 7 use.
            names = master_names(public)
            want = collections.Counter(planted_key(p, names, bank_account=BANK) for p in minted.inputs.planted)
            got = collections.Counter(ID.repair_key(r) for r in verdict.repairs)
            if want != got:
                problems.append(f"{name}: the class the scorer accepts needs "
                                f"{sorted(str(k) for k in (want - got))} and the checker reported "
                                f"{sorted(str(k) for k in (got - want))}")
        reported.append(f"{name}: {len(classes)} class, {sum(len(v) for v in classes.values())} of "
                        f"{len(enumerated)} candidates complete")
    missing = [family for family in WRONG_FAMILIES if family not in built]
    if missing:
        problems.append(f"the grammar built no {missing} candidate anywhere in the population; the "
                        f"equivalence would hold for the empty reason")
    for line in reported:
        note(line)
    note(f"{time.time() - started:.1f}s")
    return check("checker unique <=> the real scorer admits exactly one complete semantic solution class, and "
                 "the checker's repairs are that class's repairs (8 standard + 2 hard worlds, bounded repair "
                 "grammar)", not problems, "\n".join(problems))


def test_a_wrong_reading_is_not_a_solution():
    """The grammar has to contain readings the scorer REFUSES.

    If every enumerated candidate closed the month, the equivalence above
    would hold for the empty reason: a repair language in which nothing can
    be wrong proves nothing about a checker that says the right repair is
    forced. So one seed is examined in detail — the re-dated, re-accounted,
    re-attributed and partial candidates must all fail to close.
    """
    minted = TG.minted("train", 0)
    env = env_mod.load_environment("train:0")
    public = {name: data.decode("utf-8") for name, data in minted.inputs.public_files}
    verdict = ID.check_identifiable(public, bank_account=minted.world.bank_account,
                                    period_start=minted.task.period.start, period_end=minted.task.period.end)
    refused, admitted = [], []
    for label, text in candidates(minted, verdict):
        if label in ("golden",) or label.startswith("other-copy"):
            continue
        outcome = rollout(env, text)
        (admitted if is_solution(outcome) else refused).append(label)
    note(f"train:0 refused {len(refused)}: {', '.join(refused)}")
    return check("every enumerated reading other than the golden repair (and the copy that is the same books) "
                 "fails to close the month", not admitted, f"admitted as complete solutions: {admitted}")


TESTS = [
    test_a_wrong_reading_is_not_a_solution,
    test_checker_uniqueness_matches_the_scorer_solution_classes,
]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
