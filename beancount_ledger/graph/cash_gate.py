"""Phase C: the MINTING GATE and its CENSUS for the generated
cash-application population.

Round 16, decision 3. `cash_manifest.GATE_GROUPS` declares the exact gate set
— decision 3's six integrity headings plus gate (o) — and says of itself
"DECLARED HERE, IMPLEMENTED BY THE PREFLIGHT. This module does not run a
gate". This is that preflight. Every name in `cash_manifest.family_gates()`
has an implementation here, every implementation carries its own rejection
code, and `evaluate` refuses to answer at all if a declared gate has no
implementation: a gate nobody ran is not a gate that passed.

WHAT THIS ADDS TO THE CONSTRUCTION PATH. `cash_construct` already refuses a
draw its own recipe cannot lay out, a variant outside `bounded-v1` and a
variant the shipped world checker rejects. Three things were still missing,
and they are the whole of this module:

  * GATE (o) WAS NOT RUN AT MINT TIME AT ALL. It was a test — one secret, one
    company-month index — so its PASS was a fact about that draw. Here the
    nine binding baselines and the one diagnostic run on every rendered
    variant of every attempt, and an admitted binding baseline that reaches
    the entire truth through ANY enumerated reading rejects the candidate.
  * THE SIX INTEGRITY FAMILIES HAD NO EXPLICIT CHECKS. Some of what they ask
    for was implied by other gates passing; implication is not a check, and a
    gate that is never evaluated cannot be reported, cannot carry a rejection
    code, and cannot appear in a census. Each of the thirty declared gates is
    evaluated here by name.
  * THE CENSUS KEPT THE SUCCESSFUL ATTEMPT AND THE LAST EXCEPTION. Decision 3
    calls that insufficient. Every attempt now retains its ordinal, stage,
    evaluated rejection codes, the relevant baseline and witness, the reading
    count, the component versions and the content digest wherever rendering
    succeeded; and `aggregate` publishes acceptance rates, exhaustion counts
    and rejection distributions over a set of groups.

WHAT A REJECTION MEANS, AND WHAT IT DOES NOT. Decision 3 draws two lines this
module keeps:

  * "Expected construction failures may be retried. Unexpected exceptions,
    disagreement between supposedly independent derivations, or a valid
    golden failing its scorer are defects to investigate — not opportunities
    to keep drawing until the defect disappears." A `ConstructionRefused` and
    a failed gate are recorded and redrawn; a `ConstructionDefect`, an
    `AdmissionUnavailable` and anything else propagate out of the loop
    unclassified.
  * "Exceeding the 256-reading bound means verification was incomplete; it
    does not mean the candidate resisted the baseline." The reading bound is
    its own gate under its own code, `VERIFICATION-LIMIT`, and the candidate
    it fires on is rejected as UNVERIFIED rather than admitted as resistant.

`number_order` stays diagnostic. Its result is recorded on every attempt and
it is never consulted for admission; `diagnostic_baseline_recorded` is the
gate that fails if it ever stops being recorded, and it would also fail if
somebody moved it into the binding set, because the count of binding
baselines is checked against the catalogue's own declaration rather than
against a number typed here.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal

from ..candidate.canonical import TEXT_MAX_CODEPOINTS, canonical_bytes, domain_digest
from . import cash_admit as ADMIT
from . import cash_application as CA
from . import cash_construct as CC
from . import cash_manifest as FM
from . import cash_profile as PROFILE
from .cash_identity import (
    BOUNDED_V1,
    MAX_LAYOUT_ATTEMPTS,
    ConstructionIdentity,
    GenerationProfile,
    identity_leaks,
    parent_seed,
)
from .cash_split import SPLIT_MAP, SplitMap, StructuralAliasError, StructureLedger, structure_digest

#: This gate implementation's own version. It is NOT the preflight contract
#: version and NOT the catalogue version: those are declarations in
#: `cash_manifest`, and this is the number that moves when the code that
#: evaluates them moves.
GATE_VERSION = 1

_CENSUS_DOMAIN = b"piv:cash-application-mint-census:v1\0"

ZERO = Decimal("0.00")
_SI = re.compile(r"\bSI-\d+\b")
_LEDGER_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')

#: The eight refusals the fold is declared to carry. Pinned here so that
#: `no_refusal_relaxed_by_layout` fails when one is quietly dropped — which is
#: the cheapest way a refusal gets "relaxed because a more complicated layout
#: meets it".
DECLARED_REFUSALS = (
    CA.REFUSE_AMBIGUOUS_REMITTANCE_JOIN, CA.REFUSE_LINE_CONTRADICTS_REGISTER,
    CA.REFUSE_FOREIGN_OR_UNKNOWN_INVOICE, CA.REFUSE_ADVICE_AMOUNT_DISAGREES,
    CA.REFUSE_ORDER_SENSITIVE, CA.REFUSE_DUPLICATE_RECEIPT_KEY,
    CA.REFUSE_REGISTER_DOES_NOT_TIE, CA.REFUSE_SALE_WITHOUT_UNIQUE_NUMBER,
)

#: The U12 warnings a candidate may not carry. Each of them is a layout
#: sitting exactly ON a published threshold — a deduction at the tolerance, a
#: line against a zero balance, an advice that binds no payment. Admitting
#: one makes the next argument "the refusal is too strict, this layout is
#: fine", which is the relaxation decision 3 forbids.
FORBIDDEN_WARNINGS = (CA.WARN_DEDUCTION_AT_TOLERANCE, CA.WARN_LINE_ON_ZERO_BALANCE, CA.WARN_UNBOUND_ADVICE)

#: The declared header of every CSV this family publishes, read from the fold
#: rather than restated.
DECLARED_COLUMNS = {
    CA.OPEN_ITEMS_FILE: CA.OPEN_ITEMS_COLUMNS,
    CA.REMITTANCE_FILE: CA.REMITTANCE_COLUMNS,
    CA.CREDIT_NOTES_FILE: CA.CREDIT_NOTE_COLUMNS,
    CA.STATEMENT_FILE: CA.STATEMENT_COLUMNS,
}


class GateUnavailable(RuntimeError):
    """A declared gate has no implementation, or an implementation could not
    be run. Never a pass: decision 3 admits a pair that satisfied every
    condition, and a condition nobody evaluated is not one of them."""


class GroupExhausted(CC.ConstructionRefused):
    """The named failed group. A subclass of `ConstructionRefused` so that a
    caller which already treats exhaustion as a refusal keeps working, and a
    distinct type so a census reader can tell "this attempt was refused" from
    "this group was never minted".

    It CARRIES the group's census. Decision 3 calls keeping only the last
    exception insufficient, and an exhausted group is exactly the case where
    the retained attempts matter most: sixty-four refusals with their codes
    are the evidence for why the specification could not be satisfied here,
    and an exception that dropped them would leave the failure unexplainable.
    """

    def __init__(self, message, *, census=None, **kw):
        super().__init__(message, **kw)
        self.census = census


# --------------------------------------------------------------------------
# rejection codes
# --------------------------------------------------------------------------

#: One short prefix per declared group. A code is derived from the group and
#: the gate name, so a gate cannot be added without a code and a code cannot
#: drift from the gate it names.
GROUP_PREFIX = {
    "accounting_integrity": "ACC",
    "evidence_integrity": "EVI",
    "representation_integrity": "REP",
    "independent_correctness": "IND",
    "contrast_integrity": "CON",
    "population_integrity": "POP",
    "baseline_resistance": "BAS",
}

#: Decision 3 gives the reading bound a rejection of its own: "Exceeding it
#: means verification was incomplete; it does not mean the candidate resisted
#: the baseline. Record a verification-limit rejection." So that gate's code
#: is not derived from its name — it is the ruling's own word, and a census
#: reader counting `BAS-*` rejections as resistance will not silently count
#: this one among them.
VERIFICATION_LIMIT = "VERIFICATION-LIMIT"
_CODE_OVERRIDES = {"reading_bound_respected": VERIFICATION_LIMIT}

#: Codes that are not gates: the group that ran out of attempts, and a
#: construction-stage refusal that arrived before the gate could speak.
EXHAUSTION_CODE = "GROUP-EXHAUSTED"


def code_of(group: str, gate: str) -> str:
    if gate in _CODE_OVERRIDES:
        return _CODE_OVERRIDES[gate]
    if group not in GROUP_PREFIX:
        raise GateUnavailable(f"gate group {group!r} has no rejection-code prefix")
    return f"{GROUP_PREFIX[group]}-{gate.upper().replace('_', '-')}"


def rejection_codes() -> dict:
    """gate name -> rejection code, derived from `cash_manifest.GATE_GROUPS`
    at call time so that the declaration stays the single authority."""
    return {gate: code_of(group, gate) for group, gates in FM.GATE_GROUPS for gate in gates}


def group_of(gate: str) -> str:
    for group, gates in FM.GATE_GROUPS:
        if gate in gates:
            return group
    raise GateUnavailable(f"no declared group carries the gate {gate!r}")


# --------------------------------------------------------------------------
# the candidate under evaluation
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Candidate:
    """Everything the gates read about one attempt's rendered pair, built
    once so that thirty checks do not re-fold the same bytes thirty times."""

    identity: ConstructionIdentity
    profile: GenerationProfile
    family: str
    mechanism: str
    attempt: int
    declared_fact: object
    template: object
    variants: dict                    # variant -> cash_construct.Variant
    evidence: dict                    # variant -> CA.Evidence
    application: dict                 # variant -> CA.Application (the PUBLIC fold)
    content_digests: dict             # variant -> public-content digest
    seed: int | None = None

    @property
    def names(self) -> tuple:
        return tuple(sorted(self.variants))

    def public(self, name: str) -> dict:
        return self.variants[name].public_files

    def truth(self, name: str):
        return self.variants[name].truth

    def fold_kwargs(self, name: str) -> dict:
        variant = self.variants[name]
        return {"bank_account": variant.world.bank_account,
                "period_start": variant.task.period.start,
                "period_end": variant.task.period.end}


def candidate_of(ident: ConstructionIdentity, profile: GenerationProfile, attempt: int,
                 rendered: dict, fact, template, seed: int | None = None) -> Candidate:
    """One attempt's rendered pair, with the evidence, the public fold and
    the public-content digest of each variant read ONCE.

    Thirty checks share these three readings. Reading them per check would
    make the gate's cost a function of how many checks happen to want the
    fold, and — worse — would let two checks disagree about what the bytes
    say because one of them re-read after a mutation.
    """
    evidence, application, digests = {}, {}, {}
    for name, variant in rendered.items():
        kw = {"bank_account": variant.world.bank_account,
              "period_start": variant.task.period.start,
              "period_end": variant.task.period.end}
        evidence[name] = CA.read_evidence(variant.public_files, **kw)
        application[name] = CA.fold(variant.public_files, **kw)
        digests[name] = FM.public_content_digest(variant.public_files, variant.task.prompt)
    return Candidate(identity=ident, profile=profile, family=ident.template_family,
                     mechanism=CC.shape_of(ident.template_family).mechanism, attempt=attempt,
                     declared_fact=fact, template=template, variants=dict(rendered), evidence=evidence,
                     application=application, content_digests=digests, seed=seed)


# --------------------------------------------------------------------------
# small readers shared by the checks
# --------------------------------------------------------------------------

def _header(public: dict, name: str) -> tuple:
    reader = csv.reader(io.StringIO(public[name]))
    return tuple(next(reader, []))


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _parsed_ledger(text: str):
    """The ledger through the SHIPPED parse boundary, exactly as the
    production door reads it. Returns `(accepted_or_None, problem_or_None)`."""
    from ..beancount_ledger import logical_text
    from ..candidate.normalise import Accepted, parse_once

    parsed = parse_once(logical_text(text.encode("utf-8")))
    if not isinstance(parsed, Accepted):
        return None, f"the parse boundary refused it ({type(parsed).__name__}): {parsed}"
    if not parsed.domain_valid:
        return None, f"domain findings at the boundary: {parsed.finding_summary.codes}"
    return parsed, None


def _transactions(parsed):
    from ..candidate.schema import ParsedTransaction
    return [d for d in parsed.submission.directives if isinstance(d, ParsedTransaction)]


def _world_rate(world):
    """The one tax rate the world's sales and its credit note are struck at,
    or None when the world declares more than one."""
    from .schema import CreditNote as CN
    from .schema import Sale
    rates = {e.tax_rate for e in world.events if isinstance(e, (Sale, CN)) and hasattr(e, "tax_rate")}
    return rates.pop() if len(rates) == 1 else None


def _splits_at(gross: Decimal, rate: Decimal) -> bool:
    """Whether `gross` is `net + round(net * rate)` for some whole-cent net —
    `cash_construct.gross_of`'s own arithmetic, inverted."""
    guess = (gross / (1 + rate)).quantize(Decimal("0.01"))
    for net in (guess, guess - Decimal("0.01"), guess + Decimal("0.01")):
        if net > 0 and CC.gross_of(net, rate) == gross:
            return True
    return False


