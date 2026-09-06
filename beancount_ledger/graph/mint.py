"""Minting generated tasks: private seeds, domain-separated substreams,
public ids from public bytes, disjoint namespaces.

A public or reversible generation seed is refused: in a white-box
environment an agent that sees `gen-<seed>` regenerates the clean graph
and the golden answer without reconciling anything. So:

    private seed   128 bits, SHA-256 over (generator version, namespace,
                   index[, evaluator secret]); evaluator-private provenance,
                   never in a public file, a prompt, a tool reply or state
    substreams     SHA-256 over (generator version, private seed, purpose)
                   -> an integer that seeds `random.Random`; adding a
                   purpose never reshuffles another
    public id      "task-" + digest of the PUBLIC bundle bytes: what the
                   model sees; two seeds with one public world share it,
                   which is the point (occurrence provenance is not identity)
    namespaces     "train" and "eval" derive from different domains, so the
                   seed sets are disjoint by construction; evaluation seeds
                   are never listed in a training corpus
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, replace

from ..candidate.canonical import canonical_bytes, domain_digest
from .derive import ContractInputs, TaskSpec, derive_contract
from .project import Bundle
from .schema import World

GENERATOR_VERSION = 9          # 9: dense plans — 5–6 (standard) / 6–8 (hard) items spanning at least three rules, 3–4 customers and 2–3 inventory vendors so every rule keeps candidates, wrong figures pairwise distinct, residual cancellation refused at the generator; 8: `## Payments to suppliers` — the policy says where money moving to a vendor is posted, and default_account is not it; 7: the bank date is the repair date for an omitted item, and the policy says so; 6: public-uniqueness gate at mint; 5: profile in the substream; 4: fee wording; 3: keyed seeds; 2: "Dates"
NAMESPACES = ("train", "eval")
PUBLIC_ID_DOMAIN = b"piv:public-task-id:v1\0"
_SEED_DOMAIN = b"piv:private-seed:v2\0"
_SUBSTREAM_DOMAIN = b"piv:substream:v1\0"
MIN_SECRET_BYTES = 16
MAX_LAYOUT_ATTEMPTS = 64
SECRET_ENV = "PIV_EVAL_SECRET"


def evaluator_secret() -> bytes | None:
    """The evaluator's secret, from the environment (hex or raw) or from
    `~/.piv/eval_secret` — never from the package, a public file, a tool
    reply or state. None when neither is set."""
    raw = os.environ.get(SECRET_ENV)
    if raw:
        try:
            return bytes.fromhex(raw)
        except ValueError:
            return raw.encode("utf-8")
    path = os.path.join(os.path.expanduser("~"), ".piv", "eval_secret")
    if os.path.isfile(path):
        with open(path, "rb") as handle:
            data = handle.read().strip()
        try:
            return bytes.fromhex(data.decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            return data
    return None


def private_seed(namespace: str, index: int, secret: bytes) -> int:
    """A 128-bit private seed: HMAC-SHA-256 under the evaluator's secret
    over the canonically framed (version, namespace, index). A SHA-256 of
    (version, namespace, index) alone has the entropy of the selector, not
    of its width: with the generator code and the public id as an equality
    oracle, an agent enumerates the index range and regenerates the answer.
    The secret is MANDATORY here; the unkeyed derivation lives
    in `unkeyed_seed`, test-only."""
    if namespace not in NAMESPACES:
        raise ValueError(f"unknown namespace {namespace!r}")
    if type(index) is not int or index < 0:
        raise ValueError("index is a non-negative integer")
    if not isinstance(secret, (bytes, bytearray)) or len(secret) < MIN_SECRET_BYTES:
        raise ValueError(f"an evaluator secret of at least {MIN_SECRET_BYTES} bytes is required")
    material = _SEED_DOMAIN + canonical_bytes({"generator_version": GENERATOR_VERSION,
                                               "namespace": namespace, "index": index})
    return int.from_bytes(hmac.new(bytes(secret), material, hashlib.sha256).digest()[:16], "big")


def unkeyed_seed(namespace: str, index: int) -> int:
    """TEST-ONLY. The enumerable derivation; exists so the seed-recovery
    witness can show the attack it prevents. `load_environment` never
    calls this."""
    if namespace not in NAMESPACES:
        raise ValueError(f"unknown namespace {namespace!r}")
    material = _SEED_DOMAIN + b"unkeyed\0" + canonical_bytes({"generator_version": GENERATOR_VERSION,
                                                              "namespace": namespace, "index": int(index)})
    return int.from_bytes(hashlib.sha256(material).digest()[:16], "big")


def sub_seed(seed: int, purpose: str) -> int:
    """The substream seed for one purpose: SHA-256, domain-separated, never
    Python's salted `hash()`. Stable across processes and PYTHONHASHSEED."""
    material = _SUBSTREAM_DOMAIN + canonical_bytes({"generator_version": GENERATOR_VERSION,
                                                    "seed": int(seed), "purpose": purpose})
    return int.from_bytes(hashlib.sha256(material).digest()[:16], "big")


