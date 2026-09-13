# The installable generator, measured (2026-09-13)

Round 17, decision 4 named a **delivery boundary**: `graph/cash_admit.py` loaded
`tests/world_checks.py` during reconstruction, the wheel deliberately ships no tests, and so a
generated cash-application instance could be served only from a repository checkout. Checkout
serving was established; an installable generator was not.

The checker moved into the runtime package — `beancount_ledger/world_checks.py` and
`beancount_ledger/graph/repair_keys.py`, with `tests/world_checks.py` and `tests/repair_keys.py`
left as shims that bind the old names to those same module objects, so there is one implementation
and the suites' behaviour is unchanged. This directory is the measurement that the move actually
closed the boundary.

Everything here is **offline**. No model, no API call, no network: the client is a script and every
number is deterministic in the identity, the profile and the secret.

## What is here

| file | what it is |
|---|---|
| `installable_serving_check.py` | the runner, byte for byte the copy that ran (`e59e4715…`). It mints from the installed package and serves both variants of every minted group through the real `env.evaluate()` door. |
| `installable_serving_0.2.0.json` | its record: artifact binding, where the admission battery resolved from, the battery's own negative control, three minted groups, six served variants. |
| `installed_wheel_recheck_0.2.0.json` | the **existing** eleven-authored-task installed check, re-run against the same wheel so the release claim stays true. Produced by `reviews/installed_wheel_check_2026-09-12/installed_wheel_check.py` at its published hash `893f2e6f…` — the published bytes themselves, run from a copy outside the repository. |

## The measurement

A wheel was built from this phase's working tree with `uv build --wheel`, installed into a **clean
throwaway virtual environment** created under the session scratchpad — never the repository's own
`.venv` — and both runners were executed from outside the repository with the repository asserted
absent from `sys.path` and the package path asserted to be inside `site-packages`.

| | value |
|---|---|
| wheel | `beancount_ledger-0.2.0-py3-none-any.whl`, sha256 `4c783b06dfca3785d6f502ce1dd31e8ddc31d1c828f16b9de98e8146bc5e0b5b`, 655,836 bytes |
| members / runtime members | 75 / 71 |
| RECORD / METADATA sha256 | `19a9871f…` / `0e7624d0…` |
| every runtime member matches the installed file | yes (the runner aborts before minting if one differs) |
| ships `tests/` or `reviews/` | no |
| admission battery in the wheel | `beancount_ledger/world_checks.py`, `beancount_ledger/graph/repair_keys.py` |
| interpreter | CPython 3.13.11, Windows, Unicode database 15.1.0 |
| pinned libraries | as `beancount_ledger.library_versions()` reports them: verifiers 0.3.1, openai 3.5.0, openai-agents 0.22.0, griffelib 2.2.0, pydantic 2.13.4, pydantic-core 2.46.4, datasets 5.0.1, beancount 3.2.3 |

**This is not the artifact on the Environments Hub.** The uploaded 0.2.0 wheel hashes to
`1c83e4c5…` and contains no cash-application generation that can run installed — which is the whole
reason this phase exists. The wheel above shares the version string and nothing else; it is a build
of the working tree that carries the moved checker.

### Where the battery came from

Recorded through `cash_admit._world_checks()` — the construction path's own accessor, not a second
import performed for the record:

    beancount_ledger.world_checks
    …\cleanvenv\Lib\site-packages\beancount_ledger\world_checks.py
    inside_the_installed_package: true      loaded_from_a_repository_checkout: false

### The battery's negative control

A battery that cannot speak is not evidence that it ran. `world_checker_problems` is called twice
over the same minted variant, through the construction path's entry point: once as that path calls
it, and once over contract inputs whose golden ledger has been replaced by the untouched opening
ledger (on a copy — `ContractInputs` refuses literal construction). The clean call returns nothing;
the tampered call returns three problems, the first being *"the golden scores 0.000000, not 1"*.
That is `check_derived`, the half that moved, speaking from `site-packages`.

### Minting and serving

