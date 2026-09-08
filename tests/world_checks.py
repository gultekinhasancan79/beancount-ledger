"""What a hand-authored world/task pair must satisfy before it is registered.

`beancount_ledger/graph/worlds/` is the one place a human writes economic
facts by hand. Everything else about a task is derived, so the failure modes
of an authored world are not "the code is wrong" but "the facts do not
support the task the plan asks for": a planted item nothing public evidences,
a golden the scorer does not pay 1.0 for, an original the checker cannot read
uniquely, a party name the generator also draws, a derived balance typed into
the source as a literal.

The generated worlds have a gate for all of that —
`mint._require_public_uniqueness` runs the public-only checker and compares
the shared repair key before a world is allowed to exist. Hand-authored
worlds had no equivalent: `test_graph` proves the properties for Alpine
specifically, by name, against literals. This module is that gate, made
reusable, so a new world can be checked one at a time while it is being
written (`tests/verify_world.py`) and the whole registry is guarded
afterwards (`tests/test_worlds.py`).

    from world_checks import check_world_task, summarize
    problems, warnings = check_world_task(world, task, source_path=...)

A task that plants NOTHING (an empty `MutationPlan`) is checked under the
mirror-image contract, not exempted from it: branch (d) below then requires
the untouched original to score exactly 1.0, close complete, trip no offence
channel and carry no item state, and requires the opening ledger to be the
expected ledger. That is what the clean-month assurance pack is sold on, and
it is also what would catch a k>0 task whose planting had silently stopped
working.

`problems` are gates: a non-empty list means the world must not be
registered. `warnings` are the generator's *heuristics* for a world that
reads unambiguously to a human (a printed amount that occurs once, movements
of one party spread apart); they are prefixed "WARN:" and are advisory,
because the hand-authored layer is allowed to be deliberately harder than the
generator's draw as long as the identifiability GATE still passes.
"""

from __future__ import annotations

