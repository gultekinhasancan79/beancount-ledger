"""Facts about the RUNNING pilot, read-only (Codex T48a Q3 and Q9).

    python tests/pilot_facts.py
    python tests/pilot_facts.py --reviews-dir C:\\...\\prime\\environments\\beancount_ledger\\reviews

Answers, from archived rows and without repeating a single provider call:

  Q3  How many turns carry TOOL-CALL ARGUMENTS larger than the visible
      content + reasoning of the same turn (especially `write_ledger`), and
      what would such a turn's reported completion tokens imply?

  Q9  How many complete ledger reads can one assistant turn and one episode
      issue, and what aggregate observation volume does that create at the
      48 KB envelope?

WHAT IS AND IS NOT DERIVABLE FROM THESE ROWS. The pilot rows predate
`per_turn[i]["tool_call_chars"]`, so the tool-call argument size is not
recorded directly. It is RECONSTRUCTED here from an identity the rows do
support, and the reconstruction is labelled as such everywhere it is used:

    visible_chars_in_history[t+1] - visible_chars_in_history[t]
        = assistant_content_chars[t]        (the turn's own visible text)
        + tool-call argument characters[t]  (what we want)
        + tool-reply characters[t]          (what the tools answered)

`visible_chars_in_history` is what `per_turn_rows` counted in the PROMPT the
model saw that turn, and it accumulates exactly those three things. So

    non_content_added[t] = delta[t] - assistant_content_chars[t]
                         = tool-call arguments + tool replies

is an UPPER BOUND on the turn's tool-call characters. A turn flagged below
is therefore a candidate, not a proof — except where the tool list makes the
split obvious (a `write_ledger` turn's reply is a short receipt, so almost
all of `non_content_added` is the write argument; a `read_file` turn's
argument is a few dozen characters, so almost all of it is the reply). Both
readings are printed, never merged.

The last turn of an episode has no successor prompt, so its delta is
unknown and it is excluded from the flagged count rather than guessed.

Nothing here writes to the files it reads.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The pilot's own files: the replicated arm set (`*_r1`) plus the two
# NVIDIA rows from the first corrected-contract cells.
DEFAULT_PATTERNS = ("budget_*_2026-08-30_*_r1.json",
                    "budget_*_2026-08-30_Ap_train1.json",
                    "budget_*_2026-08-30_B1p_train1.json")


def load(reviews_dir: Path, patterns) -> list[tuple[Path, dict]]:
    rows = []
    for pattern in patterns:
        for path in sorted(reviews_dir.glob(pattern)):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:                  # noqa: BLE001
                print(f"WARNING: {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            for row in data if isinstance(data, list) else []:
                rows.append((path, row))
    return rows


def turn_facts(row: dict) -> list[dict]:
    """Per turn: the reconstruction described in the module docstring."""
    per_turn = row.get("per_turn") or []
    facts = []
    for index, turn in enumerate(per_turn):
        following = per_turn[index + 1] if index + 1 < len(per_turn) else None
        delta = (None if following is None else
                 (following.get("visible_chars_in_history") or 0) - (turn.get("visible_chars_in_history") or 0))
        content = turn.get("assistant_content_chars") or 0
        reasoning = turn.get("assistant_reasoning_chars") or 0
        recorded = turn.get("tool_call_chars")          # present on rows from the corrected instrument
        facts.append({
            "turn": turn.get("turn"),
            "tools": turn.get("tools") or [],
            "output_tokens": turn.get("output_tokens"),
            "content_chars": content,
            "reasoning_chars": reasoning,
            "recorded_tool_call_chars": recorded,
            "non_content_added": (None if delta is None else max(0, delta - content)),
        })
    return facts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviews-dir", default=None,
                        help="defaults to this checkout's reviews/; point it at the MAIN checkout's reviews/ "
                             "to read the running pilot without touching it")
    parser.add_argument("--patterns", nargs="+", default=list(DEFAULT_PATTERNS))
    args = parser.parse_args()

    reviews_dir = Path(args.reviews_dir) if args.reviews_dir else ROOT / "reviews"
    rows = load(reviews_dir, args.patterns)
    if not rows:
        print(f"no pilot rows under {reviews_dir} matching {args.patterns}")
        return 1

    print(f"# Pilot facts — {len(rows)} row(s) from {reviews_dir}\n")

    # ---- Q3: tool-call arguments against visible output -------------------
    print("## Q3  Turns whose TOOL-CALL ARGUMENTS exceed their visible content + reasoning")
    print("")
    print("`non_content_added` = tool-call arguments + tool replies (an UPPER BOUND on the arguments alone; "
          "see this file's docstring). A `write_ledger` turn's reply is a short receipt, so its bound is close "
          "to the true argument size; a `read_file` turn's is dominated by the reply instead.")
    print("")
    flagged, flagged_write, considered = 0, 0, 0
    write_turns, other_turns = [], []
    for path, row in rows:
        for fact in turn_facts(row):
            if fact["non_content_added"] is None:
                continue
            considered += 1
            visible = fact["content_chars"] + fact["reasoning_chars"]
            if fact["non_content_added"] <= visible:
                continue
            flagged += 1
            entry = (row, fact, visible)
            if "write_ledger" in fact["tools"]:
                flagged_write += 1
                write_turns.append(entry)
            else:
                other_turns.append(entry)

    def emit(entries, title):
        print(f"**{title}**\n")
        print("| model | arm | selector | turn | tools | out tokens | content+reasoning | non_content_added | "
              "recorded tool_call_chars | chars/token with arguments counted |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for row, fact, visible in entries:
            out_tok = fact["output_tokens"] or 0
            ratio = ((visible + fact["non_content_added"]) / out_tok) if out_tok else float("inf")
            print(f"| {row.get('model')} | {row.get('arm')} | {row.get('selector')} | {fact['turn']} | "
                  f"{','.join(fact['tools']) or '-'} | {fact['output_tokens']} | {visible} | "
                  f"{fact['non_content_added']} | {fact['recorded_tool_call_chars']} | {ratio:.1f} |")
        print("")

    emit(write_turns, "write_ledger turns — the bound here is essentially the ARGUMENT (the reply is a receipt)")
    other_turns.sort(key=lambda e: -e[1]["non_content_added"])
    emit(other_turns[:8], f"largest 8 of {len(other_turns)} other flagged turns — these are dominated by the "
                          f"tool REPLY, not by the argument")
    print(f"- {flagged} of {considered} turns with a measurable delta carry more non-content characters than "
          f"visible output; {flagged_write} of them called `write_ledger`.")
    if write_turns:
        biggest = max(write_turns, key=lambda e: e[1]["non_content_added"])
        print(f"- Largest write turn: {biggest[1]['non_content_added']:,} non-content characters against "
              f"{biggest[2]:,} visible, reporting {biggest[1]['output_tokens']} completion tokens "
              f"({biggest[0].get('model')}, arm {biggest[0].get('arm')}, {biggest[0].get('selector')}).")
    print(f"- The pre-T48 plausibility floor summed `assistant_content_chars + assistant_reasoning_chars` "
          f"only, so on a TOOL-ONLY turn its denominator was ZERO and no reported completion token count, "
          f"however small, could fail it. At the 48,000-character write envelope that is the largest "
          f"completion payload in the task passing unchecked.")
    print("")

    # ---- Q9: repeated whole reads and observation volume ------------------
    print("## Q9  Complete ledger reads per turn and per episode, and observation volume")
    print("")
    print("The archived rows record tool NAMES per turn, not tool ARGUMENTS, so `read_file` cannot be split "
          "into ledger reads and other reads from the archive alone. The counts below are therefore for "
          "`read_file` as a whole — an UPPER bound on ledger reads and a lower bound on nothing.")
    print("")
    print("`piv_complete_reads` / `piv_observation_bytes` are the PACKAGE's own exact counters; they are "
          "`None` on every row written before they landed, and the surrounding columns are the archive's "
          "bound on the same quantities.")
    print("")
    print("| model | arm | selector | turns | max read_file per turn | read_file per episode | "
          "aggregate tool-reply chars | replayed observation chars (sum over turns of prompt history) | "
          "piv_complete_reads | piv_observation_bytes |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    max_per_turn_overall = 0
    max_per_episode_overall = 0
    for path, row in rows:
        per_turn = row.get("per_turn") or []
        per_turn_counts = [Counter(t.get("tools") or []).get("read_file", 0) for t in per_turn]
        max_per_turn = max(per_turn_counts, default=0)
        per_episode = sum(per_turn_counts)
        max_per_turn_overall = max(max_per_turn_overall, max_per_turn)
        max_per_episode_overall = max(max_per_episode_overall, per_episode)
        volume = row.get("volume") or {}
        replayed = sum(t.get("visible_chars_in_history") or 0 for t in per_turn)
        print(f"| {row.get('model')} | {row.get('arm')} | {row.get('selector')} | {len(per_turn)} | "
              f"{max_per_turn} | {per_episode} | {volume.get('tool_replies')} | {replayed:,} | "
              f"{row.get('complete_reads')} | {row.get('observation_bytes')} |")
    print("")
    print(f"- maximum `read_file` calls in ONE assistant turn, over the pilot: {max_per_turn_overall}")
    print(f"- maximum `read_file` calls in ONE episode, over the pilot: {max_per_episode_overall}")
    print(f"- The episode contract does not cap either number. The output ceiling bounds how many calls can be "
          f"AUTHORED (a call costs a few dozen completion tokens), so at the 40,000-token ceiling a turn could "
          f"in principle emit hundreds of `read_file` calls and multiply one 48,000-character observation into "
          f"the next request that many times. Nothing in the pilot did: the observed maxima are above.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
