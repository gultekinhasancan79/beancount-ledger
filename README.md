# beancount-ledger

Bank reconciliation and month-end close on a [Beancount](https://beancount.github.io/) ledger, scored **deterministically** — the trial balance either ties or it does not; no LLM judge anywhere in the reward path.

The agent is a bookkeeper for a small trading company. It receives a workspace of public files — the ledger, a bank statement, a chart of accounts, counterparty registers, a prior-period archive and the accounting policy — finds what is missing, wrong or duplicated, writes the corrected ledger back, and submits. Every discrepancy is planted by a generator whose world graph is the single source of truth, so the scorer knows the exact correct books and pays exact partial credit.

### Overview
- **Environment ID**: `beancount-ledger`
- **Short description**: Multi-turn tool-use bank reconciliation with a deterministic, exploit-hardened reward
- **Tags**: `accounting`, `tool-use`, `multi-turn`, `train`, `eval`

### Quickstart

```bash
uv run vf-eval beancount-ledger          # the shipped hand-authored task, works out of the box
```

```python
import beancount_ledger

env = beancount_ledger.load_environment()            # default: the hand-authored task "bank_recon_001"
env = beancount_ledger.load_environment("train:7")   # a generated task (requires the operator setup below)
```

Generated tasks are **keyed and manifested**: each world derives from an HMAC under an evaluator secret (`PIV_EVAL_SECRET` or `~/.piv/eval_secret`, ≥16 bytes), and production serving admits only selectors recorded in a signed release manifest written by the preflight (`tests/preflight_manifest.py`, two-phase: offline gates on every minted world, then every record verified through the real serving door). Without the secret and manifest, a generated selector is refused with a named reason — the refusal path is structural: installed copies of this package **cannot** enable the development override (`PIV_DEV_UNMANIFESTED` is ignored outside the repository's own test entry points; witnessed from an installed wheel).

### Datasets
- **Primary**: generated worlds, selectors `train:<n>`, `eval:<n>`, `train:<n>:hard` (n < 100,000). The released population is preflighted 1,400/1,400 (1,000 train / 200 eval / 200 hard).
- **Shipped**: one hand-authored task (`bank_recon_001`) usable with no secret, for smoke tests and demos.
- Each world is a projection of a private fact graph; everything the scorer requires is derivable from the mounted files or stated in `policy.md`. Ledgers are 7–14 KB; the public observation contract is eight named files, nothing else.

### Task
- **Type**: multi-turn tool use, six tools: `list_files`, `read_file`, `grep`, `run_beancount`, `write_ledger`, `submit`.
- **Observation contract**: `ledger.beancount` is returned **whole in one call** (exactly as the scorer reads it, LF-normalized; envelope 48,000 bytes, enforced before the episode); other files come in numbered 200-line slices; one complete ledger read per revision (repeats get a bounded receipt); every reply is byte-capped and the episode carries an aggregate observation budget (768,000 bytes) — a cost bound, never a reward penalty.
- **Episode contract** (version 2, digest `152dbbaf…`, carried on every rollout): 25 turns; calls on the final turn are not executed, so submit by turn 24 — **or** let the limit end the episode: the latest successfully written ledger is scored either way. A total ceiling of 40,000 completion tokens (including hidden reasoning) is disclosed in the prompt and enforced exactly, per request. Three consecutive no-tool turns end the episode.
- **Rubric**: parse-gated (an unloadable ledger scores 0), then deterministic components — target account balances hit, planted discrepancies resolved as their own dated entries — minus penalties for damaging existing records, fabricating entries or inventing accounts. Partial credit is machine-computed; every reward claim in our test battery names its oracle, and the exploit corpus's oracle is semantic entitlement, independent of the scorer.

### What the fixed-panel measurement showed (evidence, not a recommendation)

A preregistered, sealed experiment (4 Mistral open-weight models × 6 tasks × 3 episode-contract arms × 2 replicates; 144 scheduled cells, 143 run, 138 valid, five named exogenous failures, one unrun cell — the full table with censuses and failure evidence is `reviews/arms_confirm1v4.md`):

- The reward is **capability-sensitive and non-degenerate** on the panel: small models deliver 0–17% correct, stronger ones 58–92%, with partial credit in between; 138 adversarially-hardened rollouts produced zero scorer disputes and zero exploits.
- Episode termination works: 83–100% of episodes ended with an explicit accepted submit; the 40K ceiling never bound.
- **Reasoning-replay is a real, model-dependent trainer knob.** On `devstral-2512`, not replaying prior-turn `reasoning_content` improved correct delivery by +0.36 (the preregistered whole-block bootstrap interval excludes zero on this fixed panel; paired discordants 4–0 over 11 blocks, exact sign test p = 0.125) at ~0.53× the provider tokens per correct delivery (the conditional bootstrap ratio interval excludes one; "P(dominates) = 0.98" is a bootstrap resample frequency, not a posterior). On `mistral-medium-2508` the observed direction reversed; the preregistered fixed-panel interval did not exclude zero. Treat replay policy as a model-specific factor to validate; this fixed panel does not establish a default.

**Deliberately not claimed:** nothing beyond this panel (four models, six tasks); no reinforcement-learning learnability claim (no policy was trained — that is what the environment is *for*); costs are measured, not adjudicated as practical.

### Security and provenance
- Worlds are keyed (HMAC under the evaluator secret); public ids derive from public bytes only — nothing an agent observes regenerates an answer.
- The Hub artefact ships **no** goldens, no test suite, no provenance records, no secrets (verified per release: the wheel's file list is audited).
- Read tools accept only the eight declared names — never paths; symlinks, reparse points and oversized content are refused; agent input can never quarantine an evaluation.
- Dependencies are pinned exactly (`verifiers==0.3.1`, `openai==3.5.0`, pydantic/griffe/datasets/beancount pinned) because the model-facing tool schemas are generated through them; a bump moves the episode-contract digest and is loud, never silent.
- Versions: generator 8, identify 7, scorer contract 1, manifest schema 2, episode contract 2.

### Provenance of this README's numbers
`reviews/confirmatory_design.md` (pre-registration, dated corrections included), `reviews/schedule_confirm1v4.json` (the sealed experiment contract), `reviews/arms_confirm1v4.md` (the rendered table). The internal design-review log is retained outside the public release; public evidence and dated corrections are in the three review artifacts named above.
