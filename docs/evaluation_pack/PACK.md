# Evaluation pack — cash application on fresh keyed instances

**For an external team that wants to evaluate its own models on this environment and produce a result
record that can be compared with ours.** Everything the pack refers to is either in this directory or
pinned by digest in `evidence_index.json`. Source described: package **0.3.0**, commit
`9d59c078eec91792b1d1a5983e724d6cf928fae6` (`frozen_declaration.json` carries the full identities).

What the environment claims, stated exactly and unchanged from the release:

> A versioned, keyed cash-application generator with a frozen development population, deterministic
> accounting checks, golden-artifact validation and signed-manifest serving under the recorded
> repository runtime. No model performance, difficulty, training benefit or generalization beyond the
> development templates has been established.

That sentence is the whole claim. This pack adds no claim; it gives you the means to make your own
measurement, under rules that keep it comparable with the records already published.

## Contents

| file | what it is |
|---|---|
| `PACK.md` | this document |
| `frozen_declaration.json` | the frozen identities: family freeze digest and every declared literal, the Unicode-independent semantic components, the parser and scorer-contract digests per Unicode database, both episode-contract digests, pinned library versions, the 0.3.0 wheel digest |
| `evidence_index.json` | the 34 files that make up the complete result records and release provenance, each with its sha256 and size |
| `check_pack.py` | verifies the declaration against the package in front of you (no secret needed) and, in a checkout, the evidence digests. **Run this first.** |
| `mint_and_serve.py` | mints the declared population under **your** evaluator key, signs **your** family manifest, serves every minted variant through the real door, writes your census |
| `freeze_selection.py` | pre-registers a screen's selection and execution order from your serving record, before any model call, with its own digest |

The runner that executes model episodes (`tests/measure_budget.py`) is a repository tool, not a pack
file, because it is nearly five thousand lines of instrument with its own suite. A checkout at the declared commit
has it; the wheel does not.

## Three ways to evaluate, and what each one compares

**A. The authored tasks (no secret).** Eleven authored cash-application tasks (`cash_application_001`
to `011`) and 95 legacy bookkeeping tasks ship in the wheel and serve with no evaluator secret. They
are the same bytes for you and for us, so results on them are directly comparable with the published
screens. They are public demonstrations: assume any model may have seen them.

**B. Fresh keyed instances of the released development population (your secret).** The generator, the
population declaration and the admission battery ship in the wheel. Under your evaluator key the 96
declared parent groups draw **your** worlds: same declaration, same templates, same admission
contract, different accounting facts, different public ids. This is the pack's purpose. Results here
compare with ours at the level of the declaration, the profile, the gate set, the scorer contracts and
the episode contract, all of which `check_pack.py` verifies, and at the level of census shape. They do
not compare world for world.

**C. Our worlds.** The nine cells of the published generated-population screen were minted under our
key. They are reproducible only by the holder of that key, and the key is not shared. What is shared
is every public and delivered byte of those cells and an executable rescore, under
`reviews/cash_application_generated_screen_2026-09-13/`.

The evaluation split (`fc-harrowfield`, `cr-oysterbank`, `ar-coldharbour`) is sealed and declared by
no released population. No selector spells it and `freeze_selection.py` cannot choose it.

## Setup

1. Install the package into a fresh virtual environment, Python 3.11 to 3.13, from one of:
   - the Environments Hub entry `cangultekn/beancount-ledger` **once its 0.3.0 upload is visible**
     (as of 14 September 2026 the Hub carries 0.2.0, which has no installable generator; 0.3.0 is a
     new version, not a rebuilt 0.2.0);
   - the repository at the declared commit: `git clone`, `git checkout 9d59c07`, `uv venv --python 3.12`,
     `uv pip install -e .` — this is also the only way to get the runner and the evidence files.
2. Copy this directory next to your work (it needs nothing else from the repository except for the
   evidence check).
3. Run `python check_pack.py`. It must print `PASS` naming freeze digest
   `b371a45a0186648e40c7aa18f03efb28`. A `FAIL` means the package is not the frozen generator, or your
   interpreter's Unicode database is one the pack does not pin (14.0.0, 15.0.0 and 15.1.0 are pinned;
   any other is an unverified runtime for this pack, not a passing one).
