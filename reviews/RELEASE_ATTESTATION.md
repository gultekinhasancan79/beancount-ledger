# Release attestation — beancount-ledger v0.1.0 (2026-09-01)

## Identities
- tag target commit: `107a948bf5dadae903f184add5a8e4f2afc34ece` (tree `8a50c27a2da122cb228d4498481e470931746481`), tracked working tree clean
- sealed execution commit (confirm1v4 instrument): `8e0770e02ed2c6be68374b47ed6fb54f16bce727`
- post-run analysis/render lineage: `d4ba5f1` (tool_call_chars correction) .. `107a948` (T52/T53 report corrections) — distinct from the executed instrument, by design (Codex T52 Q8/T53 §8)

## Artifacts (built from this clean checkout)
- wheel `beancount_ledger-0.1.0-py3-none-any.whl`: sha256 `67e8cd64770e19c04f095cfc8e777ceedb5bf023d32cbbbf8737ebcece858262`, 42 files; RECORD sha256 `026f61af8ab8d6b3152aa997fd5d9b903c998d2dcc1c906c90b83b304762884a`
- sdist `beancount_ledger-0.1.0.tar.gz`: sha256 `7de63f2b5286773007132cf50cd5356b1823b5e0d01962bf2f064b2973896574`, 43 files
- audit: no tests/, no goldens, no reviews/, no secrets in either artifact
- build: uv build (hatchling backend), python 3.12.12
- license: Apache-2.0 (SPDX), LICENSE sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Contracts and versions
- episode contract: version 4, digest `e8b8753de3e7ce1f10d4ddc8470589128b8b9b8e15fd67bfeca5102f107ad866` (2026-09-08; version 3 was `b16d726ac263…`, version 2 `152dbbaf80a1…`). Deliberately NOT in the manifest's `versions()`, which binds world semantics only.
- component versions: `{'generator': 8, 'identify': 7, 'scorer_contract': 1, 'renderer': 1, 'task_contract': 1, 'manifest_schema': 2, 'preflight_contract': 1, 'gate_set': 'e2f26ab5cdf60d53'}`
- episode contract v3, digest `b16d726ac2637486c549c3a2e94ede4da21cccc4be4e9410cb6e081c875ccba8`
- episode contract v2, digest `152dbbaf80a1f761d42d5b94139fd64c320f0810cbbe4855c7cb1cc0766fea59`
- replay contract v1: A/B1 `180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed`, B2 `29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0`
- production manifest: rotation-selected file sha256 `06800e0308658c5c9559ba51c16e766009462947726a917bf60ab527a099996e`; preflight 1400/1400 (phase 1 offline gates AND phase 2 signed-manifest serving door); the secret never appears here
- `parse_policy_digest` and `scorer_contract_digest` (and, per task, `task_contract_digest` / `environment_digest`, which embed them) are scoped to the runtime's Unicode database version, because `candidate/canonical.parse_policy_view()` records `unicodedata.unidata_version` as part of the parse policy's identity — deliberately, since a Python upgrade can change what Unicode accepts and how it canonicalises. On CPython 3.12 (Unicode 15.0.0): `parse_policy_digest` = `623ebaf29e32250d4d7f4aee98e30da6feea015ce6d3daa8ac4f1a3814dbc6a0`, `scorer_contract_digest` = `20ca7fb33fb1918d4bd9ac8954e9e3336ae8aa83b8cdfeeb8e134649523f1efa`. On CPython 3.11 (Unicode 14.0.0): `parse_policy_digest` = `f06b3513de395193cb0eb437be28ca63b6fd4830c9cb79689e440d21d84950bd`, `scorer_contract_digest` = `d1b7131ad316962490fcec637ba17acf3ac1d2f4e0c69171e041622b45cac683`. On CPython 3.13 (Unicode 15.1.0): `parse_policy_digest` = `9f39ade4bcf5bc9ee174995bd7a2765e0009894d90167fbaee5a5b3c1d0a70ca`, `scorer_contract_digest` = `3f12c01c905d62547fc8f156221ec587836e7f3615e61b1c24b0b184e5f2d5fb`. Everything else that was frozen at release — the 95 tasks' public bytes, `candidate/committed.py`'s bytes, and the contract-4 episode view — is unaffected and identical on all three interpreters; all three rows are pinned in `tests/legacy_freeze.json`, each carrying a `provenance` block that says whether it was observed natively or derived by substituting the version string, and where a runtime shipping that database confirmed it. A Unicode database the fixture does not pin FAILS the freeze; it is not accepted on the strength of its own digests (2026-09-10). The 15.1.0 row was derived on CPython 3.12 and then checked against a native CPython 3.13.11 (Windows) run of the whole battery (34/34); that run is not archived here, and anyone can repeat it -- build a CPython 3.13 venv, `uv pip install -e .`, `python tests/run_all.py`, and the freeze compares the 15.1.0 row strictly or fails. The battery matrix in `.github/workflows/ci.yml` covers CPython 3.11, 3.12 and 3.13 natively (ubuntu 3.11/3.12/3.13, windows 3.12) and runs on every push to main, every v* tag, and every pull request — so its ubuntu 3.13 job has not run yet and first compares the 15.1.0 row when this branch is opened as a pull request or merged to main. `tests/test_legacy_freeze.py` parses that workflow and fails if either file's account of when CI runs stops matching its triggers or its interpreters.

