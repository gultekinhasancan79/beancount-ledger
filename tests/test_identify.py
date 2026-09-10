"""Public-only identifiability over the new graph's public bytes.

Four things are proved, and the third is the one that makes the other three
worth anything.

    the shipped world is identifiable, and the repairs the checker finds are
    exactly the two planted rows — accepted for the right reason, not by an
    enumeration that found nothing;

    a variant built by editing the public TEXT only is rejected, and rejected
    *for the stated reason*: a test asserting `not unique` passes for a parse
    error, an empty enumeration or an unrelated complaint;

    the checker cannot see hidden identity. Its inputs are strings, it refuses
    anything else, and the module imports nothing from `schema`, `policy`,
    `project`, `derive` or `worlds`. That is asserted statically over the
    module's own source and dynamically over its globals, because a checker
    holding a recognition id would resolve the join it is supposed to prove a
    reader can resolve, and would certify every ambiguous world as unique;

    the two mutation kinds that are not omissions — a booked entry carrying
    the wrong vector, and an entry the books carry twice — are reported as a
    wrong-amount candidate and a duplicate candidate, each uniquely.

Since the matching rewrite a second block of fixtures carries
the weight the generator cannot: the generator draws every statement amount
distinct and every reference once, so 30/30 green seeds would stay green even
if the checker leaned on those conveniences. The fixtures below take them
away — repeated amounts, repeated counterparties, two bank fees in one month,
a reused invoice reference, a cheque issued last month and cleared in this
one, an exact reference pointing the wrong way — and each one names which of
the two verdicts the evidence supports and why.

One block of those fixtures carries the IDENTITY rule, which was corrected
after a reviewer refused its first form: a reference is a payment identifier
only where the public evidence declares it one (`remittance_advice.csv`'s
`payment_reference` column, a cheque the wording introduces, a bank trace id),
never because of its shape. The counterexamples the retracted shape rule
admitted are asserted here — an invoice list, a generic dated memo, two part
payments quoting one list — beside the positive case and the control that
isolates it: the same bytes with and without the advice that declares them.

The public files come from `derive_contract`, so what is checked is the bytes
the environment actually mounts, not a fixture that resembles them.

    python tests/test_identify.py
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import sys
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from beancount_ledger.graph import derive as DV  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402
from beancount_ledger.graph import project as PJ  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402
from repair_keys import master_names, planted_key  # noqa: E402

BANK = "Assets:Bank:Checking"
START, END = "2025-11-01", "2025-11-30"
PRIVATE_ID = re.compile(r"\b(rec|mov|event|party|doc|mut):[a-z0-9][a-z0-9\-]*\b")
STDLIB_ONLY = {"__future__", "csv", "io", "re", "dataclasses", "datetime", "decimal"}
FORBIDDEN = ("schema", "policy", "project", "derive", "worlds", "canonical", "beancount_ledger")


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:20]:
            print(f"      {line}")
    return ok


def public_files(plan=None) -> dict:
    """The bytes the agent is mounted, decoded. Never the bundle."""
    world, task = REGISTRY["bank_recon_001"]
    if plan is not None:
        task = dataclasses.replace(task, plan=plan)
    _, inputs = DV.derive_contract(world, task)
    return {name: data.decode("utf-8") for name, data in inputs.public_files}


def verdict_of(public: dict):
    return ID.check_identifiable(public, bank_account=BANK, period_start=START, period_end=END)


def key(repair) -> tuple:
    return (repair.kind, repair.date, repair.amount, repair.account)


def kinds(verdict) -> list:
    return sorted(r.kind for r in verdict.repairs)


# --------------------------------------------------------------------------
# editing the public TEXT, and only the text
# --------------------------------------------------------------------------

def statement_rows(public: dict) -> list:
    """The statement's movement rows as `(date, description, reference,
    debit, credit)`. The opening row is held separately by `restate`."""
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
    """A statement a bank could have printed: the rows in date order, the
    balance column walked forward from the opening balance the world already
    carries. The checker never reads the balance, so a fixture that got it
    wrong would still be rejected — for arithmetic rather than for the thing
    the fixture is about."""
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


def drop_entry(public: dict, header_prefix: str) -> dict:
    """Remove one ledger entry — its header line and its postings."""
    out, skipping = [], False
    for line in public[ID.LEDGER_FILE].splitlines():
        if line.startswith(header_prefix):
            skipping = True
            continue
        if skipping and (line.startswith(" ") or not line.strip()):
            if line.startswith(" "):
                continue
        skipping = False
        out.append(line)
    return {**public, ID.LEDGER_FILE: "\n".join(out) + "\n"}


def bank(amount: str) -> tuple:
    return (BANK, amount)


# --------------------------------------------------------------------------

def test_the_shipped_world_is_identifiable():
    """Unique, and unique because it found the two planted rows.

    The bank fee is the interesting half: the row names no counterparty at
    all, so the account can only come from the sentence in `policy.md` that
    puts bank charges in `Expenses:BankFees`. If the checker could not read
    that, it would have to reject — and asserting the account here is what
    stops the attribution rule from degenerating into "call it anything".
    """
    verdict = verdict_of(public_files())
    found = sorted(key(r) for r in verdict.repairs)
    want = sorted([
        ("missing_entry", "2025-11-26", D("4800.00"), "Assets:AR"),
        ("missing_entry", "2025-11-30", D("-85.00"), "Expenses:BankFees"),
    ])
    payers = {r.date: r.counterparty for r in verdict.repairs}
    ok = (verdict.unique and found == want
          and payers.get("2025-11-26") == "Harbor Freight Ltd" and payers.get("2025-11-30") is None
          and verdict.matched == 5 and len(verdict.outstanding) == 1
          and "1038" in verdict.outstanding[0])
    return check("the shipped world is identifiable and the repairs are exactly the two planted rows",
                 ok, f"{verdict}\nrepairs: {found}\nwant:    {want}\n"
                     f"matched {verdict.matched}, outstanding {verdict.outstanding}")


def test_the_outstanding_cheque_is_not_reported_as_a_difference():
    """Check 1038 is in the books and not on the November statement.

    A checker that treats every unmatched ledger movement as an error reports
    it as a third repair, and the world would fail a gate it should pass. The
    policy calls it a timing difference; so must this.
    """
    verdict = verdict_of(public_files())
    leaked = [r for r in verdict.repairs if r.date == "2025-11-28" or r.amount == D("-3500.00")]
    ok = verdict.unique and not leaked and len(verdict.outstanding) == 1
    return check("the outstanding cheque is an outstanding item, not a repair candidate", ok,
                 f"repairs: {[str(r) for r in verdict.repairs]}\noutstanding: {verdict.outstanding}")


def ambiguous_public() -> dict:
    """The shipped world, with the public TEXT edited and nothing else.

    The 26 November deposit loses its payer and its invoice reference, and a
    second deposit of the same amount lands the next day. Both are unrecorded,
    neither names a customer, and no policy sentence places them: crediting
    Harbor Freight and crediting Summit Wholesale are two different repaired
    ledgers, and so are the two dates. The balance column is kept honest so
    the fixture is a bank statement a bank could have printed — the checker
    does not read it, and a fixture that only broke arithmetic would be
    rejected for the wrong reason.
    """
    public = dict(public_files())
    out = []
    for line in public[ID.STATEMENT_FILE].splitlines():
        if line.startswith("2025-11-26,"):
            out.append("2025-11-26,DEPOSIT,,,4800.00,54630.00")
            out.append("2025-11-27,DEPOSIT,,,4800.00,59430.00")
        elif line.startswith("2025-11-30,"):
            out.append("2025-11-30,MONTHLY ACCOUNT SERVICE CHARGE,,85.00,,59345.00")
        else:
            out.append(line)
    public[ID.STATEMENT_FILE] = "\n".join(out) + "\n"
    return public


def test_the_ambiguous_variant_is_rejected_for_the_stated_reason():
    verdict = verdict_of(ambiguous_public())
    reason = verdict.reason
    attribution = reason.count("cannot be attributed from the public files") == 2
    indistinguishable = "no distinguishing reference" in reason
    return check("an unattributable pair of identical deposits is rejected, for attribution and for "
                 "indistinguishability", not verdict.unique and attribution and indistinguishable,
                 f"{verdict}\nambiguities: {verdict.ambiguities}")


def test_a_second_movement_of_one_amount_is_rejected():
    """The other ambiguity: one row, two ledger entries that are not twins.

    Two entries of −3,500.00 dated 10 November, one to rent and one to a
    premises deposit, and the single CHECK 1037 row could be either. Not a
    duplicate — the entries differ in narration and in the account they post
    to — so reporting it as one is exactly the mistake this case exists to
    catch. The twin quotes no document number on purpose: since the matching
    rewrite an entry that names *another* cheque is ruled out by the number
    rather than left to compete, which is the next test.
    """
    public = add_entries(public_files(), entry(
        "2025-11-10", "Cedar Property Group", "Premises deposit held",
        [("Assets:Prepayments", "3500.00"), bank("-3500.00")]))
    verdict = verdict_of(public)
    stated = "matches 2 different ledger movements" in verdict.reason
    return check("one statement row that two unlike ledger entries could answer is rejected",
                 not verdict.unique and stated, f"{verdict}")


def test_a_competing_entry_naming_another_cheque_is_not_a_competitor():
    """The same shape, decided: the twin quotes check 1038, the row is 1037.

    A cheque number is the identity of the instrument. An entry that names a
    different one is not the other half of this row however well the amount
    and the date line up, so the pairing is forced and the twin is reported
    on its own — here as a stranded entry, twenty days from the cut-off.
    """
    public = add_entries(public_files(), entry(
        "2025-11-10", "Cedar Property Group", "December rent prepaid, check 1038",
        [("Assets:Prepayments", "3500.00"), bank("-3500.00")]))
    verdict = verdict_of(public)
    stated = ("neither as an outstanding item" in verdict.reason
              and "matches 2 different ledger movements" not in verdict.reason)
    return check("an entry naming another cheque number does not compete for a numbered row",
                 not verdict.unique and stated, f"{verdict}")


def test_the_checker_cannot_see_hidden_identity():
    """Strings in, and a module that has no route to the graph.

    Static, over the source: every import is absolute and stdlib, so there is
    no `from .project import Bundle` to read a recognition id from. Dynamic,
    over the globals: nothing bound in the module comes from this package.
    And the entry point refuses a non-string value rather than coercing it,
    because a structured fact list is the shortcut this whole split exists to
    prevent.
    """
    problems = []
    source = Path(ID.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                problems.append(f"relative import of {node.module!r} at line {node.lineno}")
            elif (node.module or "").split(".")[0] not in STDLIB_ONLY:
                problems.append(f"imports {node.module!r}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in STDLIB_ONLY:
                    problems.append(f"imports {alias.name!r}")
    for word in FORBIDDEN:
        if re.search(rf"^\s*(from|import)\s+\S*{word}", source, re.MULTILINE):
            problems.append(f"an import line mentions {word!r}")
    foreign = [name for name, value in vars(ID).items()
               if getattr(value, "__module__", "") .startswith("beancount_ledger")
               and getattr(value, "__module__", "") != ID.__name__]
    if foreign:
        problems.append(f"module globals bound from the package: {foreign}")

    params = inspect.signature(ID.check_identifiable).parameters
    if list(params) != ["public", "bank_account", "period_start", "period_end", "tie_break"]:
        problems.append(f"signature is {list(params)}")
    if params["public"].annotation not in ("dict", "dict[str, str]", dict):
        problems.append(f"public is annotated {params['public'].annotation!r}")

    public = public_files()
    for bad, label in ((("a", "tuple", "of", "facts"), "a fact tuple"), (b"bytes", "bytes"), (None, "None")):
        try:
            ID.check_identifiable({**public, ID.LEDGER_FILE: bad}, bank_account=BANK,
                                  period_start=START, period_end=END)
            problems.append(f"accepted {label} as a view")
        except ID.PublicOnly:
            pass

    verdict = verdict_of(public)
    rendered = " ".join([verdict.reason, *(str(r) for r in verdict.repairs), *verdict.outstanding])
    leaks = sorted(set(PRIVATE_ID.findall(rendered)))
    if leaks:
        problems.append(f"the verdict quotes private id kinds {leaks}")
    if PRIVATE_ID.search(source):
        problems.append("the module source names a private id")
    return check("the checker reads text only: stdlib imports, no package globals, non-text refused, "
                 "no private id in or out", not problems, "\n".join(problems))


ALTER_OFFICE = PJ.AlterRecognition("x", "rec:office-2025-11", "transpose_digits", 0, "?")   # 420.00 -> 240.00
DUP_RENT = PJ.DuplicateRecognition("y", "rec:rent-2025-11", "?")


def test_the_alter_and_duplicate_kinds_are_identified():
    """A wrong vector and a doubled entry, from the bytes alone.

    The wrong amount is found because a movement of another amount shares the
    row's date and its counterparty — the pairing demands both, so the fee row
    two days from the outstanding cheque cannot be mistaken for one. The
    duplicate is found because two movements are indistinguishable in every
    field a reader can see and one bank row answers them: BOTH maximum
    matchings leave one copy over, both call it the same surplus, and a
    reading that is the same in every matching is a reading.
    """
    verdict = verdict_of(public_files(PJ.MutationPlan((ALTER_OFFICE, DUP_RENT))))
    wrong = [r for r in verdict.repairs if r.kind == "wrong_amount"]
    duplicate = [r for r in verdict.repairs if r.kind == "duplicate"]
    ok = (verdict.unique and len(verdict.repairs) == 2 and len(wrong) == 1 and len(duplicate) == 1
          and key(wrong[0]) == ("wrong_amount", "2025-11-18", D("-420.00"), "Expenses:Office")
          and wrong[0].booked_amount == D("-240.00")
          and key(duplicate[0]) == ("duplicate", "2025-11-10", D("-3500.00"), "Expenses:Rent")
          and duplicate[0].copies == 2
          and len(verdict.outstanding) == 1)
    return check("a transposed amount and a doubled entry are one wrong-amount and one duplicate candidate",
                 ok, f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}")


def test_every_planted_kind_is_seen_together():
    """All three kinds in one task, which is what a realistic month looks like.

    Two omissions, a wrong amount and a duplicate: four candidates, still one
    reading each. This is the case that would break a checker whose passes
    interfere — a wrong-amount pairing that stole the fee row, or a duplicate
    group that swallowed the outstanding cheque.
    """
    world, task = REGISTRY["bank_recon_001"]
    plan = PJ.MutationPlan(task.plan.mutations + (ALTER_OFFICE, DUP_RENT))
    verdict = verdict_of(public_files(plan))
    ok = (verdict.unique and kinds(verdict) == ["duplicate", "missing_entry", "missing_entry", "wrong_amount"]
          and len(verdict.outstanding) == 1)
    return check("two omissions, a wrong amount and a duplicate in one period are four unique candidates",
                 ok, f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}")


def test_the_reference_decides_across_a_clearing_float():
    """A cheque that floats past the amount-and-date window still matches.

    The design puts cheque numbers in the narration of cheque-settled payments
    precisely so this holds. Without the reference pass, a nine-day float
    turns a perfectly ordinary payment into a phantom repair and an equally
    phantom outstanding item, and a generated world would fail the gate for
    being realistic.
    """
    public = dict(public_files())
    rows, floated = [], "2025-11-19,CHECK 1037 CEDAR PROPERTY GROUP,1037,3500.00,,42250.00"
    for line in public[ID.STATEMENT_FILE].splitlines():
        rows.append(floated if line.startswith("2025-11-10,CHECK 1037") else line)
    public[ID.STATEMENT_FILE] = "\n".join(rows) + "\n"
    ledger = public[ID.LEDGER_FILE].replace('"November office rent"', '"November office rent, check 1037"')
    public[ID.LEDGER_FILE] = ledger
    verdict = verdict_of(public)
    ok = verdict.unique and len(verdict.repairs) == 2 and all(r.kind == "missing_entry" for r in verdict.repairs)
    return check("a quoted cheque number matches the payment across a nine-day clearing float", ok,
                 f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}")


def test_a_stranded_ledger_movement_far_from_the_cut_off_is_not_outstanding():
    """The rule has to be able to fail, or "outstanding" excuses everything.

    The same unmatched entry moved to the fourth of the month is not a timing
    difference — nothing plausible leaves a payment uncleared for twenty-six
    days and then reconciles — so it must be reported rather than waved away.
    """
    public = dict(public_files())
    public[ID.LEDGER_FILE] = public[ID.LEDGER_FILE].replace(
        '2025-11-28 * "Cedar Property Group" "December rent prepaid, check 1038"',
        '2025-11-04 * "Cedar Property Group" "December rent prepaid, check 1038"')
    verdict = verdict_of(public)
    stated = "neither as an outstanding item" in verdict.reason
    return check("an unmatched ledger movement far from the cut-off is reported, not excused",
                 not verdict.unique and stated, f"{verdict}")


# --------------------------------------------------------------------------
# the conveniences the generator happens to provide, taken away
# --------------------------------------------------------------------------

def two_receipts_of_one_amount(reference: str = "", quoted: str = "",
                               row_description: str = "ACH IN DEPOSIT") -> dict:
    """Two customer receipts of 2,500.00 in the books, one deposit on the
    statement. `reference`/`quoted` optionally give the row a reference and
    put it in one entry's narration; `row_description` is what the bank
    printed, which is what tells a cheque number from an invoice number."""
    public = public_files()
    # Both entries carry the row's own day. The bank processes a transaction
    # on or after the day it happens (`## Dates`), so a receipt recorded the
    # day AFTER the deposit could not be that deposit and would not compete
    # at all — the ambiguity this fixture is about needs two entries the row
    # could actually be.
    public = add_entries(
        public,
        entry("2025-11-20", "Harbor Freight Ltd", f"Customer payment on account{quoted}",
              [bank("2500.00"), ("Assets:AR", "-2500.00")]),
        entry("2025-11-20", "Summit Wholesale", "Customer payment on account",
              [bank("2500.00"), ("Assets:AR", "-2500.00")]))
    rows = statement_rows(public) + [("2025-11-20", row_description, reference, "", "2500.00")]
    return restate(public, rows)


