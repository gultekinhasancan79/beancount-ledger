"""PROTOTYPE public-evidence-only wrong-account checker (WA-1).
Reads the eight public files as TEXT and nothing else."""
import re, sys
from dataclasses import dataclass
from decimal import Decimal
sys.path.insert(0, r"C:/Users/gulte/Desktop/PIV/beancount-ledger-workflows")
from beancount_ledger.graph.identify import (
    ACCOUNTS_FILE, LEDGER_FILE, POLICY_FILE, STATEMENT_FILE, VENDORS_FILE,
    SUPPLIER_PAYMENT_SECTION, PublicOnly,
    _chart, _parties, _counterparties, _gap, _rail_of, ledger_movements, statement_rows,
    RAIL_WINDOW_DAYS, MATCH_WINDOW_DAYS)

WA_KIND = "wrong_account"


class Undecidable(Exception):
    """The public files do not fix the answer; the case is inadmissible."""


@dataclass(frozen=True)
class WrongAccountRepair:
    date: str
    payee: str
    amount: Decimal            # positive magnitude of the payment
    from_account: str          # what the books carry
    to_account: str            # what the policy requires
    bank_account: str
    narration: str
    reference: str
    authority: tuple           # the public sentences that decide it

    def key(self) -> tuple:
        required = tuple(sorted(((self.bank_account, f"{-self.amount:.2f}"),
                                 (self.to_account, f"{self.amount:.2f}"))))
        booked = tuple(sorted(((self.bank_account, f"{-self.amount:.2f}"),
                               (self.from_account, f"{self.amount:.2f}"))))
        return (WA_KIND, self.date, required, self.payee, booked, 1)


def _section_body(policy_text: str, section: str) -> str:
    lines = policy_text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip().startswith(section)), None)
    if start is None:
        return ""
    body = []
    for l in lines[start + 1:]:
        if l.startswith("## "):
            break
        body.append(l)
    return "\n".join(body)


def _payables_from_ledger(movements_all_entries, parties, chart):
    """The payables account, from the ledger's own purchase entries.
    A purchase entry is (Dr V.default_account, Cr L) with V a vendor whose
    default_account is typed an asset and L a liability. Exactly one L."""
    found = {}
    for date, payee, narration, legs in movements_all_entries:
        if len(legs) != 2:
            continue
        pos = [(a, v) for a, v in legs if v > 0]
        neg = [(a, v) for a, v in legs if v < 0]
        if len(pos) != 1 or len(neg) != 1:
            continue
        (da, dv), (ca, cv) = pos[0], neg[0]
        role, default = parties.get(payee, (None, None))
        if role != "vendor" or default != da or chart.get(da) != "asset":
            continue
        if chart.get(ca) != "liability":
            continue
        found.setdefault(ca, []).append((date, payee, da, dv))
    if len(found) != 1:
        raise Undecidable(f"the ledger's purchase entries name {len(found)} payables accounts: {sorted(found)}")
    account = next(iter(found))
    return account, found[account]


def _all_entries(ledger_text: str):
    """Every transaction in the ledger as (date, payee, narration, legs)."""
    out, header, legs = [], None, []
    for raw in ledger_text.splitlines():
        m = re.match(r'^(\d{4}-\d{2}-\d{2})\s+[*!]\s+"([^"]*)"\s+"([^"]*)"\s*$', raw)
        if m:
            if header:
                out.append((*header, tuple(sorted(legs))))
            header, legs = (m.group(1), m.group(2), m.group(3)), []
            continue
        p = re.match(r'^\s{2,}([A-Za-z][\w:.\-]*)\s+(-?[\d,]+\.\d{2})\s+([A-Z]{3})\s*$', raw)
        if p and header:
            legs.append((p.group(1), Decimal(p.group(2).replace(",", ""))))
            continue
        if raw.strip() == "" and header:
            out.append((*header, tuple(sorted(legs))))
            header, legs = None, []
    if header:
        out.append((*header, tuple(sorted(legs))))
    return tuple(out)


def wrong_account_repairs(public: dict, *, bank_account: str, period_start: str, period_end: str):
    """The wrong-account repairs the public files force. Raises Undecidable
    when the files do not fix the answer."""
    if not isinstance(public, dict) or any(not isinstance(v, str) for v in public.values()):
        raise PublicOnly("this checker reads the mounted bytes and nothing else")
    chart = _chart(public)
    parties = _parties(public)
    entries = _all_entries(public[LEDGER_FILE])
    payables, purchases = _payables_from_ledger(entries, parties, chart)
    section = _section_body(public.get(POLICY_FILE, ""), SUPPLIER_PAYMENT_SECTION)
    if f"`{payables}`" not in section:
        raise Undecidable(f"{POLICY_FILE} {SUPPLIER_PAYMENT_SECTION} does not name {payables} in backticks")
    # STOCK vendors: those the ledger itself shows raising a payable this period
    stock = {}
    for date, payee, narration, legs in purchases and entries or ():
        pass
    for date, payee, da, dv in purchases:
        stock.setdefault(payee, set()).add(da)
    stock = {p: next(iter(a)) for p, a in stock.items() if len(a) == 1}

    equity = frozenset(n for n, k in chart.items() if k == "equity")
    movements, _open, _outside = ledger_movements(public[LEDGER_FILE], bank_account, equity_accounts=equity,
                                                  period_start=period_start, period_end=period_end)
    rows, _sopen, _soutside = statement_rows(public[STATEMENT_FILE], period_start=period_start,
                                             period_end=period_end)
    out, notes = [], []
    for row in rows:
        if row.amount >= 0:
            continue
        named = _counterparties(row.description, parties)
        if len(named) != 1:
            continue
        payee = named[0]
        if payee not in stock:
            continue
        rail = _rail_of(row.description, bank_initiated=False)
        window = RAIL_WINDOW_DAYS.get(rail, MATCH_WINDOW_DAYS)
        cands = [m for m in movements if m.amount == row.amount and m.payee == payee
                 and _gap(m.date, row.date) <= window]
        if len(cands) != 1:
            if cands:
                notes.append(f"{row}: {len(cands)} ledger entries could be this payment")
            continue
        mov = cands[0]
        if len(mov.other_accounts) != 1:
            notes.append(f"{row}: the entry has {len(mov.other_accounts)} non-bank legs")
            continue
        got = mov.other_accounts[0]
        if got == payables:
            continue
        out.append(WrongAccountRepair(
            date=mov.date, payee=payee, amount=-row.amount, from_account=got, to_account=payables,
            bank_account=bank_account, narration=mov.narration, reference=row.reference,
            authority=(f"{VENDORS_FILE} books {payee}'s purchases to {stock[payee]}",
                       f"{ACCOUNTS_FILE} types {stock[payee]} as an asset",
                       f"{LEDGER_FILE} raises the payable in {payables} on the purchase entries for {payee}",
                       f"{POLICY_FILE} {SUPPLIER_PAYMENT_SECTION} records the payment to {payables}")))
    return tuple(out), tuple(notes), payables, dict(stock)
