"""Mint, validate and sign the cash-application DEVELOPMENT population.

    python tests/preflight_cash_population.py [--groups N] [--out PATH] [--record DIR]

Round 16, decision 5, before any model call:

    Freeze the generator, profile, catalogue, admission contract and runtime.
    Predeclare 96 development parent groups, 32 per mechanism stratum, and
    retain their complete minting census. Complete offline validation and
    signed-manifest serving checks.

Everything here is OFFLINE AND DETERMINISTIC. It makes no provider call, reads
no model output and consults no score. `cash_gate.mint_group`'s docstring is
the rule it runs under, and there is nothing in this file that could break it:
the population is a declaration in `graph/cash_population.py`, the attempt
order is the frozen construction's, and acceptance is the thirty-one declared
gates.

TWO PHASES, TWO CLAIMS — the shape `tests/preflight_manifest.py` established
for the bank family, for the same reason:

    PHASE 1 — offline validation.  Mint every declared group through
        `cash_gate.mint_population`, against ONE population ledger so that the
        two population gates see the whole population, and then validate each
        admitted group's two variants on the artifacts themselves, with no
        manifest anywhere in the picture: every phase-C gate passed; the
        public fold reproduces the private truth; the identifiability checker
        finds one reading; the golden ledger scores 1.0 and completes through
        the actual frozen `candidate/1`; the golden register scores 1.0
        through `application/1`; the composite is 1.0 and complete; and no
        private construction token reaches a public surface.

    PHASE 2 — serving verification.  AFTER the family manifest is written and
        signed, call the real `beancount_ledger.load_environment` for EVERY
        signed record and require that it serves: the served public id is the
        record's, the episode profile is `cash_application`, and the served
        episode-contract digest equals the one an AUTHORED cash-application
        task serves under. That last comparison is the phase's actual claim —
        "an instance must serve from the manifest exactly as the authored
        tasks do" — and it is made against `cash_application_001` itself
        rather than against a literal, so a contract change moves both sides.

WHAT A PASS HERE ESTABLISHES, AND WHAT IT DOES NOT. It establishes that the
generator produces admissible fresh instances and that they serve. It does not
establish that they are hard, that they are useful for training, or that any
model has been measured on them. No model has been called at this point, and
decision 5 puts the first measurement behind its own frozen rule.

THE CENSUS IS EVALUATOR-SIDE. `--record DIR` writes the complete minting
census, the aggregates and the freeze under `DIR`. The census binds enumerable
selectors to public-content digests, so it belongs beside the manifest and the
review note, never in an agent's workspace.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

#: The authored task every served instance is compared against. It is one of
#: the eleven public demonstrations, which decision 2 keeps entirely outside
#: this population — which is exactly what makes it the right reference: it
#: shares the family's episode contract and nothing else.
AUTHORED_REFERENCE = "cash_application_001"

#: The offline validation gates, in the order they are evaluated. Named here
#: so a row with a missing gate is visibly missing rather than quietly absent.
VALIDATION_GATES = (
    "gates_pass",
    "public_fold_reproduces_truth",
    "identifiable_one_reading",
    "golden_ledger_scores_one",
    "golden_register_scores_one",
    "composite_complete",
    "no_provenance_leak",
)


def validate_variant(minted, variant: str, secret: bytes) -> dict:
    """PHASE 1 for one variant: every gate in `VALIDATION_GATES`, measured
    rather than asserted.

    The scores are RECORDED, not just compared: a row that says
    `ledger_total 1` is a row a later reader can check against the engine
    version it was taken under, and a row that says `True` is not.
    """
    from beancount_ledger.candidate import application as APP
    from beancount_ledger.candidate import committed as K
    from beancount_ledger.candidate import composite as X
    from beancount_ledger.graph import cash_admit as ADMIT
    from beancount_ledger.graph import cash_application as CA
    from beancount_ledger.graph import cash_population as CP
    from beancount_ledger.graph import identify as ID
    from beancount_ledger.graph.cash_identity import identity_leaks, parent_seed

    ident = minted.pair.identity
    member = minted.pair.variant(variant)
    inputs = member.inputs
    row = {
        "group": ident.label(),
        "identity_digest": ident.digest(),
        "family": ident.template_family,
        "mechanism": minted.pair.mechanism,
        "split": ident.split,
        "variant": variant,
        "selector": CP.selector_of(ident, variant),
        "public_id": member.task.id,
        "content_digest": CP.content_digest_of(member),
        "attempt": minted.pair.attempt,
        "measurement": member.measurement.view(),
        "gates": {},
        "notes": [],
    }

    row["gates"]["gates_pass"] = bool(minted.report.passed)
    if not minted.report.passed:
        row["notes"].append(f"phase-C gates: {minted.report.witness()}"[:300])

    # The public fold, over the bytes the agent is served, against the private
    # truth register. `_render` already refuses a variant where these two
    # disagree; running it again here is the point of an independent
    # validation pass — a check that only ever runs inside the thing it
    # checks is a property of that thing.
    try:
        application = CA.fold(member.public_files, **{
            "bank_account": member.world.bank_account,
            "period_start": member.task.period.start,
            "period_end": member.task.period.end})
        row["gates"]["public_fold_reproduces_truth"] = (
            CA.application_key(application) == inputs.application.application_key())
    except Exception as exc:                       # noqa: BLE001
        row["gates"]["public_fold_reproduces_truth"] = False
        row["notes"].append(f"public fold: {type(exc).__name__}: {exc}"[:200])

    try:
        verdict = ID.check_identifiable(member.public_files, bank_account=member.world.bank_account,
                                        period_start=member.task.period.start,
                                        period_end=member.task.period.end)
        row["gates"]["identifiable_one_reading"] = bool(verdict.unique)
        row["readings"] = getattr(verdict, "readings", None)
        if not verdict.unique:
            row["notes"].append(f"identifiability: {verdict.reason}"[:200])
    except Exception as exc:                       # noqa: BLE001
        row["gates"]["identifiable_one_reading"] = False
        row["notes"].append(f"identifiability: {type(exc).__name__}: {exc}"[:200])

    # Both goldens through the ACTUAL frozen engines, and the composite over
    # them. `cash_admit.score_ledger` is the production path spelled once —
    # `parse_once(logical_text(raw))`, `commit`, `score_committed` — so this
    # is the scorer the episode runs, not a re-implementation of it.
    try:
        env = K.load_contract(inputs)
        ledger, failure = ADMIT.score_ledger(inputs.golden_text, env)
        if failure:
            row["gates"]["golden_ledger_scores_one"] = False
            row["gates"]["golden_register_scores_one"] = False
            row["gates"]["composite_complete"] = False
            row["notes"].append(f"golden ledger: {failure}"[:200])
        else:
            problems, _ = ADMIT.golden_ledger_problems(inputs, env)
            row["ledger_total"] = str(ledger.total)
            row["ledger_complete"] = bool(ledger.complete)
            row["gates"]["golden_ledger_scores_one"] = not problems
            row["notes"] += [p[:200] for p in problems]
            parsed = APP.parse_application(member.golden_register, inputs.application)
            if not isinstance(parsed, APP.ParsedApplication):
                row["gates"]["golden_register_scores_one"] = False
                row["gates"]["composite_complete"] = False
                row["notes"].append(f"golden register refused at the parse boundary: {parsed}"[:200])
            else:
                outcome = APP.score_application(parsed, inputs.application,
                                                expected_balances=env.expected_balances)
                row["register_total"] = str(outcome.total)
                row["register_penalties"] = list(outcome.penalties)
                row["gates"]["golden_register_scores_one"] = (outcome.total == 1 and not outcome.penalties)
                composite = X.compose(ledger, outcome)
                row["composite_total"] = str(composite.total)
                row["composite_complete"] = bool(composite.complete)
                row["gates"]["composite_complete"] = (composite.total == 1 and composite.complete)
    except Exception as exc:                       # noqa: BLE001
        for gate in ("golden_ledger_scores_one", "golden_register_scores_one", "composite_complete"):
            row["gates"].setdefault(gate, False)
        row["notes"].append(f"scoring: {type(exc).__name__}: {exc}"[:200])

    leaks = identity_leaks(CP.serving_surfaces(variant, member), ident, parent_seed(ident, secret))
    row["gates"]["no_provenance_leak"] = not leaks
    row["notes"] += [leak[:200] for leak in leaks]

    for gate in VALIDATION_GATES:
        row["gates"].setdefault(gate, False)
    row["passed"] = all(row["gates"][gate] for gate in VALIDATION_GATES)
    return row


def serve_one(selector: str, expected_id: str, expected_contract: str) -> dict:
    """PHASE 2: one signed record through the REAL serving door.

    Three claims, the three the manifest makes: that `load_environment`
    admits the selector at all, that what it serves carries the public id the
    record was signed for, and that it serves the family's episode contract —
    the same digest an authored cash-application task serves under.
    """
    row = {"selector": selector, "expected_public_id": expected_id, "served": False, "note": ""}
    try:
        from beancount_ledger.beancount_ledger import PROFILE_CASH_APPLICATION, load_environment
        env = load_environment(selector)
    except Exception as exc:                       # noqa: BLE001
        reasons = getattr(exc, "reasons", None)
        row["note"] = f"{type(exc).__name__}: {'; '.join(reasons) if reasons else exc}"[:240]
        return row
    first = env.dataset[0]
    served_id = (first.get("info") or {}).get("task_id") or first.get("answer")
    row["served_public_id"] = served_id
    row["profile"] = env.profile
    row["episode_contract_digest"] = env.episode_contract_digest()
    if served_id != expected_id:
        row["note"] = f"served public id {served_id!r} is not the record's {expected_id!r}"
        return row
    if env.profile != PROFILE_CASH_APPLICATION:
        row["note"] = f"served under episode profile {env.profile!r}, not the family's"
        return row
    if env.episode_contract_digest() != expected_contract:
        row["note"] = (f"served episode contract {env.episode_contract_digest()[:16]}… is not the authored "
                       f"reference's {expected_contract[:16]}…")
        return row
    row["served"] = True
    return row


def by_stratum(censuses) -> dict:
    """`cash_gate.aggregate` per mechanism stratum.

    Decision 3 asks for acceptance rates, exhaustion counts and rejection
    distributions; this phase asks for them PER STRATUM, because the three
    mechanisms are three different constructions and a population-wide
    rejection distribution would average a fallback-continuation refusal
    against a credit-residue one.
    """
    from beancount_ledger.graph import cash_gate as G
    from beancount_ledger.graph.cash_identity import MECHANISMS
    return {mechanism: G.aggregate([c for c in censuses if c.mechanism == mechanism])
            for mechanism in MECHANISMS}


def stratified_prefix(identities, per_stratum: int) -> list:
    """The first `per_stratum` declared groups of each mechanism, in the
    roster's order.

    A prefix of the roster is not a sample of the population: the roster runs
    stratum by stratum, so `identities[:3]` is three fallback-continuation
    groups and says nothing about the other two mechanisms. This is the
    shape a bounded run wants, and it is still a PREFIX — nothing here
    chooses which groups by any property of what they drew.
    """
    from beancount_ledger.graph import cash_construct as CC

    taken: dict = {}
    out = []
    for ident in identities:
        mechanism = CC.shape_of(ident.template_family).mechanism
        if taken.get(mechanism, 0) < per_stratum:
            taken[mechanism] = taken.get(mechanism, 0) + 1
            out.append(ident)
    return out


def preflight(identities, secret: bytes, out: Path, record_dir: Path | None = None) -> dict:
    """Both phases over `identities`, writing the signed family manifest to
    `out`. Returns the whole record of the run; `main` formats it and a suite
    asserts on it."""
    import os

    from beancount_ledger.graph import cash_gate as G
    from beancount_ledger.graph import cash_manifest as FM
    from beancount_ledger.graph import cash_population as CP

    identities = list(identities)
    out = Path(out)

    # ---- the freeze, before anything is drawn ---------------------------
    freeze = CP.freeze_record()
    freeze_problems = CP.freeze_problems()

    # ---- phase 1: mint, then validate -----------------------------------
    ledger = G.PopulationLedger()
    minted, censuses = G.mint_population(identities, secret=secret, ledger=ledger)
    rows = [validate_variant(group, variant, secret)
            for group in minted for variant in sorted(group.pair.variants)]

    # ---- write and sign --------------------------------------------------
    # Only groups whose BOTH variants passed offline validation are signed. A
    # half-signed pair would be a different acceptance rule from decision 3's
    # "reject both variants when either fails an acceptance condition".
    passed_groups = {row["group"] for row in rows}
    for row in rows:
        if not row["passed"]:
            passed_groups.discard(row["group"])
    records = [rec for group in minted if group.pair.identity.label() in passed_groups
               for rec in CP.records_for(group)]
    FM.write(records, secret, out)

    # ---- phase 2: every signed record through the real serving door ------
    previous = os.environ.get(FM.FAMILY_MANIFEST_ENV)
    os.environ[FM.FAMILY_MANIFEST_ENV] = str(out)
    expected_contract, serving = "", []
    try:
        from beancount_ledger.beancount_ledger import load_environment
        reference = load_environment(AUTHORED_REFERENCE)
        expected_contract = reference.episode_contract_digest()
        serving = [serve_one(f"{CP.SELECTOR_PREFIX}:{rec['identity']['population']}:"
                             f"{rec['identity']['template_family']}:"
                             f"{rec['identity']['company_month_index']}:{rec['variant']}",
                             rec["public_id"], expected_contract)
                   for rec in records]
    finally:
        if previous is None:
            os.environ.pop(FM.FAMILY_MANIFEST_ENV, None)
        else:
            os.environ[FM.FAMILY_MANIFEST_ENV] = previous

    aggregate = G.aggregate(censuses)
    strata = by_stratum(censuses)
    failed_validation = [row for row in rows if not row["passed"]]
    not_served = [row for row in serving if not row["served"]]
    run = {
        "schema": CP.POPULATION_SCHEMA,
        "population": identities[0].population if identities else None,
        "groups_declared": len(identities),
        "groups_admitted": len(minted),
        "freeze": freeze,
        "freeze_problems": freeze_problems,
        "rows": rows,
        "records": records,
        "serving": serving,
        "failed_validation": failed_validation,
        "not_served": not_served,
        "aggregate": aggregate,
        "by_stratum": strata,
        "censuses": [c.view() for c in censuses],
        "authored_reference": AUTHORED_REFERENCE,
        "authored_episode_contract": expected_contract,
        "manifest": str(out),
        "ok": (not freeze_problems and not failed_validation and not not_served
               and len(minted) == len(identities)),
    }
    if record_dir is not None:
        write_record(run, Path(record_dir))
    return run


def write_record(run: dict, directory: Path) -> dict:
    """The evaluator-side artifacts the review note cites, one file each."""
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "freeze.json": {"freeze": run["freeze"], "problems": run["freeze_problems"]},
        "census.json": {"population": run["population"], "groups": run["censuses"]},
        "aggregates.json": {"population": run["population"], "overall": run["aggregate"],
                            "by_stratum": run["by_stratum"]},
        "validation.json": {"gates": list(VALIDATION_GATES), "rows": run["rows"]},
        "serving.json": {"authored_reference": run["authored_reference"],
                         "authored_episode_contract": run["authored_episode_contract"],
                         "rows": run["serving"]},
    }
    for name, body in files.items():
        (directory / name).write_text(json.dumps(body, indent=1, sort_keys=True), encoding="utf-8")
    return {name: str(directory / name) for name in files}


def main() -> int:
    from beancount_ledger.graph import cash_manifest as FM
    from beancount_ledger.graph import cash_population as CP
    from beancount_ledger.graph.manifest import provision_rotation_id
    from beancount_ledger.graph.mint import evaluator_secret

    parser = argparse.ArgumentParser()
    parser.add_argument("--population", default=CP.DEVELOPMENT_POPULATION)
    parser.add_argument("--groups", type=int, default=0,
                        help="mint only the first N declared groups (0 = the whole population)")
    parser.add_argument("--per-stratum", type=int, default=0,
                        help="mint only the first N declared groups OF EACH MECHANISM; a stratified smoke "
                             "run, since the roster is declared stratum by stratum and --groups 3 would "
                             "take three of the first one")
    parser.add_argument("--out", default=None,
                        help="family manifest path (default PIV_CASH_APPLICATION_MANIFEST or "
                             "~/.piv/cash_application_manifest.json)")
    parser.add_argument("--record", default=None, help="directory for the census/aggregate artifacts")
    args = parser.parse_args()

    secret = evaluator_secret()
    if secret is None:
        print("no evaluator secret configured; nothing to preflight")
        return 2
    rotation = provision_rotation_id()
    problems = CP.population_problems(args.population)
    if problems:
        for problem in problems:
            print(f"POPULATION DECLARATION: {problem}")
        return 1
    identities = CP.identities_of(args.population)
    if args.per_stratum:
        identities = stratified_prefix(identities, args.per_stratum)
    if args.groups:
        identities = identities[:args.groups]
    out = Path(args.out) if args.out else FM.manifest_path()

    t0 = time.time()
    run = preflight(identities, secret, out, Path(args.record) if args.record else None)
    seconds = time.time() - t0

    print(f"{len(identities)} declared groups of {args.population!r} minted under rotation "
          f"{rotation[:8]}… in {seconds:.0f}s; freeze {run['freeze']['digest']}")
    for problem in run["freeze_problems"]:
        print(f"   FREEZE MOVED: {problem}")
    agg = run["aggregate"]
    print(f"PHASE 1 minting: {agg['admitted_groups']}/{agg['groups']} groups admitted "
          f"({agg['exhausted_groups']} exhausted); {agg['accepted_attempts']}/{agg['attempts']} attempts "
          f"accepted; rejections {agg['rejection_distribution']}")
    for mechanism, row in run["by_stratum"].items():
        print(f"   {mechanism:22s} {row['admitted_groups']}/{row['groups']} groups, "
              f"{row['attempts']} attempts, rejections {row['rejection_distribution']}")
    print(f"PHASE 1 validation: {len(run['rows']) - len(run['failed_validation'])}/{len(run['rows'])} "
          f"variants pass {list(VALIDATION_GATES)}")
    for row in run["failed_validation"][:12]:
        print(f"   FAILED {row['selector']} {[g for g, ok in row['gates'].items() if not ok]} "
              f"{' | '.join(row['notes'])[:220]}")
    print(f"PHASE 2 serving door (signed manifest): "
          f"{len(run['serving']) - len(run['not_served'])}/{len(run['serving'])} records served with the "
          f"record's public id, the family profile and the authored reference's episode contract "
          f"{run['authored_episode_contract'][:16]}…")
    for row in run["not_served"][:12]:
        print(f"   NOT SERVED {row['selector']}: {row['note']}")
    print(f"manifest written: {run['manifest']} ({len(run['records'])} records)")
    return 0 if run["ok"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
