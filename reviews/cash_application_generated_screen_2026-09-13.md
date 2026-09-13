# Cash-application screen 1, on the generated development population — INCOMPLETE DEVELOPMENT SCREEN

**13 September 2026. Subject `qwen3.7-max-2026-05-20`, development split only.**

**Disposition: nine scored, one attempted but unscored, two unattempted, against twelve planned
cells.** The screen was stopped by a provider quota refusal and is closed with its original
denominator. The missing outcomes are missing; none was refilled, no subject was substituted, and no
episode was repeated.

**What this screen does not establish.** It does not establish a population success rate, a general
difficulty, or training utility. It is not a benchmark result and the completed subset is not
reported as one. The evaluation split was never opened and remains closed. Missing outcomes are
distinguished from model failures throughout: a cell the provider refused is not a cell the model
failed.

**What it does support.** Under the recorded conditions, seven complete successes and two
application-only partials. All nine recorded ledger scores are 1.0. Every mechanism stratum contains
at least one complete success. Those observations survive the provider failure.

---

## 1. The nine scored cells

Selection was frozen and written before any model call, with its own digest
`321c9715…`: sampling seed `cash-application-screen-1:2026-09-13`, two parent groups drawn
uniformly from the 32 eligible per stratum, both variants, execution order also drawn. Settings:
temperature 0, 25 turns, a 40,000-token episode output ceiling, fresh context per episode,
`measure_budget.py` with retries 0, Free Quota Only enabled on the requested ID.

| # | cell | public task id | reward | L | A | turns | tokens |
|---|---|---|---|---|---|---|---|
| 1 | `ar-tenterhook:24:a` | `cash_application_g522591213117` | **0.625** | 1.0 | 0.625 | 9 | 163,908 |
| 2 | `cr-pikestaff:6:b` | `cash_application_g530405700405` | 1.0 | 1.0 | 1.0 | 6 | 97,435 |
| 3 | `cr-pikestaff:6:a` | `cash_application_g888972188071` | 1.0 | 1.0 | 1.0 | 7 | 99,811 |
| 4 | `ar-tenterhook:22:b` | `cash_application_g338560593754` | 1.0 | 1.0 | 1.0 | 7 | 133,777 |
| 5 | `fc-quarrymill:4:b` | `cash_application_g862432258420` | 1.0 | 1.0 | 1.0 | 7 | 125,444 |
| 6 | `ar-tenterhook:22:a` | `cash_application_g937470682826` | **0.625** | 1.0 | 0.625 | 7 | 120,711 |
| 7 | `fc-quarrymill:4:a` | `cash_application_g072688239970` | 1.0 | 1.0 | 1.0 | 6 | 97,137 |
| 8 | `cr-pikestaff:12:b` | `cash_application_g417734064104` | 1.0 | 1.0 | 1.0 | 8 | 132,284 |
| 9 | `ar-tenterhook:24:b` | `cash_application_g771922601733` | 1.0 | 1.0 | 1.0 | 7 | 113,585 |
| 10 | `cr-pikestaff:12:a` | — | — | — | — | — | **attempted, unscored: HTTP 403, free quota exhausted** |
| 11 | `fc-quarrymill:1:b` | — | — | — | — | — | **unattempted** |
| 12 | `fc-quarrymill:1:a` | — | — | — | — | — | **unattempted** |

Strata: `ar-tenterhook` is advice residue, `cr-pikestaff` credit residue, `fc-quarrymill` fallback
continuation.

### Cell 10 is lost, not unrun

The 403 propagated out of `one_rollout` and the process exited on the traceback, so the cell that
met the provider failure has no row of its own and cells 11 and 12 were never reached. The runner
defect is fixed; the cell is not recoverable. A **retrospective reconstruction** stands beside the
nine rows in `cash_screen_1_retrospective_census_2026-09-13.json`, built from the frozen selection
and the runner's console log, which is published with the evidence. It carries the fields the fixed
runner's terminal row would carry:

| field | value | source |
|---|---|---|
| status | `ATTEMPTED_UNSCORED`, quarantined, reward null | derived |
| HTTP status | 403 | the log |
| provider error code / type | `insufficient_quota` / `insufficient_quota` | the log |
| provider request id | `1b73fcc5-983a-9286-9d11-74f67b95f5a7` | the log |
| elapsed before the refusal | 176 s | the log |
| task id, start/end times, workspace, usage, deliverables | `UNKNOWN` | never captured |

`UNKNOWN` is not zero. The cell ran for nearly three minutes before the refusal, so it **spent**, and
that spend is unrecorded. Cells 11 and 12 are a different object: not attempted, not quarantined, no
spend. **The original nine rows are untouched** — the census reads them and echoes each row's reward
and binding digests so it can be checked against them.

---

## 2. The two partials, and the counterfactual made reproducible

