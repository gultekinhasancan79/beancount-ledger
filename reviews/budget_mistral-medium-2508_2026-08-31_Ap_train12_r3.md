# Token budget — mistral-medium-2508, 2026-08-31_Ap_train12_r3

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 3.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.0 | 4.0 | 18600.0 | 3358.0 | 21958 | no | no | piv_submitted | 7 incl. write_ledger | A | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 21,958, max 21,958, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 4, max 4.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 3, 'list_files': 1, 'grep': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:12 (arm A, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=108 reasoning_tok=0 cum_in=2342 cum_out=114 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file,read_file,read_file,grep]
  turn 03  in=6362 out=3239 reasoning_tok=0 cum_in=8704 cum_out=3353 msgs=9 reasoning_chars=0 sent=0 visible_chars=14429 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[write_ledger]
  turn 04  in=9896 out=5 reasoning_tok=0 cum_in=18600 cum_out=3358 msgs=11 reasoning_chars=0 sent=0 visible_chars=24789 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[submit]

