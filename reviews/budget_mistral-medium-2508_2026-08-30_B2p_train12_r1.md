# Token budget — mistral-medium-2508, 2026-08-30_B2p_train12_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 1.0 | 5.0 | 30678.0 | 3228.0 | 33906 | no | no | piv_submitted | 8 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 33,906, max 33,906, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 5, max 5.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 4, 'list_files': 1, 'grep': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:12 (arm B2, BOUND, submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=105 reasoning_tok=0 cum_in=2342 cum_out=111 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file,read_file,read_file,grep]
  turn 03  in=6359 out=132 reasoning_tok=0 cum_in=8701 cum_out=243 msgs=9 reasoning_chars=0 sent=0 visible_chars=14420 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=9347 out=2980 reasoning_tok=0 cum_in=18048 cum_out=3223 msgs=11 reasoning_chars=0 sent=0 visible_chars=23331 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[write_ledger]
  turn 05  in=12630 out=5 reasoning_tok=0 cum_in=30678 cum_out=3228 msgs=13 reasoning_chars=0 sent=0 visible_chars=32880 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[submit]

