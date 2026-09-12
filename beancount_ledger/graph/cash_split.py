"""The `cash_application` family's split map, and the canonical structural
description that keeps it honest.

Decision 2 rules both halves:

    Split by structural-template family, then keep every descendant together.
    Freeze a template-to-split map before drawing instances: 60% train, 20%
    development, 20% evaluation, stratified across the three mechanisms. All
    company-month instantiations, paired variants and later profiles derived
    from a template inherit its assignment. Preserve that map across key
    rotation and descendant versions.

    Different template names are insufficient. Check canonical structural
    descriptions for aliases across splits, stripping cosmetic names and
    absolute dates while preserving settlement relationships and ordering.
    This prevents a renamed or rescaled sibling becoming "held out."

**This does not make the public generator grammar secret.** Every rule in
this module — the stripping, the ranking, the refinement, the quotas — is
published source, and so is the fold the agent's own answer has to match. The
alias check exists to stop a held-out template from being a renamed or
rescaled twin of a trained one; it is a POPULATION-hygiene device, not an
obscurity device, and nothing here is load-bearing for the difficulty of a
single case. An agent that reads this file learns how the split was drawn and
learns nothing about the answer to any instance.

HOW THE CANONICAL DESCRIPTION IS BUILT

    cosmetic names     customer, invoice, receipt and credit-note ids are
                       discarded and replaced by SLOTS, assigned by the
                       structure itself rather than by declaration order;
    absolute dates     replaced by their RANK in the template's own sorted
                       set of distinct dates — ordering preserved exactly,
                       calendar position discarded;
    amounts            replaced by their RANK in the sorted set of distinct
                       amounts. That preserves the ORDER of the amounts and
                       equality between two individual amounts — and nothing
                       more. It does NOT preserve SUMS: a rank carries no
                       arithmetic, and a strictly increasing rescale need not
                       be affine. So the exact-subset-sum coincidence that
                       gate (o)'s amount-only branching enumerates ("every
                       exact subset of the payer's open balances", declared
                       in `cash_manifest.baseline_catalogue_view`) is NOT
                       part of the canonical form. Open balances 100/200/300
                       with a receipt of 300, which IS an exact subset sum,
                       and open balances 100/201/999 with a receipt of 999,
                       which is not, canonicalise to the same bytes. The
                       error runs in the COARSE direction — the two count as
                       aliases — so the cross-split check refuses pairs it
                       did not strictly have to. That is the safe direction
                       for split hygiene and is not a way for a sibling to
                       slip across; it is the reason this description is not
                       a statement about accounting equivalence. The suite's
                       `test_the_canonical_form_does_not_preserve_subset_sums`
                       pins it as the counterexample above;
    settlement         kept in full: who owns what, which receipt or note
                       names which invoice, in which PRINTED position, for
                       which amount rank, with which settles flag and
                       deduction rank; the plants, by kind, on their targets;
    mechanism          NOT part of the canonical structure. It is a declared
                       classification, so folding it in would let a renamed
                       stratum label carry an otherwise identical structure
                       across the split boundary. It is recorded beside the
                       structure, never inside it.

Slots come from 1-WL colour refinement over that name-free graph, then a
minimising search over whatever ties the refinement leaves. The search is
BOUNDED: a template whose tied classes would need more than
`MAX_LABELLING_PERMUTATIONS` orderings raises `StructureTooAmbiguous` rather
than returning a labelling that depends on declaration order. That is the
same discipline as the 256-reading bound in gate (o) — exceeding the bound
means the check was incomplete, not that the candidate passed it.
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from ..candidate.canonical import canonical_bytes, domain_digest
from .cash_identity import BOUNDED_V1, MECHANISMS, SPLITS, ConstructionIdentity, GenerationProfile, identity

_STRUCTURE_DOMAIN = b"piv:cash-application:canonical-structure:v1\0"
_SPLIT_MAP_DOMAIN = b"piv:cash-application:split-map:v1\0"

#: The canonical structural description's own version. A change in what is
#: stripped or preserved is a change in what "alias" means, so it moves here
#: and re-preflights every record that bound a structure digest.
STRUCTURE_SCHEMA = 1

#: The split map's declaration version. Independent of
#: `FAMILY_GENERATOR_VERSION` on purpose: the map must survive descendant
#: versions of the generator, so no generator version enters its digest.
SPLIT_MAP_SCHEMA = 1

#: 60 / 20 / 20, as integer weights out of five. Stated as integers because
#: a float share has no canonical identity and these numbers are signed.
SPLIT_WEIGHTS = (("train", 3), ("development", 1), ("evaluation", 1))
SPLIT_DENOMINATOR = sum(weight for _, weight in SPLIT_WEIGHTS)

#: The refinement is bounded twice: rounds, and the tie-breaking search.
MAX_REFINEMENT_ROUNDS = 8
MAX_LABELLING_PERMUTATIONS = 5040

#: The evidence kinds a receipt may carry.
EVIDENCE_KINDS = ("advice", "reference", "bare")


class StructureError(ValueError):
    """A structural template that cannot be described."""


class StructureTooAmbiguous(StructureError):
    """Refinement left more ties than the bounded search may resolve. The
    canonicalisation is INCOMPLETE for this template; it did not pass."""


class StructuralAliasError(ValueError):
    """A candidate whose canonical structure already appears in another
    split: a renamed or rescaled sibling trying to become held out."""


class SplitMapError(ValueError):
    """A split map that may not exist, or a family it does not carry."""


# --------------------------------------------------------------------------
# the declared structural template
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class InvoiceShape:
    invoice_id: str                  # cosmetic
    customer: str                    # cosmetic
    invoice_date: str                # absolute, ISO
    due_date: str                    # absolute, ISO
    original_amount: str             # decimal string
    open_balance: str                # decimal string; the balance ENTERING the period
    raised_in_period: bool = False


@dataclass(frozen=True)
class AdviceLineShape:
    invoice_id: str
    amount: str
    settles_invoice: bool = True
    deduction: str = "0.00"


@dataclass(frozen=True)
class ReceiptShape:
    receipt_id: str                  # cosmetic
    customer: str                    # cosmetic
    bank_date: str                   # absolute, ISO
    amount: str
    evidence: str = "advice"         # one of EVIDENCE_KINDS
    references: tuple = ()           # invoice ids the statement reference names, in PRINTED order
    advice_lines: tuple = ()         # AdviceLineShape, in the advice's own order


@dataclass(frozen=True)
class CreditNoteShape:
    credit_note_id: str              # cosmetic
    customer: str                    # cosmetic
    date: str                        # absolute, ISO
    invoice_id: str                  # the invoice the note names
    gross_amount: str


@dataclass(frozen=True)
class PlantShape:
    kind: str                        # "omission" | "transposition" | "write_off_omission" | ...
    target: str                      # the receipt, credit-note or invoice id it is planted on


@dataclass(frozen=True)
class StructuralTemplate:
    """One structural template: the recipe a company-month is instantiated
    from. Two instantiations of it, and both variants of each, inherit its
    family's split assignment."""

    family: str
    version: int
    mechanism: str
    invoices: tuple = ()
    receipts: tuple = ()
    credit_notes: tuple = ()
    plants: tuple = ()

    def __post_init__(self):
        if not isinstance(self.family, str) or not self.family.strip():
            raise StructureError("a template family is a non-empty string")
        if type(self.version) is not int or self.version < 1:
            raise StructureError(f"template version is {self.version!r}: an int >= 1")
        if self.mechanism not in MECHANISMS:
            raise StructureError(f"mechanism is {self.mechanism!r}, not one of {list(MECHANISMS)}")
        if not self.invoices:
            raise StructureError(f"{self.family}/{self.version} declares no invoices")
        for receipt in self.receipts:
            if receipt.evidence not in EVIDENCE_KINDS:
                raise StructureError(f"{receipt.receipt_id} evidence is {receipt.evidence!r}, "
                                     f"not one of {list(EVIDENCE_KINDS)}")


