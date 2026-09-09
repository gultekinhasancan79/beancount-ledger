"""Run every suite. One command, one exit code.

Ordered roughly by layer: the old reward first, then the boundary, then the
canonical graph. A failure early usually explains failures later, so the
output reads top-down.
"""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PYTHON = sys.executable

SUITES = [
    ("test_entrypoints", "no path touching agent text can import from it"),
    ("test_scripted_route", "the full route with a scripted model: control / hostile / fault"),
    ("test_episode_contract", "PLAN §6: submit ends the episode, a bare/empty/truncated turn does not"),
    ("test_reward", "the old reward's regression corpus"),
    ("test_invariants", "reward invariants the corpus cannot express"),
    ("test_leakage", "answer leakage in the world files"),
    ("test_mapping_coverage", "every parser field is classified, and enforced"),
    ("test_control_channels", "top-level controls, including the one that imports"),
    ("test_entities", "counterparty resolution, both directions"),
    ("test_validate", "domain validity and its disclosed consequences"),
    ("test_perimeter", "the adversarial corpus against the trust boundary"),
    ("test_exploits", "the same attacks as constructions on GENERATED worlds: branch reached, reward held"),
    ("test_render", "canonical rendering: round trip, idempotence, equivalence"),
    ("test_canonical", "canonical bytes, bounded numbers, structural vs semantic identity"),
    ("test_committed", "the committed state: environment-bound, single allocation, finalised by digest"),
    ("test_calibration", "candidate/1 rankings and the semantic-equivalence claim"),
    ("test_graph", "the world graph as production authority: projection, derivation, identity, oracles"),
    ("test_worlds", "every hand-authored world/task: derivable, golden 1.0, original unresolved (or already 1.0 where nothing is planted), identifiable, no merged trap, no leaked ids or derived literals"),
    ("test_clean_month", "the clean-month assurance pack: one neutral instruction over two clean months and their single-error counterparts; unchanged delivers 1.0, invented corrections are penalised"),
    ("test_legacy_freeze", "the legacy freeze: the 95 shipped tasks' public bytes, task-contract and golden digests, the candidate/1 scorer bytes and the contract-4 episode view, pinned against a checked-in fixture"),
    ("test_identify", "public-only identifiability over the new graph's public bytes"),
    ("test_state_conformance", "every scorer state answered by a public reading class or a written exclusion"),
    ("test_lag", "date lag: the bank's date is the repair date, at every rail and across a month boundary"),
    ("test_identify_differential", "checker uniqueness against the real scorer's solution classes"),
    ("test_sentinels", "the pinned structural sentinel set: coverage re-earned, differential over exactly it"),
    ("test_generator", "the seeded generator: determinism, isolation, population validity, identity, reward ordering"),
    ("test_secret_boundary", "the evaluator boundary as the attacker meets it: canary secret, symlinks, options, mint reach, finite selectors"),
    ("test_measure_budget", "the M2 measurement instrument: artifact binding from rollout state, per-turn accounting, arms, reasoning-replay projection"),
    ("liveness_witness", "a scripted conforming agent delivers the golden ledger through the real evaluate door on the six confirm1 panel selectors: reward 1.0, submitted, artifact digests bound, every declared envelope respected, identical across two runs"),
]


def _run(entry):
    name, description = entry
    result = subprocess.run(
        [PYTHON, str(HERE / f"{name}.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return name, description, result


def main() -> int:
    # Run concurrently. Almost all the wall-clock here is interpreter startup
    # plus importing beancount — about ten seconds a suite, `len(SUITES)` of
    # them, minutes serially, which is long enough that people stop running it. Each
    # suite is a separate process with its own captured output, so there is
    # nothing to interleave and nothing shared to race on.
    #
    # Output stays in the declared order rather than completion order, so a
    # run reads the same way every time.
    failures = []
    with ThreadPoolExecutor(max_workers=min(8, len(SUITES))) as pool:
        completed = dict(
            (name, (description, result))
            for name, description, result in pool.map(_run, SUITES)
        )

    for name, _ in SUITES:
        description, result = completed[name]
        last = [line for line in result.stdout.strip().splitlines() if line.strip()]
        summary = last[-1] if last else "(no output)"
        status = "ok  " if result.returncode == 0 else "FAIL"
        print(f"{status} {name:24s} {summary}")
        print(f"     {description}")
        if result.returncode != 0:
            failures.append((name, result.stdout, result.stderr))

    print()
    if failures:
        for name, out, err in failures:
            print(f"--- {name} ---")
            print(out[-2000:])
            if err.strip():
                print(err[-1000:])
        print(f"{len(failures)} of {len(SUITES)} suites FAILED")
        return 1
    print(f"all {len(SUITES)} suites pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
