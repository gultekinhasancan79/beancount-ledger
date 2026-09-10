"""Occurrence-state conformance: every scorer state answered by a public
reading, or by an argument.

Two modules classify one month and neither may import the other.
`candidate.committed` classifies a SUBMISSION; `graph.identify` classifies
the PUBLIC EVIDENCE an agent is mounted. The question is whether the second
grammar is exhaustive over the first, and the honest answer used to be that
nobody could tell: the scorer's states were bare string literals written at
four sites, so "what can a candidate occurrence be?" had no enumerable
answer and "is every one of them publicly readable?" had no test.

This suite closes that. It needs three things to be true and proves each:

    THE UNIVERSE IS CLOSED. `committed.SCORER_STATES` is the whole of it —
    seven per-item states, five occurrence states, three penalty labels and
    two account states — and the module contains no state-shaped literal
    outside a member's own construction, so an eighteenth state cannot be
    written into a scoring branch without appearing here. The rule the
    universe encodes is that EVERY PRICED CHANNEL NAMES ITS STATE: if
    `score_committed` charges for it, a member labels it and a helper in
    `committed` emits it. The lower-case vocabularies (`BLOCKED_BY`,
    `OUTCOMES`) get their own closure walk, because the state scan is
    SCREAMING_CASE and cannot see them;

    EVERY MEMBER IS ANSWERED. `graph.state_contract` maps each member to a
    public reading class or excludes it with a written argument. The
    MUTATION-COVERAGE test adds a fake member and shows the walk fails, so
    a green result is evidence rather than a tautology;

    THE ANSWERS ARE REAL, AND BOUND TO AN IDENTITY. A positive fixture per
    mapped state — a public world built by hand, in `test_identify`'s style
    — where the scorer reaches the state on a submission over that world
    and the checker reports the mapped reading FOR THE VERY SAME ITEM. Not
    "somewhere on this world": the item that reached the state is projected
    with `derive.planted_key` and the checker's repair with the equal
    `identify.repair_key` is the one whose kind must be in the mapping, so
    re-pointing a mapping at another reading goes red (the TEETH test does
    exactly that). Then pairwise fixtures where one entry could take the
    mapped reading or an alter/settle reading, asserting which public rule
    decides or that the verdict is ambiguous; and, for each exclusion, a
    positive fixture where the scorer emits the state together with a
    witness that no public reading answers it.

    python tests/test_state_conformance.py
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import pickle
import re
import sys
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate.normalise import Accepted, parse_once  # noqa: E402
from beancount_ledger.candidate.schema import ParsedTransaction  # noqa: E402
from beancount_ledger.graph import derive as DV  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402
from beancount_ledger.graph import project as PJ  # noqa: E402
from beancount_ledger.graph import state_contract as SC  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY, alpine_2025_11 as A  # noqa: E402
from repair_keys import master_names, planted_key  # noqa: E402

BANK = "Assets:Bank:Checking"
START, END = "2025-11-01", "2025-11-30"

# The three planted kinds in one hand-built world, so the checker's three
# repair classes and the scorer's three per-kind state families are the same
# month's facts rather than three unrelated fixtures.
ALTER_OFFICE = PJ.AlterRecognition("office_transposed", "rec:office-2025-11", "transpose_digits", 0, "?")
DUP_RENT = PJ.DuplicateRecognition("rent_booked_twice", "rec:rent-2025-11", "?")
OMIT_FEE = A.BANK_RECON_001.plan.mutations[1]              # unrecorded_bank_fee
THREE_KINDS = (ALTER_OFFICE, DUP_RENT, OMIT_FEE)


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:24]:
            print(f"      {line}")
    return ok


# --------------------------------------------------------------------------
# the fixture world, and the two views of it
# --------------------------------------------------------------------------

_CONTRACTS: dict = {}


def contract(mutations: tuple):
    """`(public files, ContractInputs)` for one hand-authored plan over the
    shipped world — the same door `test_identify` uses, so the bytes the
    checker reads are the bytes the environment mounts and the environment
    the scorer reads is derived from those same bytes."""
    if mutations not in _CONTRACTS:
        world, base = REGISTRY["bank_recon_001"]
        task = dataclasses.replace(base, plan=PJ.MutationPlan(mutations))
        _bundle, inputs = DV.derive_contract(world, task)
        public = {name: data.decode("utf-8") for name, data in inputs.public_files}
        _CONTRACTS[mutations] = (public, inputs)
    return _CONTRACTS[mutations]


def verdict_of(public: dict):
    return ID.check_identifiable(public, bank_account=BANK, period_start=START, period_end=END)


def statement_rows(public: dict) -> list:
    out = []
    for line in public[ID.STATEMENT_FILE].splitlines()[1:]:
        if not line.strip():
            continue
        date, description, reference, debit, credit, _balance = line.split(",")
        if not debit and not credit:
            continue
        out.append((date, description, reference, debit, credit))
    return out


def restate(public: dict, rows: list) -> dict:
    """A statement a bank could have printed: rows in date order, the balance
    column walked from the opening balance the world already carries."""
    lines = public[ID.STATEMENT_FILE].splitlines()
    header, opening = lines[0], lines[1]
    balance = D(opening.rsplit(",", 1)[1])
    out = [header, opening]
    for date, description, reference, debit, credit in sorted(rows, key=lambda r: (r[0], r[1])):
        balance += (D(credit) if credit else D("0")) - (D(debit) if debit else D("0"))
        out.append(f"{date},{description},{reference},{debit},{credit},{balance:.2f}")
    return {**public, ID.STATEMENT_FILE: "\n".join(out) + "\n"}


def entry(date: str, payee: str, narration: str, legs: list) -> str:
    body = "".join(f"  {account:<40s} {amount:>10s} USD\n" for account, amount in legs)
    return f'{date} * "{payee}" "{narration}"\n{body}'


def add_entries(public: dict, *entries: str) -> dict:
    return {**public, ID.LEDGER_FILE: public[ID.LEDGER_FILE].rstrip("\n") + "\n\n" + "\n".join(entries)}


def leg(account: str, amount: str) -> str:
    """The projector's fixed layout, so a replace() on the original text hits."""
    return f"  {account:<{PJ.POSTING_ACCOUNT_WIDTH}}{amount:>{PJ.POSTING_AMOUNT_WIDTH}} USD\n"


OFFICE_WRONG = leg("Expenses:Office", "240.00") + leg(BANK, "-240.00")
OFFICE_RIGHT = leg("Expenses:Office", "420.00") + leg(BANK, "-420.00")
OFFICE_HEAD = '2025-11-18 * "Office Depot" "Stationery and printer supplies"\n'
OFFICE_STRANGER = '2025-11-18 * "Nobody In The Master Files" "Stationery and printer supplies"\n'
RENT_ENTRY = ('2025-11-10 * "Cedar Property Group" "November office rent"\n'
              + leg("Expenses:Rent", "3500.00") + leg(BANK, "-3500.00"))
FEE_ENTRY = ('2025-11-30 * "Cascade Bank" "Monthly account service charge"\n'
             + leg("Expenses:BankFees", "85.00") + leg(BANK, "-85.00"))
# The one settled pair the PRESERVED mapping is bound to, named by date and
# amount on both sides: the statement's 2025-11-06 ACH IN of 9,800 and the
# ledger entry that receives it. Row and entry are one event.
SETTLED_ROW_DATE, SETTLED_AMOUNT = "2025-11-06", D("9800.00")
SETTLED_ENTRY = ('2025-11-06 * "Harbor Freight Ltd" "Customer payment for SI-1043"\n'
                 + leg(BANK, "9800.00") + leg("Assets:AR", "-9800.00"))
# An internal reclassification: two chart accounts the task does not score,
# no bank leg, so nothing `identify` reads even touches it.
RECLASSIFICATION = ('2025-11-29 * "Alpine Trading Co." "Reclassify prepaid to inventory"\n'
                    + leg("Assets:Inventory", "500.00") + leg("Assets:Prepayments", "-500.00"))

_SCORED: dict = {}


def score_parts(text: str, inputs):
    """`(environment, committed, outcome)` through the production door, so
    the tests that call a `committed` helper directly feed it exactly what
    `score_committed` fed it."""
    env = K.load_contract(inputs)
    parsed = parse_once(text)
    if not isinstance(parsed, Accepted):
        raise AssertionError(f"fixture text is not accepted: {parsed}")
    receipt = K.new_receipt("conformance", 1, env_mod.digests_of(text.encode("utf-8"), submitted=text))
    commitment = K.commit(parsed, env, receipt)
    return env, commitment, K.score_committed(commitment)


