# Token budget — mistral-medium-2508, 2026-08-31_B2p_train12_r3

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 3.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.0 | 5.0 | 21418.0 | 3773.0 | 25191 | no | no | piv_submitted | 5 incl. write_ledger | B2 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 25,191, max 25,191, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 5, max 5.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:12 (arm B2, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1131 out=143 reasoning_tok=0 cum_in=1131 cum_out=143 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1348 out=68 reasoning_tok=0 cum_in=2479 cum_out=211 msgs=4 reasoning_chars=0 sent=0 visible_chars=973 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4272 out=58 reasoning_tok=0 cum_in=6751 cum_out=269 msgs=6 reasoning_chars=0 sent=0 visible_chars=9666 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=5447 out=3475 reasoning_tok=0 cum_in=12198 cum_out=3744 msgs=8 reasoning_chars=0 sent=0 visible_chars=11465 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[write_ledger]
  turn 05  in=9220 out=29 reasoning_tok=0 cum_in=21418 cum_out=3773 msgs=10 reasoning_chars=0 sent=0 visible_chars=22364 req_cap=8000 wire_cap=8000 provider_model=mistral-medium-2508 finish=tool_calls trunc=False tools=[submit]

