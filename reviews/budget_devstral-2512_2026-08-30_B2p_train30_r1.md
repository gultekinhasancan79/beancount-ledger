# Token budget — devstral-2512, 2026-08-30_B2p_train30_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 1.0 | 17.0 | 109934.0 | 4634.0 | 114568 | **yes** | no | piv_submitted | 17 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 114,568, max 114,568, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 17, max 17.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'grep': 6, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:30 (arm B2, BOUND, submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=26 reasoning_tok=0 cum_in=2342 cum_out=32 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1542 out=26 reasoning_tok=0 cum_in=3884 cum_out=58 msgs=6 reasoning_chars=0 sent=0 visible_chars=1319 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2643 out=26 reasoning_tok=0 cum_in=6527 cum_out=84 msgs=8 reasoning_chars=0 sent=0 visible_chars=5077 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=2917 out=27 reasoning_tok=0 cum_in=9444 cum_out=111 msgs=10 reasoning_chars=0 sent=0 visible_chars=5953 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=3006 out=27 reasoning_tok=0 cum_in=12450 cum_out=138 msgs=12 reasoning_chars=0 sent=0 visible_chars=6163 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=3103 out=29 reasoning_tok=0 cum_in=15553 cum_out=167 msgs=14 reasoning_chars=0 sent=0 visible_chars=6430 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=6890 out=28 reasoning_tok=0 cum_in=22443 cum_out=195 msgs=16 reasoning_chars=0 sent=0 visible_chars=17566 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=8409 out=81 reasoning_tok=0 cum_in=30852 cum_out=276 msgs=18 reasoning_chars=0 sent=0 visible_chars=19751 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=8550 out=32 reasoning_tok=0 cum_in=39402 cum_out=308 msgs=20 reasoning_chars=0 sent=0 visible_chars=20098 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=8586 out=99 reasoning_tok=0 cum_in=47988 cum_out=407 msgs=22 reasoning_chars=0 sent=0 visible_chars=20195 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=8732 out=28 reasoning_tok=0 cum_in=56720 cum_out=435 msgs=24 reasoning_chars=0 sent=0 visible_chars=20558 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=8764 out=103 reasoning_tok=0 cum_in=65484 cum_out=538 msgs=26 reasoning_chars=0 sent=0 visible_chars=20637 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=8920 out=29 reasoning_tok=0 cum_in=74404 cum_out=567 msgs=28 reasoning_chars=0 sent=0 visible_chars=20987 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=8953 out=4021 reasoning_tok=0 cum_in=83357 cum_out=4588 msgs=30 reasoning_chars=0 sent=0 visible_chars=21064 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 16  in=13270 out=25 reasoning_tok=0 cum_in=96627 cum_out=4613 msgs=32 reasoning_chars=0 sent=0 visible_chars=33654 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 17  in=13307 out=21 reasoning_tok=0 cum_in=109934 cum_out=4634 msgs=34 reasoning_chars=0 sent=0 visible_chars=33778 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[submit]

