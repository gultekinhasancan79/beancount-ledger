"""Freeze the twelve-episode screen's selection and execution order, before any model call.

The design is the one fixed in advance: two admitted parent groups per mechanism
stratum, both variants, twelve episodes. The selection uses a SEPARATE recorded
sampling seed, is not made by inspecting model outcomes, and is not made by case
size. The evaluation split is not opened: only development-split groups are
eligible, and only those the replacement population actually admitted.

Nothing here calls a model. It writes one record, and that record is what the run
is held to.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import sys

sys.path.insert(0, r"C:/Users/gulte/Desktop/PIV/beancount-ledger-workflows")

import beancount_ledger.graph.cash_population as P  # noqa: E402

SAMPLING_SEED = "cash-application-screen-1:2026-09-13"   # recorded, separate from every mint seed
GROUPS_PER_STRATUM = 2
OUT = pathlib.Path(__file__).with_name("screen_selection.json")
RECORD = pathlib.Path(
    r"C:/Users/gulte/Desktop/PIV/beancount-ledger-workflows/reviews"
    r"/cash_application_development_population_2026-09-13_replacement/serving.json")


def admitted_selectors() -> dict:
    """Every admitted development selector, by mechanism, from the population's own
    serving record — the same file that recorded it served. Read, never re-derived here."""
    rows = json.loads(RECORD.read_text(encoding="utf-8"))
    rows = rows["rows"] if isinstance(rows, dict) and "rows" in rows else rows
    by_mechanism: dict[str, dict[str, list]] = {}
    for row in rows:
        if not row.get("served"):
            continue
        selector = row["selector"]
        _prefix, population, template, index, variant = selector.split(":")
        mechanism = next(m for t, m, _split in P.SPLIT_MAP.assignments if t == template)
        group = f"{population}:{template}:{index}"
        by_mechanism.setdefault(mechanism, {}).setdefault(group, []).append(variant)
    return by_mechanism


def main() -> int:
    by_mechanism = admitted_selectors()
    problems = []
    chosen = {}
    for mechanism in P.MECHANISMS:
        groups = by_mechanism.get(mechanism, {})
        # every eligible group must carry BOTH variants, or the pair is not a pair
        eligible = sorted(g for g, variants in groups.items() if sorted(variants) == list(P.VARIANTS))
        if len(eligible) != 32:
            problems.append(f"{mechanism}: {len(eligible)} eligible groups, expected 32")
        # the selection: a separate recorded seed, uniform over the eligible groups,
        # ordered by nothing but the draw — not by size, not by any outcome
        rng = random.Random(f"{SAMPLING_SEED}|{mechanism}")
        chosen[mechanism] = rng.sample(eligible, GROUPS_PER_STRATUM)

    # execution order: also drawn, so that no mechanism systematically runs first
    episodes = [f"cash_application:{group}:{variant}"
                for mechanism in P.MECHANISMS
                for group in chosen[mechanism]
                for variant in P.VARIANTS]
    random.Random(f"{SAMPLING_SEED}|order").shuffle(episodes)

    record = {
        "schema": "piv.screen-selection/1",
        "screen": "cash-application-screen-1",
        "written_before_any_model_call": True,
        "sampling_seed": SAMPLING_SEED,
        "population": P.DEVELOPMENT_POPULATION,
        "split": "development",
        "evaluation_split_opened": False,
        "groups_per_stratum": GROUPS_PER_STRATUM,
        "eligible_groups_per_stratum": {m: len(by_mechanism.get(m, {})) for m in P.MECHANISMS},
        "chosen_groups": chosen,
        "execution_order": episodes,
        "episodes": len(episodes),
        "subject": {
            "requested_id": "qwen3.7-max-2026-05-20",
            "amended_from": "qwen3.7-max",
            "why": ("the alias's console-reported free allowance was 362,620 tokens against the "
                    "snapshot's untouched 1,000,000; the amendment was made before any "
                    "generated-population model call, used no model outcomes, and kept the "
                    "twelve-episode design"),
            "disclosure_also_required": ("qwen was an adjudicator earlier in this project; a fresh "
                                         "requested ID does not make it an uninvolved validator"),
        },
        "settings": {"temperature": 0, "turns": 25, "episode_output_ceiling": 40000,
                     "fresh_context_per_episode": True, "free_quota_only": True},
        "selection_problems": problems,
    }
    body = json.dumps(record, indent=1, sort_keys=True).encode("utf-8")
    record["self_digest"] = hashlib.sha256(body).hexdigest()
    OUT.write_text(json.dumps(record, indent=1, sort_keys=True), encoding="utf-8", newline="\n")

    print(f"eligible per stratum: {record['eligible_groups_per_stratum']}")
    for mechanism, groups in chosen.items():
        print(f"  {mechanism:<22} {groups}")
    print(f"\nexecution order ({len(episodes)} episodes):")
    for i, selector in enumerate(episodes, 1):
        print(f"  {i:2d}. {selector}")
    print(f"\nproblems: {problems or 'none'}")
    print(f"written: {OUT}  digest {record['self_digest'][:16]}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
