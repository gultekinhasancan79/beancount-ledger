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
     never touches `~/.piv/`: EVERY path it writes - the manifest, `--out`,
     and each file under `--out` - is resolved and refused if it lands inside
     `~/.piv`, before anything is created.
  2. Writes `run.json` as a START record (started_at, package, runtime, the
     files it intends to write) before any other work, so a run that dies
     still leaves the record of what started it. The same file is finalized
     at the end, or marked aborted with the exception that ended it.
  3. Checks that the installed generator IS the frozen one, in its PORTABLE
     part: the live declared literals (population, profile digest, gate-set
     digest, split-map digest, catalogue, versions, limits) must equal the
     declaration's in `frozen_declaration.json` beside this script, and the
     package's own freeze must be self-consistent (`freeze_problems()` empty,
     `declared_matches_live` true). A mismatch there is a different
     generator, and the run stops before minting. The WHOLE-freeze digest is
     a different thing: it also covers the native runtime (interpreter
     version, operating system, machine, Unicode database), so it is
     RECORDED beside the reference runtime's digest with an equal/different
     flag and never demanded. On the reference runtime it is equal; on
     another interpreter or operating system it differs, and that
     difference is a runtime, not a generator. The manifest's own runtime
     checks at the serving door are untouched by this and still apply.
  4. Mints the declared groups - the first N per mechanism stratum in the
     roster's declared order (a prefix, never a sample), or all 96 with
     `--all` - against one population ledger, exactly as the published census
     was taken. Exhausted groups are named, not replaced.
  5. Writes `census.json` - the COMPLETE attempt census: every group's every
     attempt with its ordinal, stage, outcome, codes, witness, baseline,
     reading counts, component digest and content digests, plus the
     per-group public ids and content digests of the admitted groups -
     BEFORE the manifest is signed and before any serving. Whatever happens
     next, the census of what was minted is on disk.
  6. Signs one record per variant into YOUR manifest under YOUR key.
  7. Serves EVERY signed variant through the real `beancount_ledger.
     load_environment` and the real `env.evaluate()` door with a scripted
     offline client that delivers the package's own golden ledger and golden
     register, and requires: reward 1.0, completion `complete`, register
     `delivered`, the served public id equal to the record's, the episode
     profile `cash_application`, and the served episode-contract digest equal
     to what the AUTHORED task `cash_application_001` serves under. One line
     per variant is appended to `serving.jsonl` the moment its episode ends -
     a failed check or an exception included, caught per variant and named -
     and flushed to disk before the next episode starts, so an interrupted
     run keeps every outcome it reached.
  8. Writes `serving.json` as the summary of that log and finalizes
     `run.json`.

EXIT CODES. 0: every declared group admitted and every variant served.
1: a group exhausted or a variant did not serve (both named in the records).
2: the environment was refused (a setting missing or malformed, or a write
target inside `~/.piv`). 3: the package in front of you is not the frozen
generator.

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
import dataclasses
import datetime as _dt
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
DECLARATION = HERE / "frozen_declaration.json"

REQUIRED_ENV = ("PIV_EVAL_SECRET", "PIV_KEY_ID", "PIV_CASH_APPLICATION_MANIFEST")
HOME_PIV = Path(os.path.expanduser("~")) / ".piv"
OUTPUT_FILES = ("run.json", "census.json", "serving.jsonl", "serving.json")


def refuse(message: str, code: int = 2) -> "NoReturn":  # noqa: F821
    print(f"REFUSED: {message}", file=sys.stderr)
    raise SystemExit(code)


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f": {detail}" if detail else ""))
    return ok


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def outside_piv(label: str, path) -> Path:
    """`path` resolved, or a refusal if it lands anywhere under `~/.piv`.

    Every path this script writes goes through here BEFORE anything is
    created - the manifest, `--out`, and each file under it - so the promise
    "never touches ~/.piv" is checked on every write target rather than
    asserted for one of them. A path that cannot be resolved is refused too:
    a target this script cannot place is not known to be outside.
    """
    try:
        resolved = Path(path).expanduser().resolve()
        home_piv = HOME_PIV.resolve()
    except OSError as exc:
        refuse(f"{label} {path!s} could not be resolved ({exc}); a write target this script cannot place "
               f"is not known to be outside ~/.piv")
    if resolved == home_piv or resolved.is_relative_to(home_piv):
        refuse(f"{label} resolves to {resolved}, inside ~/.piv; this script writes only where you name "
               f"explicitly outside it, so a production manifest or secret is never touched by a check")
    return resolved


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
    outside_piv("PIV_CASH_APPLICATION_MANIFEST", os.environ["PIV_CASH_APPLICATION_MANIFEST"])


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
                 "it can lag pyproject.toml, so the portable freeze check below is the binding identity"),
        "library_versions": env_mod.library_versions(),
        "runtime": {"implementation": platform.python_implementation(), "version": platform.python_version(),
                    "system": platform.system(), "machine": platform.machine(),
                    "unicode_database": unicodedata.unidata_version},
    }