def test_two_receipts_of_one_amount_are_not_decidable_by_amount():
    """Repeated amounts: the convenience the generator provides, removed.

    Two receipts of the same amount, one anonymous deposit. Whichever the
    bank saw, the other is a deposit in transit — and the two readings name
    DIFFERENT entries as the one still outstanding, so the repaired
    reconciliation is not the same document. A checker that took the first
    tie would call this unique and be wrong.
    """
    verdict = verdict_of(two_receipts_of_one_amount())
    stated = "matches 2 different ledger movements" in verdict.reason
    return check("two ledger receipts of one amount answering one anonymous deposit are not decidable",
                 not verdict.unique and stated, f"{verdict}")


def test_an_invoice_number_does_not_decide_between_two_receipts_of_one_amount():
    """The same fixture with the invoice number the bank prints — and under
    the reference ontology that is NOT enough.

    `SI-1052` is quoted once across the statement, the archive and the bank
    movements of the ledger, so it was decisive until IDENTIFY_VERSION 7. It
    is an invoice id: it says which receivable the money applies to, and one
    receivable can be settled by several receipts, a refund and a deposit in
    transit. Both entries are 2,500.00 on the row's own day, so
    `## Matching the statement to the ledger` forces a settlement and is
    equally satisfied by either; `## Customer receipts` applies the deposit
    against SI-1052 and says nothing about which of two cash records the bank
    credited. Nothing public separates the two readings — they leave DIFFERENT
    receipts in transit — so the verdict is ambiguous.

    This is a deliberate contract change, not a regression: the previous
    expectation was that a globally unique invoice number decides a pairing,
    which is the class of claim the reviewer refused.
    """
    verdict = verdict_of(two_receipts_of_one_amount("SI-1052", ", settling SI-1052"))
    stated = "matches 2 different ledger movements" in verdict.reason
    ok = not verdict.unique and stated and verdict.readings == 2
    return check("an invoice id quoted once still does not decide between two same-amount receipts: it "
                 "names the receivable, not the payment", ok, f"{verdict}")


def test_a_cheque_number_does_decide_between_two_receipts_of_one_amount():
    """The other half of the ontology, on the identical fixture.

    Swap the invoice number for a cheque number the bank prints as a cheque
    row (`CHECK 4210 ...`, reference `4210`) and one entry quotes it. A cheque
    number is an INSTRUMENT: it names one cash movement, so a globally unique
    one decides both halves — the row is answered by that entry, and that
    entry is not free to answer anything else. One reading, the two planted
    repairs, and the unreferenced receipt is a deposit in transit.

    The only difference between this and the test above is the ROLE of the
    reference. That is the whole point of typing them.
    """
    public = two_receipts_of_one_amount("4210", ", check 4210", "CHECK 4210 HARBOR FREIGHT LTD")
    verdict = verdict_of(public)
    rows = ID.statement_rows(public[ID.STATEMENT_FILE], period_start=START, period_end=END)[0]
    row = next(r for r in rows if r.reference == "4210")
    facts = ID._evidence(public, BANK, START, END).facts_by_row[row.index]
    ok = (verdict.unique and kinds(verdict) == ["missing_entry", "missing_entry"]
          and any("2500.00" in item for item in verdict.outstanding)
          and facts.ref_role == ID.REF_INSTRUMENT and facts.decisive)
    return check("a cheque number quoted once DOES decide between the same two receipts: an instrument "
                 "names one cash movement", ok,
                 f"{verdict}\nrole={facts.ref_role} decisive={facts.decisive}\noutstanding: {verdict.outstanding}")


def two_partial_receipts_on_one_invoice(instrument: bool = False) -> dict:
    """One sales invoice, two PART payments of the
    same amount, one of them still in transit, and a bank row for that amount.

    The books carry 1,500.00 received on 20 November and 1,500.00 received on
    22 November, both `Part payment received on SI-1044`. The bank credits
    1,500.00 on 23 November — inside the ACH window of both, and on or after
    both, so `## Dates` rules out neither. Both are inside the outstanding
    window and more than `ALTER_WINDOW_DAYS` from the shipped statement's own
    26 November SI-1044 row, so the only question the fixture asks is which of
    the two the 23 November credit is. The shipped statement already carries
    that second SI-1044 row (the planted 4,800.00 omission), so the invoice id
    is quoted twice on the documents side as well.

    `instrument=True` gives each receipt its own cheque number and prints the
    row as a cheque row, which is the same topology with an identifying
    reference instead of an applying one.
    """
    first = ", check 4210" if instrument else ""
    second = ", check 4211" if instrument else ""
    public = add_entries(
        public_files(),
        entry("2025-11-20", "Harbor Freight Ltd", f"Part payment received on SI-1044{first}",
              [bank("1500.00"), ("Assets:AR", "-1500.00")]),
        entry("2025-11-22", "Harbor Freight Ltd", f"Part payment received on SI-1044{second}",
              [bank("1500.00"), ("Assets:AR", "-1500.00")]))
    row = (("2025-11-23", "CHECK 4210 HARBOR FREIGHT LTD", "4210", "", "1500.00") if instrument
           else ("2025-11-23", "ACH IN HARBOR FREIGHT LTD", "SI-1044", "", "1500.00"))
    return restate(public, statement_rows(public) + [row])


def test_two_partial_receipts_on_one_invoice_are_not_decided_by_the_invoice():
    """The strict verdict: AMBIGUOUS, and no other public rule decides it.

    Which rules were asked, and what each of them says:

    `## Matching the statement to the ledger` — a row and an entry of the same
    amount and the same counterparty inside the clearing window are one
    transaction. Both entries satisfy it exactly and equally, so it forces the
    row to be settled by ONE of them and does not say which.

    `## Customer receipts` — where the deposit reference identifies a sales
    invoice, it is applied against that invoice. Both entries are already
    applied against SI-1044, so the sentence is satisfied by both readings.

    `## Dates` — the bank processes on or after the day it happens. Both
    entries are dated before the row, so neither is excluded.

    `## Deposits in transit` — whichever entry is not the row's is cash the
    statement has not yet shown, which both readings say of the other one.

    The two readings therefore differ only in WHICH receipt is still in
    transit, which is a different reconciliation, and the invoice id — the
    one thing that would separate them — names the receivable rather than the
    payment. Ambiguous is the answer, and `mint` refuses a world of this shape.
    """
    verdict = verdict_of(two_partial_receipts_on_one_invoice())
    stated = "matches 2 different ledger movements" in verdict.reason
    differ = "maximum readings whose repairs differ" in verdict.reason
    ok = not verdict.unique and stated and differ and verdict.readings == 2
    return check("two partial receipts against one invoice, one in transit: the shared invoice id does not "
                 "choose, and no other public rule does either", ok, f"{verdict}")


def test_the_same_two_receipts_are_decided_by_their_cheque_numbers():
    """The same topology with instruments: 4210 clears, 4211 is outstanding.

    Each receipt names its own cheque, the bank prints 4210, and 4211 appears
    nowhere on the statement. The instrument decides the pairing and the
    conflict rule keeps the 4211 entry out of it, so there is one reading:
    nothing extra is missing and the second receipt is a timing difference.
    """
    verdict = verdict_of(two_partial_receipts_on_one_invoice(instrument=True))
    ok = (verdict.unique and kinds(verdict) == ["missing_entry", "missing_entry"]
          and any("4211" in item for item in verdict.outstanding)
          and not any("4210" in item for item in verdict.outstanding))
    return check("the same two receipts, each naming its own cheque: the instrument decides and the "
                 "unpresented one is outstanding", ok, f"{verdict}\noutstanding: {verdict.outstanding}")


