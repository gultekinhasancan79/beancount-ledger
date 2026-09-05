"""Verify ONE hand-authored world module, before it is registered.

    python tests/verify_world.py beancount_ledger/graph/worlds/<module>.py
    python tests/verify_world.py beancount_ledger/graph/worlds/<module>.py --summary

The module is imported BY PATH, so a world still being written — not listed
in `worlds/__init__.REGISTRY`, not importable by name — can be checked while
it is written. It must define `WORLD` (a `graph.schema.World`) and `TASKS`
(a dict of task id -> `graph.derive.TaskSpec`, as `alpine_2025_11.py` does);
every task in it is checked.

Exit 0 when no task reported a problem, 1 otherwise. Warnings never change
the exit code: they are the generator's readability heuristics, and a
hand-authored world is allowed to be deliberately harder than a drawn one so
long as the identifiability gate still passes.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for _p in (str(ROOT), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from world_checks import check_world_task, summarize  # noqa: E402

WORLDS_PACKAGE = "beancount_ledger.graph.worlds"
WORLDS_PARTS = ("beancount_ledger", "graph", "worlds")


def load_world_module(path):
    """Import a world module from its file.

    A world module uses relative imports (`from ..project import ...`), so
    it is loaded under its real dotted name whenever it sits in the worlds
    package directory — `spec_from_file_location` with a bare name gives the
    module an empty `__package__` and the relative imports fail. A module
    outside that directory is loaded standalone, which works as long as it
    imports absolutely.
    """
    path = Path(path).resolve()
    if not path.is_file():
        raise SystemExit(f"no such file: {path}")
    name = path.stem
    if path.parent == ROOT.joinpath(*WORLDS_PARTS):
        importlib.import_module(WORLDS_PACKAGE)     # the parent must exist for `from ..x import y`
        name = f"{WORLDS_PACKAGE}.{name}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path} as a module")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    return module


def tasks_of(module) -> dict:
    """The module's task registry: `TASKS` when it has one, else every
    module-level TaskSpec, keyed by id."""
    tasks = getattr(module, "TASKS", None)
    if isinstance(tasks, dict) and tasks:
        return dict(tasks)
    from beancount_ledger.graph.derive import TaskSpec

    found = {t.id: t for t in vars(module).values() if isinstance(t, TaskSpec)}
    return found


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    want_summary = False
    for flag in ("--summary", "-s"):
        while flag in argv:
            argv.remove(flag)
            want_summary = True
    if len(argv) != 1:
        print(__doc__.strip())
        return 2

    path = Path(argv[0])
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    module = load_world_module(path)

    world = getattr(module, "WORLD", None)
    if world is None:
        print(f"FAIL  {path}: the module defines no WORLD")
        return 1
    tasks = tasks_of(module)
    if not tasks:
        print(f"FAIL  {path}: the module defines no TASKS (and no module-level TaskSpec)")
        return 1

    print(f"world {world.id}   module {path}")
    print(f"tasks {', '.join(sorted(tasks))}")
    failed = 0
    for task_id in sorted(tasks):
        task = tasks[task_id]
        problems, warnings = check_world_task(world, task, source_path=path)
        status = "PASS" if not problems else "FAIL"
        note = "no problems" if not problems else f"{len(problems)} problem(s)"
        if warnings:
            note += f", {len(warnings)} warning(s)"
        print(f"\n{status}  {world.id}/{task_id}: {note}")
        for problem in problems:
            for i, line in enumerate(str(problem).splitlines()):
                print(f"      {'- ' if i == 0 else '  '}{line}")
        for warning in warnings:
            print(f"      {warning}")
        if problems:
            failed += 1
        if want_summary:
            print()
            print(summarize(world, task))

    print(f"\n{len(tasks) - failed} of {len(tasks)} task(s) clean")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
