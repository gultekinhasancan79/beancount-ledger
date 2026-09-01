"""Drive the adversary pass from the terminal against any OpenAI-compatible API.

Built for NVIDIA's endpoint (free, OpenAI-compatible, and the open-weight
families there are the blind-spot diversity rule 5.5 actually needs), but the
base URL is a flag, so anything speaking the same protocol works.

Setup, once:

    setx NVIDIA_API_KEY "nvapi-..."        # then open a new terminal

Usage:

    python tests/run_adversary.py list                    # what is available
    python tests/run_adversary.py list --grep qwen
    python tests/run_adversary.py attack --model <id>     # attack, save, score

The response is written to tests/adversary_out/ and scored immediately. A run
that scores above the threshold has found a hack: harden the reward, add the
submission as a regression case, and attack again (rule 28) — a patch is new
code and new code has new edges.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adversary import (  # noqa: E402
    ORIGINAL,
    TASK,
    build_prompt,
    score,
    score_candidate,
)

SHORTFALL_KEYS = (
    "target_misses", "collateral_damage", "unresolved_planted",
    "removed_or_altered", "fabricated", "merged_events", "undocumented",
    "plug_accounts", "added_prose", "padding", "balance_errors",
)

OUT = Path(__file__).resolve().parent / "adversary_out"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"


def client(base_url: str, key_var: str):
    from openai import OpenAI

    key = os.environ.get(key_var)
    if not key:
        raise SystemExit(
            f"{key_var} is not set.\n"
            f'  setx {key_var} "your-key-here"   then open a new terminal'
        )
    return OpenAI(base_url=base_url, api_key=key)


def cmd_list(args) -> int:
    models = client(args.base_url, args.key_var).models.list()
    ids = sorted(m.id for m in models.data)
    if args.grep:
        rx = re.compile(args.grep, re.IGNORECASE)
        ids = [i for i in ids if rx.search(i)]
    for model_id in ids:
        print(model_id)
    print(f"\n{len(ids)} model(s)")
    return 0


def cmd_attack(args) -> int:
    """Sample the adversary several times and report the most dangerous result.

    Finding a loophole is a search, and one draw is a thin one. A model run at
    a high reasoning budget explores far more of that space than a single
    default-settings call — which was exactly the asymmetry that made one model
    family look sharper than another here. Sampling is the cheap correction.
    """
    prompt = build_prompt()
    api = client(args.base_url, args.key_var)
    OUT.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", args.model.lower()).strip("_")

    print(f"model      : {args.model}")
    print(f"prompt     : {len(prompt)} chars (~{len(prompt) // 4} tokens)")
    print(f"samples    : {args.samples}\n")

    best_rank, best_path = None, None
    for i in range(1, args.samples + 1):
        choice = api.chat.completions.create(
            model=args.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        ).choices[0]
        text = choice.message.content or ""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        (OUT / f"{slug}_{stamp}_s{i}.txt").write_text(text, encoding="utf-8")

        ledger = extract_ledger(text)
        if not ledger:
            print(f"  sample {i}: no ledger — argued the reward is safe "
                  f"[{choice.finish_reason}]")
            continue

        ledger_path = OUT / f"{slug}_{stamp}_s{i}.beancount"
        ledger_path.write_text(ledger, encoding="utf-8")
        result = score(ledger, TASK, ORIGINAL)
        shortfalls = sum(1 for k in SHORTFALL_KEYS if result.get(k))
        print(f"  sample {i}: score {result['total']:.3f}  "
              f"shortfalls {shortfalls}  [{choice.finish_reason}]")

        # The dangerous submission is the one scoring highest while the reward
        # still failed to catch something.
        rank = (result["total"], -shortfalls)
        if best_rank is None or rank > best_rank:
            best_rank, best_path = rank, ledger_path

    if best_path is None:
        print("\nNo sample produced a ledger. Reward held.")
        return 0

    print(f"\nstrongest attempt: {best_path.name}\n")
    return score_candidate(str(best_path))


def extract_ledger(text: str) -> str | None:
    """Pull the ledger out of a reply that may wrap it in a code fence."""
    fenced = re.findall(r"```(?:beancount|text)?\s*\n(.*?)```", text, re.DOTALL)
    candidates = fenced or [text]
    for block in candidates:
        if "open Assets:" in block or re.search(r"^\s*\d{4}-\d{2}-\d{2} ", block, re.M):
            return block.strip() + "\n"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--key-var", default="NVIDIA_API_KEY")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list available models")
    p_list.add_argument("--grep", help="filter ids by regex")
    p_list.set_defaults(func=cmd_list)

    p_attack = sub.add_parser("attack", help="run the attack and score it")
    p_attack.add_argument("--model", required=True)
    p_attack.add_argument("--samples", type=int, default=5,
                          help="how many independent attempts to draw")
    p_attack.add_argument("--temperature", type=float, default=1.0)
    p_attack.add_argument("--max-tokens", type=int, default=8000)
    p_attack.set_defaults(func=cmd_attack)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
