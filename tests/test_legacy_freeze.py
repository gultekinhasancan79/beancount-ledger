"""The LEGACY FREEZE: the shipped surface, pinned byte for byte.

The cash-application family (spec section 8, implementation order step 1)
adds a second deliverable, a seventh tool, three public files and a fifth
episode contract. Every one of those must leave the 95 shipped tasks exactly
as they are: the same eight public files, the same task contracts, the same
frozen `candidate/1` scorer, the same contract-4 episode view. This suite is
what makes a drift in any of them LOUD before the step that caused it lands.

What is frozen, and where the fixture holds it (`tests/legacy_freeze.json`):

  * the sha256 of every projected public file of every registry task —
    95 tasks x 8 files — keyed task id -> file name -> digest, with the
    task's world id and its public id (`mint.public_task_id`, which binds the
    public bytes and the prompt);
  * the per-task identities the repository already exposes: `graph_digest`,
    `mutation_plan_digest`, every view digest (the private expected ledger
    and balances included), and both digests of the golden deliverable;
  * the frozen scorer: the raw bytes digest of
    `beancount_ledger/candidate/committed.py`, the engine id, and the
    validator/contract versions;
  * the contract-4 episode view: `episode_contract_digest()` at the default
    ceiling (the pin `tests/test_episode_contract.py` already holds — read
    from that file's source here so the two pins cannot diverge), the
    contract version and schema, the eight-name `PUBLIC_FILES`, the single
    write tool and the terminal tool;
  * the served legacy world directory, which is `bank_recon_001`'s projected
    bytes on disk.

Four digest families are NOT absolute constants, because
`candidate/canonical.parse_policy_view()` deliberately records
`unicodedata.unidata_version` as part of the parse policy's identity (a
Python upgrade can change what Unicode accepts and how it canonicalises, so
the database is part of the policy's identity — see that function's
comment): the scorer-level `parse_policy_digest` and `scorer_contract_digest`,
and the per-task `task_contract_digest` and `environment_digest` (which
embeds both of those). These four live under `unicode_scoped`, keyed by
`unicodedata.unidata_version` (`"14.0.0"` on CPython 3.11, `"15.0.0"` on
3.12, `"15.1.0"` on 3.13), one row per version holding `{"scorer": {...},
"tasks": {task_id: {...}}, "provenance": {...}}`.

A row for a version this interpreter is not running is DERIVED by
substituting the version string into the same view-building code
(`substituted_unicode_version` below patches the STDLIB attribute, so this
suite and `candidate/canonical.py` read one and the same string). That
derivation GENERATES a row; it does not verify one:

  * the DECLARED views take the Unicode database in only through the version
    string, so substitution reproduces them exactly;
  * `canonical.canonical_text()` does not. It calls `unicodedata.category()`
    on every code point of every string field, refuses the forbidden
    categories (unassigned among them) and normalises with
    `unicodedata.normalize("NFC", ...)` — all against the LIVE tables, which
    substituting a version string cannot emulate. Identical source can
    therefore accept different characters on two runtimes whose only visible
    difference is that string.

So a Unicode database this fixture has never seen FAILS the freeze, loudly,
naming itself: a reviewer opens the row deliberately. The substitution
survives only as a printed DIAGNOSTIC — it can tell that reviewer whether
the declared views also drifted, and it never turns a failure into a pass.
Every row carries a `provenance` block saying how it was generated
(`native` or `derived-by-substitution`) and where a runtime that actually
ships that database confirmed it. The battery matrix in
`.github/workflows/ci.yml` covers CPython 3.11 (14.0.0), 3.12 (15.0.0) and
3.13 (15.1.0) natively and runs on every push to main, every v* tag, and
every pull request -- so a job's native evidence arrives on a pull request or
on main, never on a push of a side branch, and
`test_the_ci_claims_match_the_workflow` parses the workflow and fails if this
paragraph, a row's provenance or the release attestation stops saying so.

Comparison is exact: an extra file, a missing file, a moved byte, a changed
digest or a renamed task fails. A task registered outside the freeze is
reported and does not fail — a new family is not a change to the legacy one —
but every frozen task must still be registered.

Re-pinning is a deliberate act, never a side effect of a green run:

    python tests/test_legacy_freeze.py                                    # verify
    python tests/test_legacy_freeze.py --regenerate                       # rewrite the invariant fields and this
                                                                            # interpreter's own unicode_scoped row;
                                                                            # print what moved
    python tests/test_legacy_freeze.py --regenerate-unicode-scoped 14.0.0 # add/refresh ONLY unicode_scoped["14.0.0"],
                                                                            # computed by substitution on THIS
                                                                            # interpreter; leaves everything else alone
    ... --regenerate-unicode-scoped 15.1.0 --note "confirmed by <what>"   # the same, recording in the row's
                                                                            # provenance where a runtime shipping
                                                                            # that database confirmed it
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import platform
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import canonical as C  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate.validate import VALIDATOR_VERSION  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.mint import public_task_id  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402

FIXTURE = ROOT / "tests" / "legacy_freeze.json"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
ATTESTATION = ROOT / "reviews" / "RELEASE_ATTESTATION.md"
FIXTURE_SCHEMA = "piv.legacy-freeze/2"
SCORER_SOURCE = ROOT / "beancount_ledger" / "candidate" / "committed.py"
EPISODE_CONTRACT_TEST = ROOT / "tests" / "test_episode_contract.py"

#: The two scorer-level and two per-task digest families that legitimately
#: vary with `unicodedata.unidata_version` (see the module docstring).
SCORER_UNICODE_KEYS = ("parse_policy_digest", "scorer_contract_digest")
TASK_UNICODE_KEYS = ("task_contract_digest", "environment_digest")

#: The version this repository's own Python (3.12) ships, and the row every
#: derivation starts from. It must be pinned, and pinned NATIVELY.
ANCHOR_UNICODE_VERSION = "15.0.0"

#: This interpreter's real Unicode database version, read ONCE at import so
#: that `substituted_unicode_version` — which patches the stdlib attribute —
#: can never be mistaken for it.
NATIVE_UNICODE_VERSION = unicodedata.unidata_version

#: How a `unicode_scoped` row came to exist. `native`: computed on an
#: interpreter that actually ships that Unicode database. `derived-by-
#: substitution`: the version string was substituted on some other
#: interpreter, which reproduces the DECLARED views and nothing else.
UNICODE_PROVENANCE_METHODS = ("native", "derived-by-substitution")

#: What a derived row's `native_confirmation` says until a runtime shipping
#: that database has actually run this suite against it.
PENDING_CONFIRMATION = ("PENDING: no runtime shipping this Unicode database has run this suite against this row "
                        "yet; the row is derived, not observed")

#: A Unicode version no database will ever carry, used by
#: `test_an_unpinned_unicode_version_fails_the_freeze` to prove on every run
#: that an unseen runtime is refused rather than believed.
UNSEEN_UNICODE_PROBE = "99.0.0"

#: The legacy public files, in the order the environment declares them.
LEGACY_PUBLIC_FILES = (
    "manifest.md", "policy.md", "accounts.csv", "customers.csv", "vendors.csv",
    "archive_prior_period.csv", "ledger.beancount", "bank_statement.csv",
)
LEGACY_TASK_COUNT = 95


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:40]:
            print(f"      {line}")
    return ok


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------
# the live snapshot: computed once, compared field by field
#
# Split in two: the INVARIANT snapshot (files, graph/plan/view digests,
# golden digests, the episode contract, the scorer's own bytes and version
# numbers) never legitimately moves and is compared directly against the
# fixture's top-level fields. The UNICODE-SCOPED snapshot (parse_policy_digest,
# scorer_contract_digest, and the per-task task_contract_digest /
# environment_digest that embed them) is compared against the fixture's
# `unicode_scoped[unicodedata.unidata_version]` row instead — see
# `resolve_unicode_scoped` for what happens when that row is absent.
# --------------------------------------------------------------------------

@contextlib.contextmanager
def substituted_unicode_version(version: str):
    """Within the block, `unicodedata.unidata_version` reads as `version` for
    EVERY reader, because the attribute is set on the STDLIB module object
    itself — the one object this suite, `candidate/canonical.py`,
    `candidate/entities.py` and `graph/schema.py` all hold a reference to.
    (Patching only `canonical`'s own reference, as this did before, derived a
    row on a runtime half of which still reported the native database.)

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