4. Provision your evaluator side, explicitly, in the environment of the process that will mint and
   serve — the pack scripts refuse to read or write `~/.piv/`:

   ```
   PIV_EVAL_SECRET=<hex, at least 16 bytes, generated by you, never shared, never in a prompt>
   PIV_KEY_ID=<any opaque rotation label, e.g. team-rotation-1>
   PIV_CASH_APPLICATION_MANIFEST=<a path outside any agent workspace, e.g. /srv/piv/cash_application_manifest.json>
   ```

5. Run `python mint_and_serve.py --per-stratum 1` (three groups, six variants, under a minute). Then
   `--all` for the whole population (96 groups; minutes). It writes `census.json`, `serving.json` and
   `run.json` under `--out` and must print `PASS`: every declared group admitted, every variant served
   at reward 1.0 by a scripted golden delivery, under the authored task's episode contract.

   Keep `census.json` and the manifest evaluator-side. The census binds enumerable selectors to
   public-content digests. It never goes into an agent's workspace, a prompt, or a dataset a model
   reads.

## Running episodes

For authored tasks, any `verifiers` client works:

```
uv run vf-eval beancount-ledger --env-args '{"task_id": "cash_application_001"}'
```

For generated tasks the same three environment variables must be present in the serving process,
and the selector is evaluator-side: `cash_application:<population>:<template>:<index>:<a|b>`, exactly
as `serving.json` lists it. The selector never reaches the model; the model sees a public task id.

For a **comparable result record**, run episodes through the repository runner from a checkout:

```
python tests/measure_budget.py --model <requested id> --base-url <OpenAI-compatible endpoint> \
    --api-key-var <ENV VAR holding the key> --selectors <selector> \
    --temperature 0 --retries 0 --max-total-completion-tokens 40000 \
    --screen <screen name> --selection-digest <digest from freeze_selection.py> \
    --planned-ordinal <n> --tag <screen name>
```

One selector per invocation is the pattern the published screen used, so that a provider failure on
one cell cannot lose another. The runner records the endpoint, the requested and returned model ids,
every response's usage, the per-turn accounting, the episode-contract digest, and the stored-bytes and
logical-text digests of both delivered artifacts. A provider failure produces a durable
`ATTEMPTED_UNSCORED` row with the HTTP status, provider error code and request id, never a crash and
never a retry. `python tests/measure_budget.py --help` lists every flag; the settings above are the
published screen's, and rows taken under other settings are another arm.

## Pre-registration: freeze before you call

```
python freeze_selection.py --serving <your serving.json> --screen <name> \
    --seed "<name>:<date>" --subject <requested id> --per-stratum 2 --out <name>.selection.json
```

The selection is drawn uniformly over the parent groups whose both variants served, per mechanism
stratum, under a recorded seed that has nothing to do with any mint seed; the execution order is
also drawn; the record carries its own digest, which every result row and the write-up quote. The
same seed on the repository's own serving record reproduces the published screen's draw exactly
(`fc-quarrymill` 4 and 1, `cr-pikestaff` 6 and 12, `ar-tenterhook` 22 and 24), which is how you can
check the procedure before trusting it.

Rules the record is held to, all of them already applied to the published screens:

1. **One attempt per cell, no retries, temperature 0, fresh context per episode.**
2. **A missing outcome stays missing.** Report every count against the planned denominator. A
   provider refusal is `ATTEMPTED_UNSCORED`; a cell never reached is `UNATTEMPTED`; neither is a model
   failure and neither is refilled, re-run or substituted with another model.
3. **One arm per record.** Turn cap and token budgets are part of the episode-contract digest; rows
   under different budgets are never pooled.
4. **Attribution by endpoint.** The serving service is the recorded endpoint; a driver or pacing label
   is not provider identity. Report requested id, returned id and `system_fingerprint` as captured.
5. **Consumption as reported.** Provider-reported tokens per row; an unrecorded cell's usage is
   `UNKNOWN`, never zero. Do not reconcile to a console's debits unless you actually did.