def test_the_reference_ontology_classifies_every_shape_the_worlds_publish():
    """The ontology as a table, asserted rather than described.

    An invoice or purchase-invoice code is a DOCUMENT whatever text carries
    it, and so is a LIST of them; a number introduced by the word check is an
    INSTRUMENT and the same number without it is UNKNOWN; text with no
    reference-shaped token at all is MEMO. A bank trace id is classified as an
    instrument so that a world which starts printing one gets the instrument
    rules rather than the unknown ones.

    The last block is the identity rule: SHAPE decides nothing, in either
    direction. `GR PAYRUN 0428` and `APRIL 2026` have the same shape —
    several words, one carrying a digit — and neither is an instrument until
    a mounted advice DECLARES it a payment reference. Once one does, BOTH are:
    the dated memo is a poor reference and a pack should not print one, but a
    customer has stated that a payment of theirs carries it, and refusing that
    because the string reads badly would be the shape rule again with its sign
    flipped. Uniqueness is what stops such a reference deciding what it should
    not, and that is tested where it lives.

    An invoice list is refused even when an advice declares it, because a list
    names receivables and two partial payments may quote it — and so is a list
    with one non-invoice token appended, which is the shape a pack would reach
    for to get a list declared. The only identity such a column can present is
    a bank trace id it also prints, and then the identity is that token alone.
    """
    declared = frozenset({"GRPAYRUN0428", "APRIL2026", "SI1044SI1052", "SI1044",
                          "SI1044SI1052XZ", "TRC0428442SI1044SI1052"})
    cases = [
        ("SI-1044", "ACH IN HARBOR FREIGHT LTD SI-1044", ID.REF_DOCUMENT, frozenset()),
        ("PI-2240", "Payment of purchase invoice PI-2240", ID.REF_DOCUMENT, frozenset()),
        ("si 1044", "settling si 1044", ID.REF_DOCUMENT, frozenset()),
        ("1037", "CHECK 1037 CEDAR PROPERTY GROUP", ID.REF_INSTRUMENT, frozenset()),
        ("1037", "November office rent, check 1037", ID.REF_INSTRUMENT, frozenset()),
        ("1037", "Deposit slip 1037", ID.REF_UNKNOWN, frozenset()),
        ("TRACE0284471", "ACH IN TRACE0284471", ID.REF_INSTRUMENT, frozenset()),
        ("BX-99", "Batch BX-99", ID.REF_UNKNOWN, frozenset()),
        ("", "Office supplies", ID.REF_MEMO, frozenset()),
        # the shape that used to be an instrument, undeclared and declared
        ("GR PAYRUN 0428", "ACH IN HARBOR FREIGHT LTD GR PAYRUN 0428", ID.REF_UNKNOWN, frozenset()),
        ("GR PAYRUN 0428", "ACH IN HARBOR FREIGHT LTD GR PAYRUN 0428", ID.REF_INSTRUMENT, declared),
        ("APRIL 2026", "ACH IN HARBOR FREIGHT LTD APRIL 2026", ID.REF_UNKNOWN, frozenset()),
        ("APRIL 2026", "ACH IN HARBOR FREIGHT LTD APRIL 2026", ID.REF_INSTRUMENT, declared),
        # an invoice list: document evidence, declared or not
        ("SI-1044 SI-1052", "ACH IN HARBOR FREIGHT LTD SI-1044 SI-1052", ID.REF_DOCUMENT, frozenset()),
        ("SI-1044 SI-1052", "ACH IN HARBOR FREIGHT LTD SI-1044 SI-1052", ID.REF_DOCUMENT, declared),
        ("SI-1044", "ACH IN HARBOR FREIGHT LTD SI-1044", ID.REF_DOCUMENT, declared),
        # a list with one non-invoice token appended is not promoted either:
        # the bar is "any word is an invoice id", not "every word is"
        ("SI-1044 SI-1052 XZ", "ACH IN HARBOR FREIGHT LTD SI-1044 SI-1052 XZ", ID.REF_UNKNOWN, frozenset()),
        ("SI-1044 SI-1052 XZ", "ACH IN HARBOR FREIGHT LTD SI-1044 SI-1052 XZ", ID.REF_UNKNOWN, declared),
        # the bank's own trace, printed beside the payer's invoice list — the
        # identity is the trace token, declared or not
        ("TRC0428442 SI-1044 SI-1052", "ACH IN HARBOR FREIGHT LTD TRC0428442 SI-1044 SI-1052",
         ID.REF_INSTRUMENT, frozenset()),
        ("TRC0428442 SI-1044 SI-1052", "ACH IN HARBOR FREIGHT LTD TRC0428442 SI-1044 SI-1052",
         ID.REF_INSTRUMENT, declared),
    ]
    problems = [f"{token!r} in {text!r} (evidenced={sorted(seen)}): "
                f"{ID.reference_role(token, text, evidenced=seen)} != {want}"
                for token, text, want, seen in cases
                if ID.reference_role(token, text, evidenced=seen) != want]
    if set(ID.REFERENCE_ROLES) != {ID.REF_INSTRUMENT, ID.REF_DOCUMENT, ID.REF_MEMO, ID.REF_UNKNOWN}:
        problems.append(f"the declared role set is {ID.REFERENCE_ROLES}")
    return check("every reference shape the worlds publish classifies to its declared role, and an "
                 "instrument identity comes from what the evidence declares rather than from the shape",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# the identity rule: a payment identifier is EVIDENCED, never inferred from
# the shape of the string (reviewer decision 5, round 13)
# --------------------------------------------------------------------------

ADVICE_HEADER = ("remittance_id,customer,remittance_date,payment_method,payment_reference,payment_amount,"
                 "invoice_id,amount_paid,settles_invoice,deduction_amount,note\n")


def advice_rows(*rows: tuple) -> str:
    """A `remittance_advice.csv` declaring `(remittance_id, reference)` pairs.

    Only the two columns this checker reads carry weight; the rest is filled
    so the file is what the family actually mounts rather than a stub shaped
    to the assertion.
    """
    body = "".join(f"{remittance_id},Harbor Freight Ltd,2025-11-23,ACH,{reference},1500.00,"
                   f"SI-1044,1500.00,yes,0.00,\n" for remittance_id, reference in rows)
    return ADVICE_HEADER + body


def two_partial_payments(reference: str, advice: str | None = None, *, quoted_by: tuple = (2,)) -> dict:
    """Two part payments of 1,500.00 in the books and one bank credit for that
    amount carrying `reference`.

    20 and 22 November, both `Part payment received on SI-1044`, both from
    Harbor Freight Ltd; the bank credits 1,500.00 on the 23rd. Whichever
    payment the bank credited, the other is a deposit in transit, and the two
    readings name different entries as the one outstanding. Only something
    that identifies ONE cash movement can choose between them.

    `quoted_by` says which of the two entries quote the reference in their
    narrations. The second alone by default, which is the shape an identity
    can single a payment out of; `(1, 2)` is two part payments quoting one
    reference, which is what an invoice list is actually like — the customer
    is paying the same two invoices twice over.

    `advice`, when given, is mounted as `remittance_advice.csv`.
    """
    def narration(which: int) -> str:
        base = "Part payment received on SI-1044"
        return f"{base}, {reference}" if which in quoted_by else base

    public = add_entries(
        public_files(),
        entry("2025-11-20", "Harbor Freight Ltd", narration(1),
              [bank("1500.00"), ("Assets:AR", "-1500.00")]),
        entry("2025-11-22", "Harbor Freight Ltd", narration(2),
              [bank("1500.00"), ("Assets:AR", "-1500.00")]))
    public = restate(public, statement_rows(public)
                     + [("2025-11-23", "ACH IN HARBOR FREIGHT LTD", reference, "", "1500.00")])
    return public if advice is None else {**public, ID.REMITTANCE_FILE: advice}


def identity_facts(public: dict, reference: str):
    rows = ID.statement_rows(public[ID.STATEMENT_FILE], period_start=START, period_end=END)[0]
    row = next(r for r in rows if r.reference == reference)
    return ID._evidence(public, BANK, START, END).facts_by_row[row.index]


def test_an_evidenced_unique_payment_identifier_is_decisive():
    """The positive case, and the control that isolates the evidence.

    `HF PAYRUN 1123` is a payment reference because a mounted remittance
    advice says so — customer, method and reference, the same column the
    family binds an advice by. It is quoted by one bank row and by one bank
    movement, so it is decisive: the row is answered by the entry that quotes
    it, the other part payment is a deposit in transit, and one reading
    survives.

    The control is the identical pack with the advice file removed. Nothing
    about the string changed; the rule reads UNKNOWN, nothing is decisive, and
    the two readings come back. That difference is the whole rule.
    """
    problems = []
    reference = "HF PAYRUN 1123"
    declared = two_partial_payments(reference, advice_rows(("RA-1123-HF", reference)))
    facts = identity_facts(declared, reference)
    verdict = verdict_of(declared)
    if facts.ref_role != ID.REF_INSTRUMENT or not facts.decisive or reference not in facts.presents:
        problems.append(f"declared: role {facts.ref_role}, decisive {facts.decisive}, presents {facts.presents}")
    if not verdict.unique or verdict.readings != 1:
        problems.append(f"declared: {verdict.readings} readings: {verdict.reason[:200]}")
    if not any("1500.00" in item for item in verdict.outstanding):
        problems.append(f"declared: the unquoted part payment is not outstanding: {verdict.outstanding}")
    bare = two_partial_payments(reference)
    facts = identity_facts(bare, reference)
    verdict = verdict_of(bare)
    if facts.ref_role != ID.REF_UNKNOWN or facts.decisive or facts.presents:
        problems.append(f"undeclared: role {facts.ref_role}, decisive {facts.decisive}, presents {facts.presents}")
    if verdict.unique or verdict.readings != 2:
        problems.append(f"undeclared: unique {verdict.unique}, {verdict.readings} readings")
    return check("an EVIDENCED, unique payment identifier decides between two part payments; the identical "
                 "pack without the advice that declares it does not", not problems, "\n".join(problems))


def test_an_identifier_two_advices_declare_is_no_identity():
    """Uniqueness, on the advice side.

    Two advices quoting one reference is exactly the case where the reference
    cannot say which payment a row is, so it is not admitted at all — the role
    falls back to UNKNOWN and the two readings stand. (The statement side of
    uniqueness is `test_a_reused_reference_falls_back_and_stays_ambiguous`.)
    """
    reference = "HF PAYRUN 1123"
    public = two_partial_payments(reference, advice_rows(("RA-1123-HF", reference),
                                                         ("RA-1124-HF", reference)))
    facts = identity_facts(public, reference)
    verdict = verdict_of(public)
    ok = facts.ref_role == ID.REF_UNKNOWN and not facts.decisive and not verdict.unique
    return check("a reference two advices declare is not a payment identity: the role falls back and the "
                 "world stays ambiguous", ok,
                 f"role={facts.ref_role} decisive={facts.decisive}\n{verdict}")


def test_an_invoice_list_is_document_evidence_and_decides_nothing():
    """The counterexample the shape rule admitted, at the verdict level.

    `SI-1044 SI-1052` is two or more words with a digit in them, which is what
    the retracted `_payment_reference_words` called an instrument. It is an
    invoice list: it says which receivables the money applies to, and two
    partial payments may quote the same one. So the role is DOCUMENT, the row
    presents nothing, and the two readings — which part payment the bank
    credited, which is still in transit — both survive.

    An advice declaring the list as its `payment_reference` does not change
    that. A pack cannot promote a list of receivables to an identity by
    naming it, which is why Case 2 of the cash family was given a bank trace
    id instead of having the rule loosened for it.

    AND NEITHER DOES APPENDING A TOKEN. `SI-1044 SI-1052 XZ` was the hole in
    the first version of this correction: the refusal fired only where EVERY
    word was invoice-shaped, so one junk token on the end put a list of
    receivables back on the instrument path, declared it, and decided this
    very pack. The test is now "any word is an invoice id", and the third
    label below is that counterexample held to two readings. It is checked
    here rather than only in the ontology table because the claim that was
    wrong was about what a PACK can do, and only the verdict shows that.
    """
    problems = []
    for reference in ("SI-1044 SI-1052", "SI-1044 SI-1052 XZ"):
        # the list alone is DOCUMENT evidence; the list with a junk token
        # appended is not even that, since it is no longer a list of invoice
        # ids — either way nothing is decisive and nothing is presented
        want_role = ID.REF_DOCUMENT if reference == "SI-1044 SI-1052" else ID.REF_UNKNOWN
        for label, advice in (("bare", None), ("declared", advice_rows(("RA-1123-HF", reference)))):
            public = two_partial_payments(reference, advice, quoted_by=(1, 2))
            facts = identity_facts(public, reference)
            verdict = verdict_of(public)
            where = f"{reference!r} {label}"
            if facts.ref_role != want_role or facts.decisive or facts.presents:
                problems.append(f"{where}: role {facts.ref_role}, decisive {facts.decisive}, "
                                f"presents {facts.presents}")
            if verdict.unique or verdict.readings != 2:
                problems.append(f"{where}: unique {verdict.unique}, {verdict.readings} readings: "
                                f"{verdict.reason[:200]}")
    return check("an invoice list is document evidence and decides nothing — declared by an advice or not, and "
                 "with a non-invoice token appended or not — so two part payments quoting one stay two "
                 "readings", not problems, "\n".join(problems))


def test_a_generic_dated_memo_is_not_a_payment_identity():
    """The other counterexample: `APRIL 2026`.

    Two words, one carrying a digit, so the retracted shape rule made it an
    instrument that could dominate a pairing and refuse a deposit in transit.
    It is a memo naming a month. No advice declares it, so it is UNKNOWN:
    supporting evidence with no hard prune, which is what an unrecognised code
    has to be.

    THE DECLARED HALF, asserted rather than left implicit. An advice that
    names `APRIL 2026` in `payment_reference` makes it an identity, and this
    test says so out loud instead of covering only the undeclared case and
    leaving the other to be discovered. That is not a leak in the rule, it is
    the rule: the reviewer's criterion is "explicitly evidenced", and a
    customer has explicitly said a payment of theirs carries that reference. A
    pack printing so poor a reference is an authoring problem, and it is
    caught by uniqueness — a second payment quoting `APRIL 2026`, on either
    side, drops it again — not by the checker second-guessing the string. The
    alternative is to re-derive an identity from appearance, which is the
    withdrawn rule wearing the other sign.
    """
    problems = []
    reference = "APRIL 2026"
    public = two_partial_payments(reference)
    facts = identity_facts(public, reference)
    verdict = verdict_of(public)
    if facts.ref_role != ID.REF_UNKNOWN or facts.decisive or facts.presents:
        problems.append(f"undeclared: role {facts.ref_role}, decisive {facts.decisive}, "
                        f"presents {facts.presents}")
    if verdict.unique or verdict.readings != 2:
        problems.append(f"undeclared: unique {verdict.unique}, {verdict.readings} readings: "
                        f"{verdict.reason[:200]}")
    declared = two_partial_payments(reference, advice_rows(("RA-1123-HF", reference)))
    facts = identity_facts(declared, reference)
    verdict = verdict_of(declared)
    if facts.ref_role != ID.REF_INSTRUMENT or not facts.decisive:
        problems.append(f"declared: role {facts.ref_role}, decisive {facts.decisive}")
    if not verdict.unique or verdict.readings != 1:
        problems.append(f"declared: unique {verdict.unique}, {verdict.readings} readings")
    # and uniqueness, not appearance, is the thing that takes it away again
    reused = two_partial_payments(reference, advice_rows(("RA-1123-HF", reference),
                                                         ("RA-1124-HF", reference)))
    facts = identity_facts(reused, reference)
    if facts.ref_role != ID.REF_UNKNOWN or facts.decisive:
        problems.append(f"declared twice: role {facts.ref_role}, decisive {facts.decisive}")
    return check("a generic dated memo NO ADVICE DECLARES is not a payment identity: UNKNOWN, not decisive, "
                 "presenting nothing — while one an advice does declare is an identity, deliberately, and "
                 "loses it to a second declaration rather than to how it reads",
                 not problems, "\n".join(problems))


def test_the_advice_file_is_read_for_the_reference_column_and_nothing_else():
    """The blast radius of mounting `remittance_advice.csv`.

    The checker reads one column of it. A malformed file, a file whose
    `payment_reference` column is empty, and a file naming references no row
    quotes all leave every verdict where it was — and a legacy pack, which
    mounts no advice at all, declares nothing, which is why the 95 shipped
    tasks cannot move under this rule.
    """
    problems = []
    base = two_partial_payments("HF PAYRUN 1123")
    baseline = verdict_of(base)
    for label, text in (("malformed", 'remittance_id,customer\n"unclosed,'),
                        ("empty column", ADVICE_HEADER + "RA-1,Harbor Freight Ltd,2025-11-23,ACH,,1500.00,"
                                                         "SI-1044,1500.00,yes,0.00,\n"),
                        ("another reference", advice_rows(("RA-1", "SB PAYRUN 0007")))):
        verdict = verdict_of({**base, ID.REMITTANCE_FILE: text})
        if (verdict.unique, verdict.readings) != (baseline.unique, baseline.readings):
            problems.append(f"{label}: {verdict.unique}/{verdict.readings} != "
                            f"{baseline.unique}/{baseline.readings}")
    if ID._evidenced_payment_identifiers({}) != frozenset():
        problems.append("a pack with no advice file declares something")
    if ID._evidenced_payment_identifiers({ID.REMITTANCE_FILE: advice_rows(("RA-1", "HF PAYRUN 1123"))}) \
            != frozenset({"HFPAYRUN1123"}):
        problems.append("the declared set is not the normalised payment_reference column")
    return check("the advice file is read for `payment_reference` and nothing else: malformed, empty or "
                 "irrelevant advices move no verdict, and a pack without one declares nothing",
                 not problems, "\n".join(problems))


# The corpus the two narrowness claims are measured over, and the ONLY thing
# they are claimed over: every reference shape these worlds print or were
# argued about, on the surfaces a reference is read off — the column alone, an
# ACH row, a cheque row printing the column, and a cheque row printing the
# number JOINED while the column prints it split (`CHECK 2291` beside a column
# reading `22 91`).
#
# Three shapes were added when a verifier showed that a clause measured here
# was being asserted as a universal: `22 91` and `TRC 0428442` are multi-word
# references the evidenced rule keeps and neither is a column printing a
# separate trace token, which the changelog used to say was the only kind
# kept; `CASH` is a single token carrying no digit, which an advice may
# declare and which nothing in this file used to quote or count. No world
# prints any of the three. That is the point: a claim measured over the shapes
# the worlds happen to print is a claim about those shapes, and either the
# corpus grows or the sentence says so.
IDENTITY_CORPUS = ("SI-3104 SI-3102", "SI-1044 SI-1052 XZ", "APRIL 2026", "GR PAYRUN 0428",
                   "GR PAYRUN 0410", "TRC0428442 SI-3104 SI-3102", "TRACE0284471 APRIL 2026",
                   "TRC0428442", "TRC 0428442", "SI-3104", "PI-2240", "2291", "22 91", "1037",
                   "0428442", "PAY RUN", "CASH", "BX-99", "")
IDENTITY_SURFACES = ("{ref}", "ACH IN GANNET RIGGING INC {ref}", "CHECK {ref} CEDAR PROPERTY GROUP",
                     "CHECK 2291 CEDAR PROPERTY GROUP {ref}")


def withdrawn_shape_role(reference: str, text: str) -> str:
    """RULE 1, the withdrawn shape rule, re-implemented from the revision that
    retired it (`identify.py` at 8fa99b3^).

    In full, in its own order: a cheque number the wording introduces, else an
    invoice-shaped WHOLE column is a document, else a bank trace id, else "two
    or more whitespace-separated words, at least one carrying a digit" is an
    INSTRUMENT. It lives in the test because the module no longer carries it
    and the compatibility claim is a claim about BOTH rules — asserting it
    against only the surviving one would be assuming what it states.
    """
    norm = ID._norm_ref(reference)
    if not norm:
        return ID.REF_MEMO
    if norm in ID._instrument_tokens(text):
        return ID.REF_INSTRUMENT
    if ID._DOCUMENT_SYNTAX.match(norm):
        return ID.REF_DOCUMENT
    if ID._TRACE_SYNTAX.match(norm):
        return ID.REF_INSTRUMENT
    words = tuple(w for w in (ID._norm_ref(t) for t in ID._TOKEN.findall(reference or "")) if w)
    if len(words) >= 2 and any(any(ch.isdigit() for ch in w) for w in words):
        return ID.REF_INSTRUMENT
    return ID.REF_UNKNOWN


def test_the_evidenced_rule_is_a_proper_subset_of_the_withdrawn_shape_rule():
    """The compatibility claim IDENTIFY_VERSION 7 rests on, both halves of it
    measured — and one half of it corrected here.

    On a pack that mounts no advice the evidenced rule reduces to
    cheque-or-trace, and the claim made for it is that its admitted set is a
    PROPER SUBSET of the withdrawn shape rule's. Two facts, and the module's
    changelog used to state the second one wrongly:

      * it admits NOTHING the shape rule refused. This is the half that
        carries the conclusion: no manifested verdict can move, because
        anything the current rule calls an instrument the old one called one
        too. It is asserted over the corpus and MEANT for every string — the
        rule is "declared, or the bank's own trace, or the row's own cheque
        wording", and each of those is a case the shape rule also admitted;
      * of the MULTI-WORD references the shape rule admitted, the ones it
        keeps are the ones the BANK or the ROW'S OWN WORDING vouches for. Over
        this corpus that is three kinds, and the sentence has now been wrong
        twice by naming fewer: first "it refuses every multi-word reference
        rule 1 admitted", falsified by Case 2's own printed reference
        (`TRC0428442 SI-3104 SI-3102`); then "it keeps exactly one kind, a
        column printing a single bank trace id", falsified by `TRC 0428442`
        (a trace printed with a space, an instrument by the whole column) and
        by `22 91` on a row reading `CHECK 2291` (a cheque the wording
        introduces). Both corrections are in the changelog and both shapes are
        in the corpus above; the kinds are counted here and claimed nowhere
        else. The containment is proper regardless, because the invoice list,
        the dated memo and the payer's addendum are all refused.
    """
    problems, kept, refused, admitted_new = [], [], [], []
    kinds_kept: dict = {}
    for reference in IDENTITY_CORPUS:
        for shape in IDENTITY_SURFACES:
            text = shape.format(ref=reference).strip()
            old, new = withdrawn_shape_role(reference, text), ID.reference_role(reference, text)
            if new == ID.REF_INSTRUMENT and old != ID.REF_INSTRUMENT:
                admitted_new.append((reference, text))
            if not ID._reference_words(reference) or old != ID.REF_INSTRUMENT:
                continue
            (kept if new == ID.REF_INSTRUMENT else refused).append((reference, text))
    if admitted_new:
        problems.append(f"the evidenced rule admits {len(admitted_new)} thing(s) the shape rule refused, "
                        f"so a promoted verdict could move: {admitted_new[:3]}")
    for reference, text in kept:
        norm = ID._norm_ref(reference)
        traces = [t for t in ID._ref_tokens(reference) if ID._TRACE_SYNTAX.match(t)]
        identity = ID._identity_reference(reference, text, frozenset())
        if len(traces) == 1 and identity == traces[0]:
            kind = "a column printing one bank trace id beside whatever else it carries"
        elif ID._TRACE_SYNTAX.match(norm) and not identity:
            kind = "a column that IS a bank trace id, printed with a space"
        elif identity == reference.strip() and norm in ID._instrument_tokens(text):
            kind = "a column the row's own cheque wording introduces"
        else:
            problems.append(f"{reference!r} in {text!r} survives as an instrument on none of the three "
                            f"vouched kinds: traces {traces}, identity {identity!r}, "
                            f"cheque tokens {sorted(ID._instrument_tokens(text))}")
            continue
        kinds_kept.setdefault(kind, []).append((reference, text))
    for kind in ("a column printing one bank trace id beside whatever else it carries",
                 "a column that IS a bank trace id, printed with a space",
                 "a column the row's own cheque wording introduces"):
        if kind not in kinds_kept:
            problems.append(f"no kept reference is {kind}; the corpus no longer exercises the shape the "
                            f"changelog names, so the count there would be unmeasured again")
    if not any(reference == "TRC0428442 SI-3104 SI-3102"
               for reference, _ in kinds_kept.get("a column printing one bank trace id beside whatever "
                                                  "else it carries", [])):
        problems.append("Case 2's own reference is not among the multi-word references the rule keeps; the "
                        "named exception would then be fiction")
    for reference in ("APRIL 2026", "GR PAYRUN 0428", "SI-1044 SI-1052 XZ"):
        if not any(r == reference for r, _ in refused):
            problems.append(f"{reference!r} is not refused, so the containment is not proper")
    print(f"      multi-word references the shape rule admitted: {len(kept)} kept in "
          f"{len(kinds_kept)} vouched kinds, {len(refused)} refused")
    return check("on an advice-free pack the evidenced rule admits nothing the withdrawn shape rule refused, "
                 "and OVER THIS CORPUS, of the multi-word references that rule admitted, it keeps exactly "
                 "the three kinds the bank or the row's own wording vouches for — a column printing one "
                 "trace id, a column that is a trace id printed with a space, a column the cheque wording "
                 "introduces — while the invoice list, the dated memo and the payer's addendum are refused, "
                 "so the containment is proper; the KINDS are a fact about `IDENTITY_CORPUS` and are "
                 "claimed no wider",
                 not problems, "\n".join(problems))


def test_every_identity_a_row_presents_is_one_an_entry_can_quote():
    """The symmetry between `_identity_reference` and `_quotes_identity`,
    swept rather than argued — and the second half of it closed here.

    If a row can present an identity no entry text can be found to quote, the
    outstanding rule holds a question nothing can answer: the entry that
    really is that payment cannot be recognised as naming it. Three repairs,
    and the first two both announced a closure the corpus had not earned:

      * the letter-carrying clause closed `GRPAYRUN0428`, and its commit said
        no row could any longer present an identity no entry could quote. An
        advice may declare an ALL-DIGIT single token (`0428442`);
      * handing `_quotes_identity` the declared set closed that one, and its
        commit said the same thing again. An advice may declare a DIGIT-FREE
        single token (`CASH`): the declared clause admitted it here and then
        `_mentions` fell through to `_ref_tokens`, which required a digit, so
        nothing quoted it — not even the row's own surface — while
        `_identity_reference` went on returning it as an identity.

    The repair is in `_ref_tokens`: a declared token is reference-shaped by
    declaration. Both misses came from a corpus with no such shape in it, so
    the corpus carries `CASH` now, and the claim below states the sweep it is
    measured by rather than asserting a closure over every string.

    A cheque number is the one identity an entry must INTRODUCE rather than
    merely mention, because a bare number in a narration is a quantity or a
    year; the sweep therefore accepts either wording for it and nothing else.
    """
    problems = []
    for reference in IDENTITY_CORPUS:
        for shape in IDENTITY_SURFACES:
            text = shape.format(ref=reference).strip()
            for declared in (frozenset(), frozenset({ID._norm_ref(reference)}) - {""}):
                identity = ID._identity_reference(reference, text, declared)
                if not identity:
                    continue
                if not ID._quotes_identity(text, identity, declared):
                    problems.append(f"the surface {text!r} presents {identity!r} and is not read as quoting it")
                mentioned = ID._quotes_identity(f"Part payment received on SI-1044, {identity}",
                                                identity, declared)
                introduced = ID._quotes_identity(f"November office rent, check {identity}", identity, declared)
                if not (mentioned or introduced):
                    problems.append(f"no entry text can quote {identity!r}, presented by {text!r} "
                                    f"(declared={sorted(declared)})")
    declared = frozenset({"0428442"})
    if ID._identity_reference("0428442", "ACH IN GANNET RIGGING INC 0428442", declared) != "0428442":
        problems.append("an advice declaring an all-digit reference does not make it an identity")
    if not ID._quotes_identity("Part payment received on SI-1044, 0428442", "0428442", declared):
        problems.append("a DECLARED all-digit identity is still not recognised as quoted, which is the "
                        "asymmetry the letter-carrying clause left open")
    if ID._quotes_identity("Part payment received on SI-1044, 0428442", "0428442"):
        problems.append("an UNDECLARED bare number is read as quoting an identity; a number no wording "
                        "introduces is a quantity or a year")
    # the DIGIT-FREE declared token, which the second closure missed: the
    # row's own surface has to quote it, and an undeclared word must not
    declared = frozenset({"CASH"})
    surface = "ACH IN HARBOR FREIGHT LTD CASH"
    if ID._identity_reference("CASH", surface, declared) != "CASH":
        problems.append("an advice declaring a digit-free reference does not make it an identity")
    if not ID._quotes_identity(surface, "CASH", declared):
        problems.append("a DECLARED digit-free identity is not quoted by the ROW'S OWN SURFACE, so no "
                        "entry can answer the row either")
    if not ID._quotes_identity("Part payment received on SI-1044, CASH", "CASH", declared):
        problems.append("a DECLARED digit-free identity is not recognised as quoted by an entry")
    if ID._quotes_identity("Paid CASH at the counter", "CASH"):
        problems.append("an UNDECLARED word is read as quoting an identity; a word no advice declares is "
                        "not reference-shaped at all")
    for token in ("0428442", "CASH"):
        pack = two_partial_payments(token, advice_rows((f"RA-{token}", token)))
        facts, verdict = identity_facts(pack, token), verdict_of(pack)
        if facts.ref_role != ID.REF_INSTRUMENT or not facts.decisive or token not in facts.presents:
            problems.append(f"declared {token}: role {facts.ref_role}, decisive {facts.decisive}, "
                            f"presents {facts.presents}")
        if not verdict.unique or verdict.readings != 1:
            problems.append(f"declared {token}: unique {verdict.unique}, {verdict.readings} readings")
    return check("over `IDENTITY_CORPUS` × `IDENTITY_SURFACES` × declared/undeclared — every shape these "
                 "worlds print plus the ones the reviewers named, and no wider — every identity a row "
                 "presents is one some entry text can be found to quote, the declared ALL-DIGIT and "
                 "DIGIT-FREE tokens included, which the first two closures missed; and an undeclared bare "
                 "number is still a quantity, an undeclared word still a word",
                 not problems, "\n".join(problems))


def census_of(public: dict) -> tuple:
    """The reference census `_evidence` computes, recomputed here so a test can
    read the COUNTS rather than only what they decided.

    Same three inputs and the same declared set, by the same calls: the census
    is half of the uniqueness rule ("no two statement rows quote it, no two
    bank movements quote it"), and a half that counts nothing passes every
    test written against its consequences.
    """
    rows = ID.statement_rows(public[ID.STATEMENT_FILE], period_start=START, period_end=END)[0]
    chart = ID._chart(public)
    equity = frozenset(name for name, kind in chart.items() if kind == "equity")
    movements = ID.ledger_movements(public[ID.LEDGER_FILE], BANK, equity_accounts=equity,
                                    period_start=START, period_end=END)[0]
    archive = ID._archive_reference_rows(public.get(ID.ARCHIVE_FILE, ""))
    return ID._reference_census(rows, archive, movements,
                                evidenced=ID._evidenced_payment_identifiers(public))


def two_partial_payments_and_a_second_row(reference: str, advice: str) -> dict:
    """`two_partial_payments` with a SECOND, unrelated bank row quoting the
    same reference — the statement half of uniqueness."""
    public = two_partial_payments(reference, advice)
    rows = statement_rows(public) + [("2025-11-27", "ACH IN HARBOR FREIGHT LTD", reference, "", "900.00")]
    return restate(public, rows)


def test_a_declared_digit_free_identity_is_quoted_counted_and_loses_to_a_second_quotation():
    """The digit-free declared identifier, end to end — the hole a verifier
    found in the `evidenced` repair, at the level where it did damage.

    An advice may declare `payment_reference` = `CASH`. `_identity_reference`
    returned it, `reference_role` called it an INSTRUMENT and `_row_facts`
    made it decisive; but `_mentions` fell through to `_ref_tokens`, which
    required a digit, so NO text quoted it — the row's own surface included —
    and `_reference_census` counted it nowhere. Two consequences, and the
    second is not a conservative failure:

      * the census half of uniqueness did not bite. A second statement row or
        a second bank movement quoting the identifier left `decisive` True,
        which is the gate that exists to stop exactly that;
      * with `quoted` False on every entry and the role INSTRUMENT, the
        conflict rule pruned every entry naming a document — so the bank row
        matched nothing, was reported as a MISSING ENTRY, and both part
        payments were left outstanding, with `unique=True` and one reading. An
        honest ambiguity would have been survivable; a confident wrong reading
        is not.

    All four fixtures below are one pack with one thing changed, and the
    control is the same bytes with the advice removed.
    """
    problems = []
    advice = advice_rows(("RA-1123-HF", "CASH"))
    declared = two_partial_payments("CASH", advice)
    documents, ledger = census_of(declared)
    facts, verdict = identity_facts(declared, "CASH"), verdict_of(declared)
    if (documents.get("CASH"), ledger.get("CASH")) != (1, 1):
        problems.append(f"declared: the census counts the identity {documents.get('CASH')} times on the "
                        f"statement and {ledger.get('CASH')} times in the books, not once each")
    if facts.ref_role != ID.REF_INSTRUMENT or not facts.decisive or "CASH" not in facts.presents:
        problems.append(f"declared: role {facts.ref_role}, decisive {facts.decisive}, "
                        f"presents {facts.presents}")
    if not verdict.unique or verdict.readings != 1:
        problems.append(f"declared: unique {verdict.unique}, {verdict.readings} readings: "
                        f"{verdict.reason[:200]}")
    # the wrong reading, named literally: the row is ANSWERED by the entry that
    # quotes it, not reported as unrecorded, and the OTHER part payment alone
    # is the deposit in transit
    if any(k[0] == "missing_entry" and k[1] == "2025-11-23" for k in map(key, verdict.repairs)):
        problems.append(f"declared: the bank row is read as a missing entry: "
                        f"{sorted(map(key, verdict.repairs))}")
    in_transit = [item for item in verdict.outstanding if "Harbor Freight" in item]
    if len(in_transit) != 1 or "2025-11-20" not in in_transit[0]:
        problems.append(f"declared: the part payments left outstanding are {in_transit}, not the 20th alone")
    # the control: the identical bytes with no advice to declare it
    bare = two_partial_payments("CASH")
    facts = identity_facts(bare, "CASH")
    if facts.ref_role != ID.REF_UNKNOWN or facts.decisive or facts.presents:
        problems.append(f"undeclared: role {facts.ref_role}, decisive {facts.decisive}, "
                        f"presents {facts.presents}")
    if verdict_of(bare).readings != 2:
        problems.append("undeclared: a word no advice declares decides something")
    # uniqueness, both halves, now that there is a census to count them
    both_entries = two_partial_payments("CASH", advice, quoted_by=(1, 2))
    facts, ledger_count = identity_facts(both_entries, "CASH"), census_of(both_entries)[1].get("CASH")
    if ledger_count != 2:
        problems.append(f"two bank movements quoting it are counted {ledger_count} times, not twice")
    if facts.decisive or verdict_of(both_entries).readings != 2:
        problems.append(f"two bank movements quote it and it still decides: decisive {facts.decisive}")
    two_rows = two_partial_payments_and_a_second_row("CASH", advice)
    facts, row_count = identity_facts(two_rows, "CASH"), census_of(two_rows)[0].get("CASH")
    if row_count != 2:
        problems.append(f"two statement rows quoting it are counted {row_count} times, not twice")
    if facts.decisive or facts.presents:
        problems.append(f"two statement rows quote it and it still decides: decisive {facts.decisive}, "
                        f"presents {facts.presents}")
    return check("a DECLARED digit-free identifier is an identity the whole module can see: the row's own "
                 "surface and the entry that names it both quote it, the census counts it on both sides, it "
                 "decides between two part payments instead of reading the bank row as unrecorded, and a "
                 "second quotation on either side takes the decision away",
                 not problems, "\n".join(problems))


def test_appearance_never_rescues_an_undeclared_reference_and_does_condemn_a_declared_invoice_one():
    """The module docstring's clause about what APPEARANCE may do, pinned.

    The clause said "appearance never rescues one the evidence has not
    declared, and never condemns one it has". Its first half is the rule; its
    second half was false when written, and false by the same round's own
    repair: `_identity_reference` bars a column carrying an invoice id from
    the declared and cheque branches OUTRIGHT, which is a condemnation by
    appearance of a reference an advice has declared — the deliberate one that
    stops a pack promoting receivables to an identity by declaring them.

    So the clause now states an asymmetry, and this test is what makes it a
    measured sentence rather than a readable one: the rescue half over the
    shapes a PAYER composes, the condemn half over the invoice bar, the
    not-condemned half over a declared reference that merely reads badly, and
    the bank's own trace id as the thing "appearance" does NOT mean — a trace
    is an appearance that decides undeclared, because the bank issuing and
    printing it IS the declaration.
    """
    problems = []
    surface = "ACH IN HARBOR FREIGHT LTD {ref}"
    # RESCUE, never: no shape a payer composes becomes an identity unasked
    for reference in ("GR PAYRUN 0428", "APRIL 2026", "SI-1044 SI-1052", "0428442", "CASH", "BX-99"):
        text = surface.format(ref=reference)
        if ID.reference_role(reference, text) == ID.REF_INSTRUMENT:
            problems.append(f"undeclared {reference!r} is rescued by its appearance")
    # except what the BANK composes, which is what the clause excludes by name
    if ID.reference_role("TRC0428442", surface.format(ref="TRC0428442")) != ID.REF_INSTRUMENT:
        problems.append("the bank's own trace id stopped deciding; the clause's named exception is gone")
    # CONDEMN, deliberately: the invoice bar overrules the declaration
    for reference in ("SI-1044 SI-1052", "SI-1044 SI-1052 XZ", "SI-3104"):
        text = surface.format(ref=reference)
        declared = frozenset({ID._norm_ref(reference)})
        if ID._identity_reference(reference, text, declared):
            problems.append(f"declared {reference!r} carries an invoice id and is still an identity")
        if ID.reference_role(reference, text, evidenced=declared) == ID.REF_INSTRUMENT:
            problems.append(f"declared {reference!r} carries an invoice id and is still an instrument")
    # and NOT condemned for anything else: a declared reference that merely
    # reads badly is an identity, which is the half the shape rule got wrong
    for reference in ("APRIL 2026", "CASH", "0428442"):
        text = surface.format(ref=reference)
        declared = frozenset({ID._norm_ref(reference)})
        if ID.reference_role(reference, text, evidenced=declared) != ID.REF_INSTRUMENT:
            problems.append(f"declared {reference!r} is condemned by how it reads")
    # the sentence itself, so that a future edit has to move the code with it
    prose = " ".join((ID.__doc__ or "").split())
    if ("appearance never RESCUES a reference the evidence has not declared, and it DOES condemn a "
            "declared one that carries an invoice id") not in prose:
        problems.append("the module docstring no longer states the clause this test measures")
    if "and never condemns one it has" in prose:
        problems.append("the retracted half of the clause is back in the module docstring")
    return check("the clause on what appearance may do measures true in both halves: it never rescues a "
                 "reference the evidence has not declared — the bank's own trace id being a declaration and "
                 "not an appearance — and it does condemn a declared one that carries an invoice id, while "
                 "condemning nothing for merely reading badly",
                 not problems, "\n".join(problems))


def test_an_invoice_id_alone_never_founds_an_alteration_edge():
    """The invoice-id class, at the edge level rather than the verdict level.

    A row and an entry that quote one invoice, differ in amount, and share
    NOTHING else — no counterparty on the row, no fee class — must not be
    joined by an alteration edge, because the invoice id is the only thing
    tying them together and it does not claim they are one cash movement.
    Give the row the counterparty as well and the edge appears, on the
    counterparty's narrow window rather than the reference's wide one.
    """
    base = add_entries(public_files(), entry(
        "2025-11-21", "Harbor Freight Ltd", "Part payment received on SI-1051",
        [bank("2200.00"), ("Assets:AR", "-2200.00")]))

    def alter_edges(public):
        ev = ID._evidence(public, BANK, START, END)
        edges = ID._build_edges(ev.rows, ev.movements, ev.facts_by_row, parties=ev.parties,
                                fee_account=ev.fee_account)
        rows = {r.index: r for r in ev.rows}
        return [(e.basis, ID.ALTER_WINDOW_DAYS) for e in edges
                if e.kind == "alter" and rows[e.row].reference == "SI-1051"]

    anonymous = restate(base, statement_rows(base) + [("2025-11-22", "ACH IN DEPOSIT", "SI-1051", "", "2350.00")])
    named = restate(base, statement_rows(base) + [("2025-11-22", "ACH IN HARBOR FREIGHT LTD", "SI-1051", "", "2350.00")])
    problems = []
    if alter_edges(anonymous):
        problems.append(f"an invoice id alone founded an alteration edge: {alter_edges(anonymous)}")
    named_edges = alter_edges(named)
    if [b for b, _ in named_edges] != ["counterparty"]:
        problems.append(f"with the counterparty named the edge is {named_edges}, not one counterparty edge")
    return check("an invoice id alone never founds an alteration edge; with the counterparty it does, on the "
                 "counterparty's window", not problems, "\n".join(problems))


def test_a_repeated_counterparty_does_not_decide_a_wrong_amount():
    """Repeated counterparties: two card payments to one vendor, one row.

    Neither entry equals the row, both are dated on or before it and share
    its payee and its week, so either could be the one that was keyed wrong.
    The counterparty is not an identifier — it is the vendor's whole month —
    and a wrong-amount pairing that leans on it alone has to say so.

    Both entries also sit inside the outstanding window, which puts a THIRD
    reading on the table since IDENTIFY_VERSION 5: the row is a card payment
    the books never recorded and both entries are card payments in transit.
    That reading explains the whole month exactly as well as the two
    accusations do, and nothing public prefers the cheaper story, so the
    verdict names both kinds of disagreement.
    """
    public = drop_entry(public_files(), '2025-11-18 * "Office Depot"')
    public = add_entries(
        public,
        entry("2025-11-27", "Office Depot", "Printer paper",
              [("Expenses:Office", "300.00"), bank("-300.00")]),
        entry("2025-11-28", "Office Depot", "Desk supplies",
              [("Expenses:Office", "310.00"), bank("-310.00")]))
    rows = [r for r in statement_rows(public) if not r[0].startswith("2025-11-18")]
    rows.append(("2025-11-28", "DEBIT CARD OFFICE DEPOT", "", "305.00", ""))
    verdict = verdict_of(restate(public, rows))
    stated = ("matches 2 different ledger movements" in verdict.reason
              and "3 maximum readings" in verdict.reason)
    return check("two same-party entries of unlike amounts around one row are not decidable by the "
                 "counterparty", not verdict.unique and stated, f"{verdict}")


def two_bank_fees(booked_second: str, second_row_date: str = "2025-11-14") -> dict:
    """A month with two bank charges: a wire fee mid-month and the monthly
    service charge, with the second one booked at `booked_second`."""
    public = add_entries(
        public_files(),
        entry(second_row_date, "Cascade Bank", "Wire transfer fee",
              [("Expenses:BankFees", "30.00"), bank("-30.00")]),
        entry("2025-11-30", "Cascade Bank", "Monthly account service charge",
              [("Expenses:BankFees", booked_second), bank(f"-{booked_second}")]))
    rows = statement_rows(public) + [(second_row_date, "WIRE TRANSFER FEE", "", "30.00", "")]
    return restate(public, rows)


def test_two_bank_fees_attribute_by_class_not_by_position():
    """Two fees in one month, one of them altered.

    The policy sentence names an ACCOUNT — `Expenses:BankFees` — not a row.
    So the wire fee settles against the entry that matches it and the service
    charge is paired with the entry of the wrong amount that shares its day;
    a checker that read the policy as "the first fee row" would pair the wire
    fee with the service charge entry and report the wrong difference.
    """
    verdict = verdict_of(two_bank_fees("50.00"))
    wrong = [r for r in verdict.repairs if r.kind == "wrong_amount"]
    ok = (verdict.unique and len(wrong) == 1 and wrong[0].date == "2025-11-30"
          and wrong[0].amount == D("-85.00") and wrong[0].booked_amount == D("-50.00")
          and wrong[0].account == "Expenses:BankFees"
          and not any(r.amount == D("-30.00") for r in verdict.repairs))
    return check("two bank fees in one month: the policy identifies the account class and the altered "
                 "charge is the one the amounts single out", ok,
                 f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}")


def test_two_fee_rows_around_one_fee_entry_are_not_decidable():
    """The same policy rule, where it must refuse.

    One fee entry, two fee rows within the bank's own dating window. The
    policy places the entry in the fee class; it does not say which of the
    two charges the class member was, and the two readings differ in both
    the amount that was mis-keyed and the amount that was never booked.
    """
    public = add_entries(public_files(), entry(
        "2025-11-29", "Cascade Bank", "Monthly account service charge",
        [("Expenses:BankFees", "70.00"), bank("-70.00")]))
    rows = statement_rows(public) + [("2025-11-29", "ACCOUNT MAINTENANCE CHARGE", "", "60.00", "")]
    verdict = verdict_of(restate(public, rows))
    stated = "matches 2 different ledger movements" in verdict.reason or "maximum readings" in verdict.reason
    return check("two bank-fee rows competing for one fee entry are reported, not attributed by position",
                 not verdict.unique and stated, f"{verdict}")


def two_altered_fees(same_wording: bool, same_day: bool) -> dict:
    """Two bank charges close together, BOTH booked at the wrong figure.

    The bank prints each charge's name; the books carry each entry under its
    own name and day. When the names differ (or the names agree but the days
    differ), the evidence pairs each row with its own entry; when names and
    days both agree the two readings are indistinguishable.
    """
    first_day, second_day = "2025-11-24", ("2025-11-24" if same_day else "2025-11-26")
    first_words, second_words = "Wire transfer fee", ("Wire transfer fee" if same_wording else "ACH origination fee")
    public = add_entries(
        public_files(),
        entry(first_day, "Cascade Bank", first_words, [("Expenses:BankFees", "5.75"), bank("-5.75")]),
        entry(second_day, "Cascade Bank", second_words, [("Expenses:BankFees", "27.55"), bank("-27.55")]))
    rows = statement_rows(public) + [(first_day, first_words.upper(), "", "15.75", ""),
                                     (second_day, second_words.upper(), "", "25.75", "")]
    return restate(public, rows)


def test_two_altered_fees_are_ambiguous_under_public_constraints():
    """The sweep's fee-swap class (train:153, train:135:hard, train:280:hard;
    train:319:hard under the test secret): two fee rows within three days, one
    or both mis-keyed. Both pairings cost one alteration each and no public
    text promises that a mis-keyed entry keeps its day and wording, so under
    the public constraints alone the verdict is AMBIGUOUS (two readings) —
    and `mint` refuses such a world. The verdict carries the
    diagnostic ranking the prior would give, labelled as such."""
    verdict = verdict_of(two_altered_fees(same_wording=False, same_day=False))
    ranked = [a for a in verdict.ambiguities if a.startswith("diagnostic ranking")]
    ok = (not verdict.unique and verdict.readings == 2 and len(ranked) == 1
          and "-15.75" in ranked[0] and "-25.75" in ranked[0])
    return check("two altered fees within three days: ambiguous under public constraints, with the prior's "
                 "ranking reported as diagnostic only", ok, f"{verdict}")


def test_the_day_and_wording_prior_ranks_the_fee_pairing_when_asked():
    """`tie_break=True`: the declared reconciliation prior — an altered entry
    that carries its row's own day AND wording is the one accused. Diagnostic
    only; never the production verdict. Different wording, or one wording
    on different days, both rank; one wording on one day cannot."""
    a = ID.check_identifiable(two_altered_fees(same_wording=False, same_day=False), bank_account=BANK,
                              period_start=START, period_end=END, tie_break=True)
    b = ID.check_identifiable(two_altered_fees(same_wording=True, same_day=False), bank_account=BANK,
                              period_start=START, period_end=END, tie_break=True)
    want = [("2025-11-24", D("-15.75"), D("-5.75")), ("2025-11-26", D("-25.75"), D("-27.55"))]
    wrong_a = sorted((r.date, r.amount, r.booked_amount) for r in a.repairs if r.kind == "wrong_amount")
    wrong_b = sorted((r.date, r.amount, r.booked_amount) for r in b.repairs if r.kind == "wrong_amount")
    ok = a.unique and wrong_a == want and b.unique and wrong_b == want
    return check("the day-and-wording prior, when asked for, ranks each altered fee against its own-named entry",
                 ok, f"{a}\n{b}")


def test_two_altered_fees_of_one_wording_on_one_day_are_not_decidable():
    """Where even the prior has nothing to hold: same wording, same day, both
    mis-keyed. Which entry was which charge is not in the public evidence,
    and the two readings differ in what they accuse — with or without the
    prior."""
    verdict = ID.check_identifiable(two_altered_fees(same_wording=True, same_day=True), bank_account=BANK,
                                    period_start=START, period_end=END, tie_break=True)
    stated = "maximum readings" in verdict.reason or "matches 2 different ledger movements" in verdict.reason
    return check("two altered fees of one wording on one day stay ambiguous", not verdict.unique and stated, f"{verdict}")


def reused_reference(second_reference: str) -> dict:
    """One invoice settled by two receipts of 2,400.00, only one booked."""
    public = add_entries(public_files(), entry(
        "2025-11-24", "Harbor Freight Ltd", "Customer payment settling SI-1044",
        [bank("2400.00"), ("Assets:AR", "-2400.00")]))
    rows = [r for r in statement_rows(public) if not r[0].startswith("2025-11-26")]
    rows.append(("2025-11-24", "ACH IN HARBOR FREIGHT LTD", "SI-1044", "", "2400.00"))
    rows.append(("2025-11-26", "ACH IN HARBOR FREIGHT LTD", second_reference, "", "2400.00"))
    return restate(public, rows)


def test_a_reused_reference_falls_back_and_stays_ambiguous():
    """One invoice, two receipts, one of them missing from the books.

    `SI-1044` is now quoted by two statement rows, so it identifies the
    invoice and not the payment: reference dominance must switch itself off
    and the pairing falls back to the amount, which the two rows share. Both
    readings book one receipt and leave the other; they disagree about which
    date the missing one carries.
    """
    verdict = verdict_of(reused_reference("SI-1044"))
    stated = ("maximum readings whose repairs differ" in verdict.reason
              and "2025-11-24" in verdict.reason and "2025-11-26" in verdict.reason)
    ok = not verdict.unique and stated and verdict.readings > 1
    return check("a reference quoted by two statement rows decides nothing and the pairing stays "
                 "ambiguous", ok, f"{verdict}\nambiguities: {verdict.ambiguities}")


def test_distinct_references_on_two_equal_receipts_decide():
    """The same two rows, each naming its own invoice.

    Now `SI-1044` is quoted once and `SI-1045` once, the booked receipt names
    `SI-1044`, and the second row is the only unrecorded one. One reading.
    """
    verdict = verdict_of(reused_reference("SI-1045"))
    missing = [r for r in verdict.repairs if r.amount == D("2400.00")]
    ok = (verdict.unique and len(missing) == 1 and missing[0].date == "2025-11-26"
          and missing[0].kind == "missing_entry" and missing[0].account == "Assets:AR")
    return check("two same-amount rows carrying their own invoice numbers are decided by the references",
                 ok, f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}")


def cross_period_cheque(issued: str) -> dict:
    """A cheque issued on `issued` and cleared on 3 November."""
    public = add_entries(public_files(), entry(
        issued, "Cedar Property Group", "October premises rent, check 1034",
        [("Expenses:Rent", "3100.00"), bank("-3100.00")]))
    rows = statement_rows(public) + [("2025-11-03", "CHECK 1034 CEDAR PROPERTY GROUP", "1034", "3100.00", "")]
    return restate(public, rows)


def test_a_cheque_issued_last_month_clears_in_this_one():
    """Cross-period clearing, which the policy describes from the other side.

    October's outstanding cheque is November's cleared row. The entry is
    dated before the period and is still the other half of the row: pairing
    it is not optional, because refusing would invent a missing entry for
    money the books already spent. It is never itself a repair candidate —
    it belongs to a reconciliation nobody mounted.
    """
    verdict = verdict_of(cross_period_cheque("2025-10-29"))
    ok = (verdict.unique and kinds(verdict) == ["missing_entry", "missing_entry"]
          and not any(r.amount == D("-3100.00") for r in verdict.repairs)
          and verdict.matched == 6)
    return check("a cheque issued in October and cleared in November pairs across the cut-off", ok,
                 f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}\nmatched {verdict.matched}")


def test_an_entry_far_outside_the_period_is_not_carry_forward():
    """The carry-forward window has to be able to fail.

    The same cheque dated in August is not last month's outstanding item; no
    statement in the mounted files covers it, and the November row it would
    have answered becomes a difference the checker has to report.
    """
    verdict = verdict_of(cross_period_cheque("2025-08-15"))
    stated = "dated outside" in verdict.reason
    return check("an entry months before the period is reported, not adopted as carry-forward",
                 not verdict.unique and stated, f"{verdict}")


def test_an_exact_reference_does_not_override_an_impossible_direction():
    """A refund quoting the invoice the deposit settles.

    `SI-1044` is quoted once on the statement and once in the books, so the
    reference is decisive — and it still must not pair, because the bank saw
    money arrive and the entry sends money out. An exact reference is
    evidence about WHICH document, never about which way the money went.
    """
    public = add_entries(public_files(), entry(
        "2025-11-26", "Harbor Freight Ltd", "Refund issued against SI-1044",
        [("Assets:AR", "4800.00"), bank("-4800.00")]))
    verdict = verdict_of(public)
    missing = [r for r in verdict.repairs if r.amount == D("4800.00")]
    ok = (verdict.unique and not any(r.kind == "wrong_amount" for r in verdict.repairs)
          and len(missing) == 1 and missing[0].kind == "missing_entry"
          and any("4800.00" in item for item in verdict.outstanding))
    return check("an exact reference does not pair a credit row with a debit entry", ok,
                 f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}\n"
                 f"outstanding: {verdict.outstanding}")


