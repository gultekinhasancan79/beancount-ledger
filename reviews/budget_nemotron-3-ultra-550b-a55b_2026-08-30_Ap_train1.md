# Token budget — nvidia/nemotron-3-ultra-550b-a55b, 2026-08-30_Ap_train1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 1.

| selector | reward | turns | tokens in | tokens out | total | over budget | stop | tools | arm | artifact | submitted |
|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 1.0 | 10.0 | 99540.0 | 14165.0 | 113705 | **yes** | piv_submitted | 13 incl. write_ledger | A | BOUND | True |

- total tokens: median 113,705, max 113,705, over budget 1/1
- turns: median 10, max 10.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 8, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}

## Per-turn detail

### train:1 (arm A, BOUND, submitted True)
  turn 01  in=1295 out=98 reasoning_tok=0 cum_in=1295 cum_out=98 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 req_cap=8000 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1481 out=169 reasoning_tok=0 cum_in=2776 cum_out=267 msgs=4 reasoning_chars=358 sent=358 visible_chars=409 req_cap=8000 finish=tool_calls trunc=False tools=[read_file,read_file,read_file]
  turn 03  in=5707 out=65 reasoning_tok=0 cum_in=8483 cum_out=332 msgs=8 reasoning_chars=471 sent=471 visible_chars=13017 req_cap=8000 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=6936 out=101 reasoning_tok=0 cum_in=15419 cum_out=433 msgs=10 reasoning_chars=536 sent=536 visible_chars=14694 req_cap=8000 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=7374 out=2585 reasoning_tok=0 cum_in=22793 cum_out=3018 msgs=12 reasoning_chars=789 sent=789 visible_chars=15232 req_cap=8000 finish=tool_calls trunc=False tools=[read_file,read_file]
  turn 06  in=10096 out=73 reasoning_tok=0 cum_in=32889 cum_out=3091 msgs=15 reasoning_chars=5840 sent=5840 visible_chars=15659 req_cap=8000 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=10435 out=3550 reasoning_tok=0 cum_in=43324 cum_out=6641 msgs=17 reasoning_chars=5956 sent=5956 visible_chars=16540 req_cap=8000 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=14012 out=6722 reasoning_tok=0 cum_in=57336 cum_out=13363 msgs=19 reasoning_chars=13180 sent=13180 visible_chars=16574 req_cap=8000 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=21050 out=77 reasoning_tok=0 cum_in=78386 cum_out=13440 msgs=21 reasoning_chars=21015 sent=21015 visible_chars=26358 req_cap=8000 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=21154 out=725 reasoning_tok=0 cum_in=99540 cum_out=14165 msgs=23 reasoning_chars=21282 sent=21282 visible_chars=26392 req_cap=8000 finish=tool_calls trunc=False tools=[submit]

