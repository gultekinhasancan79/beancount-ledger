"""Resolving a submitted counterparty name to a stable entity.

The old scorer required the payee field to equal a fixed string exactly, case
sensitively. That rule cost a review round to introduce and two more to defend,
and it was one of the four the M0 review found nowhere an agent could read it.

It also taught the wrong thing. "Harbor Freight" instead of "Harbor Freight
Ltd" cost a penalty on an otherwise perfect submission, so what the reward
rewarded was verbatim transcription, not judgement about who the counterparty
was. Exact string equality is presentation wearing the clothes of semantics.

The register is the authority for the name, so resolution happens against the
register: a submitted string identifies an entity or it does not. Two spellings
that identify the same entity are the same fact, and the canonical renderer
writes the register's own display name afterwards, so the submission's spelling
never reaches the comparison at all.

Where this stops being generous is worth being precise about, because the
matching that lost repeatedly under the old design was substring matching. A
name is resolved by normalising both sides and comparing the *whole* string,
never by asking whether an accepted name appears somewhere inside submitted
text. The sentence "Definitely not Harbor Freight or SI-1044" contains the
accepted name and means its opposite; it resolves to nothing here, because it
is not a name, it is a sentence. Containment is not identity, and every test
built on containment is satisfiable by a sentence that denies itself.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

# Suffixes a register may or may not carry, and a writer may or may not type.
# Stripping them is safe because they do not distinguish two entities in any
# register we generate -- an invariant the generator has to hold, not a hope,
# so it is asserted in `build_resolver` rather than assumed.
_SUFFIXES = re.compile(
    r"\s*(,)?\s*\b(ltd|limited|llc|inc|incorporated|corp|corporation|co|company|plc|gmbh)\b\.?$",
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[.,;:!?'\"]+")


def canonical_key(name: str | None) -> str | None:
    """The form two spellings of one entity share.

    Case is folded and punctuation and corporate suffixes are dropped. Each of
    those was an attack under the old rules -- a name typed in mocking case
    defeated a case-insensitive check that had been loosened for fairness --
    but under a boundary that resolves to an entity rather than comparing
    strings, folding case is the *correct* reading rather than a concession:
    "HARBOR FREIGHT LTD" names the same company as "Harbor Freight".
    """
    if name is None:
        return None
    # NFKC first, so that visually identical spellings written with different
    # code points -- fullwidth letters, ligatures, non-breaking spaces -- reach
    # the same key. Without it the register is trivially evadable by a
    # lookalike, which is the same class of defect as the mocking-case attack
    # and would have needed the same kind of hand-written answer.
    #
    # It cuts both ways, which is why `build_resolver` refuses a world whose
    # register contains two entities that collide under this function: making
    # more spellings equal is only safe while distinct entities stay distinct.
    text = unicodedata.normalize("NFKC", name)
    text = _PUNCT.sub(" ", text)
    text = " ".join(text.split()).strip()
    if not text:
        return None
    previous = None
    while previous != text:
        previous = text
        text = _SUFFIXES.sub("", text).strip()
    return text.casefold() or None


class EntityRegister:
    """Names the world declares, and the entity each one identifies."""

    def __init__(self, entities: dict[str, str]):
        self._by_key = entities

    def resolve(self, name: str | None) -> str | None:
        """The entity a submitted name identifies, or None.

        None is a real answer, not a failure: an entry whose counterparty
        cannot be identified from the register is an entry nobody can tie to a
        document, which is a bookkeeping defect and is scored as one. It is not
        a protocol failure -- the submission is perfectly readable, it just
        names somebody who does not exist.
        """
        return self._by_key.get(canonical_key(name) or "")

    def display(self, entity: str | None) -> str | None:
        return entity

    def __len__(self) -> int:
        return len(self._by_key)


def build_resolver(world: Path) -> EntityRegister:
    """Build the register from the world's own files.

    Only from files the agent can read. Resolving against a list it cannot see
    would put an undisclosed rule back into the scorer through a side door,
    which is the defect this whole redesign exists to remove.
    """
    entities: dict[str, str] = {}
    collisions: list[str] = []

    def add(display: str) -> None:
        key = canonical_key(display)
        if key is None:
            return
        if key in entities and entities[key] != display:
            collisions.append(f"{display!r} and {entities[key]!r} share key {key!r}")
            return
        entities[key] = display

    for filename, column in (("vendors.csv", "vendor"), ("customers.csv", "customer")):
        path = world / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get(column):
                    add(row[column].strip())

    # Counterparties that appear only in an account description -- the bank
    # itself is the standing example, since it is named where the account is
    # described rather than in a register of its own.
    accounts = world / "accounts.csv"
    if accounts.exists():
        with accounts.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                match = re.search(r"held at ([A-Z][\w' ]+?)(?:\s*$|[,.])",
                                  row.get("description", "") or "")
                if match:
                    add(match.group(1).strip())

    if collisions:
        # Two distinct entities sharing a canonical key would make the
        # normalisation lossy: a submission naming one would resolve to the
        # other. That is a defect in the generated world, discoverable when the
        # world is built rather than when an agent is scored by it.
        raise ValueError(
            "counterparty register is ambiguous under canonical normalisation: "
            + "; ".join(collisions)
        )

    return EntityRegister(entities)
