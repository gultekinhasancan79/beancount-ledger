# beancount-ledger — technical reference

This is the technical reference that [README.md](../README.md) points to: the detailed contract of the environment, moved here verbatim from the README.

Everything below is the detailed contract: how worlds are keyed and manifested, the observation and episode contracts, the rubric, security properties and provenance.

## Overview
- **Environment ID**: `beancount-ledger`
- **Short description**: Multi-turn tool-use bank reconciliation with a deterministic, exploit-hardened reward
- **Tags**: `accounting`, `tool-use`, `multi-turn`, `train`, `eval`

## Quickstart

```bash
uv run vf-eval beancount-ledger          # the default hand-authored task, works out of the box
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

## Hand-authored workflow tasks

Ninety-one tasks ship in the wheel and need no secret: ten small companies, one month each, authored as facts only (`beancount_ledger/graph/worlds/`), and every company except the original Alpine world carries all ten accounting workflows over the SAME statement and the SAME facts — a person opening Ironwood's October picks the job: the payment run, collections, payroll, the sales-tax filing, the month-end close. The eight public files, the golden ledger, the scored accounts and the expected balances are all derived, never typed. Every task plants two or three discrepancies of the kinds the scorer understands — an entry the books lack (`omit`, `o` below), an entry keyed with the wrong amount (`alter`, `a`), an entry posted twice (`duplicate`, `d`) — and most carry one timing-difference trap the agent must leave alone (an outstanding cheque, a deposit in transit). `tests/test_worlds.py` proves, for every entry, that the golden ledger scores 1.0, the untouched ledger leaves every planted item unresolved, the repairs are uniquely inferable from the public files, and no two planted items share a posting pair (the scorer's merged-entry rule would otherwise zero a perfect answer).

Task ids are `<workflow>_<company>`; the ten original tasks keep their `_001` ids. In the table, the letters after each id are the planted kinds in plan order.

Count them honestly: this is **nine independently authored company-months plus Alpine, exercised through ninety workflow-conditioned variants**, not ninety-one independent samples. The variants of one company share its statement, its parties and its amounts, so a model that has seen Ironwood's payment run has seen most of what Ironwood's payroll task shows it. Two rules follow. Split by world, never by task: every variant of a company stays on the same side of a train/eval split. Aggregate by world first: average a model's ten variants into one number per company, then compare companies. Within one company the ten variants are legitimate data augmentation for training, and a 7-train / 3-eval split of workflows inside a world measures workflow transfer, not generalisation to a new company. For generalisation, use the generated population.

| company, period | bank recon | AP run | AR collections | bank feed | expense reports | payroll | sales tax | fixed assets | intercompany | month-end close |
|---|---|---|---|---|---|---|---|---|---|---|
| Hawthorn Bakery, December 2025 | `bank_recon_hawthorn` (oad) | `ap_payment_run_hawthorn` (oad) | `ar_collections_hawthorn` (oad) | `bank_feed_categorisation_hawthorn` (ooa) | `expense_reports_hawthorn` (oda) | `payroll_001` (oao) | `sales_tax_remittance_hawthorn` (oad) | `fixed_assets_hawthorn` (oao) | `intercompany_transfers_hawthorn` (oda) | `month_end_close_hawthorn` (oad) |
| Maple Street Veterinary Clinic, December 2025 | `bank_recon_maple` (oad) | `ap_payment_run_maple` (oad) | `ar_collections_maple` (oad) | `bank_feed_categorisation_maple` (ooa) | `expense_reports_maple` (oda) | `payroll_maple` (oao) | `sales_tax_remittance_maple` (oad) | `fixed_assets_maple` (oao) | `intercompany_transfers_maple` (oda) | `month_end_close_001` (oad) |
| Falcon Ridge Surveying, February 2026 | `bank_recon_falcon` (oao) | `ap_payment_run_falcon` (oad) | `ar_collections_falcon` (oad) | `bank_feed_categorisation_falcon` (ooa) | `expense_reports_001` (oda) | `payroll_falcon` (oao) | `sales_tax_remittance_falcon` (oad) | `fixed_assets_falcon` (oad) | `intercompany_transfers_falcon` (oda) | `month_end_close_falcon` (oad) |
| Thistle & Quill Design Studio, January 2026 | `bank_recon_thistle` (oad) | `ap_payment_run_thistle` (oad) | `ar_collections_thistle` (oad) | `bank_feed_categorisation_001` (ooa) | `expense_reports_thistle` (oda) | `payroll_thistle` (oao) | `sales_tax_remittance_thistle` (oad) | `fixed_assets_thistle` (oao) | `intercompany_transfers_thistle` (oda) | `month_end_close_thistle` (oad) |
| Oakridge Machining, March 2026 | `bank_recon_oakridge` (oad) | `ap_payment_run_oakridge` (oad) | `ar_collections_oakridge` (oad) | `bank_feed_categorisation_oakridge` (oad) | `expense_reports_oakridge` (oda) | `payroll_oakridge` (oao) | `sales_tax_remittance_oakridge` (oad) | `fixed_assets_001` (oao) | `intercompany_transfers_oakridge` (oda) | `month_end_close_oakridge` (oad) |
| Redwood Analytics Group, November 2025 | `bank_recon_redwood` (oao) | `ap_payment_run_redwood` (oad) | `ar_collections_redwood` (oad) | `bank_feed_categorisation_redwood` (ooa) | `expense_reports_redwood` (oda) | `payroll_redwood` (oao) | `sales_tax_remittance_redwood` (oad) | `fixed_assets_redwood` (oad) | `intercompany_transfers_001` (oda) | `month_end_close_redwood` (oad) |
| Silverbrook Dental Supply, November 2025 | `bank_recon_silverbrook` (oad) | `ap_payment_run_silverbrook` (oad) | `ar_collections_001` (oad) | `bank_feed_categorisation_silverbrook` (ooa) | `expense_reports_silverbrook` (oda) | `payroll_silverbrook` (oao) | `sales_tax_remittance_silverbrook` (oad) | `fixed_assets_silverbrook` (oad) | `intercompany_transfers_silverbrook` (oda) | `month_end_close_silverbrook` (oad) |
| Alpine Trading Co., November 2025 | `bank_recon_001` (oo) | — | — | — | — | — | — | — | — | — |
| Ironwood Furniture Works, October 2025 | `bank_recon_ironwood` (oao) | `ap_payment_run_001` (oad) | `ar_collections_ironwood` (oad) | `bank_feed_categorisation_ironwood` (ooa) | `expense_reports_ironwood` (oda) | `payroll_ironwood` (oao) | `sales_tax_remittance_ironwood` (oad) | `fixed_assets_ironwood` (oad) | `intercompany_transfers_ironwood` (oda) | `month_end_close_ironwood` (oad) |
| Bluewater Marine Supply, October 2025 | `bank_recon_bluewater` (oad) | `ap_payment_run_bluewater` (oad) | `ar_collections_bluewater` (oad) | `bank_feed_categorisation_bluewater` (ooa) | `expense_reports_bluewater` (oda) | `payroll_bluewater` (oao) | `sales_tax_remittance_001` (oad) | `fixed_assets_bluewater` (oao) | `intercompany_transfers_bluewater` (oda) | `month_end_close_bluewater` (oad) |

Workflows, and what each plants: **bank recon** a receipt, a supplier payment and a bank charge; **AP run** supplier payments never posted, keyed with transposed digits, posted twice; **AR collections** customer receipts, a partial receipt, a deposit in transit; **bank feed** card spend categorised by the vendor's default account (software, telecom, office, travel); **expense reports** employee claims reimbursed by cheque and a fuel card; **payroll** net pay by cheque and the withholding remittance; **sales tax** tax collected on sales and remitted to the state; **fixed assets** equipment capitalised on payment, repairs expensed; **intercompany** cash advanced to a group company, booked as due from it; **month-end close** a prepayment for next month, two bank charges, client receipts.

The workflow lives in the prompt, the policy text, the parties and what is planted; the scoring contract (`candidate/1`), the tools, the episode contract and the observation contract are the same for every task, so results are comparable across the table.

Generated tasks are **keyed and manifested**: each world derives from an HMAC under an evaluator secret (`PIV_EVAL_SECRET` or `~/.piv/eval_secret`, ≥16 bytes), and production serving admits only selectors recorded in a signed release manifest written by the preflight (`tests/preflight_manifest.py`, two-phase: offline gates on every minted world, then every record verified through the real serving door). Without the secret and manifest, a generated selector is refused with a named reason — the refusal path is structural: installed copies of this package **cannot** enable the development override (`PIV_DEV_UNMANIFESTED` is ignored outside the repository's own test entry points; witnessed from an installed wheel).

`PIV` is the prefix of everything the evaluator side owns and the framework does not: `PIV_EVAL_SECRET`, `PIV_MANIFEST`, `PIV_DEV_UNMANIFESTED`, the `~/.piv/` directory, the `piv_*` state keys a rollout carries and the `PIV*` exception classes. When you see it, you are looking at this package's evaluator, not at `verifiers`.

## Datasets
- **Primary**: generated worlds, selectors `train:<n>`, `eval:<n>`, `train:<n>:hard` (n < 100,000). The released population is preflighted 1,400/1,400 (1,000 train / 200 eval / 200 hard).
- **Shipped**: 91 hand-authored tasks (ten companies, ten workflows each except Alpine; see the table above) usable with no secret, for smoke tests, demos and cross-workflow comparison.
- Each world is a projection of a private fact graph; everything the scorer requires is derivable from the mounted files or stated in `policy.md`. Ledgers are 7–14 KB; the public observation contract is eight named files, nothing else.

## Task
- **Type**: multi-turn tool use, six tools: `list_files`, `read_file`, `grep`, `run_beancount`, `write_ledger`, `submit`.
- **Observation contract**: `ledger.beancount` is returned **whole in one call** (exactly as the scorer reads it, LF-normalized; envelope 48,000 bytes, enforced before the episode); other files come in numbered 200-line slices; one complete ledger read per revision (repeats get a bounded receipt); every reply is byte-capped and the episode carries an aggregate observation budget (768,000 bytes) — a cost bound, never a reward penalty.
- **Episode contract** (version 2, digest `152dbbaf…`, carried on every rollout): 25 turns; calls on the final turn are not executed, so submit by turn 24 — **or** let the limit end the episode: the latest successfully written ledger is scored either way. A total ceiling of 40,000 completion tokens (including hidden reasoning) is disclosed in the prompt and enforced exactly, per request. Three consecutive no-tool turns end the episode.
- **Rubric**: parse-gated (an unloadable ledger scores 0), then deterministic components — target account balances hit, planted discrepancies resolved as their own dated entries — minus penalties for damaging existing records, fabricating entries or inventing accounts. Partial credit is machine-computed; every reward claim in our test battery names its oracle, and the exploit corpus's oracle is semantic entitlement, independent of the scorer.

## Why this is hard to game

- **The reward is derived, not judged.** Trial balance ties or it does not; planted discrepancies are resolved or they are not. Penalties for damaging existing records, fabricating entries or inventing accounts.
- **Nothing the agent sees regenerates an answer.** Worlds are HMAC-keyed under an evaluator secret; public ids derive from public bytes only. The wheel ships no golden ledgers, no tests and no provenance for generated worlds. The hand-authored tasks are the exception by construction: their facts live in the package (`graph/worlds/`) and the demo task's scoring contract (`tasks/bank_recon_001.json`: expected balances and planted keys) ships with it, because a demo must score without a secret. Treat them as demos, never as a held-out evaluation.
- **An exploit corpus and an adversary loop** live in `tests/`: 26 hand-written attacks on the demo world, 14 constructions (13 families, 92 payloads) that read a minted world's public bytes to build their attack, and a nightly sweep over rotating shards (canonicalisation, decimal edge cases, duplicate detection, entitlement, and more). The exploit corpus is scored against an oracle independent of the scorer.
- **Every number above is reproducible from a sealed contract.** The pre-registration is hashed into the schedule id; the instrument commit, episode-contract digest and package pins are recorded in [`reviews/RELEASE_ATTESTATION.md`](../reviews/RELEASE_ATTESTATION.md).

## Results at a glance (fixed panel)

Preregistered, sealed measurement: 4 open-weight Mistral models × 6 generated tasks × 3 episode-contract arms × 2 replicates. 143 of 144 cells ran, 138 valid, **0 scorer disputes, 0 exploits**. Full table with every failure named: [`reviews/arms_confirm1v4.md`](../reviews/arms_confirm1v4.md).

| Model | Arm A: 8k tok/turn, reasoning replayed | Arm B1: 16k tok/turn, replayed | Arm B2: 8k tok/turn, no replay |
|---|---|---|---|
| `devstral-2512` | 58% | 73% | **92%** |
| `mistral-medium-2508` | **82%** | 45% | 64% |
| `ministral-14b-2512` | 0% | 0% | 17% |
| `ministral-8b-2512` | 0% | 8% | 0% |

*Correct deliveries out of valid completed episodes. Accepted-submit rate 83–100% everywhere; the 40K-token episode ceiling never bound.*

Two things this shows and one it does not:

- The reward **separates capability**: small models score near zero, stronger ones 58–92%, with real partial credit in between. That is what you want from a training signal.
- **Whether to replay prior-turn reasoning is a model-specific knob.** On `devstral-2512`, not replaying improved correct delivery by +0.36 at about half the tokens per correct answer; on `mistral-medium-2508` the direction reversed. Neither is a default recommendation.
- It does **not** show RL learnability. No policy was trained here; that is what the environment is for.

## What the fixed-panel measurement showed (evidence, not a recommendation)

A preregistered, sealed experiment (4 Mistral open-weight models × 6 tasks × 3 episode-contract arms × 2 replicates; 144 scheduled cells, 143 run, 138 valid, five named exogenous failures, one unrun cell — the full table with censuses and failure evidence is `reviews/arms_confirm1v4.md`):

- The reward is **capability-sensitive and non-degenerate** on the panel: small models deliver 0–17% correct, stronger ones 58–92%, with partial credit in between; 138 adversarially-hardened rollouts produced zero scorer disputes and zero exploits.
- Episode termination works: 83–100% of episodes ended with an explicit accepted submit; the 40K ceiling never bound.
- **Reasoning-replay is a real, model-dependent trainer knob.** On `devstral-2512`, not replaying prior-turn `reasoning_content` improved correct delivery by +0.36 (the preregistered whole-block bootstrap interval excludes zero on this fixed panel; paired discordants 4–0 over 11 blocks, exact sign test p = 0.125) at ~0.53× the provider tokens per correct delivery (the conditional bootstrap ratio interval excludes one; "P(dominates) = 0.98" is a bootstrap resample frequency, not a posterior). On `mistral-medium-2508` the observed direction reversed; the preregistered fixed-panel interval did not exclude zero. Treat replay policy as a model-specific factor to validate; this fixed panel does not establish a default.

**Deliberately not claimed:** nothing beyond this panel (four models, six tasks); no reinforcement-learning learnability claim (no policy was trained — that is what the environment is *for*); costs are measured, not adjudicated as practical.

## Sample `vf-eval` runs (raw transcripts included)

Standard `vf-eval` runs on the shipped zero-setup task `bank_recon_001`, with full rollout transcripts committed under [`outputs/evals/`](../outputs/evals/):

| Model | Rollouts | Reward | Turns | Submitted |
|---|---|---|---|---|
| `nvidia/nemotron-3-ultra-550b-a55b` | 3 | 1.0 / 1.0 / 1.0 | 7–8 | 3/3 |
| `nvidia/nemotron-3-ultra-550b-a55b` | 1 | 1.0 | 7 | 1/1 |

Reproduce with any OpenAI-compatible endpoint:

```bash
vf-eval beancount-ledger -m <model> --api-base-url <url> --api-key-var <KEY_VAR> \
  -n 1 -r 3 --max-tokens 8000 --save-results
