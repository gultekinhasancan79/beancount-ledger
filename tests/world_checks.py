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
from beancount_ledger.graph import cash_application as CA  # noqa: E402
from beancount_ledger.graph import content as C  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402
from beancount_ledger.graph import project as PJ  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.policy import POLICY_SECTIONS, is_cash_application_world, movement_of, required_sections  # noqa: E402
from beancount_ledger.graph.schema import AppliedReceipt, check_world  # noqa: E402

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
    # accounting rules THIS world exercises cite — the legacy eight always,
    # the cash-application family's two when an event of theirs is authored
    # (`policy.required_sections`). `project()` enforces this too, but as a
    # ProjectionError inside derive_contract; saying it here names the
    # missing heading and the rule that wanted it.
    required = required_sections(world)
    for section in sorted(set(required.values())):
        if section not in world.policy_text:
            rules = ", ".join(sorted(r for r, s in required.items() if s == section))
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
    #
    # SCOPED to the bank-evidenced plants: `identify.py` reconciles bank
    # movements and is not taught the cash-application family's files, so a
    # planted write-off — a recognition with no bank leg, established by the
    # advice plus the policy — is not something it can read. Gate (m) below
    # validates that plant instead (amount, invoice, date, customer, shape).
    verdict = None
    try:
        verdict = ID.check_identifiable(public, bank_account=world.bank_account,
                                        period_start=task.period.start, period_end=task.period.end)
    except Exception as exc:
        problems.append(f"{where}: check_identifiable raised {type(exc).__name__}: {exc}")
    if verdict is not None:
        names = master_names(public)
        bank_evidenced = [p for p in inputs.planted if any(a == world.bank_account for a, _ in p.required)]
        want = sorted(planted_key(p, names, bank_account=world.bank_account) for p in bank_evidenced)
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
            # an advice line's cash and claimed deduction are authored facts
            # too: the 20.00 the policy writes off IS the 20.00 the customer
            # claimed, not a derived literal
            for line in getattr(event, "lines", ()):
                authored.add(abs(line.amount))
                authored.add(abs(line.deduction))
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

    # (l), (m), (n): the cash-application family's own gates, on a world the
    # family is inferred from. A legacy world runs none of them.
    if is_cash_application_world(world):
        family_problems, family_warnings = _family_gates(world, task, bundle, inputs, public, where)
        problems.extend(family_problems)
        warnings.extend(family_warnings)

    return problems, warnings


# --------------------------------------------------------------------------
# the cash-application family's gates (spec section 5 and 8)
# --------------------------------------------------------------------------

#: An APPLICATION INSTRUCTION in a narration or an advice note: a directive
#: of money to an invoice or credit-note id, WITH OR WITHOUT an amount — a
#: verb of application or settlement in the same clause as an id ("apply to
#: SI-3101 then SI-3102", "SI-3102 is to be posted at 1830.00", "SI-3102
#: settled", "pay SI-3102"), an amount sent "to" or "against" an id ("2400
#: to SI-3101", "apply 1,830.00 to SI-3102"), an amount standing next to an
#: id in any punctuation ("SI-3102 1830.00", "SI-3102: 1830.00", "SI-3104
#: (1890.00)", "1830.00 for SI-3102", "credit SI-3102 with 1830.00"), a
#: sequence over invoices ("SI-3102 then SI-3104", "SI-3102 first"), a
#: residue sent to an id ("the balance to SI-3102"), or an id "in full". The
#: spec's "apply 1,830.00 to SI-3102" is an instance of the rule, not its
#: definition. A genuine payment reference is not an instruction ("GR PAYRUN
#: 0428", "SI-3104 SI-3102", "check 2291 for SI-3103": a cheque, run or
#: reference number is not an amount), and neither is "after application of
#: CN-0412" or "written off under the cash application policy": nothing is
#: directed anywhere by either.
_VERB = (r"(?:apply|applied|applying|allocate|allocated|allocating|allocation|post|posted|posting|"
         r"book|booked|booking|match|matched|matching|offset|offsetting|"
         r"settle|settles|settled|settling|pay|pays|paid|paying)")
