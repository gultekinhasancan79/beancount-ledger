"""The private half of the shared repair key (Codex T42 §3, Q1).

`identify.repair_key(repair)` projects what the PUBLIC-ONLY checker believes
a repair is. `planted_key(spec)` here projects what the GRAPH planted, into
the same tuple type, so that "the checker found the planted items" is one
comparison performed in one place — the sweep, the generator's property 7 and
the differential all import this rather than each inventing its own weaker
notion of repair equality.

    (kind, date, postings, counterparty, booked bank amount, expected copies)

Read `identify.repair_key` for the field-by-field contract, including the
closed list of fields that are deliberately NOT part of item identity and why
it matches the scorer's `RETAINED_FIELDS`. Two things are worth repeating
here because they are where the two sides could silently drift:

*   the DATE. A planted omission carries the bank's date (contract change B:
    the recognition date is not in evidence, and `## Dates` tells the agent to
    post the entry on the date the statement shows), which is exactly the date
    the checker reads off the row. A planted alteration or duplicate carries
    the booked entry's own date, which is exactly the date the checker reads
    off the ledger. The scorer's eligibility predicate uses the same field, so
    a mismatch here is a mismatch the reward would actually pay out on.

*   the COUNTERPARTY. Only a name the mounted `customers.csv` / `vendors.csv`
    carries is a counterparty; the bank is not a master-file party, so a bank
    charge is `None` on both sides. Passing `master_names` is therefore not
    optional in anger — the default treats every payee as unlisted, which is
    right for a caller that has no master files but wrong for one that does.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal

from beancount_ledger.graph.derive import planted_key as _planted_key
from beancount_ledger.graph.identify import (
    CUSTOMERS_FILE,
    UNDERIVABLE,
    VENDORS_FILE,
    repair_key,
)

__all__ = ["planted_key", "repair_key", "master_names", "PUBLIC_KIND", "UNDERIVABLE"]

# The planted kinds, under the names the public checker uses for them.
PUBLIC_KIND = {"omit": "missing_entry", "alter": "wrong_amount", "duplicate": "duplicate"}


def master_names(public: dict) -> frozenset:
    """Every customer and vendor the mounted files list, by name."""
    out = set()
    for file_name, column in ((CUSTOMERS_FILE, "customer"), (VENDORS_FILE, "vendor")):
        for record in csv.DictReader(io.StringIO(public.get(file_name, ""))):
            name = (record.get(column) or "").strip()
            if name:
                out.add(name)
    return frozenset(out)


def planted_key(spec, master_names: frozenset = frozenset(), *, bank_account: str = "") -> tuple:
    """The truth side, from `graph.derive.planted_key` — implemented there
    independently of `identify.repair_key` (Codex T43 §2, Q3: no shared
    serializer), and used by the mint gate as well as by every test."""
    if not bank_account:
        raise ValueError("planted_key needs the bank account name")
    return _planted_key(spec, master_names, bank_account=bank_account)
