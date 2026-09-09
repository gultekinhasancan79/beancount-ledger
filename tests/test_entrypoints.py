"""Every path that touches agent-authored text must be safe. Not just one.

This suite exists because the plugin-import hole survived being found and
fixed. It was closed inside `candidate/normalise.py` and left open in
`reward.py`, which is the code the environment actually runs — the
`write_ledger` tool writes the agent's text to disk and `run_beancount` hands
it straight to `reward.load_ledger`, which called `loader.load_string`.

The write-up said the hole was closed. Every test agreed. Both were talking
about a layer nothing called.

So the property under test here is not "the boundary is safe" but "**there is
no unsafe path**", and it is checked two ways:

  1. structurally — no module in the package may import `beancount.loader` at
     all, so a future call site cannot quietly reintroduce it;
  2. behaviourally — every entry point that accepts submitted text is fed a
     `plugin` directive and must not import anything.

The structural check is the one that generalises. A behavioural test only
covers the entry points someone remembered to list, which is exactly how this
was missed the first time.

    python tests/test_entrypoints.py
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PACKAGE = ROOT / "beancount_ledger"

# The one module allowed to import a Beancount parsing surface.
SAFE_PARSE = "safe_parse.py"

PROBE = "colorsys"  # nothing else in this package imports it


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:10]:
            print(f"      {line}")
    return ok


# Beancount surfaces that turn text into entries. Only `safe_parse` may touch
# any of them.
#
# Banning `beancount.loader` alone was the first version and it is too narrow:
# a later call site could import `beancount.parser` directly and rebuild a
# partial parse, or reach a side-effecting API under an alias. The rule is
# "one door", not "one forbidden door".
PARSING_SURFACES = ("beancount.loader", "beancount.parser", "beancount.ops")


def _imports_parsing_surface(tree):
    """Every import in this module that touches a Beancount parsing surface."""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == s or alias.name.startswith(s + ".")
                       for s in PARSING_SURFACES):
                    hits.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if any(module == s or module.startswith(s + ".") for s in PARSING_SURFACES):
                hits.append((node.lineno, f"from {module} import ..."))
            elif module == "beancount":
                for alias in node.names:
                    if alias.name in ("loader", "parser", "ops"):
                        hits.append((node.lineno, f"from beancount import {alias.name}"))
    return hits


def test_only_one_module_may_parse_submitted_text():
    """Structural, and the one that generalises: parsing is a one-door capability.

    Parsed rather than grepped, because several docstrings legitimately name
    `loader.load_string` to record why it is forbidden. An actual import is
    what is banned, and only outside `safe_parse.py`.

    This does not prove absence of `importlib`/`__import__` reaching the same
    API dynamically. It is guarding against developer regression rather than
    against code that is already executing arbitrarily, and for that it holds.
    The end-to-end trap below covers the case this cannot see.
    """
    offenders = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name == SAFE_PARSE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, what in _imports_parsing_surface(tree):
            offenders.append(f"{path.name}:{lineno} {what}")
    total = len(list(PACKAGE.rglob("*.py")))
    return check(
        f"only {SAFE_PARSE} imports a Beancount parsing surface ({total} files)",
        not offenders,
        "\n".join(offenders),
    )


def test_safe_parse_actually_is_the_door():
    """The rule above is vacuous if nothing does the parsing.

    The other side of the pair: `safe_parse.py` must genuinely import a parsing
    surface, or "only safe_parse may parse" would be satisfied by a package
    that cannot parse at all.
    """
    tree = ast.parse((PACKAGE / SAFE_PARSE).read_text(encoding="utf-8"))
    hits = _imports_parsing_surface(tree)
    return check(
        f"{SAFE_PARSE} is the module that does parse ({len(hits)} imports)",
        bool(hits),
        "it imports no parsing surface at all",
    )


def _entry_points():
    """Every function that accepts submitted text, with a way to call it.

    Listed explicitly and asserted complete by the structural test above. If
    someone adds a sixth, the loader check still protects it; this list is the
    belt to that braces.
    """
    from beancount_ledger import reward
    from beancount_ledger.candidate.normalise import parse_once
    from beancount_ledger.safe_parse import safe_parse
    from beancount_ledger.task import load_task

    task = load_task(ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json")
    original = (ROOT / "beancount_ledger" / "world" / "ledger.beancount").read_text(
        encoding="utf-8"
    )
    return [
        ("safe_parse", lambda t: safe_parse(t)),
        ("reward.load_ledger (archived engine)", lambda t: reward.load_ledger(t)),
        ("reward.score (archived engine)", lambda t: reward.score(t, task, original)),
        ("candidate.parse_once", lambda t: parse_once(t)),
    ]


def _hostile(prefix=""):
    return (
        'option "operating_currency" "USD"\n'
        f'{prefix}plugin "{PROBE}"\n'
        "2025-11-01 open Assets:A USD\n"
        "2025-11-01 open Assets:B USD\n"
        '2025-11-05 * "Office Depot" "x"\n'
        "  Assets:A   1.00 USD\n"
        "  Assets:B  -1.00 USD\n"
    )


def test_no_entry_point_imports_from_submitted_text():
    """Behavioural, across every entry point, in several prefix forms.

    The prefixes matter: an earlier gate required controls at column zero, and
    the loader imported the module from an indented `plugin` line anyway while
    reporting it as a syntax error. Every form the lexer tolerates is tried.
    """
    problems = []
    for name, call in _entry_points():
        for label, prefix in (("plain", ""), ("space", " "), ("tab", "\t"),
                              ("two spaces", "  "), ("bom", "﻿")):
            sys.modules.pop(PROBE, None)
            before = set(sys.modules)
            try:
                call(_hostile(prefix))
            except Exception as exc:
                problems.append(f"{name} [{label}] raised {type(exc).__name__}: {exc}")
                continue
            if PROBE in (set(sys.modules) - before):
                problems.append(f"{name} [{label}] IMPORTED {PROBE}")
    return check(
        f"no entry point imports from submitted text ({len(_entry_points())} paths x 5 forms)",
        not problems,
        "\n".join(problems),
    )


def test_the_scoring_path_refuses_and_says_why():
    """A refusal has to be legible, not just safe.

    The submission gates to zero, and the reason names the construct rather
    than reporting a generic parse failure — otherwise the environment cannot
    tell an attack from a typo, and the protocol-rejection rate stops meaning
    anything.
    """
    from beancount_ledger import reward

    entries, parse_errors, _, _ = reward.load_ledger(_hostile())
    named = bool(parse_errors) and "control.plugin" in parse_errors[0]
    return check(
        "the scoring path refuses a plugin directive with a named reason",
        named,
        f"errors: {parse_errors[:1]}",
    )


def test_the_tool_surface_is_what_we_think_it_is():
    """The severity claim depends on which tools exist.

    The write-up said an agent could get code executed because it "can write
    files". That overstated what was measured: the environment exposes six
    tools, exactly one of which mutates anything, and `write_ledger` writes
    to one fixed filename — so an agent can cause an *already-importable*
    module to be imported but cannot plant one.

    Three halves now, and all three are pinned. If a tool that writes
    arbitrary paths is ever added, this fails and the severity has genuinely
    changed; if a SECOND way to end the episode is ever added, the episode
    contract (PLAN §6: submit, or the turn limit) has changed and this fails
    too. The sixth tool, `submit`, is the terminal one: it takes no
    agent-visible argument, opens nothing and writes nothing.
    """
    from beancount_ledger import beancount_ledger as env

    problems = []
    source = (PACKAGE / "beancount_ledger.py").read_text(encoding="utf-8")
    if 'LEDGER = "ledger.beancount"' not in source or "MUTABLE_PUBLIC_FILE = LEDGER" not in source:
        problems.append("the fixed ledger name is gone")
    body = source.split("def write_ledger", 1)[-1].split("\ndef ", 1)[0]
    if "root / MUTABLE_PUBLIC_FILE" not in body or "/ path" in body:
        problems.append("write_ledger does not target the one fixed filename")

    instance = env.load_environment()
    names = set(instance.tool_map)
    if names != {"list_files", "read_file", "grep", "run_beancount", "write_ledger", "submit"}:
        problems.append(f"the tool surface is {sorted(names)}")
    if len(instance.tool_defs) != 6:
        problems.append(f"{len(instance.tool_defs)} tool definitions advertised to the model")
    if (env.WRITE_TOOL, env.TERMINAL_TOOL) != ("write_ledger", "submit"):
        problems.append(f"write/terminal names moved: {env.WRITE_TOOL}/{env.TERMINAL_TOOL}")
    mutating = [n for n in names if n in ("write_ledger",)]
    if len(mutating) != 1:
        problems.append(f"{len(mutating)} mutating tools")
    # THE SEVENTH TOOL, and only where the contract promises it. The
    # cash-application family advertises `write_cash_application` beside the
    # six; the legacy surface does not have it at all, so a legacy episode
    # that names it is answered like any name the environment never had. It
    # writes ONE fixed filename, exactly as `write_ledger` does, so the
    # severity claim above is unchanged by its existence.
    family = env.load_environment("cash_application_001")
    family_names = set(family.tool_map)
    if family_names != names | {"write_cash_application"}:
        problems.append(f"the family tool surface is {sorted(family_names)}")
    if len(family.tool_defs) != 7:
        problems.append(f"{len(family.tool_defs)} tool definitions advertised to a family episode")
    if "write_cash_application" in names:
        problems.append("the seventh tool is on the legacy surface")
    if env.WRITE_TOOLS != ("write_ledger", "write_cash_application"):
        problems.append(f"WRITE_TOOLS moved: {env.WRITE_TOOLS}")
    application_body = source.split("def write_cash_application", 1)[-1].split("\ndef ", 1)[0]
    if "root / APPLICATION_FILE" not in application_body or "/ path" in application_body:
        problems.append("write_cash_application does not target the one fixed filename")
    if 'APPLICATION_FILE = "cash_application.json"' not in source:
        problems.append("the fixed register name is gone")
    submit_body = source.split("def submit", 1)[-1].split("\ndef ", 1)[0]
    for needle in ("open(", "mkstemp", "os.replace", "unlink", "_read_public"):
        if needle in submit_body:
            problems.append(f"the terminal tool touches {needle}")
    return check(
        "six tools on the legacy surface and seven on the family's; each write name writes one fixed filename; "
        "one terminal name that touches no file",
        not problems, "\n".join(problems),
    )


def test_read_tools_grant_only_the_manifest():
    """Readability is a capability, not containment.

    The read tools first took any path — `Path(workspace) / "C:/abs"` is
    the absolute path unchanged — so the task file with the answer key was
    one guessed path away (LESSONS 22). Resolving under the workspace closed
    that and was still the wrong shape: "inside the workspace" is broader
    than the observation contract, and a receipt, a temp file, a log or a
    misplaced key inside it would be readable under containment alone. Now
    the tools accept exact manifest NAMES, the entry must be a plain regular
    file (no symlink, junction, reparse point, second hard link), and the
    open handle is re-checked. Every denial below is exercised, and the
    positive side too, so the guard is shown not to be deny-all.
    """
    import os
    import shutil
    import tempfile
    from beancount_ledger import beancount_ledger as env

    def fresh():
        ws = tempfile.mkdtemp(prefix="beancount_env_")
        shutil.copytree(env.WORLD_DIR, ws, dirs_exist_ok=True)
        return ws

    ws = fresh()
    key = (env.HERE / "tasks" / "bank_recon_001.json").resolve()
    problems = []

    # the manifest is exactly the world, and the answer key is not in it.
    # PER INSTANCE now: the manifest a rollout's read tools consult is the
    # environment's own tuple — the legacy eight, which are the mounted
    # `WORLD_DIR`, or the family's eleven — and the module constant is the
    # legacy default the direct-call door falls back to.
    world = {p.name for p in env.WORLD_DIR.iterdir() if p.is_file()}
    legacy_instance = env.load_environment()
    if set(env.PUBLIC_FILES) != world or set(legacy_instance.public_file_names) != world:
        problems.append(f"manifest != world dir: {set(env.PUBLIC_FILES) ^ world}")
    family_instance = env.load_environment("cash_application_001")
    if set(family_instance.public_file_names) != world | set(env.EXTRA_PUBLIC_FILES):
        problems.append(f"the family manifest is {sorted(family_instance.public_file_names)}")
    for manifest in (env.PUBLIC_FILES, legacy_instance.public_file_names, family_instance.public_file_names):
        if any(name.endswith(".json") for name in manifest):
            problems.append(f"a task file is in the manifest {sorted(manifest)}")

    # an undeclared file created inside the workspace is invisible
    (Path(ws) / "receipt.json").write_text('{"expected_balances": 1}', encoding="utf-8")
    try:
        key_relative = os.path.relpath(key, ws)
    except ValueError:                  # Windows: the key and the workspace on different drives (a CI runner)
        key_relative = str(key)
    denied = [str(key), key_relative, "..", ".", "", "/etc/passwd", "C:/Windows/win.ini",
              "world/../../tasks/bank_recon_001.json", "receipt.json", "./ledger.beancount",
              "Ledger.beancount", "ledger.beancount:secret", "\\\\?\\" + str(Path(ws) / "ledger.beancount"),
              "CON", "NUL", "C:ledger.beancount", Path(ws).name + "-evil/ledger.beancount", 42, None]
    for probe in denied:
        got = env.read_file(probe, workspace=ws)
        if not got.startswith("no such file"):
            problems.append(f"read_file({probe!r}) -> {got[:60]!r}")
        if probe in ("", None):
            continue  # an omitted path means "search the public set", by contract
        got = env.grep("expected_balances|open|\\[", path=probe, workspace=ws)
        if not got.startswith("no such file"):
            problems.append(f"grep(path={probe!r}) -> {got[:60]!r}")
    if "receipt.json" in env.grep("expected_balances", workspace=ws):
        problems.append("grep searched an undeclared file")
    if "receipt.json" in env.list_files(workspace=ws):
        problems.append("list_files listed an undeclared file")

    # `manifest.md` is data: listing a filename there grants nothing
    with open(Path(ws) / "manifest.md", "a", encoding="utf-8") as handle:
        handle.write("\n| `receipt.json` | private receipt |\n")
    if not env.read_file("receipt.json", workspace=ws).startswith("no such file"):
        problems.append("manifest.md granted read authority by naming a file")

    # names are unique under case-folding even though access is exact-case
    if len({n.casefold() for n in env.PUBLIC_FILES}) != len(env.PUBLIC_FILES):
        problems.append("two public names collide under case-folding")

    # the positive side, before the workspace is corrupted below
    if env.read_file(env.LEDGER, workspace=ws).startswith("no such file"):
        problems.append("a legitimate read was refused")
    if env.grep("open", path=env.LEDGER, workspace=ws) == "no matches":
        problems.append("a legitimate grep found nothing")
    if "bank_statement.csv" not in env.list_files(workspace=ws):
        problems.append("list_files does not show a public file")
    if not env.grep("x" * (env.MAX_GREP_PATTERN + 1), workspace=ws).startswith("bad pattern"):
        problems.append("an over-long pattern was accepted")

    # swap-at-open: the entry checked and the handle opened must be the SAME
    # object, not merely both plain. The seam replaces the file between
    # lstat and open with another plain single-link file.
    def swap(target):
        decoy = Path(ws) / ".decoy"
        decoy.write_bytes(b"2025-01-01 open Assets:Decoy USD\n")
        os.replace(decoy, target)
    real_seam = env._swap_seam
    env._swap_seam = swap
    try:
        got = env.read_file("accounts.csv", workspace=ws)
    finally:
        env._swap_seam = real_seam
    if not got.startswith("no such file"):
        problems.append(f"a file swapped between check and open was read: {got[:60]!r}")

    # a manifest name that is a junction to an outside directory is denied,
    # and a declared public file that is not plain is OUR failure — never a
    # silently narrower listing
    outside = tempfile.mkdtemp(prefix="beancount_outside_")
    (Path(outside) / "x.txt").write_text("x", encoding="utf-8")
    os.remove(Path(ws) / "policy.md")
    if os.name == "nt":
        # a junction is the reparse point an attacker can plant without
        # SeCreateSymbolicLinkPrivilege; a directory symlink is the POSIX twin
        import _winapi
        _winapi.CreateJunction(outside, str(Path(ws) / "policy.md"))
    else:
        os.symlink(outside, Path(ws) / "policy.md", target_is_directory=True)
    if not env.read_file("policy.md", workspace=ws).startswith("no such file"):
        problems.append("a junction under a manifest name was readable")
    try:
        env.list_files(workspace=ws)
        problems.append("list_files silently omitted a declared file that is a junction")
    except RuntimeError:
        pass

    # a manifest name that is a hard link to an outside file is denied
    secret = Path(outside) / "secret.txt"
    secret.write_text("SECRET-LINK", encoding="utf-8")
    os.remove(Path(ws) / "vendors.csv")
    os.link(secret, Path(ws) / "vendors.csv")
    if "SECRET-LINK" in env.read_file("vendors.csv", workspace=ws):
        problems.append("a hard link under a manifest name was readable")
    if "SECRET-LINK" in env.grep("SECRET", workspace=ws):
        problems.append("grep read through a hard link")

    # source-level pin: every read path reads through the one verified door
    source = (PACKAGE / "beancount_ledger.py").read_text(encoding="utf-8")
    for tool in ("def list_files", "def read_file", "def grep", "def run_beancount", "def score_core"):
        body = source.split(tool, 1)[-1].split("\ndef ", 1)[0]
        if "_read_public(" not in body or "iterdir" in body or "read_text" in body or "read_bytes" in body:
            problems.append(f"{tool} does not read through _read_public only")
    return check(
        "read tools grant exactly the manifest: paths, undeclared files, swap-at-open, junction, hard link, ADS, case all denied",
        not problems, "\n".join(problems),
    )


def test_the_family_loads_and_its_register_is_write_only():
    """`cash_application_001` is a served id like any other, and the register
    it asks for is INVISIBLE to every read tool.

    The observation surface is deliberately the evidence pack plus the
    ledger (spec section 3, "Write-only, and why"): the register is the
    agent's own answer, and reading it back would spend a bounded
    observation budget on a second copy of bytes the agent just generated.
    So `cash_application.json` has no manifest row, no `list_files` entry, no
    `read_file` and no `grep` — checked here with the file ACTUALLY ON DISK,
    written through the real tool, so this is invisibility rather than
    absence.
    """
    import shutil
    import tempfile
    from beancount_ledger import beancount_ledger as env

    problems = []
    instance = env.load_environment("cash_application_001")
    if instance.profile != env.PROFILE_CASH_APPLICATION:
        problems.append(f"the family id resolved to profile {instance.profile!r}")
    if len(instance.public_files) != 11:
        problems.append(f"{len(instance.public_files)} public files mounted, not eleven")

    # a real rollout workspace, and a register really written into it
    state = {}
    workspace = instance._workspace(state)
    token = env._PIV_STATE.set(state)
    try:
        reply = env.write_cash_application('{"schema": "piv.cash-application/1"}', workspace=workspace)
        if env.APPLICATION_FILE not in {p.name for p in Path(workspace).iterdir()}:
            problems.append("write_cash_application did not store the register")
        if "cash application" not in reply:
            problems.append(f"the write reply is {reply[:80]!r}")
        listed = env.list_files(workspace=workspace)
        if env.APPLICATION_FILE in listed:
            problems.append("list_files shows the register")
        if len(listed.strip().splitlines()) != 11:
            problems.append(f"list_files shows {len(listed.strip().splitlines())} rows, not eleven")
        for probe in (env.APPLICATION_FILE, "./" + env.APPLICATION_FILE, env.APPLICATION_FILE.upper()):
            got = env.read_file(probe, workspace=workspace)
            if not got.startswith("no such file"):
                problems.append(f"read_file({probe!r}) -> {got[:60]!r}")
        hits = env.grep("piv.cash-application", workspace=workspace)
        if env.APPLICATION_FILE in hits or "piv.cash-application/1" in hits:
            problems.append(f"grep reached the register: {hits[:120]!r}")
        got = env.grep("piv.cash-application", path=env.APPLICATION_FILE, workspace=workspace)
        if not got.startswith("no such file"):
            problems.append(f"grep(path=register) -> {got[:60]!r}")
        # ...and the three extra evidence files ARE readable, so the test is
        # about the register and not about a deny-all workspace
        for name in env.EXTRA_PUBLIC_FILES:
            if name not in listed:
                problems.append(f"{name} is missing from list_files")
            if env.read_file(name, workspace=workspace).startswith("no such file"):
                problems.append(f"{name} is not readable")
    finally:
        env._PIV_STATE.reset(token)
        shutil.rmtree(workspace, ignore_errors=True)

    # the legacy surface has no register door at all
    legacy_state = {}
    legacy = env.load_environment()
    legacy_workspace = legacy._workspace(legacy_state)
    token = env._PIV_STATE.set(legacy_state)
    try:
        if env.write_cash_application("{}", workspace=legacy_workspace) != env.APPLICATION_NOT_REQUESTED:
            problems.append("a legacy workspace accepted a register")
        if (Path(legacy_workspace) / env.APPLICATION_FILE).exists():
            problems.append("a register was stored on a legacy rollout")
    finally:
        env._PIV_STATE.reset(token)
        shutil.rmtree(legacy_workspace, ignore_errors=True)
    return check("cash_application_001 loads through the real door with eleven public files and seven tools, "
                 "and the register it asks for is invisible to list_files, read_file and grep while the three "
                 "new evidence files are not", not problems, "\n".join(problems))


def test_grep_is_literal_and_bounded_in_time():
    """A backtracking regex was a liveness hole the agent could trigger today.

    The agent controls the ledger; a valid Beancount comment can hold
    thousands of `a`s; a short `(a+)+$` then holds the worker before any
    reward is computed, and CPython's `re` cannot be interrupted while it
    holds the GIL. The contract is literal search now. Witness: a committed
    ledger with a 20,000-character comment, the pathological pattern and a
    worst-case literal both return within a second, `.` matches only dots,
    and the next tool call still executes.
    """
    import shutil
    import tempfile
    import time
    from beancount_ledger import beancount_ledger as env

    golden = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")
    ws = tempfile.mkdtemp(prefix="beancount_env_")
    shutil.copytree(env.WORLD_DIR, ws, dirs_exist_ok=True)
    problems = []
    reply = env.write_ledger(golden + "\n; " + "a" * 20000 + "!\n", workspace=ws)
    if env.parse_attestation(reply) is None:
        problems.append("the ledger with the long comment did not commit")
    for label, pattern in (("pathological regex shape", "(a+)+$"), ("worst-case literal", "a" * 100 + "b")):
        started = time.perf_counter()
        got = env.grep(pattern, workspace=ws)
        elapsed = time.perf_counter() - started
        if got != "no matches":
            problems.append(f"{label} matched: {got[:60]!r}")
        if elapsed > 1.0:
            problems.append(f"{label} took {elapsed:.2f}s")
    dots = env.grep(".", path=env.LEDGER, workspace=ws)
    contents = [line.split(": ", 1)[-1] for line in dots.splitlines() if ": " in line]
    if not contents or any("." not in c for c in contents):
        problems.append("'.' did not behave as a literal dot")
    if not env.grep("", workspace=ws).startswith("bad pattern"):
        problems.append("an empty pattern was accepted")
    if env.read_file(env.LEDGER, workspace=ws).startswith("no such file"):
        problems.append("the next tool call after the search did not execute")
    return check("grep is literal: pathological shapes cannot stall the worker; '.' is a dot; next call runs",
                 not problems, "\n".join(problems))


def test_a_broken_world_is_our_failure_not_a_narrower_observation():
    """A declared public file that is missing is world construction failing.

    Silently omitting it would hand the agent a narrower observation and
    score the result as its own. Through `_verify_public_world`, through
    `list_files`, and through the environment's own workspace creation: an
    evaluator failure, recorded.
    """
    import os
    import shutil
    import tempfile
    from beancount_ledger import beancount_ledger as env
    from beancount_ledger.beancount_ledger import load_environment

    problems = []
    ws = tempfile.mkdtemp(prefix="beancount_env_")
    shutil.copytree(env.WORLD_DIR, ws, dirs_exist_ok=True)
    os.remove(Path(ws) / "customers.csv")
    try:
        env._verify_public_world(ws)
        problems.append("a missing declared file passed verification")
    except RuntimeError:
        pass
    try:
        env.list_files(workspace=ws)
        problems.append("list_files silently omitted a missing declared file")
    except RuntimeError:
        pass

    # The workspace is seeded from the projected public files, not from a
    # directory; a projection that lost a declared file is a world we could
    # not construct, and it fails at the door that would have mounted it.
    e = load_environment()
    del e.public_files["customers.csv"]
    state = {}
    try:
        e._workspace(state)
        problems.append("_workspace accepted a broken world")
    except env.PIVEvaluatorFailed:
        pass
    if env.evaluator_failure(state) is None:
        problems.append("no evaluator record for the broken world")
    try:
        env.BeancountLedgerEnv(dataset=None, rubric=None, contract=e.contract, public_files=e.public_files)
        problems.append("the constructor accepted public files that are not exactly the manifest")
    except env.InitializationFailure:
        pass
    return check("a missing declared public file is an evaluator failure at every door, never a narrower world",
                 not problems, "\n".join(problems))


def test_the_ledger_is_observed_whole_and_the_others_in_slices():
    """`read_file(LEDGER)` is the WHOLE file, exactly as the scorer sees it.

    The task asks for the complete file back and the preservation penalties
    punish a dropped original, so an observation the agent cannot round-trip
    is a trap: measured on a live rollout (nemotron-3-ultra, train:30) that
    rebuilt the ledger from 200-line slices and lost most of its entries
    The contract is therefore exact — no line numbers, no
    "more lines" tail, no header — and it is pinned by DIGEST rather than by
    a substring, so a decorated variant fails here:

        sha256(read_file(LEDGER)) == sha256(logical_text(public bytes))

    `offset` and `limit` are ignored for it (a model that passes them out of
    habit must still get a file it can write back), every other public file
    keeps its numbered, bounded slice, and the whole read is exercised
    through the real tool-call door as well as directly. What makes one
    whole read affordable is the envelope: a mounted ledger over
    LEDGER_ENVELOPE_BYTES / _LINES is an evaluator failure at construction,
    never a rollout served a partial view.
    """
    import asyncio
    import hashlib
    import json
    import shutil
    import tempfile
    from types import SimpleNamespace
    from beancount_ledger import beancount_ledger as env
    from beancount_ledger.beancount_ledger import load_environment

    problems = []
    e = load_environment()
    state = {}
    ws = e._workspace(state)
    expected = hashlib.sha256(env.logical_text(e.public_files[env.LEDGER]).encode("utf-8")).hexdigest()

    whole = env.read_file(env.LEDGER, workspace=ws)
    if hashlib.sha256(whole.encode("utf-8")).hexdigest() != expected:
        problems.append("read_file(LEDGER) is not byte-for-byte the public file's logical text")
    if "more lines" in whole:
        problems.append("the whole read still carries a continuation tail")
    if whole.splitlines()[0] != env.logical_text(e.public_files[env.LEDGER]).splitlines()[0]:
        problems.append(f"the first line is decorated: {whole.splitlines()[0]!r}")
    if any(line[:5].strip().isdigit() and line[5:7] == "  " for line in whole.splitlines()[:5]):
        problems.append("the whole read is line-numbered")

    # offset/limit are ignored for the ledger, whatever the agent passes
    for label, kwargs in (("huge offset", {"offset": 10 ** 40}), ("limit 1", {"limit": 1}),
                          ("both", {"offset": 10 ** 40, "limit": 1}), ("negative offset", {"offset": -7})):
        got = env.read_file(env.LEDGER, workspace=ws, **kwargs)
        if got != whole:
            problems.append(f"{label}: the ledger was not returned whole ({len(got)} vs {len(whole)} chars)")

    # the real tool-call door: `update_tool_args` injects the workspace
    call = SimpleNamespace(id="r1", name="read_file", arguments=json.dumps({"path": env.LEDGER}))
    replies = asyncio.run(e.env_response(
        [SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))
    if not replies or replies[0].content != whole:
        problems.append(f"through env_response the ledger read differs: {(replies[0].content[:60] if replies else None)!r}")
    if env.evaluator_failure(state) is not None:
        problems.append("the whole read quarantined the rollout")

    # every other public file keeps the numbered, bounded slice
    numbered = env.read_file("policy.md", workspace=ws)
    if not numbered.startswith("    1  "):
        problems.append(f"policy.md is not numbered: {numbered[:20]!r}")
    if env.read_file("policy.md", offset=10 ** 40, workspace=ws).strip():
        problems.append("policy.md's offset is not clamped past the end")
    # no shipped public file is over MAX_READ_LINES, so plant one under a
    # declared name and witness the tail rather than asserting nothing
    long_ws = tempfile.mkdtemp(prefix="beancount_env_")
    shutil.copytree(env.WORLD_DIR, long_ws, dirs_exist_ok=True)
    (Path(long_ws) / "bank_statement.csv").write_text(
        "".join(f"row{n}\n" for n in range(env.MAX_READ_LINES + 60)), encoding="utf-8")
    sliced = env.read_file("bank_statement.csv", workspace=long_ws)
    if not sliced.startswith("    1  row0"):
        problems.append(f"a long public file is not numbered from 1: {sliced[:20]!r}")
    if not sliced.endswith(f"... [60 more lines; use offset to continue]"):
        problems.append(f"a long public file lost its continuation tail: {sliced[-60:]!r}")
    if len(sliced.splitlines()) != env.MAX_READ_LINES + 1:
        problems.append(f"a long public file returned {len(sliced.splitlines())} lines, not {env.MAX_READ_LINES} + tail")

    # an over-envelope ledger is refused at construction, never served
    if env.ledger_envelope_breach(e.public_files[env.LEDGER]) is not None:
        problems.append("the shipped world is already outside the envelope")
    oversize = b"; " + b"x" * env.LEDGER_ENVELOPE_BYTES + b"\n"
    if env.ledger_envelope_breach(oversize) is None:
        problems.append("the byte envelope does not bite")
    if env.ledger_envelope_breach(b"\n" * (env.LEDGER_ENVELOPE_LINES + 1)) is None:
        problems.append("the line envelope does not bite")
    big_ws = tempfile.mkdtemp(prefix="beancount_env_")
    shutil.copytree(env.WORLD_DIR, big_ws, dirs_exist_ok=True)
    (Path(big_ws) / env.LEDGER).write_bytes(oversize)
    try:
        env._verify_public_world(big_ws)
        problems.append("an over-envelope ledger passed world verification")
    except RuntimeError:
        pass
    e2 = load_environment()
    e2.public_files[env.LEDGER] = oversize
    over_state = {}
    try:
        e2._workspace(over_state)
        problems.append("_workspace mounted an over-envelope world")
    except env.PIVEvaluatorFailed:
        pass
    if env.evaluator_failure(over_state) is None:
        problems.append("no evaluator record for the over-envelope world")

    # ...and the serving door refuses it before an environment exists at all
    real = env.load_contract

    def poisoned(inputs):
        loaded = real(inputs)
        files = dict(inputs.public_files)
        files[env.LEDGER] = oversize
        object.__setattr__(inputs, "public_files", tuple(files.items()))
        return loaded

    try:
        env.load_contract = poisoned
        try:
            load_environment()
            problems.append("load_environment served a world outside the ledger envelope")
        except env.InitializationFailure:
            pass
    finally:
        env.load_contract = real

    # the tool DESCRIPTION the model sees says which file is which
    description = next(d for d in e.tool_defs if d.name == "read_file").description or ""
    for needle in ("ledger.beancount", "complete", "line numbers", "slices"):
        if needle not in description:
            problems.append(f"read_file's description does not say {needle!r}: {description!r}")
    for needle in ("one complete call", "returns the complete ledger exactly as the scorer sees it",
                   "line endings are normalized to LF",
                   # the whole-file write must not silently drop entries — the point the old
                   # "Preserve every existing transaction" was making before it was read as a
                   # ban on the corrections the bookkeeping policies require
                   "carry through every transaction you are not correcting"):
        if needle not in env.SYSTEM_PROMPT:
            problems.append(f"SYSTEM_PROMPT does not say {needle!r}")
    # "exactly as stored" was true only of an LF-only ledger; `logical_text`
    # maps CRLF and CR to LF, so the claim is now the scorer-logical one
    # — and the same sentence appears in the tool docstring
    for stale in ("exactly as stored",
                  # contract 3 removed these: the policies require removing one copy of a
                  # doubled entry and re-posting a mis-keyed one, so a prompt forbidding it
                  # contradicts the tasks
                  "Preserve every existing transaction", "do not remove or rewrite entries"):
        if stale in env.SYSTEM_PROMPT or stale in description:
            problems.append(f"the {stale!r} claim survives in the prompt or the tool description")
    if "read them in slices" in env.SYSTEM_PROMPT:
        problems.append("SYSTEM_PROMPT still tells the model to read the ledger in slices")
    return check("the ledger is read whole and undecorated (digest-equal, offset/limit ignored, through the tool door); "
                 "other files stay numbered and bounded; an over-envelope ledger is refused at every door",
                 not problems, "\n".join(problems))


def test_the_ledger_write_is_exclusive_and_atomic():
    """A fixed filename is not enough if the file is a link.

    The target must be a plain regular file or absent; a hard link to an
    outside file is a workspace we did not create — an evaluator failure,
    and the outside file is never opened. The write goes through an
    exclusive temp file and an atomic replace, leaves nothing behind, and
    the committed file is a plain regular file with one link.
    """
    import os
    import shutil
    import tempfile
    from beancount_ledger import beancount_ledger as env

    golden = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")

    def fresh():
        ws = tempfile.mkdtemp(prefix="beancount_env_")
        shutil.copytree(env.WORLD_DIR, ws, dirs_exist_ok=True)
        return ws

    problems = []
    ws = fresh()
    outside = Path(tempfile.mkdtemp(prefix="beancount_outside_")) / "secret.beancount"
    outside.write_text("SECRET", encoding="utf-8")
    os.remove(Path(ws) / env.LEDGER)
    os.link(outside, Path(ws) / env.LEDGER)
    try:
        env.write_ledger(golden, workspace=ws)
        problems.append("wrote through a hard link")
    except RuntimeError:
        pass
    if outside.read_text(encoding="utf-8") != "SECRET":
        problems.append("the outside file was modified")
    if [p.name for p in Path(ws).iterdir() if p.name.startswith(".ledger-")]:
        problems.append("a temp file was left behind after the refusal")

    ws = fresh()
    receipt = env.parse_attestation(env.write_ledger(golden, workspace=ws))
    target = Path(ws) / env.LEDGER
    if receipt is None:
        problems.append("a normal write produced no receipt")
    if target.read_bytes() != golden.encode("utf-8"):
        problems.append("the committed bytes are not the submitted bytes")
    if os.lstat(target).st_nlink != 1 or not env._is_plain_file(target):
        problems.append("the committed file is not a plain single-link regular file")
    if [p.name for p in Path(ws).iterdir() if p.name.startswith(".ledger-")]:
        problems.append("a temp file was left behind after a commit")
    return check(
        "write_ledger: link target refused as ours, outside untouched, exclusive temp + atomic replace, no leftovers",
        not problems, "\n".join(problems),
    )


def test_newline_storage_changes_stored_digest_but_not_logical():
    """Same source, LF vs CRLF: stored bytes differ, logical text is one.

    The relationship is defined, not accidental: bytes are written exactly
    as submitted and `logical_text` maps CRLF/CR to LF under strict UTF-8.
    With LF-only source, submitted, stored and logical are byte-identical,
    so without domain-separated preimages the three digests would coincide
    and three facts would share one identity. And a lone surrogate is not
    text: a public rejection, no receipt, file untouched.
    """
    import shutil
    import tempfile
    from beancount_ledger import beancount_ledger as env

    golden = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")
    lf = golden.replace("\r\n", "\n")
    crlf = lf.replace("\n", "\r\n")

    def fresh():
        ws = tempfile.mkdtemp(prefix="beancount_env_")
        shutil.copytree(env.WORLD_DIR, ws, dirs_exist_ok=True)
        return ws

    receipts = [env.parse_attestation(env.write_ledger(text, workspace=fresh())) for text in (lf, crlf)]
    problems = []
    a, b = receipts
    if a is None or b is None:
        problems.append(f"receipt did not parse: {receipts}")
    else:
        if a["stored_bytes_digest"] == b["stored_bytes_digest"]:
            problems.append("stored digests equal across newline storage")
        if a["logical_text_digest"] != b["logical_text_digest"]:
            problems.append("logical digests differ across newline storage")
        if a["submitted_text_digest"] == b["submitted_text_digest"]:
            problems.append("submitted digests equal across newline storage")
        if a["profiles"] != env.DIGEST_PROFILES:
            problems.append("per-field profiles missing from the receipt")
        if len({a["stored_bytes_digest"], a["logical_text_digest"], a["submitted_text_digest"]}) != 3:
            problems.append("domain separation: two digests of the LF source coincide")
    ws = fresh()
    reply = env.write_ledger(lf + "\ud800", workspace=ws)
    if env.parse_attestation(reply) is not None or not reply.startswith("write rejected"):
        problems.append(f"lone surrogate accepted: {reply[:60]!r}")
    if (Path(ws) / env.LEDGER).read_bytes() != (env.WORLD_DIR / env.LEDGER).read_bytes():
        problems.append("a lone-surrogate write touched the file")
    if env.parse_attestation(env.write_ledger(42, workspace=ws)) is not None:
        problems.append("a non-string content produced a receipt")
    return check(
        "digests: three domains, one snapshot; CRLF changes stored not logical; non-text is a public rejection",
        not problems, "\n".join(problems),
    )


def test_artifact_store_is_bounded_and_the_stored_batch_is_pinned():
    """Fifty batches was a count cap, not a memory cap, and eviction could race the caller.

    Bytes are capped too; a just-stored batch is pinned until retrieved, so
    concurrent stores cannot turn an advertised `batch_id` into a dangling
    handle; pins are bounded; and a batch over its own cap is stored without
    trajectories, so pinned memory is bounded as well.
    """
    from beancount_ledger import beancount_ledger as env

    saved = (dict(env.QUARANTINE_ARTIFACTS), dict(env.QUARANTINE_PINNED))
    env.QUARANTINE_ARTIFACTS.clear()
    env.QUARANTINE_PINNED.clear()
    problems = []

    def rec(size, code="InfraError"):
        return [{"code": code, "output": {"metrics": {}, "completion": "x" * size}}]

    def present(bid):
        try:
            return bool(env.quarantine_artifact(bid, release=False))
        except env.ArtifactEvicted:
            return False

    try:
        env._store_artifact("pinned", rec(1000, "PIVEvaluatorFailed"))
        for i in range(env.MAX_QUARANTINE_BATCHES + 10):       # retrieved as they come
            env._store_artifact(f"b{i}", rec(1000))
            env.quarantine_artifact(f"b{i}")
        if not present("pinned"):
            problems.append("the pinned batch was evicted under count pressure")
        # a lost handle says so: evicted raises, unknown is just empty
        try:
            env.quarantine_artifact("b0")
            problems.append("an evicted batch id returned instead of raising ArtifactEvicted")
        except env.ArtifactEvicted:
            pass
        if env.quarantine_artifact("never-stored") != []:
            problems.append("an unknown batch id did not return []")
        if len(env.QUARANTINE_ARTIFACTS) > env.MAX_QUARANTINE_BATCHES:
            problems.append(f"count cap not enforced: {len(env.QUARANTINE_ARTIFACTS)}")
        big = env.MAX_ARTIFACT_BATCH_BYTES - 200
        for i in range(6):                                      # 6 × ~2MB > 8MB
            env._store_artifact(f"big{i}", rec(big))
            env.quarantine_artifact(f"big{i}")
        total = sum(v["bytes"] for v in env.QUARANTINE_ARTIFACTS.values())
        if total > env.MAX_QUARANTINE_BYTES:
            problems.append(f"byte cap not enforced: {total}")
        if not present("pinned"):
            problems.append("the pinned batch was evicted under byte pressure")
        env.quarantine_artifact("pinned")                       # retrieval releases the pin
        for i in range(6, 12):
            env._store_artifact(f"big{i}", rec(big))
            env.quarantine_artifact(f"big{i}")
        if present("pinned"):
            problems.append("a released batch survived byte pressure it should not have")
        env._store_artifact("huge", rec(env.MAX_ARTIFACT_BATCH_BYTES + 1))
        entry = env.QUARANTINE_ARTIFACTS.get("huge")
        if entry is None or not entry["truncated"] or entry["bytes"] > env.MAX_ARTIFACT_BATCH_BYTES:
            problems.append(f"an oversized batch was not stored in bounded form: {entry and entry['bytes']}")
        if not env.quarantine_artifact("huge")[0]["output"].get("piv_artifact_truncated"):
            problems.append("the bounded form is not marked as truncated")
        for i in range(env.MAX_PINNED_BATCHES + 3):             # never retrieved
            env._store_artifact(f"pin{i}", rec(10))
        if len(env.QUARANTINE_PINNED) > env.MAX_PINNED_BATCHES:
            problems.append(f"pins unbounded: {len(env.QUARANTINE_PINNED)}")
        # an expired pin no longer protects its batch
        import time
        env._store_artifact("stale", rec(1000))
        env.QUARANTINE_PINNED["stale"] = time.monotonic() - env.PIN_TTL_SECONDS - 1
        for i in range(12, 18):
            env._store_artifact(f"big{i}", rec(big))
            env.quarantine_artifact(f"big{i}")
        if present("stale"):
            problems.append("an expired pin held its batch")
        # the true maximum, pinned included
        for i in range(env.MAX_PINNED_BATCHES + 2):             # pinned AND oversized, never retrieved
            env._store_artifact(f"pinbig{i}", rec(env.MAX_ARTIFACT_BATCH_BYTES + 1))
        resident = sum(v["bytes"] for v in env.QUARANTINE_ARTIFACTS.values())
        if resident > env.MAX_RESIDENT_BYTES:
            problems.append(f"resident bytes {resident} exceed MAX_RESIDENT_BYTES {env.MAX_RESIDENT_BYTES}")
    finally:
        env.QUARANTINE_ARTIFACTS.clear()
        env.QUARANTINE_ARTIFACTS.update(saved[0])
        env.QUARANTINE_PINNED.clear()
        env.QUARANTINE_PINNED.update(saved[1])
    return check(
        "artifact store: count + byte caps, stored batch pinned until retrieved, pins and per-batch size bounded",
        not problems, "\n".join(problems),
    )


def test_the_real_tool_route_never_reaches_the_loader():
    """The authoritative witness: the actual environment route, with a trap.

    Everything else here is branch coverage. This is the test that would have
    caught the bug, because it goes through the same path the environment does
    — `write_ledger` writes the agent's text and calls `run_beancount`, which
    reaches the configured scorer — rather than through a list of entry points
    someone remembered.

    And it traps `loader.load_string` itself rather than watching `sys.modules`.
    A before/after module-set check silently passes when the target module was
    already imported, which is most of the standard library; replacing the
    function means any hidden caller fails immediately whatever is loaded.
    """
    import shutil
    import tempfile

    from beancount import loader

    from beancount_ledger import beancount_ledger as env

    workspace = tempfile.mkdtemp(prefix="entrypoint_test_")
    shutil.copytree(PACKAGE / "world", workspace, dirs_exist_ok=True)

    tripped = []
    original = loader.load_string

    def trap(*args, **kwargs):
        tripped.append("loader.load_string was called on submitted text")
        raise AssertionError("loader.load_string reached from the tool route")

    loader.load_string = trap
    try:
        results = []
        for prefix in ("", " ", "\t", "﻿"):
            results.append(env.write_ledger(_hostile(prefix), workspace=workspace))
    finally:
        loader.load_string = original

    refused = all("PARSE ERRORS" in r or "control.plugin" in r for r in results)
    return check(
        "the real write_ledger -> run_beancount route never calls the loader",
        not tripped and refused,
        "\n".join(tripped) + "\n" + "\n".join(r[:90] for r in results))


def test_the_trap_itself_works():
    """A trap that cannot fire proves nothing.

    Calls the loader deliberately and requires the trap to catch it. Without
    this, a typo in the patching above would make the test above pass for the
    worst possible reason.
    """
    from beancount import loader

    tripped = []
    original = loader.load_string

    def trap(*args, **kwargs):
        tripped.append("caught")
        raise AssertionError("trapped")

    loader.load_string = trap
    try:
        try:
            loader.load_string('option "operating_currency" "USD"\n')
        except AssertionError:
            pass
    finally:
        loader.load_string = original
    return check("the loader trap fires when the loader is called", bool(tripped))


# The one place this suite touches a private verifiers surface. RubricGroup
# does not expose its effective leaves publicly, and `_get_reward_funcs` is an
# implementation detail of verifiers 0.3.1 — so it is used exactly here, pinned
# to the version it was checked against, and a framework change fails on this
# line rather than somewhere that looks like a scoring bug.
VERIFIERS_CHECKED_AGAINST = "0.3.1"


def bound_rewards(env):
    """(func, weight) for every leaf the environment's rubric will execute.

    Both requested inventories come from this: the *effective scoring*
    leaves are those with non-zero weight; the *executable* leaves are all of
    them, since a zero-weight monitor still runs on the submission.
    """
    import verifiers as vf

    version = getattr(vf, "__version__", "?")
    if version != VERIFIERS_CHECKED_AGAINST:
        raise AssertionError(
            f"verifiers {version} is not the version this private-API access was "
            f"checked against ({VERIFIERS_CHECKED_AGAINST}); re-verify "
            f"RubricGroup._get_reward_funcs before trusting this helper"
        )
    rubric = env.rubric
    return list(zip(rubric._get_reward_funcs(), rubric._get_reward_weights()))


def test_the_production_composition_root():
    """The authoritative witness: the environment as production builds it.

    The route test above calls the tool functions directly. That is strong,
    and it is still one step short: the real environment could bind a stale
    adapter, an alternate scorer or an old wrapper, and a test that assembled
    the intended route by hand would stay green. Every component correct, the
    composition stale — the code analogue of a task file pointing at the wrong
    ground truth.

    So this goes through the public factory, `load_environment`, and never
    constructs `BeancountLedgerEnv` itself. From there:

      - the reward bound with non-zero weight must be `ledger_reward`, alone;
      - the workspace is obtained the way the environment obtains it, through
        `update_tool_args`, not by copying the world directory in the test;
      - hostile text goes in through the registered tool object;
      - the loader is trapped for the whole exchange;
      - the bound reward is then called on the resulting state and must gate
        to zero without the trap firing.

    Behaviour is primary. The scorer's identity is diagnostics, so a test does
    not pass because a name matched while the wrapper called something unsafe.
    """
    from beancount import loader

    from beancount_ledger.beancount_ledger import load_environment

    env = load_environment()
    leaves = bound_rewards(env)
    funcs = [f for f, _ in leaves]
    weights = [w for _, w in leaves]
    scoring = [f.__name__ for f, w in leaves if w]
    tools = env.tool_map

    problems = []
    if scoring != ["ledger_reward"]:
        problems.append(f"reward functions with non-zero weight: {scoring}")
    executable = [f.__name__ for f, _ in leaves]
    if "piv/evaluator_failed" not in executable:
        problems.append(f"the evaluator_failed monitor is not bound: {executable}")
    if "write_ledger" not in tools or "run_beancount" not in tools:
        problems.append(f"tools bound: {sorted(tools)}")

    tripped = []
    original = loader.load_string

    def trap(*args, **kwargs):
        tripped.append("loader.load_string reached from the composition root")
        raise AssertionError("trapped")

    state = {}
    reply, reward = "", None
    loader.load_string = trap
    try:
        args = env.update_tool_args("write_ledger", {"content": _hostile(" ")}, [], state)
        reply = tools["write_ledger"](**args)
        bound = next((f for f, w in zip(funcs, weights) if w), None)
        if bound is not None:
            reward = bound(state)
    except AssertionError:
        # The trap raised. That is the finding, not a crash: a test that dies
        # with a traceback here is a failure nobody can read, and the first
        # witness run did exactly that.
        pass
    finally:
        loader.load_string = original

    if tripped:
        problems.extend(tripped)
    if reward != 0.0:
        problems.append(f"hostile submission scored {reward}, expected 0.0")
    if "control.plugin" not in reply:
        problems.append(f"tool reply does not name the construct: {reply[:80]!r}")
    if not state.get("workspace"):
        problems.append("the environment never bound a workspace")

    return check(
        "the production composition root refuses hostile text and scores it zero",
        not problems,
        "\n".join(problems),
    )


def test_the_submission_path_is_live_end_to_end():
    """valid → hostile → valid, one environment instance, one public tool.

    The hostile witness above proves one dangerous submission is refused
    without reaching the loader. It does not prove the path is *live*: an
    always-zero scorer, a tool that never commits its input, or a reward
    reading stale state would all pass it. So this runs a sequence through
    the same instance and asserts the score moves with the submission:

      1. the correct solution scores 1.0
      2. the hostile submission scores 0.0, is refused by name, never reaches
         the loader, and leaves a different ledger on disk
      3. the correct solution scores 1.0 again — no rejection or parser state
         contaminated the next submission

    That kills four false greens at once: no-op writes, stale state,
    unconditional zero, and stateful poisoning.

    The digest binding is over the file the environment actually stored, so
    the tool result, the workspace, and what the reward parsed are shown to be
    the same bytes rather than three individually plausible objects.
    """
    import hashlib

    from beancount import loader

    from beancount_ledger.beancount_ledger import LEDGER, load_environment

    golden = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")
    env = load_environment()
    tools = env.tool_map
    bound = next(f for f, w in bound_rewards(env) if w)
    state = {}

    def submit(text):
        # Through the production loop: a direct tool call stores bytes but
        # commits nothing — the commitment is installed by `env_response`
        # after it recomputes the receipt, and only a commitment is scored.
        replies = _write_through_loop(env, state, text)
        reply = getattr(replies[0], "content", "")
        from beancount_ledger.beancount_ledger import digests_of, parse_attestation
        # The logical digest under the receipt's own profile: domain-prefixed
        # SHA-256 of the strict-UTF-8, newline-normalised text of the stored bytes.
        digest = digests_of((Path(state["workspace"]) / LEDGER).read_bytes())["logical_text_digest"]
        att = parse_attestation(reply)
        if att is None or att["logical_text_digest"] != digest:
            raise AssertionError(f"tool attested {att}, file is {digest}")
        return reply, digest, bound(state)

    tripped = []
    original = loader.load_string

    def trap(*a, **k):
        tripped.append("loader reached")
        raise AssertionError("trapped")

    loader.load_string = trap
    try:
        r1, d1, s1 = submit(golden)
        r2, d2, s2 = submit(_hostile(" "))
        r3, d3, s3 = submit(golden)
    except AssertionError:
        r1 = r2 = r3 = ""
        d1 = d2 = d3 = ""
        s1 = s2 = s3 = None
    finally:
        loader.load_string = original

    problems = []
    if tripped:
        problems.append("loader.load_string was reached during the sequence")
    if s1 != 1.0:
        problems.append(f"correct solution scored {s1}, expected 1.0")
    if s2 != 0.0:
        problems.append(f"hostile submission scored {s2}, expected 0.0")
    if "control.plugin" not in r2:
        problems.append(f"hostile reply does not name the construct: {r2[:60]!r}")
    if s3 != 1.0:
        problems.append(f"correct solution after rejection scored {s3}; state was poisoned")
    if d1 != d3:
        problems.append("the same submission stored different bytes on two writes")
    if d1 == d2:
        problems.append("hostile and correct submissions stored identical bytes — write is a no-op")

    return check(
        f"valid -> hostile -> valid through one instance: {s1} / {s2} / {s3}, digests {d1[:12]}/{d2[:12]}/{d3[:12]}",
        not problems,
        "\n".join(problems),
    )


def test_an_evaluator_failure_is_recorded_not_scored():
    """Behavioural: fault at the scorer seam, through the real environment.

    The source-level pin below says what the framework does with an
    exception. This says what *we* do about it: a valid submission is
    accepted, the scorer core is made to raise, and the sequence must show

      1. the framework-facing value is the placeholder 0.0;
      2. `state["error"]` is set — the slot that reaches RolloutOutput.error;
      3. the `evaluator_failed` monitor reports 1.0 for that rollout;
      4. a protocol rejection in a fresh rollout is a counted agent outcome:
         0.0 with NO failure record, so garbage cannot buy exclusion;
      5. a following valid rollout scores 1.0 and carries no stale record.

    No fabricated framework state: the environment supplies it, and only our
    own seam is fault-injected.
    """
    from beancount_ledger import beancount_ledger as env_mod
    from beancount_ledger.beancount_ledger import LEDGER, load_environment

    golden = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")

    def fresh():
        env = load_environment()
        leaves = dict((f.__name__, f) for f, _ in bound_rewards(env))
        return env, leaves["ledger_reward"], leaves["piv/evaluator_failed"]

    def submit(env, text):
        state = {}
        _write_through_loop(env, state, text)     # the production loop commits; a bare tool call does not
        return state

    problems = []

    # 1-3: valid submission, scorer core raises
    env, reward, failed = fresh()
    state = submit(env, golden)
    real_core = env_mod.score_core

    def broken(state):
        raise RuntimeError("injected scorer bug")

    env_mod.score_core = broken
    try:
        value = reward(state)
        flag = failed(state)
    finally:
        env_mod.score_core = real_core
    if value != 0.0:
        problems.append(f"placeholder should be 0.0, got {value}")
    marker = state.get("error")
    if not isinstance(marker, env_mod.PIVEvaluatorFailed):
        problems.append(f"state['error'] is {type(marker).__name__}, not PIVEvaluatorFailed")
    if flag != 1.0:
        problems.append(f"evaluator_failed monitor reported {flag}, expected 1.0")

    # sticky: a valid write in the SAME rollout must not wash the marker away.
    # A state-machine invariant, not a production control-flow witness:
    # scoring runs after the final turn today, so a score_core failure cannot
    # in production be followed by another write. It matters for parse-time
    # failures after parse-once, where a write CAN follow, and it is cheap to
    # hold now. The wash write goes through the real tool loop.
    failed_revision = state["error"].revision
    _write_through_loop(env, state, golden)
    after = reward(state)
    if after != 0.0 or evaluator_failed_now(failed, state) != 1.0:
        problems.append(f"marker was washed away by a later valid write: reward={after}")
    if state.get("piv_revision", 0) <= failed_revision:
        problems.append(f"revision did not advance across writes: {state.get('piv_revision')}")
    if state["error"].revision != failed_revision:
        problems.append("the marker's failed_revision drifted with later writes")

    # a prior framework error is preserved as the cause, not overwritten
    env_p, reward_p, _ = fresh()
    state_p = submit(env_p, golden)
    prior = RuntimeError("earlier framework error")
    state_p["error"] = prior
    env_mod.score_core = broken
    try:
        reward_p(state_p)
    finally:
        env_mod.score_core = real_core
    marker_p = state_p.get("error")
    if not isinstance(marker_p, env_mod.PIVEvaluatorFailed) or marker_p.prior_error_code != "RuntimeError":
        problems.append("a pre-existing error was not preserved as a bounded code")
    from verifiers.legacy.utils.error_utils import error_data
    serialised = error_data(marker_p)
    if len(serialised["error_chain_repr"]) > 400 or "earlier framework error" in serialised["error_chain_str"]:
        problems.append(f"the marker leaks the prior error object: {len(serialised['error_chain_repr'])} chars")

    # 4: protocol rejection is an agent outcome, not an evaluator failure
    env2, reward2, failed2 = fresh()
    state2 = submit(env2, _hostile(" "))
    v2, f2 = reward2(state2), failed2(state2)
    if v2 != 0.0 or f2 != 0.0 or state2.get("error") is not None:
        problems.append(
            f"protocol rejection must be a counted zero with no record: "
            f"reward={v2} failed={f2} error={state2.get('error')!r}")

    # 5: a following valid rollout is clean
    env3, reward3, failed3 = fresh()
    state3 = submit(env3, golden)
    v3, f3 = reward3(state3), failed3(state3)
    if v3 != 1.0 or f3 != 0.0 or state3.get("error") is not None:
        problems.append(f"valid rollout after a failure: reward={v3} failed={f3}")

    return check(
        "an evaluator failure is a sticky recorded placeholder; a protocol rejection is a counted zero",
        not problems,
        "\n".join(problems),
    )


def evaluator_failed_now(monitor, state):
    return monitor(state)


def _write_through_loop(env, state, content):
    """Submit a ledger the way the framework does: an assistant tool call
    handed to `env_response`. This is the production route, and it is what
    advances the revision — a direct tool call does not, by design."""
    import asyncio
    import json
    from types import SimpleNamespace

    call = SimpleNamespace(id="call-1", name="write_ledger",
                           arguments=json.dumps({"content": content}))
    assistant = SimpleNamespace(role="assistant", content="", tool_calls=[call])
    return asyncio.run(env.env_response([assistant], state))


def test_revision_advances_only_on_a_committed_write():
    """Revision is the nth ledger submission committed, not the nth tool call.

    Through the real `env_response` loop: a committed write advances it and
    records the digest the tool attested; a malformed call (arguments that are
    not JSON) and a call to a different tool do not.
    """
    import asyncio
    import json
    from types import SimpleNamespace

    from beancount_ledger.beancount_ledger import load_environment

    golden = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")
    env = load_environment()
    state = {}
    env._workspace(state)
    r0 = state.get("piv_revision")

    _write_through_loop(env, state, golden)
    r1, d1 = state.get("piv_revision"), state.get("piv_logical_text_digest")

    bad = SimpleNamespace(id="call-2", name="write_ledger", arguments="{not json")
    asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[bad])], state))
    r2 = state.get("piv_revision")
    # Episode contract 4: the call executed nothing, AND the stored call is
    # now replayable — the framework's client re-serialises `arguments`
    # verbatim into every later request, so leaving "{not json" there ended
    # the episode as a provider failure on the next turn.
    from beancount_ledger import beancount_ledger as env_mod

    replayable = bad.arguments == env_mod.MALFORMED_CALL_REPLAY_ARGUMENTS
    audited = [e for e in (state.get("piv_rejected_calls") or []) if e.get("arguments") == "{not json"]

    other = SimpleNamespace(id="call-3", name="list_files", arguments=json.dumps({}))
    asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[other])], state))
    r3 = state.get("piv_revision")

    problems = []
    if (r0, r1) != (0, 1):
        problems.append(f"committed write: {r0} -> {r1}, expected 0 -> 1")
    if not d1 or len(d1) != 64:
        problems.append(f"no full-length logical digest recorded: {d1!r}")
    if not state.get("piv_stored_bytes_digest") or not state.get("piv_submitted_text_digest"):
        problems.append("the stored-bytes and submitted-text digests were not recorded")
    if r2 != 1:
        problems.append(f"a malformed tool call advanced the revision to {r2}")
    if r3 != 1:
        problems.append(f"an unrelated tool call advanced the revision to {r3}")
    if not replayable:
        problems.append(f"the malformed call is still stored as {bad.arguments!r}; the next request "
                        "would be refused by a provider that validates function.arguments")
    if len(audited) != 1:
        problems.append(f"the raw malformed arguments are not in the audit record: "
                        f"{state.get('piv_rejected_calls')}")
    return check("revision advances only on a committed write_ledger; a malformed call executes nothing, "
                 "is stored replayable and is kept raw in the audit record", not problems,
                 "\n".join(problems))


def test_the_consequence_table_is_exhaustive_and_fails_closed():
    """Every error class in the pinned framework has an explicit row; unknown
    codes quarantine. Both halves of the fail-closed rule.
    """
    import verifiers.legacy.errors as E

    from beancount_ledger import beancount_ledger as env_mod

    framework = sorted(n for n, c in vars(E).items()
                       if isinstance(c, type) and issubclass(c, E.Error))
    missing = [n for n in framework if n not in env_mod.ERROR_CONSEQUENCES]

    scored, quarantined = env_mod.partition_rollouts([
        {"reward": 0.0, "error": {"error": "SomethingNewFromAnUpgrade", "message": "", "error_chain_repr": ""}, "metrics": {}},
        {"reward": 0.0, "error": {"error": "ToolParseError", "message": "", "error_chain_repr": ""}, "metrics": {}},
        {"reward": 0.0, "error": {"error": "ModelError", "message": "", "error_chain_repr": ""}, "metrics": {}},
    ])
    problems = []
    if missing:
        problems.append(f"framework error classes without a consequence row: {missing}")
    if len(quarantined) != 2 or not any(o.get("piv_unclassified_code") == "SomethingNewFromAnUpgrade" for o in quarantined):
        problems.append(f"unknown code did not quarantine loudly: q={len(quarantined)}")
    if len(scored) != 1 or scored[0]["error"]["error"] != "ToolParseError":
        problems.append("the agent-attributable tool error was not counted")
    return check(
        f"consequence table covers all {len(framework)} framework error classes and fails closed",
        not problems, "\n".join(problems))


def test_the_environment_quarantines_before_results_leave():
    """The stronger option: quarantine inside `generate`, not in a consumer.

    Runs the real subclass's real `generate` override through the real
    factory. Only the *framework's* `generate` — the part that needs a model
    client — is replaced, with a `GenerateOutputs` built the way the
    framework builds it (`error_data` for the error field). So what is under
    test is exactly the code that would run in production between the
    framework returning and the consumer receiving.

    Asserts on the object the consumer sees: the evaluator-failed rollout is
    gone from `outputs`, present under `metadata["piv_quarantined"]`, a
    protocol rejection at 0.0 is still counted, an unrelated framework error
    is still counted, and `avg_reward` no longer includes the placeholder.
    """
    import asyncio

    import verifiers as vf
    from verifiers.legacy.utils.error_utils import error_data

    from beancount_ledger import beancount_ledger as env_mod
    from beancount_ledger.beancount_ledger import load_environment

    ours = env_mod.PIVEvaluatorFailed("score_core", "abc", 1, RuntimeError("bug"))
    fake = {
        "outputs": [
            {"reward": 1.0, "error": None, "metrics": {}},
            {"reward": 0.0, "error": None, "metrics": {}},                    # protocol rejection
            {"reward": 0.0, "error": error_data(ours), "metrics": {"piv/evaluator_failed": 1.0}},   # ours: quarantine
            {"reward": 0.0, "error": error_data(vf.ToolParseError("malformed arguments")), "metrics": {}},
        ],
        "metadata": {"avg_reward": 0.25},
    }

    async def framework_generate(self, *a, **k):
        return {"outputs": list(fake["outputs"]), "metadata": dict(fake["metadata"])}

    env = load_environment(partial_batches=True)
    original = vf.Environment.generate
    vf.Environment.generate = framework_generate
    try:
        results = asyncio.run(env.generate(client=None, model="scripted"))
    finally:
        vf.Environment.generate = original

    import math

    outputs = results["outputs"]
    meta = results["metadata"]
    problems = []
    if len(outputs) != 3:
        problems.append(f"{len(outputs)} outputs left, expected 3")
    if not meta.get("piv_batch_id") or not env_mod.quarantine_artifact(meta["piv_batch_id"]):
        problems.append("no retrievable quarantine artifact for the batch")
    if any((o.get("error") or {}).get("error") == "PIVEvaluatorFailed" for o in outputs):
        problems.append("an evaluator-failed rollout is still in outputs")
    if meta.get("piv_quarantined_count") != 1:
        problems.append(f"quarantined count {meta.get('piv_quarantined_count')}, expected 1")
    # The survivor mean is NOT the score. It is published as a diagnostic and
    # the comparable aggregate is invalidated, because conditioning on
    # successful evaluation is selection bias an agent could exploit.
    if abs((meta.get("piv_conditional_avg_reward") or -1) - (1.0 / 3)) > 1e-9:
        problems.append(f"conditional avg {meta.get('piv_conditional_avg_reward')}, expected 1/3")
    if not (isinstance(meta.get("avg_reward"), float) and math.isnan(meta["avg_reward"])):
        problems.append(f"avg_reward {meta.get('avg_reward')!r} should be NaN when anything is quarantined")
    if meta.get("piv_raw_including_placeholders", {}).get("avg_reward") != 0.25:
        problems.append("the framework's raw aggregate was not preserved under the raw namespace")
    if meta.get("piv_status") != "RESAMPLE_REQUIRED":
        problems.append(f"generate-mode status {meta.get('piv_status')}, expected RESAMPLE_REQUIRED")
    if (meta.get("piv_attempted"), meta.get("piv_scored")) != (4, 3):
        problems.append(f"batch accounting missing: attempted={meta.get('piv_attempted')} scored={meta.get('piv_scored')}")
    if meta.get("piv_quarantine_reason_counts") != {"PIVEvaluatorFailed": 1}:
        problems.append(f"reason counts not reported: {meta.get('piv_quarantine_reason_counts')}")
    q = meta.get("piv_quarantined", [{}])[0]
    if q.get("original_index") != 2 or [o.get("piv_index") for o in outputs] != [0, 1, 3]:
        problems.append("original indices not preserved across the partition")
    if not isinstance(env, env_mod.BeancountLedgerEnv):
        problems.append("the factory did not return our subclass")
    return check(
        "generate() quarantines evaluator failures before results leave the environment",
        not problems, "\n".join(problems))


def test_quarantine_semantics_by_mode_and_edge_case():
    """The cases that decide whether the wrapper is safe, not just present.

      - nothing quarantined: status VALID and the framework's aggregates are
        left exactly as they were — a clean batch must not be disturbed;
      - evaluate mode with a quarantine: status INVALID, every reward-derived
        aggregate invalidated (NaN), raw values preserved under the raw key;
      - ALL rollouts quarantined: no division by zero, conditional average is
        None, scored is empty;
      - idempotence: a result already carrying `piv_status` passes through a
        second `generate` untouched — no double partition, no lost indices.
    """
    import asyncio
    import json
    import math

    import verifiers as vf
    from verifiers.legacy.utils.error_utils import error_data

    from beancount_ledger import beancount_ledger as env_mod
    from beancount_ledger.beancount_ledger import load_environment

    ours = env_mod.PIVEvaluatorFailed("score_core", "abc", 1, RuntimeError("bug"))

    def framework_result(outputs):
        return {
            "outputs": [dict(o) for o in outputs],
            "metadata": {"avg_reward": 0.5, "avg_metrics": {"m": 0.5}, "avg_error": 0.0,
                         "pass_at_k": {"1": 0.5}, "pass_all_k": {"1": 0.5}, "env_id": "x"},
        }

    clean = [{"reward": 1.0, "error": None, "metrics": {}}, {"reward": 0.0, "error": None, "metrics": {}}]
    mixed = [{"reward": 1.0, "error": None, "metrics": {}},
             {"reward": 0.0, "error": error_data(ours), "metrics": {"piv/evaluator_failed": 1.0}}]
    all_bad = [{"reward": 0.0, "error": error_data(ours), "metrics": {"piv/evaluator_failed": 1.0}}] * 2

    env = load_environment(partial_batches=True)
    strict = load_environment()
    original = vf.Environment.generate
    problems = []
    try:
        def run(outputs, via_evaluate=False, which=None):
            target = which or env
            async def fake(self, *a, **k):
                return framework_result(outputs)
            vf.Environment.generate = fake
            if via_evaluate:
                token = env_mod._PIV_MODE.set("evaluate")
                try:
                    return asyncio.run(target.generate(client=None, model="scripted"))
                finally:
                    env_mod._PIV_MODE.reset(token)
            return asyncio.run(target.generate(client=None, model="scripted"))

        r = run(clean)
        m = r["metadata"]
        if m.get("piv_status") != "VALID" or m.get("avg_reward") != 0.5 or "piv_raw_including_placeholders" in m:
            problems.append(f"clean batch disturbed: status={m.get('piv_status')} avg={m.get('avg_reward')}")

        # evaluate mode: RAISES, and the exception carries the bounded records
        try:
            run(mixed, via_evaluate=True)
            problems.append("evaluate with a quarantine returned instead of raising")
            m = {}
        except env_mod.PIVEvaluationBatchInvalid as exc:
            m = exc.metadata
            if exc.status != "INVALID" or len(exc.quarantined) != 1:
                problems.append(f"raised with status={exc.status} quarantined={len(exc.quarantined)}")
        if m.get("piv_status") != "INVALID":
            problems.append(f"evaluate-mode status {m.get('piv_status')}, expected INVALID")

        # generate mode without opt-in: RAISES PIVResampleRequired
        try:
            run(mixed, which=strict)
            problems.append("strict generate with a quarantine returned instead of raising")
        except env_mod.PIVResampleRequired as exc:
            if exc.status != "RESAMPLE_REQUIRED":
                problems.append(f"strict generate raised with status {exc.status}")
            if not exc.batch_id or not env_mod.quarantine_artifact(exc.batch_id):
                problems.append("the exception does not hand back a retrievable artifact")
            if "output" in json.dumps(exc.quarantined, default=str):
                problems.append("the exception embeds full quarantined outputs")

        # partial_batches must NOT weaken evaluate
        try:
            run(mixed, via_evaluate=True, which=env)   # env has partial_batches=True
            problems.append("partial_batches=True let evaluate return with a quarantine")
        except env_mod.PIVEvaluationBatchInvalid:
            pass

        # The sync evaluation door, for real. Measured: the framework's
        # `evaluate_sync` calls `generate_sync` -> `generate`, never
        # `evaluate`, so a mode set only in `evaluate` never reached it — and
        # the `run` helper above sets the mode by hand, which is structurally
        # blind to exactly that. Both environments, the real method.
        async def fake_mixed(self, *a, **k):
            return framework_result(mixed)
        vf.Environment.generate = fake_mixed
        for which, label in ((env, "partial_batches=True"), (strict, "strict")):
            try:
                which.evaluate_sync(client=None, model="scripted", num_examples=1)
                problems.append(f"evaluate_sync ({label}) returned with a quarantine")
            except env_mod.PIVResampleRequired as exc:
                problems.append(f"evaluate_sync ({label}) raised {type(exc).__name__}: the mode did not reach the sync door")
            except env_mod.PIVEvaluationBatchInvalid as exc:
                if exc.status != "INVALID":
                    problems.append(f"evaluate_sync ({label}) raised status={exc.status}, expected INVALID")
        # The exception carries a scalar summary only (by design). Shape-
        # preserving invalidation and survival of non-PIV metadata are
        # checked on the returned object of the explicit partial-batch path.
        mp = run(mixed)["metadata"]   # env has partial_batches=True -> returns
        for key in env_mod.REWARD_DERIVED_AGGREGATES:
            v = mp.get(key)
            bad = (isinstance(v, float) and not math.isnan(v)) or (isinstance(v, dict) and any(not math.isnan(x) for x in v.values()))
            if bad:
                problems.append(f"{key} not invalidated in a quarantined batch: {v!r}")
        if mp.get("piv_raw_including_placeholders", {}).get("avg_metrics") != {"m": 0.5}:
            problems.append("raw aggregates not preserved")
        if mp.get("env_id") != "x":
            problems.append("metadata not owned by PIV was disturbed")
        if "output" in json.dumps(m, default=str):
            problems.append("the exception summary embeds full outputs")

        r = run(all_bad)
        m = r["metadata"]
        if r["outputs"] or m.get("piv_conditional_avg_reward") is not None or m.get("piv_failure_rate") != 1.0:
            problems.append(f"all-quarantined batch mishandled: outputs={len(r['outputs'])} cond={m.get('piv_conditional_avg_reward')}")

        # structural idempotence: a second pass over an already-partitioned
        # result yields the same partition; and a marker cannot hide a newly
        # appended quarantinable output
        already = run(mixed)
        first_q = [q["original_index"] for q in already["metadata"]["piv_quarantined"]]
        async def fake_again(self, *a, **k):
            return already
        vf.Environment.generate = fake_again
        twice = asyncio.run(env.generate(client=None, model="scripted"))
        if [q["original_index"] for q in twice["metadata"]["piv_quarantined"]] != first_q or twice["metadata"]["piv_attempted"] != 2:
            problems.append("a second pass changed an already-partitioned result")
        if twice["metadata"].get("piv_raw_including_placeholders", {}).get("avg_metrics") != {"m": 0.5}:
            problems.append("a second pass overwrote the raw aggregates with its own NaNs")
        smuggled = dict(already)
        smuggled["outputs"] = list(already["outputs"]) + [{"reward": 0.0, "error": error_data(ours), "metrics": {"piv/evaluator_failed": 1.0}, "piv_index": 7}]
        async def fake_smuggled(self, *a, **k):
            return smuggled
        vf.Environment.generate = fake_smuggled
        rescanned = asyncio.run(env.generate(client=None, model="scripted"))
        if rescanned["metadata"]["piv_quarantined_count"] != 2:
            problems.append("a stale piv_status suppressed the rescan of a newly appended output")
    finally:
        vf.Environment.generate = original

    return check(
        "quarantine: VALID untouched / INVALID fails closed / all-quarantined safe / idempotent",
        not problems, "\n".join(problems))


def test_the_collector_adapter_quarantines_on_the_stable_code():
    """The consumer-side half: `partition_rollouts` keys on the class name.

    The framework serialises `state["error"]` as `{"error": ClassName, ...}`,
    so this is exercised with real `RolloutOutput`-shaped dicts built the way
    the framework builds them — through `error_data` — not with hand-written
    markers. A protocol rejection (reward 0.0, no error) must stay counted; an
    unrelated framework error must stay counted too, since it is not ours to
    quarantine; only our code quarantines.
    """
    from verifiers.legacy.utils.error_utils import error_data

    from beancount_ledger import beancount_ledger as env_mod

    import verifiers as vf

    ours = env_mod.PIVEvaluatorFailed("score_core", "abc", 1, RuntimeError("bug"))
    agent_parse = vf.ToolParseError("malformed tool arguments")
    wrapped = vf.ToolCallError()
    infra = vf.InfraError("sandbox died")
    outputs = [
        {"reward": 1.0, "error": None, "metrics": {"piv/evaluator_failed": 0.0}},
        {"reward": 0.0, "error": None, "metrics": {"piv/evaluator_failed": 0.0}},                    # protocol rejection
        {"reward": 0.0, "error": error_data(ours), "metrics": {"piv/evaluator_failed": 1.0}},        # ours: quarantine
        {"reward": 0.0, "error": error_data(agent_parse), "metrics": {"piv/evaluator_failed": 0.0}}, # agent's: counted
        {"reward": 0.0, "error": error_data(wrapped), "metrics": {"piv/evaluator_failed": 1.0}},     # ours, framework-wrapped: the typed projection says so
        {"reward": 0.0, "error": error_data(infra), "metrics": {"piv/evaluator_failed": 0.0}},       # infra: quarantine
    ]
    scored, quarantined = env_mod.partition_rollouts(outputs)
    codes = sorted(((o["error"] or {}).get("piv_code") or (o["error"] or {}).get("error") or "none") for o in quarantined)
    # And a ToolCallError with NO projected record: still quarantined, as an unattributed tool failure
    _, unattributed = env_mod.partition_rollouts([{"reward": 0.0, "error": error_data(vf.ToolCallError()), "metrics": {}}])
    ok = (len(scored) == 3 and codes == ["InfraError", "PIVEvaluatorFailed", "PIVEvaluatorFailed"]
          and len(unattributed) == 1)
    return check(
        "partition counts ToolParseError, quarantines ours (via typed projection) and infra; unattributed tool failure quarantined",
        ok, f"scored={len(scored)} quarantined={codes} unattributed={len(unattributed)}")


def test_a_throwing_reward_becomes_an_agent_zero_in_this_framework():
    """Pinning a framework behaviour we do not want, so its removal is loud.

    `verifiers` 0.3.1 catches any exception raised inside a reward function,
    logs it, and returns 0.0. So if `ledger_reward` ever raises — our bug, not
    the agent's — the agent is scored zero. That is precisely what
    `EvaluationFailure` exists to prevent, reintroduced one layer up by the
    harness.

    Pinned at source level rather than by execution: driving the private call
    needs a full rollout state, and a test that fabricates one is testing its
    own fixture. Reading the except-branch is the honest check — it asserts
    the exact lines that produce the behaviour, bound to the version sentinel
    above. When the framework changes this, or the wiring in roadmap item 13
    lands and `ledger_reward` can no longer raise, this fails and the note
    gets updated.

    Shape of the fix this implies: `ledger_reward` must never raise; an
    evaluator failure has to travel through state, because the exception path
    is a zero.
    """
    import inspect
    import re

    import verifiers as vf

    if getattr(vf, "__version__", "?") != VERIFIERS_CHECKED_AGAINST:
        return check("verifiers version matches the pinned behaviour", False,
                     f"got {getattr(vf, '__version__', '?')}")
    source = inspect.getsource(vf.Rubric._call_individual_reward_func)
    swallows = re.search(r"except Exception[^\n]*:\s*\n(?:[^\n]*\n){0,4}?\s*ans = 0\.0", source)
    return check(
        f"verifiers {vf.__version__} turns a raising reward function into 0.0",
        bool(swallows),
        "the except-branch no longer assigns 0.0 — update roadmap item 13 and this note",
    )


def test_what_logical_means_is_pinned_for_every_ledger_variant():
    """"Exactly as the scorer sees it" — pinned variant by variant.

    `read_file(LEDGER)` returns `logical_text(raw)`, which maps CRLF and CR to
    LF. "Exactly as stored" was therefore true only of an LF-only ledger
    Every ledger the projector builds today IS LF-only —
    the views are assembled with `"\\n".join(...)` and measured LF-only over
    the shipped world and 81 minted ones — but nothing ASSERTS it, and the
    wording must be true of what the tool does rather than of what the
    generator currently happens to produce.

    So the tool is driven over a mounted ledger in each variant and what it
    returns is pinned. That IS the definition of "logical":

      LF               unchanged
      CRLF, CR         normalised to LF, byte for byte the LF version
      no final newline preserved (no newline is added)
      blank lines      leading and trailing blank lines preserved
      BOM              preserved: a BOM is content, and the parser gate sees it
      non-ASCII        preserved, decoded as strict UTF-8

    and in every case the returned string equals `logical_text(mounted bytes)`
    and hashes to the `logical_text_digest` the scorer computes — the same
    equality the whole-read completeness proof rests on.
    """
    import asyncio
    import json
    import shutil
    import tempfile
    from types import SimpleNamespace
    from beancount_ledger import beancount_ledger as env
    from beancount_ledger.beancount_ledger import load_environment

    problems = []
    base = ('option "operating_currency" "USD"\n'
            '2025-11-01 open Assets:Bank:Checking USD\n'
            '2025-11-05 * "Café Zürich – naïve" "unicode payee"\n'
            "  Assets:Bank:Checking   1.00 USD\n"
            "  Assets:Bank:Checking  -1.00 USD\n")
    lf = base
    variants = (
        ("LF", lf.encode("utf-8"), lf),
        ("CRLF", lf.replace("\n", "\r\n").encode("utf-8"), lf),
        ("CR", lf.replace("\n", "\r").encode("utf-8"), lf),
        ("no final newline", lf.rstrip("\n").encode("utf-8"), lf.rstrip("\n")),
        ("leading blank lines", ("\n\n" + lf).encode("utf-8"), "\n\n" + lf),
        ("trailing blank lines", (lf + "\n\n").encode("utf-8"), lf + "\n\n"),
        ("UTF-8 BOM", "﻿".encode("utf-8") + lf.encode("utf-8"), "﻿" + lf),
        ("CRLF with a BOM and no final newline",
         "﻿".encode("utf-8") + lf.rstrip("\n").replace("\n", "\r\n").encode("utf-8"),
         "﻿" + lf.rstrip("\n")),
    )
    made = []
    for label, raw, expected in variants:
        workspace = tempfile.mkdtemp(prefix="beancount_env_")
        made.append(workspace)
        shutil.copytree(env.WORLD_DIR, workspace, dirs_exist_ok=True)
        (Path(workspace) / env.LEDGER).write_bytes(raw)
        got = env.read_file(env.LEDGER, workspace=workspace)
        if got != expected:
            problems.append(f"{label}: read_file returned {got!r}, pinned {expected!r}")
        if got != env.logical_text(raw):
            problems.append(f"{label}: the tool and logical_text disagree")
        if "\r" in got:
            problems.append(f"{label}: a carriage return survived into the observation")
        # the completeness proof: the returned text hashes to the digest the
        # scorer computes over the same file
        scorer = env.digests_of(raw)["logical_text_digest"]
        if env._domain_digest("logical_text_digest", got.encode("utf-8")) != scorer:
            problems.append(f"{label}: the observation does not hash to the scorer's logical digest")
        # offset/limit are still ignored for the ledger, whatever it contains
        if env.read_file(env.LEDGER, offset=3, limit=1, workspace=workspace) != got:
            problems.append(f"{label}: offset/limit changed the whole read")
        # and the whole read still goes through the real tool door
        state = {"workspace": workspace, "piv_phase": env.EpisodePhase.NO_CANDIDATE}
        e = load_environment()
        replies = asyncio.run(e.env_response(
            [SimpleNamespace(role="assistant", content="", tool_calls=[
                SimpleNamespace(id="r", name="read_file", arguments=json.dumps({"path": env.LEDGER}))])],
            state))
        if not replies or replies[0].content != expected:
            problems.append(f"{label}: through env_response the read differs")

    # what the projector actually mounts today: LF-only, so the two wordings
    # coincide for every SERVED world — the variants above are what makes the
    # tool's promise true regardless
    e = load_environment()
    mounted = e.public_files[env.LEDGER]
    if b"\r" in mounted:
        problems.append("the mounted ledger is not LF-only, and the whole-read wording assumes nothing else")
    # eight workspaces a run adds up (CLAUDE.md housekeeping); they are ours
    for workspace in made:
        shutil.rmtree(workspace, ignore_errors=True)
    return check("what read_file returns is pinned for LF / CRLF / CR / no final newline / leading and "
                 "trailing blanks / BOM / non-ASCII: line endings normalised to LF, everything else "
                 "preserved, equal to logical_text and to the scorer's logical digest",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_production_composition_root,
    test_the_submission_path_is_live_end_to_end,
    test_an_evaluator_failure_is_recorded_not_scored,
    test_the_collector_adapter_quarantines_on_the_stable_code,
    test_the_consequence_table_is_exhaustive_and_fails_closed,
    test_revision_advances_only_on_a_committed_write,
    test_the_environment_quarantines_before_results_leave,
    test_quarantine_semantics_by_mode_and_edge_case,
    test_a_throwing_reward_becomes_an_agent_zero_in_this_framework,
    test_only_one_module_may_parse_submitted_text,
    test_safe_parse_actually_is_the_door,
    test_the_trap_itself_works,
    test_read_tools_grant_only_the_manifest,
    test_the_family_loads_and_its_register_is_write_only,
    test_grep_is_literal_and_bounded_in_time,
    test_a_broken_world_is_our_failure_not_a_narrower_observation,
    test_the_ledger_is_observed_whole_and_the_others_in_slices,
    test_what_logical_means_is_pinned_for_every_ledger_variant,
    test_the_ledger_write_is_exclusive_and_atomic,
    test_newline_storage_changes_stored_digest_but_not_logical,
    test_artifact_store_is_bounded_and_the_stored_batch_is_pinned,
    test_the_real_tool_route_never_reaches_the_loader,
    test_no_entry_point_imports_from_submitted_text,
    test_the_scoring_path_refuses_and_says_why,
    test_the_tool_surface_is_what_we_think_it_is,
]


def run() -> int:
    # Windows pipes default to a legacy code page; test names carry UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
