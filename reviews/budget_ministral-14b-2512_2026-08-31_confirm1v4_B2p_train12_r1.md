# Token budget — ministral-14b-2512, 2026-08-31_confirm1v4_B2p_train12_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.55 | 10.0 | 52643.0 | 5194.0 | 57837 | **yes** | no | piv_submitted | 10 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 57,837, max 57,837, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 10, max 10.0
- reward: mean 0.550 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 5, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:12 (arm B2, BOUND, submitted True)
  turn 01  in=1242 out=6 reasoning_tok=0 cum_in=1242 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1322 out=25 reasoning_tok=0 cum_in=2564 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1653 out=25 reasoning_tok=0 cum_in=4217 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1331 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2744 out=25 reasoning_tok=0 cum_in=6961 cum_out=81 msgs=8 reasoning_chars=0 sent=0 visible_chars=5070 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3018 out=27 reasoning_tok=0 cum_in=9979 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=5954 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4162 out=29 reasoning_tok=0 cum_in=14141 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=7625 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=7047 out=8 reasoning_tok=0 cum_in=21188 cum_out=145 msgs=14 reasoning_chars=0 sent=0 visible_chars=16150 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=7067 out=4823 reasoning_tok=0 cum_in=28255 cum_out=4968 msgs=16 reasoning_chars=0 sent=0 visible_chars=16184 gen_chars=4687+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=12184 out=8 reasoning_tok=0 cum_in=40439 cum_out=4976 msgs=18 reasoning_chars=0 sent=0 visible_chars=30055 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=12204 out=218 reasoning_tok=0 cum_in=52643 cum_out=5194 msgs=20 reasoning_chars=0 sent=0 visible_chars=30089 gen_chars=758+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

