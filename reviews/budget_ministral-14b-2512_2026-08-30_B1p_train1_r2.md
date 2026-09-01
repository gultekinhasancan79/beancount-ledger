# Token budget — ministral-14b-2512, 2026-08-30_B1p_train1_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 0.383333 | 15.0 | 91052.0 | 3731.0 | 94783 | **yes** | no | piv_submitted | 15 incl. write_ledger | B1 | BOUND | True | VALID |

- total tokens: median 94,783, max 94,783, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 15, max 15.0
- reward: mean 0.383 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 6, 'read_file': 5, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:1 (arm B1, BOUND, submitted True)
  turn 01  in=1135 out=6 reasoning_tok=0 cum_in=1135 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1215 out=25 reasoning_tok=0 cum_in=2350 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1548 out=25 reasoning_tok=0 cum_in=3898 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1330 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2639 out=27 reasoning_tok=0 cum_in=6537 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5072 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3815 out=29 reasoning_tok=0 cum_in=10352 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6753 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6509 out=25 reasoning_tok=0 cum_in=16861 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=14711 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6785 out=25 reasoning_tok=0 cum_in=23646 cum_out=162 msgs=14 reasoning_chars=0 sent=0 visible_chars=15596 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=6965 out=25 reasoning_tok=0 cum_in=30611 cum_out=187 msgs=16 reasoning_chars=0 sent=0 visible_chars=15971 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=7199 out=25 reasoning_tok=0 cum_in=37810 cum_out=212 msgs=18 reasoning_chars=0 sent=0 visible_chars=16457 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=7390 out=33 reasoning_tok=0 cum_in=45200 cum_out=245 msgs=20 reasoning_chars=0 sent=0 visible_chars=16851 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=7529 out=33 reasoning_tok=0 cum_in=52729 cum_out=278 msgs=22 reasoning_chars=0 sent=0 visible_chars=17087 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=7615 out=35 reasoning_tok=0 cum_in=60344 cum_out=313 msgs=24 reasoning_chars=0 sent=0 visible_chars=17241 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=7760 out=3405 reasoning_tok=0 cum_in=68104 cum_out=3718 msgs=26 reasoning_chars=0 sent=0 visible_chars=17489 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 14  in=11464 out=8 reasoning_tok=0 cum_in=79568 cum_out=3726 msgs=28 reasoning_chars=0 sent=0 visible_chars=28312 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 15  in=11484 out=5 reasoning_tok=0 cum_in=91052 cum_out=3731 msgs=30 reasoning_chars=0 sent=0 visible_chars=28346 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