```

For the capability *spread* (small models 0–17%, stronger 58–92%), see the sealed fixed-panel measurement above — a single strong model solving the demo task is expected, not news. (A local `gpt-oss-120b` contrast run scored 0.0 by failing to engage the tool loop at all — model-side empty turns, no environment fault; we kept it out of the committed samples to avoid confusion.)

## How to read this repository

| Path | What it is |
|---|---|
| `beancount_ledger/` | The environment: world generator (`graph/`) and the ten hand-authored worlds, 91 workflow tasks (`graph/worlds/`), candidate-ledger canonicaliser (`candidate/`), scorer (`reward.py`), tool loop (`beancount_ledger.py`). This is all the wheel ships. |
| `tests/` | The 27-suite battery, the exploit corpus (14 constructions over 13 families), the adversary loop, the liveness witness, the preflight, sealing and audit scripts; about 110 tracked files. Not shipped. |
| `reviews/` | Dated evidence: pre-registration, the sealed confirm1v4 schedule with its 143 executed cells, the pilot and budget records that preceded it, rendered arm tables, the release attestation, the reward-lattice audit and the audit receipt. The budget records were run on generator-8 worlds; under generator 9 the same selectors name different worlds, so nothing in them describes a world that is served today. Not shipped. |
| `outputs/evals/` | Raw `vf-eval` transcripts on the demo task. |

## Security and provenance
- Worlds are keyed (HMAC under the evaluator secret); public ids derive from public bytes only — nothing an agent observes regenerates an answer.
- The Hub artefact ships **no** goldens, no test suite, no provenance records, no secrets (verified per release: the wheel's file list is audited).
- Read tools accept only the eight declared names — never paths; symlinks, reparse points and oversized content are refused; agent input can never quarantine an evaluation.
- Dependencies are pinned exactly (`verifiers==0.3.1`, `openai==3.5.0`, pydantic/griffe/datasets/beancount pinned) because the model-facing tool schemas are generated through them; a bump moves the episode-contract digest and is loud, never silent.
- Versions: generator 9, identify 7, scorer contract 1, manifest schema 2, episode contract 2.

## Provenance of the numbers in this reference
`reviews/confirmatory_design.md` (pre-registration, dated corrections included), `reviews/schedule_confirm1v4.json` (the sealed experiment contract), `reviews/arms_confirm1v4.md` (the rendered table). The internal design-review log is retained outside the public release; public evidence and dated corrections are in the three review artifacts named above.
