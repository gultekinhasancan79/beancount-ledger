# Evaluation pack — cash application on fresh keyed instances

**For an external team that wants to evaluate its own models on this environment and produce a result
record that can be compared with ours.** Everything the pack refers to is either in this directory or
pinned by digest in `evidence_index.json`. Source described: package **0.3.0**, whose reference source
commit is `9d59c078eec91792b1d1a5983e724d6cf928fae6`. The pack itself lives in a later commit;
`frozen_declaration.json` names it as `pack_commit` once it is published.

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
| `frozen_declaration.json` | three parts. `portable`: every declared literal, the Unicode-independent semantic components, the runtime-independent census components, the parser and scorer-contract digests per pinned Unicode database, both episode-contract digests, the pinned library versions. `reference_runtime_attestation`: the reference runtime and the whole-freeze digest it produced. `describes`: package version, reference source commit, pack commit, the released wheel's digest, and the package tree digest with one digest per runtime file |
| `evidence_index.json` | the 158 files that make up the complete result records and release provenance, each with its sha256 and size: the 34 files the first index bound, the 117 recovered workspace files and 6 counterfactual artifacts of the generated-population screen, and `tests/observed_truth.py` |
| `check_pack.py` | verifies the portable declaration and the package bytes against the package in front of you (no secret needed) and, in a checkout, the evidence digests; reports your runtime's whole-freeze digest beside the reference's. **Run this first.** |
| `mint_and_serve.py` | mints the declared population under **your** evaluator key, signs **your** family manifest, serves every minted variant through the real door, and records every step durably as it goes |
| `freeze_selection.py` | pre-registers a screen's selection, execution order and complete arm from your serving record, before any model call, with its own digest |

The runner that executes model episodes (`tests/measure_budget.py`) is a repository tool, not a pack
file, because it is nearly five thousand lines of instrument with its own suite. Take it from the
pack's commit or later: the runner at the reference source commit still re-sent a rate-limited request
up to seven times, the loop this document says is gone. The wheel carries no runner.

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

## Runtime support: what is portable and what is not

The whole-freeze digest `b371a45a0186648e40c7aa18f03efb28` is the **reference runtime's**: CPython
3.12.12 on Windows AMD64, Unicode database 15.0.0, the runtime that minted the released population.
It folds the native runtime and the compiled predicate catalogue into itself, so it reproduces only
there; on Linux, or on CPython 3.11 or 3.13, it legitimately differs. What every runtime must
reproduce is the portable part of the declaration. `check_pack.py` demands all of it; `mint_and_serve.py`
demands the declared literals and the package's own self-consistency, and relies on `check_pack.py`
for the rest, which is why it runs first. Both compute your own whole-freeze digest, print it beside the
reference as `EQUAL` or `DIFFERENT`, and record it. On any other runtime a difference is a note. On the
reference runtime itself both demand equality, because there a difference means a different package.
Both refuse a Unicode database the pack does not pin. The manifest's own runtime
checks at the serving door are untouched. The repository's CI validates the pack on ubuntu
3.11/3.12/3.13 and windows 3.12 by running `check_pack.py` natively in its battery job; that job's log,
not this sentence, is the evidence for a runtime.

## Setup

1. Install the package into a fresh virtual environment, Python 3.11 to 3.13, from one of:
   - the Environments Hub entry `cangultekn/beancount-ledger` **once its 0.3.0 upload is visible**
     (as of 14 September 2026 the Hub carries 0.2.0, which has no installable generator; 0.3.0 is a
     new version, not a rebuilt 0.2.0);
   - the repository: `git clone`, check out the commit that carries this pack or any later one,
     `uv venv --python 3.12`, `uv pip install -e .` — this is also the only way to get the runner and
     the evidence files. The package bytes there are the reference source commit's; `check_pack.py`
     establishes that by tree digest, not by commit.
2. Copy this directory next to your work (it needs nothing else from the repository except for the
   evidence check). To verify a wheel install, run the copy from outside any checkout: inside one, the
   checkout's package shadows the wheel, and the printed import path says which was checked.
