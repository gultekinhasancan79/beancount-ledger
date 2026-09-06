"""The release manifest: which generated tasks may be served, proven under the
evaluator's OWN secret.

HMAC-keyed seeds make `(secret, profile, selector)` determine the world, so
every sweep, differential and exploit run performed under the test-suite
secret validates a DIFFERENT population from the one the evaluator mints in
production. The release population must therefore be minted and gated under
the production secret, in the evaluator process, and task serving must
refuse anything that is not in the resulting pass record:

    preflight   `tests/preflight_manifest.py` mints a finite manifest of
                (namespace, index, profile) under the active secret and runs
                the gates on those exact worlds — generation validity,
                public-only identifiability with no prior, repair-key
                equality, canonical golden score, id collisions;
    record      one signed record per selector: namespace, index, profile,
                attempt, the public content id, every component version and
                each gate's result. NEVER the seed, the secret or any private
                truth. The signature is an HMAC under a key derived from the
                evaluator secret, so a record cannot be pasted from another
                evaluator, another key version or another component version;
    serving     `load_environment` admits a generated selector only when the
                active manifest — the one whose key id matches the active
                secret — holds a passed, correctly signed record whose public
                id equals the freshly minted world's and whose versions equal
                the running code's. Development runs under a test secret set
                PIV_DEV_UNMANIFESTED=1 explicitly; production never does.

The manifest lives outside the repo (PIV_MANIFEST or ~/.piv/manifest.json),
beside the secret it belongs to.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

from ..candidate.canonical import (
    RENDERER_VERSION,
    SCORER_CONTRACT_VERSION,
    TASK_CONTRACT_VERSION,
    canonical_bytes,
)
from .identify import IDENTIFY_VERSION
from .mint import GENERATOR_VERSION

MANIFEST_ENV = "PIV_MANIFEST"
DEV_ENV = "PIV_DEV_UNMANIFESTED"
ROTATION_ENV = "PIV_KEY_ID"
MANIFEST_SCHEMA = 2
_SIGNING_DOMAIN = b"piv:manifest-signing-key:v1\0"
ROTATION_ID_BYTES = 16
# The gates a preflighted selector must pass, and a serving contract rather
# than preflight metadata.
#
# It used to be the other way round: `admit` read a record's own `passed` flag
# and `versions()`, neither of which mentioned the gate list, so a record
# signed before a gate was ADDED kept admitting — the manifest asserting a
# gate the record had never been tested against. That was safe for
# `ledger_within_envelope` only because the same property is re-checked
# unconditionally in `load_environment` and `_verify_public_world`; the next
# gate added may have no such duplicate, and "the manifest attests the current
# release gates" was simply false meanwhile.
#
# Two independent closures now, both required. `admit` demands
# `set(rec["gates"]) == set(GATES)` and every one of them True — the historical
# aggregate is never trusted on its own — and `versions()` carries
# PREFLIGHT_CONTRACT_VERSION and a canonical digest of this tuple, so changing
# the gate set (or its meaning) invalidates every existing record through the
# versions path as well. Changing GATES therefore REQUIRES a re-preflight.
GATES = ("minted", "identifiable", "repair_key_equal", "golden_scores_one", "id_unique",
         "ledger_within_envelope")
#: Bumped when a gate's SEMANTICS change without its name changing — the digest
#: below cannot see that, and an unchanged name must not keep admitting records
#: proved against the old meaning.
PREFLIGHT_CONTRACT_VERSION = 1


def gate_set_digest() -> str:
    """A canonical 16-hex digest of the gate NAMES, order-independent."""
    payload = canonical_bytes({"gates": sorted(GATES)})
    return hashlib.sha256(b"piv:preflight-gates:v1\0" + payload).hexdigest()[:16]


def versions() -> dict:
    """Every semantic component a record is bound to. A bump in any of them
    invalidates the manifest, which is the point.

    WHAT IS HERE: the world's semantics and the release gates. The generator
    that built the world, the public-only checker the gates ran, the scorer
    contract, the renderer, the task contract, the manifest schema, the
    preflight contract version and a digest of the gate set. Every one of them
    can change whether the golden bookkeeping answer is still the golden
    bookkeeping answer, or whether the record's gates still mean what they
    meant when they passed.

    WHAT IS DELIBERATELY NOT HERE: the EPISODE contract — the system prompt,
    the tool schemas, the observation modes, the stop conditions and above all
    the per-episode output ceiling. Those were bound here
    once, and the binding was not sound: `load_environment` calls `admit()`
    BEFORE constructing the environment, and then accepts
    `max_episode_output_tokens` and `set_max_total_completion_tokens`, so a
    world admitted under the default 40,000-token digest could be served under
    an 8,000-token one with no second check. The manifest was asserting a
    contract it had not preflighted.

    Of the two repairs the reviewer offered — bind the ceiling strictly, or
    separate the two identities — the reviewer preferred separation, and so
    do we: golden
    bookkeeping validity does not depend on whether the model was given 8K or
    40K completion tokens. EXPERIMENT COMPARABILITY does, and that is where
    the episode contract is bound instead, on every rollout and every row:

        state["piv_episode_contract_digest"]   the ceiling THAT rollout ran
                                               under, stamped in `setup_state`
        results["metadata"]["piv_episode_contract"]
                                               version, digest and ceiling for
                                               the batch
        the measurement's archived rows        the same digest per row, so two
                                               conditions can never be pooled

    A release therefore admits a WORLD; a measurement identifies an EPISODE.
    Changing the prompt or the ceiling no longer invalidates a manifest, and a
    manifest can no longer be read as evidence about a ceiling nobody
    preflighted."""
    return {"generator": GENERATOR_VERSION, "identify": IDENTIFY_VERSION,
            "scorer_contract": SCORER_CONTRACT_VERSION, "renderer": RENDERER_VERSION,
            "task_contract": TASK_CONTRACT_VERSION, "manifest_schema": MANIFEST_SCHEMA,
            "preflight_contract": PREFLIGHT_CONTRACT_VERSION, "gate_set": gate_set_digest()}


def rotation_id() -> str | None:
    """The opaque rotation label provisioned BESIDE the secret:
    PIV_KEY_ID, or ~/.piv/key_id — never derived from the secret,
    so it is not a verification token for guesses at the key. A manifest
    names the rotation it was preflighted under; the HMAC signature under
    the secret is the real binding. None when nothing is provisioned."""
    # The rotation id travels WITH the secret's source. A secret handed in
    # through the environment (a test suite, a CI job) pairs only with a
    # rotation handed in the same way; the provisioned files pair with each
    # other. Otherwise a process minting under a test secret would find the
    # evaluator's production manifest "active" through ~/.piv/key_id and
    # refuse every record on signature (that is what happened the first time
    # the preflight provisioned a rotation id).
    raw = os.environ.get(ROTATION_ENV)
    if raw and raw.strip():
        return raw.strip()
    if os.environ.get("PIV_EVAL_SECRET"):
        return None
    path = Path(os.path.expanduser("~")) / ".piv" / "key_id"
    if path.is_file():
        value = path.read_text(encoding="ascii", errors="ignore").strip()
        return value or None
    return None


def provision_rotation_id() -> str:
    """Create ~/.piv/key_id if the evaluator has none: random, opaque. Used
    by the preflight, which is the provisioning step."""
    current = rotation_id()
    if current:
        return current
    path = Path(os.path.expanduser("~")) / ".piv" / "key_id"
    path.parent.mkdir(parents=True, exist_ok=True)
    value = os.urandom(ROTATION_ID_BYTES).hex()
    path.write_text(value + "\n", encoding="ascii")
    return value


_DEVELOPMENT_CAPABILITY: str | None = None


def enable_development(reason: str) -> None:
    """Grant this process the development capability EXPLICITLY: an
    interactive probe or an embedding without a main file must
    say so in code, in the process, with a reason; an environment variable
    alone never does, and neither does the absence of `__main__.__file__`
    — a production service launched through `python -c`, stdin or an
    embedding has no main file either, and must not inherit an override
    from an operator's shell."""
    global _DEVELOPMENT_CAPABILITY
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("enable_development needs a reason")
    _DEVELOPMENT_CAPABILITY = reason.strip()