def paired_receipts(rows_wanted: int) -> dict:
    """Two indistinguishable receipts in the books and `rows_wanted` rows of
    the same amount on the statement."""
    public = public_files()
    for date in ("2025-11-20", "2025-11-20"):
        public = add_entries(public, entry(date, "Ridgeline Retail", "Customer payment on account",
                                           [bank("1750.00"), ("Assets:AR", "-1750.00")]))
    rows = statement_rows(public)
    for date in ("2025-11-20", "2025-11-21")[:rows_wanted]:
        rows.append((date, "ACH IN RIDGELINE RETAIL", "", "", "1750.00"))
    return restate(public, rows)


def test_two_matchings_with_one_repair_multiset_are_unique():
    """Two maximum matchings, one reading: the case the rewrite exists for.

    Two identical receipts, two rows of that amount. Swapping which row
    answers which entry is a different MATCHING and the same reconciliation —
    nothing is missing, nothing is outstanding, no repair changes. A checker
    that rejected on multiplicity alone would fail a world that is perfectly
    determined; the test is whether the readings AGREE, not whether there is
    only one of them.
    """
    verdict = verdict_of(paired_receipts(2))
    ok = (verdict.unique and kinds(verdict) == ["missing_entry", "missing_entry"]
          and not any(r.amount == D("1750.00") for r in verdict.repairs))
    return check("two maximum matchings that mean the same reconciliation are one reading", ok,
                 f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}")