def public_task_id(inputs: ContractInputs) -> str:
    """Derived from the public bytes only: never the seed, the graph digest
    or the environment digest (each of which a generator could be run
    against)."""
    files = {name: data.decode("utf-8") for name, data in inputs.public_files}
    # The prompt is a public surface too: the id binds
    # everything the model is shown, files and instruction alike.
    return "task-" + domain_digest(PUBLIC_ID_DOMAIN, canonical_bytes({"files": files, "prompt": inputs.prompt}))[:24]


@dataclass(frozen=True)
class Provenance:
    """Evaluator-private. Not part of any digest the model can reach."""

    namespace: str
    index: int
    private_seed: int
    generator_version: int
    profile: object
    attempt: int = 0               # which bounded layout attempt produced the world
    keyed: bool = True


@dataclass(frozen=True)
class Minted:
    world: World
    task: TaskSpec
    bundle: Bundle
    inputs: ContractInputs
    provenance: Provenance


def _mint_from_seed(namespace: str, index: int, seed: int, profile, keyed: bool) -> Minted:
    from .generate import DEFAULT_PROFILE, GenerationError, generate   # the generator is the only consumer of the seed

    profile = DEFAULT_PROFILE if profile is None else profile
    # Bounded deterministic layout attempts: a draw that cannot
    # carry the profile's minimum is retried under the next attempt
    # substream; the same selector always chooses the same attempt.
    # Exhaustion is a generator/profile defect and fails loudly.
    # The profile enters the substream too: train:35 and train:35:hard are
    # different worlds by construction, not by the luck of the draw (the v4
    # sweep found 3 of 300 indices where the two profiles drew one world).
    # A world whose PUBLIC evidence admits more than one cheapest reading is
    # refused here too — `_finish` runs the public-only
    # checker with no prior — and the next attempt is drawn instead. Unique
    # therefore means unique under public constraints for every minted
    # world, not "the most plausible hidden mutation".
    last = None
    for attempt in range(MAX_LAYOUT_ATTEMPTS):
        try:
            world, task = generate(sub_seed(seed, f"profile/{profile.name}/layout_attempt/{attempt}"), profile)
            return _finish(namespace, index, seed, profile, world, task, attempt, keyed)
        except GenerationError as exc:
            last = exc
    raise GenerationError(f"{namespace}:{index}: no valid layout in {MAX_LAYOUT_ATTEMPTS} attempts "
                          f"(profile {getattr(profile, 'name', '?')}); last: {last}")


def mint(namespace: str, index: int, profile=None, *, secret: bytes | None = None) -> Minted:
    """The production door. `secret` defaults to the evaluator's configured
    secret; with none configured this REFUSES — there is no unkeyed
    fallback on this path."""
    if secret is None:
        secret = evaluator_secret()
    if secret is None:
        raise ValueError(f"no evaluator secret: set {SECRET_ENV} (hex) or ~/.piv/eval_secret; generated tasks are keyed")
    return _mint_from_seed(namespace, index, private_seed(namespace, index, secret), profile, keyed=True)