def development_entrypoint() -> bool:
    """Is this process a DEVELOPMENT entrypoint? True only when the running
    program is one of this package's own test/tool scripts (a file under
    the repository's tests/ directory), or when the process called
    `enable_development(reason)` itself. A serving process — the verifiers
    CLI, a trainer, a server importing `load_environment`, a `python -c`
    launcher — is never one, whatever its environment says (the override is
    structural or explicit, never inferred)."""
    import sys
    if _DEVELOPMENT_CAPABILITY:
        return True
    main = sys.modules.get("__main__")
    file = getattr(main, "__file__", None)
    if not file:
        return False                      # no main file: could be a launcher; nothing is inferred from that
    try:
        here = Path(file).resolve()
    except OSError:
        return False
    tests_dir = Path(__file__).resolve().parents[2] / "tests"
    return tests_dir in here.parents


def _signing_key(secret: bytes) -> bytes:
    return hmac.new(bytes(secret), _SIGNING_DOMAIN, hashlib.sha256).digest()


def record(namespace: str, index: int, profile_name: str, public_id: str, attempt: int, gates: dict) -> dict:
    """An unsigned record. `gates` maps every name in GATES to a real bool.

    `is True` / `is False`, not truthiness: a gate whose result is `1`, `"ok"`
    or a non-empty diagnostics object is a preflight that did not answer the
    question asked, and coercing it here would sign the coercion. `admit`
    compares the same way.
    """
    if set(gates) != set(GATES):
        raise ValueError(f"gates must be exactly {GATES}")
    wrong = {g: gates[g] for g in GATES if gates[g] is not True and gates[g] is not False}
    if wrong:
        raise ValueError(f"gate results must be True or False, not {wrong}")
    return {"namespace": namespace, "index": int(index), "profile": profile_name, "public_id": public_id,
            "attempt": int(attempt), "versions": versions(), "gates": {g: gates[g] for g in GATES},
            "passed": all(gates[g] is True for g in GATES)}