def test_two_matchings_with_different_repair_multisets_are_ambiguous():
    """The same evidence with one row removed: now the readings disagree.

    One row, two identical receipts — and because the entries are twins in
    every field a reader can see, one of them is a copy the books should not
    carry. That reading is the same whichever twin is consumed, so this is
    still unique; what makes the pair below ambiguous is the row, not the
    entries. Asserted here as the duplicate it is.
    """
    verdict = verdict_of(paired_receipts(1))
    duplicate = [r for r in verdict.repairs if r.kind == "duplicate"]
    ok = (verdict.unique and len(duplicate) == 1 and duplicate[0].amount == D("1750.00")
          and duplicate[0].copies == 2)
    return check("one row and two indistinguishable entries are a duplicate, identically in every "
                 "matching", ok, f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}")


def test_two_unlike_rows_of_one_amount_with_one_entry_disagree():
    """The disagreeing half: two rows a day apart, one receipt in the books.

    The entry answers either row. The two readings name different dates for
    the entry that has to be written, which is a different set of books —
    ambiguous, and for a reason that has nothing to do with iteration order.
    """
    public = public_files()
    public = add_entries(public, entry("2025-11-20", "Ridgeline Retail", "Customer payment on account",
                                       [bank("1750.00"), ("Assets:AR", "-1750.00")]))
    rows = statement_rows(public)
    rows.append(("2025-11-20", "ACH IN RIDGELINE RETAIL", "", "", "1750.00"))
    rows.append(("2025-11-21", "ACH IN RIDGELINE RETAIL", "", "", "1750.00"))
    verdict = verdict_of(restate(public, rows))
    ok = (not verdict.unique and verdict.readings == 2
          and "maximum readings whose repairs differ" in verdict.reason
          and "2025-11-20" in verdict.reason and "2025-11-21" in verdict.reason)
    return check("two same-amount rows and one entry are two readings that disagree", ok, f"{verdict}")

