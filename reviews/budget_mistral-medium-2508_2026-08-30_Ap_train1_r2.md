# Token budget — mistral-medium-2508, 2026-08-30_Ap_train1_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 1.0 | 6.0 | 31861.0 | 5701.0 | 37562 | no | no | piv_submitted | 7 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 37,562, max 37,562, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 6, max 6.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 3, 'list_files': 1, 'grep': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:1 (arm A, BOUND, submitted True)
  turn 01  in=1135 out=6 reasoning_tok=0 cum_in=1135 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1215 out=52 reasoning_tok=0 cum_in=2350 cum_out=58 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file,read_file]
  turn 03  in=4998 out=28 reasoning_tok=0 cum_in=7348 cum_out=86 msgs=7 reasoning_chars=0 sent=0 visible_chars=12108 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=6175 out=69 reasoning_tok=0 cum_in=13523 cum_out=155 msgs=9 reasoning_chars=0 sent=0 visible_chars=13790 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[grep]
  turn 05  in=6248 out=5541 reasoning_tok=0 cum_in=19771 cum_out=5696 msgs=11 reasoning_chars=0 sent=0 visible_chars=14034 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[write_ledger]
  turn 06  in=12090 out=5 reasoning_tok=0 cum_in=31861 cum_out=5701 msgs=13 reasoning_chars=0 sent=0 visible_chars=31173 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[submit]

