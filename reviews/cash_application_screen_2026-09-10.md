# Cash-application screen — result (2026-09-10, 01:36–01:44 local)

Research note, reviewed before publication; the numerical tables stand, the claims were narrowed
to what the records support. Companion notes: `reviews/wa1b_screen_2026-09-08.md` and
`reviews/qwen_authored_calibration_2026-09-08.md`.

A three-episode engineering screen, specified before the cash-application family was built and run
on the family as shipped. Instrument: `tests/budget_calibration.py --production` at `f9fbad1`,
episode contract 5 (profile `cash_application`, digest
`b11bc1acf02b7e08c9cea7d42e73b7970756bd9a979b3134c9049e76e6571b9f`), 25 turns, a 40,000-token
episode ceiling and the same per-turn cap, Alibaba Model Studio under Free Quota Only, requested
model ID `kimi-k3`. One episode per case, one attempt each, settings frozen before the run.
Cost: zero dollars, operator-reported under Free Quota Only; no billing record accompanies this
archive.

## The three episodes

| case | plants | reward | L (ledger) | A (register) | turns | out tokens | stop |
|---|---|---|---|---|---|---|---|
| `cash_application_002` — advice missing for R3, statement reference decides | 2 | **1.0** | 1.0 | 1.0 | 5 | 4,857 | submitted, complete |
| `cash_application_003` — short-pays either side of the tolerance, write-off omitted | 2 | **1.0** | 1.0 | 1.0 | 6 | 5,921 | submitted, complete |
| `cash_application_005` — credit exceeding the invoice's remaining balance, 30.00 unapplied | 2 | **0.333334** | 1.0 | 0.333334 | 10 | 6,634 | submitted, incomplete |

Total 123,413 input and 17,412 output tokens across the three episodes.

## One case's inputs moved after the measurement

Case 2's public inputs are no longer the ones this source projects. The source review named below
corrected the payment-reference identity rule, and Case 2 — the one variant with no remittance
advice for its third receipt — was left with no declared payment identifier; rather than loosen the
rule, the case was given the bank's own trace `TRC0428442`, printed ahead of the payer's invoice
list on the 28 April statement row. The archived workspace `workspaces/cash_application_002` beside
this note was measured against the bytes as they stood at `f9fbad1`, where that row's reference
reads `SI-3104 SI-3102`, and its delivered `cash_application.json` keys R3 as
`2026-04-28:SI-3104 SI-3102`. The same case folded from the current source keys it
`2026-04-28:TRC0428442 SI-3104 SI-3102`. **The archived Case 2 delivery is therefore not
reproducible against this source and would not re-score as delivered against it.** It stays valid
evidence about the run, at the revision named above, and about nothing later.

Cases 3 and 5 did not move: every input byte, task digest and scorer digest derives identically at
either revision, so the screen's one finding — Case 5's omitted `unapplied_amount` — and the rescore
and counterfactual below are untouched by this. `provenance.json` records every task and scorer
digest **at the measured revision**, names the later values separately rather than in their place,
and shows per file that each archived input reproduces its measured-revision digest.
`reviews/RELEASE_ATTESTATION.md` carries the same erratum, and
`beancount_ledger/graph/worlds/bowline_2026_04_c2.py` says it where the change lives.

## The one failure, diagnosed

Case 5 delivered a ledger scoring `L = 1.0`. Its application artifact correctly reports both R3
invoice applications, the credit-note distribution and all six closing invoice rows. R3's
`unapplied_amount` is `0.00`; the statement and advice require `30.00`. This single field error
loses receipt exactness and triggers both the receipt-conservation and closing-AR penalties,
yielding `A = total = 0.333334`.

Rescored through `application/1` from the archived workspace:

| channel / penalty | value | detail |
|---|---|---|
| `receipts_exact` | 0.666667 | R1 and R2 `RECEIPT_EXACT`; R3 `RECEIPT_WRONG_UNAPPLIED` |
| `register_exact` | 1.000000 | all six invoice rows exact, customer and `period_basis` included |
| `credit_exact` | 1.000000 | CN-0412: 300.00 to SI-3100, excess 240.00 to SI-3102, exact |
| `receipt_identity` | −0.20 | `2026-04-28:GR PAYRUN 0428: applied + unapplied 3750.00, statement credit 3780.00` |
| `ar_tie_break` | −0.30 | `remaining 2970.00 - unapplied 0.00 != closing receivables 2940.00` |

The large loss is **one receipt's exactness loss plus two correlated penalties** — the same omitted
30.00 breaks receipt conservation and the AR tie-break — not three independent mistakes, and not an
empirically calibrated measure of accounting severity. The prices were fixed before this error was
observed and were not changed after observing it.

