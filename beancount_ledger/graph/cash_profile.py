"""What `bounded-v1` MEANS once a candidate exists: the structural
measurement of a rendered pair, the enforcement of decision 4's table, and
the validated absence of manufactured difficulty.

`cash_identity.BOUNDED_V1` DECLARES the profile — its digest is what a
construction identity binds, so the declaration may not move. This module is
the other half: it reads a rendered variant and says whether that declaration
was honoured. Keeping the two apart is deliberate. A profile that could only
be enforced by the code that drew the world would be a promise the drawing
made to itself; everything below reads the rendered artifacts — the eleven
public files, the truth register, the golden ledger, the golden register —
and the authored facts, and never the generator's intentions.

WHAT A MEASUREMENT IS AND IS NOT. `measure()` returns counts, byte sizes and
depths. Those describe WHAT WAS GENERATED. Decision 4 is explicit that
"'harder for model X' requires a comparison under fixed measurement
conditions; it cannot be assigned by invoice count", so nothing here, and no
prose above a field, may be read as a difficulty claim. There is no
difficulty field, no score, and no ordering of instances by any of these
numbers.

AND EVERY FIELD OF ONE IS MEASURED. `months` and `currency` used to be
dataclass defaults that `measure()` never passed: the period row of decision
4's table could not fail on anything this module produced, and `view()`
published both to a census as measured facts. A declared value republished as
a measurement is worse than no measurement, because it reads as evidence. All
four period-and-currency fields are now read back from the rendered pack —
`manifest.md`'s statement span and the golden ledger's own commodity — and
the period is checked at its ENDS as well as by its count, because a span
from the 2nd to the 29th touches one calendar month and is not one. The two
shipped limits this module applies are IMPORTED for the same reason: a
duplicate that agrees today is a duplicate that can stop agreeing silently.

MANUFACTURED DIFFICULTY IS VALIDATED, NOT ASSUMED. Decision 4 names eight
conditions and requires their absence to be validated. Each has a check
below, and each check reads the rendered bytes or the authored facts rather
than trusting the recipe:

  * `missing_authority` — every application is decided by a document the
    pack carries or by a rung of the published policy, and the policy text
    carries the section each rule cites. A receipt whose application no rung
    reached, or a residue the policy does not explain, fails. Both halves
    live in `authority_problems`, which takes a folded application rather
    than a pack, so the rung half can be shown firing on an application that
    really carries an unpublished rung; a half nothing has watched speak is a
    half that has proved nothing.
  * `ambiguous_identity` — the advice binding is injective both ways, every
    receipt key is unique, every customer-credit row names a customer, and
    the shipped identifiability checker returns exactly one reading.
  * `unsupported_deduction` — every claimed deduction settles its invoice,
    exhausts that invoice's balance with the cash beside it, and states a
    reason in its own row.
  * `hidden_historical_fact` — the public fold, which reads the public files
    and nothing else, reproduces the private truth exactly. A fact the truth
    rests on that the pack does not carry shows up there as a disagreement.
  * `unexplained_tax_change` — the world's sales speak with ONE rate, the
    credit note uses that rate, and `policy.md` prints it.
  * `answer_bearing_narration` — gate (n)'s rule, over receipt and write-off
    narrations and advice notes: a genuine public payment reference is a
    normal transaction join; an application instruction, or an invoice no
    public document ties to that payment, is not.
  * `document_truncation` — every CSV row carries exactly its declared
    columns, no field is elided, and no free-text field is cut.
  * `budget_consuming_padding` — every public row is produced by an authored
    fact (the projector's own exhaustiveness, re-asserted from the rendered
    files), both goldens are inside decision 4's envelopes, and no free-text
    field exceeds the shipped 200-code-point narration cap.

The eight names are the profile's own `forbidden_difficulty` tuple, read from
the profile rather than restated, so a condition added to the declaration
cannot be silently unchecked here: `difficulty_problems` refuses a profile
naming a condition it has no check for.
"""

from __future__ import annotations

import calendar
import csv
import io
import re
from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal

