"""Freeze a screen's selection and execution order BEFORE any model call.

    python freeze_selection.py --serving evaluation_pack_run/serving.json \
        --screen my-screen-1 --seed "my-screen-1:2026-10-01" --subject some-model-id \
        --per-stratum 2 --out my-screen-1.selection.json

This is the pre-registration step the repository's own generated-population
screen used (`reviews/cash_application_generated_screen_2026-09-13/
cash_screen_1_selection.py`), made reusable. The rules it enforces are the
rules the result record is held to:

  * eligibility is READ from a serving record - only parent groups whose BOTH
    variants actually served under your manifest are eligible, so a pair is
    a pair;
  * only the development split of the released population is eligible; the
    evaluation split stays closed and this script cannot open it;
  * the draw is uniform over the eligible groups of each mechanism stratum
    under a SEPARATE, recorded sampling seed - never by case size, never by
    any model outcome, never by anything a group drew;
  * the execution order is also drawn, so no stratum systematically runs
    first;
  * the record carries its own digest. Quote that digest in every result row
    (`--selection-digest` on the runner) and in the write-up. If the
    selection changes, it is a new screen with a new digest.

Nothing here calls a model. It writes one record, and that record is what the
run is held to.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path


def load_package():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from beancount_ledger.graph import cash_population as CP  # noqa: E402
    return CP


def served_groups(serving_path: Path, CP) -> dict:
    """`{mechanism: {group: [variants served]}}` from a serving record: this
    pack's `serving.json` (rows with `served`) or the repository population
    record's `serving.json` (rows with `served` as well). Read, never
    re-derived."""
    body = json.loads(serving_path.read_text(encoding="utf-8"))
    rows = body["rows"] if isinstance(body, dict) and "rows" in body else body
    mechanism_of = {template: mechanism for template, mechanism, _split in CP.SPLIT_MAP.assignments}
    split_of = {template: split for template, _mechanism, split in CP.SPLIT_MAP.assignments}
    out: dict = {}
    for row in rows:
        if not row.get("served"):
            continue
        selector = row["selector"]
        prefix, population, template, index, variant = selector.split(":")
        if prefix != "cash_application" or population != CP.DEVELOPMENT_POPULATION:
            continue
        if split_of.get(template) != "development":
            # The evaluation split cannot be selected here whatever a record says.
            continue
        group = f"{population}:{template}:{index}"
        out.setdefault(mechanism_of[template], {}).setdefault(group, []).append(variant)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serving", required=True, help="serving.json written by mint_and_serve.py")
    parser.add_argument("--screen", required=True, help="the screen's name, e.g. my-screen-1")
    parser.add_argument("--seed", required=True, help="the sampling seed, recorded; separate from every mint seed")
    parser.add_argument("--subject", required=True, help="the requested model id, exactly as you will request it")
    parser.add_argument("--per-stratum", type=int, default=2, help="parent groups per mechanism stratum (default 2)")
    parser.add_argument("--turns", type=int, default=25)
    parser.add_argument("--output-ceiling", type=int, default=40_000, help="max total completion tokens per episode")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--out", required=True, help="where to write the selection record")
    args = parser.parse_args()

    CP = load_package()
    by_mechanism = served_groups(Path(args.serving), CP)
    problems, chosen = [], {}
    for mechanism in CP.MECHANISMS:
        groups = by_mechanism.get(mechanism, {})
        eligible = sorted(g for g, variants in groups.items() if sorted(variants) == list(CP.VARIANTS))
        if len(eligible) < args.per_stratum:
            problems.append(f"{mechanism}: {len(eligible)} eligible group(s) with both variants served, "
                            f"fewer than the {args.per_stratum} asked for")
            chosen[mechanism] = []
            continue
        rng = random.Random(f"{args.seed}|{mechanism}")
        chosen[mechanism] = rng.sample(eligible, args.per_stratum)

    episodes = [f"cash_application:{group}:{variant}"
                for mechanism in CP.MECHANISMS
                for group in chosen[mechanism]
                for variant in CP.VARIANTS]
    random.Random(f"{args.seed}|order").shuffle(episodes)

    record = {
        "schema": "piv.screen-selection/1",
        "screen": args.screen,
        "written_before_any_model_call": True,
        "sampling_seed": args.seed,
        "serving_record": str(Path(args.serving).resolve()),
        "population": CP.DEVELOPMENT_POPULATION,
        "split": "development",
        "evaluation_split_opened": False,
        "groups_per_stratum": args.per_stratum,
        "eligible_groups_per_stratum": {m: len(by_mechanism.get(m, {})) for m in CP.MECHANISMS},
        "chosen_groups": chosen,
        "execution_order": episodes,
        "episodes": len(episodes),
        "subject": {"requested_id": args.subject},
        "settings": {"temperature": args.temperature, "turns": args.turns,
                     "episode_output_ceiling": args.output_ceiling, "fresh_context_per_episode": True,
                     "retries": 0, "one_attempt_per_cell": True},
        "rules": [
            "no cell is re-run, refilled or substituted; a missing outcome stays missing and is reported "
            "against the planned denominator",
            "a provider refusal is ATTEMPTED_UNSCORED, never a model failure; a cell never reached is UNATTEMPTED",
            "rows taken under other settings are another arm and are never pooled with these",
            "the subject's own outputs never adjudicate the subject's own cells",
        ],
        "selection_problems": problems,
    }
    body = json.dumps(record, indent=1, sort_keys=True).encode("utf-8")
    record["self_digest"] = hashlib.sha256(body).hexdigest()
    out = Path(args.out)
    out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    print(f"eligible per stratum: {record['eligible_groups_per_stratum']}")
    for mechanism, groups in chosen.items():
        print(f"  {mechanism:<24} {groups}")
    print(f"\nexecution order ({len(episodes)} episodes):")
    for i, selector in enumerate(episodes, 1):
        print(f"  {i:2d}. {selector}")
    print(f"\nproblems: {problems or 'none'}")
    print(f"written: {out}  selection digest {record['self_digest']}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
