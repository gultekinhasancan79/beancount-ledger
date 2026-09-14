# Inspect the current scoring criteria

The local walkthrough runs the repository's production scorers on an authored task's **reference solution**. It prints the criteria and findings behind the reward without calling a model or using an API key.

The default task is `cash_application_006`, from the Thornbury company-month added in source 0.2.0. You can select any of the eleven authored cash-application tasks with `--task`.

## Run it

From a checkout with the pinned dependencies installed:

```bash
uv run --no-sync python examples/scoring_walkthrough.py
```

[Full installation commands](../README.md#quickstart).

## What happens

1. The task's authored world is projected into its public accounting files and evaluation contract.
2. The reference ledger is passed through the real parse, commit, and ledger-scoring pipeline.
3. The payment register is reconstructed from the public files using the repository's deterministic fold, then passed through the application scorer.
4. The composite scorer combines the results and checks completion. All three result digests are verified.

No historical model result is replayed. The reference ledger is available to this demonstration; it is not evidence that an agent solved the task.

## Read the output

| Output | Meaning |
|---|---|
| `targets_hit` | Fraction of scored account balances matching the task's expected balances |
| `errors_resolved` | Fraction of planted accounting errors repaired |
| Ledger findings | Unresolved work, changed original records, collateral damage, unexplained entries, or other integrity findings |
| `receipts_exact` | Fraction of receipts with exact applications, write-offs, and unapplied amounts |
| `register_exact` | Fraction of closing invoice rows matching the required fields |
| `credit_exact` | Fraction of credit notes with exact applications and residue |
| Accounting ties | Whether the register reconciles to closing receivables and period write-offs |
| `complete` | The explicit completion decision for both deliverables |

The reference solution is expected to score 1.000000 and complete. The point of the walkthrough is to expose the criteria and production code path behind that result. These checks do not establish model performance or independent accounting validation.

Excerpt from the default walkthrough:

```text
LEDGER CRITERIA
  targets_hit              1.000000
  errors_resolved          1.000000
  ...
APPLICATION CRITERIA
  receipts_exact           1.000000
  register_exact           1.000000
  credit_exact             1.000000
  ar                       AR_TIE_OK
  writeoff                 WRITEOFF_TIE_OK
  penalties                0

RESULT: L=1.000000 x A=1.000000
        total=1.000000 | complete=True
```

## Inspect structured output

```bash
uv run --no-sync python examples/scoring_walkthrough.py --task cash_application_001 --json
```

The JSON includes task ID, public filenames, engine IDs, per-criterion values, findings, completion, and the composite result digest. The script writes only to standard output; it does not change task files or archived results.

## Follow the implementation

- [Walkthrough source](../examples/scoring_walkthrough.py)
- [Ledger scoring](../beancount_ledger/candidate/committed.py)
- [Application scoring](../beancount_ledger/candidate/application.py)
- [Composite scoring](../beancount_ledger/candidate/composite.py)
- [Acceptance and adversarial tests](../tests/test_cash_application_scoring.py)

To evaluate an actual model, use the separate [model-run workflow](REFERENCE.md#sample-vf-eval-runs-raw-transcripts-included). Its result depends on the chosen model, provider settings, and task; the reference walkthrough makes no prediction about that result.

To evaluate your own models on fresh keyed instances of the generated cash-application population, under your own evaluator key and with a result record comparable to the published screens, use the [evaluation pack](evaluation_pack/PACK.md).
