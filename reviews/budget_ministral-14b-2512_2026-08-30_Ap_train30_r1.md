# Token budget — ministral-14b-2512, 2026-08-30_Ap_train30_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 1.0 | 14.0 | 96982.0 | 6921.0 | 103903 | **yes** | no | piv_submitted | 14 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 103,903, max 103,903, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 14, max 14.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 5, 'grep': 4, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:30 (arm A, BOUND, submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=25 reasoning_tok=0 cum_in=2342 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1541 out=25 reasoning_tok=0 cum_in=3883 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1318 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2641 out=25 reasoning_tok=0 cum_in=6524 cum_out=81 msgs=8 reasoning_chars=0 sent=0 visible_chars=5075 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=2914 out=27 reasoning_tok=0 cum_in=9438 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=5950 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4432 out=29 reasoning_tok=0 cum_in=13870 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=8134 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=8219 out=8 reasoning_tok=0 cum_in=22089 cum_out=145 msgs=14 reasoning_chars=0 sent=0 visible_chars=19270 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=8239 out=179 reasoning_tok=0 cum_in=30328 cum_out=324 msgs=16 reasoning_chars=0 sent=0 visible_chars=19304 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=8422 out=21 reasoning_tok=0 cum_in=38750 cum_out=345 msgs=18 reasoning_chars=0 sent=0 visible_chars=20119 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=8447 out=22 reasoning_tok=0 cum_in=47197 cum_out=367 msgs=20 reasoning_chars=0 sent=0 visible_chars=20179 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=8473 out=141 reasoning_tok=0 cum_in=55670 cum_out=508 msgs=22 reasoning_chars=0 sent=0 visible_chars=20237 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=9378 out=6277 reasoning_tok=0 cum_in=65048 cum_out=6785 msgs=24 reasoning_chars=0 sent=0 visible_chars=23084 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 13  in=15957 out=8 reasoning_tok=0 cum_in=81005 cum_out=6793 msgs=26 reasoning_chars=0 sent=0 visible_chars=40305 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 14  in=15977 out=128 reasoning_tok=0 cum_in=96982 cum_out=6921 msgs=28 reasoning_chars=0 sent=0 visible_chars=40339 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

