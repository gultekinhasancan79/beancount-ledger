# Token budget — devstral-2512, 2026-08-31_Ap_train12_r3

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 3.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.275 | 10.0 | 40047.0 | 4276.0 | 44323 | no | no | piv_submitted | 10 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 44,323, max 44,323, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 10, max 10.0
- reward: mean 0.275 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:12 (arm A, BOUND, submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=26 reasoning_tok=0 cum_in=2342 cum_out=32 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1543 out=26 reasoning_tok=0 cum_in=3885 cum_out=58 msgs=6 reasoning_chars=0 sent=0 visible_chars=1332 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2635 out=26 reasoning_tok=0 cum_in=6520 cum_out=84 msgs=8 reasoning_chars=0 sent=0 visible_chars=5072 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=2910 out=27 reasoning_tok=0 cum_in=9430 cum_out=111 msgs=10 reasoning_chars=0 sent=0 visible_chars=5957 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=2985 out=27 reasoning_tok=0 cum_in=12415 cum_out=138 msgs=12 reasoning_chars=0 sent=0 visible_chars=6132 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=3078 out=29 reasoning_tok=0 cum_in=15493 cum_out=167 msgs=14 reasoning_chars=0 sent=0 visible_chars=6393 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=5963 out=28 reasoning_tok=0 cum_in=21456 cum_out=195 msgs=16 reasoning_chars=0 sent=0 visible_chars=14918 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=7108 out=4076 reasoning_tok=0 cum_in=28564 cum_out=4271 msgs=18 reasoning_chars=0 sent=0 visible_chars=16590 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 10  in=11483 out=5 reasoning_tok=0 cum_in=40047 cum_out=4276 msgs=20 reasoning_chars=0 sent=0 visible_chars=28476 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[submit]