# --------------------------------------------------------------------------
# accounting integrity
# --------------------------------------------------------------------------

def _invoice_universe_complete(c: Candidate, name: str) -> list:
    out = []
    ev, truth = c.evidence[name], c.truth(name)
    public_ids = {i.invoice_id for i in ev.invoices}
    truth_ids = {row[0] for row in truth.invoices}
    if public_ids != truth_ids:
        out.append(f"the public invoice universe and the truth's differ: only public "
                   f"{sorted(public_ids - truth_ids)}, only truth {sorted(truth_ids - public_ids)}")
    public_source = {i.invoice_id: i.source for i in ev.invoices}
    for invoice_id, _customer, _date, _basis, source in truth.invoices:
        if public_source.get(invoice_id) != source:
            out.append(f"{invoice_id} is a {source!r} in the truth and a "
                       f"{public_source.get(invoice_id)!r} in the public universe")
    opening = {row[0] for row in truth.opening_register}
    carried = {i.invoice_id for i in ev.invoices if i.source == "register"}
    if opening != carried:
        out.append(f"the opening register carries {sorted(opening - carried)} the universe does not, and the "
                   f"universe carries {sorted(carried - opening)} the opening register does not")
    if not [i for i in ev.invoices if i.source == "sale"]:
        out.append("no invoice was raised during the period; the universe is opening-only")
    register_ids = {row.invoice_id for row in c.application[name].register}
    if register_ids != public_ids:
        out.append(f"the closing register is not over the whole universe: missing "
                   f"{sorted(public_ids - register_ids)}, extra {sorted(register_ids - public_ids)}")
    for inv in ev.invoices:
        if inv.period_basis <= 0:
            out.append(f"{inv.invoice_id} enters the period with basis {inv.period_basis}")
        if inv.source == "register" and inv.period_basis > inv.face_value:
            out.append(f"{inv.invoice_id} carries {inv.period_basis} against a face value of {inv.face_value}")
    return out


def _customer_ownership(c: Candidate, name: str) -> list:
    out = []
    ev, app = c.evidence[name], c.application[name]
    known = set(ev.customers)
    owner = {i.invoice_id: i.customer for i in ev.invoices}
    for inv in ev.invoices:
        if inv.customer not in known:
            out.append(f"{inv.invoice_id} is owned by {inv.customer!r}, who is not in customers.csv")
    for a in ev.advices:
        if a.customer not in known:
            out.append(f"advice {a.remittance_id} names {a.customer!r}, who is not in customers.csv")
    for r in app.receipts:
        if r.customer not in known:
            out.append(f"receipt {r.receipt_id} names {r.customer!r}, who is not in customers.csv")
        for invoice_id, _amount in tuple(r.applied) + tuple(r.written_off):
            if owner.get(invoice_id) != r.customer:
                out.append(f"receipt {r.receipt_id} from {r.customer} reaches {invoice_id}, owned by "
                           f"{owner.get(invoice_id)!r}: cross-customer application is outside the policy")
    for cn in app.credit_notes:
        for invoice_id, _amount in cn.applied:
            if owner.get(invoice_id) != cn.customer:
                out.append(f"credit note {cn.credit_note_id} from {cn.customer} reaches {invoice_id}, owned by "
                           f"{owner.get(invoice_id)!r}")
    for cn in ev.credit_notes:
        if owner.get(cn.invoice_id) != cn.customer:
            out.append(f"credit note {cn.credit_note_id} names {cn.invoice_id}, owned by "
                       f"{owner.get(cn.invoice_id)!r} rather than by {cn.customer!r}")
    return out


def _receipt_and_credit_conservation(c: Candidate, name: str) -> list:
    out = []
    app, truth = c.application[name], c.truth(name)
    # A write-off is NOT cash. The shortfall an advice settles is money the
    # customer never sent, so it reduces the invoice's balance (the row
    # identity below) without appearing in what the bank credited: the cash a
    # receipt conserves is what it applied plus what it left unapplied.
    for r in app.receipts:
        applied = sum((a for _i, a in r.applied), ZERO)
        written = sum((a for _i, a in r.written_off), ZERO)
        if applied + r.unapplied != r.amount:
            out.append(f"receipt {r.receipt_id}: {applied} applied + {r.unapplied} unapplied is not the "
                       f"{r.amount} received (and {written} was written off)")
        if r.unapplied < 0 or any(a <= 0 for _i, a in r.applied) or any(a <= 0 for _i, a in r.written_off):
            out.append(f"receipt {r.receipt_id} carries a non-positive allocation or a negative residue: "
                       f"applied={list(r.applied)} written_off={list(r.written_off)} unapplied={r.unapplied}")
    for cn in app.credit_notes:
        applied = sum((a for _i, a in cn.applied), ZERO)
        if applied + cn.unapplied != cn.gross:
            out.append(f"credit note {cn.credit_note_id}: {applied} applied + {cn.unapplied} unapplied is not "
                       f"the {cn.gross} raised")
        if cn.unapplied < 0 or any(a <= 0 for _i, a in cn.applied):
            out.append(f"credit note {cn.credit_note_id} carries a non-positive allocation or a negative "
                       f"residue: applied={list(cn.applied)} unapplied={cn.unapplied}")
    for row in truth.receipts:
        applied = sum((a for _i, a in row[4]), ZERO)
        if applied + row[6] != row[3]:
            out.append(f"the TRUTH's receipt {row[0]} does not conserve: {applied} applied + {row[6]} "
                       f"unapplied is not the {row[3]} received")
    for row in truth.credit_notes:
        if sum((a for _i, a in row[4]), ZERO) + row[5] != row[3]:
            out.append(f"the TRUTH's credit note {row[0]} does not conserve")
    return out


