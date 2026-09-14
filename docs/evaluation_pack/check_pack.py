"""Verify this evaluation pack against the package in front of you.

    python check_pack.py                        # verify
    python check_pack.py --wheel PATH           # verify, and bind the installed files to the released wheel
    python check_pack.py --record PATH          # verify, and write what was observed to PATH
    python check_pack.py --write --source-commit SHA [--pack-commit SHA]
                                                # author-side: regenerate the two records

VERIFY (the external team's mode) prints one PASS/FAIL line per check and one
NOTE line per thing that is reported rather than verified, and exits 1 if any
check failed. The two kinds of statement are kept apart on purpose, because a
printed reference identity is not an observed one:

  VERIFIED - a FAIL means the package in front of you is not the declared one.
    portable  the declared literals (`freeze_record()["declared"]`),
              `freeze_problems()` empty, the Unicode-independent semantic
              components, the runtime-independent census components, the
              parser and scorer-contract digests for THIS interpreter's
              Unicode database (a database the pack does not pin is refused
              by name), both episode-contract digests as `load_environment`
              serves them, and the pinned library versions. None of these
              depends on the interpreter's version, OS or architecture, so
              equality is demanded on every runtime.
    source    the installed package's tree digest over the logical text of
              its runtime files, computed from wherever `beancount_ledger`
              imports - a wheel install and a checkout alike - and its
              `importlib.metadata` version. This is what establishes that the
              source bytes are the declared ones; a commit hash cannot.
    wheel     with --wheel PATH: the wheel's sha256 against the declaration's
              and every RECORD-listed runtime member against the installed
              file. Without the flag the wheel is not checked, and the output
              says so.
    evidence  in a checkout: every indexed file's sha256 and size, and that no
              file under an indexed directory is missing from the index. The
              bytes bound are the ones a clean checkout yields (LF, under
              `.gitattributes`); a working copy holding an indexed text file
              with CRLF fails as "line endings only", with the fix named.

  REPORTED - printed, written with --record, never a FAIL on its own.
    runtime   this evaluator's WHOLE freeze digest and native runtime next to
              the reference runtime's. `freeze_record()`'s digest covers the
              declared literals AND `runtime_freeze()`: the baseline-catalogue
              digest (bound to predicate bytecode), the Unicode-scoped parser
              and the native runtime (implementation, version, OS, machine).
              It therefore reproduces on the reference runtime and is
              legitimately different on any other; demanding equality would
              reject a correct installation on Linux or CPython 3.11/3.13.
              The manifest's own serving-door checks (`cash_manifest.admit`)
              re-read all of it natively and are untouched by this. On the
              reference runtime itself the digest MUST reproduce, and there a
              difference is a FAIL.
    origin    the observed checkout commit (`git rev-parse HEAD`, read-only)
              next to the declaration's `reference_source_commit` (the commit
              the declaration describes) and `pack_commit` (the later commit
              that carries the pack). Commits are reported, not verified.

WRITE (author-side only) regenerates both records from the live package and
the checkout. `--source-commit` names the commit the declaration describes
rather than whatever HEAD happens to be; `--pack-commit` names the commit that
carries the pack, or `unpublished` while it has none.
"""

from __future__ import annotations

import argparse
import ast
import base64
import csv
import hashlib
import importlib.metadata
import io
import json
import subprocess
import sys
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DECLARATION = HERE / "frozen_declaration.json"
EVIDENCE = HERE / "evidence_index.json"
PACKAGE = "beancount_ledger"
DISTRIBUTION = "beancount-ledger"

#: The runtime the whole-freeze digest was observed on when the population
#: was minted, and the digest it produced there. RETAINED AS THE REFERENCE:
#: this is the digest the published census, serving record and screen carry.
#: It is compared strictly only on this runtime; elsewhere it is reported.
REFERENCE_RUNTIME = {
    "implementation": "CPython",
    "version": "3.12.12",
    "system": "Windows",
    "machine": "AMD64",
    "unicode_database": "15.0.0",
}
REFERENCE_WHOLE_FREEZE_DIGEST = "b371a45a0186648e40c7aa18f03efb28"
REFERENCE_BASELINE_CATALOGUE_DIGEST = "b7fa69753bcf1f5e732968f2819696a4"

#: The census components (`cash_gate.component_versions()`) that are a
#: function of the runtime, not of the source: the baseline-catalogue digest
#: binds compiled predicate bytecode (`cash_manifest.predicate_digest`), the
#: semantic components carry the Unicode-scoped parser (pinned separately
#: below), and the runtime scope IS the native runtime. Everything else in
#: that view is a declared literal and is compared strictly.
RUNTIME_SCOPED_CENSUS_COMPONENTS = ("baseline_catalogue_digest", "semantic_components", "runtime_scope")

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
    # the truth reconstruction the offline replay of the application channel
    # runs on; the rescore imports it (its other tests/ imports are found by
    # reading the rescore, see `rescore_test_imports`)
    "tests/observed_truth.py",
    # the runner and its suite, recorded separately from the package (round 19,
    # decision 1: "recording the runner separately")
    "tests/measure_budget.py",
    "tests/test_measure_budget.py",
)

