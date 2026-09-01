"""Have a model from another family review a set of files against a
question — the "second pair of eyes that is not the author" for code.

    python tests/review_code.py --model openai/gpt-oss-120b --title "allocation" \
        --question "Find logic errors in ..." beancount_ledger/candidate/committed.py ...

The review lands in reviews/code_<title>_<model>_<date>.md. The key is read
from the NVIDIA_API_KEY environment variable or HKCU\\Environment; never
printed. No tools, one request, temperature 0.2.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

INSTRUCTIONS = """You are reviewing code from a deterministic-reward RL environment (Beancount
bank reconciliation). You are not the author; be adversarial and concrete.
For every problem: file, function, the exact line or expression, a
reproduction (input → wrong output), and severity (bug / risk / nit). Do
not restate what the code does. If you find nothing in a file, say so in
one line and name what you checked. Answer in English."""


def _key() -> str:
    key = os.environ.get("NVIDIA_API_KEY")
    if not key and os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
            key = winreg.QueryValueEx(h, "NVIDIA_API_KEY")[0]
    if not key:
        raise SystemExit("no NVIDIA_API_KEY")
    return key


def numbered(text: str) -> str:
    return "\n".join(f"{i:4d}  {line}" for i, line in enumerate(text.splitlines(), 1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    parts = [INSTRUCTIONS, "\n\n# The question\n\n" + args.question.strip() + "\n"]
    for name in args.files:
        path = ROOT / name
        parts.append(f"\n\n# {name}\n\n```python\n{numbered(path.read_text(encoding='utf-8'))}\n```\n")
    prompt = "".join(parts)
    import openai
    client = openai.OpenAI(api_key=_key(), base_url=NVIDIA_BASE_URL, timeout=args.timeout, max_retries=3)
    print(f"model  : {args.model}\nprompt : {len(prompt):,} chars over {len(args.files)} files")
    response = client.chat.completions.create(
        model=args.model, messages=[{"role": "user", "content": prompt}], temperature=0.2, max_tokens=args.max_tokens)
    text = response.choices[0].message.content or ""
    usage = response.usage
    out = ROOT / "reviews"
    out.mkdir(exist_ok=True)
    slug = args.model.split("/")[-1]
    stamp = datetime.now().strftime("%Y-%m-%d")
    path = out / f"code_{args.title}_{slug}_{stamp}.md"
    header = (f"# Code review — {args.title} — {args.model}, {stamp}\n\n*Files: {', '.join(args.files)}. "
              f"Question: {args.question.strip()}*\n\n*Tokens: {usage.prompt_tokens} in, {usage.completion_tokens} out.*\n\n---\n\n")
    path.write_text(header + text, encoding="utf-8")
    print(f"wrote  : {path}\n")
    print(text[:3000])
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