def mint_unkeyed(namespace: str, index: int, profile=None) -> Minted:
    """TEST-ONLY: the enumerable construction, for the seed-recovery witness."""
    return _mint_from_seed(namespace, index, unkeyed_seed(namespace, index), profile, keyed=False)


def _finish(namespace, index, seed, profile, world, task, attempt, keyed) -> Minted:
    # The public id is a function of the public bytes; the task id inside the
    # contract must be that id, so derive once with a placeholder, compute
    # the id, and derive again with it (the id enters the contract view).
    _, first = derive_contract(world, replace(task, id="task-pending"))
    _require_public_uniqueness(namespace, index, attempt, world, task, first)
    task = replace(task, id=public_task_id(first))
    bundle, inputs = derive_contract(world, task)
    if inputs.task_id != public_task_id(inputs):
        raise RuntimeError("the public id is not a pure function of the public bytes")
    return Minted(world, task, bundle, inputs, Provenance(namespace, index, seed, GENERATOR_VERSION, profile, attempt, keyed))


def _require_public_uniqueness(namespace, index, attempt, world, task, inputs) -> None:
    """The public-only checker, with no prior, must find exactly one reading
    AND that reading must be the planted one under the shared repair key
    (checker side `identify.repair_key`, truth side `derive.planted_key`,
    two independent projections); otherwise this layout is refused and the
    caller draws the next attempt. A unique-but-wrong reading is exactly
    what shipped 32 of 150 worlds with a mis-attributed vendor payment
    before the key existed (the verifier's follow-up A): the gate now fails
    closed on it, so a checker or attribution defect costs refusals, never
    a world whose only public answer the scorer pays 0 for. The checker sees
    the same bytes the agent will be mounted and nothing else."""
    import csv
    import io
    from .derive import planted_key
    from .generate import GenerationError
    from .identify import CUSTOMERS_FILE, VENDORS_FILE, check_identifiable, repair_key
    public = {name: data.decode("utf-8") for name, data in inputs.public_files}
    verdict = check_identifiable(public, bank_account=world.bank_account,
                                 period_start=task.period.start, period_end=task.period.end)
    if not verdict.unique:
        raise GenerationError(f"{namespace}:{index} attempt {attempt}: the public evidence admits "
                              f"{verdict.readings} readings — {verdict.reason[:160]}")
    names = set()
    for file_name, column in ((CUSTOMERS_FILE, "customer"), (VENDORS_FILE, "vendor")):
        for record in csv.DictReader(io.StringIO(public.get(file_name, ""))):
            if (record.get(column) or "").strip():
                names.add(record[column].strip())
    want = sorted(planted_key(p, frozenset(names), bank_account=world.bank_account) for p in inputs.planted)
    got = sorted(repair_key(r) for r in verdict.repairs)
    if want != got:
        raise GenerationError(f"{namespace}:{index} attempt {attempt}: the unique public reading is not the planted "
                              f"one — planted {want} vs read {got}"[:400])


def literal_provenance_leaks(minted: Minted) -> list[str]:
    """LITERAL leakage only: every public surface checked for the seed, the
    index and the graph and environment identities as text. It cannot see
    an enumeration attack — that is what the keyed seed is for, and what
    the seed-recovery witness in `test_generator` exercises."""
    needles = [str(minted.provenance.private_seed), f"{minted.provenance.private_seed:x}",
               minted.bundle.graph_digest, minted.bundle.mutation_plan_digest,
               f"{minted.provenance.namespace}:{minted.provenance.index}", f"gen-{minted.provenance.index}"]
    problems = []
    surfaces = {name: data.decode("utf-8") for name, data in minted.inputs.public_files}
    surfaces["prompt"] = minted.inputs.prompt
    surfaces["task_id"] = minted.inputs.task_id
    for name, text in surfaces.items():
        for needle in needles:
            if needle and needle in text:
                problems.append(f"{name} carries private provenance {needle[:12]}…")
    return problems
