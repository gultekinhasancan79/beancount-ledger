# Evidence — cash-application screen 1, 13 September 2026

The note this belongs to is `reviews/cash_application_generated_screen_2026-09-13.md`, published as
an **INCOMPLETE DEVELOPMENT SCREEN**: nine scored, one attempted but unscored, two unattempted,
against twelve planned cells.

Everything here is either an observed byte preserved as it was delivered, or a post-run analysis
that says so on its face. No observed submission is overwritten anywhere in this directory.

## Index

| path | what it is |
|---|---|
| `workspaces/<cell>/` | the nine rescued episode workspaces, thirteen files each: the eleven public inputs, the delivered `ledger.beancount` and `cash_application.json`, and the `delivery.json` receipt. Copied out of `%TEMP%` before it was cleaned. **Observed.** |
| `counterfactual/<cell>/cash_application.delivered.json` | a byte-identical copy of that cell's delivered register, so the diff has both sides beside it. **Observed.** |
| `counterfactual/<cell>/cash_application.corrected.json` | the minimal correction: the delivered document with ONLY the omitted closing rows added. **Post-run analysis.** |
| `counterfactual/<cell>/cash_application.diff` | the exact unified diff between the two. One hunk, purely additive. |
| `rescore_cash_screen_1.py` | the executable rescore. Run it; it rebuilds every figure below. |
| `rescore_cash_screen_1.json` | its record: per-cell bindings, both decompositions, the counterfactual, the consumption arithmetic and the service-attribution audit. **Post-run analysis.** |
| `cash_screen_1_selection.py` | the script that froze the selection before any model call. Published beside the record it produced (`reviews/cash_screen_1_selection_2026-09-13.json`), which the ruling asked for: neither may live only in scratch. |
| `cash_screen_1_runner.log` | the runner's console log, including the 403 that ended the run. It is the cell-10 reconstruction's evidence. **Observed.** |

Beside this directory, in `reviews/`:

- `budget_qwen3.7-max-2026-05-20_2026-09-13_cash_screen_1.json` — the nine result rows, **unmodified**,
  and `…_cash_screen_1/` — the per-selector archive the runner wrote;
- `cash_screen_1_selection_2026-09-13.json` — the frozen selection, self-digest `321c9715…`;
- `cash_screen_1_retrospective_census_2026-09-13.json` and its builder — the twelve-cell disposition,
  with the reconstruction of the cell the provider failure took;
- `cash_application_development_population_2026-09-13_replacement.md` — the population these cells
  were drawn from.

## Reproducing it

```
.venv/Scripts/python.exe reviews/cash_application_generated_screen_2026-09-13/rescore_cash_screen_1.py
```

Offline, no model calls, no evaluator key. It exits non-zero and names the problem if anything fails
to bind. What it checks:

1. **Bindings.** Each recovered `cash_application.json` and `ledger.beancount` reproduces the
   stored-bytes and logical-text digests its result row recorded, and each workspace's delivery
   receipt agrees with the row. Nine cells, five checks each.
2. **The pin.** The truth register is rebuilt from public evidence by `tests/observed_truth.py` —
   the generated population is keyed and this analysis does not read the evaluator secret. The
   rebuild is not taken on trust: the outcome it produces must reproduce the
   `application_result_digest` the live run wrote into that cell's delivery receipt, and that digest
   covers the whole decomposition — total, all three channel fractions, every penalty, and one state
   per receipt, invoice, credit note and tie. It reproduces for all nine, along with each document's
   canonical digest.
3. **The counterfactual.** For each partial: write the corrected bytes and the diff, refuse a diff
   that removes anything, score both arms against the SAME reconstructed truth, and require
   A 0.625000 → 1.000000 with no penalty and every receipt, credit and untouched register state
   unchanged.
4. **Consumption.** 926,855 input + 157,237 output = 1,084,092 across the nine rows and 64 captured
   responses; mean 120,454.7; range 97,137–163,908. The script fails if any of those move.
5. **Attribution.** Every row's `provider` field, the recorded endpoint, the requested model, the
   returned model names and every captured `system_fingerprint`.

`tests/test_cash_application_scoring.py` carries the same two partials as observed fixtures under
`tests/observed/cash_screen_1_ar-tenterhook_{22,24}_a/`, and pins those copies to the bytes in this
directory, so neither can drift alone.

## What this evidence cannot do

`candidate/1` scores a ledger against the task's golden, which for a generated task is minted under
the evaluator key. **`L` is not recomputed here.** The live figure (1.000000 on all nine) is carried
and labelled, and the composite is the shipped product rule applied to a live `L` and a recomputed
`A`. The ledger bytes are published and bound, so the replay is available on a machine holding the
key. The claim the counterfactual tests is an application-channel claim, and the ledger bytes are
identical in both of its arms.