def task_snapshot(task_id: str) -> dict:
    """The INVARIANT half of what the freeze holds for one task, recomputed
    from the registry through the production door `derive_contract`."""
    world, task = REGISTRY[task_id]
    _, inputs = derive_contract(world, task)
    golden = env_mod.digests_of(inputs.golden_text.encode("utf-8"))
    return {
        "world_id": inputs.world_id,
        "public_task_id": public_task_id(inputs),
        "files": {name: sha256(data) for name, data in inputs.public_files},
        "graph_digest": inputs.graph_digest,
        "mutation_plan_digest": inputs.mutation_plan_digest,
        "view_digests": {name: digest for name, digest in inputs.view_digests},
        "engine": K.CANDIDATE_ENGINE.id,
        "golden_stored_bytes_digest": golden["stored_bytes_digest"],
        "golden_logical_text_digest": golden["logical_text_digest"],
    }


def task_unicode_snapshot(task_id: str) -> dict:
    """The two Unicode-scoped digests for one task, through `load_contract`
    (the production door for the scoring environment), under whatever
    `unicodedata` `canonical` currently sees — real or substituted."""
    world, task = REGISTRY[task_id]
    _, inputs = derive_contract(world, task)
    env = K.load_contract(inputs)
    return {"task_contract_digest": env.task_contract_digest, "environment_digest": env.environment_digest}


def scorer_unicode_snapshot() -> dict:
    return {"parse_policy_digest": C.parse_policy_digest(), "scorer_contract_digest": C.scorer_contract_digest()}


def scorer_unicode_digests(version: str) -> dict:
    """The two scorer-level digests for `version` alone — no task derivation.
    The cheap half of `live_unicode_scoped`, for the diagnostic to print."""
    ctx = (contextlib.nullcontext() if version == NATIVE_UNICODE_VERSION
           else substituted_unicode_version(version))
    with ctx:
        return scorer_unicode_snapshot()


def unicode_provenance(version: str, row: dict, before: dict | None, note: str | None) -> dict:
    """The `provenance` block for a freshly computed `unicode_scoped` row.

    An explicit `--note` always wins. A row computed on an interpreter that
    really ships this database documents itself. A DERIVED row keeps a
    confirmation already recorded only while the digests it was recorded
    against have not moved; once they move it reverts to `PENDING`, because
    nothing has confirmed the new ones."""
    native = version == NATIVE_UNICODE_VERSION
    previous = (before or {}).get("provenance")
    kept = previous.get("native_confirmation") if isinstance(previous, dict) else None
    unchanged = before is not None and {k: v for k, v in before.items() if k != "provenance"} == row
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
        "generated_on": f"CPython {platform.python_version()} ({platform.system()}, unicode "
                        f"{NATIVE_UNICODE_VERSION})",
        "native_confirmation": confirmation,
    }


