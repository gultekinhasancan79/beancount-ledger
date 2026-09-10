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
`unicodedata.unidata_version` (`"15.0.0"` on CPython 3.12, `"14.0.0"` on
3.11), one row per version holding `{"scorer": {...}, "tasks": {task_id:
{...}}}`. The Unicode database enters these views ONLY through that version
string — nothing else in view construction reads live Unicode tables — so a
row for a version this interpreter is not running can be DERIVED by
substituting the version string into the same view-building code
(`substituted_unicode_version` below) rather than requiring an interpreter
of that vintage to generate it.

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
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import sys
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
FIXTURE_SCHEMA = "piv.legacy-freeze/2"
SCORER_SOURCE = ROOT / "beancount_ledger" / "candidate" / "committed.py"
EPISODE_CONTRACT_TEST = ROOT / "tests" / "test_episode_contract.py"

#: The two scorer-level and two per-task digest families that legitimately
#: vary with `unicodedata.unidata_version` (see the module docstring).
SCORER_UNICODE_KEYS = ("parse_policy_digest", "scorer_contract_digest")
TASK_UNICODE_KEYS = ("task_contract_digest", "environment_digest")

#: The version this repository's own Python (3.12) ships. Every fixture row
#: is either this native, directly-computed one, or derived from it by
#: substitution (see `resolve_unicode_scoped`).
ANCHOR_UNICODE_VERSION = "15.0.0"

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

class _FakeUnicodedata:
    """Delegates every attribute to the real `unicodedata` module except
    `unidata_version`, which is substituted. This is the whole mechanism:
    `canonical.parse_policy_view` and `canonical.scorer_contract_view` read
    `unicodedata.unidata_version` as plain data, so swapping the module
    object `canonical` sees reproduces exactly what an interpreter shipping
    that Unicode database would compute — verified against CI's real
    CPython-3.11 (Unicode 14.0.0) digests."""

    def __init__(self, version: str, real):
        self.unidata_version = version
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)