def _row_identities(c: Candidate, name: str) -> list:
    out = []
    app = c.application[name]
    for row in app.register:
        if row.period_basis - row.applied_total - row.credited - row.written_off != row.remaining:
            out.append(f"row {row.invoice_id}: {row.period_basis} - {row.applied_total} - {row.credited} - "
                       f"{row.written_off} is not {row.remaining}")
        negatives = {f: getattr(row, f) for f in
                     ("period_basis", "applied_total", "credited", "written_off", "remaining")
                     if getattr(row, f) < 0}
        if negatives:
            out.append(f"row {row.invoice_id} carries negative components {negatives}")
    applied = sum((a for r in app.receipts for _i, a in r.applied), ZERO)
    written = sum((a for r in app.receipts for _i, a in r.written_off), ZERO)
    credited = sum((a for cn in app.credit_notes for _i, a in cn.applied), ZERO)
    if sum((row.applied_total for row in app.register), ZERO) != applied:
        out.append("the register's applied column is not the receipts' applied total")
    if sum((row.written_off for row in app.register), ZERO) != written:
        out.append("the register's write-off column is not the receipts' write-off total")
    if sum((row.credited for row in app.register), ZERO) != credited:
        out.append("the register's credit column is not the credit notes' applied total")
    return out


def _ar_reconciles(c: Candidate, name: str) -> list:
    out = []
    ev, app, truth = c.evidence[name], c.application[name], c.truth(name)
    opening = sum((row[5] for row in truth.opening_register), ZERO)
    if app.opening_ar != opening:
        out.append(f"the folded opening AR {app.opening_ar} is not the opening register's {opening}")
    if truth.opening_ar != app.opening_ar:
        out.append(f"the truth's opening AR {truth.opening_ar} is not the fold's {app.opening_ar}")
    unapplied = (sum((r.unapplied for r in app.receipts), ZERO)
                 + sum((cn.unapplied for cn in app.credit_notes), ZERO))
    remaining = sum((row.remaining for row in app.register), ZERO)
    if app.closing_ar != remaining - unapplied:
        out.append(f"the closing AR {app.closing_ar} is not the open items {remaining} less the unapplied "
                   f"{unapplied}")
    sales = sum((i.period_basis for i in ev.invoices if i.source == "sale"), ZERO)
    applied = sum((a for r in app.receipts for _i, a in r.applied), ZERO)
    written = sum((a for r in app.receipts for _i, a in r.written_off), ZERO)
    credited = sum((a for cn in app.credit_notes for _i, a in cn.applied), ZERO)
    movement = app.opening_ar + sales - applied - written - credited - unapplied
    if movement != app.closing_ar:
        out.append(f"AR does not roll forward: opening {app.opening_ar} + sales {sales} - applied {applied} - "
                   f"written off {written} - credited {credited} - unapplied {unapplied} is {movement}, and "
                   f"the closing AR is {app.closing_ar}")
    if truth.closing_ar != app.closing_ar:
        out.append(f"the truth's closing AR {truth.closing_ar} is not the fold's {app.closing_ar}")
    return out


def _zero_opening_write_off_balance(c: Candidate, name: str) -> list:
    """The write-off account opens the period at zero, so every write-off in
    the close is one THIS month's evidence supports.

    Two readings, because the opening balance has two representations. The
    authored one is the world's carried position, which must not mention the
    account at all (or must carry zero on it). The public one is the ledger
    the agent is given: no entry DATED BEFORE the period may post to it. The
    in-period write-off entries are the answer to the task and are of course
    there; what may not be there is a balance brought forward.
    """
    out = []
    variant, ev, truth = c.variants[name], c.evidence[name], c.truth(name)
    account = truth.write_off_account
    for carried_account, amount in variant.world.opening.carried:
        if carried_account == account and amount != 0:
            out.append(f"the world carries {amount} on {account} into the period; the write-off balance must "
                       f"open at zero")
    parsed, problem = _parsed_ledger(c.public(name)[CA.LEDGER_FILE])
    if problem:
        return out + [f"the opening ledger does not reach the write-off check: {problem}"]
    brought_forward = [f"{txn.date} {txn.narration!r} {posting.amount}"
                       for txn in _transactions(parsed) if txn.date < ev.period_start
                       for posting in txn.postings if posting.account == account]
    if brought_forward:
        out.append(f"the ledger carries {len(brought_forward)} posting(s) to {account} before "
                   f"{ev.period_start}: {brought_forward[:3]}; a write-off balance brought forward would make "
                   f"part of the close unattributable to this month's evidence")
    return out


def _consistent_sale_and_credit_tax_bases(c: Candidate, name: str) -> list:
    out = []
    variant, ev = c.variants[name], c.evidence[name]
    rate = _world_rate(variant.world)
    if rate is None:
        return ["the world's sales and credit note are not struck at one tax rate, so an original-sale base "
                "and a credit base cannot be compared"]
    for cn in ev.credit_notes:
        if cn.net + cn.tax != cn.gross:
            out.append(f"credit note {cn.credit_note_id}: {cn.net} + {cn.tax} is not {cn.gross}")
        if CC.gross_of(cn.net, rate) != cn.gross:
            out.append(f"credit note {cn.credit_note_id} is struck at a different rate from the world's "
                       f"{rate}: {cn.net} at {rate} is {CC.gross_of(cn.net, rate)}, not {cn.gross}")
        invoice = ev.invoice(cn.invoice_id)
        if invoice is not None and not _splits_at(invoice.face_value, rate):
            out.append(f"{cn.invoice_id}'s original sale of {invoice.face_value} does not split at the "
                       f"world's rate {rate}, so the note reverses a base the sale never carried")
    for inv in ev.invoices:
        if not _splits_at(inv.face_value, rate):
            out.append(f"{inv.invoice_id}'s face value {inv.face_value} does not split at the world's "
                       f"rate {rate}")
    return out


def _cumulative_reversal_bounded(c: Candidate, name: str) -> list:
    out = []
    ev = c.evidence[name]
    by_invoice: dict = {}
    for cn in ev.credit_notes:
        by_invoice.setdefault(cn.invoice_id, []).append(cn)
    for invoice_id, notes in sorted(by_invoice.items()):
        invoice = ev.invoice(invoice_id)
        if invoice is None:
            out.append(f"{len(notes)} credit note(s) name {invoice_id}, which is not in the universe")
            continue
        gross = sum((cn.gross for cn in notes), ZERO)
        net = sum((cn.net for cn in notes), ZERO)
        if gross > invoice.face_value:
            out.append(f"the notes against {invoice_id} reverse {gross} of an original sale of "
                       f"{invoice.face_value}: cumulative reversal is bounded by the sale")
        if net <= 0:
            out.append(f"the notes against {invoice_id} reverse a non-positive net {net}")
        if gross > invoice.period_basis:
            out.append(f"the notes against {invoice_id} reverse {gross} of an opening balance of "
                       f"{invoice.period_basis}")
    return out


# --------------------------------------------------------------------------
# evidence integrity
# --------------------------------------------------------------------------

def _genuine_payment_identity(c: Candidate, name: str) -> list:
    out = []
    ev = c.evidence[name]
    seen: dict = {}
    known = set(ev.customers)
    for r in ev.receipts:
        if r.receipt_id in seen:
            out.append(f"two statement rows share the receipt identity {r.receipt_id}")
        seen[r.receipt_id] = r
        if r.customer not in known:
            out.append(f"{r.receipt_id} is credited to {r.customer!r}, who is not a customer")
        if r.amount <= 0:
            out.append(f"{r.receipt_id} is a receipt of {r.amount}")
        if r.method not in ("ACH", "CHECK"):
            out.append(f"{r.receipt_id} arrives by {r.method!r}, which is neither rail the policy publishes")
        if r.method == "CHECK" and not r.cheque_number:
            out.append(f"{r.receipt_id} is a cheque with no cheque number, so the payer's instrument is "
                       f"not identified")
    upper = {}
    for customer in ev.customers:
        upper.setdefault(customer.upper(), []).append(customer)
    ambiguous = {k: v for k, v in upper.items() if len(v) > 1}
    if ambiguous:
        out.append(f"two customers share an upper-cased name, so a statement description cannot name one of "
                   f"them: {ambiguous}")
    return out


