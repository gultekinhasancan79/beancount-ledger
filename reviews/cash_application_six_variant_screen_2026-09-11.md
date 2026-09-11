# Six-variant cash-application screen — INCOMPLETE DESCRIPTIVE SCREEN (2026-09-11, 04:06–04:25 local)

Research note, reviewed before publication; the numerical tables stand, and the claims were narrowed
to what the records support. Companion notes: `reviews/cash_application_screen_2026-09-10.md`
(the Bowline screen) and `reviews/cash_application_adjudication_2026-09-10.md` (the cold
adjudication of the Bowline five).

**Read this as an incomplete descriptive screen and as nothing else.** Six variants, one subject,
one episode each, one attempt, three company-months; five cells scored and one lost to a provider
failure. It describes what one model did on six authored instances. It establishes **no population
failure rate, no accounting accreditation and no training benefit**, and it was not a release
prerequisite.

The measurement was fixed before the three new company-months were built. Instrument:
`tests/budget_calibration.py --production` at the frozen revision `328d702`, episode contract 5
(profile `cash_application`, digest `b11bc1ac…`), 25 turns, a 40,000-token episode ceiling and the
same per-turn cap, Alibaba Model Studio under Free Quota Only, requested model ID `kimi-k3`, one
episode per variant, a fresh context each, settings frozen before the run. Kept separate from the
earlier Bowline screen. Cost: zero dollars, operator-reported under Free Quota Only; no billing
record accompanies this archive.

| variant | month | reward | L | A | turns | out tokens | stop |
|---|---|---|---|---|---|---|---|
| `cash_application_006` | Thornbury, remainder falls to the oldest invoice | **1.0** | 1.0 | 1.0 | 8 | 8,232 | submitted |
| `cash_application_007` | Thornbury, receipt exhausted at the named invoices | **0.64** | 1.0 | 0.64 | 11 | 9,407 | submitted |
| `cash_application_008` | Pennywhistle, credit residue with nowhere to go | **1.0** | 1.0 | 1.0 | 9 | 6,464 | submitted |
| `cash_application_009` | Pennywhistle, no residue | **1.0** | 1.0 | 1.0 | 7 | 5,036 | submitted |
| `cash_application_010` | Tallowmere, advice leaves cash unapplied | **1.0** | 1.0 | 1.0 | 8 | 7,784 | submitted |
| `cash_application_011` | Tallowmere, advice accounts for all of it | — | — | — | — | — | provider 403, free quota exhausted |

Five of six scored; **one cell is missing and stays missing**. It is neither a zero nor an inferred
success, and every aggregate or comparison that uses this screen must preserve it as missing.

## The one partial, diagnosed

Thornbury B delivered a perfect ledger (`L = 1.0`). Rescored through `application/1` from the
archived workspace:

| channel / penalty | value | detail |
|---|---|---|
| `receipts_exact` | 1.000000 | all three receipts `RECEIPT_EXACT`, the two un-adviced ones included |
| `credit_exact` | 1.000000 | CN-0609 exact |
| `register_exact` | 0.800000 | eight of ten rows exact; `SI-4415` and `SI-4419` `INVOICE_MISSING` |
| `ar_tie_break` | −0.30 | `remaining 14058.00 - unapplied 0.00 != closing receivables 31018.00` |

**The error is one thing: the two invoices raised during the month are absent from the closing
register.** SI-4415 (6,360.00, raised 11 June) and SI-4419 (10,600.00, raised 16 June) were never
paid and should close at their full balances; 6,360.00 + 10,600.00 = 16,960.00, and
14,058.00 + 16,960.00 = 31,018.00, the true closing receivables. The submission listed only the
invoices that were open on the first day of the month. The same omission produces the register loss
and the tie-break penalty.

### The artifact diagnosis, and its limit

The delivered register's invoice set is exactly the opening register's eight invoices. It is **not**
a list of the invoices the submission put money on: `SI-4386` appears in it with no cash
application, no credit and its full 4,240.00 still outstanding. What the artifact
supports is therefore an incomplete invoice **universe** — the two in-period sales are absent — and
not a proven account of the solver's reasoning. An earlier draft of this note said the solver
"reports what it applied and forgets what remains"; that reading is **retracted** as too strong for
this evidence.