Both partials are `ar-tenterhook` variant `a`. Neither failure is in the residue the stratum exists
to test: in `24:a` the truth carries 30.00 of unapplied cash and the submission reported 30.00. What
is missing in each is **three invoices raised inside the period and unpaid at closing, absent from
the closing register**:

| cell | omitted invoices | receivables omitted |
|---|---|---|
| `ar-tenterhook:24:a` | `SI-8446` 3,127.00, `SI-8451` 3,604.00, `SI-8453` 3,074.00 | 9,805.00 |
| `ar-tenterhook:22:a` | `SI-7346` 3,180.00, `SI-7351` 1,166.00, `SI-7353` 1,802.00 | 6,148.00 |

### The decomposition is POST-RUN ANALYSIS

The live diagnostic capture failed on **all nine rows** with
`AttributeError: 'CompositeOutcome' object has no attribute 'components'`, so no breakdown was
archived. Every decomposition below was computed after the fact, from recovered bytes, and is
labelled as such. What is live is each row's reward, `piv/ledger_score`, `piv/application_score` and
each workspace's delivery receipt; those are read, never rewritten.

`application/1`, both partials, identically:

| channel / penalty | value | weight | contribution |
|---|---|---|---|
| `receipts_exact` | 1.000000 — all four receipts exact | 0.50 | +0.500000 |
| `register_exact` | 0.750000 — 9 of 12 rows, three `INVOICE_MISSING` | 0.30 | +0.225000 |
| `credit_exact` | 1.000000 | 0.20 | +0.200000 |
| `ar_tie_break` | remaining − unapplied ≠ closing receivables | — | −0.300000 |
| | | | **A = 0.625000** |

Both write-off ties are `WRITEOFF_TIE_OK`. The register channel loses 0.075 and the AR penalty 0.30;
under this diagnosis these are **two scoring consequences of the same omissions**, not independent
accounting mistakes.

### How the reader can certify it without taking anything on trust

The generated population is keyed, and this analysis does not read the evaluator secret, so the
truth register is **reconstructed from public evidence** (`tests/observed_truth.py`): the opening
register from `open_items.csv`, the invoices raised in the period from the delivered ledger's own
`Sale SI-…` entries, and the fold of the receipts and credit notes onto those invoices. Not one
register row is copied from the submission being scored. The receipt and credit-note folds *are*
taken from the submission, which would make two channels 1.0 by construction — so the reconstruction
is pinned rather than believed:

> `application/1` stamps every outcome with `result_digest`, a domain-separated SHA-256 over the
> **whole decomposition** — the total, all three channel fractions, every penalty, and one state per
> receipt, invoice, credit note and tie. The live run wrote that digest into each workspace's
> delivery receipt. **The rescore reproduces it for all nine cells, along with each document's
> canonical digest.** A wrong reconstruction would change a state and so change the digest.

Each recovered file is also bound to the result row it came from: stored-bytes and logical-text
digests, application and ledger, nine cells, all agreeing.

### The counterfactual, executed

For each partial, the delivered bytes, the corrected bytes and the exact diff between them are
published. The corrected document adds **only** the truth's rows for the omitted invoices, at their
period basis with nothing applied, credited or written off, in invoice order; the diff is a single
purely additive hunk of 27 lines with nothing removed, and the rescore re-derives it rather than
trusting the file.

| | `24:a` | `22:a` |
|---|---|---|
| delivered A | 0.625000 | 0.625000 |
| corrected A | **1.000000** | **1.000000** |
| penalties | `ar_tie_break` → none | `ar_tie_break` → none |
| receipt states | unchanged, all `RECEIPT_EXACT` | unchanged |
| credit states | unchanged, `CREDIT_EXACT` | unchanged |
| other register rows | unchanged, all `INVOICE_EXACT` | unchanged |
| ties | `AR_TIE_CONTRADICTS` → `AR_TIE_OK`; write-off OK throughout | same |

So the omission accounts for the **whole** of the loss, and the reviewer can now check that claim
from the published bytes instead of a before/after total. No delivered file was overwritten; the
corrected documents are new files beside them.

**What is not replayed here.** `candidate/1` scores against the task's golden ledger, which for a
generated task is minted under the evaluator key. `L` is therefore **not** recomputed; the live
figure (1.000000 on every cell) is carried and labelled, and the composite is reported as the
shipped product rule `quantise(L × A, 6, half-even)` applied to a live `L` and a recomputed `A`,
reproducing each row's recorded reward. The ledger **bytes** are published and bound, so a full
replay is available to anyone holding the key. This limitation belongs to the archive, not to the
counterfactual: the claim under test is entirely an application-channel claim, and the ledger bytes
are identical in both arms.

---

## 3. Consumption

> The nine scored episodes recorded 1,084,092 provider-reported tokens. The next scheduled cell
> encountered a quota-exhaustion 403; its usage was not preserved in a result row. These records do
> not reconcile provider-reported usage to the console's quota debits.

