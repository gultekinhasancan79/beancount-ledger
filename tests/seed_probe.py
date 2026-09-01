"""Live, opt-in, ~1 minute. NOT run by tests/run_all.py.

Answers Codex Turn 47 §8/Q11 directly, with the raw `openai` client (the
same pattern `live_replay_probe.py` uses): does the NVIDIA endpoint actually
HONOUR `seed`, or does it merely accept the parameter and return HTTP 200
while still sampling non-deterministically? A 200 response alone does not
prove the endpoint pays attention to `seed` at all.

Sends the SAME single-turn request THREE times with `seed=1234,
temperature=0`, and once more with `seed=1235`. Reports:

  seed_honored: true  iff all three seed=1234 responses' message content are
                      byte-identical to each other.
  different_seed_differs: true iff the seed=1235 response's content differs
                      from the (identical) seed=1234 content.

Prints usage (prompt_tokens/completion_tokens) per call. The key is read
from HKCU\\Environment (NVIDIA_API_KEY) via `measure_budget.
load_key_from_registry()` and passed only to the `openai` client; it is
never printed, and neither are raw request headers.

    python tests/seed_probe.py --model nvidia/nemotron-3-nano-30b-a3b
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import measure_budget as mb  # noqa: E402 -- reuses load_key_from_registry, NVIDIA_BASE_URL, KEY_VAR
import live_replay_probe as lrp  # noqa: E402 -- reuses pick_model, usage_fields

SYSTEM = "You are a terse creative-writing assistant."
USER = "In one sentence, invent a short fictional startup name and what it sells."
MAX_TOKENS = 64


def call(client, model, seed: int, temperature: float = 0.0):
    """(status_code, parsed ChatCompletion) for one single-turn request."""
    raw = client.chat.completions.with_raw_response.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
        max_tokens=MAX_TOKENS, temperature=temperature, seed=seed)
    return raw.status_code, raw.parse()


def report(label: str, status: int, message, usage) -> str:
    u = lrp.usage_fields(usage)
    content = (message.content or "").strip()
    print(f"{label}: HTTP {status}  prompt_tokens={u['prompt_tokens']} completion_tokens={u['completion_tokens']} "
         f"content={content!r}")
    return content


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="defaults to the preferred/cheapest nemotron-3 model listed")
    parser.add_argument("--provider", default="nvidia", help=f"endpoint preset: {sorted(mb.PROVIDERS)}")
    parser.add_argument("--base-url", default=None, help="explicit OpenAI-compatible base URL (overrides the preset)")
    parser.add_argument("--api-key-var", default=None, help="environment / HKCU variable holding the key")
    args = parser.parse_args()

    mb.configure_provider(args.provider, args.base_url, args.api_key_var)
    mb.load_key_from_registry()
    import openai

    client = openai.OpenAI(api_key=os.environ[mb.KEY_VAR], base_url=mb.BASE_URL, timeout=60.0)
    model = args.model or lrp.pick_model(client)
    print(f"probing seed honouring for {model} at {mb.BASE_URL}\n")

    seed1234_contents = []
    for i in range(3):
        status, resp = call(client, model, seed=1234)
        if status != 200:
            print(f"seed=1234 call {i + 1}: HTTP {status} -- cannot continue the probe")
            return 1
        content = report(f"seed=1234 call {i + 1}", status, resp.choices[0].message, resp.usage)
        seed1234_contents.append(content)

    status, resp = call(client, model, seed=1235)
    if status != 200:
        print(f"seed=1235 call: HTTP {status} -- cannot continue the probe")
        return 1
    seed1235_content = report("seed=1235 call", status, resp.choices[0].message, resp.usage)

    seed_honored = len(set(seed1234_contents)) == 1
    different_seed_differs = seed1235_content != seed1234_contents[0]

    print(f"\nseed_honored: {'true' if seed_honored else 'false'}  "
         f"(three seed=1234, temperature=0 calls {'were' if seed_honored else 'were NOT'} byte-identical)")
    print(f"different_seed_differs: {'true' if different_seed_differs else 'false'}  "
         f"(seed=1235's output {'differs' if different_seed_differs else 'matches'} seed=1234's)")
    if not seed_honored:
        print("\nWARNING: this endpoint did NOT return byte-identical output across three seed=1234, "
             "temperature=0 calls -- do not treat --seed as making a replication run reproducible for this "
             "model until this changes.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
