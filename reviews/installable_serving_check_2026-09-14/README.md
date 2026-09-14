# The 0.3.0 artifact, measured (2026-09-14)

The release evidence for **beancount-ledger 0.3.0**: a wheel built from this tree, installed into a
clean throwaway virtual environment, **mints** a declared group of the released development
population and **serves** both its variants, and still scores the eleven authored cash-application
tasks and a legacy control.

This repeats, against the 0.3.0 artifact, the check
[`reviews/installable_serving_check_2026-09-13/`](../installable_serving_check_2026-09-13/) made
against a 0.2.0-versioned build of the pre-release tree. Nothing here was uploaded: **publishing is
the owner's act**, and no upload, re-upload or withdrawal happens in this repository.

Everything here is **offline**. No model, no API call, no network: both clients are scripts and
every number is deterministic in the identity, the profile and the secret.

## What is here

| file | what it is |
|---|---|
| `installable_serving_0.3.0.json` | the minting-and-serving record: artifact binding, where the admission battery resolved from, the battery's own negative control, three minted groups, six served variants |
| `installed_wheel_recheck_0.3.0.json` | the eleven-authored-task installed check plus a legacy control, re-run against the same wheel so the earlier release claim stays true under the new version |

**The runners are the published bytes, not new code.** Neither is copied here, because each already
stands in the directory where it was published, and a second copy is a second thing that can drift:

| runner | published at | sha256 |
|---|---|---|
| minting and serving | `reviews/installable_serving_check_2026-09-13/installable_serving_check.py` | `e59e47151d2f8122cc4a07f3ffd698f07810337e2eb87f60adafbefa5357e841` |
| the authored twelve | `reviews/installed_wheel_check_2026-09-12/installed_wheel_check.py` | `893f2e6f56c5135d81a635af55cb7de91676921dac5c109e3e4ad6844668dc48` |

Both were executed from copies taken **outside** the repository, at exactly those hashes, with no
edit of any kind. Their own headers document what each does and what was added to them for
publication.

## The artifact

`uv build`, hatchling, from this checkout. Built twice and **byte-identical both times**.

| | value |
|---|---|
| wheel | `beancount_ledger-0.3.0-py3-none-any.whl`, sha256 `52665840cfff99813ef65248f162fefaa43b56c48b886f42668adc1e6dfc8457`, 657,365 bytes |
| sdist | `beancount_ledger-0.3.0.tar.gz`, sha256 `769594488becdd6f278e3d27be776247b89292aa7a630520446a4e683f38434c`, 598,709 bytes |
| members / runtime members | 75 / 71 |
| RECORD / METADATA sha256 | `22b0fd26…` / `e253d539…` |
| every runtime member matches the installed file | yes (the runner aborts before minting if one differs) |
| ships `tests/`, `reviews/`, a `.pyc` or a `__pycache__` | no |
| admission battery in the wheel | `beancount_ledger/world_checks.py`, `beancount_ledger/graph/repair_keys.py` |
| interpreter | CPython 3.13.11, Windows, Unicode database 15.1.0 |
| pinned libraries | as `beancount_ledger.library_versions()` reports them: verifiers 0.3.1, openai 3.5.0, openai-agents 0.22.0, griffelib 2.2.0, pydantic 2.13.4, pydantic-core 2.46.4, datasets 5.0.1, beancount 3.2.3 |

**0.3.0 is a new version, not a rebuilt 0.2.0.** The wheel uploaded to the Environments Hub hashes
to `1c83e4c5…`, is version 0.2.0, and contains no cash-application generation that can run
installed. It is not rebuilt, re-uploaded or withdrawn by anything here, and no artifact built from
this tree carries its version string: that is the whole reason the correction ships as 0.3.0.

## Where the battery came from

Recorded through `cash_admit._world_checks()` — the construction path's own accessor, not a second
import performed for the record:

    beancount_ledger.world_checks
    …\cv030\Lib\site-packages\beancount_ledger\world_checks.py
    inside_the_installed_package: true      loaded_from_a_repository_checkout: false

## The battery's negative control

A battery that cannot speak is not evidence that it ran. `world_checker_problems` is called twice
over the same minted variant, through the construction path's entry point: once as that path calls
it, and once over contract inputs whose golden ledger has been replaced by the untouched opening
ledger, on a copy. Clean: **silent**. Tampered: **three problems**, the first of which is

    the golden scores 0.000000, not 1

## Minting — three declared groups, one per mechanism stratum

A prefix of the frozen roster of `cash-application-development-2`, not a sample: nothing chooses a
group by anything it drew. Minted by the installed package under the run's **own throwaway secret
and rotation**, with the family manifest in a temporary directory — never the evaluator's
provisioned key, never `~/.piv`, and no development bypass, because this family has none.

| group | mechanism | split | attempt | gates evaluated / passed |
|---|---|---|---|---|
| `…/fc-quarrymill/1/0` | fallback continuation | `development` | 0 | 31 / all |
| `…/cr-pikestaff/1/0` | credit residue | `development` | 0 | 31 / all |
| `…/ar-tenterhook/1/0` | advice residue | `development` | 0 | 31 / all |

Three groups, three attempts, zero exhausted, group acceptance 1.000.

## Serving — six of six

All six variants signed into that manifest and served through the real `env.evaluate()` door with a
scripted offline client delivering the installed package's own golden ledger and golden register.

**Six of six at reward 1.0**, `delivery.json` `complete`, score `1`, register `delivered`, composite
`1`, each served id the one its record was signed for, profile `cash_application`, and every
episode-contract digest **captured from its own state column** and equal to the digest
`cash_application_001` serves under in the same process (`b11bc1ac…`). `failures: []`.

## The authored twelve — twelve of twelve

On the same wheel, with the published 2026-09-12 runner: `cash_application_001`..`011` at reward
1.0, `complete`, register `delivered`, composite `1`, contract `b11bc1ac…`, and `bank_recon_001` at
reward 1.0, `complete`, contract `e8b8753d…` with no application block, as a legacy receipt must be.
`failures: []`.

## The claim, stated exactly

A package installed from the **0.3.0** wheel built from this tree can mint a declared
cash-application group of the released development population and serve both its variants, and it
still scores the eleven authored cash tasks and a legacy control. The evaluation split is not
opened here and no selector spells it. **No model or API call was made**, and no difficulty,
performance, training or generalization claim is made or implied.
