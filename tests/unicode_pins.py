"""One convention for runtime-scoped pins, keyed by `unicodedata.unidata_version`.

Some values this repository pins are not functions of its source alone:
`candidate/canonical.py`'s `parse_policy_view()` records
`unicodedata.unidata_version` as part of the parse policy's identity, so
every digest that embeds `parse_policy_digest` — `scorer_contract_digest`,
`task_contract_digest`, `environment_digest`, and the evaluation/ledger/
composite result digests built on top of them — legitimately moves when the
interpreter's Unicode database changes, with nothing else moving at all.

That pin was written twice, with its own bespoke table each time: once in
`tests/legacy_freeze.json`'s `unicode_scoped` map and again as
`_007_BY_IDENTITY_UNICODE_SCOPED` in `tests/test_cash_application_scoring.py`.
Reviewer decision 6 (round 16) asked for one reusable convention instead of a
third. This is it. A runtime-scoped pin is:

  * **keyed by the version string.** `unicodedata.unidata_version`, exactly as
    the interpreter reports it — never by CPython version, which is a
    different thing that merely correlates.
  * **carrying its own provenance.** Every row says whether it was OBSERVED on
    an interpreter that really ships that database (`native`) or DERIVED by
    substituting the version string on some other interpreter
    (`derived-by-substitution`), where it was generated, and whether a runtime
    shipping that database has since confirmed it. A derived row that nothing
    has confirmed says `PENDING` and keeps saying it until something does.
  * **failing loudly on a version it does not pin.** There is no fallback.
    Substituting the version STRING reproduces what the declared views RECORD;
    it cannot reproduce what a different database ACCEPTS, normalises or
    leaves unassigned — `canonical_text()` classifies every code point against
    the LIVE tables. So the running interpreter's own digests are never
    accepted as their own expectation: an unpinned database is an UNVERIFIED
    runtime, and `UnicodeScopedPins.resolve` refuses it by name and says how a
    reviewer opens the row.

Why derived rows exist at all: one interpreter can only observe one database.
The derived rows are candidates, and the native CI battery matrix is what
turns them into observations — which is why `provenance.method` and
`provenance.native_confirmation` are separate fields. Do not collapse them.

Nothing here is shipped: `tests/` is excluded from both artifacts.
"""

import contextlib
import platform
import re
import unicodedata

#: The two ways a runtime-scoped row can come to exist. `native`: computed on
#: an interpreter that actually ships that Unicode database. `derived-by-
#: substitution`: the version string was substituted on some other
#: interpreter, which reproduces the DECLARED views and nothing else.
PROVENANCE_METHODS = ("native", "derived-by-substitution")

#: The required fields of a row's provenance block. Extra fields are allowed
#: (a table may record a cross-check); these three are not optional.
PROVENANCE_FIELDS = ("method", "generated_on", "native_confirmation")

#: What a derived row's `native_confirmation` says until a runtime shipping
#: that database has actually run the suite against it.
PENDING_CONFIRMATION = ("PENDING: no runtime shipping this Unicode database has run this suite against this row "
                        "yet; the row is derived, not observed")

#: This interpreter's real Unicode database version, read ONCE at import so
#: that `substituted_unicode_version` — which patches the stdlib attribute —
#: can never be mistaken for it.
NATIVE_UNICODE_VERSION = unicodedata.unidata_version

#: The version this repository's own Python (3.12) ships, and the row every
#: derivation starts from. It must be pinned, and pinned NATIVELY.
ANCHOR_UNICODE_VERSION = "15.0.0"

#: A Unicode version no database will ever carry, so a suite can prove on
#: every run that an unseen runtime is refused rather than believed.
UNSEEN_UNICODE_PROBE = "99.0.0"

#: What a `unicode_scoped` key has to look like.
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")


@contextlib.contextmanager
def substituted_unicode_version(version: str):
    """Within the block, `unicodedata.unidata_version` reads as `version` for
    EVERY reader, because the attribute is set on the STDLIB module object
    itself — the one object the suites, `candidate/canonical.py`,
    `candidate/entities.py` and `graph/schema.py` all hold a reference to.
    (Patching only one module's own reference derives a row on a runtime half
    of which still reports the native database.)

    Every other `unicodedata` attribute — `category`, `normalize`, the tables
    behind them — is untouched and stays the running interpreter's. That is
    exactly why a substituted run DERIVES a row and cannot verify one.
    Restores the real version on exit, including on error."""
    real = unicodedata.unidata_version
    unicodedata.unidata_version = version
    try:
        yield
    finally:
        unicodedata.unidata_version = real


