"""The nightly sweep: mint thousands of keyed seeds and report the population.

    python tests/sweep_generated.py [standard_train] [eval] [hard] [--sentinel N] [--tie-break]     (default 1500 300 300, N=24)

Per seed: generation error, literal provenance leak, which bounded layout
attempt produced the world, planted count and kind mix, statement rows,
public-only identifiability (`graph/identify`) and whether its repairs are
exactly the planted items under the FULL shared repair key (`identify.repair_key`
against `tests/repair_keys.planted_key`: kind, date, posting multiset,
counterparty, booked amount, copies), task-id distinctness.
Failing seeds are written to reviews/sweep_failures.json so they can be
pinned as regression fixtures. A sentinel subset (the first N selectors)
is re-minted in a fresh interpreter under a different PYTHONHASHSEED and
must reproduce the same public bytes (cross-process determinism, nightly). Not part of run_all: it takes a minute and
needs the evaluator secret (PIV_EVAL_SECRET or ~/.piv/eval_secret).
Exit code 1 on any failure.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")     # development: a test secret has no release manifest


def public_sha(m) -> str:
    h = hashlib.sha256()
    for name, data in m.inputs.public_files:
        h.update(name.encode("utf-8") + b"\0" + data + b"\0")
    h.update(m.inputs.prompt.encode("utf-8"))
    return h.hexdigest()


SENTINEL_SCRIPT = """
import json, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[1] + "/tests")
from sweep_generated import public_sha
from beancount_ledger.graph.mint import mint
from beancount_ledger.graph.generate import DEFAULT_PROFILE, HARD_PROFILE
out = {}
for sel in json.loads(sys.argv[2]):
    ns, idx, prof = sel.split(":")
    m = mint(ns, int(idx), HARD_PROFILE if prof == "hard" else DEFAULT_PROFILE)
    out[sel] = [m.inputs.task_id, public_sha(m)]
