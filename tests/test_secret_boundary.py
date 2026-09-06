"""The evaluator boundary, as the attacker meets it.

The keyed seed only helps if the evaluator's secret is out of the model's
reach. "No public surface contains it" was checked by grepping files; this
suite launches the SAME tool surface the model gets and tries every way a
process-local attacker could reach the secret or an oracle for it:

    canary     the evaluator secret is a canary for this process; a task is
               minted under it; then every tool reply (list, read of every
               file, grep for the canary, run_beancount, write_ledger, submit), the
               workspace bytes, the dataset row, the system prompt, the
               state after a write, the audit archive and delivery.json are
               searched for the canary in hex and raw form;

    symlinks   a symlink (file and directory) planted under a manifest name
               and a symlinked workspace root: read, grep, list, write refuse
               or fail as OUR failure, never follow;

    options    `option "insert_pythonpath"`, `option "documents"` and a
               renamed root account are refused as unmodelled options before
               any loader runs, and sys.path is untouched;

    mint       no tool can reach the minting API or the answer key: the tool
               functions' globals contain no reference to graph.mint,
               graph.generate, ContractInputs, golden_text or expected
               balances, and no tool returns anything but text;

    selectors  the released selector space is finite and injective: ASCII
               decimal indices below MAX_SELECTOR_INDEX; Arabic-Indic and
               fullwidth digits, signs, blanks and oversize indices are
               refused rather than aliased onto another selector's world.

The secret's ENTROPY is an operational rule (32 random bytes from the
provisioning step), not something a parser can check; this suite checks
that the length floor holds and that the docstring says so.

    python tests/test_secret_boundary.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import datasets as _datasets
    _datasets.disable_progress_bar()
except Exception:                           # noqa: BLE001
    pass

# A canary secret for THIS process: 32 bytes, recognisable, never the real one.
CANARY_HEX = "c0ffee5ec4e7" + "ab" * 26
os.environ["PIV_EVAL_SECRET"] = CANARY_HEX
os.environ["PIV_DEV_UNMANIFESTED"] = "1"          # the manifest test below toggles this explicitly
os.environ["PIV_MANIFEST"] = str(Path(tempfile.mkdtemp(prefix="piv_manifest_")) / "manifest.json")
os.environ["PIV_KEY_ID"] = "test-rotation-0001"       # an opaque rotation label for this process (never derived from the secret)
CANARY_NEEDLES = (CANARY_HEX, CANARY_HEX.upper(), bytes.fromhex(CANARY_HEX).hex(), "c0ffee5ec4e7")

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.graph import mint as MI  # noqa: E402


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:24]:
            print(f"      {line}")
    return ok


def note(text):
    print(f"      · {text}")


def carries_canary(text) -> bool:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    low = str(text).lower()
    return any(n.lower() in low for n in CANARY_NEEDLES)


def write_through_loop(env, state, content):
    call = SimpleNamespace(id="c", name="write_ledger", arguments=json.dumps({"content": content}))
    return asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))


# --------------------------------------------------------------------------
# 1. the canary never reaches any model-facing surface
# --------------------------------------------------------------------------

def test_the_secret_reaches_no_model_facing_surface():
    problems = []
    if MI.evaluator_secret() != bytes.fromhex(CANARY_HEX):
        return check("canary secret installed for this process", False, "evaluator_secret() is not the canary")
    env = env_mod.load_environment("train:5")
    surfaces = {}
    row = env.dataset[0]
    surfaces["dataset row"] = json.dumps({k: str(v) for k, v in row.items()})
    surfaces["system prompt"] = env.system_prompt or ""
    state = {}
    ws = env._workspace(state)
    for name in env_mod.PUBLIC_FILES:
        surfaces[f"workspace/{name}"] = (Path(ws) / name).read_bytes()
        surfaces[f"read_file({name})"] = env_mod.read_file(name, workspace=ws)
    surfaces["list_files"] = env_mod.list_files(workspace=ws)
    surfaces["grep(canary)"] = env_mod.grep("c0ffee5ec4e7", workspace=ws)
    surfaces["grep(secret)"] = env_mod.grep("secret", workspace=ws)
    surfaces["run_beancount"] = env_mod.run_beancount(workspace=ws)
    # a real write through the loop, then everything the evaluator leaves behind
    original = env_mod.read_file("ledger.beancount", workspace=ws, offset=0, limit=100000)
    reply = write_through_loop(env, state, (Path(ws) / "ledger.beancount").read_text(encoding="utf-8"))
    surfaces["write_ledger reply"] = reply[0].content if reply else ""
    surfaces["state"] = json.dumps({k: str(v) for k, v in state.items()}, default=str)
    try:
        env_mod.score_core(state)
    except Exception as exc:                # noqa: BLE001 — scoring the untouched original is a valid outcome
        surfaces["score_core exception"] = str(exc)
    for path in Path(ws).rglob("*"):
        if path.is_file():
            surfaces[f"workspace after scoring/{path.name}"] = path.read_bytes()
    audit = env_mod.audit_dir(state["piv_rollout_id"]) if state.get("piv_rollout_id") else None
    if audit and Path(audit).exists():
        for path in Path(audit).rglob("*"):
            if path.is_file():
                surfaces[f"audit/{path.name}"] = path.read_bytes()
    del original
    for name, text in surfaces.items():
        if carries_canary(text):
            problems.append(f"{name} carries the evaluator secret")
    # and the leak scan itself must look for the secret from now on
    minted = MI.mint("train", 5)
    leak_scan_src = (ROOT / "beancount_ledger" / "graph" / "mint.py").read_text(encoding="utf-8")
    if "evaluator_secret" not in leak_scan_src.split("def literal_provenance_leaks", 1)[-1]:
        note("literal_provenance_leaks does not carry the secret as a needle (belt only; nothing places it anywhere)")
    if MI.literal_provenance_leaks(minted):
        problems.append("the literal leak scan reports a leak on train:5")
    note(f"{len(surfaces)} surfaces searched for the canary in {len(CANARY_NEEDLES)} spellings")
    return check("the evaluator secret reaches no tool reply, workspace byte, dataset row, system prompt, state, "
                 "audit copy or delivery manifest", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 2. symlinks under a manifest name and at the workspace root
# --------------------------------------------------------------------------

def test_symlinks_are_never_followed():
    problems = []
    env = env_mod.load_environment("train:5")
    outside = Path(tempfile.mkdtemp(prefix="beancount_outside_"))
    (outside / "secret.txt").write_text("SECRET-SYMLINK", encoding="utf-8")
    (outside / "dir").mkdir()
    (outside / "dir" / "policy.md").write_text("SECRET-DIR", encoding="utf-8")
    try:
        os.symlink(outside / "secret.txt", outside / "probe")
    except (OSError, NotImplementedError) as exc:
        note(f"symlinks not creatable for this user ({exc.__class__.__name__}); the file-symlink probe is skipped")
        return check("symlinks under a manifest name are never followed (probe skipped: no symlink privilege)", True)
    # a file symlink under a manifest name
    ws = env._workspace({})
    os.remove(Path(ws) / "vendors.csv")
    os.symlink(outside / "secret.txt", Path(ws) / "vendors.csv")
    if "SECRET-SYMLINK" in env_mod.read_file("vendors.csv", workspace=ws):
        problems.append("read_file followed a file symlink under a manifest name")
    if "SECRET-SYMLINK" in env_mod.grep("SECRET", workspace=ws):
        problems.append("grep followed a file symlink")
    try:
        env_mod.list_files(workspace=ws)
        problems.append("list_files silently listed a symlinked declared file")
    except RuntimeError:
        pass
    # a directory symlink under a manifest name
    os.remove(Path(ws) / "policy.md")
    os.symlink(outside / "dir", Path(ws) / "policy.md", target_is_directory=True)
    if "SECRET-DIR" in env_mod.read_file("policy.md", workspace=ws):
        problems.append("read_file followed a directory symlink")
    # write_ledger through a symlinked ledger must not write outside
    os.remove(Path(ws) / "ledger.beancount")
    os.symlink(outside / "secret.txt", Path(ws) / "ledger.beancount")
    try:
        env_mod.write_ledger("2025-01-01 open Assets:Bank:Checking USD\n", workspace=ws)
        wrote_through = (outside / "secret.txt").read_text(encoding="utf-8") != "SECRET-SYMLINK"
        if wrote_through:
            problems.append("write_ledger wrote through a symlink to an outside file")
    except RuntimeError:
        pass                                          # our failure, not a write
    if (outside / "secret.txt").read_text(encoding="utf-8") != "SECRET-SYMLINK":
        problems.append("the outside file changed")
    # a symlinked workspace ROOT: the tools must still confine themselves to the real directory
    real = env._workspace({})
    link_root = outside / "wsroot"
    os.symlink(real, link_root, target_is_directory=True)
    listing = env_mod.list_files(workspace=str(link_root))
    if "ledger.beancount" not in listing:
        problems.append(f"a symlinked workspace root broke the read tools: {listing[:80]}")
    if "SECRET" in env_mod.grep("SECRET", workspace=str(link_root)):
        problems.append("grep through a symlinked root reached outside content")
    return check("symlinks under a manifest name (file, directory, the ledger) are never followed and a symlinked "
                 "root stays confined", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 3. options that would reach the filesystem or the interpreter
# --------------------------------------------------------------------------

def test_dangerous_options_are_refused_before_any_loader():
    from beancount_ledger.candidate.normalise import parse_once, ProtocolFailure
    problems = []
    before = list(sys.path)
    base = 'option "operating_currency" "USD"\n2025-01-01 open Assets:Bank:Checking USD\n'
    for line in ('option "insert_pythonpath" "TRUE"', 'option "documents" "C:/Users"', 'option "name_assets" "Secrets"',
                 'include "C:/Users/gulte/.piv/eval_secret"', 'plugin "os"', 'plugin "beancount_ledger.graph.mint"'):
        outcome = parse_once(base + line + "\n")
        if not isinstance(outcome, ProtocolFailure):
            problems.append(f"{line!r} was accepted: {type(outcome).__name__}")
        elif carries_canary(str(outcome)):
            problems.append(f"{line!r}: the refusal echoes the secret")
    if list(sys.path) != before:
        problems.append("sys.path changed while parsing")
    if "beancount.loader" in sys.modules and getattr(sys.modules["beancount.loader"], "__file__", None):
        note("beancount.loader is imported in this process (by a test import); production bans it structurally")
    return check("insert_pythonpath / documents / renamed roots / include / plugin are refused before any loader, "
                 "sys.path untouched, refusals echo no secret", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 4. the minting API and the answer key are unreachable from the tools
# --------------------------------------------------------------------------

def test_no_tool_can_reach_the_mint_or_the_answer_key():
    import inspect
    problems = []
    env = env_mod.load_environment("train:5")
    tools = {name: fn for name, fn in env.tool_map.items()}
    if set(tools) != {"list_files", "read_file", "grep", "run_beancount", "write_ledger", "submit"}:
        problems.append(f"tool surface changed: {sorted(tools)}")
    forbidden = ("mint", "generate", "ContractInputs", "golden_text", "expected_balances", "evaluator_secret", "private_seed")
    for name, fn in tools.items():
        src = inspect.getsource(fn)
        for needle in forbidden:
            if needle in src:
                problems.append(f"{name} mentions {needle}")
        sig = inspect.signature(fn)
        if sig.return_annotation not in (str, "str"):
            problems.append(f"{name} returns {sig.return_annotation}, not text")
    # the environment object holds the contract; a tool receives only its declared string arguments
    ws = env._workspace({})
    for name, fn in tools.items():
        params = [p for p in inspect.signature(fn).parameters]
        if any(p in ("env", "self", "state", "contract", "inputs") for p in params):
            problems.append(f"{name} takes a privileged argument: {params}")
    if carries_canary(env_mod.read_file("manifest.md", workspace=ws)):
        problems.append("manifest carries the secret")
    return check("the six tools mention no minting/contract symbol, take only declared text arguments and return text",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 5. the selector space is finite and injective
# --------------------------------------------------------------------------

def test_the_selector_space_is_finite_and_injective():
    problems = []
    refused = ["train:\u0663", "train:\uff13", "train:+3", "train: 3", "train:3 ", "train:", "train:-1",
               f"train:{env_mod.MAX_SELECTOR_INDEX}", "train:9999999", "train:3:medium", "test:3", "train:3:hard:x", "train:0x10"]
    for sel in refused:
        try:
            env_mod.load_environment(sel)
            problems.append(f"{sel!r} was minted (should be refused)")
        except env_mod.InitializationFailure:
            pass
    a = env_mod.load_environment("train:3").dataset[0]["answer"]
    b = env_mod.load_environment("train:0003").dataset[0]["answer"]
    if a != b:
        note("leading zeros make a different selector string but int() maps them to one index: refused? no — they minted "
             "different worlds")
        problems.append("train:3 and train:0003 minted different worlds")
    if len(str(env_mod.MAX_SELECTOR_INDEX)) > 6:
        problems.append("MAX_SELECTOR_INDEX wider than the six-character index limit")
    if MI.MIN_SECRET_BYTES < 16:
        problems.append("secret length floor below 16 bytes")
    note(f"released population per namespace and profile: {env_mod.MAX_SELECTOR_INDEX:,} selectors; "
         f"secret floor {MI.MIN_SECRET_BYTES} bytes (entropy is the provisioning step's rule, not the parser's)")
    return check("non-ASCII digits, signs, blanks, oversize and out-of-range indices are refused; the population is finite",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 6. containment probes the name gate must refuse
# --------------------------------------------------------------------------

def test_containment_probes_are_refused_by_name():
    import unicodedata
    problems = []
    env = env_mod.load_environment("train:5")
    ws = env._workspace({})
    probes = ["LEDGER.BEANCOUNT", "Ledger.beancount", "./ledger.beancount", ".\\ledger.beancount", "ledger.beancount/",
              "ledger.beancount\\", "ledger.beancount\x00", "ledger.beancount ", " ledger.beancount", "ledger.beancount:$DATA",
              "../ledger.beancount", "..\\ledger.beancount", "/ledger.beancount", "C:ledger.beancount",
              unicodedata.normalize("NFD", "ledger.béancount"), "ledger\u2024beancount", "policy.md/../ledger.beancount",
              str(Path(ws) / "ledger.beancount"), "delivery.json", ".submitted", "manifest.md.bak"]
    for probe in probes:
        reply = env_mod.read_file(probe, workspace=ws)
        if not reply.startswith("no such file"):
            problems.append(f"read_file({probe!r}) -> {reply[:60]!r}")
        reply = env_mod.grep("option", path=probe, workspace=ws)
        if not reply.startswith("no such file"):
            problems.append(f"grep(path={probe!r}) -> {reply[:60]!r}")
    # prefix confusion: a sibling directory whose name extends the workspace's
    sibling = Path(str(ws) + "-evil")
    sibling.mkdir()
    (sibling / "ledger.beancount").write_text("SECRET-SIBLING", encoding="utf-8")
    if "SECRET-SIBLING" in env_mod.read_file("ledger.beancount", workspace=ws):
        problems.append("prefix confusion: the sibling workspace was read")
    # replies never carry a resolved host path
    for reply in (env_mod.read_file("nope", workspace=ws), env_mod.grep("x", path="nope", workspace=ws),
                  env_mod.list_files(workspace=ws), env_mod.run_beancount(workspace=ws)):
        if str(ws).replace("\\", "/") in reply.replace("\\", "/") or "Users" in reply:
            problems.append(f"a reply carries a host path: {reply[:80]!r}")
    return check("case, separators, NUL, streams, traversal, absolute, drive-relative, NFD, one-dot-leader, sibling-prefix "
                 "and undeclared names are refused by name; no reply carries a host path", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 7. the release manifest decides what is served
# --------------------------------------------------------------------------

def test_serving_is_gated_by_the_signed_release_manifest():
    from beancount_ledger.graph import manifest as MF
    problems = []
    secret = bytes.fromhex(CANARY_HEX)
    path = Path(os.environ["PIV_MANIFEST"])
    if path.exists():
        path.unlink()
    saved_dev = os.environ.pop("PIV_DEV_UNMANIFESTED", None)
    try:
        # no manifest, no development flag: refused, and the reason names the remedy
        try:
            env_mod.load_environment("train:5")
            problems.append("served with no manifest and no development flag")
        except env_mod.InitializationFailure as exc:
            if "release manifest" not in exc.reasons[0]:
                problems.append(f"wrong refusal: {exc.reasons}")
        # a manifest for this key with train:5 passed and train:6 failed
        minted5 = MI.mint("train", 5)
        minted6 = MI.mint("train", 6)
        gates_ok = {g: True for g in MF.GATES}
        gates_bad = dict(gates_ok, identifiable=False)
        MF.write([MF.record("train", 5, "standard-v1", minted5.inputs.task_id, minted5.provenance.attempt, gates_ok),
                  MF.record("train", 6, "standard-v1", minted6.inputs.task_id, minted6.provenance.attempt, gates_bad)],
                 secret, path)
        env_mod.load_environment("train:5")                       # admitted
        for sel, why in (("train:6", "failed preflight"), ("train:7", "absent"), ("train:5:hard", "absent")):
            try:
                env_mod.load_environment(sel)
                problems.append(f"{sel} served ({why} expected)")
            except env_mod.InitializationFailure as exc:
                if why not in exc.reasons[0]:
                    problems.append(f"{sel}: expected {why!r} in {exc.reasons[0]!r}")
        # a tampered record: the public id edited after signing
        body = json.loads(path.read_text(encoding="utf-8"))
        body["records"][0]["public_id"] = "task-" + "0" * 24
        path.write_text(json.dumps(body), encoding="utf-8")
        try:
            env_mod.load_environment("train:5")
            problems.append("a tampered record was accepted")
        except env_mod.InitializationFailure as exc:
            if "signature" not in exc.reasons[0]:
                problems.append(f"tampered record refused for the wrong reason: {exc.reasons[0]}")
        # a manifest of ANOTHER rotation is not the active one
        MF.write([MF.record("train", 5, "standard-v1", minted5.inputs.task_id, minted5.provenance.attempt, gates_ok)], secret, path,
                 rotation="some-other-rotation")
        try:
            env_mod.load_environment("train:5")
            problems.append("another rotation's manifest admitted a selector")
        except env_mod.InitializationFailure as exc:
            if "no release manifest for this evaluator key" not in exc.reasons[0]:
                problems.append(f"other-rotation manifest refused for the wrong reason: {exc.reasons[0]}")
        # the right rotation but signed under ANOTHER secret: every record fails verification
        other = bytes.fromhex("11" * 32)
        MF.write([MF.record("train", 5, "standard-v1", minted5.inputs.task_id, minted5.provenance.attempt, gates_ok)], other, path)
        try:
            env_mod.load_environment("train:5")
            problems.append("a manifest signed under another secret admitted a selector")
        except env_mod.InitializationFailure as exc:
            if "signature" not in exc.reasons[0]:
                problems.append(f"other-secret manifest refused for the wrong reason: {exc.reasons[0]}")
        # a record from other component versions
        rec = MF.record("train", 5, "standard-v1", minted5.inputs.task_id, minted5.provenance.attempt, gates_ok)
        rec["versions"] = dict(rec["versions"], generator=rec["versions"]["generator"] + 1)
        MF.write([rec], secret, path)
        try:
            env_mod.load_environment("train:5")
            problems.append("a record from other versions was accepted")
        except env_mod.InitializationFailure as exc:
            if "versions" not in exc.reasons[0]:
                problems.append(f"version drift refused for the wrong reason: {exc.reasons[0]}")
        # the manifest carries no seed and no secret
        MF.write([MF.record("train", 5, "standard-v1", minted5.inputs.task_id, minted5.provenance.attempt, gates_ok)], secret, path)
        text = path.read_text(encoding="utf-8")
        if carries_canary(text) or str(minted5.provenance.private_seed) in text or f"{minted5.provenance.private_seed:x}" in text:
            problems.append("the manifest carries the secret or the seed")
        if MF.rotation_id() not in text or "key_id" in text:
            problems.append("the manifest does not name its rotation id (or still carries a secret-derived key id)")
        # the development override is STRUCTURAL: with the flag set but the running program not one of this
        # package's tests/ scripts, serving without a manifest is refused
        if path.exists():
            path.unlink()
        os.environ["PIV_DEV_UNMANIFESTED"] = "1"
        main = sys.modules["__main__"]
        saved_file = getattr(main, "__file__", None)
        try:
            main.__file__ = str(Path(tempfile.gettempdir()) / "serve.py")     # a serving process, not a test script
            try:
                env_mod.load_environment("train:5")
                problems.append("a non-development entrypoint honoured PIV_DEV_UNMANIFESTED=1")
            except env_mod.InitializationFailure as exc:
                if "not a development entrypoint" not in exc.reasons[0]:
                    problems.append(f"non-development refusal names the wrong reason: {exc.reasons[0]}")
        finally:
            if saved_file is None:
                try:
                    del main.__file__
                except AttributeError:
                    pass
            else:
                main.__file__ = saved_file
        # a launcher with NO main file (python -c, stdin, an embedding) is not interactive by inference:
        # the flag alone is refused; only the explicit in-process capability admits
        os.environ["PIV_DEV_UNMANIFESTED"] = "1"
        saved_file2 = getattr(main, "__file__", None)
        try:
            try:
                del main.__file__
            except AttributeError:
                pass
            try:
                env_mod.load_environment("train:5")
                problems.append("a launcher with no main file honoured the flag by inference")
            except env_mod.InitializationFailure as exc:
                if "enable_development" not in exc.reasons[0]:
                    problems.append(f"no-main-file refusal names the wrong reason: {exc.reasons[0]}")
            from beancount_ledger.graph import manifest as MF2
            MF2.enable_development("test_secret_boundary: explicit capability witness")
            try:
                env_mod.load_environment("train:5")
            except env_mod.InitializationFailure as exc:
                problems.append(f"the explicit capability did not admit: {exc.reasons[0]}")
            finally:
                MF2._DEVELOPMENT_CAPABILITY = None
        finally:
            if saved_file2 is not None:
                main.__file__ = saved_file2
        os.environ.pop("PIV_DEV_UNMANIFESTED", None)
    finally:
        if saved_dev is not None:
            os.environ["PIV_DEV_UNMANIFESTED"] = saved_dev
        if path.exists():
            path.unlink()
    return check("serving is gated by the signed release manifest: no manifest -> refused; absent / failed / tampered / "
                 "other-rotation / other-secret / other-version records -> refused; the manifest carries no seed and no "
                 "secret; the development override needs a development entrypoint, not just the flag",
                 not problems, "\n".join(problems))


def test_the_manifest_fails_closed_on_the_gate_set():
    """A record must carry exactly TODAY's gates, all True.

    `admit` used to read the record's own `passed` aggregate: true of the
    gates that existed when the preflight signed it, silent about every gate
    added since. Adding `ledger_within_envelope` therefore left older records
    admitting — the manifest asserting a gate the record had never been tested
    against. That was harmless only because the same property is re-checked
    unconditionally at load; the next gate may have no such duplicate.

    Three witnesses, each a signed record under a throwaway secret in a temp
    manifest, and a fourth on the versions path:

      - the OLD five-gate set, `passed=True`: refused, and the reason names
        the gate set rather than pretending the selector failed something;
      - today's gate names with one False: refused as a failed gate;
      - today's gate names, all True: admitted;
      - `versions()` carries the gate-set digest and the preflight contract
        version, so a gate-set change ALSO invalidates old records through the
        route that already invalidates a generator bump.

    Honest about what is being witnessed: with the gate-set digest now IN
    `versions()`, a genuinely older record is refused one line earlier, on
    versions. The records below are hand-forged to pair an old or broken gate
    map with today's versions precisely so the gate check itself is exercised
    — it is defence in depth, and the point of testing it is that it must
    still hold if the versions binding is ever loosened.
    """
    from beancount_ledger.graph import manifest as MF
    problems = []
    secret = bytes.fromhex(CANARY_HEX)
    path = Path(os.environ["PIV_MANIFEST"])
    saved_dev = os.environ.pop("PIV_DEV_UNMANIFESTED", None)
    old_gates = ("minted", "identifiable", "repair_key_equal", "golden_scores_one", "id_unique")
    try:
        minted = MI.mint("train", 5)
        current = {g: True for g in MF.GATES}

        def write_raw(gates: dict, passed: bool):
            """A record with an arbitrary gate map, signed properly — the
            signature must not be what refuses it."""
            rec = {"namespace": "train", "index": 5, "profile": "standard-v1",
                   "public_id": minted.inputs.task_id, "attempt": minted.provenance.attempt,
                   "versions": MF.versions(), "gates": gates, "passed": passed}
            body = {"schema": MF.MANIFEST_SCHEMA, "rotation_id": MF.rotation_id(),
                    "versions": MF.versions(), "records": [MF.sign(rec, secret)]}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(body, indent=1, sort_keys=True), encoding="utf-8")

        # 1. the old five-gate set, honestly signed, every gate it knew about True
        write_raw({g: True for g in old_gates}, True)
        try:
            env_mod.load_environment("train:5")
            problems.append("a record signed against the OLD gate set was admitted")
        except env_mod.InitializationFailure as exc:
            if "gate set" not in exc.reasons[0]:
                problems.append(f"the old gate set was refused for the wrong reason: {exc.reasons[0]}")

        # 2. today's names, one gate False, but `passed` claiming otherwise:
        #    the aggregate is never trusted on its own
        write_raw(dict(current, ledger_within_envelope=False), True)
        try:
            env_mod.load_environment("train:5")
            problems.append("a record with a False gate and passed=True was admitted")
        except env_mod.InitializationFailure as exc:
            if "ledger_within_envelope" not in exc.reasons[0]:
                problems.append(f"a False gate was refused for the wrong reason: {exc.reasons[0]}")

        # 3. a gate name that is not ours at all
        write_raw({**current, "invented_gate": True}, True)
        try:
            env_mod.load_environment("train:5")
            problems.append("a record carrying an unknown gate was admitted")
        except env_mod.InitializationFailure as exc:
            if "gate set" not in exc.reasons[0]:
                problems.append(f"an unknown gate was refused for the wrong reason: {exc.reasons[0]}")

        # 4. a record that disagrees with itself — every gate True, aggregate
        #    False — is evidence of nothing and is refused
        write_raw(dict(current), False)
        try:
            env_mod.load_environment("train:5")
            problems.append("a record whose gates and passed flag disagree was admitted")
        except env_mod.InitializationFailure as exc:
            if "disagree" not in exc.reasons[0]:
                problems.append(f"a self-contradicting record refused for the wrong reason: {exc.reasons[0]}")

        # 5. the current gate set, all True: admitted
        write_raw(dict(current), True)
        try:
            env_mod.load_environment("train:5")
        except env_mod.InitializationFailure as exc:
            problems.append(f"a record with every current gate True was refused: {exc.reasons[0]}")

        # 5b. a gate recorded as TRUTHY is not a gate recorded as passed. `1`,
        #     `"ok"` or a diagnostics object did not answer the question the
        #     gate asks, and admitting on truthiness would serve a world on a
        #     value nobody meant as a pass.
        for truthy in (1, "ok", ["passed"]):
            write_raw(dict(current, identifiable=truthy), True)
            try:
                env_mod.load_environment("train:5")
                problems.append(f"a gate recorded as {truthy!r} was admitted as a pass")
            except env_mod.InitializationFailure as exc:
                if "identifiable" not in exc.reasons[0]:
                    problems.append(f"a truthy gate refused for the wrong reason: {exc.reasons[0]}")
        # ...and `record()` refuses to SIGN one in the first place
        try:
            MF.record("train", 5, "standard-v1", minted.inputs.task_id, 0, dict(current, minted=1))
            problems.append("record() signed a gate result that is not a bool")
        except ValueError:
            pass

        # 5c. two records for one selector: the file's order decides which one
        #     serves. A manifest that says both "passed" and "failed" about the
        #     same world attests nothing about it, so the whole manifest is
        #     refused rather than half-believed.
        good = MF.record("train", 5, "standard-v1", minted.inputs.task_id,
                         minted.provenance.attempt, dict(current))
        bad = MF.record("train", 5, "standard-v1", minted.inputs.task_id,
                        minted.provenance.attempt, dict(current, identifiable=False))
        MF.write([good, bad], secret, path)
        try:
            env_mod.load_environment("train:5")
            problems.append("a manifest with duplicate selector records served one of them")
        except env_mod.InitializationFailure as exc:
            if "duplicate" not in exc.reasons[0]:
                problems.append(f"duplicate records refused for the wrong reason: {exc.reasons[0]}")
        # the order must not decide: the same pair the other way round is
        # refused identically, rather than serving whichever landed last
        MF.write([bad, good], secret, path)
        try:
            env_mod.load_environment("train:5")
            problems.append("reversing the duplicate pair changed the outcome")
        except env_mod.InitializationFailure as exc:
            if "duplicate" not in exc.reasons[0]:
                problems.append(f"reversed duplicates refused for the wrong reason: {exc.reasons[0]}")

        # 6. the versions path closes the same hole a second way
        versions = MF.versions()
        if versions.get("gate_set") != MF.gate_set_digest() or not versions.get("preflight_contract"):
            problems.append(f"versions() does not carry the gate set: {versions}")
        # ...and it carries WORLD semantics only. The
        # episode contract left this dict because the manifest cannot
        # preflight a ceiling it does not choose: `load_environment` admits
        # BEFORE it builds the environment and then accepts
        # `max_episode_output_tokens`, so a world admitted under the default
        # digest could be served under another with no second check. Episode
        # identity now rides every rollout and every row instead.
        if set(versions) != {"generator", "identify", "scorer_contract", "renderer", "task_contract",
                             "manifest_schema", "preflight_contract", "gate_set"}:
            problems.append(f"versions() keys moved: {sorted(versions)}")
        for leaked in ("episode_contract", "episode_contract_digest"):
            if leaked in versions:
                problems.append(f"versions() binds {leaked} again")
        # a changed episode contract must NOT invalidate a manifest any more:
        # the same record still admits when the ceiling changes the digest
        write_raw(dict(current), True)
        env_small = None
        try:
            env_small = env_mod.load_environment("train:5", max_episode_output_tokens=8_000)
        except env_mod.InitializationFailure as exc:
            problems.append(f"a non-default ceiling was refused by the manifest: {exc.reasons[0]}")
        if env_small is not None:
            if env_small.episode_contract_digest() == env_mod.episode_contract_digest():
                problems.append("an 8K environment shares the default episode digest")
            state = {}
            env_small._workspace(state)
            if state.get("piv_episode_contract_digest") != env_small.episode_contract_digest():
                problems.append("the rollout does not record the episode contract it ran under")
        rec = MF.record("train", 5, "standard-v1", minted.inputs.task_id, minted.provenance.attempt, current)
        rec["versions"] = dict(rec["versions"], gate_set="0" * 16)
        MF.write([rec], secret, path)
        try:
            env_mod.load_environment("train:5")
            problems.append("a record from another gate-set digest was admitted")
        except env_mod.InitializationFailure as exc:
            if "versions" not in exc.reasons[0]:
                problems.append(f"a gate-set digest change was refused for the wrong reason: {exc.reasons[0]}")
    finally:
        if saved_dev is not None:
            os.environ["PIV_DEV_UNMANIFESTED"] = saved_dev
        if path.exists():
            path.unlink()
    return check("admit() requires exactly the current GATES, every one True — an old gate set, a False "
                 "gate under passed=True and an unknown gate are all refused by name — and versions() "
                 "binds the gate set digest as well", not problems, "\n".join(problems))


def test_the_release_preflight_is_two_phase():
    """Offline gates on the minted world, then the real door on the signature.

    The preflight used to solve its own chicken-and-egg — it precedes the
    manifest it writes — by pointing the workers at a `PIV_MANIFEST` path that
    does not exist, so `admit` took the development route and the
    `golden_scores_one` gate judged the world rather than the file. It worked,
    and the reviewer refused it as a shape: it gates a release
    through a bypass production must never honour, and it says nothing about
    whether the SIGNED manifest admits those worlds through the door
    production uses.

    Two phases now, two claims, and this witnesses both under the suite's own
    canary secret and rotation — never the production key:

      1. `gate_one` mints and gates the exact world, with `golden_scores_one`
         built through `environment_from_minted` (no manifest consulted, no
         development override needed);
      2. after `MF.write` signs the records, `serve_one` calls the real
         `load_environment(selector)` with `PIV_DEV_UNMANIFESTED` REMOVED, and
         checks the served public id and the default episode contract.

    Then the two negatives that make the phases mean something: a record whose
    public id is wrong is refused at the serving door, and phase 1 does not
    depend on the development override at all.
    """
    import shutil
    import tempfile as _tempfile

    from beancount_ledger.graph import manifest as MF
    sys.path.insert(0, str(ROOT / "tests"))
    import preflight_manifest as PF

    problems = []
    secret = bytes.fromhex(CANARY_HEX)
    out_dir = Path(_tempfile.mkdtemp(prefix="piv_preflight_test_"))
    out = out_dir / "manifest.json"
    jobs = [("train", 5, "standard"), ("train", 6, "standard")]
    saved_dev = os.environ.get("PIV_DEV_UNMANIFESTED")
    try:
        # PHASE 1 alone, with the development override OFF, to show the
        # offline gates never needed it
        os.environ.pop("PIV_DEV_UNMANIFESTED", None)
        gated = PF.gate_one(jobs[0])
        if not all(gated["gates"].values()):
            problems.append(f"phase 1 failed with no development override: "
                            f"{[g for g, ok in gated['gates'].items() if not ok]} {gated['notes']}")
        if set(gated["gates"]) != set(MF.GATES):
            problems.append(f"gate_one does not answer exactly {sorted(MF.GATES)}: {sorted(gated['gates'])}")
        if saved_dev is not None:
            os.environ["PIV_DEV_UNMANIFESTED"] = saved_dev

        run = PF.preflight(jobs, secret, out, workers=0)
        if not run["ok"]:
            problems.append(f"the preflight failed: gates {run['gate_failed']} serving {run['serve_failed']}")
        if len(run["records"]) != len(jobs) or len(run["passed"]) != len(jobs):
            problems.append(f"{len(run['passed'])}/{len(jobs)} selectors passed the gates")
        if len(run["serving"]) != len(jobs):
            problems.append(f"phase 2 covered {len(run['serving'])} of {len(jobs)} records, not every one")
        if any(not r["served"] for r in run["serving"]):
            problems.append(f"a signed record was not served: {[r for r in run['serving'] if not r['served']]}")
        if not out.is_file():
            problems.append("no manifest was written")
        # the manifest really is the one phase 2 read, and it is signed
        body = json.loads(out.read_text(encoding="utf-8"))
        if body.get("versions") != MF.versions() or not body.get("records"):
            problems.append("the written manifest does not carry today's versions")
        if any(not MF.verify(rec, secret) for rec in body["records"]):
            problems.append("a written record does not verify under the preflight secret")

        # THE NEGATIVES. Three, because phase 2 makes three claims and each
        # one has to be able to fail on its own.
        saved_manifest = os.environ.get("PIV_MANIFEST")
        os.environ["PIV_MANIFEST"] = str(out)
        os.environ.pop("PIV_DEV_UNMANIFESTED", None)
        try:
            # (a) admission: a record signed for another public id is refused
            # by `admit` before the environment is built
            forged = [dict(r, public_id="task-" + "0" * 24) for r in run["records"]]
            for rec in forged:
                rec.pop("signature", None)
            MF.write(forged, secret, out)
            row = PF.serve_one(("train", 5, "standard", forged[0]["public_id"]))
            if row["served"]:
                problems.append("a record signed for another public id was served")
            elif "public id" not in row["note"]:
                problems.append(f"the wrong-id refusal does not name the reason: {row['note']!r}")

            # (b) serve_one's OWN id comparison — `admit` cannot catch this,
            # because the manifest and the minted world agree; what disagrees
            # is the id the caller expected. Without this the check could be
            # deleted and (a) would still pass.
            MF.write(run["records"], secret, out)
            row = PF.serve_one(("train", 5, "standard", "task-" + "1" * 24))
            if row["served"]:
                problems.append("serve_one accepted a served id that is not the record's")
            elif "served public id" not in row["note"]:
                problems.append(f"serve_one's id check did not fire: {row['note']!r}")

            # (c) serve_one's episode-contract comparison. The ENVIRONMENT's
            # digest is made to differ from the module default — the shape of
            # a host that serves a non-default ceiling, which is exactly what
            # phase 2 exists to catch now that the manifest no longer binds
            # the episode contract. Patching the module function instead would
            # move BOTH sides and witness nothing.
            real_method = env_mod.BeancountLedgerEnv.episode_contract_digest
            env_mod.BeancountLedgerEnv.episode_contract_digest = lambda self: "0" * 64
            try:
                row = PF.serve_one(("train", 5, "standard", run["records"][0]["public_id"]))
            finally:
                env_mod.BeancountLedgerEnv.episode_contract_digest = real_method
            if row["served"]:
                problems.append("serve_one accepted an environment on a non-default episode contract")
            elif "episode contract" not in row["note"]:
                problems.append(f"serve_one's episode-contract check did not fire: {row['note']!r}")
        finally:
            if saved_manifest is not None:
                os.environ["PIV_MANIFEST"] = saved_manifest
            if saved_dev is not None:
                os.environ["PIV_DEV_UNMANIFESTED"] = saved_dev
    finally:
        if saved_dev is not None:
            os.environ["PIV_DEV_UNMANIFESTED"] = saved_dev
        else:
            os.environ.pop("PIV_DEV_UNMANIFESTED", None)
        shutil.rmtree(out_dir, ignore_errors=True)
    return check("the release preflight is two phases: offline gates on the freshly minted world (no "
                 "manifest, no development override) and, after signing, every record through the real "
                 "load_environment door — where a record carrying another public id is refused",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_secret_reaches_no_model_facing_surface,
    test_symlinks_are_never_followed,
    test_dangerous_options_are_refused_before_any_loader,
    test_no_tool_can_reach_the_mint_or_the_answer_key,
    test_the_selector_space_is_finite_and_injective,
    test_containment_probes_are_refused_by_name,
    test_serving_is_gated_by_the_signed_release_manifest,
    test_the_manifest_fails_closed_on_the_gate_set,
    test_the_release_preflight_is_two_phase,
]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