def pinned_episode_contract_digest() -> str | None:
    """The literal `tests/test_episode_contract.py` pins, read from its
    source rather than imported: that module's import graph is the whole
    scripted-route harness, and the point here is only that the two pins
    name one digest."""
    match = re.search(r'^EPISODE_CONTRACT_DIGEST = "([0-9a-f]{64})"$',
                      EPISODE_CONTRACT_TEST.read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else None


def live_snapshot() -> dict:
    """The invariant fields only — schema, episode contract, the scorer's
    bytes/versions (not its two Unicode-scoped digests), the public files
    and every task's invariant half."""
    tasks = {task_id: task_snapshot(task_id) for task_id in sorted(REGISTRY)}
    scorer_bytes = SCORER_SOURCE.read_bytes()
    return {
        "schema": FIXTURE_SCHEMA,
        "episode_contract": {
            "version": env_mod.EPISODE_CONTRACT_VERSION,
            "schema": env_mod.EPISODE_CONTRACT_SCHEMA,
            "max_episode_output_tokens": env_mod.MAX_EPISODE_OUTPUT_TOKENS,
            "digest": env_mod.episode_contract_digest(),
            "public_files": list(env_mod.PUBLIC_FILES),
            "write_tool": env_mod.WRITE_TOOL,
            "terminal_tool": env_mod.TERMINAL_TOOL,
        },
        "scorer": {
            "committed_py_sha256": sha256(scorer_bytes),
            "committed_py_bytes": len(scorer_bytes),
            "engine": K.CANDIDATE_ENGINE.id,
            "validator_version": VALIDATOR_VERSION,
            "scorer_contract_version": C.SCORER_CONTRACT_VERSION,
            "task_contract_version": C.TASK_CONTRACT_VERSION,
            "renderer_version": C.RENDERER_VERSION,
        },
        "public_files": list(LEGACY_PUBLIC_FILES),
        "task_count": len(tasks),
        "tasks": tasks,
    }


_LIVE: dict | None = None
_LIVE_UNICODE_SCOPED: dict[str, dict] = {}


def live() -> dict:
    global _LIVE
    if _LIVE is None:
        _LIVE = live_snapshot()
    return _LIVE


def _legacy_task_ids() -> list[str]:
    """The task ids the freeze currently pins (95), or, before any fixture
    exists yet, every registered task — the one-time bootstrap case for a
    fresh `--regenerate`. Never the live `REGISTRY`'s full set once a
    fixture exists: a later family (e.g. `cash_application_00x`) is
    registered outside the freeze on purpose and must not leak into a newly
    generated `unicode_scoped` row."""
    if FIXTURE.exists():
        return sorted(fixture()["tasks"])
    return sorted(REGISTRY)


def live_unicode_scoped(version: str | None = None) -> dict:
    """The `{"scorer": {...}, "tasks": {task_id: {...}}}` Unicode-scoped
    snapshot for `version` (default: this interpreter's real
    `unicodedata.unidata_version`). Computed directly when `version` is the
    real one; computed by substitution otherwise. Cached per version, since
    a substitution run touches every frozen task."""
    key = NATIVE_UNICODE_VERSION if version is None else version
    if key not in _LIVE_UNICODE_SCOPED:
        ctx = (contextlib.nullcontext() if key == NATIVE_UNICODE_VERSION
               else substituted_unicode_version(key))
        with ctx:
            _LIVE_UNICODE_SCOPED[key] = {
                "scorer": scorer_unicode_snapshot(),
                "tasks": {task_id: task_unicode_snapshot(task_id) for task_id in _legacy_task_ids()},
            }
    return _LIVE_UNICODE_SCOPED[key]


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _diff(label: str, want, got, problems: list) -> None:
    if want != got:
        problems.append(f"{label}: pinned {want!r}, now {got!r}")


def _diff_unicode(label: str, version: str, want, got, problems: list) -> None:
    if want != got:
        problems.append(f"{label} @ unicode {version}: pinned {want!r}, actual {got!r}")


# --------------------------------------------------------------------------
# the checks
# --------------------------------------------------------------------------

def test_the_fixture_is_well_formed():
    problems = []
    if not FIXTURE.exists():
        return check(f"the freeze fixture exists at {FIXTURE.relative_to(ROOT)}", False,
                     "run `python tests/test_legacy_freeze.py --regenerate` once, deliberately, and commit it")
    pinned = fixture()
    _diff("fixture schema", FIXTURE_SCHEMA, pinned.get("schema"), problems)
    _diff("task count", LEGACY_TASK_COUNT, pinned.get("task_count"), problems)
    _diff("task count vs. task map", pinned.get("task_count"), len(pinned.get("tasks", {})), problems)
    _diff("public file names", list(LEGACY_PUBLIC_FILES), pinned.get("public_files"), problems)
    for task_id, row in sorted(pinned.get("tasks", {}).items()):
        names = sorted(row.get("files", {}))
        if names != sorted(LEGACY_PUBLIC_FILES):
            problems.append(f"{task_id}: the fixture pins {names}, not the eight legacy files")
        for name, digest in row.get("files", {}).items():
            if not (isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)):
                problems.append(f"{task_id}/{name}: {digest!r} is not a sha256 hex digest")
        for key in TASK_UNICODE_KEYS + SCORER_UNICODE_KEYS:
            if key in row:
                problems.append(f"{task_id}: {key!r} belongs under unicode_scoped, not on the task row directly")
    scoped = pinned.get("unicode_scoped")
    if not isinstance(scoped, dict) or not scoped:
        problems.append("the fixture carries no unicode_scoped map")
    else:
        for version, row in sorted(scoped.items()):
            if not re.fullmatch(r"\d+\.\d+\.\d+", version):
                problems.append(f"unicode_scoped key {version!r} does not look like a Unicode database version")
            if not isinstance(row, dict):
                problems.append(f"unicode_scoped[{version}] is {type(row).__name__}, not an object")
                continue
            if sorted(row) != ["provenance", "scorer", "tasks"]:
                problems.append(f"unicode_scoped[{version}] has keys {sorted(row)}, "
                                f"not ['provenance', 'scorer', 'tasks']")
            # Provenance is not decoration: it is the record of whether a
            # runtime that actually ships this database has ever confirmed
            # the row, which substitution cannot establish (module docstring).
            prov = row.get("provenance")
            if not isinstance(prov, dict):
                problems.append(f"unicode_scoped[{version}] carries no provenance block: every row must record "
                                f"whether it was observed natively or derived by substitution, and where a "
                                f"runtime shipping unicode {version} confirmed it")
            else:
                if prov.get("method") not in UNICODE_PROVENANCE_METHODS:
                    problems.append(f"unicode_scoped[{version}].provenance.method is {prov.get('method')!r}, "
                                    f"not one of {list(UNICODE_PROVENANCE_METHODS)}")
                for key in ("generated_on", "native_confirmation"):
                    if not (isinstance(prov.get(key), str) and prov[key].strip()):
                        problems.append(f"unicode_scoped[{version}].provenance.{key} is {prov.get(key)!r}, "
                                        f"not a non-empty string")
            scorer_row = row.get("scorer", {})
            if sorted(scorer_row) != sorted(SCORER_UNICODE_KEYS):
                problems.append(f"unicode_scoped[{version}].scorer has keys {sorted(scorer_row)}, "
                                f"not {sorted(SCORER_UNICODE_KEYS)}")
            for key, digest in scorer_row.items():
                if not (isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)):
                    problems.append(f"unicode_scoped[{version}].scorer.{key}: {digest!r} is not a sha256 hex digest")
            task_rows = row.get("tasks", {})
            missing_tasks = set(pinned.get("tasks", {})) - set(task_rows)
            extra_tasks = set(task_rows) - set(pinned.get("tasks", {}))
            if missing_tasks:
                problems.append(f"unicode_scoped[{version}].tasks is missing {sorted(missing_tasks)}")
            if extra_tasks:
                problems.append(f"unicode_scoped[{version}].tasks has unknown task ids {sorted(extra_tasks)}")
            for task_id, task_row in task_rows.items():
                if sorted(task_row) != sorted(TASK_UNICODE_KEYS):
                    problems.append(f"unicode_scoped[{version}].tasks[{task_id}] has keys {sorted(task_row)}, "
                                    f"not {sorted(TASK_UNICODE_KEYS)}")
                for key, digest in task_row.items():
                    if not (isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)):
                        problems.append(f"unicode_scoped[{version}].tasks[{task_id}].{key}: {digest!r} "
                                        f"is not a sha256 hex digest")
        if ANCHOR_UNICODE_VERSION not in scoped:
            problems.append(f"unicode_scoped has no {ANCHOR_UNICODE_VERSION!r} row: every other version is "
                            f"derived from it by substitution, so it must always be pinned directly")
        else:
            anchor_prov = scoped[ANCHOR_UNICODE_VERSION].get("provenance") \
                if isinstance(scoped[ANCHOR_UNICODE_VERSION], dict) else None
            method = anchor_prov.get("method") if isinstance(anchor_prov, dict) else None
            if method != "native":
                problems.append(f"unicode_scoped[{ANCHOR_UNICODE_VERSION}].provenance.method is {method!r}: the "
                                f"anchor is the row every derivation starts from, so it must itself have been "
                                f"observed on an interpreter that ships unicode {ANCHOR_UNICODE_VERSION}")
    return check(f"the fixture pins {LEGACY_TASK_COUNT} tasks x {len(LEGACY_PUBLIC_FILES)} files under schema "
                 f"{FIXTURE_SCHEMA}, with the Unicode-scoped digests under unicode_scoped and every one of those "
                 f"rows declaring its provenance", not problems, "\n".join(problems))


