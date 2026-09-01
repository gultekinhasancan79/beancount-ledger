# Token budget — devstral-2512, 2026-08-30_B2p_train1_r3

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 3.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 1.0 | 10.0 | 38680.0 | 3332.0 | 42012 | no | no | piv_submitted | 10 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 42,012, max 42,012, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 10, max 10.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:1 (arm B2, BOUND, submitted True)
  turn 01  in=1135 out=6 reasoning_tok=0 cum_in=1135 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1215 out=26 reasoning_tok=0 cum_in=2350 cum_out=32 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1549 out=26 reasoning_tok=0 cum_in=3899 cum_out=58 msgs=6 reasoning_chars=0 sent=0 visible_chars=1331 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2641 out=26 reasoning_tok=0 cum_in=6540 cum_out=84 msgs=8 reasoning_chars=0 sent=0 visible_chars=5074 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=2918 out=27 reasoning_tok=0 cum_in=9458 cum_out=111 msgs=10 reasoning_chars=0 sent=0 visible_chars=5960 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=2995 out=27 reasoning_tok=0 cum_in=12453 cum_out=138 msgs=12 reasoning_chars=0 sent=0 visible_chars=6131 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=3091 out=29 reasoning_tok=0 cum_in=15544 cum_out=167 msgs=14 reasoning_chars=0 sent=0 visible_chars=6397 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=5785 out=28 reasoning_tok=0 cum_in=21329 cum_out=195 msgs=16 reasoning_chars=0 sent=0 visible_chars=14355 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=6962 out=3132 reasoning_tok=0 cum_in=28291 cum_out=3327 msgs=18 reasoning_chars=0 sent=0 visible_chars=16037 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 10  in=10389 out=5 reasoning_tok=0 cum_in=38680 cum_out=3332 msgs=20 reasoning_chars=0 sent=0 visible_chars=25957 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[submit]

