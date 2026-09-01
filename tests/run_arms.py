"""Executes an IMMUTABLE arm schedule (Codex T48a §2/Q1, T49 §3–§7).

    python tests/schedule_arms.py --seal --label confirm1v2 ...   # once, before anything runs
    python tests/run_arms.py --schedule reviews/schedule_confirm1v2.json --provider mistral

This script no longer computes a design. `tests/schedule_arms.py` writes one
file, before any rollout, that names every cell and its planned ordinal;
`run_arms.py` executes the cells whose output file is MISSING, in the
schedule's own order, and records on every row both what was PLANNED
(`schedule_id`, `planned_ordinal`) and what actually happened
(`actual_ordinal`, `session_id`, `started_at`, `finished_at`).

CONFIRMATORY MODE is the whole of Codex T49's enforcement, and it is entered
by exactly one predicate: the schedule carries an experiment contract
(`schedule_arms.is_confirmatory`). A v1 (pilot/diagnostic) schedule keeps
every permissive path this file has always had; a SEALED one cannot reach any
of them.

  §3 EXACT CELL IDENTITY. "Done" means EXACTLY ONE row in the cell's own
     file, all of `schedule_id, tag, provider, model, selector, replicate,
     arm, planned_ordinal, block_id, permutation_index, arm_position` equal,
     and its served task id, episode digest, replay digest, per-turn cap and
     library versions equal to the sealed expectations. Anything else — a
     missing `schedule_id`, a partial match, a duplicate, a foreign row — is
     `execution_integrity`: the cell is QUARANTINED by name, never silently
     skipped and never re-run over. The tag-OR-identity and
     `schedule_id is None` compatibility paths exist for pilot files only.

  §4 IMMUTABILITY. `--force` is refused outright for a sealed schedule. A
     completed cell is never overwritten. There is no operator toggle for
     "the run is finished": closure is DERIVED from the exact cell map.

  §5 ONE EXECUTOR. A single `<schedule>.lock`, taken `O_EXCL` at start,
     carrying session id, NONCE, pid and start time. NO automatic stale
     takeover: a stale lock is reported with instructions, and
     `--take-over-lock` is an explicit operator act that is written into the
     log. Since Codex T51 §3 that act is itself an ATOMIC COMPETITION — a
     separate `O_EXCL` takeover guard, revalidation of the stale lock's exact
     bytes under it, an archive of those bytes, then acquisition through the
     same `O_EXCL` path a clean startup uses and a proof that the nonce on disk
     is ours. The per-cell claim stays as a second belt, and releasing it now
     VERIFIES OWNERSHIP — the previous release unlinked whatever claim it
     found, so a late old owner could delete a new owner's claim. `--limit`
     counts WHOLE BLOCKS: a three-arm block split across two sessions is a
     different experiment from the one the Williams order registered, and the
     executor records when that happens.

  T51 §2 PER-CELL INSTRUMENT VERIFICATION. Every cell subprocess is handed the
     sealed execution-tree and runtime-environment digests and re-verifies
     them: both before request 1 of the cell, the tree before EVERY provider
     request, and both again after the last write. A mismatch makes no
     provider call, writes no row, and exits `measure_budget.
     INSTRUMENT_DRIFT_EXIT`; this executor journals `instrument_drift`
     fail-closed and STOPS the session, because a drifted instrument
     invalidates everything after it.

  T51 §4 FAIL-CLOSED JOURNAL. The whole journal is parsed under the lock before
     every append and before the probe. A malformed or non-object line that no
     recovery record acknowledges aborts the action; `--recover-execution-
     journal` is the explicit segment recovery, refused before the first real
     row exists (abort and reseal instead).

  EXIT CODES: 0 done · 2 an operator flag refused for a sealed schedule ·
     3 the startup witness refused · 4 the executor lock · 5 the execution
     journal could not record a confirmatory action · 6 instrument drift.

  §7 CAPABILITY. Before the first cell, one two-turn tool-call probe per
     (provider, model, replay policy) establishes that the configuration can
     carry every arm's replayed payload. A configuration whose probe fails is
     refused as a whole, before any of its cells run, and a NEW
     incompatibility appearing mid-run stops that configuration's remaining
     cells instead of being applied to whichever blocks happened to fail.

  §14.12 STARTUP WITNESS. Before request 1 of EVERY session (and under
     `--dry-run`), `tests/startup_witness.py` re-checks every field of the
     sealed contract against this checkout, these libraries, this package and
     the active release manifest. Any mismatch refuses the run by name.

`--provider` remains as a FILTER: a schedule may span providers, and running
one provider per process (each with its own rate limits and its own key) is
still the practical way to execute one. The cells not selected simply stay
unrun, and `tests/arm_table.py` reports them as unrun rather than as
failures.

A failed cell's subprocess stderr tail is REDACTED
(`measure_budget.redact_secrets`) before it is written to the repo-tracked
log file.

    A'   8K per turn, reasoning replayed,     whole-ledger read
    B1'  16K per turn, reasoning replayed,    whole-ledger read
    B2'  8K per turn, reasoning NOT replayed, whole-ledger read
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
sys.path.insert(0, str(ROOT / "tests"))

# ---------------------------------------------------------------------------
# THE BYTECODE CACHE (C2, the adversarial review of the T51 closures)
#
# The runtime-environment manifest excludes `__pycache__/` and `*.pyc` by name,
# and it has to: bytecode is written by the very act of importing, so a strict
# set would not be stationary across the run it authenticates, and this venv is
# shared by every process on the machine.
#
# That exclusion was a HOLE, not merely a convenience. An EXISTING `.pyc`
# edited in place keeps the source mtime and size recorded in its own header,
# so the default timestamp validation accepts it forever: the tampered body
# executes and the sealed `.py` is never read. Nothing in the digest moves,
# because nothing the digest covers changed.
#
# The closure is to make sure no pre-existing cache is ever on the path.
# `PYTHONPYCACHEPREFIX` (and its in-process twin `sys.pycache_prefix`) moves
# the whole cache tree to a FRESH directory: at the first import of each
# module the interpreter finds nothing there and compiles from the `.py` bytes
# the manifest hashed. This process sets it BEFORE it imports anything of its
# own, and hands the same prefix to every cell subprocess, which therefore has
# it from process start.
#
# The prefix is short on purpose: the interpreter mirrors each module's FULL
# absolute source path underneath it, and a long prefix pushes deep
# site-packages paths past the Windows path limit, at which point bytecode
# writing fails silently and every import recompiles.
# ---------------------------------------------------------------------------
import tempfile  # noqa: E402

#: Set once per process by `redirect_bytecode_cache()`.
BYTECODE_CACHE_PREFIX: Path | None = None


def fresh_bytecode_cache_prefix() -> Path:
    """A per-process directory under the OS temp that did NOT exist before,
    memoised. "Fresh" is the whole property: a reused directory could already
    hold the tampered bytecode this exists to route around."""
    global BYTECODE_CACHE_PREFIX                                          # noqa: PLW0603
    if BYTECODE_CACHE_PREFIX is not None:
        return BYTECODE_CACHE_PREFIX
    base = Path(tempfile.gettempdir()) / "pivpyc"
    base.mkdir(parents=True, exist_ok=True)
    while True:
        candidate = base / uuid.uuid4().hex[:10]
        try:
            candidate.mkdir()                      # fails if it already exists
        except FileExistsError:                                            # noqa: PERF203
            continue
        BYTECODE_CACHE_PREFIX = candidate
        return candidate


def redirect_bytecode_cache() -> Path:
    """Point THIS process's bytecode cache at the fresh directory and return
    it. Called at import, before this module imports the instrument's own
    modules or (through the witness) the package, so every one of them is
    compiled from the sealed source rather than read from a cache file that
    nothing in the manifest covers."""
    prefix = fresh_bytecode_cache_prefix()
    sys.pycache_prefix = str(prefix)
    return prefix


redirect_bytecode_cache()

import measure_budget as mb  # noqa: E402 -- reuses redact_secrets
import schedule_arms as SA  # noqa: E402 -- the schedule is the design
import startup_witness as SW  # noqa: E402 -- the pre-request refusal


DEFAULT_CLAIM_TTL_SECONDS = 2 * 60 * 60

# The exact-cell predicate lives in `schedule_arms` so that the executor and
# `tests/arm_table.py` cannot drift apart about what "the row for this cell"
# means; re-exported here under the names this module has always used.
CELL_IDENTITY_FIELDS = SA.CELL_IDENTITY_FIELDS
contract_expectations = SA.contract_expectations
row_mismatches = SA.row_mismatches


def cell_status(out_path: Path, schedule: dict, cell: dict) -> tuple[str, str]:
    """`(status, why)` with `status` in `{"done", "unrun", "integrity"}`.

    A file that does not exist, does not parse, or carries no row for this
    cell is UNRUN and will be re-run — a process killed mid-write used to
    leave truncated JSON that this script skipped forever while
    `arm_table.load_rows` dropped it with a warning, so the cell was neither
    re-run nor counted.

    In CONFIRMATORY mode a file that exists and parses but whose content is
    not EXACTLY one matching row is neither done nor unrun: it is an
    `execution_integrity` failure. Re-running it would overwrite an observed
    result; skipping it would let a partial identity, a duplicate or a
    foreign row stand in for the registered cell. It is quarantined by name
    and reported.
    """
    confirmatory = SA.is_confirmatory(schedule)
    if not out_path.exists():
        return "unrun", "no output file"
    try:
        rows = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:                          # noqa: BLE001
        if confirmatory:
            return "integrity", (f"the output file exists but does not parse ({type(exc).__name__}): a "
                                 f"confirmatory cell is never silently re-run over an unreadable observation")
        return "unrun", f"unreadable ({type(exc).__name__}) — re-running"
    if not isinstance(rows, list) or not rows:
        if confirmatory:
            return "integrity", "the output file carries no rows at all"
        return "unrun", "no rows in the file — re-running"

    if not confirmatory:
        # PILOT compatibility, kept deliberately and ONLY here: a pilot row
        # may lack a schedule id, and a tag match alone is enough.
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("schedule_id") not in (None, schedule["schedule_id"]):
                continue
            matches_tag = row.get("tag") == cell["tag"]
            matches_identity = (row.get("model") == cell["model"] and row.get("selector") == cell["selector"]
                                and row.get("arm") == cell["arm"] and row.get("replicate") == cell["replicate"])
            if matches_tag or matches_identity:
                return "done", "already run"
        return "unrun", "the file carries no row for this cell — re-running"

    exact, near = [], []
    for row in rows:
        if not isinstance(row, dict):
            near.append("a non-dict entry in the row list")
            continue
        problems = row_mismatches(row, schedule, cell)
        if not problems:
            exact.append(row)
        else:
            near.append("; ".join(problems[:6]))
    if len(exact) == 1 and not near:
        return "done", "already run (exactly one matching row)"
    if len(exact) > 1:
        return "integrity", f"{len(exact)} rows claim to be this cell; exactly one is a cell"
    if exact and near:
        return "integrity", (f"one matching row AND {len(near)} row(s) that do not match this cell: "
                             + " | ".join(near[:3]))
    return "integrity", ("the output file exists but no row matches this cell exactly: "
                         + " | ".join(near[:3]))


def cell_is_done(out_path: Path, schedule: dict, cell: dict) -> tuple[bool, str]:
    """`(done, why)` — the pilot-era predicate, now a thin wrapper over
    `cell_status`. An `execution_integrity` cell is NOT done (it must never be
    counted as an observation) and is NOT re-run either; the executor handles
    that third state explicitly."""
    status, why = cell_status(out_path, schedule, cell)
    return status == "done", why


# ---------------------------------------------------------------------------
# The schedule-level executor lock (Codex T49 §5)
# ---------------------------------------------------------------------------

def lock_path_for(schedule_path: Path) -> Path:
    return Path(str(schedule_path) + ".lock")


def takeover_guard_path_for(schedule_path: Path) -> Path:
    """The separate `O_EXCL` guard that makes a takeover an ATOMIC COMPETITION
    (Codex T51 §3). It is not the schedule lock: it is the right to CONTEND for
    the schedule lock, held only for the few milliseconds of revalidate →
    archive → unlink → re-acquire."""
    return Path(str(lock_path_for(schedule_path)) + ".takeover")


def takeover_archive_path_for(schedule_path: Path, session_id: str) -> Path:
    """Where the displaced lock's exact BYTES are preserved. Never overwritten:
    the session id that performed the takeover is in the name."""
    return Path(str(lock_path_for(schedule_path)) + f".displaced.{session_id}.json")


#: A lock younger than this is a LIVE executor, not a corpse, and
#: `--take-over-lock` refuses it. The flag's contract is "I have verified that
#: process is dead"; a lock created seconds ago cannot have been verified dead,
#: and refusing it is what stops the second contender in the two-contender race
#: from displacing the first contender's brand-new lock.
TAKEOVER_MIN_LOCK_AGE_SECONDS = 300.0

#: How long the winner of the takeover guard retries the atomic rename that
#: archives and removes the stale lock. A rival contender reading the same lock
#: keeps it open for microseconds; Windows answers WinError 32 meanwhile.
LOCK_REPLACE_TIMEOUT_SECONDS = 5.0


def acquire_schedule_lock(schedule_path: Path, session_id: str, take_over: bool = False,
                          min_age_seconds: float = TAKEOVER_MIN_LOCK_AGE_SECONDS
                          ) -> tuple[bool, str, dict | None, dict | None]:
    """`(acquired, note, displaced, ours)` — ONE executor per schedule,
    `O_EXCL`.

    There is NO automatic takeover. Two contenders that both judged a claim
    stale could each `os.replace` their own claim onto it and both believe
    they won; more importantly, a second executor invalidates the planned
    temporal order even when it never duplicates a cell, and Williams order
    is an execution property, not a JSON property. A stale lock is reported
    with the instruction to verify the holder is dead and pass
    `--take-over-lock`, which is written into the log as an operator act.

    THE TAKEOVER IS ITSELF ATOMIC (Codex T51 §3). The previous implementation
    was `path.write_text(...)` — no exclusion at all, so two recovery operators
    could both observe the same stale lock, both overwrite it, and both return
    as owners, then execute different cells concurrently. The replacement is a
    four-step competition:

      1. acquire a SEPARATE takeover guard with `O_CREAT | O_EXCL`. Exactly one
         contender gets it; the others are told a takeover is in progress.
      2. while holding it, REVALIDATE: the lock must still be byte-for-byte the
         one this process judged stale, and at least `min_age_seconds` old. A
         contender that arrives after the winner has already replaced the lock
         sees different bytes and refuses — it is not taking over the corpse it
         was authorised to take over.
      3. ARCHIVE the stale lock's exact bytes to their own file, then unlink it.
      4. acquire the ordinary schedule lock through the SAME `O_EXCL` path a
         clean startup uses, and re-read it to prove the nonce is ours.

    The guard is released in a `finally` whatever happens, so a crashed
    takeover does not wedge the next one out of existence — it leaves the
    archive and the (absent or present) lock exactly as it found them.
    """
    path = lock_path_for(schedule_path)
    nonce = uuid.uuid4().hex
    payload = {"session_id": session_id, "nonce": nonce, "pid": os.getpid(),
               "started_at": datetime.now(timezone.utc).isoformat(),
               "host": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "?"}
    body = json.dumps(payload, sort_keys=True)

    def _create(where: Path) -> bool:
        try:
            handle = os.open(where, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            fh.write(body)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        return True

    if _create(path):
        return True, f"holding the schedule lock as session {session_id}", None, dict(payload)

    # -- the lock exists ----------------------------------------------------
    held, state = lock_holder(path)
    held = held or {}
    if state == "unknown":
        held = {"session_id": "UNREADABLE (a lock file exists but cannot be parsed — treat it as "
                              "held by an unknown session)"}
    try:
        observed = path.read_bytes()
    except OSError:
        observed = None
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        age = 0.0
    if not take_over:
        return False, (f"the schedule is locked by session {held.get('session_id', '?')} "
                       f"(pid {held.get('pid', '?')} on {held.get('host', '?')}, started "
                       f"{held.get('started_at', '?')}, {age / 60:.0f} min ago).\n"
                       f"  ONE executor runs a schedule. If that process is genuinely dead, verify it, "
                       f"then re-run with --take-over-lock (the takeover is recorded in the arms log).\n"
                       f"  Lock file: {path}"), held, None
    if age < min_age_seconds:
        return False, (f"REFUSED to take over: the lock held by session {held.get('session_id', '?')} "
                       f"is {age:.0f}s old, younger than the {min_age_seconds:.0f}s a lock must reach "
                       f"before it may be called a corpse. --take-over-lock means 'I have verified that "
                       f"process is dead'; a lock created moments ago belongs to a live executor (or to "
                       f"a contender that has just won this same takeover)."), held, None

    guard = takeover_guard_path_for(schedule_path)
    try:
        guard_handle = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False, (f"REFUSED to take over: another process holds the takeover guard "
                       f"{guard.name} and is contending for this schedule right now. Exactly one "
                       f"takeover may proceed; verify which process won before retrying."), held, None
    except OSError as exc:                                                 # noqa: BLE001
        return False, f"could not create the takeover guard {guard}: {type(exc).__name__}: {exc}", held, None
    archive = None
    try:
        os.write(guard_handle, body.encode("utf-8"))
        os.close(guard_handle)
        guard_handle = None
        # 2. REVALIDATE under the guard: is this still the lock we judged stale?
        try:
            current = path.read_bytes()
        except FileNotFoundError:
            current = None
        except OSError as exc:                                             # noqa: BLE001
            return False, f"the stale lock could not be re-read under the guard: {exc}", held, None
        if current is None:
            return False, ("REFUSED to take over: the lock disappeared between this process judging it "
                           "stale and acquiring the takeover guard. Another contender has already "
                           "completed the takeover, or the holder released it; re-run without "
                           "--take-over-lock."), held, None
        if observed is not None and current != observed:
            return False, ("REFUSED to take over: the lock changed between this process judging it stale "
                           "and acquiring the takeover guard — the corpse this takeover was authorised "
                           "for is not the lock now present. Exactly one contender proceeds; this one "
                           "does not."), held, None
        # 3. ARCHIVE the displaced bytes and remove the lock — as ONE atomic
        #    rename, so there is no instant in which the bytes are archived but
        #    the lock still stands (or vice versa). Retried briefly: on Windows
        #    a rival contender that is reading the very same lock to decide
        #    whether IT should contend holds the file open, and the rename
        #    fails with WinError 32 until it lets go. Observed directly in the
        #    four-thread witness.
        archive = takeover_archive_path_for(schedule_path, session_id)
        deadline = time.monotonic() + LOCK_REPLACE_TIMEOUT_SECONDS
        last_error: OSError | None = None
        while True:
            try:
                os.replace(path, archive)
                last_error = None
                break
            except OSError as exc:                                         # noqa: BLE001
                last_error = exc
                if time.monotonic() > deadline:
                    break
                time.sleep(0.02)
        if last_error is not None:
            return False, (f"REFUSED to take over: the stale lock could not be archived and removed "
                           f"within {LOCK_REPLACE_TIMEOUT_SECONDS:.0f}s ({type(last_error).__name__}: "
                           f"{last_error}) — another process is holding it open. Nothing was changed."
                           ), held, None
        # 4. Acquire through the SAME exclusive-create path as clean startup.
        if not _create(path):
            return False, ("REFUSED to take over: the schedule lock was re-created by another process "
                           "in the instant between removing the stale one and claiming it. Nothing was "
                           "run."), held, None
    finally:
        if guard_handle is not None:
            try:
                os.close(guard_handle)
            except OSError:
                pass
        try:
            guard.unlink()
        except OSError:
            pass

    # AFTER ACQUISITION: prove the lock on disk is ours before anything runs.
    ok, detail = prove_lock_ownership(schedule_path, payload)
    if not ok:
        return False, f"REFUSED after taking over: {detail}", held, None
    return True, (f"TOOK OVER the schedule lock from session {held.get('session_id', '?')} "
                  f"(pid {held.get('pid', '?')}, {age / 60:.0f} min old) on an explicit "
                  f"--take-over-lock, atomically: guard {guard.name}, displaced bytes preserved in "
                  f"{archive.name if archive else '?'}, nonce {nonce[:8]} verified on disk"), held, dict(payload)


def prove_lock_ownership(schedule_path: Path, ours: dict | None) -> tuple[bool, str]:
    """Re-read the lock and prove the session id AND the nonce are ours (Codex
    T51 §3: "after acquisition reread the lock and prove that its nonce/owner
    token is still ours before any execution begins").

    The nonce is what makes this a proof rather than a coincidence: two
    sessions could in principle be given the same short session id, but not the
    same 128-bit nonce."""
    if not ours:
        return False, "this process holds no lock record, so it can prove no ownership"
    path = lock_path_for(schedule_path)
    held, state = lock_holder(path)
    if state == "free":
        return False, f"the schedule lock {path.name} is gone after acquisition"
    if state == "unknown":
        return False, f"the schedule lock {path.name} cannot be parsed after acquisition"
    if (held or {}).get("session_id") != ours.get("session_id"):
        return False, (f"the schedule lock names session {(held or {}).get('session_id')!r}, not "
                       f"{ours.get('session_id')!r}")
    if (held or {}).get("nonce") != ours.get("nonce"):
        return False, (f"the schedule lock names nonce {(held or {}).get('nonce')!r}, not this "
                       f"session's — another process replaced it after acquisition")
    return True, f"the lock on disk carries this session's nonce {str(ours.get('nonce'))[:8]}"


def lock_holder(path: Path) -> tuple[dict | None, str]:
    """`(record, state)` for a lock/claim file: `("held")` with a readable
    record, `("unknown")` when the file EXISTS but cannot be read or names no
    session, `("free")` when there is no file.

    An unreadable lock is the case the ownership check used to fall through
    (adversarial-review finding F4): `json.loads` failed, `held` became `{}`,
    `{}.get("session_id")` was `None`, and `None in (None, session_id)` was
    True — so any process could unlink a lock whose holder it could not even
    identify. A file that exists is a claim by SOMEONE; failing to parse it
    is a reason to refuse, not a licence."""
    if not path.exists():
        return None, "free"
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "unknown"
    if not isinstance(held, dict) or not held.get("session_id"):
        return (held if isinstance(held, dict) else None), "unknown"
    return held, "held"


def release_schedule_lock(schedule_path: Path, session_id: str, ours: dict | None = None) -> None:
    """Drop the lock only when it is still OURS. A lock taken over by a later
    session must survive this process's exit — and an UNREADABLE lock is
    owned by someone unknown, so it survives too (only `--take-over-lock`
    clears one, deliberately).

    When the acquisition record is supplied, the NONCE is checked too (Codex
    T51 §3): a later session that happened to draw the same 12-hex session id
    must not have its lock deleted by this process's exit."""
    path = lock_path_for(schedule_path)
    held, state = lock_holder(path)
    if state == "free":
        return
    if state == "unknown" or (held or {}).get("session_id") != session_id:
        return
    if ours is not None and (held or {}).get("nonce") != ours.get("nonce"):
        return
    try:
        path.unlink()
    except OSError:
        pass


def claim_cell(out_path: Path, session_id: str, cell: dict, ttl_seconds: float) -> tuple[bool, str]:
    """The second belt: an exclusive per-cell claim, `O_CREAT | O_EXCL`, so
    even two executors that somehow bypassed the schedule lock cannot both pay
    the provider for one cell.

    NO automatic stale takeover here either (Codex T49 §5): the previous
    version's takeover was a read-then-`os.replace`, which two contenders can
    both complete believing they won. A stale claim is reported; the schedule
    lock is the mechanism that makes one exist in the first place, and
    `--take-over-lock` is the operator act that clears a dead session.
    """
    claim_path = out_path.with_name(out_path.name + ".claim")
    payload = json.dumps({"session_id": session_id, "claimed_at": datetime.now(timezone.utc).isoformat(),
                          "planned_ordinal": cell["planned_ordinal"], "tag": cell["tag"],
                          "pid": os.getpid()})
    try:
        handle = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        held, state = lock_holder(claim_path)
        held = held or {}
        if state == "unknown":
            held = {"session_id": "UNREADABLE (an unknown session holds this cell)"}
        try:
            age = time.time() - claim_path.stat().st_mtime
        except OSError:
            age = 0.0
        stale = age >= ttl_seconds
        return False, (f"claimed by session {held.get('session_id', '?')} {age / 60:.0f} min ago"
                       + (f" — STALE (ttl {ttl_seconds / 60:.0f} min): verify that session is dead and "
                          f"remove {claim_path.name} deliberately" if stale
                          else f" (ttl {ttl_seconds / 60:.0f} min)"))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            fh.write(payload)
    except OSError:
        os.close(handle)
    return True, "claimed"


def release_cell(out_path: Path, session_id: str | None = None) -> None:
    """Drop the claim — but only when we still hold it (Codex T49 §5). The
    previous version unlinked whatever claim it found, so a late old owner
    could delete a NEW owner's claim and let a third process in. Called
    whether the cell succeeded or failed: a claim outlives its process only
    when the process died.

    `session_id` is now REQUIRED in effect (finding F4): a caller that names
    no session cannot prove ownership, and an unreadable claim file is owned
    by someone unknown. Both refuse."""
    claim_path = out_path.with_name(out_path.name + ".claim")
    if session_id is None:
        return                                # no proof of ownership, no release
    held, state = lock_holder(claim_path)
    if state != "held" or (held or {}).get("session_id") != session_id:
        return
    try:
        claim_path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Blocks, execution journal, capability probes
# ---------------------------------------------------------------------------

def block_order(cells: list[dict]) -> list[str]:
    """Block ids in planned order, first appearance first."""
    seen, order = set(), []
    for cell in sorted(cells, key=lambda c: c["planned_ordinal"]):
        if cell["block_id"] not in seen:
            seen.add(cell["block_id"])
            order.append(cell["block_id"])
    return order


def limit_to_whole_blocks(pending: list, limit: int | None) -> tuple[list, int]:
    """Take the first `limit` whole three-arm BLOCKS from `pending` (Codex
    T49 §5). Never an arbitrary cell count: a block whose arms run in two
    different sessions, minutes or hours apart, is not the block the Williams
    order registered, and a `--limit` that cuts one in half produces exactly
    that without saying so.

    Returns `(selected, n_blocks)`."""
    if limit is None:
        return pending, len(block_order([c for c, _ in pending]))
    wanted = block_order([c for c, _ in pending])[:max(0, limit)]
    keep = set(wanted)
    return [item for item in pending if item[0]["block_id"] in keep], len(wanted)


journal_path_for = SA.journal_path_for


class JournalUnavailable(RuntimeError):
    """The execution journal could not be written (Codex T50 §6).

    In CONFIRMATORY mode this is fatal to the action the entry authorizes. The
    previous implementation was `except OSError: pass`, while the schedule
    claimed that a takeover is journalled before the probe, that a crashed
    cell stays visible through `cell_started`, that the actual order can be
    reconstructed and that capability exclusions and split sessions are
    recorded. Every one of those claims is false the moment an append fails
    silently — and it fails silently exactly when something is already wrong.
    """


class JournalCorrupt(JournalUnavailable):
    """The execution journal already contains a line that cannot be read
    (Codex T51 §4).

    T50 closed the WRITE side and left the CONTENT side open: `journal()`
    appended under the lock without validating the existing records, and
    `journal_probe()` only checked that its OWN token came back. A process
    killed mid-append leaves a truncated final line; the next append
    concatenates onto it, turning a malformed TAIL into a malformed MIDDLE and
    taking the following record with it. The audit sequence that explains
    takeover, recovery, inconclusive classification and integrity state is then
    no longer complete, while the confirmatory table still renders.

    So this is raised BEFORE any append and BEFORE the probe, in every mode:
    unlike an unwritable path, damaged evidence is not a condition a pilot gets
    to shrug off either. The bytes are never repaired and never deleted —
    recovery is the explicit operator act below.
    """


journal_scan = SA.journal_scan
journal_health = SA.journal_health
JOURNAL_RECOVERY_RECORD = SA.JOURNAL_RECOVERY_RECORD


def journal(path: Path, event: dict, *, required: bool = False, root: Path | None = None) -> bool:
    """Append one execution-journal entry. Returns whether it landed.

    Locked (the same `O_EXCL` lock the window ledger uses, so two writers
    cannot interleave a line), flushed, and fsync'd where the platform
    supports it. Every entry carries the RUNTIME HEAD and both instrument
    digests (Codex T50 §1, T51 §1), so the journal states which checkout AND
    which installed environment produced it rather than leaving that to the
    schedule's sealed contract.

    THE WHOLE FILE IS PARSED FIRST, under the same lock (Codex T51 §4). A
    malformed or non-object line that no recovery record acknowledges raises
    `JournalCorrupt` and NOTHING is appended: the action the entry authorizes
    must be aborted. The scan is INSIDE the lock for the reason the window
    ledger's is — outside it, it is a TOCTOU window that a concurrent
    truncating writer walks straight through.

    `required=True` (confirmatory mode) also RAISES when the append itself
    fails; `required=False` keeps the pilot's lenient behaviour there, and a
    pilot run says so in its header.
    """
    entry = dict(event)
    identity = mb.runtime_identity()
    entry.setdefault("runtime_head", identity.get("runtime_head"))
    entry.setdefault("execution_tree_digest", identity.get("execution_tree_digest"))
    entry.setdefault("runtime_environment_digest", identity.get("runtime_environment_digest"))
    line = json.dumps(entry, sort_keys=True, default=str) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with mb._LedgerLock(path):                                         # noqa: SLF001 -- the same lock
            scan = journal_scan(path)
            if not scan["healthy"]:
                raise JournalCorrupt(
                    f"the execution journal {path} is CORRUPT and must not be appended to: "
                    f"{scan['detail']}. Appending here would turn a malformed tail into a malformed "
                    f"middle and lose the following record too. The bytes are preserved for audit; "
                    f"recover deliberately with tests/run_arms.py --recover-execution-journal, which "
                    f"is refused before the first real row exists (abort and reseal instead).")
            with path.open("a", encoding="utf-8", newline="") as fh:
                fh.write(line)
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:              # best-effort durability; the append itself succeeded
                    pass
        return True
    except (OSError, mb.WindowLedgerUnavailable) as exc:                   # noqa: BLE001
        if required:
            raise JournalUnavailable(
                f"the execution journal {path} could not record {event.get('event')!r}: "
                f"{type(exc).__name__}: {exc}. A confirmatory action that cannot be recorded does not "
                f"happen: nothing further was run.") from exc
        return False


def journal_recover(path: Path, *, reason: str, session_id: str | None = None,
                    operator: str | None = None) -> dict:
    """The EXPLICIT operator recovery of a damaged execution journal (Codex
    T51 §4, his Q4 answer for the AFTER-rows case). It mirrors the window
    ledger's segment recovery exactly: an immutable boundary record that
    ACKNOWLEDGES the damaged lines by number and never rewrites or removes a
    byte of them.

    The one write it makes to existing content is a terminating newline when
    the file ends mid-record — without it the very next append would
    concatenate onto the partial record and destroy the following one too. The
    boundary record says it did this.

    The record IS the provenance record: it names the malformed lines, the
    segment number, the session, the operator act that authorised it, and the
    runtime identity that performed it. Every audit claim that spans the
    boundary is thereby readable as spanning it."""
    path = Path(path)
    scan = journal_scan(path)
    if scan["healthy"]:
        return {"recovered": False, "reason": "the execution journal is healthy; nothing to recover",
                "health": {k: v for k, v in scan.items() if k != "events"}}
    identity = mb.runtime_identity()
    segment = len(scan["recoveries"]) + 1
    record = {"record": JOURNAL_RECOVERY_RECORD, "event": "execution_journal_recovered",
              "at": datetime.now(timezone.utc).isoformat(), "segment": segment,
              "acknowledged_through_line": scan["line_count"],
              "malformed_lines": [m["line"] for m in scan["malformed"]],
              "terminated_partial_line": bool(scan["unterminated_final_line"]),
              "reason": str(reason)[:300], "session_id": session_id, "operator": operator,
              "bytes_preserved": True,
              "runtime_head": identity.get("runtime_head"),
              "execution_tree_digest": identity.get("execution_tree_digest"),
              "runtime_environment_digest": identity.get("runtime_environment_digest")}
    line = json.dumps(record, sort_keys=True, default=str) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with mb._LedgerLock(path):                                             # noqa: SLF001 -- the same lock
        with open(path, "ab") as handle:
            if scan["unterminated_final_line"]:
                handle.write(b"\n")
            handle.write(line.encode("utf-8"))
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
    record["recovered"] = True
    return record


def journal_probe(path: Path) -> tuple[bool, str]:
    """Create / append / READ BACK one probe entry, before any provider
    request (Codex T50 §6) — and, since T51 §4, PARSE THE WHOLE FILE first.

    The old probe appended a token and checked that its own token came back,
    which an already-truncated line does not disturb: the probe passed, the
    append landed after the damage, and the malformed tail became a malformed
    middle. A journal whose earlier records cannot be read is not a journal,
    whatever this session's own line does."""
    health = journal_health(path)
    if not health["healthy"]:
        return False, (f"the execution journal is CORRUPT before this session's first append: "
                       f"{health['detail']}. The bytes are preserved; recover deliberately with "
                       f"tests/run_arms.py --recover-execution-journal (refused before the first real "
                       f"row exists — abort and reseal instead).")
    token = uuid.uuid4().hex
    event = {"event": "journal_probe", "token": token,
             "at": datetime.now(timezone.utc).isoformat()}
    try:
        journal(path, event, required=True)
    except JournalUnavailable as exc:
        return False, str(exc)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:                                                 # noqa: BLE001
        return False, f"the journal was written but cannot be read back: {type(exc).__name__}: {exc}"
    if token not in text:
        return False, "the journal accepted an append that does not read back — the entry is not durable"
    after = journal_health(path)
    if not after["healthy"]:
        return False, f"the journal became unhealthy as this session's probe landed: {after['detail']}"
    return True, "whole-file parse plus create/append/read-back probe passed"


def run_capability_probes(schedule: dict, providers_models: list[tuple], probe_fn=None,
                          timeout: float = 60.0, min_interval: float = 6.0,
                          window_ledger=None) -> dict:
    """`{(provider, model): result}` — one probe per configuration, covering
    EVERY replay policy the schedule's arms use (Codex T49 §7). Live, and
    tiny: two requests per policy, roughly six per configuration.

    `probe_fn` is injected by the tests; the default is
    `measure_budget.probe_configuration`."""
    contract = schedule.get("experiment_contract") or {}
    arms = contract.get("arm_contract") or SA.arm_contract(list(schedule["roster"]["arms"]))
    policies = sorted({bool(spec["reasoning_replay"]) for spec in arms.values()}, reverse=True)
    probe_fn = probe_fn or mb.probe_configuration
    results = {}
    for provider, model in providers_models:
        results[(provider, model)] = probe_fn(provider, model, tuple(policies), timeout=timeout,
                                              min_interval=min_interval, window_ledger=window_ledger)
    return results


#: The FOUR distinct probe outcomes (Codex T50 §7). The retired loop wrote
#: `capability_incompatible` for every non-admitted result, including one that
#: established nothing at all: unknown is not incompatible, and a journal that
#: says otherwise is evidence for a claim nobody made.
PROBE_EVENTS = ("probe_passed", "capability_failed", "probe_inconclusive", "inconclusive_accepted")


def probe_event(result: dict, accept_inconclusive: bool = False) -> str:
    """Which of `PROBE_EVENTS` this probe result IS.

    `admissible` is `all(v is not False)` and `conclusive` is `all(v is True)`
    (`measure_budget.probe_configuration`), so `not admissible` means at least
    one replay policy DETERMINISTICALLY failed — a conclusive capability
    verdict — while `admissible and not conclusive` is the unreachable
    endpoint / no-tool-call case, which establishes nothing."""
    if not bool(result.get("admissible")):
        return "capability_failed"
    if bool(result.get("conclusive")):
        return "probe_passed"
    return "inconclusive_accepted" if accept_inconclusive else "probe_inconclusive"


def probe_conclusively_failed(result: dict) -> bool:
    """Only a CONCLUSIVE failure excludes a configuration and writes an
    exclusion record. An inconclusive probe leaves the configuration unrun and
    UNKNOWN — never recorded as incompatible (Codex T50 §7/§8)."""
    return probe_event(result) == "capability_failed"


def probe_admits(result: dict, accept_inconclusive: bool = False) -> tuple[bool, bool]:
    """`(admitted, inconclusive)` for one configuration's probe result.

    A probe that FAILED refuses the configuration. A probe that was
    INCONCLUSIVE — the endpoint was unreachable, or the model would not call
    a tool, so the replaying request this probe exists to make was never made
    — establishes nothing, and admitting on it is starting untested, which is
    what §7 forbids. It is refused unless the operator says otherwise
    explicitly, and that decision is journalled."""
    admissible = bool(result.get("admissible"))
    inconclusive = admissible and not result.get("conclusive")
    admitted = admissible and (not inconclusive or bool(accept_inconclusive))
    return admitted, inconclusive


def startup_results(schedule: dict, reviews_dir: Path, root: Path | None = None,
                    window_ledger: Path | None = None, skip_journal_probe: bool = False) -> list[dict]:
    """The startup witness AS THE EXECUTOR RUNS IT — with the execution
    journal and the shared window ledger it is about to use.

    A separate function so the fail-closed journal probe (Codex T50 §6) and
    the ledger-health check (§5) are witnessed on the executor's own path,
    not only on a hand-built call in a test.

    `skip_journal_probe` is for the one pass that PRECEDES an explicit
    `--recover-execution-journal`: the probe's failure is the reason the
    operator is here, and the witness must still refuse everything else before
    the single mutating operation runs (the same ordering the window ledger's
    recovery already uses)."""
    return SW.witness(schedule, root=root,
                      journal_path=None if skip_journal_probe else SA.journal_path_for(reviews_dir, schedule),
                      window_ledger=window_ledger)


def sanitized_cell_environment(confirmatory: bool, base: dict | None = None,
                               pycache_prefix: Path | None = None) -> tuple[dict, dict]:
    """`(environment, record)` for a cell subprocess — the C1(a) closure.

    THE HOLE. Every cell was launched with this process's `os.environ`
    inherited whole. `PYTHONPATH` prepends directories to the child's
    `sys.path` before a line of the sealed instrument runs, so a directory
    named there shadows any sealed module — `openai/`, `json/`, `ssl.py` —
    while every hashed byte of the walked roots, and therefore the
    runtime-environment digest, stays exactly as sealed. `PYTHONHOME`
    relocates the standard library wholesale; `PYTHONSTARTUP` names a file the
    interpreter executes.

    In CONFIRMATORY mode all three are stripped, and `PYTHONPYCACHEPREFIX` is
    pointed at this session's fresh bytecode-cache directory (C2), so the
    child compiles from the sealed `.py` bytes instead of consulting a
    `__pycache__` the manifest does not cover. `record` is what the journal
    stores: which variables were present and stripped, and where the cache
    went. A pilot schedule is left alone — the sanitization is part of the
    confirmatory contract, not a global policy, and a pilot that needs a
    `PYTHONPATH` to run at all should keep it.

    Stripping is not the whole closure and is not meant to be: it protects the
    CELLS, while `schedule_arms.sys_path_survey` and the startup witness catch
    an injection in THIS process, before the strip could hide it."""
    environment = dict(os.environ if base is None else base)
    present = sorted(name for name in SA.IMPORT_INJECTING_ENVIRONMENT_VARS if name in environment)
    record = {"confirmatory": bool(confirmatory), "candidates": list(SA.IMPORT_INJECTING_ENVIRONMENT_VARS),
              "present": present, "stripped": [], "pycache_prefix": None}
    if not confirmatory:
        return environment, record
    for name in present:
        environment.pop(name, None)
    record["stripped"] = present
    prefix = pycache_prefix if pycache_prefix is not None else fresh_bytecode_cache_prefix()
    environment["PYTHONPYCACHEPREFIX"] = str(prefix)
    record["pycache_prefix"] = str(prefix)
    return environment, record


def cell_command(schedule: dict, cell: dict, session_id: str, actual_ordinal: int,
                 window_ledger: Path | None = None) -> list[str]:
    """The exact `measure_budget.py` invocation for one scheduled cell. Every
    sampling/budget parameter comes from the SCHEDULE, never from this
    process's own flags — a resumed session cannot silently run under
    different pins from the session that ran the first half."""
    roster = schedule["roster"]
    sampling = roster["sampling"]
    cmd = [PYTHON, str(ROOT / "tests" / "measure_budget.py"),
           "--model", cell["model"], "--provider", cell["provider"],
           "--selectors", cell["selector"], "--arm", cell["arm"], "--tag", cell["tag"],
           "--stamp-date", schedule["date_stamp"],
           "--replicate", str(cell["replicate"]),
           "--schedule-id", schedule["schedule_id"],
           "--planned-ordinal", str(cell["planned_ordinal"]),
           "--actual-ordinal", str(actual_ordinal),
           "--session-id", session_id,
           "--block-id", cell["block_id"],
           "--permutation-index", str(cell["permutation_index"]),
           "--arm-position", str(cell["arm_position"]),
           "--temperature", str(sampling["temperature"]), "--top-p", str(sampling["top_p"]),
           "--max-total-completion-tokens", str(roster["max_total_completion_tokens"]),
           "--timeout", str(roster["timeout"]), "--retries", str(roster["framework_retries"]),
           "--min-interval", str(roster["min_interval"])]
    # THE SEALED INSTRUMENT, PASSED DOWN (Codex T51 §2). The cell subprocess is
    # the process that spends the provider call, so it is the process that must
    # be able to refuse to: it re-verifies the execution tree before EVERY
    # request and both digests at the cell's opening and closing checks, and
    # exits `measure_budget.INSTRUMENT_DRIFT_EXIT` without calling the provider
    # when either differs.
    contract = schedule.get("experiment_contract") or {}
    for flag, key in (("--sealed-execution-tree-digest", "execution_tree_digest"),
                      ("--sealed-runtime-environment-digest", "runtime_environment_digest"),
                      ("--sealed-instrument-identity-version", "instrument_identity_version"),
                      ("--sealed-runtime-environment-identity-version",
                       "runtime_environment_identity_version")):
        if contract.get(key) is not None:
            cmd += [flag, str(contract[key])]
    if window_ledger is not None:
        cmd += ["--window-ledger", str(window_ledger)]
    if sampling.get("seed") is not None:
        cmd += ["--seed", str(sampling["seed"])]
    return cmd


def main() -> int:
    """`_main`, with the fail-closed execution journal turned into an exit
    code (Codex T50 §6). A confirmatory action that could not be recorded does
    not happen: the run stops where the append failed, and the operator sees
    exit 5 rather than a run that quietly lost its own audit trail."""
    try:
        return _main()
    except JournalUnavailable as exc:
        print(f"REFUSED (the execution journal fails CLOSED in confirmatory mode): {exc}", file=sys.stderr)
        return 5
    except mb.InstrumentDrift as exc:
        # Raised by this process's OWN pre-request check — the capability probe
        # is a provider call made here, not in a cell subprocess (Codex T51
        # §2.3). `_main`'s `finally` has already released the schedule lock.
        print(f"REFUSED (INSTRUMENT DRIFT in the executor's own provider call): {exc}", file=sys.stderr)
        return mb.INSTRUMENT_DRIFT_EXIT


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", required=True,
                        help="reviews/schedule_<label>.json, written by tests/schedule_arms.py BEFORE any "
                             "rollout. Its content digest is verified on load: an edited schedule is refused")
    parser.add_argument("--provider", default=None,
                        help="execute only this provider's cells (a schedule may span providers; running one "
                             "provider per process is fine). Unselected cells stay unrun, never failed")
    parser.add_argument("--models", nargs="+", default=None, help="further restrict to these models")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after this many whole three-arm BLOCKS this session. Never a cell count: "
                             "a block split across sessions is not the block the Williams order registered")
    parser.add_argument("--force", action="store_true",
                        help="re-run a cell that already has a complete row (overwrites it). REFUSED for a "
                             "sealed confirmatory schedule (Codex T49 §4): an observed result may not be "
                             "replaced, because the decision to replace it would be made after seeing it")
    parser.add_argument("--claim-ttl", type=float, default=DEFAULT_CLAIM_TTL_SECONDS,
                        help="seconds after which another executor's per-cell claim is REPORTED as stale "
                             "(default 2 h). It is never taken over automatically — see --take-over-lock")
    parser.add_argument("--take-over-lock", action="store_true",
                        help="take over the schedule-level executor lock from a session you have VERIFIED is "
                             "dead. The takeover is written into the arms log as an operator act")
    parser.add_argument("--probe-capabilities", dest="probe", action="store_true", default=None,
                        help="run the pre-run capability probe (default ON for a confirmatory schedule)")
    parser.add_argument("--no-probe-capabilities", dest="probe", action="store_false",
                        help="skip the capability probe (a configuration is then admitted untested)")
    parser.add_argument("--accept-inconclusive-probe", action="store_true",
                        help="admit a configuration whose capability probe was INCONCLUSIVE (endpoint "
                             "unreachable, or the model would not call a tool). Without it such a "
                             "configuration is REFUSED rather than started untested; with it, the decision "
                             "is recorded in the execution journal as an operator act")
    parser.add_argument("--recover-window-ledger", action="store_true",
                        help="EXPLICIT operator recovery of a window ledger that carries malformed "
                             "evidence (Codex T50 §5). The damaged bytes are preserved; a segment "
                             "boundary is appended, the act is journalled, and every rate-limit "
                             "classification whose window spans the boundary becomes ambiguous. Refused "
                             "when the ledger is healthy — this is not a routine flag")
    parser.add_argument("--recover-execution-journal", action="store_true",
                        help="EXPLICIT operator recovery of an execution journal that carries a "
                             "malformed line (Codex T51 §4, his Q4). REFUSED before the first real row "
                             "exists — there is no recovery path there, the answer is to abort and "
                             "RESEAL. After rows exist it mirrors the window ledger's segment recovery: "
                             "the damaged bytes are preserved, an immutable boundary with a provenance "
                             "record is appended, and every audit claim that spans it reads as spanning "
                             "it")
    parser.add_argument("--window-ledger", default=None,
                        help="the shared provider-window ledger (default <schedule>.window.jsonl). Pacing is "
                             "enforced against ITS last entry across cells, and a 429 archives the observed "
                             "trailing-60 s window it was refused in")
    parser.add_argument("--dry-run", action="store_true",
                        help="run the startup witness and print the plan; make no provider call")
    parser.add_argument("--reviews-dir", default=None)
    args = parser.parse_args()

    schedule_path = Path(args.schedule)
    schedule = SA.load_schedule(schedule_path)
    confirmatory = SA.is_confirmatory(schedule)
    reviews_dir = Path(args.reviews_dir) if args.reviews_dir else ROOT / "reviews"
    session_id = uuid.uuid4().hex[:12]
    window_ledger = Path(args.window_ledger) if args.window_ledger else Path(str(schedule_path) + ".window.jsonl")

    if confirmatory and args.force:
        print("REFUSED: --force on a SEALED confirmatory schedule. An observed cell may not be re-run or "
              "overwritten — the decision to replace it would be made after seeing its outcome (Codex T49 "
              "§4). An instrument defect is repaired by a NEW schedule or a predeclared replacement record "
              "that preserves the original row and its reason.", file=sys.stderr)
        return 2

    # Codex T50 §7: the capability probe is a PRE-RUN, CONFIGURATION-WIDE fact
    # in the sealed analysis plan. An operator flag that turns it off does not
    # change `schedule_id`, so rows created through that path would satisfy the
    # same exact cell identity and enter the confirmatory table as though the
    # configuration had been established. There is no such flag for a sealed
    # schedule.
    if confirmatory and args.probe is False:
        print("REFUSED: --no-probe-capabilities on a SEALED confirmatory schedule. The analysis plan "
              "registers the capability probe as pre-run and configuration-wide; skipping it would admit "
              "an untested configuration whose rows are indistinguishable from probed ones, without "
              "changing schedule_id (Codex T50 §7). Run the probe, or admit an INCONCLUSIVE one "
              "deliberately with --accept-inconclusive-probe, which is journalled fail-closed.",
              file=sys.stderr)
        return 2

    # -- the startup witness, before anything else at all -------------------
    # Including before the ONE mutating operation a sealed schedule permits
    # (adversarial review, C3). Recovery used to run and journal FIRST, so the
    # single write the contract allows was made from a checkout the witness
    # would then have refused. The ledger-health row is skipped for this pass
    # when a recovery is requested — its failure is the reason we are here —
    # and re-checked immediately after the recovery lands.
    if confirmatory:
        results = startup_results(schedule, reviews_dir, root=ROOT,
                                  window_ledger=None if args.recover_window_ledger else window_ledger,
                                  skip_journal_probe=args.recover_execution_journal)
        print(f"startup witness ({len(results)} fields) for {schedule['label']} "
              f"{schedule['schedule_id'][:12]}...")
        bad = SW.failures(results)
        if bad or args.dry_run:
            print("\n".join(SW.format_results(results)))
        if bad:
            print("REFUSED before request 1: " + ", ".join(r["field"] for r in bad), file=sys.stderr)
            print("  The sealed schedule does not describe this checkout/evaluator. Nothing was run.",
                  file=sys.stderr)
            return 3
        print(f"  all {len(results)} sealed fields match this checkout, these libraries and the active "
              f"release manifest")
        # ARM THIS PROCESS TOO (Codex T51 §2.3). The capability probe is a real
        # provider call, made HERE rather than in a cell subprocess, and it
        # happens seconds to minutes after the witness. Arming the executor
        # puts the probe's requests behind the same per-request tree check that
        # every cell's requests are behind, instead of relying on the witness
        # having been green a moment earlier.
        mb.set_sealed_instrument(
            (schedule["experiment_contract"] or {}).get("execution_tree_digest"),
            (schedule["experiment_contract"] or {}).get("runtime_environment_digest"),
            (schedule["experiment_contract"] or {}).get("instrument_identity_version"),
            (schedule["experiment_contract"] or {}).get("runtime_environment_identity_version"))

    # -- the operator recovery of a damaged EXECUTION JOURNAL (Codex T51 §4) --
    #    AFTER the witness is green, for the same reason the ledger recovery is
    #    (adversarial review, C3): a recovery written from a checkout the
    #    witness would refuse is a mutation nobody authorised.
    if args.recover_execution_journal:
        journal_file = journal_path_for(reviews_dir, schedule)
        health = journal_health(journal_file)
        if health["healthy"]:
            print(f"REFUSED: --recover-execution-journal, but {journal_file.name} is healthy "
                  f"({health['line_count']} line(s), no malformed evidence). Recovery starts a new "
                  f"audit segment; it is not a routine flag.", file=sys.stderr)
            return 2
        # HIS Q4 ANSWER, ENCODED. Before the first real row exists there is no
        # recovery path at all: nothing has been observed, so nothing is lost
        # by cutting a new schedule, and a journal whose first segment is
        # already damaged has no audit trail to preserve.
        observed = [cell for cell in schedule["cells"]
                    if cell_status(SA.output_path_for(reviews_dir, cell["model"],
                                                      schedule["date_stamp"], cell["tag"]),
                                   schedule, cell)[0] == "done"]
        if not observed:
            print(f"REFUSED: --recover-execution-journal, but NO cell of this schedule has a real row "
                  f"yet ({len(schedule['cells'])} scheduled, 0 observed). Before the first row there is "
                  f"no recovery path: nothing has been observed, so ABORT AND RESEAL — cut a new label "
                  f"with tests/schedule_arms.py --seal and leave this journal's bytes as evidence. "
                  f"Segment recovery exists only to preserve an audit trail that already has "
                  f"observations in it (Codex T51 Q4).", file=sys.stderr)
            return 2
        record = journal_recover(journal_file, reason=health["detail"], session_id=session_id,
                                 operator="run_arms --recover-execution-journal")
        after = journal_health(journal_file)
        if not after["healthy"]:
            print(f"REFUSED: the execution journal is still UNHEALTHY after recovery: {after['detail']}",
                  file=sys.stderr)
            return 3
        # Journalled AFTER the boundary lands, because the boundary is what
        # makes the journal appendable again — the recovery record IS the
        # provenance record, and this entry names the observations it protects.
        journal(journal_file,
                {"event": "execution_journal_recovered", "session_id": session_id,
                 "at": datetime.now(timezone.utc).isoformat(), "journal": str(journal_file),
                 "segment": record.get("segment"), "record": record, "health_before": health,
                 "observed_cells_at_recovery": len(observed)},
                required=confirmatory)
        print(f"  EXECUTION JOURNAL RECOVERED: {health['detail']}\n"
              f"  The damaged bytes are preserved; audit segment {record.get('segment')} starts here, "
              f"{len(observed)} observed cell(s) preceded it, and every audit claim that spans the "
              f"boundary reads as spanning it.")

    # -- the operator recovery of a damaged window ledger (Codex T50 §5) ----
    #    AFTER the witness is green (adversarial review, C3).
    if args.recover_window_ledger:
        health = mb.window_ledger_health(window_ledger)
        if health["healthy"]:
            print(f"REFUSED: --recover-window-ledger, but {window_ledger.name} is healthy "
                  f"({health['line_count']} line(s), no malformed evidence). Recovery starts a new "
                  f"evidence segment and makes the rate-limit classifications that span it ambiguous; it "
                  f"is not a routine flag.", file=sys.stderr)
            return 2
        record = mb.window_ledger_recover(window_ledger, reason=health["detail"], session_id=session_id,
                                          operator="run_arms --recover-window-ledger")
        try:
            journal(journal_path_for(reviews_dir, schedule),
                    {"event": "window_ledger_recovered", "session_id": session_id,
                     "at": datetime.now(timezone.utc).isoformat(), "ledger": str(window_ledger),
                     "record": record, "health_before": health}, required=confirmatory)
        except JournalUnavailable as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 5
        after = mb.window_ledger_health(window_ledger)
        if not after["healthy"]:
            print(f"REFUSED: the window ledger is still UNHEALTHY after recovery: {after['detail']}",
                  file=sys.stderr)
            return 3
        print(f"  WINDOW LEDGER RECOVERED: {health['detail']}\n"
              f"  The damaged bytes are preserved; evidence segment {record.get('segment')} starts here, "
              f"and every 429 whose trailing window spans the boundary classifies AMBIGUOUS.")

    cells = sorted(schedule["cells"], key=lambda c: c["planned_ordinal"])
    selected = [c for c in cells
                if (args.provider is None or c["provider"] == args.provider)
                and (args.models is None or c["model"] in args.models)]
    pending: list = []
    resumed: list[str] = []
    quarantined: list[str] = []
    done_count = 0
    for cell in selected:
        out_path = SA.output_path_for(reviews_dir, cell["model"], schedule["date_stamp"], cell["tag"])
        status, why = cell_status(out_path, schedule, cell)
        if status == "done" and not args.force:
            done_count += 1
            continue
        if status == "integrity":
            # Never silently skipped, never re-run over.
            quarantined.append(f"planned {cell['planned_ordinal']} {cell['tag']}: {why}")
            journal(journal_path_for(reviews_dir, schedule),
                    {"event": "execution_integrity", "session_id": session_id, "tag": cell["tag"],
                     "planned_ordinal": cell["planned_ordinal"], "block_id": cell["block_id"],
                     "at": datetime.now(timezone.utc).isoformat(), "detail": why},
                    required=confirmatory)
            continue
        if out_path.exists() and not args.force:
            resumed.append(f"{cell['tag']}: {why}")
        pending.append((cell, out_path))
    pending, n_blocks = limit_to_whole_blocks(pending, args.limit)

    # A block whose arms are not all pending is being SPLIT across sessions:
    # some of its cells already ran, under another session and another
    # provider-window state. That is not a refusal, but it is a fact about
    # the executed design and it goes on the record.
    pending_by_block: dict = {}
    for cell, _ in pending:
        pending_by_block.setdefault(cell["block_id"], []).append(cell)
    split_blocks = [bid for bid, group in sorted(pending_by_block.items())
                    if len(group) != sum(1 for c in selected if c["block_id"] == bid)]

    log = reviews_dir / f"arms_{datetime.now().strftime('%Y-%m-%d')}.log"
    journal_file = journal_path_for(reviews_dir, schedule)
    started = time.monotonic()
    header = (f"\n=== schedule {schedule['label']} ({schedule['schedule_id'][:12]}...) "
              f"{'CONFIRMATORY' if confirmatory else 'pilot'} session {session_id} "
              f"started {datetime.now().isoformat(timespec='seconds')}: {len(pending)} of "
              f"{len(selected)} selected cells pending in {n_blocks} whole block(s) "
              f"({done_count} already complete, {len(quarantined)} quarantined; "
              f"{schedule['n_cells']} scheduled in total); "
              f"provider filter {args.provider}, models {args.models}, force={args.force} ===")
    print(header)
    print(f"BALANCE: {schedule['balance']['statement']}")
    for line in quarantined:
        print(f"  EXECUTION INTEGRITY (quarantined, NOT re-run) — {line}")
    for line in resumed:
        print(f"  RE-RUNNING an incomplete output file — {line}")
    for bid in split_blocks:
        print(f"  BLOCK SPLIT ACROSS SESSIONS: {bid} — some arms ran in an earlier session")

    if args.dry_run:
        for cell, out_path in pending:
            print(f"  planned {cell['planned_ordinal']:>4}  {cell['provider']}/{cell['model']} "
                  f"{cell['selector']} r{cell['replicate']} {cell['arm']}' (position {cell['arm_position']}, "
                  f"permutation {cell['permutation_index']}) -> {out_path.name}")
        print(f"dry run: {len(pending)} cells in {n_blocks} block(s) would run; window ledger "
              f"{window_ledger.name}")
        if quarantined:
            print(f"dry run: {len(quarantined)} cell(s) are QUARANTINED for execution integrity and would "
                  f"NOT run")
        return 0

    # -- one executor per schedule -----------------------------------------
    acquired, lock_note, held, ours = acquire_schedule_lock(schedule_path, session_id,
                                                            args.take_over_lock)
    if not acquired:
        print(f"REFUSED: {lock_note}", file=sys.stderr)
        return 4
    # AFTER ACQUISITION, BEFORE ANY EXECUTION (Codex T51 §3): re-read the lock
    # and prove its nonce is ours. The takeover path already did this inside
    # the guard; doing it here as well covers the clean path and costs a read.
    proved, proof = prove_lock_ownership(schedule_path, ours)
    if not proved:
        print(f"REFUSED: {proof}. Nothing was run.", file=sys.stderr)
        return 4
    print(f"  {lock_note}")
    print(f"  {proof}")
    reviews_dir.mkdir(exist_ok=True)
    # THE CELL ENVIRONMENT, SANITIZED AND RECORDED (C1(a), C2). Computed ONCE
    # for the session so every cell is launched under the same environment and
    # the journal's record describes all of them. The startup witness has
    # already refused if an injected `sys.path` entry was live in THIS process,
    # so this is the second half: what the cells get.
    cell_environment, environment_record = sanitized_cell_environment(
        confirmatory, pycache_prefix=fresh_bytecode_cache_prefix())
    #: Set when a cell subprocess reports INSTRUMENT DRIFT. A drifted
    #: instrument invalidates everything after it, so the session stops where
    #: it happened and says so in its exit code (Codex T51 §2).
    drift_stop: str | None = None
    try:
        # WHAT THE CELLS WILL RUN UNDER, journalled BEFORE the first of them
        # and fail-closed in confirmatory mode: a sanitization that was
        # performed and not recorded reads afterwards exactly like one that
        # never happened, and the whole point of C1(a)/C2 is that a reader can
        # tell which environment produced the rows.
        journal(journal_file,
                {"event": "cell_environment_sealed", "session_id": session_id,
                 "at": datetime.now(timezone.utc).isoformat(), **environment_record},
                required=confirmatory)
        if environment_record["stripped"]:
            print(f"  CELL ENVIRONMENT SANITIZED: stripped "
                  f"{', '.join(environment_record['stripped'])} from every cell subprocess — an "
                  f"import-injecting variable shadows a sealed module without moving one hashed byte")
        if environment_record["pycache_prefix"]:
            print(f"  BYTECODE CACHE REDIRECTED: PYTHONPYCACHEPREFIX="
                  f"{environment_record['pycache_prefix']} (fresh this session, for this process and "
                  f"every cell) — no pre-existing __pycache__ is consulted, so the excluded *.pyc are "
                  f"only ones compiled from the sealed source")
        if args.take_over_lock:
            # Written IMMEDIATELY, before the capability probe and before any
            # cell: a takeover that is only journalled at the end is missing
            # from exactly the run that crashed after it. The displaced
            # session is named, so the actual-order census can see the seam.
            # FAIL-CLOSED in confirmatory mode (Codex T50 §6): a takeover that
            # could not be recorded is a takeover that did not happen — the
            # raise reaches `main`, the `finally` below releases the lock, and
            # nothing runs.
            journal(journal_path_for(reviews_dir, schedule),
                    {"event": "schedule_lock_taken_over", "session_id": session_id,
                     "displaced_session": (held or {}).get("session_id"),
                     "displaced_pid": (held or {}).get("pid"),
                     # The displaced lock's exact bytes are preserved beside
                     # the schedule and named here (Codex T51 §3), so the
                     # takeover is reconstructable rather than merely asserted.
                     "displaced_archive":
                         takeover_archive_path_for(schedule_path, session_id).name,
                     "lock_nonce": (ours or {}).get("nonce"),
                     "at": datetime.now(timezone.utc).isoformat(), "note": lock_note},
                    required=confirmatory)
        # -- the configuration-wide capability probe ------------------------
        probe = args.probe if args.probe is not None else confirmatory
        blocked: set = set()
        probe_results: dict = {}
        if probe and pending:
            configurations = sorted({(c["provider"], c["model"]) for c, _ in pending})
            print(f"  capability probe: {len(configurations)} configuration(s), every replay policy")
            probe_results = run_capability_probes(schedule, configurations,
                                                  timeout=schedule["roster"]["timeout"],
                                                  min_interval=schedule["roster"]["min_interval"],
                                                  window_ledger=window_ledger)
            failed_configurations: set = set()
            for key, result in sorted(probe_results.items(), key=str):
                admitted, inconclusive = probe_admits(result, args.accept_inconclusive_probe)
                # FOUR DISTINCT OUTCOMES (Codex T50 §7). "Unknown" is not
                # "incompatible": the retired loop wrote `capability_
                # incompatible` for every non-admitted result, so an
                # unreachable endpoint became evidence of a capability
                # verdict nobody established.
                event = probe_event(result, args.accept_inconclusive_probe)
                verdict = ("ADMISSIBLE" if admitted else "REFUSED")
                if inconclusive:
                    verdict += (" — INCONCLUSIVE, admitted on an explicit --accept-inconclusive-probe"
                                if args.accept_inconclusive_probe
                                else " — INCONCLUSIVE: re-run the probe, or admit it deliberately with "
                                     "--accept-inconclusive-probe")
                print(f"    {key[0]}/{key[1]}: {verdict}  [{event}]")
                journal(journal_file, {"event": event, "session_id": session_id,
                                       "provider": key[0], "model": key[1], "admitted": bool(admitted),
                                       "inconclusive": bool(inconclusive),
                                       "conclusive": bool(result.get("conclusive")),
                                       "accept_inconclusive_probe": bool(args.accept_inconclusive_probe),
                                       "at": datetime.now(timezone.utc).isoformat(), "result": result},
                        required=confirmatory)
                if not admitted:
                    blocked.add(key)
                if probe_conclusively_failed(result):
                    failed_configurations.add(key)
                    if confirmatory:
                        # THE IMMUTABLE, CONTENT-BOUND EXCLUSION RECORD (his
                        # Q9). `arm_table` cannot infer a configuration-level
                        # exclusion from row-level failures, because the cells
                        # this blocks have no rows at all. Written beside the
                        # schedule, fail-closed: an exclusion that was decided
                        # and not recorded would read afterwards as merely
                        # unrun.
                        try:
                            record = SA.write_configuration_exclusion(
                                schedule_path, schedule, key[0], key[1],
                                reason="capability_probe_failed",
                                evidence={"policies": result.get("policies"),
                                          "admissible": result.get("admissible"),
                                          "conclusive": result.get("conclusive")},
                                session_id=session_id, root=ROOT)
                        except OSError as exc:                             # noqa: BLE001
                            raise JournalUnavailable(
                                f"the configuration exclusion for {key[0]}/{key[1]} could not be "
                                f"recorded beside the schedule: {type(exc).__name__}: {exc}") from exc
                        print(f"      configuration_exclusion recorded "
                              f"({str(record.get('record_digest'))[:12]}...)")
            if blocked:
                for cell, _ in pending:
                    configuration = (cell["provider"], cell["model"])
                    if configuration not in blocked:
                        continue
                    journal(journal_file,
                            {"event": ("capability_incompatible" if configuration in failed_configurations
                                       else "cell_unrun_probe_inconclusive"),
                             "session_id": session_id, "tag": cell["tag"], "provider": cell["provider"],
                             "model": cell["model"], "block_id": cell["block_id"],
                             "at": datetime.now(timezone.utc).isoformat()},
                            required=confirmatory)
                pending = [item for item in pending if (item[0]["provider"], item[0]["model"]) not in blocked]
                print(f"    {len(blocked)} configuration(s) refused BEFORE any of their cells ran "
                      f"({len(failed_configurations)} conclusively incompatible and excluded by record; "
                      f"the rest INCONCLUSIVE — left unrun and UNKNOWN, never recorded as incompatible)")

        with log.open("a", encoding="utf-8") as fh:
            fh.write(header + "\n")
            fh.write(f"  {lock_note}\n")
            fh.write(f"  balance: {schedule['balance']['statement']}\n")
            for line in quarantined:
                fh.write(f"  EXECUTION INTEGRITY (quarantined, not re-run): {line}\n")
            for bid in split_blocks:
                fh.write(f"  BLOCK SPLIT ACROSS SESSIONS: {bid}\n")
            for key, result in sorted(probe_results.items(), key=str):
                fh.write(f"  capability probe {key[0]}/{key[1]}: "
                         f"admissible={result.get('admissible')} conclusive={result.get('conclusive')}\n")
            # The PLANNED order is logged before any cell runs; the ACTUAL
            # order is whatever the session then achieves, and both are on
            # every row.
            for cell, out_path in pending:
                fh.write(f"  planned {cell['planned_ordinal']:>4}: {cell['provider']}/{cell['model']} "
                         f"{cell['selector']} r{cell['replicate']} {cell['arm']}' "
                         f"position={cell['arm_position']} permutation={cell['permutation_index']} "
                         f"block={cell['block_id']}\n")
            fh.flush()

            actual_ordinal = 0
            stopped_configurations: set = set()
            for cell, out_path in pending:
                configuration = (cell["provider"], cell["model"])
                if configuration in stopped_configurations:
                    note = (f"SKIP planned {cell['planned_ordinal']} {cell['tag']}: its configuration was "
                            f"stopped mid-run for a NEW capability incompatibility; remaining cells are "
                            f"left unrun rather than decided by outcome")
                    print(f"  {note}", flush=True)
                    fh.write(f"  {note}\n")
                    journal(journal_file, {"event": "configuration_stopped", "session_id": session_id,
                                           "tag": cell["tag"], "provider": cell["provider"],
                                           "model": cell["model"],
                                           "at": datetime.now(timezone.utc).isoformat()},
                            required=confirmatory)
                    continue
                claimed, claim_note = claim_cell(out_path, session_id, cell, args.claim_ttl)
                if not claimed:
                    skip = (f"SKIP planned {cell['planned_ordinal']} {cell['tag']}: {claim_note}")
                    print(f"  {skip}", flush=True)
                    fh.write(f"  {skip}\n")
                    fh.flush()
                    continue
                actual_ordinal += 1
                label = (f"[{actual_ordinal}/{len(pending)}] planned {cell['planned_ordinal']} "
                         f"{cell['selector']} r{cell['replicate']} {cell['model'].split('/')[-1]} "
                         f"{cell['arm']}' ")
                cmd = cell_command(schedule, cell, session_id, actual_ordinal, window_ledger)
                t0 = time.monotonic()
                started_at = datetime.now(timezone.utc).isoformat()
                journal(journal_file, {"event": "cell_started", "session_id": session_id, "tag": cell["tag"],
                                       "planned_ordinal": cell["planned_ordinal"],
                                       "actual_ordinal": actual_ordinal, "block_id": cell["block_id"],
                                       "arm": cell["arm"], "provider": cell["provider"],
                                       "model": cell["model"], "selector": cell["selector"],
                                       "replicate": cell["replicate"], "at": started_at},
                        required=confirmatory)
                print(f"{label}... ", end="", flush=True)
                fh.write(f"{datetime.now().isoformat(timespec='seconds')} actual {actual_ordinal} {label}"
                         f"({claim_note})...\n")
                fh.flush()
                try:
                    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                                          encoding="utf-8", errors="replace",
                                          env=cell_environment)
                finally:
                    # Released only if still ours: a claim that outlives its
                    # process is a process that died.
                    release_cell(out_path, session_id)
                took = time.monotonic() - t0
                tail = mb.redact_secrets("\n".join((proc.stdout or "").strip().splitlines()[-6:]))
                print(f"exit {proc.returncode} in {took / 60:.1f} min", flush=True)
                fh.write(f"  exit {proc.returncode} in {took / 60:.1f} min\n{tail}\n")
                stderr_tail = ""
                if proc.returncode != 0:
                    stderr_tail = mb.redact_secrets("\n".join((proc.stderr or "").strip().splitlines()[-12:]))
                    fh.write("  stderr tail:\n" + stderr_tail + "\n")
                journal(journal_file, {"event": "cell_finished", "session_id": session_id, "tag": cell["tag"],
                                       "planned_ordinal": cell["planned_ordinal"],
                                       "actual_ordinal": actual_ordinal, "block_id": cell["block_id"],
                                       "started_at": started_at,
                                       "finished_at": datetime.now(timezone.utc).isoformat(),
                                       "seconds": round(took, 1), "exit_code": proc.returncode},
                        required=confirmatory)
                # INSTRUMENT DRIFT (Codex T51 §2). The cell verified both
                # digests before request 1 and the execution tree before every
                # request; it exited without making a call and without leaving
                # a row. A drifted instrument invalidates everything after it,
                # so this is not a cell-level skip: the SESSION stops here,
                # fail-closed, and the journal carries the quarantine that the
                # table then refuses to render estimands over.
                if proc.returncode == mb.INSTRUMENT_DRIFT_EXIT:
                    drift_stop = (f"cell {cell['tag']} (planned {cell['planned_ordinal']}) reported "
                                  f"INSTRUMENT DRIFT and made no provider call: {stderr_tail.strip()[:400]}")
                    note = (f"  EXECUTION INTEGRITY — instrument_drift: {drift_stop}\n"
                            f"  The session STOPS here. The code or the interpreter that would have run "
                            f"this cell is not the sealed instrument, so nothing after this point could "
                            f"be attributed to the sealed one either.")
                    print(note, flush=True)
                    fh.write(note + "\n")
                    journal(journal_file,
                            {"event": "execution_integrity", "reason": "instrument_drift",
                             "session_id": session_id, "tag": cell["tag"],
                             "planned_ordinal": cell["planned_ordinal"], "block_id": cell["block_id"],
                             "provider": cell["provider"], "model": cell["model"],
                             "at": datetime.now(timezone.utc).isoformat(), "detail": drift_stop},
                            required=confirmatory)
                    journal(journal_file,
                            {"event": "instrument_drift", "session_id": session_id, "tag": cell["tag"],
                             "planned_ordinal": cell["planned_ordinal"], "block_id": cell["block_id"],
                             "at": datetime.now(timezone.utc).isoformat(), "detail": drift_stop,
                             "session_stopped": True},
                            required=confirmatory)
                    fh.flush()
                    break
                # A NEW capability incompatibility appearing mid-run stops the
                # CONFIGURATION (Codex T49 §7). It is read from the archived
                # row's own blind classification, never from the arm.
                if confirmatory and _row_is_capability_incompatible(out_path, cell):
                    stopped_configurations.add(configuration)
                    note = (f"  CONFIGURATION STOPPED: {configuration[0]}/{configuration[1]} produced a "
                            f"capability incompatibility mid-run; its remaining cells will not be run and "
                            f"are left unrun, not decided by outcome")
                    print(note, flush=True)
                    fh.write(note + "\n")
                    # The cells this blocks have NO rows, so the table cannot
                    # learn about the exclusion from row-level failures (Codex
                    # T50 §8/Q9). The record is what carries it.
                    try:
                        SA.write_configuration_exclusion(
                            schedule_path, schedule, configuration[0], configuration[1],
                            reason="capability_incompatible_mid_run",
                            evidence={"first_offending_tag": cell["tag"],
                                      "planned_ordinal": cell["planned_ordinal"]},
                            session_id=session_id, root=ROOT)
                    except OSError as exc:                                 # noqa: BLE001
                        raise JournalUnavailable(
                            f"the mid-run configuration exclusion for {configuration[0]}/"
                            f"{configuration[1]} could not be recorded: "
                            f"{type(exc).__name__}: {exc}") from exc
                fh.flush()
            fh.write(f"=== session {session_id} finished in {(time.monotonic() - started) / 60:.1f} min "
                     f"===\n")
    finally:
        release_schedule_lock(schedule_path, session_id, ours)
    if drift_stop is not None:
        print(f"REFUSED (INSTRUMENT DRIFT): {drift_stop}", file=sys.stderr)
        return mb.INSTRUMENT_DRIFT_EXIT
    print(f"done in {(time.monotonic() - started) / 60:.1f} min; log {log}; journal {journal_file.name}")
    return 0


def _row_is_capability_incompatible(out_path: Path, cell: dict) -> bool:
    """Did the cell that just ran fail with a CAPABILITY incompatibility? Read
    from the archived row through the same blind classifier the table uses —
    never from the arm and never from the outcome."""
    try:
        rows = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(rows, list):
        return False
    import arm_table as AT                                                 # noqa: PLC0415 -- lazy
    for row in rows:
        if isinstance(row, dict) and row.get("tag") == cell["tag"]:
            bucket, _rule = AT.classify_row(row)
            if bucket == "capability_incompatible":
                return True
    return False


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
