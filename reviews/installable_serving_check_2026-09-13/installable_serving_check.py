"""Can the INSTALLED package MINT? Round 17, decision 4's delivery boundary.

The 2026-09-12 installed-wheel check established that the eleven authored
cash-application tasks SERVE from the distributed artifact. It could not
establish that a generated instance does, because serving a generated
instance RECONSTRUCTS it, reconstruction runs the admission battery, and the
battery was `tests/world_checks.py` — which the wheel deliberately does not
ship. Decision 4 named that a delivery boundary and asked for the checker to
move into the runtime package before any installable-release claim.

This runner is the measurement of that claim, and it is made the way the
earlier one was made: from a CLEAN throwaway virtual environment holding
nothing but the wheel and its pinned dependencies, with the repository
asserted absent from `sys.path`, against a wheel whose every runtime member
is compared byte for byte with the file the interpreter actually imported.

WHAT IT DOES, IN ORDER.

  1. binds the artifact (wheel sha256, RECORD, METADATA, every
     `beancount_ledger/` member against `site-packages`);
  2. reports WHERE the admission battery resolved from — the claim is
     false if that path is not inside the installed package;
  3. runs the battery on a minted variant and then on a TAMPERED copy of
     it, because a battery that cannot fail is not evidence that it ran;
  4. MINTS one declared parent group per mechanism stratum, from the
     installed package, under its own throwaway secret and rotation, with
     its manifest in a temporary directory — never the evaluator's key and
     never `~/.piv`;
  5. writes and SIGNS a family manifest over those groups' records;
  6. serves BOTH variants of every minted group through the real
     `env.evaluate()` door with a scripted offline client that delivers the
     package's own golden ledger and golden register, and requires reward
     1.0, `complete`, the register `delivered` and the composite 1.

No model or API call is made anywhere: the client is a script, and every
number below is deterministic in the identity, the profile and the secret.

Usage:  python installable_serving_check.py <out.json> --wheel <path to .whl>
"""
import asyncio
import hashlib
import json
import os
import platform
import sys
import tempfile
import unicodedata
import zipfile
from datetime import date
from pathlib import Path

REPO = r"C:\Users\gulte\Desktop\PIV\beancount-ledger-workflows"

# --- assert the repository cannot be imported from ---------------------------
bad = [p for p in sys.path if p and os.path.normcase(os.path.abspath(p)).startswith(
    os.path.normcase(REPO))]
assert not bad, f"repository on sys.path: {bad}"

# --- this check's OWN secret, rotation and manifest --------------------------
# Never the evaluator's provisioned key, never `~/.piv`, and never a
# development bypass (this family has none): the only way to serve here is to
# sign a real manifest and admit through it.
SECRET_HEX = "installable-serving-check-2026-09-13-throwaway".encode("utf-8").hex()
_TMP = tempfile.mkdtemp(prefix="installable_serving_")
os.environ["PIV_EVAL_SECRET"] = SECRET_HEX
os.environ["PIV_KEY_ID"] = "installable-serving-check-rotation"
os.environ["PIV_CASH_APPLICATION_MANIFEST"] = str(Path(_TMP) / "cash_application_manifest.json")

import beancount_ledger  # noqa: E402

pkg = os.path.abspath(beancount_ledger.__file__)
assert "site-packages" in pkg.replace("/", os.sep), pkg
assert not os.path.normcase(pkg).startswith(os.path.normcase(REPO)), pkg
PACKAGE_DIR = Path(pkg).parent
print("installed package:", pkg)
print("version:", __import__("importlib.metadata", fromlist=["x"]).version("beancount-ledger"))

import verifiers as vf  # noqa: E402
from verifiers.legacy.types import Response, ResponseMessage, ToolCall  # noqa: E402

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import application as A  # noqa: E402
from beancount_ledger.graph import cash_admit as ADMIT  # noqa: E402
from beancount_ledger.graph import cash_construct as CC  # noqa: E402
from beancount_ledger.graph import cash_gate as G  # noqa: E402
from beancount_ledger.graph import cash_manifest as FM  # noqa: E402
from beancount_ledger.graph import cash_population as CP  # noqa: E402
from beancount_ledger.graph.mint import evaluator_secret  # noqa: E402


# --- bind the tested artifact ------------------------------------------------