def generated_on() -> str:
    """Where a row computed right now was computed."""
    return (f"CPython {platform.python_version()} ({platform.system()}, unicode "
            f"{NATIVE_UNICODE_VERSION})")


def provenance_block(version: str, values: dict, previous: dict | None = None,
                     note: str | None = None) -> dict:
    """The `provenance` block for a freshly computed row.

    An explicit `note` always wins. A row computed on an interpreter that
    really ships this database documents itself. A DERIVED row keeps a
    confirmation already recorded only while the values it was recorded
    against have not moved; once they move it reverts to `PENDING`, because
    nothing has confirmed the new ones."""
    native = version == NATIVE_UNICODE_VERSION
    kept = (previous or {}).get("provenance")
    kept = kept.get("native_confirmation") if isinstance(kept, dict) else None
    unchanged = previous is not None and {k: v for k, v in previous.items() if k != "provenance"} == values
    if note is not None:
        confirmation = note
    elif native:
        confirmation = (f"observed natively on CPython {platform.python_version()} "
                        f"({platform.system()}), which ships unicode {version}")
    elif unchanged and isinstance(kept, str) and kept.strip():
        confirmation = kept
    else:
        confirmation = PENDING_CONFIRMATION
    return {
        "method": "native" if native else "derived-by-substitution",
        "generated_on": generated_on(),
        "native_confirmation": confirmation,
    }


def derived(generated_on_text: str, native_confirmation: str = PENDING_CONFIRMATION, **extra) -> dict:
    """A literal provenance block for a row DERIVED by substitution. The
    confirmation defaults to `PENDING`: a cross-check against published
    digests is evidence that the declared views did not drift, and belongs in
    `extra` (e.g. `cross_check=...`), never in `native_confirmation`."""
    return {"method": "derived-by-substitution", "generated_on": generated_on_text,
            "native_confirmation": native_confirmation, **extra}


def observed(generated_on_text: str, native_confirmation: str, **extra) -> dict:
    """A literal provenance block for a row OBSERVED on a runtime that ships
    the database it pins."""
    return {"method": "native", "generated_on": generated_on_text,
            "native_confirmation": native_confirmation, **extra}


def validate_provenance(label: str, prov, problems: list) -> None:
    """Append a problem for every way `prov` fails to be a provenance block."""
    if not isinstance(prov, dict):
        problems.append(f"{label} carries no provenance block: every row must record whether it was observed "
                        f"natively or derived by substitution, and where a runtime shipping that Unicode "
                        f"database confirmed it")
        return
    if prov.get("method") not in PROVENANCE_METHODS:
        problems.append(f"{label}.provenance.method is {prov.get('method')!r}, not one of "
                        f"{list(PROVENANCE_METHODS)}")
    for key in ("generated_on", "native_confirmation"):
        if not (isinstance(prov.get(key), str) and prov[key].strip()):
            problems.append(f"{label}.provenance.{key} is {prov.get(key)!r}, not a non-empty string")


