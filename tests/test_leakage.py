"""Script-level leakage scan (LESSONS rules 11, 5.4).

These are the checks a model should never be paid to do. They run first and
they run free. Only what survives here is worth an adversary's attention.

  1. verbatim      does the answer appear literally in the world?
  2. single file   can one file alone yield the answer?
  3. filename      does a file name give the task away?
  4. baselines     do stupid constant policies score well?
"""

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.reward import load_task, score  # noqa: E402

WORLD = ROOT / "beancount_ledger" / "world"
TASK = load_task(ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json")
ORIGINAL = (WORLD / "ledger.beancount").read_text(encoding="utf-8")

BASELINE_CAP = Decimal("0.30")
WORLD_FILES = sorted(p for p in WORLD.iterdir() if p.is_file())


def _norm(value: str) -> list[str]:
    """Surface forms a number might take in a document."""
    d = Decimal(value)
    plain = f"{abs(d):.2f}"
    return [plain, plain.replace(",", ""), f"{abs(d):,.2f}"]


def check_verbatim() -> list[str]:
    """The derived answers must not be sitting in a file ready to be copied.

    The evidence values (4600, 85) are supposed to be present — that is the
    point of a bank statement. What must not be present is anything that only
    exists after the work has been done.
    """
    problems = []
    derived = {
        "Assets:Bank:Checking closing": TASK["expected_balances"]["Assets:Bank:Checking"],
        "Assets:AR closing": TASK["expected_balances"]["Assets:AR"],
    }
    for label, value in derived.items():
        for form in _norm(value):
            for path in WORLD_FILES:
                if form in path.read_text(encoding="utf-8"):
                    problems.append(f"{label} ({form}) appears verbatim in {path.name}")
    return problems


def check_single_file() -> list[str]:
    """No single file may contain every planted value on its own."""
    needed = {
        form
        for item in TASK["planted"]
        for _account, amount in item["required_postings"]
        for form in _norm(amount)[:1]
    }
    problems = []
    for path in WORLD_FILES:
        if path.name == "ledger.beancount":
            continue
        text = path.read_text(encoding="utf-8")
        if all(value in text for value in needed) and "bank_statement" not in path.name:
            problems.append(f"{path.name} contains every planted value on its own")
    return problems


def check_filenames() -> list[str]:
    banned = ("answer", "solution", "expected", "truth", "key", "fix", "correct")
    return [
        f"{p.name} contains a giveaway word"
        for p in WORLD_FILES
        if any(word in p.name.lower() for word in banned)
    ]


def check_baselines() -> list[str]:
    """Constant policies that do no accounting must score near zero."""
    chart = "\n".join(
        line for line in ORIGINAL.splitlines()
        if line.startswith("option") or " open " in line
    )
    baselines = {
        "do nothing": ORIGINAL,
        "empty ledger": chart + "\n",
        "chart only, no transactions": chart + "\n",
    }
    problems = []
    for name, text in baselines.items():
        total = score(text, TASK, ORIGINAL)["total"]
        print(f"    baseline {name:32s} -> {total:.3f}")
        if total > BASELINE_CAP:
            problems.append(f"baseline '{name}' scored {total:.3f} (cap {BASELINE_CAP})")
    return problems


def run() -> int:
    checks = [
        ("verbatim answer in world files", check_verbatim),
        ("single file sufficiency", check_single_file),
        ("filename giveaway", check_filenames),
        ("dumb baseline policies", check_baselines),
    ]
    failures = []
    for label, fn in checks:
        print(f"  {label}")
        problems = fn()
        if problems:
            failures.extend(problems)
            for p in problems:
                print(f"    LEAK: {p}")
        else:
            print("    clean")

    print()
    if failures:
        print(f"{len(failures)} leak(s) found")
        return 1
    print("no leaks found")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
