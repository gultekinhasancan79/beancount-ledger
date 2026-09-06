"""The property suite for the seeded world generator.

`mint(namespace, index, profile)` is the only production door to a generated
task. Everything an agent ever sees is downstream of it, so the properties
that matter are properties of that function, not of any one world:

    determinism     the same (namespace, index, profile) returns equal
                    dataclasses, equal digests and identical public bytes —
                    in one process, across processes, and under three
                    PYTHONHASHSEED values (a salted `hash()` anywhere in the
                    draw would show up as a cross-process disagreement);

    isolation       every draw comes from `_rng(seed, purpose)`, so drawing
                    an unrelated purpose does not reshuffle the world. Proved
                    twice: by injecting a decoy stream into the real
                    generator and re-minting, and statically over the
                    module's own source;

    validity        160 seeds mint (which runs `check_world`, the projector's
                    exhaustive classification, the accounting invariants and
                    the independent Beancount oracle inside), leak nothing,
                    and land inside the profile they were drawn for;

    identity        the public id is a pure function of the public bytes; the
                    private seed, the namespace:index occurrence, the graph
                    digest and the environment digest reach no public file,
                    no prompt, no task id, no dataset row and no system
                    prompt; `train:i` and `eval:i` are different worlds;

    reward          through the REAL loop (write_ledger -> env_response ->
                    commit -> score_core): golden is 1.0 and COMPLETE, the
                    untouched original is 0.0 and INCOMPLETE with every item
                    unresolved, and repairing exactly one planted item lands
                    strictly between the two, renderable and incomplete;

    inferability    the public-only checker reads the mounted bytes back and
                    must find the planted repairs and nothing else;

    separation      no generated world reuses Alpine's cast or title.

`test_graph.py` proves these things about the ONE hand-authored world. This
file proves them about the population, which is where a generator fails.

    python tests/test_generator.py
"""

from __future__ import annotations

import ast
import asyncio
import collections
import dataclasses
import datetime
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:                                        # the dataset "Map:" bar is noise in a test log
    import datasets as _datasets
    _datasets.disable_progress_bar()
except Exception:                           # noqa: BLE001 - never a reason to fail the suite
    pass

# The evaluator secret, for this suite and the interpreters it spawns. A
# fixed value: determinism properties compare runs under the SAME secret.
TEST_SECRET = "5f1c7b9e2a4d6c8b0e1f3a5c7d9b2e4f6a8c0d2e4f6a8b0c1d3e5f7a9b1c3d5e"  # gitleaks:allow  (a public test constant, not a credential: determinism compares runs under one key)
os.environ.setdefault("PIV_EVAL_SECRET", TEST_SECRET)
os.environ.setdefault("PIV_DEV_UNMANIFESTED", "1")     # development: a test secret has no release manifest

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.candidate.normalise import Accepted, parse_once  # noqa: E402
from beancount_ledger.graph import generate as GEN  # noqa: E402
from beancount_ledger.graph import identify as ID  # noqa: E402
from beancount_ledger.graph import mint as MI  # noqa: E402
from beancount_ledger.graph.worlds import alpine_2025_11 as ALPINE  # noqa: E402
from repair_keys import master_names, planted_key  # noqa: E402

PROFILES = {"standard": GEN.DEFAULT_PROFILE, "hard": GEN.HARD_PROFILE}

# Alpine's cast, quoted from Codex T40's "generated worlds must avoid
# Alpine's exact names": the calibrated world's parties and its title.
ALPINE_NAMES = ("Harbor Freight Ltd", "Summit Wholesale", "Ridgeline Retail", "Northwind Supplies",
                "Cedar Property Group", "Office Depot", "Cascade Bank")

BANK = "Assets:Bank:Checking"
# planted kind -> the category the public-only checker reports it as
UNRESOLVED_STATES = {"MISSING", "STALE_ONLY", "EXTRA_PRESENT"}

HEAD = re.compile(r"^(\d{4}-\d{2}-\d{2}) [*!] ")
POST = re.compile(r"^\s+([A-Za-z][A-Za-z0-9:_\-]*)\s+(-?\d+(?:\.\d+)?)\s+[A-Z]+\s*$")


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:24]:
            print(f"      {line}")
    return ok


def note(text):
    print(f"      · {text}")


# --------------------------------------------------------------------------
# minting, cached: several properties read the same population
# --------------------------------------------------------------------------

_MINTED: dict = {}


def minted(namespace: str, index: int, profile: str = "standard"):
    key = (namespace, index, profile)
    if key not in _MINTED:
        _MINTED[key] = MI.mint(namespace, index, PROFILES[profile])
    return _MINTED[key]


def public(m) -> dict:
    """The bytes the environment mounts, decoded. Never the bundle."""
    return {name: data.decode("utf-8") for name, data in m.inputs.public_files}


def rows_of(text: str) -> list:
    """A statement's data rows: non-blank lines less the header. The opening
    balance row COUNTS — `Profile.statement_rows` says so in its docstring
    and `manifest.md` reports the same number to the agent."""
    return [line for line in text.splitlines() if line.strip()][1:]


def counterparties(files: dict) -> int:
    customers = len(rows_of(files["customers.csv"]))
    vendors = len(rows_of(files["vendors.csv"]))
    return customers + vendors + 1        # the bank is a counterparty the agent reads in accounts.csv


def digest_of_public(m) -> str:
    h = hashlib.sha256()
    for name, data in m.inputs.public_files:
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update(data)
        h.update(b"\0")
    return h.hexdigest()


# --------------------------------------------------------------------------
# 1. determinism in one process
# --------------------------------------------------------------------------

