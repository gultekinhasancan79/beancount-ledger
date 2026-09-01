# Token budget — mistral-medium-2508, 2026-08-30_B1p_train30_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 0.0 | 5.0 | 24775.0 | 4170.0 | 28945 | no | no | piv_submitted | 5 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 28,945, max 28,945, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 5, max 5.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:30 (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=27 reasoning_tok=0 cum_in=2342 cum_out=33 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4996 out=28 reasoning_tok=0 cum_in=7338 cum_out=61 msgs=6 reasoning_chars=0 sent=0 visible_chars=11540 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=6515 out=4104 reasoning_tok=0 cum_in=13853 cum_out=4165 msgs=8 reasoning_chars=0 sent=0 visible_chars=13725 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[write_ledger]
  turn 05  in=10922 out=5 reasoning_tok=0 cum_in=24775 cum_out=4170 msgs=10 reasoning_chars=0 sent=0 visible_chars=26556 req_cap=16000 wire_cap=16000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[submit]

