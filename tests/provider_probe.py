"""Is this OpenAI-compatible endpoint usable for the measurement loop? (live, opt-in)

For a provider preset (`--provider groq`, `nvidia`, or `--base-url`), reports:

  1. the models the endpoint lists (ids only);
  2. for each candidate (`--models`, or every listed id matching `--match`), a
     two-turn tool-call probe: turn 1 must produce a tool call, turn 2 replays
     the assistant message WITHOUT `reasoning_content` plus the tool result and
     must produce a final answer — HTTP status, latency, usage fields, whether
     `reasoning_content` / `reasoning` came back;
  3. the rate-limit headers the provider sends (`x-ratelimit-limit-tokens`,
     `-remaining-tokens`, `-limit-requests`, `-remaining-requests`, `retry-after`),
     which decide whether a 25-turn rollout that replays 20–100K tokens of
     history can run at all on this tier.

The key is read through `measure_budget.load_key_from_registry()` (environment
or HKCU\\Environment) and passed only to the `openai` client; it is never
printed. Nothing here writes to the repository.

    tests/provider_probe.py --provider groq --match "llama|qwen|gpt-oss|kimi|deepseek"
    tests/provider_probe.py --provider groq --models openai/gpt-oss-120b qwen/qwen3-32b
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure_budget as mb  # noqa: E402

SYSTEM = "You are a bookkeeping assistant. Use the tool when a balance is needed. Be brief."
USER = "What is the current balance of Assets:Checking? Use the tool, then answer in one sentence."
TOOL = {
    "type": "function",
    "function": {
        "name": "get_balance",
        "description": "Return the current balance of one ledger account.",
        "parameters": {"type": "object", "properties": {"account": {"type": "string"}}, "required": ["account"]},
    },
}
RL_HEADERS = ("x-ratelimit-limit-requests", "x-ratelimit-limit-tokens", "x-ratelimit-remaining-requests",
              "x-ratelimit-remaining-tokens", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens", "retry-after")


def usage_fields(usage) -> dict:
    if usage is None:
        return {"prompt_tokens": None, "completion_tokens": None, "reasoning_tokens": None}
    details = getattr(usage, "completion_tokens_details", None)
    reasoning = getattr(details, "reasoning_tokens", None) if details is not None else None
    if reasoning is None:
        reasoning = getattr(usage, "reasoning_tokens", None)
    return {"prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "reasoning_tokens": reasoning}


def call(client, model, messages, tools=None, max_tokens=400):
    t0 = time.monotonic()
    raw = client.chat.completions.with_raw_response.create(
        model=model, messages=messages, tools=tools, max_tokens=max_tokens, temperature=0.0)
    took = time.monotonic() - t0
    headers = {h: raw.headers.get(h) for h in RL_HEADERS if raw.headers.get(h) is not None}
    return raw.status_code, raw.parse(), took, headers


def probe_model(client, model: str) -> dict:
    out = {"model": model}
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}]
    try:
        status, resp, took, headers = call(client, model, messages, tools=[TOOL])
    except Exception as exc:  # noqa: BLE001 — a refused model is a finding, not a crash
        out.update(turn1="ERROR", error=f"{type(exc).__name__}: {str(exc)[:160]}")
        return out
    msg = resp.choices[0].message
    calls = list(getattr(msg, "tool_calls", None) or [])
    out.update(turn1=f"HTTP {status} in {took:.1f}s", tool_call=bool(calls), usage1=usage_fields(resp.usage),
               reasoning_field=bool(getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)),
               ratelimit=headers)
    if not calls:
        out["turn1_text"] = (msg.content or "")[:120]
        return out
    tc = calls[0]
    assistant = {"role": "assistant", "content": msg.content or "",
                 "tool_calls": [{"id": tc.id, "type": "function",
                                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}]}
    messages = messages + [assistant, {"role": "tool", "tool_call_id": tc.id,
                                       "content": json.dumps({"account": "Assets:Checking", "balance": "1234.56 USD"})}]
    try:
        status2, resp2, took2, headers2 = call(client, model, messages, tools=[TOOL])
    except Exception as exc:  # noqa: BLE001
        out.update(turn2="ERROR", error=f"{type(exc).__name__}: {str(exc)[:160]}")
        return out
    msg2 = resp2.choices[0].message
    out.update(turn2=f"HTTP {status2} in {took2:.1f}s", usage2=usage_fields(resp2.usage),
               answer=(msg2.content or "")[:100].replace("\n", " "), ratelimit=headers2 or headers)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="groq", help=f"endpoint preset: {sorted(mb.PROVIDERS)}")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-var", default=None)
    parser.add_argument("--models", nargs="*", default=None, help="model ids to probe (default: every listed id matching --match)")
    parser.add_argument("--match", default=r"llama|qwen|gpt-oss|kimi|deepseek|nemotron|mistral|glm|compound",
                        help="regex over listed model ids when --models is not given")
    parser.add_argument("--limit", type=int, default=12, help="probe at most this many models")
    args = parser.parse_args()
    provider, base_url, key_var = mb.configure_provider(args.provider, args.base_url, args.api_key_var)
    mb.load_key_from_registry()
    import openai

    client = openai.OpenAI(api_key=os.environ[key_var], base_url=base_url, timeout=90.0, max_retries=0)
    listed = sorted(m.id for m in client.models.list().data)
    print(f"provider {provider} at {base_url}: {len(listed)} models listed")
    for m in listed:
        print(f"  {m}")
    candidates = args.models or [m for m in listed if re.search(args.match, m, re.I)][: args.limit]
    print(f"\nprobing {len(candidates)} models (two-turn tool call, reasoning not replayed)\n")
    rows = []
    for model in candidates:
        row = probe_model(client, model)
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
        time.sleep(1.0)
    print("\nsummary")
    for r in rows:
        ok = r.get("tool_call") and str(r.get("turn2", "")).startswith("HTTP 200")
        rl = r.get("ratelimit") or {}
        print(f"  {'ok  ' if ok else 'FAIL'} {r['model']:45s} turn1={r.get('turn1')} turn2={r.get('turn2')} "
              f"tokens/min={rl.get('x-ratelimit-limit-tokens')} req/day={rl.get('x-ratelimit-limit-requests')} "
              f"reasoning_field={r.get('reasoning_field')} {r.get('error', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
