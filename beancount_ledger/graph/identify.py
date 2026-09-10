"""Public-only identifiability: does the visible evidence force one repair?

**STATUS: a generation gate for the shapes the projector can plant, not a
proof of solvability in general.** What is established here is that a reader
holding only the mounted files can reconstruct the planted differences and
nothing else. Read the limitations at the bottom of this docstring before
treating a green verdict as a promise.

The distinction this module exists to protect is the one the old prototype
(`canonical/identify.py`) got right and paid for: *consistency* asks whether
the intended repair reconciles to one clean state and legitimately consumes
the answer key; *identifiability* asks whether an agent, seeing only the
documents, is left with exactly one defensible repair. It must not know the
answer. So the signature takes `dict[str, str]` — file name to text — and
this module imports nothing from `schema`, `policy`, `project`, `derive` or
`worlds`. There is no `World` to accidentally read, no `Bundle`, no
`MutationPlan`, no recognition identifier. The private identifier is the join
key that makes a bank row and a ledger entry describe one economic event; a
checker holding it would not have to *prove* the join is possible, it could
look it up, and every ambiguous world would come back unique — which is
precisely the answer that makes a broken generator look correct.

The reconciliation is the bookkeeper's, performed on the bytes, and since
version 2 it is a MATCHING problem rather than a scan:

    parse the bank-account movements out of `ledger.beancount` (date, signed
    amount, payee, narration) and the rows out of `bank_statement.csv`
    (date, description, reference, signed amount), reading
    `archive_prior_period.csv` as part of one public evidence set;

    build a bipartite ADMISSIBILITY GRAPH — statement rows on one side,
    ledger movements on the other. An edge means "these two could be one
    event": either a settlement (equal amounts, compatible direction and
    account role, dated inside the window the rail and the policy allow) or
    an alteration (a booked amount that differs, tied to the row by a
    reference, by the policy's account class or by the counterparty);

    read the repairs off a matching: an unmatched row is a `missing_entry`,
    a row matched across an alteration edge is a `wrong_amount`, a movement
    left over beside a matched twin of the same visible shape is a
    `duplicate`, a movement left over near the cut-off is an OUTSTANDING item
    — a timing difference, not an error, and the policy says so;

    enumerate every matching that (i) realises the greatest possible number
    of SETTLEMENTS and (ii) leaves nothing unexplained. Both constraints are
    public. The first is `## Matching the statement to the ledger`: a row and
    an entry of the same amount and counterparty inside the clearing window
    ARE one transaction, so a reading that declines such a pairing is not a
    competing history. The second is what a reconciliation IS: every row and
    every entry ends up settled, restated, reported missing, named as a
    surplus copy, or named as a timing difference the policy describes;

    the verdict is `unique` only when every surviving matching yields the
    SAME semantic repair multiset. Two readings that disagree about which row
    the books already carry, or about which entry carries the wrong amount,
    are an ambiguity however the iteration order happens to fall — and
    NEITHER matching cardinality nor "fewest alterations" is allowed to
    settle it. Both were parsimony priors no public text promises, and both
    used to erase the competing history "the row is missing and this entry is
    a surplus copy of its twin" before anyone could compare it.

Reference dominance is CONDITIONAL, ROLE-AWARE and EVIDENCED.
Every reference-shaped token is classified by `reference_role` — instrument,
document, memo, unknown — and only an INSTRUMENT may decide a pairing, because
only an instrument names one cash movement. What makes a reference an
instrument is never its SHAPE. It is one of three things the public evidence
says out loud: a cheque number the row's own wording introduces (`check
2291`), a bank trace id (`_TRACE_SYNTAX` — the bank's own identifier for one
transfer), or a payment identifier a mounted document DECLARES to be one —
`remittance_advice.csv`'s `payment_reference` column, a customer stating that
a payment of theirs carries that reference. Nothing else is an instrument, and
in particular a multi-word reference is not: "two or more words, one with a
digit" describes an invoice list (`SI-3104 SI-3102`) and a dated memo (`APRIL
2026`) as readily as an ACH addendum, and no shape a PAYER composes names one
cash movement. What the BANK composes is not the same thing: the trace id is
an appearance that DOES decide, and it decides because the bank issues it for
one transfer and prints it itself — the bank vouching for it is the
declaration, which is why `_TRACE_SYNTAX` survives the correction and stands
in the list of three above. For every other
reference the declaration decides — appearance never rescues one the evidence
has not declared, and never condemns one it has. (An earlier draft of this
paragraph said "appearance decides nothing IN EITHER DIRECTION", which
contradicted the trace id three lines above it.)
A column carrying an invoice id is barred from the first two declarations
outright, so nothing can promote receivables to an identity by declaring
them; a dated memo an advice DOES declare is an identity, because the advice
has stated that a payment of the customer's carries that reference, and
refusing it because it reads badly would put the shape rule back with its
sign flipped. What stops a poor reference from deciding what it should not is
uniqueness, not appearance. The advice bytes reach this module the way every
other public file does — as text in the `public` mapping, read here and
nowhere else; nothing is imported to obtain them.

An instrument decides only when, after one normalisation, no two
advices declare it, it is quoted by at most one bank row across the current
statement and the archive and by at most one ledger bank movement, and the
candidate is compatible in direction (a credit row never pairs with a debit
entry), in account role (a row naming one master party does not pair with an
entry booked to a different master party) and in policy-valid timing. A
DOCUMENT reference — `SI-*`, `PI-*`, or a list of them — names the receivable
or payable the money applies to, which several receipts, a refund and a
deposit in transit may share: it may be the stated basis of a settlement the
amount and the window already allow, but it never dominates, never founds an
alteration edge on its own, and never buys the wide reference float. A
reused reference of either kind buys nothing and the pairing falls back to
amount and counterparty. An exact reference never overrides an impossible
direction.

Windows are rail and policy semantics, not one number: a cheque floats, an
ACH credit lands in a day or two, a card settles within the week, a charge
the bank levies itself is dated by the bank. They are named constants below
with the reasoning attached. Which rail a row runs on is decided by asking
FIRST whether the bank levied the charge itself — no counterparty, no
reference, the bank's own charge wording — because `CHECK PRINTING FEE` is a
fee and not a cheque. Windows are also one-sided for a customer or vendor
rail: the bank processes a transaction on or after the day it happens, so an
entry dated after the row is not that row's transaction. Where the public
evidence cannot distinguish two readings the answer is `ambiguous`; the
checker never breaks a tie by iteration order.

Attribution is done the way the agent must do it, and it reads the PUBLIC RULE
first. The row's description is searched for a name that appears in the
customer or vendor master. For money moving OUT to a vendor, `policy.md`'s
`## Payments to suppliers` decides: a supplier whose `default_account` is an
asset had a payable raised when the goods arrived, so the payment settles the
payable the section names in backticks; a supplier whose `default_account` is
an expense had none, so the payment IS the expense. That is three published
facts and no inference — the row's direction, `vendors.csv`, and the account
type in `accounts.csv` — and it is what stops `default_account` being read as
the account a payment lands on (an inventory supplier's goods go to stock; the
cheque that pays for them settles the payable). The ledger's own precedent for
money moving the same way to that party then CORROBORATES the rule: agreement
is quoted alongside it, and disagreement is a refusal, because the rule and the
books cannot both be right. Where no public rule covers the direction, the
precedent decides on its own and the master file's `default_account` is the
fallback where the month shows none. Two different precedents for one party and
one direction is a refusal, not a guess. A row that
names no party is attributed only if the policy document places it — the
`## Bank service charges` section names a chart account in backticks, and a
bank-initiated charge with no counterparty lands in that CLASS. The class is
what the policy fixes; it never selects "the first fee row" when a month
carries several. Nothing else is attributable, and "not attributable" is a
rejection, not a guess.

Known limitations, stated because a green test gets mistaken for a gate:

    the repair language is the three shapes the projector can plant. A world
    whose intended repair is a split receipt, a batched deposit or a partial
    application is outside the enumeration, and "unsupported topology" and
    "unique" are different claims of which only one would be true here;

    the running-balance column is not re-walked (that is `check_bundle`'s
    job, on the private side) and `manifest.md` is accepted but carries no
    weight. The archive is read for two purposes only: reference uniqueness,
    and nothing else — a period row is never matched against an archive row;

    reference uniqueness is counted over bank rows and over ledger entries
    that TOUCH THE BANK ACCOUNT. A sale entry and its cost-of-goods twin
    both quote the invoice number by design and are not competing pairings,
    so counting them would make every invoice reference non-decisive;

    one currency is assumed. The mounted worlds publish one operating
    currency and the statement carries no currency column, so the currency
    compatibility the specification asks for is vacuous here rather than
    checked;

    the enumeration is bounded. Components larger than the budget below come
    back ambiguous, which is the safe direction but is not a proof that the
    world was ambiguous.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date as _date
from decimal import Decimal, InvalidOperation

# 7: `## Payments to suppliers` is the public rule for a money-out row and
#    precedent corroborates it; references carry a ROLE and only an instrument
#    may dominate or found an alteration. The instrument table later gained
#    the payment reference, FIRST AS A SHAPE and now as EVIDENCE: the shape
#    rule (two or more words, one with a digit) was wrong and is retracted in
#    `_reference_words`; an instrument identity is now one the public bytes
#    declare (`_identity_reference`). That correction is versioned separately,
#    as `REFERENCE_IDENTITY_VERSION` below, and NOT by a bump here; the
#    argument is written out there rather than asserted here.
# 5: settlements are forced by the declared convention and every OTHER reading
#    that explains the whole month competes on equal terms — cardinality and
#    "fewest alterations" no longer erase one; time direction; bank-initiated
#    rows are classified before the rail wording; `repair_key`
# 4: the agreement prior is diagnostic only (tie_break=False by default)
# 3: the prior broke ties; 2: complete matching
IDENTIFY_VERSION = 7

# WHAT MAKES A REFERENCE A PAYMENT IDENTITY, versioned in its own right.
#
#   1  SHAPE (withdrawn). `_payment_reference_words`: two or more
#      whitespace-separated words, at least one carrying a digit. Wrong, and
#      retracted in `_reference_words`.
#   2  EVIDENCE. `_identity_reference`: a cheque number the row's own wording
#      introduces, a bank trace id, or a reference a mounted
#      `remittance_advice.csv` DECLARES in `payment_reference` — and, in the
#      first two cases and the third alike, only where the declaration is
#      unique across the pack.
#
# This constant exists because the reviewer required the family's admission
# semantics to be versioned while the OLD SIGNED POPULATION stays verifiable,
# and those two are not the same version. `IDENTIFY_VERSION` is bound into
# `manifest.versions()` and therefore into every promoted record's signature:
# bumping it would make `manifest.admit` refuse the whole v9 population over
# a rule none of those worlds can reach. So the identity rule carries its OWN
# number, which the family's admission declares
# (`manifest.family_admission_versions()`) and which the family manifest
# deferred by the reviewer's decision 3 must sign when it is built. Nothing
# about this is a claim that the change is too small to version — it is a
# claim about WHICH artifact the version belongs in.
#
# The compatibility argument, stated at the width it actually holds. On any
# pack that mounts NO advice, `evidenced` is empty and rule 2 reduces to
# cheque-or-trace, whose admitted set is a PROPER SUBSET of rule 1's: it
# admits nothing rule 1 refused — the load-bearing half, since that is what
# stops a verdict moving — and of the multi-word references rule 1 admitted it
# keeps exactly one kind, a column printing a single bank trace id
# (`TRC0428442 SI-3104 SI-3102`, Case 2's own reference), which rule 1
# admitted too. RETRACTED IN PLACE: this clause used to read "it refuses every
# multi-word reference rule 1 admitted", which is false, and the trace column
# is the counterexample. The subset is proper all the same, because `APRIL
# 2026`, `GR PAYRUN 0428` and `SI-1044 SI-1052 XZ` are all refused, so the
# conclusion below is untouched. Both halves are now MEASURED rather than
# asserted (`test_identify.py`, the withdrawn rule re-implemented beside the
# current one over the shapes these worlds print).
# Every manifested world is such a pack — no legacy task and no generated
# world mounts a `remittance_advice.csv`, prints a multi-word reference or
# prints a trace id — so no promoted verdict can move in either direction.
# The unrestricted claim would be FALSE and is not made: where an advice IS
# mounted, rule 2 admits inputs rule 1 refused, a declared single-token
# reference (`GRPAYRUN0428`) being the plain case, and the repository's own
# ontology table asserts exactly that. `tests/test_family_validators.py`
# surveys both populations for both facts rather than asserting them.
REFERENCE_IDENTITY_VERSION = 2

LEDGER_FILE = "ledger.beancount"
STATEMENT_FILE = "bank_statement.csv"
ARCHIVE_FILE = "archive_prior_period.csv"
ACCOUNTS_FILE = "accounts.csv"
CUSTOMERS_FILE = "customers.csv"
VENDORS_FILE = "vendors.csv"
POLICY_FILE = "policy.md"
# Read for ONE fact and nothing else: which references the evidence itself
# declares to be payment identifiers (`payment_reference`). Absent from the
# legacy packs, in which case no reference is evidenced and only cheque
# numbers and trace ids are instruments. Nothing else in this module reads it:
# the applications, the amounts and the invoices it carries are the cash
# family's business, not the bank reconciliation's.
REMITTANCE_FILE = "remittance_advice.csv"

# ---------------------------------------------------------------------------
# Windows. Each one is a rail or a policy statement, not a tuning knob.
# ---------------------------------------------------------------------------
# A cheque is written on the day it is issued and cleared when the payee
# banks it. The float is the reason `## Outstanding checks` exists; a week
# and a half covers "posted Friday, banked the following week" without
# reaching the next month's cheque of the same amount.
CHEQUE_FLOAT_DAYS = 12
# ACH settles next business day; two days plus a weekend is the whole range
# the generator's `_clears` can draw and the range a bank actually prints.
ACH_WINDOW_DAYS = 5
# A card authorisation settles within the week.
CARD_WINDOW_DAYS = 5
# A charge the bank levies itself is dated by the bank on the day it applies
# it, and the books carry the same day. The slack is for a month end that
# falls on a weekend.
BANK_INITIATED_WINDOW_DAYS = 3
# A row whose wording names no rail: the ACH range, which is the commonest.
MATCH_WINDOW_DAYS = 5
RAIL_WINDOW_DAYS = {
    "cheque": CHEQUE_FLOAT_DAYS,
    "ach": ACH_WINDOW_DAYS,
    "card": CARD_WINDOW_DAYS,
    "bank": BANK_INITIATED_WINDOW_DAYS,
    "unknown": MATCH_WINDOW_DAYS,
}
# A wrong amount is booked on the day the event happened; the tolerance here
# is for a transposed date, not for a float, and the pairing additionally
# demands the reference, the policy's account class or the counterparty.
ALTER_WINDOW_DAYS = 3
# A reference the whole public evidence set quotes once decides the pairing
# whatever the float — bounded, because "somewhere in the file" is not a
# timing claim and the archive is a month long.
REFERENCE_FLOAT_DAYS = 40
# How close to the cut-off a stranded ledger movement must be to read as a
# timing difference (an issued cheque the bank has not cleared, a deposit in
# transit) rather than as an entry the bank never saw.
OUTSTANDING_WINDOW_DAYS = 10
# A ledger entry dated before the period may still be the thing an early row
# settles: last month's cheque clearing in this one. Further back than this
# and the entry belongs to a reconciliation nobody mounted.
CARRY_FORWARD_DAYS = 45

# The enumeration is bounded per connected component. Worlds carry at most
# thirty rows and the components are small; a component that blows either
# budget is reported ambiguous rather than decided by where the search
# happened to stop.
MAX_SEARCH_NODES = 200_000
MAX_READINGS = 200

STATEMENT_COLUMNS = ("date", "description", "reference", "debit", "credit", "balance")
BANK_FEE_SECTION = "## Bank service charges"
# The public rule for money moving OUT to a party the vendor master carries.
# The section names one chart account in backticks — the payables account —
# and states the test that decides whether a payment lands there or on the
# supplier's own `default_account`: whether that account holds the supplier's
# purchases as an ASSET (a payable was raised when the goods arrived) or as an
# EXPENSE (none was). `accounts.csv` types the account, so the whole test is
# public, and it is a RULE rather than an inference from this month's entries.
SUPPLIER_PAYMENT_SECTION = "## Payments to suppliers"

_ENTRY = re.compile(r'^(\d{4}-\d{2}-\d{2})\s+[*!]\s+"([^"]*)"(?:\s+"([^"]*)")?\s*$')
_POSTING = re.compile(r'^\s{2,}([A-Z][A-Za-z0-9:_-]*)\s+(-?[\d,]+\.\d{2})\s+[A-Z]{3}\s*$')
_FEE_WORDING = re.compile(r"\b(SERVICE\s+CHARGE|CHARGES?|FEES?)\b", re.IGNORECASE)
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*")
_CHEQUE_ROW = re.compile(r"\bCHECK\b|\bCHEQUE\b", re.IGNORECASE)
_ACH_ROW = re.compile(r"\bACH\b|\bWIRE\b|\bTRANSFER\b", re.IGNORECASE)
_CARD_ROW = re.compile(r"\bCARD\b", re.IGNORECASE)


class PublicOnly(TypeError):
    """Something that is not text was handed to a public-only checker."""


class _Exhausted(Exception):
    """The bounded enumeration ran out of budget: report, do not decide."""


# --------------------------------------------------------------------------
# what the two documents say, and nothing about where it came from
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LedgerMovement:
    """One entry's net effect on the bank account, read from the ledger text."""

    index: int
    date: str
    amount: Decimal          # signed on the bank account, as the books print it
    payee: str
    narration: str
    legs: tuple              # ((account, Decimal), ...) sorted: the whole entry
    other_accounts: tuple    # the non-bank accounts of the entry, sorted
    in_period: bool = True   # False: a carry-forward entry from before the period

    @property
    def text(self) -> str:
        return f"{self.payee} {self.narration}"

    @property
    def shape(self) -> tuple:
        """What makes two entries indistinguishable to a reader."""
        return (self.date, self.amount, self.payee, self.narration, self.legs)

    def __str__(self) -> str:
        return f"{self.date} {self.payee} {self.narration!r} {self.amount:+.2f}"


