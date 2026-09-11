# Cold adjudication of the cash-application pack — declared before the run

Written and dated before any adjudicator was called. 2026-09-10.

## The question this answers, and the one it does not

**Answers:** do the public documents, on their own, determine one application of the
period's receipts and credit note — or did the authors know something the pack does
not say? This is admissibility of the evidence.

**Does not answer:** whether these documents and this policy reflect real bookkeeping
practice. That is domain validity and only a practising accountant can supply it. A
model's agreement is not a substitute and will not be reported as one.

## Method

Five cases: `cash_application_001` … `005`. For each, an adjudicator is given exactly
the eleven public files the agent is given — the bank statement, the ledger as found,
the open-item register, the remittance advice, the credit notes, the masters, the
chart, the policy, the prior archive and the manifest — and nothing else. No
specification, no scoring code, no truth register, no mention that a register is
scored or what shape it takes, no statement that a unique answer exists.

Two adjudicators, both of a different lineage from each other and **neither the
subject**: `qwen3.7-max` and `deepseek-v4-flash` on Alibaba. The screen's subject
`kimi-k3` is excluded: a model cannot certify the pack it was measured on.
Temperature 0, one call per case per adjudicator, 16,000-token cap, the answer read
from `reasoning_content` when the visible content is empty.

The question is neutral: for each customer receipt the bank shows, which invoices does
it settle and for how much; what becomes of any part not applied; how is the credit
note applied; what is each invoice's balance at month end. The answer is requested as
JSON so it can be compared mechanically rather than read charitably.

## The rule, fixed now

An adjudicator **passes** a case when its answer equals the truth register on all four:
per-receipt applied sets (invoice and amount), write-offs, unapplied amounts, and the
credit-note application; and its closing remaining balances equal the truth's.
Differences in wording, ordering or extra commentary do not count against it. A missing
field counts as a failure, not as agreement.

A case is **admissible** when both adjudicators pass it.

What each outcome means, decided now:

- **Both pass** — the pack determines the application without the authors' private
  knowledge. Admissible.
- **One passes, one differs** — the pack is not decisive for a competent reader. The
  case is recorded as contested and its disagreement is reported in full; it is not
  quietly kept because the majority agreed.
- **Both differ, and they differ the same way** — the authors are probably wrong, not
  the readers. Treat the case as defective and re-examine the evidence, not the readers.
- **Both differ, differently** — the pack is ambiguous. Defective.

No case is adjusted to make an adjudicator agree after the fact, and no adjudicator is
replaced. Whatever comes back is published beside the screen note with the full answers.

## What a pass is worth

It says a capable reader who never saw the design can derive the same application from
the documents. It does not say the documents look like real remittances, that the
policy is one a firm would publish, that the tolerance is sensible, or that the family
is hard. Those remain open, and the first three are for the accountant.