#: Directories whose EVERY file is evidence: the nine recovered workspaces
#: (the public inputs, both delivered artifacts and the delivery receipt of
#: each scored cell) and the counterfactual arms. Without them the advertised
#: offline replay cannot run, so the index carries each file, and at verify
#: time a file under one of these that the index does not name is a failure.
EVIDENCE_DIRECTORIES = (
    "reviews/cash_application_generated_screen_2026-09-13/workspaces",
    "reviews/cash_application_generated_screen_2026-09-13/counterfactual",
)

#: The rescore whose imports from tests/ are indexed with it.
RESCORE = "reviews/cash_application_generated_screen_2026-09-13/rescore_cash_screen_1.py"

#: The runtime-scoped parser component per Unicode database, with its
#: provenance. `parse_policy_view()` records `unicodedata.unidata_version`,
#: so this one component legitimately moves with the interpreter's Unicode
#: database and nothing else moves. Rows come from `tests/legacy_freeze.json`'s
#: `unicode_scoped` map at write time; a database not pinned there is refused
#: by name at verify time rather than believed.
UNICODE_NOTE = ("the parser component is parse_policy_digest(); it records unicodedata.unidata_version, so it and "
                "scorer_contract_digest() are pinned per Unicode database with the provenance tests/unicode_pins.py "
                "requires, and both are compared strictly against the running interpreter's own database. A "
                "database this table does not carry is an UNVERIFIED runtime for this pack, not a passing one.")

PORTABLE_NOTE = ("everything under this key is a function of the source alone and is compared strictly on every "
                 "runtime. The WHOLE freeze digest is not here: freeze_record() folds runtime_freeze() into it - the "
                 "baseline-catalogue digest over predicate bytecode, the Unicode-scoped parser and the native "
                 "runtime - so it reproduces only on the reference runtime and is recorded under "
                 "reference_runtime_attestation instead.")

REFERENCE_NOTE = ("the whole-freeze digest freeze_record()['digest'] as observed on the runtime that minted the "
                  "released population; the published census, serving record and screen carry this value. An "
                  "evaluator on another runtime computes and records its OWN whole-freeze digest, which check_pack "
                  "prints and writes with --record; a difference there is expected and is not a failure. On this "
                  "exact runtime the digest must reproduce.")

PACKAGE_TREE_METHOD = (
    "every file under the imported beancount_ledger package directory except __pycache__/ and *.pyc, sorted by "
    "POSIX relative path from the package's parent (so 'beancount_ledger/graph/cash_gate.py'); per file, "
    "sha256(relpath + '\\n' + text) where text is the file's logical text - strict UTF-8, CRLF and CR mapped to "
    "LF, the same rule beancount_ledger.logical_text applies to delivered artifacts; the tree digest is sha256 "
    "over the concatenated raw per-file digests in that order. Logical text rather than stored bytes because the "
    "released 0.3.0 wheel was built from a Windows checkout and carries CRLF in graph/cash_profile.py while a "
    "clean checkout under .gitattributes (eol=lf) has LF: same source, different bytes. The stored-bytes tree "
    "digest is recorded beside it and REPORTED at verify time, not demanded."
)


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:30]:
            print(f"      {line}")
    return ok


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refuse_piv(path: Path, what: str) -> Path:
    """The pack's rule: nothing it runs writes under ~/.piv, where the
    evaluator's own secret and manifest live."""
    resolved = path.expanduser().resolve()
    piv = (Path.home() / ".piv").resolve()
    if resolved == piv or piv in resolved.parents:
        raise SystemExit(f"refusing to write {what} under {piv}: the pack never writes into the evaluator's key store")
    return resolved


def load_package():
    sys.path.insert(0, str(ROOT))
    try:  # the dataset library's progress bars are noise on a check's terminal
        import datasets
        datasets.disable_progress_bars()
    except Exception:  # noqa: BLE001
        pass
    from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
    from beancount_ledger.candidate import canonical as CANON  # noqa: E402
    from beancount_ledger.graph import cash_gate as G  # noqa: E402
    from beancount_ledger.graph import cash_manifest as FM  # noqa: E402
    from beancount_ledger.graph import cash_population as CP  # noqa: E402
    return env_mod, FM, CP, G, CANON


def package_dir() -> Path:
    import beancount_ledger
    return Path(beancount_ledger.__file__).resolve().parent


def native_runtime(FM) -> dict:
    scope = FM.runtime_scope()
    return {**scope["native_runtime"], "unicode_database": scope["unicode_database"]}


def describe_runtime(runtime: dict) -> str:
    return (f"{runtime['implementation']} {runtime['version']} {runtime['system']} {runtime['machine']} "
            f"unicode {runtime['unicode_database']}")


# --------------------------------------------------------------------------
# the source in front of you
# --------------------------------------------------------------------------

def logical_bytes(raw: bytes) -> bytes | None:
    """The logical text of a runtime file, or None when it is not UTF-8 text."""
    try:
        return raw.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    except UnicodeDecodeError:
        return None


