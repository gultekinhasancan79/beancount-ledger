"""The seeded generator: one integer in, one world and one task out.

    generate(seed) -> (World, TaskSpec)

Everything downstream — public files, planted predicates, targets, digests —
is the projection of what this module draws, exactly as it is for the
hand-authored world. The generator therefore authors *facts only*: parties,
documents, amounts, dates, rails and clearing dates, plus which derived
recognitions the task plants a difference on. It never writes a posting
vector, a balance or a target.

**Determinism.** Every draw comes from `random.Random(mint.sub_seed(seed, purpose))`
— a SHA-256 domain-separated integer per purpose.
The substreams are keyed by purpose — parties, documents, events, amounts,
timing, wording, plan — so that adding a purpose later changes only what
that purpose draws and leaves every other stream where it was. Nothing
reads a clock, a set iteration order or a dict order; pools are tuples and
candidate lists are sorted before they are sampled. `generate(seed)` twice
returns equal dataclasses and therefore identical digests.

**The seed is provenance, not content.** It never names the task (the public
id is derived from the public bytes by `mint`)
and nothing else: no id, name, memo or amount in the World is a function of
the seed value except through the facts the substreams drew.

**Identifiability by construction.** Every amount that reaches a bank
statement row — this period's or the archive's — is drawn distinct from
every other, so a planted difference can always be pinned to exactly one
public row by its amount alone. The one deliberate exception is the rent,
which is the same figure every month because rent is; the plan therefore
never plants on an amount that appears twice, and it checks that rather
than assuming it.

The audits that decide whether a world is *valid* live in `check_world`,
`check_bundle` and `derive_contract`. This module does not re-implement
them; it constructs worlds that pass them, and `check_world` is asserted
here only so a construction defect fails at the generator rather than three
layers downstream.
"""

from __future__ import annotations

import calendar
import random
import re
from collections import Counter
from dataclasses import dataclass, replace
from itertools import combinations
from datetime import date, timedelta
from decimal import Decimal as D

from . import content as C
from .derive import TaskSpec
from .policy import Roles, movement_of, recognitions_of
from .project import (
    AlterRecognition,
    DuplicateRecognition,
    MutationPlan,
    OmitRecognition,
    Period,
    derive_mutant,
    prior_period,
)
from .schema import (
    Account,
    AccountKind as K,
    BankFee,
    BankOpening,
    CustomerReceipt,
    Document,
    DocumentKind as DK,
    ExpensePayment,
    OpeningPosition,
    Party,
    PartyRole as R,
    Prepayment,
    Purchase,
    Rail,
    Sale,
    Settlement,
    VendorPayment,
    World,
    check_world,
)

from .mint import GENERATOR_VERSION   # one source: the version enters every substream seed

CENT = D("0.01")
OPENED = "2025-01-01"
YEAR = 2025
FIRST_MONTH, LAST_MONTH = 2, 11        # the task period is a full calendar month in this range


class GenerationError(Exception):
    """A seed the generator could not build a valid world for. Ours."""


# --------------------------------------------------------------------------
# the profile
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Profile:
    """The shape of the worlds a run draws, as inclusive ranges.

    `statement_rows` counts the rows of the task period's statement
    INCLUDING the opening-balance row, which is what the manifest reports
    and what a reader counts.
    """

    statement_rows: tuple = (26, 30)
    customers: tuple = (3, 4)
    vendors: tuple = (4, 5)                 # rent, office and 2–3 inventory vendors; with the bank: 8–10 counterparties
    planted: tuple = (5, 6)
    kinds: tuple = ("omit", "alter", "duplicate")
    max_per_kind: tuple = (("alter", 2), ("duplicate", 2))   # the hard profile lifts both to 3
    min_rules: int = 3                      # the planted items span at least this many rules, so with the bank
                                            # they move at least min_rules + 1 target accounts (version 9)
    prior_rows: tuple = (5, 8)
    tax_rates: tuple = (D("0.08"), D("0.10"), D("0.20"))
    name: str = "standard-v1"


DEFAULT_PROFILE = Profile()
HARD_PROFILE = Profile(statement_rows=(28, 30), vendors=(5, 5), planted=(6, 8),
                       max_per_kind=(("alter", 3), ("duplicate", 3)), name="hard-v1")


# --------------------------------------------------------------------------
# substreams and small draws
# --------------------------------------------------------------------------

def _days(a: str, b: str) -> int:
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def _rng(seed: int, purpose: str) -> random.Random:
    """One stream per purpose, seeded by a SHA-256 domain-separated integer
    over (generator version, private seed, purpose) — never Python's salted
    `hash()` and never the raw seed string — so a new purpose does not
    reshuffle the existing ones and the draw is identical across processes
    and PYTHONHASHSEED values."""
    from .mint import sub_seed
    return random.Random(sub_seed(seed, purpose))


def _weighted(rng: random.Random, options):
    """Integer-weighted choice: no float accumulation, same answer anywhere."""
    total = sum(w for _, w in options)
    draw = rng.randrange(total)
    for value, weight in options:
        if draw < weight:
            return value
        draw -= weight
    return options[-1][0]


def _cents(rng: random.Random, low: int, high: int) -> D:
    """A money amount in [low, high] with cents, drawn in integer cents."""
    return (D(rng.randint(low * 100, high * 100)) / 100).quantize(CENT)


def _bucketed(rng: random.Random, buckets) -> D:
    """Log-normal-ish: a weighted band, then uniform cents inside it."""
    low, high = _weighted(rng, tuple((b[:2], b[2]) for b in buckets))
    return _cents(rng, low, high)


SALE_BANDS = ((800, 2500, 5), (2500, 7000, 4), (7000, 14000, 2), (14000, 20000, 1))
PURCHASE_BANDS = ((900, 3000, 4), (3000, 7000, 3), (7000, 12000, 1))
FEE_DOLLARS = (9, 12, 15, 18, 22, 25, 28, 32, 35, 42, 48, 55, 65, 75, 85, 95, 110, 125)
FEE_CENTS = (0, 25, 43, 50, 60, 75, 85, 95)
RECEIPT_PERCENTS = (25, 30, 35, 40, 45, 50, 55, 60, 65, 70)