Verified from the rows by the rescore script: 926,855 input + 157,237 output = 1,084,092 across 64
captured responses, a mean of **120,454.7** per scored episode and a range of **97,137 to 163,908**.
That is far above the 66,286 mean planned from an earlier subject's rows, which is why nine episodes
spent the allowance twelve were budgeted for. Cell 10's usage is `UNKNOWN`, not zero.

## 4. Service attribution

Every row records `provider: nvidia` while recording the endpoint
an `ap-southeast-1.maas.aliyuncs.com` compatible-mode endpoint. **The raw records are preserved
unedited; the correction is made here, in analysis.**

- The nine episodes were served by **Alibaba Cloud Model Studio**, at the `ap-southeast-1` endpoint
  recorded on every row.
- `provider` in `measure_budget.py` is a **driver and pacing label** — which client path was taken —
  and is not the identity of the serving service. Read it that way and never as provider identity.
- The **returned model names match the requested snapshot** `qwen3.7-max-2026-05-20` on all 64
  captured responses. **Every captured `system_fingerprint` is null**, so the records carry no
  serving-build identity beyond the returned name.

## 5. The failure-mode history, corrected

An earlier report of this screen called the two partials "a third observation of one failure",
counting two authored occurrences and two generated ones. **That count was wrong, and it is
retracted here.**

- The authored **Thornbury B** omitted in-period invoices from the closing register.
- **Bowline case 5 omitted unapplied CASH while reporting all closing invoice rows correctly.** That
  is a *different* failure, and this project's own earlier note already drew the distinction.

The history therefore comprises **one authored occurrence (Thornbury B, on Kimi) and two reported
generated occurrences (on Qwen)** — not two authored plus two generated, and not repeated
observations of one subject. The two generated instances **share one structural template**
(`ar-tenterhook`, two different parent groups, both variant `a`); they are two cases from one
template, which is weaker evidence than two independent templates would be.

This warrants a reusable diagnostic example and nothing more. It does not establish why the model
omitted the rows, a general variant-`a` effect, or a prevalence estimate.

## 6. Diagnosis and what changed in the scorer — nothing

The diagnosis uses the **existing `INVOICE_MISSING` state**, supplemented with the public fact that
the missing invoices were **raised during the period**: the solver's own delivered ledger posts each
of them as a `Sale SI-…` inside the period, and each is unpaid at closing. The accounting
consequence is that the closing register understates receivables by the omitted balances, which is
why the register channel and the AR tie both move.

**No new scoring rule was introduced. No weight, penalty or population membership was changed.** The
two delivered registers and their minimal corrected counterparts are retained as **observed
fixtures** now that their bytes are recovered and bound — `tests/observed/cash_screen_1_ar-tenterhook_24_a/`
and `tests/observed/cash_screen_1_ar-tenterhook_22_a/` — and the battery scores them on every run
(`tests/test_cash_application_scoring.py`), failing loudly if either the fixtures or the published
evidence drift.

## 7. Evidence

`reviews/cash_application_generated_screen_2026-09-13/` — see its `README.md` for the index:

- `workspaces/` — the nine rescued workspaces, thirteen files each, including the delivered
  `ledger.beancount`, `cash_application.json` and `delivery.json`;
- `counterfactual/` — for each partial: the delivered bytes, the corrected bytes and the exact diff;
- `rescore_cash_screen_1.py` / `.json` — the executable rescore and its record: bindings, both
  decompositions, the counterfactual, the consumption arithmetic and the attribution audit;
- `cash_screen_1_selection.py` — the selection script, published beside the record it produced;
- `cash_screen_1_runner.log` — the runner's console log, the cell-10 reconstruction's evidence.

Beside it: `budget_qwen3.7-max-2026-05-20_2026-09-13_cash_screen_1.json` (the nine rows, unmodified)
and its per-selector directory; `cash_screen_1_selection_2026-09-13.json` (the frozen selection,
byte-identical to the pre-run original); `cash_screen_1_retrospective_census_2026-09-13.json` (the
twelve-cell disposition, with cell 10's reconstruction) and its builder;
`cash_application_development_population_2026-09-13_replacement.md` (the population these cells were
drawn from).

## 8. Limits

1. **Nine of twelve.** The counts are reported against twelve planned cells. Three outcomes are
   permanently missing and stay missing wherever this screen is cited.
2. **Not a population estimate.** Six parent groups of 96, one subject, one settings profile. No
   success rate, no difficulty claim, no training-utility claim.
3. **The evaluation split is closed** and was never opened for this screen.
4. **Post-run analysis.** Every decomposition here was computed after the run because the live
   capture failed. The rewards are unaffected by that failure and are preserved exactly; their
   validity is separate from the failed diagnostic and archival steps.
5. **`L` is not replayed offline** for generated cells; see §2.
6. **Two cases, one template.** The omission pattern is observed twice on `ar-tenterhook` and once,
   earlier, on an authored world. That is a diagnostic example, not a rate.
