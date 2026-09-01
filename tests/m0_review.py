"""Independent review of the whole M0 deliverable, before it gets scaled up.

The reward has been hardened over twenty-five rounds against two model families
and both now come back empty. That is good evidence it resists the attacks
those two thought of, and no evidence at all about the questions they were
never asked: whether the thing measures what it should, whether the world is
sound, whether the tests cover what matters, and what a generator built on top
of this would inherit.

A different reader, given the whole package at once and asked to be critical,
is the cheapest way to find out. This is not the review loop — nothing here
asks anyone to defeat the scoring.

    python tests/m0_review.py prompt
    python tests/m0_review.py run --model moonshotai/kimi-k3
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
WORLD = ROOT / "beancount_ledger" / "world"
OUT = HERE / "adversary_out"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

BRIEF = """You are reviewing a piece of work before it gets built on. Be
critical and concrete. I would rather hear an uncomfortable finding now than
discover it after a generator has produced a thousand copies of the same
mistake.

WHAT THIS IS

A reinforcement-learning environment for bookkeeping. An agent is given a small
company's books plus the source documents a bookkeeper would have, and asked to
reconcile the month. Two items on the bank statement were never posted to the
ledger; a third item, a check issued near period end, had not cleared and is a
timing difference that must be left alone. The agent explores the files with
tools and writes back a corrected ledger. A deterministic function scores it —
no model, no judgement, no tolerance bands.

This is the first task in what will become a family. Next step is a generator:
change a seed, get a different company, period and set of planted errors. So
anything wrong here gets multiplied.

WHAT I WANT FROM YOU

1. THE SCORING FUNCTION. Does it measure the right thing? Is the weighting
   defensible? Are the penalties proportionate to the harm? Is there a
   submission that would be marked wrongly — either a good one punished or a
   poor one rewarded — that the test cases below do not cover?

2. THE REWARD AS A TRAINING SIGNAL. An agent will be trained against this.
   What behaviour does this reward actually teach? Is there anything here that
   would train a habit you would not want in a bookkeeping agent?

3. THE WORLD AND THE TASK. Realistic? Internally consistent? Is the task
   well-posed — is there exactly one defensible answer, and is it reachable
   from the documents given?

4. THE TEST SUITE. What is it not testing? Where could this break silently?

5. WHAT A GENERATOR WOULD INHERIT. If this exact design were parameterised by
   a seed, what would go wrong at scale that is invisible at n=1?

6. VERDICT. Is this sound enough to build on? Name the single most important
   thing to fix first.

===============================================================================
THE SCORING FUNCTION
===============================================================================
{reward}

===============================================================================
THE TASK DEFINITION
===============================================================================
{task}

===============================================================================
THE WORLD THE AGENT SEES
===============================================================================
{world}

===============================================================================
THE TEST SUITE
===============================================================================
Each case below is a submitted ledger that must score at or below its cap. Most
were found by review passes against the scoring function; a few were written to
exercise a code path rather than to catch anything.

{cases}
===============================================================================
"""


def build_prompt() -> str:
    reward = (ROOT / "beancount_ledger" / "reward.py").read_text(encoding="utf-8")
    task = (ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json").read_text(encoding="utf-8")
    world = "\n".join(
        f"--- {p.name} ---\n{p.read_text(encoding='utf-8')}"
        for p in sorted(WORLD.iterdir())
        if p.is_file()
    )
    cases_src = (HERE / "test_reward.py").read_text(encoding="utf-8")
    block = cases_src[cases_src.index("CASES = {"):cases_src.index("}\n", cases_src.index("CASES = {")) + 1]
    return BRIEF.format(reward=reward, task=task, world=world, cases=block)


def run(args) -> int:
    from openai import OpenAI

    key = os.environ.get(args.key_var)
    if not key:
        raise SystemExit(f'{args.key_var} is not set.  setx {args.key_var} "your-key"')

    prompt = build_prompt()
    print(f"model  : {args.model}")
    print(f"prompt : {len(prompt)} chars (~{len(prompt)//4} tokens)\nsending...\n")

    reply = OpenAI(base_url=args.base_url, api_key=key).chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=6000,
    ).choices[0].message.content or ""

    OUT.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", args.model.lower()).strip("_")
    path = OUT / f"m0_review_{slug}_{datetime.now():%Y%m%d_%H%M%S}.md"
    path.write_text(reply, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(reply)
    print(f"\nsaved: {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--key-var", default="NVIDIA_API_KEY")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompt").set_defaults(func=lambda a: (print(build_prompt()), 0)[1])
    p_run = sub.add_parser("run")
    p_run.add_argument("--model", default="moonshotai/kimi-k3")
    p_run.set_defaults(func=run)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
