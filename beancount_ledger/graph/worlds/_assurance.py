"""The assurance pack's shared instruction.

The buyer-facing question this pack answers is not "can the agent find the
error" but "does the agent damage books that already reconcile". Answering it
needs a pair of months that are indistinguishable from the instruction alone:
one whose opening ledger is already correct, one with a single planted
discrepancy, and the SAME words in front of both. If the prompt for the clean
month read differently - softer, hedged, "check whether anything is wrong" -
the pair would measure reading comprehension of the prompt rather than of the
books, and a model that never looked at the ledger could split them.

So the instruction lives here, once, and every task in the pack imports this
one string. It is deliberately free of the company, the month, the bank and
the count of differences: four tasks across two company-months share it
byte-for-byte, and `tests/test_clean_month.py` asserts that they do.

It is a neutral audit instruction in the same register as the other
hand-authored prompts - second person, naming the bundle and the policy, and
ending in the write-back the contract requires - and it says nothing about
whether there is anything to correct. It does not hedge either: an
instruction that hinted "there may be nothing to fix" would be a different
tell, pointing the other way.
"""

from __future__ import annotations

#: The one instruction, shared by all four assurance-pack tasks.
ASSURANCE_PROMPT = (
    "An independent review of this period's books has been asked for before the month is signed off. "
    "The bank statement for the period is in the bundle with the prior month's archive, the chart of "
    "accounts, the customer and vendor masters and the bookkeeping policy. Work through the ledger "
    "against the statement and the policy, decide what the books should say for the period, and write "
    "the ledger the period should close on back to ledger.beancount."
)
