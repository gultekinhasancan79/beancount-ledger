"""Backfills `prompt_schema_digest` (Codex T47 §2 last paragraph/Q5), and
optionally `budget_accounting` (adversarial-review finding 3, `--backfill-
accounting`), into ALREADY-ARCHIVED `reviews/budget_*.json` row files that
predate one or both fields — in particular the running batch this
milestone's measurement changes were built alongside, whose rows were
written by an OLDER `measure_budget.py`.

Simpler than replaying a git commit into a temp module (`git show
<commit>:path | exec`, fragile against `beancount_ledger.py`'s own relative
imports, which need the real package structure to resolve): given
`--from-checkout <path>` (a full `environments/beancount_ledger` checkout
root, containing `beancount_ledger/beancount_ledger.py`), imports THAT
checkout's package fresh — evicting any already-cached `beancount_ledger*`
modules first and inserting the checkout at the FRONT of `sys.path` so it
wins over this checkout's own package of the same name — and runs THIS
file's `measure_budget.compute_prompt_schema_digest` (the current, correct
algorithm) over it. That digest describes what SYSTEM_PROMPT/tool schema the
TARGET checkout actually served, which is what a batch minted under that
checkout observed — independent of which `measure_budget.py` version
happened to be running the measurement loop at the time.

`stamped_from` is NOT the bare checkout path (adversarial-review finding 3:
"path alone is not provenance" — a path can be re-checked-out, branch-
switched or edited after the fact without the path string changing at all).
Every stamped row instead gets a `stamped_from` DICT: the checkout path, the
SHA-256 of `beancount_ledger/beancount_ledger.py` AS READ (what actually
produced the digest, byte for byte), and the checkout's own `git rev-parse
HEAD` (`None` if the checkout is not a git repo or the command fails —
never silently omitted, never guessed).

`--backfill-accounting` additionally derives `budget_accounting` (via
`arm_table.derive_budget_accounting` — the SAME derivation `arm_table.py`
itself falls back to for a row missing the field, so a row stamped this way
and a row read live by `arm_table.py` without ever being stamped report the
IDENTICAL verdict) into any row lacking the field, marking
`budget_accounting_stamped: true` on that row so a reader can tell a live
"VALID/derived" apart from a value this script wrote after the fact. Rows
that already carry a field are left untouched either way.

    python tests/stamp_contract_digest.py --from-checkout C:\\path\\to\\other\\checkout\\environments\\beancount_ledger \\
        --backfill-accounting reviews/budget_nemotron-3-ultra-550b-a55b_2026-08-30_Ap_train1.json ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arm_table as AT  # noqa: E402 -- reuses derive_budget_accounting
import measure_budget as mb  # noqa: E402 -- never imports beancount_ledger at module level itself


def load_env_mod_from_checkout(checkout: Path):
    """Imports `beancount_ledger.beancount_ledger` fresh from `checkout`,
    evicting any already-cached module of that name first (so a later call
    in the SAME process, or an earlier import by something else in this
    process, cannot silently hand back a DIFFERENT checkout's package) and
    inserting `checkout` at `sys.path[0]` so Python's normal package import
    machinery resolves relative imports inside `beancount_ledger.py`
    correctly (a raw `exec` of the file's source, outside its package,
    cannot)."""
    for name in list(sys.modules):
        if name == "beancount_ledger" or name.startswith("beancount_ledger."):
            del sys.modules[name]
    sys.path.insert(0, str(checkout))
    from beancount_ledger import beancount_ledger as env_mod
    return env_mod


def checkout_provenance(checkout: Path) -> dict:
    """`{"checkout_path", "package_file_sha256", "git_head_sha"}` — a path
    alone is not provenance (adversarial-review finding 3): a checkout can
    move to a different commit without its filesystem path ever changing.
    The sha256 is over the EXACT bytes read to compute the digest; the git
    sha is best-effort (`None`, never raises, if the checkout is not a git
    repo or `git` is unavailable)."""
    package_file = checkout / "beancount_ledger" / "beancount_ledger.py"
    package_file_sha256 = hashlib.sha256(package_file.read_bytes()).hexdigest()
    git_head_sha = None
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(checkout),
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            git_head_sha = result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    return {"checkout_path": str(checkout), "package_file_sha256": package_file_sha256,
           "git_head_sha": git_head_sha}


def sealed_schedule_ids(schedule_ids: list[str], reviews_dir: Path) -> tuple[list[str], list[str]]:
    """`(sealed, unlocatable)` for the ids these rows carry.

    A row belonging to a SEALED (v2) schedule may never be edited in place,
    whatever flag the operator passes: it is an observation of a registered
    cell, and this script rewrites archived files. An id whose schedule file
    cannot be found is returned as UNLOCATABLE and refused just as hard —
    "I could not check whether this is sealed" is not "it is not sealed".
    """
    import schedule_arms as SA                                             # noqa: PLC0415 -- lazy

    found: dict = {}
    for path in sorted(Path(reviews_dir).glob("schedule_*.json")):
        try:
            schedule = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(schedule, dict) and schedule.get("schedule_id"):
            found[schedule["schedule_id"]] = SA.is_confirmatory(schedule)
    sealed = sorted(i for i in schedule_ids if found.get(i))
    unlocatable = sorted(i for i in schedule_ids if i not in found)
    return sealed, unlocatable


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-checkout", required=True, type=Path,
                        help="an environments/beancount_ledger checkout root (containing "
                             "beancount_ledger/beancount_ledger.py) -- the package that actually served the "
                             "rows being stamped")
    parser.add_argument("--backfill-accounting", action="store_true",
                        help="also derive budget_accounting (arm_table.derive_budget_accounting) into any row "
                             "that lacks the field entirely, marking budget_accounting_stamped: true on it")
    parser.add_argument("--allow-scheduled-rows", action="store_true",
                        help="stamp rows that carry a schedule_id. REFUSED by default (Codex T49 §4): a "
                             "scheduled row is an observation of a registered experiment cell, and this "
                             "script edits archived files in place — a stamp would change the bytes the "
                             "exact-cell check reads and could not be told from the original observation")
    parser.add_argument("files", nargs="+", help="reviews/budget_*.json row files to stamp in place")
    args = parser.parse_args()

    checkout = args.from_checkout.resolve()
    if not (checkout / "beancount_ledger" / "beancount_ledger.py").is_file():
        print(f"{checkout} does not look like an environments/beancount_ledger checkout "
             "(beancount_ledger/beancount_ledger.py not found)")
        return 1

    env_mod = load_env_mod_from_checkout(checkout)
    digest = mb.compute_prompt_schema_digest(env_mod)
    provenance = checkout_provenance(checkout)
    print(f"prompt_schema_digest from {checkout}: {digest}")
    print(f"stamped_from provenance: {provenance}\n")

    stamped_total = 0
    accounting_stamped_total = 0
    for raw_path in args.files:
        path = Path(raw_path)
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:                     # noqa: BLE001
            print(f"skip {path.name}: {type(exc).__name__}: {exc}")
            continue
        if not isinstance(rows, list):
            print(f"skip {path.name}: not a list of rows")
            continue
        scheduled = sorted({row.get("schedule_id") for row in rows
                            if isinstance(row, dict) and row.get("schedule_id")})
        if scheduled:
            sealed, unknown = sealed_schedule_ids(scheduled, path.parent)
            if sealed or unknown:
                # NOT overridable by --allow-scheduled-rows (F2): a row of a
                # SEALED schedule is an observation of a registered cell, and
                # this script edits archived files in place. An id whose
                # schedule file cannot be found is refused too — "I could not
                # check" is not "it is safe".
                print(f"REFUSED {path.name}: "
                      + (f"schedule(s) {sealed} are SEALED confirmatory schedules; " if sealed else "")
                      + (f"schedule(s) {unknown} could not be located under {path.parent}, so their "
                         f"sealed status is unknown; " if unknown else "")
                      + "an observation of a registered experiment cell is immutable and no flag "
                        "overrides that")
                continue
            if not args.allow_scheduled_rows:
                print(f"REFUSED {path.name}: it carries rows from schedule(s) {scheduled}. Pass "
                      f"--allow-scheduled-rows only for a PILOT schedule whose rows are not "
                      f"decision-bearing")
                continue
        changed = 0
        accounting_changed = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            if not row.get("prompt_schema_digest"):
                row["prompt_schema_digest"] = digest
                row["stamped_from"] = provenance
                changed += 1
            if args.backfill_accounting and "budget_accounting" not in row:
                row["budget_accounting"] = AT.derive_budget_accounting(row)
                row["budget_accounting_stamped"] = True
                accounting_changed += 1
        if changed or accounting_changed:
            path.write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
        print(f"{path.name}: stamped {changed}/{len(rows)} prompt_schema_digest"
             + (f", {accounting_changed}/{len(rows)} budget_accounting" if args.backfill_accounting else "")
             + ("" if changed or accounting_changed else " (nothing to stamp)"))
        stamped_total += changed
        accounting_stamped_total += accounting_changed

    print(f"\nstamped {stamped_total} row(s) with prompt_schema_digest"
         + (f", {accounting_stamped_total} row(s) with budget_accounting" if args.backfill_accounting else "")
         + " total")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
