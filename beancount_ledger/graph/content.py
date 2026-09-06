"""The content library the generator draws from: names, wording, shapes.

Nothing here decides anything. It is inert vocabulary — name stems and
suffixes in three styles, one narration template set per accounting rule,
the prompt templates and the policy document — so that `generate.py` holds
the structure of a world and this module holds only how it reads.

Two rules govern every string in this file, and `check_content()` asserts
both rather than leaving them to a downstream parse failure:

* **No commas in anything that reaches a CSV column.** The bank statement,
  the chart and the two master files are naive CSV, so a comma in a party
  name or a term would silently move a column rather than fail. Narrations
  are quoted Beancount fields and may carry one — "Office supplies, check
  1042" is the point of one.
* **ASCII, NFC, no quotes.** Payees and narrations are printed inside
  double-quoted Beancount strings and pass the submission boundary's
  string policy on the way back in.

The families exist so that two seeds do not read like the same bookkeeper
typed them, and so that one world mixes styles the way a real customer
ledger does: a geographic wholesaler, an industrial supplier and a family
firm on the same page.
"""

from __future__ import annotations

FAMILIES = ("geographic", "industrial", "personal")

# --------------------------------------------------------------------------
# name stems, by style family
# --------------------------------------------------------------------------

GEOGRAPHIC_STEMS = (
    "Bayside", "Beacon Hill", "Birchwood", "Blackrock", "Bridgeport", "Clearwater",
    "Coldbrook", "Copperfield", "Eastgate", "Fairhaven", "Glenmoor", "Granite Bay",
    "Greenfield", "Harborview", "Highfield", "Ironbridge", "Kingsford", "Lakeshore",
    "Larkspur", "Millbrook", "Northgate", "Oakhurst", "Pinecrest", "Redstone",
    "Riverbend", "Sandpoint", "Silverlake", "Stonegate", "Westmoor", "Whitmore",
)

INDUSTRIAL_STEMS = (
    "Anvil", "Apex", "Axiom", "Ballast", "Bellwether", "Caliper", "Cardinal",
    "Crucible", "Datum", "Ferrous", "Flintlock", "Foundry", "Gearworks", "Halyard",
    "Kinetic", "Lodestone", "Magneto", "Meridian", "Pinion", "Quadrant", "Regent",
    "Sextant", "Sprocket", "Tenon", "Torsion", "Truewell", "Vector", "Vulcan",
)

PERSONAL_STEMS = (
    "Ashcroft", "Bergstrom", "Calloway", "Delgado", "Ellsworth", "Farrow",
    "Gallagher", "Halloran", "Ibarra", "Jarreau", "Kowalski", "Lindqvist",
    "Marchetti", "Nakamura", "Okafor", "Pettersen", "Quintero", "Rasmussen",
    "Sorensen", "Thackeray", "Ueda", "Vasquez", "Whitcombe", "Yamashita",
    "Zabala", "Brennan", "Castellano", "Dumont",
)

STEMS = {
    "geographic": GEOGRAPHIC_STEMS,
    "industrial": INDUSTRIAL_STEMS,
    "personal": PERSONAL_STEMS,
}

# --------------------------------------------------------------------------
# suffixes, by the part the party plays
# --------------------------------------------------------------------------

TRADE_SUFFIXES = {
    "customer": ("Retail", "Wholesale", "Trading Co", "Distributors", "Markets",
                 "Outfitters", "Mercantile", "Stores", "Provisions", "Supply Group"),
    "inventory": ("Supplies", "Imports", "Distribution", "Wholesale Supply", "Trading",
                  "Components", "Materials Co", "Sourcing", "Merchants"),
    "rent": ("Property Group", "Realty", "Estates", "Property Partners", "Properties",
             "Property Holdings", "Asset Management"),
    "office": ("Office Supply", "Stationers", "Business Supply", "Office Works",
               "Paper and Print", "Copy Supply", "Workplace Supply"),
}

PERSONAL_SUFFIXES = {
    "customer": ("and Sons", "Brothers", "and Company", "Retail", "Trading",
                 "and Daughters", "Family Stores"),
    "inventory": ("and Sons Supply", "Brothers Wholesale", "and Company Imports",
                  "Supply", "Trading", "and Partners Distribution"),
    "rent": ("Property", "Estates", "and Sons Realty", "Property Holdings", "Land and Buildings"),
    "office": ("Stationers", "Office Supply", "Business Supply", "and Sons Stationery"),
}

COMPANY_STEMS = (
    "Alderbrook", "Ambervale", "Brightwater", "Cobblestone", "Driftwood", "Elmridge",
    "Fernbank", "Goldenrod", "Hollowfield", "Inglewood", "Juniper", "Kestrel",
    "Lantern Bay", "Marlowe", "Netherfield", "Orchard Hill", "Pemberton", "Quarrystone",
    "Rookwood", "Saltmarsh", "Thornbury", "Underhill", "Vantage Point", "Wrenfield",
)

COMPANY_SUFFIXES = (
    "Trading Co.", "Supply Co.", "Distributors", "Merchants", "Wholesale Co.",
    "Trading Partners", "Provisions Co.", "Supply Partners",
)

