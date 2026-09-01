"""Item-level recall of the blind bookkeeper reviews.

    python tests/recall_generated.py reviews/generated_minimax-m3_2026-08-29.md [...]

For every world section in a review file, the planted truth appended by
review_generated.py is parsed back and each planted item is looked up in
the reviewer's answer by its signed bank amount (any of the usual
spellings: 1,234.56 / 1234.56 / -1,234.56 / (1,234.56)). An item counts as
*found* when its amount appears in Part A at all, and as *classified* when
the nearest kind word (missing/omitted/not booked, wrong amount/mis-keyed/
transposed, duplicate/twice/double) matches the planted kind within the
same table row. The outstanding traps are checked the same way: a trap is
*respected* when its amount is mentioned together with timing language
(outstanding/in transit/timing) and never called an error.

This is a coarse instrument — it cannot see a correct repair described
without its amount — but it is the same instrument for every model and
every generator version, which is what a recall trend needs.
"""

from __future__ import annotations

import re
import sys
from decimal import Decimal
from pathlib import Path

KIND_WORDS = {
    "omit": ("missing", "omitted", "not booked", "not recorded", "unrecorded", "absent", "no entry", "not in the ledger",
             "not in ledger", "never booked", "missing entry"),
    "alter": ("wrong amount", "incorrect amount", "mis-keyed", "miskeyed", "transpos", "amount differs", "booked as",
              "recorded as", "should be", "difference of", "understated", "overstated", "wrong_amount", "amount error"),
    "duplicate": ("duplicate", "twice", "double", "booked two", "recorded two", "second entry", "dup"),
}
TIMING_WORDS = ("outstanding", "in transit", "timing", "not yet cleared", "uncleared", "has not cleared", "clears in",
                "not an error", "will clear")


def spellings(amount: Decimal) -> list[str]:
    a = abs(amount).quantize(Decimal("0.01"))
    plain = f"{a}"
    grouped = f"{a:,}"
    forms = {plain, grouped}
    if a == a.to_integral_value():          # "2,500" for a round cheque
        forms.add(f"{a:,.0f}")
    return sorted(forms, key=len, reverse=True)


def rows_mentioning(answer: str, amount: Decimal) -> list[str]:
    hits = []
    for line in answer.splitlines():
        if any(s in line for s in spellings(amount)):
            hits.append(line)
    return hits


def classify(lines: list[str], kind: str) -> bool:
    text = " ".join(lines).lower()
    return any(w in text for w in KIND_WORDS[kind])


def parse_truth(block: str):
    planted, traps = [], []
    for line in block.splitlines():
        m = re.match(r"- (omit|alter|duplicate) — (\S+): (\d{4}-\d{2}-\d{2}) ", line)
        if m:
            amt = re.search(r"'Assets:Bank:[^']+', '(-?[\d.]+)'", line)
            if amt:
                planted.append((m.group(1), m.group(2), m.group(3), Decimal(amt.group(1))))
            continue
        t = re.match(r"- outstanding: (\S+) (\d{4}-\d{2}-\d{2}) (-?[\d.]+)", line)
        if t:
            traps.append((t.group(1), t.group(2), Decimal(t.group(3))))
    return planted, traps


def main(paths: list[str]) -> int:
    grand = {"found": 0, "classified": 0, "planted": 0, "traps": 0, "respected": 0, "false_alarm": 0}
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        print(f"\n# {Path(path).name}")
        # split on the script's own world separator, not on the reviewer's horizontal rules
        for section in re.split(r"\n---\n\n(?=## (?:train|eval):\d+)", text)[1:]:
            head = section.strip().splitlines()[0]
            if "### Planted truth" not in section:
                print(f"{head}: no truth block")
                continue
            answer, truth = section.split("### Planted truth", 1)
            cut = re.search(r"\n#+ *Part B|\n\*\*Part B", answer)
            part_a = answer[:cut.start()] if cut else answer
            planted, traps = parse_truth(truth)
            found = classified = 0
            detail = []
            for kind, pid, day, amount in planted:
                lines = rows_mentioning(part_a, amount)
                ok_found = bool(lines)
                ok_kind = ok_found and classify(lines, kind)
                found += ok_found
                classified += ok_kind
                detail.append(f"    {kind:9s} {day} {amount:>10}  {'found' if ok_found else 'MISSED':6s} {'kind ok' if ok_kind else ('kind ?' if ok_found else '')}")
            respected = alarms = 0
            for tid, day, amount in traps:
                lines = rows_mentioning(part_a, amount)
                low = " ".join(lines).lower()
                if lines and any(w in low for w in TIMING_WORDS):
                    respected += 1
                elif lines and any(w in low for kind in KIND_WORDS for w in KIND_WORDS[kind]):
                    alarms += 1
                detail.append(f"    trap      {day} {amount:>10}  {'respected' if lines and any(w in low for w in TIMING_WORDS) else ('FALSE ALARM' if alarms and lines else 'not mentioned')}")
            print(f"{head}: found {found}/{len(planted)}, classified {classified}/{len(planted)}, traps respected {respected}/{len(traps)}, false alarms {alarms}")
            print("\n".join(detail))
            grand["found"] += found
            grand["classified"] += classified
            grand["planted"] += len(planted)
            grand["traps"] += len(traps)
            grand["respected"] += respected
            grand["false_alarm"] += alarms
    p = grand["planted"] or 1
    print(f"\nTOTAL: item recall {grand['found']}/{grand['planted']} ({100*grand['found']/p:.0f}%), "
          f"classified {grand['classified']}/{grand['planted']} ({100*grand['classified']/p:.0f}%), "
          f"traps respected {grand['respected']}/{grand['traps']}, false alarms {grand['false_alarm']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv[1:]))
