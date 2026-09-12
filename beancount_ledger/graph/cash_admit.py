"""The admission gate the CONSTRUCTION PATH runs, not the one a suite runs
afterwards.

Round 16, decision 3 lists the conditions every candidate pair must satisfy,
and two of them are about artifacts the construction produces rather than
about the recipe that produced them:

    Independent correctness: private derivation equals the public fold;
    every planted repair matches the independent public reading; BOTH GOLDEN
    ARTIFACTS SCORE COMPLETE THROUGH THE ACTUAL ENGINES.

A check that lives only in a test file is a property of the draws that test
file happens to take. `tests/test_cash_construction.py` draws one secret at
one company-month index, so its PASS said something about thirty variants and
nothing about the path. This module is the same checks placed where they
decide admission: `cash_construct._render` calls all three of the entry
points below on every rendered variant of every attempt, and an attempt that
fails one is never returned.

THE THREE ENTRY POINTS, AND WHY THEY ARE THREE AND NOT ONE. Decision 3 also
draws a line through the middle of "this candidate failed":

    Expected construction failures may be retried. Unexpected exceptions,
    disagreement between supposedly independent derivations, or a VALID
    GOLDEN FAILING ITS SCORER are defects to investigate — not opportunities
    to keep drawing until the defect disappears.

So the construction path has to be able to say which it is, and saying it
needs the two cases to be separable BEFORE the scorer runs:

  * `posting_collision_problems` is the MERGED trap, computed at
    construction. `candidate/1` labels a submitted transaction merged when
    its posting multiset shares an (account, amount) pair with two or more
    planted shapes, and that predicate does not ask whether the entry is a
    legitimate pre-existing one. Two receipts drawn at the same amount give
    their two plants the same two postings; a credit note whose gross lands
    on a receipt's amount gives a pre-existing entry a leg each plant also
    carries. Either way the month is unreadable through the scorer, and the
    draw — not the scorer, and not the golden — is what is wrong. It is a
    DECLARED acceptance condition with an accounting reason (two evidenced
    events a reader cannot tell apart), so a draw that trips it is an
    expected construction failure and the next attempt is drawn.
  * `golden_score_problems` scores both goldens through the actual
    `candidate/1`, `application/1` and `composite/1`. It runs AFTER the
    collision guard, so a golden that fails here is a golden the
    construction's own declared conditions say should have scored: decision
    3's "valid golden failing its scorer", which `cash_construct` raises as a
    ConstructionDefect rather than redrawing past.
  * `world_checker_problems` runs every remaining gate a hand-authored world
    must pass, through the shipped `tests/world_checks.check_derived` — the
    same battery, over the inputs `derive_contract` already produced, so the
    generated population is held to the standard the authored eleven are
    held to rather than to a private copy of it that could drift from it.

WHY THE CHECKER IS IMPORTED AND NOT REIMPLEMENTED. `tests/world_checks.py` is
the one implementation of those gates; a second one here would be a second
thing to keep in step, and the failure it would eventually have is precisely
the one this repair exists to close. It lives under `tests/` because that is
where the authored-world gate was written, and the wheel deliberately ships
no tests, so `world_checker_problems` FAILS CLOSED: if the battery cannot be
located it raises `AdmissionUnavailable` and the construction path turns that
into a defect. A pair that could not be checked is not a pair that passed.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

ONE = Decimal("1")

#: The offence channels `candidate/1` reports. A golden that trips any of
#: them is not a close a reader could deliver, whatever its total says.
OFFENCE_CHANNELS = ("merged_events", "fabricated", "removed_or_altered", "collateral_damage")


class AdmissionUnavailable(RuntimeError):
    """The admission battery could not be located, so nothing can be
    admitted. Never a pass: a candidate nobody checked is not a candidate
    that passed."""


# --------------------------------------------------------------------------
# the merged trap, at construction
# --------------------------------------------------------------------------

def _shapes(inputs) -> dict:
    """Every planted item's required posting multiset, as the set of
    (account, canonical amount) pairs `score_committed` intersects.

    Built with the scorer's OWN expressions — `committed._txn_shape` and
    `canonical.canonical_decimal` — rather than a re-spelling of them, so
    this measures the real predicate.
    """
    from ..candidate.canonical import canonical_decimal
    return {p.id: frozenset((account, canonical_decimal(Decimal(value))) for account, value in p.required)
            for p in inputs.planted}


def posting_collision_problems(inputs) -> list:
    """The ways this draw walks into `candidate/1`'s MERGED predicate.

    Three readings of one predicate: two planted shapes that intersect at
    all (the repair for one is then a merged entry), a pre-existing entry of
    the opening ledger that shares a pair with two plants (an entry the agent
    never touched is labelled merged and blocks the deliverable), and the
    same over the expected ledger the golden delivers.

    Every message names the postings, so the census records WHY a draw was
    refused rather than that it was.
    """
    from ..candidate.committed import _txn_shape
    from ..candidate.normalise import Accepted, parse_once
    from ..candidate.schema import ParsedTransaction

    problems: list = []
    shapes = _shapes(inputs)
    ordered = sorted(shapes)
    for index, first in enumerate(ordered):
        for second in ordered[index + 1:]:
            overlap = sorted(shapes[first] & shapes[second])
            if overlap:
                problems.append(
                    f"the planted items {first} and {second} share the posting(s) {overlap}: two evidenced "
                    f"events a reader cannot tell apart, and the scorer would label the repair for one of "
                    f"them a merged entry")
    if problems:
        return problems
    for label, text in (("opening", inputs.original_text), ("expected", inputs.golden_text)):
        parsed = parse_once(text)
        if not isinstance(parsed, Accepted):
            problems.append(f"the {label} ledger does not parse at the boundary: {parsed}")
            continue
        for txn in (d for d in parsed.submission.directives if isinstance(d, ParsedTransaction)):
            shape = frozenset(_txn_shape(txn))
            hit = sorted(name for name, planted in shapes.items() if planted & shape)
            if len(hit) >= 2:
                problems.append(
                    f"the {label} ledger's entry {txn.date} {txn.narration!r} shares a posting with the "
                    f"planted items {hit}: the scorer would label it a merged entry and block the deliverable")
    return problems


# --------------------------------------------------------------------------
# both goldens, through the actual engines
# --------------------------------------------------------------------------

def score_ledger(text: str, env):
    """One ledger scored exactly as the production door scores it:
    `parse_once(logical_text(raw))`, `commit(...)`, `score_committed(...)`.
    Returns `(outcome, problem)`; exactly one of the two is None.

    The environment module is imported HERE rather than at module scope: it
    sits above `graph/` in the stack and imports from it, so reading its
    definitions at call time keeps the layering one-way.
    """
    from ..beancount_ledger import digests_of, logical_text
    from ..candidate import committed as K
    from ..candidate.normalise import Accepted, parse_once

    raw = text.encode("utf-8")
    parsed = parse_once(logical_text(raw))
    if not isinstance(parsed, Accepted):
        return None, f"the parse boundary refused it ({type(parsed).__name__}): {parsed}"
    if not parsed.domain_valid:
        return None, f"domain findings at the boundary: {parsed.finding_summary.codes}"
    receipt = K.new_receipt("construction", 1, digests_of(raw, submitted=text))
    try:
        return K.score_committed(K.commit(parsed, env, receipt)), None
    except Exception as exc:                       # a scorer refusal is a finding, not a crash of the gate
        return None, f"scoring raised {type(exc).__name__}: {exc}"


def golden_score_problems(inputs, golden_register: str) -> list:
    """Decision 3's "both golden artifacts score complete through the actual
    engines", as an admission condition of the construction path.

    The golden ledger goes through `candidate/1` and must pay exactly 1,
    close completely, resolve every planted item and trip no offence
    channel; the golden register goes through `application/1` and must parse,
    pay exactly 1 and carry no penalty; `composite/1` multiplies them and
    must be 1 and complete.
    """
    from ..candidate import application as APP
    from ..candidate import committed as K
    from ..candidate import composite as X

    problems: list = []
    try:
        env = K.load_contract(inputs)
    except Exception as exc:
        return [f"load_contract refused the derived inputs: {type(exc).__name__}: {exc}"]

    ledger, failure = score_ledger(inputs.golden_text, env)
    if failure:
        return [f"the golden ledger: {failure}"]
    if ledger.total != ONE:
        problems.append(f"the golden ledger scores {ledger.total}, not 1; "
                        f"components={dict(ledger.components)} "
                        f"unresolved={list(ledger.unresolved_planted)} misses={list(ledger.target_misses)}")
    if not ledger.complete:
        problems.append(f"the golden ledger is not a complete close: renderable={ledger.renderable} "
                        f"blocked_by={list(ledger.blocked_by)} undocumented={list(ledger.undocumented)}")
    for channel in OFFENCE_CHANNELS:
        values = list(getattr(ledger, channel))
        if values:
            problems.append(f"the golden ledger trips {channel}: {values}")
    states = dict(ledger.allocation.item_states)
    if set(states) != {p.id for p in inputs.planted} or any(str(s) != "RESOLVED" for s in states.values()):
        problems.append(f"the golden ledger does not resolve every planted item: "
                        f"{ {i: str(s) for i, s in states.items()} }")

    parsed = APP.parse_application(golden_register, inputs.application)
    if not isinstance(parsed, APP.ParsedApplication):
        return problems + [f"the golden register is refused at the parse boundary: {parsed}"]
    outcome = APP.score_application(parsed, inputs.application, expected_balances=env.expected_balances)
    if outcome.total != ONE or outcome.penalties:
        problems.append(f"the golden register scores {outcome.total} with penalties {list(outcome.penalties)}")
    composite = X.compose(ledger, outcome)
    if composite.total != ONE or not composite.complete:
        problems.append(f"the composite of the two goldens is {composite.total}, complete={composite.complete}")
    return problems


# --------------------------------------------------------------------------
# every other gate an authored world must pass
# --------------------------------------------------------------------------

def _world_checks():
    """The shipped gate battery, or `AdmissionUnavailable`.

    Already imported by every suite that uses it, so the common case is a
    `sys.modules` hit; otherwise it is loaded from the repository checkout
    this package sits in, by path, and registered under its own name so the
    suites and the construction path share one module object.
    """
    module = sys.modules.get("world_checks")
    if module is not None:
        return module
    path = Path(__file__).resolve().parents[2] / "tests" / "world_checks.py"
    if not path.is_file():
        raise AdmissionUnavailable(
            f"the admission battery is not at {path}; construction may not admit a pair it cannot check")
    spec = importlib.util.spec_from_file_location("world_checks", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["world_checks"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        del sys.modules["world_checks"]
        raise AdmissionUnavailable(f"the admission battery at {path} did not load: "
                                   f"{type(exc).__name__}: {exc}") from exc
    return module


def world_checker_problems(world, task, bundle, inputs) -> list:
    """Every gate a hand-authored world/task pair must pass, run over the
    contract `derive_contract` already minted for this variant.

    `check_derived` rather than `check_world_task`: the latter derives the
    contract again, and one derivation per rendered variant is enough — the
    construction path holds the bundle and the inputs the gates are about.
    The two pre-derivation checks `check_world_task` runs first are package
    code, so they are run here directly.
    """
    from .policy import required_sections
    from .schema import check_world

    where = f"{world.id}/{task.id}"
    problems = [f"{where}: schema.check_world: {problem}" for problem in check_world(world)]
    required = required_sections(world)
    for section in sorted(set(required.values())):
        if section not in world.policy_text:
            rules = ", ".join(sorted(role for role, cited in required.items() if cited == section))
            problems.append(f"{where}: policy text lacks the heading {section!r}, cited by the {rules} rule(s)")
    if problems:
        return problems
    found, _warnings = _world_checks().check_derived(world, task, bundle, inputs)
    return list(found)


__all__ = [
    "AdmissionUnavailable", "OFFENCE_CHANNELS",
    "posting_collision_problems", "score_ledger", "golden_score_problems", "world_checker_problems",
]