def test_every_frozen_task_is_still_registered():
    pinned = set(fixture()["tasks"])
    registered = set(REGISTRY)
    missing = sorted(pinned - registered)
    extra = sorted(registered - pinned)
    if extra:
        print(f"      {len(extra)} registered task(s) outside the freeze (a new family, not a legacy change): {extra}")
    return check(f"all {len(pinned)} frozen task ids are registered (none removed or renamed)",
                 not missing, f"frozen tasks no longer registered: {missing}")


def test_every_legacy_public_file_is_byte_identical():
    """The 95 x 8 projected files: the same names, the same bytes."""
    pinned = fixture()["tasks"]
    now = live()["tasks"]
    problems = []
    files = 0
    for task_id in sorted(pinned):
        if task_id not in now:
            continue                                  # reported by the registration check
        want, got = pinned[task_id], now[task_id]
        _diff(f"{task_id}: world id", want["world_id"], got["world_id"], problems)
        _diff(f"{task_id}: public task id", want["public_task_id"], got["public_task_id"], problems)
        for name in sorted(set(want["files"]) | set(got["files"])):
            files += 1
            if name not in got["files"]:
                problems.append(f"{task_id}/{name}: no longer projected as a public file")
            elif name not in want["files"]:
                problems.append(f"{task_id}/{name}: a public file the freeze does not know")
            elif want["files"][name] != got["files"][name]:
                problems.append(f"{task_id}/{name}: bytes changed ({want['files'][name][:12]} -> {got['files'][name][:12]})")
    return check(f"every projected public file of the {len(pinned)} legacy tasks ({files} files) is byte-identical "
                 f"to the freeze, and each task still has exactly the eight legacy files",
                 not problems, "\n".join(problems))


def test_every_legacy_task_contract_is_unchanged():
    """The identities the scorer and the manifest already bind per task —
    the invariant half; `task_contract_digest` and `environment_digest` are
    Unicode-scoped and checked separately, in
    `test_the_unicode_scoped_digests_are_pinned_for_this_runtime`."""
    pinned = fixture()["tasks"]
    now = live()["tasks"]
    keys = ("graph_digest", "mutation_plan_digest", "engine",
            "golden_stored_bytes_digest", "golden_logical_text_digest")
    problems = []
    for task_id in sorted(pinned):
        if task_id not in now:
            continue
        want, got = pinned[task_id], now[task_id]
        for key in keys:
            _diff(f"{task_id}: {key}", want[key], got[key], problems)
        _diff(f"{task_id}: view digests", want["view_digests"], got["view_digests"], problems)
    return check(f"graph, plan, view and golden digests of the {len(pinned)} legacy tasks are the pinned ones",
                 not problems, "\n".join(problems))


def print_unpinned_unicode_diagnostic(pinned_scoped: dict, running_version: str) -> None:
    """Everything a reviewer needs to open a fixture row for
    `running_version` — and nothing that can decide the run. Two derived
    facts, both PRINTED, neither compared against anything by the caller:

      * the ANCHOR CROSS-CHECK. Substitute this interpreter's code back to
        `ANCHOR_UNICODE_VERSION` and compare with the pinned anchor row.
        Reproducing it says the DECLARED views did not drift, i.e. the only
        difference this runtime brings to them is the version string. It
        says nothing about what this runtime's Unicode database actually
        does — `canonical.canonical_text()` classifies and normalises with
        the live tables and refuses unassigned code points, which no
        substitution emulates. That gap is why this is a diagnostic and not
        a verdict.
      * the SCORER-LEVEL DIGESTS this runtime really computes, printed as
        JSON to paste, so the reviewer can see them here and compare them
        with what a regeneration writes.
    """
    print(f"      DIAGNOSTIC for unicode {running_version} (informational; it does not affect the verdict):")
    anchor_pinned = pinned_scoped.get(ANCHOR_UNICODE_VERSION)
    if not isinstance(anchor_pinned, dict):
        print(f"        no pinned {ANCHOR_UNICODE_VERSION} anchor row to cross-check this code against")
    else:
        anchor_live = live_unicode_scoped(ANCHOR_UNICODE_VERSION)   # substituted back to the anchor, on THIS code
        drift: list = []
        for key in SCORER_UNICODE_KEYS:
            _diff_unicode(f"scorer.{key}", ANCHOR_UNICODE_VERSION, anchor_pinned["scorer"][key],
                          anchor_live["scorer"][key], drift)
        for task_id in sorted(anchor_pinned["tasks"]):
            if task_id not in anchor_live["tasks"]:
                continue
            for key in TASK_UNICODE_KEYS:
                _diff_unicode(f"{task_id}.{key}", ANCHOR_UNICODE_VERSION, anchor_pinned["tasks"][task_id][key],
                              anchor_live["tasks"][task_id][key], drift)
        if drift:
            print(f"        anchor cross-check FAILED ({len(drift)} field(s)): substituting this code back to "
                  f"{ANCHOR_UNICODE_VERSION} does not reproduce the pinned anchor row, so the scorer, a task "
                  f"contract or the parse policy drifted independently of the Unicode database:")
            for line in drift[:12]:
                print(f"          {line}")
            if len(drift) > 12:
                print(f"          ... and {len(drift) - 12} more")
        else:
            print(f"        anchor cross-check clean: substituted back to {ANCHOR_UNICODE_VERSION} this code "
                  f"reproduces the pinned anchor row, so the declared views did not drift. This does NOT show "
                  f"that unicode {running_version} classifies and normalises the world's text as "
                  f"{ANCHOR_UNICODE_VERSION} does.")
    scorer = scorer_unicode_digests(running_version)
    print(f'        to paste into unicode_scoped["{running_version}"].scorer:')
    for key in SCORER_UNICODE_KEYS:
        print(f'          "{key}": "{scorer[key]}"')
    print(f"        for the whole row, on this runtime: python tests/test_legacy_freeze.py "
          f"--regenerate-unicode-scoped {running_version} --note \"<where a unicode {running_version} runtime "
          f"confirmed it>\"")


