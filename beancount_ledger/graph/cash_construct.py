"""The construction path: from a private construction identity to a rendered
candidate PAIR — the eleven public files, the private truth register, the
golden ledger and the golden register, for each of two variants that differ
in exactly one declared authored fact.

Round 16, decision 4 governs this module. `cash_identity.BOUNDED_V1` declares
the bounds; `cash_profile` measures and enforces them against the rendered
artifacts; this module DRAWS the world that has to satisfy them. The three
strata the scope is frozen at — fallback continuation, credit residue, advice
residue — each have a recipe below, and closing-register completeness is
exercised in all three, because every case's register lists every invoice,
zero rows included.

WHAT IS DECLARED AND WHAT IS DRAWN. A structural-template FAMILY declares the
shape: how many customers, how many invoices are carried and how many are
raised in the month, how many receipts, which of them carry an advice and
which are decided by the statement reference, and where the two plants sit.
Nothing about that shape is drawn. What IS drawn from the identity's seed is
the company, the parties, the month, the invoice numbers, the dates and the
amounts. Two instantiations of one family are therefore the same accounting
structure in different clothes — which is exactly why the split map keys on
the family name and keeps every descendant together.

THE PAIR. Both variants grow from ONE parent seed (`cash_identity`'s rule:
"the variant changes its declared fact, not the entire random stream"). The
draw runs once and the recipe is rendered twice, with a single polarity flag.
Every consequence of that one fact — the statement's closing balance, the
ledger, the register, both goldens, the as-found amount of a transposed
plant — is DERIVED by re-folding, never authored twice. `DeclaredFact` names
the fact and its two values, so the contrast is a statement the construction
makes and a test can check rather than a claim in a docstring.

LEGITIMATE COMPLEXITY, AND WHAT IS FORBIDDEN. The work in these months is
maintaining customer-specific balances across evidenced events and applying
the stated authority hierarchy. Every dependency an instance carries has an
accounting reason — one event left a balance the next one reads — and a
checkable witness in the facts, because both events name the invoice in a
public row. `cash_profile.difficulty_problems` validates the ABSENCE of the
eight manufactured-difficulty conditions against the rendered bytes;
`construct` calls it and refuses the attempt when it speaks.

NO MODEL INFLUENCE. Candidate construction, attempt order, acceptance,
rejection, profile assignment and split membership are determined solely by
the frozen generation specification and declared model-independent checks. No
learned-model output, score, success or failure label, token usage or
trajectory may influence those decisions. All bounded attempts and evaluated
rejection reasons are retained. Model observations may motivate a separately
versioned future specification; they may not select or alter members of this
version.

WHAT IS NOT CLAIMED. The measurements `cash_profile` takes describe what was
generated. Nothing here asserts that an instance is harder for any model, and
no structural quantity orders or selects instances.

THE ACCOUNTING IS REUSED, NOT REWRITTEN. The policy text is
`graph/worlds/_variant_pack.policy_text` — the reviewed policy the eleven
authored variants carry, with the accounting review of 2026-09-11's three
clarifications and the credit-note basis paragraph. Introducing an unreviewed
policy would be a scope change; drawing more worlds under the reviewed one is
not. The instruction is that pack's `prompt`, so a generated month asks for
the same two deliverables in the same words. The coupling is deliberate and
has a consequence worth stating: editing that text moves every generated
world's public bytes, which the family manifest's `public_content_digest`
records and a re-preflight has to clear.
"""

from __future__ import annotations

import calendar
import random
from dataclasses import dataclass
from datetime import date as _date
from datetime import timedelta
from decimal import Decimal as D

from . import cash_application as CA
from . import cash_profile as PROFILE
from .cash_identity import (
    BOUNDED_V1,
    MAX_LAYOUT_ATTEMPTS,
    VARIANTS,
    ConstructionIdentity,
    GenerationProfile,
    identity,
    layout_attempt_stream,
    parent_seed,
    stream,
)
from .cash_split import (
    SPLIT_MAP,
    AdviceLineShape,
    CreditNoteShape,
    InvoiceShape,
    PlantShape,
    ReceiptShape,
    StructuralTemplate,
)
from .derive import DerivationError, TaskSpec, derive_contract
from .project import (
    AlterRecognition,
    DuplicateRecognition,
    MutationPlan,
    OmitRecognition,
    Period,
    ProjectionError,
)
from .schema import (
    Account,
    AccountKind as K,
    AppliedReceipt,
    BankFee,
    BankOpening,
    CreditNote,
    CustomerReceipt,
    Document,
    DocumentKind as DK,
    OpeningPosition,
    Party,
    PartyRole as R,
    Rail,
    ReceiptLine,
    Sale,
    Settlement,
    VendorPayment,
    World,
)
from .worlds import _variant_pack as V

CONSTRUCTION_VERSION = 1
TEMPLATE_VERSION = 1

AR = V.AR
WRITE_OFFS = V.WRITE_OFFS
BANK_ACCOUNT = "Assets:Bank:Checking"
INVENTORY = "Assets:Inventory"
PREPAYMENTS = "Assets:Prepayments"
PAYABLES = "Liabilities:AP"
SALES_TAX = "Liabilities:SalesTax-Payable"
SALES = "Income:Sales"
COGS = "Expenses:COGS"
BANK_FEES = "Expenses:BankFees"
OPENING_EQUITY = "Equity:Opening"
CURRENCY = "USD"

ZERO = D("0.00")


class ConstructionRefused(ValueError):
    """This layout attempt cannot be rendered, or the rendered pair fails a
    declared check. Expected; the next attempt is drawn. Decision 3: an
    expected construction failure may be retried."""


class ConstructionDefect(RuntimeError):
    """Something that should be impossible: two supposedly independent
    derivations disagree, or a rendered pair contradicts its own recipe.
    Decision 3 forbids drawing past this — it is a defect to investigate, not
    an opportunity to keep drawing until it disappears."""


# --------------------------------------------------------------------------
# the family shapes
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class FamilyShape:
    """One structural-template family's DECLARED shape. Nothing here is
    drawn; everything here is frozen with the family name, because the split
    map keys on that name and every descendant inherits its assignment."""

    family: str
    mechanism: str
    carried: tuple            # carried invoices per customer, in customer order
    raised: tuple             # invoices raised inside the month, per customer
    receipts: int
    plants: tuple             # two (kind, receipt slot) pairs; kinds omit|alter|duplicate
    scrambled_numbering: bool = False

    @property
    def customers(self) -> int:
        return len(self.carried)

    @property
    def invoices(self) -> int:
        return sum(self.carried) + sum(self.raised)


SHAPES = (
    # fallback continuation — an un-adviced receipt whose cash either does or
    # does not run past the invoices its statement reference names.
    FamilyShape("fc-sedgewick", "fallback_continuation", (3, 4), (1, 1), 3,
                (("omit", 1), ("alter", 2)), scrambled_numbering=True),
    FamilyShape("fc-quarrymill", "fallback_continuation", (3, 4, 2), (1, 1, 1), 4,
                (("omit", 1), ("alter", 2)), scrambled_numbering=True),
    FamilyShape("fc-lintelgate", "fallback_continuation", (4, 5), (1, 2), 3,
                (("duplicate", 0), ("alter", 2)), scrambled_numbering=True),
    FamilyShape("fc-harrowfield", "fallback_continuation", (3, 4, 2), (1, 1, 2), 5,
                (("omit", 3), ("alter", 2)), scrambled_numbering=True),
    FamilyShape("fc-marlowbridge", "fallback_continuation", (4, 4, 2), (1, 2, 1), 4,
                (("alter", 2), ("duplicate", 3)), scrambled_numbering=True),
    # credit residue — a credit note whose gross either does or does not
    # exceed what its customer's open invoices can absorb.
    FamilyShape("cr-gallowtree", "credit_residue", (3, 3), (1, 1), 3,
                (("omit", 1), ("alter", 2))),
    FamilyShape("cr-pikestaff", "credit_residue", (3, 3, 2), (1, 1, 1), 4,
                (("duplicate", 1), ("alter", 3))),
    FamilyShape("cr-brindlecote", "credit_residue", (3, 4), (2, 1), 3,
                (("alter", 1), ("omit", 2))),
    FamilyShape("cr-oysterbank", "credit_residue", (3, 4, 3), (1, 1, 1), 5,
                (("omit", 2), ("duplicate", 4))),
    FamilyShape("cr-ashenford", "credit_residue", (3, 3, 3), (1, 2, 1), 6,
                (("alter", 1), ("omit", 5))),
    # advice residue — an advice whose lines either do or do not exhaust the
    # payment the bank shows, while the payer still has an invoice open.
    FamilyShape("ar-quillmarsh", "advice_residue", (4, 3), (1, 1), 3,
                (("omit", 1), ("duplicate", 0))),
    FamilyShape("ar-tenterhook", "advice_residue", (4, 3, 2), (1, 1, 1), 4,
                (("alter", 0), ("omit", 2))),
    FamilyShape("ar-wickenhall", "advice_residue", (5, 3), (2, 1), 4,
                (("omit", 0), ("duplicate", 2))),
    FamilyShape("ar-coldharbour", "advice_residue", (4, 3, 3), (1, 1, 1), 5,
                (("alter", 3), ("omit", 2))),
    FamilyShape("ar-saltgrave", "advice_residue", (4, 4, 2), (1, 1, 2), 6,
                (("omit", 3), ("duplicate", 4))),
)

