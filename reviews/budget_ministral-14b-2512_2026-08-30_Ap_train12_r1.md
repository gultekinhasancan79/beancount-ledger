# Token budget — ministral-14b-2512, 2026-08-30_Ap_train12_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.55 | 16.0 | 100699.0 | 4393.0 | 105092 | **yes** | no | piv_submitted | 16 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 105,092, max 105,092, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 16, max 16.0
- reward: mean 0.550 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 7, 'read_file': 5, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:12 (arm A, BOUND, submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=25 reasoning_tok=0 cum_in=2342 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1542 out=25 reasoning_tok=0 cum_in=3884 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1331 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2633 out=27 reasoning_tok=0 cum_in=6517 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5070 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3777 out=29 reasoning_tok=0 cum_in=10294 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6741 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6662 out=25 reasoning_tok=0 cum_in=16956 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=15266 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6936 out=25 reasoning_tok=0 cum_in=23892 cum_out=162 msgs=14 reasoning_chars=0 sent=0 visible_chars=16150 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=7123 out=25 reasoning_tok=0 cum_in=31015 cum_out=187 msgs=16 reasoning_chars=0 sent=0 visible_chars=16534 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=7310 out=25 reasoning_tok=0 cum_in=38325 cum_out=212 msgs=18 reasoning_chars=0 sent=0 visible_chars=16918 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=7431 out=25 reasoning_tok=0 cum_in=45756 cum_out=237 msgs=20 reasoning_chars=0 sent=0 visible_chars=17161 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=7498 out=22 reasoning_tok=0 cum_in=53254 cum_out=259 msgs=22 reasoning_chars=0 sent=0 visible_chars=17308 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=7556 out=25 reasoning_tok=0 cum_in=60810 cum_out=284 msgs=24 reasoning_chars=0 sent=0 visible_chars=17451 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=7704 out=25 reasoning_tok=0 cum_in=68514 cum_out=309 msgs=26 reasoning_chars=0 sent=0 visible_chars=17760 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=7811 out=4071 reasoning_tok=0 cum_in=76325 cum_out=4380 msgs=28 reasoning_chars=0 sent=0 visible_chars=17976 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 15  in=12177 out=8 reasoning_tok=0 cum_in=88502 cum_out=4388 msgs=30 reasoning_chars=0 sent=0 visible_chars=30248 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 16  in=12197 out=5 reasoning_tok=0 cum_in=100699 cum_out=4393 msgs=32 reasoning_chars=0 sent=0 visible_chars=30282 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

