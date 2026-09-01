# Token budget — mistral-medium-2508, 2026-08-30_B1p_train1_r3

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 3.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 1.0 | 5.0 | 20653.0 | 3420.0 | 24073 | no | no | piv_submitted | 5 incl. write_ledger | B1 | BOUND | True | VALID |

- total tokens: median 24,073, max 24,073, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 5, max 5.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:1 (arm B1, BOUND, submitted True)
  turn 01  in=1135 out=162 reasoning_tok=0 cum_in=1135 cum_out=162 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1371 out=78 reasoning_tok=0 cum_in=2506 cum_out=240 msgs=4 reasoning_chars=0 sent=0 visible_chars=1097 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4114 out=59 reasoning_tok=0 cum_in=6620 cum_out=299 msgs=6 reasoning_chars=0 sent=0 visible_chars=9262 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=5322 out=3093 reasoning_tok=0 cum_in=11942 cum_out=3392 msgs=8 reasoning_chars=0 sent=0 visible_chars=11087 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[write_ledger]
  turn 05  in=8711 out=28 reasoning_tok=0 cum_in=20653 cum_out=3420 msgs=10 reasoning_chars=0 sent=0 visible_chars=21178 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[submit]

