"""WA-1b pilot runner: the control ceiling gate and the paired arms, with a sidecar.

Design (Codex rounds 3-5, astra brief 2), all of it enforced here rather than
remembered:

  pilot identity   every row carries "wa1/pilot-1", the episode contract digest
                   it ran under, the per-turn cap, the ceiling and the route, so
                   a row can be refused from a pool on its contents.
  serving          the arms are ContractInputs rebuilt deterministically from
                   the pool row (world, task, target, wrong, strategy, parameter)
                   and served through `environment_from_inputs` behind a shim on
                   `load_environment`, so `budget_calibration.run_one` needs no
                   change. The shipped contract-3 prompt is used: the pilot no
                   longer needs an override because the contradiction it was
                   meant to paper over is gone.
  --gate           the ten CONTROL arms alone, N replicates each. Pass needs
                   >= 18/20 globally complete AND >= 19/20 selected item
                   RESOLVED (Codex round 5 §5). These runs are never reused as
                   paired controls: they are not adjacent to a treatment.
  --paired         fresh adjacent pairs: control and treatment of one case run
                   back to back, order randomised per pair from a fixed seed,
                   no unrelated episode between them. A provider failure in
                   either arm invalidates the pair; both are rerun, never one.
  sidecar          the production runner archives total/verdict/complete only.
                   After every episode this reads the final ledger from the
                   episode's workspace (it outlives the rollout), hashes it,
                   rescores it through the real chain with the arm's own
                   contract, and archives item_states, unresolved_planted,
                   blocked_by and the selected item's state. The reward the
                   environment returned is checked against the rescored total.
  no substitution  a missing arm is a missing arm. The subject is one model on
                   one route for the whole pilot.

    python wa1b_run.py --gate   --model ... --base-url ... --key-var ... --replicates 2 --jsonl out.jsonl
    python wa1b_run.py --paired --model ... --base-url ... --key-var ... --replicates 2 --jsonl out.jsonl
                       [--cases 10] [--pool relaxed|strict] [--adjudication FILE]
"""
import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path
from types import SimpleNamespace

SCRATCH = r"C:/Users/gulte/AppData/Local/Temp/claude/C--Users-gulte-Desktop-PIV/e5af9fd8-5589-401a-8521-18264e0703e0/scratchpad"
sys.path.insert(0, SCRATCH)
sys.path.insert(0, r"C:/Users/gulte/Desktop/PIV/beancount-ledger-workflows")

from beancount_ledger import beancount_ledger as env_mod   # noqa: E402
from beancount_ledger.candidate import committed as K      # noqa: E402
from beancount_ledger.graph.worlds import WORLD_MODULES    # noqa: E402
import tests.budget_calibration as bc                     # noqa: E402
from wa1_build import build_pair, score                    # noqa: E402

PILOT_ID = "wa1/pilot-1"
# astra round 9 §1: the frozen screen. (world, rec) pairs index the adjudicated pool.
SCREEN = {
    "qwen3.7-max":       (("bluewater-2025-10", "rec:pi-7752-payment"), ("maple-2025-12", "rec:pi-5131-payment")),
    "deepseek-v4-flash": (("bluewater-2025-10", "rec:pi-7752-payment"), ("hawthorn-2025-12", "rec:pi-7745-payment")),
    "glm-5.2":           (("falcon-2026-02", "rec:pi-3309-payment"), ("hawthorn-2025-12", "rec:pi-7745-payment")),
    "kimi-k3":           (("falcon-2026-02", "rec:pi-3309-payment"), ("maple-2025-12", "rec:pi-5131-payment")),
}
SCREEN_ID = "wa1b/screen-1"
WA_ID = "misbooked_supplier_payment"
SEED = 20260908


def rebuild_pair(row, prompt):
    module = next(m for m in WORLD_MODULES if m.WORLD.id == row["world"])
    world, task = module.WORLD, module.TASKS[row["task"]]
    if row["target_mode"] == "replaced":
        shared = tuple(mu for mu in task.plan.mutations if mu.recognition_id != row["rec"])
    else:
        shared = tuple(task.plan.mutations)
    C, T, rep = build_pair(world, f"wa1b_{world.id}_{row['rec'].split(':', 1)[1]}", prompt, task.period,
                           shared, row["rec"], row["wrong"], control_strategy=row["strategy"],
                           control_parameter=row["parameter"], claim="wa1b")
    return C, T, rep


def install_shim(arms: dict):
    """Serve the pilot arms by task id through load_environment; pass everything else through."""
    original = env_mod.load_environment

    def shim(task_id="bank_recon_001", **kw):
        if task_id in arms:
            return env_mod.environment_from_inputs(arms[task_id], **kw)
        return original(task_id, **kw)
    env_mod.load_environment = shim
    return original