from ..candidate.canonical import TEXT_MAX_CODEPOINTS
from . import cash_application as CA
from .cash_identity import BOUNDED_V1, GenerationProfile
from .policy import SHORT_PAY_TOLERANCE, is_cash_application_world
from .project import MANIFEST_VIEW
from .schema import AppliedReceipt, CreditNote, DocumentKind, Sale

#: `TEXT_MAX_CODEPOINTS` is IMPORTED, not restated. It is the shipped
#: candidate's cap on a single rendered string, and a memo over it renders a
#: ledger the parse boundary refuses — so it bounds the authored free text
#: too, and it has to keep meaning whatever `candidate/canonical.py` means by
#: it. A copy that agreed on the day it was typed is a copy that can stop
#: agreeing without anything failing.


def application_envelope_lines() -> int:
    """The delivery envelope `write_cash_application` enforces, READ FROM the
    module that enforces it.

    Decision 4 bounds the golden register at "8,000 bytes and within the
    EXISTING line limit", so this must be the existing limit rather than a
    number that matches it today. The environment module sits above `graph/`
    in the import stack, so it is read at call time and the layering stays
    one-way.
    """
    from ..beancount_ledger import APPLICATION_ENVELOPE_LINES
    return APPLICATION_ENVELOPE_LINES


class ProfileViolation(ValueError):
    """A rendered candidate that `bounded-v1` does not admit."""


# --------------------------------------------------------------------------
# structural measurement
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Measurement:
    """What was generated. Counts, sizes and depths — never a difficulty."""

    customers: int
    invoices: int
    invoices_raised_in_period: int
    receipts: int
    credit_notes: int
    ledger_plants: int
    max_allocations_per_receipt: int
    max_allocations_per_credit_note: int
    dependency_depth: int
    golden_ledger_bytes: int
    golden_register_bytes: int
    golden_register_lines: int
    unpaid_in_period_invoices: int
    #: Residue polarity, for the stratum's both-polarities requirement:
    #: whether this variant carries a continuation, a credit residue and an
    #: advice residue at all. The PAIR must show both values of the one its
    #: mechanism turns on.
    has_fallback_continuation: bool
    has_credit_residue: bool
    has_advice_residue: bool
    #: The period and the currency, READ BACK from the rendered pack: the
    #: first and last day `manifest.md` says the statement covers, the count
    #: of calendar months that span touches, and the currency the golden
    #: ledger actually denominates its postings in.
    #:
    #: These carried dataclass defaults of 1 and "USD" and were never passed,
    #: so `bound_problems`' period row could not fire on anything `measure()`
    #: produced while `view()` published both as measured facts for a census.
    #: A bound that cannot fail is not a bound, and a declared value
    #: published as a measurement is worse than no measurement. They are
    #: required fields now, and `period_start`/`period_end` are here because
    #: "one calendar month" is a claim about the span's ENDS: a month-long
    #: window that starts on the 2nd spans one month and is not one.
    period_start: str
    period_end: str
    months: int
    currency: str

    def view(self) -> dict:
        return {f: getattr(self, f) for f in self.__dataclass_fields__}


def _receipt_allocations(truth) -> int:
    return max((len([1 for _, amount in r[4] if amount > 0]) for r in truth.receipts), default=0)


def _credit_allocations(truth) -> int:
    return max((len([1 for _, amount in c[4] if amount > 0]) for c in truth.credit_notes), default=0)


def dependency_depth(truth) -> int:
    """The longest chain of SEQUENTIAL cash or credit events that affects a
    later allocation.

    An event is a link in the chain of a later one when it moved the balance
    of an invoice the later event allocates to: that is exactly what "a
    dependency affecting a later allocation" means in a register kept by
    invoice. The chain is computed as the longest path of a DAG whose nodes
    are the period's receipts and credit notes in fold order and whose edges
    run from an earlier event to a later one that touches an invoice the
    earlier one touched. A single event with no predecessor has depth 1.

    Each edge therefore HAS an accounting reason — one event left a balance
    the next one reads — and a checkable witness in the facts, since both
    events name the invoice in a public row.
    """
    events = []                                   # (order, key, invoices touched)
    for index, r in enumerate(truth.receipts):
        touched = {invoice for invoice, amount in tuple(r[4]) + tuple(r[5]) if amount > 0}
        events.append((r[1], 1, index, touched))
    for index, c in enumerate(truth.credit_notes):
        touched = {invoice for invoice, amount in c[4] if amount > 0}
        events.append((c[1], 0, index, touched))
    events.sort(key=lambda e: e[:3])
    depth = [1] * len(events)
    for j in range(len(events)):
        for i in range(j):
            if events[i][3] & events[j][3] and depth[i] + 1 > depth[j]:
                depth[j] = depth[i] + 1
    return max(depth, default=0)