# --------------------------------------------------------------------------
# canonical structural description
# --------------------------------------------------------------------------

def _money(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise StructureError(f"{value!r} is not a decimal amount")


def _rank_map(values) -> dict:
    return {value: position for position, value in enumerate(sorted(set(values)))}


@dataclass
class _Node:
    kind: str                        # "customer" | "invoice" | "receipt" | "credit"
    key: str                         # the cosmetic id, used only to wire edges
    base: tuple                      # the name-free, date-free, scale-free own colour
    edges: list = field(default_factory=list)   # (label, other node index)


def _graph(template: StructuralTemplate) -> list:
    """The template as a name-free, date-free, scale-free graph."""
    dates, amounts = [], []
    for inv in template.invoices:
        dates += [inv.invoice_date, inv.due_date]
        amounts += [_money(inv.original_amount), _money(inv.open_balance)]
    for rec in template.receipts:
        dates.append(rec.bank_date)
        amounts.append(_money(rec.amount))
        for line in rec.advice_lines:
            amounts += [_money(line.amount), _money(line.deduction)]
    for note in template.credit_notes:
        dates.append(note.date)
        amounts.append(_money(note.gross_amount))
    date_rank, amount_rank = _rank_map(dates), _rank_map(amounts)

    plants_on: dict = {}
    for plant in template.plants:
        plants_on.setdefault(plant.target, []).append(plant.kind)

    def planted(key) -> tuple:
        return tuple(sorted(plants_on.get(key, ())))

    nodes: list = []
    index: dict = {}

    def add(kind, key, base) -> int:
        if (kind, key) in index:
            raise StructureError(f"duplicate {kind} id {key!r} in {template.family}/{template.version}")
        index[(kind, key)] = len(nodes)
        nodes.append(_Node(kind, key, base))
        return index[(kind, key)]

    customers = []
    for holder in list(template.invoices) + list(template.receipts) + list(template.credit_notes):
        if holder.customer not in customers:
            customers.append(holder.customer)
    for name in customers:
        add("customer", name, ("customer",))
    for inv in template.invoices:
        add("invoice", inv.invoice_id,
            ("invoice", date_rank[inv.invoice_date], date_rank[inv.due_date],
             amount_rank[_money(inv.original_amount)], amount_rank[_money(inv.open_balance)],
             bool(inv.raised_in_period), planted(inv.invoice_id)))
    for rec in template.receipts:
        add("receipt", rec.receipt_id,
            ("receipt", date_rank[rec.bank_date], amount_rank[_money(rec.amount)], rec.evidence,
             len(rec.references), len(rec.advice_lines), planted(rec.receipt_id)))
    for note in template.credit_notes:
        add("credit", note.credit_note_id,
            ("credit", date_rank[note.date], amount_rank[_money(note.gross_amount)],
             planted(note.credit_note_id)))

    def link(a, b, label):
        nodes[a].edges.append((label, b))
        nodes[b].edges.append((("~",) + label, a))

    def invoice_at(invoice_id):
        try:
            return index[("invoice", invoice_id)]
        except KeyError:
            raise StructureError(f"{template.family}/{template.version} names unknown invoice {invoice_id!r}")

    for inv in template.invoices:
        link(index[("invoice", inv.invoice_id)], index[("customer", inv.customer)], ("owns",))
    for rec in template.receipts:
        link(index[("receipt", rec.receipt_id)], index[("customer", rec.customer)], ("paid_by",))
        for position, invoice_id in enumerate(rec.references):
            link(index[("receipt", rec.receipt_id)], invoice_at(invoice_id), ("reference", position))
        for position, line in enumerate(rec.advice_lines):
            link(index[("receipt", rec.receipt_id)], invoice_at(line.invoice_id),
                 ("advice", position, amount_rank[_money(line.amount)], bool(line.settles_invoice),
                  amount_rank[_money(line.deduction)]))
    for note in template.credit_notes:
        link(index[("credit", note.credit_note_id)], index[("customer", note.customer)], ("issued_to",))
        link(index[("credit", note.credit_note_id)], invoice_at(note.invoice_id), ("credits",))

    known = {key for _, key in index}
    unknown = sorted({p.target for p in template.plants} - known)
    if unknown:
        raise StructureError(f"{template.family}/{template.version} plants on unknown targets {unknown}")
    return nodes


def _refine(nodes: list) -> list:
    """1-WL colour refinement. Returns one colour per node, as a small int."""
    colours = [hash_of(node.base) for node in nodes]
    for _ in range(MAX_REFINEMENT_ROUNDS):
        signature = [(colours[i], tuple(sorted((label, colours[j]) for label, j in node.edges)))
                     for i, node in enumerate(nodes)]
        fresh = [hash_of(s) for s in signature]
        if fresh == colours:
            break
        colours = fresh
    return colours


def hash_of(value) -> int:
    """A stable small int for a hashable structural signature. SHA-256, not
    Python's salted `hash()`: a colour that changed with PYTHONHASHSEED would
    make the canonical form ambient."""
    return int.from_bytes(hashlib.sha256(repr(value).encode("utf-8")).digest()[:8], "big")


def _labelling(nodes: list, colours: list) -> dict:
    """Node index -> slot, per kind. Nodes are ordered by colour; whatever
    ties the refinement leaves are resolved by taking the ordering that
    MINIMISES the canonical bytes, over a bounded search."""
    by_kind: dict = {}
    for position, node in enumerate(nodes):
        by_kind.setdefault(node.kind, []).append(position)

    groups: list = []                  # tied classes, in a colour-determined order
    order: dict = {}                   # kind -> list of node indices, ties as placeholders
    for kind in sorted(by_kind):
        members = sorted(by_kind[kind], key=lambda i: (colours[i], i))
        laid: list = []
        run: list = []
        for position in members + [None]:
            if run and (position is None or colours[position] != colours[run[0]]):
                if len(run) == 1:
                    laid.append(run[0])
                else:
                    laid.append(("tie", len(groups)))
                    groups.append(tuple(run))
                run = []
            if position is not None:
                run.append(position)
        order[kind] = laid

    total = 1
    for group in groups:
        total *= _factorial(len(group))
        if total > MAX_LABELLING_PERMUTATIONS:
            raise StructureTooAmbiguous(
                f"colour refinement left tied classes needing more than {MAX_LABELLING_PERMUTATIONS} orderings; "
                f"the canonical structural description is INCOMPLETE for this template, which means the "
                f"cross-split alias check did not run — not that the template passed it")

    best_key, best = None, None
    for choice in itertools.product(*(itertools.permutations(group) for group in groups)):
        slots: dict = {}
        for kind, laid in order.items():
            position = 0
            for entry in laid:
                members = choice[entry[1]] if isinstance(entry, tuple) else (entry,)
                for node in members:
                    slots[node] = position
                    position += 1
        key = canonical_bytes(_form(nodes, slots))
        if best_key is None or key < best_key:
            best_key, best = key, slots
    return best


def _factorial(n: int) -> int:
    out = 1
    for i in range(2, n + 1):
        out *= i
    return out


def _form(nodes: list, slots: dict) -> dict:
    """The canonical structural description, given a labelling."""
    rows: dict = {}
    for position, node in enumerate(nodes):
        entry = {"slot": slots[position], "own": list(node.base[1:]),
                 "edges": sorted([list(label), nodes[other].kind, slots[other]]
                                 for label, other in node.edges if not label[0] == "~")}
        rows.setdefault(node.kind, []).append(entry)
    return {"schema": STRUCTURE_SCHEMA,
            **{kind: sorted(entries, key=lambda e: e["slot"]) for kind, entries in sorted(rows.items())}}


def canonical_structure(template: StructuralTemplate) -> dict:
    """The template with cosmetic names and absolute dates stripped, and
    settlement relationships and ordering preserved. The declared mechanism
    is NOT in here (see the module docstring)."""
    nodes = _graph(template)
    return _form(nodes, _labelling(nodes, _refine(nodes)))


def structure_digest(template: StructuralTemplate) -> str:
    return domain_digest(_STRUCTURE_DOMAIN, canonical_bytes(canonical_structure(template)))[:32]


# --------------------------------------------------------------------------
# the split map
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TemplateFamily:
    """One entry of the frozen roster: a family name and the mechanism
    stratum it is stratified within."""

    name: str
    mechanism: str

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise SplitMapError("a template family name is a non-empty string")
        if self.mechanism not in MECHANISMS:
            raise SplitMapError(f"{self.name}: mechanism {self.mechanism!r} is not one of {list(MECHANISMS)}")


@dataclass(frozen=True)
class SplitMap:
    """Template family -> split, frozen before any instance is drawn.

    The key is the family NAME alone. Its version is not part of the key, so
    a descendant version inherits the assignment; neither is the evaluator
    secret, the rotation id or `FAMILY_GENERATOR_VERSION`, so the map — and
    its digest — survive key rotation and generator descendants. Every
    company-month instantiation and both variants of every pair inherit the
    family's split by construction, because they carry the family in their
    construction identity and read their split from here.
    """

    assignments: tuple               # ((family, mechanism, split), ...) sorted by family

    def __post_init__(self):
        names = [row[0] for row in self.assignments]
        if len(set(names)) != len(names):
            raise SplitMapError(f"the split map assigns a family twice: {sorted(names)}")
        if list(names) != sorted(names):
            raise SplitMapError("the split map is not in canonical family order")
        for _, mechanism, split in self.assignments:
            if mechanism not in MECHANISMS:
                raise SplitMapError(f"unknown mechanism {mechanism!r}")
            if split not in SPLITS:
                raise SplitMapError(f"unknown split {split!r}")

    # -- lookup -----------------------------------------------------------
    def split_of(self, family: str) -> str:
        for name, _, split in self.assignments:
            if name == family:
                return split
        raise SplitMapError(f"template family {family!r} is not in the frozen split map; a family must be "
                            f"declared in the roster and the map re-sealed before any instance is drawn")

    def mechanism_of(self, family: str) -> str:
        for name, mechanism, _ in self.assignments:
            if name == family:
                return mechanism
        raise SplitMapError(f"template family {family!r} is not in the frozen split map")

    def families(self) -> tuple:
        return tuple(name for name, _, _ in self.assignments)

    def stratum(self, mechanism: str) -> tuple:
        return tuple(row for row in self.assignments if row[1] == mechanism)

    def counts(self) -> dict:
        """mechanism -> split -> how many families."""
        out = {m: {s: 0 for s in SPLITS} for m in MECHANISMS}
        for _, mechanism, split in self.assignments:
            out[mechanism][split] += 1
        return out

    def view(self) -> dict:
        return {"schema": SPLIT_MAP_SCHEMA,
                "weights": [[name, weight] for name, weight in SPLIT_WEIGHTS],
                "assignments": [list(row) for row in self.assignments]}

    def digest(self) -> str:
        return domain_digest(_SPLIT_MAP_DOMAIN, canonical_bytes(self.view()))[:32]

    @classmethod
    def from_view(cls, view: dict) -> "SplitMap":
        """The inverse of `view()`, for a map read back from a checked-in
        freeze. The schema and the weights are CHECKED rather than assumed: a
        map apportioned under other weights is not this map, and silently
        adopting its rows would be the reassignment the freeze exists to
        prevent."""
        if not isinstance(view, dict):
            raise SplitMapError("a split-map view is a mapping")
        if view.get("schema") != SPLIT_MAP_SCHEMA:
            raise SplitMapError(f"the frozen map declares schema {view.get('schema')!r}, "
                                f"not {SPLIT_MAP_SCHEMA}")
        weights = [[name, weight] for name, weight in SPLIT_WEIGHTS]
        if view.get("weights") != weights:
            raise SplitMapError(f"the frozen map was sealed under weights {view.get('weights')!r}, not "
                                f"today's {weights}: re-apportioning it here would move assignments")
        rows = view.get("assignments")
        if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != 3 for row in rows):
            raise SplitMapError("a frozen map's assignments are [family, mechanism, split] triples")
        return cls(tuple(tuple(row) for row in rows))

    # -- sealing ----------------------------------------------------------
    @classmethod
    def seal(cls, roster, previous: "SplitMap | None" = None) -> "SplitMap":
        """Freeze `roster` into a map, carrying every assignment `previous`
        already made VERBATIM.

        Extension is therefore monotone: a family that has a split keeps it
        for the life of the family, whatever else joins the roster. New
        families are apportioned within their mechanism stratum by largest
        remainder against the 3:1:1 weights, so each stratum's counts stay
        within one of its exact 60/20/20 share. Order within a stratum is the
        roster's declaration order, which is a frozen, auditable declaration
        rather than anything drawn.
        """
        roster = tuple(roster)
        names = [entry.name for entry in roster]
        if len(set(names)) != len(names):
            raise SplitMapError(f"the roster declares a family twice: {sorted(names)}")
        kept = {name: (mechanism, split) for name, mechanism, split in (previous.assignments if previous else ())}
        for entry in roster:
            if entry.name in kept and kept[entry.name][0] != entry.mechanism:
                raise SplitMapError(f"{entry.name} was sealed under mechanism {kept[entry.name][0]!r} and the "
                                    f"roster now says {entry.mechanism!r}: a stratum change is a new family")
        missing = sorted(set(kept) - set(names))
        if missing:
            raise SplitMapError(f"the roster drops already-sealed families {missing}: a sealed assignment is "
                                f"frozen for the life of the family, so a family may be added but never removed")
        assignments = {name: (mechanism, split) for name, (mechanism, split) in kept.items()}
        for mechanism in MECHANISMS:
            counts = {split: 0 for split in SPLITS}
            for _, (owner, split) in assignments.items():
                if owner == mechanism:
                    counts[split] += 1
            for entry in roster:
                if entry.mechanism != mechanism or entry.name in assignments:
                    continue
                total = sum(counts.values())
                deficits = {split: weight * (total + 1) - SPLIT_DENOMINATOR * counts[split]
                            for split, weight in SPLIT_WEIGHTS}
                chosen = max(SPLITS, key=lambda s: (deficits[s], -SPLITS.index(s)))
                counts[chosen] += 1
                assignments[entry.name] = (mechanism, chosen)
        return cls(tuple(sorted((name, mechanism, split)
                                for name, (mechanism, split) in assignments.items())))


