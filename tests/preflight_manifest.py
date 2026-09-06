"""Preflight the release population under the evaluator's OWN secret and write
the signed manifest that `load_environment` serves from.

    python tests/preflight_manifest.py --train 2000 --eval 500 --hard 500 [--out ~/.piv/manifest.json]

Runs in the evaluator process, under the active secret (PIV_EVAL_SECRET or
~/.piv/eval_secret) — NOT the test-suite secret: a test-secret sweep validates
a different population.

TWO PHASES, TWO CLAIMS
----------------------
The two things a release has to prove are different things, and a preflight
that mixes them proves neither cleanly:

    PHASE 1 — offline gates.   Mint each selector and run every gate on THAT
        EXACT immutable world, with no manifest and no serving door anywhere
        in the picture. `golden_scores_one` builds its environment through
        `beancount_ledger.environment_from_minted(m)`, which consults no
        manifest at all. Claim: the minted world passes the semantic gates.

    PHASE 2 — serving verification.   AFTER the manifest is written and
        signed, call the real `load_environment(selector)` for EVERY record,
        with the development override explicitly removed from the worker's
        environment. The served public id must equal the record's, and the
        served environment's `episode_contract_digest()` must equal the
        default one. Claim: the signed manifest admits exactly those worlds
        through the door production uses.

The previous single phase pointed the workers at a `PIV_MANIFEST` path that
does not exist, so `admit` took the development route (a `tests/` entrypoint
with PIV_DEV_UNMANIFESTED=1) and judged the world rather than the file. That
solved the chicken-and-egg by invoking a bypass production must never honour,
and it said nothing about the serving door. Both phases are now reported
separately, and either one failing exits 1.

The gates, all run in phase 1:

    minted             the generator produced a valid world within its attempts
    identifiable       the public-only checker, with no prior, finds one reading
    repair_key_equal   that reading's repairs equal the planted items under the
                       decomposed repair key (checker side `identify.repair_key`
                       vs truth side `repair_keys.planted_key`)
    golden_scores_one  the contract's golden ledger scores 1.0, complete and
                       renderable, through the real write/commit/finalise loop
                       on the freshly minted world
    id_unique          the public id collides with no other selector's
    ledger_within_envelope
                       the projected ledger fits LEDGER_ENVELOPE_BYTES /
                       LEDGER_ENVELOPE_LINES, which is what `read_file`
                       returning it whole in one call is sized for

SERVEABILITY IS NOT A PHASE-1 GATE, by construction. The six gates ask whether
the minted WORLD is sound; none of them asks whether `load_environment` would
accept the SELECTOR. So a permanently unservable selector — an index at or
above MAX_SELECTOR_INDEX is the clean example — mints a perfectly good world,
passes all six, and is signed into the manifest as passed. Phase 2 is exactly
that missing check: it refuses the selector and fails the preflight, which is
the intended outcome and the reason the two claims are reported separately
instead of being summed into one "N/M passed".

A selector failing any gate is recorded as failed (served: never) and listed;
the manifest is still written so serving is well-defined. Exit code 1 when any
selector failed a gate OR any record was refused at the serving door.

The run also reports and stores the LEDGER CENSUS beside the manifest
(`<manifest>_census.json`): how many ledgers were measured, the maximum and
minimum bytes and logical lines, and the headroom against the envelope. The
gate says every world fits; the census is what makes a generator change that
quietly eats the headroom visible before a live rollout pays for it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Phase 1 mints before a manifest exists, by definition, and nothing in it
# goes through the serving door — but `tests/score_payload.py` sets the same
# flag at import for its own interactive use, so it is set here explicitly and
# REMOVED again inside the phase-2 workers. On Windows every pool worker
# re-imports this module, so a value popped in the parent would come back;
# `serve_one` pops it in the worker instead, where it cannot.
PHASE_ENV = "PIV_PREFLIGHT_PHASE"
if os.environ.get(PHASE_ENV) != "serve":
    os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")


def selector_of(namespace: str, index: int, profile_name: str) -> str:
    """The public selector string `load_environment` takes."""
    return f"{namespace}:{index}" + (":hard" if profile_name == "hard" else "")


def gate_one(job):
    """PHASE 1. Every gate, run on the freshly minted world itself."""
    namespace, index, profile_name = job
    from beancount_ledger.graph.generate import DEFAULT_PROFILE, HARD_PROFILE
    from beancount_ledger.graph import identify as ID
    from beancount_ledger.graph.mint import mint
    from beancount_ledger.graph import manifest as MF
    profile = HARD_PROFILE if profile_name == "hard" else DEFAULT_PROFILE
    out = {"namespace": namespace, "index": index, "profile": profile.name, "gates": {}, "notes": []}
    try:
        m = mint(namespace, index, profile)
    except Exception as exc:                      # noqa: BLE001
        out["gates"] = {g: False for g in MF.GATES}
        out["notes"].append(f"mint: {type(exc).__name__}: {exc}"[:200])
        return out
    out.update(public_id=m.inputs.task_id, attempt=m.provenance.attempt)
    out["gates"]["minted"] = True
    # The observation envelope: `read_file` hands the ledger back whole, so a
    # world whose ledger does not fit is not one we can serve. Same predicate
    # `load_environment`, `_verify_public_world` and `write_ledger` use.
    from beancount_ledger.beancount_ledger import LEDGER, ledger_envelope_breach, logical_text
    ledger_bytes = dict(m.inputs.public_files)[LEDGER]
    breach = ledger_envelope_breach(ledger_bytes)
    out["gates"]["ledger_within_envelope"] = breach is None
    if breach is not None:
        out["notes"].append(f"ledger envelope: {breach}")
    # The census, not just the gate: the envelope is comfortably
    # above the measured population TODAY, and a generator change that quietly
    # consumes the headroom would still pass every gate. Reporting the measured
    # maximum beside the envelope is what makes that visible in the release
    # record rather than in a live rollout.
    out["ledger_bytes"] = len(ledger_bytes)
    out["ledger_lines"] = len(logical_text(ledger_bytes).splitlines())
    pub = {n: d.decode("utf-8") for n, d in m.inputs.public_files}
    v = ID.check_identifiable(pub, bank_account=m.world.bank_account,
                              period_start=m.task.period.start, period_end=m.task.period.end)
    out["gates"]["identifiable"] = bool(v.unique)
    if not v.unique:
        out["notes"].append("ambiguous: " + v.reason[:160])
    # decomposed repair-key equality: both sides must exist; otherwise the gate fails loudly
    try:
        from beancount_ledger.graph.identify import repair_key
        from repair_keys import master_names, planted_key
        names = master_names(pub)
        want = sorted(planted_key(p, names, bank_account=m.world.bank_account) for p in m.inputs.planted)
        got = sorted(repair_key(r) for r in v.repairs)
        out["gates"]["repair_key_equal"] = bool(v.unique and want == got)
        if v.unique and want != got:
            out["notes"].append(f"repair key mismatch: want {want} got {got}"[:300])
    except ImportError as exc:
        out["gates"]["repair_key_equal"] = False
        out["notes"].append(f"repair key unavailable: {exc}")
    # The golden scores 1.0, complete and renderable, through the real
    # write/commit/finalise loop — over THIS minted object, built with
    # `environment_from_minted`, so no manifest is consulted and no
    # development bypass is invoked to reach the gate.
    try:
        import score_payload as SP
        SP.set_minted(selector_of(namespace, index, profile_name), m)
        gold = SP.golden_delivered()
        ok = gold.get("total") == 1.0 and gold.get("outcome") == "delivered" and bool(gold.get("renderable"))
        out["gates"]["golden_scores_one"] = ok
        if not ok:
            out["notes"].append(f"golden: total {gold.get('total')} outcome {gold.get('outcome')} renderable {gold.get('renderable')}")
    except Exception as exc:                      # noqa: BLE001
        out["gates"]["golden_scores_one"] = False
        out["notes"].append(f"golden: {type(exc).__name__}: {exc}"[:200])
    out["gates"]["id_unique"] = True              # decided across the population below
    return out


def serve_one(job):
    """PHASE 2. One record through the REAL serving door, overrides off.

    `(namespace, index, profile_name, expected public id)` in; a dict with
    `served` and, when it is False, why. The three things checked are the
    three the manifest claims: that `load_environment` admits the selector at
    all, that what it serves carries the public id the record was signed for,
    and that it serves the DEFAULT episode contract — the ceiling the digest
    in a release note refers to.
    """
    namespace, index, profile_name, expected_id = job
    # Development overrides off, inside the worker, where a re-import of this
    # module cannot put them back. `admit` would not reach the development
    # branch anyway once an active manifest exists; removing the flag is what
    # makes "with development overrides disabled" a fact rather than a hope.
    os.environ.pop("PIV_DEV_UNMANIFESTED", None)
    selector = selector_of(namespace, index, profile_name)
    row = {"namespace": namespace, "index": index, "profile": profile_name,
           "selector": selector, "served": False, "note": ""}
    if os.environ.get("PIV_DEV_UNMANIFESTED"):
        row["note"] = "the development override is set in a serving worker"
        return row
    try:
        from beancount_ledger.beancount_ledger import episode_contract_digest, load_environment
        env = load_environment(selector)
    except Exception as exc:                      # noqa: BLE001
        reasons = getattr(exc, "reasons", None)
        row["note"] = f"{type(exc).__name__}: {'; '.join(reasons) if reasons else exc}"[:220]
        return row
    row0 = env.dataset[0]
    served_id = (row0.get("info") or {}).get("task_id") or row0.get("answer")
    if served_id != expected_id:
        row["note"] = f"served public id {served_id!r} is not the record's {expected_id!r}"
        return row
    if env.episode_contract_digest() != episode_contract_digest():
        row["note"] = (f"served episode contract {env.episode_contract_digest()[:16]}… is not the "
                       f"default {episode_contract_digest()[:16]}…")
        return row
    row["served"] = True
    return row


def _map(fn, jobs, workers: int):
    """`fn` over `jobs`, in a pool or in this process (`--workers 0`).

    In-process is what a test uses: `multiprocessing` on Windows re-imports
    the main module in every child, which a test module cannot promise is
    side-effect free.
    """
    if workers and len(jobs) > 1:
        with Pool(workers) as pool:
            return pool.map(fn, jobs, chunksize=4)
    return [fn(job) for job in jobs]


def ledger_census(results: list) -> dict:
    """The measured ledger population beside the envelope it has to fit.

    A gate answers "does every world fit?"; the census answers "by how much,
    and how close is the generator getting?". Without it a
    generator change could consume the whole headroom silently — every gate
    still green, one read suddenly ten times more expensive — and the first
    place anyone would notice is a live rollout's token bill.
    """
    from beancount_ledger.beancount_ledger import LEDGER_ENVELOPE_BYTES, LEDGER_ENVELOPE_LINES
    sizes = [(r["ledger_bytes"], r["ledger_lines"]) for r in results if "ledger_bytes" in r]
    if not sizes:
        return {"count": 0, "envelope_bytes": LEDGER_ENVELOPE_BYTES, "envelope_lines": LEDGER_ENVELOPE_LINES}
    max_bytes = max(b for b, _ in sizes)
    max_lines = max(l for _, l in sizes)
    return {
        "count": len(sizes),
        "max_bytes": max_bytes, "min_bytes": min(b for b, _ in sizes),
        "max_lines": max_lines, "min_lines": min(l for _, l in sizes),
        "envelope_bytes": LEDGER_ENVELOPE_BYTES, "envelope_lines": LEDGER_ENVELOPE_LINES,
        "headroom_bytes": round(LEDGER_ENVELOPE_BYTES / max_bytes, 2) if max_bytes else None,
        "headroom_lines": round(LEDGER_ENVELOPE_LINES / max_lines, 2) if max_lines else None,
    }


def format_census(census: dict) -> str:
    if not census.get("count"):
        return "no ledger measured"
    return (f"{census['count']} ledgers; max {census['max_bytes']} bytes / {census['max_lines']} lines, "
            f"min {census['min_bytes']} / {census['min_lines']}; envelope "
            f"{census['envelope_bytes']} / {census['envelope_lines']} "
            f"(headroom x{census['headroom_bytes']} bytes, x{census['headroom_lines']} lines)")


def preflight(jobs, secret: bytes, out: Path, workers: int = 6) -> dict:
    """Both phases over `jobs`, writing the signed manifest to `out`.

    Returns the whole record of the run: the gate results, the signed records,
    the serving rows and the census. `main` formats it; a test asserts on it.
    """
    from beancount_ledger.graph import manifest as MF
    out = Path(out)

    # ---- phase 1: offline gates on the minted worlds ---------------------
    results = _map(gate_one, list(jobs), workers)
    by_id = Counter(r.get("public_id") for r in results if r.get("public_id"))
    records = []
    for r in results:
        if r.get("public_id") and by_id[r["public_id"]] > 1:
            r["gates"]["id_unique"] = False
            r["notes"].append("public id shared with another selector")
        if r.get("public_id"):
            records.append(MF.record(r["namespace"], r["index"], r["profile"], r["public_id"],
                                     r.get("attempt", 0), r["gates"]))
        else:
            records.append(MF.record(r["namespace"], r["index"], r["profile"], "", 0, r["gates"]))

    # ---- write and sign --------------------------------------------------
    MF.write(records, secret, out)

    # ---- phase 2: every record through the real serving door -------------
    # The workers must see the manifest that was just written, and must not
    # see the development override. Only records that PASSED are put through:
    # a failed record is expected to be refused, so serving it would prove
    # nothing about the door and refusing it would prove nothing either.
    #
    # Phase 2 RE-MINTS every selector, because `load_environment` mints before
    # it admits — that is the point (it proves the manifest admits the world
    # the generator actually produces today), and it roughly doubles the wall
    # clock of a full release preflight. Budget for it.
    previous_manifest = os.environ.get(MF.MANIFEST_ENV)
    previous_phase = os.environ.get(PHASE_ENV)
    previous_dev = os.environ.get(MF.DEV_ENV)
    os.environ[MF.MANIFEST_ENV] = str(out)
    os.environ[PHASE_ENV] = "serve"
    os.environ.pop(MF.DEV_ENV, None)
    try:
        expect_served = [(r["namespace"], r["index"],
                          "hard" if r["profile"].startswith("hard") else "standard", r["public_id"])
                         for r in records if r["passed"]]
        serving = _map(serve_one, expect_served, workers)
    finally:
        if previous_manifest is None:
            os.environ.pop(MF.MANIFEST_ENV, None)
        else:
            os.environ[MF.MANIFEST_ENV] = previous_manifest
        if previous_phase is None:
            os.environ.pop(PHASE_ENV, None)
        else:
            os.environ[PHASE_ENV] = previous_phase
        # The development override is restored for the CALLER (a test suite
        # that set it for its own reasons); phase 2 itself ran without it.
        if previous_dev is not None:
            os.environ[MF.DEV_ENV] = previous_dev

    gate_failed = [r for r in results if not all(r["gates"].values())]
    serve_failed = [r for r in serving if not r["served"]]
    return {
        "results": results, "records": records, "serving": serving,
        "gate_failed": gate_failed, "serve_failed": serve_failed,
        "passed": [r for r in records if r["passed"]],
        "gate_fail_counts": Counter(g for r in results for g, ok in r["gates"].items() if not ok),
        "attempts": Counter(r.get("attempt") for r in results if "attempt" in r),
        "census": ledger_census(results), "manifest": out,
        "ok": not gate_failed and not serve_failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=int, default=2000)
    parser.add_argument("--eval", type=int, default=500)
    parser.add_argument("--hard", type=int, default=500)
    parser.add_argument("--out", default=None, help="manifest path (default PIV_MANIFEST or ~/.piv/manifest.json)")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    from beancount_ledger.graph import manifest as MF
    from beancount_ledger.graph.mint import evaluator_secret
    secret = evaluator_secret()
    if secret is None:
        print("no evaluator secret configured; nothing to preflight")
        return 2
    rotation = MF.provision_rotation_id()          # opaque, beside the secret; never derived from it
    jobs = [("train", i, "standard") for i in range(args.train)] + \
           [("eval", i, "standard") for i in range(args.eval)] + \
           [("train", i, "hard") for i in range(args.hard)]
    out = Path(args.out) if args.out else MF.manifest_path()
    t0 = time.time()
    run = preflight(jobs, secret, out, args.workers)

    print(f"{len(jobs)} selectors preflighted under rotation {rotation[:8]}… in {time.time() - t0:.0f}s; "
          f"versions {MF.versions()}")
    print(f"PHASE 1 offline gates: passed {len(run['passed'])}/{len(jobs)}; "
          f"gate failures {dict(run['gate_fail_counts'])}; attempts {sorted(run['attempts'].items())}")
    print("ledger census: " + format_census(run["census"]))
    for r in run["gate_failed"][:12]:
        print(f"   GATE FAILED {r['namespace']}:{r['index']}:{r['profile']} "
              f"{[g for g, ok in r['gates'].items() if not ok]} {' | '.join(r['notes'])[:220]}")
    print(f"PHASE 2 serving door (signed manifest, development overrides off): "
          f"{len(run['serving']) - len(run['serve_failed'])}/{len(run['serving'])} records admitted "
          f"with the record's public id and the default episode contract")
    for r in run["serve_failed"][:12]:
        print(f"   NOT SERVED {r['selector']}: {r['note']}")
    census_path = out.with_name(out.stem + "_census.json")
    census_path.write_text(json.dumps(run["census"], indent=1, sort_keys=True), encoding="utf-8")
    print(f"manifest written: {out} (serves {len(run['passed'])} selectors); census {census_path}")
    return 0 if run["ok"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
