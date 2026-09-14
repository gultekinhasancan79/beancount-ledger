"""Freeze a screen's selection, execution order and COMPLETE ARM before any
model call.

    python freeze_selection.py --serving evaluation_pack_run/serving.json \
        --screen my-screen-1 --seed "my-screen-1:2026-10-01" \
        --subjects some-model-id [another-model-id ...] \
        --per-stratum 2 --timeout 3600 --out my-screen-1.selection.json

This is the pre-registration step the repository's own generated-population
screen used (`reviews/cash_application_generated_screen_2026-09-13/
cash_screen_1_selection.py`), made reusable and held to more. The rules it
enforces are the rules the result record is held to:

  * the serving record is VALIDATED, not trusted: every row must carry
    `selector` and a boolean `served`; every selector must parse as a
    declared member of the released population (`cash_population.
    parse_selector`), in its canonical spelling; and no selector may appear
    twice. A record that fails any of this is refused whole, because a draw
    over a malformed eligibility set is not a draw over the population;
  * eligibility is READ from that record - a parent group is eligible only
    when BOTH its variants have a served row, exactly once each, so a pair
    is a pair;
  * only the development split of the released population is eligible; the
    evaluation split is declared in no population, so no selector spells it
    and this script cannot open it;
  * the draw is uniform over the eligible groups of each mechanism stratum
    under a SEPARATE, recorded sampling seed - never by case size, never by
    any model outcome, never by anything a group drew;
  * the execution order is also drawn, so no stratum systematically runs
    first;
  * the record BINDS what it sampled from: the serving record's bytes
    (sha256 and size), the manifest identity that record carries (path,
    sha256, records signed) when it carries one, and the population's
    declared identity read from the package (population, split-map digest,
    profile digest, gate-set digest, preflight contract). A path and a
    self-digest alone would not say which eligible population was drawn;
  * the record carries the COMPLETE ARM: per-turn cap, per-episode ceiling,
    turns, replay policy, sampling pins, request timeout, retry policy (SDK
    and pacing), provider label, base URL and the NAME of the key variable.
    The episode-contract digest does not cover every client setting, so
    equal contract digests do not make equal arms; this block does.
    `--timeout` has no default: the caller declares it;
  * one draw may be frozen for several subjects (`--subjects a b`): they
    share the selection and the arm, and each is its own model record;
  * the record carries its own digest, over everything above. Quote that
    digest in every result row (`--selection-digest` on the runner) and in
    the write-up. If the selection or the arm changes, it is a new screen
    with a new digest.

Nothing here calls a model. It writes one record, and that record is what the
run is held to.

EXIT CODES. 0: written. 1: written, with a selection problem named (a stratum
short of eligible groups). 2: the serving record or an argument was refused;
nothing written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path

# Screen 1's arm, as its rows record it, so the defaults reproduce that arm
# and a departure is a declared choice.
SCREEN_1_BASE_URL = "https://ws-r76rtaa6sn7jqbcr.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
SCREEN_1_PROVIDER_LABEL = "alibaba-model-studio"   # screen 1's rows carry the runner's default label instead
SCREEN_1_KEY_VAR = "DASHSCOPE_API_KEY"             # the NAME this repository's scripts use for that endpoint
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
HOME_PIV = Path(os.path.expanduser("~")) / ".piv"


def refuse(message: str) -> "NoReturn":  # noqa: F821
    print(f"REFUSED: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_package():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from beancount_ledger.graph import cash_population as CP  # noqa: E402
    return CP


def outside_piv(label: str, path) -> Path:
    """`path` resolved, or a refusal if it lands under `~/.piv`: a selection
    record is evaluator-side paperwork, and nothing here writes there."""
    try:
        resolved = Path(path).expanduser().resolve()
        home_piv = HOME_PIV.resolve()
    except OSError as exc:
        refuse(f"{label} {path!s} could not be resolved ({exc})")
    if resolved == home_piv or resolved.is_relative_to(home_piv):
        refuse(f"{label} resolves to {resolved}, inside ~/.piv; name a path outside it")
    return resolved


def read_serving_record(serving_path: Path, CP) -> dict:
    """The serving record, validated whole and bound by its bytes.

    Returns `served` as `{mechanism: {group: {variant: served rows}}}` -
    counts, not a bag of variants, so eligibility can ask for exactly one
    served row per variant - and `binding` as what the selection record
    quotes about the file it drew from. Any malformed row refuses the whole
    record: a selector that does not parse, that is not spelled the way the
    package spells it, that names another population, or that appears
    twice, is not a row to skip but a record not to draw over.
    """
    raw = serving_path.read_bytes()
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        refuse(f"{serving_path} is not a JSON document: {exc}")
    rows = body["rows"] if isinstance(body, dict) and "rows" in body else body
    if not isinstance(rows, list):
        refuse(f"{serving_path} carries no row list (a top-level list, or an object with `rows`)")
    mechanism_of = {template: mechanism for template, mechanism, _split in CP.SPLIT_MAP.assignments}
    split_of = {template: split for template, _mechanism, split in CP.SPLIT_MAP.assignments}

    problems, seen = [], set()
    served: dict = {}
    served_rows = 0
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(f"row {position} is not an object")
            continue
        if "selector" not in row or "served" not in row:
            problems.append(f"row {position} lacks `selector` or `served`")
            continue
        selector, is_served = row["selector"], row["served"]
        if not isinstance(is_served, bool):
            problems.append(f"row {position} ({selector!r}): `served` is {is_served!r}, not a boolean")
            continue
        try:
            identity, variant = CP.parse_selector(selector)
        except CP.SelectorError as exc:
            problems.append(f"row {position}: {exc}")
            continue
        canonical = CP.selector_of(identity, variant)
        if canonical != selector:
            # `parse_selector` accepts "007" for member 7; two spellings of one
            # member would be two rows for one variant, so only the package's
            # own spelling is a row.
            problems.append(f"row {position}: {selector!r} is not the canonical spelling {canonical!r}")
            continue
        if selector in seen:
            problems.append(f"row {position}: {selector!r} appears more than once")
            continue
        seen.add(selector)
        template = identity.template_family
        if identity.population != CP.DEVELOPMENT_POPULATION:
            problems.append(f"row {position}: {selector!r} names {identity.population!r}, not "
                            f"{CP.DEVELOPMENT_POPULATION!r}; one serving record is one population")
            continue
        if split_of.get(template) != "development":
            # Unreachable through `parse_selector` (the roster declares only
            # development members), kept as the closed door it promises.
            problems.append(f"row {position}: {selector!r} is not in the development split")
            continue
        group = f"{identity.population}:{template}:{identity.company_month_index}"
        counts = served.setdefault(mechanism_of[template], {}).setdefault(group, {v: 0 for v in CP.VARIANTS})
        if is_served:
            counts[variant] += 1
            served_rows += 1
    if problems:
        shown = problems[:20]
        refuse(f"the serving record {serving_path} is malformed; refusing to draw over it:\n  "
               + "\n  ".join(shown)
               + (f"\n  ... and {len(problems) - len(shown)} more" if len(problems) > len(shown) else ""))

    manifest = body.get("manifest") if isinstance(body, dict) else None
    binding = {
        "path": str(serving_path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "schema": body.get("schema") if isinstance(body, dict) else None,
        "rows": len(rows),
        "served_rows": served_rows,
        "manifest": manifest if isinstance(manifest, dict) else None,
        "manifest_note": (None if isinstance(manifest, dict)
                          else "manifest identity not present in this serving record"),
        "authored_reference": (body.get("authored_reference", body.get("authored_episode_contract"))
                               if isinstance(body, dict) else None),
    }
    return {"served": served, "binding": binding}


def population_identity(CP) -> dict:
    """The declared identities of the population being drawn from, read from
    the package in front of you; a package whose own declaration has moved
    is refused, because a selection frozen under it would name a population
    the package no longer generates."""
    freeze = CP.freeze_record()
    if not freeze.get("declared_matches_live"):
        refuse("the package's live freeze does not match its own declared literals: "
               + "; ".join(CP.freeze_problems()))
    declared = freeze["declared"]
    return {
        "population": CP.DEVELOPMENT_POPULATION,
        "split_map_digest": declared["split_map_digest"],
        "profile_digest": declared["profile_digest"],
        "gate_set_digest": declared["gate_set_digest"],
        "family_preflight_contract": declared["family_preflight_contract"],
        "declared_matches_live": True,
    }


def model_seed(text: str):
    if text.strip().lower() == "none":
        return None
    try:
        return int(text)
    except ValueError:
        refuse(f"--model-seed must be an integer or `none`, not {text!r}")


def arm_block(args) -> dict:
    """Every client setting the runner is held to, in one place. The runner
    flags are listed so the invocation can be checked against the record,
    not reconstructed from it."""
    if not _ENV_NAME.match(args.api_key_var):
        refuse(f"--api-key-var must be the NAME of an environment variable (letters, digits, underscores), "
               f"not {args.api_key_var[:8]!r}...; a key value never belongs in a selection record")
    if args.timeout <= 0:
        refuse(f"--timeout must be a positive number of seconds, not {args.timeout!r}")
    if args.retries < 0:
        refuse(f"--retries must be 0 or more, not {args.retries!r}")
    replay = args.reasoning_replay == "on"
    seed = model_seed(args.model_seed)
    flags = [f"--max-tokens {args.max_tokens}",
             f"--max-total-completion-tokens {args.max_total_completion_tokens}",
             f"--temperature {args.temperature}", f"--top-p {args.top_p}"]
    if seed is not None:
        flags.append(f"--seed {seed}")
    flags += [f"--timeout {args.timeout:g}", f"--retries {args.retries}",
              f"--provider {args.provider_label}", f"--base-url {args.base_url}",
              f"--api-key-var {args.api_key_var}"]
    if not replay:
        flags.append("--no-reasoning-replay")
    return {
        "turns": args.turns,
        "per_turn_max_tokens": args.max_tokens,
        "max_total_completion_tokens": args.max_total_completion_tokens,
        "reasoning_replay": replay,
        "replay_policy": "full" if replay else "no_reasoning_content",
        "sampling": {"temperature": args.temperature, "top_p": args.top_p, "seed": seed},
        "request_timeout_seconds": args.timeout,
        "retry_policy": {
            "retries": args.retries,
            "sdk_max_retries": 0,   # fixed in the runner (SDK_MAX_RETRIES); not a flag
            "pacing_retries": args.retries,
            "framework_rollout_retries": args.retries,
            "one_attempt_per_cell": True,
            "rate_limited_or_refused_cell": "ATTEMPTED_UNSCORED; the cell is never re-requested",
        },
        "routing": {"provider_label": args.provider_label, "base_url": args.base_url,
                    "api_key_var": args.api_key_var, "api_key_value_recorded": False},
        "fresh_context_per_episode": True,
        "runner_flags": flags,
        "note": ("the episode-contract digest covers the environment's budget, not every client setting; "
                 "rows are the same arm only if every value in this block is the same"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serving", required=True, help="serving.json written by mint_and_serve.py")
    parser.add_argument("--screen", required=True, help="the screen's name, e.g. my-screen-1")
    parser.add_argument("--seed", required=True, help="the sampling seed, recorded; separate from every mint seed")
    parser.add_argument("--subjects", "--subject", dest="subjects", nargs="+", required=True,
                        help="one or more requested model ids, exactly as you will request them; several "
                             "subjects share this draw and this arm, each as its own model record")
    parser.add_argument("--per-stratum", type=int, default=2, help="parent groups per mechanism stratum (default 2)")
    # the arm; screen 1's values are the defaults, --timeout is declared by the caller
    parser.add_argument("--turns", type=int, default=25, help="episode turn budget (screen 1: 25)")
    parser.add_argument("--max-tokens", type=int, default=40_000,
                        help="PER-TURN completion cap, the runner's --max-tokens (screen 1: 40000; the "
                             "runner's own default is 4000, which is why it is declared here)")
    parser.add_argument("--max-total-completion-tokens", "--output-ceiling", dest="max_total_completion_tokens",
                        type=int, default=40_000,
                        help="per-episode output ceiling summed over turns (screen 1: 40000)")
    parser.add_argument("--temperature", type=float, default=0.0, help="sampling pin (screen 1: 0)")
    parser.add_argument("--top-p", type=float, default=1.0, help="sampling pin (screen 1: 1)")
    parser.add_argument("--model-seed", default="none",
                        help="the sampling seed sent to the model, or `none` to send no seed (screen 1: none). "
                             "Not the draw seed; that is --seed")
    parser.add_argument("--reasoning-replay", choices=("on", "off"), default="on",
                        help="whether reasoning_content is replayed in later requests (screen 1: on)")
    parser.add_argument("--timeout", type=float, required=True,
                        help="request timeout in seconds; REQUIRED so the caller declares it (screen 1's rows "
                             "carry 180; screen 2 declares 3600)")
    parser.add_argument("--retries", type=int, default=0,
                        help="retry policy governing the SDK's max_retries AND the runner's pacing retries "
                             "(screen 1: 0 SDK retries; its pacing wrapper still retried on 429, which is "
                             "what this declaration forbids)")
    parser.add_argument("--provider-label", default=SCREEN_1_PROVIDER_LABEL,
                        help=f"the service the base URL belongs to, recorded on every row (default "
                             f"{SCREEN_1_PROVIDER_LABEL}; screen 1's rows carry the runner's default label "
                             f"`nvidia` for this same endpoint, which is why it is declared here)")
    parser.add_argument("--base-url", default=SCREEN_1_BASE_URL,
                        help="the OpenAI-compatible endpoint (default: screen 1's recorded endpoint)")
    parser.add_argument("--api-key-var", default=SCREEN_1_KEY_VAR,
                        help="the NAME of the variable holding the key, never a value (default "
                             f"{SCREEN_1_KEY_VAR}); refused if it does not look like a variable name")
    parser.add_argument("--out", required=True, help="where to write the selection record")
    args = parser.parse_args()

    if args.per_stratum < 1:
        refuse(f"--per-stratum must be at least 1, not {args.per_stratum}")
    subjects = [s.strip() for s in args.subjects]
    if any(not s for s in subjects):
        refuse("--subjects: an empty requested id is not a subject")
    if len(set(subjects)) != len(subjects):
        refuse(f"--subjects repeats a requested id: {subjects}")
    out = outside_piv("--out", args.out)
    serving_path = outside_piv("--serving", args.serving)
    if not serving_path.is_file():
        refuse(f"--serving {serving_path} is not a file")
    arm = arm_block(args)

    CP = load_package()
    identity = population_identity(CP)
    record_in = read_serving_record(serving_path, CP)
    by_mechanism = record_in["served"]
    problems, chosen, eligible_count, seen_count = [], {}, {}, {}
    for mechanism in CP.MECHANISMS:
        groups = by_mechanism.get(mechanism, {})
        # eligible: every variant served exactly once, or the pair is not a pair
        eligible = sorted(g for g, counts in groups.items() if all(counts[v] == 1 for v in CP.VARIANTS))
        eligible_count[mechanism] = len(eligible)
        seen_count[mechanism] = len(groups)
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
        "schema": "piv.screen-selection/2",
        "screen": args.screen,
        "written_before_any_model_call": True,
        "sampling_seed": args.seed,
        "serving_record": record_in["binding"],
        "population": CP.DEVELOPMENT_POPULATION,
        "population_identity": identity,
        "split": "development",
        "evaluation_split_opened": False,
        "groups_per_stratum": args.per_stratum,
        "eligible_groups_per_stratum": eligible_count,
        "groups_with_a_served_row_per_stratum": seen_count,
        "eligibility": "a parent group is eligible only when both variants have a served row, exactly once each",
        "chosen_groups": chosen,
        "execution_order": episodes,
        "episodes": len(episodes),
        "subjects": subjects,
        "subject": {"requested_id": subjects[0]},
        "arm": arm,
        "settings": {"temperature": arm["sampling"]["temperature"], "turns": arm["turns"],
                     "episode_output_ceiling": arm["max_total_completion_tokens"],
                     "fresh_context_per_episode": True, "retries": arm["retry_policy"]["retries"],
                     "one_attempt_per_cell": True},
        "rules": [
            "no cell is re-run, refilled or substituted; a missing outcome stays missing and is reported "
            "against the planned denominator",
            "a provider refusal is ATTEMPTED_UNSCORED, never a model failure; a cell never reached is UNATTEMPTED",
            "rows taken under any other value in `arm` are another arm and are never pooled with these",
            "the subject's own outputs never adjudicate the subject's own cells",
            "every result row quotes this record's self_digest; a row without it is not a row of this screen",
        ],
        "selection_problems": problems,
    }
    # The self-digest covers the draw, the bindings and the arm, NOT where
    # the files were read from: the same draw over the same serving bytes
    # yields the same digest from a checkout at any location. The paths are
    # still recorded, beside the sha256 that actually binds the bytes.
    record["digest_excludes"] = ["serving_record.path", "serving_record.manifest.path"]
    digested = json.loads(json.dumps(record))
    holder = digested.get("serving_record") or {}
    holder.pop("path", None)
    if isinstance(holder.get("manifest"), dict):
        holder["manifest"].pop("path", None)
    body = json.dumps(digested, indent=1, sort_keys=True).encode("utf-8")
    record["self_digest"] = hashlib.sha256(body).hexdigest()
    out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    print(f"serving record: {record_in['binding']['sha256'][:16]}... ({record_in['binding']['bytes']} bytes, "
          f"{record_in['binding']['rows']} rows, {record_in['binding']['served_rows']} served); "
          f"manifest {'bound' if record_in['binding']['manifest'] else 'not present in the record'}")
    print(f"population: {identity['population']} split map {identity['split_map_digest']} profile "
          f"{identity['profile_digest']} gates {identity['gate_set_digest']}")
    print(f"eligible per stratum: {record['eligible_groups_per_stratum']}")
    for mechanism, groups in chosen.items():
        print(f"  {mechanism:<24} {groups}")
    print(f"\nexecution order ({len(episodes)} episodes):")
    for i, selector in enumerate(episodes, 1):
        print(f"  {i:2d}. {selector}")
    print(f"\nsubjects: {subjects}")
    print(f"arm: {' '.join(arm['runner_flags'])}")
    print(f"\nproblems: {problems or 'none'}")
    print(f"written: {out}  selection digest {record['self_digest']}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