@dataclass(frozen=True)
class StatementRow:
    index: int
    date: str
    description: str
    reference: str
    amount: Decimal          # signed on the bank account: credit positive

    def __str__(self) -> str:
        ref = f" [{self.reference}]" if self.reference else ""
        return f"{self.date} {self.description}{ref} {self.amount:+.2f}"


UNDERIVABLE = "the public files do not fix this field"


@dataclass(frozen=True)
class Repair:
    """One repair a reader could defend from the documents alone.

    `date` is the date the CORRECTED BOOKS carry the entry, which is not
    always the row's date: an entry the books are missing is posted on the
    bank's date (`## Dates`, contract change B), while an entry that is
    already booked at the wrong figure keeps its own date and only the figure
    is restated. `row_date` keeps the statement row's date for the checks
    that are about rows.
    """

    kind: str                        # missing_entry | wrong_amount | duplicate
    date: str
    amount: Decimal                  # what the bank saw, signed on the bank account
    description: str
    reference: str
    counterparty: str | None         # a customers.csv/vendors.csv name, or None
    account: str | None              # the non-bank account the repair posts to
    booked_amount: Decimal | None = None   # wrong_amount: what the books say instead
    copies: int = 1                  # duplicate: how many copies the books carry
    expected_copies: int = 1         # how many copies the CORRECT books carry
    postings: tuple | None = ()      # ((account, Decimal), ...) sorted; None: not derivable
    bank_account: str = ""
    row_date: str | None = None      # the statement row this repair answers, when there is one
    detail: str = ""
    basis: str = ""                  # what tied the row to the entry, when one did
    notes: tuple = ()                # attribution complaints, if any
    authority: str = ""              # the public rule that fixed `account`, quoted by name

    def __str__(self) -> str:
        return f"{self.kind} {self.date} {self.amount:+.2f} {self.detail}"

    def semantic_key(self) -> tuple:
        """What two readings must agree on to be the same repair.

        Not the wording, not which of two indistinguishable ledger entries
        was the one consumed: the accounting claim.
        """
        return repair_key(self)


def _posting_key(postings) -> tuple | str:
    if postings is None:
        return UNDERIVABLE
    return tuple(sorted((account, f"{Decimal(value):.2f}") for account, value in postings))


def repair_key(repair: Repair) -> tuple:
    """THE projection of a repair, used everywhere a checker repair is
    compared with a planted item.

        (kind, date, postings, counterparty, booked bank amount, copies)

    * `kind`      `missing_entry` / `wrong_amount` / `duplicate`, the public
                  names of the three planted kinds.
    * `date`      the date the corrected books carry the entry: the bank's
                  date for an entry the books lack, the entry's own date for
                  one that is already booked (contract change B).
    * `postings`  the whole entry, as a sorted tuple of
                  `(account, amount to two places)`. The bank leg comes from
                  the row (or from the booked entry); the counter leg from the
                  policy's `## Payments to suppliers` rule for money moving out
                  to a vendor, from the account the policy's fee section names
                  for a bank charge, from the ledger's own precedent for money
                  moving the same way to that party where no rule covers it, or
                  from the master file's `default_account` where the month shows
                  no precedent either. Currency is NOT a component: see the note
                  below. Where the
                  public files fix no counter account the field is the string
                  `UNDERIVABLE` — said explicitly, never dropped.
    * `counterparty`  a customers.csv / vendors.csv name, or None. The bank
                  itself is not a master-file party, so a bank charge carries
                  None on both sides of the comparison.
    * `booked`    `wrong_amount` only: the figure the books carry instead.
    * `copies`    how many copies the CORRECT books carry (1 everywhere
                  except a duplicate the reader thinks should stay doubled).

    CURRENCY is deliberately absent from `postings`, and the reason is an
    ENFORCED INVARIANT rather than an oversight. The parse
    boundary refuses a second currency and every cost, price and lot
    annotation before a submission can be scored: `mapping.POSTING_FIELDS`
    classifies `cost` and `price` as `rejected`, so a posting carrying either
    is a `ProtocolFailure`, and `normalise._build_event` refuses any posting
    whose unit currency is not the declared operating currency
    (`posting.units.currency`), while `option.operating_currency.not_single`
    refuses a document that declares two. A changed operating currency is a
    preservation failure the scorer prices. So every posting the scorer can
    ever compare is denominated in the one operating currency of the world,
    and a currency component would be a constant on both sides of every
    comparison. `tests/test_identify.py` asserts those three refusals rather
    than leaving the claim to this comment. If a world ever publishes two
    currencies, this key gains a currency component in the same change.

    NOT part of item identity, and why — the same closed list the scorer's
    `RETAINED_FIELDS` publishes: narration and payee wording (the deliverable
    prints the graph's own, so authored text is never scored), entry and
    posting flags, tags, links, source references, posting ORDER (Beancount
    ignores it and `occurrence_key` sorts it away), the statement row's
    description and reference (evidence for the join, not part of the entry),
    and which of two indistinguishable entries was the one consumed.
    """
    return (repair.kind, repair.date, _posting_key(repair.postings), repair.counterparty,
            None if repair.booked_amount is None else f"{repair.booked_amount:.2f}",
            repair.expected_copies)


@dataclass
class Verdict:
    unique: bool
    repairs: list
    ambiguities: list
    reason: str
    outstanding: list = field(default_factory=list)
    matched: int = 0
    readings: int = 1        # how many maximum matchings the evidence admits

    def __str__(self) -> str:
        head = "identifiable" if self.unique else "NOT identifiable"
        return f"{head}: {self.reason}"