#: THE SHIPPED ANCHOR of "frozen for the life of the family".
#:
#: `seal` is monotone only against a `previous` map. With no `previous` it
#: apportions the WHOLE roster from scratch in declaration order, so a single
#: edit that both adds and REORDERS families would silently reassign the old
#: ones — the only alarm being a moved split-map digest that re-preflights
#: everything after the fact. So the assignments already made are checked in
#: here, verbatim, and the seal below carries them. Phase B appends to
#: `TEMPLATE_ROSTER`, re-seals, and copies the resulting rows into this tuple;
#: from then on a family's split is frozen by a line of source rather than by
#: a procedure somebody has to remember. `tests/cash_split_freeze.json` holds
#: the same map as external evidence, in the shape `tests/legacy_freeze.json`
#: uses, and the battery fails if either side moves without the other.
#:
#: Written in phase B from the seal of the fifteen-family roster below. From
#: here on, appending a family and re-sealing cannot move any of these fifteen
#: — `seal` carries `previous` verbatim and refuses a roster that drops a
#: sealed family or moves one between strata.
FROZEN_ASSIGNMENTS: tuple = (
    ("ar-coldharbour", "advice_residue", "evaluation"),
    ("ar-quillmarsh", "advice_residue", "train"),
    ("ar-saltgrave", "advice_residue", "train"),
    ("ar-tenterhook", "advice_residue", "development"),
    ("ar-wickenhall", "advice_residue", "train"),
    ("cr-ashenford", "credit_residue", "train"),
    ("cr-brindlecote", "credit_residue", "train"),
    ("cr-gallowtree", "credit_residue", "train"),
    ("cr-oysterbank", "credit_residue", "evaluation"),
    ("cr-pikestaff", "credit_residue", "development"),
    ("fc-harrowfield", "fallback_continuation", "evaluation"),
    ("fc-lintelgate", "fallback_continuation", "train"),
    ("fc-marlowbridge", "fallback_continuation", "train"),
    ("fc-quarrymill", "fallback_continuation", "development"),
    ("fc-sedgewick", "fallback_continuation", "train"),
)

