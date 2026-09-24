# Environments Hub upload of 0.3.0.post1 (24 September 2026)

The owner published `cangultekn/beancount-ledger` version 0.3.0.post1 to the Prime Intellect
Environments Hub on 24 September 2026. This file records the upload. It sits beside the earlier
publication records in `reviews/RELEASE_ATTESTATION.md` and does not edit them. Background, the
15 September deletion and the version decision are in `docs/dev_journal/2026-09-24.md`.

## What was uploaded

- Source commit of the export: `62df434706192cedc8d91050d0048c6b306a0bfb` (branch
  `docs/hub-republish`, pull request #12). The four exported paths (`README.md`, `pyproject.toml`,
  `LICENSE`, `beancount_ledger/`) are identical to `80ff82b`, the commit the two advisory reviews
  and the installed-wheel checks covered.
- Export: `git archive --format=zip` of those four paths, unpacked into a new folder, pushed from
  there with prime CLI 0.7.3: `prime env push --visibility PUBLIC --runtime v0`.
- `.prime/.env-metadata.json` written by the CLI in the export folder:

  ```json
  {
    "environment_id": "dhp3317m32twj7z0rxfl37r6",
    "owner": "cangultekn",
    "name": "beancount-ledger",
    "pushed_at": "2026-09-24T14:30:24.528561",
    "wheel_sha256": "425d339b71f82cd8a68ba7b6234fc713d09c5540f39b7e1a945439082f5e33f9",
    "version": "0.3.0.post1"
  }
  ```

## Checks after the upload

- The wheel the push built (`dist/beancount_ledger-0.3.0.post1-py3-none-any.whl` in the export
  folder): 654,867 bytes, sha256 `425d339b71f82cd8a68ba7b6234fc713d09c5540f39b7e1a945439082f5e33f9`,
  `WHEEL` `Generator: hatchling 1.32.4`. This is byte-for-byte the local build the journal's 02:30
  entry verified (installed_wheel_check 12/12, installable_serving_check 6/6 at reward 1.0), so no
  difference needs explaining.
- Member audit of that wheel: 75 members; none under `tests/`, `reviews/`, `outputs/` or
  `solutions/`; no `.piv`, `eval_secret` or `adversary` in a member name; no `.pyc` or
  `__pycache__`.
- The wheel the Hub serves, downloaded from
  `https://hub.primeintellect.ai/cangultekn/beancount-ledger/@70c0a4cc/beancount_ledger-0.3.0.post1-py3-none-any.whl`:
  HTTP 200, 654,867 bytes, sha256 `425d339b71f82cd8a68ba7b6234fc713d09c5540f39b7e1a945439082f5e33f9`,
  the same bytes.
- Unauthenticated `GET https://api.primeintellect.ai/api/v1/environmentshub/cangultekn/beancount-ledger/@latest`:
  HTTP 200, `visibility` `PUBLIC`, `runtime` `VERIFIERS_V0`, `verifiers_requirement` `==0.3.1`,
  environment id `dhp3317m32twj7z0rxfl37r6`, version id `d9tegkwd7h7ic1wfkffoc1c1`, source archive
  `beancount-ledger-0.3.0.post1.tar.gz` (sha256 `96dc890893e0481bc9893750a6b11d59917b0a5d2a29ffb6963765804869a444`),
  `created_at` `2026-09-24T11:30:19.930000` (UTC).

## Relation to earlier uploads

The environment id is new. The 14 September upload of 0.3.0 used environment
`fv9m1f3tke0b41xmofm5lqfn` and wheel `27be094f…`; the owner deleted that environment with all its
versions on 15 September. 0.1.0, 0.2.0 and 0.3.0 cannot be installed from the Hub. Their records in
`reviews/RELEASE_ATTESTATION.md` stand as written.