BANK_STEMS = (
    "Alderway", "Bellhaven", "Cobalt", "Dunmore", "Eastfield", "Fairmount",
    "Greylock", "Havenport", "Ironvale", "Juniper Ridge", "Keystone", "Longmeadow",
    "Merchants Row", "Northcliff", "Oakvale", "Pennwood", "Riverstone", "Southbank",
    "Thornhill", "Westbury",
)

BANK_SUFFIXES = (
    "Bank", "Savings Bank", "Community Bank", "Bank and Trust", "National Bank",
    "Commercial Bank", "State Bank",
)

CUSTOMER_TERMS = ("net 30", "net 45", "net 15", "net 30", "net 60")
INVENTORY_VENDOR_TERMS = ("net 30", "net 45", "net 30")
SERVICE_VENDOR_TERMS = ("due on receipt", "net 15", "due on receipt")

# Names the hand-authored world already uses. A generated world never
# reuses one, so a solver that memorised Alpine (it is in the calibration
# corpus) learns nothing transferable from the name alone.
RESERVED_NAMES = frozenset({
    "Alpine Trading Co.", "Harbor Freight Ltd", "Summit Wholesale", "Ridgeline Retail",
    "Northwind Supplies", "Cedar Property Group", "Office Depot", "Cascade Bank",
})

# --------------------------------------------------------------------------
# narration templates, one set per accounting rule
# --------------------------------------------------------------------------

NARRATIONS = {
    "sale": ("Sale {invoice}", "Goods sold on {invoice}", "Invoice {invoice} raised",
             "Sale of goods - {invoice}", "{invoice} goods despatched"),
    "sale_cost": ("Cost of goods sold on {invoice}", "Cost of sales - {invoice}",
                  "Goods shipped against {invoice} at cost", "Stock relieved for {invoice}"),
    "purchase": ("Purchase invoice {invoice} received", "Goods received on {invoice}",
                 "Stock purchase {invoice}", "Supplier invoice {invoice} booked"),
    "receipt_full": ("Customer payment for {invoice}", "Payment received settling {invoice}",
                     "Receipt against {invoice}", "{invoice} settled in full"),
    "receipt_partial": ("Partial payment against {invoice}", "Part payment received on {invoice}",
                        "Payment on account against {invoice}", "Instalment against {invoice}"),
    "vendor_payment": ("Payment of purchase invoice {invoice}", "Settlement of {invoice}",
                       "Supplier payment for {invoice}", "{invoice} paid"),
    "office": ("Office supplies", "Stationery and printer supplies", "Printer toner and paper",
               "Office consumables", "Packaging and office supplies", "Filing and desk supplies",
               "Shipping labels and envelopes"),
    "rent": ("{month} office rent", "{month} premises rent", "Rent for {month}",
             "{month} warehouse and office rent"),
    "prepayment": ("{month} rent prepaid", "Rent for {month} paid in advance",
                   "{month} premises rent settled early"),
    "bank_fee": ("Monthly account service charge", "Account maintenance charge",
                 "Monthly service fee", "Business account service charge"),
    # Only fees a domestic trader with no returned items would actually see
    # (a "foreign transaction fee" with no FX activity and a "returned item
    # fee" with no returned deposit read as fabricated).
    "bank_fee_extra": ("Wire transfer fee", "Cash handling fee", "Paper statement fee",
                       "Check printing fee", "ACH origination fee"),
}

CHEQUE_MEMO = "{memo}, check {number}"

PROMPTS = (
    "The {month} checking account statement has arrived and the month needs to be closed. Bring the "
    "ledger into agreement with the statement, following the bookkeeping policy. Write the corrected "
    "ledger back to ledger.beancount.",
    "{month} is being closed. Reconcile the ledger against the {month} checking account statement and "
    "correct the books in line with the bookkeeping policy. Save the corrected ledger as ledger.beancount.",
    "Month-end close for {month}. The bank statement is in; the ledger is not yet in agreement with it. "
    "Work through the differences under the bookkeeping policy and write the corrected ledger back to "
    "ledger.beancount.",
    "Please reconcile the {month} checking account. Compare the statement with the ledger, apply the "
    "bookkeeping policy to whatever differs and write the corrected ledger back to ledger.beancount.",
)

# --------------------------------------------------------------------------
# the policy document
# --------------------------------------------------------------------------