SHAPE_BY_FAMILY = {shape.family: shape for shape in SHAPES}

#: The public files a pair's ONE declared fact may reach, per mechanism.
#: Everything else — the chart, the parties, the policy, the opening register,
#: the vendor master, the archive, the manifest — belongs to the PARENT world
#: the two variants share, and a difference there would mean two
#: company-months rather than two readings of one. Enforced at construction:
#: `_pair_problems` refuses a pair whose moved set is not a subset of its
#: mechanism's row.
#:
#: An advice-residue pair moves ONE cell of one file: the money the bank
#: showed did not change, so neither the statement nor the books may.
MECHANISM_CONSEQUENCES = {
    "fallback_continuation": frozenset({"bank_statement.csv", "ledger.beancount"}),
    "credit_residue": frozenset({"credit_notes.csv", "ledger.beancount"}),
    "advice_residue": frozenset({"remittance_advice.csv"}),
}


def shape_of(family: str) -> FamilyShape:
    try:
        return SHAPE_BY_FAMILY[family]
    except KeyError:
        raise ConstructionRefused(f"no structural-template family named {family!r}") from None


# --------------------------------------------------------------------------
# drawn vocabulary
# --------------------------------------------------------------------------

#: Deliberately disjoint from `graph/content.py` — the bank family's pools —
#: and from the eleven authored company-months, so a generated world cannot
#: be mistaken for either and no public-content collision arises by name.
COMPANIES = (
    ("Ashgrove Cordage & Net Co.", "Ashgrove", "Kettleby Mutual Bank"),
    ("Bellmarsh Tile Works LLC", "Bellmarsh", "Whitlow Union Bank"),
    ("Copperline Awning Co.", "Copperline", "Sandgate Commerce Bank"),
    ("Draycott Malt & Grain Co.", "Draycott", "Overton Valley Bank"),
    ("Elmsworth Cabinetry LLC", "Elmsworth", "Barrowdale State Bank"),
    ("Fernhollow Ceramics Co.", "Fernhollow", "Linnet Harbor Bank"),
    ("Gorsewell Signage LLC", "Gorsewell", "Padstow Mercantile Bank"),
    ("Harlington Rope & Canvas Co.", "Harlington", "Beacon Row Savings Bank"),
    ("Inglewood Shutters LLC", "Inglewood", "Caldmore Union Bank"),
    ("Juniper Reach Joinery Co.", "Juniper Reach", "Stanwick Mutual Bank"),
)

CUSTOMER_NAMES = (
    "Aldergate Facilities Group", "Brackenhurst Leisure Partners", "Calloway Marine Services",
    "Dunhollow Retail Holdings", "Eastmoor Hospitality Group", "Fairstead Property Services",
    "Glenhaven Resorts Company", "Hollowbrook Estates Group", "Ivyrise Contract Interiors",
    "Kilnbridge Development Partners", "Larkmead Venue Management", "Maplewick Commercial Trust",
)

VENDOR_NAMES = (
    "Northrop Timber & Board Co", "Orchard Row Fastenings Ltd", "Pennington Coatings Supply",
    "Quarrybrook Materials Co", "Ravenscar Fittings Company", "Stonemill Abrasives Supply",
)

TAX_RATES = (D("0.05"), D("0.06"), D("0.07"), D("0.08"))

CREDIT_REASONS = (
    "Agreed price allowance on goods retained by the customer; no return and no replacement supplied.",
    "Agreed allowance for finish defects on units the customer kept; nothing returned and nothing remade.",
    "Agreed price correction on the rate quoted for work already accepted; no goods came back.",
)


# --------------------------------------------------------------------------
# arithmetic and dates the recipes share
# --------------------------------------------------------------------------

def gross_of(net: D, rate: D) -> D:
    """A sale's gross from its net at the world's one rate. Every net drawn
    below is a multiple of 50 and every rate has two places, so the tax is
    exact and `gross_of(a, r) + gross_of(b, r) == gross_of(a + b, r)` — which
    is what lets a credit note be aimed at an exact open balance without
    rounding drift."""
    return (net + (net * rate).quantize(D("0.01"))).quantize(D("0.01"))


def _iso(day: _date) -> str:
    return day.isoformat()