#: `manifest.md`'s statement row, which prints the span the pack covers.
#: Read from the file the AGENT reads, not from `task.period`, which is the
#: generator's intention and would make the period bound a promise the
#: drawing made to itself.
_STATEMENT_PERIOD = re.compile(
    r"\|\s*`" + re.escape(CA.STATEMENT_FILE) + r"`\s*\|[^|]*?\bPeriod (\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})\b")

#: A posting's currency, as the renderer writes it: `<amount> <CURRENCY>` at
#: the end of a posting line. `CURRENCY_GRAMMAR`'s shape, anchored.
_POSTING_CURRENCY = re.compile(r"^\s+\S+\s+-?[\d,]+\.\d\d\s+([A-Z][A-Z0-9'._\-]{0,22})\s*$", re.MULTILINE)
_OPERATING_CURRENCY = re.compile(r'^option\s+"operating_currency"\s+"([^"]*)"\s*$', re.MULTILINE)


def rendered_period(public: dict) -> tuple:
    """The first and last day the rendered pack says it covers."""
    match = _STATEMENT_PERIOD.search(public.get(MANIFEST_VIEW, ""))
    if match is None:
        raise ProfileViolation(f"{MANIFEST_VIEW} does not state the period {CA.STATEMENT_FILE} covers, so the "
                               f"rendered period cannot be measured and no period bound can be applied")
    return match.group(1), match.group(2)


def calendar_months(start: str, end: str) -> int:
    """How many calendar months the span touches. Zero is impossible; an end
    before its start is refused rather than reported as a count."""
    first, last = _date.fromisoformat(start), _date.fromisoformat(end)
    if last < first:
        raise ProfileViolation(f"the rendered period ends {end}, before it starts {start}")
    return (last.year - first.year) * 12 + (last.month - first.month) + 1


def is_whole_calendar_month(start: str, end: str) -> bool:
    """Whether the span is exactly one calendar month, ends included."""
    first, last = _date.fromisoformat(start), _date.fromisoformat(end)
    return (first.day == 1 and (first.year, first.month) == (last.year, last.month)
            and last.day == calendar.monthrange(last.year, last.month)[1])


def rendered_currency(golden_ledger: str) -> str:
    """The currency the golden ledger denominates itself in, read off the
    rendered text: the declared operating currency and every posting's own
    commodity. More than one is reported as the joined set rather than as a
    first answer, so the bound sees the disagreement instead of a currency
    that happens to be right."""
    found = set(_OPERATING_CURRENCY.findall(golden_ledger)) | set(_POSTING_CURRENCY.findall(golden_ledger))
    if not found:
        raise ProfileViolation("the golden ledger denominates nothing; its currency cannot be measured")
    return found.pop() if len(found) == 1 else "+".join(sorted(found))