def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind_artifact(wheel_path):
    """Identify the wheel and PROVE the interpreter imported from it.

    Every `beancount_ledger/` member of the wheel is compared with the file at
    the same relative path under the installed package's parent directory. A
    reinstall, an editable shim or a stale `site-packages` shows up as a
    mismatch and raises before anything is minted."""
    wheel = Path(wheel_path).resolve()
    zf = zipfile.ZipFile(wheel)
    names = zf.namelist()
    record = next(n for n in names if n.endswith(".dist-info/RECORD"))
    members = [n for n in names if n.startswith("beancount_ledger/")]
    site = PACKAGE_DIR.parent
    mismatched = [n for n in members
                  if not (site / n).is_file() or (site / n).read_bytes() != zf.read(n)]
    if mismatched:
        raise SystemExit(f"the installed package does not match {wheel.name}: {mismatched[:5]} "
                         f"({len(mismatched)} member(s) differ)")
    return {
        "wheel": wheel.name,
        "wheel_sha256": sha256_file(wheel),
        "wheel_bytes": wheel.stat().st_size,
        "members": len(names),
        "runtime_members": len(members),
        "record_sha256": hashlib.sha256(zf.read(record)).hexdigest(),
        "metadata_sha256": hashlib.sha256(
            zf.read(next(n for n in names if n.endswith(".dist-info/METADATA")))).hexdigest(),
        "installed_package": pkg,
        "every_runtime_member_matches_the_installed_file": True,
        "ships_no_tests_or_reviews": not [n for n in names
                                          if n.startswith(("tests/", "reviews/"))],
        "admission_battery_members": sorted(
            n for n in members if n.endswith(("world_checks.py", "repair_keys.py"))),
    }


def runtime_block():
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "unicode_database_version": unicodedata.unidata_version,
        "library_versions": beancount_ledger.library_versions(),
        "repository_absent_from_sys_path": True,
    }


# --- where the battery came from, and whether it can still fail --------------

def battery_block():
    """The claim this whole run exists to make, plus its negative control.

    `_world_checks()` is the construction path's own accessor, so the path
    recorded here is the path the minting path uses — not a second import
    performed for the record.
    """
    module = ADMIT._world_checks()
    where = Path(module.__file__).resolve()
    return {
        "module": module.__name__,
        "file": str(where),
        "inside_the_installed_package": PACKAGE_DIR.resolve() in where.parents,
        "loaded_from_a_repository_checkout": os.path.normcase(str(where)).startswith(
            os.path.normcase(REPO)),
        "has_check_derived": callable(getattr(module, "check_derived", None)),
    }


def tamper_control(member):
    """A battery that cannot speak is not a battery.

    The gates are run twice over the SAME minted variant, through the
    construction path's own entry point: once as that path runs them, and
    once over contract inputs whose GOLDEN LEDGER has been replaced by the
    untouched opening ledger. The second is a world whose golden does not
    close the month, which is exactly what `check_derived` — the half that
    moved into the package — exists to catch. The first must be silent and
    the second must not be, or "the installed package checks what it mints"
    is not supported by this run.

    The inputs are copied without re-deriving (`ContractInputs` refuses
    literal construction) and mutated on the copy, so nothing the serving
    path later reads is touched.
    """
    import copy

    from beancount_ledger.graph.derive import derive_contract

    bundle, inputs = derive_contract(member.world, member.task)
    clean = ADMIT.world_checker_problems(member.world, member.task, bundle, inputs)
    hurt = copy.copy(inputs)
    object.__setattr__(hurt, "golden_text", inputs.original_text)
    spoke = ADMIT.world_checker_problems(member.world, member.task, bundle, hurt)
    return {
        "entry_point": "graph.cash_admit.world_checker_problems (the construction path's own)",
        "clean_variant_problems": [p[:200] for p in clean],
        "clean_variant_is_silent": not clean,
        "tamper": "golden_text replaced by original_text on a copy of the derived inputs",
        "tampered_variant_problems": [p[:200] for p in spoke],
        "tampered_variant_speaks": bool(spoke),
    }


# --- the scripted offline client --------------------------------------------

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