# --------------------------------------------------------------------------
# parsing the bytes
# --------------------------------------------------------------------------

def _day(iso: str) -> _date:
    return _date.fromisoformat(iso)


def _gap(a: str, b: str) -> int:
    return abs((_day(a) - _day(b)).days)


def _amount(text: str) -> Decimal:
    return Decimal(text.replace(",", "").strip())


def _norm_ref(token: str) -> str:
    """One normalisation, applied to every reference on every surface.

    Case folded and stripped of punctuation, so `SI-1044`, `si 1044` and
    `SI1044` are one reference and `PI-1037` is still not `1037`.
    """
    return re.sub(r"[^A-Z0-9]", "", (token or "").upper())


def _ref_tokens(text: str) -> set:
    """Every normalised reference-shaped token the text quotes.

    A token must carry a digit: `check` is a word, `1037` is a reference,
    and word-shaped tokens would otherwise make every narration collide.
    """
    out = set()
    for token in _TOKEN.findall(text or ""):
        norm = _norm_ref(token)
        if norm and any(ch.isdigit() for ch in norm):
            out.add(norm)
    return out


def _mentions(haystack: str, token: str) -> bool:
    """Does the text quote this reference as a token of its own?

    A reference is sometimes several words (`GR PAYRUN 0428`, `SI-3104
    SI-3102`), so no single token of the text equals it; the text quotes it
    when it carries the reference's words, normalised one by one, as a
    contiguous run in the same order. `PAYRUN 0428 GR` does not quote
    `GR PAYRUN 0428`, and `SI-3102` alone does not quote `SI-3104 SI-3102`.

    QUOTATION, not identity. That a text names a reference says nothing about
    whether the reference names one payment; `reference_role` decides that,
    and it asks the evidence rather than the shape.
    """
    norm = _norm_ref(token)
    if not norm:
        return False
    if norm in _ref_tokens(haystack):
        return True
    words = _reference_words(token)
    if not words:
        return False
    tokens = [_norm_ref(t) for t in _TOKEN.findall(haystack or "")]
    n = len(words)
    return any(tuple(tokens[i:i + n]) == words for i in range(len(tokens) - n + 1))


# --------------------------------------------------------------------------
# the reference ontology
# --------------------------------------------------------------------------
# `SI-1247` is an invoice number, not a payment identifier. Two partial
# receipts, a refund and a deposit in transit may all quote one, so treating
# the string as if it named a cash movement confuses "which receivable?" with
# "which payment?" — which is how a later deposit in transit came to be
# accused of carrying an earlier row's wrong amount. Every reference-shaped
# token therefore carries a ROLE, and the role says what the token may do:
#
#   instrument  a payment identifier the PUBLIC EVIDENCE DECLARES to be one:
#               a cheque number the row's own wording introduces (`check
#               2291`), a bank trace id (`_TRACE_SYNTAX`), or a reference a
#               mounted `remittance_advice.csv` names in its
#               `payment_reference` column — the customer's own statement that
#               a payment of theirs carries it (spec section 2:
#               "`payment_reference` is what the bank prints (ACH addendum,
#               verbatim in the statement `reference`, or cheque number)").
#               Names ONE cash movement, so a globally unique one may decide a
#               pairing outright (dominance), may found an alteration edge on
#               its own, gets the long reference float, and CONFLICTS: an
#               entry naming a different instrument is not this row's
#               movement. An identifier two advices declare is no identity at
#               all; one two bank rows quote is an identity that decides
#               nothing.
#   document    an invoice or order id (`SI-*`, `PI-*`), alone or as a LIST of
#               them (`SI-3104 SI-3102`). Names the document, or documents, a
#               payment applies to — and two partial payments may quote one
#               list. Supporting evidence: it may be the stated basis of a
#               SETTLEMENT the amount and the window already allow,
#               but it is never dominant, never founds an alteration edge by
#               itself, and never hard-prunes.
#   memo        text carrying no reference-shaped token at all. Never decides
#               anything.
#   unknown     reference-shaped, but neither syntax. Supporting evidence with
#               no hard prune: an unrecognised code must not be read as an
#               identity claim in either direction.
REF_INSTRUMENT = "instrument"
REF_DOCUMENT = "document"
REF_MEMO = "memo"
REF_UNKNOWN = "unknown"
REFERENCE_ROLES = (REF_INSTRUMENT, REF_DOCUMENT, REF_MEMO, REF_UNKNOWN)

# The document syntaxes the generator publishes, and Alpine's: a sales
# invoice and a purchase invoice. Normalised, so `SI-1044`, `si 1044` and
# `SI1044` are one token.
_DOCUMENT_SYNTAX = re.compile(r"^(SI|PI)\d{2,8}$")
# A bank trace id: the bank's own long reference for one transfer. Not
# produced by these worlds today; classified so that a world that starts
# printing one gets the instrument rules rather than the unknown ones.
_TRACE_SYNTAX = re.compile(r"^(TRACE|TRC|REF)\d{6,}$")


def _reference_words(reference: str) -> tuple:
    """The normalised words of a reference printed as SEVERAL words, or `()`.

    A quotation aid and a census key, nothing more. A multi-word reference is
    one token on no surface — `GR PAYRUN 0428` normalises to `GRPAYRUN0428`,
    which no narration contains — so `_mentions` has to look for its words in
    order and `_reference_census` has to count the whole string beside the
    tokens inside it. Only the raw column carries word boundaries, so callers
    pass the reference as printed.

    RETRACTION. This was `_payment_reference_words`, and its shape — "two or
    more whitespace-separated words, at least one carrying a digit" — was read
    as an INSTRUMENT identity, on the argument that the bank attaches an
    addendum to one credit and prints it verbatim, so the string names one
    cash movement the way a cheque number does. That argument does not hold
    and the rule is withdrawn. The shape admits an invoice list (`SI-3104
    SI-3102`) and a generic dated memo (`APRIL 2026`), and neither of those
    names a payment. And an addendum being attached to one bank row does not
    establish that its text names exactly one payment: two partial payments
    may quote the same invoice list, and one sighting of that list on the
    statement beside one in the books does not exclude an unrecorded receipt
    standing next to a deposit in transit. The tests of the old rule showed
    that it forced the reading the cash-application family wanted; they never
    showed the classification was warranted. What an instrument identity is
    now comes from `_identity_reference`: evidence, not shape. The digit
    condition went with the rest of it — a quotation aid has no business
    requiring one.
    """
    words = tuple(w for w in (_norm_ref(t) for t in _TOKEN.findall(reference or "")) if w)
    return words if len(words) >= 2 else ()


def _evidenced_payment_identifiers(public: dict) -> frozenset:
    """The references the mounted evidence DECLARES to be payment identifiers.

    One source, read leniently: `remittance_advice.csv`'s `payment_reference`
    column. A row there is a customer saying "a payment of mine carries this
    reference", and that statement — not the shape of the string — is what
    lets a bank row's reference be read as naming one cash movement.
    Normalised, so the column and the statement meet the way every other
    reference does.

    An identifier TWO ADVICES declare is dropped: two payments quoting one
    reference is exactly the case where the reference cannot say which payment
    a row is. The other half of uniqueness — that no two bank rows quote it,
    archive included — is the census test in `_row_facts`.

    A pack that mounts no advices declares nothing, which is every legacy
    world: there only a cheque number and a trace id are instruments, exactly
    as before this file had heard of `payment_reference`. The file is read for
    this and nothing else — its amounts, invoices and applications are the
    cash family's business, and reading them here would be reading an answer
    this module has to prove a reader can reconstruct.
    """
    text = public.get(REMITTANCE_FILE, "")
    if not text:
        return frozenset()
    declared: dict = {}
    try:
        for record in csv.DictReader(io.StringIO(text)):
            reference = _norm_ref((record.get("payment_reference") or "").strip())
            if not reference:
                continue
            declared.setdefault(reference, set()).add((record.get("remittance_id") or "").strip())
    except csv.Error:
        return frozenset()
    return frozenset(reference for reference, advices in declared.items() if len(advices) == 1)


def _identity_reference(reference: str, text: str, evidenced: frozenset) -> str:
    """The PAYMENT IDENTIFIER this reference names, as printed, or `""`.

    Three declarations and no fourth:

      * the column is one an advice declares (`evidenced`);
      * the row's own wording introduces it as a cheque (`check 2291`);
      * the column names exactly one bank trace id (`_TRACE_SYNTAX`), the
        bank's own identifier for one transfer — printed beside whatever
        addendum the payer sent, so the identity is that token and not the
        whole column.

    A column that CARRIES an invoice id is barred from the first two, so a
    declaration cannot promote receivables to an identity: a list names
    receivables, and an advice quoting one has stated the basis of an
    application rather than the identity of a payment. Two partial payments
    may still quote it. One invoice number was never enough for this, and
    concatenating two does not cure it.

    CORRECTION, and the guarantee stated at its real width. This clause used
    to read "an invoice id, and a LIST of invoice ids, is refused before any
    of the three, so no pack can turn one into an identity by declaring it",
    and the code behind it fired only where EVERY word was invoice-shaped.
    `SI-1044 SI-1052 XZ`, declared by one advice, was therefore an instrument
    and decided a two-part-payment pack — a list of receivables promoted by
    appending one junk token, which is the very thing the sentence claimed no
    pack could do. The test is now "any word of the column is an invoice id",
    so the mixed list is refused too, and the guarantee holds as written.
    What such a column may still present is the third declaration and only
    it: one bank trace id it also prints, and the identity is THAT TOKEN, not
    the list around it. That is Case 2 of the cash family, and it is why the
    trace is extracted rather than the column returned whole — an advice that
    declares the whole printed column, invoice ids and all, still yields the
    trace alone.

    Anything else names no payment either: an unrecognised code, or a dated
    memo NO ADVICE DECLARES. A dated memo an advice does declare is an
    identity, deliberately: `evidenced` is a customer stating that a payment
    of theirs carries that reference, and the whole point of the correction
    is that the declaration decides and the shape does not. `APRIL 2026` is
    a poor reference and a pack should not print one, but a pack that
    declares it has said what it says; the rule refuses to re-derive an
    identity from the string's appearance in either direction. Uniqueness,
    not taste, is what keeps such a reference from deciding anything it
    should not: two advices declaring it drops it, and so does a second bank
    row quoting it.

    The caller keeps a refusal as document or unknown evidence, which is what
    it is. Returned AS PRINTED, because `_mentions` needs the word boundaries
    normalisation erases.
    """
    printed = (reference or "").strip()
    norm = _norm_ref(printed)
    if not norm:
        return ""
    words = _reference_words(printed)
    carries_invoice = bool(_DOCUMENT_SYNTAX.match(norm)) or any(_DOCUMENT_SYNTAX.match(word) for word in words)
    if not carries_invoice and (norm in evidenced or norm in _instrument_tokens(text)):
        return printed
    traces = sorted(token for token in _ref_tokens(printed) if _TRACE_SYNTAX.match(token))
    return traces[0] if len(traces) == 1 else ""