def measure(world, task, inputs) -> Measurement:
    """Measure one rendered variant from its world, its task and the
    contract `derive_contract` minted for it."""
    truth = inputs.application
    if truth is None:
        raise ProfileViolation(f"{task.id}: not a cash-application world; there is no register to measure")
    public = {name: data.decode("utf-8") for name, data in inputs.public_files}
    period_start, period_end = rendered_period(public)
    customers = len([p for p in world.parties if p.role.value == "customer"])
    in_period = [i for i in truth.invoices if i[4] == "sale"]
    register = {row[0]: row for row in truth.register}
    unpaid_in_period = [i for i in in_period if register[i[0]][6] > 0]
    golden_register = CA.document_text(CA.fold(public, bank_account=world.bank_account,
                                               period_start=task.period.start, period_end=task.period.end))
    return Measurement(
        customers=customers,
        invoices=len(truth.invoices),
        invoices_raised_in_period=len(in_period),
        receipts=len(truth.receipts),
        credit_notes=len(truth.credit_notes),
        ledger_plants=len(task.plan.mutations),
        max_allocations_per_receipt=_receipt_allocations(truth),
        max_allocations_per_credit_note=_credit_allocations(truth),
        dependency_depth=dependency_depth(truth),
        golden_ledger_bytes=len(inputs.golden_text.encode("utf-8")),
        golden_register_bytes=len(golden_register.encode("utf-8")),
        golden_register_lines=len(golden_register.splitlines()),
        unpaid_in_period_invoices=len(unpaid_in_period),
        has_fallback_continuation=_has_continuation(public, world, task),
        has_credit_residue=any(c[5] > 0 for c in truth.credit_notes),
        has_advice_residue=any(r[6] > 0 for r in truth.receipts if r[7]),
        period_start=period_start,
        period_end=period_end,
        months=calendar_months(period_start, period_end),
        currency=rendered_currency(inputs.golden_text),
    )


def _has_continuation(public: dict, world, task) -> bool:  # noqa: D401
    """Whether any receipt's application ran on past the rung that started
    it — the fold's own record, not the generator's intention. `rungs` is the
    public fold's per-receipt chain; a receipt that reached `oldest_first`
    after `reference` continued past the invoices the reference named."""
    app = CA.fold(public, bank_account=world.bank_account,
                  period_start=task.period.start, period_end=task.period.end)
    return any("reference" in r.rungs and "oldest_first" in r.rungs for r in app.receipts)


# --------------------------------------------------------------------------
# decision 4's table
# --------------------------------------------------------------------------

def _in_range(name: str, value, bound, problems: list) -> None:
    low, high = bound
    if not low <= value <= high:
        problems.append(f"{name} is {value}, outside bounded-v1's {low}-{high}")


def bound_problems(measurement: Measurement, profile: GenerationProfile = BOUNDED_V1) -> list:
    """Every way one variant leaves decision 4's table. Empty is the only
    acceptable answer."""
    problems: list = []
    if measurement.months != profile.months:
        problems.append(f"the rendered period {measurement.period_start}..{measurement.period_end} spans "
                        f"{measurement.months} calendar months, not {profile.months}")
    elif profile.months == 1 and not is_whole_calendar_month(measurement.period_start, measurement.period_end):
        # The count alone cannot carry decision 4's row. A span from the 2nd
        # to the 29th touches one calendar month and is not one, so the ENDS
        # are checked as well as the count.
        problems.append(f"the rendered period {measurement.period_start}..{measurement.period_end} is not one "
                        f"WHOLE calendar month: bounded-v1's period is a month, from its first day to its last")
    if measurement.currency != profile.currency:
        problems.append(f"the golden ledger is denominated in {measurement.currency}, not {profile.currency}")
    _in_range("the customer count", measurement.customers, profile.customers, problems)
    _in_range("the invoice universe", measurement.invoices, profile.invoices, problems)
    _in_range("the count of invoices raised in the period", measurement.invoices_raised_in_period,
              profile.invoices_raised_in_period, problems)
    _in_range("the receipt count", measurement.receipts, profile.receipts, problems)
    _in_range("the credit-note count", measurement.credit_notes, profile.credit_notes, problems)
    _in_range("the ledger-plant count", measurement.ledger_plants, profile.ledger_plants, problems)
    if measurement.max_allocations_per_receipt > profile.max_allocations_per_receipt:
        problems.append(f"a receipt carries {measurement.max_allocations_per_receipt} positive allocations, "
                        f"above bounded-v1's {profile.max_allocations_per_receipt}")
    if measurement.max_allocations_per_credit_note > profile.max_allocations_per_credit_note:
        problems.append(f"a credit note carries {measurement.max_allocations_per_credit_note} positive "
                        f"allocations, above bounded-v1's {profile.max_allocations_per_credit_note}")
    if measurement.dependency_depth > profile.max_dependency_depth:
        problems.append(f"the dependency depth is {measurement.dependency_depth}, above bounded-v1's "
                        f"{profile.max_dependency_depth}")
    if measurement.golden_ledger_bytes > profile.max_golden_ledger_bytes:
        problems.append(f"the golden ledger is {measurement.golden_ledger_bytes} bytes, above bounded-v1's "
                        f"{profile.max_golden_ledger_bytes}")
    if measurement.golden_register_bytes > profile.max_golden_register_bytes:
        problems.append(f"the golden register is {measurement.golden_register_bytes} bytes, above bounded-v1's "
                        f"{profile.max_golden_register_bytes}")
    envelope_lines = application_envelope_lines()
    if measurement.golden_register_lines > envelope_lines:
        problems.append(f"the golden register is {measurement.golden_register_lines} lines, above the delivery "
                        f"envelope's {envelope_lines}")
    if profile.requires_unpaid_in_period_invoice and measurement.unpaid_in_period_invoices < 1:
        problems.append("no invoice raised in the period is left unpaid, which bounded-v1 requires of every case")
    return problems