print(json.dumps(out))
"""


def sentinel_check(results, count):
    """Re-mint the first `count` selectors in a fresh interpreter under
    another PYTHONHASHSEED; every task id and public digest must agree."""
    chosen = [r for r in results if "public_sha" in r][:count]
    if not chosen:
        return []
    env = dict(os.environ, PYTHONHASHSEED=str(int.from_bytes(os.urandom(2), "big")))
    proc = subprocess.run([sys.executable, "-c", SENTINEL_SCRIPT, str(ROOT), json.dumps([r["sel"] for r in chosen])],
                          capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(ROOT))
    if proc.returncode != 0:
        return [{"sel": "sentinel", "error": "fresh interpreter failed: " + proc.stderr[-400:]}]
    line = [l for l in proc.stdout.splitlines() if l.startswith("{")][-1]
    other = json.loads(line)
    problems = []
    for r in chosen:
        tid, sha = other.get(r["sel"], [None, None])
        if tid != r["task_id"] or sha != r["public_sha"]:
            problems.append({"sel": r["sel"], "error": f"cross-process disagreement under PYTHONHASHSEED={env['PYTHONHASHSEED']}"})
    return problems


def one(job):
    namespace, index, profile_name, tie_break = job
    from beancount_ledger.graph.mint import mint, literal_provenance_leaks
    from beancount_ledger.graph.generate import DEFAULT_PROFILE, HARD_PROFILE
    from beancount_ledger.graph import identify as ID
    profile = HARD_PROFILE if profile_name == "hard" else DEFAULT_PROFILE
    out = {"sel": f"{namespace}:{index}:{profile_name}"}
    try:
        m = mint(namespace, index, profile)
    except Exception as exc:                      # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"[:300]
        return out
    out["task_id"] = m.inputs.task_id
    out["public_sha"] = public_sha(m)
    out["attempt"] = m.provenance.attempt
    out["leaks"] = literal_provenance_leaks(m)
    out["planted"] = len(m.inputs.planted)
    out["kinds"] = "+".join(sorted(p.kind for p in m.inputs.planted))
    pub = {n: d.decode("utf-8") for n, d in m.inputs.public_files}
    out["rows"] = pub["bank_statement.csv"].count("\n") - 1
    try:
        # tie_break is a diagnostic prior (Codex T42 §5); production and the
        # mint-time gate run without it, so the default sweep does too.
        v = ID.check_identifiable(pub, bank_account=m.world.bank_account, period_start=m.task.period.start,
                                  period_end=m.task.period.end, tie_break=tie_break)
        out["unique"] = bool(v.unique)
        out["readings"] = getattr(v, "readings", None)
        out["ambiguities"] = [a[:200] for a in v.ambiguities][:3]
        # The FULL shared repair key (Codex T42 §3), not (kind, amount):
        # date, posting multiset, counterparty, booked amount and copies all
        # enter, so a checker that found the right kind for the right money
        # on the wrong day or against the wrong account is a mismatch here.
        from repair_keys import master_names, planted_key
        names = master_names(pub)
        want = sorted(planted_key(p, names, bank_account=m.world.bank_account) for p in m.inputs.planted)
        got = sorted(ID.repair_key(r) for r in v.repairs)
        out["repairs_match"] = want == got
        if want != got:
            out["want"] = [str(k) for k in want if k not in got]
            out["got"] = [str(k) for k in got if k not in want]
    except Exception as exc:                      # noqa: BLE001
        out["ident_error"] = f"{type(exc).__name__}: {exc}"[:300]
    return out


def main():
    argv = list(sys.argv[1:])
    sentinel = 24
    tie_break = False
    if "--tie-break" in argv:                # diagnostic: rank ambiguous worlds under the day-and-wording prior
        tie_break = True
        argv.remove("--tie-break")
    if "--sentinel" in argv:
        at = argv.index("--sentinel")
        sentinel = int(argv[at + 1])
        del argv[at:at + 2]
    n_std = int(argv[0]) if len(argv) > 0 else 1500
    n_eval = int(argv[1]) if len(argv) > 1 else 300
    n_hard = int(argv[2]) if len(argv) > 2 else 300
    jobs = [("train", i, "standard", tie_break) for i in range(n_std)] + \
           [("eval", i, "standard", tie_break) for i in range(n_eval)] + \
           [("train", i, "hard", tie_break) for i in range(n_hard)]
    t0 = time.time()
    with Pool(8) as pool:
        results = pool.map(one, jobs, chunksize=8)
    dt = time.time() - t0
    errors = [r for r in results if "error" in r]
    sentinel_problems = sentinel_check(results, sentinel)
    errors += sentinel_problems
    ident_err = [r for r in results if "ident_error" in r]
    leaks = [r for r in results if r.get("leaks")]
    ambiguous = [r for r in results if "unique" in r and not r["unique"]]
    mismatch = [r for r in results if r.get("unique") and not r.get("repairs_match")]
    ids = [r["task_id"] for r in results if "task_id" in r]
    by_id = {}
    for r in results:
        if "task_id" in r:
            by_id.setdefault(r["task_id"], []).append(r["sel"])
    collisions = [{"task_id": k, "selectors": v, "collision": True} for k, v in by_id.items() if len(v) > 1]
    attempts = Counter(r.get("attempt") for r in results if "attempt" in r)
    kinds = Counter(r.get("kinds") for r in results if "kinds" in r)
    planted = Counter((r["sel"].split(":")[2], r["planted"]) for r in results if "planted" in r)
    rows = Counter((r["sel"].split(":")[2], r["rows"]) for r in results if "rows" in r)
    print(f"{len(jobs)} seeds in {dt:.0f}s")
    print(f"errors {len(errors)}  ident_errors {len(ident_err)}  literal leaks {len(leaks)}  "
          f"ambiguous {len(ambiguous)}  unique-but-wrong-repairs {len(mismatch)}")
    print(f"distinct task ids {len(set(ids))}/{len(ids)}")
    print(f"sentinel: {min(sentinel, len(ids))} selectors re-minted in a fresh interpreter under another PYTHONHASHSEED: "
          f"{'all identical' if not sentinel_problems else str(len(sentinel_problems)) + ' DISAGREE'}")
    for c in collisions:
        print("   COLLISION", c["task_id"], c["selectors"])
    print("attempts:", sorted(attempts.items()))
    readings = Counter(r.get("readings") for r in results if "readings" in r)
    print("readings per selector:", sorted(readings.items(), key=lambda kv: (kv[0] is None, kv[0])),
          "  [diagnostic prior on]" if tie_break else "")
    print("kind mixes:", sorted(kinds.items(), key=lambda kv: -kv[1]))
    print("planted:", sorted(planted.items()))
    std_rows = sorted(v for (p, v) in rows.elements() if p == "standard")
    hard_rows = sorted(v for (p, v) in rows.elements() if p == "hard")
    if std_rows:
        print(f"standard rows: min {std_rows[0]} median {std_rows[len(std_rows)//2]} max {std_rows[-1]}")
    if hard_rows:
        print(f"hard rows: min {hard_rows[0]} median {hard_rows[len(hard_rows)//2]} max {hard_rows[-1]}")
    for r in (errors + ident_err + leaks + ambiguous + mismatch)[:12]:
        print("  ", json.dumps(r)[:400])
    failures = errors + ident_err + leaks + ambiguous + mismatch + collisions
    out_dir = ROOT / "reviews"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "sweep_failures.json", "w", encoding="utf-8") as fh:
        json.dump(failures, fh, indent=1)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