def _fee_amount(rng: random.Random) -> D:
    return (D(rng.choice(FEE_DOLLARS)) + D(rng.choice(FEE_CENTS)) / 100).quantize(CENT)


def _rent_amount(rng: random.Random) -> D:
    return D(rng.randrange(2000, 6001, 250)).quantize(CENT)


def _fresh(used: set, draw) -> D:
    """An amount no other statement or archive row already carries."""
    for _ in range(500):
        amount = draw()
        if amount not in used:
            used.add(amount)
            return amount
    raise GenerationError("no distinct amount available after 500 draws")


# --------------------------------------------------------------------------
# dates
# --------------------------------------------------------------------------

def _iso(day: date) -> str:
    return day.isoformat()


def _weekday(day: date, forward: bool = True) -> date:
    step = timedelta(days=1 if forward else -1)
    while day.weekday() >= 5:
        day += step
    return day


def _between(rng: random.Random, start: date, end: date) -> date:
    if end < start:
        return start
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _business_day(rng: random.Random, start: date, end: date) -> date:
    """A date in the window that is not a weekend, preferring to move
    forward and falling back to moving back when the window ends on one.
    Never returns a date after `end`: a collapsed window yields `end`, and
    a caller that would have to clamp afterwards is a caller with a bug."""
    if end < start:
        start = end
    day = _weekday(_between(rng, start, end))
    if day > end:
        day = _weekday(end, forward=False)
    return min(max(day, start), end)


def _clears(rng: random.Random, when: date, latest: date, spread: int = 2) -> date:
    """When the bank saw a payment made on `when`: a business day at most
    `spread` days later, never before the payment and never after the
    cut-off the caller names."""
    return max(when, min(_weekday(when + timedelta(days=rng.randint(0, spread))), latest))


def _month_period(year: int, month: int) -> Period:
    last = calendar.monthrange(year, month)[1]
    return Period(f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}",
                  f"{calendar.month_name[month]} {year}")