#: Verbs that direct money only when they stand right before the id: "credit"
#: and "clear" are nouns and descriptions elsewhere in a note ("credit
#: requested", "cheque cleared").
_DIRECT_VERB = r"(?:credit|credits|credited|crediting|clear|clears|cleared|clearing)"
_ID = r"(?:SI|CN)-\d+"
_SI = r"SI-\d+"
_TO = r"(?:to|against|on|onto|toward|towards)"
_AMOUNT = (r"(?<![-\w.])(?:\$\s*|USD\s*)?\d(?:[\d,]*\d)?(?:\.\d+)?"    # never the digits of an id
           r"(?![\w-])(?!\.\d)")                                        # nor the first field of a date
_NOT_A_NUMBER_LABEL = r"(?<!check )(?<!cheque )(?<!chq )(?<!#)(?<!no\. )(?<!no )(?<!ref )(?<!run )"
_CLAUSE = r"(?:[^.;\n]|(?<=\d)\.(?=\d)){0,80}?"                   # a decimal point is not a clause end
#: What may stand between an id and its amount: punctuation, or one small
#: connecting word ("with", "for", "at", "of", "=").
_GAP = (r"(?:[ \t:,()\[\]{}\-–—=@/*]|\b(?:with|for|of|at|re|per|in|is|was|"
        r"to|against|on|onto|toward|towards)\b){0,6}")
_SEQ = r"(?:then|first|firstly|next|last|lastly|before|after|followed\s+by|thereafter|subsequently|prior\s+to)"
_INSTRUCTION = re.compile(
    rf"\b{_VERB}\b{_CLAUSE}\b{_ID}\b"
    rf"|\b{_ID}\b{_CLAUSE}\b{_VERB}\b"
    rf"|\b{_DIRECT_VERB}\s+(?:the\s+|invoice\s+)?{_ID}\b"
    rf"|{_AMOUNT}\s+{_TO}\s+{_ID}\b"
    rf"|\b{_ID}\b{_GAP}{_AMOUNT}"                                     # id, then an amount within reach
    rf"|{_NOT_A_NUMBER_LABEL}{_AMOUNT}{_GAP}\b{_ID}\b"                 # an amount, then the id
    rf"|\b{_SI}\b{_CLAUSE}\b{_SEQ}\b{_CLAUSE}\b{_SI}\b"              # SI-a then/before/after SI-b
    rf"|\b{_SI}\b[ \t,]*(?:first|firstly|next|last|lastly)\b"
    rf"|\b(?:first|firstly|then|next|secondly)\b[ \t,:]*(?:the\s+|invoice\s+)?{_SI}\b"
    rf"|\b(?:balance|remainder|remaining|rest|residue|excess)\b{_CLAUSE}\b{_TO}\s+{_ID}\b"
    rf"|\b{_ID}\b{_CLAUSE}\bin\s+full\b",
    re.IGNORECASE)
_INVOICE_TOKEN = re.compile(r"\bSI-\d+\b")
_CREDIT_TOKEN = re.compile(r"\bCN-\d+\b")


def public_ties(ev, receipt_id: str) -> frozenset:
    """The invoices the PUBLIC documents tie to one payment (U10): the ids
    its statement row's reference quotes, and the lines of the advice the
    evidence BINDS to that row. A receipt with no advice ties nothing beyond
    its reference, whatever the author typed in `AppliedReceipt.lines` —
    those are not a public document then, even when policy rung (3) reaches
    exactly them and gate (m) passes."""
    receipt = next((r for r in ev.receipts if r.receipt_id == receipt_id), None)
    if receipt is None:
        return frozenset()
    advice = ev.advice_for(receipt)
    return frozenset(set(_INVOICE_TOKEN.findall(receipt.reference))
                     | ({line.invoice_id for line in advice.lines} if advice is not None else set()))


