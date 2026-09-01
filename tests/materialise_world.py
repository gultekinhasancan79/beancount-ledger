"""Re-materialise the shipped world's public files from the graph.

`beancount_ledger/world/` is a CACHE of `derive_contract(ALPINE, BANK_RECON_001)`
— `test_graph.test_the_shipped_world_is_the_projection` compares it byte for
byte — so any change to the projector, the policy document or the world
authoring must be written back through here rather than edited by hand.

The golden deliverable (`tests/solutions/golden.beancount`) is compared
STRUCTURALLY against the expected-ledger projection, so it is not rewritten:
this script reports whether the two still agree and, if they do not, names the
entries that moved. `tests/build_solutions.py` rebuilds it and the attack
corpus from the re-materialised ledger.

    python tests/materialise_world.py [--check]

`--check` writes nothing and exits 1 if anything is stale, which is what a
pre-commit hook or a release check wants.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.candidate.normalise import Accepted, parse_once  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402

WORLD_DIR = ROOT / "beancount_ledger" / "world"
GOLDEN = ROOT / "tests" / "solutions" / "golden.beancount"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    check_only = "--check" in sys.argv[1:]
    world, task = REGISTRY["bank_recon_001"]
    bundle, inputs = derive_contract(world, task)

    stale = []
    for name, data in sorted(inputs.public_files):
        target = WORLD_DIR / name
        current = target.read_bytes() if target.exists() else None
        if current == data:
            print(f"  ok      {name} ({len(data)} bytes)")
            continue
        stale.append(name)
        if check_only:
            print(f"  STALE   {name}")
        else:
            target.write_bytes(data)
            print(f"  written {name} ({len(data)} bytes)")

    restated = dict(bundle.restated)
    if restated:
        print(f"  restated onto the bank's date: {sorted(restated.items())}")
    else:
        print("  restated onto the bank's date: none — every omitted item's recognition date already IS "
              "its bank date, so the golden deliverable does not move")

    golden_text = GOLDEN.read_text(encoding="utf-8")
    shipped, expected = parse_once(golden_text), parse_once(inputs.golden_text)
    ok = (isinstance(shipped, Accepted) and isinstance(expected, Accepted)
          and shipped.candidate_digest == expected.candidate_digest)
    print(f"  golden  {'agrees with' if ok else 'DIFFERS FROM'} the expected-ledger projection "
          f"(structural digest)")
    if not ok:
        print("      the shipped golden is no longer the projection: rebuild it with "
              "tests/build_solutions.py (the omitted items' dates have moved) and re-run")
        stale.append("golden.beancount")

    if check_only and stale:
        print(f"\n{len(stale)} stale: {', '.join(stale)}")
        return 1
    print(f"\n{'nothing stale' if not stale else str(len(stale)) + ' file(s) rewritten'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