**This is not the failure the pair was built to provoke, and it must not be reported as one.**
Thornbury's two variants differ in whether the un-adviced 25 June receipt leaves a remainder to fall
through to the oldest-invoice rung. The submission applied all three receipts exactly in both
variants, fallback included. It failed on a different thing entirely: what belongs in a closing
open-item list. Each pair differs in one authored fact, which defines the accounting distinction it
is intended to test; that does not guarantee that a solver's error concerns that distinction, and
attribution requires inspection of the delivered artifacts — which is what this section is.

### The executed counterfactual

The delivery was turned into a regression fixture rather than left as an argument. The delivered
artifacts are copied verbatim to `tests/observed/cash_application_007/`, checked against the run's
own delivery receipt, and scored through the **shipped** `candidate/1`, `application/1` and
`composite/1`; the counterfactual adds **only** the two omitted closing rows, at their period basis
with all four outcome columns zero, and is scored the same way.

| | delivered | counterfactual (+ SI-4415 6,360.00, + SI-4419 10,600.00) |
|---|---|---|
| `L` (the delivered ledger, unchanged in both) | 1.000000, complete | 1.000000, complete |
| `receipts_exact` / `register_exact` / `credit_exact` | 1.000000 / 0.800000 / 1.000000 | 1.000000 / 1.000000 / 1.000000 |
| penalties | `ar_tie_break` | none |
| invoice states | eight `INVOICE_EXACT`, two `INVOICE_MISSING` | ten `INVOICE_EXACT` |
| `A` | 0.640000 | 1.000000 |
| composite | 0.640000, **not** complete | 1.000000, complete |

Both decompositions are archived as machine-readable JSON beside this note. What the counterfactual
establishes is that the two omitted rows account for the **whole** of the loss — not why the solver
omitted them. The re-score reproduces the delivery receipt's `canonical_digest` and
`application_result_digest` and its `0.64`; it does not reproduce the ledger's `score_result_digest`
or the `composite_result_digest`, because those bind the rollout's `submitted_text_digest` and the
archive holds the canonical stored artifact rather than the original submitted text. The
regression tests are `tests/test_cash_application_scoring.py`.

## Decision under the pre-declared rule

The rule, fixed before the run: continue toward a generator only if every company-month has at least
one complete success **and** at least one pair shows a correct counterpart plus an inspectable
application failure **exercising that pair's intended distinction**; six complete successes mean
retain the expanded pack and defer generation; a company-month with no complete success must be
diagnosed before more instances are generated; a provider or evaluator failure makes the planned
screen incomplete, and budget or protocol failures and ordinary ledger-repair mistakes do not
satisfy the application-failure condition. No adaptive repeats, no subject switching, stop if free
quota disappears.

- Every company-month has at least one complete success: Thornbury 006, Pennywhistle 008 and 009,
  Tallowmere 010. **Satisfied.**
- A pair with a correct counterpart and an application failure exercising its own distinction:
  **not satisfied.** The only failure is Thornbury B's, and it does not exercise Thornbury's
  distinction.
- One cell was lost to a provider 403. **The screen is incomplete.**

**Do not proceed to the generator. Retain the expanded assurance pack.** The screen was stopped
where the quota stopped it; the missing cell was not refilled, no subject was substituted, and no
episode was repeated. `kimi-k3`'s free allowance on this route is spent and does not reset, so the
missing cell cannot be filled with this subject at zero cost. Filling it with another model would
make it a different measurement and is forbidden by the rule that was fixed in advance. A later,
separately declared observation on another subject may measure `cash_application_010`/`011` as that
subject's paired observation; it may not be inserted into this table, pooled with these rewards, or
described as completing this screen.

The pair-distinction condition above was a useful test of one hypothesis and too narrow as a veto on
other evidence of application failure. It has been **replaced prospectively** for the next full
screen, and this screen's historical decision is unchanged. The replacement: freeze the cases,
subject, settings and failure categories before collection; continue toward generation only after a
complete screen contains at least one complete success per company-month and at least one
inspectable application-only failure on another case — correct ledger, incorrect application
deliverable, with the error established from public evidence and a targeted correction verified
through the scorer. Qualifying errors include allocation, write-off, cash or credit residue, and
closing-register completeness. Pair-specific claims require errors that actually concern the pair's
distinction. All successes retain an assurance pack; a company-month without a success requires
diagnosis; provider or evaluator failures leave the screen incomplete. No adaptive repeats or
substitutions. **This run did not authorize generation, and the replacement does not apply to it
retrospectively.**

## What was learned anyway