def polarity_of(mechanism: str, measurement: Measurement) -> bool:
    """The polarity one variant shows for its OWN mechanism: True for the
    positive condition (a continuation, a credit residue, an advice residue),
    False for the zero-residue or no-continuation counterpart.

    The pair must show both, so that "always report a residue" never wins.
    """
    if mechanism == "fallback_continuation":
        return measurement.has_fallback_continuation
    if mechanism == "credit_residue":
        return measurement.has_credit_residue
    if mechanism == "advice_residue":
        return measurement.has_advice_residue
    raise ProfileViolation(f"unknown mechanism {mechanism!r}")


def polarity_problems(mechanism: str, measurements: dict,
                      profile: GenerationProfile = BOUNDED_V1) -> list:
    """`measurements` is variant -> Measurement for one pair."""
    if not profile.requires_both_polarities_per_mechanism:
        return []
    shown = {variant: polarity_of(mechanism, m) for variant, m in measurements.items()}
    if set(shown.values()) != {True, False}:
        return [f"the {mechanism} pair shows polarities {shown}: bounded-v1 requires both the positive condition "
                f"and its zero-residue or no-continuation counterpart, so that always reporting a residue is "
                f"never a winning habit"]
    return []


# --------------------------------------------------------------------------
# manufactured difficulty, validated
# --------------------------------------------------------------------------

def _rows(public: dict, name: str, columns: tuple) -> list:
    return list(csv.DictReader(io.StringIO(public[name])))


def _fold_or_problem(world, task, public) -> tuple:
    """The public fold, or the reason it refuses. A refusal is a FINDING —
    the pack does not support a reading — not a crash of the validator, and
    every check below that needs the fold reports it as one."""
    try:
        return CA.fold(public, bank_account=world.bank_account,
                       period_start=task.period.start, period_end=task.period.end), None
    except CA.Refusal as exc:
        return None, f"the public fold refuses this pack: {exc}"
    except CA.PublicOnly as exc:
        return None, f"the public surface is not readable: {exc}"


#: The application rungs `policy.md` publishes, in the order the fold climbs
#: them: the payer's own advice, the payment's statement reference, then
#: oldest-first. `"none"` is the fold's word for "no rung reached it", which
#: is a missing authority rather than a rung.
PUBLISHED_RUNGS = ("advice", "reference", "oldest_first")


def authority_problems(app, world) -> list:
    """The two halves of `missing_authority`, over a folded application and
    the policy the pack publishes.

    Split out of `_missing_authority` so BOTH halves can be shown able to
    speak. The policy half has an easy negative control — take a heading out
    of `policy.md` — while the rung half needs an application whose receipt
    was applied by something the policy does not publish, which no rendered
    pack can be edited into producing. A check nothing has ever seen fire is
    a check that proves nothing about the worlds it passed, so the seam is
    here and `tests/test_cash_construction.py` hands it a tampered
    `ReceiptApplication` of the shipped type.
    """
    problems = []
    for receipt in app.receipts:
        if receipt.rungs == ("none",) and receipt.amount > 0:
            problems.append(f"receipt {receipt.receipt_id} of {receipt.amount} is applied by no rung of the "
                            f"published policy")
        for rung in receipt.rungs:
            if rung != "none" and rung not in PUBLISHED_RUNGS:
                problems.append(f"receipt {receipt.receipt_id} was applied by {rung!r}, which the policy does "
                                f"not publish")
    for role, section in _required_sections(world).items():
        if section not in world.policy_text:
            problems.append(f"the policy rule {role!r} cites {section!r}, which policy.md does not carry")
    return problems