def sidecar(inputs, out: dict) -> dict:
    """Rescore the episode's final ledger through the real chain; archive the item states."""
    result = {"final_ledger_sha256": None, "rescored_total": None, "reward_matches_rescore": None,
              "item_states": None, "unresolved_planted": None, "blocked_by": None,
              "selected_item_state": None, "complete": None, "sidecar_error": None}
    workspace = out.get("workspace")
    try:
        text = (Path(workspace) / "ledger.beancount").read_text(encoding="utf-8") if workspace else None
        if text is None:
            result["sidecar_error"] = "no workspace on the rollout"
            return result
        result["final_ledger_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        outcome, refusal = score(text, K.load_contract(inputs))
        if outcome is None:
            result["sidecar_error"] = f"not renderable: {type(refusal).__name__}"
            result["rescored_total"] = 0.0
        else:
            result["rescored_total"] = float(outcome.total)
            result["item_states"] = [(i, str(s)) for i, s in outcome.allocation.item_states]
            result["unresolved_planted"] = list(getattr(outcome, "unresolved_planted", ()) or ())
            result["blocked_by"] = list(getattr(outcome, "blocked_by", ()) or ())
            result["complete"] = bool(getattr(outcome, "complete", False))
            result["selected_item_state"] = next((str(s) for i, s in outcome.allocation.item_states if i == WA_ID), None)
        reward = out.get("reward")
        if reward is not None and result["rescored_total"] is not None:
            result["reward_matches_rescore"] = abs(float(reward) - result["rescored_total"]) < 1e-9
    except Exception as exc:                                             # noqa: BLE001
        result["sidecar_error"] = f"{type(exc).__name__}: {exc}"[:200]
    return result


def config_key(args) -> str:
    """The configuration a row must match to count towards resume: the same model on
    the same route under the same contract and caps. Anything else is another arm."""
    return "|".join(str(x) for x in (args.model, args.base_url, env_mod.episode_contract_digest(args.tokens),
                                      args.max_tokens, args.tokens, args.turns))


def row_ok(row: dict) -> bool:
    """A row counts only if the provider answered, the sidecar rescored the final ledger,
    and the reward the environment returned equals the rescore. Anything else is a hole
    in the record, not a data point, and resume must not skip over it."""
    return (not row.get("provider_failure") and row.get("sidecar_error") is None
            and row.get("reward_matches_rescore") is True)


def run_episode(task_id, inputs, args):
    cell = SimpleNamespace(model=args.model, base_url=args.base_url, key_var=args.key_var, turns=args.turns,
                           tokens=args.tokens, max_tokens=args.max_tokens, timeout=args.timeout,
                           production=False, tool_schema_fix=False)
    row = bc.run_one(task_id, cell)
    row["pilot"] = SCREEN_ID if getattr(args, "screen", None) else PILOT_ID
    # a free quota that has run out ends this subject exactly as a retired route does:
    # the missing cells stay missing, nothing is filled from another model
    q = str(row.get("quarantined") or row.get("crashed") or "")
    if "403" in q and "quota" in q.lower():
        row["retired"] = True
        row["retired_reason"] = "free quota exhausted"
    row["config_key"] = config_key(args)
    row["episode_contract_digest"] = env_mod.episode_contract_digest(args.tokens)
    row["episode_contract_version"] = env_mod.EPISODE_CONTRACT_VERSION
    row["route"] = args.base_url
    provider_failure = bool(row.get("quarantined") or row.get("crashed"))
    row["provider_failure"] = provider_failure
    if not provider_failure:
        row.update(sidecar(inputs, row))
    row["row_valid"] = row_ok(row)
    return row


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--gate", action="store_true")
    mode.add_argument("--paired", action="store_true")
    mode.add_argument("--screen", metavar="SUBJECT", choices=sorted(SCREEN),
                      help="astra round 9: run this subject's two frozen pairs (must equal --model)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--key-var", required=True)
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--cases", type=int, default=10)
    ap.add_argument("--pool", default="relaxed")
    ap.add_argument("--adjudication", type=Path, default=None,
                    help="jsonl from wa1b_adjudicate.py; only cases with case_pass are eligible")
    ap.add_argument("--turns", type=int, default=env_mod.MAX_TURNS)
    ap.add_argument("--tokens", type=int, default=env_mod.MAX_EPISODE_OUTPUT_TOKENS)
    ap.add_argument("--max-tokens", type=int, default=40_000,
                    help="per-turn cap; 40k = no restriction beyond the episode ceiling (astra brief 2, Q2)")
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--pace", type=float, default=8.0)
    ap.add_argument("--jsonl", type=Path, required=True)
    ap.add_argument("--resume", action="store_true",
                    help="skip (case, replicate, arm) rows already in --jsonl that were not provider failures")
    args = ap.parse_args()

    if not bc.os.environ.get(args.key_var):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                bc.os.environ[args.key_var] = winreg.QueryValueEx(h, args.key_var)[0]
        except OSError:
            pass
    if not bc.os.environ.get(args.key_var):
        print(f"{args.key_var} is not set", file=sys.stderr)
        return 2
    bc.env_mod.MAX_TURNS = args.turns

    pool_file = Path(SCRATCH) / ("wa1b_pool_relaxed.json" if args.pool == "relaxed" else "wa1b_pool.json")
    d = json.loads(pool_file.read_text(encoding="utf-8"))
    pool = d["pool"]
    if args.adjudication:
        passed = {json.loads(l)["case"] for l in args.adjudication.read_text(encoding="utf-8").splitlines()
                  if l.strip() and json.loads(l)["case_pass"]}
        pool = [r for r in pool if f"wa1b_{r['world']}_{r['rec'].split(':', 1)[1]}" in passed]
        print(f"{len(passed)} cases passed adjudication; {len(pool)} of the pool are eligible", flush=True)
    if args.screen:
        if args.screen != args.model:
            print(f"--screen {args.screen} must equal --model {args.model}", file=sys.stderr)
            return 2
        wanted = SCREEN[args.screen]
        by_key = {(r["world"], r["rec"]): r for r in d["pool"]}
        missing = [k for k in wanted if k not in by_key]
        if missing:
            print(f"screen cases not in the pool: {missing}", file=sys.stderr)
            return 2
        pool = [by_key[k] for k in wanted]
        if args.adjudication:
            not_passed = [k for k in wanted if f"wa1b_{k[0]}_{k[1].split(':', 1)[1]}" not in passed]
            if not_passed:
                print(f"screen cases that did not pass adjudication: {not_passed}", file=sys.stderr)
                return 2
        args.cases = len(pool)
        args.replicates = 1
    pool = pool[:args.cases]
    if len(pool) < args.cases:
        print(f"only {len(pool)} eligible cases; the design wants {args.cases}. Refusing to run short.",
              file=sys.stderr)
        return 3

    arms, meta = {}, {}
    for row in pool:
        C, T, rep = rebuild_pair(row, d["prompt"])
        arms[C.task_id], arms[T.task_id] = C, T
        meta[rep["case"]] = dict(row=row, rep=rep, control=C.task_id, treatment=T.task_id)
    install_shim(arms)

    schedule = []
    if args.gate:
        for replicate in range(1, args.replicates + 1):
            for case, m in meta.items():
                schedule.append((case, replicate, "control", m["control"]))
    elif args.screen:
        # the two pairs of a subject take opposite arm orders; which one is control-first
        # comes from the recorded seed, so the schedule is reproducible and pre-committed
        cases = list(meta.items())
        first_control_first = random.Random(f"{SEED}:{SCREEN_ID}:{args.screen}").random() < 0.5
        for i, (case, m) in enumerate(cases):
            control_first = first_control_first if i == 0 else not first_control_first
            order = [("control", m["control"]), ("treatment", m["treatment"])]
            if not control_first:
                order.reverse()
            schedule.append((case, 1, order))
    else:
        for replicate in range(1, args.replicates + 1):
            for case, m in meta.items():
                order = [("control", m["control"]), ("treatment", m["treatment"])]
                random.Random(f"{SEED}:{case}:{replicate}").shuffle(order)
                schedule.append((case, replicate, order))

    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.resume and args.jsonl.exists():
        for line in args.jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("record") == "pair":
                    if r.get("pair_valid") and r.get("config_key") == config_key(args):
                        for arm in ("control", "treatment"):
                            done.add((r["case"], r["replicate"], arm))
                    continue
                if r.get("row_valid") and args.gate and r.get("config_key") == config_key(args):
                    done.add((r["case"], r["replicate"], r["arm"]))
        if args.gate:
            schedule = [s for s in schedule if (s[0], s[1], s[2]) not in done]
        else:
            schedule = [s for s in schedule if not all((s[0], s[1], a) in done for a, _ in s[2])]
        print(f"resume: {len(done)} rows already archived, {len(schedule)} left", flush=True)
    started = time.time()
    label = ("GATE (controls only)" if args.gate else
             f"SCREEN {SCREEN_ID} subject={args.screen}" if args.screen else "PAIRED (adjacent, randomised)")
    print(f"{label}: {len(pool)} cases x {args.replicates} replicates on {args.model}; "
          f"cap {args.max_tokens}/{args.tokens}, contract v{env_mod.EPISODE_CONTRACT_VERSION} "
          f"{env_mod.episode_contract_digest(args.tokens)[:12]}", flush=True)
    with args.jsonl.open("a", encoding="utf-8") as sink:
        if args.gate:
            for n, (case, replicate, arm, task_id) in enumerate(schedule, 1):
                row = run_episode(task_id, arms[task_id], args)
                row.update(case=case, replicate=replicate, arm=arm, wrong=meta[case]["row"]["wrong"],
                           stratum_sibling=meta[case]["row"]["stratum_sibling"], target_mode=meta[case]["row"]["target_mode"])
                sink.write(json.dumps(row, default=str) + "\n"); sink.flush()
                print(f"  [{n:2d}/{len(schedule)}] {case:<40} r{replicate} {arm:<9} reward={row.get('reward')} "
                      f"complete={row.get('complete')} item={row.get('selected_item_state')} "
                      f"{'PROVIDER-FAIL' if row['provider_failure'] else ''}", flush=True)
                if row.get("retired"):
                    print(f"SUBJECT STOPPED: {args.model} on {args.base_url} — {row.get('retired_reason') or 'route retired (definitive 404)'}; missing cells stay missing.", flush=True)
                    return 3
                time.sleep(args.pace)
        else:
            for n, (case, replicate, order) in enumerate(schedule, 1):
                pair_id = f"{case}#r{replicate}"
                results = []
                retired = False
                for arm, task_id in order:
                    row = run_episode(task_id, arms[task_id], args)
                    row.update(case=case, replicate=replicate, arm=arm, pair_id=pair_id,
                               pair_order=[a for a, _ in order], wrong=meta[case]["row"]["wrong"],
                               stratum_sibling=meta[case]["row"]["stratum_sibling"],
                               target_mode=meta[case]["row"]["target_mode"])
                    results.append(row)
                    # persist the arm the moment it finishes; a crash between arms loses nothing
                    sink.write(json.dumps(row, default=str) + "\n"); sink.flush()
                    if row.get("retired"):
                        retired = True
                        break
                    time.sleep(args.pace)
                pair_valid = (len(results) == 2) and all(row_ok(r) for r in results)
                sink.write(json.dumps({"record": "pair", "pair_id": pair_id, "case": case, "replicate": replicate,
                                       "pair_valid": pair_valid, "config_key": config_key(args),
                                       "arms": [r["arm"] for r in results],
                                       "rewards": [r.get("reward") for r in results],
                                       "selected_item_states": [r.get("selected_item_state") for r in results]},
                                      default=str) + "\n"); sink.flush()
                if retired:
                    print(f"SUBJECT STOPPED: {args.model} on {args.base_url} — {row.get('retired_reason') or 'route retired (definitive 404)'}; missing cells stay missing.", flush=True)
                    return 3
                summary = " | ".join(f"{r['arm'][:4]}={r.get('reward')}/{r.get('selected_item_state')}" for r in results)
                print(f"  [{n:2d}/{len(schedule)}] {pair_id:<44} {summary} {'' if pair_valid else 'PAIR-INVALID'}", flush=True)
    print(f"\n{len(schedule)} {'episodes' if args.gate else 'pairs'} in {(time.time() - started) / 60:.0f} min -> {args.jsonl}")
    if args.screen:
        recs = [json.loads(l) for l in args.jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
        pairs = [r for r in recs if r.get("record") == "pair" and r.get("config_key") == config_key(args)]
        done = [p for p in pairs if p.get("pair_valid")]
        print(f"SCREEN {args.screen}: {len(done)}/{len(SCREEN[args.screen])} complete pairs")
        for p in pairs:
            print(f"  {p['case']:<44} arms={p['arms']} rewards={p['rewards']} item={p['selected_item_states']} "
                  f"{'OK' if p.get('pair_valid') else 'INCOMPLETE'}")
        return 0 if len(done) == len(SCREEN[args.screen]) else 2
    if args.gate:
        rows = [json.loads(l) for l in args.jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
        valid = [r for r in rows if r.get("row_valid")]
        complete = sum(1 for r in valid if r.get("complete"))
        resolved = sum(1 for r in valid if r.get("selected_item_state") == "RESOLVED")
        need = len(meta) * args.replicates
        if len(valid) < need:
            print(f"GATE INCOMPLETE/UNAVAILABLE: valid {len(valid)}/{need} scored episodes; this is a missing "
                  f"measurement, not a failed gate (complete {complete}, RESOLVED {resolved} among the valid).")
            return 2
        verdict = "PASS" if (complete >= 18 and resolved >= 19) else "FAIL"
        print(f"GATE {verdict}: valid {len(valid)}/{need}, complete {complete}/{len(valid)}, "
              f"selected item RESOLVED {resolved}/{len(valid)} (needs >=18 complete and >=19 resolved of 20)")
        return 0 if verdict == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
