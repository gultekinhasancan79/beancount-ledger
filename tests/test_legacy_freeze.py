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
    and balances included), the `task_contract_digest` over
    `ContractInputs.contract_view()`, the `environment_digest` of the loaded
    scoring environment, and both digests of the golden deliverable;
  * the frozen scorer: the raw bytes digest of
    `beancount_ledger/candidate/committed.py`, the engine id, the scorer
    contract digest, the parse-policy digest and the validator/contract
    versions;
  * the contract-4 episode view: `episode_contract_digest()` at the default
    ceiling (the pin `tests/test_episode_contract.py` already holds — read
    from that file's source here so the two pins cannot diverge), the
    contract version and schema, the eight-name `PUBLIC_FILES`, the single
    write tool and the terminal tool;
  * the served legacy world directory, which is `bank_recon_001`'s projected
    bytes on disk.

Comparison is exact: an extra file, a missing file, a moved byte, a changed
digest or a renamed task fails. A task registered outside the freeze is
reported and does not fail — a new family is not a change to the legacy one —
but every frozen task must still be registered.

Re-pinning is a deliberate act, never a side effect of a green run:

    python tests/test_legacy_freeze.py                # verify
    python tests/test_legacy_freeze.py --regenerate   # rewrite the fixture, print what moved
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
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
FIXTURE_SCHEMA = "piv.legacy-freeze/1"
SCORER_SOURCE = ROOT / "beancount_ledger" / "candidate" / "committed.py"
EPISODE_CONTRACT_TEST = ROOT / "tests" / "test_episode_contract.py"

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
# --------------------------------------------------------------------------

def task_snapshot(task_id: str) -> dict:
    """Everything the freeze holds for one task, recomputed from the registry
    through the production doors: `derive_contract` for the bytes and the
    contract view, `load_contract` for the scoring environment."""
    world, task = REGISTRY[task_id]
    _, inputs = derive_contract(world, task)
    env = K.load_contract(inputs)
    golden = env_mod.digests_of(inputs.golden_text.encode("utf-8"))
    return {
        "world_id": inputs.world_id,
        "public_task_id": public_task_id(inputs),
        "files": {name: sha256(data) for name, data in inputs.public_files},
        "graph_digest": inputs.graph_digest,
        "mutation_plan_digest": inputs.mutation_plan_digest,
        "view_digests": {name: digest for name, digest in inputs.view_digests},
        "task_contract_digest": env.task_contract_digest,
        "environment_digest": env.environment_digest,
        "scorer_contract_digest": env.scorer_contract_digest,
        "parse_policy_digest": env.parse_policy_digest,
        "engine": env.engine.id,
        "golden_stored_bytes_digest": golden["stored_bytes_digest"],
        "golden_logical_text_digest": golden["logical_text_digest"],
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
            "scorer_contract_digest": C.scorer_contract_digest(),
            "parse_policy_digest": C.parse_policy_digest(),
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


def live() -> dict:
    global _LIVE
    if _LIVE is None:
        _LIVE = live_snapshot()
    return _LIVE


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _diff(label: str, want, got, problems: list) -> None:
    if want != got:
        problems.append(f"{label}: pinned {want!r}, now {got!r}")


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
    return check(f"the fixture pins {LEGACY_TASK_COUNT} tasks x {len(LEGACY_PUBLIC_FILES)} files under schema "
                 f"{FIXTURE_SCHEMA}", not problems, "\n".join(problems))


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
    """The identities the scorer and the manifest already bind per task."""
    pinned = fixture()["tasks"]
    now = live()["tasks"]
    keys = ("graph_digest", "mutation_plan_digest", "task_contract_digest", "environment_digest",
            "scorer_contract_digest", "parse_policy_digest", "engine",
            "golden_stored_bytes_digest", "golden_logical_text_digest")
    problems = []
    for task_id in sorted(pinned):
        if task_id not in now:
            continue
        want, got = pinned[task_id], now[task_id]
        for key in keys:
            _diff(f"{task_id}: {key}", want[key], got[key], problems)
        _diff(f"{task_id}: view digests", want["view_digests"], got["view_digests"], problems)
    return check(f"graph, plan, view, task-contract, environment and golden digests of the {len(pinned)} legacy "
                 f"tasks are the pinned ones", not problems, "\n".join(problems))


def test_the_frozen_scorer_bytes():
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
    return check("candidate/committed.py is byte-identical to the freeze and the candidate/1 scorer contract, "
                 "parse policy and versions are the pinned ones", not problems, "\n".join(problems))


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
    test_the_frozen_scorer_bytes,
    test_the_contract_4_view_is_pinned,
    test_the_served_world_dir_is_bank_recon_001,
]


def regenerate() -> int:
    """Rewrite the fixture from the live snapshot and say what moved. A
    deliberate act for a release that means to move the legacy surface;
    never run by the battery."""
    now = live()
    before = fixture() if FIXTURE.exists() else None
    FIXTURE.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if before is None:
        print(f"wrote {FIXTURE.relative_to(ROOT)}: {now['task_count']} tasks")
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
    print(f"rewrote {FIXTURE.relative_to(ROOT)}: {len(moved)} pinned value(s) moved")
    for line in moved:
        print(f"  {line}")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--regenerate" in sys.argv[1:]:
        return regenerate()
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