def scored(text: str, inputs):
    """The outcome alone, memoised: the same submission over the same
    environment scores to the same result by construction (that is the
    reward-input identity `recheck` enforces), so re-deriving it per test
    would only cost time."""
    key = (id(inputs), text)
    if key not in _SCORED:
        _SCORED[key] = score_parts(text, inputs)[2]
    return _SCORED[key]


def buckets(outcome) -> set:
    return set(K.occurrence_states(outcome.allocation))


def canonical_occurrences(text: str) -> list:
    """The submission's transactions in the scorer's canonical occurrence
    order — the order `Allocation.keys` and `occurrence_states` index, so a
    position here is the scorer's own identity for an entry."""
    parsed = parse_once(text)
    if not isinstance(parsed, Accepted):
        raise AssertionError(f"fixture text is not accepted: {parsed}")
    return sorted((d for d in parsed.submission.directives if isinstance(d, ParsedTransaction)),
                  key=K.occurrence_key)


def bank_leg(txn) -> D:
    return sum((p.amount for p in txn.postings if p.account == BANK), D("0"))


def posting_key(txn) -> tuple:
    """The entry's postings in the shape `repair_key`/`planted_key` use, so
    the two sides can be compared literally rather than by analogy."""
    return tuple(sorted((p.account, f"{p.amount:.2f}") for p in txn.postings))


def fixture_submissions(inputs) -> dict:
    """Five submissions over the ONE fixture world, between them reaching
    every mapped state. Named here rather than inline so the identity-bound
    walk and its teeth test read the same fixtures."""
    original, golden = inputs.original_text, inputs.golden_text
    return {
        "golden": golden,
        "untouched": original,
        "repair beside the stale entry": original + "\n" + OFFICE_HEAD + OFFICE_RIGHT,
        "wrong entry deleted, nothing posted": original.replace(OFFICE_HEAD + OFFICE_WRONG, ""),
        "both copies of the duplicate removed": original.replace(RENT_ENTRY, "", 2),
    }


def blocked_fixtures(inputs) -> dict:
    """Submissions that reach different `blocked_by` reasons, so the
    vocabulary walk has values the scorer actually emitted."""
    golden = inputs.golden_text
    return {
        "clean": golden,
        "an original entry deleted": golden.replace(SETTLED_ENTRY, ""),
        "an entry nothing explains": golden + "\n" + RECLASSIFICATION,
        "a ghost account opened": golden + "\n2025-01-01 open Equity:Suspense USD\n",
    }


# --------------------------------------------------------------------------
# 1. the universe is closed
# --------------------------------------------------------------------------

_STATE_SHAPED = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
_VOCABULARY_SHAPED = re.compile(r"^[a-z][a-z0-9_]{2,}$")
# Screaming-case string literals in `committed.py` that are NOT states. Each
# one is listed by hand: a new literal has to be classified here or the test
# fails, which is the point.
NOT_A_STATE = {"NO_ARTIFACT"}
# The lower-case vocabularies the scorer draws from, by the name of the
# closed tuple that holds each. `test_the_lower_case_vocabularies_are_closed`
# walks these; `_STATE_SHAPED` cannot see them.
LOWER_VOCABULARIES = ("BLOCKED_BY", "OUTCOMES")


def test_the_state_universe_is_closed_and_every_member_is_named_once():
    """`SCORER_STATES` is the whole universe, and the module writes no state
    outside it.

    The static half is what makes the dynamic half worth anything: a walk of
    `SCORER_STATES` proves nothing if a scoring branch can still assign a
    bare `"SETTLED_LATE"`. So every screaming-case literal in the source is
    either a member's own construction argument (exactly once) or is named
    in `NOT_A_STATE` here.

    THE LIMIT OF THIS SCAN, stated rather than left to be discovered:
    `_STATE_SHAPED` is `^[A-Z][A-Z0-9_]{2,}$`, so it sees SCREAMING_CASE
    literals of three characters or more and NOTHING ELSE. A lower-case
    vocabulary (a `blocked_by` reason, a delivery outcome), a two-character
    name, a mixed-case one and a value built by concatenation or an f-string
    all pass under it. The lower-case vocabularies the scorer actually has
    are closed by `test_the_lower_case_vocabularies_are_closed` below;
    non-literal construction is out of reach of any source scan and is
    covered instead by the conservation identity in `occurrence_states` and
    the `assert state in ITEM_STATES[item.kind]` in `allocate`, which refuse
    a value that is not a member however it was built.
    """
    problems = []
    values = {str(s) for s in K.SCORER_STATES}
    source = (ROOT / "beancount_ledger" / "candidate" / "committed.py").read_text(encoding="utf-8")
    seen: dict = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _STATE_SHAPED.match(node.value):
            seen[node.value] = seen.get(node.value, 0) + 1
    for literal, count in sorted(seen.items()):
        if literal in NOT_A_STATE:
            continue
        if literal not in values:
            problems.append(f"{literal!r} is a state-shaped literal that is not a member of SCORER_STATES")
        elif count != 1:
            problems.append(f"{literal!r} appears {count} times as a literal; a member is written once, "
                            f"where it is constructed, and referenced by name everywhere else")
    for value in sorted(values):
        if value not in seen:
            problems.append(f"{value!r} is a member no literal in the module constructs")
    if len(set(K.SCORER_STATES)) != len(K.SCORER_STATES):
        problems.append("SCORER_STATES carries a duplicate")
    for state in K.SCORER_STATES:
        if not isinstance(state, K.ScorerState) or not isinstance(state, str):
            problems.append(f"{state!r} is not a ScorerState (and a str)")
        if state.scope not in K.STATE_SCOPES:
            problems.append(f"{state!r} has scope {state.scope!r}")
    # ITEM_STATES is derived from the universe, and still says what it said.
    want = {
        "omit": ("MISSING", "RESOLVED"),
        "alter": ("STALE_ONLY", "REMOVED_WITHOUT_REPAIR", "REPAIR_PLUS_STALE", "RESOLVED"),
        "duplicate": ("EXTRA_PRESENT", "OVER_REMOVED", "RESOLVED"),
    }
    for kind, states in want.items():
        if tuple(sorted(K.ITEM_STATES[kind])) != tuple(sorted(states)):
            problems.append(f"ITEM_STATES[{kind!r}] = {K.ITEM_STATES[kind]}, not {states}")
    # A str subclass, deliberately: every existing surface compares, hashes
    # and JSON-encodes these as strings.
    if K.STATE_RESOLVED != "RESOLVED" or {K.STATE_RESOLVED} != {"RESOLVED"} \
            or dict.fromkeys([K.STATE_RESOLVED]) != {"RESOLVED": None}:
        problems.append("a ScorerState no longer compares and hashes as its own string")
    # ... and a COPY of one is a plain str of the same value: `__new__` takes
    # keyword-only metadata, so without `__reduce__` every pickle and every
    # deepcopy of an Allocation or a ScoreOutcome would raise.
    if [type(x) for x in (pickle.loads(pickle.dumps(K.STATE_RESOLVED)), copy.deepcopy(K.STATE_RESOLVED))] != [str, str] \
            or pickle.loads(pickle.dumps(K.STATE_RESOLVED)) != "RESOLVED" or copy.deepcopy(K.STATE_TAMPER) != "TAMPER":
        problems.append("a ScorerState does not pickle/deepcopy to a plain str of the same value")
    return check("the scorer's state universe is closed, enumerable, written once per member, and copies to "
                 "a plain str", not problems, "\n".join(problems))


