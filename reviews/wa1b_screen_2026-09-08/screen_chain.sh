#!/usr/bin/env bash
# Subjects 2-4 of wa1b/screen-1, strictly one after another, starting only when
# subject 1's process has exited. Sequential subjects keep every pair's two arms
# adjacent with no unrelated rollout in between (astra round 9 §4). Each subject
# writes to the shared jsonl (rows carry their config_key) and its own log.
set -u
S="/c/Users/gulte/AppData/Local/Temp/claude/C--Users-gulte-Desktop-PIV/e5af9fd8-5589-401a-8521-18264e0703e0/scratchpad"
PY="/c/Users/gulte/Desktop/PIV/beancount-ledger-workflows/.venv/Scripts/python.exe"
BASE="https://ws-r76rtaa6sn7jqbcr.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
cd /c/Users/gulte/Desktop/PIV/beancount-ledger-workflows || exit 1
running() { powershell -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { \$_.Name -eq 'python.exe' -and \$_.CommandLine -like '*wa1b_run.py*' }).Count" | tr -d '\r '; }
while [ "$(running)" != "0" ]; do sleep 60; done
echo "subject 1 finished at $(date -Iseconds)"
for SUBJ in deepseek-v4-flash glm-5.2 kimi-k3; do
  echo "=== $SUBJ start $(date -Iseconds)"
  "$PY" "$S/wa1b_run.py" --screen "$SUBJ" --model "$SUBJ" --base-url "$BASE" --key-var DASHSCOPE_API_KEY \
    --adjudication "$S/wa1b_adjudication_relaxed.jsonl" --max-tokens 40000 --tokens 40000 --pace 10 --resume \
    --jsonl "$S/wa1b_screen.jsonl" > "$S/wa1b_screen_${SUBJ}.log" 2>&1
  echo "=== $SUBJ exit=$? $(date -Iseconds)"
done
echo "chain done $(date -Iseconds)"