def _unambiguous_advice_binding(c: Candidate, name: str) -> list:
    out = []
    ev = c.evidence[name]
    ids = [a.remittance_id for a in ev.advices]
    if len(set(ids)) != len(ids):
        out.append(f"two advices share a remittance identity: {sorted({i for i in ids if ids.count(i) > 1})}")
    receipts = {r.receipt_id: r for r in ev.receipts}
    advices = {a.remittance_id: a for a in ev.advices}
    bound_advices = list(ev.bindings.values())
    if len(set(bound_advices)) != len(bound_advices):
        out.append(f"one advice binds more than one receipt: {sorted(bound_advices)}")
    for receipt_id, remittance_id in sorted(ev.bindings.items()):
        if receipt_id not in receipts:
            out.append(f"the binding names a receipt {receipt_id} the statement does not carry")
            continue
        if remittance_id not in advices:
            out.append(f"the binding names an advice {remittance_id} the file does not carry")
            continue
        r, a = receipts[receipt_id], advices[remittance_id]
        if a.customer != r.customer or a.payment_amount != r.amount:
            out.append(f"{receipt_id} is bound to {remittance_id}, which is {a.customer!r} for "
                       f"{a.payment_amount} against a receipt of {r.customer!r} for {r.amount}")
    unbound = sorted(set(advices) - set(bound_advices))
    if unbound:
        out.append(f"advice(s) {unbound} bind no payment; policy reads an unbound advice as evidence for no "
                   f"payment, which is a layout a reader cannot resolve rather than a fact")
    return out


def _chronology_consistent_with_policy(c: Candidate, name: str) -> list:
    out = []
    ev, app = c.evidence[name], c.application[name]
    start, end = ev.period_start, ev.period_end
    if not start <= end:
        out.append(f"the period runs {start} to {end}")
    owner = {i.invoice_id: i for i in ev.invoices}
    for inv in ev.invoices:
        # An in-period sale is read off the LEDGER, which publishes no due
        # date, so `due_date` is empty for it by design. Comparing an empty
        # string with a date would make every case fail on a fact the pack
        # never claimed.
        if inv.due_date and inv.due_date < inv.invoice_date:
            out.append(f"{inv.invoice_id} is due {inv.due_date}, before it was issued {inv.invoice_date}")
        if inv.source == "sale" and not start <= inv.invoice_date <= end:
            out.append(f"{inv.invoice_id} is an in-period sale dated {inv.invoice_date}, outside {start}..{end}")
        if inv.source == "register" and inv.invoice_date >= start:
            out.append(f"{inv.invoice_id} is carried into the period and dated {inv.invoice_date}, on or after "
                       f"{start}")
    for r in ev.receipts:
        if not start <= r.date <= end:
            out.append(f"receipt {r.receipt_id} is dated {r.date}, outside {start}..{end}")
    for a in ev.advices:
        if not start <= a.remittance_date <= end:
            out.append(f"advice {a.remittance_id} is dated {a.remittance_date}, outside {start}..{end}")
    for cn in ev.credit_notes:
        if not start <= cn.date <= end:
            out.append(f"credit note {cn.credit_note_id} is dated {cn.date}, outside {start}..{end}")
    for r in app.receipts:
        for invoice_id, _amount in tuple(r.applied) + tuple(r.written_off):
            invoice = owner.get(invoice_id)
            if invoice is not None and invoice.invoice_date > r.date:
                out.append(f"receipt {r.receipt_id} of {r.date} settles {invoice_id}, issued "
                           f"{invoice.invoice_date}: a payment cannot reach an invoice that does not exist")
    for cn in app.credit_notes:
        for invoice_id, _amount in cn.applied:
            invoice = owner.get(invoice_id)
            if invoice is not None and invoice.invoice_date > cn.date:
                out.append(f"credit note {cn.credit_note_id} of {cn.date} credits {invoice_id}, issued "
                           f"{invoice.invoice_date}")
    return out


def _order_insensitive(c: Candidate, name: str) -> list:
    """The EXISTING order-sensitivity checks, as an explicit gate.

    `CA.fold` re-runs itself with every adviced receipt on its advice's
    remittance date and raises `REFUSE_ORDER_SENSITIVE` if any line moves;
    reaching this gate means that ran and was silent. Two things are still
    worth evaluating, because both would make that silence meaningless: the
    refusal must still be in the catalogue, and the fold must not depend on
    the order the caller happens to hand it the files in.
    """
    out = []
    if CA.REFUSE_ORDER_SENSITIVE not in CA.REFUSALS:
        out.append("REFUSE_ORDER_SENSITIVE is not in the shipped refusal catalogue, so the fold's own "
                   "order-sensitivity check cannot fire")
    public = c.public(name)
    shuffled = {key: public[key] for key in reversed(list(public))}
    try:
        again = CA.fold(shuffled, **c.fold_kwargs(name))
    except CA.Refusal as exc:
        out.append(f"the same bytes in another mapping order refuse: {exc}")
        return out
    except (ValueError, KeyError) as exc:
        out.append(f"the same bytes in another mapping order do not reach the fold: "
                   f"{type(exc).__name__}: {exc}")
        return out
    if CA.application_key(again) != CA.application_key(c.application[name]):
        out.append("the fold's answer depends on the order the public files are presented in")
    return out


def _no_refusal_relaxed_by_layout(c: Candidate, name: str) -> list:
    """Decision 3: "No relaxation of a refusal merely because a more
    complicated layout encounters it."

    Three readings, all model-independent. The catalogue still carries the
    eight refusals it declares — dropping one is the cheapest relaxation
    there is. The candidate does not sit ON a published threshold, because a
    layout that does is exactly the one that makes "the refusal is too
    strict" the next argument. And the refusal machinery is still ARMED on
    THIS layout, witnessed by a live probe: duplicate a statement credit row
    and the duplicate-receipt refusal must fire on these bytes, not on a
    simpler fixture somewhere else.
    """
    out = []
    if tuple(CA.REFUSALS) != DECLARED_REFUSALS:
        out.append(f"the refusal catalogue is {list(CA.REFUSALS)}, not the eight this gate version was "
                   f"declared against")
    carried = [w for w in c.application[name].warnings
               if any(w.startswith(code) for code in FORBIDDEN_WARNINGS)]
    if carried:
        out.append(f"the candidate sits on a published threshold: {carried}")
    public = dict(c.public(name))
    statement = public[CA.STATEMENT_FILE].splitlines(keepends=True)
    credit_index = None
    for index, line in enumerate(statement[1:], start=1):
        row = next(csv.reader(io.StringIO(line)), [])
        if len(row) == len(CA.STATEMENT_COLUMNS) and row[4].strip():
            credit_index = index
            break
    if credit_index is None:
        out.append("the statement carries no credit row, so the duplicate-receipt refusal cannot be probed "
                   "on this layout")
        return out
    probed = statement[:credit_index + 1] + [statement[credit_index]] + statement[credit_index + 1:]
    public[CA.STATEMENT_FILE] = "".join(probed)
    try:
        CA.read_evidence(public, **c.fold_kwargs(name))
    except CA.Refusal as exc:
        if exc.code != CA.REFUSE_DUPLICATE_RECEIPT_KEY:
            out.append(f"duplicating a statement credit row on this layout raises {exc.code}, not "
                       f"{CA.REFUSE_DUPLICATE_RECEIPT_KEY}")
    except (ValueError, KeyError) as exc:
        # The probe answered something that is not a refusal at all, which
        # means these bytes do not reach the refusal machinery. That is a
        # candidate whose refusals were never exercised, so it is reported
        # rather than passed over.
        out.append(f"the duplicate-receipt probe could not be run on this layout: "
                   f"{type(exc).__name__}: {exc}")
    else:
        out.append("duplicating a statement credit row on this layout is accepted; the duplicate-receipt "
                   "refusal is not armed against this candidate")
    return out


# --------------------------------------------------------------------------
# representation integrity
# --------------------------------------------------------------------------

def _renders_and_parses_through_shipped_boundaries(c: Candidate, name: str) -> list:
    from ..candidate import application as APP

    out = []
    variant, public = c.variants[name], c.public(name)
    expected = set(CA.EXTRA_PUBLIC_FILES) | {CA.LEDGER_FILE, CA.STATEMENT_FILE, CA.ACCOUNTS_FILE,
                                             CA.CUSTOMERS_FILE}
    missing = sorted(expected - set(public))
    if missing:
        out.append(f"the projection is missing {missing}")
    if len(public) != 11:
        out.append(f"the projection emitted {len(public)} public files, not eleven")
    for title, text in ((CA.LEDGER_FILE, public.get(CA.LEDGER_FILE, "")),
                        ("the golden ledger", variant.golden_ledger)):
        _parsed, problem = _parsed_ledger(text)
        if problem:
            out.append(f"{title} does not pass the shipped parse boundary: {problem}")
    try:
        document = json.loads(variant.golden_register)
    except ValueError as exc:
        out.append(f"the golden register is not JSON: {exc}")
    else:
        if document.get("schema") != CA.APPLICATION_SCHEMA:
            out.append(f"the golden register declares schema {document.get('schema')!r}")
    parsed = APP.parse_application(variant.golden_register, variant.inputs.application)
    if not isinstance(parsed, APP.ParsedApplication):
        out.append(f"the golden register is refused at the application boundary: {parsed}")
    if CA.document_text(c.application[name]) != variant.golden_register:
        out.append("the golden register is not the document the public fold renders")
    return out