def _month_days(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _shift_month(year: int, month: int, back: int) -> tuple:
    index = year * 12 + (month - 1) - back
    return index // 12, index % 12 + 1


def _business_before(day: _date) -> _date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _business_after(day: _date) -> _date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _in_month(period: Period, ordinal: int) -> str:
    """The `ordinal`-th day of the period, nudged off the weekend and kept
    inside the month. A statement that shows an ACH clearing on a Sunday is a
    detail a reader notices and nothing in the accounting needs; a date that
    left the month would turn a receipt into an outstanding item."""
    start = _date.fromisoformat(period.start)
    end = _date.fromisoformat(period.end)
    day = start + timedelta(days=max(1, min(ordinal, (end - start).days + 1)) - 1)
    forward = _business_after(day)
    return _iso(forward if forward <= end else _business_before(day))


def _bank_after(period: Period, on: str, lag: int) -> str:
    end = _date.fromisoformat(period.end)
    day = _business_after(_date.fromisoformat(on) + timedelta(days=lag))
    return _iso(day if day <= end else _business_before(end))


# --------------------------------------------------------------------------
# the drawn layout
# --------------------------------------------------------------------------

@dataclass
class _Invoice:
    key: str
    number: str
    customer: int
    issued: str
    net: D                    # the sale's own net; a carried invoice's gross splits at the world's rate
    gross: D
    raised_in_period: bool
    prior_payment: D = ZERO
    cost: D = ZERO

    @property
    def basis(self) -> D:
        return self.gross - self.prior_payment


@dataclass
class _Line:
    invoice: _Invoice
    amount: D
    settles: bool = False
    deduction: D = ZERO
    note: str = ""


@dataclass
class _Receipt:
    slot: int
    customer: int
    doc_date: str
    bank_date: str
    amount: D
    reference: str
    remittance_id: str
    lines: list
    rail: Rail = Rail.ACH_IN

    @property
    def key(self) -> str:
        return f"event:receipt-{self.slot}"

    @property
    def memo(self) -> str:
        return f"Customer payment, {self.reference}"


@dataclass
class _Note:
    number: str
    customer: int
    invoice: _Invoice
    date: str
    net: D
    memo: str
    key: str = "event:credit-note"


@dataclass(frozen=True)
class DeclaredFact:
    """The one authored fact a pair differs in, and its value in each
    variant. Everything else the two worlds differ in is a consequence of
    this and is derived by re-folding."""

    name: str
    values: dict              # variant -> the value as it is printed

    def differs(self) -> bool:
        return len(set(self.values.values())) == len(self.values) > 1


@dataclass
class _Layout:
    shape: FamilyShape
    drawn: dict
    invoices: list
    receipts: list
    note: _Note
    declared_name: str
    declared_value: str
    book: "_Book"


class _Book:
    """The open-item register as a recipe walks the month.

    A construction aid, never the authority: the facts the recipe authors are
    kept consistent with the policy the PUBLIC fold will apply, and the fold
    is then run over the rendered bytes and compared with the private truth
    `derive_application` folds. Two independent derivations that must agree
    is the point; this third walk exists only so the recipe can aim.
    """

    def __init__(self, invoices):
        self.invoices = list(invoices)
        self.open = {i.key: i.basis for i in invoices}

    def open_of(self, customer: int, on: str, exclude=()) -> list:
        rows = [i for i in self.invoices
                if i.customer == customer and i.issued <= on and self.open[i.key] > 0
                and i.key not in exclude]
        return sorted(rows, key=lambda i: (i.issued, i.number))

    def take(self, invoice: _Invoice, amount: D) -> None:
        if amount < 0 or amount > self.open[invoice.key]:
            raise ConstructionRefused(f"{invoice.number}: {amount} is not inside its open balance "
                                      f"{self.open[invoice.key]}")
        self.open[invoice.key] -= amount


# --------------------------------------------------------------------------
# the draw
# --------------------------------------------------------------------------

def _draw_common(rng: random.Random, shape: FamilyShape) -> dict:
    company = COMPANIES[rng.randrange(len(COMPANIES))]
    rate = TAX_RATES[rng.randrange(len(TAX_RATES))]
    year = 2025 + rng.randrange(3)
    month = 1 + rng.randrange(12)
    last = _month_days(year, month)
    period = Period(f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}",
                    f"{calendar.month_name[month]} {year}")
    prior_year, prior_month = _shift_month(year, month, 1)
    prior_last = _month_days(prior_year, prior_month)
    prior = Period(f"{prior_year:04d}-{prior_month:02d}-01",
                   f"{prior_year:04d}-{prior_month:02d}-{prior_last:02d}",
                   f"{calendar.month_name[prior_month]} {prior_year}")
    names = list(CUSTOMER_NAMES)
    rng.shuffle(names)
    terms = ("net 30", "net 45", "net 30")
    customers = tuple((f"party:customer-{index + 1}", names[index], terms[index])
                      for index in range(shape.customers))
    return {"company": company, "rate": rate, "period": period, "prior": prior,
            "customers": customers,
            "vendor": ("party:vendor-1", VENDOR_NAMES[rng.randrange(len(VENDOR_NAMES))]),
            "invoice_base": 3000 + 100 * rng.randrange(60),
            "note_number": 400 + rng.randrange(500),
            "trace_base": rng.randrange(1000000, 9999999),
            "bank_opening": D(1000 * rng.randrange(60, 140)),
            "fee": D(5 * rng.randrange(6, 20)),
            "purchase_nets": (D(500 * rng.randrange(8, 26)), D(500 * rng.randrange(8, 26))),
            "salt": rng.randrange(1, 9973)}


def _numbers(rng: random.Random, base: int, count: int, scrambled: bool) -> list:
    """Invoice numbers for the universe, in issue order. Scrambled means the
    numbers run AGAINST the dates, which the policy's `## Sales invoice
    numbering` section states as a fact of the business — so a reader cannot
    mistake the numbering for a chronology, and the diagnostic number-order
    reading is separated from the published invoice-date order."""
    pool = [base + 1 + index * rng.randrange(2, 6) for index in range(count)]
    for index in range(1, count):
        if pool[index] <= pool[index - 1]:
            pool[index] = pool[index - 1] + 2
    if scrambled:
        rng.shuffle(pool)
    return [f"SI-{value}" for value in pool]


#: When each customer's in-period sales are raised, per mechanism. The target
#: customer's book has to be in a stated state when its target event runs, and
#: an invoice raised in the middle of that is a fact the recipe would have to
#: work around rather than a difficulty worth having.
_SALE_DAYS = {
    "fallback_continuation": {"target": (10, 12), "other": (20, 22, 24)},
    "credit_residue": {"target": (22, 24), "other": (11, 13, 15)},
    "advice_residue": {"target": (11, 13), "other": (15, 17, 19)},
}


def _invoice_universe(rng: random.Random, shape: FamilyShape, drawn: dict) -> list:
    rate = drawn["rate"]
    period = drawn["period"]
    start = _date.fromisoformat(period.start)

    order = []
    remaining = list(shape.carried)
    while any(remaining):
        for owner in range(shape.customers):
            if remaining[owner]:
                order.append(owner)
                remaining[owner] -= 1
    total_carried = len(order)

    span, dates = 100, []
    step = span // (total_carried + 1)
    for index in range(total_carried):
        day = start - timedelta(days=span - index * step - rng.randrange(0, max(1, step - 1)))
        dates.append(_business_after(day))
    dates.sort()
    if len(set(dates)) != total_carried or dates[-1] >= start:
        raise ConstructionRefused("the carried invoices did not draw distinct dates before the period")

    numbers = _numbers(rng, drawn["invoice_base"], shape.invoices, shape.scrambled_numbering)
    invoices = []
    for index, owner in enumerate(order):
        net = D(50 * rng.randrange(20, 96))
        invoices.append(_Invoice(key=f"doc:{numbers[index].lower()}", number=numbers[index], customer=owner,
                                 issued=_iso(dates[index]), net=net, gross=gross_of(net, rate),
                                 raised_in_period=False))

    days = _SALE_DAYS[shape.mechanism]
    cursor = {"target": 0, "other": 0}
    taken: set = set()
    position = total_carried
    for owner in range(shape.customers):
        for _ in range(shape.raised[owner]):
            lane = "target" if owner == 0 else "other"
            if cursor[lane] >= len(days[lane]):
                raise ConstructionRefused(f"the {lane} lane has no day left for an in-period sale")
            ordinal = days[lane][cursor[lane]]
            cursor[lane] += 1
            # The lanes keep each recipe's target customer out of the way of
            # its own target event; two lanes can still land on one business
            # day, and two invoices raised on one day would make the sale
            # dates ambiguous where the register orders by them.
            when = _in_month(period, ordinal)
            for nudge in range(1, 4):
                if when not in taken:
                    break
                when = _in_month(period, ordinal + nudge)
            if when in taken:
                raise ConstructionRefused("two in-period sales could not be given distinct dates")
            taken.add(when)
            number = numbers[position]
            net = D(50 * rng.randrange(16, 70))
            invoices.append(_Invoice(key=f"doc:{number.lower()}", number=number, customer=owner,
                                     issued=when, net=net, gross=gross_of(net, rate), raised_in_period=True,
                                     cost=D(10 * int(net * D("0.6") / 10))))
            position += 1
    return invoices


def _carried_of(invoices: list, customer: int) -> list:
    return sorted([i for i in invoices if i.customer == customer and not i.raised_in_period],
                  key=lambda i: (i.issued, i.number))


def _shape_the_target_customer(rng: random.Random, shape: FamilyShape, drawn: dict, invoices: list) -> None:
    """Give the target customer the balances its recipe needs, and part-pay
    one carried invoice before the period so that an invoice's FACE VALUE and
    the balance ENTERING the period are visibly different in every case.

    For the credit-residue recipe the second carried invoice is the ANCHOR
    the note names, and it is sized so that the note — bounded by that sale's
    OWN original net and tax — still has room above what the customer's open
    invoices absorb. The bound is the original sale, never the unpaid
    balance."""
    rate = drawn["rate"]
    rows = _carried_of(invoices, 0)
    if len(rows) < 3:
        raise ConstructionRefused("the target customer carries fewer than three invoices")
    withheld, anchor = rows[0], rows[1]
    if shape.mechanism == "credit_residue":
        withheld.net = D(50 * rng.randrange(12, 23))
        anchor.net = D(50 * rng.randrange(84, 130))
        rows[2].net = D(50 * rng.randrange(24, 50))
        for invoice in (withheld, anchor, rows[2]):
            invoice.gross = gross_of(invoice.net, rate)
        prior_net = D(50 * rng.randrange(30, 50))
    else:
        prior_net = D(50 * int(anchor.net / 150))
    if prior_net <= 0 or prior_net >= anchor.net:
        raise ConstructionRefused("the prior part payment does not sit strictly inside the anchor invoice")
    anchor.prior_payment = gross_of(prior_net, rate)


