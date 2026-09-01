"""The adversarial corpus, re-expressed against the trust boundary.

Twenty-six of these payloads came out of review rounds against the old scorer,
each one a submission that scored higher than it deserved until a rule was
written to stop it. Their *score assertions* do not survive the redesign, but
the payloads are the valuable part: a corpus of syntax that hostile readers
actually produced, which is exactly what a new perimeter should face.

So they are reclassified rather than retired, into five classes:

    presentation-equivalent   normalises to the same candidate as the correct
                              solution. Not caught -- not expressible.
    protocol rejection        no supported candidate could be obtained.
    resource rejection        refused by a bound, cheaply.
    domain violation          read correctly; the bookkeeping is malformed.
    semantic                  a genuinely different candidate, which the
                              scoring layer must then judge.

The distribution is the evidence. Six presentation-equivalent cases are six
hand-written rules the old design needed and this one does not have; the two
resource cases are still caught, by hand-chosen numeric bounds — a rule that
changed from a penalty into a refusal, not one that disappeared. Thirteen semantic cases are the ones that were always about
bookkeeping. If far more had survived as semantic, the boundary would not be
cutting where we think it does; if far fewer, it would be discarding meaning.

    python tests/test_perimeter.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.candidate.entities import build_resolver  # noqa: E402
from beancount_ledger.candidate.normalise import (  # noqa: E402
    Accepted,
    ProtocolFailure,
    parse_once,
)

SOLUTIONS = Path(__file__).resolve().parent / "solutions"
WORLD = ROOT / "beancount_ledger" / "world"

# name -> (class, why)
#
# "presentation" means the payload says the same thing as the correct solution
# and is therefore the same object. Every one of these needed its own detector
# and its own penalty in the old design.
CORPUS = {
    "bad_comment_injection": ("presentation",
        "a block headed as the audited ledger telling the reader to ignore the "
        "entries below. Comments are not in the candidate type, so the "
        "injection has nowhere to live rather than being detected"),
    "bad_computed_amounts": ("presentation",
        "amounts written as arithmetic; they evaluate to the same Decimal, so "
        "this is equivalent syntax rather than an attack"),
    "bad_overprecise_amounts": ("presentation",
        "amounts padded to fifteen decimal places; 85.000000000000 is 85.00"),
    "bad_pending_flags": ("presentation",
        "every entry flagged unverified. The flag is renderer-owned, and "
        "scoring the agent's spelling of it was an undisclosed rule"),
    "bad_tagged_entries": ("presentation",
        "every entry stamped #unreviewed ^fabricated-source; no tag carries "
        "meaning in v1, so none reaches the candidate"),
    "bad_mocking_case": ("presentation",
        "the counterparty named in mocking case. It resolves to the right "
        "entity, so it names the right company and is the same fact -- exact "
        "string equality was presentation wearing the clothes of semantics"),

    "bad_unparseable": ("protocol", "does not parse"),
    "bad_duplicate_opens": ("domain",
        "every open directive duplicated. Syntactically supported and "
        "semantically malformed, so it is a broken ledger rather than an "
        "unreadable one -- it was protocol until that distinction was drawn"),
    "bad_removed_open": ("domain",
        "an open directive deleted, leaving postings to an account the chart "
        "no longer declares"),
    "bad_elided_amounts": ("protocol",
        "explicit amounts stripped so elision refills them; rejected in v1 "
        "because resolving elision needs a booking model we do not have"),
    "bad_rewritten_options": ("protocol",
        "ledger header and operating currency rewritten"),

    "bad_padded_file": ("resource", "padded to ten thousand lines"),
    "bad_wide_line": ("resource", "one line of fifty thousand characters"),

    "bad_deleted_check": ("semantic", "destroyed a legitimate timing difference"),
    "bad_altered_unrelated": ("semantic", "quietly edited an unrelated entry"),
    "bad_copied_statement": ("semantic", "double-posted the statement lines"),
    "bad_merged_events": ("semantic", "two events posted as one entry"),
    "bad_no_narration": ("semantic",
        "counterparty unidentifiable from the register -- a real defect, since "
        "nobody can tie the entry to a document"),
    "bad_negated_keywords": ("semantic",
        "the accepted name buried in a sentence denying it. Containment is not "
        "identity, so it resolves to nobody"),
    "bad_payee_rewrite": ("semantic", "rewrote the counterparty of every entry"),
    "bad_closed_accounts": ("semantic", "closed every account after reconciling"),
    "bad_opening_balance": ("semantic", "moved the opening balances"),
    "bad_opening_forgery_full": ("semantic", "forged all three scored accounts"),
    "bad_wash_transaction": ("semantic", "a fabricated net-zero entry"),
    "bad_plug_account": ("semantic", "invented a suspense account"),
    "baseline_untouched": ("semantic", "did nothing at all"),
}


def classify(text, resolver, golden):
    """Five outcomes, and the split between the middle three is the point.

    A resource rejection is cheap and bounded. A protocol rejection means no
    supported candidate could be obtained. A domain violation means the
    submission was read correctly and the bookkeeping in it is wrong -- which
    is a fact about the ledger, not about whether we speak the same language.

    Keeping domain out of protocol matters for more than tidiness: the
    protocol-rejection rate is the health metric for whether our accepted
    subset is too narrow, and ordinary bad bookkeeping landing in it would make
    that metric measure the agents instead of the contract.
    """
    result = parse_once(text, entity_resolver=resolver)
    if isinstance(result, ProtocolFailure):
        kind = "resource" if result.reason.startswith("envelope.") else "protocol"
        return kind, result.reason
    if not isinstance(result, Accepted):
        return "evaluator", str(result)[:60]
    if not result.domain_valid:
        return "domain", str(result.domain_findings[0])[:60]
    if result.candidate == golden:
        return "presentation", "identical to the correct solution"
    return "semantic", f"{len(result.candidate.events)} events"


def run() -> int:
    resolver = build_resolver(WORLD).resolve
    parsed = parse_once((SOLUTIONS / "golden.beancount").read_text(encoding="utf-8"),
                        entity_resolver=resolver)
    if not isinstance(parsed, Accepted):
        print(f"FAIL  the correct solution does not parse: {parsed}")
        return 1
    golden = parsed.candidate

    print(f"corpus of {len(CORPUS)} payloads against the trust boundary\n")
    failures = []
    counts = {}
    for name, (expected, why) in sorted(CORPUS.items(), key=lambda kv: (kv[1][0], kv[0])):
        path = SOLUTIONS / f"{name}.beancount"
        if not path.exists():
            failures.append((name, "missing", "solution file not built"))
            continue
        actual, detail = classify(path.read_text(encoding="utf-8"), resolver, golden)
        counts[actual] = counts.get(actual, 0) + 1
        ok = actual == expected
        print(f"{'PASS' if ok else 'FAIL'}  {name:28s} {actual:12s} {detail}")
        if not ok:
            failures.append((name, f"expected {expected}, got {actual}", why))

    print("\n  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    # The correct solution's derived balances must equal what the task file
    # currently stores by hand. Once they agree, the stored numbers are
    # redundant and can go -- which is the point of a projection.
    print("\n  derived balances on the correct solution:")
    for account in ("Assets:Bank:Checking", "Assets:AR", "Expenses:BankFees"):
        print(f"    {account:24s} {golden.balances.get(account)}")

    if failures:
        print(f"\n{len(failures)} FAILURE(S)")
        for name, problem, why in failures:
            print(f"  {name}: {problem}\n      {why}")
        return 1
    print("\nevery payload lands in its expected class")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
