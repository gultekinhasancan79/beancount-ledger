# beancount-ledger

[![CI](https://github.com/gultekinhasancan79/beancount-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/gultekinhasancan79/beancount-ledger/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.11–3.13](https://img.shields.io/badge/python-3.11%E2%80%933.13-blue.svg)](pyproject.toml)

**A deterministic accounting environment for ledger repair and batched cash application.** Agents inspect accounting evidence and deliver a corrected Beancount ledger. Cash-application tasks additionally require a receipt-and-invoice application register, allowing the evaluator to detect errors that aggregate ledger postings cannot distinguish.

Version 0.3.0 includes 106 authored task IDs: 91 workflow tasks, four clean-month assurance tasks and eleven cash-application variants across four company-months (Bowline's five, then three matched pairs whose two variants differ in exactly one authored fact). The 95 legacy tasks retain episode contract 4; cash application uses contract 5 and combines the ledger and application scores multiplicatively. Authored tasks are public demonstrations and tests. **0.3.0 also distributes cash-application generation**, as a *released development population* — 96 keyed parent groups, 192 variants, admitted under the corrected admission contract 2 — that an installed wheel can mint and serve. The existing keyed bank-reconciliation population (generator 9) is separate and unmoved.

> **0.3.0 is a NEW package version, not a rebuilt 0.2.0.** The generator correction ships under its own version so that no rebuilt wheel ever carries the published 0.2.0 identity. 0.2.0 stands on the Environments Hub as `cangultekn/beancount-ledger` exactly as it was uploaded, and it contains no cash-application generation that can run installed. **Nothing here was uploaded or withdrawn:** publishing is the owner's act. Like 0.2.0, this release uses the deprecated verifiers v0 interface and does not provide v1 compatibility.

> **Compatibility.** This release (0.3.0) targets the **v0 workflow** — `load_environment` discovered by name in the installed module, driven by `vf-eval`, configured by `[tool.verifiers.eval]`, against the pinned `verifiers==0.3.1`. Prime Intellect's current environment documentation lists that workflow under **Legacy** and identifies it as deprecated v0. Publishing 0.3.0 does **not** imply v1 support, and nothing here claims it: verified against this package's own entry points, `beancount_ledger/__init__.py` exports exactly one serving door (`load_environment`), `pyproject.toml` declares no `[project.entry-points]` group and no v1 protocol object, and every `verifiers` base the environment subclasses resolves into the framework's own legacy tree (`StatefulToolEnv` → `verifiers.legacy.envs.stateful_tool_env`, `Rubric` → `verifiers.legacy.rubrics.rubric`, `Environment` → `verifiers.legacy.envs.environment`, `stop` → `verifiers.legacy.decorators`; the framework's own loader logs under `verifiers.legacy.utils.env_utils`). A v1 migration is separate work and is deliberately not slipped into this frozen instrument. The documented versioned upload preserves earlier releases, so publishing 0.3.0 withdraws neither 0.2.0 nor 0.1.0.

No LLM judge: every discrepancy is planted by a generator or an author that knows the correct ledger, and the scorer pays exact partial credit against it.

Built on [Prime Intellect's `verifiers`](https://github.com/PrimeIntellect-ai/verifiers). Published on the Environments Hub as `cangultekn/beancount-ledger`. Apache-2.0.

### Why this is hard to game

- **The reward is derived, not judged.** Trial balance ties or it does not; planted discrepancies are resolved or they are not. Penalties for damaging existing records, fabricating entries or inventing accounts.
- **Generation identity is keyed; the accounting evidence is not.** Worlds are HMAC-keyed under an evaluator secret and public ids derive from public bytes only, so the private generation identity of a task cannot be recovered from what the agent sees. That is all the key protects. It does not make the accounting unsolvable from the evidence, and it is not meant to: the cash-application family's public fold deliberately reconstructs the whole application register from the public files, and that reconstruction is one of the checks a task must pass before it is admitted. The wheel ships no golden ledgers, no tests and no provenance for generated worlds. The hand-authored tasks are demos and tests by construction, never a held-out evaluation.
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

One hundred and six hand-authored tasks ship in the wheel and need no secret. **Ninety-one of them are the workflow grid** this section describes: ten small companies, one month each, authored as facts only (`beancount_ledger/graph/worlds/`), and every company except the original Alpine world carries all ten accounting workflows over the SAME statement and the SAME facts. Each task plants two or three discrepancies (an omitted entry, a wrong amount, a duplicate), each of the ninety workflow tasks with two timing-difference traps to leave alone. Task ids are `<workflow>_<company>`; the ten original tasks keep their `_001` ids. Count them honestly: nine independently authored company-months plus Alpine, exercised through ninety workflow-conditioned variants, so split by world, never by task. **The other fifteen** are the four-task clean-month pack (`clean_month_maple`/`clean_month_silverbrook`, `single_error_maple`/`single_error_silverbrook`) and the eleven cash-application variants (`cash_application_001`..`011`), which serve eleven public files and a second deliverable under episode contract 5. The full 91-cell table, what each workflow plants and the split rules: [docs/REFERENCE.md](docs/REFERENCE.md#hand-authored-workflow-tasks).

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

### The two episode profiles

A task resolves one of two profiles, and the profile fixes the tool surface, the deliverables and the envelopes. Nothing else about the loop differs: whole-file reads, the same stop conditions, the same malformed-call policy, the same budgets.

| | `legacy` — the 95 workflow and clean-month tasks | `cash_application` — `cash_application_001`..`011` |
|---|---|---|
| Episode contract | 4, shape `piv.episode-contract/2`, digest `e8b8753d…` | 5, shape `piv.episode-contract/3`, digest `b11bc1ac…` |
| Tools | `list_files`, `read_file`, `grep`, `run_beancount`, `write_ledger`, `submit` | the same six, plus `write_cash_application` |
| Public files | 8 | 11 (adds `open_items.csv`, `remittance_advice.csv`, `credit_notes.csv`) |
| Deliverables | `ledger.beancount` | `ledger.beancount` **and** `cash_application.json` (schema `piv.cash-application/1`), the second write-only, optional at submit and required for `complete` |
| Reward | `L` from `candidate/1` | `total = L × A`, `A` from `application/1`, composed by `composite/1` |
| Write envelopes | ledger 48,000 bytes / 1,000 lines | ledger as legacy; register 16,000 bytes / 400 lines |
| Budgets | 25 turns, 40,000-token episode output ceiling, 768,000-byte observation ceiling | identical |

Contract 4 is preserved byte for byte for the 95 legacy tasks, because they were measured under it; the two views are dispatched by profile and both digests are pinned in `tests/test_episode_contract.py`.

**What has been measured on the authored cash-application tasks.** Two small screens and one cold adjudication, all zero-cost, one requested model ID each and one attempt per cell. The one screen run on the *generated* population is in the next section.

- **Bowline, three episodes** on three of that company-month's five variants: two complete two-artifact deliveries and one case where the ledger scored 1.0 while the application register lost a single field — [reviews/cash_application_screen_2026-09-10.md](reviews/cash_application_screen_2026-09-10.md).
- **The six new variants, one episode each** — an **incomplete descriptive screen**: five scored deliveries, four of them a complete 1.0, one (`cash_application_007`) scoring 0.64 on a complete ledger repair with two invoices missing from the closing register, and `cash_application_011` lost to a provider 403 with no delivery. That sixth cell stays missing — neither a zero nor an inferred success — [reviews/cash_application_six_variant_screen_2026-09-11.md](reviews/cash_application_six_variant_screen_2026-09-11.md).
- **A cold adjudication of the Bowline five**, two models of different lineages, neither the screens' subject, each shown only the eleven public files — [reviews/cash_application_adjudication_2026-09-10.md](reviews/cash_application_adjudication_2026-09-10.md).

Together these establish that the second deliverable can fail on its own while the ledger is perfect, and that two independent readers reconstructed the specified applications and closing balances from the public files alone on five authored cases. They establish **no** population failure rate, no difficulty level, no accounting accreditation, no generalization beyond these company-months and no training benefit. The accounting of the three new company-months carries a dated AI accounting-plausibility review, not a practising accountant's sign-off; practitioner validation is still outstanding.

### The generated cash-application population (new in 0.3.0)

0.3.0 distributes `cash-application-development-2` as a **released development population**. *Released* describes distribution: the generator, the population declaration and the admission battery ship in the wheel, and a package installed from that wheel can mint a declared group and serve both its variants. *Development* describes the population's experimental role, and it keeps that role — the frozen 60/20/20 split assignment is unchanged and **the evaluation split is not opened**. It stays closed by the absence of a roster entry rather than by a prohibition: `fc-harrowfield`, `cr-oysterbank` and `ar-coldharbour` are sealed into `evaluation`, no released population declares them, so no selector spells them and the door refuses them as undeclared members.

- **96 predeclared parent groups**, 32 per mechanism stratum (fallback continuation, credit residue, advice residue), two variants each, every one of them in the `development` split, declared in a fixed order before any draw. Membership is a function of the frozen split map alone; the evaluator secret decides only what a declared identity draws.
- **The admission rule was corrected before this population was drawn.** A credit note is bounded by the original sale it names, never by the invoice's unpaid opening balance. The correction is versioned — gate implementation version **2**, family preflight contract **2**, gate-set digest `2491e97f97b48cee` — and the population selected under the old rule, `cash-application-development-1`, is retired, unspellable and preserved unaltered as history.
- **Census, validation, serving.** 96 admitted groups, 0 exhausted, 98 retained attempts, **0 accounting-gate refusals**; 192/192 variants pass all seven offline validation gates, including both goldens and their composite at `1.000000` through the shipped `candidate/1`, `application/1` and `composite/1`; 192/192 signed records serve through the real `load_environment` under the same episode-contract digest an authored cash task serves — [`reviews/cash_application_development_population_2026-09-13_replacement.md`](reviews/cash_application_development_population_2026-09-13_replacement.md).
- **Measured from the distributed artifact, not only from a checkout.** A 0.3.0 wheel installed into a clean throwaway virtual environment, with the repository absent from `sys.path`, mints one declared group per stratum and serves all six variants at reward 1.0, and the eleven authored cash tasks plus a legacy control score twelve of twelve on the same wheel — [`reviews/installable_serving_check_2026-09-14/`](reviews/installable_serving_check_2026-09-14/).
- **One screen has been run on it, and it is incomplete.** Nine scored cells, one attempted but unscored (a provider quota refusal took the cell), two unattempted, against twelve planned — seven complete successes and two application-only partials, with missing outcomes distinguished from model failures and left missing: [`reviews/cash_application_generated_screen_2026-09-13.md`](reviews/cash_application_generated_screen_2026-09-13.md). It establishes no population success rate, no difficulty and no training utility.

The whole of what this generator deliverable claims, stated exactly:

> A versioned, keyed cash-application generator with a frozen development population, deterministic accounting checks, golden-artifact validation and signed-manifest serving under the recorded repository runtime. No model performance, difficulty, training benefit or generalization beyond the development templates has been established.

Generated cash-application selectors are evaluator-side and need the evaluator secret and a signed family manifest; this family has no development bypass. The wheel ships no goldens, no census and no provenance for generated worlds.

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