def test_the_lower_case_vocabularies_are_closed():
    """The other closed vocabularies `committed.py` draws from.

    `blocked_by` reasons and delivery `OUTCOMES` are exactly as much a
    vocabulary as the states are — `tests/exploits` builds payloads that
    claim one by name, and a reason invented inside a branch is a reason no
    consumer can enumerate — but they are lower-case, so the state scan
    above is blind to them. This walk asserts, for each:

        the closed tuple EXISTS and is closed (unique lower-case values);

        every value is CONSTRUCTED as a literal in the module (so the tuple
        is the module's own vocabulary, not a restatement of one);

        every site that PRODUCES a value draws it from the tuple BY NAME —
        `blocked.append(...)` takes a `BLOCKED_*` name, never a literal, and
        each `OUTCOME_*` constant is a member of OUTCOMES;

        the GUARD holds at runtime: `DeliveryReceipt` refuses an outcome
        outside OUTCOMES, and every `blocked_by` the scorer emits on the
        fixture submissions is a member.

    One deliberate weakening against the state scan, and the reason: the
    states are asserted to be written EXACTLY ONCE, which cannot hold here.
    `"policy"` is both a `blocked_by` reason and a key in
    `LoadedEnvironment.material()`, so a lower-case value can legitimately
    appear as an unrelated literal elsewhere in the module. The by-name rule
    at the production sites is what carries the closure instead.

    Still out of scope, said rather than implied: `DeliveryReceipt`'s
    `complete`/`incomplete` pair is a two-value vocabulary that stays inline
    in `__post_init__`; it has no consumer that names a member.
    """
    problems = []
    source = (ROOT / "beancount_ledger" / "candidate" / "committed.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    literals: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _VOCABULARY_SHAPED.match(node.value):
            literals[node.value] = literals.get(node.value, 0) + 1
    for name in LOWER_VOCABULARIES:
        vocabulary = getattr(K, name, None)
        if not isinstance(vocabulary, tuple) or not vocabulary or len(set(vocabulary)) != len(vocabulary):
            problems.append(f"committed.{name} is not a closed tuple of unique values: {vocabulary!r}")
            continue
        for value in vocabulary:
            if not isinstance(value, str) or not _VOCABULARY_SHAPED.match(value):
                problems.append(f"{name}: {value!r} is not a lower-case vocabulary value")
            elif value not in literals:
                problems.append(f"{name}: {value!r} is a member no literal in the module constructs")
    # the production sites name a member; they do not write one
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "append"
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "blocked"):
            arg = node.args[0] if node.args else None
            named = getattr(K, arg.id, None) if isinstance(arg, ast.Name) else None
            if named not in K.BLOCKED_BY:
                problems.append(f"a blocked_by reason is appended that BLOCKED_BY does not carry "
                                f"(line {node.lineno}); a reason is written once, at the tuple, and "
                                f"referenced by name at the branch")
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id.startswith("OUTCOME_") and isinstance(node.value, ast.Constant)):
            if node.value.value not in K.OUTCOMES:
                problems.append(f"{node.targets[0].id} = {node.value.value!r} is not a member of OUTCOMES")
    # the guards
    try:
        K.DeliveryReceipt("rollout", 1, "sideways", "d", "d", "d", "d", "incomplete",
                          K.NO_ARTIFACT, K.NO_ARTIFACT, "0")
    except ValueError:
        pass
    else:
        problems.append("DeliveryReceipt accepted an outcome outside OUTCOMES")
    _public, inputs = contract(THREE_KINDS)
    emitted = set()
    for text in blocked_fixtures(inputs).values():
        emitted |= set(scored(text, inputs).blocked_by)
    if not emitted <= set(K.BLOCKED_BY):
        problems.append(f"the scorer emitted blocked_by reasons outside the vocabulary: "
                        f"{sorted(emitted - set(K.BLOCKED_BY))}")
    if not problems:
        print(f"      · BLOCKED_BY {list(K.BLOCKED_BY)}; reached on the fixtures: {sorted(emitted)}")
        print(f"      · OUTCOMES {list(K.OUTCOMES)}")
    return check("the lower-case vocabularies (blocked_by reasons, delivery outcomes) are closed tuples the "
                 "code draws from by name", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 2. every member is answered
# --------------------------------------------------------------------------

def conformance_problems() -> list:
    """The walk. Reads both live modules, so monkeypatching either shows up
    here — which is what the mutation-coverage test below relies on."""
    problems = []
    states = {str(s) for s in K.SCORER_STATES}
    rows = set(SC.STATE_CONTRACT)
    for missing in sorted(states - rows):
        problems.append(f"{missing}: no row in STATE_CONTRACT — every scorer state needs a public reading "
                        f"or a documented exclusion")
    for orphan in sorted(rows - states):
        problems.append(f"{orphan}: STATE_CONTRACT names a state the scorer cannot reach")
    for state in sorted(states & rows):
        readings, note = SC.STATE_CONTRACT[state]
        for reading in readings:
            if reading not in SC.PUBLIC_READINGS:
                problems.append(f"{state}: maps to {reading!r}, which is not a public reading class")
        if not isinstance(note, str) or len(note.split()) < 20:
            problems.append(f"{state}: the {'mapping' if readings else 'exclusion'} carries no argument")
        if not readings and not note.startswith("EXCLUDED"):
            problems.append(f"{state}: an unmapped state must say EXCLUDED and why")
    return problems


def test_every_scorer_state_has_a_public_reading_or_a_documented_exclusion():
    """The contract walk itself, over the shipped table."""
    problems = conformance_problems()
    covered = sorted(SC.MAPPED_STATES)
    excluded = sorted(SC.EXCLUDED_STATES)
    ok = not problems
    if ok:
        print(f"      · {len(covered)} mapped, {len(excluded)} excluded, "
              f"{len(K.SCORER_STATES)} members total")
    return check("every member of the scorer's closed state universe is mapped or excluded",
                 ok, "\n".join(problems))


def test_the_table_quotes_the_reading_grammar_identify_actually_emits():
    """The public half of the table is not free text either.

    `identify` builds exactly three `Repair` kinds and reports `outstanding`
    and `unexplained` on the verdict; `settled` is the fourth thing a reading
    concludes about a row. If a fourth repair kind is added the table has to
    learn about it, so the kinds are read out of the checker's own source.
    """
    problems = []
    source = (ROOT / "beancount_ledger" / "graph" / "identify.py").read_text(encoding="utf-8")
    kinds = set()
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Repair"
                and node.args and isinstance(node.args[0], ast.Constant)):
            kinds.add(node.args[0].value)
    if kinds != set(SC.REPAIR_READINGS):
        problems.append(f"identify builds repair kinds {sorted(kinds)}; the table declares {sorted(SC.REPAIR_READINGS)}")
    if set(SC.KIND_READING) != set(K.PLANTED_KINDS):
        problems.append(f"KIND_READING covers {sorted(SC.KIND_READING)}, not the planted kinds {list(K.PLANTED_KINDS)}")
    if set(SC.KIND_READING.values()) != set(SC.REPAIR_READINGS):
        problems.append("KIND_READING does not land on exactly the repair readings")
    if set(SC.KIND_READING) != set(DV.PUBLIC_KIND) or any(SC.KIND_READING[k] != DV.PUBLIC_KIND[k] for k in DV.PUBLIC_KIND):
        problems.append(f"KIND_READING disagrees with derive.PUBLIC_KIND: {SC.KIND_READING} vs {DV.PUBLIC_KIND}")
    for field in ("outstanding", "repairs", "unique"):
        if not hasattr(ID.Verdict, "__dataclass_fields__") or field not in ID.Verdict.__dataclass_fields__:
            problems.append(f"identify.Verdict has no {field!r}")
    # The table is DATA: it imports neither of the modules it constrains, so
    # it cannot agree with either by construction.
    table = (ROOT / "beancount_ledger" / "graph" / "state_contract.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(table)):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue                                  # `annotations` is a compiler directive, not a dependency
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) else [])
            problems.append(f"state_contract imports {names}; the table must import nothing")
    return check("the table's public half is the reading grammar identify emits, and the table imports nothing",
                 not problems, "\n".join(problems))


