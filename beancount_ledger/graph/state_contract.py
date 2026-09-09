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


# --------------------------------------------------------------------------
# the cash-application state catalogue (candidate/application.py)
# --------------------------------------------------------------------------

# `application/1` classifies the REGISTER an agent delivers beside its
# ledger. Its closed universe is `application.APPLICATION_STATES`. The
# question asked of it is the one asked of the ledger scorer above: for
# every state the register scorer can reach, which PUBLIC DOCUMENT decides
# the fact behind it — so an agent reading the evidence pack can name the
# defect — and where none does, why. The authorities are the public files
# of the family (spec section 5): the fold `graph/cash_application.py`
# reconstructs the truth register from exactly these, so a state mapped to
# an authority is a state the public fold could have avoided.

AUTHORITY_ADVICE = "remittance_advice.csv"             # rung (1): the customer's advice, bound to the payment
AUTHORITY_REFERENCE = "bank_statement.csv:reference"   # rung (2): the invoices the statement reference quotes
AUTHORITY_STATEMENT = "bank_statement.csv"             # the receipt's existence, date, amount and remitter
AUTHORITY_POLICY = "policy.md"                         # rung (3), the credit rule, the tolerance, the unapplied rule
AUTHORITY_OPEN_ITEMS = "open_items.csv"                # the carried invoices, their customer and period basis
AUTHORITY_LEDGER = "ledger.beancount"                  # the in-period sales: invoice, customer, gross
AUTHORITY_CREDIT_NOTES = "credit_notes.csv"            # the credit notes: id, invoice, gross
AUTHORITY_CUSTOMERS = "customers.csv"                  # the customer names a row must print

APPLICATION_AUTHORITIES = (AUTHORITY_ADVICE, AUTHORITY_REFERENCE, AUTHORITY_STATEMENT, AUTHORITY_POLICY,
                           AUTHORITY_OPEN_ITEMS, AUTHORITY_LEDGER, AUTHORITY_CREDIT_NOTES, AUTHORITY_CUSTOMERS)

