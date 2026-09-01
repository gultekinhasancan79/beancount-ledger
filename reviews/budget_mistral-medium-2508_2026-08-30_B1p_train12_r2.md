# Token budget — mistral-medium-2508, 2026-08-30_B1p_train12_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.55 | 4.0 | 18517.0 | 3308.0 | 21825 | no | no | piv_submitted | 6 incl. write_ledger | B1 | BOUND | True | VALID |

- total tokens: median 21,825, max 21,825, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 4, max 4.0
- reward: mean 0.550 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 3, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:12 (arm B1, BOUND, submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=79 reasoning_tok=0 cum_in=2342 cum_out=85 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file,read_file,read_file]
  turn 03  in=6329 out=3218 reasoning_tok=0 cum_in=8671 cum_out=3303 msgs=8 reasoning_chars=0 sent=0 visible_chars=14343 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[write_ledger]
  turn 04  in=9846 out=5 reasoning_tok=0 cum_in=18517 cum_out=3308 msgs=10 reasoning_chars=0 sent=0 visible_chars=24554 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[submit]

