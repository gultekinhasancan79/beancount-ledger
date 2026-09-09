"""Authored worlds: irreducible facts only, and the task registry.

Every module here states what happened at one small company in one month
(amounts, dates, counterparties, documents, rails, clearing dates) and names
the recognitions its task plants. Nothing derived is typed: the projector
renders the eight public files and the private expected ledger from the
facts, and the scorer is bound to that derivation. `tests/verify_world.py`
checks a module before it is registered; `tests/test_worlds.py` re-checks
every registry entry in the battery.

Each module exposes `WORLD` and `TASKS` (task id -> TaskSpec). Task ids are
free of ':' so the serving door never confuses them with generated selectors.
"""

from . import (
    alpine_2025_11,
    bluewater_2025_10,
    falcon_2026_02,
    hawthorn_2025_12,
    ironwood_2025_10,
    maple_2025_12,
    oakridge_2026_03,
    redwood_2025_11,
    silverbrook_2025_11,
    thistle_2026_01,
)
from .alpine_2025_11 import BANK_RECON_001, WORLD as ALPINE_2025_11  # noqa: F401  the original, kept by name

#: Registered in the order the tasks were authored: the bank reconciliation
#: the environment shipped with, then one world per accounting workflow.
WORLD_MODULES = (
    alpine_2025_11,       # bank_recon_001            bank reconciliation, month-end close
    ironwood_2025_10,     # ap_payment_run_001        accounts-payable payment run
    silverbrook_2025_11,  # ar_collections_001        receivables and collections
    thistle_2026_01,      # bank_feed_categorisation_001  card spend categorised from the bank feed
    falcon_2026_02,       # expense_reports_001       employee expense claims reimbursed by cheque
    hawthorn_2025_12,     # payroll_001               net pay by cheque, withholdings remitted
    bluewater_2025_10,    # sales_tax_remittance_001  sales tax collected and remitted to the state
    oakridge_2026_03,     # fixed_assets_001          equipment capitalised on payment, repairs expensed
    redwood_2025_11,      # intercompany_transfers_001  cash advanced to a group company
    maple_2025_12,        # month_end_close_001       prepaid insurance, bank charges, receipts
)

# task id -> (world, task spec). The production composition root reads
# this and nothing else to build an environment.
REGISTRY: dict = {}
for _module in WORLD_MODULES:
    for _task_id, _task in _module.TASKS.items():
        if _task_id in REGISTRY:
            raise RuntimeError(f"task id {_task_id!r} is registered twice (second time by {_module.__name__})")
        REGISTRY[_task_id] = (_module.WORLD, _task)
del _module, _task_id, _task

# The cash-application family: five variants of one company-month
# (`_bowline.py`), each projecting eleven public files and deriving the
# truth register `application/1` scores against. Authored, checked and held
# to gates (l), (m) and (n) in step 4; REGISTERED here now that the
# environment step has landed — the serving door resolves the episode
# profile from the derived inputs (`episode_profile`), mounts eleven public
# files instead of eight, advertises the seventh tool and scores the second
# deliverable. They load exactly like every other hand-authored id, with no
# evaluator secret and no manifest: `load_environment("cash_application_001")`
# and the rest.
#
# `CASH_APPLICATION_REGISTRY` stays as its own mapping beside `REGISTRY`, so
# a test can name the family without pattern-matching on task ids, and so
# the legacy 95 remain enumerable as `REGISTRY` minus this.
from . import (  # noqa: E402
    bowline_2026_04_c1,
    bowline_2026_04_c2,
    bowline_2026_04_c3,
    bowline_2026_04_c4,
    bowline_2026_04_c5,
)

CASH_APPLICATION_MODULES = (
    bowline_2026_04_c1,   # cash_application_001  canonical minimum
    bowline_2026_04_c2,   # cash_application_002  advice missing for R3; the reference names the invoices
    bowline_2026_04_c3,   # cash_application_003  short-pays both sides of the tolerance; the write-off omitted
    bowline_2026_04_c4,   # cash_application_004  short-pays both sides of the tolerance; R3 transposed
    bowline_2026_04_c5,   # cash_application_005  a credit exceeding the invoice's remaining balance
)

#: The 95 shipped ids, frozen at the moment before the family joins them:
#: `tests/test_legacy_freeze.py` and `tests/test_worlds.py` read this to say
#: "the legacy surface" without listing ninety-five strings.
LEGACY_TASK_IDS = tuple(REGISTRY)

CASH_APPLICATION_REGISTRY: dict = {}
for _module in CASH_APPLICATION_MODULES:
    for _task_id, _task in _module.TASKS.items():
        if _task_id in REGISTRY or _task_id in CASH_APPLICATION_REGISTRY:
            raise RuntimeError(f"task id {_task_id!r} is registered twice (second time by {_module.__name__})")
        _entry = (_module.WORLD, _task)
        CASH_APPLICATION_REGISTRY[_task_id] = _entry
        REGISTRY[_task_id] = _entry
del _module, _task_id, _task, _entry