# --------------------------------------------------------------------------
# the three recipes
# --------------------------------------------------------------------------

def _advice_id(day: str, customer_name: str) -> str:
    initials = "".join(word[0] for word in customer_name.split()[:2]).upper()
    return f"RA-{day[5:7]}{day[8:10]}-{initials}"


def _payrun(customer_name: str, day: str) -> str:
    return f"{customer_name.split()[0].upper()} PAYRUN {day[5:7]}{day[8:10]}"


def _trace(drawn: dict, slot: int) -> str:
    return f"TRC{drawn['trace_base'] + slot * 37}"


def _settle_oldest(book: _Book, drawn: dict, customer: int, on: str, slot: int) -> _Receipt:
    """An ordinary adviced receipt: the customer pays its oldest open invoice
    in full and says so. Nothing in it is a mechanism; it is the month's
    normal traffic, and it is what keeps a register from being three rows
    long while every row still has to be reported."""
    rows = book.open_of(customer, on)
    if not rows:
        raise ConstructionRefused(f"customer {customer} has nothing open on {on}")
    invoice = rows[0]
    amount = book.open[invoice.key]
    book.take(invoice, amount)
    name = drawn["customers"][customer][1]
    return _Receipt(slot=slot, customer=customer, doc_date=on,
                    bank_date=_bank_after(drawn["period"], on, 2), amount=amount,
                    reference=_payrun(name, on), remittance_id=_advice_id(on, name),
                    lines=[_Line(invoice, amount, True, ZERO, "")])


def _dispute_and_settle(book: _Book, drawn: dict, customer: int, on: str, slot: int) -> _Receipt:
    """The receipt that defeats oldest-first in every recipe: the customer
    withholds its OLDEST invoice with a zero-cash statement of dispute,
    settles a later one in full and part-pays another. Three lines, two of
    them cash, so the advice contradicts both the oldest-first reading and
    any exact-subset reading that closes the oldest."""
    rows = book.open_of(customer, on)
    if len(rows) < 3:
        raise ConstructionRefused(f"customer {customer} has {len(rows)} open invoices on {on}; this receipt "
                                  f"needs three")
    withheld, settled, part = rows[0], rows[1], rows[2]
    settled_amount = book.open[settled.key]
    part_amount = D(50 * int(book.open[part.key] / 100))
    if not ZERO < part_amount < book.open[part.key]:
        raise ConstructionRefused("the part payment does not sit strictly inside its balance")
    book.take(settled, settled_amount)
    book.take(part, part_amount)
    name = drawn["customers"][customer][1]
    return _Receipt(slot=slot, customer=customer, doc_date=on,
                    bank_date=_bank_after(drawn["period"], on, 2),
                    amount=settled_amount + part_amount, reference=_payrun(name, on),
                    remittance_id=_advice_id(on, name),
                    lines=[_Line(withheld, ZERO, False, ZERO, "withheld; short shipment; credit requested"),
                           _Line(settled, settled_amount, True, ZERO, ""),
                           _Line(part, part_amount, False, ZERO,
                                 "part payment; balance to follow on the next payment run")])


def _reference_receipt(book: _Book, drawn: dict, customer: int, on: str, slot: int,
                       named: list, amount: D) -> _Receipt:
    """An un-adviced receipt. The bank prints its own trace ahead of the
    payer's invoice list, so the row carries a DECLARED payment identity and
    the invoice list stays what it is — document evidence naming which
    invoices the payment reaches. The lines are the application the published
    rungs reach on their own; gate (m) checks that they do."""
    printed = sorted(named, key=lambda i: (i.issued, i.number), reverse=True)
    reference = " ".join([_trace(drawn, slot)] + [i.number for i in printed])
    cash, lines = amount, []
    for invoice in sorted(named, key=lambda i: (i.issued, i.number)):
        if cash <= 0:
            break
        take = min(cash, book.open[invoice.key])
        if take > 0:
            book.take(invoice, take)
            lines.append(_Line(invoice, take, False, ZERO, ""))
            cash -= take
    if cash > 0:
        for invoice in book.open_of(customer, on):
            if cash <= 0:
                break
            take = min(cash, book.open[invoice.key])
            book.take(invoice, take)
            lines.append(_Line(invoice, take, False, ZERO, ""))
            cash -= take
    if cash > 0:
        raise ConstructionRefused("an un-adviced receipt would leave cash no open invoice absorbs; these "
                                  "recipes do not model an unapplied residue on a reference receipt")
    if len(lines) > BOUNDED_V1.max_allocations_per_receipt:
        raise ConstructionRefused(f"the receipt would carry {len(lines)} allocations")
    return _Receipt(slot=slot, customer=customer, doc_date=on, bank_date=on, amount=amount,
                    reference=reference, remittance_id="", lines=lines)


def _build_fallback(book: _Book, shape: FamilyShape, drawn: dict, positive: bool) -> tuple:
    """Fallback continuation. The target receipt's CASH is the declared fact:
    above what the referenced invoices are open for, the fold continues to
    rung (3) and reaches an invoice the reference never named; below it, the
    fold stops inside the last named invoice and rung (3) never runs."""
    period = drawn["period"]
    receipts = [_dispute_and_settle(book, drawn, 0, _in_month(period, 6), 0)]

    second = _in_month(period, 15)
    rows = book.open_of(1, second)
    if len(rows) < 4:
        raise ConstructionRefused(f"the second customer has {len(rows)} open invoices on {second}; its "
                                  f"reference receipt needs four")
    # Skip the second-oldest deliberately: the reference must not name the
    # oldest prefix, or the oldest-first reading would reproduce it.
    named = [rows[0], rows[2], rows[3]]
    short = D(50 * max(1, int(book.open[named[-1].key] / 150)))
    if short >= book.open[named[-1].key]:
        raise ConstructionRefused("the second receipt would close every invoice its reference names")
    receipts.append(_reference_receipt(book, drawn, 1, second, 1, named,
                                       sum((book.open[i.key] for i in named), ZERO) - short))

    note_day = _in_month(period, 18)
    note_rows = book.open_of(1, note_day)
    if not note_rows:
        raise ConstructionRefused("the second customer has nothing open for the credit note")
    note = _fit_note(book, drawn, 1, note_rows[0], note_day, CREDIT_REASONS[0])

    third = _in_month(period, 26)
    rows = book.open_of(0, third)
    if len(rows) < 3:
        raise ConstructionRefused(f"the paying customer has {len(rows)} open invoices on {third}; its target "
                                  f"receipt needs three")
    spare, named = rows[0], [rows[1], rows[2]]
    named_total = sum((book.open[i.key] for i in named), ZERO)
    step = D(50 * max(1, int(book.open[spare.key] / 200)))
    if positive:
        if step >= book.open[spare.key]:
            raise ConstructionRefused("the continuation would close the invoice the reference never names")
        amount = named_total + step
    else:
        if step >= book.open[named[-1].key]:
            raise ConstructionRefused("the shortfall would empty the last named invoice")
        amount = named_total - step
    receipts.append(_reference_receipt(book, drawn, 0, third, 2, named, amount))

    for slot in range(3, shape.receipts):
        customer = 1 + (slot - 3) % max(1, shape.customers - 1)
        receipts.append(_settle_oldest(book, drawn, customer, _in_month(period, 20 + slot), slot))
    return receipts, note, f"{amount:.2f}", "the target receipt's cash"


def _fit_note(book: _Book, drawn: dict, customer: int, invoice: _Invoice, on: str, reason: str) -> _Note:
    """A credit note that fits strictly inside the invoice it names — no
    excess, no residue. The recipes that do not turn on the credit mechanism
    use this, so the credit-ignored reading is still defeated (the note moves
    a register row) without a second mechanism entering the month."""
    rate = drawn["rate"]
    net = D(50 * max(1, int(book.open[invoice.key] / (1 + rate) / 100)))
    gross = gross_of(net, rate)
    if gross >= book.open[invoice.key] or net > invoice.net:
        raise ConstructionRefused("the credit note does not fit strictly inside the invoice it names")
    book.take(invoice, gross)
    return _Note(number=f"CN-{drawn['note_number']}", customer=customer, invoice=invoice, date=on,
                 net=net, memo=reason)