def _quotes_identity(text: str, token: str, evidenced: frozenset = frozenset()) -> bool:
    """Does this text NAME the payment identifier a statement row presented?

    A cheque number counts only where the wording introduces it — a bare
    number in a memo is a quantity or a year, and an entry that means the
    cheque says so. Everything else an identity can be is either distinctive
    enough that quoting it is naming it, or DECLARED: a trace id, a multi-word
    identifier (whose words `_mentions` requires in order), a token carrying a
    letter (`GRPAYRUN0428`), and a reference a mounted advice declares —
    which is why `evidenced` is handed in here too, from the same public
    mapping and by the same route as everywhere else in this module.

    SYMMETRY, at the width it now holds. Every identity `_identity_reference`
    can return has to be one SOME entry text can be found to quote, or a row
    presents an identity no narration can answer and the outstanding rule is
    left unanswerable. Two rounds of repair, and the first one over-claimed:
    the letter-carrying clause closed the case of a declared alphanumeric
    token, and the commit that added it said flatly that no row could any
    longer present an identity no entry could be found to quote. That was
    false. An advice may declare an ALL-DIGIT single token (`0428442`), which
    `_identity_reference` returns as an identity and which none of the earlier
    tests here recognised. The `evidenced` clause is that case, and with it
    the guarantee holds: a cheque number is quoted by an entry that introduces
    it as one, and every other identity by an entry that mentions it. The
    residual asymmetry was never a wrong pairing — it failed toward ambiguity
    — and it reaches no shipped world, since every identity the five family
    packs declare carries a letter and the 95 legacy packs present only cheque
    numbers; it is repaired rather than left standing, and `test_identify`
    sweeps the pairing rather than trusting this paragraph.
    """
    norm = _norm_ref(token)
    if norm in _instrument_tokens(text):
        return True
    if (norm in evidenced or _reference_words(token) or _TRACE_SYNTAX.match(norm)
            or any(ch.isalpha() for ch in norm)):
        return _mentions(text, token)
    return False


def reference_role(token: str, text: str = "", *, evidenced: frozenset = frozenset()) -> str:
    """The role of one reference, read from what the evidence DECLARES it to
    be and from how the text that carries it introduces it.

    `text` is the surface the token was read off — a statement row's
    description and reference column, or an entry's payee and narration — and
    it is what turns a bare number into an instrument: `1037` alone is a
    quantity or a year, `check 1037` is a cheque.

    `evidenced` is the set of normalised references a mounted
    `remittance_advice.csv` declares to be payment identifiers
    (`_evidenced_payment_identifiers`). It is handed in rather than looked up
    here, the way this module is handed every public file: it holds no world
    and opens nothing.

    `token` is the reference AS PRINTED: an identity may be several words
    (`GR PAYRUN 0428`) or one token inside the column (a trace id), and
    normalisation erases the boundaries either way.
    """
    norm = _norm_ref(token)
    if not norm:
        return REF_MEMO
    if _identity_reference(token, text, evidenced):
        return REF_INSTRUMENT
    if _DOCUMENT_SYNTAX.match(norm):
        return REF_DOCUMENT
    if _TRACE_SYNTAX.match(norm):
        return REF_INSTRUMENT
    words = _reference_words(token)
    if words and all(_DOCUMENT_SYNTAX.match(word) for word in words):
        # A list of invoice ids names receivables, not a payment: two partial
        # payments may quote one list. Document evidence, exactly as one
        # invoice id is.
        return REF_DOCUMENT
    return REF_UNKNOWN


def _instrument_tokens(text: str) -> set:
    """The payment INSTRUMENTS a text names: cheque numbers, introduced by
    the word "check"/"cheque". An instrument identifies one cash movement;
    a statement row that shows it has presented it. Invoice-shaped codes
    (`SI-1044`, `PI-2178`) are NOT instruments — they name the receivable or
    payable an amount applies to, and several receipts, a refund or a
    deposit in transit may all quote one."""
    return {t for t in (_norm_ref(n) for n in re.findall(r"(?:check|cheque)\s*#?\s*(\d{2,8})", text or "", re.IGNORECASE)) if t}


def _document_tokens(text: str) -> set:
    """The documents an entry NAMES: cheque numbers and invoice-shaped codes.

    A bare number in a memo is a quantity or a year; a number introduced by
    the word "check" is an instrument, and a token mixing letters and digits
    is a document code. Used for the conflict rule: an entry that names one
    document is not the other half of a row that names a different one, even
    when the amount and the date would otherwise allow it.
    """
    coded = {token for token in _ref_tokens(text) if any(ch.isalpha() for ch in token)}
    return {t for t in (_instrument_tokens(text) | coded) if t}


def _rail_of(description: str, *, bank_initiated: bool) -> str:
    """Which rail the bank's own wording names. The window follows from it.

    BANK-INITIATED FIRST. A row with no counterparty and no reference whose
    wording is the bank's own charge language is a charge the bank levied on
    itself, whatever instrument the words mention: `CHECK PRINTING FEE` is a
    fee for printing checks, not a check with a twelve-day float, and
    `ACH ORIGINATION FEE` is not an ACH credit. Reading the instrument word
    first gave a mis-keyed fee row the whole cheque float to find a partner
    in (the train:184 class), which is how a duplicated fee twin twelve days
    away came to be read as the missing fee's mis-keyed version.
    """
    if bank_initiated:
        return "bank"
    if _CHEQUE_ROW.search(description):
        return "cheque"
    if _CARD_ROW.search(description):
        return "card"
    if _ACH_ROW.search(description):
        return "ach"
    if _FEE_WORDING.search(description):
        return "bank"
    return "unknown"


def _chart(public: dict) -> dict:
    """account name -> type, from `accounts.csv`."""
    out: dict[str, str] = {}
    for record in csv.DictReader(io.StringIO(public.get(ACCOUNTS_FILE, ""))):
        name = (record.get("account") or "").strip()
        if name:
            out[name] = (record.get("type") or "").strip().lower()
    return out


def _parties(public: dict) -> dict:
    """party name -> (role, default account), from the two master files."""
    out: dict[str, tuple] = {}
    for file_name, column in ((CUSTOMERS_FILE, "customer"), (VENDORS_FILE, "vendor")):
        for record in csv.DictReader(io.StringIO(public.get(file_name, ""))):
            name = (record.get(column) or "").strip()
            if not name:
                continue
            account = (record.get("default_account") or "").strip()
            out[name] = (column, account or None)
    return out


def _policy_account(policy_text: str, section: str, chart: set) -> str | None:
    """The one chart account a policy section names in backticks.

    The agent reads the same sentence; this reads the same sentence. Two
    accounts in the section, or none, means the policy does not decide the
    posting and the checker must not pretend it does.
    """
    lines = policy_text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().startswith(section)), None)
    if start is None:
        return None
    body: list[str] = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    named = sorted({token for token in re.findall(r"`([^`]+)`", "\n".join(body)) if token in chart})
    return named[0] if len(named) == 1 else None


def _counterparties(description: str, parties: dict) -> list:
    """Every master-file party the row's wording names, longest name wins."""
    upper = description.upper()
    hits = [name for name in parties if name.upper() in upper]
    return sorted(n for n in hits if not any(o != n and n.upper() in o.upper() for o in hits))


def ledger_movements(ledger_text: str, bank_account: str, *, equity_accounts: frozenset,
                     period_start: str, period_end: str) -> tuple:
    """Every bank-account movement the ledger records, in the period and just
    before it.

    Returns `(movements, opening_entries, out_of_period)`. The carry-forward
    balance entry is dropped because it is not a movement: the statement
    prints it as an opening row with no debit and no credit, and pairing the
    two would invent a match. It is recognised the way a reader recognises it
    — it posts to an account `accounts.csv` types as equity — with a shape
    fallback for a world that publishes no chart.

    An entry dated inside `CARRY_FORWARD_DAYS` before the period is kept, and
    flagged `in_period=False`: last month's cheque clearing in this month's
    statement is a legitimate pairing (`## Outstanding checks` describes the
    other half of it), and a checker that refused it would report a phantom
    missing entry every time a real world carried one. Such an entry is never
    itself a repair candidate: it answers a row or it is somebody else's
    reconciliation. Anything further out is reported.
    """
    movements: list[LedgerMovement] = []
    opening: list[str] = []
    outside: list[str] = []
    pending: list = []          # (date, payee, narration, [legs])
    carry_first = (_day(period_start) - _date.resolution * CARRY_FORWARD_DAYS).isoformat()

    def close():
        if not pending:
            return
        date, payee, narration, legs = pending.pop()
        bank = sum((v for a, v in legs if a == bank_account), Decimal("0"))
        if not any(a == bank_account for a, _ in legs):
            return
        is_opening = (any(a in equity_accounts for a, _ in legs)
                      if equity_accounts else (date <= period_start and len(legs) > 2))
        if is_opening and date <= period_start:
            opening.append(f"{date} {payee} {narration!r}")
            return
        in_period = period_start <= date <= period_end
        if not in_period and not (carry_first <= date < period_start):
            outside.append(f"{date} {payee} {narration!r} {bank:+.2f}")
            return
        movements.append(LedgerMovement(
            len(movements), date, bank, payee, narration,
            tuple(sorted((a, v) for a, v in legs)),
            tuple(sorted({a for a, _ in legs if a != bank_account})),
            in_period))

    for line in ledger_text.splitlines():
        header = _ENTRY.match(line)
        if header:
            close()
            pending.append((header.group(1), header.group(2), header.group(3) or "", []))
            continue
        posting = _POSTING.match(line)
        if posting and pending:
            pending[-1][3].append((posting.group(1), _amount(posting.group(2))))
            continue
        if not line.strip() or not line.startswith(" "):
            close()
    close()
    return tuple(movements), tuple(opening), tuple(outside)


def statement_rows(statement_text: str, *, period_start: str, period_end: str) -> tuple:
    """Every dated movement the bank printed, signed on the bank account.

    Returns `(rows, opening_rows, out_of_period)`. A row with neither a debit
    nor a credit is the carried-forward balance, which asserts a number rather
    than reporting a movement.
    """
    reader = csv.DictReader(io.StringIO(statement_text))
    header = tuple(name.strip() for name in (reader.fieldnames or ()))
    if header != STATEMENT_COLUMNS:
        raise ValueError(f"{STATEMENT_FILE}: columns {header} are not {STATEMENT_COLUMNS}")
    rows: list[StatementRow] = []
    opening: list[str] = []
    outside: list[str] = []
    for record in reader:
        date = (record.get("date") or "").strip()
        if not date:
            continue
        debit, credit = (record.get("debit") or "").strip(), (record.get("credit") or "").strip()
        description = (record.get("description") or "").strip()
        if not debit and not credit:
            opening.append(f"{date} {description}")
            continue
        try:
            amount = (_amount(credit) if credit else Decimal("0")) - (_amount(debit) if debit else Decimal("0"))
        except InvalidOperation as exc:
            raise ValueError(f"{STATEMENT_FILE}: row {date} carries an unreadable amount") from exc
        if not (period_start <= date <= period_end):
            outside.append(f"{date} {description} {amount:+.2f}")
            continue
        rows.append(StatementRow(len(rows), date, description, (record.get("reference") or "").strip(), amount))
    return tuple(rows), tuple(opening), tuple(outside)


def _archive_reference_rows(archive_text: str) -> list:
    """(reference, description) for every archive row, leniently.

    The archive is prior-period evidence: it is read to find out whether a
    reference is REUSED, and for nothing else. A malformed archive costs the
    reference test its archive half rather than raising.
    """
    out = []
    try:
        reader = csv.DictReader(io.StringIO(archive_text or ""))
        for record in reader:
            if not (record.get("date") or "").strip():
                continue
            out.append(((record.get("reference") or "").strip(), (record.get("description") or "").strip()))
    except csv.Error:
        return out
    return out


# --------------------------------------------------------------------------
# the admissibility graph
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _RowFacts:
    """Everything the public evidence says about one row, before matching."""

    rail: str
    ref: str                 # normalised reference, "" when the row carries none
    decisive: bool           # the reference is quoted once, so it may decide
    parties: tuple           # master-file parties the wording names
    fee: bool                # bank-initiated wording with no party and no reference
    counterparty: str | None
    account: str | None      # what the repair would post to, None when unattributable
    notes: tuple             # why the attribution failed, when it did
    authority: str = ""      # which public rule fixed the account, quoted by name
    ref_role: str = REF_MEMO  # the reference ontology's role for this row's reference
    reference: str = ""      # the reference column as printed (a payment reference keeps its words)
    presents: tuple = ()     # the instruments the statement shows on this row (see `_outstanding_eligible`)


