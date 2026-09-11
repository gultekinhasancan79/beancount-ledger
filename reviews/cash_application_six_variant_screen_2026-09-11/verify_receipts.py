"""Do the archived artifacts still match the receipts the run wrote?

Ten files — a `ledger.beancount` and a `cash_application.json` in each of the
five archived workspaces — against their own `delivery.json`. The digests are
DOMAIN-SEPARATED (`piv:stored-bytes:v1\\0`, `piv:logical-text:v1\\0`), so this
imports `digests_of` from the shipped package rather than hashing the bytes
raw; a plain `sha256` of the file reproduces nothing and would look like a
failure.

It also records the thing the archive does NOT contain. `_publish` writes the
CANONICAL register over the workspace path, so the archived bytes are the
canonical form and do not reproduce the `submitted_*` digests beside them,
which are of the agent's own text. That is asserted here rather than left to
be discovered: all five must differ.

No model is called and nothing is written outside this directory.

    python verify_receipts.py
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# the repository root: this file lives at reviews/<note dir>/ inside it
sys.path.insert(0, str(HERE.parents[1]))

from beancount_ledger.beancount_ledger import digests_of

WORKSPACES = HERE / "workspaces"
OUT = HERE / "verify_receipts.json"


def main() -> int:
    report = {
        "schema": "piv.six-screen-receipt-check/1",
        "what_this_is": ("Each archived delivered artifact re-hashed through the shipped package's own "
                         "`digests_of` and compared with the `delivery.json` the run wrote beside it. "
                         "`submitted_reproduced` is expected to be false everywhere: the archive holds the "
                         "canonical register, never the agent's submitted text."),
        "files": [],
    }
    problems = []
    for ws in sorted(WORKSPACES.iterdir()):
        if not ws.is_dir():
            continue
        receipt = json.loads((ws / "delivery.json").read_text(encoding="utf-8"))
        for name, block in (("ledger.beancount", receipt), ("cash_application.json", receipt["application"])):
            raw = (ws / name).read_bytes()
            got = digests_of(raw)
            row = {
                "workspace": ws.name,
                "file": name,
                "bytes": len(raw),
                "stored_bytes_digest": got["stored_bytes_digest"],
                "logical_text_digest": got["logical_text_digest"],
                "stored_matches_receipt": got["stored_bytes_digest"] == block["artifact_stored_bytes_digest"],
                "logical_matches_receipt": got["logical_text_digest"] == block["artifact_logical_text_digest"],
            }
            if "submitted_stored_bytes_digest" in block:
                row["submitted_reproduced"] = (got["stored_bytes_digest"] == block["submitted_stored_bytes_digest"])
                if row["submitted_reproduced"]:
                    problems.append(f"{ws.name}/{name}: the archived bytes reproduce the SUBMITTED digest, "
                                    f"which the canonical form must not")
            for field in ("stored_matches_receipt", "logical_matches_receipt"):
                if not row[field]:
                    problems.append(f"{ws.name}/{name}: {field} is false")
            report["files"].append(row)
            print(f"  {ws.name:<22} {name:<22} stored={row['stored_matches_receipt']} "
                  f"logical={row['logical_matches_receipt']}")

    report["checked"] = len(report["files"])
    report["problems"] = problems
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="")
    print()
    if problems:
        for p in problems:
            print("  " + p)
        return 1
    print(f"{len(report['files'])} archived artifacts match their receipts; the canonical register "
          f"reproduces no submitted digest, as expected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
