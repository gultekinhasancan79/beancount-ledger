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