@dataclass(frozen=True)
class _Edge:
    row: int
    mov: int
    kind: str                # settle | alter
    basis: str               # reference | amount | policy | counterparty
    cost: int                # 0 for a settlement, 1 for an alteration
    agreement: int = 0       # alterations only: 1 when the entry carries the row's own day AND wording

    @property
    def weight(self) -> int:
        """The objective is lexicographic — fewest alterations, then the most
        day-and-wording agreement between an altered entry and its row. One
        integer carries both: an alteration outweighs every agreement a
        component can hold (AGREEMENT_SCALE > 2 x the widest component)."""
        return self.cost * AGREEMENT_SCALE - self.agreement


AGREEMENT_SCALE = 10_000
_WORDS = re.compile(r"[a-z0-9]+")


def _wording(text: str) -> str:
    """Case- and punctuation-insensitive wording: `"ACH ORIGINATION FEE"` and
    `"ACH origination fee"` are one wording."""
    return " ".join(_WORDS.findall(text.lower()))


def _reference_census(rows, archive_rows, movements, *, evidenced=frozenset()) -> tuple:
    """How often each normalised reference is quoted, on each side.

    Documents: the current statement and the archive, reference column and
    description alike (a cheque row prints the number in both). Ledger: the
    entries that touch the bank account. An entry that does not touch the
    bank cannot be the other half of a bank row, so the sale entry and its
    cost-of-goods twin quoting one invoice number do not make that number
    ambiguous.

    `evidenced` is what the advices declare, because the census has to count
    the key `_row_facts` will look up: a row's IDENTITY, not its whole
    reference column.
    """
    documents: dict = {}
    ledger: dict = {}
    # A MULTI-WORD identity is counted as one token — the whole addendum, the
    # key `_row_facts` looks up — beside the tokens inside it, which
    # `_ref_tokens` has already counted. A single-token identity (a cheque
    # number, a trace id) is in that census already and is not counted twice.
    # A reference that is no identity is counted as its tokens and nothing
    # else: `SI-3104 SI-3102` is two invoice numbers, which is all it is.
    addenda: set = set()
    for row in rows:
        for token in _ref_tokens(row.reference) | _ref_tokens(row.description):
            documents[token] = documents.get(token, 0) + 1
        identity = _identity_reference(row.reference, f"{row.description} {row.reference}", evidenced)
        if identity and _reference_words(identity):
            documents[_norm_ref(identity)] = documents.get(_norm_ref(identity), 0) + 1
            addenda.add(identity)
    for reference, description in archive_rows:
        for token in _ref_tokens(reference) | _ref_tokens(description):
            documents[token] = documents.get(token, 0) + 1
        identity = _identity_reference(reference, f"{description} {reference}", evidenced)
        if identity and _reference_words(identity):
            documents[_norm_ref(identity)] = documents.get(_norm_ref(identity), 0) + 1
            addenda.add(identity)
    # Distinct SHAPES, not entries. Two copies of one entry are one candidate
    # pairing, so a doubled entry must not make its own cheque number look
    # reused — that would switch off the reference exactly where the books
    # carry the surplus the reference identifies.
    for shape in {m.shape for m in movements}:
        for token in _ref_tokens(f"{shape[2]} {shape[3]}"):
            ledger[token] = ledger.get(token, 0) + 1
        for reference in addenda:
            if _mentions(f"{shape[2]} {shape[3]}", reference):
                ledger[_norm_ref(reference)] = ledger.get(_norm_ref(reference), 0) + 1
    return documents, ledger


def _precedents(movements, parties) -> dict:
    """How the books ALREADY post this counterparty's money, by direction.

    Since version 7 this CORROBORATES `## Payments to suppliers` rather than
    standing in for it: the policy section is the public rule and this is the
    month's own evidence that the books agree with it. Where the two disagree,
    or where the books show two treatments for one party and one direction, the
    row is refused rather than guessed.

    `default_account` in the master files is where the party's TRADE lands —
    an inventory supplier's goods go to `Assets:Inventory` — and that is not
    where a payment to that supplier lands: the invoice was booked when the
    goods arrived, so the cheque settles `Liabilities:AP`. Reading the master
    file as if it named the payment account posted the same money to stock
    twice, and the full repair key is what made that visible;
    the old `(kind, signed bank amount)` comparison could not see it.

    So the counter account is read the way a bookkeeper reads it: how does
    this ledger already book money going the same way to this party? Keyed by
    `(party, money out?)` because a receipt from a customer and a refund to
    one are not the same posting.
    """
    seen: dict = {}
    for movement in movements:
        if movement.payee in parties and len(movement.other_accounts) == 1:
            seen.setdefault((movement.payee, movement.amount < 0), set()).add(movement.other_accounts[0])
    return seen


def _supplier_payment_account(counterparty, row, *, parties, chart, payables_account):
    """`## Payments to suppliers`, applied: the account a payment to this
    supplier lands on, and the sentence that says so — or `(None, "")`.

    The section is a PUBLIC RULE and is read first, ahead of what this month's
    entries happen to do (the verifier's follow-up B). It fixes
    the answer from three published facts and no inference: the row moves money
    out, `vendors.csv` gives the supplier a `default_account`, and
    `accounts.csv` types that account. An asset means the goods were taken into
    it on arrival and the payable was raised then, so the payment settles the
    payable the section names in backticks; an expense means no payable was
    raised and the payment IS the expense. Reading the master file as if
    `default_account` were the payment account posted an inventory supplier's
    cheque to stock a second time, which is the defect this section closes.
    """
    if row.amount >= 0 or payables_account is None or not counterparty:
        return None, ""
    role, default_account = parties.get(counterparty, (None, None))
    if role != "vendor" or not default_account:
        return None, ""
    kind = chart.get(default_account, "")
    if kind == "asset":
        return payables_account, (f"{POLICY_FILE} {SUPPLIER_PAYMENT_SECTION}: {VENDORS_FILE} books "
                                  f"{counterparty}'s purchases to {default_account}, which {ACCOUNTS_FILE} "
                                  f"types as an asset, so the payable was raised when the goods arrived and "
                                  f"this payment settles it in {payables_account}")
    if kind == "expense":
        return default_account, (f"{POLICY_FILE} {SUPPLIER_PAYMENT_SECTION}: {VENDORS_FILE} books "
                                 f"{counterparty}'s purchases to {default_account}, which {ACCOUNTS_FILE} "
                                 f"types as an expense, so no payable was raised and the payment is the "
                                 f"expense")
    return None, ""


def _row_facts(row, *, parties, chart, fee_account, documents, ledger, precedents,
               payables_account=None, evidenced=frozenset()) -> _RowFacts:
    named = _counterparties(row.description, parties)
    surface = f"{row.description} {row.reference}"
    # The identity this row NAMES, where the evidence declares one: the
    # reference an advice calls a payment reference, the cheque the wording
    # introduces, or the one trace id the column prints. That, and not the
    # whole column, is what the census counts and what an entry has to quote.
    # A row whose reference names no identity keeps the column as its
    # reference and takes a document or unknown role.
    identity = _identity_reference(row.reference, surface, evidenced)
    ref = _norm_ref(identity or row.reference)
    reference = identity or row.reference
    # The four roles are total over rows: a row carrying no reference-shaped
    # token at all is MEMO, which decides nothing, and needs no fifth case.
    # Classified from the column AS PRINTED: an identity may be several words,
    # and the normalised `ref` no longer shows that.
    ref_role = reference_role(row.reference, surface, evidenced=evidenced)
    # What the statement SHOWS on this row, for the in-transit rule: every
    # cheque number the row names, and the row's declared identity when the
    # documents print it exactly once — a reused identifier could be a third
    # payment's, so it presents nothing and the reading stays open. A
    # reference that names no payment presents NOTHING: seeing an invoice list
    # once on the statement and once in the books does not exclude an
    # unrecorded receipt standing beside a deposit in transit.
    presents = tuple(sorted(_instrument_tokens(surface)))
    if identity and _norm_ref(identity) not in presents and documents.get(ref, 0) == 1:
        presents += (identity,)
    # Only an INSTRUMENT may dominate: a cheque number or a bank trace id names
    # one cash movement, so a globally unique one decides a pairing outright.
    # An invoice or order id names the DOCUMENT a payment applies to and several
    # receipts may quote one, so it is supporting evidence and never dominant.
    # See `reference_role` for the whole ontology.
    decisive = (ref_role == REF_INSTRUMENT and documents.get(ref, 0) <= 1 and ledger.get(ref, 0) <= 1)
    fee = not ref and not named and bool(_FEE_WORDING.search(row.description))
    counterparty = named[0] if len(named) == 1 else None
    account = None
    authority = ""
    notes: list[str] = []
    if counterparty:
        booked = precedents.get((counterparty, row.amount < 0), set())
        ruled, sentence = _supplier_payment_account(counterparty, row, parties=parties, chart=chart,
                                                    payables_account=payables_account)
        if len(booked) > 1:
            # Two treatments for one party and one direction: the refusal
            # stands whatever the policy says, because the books themselves
            # disagree about what this money is.
            notes.append(f"{LEDGER_FILE} books money {'out to' if row.amount < 0 else 'in from'} "
                         f"{counterparty} to {len(booked)} different accounts ({', '.join(sorted(booked))}), "
                         f"so which one {row} belongs to is not decidable from the public files")
        elif ruled is not None:
            # The public rule decides; this month's entries CORROBORATE it.
            account, authority = ruled, sentence
            if len(booked) == 1 and next(iter(booked)) != ruled:
                account = None
                notes.append(f"{sentence}, and {LEDGER_FILE} books money out to {counterparty} to "
                             f"{next(iter(booked))} instead; the rule and the books disagree about {row}, "
                             f"so it is not decidable from the public files")
            elif len(booked) == 1:
                authority = f"{sentence}; {LEDGER_FILE} already books money out to {counterparty} there"
        elif len(booked) == 1:
            account = next(iter(booked))
            authority = (f"{LEDGER_FILE} already books money {'out to' if row.amount < 0 else 'in from'} "
                         f"{counterparty} to {account}")
        else:
            # No public rule for this direction and no precedent in this
            # month's books: the master file's own account is all there is.
            account = parties.get(counterparty, (None, None))[1]
            if account:
                authority = f"{CUSTOMERS_FILE}/{VENDORS_FILE} gives {counterparty} the account {account}"
    if len(named) > 1:
        notes.append(f"{row} names {len(named)} master-file parties ({', '.join(named)}); the counterparty "
                     f"of the missing entry is not decidable")
    if account is None and fee and fee_account is not None:
        account = fee_account
        authority = f"{POLICY_FILE} {BANK_FEE_SECTION} names {fee_account}"
    contested = bool(counterparty) and (len(precedents.get((counterparty, row.amount < 0), set())) > 1
                                        or (account is None and notes))
    if account is None and not contested:
        notes.append(f"{row} has no matching entry and names no party from {CUSTOMERS_FILE}/{VENDORS_FILE}; "
                     f"no rule in {POLICY_FILE} attributes it either, so the counterparty and account "
                     f"cannot be attributed from the public files")
    elif account is not None and account not in chart and chart:
        notes.append(f"{row} attributes to {account}, which {ACCOUNTS_FILE} does not carry")
    return _RowFacts(_rail_of(row.description, bank_initiated=fee), ref, decisive, tuple(named), fee, counterparty,
                     account, tuple(notes), authority, ref_role, reference, presents)


def _direction_ok(row, movement) -> bool:
    """A credit row is not answered by a debit entry, whatever it quotes."""
    return (row.amount < 0) == (movement.amount < 0)


def _role_ok(facts, movement, parties) -> bool:
    """Account role: a row that names one master party is not answered by an
    entry booked against a DIFFERENT master party. An entry whose payee is
    nobody the masters list (the bank itself, an accrual) stays admissible —
    the masters are not a closed world."""
    if len(facts.parties) != 1:
        return True
    return not (movement.payee in parties and movement.payee != facts.parties[0])