def test_a_state_with_no_mapping_fails_the_walk():
    """MUTATION COVERAGE. A green conformance result is worthless unless the
    walk can go red, so this adds a member to the universe with no row, and
    a row naming a reading the checker cannot emit, and requires each to be
    reported and named. Both mutations are undone and the walk is re-run
    clean, so the test cannot leave the universe patched.
    """
    problems = []
    if conformance_problems():
        return check("a fake state fails the walk", False, "the walk was already failing before the mutation")
    fake = K.ScorerState("SETTLED_LATE", scope=K.OCCURRENCE_SCOPE, meaning="a state nobody wrote a contract for")
    real_states, real_table = K.SCORER_STATES, SC.STATE_CONTRACT
    try:
        K.SCORER_STATES = real_states + (fake,)
        found = conformance_problems()
        if not any("SETTLED_LATE" in p and "STATE_CONTRACT" in p for p in found):
            problems.append(f"an unmapped member did not fail the walk: {found}")
        K.SCORER_STATES = real_states
        SC.STATE_CONTRACT = {**real_table, "PRESERVED": (("reconciled_somehow",), real_table["PRESERVED"][1])}
        found = conformance_problems()
        if not any("reconciled_somehow" in p for p in found):
            problems.append(f"a reading outside the public grammar did not fail the walk: {found}")
        SC.STATE_CONTRACT = real_table
        SC.STATE_CONTRACT = {k: v for k, v in real_table.items() if k != "STALE"}
        found = conformance_problems()
        if not any(p.startswith("STALE:") for p in found):
            problems.append(f"deleting a row did not fail the walk: {found}")
        SC.STATE_CONTRACT = {**real_table, "STALE": ((), "EXCLUDED: because.")}
        found = conformance_problems()
        if not any("STALE" in p and "argument" in p for p in found):
            problems.append(f"an exclusion with no argument did not fail the walk: {found}")
    finally:
        K.SCORER_STATES, SC.STATE_CONTRACT = real_states, real_table
    if conformance_problems():
        problems.append("the universe was left mutated")
    return check("a state with no mapping, a reading outside the grammar and an empty exclusion each fail the walk",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3. a positive fixture per mapped state, bound to an IDENTITY
# --------------------------------------------------------------------------

def _repair_kinds(verdict) -> set:
    return {r.kind for r in verdict.repairs}


def settled_rows(public: dict, verdict) -> list:
    """`[(date, signed amount), ...]`: the rows the reading pairs with a
    ledger entry and reports NOTHING about — every in-period movement row no
    repair answers. `Verdict.matched` counts exactly these, which is the
    cross-check that this reconstruction is the checker's own.

    There is no `settled` object on the verdict to read, because a
    reconciliation reports differences: `settled` IS the absence of a
    finding about a row. So it is reconstructed here from what the checker
    did say, and pinned against `matched`.
    """
    answered = {r.row_date for r in verdict.repairs if r.row_date}
    return [(date, (D(credit) if credit else -D(debit)))
            for date, _description, _reference, debit, credit in statement_rows(public)
            if date not in answered]


def positive_fixture_problems(table: dict | None = None) -> list:
    """THE IDENTITY-BOUND WALK. For every mapped state, the checker's reading
    OF THE VERY SAME ITEM must be one the table maps that state to.

    What this replaces, and why. The first version of this test collected
    every reading the checker emitted ANYWHERE on the fixture world into one
    set and asked whether a state's mapping intersected it. Since the world
    carries all three repair kinds plus a settled pair and an outstanding
    item, that set is nearly the whole grammar, so ANY non-empty mapping
    passed: an adversarial reviewer re-pointed every mapped state at
    `outstanding` and the suite stayed green. A mapping that cannot be
    wrong is not a claim.

    So each assertion now names an identity and follows it across the two
    modules, which is what `derive.planted_key` and `identify.repair_key`
    exist for — one tuple type, two independent implementations, compared
    literally (kind, date, postings, counterparty, booked bank amount,
    expected copies):

        ITEM STATES. The planted item that reached the state on a fixture
        submission is projected with `planted_key`; the checker repair whose
        `repair_key` is EQUAL to it is located (both exist on this world —
        `test_identify` pins the tuples); that repair's kind must be one the
        table maps the state to. Every item that reaches the state is
        checked, not the first, so RESOLVED is bound to all three kinds.

        PRESERVED. Bound to one NAMED settled pair — the 2025-11-06 ACH IN
        of 9,800 and the ledger entry that receives it — proved settled on
        the checker's side (no repair answers that row, it is not
        outstanding, and it is one of the `matched` rows) and PRESERVED on
        the scorer's side (that entry's canonical occurrence, found by date
        and bank leg, is in the preserved bucket of the golden submission).

        PLANTED_REPAIR. The same key equality as the item states, per
        allocated occurrence, plus the literal check that the occurrence the
        scorer allocated carries the key's own date and postings.

    `table` defaults to the shipped contract; the teeth test passes a copy
    with one mapping re-pointed and requires this walk to go red.
    """
    table = SC.STATE_CONTRACT if table is None else table
    mapped = tuple(state for state, (readings, _note) in table.items() if readings)
    problems = []
    public, inputs = contract(THREE_KINDS)
    verdict = verdict_of(public)
    if not verdict.unique:
        return [f"the fixture world is not identifiable: {verdict}"]
    names = master_names(public)
    found: dict = {}
    for repair in verdict.repairs:
        found.setdefault(ID.repair_key(repair), []).append(repair)
    key_of = {p.id: planted_key(p, names, bank_account=BANK) for p in inputs.planted}

    # which planted item reached which item state, and on which submission
    reached_by_item: dict = {}
    reached_bucket: dict = {}
    outcomes: dict = {}
    for label, text in fixture_submissions(inputs).items():
        outcome = scored(text, inputs)
        outcomes[label] = outcome
        for pid, state in outcome.allocation.item_states:
            reached_by_item.setdefault(str(state), {}).setdefault(pid, label)
        for state in buckets(outcome):
            reached_bucket.setdefault(str(state), label)

    def reading_of(pid: str, state: str, readings: tuple, label: str) -> None:
        """The checker's reading of the planted item `pid`, by key equality."""
        key = key_of[pid]
        repairs = found.get(key)
        if not repairs:
            problems.append(f"{state}: the planted item {pid} that reaches it on '{label}' projects to "
                            f"{key}, and no checker repair keys to it — the two sides are not talking "
                            f"about the same item, so the mapping asserts nothing")
            return
        kinds = {r.kind for r in repairs}
        if not kinds <= set(readings):
            problems.append(f"{state}: the checker's own repair for the item that reaches it ({pid} on "
                            f"'{label}', key {key}) reads as {sorted(kinds)}, which is not among the "
                            f"readings the table maps {state} to ({list(readings)})")

    for state in sorted(mapped):
        readings, _note = table[state]
        member = next((s for s in K.SCORER_STATES if str(s) == state), None)
        if member is None:
            problems.append(f"{state}: STATE_CONTRACT maps a state the scorer cannot reach")
            continue

        if member.scope == K.ITEM_SCOPE:
            if state not in reached_by_item:
                problems.append(f"{state}: no submission over the fixture world reaches it")
                continue
            for pid, label in sorted(reached_by_item[state].items()):
                reading_of(pid, state, readings, label)

        elif state == str(K.STATE_PRESERVED):
            if state not in reached_bucket:
                problems.append(f"{state}: no submission over the fixture world reaches it")
                continue
            settled = settled_rows(public, verdict)
            pair = (SETTLED_ROW_DATE, SETTLED_AMOUNT)
            if len(settled) != verdict.matched:
                problems.append(f"PRESERVED: {len(settled)} rows go unanswered by a repair but the checker "
                                f"reports {verdict.matched} matched; the settled set is not reconstructed")
            if settled.count(pair) != 1:
                problems.append(f"PRESERVED: the checker does not settle exactly the {pair[0]} {pair[1]} row; "
                                f"it settles {settled}")
            if any(f"{SETTLED_AMOUNT:.2f}" in item or SETTLED_ROW_DATE in item for item in verdict.outstanding):
                problems.append(f"PRESERVED: the {pair} row is reported as a timing difference, not settled: "
                                f"{verdict.outstanding}")
            golden = outcomes["golden"]
            txns = canonical_occurrences(inputs.golden_text)
            where = [i for i, t in enumerate(txns) if t.date == SETTLED_ROW_DATE and bank_leg(t) == SETTLED_AMOUNT]
            if len(where) != 1:
                problems.append(f"PRESERVED: the golden submission carries {len(where)} occurrences dated "
                                f"{SETTLED_ROW_DATE} with a bank leg of {SETTLED_AMOUNT}, not one")
            elif K.occurrence_states(golden.allocation)[where[0]] is not K.STATE_PRESERVED:
                problems.append(f"PRESERVED: the entry the checker settles is occurrence {where[0]} of the "
                                f"golden submission, and the scorer puts it in "
                                f"{K.occurrence_states(golden.allocation)[where[0]]!r}, not PRESERVED")
            elif SC.READING_SETTLED not in readings:
                problems.append(f"PRESERVED: the checker settles the {pair[0]} {pair[1]} pair — row and entry, "
                                f"one event, answered by no repair and not outstanding — and the scorer "
                                f"preserves that same entry (occurrence {where[0]}); the table maps "
                                f"PRESERVED to {list(readings)}, which does not carry "
                                f"{SC.READING_SETTLED!r}")

        elif state == str(K.STATE_PLANTED_REPAIR):
            if state not in reached_bucket:
                problems.append(f"{state}: no submission over the fixture world reaches it")
                continue
            golden = outcomes["golden"]
            txns = canonical_occurrences(inputs.golden_text)
            allocated = [(pid, index) for pid, index in golden.allocation.planted_to_occurrence if index is not None]
            # A DUPLICATE's repair is a removal, so it never points at an
            # occurrence: `allocate` maps it to None by construction and its
            # resolution shows in the item state. The `duplicate` reading in
            # this mapping is therefore carried by RESOLVED's binding above,
            # where the duplicate item's planted_key finds the checker's
            # `duplicate` repair.
            posted = sorted(p.id for p in inputs.planted if p.kind != "duplicate")
            if sorted(pid for pid, _index in allocated) != posted:
                problems.append(f"PLANTED_REPAIR: the golden submission allocates "
                                f"{sorted(pid for pid, _i in allocated)}, not the posted items {posted}")
            for pid, index in allocated:
                if K.occurrence_states(golden.allocation)[index] is not K.STATE_PLANTED_REPAIR:
                    problems.append(f"PLANTED_REPAIR: occurrence {index} carries item {pid} but sits in "
                                    f"{K.occurrence_states(golden.allocation)[index]!r}")
                    continue
                key = key_of[pid]
                if (txns[index].date, posting_key(txns[index])) != (key[1], key[2]):
                    problems.append(f"PLANTED_REPAIR: the occurrence the scorer allocated to {pid} is "
                                    f"{txns[index].date} {posting_key(txns[index])}, and the shared key says "
                                    f"{key[1]} {key[2]}")
                reading_of(pid, state, readings, "golden")

        else:
            problems.append(f"{state}: mapped, but this walk binds no identity for a "
                            f"{member.scope}-scoped state — add one rather than leaving the mapping unproved")

    # and the specific pairings, named rather than counted
    reported = _repair_kinds(verdict)
    want = {"missing_entry": "the 2025-11-30 service charge the books never recorded",
            "wrong_amount": "the 2025-11-18 card payment booked 240.00 against a 420.00 row",
            "duplicate": "the 2025-11-10 rent entry the books carry twice"}
    for kind, description in want.items():
        if kind not in reported:
            problems.append(f"the checker did not report {kind} ({description})")
    if verdict.matched != 5:
        problems.append(f"the checker settled {verdict.matched} rows, not the 5 the fixture carries")
    return problems


def test_a_positive_fixture_for_every_mapped_state():
    """One hand-built public world carrying all three planted kinds, read
    twice: by the checker, which must report the mapped reading FOR THE SAME
    ITEM, and by the scorer, which must reach the state on a submission over
    that same world.

    Sharing one world is deliberate. A per-state fixture would let the two
    grammars be checked against different months, which is precisely the
    cross-layer comparison the 29% incident was made of; here the bytes the
    checker reads and the environment the scorer scores come from one
    `derive_contract` call, and the item is followed across the two by the
    shared repair key rather than by the coincidence of both grammars being
    exercised somewhere on the month.
    """
    _public, inputs = contract(THREE_KINDS)
    problems = positive_fixture_problems()
    if not problems:
        reached: dict = {}
        for label, text in fixture_submissions(inputs).items():
            outcome = scored(text, inputs)
            for _pid, state in outcome.allocation.item_states:
                reached.setdefault(str(state), label)
            for state in buckets(outcome):
                reached.setdefault(str(state), label)
        print("      · states reached: " + ", ".join(f"{s}({reached[s]})" for s in sorted(reached)))
        print(f"      · PRESERVED is bound to the {SETTLED_ROW_DATE} {SETTLED_AMOUNT} settled pair; every "
              f"other mapping to a planted_key == repair_key identity")
    return check("every mapped state has a positive fixture bound to an identity: the checker's reading of "
                 "the very item the scorer put in that state is one the table maps it to",
                 not problems, "\n".join(problems))


def test_re_pointing_one_mapping_fails_the_identity_bound_walk():
    """TEETH. The walk above is worth its green only if a WRONG mapping goes
    red, and the version it replaced did not: re-pointing every mapped state
    at `outstanding` left the suite at 8/8, because the assertion was
    against a world-global set of readings rather than against an identity.

    So: re-point one mapping at a time in a COPY of the table, and require
    the walk to report a problem naming that state. `MISSING -> duplicate`
    is the case the reviewer used — a reading the checker really does emit
    on this world, so nothing but the identity binding can reject it. The
    shipped table is never mutated (the walk takes the table as an
    argument), and it is re-run clean at the end.
    """
    problems = []
    if positive_fixture_problems():
        return check("re-pointing a mapping fails the identity-bound walk", False,
                     "the identity-bound walk was already failing before the mutation")
    repointed = (("MISSING", SC.READING_DUPLICATE),
                 ("RESOLVED", SC.READING_OUTSTANDING),
                 ("PRESERVED", SC.READING_OUTSTANDING),
                 ("PLANTED_REPAIR", SC.READING_SETTLED),
                 ("EXTRA_PRESENT", SC.READING_MISSING_ENTRY))
    for state, wrong in repointed:
        mutated = {**SC.STATE_CONTRACT, state: ((wrong,), SC.STATE_CONTRACT[state][1])}
        found = positive_fixture_problems(mutated)
        if not any(p.startswith(f"{state}:") for p in found):
            problems.append(f"re-pointing {state} at {wrong!r} did not fail the walk: {found}")
    if positive_fixture_problems():
        problems.append("the shipped table stopped passing the walk after the mutations")
    if not problems:
        print("      · " + ", ".join(f"{s}->{w}" for s, w in repointed) + " each go red")
    return check("re-pointing a mapping at a reading the checker emits elsewhere on the same world fails the "
                 "walk, one state at a time", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 4. pairwise: the mapped reading against an alter/settle reading
# --------------------------------------------------------------------------

def pairwise_settled_against_an_alteration() -> dict:
    """The 8,000 row could settle the 8,000 entry or restate the 7,500 one.

    Both edges are admissible: same counterparty, one day apart, inside the
    ACH window and inside `ALTER_WINDOW_DAYS`. The public rule is the
    settlement convention in `## Matching the statement to the ledger` — a
    row and an entry of the same amount and counterparty inside the clearing
    window ARE one transaction — so only maximum-settlement matchings are
    readings at all, and the 7,500 entry is a deposit in transit.
    """
    public, _inputs = contract(THREE_KINDS)
    return add_entries(public, entry("2025-11-24", "Summit Wholesale", "Further payment against SI-1051",
                                     [(BANK, "7500.00"), ("Assets:AR", "-7500.00")]))


def pairwise_missing_against_an_alteration() -> dict:
    """A 27 November credit of 1,855.51 quoting SI-1055 and a 29 November
    entry of 4,329.51 quoting the same invoice.

    The invoice reference is a DOCUMENT reference, which several receipts may
    share, so it founds no alteration edge; and `## Dates` says the bank
    processes on or after the day the transaction happens, so an entry dated
    after the row cannot be what the row credited. The row is a receipt the
    books never recorded; the entry is a deposit in transit.
    """
    public, _inputs = contract(THREE_KINDS)
    public = add_entries(public, entry("2025-11-29", "Harbor Freight Ltd", "Part payment received on SI-1055",
                                       [(BANK, "4329.51"), ("Assets:AR", "-4329.51")]))
    return restate(public, statement_rows(public)
                   + [("2025-11-27", "ACH IN HARBOR FREIGHT LTD", "SI-1055", "", "1855.51")])


def pairwise_duplicate_against_an_alteration() -> dict:
    """Two identical 3,500 rent entries and a CHECK row of 3,600.

    Every reading has to explain the whole month. One entry must answer the
    row across an alteration edge; the other is 20 days before the cut-off,
    so it cannot read as a timing difference and the only class left for it
    is the surplus copy of its twin. Both roles in one reading.
    """
    public, _inputs = contract((DUP_RENT, OMIT_FEE))
    rows = [(date, description, reference, ("3600.00" if description.startswith("CHECK 1037") else debit), credit)
            for date, description, reference, debit, credit in statement_rows(public)]
    return restate(public, rows)


def pairwise_two_fee_readings() -> dict:
    """Two service-charge rows (85.00 on the 28th, 95.00 on the 30th) and two
    85.00 service-charge entries (the 28th and the 30th).

    Either entry can settle the 85.00 row and the other is then restated
    against the 95.00 row. Both matchings settle exactly one row, so the
    settlement convention does not separate them, and they disagree about
    WHICH entry carries the wrong amount: different repair multisets, so the
    only honest verdict is ambiguous.
    """
    public, _inputs = contract((OMIT_FEE,))
    rows = [r for r in statement_rows(public) if "SERVICE CHARGE" not in r[1]]
    public = add_entries(
        public,
        entry("2025-11-28", "Cascade Bank", "Monthly account service charge",
              [("Expenses:BankFees", "85.00"), (BANK, "-85.00")]),
        entry("2025-11-30", "Cascade Bank", "Monthly account service charge",
              [("Expenses:BankFees", "85.00"), (BANK, "-85.00")]))
    return restate(public, rows + [("2025-11-28", "MONTHLY ACCOUNT SERVICE CHARGE", "", "85.00", ""),
                                   ("2025-11-30", "MONTHLY ACCOUNT SERVICE CHARGE", "", "95.00", "")])


def test_pairwise_the_checker_names_a_public_rule_or_reports_ambiguity():
    """Four fixtures in which one entry could take a mapped reading or an
    alter/settle reading. Each asserts WHICH way it went and why — three
    decided by a rule the public files state, one ambiguous.

    Asserting only `unique` would pass for a checker that guessed, and
    asserting only `not unique` would pass for a parse error. So each case
    pins the repair multiset or the ambiguity wording.
    """
    problems = []

    v = verdict_of(pairwise_settled_against_an_alteration())
    # 2025-11-24, the DATE THE 7,500 ENTRY CARRIES: a `wrong_amount` reading
    # restates a booked entry and keeps that entry's own date, so a repair
    # against the 7,500 movement would be dated 24 November. The clause read
    # 2025-11-25 (the row's date) and could therefore never fire, which made
    # the "the settlement convention forced the pairing" half of this
    # assertion vacuous.
    if not v.unique or SC.READING_WRONG_AMOUNT in {r.kind for r in v.repairs if r.date == "2025-11-24"} \
            or not any("7500.00" in item for item in v.outstanding):
        problems.append(f"settled vs alteration: expected the settlement convention to force the pairing and "
                        f"leave 7,500 in transit; got {v}\n  repairs={[str(r) for r in v.repairs]}\n"
                        f"  outstanding={v.outstanding}")

    v = verdict_of(pairwise_missing_against_an_alteration())
    missing = [r for r in v.repairs if r.amount == D("1855.51")]
    if not v.unique or len(missing) != 1 or missing[0].kind != SC.READING_MISSING_ENTRY \
            or missing[0].date != "2025-11-27" or not any("4329.51" in item for item in v.outstanding):
        problems.append(f"missing vs alteration: expected time direction to refuse the alteration edge; got {v}\n"
                        f"  repairs={[str(r) for r in v.repairs]}\n  outstanding={v.outstanding}")

    v = verdict_of(pairwise_duplicate_against_an_alteration())
    kinds = sorted(r.kind for r in v.repairs if r.date == "2025-11-10")
    if not v.unique or kinds != [SC.READING_DUPLICATE, SC.READING_WRONG_AMOUNT]:
        problems.append(f"duplicate vs alteration: expected one reading carrying both roles; got {v}\n"
                        f"  repairs={[str(r) for r in v.repairs]}")

    v = verdict_of(pairwise_two_fee_readings())
    if v.unique or v.readings < 2 or "cannot tell which one it is" not in v.reason:
        problems.append(f"two fee readings: expected an ambiguity naming the competing movements; got {v}")
    return check("pairwise, the checker either decides by a public rule or reports the ambiguity",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 5. the exclusions
# --------------------------------------------------------------------------

def test_the_original_books_can_never_be_stale():
    """The STALE exclusion, on three legs.

    (1) STRUCTURAL. The public reading grammar has no class for retired
    content left in place: `identify` builds three repair kinds, reports
    outstanding items and unexplained ones, and that is all.

    (2) BEHAVIOURAL. The entry the scorer would call stale IS public — it is
    the wrongly-booked entry and the surplus rent copy — and the checker
    reads it as `wrong_amount` and `duplicate`, i.e. as the difference to be
    repaired, never as something explained and forgiven.

    (3) THE ARGUMENT ITSELF. Two submissions over ONE world, whose public
    bytes are therefore byte-identical, differ in whether the scorer's stale
    bucket is empty. A classification that varies while the evidence is
    constant is not a reading of that evidence; it is a judgement about a
    document the public reader never sees.
    """
    problems = []
    public, inputs = contract(THREE_KINDS)
    verdict = verdict_of(public)
    if K.STATE_STALE in SC.PUBLIC_READINGS or "STALE" not in SC.EXCLUDED_STATES:
        problems.append("STALE is not excluded in the table")
    if any(str(r.kind) == "stale" for r in verdict.repairs):
        problems.append("the checker reported a `stale` repair class")
    wrong = [r for r in verdict.repairs if r.kind == SC.READING_WRONG_AMOUNT and r.date == "2025-11-18"]
    dup = [r for r in verdict.repairs if r.kind == SC.READING_DUPLICATE and r.date == "2025-11-10"]
    if len(wrong) != 1 or len(dup) != 1:
        problems.append(f"the checker does not report the two entries the scorer can call stale as the "
                        f"differences they are: {[str(r) for r in verdict.repairs]}")

    untouched = scored(inputs.original_text, inputs)
    golden = scored(inputs.golden_text, inputs)
    if len(untouched.allocation.stale) != 2 or K.STATE_STALE not in buckets(untouched):
        problems.append(f"the untouched original does not leave the two retired occurrences stale: "
                        f"{untouched.allocation.stale}")
    if golden.allocation.stale or K.STATE_STALE in buckets(golden):
        problems.append(f"the golden submission left something stale: {golden.allocation.stale}")
    if untouched.environment_digest != golden.environment_digest:
        problems.append("the two submissions were not scored against one environment")
    # the public bytes are the same bytes in both cases: nothing the checker
    # could read distinguishes them.
    again = {name: data.decode("utf-8") for name, data in inputs.public_files}
    if again != public:
        problems.append("the fixture's public bytes are not stable")
    if not problems:
        print("      · one world, identical public bytes; stale=2 for the untouched books, stale=0 for the golden")
    return check("STALE is a state of an agent's leftover: the public books are read as the difference, and the "
                 "bucket varies while the public bytes do not", not problems, "\n".join(problems))


def test_the_original_books_are_never_unexplained_merged_or_plugged():
    """The other three exclusions, as literal properties of the ORIGINAL
    public ledger of every world the environment can serve.

    UNEXPLAINED and FABRICATED: allocate the original against its own
    environment — every occurrence is preserved content or content a planted
    item retires, so the unexplained bucket is empty and nothing is priced as
    a fabrication.

    MERGED: no original occurrence straddles two planted shapes; the
    contract audits the predicates disjoint and derivation refuses a
    collision, so the merge label cannot attach to a pre-existing entry.

    PLUG: `allowed_accounts` is the chart the projector emitted the ledger
    from, so the original names no account outside it.
    """
    problems = []
    worlds = [("bank_recon_001 (three kinds)", contract(THREE_KINDS)),
              ("bank_recon_001 (shipped plan)", None)]
    world, base = REGISTRY["bank_recon_001"]
    _bundle, shipped_inputs = DV.derive_contract(world, base)
    worlds[1] = ("bank_recon_001 (shipped plan)",
                 ({name: data.decode("utf-8") for name, data in shipped_inputs.public_files}, shipped_inputs))
    for label, (_public, inputs) in worlds:
        outcome = scored(inputs.original_text, inputs)
        if outcome.allocation.unexplained or K.STATE_UNEXPLAINED in buckets(outcome):
            problems.append(f"{label}: the original ledger has unexplained occurrences {outcome.allocation.unexplained}")
        if outcome.fabricated:
            problems.append(f"{label}: the original ledger is priced as fabrication {outcome.fabricated}")
        if outcome.merged_events:
            problems.append(f"{label}: an original occurrence was labelled merged {outcome.merged_events}")
        if outcome.plug_accounts:
            problems.append(f"{label}: the original ledger names a plug account {outcome.plug_accounts}")
        if outcome.removed_or_altered:
            problems.append(f"{label}: the original ledger fails preservation against itself {outcome.removed_or_altered}")
        if set(buckets(outcome)) - {K.STATE_PRESERVED, K.STATE_STALE}:
            problems.append(f"{label}: the original ledger occupies a bucket other than PRESERVED/STALE: "
                            f"{sorted(set(buckets(outcome)))}")
        # and the checker, on the same world's public bytes, finds nothing
        # that its own `unexplained` class would fire on
        verdict = verdict_of(_public)
        if not verdict.unique:
            problems.append(f"{label}: the checker refuses the shipped world: {verdict.reason[:160]}")
    return check("the original public books are never UNEXPLAINED, MERGED, FABRICATED or a PLUG",
                 not problems, "\n".join(problems))


def test_the_three_priced_channels_that_have_no_public_reading():
    """TAMPER, UNDOCUMENTED and COLLATERAL: a positive fixture each.

    These three are priced channels of `score_committed` — `PENALTY_TAMPER`,
    `PENALTY_UNDOCUMENTED`, `PENALTY_COLLATERAL` — that the closed universe
    did not name until this change, so "every state the scorer can reach is
    answered" was true of a universe that was not the whole scorer. Each now
    has a member, a helper in `committed` that emits it where the penalty is
    computed, and a row in the table.

    All three are exclusions, and the argument has the same shape as STALE's
    in every case: the public bytes the checker reads are IDENTICAL across
    two submissions that differ in the state, so the state cannot be a
    reading of those bytes. What differs is which side of the public grammar
    the state falls outside of:

        TAMPER is the complement of PRESERVED. The entry it names is public
        — here the 2025-11-06 receipt of 9,800 — and the checker's reading
        of it is `settled`, the case the reconciliation reports nothing
        about. 'Deleted by the agent' is not a further fact about that pair.

        UNDOCUMENTED is an attribution penalty on the AGENT's entry. The
        public reading does name a counterparty (`Office Depot` is on both
        sides of the shared repair key), but that is the party the corrected
        books must show; what the agent wrote in the payee field is in a
        file the checker never opens.

        COLLATERAL is ACCOUNT-scoped, like PLUG. It classifies a balance,
        and the public grammar classifies entries and rows — and `identify`
        does not even read the accounts involved, since it reads only
        entries that touch the bank account.
    """
    problems = []
    public, inputs = contract(THREE_KINDS)
    verdict = verdict_of(public)
    golden = inputs.golden_text
    for state in ("TAMPER", "UNDOCUMENTED", "COLLATERAL"):
        if state not in SC.EXCLUDED_STATES or SC.readings_for(state):
            problems.append(f"{state} is not excluded in the table")
        if state not in {str(s) for s in K.SCORER_STATES}:
            problems.append(f"{state} is not a member of the closed universe")

    # ---- TAMPER: the settled pair, deleted ------------------------------
    text = golden.replace(SETTLED_ENTRY, "")
    if text == golden:
        problems.append("the TAMPER fixture did not remove the settled entry from the golden text")
    env, commitment, outcome = score_parts(text, inputs)
    labelled = K.tamper_states(env, commitment.submission, commitment.allocation)
    if {s for _label, s in labelled} != {K.STATE_TAMPER} or [x for x, _s in labelled] != list(outcome.removed_or_altered):
        problems.append(f"tamper_states does not label exactly what score_committed priced: {labelled} vs "
                        f"{outcome.removed_or_altered}")
    if len(outcome.removed_or_altered) != 1 or SETTLED_ROW_DATE not in outcome.removed_or_altered[0]:
        problems.append(f"the TAMPER fixture does not lose exactly the {SETTLED_ROW_DATE} entry: "
                        f"{outcome.removed_or_altered}")
    if K.BLOCKED_TAMPERED not in outcome.blocked_by:
        problems.append(f"a TAMPERed submission is not blocked: {outcome.blocked_by}")
    if scored(golden, inputs).removed_or_altered:
        problems.append("the golden submission loses original content")
    # the very entry the scorer calls TAMPER is the pair the checker settles
    settled = settled_rows(public, verdict)
    if (SETTLED_ROW_DATE, SETTLED_AMOUNT) not in settled:
        problems.append(f"the entry the TAMPER fixture deletes is not one the checker settles: {settled}")

    # ---- UNDOCUMENTED: the right repair, the wrong party ----------------
    text = golden.replace(OFFICE_HEAD + OFFICE_RIGHT, OFFICE_STRANGER + OFFICE_RIGHT)
    if text == golden:
        problems.append("the UNDOCUMENTED fixture did not re-attribute the office repair")
    env, commitment, outcome = score_parts(text, inputs)
    labelled = K.undocumented_states(env, commitment.allocation, canonical_occurrences(text))
    if {s for _label, s in labelled} != {K.STATE_UNDOCUMENTED} or [x for x, _s in labelled] != list(outcome.undocumented):
        problems.append(f"undocumented_states does not label exactly what score_committed priced: {labelled} "
                        f"vs {outcome.undocumented}")
    if len(outcome.undocumented) != 1 or not outcome.undocumented[0].startswith("office_transposed:"):
        problems.append(f"the UNDOCUMENTED fixture does not charge the office repair: {outcome.undocumented}")
    if dict(outcome.allocation.item_states)["office_transposed"] != K.STATE_RESOLVED:
        problems.append("the UNDOCUMENTED fixture did not resolve the item it mis-attributes")
    if scored(golden, inputs).undocumented:
        problems.append("the golden submission is undocumented")
    # the public side DOES name the counterparty — for the corrected books
    key = planted_key(next(p for p in inputs.planted if p.id == "office_transposed"),
                      master_names(public), bank_account=BANK)
    repairs = [r for r in verdict.repairs if ID.repair_key(r) == key]
    if len(repairs) != 1 or repairs[0].counterparty != "Office Depot":
        problems.append(f"the checker's repair for office_transposed does not name the counterparty: "
                        f"{[str(r) for r in repairs]}")

    # ---- COLLATERAL: a balance the task does not score ------------------
    text = golden + "\n" + RECLASSIFICATION
    env, commitment, outcome = score_parts(text, inputs)
    expected, targets = dict(env.expected_balances), list(env.scored_accounts)
    labelled = K.collateral_states(commitment.candidate.balances, expected, targets)
    if {s for _account, s in labelled} != {K.STATE_COLLATERAL} \
            or [a for a, _s in labelled] != [item.rsplit(": expected ", 1)[0] for item in outcome.collateral_damage]:
        problems.append(f"collateral_states does not label exactly what score_committed priced: {labelled} vs "
                        f"{outcome.collateral_damage}")
    if sorted(a for a, _s in labelled) != ["Assets:Inventory", "Assets:Prepayments"]:
        problems.append(f"the COLLATERAL fixture does not move exactly the two internal accounts: {labelled}")
    if any(a in targets for a, _s in labelled) or outcome.target_misses:
        problems.append(f"the COLLATERAL fixture moved a SCORED account: {labelled} / {outcome.target_misses}")
    if scored(golden, inputs).collateral_damage:
        problems.append("the golden submission does collateral damage")

    # ---- and the shared witness: the public bytes never moved -----------
    again = {name: data.decode("utf-8") for name, data in inputs.public_files}
    if again != public or verdict_of(again).unique is not True:
        problems.append("the fixture's public bytes are not stable across the three submissions")
    for account in ("Assets:Inventory", "Assets:Prepayments"):
        if any(account in str(r) for r in verdict.repairs) or any(account in o for o in verdict.outstanding):
            problems.append(f"{account} reached the public reading grammar; it has no bank leg")
    if not problems:
        print("      · TAMPER: the 2025-11-06 pair the checker settles, deleted — one world, identical bytes")
        print("      · UNDOCUMENTED: office_transposed RESOLVED and charged; the checker's own repair for it "
              "names Office Depot")
        print("      · COLLATERAL: Assets:Inventory / Assets:Prepayments, neither scored nor read by identify")
    return check("TAMPER, UNDOCUMENTED and COLLATERAL are each emitted by a committed helper on a positive "
                 "fixture, and none of them is a reading of the public bytes", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 5. the cash-application state catalogue (candidate/application.py)
# --------------------------------------------------------------------------

# `application/1` classifies the REGISTER delivered beside the ledger, and
# its closed universe gets the same three proofs as the ledger scorer's:
# the universe is closed and written once per member; every member is
# answered by a row of `state_contract.APPLICATION_STATE_CONTRACT` — mapped
# to the PUBLIC DOCUMENTS that decide the fact behind it, or excluded with
# an argument; and a fake member or a re-pointed row fails the walk. The
# positive fixture per state (every member reached on a scored register,
# with the diagnosis the spec names) lives in
# `tests/test_cash_application_scoring.py`, beside the S-rows that reach
# them.

from beancount_ledger.candidate import application as AP  # noqa: E402
from beancount_ledger.graph import cash_application as CA  # noqa: E402

# Screaming-case string literals in `application.py` that are NOT states.
NOT_AN_APPLICATION_STATE: set = set()
APPLICATION_LOWER_VOCABULARIES = ("PENALTY_LABELS", "REJECTION_LABELS", "STATUSES", "CHANNELS", "STATE_SCOPES")


def test_the_application_state_universe_is_closed_and_every_member_is_named_once():
    problems = []
    values = {str(s) for s in AP.APPLICATION_STATES}
    source = (ROOT / "beancount_ledger" / "candidate" / "application.py").read_text(encoding="utf-8")
    seen: dict = {}
    literals: set = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.add(node.value)
            if _STATE_SHAPED.match(node.value):
                seen[node.value] = seen.get(node.value, 0) + 1
    for literal, count in sorted(seen.items()):
        if literal in NOT_AN_APPLICATION_STATE:
            continue
        if literal not in values:
            problems.append(f"{literal!r} is a state-shaped literal that is not a member of APPLICATION_STATES")
        elif count != 1:
            problems.append(f"{literal!r} appears {count} times as a literal; a member is written once")
    for value in sorted(values):
        if value not in seen:
            problems.append(f"{value!r} is a member no literal in the module constructs")
    if len(set(AP.APPLICATION_STATES)) != len(AP.APPLICATION_STATES) or len(AP.APPLICATION_STATES) != 26:
        problems.append(f"APPLICATION_STATES has {len(AP.APPLICATION_STATES)} members, with duplicates or not 26")
    for state in AP.APPLICATION_STATES:
        if not isinstance(state, AP.ApplicationState) or not isinstance(state, str):
            problems.append(f"{state!r} is not an ApplicationState (and a str)")
        elif state.scope not in AP.STATE_SCOPES:
            problems.append(f"{state!r} has scope {state.scope!r}")
    if {s.scope for s in AP.APPLICATION_STATES} != set(AP.STATE_SCOPES):
        problems.append("a scope is declared and unused, or used and undeclared")
    if AP.RECEIPT_EXACT != "RECEIPT_EXACT" or {AP.RECEIPT_EXACT} != {"RECEIPT_EXACT"} \
            or dict.fromkeys([AP.AR_TIE_OK]) != {"AR_TIE_OK": None}:
        problems.append("an ApplicationState no longer compares and hashes as its own string")
    if [type(x) for x in (pickle.loads(pickle.dumps(AP.RECEIPT_EXACT)), copy.deepcopy(AP.RECEIPT_EXACT))] != [str, str] \
            or copy.deepcopy(AP.APPLICATION_REJECTED) != "APPLICATION_REJECTED":
        problems.append("an ApplicationState does not pickle/deepcopy to a plain str of the same value")
    # the lower-case vocabularies: closed tuples whose members the module writes as literals
    for name in APPLICATION_LOWER_VOCABULARIES:
        vocabulary = getattr(AP, name, None)
        if not isinstance(vocabulary, tuple) or not vocabulary or len(set(vocabulary)) != len(vocabulary):
            problems.append(f"application.{name} is not a closed tuple of unique values: {vocabulary!r}")
            continue
        for value in vocabulary:
            if value not in literals:
                problems.append(f"{name}: {value!r} is a member no literal in the module constructs")
    if set(AP.PENALTY_PRICES) != set(AP.PENALTY_LABELS):
        problems.append("PENALTY_PRICES and PENALTY_LABELS disagree")
    return check("the application scorer's state universe is closed (26 members, written once each, five scopes), "
                 "copies to a plain str, and its lower-case vocabularies are closed tuples the module writes",
                 not problems, "\n".join(problems))


def application_conformance_problems(states=None, table=None) -> list:
    problems = []
    states = {str(s) for s in AP.APPLICATION_STATES} if states is None else {str(s) for s in states}
    table = SC.APPLICATION_STATE_CONTRACT if table is None else table
    rows = set(table)
    for missing in sorted(states - rows):
        problems.append(f"{missing}: no row in APPLICATION_STATE_CONTRACT — every application state needs the "
                        f"public documents that decide it, or a documented exclusion")
    for orphan in sorted(rows - states):
        problems.append(f"{orphan}: APPLICATION_STATE_CONTRACT names a state the scorer cannot reach")
    for state in sorted(states & rows):
        authorities, note = table[state]
        for authority in authorities:
            if authority not in SC.APPLICATION_AUTHORITIES:
                problems.append(f"{state}: names {authority!r}, which is not a public authority")
        if not isinstance(note, str) or len(note.split()) < 20:
            problems.append(f"{state}: the {'mapping' if authorities else 'exclusion'} carries no argument")
        if not authorities and not note.startswith("EXCLUDED"):
            problems.append(f"{state}: an unmapped state must say EXCLUDED and why")
    return problems


def test_every_application_state_has_a_public_authority_or_a_documented_exclusion():
    problems = application_conformance_problems()
    # the authorities are the family's public files (the reference column of the statement counted as its file)
    public = set(env_mod.PUBLIC_FILES) | set(CA.EXTRA_PUBLIC_FILES)
    for authority in SC.APPLICATION_AUTHORITIES:
        if authority.split(":")[0] not in public:
            problems.append(f"{authority!r} is not a public file of the family")
    if set(SC.APPLICATION_EXCLUDED_STATES) != {"APPLICATION_ABSENT", "APPLICATION_REJECTED"}:
        problems.append(f"excluded: {SC.APPLICATION_EXCLUDED_STATES}; only the two artifact states are properties "
                        f"of the submission alone")
    if not problems:
        print(f"      · {len(SC.APPLICATION_MAPPED_STATES)} mapped, {len(SC.APPLICATION_EXCLUDED_STATES)} "
              f"excluded, {len(AP.APPLICATION_STATES)} members total")
    return check("every member of the application scorer's state universe is mapped to public authorities or "
                 "excluded with an argument, and the authorities are the family's public files",
                 not problems, "\n".join(problems))


def test_an_application_state_with_no_row_fails_the_walk():
    problems = []
    real_states, real_table = AP.APPLICATION_STATES, SC.APPLICATION_STATE_CONTRACT
    fake = AP.ApplicationState("RECEIPT_SETTLED_LATE", scope=AP.RECEIPT_SCOPE)
    found = application_conformance_problems(states=real_states + (fake,))
    if not any("RECEIPT_SETTLED_LATE" in p and "no row" in p for p in found):
        problems.append("a state with no row passed the walk")
    found = application_conformance_problems(table={**real_table, "RECEIPT_EXACT": (("oracle.csv",),
                                                                                     real_table["RECEIPT_EXACT"][1])})
    if not any("oracle.csv" in p for p in found):
        problems.append("a row naming a non-public authority passed the walk")
    found = application_conformance_problems(table={k: v for k, v in real_table.items() if k != "CREDIT_MISSING"})
    if not any("CREDIT_MISSING" in p for p in found):
        problems.append("a dropped row passed the walk")
    found = application_conformance_problems(table={**real_table, "APPLICATION_ABSENT": ((), "EXCLUDED: because.")})
    if not any("APPLICATION_ABSENT" in p and "no argument" in p for p in found):
        problems.append("an exclusion without an argument passed the walk")
    found = application_conformance_problems(table={**real_table, "GHOST_STATE": ((SC.AUTHORITY_POLICY,),
                                                                                    real_table["RECEIPT_EXACT"][1])})
    if not any("GHOST_STATE" in p and "cannot reach" in p for p in found):
        problems.append("an orphan row passed the walk")
    if AP.APPLICATION_STATES is not real_states or SC.APPLICATION_STATE_CONTRACT is not real_table:
        problems.append("the walk mutated the live modules")
    return check("MUTATION COVERAGE: a fake application state, a non-public authority, a dropped row, a bare "
                 "exclusion and an orphan row each fail the walk", not problems, "\n".join(problems))


TESTS = [
    test_the_state_universe_is_closed_and_every_member_is_named_once,
    test_the_lower_case_vocabularies_are_closed,
    test_every_scorer_state_has_a_public_reading_or_a_documented_exclusion,
    test_the_table_quotes_the_reading_grammar_identify_actually_emits,
    test_a_state_with_no_mapping_fails_the_walk,
    test_a_positive_fixture_for_every_mapped_state,
    test_re_pointing_one_mapping_fails_the_identity_bound_walk,
    test_pairwise_the_checker_names_a_public_rule_or_reports_ambiguity,
    test_the_original_books_can_never_be_stale,
    test_the_original_books_are_never_unexplained_merged_or_plugged,
    test_the_three_priced_channels_that_have_no_public_reading,
    test_the_application_state_universe_is_closed_and_every_member_is_named_once,
    test_every_application_state_has_a_public_authority_or_a_documented_exclusion,
    test_an_application_state_with_no_row_fails_the_walk,
]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
