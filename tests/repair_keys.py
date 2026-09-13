"""`beancount_ledger.graph.repair_keys`, under the name the suites import it by.

The private half of the shared repair key moved into the runtime package with
`world_checks`, which imports it (round 17, decision 4). This file is a SHIM
that binds the module name `repair_keys` to that one module object; the
implementation and its docstring are there.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beancount_ledger.graph import repair_keys as _impl  # noqa: E402

sys.modules[__name__] = _impl
