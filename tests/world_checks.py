"""`beancount_ledger.world_checks`, under the name the suites import it by.

THE BATTERY MOVED INTO THE RUNTIME PACKAGE (round 17, decision 4). The
construction path runs it — `graph/cash_admit.world_checker_problems` calls
`check_derived` on every rendered variant of every attempt — and the wheel
ships no tests, so a battery living only here meant an installed package
could serve but could not mint. It is now
`beancount_ledger/world_checks.py`.

This file is a SHIM, not a copy: it binds the module name `world_checks` to
that one module object, so `from world_checks import check_world_task` in a
suite and `from .. import world_checks` in the construction path are the same
code with the same identity. Nothing is re-exported by hand, so a private
name a suite reaches for (`_family_gates`) resolves exactly as it did.

The two `sys.path` entries the old module inserted as a side effect are kept,
because suites imported through this name relied on them.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for _p in (str(ROOT), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from beancount_ledger import world_checks as _impl  # noqa: E402

sys.modules[__name__] = _impl