3. Run `python check_pack.py`. It prints one `PASS`/`FAIL` line per check, one `NOTE` line per thing
   it reports without judging, and exits non-zero on any `FAIL`. **Verified**: the portable declaration
   (declared literals, semantic and census components, the parser and scorer-contract digests for your
   interpreter's Unicode database, both episode-contract digests, library versions); the package tree
   digest over the logical text of the 71 runtime files, from wherever `beancount_ledger` imports, a
   changed file named; the installed version `0.3.0`; in a checkout, the 158 evidence digests, as a
   clean clone's LF bytes (a CRLF working copy fails as "line endings only", with the fix named);
   with `--wheel PATH`, the wheel's sha256 and every `RECORD` member against the installed files.
   **Reported**: your whole-freeze digest beside the reference's; the observed checkout commit beside
   the reference source commit and the pack commit; without `--wheel`, that the wheel was not checked.
   The runner and its suite are bound by the evidence index, separately from the package. A Unicode database the pack does not pin
   (14.0.0, 15.0.0 and 15.1.0 are pinned) is refused by name: an unverified runtime, not a passing one.
   `--record PATH` writes everything observed to a JSON file you can send back.
4. Provision your evaluator side, explicitly, in the environment of the process that will mint and
   serve — the pack scripts refuse to read or write `~/.piv/`:

   ```
   PIV_EVAL_SECRET=<hex, at least 16 bytes, generated by you, never shared, never in a prompt>
   PIV_KEY_ID=<any opaque rotation label, e.g. team-rotation-1>
   PIV_CASH_APPLICATION_MANIFEST=<a path outside any agent workspace, e.g. /srv/piv/cash_application_manifest.json>
   ```

5. Run `python mint_and_serve.py --per-stratum 1` (three groups, six variants, under a minute). Then
   `--all` for the whole population (96 groups; minutes). Every path it writes — `--out`, each file
   under it, the manifest — is resolved and refused under `~/.piv` before anything is created. It
   writes `run.json` as a start record first. After minting, before the manifest is signed or anything
   is served, it writes `census.json` with every group's every attempt (ordinal, stage, outcome, codes,
   witness, baseline, reading counts, component and content digests). It appends one fsynced line per
   variant to `serving.jsonl` the moment that episode ends, a failed check or an exception included and
   named. `serving.json` summarises that log; `run.json` is finalised last, or marked aborted with the
   exception named. It must print `PASS`: every declared group admitted, every variant served at
   reward 1.0 by a scripted golden delivery, under the authored task's episode contract. Only the
   portable freeze is demanded (a mismatch stops it before minting, exit 3); the whole-freeze digest
   is a `NOTE`.

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

For a **comparable result record**, run episodes through the repository runner from a checkout at the
pack's commit or later:

```
python tests/measure_budget.py --model <requested id> \
    --provider openrouter --base-url <OpenAI-compatible endpoint> --api-key-var <ENV VAR holding the key> \
    --selectors <selector> \
    --max-tokens 40000 --max-total-completion-tokens 40000 --temperature 0 --top-p 1 \
    --timeout 3600 --retries 0 \
    --screen <screen name> --selection-digest <digest from freeze_selection.py> \
    --planned-ordinal <n> --tag <screen name>
```

Every setting the arm binds is passed explicitly, because the runner's defaults are not the arm:
without `--max-tokens` the per-turn cap is 4,000 where the published rows record 40,000; without
`--provider` the row is labelled `nvidia` whatever the endpoint; without `--timeout` the request
timeout is 180 s where the next screen declares 3,600 s. A label outside the runner's preset table is
accepted only with `--base-url`; pass `--api-key-var` too, so row and arm record name the same
variable. No `--seed` means no seed is sent, and the arm record says so. SDK retries are fixed at 0
in the runner. `--retries 0` (the default) governs the pacing wrapper and framework re-runs together:
one request per turn, and a 429 is a terminal provider refusal recorded with its status, provider code, request id and rate-limit
headers. A runner older than the pack's commit re-sent a 429 up to seven times regardless of this
flag; take no rows with it.

One selector per invocation is the pattern the published screen used, so that a provider failure on
one cell cannot lose another. The runner writes a start record per cell to `<rows>.starts.jsonl`
before the first request, a terminal row for any failure, and a cell census `<rows>.cells.json`
rewritten after every cell, so a lost cell (start record and terminal row) and an unattempted one
(neither) are different objects in the data. A row records the endpoint, the provider label, the
requested and returned model ids, the provider requests it made, every response's usage, the per-turn
accounting, the arm settings, the episode-contract digest, and the stored-bytes and logical-text
digests of both delivered artifacts. A provider failure produces a durable `ATTEMPTED_UNSCORED` row,
never a crash and never a second request. `python tests/measure_budget.py --help` lists every flag.

## The arm record