## Evidence files (sha256)
- reviews/confirmatory_design.md: `c0659a48124b84025591211f246ba2d9dc0af72d98d1b909754dfcc0d099266c`
- reviews/schedule_confirm1v4.json: `280a46108d82b348a6d0e798d223a322c664644ab1f91b91a883ffad34f5b494`
- reviews/arms_confirm1v4.md: `ede6960192514a3f367e01655571a9e621253c1e8375515906a6c89d10acddef`
- reviews/release_lock.txt: `194ae89253ce327a55d4476bd0ce8d346dd413b3331b54cd8a72a5e2304c6ee2`
- reviews/submission_texts.md: `83cf9618ed6e196fed18ab77cbe81023c5bc94ace97e703292d44642af95db7a`
- README.md: `6e87615f7b596cde9ef30f8601098178483dc5b717af1ef07d37958cccbc875c`
- LICENSE: `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

### Errata to the evidence hashes (2026-09-06)
- The values above for `reviews/schedule_confirm1v4.json` and `reviews/arms_confirm1v4.md` were computed on CRLF working copies on Windows. The bytes git stores (`.gitattributes` normalises to LF) hash to `a5bc3895f52889b162d5519adea91d8e02b4c6b23d6f8faeab94f6476e1edf84` (schedule) and `7712ea7c7b025ce28b84e0ec2c6cee12625aed695a50bdaccb59aa442b501048` (arms table); those are the values a fresh clone reproduces. `reviews/confirmatory_design.md` (`c0659a48124b84025591211f246ba2d9dc0af72d98d1b909754dfcc0d099266c`), `release_lock.txt`, `README.md` and `LICENSE` were already LF.
- The schedule's sealed `analysis_plan_sha256` (`c3c96b1b571d0412d7a881facb8a2948455eef2037263f5d8a6b48c01b9482a5`) is the hash of `confirmatory_design.md` as sealed on 2026-08-30, BEFORE its dated "Post-run corrections" section was appended; the current file therefore hashes differently by design. The sealed value is the pre-registration identity; the corrections section is outcome-independent and is the only later change.
- `reviews/submission_texts.md` was a marketing draft, not evidence; it was removed from the repository on 2026-09-06 and its line above is void.
- The commit ids in "Identities" (`107a948…`, `8e0770e…`, `d4ba5f1…`) name objects of the history as it stood on 2026-09-01. On 2026-09-04 the history was rewritten to purge `tests/adversary_out/` and a stray `render_out.html` from every commit, so those ids no longer resolve. The tag `v0.1.0` now points at `c79dd41d7bc3bbb579fcfacff743ab64a36d19d0` (tree `8532eac448c0b52824b6a4eb23eede5aea6f40a6`): the same release content minus the purged files. The wheel and sdist hashes above are unaffected (neither artefact ever contained the purged files).

## Panel census (confirm1v4, INCOMPLETE, as rendered)
- 144 scheduled = 143 exactly-matched rows + 1 unrun + 0 execution-integrity
- 143 = 138 valid + 5 exogenous provider-failed + 0 instrument-invalid + 0 other
- the unrun cell: mistral / ministral-14b-2512 / eval:5 / A / replicate 2 (planned ordinal 101)

## Suites at this commit
- tests/run_all.py: all 26 suites pass (incl. test_measure_budget and the deterministic liveness witness 6/6; sentinel extension 23/23 ran pre-tag)
- release-gate sweeps: generator 2,100 seeds clean; differential 330 selectors 0 violations; exploit corpus 0 gaps; fresh-family adversary 0 gaps; blind review 9/9 recall / 0 false alarms

## Control-round raw evidence
The raw provider outputs of the fresh-family adversary (tests/adversary_out/) are retained OUTSIDE the tagged source; their summarized results are in this attestation and the committed review artifacts. The blind-review artifacts (nemotron-super full, minimax partial) ARE committed.

---

# Branch attestation — feat/dense-rewards, GENERATOR_VERSION 9 (2026-09-05)

Not a release. What the dense-plan generator (commit `a149060`, "Dense plans: five to eight planted items a world") was checked against before the user decides on merge and manifest promotion. The tag target above stays the shipped state.

## Contracts and versions
- component versions: `{'generator': 9, 'identify': 7, 'scorer_contract': 1, 'renderer': 1, 'task_contract': 1, 'manifest_schema': 2, 'preflight_contract': 1, 'gate_set': 'e2f26ab5cdf60d53'}` — only the generator moved; scorer, gates and contracts are the release's
- episode contract 5 / shape `piv.episode-contract/3`, digest `b11bc1acf02b7e08c9cea7d42e73b7970756bd9a979b3134c9049e76e6571b9f` (2026-09-09), the **cash-application profile only**: a seventh tool `write_cash_application`, eleven observed public files instead of eight (`open_items.csv`, `remittance_advice.csv`, `credit_notes.csv`), a second deliverable `cash_application.json` (schema `piv.cash-application/1`, 16,000-byte / 400-line envelope, write-only, optional at submit and required for `complete`), that register's own phase machine and revisions, submit binding the exact latest revision of both artifacts, and the scoring composition `total = L x A` over engines `candidate/1`, `application/1`, `composite/1`. Contract **4** is PRESERVED byte for byte for the 95 shipped tasks — digest `e8b8753de3e7ce1f10d4ddc8470589128b8b9b8e15fd67bfeca5102f107ad866`, unchanged — because they were measured under it; the two views are dispatched by episode profile and both digests are pinned in `tests/test_episode_contract.py`, whose checks are parameterised over the profiles. Like contract 4, deliberately NOT in the manifest's `versions()`. The five `cash_application_001..005` ids are served from `graph/worlds/REGISTRY` with no evaluator secret; no model has been run on them yet, so this bullet attests the contract and the battery, not any measured difficulty. **[That last clause is the statement of 2026-09-09, preserved here as dated history. It was true when written; it is no longer. What has since been run is recorded in the MEASUREMENT bullet below, and this bullet still attests the contract and the battery — the measurement attests neither difficulty nor a failure rate.]**
- CORRECTION (2026-09-10), the same day: the commit that put the family live claimed — in a source comment and in its own message — that a reader knowing nothing about registers still parses the family's `delivery.json`. It does not. `DeliveryReceipt` (frozen with `candidate/1`) reads the top level by EXACT KEY SET and raises on the extra `application` member; only a reader that pops that member first parses it. `tests/measure_budget.bind_artifact` — the M2 instrument round 12 §6 names for the family's own measurement — was using the frozen reader and swallowing the exception, so every cash-application rollout, a reward-1.0 one included, was recorded as `ARTIFACT_MISMATCH: delivery.json unreadable`. No model episode had been run on the family, so no archived row carries the false diagnosis. Fixed: `bind_artifact` reads through the scorer's own `_read_publication`, and reports the SECOND deliverable's binding beside the ledger's (`application` BOUND / NO_ARTIFACT / ARTIFACT_MISMATCH, `application_status`, `application_revision`, the register's own digests), absent entirely on a legacy row. `tests/test_measure_budget.py` (78 checks, was 75) now covers a family rollout in all three register states, pins that the frozen reader still refuses the family manifest, and pins that a legacy row gains no key and its `delivery.json` is still byte-for-byte `DeliveryReceipt.to_json()`. In the same repair the model-facing-reply guard in `tests/test_episode_contract.py` was extended to `write_cash_application` and `_application_report` and parameterised over both profiles — nothing was found wrong behind it — and the `--manual` sweeps of `tests/audit_receipt.py` and `tests/reward_lattice_audit.py` were scoped to the 95 legacy ids, since both attest `candidate/1` alone and the family's reward is `composite/1`'s `L x A`.
- CORRECTION (2026-09-10), later the same day: the repair above fixed the M2 instrument's ARTIFACT binding for the family but left the same file's CONTRACT PROVENANCE legacy-only, so a family row stated a contract it had not run. Three places, all in `tests/measure_budget.py`: `episode_contract_digest_declared` came from the module-level `episode_contract_digest(ceiling)`, whose profile argument DEFAULTS to legacy (it is also what a quarantined cell falls back to, and what `schedule_arms.contract_expectations` admits rows on, so a quarantined family cell would have been admitted or rejected against contract 4); `episode_contract_version` came from the module constant `EPISODE_CONTRACT_VERSION`, permanently 4, so a family row read "contract 4" beside a contract-5 digest; and `prompt_schema_digest` was computed once from an UNSELECTED default environment on the written claim that the tool surface is fixed at six tools — false since the family, which serves seven and a different system prompt. Again no model episode had been run on the family, so no archived row carries the false provenance, and no legacy row moved: the legacy profile resolves the same digest, the same version and the same prompt-schema digest as before, which `tests/test_measure_budget.py` now pins from both sides. Fixed: all three resolve on the environment the cell actually loaded (`env.episode_contract_digest()`, `episode_contract_version(env.profile)`, `compute_prompt_schema_digest(env_mod, env=env)`), the resolved version and profile are requested from state (`piv_episode_contract_version`, `piv_episode_profile`) so a completed row's three provenance fields all come from one place, every row now carries `episode_contract_profile`, the run summary reports the digests its rows actually carry rather than one computed up front, and the false docstring claim is retracted in place. The mirror on the schedule side is closed too: `schedule_arms.build_experiment_contract` resolves the sealed digest and version under the profile its selectors serve, seals that profile beside them, and REFUSES to seal a schedule mixing profiles (one admission digest cannot be right for both); `tests/startup_witness.py` rechecks both under the sealed profile, treating a schedule sealed before the field existed as legacy. `tests/test_measure_budget.py` is 82 checks (was 78): a family row states contract 5 and the family digest in both digest fields, a legacy row states contract 4 exactly as before, the per-profile prompt-schema digest, and the seal/witness pair including the mixed-profile refusal.
- MEASUREMENT (2026-09-10), superseding the "no model has been run" clause above without erasing it: a three-episode engineering screen, specified before the family was built, was run on the family as shipped — `tests/budget_calibration.py --production` at `f9fbad1`, episode contract 5 / digest `b11bc1ac…`, 25 turns, a 40,000-token episode ceiling and the same per-turn cap, one requested model ID (`kimi-k3`) over one route under free quota, one episode per case, settings frozen before the run. Three of the five variants ran: `cash_application_002` reward 1.0 (`L` 1.0, `A` 1.0, 5 turns), `cash_application_003` reward 1.0 (`L` 1.0, `A` 1.0, 6 turns), `cash_application_005` reward 0.333334 (`L` 1.0, `A` 0.333334, 10 turns, submitted but INCOMPLETE). All three ended `piv_submitted`; no provider, budget or protocol failure; 123,413 input and 17,412 output tokens in 434 s; cost zero dollars, operator-reported under free quota, with no billing evidence in the archive. Case 5's whole loss is one field: receipt `2026-04-28:GR PAYRUN 0428`'s `unapplied_amount` reads `0.00` where the statement and advice require `30.00`, which loses that receipt's exactness and trips two CORRELATED penalties — `receipt_identity` −0.20 and `ar_tie_break` −0.30 — not three independent mistakes and not a calibrated measure of accounting severity; the prices were fixed before the error was seen and were not changed after seeing it. An offline single-field counterfactual, the archived register with that one field set to `30.00` and nothing else touched, rescores through the shipped `application/1` against the task's own derived truth at `A = 1.000000`, the value the shipped formula predicts; the same run reproduces the delivered artifact's archived stored-byte, logical-text, canonical and result digests and its `0.333334`. What this attests: the family runs end to end through the production instrument, both artifacts are delivered and bound, and the second deliverable can fail while the ledger scores 1.0. What it does NOT attest: any difficulty level, failure rate, generalization beyond this one company-month, or training utility — three episodes, one subject, one attempt each, three of five variants. The note and the whole archive (calibration JSON preserved untouched, run log, three workspaces with public inputs and canonical delivered artifacts and receipts, the rescore and counterfactual as machine-readable JSON, and a provenance sidecar) are committed at `reviews/cash_application_screen_2026-09-10.md` and `reviews/cash_application_screen_2026-09-10/`. One caveat the sidecar records rather than infers: the calibration rows' `profile = standard` field is a GENERATOR-profile label, not the episode profile — the episode profile is `cash_application`, established from the contract digest each row carries and from the source that resolves it.
- v9 manifest, first written to a SEPARATE path and PROMOTED on 2026-09-06 (it is now `~/.piv/manifest.json`; the v8 file is kept as `~/.piv/manifest_v8.json`, sha256 `06800e0308658c5c9559ba51c16e766009462947726a917bf60ab527a099996e`, and the sealed confirm1v4 schedule needs that file and the v8 code to be re-run): sha256 `48500f6c3ee7c06ede2ea93ddbcd1fd55ce95fb75237d6299d3a82168df9be60`; preflight 1400/1400 (1,000 train / 200 eval / 200 hard; phase 1 offline gates AND phase 2 signed-manifest serving door), 197 s with 6 workers; layout attempts {0: 1064, 1: 259, 2: 63, 3: 10, 4: 3, 5: 1}; the secret never appears here
- ledger census over the 1,400: max 13,901 bytes / 304 lines, min 8,821 / 191; envelope 48,000 / 1,000 (headroom x3.45 bytes, x3.29 lines)
- serving door: `tests/liveness_witness.py --production` witnesses the six confirm1 panel selectors, reward 1.0, identical across 2 runs. CORRECTION (2026-09-06): the run recorded here was `--production --sentinels` and reported 10/10, but importing the sentinel list installed the suites' test key and the development route at import time, so that run did not exercise the production door at all; the witness now refuses that combination and skips the sentinels under `--production` (they are chosen under the test key, and one of them, `train:263:hard`, is outside the preflighted range). What DOES witness the production door is the audit receipt below (1,400/1,400 admitted, each serving the id its gates minted) and the probe that a selector outside the manifest is refused

## What the bump is for (measured under the test secret, train:0-299 / eval:0-99 / train:0-299:hard)
- 700/700 minted, no refusals; planted 5-6 standard, 6-8 hard; target accounts 5 in 85% of worlds, 4 otherwise (v8: 2-4 items, 3-4 targets)
- reachable reward ladder (every subset of planted items solved perfectly): 9-13 distinct totals standard (mean 10.3), 10-21 hard (mean 14.5); largest gap between adjacent rungs mean 0.35, max 0.41 (v8: 3-4 rungs standard, mean gap 0.54, max 0.85)

## Suites at this commit
- tests/run_all.py in the clean clone: all 27 suites pass (test_generator 14/14, test_sentinels 2/2 over the four-world cover, test_exploits 17/17 with the payee-attribution witness re-derived on `train:263:hard` at 0.4825 / 0.6825, liveness witness 6/6)
- release-gate sweeps: generator 2,100 seeds clean (52 s; 24 sentinel re-mints identical under another PYTHONHASHSEED); differential 330 selectors (300 hard + 30 standard, shard 48 of 50) 0 violations in 559 s; exploit corpus 0 gaps over 34 selectors (4 sentinels + 30 rotating standard, shard 0), every family reached at least one payload
- `reviews/sweep_failures.json` and `tests/exploits/failures.json` unchanged (clean)

## Not done here, by design
- (superseded 2026-09-06: the v9 manifest WAS promoted, see above. Promotion makes the sealed confirm1v4 schedule un-runnable against the active manifest — its digest and expected public task ids are bound — so re-running it needs `PIV_MANIFEST=~/.piv/manifest_v8.json` and the v8 code; any new confirmatory schedule must be sealed under the manifest it will run against)
- no model panel was run on the dense worlds; the ladder figures above are structural (what a partial repair CAN score), not observed model behaviour

## Reward lattice audit (2026-09-06, `tests/reward_lattice_audit.py`, evidence `reviews/reward_lattice_v9.json`)
Every subset of a world's golden repairs applied to the untouched ledger and scored through the real chain (candidate/1), a sample re-scored through the production loop.
- generated v9, the 1,400 preflighted selectors through the serving door: 82,016 subsets scored, 2,800 also through the loop; monotonicity violations 0; correct-repair penalty activations 0; unexpected states 0; loop mismatches 0; 1,210 s with 8 workers
- marginal reward jumps over 251,952 steps: per-world p95 median 0.225, per-world p95 max 0.410, overall max 0.410; 7,916 steps (3.14%) jump above 0.25 and every one of them is the step that unlocks the bank target (the bank balance is right only when the last item touching it is repaired)
- ladder rungs per world: min 9, median 12, max 21
- cancelling hits: 4 subsets in 4 worlds (train:166, train:568, eval:39, eval:132) where two unresolved transpositions of the same magnitude leave the bank balance right while both counter accounts still miss; the scorer measures balances, so the reward is exactly its arithmetic and stays monotone — a compensating-error case a v10 generator could refuse (equal and opposite bank residuals), noted, not changed
- hand-authored, all 91 registry tasks: 724 subsets, 182 through the loop; 0 / 0 / 0 / 0; 2–3 items a task, so 75% of steps jump above 0.25 (the demo set is small by design; its ladders are 3–5 rungs)

## Audit receipt (2026-09-06, `tests/audit_receipt.py`, evidence `reviews/audit_receipt_v9.json`)
One record per world, built from the evidence the package already produces: the preflight's offline gates re-run on the freshly minted world (minted, ledger within the envelope, publicly identifiable, the public-only checker's repairs EQUAL the seeded plan, golden 1.0 through the real loop), the serving door (admitted by the signed v9 manifest, served id == minted id), a sha256 over the eight public files, the scorer facts (golden 1.0 and complete; untouched 0 with every item unresolved), the reward-lattice counts, and whether the exploit corpus exercised the world.
- generated v9, 1,400/1,400 ok: gates 1,400/1,400; admitted with matching id 1,400/1,400; golden 1.0 1,400/1,400; untouched unresolved 1,400/1,400; lattice clean 1,400/1,400; exploit corpus exercised on 33 (the sentinels and the rotating shard); 182 s with 8 workers
- hand-authored, 91/91 ok (`reviews/audit_receipt_manual.json`): verification 0 problems, golden 1.0, untouched unresolved, lattice clean

## Budget calibration, scripted oracle (2026-09-06, `tests/oracle_budget.py`, evidence `reviews/oracle_budget_v9.json`)
Four scripted strategies that KNOW the answer, played through the real `evaluate` door with realistic reported output tokens, on 15 stratified v9 training worlds (standard k=5,6; hard k=6,7,8; 3 each); caps 25 turns (24 executable) / 40,000 output tokens.
- minimal (read the ledger, write the golden, submit): 4 turns, ~3.7k tokens, 15/15
- diligent (read all eight files, check, write, check, submit): 13 turns, ~5k tokens, 15/15
- incremental (one full rewrite per item, then check and submit): k + 11 turns = 16–19, 17–29k tokens (up to 72% of the ceiling on k=8), 15/15
- sloppy (rewrite, check and re-read per item): 3k + 11 turns; solves k=5 (25 turns) and fails every k >= 6 world at the turn cap with the last committed revision scored (0.33–0.67)
- reading: the shipped budget fits a write-once or write-per-item agent on every world; an agent that also re-reads the whole ledger after every write cannot finish a six-item world. Whether real models are turn-bound or accounting-bound is the hosted-model calibration below.

## Budget calibration, hosted models (2026-09-06, `tests/budget_calibration.py`, evidence `reviews/calibration/`)
Planned: two models on ten stratified v9 training worlds (standard k=5,6; hard k=6,7,8; two each) under the shipped budget (25 turns / 40,000 output tokens) and a looser one (50 / 80,000). INCONCLUSIVE: the hosted endpoints available to a solo developer did not sustain it.
- Gemini 2.5 Flash (OpenAI-compatible endpoint): a `finish_reason` the SDK does not accept ("function_call_filter: MALFORMED…"), then 429 quota on every world
- gpt-oss-120b on Groq: the environment's parameterless tool schemas are refused (`required: []` beside an empty `properties`, then strict-mode call validation of omitted optional arguments, then replayed `reasoning_content`); with those shimmed in the calibration client the free tier's 8,000 tokens-per-minute limit refuses the second turn — a finding for the environment's tool schema under an episode-contract version bump, not for the scorer
- Nemotron-3 Super 120B (NVIDIA): one episode, train:0 (k=5): burned the whole 40,000-token ceiling in 25 turns and scored 0 (`piv_output_budget_exhausted`)
- Kimi K3 (NVIDIA): 17 of 20 episodes ended in provider 500/504 after 15–28 minutes each; the three that ran solved their world completely — train:3 (k=5) 1.0 in 6 turns / 5.9k tokens, train:3:hard (k=7) 1.0 in 7 turns / 4.3k tokens, and under the looser arm train:2:hard (k=7) 1.0 in 7 turns / 5.2k tokens — all far inside the shipped budget, consistent with the write-once oracle above
- DeepSeek V4 Flash (NVIDIA): first episode 504; the chain was stopped
- what can be said: nothing observed contradicts "the shipped budget is not what makes a dense world hard" — a capable model that reads, writes once and submits finishes a seven-item world in 7 turns; the budget-bound failure seen (Nemotron) is a model spending its output on reasoning, not on the ledger. What cannot be said yet: strict-solve rates by k and the shipped-versus-loose delta; that needs a paid or quieter endpoint and is the user's call

## Errata (2026-09-07)
- **The system prompt contradicted the tasks; episode contract 2 -> 3.** The shipped prompt said "Preserve every existing transaction." and "do not remove or rewrite entries that are already there", while every bookkeeping policy requires removing one copy of a doubled entry and re-posting a mis-keyed one. Every model that scored 1.0 resolved the conflict in the policies' favour, so the sentence was not redundant but actively wrong, and what it cost the models that did not is unmeasured. Found in external review (Codex, 2026-09-06), confirmed in the shipped bytes. Replaced by: "A write replaces the whole file, so carry through every transaction you are not correcting." and "An entry that is already there may itself be the error: correct or remove one only where the files you were given show that it is wrong, and leave anything you cannot show is wrong exactly as it stands." — the whole-file write still must not drop entries, the chart is still closed, and no kind of error is named. `EPISODE_CONTRACT_VERSION` is 3; `tests/arm_table.py` refuses to pool a contract-3 row with the archived contract-2 rows, by digest, which is the intended cost. The same bump drops the `required: []` a parameterless tool advertised beside its empty `properties` (Known issues, third bullet): strict validators (Groq) refused the request outright, and a fix that moves the digest belongs on a bump that is happening anyway rather than on one of its own.
- **Two latent projector faults in Known issues are fixed, byte-for-byte compatible with every shipped world.** `policy.movement_of` no longer reads `event.invoice_id` on an ACH row for an event that carries no invoice (`ExpensePayment`, `Prepayment` now render a bank row with an empty reference, as a card row does). `project.py` pads an account name to the fixed column width or one past the name, whichever is larger (`_padded`), so a 30- or 40-character name keeps its separator; the longest shipped name is 29. Guard tests: `tests/test_graph.py` (`test_events_without_an_invoice_settle_by_ach`, `test_an_account_name_at_the_column_width_keeps_its_separator`).
- **`tests/budget_calibration.py` did not archive the setting it calibrates.** Rows carried the reward and the stop label but not the per-turn completion cap, so an 8k row and a 16k row were indistinguishable after the fact (found in external review, 2026-09-07). Rows now carry the arm identity (per-turn cap, episode ceiling, turns, route), the wire caps the environment intended per turn (`piv_request_max_tokens`), the truncation and no-tool counters, the revision count and the workspace. A stop label is not a diagnosis: an episode can end at the ceiling and still have delivered.
- **The world validator accumulated customer receipts per invoice but checked vendor payments one at a time.** One payment above an invoice's gross was refused ("pays more than the invoice gross"); two payments that together exceed it passed `project.check_bundle`, so an economically wrong generated world could have been accepted. No shipped world does this (all 91 registered tasks and a 60-selector generated sample derive unchanged). Found in external review (2026-09-07), fixed by accumulating `VendorPayment` amounts per invoice beside the receipts; guard test `tests/test_graph.py::test_vendor_payments_accumulate_per_invoice`. A validator change: no served byte and no contract digest moves.
- **A phantom 1-of-27 failure was the test venv, not the code.** `test_measure_budget`'s import-seal witness refused `sys.path` entry `…/beancount-ledger-ci`, the root of a *different* clone whose editable install had put it on the path. With this repository's own venv (`uv venv .venv --python-preference only-managed && uv pip install -e .`, as CI does) all 27 suites pass. The witness was right; recorded so nobody debugs it twice.

## Errata (2026-09-10)
- **Cash-application Case 2's public inputs moved after the screen was measured.** The payment-reference identity rule in `graph/identify.py` was wrong (external review, round 13, decision 5): it read any reference of two or more whitespace-separated words with a digit in one of them as a payment INSTRUMENT, which admits an invoice list (`SI-3104 SI-3102`) and a dated memo (`APRIL 2026`), neither of which names one cash movement. Decisive identity is now restricted to a payment identifier the public evidence DECLARES — a cheque number the row's own wording introduces, a bank trace id, or a reference a mounted `remittance_advice.csv` names in `payment_reference` — and only where no two advices and no two statement rows carry it. Case 2 has no advice for its third receipt by design, so under the corrected rule its invoice list stopped deciding; rather than loosen the rule, the case was given a genuine public identity, the bank's own trace `TRC0428442`, printed ahead of the payer's invoice list on the 28 April statement row and quoted by the entry the books carry. **Consequence for the archived screen:** the 28 April reference read `SI-3104 SI-3102` when `v10-codex/cash_screen_evidence/workspaces/cash_application_002` was measured, and that workspace's delivered `cash_application.json` keys R3 as `2026-04-28:SI-3104 SI-3102`. The same case folded from the current source keys it `2026-04-28:TRC0428442 SI-3104 SI-3102`. The archived Case 2 delivery is not reproducible against this revision and would not re-score as delivered. Cases 1, 3, 4 and 5 are unmoved, so the screen's finding — Case 5's omitted `unapplied_amount` — stands. Any publication of that screen must state the source revision it was measured at; the delivered artifacts remain valid evidence about the run, not about this source.
- **The rule's own version is separated from the signed population's.** `IDENTIFY_VERSION` stays 7 because it is bound into `manifest.versions()` and therefore into every promoted record's signature; bumping it would make `admit` refuse the whole v9 population over a rule none of those worlds can reach (surveyed: none of the 95 authored tasks and none of 60 sampled generated worlds mounts an advice or prints a multi-word reference or a trace id). The rule instead carries `identify.REFERENCE_IDENTITY_VERSION`, now 2, declared by `manifest.family_admission_versions()` for the cash-application family manifest that decision 3 defers. Stated for the record: on an advice-free pack the new rule IS strictly narrower than the shape rule it replaced; unrestricted it is not, because a mounted advice can declare a single-token reference the shape rule refused.

## Known issues (2026-09-06)
Open defects and limits, recorded here because a reader should not have to find them in a diff.
- FIXED 2026-09-07 (see Errata): `graph/project.py` renders an account name of 30 characters or more into the opening block without a separator; hand-authored worlds must keep names at 29 characters or fewer. The generator's own charts are inside that limit.
- FIXED 2026-09-07 (see Errata): An `ExpensePayment` or `Prepayment` settled by ACH_OUT raises in the projector (it looks for an invoice that kind of event does not carry). Cheque and card are the settlement rails those events support.
- FIXED 2026-09-07 (rode contract 3, see Errata): The six public tools' JSON schemas declare `required: []` beside an empty `properties` with `strict: true` for the parameterless tools; providers that validate strictly (Groq) refuse the request. Fixing the schema moves the episode-contract digest, so it waits for a contract version bump.
- The reward lattice contains four subsets (of 82,016) where two unresolved transpositions cancel on the bank leg, so the bank balance is right while both items stay unresolved. The scorer measures balances, so this is its arithmetic, not a defect; a later generator can refuse equal-and-opposite bank residuals.
- The hosted-model budget calibration is inconclusive (provider quotas and outages, see above); the scripted-oracle calibration is what the budget claim rests on.

## Cash-application family: three more company-months, six variants (2026-09-11)
The family is now **eleven** shipped ids, so the hand-authored surface is **106** tasks (95 legacy + 11 family).
`cash_application_006`..`011` are three MATCHED PAIRS — two variants of one company-month differing in exactly one
authored fact, every other authored fact held identical, so a solver's failure localises to the question that fact
asks. Worlds `thornbury-2026-06-pf-a`/`-b` (policy fallback: R3 26,868.00 against 21,000.00 — does the fold continue
past the invoices the statement reference names?), `pennywhistle-2026-06-cr-a`/`-b` (credit-note residue: CN-0618
gross 3,150.00 against 2,940.00 — what happens to credit nothing absorbs?), `tallowmere-2026-07-ar-a`/`-b` (advice
residue: one advice cell, 4,020.00 against 4,560.00 — is cash rung (1) does not name left unapplied?). Modules
`graph/worlds/thornbury_2026_06.py`, `pennywhistle_2026_06.py`, `tallowmere_2026_07.py`, each stating its pair as
`WORLD_BY_TASK`, with the shared policy text and instruction in `_variant_pack.py`; served from
`graph/worlds/REGISTRY` under episode contract 5 with **no evaluator secret**, exactly like the Bowline five.
- **The specification is `v10-codex/six_variant_packs.md`, and every one of the 66 projected public files equals its
  rendered file BYTE FOR BYTE** (11 files x 6 variants, checked file by file against the document). One of the 66
  the pack prints as a patch rather than as a whole file — pair 1's variant-B `ledger.beancount`, given as a
  two-posting delta on variant A's — and it is A plus that delta that matches. Nothing in the pack was changed to
  make a world fit.
- Gates: (l) the opening register ties to the opening entry on the public bytes and in the truth (63,890.00 /
  18,375.00 / 25,815.00); (m) the shipped public fold over the projected bytes equals the truth folded from the
  authored facts under independently built keys, and both close at the expected ledger's `Assets:AR` (25,150.00 /
  31,018.00 / 9,660.00 / 9,870.00 / 5,130.00 / 5,130.00); (n) the narration rule over every narration, advice note
  and credit memo; (o) no admitted baseline reaches any of the six truths — the diagnostic `number_order`
  included, so the claim is not just an empty `refused_by` — and the admitted SETS are the pack's: EIGHT of the ten
  at Thornbury, because `write_off_everything` and `write_off_nothing` are NOT admitted there (no bound advice claims
  a deduction anywhere in that month, which is what `six_variant_packs.md` section 4 says of them), three at
  Pennywhistle, five at Tallowmere. The worlds suite pins each of the three sets by name.
- Identifiability: `identify.check_identifiable` returns `unique`, ONE reading, on all six, and the reading is
  exactly the planted bank-evidenced repairs. Every plant is covered by an explicit validator. The three
  company-months carry three DIFFERENT two-plant recipes — omission + alteration (Thornbury), duplicate +
  alteration (Pennywhistle), duplicate + omission (Tallowmere).
- `Expenses:SmallBalanceWriteOffs` opens at ZERO in all three months — no opening leg, no carry-forward row — so its
  expected closing balance IS its period movement: 0.00 / 0.00 / 15.00, which is what `candidate/application.py`
  reads for `writeoff_tie_break`.
- NEW authoring check, from the review's decision 5: `schema.check_world` refuses a `CreditNote` whose net exceeds
  the named invoice's ORIGINAL net, or whose tax exceeds its original tax. The bound is the original SALE, never the
  unpaid BALANCE — Bowline's Case 5 credits 540.00 against an invoice with 300.00 outstanding and is correct, and
  capping at the balance would prohibit it.
- `tests/world_checks.check_world_task` gained `co_authored`: a variant-pack module states TWO worlds, so the
  derived-literal scan (gate (h)) must read the sibling's authored amounts as authored literals in that file. It is
  load-bearing rather than vacuous, and `tests/test_family_validators.py` pins that it bites without it (Tallowmere
  variant A's cost of sales folds to 4,560.00, which is variant B's advice cell).
- **The shipped bytes did not move.** The five Bowline bundles' public bytes and the 95 legacy tasks' public bytes
  are byte-identical before and after this phase (sha256 over name-and-content of every public file:
  `cash_application_001` `0a5c94fa…`, `002` `a7153bca…`, `003` `64956ef6…`, `004` `c5869203…`, `005` `9189497e…`;
  the 95 legacy together `089873e0…`). The archived Bowline measurement evidence therefore remains valid, and the
  legacy episode-contract view and digest `e8b8753d…` are untouched.
- Suites: `tests/run_all.py` 34/34. The family's four suites were extended rather than duplicated — the fold suite
  folds all six packs from the projector's own bytes, the worlds suite runs (l)/(m)/(n)/(o) and the pair rules over
  the six, the validators suite runs identifiability and plant coverage, and the scoring suite scores every
  variant's golden at 1.000000 and complete through the frozen `candidate/1` and `application/1`.
- **The packs carry a dated AI accounting-plausibility review, not a practising accountant's sign-off:** the review
  is archived verbatim as `v10-codex/accounting_review_2026-09-11.md` under its own label sentence — it identifies
  corrections required before implementing these synthetic examples and validates neither operational accounting,
  tax compliance nor financial-statement presentation. Practitioner validation is still outstanding.
- No model has been run on `cash_application_006`..`011`. This section attests the packs, the gates and the battery,
  and no difficulty, failure rate or training utility.

## Errata (2026-09-11, to the section above, same day)
- The gate-(o) bullet first read "the admitted SETS are the pack's (all ten at Thornbury, three at Pennywhistle,
  five at Tallowmere)". **Thornbury admits EIGHT of the ten**, not all ten: `write_off_everything` and
  `write_off_nothing` are not admitted there, which `six_variant_packs.md` section 4 states in as many words ("no
  bound advice claims a deduction anywhere in the month"). Measured with the shipped `cash_application.baseline_report`
  over the projected bytes of `cash_application_006`/`007`. The bullet now says eight; Pennywhistle's three and
  Tallowmere's five were right as written.
- Nothing in the battery caught it, because the worlds suite asserted only that `refused_by` was empty. It now pins
  the admitted SET of every variant by name, and that every shipped baseline is admitted somewhere, so a set that
  grows, shrinks or is renamed fails `tests/test_cash_application_worlds.py`. The pin was checked against a negative
  control: adding the two write-off baselines to Thornbury's pinned set fails the suite.
- The byte-for-byte bullet now records that one of the 66 files, pair 1's variant-B `ledger.beancount`, is printed
  in the pack as a two-posting delta on variant A's rather than as a whole file; it is A plus that delta that
  matches byte for byte. No projected byte moved: the 95 legacy and the five Bowline public bundles hash exactly as
  above (`089873e0…`, `0a5c94fa…`, `a7153bca…`, `64956ef6…`, `c5869203…`, `9189497e…`) before and after this
  correction, and the six new ids are unchanged too.
- `docs/REFERENCE.md` said "the 27-suite battery" — a pre-existing staleness, not from the variant work. The battery
  is 34 suites (`len(tests/run_all.py::SUITES)`), and the line now says so.

## Errata (2026-09-11, second set, after the six-variant screen)
- **The Bowline validity inference above is too broad and is qualified here.** The bullet says the shipped bytes did
  not move "therefore" the archived Bowline measurement evidence remains valid. The hashes are correct and unchanged:
  this phase preserved the Bowline bytes as they stood immediately before it. It did **not** undo the Case 2
  payment-reference change made earlier the same week, which `reviews/cash_application_screen_2026-09-10.md` and its
  sidecar already document — that screen was measured where the 28 April row's reference reads `SI-3104 SI-3102`,
  and this source folds the receipt as `2026-04-28:TRC0428442 SI-3104 SI-3102`. Historical evidence remains valid
  **at its recorded revision**, not automatically against every later checkout. Unchanged bytes across one phase are
  evidence about that phase and about nothing before it.
- **"No model has been run on `cash_application_006`..`011`" was true when written and is now superseded.** One
  screen has since been run against the six variants at `328d702`, one subject and one episode each:
  **five variants produced scored deliveries and `cash_application_011` ended with a provider 403 and no delivery.**
  Four scored a complete `1.0`; `cash_application_007` scored `0.64` on a complete ledger repair with an incomplete
  closing register. The missing 011 cell stays missing — neither a zero nor an inferred success — and the screen is
  an incomplete descriptive one. It attests no difficulty, failure rate, generalisation or training utility, and it
  is not a release prerequisite. The note is `v10-codex/six_screen.result.md`.

## Errata (2026-09-11, third set, on review of the correction phase)
- **The failure-localisation sentence in the six-variant section above is retracted.** That section opens by calling
  `cash_application_006`..`011` three matched pairs "differing in exactly one authored fact, every other authored fact
  held identical, so a solver's failure localises to the question that fact asks". The clause after "so" does not
  follow and is withdrawn. **Each pair differs in one authored fact, which defines the accounting distinction it is
  intended to test. This does not guarantee that a solver's error concerns that distinction. Attribution requires
  inspection of the delivered artifacts.** The screen of 11 September showed the difference: `cash_application_007`'s
  only error was an incomplete closing register, which is not the question that pair's differing fact asks. The same
  correction is now written in place in `docs/REFERENCE.md`, and in `v10-codex/six_variant_packs.md` (introduction,
  Thornbury's framing and the Tallowmere shortcut table), `v10-codex/accountant_review_pack.md` and
  `beancount_ledger/graph/worlds/_variant_pack.py`.
- **The `check_world` credit-note bullet above overstates the guard, and is corrected here.** It says the check
  refuses a `CreditNote` whose net exceeds the named invoice's ORIGINAL net or whose tax exceeds its original tax.
  `beancount_ledger/graph/schema.py:582-583` derives that supposed basis from the invoice's GROSS at the CREDIT
  NOTE's own rate — `original_net = (gross / (1 + credit_note.tax_rate))`, then `original_tax = gross - original_net`
  — and a `Document` carries only a gross, never its own net or rate, so the check does not independently establish
  the original sale's net and tax. At a credit-note rate of zero, a 4,100.00 net credit passes against a 4,200.00
  gross invoice whose actual basis was 4,000.00 net plus 200.00 tax. What the check does enforce is a bound derived
  from the named invoice's gross at the note's own rate, and — deliberately — no cap at the invoice's unpaid balance
  (Bowline's Case 5 credits 540.00 against an invoice with 300.00 outstanding and is correct). Every credit note in
  the shipped worlds uses its invoice's rate and fits that invoice, so this changes no shipped world's accounting and
  no screen score. Validating against an independently established original-sale basis, and adding a mismatched-rate
  negative control, are outstanding before the requirement may be called enforced. The guard itself is unchanged in
  this phase; only the claim about it is.
- **The bundle digests above had no stated recipe; here it is, for the five that reproduce.** Each
  `cash_application_00N` figure is `sha256` over the task's projected public files taken in sorted name order, each
  contributing `name || 0x00 || content || 0x00`, truncated to eight hex digits. Re-derived from `REGISTRY` through
  `graph.derive.derive_contract` at this revision, that recipe reproduces all five exactly — `001` `0a5c94fa`, `002`
  `a7153bca`, `003` `64956ef6`, `004` `c5869203`, `005` `9189497e` — and yields `006` `5fc4b055`, `007` `bd64e62d`,
  `008` `2573e334`, `009` `ee1ca200`, `010` `f6e7616f`, `011` `2f7a27f6` for the six new ids. The **combining rule
  for the single `089873e0` figure over the 95 legacy tasks is not recorded anywhere and was not recovered**; that
  one number is therefore not independently checkable from this document, and the claim it summarises should be read
  against `tests/test_legacy_freeze.py`, which pins all 760 legacy public files individually and passes.

## Errata (2026-09-11, fourth set: the credit-basis guard is now fixed, and 007 is a measured fixture)

- **The credit-basis guard no longer derives the basis from the note being checked.** The third errata set above
  recorded that `check_world` overstated what it enforced and left the guard unchanged; this set changes the guard.
  `beancount_ledger/graph/schema.py` gains `original_sale_basis(world, invoice_id)`, which establishes an invoice's
  original net and tax **from the world and never from a credit note**, and the `CreditNote` branch of `check_world`
  bounds the note against what it returns. Two sources, in order:
  - the `Sale` the world authors for that invoice — its own net at its own rate, READ rather than derived. This is
    the whole basis for an invoice raised inside the period (Thornbury's SI-4415 is 6,000.00 at 6%). A sale whose
    net and tax do not add up to the invoice's gross establishes nothing, and is reported as such.
  - an invoice **carried in from the prior period** has no `Sale` in this world and a `Document` carries only a
    gross, so its basis is that gross split at **the world's own single authored sales-tax rate** — a fact of the
    world's sales, identical whatever rate a note claims. Every shipped credit note names such an invoice. Where a
    world's sales are authored at several rates, or at none, no basis is established and the world **may not carry a
    credit note against that invoice at all**: `check_world` says so rather than inventing a rate.
  What is therefore enforced, and may now be claimed: a note may not reverse more sales value than the original sale
  carried, nor more tax than the original sale's tax, with the original sale established independently of the note.
  What is **not** enforced, and is not claimed: an original net and tax authored on the invoice document itself. A
  `Document` carries a gross and nothing else, and adding fields to it would move every world's graph digest, so the
  prior-period basis rests on the world's rate being single and authored. The bound remains the SALE and never the
  unpaid BALANCE — Bowline's Case 5 credits 540.00 against an invoice with 300.00 outstanding and is correct.
- **The negative control round 15 named is now a test.** Pennywhistle's SI-5219 is a 4,200.00 invoice **carried in
  from the prior period**: the world authors no `Sale` for it, so — like all eleven shipped notes' invoices — its
  basis comes from the gross-split branch above, 4,200.00 at the world's single authored sales rate of 0.05, i.e.
  4,000.00 net and 200.00 tax. (Earlier wording here called that "a 4,000.00 + 200.00 sale at the world's 5%", which
  reads as an authored sale event; the figures are right, the wording was not.) A 4,100.00 net credit at a **zero**
  tax rate passed the superseded
  derivation (`4,200.00 / 1.00 = 4,200.00`) and is now refused: *"reverses 4100.00 of sales value against
  doc:si-5219, whose original sale is 4000.00 (4200.00 gross at this world's authored sales rate 0.05)"*. The same
  test pins that a note's rate cannot move its own bound at 0.00 / 0.05 / 0.20 / 1.00, that an over-credited tax leg
  is refused on that leg, that a two-rate world may not carry the note, and that Case 5's 540.00-against-300.00
  credit still passes — `tests/test_cash_application_worlds.py::`
  `test_the_credit_basis_guard_reads_an_independently_established_original_sale`.
- **No shipped world's accounting or score changed, and this was verified rather than assumed.** All eleven
  cash-application worlds return an empty `check_world` before and after. Each of the eleven notes fits a basis that
  is now read rather than manufactured: CN-0412 250.00 + 20.00 against 3,333.33 + 266.67 (Bowline c1–c4), 500.00 +
  40.00 against 1,000.00 + 80.00 (c5), CN-0609 1,200.00 + 72.00 against 9,000.00 + 540.00, CN-0618 3,000.00 + 150.00
  and 2,800.00 + 140.00 against 4,000.00 + 200.00, CN-0714 600.00 + 30.00 against 3,600.00 + 180.00. The guard is a
  generator-side authoring check; it reads no submission and enters no reward.
- **`cash_application_007` is now an executed regression fixture, not an argument.** The 11 September screen's
  Thornbury B delivery was re-scored through the **shipped** `application/1`, `candidate/1` and `composite/1` at
  this revision, and the counterfactual that adds **only** the two omitted closing rows was scored the same way.
  The delivered artifacts are copied verbatim to `tests/observed/cash_application_007/` (application, ledger and
  the run's own delivery receipt) and checked against that receipt's stored-byte and logical-text digests, and the
  two decompositions are archived as machine-readable JSON beside the screen evidence
  (`v10-codex/six_screen_evidence/cash_application_007_{delivered,counterfactual}.decomposition.json`).

  | | delivered | counterfactual (+ SI-4415 6,360.00, + SI-4419 10,600.00, all four outcome columns zero) |
  |---|---|---|
  | `L` (`candidate/1`, the delivered ledger, unchanged in both) | 1.000000, complete | 1.000000, complete |
  | `receipts_exact` / `register_exact` / `credit_exact` | 1.000000 / 0.800000 / 1.000000 | 1.000000 / 1.000000 / 1.000000 |
  | penalties | `ar_tie_break` (remaining 14,058.00 − unapplied 0.00 ≠ closing receivables 31,018.00) | none |
  | invoice states | eight `INVOICE_EXACT`, SI-4415 and SI-4419 `INVOICE_MISSING` | ten `INVOICE_EXACT` |
  | `A` (`application/1`) | 0.640000 | 1.000000 |
  | composite | 0.640000, **not** complete | 1.000000, complete |

  The re-score reproduces the delivery receipt's own `canonical_digest` `66088b2c…` and `application_result_digest`
  `199e8af7…` and its `0.64`. It does **not** reproduce the ledger's `score_result_digest` or the
  `composite_result_digest`; the reason is given in the correction immediately below. Round 15 expected the
  counterfactual at `L = A = total = 1`; the measurement agrees, and what it establishes is that the two omitted
  rows account for the **whole** of the loss — not why the solver omitted them.
  `tests/test_cash_application_scoring.py::test_the_observed_007_delivery_and_its_two_row_counterfactual`.
- **CORRECTION, same day: the stated reason for that non-reproduction was false, and "never" overstated it.** The
  outcome above is true — a re-score does not return the delivery receipt's ledger or composite result digest — but
  the mechanism published for it was not. The superseded wording, which stood at lines 309–310 of this file, in the
  archived decomposition JSON and in the `a19310d` commit message, read: *"a `PrivateReceipt` carries a fresh
  `uuid4` per evaluation and the ledger result digest binds it"* / *"never the same ledger or composite RESULT
  digest"*. **The `uuid4` binds nothing.** `receipt_identity()` at `beancount_ledger/candidate/committed.py:875`
  deliberately EXCLUDES the receipt's `attempt_id` — its docstring is *"The input receipt minus the attempt id: a
  replay of the same bytes for the same revision of the same rollout is the same evaluation"* — and `attempt_id`
  appears nowhere else in the package beyond its field declaration at `committed.py:775`. MEASURED, by scoring the
  identical fixture bytes twice with a fresh `uuid4` each time: the SAME evaluation receipt `a97951b7…`, the SAME
  ledger result digest `91d1378d…` and the SAME composite `498f3fe8…` both times. What the evaluation receipt does
  bind is the replayed identity — `rollout_id`, `committed_revision` and the three input digests — and that is what
  differs here:

  | identity scored | evaluation receipt | ledger result | composite result |
  |---|---|---|---|
  | the test's (`rollout_id="check"`, revision 1) | `a97951b7…` | `91d1378d…` | `498f3fe8…` |
  | the run's own `f2f7e5f6cada45b292383d77330708fc`, revision 1 | `42c42917…` | `cfe5054f…` | `f035479d…` |
  | what the delivery receipt records | `647b5857…` | — | `a1e28649…` |

  Even under the run's own rollout id it does not reproduce, because `receipt_identity` also binds
  `submitted_text_digest` (ours, over the stored artifact, is `f6d7a5c9…`) and the archive holds the canonical
  stored artifact, **not the original submitted text** — which is exactly what round 15's own Records replacement
  says the archive does not contain. Measured: holding the rollout id fixed and substituting any other submitted
  text moves the evaluation receipt and both result digests. So these digests are **deterministic** given the
  rollout id, the revision and the three input digests; what cannot be reconstructed from the archive is the
  submitted text, and that is the honest limitation. The regression test never encoded the false claim; a second
  test now pins the measured behaviour so the claim cannot come back —
  `tests/test_cash_application_scoring.py::test_the_007_result_digests_replay_by_identity_not_by_nonce`. Nothing
  about any score, byte or shipped artifact changes with this correction; the `a19310d` commit message stands in
  history with the superseded wording and is corrected here rather than rewritten.
- **The shipped bytes still did not move.** The eleven cash bundles re-derive to `0a5c94fa` / `a7153bca` /
  `64956ef6` / `c5869203` / `9189497e` / `5fc4b055` / `bd64e62d` / `2573e334` / `ee1ca200` / `f6e7616f` / `2f7a27f6`
  and `tests/test_legacy_freeze.py` holds the 760 legacy public files and `committed.py` byte-identical, before and
  after this phase. `tests/run_all.py`: 34 of 34 suites pass.
