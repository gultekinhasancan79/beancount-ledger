"""The state conformance contract: every scorer state answered by a public
reading class, or by a written exclusion.

Two modules classify the same month and neither may import the other.

    `candidate.committed` classifies a SUBMISSION. Its closed universe is
    `SCORER_STATES`: seven per-item states, five occurrence states (the four
    allocation buckets and TAMPER, the loss of an original occurrence),
    three penalty labels and two account states.

    `graph.identify` classifies the PUBLIC EVIDENCE — the mounted
    `ledger.beancount` and `bank_statement.csv` as an agent reads them,
    with no world, no bundle and no recognition id. Its closed universe is
    `PUBLIC_READINGS` below: the classes a bank reconciliation can put an
    ORIGINAL ledger entry or statement row into.

The question this module exists to answer is the reviewer's, asked of the
scorer instead of the checker: *for every state the scorer can reach, what
is the corresponding public reading, and where there is none, why?* Left
unanswered, the two grammars drift — an entry the scorer can price is a
condition the public reader has no name for, so the world is unsolvable
from the bytes, and neither module can notice because neither knows about
the other. That is exactly how a "publicly identifiable" claim was true at
sweep precision and false at scorer precision.

**This module imports nothing.** It is data, not behaviour. It names both
universes by their string values and `tests/test_state_conformance.py`
walks it against the two live modules: a member added to `SCORER_STATES`
without a row here fails; a row naming a state or a reading neither module
produces fails. Importing `committed` would make the table agree with the
scorer by construction, which is the one thing it must not do; importing
`identify` would break that module's standing guarantee that it imports
nothing from the graph packages.

WHY IT LIVES HERE rather than in `tests/`. The mapping is normative: it is
the claim that every condition the scorer prices is a condition a reader of
the public files can name, which is the task's solvability contract and not
a property of the test suite. `RETAINED_FIELDS` in `candidate.committed`
sets the precedent — a closed inventory published beside the code, walked
by a test. It sits under `graph/` beside `identify.py`, whose reading
grammar it quotes; it is not owned by `identify.py` and is not imported by
it.

WHAT A MAPPING MEANS. For a state `S` mapped to readings `R`: whenever the
scorer can put an item or an occurrence into `S`, the public evidence for
that same item or occurrence is read by `identify` as one of `R`. It does
NOT mean the state and the reading are the same fact — the state describes
what the AGENT did, the reading describes what the ORIGINAL BOOKS are — it
means the defect behind the state has a public name.

WHAT AN EXCLUSION MEANS. There is no public reading, because the state is a
property of the submitted document that no original public document can
exhibit. Each exclusion carries its argument and is witnessed by a test.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# the public reading grammar (graph/identify.py)
# --------------------------------------------------------------------------

# What a bank reconciliation can conclude about one original ledger entry or
# one statement row, from the mounted bytes alone.
READING_SETTLED = "settled"                 # row and entry are one event: the books already carry it
READING_MISSING_ENTRY = "missing_entry"     # a row nothing in the books answers: post it, on the row's date
READING_WRONG_AMOUNT = "wrong_amount"       # a booked entry whose figure the row contradicts: restate it
READING_DUPLICATE = "duplicate"             # a surplus copy of a movement the statement shows fewer times
READING_OUTSTANDING = "outstanding"         # `## Outstanding checks` / `## Deposits in transit`: a timing
                                            # difference, not an error — both policy sections land here
READING_UNEXPLAINED = "unexplained"         # a stranded entry that reads neither as a timing difference nor
                                            # as a difference the statement evidences: the verdict is not
                                            # unique and the world is refused at mint

PUBLIC_READINGS = (READING_SETTLED, READING_MISSING_ENTRY, READING_WRONG_AMOUNT, READING_DUPLICATE,
                   READING_OUTSTANDING, READING_UNEXPLAINED)

# The three reading classes that are REPAIRS: `identify.Repair.kind`, and the
# public names of the three planted kinds (`derive.PUBLIC_KIND`).
REPAIR_READINGS = (READING_MISSING_ENTRY, READING_WRONG_AMOUNT, READING_DUPLICATE)

# planted kind -> the reading class an original book in that condition occupies
KIND_READING = {
    "omit": READING_MISSING_ENTRY,
    "alter": READING_WRONG_AMOUNT,
    "duplicate": READING_DUPLICATE,
}


# --------------------------------------------------------------------------
# the table
# --------------------------------------------------------------------------

# state -> (readings, note). `readings` empty means EXCLUDED and the note is
# the exclusion argument. Order is the order of `committed.SCORER_STATES`.
STATE_CONTRACT: dict = {

    # ---- item states -----------------------------------------------------
    "MISSING": ((READING_MISSING_ENTRY,),
                "The item is an omission, so the public evidence is a statement row no ledger entry "
                "answers, and the reader posts it on the row's date (contract change B). MISSING says "
                "the agent did not; `missing_entry` says what the books are. Same defect, two sides."),

    "STALE_ONLY": ((READING_WRONG_AMOUNT,),
                   "The item is an alteration: the books carry the entry with the wrong figure and the "
                   "statement contradicts it, which the reader reports as `wrong_amount`. STALE_ONLY "
                   "adds that the agent neither restated nor removed it."),

    "REMOVED_WITHOUT_REPAIR": ((READING_WRONG_AMOUNT,),
                               "Same public defect as STALE_ONLY — the books' figure is wrong and the "
                               "row says so. The agent deleted the entry and posted nothing, which is "
                               "not the repair `wrong_amount` calls for."),

    "REPAIR_PLUS_STALE": ((READING_WRONG_AMOUNT,),
                          "Same public defect again. The agent posted the corrected entry and left the "
                          "wrong one beside it, so the books now show the movement twice."),

    "EXTRA_PRESENT": ((READING_DUPLICATE,),
                      "The item is a duplication: the books carry a movement more times than the "
                      "statement shows it, which the reader reports as `duplicate`. EXTRA_PRESENT says "
                      "the surplus copy is still there."),

    "OVER_REMOVED": ((READING_DUPLICATE,),
                     "Same public defect. The agent removed the surplus copy AND the occurrence the "
                     "correct books keep, which the `duplicate` reading explicitly does not ask for: it "
                     "names how many copies remain (`expected_copies`), not zero."),

    "RESOLVED": (REPAIR_READINGS,
                 "The agent's treatment matches the correct books. Which public defect was repaired "
                 "depends on the item's kind, so the reading is the kind's class: `missing_entry` for "
                 "an omission, `wrong_amount` for an alteration, `duplicate` for a duplication "
                 "(`KIND_READING`). RESOLVED is the only state that credits `errors_resolved`."),

    # ---- occurrence buckets ---------------------------------------------
    "PRESERVED": ((READING_SETTLED,),
                  "The occurrence is original content the correct books also carry. For a bank-touching "
                  "entry the reader classifies it as `settled` — a row and an entry that are one event, "
                  "the case the reconciliation reports nothing about. LIMIT, stated rather than "
                  "implied: `identify` reads only entries that touch the bank account, so a preserved "
                  "entry with no bank leg (a sale's revenue recognition, its cost-of-goods twin) is "
                  "outside the public reading grammar altogether. It is still PRESERVED, and the "
                  "public reader neither names it nor needs to: it is not part of a bank "
                  "reconciliation. `settled` is the mapping for the bank-touching case, which is every "
                  "occurrence the reconciliation can be wrong about."),

    "PLANTED_REPAIR": (REPAIR_READINGS,
                       "The occurrence satisfies a planted item's repair predicate — it IS the repair "
                       "the public reading calls for, so its reading is the item kind's class. The two "
                       "sides are compared literally, not by analogy: `derive.planted_key` and "
                       "`identify.repair_key` build the same tuple type independently and "
                       "`mint._require_public_uniqueness` refuses a world where they disagree."),

    "STALE": ((),
              "EXCLUDED: a state of the AGENT's leftover, not of the original public books. The "
              "underlying entry is public — it is the wrongly-booked entry or the surplus copy, and "
              "`identify` reads it as `wrong_amount` or `duplicate`, which is exactly the mapping the "
              "item states above already carry. What STALE adds is not a fact about that entry but a "
              "judgement about a SUBMISSION: this content was retired by a repair the agent was asked "
              "to make, the agent left it, and the scorer will therefore decline to price it as a "
              "fabrication while leaving its item unresolved. 'Retired' is defined only relative to a "
              "repair obligation, and the original books carry no obligation — before an agent acts "
              "there is no leftover, only the defect. The public reading grammar has no class for "
              "'still here and forgiven' because a reader of the bytes has nothing to forgive: it "
              "reports the entry as the difference it is. The witness is that STALE varies between two "
              "submissions while the public bytes are byte-identical, so it cannot be a reading of "
              "those bytes."),

    "UNEXPLAINED": ((),
                    "EXCLUDED: an occurrence the task does not explain — neither pre-existing, nor a "
                    "repair, nor retired content. The original public books can contain no such "
                    "occurrence by construction: `load_contract` accepts the original ledger clean and "
                    "every one of its transactions is either content the correct books keep or content "
                    "a planted item retires, so `allocate(env, original)` leaves `unexplained` empty "
                    "for every world the environment can serve. `identify` does carry a class of the "
                    "same NAME, but it is not a counterpart: it is the checker's refusal — a stranded "
                    "entry that reads neither as a timing difference nor as an evidenced difference — "
                    "and a world in which it fires is not unique and is refused at mint, so it never "
                    "reaches a scorer at all. Mapping the two would claim a correspondence between a "
                    "state of a submitted file and a reason a world was never minted."),

    "TAMPER": ((),
               "EXCLUDED: original content the submission no longer carries — an occurrence the correct "
               "books keep, a lifecycle directive, an option value. It is the complement of PRESERVED and, "
               "like STALE, a state of a SUBMISSION rather than of the original public books. What the "
               "checker reads at that entry is the `settled` pair PRESERVED already maps to: a row and an "
               "entry that are one event, the case the reconciliation reports nothing about. 'Removed' is "
               "not a further fact about that pair, it is a difference between the original books and a "
               "file the public reader never sees, and the original cannot exhibit it by definition — an "
               "entry the original carries is an entry the original carries. The witness is STALE's: two "
               "submissions over ONE world, whose public bytes are therefore byte-identical, differ in "
               "whether anything is TAMPERed, and a classification that varies while the evidence is "
               "constant is not a reading of that evidence."),

    # ---- penalty labels --------------------------------------------------
    "MERGED": ((),
               "EXCLUDED: an authored occurrence that straddles two or more planted repair shapes — one "
               "entry doing the work of two repairs. It is a property of what the agent wrote. The "
               "original books cannot exhibit it: `load_contract` audits the planted predicates "
               "pairwise disjoint and disjoint from the original ledger, and `derive_contract` refuses "
               "a world where a planted shape collides with a legitimate same-date entry, so no "
               "original occurrence answers two planted shapes. There is no public reading class for it "
               "because there is no public document it could describe."),

    "FABRICATED": ((),
                   "EXCLUDED, and for the same reason as UNEXPLAINED, of which it is the price: an "
                   "unexplained occurrence that is not merged, or a lifecycle directive the original "
                   "did not carry. Both halves are states of the submission — the original's directives "
                   "are, definitionally, the original's directives. `identify`'s `unexplained` is a "
                   "refusal to certify a world, not a reading a shipped world's books can occupy."),

    "UNDOCUMENTED": ((),
                     "EXCLUDED: a resolved planted repair whose payee is not one the item accepts. The "
                     "public reading DOES name a counterparty — `identify.repair_key` carries the "
                     "customers.csv / vendors.csv name the corrected entry must be attributed to, and "
                     "`derive.planted_key` carries the same name on the truth side — but that is the party "
                     "the CORRECT BOOKS must show, not what the agent wrote. UNDOCUMENTED is an attribution "
                     "penalty read off the AGENT's own file, and the public checker never sees that file: "
                     "two submissions differing only in the payee string on one repair produce different "
                     "UNDOCUMENTED over byte-identical public evidence. The public reading of the item is "
                     "its kind's repair class either way — the repair is the same repair, which is why the "
                     "occurrence stays a PLANTED_REPAIR — so a mapping here would restate RESOLVED's row "
                     "while claiming the checker had read something it cannot read."),

    # ---- accounts --------------------------------------------------------
    "PLUG": ((),
             "EXCLUDED: an account the submission posts to or opens that the published chart does not "
             "carry. `allowed_accounts` IS the chart, derived from `world.accounts`, and the original "
             "ledger is projected from those same accounts, so every account the original names is in "
             "the chart. The public reading grammar is about entries and rows, not about the chart; a "
             "reader who found an account outside `accounts.csv` would be reading a file the projector "
             "cannot emit."),

    "COLLATERAL": ((),
                   "EXCLUDED, and for PLUG's reason: the state is ACCOUNT-scoped and the public reading "
                   "grammar is not. A reading classifies one original ledger ENTRY or one statement ROW; "
                   "COLLATERAL classifies a BALANCE — an account of the published chart the task does not "
                   "score whose total the submission moved off the correct books' figure. There is no row "
                   "and no entry for it to be a reading of, and `identify` does not read those accounts at "
                   "all: it reads only entries that touch the bank account, so a purely internal account "
                   "(`Assets:Inventory` against `Assets:Prepayments`) never enters its grammar even when "
                   "the original books post to it. Like PLUG it is a property of what the AGENT's file "
                   "does to the chart, and it varies between two submissions whose public bytes are "
                   "byte-identical."),
}

MAPPED_STATES = tuple(state for state, (readings, _note) in STATE_CONTRACT.items() if readings)
EXCLUDED_STATES = tuple(state for state, (readings, _note) in STATE_CONTRACT.items() if not readings)


def readings_for(state: str) -> tuple:
    """The public reading classes a state maps to; empty when excluded."""
    return STATE_CONTRACT[state][0]


def note_for(state: str) -> str:
    """The mapping's justification, or the exclusion argument."""
    return STATE_CONTRACT[state][1]