One declared parent group per mechanism stratum, taken as a **prefix** of the frozen roster of
`cash-application-development-2` — nothing chooses a group by anything it drew. Minted under this
run's own throwaway secret and rotation, signed into a manifest in a temporary directory: never the
evaluator's provisioned key, never `~/.piv`, and no development bypass (this family has none, so the
only way to serve is to sign a real manifest and admit through it).

| group | mechanism | attempt | gates | minted |
|---|---|---|---|---|
| `…/fc-quarrymill/1/0` (`a6dd23b5…`) | fallback_continuation | 0 | 31 | yes |
| `…/cr-pikestaff/1/0` (`d3ee6385…`) | credit_residue | 0 | 31 | yes |
| `…/ar-tenterhook/1/0` (`bbc3d56d…`) | advice_residue | 0 | 31 | yes |

Then every variant of every group through the real door —
`list_files → read_file(ledger) → write_ledger(golden) → write_cash_application(golden register) →
submit` — with both deliverables taken from the **installed package's own** minted artifacts:

| selector | reward | `delivery.json` completion | score | register | composite | contract digest |
|---|---|---|---|---|---|---|
| `cash_application:cash-application-development-2:fc-quarrymill:0:a` | **1.0** | `complete` | `1` | `delivered` | `1` | `b11bc1ac…` |
| `…:fc-quarrymill:0:b` | **1.0** | `complete` | `1` | `delivered` | `1` | `b11bc1ac…` |
| `…:cr-pikestaff:0:a` | **1.0** | `complete` | `1` | `delivered` | `1` | `b11bc1ac…` |
| `…:cr-pikestaff:0:b` | **1.0** | `complete` | `1` | `delivered` | `1` | `b11bc1ac…` |
| `…:ar-tenterhook:0:a` | **1.0** | `complete` | `1` | `delivered` | `1` | `b11bc1ac…` |
| `…:ar-tenterhook:0:b` | **1.0** | `complete` | `1` | `delivered` | `1` | `b11bc1ac…` |

Six of six, `failures: []`. Every row's served public id is the one its record was signed for, the
profile is `cash_application`, and every `contract_digest` was **captured** from that episode's own
`piv_episode_contract_digest` state column and compared against the digest
`cash_application_001` serves under in the same process — never copied from a module constant.

### The authored eleven, re-checked

`installed_wheel_recheck_0.2.0.json`: twelve of twelve, `failures: []`, the eleven cash tasks at
`b11bc1ac…` and the `bank_recon_001` legacy control at `e8b8753d…`, each `complete` with score `1`
and the legacy receipt carrying no application block. The release claim of 2026-09-12 still holds on
a wheel built from this tree.

## What this establishes, and what it does not

1. **An installed package can now mint as well as serve.** That is the claim, and it is the only new
   claim here.
2. **No model was measured.** Nothing here supports a performance, difficulty or training claim.
3. **Three groups of ninety-six, and three structural templates.** A prefix of one stratum each says
   the path works; it is not a census, and the population's own census stays
   `reviews/cash_application_development_population_2026-09-13_replacement/`.
4. **The runtime is part of the evidence.** These runs minted and served in one process under CPython
   3.13.11 / Unicode 15.1.0, so nothing here carries a record preflighted under another runtime
   across to this one; runtime-scoped evidence is scoped by design, and re-preflighting is the answer
   rather than assuming.
5. **This wheel is not the published one.** See the artifact table above.

## How it was run

    uv build --wheel --out-dir <scratch>/dist .
    uv venv <scratch>/cleanvenv --python-preference only-managed
    uv pip install --python <scratch>/cleanvenv/Scripts/python.exe <scratch>/dist/*.whl
    cd <scratch>
    cleanvenv/Scripts/python.exe installable_serving_check.py out.json --wheel <wheel>
    cleanvenv/Scripts/python.exe installed_wheel_check.py out2.json --wheel <wheel>

Both runners refuse to start with the repository on `sys.path`, which includes their own directory
once they live under `reviews/`. They were therefore executed from copies outside the repository —
the published bytes in both cases, hashed above.