def resolve_unicode_scoped(pinned_scoped: dict, running_version: str, problems: list) -> dict | None:
    """The pinned `{"scorer": {...}, "tasks": {...}, "provenance": {...}}`
    row for `running_version` — or `None`, which fails the freeze.

    There is no fallback, on purpose (reviewer decision 5, round 13). A
    Unicode database this fixture has never seen is an UNVERIFIED runtime,
    not a verified one: `canonical.canonical_text()` calls
    `unicodedata.category()` on every code point of every string field,
    refuses the forbidden categories — unassigned included — and normalises
    NFC, all against the LIVE tables. Substituting the version STRING
    reproduces what the declared views RECORD; it cannot reproduce what a
    different database ACCEPTS, normalises, or leaves unassigned. So the
    same source can admit different characters on two runtimes whose only
    visible difference is that string, and taking the running interpreter's
    own digests as their own expectation would check nothing at all — it
    would only restate them.

    An unpinned version therefore fails, naming itself and naming the row a
    reviewer has to add. The substitution still runs, as the printed
    diagnostic above; it never becomes the answer.
    """
    if running_version in pinned_scoped:
        return pinned_scoped[running_version]
    problems.append(
        f"unicode {running_version} is NOT pinned in {FIXTURE.name}. This runtime's Unicode database has never "
        f"been reviewed against the freeze, and the freeze does not certify a database it has not seen: identical "
        f"source can accept different characters under different databases, so the running interpreter's own "
        f"digests are not evidence about themselves. Add the row deliberately, under review -- "
        f"`python tests/test_legacy_freeze.py --regenerate-unicode-scoped {running_version}` -- record in its "
        f"provenance where a runtime shipping unicode {running_version} confirmed it, and commit it. "
        f"Pinned versions: {sorted(pinned_scoped)}")
    print_unpinned_unicode_diagnostic(pinned_scoped, running_version)
    return None


def test_the_unicode_scoped_digests_are_pinned_for_this_runtime():
    """`parse_policy_digest`/`scorer_contract_digest` (scorer-level) and
    `task_contract_digest`/`environment_digest` (per task) legitimately vary
    with `unicodedata.unidata_version`, so the fixture pins them per version.
    THIS interpreter's version must be one of the pinned ones; an unseen
    Unicode database fails here rather than certifying itself (see
    `resolve_unicode_scoped`)."""
    running_version = NATIVE_UNICODE_VERSION
    pinned = fixture()
    pinned_scoped = pinned.get("unicode_scoped", {})
    pinned_tasks = pinned["tasks"]
    problems: list = []
    expected = resolve_unicode_scoped(pinned_scoped, running_version, problems)
    if expected is None:
        return check(f"unicode {running_version} is pinned in {FIXTURE.name} and its scorer and per-task "
                     f"Unicode-scoped digests match", False, "\n".join(problems))
    live_row = live_unicode_scoped(running_version)
    for key in SCORER_UNICODE_KEYS:
        _diff_unicode(f"scorer.{key}", running_version, expected["scorer"][key], live_row["scorer"][key], problems)
    for task_id in sorted(pinned_tasks):
        if task_id not in live_row["tasks"] or task_id not in expected["tasks"]:
            continue                                       # reported by the registration check
        for key in TASK_UNICODE_KEYS:
            _diff_unicode(f"{task_id}.{key}", running_version, expected["tasks"][task_id][key],
                          live_row["tasks"][task_id][key], problems)
    provenance = expected.get("provenance") if isinstance(expected.get("provenance"), dict) else {}
    origin = provenance.get("method", "provenance missing")
    return check(f"scorer_contract_digest, parse_policy_digest and the {len(pinned_tasks)} legacy tasks' "
                 f"task_contract_digest/environment_digest match the PINNED unicode {running_version} row "
                 f"({origin})", not problems, "\n".join(problems))


def test_an_unpinned_unicode_version_fails_the_freeze():
    """The rule that replaced the old fallback, exercised on every run.

    Reviewer decision 5 (round 13): stop automatically treating an unseen
    runtime as verified. This drives `resolve_unicode_scoped` with a version
    no database will ever carry and requires it to REFUSE — no row back, a
    problem that names the version and tells the reviewer how to open the
    row — while the diagnostic runs (it prints) without becoming the answer,
    and leaves the real `unicodedata.unidata_version` in place afterwards.

    Without this the freeze would be one `return live_...()` away from
    passing on any runtime at all, silently, and no other suite would notice.
    """
    pinned_scoped = fixture().get("unicode_scoped", {})
    failures = []
    if UNSEEN_UNICODE_PROBE in pinned_scoped:
        failures.append(f"{UNSEEN_UNICODE_PROBE} is a pinned row: the probe no longer probes anything")
    else:
        problems: list = []
        resolved = resolve_unicode_scoped(pinned_scoped, UNSEEN_UNICODE_PROBE, problems)
        if resolved is not None:
            failures.append(f"an unpinned unicode version resolved to a row ({sorted(resolved)}) instead of failing")
        if not problems:
            failures.append("an unpinned unicode version produced no problem at all")
        else:
            if not all(UNSEEN_UNICODE_PROBE in p for p in problems):
                failures.append(f"the reported failure does not name the version: {problems}")
            if not any("--regenerate-unicode-scoped" in p for p in problems):
                failures.append("the reported failure does not tell the reviewer how to add the row")
    if unicodedata.unidata_version != NATIVE_UNICODE_VERSION:
        failures.append(f"the diagnostic left unicodedata.unidata_version patched to "
                        f"{unicodedata.unidata_version!r} (expected {NATIVE_UNICODE_VERSION!r})")
    return check(f"an unpinned Unicode database (probe {UNSEEN_UNICODE_PROBE}) FAILS the freeze, naming the "
                 f"version and the fixture row a reviewer must add, and the substitution stays a diagnostic",
                 not failures, "\n".join(failures))


def test_the_substitution_reaches_every_reader_of_unidata_version():
    """A derived row is only meaningful if the substitution is total: the
    suite, `candidate/canonical.py` and the views it builds must all read the
    same substituted string. Patching only `canonical`'s module reference —
    what this file did before round 13 — left the suite (and every other
    importer) reporting the native database while the views reported the
    substituted one, which is a row derived from no single runtime at all.

    Also requires that the substitution is reversible and does NOT touch the
    tables themselves: `unicodedata.category`/`normalize` keep working, which
    is the very asymmetry that makes substitution insufficient as proof."""
    probe = "0.0.0"
    failures = []
    inside: dict = {}
    with substituted_unicode_version(probe):
        inside["unicodedata.unidata_version (this suite)"] = unicodedata.unidata_version
        inside["canonical.unicodedata.unidata_version"] = C.unicodedata.unidata_version
        inside["parse_policy_view()['unicode']['database_version']"] = \
            C.parse_policy_view()["unicode"]["database_version"]
        inside["scorer_contract_view()['unicode_database_version']"] = \
            C.scorer_contract_view()["unicode_database_version"]
        if unicodedata.category("A") != "Lu" or unicodedata.normalize("NFC", "é") != "é":
            failures.append("substitution disturbed the live Unicode tables; only the version string may move")
    for label, seen in sorted(inside.items()):
        if seen != probe:
            failures.append(f"{label} read {seen!r} inside the substitution, not {probe!r}")
    for label, seen in (("unicodedata.unidata_version", unicodedata.unidata_version),
                        ("canonical.unicodedata.unidata_version", C.unicodedata.unidata_version),
                        ("parse_policy_view()", C.parse_policy_view()["unicode"]["database_version"])):
        if seen != NATIVE_UNICODE_VERSION:
            failures.append(f"{label} read {seen!r} after the substitution, not the native "
                            f"{NATIVE_UNICODE_VERSION!r}")
    return check("substituted_unicode_version moves the stdlib attribute, so the suite, candidate/canonical and "
                 "both declared views read the substituted database version and nothing else moves",
                 not failures, "\n".join(failures))


