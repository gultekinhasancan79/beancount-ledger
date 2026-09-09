"""The STARTUP WITNESS: everything a sealed
schedule claims, re-checked against this checkout and this evaluator BEFORE
request 1 — and again at the start of every resumed session.

    python tests/run_arms.py --schedule reviews/schedule_confirm1v2.json --dry-run

A sealed `schedule_id` binds the treatment, the world, the code and the
analysis plan (`tests/schedule_arms.build_experiment_contract`). Binding them
is only half the work: a hash nobody re-checks is a promise, and the pilot
already demonstrated what a process promise is worth ("we run from a pinned
worktree" — the cut-over happened mid-run anyway). This module is the
executable refusal. Every field of the experiment contract is recomputed here
from the live checkout, the installed libraries, the package and the active
release manifest, and any disagreement stops the run with the field named.

WHAT IT DOES NOT DO. It never runs a rollout and never calls a provider. The
most expensive check is `load_environment(selector)` once per selector, which
mints the world through the real serving door — the only authority on which
public task id a selector currently serves. `--dry-run` runs exactly the same
witness and prints it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import schedule_arms as SA  # noqa: E402


def _check(results: list[dict], field: str, expected, actual, note: str = "") -> None:
    results.append({"field": field, "expected": expected, "actual": actual,
                    "ok": expected == actual, "note": note})


def identity_checks(schedule: dict, *, root: Path | None = None, check_tree: bool = True) -> list[dict]:
    """THE GIT-PATH CONTRACT.

    v2 compared `git rev-parse HEAD` to the sealed `instrument_commit` for
    exact equality. That rule cannot be satisfied by its own storage
    workflow — the sealed schedule is committed into the repository, which
    moves HEAD — and a real seal showed the run failing its own witness for
    exactly that reason, with a diff confined to root notes files, a private
    notes directory and the schedule file.

    The replacement is not "ancestor instead of equal": a descendant may
    change Python. And it is not git alone either — the adversarial review of
    the first fix (attack 1(h)) defeated an all-git identity three ways
    without ever turning the witness red:

      (A) `git update-index --assume-unchanged <file>`, then edit it: status
          silent, `ls-tree` reports the sealed blob, digest recomputes sealed;
      (B) MODULE SHADOWING: a new `.py` beside the package — outside the three
          sealed subtrees, but `sys.path[0]` for every cell process;
      (C) a file inside `tests/` hidden by a `.gitignore` line committed on an
          EVIDENCE path: invisible to both `status` and `ls-tree`.

    So the PRIMARY identity is now the bytes ON DISK, over the WHOLE package
    directory minus a named exclusion list:

      `execution_tree_digest`       sha256 over the sorted (relative path,
                                    sha256 of the file's actual bytes) pairs
                                    under the execution root — PRIMARY
      `execution_tree_file_count`   sealed beside it, so an ADDED or REMOVED
                                    file is named as such — PRIMARY
      `execution_paths`/`_excludes` the sealed root and exclusion list are the
                                    ones this instrument still declares
      `runtime_environment_digest`  the BYTES of every installed distribution,
                                    every file no RECORD references, and the
                                    interpreter — PRIMARY
      `runtime_environment_*_count` the file and no-RECORD-reference counts,
                                    sealed beside it — PRIMARY
      `runtime_environment_uncovered_sys_path`
                                    the `sys.path` entries that NOTHING seals
                                    — neither the environment walk nor the
                                    execution tree. `[]` is the healthy state;
                                    a `PYTHONPATH` live at startup lands here
                                    and is named — PRIMARY
      `record_hash[...]`            a wheel's own RECORD-declared sha256 that
                                    the installed bytes no longer produce
      `python_version`              the interpreter's version string, beside
                                    its authenticated bytes
      `instrument_commit_ancestry`  the sealed commit is reachable from the
                                    runtime HEAD — SECONDARY evidence
      `execution_tree_unchanged`    `git diff <instrument>..HEAD` is EMPTY over
                                    those paths, changed files NAMED —
                                    SECONDARY
      `clean_execution_tree`        `git status` is clean over those paths; a
                                    dirty evidence file (reviews/,
                                    notes/, a root *.md) does NOT fail —
                                    SECONDARY

    The git rows are kept because they say something the walk cannot — which
    commit this content corresponds to, and what a reviewer would read as the
    diff — but they can no longer carry the identity on their own.

    The runtime HEAD is reported as its own row — informational, always `ok` —
    because under this contract it may legitimately differ from the sealed
    commit and the report must state both.
    """
    contract = schedule["experiment_contract"]
    results: list[dict] = []
    sealed_commit = contract.get("instrument_commit")
    head = SA.git_head(root)

    _check(results, "runtime_head", head, head,
           f"the checkout that will execute; the sealed instrument commit is {sealed_commit}")
    ancestor = SA.git_is_ancestor(sealed_commit, head, root)
    _check(results, "instrument_commit_ancestry", True, bool(ancestor),
           "" if ancestor else (f"the sealed instrument commit {sealed_commit} is not an ancestor of the "
                                f"runtime HEAD {head} (and is not it). This checkout is not a continuation "
                                f"of the sealed one."))
    _check(results, "execution_paths", contract.get("execution_paths"), list(SA.EXECUTION_PATHS),
           "the CLOSED set of paths whose content is the instrument")
    _check(results, "execution_excludes", contract.get("execution_excludes"), list(SA.EXECUTION_EXCLUDES),
           "what the on-disk walk skips: evidence, the interpreter's own libraries (bound instead by "
           "package_lock and the replay-contract digests), and build droppings")

    # THE PRIMARY IDENTITY: the bytes on disk, walked once.
    tree = SA.execution_tree_manifest(root)
    for problem in tree["unreadable"]:
        results.append({"field": "execution_tree_readable", "expected": "readable", "actual": problem,
                        "ok": False, "note": "an instrument file that cannot be read is a changed "
                                             "instrument"})
    _check(results, "execution_tree_file_count", contract.get("execution_tree_file_count"),
           len(tree["files"]),
           f"files present under {tree['execution_root']} after the sealed exclusions; a SHADOWING "
           f"module or a gitignore-hidden file adds one")
    _check(results, "execution_tree_digest", contract.get("execution_tree_digest"),
           SA.manifest_digest(tree),
           "sha256 over the sorted (relative path, sha256 of the file's ACTUAL BYTES) pairs ON DISK — "
           "not over git's index, which --assume-unchanged and .gitignore both lie to")
    _check(results, "instrument_identity_version", contract.get("instrument_identity_version"),
           SA.INSTRUMENT_IDENTITY_VERSION,
           "the ALGORITHM that computes the identity is part of the identity")

    # THE RUNTIME ENVIRONMENT, AS BYTES. The execution tree
    # stops at `.venv/**`; this is what makes "the same package versions" into
    # "the same executable instrument". Walked from the RUNNING interpreter's
    # own site-package roots (`sysconfig`/`sys.prefix`), never from a path
    # relative to this checkout — a worktree has no `.venv` at all.
    environment = SA.runtime_environment_manifest()
    for problem in environment["unreadable"]:
        results.append({"field": "runtime_environment_readable", "expected": "readable",
                        "actual": problem, "ok": False,
                        "note": "an installed file that cannot be read is a changed environment"})
    for record in environment["distributions"]:
        if record["declared_hash_mismatch"]:
            results.append({"field": f"record_hash[{record['name']}]", "expected": "RECORD hashes match",
                            "actual": record["declared_hash_mismatch"][:6], "ok": False,
                            "note": "the wheel's own RECORD declares a sha256 that the installed bytes "
                                    "do not produce"})
        if record["missing"]:
            results.append({"field": f"record_missing[{record['name']}]", "expected": "no missing file",
                            "actual": record["missing"][:6], "ok": False,
                            "note": "a RECORD-referenced file is gone: the distribution on disk is not "
                                    "the distribution that was installed"})
    _check(results, "runtime_environment_identity_version",
           contract.get("runtime_environment_identity_version"),
           SA.RUNTIME_ENVIRONMENT_IDENTITY_VERSION)
    _check(results, "python_version", contract.get("python_version"), environment["python_version"],
           "the interpreter's own version string, beside its authenticated bytes")
    _check(results, "runtime_environment_file_count", contract.get("runtime_environment_file_count"),
           len(environment["files"]),
           f"files under {environment['environment_roots']} plus the RECORD entries outside them and "
           f"the interpreter; an ADDED module is what no RECORD references")
    _check(results, "runtime_environment_extra_file_count",
           contract.get("runtime_environment_extra_file_count"), len(environment["extra_files"]),
           "files under site-packages that NO distribution's RECORD references — the site-packages "
           "analogue of the module-shadow attack")
    _check(results, "runtime_environment_stdlib_file_count",
           contract.get("runtime_environment_stdlib_file_count"), environment["stdlib_file_count"],
           "the STANDARD LIBRARY's own files: json, ssl, http, subprocess, asyncio all shape a "
           "provider request, and hashing pythonXY.dll does not cover their source")
    # THE IMPORT ENVIRONMENT (C1(b), the adversarial review).
    # `PYTHONPATH` is not a file under any walked root: a directory
    # named there is PREPENDED to `sys.path` and shadows any sealed module
    # while every hashed byte stays identical. The digest below now carries the
    # survey, so this row is not the only guard — but it is the one that NAMES
    # the offending path instead of reporting an opaque mismatch, and it fires
    # before the executor sanitizes the cell environment, so a `PYTHONPATH` set
    # at startup is caught at startup.
    uncovered = list(environment["uncovered_sys_path"])
    _check(results, "runtime_environment_uncovered_sys_path",
           contract.get("runtime_environment_uncovered_sys_path"), uncovered,
           "" if not uncovered else
           (f"{len(uncovered)} sys.path entr(ies) are covered by NEITHER the sealed environment roots "
            f"NOR the execution tree, so nothing seals what they can import:\n        "
            + "\n        ".join(uncovered)
            + "\n        Unset PYTHONPATH/PYTHONHOME for this shell and start the session again."))
    _check(results, "runtime_environment_digest", contract.get("runtime_environment_digest"),
           SA.environment_manifest_digest(environment),
           "sha256 over every installed distribution's actual bytes, its RECORD verdicts, the files no "
           "RECORD references, and the interpreter — not over version strings, which an in-place edit "
           "to openai/_client.py leaves untouched")

    # SECONDARY evidence: what git says about the same content.
    empty, changed = SA.git_diff_execution_paths(sealed_commit, head, root)
    _check(results, "execution_tree_unchanged", True, bool(empty),
           "" if empty else ("commits after the instrument commit changed EXECUTION content:\n        "
                             + "\n        ".join(changed[:12])))
    if check_tree:
        clean, detail = SA.git_execution_tree_status(root)
        _check(results, "clean_execution_tree", True, bool(clean), "" if clean else detail)
    return results


def witness(schedule: dict, *, root: Path | None = None, check_task_ids: bool = True,
            check_tree: bool = True, env_mod=None, mb_mod=None,
            journal_path: Path | None = None, window_ledger: Path | None = None) -> list[dict]:
    """One row per checked field: `{field, expected, actual, ok, note}`.

    A non-confirmatory (unsealed, v1) schedule has no experiment contract to
    witness and returns an empty list — the checks exist to enforce a sealed
    contract, not to invent one for a pilot.

    `journal_path` and `window_ledger` add the two PRE-REQUEST probes the
    executor requires: the execution journal must accept and read back an
    entry, and the shared window ledger must be healthy, both before request
    1. `run_arms.startup_results` always passes them; a caller that does not
    simply gets no such row, and never a false `ok`.
    """
    if not SA.is_confirmatory(schedule):
        return []
    contract = schedule["experiment_contract"]
    results: list[dict] = []

    if mb_mod is None:
        import measure_budget as mb_mod                                    # noqa: PLC0415
    if env_mod is None:
        from beancount_ledger import beancount_ledger as env_mod           # noqa: PLC0415

    # 1. The INSTRUMENT IDENTITY — the git-path contract, not commit equality.
    results += identity_checks(schedule, root=root, check_tree=check_tree)

    # 1b. The execution journal must work BEFORE any provider request:
    #     create, append, read back. A journal that fails open is a
    #     schedule whose every recording claim is conditional on nothing
    #     having gone wrong.
    if journal_path is not None:
        import run_arms as RA_mod                                          # noqa: PLC0415 -- lazy, avoids a cycle
        ok, detail = RA_mod.journal_probe(Path(journal_path))
        _check(results, "execution_journal", True, bool(ok), detail)

    # 1c. The shared provider-window ledger must be HEALTHY:
    #     malformed evidence refuses the session rather than being skipped
    #     line by line at read time.
    if window_ledger is not None:
        health = mb_mod.window_ledger_health(window_ledger)
        _check(results, "window_ledger_health", True, bool(health["healthy"]),
               health["detail"] or f"{health['line_count']} line(s), no malformed evidence")

    # 2. The analysis plan this schedule adopted, by content — and the plan
    #    NAME itself, checked before the digest. `analysis_plan` is joined
    #    onto reviews/, so a name carrying a path (`../elsewhere/plan.md`, an
    #    absolute path) resolves somewhere this witness does not govern. That
    #    used to surface only as an unexplained digest mismatch, or not at
    #    all if the file happened to exist; it is now named for what it is.
    plan_name = str(contract.get("analysis_plan") or "confirmatory_design.md")
    plan = (ROOT / "reviews" / plan_name)
    inside = False
    try:
        inside = plan.resolve().parent == (ROOT / "reviews").resolve()
    except OSError:
        inside = False
    _check(results, "analysis_plan_location", True, inside,
           "" if inside else (f"the sealed analysis_plan {plan_name!r} does not resolve to a file directly "
                              f"inside reviews/ (it resolves to {plan}); a pre-registration this witness "
                              f"cannot govern is not a pre-registration"))
    _check(results, "analysis_plan_sha256", contract.get("analysis_plan_sha256"),
           SA.sha256_file(plan) if inside else None, f"plan {plan_name}")

    # 3. The treatment behind every arm LABEL, from the presets that will
    #    actually be passed to the provider.
    arms = sorted(contract.get("arm_contract") or {})
    _check(results, "arm_contract", contract.get("arm_contract"), SA.arm_contract(arms))

    # 4. The episode contract, at the ceiling this schedule pins AND under the
    #    profile it sealed. Two profiles resolve two different contract views
    #    (legacy -> 4, cash_application -> 5), and the module-level default
    #    answers for the legacy one whatever was asked, so rechecking without
    #    the profile would "confirm" a cash-application seal against a view it
    #    never ran. A schedule sealed before the profile field existed is
    #    legacy by construction, which is exactly what the fallback says.
    ceiling = contract.get("max_episode_output_tokens")
    profile = contract.get("episode_contract_profile") or getattr(env_mod, "PROFILE_LEGACY", "legacy")
    actual_episode = None
    try:
        actual_episode = (env_mod.episode_contract_digest(ceiling, profile) if ceiling is not None
                          else env_mod.episode_contract_digest(
                              env_mod.MAX_EPISODE_OUTPUT_TOKENS, profile))
    except Exception as exc:                                               # noqa: BLE001
        actual_episode = f"unavailable: {type(exc).__name__}: {exc}"
    _check(results, "expected_episode_contract_digest",
           contract.get("expected_episode_contract_digest"), actual_episode)
    if contract.get("episode_contract_version") is not None:
        actual_version = None
        try:
            actual_version = env_mod.episode_contract_version(profile)
        except Exception as exc:                                           # noqa: BLE001
            actual_version = f"unavailable: {type(exc).__name__}: {exc}"
        _check(results, "episode_contract_version",
               contract.get("episode_contract_version"), actual_version)

    # 5. The replay contract, per arm, under the libraries installed HERE.
    versions = mb_mod.library_versions()
    for arm in arms:
        replay = bool(contract["arm_contract"][arm]["reasoning_replay"])
        _check(results, f"expected_replay_contract_digest[{arm}]",
               (contract.get("expected_replay_contract_digest_by_arm") or {}).get(arm),
               mb_mod.replay_contract_digest(replay, versions))

    # 6. The package lock. A dependency bump changes the provider-native
    #    projection without a line of this repository changing.
    _check(results, "package_lock", contract.get("package_lock"), SA.package_lock())

    # 7. The blind failure map, the quota table and the window rule.
    _check(results, "failure_map_digest", contract.get("failure_map_digest"), SA.failure_map_digest())
    _check(results, "provider_quotas", contract.get("provider_quotas"), SA.provider_quota_table())

    # 8. The active release manifest: a rotation makes the same selector
    #    string serve a different public world.
    expected_manifest = contract.get("manifest") or {}
    actual_manifest = SA.manifest_identity()
    for key in ("rotation_id", "manifest_content_digest"):
        _check(results, f"manifest.{key}", expected_manifest.get(key), actual_manifest.get(key))

    # 9. What each selector ACTUALLY serves right now, through the real door.
    if check_task_ids:
        expected_ids = contract.get("expected_public_task_id_by_selector") or {}
        for selector in sorted(expected_ids):
            try:
                env = env_mod.load_environment(selector)
                served = env.dataset[0]["info"]["task_id"] if len(env.dataset) else None
            except Exception as exc:                                       # noqa: BLE001
                served = f"unavailable: {type(exc).__name__}: {exc}"
            _check(results, f"public_task_id[{selector}]", expected_ids[selector], served)

    return results


def failures(results: list[dict]) -> list[dict]:
    return [r for r in results if not r["ok"]]


def format_results(results: list[dict]) -> list[str]:
    lines = []
    for r in results:
        mark = "ok  " if r["ok"] else "MISMATCH"
        if r["ok"]:
            lines.append(f"  {mark} {r['field']}")
        else:
            lines.append(f"  {mark} {r['field']}\n"
                         f"        sealed: {r['expected']}\n"
                         f"        actual: {r['actual']}"
                         + (f"\n        {r['note']}" if r.get("note") else ""))
    return lines


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--skip-task-ids", action="store_true",
                        help="skip the per-selector serving-door check (it mints every panel world)")
    args = parser.parse_args()

    schedule = SA.load_schedule(Path(args.schedule))
    if not SA.is_confirmatory(schedule):
        print(f"{Path(args.schedule).name} is not a sealed confirmatory schedule (no experiment contract): "
              f"there is nothing to witness. Seal it with tests/schedule_arms.py --seal.")
        return 1
    # The same two pre-request probes the executor runs:
    # the journal must accept and read back an entry, and the shared window
    # ledger must be healthy. Both are addressed exactly as `run_arms` will
    # address them, so this command witnesses the real paths.
    results = witness(schedule, check_task_ids=not args.skip_task_ids,
                      journal_path=SA.journal_path_for(ROOT / "reviews", schedule),
                      window_ledger=Path(str(args.schedule) + ".window.jsonl"))
    print(f"startup witness for {schedule['label']} ({schedule['schedule_id']})")
    print("\n".join(format_results(results)))
    bad = failures(results)
    print(f"\n{len(results) - len(bad)}/{len(results)} fields match")
    if bad:
        print("REFUSED: " + ", ".join(r["field"] for r in bad))
        return 2
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