# --- the pack's declaration, whichever layout it is in -----------------------

_HEX32 = re.compile(r"^[0-9a-f]{32}$")
# A dict carrying all four of these IS the declared-literal block: nothing
# else in the declaration names the population beside its digests.
DECLARED_MARKERS = ("development_population", "gate_set_digest", "split_map_digest", "profile_digest")
RUNTIME_MARKERS = ("implementation", "version", "system", "machine")
# Named locations, tried first: the original layout, then the revised one
# that separates the portable literals from the runtime-bound attestation.
DECLARED_PATHS = ("family_freeze/declared", "portable/family_freeze/declared", "portable/declared",
                  "portable/declared_literals", "portable")
DIGEST_PATHS = ("family_freeze/digest", "reference_runtime_attestation/whole_freeze_digest",
                "reference_runtime_attestation/freeze_digest", "reference_runtime_attestation/digest")
RUNTIME_PATHS = ("reference_runtime_attestation/runtime", "reference_runtime_attestation/native_runtime",
                 "reference_runtime_attestation/runtime_scope/native_runtime")


def _walk(node, path=()):
    """Every (path, value) in a JSON tree, depth first, keys in sorted order."""
    yield path, node
    if isinstance(node, dict):
        for key in sorted(node):
            yield from _walk(node[key], path + (key,))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from _walk(item, path + (str(i),))


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True)