def _slug(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", out)


# --------------------------------------------------------------------------
# the chart: alpine's twelve accounts, one description carrying the bank name
# --------------------------------------------------------------------------

def _chart(bank_name: str) -> tuple:
    return (
        Account("Assets:Bank:Checking", K.ASSET, f"Primary operating checking account held at {bank_name}", OPENED, 1000),
        Account("Assets:AR", K.ASSET, "Trade receivables from customers", OPENED, 1100),
        Account("Assets:Inventory", K.ASSET, "Goods held for resale", OPENED, 1200),
        Account("Assets:Prepayments", K.ASSET, "Amounts paid in advance of the period they relate to", OPENED, 1300),
        Account("Liabilities:AP", K.LIABILITY, "Trade payables to suppliers", OPENED, 2000),
        Account("Liabilities:SalesTax-Payable", K.LIABILITY,
                "Sales tax collected from customers and owed to the state", OPENED, 2100),
        Account("Income:Sales", K.INCOME, "Revenue from goods sold", OPENED, 4000),
        Account("Expenses:COGS", K.EXPENSE, "Cost of goods sold", OPENED, 5000),
        Account("Expenses:Office", K.EXPENSE, "Office supplies and consumables", OPENED, 5100),
        Account("Expenses:Rent", K.EXPENSE, "Premises rent for the period", OPENED, 5200),
        Account("Expenses:BankFees", K.EXPENSE, "Bank service charges and transaction fees", OPENED, 5300),
        Account("Equity:Opening", K.EQUITY, "Opening balance equity", OPENED, 9000),
    )


ROLES = (("receivables", "Assets:AR"), ("inventory", "Assets:Inventory"),
         ("prepayments", "Assets:Prepayments"), ("payables", "Liabilities:AP"),
         ("sales_tax", "Liabilities:SalesTax-Payable"), ("sales", "Income:Sales"),
         ("cogs", "Expenses:COGS"), ("bank_fees", "Expenses:BankFees"),
         ("opening_equity", "Equity:Opening"))


# --------------------------------------------------------------------------
# identity and parties
# --------------------------------------------------------------------------

def _compose(rng: random.Random, family: str, stem: str, role: str) -> str:
    suffixes = C.PERSONAL_SUFFIXES[role] if family == "personal" else C.TRADE_SUFFIXES[role]
    return f"{stem} {rng.choice(suffixes)}"


@dataclass(frozen=True)
class _Cast:
    company: str
    bank: Party
    customers: tuple
    vendors: tuple                 # (Party, ...) — the rent vendor first, then office, then inventory
    rent_vendor: Party
    office_vendor: Party
    inventory_vendors: tuple


def _cast(seed: int, profile: Profile) -> _Cast:
    rng = _rng(seed, "parties")
    company = ""
    while not company or company in C.RESERVED_NAMES:
        company = f"{rng.choice(C.COMPANY_STEMS)} {rng.choice(C.COMPANY_SUFFIXES)}"
    bank_name = ""
    while not bank_name or bank_name in C.RESERVED_NAMES:
        bank_name = f"{rng.choice(C.BANK_STEMS)} {rng.choice(C.BANK_SUFFIXES)}"

    n_customers = rng.randint(*profile.customers)
    n_vendors = rng.randint(*profile.vendors)
    # roles the world needs: rent, office, and the rest buying stock
    vendor_roles = ["rent", "office"] + ["inventory"] * (n_vendors - 2)
    slots = [("customer", "customer")] * n_customers + [("vendor", r) for r in vendor_roles]

    # A rotation of the three families, offset per seed: one world mixes
    # styles the way a real customer ledger does, and two seeds do not read
    # like the same bookkeeper typed them.
    order = list(C.FAMILIES)
    rng.shuffle(order)
    taken: dict[str, list] = {family: list(C.STEMS[family]) for family in C.FAMILIES}
    for family in C.FAMILIES:                            # by the declared order, never the dict's
        rng.shuffle(taken[family])

    parties, used_names, used_ids = [], set(), set()
    for index, (side, role) in enumerate(slots):
        family = order[index % len(order)]
        name = ""
        while not name or name in used_names or name in C.RESERVED_NAMES:
            if not taken[family]:
                raise GenerationError(f"the {family} stem pool is exhausted")
            name = _compose(rng, family, taken[family].pop(), role)
        used_names.add(name)
        party_id = f"party:{_slug(name)}"
        if party_id in used_ids:
            raise GenerationError(f"two parties slug to {party_id}")
        used_ids.add(party_id)
        if side == "customer":
            terms, account = rng.choice(C.CUSTOMER_TERMS), "Assets:AR"
        elif role == "inventory":
            terms, account = rng.choice(C.INVENTORY_VENDOR_TERMS), "Assets:Inventory"
        elif role == "rent":
            terms, account = rng.choice(C.SERVICE_VENDOR_TERMS), "Expenses:Rent"
        else:
            terms, account = rng.choice(C.SERVICE_VENDOR_TERMS), "Expenses:Office"
        parties.append((role, Party(party_id, name, R.CUSTOMER if side == "customer" else R.VENDOR,
                                    index + 1, terms, account)))

    bank = Party(f"party:{_slug(bank_name)}", bank_name, R.BANK, len(parties) + 1)
    customers = tuple(p for role, p in parties if role == "customer")
    vendors = tuple(p for role, p in parties if role != "customer")
    return _Cast(company, bank, customers, vendors,
                 next(p for role, p in parties if role == "rent"),
                 next(p for role, p in parties if role == "office"),
                 tuple(p for role, p in parties if role == "inventory"))


# --------------------------------------------------------------------------
# documents: numbered once, in issue order, after every date is known
# --------------------------------------------------------------------------

class _Invoice:
    """A pending invoice. Its number is assigned after every issue date is
    known, so numbers run in date order the way a real book of invoices
    does, and the memos that quote the number are written afterwards."""

    __slots__ = ("kind", "party_id", "issued", "gross", "number", "id")

    def __init__(self, kind: str, party_id: str, issued: date, gross: D):
        self.kind, self.party_id, self.issued, self.gross = kind, party_id, issued, gross
        self.number = ""
        self.id = ""


class _Cheque:
    """A pending check. Numbered after every issue date is known, so a
    check book runs in date order: the payment made on the 3rd carries a
    lower number than the one made on the 27th, which is the only thing a
    reader checks about a check number."""

    __slots__ = ("party_id", "issued", "mine", "sequence", "number", "id", "placeholder")

    def __init__(self, party_id: str, issued: date, mine: bool, sequence: int):
        self.party_id, self.issued, self.mine, self.sequence = party_id, issued, mine, sequence
        self.number = 0
        self.placeholder = f"doc:chq-pending-{sequence}"
        self.id = self.placeholder


# --------------------------------------------------------------------------
# the draw
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _Draft:
    documents: tuple
    events: tuple
    bank_opening: BankOpening
    opening: OpeningPosition


def _receipt_split(rng: random.Random, gross: D, count: int):
    """How a customer settles an invoice: in full, in part, or in two
    instalments. Never more than the gross — the invariant that
    `check_bundle` re-checks from the other side."""
    if count == 0:
        return ()
    if count == 1:
        if _weighted(rng, ((True, 6), (False, 4))):
            return (gross,)
        part = (gross * D(rng.choice(RECEIPT_PERCENTS)) / 100).quantize(CENT)
        return (part,) if D("0") < part < gross else (gross,)
    first = (gross * D(rng.choice(RECEIPT_PERCENTS)) / 100).quantize(CENT)
    if not D("0") < first < gross:
        return (gross,)
    if _weighted(rng, ((True, 7), (False, 3))):
        return (first, (gross - first).quantize(CENT))
    second = ((gross - first) * D(rng.choice(RECEIPT_PERCENTS)) / 100).quantize(CENT)
    return (first, second) if second > 0 else (first,)


def _facts(seed: int, profile: Profile, period: Period, cast: _Cast) -> _Draft:
    rng_amount = _rng(seed, "amounts")
    rng_event = _rng(seed, "events")
    rng_time = _rng(seed, "timing")
    rng_word = _rng(seed, "wording")
    rng_doc = _rng(seed, "documents")

    prior = prior_period(period)
    p_start, p_end = date.fromisoformat(period.start), date.fromisoformat(period.end)
    q_start, q_end = date.fromisoformat(prior.start), date.fromisoformat(prior.end)
    month_name = calendar.month_name[p_start.month]
    next_month = date(p_end.year + (1 if p_end.month == 12 else 0), 1 if p_end.month == 12 else p_end.month + 1, 1)

    tax_rate = rng_amount.choice(profile.tax_rates)
    rent = _rent_amount(rng_amount)

    # --- how many of each row the two statements carry ------------------
    rows = rng_event.randint(*profile.statement_rows)
    budget = rows - 1                                   # the opening row is not a movement
    n_fee = _weighted(rng_event, ((1, 6), (2, 4)))
    n_office = min(5, max(3, round(budget * 0.18)))
    n_vendor = min(6, max(4, round(budget * 0.28)))
    n_receipt = budget - n_fee - 1 - n_office - n_vendor
    if n_receipt < 4:
        raise GenerationError(f"seed {seed}: only {n_receipt} receipts fit the statement budget")
    n_prior = rng_event.randint(*profile.prior_rows)
    prior_rest = n_prior - 3                            # rent, office and the fee are always there
    n_prior_receipt = prior_rest - prior_rest // 2
    n_prior_payment = prior_rest // 2
    n_boundary_receipt = min(rng_event.randint(1, 2), n_receipt - 3)

    documents: list = []
    events: list = []
    used: set = set()                                   # every amount a statement row will carry
    cheques: list = []

    def next_cheque(party_id: str, issued: date) -> _Cheque:
        cheque = _Cheque(party_id, issued, True, len(cheques))
        cheques.append(cheque)
        documents.append(cheque)
        return cheque

    def customer_cheque(party_id: str, issued: date) -> _Cheque:
        cheque = _Cheque(party_id, issued, False, len(cheques))
        cheques.append(cheque)
        documents.append(cheque)
        return cheque

    def invoice(kind: str, party_id: str, issued: date, gross: D) -> _Invoice:
        doc = _Invoice(kind, party_id, issued, gross)
        documents.append(doc)
        return doc

    # --- the prior period: five to eight rows the archive prints ---------
    prior_receipt_docs, prior_payment_docs = [], []
    for _ in range(n_prior_receipt):
        issued = _between(rng_time, q_start - timedelta(days=70), q_start - timedelta(days=8))
        prior_receipt_docs.append(invoice("sales", rng_event.choice(cast.customers).id, issued,
                                          _fresh(used, lambda: _bucketed(rng_amount, SALE_BANDS))))
    for _ in range(n_prior_payment):
        vendor = rng_event.choice(cast.inventory_vendors)
        issued = _between(rng_time, q_start - timedelta(days=70), q_start - timedelta(days=8))
        prior_payment_docs.append(invoice("purchase", vendor.id, issued,
                                          _fresh(used, lambda: _bucketed(rng_amount, PURCHASE_BANDS))))

    # --- the boundary: issued last month, settled this month -------------
    boundary_receipt_docs = []
    for _ in range(n_boundary_receipt):
        boundary_receipt_docs.append(invoice("sales", rng_event.choice(cast.customers).id,
                                             _business_day(rng_time, q_start + timedelta(days=6), q_end),
                                             _fresh(used, lambda: _bucketed(rng_amount, SALE_BANDS))))
    boundary_payment_docs = []
    for _ in range(n_vendor):
        vendor = rng_event.choice(cast.inventory_vendors)
        boundary_payment_docs.append(invoice("purchase", vendor.id,
                                             _business_day(rng_time, q_start, q_end - timedelta(days=2)),
                                             _fresh(used, lambda: _bucketed(rng_amount, PURCHASE_BANDS))))

    # --- this period's sales, and how they are settled -------------------
    sale_plan = []                                       # (receipt count, ...)
    scheduled = n_receipt - n_boundary_receipt
    while scheduled > 0:
        take = min(_weighted(rng_event, ((1, 5), (2, 3))), scheduled)
        sale_plan.append(take)
        scheduled -= take
    open_sales = rng_event.randint(1, 2)
    sale_plan += [0] * open_sales
    rng_event.shuffle(sale_plan)

    sales = []                                           # (invoice, sale event fields, receipt amounts)
    for count in sale_plan:
        # room for every instalment: three clear days each, then the sale
        latest = p_end - timedelta(days=3 * count + 2) if count else p_end
        issued = _business_day(rng_time, p_start, max(latest, p_start))
        for _ in range(500):
            net = _bucketed(rng_amount, SALE_BANDS)
            gross = (net + (net * tax_rate).quantize(CENT)).quantize(CENT)
            amounts = _receipt_split(rng_amount, gross, count)
            if len(set(amounts)) == len(amounts) and not used.intersection(amounts):
                used.update(amounts)
                break
        else:
            raise GenerationError("no distinct sale settlement available")
        cost = (net * D(rng_amount.randint(45, 70)) / 100).quantize(CENT)
        doc = invoice("sales", rng_event.choice(cast.customers).id, issued, gross)
        sales.append((doc, net, cost, issued, amounts))

    # --- this period's purchases: received on credit, unpaid at close ---
    purchases = []
    for _ in range(rng_event.randint(2, 3)):
        vendor = rng_event.choice(cast.inventory_vendors)
        received = _business_day(rng_time, p_start + timedelta(days=3), p_end)
        amount = _bucketed(rng_amount, PURCHASE_BANDS)
        purchases.append((invoice("purchase", vendor.id, received, amount), received, amount))

    # --- numbering: invoices run in issue order -------------------------
    si_number = rng_doc.randrange(1000, 1600)
    pi_number = rng_doc.randrange(2000, 2700)
    for doc in sorted((d for d in documents if isinstance(d, _Invoice)),
                      key=lambda d: (d.issued, d.party_id, str(d.gross))):
        if doc.kind == "sales":
            si_number += 1
            doc.number, doc.id = f"SI-{si_number}", f"doc:si-{si_number}"
        else:
            pi_number += 1
            doc.number, doc.id = f"PI-{pi_number}", f"doc:pi-{pi_number}"

    # --- the events -----------------------------------------------------
    # One template per rule for the whole world: a ledger is written by one
    # bookkeeper (or one billing system), so its sale lines all read the
    # same way. Only what was actually bought varies line by line.
    voice = {rule: rng_word.choice(templates) for rule, templates in sorted(C.NARRATIONS.items())}
    varies = ("office", "bank_fee_extra")               # what was bought differs purchase by purchase

    def memo(rule: str, **fields) -> str:
        template = rng_word.choice(C.NARRATIONS[rule]) if rule in varies else voice[rule]
        return template.format(**fields)

    def with_cheque(text: str) -> str:
        """The number is not known until the check book is numbered, so the
        memo carries a `{number}` slot that the numbering pass fills in."""
        return C.CHEQUE_MEMO.format(memo=text, number="{number}")

    def add_receipt(doc: _Invoice, when: date, amount: D, clears: date, full: bool, tag: str):
        by_cheque = _weighted(rng_event, ((True, 3), (False, 7)))
        text = memo("receipt_full" if full else "receipt_partial", invoice=doc.number)
        if by_cheque:
            cheque = customer_cheque(doc.party_id, when)
            settlement = Settlement(Rail.CHEQUE, _iso(clears), cheque.id)
            text = with_cheque(text)
        else:
            settlement = Settlement(Rail.ACH_IN, _iso(clears))
        events.append(CustomerReceipt(f"event:{doc.id.split(':', 1)[1]}-receipt{tag}", _iso(when),
                                      doc.party_id, doc.id, amount, settlement, text))

    def add_vendor_payment(doc: _Invoice, when: date, clears: date):
        by_cheque = _weighted(rng_event, ((True, 4), (False, 6)))
        text = memo("vendor_payment", invoice=doc.number)
        if by_cheque:
            cheque = next_cheque(doc.party_id, when)
            settlement = Settlement(Rail.CHEQUE, _iso(clears), cheque.id)
            text = with_cheque(text)
        else:
            settlement = Settlement(Rail.ACH_OUT, _iso(clears))
        events.append(VendorPayment(f"event:{doc.id.split(':', 1)[1]}-payment", _iso(when),
                                    doc.party_id, doc.id, doc.gross, settlement, text))

    def add_office(when: date, clears: date, amount: D, index: int):
        by_cheque = _weighted(rng_event, ((True, 2), (False, 8)))
        text = memo("office")
        if by_cheque:
            cheque = next_cheque(cast.office_vendor.id, when)
            settlement = Settlement(Rail.CHEQUE, _iso(clears), cheque.id)
            text = with_cheque(text)
        else:
            settlement = Settlement(Rail.CARD, _iso(when))
        events.append(ExpensePayment(f"event:office-{when.year}-{when.month:02d}-{index}", _iso(when),
                                     cast.office_vendor.id, amount, settlement, text))

    # prior period
    for doc in prior_receipt_docs:
        when = _business_day(rng_time, q_start, q_end)
        add_receipt(doc, when, doc.gross, when, True, "")
    for doc in prior_payment_docs:
        when = _business_day(rng_time, q_start, q_end)
        add_vendor_payment(doc, when, when)
    prior_rent_day = _business_day(rng_time, q_start, q_start + timedelta(days=4))
    prior_rent_cheque = next_cheque(cast.rent_vendor.id, prior_rent_day)
    used.add(rent)
    events.append(ExpensePayment(f"event:rent-{q_start.year}-{q_start.month:02d}", _iso(prior_rent_day),
                                 cast.rent_vendor.id, rent,
                                 Settlement(Rail.CHEQUE, _iso(_clears(rng_time, prior_rent_day, q_end)),
                                            prior_rent_cheque.id),
                                 with_cheque(memo("rent", month=calendar.month_name[q_start.month]))))
    prior_office_day = _business_day(rng_time, q_start + timedelta(days=8), q_end - timedelta(days=3))
    add_office(prior_office_day, prior_office_day, _fresh(used, lambda: _cents(rng_amount, 40, 900)), 1)
    prior_fee_day = q_end - timedelta(days=rng_time.randint(0, 1))
    events.append(BankFee(f"event:fee-{q_start.year}-{q_start.month:02d}", _iso(prior_fee_day),
                          _fresh(used, lambda: _fee_amount(rng_amount)), memo("bank_fee")))

    # this period: the boundary receipts
    for doc in boundary_receipt_docs:
        when = _business_day(rng_time, p_start, p_end - timedelta(days=3))
        add_receipt(doc, when, doc.gross, _clears(rng_time, when, p_end), True, "")
    # this period: the vendor payments against last month's purchase invoices
    for doc in boundary_payment_docs:
        when = _business_day(rng_time, p_start, p_end - timedelta(days=2))
        add_vendor_payment(doc, when, _clears(rng_time, when, p_end, spread=3))
    # this period: sales and their receipts
    for doc, net, cost, issued, amounts in sales:
        events.append(Sale(f"event:{doc.id.split(':', 1)[1]}-sale", _iso(issued), doc.party_id, doc.id,
                           net, tax_rate, cost, memo("sale", invoice=doc.number),
                           memo("sale_cost", invoice=doc.number)))
        when = issued
        for index, amount in enumerate(amounts):
            when = _business_day(rng_time, when + timedelta(days=3),
                                 p_end - timedelta(days=3 * (len(amounts) - 1 - index)))
            add_receipt(doc, when, amount, _clears(rng_time, when, p_end), amount == doc.gross,
                        "" if index == 0 else f"-{index + 1}")
    # this period: purchases on credit
    for doc, received, amount in purchases:
        events.append(Purchase(f"event:{doc.id.split(':', 1)[1]}-purchase", _iso(received), doc.party_id,
                               doc.id, amount, memo("purchase", invoice=doc.number)))
    # this period: office spending
    for index in range(n_office):
        when = _business_day(rng_time, p_start, p_end - timedelta(days=1))
        add_office(when, _clears(rng_time, when, p_end), _fresh(used, lambda: _cents(rng_amount, 40, 900)), index + 1)
    # this period: rent, and next month's rent paid early by check
    rent_day = _business_day(rng_time, p_start, p_start + timedelta(days=4))
    rent_cheque = next_cheque(cast.rent_vendor.id, rent_day)
    events.append(ExpensePayment(f"event:rent-{p_start.year}-{p_start.month:02d}", _iso(rent_day),
                                 cast.rent_vendor.id, rent,
                                 Settlement(Rail.CHEQUE, _iso(_clears(rng_time, rent_day, p_end)),
                                            rent_cheque.id),
                                 with_cheque(memo("rent", month=month_name))))
    prepaid_day = _business_day(rng_time, p_end - timedelta(days=4), p_end)
    prepaid_cheque = next_cheque(cast.rent_vendor.id, prepaid_day)
    events.append(Prepayment(f"event:rent-{next_month.year}-{next_month.month:02d}-prepaid", _iso(prepaid_day),
                             cast.rent_vendor.id, rent,
                             Settlement(Rail.CHEQUE, _iso(_weekday(next_month + timedelta(days=rng_time.randint(1, 5)))),
                                        prepaid_cheque.id),
                             f"{next_month.year}-{next_month.month:02d}",
                             with_cheque(memo("prepayment", month=calendar.month_name[next_month.month]))))
    # this period: the bank's own charges
    fee_day = p_end - timedelta(days=rng_time.randint(0, 1))
    events.append(BankFee(f"event:fee-{p_start.year}-{p_start.month:02d}", _iso(fee_day),
                          _fresh(used, lambda: _fee_amount(rng_amount)), memo("bank_fee")))
    if n_fee == 2:
        extra_day = _business_day(rng_time, p_start + timedelta(days=8), p_end - timedelta(days=4))
        events.append(BankFee(f"event:fee-{p_start.year}-{p_start.month:02d}-b", _iso(extra_day),
                              _fresh(used, lambda: _fee_amount(rng_amount)), memo("bank_fee_extra")))
    # this period: a deposit the bank had not credited by the cut-off
    owing = [(doc, issued, (doc.gross - sum(amounts, D("0"))).quantize(CENT))
             for doc, _, _, issued, amounts in sales
             if (doc.gross - sum(amounts, D("0"))) > 0 and issued < p_end]
    if owing and _weighted(rng_event, ((True, 5), (False, 5))):
        doc, issued, outstanding = owing[-1]
        when = max(_business_day(rng_time, p_end - timedelta(days=3), p_end), issued)
        # Distinct across EVERY movement, cleared or in transit: the sweep
        # found a transit deposit equal to an earlier receipt on the same
        # invoice, which no public evidence could tell apart.
        def draw_transit() -> D:
            return outstanding if _weighted(rng_event, ((True, 6), (False, 4))) else (
                (outstanding * D(rng_amount.choice(RECEIPT_PERCENTS)) / 100).quantize(CENT))
        amount = _fresh(used, draw_transit)
        if amount > 0:
            add_receipt(doc, when, amount, _weekday(p_end + timedelta(days=rng_time.randint(1, 4))),
                        amount == doc.gross, "-transit")

    # --- the check book: numbered in issue order, then written in --------
    ours = rng_doc.randrange(1010, 1880)
    for offset, cheque in enumerate(sorted((c for c in cheques if c.mine),
                                           key=lambda c: (c.issued, c.sequence))):
        cheque.number = ours + offset
        cheque.id = f"doc:chq-{cheque.number}"
    bases = rng_doc.sample(range(4000, 9600, 200), len(cast.customers))
    for base, customer in zip(bases, cast.customers):
        for offset, cheque in enumerate(sorted((c for c in cheques if not c.mine and c.party_id == customer.id),
                                               key=lambda c: (c.issued, c.sequence))):
            cheque.number = base + offset
            cheque.id = f"doc:chq-{cheque.number}"
    written = {c.placeholder: c for c in cheques}
    for index, event in enumerate(events):
        settlement = getattr(event, "settlement", None)
        if settlement is None or settlement.cheque_id not in written:
            continue
        cheque = written[settlement.cheque_id]
        events[index] = replace(event, memo=event.memo.format(number=cheque.number),
                                settlement=replace(settlement, cheque_id=cheque.id))

    # --- the balances history did not model -----------------------------
    prior_open_ar = sum((d.gross for d in boundary_receipt_docs), D("0"))
    prior_open_ap = sum((d.gross for d in boundary_payment_docs), D("0"))
    period_cost = sum((cost for _, _, cost, _, _ in sales), D("0"))
    period_stock = sum((amount for _, _, amount in purchases), D("0"))
    opening = OpeningPosition(period.start, (
        ("Assets:AR", (prior_open_ar + _cents(rng_amount, 2000, 12000)).quantize(CENT)),
        ("Assets:Inventory", (period_cost + period_stock + _cents(rng_amount, 8000, 25000)).quantize(CENT)),
        ("Liabilities:AP", -(prior_open_ap + _cents(rng_amount, 1500, 9000)).quantize(CENT)),
    ))

    # --- the one authored bank figure -----------------------------------
    flows = []
    for event in events:
        settlement = getattr(event, "settlement", None)
        if settlement is None and not isinstance(event, BankFee):
            continue                                    # a sale on credit moves no cash
        when = settlement.cleared_on if settlement is not None else event.date
        sign = 1 if isinstance(event, CustomerReceipt) else -1
        flows.append((when, sign * event.amount))
    flows.sort()
    running, lowest = D("0"), D("0")
    for _, amount in flows:
        running += amount
        lowest = min(lowest, running)
    floor = _cents(rng_amount, 4000, 12000)
    bank_opening = BankOpening(prior.start, (-lowest + floor).quantize(CENT))

    docs = tuple(Document(d.id, DK.SALES_INVOICE if d.kind == "sales" else DK.PURCHASE_INVOICE,
                          d.number, d.party_id, _iso(d.issued), d.gross)
                 if isinstance(d, _Invoice) else
                 Document(d.id, DK.CHEQUE, str(d.number), d.party_id, _iso(d.issued))
                 for d in documents)
    return _Draft(docs, tuple(events), bank_opening, opening)


# --------------------------------------------------------------------------
# the plan: which derived recognitions the task plants a difference on
# --------------------------------------------------------------------------

_RULE_OF = {
    CustomerReceipt: "customer_receipt",
    VendorPayment: "vendor_payment",
    ExpensePayment: "expense_payment",
    BankFee: "bank_fee",
    Prepayment: "prepayment",
}

_OMIT_ID = {
    "customer_receipt": "unrecorded_customer_deposit",
    "vendor_payment": "unrecorded_supplier_payment",
    "expense_payment": "unrecorded_card_payment",
    "bank_fee": "unrecorded_bank_fee",
}


def _claim(kind: str, world: World, event, movement, wrong: D | None) -> str:
    party = world.party(getattr(event, "party_id", world.bank_party_id))
    row = f"{movement.cleared_on} {movement.description} for {abs(movement.amount):.2f}"
    if isinstance(event, CustomerReceipt):
        where = (f"the reference names {world.document(event.invoice_id).number} and customers.csv maps "
                 f"{party.name} to Assets:AR")
    elif isinstance(event, VendorPayment):
        where = (f"the reference names {world.document(event.invoice_id).number}, an open payable in the "
                 f"opening balances")
    elif isinstance(event, ExpensePayment):
        where = f"vendors.csv maps {party.name} to {party.default_account}"
    else:
        where = ("it is a bank-initiated charge with no counterparty and policy.md records bank fees to "
                 "Expenses:BankFees on the date applied")
    if kind == "omit":
        return f"the statement row {row} has no matching ledger entry; {where}"
    if kind == "alter":
        return f"the statement row {row} disagrees with the ledger entry of {wrong:.2f} on the same date; {where}"
    return f"the statement row {row} appears once and the ledger carries the entry twice; {where}"


def _plan(seed: int, profile: Profile, world: World, period: Period) -> MutationPlan:
    rng = _rng(seed, "plan")
    prior = prior_period(period)
    movements = {}
    for event in world.events:
        movement = movement_of(world, event)
        if movement is not None:
            movements[event.id] = movement
    # every amount either statement prints: a planted difference must be
    # pinnable to exactly one public row by its amount alone
    printed = Counter(abs(m.amount) for m in movements.values()
                      if prior.start <= m.cleared_on <= period.end)
    # A reference decides a pairing only when it is unique across all
    # public evidence: a planted item whose row reference an
    # invoice paid in two receipts also carries is not decidable by it.
    ref_count = Counter(m.reference for m in movements.values() if m.reference)
    candidates = []
    alterable_ids: set = set()
    for event in sorted(world.events, key=lambda e: e.id):
        movement = movements.get(event.id)
        if movement is None or not period.contains(movement.cleared_on):
            continue
        if _RULE_OF.get(type(event)) not in _OMIT_ID:
            continue                                    # a prepayment clears after the cut-off: no public row
        if printed[abs(movement.amount)] != 1:
            continue                                    # the rent: the same figure every month
        # A reader pins a discrepancy to a counterparty and a few days: if the
        # same party has ANOTHER movement clearing within three days, a
        # missing entry and a wrong amount become two defensible readings
        # (the property suite's public-only checker found 3/30 such plans).
        party = getattr(event, "party_id", None)
        crowded = any(
            other.id != event.id and getattr(other, "party_id", None) == party and other.id in movements
            and (abs(_days(other.date, event.date)) <= 3 or abs(_days(other.date, movement.cleared_on)) <= 3
                 or abs(_days(movements[other.id].cleared_on, movement.cleared_on)) <= 3)
            for other in world.events)
        if party is not None and crowded:
            continue
        if movement.reference and ref_count[movement.reference] != 1:
            continue                                    # the reference is reused: not decidable by it
        candidates.append(event)
        # A wrong amount is decidable from the public files only when the
        # statement row ties to the booked entry by a reference (cheque or
        # invoice number), by the policy's wording (a bank fee), or when the
        # entry is too early to pass as an outstanding item. Otherwise the
        # reader has two readings and the checker rightly refuses.
        if movement.reference or _RULE_OF[type(event)] == "bank_fee" or _days(period.end, movement.cleared_on) > 10:
            alterable_ids.add(event.id)
    if len(candidates) < 2:
        raise GenerationError(f"seed {seed}: {len(candidates)} identifiable recognition(s); profile "
                              f"{profile.name} needs {profile.planted[0]}")

    # spread the plan over different kinds of event where the world allows
    by_rule: dict[str, list] = {}
    for event in candidates:
        by_rule.setdefault(_RULE_OF[type(event)], []).append(event)
    rules = sorted(by_rule)
    if len(rules) < profile.min_rules:
        # The round-robin below puts one candidate of every rule first, so the
        # number of rules among the candidates is the number of counter
        # accounts the plan can move; a world with too few is refused.
        raise GenerationError(f"seed {seed}: candidates span {len(rules)} rule(s), profile {profile.name} needs "
                              f"{profile.min_rules} so the planted items touch {profile.min_rules + 1} target accounts; "
                              "unsupported topology")
    for rule in rules:                                   # by name, never by dict order
        rng.shuffle(by_rule[rule])
    rng.shuffle(rules)
    ordered = []
    while any(by_rule[rule] for rule in rules):
        for rule in rules:
            if by_rule[rule]:
                ordered.append(by_rule[rule].pop())

    count = min(rng.randint(*profile.planted), len(ordered))
    if count < profile.planted[0]:
        # The profile is a versioned promise, not a target: a world that
        # cannot carry its minimum is refused, never silently under-planted.
        raise GenerationError(f"seed {seed}: {len(ordered)} identifiable candidates, profile {profile.name} "
                              f"needs {profile.planted[0]}; unsupported topology")
    chosen = ordered[:count]
    kinds = list(rng.sample(list(profile.kinds), min(2, len(profile.kinds))))
    kinds += [rng.choice(list(profile.kinds)) for _ in range(count - len(kinds))]
    kinds = kinds[:count]
    rng.shuffle(kinds)
    # the profile's per-kind caps: surplus alterations/duplicates become omissions
    caps = dict(profile.max_per_kind)
    seen_kind: Counter = Counter()
    for i, kind in enumerate(kinds):
        seen_kind[kind] += 1
        if seen_kind[kind] > caps.get(kind, count):
            kinds[i] = "omit"
    # an alteration needs an alterable candidate; downgrade the rest, then
    # restore the profile's promise of two kinds with a duplicate (always
    # available: every candidate is unique in the period by construction)
    for i, (event, kind) in enumerate(zip(chosen, kinds)):
        if kind == "alter" and event.id not in alterable_ids:
            kinds[i] = "omit"
    if count >= 2 and len(set(kinds)) < 2 and "duplicate" in profile.kinds and caps.get("duplicate", count) >= 1:
        kinds[kinds.index("omit")] = "duplicate"

    mutations, taken, residuals = [], set(), []
    roles = Roles(**dict(world.roles))
    for event, kind in zip(chosen, kinds):
        rule = _RULE_OF[type(event)]
        movement = movements[event.id]
        recognition = f"rec:{event.id.split(':', 1)[1]}"
        choice = _alter_choice(rng, world, event, printed) if kind == "alter" else None
        wrong = choice[2] if choice else None
        if wrong is not None:
            printed[wrong] += 1                          # two altered entries never share a wrong figure
        if kind == "alter" and choice is None:
            kind = "omit"
        # The residual each item leaves on the books, as `derive` will compute
        # it: the clean legs for an omission, clean minus wrong for an
        # alteration, minus the clean legs for a duplicate.
        clean = {leg.account: leg.amount for leg in recognitions_of(world, roles, event)[0].legs}
        if kind == "omit":
            residual = dict(clean)
        elif kind == "alter":
            observed = dict(derive_mutant(tuple(clean.items()), choice[0], choice[1]))
            residual = {a: clean[a] - observed.get(a, D("0")) for a in clean if clean[a] != observed.get(a, D("0"))}
        else:
            residual = {a: -v for a, v in clean.items()}
        residuals.append(residual)
        if kind == "omit":
            mutation_id = _OMIT_ID[rule]
        elif kind == "alter":
            mutation_id = f"transposed_{rule}"
        else:
            mutation_id = f"duplicated_{rule}"
        while mutation_id in taken:
            mutation_id += "-again"
        taken.add(mutation_id)
        claim = _claim(kind, world, event, movement, wrong)
        if kind == "omit":
            mutations.append(OmitRecognition(mutation_id, recognition, claim))
        elif kind == "alter":
            strategy, parameter, _ = choice
            mutations.append(AlterRecognition(mutation_id, recognition, strategy, parameter, claim))
        else:
            mutations.append(DuplicateRecognition(mutation_id, recognition, claim))
    # No subset of the planted items may cancel on every target account
    # (`derive` refuses such a plan). Two transpositions on one rule can leave
    # equal and opposite residuals; refusing here makes it a retried layout
    # rather than a selector that fails to derive.
    support = {a for r in residuals for a in r}
    for n in range(2, len(residuals) + 1):
        for subset in combinations(residuals, n):
            total: dict = {}
            for r in subset:
                for a, v in r.items():
                    total[a] = total.get(a, D("0")) + v
            if all(total.get(a, D("0")) == 0 for a in support):
                raise GenerationError(f"seed {seed}: planted residuals cancel on a subset of the plan; unsupported topology")
    return MutationPlan(tuple(mutations))


def _alter_choice(rng: random.Random, world: World, event, printed: Counter):
    """A typed bookkeeping error for this recognition: (strategy, parameter,
    wrong amount), or None when no plausible error is available. The wrong
    figure is what `project.derive_mutant` makes of the truth — the
    generator never authors a vector — and it must not be a
    figure any statement row carries. Transposition is preferred 6:4 over a
    dropped digit; a decimal shift is the rare third, and never on a bank
    fee — a ten-fold error on a $85 charge reads as fabricated, not as a
    clerk's slip."""
    from .project import ProjectionError
    recognition = recognitions_of(world, Roles(**dict(world.roles)), event)[0]
    true_legs = tuple((leg.account, leg.amount) for leg in recognition.legs)
    cents = int((abs(true_legs[0][1]) * 100).to_integral_value())
    width = len(str(cents))
    options = [("transpose_digits", i) for i in range(width - 1)] * 6 + [("drop_digit", i) for i in range(width)] * 4 \
        + [("decimal_shift", -1), ("decimal_shift", 1)]
    rng.shuffle(options)
    seen = set()
    for strategy, parameter in options:
        if (strategy, parameter) in seen:
            continue
        seen.add((strategy, parameter))
        if strategy == "decimal_shift" and isinstance(event, BankFee):
            continue
        try:
            wrong_legs = derive_mutant(true_legs, strategy, parameter)
        except ProjectionError:
            continue
        wrong = abs(wrong_legs[0][1])
        if printed[wrong] == 0 and wrong >= D("1.00"):
            return strategy, parameter, wrong
    return None


# --------------------------------------------------------------------------
# the entry point
# --------------------------------------------------------------------------

def generate(seed: int, profile: Profile = DEFAULT_PROFILE) -> tuple[World, TaskSpec]:
    """One integer in; one valid world and the task over it out. Pure."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise GenerationError(f"a seed is an int, not {type(seed).__name__}")
    problems = C.check_content()
    if problems:
        raise GenerationError("content library: " + "; ".join(problems))

    month = _rng(seed, "period").randint(FIRST_MONTH, LAST_MONTH)
    period = _month_period(YEAR, month)
    cast = _cast(seed, profile)
    draft = _facts(seed, profile, period, cast)

    world = World(
        id=f"{_slug(cast.company)}-{period.start[:7]}",
        title=f"{cast.company} - FY{YEAR}",
        currency="USD",
        bank_account="Assets:Bank:Checking",
        bank_party_id=cast.bank.id,
        accounts=_chart(cast.bank.name),
        parties=cast.customers + cast.vendors + (cast.bank,),
        documents=draft.documents,
        bank_opening=draft.bank_opening,
        opening=draft.opening,
        events=draft.events,
        roles=ROLES,
        policy_text=C.POLICY_TEMPLATE.format(company=cast.company),
    )
    problems = check_world(world)
    if problems:
        raise GenerationError(f"seed {seed}: " + "; ".join(problems))

    task = TaskSpec(
        # Never the seed: the public id is derived from the public bytes by
        # `mint.mint`, which is the only production door to a generated task.
        id="task-pending",
        type="bank_reconciliation",
        prompt=_rng(seed, "prompt").choice(C.PROMPTS).format(month=period.label.split()[0]),
        period=period,
        plan=_plan(seed, profile, world, period),
    )
    return world, task


# --------------------------------------------------------------------------
# eyeballing: python -m beancount_ledger.graph.generate <seed>
# --------------------------------------------------------------------------

def _main(argv) -> int:
    import sys

    from .project import project

    if len(argv) != 2:
        print("usage: python -m beancount_ledger.graph.generate <seed>")
        return 2
    seed = int(argv[1])
    world, task = generate(seed)
    bundle = project(world, task.period, task.plan)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"# {task.id}: {world.title} — {task.period.label}")
    print(f"# {task.prompt}")
    for mutation in task.plan.mutations:
        print(f"# {type(mutation).__name__} {mutation.mutation_id}: {mutation.identifiability_claim}")
    for name, data in sorted(bundle.public_files().items()):
        print(f"\n===== {name} =====")
        print(data.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
