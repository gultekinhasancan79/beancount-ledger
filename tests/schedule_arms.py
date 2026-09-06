"""The IMMUTABLE arm schedule — written
BEFORE any rollout, executed by `tests/run_arms.py`, read by
`tests/arm_table.py`.

    python tests/schedule_arms.py --label confirm1 --provider mistral \
        --models devstral-2512 ministral-14b-2512 ministral-8b-2512 mistral-medium-2508 \
        --selectors train:1 train:12 train:30 eval:5 train:3:hard train:107:hard \
        --arms A B1 B2 --replicates 2 --timeout 600

WHY A FILE AND NOT A LOOP. `run_arms.build_blocks()` used to compute the
block index on the fly, looping `selector -> replicate 1..N -> model`. The
index a block received therefore depended on the MAXIMUM `N` passed today:
a cell written under `--replicate 1` sat at a different conceptual position
from the one the same cell would occupy when the design was later rebuilt
with `--replicate 3`. Skipping an existing output file prevented an
overwrite; it did NOT preserve the intended schedule. Staged replication
silently produced a different design from the one the run claimed.

So the design is now DATA. This script writes `reviews/schedule_<label>.json`
once; `run_arms.py --schedule <file>` executes the rows whose output file is
missing, in the planned order, and never recomputes an order. The block
index is REPLICATE-MAJOR over a FIXED roster, so replicate 1's ordinals are
identical whether the schedule was cut for one replicate or for ten.

BALANCE. Within each `(provider, model, replicate)` layer the six
permutations of the three arms are dealt across the selectors from a fixed
cycle:

    0  A  B1 B2        rows 0-2: a cyclic Latin square (forward steps only)
    1  B1 B2 A
    2  B2 A  B1
    3  A  B2 B1        rows 3-5: its reverse
    4  B2 B1 A
    5  B1 A  B2

Over all six rows every arm occupies every position exactly twice AND every
ORDERED adjacent pair of distinct arms occurs exactly twice — the Williams
property for an odd number of treatments. Over rows 0-2 (or 3-5) alone only
POSITION balance survives: a cyclic square never produces a reverse step
like B1 -> A, so first-order carry-over is not balanced.

The schedule therefore states what it actually achieved, per
`(provider, model, replicate)` layer, and claims nothing more:

  - `len(selectors) % 6 == 0`  -> position AND adjacency balance, exact;
  - `len(selectors) % 3 == 0`  -> position balance only (offsets are held to
                                  {0, 3} so each layer is a whole Latin
                                  square); adjacency is NOT balanced;
  - otherwise                  -> neither is claimed. Each cell still runs
                                  all three arms, so arm FREQUENCY is equal;
                                  order is simply not a controlled factor.

`schedule_id` is the sha256 of the canonical content — everything except
`created_at` and the id itself, which are named in `digest_excludes`. Two
schedules with the same design have the same id, by design: the id names the
DESIGN, not the moment it was written.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import itertools
import json
import os
import subprocess
import sys
import sysconfig
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The experiment contract is computed from the package and from the sibling
# instrument modules; both must import whether this file is run as a script
# or imported by `run_arms` / `arm_table`.
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

SCHEDULE_VERSION = 1
DIGEST_EXCLUDES = ("created_at", "schedule_id")
#: The analysis plan a sealed schedule binds itself to.
ANALYSIS_PLAN = ROOT / "reviews" / "confirmatory_design.md"

DEFAULT_ARMS = ("A", "B1", "B2")


def permutation_cycle(arms: list[str]) -> list[list[str]]:
    """The six sequences of a three-treatment Williams design, ordered so
    that rows 0-2 and rows 3-5 are each a complete Latin square (see the
    module docstring). For a number of arms other than three, fall back to
    every permutation in `itertools` order: the balance CLAIM is computed
    from the dealt cells afterwards, never assumed, so an unusual arm count
    simply produces a weaker, truthfully stated claim."""
    if len(arms) != 3:
        return [list(p) for p in itertools.permutations(arms)]
    a, b, c = arms
    return [[a, b, c], [b, c, a], [c, a, b],
            [a, c, b], [c, b, a], [b, a, c]]


def layer_offset(layer_index: int, n_selectors: int, n_permutations: int) -> int:
    """Where in the permutation cycle a `(provider, model, replicate)` layer
    starts. When the selector count is not a multiple of the cycle length but
    IS a multiple of the arm count, offsets are held to whole Latin squares
    (0, 3, 0, 3, ...) so that position balance survives; otherwise the offset
    walks the cycle so that two replicates of the same layer never pair the
    same selector with the same arm order."""
    if n_permutations == 0:
        return 0
    if n_selectors % n_permutations == 0:
        return layer_index % n_permutations
    if n_permutations == 6 and n_selectors % 3 == 0:
        return (3 * layer_index) % 6
    return layer_index % n_permutations


def output_tag(label: str, arm: str, selector: str, replicate: int) -> str:
    """The `--tag` `measure_budget.py` is given for one cell, and therefore
    the part of its output filename after the date. The LABEL is part of it:
    two schedules (or a schedule and the pilot) must never write to the same
    `budget_<slug>_<date>_<tag>.json` and silently "resume" each other."""
    return f"{label}_{arm}p_{selector.replace(':', '')}_r{replicate}"


def output_path_for(reviews_dir: Path, model: str, date_stamp: str, tag: str) -> Path:
    """The exact file `measure_budget.py` writes for this cell. The date
    comes from the SCHEDULE, not from today, so resuming a schedule on a
    later day finds the cells it already ran."""
    slug = model.split("/")[-1]
    return reviews_dir / f"budget_{slug}_{date_stamp}_{tag}.json"


def build_cells(roster: list[dict], selectors: list[str], arms: list[str], replicates: int,
                label: str) -> list[dict]:
    """One row per scheduled cell, in PLANNED execution order:
    replicate-major over the fixed roster, then selector, then the three arms
    of that block in their dealt order.

    Replicate-major is what makes the ordinals stable
    under staged replication: every cell of replicate 1 keeps its ordinal no
    matter how many replicates the schedule was cut for.
    """
    cycle = permutation_cycle(arms)
    cells: list[dict] = []
    planned_ordinal = 0
    block_index = 0
    for replicate in range(1, replicates + 1):
        for entry_index, entry in enumerate(roster):
            layer_index = (replicate - 1) * len(roster) + entry_index
            offset = layer_offset(layer_index, len(selectors), len(cycle))
            for selector_index, selector in enumerate(selectors):
                permutation_index = (offset + selector_index) % len(cycle)
                order = cycle[permutation_index]
                block_id = (f"{entry['provider']}|{entry['model']}|{selector}|r{replicate}")
                for arm_position, arm in enumerate(order):
                    planned_ordinal += 1
                    cells.append({
                        "provider": entry["provider"],
                        "model": entry["model"],
                        "selector": selector,
                        "replicate": replicate,
                        "arm": arm,
                        "planned_ordinal": planned_ordinal,
                        "arm_position": arm_position,
                        "permutation_index": permutation_index,
                        "block_id": block_id,
                        "block_index": block_index,
                        "tag": output_tag(label, arm, selector, replicate),
                    })
                block_index += 1
    return cells


# ---------------------------------------------------------------------------
# The sequence / position / adjacency census. Computed
# FROM the dealt cells (or, in `arm_table.py`, from the rows actually run) —
# never assumed from the construction. `arm_table.py` imports these.
# ---------------------------------------------------------------------------

def block_sequences(cells: list[dict]) -> dict:
    """`{block_id: (cell, [arm, ...])}` — each block's arm order, taken from
    `arm_position`. Works on schedule cells and on archived rows alike: both
    carry `block_id`, `arm` and `arm_position`."""
    blocks: dict = {}
    for cell in cells:
        block_id = cell.get("block_id")
        if block_id is None or cell.get("arm_position") is None:
            continue
        blocks.setdefault(block_id, (cell, []))[1].append((cell["arm_position"], cell.get("arm")))
    return {bid: (cell, [arm for _, arm in sorted(pairs)]) for bid, (cell, pairs) in blocks.items()}


def census(cells: list[dict], key_fields: tuple) -> dict:
    """Position and ordered-adjacency counts per stratum, plus whether the
    balance is EXACT there.

    `key_fields` names the stratum, e.g. `("provider", "model")`,
    `("selector",)` or `("provider", "model", "selector")`. A stratum is
    position-balanced when every (arm, position) count is equal, and
    adjacency-balanced when every ordered pair of DISTINCT arms occurs
    equally often — the honest test being equality of the observed counts,
    not a claim about how they were constructed.
    """
    sequences = block_sequences(cells)
    strata: dict = {}
    for _, (cell, order) in sequences.items():
        key = tuple(cell.get(f) for f in key_fields)
        strata.setdefault(key, []).append(order)
    out: dict = {}
    for key, orders in sorted(strata.items(), key=str):
        positions: Counter = Counter()
        pairs: Counter = Counter()
        for order in orders:
            for position, arm in enumerate(order):
                positions[(arm, position)] += 1
            for i in range(len(order) - 1):
                pairs[(order[i], order[i + 1])] += 1
        arms = sorted({arm for order in orders for arm in order})
        want_positions = {(a, p) for a in arms for p in range(max((len(o) for o in orders), default=0))}
        want_pairs = {(a, b) for a in arms for b in arms if a != b}
        position_exact = (set(positions) == want_positions and len(set(positions.values())) == 1)
        adjacency_exact = (set(pairs) == want_pairs and len(set(pairs.values())) == 1)
        out[key] = {
            "n_blocks": len(orders),
            "sequences": Counter(tuple(o) for o in orders),
            "position_counts": positions,
            "pair_counts": pairs,
            "position_balance_exact": position_exact,
            "adjacency_balance_exact": adjacency_exact,
        }
    return out


def balance_claim(cells: list[dict], selectors: list[str], arms: list[str]) -> dict:
    """What this schedule may HONESTLY claim, verified against the cells it
    actually dealt rather than against the construction that produced them.
    The `statement` is the sentence the schedule header and
    `reviews/confirmatory_design.md` both use, verbatim."""
    layer = census(cells, ("provider", "model", "replicate"))
    per_model = census(cells, ("provider", "model"))
    position_exact = bool(layer) and all(s["position_balance_exact"] for s in layer.values())
    adjacency_exact = bool(layer) and all(s["adjacency_balance_exact"] for s in layer.values())
    model_position = bool(per_model) and all(s["position_balance_exact"] for s in per_model.values())
    model_adjacency = bool(per_model) and all(s["adjacency_balance_exact"] for s in per_model.values())
    if position_exact and adjacency_exact:
        statement = (f"{len(selectors)} selectors = {len(selectors) // len(permutation_cycle(arms))} complete "
                     f"Williams cycle(s) per (provider, model, replicate): every arm occupies every position "
                     f"exactly equally often AND every ordered adjacent pair of distinct arms occurs exactly "
                     f"equally often, WITHIN each (provider, model, replicate) layer. Order balance is claimed "
                     f"at the (provider, model) level; it is NOT claimed within a single selector, where each "
                     f"(provider, model, selector, replicate) block runs exactly one of the six sequences.")
    elif position_exact:
        statement = (f"{len(selectors)} selectors is not a multiple of {len(permutation_cycle(arms))}, so each "
                     f"(provider, model, replicate) layer is a whole Latin square: POSITION balance holds "
                     f"(every arm occupies every position equally often) and first-order ADJACENCY balance "
                     f"does NOT (a cyclic square emits forward steps only). Carry-over is therefore not a "
                     f"controlled factor in this schedule.")
    else:
        statement = (f"{len(selectors)} selectors supports NEITHER position nor adjacency balance within a "
                     f"(provider, model, replicate) layer. Every cell still runs all three arms, so arm "
                     f"FREQUENCY is equal, but ORDER is not a controlled factor and no order claim may be "
                     f"made from this schedule.")
    return {
        "position_balance_within_provider_model_replicate": position_exact,
        "adjacency_balance_within_provider_model_replicate": adjacency_exact,
        "position_balance_within_provider_model": model_position,
        "adjacency_balance_within_provider_model": model_adjacency,
        "balance_within_selector": False,
        "statement": statement,
    }


def schedule_digest(content: dict) -> str:
    payload = {k: v for k, v in content.items() if k not in DIGEST_EXCLUDES}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# THE EXPERIMENT CONTRACT (schedule v2). Version 1's
# `schedule_id` hashed the roster, the selectors, the arm LABELS and the
# order. It did not hash what those labels MEAN. `run_arms.cell_command`
# passes `--arm A`; `measure_budget.ARM_PRESETS` supplies `(8000, replay on)`
# at execution time — so the treatment could be edited while `schedule_id`
# stayed the same. Likewise a manifest rotation can make `train:1` a
# different public world under an unchanged selector string.
#
# A v2 schedule therefore hashes the TREATMENT, the WORLD, the CODE and the
# ANALYSIS PLAN as well as the order:
#
#   instrument_commit                 the git HEAD that will execute (clean tree required)
#   analysis_plan_sha256              reviews/confirmatory_design.md, as sealed
#   arm_contract                      the literal ARM_PRESETS mapping for these arms
#   expected_episode_contract_digest  the package's own digest at this ceiling
#   expected_replay_contract_digest_by_arm
#   package_lock                      the pinned library versions (a READING aid)
#   runtime_environment_digest        the BYTES of every installed distribution,
#                                     of every file no RECORD references, and of
#                                     the interpreter itself
#   failure_map_digest                the blind bucket map + quota table + window rule
#   manifest_rotation_id / manifest_content_digest
#   expected_public_task_id_by_selector   minted once, through the serving door
#   provider_quotas                   the console's TPM/rps table, with its date
#
# `tests/startup_witness.py` re-checks every one of them before the first
# provider call of every session; `tests/run_arms.py` refuses to start when
# any differs, naming the field.
# ---------------------------------------------------------------------------

SEALED_SCHEDULE_VERSION = 2

# ---------------------------------------------------------------------------
# THE INSTRUMENT IDENTITY (the GIT-PATH CONTRACT).
#
# v2 bound `instrument_commit` and the startup witness compared it to
# `git rev-parse HEAD` for EXACT equality. That rule is incompatible with its
# own storage workflow: the sealed schedule is written into the repository, so
# committing it MOVES HEAD, and the witness then refuses the very run it was
# sealed for. A real seal showed exactly that — `cf613c1…` sealed, HEAD at
# `5d03346…`, diff confined to root notes files, a private notes directory
# and the schedule file itself, and the run could not have passed its own
# witness.
#
# Relaxing equality to "ancestor" is NOT the fix: a descendant commit may
# change Python. The security property is the PATH/DIGEST constraint, so the
# seal binds three things instead of one:
#
#   instrument_commit      the commit whose execution tree was sealed
#   execution_paths        a CLOSED set of paths that carry executable/instrument
#                          content; everything else in the repository is EVIDENCE
#   execution_tree_digest  sha256 over the sorted (path, git blob sha) pairs
#                          under those paths AT the instrument commit
#
# and the startup witness requires, before request 1:
#
#   1. the sealed commit is an ANCESTOR of the runtime HEAD (or is it);
#   2. `git diff <instrument>..HEAD` is EMPTY over the execution paths;
#   3. the working tree is clean over the execution paths (a dirty
#      `reviews/…`, a notes directory or root `*.md` does NOT fail — those are
#      evidence, and an experiment that cannot write its own log while it runs
#      is not an experiment);
#   4. the recomputed execution-tree digest equals the sealed one.
#
# The runtime HEAD is recorded SEPARATELY — on every archived row and every
# execution-journal entry — so the report can state both identities rather than
# pretending they were the same commit.
# ---------------------------------------------------------------------------

#: The CLOSED set of repository paths whose content is the instrument — now the
#: WHOLE package directory, minus a named exclusion list (adversarial review,
#: attack 1(h)). The previous set named three subtrees, and
#: `sys.path` is wider than any of them: `measure_budget.py` inserts the
#: package ROOT at position 0 and `tests/` right behind it, so ANY new
#: `environments/beancount_ledger/<name>.py` — outside the three sealed paths
#: and therefore invisible to the digest — is imported BEFORE the real module
#: of that name. A live attack resolved `import openai` to an unsealed
#: `environments/beancount_ledger/openai.py`, and `package_lock` cannot see it
#: (`importlib.metadata` reads distribution metadata, not the module that was
#: actually imported).
#:
#: THE NAME IS RESOLVED, NEVER HARDCODED. The package directory is VENDORED
#: inside a larger repository during development (`environments/beancount_ledger`
#: beside private notes and the other environments) and IS the repository top
#: level in a standalone checkout of the published repository. Both layouts
#: name exactly the same bytes, but a hardcoded relative name that does not
#: exist makes the walk descend nothing: `execution_tree_digest()` then returns
#: `None`, and `None` compares equal to `None` on both sides of every
#: comparison — the identity would be vacuously green in precisely the checkout
#: where it must be loudest. `execution_root_for()` below asks the repository
#: which layout it is; `EXECUTION_ROOT`/`EXECUTION_PATHS` are that answer for
#: the package this module belongs to, and every per-root caller re-resolves.
VENDORED_EXECUTION_ROOT = "environments/beancount_ledger"
#: What makes "this directory IS the package" a FACT rather than a guess: the
#: three things a beancount-ledger checkout always has at its own top.
PACKAGE_MARKERS = ("pyproject.toml", "tests", "beancount_ledger")
#: What the walk skips, RELATIVE to the execution root. `reviews/**` is the
#: evidence directory (schedules, journals, ledgers, tables — all written BY a
#: run, all content-bound by their own digests where it matters). `.venv/**` is
#: the interpreter's own installed libraries: gitignored, tens of thousands of
#: files, and already bound by `package_lock` (the pinned `verifiers`/`openai`
#: versions and the interpreter version) plus the replay-contract digests, so
#: hashing it here would buy nothing and cost minutes. The last two are build
#: droppings that no source change can hide behind.
#:
#: A bare `**/<name>/**` pattern matches that directory component at ANY depth;
#: a `<name>/**` pattern is anchored at the execution root; a `*.ext` pattern
#: matches by file extension.
#:
#: `.git/**` is the REPOSITORY's own metadata, and it is excluded for the same
#: reason `reviews/**` is: it is not the instrument. It sits ABOVE the execution
#: root in the vendored layout, so the exclusion is a no-op there; it sits
#: INSIDE it in a standalone checkout, where hashing it would be both wrong and
#: non-stationary — `git status`, which this very module runs on the way to the
#: witness, rewrites `.git/index`, so the digest would move during the run it
#: authenticates. Nothing under `.git/` is importable and nothing there is on
#: `sys.path`, so the exclusion opens no shadowing hole; git remains SECONDARY
#: evidence either way.
EXECUTION_EXCLUDES = ("reviews/**", ".venv/**", ".git/**", "**/__pycache__/**", "*.pyc")
#: Bumping this changes every execution-tree digest, and therefore every
#: sealed schedule id: the ALGORITHM that computes the identity is part of the
#: identity. Version 2 is the on-disk walk; version 1 asked git's index, which
#: three different attacks defeated while leaving the witness fully green.
#: Version 3 RESOLVES the execution root per repository (vendored
#: `environments/beancount_ledger`, or the repository top level in a standalone
#: checkout of the published package) and excludes `.git/**` from the walk;
#: version 2 hardcoded the vendored name, so in a standalone checkout the walk
#: descended nothing, the digest was `None`, and `None == None` left every
#: identity check vacuously green. Every schedule sealed at version 2
#: (`reviews/schedule_confirm1v4.json` was, in the vendored layout, with a real
#: 321-file digest) stays exactly what it was: a v2 seal names v2 bytes and is
#: neither re-run nor re-sealed under this constant.
INSTRUMENT_IDENTITY_VERSION = 3
#: Paths outside `EXECUTION_PATHS` that the contract explicitly recognises as
#: EVIDENCE. Documentation only — the rule is "not in the execution set" — but
#: naming them keeps the witness's error messages honest about what it allows.
EVIDENCE_PATH_HINTS = ("environments/beancount_ledger/reviews/", "notes/", "*.md at the repository root")


def _pathspecs(paths=None, root: Path | None = None) -> list[str]:
    """The execution set as git pathspecs anchored at the repository root, so
    the same set is meant whatever directory git is invoked from. Used only by
    the SECONDARY git checks (ancestry, diff, working-tree status); the
    PRIMARY identity is the on-disk digest below.

    RESOLVED PER REPOSITORY, like the walk. A pathspec naming a directory that
    does not exist matches nothing, and `git status -- <nothing>` is silently
    EMPTY — i.e. reported clean. A stale hardcoded name would therefore turn
    this check into one that always passes, which is worse than not having it."""
    relative = execution_root_for(root)
    paths = execution_paths_for(root) if paths is None else paths
    out = []
    for path in paths:
        base = path[:-3] if path.endswith("/**") else path
        # `**` is the whole repository (the package IS the top level): the bare
        # `:(top)` pathspec means exactly that, and no glob magic is involved.
        out.append(":(top)" if base in ("**", ".") else f":(top){base}")
    prefix = "" if relative == "." else f"{relative}/"
    for pattern in EXECUTION_EXCLUDES:
        if pattern.startswith("**/") or pattern.startswith("*."):
            continue                         # git ignores these already (build droppings)
        out.append(f":(top,exclude){prefix}{pattern[:-3] if pattern.endswith('/**') else pattern}")
    return out


def _excluded(relative: str, excludes=EXECUTION_EXCLUDES) -> bool:
    """Is this path (POSIX, relative to the execution root) outside the sealed
    content? Three pattern shapes, each deliberately narrow — a wide exclusion
    is a blind spot, and a blind spot on `sys.path` is attack 1(h)."""
    parts = relative.split("/")
    for pattern in excludes:
        if pattern.startswith("**/") and pattern.endswith("/**"):
            if pattern[3:-3] in parts[:-1]:            # that directory, at any depth
                return True
        elif pattern.endswith("/**"):
            base = pattern[:-3]                        # anchored at the execution root
            if relative == base or relative.startswith(base + "/"):
                return True
        elif pattern.startswith("*."):
            if parts[-1].endswith(pattern[1:]):
                return True
        elif relative == pattern:
            return True
    return False


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:                   # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"
    return result.returncode, (result.stdout or "").strip()


def repo_root(root: Path | None = None) -> Path:
    """The REPOSITORY top level. `ROOT` in this module is the package
    directory (`environments/beancount_ledger`), while `EXECUTION_ROOT` is
    named relative to the repository, so the on-disk walk has to ask git where
    the repository begins. Falls back to the given directory when git cannot
    answer — the walk then finds nothing and the digest is `None`, which every
    caller treats as a refusal."""
    code, out = _git(root or ROOT, "rev-parse", "--show-toplevel")
    if code == 0 and out:
        return Path(out)
    return Path(root or ROOT)


def _is_package_directory(path: Path) -> bool:
    """Does this directory carry every marker a beancount-ledger checkout has
    at its own top? Used to decide "the repository top level IS the package",
    and deliberately conjunctive: a repository that merely happens to contain a
    `tests/` is not this package."""
    try:
        return path.is_dir() and all((path / marker).exists() for marker in PACKAGE_MARKERS)
    except OSError:                                                        # noqa: BLE001
        return False


def execution_root_for(root: Path | None = None) -> str:
    """The package directory, named RELATIVE to the repository that contains
    it — the string the walk descends and the manifest records.

    Two real layouts, the same bytes:

      `environments/beancount_ledger`  the development monorepo, where the
                                       package is vendored beside
                                       a private notes directory and the other
                                       environments and `.git/` sits ABOVE it;
      `.`                              a standalone checkout of the published
                                       repository, where the package IS the
                                       repository top level.

    The vendored name WINS whenever that directory exists, so this resolution
    is a no-op — byte-for-byte the previous behaviour — in every checkout that
    had one. The fallback exists because the alternative is silent: a relative
    name that resolves to nothing makes `execution_tree_manifest` return zero
    files, `execution_tree_digest` return `None`, and `None == None` on both
    sides of the startup witness, the per-cell check and row admission. The
    identity would pass while sealing nothing at all.

    When NEITHER holds, the vendored name is returned unchanged and the walk
    fails closed on it exactly as before: `unreadable` names the missing root
    and the digest is `None`, which every caller treats as a refusal."""
    return _execution_root_under(repo_root(root))


def _execution_root_under(top: Path) -> str:
    """`execution_root_for`, with the repository top level already in hand.
    Split out because the pre-request check re-derives the execution tree
    before EVERY provider request, and `repo_root` is a `git` subprocess."""
    try:
        if (Path(top) / VENDORED_EXECUTION_ROOT).is_dir():
            return VENDORED_EXECUTION_ROOT
    except OSError:                                                        # noqa: BLE001
        pass
    if _is_package_directory(Path(top)):
        return "."
    return VENDORED_EXECUTION_ROOT


def execution_paths_for(root: Path | None = None) -> tuple[str, ...]:
    """The CLOSED path set — the whole package directory — as it is named in
    the repository that holds it. `("**",)` when the package IS the repository
    top level; the walk and the git pathspecs both read it the same way."""
    relative = execution_root_for(root)
    return ("**",) if relative == "." else (f"{relative}/**",)


#: The execution root of THIS package, relative to its own repository: what the
#: walk descends and what the manifest records. Resolved once at import; every
#: function that takes a `root` re-resolves for that root.
EXECUTION_ROOT = execution_root_for()
EXECUTION_PATHS = execution_paths_for()


def git_head(root: Path | None = None) -> str | None:
    """The commit that will execute this schedule. `None` when the checkout
    is not a git repository or `git` is unavailable — never guessed."""
    code, out = _git(root or ROOT, "rev-parse", "HEAD")
    return out or None if code == 0 else None


def git_tree_status(root: Path | None = None) -> tuple[bool, str]:
    """`(clean, detail)`. A schedule may only be SEALED against a clean tree:
    an instrument commit that does not describe the files that will actually
    run is provenance theatre. `--seal` refuses a dirty tree; the startup
    witness refuses to execute one."""
    code, out = _git(root or ROOT, "status", "--porcelain")
    if code != 0:
        return False, f"git status failed: {out}"
    if out:
        return False, "uncommitted changes:\n" + "\n".join(out.splitlines()[:20])
    return True, "clean"


def git_is_ancestor(ancestor: str | None, descendant: str | None, root: Path | None = None) -> bool:
    """Is `ancestor` reachable from `descendant`? A commit is its own
    ancestor, so a run at the sealed commit itself passes. `False` whenever
    either name is missing or git cannot answer — never assumed."""
    if not ancestor or not descendant:
        return False
    code, _ = _git(root or ROOT, "merge-base", "--is-ancestor", ancestor, descendant)
    return code == 0


def git_diff_execution_paths(base: str | None, head: str | None, root: Path | None = None,
                             paths=None) -> tuple[bool, list[str]]:
    """`(empty, changed_files)` for `git diff base..head` restricted to the
    execution paths. `(False, ["<git failed: ...>"])` when git cannot answer:
    "I could not check" is not "nothing changed"."""
    if not base or not head:
        return False, ["<no commit to compare>"]
    code, out = _git(root or ROOT, "diff", "--name-only", f"{base}..{head}", "--",
                     *_pathspecs(paths, root))
    if code != 0:
        return False, [f"<git diff failed: {out}>"]
    changed = [line.strip() for line in out.splitlines() if line.strip()]
    return (not changed), changed


def git_execution_tree_status(root: Path | None = None, paths=None) -> tuple[bool, str]:
    """`(clean, detail)` for the WORKING TREE over the execution paths only.

    A dirty evidence file — `reviews/arms_*.log`, a notes directory, a root
    `*.md` — is not a reason to refuse a run: those files are written BY the
    run. A dirty `tests/` or `beancount_ledger/` file is: the sealed digest
    then describes bytes that are not the bytes about to execute."""
    code, out = _git(root or ROOT, "status", "--porcelain", "--", *_pathspecs(paths, root))
    if code != 0:
        return False, f"git status failed: {out}"
    if out:
        return False, ("uncommitted changes under the sealed execution paths:\n"
                       + "\n".join(out.splitlines()[:20]))
    return True, "clean over the execution paths"


def execution_tree_manifest(root: Path | None = None, execution_root: str | None = None,
                            excludes=EXECUTION_EXCLUDES) -> dict:
    """Every file ON DISK under the execution root, with the sha256 of its
    ACTUAL BYTES: `{"files": [(relative_posix_path, sha256), ...], ...}`.

    WHY THE DISK AND NOT GIT (adversarial review, attack 1(h)).
    Version 1 of this identity asked git three questions — `git status`,
    `git diff`, `git ls-tree` — and all three answer about the INDEX, not about
    the bytes the interpreter will import. Three working defeats, each leaving
    the witness fully green:

      (A) `git update-index --assume-unchanged tests/measure_budget.py` (or
          `--skip-worktree`), then edit the file. `git status` is silent,
          `git ls-tree` reports the sealed blob, and the old digest recomputed
          to the sealed value while the file on disk had changed.
      (B) MODULE SHADOWING. Any new `environments/beancount_ledger/<name>.py`
          sat outside the three sealed subtrees, yet the package root is
          `sys.path[0]` for every cell process — an unsealed `openai.py` there
          was imported in place of the real library, and `tests/` siblings can
          shadow the instrument's own modules the same way.
      (C) A new file inside `tests/` hidden by a committed `.gitignore` line —
          `.gitignore` lives on an EVIDENCE path, so adding the line is
          permitted, and the file it hides is invisible to both `git status`
          and `git ls-tree` while `tests/` is `sys.path[0]`.

    So the digest walks the directory and hashes what is there. The RELATIVE
    FILE SET is part of the digest material, so an ADDED or REMOVED file moves
    it even when every surviving file is untouched — which is what kills (B)
    and (C). Reading each file's bytes is what kills (A).

    The git checks are kept as SECONDARY evidence: they say something the walk
    cannot (which commit this content corresponds to, and whether anything
    changed since the seal in a way a reviewer could read as a diff), but they
    are no longer the identity.
    """
    # `None` means "ask THIS repository where its package directory is" (the
    # vendored `environments/beancount_ledger`, or the repository top level in
    # a standalone checkout). An explicit string is honoured as given, so a
    # caller can still name a root that does not exist and get the refusal.
    top = repo_root(root)
    execution_root = _execution_root_under(top) if execution_root is None else execution_root
    base = top if execution_root == "." else top / execution_root
    files: list[tuple[str, str]] = []
    unreadable: list[str] = []
    if not base.is_dir():
        return {"files": [], "unreadable": [f"the execution root {base} is not a directory"],
                "execution_root": execution_root, "excludes": list(excludes), "bytes": 0}
    total = 0
    for directory, subdirectories, names in os.walk(base):
        here = Path(directory)
        relative_dir = here.relative_to(base).as_posix()
        relative_dir = "" if relative_dir == "." else relative_dir + "/"
        # Prune excluded directories rather than walking into them: `.venv`
        # alone is tens of thousands of files.
        subdirectories[:] = [d for d in sorted(subdirectories)
                             if not _excluded(f"{relative_dir}{d}/x", excludes)]
        for name in sorted(names):
            relative = f"{relative_dir}{name}"
            if _excluded(relative, excludes):
                continue
            try:
                data = (here / name).read_bytes()
            except OSError as exc:                                         # noqa: BLE001
                unreadable.append(f"{relative}: {type(exc).__name__}")
                continue
            total += len(data)
            files.append((relative, hashlib.sha256(data).hexdigest()))
    return {"files": sorted(files), "unreadable": sorted(unreadable),
            "execution_root": execution_root, "excludes": list(excludes), "bytes": total}


def execution_tree_digest(root: Path | None = None, execution_root: str | None = None,
                          excludes=EXECUTION_EXCLUDES) -> str | None:
    """sha256 over the sorted `(relative path, sha256 of the file's bytes)`
    pairs on disk, plus the root and the exclusion list themselves.

    `None` when the tree cannot be read at all — the caller must treat that as
    a refusal, never as a match. A file that exists but cannot be read makes
    the manifest carry it under `unreadable`, which is part of the material:
    an unreadable instrument file is a changed instrument."""
    return manifest_digest(execution_tree_manifest(root, execution_root, excludes))


def manifest_digest(manifest: dict) -> str | None:
    """The digest of an already-computed manifest, so the sealer and the
    witness walk the tree ONCE for both the digest and the file count."""
    if not manifest["files"]:
        # An EMPTY path set must never produce a digest (adversarial review,
        # INFO): a digest over nothing compares equal to a digest over
        # nothing, so a mis-set execution root would witness itself green.
        return None
    payload = {"instrument_identity_version": INSTRUMENT_IDENTITY_VERSION,
               "execution_root": manifest["execution_root"],
               "excludes": manifest["excludes"],
               "unreadable": manifest["unreadable"],
               "files": [list(pair) for pair in manifest["files"]]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# THE RUNTIME ENVIRONMENT IDENTITY
#
# The execution-tree digest stops at the repository boundary: `.venv/**` is
# excluded from it, and the replacement binding was version STRINGS —
# `importlib.metadata.version("openai")`, `version("verifiers")`, the Python
# version. But an in-place edit to a file under
# `.venv/Lib/site-packages/openai/` changes request construction, retries,
# response interpretation or token accounting while `METADATA` still reports
# the sealed version. It is the site-packages analogue of the module-shadow
# attack, it needs no new distribution and no `sys.path` change, and the
# transitive packages are even less covered than the two named ones.
#
# So the seal binds the BYTES of the whole runtime environment:
#
#   1. every file under every directory the running interpreter can IMPORT
#      from — the site-package roots AND the standard library — hashed from its
#      actual bytes: not only the two named distributions, not only the files a
#      RECORD happens to mention, and not only what pip installed. Hashing
#      `python312.dll` does not cover `json/encoder.py` or `ssl.py`, and those
#      shape every provider request;
#   2. every distribution's RECORD, enumerated: each referenced file is
#      located and hashed, its RECORD-DECLARED sha256 is verified where the
#      wheel published one, and a mismatch is recorded IN the material; a
#      referenced file that no longer exists is recorded as missing;
#   3. the files under site-packages that NO RECORD references — the shadow
#      analogue: an added module is invisible to `importlib.metadata` exactly
#      as a shadowing `.py` beside the package was invisible to `package_lock`;
#   4. the INTERPRETER as bytes: `sys.executable` itself and the `pythonXY`
#      runtime library beside it (or, for a venv whose `Scripts/` carries only
#      the launcher, the one beside `sys.base_prefix`), plus `sys.version`.
#
# THE ROOTS COME FROM THE RUNNING INTERPRETER (`sysconfig`/`sys.prefix`),
# never from a repository-relative `.venv` path: a worktree has no `.venv` at
# all, and the digest must describe the interpreter that will execute cells,
# not one that happens to sit beside the checkout.
#
# Keys are stated relative to `sys.prefix` / `sys.base_prefix` so the manifest
# reads as `prefix/Lib/site-packages/openai/_client.py` rather than as an
# absolute path, and so the digest does not move when the same environment is
# reached from a worktree.
#
# AND (identity version 2, the adversarial review):
#
#   5. THE IMPORT ENVIRONMENT (C1). `PYTHONPATH` was not in the walk. A
#      directory named there is PREPENDED to `sys.path` and shadows any sealed
#      module while every hashed byte — and therefore the digest — stays
#      identical. `sys_path_survey` classifies every entry against the walked
#      roots and the execution root and reports the UNCOVERED ones by name;
#      an empty list is the healthy state, and the startup witness refuses on
#      a non-empty one. `run_arms` strips the injecting variables from every
#      confirmatory cell's environment as the other half of the same closure;
#   6. THE REST OF `sys.path` (C3). `base_prefix/DLLs` (37 extension modules,
#      `_ssl.pyd` and `_socket.pyd` among them), the `base_prefix/pythonXY.zip`
#      slot, `prefix/pyvenv.cfg` and everything in `Scripts/` that no RECORD
#      references were all outside the walk. The roots now come from `sys.path`
#      itself, keeping the entries inside the interpreter's own prefixes —
#      which on this machine collapses to `sys.prefix` and `sys.base_prefix`
#      and subsumes all four.
#
# EXCLUSIONS, BY NAME ONLY: `__pycache__/` directories and `*.pyc`. Bytecode
# is written by the very act of importing, so including it would make the
# digest non-stationary across the run it is supposed to authenticate — and
# this venv is shared by every process on the machine.
#
# THE EXCLUSION IS SOUND, NOT MERELY CONVENIENT (C2). An excluded `.pyc` that
# the interpreter still LOADS is a hole: an existing cache file edited in place
# keeps its recorded source mtime and size, so timestamp validation accepts it
# forever and a tampered body executes without the sealed `.py` ever being
# read. So the executor redirects `PYTHONPYCACHEPREFIX` to a FRESH per-session
# directory for every cell subprocess and for its own package import
# (`run_arms.fresh_bytecode_cache_prefix`). No pre-existing `__pycache__` is on
# the path, the fresh tree is written from the sealed `.py` bytes on first
# import, and what the exclusion skips is then only bytecode this session
# generated from bytes this manifest hashed.
#
# `*.dist-info/RECORD` is INCLUDED as bytes: it is the file that says what the
# distribution is. The residual is named in `reviews/confirmatory_design.md`.
# ---------------------------------------------------------------------------

#: Bumping this changes every runtime-environment digest and therefore every
#: sealed schedule id: the ALGORITHM that computes the identity is part of it.
#: Version 2 is the `sys.path`-derived walk with the import-environment survey
#: (C1, C3); version 1 walked `sysconfig`'s roots only, and left `PYTHONPATH`,
#: `DLLs/`, the `pythonXY.zip` slot, `pyvenv.cfg` and unreferenced `Scripts/`
#: files outside the seal.
RUNTIME_ENVIRONMENT_IDENTITY_VERSION = 2
ENVIRONMENT_EXCLUDED_DIR_NAMES = ("__pycache__",)
ENVIRONMENT_EXCLUDED_SUFFIXES = (".pyc",)
#: Environment variables that inject importable code, or a path to it, into a
#: subprocess before a line of the sealed instrument runs. `PYTHONPATH`
#: prepends directories to `sys.path`; `PYTHONHOME` relocates the standard
#: library wholesale; `PYTHONSTARTUP` names a file the interpreter executes.
#: `run_arms.sanitized_cell_environment` strips all three in confirmatory mode.
IMPORT_INJECTING_ENVIRONMENT_VARS = ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP")

_ENVIRONMENT_MANIFEST: dict | None = None


def _environment_key(path: Path) -> str:
    """A path stated relative to `sys.prefix` (the venv), `sys.base_prefix`
    (the interpreter it was made from) or the EXECUTION ROOT, POSIX, so the
    manifest is readable and does not move between a checkout and its
    worktree. An absolute key is the honest fallback for a RECORD entry that
    points outside all three.

    `sys.prefix` is tried FIRST because this venv lives INSIDE the execution
    root (`environments/beancount_ledger/.venv`), and the execution root is
    tried at all because `sys.path` carries the package directory and
    `tests/` — a worktree's copies of which are at different absolute paths,
    and an absolute key there would move the digest between checkouts of the
    same content.

    A path that IS one of the bases keys as the bare label (`prefix`), never
    as `prefix/.`: the walk joins the label to each relative path, and a `/.`
    in the middle would make every file key differ from the RECORD-derived key
    for the same file."""
    for base, label in ((sys.prefix, "prefix"), (sys.base_prefix, "base_prefix"),
                        (str(ROOT), "execution_root")):
        if not base:
            continue
        try:
            relative = Path(path).resolve().relative_to(Path(base).resolve()).as_posix()
        except (ValueError, OSError):
            continue
        return label if relative == "." else f"{label}/{relative}"
    try:
        return "abs/" + Path(path).resolve().as_posix()
    except OSError:
        return "abs/" + Path(path).as_posix()


def _join_key(base_key: str, relative: str) -> str:
    """`base_key` joined with a RECORD-relative path, normalised as a STRING.
    RECORD entries routinely escape their own directory (`../../Scripts/x.exe`),
    and doing this without touching the filesystem is what keeps the walk over
    16k RECORD entries cheap enough to run per cell."""
    parts = [p for p in base_key.split("/") if p]
    for piece in str(relative).replace("\\", "/").split("/"):
        if piece in ("", "."):
            continue
        if piece == "..":
            if parts:
                parts.pop()
            continue
        parts.append(piece)
    return "/".join(parts)


def _digest_file(path) -> tuple[str | None, int, str | None]:
    """`(sha256_hex, bytes, error)` from the file's ACTUAL BYTES, streamed:
    `hashlib.file_digest` never materialises a 40 MB wheel payload in Python,
    which is what makes hashing 376 MB of site-packages a seconds-scale
    operation rather than a minutes-scale one."""
    try:
        with open(path, "rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
            size = os.fstat(handle.fileno()).st_size
        return digest, size, None
    except OSError as exc:                                                 # noqa: BLE001
        return None, 0, type(exc).__name__


def site_package_roots() -> list[Path]:
    """The RUNNING interpreter's own `purelib`/`platlib` (identical in a
    Windows venv, distinct on some platforms), resolved from `sysconfig` —
    i.e. from `sys.prefix` — and never from a path relative to this file."""
    roots: list[Path] = []
    for key in ("purelib", "platlib"):
        try:
            path = Path(sysconfig.get_paths()[key]).resolve()
        except (KeyError, OSError):                                        # noqa: BLE001
            continue
        if path not in roots:
            roots.append(path)
    return roots


def interpreter_layout() -> dict:
    """The PLATFORM'S OWN NAMES for the four `sys.path` members that are
    neither site-packages nor the standard library proper — asked of
    `sysconfig` and of the interpreter, never spelled as a Windows literal.

    The C3 closure was written against one layout and named it directly:
    `base_prefix/DLLs/*.pyd`, `prefix/Scripts/`, `base_prefix/pythonXY.zip`.
    Those are the WINDOWS names of four things every CPython has:

      `extension_dir`     the compiled extension modules the interpreter
                          imports before any `.py` in the standard library can
                          run — `_ssl`, `_socket`, `select`, `pyexpat`. Windows
                          keeps them in `base_prefix/DLLs`; POSIX keeps them in
                          `<stdlib>/lib-dynload` (`sysconfig`'s `DESTSHARED`).
      `extension_suffix`  what one of those files is called at the end:
                          `.pyd` or `.so`, taken from `EXT_SUFFIX` rather than
                          assumed.
      `scripts_dir`       the console scripts and the activation shims:
                          `prefix/Scripts` or `prefix/bin`. `sysconfig`'s
                          `scripts` path is the portable name of both.
      `zip_slot`          the `pythonXY.zip` entry that PRECEDES the standard
                          library on `sys.path`. It sits beside the stdlib
                          directory on every platform — `base_prefix/` on
                          Windows because the stdlib is `base_prefix/Lib`,
                          `base_prefix/lib/` on POSIX because the stdlib is
                          `base_prefix/lib/pythonX.Y`. Usually absent on disk;
                          creating it shadows the whole standard library,
                          which is why its ABSENCE is sealed.

    `script_suffix` is only the extension the witness gives the file it adds to
    `scripts_dir`; nothing imports it, it just has to be a plausible name for
    the platform.

    Every value is a NAME, computed without requiring the thing to exist: the
    zip slot's whole point is that it usually does not, and the witness has to
    be able to say which path it means."""
    version = f"{sys.version_info.major}{sys.version_info.minor}"
    try:
        stdlib = Path(sysconfig.get_paths()["stdlib"])
    except (KeyError, OSError):                                            # noqa: BLE001
        stdlib = Path(sys.base_prefix) / "Lib"
    try:
        scripts = Path(sysconfig.get_paths()["scripts"])
    except (KeyError, OSError):                                            # noqa: BLE001
        scripts = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
    # `<stdlib>/lib-dynload` is asked FIRST because a relocated interpreter
    # (uv's managed CPython, a python-build-standalone tarball) can carry a
    # `DESTSHARED` that still names the directory the build was staged in,
    # while the stdlib path is resolved from the running interpreter. On
    # Windows neither exists, and the answer is `base_prefix/DLLs`.
    extension_dir = Path(sys.base_prefix) / "DLLs"
    for candidate in (stdlib / "lib-dynload", sysconfig.get_config_var("DESTSHARED"),
                      Path(sys.base_prefix) / "DLLs"):
        if not candidate:
            continue
        try:
            path = Path(candidate)
            if path.is_dir():
                extension_dir = path
                break
        except OSError:                                                    # noqa: BLE001, PERF203
            continue
    full_suffix = sysconfig.get_config_var("EXT_SUFFIX") or ""
    extension_suffix = os.path.splitext(full_suffix)[1] or full_suffix or (
        ".pyd" if sys.platform == "win32" else ".so")
    return {"extension_dir": extension_dir,
            "extension_suffix": extension_suffix,
            "scripts_dir": scripts,
            "script_suffix": ".bat" if sys.platform == "win32" else ".sh",
            "zip_slot": stdlib.parent / f"python{version}.zip"}


def environment_prefixes() -> list[Path]:
    """The interpreter's OWN two prefixes: the venv (`sys.prefix`) and the
    installation it was made from (`sys.base_prefix`). Everything inside them
    is the runtime environment; a `sys.path` entry outside both is something
    else, and the survey below names it."""
    out: list[Path] = []
    for base in (sys.prefix, sys.base_prefix):
        if not base:
            continue
        try:
            path = Path(base).resolve()
        except OSError:                                                    # noqa: BLE001
            continue
        if path not in out:
            out.append(path)
    return out


def _within(path: Path, base: Path) -> bool:
    return path == base or base in path.parents


def sys_path_entries() -> list[tuple[str, Path | None]]:
    """`sys.path` as `(raw entry, resolved path or None)`, in order.

    The EMPTY entry means "the current working directory" and is resolved to
    what it means: an empty string is not a thing anyone can seal, and the
    directory it stands for is importable exactly like a named one."""
    out: list[tuple[str, Path | None]] = []
    for raw in list(sys.path):
        try:
            text = str(raw) if str(raw) else os.getcwd()
            out.append((str(raw), Path(text).resolve()))
        except OSError:                # a deleted cwd makes getcwd() itself raise
            out.append((str(raw), None))
    return out


def environment_roots() -> list[Path]:
    """Every directory the running interpreter can IMPORT from and that
    belongs to the interpreter itself: the site-package roots, the STANDARD
    LIBRARY, `Scripts/`, `base_prefix/DLLs`, and every other `sys.path`
    directory that lies inside `sys.prefix` or `sys.base_prefix`.

    Hashing `python312.dll` does not cover the stdlib. `sysconfig`'s `stdlib`
    for a venv is `base_prefix/Lib` — the real `json/encoder.py`, `ssl.py`,
    `subprocess.py`, `asyncio/` the client imports on every request — and an
    edit there changes provider behaviour exactly as an edit under
    `site-packages/openai/` does. The closure names "the interpreter and
    relevant runtime library identity"; the stdlib IS that library.

    THE C3 CLOSURE (adversarial review). `sysconfig`'s
    `purelib`/`stdlib` are not all of `sys.path`. Four real entries sat
    outside the walk:

      * `base_prefix/DLLs` — 37 extension modules, `_ssl.pyd`, `_socket.pyd`,
        `select.pyd`, `pyexpat.pyd`. Every one of them is imported on a
        provider request, and none of them is a `.py` under `Lib`;
      * `base_prefix/pythonXY.zip` — a SLOT that precedes `Lib` on `sys.path`.
        It does not exist here, and creating it would shadow the entire
        standard library. The survey seals its ABSENCE, so creating it moves
        the digest;
      * `prefix/pyvenv.cfg` — the file that says which interpreter this venv
        points at and whether system site-packages are visible;
      * `prefix/Scripts/` — only the RECORD-referenced console scripts were
        hashed, so an ADDED file there (a `python.bat` shim, a replaced
        `activate`) was invisible.

    Those four are the WINDOWS NAMES of four things every CPython has, and
    `interpreter_layout()` is where the platform's own names for them live:
    the extension modules are `base_prefix/DLLs/*.pyd` on Windows and
    `<stdlib>/lib-dynload/*.so` on POSIX; the console scripts and activation
    shims are `prefix/Scripts` on Windows and `prefix/bin` on POSIX (both are
    `sysconfig`'s `scripts` path); the zip slot sits beside the stdlib
    directory on both. All of them are named as CANDIDATES below, so the walk
    covers them because it was told to and not because one platform happens to
    nest them inside a root that was already there.

    The generalisation that covers all four, and C1's `PYTHONPATH` shadow with
    them: take the roots from `sys.path` itself, keeping the ones the
    interpreter owns. On this machine that collapses to `sys.prefix` and
    `sys.base_prefix` themselves — both are on `sys.path` — which SUBSUMES
    site-packages, the stdlib, `DLLs`, `Scripts` and `pyvenv.cfg` in two
    walks. The named candidates are kept anyway so a layout that does not put
    the prefixes on `sys.path` still seals them.

    NESTED ROOTS ARE DROPPED: `platstdlib` is the venv's own `Lib`, which
    CONTAINS `site-packages`, so walking both would hash every installed file
    twice under the same key and double-count the byte total. After the C3
    generalisation this matters more, not less — `sys.prefix` contains
    `site-packages`, and `sys.base_prefix` contains `Lib` and `DLLs`."""
    candidates: list[Path] = list(site_package_roots())
    for key in ("stdlib", "platstdlib", "scripts"):
        try:
            path = Path(sysconfig.get_paths()[key]).resolve()
        except (KeyError, OSError):                                        # noqa: BLE001
            continue
        if path.is_dir() and path not in candidates:
            candidates.append(path)
    # The EXTENSION MODULE directory under its platform's own name
    # (`base_prefix/DLLs` on Windows, `<stdlib>/lib-dynload` on POSIX) and the
    # console-script directory, named explicitly so the walk does not depend on
    # a layout accident. On POSIX both are nested inside a root that is already
    # a candidate (`lib-dynload` under `stdlib`, and `bin` is `sysconfig`'s own
    # `scripts` path above), so the maximal-root rule below drops them again
    # and the digest does not move; naming them here is what makes the coverage
    # a stated fact rather than a consequence of where CPython happens to put
    # them on one platform.
    layout = interpreter_layout()
    for named in (layout["extension_dir"], layout["scripts_dir"]):
        try:
            path = Path(named).resolve()
        except OSError:                                                    # noqa: BLE001, PERF203
            continue
        if path.is_dir() and path not in candidates:
            candidates.append(path)
    prefixes = environment_prefixes()
    for _raw, resolved in sys_path_entries():
        if resolved is None or not resolved.is_dir():
            continue
        if any(_within(resolved, prefix) for prefix in prefixes) and resolved not in candidates:
            candidates.append(resolved)
    maximal = [p for p in candidates
               if not any(other != p and other in p.parents for other in candidates)]
    return sorted(set(maximal), key=str)


def environment_extra_files() -> list[Path]:
    """Files that are part of the environment but may sit outside every walked
    root on some layout. `pyvenv.cfg` is the venv's own definition — which
    interpreter it points at, whether the system site-packages are visible —
    and it is a file, so no directory walk names it unless `sys.prefix` itself
    is a root."""
    out: list[Path] = []
    try:
        cfg = (Path(sys.prefix) / "pyvenv.cfg").resolve()
    except OSError:                                                        # noqa: BLE001
        return out
    if cfg.is_file():
        out.append(cfg)
    return out


def sys_path_survey(roots: list[Path] | None = None) -> dict:
    """Every `sys.path` entry, classified against what the manifest walks —
    the C1(b) closure.

    `PYTHONPATH` was not in the walk at all. A directory named there is
    PREPENDED to `sys.path`, so it shadows any sealed module — `openai/`,
    `json/`, `ssl.py` — while every hashed byte stays identical and the digest
    stays identical with them. `run_arms` passed `os.environ` straight to
    every cell subprocess, so the shadow reached the process that spends the
    provider call.

    The closure has two halves. `run_arms.sanitized_cell_environment` STRIPS
    the injecting variables from every confirmatory cell's environment; this
    survey is the other half, and it fires earlier — an entry that is neither
    inside the interpreter's own prefixes nor inside the execution root is
    reported as UNCOVERED, by name, and the startup witness refuses on it
    before request 1. An empty `uncovered` list is the healthy state.

    The four statuses that are not `uncovered`:

      `walked`          inside a root this manifest hashes;
      `execution_tree`  inside the package directory — `tests/` and the
                        package root are `sys.path[0]` and `sys.path[1]` for
                        every process here, and they are sealed by the OTHER
                        half of the instrument identity, `execution_tree_digest`;
      `file`            a real file on `sys.path` (a `pythonXY.zip`), hashed;
      `absent`          a `sys.path` slot with nothing at it. Sealed as absent
                        BECAUSE it is importable the moment it exists:
                        `base_prefix/python312.zip` precedes `Lib`, so
                        creating it shadows the whole standard library.

    An uncovered directory is ALSO walked, so its bytes reach the digest —
    unless it CONTAINS a walked root or the execution root, which would turn
    `PYTHONPATH=C:\\` into an hour-long walk. Those are recorded as
    `uncovered_container` and named just the same: the refusal does not depend
    on having hashed them."""
    roots = environment_roots() if roots is None else roots
    execution_root = ROOT.resolve()
    records: list[list[str]] = []
    order: list[str] = []
    uncovered: list[str] = []
    extra_roots: list[Path] = []
    files: list[Path] = []
    seen: set[str] = set()
    for raw, resolved in sys_path_entries():
        key = _environment_key(resolved) if resolved is not None else f"unresolvable/{raw}"
        order.append(key)
        if key in seen:
            continue
        seen.add(key)
        if resolved is None:
            status = "unresolvable"
        elif resolved.is_file():
            status = "file"
            files.append(resolved)
        elif not resolved.is_dir():
            status = "absent"
        elif any(_within(resolved, root) for root in roots):
            status = "walked"
        elif _within(resolved, execution_root):
            status = "execution_tree"
        elif (any(_within(root, resolved) for root in roots)
              or _within(execution_root, resolved)):
            status = "uncovered_container"
            uncovered.append(key)
        else:
            status = "uncovered"
            uncovered.append(key)
            extra_roots.append(resolved)
        records.append([key, status])
    return {"records": sorted(records), "order": order, "uncovered": sorted(uncovered),
            "extra_roots": extra_roots, "files": files}


def interpreter_files() -> list[tuple[str, Path]]:
    """`[(label, path)]` for the interpreter AS BYTES: the executable itself
    and the `pythonXY` runtime library. A stdlib `venv` copies only the
    launcher into `Scripts/`, so when nothing matches beside the executable the
    search falls back to `sys.base_prefix` — measured on this machine:
    `Scripts/` carries no `python*.dll`, and `base_prefix` carries
    `python3.dll` and `python312.dll`."""
    out: list[tuple[str, Path]] = []
    if not sys.executable:
        return out
    exe = Path(sys.executable)
    out.append(("executable", exe))
    patterns = ("python*.dll", "libpython*.so*", "libpython*.dylib")
    libraries: list[Path] = []
    for directory in (exe.parent, Path(sys.base_prefix), Path(sys.base_prefix) / "lib"):
        try:
            for pattern in patterns:
                libraries += sorted(p for p in directory.glob(pattern) if p.is_file())
        except OSError:                                                    # noqa: BLE001
            continue
        if libraries:
            break
    for library in libraries:
        out.append((f"runtime_library:{library.name.lower()}", library))
    return out


def runtime_environment_manifest(use_cache: bool = True) -> dict:
    """Every installed distribution's RECORD, every file under the site-package
    roots, every file no RECORD references, and the interpreter — all by the
    sha256 of their ACTUAL BYTES.

    `use_cache` is TRUE for the startup witness and for row provenance (one
    walk per process) and FALSE for the per-cell verification, which must
    describe the environment as it is at that moment rather than as it was when
    the process started.
    """
    global _ENVIRONMENT_MANIFEST                                          # noqa: PLW0603
    if use_cache and _ENVIRONMENT_MANIFEST is not None:
        return _ENVIRONMENT_MANIFEST

    roots = environment_roots()
    site_roots = site_package_roots()
    survey = sys_path_survey(roots)
    files: dict[str, str] = {}
    unreadable: list[str] = []
    total = 0

    # 1. THE BYTES UNDER EVERY IMPORTABLE ROOT — the site-package roots, the
    #    standard library, `Scripts/`, `DLLs/`, and every other `sys.path`
    #    directory inside the interpreter's own prefixes (C3). Everything under
    #    them, not only what a RECORD mentions: an added module is exactly what
    #    no RECORD mentions, and an added `Scripts/` file is exactly what no
    #    RECORD mentions either.
    #
    #    An UNCOVERED `sys.path` directory is walked too, under its own
    #    absolute key, so a `PYTHONPATH` shadow reaches the digest as bytes as
    #    well as reaching the witness by name (C1). It is not a walked ROOT:
    #    the survey above already recorded it as uncovered, and the witness
    #    refuses on that record whether or not the walk could read it.
    #
    #    `walked_keys` is the set of directories this loop covers, as manifest
    #    keys. Step 2 classifies every RECORD entry against IT rather than
    #    against "is this key already in `files`" — see the note there.
    walked_keys = tuple(_environment_key(r) for r in list(roots) + list(survey["extra_roots"]))
    for root in list(roots) + list(survey["extra_roots"]):
        root_key = _environment_key(root)
        if not root.is_dir():
            unreadable.append(f"{root_key}: not a directory")
            continue
        for directory, subdirectories, names in os.walk(root):
            subdirectories[:] = [d for d in sorted(subdirectories)
                                 if d not in ENVIRONMENT_EXCLUDED_DIR_NAMES]
            here = Path(directory)
            relative = here.relative_to(root).as_posix()
            prefix = root_key if relative == "." else f"{root_key}/{relative}"
            for name in sorted(names):
                if name.endswith(ENVIRONMENT_EXCLUDED_SUFFIXES):
                    continue
                key = f"{prefix}/{name}"
                if key in files:
                    # Two roots that overlap name the same file under the same
                    # key. The maximal-root rule prevents that among the
                    # environment roots; an UNCOVERED `PYTHONPATH` pair like
                    # `A` and `A/B` can still produce it, and hashing twice
                    # would double the byte total for no information.
                    continue
                digest, size, error = _digest_file(here / name)
                if error:
                    unreadable.append(f"{key}: {error}")
                    continue
                files[key] = digest
                total += size

    # 2. EVERY DISTRIBUTION'S RECORD. The file set above already covers what
    #    lives under the roots; this enumeration adds the entries that escape
    #    them (console scripts in `Scripts/`, data files), verifies the
    #    RECORD-DECLARED hash where a wheel published one, and names every
    #    referenced file that no longer exists.
    #
    #    `outside_roots` IS COUNTED FROM THE KEY, NOT FROM `files`. It used to
    #    be incremented whenever the entry's key was not yet in `files` — which
    #    made it depend on WHETHER THIS DISTRIBUTION HAD ALREADY BEEN
    #    ENUMERATED ONCE, because the first pass puts the file in `files` and
    #    the second therefore counts zero. `importlib.metadata` enumerates per
    #    `sys.path` ENTRY, so a duplicate entry (a `.pth`, a re-inserted path,
    #    a `PYTHONPATH` naming a directory that is already there) produced two
    #    records for the same distribution that differed ONLY in that field,
    #    the exact-duplicate collapse below could not collapse them, and the
    #    digest moved with no byte on disk having changed. On the Windows
    #    layout the field is 0 for every distribution — `sys.prefix` itself is
    #    a walked root, so nothing a RECORD names is outside one — and the bug
    #    was invisible; on POSIX the walked roots are `bin/`, the venv's `lib/`
    #    and the stdlib, a wheel that ships a man page under `prefix/share/`
    #    lands outside all three, and the seal stopped being stationary.
    #
    #    Counting from the key says the same thing about the FIRST enumeration
    #    (the walk covers exactly `walked_keys`, minus the names excluded on
    #    both sides) and says it identically about every later one.
    def _under_walked_root(key: str) -> bool:
        return any(key == root_key or key.startswith(root_key + "/")
                   for root_key in walked_keys)

    distributions: list[dict] = []
    referenced: set[str] = set()
    try:
        installed = list(importlib.metadata.distributions())
    except Exception as exc:                                               # noqa: BLE001
        installed = []
        unreadable.append(f"importlib.metadata.distributions(): {type(exc).__name__}")
    for dist in installed:
        try:
            name = dist.metadata["Name"]
        except Exception:                                                  # noqa: BLE001
            name = None
        record = {"name": name or "?", "version": getattr(dist, "version", None),
                  "base_key": None, "record_present": False, "record_entries": 0,
                  "missing": [], "declared_hash_mismatch": [], "outside_roots": 0}
        try:
            entries = dist.files
        except Exception as exc:                                           # noqa: BLE001
            entries = None
            unreadable.append(f"{record['name']}: RECORD unreadable ({type(exc).__name__})")
        if entries is None:
            distributions.append(record)
            continue
        record["record_present"] = True
        try:
            base_key = _environment_key(Path(dist.locate_file("")))
        except Exception:                                                  # noqa: BLE001
            base_key = _environment_key(site_roots[0]) if site_roots else "abs"
        # WHERE this distribution was found. Part of the record (and of the
        # digest) because the same name and version served from a different
        # root is a different environment — and because the de-duplication
        # below must not collapse two genuinely distinct copies into one.
        record["base_key"] = base_key
        for entry in entries:
            text = str(entry)
            if text.endswith(ENVIRONMENT_EXCLUDED_SUFFIXES) or "__pycache__" in text.replace("\\", "/"):
                continue                       # excluded by name, on both sides of the comparison
            record["record_entries"] += 1
            key = _join_key(base_key, text)
            referenced.add(key)
            if not _under_walked_root(key):
                # Outside the walked roots (a console script, a data file) —
                # located through the distribution itself and hashed below.
                record["outside_roots"] += 1
            if key not in files:
                try:
                    target = Path(dist.locate_file(entry))
                except Exception:                                          # noqa: BLE001
                    record["missing"].append(text)
                    continue
                digest, size, error = _digest_file(target)
                if error:
                    if target.exists():
                        unreadable.append(f"{key}: {error}")
                    else:
                        record["missing"].append(text)
                    continue
                files[key] = digest
                total += size
            declared = getattr(entry, "hash", None)
            if declared is not None and getattr(declared, "mode", None) == "sha256":
                got = base64.urlsafe_b64encode(bytes.fromhex(files[key])).rstrip(b"=").decode("ascii")
                if got != getattr(declared, "value", None):
                    record["declared_hash_mismatch"].append(text)
        record["missing"] = sorted(record["missing"])
        record["declared_hash_mismatch"] = sorted(record["declared_hash_mismatch"])
        distributions.append(record)

    # EXACT DUPLICATES ARE ONE DISTRIBUTION. `importlib.metadata` enumerates
    # per `sys.path` ENTRY, so a root that appears on `sys.path` twice — which
    # a `.pth`, a re-inserted path or a `PYTHONPATH` naming an already-present
    # directory all produce — reports all 112 distributions twice and moves the
    # digest without one byte on disk having changed. Two records are collapsed
    # only when they are identical in every field INCLUDING the base key, so a
    # genuinely shadowing second copy of a package (a different directory,
    # hence a different key) stays visible as the two distributions it is.
    seen_records: set[str] = set()
    unique: list[dict] = []
    for record in distributions:
        fingerprint = json.dumps(record, sort_keys=True, default=str)
        if fingerprint in seen_records:
            continue
        seen_records.add(fingerprint)
        unique.append(record)
    distributions = unique

    # 3. THE FILES NO RECORD REFERENCES — computed BEFORE the interpreter files
    #    are merged in, so the interpreter never reads as an unexplained extra,
    #    and only under the SITE-PACKAGE roots, where a RECORD is the thing that
    #    is supposed to account for a file. The standard library has no RECORD
    #    at all; counting all 1,211 of its files as "extras" would drown the one
    #    signal this field exists to carry — an unaccounted module dropped in
    #    beside the installed ones.
    site_prefixes = tuple(f"{_environment_key(r)}/" for r in site_roots)
    extra = sorted(key for key in files
                   if key not in referenced and key.startswith(site_prefixes))
    # The STANDARD LIBRARY proper: under `sysconfig`'s own `stdlib` path,
    # outside site-packages. Taken from THAT path and not from "any walked root
    # minus site-packages", because after the C3 generalisation the walked
    # roots are the two PREFIXES — `Scripts/`, `DLLs/`, `include/`, `libs/`
    # and `tcl/` are under them, and none of those is the standard library.
    # Not the console scripts and not the interpreter either: those reach the
    # manifest through their RECORD entry and through `interpreter_files()`,
    # and counting them here would make the field say something other than its
    # name.
    try:
        stdlib_prefix = _environment_key(Path(sysconfig.get_paths()["stdlib"]).resolve()) + "/"
    except (KeyError, OSError):                                            # noqa: BLE001
        stdlib_prefix = "\x00never"
    stdlib_files = sorted(key for key in files
                          if key.startswith(stdlib_prefix) and not key.startswith(site_prefixes))

    # 3b. THE `sys.path` ENTRIES THAT ARE FILES, and the environment files that
    #     no directory walk names. A `pythonXY.zip` on `sys.path` PRECEDES
    #     `Lib`, so its bytes decide what `import json` returns; `pyvenv.cfg`
    #     decides which interpreter this venv is and whether the system
    #     site-packages are visible.
    for path in list(survey["files"]) + list(environment_extra_files()):
        key = _environment_key(path)
        if key in files:
            continue
        digest, size, error = _digest_file(path)
        if error:
            unreadable.append(f"{key}: {error}")
            continue
        files[key] = digest
        total += size

    # 4. THE INTERPRETER, AS BYTES.
    interpreter: list[list[str]] = []
    for label, path in interpreter_files():
        key = _environment_key(path)
        digest, size, error = _digest_file(path)
        if error:
            unreadable.append(f"{key}: {error}")
            continue
        if key not in files:
            files[key] = digest
            total += size
        interpreter.append([label, key, digest])

    manifest = {
        "environment_identity_version": RUNTIME_ENVIRONMENT_IDENTITY_VERSION,
        "python_version": sys.version,
        "environment_roots": [_environment_key(r) for r in roots],
        "site_package_roots": [_environment_key(r) for r in site_roots],
        "stdlib_file_count": len(stdlib_files),
        "excluded_directory_names": list(ENVIRONMENT_EXCLUDED_DIR_NAMES),
        "excluded_suffixes": list(ENVIRONMENT_EXCLUDED_SUFFIXES),
        # THE IMPORT ENVIRONMENT ITSELF (C1(b)). `sys_path` is the SORTED,
        # de-duplicated classification and is digest material; `sys_path_order`
        # is the live order, reported but NOT sealed — three cooperating
        # processes (the sealer, the executor, each cell) build `sys.path` by
        # the same two insertions but a reader should not have to prove that
        # they produce the same permutation before the digests can be compared.
        # Order between two SEALED roots decides only which of two identical-
        # named modules wins, and both are hashed; order relative to an
        # UNSEALED entry is what matters, and any such entry is `uncovered`
        # whatever its position.
        "sys_path": survey["records"],
        "sys_path_order": survey["order"],
        "uncovered_sys_path": survey["uncovered"],
        "distributions": sorted(distributions, key=lambda d: (str(d["name"]), str(d["version"]),
                                                              str(d.get("base_key")))),
        "files": sorted(files.items()),
        "extra_files": extra,
        "interpreter": sorted(interpreter),
        "unreadable": sorted(unreadable),
        "bytes": total,
    }
    if use_cache:
        _ENVIRONMENT_MANIFEST = manifest
    return manifest


def environment_manifest_digest(manifest: dict) -> str | None:
    """sha256 over an already-computed runtime-environment manifest.

    `None` when the walk found NO file at all — a digest over nothing compares
    equal to a digest over nothing, so an interpreter whose site-packages could
    not be read must refuse rather than witness itself green (the same rule the
    execution-tree digest follows)."""
    if not manifest.get("files"):
        return None
    payload = {
        "environment_identity_version": manifest["environment_identity_version"],
        "python_version": manifest["python_version"],
        "environment_roots": manifest["environment_roots"],
        "site_package_roots": manifest["site_package_roots"],
        "excluded_directory_names": manifest["excluded_directory_names"],
        "excluded_suffixes": manifest["excluded_suffixes"],
        # The IMPORT ENVIRONMENT is material (C1(b)): a `PYTHONPATH` directory
        # shadows a sealed module without changing one hashed byte of the
        # roots, so "which entries are on `sys.path`, and which of them nothing
        # seals" has to be part of what the digest says.
        "sys_path": manifest["sys_path"],
        "uncovered_sys_path": manifest["uncovered_sys_path"],
        # The RECORD verdicts are MATERIAL, not commentary: a distribution
        # whose declared hash stops matching, or whose referenced file
        # disappears, is a changed environment even if the bytes of some other
        # file moved to compensate.
        "distributions": [[d["name"], d["version"], d.get("base_key"), d["record_present"],
                           d["record_entries"], d["missing"], d["declared_hash_mismatch"],
                           d["outside_roots"]]
                          for d in manifest["distributions"]],
        "files": [list(pair) for pair in manifest["files"]],
        "extra_files": manifest["extra_files"],
        "interpreter": manifest["interpreter"],
        "unreadable": manifest["unreadable"],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def runtime_environment_digest(use_cache: bool = True) -> str | None:
    """The digest of the runtime environment the RUNNING interpreter is."""
    return environment_manifest_digest(runtime_environment_manifest(use_cache))


def instrument_identity(root: Path | None = None, use_cache: bool = True) -> dict:
    """What the RUNTIME is, recorded separately from what was sealed: the
    HEAD that is executing, the on-disk execution-tree
    digest, and the runtime-environment digest. Stamped on every archived row
    and every execution-journal entry."""
    environment = runtime_environment_manifest(use_cache)
    return {"runtime_head": git_head(root),
            "execution_tree_digest": execution_tree_digest(root),
            "instrument_identity_version": INSTRUMENT_IDENTITY_VERSION,
            "runtime_environment_digest": environment_manifest_digest(environment),
            "runtime_environment_identity_version": RUNTIME_ENVIRONMENT_IDENTITY_VERSION}


def journal_path_for(reviews_dir: Path, schedule: dict) -> Path:
    """The execution journal for one schedule. Defined HERE so the executor,
    the startup witness (whose fail-closed probe must write to the same file)
    and the table all name the same path."""
    return Path(reviews_dir) / f"arms_{schedule['label']}_execution.jsonl"


# ---------------------------------------------------------------------------
# EXECUTION-JOURNAL HEALTH. Defined HERE, beside
# `journal_path_for`, because the executor (which must fail CLOSED before every
# append) and the table (which must refuse confirmatory estimands while the
# journal is unhealthy) have to mean the same thing by "healthy". The window
# ledger's own scan is the model: malformed bytes are never repaired and never
# deleted, and only an explicit, journalled operator recovery — an immutable
# SEGMENT BOUNDARY with a provenance record — makes them acknowledged.
# ---------------------------------------------------------------------------

#: The record an explicit `run_arms.py --recover-execution-journal` appends.
JOURNAL_RECOVERY_RECORD = "execution_journal_recovery"


def journal_scan(path) -> dict:
    """Read the WHOLE execution journal and report its health. Never raises,
    never writes.

    `{"events", "malformed", "unterminated_final_line",
    "acknowledged_through_line", "recoveries", "line_count", "healthy",
    "detail", "exists"}`.

    A malformed or non-object line is OUTSTANDING until a recovery record
    acknowledges it by line number. An unterminated final line is a process
    killed mid-append: appending after it concatenates two records into one
    malformed line and loses both, which is exactly how a malformed TAIL
    becomes a malformed MIDDLE."""
    empty = {"events": [], "malformed": [], "unterminated_final_line": False,
             "acknowledged_through_line": 0, "recoveries": [], "line_count": 0,
             "healthy": True, "detail": "", "exists": False}
    if not path:
        return empty
    path = Path(path)
    try:
        raw = path.read_bytes().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return empty
    except OSError as exc:                                                 # noqa: BLE001
        bad = dict(empty)
        bad.update({"healthy": False, "exists": True,
                    "detail": f"the execution journal cannot be read: {type(exc).__name__}: {exc}"})
        return bad
    pieces = raw.split("\n")
    unterminated = bool(raw) and not raw.endswith("\n")
    line_count = len(pieces) if unterminated else len(pieces) - 1
    events: list[dict] = []
    malformed: list[dict] = []
    recoveries: list[dict] = []
    acknowledged = 0
    for index, line in enumerate(pieces[:line_count], start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError:
            malformed.append({"line": index, "chars": len(line), "preview": line[:80]})
            continue
        if not isinstance(value, dict):
            malformed.append({"line": index, "chars": len(line), "preview": "a non-object JSON line"})
            continue
        events.append(value)
        if value.get("record") == JOURNAL_RECOVERY_RECORD:
            recoveries.append(value)
            through = value.get("acknowledged_through_line")
            if isinstance(through, int):
                acknowledged = max(acknowledged, through)
    outstanding = [m for m in malformed if m["line"] > acknowledged]
    healthy = not outstanding and not unterminated
    detail = ""
    if outstanding:
        detail = (f"{len(outstanding)} malformed line(s) at {[m['line'] for m in outstanding][:8]} that "
                  f"no recovery record acknowledges")
    elif unterminated:
        detail = (f"the final line (line {line_count}) has no terminating newline: a process was killed "
                  f"mid-append, and the next append would concatenate onto it and destroy both records")
    return {"events": events, "malformed": malformed, "unterminated_final_line": unterminated,
            "acknowledged_through_line": acknowledged, "recoveries": recoveries,
            "line_count": line_count, "healthy": healthy, "detail": detail, "exists": True}


def journal_health(path) -> dict:
    """The scan without its events — what the table renders and what the
    executor checks before every append."""
    scan = journal_scan(path)
    return {k: v for k, v in scan.items() if k != "events"}


def exclusion_record_path_for(schedule_path: Path) -> Path:
    """The configuration-exclusion record file that lives BESIDE the sealed
    schedule. Append-only, one immutable content-bound
    record per excluded (provider, model)."""
    return Path(str(schedule_path) + ".exclusions.jsonl")


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def manifest_identity() -> dict:
    """The ACTIVE release manifest's rotation id and a sha256 over its bytes.

    Asked of the package, never of a hardcoded path: `manifest.rotation_id()`
    and `manifest.manifest_path()` do their own resolution (environment
    first, then the evaluator's own directory), so this function has no
    knowledge of where the evaluator keeps its secrets and never reads or
    reproduces their content — only a digest of the manifest file leaves it.
    A development process (test secret, no manifest) gets `None` for both,
    which is a truthful statement about a development schedule, not a
    failure."""
    try:
        from beancount_ledger.graph import manifest as manifest_mod
    except Exception as exc:                                               # noqa: BLE001
        return {"rotation_id": None, "manifest_content_digest": None,
                "manifest_present": False, "note": f"unavailable: {type(exc).__name__}"}
    rotation = None
    try:
        rotation = manifest_mod.rotation_id()
    except Exception:                                                      # noqa: BLE001
        rotation = None
    digest, present = None, False
    if rotation:
        # Only when a rotation is actually active for THIS process. Under a
        # development/test secret `rotation_id()` is None and there is no
        # active manifest at all — hashing whatever file happens to sit at
        # the evaluator's manifest path would then attest to something this
        # process does not serve from.
        try:
            path = manifest_mod.manifest_path()
            present = Path(path).is_file()
            if present:
                digest = sha256_file(Path(path))
        except Exception:                                                  # noqa: BLE001
            pass
    return {"rotation_id": rotation, "manifest_content_digest": digest, "manifest_present": present}


def arm_contract(arms: list[str]) -> dict:
    """The literal treatment behind every arm LABEL in this schedule."""
    import measure_budget as mb
    contract = {}
    for arm in arms:
        cap, replay = mb.ARM_PRESETS[arm]
        contract[arm] = {"per_turn_max_tokens": cap, "reasoning_replay": bool(replay)}
    return contract


def package_lock() -> dict:
    """The library versions the replay projection is bound to, plus the
    interpreter. `replay_libraries` is exactly what a row archives under
    `library_versions`, so the executor can compare them field for field."""
    import measure_budget as mb
    return {"replay_libraries": mb.library_versions(), "python": sys.version.split()[0]}


def failure_map_digest() -> str:
    """One digest over everything the blind failure classification consults:
    the ordered bucket rules, the provider quota table (TPM and requests per
    minute, with the date it was read from the console), and the constants of
    the observed rolling-window rule. A change to any of them is a different
    analysis and must invalidate the schedule rather than silently reclassify
    an archived 429."""
    import arm_table as AT                      # lazy: arm_table imports THIS module
    payload = {
        "rules": [[bucket, rule, list(needles)] for bucket, rule, needles in AT.ERROR_CLASS_RULES],
        "capability_rules": [[b, r, list(n)] for b, r, n in AT.CAPABILITY_RULES],
        "http_status_rules": {str(code): list(verdict)
                              for code, verdict in sorted(AT.HTTP_STATUS_RULES.items())},
        "buckets": list(AT.FAILURE_BUCKETS),
        "model_quotas": {f"{p}/{m}": q for (p, m), q in sorted(AT.MODEL_QUOTAS.items())},
        "provider_tpm_defaults": dict(sorted(AT.PROVIDER_TPM_DEFAULTS.items())),
        "quota_source": AT.QUOTA_SOURCE,
        "window_seconds": AT.RATE_LIMIT_WINDOW_SECONDS,
        "window_rule_version": AT.WINDOW_RULE_VERSION,
        "majority_share": AT.ARM_INDUCED_MAJORITY_SHARE,
        # The FALLBACK behaviour must be bound too, not only the
        # tuple constants. The free-text path is where a bare `"429"` needle
        # survived the "no digit in any map needle" witness, so the needles it
        # uses AND the version of the algorithm that consults them are hashed.
        "classifier_algorithm_version": AT.CLASSIFIER_ALGORITHM_VERSION,
        "rate_limit_text_needles": list(AT.RATE_LIMIT_TEXT_NEEDLES),
        "admission_semantics": AT.ADMISSION_SEMANTICS,
        "window_evidence_fields": list(AT.WINDOW_EVIDENCE_FIELDS),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def expected_public_task_ids(selectors: list[str]) -> dict:
    """`{selector: public task id}`, minted ONCE per selector through the real
    serving door (`load_environment`), which is the only authority on what a
    selector currently serves. A manifest rotation changes these ids while
    every selector STRING stays the same — the defect this field exists to
    make impossible."""
    from beancount_ledger import beancount_ledger as env_mod
    ids = {}
    for selector in selectors:
        env = env_mod.load_environment(selector)
        ids[selector] = env.dataset[0]["info"]["task_id"] if len(env.dataset) else None
    return ids


def build_experiment_contract(arms: list[str], selectors: list[str], ceiling: int,
                              analysis_plan: Path, root: Path | None = None) -> dict:
    """Everything §2 asks the schedule to bind, computed HERE, once, at
    sealing time."""
    import measure_budget as mb
    from beancount_ledger import beancount_ledger as env_mod

    contract = arm_contract(arms)
    versions = mb.library_versions()
    tree = execution_tree_manifest(root)
    environment = runtime_environment_manifest()
    return {
        "experiment_contract_version": SEALED_SCHEDULE_VERSION,
        "instrument_commit": git_head(root),
        # The commit alone is not the identity.
        # The CLOSED execution-path set and the content digest over it are
        # what the startup witness re-checks; later commits are permitted
        # exactly while they change nothing under those paths.
        "instrument_identity_version": INSTRUMENT_IDENTITY_VERSION,
        "execution_paths": list(EXECUTION_PATHS),
        "execution_excludes": list(EXECUTION_EXCLUDES),
        "execution_tree_digest": manifest_digest(tree),
        # The file COUNT is sealed beside the digest so that an added or
        # removed file is named as such by the witness, rather than surfacing
        # only as an opaque digest mismatch. Module shadowing (attack 1(h)(B))
        # and a gitignore-hidden file (1(h)(C)) both ADD a file.
        "execution_tree_file_count": len(tree["files"]),
        # THE RUNTIME ENVIRONMENT, AS BYTES. `package_lock`
        # below stays — it is what a reader can compare at a glance — but it is
        # no longer the binding: a version string cannot distinguish an edited
        # `openai/_client.py` from the wheel that was installed.
        "runtime_environment_identity_version": RUNTIME_ENVIRONMENT_IDENTITY_VERSION,
        "runtime_environment_digest": environment_manifest_digest(environment),
        "runtime_environment_file_count": len(environment["files"]),
        "runtime_environment_bytes": environment["bytes"],
        "runtime_environment_distribution_count": len(environment["distributions"]),
        "runtime_environment_extra_file_count": len(environment["extra_files"]),
        "runtime_environment_stdlib_file_count": environment["stdlib_file_count"],
        # The IMPORT ENVIRONMENT (C1(b)). Sealed as its own field, not only
        # inside the digest, so the witness can name the offending path instead
        # of reporting an opaque digest mismatch. `[]` is the healthy state.
        "runtime_environment_uncovered_sys_path": list(environment["uncovered_sys_path"]),
        "python_version": environment["python_version"],
        "analysis_plan": str(Path(analysis_plan).name),
        "analysis_plan_sha256": sha256_file(Path(analysis_plan)),
        "arm_contract": contract,
        "expected_episode_contract_digest": env_mod.episode_contract_digest(ceiling),
        "episode_contract_version": getattr(env_mod, "EPISODE_CONTRACT_VERSION", None),
        "max_episode_output_tokens": ceiling,
        "expected_replay_contract_digest_by_arm": {
            arm: mb.replay_contract_digest(spec["reasoning_replay"], versions)
            for arm, spec in contract.items()},
        "replay_contract_version": mb.REPLAY_CONTRACT_VERSION,
        "package_lock": package_lock(),
        "failure_map_digest": failure_map_digest(),
        "manifest": manifest_identity(),
        "expected_public_task_id_by_selector": expected_public_task_ids(selectors),
        "provider_quotas": provider_quota_table(),
    }


def provider_quota_table() -> dict:
    """The provider's own published limits, as read from the user's console
    on the date named. Part of the hashed content: a 429 classified against a
    quota table is only interpretable if the table is pinned to the run."""
    import arm_table as AT
    return {"source": AT.QUOTA_SOURCE,
            # Mistral publishes the LIMITS but does not
            # document whether a request it rejects with a 429 consumes token
            # or request quota. That ignorance is itself part of the sealed
            # analysis — it is what forbids adding a rejected request's
            # estimate to consumed quota as fact — so it is hashed with the
            # numbers rather than left as a reader's assumption.
            "admission_semantics": AT.ADMISSION_SEMANTICS,
            "models": {f"{p}/{m}": dict(q) for (p, m), q in sorted(AT.MODEL_QUOTAS.items())}}


def build_schedule(label: str, roster: list[dict], selectors: list[str], arms: list[str],
                   replicates: int, date_stamp: str, sampling: dict, ceiling: int,
                   timeout: float, retries: int, min_interval: float,
                   experiment_contract: dict | None = None) -> dict:
    """One schedule. With `experiment_contract` it is a SEALED (v2,
    confirmatory) schedule: the contract is INSIDE the hashed content, so
    `schedule_id` names the treatment, the world, the code and the analysis
    plan — not merely the order in which three mutable labels are invoked.
    Without it the schedule is v1: a pilot/diagnostic design, executable but
    never confirmatory."""
    cells = build_cells(roster, selectors, arms, replicates, label)
    content = {
        "schedule_version": SEALED_SCHEDULE_VERSION if experiment_contract else SCHEDULE_VERSION,
        "confirmatory": bool(experiment_contract),
        "label": label,
        "date_stamp": date_stamp,
        "digest_excludes": list(DIGEST_EXCLUDES),
        "roster": {
            "providers_models": roster,
            "selectors": list(selectors),
            "arms": list(arms),
            "replicates": replicates,
            "permutation_cycle": permutation_cycle(arms),
            "sampling": sampling,
            "max_total_completion_tokens": ceiling,
            "timeout": timeout,
            "framework_retries": retries,
            "sdk_retries": 0,
            "min_interval": min_interval,
        },
        "balance": balance_claim(cells, selectors, arms),
        "n_cells": len(cells),
        "cells": cells,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    if experiment_contract:
        content["experiment_contract"] = experiment_contract
    content["schedule_id"] = schedule_digest(content)
    return content


# ---------------------------------------------------------------------------
# EXACT CELL IDENTITY. Defined here, once, because BOTH the
# executor and the table must mean the same thing by "the row for this cell":
# `run_arms` decides whether to run it, `arm_table` decides whether to count
# it, and a disagreement between those two is exactly how a panel loses a cell
# without either tool saying so.
# ---------------------------------------------------------------------------

CELL_IDENTITY_FIELDS = ("schedule_id", "tag", "provider", "model", "selector", "replicate", "arm",
                        "planned_ordinal", "block_id", "permutation_index", "arm_position")


def contract_expectations(schedule: dict, cell: dict) -> dict:
    """What a row for this cell must ALSO carry, beyond its own identity: the
    world it served, the two contracts it ran under, the treatment behind its
    arm label, the libraries the replay projection was bound to, and the
    INSTRUMENT that produced it.

    All from the SEALED contract, never from the row. The three instrument
    fields make the digests part of EXACT row admission rather than of a
    reporting paragraph: the concrete bad execution is a session that
    passes startup, changes an executable file before a later cell, and lets
    that fresh subprocess write a row bearing the changed digest. The old
    `render_instrument_identity` printed "DIFFERENT from the sealed instrument
    tree" and computed the confirmatory estimates anyway.
    """
    contract = schedule.get("experiment_contract") or {}
    arm_spec = (contract.get("arm_contract") or {}).get(cell["arm"]) or {}
    return {
        "task_id": (contract.get("expected_public_task_id_by_selector") or {}).get(cell["selector"]),
        "episode_contract_digest": contract.get("expected_episode_contract_digest"),
        "replay_contract_digest": (contract.get("expected_replay_contract_digest_by_arm") or {}).get(cell["arm"]),
        "per_turn_cap": arm_spec.get("per_turn_max_tokens"),
        "reasoning_replay": arm_spec.get("reasoning_replay"),
        "library_versions": (contract.get("package_lock") or {}).get("replay_libraries"),
        # THE INSTRUMENT. A row whose own digests differ
        # from the seal — or that carries none at all, which is what a row
        # written by an older instrument looks like — is not this cell's row.
        "instrument_identity_version": contract.get("instrument_identity_version"),
        "execution_tree_digest": contract.get("execution_tree_digest"),
        "runtime_environment_digest": contract.get("runtime_environment_digest"),
    }


def row_mismatches(row: dict, schedule: dict, cell: dict) -> list[str]:
    """Every way this row fails to BE the sealed cell, named. Empty means the
    row is exactly this cell's row."""
    problems = []
    for field in CELL_IDENTITY_FIELDS:
        want = schedule["schedule_id"] if field == "schedule_id" else cell.get(field)
        got = row.get(field)
        if got != want:
            problems.append(f"{field}={got!r} (schedule says {want!r})")
    for field, want in contract_expectations(schedule, cell).items():
        if want is None:
            continue
        if row.get(field) != want:
            problems.append(f"{field}={row.get(field)!r} (contract says {want!r})")
    return problems


def cell_key(cell: dict) -> tuple:
    """The canonical identity of one scheduled cell — used as a dict key by
    the executor and the table alike."""
    return (cell.get("provider"), cell.get("model"), cell.get("selector"),
            cell.get("replicate"), cell.get("arm"))


def is_confirmatory(schedule: dict) -> bool:
    """A schedule is CONFIRMATORY exactly when it carries an experiment
    contract. Every confirmatory refusal in `run_arms` and `arm_table`
    is gated on this one predicate, so a pilot schedule keeps the
    permissive paths and a sealed one cannot reach them."""
    return bool(isinstance(schedule, dict) and schedule.get("experiment_contract"))


def load_schedule(path: Path) -> dict:
    """Reads a schedule and REFUSES one whose content no longer hashes to its
    own id — an immutable schedule that can be edited after the fact is not
    an immutable schedule."""
    schedule = json.loads(Path(path).read_text(encoding="utf-8"))
    recomputed = schedule_digest(schedule)
    if recomputed != schedule.get("schedule_id"):
        raise SystemExit(f"{path}: schedule_id {schedule.get('schedule_id')} does not match the content "
                         f"(recomputed {recomputed}) — the file was edited after it was written; "
                         f"regenerate it with tests/schedule_arms.py rather than patching it")
    return schedule


# ---------------------------------------------------------------------------
# CONFIGURATION-LEVEL EXCLUSION RECORDS
#
# "If a resumed configuration has earlier rows and a later probe becomes
# conclusively incompatible, the table must consume an immutable
# configuration-level exclusion record and exclude the whole configuration. It
# cannot infer this only from row-level failures, because the newly blocked
# cells have no rows."
#
# So the executor WRITES the exclusion, once, when a probe conclusively fails,
# and `arm_table` READS it. The record is content-bound (`record_digest` over
# its own remaining fields) and append-only: a configuration that already has a
# record is never given a second one, and an edited record is refused rather
# than believed.
# ---------------------------------------------------------------------------

EXCLUSION_DIGEST_EXCLUDES = ("record_digest",)


def exclusion_digest(record: dict) -> str:
    payload = {k: v for k, v in record.items() if k not in EXCLUSION_DIGEST_EXCLUDES}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def read_configuration_exclusions(schedule_path: Path, schedule: dict | None = None) -> dict:
    """`{"records": [...], "problems": [...]}` from the exclusion file beside
    the schedule. A record whose digest does not recompute, or that names a
    different `schedule_id`, is a PROBLEM and is not returned as a record: an
    exclusion the table cannot authenticate is not an exclusion."""
    path = exclusion_record_path_for(schedule_path)
    records: list[dict] = []
    problems: list[str] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"records": records, "problems": problems, "path": path}
    except OSError as exc:                                                 # noqa: BLE001
        return {"records": records, "problems": [f"{path.name}: unreadable ({type(exc).__name__})"],
                "path": path}
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            problems.append(f"{path.name}:{number}: not JSON — an exclusion record that cannot be read "
                            f"is not an exclusion, and the line is preserved for audit")
            continue
        if not isinstance(record, dict):
            problems.append(f"{path.name}:{number}: not an object")
            continue
        if record.get("record_digest") != exclusion_digest(record):
            problems.append(f"{path.name}:{number}: record_digest does not match the record content "
                            f"({record.get('provider')}/{record.get('model')}) — refused, not believed")
            continue
        if schedule is not None and record.get("schedule_id") != schedule.get("schedule_id"):
            problems.append(f"{path.name}:{number}: names schedule_id {record.get('schedule_id')!r}, "
                            f"not this schedule's")
            continue
        records.append(record)
    return {"records": records, "problems": problems, "path": path}


def write_configuration_exclusion(schedule_path: Path, schedule: dict, provider: str, model: str, *,
                                  reason: str, evidence: dict | None = None,
                                  session_id: str | None = None, root: Path | None = None) -> dict:
    """Append ONE immutable exclusion record for `(provider, model)`.

    Raises `OSError` when it cannot be written — the caller must treat that as
    fatal in confirmatory mode, exactly like a failed journal append: an
    exclusion that was decided but not recorded is a configuration the table
    will silently treat as merely unrun."""
    path = exclusion_record_path_for(schedule_path)
    existing = read_configuration_exclusions(schedule_path, schedule)
    for record in existing["records"]:
        if (record.get("provider"), record.get("model")) == (provider, model):
            return record                    # already excluded; never rewritten
    identity = instrument_identity(root)
    record = {"record": "configuration_exclusion", "schedule_id": schedule.get("schedule_id"),
              "label": schedule.get("label"), "provider": provider, "model": model,
              "reason": reason, "conclusive": True, "evidence": evidence or {},
              "session_id": session_id, "at": datetime.now(timezone.utc).isoformat(),
              "instrument_commit": (schedule.get("experiment_contract") or {}).get("instrument_commit"),
              "runtime_head": identity["runtime_head"],
              "execution_tree_digest": identity["execution_tree_digest"],
              "runtime_environment_digest": identity["runtime_environment_digest"]}
    record["record_digest"] = exclusion_digest(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:                      # best-effort durability; the append already succeeded
            pass
    return record


def format_census(cells: list[dict], key_fields: tuple, title: str) -> list[str]:
    lines = [f"### {title}", "",
             "| " + " | ".join(key_fields) + " | blocks | sequences | position balance | adjacency balance |",
             "|" + "---|" * (len(key_fields) + 4)]
    for key, stats in census(cells, key_fields).items():
        sequences = ", ".join(f"{'>'.join(seq)}×{n}" for seq, n in sorted(stats["sequences"].items()))
        lines.append("| " + " | ".join(str(k) for k in key) + f" | {stats['n_blocks']} | {sequences} | "
                     f"{'exact' if stats['position_balance_exact'] else 'approximate'} | "
                     f"{'exact' if stats['adjacency_balance_exact'] else 'approximate'} |")
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="schedule label; the file is reviews/schedule_<label>.json "
                                                       "and every output tag begins with it")
    parser.add_argument("--provider", default=None, help="one provider for every model in --models")
    parser.add_argument("--models", nargs="+", default=None, help="model ids for --provider")
    parser.add_argument("--roster", nargs="+", default=None,
                        help="explicit provider=model pairs, for a schedule spanning providers")
    parser.add_argument("--selectors", nargs="+", required=True)
    parser.add_argument("--arms", nargs="+", default=list(DEFAULT_ARMS), choices=("A", "B1", "B2", "B3"))
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--date-stamp", default=None, help="the YYYY-MM-DD part of every output filename; "
                                                           "defaults to today. Fixed here so that resuming the "
                                                           "schedule on a later day does not re-run every cell")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max-total-completion-tokens", type=int, default=40_000)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--retries", type=int, default=0, help="FRAMEWORK rollout retries; SDK retries are "
                                                               "always 0 (measure_budget.py sets max_retries=0)")
    parser.add_argument("--min-interval", type=float, default=6.0)
    parser.add_argument("--reviews-dir", default=None)
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing schedule file. REFUSED for a SEALED (confirmatory) "
                             "schedule: an observed experiment's contract may not be replaced on an "
                             "operator's promise; cut a new label instead")
    parser.add_argument("--seal", action="store_true",
                        help="SEAL this schedule as CONFIRMATORY (v2): compute the experiment contract "
                             "(instrument commit, analysis-plan sha256, arm contract, episode/replay "
                             "digests, package lock, failure-map digest, manifest rotation/content digest, "
                             "selector -> served public task id, provider quota table) and hash it INTO "
                             "schedule_id. Requires a CLEAN git tree: an instrument commit that does not "
                             "describe the files that will run is not provenance")
    parser.add_argument("--analysis-plan", default=None,
                        help="the pre-registration this schedule adopts (default reviews/confirmatory_design.md)")
    parser.add_argument("--allow-dirty-tree", action="store_true",
                        help="seal against a DIRTY tree. For a witness/test schedule only: the sealed "
                             "contract then names a commit that does not describe the executing files, and "
                             "tests/startup_witness.py will refuse to run it")
    args = parser.parse_args()

    roster: list[dict] = []
    if args.roster:
        for entry in args.roster:
            if "=" not in entry:
                raise SystemExit(f"--roster entries are provider=model, got {entry!r}")
            provider, model = entry.split("=", 1)
            roster.append({"provider": provider, "model": model})
    elif args.provider and args.models:
        roster = [{"provider": args.provider, "model": model} for model in args.models]
    else:
        raise SystemExit("give either --roster provider=model ... or --provider P --models M ...")

    date_stamp = args.date_stamp or datetime.now().strftime("%Y-%m-%d")
    sampling = {"temperature": args.temperature, "top_p": args.top_p, "seed": args.seed}

    contract = None
    if args.seal:
        # The gate is the EXECUTION PATHS, not the whole tree. A
        # dirty `reviews/` or private-notes file is evidence being written and
        # must not block a seal — that requirement is precisely what made the
        # previous identity rule impossible to satisfy, since the schedule
        # itself is evidence stored in the repository. A dirty `tests/` or
        # `beancount_ledger/` file still refuses: the sealed digest would then
        # describe bytes that are not the bytes about to run.
        clean, detail = git_execution_tree_status()
        if not clean and not args.allow_dirty_tree:
            raise SystemExit("REFUSED to seal: the EXECUTION paths are not clean, so `execution_tree_digest` "
                             "would describe bytes that are not the bytes that will execute.\n" + detail +
                             "\nExecution paths: " + ", ".join(EXECUTION_PATHS) +
                             "\nCommit (or stash) first, then seal. --allow-dirty-tree exists only for a "
                             "witness schedule that will never run cells.")
        whole_clean, whole_detail = git_tree_status()
        if not whole_clean:
            print("note: the working tree is dirty OUTSIDE the sealed execution paths (evidence files: "
                  "reviews/, notes/, root *.md). That is permitted by the git-path contract and is "
                  "recorded here, not hidden:\n  " + whole_detail.replace("\n", "\n  "))
        plan = Path(args.analysis_plan) if args.analysis_plan else ANALYSIS_PLAN
        if not plan.is_file():
            raise SystemExit(f"REFUSED to seal: the analysis plan {plan} does not exist. A sealed schedule "
                             f"binds the pre-registration it adopts, by content digest.")
        contract = build_experiment_contract(args.arms, args.selectors,
                                             args.max_total_completion_tokens, plan)
        # An execution tree with no files is not an instrument (adversarial
        # review, INFO): a digest over nothing would witness itself green
        # forever, so the seal refuses rather than producing one.
        if not contract["execution_tree_digest"] or not contract["execution_tree_file_count"]:
            raise SystemExit(f"REFUSED to seal: the execution root {EXECUTION_ROOT} contains no files "
                             f"after the exclusions {list(EXECUTION_EXCLUDES)}. An empty execution set "
                             f"binds nothing and would witness itself green.")
        # The same rule for the interpreter: an environment
        # whose site-packages could not be read binds nothing either.
        if not contract["runtime_environment_digest"] or not contract["runtime_environment_file_count"]:
            raise SystemExit(f"REFUSED to seal: the running interpreter's importable roots "
                             f"({environment_roots()}) yielded no file. The runtime-environment digest "
                             f"is what makes 'the same package versions' into 'the same executable "
                             f"instrument'; a digest over nothing would witness itself green.")
        # And the IMPORT ENVIRONMENT must be clean AT SEALING TIME (C1(b)). An
        # uncovered `sys.path` entry can be sealed — the field records it — but
        # sealing one would bake a module-shadow into the contract and make
        # every later witness green over it. The healthy list is empty.
        if contract["runtime_environment_uncovered_sys_path"]:
            raise SystemExit(
                f"REFUSED to seal: {len(contract['runtime_environment_uncovered_sys_path'])} sys.path "
                f"entr(ies) are covered by NEITHER the sealed environment roots NOR the execution "
                f"tree: {contract['runtime_environment_uncovered_sys_path']}. A directory there "
                f"shadows any sealed module. Unset PYTHONPATH/PYTHONHOME (and any .pth that adds an "
                f"outside directory) and seal again.")
        missing = [s for s, t in contract["expected_public_task_id_by_selector"].items() if not t]
        if missing:
            raise SystemExit(f"REFUSED to seal: the serving door returned no public task id for {missing}. "
                             f"A schedule that cannot name the world it will serve binds nothing.")

    schedule = build_schedule(args.label, roster, args.selectors, args.arms, args.replicates,
                              date_stamp, sampling, args.max_total_completion_tokens,
                              args.timeout, args.retries, args.min_interval, contract)

    reviews_dir = Path(args.reviews_dir) if args.reviews_dir else ROOT / "reviews"
    reviews_dir.mkdir(exist_ok=True)
    path = reviews_dir / f"schedule_{args.label}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        # `--force` is an operator promise. A SEALED schedule's
        # contract may not be replaced by one, whatever the promise says —
        # the replacement would silently redefine the treatment of rows
        # already observed under the old id.
        if is_confirmatory(existing):
            raise SystemExit(f"REFUSED: {path.name} is a SEALED confirmatory schedule (schedule_id "
                             f"{existing.get('schedule_id')}). It is immutable — --force cannot replace it. "
                             f"A changed design is a NEW label and a NEW schedule_id, so that rows already "
                             f"observed keep naming the contract they actually ran under.")
        if not args.force:
            raise SystemExit(f"{path.name} already exists (schedule_id {existing.get('schedule_id')}). A "
                             f"schedule is immutable once cells have run — pass --force only if nothing has "
                             f"been executed against it")
    path.write_text(json.dumps(schedule, indent=1, default=str), encoding="utf-8")

    print(f"schedule_id {schedule['schedule_id']}")
    if contract:
        print(f"SEALED confirmatory schedule v{SEALED_SCHEDULE_VERSION}")
        print(f"  instrument_commit           {contract['instrument_commit']}")
        print(f"  execution_paths             {', '.join(contract['execution_paths'])}")
        print(f"  execution_excludes          {', '.join(contract['execution_excludes'])}")
        print(f"  execution_tree_digest       {contract['execution_tree_digest']} "
              f"({contract['execution_tree_file_count']} files ON DISK)")
        print(f"  runtime_environment_digest  {contract['runtime_environment_digest']} "
              f"({contract['runtime_environment_file_count']} files, "
              f"{contract['runtime_environment_bytes']:,} bytes, "
              f"{contract['runtime_environment_distribution_count']} distributions, "
              f"{contract['runtime_environment_stdlib_file_count']} stdlib, "
              f"{contract['runtime_environment_extra_file_count']} referenced by no RECORD)")
        uncovered = contract.get("runtime_environment_uncovered_sys_path") or []
        print(f"  uncovered_sys_path          "
              + ("none — every sys.path entry is inside the sealed roots or the execution tree"
                 if not uncovered else f"{len(uncovered)}: {', '.join(uncovered)}"))
        print(f"  python_version              {contract['python_version'].splitlines()[0]}")
        print(f"  analysis_plan_sha256        {contract['analysis_plan_sha256']} ({contract['analysis_plan']})")
        print(f"  arm_contract                {contract['arm_contract']}")
        print(f"  episode_contract_digest     {contract['expected_episode_contract_digest']}")
        for arm, digest in sorted(contract["expected_replay_contract_digest_by_arm"].items()):
            print(f"  replay digest {arm:<3}           {digest}")
        print(f"  package_lock                {contract['package_lock']}")
        print(f"  failure_map_digest          {contract['failure_map_digest']}")
        print(f"  manifest rotation           {contract['manifest']['rotation_id']}")
        print(f"  manifest content digest     {contract['manifest']['manifest_content_digest']}")
        for selector, task_id in sorted(contract["expected_public_task_id_by_selector"].items()):
            print(f"  task id {selector:<16s}    {task_id}")
        print(f"  provider quotas             {contract['provider_quotas']['source']}")
    print(f"label {schedule['label']}  date_stamp {schedule['date_stamp']}  cells {schedule['n_cells']}")
    print("roster: " + ", ".join("{}/{}".format(e["provider"], e["model"]) for e in roster))
    print(f"selectors: {args.selectors}  arms: {args.arms}  replicates: {args.replicates}")
    print(f"\nBALANCE: {schedule['balance']['statement']}\n")
    for line in (format_census(schedule["cells"], ("provider", "model"), "Per (provider, model)")
                 + format_census(schedule["cells"], ("selector",), "Per selector")):
        print(line)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
