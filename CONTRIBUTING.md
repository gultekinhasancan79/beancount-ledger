# Contributing to beancount-ledger

Useful contributions make an accounting task clearer, an evaluation easier to reproduce, or a scorer more reliable. Small documentation fixes and reproducible disagreements are welcome.

## Start with an existing task

Follow the [installation and local walkthrough](README.md#quickstart). The walkthrough uses a reference solution and does not call a model. Read [what gets checked](README.md#what-gets-checked) before interpreting a result.

For setup failures, use the **Bug or installation problem** issue form. For a task ambiguity, unexpected scoring decision, or missing accounting check, use **Task or scorer feedback**. A useful report includes:

- source commit or installed version, and the task ID when applicable;
- the smallest reproduction you can share;
- the relevant public accounting facts;
- expected versus observed behavior, including scoring components rather than only the total.

If the result came from a model run, include the requested model ID and the relevant run settings. Exclude API keys, evaluator secrets, private ledgers, and client data from public reports. Reports based on the repository's authored examples are easiest to reproduce.

## Local checks

From the repository root with its pinned dependencies installed:

```bash
uv run --no-sync python examples/scoring_walkthrough.py
```

For a cash-application scoring change, run the existing targeted suite:

```bash
uv run --no-sync python tests/test_cash_application_scoring.py
```

Run the full suite before submitting a code, task, dependency, or scoring change:

```bash
uv run --no-sync python tests/run_all.py
```

CI exercises the full suite on Linux and Windows, checks supported Python/Unicode versions, and audits the wheel and source distribution. Documentation-only changes need link and formatting checks; the repository's configured CI still runs on the pull request.

## Keep measurement changes explicit

- **Scorers and schemas:** identify which behavior changes and why. Include a reproducing failure and the expected result, and retain acceptance coverage for correct solutions.
- **Task authoring:** explain the accounting facts and intended distinction. Workflow variants sharing a company-month are related samples; preserve the documented world-level split rules.
- **Observed failures:** a task or test designed after an observation is development or regression evidence. Label that relationship rather than treating it as an untouched evaluation case.
- **Dependencies and episode contracts:** exact pins and digests are part of the instrument. Follow the [technical reference](docs/REFERENCE.md) and existing conformance tests when changing them; describe any new measurement condition.
- **Published evidence:** preserve original run artifacts and measured revisions. Add a dated correction or a separately named new run instead of silently replacing historical results.
- **Packaging:** keep tests, evaluator-only fixtures, and evidence archives out of the published runtime package.

## Pull requests

Keep one concrete problem per change. Describe the resulting behavior, the validation performed, and any effect on tasks, scoring, contracts, or published claims. A proposed feature can start as an issue explaining who would use it and what observable behavior it should add.

No new model evaluation is necessary for a documentation-only change. When a measurement is part of a contribution, distinguish an actual model run from a reference-solution check and report its scope and limitations.