def narration_problems(text: str, tied: frozenset, credit_notes: frozenset, label: str) -> list:
    """Gate (n) / U10 on one narration or advice note: no application
    instruction; every invoice it names is one a public document ties to
    that payment (`tied`); every credit note it names exists."""
    out = []
    hit = _INSTRUCTION.search(text or "")
    if hit:
        out.append(f"{label} carries an application instruction: {hit.group(0)!r}")
    for token in sorted(set(_INVOICE_TOKEN.findall(text or ""))):
        if token not in tied:
            out.append(f"{label} names {token}, which no public document ties to that payment")
    for token in sorted(set(_CREDIT_TOKEN.findall(text or ""))):
        if token not in credit_notes:
            out.append(f"{label} names {token}, which is not a credit note in the evidence")
    return out


def _family_gates(world, task, bundle, inputs, public, where) -> tuple:
    """Returns `(problems, warnings)`. A `WARN_*` the public evidence or the
    public fold raises — U12's deduction of exactly the tolerance or advice
    line on a zero-balance invoice, an advice bound to no row — is a
    WARNING here too, never a gate: section 7 has a 25.00 deduction "written
    off with the U12 warning", so a world at the spec's own boundary must
    pass `verify_world`. Refusals (`REFUSE_*`) remain problems."""
    problems: list = []
    warnings: list = []
    truth = inputs.application
    if truth is None:
        return [f"{where}: a cash-application world derived no ApplicationInputs"], warnings
    kw = dict(bank_account=world.bank_account, period_start=task.period.start, period_end=task.period.end)
    receivables = truth.receivables_account
    expected = dict(inputs.expected_balances)

    # (l) the register entering the period ties to the opening entry, read
    # off the PROJECTED BYTES by the public fold (U7), and row for row is the
    # register the truth derived from the documents and the March receipts.
    try:
        ev = CA.read_evidence(public, **kw)
    except CA.Refusal as exc:
        return problems + [f"{where}: gate (l): the public evidence refuses: {exc}"], warnings
    except Exception as exc:
        return problems + [f"{where}: gate (l): read_evidence raised {type(exc).__name__}: {exc}"], warnings
    carried = dict(world.opening.carried).get(receivables, Decimal("0"))
    if ev.opening_ar != carried or truth.opening_ar != carried:
        problems.append(f"{where}: gate (l): opening receivables read {ev.opening_ar} (public) / {truth.opening_ar} "
                        f"(truth) against the opening entry's {carried}")
    public_register = tuple((i.invoice_id, i.customer, i.invoice_date, i.due_date, i.face_value, i.period_basis)
                            for i in ev.invoices if i.source == "register")
    if public_register != truth.opening_register:
        problems.append(f"{where}: gate (l): open_items.csv reads {public_register}, the truth's register is "
                        f"{truth.opening_register}")
    for warning in ev.warnings:
        warnings.append(f"WARN: {where}: the public evidence warns: {warning}")

    # (m) the public fold over the ACTUAL projected bytes equals the truth
    # folded from the authored facts, under a key built independently on
    # each side; closing AR ties to the expected ledger's receivables; and
    # every write-off the truth makes is a separate entry of the expected
    # ledger with that amount, invoice, date, customer and shape.
    try:
        app = CA.fold(public, **kw)
    except CA.Refusal as exc:
        return problems + [f"{where}: gate (m): the public fold refuses: {exc}"], warnings
    except Exception as exc:
        return problems + [f"{where}: gate (m): the public fold raised {type(exc).__name__}: {exc}"], warnings
    if CA.application_key(app) != truth.application_key():
        left = dict(_key_rows(CA.application_key(app)))
        right = dict(_key_rows(truth.application_key()))
        moved = sorted(k for k in set(left) | set(right) if left.get(k) != right.get(k))
        problems.append(f"{where}: gate (m): the public fold and the truth disagree on "
                        + "; ".join(f"{k}: public {left.get(k)} vs truth {right.get(k)}" for k in moved[:6]))
    if app.closing_ar != expected.get(receivables) or truth.closing_ar != expected.get(receivables):
        problems.append(f"{where}: gate (m): closing AR public {app.closing_ar} / truth {truth.closing_ar} against "
                        f"the expected ledger's {expected.get(receivables)} (U8)")
    for warning in app.warnings:
        if warning not in ev.warnings:                   # the fold repeats the evidence's own
            warnings.append(f"WARN: {where}: the public fold warns: {warning}")
    golden = parse_once(inputs.golden_text)
    original = parse_once(inputs.original_text)
    if not isinstance(golden, Accepted) or not isinstance(original, Accepted):
        return problems + [f"{where}: gate (m): the ledgers do not parse"], warnings
    def shaped(text_parsed, date, payee, shape):
        return [t for t in text_parsed.submission.directives if isinstance(t, ParsedTransaction)
                and t.date == date and (t.payee or "") == payee and frozenset(K._txn_shape(t)) == shape]
    for receipt in truth.receipts:
        receipt_id, date, customer, _amount, _applied, offs, _unapplied, _rid, event_id, rec_id = receipt
        total = sum((amount for _, amount in offs), Decimal("0"))
        shape = _pairs(((truth.write_off_account, total), (receivables, -total)))
        entries = shaped(golden, date, customer, shape) if offs else []
        if offs and len(entries) != 1:
            problems.append(f"{where}: gate (m): the expected ledger carries {len(entries)} write-off entries for "
                            f"{receipt_id} ({date}, {customer}, {sorted(shape)}), not one")
        elif offs:
            named = set(_INVOICE_TOKEN.findall(entries[0].narration))
            written = {invoice_id for invoice_id, _ in offs}
            if named != written:
                problems.append(f"{where}: gate (m): the write-off entry for {receipt_id} names {sorted(named)}, "
                                f"the register writes off {sorted(written)}")
        if not offs and any(t for t in golden.submission.directives if isinstance(t, ParsedTransaction)
                            and t.date == date and (t.payee or "") == customer
                            and truth.write_off_account in {a for a, _ in K._txn_shape(t)}):
            problems.append(f"{where}: gate (m): the expected ledger writes something off for {receipt_id} and "
                            f"the register writes off nothing")
        planted = [p for p in inputs.planted if p.recognition_id == rec_id + "-writeoff"]
        for p in planted:
            if p.kind != "omit" or p.date != date or _pairs(p.required) != shape or p.must_be_payee != (customer,):
                problems.append(f"{where}: gate (m): the planted write-off {p.id} ({p.kind}, {p.date}, "
                                f"{p.required}, {p.must_be_payee}) is not the register's ({date}, {sorted(shape)}, "
                                f"{customer})")
            if offs and shaped(original, date, customer, shape):
                problems.append(f"{where}: gate (m): the write-off {p.id} is planted as omitted and the opening "
                                f"ledger still carries it")
        if offs and not planted and not shaped(original, date, customer, shape):
            problems.append(f"{where}: gate (m): the write-off for {receipt_id} is not planted, yet the opening "
                            f"ledger lacks it")

    # (n) the narration rule (U10): a receipt or write-off narration may carry
    # the genuine payment reference; it may not carry an application
    # instruction or name an invoice no PUBLIC document ties to that payment
    # — the statement row's reference and the advice the evidence binds to
    # it, read off the projected bytes, not the authored lines. The same rule
    # governs advice notes.
    credit_numbers = frozenset(c.credit_note_id for c in ev.credit_notes)
    receipt_of_event = {r[8]: r[0] for r in truth.receipts}
    for event in world.events:
        if not isinstance(event, AppliedReceipt):
            continue
        slug = event.id.split(":", 1)[1]
        if event.id not in receipt_of_event:
            problems.append(f"{where}: gate (n): the truth derived no statement receipt for {event.id}")
        tied = public_ties(ev, receipt_of_event.get(event.id, ""))
        for rec in bundle.recognitions:
            if rec.event_id == event.id:
                problems.extend(f"{where}: gate (n): {p}" for p in narration_problems(
                    rec.narration, tied, credit_numbers, f"the narration of {rec.id} {rec.narration!r}"))
        for i, line in enumerate(event.lines, 1):
            problems.extend(f"{where}: gate (n): {p}" for p in narration_problems(
                line.note, tied, credit_numbers, f"advice note {slug} line {i} {line.note!r}"))
    return problems, warnings


def _key_rows(key: tuple):
    for section, rows in key:
        for row in rows:
            yield f"{section} {row[0]}", row[1:]


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