def _build_credit_residue(book: _Book, shape: FamilyShape, drawn: dict, positive: bool) -> tuple:
    """Credit residue. The note's NET is the declared fact: at the net its
    customer's open invoices absorb exactly, nothing is left over; one step
    above it the excess reaches no open invoice of that customer and is held
    as that customer's unapplied credit inside the control account."""
    rate, period = drawn["rate"], drawn["period"]
    first = _in_month(period, 7)
    rows = book.open_of(0, first)
    if len(rows) < 3:
        raise ConstructionRefused("the credit customer needs three open invoices before the note")
    withheld, anchor, settled = rows[0], rows[1], rows[2]
    if anchor.prior_payment <= 0:
        raise ConstructionRefused("the anchor invoice was not part-paid before the period, so the note has no "
                                  "room under its original sale")
    open_net = (book.open[anchor.key] / (1 + rate)).quantize(D("0.01"))
    if gross_of(open_net, rate) != book.open[anchor.key]:
        raise ConstructionRefused("the anchor's open balance does not split exactly at the world's rate")
    part_net = D(50 * int(open_net / 100))
    part = gross_of(part_net, rate)
    if not ZERO < part < book.open[anchor.key]:
        raise ConstructionRefused("the anchor part payment does not sit strictly inside its balance")
    settled_amount = book.open[settled.key]
    book.take(settled, settled_amount)
    book.take(anchor, part)
    name = drawn["customers"][0][1]
    receipts = [_Receipt(slot=0, customer=0, doc_date=first,
                         bank_date=_bank_after(period, first, 2), amount=settled_amount + part,
                         reference=_payrun(name, first), remittance_id=_advice_id(first, name),
                         lines=[_Line(withheld, ZERO, False, ZERO,
                                      "withheld; allowance requested for the disputed units"),
                                _Line(settled, settled_amount, True, ZERO, ""),
                                _Line(anchor, part, False, ZERO,
                                      "part payment; balance held pending the agreed allowance")])]

    note_day = _in_month(period, 17)
    open_now = book.open_of(0, note_day)
    if {i.key for i in open_now} != {withheld.key, anchor.key}:
        raise ConstructionRefused("the credit customer's open set on the note's date is not the anchor and the "
                                  "one invoice its excess is meant to reach")
    base_net = sum(((book.open[i.key] / (1 + rate)).quantize(D("0.01")) for i in open_now), ZERO)
    if gross_of(base_net, rate) != sum((book.open[i.key] for i in open_now), ZERO):
        raise ConstructionRefused("the absorbing balances do not split exactly at the world's rate")
    # A twentieth of what the open invoices absorb, rounded to the 50 every
    # net in this world is a multiple of: large enough to be a residue a
    # reader must place, small enough to stay under the anchor's own sale.
    step = D(50 * max(1, int(base_net / 1000)))
    note_net = base_net + step if positive else base_net
    if note_net > anchor.net:
        raise ConstructionRefused("the note would reverse more sales value than its invoice's original sale")
    remaining = gross_of(note_net, rate)
    for invoice in open_now:
        take = min(remaining, book.open[invoice.key])
        book.take(invoice, take)
        remaining -= take
    note = _Note(number=f"CN-{drawn['note_number']}", customer=0, invoice=anchor, date=note_day,
                 net=note_net, memo=CREDIT_REASONS[1])

    receipts_out = list(receipts)
    for slot in range(1, shape.receipts):
        customer = 1 + (slot - 1) % max(1, shape.customers - 1)
        receipts_out.append(_settle_oldest(book, drawn, customer, _in_month(period, 8 + 3 * slot), slot))
    return receipts_out, note, f"{note_net:.2f}", "the credit note's net"