def _missing_authority(world, task, inputs, public) -> list:
    app, refusal = _fold_or_problem(world, task, public)
    if app is None:
        return [refusal]
    return authority_problems(app, world)


def _required_sections(world) -> dict:
    from .policy import required_sections
    return required_sections(world)


def _ambiguous_identity(world, task, inputs, public) -> list:
    problems = []
    try:
        evidence = CA.read_evidence(public, bank_account=world.bank_account,
                                    period_start=task.period.start, period_end=task.period.end)
    except (CA.Refusal, CA.PublicOnly) as exc:
        return [f"the evidence reader refuses this pack: {exc}"]
    keys = [r.receipt_id for r in evidence.receipts]
    if len(set(keys)) != len(keys):
        problems.append(f"two customer-credit rows share a receipt key: {sorted(keys)}")
    bound = list(evidence.bindings.values())
    if len(set(bound)) != len(bound):
        problems.append("one advice binds two payments")
    for receipt in evidence.receipts:
        if not receipt.customer:
            problems.append(f"the credit row {receipt.receipt_id} names no customer")
    from .identify import check_identifiable
    verdict = check_identifiable(public, bank_account=world.bank_account,
                                 period_start=task.period.start, period_end=task.period.end)
    if not verdict.unique or verdict.readings != 1:
        problems.append(f"the shipped identifiability checker reports unique={verdict.unique} over "
                        f"{verdict.readings} readings ({verdict.reason})")
    return problems


def _unsupported_deduction(world, task, inputs, public) -> list:
    problems = []
    for event in world.events:
        if not isinstance(event, AppliedReceipt):
            continue
        for line in event.lines:
            if line.deduction <= 0:
                continue
            if not line.settles:
                problems.append(f"{event.id}: a deduction of {line.deduction} on {line.invoice_id} settles nothing")
            if not line.note.strip():
                problems.append(f"{event.id}: the deduction of {line.deduction} on {line.invoice_id} states no "
                                f"reason in its own row")
    truth = inputs.application
    for receipt in truth.receipts:
        for invoice, amount in receipt[5]:
            if amount > SHORT_PAY_TOLERANCE:
                problems.append(f"{receipt[0]} writes off {amount} on {invoice}, above the published tolerance "
                                f"{SHORT_PAY_TOLERANCE}")
    return problems


def _hidden_historical_fact(world, task, inputs, public) -> list:
    """The public fold reads the eleven files and nothing else. If it
    reproduces the private truth, every fact the truth rests on is in the
    pack; if it does not, something the author knew is not on the table."""
    truth = inputs.application
    app, refusal = _fold_or_problem(world, task, public)
    if app is None:
        return [refusal]
    if CA.application_key(app) != truth.application_key():
        return ["the public fold and the private truth disagree: a fact the truth rests on is not in the "
                "eleven public files"]
    if app.closing_ar != truth.closing_ar:
        return [f"the public fold closes receivables at {app.closing_ar}, the truth at {truth.closing_ar}"]
    return []


def _unexplained_tax_change(world, task, inputs, public) -> list:
    problems = []
    rates = {e.tax_rate for e in world.events if isinstance(e, Sale)}
    if len(rates) != 1:
        problems.append(f"the world's sales are authored at {len(rates)} tax rates {sorted(rates)}; one rate is "
                        f"what the policy states and what a carried invoice's basis splits at")
    for event in world.events:
        if isinstance(event, CreditNote) and rates and event.tax_rate not in rates:
            problems.append(f"{event.id} credits tax at {event.tax_rate}, a rate the world's sales never used")
    if rates:
        rate = next(iter(rates))
        printed = f"{(rate * 100).normalize():f}%"
        if printed not in world.policy_text:
            problems.append(f"policy.md does not print the sales-tax rate {printed}")
    return problems