def _policy_class_ok(facts, movement, fee_account) -> bool:
    """Bank-fee attribution names an account CLASS, not a row.

    A bank-initiated row (the bank's own wording, no counterparty, no
    reference) belongs to the account the policy names, so the entries that
    can answer it are the entries booked there — all of them, in whatever
    order the month printed them. When the policy names no account the rule
    has nothing to say and does not constrain.
    """
    if not facts.fee or fee_account is None:
        return True
    return fee_account in movement.other_accounts


def _time_direction_ok(row, movement, rail) -> bool:
    """The bank processes a transaction ON OR AFTER the day it happens.

    So for a customer or vendor rail — cheque, ACH, card, wire — a ledger
    entry dated AFTER the row cannot be that row's transaction, whatever
    else agrees. `## Dates` says this in the policy the agent reads, and it
    is the rule that stops a deposit in transit quoting an invoice from
    being accused of carrying the wrong amount for an earlier row that
    quotes the same invoice (the train:715 class): a receipt recorded on the
    29th is not the deposit the bank credited on the 25th, however loudly
    both name SI-1247.

    A charge the bank levies itself is different and keeps the small
    SYMMETRIC slack: there is no transaction date of the customer's own to
    be earlier than. The bank dates the charge and the books copy that date,
    so the two disagree only by a month end falling across a weekend, and
    the disagreement can fall either way — the bookkeeper may have accrued
    the charge a day early as easily as the bank applied it a day late.
    """
    if rail == "bank":
        return True
    return movement.date <= row.date


def _timing_ok(row, movement, window, *, referenced: bool) -> bool:
    gap = _gap(movement.date, row.date)
    if referenced:
        return gap <= REFERENCE_FLOAT_DAYS
    return gap <= window


def _build_edges(rows, movements, facts_by_row, *, parties, fee_account, tie_break=False) -> list:
    """Every pairing the public evidence admits, with reference dominance
    applied afterwards rather than as a first pass that wins by running
    first."""
    edges: list[_Edge] = []
    for row in rows:
        facts = facts_by_row[row.index]
        window = RAIL_WINDOW_DAYS.get(facts.rail, MATCH_WINDOW_DAYS)
        for movement in movements:
            if not _direction_ok(row, movement):
                continue
            if not _time_direction_ok(row, movement, facts.rail):
                continue
            if not _role_ok(facts, movement, parties):
                continue
            if not _policy_class_ok(facts, movement, fee_account):
                continue
            quoted = bool(facts.ref) and _mentions(movement.text, facts.reference)
            # A CONFLICT: this row names a reference and the entry names some
            # other document or instrument instead. What the conflict is worth
            # depends on the roles:
            #
            #   the ROW naming an INSTRUMENT is a claim about which cash
            #   movement this is, so an entry naming some other document or
            #   instrument is not that movement: the conflict prunes
            #   everything (settlement and alteration alike);
            #   the ROW naming a DOCUMENT is a claim about which receivable or
            #   payable the money applies to, so an entry naming another
            #   document prunes a SETTLEMENT — two documents are not one
            #   payment of one amount — but never an alteration, where it
            #   would be the whole basis of the accusation (the second
            #   verifier's repro: adding an invoice number to a row must not
            #   turn two readings into one);
            #   a row with an UNRECOGNISED code, or none, prunes nothing in
            #   either direction: what the entry names is then supporting
            #   evidence, not an identity claim the row can contradict.
            conflict = bool(facts.ref) and not quoted and bool(_document_tokens(movement.text))
            instrument_conflict = conflict and facts.ref_role == REF_INSTRUMENT
            document_conflict = conflict and facts.ref_role == REF_DOCUMENT
            if instrument_conflict:
                continue        # the entry names another instrument or document; it is not this row's movement
            if movement.amount == row.amount:
                if document_conflict:
                    continue    # two documents are not one payment of one amount
                if _timing_ok(row, movement, window, referenced=quoted and facts.decisive):
                    edges.append(_Edge(row.index, movement.index, "settle",
                                       "reference" if quoted else "amount", 0))
                continue
            # a booked amount that differs: an alteration, and only where
            # something other than the amount ties the two together; a
            # document conflict falls through — the accusation must stand on
            # the counterparty or the policy class, never on the invoice id
            if quoted and facts.ref_role == REF_INSTRUMENT:
                # An instrument names ONE cash movement, so quoting it is a
                # claim that these two records are that movement and the figure
                # is wrong. The rail still says when it can have cleared: a wide
                # float belongs to a settlement of the same amount, not to a
                # claim that the books hold the wrong number — an entry a week
                # after the row and a day before the cut-off is a deposit in
                # transit, and `## Deposits in transit` says so.
                basis, alter_window = "reference", window
            elif facts.fee and fee_account is not None and fee_account in movement.other_accounts:
                basis, alter_window = "policy", window
            elif len(facts.parties) == 1 and movement.payee == facts.parties[0]:
                # A quoted INVOICE id is supporting evidence here and nothing
                # more: several receipts, a refund and a deposit in transit may
                # all apply to one invoice, so it cannot by itself say that two
                # records of different amounts are one payment. The pairing has
                # to stand on the counterparty, and it keeps the counterparty's
                # narrow window rather than the reference's wide one.
                basis, alter_window = "counterparty", ALTER_WINDOW_DAYS
            else:
                continue
            if _gap(movement.date, row.date) <= alter_window:
                # Two bank fees three days apart, one or both mis-keyed, admit
                # two maximum readings of equal cost; a bookkeeper pairs the
                # charge with the entry that carries its own name AND day
                # before accusing the other one. That full agreement — the
                # bank describing the charge in the entry's own words on the
                # entry's own day — is public evidence on both sides and
                # breaks the tie. Either half alone decides nothing: a same-day
                # coincidence (two card payments to one vendor around one row)
                # and a same-wording entry booked on another day (one fee
                # entry between two fee rows) both stay undecidable, because
                # the competing reading then has as much evidence as this one.
                # Where the rows agree equally (two "Monthly service fee" rows
                # on one day) the tie stands and the verdict is ambiguous.
                agreement = int(tie_break and movement.date == row.date
                                and _wording(movement.narration) == _wording(row.description))
                edges.append(_Edge(row.index, movement.index, "alter", basis, 1, agreement))

    # Reference dominance, conditional: where a row carries a reference the
    # whole public evidence set quotes once and something compatible answers
    # it, that pairing is the pairing — and the entry it names is not free to
    # answer anything else. A reused reference gets neither half.
    #
    # A dominance read off an ALTERATION prunes alterations only. The
    # alteration says "these two are one event and the figure is wrong"; a
    # SETTLEMENT of the named entry against some other row says "these two
    # are one event and the figure agrees", which is the identity
    # `## Matching the statement to the ledger` declares and is stronger
    # evidence than a reference quoted elsewhere in the month. Letting the
    # alteration prune it emptied the named entry's own pairing and then won
    # the matching it had just emptied. A dominance read off a SETTLEMENT —
    # exact amount AND a reference quoted once in the whole evidence set —
    # still decides both halves outright.
    dominant = {(e.row, e.mov) for e in edges
                if e.basis == "reference" and facts_by_row[e.row].decisive}
    settled_pairs = {(e.row, e.mov) for e in edges if e.kind == "settle"}
    for pairs, prunes_settlements in ((dominant & settled_pairs, True), (dominant - settled_pairs, False)):
        if not pairs:
            continue
        rows_decided = {r for r, _ in pairs}
        movs_decided = {m for _, m in pairs}
        edges = [e for e in edges
                 if (e.kind == "settle" and not prunes_settlements)
                 or (e.row, e.mov) in pairs
                 or (e.row not in rows_decided and e.mov not in movs_decided)]
    return edges


# --------------------------------------------------------------------------
# matchings
# --------------------------------------------------------------------------

def _components(row_ids, mov_ids, edges) -> list:
    """The connected components of the admissibility graph.

    Matchings compose across components, so each is enumerated on its own:
    the search stays small, and an ambiguity in one corner of the month does
    not multiply the readings of every other corner. Two ledger entries with
    the same visible shape have the same admissibility and therefore land in
    the same component, which is what lets the duplicate rule see its twin.
    """
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for r in row_ids:
        find(("r", r))
    for m in mov_ids:
        find(("m", m))
    for e in edges:
        union(("r", e.row), ("m", e.mov))
    groups: dict = {}
    for node in list(parent):
        groups.setdefault(find(node), []).append(node)
    out = []
    for members in groups.values():
        out.append((sorted(r for kind, r in members if kind == "r"),
                    sorted(m for kind, m in members if kind == "m")))
    return sorted(out)


def _max_cardinality(comp_rows, adjacency) -> int:
    """Kuhn's algorithm. Thirty rows: the simple one is the right one."""
    pair: dict = {}

    def augment(row, seen) -> bool:
        for mov in adjacency.get(row, ()):
            if mov in seen:
                continue
            seen.add(mov)
            if mov not in pair or augment(pair[mov], seen):
                pair[mov] = row
                return True
        return False

    return sum(1 for row in comp_rows if augment(row, set()))


def _optimal_readings(comp_rows, edges_by_row, describe, *, rank=False) -> tuple:
    """Every reading of one component the public evidence admits, keyed by
    what it MEANS. Returns `(readings, incomplete)`.

    `describe(assignment)` returns the semantic reading — the repair
    multiset, the outstanding items and whatever the reading leaves
    UNEXPLAINED — so two matchings that differ only in which of two
    indistinguishable entries was consumed collapse to one key.

    Two constraints select the readings, and only two:

    **Settlements are forced.** `## Matching the statement to the ledger`
    declares that a row and an entry of the same amount and counterparty
    inside the clearing window ARE one transaction, so a reading that leaves
    such a pairing on the table is not a competing history — it is a refusal
    to read the evidence. Only matchings that realise the greatest possible
    number of settlements are considered.

    **A reading must explain the whole month.** Every row is settled,
    restated or reported missing; every ledger entry is settled, restated,
    a surplus copy of a twin, or a timing difference the policy names. A
    reading that strands an entry nothing accounts for is not a history of
    this month at all, and is dropped rather than ranked.

    What is NOT a constraint any more: matching cardinality, and "fewest
    alterations". Both were parsimony priors that no public text promises,
    and both silently erased the competing history the T42 review asked for
    — "the row is missing from the books and this entry is a duplicate of
    its twin" loses on cardinality to "the row is this entry, mis-keyed",
    every time, whatever the evidence says. Among the readings that survive
    the two constraints above, DISAGREEMENT IS AMBIGUITY: nothing here
    prefers the cheaper accusation.

    `rank=True` (the diagnostic prior only) re-applies the old lexicographic
    ordering — fewest alterations, then the most day-and-wording agreement —
    to the survivors, which is what `tie_break` reports after an ambiguity.

    The third return value is how many ASSIGNMENTS were enumerated at all —
    occurrence-level matchings, before they are quotiented by what they mean.
    Diagnostic only (`structure()` reports it so the CI sentinel set can
    require a world where more than one matching had to be compared); the
    verdict never reads it.
    """
    settle_by_row = {row: [e for e in edges_by_row.get(row, ()) if e.kind == "settle"] for row in comp_rows}
    settle_target = _max_cardinality(comp_rows, {r: [e.mov for e in es] for r, es in settle_by_row.items()})
    order = sorted(comp_rows, key=lambda r: (len(edges_by_row.get(r, ())), r))
    readings: dict = {}
    incomplete: dict = {}
    assignments = [0]
    budget = [MAX_SEARCH_NODES]
    used: set = set()
    chosen: dict = {}

    def walk(k, settled, weight):
        budget[0] -= 1
        if budget[0] <= 0:
            raise _Exhausted("the matching enumeration exceeded its node budget")
        if settled + (len(order) - k) < settle_target:
            return
        if k == len(order):
            if settled != settle_target:
                return
            assignments[0] += 1
            reading = describe(dict(chosen))
            target = incomplete if reading[3] else readings
            target.setdefault(reading[0], (reading, weight))
            if len(readings) > MAX_READINGS:
                raise _Exhausted("the component admits more readings than the budget lists")
            if len(incomplete) > MAX_READINGS:
                incomplete.pop(next(iter(incomplete)))
            return
        row = order[k]
        for edge in sorted(edges_by_row.get(row, ()), key=lambda e: (e.weight, e.mov)):
            if edge.mov in used:
                continue
            used.add(edge.mov)
            chosen[row] = edge
            walk(k + 1, settled + (edge.kind == "settle"), weight + edge.weight)
            del chosen[row]
            used.discard(edge.mov)
        walk(k + 1, settled, weight)

    walk(0, 0, 0)
    if rank and readings:
        best = min(weight for _reading, weight in readings.values())
        readings = {key: value for key, value in readings.items() if value[1] == best}
    return ({key: reading for key, (reading, _weight) in readings.items()},
            {key: reading for key, (reading, _weight) in incomplete.items()},
            assignments[0])


