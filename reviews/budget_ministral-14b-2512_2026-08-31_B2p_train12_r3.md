# Token budget — ministral-14b-2512, 2026-08-31_B2p_train12_r3

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 3.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.55 | 18.0 | 116676.0 | 4227.0 | 120903 | **yes** | no | piv_submitted | 18 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 120,903, max 120,903, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 18, max 18.0
- reward: mean 0.550 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 9, 'read_file': 5, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
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
  turn 07  in=6936 out=25 reasoning_tok=0 cum_in=23892 cum_out=162 msgs=14 reasoning_chars=0 sent=0 visible_chars=16150 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=7123 out=25 reasoning_tok=0 cum_in=31015 cum_out=187 msgs=16 reasoning_chars=0 sent=0 visible_chars=16534 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=7310 out=25 reasoning_tok=0 cum_in=38325 cum_out=212 msgs=18 reasoning_chars=0 sent=0 visible_chars=16918 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=7458 out=25 reasoning_tok=0 cum_in=45783 cum_out=237 msgs=20 reasoning_chars=0 sent=0 visible_chars=17227 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=7579 out=25 reasoning_tok=0 cum_in=53362 cum_out=262 msgs=22 reasoning_chars=0 sent=0 visible_chars=17470 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=7646 out=25 reasoning_tok=0 cum_in=61008 cum_out=287 msgs=24 reasoning_chars=0 sent=0 visible_chars=17617 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=7720 out=25 reasoning_tok=0 cum_in=68728 cum_out=312 msgs=26 reasoning_chars=0 sent=0 visible_chars=17766 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=7794 out=25 reasoning_tok=0 cum_in=76522 cum_out=337 msgs=28 reasoning_chars=0 sent=0 visible_chars=17919 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=7915 out=22 reasoning_tok=0 cum_in=84437 cum_out=359 msgs=30 reasoning_chars=0 sent=0 visible_chars=18165 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=7973 out=3855 reasoning_tok=0 cum_in=92410 cum_out=4214 msgs=32 reasoning_chars=0 sent=0 visible_chars=18308 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 17  in=12123 out=8 reasoning_tok=0 cum_in=104533 cum_out=4222 msgs=34 reasoning_chars=0 sent=0 visible_chars=30757 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 18  in=12143 out=5 reasoning_tok=0 cum_in=116676 cum_out=4227 msgs=36 reasoning_chars=0 sent=0 visible_chars=30791 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