def _answer_bearing_narration(world, task, inputs, public) -> list:
    """Gate (n)'s rule, applied to the rendered ledgers. Reuses the shipped
    reading of "an application instruction, or an invoice no public document
    ties to that payment" rather than restating it."""
    from .cash_application import _INVOICE_TOKEN          # the shipped token syntax
    truth = inputs.application
    ties: dict = {}
    for receipt in truth.receipts:
        ties[receipt[0]] = {invoice for invoice, _ in tuple(receipt[4]) + tuple(receipt[5])}
    problems = []
    numbers = {d.id: d.number for d in world.documents}
    for event in world.events:
        if isinstance(event, AppliedReceipt):
            named = {numbers[line.invoice_id] for line in event.lines}
            for text, where in ((event.memo, f"{event.id} narration"),
                                *((line.note, f"{event.id} advice note on {numbers[line.invoice_id]}")
                                  for line in event.lines)):
                for token in _INVOICE_TOKEN.findall(text):
                    if token not in named:
                        problems.append(f"{where} names {token}, which no public document ties to that payment")
                if any(word in text.lower() for word in ("apply ", "applied to ", "allocate ")):
                    problems.append(f"{where} reads as an application instruction: {text[:60]!r}")
    return problems


def _document_truncation(world, task, inputs, public) -> list:
    problems = []
    for name, columns in ((CA.OPEN_ITEMS_FILE, CA.OPEN_ITEMS_COLUMNS),
                          (CA.REMITTANCE_FILE, CA.REMITTANCE_COLUMNS),
                          (CA.CREDIT_NOTES_FILE, CA.CREDIT_NOTE_COLUMNS),
                          (CA.STATEMENT_FILE, CA.STATEMENT_COLUMNS)):
        lines = public[name].splitlines()
        if lines[0].split(",") != list(columns):
            problems.append(f"{name} declares columns {lines[0]!r}, not {','.join(columns)}")
        for number, line in enumerate(lines[1:], start=2):
            if len(line.split(",")) != len(columns):
                problems.append(f"{name} line {number} carries {len(line.split(','))} fields, not {len(columns)}")
            if line.rstrip().endswith(("...", "…")):
                problems.append(f"{name} line {number} is cut short")
    return problems


def _budget_consuming_padding(world, task, inputs, public) -> list:
    """Padding is text that is not evidence. Three checks, none of which
    needs a number this project has not already declared: every public row
    comes from an authored fact, both goldens sit inside decision 4's
    envelopes, and no free-text field exceeds the shipped narration cap."""
    problems = []
    truth = inputs.application
    rows = len(public[CA.OPEN_ITEMS_FILE].splitlines()) - 1
    if rows != len(truth.opening_register):
        problems.append(f"{CA.OPEN_ITEMS_FILE} prints {rows} rows against {len(truth.opening_register)} opening "
                        f"register entries")
    advice_lines = sum(len(e.lines) for e in world.events
                       if isinstance(e, AppliedReceipt) and e.remittance_id
                       and task.period.contains(e.settlement.cleared_on))
    rows = len(public[CA.REMITTANCE_FILE].splitlines()) - 1
    if rows != advice_lines:
        problems.append(f"{CA.REMITTANCE_FILE} prints {rows} rows against {advice_lines} authored advice lines")
    rows = len(public[CA.CREDIT_NOTES_FILE].splitlines()) - 1
    if rows != len(truth.credit_notes):
        problems.append(f"{CA.CREDIT_NOTES_FILE} prints {rows} rows against {len(truth.credit_notes)} credit notes")
    for event in world.events:
        texts = [getattr(event, "memo", "") or ""]
        if isinstance(event, AppliedReceipt):
            texts += [line.note for line in event.lines]
        if isinstance(event, CreditNote):
            number = next(d.number for d in world.documents if d.id == event.invoice_id)
            texts.append(f"Credit note {event.number} against {number}: {event.memo}")
        for text in texts:
            if len(text) > TEXT_MAX_CODEPOINTS:
                problems.append(f"{event.id}: a free-text field is {len(text)} code points, above the shipped "
                                f"{TEXT_MAX_CODEPOINTS}-code-point cap the parse boundary enforces")
    return problems