def _csv_columns_declared(c: Candidate, name: str) -> list:
    out = []
    public = c.public(name)
    for file_name, columns in sorted(DECLARED_COLUMNS.items()):
        if file_name not in public:
            out.append(f"{file_name} is not in the projection")
            continue
        header = _header(public, file_name)
        if header != columns:
            out.append(f"{file_name} publishes columns {list(header)}, not the declared {list(columns)}")
    for file_name in sorted(public):
        if not file_name.endswith(".csv"):
            continue
        reader = list(csv.reader(io.StringIO(public[file_name])))
        if not reader or not reader[0]:
            out.append(f"{file_name} carries no header row")
            continue
        width = len(reader[0])
        ragged = [index for index, row in enumerate(reader[1:], start=2) if row and len(row) != width]
        if ragged:
            out.append(f"{file_name} has {len(ragged)} row(s) of a width other than {width}, first at line "
                       f"{ragged[0]}")
    return out


def _memo_narration_agreement(c: Candidate, name: str) -> list:
    out = []
    ev, public = c.evidence[name], c.public(name)
    universe = {i.invoice_id for i in ev.invoices}
    owner = {i.invoice_id: i.customer for i in ev.invoices}
    for r in ev.receipts:
        for token in _SI.findall(r.reference):
            if token not in universe:
                out.append(f"the statement reference of {r.receipt_id} names {token}, which is not in the "
                           f"invoice universe")
            elif owner[token] != r.customer:
                out.append(f"the statement reference of {r.receipt_id} (from {r.customer}) names {token}, "
                           f"owned by {owner[token]}")
    for a in ev.advices:
        for line in a.lines:
            for token in _SI.findall(line.note or ""):
                if token != line.invoice_id:
                    out.append(f"advice {a.remittance_id}'s note on {line.invoice_id} names {token} instead")
    for cn in ev.credit_notes:
        for token in _SI.findall(cn.reason or ""):
            if token != cn.invoice_id:
                out.append(f"credit note {cn.credit_note_id} names {cn.invoice_id} and its reason names "
                           f"{token}")
    parsed, problem = _parsed_ledger(public[CA.LEDGER_FILE])
    if problem:
        return out + [f"the ledger does not reach the narration check: {problem}"]
    for txn in _transactions(parsed):
        for token in _SI.findall(txn.narration) + _SI.findall(txn.payee or ""):
            if token not in universe:
                out.append(f"the ledger entry of {txn.date} names {token}, which is not in the invoice "
                           f"universe")
    return out


def _string_limits_respected(c: Candidate, name: str) -> list:
    """`TEXT_MAX_CODEPOINTS` over every string the boundary will read back.

    That is the CSV cells and the ledgers' quoted payee/narration strings —
    a memo over the cap renders a ledger the parse boundary refuses, so it
    bounds the authored free text too. It is NOT a bound on the prose files
    (`policy.md`, `manifest.md`): those are read by a person, never parsed
    into a payee or a narration, and holding them to a parser's field width
    would be a limit nothing enforces.
    """
    out = []
    variant, public = c.variants[name], c.public(name)
    for file_name in sorted(public):
        text = public[file_name]
        if file_name.endswith(".csv"):
            for index, row in enumerate(csv.reader(io.StringIO(text)), start=1):
                for column, cell in enumerate(row):
                    if len(cell) > TEXT_MAX_CODEPOINTS:
                        out.append(f"{file_name} line {index} column {column} is {len(cell)} codepoints, over "
                                   f"the shipped limit of {TEXT_MAX_CODEPOINTS}")
        elif file_name.endswith(".beancount"):
            for match in _LEDGER_STRING.finditer(text):
                if len(match.group(1)) > TEXT_MAX_CODEPOINTS:
                    out.append(f"{file_name} carries a {len(match.group(1))}-codepoint string, over the "
                               f"shipped limit of {TEXT_MAX_CODEPOINTS}")
    for match in _LEDGER_STRING.finditer(variant.golden_ledger):
        if len(match.group(1)) > TEXT_MAX_CODEPOINTS:
            out.append(f"the golden ledger carries a {len(match.group(1))}-codepoint string")
    return out


def _delivery_envelope_respected(c: Candidate, name: str) -> list:
    from ..beancount_ledger import application_envelope_breach, ledger_envelope_breach

    out = []
    variant, public = c.variants[name], c.public(name)
    for title, text in ((CA.LEDGER_FILE, public[CA.LEDGER_FILE]), ("the golden ledger", variant.golden_ledger)):
        breach = ledger_envelope_breach(text.encode("utf-8"))
        if breach is not None:
            out.append(f"{title} is outside the observation envelope: {breach}")
    breach = application_envelope_breach(variant.golden_register.encode("utf-8"))
    if breach is not None:
        out.append(f"the golden register is outside the delivery envelope: {breach}")
    return out


# --------------------------------------------------------------------------
# independent correctness
# --------------------------------------------------------------------------

def _private_derivation_equals_public_fold(c: Candidate, name: str) -> list:
    if CA.application_key(c.application[name]) != c.truth(name).application_key():
        return ["the private derivation and the public fold disagree; two supposedly independent derivations "
                "must not, and decision 3 calls that a defect to investigate rather than a draw to redo"]
    return []


def _planted_repairs_match_public_reading(c: Candidate, name: str) -> list:
    """Every planted repair is the entry the PUBLIC evidence reads, at the
    amount and against the account the public evidence reads.

    The repair's required postings come from the mutation plan; the amount
    and the receivables account come from the public fold. If those two ever
    disagree the golden is right about a month the agent cannot see, which is
    a task no reading of the pack can solve.
    """
    out = []
    variant, ev, truth = c.variants[name], c.evidence[name], c.truth(name)
    receipts = {r.receipt_id: r for r in ev.receipts}
    by_recognition = {row[9]: row for row in truth.receipts}
    accounts = {truth.receivables_account}
    for plant in variant.inputs.planted:
        row = by_recognition.get(plant.recognition_id) if hasattr(plant, "recognition_id") else None
        required = {account: amount for account, amount in plant.required}
        if not required:
            out.append(f"planted item {plant.id} requires no posting")
            continue
        # `required` carries CANONICAL amounts — the scorer's own spelling,
        # which is text — so they are read back as money here rather than
        # compared against a Decimal by luck.
        receivable = [_money(amount) for account, amount in plant.required if account in accounts]
        if not receivable:
            out.append(f"planted item {plant.id} touches no receivables account; a cash-application repair "
                       f"that never reaches {sorted(accounts)} is not one this family plants")
            continue
        amount = -min(receivable)
        matched = [r for r in receipts.values() if r.amount == amount]
        if not matched:
            out.append(f"planted item {plant.id} repairs {amount} against receivables and the public "
                       f"statement carries no receipt at that amount")
        if row is not None and row[3] != amount:
            out.append(f"planted item {plant.id} repairs {amount} and the truth's receipt {row[0]} is {row[3]}")
    ids = [p.id for p in variant.inputs.planted]
    if len(set(ids)) != len(ids):
        out.append(f"two planted items share an id: {sorted(ids)}")
    return out


def _golden_ledger_scores_complete(c: Candidate, name: str) -> list:
    problems, _ledger = ADMIT.golden_ledger_problems(c.variants[name].inputs)
    return list(problems)


def _golden_register_scores_complete(c: Candidate, name: str) -> list:
    variant = c.variants[name]
    return list(ADMIT.golden_register_problems(variant.inputs, variant.golden_register))


# --------------------------------------------------------------------------
# contrast integrity (pair-level)
# --------------------------------------------------------------------------

def _variants_differ_in_declared_fact(c: Candidate) -> list:
    out = []
    fact = c.declared_fact
    if len(c.variants) != 2:
        out.append(f"a pair carries {len(c.variants)} variants")
    if not fact.differs():
        out.append(f"the declared fact {fact.name} reads {fact.values} in both variants; a pair differs in "
                   f"exactly one declared authored fact")
    return out


def _consequences_derived_not_authored(c: Candidate) -> list:
    out = []
    names = c.names
    if len(names) != 2:
        return [f"a pair carries {len(names)} variants"]
    a, b = (c.public(n) for n in names)
    if set(a) != set(b):
        out.append(f"the two variants publish different file sets: {sorted(set(a) ^ set(b))}")
    moved = {key for key in set(a) & set(b) if a[key] != b[key]}
    if not moved:
        out.append("the two variants render the same public bytes")
    allowed = CC.MECHANISM_CONSEQUENCES[c.mechanism]
    if not moved <= allowed:
        out.append(f"the variants differ in {sorted(moved - allowed)}, which the declared fact does not reach; "
                   f"they are two company-months rather than two variants of one")
    return out