# --------------------------------------------------------------------------
# IDENTIFY_VERSION 5: the readings cardinality and cheapness used to erase
# --------------------------------------------------------------------------

def duplicated_fee_twin() -> dict:
    """A duplicated bank charge, and another charge the books never carried.

    The month has two bank-initiated rows: a 20 November charge of 32.60
    that no entry answers, and a 23 November charge of 18.50 whose entry the
    books carry TWICE. The two rows are three days apart, which is inside
    the window a bank's own dating slack allows.
    """
    public = add_entries(
        public_files(),
        entry("2025-11-23", "Cascade Bank", "Wire transfer fee",
              [("Expenses:BankFees", "18.50"), bank("-18.50")]),
        entry("2025-11-23", "Cascade Bank", "Wire transfer fee",
              [("Expenses:BankFees", "18.50"), bank("-18.50")]))
    rows = statement_rows(public) + [("2025-11-20", "CHECK PRINTING FEE", "", "32.60", ""),
                                     ("2025-11-23", "WIRE TRANSFER FEE", "", "18.50", "")]
    return restate(public, rows)


def test_a_duplicated_fee_twin_beside_a_missing_fee_row_is_ambiguous():
    """The train:184 class, which cardinality used to hide.

    Two readings explain this month completely:

        the 32.60 row is a charge the books never recorded, and the second
        copy of the 18.50 entry is a duplicate that must go;

        the 32.60 row IS one of the two 18.50 entries, mis-keyed, and the
        23 November row settles the other one.

    Until version 5 only the second was ever enumerated: it pairs one more
    row, and maximum cardinality was applied before anyone compared the
    accounting. Both readings now stand, they disagree about which entry the
    books should end up carrying, and the verdict is ambiguous — which is
    also why `mint` refuses to ship a world of this shape.
    """
    verdict = verdict_of(duplicated_fee_twin())
    named = " ".join(verdict.ambiguities)
    both = "duplicate" in named and "missing_entry" in named and "wrong_amount" in named
    ok = not verdict.unique and verdict.readings == 2 and both
    return check("a duplicated fee twin beside a missing fee row is two readings, not one: the duplicate "
                 "reading is enumerated even though it pairs one row fewer", ok,
                 f"{verdict}\nambiguities: {verdict.ambiguities}")


