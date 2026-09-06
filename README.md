# beancount-ledger

[![CI](https://github.com/gultekinhasancan79/beancount-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/gultekinhasancan79/beancount-ledger/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.11–3.13](https://img.shields.io/badge/python-3.11%E2%80%933.13-blue.svg)](pyproject.toml)

**A reinforcement-learning environment where an agent does a small company's bookkeeping, and the reward is whether the books actually balance.** No LLM judge. Every discrepancy is planted by a generator that knows the correct ledger, so the scorer pays exact partial credit and cannot be argued with.

Built on [Prime Intellect's `verifiers`](https://github.com/PrimeIntellect-ai/verifiers). Published on the Environments Hub as `beancount-ledger`. Apache-2.0.

### Why this is hard to game

- **The reward is derived, not judged.** Trial balance ties or it does not; planted discrepancies are resolved or they are not. Penalties for damaging existing records, fabricating entries or inventing accounts.
- **Nothing the agent sees regenerates an answer.** Worlds are HMAC-keyed under an evaluator secret; public ids derive from public bytes only. The wheel ships no golden ledgers, no tests and no provenance for generated worlds. The hand-authored tasks are demos by construction, never a held-out evaluation.
- **An exploit corpus and an adversary loop** live in `tests/`: 26 hand-written attacks on the demo world, 14 constructions (13 families, 103 declared payloads, of which a world builds about 90 and skips the rest by name because it lacks the structure they attack) built from a minted world's public bytes, and a nightly sweep over rotating shards. The exploit corpus is scored against an oracle independent of the scorer.

### Quickstart

```bash
uv run vf-eval beancount-ledger          # zero setup: the default hand-authored task, works out of the box
```

```python
import beancount_ledger

env = beancount_ledger.load_environment()               # default: the hand-authored task "bank_recon_001"
env = beancount_ledger.load_environment("payroll_001")  # any other hand-authored workflow task (table below)
env = beancount_ledger.load_environment("train:7")      # a generated task (requires the operator setup below)
```

```bash
uv run vf-eval beancount-ledger --env-args '{"task_id": "ap_payment_run_001"}'   # a workflow task from the CLI
```

### Hand-authored tasks

Ninety-one tasks ship in the wheel and need no secret: ten small companies, one month each, authored as facts only (`beancount_ledger/graph/worlds/`), and every company except the original Alpine world carries all ten accounting workflows over the SAME statement and the SAME facts. Each task plants two or three discrepancies (an omitted entry, a wrong amount, a duplicate), most with one timing-difference trap to leave alone. Task ids are `<workflow>_<company>`; the ten original tasks keep their `_001` ids. Count them honestly: nine independently authored company-months plus Alpine, exercised through ninety workflow-conditioned variants, so split by world, never by task. The full 91-cell table, what each workflow plants and the split rules: [docs/REFERENCE.md](docs/REFERENCE.md#hand-authored-workflow-tasks).

| Company | Month |
|---|---|
| Hawthorn Bakery | December 2025 |
| Maple Street Veterinary Clinic | December 2025 |
| Falcon Ridge Surveying | February 2026 |
| Thistle & Quill Design Studio | January 2026 |
| Oakridge Machining | March 2026 |
| Redwood Analytics Group | November 2025 |
| Silverbrook Dental Supply | November 2025 |
| Alpine Trading Co. | November 2025 (bank recon only: `bank_recon_001`) |
| Ironwood Furniture Works | October 2025 |
| Bluewater Marine Supply | October 2025 |

The ten workflows, with their id prefixes: bank recon (`bank_recon`), AP run (`ap_payment_run`), AR collections (`ar_collections`), bank feed (`bank_feed_categorisation`), expense reports (`expense_reports`), payroll (`payroll`), sales tax (`sales_tax_remittance`), fixed assets (`fixed_assets`), intercompany (`intercompany_transfers`), month-end close (`month_end_close`).

### Desktop app

A native window that runs and replays episodes. Start it from a repository checkout with `pywebview` installed:

```bash
python tests/replay_webview.py
```

Pick a company and month, then a task, and press Run: every `write_ledger` is diffed and scored the moment it is committed, by the production scorer. API keys are read from environment variables set on the PC; the window shows their names only, never values. Runs are saved under `outputs/evals/` and stay on that machine. Generated worlds need the evaluator secret and a release manifest.

### Results at a glance

Preregistered, sealed measurement: 4 open-weight Mistral models × 6 generated tasks × 3 episode-contract arms × 2 replicates. 143 of 144 cells ran, 138 valid, **0 scorer disputes, 0 exploits**.

- **The reward separates capability.** Small models deliver 0–17% correct, stronger ones 58–92%, with real partial credit in between.
- **Replaying prior-turn reasoning is a model-specific knob.** On `devstral-2512`, not replaying improved correct delivery by +0.36; on `mistral-medium-2508` the direction reversed. Neither is a default recommendation.
- **No RL learnability claim.** No policy was trained here; that is what the environment is for.

Per-model table, intervals and every failure named: [docs/REFERENCE.md](docs/REFERENCE.md#results-at-a-glance-fixed-panel) and [`reviews/arms_confirm1v4.md`](reviews/arms_confirm1v4.md).

### Security and provenance

- Worlds are keyed (HMAC under the evaluator secret); public ids derive from public bytes only.
- The Hub artefact ships **no** goldens, no test suite, no provenance records, no secrets; the wheel's file list is audited per release.
- Read tools accept only the eight declared names, never paths.
- Dependencies are pinned exactly; a bump moves the episode-contract digest and is loud, never silent.
- Every number above is reproducible from a sealed contract: the instrument commit, episode-contract digest and package pins are recorded in [`reviews/RELEASE_ATTESTATION.md`](reviews/RELEASE_ATTESTATION.md).

### Read more

- [docs/REFERENCE.md](docs/REFERENCE.md): the technical reference — contracts, rubric, the full 91-task matrix, the fixed-panel measurement, sample runs, versions, provenance.
- [reviews/README.md](reviews/README.md): the index of dated evidence — pre-registration, sealed schedule, arm tables, release attestation, audits.

### Author

Designed and built by Hasancan Gültekin in 2026 as a deterministic-reward alternative to judge-scored agent benchmarks. Registered as a project on [Manifund](https://manifund.org/projects/beancount-ledger-a-deterministic-reward-rl-environment-for-agentic-bookkeeping). Questions, collaboration, or a run on your own models: gultekinhasancan79@gmail.com · [GitHub](https://github.com/gultekinhasancan79) · [LinkedIn](https://linkedin.com/in/can79).