# --------------------------------------------------------------------------
# reading a matching back as accounting
# --------------------------------------------------------------------------

def _master(payee, parties) -> str | None:
    """A payee only counts as a counterparty when the master files carry it.

    The bank is not a customer and not a vendor, so a bank charge names no
    counterparty on either side of the comparison with a planted item.
    """
    return payee if payee in parties else None


def _two_sided(bank_account, counter, amount) -> tuple | None:
    """The postings an added or restated entry carries: the bank leg the row
    fixes and the counter leg the master files or the policy fix. When the
    counter account is not attributable there is no posting multiset to
    state, and the key says so rather than dropping the field."""
    if not bank_account or counter is None:
        return None
    return ((bank_account, amount), (counter, -amount))


def _missing_repair(row, facts, bank_account) -> Repair:
    # Contract change B: the entry the books lack is posted on the BANK's
    # date, because the transaction date went missing with the entry and the
    # statement's date is the only one in evidence. `## Dates` says so.
    return Repair("missing_entry", row.date, row.amount, row.description, row.reference,
                  facts.counterparty, facts.account, notes=facts.notes, authority=facts.authority,
                  postings=_two_sided(bank_account, facts.account, row.amount),
                  bank_account=bank_account, row_date=row.date,
                  detail=f"the statement shows {row} and the books record nothing against it")


def _wrong_repair(row, facts, movement, edge, parties, bank_account) -> Repair:
    account = movement.other_accounts[0] if len(movement.other_accounts) == 1 else None
    # The entry is already in the books and keeps its own date; only the
    # figure is restated, so the repair is dated where the entry is dated —
    # which is where the scorer's predicate for an altered item looks.
    return Repair("wrong_amount", movement.date, row.amount, row.description, row.reference,
                  _master(movement.payee, parties) or facts.counterparty, account,
                  booked_amount=movement.amount, basis=edge.basis,
                  postings=_two_sided(bank_account, account, row.amount),
                  bank_account=bank_account, row_date=row.date,
                  detail=(f"the bank shows {row.amount:+.2f} and the books show {movement.amount:+.2f} for "
                          f"{movement}"))


def _duplicate_repair(movement, copies, surplus, parties, bank_account) -> Repair:
    return Repair("duplicate", movement.date, movement.amount, movement.narration, "",
                  _master(movement.payee, parties),
                  movement.other_accounts[0] if len(movement.other_accounts) == 1 else None,
                  copies=copies, expected_copies=copies - surplus,
                  postings=tuple(movement.legs), bank_account=bank_account,
                  detail=(f"the books carry {copies} identical copies of {movement}; the statement shows "
                          f"the movement {copies - surplus} time(s), so {surplus} copy must go"))


def _outstanding_eligible(movement, period_end, fee_account, presented, evidenced=frozenset()) -> str | None:
    """Can this stranded entry read as a timing difference? The reason it
    cannot, or None.

    The policy names exactly two: `## Outstanding checks` (a check issued and
    recorded that the bank has not cleared) and `## Deposits in transit`
    (cash recorded as received that the statement has not yet shown). Both
    are about a customer or vendor movement the bank has not got to yet, so:

    * a charge the bank levies ITSELF is never one. The bank dates its own
      charge; there is nothing in flight. An entry in the fee class that no
      row answers means the books carry a charge the bank never made, which
      is a difference, not a timing difference;

    * an instrument the statement SHOWS is not outstanding. If a row this
      reading — or any reading, for a row nothing can answer — reports as
      unrecorded names the very cheque this entry names, and the entry is
      dated on or before that row, then
      the bank has seen the instrument: `presented` carries those tokens,
      and calling the entry outstanding would be reading the same cheque as
      both cleared and uncleared;

    * and the entry has to be near enough the cut-off to be in flight at
      all, which is what `OUTSTANDING_WINDOW_DAYS` is for.
    """
    if not movement.in_period:
        return "carry-forward"          # last month's entry, and last month's reconciliation
    if fee_account is not None and fee_account in movement.other_accounts:
        return (f"{LEDGER_FILE} records {movement} against {fee_account} and no statement row answers it; a "
                f"charge the bank levies itself is dated by the bank, so this is not a timing difference")
    for token, row_date in presented:
        # a cheque number the entry names, or a trace id or multi-word
        # identifier the entry quotes (`_quotes_identity`): either way the
        # bank has shown the instrument
        if _quotes_identity(movement.text, token, evidenced):
            # whichever way the dates fall: on or before the row, the cheque
            # has been presented and is not in flight; after the row, the
            # books date a cheque later than the bank cleared it, which is a
            # difference, not a timing item (the verifier's D1 case)
            return (f"{LEDGER_FILE} records {movement}, which names {token}; the statement's {row_date} row "
                    f"shows {token} cleared, so the instrument has been presented and the entry is not "
                    f"outstanding")
    if not (movement.date <= period_end and _gap(movement.date, period_end) <= OUTSTANDING_WINDOW_DAYS):
        return (f"{LEDGER_FILE} records {movement}, no statement row answers it, and it is more than "
                f"{OUTSTANDING_WINDOW_DAYS} days before the {period_end} cut-off; it reads neither "
                f"as an outstanding item nor as a difference the statement evidences")
    return None


def _describe(rows, movements, facts_by_row, comp_rows, comp_movs, period_end, *, parties, fee_account,
              bank_account, presented_everywhere=(), evidenced=frozenset()):
    """Build the `describe` callback one component needs."""

    def describe(assignment: dict) -> tuple:
        repairs: list[Repair] = []
        outstanding: list[str] = []
        unexplained: list[str] = []
        settled = 0
        # Instruments the statement has shown — every cheque number any row
        # carries, whatever the reading and whichever component the row is
        # in. A cheque the bank has cleared is not in transit, full stop: an
        # entry naming it that is not that row's settlement is a surplus copy
        # or a difference, never a timing item. Computed world-wide because
        # the time-direction rule can sever the edge that would have put row
        # and entry in one component (the verifier's post-dated-cheque case:
        # a component-local set let the checker add a second entry for a
        # cheque and call the first one in transit).
        presented: list = list(presented_everywhere)
        for row_index in comp_rows:
            row, facts = rows[row_index], facts_by_row[row_index]
            edge = assignment.get(row_index)
            if edge is None:
                repairs.append(_missing_repair(row, facts, bank_account))
                presented += [(token, row.date) for token in facts.presents]
            elif edge.kind == "alter":
                repairs.append(_wrong_repair(row, facts, movements[edge.mov], edge, parties, bank_account))
            else:
                settled += 1
        taken = {e.mov for e in assignment.values()}
        matched_shapes: dict = {}
        for mov_index in taken:
            shape = movements[mov_index].shape
            matched_shapes[shape] = matched_shapes.get(shape, 0) + 1
        leftover_shapes: dict = {}
        for mov_index in comp_movs:
            if mov_index in taken:
                continue
            leftover_shapes.setdefault(movements[mov_index].shape, []).append(mov_index)
        for shape in sorted(leftover_shapes, key=lambda s: (s[0], str(s[1]), s[2], s[3])):
            group = leftover_shapes[shape]
            movement = movements[group[0]]
            kept = matched_shapes.get(shape, 0)
            if kept:
                repairs.append(_duplicate_repair(movement, kept + len(group), len(group), parties, bank_account))
                continue
            for mov_index in group:
                stranded = movements[mov_index]
                refused = _outstanding_eligible(stranded, period_end, fee_account, presented, evidenced)
                if refused == "carry-forward":
                    continue
                if refused is None:
                    outstanding.append(f"{stranded} (issued near the cut-off; a timing difference, not an error)")
                else:
                    unexplained.append(refused)
        signature = (tuple(sorted(r.semantic_key() for r in repairs)),
                     tuple(sorted(outstanding)), tuple(sorted(unexplained)))
        return signature, repairs, outstanding, unexplained, settled, assignment

    return describe


# --------------------------------------------------------------------------
# the verdict
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _Evidence:
    """Everything the mounted bytes say, before any matching is attempted."""

    chart: dict
    parties: dict
    fee_account: str | None
    payables_account: str | None
    movements: tuple
    ledger_opening: tuple
    ledger_outside: tuple
    rows: tuple
    statement_opening: tuple
    statement_outside: tuple
    facts_by_row: dict
    # what the mounted advices DECLARE to be payment identifiers: read once
    # off the public bytes and carried, because the outstanding rule needs it
    # to recognise a declared identity as quoted (`_quotes_identity`)
    evidenced: frozenset = frozenset()


def _evidence(public: dict, bank_account: str, period_start: str, period_end: str) -> _Evidence:
    chart = _chart(public)
    parties = _parties(public)
    equity = frozenset(name for name, kind in chart.items() if kind == "equity")
    fee_account = _policy_account(public.get(POLICY_FILE, ""), BANK_FEE_SECTION, set(chart))
    payables_account = _policy_account(public.get(POLICY_FILE, ""), SUPPLIER_PAYMENT_SECTION, set(chart))
    movements, ledger_opening, ledger_outside = ledger_movements(
        public[LEDGER_FILE], bank_account, equity_accounts=equity,
        period_start=period_start, period_end=period_end)
    rows, statement_opening, statement_outside = statement_rows(
        public[STATEMENT_FILE], period_start=period_start, period_end=period_end)
    archive_rows = _archive_reference_rows(public.get(ARCHIVE_FILE, ""))
    # What the mounted advices DECLARE to be payment identifiers, read off the
    # same `public` mapping as everything else. Empty for a pack that mounts
    # no advices, which is every legacy world.
    evidenced = _evidenced_payment_identifiers(public)
    documents, ledger_refs = _reference_census(rows, archive_rows, movements, evidenced=evidenced)
    precedents = _precedents(movements, parties)
    facts_by_row = {row.index: _row_facts(row, parties=parties, chart=chart, fee_account=fee_account,
                                          documents=documents, ledger=ledger_refs, precedents=precedents,
                                          payables_account=payables_account, evidenced=evidenced)
                    for row in rows}
    return _Evidence(chart, parties, fee_account, payables_account, movements, ledger_opening, ledger_outside,
                     rows, statement_opening, statement_outside, facts_by_row, evidenced)


