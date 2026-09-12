"""Independent installed-wheel check, run from a CLEAN throwaway venv.

Loads and SCORES all eleven cash-application tasks plus one legacy task
through the real `env.evaluate()` door of the INSTALLED package, with the
repository asserted absent from sys.path.  Offline: the client is scripted,
no model or API call is made.

PUBLISHED FORM.  The scoring path below -- the scripted turns, the golden
register construction, the `env.evaluate()` call, the `ok` predicate and
every recorded field of a row -- is byte-identical to the runner that
produced `attested_build_2026-09-11.json`.  What was ADDED for publication,
and is declared here rather than left for a reader to discover:

  * `--wheel`, which BINDS the tested artifact.  The wheel file is hashed,
    its RECORD is hashed, and every `beancount_ledger/` member of it is
    compared byte for byte with the file the interpreter actually imported
    from `site-packages`.  A mismatch aborts before a single task is
    scored, so a record cannot name an artifact it did not test.
  * a `runtime` block (interpreter, platform, Unicode database, the pinned
    library versions the package itself reports).
  * `contract_digest_source` on every row.  The digest is CAPTURED from the
    episode's own `piv_episode_contract_digest` state column.  It is never
    read from a module constant, so a row's digest is what that episode
    reported and not what the package declares it ought to be.

The earlier `wheel_check*.json` records in the working area read
`episode_contract_digest` from the top level of the publication manifest,
where the field does not live, and so recorded `contract_digest: null`
twelve times over.  Their twelve complete successes stand; their contract
digests were never captured, and the attestation says so.

Usage:  python installed_wheel_check.py <out.json> --wheel <path to .whl>
"""
import asyncio
import hashlib
import json
import os
import platform
import sys
import unicodedata
import zipfile
from datetime import date
from decimal import Decimal as D
from pathlib import Path

REPO = r"C:\Users\gulte\Desktop\PIV\beancount-ledger-workflows"

# --- assert the repository cannot be imported from ---------------------------
bad = [p for p in sys.path if p and os.path.normcase(os.path.abspath(p)).startswith(
    os.path.normcase(REPO))]
assert not bad, f"repository on sys.path: {bad}"

import beancount_ledger  # noqa: E402
pkg = os.path.abspath(beancount_ledger.__file__)
assert "site-packages" in pkg.replace("/", os.sep), pkg
assert not os.path.normcase(pkg).startswith(os.path.normcase(REPO)), pkg
print("installed package:", pkg)
print("version:", __import__("importlib.metadata", fromlist=["x"]).version("beancount-ledger"))

import verifiers as vf  # noqa: E402
from verifiers.legacy.types import Response, ResponseMessage, ToolCall  # noqa: E402

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.beancount_ledger import load_environment  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.worlds import CASH_APPLICATION_REGISTRY, REGISTRY  # noqa: E402
from beancount_ledger.candidate import application as A  # noqa: E402


# --- bind the tested artifact ------------------------------------------------

def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind_artifact(wheel_path):
    """Identify the wheel and PROVE the interpreter imported from it.

    Every `beancount_ledger/` member of the wheel is compared with the file
    at the same relative path under the installed package's parent
    directory.  Nothing here is taken on trust from the install record: a
    reinstall, an editable shim or a stale `site-packages` shows up as a
    mismatch and raises."""
    wheel = Path(wheel_path).resolve()
    zf = zipfile.ZipFile(wheel)
    names = zf.namelist()
    record = next(n for n in names if n.endswith(".dist-info/RECORD"))
    members = [n for n in names if n.startswith("beancount_ledger/")]
    site = Path(pkg).parent.parent
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
    }


def runtime_block():
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "unicode_database_version": unicodedata.unidata_version,
        "library_versions": beancount_ledger.library_versions(),
    }


def money(v):
    return f"{D(v):.2f}"


def items(pairs):
    return [{"invoice_id": i, "amount": money(a)} for i, a in pairs]


def rec(receipt_id, applied, written_off=(), unapplied="0.00"):
    return {"receipt_id": receipt_id, "applied": items(applied),
            "written_off": items(written_off), "unapplied_amount": money(unapplied)}


def cn(credit_note_id, applied, unapplied="0.00"):
    return {"credit_note_id": credit_note_id, "applied": items(applied),
            "unapplied_amount": money(unapplied)}


def row(invoice_id, customer, basis, applied, credited, written_off, remaining):
    return {"invoice_id": invoice_id, "customer": customer, "period_basis": money(basis),
            "applied_total": money(applied), "credited": money(credited),
            "written_off": money(written_off), "remaining": money(remaining)}


def golden_document(truth):
    """The register the installed package's own truth says, in the delivered schema."""
    return {"schema": A.APPLICATION_SCHEMA,
            "receipts": [rec(r[0], r[4], r[5], r[6]) for r in truth.receipts],
            "credit_notes": [cn(c[0], c[4], c[5]) for c in truth.credit_notes],
            "closing_open_items": [row(*w) for w in truth.register]}


