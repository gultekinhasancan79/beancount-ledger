# Token budget — devstral-2512, 2026-08-30_B2p_train30_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 0.0 | 15.0 | 88301.0 | 4751.0 | 93052 | **yes** | no | piv_submitted | 15 incl. write_ledger | B2 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 93,052, max 93,052, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 15, max 15.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'grep': 5, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:30 (arm B2, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=26 reasoning_tok=0 cum_in=2342 cum_out=32 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1542 out=26 reasoning_tok=0 cum_in=3884 cum_out=58 msgs=6 reasoning_chars=0 sent=0 visible_chars=1319 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2643 out=26 reasoning_tok=0 cum_in=6527 cum_out=84 msgs=8 reasoning_chars=0 sent=0 visible_chars=5077 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=2917 out=27 reasoning_tok=0 cum_in=9444 cum_out=111 msgs=10 reasoning_chars=0 sent=0 visible_chars=5953 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=3006 out=27 reasoning_tok=0 cum_in=12450 cum_out=138 msgs=12 reasoning_chars=0 sent=0 visible_chars=6163 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=3103 out=29 reasoning_tok=0 cum_in=15553 cum_out=167 msgs=14 reasoning_chars=0 sent=0 visible_chars=6430 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=6890 out=28 reasoning_tok=0 cum_in=22443 cum_out=195 msgs=16 reasoning_chars=0 sent=0 visible_chars=17566 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=8409 out=81 reasoning_tok=0 cum_in=30852 cum_out=276 msgs=18 reasoning_chars=0 sent=0 visible_chars=19751 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=8550 out=63 reasoning_tok=0 cum_in=39402 cum_out=339 msgs=20 reasoning_chars=0 sent=0 visible_chars=20098 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=8678 out=59 reasoning_tok=0 cum_in=48080 cum_out=398 msgs=22 reasoning_chars=0 sent=0 visible_chars=20316 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=8797 out=43 reasoning_tok=0 cum_in=56877 cum_out=441 msgs=24 reasoning_chars=0 sent=0 visible_chars=20533 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=8893 out=45 reasoning_tok=0 cum_in=65770 cum_out=486 msgs=26 reasoning_chars=0 sent=0 visible_chars=20701 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=8985 out=4260 reasoning_tok=0 cum_in=74755 cum_out=4746 msgs=28 reasoning_chars=0 sent=0 visible_chars=20869 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 15  in=13546 out=5 reasoning_tok=0 cum_in=88301 cum_out=4751 msgs=30 reasoning_chars=0 sent=0 visible_chars=34122 req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[submit]