def structure(public: dict, *, bank_account: str, period_start: str, period_end: str) -> dict:
    """The SHAPE of the reconciliation problem, for coverage reporting.

    A distribution-wide differential that only counts violations cannot say
    what it covered: "every wrong-variant family was built
    somewhere" is weaker than "this world had a five-row component with two
    cheapest matchings and both were compared". This reports the structure
    the verdict was computed over — component sizes, admissible edges by
    kind, how many occurrence-level MATCHINGS realise the forced settlements,
    how many distinct semantic readings survive, how many are dropped for
    leaving something unexplained, and how many rows carry a reference of each
    ONTOLOGY ROLE — without repeating the verdict itself.

    Diagnostic only: nothing in production reads it, and like everything
    else here it sees the mounted bytes and nothing more.
    """
    ev = _evidence(public, bank_account, period_start, period_end)
    edges = _build_edges(ev.rows, ev.movements, ev.facts_by_row, parties=ev.parties,
                         fee_account=ev.fee_account, tie_break=False)
    edges_by_row: dict = {}
    for edge in edges:
        edges_by_row.setdefault(edge.row, []).append(edge)
    # every instrument the statement shows, whatever the reading (see describe).
    # `ev.rows`, not a bare `rows`: the name was free in this function and the
    # comprehension raised `NameError` on every call, so `structure()` — and
    # with it `differential_sweep.py`'s whole coverage matrix — never ran.
    presented_everywhere = [(token, row.date) for row in ev.rows for token in ev.facts_by_row[row.index].presents]
    out = {"rows": len(ev.rows), "movements": len(ev.movements),
           "settle_edges": sum(1 for e in edges if e.kind == "settle"),
           "alter_edges": sum(1 for e in edges if e.kind == "alter"),
           "unattributable_rows": sum(1 for f in ev.facts_by_row.values() if f.account is None),
           "bank_initiated_rows": sum(1 for f in ev.facts_by_row.values() if f.fee),
           "decisive_references": sum(1 for f in ev.facts_by_row.values() if f.decisive),
           "reference_roles": {role: sum(1 for f in ev.facts_by_row.values() if f.ref_role == role)
                               for role in REFERENCE_ROLES},
           "policy_attributed_rows": sum(1 for f in ev.facts_by_row.values()
                                         if SUPPLIER_PAYMENT_SECTION in f.authority),
           "components": [], "exhausted": 0}
    for comp_rows, comp_movs in _components([r.index for r in ev.rows], [m.index for m in ev.movements], edges):
        describe = _describe(ev.rows, ev.movements, ev.facts_by_row, comp_rows, comp_movs, period_end,
                             parties=ev.parties, fee_account=ev.fee_account, bank_account=bank_account,
                             presented_everywhere=presented_everywhere, evidenced=ev.evidenced)
        comp_edges = sum(len(edges_by_row.get(r, ())) for r in comp_rows)
        try:
            readings, incomplete, matchings = _optimal_readings(comp_rows, edges_by_row, describe)
        except _Exhausted:
            out["exhausted"] += 1
            out["components"].append({"rows": len(comp_rows), "movements": len(comp_movs),
                                      "edges": comp_edges, "readings": None, "dropped": None,
                                      "matchings": None})
            continue
        out["components"].append({"rows": len(comp_rows), "movements": len(comp_movs), "edges": comp_edges,
                                  "readings": len(readings), "dropped": len(incomplete),
                                  "matchings": matchings})
    return out


def check_identifiable(public: dict, *, bank_account: str, period_start: str,
                       period_end: str, tie_break: bool = False) -> Verdict:
    """Reconcile the mounted files as a bookkeeper would, and report whether
    exactly one reading survives.

    `tie_break=False` (production, the mint-time gate, the sweep): unique
    means unique under the public constraints alone — every settlement the
    declared convention forces, every reading that explains the whole month,
    and nothing else to separate them. `tie_break=True` re-applies the old
    parsimony ordering (fewest alterations, then the day-and-wording
    agreement between an altered entry and its row) as a DECLARED
    RECONCILIATION PRIOR: a sensible ranking for a human
    assistant, not a proof, because no public text promises either that the
    books make as few mistakes as possible or that a mis-keyed entry keeps
    its date and description. It is used only to rank the readings of a
    world already reported ambiguous, and in the fixtures that pin what the
    prior would decide.

    `public` is file name -> text and must be nothing else: a structured fact
    list, a projection object or a bundle would let this function resolve a
    join it is supposed to prove a reader can resolve, so anything that is not
    a string is refused rather than coerced.
    """
    if not isinstance(public, dict):
        raise PublicOnly("check_identifiable takes a mapping of file name to text")
    for name, text in public.items():
        if not isinstance(name, str) or not isinstance(text, str):
            raise PublicOnly(f"{name!r} is {type(text).__name__}, not text; this checker reads the "
                             f"mounted bytes and never a structured fact")
    for required in (LEDGER_FILE, STATEMENT_FILE):
        if required not in public:
            raise ValueError(f"the public files do not include {required}")
    if not (period_start <= period_end):
        raise ValueError(f"the period {period_start}..{period_end} runs backwards")

    ev = _evidence(public, bank_account, period_start, period_end)
    parties, fee_account = ev.parties, ev.fee_account
    movements, ledger_opening, ledger_outside = ev.movements, ev.ledger_opening, ev.ledger_outside
    rows, statement_opening, statement_outside = ev.rows, ev.statement_opening, ev.statement_outside

    ambiguities: list[str] = []
    for note in statement_outside:
        ambiguities.append(f"{STATEMENT_FILE} row {note} is dated outside {period_start}..{period_end}; "
                           f"the statement does not say what period it settles")
    for note in ledger_outside:
        ambiguities.append(f"{LEDGER_FILE} entry {note} is dated outside {period_start}..{period_end}; "
                           f"no statement in the mounted files covers it")

    facts_by_row = ev.facts_by_row
    edges = _build_edges(rows, movements, facts_by_row, parties=parties, fee_account=fee_account, tie_break=tie_break)
    edges_by_row: dict = {}
    for edge in edges:
        edges_by_row.setdefault(edge.row, []).append(edge)
    # every instrument the statement shows, whatever the reading (see describe)
    presented_everywhere = [(token, rows[i].date) for i in range(len(rows)) for token in facts_by_row[i].presents]

    repairs: list[Repair] = []
    outstanding: list[str] = []
    matched = 0
    readings_total = 1
    for comp_rows, comp_movs in _components([r.index for r in rows], [m.index for m in movements], edges):
        describe = _describe(rows, movements, facts_by_row, comp_rows, comp_movs, period_end,
                             parties=parties, fee_account=fee_account, bank_account=bank_account,
                             presented_everywhere=presented_everywhere, evidenced=ev.evidenced)
        try:
            readings, incomplete, _matchings = _optimal_readings(comp_rows, edges_by_row, describe,
                                                                 rank=tie_break)
        except _Exhausted as exc:
            ambiguities.append(
                f"the reconciliation of {len(comp_rows)} statement row(s) and {len(comp_movs)} ledger "
                f"movement(s) around {rows[comp_rows[0]].date if comp_rows else movements[comp_movs[0]].date} "
                f"could not be enumerated within the budget ({exc}); it is reported ambiguous rather than "
                f"decided by where the search stopped")
            continue
        if not readings:
            # Nothing explains the whole month here: report what every reading
            # was left holding rather than picking one that strands an entry.
            seen: list[str] = []
            if len(incomplete) > 1:
                seen += _disagreement(rows, movements, comp_rows, incomplete)
                readings_total *= len(incomplete)
            for _sig, _repairs, _outstanding, comp_unexplained, _settled, _assignment in incomplete.values():
                for note in comp_unexplained:
                    if note not in seen:
                        seen.append(note)
            ambiguities.extend(seen[:6] or [
                f"the {len(comp_rows)} statement row(s) and {len(comp_movs)} ledger movement(s) around "
                f"{rows[comp_rows[0]].date if comp_rows else movements[comp_movs[0]].date} admit no reading "
                f"that accounts for every row and every entry"])
            continue
        if len(readings) != 1:
            readings_total *= max(len(readings), 1)
            ambiguities.extend(_disagreement(rows, movements, comp_rows, readings))
            continue
        _, comp_repairs, comp_outstanding, comp_unexplained, settled, _assignment = next(iter(readings.values()))
        repairs.extend(comp_repairs)
        outstanding.extend(comp_outstanding)
        ambiguities.extend(comp_unexplained)
        matched += settled

    ambiguities.extend(_attribution_complaints(repairs))
    ambiguities.extend(_indistinguishable_rows(rows, repairs))

    if len(statement_opening) > 1:
        ambiguities.append(f"{STATEMENT_FILE} carries {len(statement_opening)} rows with neither a debit nor "
                           f"a credit; only the carried-forward balance may be one")
    if len(ledger_opening) > 1:
        ambiguities.append(f"{LEDGER_FILE} carries {len(ledger_opening)} carry-forward entries")

    repairs.sort(key=lambda r: (r.date, r.kind, r.amount))
    outstanding.sort()
    if ambiguities:
        if not tie_break:
            # The declared reconciliation prior, reported as a ranking of an
            # ambiguous world — never as the verdict.
            ranked = check_identifiable(public, bank_account=bank_account, period_start=period_start,
                                        period_end=period_end, tie_break=True)
            if ranked.unique:
                ambiguities.append("diagnostic ranking under the day-and-wording prior (not public uniqueness): "
                                   + "; ".join(str(r) for r in ranked.repairs))
        return Verdict(False, repairs, ambiguities, "; ".join(ambiguities), outstanding, matched, readings_total)
    kinds = ", ".join(sorted({r.kind for r in repairs})) or "none"
    return Verdict(
        True, repairs, [],
        f"{len(rows)} statement rows, {matched} matched to ledger entries, {len(repairs)} repair candidate(s) "
        f"({kinds}), {len(outstanding)} outstanding item(s); each with one reading",
        outstanding, matched, 1)


def _disagreement(rows, movements, comp_rows, readings) -> list:
    """Why the maximum matchings of one component are not one reading.

    Named concretely, because "not identifiable" is a claim a reader has to
    be able to check: which row could go two ways, and what the two repair
    multisets actually were.
    """
    out: list[str] = []
    partners: dict = {}
    for _sig, _repairs, _outstanding, _unexplained, _settled, assignment in readings.values():
        for row_index in comp_rows:
            edge = assignment.get(row_index)
            partners.setdefault(row_index, set()).add(None if edge is None else edge.mov)
    for row_index in sorted(partners):
        choices = partners[row_index]
        if len(choices) < 2:
            continue
        named = [str(movements[m]) for m in sorted(m for m in choices if m is not None)]
        if len(named) > 1:
            out.append(f"{rows[row_index]} matches {len(named)} different ledger movements "
                       f"({'; '.join(named)}); a reader cannot tell which one it is")
        else:
            out.append(f"{rows[row_index]} is answered by {named[0]} in one reading and by nothing in "
                       f"another; whether the books already carry it is not decidable")
    shown = []
    for _sig, comp_repairs, comp_outstanding, _unexplained, _settled, _assignment in list(readings.values())[:2]:
        shown.append("{" + "; ".join(sorted(str(r) for r in comp_repairs) + sorted(comp_outstanding)) + "}")
    out.append(f"the evidence admits {len(readings)} maximum readings whose repairs differ: "
               + " versus ".join(shown))
    return out


def _attribution_complaints(repairs) -> list:
    """A repair nobody can post is not a repair.

    Carried on the repair itself, so the complaint is raised only when the
    surviving reading actually asks for that entry to be written.
    """
    out: list[str] = []
    for repair in repairs:
        if repair.kind == "missing_entry":
            out.extend(repair.notes)
    return out


def _indistinguishable_rows(rows, repairs) -> list:
    """Two rows of one amount that nothing tells apart, one of them unrecorded.

    A matching ambiguity is about which ENTRY answers a row; this is about
    which ROW an entry answers, which the matching cannot see when the rows
    are equal in every field a reader can compare. Restricted to groups
    containing a repair candidate on purpose: where every row of an amount is
    answered, permuting the assignment yields the same repaired books.
    """
    out: list[str] = []
    repaired = {(r.row_date, r.amount) for r in repairs if r.kind != "duplicate" and r.row_date}
    by_amount: dict = {}
    for row in rows:
        by_amount.setdefault(row.amount, []).append(row)
    for amount, group in sorted(by_amount.items()):
        if len(group) < 2 or not any((row.date, row.amount) in repaired for row in group):
            continue
        references = [row.reference for row in group]
        if all(references) and len(set(references)) == len(references):
            continue
        out.append(
            f"{amount:+.2f} appears on {len(group)} statement rows ({', '.join(row.date for row in group)}) "
            f"with no distinguishing reference, and at least one of them is unrecorded; which row the books "
            f"already carry is not decidable")
    return out