# state -> (authorities, note). `authorities` empty means EXCLUDED and the
# note is the exclusion argument. Order is `application.APPLICATION_STATES`.
APPLICATION_STATE_CONTRACT: dict = {

    # ---- receipts ----------------------------------------------------------
    "RECEIPT_EXACT": ((AUTHORITY_ADVICE, AUTHORITY_REFERENCE, AUTHORITY_POLICY),
                      "The record's canonical applied mapping, write-offs and unapplied residue all equal the "
                      "truth. Which authority decided the receipt is the fold's first rung that reached it: the "
                      "advice bound to the payment, else the invoices the statement reference quotes, else the "
                      "policy's oldest-first rule — all public."),

    "RECEIPT_CONTRADICTS_ADVICE": ((AUTHORITY_ADVICE,),
                                   "The receipt has a remittance advice bound to it (customer, payment reference "
                                   "and amount agree) and the record applies cash to a different SET of invoices "
                                   "than the advice's lines name. The advice is the first authority and it is "
                                   "public, so the defect is named by a document the agent holds."),

    "RECEIPT_CONTRADICTS_REFERENCE": ((AUTHORITY_REFERENCE, AUTHORITY_POLICY),
                                      "No advice belongs to the payment; the statement reference quotes invoice "
                                      "numbers and the record's invoice set is not what rung (2) reaches — the "
                                      "named invoices in invoice-date order, then number, each up to its open "
                                      "balance, any remainder by rung (3). Both the reference and the ordering "
                                      "sentence are public."),

    "RECEIPT_WRONG_INVOICES": ((AUTHORITY_POLICY,),
                               "Neither an advice nor a reference names invoices for this payment, so rung (3) "
                               "decides — the customer's open invoices oldest first by invoice date, then number "
                               "— and the record's invoice set is not that. The rule is printed in policy.md; "
                               "no case exercises it and a fixture does."),

    "RECEIPT_WRONG_AMOUNT": ((AUTHORITY_ADVICE, AUTHORITY_REFERENCE, AUTHORITY_POLICY),
                             "The record names exactly the invoices the authority names and splits the cash among "
                             "them differently: an advice line's amount, or rung (2)'s each-up-to-its-open-balance "
                             "order, misread. Diagnosed as an amount defect, not as wrong invoices, because the "
                             "destinations are right."),

    "RECEIPT_WRONG_WRITEOFF": ((AUTHORITY_ADVICE, AUTHORITY_POLICY),
                               "The applications are right and the receipt's written_off mapping is not: a "
                               "shortfall the advice marks settled and the policy's tolerance writes off was not, "
                               "or one above the tolerance (or without a settlement flag) was. The flag, the "
                               "deduction and the 25.00 threshold are all public."),

    "RECEIPT_WRONG_UNAPPLIED": ((AUTHORITY_ADVICE, AUTHORITY_STATEMENT, AUTHORITY_POLICY),
                                "Applications and write-offs are right and the unapplied residue is not: the part "
                                "of the payment the advice does not name, which the policy leaves unapplied rather "
                                "than carrying to the lower rungs, is the statement amount less the advice's "
                                "lines — two public figures."),

    "RECEIPT_MISSING": ((AUTHORITY_STATEMENT,),
                        "The statement shows a customer credit — ACH IN or CHECK naming a customer of "
                        "customers.csv — and the register carries no record with its date:reference key. The "
                        "row is public; the receipt_id is formed from it alone."),

    "RECEIPT_FABRICATED": ((AUTHORITY_STATEMENT,),
                           "A record whose receipt_id matches no customer-credit row of the statement. The "
                           "statement is the only source of receipts, it is public, and an id it does not print "
                           "is an id no evidence carries — priced as fabricated_receipt."),

    # ---- invoices ----------------------------------------------------------
    "INVOICE_EXACT": ((AUTHORITY_OPEN_ITEMS, AUTHORITY_LEDGER),
                      "The row equals the truth on customer, period_basis and the four outcome columns. The "
                      "customer and period basis come from open_items.csv for a carried invoice and from the "
                      "in-period sale entry for one raised in the month; the outcome columns are the fold of the "
                      "receipts and credit notes over them."),

    "INVOICE_WRONG_CUSTOMER": ((AUTHORITY_OPEN_ITEMS, AUTHORITY_LEDGER, AUTHORITY_CUSTOMERS),
                               "The row names a customer other than the invoice's: open_items.csv prints the "
                               "customer of a carried invoice, the sale entry's payee names it for an in-month "
                               "one, and customers.csv is the list of names. All three are public."),

    "INVOICE_WRONG_BASIS": ((AUTHORITY_OPEN_ITEMS, AUTHORITY_LEDGER),
                            "The row's period_basis is not the balance entering the period — typically the "
                            "face value (original_amount) printed for a part-paid carried invoice instead of its "
                            "open_balance, or a net amount instead of the sale's gross. Both columns of "
                            "open_items.csv and the sale's receivables debit are public."),

    "INVOICE_INEXACT": ((AUTHORITY_ADVICE, AUTHORITY_REFERENCE, AUTHORITY_CREDIT_NOTES, AUTHORITY_POLICY),
                        "Customer and period basis are right and an outcome column is not: applied_total, "
                        "credited, written_off or remaining. The row is the fold of every receipt and credit "
                        "note over the invoice, so the defect is one of the receipt or credit-note defects above "
                        "seen from the invoice's side."),

    "INVOICE_MISSING": ((AUTHORITY_OPEN_ITEMS, AUTHORITY_LEDGER),
                        "An invoice of the register — a carried row of open_items.csv or an in-period sale of "
                        "the ledger — has no closing_open_items entry. Every invoice is listed, zero rows "
                        "included, so an absent row is an absent invoice."),

    "INVOICE_FABRICATED": ((AUTHORITY_OPEN_ITEMS, AUTHORITY_LEDGER),
                           "An invoice id in no register row and no in-period sale: nothing public carries it. "
                           "Priced as fabricated_invoice wherever it appears — a row, a receipt's application or "
                           "a credit note's — because an id no evidence carries is the same offence anywhere."),

    # ---- credit notes ------------------------------------------------------
    "CREDIT_EXACT": ((AUTHORITY_CREDIT_NOTES, AUTHORITY_POLICY),
                     "The record's canonical applied mapping and unapplied residue equal the truth: the note's "
                     "invoice, gross and date are in credit_notes.csv and the credit policy — up to the named "
                     "invoice's open balance, excess by invoice date then number, remainder unapplied — is in "
                     "policy.md."),

    "CREDIT_WRONG_INVOICES": ((AUTHORITY_CREDIT_NOTES, AUTHORITY_POLICY),
                              "The record applies the note to an invoice the truth does not credit at all: the "
                              "wrong invoice, or the wrong customer's. The note names its invoice in "
                              "credit_notes.csv and the policy names where any excess goes."),

    "CREDIT_WRONG_SPLIT": ((AUTHORITY_CREDIT_NOTES, AUTHORITY_POLICY),
                           "Every invoice the record names is one the truth credits, and the amounts or the "
                           "unapplied residue differ — the excess held unapplied instead of routed, the note "
                           "applied in full to an invoice whose open balance is smaller. Distinguished from "
                           "naming the wrong invoice; the split rule is public."),

    "CREDIT_MISSING": ((AUTHORITY_CREDIT_NOTES,),
                       "A credit note of credit_notes.csv has no record. The file is public and the note's "
                       "gross must be conserved somewhere — applied or unapplied — so an ignored note cannot "
                       "hide inside applied_total either; the register's credited column is separate."),

    "CREDIT_FABRICATED": ((AUTHORITY_CREDIT_NOTES,),
                          "A record whose credit_note_id matches no credit note of the evidence. It has no gross "
                          "to conserve, so the conservation identity does not reach it; it is priced as "
                          "fabricated_credit_note instead, the same price as any invented id."),

    # ---- the ties ----------------------------------------------------------
    "AR_TIE_OK": ((AUTHORITY_OPEN_ITEMS, AUTHORITY_STATEMENT, AUTHORITY_CREDIT_NOTES),
                  "sum(remaining) - sum(unapplied_amount), receipts and credit notes alike, equals the expected "
                  "closing receivables: the opening register plus the in-period sales less the statement's "
                  "customer credits, the credit notes' gross and the write-offs — every term public."),

    "AR_TIE_CONTRADICTS": ((AUTHORITY_OPEN_ITEMS, AUTHORITY_STATEMENT, AUTHORITY_CREDIT_NOTES),
                           "The register does not roll forward to the closing receivables the public evidence "
                           "determines. Not a degenerate test: Case 5's golden carries a 30.00 unapplied residue "
                           "and ties at sum(remaining) - 30.00, so a register on the wrong side of the tie is one "
                           "that dropped or invented a movement."),

    "WRITEOFF_TIE_OK": ((AUTHORITY_ADVICE, AUTHORITY_POLICY),
                        "The rows' written_off column sums to the period's write-off movement, which the advice "
                        "flags and deductions together with the policy's tolerance determine. The receipts' "
                        "written_off items are held equal to this column by the writeoff_identity at the parse "
                        "boundary, so the tie reads one number."),

    "WRITEOFF_TIE_CONTRADICTS": ((AUTHORITY_ADVICE, AUTHORITY_POLICY),
                                 "The rows write off more or less than the advice and the tolerance authorise: "
                                 "a shortfall above 25.00 written off, a settled one at or below it left open, or "
                                 "a deduction the advice never claimed. Neither always-write-off nor "
                                 "never-write-off reproduces both of a case's deductions."),

    # ---- the artifact ------------------------------------------------------
    "APPLICATION_ABSENT": ((),
                           "EXCLUDED: no register was delivered. That is a state of the SUBMISSION — the tool was "
                           "never called, or its last stored revision was refused before storage — and no public "
                           "document can exhibit it. A submission without an application stays legal and scores "
                           "A = 0, the ledger reported diagnostically with no composite credit."),

    "APPLICATION_REJECTED": ((),
                             "EXCLUDED: the last stored register failed the parse boundary — schema, decimals, a "
                             "duplicated member or key, or one of the five accounting identities — and is a "
                             "rejected artifact, not a priced one. Internal contradiction is a property of the "
                             "delivered bytes; the evidence pack has no reading for a file that disagrees with "
                             "itself."),
}

APPLICATION_MAPPED_STATES = tuple(state for state, (authorities, _note) in APPLICATION_STATE_CONTRACT.items()
                                  if authorities)
APPLICATION_EXCLUDED_STATES = tuple(state for state, (authorities, _note) in APPLICATION_STATE_CONTRACT.items()
                                    if not authorities)


def authorities_for(state: str) -> tuple:
    """The public documents that decide an application state; empty when excluded."""
    return APPLICATION_STATE_CONTRACT[state][0]


def application_note_for(state: str) -> str:
    return APPLICATION_STATE_CONTRACT[state][1]