def calls(*specs):
    return ResponseMessage(
        content="", finish_reason="tool_calls", is_truncated=False,
        tool_calls=[ToolCall(id=i, name=n, arguments=json.dumps(a)) for i, n, a in specs])


def narrated(text="Working."):
    return ResponseMessage(content=text, tool_calls=None, finish_reason="stop",
                           is_truncated=False)


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


def run(task_id, turns):
    env = load_environment(task_id)
    results = asyncio.run(env.evaluate(
        client=TurnScript(turns), model="scripted", num_examples=1, rollouts_per_example=1,
        max_concurrent=1, save_results=False, state_columns=list(COLUMNS)))
    return (results["outputs"] or [{}])[0]


out_path = sys.argv[1] if len(sys.argv) > 1 else "installed_wheel_check.json"
wheel_arg = sys.argv[sys.argv.index("--wheel") + 1] if "--wheel" in sys.argv else None
artifact = bind_artifact(wheel_arg) if wheel_arg else {
    "wheel": None,
    "note": "NOT BOUND: this run was given no --wheel, so it identifies no artifact",
    "installed_package": pkg,
}
print("artifact:", json.dumps(artifact, indent=1))

rows = []
failures = []

for tid in sorted(CASH_APPLICATION_REGISTRY):
    world, task = CASH_APPLICATION_REGISTRY[tid]
    _bundle, inputs = derive_contract(world, task)
    ledger = inputs.golden_text
    register = json.dumps(golden_document(inputs.application))
    turns = [
        calls(("a", "list_files", {})),
        calls(("b", "read_file", {"name": "ledger.beancount"})),
        calls(("c", "write_ledger", {"content": ledger})),
        calls(("d", "write_cash_application", {"content": register})),
        calls(("e", "submit", {})),
    ]
    out = run(tid, turns)
    manifest = Path(out["workspace"]) / env_mod.PUBLICATION_FILE
    delivery, application = env_mod._read_publication(manifest.read_text(encoding="utf-8"))
    ok = (out.get("reward") == 1.0 and out.get("error") is None
          and delivery.completion == "complete"
          and application is not None and application.status == A.STATUS_DELIVERED)
    rows.append({
        "task": tid, "reward": out.get("reward"), "error": out.get("error"),
        "turns": len([t for t in turns]),
        "stop": out.get("stop_condition"),
        "completion": delivery.completion,
        "score": str(delivery.score),
        "contract_digest": out.get("piv_episode_contract_digest"),
        "contract_digest_source": CONTRACT_DIGEST_SOURCE,
        "application_status": None if application is None else application.status,
        "application_score": None if application is None else str(application.application_score),
        "composite": None if application is None else str(application.composite_score),
        "ok": ok,
    })
    if not ok:
        failures.append(tid)
    print(rows[-1])

# legacy control
for tid in ["bank_recon_001"]:
    world, task = REGISTRY[tid]
    _bundle, inputs = derive_contract(world, task)
    turns = [
        calls(("a", "list_files", {})),
        calls(("b", "read_file", {"name": "ledger.beancount"})),
        calls(("c", "write_ledger", {"content": inputs.golden_text})),
        calls(("d", "submit", {})),
    ]
    out = run(tid, turns)
    manifest = Path(out["workspace"]) / env_mod.PUBLICATION_FILE
    delivery, application = env_mod._read_publication(manifest.read_text(encoding="utf-8"))
    ok = (out.get("reward") == 1.0 and delivery.completion == "complete" and application is None)
    rows.append({"task": tid, "reward": out.get("reward"), "completion": delivery.completion,
                 "score": str(delivery.score), "stop": out.get("stop_condition"),
                 "contract_digest": out.get("piv_episode_contract_digest"),
                 "contract_digest_source": CONTRACT_DIGEST_SOURCE,
                 "application_status": None if application is None else application.status,
                 "turns": len(turns),
                 "ok": ok})
    if not ok:
        failures.append(tid)
    print(rows[-1])

with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
    json.dump({
        "schema": "piv.installed-wheel-check/1",
        "measured_on": date.today().isoformat(),
        "what_this_is": "Twelve episodes through the real env.evaluate() door of the INSTALLED "
                        "package in a clean throwaway venv, offline, with a scripted client. "
                        "Every contract_digest below was CAPTURED from the episode's own state "
                        "column; none is copied from a declared constant.",
        "artifact": artifact,
        "runtime": runtime_block(),
        "package": pkg,
        "rows": rows,
        "failures": failures,
    }, fh, indent=1)
    fh.write("\n")
print("\nFAILURES:", failures or "none", f"({len(rows)} rows)")
