# Token budget — mistral-medium-2508, 2026-08-30_Ap_train1_r3

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 3.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 1.0 | 6.0 | 31044.0 | 6082.0 | 37126 | no | no | piv_submitted | 6 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 37,126, max 37,126, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 6, max 6.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 3, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:1 (arm A, BOUND, submitted True)
  turn 01  in=1135 out=162 reasoning_tok=0 cum_in=1135 cum_out=162 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1371 out=70 reasoning_tok=0 cum_in=2506 cum_out=232 msgs=4 reasoning_chars=0 sent=0 visible_chars=1097 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4106 out=58 reasoning_tok=0 cum_in=6612 cum_out=290 msgs=6 reasoning_chars=0 sent=0 visible_chars=9228 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=5313 out=293 reasoning_tok=0 cum_in=11925 cum_out=583 msgs=8 reasoning_chars=0 sent=0 visible_chars=11037 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=6672 out=5476 reasoning_tok=0 cum_in=18597 cum_out=6059 msgs=10 reasoning_chars=0 sent=0 visible_chars=15917 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[write_ledger]
  turn 06  in=12447 out=23 reasoning_tok=0 cum_in=31044 cum_out=6082 msgs=12 reasoning_chars=0 sent=0 visible_chars=32874 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[submit]