def _intended_distinction_changes(c: Candidate) -> list:
    out = []
    names = c.names
    if len(names) != 2:
        return [f"a pair carries {len(names)} variants"]
    first, second = names
    if c.truth(first).application_key() == c.truth(second).application_key():
        out.append("the two variants fold to the same register; the intended accounting distinction does not "
                   "change")
    if CA.application_key(c.application[first]) == CA.application_key(c.application[second]):
        out.append("the two variants' PUBLIC folds agree; whatever moved in the bytes, a reader answers the "
                   "same register for both")
    out += PROFILE.polarity_problems(c.mechanism,
                                     {n: c.variants[n].measurement for n in names}, c.profile)
    return out


# --------------------------------------------------------------------------
# population integrity (pair-level; needs the population ledger)
# --------------------------------------------------------------------------

class PopulationLedger:
    """What a candidate has to be checked against that is not in the
    candidate: every pair admitted before it.

    Two registers, both append-only. The structural one is
    `cash_split.StructureLedger` — imported, not reimplemented, because the
    canonical-structure comparison that strips cosmetic names and absolute
    dates is the thing that makes "no cross-split structural sibling" mean
    anything, and a second copy of it here would be a second thing to keep in
    step. The content one is a map from public-content digest to the public
    id that first published those bytes.

    Probing and recording are SEPARATE. The gate probes; only `mint_group`
    records, and only after the whole gate passed. A candidate that fails its
    fortieth gate must not have been written into the population by its
    third.
    """

    def __init__(self, split_map: SplitMap = SPLIT_MAP):
        self.structures = StructureLedger(split_map)
        self._content: dict = {}
        self._groups: list = []

    def content_collisions(self, c: Candidate) -> list:
        out = []
        digests = {name: c.content_digests[name] for name in c.names}
        if len(set(digests.values())) != len(digests):
            out.append(f"the two variants publish the same bytes: {digests}")
        for name in c.names:
            prior = self._content.get(digests[name])
            if prior is not None:
                out.append(f"variant {name} publishes the bytes already published as {prior}")
        return out

    def structural_siblings(self, c: Candidate) -> list:
        digest = structure_digest(c.template)
        split = self.structures.split_map.split_of(c.template.family)
        prior = self.structures.structures().get(digest)
        if prior is not None and prior[1] != split:
            return [f"{c.template.family} is in {split!r} and its canonical structure already appears in "
                    f"{prior[1]!r} as {prior[0]!r}: a renamed or rescaled sibling cannot become held out"]
        return []

    def record(self, c: Candidate) -> None:
        try:
            self.structures.admit(c.template)
        except StructuralAliasError as exc:
            raise GateUnavailable(f"the structure ledger refused an admitted candidate: {exc}") from exc
        for name in c.names:
            self._content.setdefault(c.content_digests[name], c.variants[name].task.id)
        self._groups.append((c.identity.label(), c.family, tuple(c.content_digests[n] for n in c.names)))

    def groups(self) -> tuple:
        return tuple(self._groups)


def _no_public_content_collision(c: Candidate) -> list:
    ledger = _LEDGER.get(id(c))
    return ledger.content_collisions(c) if ledger is not None else _FRESH.content_collisions(c)


def _no_cross_split_structural_sibling(c: Candidate) -> list:
    ledger = _LEDGER.get(id(c))
    return ledger.structural_siblings(c) if ledger is not None else _FRESH.structural_siblings(c)


def _no_evaluator_provenance_leak(c: Candidate) -> list:
    out = []
    for name in c.names:
        variant = c.variants[name]
        surfaces = {f"{name}/{file_name}": text for file_name, text in variant.public_files.items()}
        surfaces[f"{name}/prompt"] = variant.task.prompt
        surfaces[f"{name}/task_id"] = variant.task.id
        surfaces[f"{name}/world_id"] = variant.world.id
        surfaces[f"{name}/golden_ledger"] = variant.golden_ledger
        surfaces[f"{name}/golden_register"] = variant.golden_register
        out += identity_leaks(surfaces, c.identity, c.seed)
    return out


#: `evaluate` takes the population ledger as an argument, and the two
#: population checks are the only ones that need it. Rather than give every
#: check a second parameter it would ignore, the ledger for the candidate
#: under evaluation is held here for the duration of the call and removed
#: afterwards. `_FRESH` is the empty ledger a caller with no population gets:
#: it can still catch a pair colliding with ITSELF, which is the one
#: collision a single pair can have.
_LEDGER: dict = {}
_FRESH = PopulationLedger()


# --------------------------------------------------------------------------
# gate (o)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class BaselineObservation:
    """One baseline's result on one variant, retained whatever it says."""

    variant: str
    name: str
    role: str                         # "binding" | "diagnostic"
    admitted: bool
    readings: int
    reaches_truth: object             # True / False / None when not admitted

    def view(self) -> dict:
        return {"variant": self.variant, "name": self.name, "role": self.role, "admitted": self.admitted,
                "readings": self.readings, "reaches_truth": self.reaches_truth}


def observe_baselines(c: Candidate, name: str) -> tuple:
    """Every baseline the catalogue declares, run over one variant.

    Returns `(observations, limit_problem_or_None)`. The reading bound is the
    fold's own: `_run` raises when a baseline branches past
    `MAX_BASELINE_READINGS`, and decision 3 says what that means — the
    verification was incomplete, so the candidate is rejected as UNVERIFIED
    rather than admitted as resistant.
    """
    public, kw = c.public(name), c.fold_kwargs(name)
    try:
        report = CA.baseline_report(public, c.application[name], c.evidence[name], **kw)
    except ValueError as exc:
        if "readings" in str(exc):
            return (), (f"{name}: the enumeration exceeded the {CA.MAX_BASELINE_READINGS}-reading bound "
                        f"({exc}); the candidate was NOT shown to resist the baselines")
        raise
    observations = []
    for baseline in CA.BASELINES:
        result = report[baseline.name]
        observations.append(BaselineObservation(
            variant=name, name=baseline.name, role="diagnostic" if baseline.diagnostic else "binding",
            admitted=result.admitted, readings=len(result.readings), reaches_truth=result.reaches_truth))
    return tuple(observations), None


def _no_binding_baseline_reaches_truth(c: Candidate, name: str) -> list:
    observations = _OBSERVED.get((id(c), name))
    if observations is None:
        raise GateUnavailable(f"gate (o) was not observed for variant {name!r}")
    out = []
    for o in observations:
        if o.role == "binding" and o.admitted and o.reaches_truth:
            out.append(f"the binding baseline {o.name} reaches the entire truth through one of its "
                       f"{o.readings} enumerated reading(s)")
    return out


def _reading_bound_respected(c: Candidate, name: str) -> list:
    limit = _LIMITS.get((id(c), name))
    if limit:
        return [limit]
    observations = _OBSERVED.get((id(c), name)) or ()
    return [f"{o.name} enumerated {o.readings} readings, over the bound of {CA.MAX_BASELINE_READINGS}"
            for o in observations if o.readings > CA.MAX_BASELINE_READINGS]


def _diagnostic_baseline_recorded(c: Candidate, name: str) -> list:
    out = []
    observations = _OBSERVED.get((id(c), name))
    if observations is None:
        return [f"gate (o) produced no observations for variant {name!r}"]
    declared = {b.name: ("diagnostic" if b.diagnostic else "binding") for b in CA.BASELINES}
    recorded = {o.name: o.role for o in observations}
    if recorded != declared:
        out.append(f"the recorded roles {recorded} are not the catalogue's {declared}")
    diagnostics = [o for o in observations if o.role == "diagnostic"]
    if not diagnostics:
        out.append("the catalogue declares no diagnostic baseline; decision 3 keeps number_order as one")
    for o in diagnostics:
        if o.admitted and o.reaches_truth is None:
            out.append(f"the diagnostic baseline {o.name} was admitted and its result was not recorded")
    return out


#: gate (o)'s observations and any verification-limit finding, for the
#: candidate under evaluation. Same reason as `_LEDGER`: the baselines are
#: enumerated ONCE per variant and three gates read the result.
_OBSERVED: dict = {}
_LIMITS: dict = {}


# --------------------------------------------------------------------------
# the gate set, and its evaluation
# --------------------------------------------------------------------------

