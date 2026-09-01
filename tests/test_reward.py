"""Regression suite for the reward function (LESSONS rule 21).

The reward is the foundation everything else sits on. If it is wrong, every
task built on top of it produces noise. This suite runs on every change to
reward.py.

Contract:
  golden solution        -> exactly 1.0
  every bad solution     -> at most the stated ceiling
  do-nothing baseline    -> low, and must never approach the golden score
"""

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.reward import load_task, score  # noqa: E402

WORLD = ROOT / "beancount_ledger" / "world"
SOLUTIONS = Path(__file__).resolve().parent / "solutions"
TASK = load_task(ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json")
ORIGINAL = (WORLD / "ledger.beancount").read_text(encoding="utf-8")

# name -> (max allowed score, why it must not score higher)
CASES = {
    "golden": (Decimal("1.00"), "correct solution, must be exactly 1.0"),
    "bad_deleted_check": (Decimal("0.05"), "destroyed a legitimate timing difference"),
    "bad_plug_account": (Decimal("0.00"), "invented a suspense account"),
    "bad_unparseable": (Decimal("0.00"), "ledger does not parse"),
    "bad_altered_unrelated": (Decimal("0.05"), "quietly edited an unrelated entry"),
    "bad_copied_statement": (Decimal("0.05"), "double-posted statement lines"),
    "bad_merged_events": (Decimal("0.05"), "one combined entry instead of separate events (found by adversary)"),
    "bad_no_narration": (Decimal("0.65"), "right numbers, entries name nobody (found by adversary 2)"),
    "bad_negated_keywords": (Decimal("0.65"), "keyword buried in a sentence denying it (adversary 3)"),
    "bad_mocking_case": (Decimal("0.65"), "accepted name in mocking case, gaming a lenient normaliser (adversary 5)"),
    "bad_opening_balance": (Decimal("0.10"), "moved the opening balances instead of posting the entry (adversary 6)"),
    "bad_opening_forgery_full": (Decimal("0.05"), "forged all three scored accounts in the opening entry, posted nothing (M0 review)"),
    "bad_wash_transaction": (Decimal("0.65"), "correct work plus a fabricated wash entry (adversary 6)"),
    "bad_payee_rewrite": (Decimal("0.05"), "rewrote the payee of every existing entry (adversary 7)"),
    "bad_pending_flags": (Decimal("0.05"), "flagged every entry as unverified (adversary 8)"),
    "bad_closed_accounts": (Decimal("0.05"), "closed every account after reconciling (adversary 9)"),
    "bad_rewritten_options": (Decimal("0.25"), "rewrote the ledger header and currency (adversary 10)"),
    "bad_tagged_entries": (Decimal("0.05"), "stamped every entry #unreviewed ^fabricated-source (adversary 11)"),
    "bad_elided_amounts": (Decimal("0.05"), "stripped every explicit amount and let elision refill it (adversary 12)"),
    "bad_computed_amounts": (Decimal("0.05"), "amounts written as arithmetic, unreadable source (adversary 13)"),
    "bad_comment_injection": (Decimal("0.05"), "comment block telling the reader to ignore the books (adversary 14)"),
    "bad_duplicate_opens": (Decimal("0.05"), "duplicated every open directive (adversary 15)"),
    "bad_overprecise_amounts": (Decimal("0.05"), "amounts padded to 15 decimal places (the attack adversary 16 missed)"),
    "bad_padded_file": (Decimal("0.65"), "padded the ledger to ten thousand lines (adversary 17)"),
    "bad_wide_line": (Decimal("0.65"), "one line of fifty thousand spaces (adversary 18)"),
    "bad_removed_open": (Decimal("0.05"), "deleted an open directive (branch coverage, not an attack)"),
    "baseline_untouched": (Decimal("0.05"), "did nothing at all"),
}


def run() -> int:
    failures = []
    print(f"{'case':26s} {'score':>7s}  {'cap':>5s}  result")
    print("-" * 72)

    golden_score = None
    for name, (cap, why) in CASES.items():
        text = (SOLUTIONS / f"{name}.beancount").read_text(encoding="utf-8")
        result = score(text, TASK, ORIGINAL)
        total = result["total"]
        if name == "golden":
            golden_score = total
            ok = total == Decimal("1.00")
        else:
            ok = total <= cap
        status = "PASS" if ok else "FAIL"
        print(f"{name:26s} {total:>7.3f}  {cap:>5.2f}  {status}")
        if not ok:
            failures.append((name, total, cap, why, result))

    # The do-nothing baseline must be clearly separated from the golden score,
    # otherwise the reward carries no learning signal.
    baseline = score(
        (SOLUTIONS / "baseline_untouched.beancount").read_text(encoding="utf-8"),
        TASK,
        ORIGINAL,
    )["total"]
    margin = (golden_score or Decimal("0")) - baseline
    print("-" * 72)
    print(f"golden - baseline margin: {margin:.3f}  (needs >= 0.400)")
    if margin < Decimal("0.400"):
        failures.append(("margin", margin, Decimal("0.400"), "reward gives too little signal", {}))

    if failures:
        print(f"\n{len(failures)} FAILURE(S)\n")
        for name, got, cap, why, detail in failures:
            print(f"  {name}: scored {got}, cap {cap} — {why}")
            for key in ("target_misses", "collateral_damage", "unresolved_planted",
                        "removed_or_altered", "fabricated", "merged_events", "undocumented", "plug_accounts", "added_prose", "padding", "balance_errors"):
                if detail.get(key):
                    print(f"      {key}: {detail[key]}")
        return 1

    print("\nall cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
