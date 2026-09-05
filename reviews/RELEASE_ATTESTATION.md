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
- component versions: `{'generator': 8, 'identify': 7, 'scorer_contract': 1, 'renderer': 1, 'task_contract': 1, 'manifest_schema': 2, 'preflight_contract': 1, 'gate_set': 'e2f26ab5cdf60d53'}`
- episode contract v2, digest `152dbbaf80a1f761d42d5b94139fd64c320f0810cbbe4855c7cb1cc0766fea59`
- replay contract v1: A/B1 `180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed`, B2 `29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0`
- production manifest: rotation-selected file sha256 `06800e0308658c5c9559ba51c16e766009462947726a917bf60ab527a099996e`; preflight 1400/1400 (phase 1 offline gates AND phase 2 signed-manifest serving door); the secret never appears here

## Evidence files (sha256)
- reviews/confirmatory_design.md: `c0659a48124b84025591211f246ba2d9dc0af72d98d1b909754dfcc0d099266c`
- reviews/schedule_confirm1v4.json: `280a46108d82b348a6d0e798d223a322c664644ab1f91b91a883ffad34f5b494`
- reviews/arms_confirm1v4.md: `ede6960192514a3f367e01655571a9e621253c1e8375515906a6c89d10acddef`
- reviews/release_lock.txt: `194ae89253ce327a55d4476bd0ce8d346dd413b3331b54cd8a72a5e2304c6ee2`
- reviews/submission_texts.md: `83cf9618ed6e196fed18ab77cbe81023c5bc94ace97e703292d44642af95db7a`
- README.md: `6e87615f7b596cde9ef30f8601098178483dc5b717af1ef07d37958cccbc875c`
- LICENSE: `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

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
- v9 manifest, written to a SEPARATE path (`~/.piv/manifest_v9.json`, the v8 file untouched and still the rotation's active manifest): sha256 `48500f6c3ee7c06ede2ea93ddbcd1fd55ce95fb75237d6299d3a82168df9be60`; preflight 1400/1400 (1,000 train / 200 eval / 200 hard; phase 1 offline gates AND phase 2 signed-manifest serving door), 197 s with 6 workers; layout attempts {0: 1064, 1: 259, 2: 63, 3: 10, 4: 3, 5: 1}; the secret never appears here
- ledger census over the 1,400: max 13,901 bytes / 304 lines, min 8,821 / 191; envelope 48,000 / 1,000 (headroom x3.45 bytes, x3.29 lines)
- serving door witnessed with `PIV_MANIFEST` pointing at the v9 file: `tests/liveness_witness.py --production --sentinels` 10/10 (the six confirm1 panel selectors and the four v9 sentinels), reward 1.0, identical across 2 runs. Without `PIV_MANIFEST` the same code refuses every generated selector ("minted under other component versions: ['generator']") — the intended behaviour of the untouched v8 file

## What the bump is for (measured under the test secret, train:0-299 / eval:0-99 / train:0-299:hard)
- 700/700 minted, no refusals; planted 5-6 standard, 6-8 hard; target accounts 5 in 85% of worlds, 4 otherwise (v8: 2-4 items, 3-4 targets)
- reachable reward ladder (every subset of planted items solved perfectly): 9-13 distinct totals standard (mean 10.3), 10-21 hard (mean 14.5); largest gap between adjacent rungs mean 0.35, max 0.41 (v8: 3-4 rungs standard, mean gap 0.54, max 0.85)

## Suites at this commit
- tests/run_all.py in the clean clone: all 27 suites pass (test_generator 14/14, test_sentinels 2/2 over the four-world cover, test_exploits 17/17 with the payee-attribution witness re-derived on `train:263:hard` at 0.4825 / 0.6825, liveness witness 6/6)
- release-gate sweeps: generator 2,100 seeds clean (52 s; 24 sentinel re-mints identical under another PYTHONHASHSEED); differential 330 selectors (300 hard + 30 standard, shard 48 of 50) 0 violations in 559 s; exploit corpus 0 gaps over 34 selectors (4 sentinels + 30 rotating standard, shard 0), every family reached at least one payload
- `reviews/sweep_failures.json` and `tests/exploits/failures.json` unchanged (clean)

## Not done here, by design
- the v9 manifest is not promoted: copying it over `~/.piv/manifest.json` would make the sealed confirm1v4 schedule un-runnable (manifest digest and expected public task ids are bound); any new confirmatory schedule must be sealed under the manifest it will run against
- no model panel was run on the dense worlds; the ladder figures above are structural (what a partial repair CAN score), not observed model behaviour