def _load_declaration_inner() -> dict:
    """The declaration's declared literals, its reference whole-freeze digest
    and (when it names one) the reference runtime, whichever layout the file
    is in.

    Two layouts are read. The original keeps both under `family_freeze`
    (`declared`, `digest`). The revised one separates them: the portable
    literals under a `portable` block, the runtime-bound digest under a
    `reference_runtime_attestation` block. The reader takes the named
    locations first and otherwise searches the tree for a dict carrying the
    declared-literal markers and for a 32-hex `digest`/`freeze_digest`
    OUTSIDE that dict (the literals carry 32-hex digests of their own). More
    than one distinct candidate for either is refused: guessing between two
    declarations is worse than stopping.
    """
    try:
        body = json.loads(DECLARATION.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        refuse(f"{DECLARATION} is unreadable ({exc}); the pack's declaration is the reference this check "
               f"runs against", code=3)
    tree = list(_walk(body))
    by_path = {"/".join(path): node for path, node in tree}

    # the declared literals
    literal_blocks = {"/".join(path): node for path, node in tree
                      if isinstance(node, dict) and all(marker in node for marker in DECLARED_MARKERS)}
    named = [p for p in DECLARED_PATHS if p in literal_blocks]
    if named:
        declared_path = named[0]
    elif len({_canonical(v) for v in literal_blocks.values()}) == 1:
        declared_path = sorted(literal_blocks)[0]
    elif not literal_blocks:
        refuse(f"{DECLARATION.name} carries no declared-literal block (a dict with "
               f"{', '.join(DECLARED_MARKERS)}); nothing to hold the live freeze to", code=3)
    else:
        refuse(f"{DECLARATION.name} carries {len(literal_blocks)} DIFFERENT declared-literal blocks "
               f"({', '.join(sorted(literal_blocks))}); refusing to guess which one is the reference", code=3)
    declared = literal_blocks[declared_path]

    # the reference whole-freeze digest: a 32-hex value under a key named
    # `digest` or `*freeze_digest`, not inside any declared-literal block
    inside_literals = tuple(p + "/" for p in literal_blocks)
    digests = {"/".join(path): node for path, node in tree
               if path and isinstance(node, str) and _HEX32.match(node)
               and (path[-1] == "digest" or path[-1].endswith("freeze_digest"))
               and not "/".join(path).startswith(inside_literals)}
    named = [p for p in DIGEST_PATHS if p in digests]
    if named:
        digest_path = named[0]
    elif len(set(digests.values())) == 1:
        digest_path = sorted(digests)[0]
    elif not digests:
        refuse(f"{DECLARATION.name} carries no reference whole-freeze digest (a 32-hex `digest` or "
               f"`freeze_digest` outside the declared literals)", code=3)
    else:
        refuse(f"{DECLARATION.name} carries {len(digests)} DIFFERENT 32-hex freeze digests "
               f"({', '.join(sorted(digests))}); refusing to guess which one is the reference", code=3)

    # the reference runtime, when the declaration names one; the original
    # layout does not, and says so in the record rather than inventing one
    runtimes = {p: by_path[p] for p in RUNTIME_PATHS if isinstance(by_path.get(p), dict)}
    if not runtimes:
        runtimes = {"/".join(path): node for path, node in tree
                    if isinstance(node, dict) and all(m in node for m in RUNTIME_MARKERS)
                    and ("reference" in "/".join(path) or "attestation" in "/".join(path))}
    runtime_path = sorted(runtimes)[0] if runtimes else None
    layout = ("family_freeze" if declared_path == "family_freeze/declared" and digest_path == "family_freeze/digest"
              else "portable+reference_runtime_attestation"
              if declared_path.startswith("portable/") and digest_path.startswith("reference_runtime_attestation/")
              else "searched")
    return {
        "file": str(DECLARATION), "schema": body.get("schema") if isinstance(body, dict) else None,
        "layout": layout, "declared_path": declared_path, "declared": declared,
        "reference_freeze_digest": digests[digest_path], "reference_digest_path": digest_path,
        "reference_runtime": runtimes.get(runtime_path) if runtime_path else None,
        "reference_runtime_path": runtime_path,
    }


def load_declaration() -> dict:
    """`_load_declaration_inner()` plus the per-Unicode-database rows the
    declaration pins (`portable.runtime_scoped_by_unicode_database.rows`),
    when it carries them, so an unpinned database can be refused by name."""
    found = _load_declaration_inner()
    try:
        raw = json.loads(DECLARATION.read_text(encoding="utf-8"))
        rows = raw.get("portable", {}).get("runtime_scoped_by_unicode_database", {}).get("rows")
        if not rows:
            rows = raw.get("runtime_scoped_by_unicode_database", {}).get("rows")
        found["unicode_rows"] = rows or {}
    except (OSError, ValueError, AttributeError):
        found["unicode_rows"] = {}
    return found


def frozen_generator_block(declaration: dict) -> dict:
    """The live freeze against the pack's declaration: the PORTABLE part is
    demanded, the runtime-bound digest is recorded.

    The declared literals are compared after a JSON round-trip on both sides,
    so a tuple in the live module and a list in the file are the same value,
    and every key is compared in both directions: a key the pack declares and
    the package lacks is as much a different generator as a moved value.
    Anything but equality there stops the run before minting. The
    whole-freeze digest also covers `runtime_freeze()` - the native runtime,
    the Unicode database, the compiled catalogue - so equality with the
    reference is reported and recorded, never required: it says whether this
    run was taken on the reference runtime, not whether the generator is the
    frozen one.
    """
    live = CP.freeze_record()
    problems = list(CP.freeze_problems())
    if not live.get("declared_matches_live"):
        problems.append("the live freeze does not match the package's own declared literals")
    pack_declared = json.loads(_canonical(declaration["declared"]))
    live_declared = json.loads(_canonical(live["declared"]))
    for key in sorted(set(pack_declared) | set(live_declared)):
        if key not in live_declared:
            problems.append(f"{key} is declared in the pack at {pack_declared[key]!r} and the live freeze "
                            f"has no such key")
        elif key not in pack_declared:
            problems.append(f"{key} is live at {live_declared[key]!r} and the pack declares no such key")
        elif pack_declared[key] != live_declared[key]:
            problems.append(f"{key} is declared in the pack at {pack_declared[key]!r} and is live at "
                            f"{live_declared[key]!r}")
    check("portable freeze: the package's declared literals equal the pack's declaration",
          not problems, f"{len(pack_declared)} keys compared, declaration layout {declaration['layout']}"
          if not problems else "; ".join(problems))
    check("portable freeze: the package's own declaration matches its live modules",
          bool(live.get("declared_matches_live")))
    if problems:
        refuse("this is not the frozen generator: " + "; ".join(problems), code=3)

    reference = declaration["reference_freeze_digest"]
    equal = live["digest"] == reference
    scope = live["runtime_scoped"]["runtime_scope"]
    reference_runtime = declaration["reference_runtime"]
    print(f"NOTE  whole-freeze digest {live['digest']} {'equals' if equal else 'differs from'} the reference "
          f"runtime's {reference}; this runtime is {json.dumps(scope['native_runtime'])} under unicode "
          f"{scope['unicode_database']}"
          + (f", the reference is {json.dumps(reference_runtime)}" if reference_runtime else
             ", and the declaration does not name the reference runtime")
          + ("" if equal else "; a difference here is a runtime, not a generator, and is recorded, not failed"))
    # ON THE REFERENCE RUNTIME ITSELF the whole-freeze digest must reproduce:
    # nothing runtime-bound differs there, so a difference is a different
    # package (a recompiled catalogue, a moved parser), and the run stops.
    on_reference = bool(reference_runtime) and all(
        scope["native_runtime"].get(k) == reference_runtime.get(k)
        for k in ("implementation", "version", "system", "machine")
    ) and scope["unicode_database"] == reference_runtime.get("unicode_database")
    if on_reference and not equal:
        refuse(f"this runtime IS the reference runtime {json.dumps(reference_runtime)}, and the whole-freeze "
               f"digest {live['digest']} differs from the reference {reference}: on the reference runtime a "
               f"difference is a different package, not a runtime", code=3)
    check("whole-freeze digest: reproduces on the reference runtime, or this is another runtime and it is recorded",
          True, "equal on the reference runtime" if on_reference else
          ("equal" if equal else "different; another runtime"))
    # A Unicode database the pack does not pin is an UNVERIFIED runtime for
    # the pack, not a passing one - the same refusal check_pack.py makes.
    pinned = declaration.get("unicode_rows") or {}
    if pinned and scope["unicode_database"] not in pinned:
        refuse(f"unicode {scope['unicode_database']} is NOT pinned by this pack (pinned: {sorted(pinned)}); "
               f"this interpreter's Unicode database has not been reviewed against the pack, so a run here "
               f"would be an unverified runtime rather than a measurement", code=3)
    return {
        "portable": {
            "declared_literals_match_pack": True,
            "keys_compared": len(pack_declared),
            "declared": live_declared,
            "declaration": {"file": declaration["file"], "schema": declaration["schema"],
                            "layout": declaration["layout"], "declared_at": declaration["declared_path"]},
        },
        "reference_runtime_attestation": {
            "freeze_digest": reference,
            "recorded_at": declaration["reference_digest_path"],
            "runtime": reference_runtime,
            "runtime_recorded_at": declaration["reference_runtime_path"],
        },
        "this_runtime": {
            "freeze_digest": live["digest"],
            "equals_reference_freeze_digest": equal,
            "runtime_scope": scope,
            "runtime_scoped": live["runtime_scoped"],
        },
        "note": ("the whole-freeze digest covers the native runtime (interpreter, operating system, machine, "
                 "Unicode database) and the compiled catalogue as well as the declared literals; equality "
                 "with the reference means this run was taken on the reference runtime and a difference "
                 "means another runtime - neither is a generator verdict. The generator verdict is the "
                 "portable check above; the manifest's own runtime checks apply at the serving door"),
    }


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


def append_jsonl(path: Path, row: dict) -> None:
    """One line, flushed and fsynced before returning, so the line is on disk
    before the next episode starts and a crash cannot take it."""
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Every field the pack promises the census carries; the dataclasses may carry
# more, and `dataclasses.asdict` takes whatever they carry.
CENSUS_FIELDS = ("group", "identity_digest", "family", "mechanism", "split", "profile", "population",
                 "outcome", "accepted_attempt", "attempts")
ATTEMPT_FIELDS = ("ordinal", "stage", "outcome", "codes", "witness", "components")


def census_view(census) -> dict:
    """Every field of a GroupCensus and of each of its Attempts, by the
    dataclass's own field list, so a field added to the census later shows
    up here without this script being told; plus the rejection distribution
    the module derives from the attempts."""
    body = dataclasses.asdict(census)
    body["rejection_distribution"] = census.distribution()
    return body


def census_fields_complete() -> list:
    """The fields the pack promises, against the installed dataclasses."""
    have_group = {f.name for f in dataclasses.fields(G.GroupCensus)}
    have_attempt = {f.name for f in dataclasses.fields(G.Attempt)}
    return ([f"GroupCensus lacks {name}" for name in CENSUS_FIELDS if name not in have_group]
            + [f"Attempt lacks {name}" for name in ATTEMPT_FIELDS if name not in have_attempt])


def serve_one(ordinal: int, m, variant: str, expected_contract: str) -> dict:
    """One variant through the real door, as one row. An exception anywhere
    in the episode - admission, evaluation, reading the publication - is
    caught HERE, named in the row and counted as not served; it is never
    allowed to end the run with the earlier rows unrecorded."""
    member = m.pair.variant(variant)
    selector = CP.selector_of(m.pair.identity, variant)
    row = {
        "ordinal": ordinal,
        "selector": selector,
        "group": m.pair.identity.label(),
        "variant": variant,
        "served": False,
        "exception": None,
        "expected_public_id": member.task.id,
        "served_public_id": None,
        "profile": None,
        "reward": None,
        "error": None,
        "completion": None,
        "ledger_score": None,
        "application_status": None,
        "application_score": None,
        "composite": None,
        "episode_contract_digest": None,
        "authored_reference_contract": expected_contract,
        "logged_at": None,
    }
    try:
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
        row.update({
            "served": bool(ok),
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
        })
    except Exception as exc:  # noqa: BLE001 - recorded in the row, never swallowed: served stays False
        row["exception"] = {"type": type(exc).__name__, "message": str(exc)}
    row["logged_at"] = now()
    return row


def run(per_stratum: int, paths: dict, manifest_path: Path, start: dict) -> int:
    generator = frozen_generator_block(load_declaration())

    secret = evaluator_secret()
    identities = stratified_prefix(CP.identities_of(CP.DEVELOPMENT_POPULATION), per_stratum)
    print(f"minting {len(identities)} declared group(s) of {CP.DEVELOPMENT_POPULATION} ...")

    ledger = G.PopulationLedger()
    minted, censuses = G.mint_population(identities, secret=secret, ledger=ledger)
    aggregate = G.aggregate(censuses)
    # A GroupCensus's `outcome` is "admitted" or "exhausted"; an exhausted
    # group is a named failure with its whole attempt history, never replaced.
    exhausted = [{"group": c.group, "mechanism": c.mechanism, "outcome": c.outcome, "attempts": len(c.attempts)}
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

    # The complete census goes to disk BEFORE the manifest is signed and
    # before any serving: whatever happens next, what was minted is recorded.
    missing = census_fields_complete()
    if missing:
        refuse("the installed census dataclasses lack fields the pack promises: " + "; ".join(missing), code=3)
    attempts = sum(len(c.attempts) for c in censuses)
    census_digest = write_json(paths["census.json"], {
        "schema": "piv.evaluation-pack.census/2",
        "evaluator_side": "keep beside the manifest; never inside an agent workspace, prompt or dataset",
        "population": CP.DEVELOPMENT_POPULATION,
        "declared_order": "roster prefix per mechanism stratum, never a sample",
        "per_stratum": per_stratum,
        "declared_groups_minted": len(identities),
        "admitted_groups": len(groups),
        "exhausted_groups": len(exhausted),
        "exhausted": exhausted,
        "aggregate": aggregate,
        "attempts": attempts,
        "census_fields": [f.name for f in dataclasses.fields(G.GroupCensus)],
        "attempt_fields": [f.name for f in dataclasses.fields(G.Attempt)],
        "censuses": [census_view(c) for c in censuses],
        "groups": groups,
        "written_before": ["manifest signing", "serving"],
    })
    check("census on disk before signing and serving", True,
          f"{len(censuses)} group census(es), {attempts} attempt(s), sha256 {census_digest[:16]}...")

    records = [rec for m in minted for rec in CP.records_for(m)]
    FM.write(records, secret, manifest_path)
    print(f"signed {len(records)} record(s) into {manifest_path}")
    manifest = {"path": str(manifest_path), "records_signed": len(records), "sha256": sha256_file(manifest_path)}

    reference = env_mod.load_environment("cash_application_001")
    expected_contract = reference.episode_contract_digest()

    # A fresh log for this run; each row lands on disk the moment its
    # episode ends, whatever the episode did.
    paths["serving.jsonl"].write_text("", encoding="utf-8", newline="\n")
    rows, failures, exceptions = [], [], []
    ordinal = 0
    for m in minted:
        for variant in sorted(m.pair.variants):
            ordinal += 1
            row = serve_one(ordinal, m, variant, expected_contract)
            append_jsonl(paths["serving.jsonl"], row)
            rows.append(row)
            if not row["served"]:
                failures.append(row["selector"])
            if row["exception"] is not None:
                exceptions.append(row["selector"])
            print({k: row[k] for k in ("selector", "reward", "completion", "application_status", "composite",
                                       "served", "exception")})

    serving_digest = write_json(paths["serving.json"], {
        "schema": "piv.evaluation-pack.serving/2",
        "authored_reference": {"task_id": "cash_application_001", "episode_contract_digest": expected_contract},
        "manifest": manifest,
        "serving_log": {"path": str(paths["serving.jsonl"]), "sha256": sha256_file(paths["serving.jsonl"]),
                        "lines": len(rows),
                        "note": "one line per variant, appended and fsynced as each episode ended"},
        "planned": len(rows),
        "served": len(rows) - len(failures),
        "failed": failures,
        "exceptions": exceptions,
        "rows": rows,
    })
    check("every signed variant served", not failures,
          f"{len(rows) - len(failures)} of {len(rows)}" + (f"; not served: {failures}" if failures else ""))
    check("no declared group exhausted", not exhausted,
          "" if not exhausted else f"{len(exhausted)} exhausted under this key, named in census.json")
    result = "PASS" if not failures and not exhausted else "FAIL"
    write_json(paths["run.json"], dict(
        start,
        status="finished",
        finished_at=now(),
        frozen_generator=generator,
        manifest=manifest,
        outputs={"census.json": census_digest, "serving.jsonl": sha256_file(paths["serving.jsonl"]),
                 "serving.json": serving_digest},
        result=result,
        what_a_pass_means=("your installation mints admissible fresh instances of the declared population "
                           "under your key and serves them under the authored episode contract; nothing "
                           "about difficulty, any model, or training benefit"),
    ))
    print(f"\ncensus: {paths['census.json']}\nserving log: {paths['serving.jsonl']}\n"
          f"serving: {paths['serving.json']}\nrun: {paths['run.json']}")
    if exhausted:
        print(f"FAIL: {len(exhausted)} declared group(s) exhausted under this key: named in census.json")
    if failures:
        print(f"FAIL: {len(failures)} variant(s) did not serve: {failures}")
    print(result)
    return 0 if result == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--per-stratum", type=int, default=1,
                       help="declared groups per mechanism stratum, as a roster prefix (default 1)")
    group.add_argument("--all", action="store_true", help="every declared group (96)")
    parser.add_argument("--out", default="evaluation_pack_run",
                        help="directory for run.json, census.json, serving.jsonl and serving.json "
                             "(default ./evaluation_pack_run)")
    args = parser.parse_args()
    per_stratum = 32 if args.all else args.per_stratum
    if per_stratum < 1 or per_stratum > 32:
        refuse("--per-stratum must be between 1 and 32")

    # Every write target is placed, and refused if inside ~/.piv, before a
    # directory is created or a byte is written.
    out = outside_piv("--out", args.out)
    paths = {name: outside_piv(name, out / name) for name in OUTPUT_FILES}
    manifest_path = outside_piv("PIV_CASH_APPLICATION_MANIFEST", os.environ["PIV_CASH_APPLICATION_MANIFEST"])
    if out.exists() and any(out.iterdir()):
        refuse(f"--out {out} is not empty; a run writes only into a fresh directory, so an aborted run can "
               f"never be mistaken for a complete one by a directory listing")
    out.mkdir(parents=True, exist_ok=True)

    package = package_block()
    print("package:", package["import_path"])
    print("runtime:", json.dumps(package["runtime"]))
    start = {
        "schema": "piv.evaluation-pack.run/2",
        "status": "started",
        "started_at": now(),
        "finished_at": None,
        "package": package,
        "population": CP.DEVELOPMENT_POPULATION,
        "groups_requested_per_stratum": per_stratum,
        "manifest_path": str(manifest_path),
        "outputs_planned": {name: str(path) for name, path in paths.items()},
        "result": None,
    }
    write_json(paths["run.json"], start)
    print(f"run.json start record written: {paths['run.json']}")
    try:
        return run(per_stratum, paths, manifest_path, start)
    except BaseException as exc:  # noqa: BLE001 - the start record says how the run ended, then the exit stands
        ended = dict(start, status="aborted", aborted_at=now(),
                     abort={"type": type(exc).__name__, "message": str(exc),
                            "exit_code": exc.code if isinstance(exc, SystemExit) else None})
        try:
            write_json(paths["run.json"], ended)
        except OSError as write_exc:
            print(f"run.json could not record the abort ({write_exc}); the start record stands", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