def _material(rec: dict) -> bytes:
    return canonical_bytes({k: v for k, v in rec.items() if k != "signature"})


def sign(rec: dict, secret: bytes) -> dict:
    signed = dict(rec)
    signed["signature"] = hmac.new(_signing_key(secret), _material(rec), hashlib.sha256).hexdigest()
    return signed


def verify(rec: dict, secret: bytes) -> bool:
    signature = rec.get("signature")
    if not isinstance(signature, str):
        return False
    expected = hmac.new(_signing_key(secret), _material(rec), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def selector_key(namespace: str, index: int, profile_name: str) -> str:
    return f"{namespace}:{int(index)}:{profile_name}"


def manifest_path() -> Path:
    raw = os.environ.get(MANIFEST_ENV)
    if raw:
        return Path(raw)
    return Path(os.path.expanduser("~")) / ".piv" / "manifest.json"


def write(records: list, secret: bytes, path: Path | None = None, *, rotation: str | None = None) -> Path:
    """Write a manifest for this rotation: schema, rotation id, versions,
    signed records. `rotation` defaults to the provisioned rotation id."""
    rotation = rotation or rotation_id()
    if not rotation:
        raise ValueError(f"no rotation id provisioned: set {ROTATION_ENV} or ~/.piv/key_id (the preflight provisions one)")
    path = path or manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema": MANIFEST_SCHEMA, "rotation_id": rotation, "versions": versions(),
            "records": [sign(r, secret) for r in records]}
    path.write_text(json.dumps(body, indent=1, sort_keys=True), encoding="utf-8")
    return path