def package_tree(directory: Path, read=None) -> dict:
    """Both tree digests over the package's runtime files, per the method
    above, plus one logical-text digest per file so a mismatch can be named.
    `read(relpath) -> bytes` is the write-time clean-checkout reader; at
    verify time the bytes on disk are what is hashed."""
    files = sorted((p for p in directory.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"),
                   key=lambda p: p.relative_to(directory.parent).as_posix())
    per_file, not_text, cr_bearing = {}, [], []
    logical, stored = hashlib.sha256(), hashlib.sha256()
    for path in files:
        rel = path.relative_to(directory.parent).as_posix()
        raw = read(rel) if read is not None else path.read_bytes()
        text = logical_bytes(raw)
        if text is None:
            not_text.append(rel)
            text = raw
        elif text != raw:
            cr_bearing.append(rel)
        digest = hashlib.sha256(rel.encode("utf-8") + b"\n" + text).digest()
        per_file[rel] = digest.hex()
        logical.update(digest)
        stored.update(hashlib.sha256(rel.encode("utf-8") + b"\n" + raw).digest())
    return {
        "files": len(files),
        "logical_text_digest": logical.hexdigest(),
        "stored_bytes_digest": stored.hexdigest(),
        "per_file_logical_text": per_file,
        "not_utf8_text": not_text,
        "cr_bearing": cr_bearing,
    }


def installed_version() -> str | None:
    try:
        return importlib.metadata.version(DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError:
        return None


def observed_checkout_commit(root: Path) -> str | None:
    """`git rev-parse HEAD` in the import root, read-only; None when the
    root is not a checkout or git is not there to ask."""
    if not (root / ".git").exists():
        return None
    try:
        done = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def git_eol_map(root: Path) -> dict:
    """`git ls-files --eol -z` over the checkout, read-only: tracked path ->
    (line endings in the index, line endings in this working copy)."""
    try:
        done = subprocess.run(["git", "-C", str(root), "ls-files", "--eol", "-z"], capture_output=True,
                              timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"--write needs git to answer `ls-files --eol`: {exc}")
    if done.returncode != 0:
        raise SystemExit(f"--write needs git: `git ls-files --eol` failed in {root}: {done.stderr.decode(errors='replace')}")
    out = {}
    for entry in done.stdout.split(b"\0"):
        if not entry:
            continue
        attrs, _tab, path = entry.partition(b"\t")
        fields = attrs.split()
        out[path.decode("utf-8")] = (fields[0].decode("ascii")[2:], fields[1].decode("ascii")[2:])
    return out


class CleanCheckoutReader:
    """Read a tracked file as a clean checkout holds it.

    WHY. The records bind bytes, and the bytes an external team gets are the
    ones `git clone` writes under `.gitattributes` (`* text=auto eol=lf`):
    LF. This working copy is not guaranteed to be that: round 19's follow-up
    found seven indexed evidence files (and `graph/cash_profile.py`) held
    with CRLF here while git's index holds them with LF - git calls the tree
    clean because it normalises on the way in - and the index published at
    f3f3c45 had recorded those CRLF hashes and sizes, which no clean clone
    could ever reproduce. So at write time a text file whose working copy
    carries CRLF against an LF index is read CRLF-folded, exactly as git
    would store it, and named in a NOTE; an untracked file is refused,
    because a clone would not have it. At verify time nothing is folded:
    the bytes in front of the verifier are the bytes it hashes.
    """

    def __init__(self, root: Path):
        self.root = root
        self.eol = git_eol_map(root)
        self.normalised: list[str] = []

    def read(self, rel: str) -> bytes:
        if rel not in self.eol:
            raise SystemExit(f"{rel} is not tracked by git: a clone would not carry it, so it cannot be bound")
        raw = (self.root / rel).read_bytes()
        index_eol, worktree_eol = self.eol[rel]
        if index_eol == "lf" and worktree_eol in ("crlf", "mixed"):
            self.normalised.append(rel)
            return raw.replace(b"\r\n", b"\n")
        return raw


def urlsafe_sha256(raw: bytes) -> str:
    """The RECORD file's own spelling of a sha256: urlsafe base64, no padding."""
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode("ascii")


def wheel_members(wheel: Path) -> tuple[zipfile.ZipFile, list[tuple[str, str, int]]]:
    """The wheel's RECORD rows for its runtime members: (path, sha256 as
    RECORD spells it, size)."""
    zf = zipfile.ZipFile(wheel)
    record = next((n for n in zf.namelist() if n.endswith(".dist-info/RECORD")), None)
    if record is None:
        raise SystemExit(f"{wheel.name} carries no .dist-info/RECORD; it is not a wheel this pack can bind")
    rows = []
    for row in csv.reader(io.StringIO(zf.read(record).decode("utf-8"))):
        if not row or not row[0].startswith(f"{PACKAGE}/"):
            continue
        path, hashed, size = row[0], row[1], row[2]
        if not hashed.startswith("sha256="):
            raise SystemExit(f"{wheel.name}: RECORD row for {path} carries {hashed!r}, not a sha256")
        rows.append((path, hashed[len("sha256="):], int(size) if size else -1))
    return zf, rows


# --------------------------------------------------------------------------
# write
# --------------------------------------------------------------------------

def rescore_test_imports() -> list[str]:
    """Every module under tests/ the rescore imports at top level, as
    evidence paths. Read from the script's own import statements so the index
    cannot drift from what the replay actually needs."""
    tree = ast.parse((ROOT / RESCORE).read_text(encoding="utf-8"))
    names = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module.split(".")[0])
    return sorted({f"tests/{name}.py" for name in names if (ROOT / "tests" / f"{name}.py").is_file()})


def evidence_paths() -> list[str]:
    paths = set(EVIDENCE_PATHS) | set(rescore_test_imports())
    for rel in EVIDENCE_DIRECTORIES:
        directory = ROOT / rel
        if not directory.is_dir():
            raise SystemExit(f"evidence directory missing at write time: {rel}")
        paths |= {p.relative_to(ROOT).as_posix() for p in directory.rglob("*") if p.is_file()}
    return sorted(paths)


def evidence_rows(reader: CleanCheckoutReader) -> dict:
    rows = {}
    for rel in evidence_paths():
        if not (ROOT / rel).is_file():
            raise SystemExit(f"evidence file missing at write time: {rel}")
        raw = reader.read(rel)
        rows[rel] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return rows


def live_declaration(source_commit: str, pack_commit: str, reader: CleanCheckoutReader) -> dict:
    env_mod, FM, CP, G, CANON = load_package()
    directory = package_dir()
    if directory.parent != ROOT:
        raise SystemExit(f"--write must run from the checkout's own environment: beancount_ledger imports from "
                         f"{directory}, not {ROOT / PACKAGE}")
    freeze = CP.freeze_record()
    problems = CP.freeze_problems()
    if problems or not freeze.get("declared_matches_live"):
        raise SystemExit(f"the live freeze contradicts the package's own declared literals: {problems}")
    components = dict(FM.semantic_components())
    parser_now = components.pop("parser")
    census = {k: v for k, v in G.component_versions().items() if k not in RUNTIME_SCOPED_CENSUS_COMPONENTS}
    freeze_json = json.loads((ROOT / "tests" / "legacy_freeze.json").read_text(encoding="utf-8"))
    parser_rows = {}
    for version, row in sorted(freeze_json["unicode_scoped"].items()):
        parser_rows[version] = {
            "parser": row["scorer"]["parse_policy_digest"],
            "scorer_contract_digest": row["scorer"]["scorer_contract_digest"],
            "provenance": row.get("provenance"),
        }
    native = unicodedata.unidata_version
    if native not in parser_rows:
        raise SystemExit(f"unicode {native} is not pinned in tests/legacy_freeze.json; refusing to write from an "
                         f"unpinned runtime")
    if parser_rows[native]["parser"] != parser_now:
        raise SystemExit(f"the live parser component {parser_now} != the pinned {parser_rows[native]['parser']} "
                         f"for unicode {native}; refusing to write a declaration that contradicts the freeze")
    if parser_rows[native]["scorer_contract_digest"] != CANON.scorer_contract_digest():
        raise SystemExit(f"the live scorer contract {CANON.scorer_contract_digest()} != the pinned "
                         f"{parser_rows[native]['scorer_contract_digest']} for unicode {native}")
    runtime = native_runtime(FM)
    if runtime == REFERENCE_RUNTIME:
        if freeze["digest"] != REFERENCE_WHOLE_FREEZE_DIGEST:
            raise SystemExit(f"on the reference runtime the whole-freeze digest is {freeze['digest']}, not the "
                             f"reference {REFERENCE_WHOLE_FREEZE_DIGEST}; the package is not the one that minted "
                             f"the released population, and this script will not re-label it")
        if FM.baseline_catalogue_digest() != REFERENCE_BASELINE_CATALOGUE_DIGEST:
            raise SystemExit(f"on the reference runtime the baseline-catalogue digest is "
                             f"{FM.baseline_catalogue_digest()}, not the reference {REFERENCE_BASELINE_CATALOGUE_DIGEST}")
    tree = package_tree(directory, reader.read)
    if tree["not_utf8_text"]:
        raise SystemExit(f"runtime files that are not UTF-8 text: {tree['not_utf8_text']}; the tree method assumes "
                         f"text, extend it before pinning")
    authored = env_mod.load_environment("cash_application_001")
    legacy = env_mod.load_environment()
    version = installed_version()
    if version is None:
        raise SystemExit(f"{DISTRIBUTION} is not an installed distribution here; --write needs the checkout installed")
    release = {}
    record = ROOT / "reviews" / "installable_serving_check_2026-09-14" / "installable_serving_0.3.0.json"
    if record.is_file():
        artifact = json.loads(record.read_text(encoding="utf-8")).get("artifact", {})
        release = {k: artifact.get(k) for k in ("wheel", "wheel_sha256", "wheel_bytes", "members", "runtime_members",
                                                "record_sha256")}
        release["measured_in"] = "reviews/installable_serving_check_2026-09-14/"
    return {
        "schema": "piv.evaluation-pack.declaration/2",
        "describes": {
            "package_version": version,
            "reference_source_commit": source_commit,
            "pack_commit": pack_commit,
            "commits_note": ("reference_source_commit is the commit whose package this declaration describes; "
                             "pack_commit is the later commit that carries the pack itself, or 'unpublished'. "
                             "Neither is verified by check_pack: what it verifies is the package tree digest and "
                             "the installed version, and it REPORTS the checkout commit it observes beside these."),
            "release_artifact": release,
            "hub_entry": "cangultekn/beancount-ledger (0.2.0 as of 2026-09-14; 0.3.0 is the owner's upload, "
                         "and it is a new version, not a rebuilt 0.2.0)",
            "package_tree": {
                "method": PACKAGE_TREE_METHOD,
                "files": tree["files"],
                "logical_text_digest": tree["logical_text_digest"],
                "stored_bytes_digest_at_write": tree["stored_bytes_digest"],
                "per_file_logical_text": tree["per_file_logical_text"],
            },
            "written_on": {
                "runtime": runtime,
                "whole_freeze_digest": freeze["digest"],
                "baseline_catalogue_digest": FM.baseline_catalogue_digest(),
                "import_path": (directory.relative_to(ROOT).as_posix()
                                if str(directory).startswith(str(ROOT)) else directory.name),
                "observed_checkout_commit": observed_checkout_commit(ROOT),
            },
        },
        "portable": {
            "note": PORTABLE_NOTE,
            "family_freeze": {"schema": freeze["schema"], "declared": freeze["declared"]},
            "semantic_components_unicode_independent": components,
            "census_components_runtime_independent": census,
            "runtime_scoped_by_unicode_database": {"note": UNICODE_NOTE, "rows": parser_rows},
            "episode_contracts": {
                "cash_application": {"reference_task": "cash_application_001", "profile": authored.profile,
                                     "digest": authored.episode_contract_digest()},
                "legacy": {"reference_task": "bank_recon_001", "profile": legacy.profile,
                           "digest": legacy.episode_contract_digest()},
                "note": ("episode settings (turns, token budgets) are part of the contract digest; rows taken under "
                         "different budgets are different arms and must never be pooled. The digest does NOT cover "
                         "every client setting (per-turn cap, sampling, timeout, retries, routing): equal digests "
                         "do not establish equal arms; the screen's arm record does"),
            },
            "library_versions": env_mod.library_versions(),
        },
        "reference_runtime_attestation": {
            "note": REFERENCE_NOTE,
            "runtime": dict(REFERENCE_RUNTIME),
            "whole_freeze_digest": REFERENCE_WHOLE_FREEZE_DIGEST,
            "baseline_catalogue_digest": REFERENCE_BASELINE_CATALOGUE_DIGEST,
        },
    }


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

class Verification:
    """The PASS/FAIL and NOTE lines of one run, kept so --record can write
    exactly what was printed."""

    def __init__(self):
        self.checks: list[dict] = []
        self.notes: list[str] = []
        self.observed: dict = {}

    def check(self, name, ok, detail=""):
        ok = bool(ok)
        self.checks.append({"name": name, "ok": ok, **({"detail": str(detail)} if not ok and detail else {})})
        return check(name, ok, detail)

    def note(self, text):
        self.notes.append(text)
        print(f"NOTE  {text}")

    @property
    def passed(self) -> bool:
        return all(c["ok"] for c in self.checks)


def diff_paths(live, pack, path="") -> list[str]:
    """Where two JSON values differ, by path; the whole path when the shapes do."""
    if isinstance(live, dict) and isinstance(pack, dict):
        out = []
        for key in sorted(set(live) | set(pack)):
            if key not in live:
                out.append(f"{path}/{key}: only in the pack ({pack[key]!r})")
            elif key not in pack:
                out.append(f"{path}/{key}: only live ({live[key]!r})")
            else:
                out.extend(diff_paths(live[key], pack[key], f"{path}/{key}"))
        return out
    if live != pack:
        return [f"{path or '/'}: live {live!r} != pack {pack!r}"]
    return []


def verify_portable(v: Verification, declared: dict, env_mod, FM, CP, G, CANON) -> None:
    portable = declared["portable"]
    freeze = CP.freeze_record()
    problems = CP.freeze_problems()
    v.check("portable: freeze_problems() is empty and the live literals match the package's own declaration",
            not problems and freeze.get("declared_matches_live"), "\n".join(problems))
    # Compare as JSON: the live literals hold tuples, the pack holds lists.
    live_declared = json.loads(json.dumps(freeze["declared"]))
    v.check(f"portable: the {len(live_declared)} declared literals equal the pack's",
            live_declared == portable["family_freeze"]["declared"],
            "\n".join(diff_paths(live_declared, portable["family_freeze"]["declared"])))
    v.check("portable: family freeze schema", freeze["schema"] == portable["family_freeze"]["schema"],
            f"live {freeze['schema']} != pack {portable['family_freeze']['schema']}")
    components = json.loads(json.dumps(dict(FM.semantic_components())))
    parser_now = components.pop("parser")
    v.check("portable: the Unicode-independent semantic components equal the pack's",
            components == portable["semantic_components_unicode_independent"],
            "\n".join(diff_paths(components, portable["semantic_components_unicode_independent"])))
    census = json.loads(json.dumps({k: val for k, val in G.component_versions().items()
                                    if k not in RUNTIME_SCOPED_CENSUS_COMPONENTS}))
    v.check("portable: the runtime-independent census components equal the pack's",
            census == portable["census_components_runtime_independent"],
            "\n".join(diff_paths(census, portable["census_components_runtime_independent"])))
    rows = portable["runtime_scoped_by_unicode_database"]["rows"]
    native = unicodedata.unidata_version
    v.observed["unicode_database"] = native
    if not v.check(f"portable: unicode {native} is a database this pack pins (pinned: {sorted(rows)})", native in rows,
                   "this interpreter's Unicode database is an UNVERIFIED runtime for the pack, not a passing one; "
                   "open a row for it under tests/unicode_pins.py's convention before believing any result"):
        return
    row = rows[native]
    method = (row.get("provenance") or {}).get("method", "unrecorded provenance")
    v.check(f"portable: parser digest for unicode {native} (row provenance: {method})", row["parser"] == parser_now,
            f"live {parser_now} != pinned {row['parser']}")
    scorer_now = CANON.scorer_contract_digest()
    v.check(f"portable: scorer-contract digest for unicode {native}", row["scorer_contract_digest"] == scorer_now,
            f"live {scorer_now} != pinned {row['scorer_contract_digest']}")
    for key, task in (("cash_application", "cash_application_001"), ("legacy", "bank_recon_001")):
        env = env_mod.load_environment(task)
        want = portable["episode_contracts"][key]
        v.check(f"portable: episode contract {key} as served for {task} ({want['digest'][:12]}...)",
                env.profile == want["profile"] and env.episode_contract_digest() == want["digest"],
                f"served {env.profile}/{env.episode_contract_digest()} != pack {want['profile']}/{want['digest']}")
    versions = env_mod.library_versions()
    v.check("portable: the pinned library versions", versions == portable["library_versions"],
            "\n".join(diff_paths(versions, portable["library_versions"])))


def verify_source(v: Verification, declared: dict, directory: Path) -> None:
    describes = declared["describes"]
    want = describes["package_tree"]
    tree = package_tree(directory)
    v.observed["import_path"] = str(directory)
    v.observed["package_tree"] = {k: tree[k] for k in ("files", "logical_text_digest", "stored_bytes_digest")}
    v.check("source: every runtime file is UTF-8 text", not tree["not_utf8_text"], tree["not_utf8_text"])
    detail = diff_paths(tree["per_file_logical_text"], want["per_file_logical_text"])
    v.check(f"source: package tree logical-text digest {tree['logical_text_digest'][:16]}... over {tree['files']} "
            f"files equals the declared ({directory})",
            tree["logical_text_digest"] == want["logical_text_digest"] and tree["files"] == want["files"],
            "\n".join(detail) or f"live {tree['logical_text_digest']} != declared {want['logical_text_digest']}")
    same_bytes = tree["stored_bytes_digest"] == want["stored_bytes_digest_at_write"]
    v.observed["package_tree"]["stored_bytes_equal_to_write_time"] = same_bytes
    v.observed["package_tree"]["cr_bearing"] = tree["cr_bearing"]
    v.note(f"source: stored-bytes tree digest {tree['stored_bytes_digest'][:16]}... is "
           + ("EQUAL to" if same_bytes else "DIFFERENT from")
           + f" the write-time {want['stored_bytes_digest_at_write'][:16]}... (reported, not demanded; "
           + (f"files holding CR/CRLF here: {', '.join(tree['cr_bearing'])}" if tree["cr_bearing"]
              else "no file holds CR/CRLF here")
           + "; the released 0.3.0 wheel carries CRLF in graph/cash_profile.py and a clean checkout does not, "
             "so the logical text above is what is verified)")
    version = installed_version()
    v.observed["installed_version"] = version
    v.check(f"source: importlib.metadata reports {DISTRIBUTION} {version}, the declared {describes['package_version']}",
            version == describes["package_version"], "the installed distribution is not the declared version")
    commit = observed_checkout_commit(directory.parent)
    v.observed["origin"] = {"observed_checkout_commit": commit,
                            "reference_source_commit": describes["reference_source_commit"],
                            "pack_commit": describes["pack_commit"]}
    v.note(f"origin: observed checkout commit {commit or 'none (not a git checkout, or git unavailable)'}; "
           f"reference_source_commit {describes['reference_source_commit']}; pack_commit {describes['pack_commit']}. "
           f"Commits are reported, not verified: the bytes and the version above are what is verified")


def verify_wheel(v: Verification, declared: dict, wheel: Path | None, directory: Path) -> None:
    if wheel is None:
        v.observed["wheel"] = "not checked"
        v.note("wheel: not checked (pass --wheel PATH to bind the installed files to the released wheel's RECORD)")
        return
    release = declared["describes"].get("release_artifact") or {}
    if not release.get("wheel_sha256"):
        v.check("wheel: the declaration names a release wheel to compare with", False, "release_artifact is empty")
        return
    if not wheel.is_file():
        v.check(f"wheel: {wheel} exists", False)
        return
    digest = sha256_file(wheel)
    size = wheel.stat().st_size
    v.observed["wheel"] = {"path": str(wheel), "sha256": digest, "bytes": size}
    v.check(f"wheel: sha256 of {wheel.name} equals the declared {release['wheel_sha256'][:16]}...",
            digest == release["wheel_sha256"] and size == release.get("wheel_bytes", size),
            f"observed {digest} ({size} bytes); declared {release['wheel_sha256']} ({release.get('wheel_bytes')} bytes)")
    zf, rows = wheel_members(wheel)
    site = directory.parent
    identical, text_only, differ, missing, self_inconsistent = [], [], [], [], []
    for path, want, _size in rows:
        member = zf.read(path)
        if urlsafe_sha256(member) != want:
            self_inconsistent.append(path)
        local = site / path
        if not local.is_file():
            missing.append(path)
            continue
        raw = local.read_bytes()
        if urlsafe_sha256(raw) == want:
            identical.append(path)
        elif logical_bytes(raw) is not None and logical_bytes(raw) == logical_bytes(member):
            text_only.append(path)
        else:
            differ.append(path)
    v.observed["wheel"].update({"record_members": len(rows), "byte_identical": len(identical),
                                "logical_text_only": text_only, "differ": differ, "not_installed": missing})
    v.check(f"wheel: every RECORD-listed member's sha256 matches the wheel's own bytes ({len(rows)} members)",
            not self_inconsistent, self_inconsistent)
    v.check(f"wheel: the installed files carry the RECORD-listed members' logical text "
            f"({len(identical)} byte-identical, {len(text_only)} equal in logical text only, {len(differ)} differ, "
            f"{len(missing)} not installed)", not differ and not missing,
            "\n".join(f"differs: {p}" for p in differ) + "\n" + "\n".join(f"not installed: {p}" for p in missing))
    if text_only:
        v.note("wheel: members equal in logical text only (line endings): " + ", ".join(text_only))


def verify_runtime(v: Verification, declared: dict, FM, CP) -> None:
    reference = declared["reference_runtime_attestation"]
    runtime = native_runtime(FM)
    freeze = CP.freeze_record()
    baseline = FM.baseline_catalogue_digest()
    equal = freeze["digest"] == reference["whole_freeze_digest"]
    same_runtime = runtime == reference["runtime"]
    v.observed.update({"runtime": runtime, "whole_freeze_digest": freeze["digest"],
                       "reference_whole_freeze_digest": reference["whole_freeze_digest"],
                       "whole_freeze_digest_equals_reference": equal,
                       "baseline_catalogue_digest": baseline,
                       "runtime_is_the_reference_runtime": same_runtime})
    v.note(f"runtime: this evaluator's whole-freeze digest is {freeze['digest']} under "
           f"{describe_runtime(runtime)}; the reference is {reference['whole_freeze_digest']} under "
           f"{describe_runtime(reference['runtime'])}: " + ("EQUAL" if equal else "DIFFERENT")
           + ("" if same_runtime else " (expected off the reference runtime: the digest folds the native runtime and "
                                      "predicate bytecode in; it is recorded, not demanded)"))
    v.note(f"runtime: baseline-catalogue digest {baseline} (reference {reference['baseline_catalogue_digest']}, "
           + ("equal" if baseline == reference["baseline_catalogue_digest"] else "different") + ")")
    if same_runtime:
        v.check("runtime: on the reference runtime itself the whole-freeze digest reproduces", equal,
                f"live {freeze['digest']} != reference {reference['whole_freeze_digest']} on the very runtime that "
                f"minted the population; this package is not the one that minted it")


def verify_evidence(v: Verification, root: Path) -> None:
    if not EVIDENCE.is_file():
        v.check("evidence: evidence_index.json is present", False)
        return
    index = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    files = index["files"]
    if not (root / "reviews").is_dir():
        v.observed["evidence"] = "not a checkout"
        v.note(f"evidence: not a repository checkout ({root}): the {len(files)} indexed files are not present here, "
               f"so their digests were not checked (they are checked from a checkout of the declared source commit)")
        return
    missing, changed, line_endings_only = [], [], []
    for rel, want in files.items():
        path = root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        raw = path.read_bytes()
        if len(raw) == want["bytes"] and hashlib.sha256(raw).hexdigest() == want["sha256"]:
            continue
        folded = raw.replace(b"\r\n", b"\n")
        if len(folded) == want["bytes"] and hashlib.sha256(folded).hexdigest() == want["sha256"]:
            line_endings_only.append(rel)
        else:
            changed.append(rel)
    v.observed["evidence"] = {"indexed": len(files), "missing": missing, "changed": changed,
                              "line_endings_only": line_endings_only}
    v.check(f"evidence: all {len(files)} indexed files are present with their recorded sha256 and size",
            not missing and not changed and not line_endings_only,
            "\n".join([f"missing: {p}" for p in missing] + [f"changed: {p}" for p in changed]
                      + [f"line endings only: {p} (this working copy holds CRLF where a clean checkout under "
                         f".gitattributes has LF; renormalise it with git checkout -- {p})"
                         for p in line_endings_only]))
    unindexed = []
    for rel in index.get("directories", ()):
        directory = root / rel
        if not directory.is_dir():
            unindexed.append(f"{rel}/ (directory missing)")
            continue
        unindexed.extend(p.relative_to(root).as_posix() for p in directory.rglob("*")
                         if p.is_file() and p.relative_to(root).as_posix() not in files)
    v.check(f"evidence: no file under the {len(index.get('directories', ()))} indexed directories is missing from "
            f"the index", not unindexed, "\n".join(unindexed))


def verify(wheel: Path | None) -> Verification:
    v = Verification()
    if not DECLARATION.is_file():
        v.check("frozen_declaration.json is present", False)
        return v
    declared = json.loads(DECLARATION.read_text(encoding="utf-8"))
    if declared.get("schema") != "piv.evaluation-pack.declaration/2":
        v.check("the declaration's schema is piv.evaluation-pack.declaration/2", False,
                f"found {declared.get('schema')!r}; regenerate with --write")
        return v
    env_mod, FM, CP, G, CANON = load_package()
    directory = package_dir()
    verify_portable(v, declared, env_mod, FM, CP, G, CANON)
    verify_source(v, declared, directory)
    verify_wheel(v, declared, wheel, directory)
    verify_runtime(v, declared, FM, CP)
    verify_evidence(v, directory.parent)
    return v


def write_record(path: Path, v: Verification, declared: dict | None) -> None:
    record = {
        "schema": "piv.evaluation-pack.verification/1",
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "declaration": {"schema": declared.get("schema"), "package_version": declared["describes"]["package_version"],
                        "reference_source_commit": declared["describes"]["reference_source_commit"],
                        "pack_commit": declared["describes"]["pack_commit"],
                        "sha256": sha256_file(DECLARATION)} if declared else None,
        "passed": v.passed,
        "observed": v.observed,
        "checks": v.checks,
        "notes": v.notes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="author-side: regenerate both records")
    parser.add_argument("--source-commit", default=None, help="the commit the declaration describes (with --write)")
    parser.add_argument("--pack-commit", default="unpublished",
                        help="the commit that carries the pack, or 'unpublished' (with --write)")
    parser.add_argument("--wheel", default=None, help="the released wheel: bind its RECORD to the installed files")
    parser.add_argument("--record", default=None, help="write what this run observed (runtime, digests, checks) here")
    args = parser.parse_args()

    record_path = refuse_piv(Path(args.record), "the verification record") if args.record else None
    wheel = Path(args.wheel).expanduser().resolve() if args.wheel else None

    if args.write:
        if not args.source_commit:
            raise SystemExit("--write needs --source-commit <sha>: the declaration names what it describes")
        reader = CleanCheckoutReader(ROOT)
        declaration = live_declaration(args.source_commit, args.pack_commit, reader)
        DECLARATION.write_text(json.dumps(declaration, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                               newline="\n")
        index = {"schema": "piv.evaluation-pack.evidence-index/2",
                 "reference_source_commit": args.source_commit, "pack_commit": args.pack_commit,
                 "bytes_are": ("the bytes a clean checkout under .gitattributes (* text=auto eol=lf) yields, i.e. "
                               "git's own copy: a working copy that holds an indexed text file with CRLF verifies "
                               "as changed in line endings only, and the fix is to renormalise that copy, not the "
                               "index"),
                 "directories": list(EVIDENCE_DIRECTORIES), "files": evidence_rows(reader)}
        EVIDENCE.write_text(json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        for rel in reader.normalised:
            print(f"NOTE  write: {rel} is held with CRLF in this working copy against an LF index; the record binds "
                  f"the LF bytes a clean checkout yields. Renormalise this copy (git checkout -- {rel}) before "
                  f"expecting it to verify here")
        print(f"wrote {DECLARATION.name} (package tree {declaration['describes']['package_tree']['logical_text_digest'][:16]}"
              f"... over {declaration['describes']['package_tree']['files']} files; reference whole-freeze digest "
              f"{declaration['reference_runtime_attestation']['whole_freeze_digest']}) and "
              f"{EVIDENCE.name} ({len(index['files'])} files)")

    v = verify(wheel)
    declared = json.loads(DECLARATION.read_text(encoding="utf-8")) if DECLARATION.is_file() else None
    if record_path is not None:
        write_record(record_path, v, declared)
    failed = [c["name"] for c in v.checks if not c["ok"]]
    if failed:
        print(f"FAIL  {len(failed)} of {len(v.checks)} checks failed; the package in front of you is not verified "
              f"as the declared one")
        return 1
    observed = v.observed
    print(f"PASS  {len(v.checks)} checks: the package in front of you carries the pack's portable identity and the "
          f"declared source bytes (tree {observed['package_tree']['logical_text_digest'][:16]}..., "
          f"{DISTRIBUTION} {observed['installed_version']}) under unicode {observed['unicode_database']}; "
          f"whole-freeze digest {observed['whole_freeze_digest']} "
          + ("equals" if observed["whole_freeze_digest_equals_reference"] else "differs from")
          + f" the reference {observed['reference_whole_freeze_digest']} (reported)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