Thornbury B produced a complete ledger repair and an incomplete closing register. Its register
contains exactly the eight opening invoices and omits the two invoices raised during June, both
unpaid at closing. Those omissions explain the entire register-exactness loss and closing-AR
penalty. The scorer already covered missing invoice rows; this run supplies an observed model
example. The artifact does not establish whether the omission arose from misunderstanding,
transcription or another process.

The earlier Bowline failure omitted 30.00 of unapplied cash while reporting its credit-note
distribution and all closing invoice rows correctly. Tallowmere A correctly reported 540.00 of
unapplied cash in this screen. Pennywhistle A correctly reported 210.00 of unapplied credit-note
value, a condition the earlier screen did not establish as a failure. These are observations on
different instances, not evidence of improvement or a shared cognitive mechanism.

Two claims that stood in earlier drafts of this note are **retracted**. "Nobody designed this
failure mode" is false: `application/1` already names `INVOICE_MISSING`, and
`tests/test_cash_application_scoring.py` already removes `SI-3105`, an invoice raised during
Bowline's month, from a closing register. What is new is observing a model make the error. And
"this subject solved the residue cases it previously failed" is false as written: the earlier
failure concerned **cash**, while that episode's credit-note distribution was correct.

Authoring a case after observing a failure is legitimate for development and regression coverage.
Any such case must be labelled as informed by that observation and kept out of a set later claimed
to be untouched.

## Limitations

Six variants, one subject, one episode each, one attempt, three company-months, five scored cells,
one deployment route, one cap, no within-cell replication. Nothing here establishes difficulty, a
failure rate, generalisation or training utility, and nothing here is an accounting accreditation.
Four of the five scored episodes were solved in seven to nine turns for under 8,300 output tokens,
so nothing suggests the family is hard for a capable model. The record attests a requested model ID,
not an immutable served checkpoint. The three company-months carry a dated AI
accounting-plausibility review, not a practising accountant's sign-off; practitioner validation
remains outstanding.

## Records

`reviews/cash_application_six_variant_screen_2026-09-11/` holds the archive:

- `six_screen_kimi.json` — the calibration settings and outcomes, **preserved untouched**;
- `six_screen_kimi.log` — the run log;
- `workspaces/cash_application_{006,007,008,009,010}/` — eleven immutable public input files per
  workspace, the canonical delivered `ledger.beancount` and `cash_application.json`, and
  `delivery.json`;
- `cash_application_007_{delivered,counterfactual}.decomposition.json` — the two executed scorer
  decompositions above;
- `verify_receipts.py` / `verify_receipts.json` — the receipt check re-run at publication.

The archive contains the calibration JSON, run log and five final delivered workspaces, including
ledger and application artifacts and their delivery receipts. The delivered artifacts match the
receipts' stored-byte and logical-text digests. The archive does not contain full trajectories, the
original submitted texts, untouched initial ledgers or a complete runtime/task/scorer provenance
record. Any subsequently reconstructed inputs or provenance must be identified as reconstructions.

The 011 record contains a truncated provider 403 error and no scored delivery. No 011 workspace is
archived here. The record does not establish that no workspace was created, how far the episode
progressed, or its token consumption before failure.

Two measured facts say why that last sentence is the honest one. The log's 011 line reads
`0/1 [03:03<?, ?it/s, reward=?]` — roughly three minutes inside evaluation before the failure. And
`tests/budget_calibration.py`'s broad `except Exception` replaces the entire result row with
`{"selector": …, "crashed": …}`, discarding the `workspace` field and every token-usage field the
runner assembles. The archived 011 row accordingly carries only `selector`, `crashed` and
`attempts`, and its 403 message is cut at 200 characters.

Two claims that stood in earlier drafts are **retracted**: that the calibration JSON carries "every
provenance field", which is demonstrably false, and that "the sixth workspace does not exist",
which this record does not support.

Note which register the archive holds: `_publish` writes the **canonical** register over the
workspace file, so the archived bytes are the canonical form and do **not** reproduce the
`submitted_*` digests beside them, which are of the agent's own text. `verify_receipts.py` asserts
both halves of that — ten artifacts matching their receipts, and five canonical registers
reproducing no submitted digest.

## Resources

294,508 input and 36,923 output tokens across the five scored episodes. The table describes this
screen's usage only. Zero charges are reported by the operator under Free Quota Only; the remaining
allowance must be read from the account. No future route availability or episode count is implied.
