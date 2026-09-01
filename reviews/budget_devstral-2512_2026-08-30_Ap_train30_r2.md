# Token budget — devstral-2512, 2026-08-30_Ap_train30_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 1.0 | 13.0 | 69769.0 | 4561.0 | 74330 | **yes** | no | piv_submitted | 13 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 74,330, max 74,330, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 13, max 13.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'grep': 2, 'list_files': 1, 'run_beancount': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:30 (arm A, BOUND, submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=26 reasoning_tok=0 cum_in=2342 cum_out=32 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1542 out=26 reasoning_tok=0 cum_in=3884 cum_out=58 msgs=6 reasoning_chars=0 sent=0 visible_chars=1319 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2643 out=26 reasoning_tok=0 cum_in=6527 cum_out=84 msgs=8 reasoning_chars=0 sent=0 visible_chars=5077 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=2917 out=27 reasoning_tok=0 cum_in=9444 cum_out=111 msgs=10 reasoning_chars=0 sent=0 visible_chars=5953 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=3006 out=27 reasoning_tok=0 cum_in=12450 cum_out=138 msgs=12 reasoning_chars=0 sent=0 visible_chars=6163 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=3103 out=29 reasoning_tok=0 cum_in=15553 cum_out=167 msgs=14 reasoning_chars=0 sent=0 visible_chars=6430 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=6890 out=28 reasoning_tok=0 cum_in=22443 cum_out=195 msgs=16 reasoning_chars=0 sent=0 visible_chars=17566 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=8409 out=30 reasoning_tok=0 cum_in=30852 cum_out=225 msgs=18 reasoning_chars=0 sent=0 visible_chars=19751 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=8451 out=186 reasoning_tok=0 cum_in=39303 cum_out=411 msgs=20 reasoning_chars=0 sent=0 visible_chars=19915 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=8641 out=25 reasoning_tok=0 cum_in=47944 cum_out=436 msgs=22 reasoning_chars=0 sent=0 visible_chars=20446 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=8705 out=4120 reasoning_tok=0 cum_in=56649 cum_out=4556 msgs=24 reasoning_chars=0 sent=0 visible_chars=20574 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 13  in=13120 out=5 reasoning_tok=0 cum_in=69769 cum_out=4561 msgs=26 reasoning_chars=0 sent=0 visible_chars=33345 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[submit]