def _build_advice_residue(book: _Book, shape: FamilyShape, drawn: dict, positive: bool) -> tuple:
    """Advice residue. One advice cell is the declared fact: the line either
    leaves part of the payment unnamed — which rung (1) leaves unapplied
    rather than carrying on to the rules below, while the payer still has an
    invoice open that rung (3) would have reached — or names the whole of it."""
    period, salt = drawn["period"], drawn["salt"]
    first = _in_month(period, 5)
    if len(book.open_of(0, first)) < 4:
        raise ConstructionRefused("the target customer needs four open invoices at the opening receipt")
    # The opening receipt part-pays the invoice the TARGET receipt later
    # closes, so that invoice is settled across two evidenced events: the
    # dependency has an accounting reason and a witness in both advices.
    receipts = [_dispute_and_settle(book, drawn, 0, first, 0)]

    # A deduction ABOVE the tolerance: nothing is written off and the invoice
    # stays open for it. With the one below the tolerance at the target
    # receipt, neither write-off-everything nor write-off-nothing reproduces
    # the month.
    second = _in_month(period, 12)
    rows = book.open_of(1, second)
    if not rows:
        raise ConstructionRefused("the second customer has nothing open for the large deduction")
    big = rows[0]
    big_deduction = D(10 * (6 + salt % 5))
    if big_deduction <= CA.SHORT_PAY_TOLERANCE or big_deduction >= book.open[big.key]:
        raise ConstructionRefused("the large deduction is not strictly above the tolerance and inside the balance")
    big_cash = book.open[big.key] - big_deduction
    book.take(big, big_cash)
    name_two = drawn["customers"][1][1]
    receipts.append(_Receipt(slot=1, customer=1, doc_date=second, bank_date=_bank_after(period, second, 3),
                             amount=big_cash, reference=_payrun(name_two, second),
                             remittance_id=_advice_id(second, name_two),
                             lines=[_Line(big, big_cash, True, big_deduction,
                                          "freight overcharge; credit requested")]))

    note_day = _in_month(period, 16)
    note_rows = [i for i in book.open_of(1, note_day) if i.key != big.key]
    if not note_rows:
        raise ConstructionRefused("the second customer has nothing left for the credit note")
    note = _fit_note(book, drawn, 1, note_rows[0], note_day, CREDIT_REASONS[2])

    target_slot = shape.receipts - 1
    for slot in range(2, target_slot):
        customer = 1 + (slot - 2) % max(1, shape.customers - 1)
        receipts.append(_settle_oldest(book, drawn, customer, _in_month(period, 14 + 2 * slot), slot))

    target_day = _in_month(period, 27)
    rows = book.open_of(0, target_day)
    if len(rows) < 3:
        raise ConstructionRefused("the target customer needs three open invoices at the target receipt")
    _kept, closing, part = rows[0], rows[1], rows[2]
    small_deduction = D(5 * (1 + (salt // 7) % 4))
    if not ZERO < small_deduction < CA.SHORT_PAY_TOLERANCE:
        raise ConstructionRefused("the small deduction is not strictly inside the tolerance")
    if small_deduction >= book.open[closing.key]:
        raise ConstructionRefused("the small deduction does not sit inside its invoice's balance")
    closing_cash = book.open[closing.key] - small_deduction
    part_base = D(50 * max(1, int(book.open[part.key] / 200)))
    residue = D(10 * (3 + salt % 7))
    if part_base + residue >= book.open[part.key]:
        raise ConstructionRefused("the target line plus its residue would exceed the invoice's open balance")
    line_amount = part_base if positive else part_base + residue
    total = closing_cash + part_base + residue
    book.take(closing, book.open[closing.key])
    book.take(part, line_amount)
    name_target = drawn["customers"][0][1]
    receipts.append(_Receipt(slot=target_slot, customer=0, doc_date=target_day,
                             bank_date=_bank_after(period, target_day, 1), amount=total,
                             reference=_payrun(name_target, target_day),
                             remittance_id=_advice_id(target_day, name_target),
                             lines=[_Line(closing, closing_cash, True, small_deduction,
                                          "minor remittance discrepancy; invoice treated as settled"),
                                    _Line(part, line_amount, False, ZERO,
                                          "part payment against the balance on account")]))
    receipts.sort(key=lambda r: r.slot)
    return receipts, note, f"{line_amount:.2f}", "the target advice line's cash"


_RECIPES = {
    "fallback_continuation": _build_fallback,
    "credit_residue": _build_credit_residue,
    "advice_residue": _build_advice_residue,
}


# --------------------------------------------------------------------------
# from a layout to a World
# --------------------------------------------------------------------------

def _chart(drawn: dict) -> tuple:
    company = drawn["company"]
    opened = f"{int(drawn['period'].start[:4]) - 1:04d}-01-01"
    return (
        Account(BANK_ACCOUNT, K.ASSET, f"Primary operating checking account held at {company[2]}", opened, 1000),
        Account(AR, K.ASSET, "Trade receivables from customers", opened, 1100),
        Account(INVENTORY, K.ASSET, "Finished goods and stock materials held for sale", opened, 1200),
        Account(PREPAYMENTS, K.ASSET, "Amounts paid in advance of the period they relate to", opened, 1300),
        Account(PAYABLES, K.LIABILITY, "Trade payables to suppliers", opened, 2000),
        Account(SALES_TAX, K.LIABILITY, "Sales tax collected from customers and owed to the state", opened, 2100),
        Account(SALES, K.INCOME, f"Revenue from goods supplied by {company[1]}", opened, 4100),
        Account(COGS, K.EXPENSE, "Cost of goods sold", opened, 5000),
        Account(BANK_FEES, K.EXPENSE, "Bank service charges and transaction fees", opened, 5300),
        Account(WRITE_OFFS, K.EXPENSE,
                "Short payments within the cash application tolerance written off on receipt", opened, 5400),
        Account(OPENING_EQUITY, K.EQUITY, "Opening balance equity", opened, 9000),
    )


ROLES = (("receivables", AR), ("inventory", INVENTORY), ("prepayments", PREPAYMENTS),
         ("payables", PAYABLES), ("sales_tax", SALES_TAX), ("sales", SALES), ("cogs", COGS),
         ("bank_fees", BANK_FEES), ("opening_equity", OPENING_EQUITY),
         ("small_balance_write_offs", WRITE_OFFS))


def _policy_text(drawn: dict, shape: FamilyShape) -> str:
    rate = (drawn["rate"] * 100).quantize(D("1")) if (drawn["rate"] * 100) % 1 == 0 else drawn["rate"] * 100
    return V.policy_text(drawn["company"][0], drawn["company"][1], f"{rate:f}".rstrip("0").rstrip("."),
                         numbering=V.NUMBERING_SECTION if shape.scrambled_numbering else "")


def _world_of(layout: _Layout, world_id: str) -> World:
    shape, drawn = layout.shape, layout.drawn
    period, prior, rate = drawn["period"], drawn["prior"], drawn["rate"]
    company = drawn["company"]
    parties = tuple(Party(pid, name, R.CUSTOMER, index + 1, terms, AR)
                    for index, (pid, name, terms) in enumerate(drawn["customers"]))
    vendor_id, vendor_name = drawn["vendor"]
    parties += (Party(vendor_id, vendor_name, R.VENDOR, shape.customers + 1, "net 30", INVENTORY),
                Party("party:bank", company[2], R.BANK, shape.customers + 2))

    prior_start = _date.fromisoformat(prior.start)
    pi_one_issued = _iso(_business_after(prior_start - timedelta(days=40)))
    pi_two_issued = _iso(_business_after(prior_start - timedelta(days=12)))
    pi_one = gross_of(drawn["purchase_nets"][0], D("0"))
    pi_two = gross_of(drawn["purchase_nets"][1], D("0"))
    documents = tuple(Document(i.key, DK.SALES_INVOICE, i.number, drawn["customers"][i.customer][0],
                               i.issued, i.gross) for i in layout.invoices)
    documents += (Document("doc:pi-1", DK.PURCHASE_INVOICE, "PI-8001", vendor_id, pi_one_issued, pi_one),
                  Document("doc:pi-2", DK.PURCHASE_INVOICE, "PI-8002", vendor_id, pi_two_issued, pi_two))

    def ach_in(on):
        return Settlement(Rail.ACH_IN, on)

    def ach_out(on):
        return Settlement(Rail.ACH_OUT, on)

    prior_events = []
    for invoice in layout.invoices:
        if invoice.prior_payment > 0:
            when = _iso(_business_after(prior_start + timedelta(days=9)))
            prior_events.append(CustomerReceipt(
                f"event:prior-receipt-{invoice.number.lower()}", when,
                drawn["customers"][invoice.customer][0], invoice.key, invoice.prior_payment,
                ach_in(when), f"Part payment against {invoice.number}"))
    pay_one = _iso(_business_after(prior_start + timedelta(days=4)))
    prior_events.append(VendorPayment("event:pi-1-payment", pay_one, vendor_id, "doc:pi-1", pi_one,
                                      ach_out(pay_one), "Payment of purchase invoice PI-8001"))
    prior_events.append(BankFee("event:fee-prior", prior.end, drawn["fee"], "Monthly account service charge"))

    pay_two = _in_month(period, 4)
    events = [VendorPayment("event:pi-2-payment", pay_two, vendor_id, "doc:pi-2", pi_two,
                            ach_out(pay_two), "Payment of purchase invoice PI-8002")]
    for invoice in layout.invoices:
        if invoice.raised_in_period:
            events.append(Sale(f"event:sale-{invoice.number.lower()}", invoice.issued,
                               drawn["customers"][invoice.customer][0], invoice.key, invoice.net, rate,
                               invoice.cost, f"Sale {invoice.number}",
                               f"Cost of goods sold on {invoice.number}"))
    note = layout.note
    events.append(CreditNote(note.key, note.date, drawn["customers"][note.customer][0], note.invoice.key,
                             note.number, note.net, rate, note.memo))
    for receipt in layout.receipts:
        events.append(AppliedReceipt(
            receipt.key, receipt.doc_date, drawn["customers"][receipt.customer][0], receipt.amount,
            ach_in(receipt.bank_date), receipt.memo, receipt.reference,
            tuple(ReceiptLine(line.invoice.key, line.amount, line.settles, line.deduction, line.note)
                  for line in receipt.lines),
            receipt.remittance_id))
    events.append(BankFee("event:fee-period", period.end, drawn["fee"], "Monthly account service charge"))

    opening_ar = sum((i.basis for i in layout.invoices if not i.raised_in_period), ZERO)
    opening_inventory = (sum((i.cost for i in layout.invoices), ZERO) + pi_one + pi_two) * 3
    opening = OpeningPosition(period.start, ((AR, opening_ar), (INVENTORY, opening_inventory),
                                             (PAYABLES, -pi_two)))
    return World(id=world_id, title=f"{company[0]} - FY{period.start[:4]}", currency=CURRENCY,
                 bank_account=BANK_ACCOUNT, bank_party_id="party:bank", accounts=_chart(drawn),
                 parties=parties, documents=documents,
                 bank_opening=BankOpening(prior.start, drawn["bank_opening"]),
                 opening=opening, events=tuple(prior_events + events), roles=ROLES,
                 policy_text=_policy_text(drawn, shape))


# --------------------------------------------------------------------------
# the plants
# --------------------------------------------------------------------------

def _alter_parameter(amount: D, forbidden: set) -> int:
    """The transposition position whose as-found amount coincides with no
    balance and no face value in the month. A coincidence would make the
    wrong figure readable as a legitimate one."""
    cents = int((amount * 100).to_integral_value())
    digits = list(str(cents))
    for position in range(len(digits) - 1):
        swapped = digits[:]
        swapped[position], swapped[position + 1] = swapped[position + 1], swapped[position]
        wrong = int("".join(swapped))
        if wrong in (0, cents):
            continue
        if D(wrong) / 100 in forbidden:
            continue
        return position
    raise ConstructionRefused("no transposition of the altered receipt avoids a figure the month already carries")


def _plan_of(layout: _Layout, world: World) -> MutationPlan:
    shape, drawn = layout.shape, layout.drawn
    by_slot = {r.slot: r for r in layout.receipts}
    forbidden = {i.gross for i in layout.invoices} | {i.basis for i in layout.invoices} \
        | {r.amount for r in layout.receipts}
    mutations = []
    for kind, slot in shape.plants:
        receipt = by_slot.get(slot)
        if receipt is None:
            raise ConstructionDefect(f"{shape.family}: a plant names receipt slot {slot}, which the recipe "
                                     f"did not build")
        if any(line.deduction > 0 and line.settles and line.deduction <= CA.SHORT_PAY_TOLERANCE
               for line in receipt.lines):
            raise ConstructionDefect(f"{shape.family}: slot {slot} carries a write-off, so a plant on it would "
                                     f"put two planted items on one economic event")
        recognition = f"rec:{receipt.key.split(':', 1)[1]}"
        name = drawn["customers"][receipt.customer][1]
        row = (f"the statement row ACH IN {name.upper()} of {receipt.bank_date} names the remitter and prints "
               f"{receipt.reference} in its reference column; customers.csv maps the customer to {AR}")
        if kind == "omit":
            mutations.append(OmitRecognition(
                f"unrecorded_customer_receipt_{slot}", recognition,
                f"{row}; the dates section posts an entry the books lack on the date the bank shows"))
        elif kind == "alter":
            parameter = _alter_parameter(receipt.amount, forbidden - {receipt.amount})
            mutations.append(AlterRecognition(
                f"transposed_customer_receipt_{slot}", recognition, "transpose_digits", parameter,
                f"{row}; the ledger carries the same receipt at a transposed amount and the entry is re-posted "
                f"at the statement's figure"))
        elif kind == "duplicate":
            mutations.append(DuplicateRecognition(
                f"duplicated_customer_receipt_{slot}", recognition,
                f"{row} once, while the ledger carries the entry twice; the repair removes one copy"))
        else:
            raise ConstructionDefect(f"unknown plant kind {kind!r}")
    return MutationPlan(tuple(mutations))


# --------------------------------------------------------------------------
# rendering one variant
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Variant:
    """One rendered member of a pair: everything decision 4 requires the
    construction to produce for it."""

    variant: str
    world: World
    task: TaskSpec
    inputs: object                    # ContractInputs, with its ApplicationInputs truth register
    public_files: dict                # the eleven, name -> text
    golden_ledger: str
    golden_register: str
    measurement: PROFILE.Measurement

    @property
    def truth(self):
        return self.inputs.application


@dataclass(frozen=True)
class CandidatePair:
    identity: ConstructionIdentity
    family: str
    mechanism: str
    attempt: int
    declared_fact: DeclaredFact
    variants: dict                    # variant -> Variant
    template: StructuralTemplate
    census: tuple                     # every attempt's ordinal and outcome

    def variant(self, name: str) -> Variant:
        return self.variants[name]


def identity_of(population: str, family: str, company_month_index: int,
                profile: GenerationProfile = BOUNDED_V1) -> ConstructionIdentity:
    """A construction identity for one company-month of one family, with its
    split READ FROM the frozen map.

    `cash_split.identity_for` does the same from a `StructuralTemplate`, which
    only exists once an instance has been rendered; this is the door the
    construction path itself walks through, and it takes the family NAME,
    which is what the map keys on. There is no argument here that could
    disagree with the map, and a family the map does not carry cannot produce
    an identity at all."""
    shape = shape_of(family)
    if SPLIT_MAP.mechanism_of(family) != shape.mechanism:
        raise ConstructionDefect(f"{family} is sealed under {SPLIT_MAP.mechanism_of(family)!r} and its shape "
                                 f"declares {shape.mechanism!r}")
    return identity(population=population, split=SPLIT_MAP.split_of(family), template_family=family,
                    template_version=TEMPLATE_VERSION, company_month_index=company_month_index,
                    profile=profile)


def public_stem(seed: int) -> str:
    """The twelve digits a pair's public names are built from.

    KEYED, through a substream of the parent seed, and deliberately not the
    identity's own digest. That digest carries no secret, but it is an
    unkeyed function of an ENUMERABLE selector — population, family, version,
    company-month index, profile — so printing it on a task id would hand an
    agent an equality oracle over the selector space, which is the attack the
    keyed seed exists to defeat. This stem is a one-way function of the seed
    under its own substream domain: it identifies the pair without naming
    anything the identity is made of, and it does not lead back to the seed.
    """
    return f"{stream(seed, 'public-name') % 10 ** 12:012d}"


def _public_id(stem: str, variant: str) -> str:
    """The task id an episode carries. Never the population, the template
    family, the company-month index or the seed, none of which may reach an
    agent surface."""
    return f"cash_application_g{stem}{variant}"


def _render(stem: str, shape: FamilyShape, drawn: dict, invoices: list,
            variant: str, positive: bool, profile: GenerationProfile) -> tuple:
    """One variant, from the shared draw and a single polarity flag."""
    fresh = [
        _Invoice(key=i.key, number=i.number, customer=i.customer, issued=i.issued, net=i.net,
                 gross=i.gross, raised_in_period=i.raised_in_period, prior_payment=i.prior_payment,
                 cost=i.cost)
        for i in invoices
    ]
    book = _Book(fresh)
    receipts, note, value, fact_name = _RECIPES[shape.mechanism](book, shape, drawn, positive)
    layout = _Layout(shape=shape, drawn=drawn, invoices=fresh, receipts=receipts, note=note,
                     declared_name=fact_name, declared_value=value, book=book)
    world = _world_of(layout, f"cash-application-{stem}-{variant}")
    task = TaskSpec(id=_public_id(stem, variant), type="bank_reconciliation",
                    prompt=V.prompt(drawn["period"].label.split()[0]), period=drawn["period"],
                    plan=_plan_of(layout, world))
    try:
        _bundle, inputs = derive_contract(world, task)
    except (DerivationError, ProjectionError, TypeError, ValueError) as exc:
        # Decision 3 draws the line here: an authoring slip the projector or
        # the derivation refuses is an EXPECTED construction failure and the
        # next attempt may be drawn. A disagreement between two supposedly
        # independent derivations is a defect to investigate, and drawing
        # again until it disappears is exactly what must not happen.
        if "oracle disagreement" in str(exc):
            raise ConstructionDefect(f"{shape.family}/{variant}: the projector, the boundary and the "
                                     f"independent fold disagree: {exc}") from exc
        raise ConstructionRefused(f"{shape.family}/{variant}: {type(exc).__name__}: {exc}") from exc
    public = {name: data.decode("utf-8") for name, data in inputs.public_files}
    if len(public) != 11:
        raise ConstructionDefect(f"{task.id}: the projection emitted {len(public)} public files, not eleven")
    try:
        application = CA.fold(public, bank_account=world.bank_account,
                              period_start=task.period.start, period_end=task.period.end)
    except CA.Refusal as exc:
        raise ConstructionRefused(f"{shape.family}/{variant}: the public fold refuses: {exc}") from exc
    if CA.application_key(application) != inputs.application.application_key():
        raise ConstructionDefect(f"{task.id}: the public fold and the private truth disagree; two supposedly "
                                 f"independent derivations must not")
    golden_register = CA.document_text(application)
    measurement = PROFILE.measure(world, task, inputs)
    problems = PROFILE.bound_problems(measurement, profile)
    problems += PROFILE.excluded_accounting_problems(world, profile)
    problems += PROFILE.difficulty_problems(world, task, inputs, profile)
    if problems:
        raise ConstructionRefused(f"{shape.family}/{variant}: " + "; ".join(problems))
    return Variant(variant=variant, world=world, task=task, inputs=inputs, public_files=public,
                   golden_ledger=inputs.golden_text, golden_register=golden_register,
                   measurement=measurement), layout


# --------------------------------------------------------------------------
# the structural template
# --------------------------------------------------------------------------

def template_of(family: str, layout: _Layout, variant: Variant) -> StructuralTemplate:
    """The canonical structural description of what was drawn, in the shape
    `cash_split` digests. Built from the RENDERED variant, so the description
    is of the world that exists rather than of the recipe's intention."""
    truth = variant.truth
    opening = {row[0]: row for row in truth.opening_register}
    invoices = []
    for invoice_id, customer, invoice_date, basis, source in truth.invoices:
        row = opening.get(invoice_id)
        invoices.append(InvoiceShape(
            invoice_id=invoice_id, customer=customer, invoice_date=invoice_date,
            due_date=row[3] if row else invoice_date,
            original_amount=f"{(row[4] if row else basis):.2f}", open_balance=f"{basis:.2f}",
            raised_in_period=source == "sale"))
    advices = {e.remittance_id: e for e in variant.world.events
               if isinstance(e, AppliedReceipt) and e.remittance_id}
    numbers = {d.id: d.number for d in variant.world.documents}
    receipts = []
    for receipt_id, when, customer, amount, _applied, _written, _unapplied, remittance_id, *_rest in truth.receipts:
        event = advices.get(remittance_id)
        lines = tuple(AdviceLineShape(numbers[line.invoice_id], f"{line.amount:.2f}", line.settles,
                                      f"{line.deduction:.2f}")
                      for line in (event.lines if event is not None else ()))
        reference = receipt_id.split(":", 1)[1]
        named = tuple(token for token in reference.split() if token.startswith("SI-"))
        receipts.append(ReceiptShape(receipt_id=receipt_id, customer=customer, bank_date=when,
                                     amount=f"{amount:.2f}",
                                     evidence="advice" if event is not None else "reference",
                                     references=named, advice_lines=lines))
    named_by_note = {e.number: numbers[e.invoice_id] for e in variant.world.events
                     if isinstance(e, CreditNote)}
    notes = tuple(CreditNoteShape(credit_note_id=c[0], customer=c[2], date=c[1],
                                  invoice_id=named_by_note[c[0]], gross_amount=f"{c[3]:.2f}")
                  for c in truth.credit_notes)
    # A plant is described by WHAT it sits on, in the same vocabulary the rest
    # of the structure uses: the receipt, not the recognition id, which is a
    # name of the projector's and would make the description depend on it.
    receipt_of_recognition = {row[9]: row[0] for row in truth.receipts}
    plants = tuple(PlantShape(kind=p.kind, target=receipt_of_recognition[p.recognition_id])
                   for p in variant.inputs.planted)
    return StructuralTemplate(family=family, version=TEMPLATE_VERSION,
                              mechanism=SHAPE_BY_FAMILY[family].mechanism,
                              invoices=tuple(invoices), receipts=tuple(receipts),
                              credit_notes=notes, plants=plants)


# --------------------------------------------------------------------------
# the bounded attempt loop
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class AttemptRecord:
    """Decision 3: every attempt's ordinal, stage and rejection reason is
    retained. The preflight adds the gate results; the construction retains
    what IT saw, and an exhausted group is a NAMED failure rather than a
    silent advance to a replacement selector."""

    ordinal: int
    stage: str                        # draw | render | pair
    outcome: str                      # accepted | refused
    reason: str = ""


def construct(ident: ConstructionIdentity, attempt: int,
              profile: GenerationProfile = BOUNDED_V1, secret: bytes | None = None) -> tuple:
    """One bounded layout attempt: the drawn universe rendered into both
    variants, each satisfying the profile on its own and the two together
    satisfying the pair's contract."""
    if type(attempt) is not int or not 0 <= attempt < MAX_LAYOUT_ATTEMPTS:
        raise ConstructionRefused(f"attempt is an int in [0, {MAX_LAYOUT_ATTEMPTS})")
    if ident.profile_digest != profile.digest():
        raise ConstructionRefused("the identity was minted under another profile; the profile digest is part "
                                  "of the construction identity and may not be swapped at render time")
    shape = shape_of(ident.template_family)
    if not profile.invoices[0] <= shape.invoices <= profile.invoices[1]:
        raise ConstructionDefect(f"{shape.family} declares {shape.invoices} invoices, outside bounded-v1")
    seed = parent_seed(ident, secret)
    stem = public_stem(seed)
    rng = random.Random(layout_attempt_stream(seed, attempt))
    drawn = _draw_common(rng, shape)
    invoices = _invoice_universe(rng, shape, drawn)
    _shape_the_target_customer(rng, shape, drawn, invoices)

    rendered, layouts = {}, {}
    for variant, positive in zip(VARIANTS, (True, False)):
        rendered[variant], layouts[variant] = _render(stem, shape, drawn, invoices, variant, positive,
                                                      profile)

    names = {layouts[variant].declared_name for variant in VARIANTS}
    if len(names) != 1:
        raise ConstructionDefect(f"{shape.family}: the two variants declare different facts {sorted(names)}; a "
                                 f"pair differs in ONE authored fact, and which one it is cannot depend on the "
                                 f"polarity")
    fact = DeclaredFact(name=names.pop(),
                        values={variant: layouts[variant].declared_value for variant in VARIANTS})
    problems = _pair_problems(shape, rendered, fact, profile)
    if problems:
        raise ConstructionRefused(f"{shape.family}: " + "; ".join(problems))
    template = template_of(shape.family, layouts["a"], rendered["a"])
    return rendered, fact, template


def _pair_problems(shape: FamilyShape, rendered: dict, fact: DeclaredFact,
                   profile: GenerationProfile) -> list:
    """The pair's own contract: one declared fact differs, every consequence
    is derived, both polarities are present, and the intended accounting
    distinction really changes."""
    problems = []
    if not fact.differs():
        problems.append(f"the declared fact {fact.name} reads {fact.values} in the two variants; a pair must "
                        f"differ in exactly one declared authored fact")
    a, b = rendered["a"], rendered["b"]
    if a.truth.application_key() == b.truth.application_key():
        problems.append("the two variants fold to the same register; the intended accounting distinction does "
                        "not change")
    moved = {name for name in a.public_files if a.public_files[name] != b.public_files[name]}
    if not moved:
        problems.append("the two variants render the same public bytes")
    allowed = MECHANISM_CONSEQUENCES[shape.mechanism]
    if not moved <= allowed:
        problems.append(f"the variants differ in {sorted(moved - allowed)}, which the declared fact does not "
                        f"reach; they are two company-months rather than two variants of one")
    problems += PROFILE.polarity_problems(shape.mechanism,
                                          {v: rendered[v].measurement for v in VARIANTS}, profile)
    return problems


def candidate_pair(ident: ConstructionIdentity, profile: GenerationProfile = BOUNDED_V1,
                   secret: bytes | None = None) -> CandidatePair:
    """Draw a parent group: up to `MAX_LAYOUT_ATTEMPTS` deterministic layout
    attempts, both variants rejected whenever either fails an acceptance
    condition, and exhaustion raising a NAMED failed group rather than
    advancing to a replacement selector."""
    census = []
    for attempt in range(MAX_LAYOUT_ATTEMPTS):
        try:
            rendered, fact, template = construct(ident, attempt, profile, secret)
        except ConstructionRefused as exc:
            census.append(AttemptRecord(attempt, "render", "refused", str(exc)))
            continue
        census.append(AttemptRecord(attempt, "pair", "accepted"))
        return CandidatePair(identity=ident, family=ident.template_family,
                             mechanism=shape_of(ident.template_family).mechanism, attempt=attempt,
                             declared_fact=fact, variants=rendered, template=template,
                             census=tuple(census))
    raise ConstructionRefused(
        f"group {ident.label()} is EXHAUSTED after {MAX_LAYOUT_ATTEMPTS} attempts; it is a named failed group "
        f"and no replacement selector is drawn. Reasons: "
        + "; ".join(sorted({record.reason for record in census})[:4]))


__all__ = [
    "CONSTRUCTION_VERSION", "TEMPLATE_VERSION", "ConstructionRefused", "ConstructionDefect",
    "FamilyShape", "SHAPES", "SHAPE_BY_FAMILY", "shape_of",
    "COMPANIES", "CUSTOMER_NAMES", "VENDOR_NAMES", "TAX_RATES", "gross_of",
    "MECHANISM_CONSEQUENCES", "DeclaredFact", "Variant", "CandidatePair", "AttemptRecord",
    "construct", "candidate_pair", "template_of", "identity_of", "public_stem",
]