The episode-contract digest covers the environment's budget (turns, token ceilings), not every client
setting, so equal episode-contract digests alone do not establish equal arms. The selection record's
`arm` block binds the rest: the per-turn cap (`--max-tokens`), the per-episode ceiling
(`--max-total-completion-tokens`), the turn budget, the replay policy, the sampling parameters
(temperature, top_p, model seed), the request timeout, the retry policy (SDK retries, fixed at 0;
pacing and framework retries, both governed by `--retries`) and the routing (provider label, base URL, and the NAME of the
key variable, never its value). It lists the runner flags it stands for, so an invocation is checked
against the record, not reconstructed from it. Every row records the same settings (`per_turn_cap`,
`max_total_completion_tokens`, `timeout`, `retries`, `sdk_retries`, `pacing_retries`,
`pacing_attempts_per_request`, `replay_policy`, `temperature`, `top_p`, `seed`, `provider`,
`endpoint`), and the runner's own identity (`runtime_head`, `execution_tree_digest`,
`instrument_identity_version`, `runtime_environment_digest`), so the runner is recorded on every row
separately from the package; a row whose values differ from the block is another arm. Screen 1's rows
record a 40,000 per-turn cap, a 180 s timeout, Alibaba Model Studio's endpoint and the label `nvidia`,
which was the runner's default and not the service; that is why the label is now declared. They
predate `sdk_retries`, `pacing_retries` and `pacing_attempts_per_request`, which the runner at the
pack's commit adds.

## Pre-registration: freeze before you call

```
python freeze_selection.py --serving <your serving.json> --screen <name> \
    --seed "<name>:<date>" --subjects <requested id> [<another id> ...] --per-stratum 2 \
    --timeout 3600 --provider-label openrouter --base-url <endpoint> --api-key-var <ENV VAR> \
    --out <name>.selection.json
```

The serving record is validated, not trusted: every row must carry `selector` and a boolean `served`;
every selector must parse as a declared member of the released population, in the package's own
spelling; a selector that appears twice, names another population or does not parse refuses the whole
record (exit 2, nothing written). A parent group is eligible only when both its variants have a served
row, exactly once each. The selection is drawn uniformly over the eligible groups of each mechanism
stratum, under a recorded seed that has nothing to do with any mint seed; the execution order is also
drawn. The record binds the serving record's bytes (sha256, size), the manifest identity it carries
(path, sha256, records signed), the population's declared identity as the package states it
(population, split-map, profile and gate-set digests, preflight contract) and the complete arm; the
self-digest covers all of it. Several subjects may share one draw and arm (`--subjects a b`), each as
its own model record. `--timeout` has no default. The routing flags default to screen 1's endpoint and
to the service label for it (`alibaba-model-studio`, not the `nvidia` its rows carry); pass yours, so
the record and the runner invocation agree. The record's paths (where the serving record and the
manifest were read from) are outside the self-digest, so the same draw over the same bytes has the same
digest wherever the checkout lives. Every result row of a later screen
carries the digest (`--selection-digest`) and the write-up quotes it; screen 1's rows predate that
flag. The same seed on the repository's own serving record reproduces the published draw exactly
(`fc-quarrymill` 4 and 1, `cr-pikestaff` 6 and 12, `ar-tenterhook` 22 and 24), which is how you can
check the procedure before trusting it; the self-digest differs from the published `321c9715...`
because the record now carries the arm and the bindings.

Rules the record is held to. The first seven held in outcome in the published screens, with one
qualification: screen 1's runner did not enforce the pacing bound in rule 1 (no request went past its
first attempt, but the instrument would have allowed up to seven). The last two are requirements from
the next screen on:

1. **One attempt per cell, no retries, temperature 0, fresh context per episode.** No retries means
   SDK retries 0, pacing retries 0 and framework retries 0: one request per turn.
2. **A missing outcome stays missing.** Report every count against the planned denominator. A
   provider refusal is `ATTEMPTED_UNSCORED`; a cell never reached is `UNATTEMPTED`; neither is a model
   failure and neither is refilled, re-run or substituted with another model.
3. **One arm per record.** Turn cap and token budgets are part of the episode-contract digest; the
   rest of the arm is bound by the selection record's `arm` block; rows under a different value of
   either are never pooled.
4. **Attribution by endpoint.** The serving service is the recorded endpoint; a driver or pacing label
   is not provider identity. Report requested id, returned id and `system_fingerprint` as captured.
5. **Consumption as reported.** Provider-reported tokens per row; an unrecorded cell's usage is
   `UNKNOWN`, never zero. Do not reconcile to a console's debits unless you actually did.
6. **No self-certification.** The subject model's outputs never adjudicate the subject's own cells. If
   you adjudicate, use models of other lineages, shown only the public files, under a pre-declared
   rule, as `reviews/cash_application_adjudication_2026-09-10/predeclared.md` did.
7. **Development split only.** The evaluation split is closed; a record that opened it is a different
   experiment and says so.
8. **One-cell invocations and durable failure records.** Every cell is its own runner invocation, with
   its start record, its terminal row on failure and its entry in the cell census.
9. **Daily limit.** OpenRouter's free tier for an account without purchased credits is 50 requests per
   day and 20 per minute, and failed requests count. A cell is launched only when at least 25 requests
   remain in the accounted daily allowance. One relaunch is permitted only for a documented platform
   daily-limit rejection of the episode's FIRST inference request, before any model response, with the
   HTTP status, error body, request id and rate-limit/reset headers preserved; otherwise an attempted
   cell stays missing.