6. **No self-certification.** The subject model's outputs never adjudicate the subject's own cells. If
   you adjudicate, use models of other lineages, shown only the public files, under a pre-declared
   rule, as `reviews/cash_application_adjudication_2026-09-10/predeclared.md` did.
7. **Development split only.** The evaluation split is closed; a record that opened it is a different
   experiment and says so.

## What a complete result record contains

The published generated-population screen is the worked example; its files are the pattern:

| part | published example |
|---|---|
| the frozen selection, with digest | `reviews/cash_screen_1_selection_2026-09-13.json` |
| one result row per attempted cell, unmodified | `reviews/budget_qwen3.7-max-2026-05-20_2026-09-13_cash_screen_1.json` |
| the per-cell disposition against the planned denominator | `reviews/cash_screen_1_retrospective_census_2026-09-13.json` |
| the delivered bytes of every scored cell | `reviews/cash_application_generated_screen_2026-09-13/workspaces/` |
| an executable rescore that rebuilds every published figure from the bytes | `…/rescore_cash_screen_1.py` and `.json` |
| the write-up, labelled by disposition, with its limits | `reviews/cash_application_generated_screen_2026-09-13.md` |

A row binds its deliverables by stored-bytes and logical-text digests and carries the episode-contract
digest, so anyone holding the bytes can re-score the application channel offline (`tests/observed_truth.py`
rebuilds the truth register from public evidence and is pinned by the scorer's own result digest). The
ledger channel of a generated cell replays only under the minting key: publish the bytes and say so.

## What has been measured so far, so you know what you are comparing with

| record | disposition | what it supports |
|---|---|---|
| `reviews/cash_application_generated_screen_2026-09-13.md` | **incomplete**: 9 scored, 1 attempted-unscored (provider 403), 2 unattempted, of 12 planned; one subject | seven complete successes and two application-only partials (in-period invoices omitted from the closing register; the counterfactual with only those rows added scores 1.0). Not a rate. |
| `reviews/cash_application_six_variant_screen_2026-09-11.md` | incomplete descriptive screen on the authored variants, one subject | per-case observations, one rescored fixture |
| `reviews/cash_application_screen_2026-09-10.md` | three episodes on three authored variants, one subject | two complete deliveries, one register losing a field |
| `reviews/cash_application_adjudication_2026-09-10.md` | cold adjudication, two models of other lineages, five authored cases | the specified applications were reconstructed from the public files alone |
| `reviews/arms_confirm1v4.md` | fixed panel on the **bank** family: 4 models × 6 tasks × 3 arms × 2 replicates, 143 of 144 cells ran, 138 valid | the only multi-model study; a different task family |

None of these establishes a population success rate, difficulty, training utility, or a practising
accountant's sign-off; the accounting of the newest company-months carries a dated AI plausibility
review only. The generated-population screen's decomposition is post-run analysis because its live
breakdown capture failed; the rewards themselves are live and preserved.

## Reporting back

Open an issue on the repository with: the pack's freeze digest as `check_pack.py` printed it, your
`run.json` (it names where the package resolved from and under what runtime), the selection record's
digest, the disposition counts against the planned denominator, and the result rows. A scorer
disagreement is the most useful report of all: give the task's public id, the delivered bytes and the
expected versus actual outcome.

## Limits of the pack itself

- It describes one commit and one package version. `check_pack.py` fails on any other.
- Your census will differ from ours in public ids, attempt ordinals and, possibly, exhaustion: the
  published census (96 admitted, 98 attempts, 0 exhausted) is a property of our key's draw. As a
  second data point, the pack's own scripts were run before publication under a throwaway key on
  14 September 2026: 96 of 96 admitted, 97 attempts (one `RENDER-POSTING-COLLISION` refusal, where
  ours had two `DRAW-LAYOUT-REFUSED`), 0 exhausted, 192 of 192 served, 192 distinct public ids with
  no overlap with the published ones, in three and a half minutes on a laptop. Same shape, different
  worlds, as intended.
- The runner is a checkout tool. Results produced by any other client are still results, but they are
  not the published record's shape and cannot be compared cell for cell.
- Nothing here has been run by an external team yet. The first such run is the test of this pack.
