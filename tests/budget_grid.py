"""The budget grid: which cap was actually binding, measured rather than argued.

An earlier sweep raised the episode ceiling and the per-turn cap in the same step
and read the improvement as the per-turn cap's doing. It might have been either.
This runs the missing cells.

Four arms over the same ten hand-authored worlds, two replicates each:

    per-turn cap   episode ceiling   what it is for
        8,000           40,000       the instrument every archived row was taken on
       16,000           40,000       THE MISSING CELL: per-turn cap alone, ceiling held
       40,000           40,000       no per-turn restriction beyond the episode budget
       16,000           80,000       the additional effect of the ceiling, cap held

The pre-registered primary contrast is 8k/40k against 16k/40k. Everything else is
held: 25 turns, both three-turn guards, the shipped prompt, one route.

Arms are run ADJACENT within a (world, replicate) block, in an order shuffled by a
fixed seed, so that provider drift across the run falls on all four arms alike
instead of on whichever happened to run last. A cell that the provider refuses is
recorded as a refusal and never silently retried into a different arm.

Rows land in JSONL, one line per episode, each carrying its own arm identity —
`tests/budget_calibration.run_one` now archives the wire caps, the truncation and
no-tool counters and the revision count, so a row can be pooled or refused on its
contents rather than on a memory of how it was launched.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tests.budget_calibration as bc

WORLDS = ("bank_recon_001", "bank_recon_ironwood", "bank_recon_silverbrook", "bank_recon_thistle",
          "bank_recon_falcon", "bank_recon_hawthorn", "bank_recon_bluewater", "bank_recon_oakridge",
          "bank_recon_redwood", "bank_recon_maple")

#: (per-turn cap, episode ceiling). The first two are the primary contrast.
ARMS = ((8_000, 40_000), (16_000, 40_000), (40_000, 40_000), (16_000, 80_000))

SEED = 20260907


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--key-var", required=True)
    parser.add_argument("--replicates", type=int, default=2)
    parser.add_argument("--turns", type=int, default=25)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--backoff", type=float, default=45.0)
    parser.add_argument("--pace", type=float, default=2.0)
    parser.add_argument("--worlds", nargs="*", default=list(WORLDS))
    parser.add_argument("--jsonl", type=Path, required=True)
    args = parser.parse_args()

    bc.resolve_key(args.key_var) if hasattr(bc, "resolve_key") else None
    if not bc.os.environ.get(args.key_var):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
                bc.os.environ[args.key_var] = winreg.QueryValueEx(handle, args.key_var)[0]
        except OSError:
            pass
    if not bc.os.environ.get(args.key_var):
        print(f"{args.key_var} is not set", file=sys.stderr)
        return 2

    cells = []
    for replicate in range(1, args.replicates + 1):
        for world in args.worlds:
            order = list(ARMS)
            # one stream, seeded once, so the whole schedule is reproducible from SEED
            random.Random(f"{SEED}:{world}:{replicate}").shuffle(order)
            for cap, ceiling in order:
                cells.append((world, replicate, cap, ceiling))

    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    print(f"budget grid: {args.model}; {len(cells)} cells "
          f"({len(args.worlds)} worlds x {len(ARMS)} arms x {args.replicates} replicates)", flush=True)

    with args.jsonl.open("w", encoding="utf-8") as sink:
        for index, (world, replicate, cap, ceiling) in enumerate(cells, 1):
            cell_args = SimpleNamespace(model=args.model, base_url=args.base_url, key_var=args.key_var,
                                        turns=args.turns, tokens=ceiling, max_tokens=cap,
                                        timeout=args.timeout, production=False, tool_schema_fix=False)
            attempt, row = 0, None
            while attempt < max(1, args.retries):
                attempt += 1
                try:
                    row = bc.run_one(world, cell_args)
                except Exception as exc:                                  # noqa: BLE001
                    row = {"selector": world, "crashed": f"{type(exc).__name__}: {exc}"[:200]}
                if not (row.get("quarantined") or row.get("crashed")):
                    break
                if attempt < max(1, args.retries):
                    print(f"  [{index:>3}/{len(cells)}] {world} cap={cap} refused; "
                          f"waiting {args.backoff}s (attempt {attempt})", flush=True)
                    time.sleep(args.backoff)
            row.update({"replicate": replicate, "arm": f"{cap}/{ceiling}", "cell_index": index,
                        "attempts": attempt, "seed": SEED})
            sink.write(json.dumps(row, default=str) + "\n")
            sink.flush()
            print(f"  [{index:>3}/{len(cells)}] {world:<22} arm={cap}/{ceiling:<6} "
                  f"reward={row.get('reward')} stop={str(row.get('stop') or row.get('quarantined') or row.get('crashed'))[:34]}",
                  flush=True)
            if args.pace:
                time.sleep(args.pace)

    print(f"\n{len(cells)} cells in {(time.time() - started) / 60:.0f} min -> {args.jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
