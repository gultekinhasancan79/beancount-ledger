#!/usr/bin/env bash
set -u
S="/c/Users/gulte/AppData/Local/Temp/claude/C--Users-gulte-Desktop-PIV/e5af9fd8-5589-401a-8521-18264e0703e0/scratchpad"
PY="/c/Users/gulte/Desktop/PIV/beancount-ledger-workflows/.venv/Scripts/python.exe"
cd /c/Users/gulte/Desktop/PIV/beancount-ledger-workflows || exit 1
"$PY" "$S/wa1b_run.py" --screen qwen3.7-max --model qwen3.7-max \
  --base-url https://ws-r76rtaa6sn7jqbcr.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1 --key-var DASHSCOPE_API_KEY \
  --adjudication "$S/wa1b_adjudication_relaxed.jsonl" --max-tokens 40000 --tokens 40000 --pace 10 --resume \
  --jsonl "$S/wa1b_screen.jsonl"
echo "exit=$? at $(date -Iseconds)"
