"""The independent bookkeeper: a model from another family reviews GENERATED
worlds from their public files alone — no hidden graph, no answer key —
and reports the discrepancies it finds and how real the books look.

    python tests/review_generated.py --model openai/gpt-oss-120b --selectors train:5 train:17 eval:2

Each selector is minted privately here; the reviewer sees the public
bundle only. The review lands in reviews/generated_<model>_<date>.md with,
per world, the reviewer's repairs beside the planted truth (added by this
script AFTER the model answered) so the comparison is honest.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")     # development: a test secret has no release manifest

from beancount_ledger.graph.mint import mint  # noqa: E402
from beancount_ledger.graph.generate import DEFAULT_PROFILE, HARD_PROFILE  # noqa: E402

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

INSTRUCTIONS = """You are a senior bookkeeper doing a month-end bank reconciliation for a
small trading company. You are given the company's ledger (Beancount), the
bank statement for the month, the prior month's statement, the chart of
accounts, customer and vendor masters and the bookkeeping policy — exactly
what the junior who prepared the books had. Nothing else exists.

Part A — reconcile. List every discrepancy between the books and the
bank: entries the books are missing, entries booked with a wrong amount,
entries booked twice, and items that are timing differences (outstanding
cheques, deposits in transit) and therefore NOT errors. For each, give the
date, the amount, the counterparty, which account you would post to and
why (cite the policy or the master file). Be precise; do not guess.

Part B — realism. As a bookkeeper who has seen many such months: does
this look like a real small company's month? Comment on amount
distributions, narrations, counterparties, cheque timing, fee wording,
anything implausible. Score 1–5 for realism and 1–5 for difficulty.

Answer in English, Part A as a table, Part B as short prose."""


def _key() -> str:
    key = os.environ.get("NVIDIA_API_KEY")
    if not key and os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
            key = winreg.QueryValueEx(h, "NVIDIA_API_KEY")[0]
    if not key:
        raise SystemExit("no NVIDIA_API_KEY")
    return key


def numbered(text: str) -> str:
    return "\n".join(f"{i:4d}  {line}" for i, line in enumerate(text.splitlines(), 1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--selectors", nargs="+", required=True)
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()
    import openai
    client = openai.OpenAI(api_key=_key(), base_url=NVIDIA_BASE_URL, timeout=args.timeout, max_retries=3)
    out = ROOT / "reviews"
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    slug = args.model.split("/")[-1]
    path = out / f"generated_{slug}_{stamp}.md"
    sections = [f"# Generated-world reviews — {args.model}, {stamp}\n\n*The reviewer saw public files only. "
                f"The planted truth is appended by the script after each answer.*\n"]
    for selector in args.selectors:
        namespace, index, *rest = selector.split(":")
        profile = HARD_PROFILE if rest and rest[0] == "hard" else DEFAULT_PROFILE
        minted = mint(namespace, int(index), profile)     # keyed: PIV_EVAL_SECRET must be set on the evaluator
        files = dict(minted.inputs.public_files)
        prompt = INSTRUCTIONS + "\n\n# Task\n\n" + minted.inputs.prompt + "\n"
        for name in ("manifest.md", "policy.md", "accounts.csv", "customers.csv", "vendors.csv", "ledger.beancount",
                     "bank_statement.csv", "archive_prior_period.csv"):
            prompt += f"\n\n## {name}\n\n```\n{numbered(files[name].decode('utf-8'))}\n```\n"
        print(f"{selector}: {minted.inputs.task_id} — {len(prompt):,} chars, {len(minted.inputs.planted)} planted")
        response = client.chat.completions.create(
            model=args.model, messages=[{"role": "user", "content": prompt}], temperature=0.2, max_tokens=args.max_tokens)
        text = response.choices[0].message.content or ""
        truth = "\n".join(f"- {p.kind} — {p.id}: {p.date} {p.must_be_payee[0]} {p.required} (evidence: {', '.join(p.evidence)})"
                          for p in minted.inputs.planted)
        traps = "\n".join(f"- outstanding: {t.id} {t.date} {t.amount}" for t in minted.inputs.traps)
        sections.append(f"\n---\n\n## {selector} → {minted.inputs.task_id}\n\n{text}\n\n### Planted truth (appended after the answer)\n\n{truth}\n{traps}\n")
        path.write_text("".join(sections), encoding="utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
