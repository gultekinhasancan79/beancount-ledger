# Token budget — mistral-medium-2508, 2026-08-30_B2p_train1_r3

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 3.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 0.0 | 4.0 | 18744.0 | 5697.0 | 24441 | no | no | piv_submitted | 5 incl. write_ledger | B2 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 24,441, max 24,441, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 4, max 4.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:1 (arm B2, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1135 out=153 reasoning_tok=0 cum_in=1135 cum_out=153 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1362 out=56 reasoning_tok=0 cum_in=2497 cum_out=209 msgs=4 reasoning_chars=0 sent=0 visible_chars=1052 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file,read_file]
  turn 03  in=5232 out=5483 reasoning_tok=0 cum_in=7729 cum_out=5692 msgs=7 reasoning_chars=0 sent=0 visible_chars=10692 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[write_ledger]
  turn 04  in=11015 out=5 reasoning_tok=0 cum_in=18744 cum_out=5697 msgs=9 reasoning_chars=0 sent=0 visible_chars=25842 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[submit]