def test_a_check_printing_fee_is_a_bank_charge_and_not_a_cheque():
    """`CHECK PRINTING FEE` is a fee for printing checks.

    The rail decides the window: a cheque floats for twelve days, a charge
    the bank levies itself is dated by the bank and slips by three. Reading
    the instrument word first gave this row the whole cheque float to find a
    partner in — which is the other half of the train:184 defect — so the
    bank-initiated class is decided FIRST. Asserted where it bites: the
    duplicated 18.50 twin twelve days away is out of reach of the 32.60 row
    as a cheque would not be.
    """
    public = duplicated_fee_twin()
    rows = ID.statement_rows(public[ID.STATEMENT_FILE], period_start=START, period_end=END)[0]
    printing = next(r for r in rows if "PRINTING" in r.description)
    cheque = next(r for r in rows if "CHECK 1037" in r.description)
    facts = {r.index: ID._row_facts(r, parties=ID._parties(public), chart=ID._chart(public),
                                    fee_account="Expenses:BankFees", documents={}, ledger={}, precedents={})
             for r in (printing, cheque)}
    ok = (facts[printing.index].fee and facts[printing.index].rail == "bank"
          and ID.RAIL_WINDOW_DAYS["bank"] == ID.BANK_INITIATED_WINDOW_DAYS
          and not facts[cheque.index].fee and facts[cheque.index].rail == "cheque"
          and ID.RAIL_WINDOW_DAYS["cheque"] > ID.RAIL_WINDOW_DAYS["bank"])
    return check("a bank-initiated row is classified before its wording is read for a rail, so CHECK PRINTING "
                 "FEE gets the bank's three days and a real cheque row still gets twelve", ok,
                 f"printing {facts[printing.index]}\ncheque {facts[cheque.index]}")


def deposit_in_transit_quoting_the_missing_receipt() -> dict:
    """The train:715 class: a missing deposit and a later one on one invoice.

    The bank credits 1,855.51 on 25 November quoting SI-1044 and the books
    record nothing. On 29 November the books record a PART payment of
    4,329.51 against the same invoice, which the bank has not seen yet.
    """
    public = add_entries(public_files(), entry(
        "2025-11-29", "Harbor Freight Ltd", "Part payment received on SI-1044",
        [bank("4329.51"), ("Assets:AR", "-4329.51")]))
    rows = statement_rows(public) + [("2025-11-25", "ACH IN HARBOR FREIGHT LTD", "SI-1044", "", "1855.51")]
    return restate(public, rows)


def test_a_deposit_in_transit_is_not_the_wrong_amount_for_an_earlier_row():
    """Time direction: the bank processes on or after the day it happens.

    Both entries quote SI-1044, so a checker that let reference dominance
    force a pairing read the 29 November entry as the 25 November row keyed
    wrong — a difference of 2,474.00 out of nowhere. The bank credited the
    money on the 25th; an entry dated the 29th cannot be what it credited.
    `## Dates` says so, so there is no edge at all: the row is a receipt the
    books never recorded and the entry is a deposit in transit.
    """
    verdict = verdict_of(deposit_in_transit_quoting_the_missing_receipt())
    missing = [r for r in verdict.repairs if r.amount == D("1855.51")]
    ok = (verdict.unique and not any(r.kind == "wrong_amount" for r in verdict.repairs)
          and len(missing) == 1 and missing[0].kind == "missing_entry"
          and missing[0].date == "2025-11-25" and missing[0].account == "Assets:AR"
          and missing[0].counterparty == "Harbor Freight Ltd"
          and any("4329.51" in item for item in verdict.outstanding))
    return check("a later entry quoting the same invoice is a deposit in transit, never the earlier row's "
                 "wrong amount", ok,
                 f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}\n"
                 f"outstanding: {verdict.outstanding}")


def dominated_settlement() -> dict:
    """One receipt in the books, two rows that could want it.

    The books record 2,500.00 from Harbor Freight on 20 November settling
    SI-1052. The bank shows an unreferenced credit of exactly 2,500.00 that
    same day — the settlement — and a SECOND credit of 2,450.00 two days
    later that quotes SI-1052, which the books never recorded.
    """
    public = add_entries(public_files(), entry(
        "2025-11-20", "Harbor Freight Ltd", "Customer payment settling SI-1052",
        [bank("2500.00"), ("Assets:AR", "-2500.00")]))
    rows = statement_rows(public) + [("2025-11-20", "ACH IN HARBOR FREIGHT LTD", "", "", "2500.00"),
                                     ("2025-11-22", "ACH IN HARBOR FREIGHT LTD", "SI-1052", "", "2450.00")]
    return restate(public, rows)


def test_reference_dominance_never_removes_a_settlement():
    """A reference may force an alteration; it may not empty a settlement.

    `SI-1052` is quoted once on the statement and once in the books, so it is
    decisive, and it points the 2,450.00 row at the entry — as an ALTERATION,
    because the amounts differ. Dominance used to clear that entry's diary for
    the pairing it had just won: the exact, same-day, same-party 2,500.00
    settlement was deleted as a competitor, the entry was then accused of
    being 50.00 out, and the 2,500.00 the bank really did credit was reported
    as money the books never saw. The settlement is the identity
    `## Matching the statement to the ledger` declares and the reference is
    weaker evidence than an exact amount with the same counterparty on the
    same day, so it survives — and the 2,450.00 row is simply unrecorded.
    """
    verdict = verdict_of(dominated_settlement())
    kept = not any(r.amount == D("2500.00") for r in verdict.repairs)
    missing = [r for r in verdict.repairs if r.amount == D("2450.00")]
    ok = (verdict.unique and kept and len(missing) == 1 and missing[0].kind == "missing_entry"
          and missing[0].date == "2025-11-22" and missing[0].account == "Assets:AR"
          and not any(r.kind == "wrong_amount" for r in verdict.repairs))
    return check("a reference-based pairing never prunes the equal-amount settlement of the entry it names",
                 ok,
                 f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}\nmatched {verdict.matched}")


# --------------------------------------------------------------------------
# IDENTIFY_VERSION 7: `## Payments to suppliers` is the public rule, and
# this month's entries corroborate it (the verifier's follow-up B)
# --------------------------------------------------------------------------

def unrecorded_supplier_payment(precedent: str = "") -> dict:
    """A supplier payment the books never recorded, with NO other payment to
    that supplier in the month.

    November's only other money-out row to Northwind Supplies is dropped
    (entry and statement row alike), so nothing in this month's ledger says
    how a payment to Northwind is posted. `vendors.csv` gives Northwind
    `Assets:Inventory`, which is where its GOODS land — the ledger's
    21 November purchase entry shows exactly that — and reading the master
    file as if it named the payment account posts the same money to stock
    twice. Only `## Payments to suppliers` can attribute this row.

    `precedent` optionally re-adds a money-out entry to Northwind booked to
    that account, which is the ledger contradicting the rule.
    """
    public = drop_entry(public_files(), '2025-11-04 * "Northwind Supplies"')
    if precedent:
        public = add_entries(public, entry(
            "2025-11-12", "Northwind Supplies", "Payment of purchase invoice PI-2211",
            [(precedent, "6200.00"), bank("-6200.00")]))
    rows = [r for r in statement_rows(public) if not r[0].startswith("2025-11-04")]
    if precedent:
        rows.append(("2025-11-12", "ACH OUT NORTHWIND SUPPLIES", "PI-2211", "6200.00", ""))
    rows.append(("2025-11-24", "ACH OUT NORTHWIND SUPPLIES", "PI-2240", "5100.00", ""))
    return restate(public, rows)


def test_a_supplier_payment_is_attributed_by_the_policy_not_by_default_account():
    """The row is posted to the payables account, on the policy's authority.

    `vendors.csv` books Northwind's purchases to `Assets:Inventory`;
    `accounts.csv` types that account as an asset; `## Payments to suppliers`
    says the payable was therefore raised when the goods arrived and the cash
    settles it in `Liabilities:AP`. No entry in this month's books says so —
    the precedent has been removed — and the answer is still `Liabilities:AP`,
    which is the whole point of making it a published rule rather than an
    inference. The repair's `authority` quotes the section by name.
    """
    verdict = verdict_of(unrecorded_supplier_payment())
    payment = [r for r in verdict.repairs if r.amount == D("-5100.00")]
    ok = (verdict.unique and len(payment) == 1 and payment[0].kind == "missing_entry"
          and payment[0].account == "Liabilities:AP"
          and payment[0].counterparty == "Northwind Supplies"
          and "## Payments to suppliers" in payment[0].authority
          and "Assets:Inventory" in payment[0].authority)
    return check("a supplier payment with no precedent is posted to the payables account the policy names, "
                 "not to the master file's default_account", ok,
                 f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}\n"
                 f"authority: {[r.authority for r in verdict.repairs]}")


def test_the_supplier_payment_key_is_the_planted_key_literally():
    """The literal tuple, both sides, for the case follow-up B was about.

    Pinned as a value rather than as an equality between two functions: if
    `repair_key` and `planted_key` both drifted the same way, an
    equality-only test would still pass.
    """
    world, base = REGISTRY["bank_recon_001"]
    plan = PJ.MutationPlan((PJ.OmitRecognition("unrecorded_supplier_payment", "rec:pi-2211-payment",
                                               "the statement row names the supplier and the invoice"),))
    _, inputs = DV.derive_contract(world, dataclasses.replace(base, plan=plan))
    public = {name: data.decode("utf-8") for name, data in inputs.public_files}
    verdict = verdict_of(public)
    want = ("missing_entry", "2025-11-04",
            (("Assets:Bank:Checking", "-6200.00"), ("Liabilities:AP", "6200.00")),
            "Northwind Supplies", None, 1)
    planted = [planted_key(p, master_names(public), bank_account=BANK) for p in inputs.planted]
    found = [ID.repair_key(r) for r in verdict.repairs]
    ok = verdict.unique and planted == [want] and found == [want]
    return check("an omitted supplier payment keys to the literal tuple on both sides", ok,
                 f"want    {want}\nplanted {planted}\nchecker {found}")


def test_a_ledger_that_contradicts_the_policy_is_a_refusal():
    """Corroboration that fails. The books post money out to Northwind to
    `Assets:Inventory`, which is what the policy says a payment is NOT. Rule
    and ledger cannot both be right about the unrecorded row, so it is
    refused rather than resolved in either direction — and the refusal names
    both readings.
    """
    verdict = verdict_of(unrecorded_supplier_payment(precedent="Assets:Inventory"))
    stated = ("the rule and the books disagree" in verdict.reason
              and "## Payments to suppliers" in verdict.reason
              and "Assets:Inventory" in verdict.reason)
    return check("a ledger that books a supplier payment against the policy's rule is a refusal, not a guess",
                 not verdict.unique and stated, f"{verdict}")


def test_an_expense_supplier_payment_is_the_expense_by_the_same_rule():
    """The other branch of the one section, with the precedent removed too.

    Office Depot's purchases are booked to `Expenses:Office`, which
    `accounts.csv` types as an expense, so no payable was raised and the
    payment IS the expense. The account happens to equal `default_account`
    here — which is exactly why the rule has to be stated: the two coincide
    for an expense supplier and diverge for a stock supplier, and only the
    section says which case a row is in.
    """
    public = drop_entry(public_files(), '2025-11-18 * "Office Depot"')
    rows = [r for r in statement_rows(public) if not r[0].startswith("2025-11-18")]
    rows.append(("2025-11-19", "DEBIT CARD OFFICE DEPOT", "", "305.00", ""))
    verdict = verdict_of(restate(public, rows))
    card = [r for r in verdict.repairs if r.amount == D("-305.00")]
    ok = (verdict.unique and len(card) == 1 and card[0].account == "Expenses:Office"
          and "## Payments to suppliers" in card[0].authority
          and "expense" in card[0].authority)
    return check("a payment to a supplier whose purchases are an expense posts to that expense account, on "
                 "the same section's authority", ok,
                 f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}\n"
                 f"authority: {[r.authority for r in verdict.repairs]}")


