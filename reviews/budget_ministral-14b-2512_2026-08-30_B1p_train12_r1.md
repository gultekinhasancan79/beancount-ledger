# Token budget — ministral-14b-2512, 2026-08-30_B1p_train12_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 180s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest d67f5324e599d78c4ce68f70d89c2c1bf39bdc6ea230330df72155623e4e0c33.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.0 | 18.0 | 116901.0 | 4236.0 | 121137 | **yes** | no | piv_submitted | 18 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 121,137, max 121,137, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 18, max 18.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 9, 'read_file': 5, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}

## Per-turn detail

### train:12 (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1131 out=6 reasoning_tok=0 cum_in=1131 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1211 out=25 reasoning_tok=0 cum_in=2342 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1542 out=25 reasoning_tok=0 cum_in=3884 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1331 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2633 out=27 reasoning_tok=0 cum_in=6517 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5070 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3777 out=29 reasoning_tok=0 cum_in=10294 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6741 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6662 out=25 reasoning_tok=0 cum_in=16956 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=15266 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6936 out=25 reasoning_tok=0 cum_in=23892 cum_out=162 msgs=14 reasoning_chars=0 sent=0 visible_chars=16150 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=7123 out=25 reasoning_tok=0 cum_in=31015 cum_out=187 msgs=16 reasoning_chars=0 sent=0 visible_chars=16534 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=7310 out=25 reasoning_tok=0 cum_in=38325 cum_out=212 msgs=18 reasoning_chars=0 sent=0 visible_chars=16918 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=7431 out=25 reasoning_tok=0 cum_in=45756 cum_out=237 msgs=20 reasoning_chars=0 sent=0 visible_chars=17161 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=7579 out=25 reasoning_tok=0 cum_in=53335 cum_out=262 msgs=22 reasoning_chars=0 sent=0 visible_chars=17470 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=7686 out=25 reasoning_tok=0 cum_in=61021 cum_out=287 msgs=24 reasoning_chars=0 sent=0 visible_chars=17686 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=7760 out=25 reasoning_tok=0 cum_in=68781 cum_out=312 msgs=26 reasoning_chars=0 sent=0 visible_chars=17835 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=7827 out=25 reasoning_tok=0 cum_in=76608 cum_out=337 msgs=28 reasoning_chars=0 sent=0 visible_chars=17982 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=7901 out=25 reasoning_tok=0 cum_in=84509 cum_out=362 msgs=30 reasoning_chars=0 sent=0 visible_chars=18135 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=8022 out=3861 reasoning_tok=0 cum_in=92531 cum_out=4223 msgs=32 reasoning_chars=0 sent=0 visible_chars=18381 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 17  in=12175 out=8 reasoning_tok=0 cum_in=104706 cum_out=4231 msgs=34 reasoning_chars=0 sent=0 visible_chars=30341 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 18  in=12195 out=5 reasoning_tok=0 cum_in=116901 cum_out=4236 msgs=36 reasoning_chars=0 sent=0 visible_chars=30375 req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