import csv
import io
import re
import sys
from datetime import date as _date
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for _p in (str(ROOT), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate.canonical import canonical_decimal  # noqa: E402
from beancount_ledger.candidate.normalise import Accepted, parse_once  # noqa: E402
from beancount_ledger.candidate.schema import ParsedTransaction  # noqa: E402
from beancount_ledger.graph import content as C  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402
from beancount_ledger.graph import project as PJ  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.policy import POLICY_SECTIONS, movement_of  # noqa: E402
from beancount_ledger.graph.schema import check_world  # noqa: E402

from repair_keys import master_names, planted_key  # noqa: E402  (tests/repair_keys.py)

__all__ = ["check_world_task", "summarize", "score_text", "decoded_public",
           "generator_name_pools", "PRIVATE_ID"]

# The same shape `test_graph.PRIVATE_ID` scans for, plus `mut:` (the
# projector's provenance prefix for an altered entry's observation).
PRIVATE_ID = re.compile(r"(rec|mov|event|party|doc|mut):[a-z0-9][a-z0-9-]*")

LEDGER_FILE = PJ.LEDGER_VIEW
STATEMENT_FILE = PJ.STATEMENT_VIEW
ARCHIVE_FILE = PJ.ARCHIVE_VIEW

# `RESERVED_NAMES` is not a draw pool: it is the generator's EXCLUSION list,
# and it holds the names the original Alpine world uses
# (`generate.py:293,296,318` reject a draw that lands in it). Scanning a
# hand-authored world against it would flag the world for using its own
# names, so it is the one uppercase global in `content.py` that is skipped.
_NOT_A_POOL = ("RESERVED_NAMES",)

# A generated party name is one stem plus one suffix, so a hand-authored name
# that composes the same way is reachable by some seed even though the whole
# string appears in no pool.
_STEM_POOLS = ("GEOGRAPHIC_STEMS", "INDUSTRIAL_STEMS", "PERSONAL_STEMS", "COMPANY_STEMS", "BANK_STEMS")
_SUFFIX_POOLS = ("TRADE_SUFFIXES", "PERSONAL_SUFFIXES", "COMPANY_SUFFIXES", "BANK_SUFFIXES")


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def decoded_public(inputs) -> dict:
    """`inputs.public_files` — a tuple of (name, bytes) — as name -> text."""
    return {name: data.decode("utf-8") for name, data in inputs.public_files}


def _money(value) -> str:
    return f"{Decimal(value):.2f}"


def _pairs(shape) -> frozenset:
    """A posting shape as a set of (account, canonical amount) pairs — the
    exact element type `score_committed` intersects when it labels a merged
    entry (`shapes = [set(item.required) for item in planted]`)."""
    return frozenset((account, canonical_decimal(Decimal(value))) for account, value in shape)


def _days(a: str, b: str) -> int:
    return abs((_date.fromisoformat(a) - _date.fromisoformat(b)).days)


def _label(txn: ParsedTransaction) -> str:
    return f'{txn.date} "{txn.payee or ""}" "{txn.narration}"'


def score_text(text: str, env, label: str):
    """Score one submitted ledger exactly as the production door does:
    `parse_once(logical_text(raw))`, `commit(...)`, `score_committed(...)`.
    Returns (outcome, problem); exactly one of the two is None."""
    raw = text.encode("utf-8")
    parsed = parse_once(env_mod.logical_text(raw))
    if not isinstance(parsed, Accepted):
        return None, f"{label}: the parse boundary refused it ({type(parsed).__name__}): {parsed}"
    if not parsed.domain_valid:
        return None, f"{label}: domain findings at the boundary: {parsed.finding_summary.codes}"
    receipt = K.new_receipt("check", 1, env_mod.digests_of(raw, submitted=text))
    try:
        committed = K.commit(parsed, env, receipt)
        return K.score_committed(committed), None
    except Exception as exc:              # a scorer refusal is a finding, not a crash of the checker
        return None, f"{label}: scoring raised {type(exc).__name__}: {exc}"


def generator_name_pools() -> dict:
    """Every uppercase global of `graph/content.py` that is a tuple, list or
    dict of strings, flattened to pool name -> frozenset of strings."""
    pools: dict = {}
    for name, value in sorted(vars(C).items()):
        if not name.isupper() or name in _NOT_A_POOL:
            continue
        if isinstance(value, dict):
            values = [v for group in value.values()
                      for v in (group if isinstance(group, (tuple, list, set, frozenset)) else [group])]
        elif isinstance(value, (tuple, list, set, frozenset)):
            values = list(value)
        else:
            continue
        strings = frozenset(v for v in values if isinstance(v, str))
        if strings:
            pools[name] = strings
    return pools


def _statement_amounts(text: str) -> list:
    """Every absolute figure the debit and credit columns print. The balance
    column is a running total, not a printed movement, and the opening row
    carries neither debit nor credit."""
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        for column in ("debit", "credit"):
            raw = (row.get(column) or "").strip()
            if raw:
                out.append(abs(Decimal(raw)))
    return out


# --------------------------------------------------------------------------
# the checks
# --------------------------------------------------------------------------

def check_world_task(world, task, source_path=None):
    """Every gate a hand-authored (world, task) pair must pass.

    Returns `(problems, warnings)`: two lists of strings, each message naming
    the world and the task. An empty `problems` list is the only acceptable
    answer; `warnings` are advisory heuristics.

    `source_path` is the world module's .py file. When given, the
    derived-literal scan (h) runs; without it that one check is skipped.
    """
    problems: list = []
    warnings: list = []
    where = f"{world.id}/{task.id}"

    # (a) the world graph itself: referential integrity, canonical strings.
    for problem in check_world(world):
        problems.append(f"{where}: schema.check_world: {problem}")

    # (j) the policy document the agent reads must carry every heading the
    # accounting rules cite. `project()` enforces this too, but as a
    # ProjectionError inside derive_contract; saying it here names the
    # missing heading and the rule that wanted it.
    for section in sorted(set(POLICY_SECTIONS.values())):
        if section not in world.policy_text:
            rules = ", ".join(sorted(r for r, s in POLICY_SECTIONS.items() if s == section))
            problems.append(f"{where}: policy text lacks the heading {section!r}, cited by the {rules} rule(s)")

    if problems:
        problems.append(f"{where}: the world does not project; the derivation-dependent checks did not run")
        return problems, warnings

    # (b) derivation, the contract door, and the observation envelope.
    try:
        bundle, inputs = derive_contract(world, task)
    except Exception as exc:
        problems.append(f"{where}: derive_contract failed: {type(exc).__name__}: {exc}")
        return problems, warnings
    try:
        env = K.load_contract(inputs)
    except Exception as exc:
        problems.append(f"{where}: load_contract refused the derived inputs: {type(exc).__name__}: {exc}")
        return problems, warnings

    public = decoded_public(inputs)
    files = dict(inputs.public_files)
    if LEDGER_FILE not in files:
        problems.append(f"{where}: the public files carry no {LEDGER_FILE}")
    else:
        breach = env_mod.ledger_envelope_breach(files[LEDGER_FILE])
        if breach is not None:
            problems.append(f"{where}: {LEDGER_FILE} is outside the observation envelope: {breach}")

    # (c) the golden deliverable is worth exactly 1.0 and is a complete close.
    golden, failure = score_text(inputs.golden_text, env, f"{where}: golden")
    if failure:
        problems.append(failure)
    else:
        if golden.total != Decimal("1"):
            problems.append(f"{where}: the golden scores {golden.total}, not 1; "
                            f"components={dict(golden.components)} "
                            f"unresolved={list(golden.unresolved_planted)} misses={list(golden.target_misses)}")
        if not golden.complete:
            problems.append(f"{where}: the golden is not a complete close: renderable={golden.renderable} "
                            f"blocked_by={list(golden.blocked_by)} undocumented={list(golden.undocumented)}")
        for channel in ("merged_events", "fabricated", "removed_or_altered", "collateral_damage"):
            values = list(getattr(golden, channel))
            if values:
                problems.append(f"{where}: the golden trips {channel}: {values}")
        states = dict(golden.allocation.item_states)
        wrong = {i: str(s) for i, s in states.items() if str(s) != "RESOLVED"}
        if wrong or set(states) != {p.id for p in inputs.planted}:
            problems.append(f"{where}: the golden does not resolve every planted item: "
                            f"{ {i: str(s) for i, s in states.items()} }")

    # (d) the untouched original, under whichever of the two contracts the
    # task declares by its planted set.
    #
    # A task with planted items owes the ordinary guarantee: the original is
    # not already the answer, and it is not itself an offence — an author who
    # plants nothing the scorer can see, or who ships an original the scorer
    # reads as tampered, finds out here.
    #
    # A task with an EMPTY planted set (k=0) is the exact opposite claim, and
    # it has to be checked rather than exempted. The assurance pack asks
    # whether an agent damages books that already reconcile, so its clean
    # months assert that the opening ledger IS the deliverable: the untouched
    # original scores exactly 1.0, closes completely, trips no offence
    # channel, and carries no item state at all. Read the other way, this is
    # what stops a "clean" task from being a task whose planting silently
    # stopped working — the same failure branch (d) catches for k>0, stated
    # for k=0. It also pins the structural claim the pack is sold on: with
    # nothing planted the projector must emit the opening ledger and the
    # expected ledger as one text, so "submit it unchanged" and "submit the
    # golden" are the same deliverable rather than two that happen to score
    # alike.
    original, failure = score_text(inputs.original_text, env, f"{where}: original")
    if failure:
        problems.append(failure)
    elif not inputs.planted:
        if inputs.original_text != inputs.golden_text:
            problems.append(f"{where}: nothing is planted, yet the opening ledger and the expected ledger differ; "
                            f"a clean month's deliverable must be the ledger as it stands")
        if original.total != Decimal("1"):
            problems.append(f"{where}: nothing is planted, so the untouched original must score exactly 1, not "
                            f"{original.total}; components={dict(original.components)} "
                            f"misses={list(original.target_misses)}")
        if not original.complete:
            problems.append(f"{where}: nothing is planted, so the untouched original must be a complete close: "
                            f"renderable={original.renderable} blocked_by={list(original.blocked_by)} "
                            f"undocumented={list(original.undocumented)}")
        for channel in ("fabricated", "merged_events", "removed_or_altered", "plug_accounts", "collateral_damage"):
            values = list(getattr(original, channel))
            if values:
                problems.append(f"{where}: the untouched original of a clean month trips {channel}: {values}")
        states = dict(original.allocation.item_states)
        if states:
            problems.append(f"{where}: nothing is planted, yet the untouched original carries the item states "
                            f"{ {i: str(s) for i, s in states.items()} }")
    else:
        if original.total >= Decimal("1"):
            problems.append(f"{where}: the untouched original already scores {original.total}; nothing was planted")
        for channel in ("fabricated", "merged_events", "removed_or_altered", "plug_accounts"):
            values = list(getattr(original, channel))
            if values:
                problems.append(f"{where}: the untouched original trips {channel}: {values} — the opening ledger "
                                f"is not a clean starting point")
        states = dict(original.allocation.item_states)
        resolved = sorted(i for i, s in states.items() if str(s) == "RESOLVED")
        if resolved:
            problems.append(f"{where}: the untouched original already RESOLVES {resolved}; those items are not "
                            f"planted discrepancies")
        if set(states) != {p.id for p in inputs.planted}:
            problems.append(f"{where}: the original's item states {sorted(states)} are not the planted items "
                            f"{sorted(p.id for p in inputs.planted)}")

    # (e) the MERGED trap. `score_committed` labels a submitted transaction
    # MERGED when its posting multiset shares at least one (account, amount)
    # pair with two or more planted shapes:
    #
    #     shapes    = [set(item.required) for item in planted]
    #     merged_at = {i for i, t in enumerate(txns)
    #                  if sum(1 for s in shapes if s & set(_txn_shape(t))) >= 2}
    #
    # That predicate does not ask whether the entry is a legitimate
    # pre-existing one, so an ORIGINAL transaction that happens to share one
    # leg with two planted shapes is labelled merged, blocks the deliverable
    # (BLOCKED_UNEXPLAINED) and caps the reward — for an agent that touched
    # nothing. It is a scorer gap, not an author's mistake, so the authored
    # layer must stay out of its way. Two planted shapes that intersect at
    # all are the same trap one step earlier: the repair for one item then
    # shares a pair with the other item's shape.
    #
    # The original's transactions are read at the parse boundary
    # (`parse_once(original_text).submission.directives`, filtered to
    # `ParsedTransaction`) and shaped with `committed._txn_shape` — the same
    # two expressions `score_committed` uses, so this measures the real
    # predicate rather than a re-implementation of it.
    shapes = {p.id: _pairs(p.required) for p in inputs.planted}
    ordered = sorted(shapes)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            overlap = sorted(shapes[a] & shapes[b])
            if overlap:
                problems.append(f"{where}: planted items {a} and {b} share the posting(s) {overlap}; the scorer "
                                f"would label the repair for one of them a merged entry")
    parsed_original = parse_once(inputs.original_text)
    if not isinstance(parsed_original, Accepted):
        problems.append(f"{where}: the original ledger does not parse: {parsed_original}")
    else:
        for txn in (d for d in parsed_original.submission.directives if isinstance(d, ParsedTransaction)):
            shape = frozenset(K._txn_shape(txn))
            hit = sorted(i for i, s in shapes.items() if s & shape)
            if len(hit) >= 2:
                problems.append(f"{where}: the pre-existing entry {_label(txn)} shares a posting with the planted "
                                f"items {hit}; the scorer would label it a merged entry and block the deliverable")

    # (f) identifiability, exactly the gate `mint._require_public_uniqueness`
    # applies to a generated world: the public-only checker must find one
    # reading, and that reading must be the planted one under the shared
    # repair key (truth side `derive.planted_key`, checker side
    # `identify.repair_key`, two independent projections).
    verdict = None
    try:
        verdict = ID.check_identifiable(public, bank_account=world.bank_account,
                                        period_start=task.period.start, period_end=task.period.end)
    except Exception as exc:
        problems.append(f"{where}: check_identifiable raised {type(exc).__name__}: {exc}")
    if verdict is not None:
        names = master_names(public)
        want = sorted(planted_key(p, names, bank_account=world.bank_account) for p in inputs.planted)
        got = sorted(ID.repair_key(r) for r in verdict.repairs)
        status = "unique" if verdict.unique else f"AMBIGUOUS ({verdict.readings} readings)"
        if not verdict.unique:
            problems.append(f"{where}: the public evidence is {status}, not one reading — {verdict.reason[:400]}"
                            + (f"; unexplained/ambiguous rows: {list(verdict.ambiguities)[:4]}"
                               if verdict.ambiguities else ""))
        if want != got:
            problems.append(f"{where}: the public reading is not the planted one (status {status}, matched "
                            f"{verdict.matched}, {len(verdict.repairs)} repairs)\n"
                            f"    planted: {want}\n    read:    {got}")
        elif verdict.ambiguities:
            warnings.append(f"WARN: {where}: the checker reports unexplained rows even though the reading is the "
                            f"planted one: {list(verdict.ambiguities)[:4]}")

    # (g) no private id in any public byte. The graph's node ids are the
    # evaluator's vocabulary; a leaked one hands the agent the join it is
    # meant to reconstruct.
    for name in sorted(public):
        for hit in sorted({m.group(0) for m in PRIVATE_ID.finditer(public[name])}):
            problems.append(f"{where}: {name} carries the private id {hit}")

    # (h) no derived number typed into the authored source. The authored
    # layer states facts; a closing balance, the statement's own close and
    # the opening bank balance are consequences of them. A literal that
    # matches one is either a coincidence or a second authority that will
    # silently stop agreeing with the projector.
    if source_path is not None:
        src = Path(source_path).read_text(encoding="utf-8")
        derived: dict = {}
        for account, value in inputs.expected_balances:
            if value != 0:
                derived.setdefault(abs(Decimal(value)), []).append(f"the expected balance of {account}")
        derived.setdefault(abs(Decimal(inputs.statement_closing)), []).append("the statement closing balance")
        derived.setdefault(abs(Decimal(bundle.opening_bank_balance)), []).append("the derived opening bank balance")
        authored = set()
        for event in world.events:
            for attr in ("amount", "net", "cost"):
                value = getattr(event, attr, None)
                if isinstance(value, Decimal):
                    authored.add(abs(value))
        authored |= {abs(v) for _, v in world.opening.carried}
        authored.add(abs(world.bank_opening.balance))
        authored |= {abs(d.gross) for d in world.documents if d.gross is not None}
        scan = {value: what for value, what in derived.items() if value not in authored}
        if not scan:
            problems.append(f"{where}: the derived-literal scan is vacuous — every derived number is also an "
                            f"authored amount, so it would pass whatever the source said")
        for value in sorted(scan):
            what = ", ".join(sorted(set(scan[value])))
            two_places = _money(value)
            if two_places in src:
                problems.append(f"{where}: {what} ({two_places}) appears as a literal in {Path(source_path).name}")
            elif value == value.to_integral_value():
                plain = str(int(value))
                if re.search(rf"(?<![\d.]){re.escape(plain)}(?![\d.])", src):
                    problems.append(f"{where}: {what} ({two_places}) appears as the literal {plain} in "
                                    f"{Path(source_path).name}")

    # (i) name pools. A hand-authored world that reuses a generated name
    # makes the two populations indistinguishable by name, which is the one
    # thing `RESERVED_NAMES` exists to prevent in the other direction.
    pools = generator_name_pools()
    folded: dict = {}
    for pool, values in pools.items():
        for value in values:
            folded.setdefault(value.casefold(), set()).add(pool)
    stems = {s.casefold(): p for p in _STEM_POOLS for s in pools.get(p, ())}
    suffixes = {s.casefold(): p for p in _SUFFIX_POOLS for s in pools.get(p, ())}
    subjects = [("the world title", world.title)] + [(f"party {p.id}", p.name) for p in world.parties]
    for what, name in subjects:
        key = name.casefold()
        if key in folded:
            problems.append(f"{where}: {what} {name!r} is a string the generator draws from {sorted(folded[key])}")
            continue
        words = name.split()
        for cut in range(1, len(words)):
            stem, suffix = " ".join(words[:cut]).casefold(), " ".join(words[cut:]).casefold()
            if stem in stems and suffix in suffixes:
                problems.append(f"{where}: {what} {name!r} composes the generator's {stems[stem]} stem "
                                f"{' '.join(words[:cut])!r} with the {suffixes[suffix]} suffix "
                                f"{' '.join(words[cut:])!r}; some seed draws this exact name")
                break

    # (k) the generator's readability heuristics, as WARNINGS. `generate._plan`
    # only ever plants on an event whose figure is printed once across the
    # archive and the task statement, and whose party has no other movement
    # within three days; a hand-authored world that breaks either is harder
    # to read than any generated one, which may well be deliberate.
    printed: dict = {}
    for name in (STATEMENT_FILE, ARCHIVE_FILE):
        for value in _statement_amounts(public.get(name, "")):
            printed.setdefault(value, []).append(name)
    for value in sorted(v for v, seen in printed.items() if len(seen) > 1):
        warnings.append(f"WARN: {where}: the figure {_money(value)} is printed {len(printed[value])} times across "
                        f"{sorted(set(printed[value]))}; a discrepancy of that size is not pinnable to one row by "
                        f"its amount alone")
    window_start, window_end = bundle.prior.start, task.period.end
    movements = []
    for event in world.events:
        movement = movement_of(world, event)
        if movement is not None and window_start <= movement.cleared_on <= window_end:
            movements.append((event, movement))
    for i, (event_a, mov_a) in enumerate(movements):
        for event_b, mov_b in movements[i + 1:]:
            party = getattr(event_a, "party_id", None)
            if party is None or party != getattr(event_b, "party_id", None):
                continue
            gaps = (_days(event_a.date, event_b.date), _days(event_b.date, mov_a.cleared_on),
                    _days(mov_a.cleared_on, mov_b.cleared_on))
            if min(gaps) <= 3:
                warnings.append(f"WARN: {where}: {world.party(party).name} has two movements within {min(gaps)} "
                                f"day(s) ({event_a.id} clearing {mov_a.cleared_on}, {event_b.id} clearing "
                                f"{mov_b.cleared_on}); a missing entry and a wrong amount become two readings")

    return problems, warnings


# --------------------------------------------------------------------------
# what an author reads while writing the world
# --------------------------------------------------------------------------

def summarize(world, task) -> str:
    """Everything the derivation decided, for a human writing the world: the
    scored accounts and their expected balances, each planted item with the
    evidence that makes it inferable, the timing traps, and what the scorer
    pays for the golden and for the untouched original."""
    lines = [f"world {world.id}  ({world.title})",
             f"task  {task.id}  [{task.type}]  {task.period.start}..{task.period.end} ({task.period.label})"]
    try:
        bundle, inputs = derive_contract(world, task)
    except Exception as exc:
        lines.append(f"  derive_contract failed: {type(exc).__name__}: {exc}")
        return "\n".join(lines)

    expected = dict(inputs.expected_balances)
    lines.append("")
    lines.append(f"opening bank balance (derived) {_money(bundle.opening_bank_balance)}    "
                 f"statement closing {_money(inputs.statement_closing)}")
    lines.append(f"scored accounts ({len(inputs.scored_accounts)}):")
    for account in inputs.scored_accounts:
        lines.append(f"    {account:<34}{_money(expected.get(account, 0)):>14}")
    lines.append("expected balances (whole chart; * = scored):")
    for account, value in inputs.expected_balances:
        mark = "*" if account in inputs.scored_accounts else " "
        lines.append(f"  {mark} {account:<34}{_money(value):>14}")

    lines.append("")
    lines.append(f"planted items ({len(inputs.planted)}):")
    for p in inputs.planted:
        lines.append(f"  {p.id}   kind={p.kind}  date={p.date}  from {p.recognition_id}")
        lines.append(f"      required      {[(a, _money(v)) for a, v in p.required]}")
        if p.replaces:
            lines.append(f"      replaces      {[(a, _money(v)) for a, v in p.replaces]}")
        if p.kind == "duplicate":
            lines.append(f"      expected_count {p.expected_count}")
        lines.append(f"      residual      {[(a, _money(v)) for a, v in p.residual]}")
        lines.append(f"      must_be_payee {list(p.must_be_payee)}   narration {p.narration!r}")
        for row in p.evidence:
            lines.append(f"      evidence      {row}")
        lines.append(f"      claim         {p.identifiability_claim}")
    lines.append(f"traps ({len(inputs.traps)}):")
    for t in inputs.traps:
        lines.append(f"  {t.id}   recognised {t.date}  cleared {t.cleared_on}  {_money(t.amount)}  {t.narration!r}")

    lines.append("")
    try:
        env = K.load_contract(inputs)
    except Exception as exc:
        lines.append(f"load_contract refused the derived inputs: {type(exc).__name__}: {exc}")
        return "\n".join(lines)
    for label, text in (("golden", inputs.golden_text), ("original", inputs.original_text)):
        outcome, failure = score_text(text, env, label)
        if failure:
            lines.append(f"{label}: {failure}")
            continue
        lines.append(f"{label:<9} total={outcome.total} complete={outcome.complete} "
                     f"renderable={outcome.renderable} "
                     f"components={ {n: str(v) for n, v in outcome.components} }")
        lines.append(f"          item_states={ {i: str(s) for i, s in outcome.allocation.item_states} }")
        for channel in ("target_misses", "collateral_damage", "unresolved_planted", "removed_or_altered",
                        "fabricated", "merged_events", "undocumented", "plug_accounts", "blocked_by"):
            values = list(getattr(outcome, channel))
            if values:
                lines.append(f"          {channel}={values}")
    return "\n".join(lines)