def test_the_policy_section_is_in_every_world_the_environment_ships():
    """The contract sentence itself: identical in the template and in the
    hand-authored world, naming exactly one chart account, and required by
    `check_content`. A generated world and Alpine must not disagree about a
    rule the checker reads."""
    from beancount_ledger.graph import content as C
    from beancount_ledger.graph.policy import POLICY_SECTIONS
    from beancount_ledger.graph.worlds import alpine_2025_11 as A

    def section(text: str) -> str:
        lines = text.splitlines()
        at = lines.index(ID.SUPPLIER_PAYMENT_SECTION)
        body = []
        for line in lines[at + 1:]:
            if line.startswith("## "):
                break
            body.append(line)
        return "\n".join(body).strip()

    problems = []
    template = section(C.POLICY_TEMPLATE)
    if template != section(A.POLICY_TEXT):
        problems.append("the template and Alpine do not share the section")
    if ID.SUPPLIER_PAYMENT_SECTION not in C.POLICY_TEMPLATE or ID.SUPPLIER_PAYMENT_SECTION not in A.POLICY_TEXT:
        problems.append("a world is missing the section")
    if POLICY_SECTIONS.get("vendor_payment") != ID.SUPPLIER_PAYMENT_SECTION:
        problems.append(f"the vendor_payment rule cites {POLICY_SECTIONS.get('vendor_payment')!r}")
    if POLICY_SECTIONS.get("expense_payment") != ID.SUPPLIER_PAYMENT_SECTION:
        problems.append(f"the expense_payment rule cites {POLICY_SECTIONS.get('expense_payment')!r}")
    # `check_content` must require it, so a future edit that drops it fails here
    stripped = C.POLICY_TEMPLATE.replace(ID.SUPPLIER_PAYMENT_SECTION + "\n", "")
    saved, C.POLICY_TEMPLATE = C.POLICY_TEMPLATE, stripped
    try:
        if not any("Payments to suppliers" in p for p in C.check_content()):
            problems.append("check_content does not require the section")
    finally:
        C.POLICY_TEMPLATE = saved
    public = public_files()
    chart = set(ID._chart(public))
    named = ID._policy_account(public[ID.POLICY_FILE], ID.SUPPLIER_PAYMENT_SECTION, chart)
    if named != "Liabilities:AP":
        problems.append(f"the section names {named!r}, not one payables account")
    return check("the supplier-payment section is identical in the template and in Alpine, is required by "
                 "check_content, is cited by the two money-out rules, and names one chart account",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# currency and annotations: refused at the parse boundary
# --------------------------------------------------------------------------

def test_costs_prices_and_a_second_currency_never_reach_the_scorer():
    """Why `repair_key` omits currency: it is an ENFORCED INVARIANT.

    Three refusals, asserted at the boundary rather than asserted in a
    comment. A posting carrying a cost lot, a posting carrying an `@` price,
    and a posting denominated in something other than the declared operating
    currency are each a `ProtocolFailure` with a named code, so no such
    posting can be allocated, resolved or scored. A document declaring two
    operating currencies is refused as well. Every posting the scorer can
    ever compare is therefore in the one operating currency, and a currency
    component of the key would be a constant on both sides.
    """
    from beancount_ledger.candidate.mapping import POSTING_FIELDS, Disposition
    from beancount_ledger.candidate.normalise import ProtocolFailure, parse_once

    header = ('option "title" "T"\noption "operating_currency" "USD"\n'
              "2025-01-01 open Assets:Bank:Checking USD\n"
              "2025-01-01 open Assets:Inventory USD\n"
              "2025-01-01 open Expenses:Office USD\n\n")
    cases = {
        "cost": header + ('2025-11-18 * "X" "Y"\n  Assets:Inventory   10 WIDGET {42.00 USD}\n'
                          "  Assets:Bank:Checking  -420.00 USD\n"),
        "price": header + ('2025-11-18 * "X" "Y"\n  Assets:Inventory   10 WIDGET @ 42.00 USD\n'
                           "  Assets:Bank:Checking  -420.00 USD\n"),
        "currency": header + ('2025-11-18 * "X" "Y"\n  Expenses:Office   420.00 EUR\n'
                              "  Assets:Bank:Checking  -420.00 USD\n"),
        "two_currencies": ('option "title" "T"\noption "operating_currency" "USD"\n'
                           'option "operating_currency" "EUR"\n'
                           "2025-01-01 open Assets:Bank:Checking USD\n"),
    }
    want = {"cost": "posting.cost", "price": "posting.price",
            "currency": "posting.units.currency", "two_currencies": "option.operating_currency"}
    problems = []
    for label, text in cases.items():
        result = parse_once(text)
        if not isinstance(result, ProtocolFailure):
            problems.append(f"{label}: accepted, not refused ({type(result).__name__})")
        elif not result.reason.startswith(want[label]):
            problems.append(f"{label}: refused as {result.reason!r}, not {want[label]}*")
    for field in ("cost", "price"):
        if POSTING_FIELDS[field].disposition is not Disposition.REJECTED:
            problems.append(f"Posting.{field} is classified {POSTING_FIELDS[field].disposition}")
    # and the key is documented as omitting currency FOR THIS REASON
    if "ENFORCED INVARIANT" not in (ID.repair_key.__doc__ or ""):
        problems.append("repair_key does not document why currency is absent")
    return check("cost lots, prices, a foreign posting currency and a second operating currency are all "
                 "refused at the parse boundary, which is why the repair key omits currency",
                 not problems, "\n".join(problems))


def test_both_key_implementations_match_literal_tuples_per_kind():
    """Literal pins, one fixture per planted kind.

    `identify.repair_key` and `derive.planted_key` are separate
    implementations, and this compares each of them to a WRITTEN-OUT tuple
    rather than to the other, so a common-mode change to both is a failure
    here instead of a silent agreement.
    """
    world, base = REGISTRY["bank_recon_001"]
    fixtures = {
        "omit": (base.plan, [
            ("missing_entry", "2025-11-26",
             (("Assets:AR", "-4800.00"), ("Assets:Bank:Checking", "4800.00")), "Harbor Freight Ltd", None, 1),
            ("missing_entry", "2025-11-30",
             (("Assets:Bank:Checking", "-85.00"), ("Expenses:BankFees", "85.00")), None, None, 1),
        ]),
        "alter": (PJ.MutationPlan((ALTER_OFFICE,)), [
            ("wrong_amount", "2025-11-18",
             (("Assets:Bank:Checking", "-420.00"), ("Expenses:Office", "420.00")), "Office Depot", "-240.00", 1),
        ]),
        "duplicate": (PJ.MutationPlan((DUP_RENT,)), [
            ("duplicate", "2025-11-10",
             (("Assets:Bank:Checking", "-3500.00"), ("Expenses:Rent", "3500.00")), "Cedar Property Group", None, 1),
        ]),
    }
    problems = []
    for kind, (plan, want) in fixtures.items():
        _, inputs = DV.derive_contract(world, dataclasses.replace(base, plan=plan))
        public = {name: data.decode("utf-8") for name, data in inputs.public_files}
        verdict = verdict_of(public)
        names = master_names(public)
        planted = sorted(planted_key(p, names, bank_account=BANK) for p in inputs.planted)
        found = sorted(ID.repair_key(r) for r in verdict.repairs)
        if planted != sorted(want):
            problems.append(f"{kind}: planted_key {planted} != pinned {sorted(want)}")
        if not verdict.unique or found != sorted(want):
            problems.append(f"{kind}: repair_key {found} != pinned {sorted(want)} (unique={verdict.unique})")
        for tuple_ in planted + found:
            if any("USD" in str(part) for part in tuple_):
                problems.append(f"{kind}: a currency reached the key: {tuple_}")
    return check("repair_key and planted_key each equal the literal pinned tuple for omit, alter and "
                 "duplicate, and neither carries a currency", not problems, "\n".join(problems))


def test_an_omitted_item_is_repaired_on_the_bank_s_date_and_the_keys_agree():
    """Contract change B, end to end on the shipped world.

    The planted omissions carry the date the statement shows, the checker
    reads that same date off the row, and the two projections of a repair —
    `identify.repair_key` over what the checker inferred and `planted_key`
    over what the graph planted — are equal tuple for tuple. That is the
    whole claim the sweep's old `(kind, signed amount)` comparison could not
    make: same kind, same date, same postings, same counterparty, same
    multiplicity.
    """
    world, task = REGISTRY["bank_recon_001"]
    bundle, inputs = DV.derive_contract(world, task)
    public = {name: data.decode("utf-8") for name, data in inputs.public_files}
    verdict = verdict_of(public)
    names = master_names(public)
    want = sorted(planted_key(p, names, bank_account=BANK) for p in inputs.planted)
    got = sorted(ID.repair_key(r) for r in verdict.repairs)
    statement_dates = {line.split(",")[0] for line in public[ID.STATEMENT_FILE].splitlines()[1:]}
    on_bank_date = all(p.date in statement_dates for p in inputs.planted if p.kind == "omit")
    ok = verdict.unique and want == got and on_bank_date
    return check("an omitted item's repair date is the bank's date, and planted_key == repair_key on the "
                 "shipped world's planted items", ok,
                 f"planted: {want}\nchecker: {got}\nomissions on a statement date: {on_bank_date}")


def test_a_cheque_the_statement_shows_is_never_also_in_transit():
    """The verifier's post-dated-cheque case (D1). An entry for check 1055
    dated AFTER the row that shows check 1055 clearing: the time-direction
    rule severs the edge, so row and entry fall into different components.
    A component-scoped 'presented' set then read the row as a missing entry
    AND the entry as a deposit in transit — a unique verdict that books one
    cheque twice. Presentation is world-wide: a row nothing can answer is
    missing in every reading, and an entry naming its cheque is not in
    transit. The verdict must not be a confident double booking."""
    public = add_entries(public_files(), entry(
        "2025-11-25", "Office Depot", "Office supplies, check 1055",
        [("Expenses:Office", "640.00"), bank("-640.00")]))
    rows = statement_rows(public) + [("2025-11-20", "CHECK 1055 OFFICE DEPOT", "1055", "640.00", "")]
    verdict = verdict_of(restate(public, rows))
    double = (any(r.kind == "missing_entry" and r.amount == D("-640.00") for r in verdict.repairs)
              and any("1055" in o for o in verdict.outstanding))
    ok = not (verdict.unique and double)
    return check("a cheque the statement shows is never also reported in transit: the post-dated entry is not a "
                 "confident double booking", ok,
                 f"{verdict}\nrepairs: {[str(r) for r in verdict.repairs]}\noutstanding: {verdict.outstanding}")


def test_a_conflicting_invoice_id_prunes_the_settlement_but_never_the_alteration():
    """The second verifier's repro. An entry `Part payment received on
    SI-1097` (+2200) and a bank row two days later for +2350 naming the same
    customer: with no reference, or an unrecognised one, the world has two
    readings (the row missing + the entry in transit, or the entry mis-keyed).
    Adding the invoice id `SI-1098` to the row — a DOCUMENT conflict with
    the entry's `SI-1097` — must not turn those two readings into one: a
    document says which receivable the money applies to, not which cash
    movement this is, so it prunes a settlement of equal amount but never
    the alteration that stands on the counterparty. A ROW naming an
    INSTRUMENT (a cheque number) that the entry contradicts prunes both."""
    problems = []
    base = add_entries(public_files(), entry(
        "2025-11-21", "Harbor Freight Ltd", "Part payment received on SI-1097",
        [("Assets:AR", "-2200.00"), bank("2200.00")]))
    readings = {}
    for label, reference in (("none", ""), ("unknown", "XX-1098"), ("invoice", "SI-1098")):
        rows = statement_rows(base) + [("2025-11-22", "ACH IN HARBOR FREIGHT LTD", reference, "", "2350.00")]
        verdict = verdict_of(restate(base, rows))
        readings[label] = (verdict.unique, verdict.readings)
    if readings["none"][0] or readings["unknown"][0]:
        problems.append(f"the reference-free / unknown-reference rows should be ambiguous: {readings}")
    if readings["invoice"] != readings["none"]:
        problems.append(f"an invoice id changed the verdict: {readings}")
    # the same amount and a conflicting invoice id: the settlement is pruned (row missing, entry not its match)
    rows = statement_rows(base) + [("2025-11-22", "ACH IN HARBOR FREIGHT LTD", "SI-1098", "", "2200.00")]
    same = verdict_of(restate(base, rows))
    settled_anyway = same.unique and not any(r.amount == D("2200.00") for r in same.repairs)
    if settled_anyway:
        problems.append("a row naming SI-1098 was settled by an entry naming SI-1097")
    # a cheque number on the row that the entry contradicts prunes the alteration too
    cheque = add_entries(public_files(), entry(
        "2025-11-21", "Harbor Freight Ltd", "Part payment received, check 4277",
        [("Assets:AR", "-2200.00"), bank("2200.00")]))
    rows = statement_rows(cheque) + [("2025-11-22", "CHECK 4278 HARBOR FREIGHT LTD", "4278", "", "2350.00")]
    instrument = verdict_of(restate(cheque, rows))
    if any(r.kind == "wrong_amount" and r.amount == D("2350.00") for r in instrument.repairs):
        problems.append("a row naming check 4278 was read as a mis-keyed check 4277")
    return check("a conflicting invoice id prunes an equal-amount settlement but never the counterparty-based "
                 "alteration (two readings stay two); a conflicting cheque number prunes both",
                 not problems, f"{readings}\n" + "\n".join(problems))


TESTS = [
    test_a_conflicting_invoice_id_prunes_the_settlement_but_never_the_alteration,
    test_a_cheque_the_statement_shows_is_never_also_in_transit,
    test_the_shipped_world_is_identifiable,
    test_the_outstanding_cheque_is_not_reported_as_a_difference,
    test_the_ambiguous_variant_is_rejected_for_the_stated_reason,
    test_a_second_movement_of_one_amount_is_rejected,
    test_a_competing_entry_naming_another_cheque_is_not_a_competitor,
    test_the_checker_cannot_see_hidden_identity,
    test_the_alter_and_duplicate_kinds_are_identified,
    test_every_planted_kind_is_seen_together,
    test_the_reference_decides_across_a_clearing_float,
    test_a_stranded_ledger_movement_far_from_the_cut_off_is_not_outstanding,
    test_two_receipts_of_one_amount_are_not_decidable_by_amount,
    test_the_reference_ontology_classifies_every_shape_the_worlds_publish,
    test_an_evidenced_unique_payment_identifier_is_decisive,
    test_an_identifier_two_advices_declare_is_no_identity,
    test_an_invoice_list_is_document_evidence_and_decides_nothing,
    test_a_generic_dated_memo_is_not_a_payment_identity,
    test_the_advice_file_is_read_for_the_reference_column_and_nothing_else,
    test_the_evidenced_rule_is_a_proper_subset_of_the_withdrawn_shape_rule,
    test_every_identity_a_row_presents_is_one_an_entry_can_quote,
    test_a_declared_digit_free_identity_is_quoted_counted_and_loses_to_a_second_quotation,
    test_appearance_never_rescues_an_undeclared_reference_and_does_condemn_a_declared_invoice_one,
    test_an_invoice_number_does_not_decide_between_two_receipts_of_one_amount,
    test_a_cheque_number_does_decide_between_two_receipts_of_one_amount,
    test_two_partial_receipts_on_one_invoice_are_not_decided_by_the_invoice,
    test_the_same_two_receipts_are_decided_by_their_cheque_numbers,
    test_an_invoice_id_alone_never_founds_an_alteration_edge,
    test_a_repeated_counterparty_does_not_decide_a_wrong_amount,
    test_two_bank_fees_attribute_by_class_not_by_position,
    test_two_fee_rows_around_one_fee_entry_are_not_decidable,
    test_two_altered_fees_are_ambiguous_under_public_constraints,
    test_the_day_and_wording_prior_ranks_the_fee_pairing_when_asked,
    test_two_altered_fees_of_one_wording_on_one_day_are_not_decidable,
    test_a_reused_reference_falls_back_and_stays_ambiguous,
    test_distinct_references_on_two_equal_receipts_decide,
    test_a_cheque_issued_last_month_clears_in_this_one,
    test_an_entry_far_outside_the_period_is_not_carry_forward,
    test_an_exact_reference_does_not_override_an_impossible_direction,
    test_two_matchings_with_one_repair_multiset_are_unique,
    test_two_matchings_with_different_repair_multisets_are_ambiguous,
    test_two_unlike_rows_of_one_amount_with_one_entry_disagree,
    test_a_duplicated_fee_twin_beside_a_missing_fee_row_is_ambiguous,
    test_a_check_printing_fee_is_a_bank_charge_and_not_a_cheque,
    test_a_deposit_in_transit_is_not_the_wrong_amount_for_an_earlier_row,
    test_reference_dominance_never_removes_a_settlement,
    test_an_omitted_item_is_repaired_on_the_bank_s_date_and_the_keys_agree,
    test_the_policy_section_is_in_every_world_the_environment_ships,
    test_a_supplier_payment_is_attributed_by_the_policy_not_by_default_account,
    test_the_supplier_payment_key_is_the_planted_key_literally,
    test_a_ledger_that_contradicts_the_policy_is_a_refusal,
    test_an_expense_supplier_payment_is_the_expense_by_the_same_rule,
    test_costs_prices_and_a_second_currency_never_reach_the_scorer,
    test_both_key_implementations_match_literal_tuples_per_kind,
]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
