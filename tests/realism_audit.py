"""Domain-realism audit of the world (LESSONS rule 24, second column).

Rule 24 splits the review into three jobs with three different auditors:
correctness is the script's, shape is the human's, and domain realism belongs
to someone who knows the domain. Hiring that person is expensive and finding
one is slow, so a finance-tuned model from a different family stands in.

This is NOT the adversary. It is not asked to attack, to game anything, or to
solve the task — only to say whether the scenario would survive contact with a
real set of books, and where it would not.

    python tests/realism_audit.py prompt
    python tests/realism_audit.py run --model writer/palmyra-fin-70b-32k

Output is prose for a human to read. There is no score: realism is a judgement,
and judgement never enters the reward (rule 7).
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

from beancount_ledger.reward import load_task  # noqa: E402

WORLD = ROOT / "beancount_ledger" / "world"
TASK = load_task(ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json")
OUT = Path(__file__).resolve().parent / "adversary_out"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

AUDIT = """You are a senior bookkeeper reviewing a synthetic set of books built \
to train and evaluate AI agents. Your job is to judge whether it would survive \
contact with reality.

Do NOT solve the reconciliation. Do not attack or game anything. Assess the
scenario as an experienced practitioner reading someone else's books.

The intended exercise: the November bank statement has arrived and two items on
it were never posted to the ledger — a customer receipt and a monthly service
charge. A third item, a check issued on 28 November, is recorded in the ledger
but had not cleared by the cut-off; it is a timing difference and must be left
alone.

Answer these, briefly and concretely:

1. REALISM. Would a bookkeeper at a small trading company plausibly face this,
   in this form? Anything here that would never happen?

2. FIGURES. Are the amounts internally consistent and proportionate for a
   business of this size? Anything implausible in scale, or in the relationship
   between revenue, margin, receivables, rent and payroll?

3. MISSING. What would normally be present in a real November that is absent
   here, and whose absence a practitioner would notice? Be specific.

4. THE TRAP. Is the outstanding check a fair test, or does it read as a
   contrivance? Would a competent bookkeeper handle it the intended way?

5. ERRORS. Are there mistakes in the books themselves — dates, classifications,
   VAT treatment, chart of accounts, anything that is simply wrong?

6. VERDICT. One paragraph: is this good enough to put in front of a
   professional, and what is the single change that would most improve it?

===============================================================================
THE BOOKS
===============================================================================
{files}
===============================================================================
"""


def build_prompt() -> str:
    files = "\n".join(
        f"--- {p.name} ---\n{p.read_text(encoding='utf-8')}"
        for p in sorted(WORLD.iterdir())
        if p.is_file()
    )
    return AUDIT.format(files=files)


def run(args) -> int:
    from openai import OpenAI

    key = os.environ.get(args.key_var)
    if not key:
        raise SystemExit(f'{args.key_var} is not set.  setx {args.key_var} "your-key"')

    print(f"model : {args.model}\nsending...\n")
    reply = OpenAI(base_url=args.base_url, api_key=key).chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": build_prompt()}],
        temperature=0.3,
        max_tokens=4000,
    ).choices[0].message.content or ""

    OUT.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", args.model.lower()).strip("_")
    path = OUT / f"realism_{slug}_{datetime.now():%Y%m%d_%H%M%S}.md"
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
    p_run.add_argument("--model", default="writer/palmyra-fin-70b-32k")
    p_run.set_defaults(func=run)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
