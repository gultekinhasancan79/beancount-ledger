"""Does this provider accept the request sizes a 25-turn rollout sends? (live, opt-in)

Two empirical questions the rate-limit headers do not always answer:

  1. SIZE — one request with a ~N-token prompt (N in `--sizes`), `max_tokens=10`:
     accepted (HTTP 200, provider-reported prompt_tokens) or refused (the status
     and the provider's message, e.g. Groq's 413 "tokens per minute ... Requested").
  2. BURST — `--burst` requests back to back with no pause: how many succeed,
     how many 429, and the `retry-after` the provider asks for. The measurement
     loop paces itself (`--min-interval`), so this only has to be survivable.

The key is read through `measure_budget.load_key_from_registry()` and passed
only to the `openai` client; never printed. Nothing here writes to the repo.

    tests/request_size_probe.py --provider mistral --model mistral-small-latest
    tests/request_size_probe.py --provider gemini --model gemini-2.5-flash --sizes 12000 30000 100000
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure_budget as mb  # noqa: E402

FILLER = ("2025-11-03 * \"Alpine Supplies\" \"Invoice SI-1042 office paper\"\n"
          "  Expenses:Office        184.20 USD\n  Assets:Bank:Checking\n\n")   # ~30 tokens


def one(client, model, text, max_tokens=10):
    t0 = time.monotonic()
    raw = client.chat.completions.with_raw_response.create(
        model=model, max_tokens=max_tokens, temperature=0.0,
        messages=[{"role": "user", "content": text}])
    resp = raw.parse()
    return raw.status_code, resp, time.monotonic() - t0, raw.headers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, help=f"endpoint preset: {sorted(mb.PROVIDERS)}")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-var", default=None)
    parser.add_argument("--model", required=True)
    parser.add_argument("--sizes", nargs="+", type=int, default=[12_000, 30_000, 60_000])
    parser.add_argument("--burst", type=int, default=5)
    args = parser.parse_args()
    provider, base_url, key_var = mb.configure_provider(args.provider, args.base_url, args.api_key_var)
    mb.load_key_from_registry()
    import openai

    client = openai.OpenAI(api_key=os.environ[key_var], base_url=base_url, timeout=120.0, max_retries=0)
    print(f"provider {provider}, model {args.model}\n\nSIZE")
    for target in args.sizes:
        text = FILLER * max(1, target // 30) + "\nHow many transactions above? Answer with a number."
        try:
            status, resp, took, headers = one(client, args.model, text)
            print(f"  ~{target:>7} tokens: HTTP {status} in {took:.1f}s; prompt_tokens={resp.usage.prompt_tokens}; "
                  f"answer={(resp.choices[0].message.content or '')[:30]!r}")
        except openai.APIStatusError as exc:
            body = getattr(exc, "body", None)
            msg = str(body)[:240] if body is not None else str(exc)[:240]
            print(f"  ~{target:>7} tokens: HTTP {exc.status_code}: {msg}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ~{target:>7} tokens: {type(exc).__name__}: {str(exc)[:200]}")
        time.sleep(2.0)

    print(f"\nBURST ({args.burst} requests, no pause)")
    ok = limited = other = 0
    retry_after = set()
    t0 = time.monotonic()
    for i in range(args.burst):
        try:
            status, resp, took, headers = one(client, args.model, "Reply with the single word OK.", max_tokens=5)
            ok += 1
        except openai.APIStatusError as exc:
            if exc.status_code == 429:
                limited += 1
                ra = getattr(exc, "response", None)
                if ra is not None and ra.headers.get("retry-after"):
                    retry_after.add(ra.headers.get("retry-after"))
            else:
                other += 1
                print(f"  request {i + 1}: HTTP {exc.status_code}: {str(getattr(exc, 'body', exc))[:160]}")
        except Exception as exc:  # noqa: BLE001
            other += 1
            print(f"  request {i + 1}: {type(exc).__name__}: {str(exc)[:160]}")
    print(f"  ok={ok} rate_limited={limited} other={other} in {time.monotonic() - t0:.1f}s; "
          f"retry-after={sorted(retry_after) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
