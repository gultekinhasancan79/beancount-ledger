"""Live, opt-in, ~1 minute. NOT run by tests/run_all.py.

Answers two of Codex Turn 46's open questions (`design_chat/from_codex.md`
§2, §7, "Questions" 2 and 4) about the NVIDIA endpoint directly, with the raw
`openai` client rather than through the framework:

  Q4: does the endpoint accept a multi-turn tool-call conversation when the
      earlier assistant message is replayed WITHOUT its `reasoning_content`?
  Q2: do the provider's usage fields report reasoning tokens, and does
      `completion_tokens` include them?

    python tests/live_replay_probe.py

The key is read from HKCU\\Environment (NVIDIA_API_KEY) via
`measure_budget.load_key_from_registry()` and passed only to the `openai`
client; it is never printed, and neither are raw request headers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import measure_budget as mb  # noqa: E402 -- reuses load_key_from_registry, NVIDIA_BASE_URL, KEY_VAR

TOOL = {
    "type": "function",
    "function": {
        "name": "get_balance",
        "description": "Get the current balance of an account.",
        "parameters": {
            "type": "object",
            "properties": {"account": {"type": "string", "description": "The account name, e.g. Assets:Checking."}},
            "required": ["account"],
        },
    },
}
SYSTEM = "You are a bookkeeping assistant. Use the get_balance tool whenever asked about a balance."
USER = "What is the balance of Assets:Checking?"
PREFERRED_MODEL = "nvidia/nemotron-3-nano-30b-a3b"


def pick_model(client) -> str:
    """`PREFERRED_MODEL` if the endpoint currently lists it; else the
    cheapest nemotron-3 model it lists (nano, then super, then ultra, by
    name) -- never a hardcoded guess the endpoint might not actually serve."""
    try:
        listed = [m.id for m in client.models.list().data]
    except Exception as exc:                                   # noqa: BLE001
        print(f"could not list models ({type(exc).__name__}: {exc}); falling back to the fixed nano id")
        return PREFERRED_MODEL
    if PREFERRED_MODEL in listed:
        return PREFERRED_MODEL
    nemotron3 = sorted(m for m in listed if "nemotron-3" in m)
    for tier in ("nano", "super", "ultra"):
        for m in nemotron3:
            if tier in m:
                print(f"{PREFERRED_MODEL!r} not listed; falling back to {m!r} (endpoint lists: {nemotron3})")
                return m
    if nemotron3:
        print(f"{PREFERRED_MODEL!r} not listed; falling back to {nemotron3[0]!r} (endpoint lists: {nemotron3})")
        return nemotron3[0]
    raise RuntimeError(f"no nemotron-3 model listed by the endpoint at all: {sorted(listed)}")


def usage_fields(usage) -> dict:
    if usage is None:
        return {"prompt_tokens": None, "completion_tokens": None, "reasoning_tokens": None}
    details = getattr(usage, "completion_tokens_details", None)
    reasoning = getattr(details, "reasoning_tokens", None) if details is not None else None
    if reasoning is None:
        reasoning = getattr(usage, "reasoning_tokens", None)   # some providers put it top-level instead
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "reasoning_tokens": reasoning,
    }


def call(client, model, messages, tools=None):
    """(status_code, parsed ChatCompletion). The raw-response door, so "HTTP
    200" is an actual asserted fact rather than "no exception was raised"."""
    raw = client.chat.completions.with_raw_response.create(
        model=model, messages=messages, tools=tools, max_tokens=512)
    return raw.status_code, raw.parse()


def report_turn(label: str, status: int, message, usage) -> dict:
    u = usage_fields(usage)
    reasoning_chars = len(getattr(message, "reasoning_content", "") or "")
    print(f"{label}: HTTP {status}  prompt_tokens={u['prompt_tokens']} completion_tokens={u['completion_tokens']} "
         f"reasoning_tokens={u['reasoning_tokens']} reasoning_content_chars={reasoning_chars}")
    return u


def main() -> int:
    import argparse
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
    model = args.model or pick_model(client)
    print(f"probing {model} at {mb.BASE_URL}\n")

    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}]
    status1, resp1 = call(client, model, messages, tools=[TOOL])
    msg1 = resp1.choices[0].message
    report_turn("turn 1 (tool request)", status1, msg1, resp1.usage)
    assert status1 == 200, f"turn 1: HTTP {status1}"

    if not msg1.tool_calls:
        print(f"turn 1 produced no tool call (finish_reason={resp1.choices[0].finish_reason}, "
             f"content={msg1.content!r}) -- cannot continue the Q4 multi-turn tool-call probe")
        return 1
    tool_call = msg1.tool_calls[0]
    print(f"turn 1 called {tool_call.function.name}({tool_call.function.arguments})")
    tool_result = {"role": "tool", "tool_call_id": tool_call.id, "content": "1234.56 USD"}
    assistant_calls = [{"id": tc.id, "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                       for tc in msg1.tool_calls]

    # Q4: turn 2 WITHOUT the earlier assistant message's reasoning_content.
    assistant_no_reasoning = {"role": "assistant", "content": msg1.content, "tool_calls": assistant_calls}
    messages_no_reasoning = messages + [assistant_no_reasoning, tool_result]
    status2, resp2 = call(client, model, messages_no_reasoning)
    msg2 = resp2.choices[0].message
    u2 = report_turn("turn 2, reasoning NOT replayed", status2, msg2, resp2.usage)
    assert status2 == 200, f"turn 2 (no reasoning replay): HTTP {status2}"
    assert (msg2.content or "").strip(), "turn 2 (no reasoning replay) returned no final answer content"
    print(f"turn 2 (no reasoning replay) final answer: {msg2.content!r}")

    # Q2 comparison: the same turn 2, but WITH reasoning replayed, if the
    # provider gave us any reasoning_content to replay in the first place.
    reasoning_text = getattr(msg1, "reasoning_content", None)
    if reasoning_text:
        assistant_with_reasoning = {"role": "assistant", "content": msg1.content, "tool_calls": assistant_calls,
                                    "reasoning_content": reasoning_text}
        messages_with_reasoning = messages + [assistant_with_reasoning, tool_result]
        status3, resp3 = call(client, model, messages_with_reasoning)
        msg3 = resp3.choices[0].message
        u3 = report_turn("turn 2, reasoning REPLAYED", status3, msg3, resp3.usage)
        assert status3 == 200, f"turn 2 (reasoning replayed): HTTP {status3}"
        if u2["prompt_tokens"] is not None and u3["prompt_tokens"] is not None:
            smaller = u2["prompt_tokens"] < u3["prompt_tokens"]
            print(f"\nQ2/Q4 comparison: prompt_tokens without replay ({u2['prompt_tokens']}) "
                 f"{'<' if smaller else '>=' } with replay ({u3['prompt_tokens']}) "
                 f"-- dropping reasoning_content {'reduced' if smaller else 'did NOT reduce'} prompt_tokens")
        else:
            print("\nQ2/Q4 comparison: the endpoint did not report prompt_tokens for one of the two calls")
    else:
        print(f"\nturn 1 returned no reasoning_content to replay at all (model={model!r}); "
             "the with/without-replay prompt_tokens comparison is not meaningful for this model")

    print("\nQ4 answer: the endpoint accepted the multi-turn tool-call conversation with the earlier assistant "
         "message's reasoning_content omitted (HTTP 200, a coherent final answer).")
    print("Q2 answer: see the reasoning_tokens field printed per turn above (None means the provider did not "
         "report it under completion_tokens_details.reasoning_tokens or top-level reasoning_tokens for this model).")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