def load_active(secret: bytes, path: Path | None = None) -> dict | None:
    """The manifest for THIS rotation, or None when there is none. A manifest
    for another rotation (or another schema) is not an error; it is simply
    not the active one — a stale file must never admit anything. The
    rotation id only SELECTS the file; every record is then verified under
    the secret, which is the binding that matters."""
    path = path or manifest_path()
    if not path.is_file():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    current = rotation_id()
    if (not isinstance(body, dict) or body.get("schema") != MANIFEST_SCHEMA or not current
            or body.get("rotation_id") != current):
        return None
    records, duplicates = {}, []
    for rec in body.get("records", []):
        if isinstance(rec, dict) and {"namespace", "index", "profile"} <= set(rec):
            key = selector_key(rec["namespace"], rec["index"], rec["profile"])
            if key in records:
                # Two records for one selector: the file decides which one
                # serves, by position. A manifest that says both "passed" and
                # "failed" about the same world attests nothing about it, and
                # last-write-wins would hide the disagreement — so the whole
                # manifest is refused rather than half-believed.
                duplicates.append(key)
            records[key] = rec
    if duplicates:
        return {"path": path, "records": {}, "duplicates": sorted(set(duplicates))}
    return {"path": path, "records": records, "duplicates": []}


def admit(secret: bytes, namespace: str, index: int, profile_name: str, public_id: str) -> tuple[bool, str]:
    """May this freshly minted world be served? Every refusal names its reason;
    none of them reveals anything about the world."""
    active = load_active(secret)
    if active is None:
        if os.environ.get(DEV_ENV) == "1" and development_entrypoint():
            return True, "development: serving without a release manifest (development entrypoint + PIV_DEV_UNMANIFESTED=1)"
        if os.environ.get(DEV_ENV) == "1":
            return (False, "no release manifest for this evaluator key, and this is not a development entrypoint: "
                           f"{DEV_ENV}=1 is ignored outside the package's own tests/ scripts unless the process "
                           "called enable_development(reason)")
        return (False, f"no release manifest for this evaluator key: preflight one ({MANIFEST_ENV} or ~/.piv/manifest.json) "
                       f"or, in a development entrypoint, set {DEV_ENV}=1")
    if active.get("duplicates"):
        return (False, f"release manifest holds duplicate records for {active['duplicates']}: "
                       "it attests nothing about any selector until it is re-preflighted")
    rec = active["records"].get(selector_key(namespace, index, profile_name))
    if rec is None:
        return False, "selector absent from the release manifest"
    if not verify(rec, secret):
        return False, "manifest record signature does not verify under this key"
    current = versions()
    if rec.get("versions") != current:
        # Name WHICH components differ, so an operator can read the reason and
        # know whether to re-preflight or to pin something. Since the episode
        # contract left this dict, every key here is a world-semantics or
        # gate-set version that WE own: a `verifiers`/`pydantic` bump no longer
        # refuses a manifest (it moves the episode digest, which rides the
        # rollout rows instead), and a difference here really does mean the
        # released world's meaning changed.
        was = rec.get("versions") if isinstance(rec.get("versions"), dict) else {}
        drifted = sorted(set(was) ^ set(current) | {k for k in current if k in was and was[k] != current[k]})
        return False, f"manifest record was minted under other component versions: {drifted}"
    # The gate set, checked against the CURRENT one rather than against the
    # record's own summary. `passed` is the preflight's historical aggregate:
    # true of the gates that existed when it was signed, and silent about the
    # ones added since. A record must carry exactly today's gate names, each
    # one True, or it does not attest today's release contract.
    gates = rec.get("gates")
    if not isinstance(gates, dict) or set(gates) != set(GATES):
        return (False, f"manifest record was preflighted against another gate set "
                       f"{sorted(gates) if isinstance(gates, dict) else gates!r}, not {sorted(GATES)}")
    # `is not True`, not falsiness: a gate recorded as 1, "ok" or a
    # diagnostics object did not answer the question, and admitting on its
    # truthiness would serve a world on a value nobody meant as a pass.
    failed = [g for g in GATES if gates.get(g) is not True]
    if failed:
        return False, f"selector failed preflight gates {failed}"
    if not rec.get("passed"):
        # Every current gate reads True and the aggregate still says no: the
        # record disagrees with itself, so neither half is evidence.
        return False, "selector failed preflight gates: the record's gates and its passed flag disagree"
    if rec.get("public_id") != public_id:
        return False, "manifest public id differs from the minted world"
    return True, "release manifest"