## What a complete result record contains

The published generated-population screen is the worked example; its files are the pattern:

| part | published example |
|---|---|
| the frozen selection, with digest | `reviews/cash_screen_1_selection_2026-09-13.json` |
| one result row per attempted cell, unmodified | `reviews/budget_qwen3.7-max-2026-05-20_2026-09-13_cash_screen_1.json` |
| the start journal and cell census beside the rows (`<rows>.starts.jsonl`, `<rows>.cells.json`) | none yet: screen 1 predates them; required of every later screen |
| the per-cell disposition against the planned denominator | `reviews/cash_screen_1_retrospective_census_2026-09-13.json` |
| the delivered bytes of every scored cell | `reviews/cash_application_generated_screen_2026-09-13/workspaces/` |
| an executable rescore that rebuilds every published figure from the bytes | `…/rescore_cash_screen_1.py` and `.json`; a plain run rebuilds into a fresh directory and compares with the published record, and only `--write-record` rewrites it |
| the write-up, labelled by disposition, with its limits | `reviews/cash_application_generated_screen_2026-09-13.md` |

A row binds its deliverables by stored-bytes and logical-text digests and carries the episode-contract
digest, so anyone holding the bytes can re-score the application channel offline (`tests/observed_truth.py`
rebuilds the truth register from public evidence and is pinned by the scorer's own result digest). The
evidence index binds that whole dependency set: the recovered workspaces, the counterfactual artifacts
and `tests/observed_truth.py`, beside the records themselves. The ledger channel of a generated cell
replays only under the minting key: publish the bytes and say so.

## What has been measured so far, so you know what you are comparing with

| record | disposition | what it supports |
|---|---|---|
| `reviews/cash_application_generated_screen_2026-09-13.md` | **incomplete**, one subject, twelve planned cells; stated exactly below | nine scored rows; not a rate |
| `reviews/cash_application_six_variant_screen_2026-09-11.md` | incomplete descriptive screen on the authored variants, one subject | per-case observations, one rescored fixture |
| `reviews/cash_application_screen_2026-09-10.md` | three episodes on three authored variants, one subject | two complete deliveries, one register losing a field |
| `reviews/cash_application_adjudication_2026-09-10.md` | cold adjudication, two models of other lineages, five authored cases | the specified applications were reconstructed from the public files alone |
| `reviews/arms_confirm1v4.md` | fixed panel on the **bank** family: 4 models × 6 tasks × 3 arms × 2 replicates, 143 of 144 cells ran, 138 valid | the only multi-model study; a different task family |

The generated-population screen, as the review stated it: Screen 1 preserved nine scored rows. Its
tenth attempted cell has a retrospective disposition, not an original result row; two further cells
were unattempted. Recovered artifacts support offline replay of the application channel. The ledger
score is carried from the live observation and is not independently recomputed without the minting
key. One-cell invocations and durable failure records are requirements for subsequent screens.

None of these establishes a population success rate, difficulty, training utility, or a practising
accountant's sign-off; the accounting of the newest company-months carries a dated AI plausibility
review only.

## Reporting back

Open an issue on the repository with: the verification record `check_pack.py --record PATH` wrote
(your runtime and whole-freeze digest beside the reference's, the package tree digest, the installed
version, the observed commit, the wheel result if you passed `--wheel`, every check and note), your
`run.json` (it names where the package resolved from and under what runtime), the selection record's
digest, the disposition counts against the planned denominator, and the result rows with their start
journal and cell census. A scorer disagreement is the most useful report of all: give the task's
public id, the delivered bytes and the expected versus actual outcome.

## Limits of the pack itself

- It describes one package version and one reference source commit. `check_pack.py` verifies the
  package bytes and the version; it reports the commit it observes and verifies no commit. A package
  with the same bytes at another commit passes, and the record says which commit it saw.
- Your census will differ from ours in public ids, attempt ordinals and, possibly, exhaustion: the
  published census (96 admitted, 98 attempts, 0 exhausted) is a property of our key's draw. As a
  second data point, the pack's scripts as they then were ran before publication under a throwaway
  key on 14 September 2026: 96 of 96 admitted, 97 attempts (one `RENDER-POSTING-COLLISION` refusal,
  where ours had two `DRAW-LAYOUT-REFUSED`), 0 exhausted, 192 of 192 served, 192 distinct public ids
  with no overlap with the published ones, in three and a half minutes on a laptop. Same shape,
  different worlds, as intended.
- The runner is a checkout tool. Results produced by any other client are still results, but they are
  not the published record's shape and cannot be compared cell for cell.
- Nothing here has been run by an external team yet. The first such run is the test of this pack.