POLICY_TEMPLATE = """# {company} - Bookkeeping Policy

## Bank service charges
Fees levied directly by the bank (monthly service charges, wire fees, returned
item fees) are recorded to `Expenses:BankFees` on the date the bank applies them.

## Customer receipts
Cash received from a customer reduces `Assets:AR`. Where the deposit reference
identifies a sales invoice, it is applied against that invoice.

## Payments to suppliers
The `default_account` a supplier carries in the vendor master is where that
supplier's purchases are booked when they arrive. It is not where a payment to
that supplier lands. Where a supplier's purchases are booked to an asset
account, the goods were taken into that account when they were received and a
payable was raised for them at the same time, so cash paid to that supplier
afterwards settles the payable and is recorded to `Liabilities:AP`. Where a
supplier's purchases are booked to an expense account, no payable is raised:
the payment is the expense, and it is recorded to that supplier's own
`default_account` on the day it is paid, except where it is paid ahead of the
period it covers, which the prepayments section below governs.

## Outstanding checks
A check that has been issued and recorded in the ledger but has not cleared the
bank as at the statement cut-off date remains recorded. It is a timing
difference and is listed as an outstanding item in the reconciliation. It is
never removed or adjusted.

## Deposits in transit
Cash recorded as received in the ledger that does not appear on the bank
statement until after the cut-off date is likewise a timing difference and is
listed as an outstanding item.

## Dates
An entry carries the date of the transaction — the day a check was issued, a
receipt was received or an invoice was raised — never the date the bank
processed it. A ledger date that differs from the statement's date for the
same item is not an error and is not to be changed.

The bank processes a transaction on or after the day it happens, so for a
customer or vendor movement the ledger date is never later than the
statement's date for the same item.

An item the books do not carry at all has no transaction date to keep. The
statement's date is then the only date in evidence, so an entry added for a
statement row the ledger is missing is posted on the date the bank shows.

## Matching the statement to the ledger
A statement row and a ledger entry of the same amount and the same
counterparty, dated within the clearing window for the rail the row names,
are the same transaction and are treated as one item — not as two that
happen to agree.

## Prepayments
Amounts paid before the period they relate to are recorded to
`Assets:Prepayments` and released to expense in the period they cover. Rent
paid in one month for the following month is a prepayment, not an expense of
the month it was paid.

## Sales tax
{company} collects sales tax from customers on sales and owes it to the state.
Purchases of goods for resale are exempt, so no tax is recoverable on the
purchase side.

## Suspense accounts
{company} does not operate a suspense or plug account. Every posting is made to
the account that reflects the underlying transaction.
"""

# --------------------------------------------------------------------------
# the one check this module owes
# --------------------------------------------------------------------------

# Strings that reach a CSV column (party names, terms) must also be
# comma-free; narrations and prompts are prose in quoted fields and may
# carry a comma — "Office supplies, check 1042" is the point of one.
_CSV_POOLS = (
    GEOGRAPHIC_STEMS, INDUSTRIAL_STEMS, PERSONAL_STEMS, COMPANY_STEMS, COMPANY_SUFFIXES,
    BANK_STEMS, BANK_SUFFIXES, CUSTOMER_TERMS, INVENTORY_VENDOR_TERMS, SERVICE_VENDOR_TERMS,
) + tuple(TRADE_SUFFIXES.values()) + tuple(PERSONAL_SUFFIXES.values())

_PROSE_POOLS = (PROMPTS, (CHEQUE_MEMO,)) + tuple(NARRATIONS.values())


def check_content() -> list[str]:
    """Every string this module can put into a CSV column or a quoted
    Beancount field is ASCII and quote-free, and every string that reaches
    a CSV column is comma-free as well. A defect here would move a
    statement column rather than fail a parse, so it is checked.
    """
    problems: list[str] = []
    for pool, csv in [(p, True) for p in _CSV_POOLS] + [(p, False) for p in _PROSE_POOLS]:
        for value in pool:
            if not isinstance(value, str):
                problems.append(f"{value!r} is not a string")
                continue
            if not value.isascii():
                problems.append(f"{value!r} is not ASCII")
            if csv and "," in value:
                problems.append(f"{value!r} contains a comma")
            if '"' in value or "\\" in value:
                problems.append(f"{value!r} contains a quote or backslash")
            if value != value.strip():
                problems.append(f"{value!r} is not stripped")
    for family in FAMILIES:
        if family not in STEMS:
            problems.append(f"family {family} has no stems")
        elif len(set(STEMS[family])) != len(STEMS[family]):
            problems.append(f"family {family} repeats a stem")
    for role in ("customer", "inventory", "rent", "office"):
        if role not in TRADE_SUFFIXES or role not in PERSONAL_SUFFIXES:
            problems.append(f"role {role} has no suffixes")
    for section in ("## Bank service charges", "## Customer receipts", "## Payments to suppliers",
                    "## Outstanding checks", "## Deposits in transit", "## Dates",
                    "## Matching the statement to the ledger",
                    "## Prepayments", "## Sales tax", "## Suspense accounts"):
        if section not in POLICY_TEMPLATE:
            problems.append(f"the policy template lacks {section!r}")
    return problems


def content_digest() -> str:
    """The identity of the content library: every module-level table, in
    canonical bytes. A change to any pool changes the draws of every seed,
    so a change here REQUIRES a GENERATOR_VERSION bump — the property suite
    pins this digest per version."""
    from ..candidate.canonical import canonical_bytes, domain_digest

    tables = {}
    for name, value in sorted(globals().items()):
        if name.isupper() and isinstance(value, (str, tuple, list, dict, int)):
            tables[name] = value
    return domain_digest(b"piv:generator-content:v1" + bytes([0]), canonical_bytes(tables))