class UnicodeScopedPins:
    """A table of pinned values keyed by `unicodedata.unidata_version`.

    `rows` maps a version string to a row: a `provenance` block plus the
    table's own `value_keys`. The rows may come from a checked-in JSON
    fixture (`tests/legacy_freeze.json`) or be written as literals in a suite
    (`tests/test_cash_application_scoring.py`); the convention is the same
    either way, and so is the refusal.

    Nothing is validated at construction: a suite may hand this a deliberately
    mutated fixture to prove the checks fail. `check_shape` is the validator;
    `resolve` is the lookup that refuses instead of guessing.
    """

    def __init__(self, *, name: str, source: str, rows: dict, value_keys: tuple,
                 how_to_add: str, anchor: str = ANCHOR_UNICODE_VERSION):
        self.name = name                    # what a reader calls this table
        self.source = source                # the file a reviewer opens
        self.rows = rows if isinstance(rows, dict) else {}
        self.value_keys = tuple(value_keys)
        self.how_to_add = how_to_add        # a format string taking {version}
        self.anchor = anchor

    # -- lookup -----------------------------------------------------------
    def versions(self) -> list:
        return sorted(self.rows)

    def __contains__(self, version: str) -> bool:
        return version in self.rows

    def row(self, version: str):
        return self.rows.get(version)

    def method(self, version: str) -> str:
        row = self.rows.get(version)
        prov = row.get("provenance") if isinstance(row, dict) else None
        return prov.get("method", "provenance missing") if isinstance(prov, dict) else "provenance missing"

    def resolve(self, version: str, problems: list, diagnostic=None):
        """The pinned row for `version`, or `None` — which fails the caller.

        There is no fallback, on purpose. An unpinned version appends a
        problem that NAMES the version and tells a reviewer how to open the
        row, and runs `diagnostic` (which may print, and may not decide
        anything) if one was given."""
        if version in self.rows:
            return self.rows[version]
        problems.append(
            f"unicode {version} is NOT pinned in {self.source}. This runtime's Unicode database has never been "
            f"reviewed against {self.name}, which does not certify a database it has not seen: identical source "
            f"can embed different digests under a different database, so the running interpreter's own digests "
            f"are not evidence about themselves. Add the row deliberately, under review -- "
            f"{self.how_to_add.format(version=version)} -- record in its provenance where a runtime shipping "
            f"unicode {version} confirmed it, and commit it. Pinned versions: {self.versions()}")
        if diagnostic is not None:
            diagnostic()
        return None

    def values(self, version: str, key: str):
        row = self.rows.get(version)
        return row.get(key) if isinstance(row, dict) else None

    # -- validation -------------------------------------------------------
    def check_shape(self, problems: list, value_check=None) -> None:
        """Every generic thing that must be true of this table, whatever it
        pins: a plausible version key, a row object, exactly the declared
        keys, a provenance block, and an anchor row that was observed rather
        than derived. `value_check(version, key, value, problems)` gets each
        pinned value for the table's own checks."""
        if not self.rows:
            problems.append(f"{self.source} carries no {self.name}")
            return
        expected_keys = sorted(("provenance",) + self.value_keys)
        for version, row in sorted(self.rows.items()):
            label = f"{self.name}[{version}]"
            if not VERSION_PATTERN.fullmatch(version):
                problems.append(f"{self.name} key {version!r} does not look like a Unicode database version")
            if not isinstance(row, dict):
                problems.append(f"{label} is {type(row).__name__}, not an object")
                continue
            if sorted(row) != expected_keys:
                problems.append(f"{label} has keys {sorted(row)}, not {expected_keys}")
            # Provenance is not decoration: it is the record of whether a
            # runtime that actually ships this database has ever confirmed
            # the row, which substitution cannot establish.
            validate_provenance(label, row.get("provenance"), problems)
            if value_check is not None:
                for key in self.value_keys:
                    if key in row:
                        value_check(version, key, row[key], problems)
        if self.anchor not in self.rows:
            problems.append(f"{self.name} has no {self.anchor!r} row: every other version is derived from it by "
                            f"substitution, so it must always be pinned directly")
        elif self.method(self.anchor) != "native":
            problems.append(f"{self.name}[{self.anchor}].provenance.method is {self.method(self.anchor)!r}: the "
                            f"anchor is the row every derivation starts from, so it must itself have been "
                            f"observed on an interpreter that ships unicode {self.anchor}")

    def check_refuses_an_unpinned_version(self, failures: list, probe: str = UNSEEN_UNICODE_PROBE,
                                          must_say: tuple = ()) -> None:
        """Drive `resolve` with a version no database will ever carry and
        require it to REFUSE — no row back, a problem naming the version.
        A suite calls this so the refusal is exercised on every run rather
        than assumed."""
        if probe in self.rows:
            failures.append(f"{probe} is a pinned row of {self.name}: the probe no longer probes anything")
            return
        problems: list = []
        resolved = self.resolve(probe, problems)
        if resolved is not None:
            failures.append(f"an unpinned unicode version resolved to a row of {self.name} instead of failing")
        if not problems:
            failures.append(f"an unpinned unicode version produced no problem at all from {self.name}")
            return
        if not all(probe in p for p in problems):
            failures.append(f"the reported failure does not name the version: {problems}")
        for token in must_say:
            if not any(token in p for p in problems):
                failures.append(f"the reported failure never says {token!r}: {problems}")