#: gate name -> implementation, for the gates evaluated once per VARIANT. A
#: finding on either variant rejects the pair: decision 3 says "Reject both
#: variants when either fails any acceptance condition", so the pair is the
#: unit and this is where that is true.
VARIANT_CHECKS = {
    "invoice_universe_complete": _invoice_universe_complete,
    "customer_ownership": _customer_ownership,
    "receipt_and_credit_conservation": _receipt_and_credit_conservation,
    "row_identities": _row_identities,
    "ar_reconciles": _ar_reconciles,
    "zero_opening_write_off_balance": _zero_opening_write_off_balance,
    "consistent_sale_and_credit_tax_bases": _consistent_sale_and_credit_tax_bases,
    "cumulative_reversal_bounded": _cumulative_reversal_bounded,
    "genuine_payment_identity": _genuine_payment_identity,
    "unambiguous_advice_binding": _unambiguous_advice_binding,
    "chronology_consistent_with_policy": _chronology_consistent_with_policy,
    "order_insensitive": _order_insensitive,
    "no_refusal_relaxed_by_layout": _no_refusal_relaxed_by_layout,
    "renders_and_parses_through_shipped_boundaries": _renders_and_parses_through_shipped_boundaries,
    "csv_columns_declared": _csv_columns_declared,
    "memo_narration_agreement": _memo_narration_agreement,
    "string_limits_respected": _string_limits_respected,
    "delivery_envelope_respected": _delivery_envelope_respected,
    "private_derivation_equals_public_fold": _private_derivation_equals_public_fold,
    "planted_repairs_match_public_reading": _planted_repairs_match_public_reading,
    "golden_ledger_scores_complete": _golden_ledger_scores_complete,
    "golden_register_scores_complete": _golden_register_scores_complete,
    "no_binding_baseline_reaches_truth": _no_binding_baseline_reaches_truth,
    "reading_bound_respected": _reading_bound_respected,
    "diagnostic_baseline_recorded": _diagnostic_baseline_recorded,
}

#: gate name -> implementation, for the gates that are properties of the PAIR
#: or of the population rather than of one variant.
PAIR_CHECKS = {
    "variants_differ_in_declared_fact": _variants_differ_in_declared_fact,
    "consequences_derived_not_authored": _consequences_derived_not_authored,
    "intended_distinction_changes": _intended_distinction_changes,
    "no_public_content_collision": _no_public_content_collision,
    "no_cross_split_structural_sibling": _no_cross_split_structural_sibling,
    "no_evaluator_provenance_leak": _no_evaluator_provenance_leak,
}


def unimplemented_gates() -> tuple:
    """The declared gates no implementation here covers. Read at call time,
    so adding a name to `cash_manifest.GATE_GROUPS` without writing the check
    stops admission rather than passing silently."""
    covered = set(VARIANT_CHECKS) | set(PAIR_CHECKS)
    return tuple(gate for gate in FM.family_gates() if gate not in covered)


def undeclared_checks() -> tuple:
    """The reverse: an implementation here that the gate set does not
    declare. It would run, could reject a candidate, and would never appear
    in a manifest record's `gates` map — a rejection nobody could audit."""
    declared = set(FM.family_gates())
    return tuple(sorted((set(VARIANT_CHECKS) | set(PAIR_CHECKS)) - declared))


@dataclass(frozen=True)
class Finding:
    gate: str
    group: str
    code: str
    variant: str                      # "" for a pair-level gate
    witness: str

    def view(self) -> dict:
        return {"gate": self.gate, "group": self.group, "code": self.code,
                "variant": self.variant, "witness": self.witness}


@dataclass(frozen=True)
class GateReport:
    """Every declared gate's result, and the witnesses for the ones that
    failed. `gates` is the map a family manifest record binds."""

    gates: dict                       # gate name -> bool
    findings: tuple                   # Finding
    baselines: tuple                  # BaselineObservation, both variants
    reading_counts: dict              # variant -> {baseline: readings}
    verification_limited: bool
    catalogue: str
    catalogue_digest: str
    gate_set: str

    @property
    def passed(self) -> bool:
        return all(self.gates.values())

    @property
    def codes(self) -> tuple:
        seen, out = set(), []
        for finding in self.findings:
            if finding.code not in seen:
                seen.add(finding.code)
                out.append(finding.code)
        return tuple(out)

    def witness(self) -> str:
        return "; ".join(f"{f.code}{('/' + f.variant) if f.variant else ''}: {f.witness}"
                         for f in self.findings[:6])

    def baseline_witness(self) -> str:
        """The relevant baseline, for the census. A verification limit names
        no baseline — that is the point of it — so it names the bound."""
        if self.verification_limited:
            return f"reading-bound/{CA.MAX_BASELINE_READINGS}"
        reached = [o for o in self.baselines if o.role == "binding" and o.admitted and o.reaches_truth]
        return ",".join(sorted({f"{o.name}/{o.variant}" for o in reached}))

    def view(self) -> dict:
        return {"gates": dict(sorted(self.gates.items())),
                "findings": [f.view() for f in self.findings],
                "baselines": [o.view() for o in self.baselines],
                "verification_limited": self.verification_limited,
                "catalogue": self.catalogue, "catalogue_digest": self.catalogue_digest,
                "gate_set": self.gate_set}


def evaluate(c: Candidate, ledger: PopulationLedger | None = None) -> GateReport:
    """Every gate `cash_manifest.family_gates()` declares, evaluated by name
    on this candidate pair.

    Fails closed twice over: a declared gate with no implementation and an
    implementation the gate set does not declare both raise
    `GateUnavailable`, because the first would be a condition nobody checked
    and the second a rejection nobody could audit.
    """
    missing, extra = unimplemented_gates(), undeclared_checks()
    if missing or extra:
        raise GateUnavailable(f"the gate set and its implementations disagree: declared without an "
                              f"implementation {list(missing)}, implemented without a declaration "
                              f"{list(extra)}")
    codes = rejection_codes()
    gates = {gate: True for gate in FM.family_gates()}
    findings: list = []
    observations: list = []
    limited = False

    key = id(c)
    _LEDGER[key] = ledger if ledger is not None else PopulationLedger()
    try:
        for name in c.names:
            seen, limit = observe_baselines(c, name)
            _OBSERVED[(key, name)] = seen
            _LIMITS[(key, name)] = limit
            observations += list(seen)
            limited = limited or bool(limit)
        for gate, check in sorted(VARIANT_CHECKS.items()):
            for name in c.names:
                for witness in check(c, name):
                    gates[gate] = False
                    findings.append(Finding(gate, group_of(gate), codes[gate], name, witness))
        for gate, check in sorted(PAIR_CHECKS.items()):
            for witness in check(c):
                gates[gate] = False
                findings.append(Finding(gate, group_of(gate), codes[gate], "", witness))
    finally:
        _LEDGER.pop(key, None)
        for name in c.names:
            _OBSERVED.pop((key, name), None)
            _LIMITS.pop((key, name), None)

    counts = {name: {o.name: o.readings for o in observations if o.variant == name} for name in c.names}
    return GateReport(gates=gates, findings=tuple(findings), baselines=tuple(observations),
                      reading_counts=counts, verification_limited=limited,
                      catalogue=FM.BASELINE_CATALOGUE_ID, catalogue_digest=FM.baseline_catalogue_digest(),
                      gate_set=FM.gate_set_digest())


# --------------------------------------------------------------------------
# the census
# --------------------------------------------------------------------------

def component_versions() -> dict:
    """Every version an attempt was evaluated under: the construction, this
    gate, the profile machinery's declared exclusions, the baseline catalogue
    and every semantic component a family record binds."""
    return {
        "construction": CC.CONSTRUCTION_VERSION,
        "template": CC.TEMPLATE_VERSION,
        "gate": GATE_VERSION,
        "baseline_catalogue": FM.BASELINE_CATALOGUE_ID,
        "baseline_catalogue_digest": FM.baseline_catalogue_digest(),
        "gate_set": FM.gate_set_digest(),
        "max_baseline_readings": CA.MAX_BASELINE_READINGS,
        "max_layout_attempts": MAX_LAYOUT_ATTEMPTS,
        "semantic_components": FM.semantic_components(),
        "runtime_scope": FM.runtime_scope(),
    }


def components_digest(components: dict | None = None) -> str:
    return domain_digest(_CENSUS_DOMAIN, canonical_bytes(components or component_versions()))[:16]


@dataclass(frozen=True)
class Attempt:
    """One attempt, retained whatever it did.

    Decision 3: "Retain every attempt's ordinal, stage, evaluated rejection
    codes, relevant baseline and witness, reading count, component versions
    and content digest where rendering succeeded." Every field below is one
    of those, and `reason` is an alias for `witness` so that a reader written
    against the construction's earlier census keeps working.
    """

    ordinal: int
    stage: str                        # attempt | draw | render | pair | gate
    outcome: str                      # accepted | refused
    codes: tuple = ()
    witness: str = ""
    baseline: str = ""
    reading_counts: tuple = ()        # ((variant, baseline, readings), ...)
    components: str = ""
    content_digests: tuple = ()       # ((variant, digest), ...)

    @property
    def reason(self) -> str:
        return self.witness

    @property
    def readings(self) -> int:
        return max((count for _v, _b, count in self.reading_counts), default=0)

    def view(self) -> dict:
        return {"ordinal": self.ordinal, "stage": self.stage, "outcome": self.outcome,
                "codes": list(self.codes), "witness": self.witness, "baseline": self.baseline,
                "reading_counts": [list(row) for row in self.reading_counts],
                "components": self.components,
                "content_digests": [list(row) for row in self.content_digests]}


