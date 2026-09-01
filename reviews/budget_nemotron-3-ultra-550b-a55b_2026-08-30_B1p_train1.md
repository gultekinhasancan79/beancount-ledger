# Token budget — nvidia/nemotron-3-ultra-550b-a55b, 2026-08-30_B1p_train1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 1.

| selector | reward | turns | tokens in | tokens out | total | over budget | stop | tools | arm | artifact | submitted |
|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 1.0 | 9.0 | 123754.0 | 18957.0 | 142711 | **yes** | piv_submitted | 15 incl. write_ledger | B1 | BOUND | True |

- total tokens: median 142,711, max 142,711, over budget 1/1
- turns: median 9, max 9.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 8, 'run_beancount': 3, 'list_files': 1, 'grep': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}

## Per-turn detail

### train:1 (arm B1, BOUND, submitted True)
  turn 01  in=1295 out=91 reasoning_tok=0 cum_in=1295 cum_out=91 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 req_cap=16000 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1474 out=162 reasoning_tok=0 cum_in=2769 cum_out=253 msgs=4 reasoning_chars=319 sent=319 visible_chars=409 req_cap=16000 finish=tool_calls trunc=False tools=[read_file,read_file,read_file]
  turn 03  in=5693 out=260 reasoning_tok=0 cum_in=8462 cum_out=513 msgs=8 reasoning_chars=410 sent=410 visible_chars=13017 req_cap=16000 finish=tool_calls trunc=False tools=[read_file,read_file,read_file,read_file,read_file]
  turn 04  in=7821 out=4813 reasoning_tok=0 cum_in=16283 cum_out=5326 msgs=14 reasoning_chars=513 sent=513 visible_chars=16540 req_cap=16000 finish=tool_calls trunc=False tools=[run_beancount]
  turn 05  in=12661 out=3802 reasoning_tok=0 cum_in=28944 cum_out=9128 msgs=16 reasoning_chars=11021 sent=11021 visible_chars=16574 req_cap=16000 finish=tool_calls trunc=False tools=[grep]
  turn 06  in=17115 out=8364 reasoning_tok=0 cum_in=46059 cum_out=17492 msgs=18 reasoning_chars=18194 sent=18194 visible_chars=18622 req_cap=16000 finish=tool_calls trunc=False tools=[write_ledger]
  turn 07  in=25795 out=72 reasoning_tok=0 cum_in=71854 cum_out=17564 msgs=20 reasoning_chars=26060 sent=26060 visible_chars=30239 req_cap=16000 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=25894 out=85 reasoning_tok=0 cum_in=97748 cum_out=17649 msgs=22 reasoning_chars=26323 sent=26323 visible_chars=30273 req_cap=16000 finish=tool_calls trunc=False tools=[run_beancount]
  turn 09  in=26006 out=1308 reasoning_tok=0 cum_in=123754 cum_out=18957 msgs=24 reasoning_chars=26553 sent=26553 visible_chars=30409 req_cap=16000 finish=tool_calls trunc=False tools=[submit]

