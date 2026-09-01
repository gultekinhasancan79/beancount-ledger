"""One rollout with a real model, through the real environment.

Everything else in this suite proves the machinery with a scripted client.
This is the one thing that machinery cannot prove: that an actual language
model, given the tools and the world, can do the task. M0's fifth step was
"run one rollout" and until this ran, it had only ever run with a fake model.

    python tests/run_live_rollout.py --model nvidia/nemotron-3-ultra-550b-a55b

Probed 2026-08-29 on integrate.api.nvidia.com: tool calls work on the
nemotron-3 family, gpt-oss-20b/120b, minimax-m3 and kimi-k3; kimi-k3's
per-minute quota is too small for a tool loop, deepseek-v4 timed out at 90s.

The API key is read from the user's registry environment (HKCU\\Environment,
NVIDIA_API_KEY) and placed in this process's environment for the framework's
client to pick up by name. It is never printed.

What is reported:
  - reward, and the scorer's full breakdown (which planted items resolved,
    which penalties fired);
  - the number of turns and which tools were called;
  - whether the rollout was scored, protocol-rejected, or quarantined;
  - the lines the model added to the ledger, so a human can read what it did.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
KEY_VAR = "NVIDIA_API_KEY"


def load_key_from_registry() -> None:
    """Populate the env var from HKCU without printing it."""
    if os.environ.get(KEY_VAR):
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
        value, _ = winreg.QueryValueEx(handle, KEY_VAR)
    os.environ[KEY_VAR] = value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--retries", type=int, default=3,
                        help="framework-level retries of a rollout aborted by a provider error (429 etc.)")
    parser.add_argument("--min-interval", type=float, default=6.0,
                        help="seconds between requests; NVIDIA's per-model limits are tight")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_key_from_registry()

    import time

    import openai
    from verifiers.legacy.clients.openai_chat_completions_client import OpenAIChatCompletionsClient
    from verifiers.legacy.types import ClientConfig

    from beancount_ledger import beancount_ledger as env_mod
    from beancount_ledger.beancount_ledger import LEDGER, WORLD_DIR, digests_of, load_environment, logical_text

    class PacedClient(OpenAIChatCompletionsClient):
        """The framework client, with a minimum interval between requests
        and a long back-off on 429.

        The SDK's own retry (10 attempts, back-off capped at 8s) was not
        enough: NVIDIA's preview models throttle per minute, and a tool loop
        fires a request per turn. Two live attempts died at 51s and 64s with
        `RateLimitError` — quarantined, batch INVALID, exactly as designed,
        but a witness of the quarantine is not the rollout we came for.
        """
        _last = 0.0
        _gate = None

        async def get_native_response(self, *a, **k):
            if PacedClient._gate is None:
                PacedClient._gate = asyncio.Lock()
            for attempt in range(6):
                async with PacedClient._gate:
                    wait = PacedClient._last + args.min_interval - time.monotonic()
                    if wait > 0:
                        await asyncio.sleep(wait)
                    PacedClient._last = time.monotonic()
                try:
                    return await super().get_native_response(*a, **k)
                except openai.RateLimitError:
                    pause = 20.0 * (attempt + 1)
                    print(f"  429 from the provider; pausing {pause:.0f}s (attempt {attempt + 1}/6)", flush=True)
                    await asyncio.sleep(pause)
            return await super().get_native_response(*a, **k)

    env = load_environment()
    config = ClientConfig(
        client_type="openai_chat_completions",
        api_key_var=KEY_VAR,
        api_base_url=NVIDIA_BASE_URL,
        timeout=args.timeout,
        connect_timeout=15.0,
    )
    client = PacedClient(config)
    print(f"model   : {args.model}")
    print(f"endpoint: {NVIDIA_BASE_URL}")
    print("running one rollout...\n", flush=True)

    # Workspaces are mkdtemp'd and never deleted; the one this rollout mints
    # is whichever appears that was not there before.
    temp_root = Path(tempfile.gettempdir())
    before = set(temp_root.glob("beancount_env_*"))

    try:
        results = asyncio.run(env.evaluate(
            client=client, model=args.model,
            sampling_args={"max_tokens": args.max_tokens},
            num_examples=1, rollouts_per_example=1, max_concurrent=1,
            max_retries=args.retries, save_results=False,
        ))
    except env_mod.PIVEvaluationBatchInvalid as exc:
        # Not the model's answer: a provider or evaluator failure. The first
        # live run hit exactly this — an NVIDIA 429 wrapped as ModelError,
        # quarantined, batch INVALID — which is the machinery doing its job.
        print("QUARANTINED — not a scored answer (provider/evaluator failure):")
        print(f"  status={exc.status} reasons={exc.reason_counts}")
        for q in exc.quarantined:
            print(f"  {q}")
        return 2

    out = results["outputs"][0]
    meta = results["metadata"]
    trajectory = out.get("trajectory") or []
    completion = out.get("completion") or []

    tools_called = []
    for message in completion:
        for call in (getattr(message, "tool_calls", None) or (message.get("tool_calls") if isinstance(message, dict) else None) or []):
            if isinstance(call, dict):
                name = call.get("name") or (call.get("function") or {}).get("name")
            else:
                name = getattr(call, "name", None) or getattr(getattr(call, "function", None), "name", None)
            tools_called.append(name or "?")
    metrics = out.get("metrics") or {}

    print("=" * 70)
    print(f"reward        : {out.get('reward')}")
    print(f"batch status  : {meta.get('piv_status')}")
    print(f"error         : {out.get('error')}")
    print(f"stop          : {out.get('stop_condition')}  truncated={out.get('is_truncated')}")
    print(f"turns         : {metrics.get('num_turns', len(trajectory))}")
    print(f"tools called  : {len(tools_called)} -> {tools_called}")
    print(f"metrics       : {metrics}")
    usage = out.get("token_usage") or {}
    if usage:
        print(f"tokens        : {usage}")

    # Score breakdown from the scorer itself, on the ledger the model left.
    # The workspace lives in the framework state, not in the output; rescore
    # from the environment's last workspace if we can find it, else skip.
    new_workspaces = sorted(set(temp_root.glob("beancount_env_*")) - before, key=lambda p: p.stat().st_mtime)
    if new_workspaces:
        ws = new_workspaces[-1]
        raw = (ws / LEDGER).read_bytes()
        submitted = logical_text(raw)
        original = logical_text((WORLD_DIR / LEDGER).read_bytes())
        # The candidate/1 engine, exactly as the environment scores: parse
        # once, commit against the environment's contract, score the
        # committed object. No text reaches the scorer.
        from beancount_ledger.candidate import committed as K
        from beancount_ledger.candidate.normalise import Accepted, parse_once
        parsed = parse_once(submitted)
        print("-" * 70)
        print("scorer breakdown (candidate/1):")
        if isinstance(parsed, Accepted):
            outcome = K.score_committed(K.commit(parsed, env.contract,
                                                 K.new_receipt("live", 1, digests_of(raw, submitted=submitted))))
            breakdown = outcome.as_dict()
            for key in ("total", "components", "gated", "renderable", "target_misses", "unresolved_planted",
                        "removed_or_altered", "fabricated", "merged_events", "undocumented",
                        "plug_accounts", "collateral_damage"):
                if key in breakdown and breakdown[key] not in ([], {}, None, False):
                    print(f"  {key:20s} {breakdown[key]}")
        else:
            print(f"  outcome              {parsed}")
        print("-" * 70)
        print("what the model added to the ledger:")
        added = [l for l in difflib.unified_diff(original.splitlines(), submitted.splitlines(), lineterm="", n=0)
                 if l.startswith("+") and not l.startswith("+++")]
        removed = [l for l in difflib.unified_diff(original.splitlines(), submitted.splitlines(), lineterm="", n=0)
                   if l.startswith("-") and not l.startswith("---")]
        for line in added[:40]:
            print("  " + line)
        if removed:
            print(f"  ({len(removed)} line(s) removed/changed)")
            for line in removed[:10]:
                print("  " + line)
        if not added and not removed:
            print("  (nothing — the ledger is unchanged)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
