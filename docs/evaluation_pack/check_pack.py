"""Verify this evaluation pack against the package in front of you.

    python check_pack.py               # verify
    python check_pack.py --write ...   # author-side: regenerate the two records

VERIFY (the external team's mode) checks, and exits 1 on the first group of
problems:

  1. `frozen_declaration.json` against the LIVE package: the family freeze
     digest and every declared literal, the Unicode-independent semantic
     components, the runtime-scoped parser digest for THIS interpreter's
     Unicode database (refusing a database the pack does not pin, by name),
     and both episode-contract digests as `load_environment` serves them for
     the authored reference tasks. No secret is needed: authored tasks are
     public.
  2. `evidence_index.json` against the repository files it names - only when
     run inside a checkout. From an installed wheel the evidence is not
     present, and the check says so instead of pretending.

WRITE (author-side only) regenerates both records from the live package and
the checkout, and takes `--source-commit` so the declaration names the
commit it describes rather than whatever HEAD happens to be.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DECLARATION = HERE / "frozen_declaration.json"
EVIDENCE = HERE / "evidence_index.json"

#: The complete result records and the provenance behind them, by path from
#: the repository root. Every path must exist at write time; at verify time a
#: missing or moved file is reported by name.
EVIDENCE_PATHS = (
    # the population this pack distributes, and its retired predecessor
    "reviews/cash_application_development_population_2026-09-13_replacement.md",
    "reviews/cash_application_development_population_2026-09-13_replacement/freeze.json",
    "reviews/cash_application_development_population_2026-09-13_replacement/census.json",
    "reviews/cash_application_development_population_2026-09-13_replacement/aggregates.json",
    "reviews/cash_application_development_population_2026-09-13_replacement/validation.json",
    "reviews/cash_application_development_population_2026-09-13_replacement/serving.json",
    "reviews/cash_application_development_population_2026-09-13_replacement/superseded_rejections.json",
    "reviews/cash_application_development_population_2026-09-13.md",
    # the one screen on the generated population: incomplete, nine of twelve
    "reviews/cash_application_generated_screen_2026-09-13.md",
    "reviews/cash_application_generated_screen_2026-09-13/README.md",
    "reviews/cash_application_generated_screen_2026-09-13/cash_screen_1_selection.py",
    "reviews/cash_application_generated_screen_2026-09-13/rescore_cash_screen_1.py",
    "reviews/cash_application_generated_screen_2026-09-13/rescore_cash_screen_1.json",
    "reviews/cash_application_generated_screen_2026-09-13/cash_screen_1_runner.log",
    "reviews/cash_screen_1_selection_2026-09-13.json",
    "reviews/cash_screen_1_retrospective_census_2026-09-13.json",
    "reviews/budget_qwen3.7-max-2026-05-20_2026-09-13_cash_screen_1.json",
    # the authored-variant screens and the cold adjudication
    "reviews/cash_application_screen_2026-09-10.md",
    "reviews/cash_application_six_variant_screen_2026-09-11.md",
    "reviews/cash_application_adjudication_2026-09-10.md",
    "reviews/cash_application_adjudication_2026-09-10/predeclared.md",
    "reviews/cash_application_adjudication_2026-09-10/cash_adjudication.jsonl",
    "reviews/qwen_authored_calibration_2026-09-08.md",
    # the fixed-panel study on the bank family (the only multi-model study)
    "reviews/confirmatory_design.md",
    "reviews/schedule_confirm1v4.json",
    "reviews/arms_confirm1v4.md",
    # release provenance and the installed-artifact checks
    "reviews/RELEASE_ATTESTATION.md",
    "reviews/installable_serving_check_2026-09-14/README.md",
    "reviews/installable_serving_check_2026-09-14/installable_serving_0.3.0.json",
    "reviews/installable_serving_check_2026-09-14/installed_wheel_recheck_0.3.0.json",
    "reviews/installable_serving_check_2026-09-13/installable_serving_check.py",
    "reviews/installed_wheel_check_2026-09-12/installed_wheel_check.py",
    # the runtime-scoped digests, pinned per Unicode database
    "tests/legacy_freeze.json",
    "tests/unicode_pins.py",
)

#: The runtime-scoped parser component per Unicode database, with its
#: provenance. `parse_policy_view()` records `unicodedata.unidata_version`,
#: so this one component legitimately moves with the interpreter's Unicode
#: database and nothing else moves. Rows come from `tests/legacy_freeze.json`'s
#: `unicode_scoped` map at write time; a database not pinned there is refused
#: by name at verify time rather than believed.
UNICODE_NOTE = ("the parser component is parse_policy_digest(); it records unicodedata.unidata_version, so it is "
                "pinned per Unicode database with the provenance tests/unicode_pins.py requires. A database this "
                "table does not carry is an UNVERIFIED runtime for this pack, not a passing one.")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_package():
    sys.path.insert(0, str(ROOT))
    try:  # the dataset library's progress bars are noise on a check's terminal
        import datasets
        datasets.disable_progress_bars()
    except Exception:  # noqa: BLE001
        pass
    from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
    from beancount_ledger.graph import cash_manifest as FM  # noqa: E402
    from beancount_ledger.graph import cash_population as CP  # noqa: E402
    return env_mod, FM, CP


def live_declaration(source_commit: str | None) -> dict:
    env_mod, FM, CP = load_package()
    freeze = CP.freeze_record()
    components = dict(FM.semantic_components())
    parser_now = components.pop("parser")
    freeze_json = json.loads((ROOT / "tests" / "legacy_freeze.json").read_text(encoding="utf-8"))
    parser_rows = {}
    for version, row in sorted(freeze_json["unicode_scoped"].items()):
        parser_rows[version] = {
            "parser": row["scorer"]["parse_policy_digest"],
            "scorer_contract_digest": row["scorer"]["scorer_contract_digest"],
            "provenance": row.get("provenance"),
        }
    native = unicodedata.unidata_version
    if native in parser_rows and parser_rows[native]["parser"] != parser_now:
        raise SystemExit(f"the live parser component {parser_now} != the pinned {parser_rows[native]['parser']} "
                         f"for unicode {native}; refusing to write a declaration that contradicts the freeze")
    authored = env_mod.load_environment("cash_application_001")
    legacy = env_mod.load_environment()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8") if (ROOT / "pyproject.toml").is_file() else ""
    version = None
    for line in pyproject.splitlines():
        if line.strip().startswith("version"):
            version = line.split("=", 1)[1].strip().strip('"')
            break
    release = {}
    record = ROOT / "reviews" / "installable_serving_check_2026-09-14" / "installable_serving_0.3.0.json"
    if record.is_file():
        artifact = json.loads(record.read_text(encoding="utf-8")).get("artifact", {})
        release = {k: artifact.get(k) for k in ("wheel", "wheel_sha256", "wheel_bytes", "members", "runtime_members")}
        release["measured_in"] = "reviews/installable_serving_check_2026-09-14/"
    return {
        "schema": "piv.evaluation-pack.declaration/1",
        "describes": {
            "package_version": version,
            "source_commit": source_commit,
            "release_artifact": release,
            "hub_entry": "cangultekn/beancount-ledger (0.2.0 as of 2026-09-14; 0.3.0 is the owner's upload, "
                         "and it is a new version, not a rebuilt 0.2.0)",
        },
        "family_freeze": {
            "schema": freeze["schema"],
            "digest": freeze["digest"],
            "declared": freeze["declared"],
        },
        "semantic_components_unicode_independent": components,
        "runtime_scoped_by_unicode_database": {"note": UNICODE_NOTE, "rows": parser_rows},
        "episode_contracts": {
            "cash_application": {"reference_task": "cash_application_001", "profile": authored.profile,
                                 "digest": authored.episode_contract_digest()},
            "legacy": {"reference_task": "bank_recon_001", "profile": legacy.profile,
                       "digest": legacy.episode_contract_digest()},
            "note": ("episode settings (turns, token budgets) are part of the contract digest; rows taken under "
                     "different budgets are different arms and must never be pooled"),
        },
        "library_versions": env_mod.library_versions(),
    }


def verify_declaration(problems: list) -> None:
    if not DECLARATION.is_file():
        problems.append("frozen_declaration.json is missing")
        return
    env_mod, FM, CP = load_package()
    declared = json.loads(DECLARATION.read_text(encoding="utf-8"))
    freeze = CP.freeze_record()
    for issue in CP.freeze_problems():
        problems.append(f"live freeze: {issue}")
    if not freeze.get("declared_matches_live"):
        problems.append("the live freeze does not match the package's own declared literals")
    if freeze["digest"] != declared["family_freeze"]["digest"]:
        problems.append(f"freeze digest: live {freeze['digest']} != pack {declared['family_freeze']['digest']}")
    # Compare as JSON: the live literals hold tuples, the pack holds lists.
    live_declared = json.loads(json.dumps(freeze["declared"]))
    if live_declared != declared["family_freeze"]["declared"]:
        for key in sorted(set(live_declared) | set(declared["family_freeze"]["declared"])):
            if live_declared.get(key) != declared["family_freeze"]["declared"].get(key):
                problems.append(f"declared literal {key}: live {live_declared.get(key)!r} != "
                                f"pack {declared['family_freeze']['declared'].get(key)!r}")
    components = dict(FM.semantic_components())
    parser_now = components.pop("parser")
    if components != declared["semantic_components_unicode_independent"]:
        problems.append("the Unicode-independent semantic components differ from the pack's")
    rows = declared["runtime_scoped_by_unicode_database"]["rows"]
    native = unicodedata.unidata_version
    if native not in rows:
        problems.append(f"unicode {native} is NOT pinned by this pack (pinned: {sorted(rows)}); this interpreter's "
                        f"Unicode database is an unverified runtime for the pack, not a passing one")
    elif rows[native]["parser"] != parser_now:
        problems.append(f"parser component for unicode {native}: live {parser_now} != pinned {rows[native]['parser']}")
    for key, task in (("cash_application", "cash_application_001"), ("legacy", "bank_recon_001")):
        env = env_mod.load_environment(task)
        want = declared["episode_contracts"][key]
        if env.profile != want["profile"] or env.episode_contract_digest() != want["digest"]:
            problems.append(f"episode contract {key}: served {env.profile}/{env.episode_contract_digest()} != "
                            f"pack {want['profile']}/{want['digest']}")
    if env_mod.library_versions() != declared["library_versions"]:
        problems.append(f"library versions differ from the pack's: {env_mod.library_versions()}")


def evidence_rows() -> dict:
    rows = {}
    for rel in EVIDENCE_PATHS:
        path = ROOT / rel
        if not path.is_file():
            raise SystemExit(f"evidence file missing at write time: {rel}")
        rows[rel] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    return rows


def verify_evidence(problems: list, notes: list) -> None:
    if not EVIDENCE.is_file():
        problems.append("evidence_index.json is missing")
        return
    index = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if not (ROOT / "reviews").is_dir():
        notes.append("not a repository checkout: the evidence files are not present here, so their digests were "
                     "not checked (they are checked from a checkout of the declared source commit)")
        return
    for rel, want in index["files"].items():
        path = ROOT / rel
        if not path.is_file():
            problems.append(f"evidence missing: {rel}")
        elif sha256_file(path) != want["sha256"]:
            problems.append(f"evidence changed: {rel}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="author-side: regenerate both records")
    parser.add_argument("--source-commit", default=None, help="the commit the declaration describes (with --write)")
    args = parser.parse_args()

    if args.write:
        if not args.source_commit:
            raise SystemExit("--write needs --source-commit <sha>: the declaration names what it describes")
        declaration = live_declaration(args.source_commit)
        DECLARATION.write_text(json.dumps(declaration, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                               newline="\n")
        index = {"schema": "piv.evaluation-pack.evidence-index/1", "source_commit": args.source_commit,
                 "files": evidence_rows()}
        EVIDENCE.write_text(json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {DECLARATION.name} (freeze {declaration['family_freeze']['digest']}) and "
              f"{EVIDENCE.name} ({len(index['files'])} files)")

    problems, notes = [], []
    verify_declaration(problems)
    verify_evidence(problems, notes)
    for note in notes:
        print(f"NOTE  {note}")
    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        return 1
    declared = json.loads(DECLARATION.read_text(encoding="utf-8"))
    print(f"PASS  the package in front of you is the frozen generator "
          f"{declared['family_freeze']['digest']} (source {declared['describes']['source_commit']}), "
          f"under unicode {unicodedata.unidata_version}"
          + ("" if notes else f"; {len(json.loads(EVIDENCE.read_text(encoding='utf-8'))['files'])} evidence "
                              f"files bound"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
