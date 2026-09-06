"""Have a model review the world and the task scenario for realism.

The first milestone ended with a human realism review of the demo world. This puts
a model in that seat: it sees exactly what the agent sees (system prompt,
task prompt, every world file) plus — marked as reviewer-only — the task
definition with the answer key, so it can judge whether the planted
discrepancies and the trap are the kind that occur in real reconciliations.

    python tests/review_world.py --model moonshotai/kimi-k3

One request, no tools; the review is written to reviews/ and printed. The
API key is read from HKCU\\Environment (NVIDIA_API_KEY) and never printed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
KEY_VAR = "NVIDIA_API_KEY"
PACKAGE = ROOT / "beancount_ledger"
WORLD = PACKAGE / "world"
REVIEWS = ROOT / "reviews"

WORLD_ORDER = ["manifest.md", "policy.md", "accounts.csv", "customers.csv", "vendors.csv",
               "archive_prior_period.csv", "ledger.beancount", "bank_statement.csv"]

REVIEW_INSTRUCTIONS = """\
You are a small-business accountant with twenty years of practice, and at the same
time an auditor of reinforcement-learning environment design. Below is the "world"
of one such environment: a small trading company's Beancount ledger, its bank
statement, chart of accounts, customer and vendor lists, the prior period's archive,
the bookkeeping policy; and the task text the agent receives. At the very end, FOR
YOUR EYES ONLY, the task definition and the answer key (the agent never sees them).

Your job is a REALISM review. Judge the world and the scenario, not the scoring
code. Be concrete: for every finding give the file name and the line (or record),
say in one sentence why it is not realistic, and propose the fix. No praise; where
there is no problem say "no problem" and move on.

Answer in English, in Markdown, under these headings:

## A. Overall impression
One paragraph: does this look like a real small company's books and a real bank
statement? What gives it away as "synthetic" at first glance?

## B. Findings file by file
One subheading per file. Amounts, dates, names, account names, the sales-tax
rate, margins, rent, balances, reference numbers, the statement format (would a
bank really export a CSV like this?), the wording of narrations and payees — would
the real world look like this? Look especially for synthetic traces: round numbers,
uniform intervals, name templates, date patterns.

## C. The task scenario
The task text plus the policy: is this the job a real accountant would be given? Is
anything vague or unfair (a behaviour the policy does not state but the scoring
expects)? Do the planted differences (an unrecorded ACH receipt, an unrecorded bank
fee) and the trap (an outstanding cheque) occur like this in real reconciliations?
Which difference kinds are typical of real reconciliations and absent here (NSF or
bounced cheques, date drift, double entries, transposed digits, wrong amounts,
receipts net of a deduction, and so on)?

## D. Evidence and determinability
Do the statement rows give the agent enough evidence to write the correct entry in
ONE way only? Could an accountant reach a different correct result from this
statement and this ledger? (For example: is the invoice a receipt settles visible on
the statement, or inferred from the amount alone?)

## E. Scores (1–5, one line of reasoning each)
- Realism
- Difficulty (for a junior accountant)
- Absence of ambiguity
- Fairness of the trap

## F. The five most important fixes
In priority order, one sentence each plus the file and line.
"""


def load_key_from_registry() -> None:
    if os.environ.get(KEY_VAR):
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
        value, _ = winreg.QueryValueEx(handle, KEY_VAR)
    os.environ[KEY_VAR] = value


def numbered(text: str) -> str:
    return "\n".join(f"{i + 1:4d}  {line}" for i, line in enumerate(text.splitlines()))


def build_prompt(task_id: str) -> tuple[str, str]:
    from beancount_ledger.beancount_ledger import SYSTEM_PROMPT

    task_path = PACKAGE / "tasks" / f"{task_id}.json"
    task_json = task_path.read_text(encoding="utf-8")
    import json

    task_prompt = json.loads(task_json)["prompt"]

    parts = [REVIEW_INSTRUCTIONS, "\n---\n\n# The system message the agent sees\n\n```\n" + SYSTEM_PROMPT.strip() + "\n```\n",
             "\n# The task text the agent sees\n\n```\n" + task_prompt.strip() + "\n```\n",
             "\n# World files (the agent reads these through tools; the line numbers are for you)\n"]
    for name in WORLD_ORDER:
        path = WORLD / name
        if not path.is_file():
            continue
        parts.append(f"\n## {name}\n\n```\n{numbered(path.read_text(encoding='utf-8'))}\n```\n")
    extra = sorted(p.name for p in WORLD.iterdir() if p.is_file() and p.name not in WORLD_ORDER)
    for name in extra:
        parts.append(f"\n## {name}\n\n```\n{numbered((WORLD / name).read_text(encoding='utf-8'))}\n```\n")
    parts.append("\n---\n\n# FOR THE REVIEWER ONLY — task definition and answer key (the agent never sees this)\n\n```json\n" + task_json.strip() + "\n```\n")
    return "".join(parts), task_prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="moonshotai/kimi-k3")
    parser.add_argument("--task", default="bank_recon_001")
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_key_from_registry()

    import openai

    prompt, _ = build_prompt(args.task)
    print(f"model  : {args.model}")
    print(f"prompt : {len(prompt):,} chars, {len(prompt.split()):,} words", flush=True)

    client = openai.OpenAI(api_key=os.environ[KEY_VAR], base_url=NVIDIA_BASE_URL,
                           timeout=args.timeout, max_retries=0)
    text = None
    usage = None
    for attempt in range(6):
        t0 = time.time()
        try:
            response = client.chat.completions.create(
                model=args.model, max_tokens=args.max_tokens, temperature=0.3,
                messages=[{"role": "user", "content": prompt}])
            text = response.choices[0].message.content or ""
            usage = response.usage
            print(f"answered in {time.time() - t0:.0f}s", flush=True)
            break
        except openai.RateLimitError:
            pause = 30.0 * (attempt + 1)
            print(f"429 from the provider; pausing {pause:.0f}s (attempt {attempt + 1}/6)", flush=True)
            time.sleep(pause)
        except openai.APITimeoutError:
            print(f"timed out after {time.time() - t0:.0f}s (attempt {attempt + 1}/6)", flush=True)
    if text is None:
        print("no review: the provider never answered")
        return 2

    REVIEWS.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    slug = args.model.split("/")[-1]
    out = REVIEWS / f"realism_{slug}_{stamp}.md"
    header = (f"# Realism review — {args.model}, {stamp}\n\n"
              f"*The model saw the system message the agent sees, the task text and the {len(WORLD_ORDER)} world files "
              f"with line numbers, plus, marked reviewer-only, the task definition and the answer key. "
              f"One request, no tools, temperature 0.3.*\n\n"
              + (f"*Tokens: {usage.prompt_tokens} in, {usage.completion_tokens} out.*\n\n" if usage else "")
              + "---\n\n")
    out.write_text(header + text.strip() + "\n", encoding="utf-8")
    print(f"written: {out}")
    print("=" * 70)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
