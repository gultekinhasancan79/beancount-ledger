"""Every hand-authored world in the registry, held to the mint's standard.

A generated world cannot exist unless `mint._require_public_uniqueness`
agrees that its public bytes admit exactly one reading and that the reading
is the planted one. A hand-authored world is written by a person and put
straight into `worlds.REGISTRY`, so the same properties have to be asserted
somewhere or they are simply assumed. This is that somewhere, over every
registry entry rather than over Alpine by name.

What is checked per entry lives in `tests/world_checks.py` — the world
schema, derivation and the contract door, the golden at 1.0 and complete,
the untouched original below 1.0 with nothing resolved — or, for a task that
plants nothing, already worth 1.0 and complete with no item state at all —
the MERGED trap the
scorer's `shapes & _txn_shape(t)` predicate leaves open, public-only
identifiability under the shared repair key, leaked private ids, derived
numbers typed into the authored source, generator name-pool collisions and
the policy headings. Warnings (the generator's readability heuristics) are
printed and do not fail the suite.

    python tests/test_worlds.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402

from world_checks import check_world_task  # noqa: E402

WORLDS_DIR = ROOT / "beancount_ledger" / "graph" / "worlds"
WORLDS_PACKAGE = "beancount_ledger.graph.worlds"


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:40]:
            print(f"      {line}")
    return ok


def module_by_task_id() -> dict:
    """task id -> the .py file that authored it.

    The `World` class is shared by every world, so the source file cannot be
    recovered from the object; the modules are scanned instead, and a task
    id is claimed by the module whose `TASKS` carries it. A registry entry
    no module claims is itself a failure (below): the derived-literal scan
    would silently not run for it.
    """
    owners: dict = {}
    for path in sorted(WORLDS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = importlib.import_module(f"{WORLDS_PACKAGE}.{path.stem}")
        for task_id in getattr(module, "TASKS", {}):
            owners.setdefault(task_id, []).append(path)
    return owners


def test_every_registered_world_and_task():
    owners = module_by_task_id()
    results = []
    warned = []
    problems = []
    for task_id in sorted(REGISTRY):
        world, task = REGISTRY[task_id]
        claimed = owners.get(task_id, [])
        if len(claimed) != 1:
            problems.append(f"{task_id}: {len(claimed)} world module(s) in {WORLDS_DIR.name}/ define this task id "
                            f"({[p.name for p in claimed]}); the source of the task is ambiguous")
            source = claimed[0] if claimed else None
        else:
            source = claimed[0]
        found, warnings = check_world_task(world, task, source_path=source)
        problems.extend(found)
        warned.extend(warnings)
        results.append((task_id, world.id, source.name if source else "?", len(found), len(warnings)))
    for task_id, world_id, module, bad, warns in results:
        print(f"      {world_id}/{task_id} [{module}]: {bad} problem(s), {warns} warning(s)")
    for warning in warned:
        print(f"      {warning}")
    return check(f"every world/task in REGISTRY ({len(REGISTRY)}) derives, scores its golden 1.0, leaves its original "
                 f"unresolved (or, where nothing is planted, already worth 1.0 and complete), reads back uniquely "
                 f"as the planted repair, and leaks no id or derived literal",
                 not problems, "\n".join(problems))


def test_the_registry_is_not_empty():
    return check(f"the registry carries at least one hand-authored task ({sorted(REGISTRY)})", bool(REGISTRY))


TESTS = [
    test_the_registry_is_not_empty,
    test_every_registered_world_and_task,
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