def test_minting_is_deterministic_in_process():
    """Twice in one process: equal World, equal TaskSpec, equal digests,
    identical public bytes, identical public id."""
    problems = []
    for i in range(10):
        a = MI.mint("train", i)
        b = MI.mint("train", i)
        if a.world != b.world:
            problems.append(f"train:{i}: the World dataclasses differ")
        if a.task != b.task:
            problems.append(f"train:{i}: the TaskSpec dataclasses differ")
        if a.bundle.graph_digest != b.bundle.graph_digest:
            problems.append(f"train:{i}: graph digest {a.bundle.graph_digest[:12]} != {b.bundle.graph_digest[:12]}")
        if a.bundle.mutation_plan_digest != b.bundle.mutation_plan_digest:
            problems.append(f"train:{i}: mutation plan digest differs")
        if a.inputs.view_digests != b.inputs.view_digests:
            problems.append(f"train:{i}: view digests differ")
        if a.inputs.public_files != b.inputs.public_files:
            differing = [n for (n, x), (_, y) in zip(a.inputs.public_files, b.inputs.public_files) if x != y]
            problems.append(f"train:{i}: public bytes differ in {differing}")
        if a.inputs.task_id != b.inputs.task_id:
            problems.append(f"train:{i}: task id {a.inputs.task_id} != {b.inputs.task_id}")
        if a.provenance.private_seed != b.provenance.private_seed:
            problems.append(f"train:{i}: the private seed is not a function of (namespace, index)")
    return check("mint() twice in one process: equal World and TaskSpec, equal graph/plan/view digests, identical "
                 "public bytes and public id (10 seeds)", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 2. determinism across processes and hash seeds
# --------------------------------------------------------------------------

_CHILD = r"""
import sys, json, hashlib
sys.path.insert(0, sys.argv[1])
from beancount_ledger.graph.mint import mint
rows = []
for i in range(8):
    m = mint("train", i)
    h = hashlib.sha256()
    for name, data in m.inputs.public_files:
        h.update(name.encode("utf-8")); h.update(b"\0"); h.update(data); h.update(b"\0")
    rows.append([m.inputs.task_id, h.hexdigest(), m.inputs.graph_digest])
sys.stdout.write(json.dumps(rows))
"""


def test_minting_is_deterministic_across_processes_and_hash_seeds():
    """Three fresh interpreters under three PYTHONHASHSEED values agree with
    each other and with this process. A salted `hash()`, a set iteration
    order or a dict order anywhere in the draw shows up here and nowhere
    else."""
    here = [[m.inputs.task_id, digest_of_public(m), m.inputs.graph_digest]
            for m in (minted("train", i) for i in range(8))]
    hash_seeds = ["0", "12345", str(random.randrange(1, 2 ** 32))]
    problems, runs = [], {}
    for hash_seed in hash_seeds:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        proc = subprocess.run([sys.executable, "-c", _CHILD, str(ROOT)], env=env,
                              capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            problems.append(f"PYTHONHASHSEED={hash_seed}: exit {proc.returncode}: {proc.stderr.strip()[:400]}")
            continue
        try:
            runs[hash_seed] = json.loads(proc.stdout)
        except json.JSONDecodeError:
            problems.append(f"PYTHONHASHSEED={hash_seed}: unreadable output {proc.stdout[:200]!r}")
    for hash_seed, rows in runs.items():
        for i, (child, mine) in enumerate(zip(rows, here)):
            if child != mine:
                problems.append(f"PYTHONHASHSEED={hash_seed} train:{i}: child {child} != parent {mine}")
    if len(runs) == len(hash_seeds) and not problems:
        note(f"interpreter {Path(sys.executable).parent.parent.name}; PYTHONHASHSEED "
             f"{', '.join(hash_seeds)}; 8 seeds identical on task id, public-bytes sha256 and graph digest")
    return check("mint() in three fresh interpreters under PYTHONHASHSEED 0 / 12345 / random: same task id, same "
                 "sha256 over the public bytes, same graph digest as this process (8 seeds)",
                 not problems and len(runs) == len(hash_seeds), "\n".join(problems))


# --------------------------------------------------------------------------
# 3. substream isolation
# --------------------------------------------------------------------------

def _purposes_in_source(tree) -> set:
    """Every literal purpose `_rng(seed, "...")` names in the source."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_rng" \
                and len(node.args) == 2 and isinstance(node.args[1], ast.Constant) \
                and isinstance(node.args[1].value, str):
            out.add(node.args[1].value)
    return out


def _enclosing(tree, node):
    best = None
    for candidate in ast.walk(tree):
        if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and candidate.lineno <= node.lineno <= (candidate.end_lineno or node.lineno) \
                and (best is None or candidate.lineno > best.lineno):
            best = candidate
    return best.name if best else "<module>"


def test_substreams_are_isolated():
    """Three claims. `sub_seed` separates purposes; drawing an unrelated
    purpose leaves the world untouched (injected into the real generator,
    not argued); and the generator has exactly one seeding site."""
    problems = []
    source = (ROOT / "beancount_ledger" / "graph" / "generate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    purposes = sorted(_purposes_in_source(tree))

    # (a) one purpose, one stream: distinct per purpose and per seed, pure.
    for seed in (0, 1, MI.private_seed("train", 3, bytes.fromhex(TEST_SECRET))):
        seen = {}
        for purpose in purposes + ["decoy", "parties2", ""]:
            value = MI.sub_seed(seed, purpose)
            if value in seen:
                problems.append(f"sub_seed collides: {purpose!r} and {seen[value]!r} share a stream")
            seen[value] = purpose
            if MI.sub_seed(seed, purpose) != value:
                problems.append(f"sub_seed({purpose!r}) is not a pure function")
    for purpose in purposes:
        if MI.sub_seed(11, purpose) == MI.sub_seed(12, purpose):
            problems.append(f"sub_seed({purpose!r}) does not separate two seeds")

    # (b) the decoy: the real generator, with an unrelated purpose drawn
    #     before every named one. Nothing about the world may move.
    baseline = MI.mint("train", 7)
    real_rng = GEN._rng

    def decoy_rng(seed, purpose):
        stream = real_rng(seed, "an-unrelated-purpose-nothing-uses")
        stream.random(), stream.randint(0, 99), stream.shuffle([1, 2, 3])
        return real_rng(seed, purpose)

    GEN._rng = decoy_rng
    try:
        after = MI.mint("train", 7)
    finally:
        GEN._rng = real_rng
    if after.world != baseline.world or after.task != baseline.task:
        problems.append("drawing an unrelated purpose changed the World or the TaskSpec")
    if (after.inputs.task_id, after.inputs.public_files, after.bundle.graph_digest) != \
            (baseline.inputs.task_id, baseline.inputs.public_files, baseline.bundle.graph_digest):
        problems.append("drawing an unrelated purpose changed the public bytes, the public id or the graph digest")
    if MI.mint("train", 7).world != baseline.world:
        problems.append("the generator did not recover after the decoy was removed")

    # (c) one seeding site, and no unnamed entropy anywhere in the module.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Random" \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "random":
            where = _enclosing(tree, node)
            if where != "_rng":
                problems.append(f"random.Random() constructed in {where}() at line {node.lineno}, not in _rng()")
        if isinstance(node, ast.Attribute) and node.attr in ("seed", "urandom", "now", "today", "time", "uuid4") \
                and isinstance(node.value, ast.Name) and node.value.id in ("random", "os", "time", "datetime", "date", "uuid"):
            problems.append(f"unnamed entropy {node.value.id}.{node.attr} at line {node.lineno}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "hash":
            problems.append(f"salted hash() at line {node.lineno}")
    if not purposes:
        problems.append("no literal purpose reaches _rng; the substreams cannot be audited from the source")
    if not problems:
        note(f"{len(purposes)} named purposes: {', '.join(purposes)}")
    return check("substreams are isolated: sub_seed separates every purpose and every seed, a decoy purpose drawn "
                 "inside the real generator moves nothing, and random.Random() is constructed only in _rng()",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 4. validity of the population
# --------------------------------------------------------------------------

def test_the_population_is_valid():
    """160 seeds. `mint` runs check_world, the exhaustive projection, the
    accounting invariants and the Beancount oracle before it returns, so a
    seed that mints is a seed whose books are right; what is checked here is
    the SHAPE the profile promised."""
    problems = []
    stats = {"standard": collections.Counter(), "hard": collections.Counter()}
    rows_seen = {"standard": [], "hard": []}
    parties_seen = collections.Counter()
    for profile_name, count in (("standard", 120), ("hard", 40)):
        profile = PROFILES[profile_name]
        low, high = profile.statement_rows
        for i in range(count):
            label = f"train:{i}" + ("" if profile_name == "standard" else ":hard")
            try:
                m = minted("train", i, profile_name)
            except GEN.GenerationError as exc:
                # A refusal is the generator keeping its promise (the world
                # cannot carry the profile's minimum): counted, bounded
                # below, never silently under-planted.
                stats[profile_name]["refused"] += 1
                continue
            except Exception as exc:                       # noqa: BLE001 - the seed is the finding
                problems.append(f"{label}: {type(exc).__name__}: {exc}")
                continue
            files = public(m)
            leaks = MI.literal_provenance_leaks(m)
            if leaks:
                problems.append(f"{label}: {'; '.join(leaks)}")
            planted = m.inputs.planted
            kinds = collections.Counter(p.kind for p in planted)
            stats[profile_name][tuple(sorted(kinds.items()))] += 1
            stats[profile_name][f"n={len(planted)}"] += 1
            if not (profile.planted[0] <= len(planted) <= profile.planted[1]):
                problems.append(f"{label}: {len(planted)} planted items, profile says {profile.planted}")
            for p in planted:
                if not p.evidence:
                    problems.append(f"{label}: planted item {p.id} carries no public evidence row")
                if not p.residual:
                    problems.append(f"{label}: planted item {p.id} has an empty residual")
            if len(kinds) < 2:
                problems.append(f"{label}: {len(kinds)} mutation kind(s) {sorted(kinds)}, the profile promises >= 2")
            for kind, cap in profile.max_per_kind:
                if kinds[kind] > cap:
                    problems.append(f"{label}: {kinds[kind]} {kind} items, the profile caps it at {cap}")
            n_rows = len(rows_of(files["bank_statement.csv"]))
            rows_seen[profile_name].append(n_rows)
            if not (low <= n_rows <= high):
                problems.append(f"{label}: {n_rows} statement rows (opening row counted), profile says {low}-{high}")
            if f"{n_rows} rows" not in files["manifest.md"]:
                problems.append(f"{label}: manifest.md does not report {n_rows} statement rows")
            if profile_name == "standard":
                n_parties = counterparties(files)
                parties_seen[n_parties] += 1
                if not (8 <= n_parties <= 10):
                    problems.append(f"{label}: {n_parties} counterparties, the profile shape says 8-10")
    if not problems:
        for name in ("standard", "hard"):
            rows = rows_seen[name]
            combos = {k: v for k, v in stats[name].items() if isinstance(k, tuple)}
            note(f"{name}: {len(rows)} seeds, statement rows {min(rows)}-{max(rows)}, "
                 f"{len(combos)} distinct kind mixes, planted counts "
                 f"{ {k: v for k, v in stats[name].items() if isinstance(k, str)} }")
        note(f"standard counterparties: {dict(sorted(parties_seen.items()))}")
    for name, total in (("standard", 120), ("hard", 40)):
        refused = stats[name]["refused"]
        if refused > max(1, total // 10):
            problems.append(f"{name}: {refused}/{total} seeds refused as unsupported topology — the profile is not deliverable")
    print(f"      · refused as unsupported topology: standard {stats['standard']['refused']}/120, hard {stats['hard']['refused']}/40")
    return check("120 standard + 40 hard seeds mint (world, projection, invariants and the Beancount oracle inside), "
                 "leak no provenance, plant only evidenced items with >= 2 kinds inside the profile's caps, and land "
                 "inside the profile's statement rows and counterparty count", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 5. namespaces, public identity, and what never reaches a public surface
# --------------------------------------------------------------------------

def test_namespaces_are_disjoint_and_identity_is_public_only():
    """`train:i` and `eval:i` are different worlds; the public id is a pure
    function of the public bytes; and nothing an evaluator knows — the
    private seed, the occurrence, the graph digest, the environment digest —
    reaches a file, a prompt, an id, a dataset row or the system prompt."""
    problems = []
    for i in range(10):
        t, e = minted("train", i), minted("eval", i)
        if t.provenance.private_seed == e.provenance.private_seed:
            problems.append(f"index {i}: train and eval share a private seed")
        if t.inputs.task_id == e.inputs.task_id:
            problems.append(f"index {i}: train and eval share the public id {t.inputs.task_id}")
        if t.bundle.graph_digest == e.bundle.graph_digest:
            problems.append(f"index {i}: train and eval share a graph digest")
        for m in (t, e):
            if MI.public_task_id(m.inputs) != m.inputs.task_id:
                problems.append(f"{m.provenance.namespace}:{i}: the public id is not a function of the public bytes")
            leaks = MI.literal_provenance_leaks(m)
            if leaks:
                problems.append(f"{m.provenance.namespace}:{i}: {'; '.join(leaks)}")

    # every needle an evaluator holds, against every public surface — the
    # mounted files, the prompt, the id, and the two surfaces the framework
    # itself publishes: the dataset row and the system prompt.
    for i in range(10):
        m = minted("train", i)
        loaded = K.load_contract(m.inputs)
        needles = {
            "private seed (decimal)": str(m.provenance.private_seed),
            "private seed (hex)": f"{m.provenance.private_seed:x}",
            "occurrence": f"{m.provenance.namespace}:{m.provenance.index}",
            "legacy gen id": f"gen-{m.provenance.index}",
            "graph digest": m.bundle.graph_digest,
            "mutation plan digest": m.bundle.mutation_plan_digest,
            "environment digest": loaded.environment_digest,
        }
        env = env_mod.load_environment(f"train:{i}")
        row = env.dataset[0]
        surfaces = dict(public(m))
        surfaces["prompt"] = m.inputs.prompt
        surfaces["task_id"] = m.inputs.task_id
        surfaces["dataset row"] = json.dumps({k: str(v) for k, v in row.items()})
        surfaces["system prompt"] = env.system_prompt or ""
        for label, needle in needles.items():
            if not needle:
                continue
            for surface, text in surfaces.items():
                if needle in text:
                    problems.append(f"train:{i}: {surface} carries the {label}")
        if row["answer"] != m.inputs.task_id or row["info"]["task_id"] != m.inputs.task_id:
            problems.append(f"train:{i}: the dataset row does not carry the public id")
    # Profiles are disjoint by construction too: the profile name enters the
    # layout substream, so train:i and train:i:hard never share a world (the
    # v4 sweep found three indices where the two profiles drew one world).
    for i in range(10):
        standard, hard = minted("train", i), minted("train", i, "hard")
        if standard.inputs.task_id == hard.inputs.task_id or standard.bundle.graph_digest == hard.bundle.graph_digest:
            problems.append(f"train:{i}: the standard and hard profiles minted one world")
    if not problems:
        note("dataset row, system prompt, prompt, task id and all 8 mounted files checked against 7 evaluator "
             "needles for 10 train seeds; train:i and eval:i disjoint for 10 i; train:i and train:i:hard disjoint for 10 i")
    return check("train and eval are disjoint worlds, the public id recomputes from the public bytes alone, and the "
                 "private seed / occurrence / graph digest / environment digest reach no public file, prompt, id, "
                 "dataset row or system prompt", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 6. reward ordering through the real loop
# --------------------------------------------------------------------------

def records(text: str) -> tuple:
    """(lines, [(start, stop, date, frozenset legs)]) over a ledger's text."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        head = HEAD.match(lines[i])
        if not head:
            i += 1
            continue
        j, legs = i + 1, []
        while j < len(lines) and lines[j].strip():
            posting = POST.match(lines[j])
            if posting:
                legs.append((posting.group(1), Decimal(posting.group(2))))
            j += 1
        out.append((i, j, head.group(1), frozenset(legs)))
        i = j
    return lines, out


def _legs(pairs) -> frozenset:
    return frozenset((account, Decimal(value)) for account, value in pairs)


def partial_repair(original: str, golden: str, item) -> str:
    """`original` with EXACTLY this planted item's fix applied, by editing
    the text the way an agent would: append the golden entry for an
    omission, drop one copy of a duplicate, put the right figure back for an
    alteration. Nothing else moves."""
    olines, orecs = records(original)
    glines, grecs = records(golden)

    def find(recs, legs):
        return [r for r in recs if r[2] == item.date and r[3] == legs]

    if item.kind == "omit":
        source = find(grecs, _legs(item.required))
        if len(source) != 1:
            raise AssertionError(f"{item.id}: {len(source)} golden entries match the omitted item")
        block = glines[source[0][0]:source[0][1]]
        at = _insert_at(olines, orecs, grecs, source[0])
        # A blank line on BOTH sides. `records()` closes an entry on a blank
        # line, not on the next header, so an entry appended straight after
        # the file's last posting is swallowed into the record before it —
        # which is how the last item of `train:179:hard` (an omission dated
        # 31 August, after every other entry) made the alteration on the 30th
        # unfindable and crashed `differential_sweep`.
        return "\n".join(olines[:at] + [""] + block + [""] + olines[at:]) + "\n"
    if item.kind == "duplicate":
        hits = find(orecs, _legs(item.required))
        if len(hits) != 2:
            raise AssertionError(f"{item.id}: the original carries {len(hits)} copies, not two")
        start, stop = hits[1][0], hits[1][1]
        while stop < len(olines) and not olines[stop].strip():
            stop += 1
        return "\n".join(olines[:start] + olines[stop:]) + "\n"
    if item.kind == "alter":
        hits = find(orecs, _legs(item.replaces))
        source = find(grecs, _legs(item.required))
        if len(hits) != 1 or len(source) != 1:
            raise AssertionError(f"{item.id}: {len(hits)} booked / {len(source)} golden entries match")
        block = glines[source[0][0]:source[0][1]]
        return "\n".join(olines[:hits[0][0]] + block + olines[hits[0][1]:]) + "\n"
    raise AssertionError(f"unknown planted kind {item.kind!r}")


def _insert_at(olines, orecs, grecs, source) -> int:
    """Where the golden entry belongs in the original: before the next
    golden entry the original still carries, so date order survives."""
    index = grecs.index(source)
    for following in grecs[index + 1:]:
        for record in orecs:
            if (record[2], record[3]) == (following[2], following[3]):
                return record[0]
    return len(olines)


def rollout(env, text: str) -> dict:
    """One submission through the production loop, exactly as `verifiers`
    drives it: workspace, write_ledger tool call, env_response (which
    commits), then score_core (which scores, renders and publishes)."""
    state: dict = {}
    env._workspace(state)
    call = SimpleNamespace(id="call-1", name="write_ledger", arguments=json.dumps({"content": text}))
    asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))
    if state.get("piv_committed") is None:
        return {"committed": False, "total": None}
    total = env_mod.score_core(state)
    delivery, result = state["piv_delivery"], state["piv_result"]
    workspace = Path(state["workspace"])
    manifest = json.loads((workspace / K.PUBLICATION_FILE).read_text(encoding="utf-8"))
    return {"committed": True, "total": Decimal(str(total)), "outcome": delivery.outcome,
            "renderable": delivery.renderable, "complete": bool(result and result.complete),
            "states": dict(result.allocation.item_states), "completion": manifest["completion"],
            "delivered": (workspace / env_mod.LEDGER).is_file()}


