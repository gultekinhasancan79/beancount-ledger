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
    ("test_cash_application_fold", "the public cash-application fold: the five cases of the spec fold to their stated applications and closing AR, every U-table refusal fires on a minimal fixture, the offline boundary fixtures behave as specified, and no named gate-(o) baseline reaches a case"),
    ("test_cash_application_worlds", "the cash-application company-month and its five variants on the world machinery: eleven projected files matching the spec, the truth register derived from the authored facts, gate (m) public fold == truth over the actual bytes, gates (l) and (n), the plants, the bank-date rule, the cheque-sign and receipt-validation extensions, the ten shipped worlds' digests unchanged"),
    ("test_family_validators", "step 4 of the cash-application spec, as corrected: an EVIDENCED payment identity makes the five cases identifiable with one reading (Cases 1 and 2 first, then all five) and reaches no shipped task; the write-off plant is validated through the public fold on amount, invoice, date, customer and shape; every plant is covered by an explicit validator; verify_world accepts the five modules"),
    ("test_cash_application_scoring", "step 5 of the cash-application spec: application/1 parses and scores cash_application.json (schema, duplicate members and keys, canonicalisation by invoice, the five identities as REJECTIONS) and composite/1 multiplies it with the frozen candidate/1; every S-row of section 6 and the three worked examples reproduce their stated values through the ACTUAL candidate/1 for L; every golden register scores 1; the composite is monotone and complete iff 1; every catalogue state is reached"),
    ("test_cash_application_route", "step 6 of the cash-application spec, through the REAL evaluate door: cash_application_001 with the golden ledger and the golden register scores 1.0 and completes; the same case with the ledger alone scores 0 with L reported diagnostically and the register APPLICATION_ABSENT; a stored invalid register supersedes an accepted one (A = 0, no fallback) and an over-envelope request is refused before storage; a non-protocol ending scores the last committed revision of each artifact; score_core composes and _publish writes the canonical register and both digests into delivery.json; the malformed-call path and the per-tool one-write-per-turn rule cover the seventh tool"),
    ("test_cash_family_identity", "phase A of the generated cash-application population: cash_application/1 is a "
                                  "separate versioned implementation with its own seed and manifest-signing "
                                  "domains; the construction identity binds decision 2's eight components and "
                                  "nothing else; the seed is keyed and no private selector reaches a surface; "
                                  "both variants share one parent world; token budgets do not move the world; "
                                  "the split map is a frozen 60/20/20 by structural-template family, stratified "
                                  "across the three mechanisms, and a renamed or rescaled cross-split sibling is "
                                  "refused by canonical structure"),
    ("test_cash_family_manifest", "the family manifest schema (1) and the admission contract (2, since the "
                                  "credit bound was corrected to the original sale): a record "
                                  "binds the construction identity, public-content digest, parent/variant, "
                                  "split-map digest, profile, baseline catalogue, exact gate set and every "
                                  "semantic component; admission reads today's gate set, not the record's own "
                                  "flag; runtime-dependent evidence is Unicode-scoped through the one shared "
                                  "convention; GENERATOR_VERSION 9 and the bank manifest are untouched"),
    ("test_cash_construction", "phase B of the generated cash-application population: bounded-v1 enforced and "
                               "the construction path that renders a candidate pair. Fifteen sealed families "
                               "and fifteen recipes agree in both directions; every family renders a pair from "
                               "its identity — eleven public files, a truth register, a golden ledger and a "
                               "golden register per variant — inside the 64-attempt loop; the ADMISSION GATE "
                               "runs in that path rather than here — the merged-trap guard, both goldens "
                               "through the actual candidate/1, application/1 and composite/1, and the shipped "
                               "world checker, on every rendered variant of every attempt, each classified as "
                               "decision 3 classifies it — witnessed on the counterexample group that used to "
                               "be admitted with a golden scoring zero, and re-drawn under a second secret, a "
                               "second population and further company-month indices; the pair differs in "
                               "exactly one declared authored fact and only the files that fact reaches move; "
                               "both polarities appear in every stratum and the public id says which nowhere; "
                               "decision 4's table holds, every bound including the measured period and "
                               "currency refuses a variant that breaks it; manufactured difficulty is "
                               "validated absent with a negative control per condition; no binding baseline "
                               "reaches any truth inside the 256-reading bound; construction is keyed and "
                               "leaks no private selector; exhaustion is a named failed group; the authored "
                               "eleven stay outside"),
    ("test_cash_gate", "phase C of the generated cash-application population: the MINTING GATE and its "
                       "CENSUS. Decision 3's six integrity families plus gate (o) are thirty-one named gates, "
                       "each implemented, each with its own rejection code and each with a negative control "
                       "that makes IT speak; a declared gate with no implementation and an implementation the "
                       "gate set does not declare both refuse to evaluate; gate (o) runs IN THE MINTING PATH "
                       "on both variants of every family — nine binding baselines, one diagnostic recorded "
                       "and never promoted, the 256-reading bound a VERIFICATION-LIMIT rejection rather than "
                       "evidence of resistance; a finding on either variant rejects the pair; every attempt "
                       "retains its ordinal, stage, codes, baseline, witness, reading count, component "
                       "versions and content digests; acceptance rates, exhaustion counts and rejection "
                       "distributions are published; exhaustion is a named failed group that draws no "
                       "replacement selector, and a defect is not drawn past; a population declaring one "
                       "construction identity twice is refused before anything is minted; the ruling's "
                       "minting paragraph is verbatim; the catalogue digest binds admission predicates, not "
                       "their names, and the diagnostic's role is compared against the catalogue version's "
                       "own declaration rather than against the tuple it is read from"),
    ("test_cash_population", "phase D of the generated cash-application population: the FROZEN DEVELOPMENT "
                             "POPULATION and its SERVING DOOR. The freeze is declared as literals and matches "
                             "the live modules in both directions, with a negative control per declaration "
                             "and the runtime-scoped half recorded rather than pinned; 96 predeclared parent "
                             "groups, 32 per mechanism stratum, all in the development split, in a fixed "
                             "order with no repeated identity; the evaluation split stays unopened because no "
                             "released population declares a sealed evaluation family, so the selector does "
                             "not exist; the selector round-trips and refuses an unreleased population, an "
                             "undeclared index, a non-ASCII index, an unknown variant, a bank selector and an "
                             "authored id; a bounded slice mints, validates offline — every phase-C gate, the "
                             "public fold against the truth, ONE identifiable reading, both goldens and their "
                             "composite at 1.0 through the actual frozen engines, no provenance leak — is "
                             "signed into a manifest and then SERVES through the real load_environment "
                             "exactly as cash_application_001 does: same profile, public file manifest, tool "
                             "surface and episode-contract digest, with no selector on an agent surface; the "
                             "signed manifest is the only door, with no development bypass; the census "
                             "retains decision 3's nine fields and the aggregates are per stratum; no "
                             "phase-D source reaches a provider; and round 17 decision 4's REPLACEMENT "
                             "population — the population selected under the incorrect opening-balance cap "
                             "is retired and unspellable, the freeze pins the population identifier as a "
                             "literal and reports it moving, and both records are published and cross-linked "
                             "with the superseded artifacts unaltered and the paired replay showing every "
                             "refusal the removed clause caused is now admitted"),
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
