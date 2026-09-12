# The installed-wheel check, published (2026-09-12)

Twelve episodes through the real `env.evaluate()` door of the **installed** package, in a clean
throwaway virtual environment, offline, driven by a scripted client. No model or API call. The
eleven cash-application tasks each deliver the installed package's own golden ledger and golden
register; `bank_recon_001` is the legacy control and must carry no application block.

## What is here

| file | what it is |
|---|---|
| `installed_wheel_check.py` | the runner. It is the copy that ran with its module docstring corrected afterwards, and nothing else changed — see "Which bytes ran" below. Its scoring path is byte-identical to `V15_wheel_check2.py`, the private runner that produced `verify15/wheel_check15b.json` (2026-09-11 21:16:03) — the one 2026-09-11 run that captured contract digests. Neither that runner (sha256 `6cff7704…`, `bb5c3f1a…` LF-normalised) nor that record (sha256 `ae0d524a…`) is published, so the docstring binds the claim to their bytes, and names the row fields — `contract_digest_source`, and `turns` on the legacy branch — that were added and so are not part of it. |
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

That distinction is the reason this directory exists. The private working area holds **five**
`wheel_check*.json` records, all made on 2026-09-11, each with twelve complete successes — the
twelve successes stand. **Four** of them — `wheel_check.json` (20:27:28), `wheel_check2.json`
(20:46:31), `wheel_check3.json` (20:51:40) and `verify15/wheel_check15.json` (21:14:27) — came from
a runner that read `episode_contract_digest` from the top level of the publication manifest, where
the field does not live, and so recorded `contract_digest: null` twelve times each. The contract
digests printed beside those four runs were **declared** values, not values those runs captured.
They are not published here as though they had been recorded. The fifth,
`verify15/wheel_check15b.json` (21:16:03), did capture `b11bc1ac…` / `e8b8753d…`, and is the run
whose scoring path this directory's runner matches.

## How it was run

The runner refuses to start if the repository is on `sys.path`, which includes its own directory
once it lives in `reviews/`. It was therefore executed from a copy outside the repository, against a
throwaway environment holding nothing but the wheel and its pinned dependencies — never the
repository's own `.venv`.

    python installed_wheel_check.py <out.json> --wheel <path to the .whl>

## Which bytes ran

The copy that ran is `run_published_check.py` in the private working area: sha256
`27004bc7f62bb3108b6090e50d3c6a4f35467ca50819506041f4ec6ec471fbb8`, 12,311 bytes, written
2026-09-12 21:35:33. It wrote `uploaded_0.2.0.json` at 21:35:57 and `attested_build_0.2.0.json` at
21:36:37, and both records are published here byte-unchanged (`d31b81af…`, `4246c6be…`).

The file published in this directory hashes to
`893f2e6f56c5135d81a635af55cb7de91676921dac5c109e3e4ad6844668dc48`. It is that copy with its
**module docstring** corrected after the runs — first to name `verify15/wheel_check15b.json` in
place of a record that does not exist and to count the working area's five runs, then to add the
paragraph you are reading the other half of. Nothing outside the docstring differs: strip the module
docstring from both files and the remaining bytes are identical, so no imported name, no scripted
turn, no `env.evaluate()` call and no recorded row field moved. The twelve-of-twelve results here
are the results of these bytes, up to that docstring.

It was first published in this directory at commit `9cd0c95` hashing to `27004bc7…` — the executed
bytes exactly. That hash is superseded as this file's identity and retained above as the identity of
the bytes that produced the two records.