FROZEN_SPLIT_MAP = SplitMap(FROZEN_ASSIGNMENTS)

#: The frozen roster: fifteen structural-template families, five per mechanism
#: stratum, declared in phase B before any instance is drawn.
#:
#: NAMES AND MECHANISMS ONLY. The SHAPE each family stands for — how many
#: customers, how many invoices are carried and how many raised in the month,
#: how many receipts, which of them carry an advice, where the two plants sit
#: — is declared in `graph/cash_construct.SHAPES`, keyed by these names.
#: Keeping the shape out of this module is what lets the map be sealed without
#: importing the construction path, and `tests/test_cash_construction.py`
#: asserts the two lists agree in BOTH directions, so a family can neither be
#: sealed without a recipe nor drawn without a split.
#:
#: Five per stratum apportions to exactly 3 train / 1 development / 1
#: evaluation under the 3:1:1 weights — decision 2's 60/20/20 exactly, not by
#: rounding. Extension stays monotone: a later phase may append families and
#: re-seal, and every assignment below keeps its split.
TEMPLATE_ROSTER: tuple = (
    TemplateFamily("fc-sedgewick", "fallback_continuation"),
    TemplateFamily("fc-quarrymill", "fallback_continuation"),
    TemplateFamily("fc-lintelgate", "fallback_continuation"),
    TemplateFamily("fc-harrowfield", "fallback_continuation"),
    TemplateFamily("fc-marlowbridge", "fallback_continuation"),
    TemplateFamily("cr-gallowtree", "credit_residue"),
    TemplateFamily("cr-pikestaff", "credit_residue"),
    TemplateFamily("cr-brindlecote", "credit_residue"),
    TemplateFamily("cr-oysterbank", "credit_residue"),
    TemplateFamily("cr-ashenford", "credit_residue"),
    TemplateFamily("ar-quillmarsh", "advice_residue"),
    TemplateFamily("ar-tenterhook", "advice_residue"),
    TemplateFamily("ar-wickenhall", "advice_residue"),
    TemplateFamily("ar-coldharbour", "advice_residue"),
    TemplateFamily("ar-saltgrave", "advice_residue"),
)