@dataclass(frozen=True)
class GroupCensus:
    """The complete record of one parent group's bounded attempts."""

    group: str                        # the identity's label: the NAMED group
    identity_digest: str
    family: str
    mechanism: str
    split: str
    profile: str
    population: str
    outcome: str                      # admitted | exhausted
    accepted_attempt: int | None
    attempts: tuple
    components: dict = field(default_factory=dict)

    @property
    def refusals(self) -> tuple:
        return tuple(a for a in self.attempts if a.outcome == "refused")

    def distribution(self) -> dict:
        counts: dict = {}
        for attempt in self.attempts:
            for code in attempt.codes:
                counts[code] = counts.get(code, 0) + 1
        return dict(sorted(counts.items()))

    def view(self) -> dict:
        return {"group": self.group, "identity_digest": self.identity_digest, "family": self.family,
                "mechanism": self.mechanism, "split": self.split, "profile": self.profile,
                "population": self.population, "outcome": self.outcome,
                "accepted_attempt": self.accepted_attempt,
                "attempts": [a.view() for a in self.attempts],
                "rejection_distribution": self.distribution(),
                "components": self.components}


@dataclass(frozen=True)
class MintedGroup:
    pair: CC.CandidatePair
    report: GateReport
    census: GroupCensus


def _attempt_from_refusal(ordinal: int, exc: CC.ConstructionRefused, components: str) -> Attempt:
    return Attempt(ordinal=ordinal, stage=getattr(exc, "stage", CC.DRAW_STAGE), outcome="refused",
                   codes=(getattr(exc, "code", CC.DRAW_REFUSAL_CODE),), witness=str(exc),
                   components=components)


def _attempt_from_report(ordinal: int, c: Candidate, report: GateReport, components: str) -> Attempt:
    counts = tuple((variant, baseline, count)
                   for variant in sorted(report.reading_counts)
                   for baseline, count in sorted(report.reading_counts[variant].items()))
    return Attempt(ordinal=ordinal, stage="gate", outcome="accepted" if report.passed else "refused",
                   codes=report.codes, witness=report.witness(), baseline=report.baseline_witness(),
                   reading_counts=counts, components=components,
                   content_digests=tuple((n, c.content_digests[n]) for n in c.names))


def mint_group(ident: ConstructionIdentity, profile: GenerationProfile = BOUNDED_V1,
               secret: bytes | None = None, ledger: PopulationLedger | None = None) -> MintedGroup:
    """Candidate construction, attempt order, acceptance, rejection, profile
    assignment and split membership are determined solely by the frozen
    generation specification and declared model-independent checks. No
    learned-model output, score, success or failure label, token usage or
    trajectory may influence those decisions. All bounded attempts and
    evaluated rejection reasons are retained. Model observations may motivate
    a separately versioned future specification; they may not select or alter
    members of this version.

    ---

    Up to `MAX_LAYOUT_ATTEMPTS` deterministic attempts at one parent group.
    Each attempt is constructed by `cash_construct.construct` and then put
    through every gate `cash_manifest.family_gates()` declares; both variants
    are rejected when either fails any acceptance condition, and exhaustion
    raises a NAMED failed group rather than advancing to a replacement
    selector.

    What is retried and what is not is decision 3's classification, not a
    convenience: a `ConstructionRefused` and a failed gate are expected
    outcomes of a draw and the next attempt follows; a `ConstructionDefect`,
    a `GateUnavailable` and any other exception leave the loop untouched, so
    a defect is investigated rather than drawn past until it disappears.
    """
    components = component_versions()
    digest = components_digest(components)
    seed = parent_seed(ident, secret)
    census: list = []
    accepted = None
    for ordinal in range(MAX_LAYOUT_ATTEMPTS):
        try:
            rendered, fact, template = CC.construct(ident, ordinal, profile, secret)
        except CC.ConstructionRefused as exc:
            census.append(_attempt_from_refusal(ordinal, exc, digest))
            continue
        candidate = candidate_of(ident, profile, ordinal, rendered, fact, template, seed)
        report = evaluate(candidate, ledger)
        census.append(_attempt_from_report(ordinal, candidate, report, digest))
        if report.passed:
            accepted = (candidate, report)
            break
    record = GroupCensus(
        group=ident.label(), identity_digest=ident.digest(), family=ident.template_family,
        mechanism=CC.shape_of(ident.template_family).mechanism, split=ident.split,
        profile=profile.name, population=ident.population,
        outcome="admitted" if accepted else "exhausted",
        accepted_attempt=accepted[0].attempt if accepted else None,
        attempts=tuple(census), components=components)
    if accepted is None:
        reasons = sorted({code for attempt in census for code in attempt.codes})
        raise GroupExhausted(
            f"group {ident.label()} is EXHAUSTED after {MAX_LAYOUT_ATTEMPTS} attempts; it is a named failed "
            f"group and no replacement selector is drawn. Codes: " + ", ".join(reasons[:8]),
            census=record, stage="group", code=EXHAUSTION_CODE)
    candidate, report = accepted
    (ledger if ledger is not None else PopulationLedger()).record(candidate)
    pair = CC.CandidatePair(identity=ident, family=candidate.family, mechanism=candidate.mechanism,
                            attempt=candidate.attempt, declared_fact=candidate.declared_fact,
                            variants=candidate.variants, template=candidate.template,
                            census=tuple(census))
    return MintedGroup(pair=pair, report=report, census=record)


def mint_population(identities, profile: GenerationProfile = BOUNDED_V1, secret: bytes | None = None,
                    ledger: PopulationLedger | None = None) -> tuple:
    """Mint a set of parent groups against ONE population ledger, so that the
    two population gates are evaluated against the pairs already admitted.

    Returns `(minted, censuses)`. An exhausted group is a named failure and
    is recorded in the censuses; it does not stop the rest of the population,
    and no replacement selector is drawn for it. A defect stops everything.
    """
    ledger = ledger if ledger is not None else PopulationLedger()
    minted, censuses = [], []
    for ident in identities:
        try:
            group = mint_group(ident, profile, secret, ledger)
        except GroupExhausted as exc:
            # The group's OWN census, with all sixty-four attempts and their
            # codes, plus one closing row naming the group failure itself.
            record = exc.census
            censuses.append(dataclasses.replace(
                record, attempts=record.attempts + (
                    Attempt(ordinal=len(record.attempts), stage="group", outcome="refused",
                            codes=(EXHAUSTION_CODE,), witness=str(exc),
                            components=components_digest(record.components)),)))
            continue
        minted.append(group)
        censuses.append(group.census)
    return tuple(minted), tuple(censuses)


def aggregate(censuses) -> dict:
    """Decision 3: "Publish aggregate acceptance rates, exhaustion counts and
    rejection distributions."

    Acceptance is counted two ways on purpose. Per GROUP it is the share of
    parent groups that were minted at all; per ATTEMPT it is the share of
    bounded attempts that were accepted, which is the number that says how
    hard the specification is to satisfy. Reporting only the first would hide
    a group that took sixty-three refusals to mint.
    """
    censuses = list(censuses)
    groups = len(censuses)
    admitted = [c for c in censuses if c.outcome == "admitted"]
    attempts = [a for c in censuses for a in c.attempts]
    accepted = [a for a in attempts if a.outcome == "accepted"]
    distribution: dict = {}
    by_stage: dict = {}
    for attempt in attempts:
        by_stage[attempt.stage] = by_stage.get(attempt.stage, 0) + 1
        for code in attempt.codes:
            distribution[code] = distribution.get(code, 0) + 1
    by_mechanism: dict = {}
    for census in censuses:
        row = by_mechanism.setdefault(census.mechanism, {"groups": 0, "admitted": 0, "attempts": 0})
        row["groups"] += 1
        row["admitted"] += 1 if census.outcome == "admitted" else 0
        row["attempts"] += len(census.attempts)
    return {
        "groups": groups,
        "admitted_groups": len(admitted),
        "exhausted_groups": groups - len(admitted),
        "group_acceptance_rate": (len(admitted) / groups) if groups else None,
        "attempts": len(attempts),
        "accepted_attempts": len(accepted),
        "attempt_acceptance_rate": (len(accepted) / len(attempts)) if attempts else None,
        "attempts_per_admitted_group": (
            sum(len(c.attempts) for c in admitted) / len(admitted)) if admitted else None,
        "rejection_distribution": dict(sorted(distribution.items())),
        "attempts_by_stage": dict(sorted(by_stage.items())),
        "by_mechanism": {k: by_mechanism[k] for k in sorted(by_mechanism)},
        "components": components_digest(),
    }


__all__ = [
    "GATE_VERSION", "GateUnavailable", "GroupExhausted",
    "GROUP_PREFIX", "VERIFICATION_LIMIT", "EXHAUSTION_CODE", "code_of", "rejection_codes", "group_of",
    "DECLARED_REFUSALS", "FORBIDDEN_WARNINGS", "DECLARED_COLUMNS",
    "Candidate", "candidate_of", "Finding", "GateReport", "BaselineObservation", "observe_baselines",
    "VARIANT_CHECKS", "PAIR_CHECKS", "unimplemented_gates", "undeclared_checks", "evaluate",
    "PopulationLedger",
    "component_versions", "components_digest", "Attempt", "GroupCensus", "MintedGroup",
    "mint_group", "mint_population", "aggregate",
]