def test_reward_orders_golden_above_partial_above_original():
    problems, reported = [], []
    for selector in ("train:1", "train:2", "eval:0"):
        namespace, index = selector.split(":")
        m = minted(namespace, int(index))
        env = env_mod.load_environment(selector)
        ids = [p.id for p in m.inputs.planted]

        gold = rollout(env, m.inputs.golden_text)
        if gold["total"] != Decimal("1.0") or not gold["complete"] or not gold["renderable"] \
                or gold["outcome"] != K.OUTCOME_DELIVERED:
            problems.append(f"{selector}: golden scored {gold['total']} complete={gold['complete']} "
                            f"renderable={gold['renderable']} outcome={gold.get('outcome')}")
        if set(gold["states"].values()) != {"RESOLVED"}:
            problems.append(f"{selector}: golden left items unresolved: {gold['states']}")

        base = rollout(env, m.inputs.original_text)
        if base["total"] != Decimal("0") or base["complete"] or not base["renderable"]:
            problems.append(f"{selector}: the untouched original scored {base['total']} "
                            f"complete={base['complete']} renderable={base['renderable']}")
        if set(base["states"]) != set(ids) or not set(base["states"].values()) <= UNRESOLVED_STATES:
            problems.append(f"{selector}: the original's item states are {base['states']}, expected every item in "
                            f"{sorted(UNRESOLVED_STATES)}")

        for outcome, label in ((gold, "golden"), (base, "original")):
            if outcome["renderable"] and not outcome["delivered"]:
                problems.append(f"{selector}: {label} is renderable but no ledger was delivered")
            if outcome["completion"] != ("complete" if outcome["complete"] else "incomplete"):
                problems.append(f"{selector}: {label} manifest says {outcome['completion']}, "
                                f"result says complete={outcome['complete']}")

        for item in m.inputs.planted:
            try:
                text = partial_repair(m.inputs.original_text, m.inputs.golden_text, item)
            except AssertionError as exc:
                problems.append(f"{selector}: {exc}")
                continue
            part = rollout(env, text)
            reported.append(f"{selector} {item.kind:<9} {part['total']}")
            if not (base["total"] < part["total"] < gold["total"]):
                problems.append(f"{selector}: repairing {item.id} ({item.kind}) scored {part['total']}, not strictly "
                                f"between {base['total']} and {gold['total']}")
            if part["complete"] or not part["renderable"]:
                problems.append(f"{selector}: the partial repair of {item.id} is "
                                f"complete={part['complete']} renderable={part['renderable']}")
            if not part["delivered"]:
                problems.append(f"{selector}: the partial repair of {item.id} is renderable but nothing was delivered")
            if part["completion"] != "incomplete":
                problems.append(f"{selector}: the partial repair manifest says {part['completion']}")
            resolved = {pid for pid, st in part["states"].items() if st == "RESOLVED"}
            if resolved != {item.id}:
                problems.append(f"{selector}: repairing {item.id} resolved {sorted(resolved)}")
            stale = {pid: st for pid, st in part["states"].items() if pid != item.id}
            if not set(stale.values()) <= UNRESOLVED_STATES:
                problems.append(f"{selector}: the untouched items are {stale}")
    if not problems:
        for line in reported:
            note(f"one item repaired: {line}")
    return check("through the real loop (write_ledger -> env_response -> commit -> score_core): golden = 1.0 and "
                 "COMPLETE, the untouched original = 0.0 and INCOMPLETE with every item unresolved, one repaired "
                 "item lands strictly between — renderable, incomplete, delivered, manifest agreeing (3 seeds)",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 7. public-only identifiability
# --------------------------------------------------------------------------

def test_the_planted_repairs_are_inferable_from_the_public_bytes():
    """The checker reads the mounted bytes back — no graph, no ids — and
    must find exactly the planted repairs. `unique` alone proves nothing: a
    checker that certifies every world returns it too. What is asserted is
    the correspondence under the FULL shared repair key (Codex T42 §3) —
    kind, date, posting multiset, counterparty, booked amount and copies —
    not the (category, signed bank amount) proxy the distinct amounts used
    to make look strong."""
    problems, gaps, not_unique = [], [], []
    for i in range(30):
        m = minted("train", i)
        verdict = ID.check_identifiable(public(m), bank_account=m.world.bank_account,
                                        period_start=m.task.period.start, period_end=m.task.period.end)
        if not verdict.unique:
            not_unique.append(i)
            problems.append(f"train:{i}: NOT identifiable — {verdict.reason}")
            for ambiguity in verdict.ambiguities[:2]:
                problems.append(f"          {ambiguity}")
            continue
        names = master_names(public(m))
        want = collections.Counter(planted_key(p, names, bank_account=BANK) for p in m.inputs.planted)
        got = collections.Counter(ID.repair_key(r) for r in verdict.repairs)
        if want != got:
            missing = sorted(str(k) for k, n in (want - got).items() for _ in range(n))
            extra = sorted(str(k) for k, n in (got - want).items() for _ in range(n))
            problems.append(f"train:{i} ({m.task.period.label}): planted {missing} reported as {extra}")
        for repair in verdict.repairs:
            for p in m.inputs.planted:
                if repair.amount == next(Decimal(v) for account, v in p.required if account == BANK):
                    gaps.append(abs((ID._day(repair.date) - ID._day(p.date)).days))
    if gaps:
        note(f"repair date vs planted item date: {min(gaps)}-{max(gaps)} days "
             f"({collections.Counter(gaps).most_common(4)}); contract change B makes an omitted item's date "
             f"the bank's, which is the date the checker reads off the row")
    if not_unique:
        note(f"seeds reported NOT unique: {not_unique}")
    return check("check_identifiable over the mounted public bytes finds a unique reading whose repairs are exactly "
                 "the planted items (30 seeds, under the full shared repair key: kind, date, posting multiset, "
                 "counterparty, booked amount, copies)",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 8. golden parity
# --------------------------------------------------------------------------

def test_the_golden_books_are_the_expected_balances():
    """Beancount, through the same boundary a submission crosses, must book
    the golden text to exactly `expected_balances`; the original must not,
    on at least one scored account; and the scored accounts must be the
    residual support and nothing wider (Codex T40 refused "every account a
    recognition touches")."""
    problems, fully_moved = [], 0
    for i in range(30):
        m = minted("train", i)
        expected = dict(m.inputs.expected_balances)
        golden = parse_once(m.inputs.golden_text)
        original = parse_once(m.inputs.original_text)
        if not isinstance(golden, Accepted) or not golden.domain_valid:
            problems.append(f"train:{i}: the golden text is not accepted clean: {golden}")
            continue
        if not isinstance(original, Accepted) or not original.domain_valid:
            problems.append(f"train:{i}: the original text is not accepted clean: {original}")
            continue
        wrong = {a: (v, golden.candidate.balances.get(a, Decimal("0")))
                 for a, v in expected.items() if golden.candidate.balances.get(a, Decimal("0")) != v}
        if wrong:
            problems.append(f"train:{i}: golden balances disagree with expected_balances on {wrong}")
        support = {a for p in m.inputs.planted for a, _ in p.residual}
        if set(m.inputs.scored_accounts) != support:
            problems.append(f"train:{i}: scored accounts {sorted(m.inputs.scored_accounts)} are not the residual "
                            f"support {sorted(support)}")
        moved = [a for a in m.inputs.scored_accounts
                 if original.candidate.balances.get(a, Decimal("0")) != expected[a]]
        if not moved:
            problems.append(f"train:{i}: the original agrees with the golden on every scored account "
                            f"{sorted(m.inputs.scored_accounts)}; nothing is at stake")
        if len(moved) == len(m.inputs.scored_accounts):
            fully_moved += 1
    note(f"the original differs from the golden on EVERY scored account in {fully_moved}/30 seeds "
         f"(the property asserted is >= 1)")
    return check("Beancount books the golden text to exactly expected_balances, the original disagrees on at least "
                 "one scored account, and the scored accounts are exactly the planted residual support (30 seeds)",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 9. separation from the calibrated world
# --------------------------------------------------------------------------

def test_no_generated_world_borrows_alpine():
    """Codex T40: generated worlds must avoid Alpine's exact names and its
    title. Checked over the world objects AND the mounted bytes, because a
    name can reach a statement description without being a party."""
    problems = []
    forbidden = list(ALPINE_NAMES) + [ALPINE.WORLD.title]
    for i in range(60):
        m = minted("train", i)
        files = public(m)
        for name in forbidden:
            for party in m.world.parties:
                if party.name == name:
                    problems.append(f"train:{i}: party {name!r} is Alpine's")
            if m.world.title == name:
                problems.append(f"train:{i}: the world title is Alpine's ({name!r})")
            for file_name, text in files.items():
                if name in text:
                    problems.append(f"train:{i}: {file_name} carries Alpine's {name!r}")
    if not problems:
        note(f"60 worlds checked against {len(forbidden)} Alpine names and the title {ALPINE.WORLD.title!r}")
    return check("no generated world reuses Alpine's party names or its title, in the world or in the mounted bytes "
                 "(60 seeds)", not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# 10. realism, reported
# --------------------------------------------------------------------------

def test_realism_metrics_are_reported():
    """Reported, not asserted beyond the profile: the numbers Codex T40
    asked to see, so a regression in the amount policy or the name pools is
    visible in the log rather than inferred from a passing suite."""
    amounts, names, companies, banks = [], set(), set(), set()
    for i in range(60):
        m = minted("train", i)
        amounts += [abs(movement.amount) for movement in m.bundle.movements]
        names |= {party.name for party in m.world.parties}
        companies.add(m.world.title)
        banks.add(m.world.bank_party_id)
    with_cents = sum(1 for a in amounts if a % 1 != 0)
    off_hundred = sum(1 for a in amounts if a % 100 != 0)
    share_cents = 100.0 * with_cents / len(amounts)
    share_hundred = 100.0 * off_hundred / len(amounts)
    note(f"{len(amounts)} movement amounts over 60 seeds: {share_cents:.1f}% carry cents, "
         f"{share_hundred:.1f}% are not a multiple of 100 (target >= 80%)")
    note(f"{len(names)} distinct party names, {len(companies)} distinct company titles, "
         f"{len(banks)} distinct banks over 60 seeds (target >= 100 names)")
    note(f"non-round share {'meets' if share_cents >= 80 else 'MISSES'} 80%; "
         f"distinct names {'meet' if len(names) >= 100 else 'MISS'} 100")
    return check("realism metrics computed and reported over 60 seeds (non-round amount share, distinct party names)",
                 bool(amounts) and bool(names),
                 "no movements or no parties were collected")



CONTENT_DIGESTS = {6: "56f50db08301d1d75747a99173f32791a5261206e0ee02eb6b6d1b1d83bc23cb",
                   7: "4248be1965abbd77ba5102e50e7ed8af20e2f707788a869290c7251bdbc0c1cf",
                   8: "bc1bca1e3f40c097c18733e9e898542300f35134ae83a4cfbbf14b975e74087a",
                   9: "bc1bca1e3f40c097c18733e9e898542300f35134ae83a4cfbbf14b975e74087a"}   # per GENERATOR_VERSION: a content change without a bump fails here


def test_the_content_library_is_pinned_to_the_generator_version():
    """Every pool in content.py enters every seed's draws, so a change to
    any of them must come with a GENERATOR_VERSION bump (Codex T40; gpt-oss
    review). The digest is pinned per version; a mismatch is the bump that
    was forgotten."""
    from beancount_ledger.graph import content as C
    from beancount_ledger.graph.mint import GENERATOR_VERSION as V
    pinned = CONTENT_DIGESTS.get(V)
    ok = pinned is not None and C.content_digest() == pinned
    return check(f"content library digest is pinned for GENERATOR_VERSION {V}", ok,
                 f"version {V}: pinned {pinned}, actual {C.content_digest()} — bump the version and pin the new digest")


def test_the_seed_cannot_be_recovered_by_enumeration():
    """Codex T41: an attacker holding the generator, the public bundle, the
    public id, the namespaces and a plausible index range — but not the
    evaluator secret. Under the UNKEYED construction the public id is an
    equality oracle and the selector (hence the clean graph and the golden
    answer) is recovered by enumeration; under the production construction
    the same enumeration finds nothing, and no unkeyed door is reachable
    from `load_environment`."""
    problems = []
    victim = MI.mint_unkeyed("train", 7)
    recovered = [i for i in range(20) if MI.mint_unkeyed("train", i).inputs.task_id == victim.inputs.task_id]
    if recovered != [7]:
        problems.append(f"the unkeyed construction did not expose the selector as expected: {recovered}")
    production = MI.mint("train", 7)
    found = [i for i in range(20) if MI.mint_unkeyed("train", i).inputs.task_id == production.inputs.task_id]
    if found:
        problems.append(f"the keyed world was recovered from an unkeyed enumeration: {found}")
    other = MI.mint("train", 7, secret=bytes.fromhex("00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"))
    if other.inputs.task_id == production.inputs.task_id or other.bundle.graph_digest == production.bundle.graph_digest:
        problems.append("a different secret produced the same world")
    if not production.provenance.keyed or victim.provenance.keyed:
        problems.append("provenance does not record keying")
    try:
        MI.private_seed("train", 7, b"short")
        problems.append("a short secret was accepted")
    except ValueError:
        pass
    saved = os.environ.pop("PIV_EVAL_SECRET", None)
    try:
        home_secret = Path(os.path.expanduser("~")) / ".piv" / "eval_secret"
        if not home_secret.exists():
            try:
                env_mod.load_environment("train:7")
                problems.append("load_environment minted a generated task with no evaluator secret")
            except env_mod.InitializationFailure as exc:
                if "keyed" not in exc.reasons[0]:
                    problems.append(f"wrong refusal: {exc.reasons}")
            try:
                MI.mint("train", 7)
                problems.append("mint() minted with no evaluator secret")
            except ValueError:
                pass
        else:
            note("~/.piv/eval_secret exists on this machine; the no-secret refusal is not exercised here")
    finally:
        if saved is not None:
            os.environ["PIV_EVAL_SECRET"] = saved
    src = (ROOT / "beancount_ledger" / "beancount_ledger.py").read_text(encoding="utf-8")
    if "mint_unkeyed" in src or "unkeyed_seed" in src:
        problems.append("the production module references the unkeyed door")
    return check("seed recovery: the unkeyed construction leaks the selector by enumeration (demonstrated); the keyed "
                 "production construction does not; no secret -> refusal; no unkeyed door in production",
                 not problems, "\n".join(problems))


def test_bounded_layout_attempts_are_deterministic_and_finite():
    """Codex T41: a draw that cannot carry the profile's minimum is not a
    refusal any more — the selector is retried under the next attempt
    substream, deterministically, at most MAX_LAYOUT_ATTEMPTS times. The
    sweep sees ~0.7% of selectors land on attempt 1. Witness: (a) some
    selector under the test secret uses attempt > 0 and minting it twice
    gives the same bytes, (b) attempt 0 selectors are exactly what the raw
    generator returns for the attempt-0 substream, (c) when every attempt
    fails the exhaustion is loud, names the selector and stops at the cap."""
    problems = []
    # (a) a controlled retry: attempt 0 of train:11 is made to fail, so the
    # mint must land on attempt 1 — twice, identically — and that world must
    # be the raw generator's attempt-1 substream, not attempt 0 patched up.
    original = GEN.generate
    seed_11 = MI.private_seed("train", 11, bytes.fromhex(TEST_SECRET))
    failing = MI.sub_seed(seed_11, "profile/standard-v1/layout_attempt/0")

    def fails_on_attempt_zero(seed, profile):
        if seed == failing:
            raise GEN.GenerationError("synthetic: attempt 0 cannot carry the profile")
        return original(seed, profile)
    GEN.generate = fails_on_attempt_zero
    try:
        first = MI.mint("train", 11)
        second = MI.mint("train", 11)
    finally:
        GEN.generate = original
    if first.provenance.attempt != 1 or second.provenance.attempt != 1:
        problems.append(f"expected attempt 1 twice, saw {first.provenance.attempt} and {second.provenance.attempt}")
    if first.inputs.public_files != second.inputs.public_files or first.inputs.task_id != second.inputs.task_id:
        problems.append("the retried mint is not deterministic")
    raw_world, _ = original(MI.sub_seed(seed_11, "profile/standard-v1/layout_attempt/1"), GEN.DEFAULT_PROFILE)
    if raw_world != first.world:
        problems.append("the retried world is not the raw attempt-1 substream")
    if first.inputs.task_id == minted("train", 11).inputs.task_id:
        problems.append("attempt 1 produced the same public world as attempt 0")
    natural = [i for i in range(120) if minted("train", i).provenance.attempt > 0]
    note(f"controlled retry on train:11 landed on attempt 1 twice, identical; natural retries in train:0..119: {natural or 'none'}")
    m0 = minted("train", 0)
    if m0.provenance.attempt == 0:
        world, task = GEN.generate(MI.sub_seed(m0.provenance.private_seed, "profile/standard-v1/layout_attempt/0"), GEN.DEFAULT_PROFILE)
        if world != m0.world:
            problems.append("attempt 0 is not the raw generator's attempt-0 substream")
    calls = []
    original = GEN.generate

    def always_fails(seed, profile):
        calls.append(seed)
        raise GEN.GenerationError("synthetic: no layout")
    GEN.generate = always_fails
    try:
        MI.mint("train", 3)
        problems.append("exhaustion did not raise")
    except GEN.GenerationError as exc:
        if "train:3" not in str(exc) or "64 attempts" not in str(exc):
            problems.append(f"exhaustion message does not name the selector and the cap: {exc}")
    finally:
        GEN.generate = original
    if len(calls) != MI.MAX_LAYOUT_ATTEMPTS or len(set(calls)) != len(calls):
        problems.append(f"expected {MI.MAX_LAYOUT_ATTEMPTS} distinct attempt seeds, saw {len(calls)} ({len(set(calls))} distinct)")
    return check("bounded layout attempts: deterministic retry under the attempt substream, attempt 0 is the raw draw, "
                 "exhaustion is loud and capped at MAX_LAYOUT_ATTEMPTS distinct seeds",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# private history is observationally irrelevant (Codex T44 §1, Q1)
# --------------------------------------------------------------------------

# The two receipt fields that are NOT reward-relevant and are expected to
# move: the environment digest binds the graph digest, which is
# evaluator-private provenance and reaches no public surface; the evaluation
# receipt digest binds a per-attempt uuid and differs between two runs of
# the SAME world (asserted below, so this exclusion is not a loophole).
_PRIVATE_RECEIPT_FIELDS = ("environment_digest", "evaluation_receipt_digest")


def _restated_selector(limit: int = 24):
    """The first selector under the test secret whose omitted recognition was
    RESTATED onto the bank's date — i.e. whose private recognition date and
    public bank date actually differ, which is the only case where the
    question has content. Searched rather than pinned: the population is a
    function of the generator version and the secret, so a hard-coded index
    would rot into a vacuous pass."""
    for index in range(limit):
        for profile in ("standard", "hard"):
            m = minted("train", index, profile)
            if m.bundle.restated:
                selector = f"train:{index}" + ("" if profile == "standard" else ":hard")
                return selector, profile, m
    return None, None, None


def _remint_with(m, event):
    """The same selector, the same seed, the same attempt and the same task —
    one economic event replaced. `_finish` is the production tail: derive,
    check public uniqueness against the planted keys, derive again with the
    public id. Nothing about the mutation is allowed to skip a gate."""
    world = dataclasses.replace(m.world, events=tuple(event if e.id == event.id else e for e in m.world.events))
    return MI._finish(m.provenance.namespace, m.provenance.index, m.provenance.private_seed,
                      m.provenance.profile, world, m.task, m.provenance.attempt, m.provenance.keyed)


def _score_golden(m, selector: str) -> dict:
    """The golden deliverable through the REAL loop, for a hand-built
    `Minted`. `load_environment` is the production composition root and takes
    a selector, so the mint door is redirected to this world for exactly one
    call — every audit downstream of it (provenance leak scan, manifest
    admission, `load_contract`) still runs."""
    real = MI.mint
    MI.mint = lambda *args, **kwargs: m
    try:
        env = env_mod.load_environment(selector)
    finally:
        MI.mint = real
    state: dict = {}
    env._workspace(state)
    call = SimpleNamespace(id="call-1", name="write_ledger",
                           arguments=json.dumps({"content": m.inputs.golden_text}))
    asyncio.run(env.env_response([SimpleNamespace(role="assistant", content="", tool_calls=[call])], state))
    total = env_mod.score_core(state)
    result = state["piv_result"]
    return {"total": Decimal(str(total)), "result": result, "canonical": result.as_canonical(),
            "material": env.contract.material()}


def test_the_private_recognition_date_is_observationally_irrelevant():
    """Codex T44 §1: after contract change B, the clean graph still carries
    the pre-bank recognition date of an omitted item. This is the permanent
    negative-dependency test that it reaches nothing.

    Take a world whose omitted recognition WAS restated — its own date and
    its bank date differ, so the two dates are distinguishable — and replace
    the private date on the World's economic event, keeping the settlement
    (and therefore the bank row), every other event and the whole task
    unchanged. Re-mint through `_finish`, the production tail, and require:

        every public file byte-identical, the prompt identical, the public
        task id identical, every `PlantedSpec.date` and every `planted_key`
        tuple identical, the golden deliverable identical, and the golden
        scored through the real loop returning the same total, the same
        components and the same receipt — everything but the two fields that
        bind evaluator-private provenance, which are named and bounded.

    And the vacuity guard, without which the whole test would pass on a
    generator that ignored the mutation: moving the PUBLIC bank date changes
    the public bytes and the public id.
    """
    problems = []
    selector, profile, m = _restated_selector()
    if m is None:
        return check("the private recognition date is observationally irrelevant", False,
                     "no selector in train:0..23 has a restated omission under the test secret; "
                     "the property cannot be witnessed and the test must not pass silently")
    recognition_id, bank_date = m.bundle.restated[0]
    rec = m.bundle.recognition(recognition_id)
    event = m.world.event(rec.event_id)
    private_date = event.date
    settlement = getattr(event, "settlement", None)
    if settlement is None or settlement.cleared_on != bank_date or private_date == bank_date:
        return check("the private recognition date is observationally irrelevant", False,
                     f"{selector}: fixture drift — {recognition_id} is dated {private_date}, restated to "
                     f"{bank_date}, settlement {settlement}")
    note(f"{selector} ({profile}): {recognition_id} recognised {private_date}, banked {bank_date}")

    # ---- the mutation: the private date only ---------------------------
    # The replacement date is chosen so that its ISO string occurs NOWHERE in
    # the public bytes or the prompt of the unmutated world. A date that
    # already appears (another entry booked the same day) would make the leak
    # scan below pass for free.
    surfaces = list(dict(m.inputs.public_files).values()) + [m.inputs.prompt.encode("utf-8")]
    moved, mutant = None, None
    for back in range(2, 12):
        candidate = (datetime.date.fromisoformat(private_date) - datetime.timedelta(days=back)).isoformat()
        if any(candidate.encode("utf-8") in surface for surface in surfaces):
            continue
        moved, mutant = candidate, _remint_with(m, dataclasses.replace(event, date=candidate))
        break
    if mutant is None:
        return check("the private recognition date is observationally irrelevant", False,
                     f"{selector}: no replacement date in the fortnight before {private_date} is absent from "
                     f"the public bytes; the leak scan would be vacuous")
    after = mutant.world.event(rec.event_id)
    if after.date != moved or getattr(after, "settlement") != settlement:
        problems.append("the mutation did not move the private date, or it moved the settlement")
    if mutant.bundle.restated != m.bundle.restated:
        problems.append(f"the restatement changed: {mutant.bundle.restated} vs {m.bundle.restated}")
    if mutant.bundle.graph_digest == m.bundle.graph_digest:
        problems.append("the graph digest did not change; the mutation did not reach the world")

    if dict(mutant.inputs.public_files) != dict(m.inputs.public_files):
        differing = sorted(name for name, data in m.inputs.public_files
                           if dict(mutant.inputs.public_files).get(name) != data)
        problems.append(f"public files changed: {differing}")
    if mutant.inputs.prompt != m.inputs.prompt:
        problems.append("the prompt changed")
    if mutant.inputs.task_id != m.inputs.task_id or MI.public_task_id(mutant.inputs) != MI.public_task_id(m.inputs):
        problems.append(f"the public task id changed: {mutant.inputs.task_id} vs {m.inputs.task_id}")
    if mutant.inputs.golden_text != m.inputs.golden_text:
        problems.append("the golden deliverable changed")
    if mutant.inputs.original_text != m.inputs.original_text:
        problems.append("the opening ledger changed")
    if mutant.inputs.expected_balances != m.inputs.expected_balances:
        problems.append("the expected balances changed")
    dates_before = {p.id: p.date for p in m.inputs.planted}
    dates_after = {p.id: p.date for p in mutant.inputs.planted}
    if dates_after != dates_before:
        problems.append(f"PlantedSpec dates changed: {dates_after} vs {dates_before}")
    restated_item = [p for p in m.inputs.planted if p.recognition_id == recognition_id]
    if len(restated_item) != 1:
        problems.append(f"{recognition_id} is restated but is not exactly one planted item")
    elif restated_item[0].date != bank_date:
        problems.append(f"the restated item {restated_item[0].id} is dated {restated_item[0].date}, not the "
                        f"bank's {bank_date}")
    names = master_names(public(m))
    keys_before = sorted(planted_key(p, names, bank_account=BANK) for p in m.inputs.planted)
    keys_after = sorted(planted_key(p, master_names(public(mutant)), bank_account=BANK) for p in mutant.inputs.planted)
    if keys_after != keys_before:
        problems.append(f"planted_key tuples changed:\n  before {keys_before}\n  after  {keys_after}")

    # ---- the receipt, through the real loop ----------------------------
    before = _score_golden(m, selector)
    after_run = _score_golden(mutant, selector)
    if before["total"] != Decimal("1.0") or after_run["total"] != Decimal("1.0"):
        problems.append(f"golden did not score 1.0: {before['total']} / {after_run['total']}")
    moved_fields = sorted(k for k in before["canonical"] if before["canonical"][k] != after_run["canonical"][k])
    if moved_fields != sorted(_PRIVATE_RECEIPT_FIELDS):
        problems.append(f"the score receipt moved in {moved_fields}, not exactly {sorted(_PRIVATE_RECEIPT_FIELDS)}")
    if before["result"].reward_input_digest != after_run["result"].reward_input_digest:
        problems.append("the reward input digest — the cache and equivalence key — changed")
    # the two excluded fields, bounded rather than waved through: the
    # evaluation receipt digest already differs between two runs of the SAME
    # world (it binds a per-attempt id), and the environment digest differs
    # only through the two evaluator-private provenance fields.
    twice = _score_golden(m, selector)
    if twice["canonical"]["evaluation_receipt_digest"] == before["canonical"]["evaluation_receipt_digest"]:
        problems.append("the evaluation receipt digest is stable across runs; excluding it hides a real change")
    if twice["canonical"]["environment_digest"] != before["canonical"]["environment_digest"]:
        problems.append("the environment digest is not stable across runs of one world")
    material_moved = sorted(k for k in before["material"]
                            if before["material"][k] != after_run["material"].get(k))
    if material_moved != ["graph_digest", "task_contract_digest"]:
        problems.append(f"the environment material moved in {material_moved}, not only in the two "
                        f"evaluator-private provenance fields")
    for surface in list(dict(mutant.inputs.public_files).values()) + [mutant.inputs.prompt.encode("utf-8"),
                                                                     mutant.inputs.task_id.encode("utf-8")]:
        if moved.encode("utf-8") in surface:
            problems.append(f"the mutated private recognition date {moved} reached a public surface")
            break

    # ---- the vacuity guard: the PUBLIC bank date is observable ----------
    later = (datetime.date.fromisoformat(bank_date) + datetime.timedelta(days=1)).isoformat()
    banked = _remint_with(m, dataclasses.replace(event, settlement=dataclasses.replace(settlement, cleared_on=later)))
    if dict(banked.inputs.public_files) == dict(m.inputs.public_files):
        problems.append("moving the PUBLIC bank date changed no public byte; the test is vacuous")
    if banked.inputs.task_id == m.inputs.task_id:
        problems.append("moving the PUBLIC bank date did not change the public task id; the test is vacuous")
    if bank_date not in {p.date for p in m.inputs.planted} or later not in {p.date for p in banked.inputs.planted}:
        problems.append(f"the restated item is not dated on the bank row: {sorted(p.date for p in banked.inputs.planted)}")
    if not problems:
        note(f"private date {private_date} -> {moved}: public bytes, prompt, id, planted keys, golden and receipt all identical")
        note(f"public bank date {bank_date} -> {later}: public bytes and public id both change")
    return check("the private recognition date of a restated omission reaches no public byte, no planted key and "
                 "no score receipt; the public bank date reaches all three",
                 not problems, "\n".join(problems))


TESTS = [
    test_minting_is_deterministic_in_process,
    test_minting_is_deterministic_across_processes_and_hash_seeds,
    test_substreams_are_isolated,
    test_the_population_is_valid,
    test_namespaces_are_disjoint_and_identity_is_public_only,
    test_reward_orders_golden_above_partial_above_original,
    test_the_planted_repairs_are_inferable_from_the_public_bytes,
    test_the_golden_books_are_the_expected_balances,
    test_no_generated_world_borrows_alpine,
    test_realism_metrics_are_reported,
    test_the_content_library_is_pinned_to_the_generator_version,
    test_the_seed_cannot_be_recovered_by_enumeration,
    test_bounded_layout_attempts_are_deterministic_and_finite,
    test_the_private_recognition_date_is_observationally_irrelevant,
]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