@contextlib.contextmanager
def substituted_unicode_version(version: str):
    """Within the block, `canonical.unicodedata.unidata_version` reads as
    `version`; every other `unicodedata` attribute is untouched. Restores
    the real module on exit, including on error."""
    real = C.unicodedata
    C.unicodedata = _FakeUnicodedata(version, real)
    try:
        yield
    finally:
        C.unicodedata = real


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
    real = unicodedata.unidata_version
    key = real if version is None else version
    if key not in _LIVE_UNICODE_SCOPED:
        ctx = contextlib.nullcontext() if key == real else substituted_unicode_version(key)
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
    return check(f"the fixture pins {LEGACY_TASK_COUNT} tasks x {len(LEGACY_PUBLIC_FILES)} files under schema "
                 f"{FIXTURE_SCHEMA}, with the Unicode-scoped digests under unicode_scoped", not problems,
                 "\n".join(problems))


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
    `test_the_unicode_scoped_digests_are_pinned_or_derived`."""
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


def resolve_unicode_scoped(pinned_scoped: dict, running_version: str, problems: list) -> dict | None:
    """The `{"scorer": {...}, "tasks": {...}}` row to check the running
    interpreter's live Unicode-scoped digests against.

    If `running_version` is pinned directly, that row IS the expected one —
    no substitution involved, the same strict comparison as every other
    frozen field. Otherwise (a future Python/Unicode database this fixture
    has never seen), derive one: substitute the version string back to
    `ANCHOR_UNICODE_VERSION` in the CURRENTLY RUNNING code and require that
    to reproduce the anchor's pinned digests exactly. That is the loud
    check — if the scorer, a task contract or the parse policy has actually
    changed, this substitution does NOT reproduce the anchor and every such
    drift is reported by version and by field. Only once that proof holds
    is the interpreter's own (unsubstituted) digest accepted as correct for
    `running_version`, since the Unicode database enters these views only
    through the version string.
    """
    if running_version in pinned_scoped:
        return pinned_scoped[running_version]
    if ANCHOR_UNICODE_VERSION not in pinned_scoped:
        problems.append(f"unicode {running_version}: not pinned, and no {ANCHOR_UNICODE_VERSION} anchor row to "
                        f"derive it from")
        return None
    print(f"      unicodedata.unidata_version={running_version} is not pinned in {FIXTURE.name}; deriving the "
          f"expected scorer/task-contract digests by substitution from the pinned {ANCHOR_UNICODE_VERSION} row.")
    anchor_pinned = pinned_scoped[ANCHOR_UNICODE_VERSION]
    anchor_live = live_unicode_scoped(ANCHOR_UNICODE_VERSION)      # substituted back to the anchor, on THIS code
    drift = []
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
        problems.append(f"unicode {running_version} is unpinned, and substituting this interpreter's code back to "
                        f"the anchor {ANCHOR_UNICODE_VERSION} does NOT reproduce the pinned anchor digests -- the "
                        f"scorer, a task contract or the parse policy changed independently of the Unicode "
                        f"database:\n" + "\n".join(drift))
        return None
    return live_unicode_scoped(running_version)


def test_the_unicode_scoped_digests_are_pinned_or_derived():
    """`parse_policy_digest`/`scorer_contract_digest` (scorer-level) and
    `task_contract_digest`/`environment_digest` (per task) legitimately vary
    with `unicodedata.unidata_version`. Selects the fixture row for the
    version THIS interpreter actually has; if that version was never pinned,
    derives the expected digests by substitution instead of failing or
    silently passing (see `resolve_unicode_scoped`)."""
    running_version = unicodedata.unidata_version
    pinned = fixture()
    pinned_scoped = pinned.get("unicode_scoped", {})
    pinned_tasks = pinned["tasks"]
    problems: list = []
    expected = resolve_unicode_scoped(pinned_scoped, running_version, problems)
    if expected is None:
        return check(f"scorer and per-task Unicode-scoped digests resolved for unicode {running_version}",
                     False, "\n".join(problems))
    live_row = live_unicode_scoped(running_version)
    for key in SCORER_UNICODE_KEYS:
        _diff_unicode(f"scorer.{key}", running_version, expected["scorer"][key], live_row["scorer"][key], problems)
    for task_id in sorted(pinned_tasks):
        if task_id not in live_row["tasks"] or task_id not in expected["tasks"]:
            continue                                       # reported by the registration check
        for key in TASK_UNICODE_KEYS:
            _diff_unicode(f"{task_id}.{key}", running_version, expected["tasks"][task_id][key],
                          live_row["tasks"][task_id][key], problems)
    origin = "pinned directly" if running_version in pinned_scoped else "derived by substitution from the anchor"
    return check(f"scorer_contract_digest, parse_policy_digest and the {len(pinned_tasks)} legacy tasks' "
                 f"task_contract_digest/environment_digest match unicode {running_version} ({origin})",
                 not problems, "\n".join(problems))


def test_the_frozen_scorer_bytes():
    """The scorer's invariant identity: its own bytes and version numbers.
    Its two Unicode-scoped digests (`parse_policy_digest`,
    `scorer_contract_digest`) are checked in
    `test_the_unicode_scoped_digests_are_pinned_or_derived`."""
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
    test_the_unicode_scoped_digests_are_pinned_or_derived,
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
    real_version = unicodedata.unidata_version
    before = fixture() if FIXTURE.exists() else None
    unicode_scoped = dict(before.get("unicode_scoped", {})) if before else {}
    unicode_scoped[real_version] = live_unicode_scoped(real_version)
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


def regenerate_unicode_scoped(version: str) -> int:
    """Add or refresh ONLY `unicode_scoped[version]`, computed by
    substitution on this interpreter (or directly, if `version` happens to
    be this interpreter's real `unicodedata.unidata_version`). Leaves the
    invariant fields and every other pinned Unicode version untouched. This
    is how a version this machine cannot natively run (e.g. 14.0.0, CPython
    3.11's database, on this CPython 3.12 machine) gets pinned at all."""
    if not FIXTURE.exists():
        print(f"{FIXTURE.relative_to(ROOT)} does not exist; run --regenerate first")
        return 1
    before = fixture()
    row = live_unicode_scoped(version)
    existed = version in before.get("unicode_scoped", {})
    before.setdefault("unicode_scoped", {})[version] = row
    FIXTURE.write_text(json.dumps(before, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    real = unicodedata.unidata_version
    technique = "direct" if version == real else f"substitution (this interpreter's real unidata_version is {real})"
    print(f"{'refreshed' if existed else 'added'} unicode_scoped[{version}] in {FIXTURE.relative_to(ROOT)} "
          f"via {technique}")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:]
    if "--regenerate" in argv:
        return regenerate()
    if "--regenerate-unicode-scoped" in argv:
        i = argv.index("--regenerate-unicode-scoped")
        if i + 1 >= len(argv):
            print("usage: tests/test_legacy_freeze.py --regenerate-unicode-scoped VERSION")
            return 2
        return regenerate_unicode_scoped(argv[i + 1])
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
