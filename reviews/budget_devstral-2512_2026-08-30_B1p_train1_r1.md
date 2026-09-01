# Token budget — devstral-2512, 2026-08-30_B1p_train1_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 0.0 | 9.0 | 47718.0 | 4772.0 | 52490 | **yes** | no | piv_submitted | 9 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 52,490, max 52,490, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 9, max 9.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 4, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:1 (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1135 out=6 reasoning_tok=0 cum_in=1135 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 req_cap=16000 wire_cap=16000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1215 out=26 reasoning_tok=0 cum_in=2350 cum_out=32 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 req_cap=16000 wire_cap=16000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1549 out=26 reasoning_tok=0 cum_in=3899 cum_out=58 msgs=6 reasoning_chars=0 sent=0 visible_chars=1331 req_cap=16000 wire_cap=16000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2641 out=29 reasoning_tok=0 cum_in=6540 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=5074 req_cap=16000 wire_cap=16000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=5335 out=28 reasoning_tok=0 cum_in=11875 cum_out=115 msgs=10 reasoning_chars=0 sent=0 visible_chars=13032 req_cap=16000 wire_cap=16000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6512 out=54 reasoning_tok=0 cum_in=18387 cum_out=169 msgs=12 reasoning_chars=0 sent=0 visible_chars=14714 req_cap=16000 wire_cap=16000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 07  in=6578 out=4397 reasoning_tok=0 cum_in=24965 cum_out=4566 msgs=14 reasoning_chars=0 sent=0 visible_chars=15001 req_cap=16000 wire_cap=16000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 08  in=11280 out=181 reasoning_tok=0 cum_in=36245 cum_out=4747 msgs=16 reasoning_chars=0 sent=0 visible_chars=26793 req_cap=16000 wire_cap=16000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 09  in=11473 out=25 reasoning_tok=0 cum_in=47718 cum_out=4772 msgs=18 reasoning_chars=0 sent=0 visible_chars=27322 req_cap=16000 wire_cap=16000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[submit]

