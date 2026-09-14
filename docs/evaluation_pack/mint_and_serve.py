"""Mint the frozen cash-application development population under YOUR evaluator
key, sign YOUR family manifest, and prove that every minted variant serves.

    python mint_and_serve.py [--per-stratum N | --all] [--out DIR]

This is the external team's copy of the check this repository published as
`reviews/installable_serving_check_2026-09-13/installable_serving_check.py`,
stripped of the wheel-binding bookkeeping that only matters for a release
record. It runs against whatever `beancount_ledger` is importable - a wheel
installed from the Environments Hub or a checkout - and it prints where the
package resolved from, so the record says which.

WHAT IT DOES, IN ORDER

  1. Refuses to run unless the three evaluator-side settings are explicit:
     `PIV_EVAL_SECRET` (hex, >= 16 bytes), `PIV_KEY_ID` (any opaque rotation
     label) and `PIV_CASH_APPLICATION_MANIFEST` (the file it may write). It
     never touches `~/.piv/`.
  2. Checks that the installed generator IS the frozen one: the live freeze
     record's digest must equal the digest in `frozen_declaration.json` beside
     this script. A different digest means a different generator, profile,
     gate set, catalogue or split map, and nothing minted under it belongs to
     this population.
  3. Mints the declared groups - the first N per mechanism stratum in the
     roster's declared order (a prefix, never a sample), or all 96 with
     `--all` - against one population ledger, exactly as the published census
     was taken. Exhausted groups are named, not replaced.
  4. Signs one record per variant into YOUR manifest under YOUR key.
  5. Serves EVERY signed variant through the real `beancount_ledger.
     load_environment` and the real `env.evaluate()` door with a scripted
     offline client that delivers the package's own golden ledger and golden
     register, and requires: reward 1.0, completion `complete`, register
     `delivered`, the served public id equal to the record's, the episode
     profile `cash_application`, and the served episode-contract digest equal
     to what the AUTHORED task `cash_application_001` serves under.
  6. Writes `census.json`, `serving.json` and `run.json` under `--out`.

WHAT IT PROVES, AND WHAT IT DOES NOT. A pass proves that your installation
mints admissible fresh instances of the declared population under your key
and that they serve through the same door, under the same episode contract,
as the authored tasks. It does not prove anything about difficulty, about any
model, or about training benefit. No model is called here; every number is
deterministic in the identity, the profile and your secret.

YOUR WORLDS ARE NOT OUR WORLDS. The evaluator secret decides what each
declared identity draws. Your census will carry the same 96 declared
identities and the same declared order as ours, and its OWN public ids,
content digests, attempt ordinals and exhaustion outcomes. Compare census
SHAPE (declared / admitted / exhausted, attempts) with ours; do not expect the
public ids to match, and do not expect the published attempt count (98) to
be yours.

KEEP `census.json` EVALUATOR-SIDE. It binds enumerable selectors to
public-content digests. It belongs beside your manifest, never inside an
agent's workspace, a prompt, or a dataset a model can read.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
DECLARATION = HERE / "frozen_declaration.json"

REQUIRED_ENV = ("PIV_EVAL_SECRET", "PIV_KEY_ID", "PIV_CASH_APPLICATION_MANIFEST")


def refuse(message: str, code: int = 2) -> "NoReturn":  # noqa: F821
    print(f"REFUSED: {message}", file=sys.stderr)
    raise SystemExit(code)


def check_environment() -> None:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        refuse("set these explicitly before running (this script never reads or writes ~/.piv): "
               + ", ".join(missing))
    try:
        secret = bytes.fromhex(os.environ["PIV_EVAL_SECRET"].strip())
    except ValueError:
        refuse("PIV_EVAL_SECRET must be hex")
    if len(secret) < 16:
        refuse("PIV_EVAL_SECRET must be at least 16 bytes")
    manifest = Path(os.environ["PIV_CASH_APPLICATION_MANIFEST"]).expanduser()
    home_piv = Path(os.path.expanduser("~")) / ".piv"
    try:
        if manifest.resolve().is_relative_to(home_piv.resolve()):
            refuse("PIV_CASH_APPLICATION_MANIFEST points into ~/.piv; this script writes only where you name "
                   "explicitly outside it, so a production manifest is never overwritten by a check")
    except OSError:
        pass


check_environment()

try:  # the dataset library's progress bars are noise on a check's terminal
    import datasets
    datasets.disable_progress_bars()
except Exception:  # noqa: BLE001
    pass

import verifiers as vf  # noqa: E402
from verifiers.legacy.types import Response, ResponseMessage, ToolCall  # noqa: E402

import beancount_ledger  # noqa: E402
from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import application as A  # noqa: E402
from beancount_ledger.graph import cash_construct as CC  # noqa: E402
from beancount_ledger.graph import cash_gate as G  # noqa: E402
from beancount_ledger.graph import cash_manifest as FM  # noqa: E402
from beancount_ledger.graph import cash_population as CP  # noqa: E402
from beancount_ledger.graph.mint import evaluator_secret  # noqa: E402


# --- where the package came from --------------------------------------------

def package_block() -> dict:
    origin = Path(beancount_ledger.__file__).resolve()
    try:
        metadata_version = importlib.metadata.version("beancount-ledger")
    except importlib.metadata.PackageNotFoundError:
        metadata_version = None
    return {
        "import_path": str(origin),
        "resolved_from_site_packages": "site-packages" in str(origin).replace("/", os.sep),
        "distribution_version_from_metadata": metadata_version,
        "note": ("the metadata version is authoritative for an installed wheel; for an editable checkout "
                 "it can lag pyproject.toml, so the freeze digest below is the binding identity"),
        "library_versions": env_mod.library_versions(),
        "runtime": {"implementation": platform.python_implementation(), "version": platform.python_version(),
                    "system": platform.system(), "machine": platform.machine(),
                    "unicode_database": unicodedata.unidata_version},
    }


def frozen_generator_block() -> dict:
    """The live freeze against the pack's declaration. Anything but equality
    is a different generator, and the run stops before minting."""
    live = CP.freeze_record()
    declared = json.loads(DECLARATION.read_text(encoding="utf-8"))
    expected = declared["family_freeze"]["digest"]
    problems = list(CP.freeze_problems())
    if not live.get("declared_matches_live"):
        problems.append("the live freeze does not match the package's own declared literals")
    if live["digest"] != expected:
        problems.append(f"live freeze digest {live['digest']} != the pack's frozen {expected}")
    if problems:
        refuse("this is not the frozen generator: " + "; ".join(problems), code=3)
    return {"freeze_digest": live["digest"], "declared": live["declared"],
            "matches_pack_declaration": True}


# --- the scripted offline client (the published check's, verbatim in shape) --

def calls(*specs):
    return ResponseMessage(
        content="", finish_reason="tool_calls", is_truncated=False,
        tool_calls=[ToolCall(id=i, name=n, arguments=json.dumps(a)) for i, n, a in specs])


def narrated(text="Working."):
    return ResponseMessage(content=text, tool_calls=None, finish_reason="stop", is_truncated=False)


class TurnScript(vf.Client):
    def __init__(self, turns):
        super().__init__(object())
        self.turns = list(turns)
        self.turn = 0

    def setup_client(self, config):
        return object()

    async def to_native_tool(self, tool):
        return tool

    async def to_native_prompt(self, messages):
        return messages, {}

    async def get_native_response(self, prompt, model, sampling_args, tools=None, **kwargs):
        self.turn += 1
        m = self.turns[self.turn - 1] if self.turn <= len(self.turns) else narrated()
        return Response(id=f"s-{self.turn}", created=0, model=model, usage=None, message=m)

    async def raise_from_native_response(self, response):
        return None

    async def from_native_response(self, response):
        return response

    async def close(self):
        return None


COLUMNS = ["workspace", "piv_score", "piv_episode_contract_digest"]


def run_episode(selector, turns):
    env = env_mod.load_environment(selector)
    results = asyncio.run(env.evaluate(
        client=TurnScript(turns), model="scripted", num_examples=1, rollouts_per_example=1,
        max_concurrent=1, save_results=False, state_columns=list(COLUMNS)))
    return env, (results["outputs"] or [{}])[0]


# --- the run -----------------------------------------------------------------

def stratified_prefix(identities, per_stratum):
    """The first `per_stratum` declared groups of each mechanism, in the
    roster's order. A prefix, not a sample: nothing here chooses a group by
    anything it drew."""
    taken, out = {}, []
    for ident in identities:
        mechanism = CC.shape_of(ident.template_family).mechanism
        if taken.get(mechanism, 0) < per_stratum:
            taken[mechanism] = taken.get(mechanism, 0) + 1
            out.append(ident)
    return out


def write_json(path: Path, body) -> str:
    text = json.dumps(body, indent=1, sort_keys=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--per-stratum", type=int, default=1,
                       help="declared groups per mechanism stratum, as a roster prefix (default 1)")
    group.add_argument("--all", action="store_true", help="every declared group (96)")
    parser.add_argument("--out", default="evaluation_pack_run",
                        help="directory for census.json, serving.json and run.json (default ./evaluation_pack_run)")
    args = parser.parse_args()
    per_stratum = 32 if args.all else args.per_stratum
    if per_stratum < 1 or per_stratum > 32:
        refuse("--per-stratum must be between 1 and 32")

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    package = package_block()
    print("package:", package["import_path"])
    print("runtime:", json.dumps(package["runtime"]))
    generator = frozen_generator_block()
    print("frozen generator confirmed, freeze digest", generator["freeze_digest"])

    secret = evaluator_secret()
    manifest_path = Path(os.environ["PIV_CASH_APPLICATION_MANIFEST"]).expanduser().resolve()
    identities = stratified_prefix(CP.identities_of(CP.DEVELOPMENT_POPULATION), per_stratum)
    print(f"minting {len(identities)} declared group(s) of {CP.DEVELOPMENT_POPULATION} ...")

    ledger = G.PopulationLedger()
    minted, censuses = G.mint_population(identities, secret=secret, ledger=ledger)
    aggregate = G.aggregate(censuses)
    # A GroupCensus's `outcome` is "admitted" or "exhausted"; an exhausted
    # group is a named failure with its whole attempt history, never replaced.
    exhausted = [{"group": getattr(c, "group", None) or getattr(c, "label", None),
                  "mechanism": c.mechanism, "outcome": c.outcome, "attempts": len(c.attempts)}
                 for c in censuses if c.outcome != "admitted"]

    groups = []
    for m in minted:
        row = {
            "group": m.pair.identity.label(),
            "identity_digest": m.pair.identity.digest(),
            "population": m.pair.identity.population,
            "template_family": m.pair.identity.template_family,
            "mechanism": m.pair.mechanism,
            "split": m.pair.identity.split,
            "attempt": m.pair.attempt,
            "gates_evaluated": len(m.report.gates),
            "gates_passed": bool(m.report.passed),
            "variants": {},
        }
        for variant in sorted(m.pair.variants):
            member = m.pair.variant(variant)
            row["variants"][variant] = {
                "selector": CP.selector_of(m.pair.identity, variant),
                "public_id": member.task.id,
                "public_content_digest": CP.content_digest_of(member),
            }
        groups.append(row)
    print(f"minted {len(groups)} group(s); exhausted {len(exhausted)}")

    records = [rec for m in minted for rec in CP.records_for(m)]
    FM.write(records, secret, manifest_path)
    print(f"signed {len(records)} record(s) into {manifest_path}")

    reference = env_mod.load_environment("cash_application_001")
    expected_contract = reference.episode_contract_digest()

    rows, failures = [], []
    for m in minted:
        for variant in sorted(m.pair.variants):
            member = m.pair.variant(variant)
            selector = CP.selector_of(m.pair.identity, variant)
            turns = [
                calls(("a", "list_files", {})),
                calls(("b", "read_file", {"name": "ledger.beancount"})),
                calls(("c", "write_ledger", {"content": member.inputs.golden_text})),
                calls(("d", "write_cash_application", {"content": member.golden_register})),
                calls(("e", "submit", {})),
            ]
            env, result = run_episode(selector, turns)
            served_id = (env.dataset[0].get("info") or {}).get("task_id") or env.dataset[0].get("answer")
            publication = Path(result["workspace"]) / env_mod.PUBLICATION_FILE
            delivery, application = env_mod._read_publication(publication.read_text(encoding="utf-8"))
            ok = (result.get("reward") == 1.0 and result.get("error") is None
                  and served_id == member.task.id
                  and env.profile == env_mod.PROFILE_CASH_APPLICATION
                  and result.get("piv_episode_contract_digest") == expected_contract
                  and delivery.completion == "complete" and str(delivery.score) == "1"
                  and application is not None and application.status == A.STATUS_DELIVERED
                  and str(application.application_score) == "1"
                  and str(application.composite_score) == "1")
            row = {
                "selector": selector,
                "group": m.pair.identity.label(),
                "variant": variant,
                "served": bool(ok),
                "expected_public_id": member.task.id,
                "served_public_id": served_id,
                "profile": env.profile,
                "reward": result.get("reward"),
                "error": result.get("error"),
                "completion": delivery.completion,
                "ledger_score": str(delivery.score),
                "application_status": None if application is None else application.status,
                "application_score": None if application is None else str(application.application_score),
                "composite": None if application is None else str(application.composite_score),
                "episode_contract_digest": result.get("piv_episode_contract_digest"),
                "authored_reference_contract": expected_contract,
            }
            rows.append(row)
            if not ok:
                failures.append(selector)
            print({k: row[k] for k in ("selector", "reward", "completion", "application_status", "composite",
                                       "served")})

    finished = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    census_digest = write_json(out / "census.json", {
        "schema": "piv.evaluation-pack.census/1",
        "evaluator_side": "keep beside the manifest; never inside an agent workspace, prompt or dataset",
        "population": CP.DEVELOPMENT_POPULATION,
        "declared_order": "roster prefix per mechanism stratum, never a sample",
        "per_stratum": per_stratum,
        "declared_groups_minted": len(identities),
        "admitted_groups": len(groups),
        "exhausted_groups": len(exhausted),
        "exhausted": exhausted,
        "aggregate": aggregate,
        "groups": groups,
    })
    serving_digest = write_json(out / "serving.json", {
        "schema": "piv.evaluation-pack.serving/1",
        "authored_reference": {"task_id": "cash_application_001", "episode_contract_digest": expected_contract},
        "manifest": {"path": str(manifest_path), "records_signed": len(records),
                     "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
        "served": len(rows) - len(failures),
        "failed": failures,
        "rows": rows,
    })
    write_json(out / "run.json", {
        "schema": "piv.evaluation-pack.run/1",
        "started_at": started, "finished_at": finished,
        "package": package,
        "frozen_generator": generator,
        "population": CP.DEVELOPMENT_POPULATION,
        "groups_requested_per_stratum": per_stratum,
        "outputs": {"census.json": census_digest, "serving.json": serving_digest},
        "result": "PASS" if not failures and not exhausted else "FAIL",
        "what_a_pass_means": ("your installation mints admissible fresh instances of the declared population "
                              "under your key and serves them under the authored episode contract; nothing "
                              "about difficulty, any model, or training benefit"),
    })
    print(f"\ncensus: {out / 'census.json'}\nserving: {out / 'serving.json'}\nrun: {out / 'run.json'}")
    if exhausted:
        print(f"FAIL: {len(exhausted)} declared group(s) exhausted under this key: named in census.json")
    if failures:
        print(f"FAIL: {len(failures)} variant(s) did not serve: {failures}")
    print("PASS" if not failures and not exhausted else "FAIL")
    return 0 if not failures and not exhausted else 1


if __name__ == "__main__":
    raise SystemExit(main())
