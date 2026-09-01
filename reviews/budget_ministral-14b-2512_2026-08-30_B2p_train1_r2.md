# Token budget — ministral-14b-2512, 2026-08-30_B2p_train1_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 0.0 | 11.0 | 58978.0 | 3694.0 | 62672 | **yes** | no | piv_submitted | 11 incl. write_ledger | B2 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 62,672, max 62,672, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 11, max 11.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:1 (arm B2, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1135 out=6 reasoning_tok=0 cum_in=1135 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1215 out=25 reasoning_tok=0 cum_in=2350 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1548 out=25 reasoning_tok=0 cum_in=3898 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1330 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2639 out=27 reasoning_tok=0 cum_in=6537 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5072 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3815 out=29 reasoning_tok=0 cum_in=10352 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6753 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6509 out=25 reasoning_tok=0 cum_in=16861 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=14711 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6785 out=25 reasoning_tok=0 cum_in=23646 cum_out=162 msgs=14 reasoning_chars=0 sent=0 visible_chars=15596 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=6860 out=25 reasoning_tok=0 cum_in=30506 cum_out=187 msgs=16 reasoning_chars=0 sent=0 visible_chars=15765 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=6954 out=3494 reasoning_tok=0 cum_in=37460 cum_out=3681 msgs=18 reasoning_chars=0 sent=0 visible_chars=16029 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 10  in=10749 out=8 reasoning_tok=0 cum_in=48209 cum_out=3689 msgs=20 reasoning_chars=0 sent=0 visible_chars=26909 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 11  in=10769 out=5 reasoning_tok=0 cum_in=58978 cum_out=3694 msgs=22 reasoning_chars=0 sent=0 visible_chars=26943 req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