# --------------------------------------------------------------------------
# what this repository SAYS about CI, read out of the workflow itself
#
# The Unicode rows above are only as good as the runtime that confirmed
# them, so both `provenance.native_confirmation` and the release attestation
# describe WHEN the CI battery compares a row. That sentence is evidence,
# and evidence has to be measured: the helpers below parse
# `.github/workflows/ci.yml` and `test_the_ci_claims_match_the_workflow`
# fails when what the repository says about CI stops matching what CI does.
# --------------------------------------------------------------------------

def ci_triggers() -> dict:
    """The workflow's `on:` block, parsed: which pushes and which tags fire
    it, and whether pull requests do. `push_branches` is `None` when the
    push trigger names no branches, i.e. every branch fires it."""
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    block = re.search(r"^on:[ \t]*\n((?:[ \t]+\S.*\n|[ \t]*\n)*)", text, re.M)
    if not block:
        raise AssertionError(f"{CI_WORKFLOW.name} has no top-level `on:` block: the triggers this repository's "
                             f"prose describes cannot be read, so nothing here may claim to know them")
    body = block.group(1)
    push = re.search(r"^  push:[ \t]*\n((?:    \S.*\n)*)", body, re.M)
    listed = lambda m: [v.strip().strip("\"'") for v in m.group(1).split(",") if v.strip()] if m else None
    branches = re.search(r"^    branches:\s*\[([^\]]*)\]", push.group(1), re.M) if push else None
    tags = re.search(r"^    tags:\s*\[([^\]]*)\]", push.group(1), re.M) if push else None
    return {
        "push": push is not None,
        "push_branches": listed(branches),
        "push_tags": listed(tags) or [],
        "pull_request": re.search(r"^  pull_request:", body, re.M) is not None,
    }


def ci_trigger_clause() -> str:
    """The clause every sentence in this repository that says WHEN CI runs
    must carry, built from the workflow's own triggers -- e.g. "on every push
    to main, every v* tag, and every pull request". Derived, not written
    down, so changing the workflow's triggers changes what the prose has to
    say and the check below notices."""
    t = ci_triggers()
    parts: list[str] = []
    if t["push"]:
        parts.append("every push" if t["push_branches"] is None
                     else "every push to " + " or ".join(t["push_branches"]))
        parts += [f"every {tag} tag" for tag in t["push_tags"]]
    if t["pull_request"]:
        parts.append("every pull request")
    if not parts:
        raise AssertionError(f"{CI_WORKFLOW.name} declares no trigger this reader understands")
    if len(parts) == 1:
        return f"on {parts[0]}"
    return "on " + ", ".join(parts[:-1]) + (", and " if len(parts) > 2 else " and ") + parts[-1]


def ci_battery_pythons() -> list[str]:
    """The CPython versions the battery job's matrix actually runs."""
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    strategy = re.search(r"^    strategy:\n(.*?)^    steps:", text, re.M | re.S)
    if not strategy:
        raise AssertionError(f"{CI_WORKFLOW.name}'s battery job has no strategy/matrix block to read")
    return sorted({v for v in re.findall(r'"(\d+\.\d+)"', strategy.group(1))},
                  key=lambda v: tuple(int(part) for part in v.split(".")))


def _ci_claim_sentences(text: str) -> list[str]:
    """The sentences of `text` that name the CI workflow file, with runs of
    whitespace collapsed -- a claim is the same claim whether a docstring or
    a Markdown paragraph happens to wrap it."""
    return [" ".join(s.split()) for s in re.split(r"(?<=\.)\s+", text) if CI_WORKFLOW.name in s]


def test_the_ci_claims_match_the_workflow():
    """Every sentence that names `.github/workflows/ci.yml` says when that
    job runs, and the workflow decides whether it is true.

    This exists because the wording was false once and nothing caught it: a
    row's provenance said the ubuntu 3.13 job confirms it "from the first
    push of this branch onward", while the workflow triggers on pushes to
    main, on tags and on pull requests -- so a push of a feature branch runs
    no job at all, and the sentence promised evidence that no run would ever
    produce. A `native_confirmation` is the whole reason a derived row may
    be trusted later; if it can drift from the workflow, the freeze's
    provenance is decoration.

    So: the trigger clause is DERIVED from the `on:` block and must appear
    verbatim wherever the repository describes when CI runs; no site may
    claim a push to a branch the workflow does not list, or an unqualified
    "every push"; and the two places that describe the matrix -- this
    module's docstring and the release attestation -- must name exactly the
    interpreters the matrix runs. Editing the workflow's triggers or its
    matrix without editing the prose fails here.
    """
    clause = ci_trigger_clause()
    triggers = ci_triggers()
    pythons = ci_battery_pythons()
    failures: list[str] = []
    sources: list[tuple[str, str, bool]] = [
        (ATTESTATION.relative_to(ROOT).as_posix(), ATTESTATION.read_text(encoding="utf-8"), True),
        (f"{Path(__file__).name} module docstring", __doc__ or "", True),
    ]
    for version, row in sorted(fixture().get("unicode_scoped", {}).items()):
        prov = row.get("provenance") if isinstance(row, dict) else None
        said = prov.get("native_confirmation") if isinstance(prov, dict) else None
        if isinstance(said, str):
            sources.append((f"legacy_freeze.json unicode_scoped[{version}].provenance.native_confirmation",
                            said, False))
    sites = 0
    for label, text, claims_matrix in sources:
        sentences = _ci_claim_sentences(text)
        if not sentences:
            if claims_matrix:
                failures.append(f"{label} no longer says anything about {CI_WORKFLOW.name}: what CI witnesses "
                                f"natively is why a derived Unicode row may be believed, and it may not go silent")
            continue
        sites += len(sentences)
        for sentence in sentences:
            if clause not in sentence:
                failures.append(f"{label} names {CI_WORKFLOW.name} but does not carry the workflow's actual "
                                f"trigger clause {clause!r}:\n    {sentence}")
            if triggers["push_branches"] is not None and re.search(r"every push(?! to )", sentence):
                failures.append(f'{label} says "every push" unqualified, but the workflow\'s push trigger is '
                                f"limited to {triggers['push_branches']}:\n    {sentence}")
            for match in re.finditer(r"push(?:es)? to ([A-Za-z0-9_./-]+)", sentence):
                branch = match.group(1).rstrip(".,;:")
                if branch not in (triggers["push_branches"] or [branch]):
                    failures.append(f"{label} claims CI runs on a push to {branch!r}; the workflow's push trigger "
                                    f"lists {triggers['push_branches']}")
            for banned in ("first push of this branch", "every push of this branch", "from the first push"):
                if banned in sentence:
                    failures.append(f"{label} claims CI runs {banned!r}, which the workflow's triggers do not do")
        if claims_matrix:
            named = sorted({v for v in re.findall(r"\b(\d+\.\d+)\b", " ".join(sentences)) if v.startswith("3.")},
                           key=lambda v: tuple(int(part) for part in v.split(".")))
            if named != pythons:
                failures.append(f"{label} says CI covers CPython {named}; the battery matrix in "
                                f"{CI_WORKFLOW.name} runs {pythons}")
    if sites < 3:
        failures.append(f"only {sites} sentence(s) in the repository describe {CI_WORKFLOW.name}: the attestation, "
                        f"this module and the confirmed Unicode rows all have to say when CI compares them")
    return check(f"every sentence naming {CI_WORKFLOW.name} carries the workflow's own trigger clause "
                 f"({clause}) and the matrix it really runs ({', '.join(pythons)})", not failures,
                 "\n".join(failures))