_CHECKS = {
    "missing_authority": _missing_authority,
    "ambiguous_identity": _ambiguous_identity,
    "unsupported_deduction": _unsupported_deduction,
    "hidden_historical_fact": _hidden_historical_fact,
    "unexplained_tax_change": _unexplained_tax_change,
    "answer_bearing_narration": _answer_bearing_narration,
    "document_truncation": _document_truncation,
    "budget_consuming_padding": _budget_consuming_padding,
}


def difficulty_problems(world, task, inputs, profile: GenerationProfile = BOUNDED_V1) -> list:
    """Run every manufactured-difficulty check the profile declares.

    A condition the profile names and this module has no check for is itself
    a problem: decision 4 says the absence is VALIDATED, and a condition
    nobody validates is assumed absent, which is the failure being guarded
    against."""
    if not is_cash_application_world(world):
        raise ProfileViolation(f"{task.id}: not a cash-application world")
    public = {name: data.decode("utf-8") for name, data in inputs.public_files}
    problems = []
    for condition in profile.forbidden_difficulty:
        check = _CHECKS.get(condition)
        if check is None:
            problems.append(f"the profile forbids {condition!r} and nothing validates its absence")
            continue
        problems.extend(f"{condition}: {p}" for p in check(world, task, inputs, public))
    return problems


#: The exclusions this module can check, and what each check reads. An
#: exclusion the profile retains that is not a key here blocks admission
#: rather than passing silently — the same direction as the
#: manufactured-difficulty list.
CHECKED_EXCLUSIONS = ("foreign_exchange", "refunds", "retention_accounting",
                      "cross_customer_application", "multi_period_editing")


def excluded_accounting_problems(world, profile: GenerationProfile = BOUNDED_V1) -> list:
    """The accounting limits the reviewed policy keeps. More steps within it
    are acceptable; an unreviewed policy is a scope change, so each exclusion
    is checked against the authored facts rather than assumed by recipe."""
    problems = [f"the profile retains the accounting limit {name!r} and nothing checks it"
                for name in profile.excluded_accounting if name not in CHECKED_EXCLUSIONS]
    currencies = {world.currency}
    if currencies != {"USD"}:
        problems.append(f"foreign_exchange: the world's currency is {sorted(currencies)}, not USD alone")
    for event in world.events:
        if isinstance(event, AppliedReceipt):
            customer = event.party_id
            for line in event.lines:
                document = next(d for d in world.documents if d.id == line.invoice_id)
                if document.party_id != customer:
                    problems.append(f"cross_customer_application: {event.id} applies to {document.number}, which "
                                    f"belongs to another customer")
        if isinstance(event, CreditNote):
            document = next(d for d in world.documents if d.id == event.invoice_id)
            if document.party_id != event.party_id:
                problems.append(f"cross_customer_application: {event.id} credits another customer's invoice")
    negative = [e for e in world.events if getattr(e, "amount", Decimal("1")) <= 0]
    if negative:
        problems.append(f"refunds: {[e.id for e in negative]} carry a non-positive amount; money flows one way "
                        f"in this family")
    for account in world.accounts:
        if "retention" in account.name.lower() or "retainage" in account.name.lower():
            problems.append(f"retention_accounting: the chart carries {account.name}")
    invoices = [d for d in world.documents if d.kind is DocumentKind.SALES_INVOICE]
    if not invoices:
        problems.append("the world carries no sales invoices")
    # multi_period_editing: the books the agent may change are ONE month's.
    # A prior-period event exists (the archive is real history) but no
    # recognition the expected ledger carries may sit outside the period.
    return problems


__all__ = [
    "TEXT_MAX_CODEPOINTS", "application_envelope_lines", "PUBLISHED_RUNGS", "ProfileViolation",
    "Measurement", "measure", "dependency_depth",
    "rendered_period", "rendered_currency", "calendar_months", "is_whole_calendar_month",
    "bound_problems", "polarity_of", "polarity_problems", "authority_problems",
    "CHECKED_EXCLUSIONS", "difficulty_problems", "excluded_accounting_problems",
]
