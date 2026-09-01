# Token budget — ministral-14b-2512, 2026-08-30_B2p_train12_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.55 | 11.0 | 59561.0 | 3684.0 | 63245 | **yes** | no | piv_submitted | 11 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 63,245, max 63,245, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 11, max 11.0
- reward: mean 0.550 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:12 (arm B2, BOUND, submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=25 reasoning_tok=0 cum_in=2342 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1542 out=25 reasoning_tok=0 cum_in=3884 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1331 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2633 out=27 reasoning_tok=0 cum_in=6517 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5070 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3777 out=29 reasoning_tok=0 cum_in=10294 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6741 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6662 out=25 reasoning_tok=0 cum_in=16956 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=15266 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6936 out=25 reasoning_tok=0 cum_in=23892 cum_out=162 msgs=14 reasoning_chars=0 sent=0 visible_chars=16150 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=7027 out=25 reasoning_tok=0 cum_in=30919 cum_out=187 msgs=16 reasoning_chars=0 sent=0 visible_chars=16409 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=7100 out=3366 reasoning_tok=0 cum_in=38019 cum_out=3553 msgs=18 reasoning_chars=0 sent=0 visible_chars=16582 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 10  in=10761 out=8 reasoning_tok=0 cum_in=48780 cum_out=3561 msgs=20 reasoning_chars=0 sent=0 visible_chars=27462 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 11  in=10781 out=123 reasoning_tok=0 cum_in=59561 cum_out=3684 msgs=22 reasoning_chars=0 sent=0 visible_chars=27496 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