#: Every row's `contract_digest` comes from here and from nowhere else.
CONTRACT_DIGEST_SOURCE = "captured from the episode state column piv_episode_contract_digest"


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


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "installable_serving_check.json"
    wheel_arg = sys.argv[sys.argv.index("--wheel") + 1] if "--wheel" in sys.argv else None
    per_stratum = int(sys.argv[sys.argv.index("--per-stratum") + 1]) if "--per-stratum" in sys.argv else 1
    artifact = bind_artifact(wheel_arg) if wheel_arg else {
        "wheel": None,
        "note": "NOT BOUND: this run was given no --wheel, so it identifies no artifact",
        "installed_package": pkg,
    }
    print("artifact:", json.dumps(artifact, indent=1))
    battery = battery_block()
    print("battery:", json.dumps(battery, indent=1))

    secret = evaluator_secret()
    manifest_path = Path(os.environ["PIV_CASH_APPLICATION_MANIFEST"])
    identities = stratified_prefix(CP.development_identities(), per_stratum)
    print(f"minting {len(identities)} declared group(s) from the installed package…")

    ledger = G.PopulationLedger()
    minted, censuses = G.mint_population(identities, secret=secret, ledger=ledger)
    groups = [{
        "group": m.pair.identity.label(),
        "identity_digest": m.pair.identity.digest(),
        "population": m.pair.identity.population,
        "family": m.pair.identity.template_family,
        "mechanism": m.pair.mechanism,
        "split": m.pair.identity.split,
        "attempt": m.pair.attempt,
        "gates_evaluated": len(m.report.gates),
        "gates_passed": bool(m.report.passed),
        "variants": sorted(m.pair.variants),
    } for m in minted]
    print(json.dumps(groups, indent=1))

    control = tamper_control(minted[0].pair.variant(sorted(minted[0].pair.variants)[0]))
    print("battery control:", json.dumps(control, indent=1)[:600])

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
            env, out = run_episode(selector, turns)
            served_id = (env.dataset[0].get("info") or {}).get("task_id") or env.dataset[0].get("answer")
            manifest = Path(out["workspace"]) / env_mod.PUBLICATION_FILE
            delivery, application = env_mod._read_publication(manifest.read_text(encoding="utf-8"))
            ok = (out.get("reward") == 1.0 and out.get("error") is None
                  and served_id == member.task.id
                  and env.profile == env_mod.PROFILE_CASH_APPLICATION
                  and out.get("piv_episode_contract_digest") == expected_contract
                  and delivery.completion == "complete" and str(delivery.score) == "1"
                  and application is not None and application.status == A.STATUS_DELIVERED
                  and str(application.application_score) == "1"
                  and str(application.composite_score) == "1")
            row = {
                "group": m.pair.identity.label(),
                "variant": variant,
                "selector": selector,
                "expected_public_id": member.task.id,
                "served_public_id": served_id,
                "profile": env.profile,
                "turns": len(turns),
                "reward": out.get("reward"),
                "error": out.get("error"),
                "stop": out.get("stop_condition"),
                "completion": delivery.completion,
                "score": str(delivery.score),
                "contract_digest": out.get("piv_episode_contract_digest"),
                "contract_digest_source": CONTRACT_DIGEST_SOURCE,
                "authored_reference_contract": expected_contract,
                "application_status": None if application is None else application.status,
                "application_score": None if application is None else str(application.application_score),
                "composite": None if application is None else str(application.composite_score),
                "ok": ok,
            }
            rows.append(row)
            if not ok:
                failures.append(selector)
            print({k: row[k] for k in ("selector", "reward", "completion", "application_status",
                                       "composite", "ok")})

    aggregate = G.aggregate(censuses)
    body = {
        "schema": "piv.installable-serving-check/1",
        "measured_on": date.today().isoformat(),
        "what_this_is":
            "Round 17, decision 4's delivery boundary, measured. One declared parent group per "
            "mechanism stratum is MINTED by the INSTALLED package in a clean throwaway virtual "
            "environment with the repository absent from sys.path, signed into a manifest under this "
            "run's own throwaway secret, and both variants of each are served through the real "
            "env.evaluate() door with a scripted offline client delivering the package's own golden "
            "ledger and golden register. No model or API call. Every contract_digest was CAPTURED "
            "from the episode's own state column.",
        "artifact": artifact,
        "runtime": runtime_block(),
        "admission_battery": battery,
        "admission_battery_control": control,
        "population": CP.DEVELOPMENT_POPULATION,
        "groups_declared": len(identities),
        "groups_minted": len(minted),
        "groups": groups,
        "aggregate": aggregate,
        "manifest_records_signed": len(records),
        "authored_reference": "cash_application_001",
        "authored_episode_contract": expected_contract,
        "rows": rows,
        "failures": failures,
    }
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(body, fh, indent=1)
        fh.write("\n")
    print("\nFAILURES:", failures or "none", f"({len(rows)} served rows)")
    return 1 if failures or len(minted) != len(identities) else 0


if __name__ == "__main__":
    raise SystemExit(main())