SPLIT_MAP = SplitMap.seal(TEMPLATE_ROSTER, previous=FROZEN_SPLIT_MAP)


# --------------------------------------------------------------------------
# the cross-split alias check
# --------------------------------------------------------------------------

class StructureLedger:
    """Append-only canonical structure -> (family, split).

    A candidate whose canonical structure already appears under ANOTHER split
    is refused: that is a renamed or rescaled sibling trying to become held
    out. The same structure under the SAME split is fine and expected — a
    descendant version, a second company-month, the pair's other variant.
    """

    def __init__(self, split_map: SplitMap = SPLIT_MAP):
        self.split_map = split_map
        self._by_structure: dict = {}
        self._admitted: list = []

    def admit(self, template: StructuralTemplate) -> str:
        """Register `template`, or refuse it. Returns its structure digest."""
        split = self.split_map.split_of(template.family)
        digest = structure_digest(template)
        prior = self._by_structure.get(digest)
        if prior is not None and prior[1] != split:
            raise StructuralAliasError(
                f"{template.family}/{template.version} is in {split!r} and its canonical structure already "
                f"appears in {prior[1]!r} as {prior[0]!r}: cosmetic names and absolute dates are stripped "
                f"before the comparison, so a renamed or rescaled sibling cannot become held out")
        self._by_structure.setdefault(digest, (template.family, split))
        self._admitted.append((template.family, template.version, digest, split))
        return digest

    def entries(self) -> tuple:
        return tuple(self._admitted)

    def structures(self) -> dict:
        return dict(self._by_structure)


