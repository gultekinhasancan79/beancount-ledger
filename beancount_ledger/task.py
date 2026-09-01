"""Task loading and its audits. Not scoring.

Separated from the scorer so that production code can import the task
without importing any engine, and so the structural test "no production
module imports a text-scoring API" has a clean boundary to assert.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Account names that read like a suspense or plug account.
PLUG_PATTERNS = re.compile(
    r"(suspense|plug|clearing|misc|miscellaneous|other|adjust|rounding|unknown|temp|tmp)",
    re.IGNORECASE,
)


def audit_allowed_accounts(allowed: list) -> list[str]:
    """Allowed accounts whose names read like a plug. A task defect, not a
    submission defect.

    The plug check used to run over every account in the submission, allowed or
    not, on the reasoning that a future chart should not be able to smuggle one
    in. At n=1 that is free — this chart has no such account. At scale it is a
    trap: `Expenses:Other`, `Expenses:Miscellaneous` and `Assets:Clearing` are
    ordinary lines in a real chart of accounts, and a generator that emits one
    would produce a task where posting to a legitimate, explicitly allowed
    account costs the largest penalty in the system. The task would be
    unwinnable and nothing would say so.

    So the check moves. The scorer flags plugs only among accounts the task did
    not allow; the chart itself is audited once, when the task is loaded, and a
    chart that names an allowed account like a plug is rejected as malformed.
    Same rule, applied to the party that can actually fix it.
    """
    return [a for a in allowed if PLUG_PATTERNS.search(a)]


def load_task(path: str | Path) -> dict:
    """Load a task definition, refusing one that cannot be solved.

    An allowed account that reads like a plug would make every correct
    submission score as if it had invented a suspense account; that is a
    defect in the task, and it is refused here rather than charged to the
    agent.
    """
    task = json.loads(Path(path).read_text(encoding="utf-8"))
    plugs = audit_allowed_accounts(task.get("allowed_accounts", []))
    if plugs:
        raise ValueError(
            f"task {task.get('id')!r} allows account(s) that read like a plug: "
            f"{plugs}; the chart must be fixed before the task can be used"
        )
    return task