def test_a_fixture_row_that_cannot_be_trusted_fails_the_whole_suite():
    """The refusal, driven END TO END rather than through the helper.

    `test_an_unpinned_unicode_version_fails_the_freeze` drives
    `resolve_unicode_scoped` directly, so it proves the helper refuses but
    not that its caller acts on the refusal -- one careless `if expected is
    None: expected = live_row` away from a suite that passes anyway. This
    repoints `FIXTURE` at a mutated COPY (the real fixture is never written)
    and runs the real check, twice:

      * the running runtime's row deleted -- the freeze must fail with the
        unseen-database message, not fall back to the live digests;
      * the running row present but one pinned scorer digest corrupted --
        the freeze must fail on the comparison, which is what shows the row
        is compared strictly rather than merely looked up.
    """
    global FIXTURE
    real, pinned = FIXTURE, fixture()
    scoped = pinned.get("unicode_scoped", {})
    failures: list[str] = []
    # On a runtime whose database IS pinned, the two mutations are "delete
    # that row" and "tamper with it". On a runtime whose database is NOT
    # pinned -- where the deletion is already the live state -- the tampered
    # row is minted for this version from the live digests instead, so both
    # cases are still measured rather than skipped.
    base_row = copy.deepcopy(scoped[NATIVE_UNICODE_VERSION]) if NATIVE_UNICODE_VERSION in scoped else {
        **copy.deepcopy(live_unicode_scoped(NATIVE_UNICODE_VERSION)),
        "provenance": {"method": "derived-by-substitution",
                       "generated_on": "synthetic",
                       "native_confirmation": "SYNTHETIC: minted inside this guard, never written to the fixture"},
    }
    without = {**pinned, "unicode_scoped": {v: r for v, r in scoped.items() if v != NATIVE_UNICODE_VERSION}}
    corrupted_row = base_row
    corrupted_row["scorer"]["parse_policy_digest"] = "0" * 64
    corrupted = {**pinned, "unicode_scoped": {**scoped, NATIVE_UNICODE_VERSION: corrupted_row}}
    workspace = Path(tempfile.mkdtemp(prefix="legacy-freeze-guard-"))
    try:
        for name, mutated, must_say in (
            ("the running row deleted", without, ("is NOT pinned", "--regenerate-unicode-scoped")),
            ("one pinned scorer digest corrupted", corrupted, ("parse_policy_digest", "0" * 64)),
        ):
            path = workspace / (name.replace(" ", "_") + ".json")
            path.write_text(json.dumps(mutated, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
            captured = io.StringIO()
            FIXTURE = path
            try:
                with contextlib.redirect_stdout(captured):
                    passed = test_the_unicode_scoped_digests_are_pinned_for_this_runtime()
            finally:
                FIXTURE = real
            said = captured.getvalue()
            if passed:
                failures.append(f"with {name}, the freeze still PASSED end to end")
            for token in must_say:
                if token not in said:
                    failures.append(f"with {name}, the reported failure never mentions {token!r}: {said.strip()!r}")
    finally:
        FIXTURE = real
        shutil.rmtree(workspace, ignore_errors=True)
    if FIXTURE != real or fixture() != pinned:
        failures.append("the guard did not restore the real fixture afterwards")
    return check("the pinned-row check itself fails end to end when the running runtime's row is missing, and "
                 "when it is present but a pinned digest was tampered with", not failures, "\n".join(failures))


def test_the_frozen_scorer_bytes():
    """The scorer's invariant identity: its own bytes and version numbers.
    Its two Unicode-scoped digests (`parse_policy_digest`,
    `scorer_contract_digest`) are checked in
    `test_the_unicode_scoped_digests_are_pinned_for_this_runtime`."""
    want = fixture()["scorer"]
    got = live()["scorer"]
    problems = []
    raw = SCORER_SOURCE.read_bytes()
    if b"\r" in raw:
        problems.append(f"{SCORER_SOURCE.relative_to(ROOT)} carries CR bytes: the checkout is not LF "
                        f"(.gitattributes says eol=lf); the byte digest cannot be compared")
    for key in sorted(want):
        _diff(f"scorer {key}", want[key], got[key], problems)
    _diff("engine id", "candidate/1", got["engine"], problems)
    return check("candidate/committed.py is byte-identical to the freeze and the candidate/1 scorer's engine id "
                 "and version numbers are the pinned ones", not problems, "\n".join(problems))


def test_the_contract_4_view_is_pinned():
    want = fixture()["episode_contract"]
    got = live()["episode_contract"]
    problems = []
    for key in sorted(want):
        _diff(f"episode contract {key}", want[key], got[key], problems)
    _diff("EPISODE_CONTRACT_VERSION", 4, got["version"], problems)
    _diff("EPISODE_CONTRACT_SCHEMA", "piv.episode-contract/2", got["schema"], problems)
    _diff("PUBLIC_FILES", list(LEGACY_PUBLIC_FILES), got["public_files"], problems)
    other = pinned_episode_contract_digest()
    if other is None:
        problems.append(f"{EPISODE_CONTRACT_TEST.name} no longer carries a literal EPISODE_CONTRACT_DIGEST pin")
    else:
        _diff(f"the pin in {EPISODE_CONTRACT_TEST.name}", want["digest"], other, problems)
    # the no-argument form stays the legacy answer whatever a later profile
    # dispatcher adds: the same digest through the module function and the
    # default ceiling argument
    _diff("episode_contract_digest(MAX_EPISODE_OUTPUT_TOKENS)", want["digest"],
          env_mod.episode_contract_digest(env_mod.MAX_EPISODE_OUTPUT_TOKENS), problems)
    return check("the contract-4 episode view digest, version 4 / piv.episode-contract/2, the eight PUBLIC_FILES, "
                 "write_ledger and submit are the pinned ones, and test_episode_contract pins the same digest",
                 not problems, "\n".join(problems))


def test_the_served_world_dir_is_bank_recon_001():
    """`WORLD_DIR` is the on-disk copy the serving door seeds from; it must be
    the projected bytes of the original task, name for name."""
    pinned = fixture()["tasks"]["bank_recon_001"]["files"]
    problems = []
    on_disk = {p.name: sha256(p.read_bytes()) for p in env_mod.WORLD_DIR.iterdir() if p.is_file()}
    if set(on_disk) != set(pinned):
        problems.append(f"world dir names != the frozen files: {set(on_disk) ^ set(pinned)}")
    for name in sorted(set(on_disk) & set(pinned)):
        if on_disk[name] != pinned[name]:
            problems.append(f"{name}: the served copy differs from bank_recon_001's projected bytes")
    return check("the served world directory is byte-identical to bank_recon_001's frozen public files",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_fixture_is_well_formed,
    test_every_frozen_task_is_still_registered,
    test_every_legacy_public_file_is_byte_identical,
    test_every_legacy_task_contract_is_unchanged,
    test_the_unicode_scoped_digests_are_pinned_for_this_runtime,
    test_an_unpinned_unicode_version_fails_the_freeze,
    test_the_substitution_reaches_every_reader_of_unidata_version,
    test_a_fixture_row_that_cannot_be_trusted_fails_the_whole_suite,
    test_the_ci_claims_match_the_workflow,
    test_the_frozen_scorer_bytes,
    test_the_contract_4_view_is_pinned,
    test_the_served_world_dir_is_bank_recon_001,
]


def regenerate() -> int:
    """Rewrite the invariant fields AND this interpreter's own
    `unicode_scoped[unicodedata.unidata_version]` row from a true (no
    substitution) live run, and say what moved. Every OTHER pinned
    `unicode_scoped` version — generated elsewhere by substitution, e.g.
    `--regenerate-unicode-scoped 14.0.0` — is carried over untouched. A
    deliberate act for a release that means to move the legacy surface;
    never run by the battery."""
    now = live()
    real_version = NATIVE_UNICODE_VERSION
    before = fixture() if FIXTURE.exists() else None
    unicode_scoped = dict(before.get("unicode_scoped", {})) if before else {}
    row = live_unicode_scoped(real_version)
    unicode_scoped[real_version] = {**row, "provenance": unicode_provenance(
        real_version, row, unicode_scoped.get(real_version), None)}
    now = {**now, "unicode_scoped": unicode_scoped}
    FIXTURE.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if before is None:
        print(f"wrote {FIXTURE.relative_to(ROOT)}: {now['task_count']} tasks, unicode {real_version}")
        return 0
    moved = []
    for section in ("episode_contract", "scorer"):
        for key in sorted(set(before.get(section, {})) | set(now[section])):
            if before.get(section, {}).get(key) != now[section].get(key):
                moved.append(f"{section}.{key}")
    for task_id in sorted(set(before.get("tasks", {})) | set(now["tasks"])):
        a, b = before.get("tasks", {}).get(task_id), now["tasks"].get(task_id)
        if a is None or b is None:
            moved.append(f"tasks.{task_id}: {'added' if a is None else 'removed'}")
            continue
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                moved.append(f"tasks.{task_id}.{key}")
    before_uv = before.get("unicode_scoped", {}).get(real_version, {})
    now_uv = now["unicode_scoped"][real_version]
    for key in sorted(set(before_uv.get("scorer", {})) | set(now_uv["scorer"])):
        if before_uv.get("scorer", {}).get(key) != now_uv["scorer"].get(key):
            moved.append(f"unicode_scoped.{real_version}.scorer.{key}")
    for task_id in sorted(set(before_uv.get("tasks", {})) | set(now_uv["tasks"])):
        if before_uv.get("tasks", {}).get(task_id) != now_uv["tasks"].get(task_id):
            moved.append(f"unicode_scoped.{real_version}.tasks.{task_id}")
    print(f"rewrote {FIXTURE.relative_to(ROOT)}: {len(moved)} pinned value(s) moved (unicode {real_version})")
    for line in moved:
        print(f"  {line}")
    return 0


def regenerate_unicode_scoped(version: str, note: str | None = None) -> int:
    """Add or refresh ONLY `unicode_scoped[version]`, computed by
    substitution on this interpreter (or directly, if `version` happens to
    be this interpreter's real `unicodedata.unidata_version`). Leaves the
    invariant fields and every other pinned Unicode version untouched. This
    is how a version this machine cannot natively run (e.g. 14.0.0, CPython
    3.11's database, on this CPython 3.12 machine) gets pinned at all.

    The row is stamped with its provenance. A derived row is written as
    PENDING native confirmation unless `--note` says where a runtime that
    actually ships this database confirmed it — the freeze will not invent
    that sentence for you, because nothing on this interpreter can."""
    if not FIXTURE.exists():
        print(f"{FIXTURE.relative_to(ROOT)} does not exist; run --regenerate first")
        return 1
    before = fixture()
    row = live_unicode_scoped(version)
    previous = before.get("unicode_scoped", {}).get(version)
    provenance = unicode_provenance(version, row, previous, note)
    before.setdefault("unicode_scoped", {})[version] = {**row, "provenance": provenance}
    FIXTURE.write_text(json.dumps(before, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    technique = ("direct" if version == NATIVE_UNICODE_VERSION else
                 f"substitution (this interpreter's real unidata_version is {NATIVE_UNICODE_VERSION})")
    print(f"{'refreshed' if previous is not None else 'added'} unicode_scoped[{version}] in "
          f"{FIXTURE.relative_to(ROOT)} via {technique}")
    print(f"  provenance.method              = {provenance['method']}")
    print(f"  provenance.native_confirmation = {provenance['native_confirmation']}")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:]
    if "--regenerate" in argv:
        return regenerate()
    if "--regenerate-unicode-scoped" in argv:
        i = argv.index("--regenerate-unicode-scoped")
        if i + 1 >= len(argv):
            print('usage: tests/test_legacy_freeze.py --regenerate-unicode-scoped VERSION [--note "..."]')
            return 2
        note = None
        if "--note" in argv:
            j = argv.index("--note")
            if j + 1 >= len(argv):
                print('usage: tests/test_legacy_freeze.py --regenerate-unicode-scoped VERSION [--note "..."]')
                return 2
            note = argv[j + 1]
        return regenerate_unicode_scoped(argv[i + 1], note)
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