def identity_for(population: str, template: StructuralTemplate, company_month_index: int,
                 profile: GenerationProfile = BOUNDED_V1, split_map: SplitMap = SPLIT_MAP) -> ConstructionIdentity:
    """A construction identity whose split is READ FROM the frozen map rather
    than restated by the caller.

    This is how "all company-month instantiations, paired variants and later
    profiles derived from a template inherit its assignment" is enforced
    rather than hoped for: there is no argument here that could disagree with
    the map, and a family the map does not carry cannot produce an identity
    at all."""
    return identity(population=population, split=split_map.split_of(template.family),
                    template_family=template.family, template_version=template.version,
                    company_month_index=company_month_index, profile=profile)


__all__ = [
    "STRUCTURE_SCHEMA", "SPLIT_MAP_SCHEMA", "SPLIT_WEIGHTS", "SPLIT_DENOMINATOR", "EVIDENCE_KINDS",
    "identity_for",
    "MAX_REFINEMENT_ROUNDS", "MAX_LABELLING_PERMUTATIONS",
    "StructureError", "StructureTooAmbiguous", "StructuralAliasError", "SplitMapError",
    "InvoiceShape", "AdviceLineShape", "ReceiptShape", "CreditNoteShape", "PlantShape", "StructuralTemplate",
    "canonical_structure", "structure_digest",
    "TemplateFamily", "SplitMap", "FROZEN_ASSIGNMENTS", "FROZEN_SPLIT_MAP",
    "TEMPLATE_ROSTER", "SPLIT_MAP", "StructureLedger",
]