**Single-field counterfactual.** Taking the archived Case 5 register and changing only R3's
`unapplied_amount` from `0.00` to `30.00` — one line, ledger untouched, nothing else edited — and
rescoring through the shipped `beancount_ledger.candidate.application.score_application` against the
truth `graph.derive.derive_contract` mints for the task itself: **`A = 1.000000`**, all three
channels 1.000000, no penalties, `AR_TIE_OK`. The shipped formula predicts `A = total = 1` and the
measured result is that value. The same run rescores the artifact as delivered and reproduces the
archived receipt's stored-byte, logical-text, canonical and result digests together with its
`0.333334`. Both rescores are archived, machine-readable, as
`cash_application_screen_2026-09-10/cash_application_005_rescore.json`. This is a same-scorer
consistency check on the register alone; no composite total is claimed for the counterfactual, and
it is not an independent accounting validation.

The observed defect is an omitted unapplied-cash balance in the application deliverable. The ledger
postings are correct and do not encode that balance's per-receipt attribution. The archived output
establishes the defect, but does not establish whether it arose from arithmetic, transcription or
misunderstanding, or whether another attempt would repeat it.

## Decision under the pre-declared rule

The rule, fixed before the run: retain the family for expansion only if the three valid episodes
include at least one complete success **and** at least one inspectable failure in application or
write-off logic on another case; ordinary receipt-repair mistakes do not qualify. Three successes
mean retain an assurance pack and defer difficulty-driven expansion; no successes mean defer and
diagnose; provider loss or exclusively budget/protocol failures make the screen inconclusive.

Two complete successes (Cases 2 and 3) and one inspectable application-logic failure on a third case
(Case 5, unapplied cash), with no provider, budget or protocol failure in any episode.
**Retain the family for a bounded expansion.**

## What this does and does not establish

The screen demonstrates successful two-artifact delivery on two variants and an application-artifact
error alongside a fully scoring ledger on a third. It meets the predeclared engineering rule for a
bounded expansion. It does not establish recurring difficulty, failure on invoice allocation,
generalization beyond the Bowline company-month, or training utility. A subsequent source review
identified an unsupported payment-reference identity rule in the bank identifiability checker; that
rule required correction before release certification, and it has since been corrected — in
`8fa99b3`, `21dc563`, `a4264f5`, `794ce66` and `551e56b`. Decisive identity is now what the evidence
declares to be a payment identifier, not what a reference string looks like; an invoice list stays
document evidence, because two partial payments can quote the same list.

Three episodes, one subject, one attempt each, on three of five variants of one company-month. Two of
the three were solved in five and six turns for under 6,000 output tokens, so nothing here suggests
the family is hard for a capable model. Nothing here speaks to other subjects, or to the two
truth-side paths that still have no golden (policy rung 3 and a credit-note residue).

## Limitations

One company-month, three of its five variants, one subject, one attempt per case, one deployment
route and one cap; no within-cell replication; no generated-world population and no training-utility
conclusion. The records attest a requested model ID, not an immutable served checkpoint. The rescore
is a same-scorer consistency check, not independent accounting validation.

## Records

`reviews/cash_application_screen_2026-09-10/` holds the archive:

- `cash_screen_kimi.json` — the calibration settings and outcomes, preserved untouched, with each
  row's contract digest, per-turn cap, ceiling, route, tokens, stop and candidate digests;
- `cash_screen_kimi.log` — the run log;
- `workspaces/cash_application_{002,003,005}/` — ten immutable public input files per workspace, the
  canonical delivered `ledger.beancount` and `cash_application.json`, and `delivery.json`;
- `cash_application_005_rescore.json` — the rescore of the delivered Case 5 register and the
  single-field counterfactual;
- `provenance.json` — source revision, resolved episode profile and version, task and scorer
  digests, runtime identity where recoverable, and both artifacts' submission and delivery
  identities. Its task and scorer digests are recomputed at the revision the screen was **measured**
  at, not at the revision the sidecar was written at; where the two differ — Case 2 alone — both are
  recorded, labelled, and the later ones are kept out of the provenance fields. It also names, by
  file, exactly what changed in the package between those two revisions.

The delivered artifacts match their receipts' artifact hashes; `provenance.json` records that check.
Every archived public input file reproduces the measured-revision view digest recorded for it, Case
2's superseded `bank_statement.csv` included; `provenance.json` records that check per file.
The calibration field `profile = standard` is a **generator**-profile label, not the episode profile;
the cash-application episode profile is established separately, from the contract digest each row
records and from the source that resolves it. The archive does not contain full trajectories, or
separate copies of the initial ledger and the raw submitted artifact bytes; `provenance.json` names
those gaps rather than inferring values for them, and no inferred value has been backfilled into the
calibration JSON.

## Resources

123,413 input and 17,412 output tokens across three episodes, 434 seconds of wall clock. The table
describes this screen's usage only. Zero charges are reported by the operator under Free Quota Only;
the remaining allowance must be read from the account. No future route availability or episode count
is implied.
