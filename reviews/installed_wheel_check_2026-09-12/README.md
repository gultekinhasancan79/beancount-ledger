# The installed-wheel check, published (2026-09-12)

Twelve episodes through the real `env.evaluate()` door of the **installed** package, in a clean
throwaway virtual environment, offline, driven by a scripted client. No model or API call. The
eleven cash-application tasks each deliver the installed package's own golden ledger and golden
register; `bank_recon_001` is the legacy control and must carry no application block.

## What is here

| file | what it is |
|---|---|
| `installed_wheel_check.py` | the runner, as executed. Its docstring declares exactly what was added for publication over the runner that produced the 2026-09-11 record. |
| `uploaded_0.2.0.json` | the run against the wheel **that was uploaded to the Environments Hub** (`1c83e4c5…`). |
| `attested_build_0.2.0.json` | the run against the wheel the release attestation names (`5a1171c5…`), preserved as the earlier build's evidence. |

Both records were produced on 2026-09-12 by the runner in this directory, one wheel installed at a
time into the same throwaway environment.

## The tested artifact is bound, not asserted

`--wheel` makes the record name an artifact it actually tested. The runner hashes the wheel, hashes
its `RECORD` and `METADATA`, and then compares **every** `beancount_ledger/` member of the wheel
with the file at the same path under the installed `site-packages`. A single mismatch aborts before
any task is scored. `every_runtime_member_matches_the_installed_file` in each record is that check
having passed over all 61 runtime members.

| | uploaded | attested build |
|---|---|---|
| wheel sha256 | `1c83e4c5134b7d24ddb8e0ac0ec260108f23ebed2a2ec2ecaeb9071822e630a9` | `5a1171c5f6ac957e2c9d6b2e18dada34bb353a17718edc22c1a7251bb08161ef` |
| wheel bytes | 527,497 | 527,487 |
| RECORD sha256 | `78d0593222dece87cb5be4ac813db3f0046d3b1c7d1970e630a8439dbce203b1` | `eedc849f134d2df2874f93c10967bf650e8d9602c6d8236b085d380423bb7a46` |
| METADATA sha256 | `c10b7c8bee24ad23c98e216574a0274cd478a216d36aef240ee69d4a4a1b4dba` | the same |
| members / runtime members | 65 / 61 | 65 / 61 |
| result | twelve of twelve, `failures: []` | twelve of twelve, `failures: []` |

The two wheels differ in exactly one runtime member and in the `RECORD` that hashes it — see the
publication record in `reviews/RELEASE_ATTESTATION.md`.

## Captured, not declared

Every row's `contract_digest` is **captured** from that episode's own
`piv_episode_contract_digest` state column, and every row says so in its own
`contract_digest_source` field. Nothing is copied from a module constant.

That distinction is the reason this directory exists. Three earlier `wheel_check*.json` records in
the private working area each hold twelve complete successes — the twelve successes stand — but
their runner read `episode_contract_digest` from the top level of the publication manifest, where
the field does not live, and so recorded `contract_digest: null` twelve times. The contract digests
printed beside those runs were **declared** values, not values that run captured. They are not
published here as though they had been recorded.

## How it was run

The runner refuses to start if the repository is on `sys.path`, which includes its own directory
once it lives in `reviews/`. It was therefore executed from a byte-identical copy outside the
repository, against `wheelvenv15`, a throwaway environment holding nothing but the wheel and its
pinned dependencies — never the repository's own `.venv`.

    python installed_wheel_check.py <out.json> --wheel <path to the .whl>
