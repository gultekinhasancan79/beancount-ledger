# beancount-ledger

[![CI](https://github.com/gultekinhasancan79/beancount-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/gultekinhasancan79/beancount-ledger/actions/workflows/ci.yml) [![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE) [![Python 3.11–3.13](https://img.shields.io/badge/python-3.11%E2%80%933.13-blue.svg)](pyproject.toml)

**An environment for evaluating AI agents on bookkeeping and cash application, with inspectable, deterministic scoring.**

Agents read accounting evidence, repair a Beancount ledger, and, for cash-application tasks, deliver a register of payments and invoice balances. The evaluator checks the work against the task's accounting facts and reports the criteria behind the reward.

[Try the scorer](#quickstart) · [What gets checked](#what-gets-checked) · [Evaluation evidence](#evaluation-evidence) · [Technical reference](docs/REFERENCE.md)

![Accounting evidence leads to a ledger and payment register, evaluated through ledger criteria, application criteria, and a completion check.](docs/assets/scoring-overview.svg)

## What gets checked

| Deliverable | Scoring criteria | Additional checks |
|---|---|---|
| Beancount ledger | Target balances reached; planted errors resolved | Preservation of existing records, damage to other accounts, fabricated or merged entries, undocumented repairs, and accounts outside the chart |
| Cash-application register | Receipt applications, closing invoice rows, and credit-note applications | Receipt conservation, closing receivables, write-offs, schema validity, and internal accounting identities |

The ledger and application components are evaluated separately. Cash-application reward is **ledger score × application score**, with completion requiring a complete ledger and an exact, delivered register without application penalties. Ledger-only tasks use the ledger score. [Scoring contracts and formulas](docs/REFERENCE.md).

## Quickstart

### Run a local scoring walkthrough

Requirements: Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Python 3.11–3.13. The commands below select Python 3.12 and install the pinned package dependencies.

```bash
git clone https://github.com/gultekinhasancan79/beancount-ledger.git
cd beancount-ledger
uv venv --python 3.12
uv pip install -e .
uv run --no-sync python examples/scoring_walkthrough.py
```

The walkthrough executes the production scorers on the reference ledger and a register reconstructed from the task's public evidence. It prints the scoring components, findings, accounting ties, and completion result, then verifies the result digests. **No API key or model call is needed.** Installing dependencies requires network access.

This is a reference-solution walkthrough, not an agent rollout or a model-performance result. [Example output and explanation](docs/DEMO.md).

To select another authored cash-application task or inspect structured output:

```bash
uv run --no-sync python examples/scoring_walkthrough.py --task cash_application_001 --json
```

### Evaluate your model or review episodes

From the installed checkout, configure your provider's API key in an environment variable and use the pinned `vf-eval` CLI. [Model-run command and recorded examples](docs/REFERENCE.md#sample-vf-eval-runs-raw-transcripts-included).

For the local desktop app:

```bash
uv pip install -e ".[app]"
uv run --no-sync python tests/replay_webview.py
```

Live model runs use your provider account. Authored tasks need no evaluator secret; generated worlds require the [operator setup](docs/REFERENCE.md).

**Version and compatibility:** this README describes source **0.2.0**, using `verifiers==0.3.1` and its legacy **v0** workflow. It does not implement v1. The published Hub package is still the earlier version; use this source checkout for 0.2.0 and the walkthrough. [Compatibility details](docs/REFERENCE.md#compatibility-020).

## Environment coverage

| Task set | Current source coverage |
|---|---|
| Bookkeeping workflows | 91 task IDs across ten company-months |
| Clean-month assurance | Four task IDs |
| Cash application | Eleven variants across four company-months |
| Keyed bank reconciliation | Separate generated population with evaluator-controlled manifests |

The **106 authored task IDs** are public demonstrations and tests. Workflow variants share company facts, so they must be split and aggregated by world. They are not 106 independent held-out samples. Cash-application generation is not implemented.

Workflows cover bank reconciliation, accounts payable, receivables, bank-feed categorization, expenses, payroll, sales tax, fixed assets, intercompany transfers, and month-end close. [Full task matrix and split rules](docs/REFERENCE.md#hand-authored-workflow-tasks).

## Evaluation evidence

- **[Fixed-panel study](reviews/arms_confirm1v4.md):** four open-weight models × six generated bank-reconciliation tasks × three episode-contract arms × two replicates. Of 144 scheduled cells, 143 ran and 138 were valid. The report records the measured source revision, results, missing cells, and limitations.
- **[Evidence index](reviews/README.md):** dated cash-application screens, scorer audits, exploit tests, and release provenance. Each historical result belongs to its recorded task and instrument version.
- **[Tests](tests/):** reference acceptance, adversarial cases, scorer behavior, and reproducibility checks, exercised by CI.

The fixed-panel study is separate from the 106 authored tasks and the local walkthrough. **No RL policy was trained in that study.** The small cash-application screens do not establish population failure rates or training utility; practitioner accounting validation remains outstanding.

## Engineering details

- **Reproducibility:** pinned dependencies, versioned episode contracts, and recorded result digests.
- **Adversarial checks:** hand-written attacks, generated constructions, an independent exploit oracle, and rotating nightly sweeps.
- **Generation boundary:** HMAC-keyed generation identity; each task remains solvable from its public accounting evidence.
- **Package boundary:** evidence archives, test fixtures, and the local walkthrough stay in the repository rather than the Hub package.

[Technical reference](docs/REFERENCE.md) · [Release attestation](reviews/RELEASE_ATTESTATION.md)

## Try it and report what you find

If you evaluate accounting agents or build task graders, start with the local walkthrough. Useful feedback includes an unclear input, a scorer disagreement, or a reproducible model failure. [Open an issue](https://github.com/gultekinhasancan79/beancount-ledger/issues) with the task ID, source commit, reproduction steps, and expected versus actual result.

Built by [Hasancan Gültekin](https://github.com/gultekinhasancan79) on [Prime Intellect's verifiers](https://github.com/PrimeIntellect-ai/verifiers). [Email](mailto:gultekinhasancan79@gmail.com) · [LinkedIn](https://linkedin.com/in/can79) · [Manifund project](https://manifund.org/projects/beancount-ledger-a-deterministic-reward-rl-environment-for-agentic-bookkeeping).
