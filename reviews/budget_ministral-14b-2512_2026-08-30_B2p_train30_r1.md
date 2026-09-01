# Token budget — ministral-14b-2512, 2026-08-30_B2p_train30_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 0.383333 | 9.0 | 43740.0 | 5019.0 | 48759 | no | no | piv_submitted | 9 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 48,759, max 48,759, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 9, max 9.0
- reward: mean 0.383 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 5, 'list_files': 1, 'run_beancount': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:30 (arm B2, BOUND, submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=25 reasoning_tok=0 cum_in=2342 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1541 out=25 reasoning_tok=0 cum_in=3883 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1318 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2641 out=25 reasoning_tok=0 cum_in=6524 cum_out=81 msgs=8 reasoning_chars=0 sent=0 visible_chars=5075 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=2914 out=27 reasoning_tok=0 cum_in=9438 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=5950 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4432 out=29 reasoning_tok=0 cum_in=13870 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=8134 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=8219 out=8 reasoning_tok=0 cum_in=22089 cum_out=145 msgs=14 reasoning_chars=0 sent=0 visible_chars=19270 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=8239 out=4869 reasoning_tok=0 cum_in=30328 cum_out=5014 msgs=16 reasoning_chars=0 sent=0 visible_chars=19304 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=13412 out=5 reasoning_tok=0 cum_in=43740 cum_out=5019 msgs=18 reasoning_chars=0 sent=0 visible_chars=34279 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

