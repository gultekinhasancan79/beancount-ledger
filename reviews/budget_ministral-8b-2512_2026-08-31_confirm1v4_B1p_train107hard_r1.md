# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B1p_train107hard_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:107:hard | 0.0 | 7.0 | 52108.0 | 5567.0 | 57675 | **yes** | no | piv_submitted | 7 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 57,675, max 57,675, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 7, max 7.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 2, 'list_files': 1, 'grep': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:107:hard (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1249 out=31 reasoning_tok=0 cum_in=1249 cum_out=31 msgs=2 reasoning_chars=0 sent=0 visible_chars=222 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 02  in=5253 out=43 reasoning_tok=0 cum_in=6502 cum_out=74 msgs=4 reasoning_chars=0 sent=0 visible_chars=12344 gen_chars=186+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 03  in=5370 out=27 reasoning_tok=0 cum_in=11872 cum_out=101 msgs=6 reasoning_chars=0 sent=0 visible_chars=12747 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=6940 out=786 reasoning_tok=0 cum_in=18812 cum_out=887 msgs=8 reasoning_chars=0 sent=0 visible_chars=14998 gen_chars=2378+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 05  in=7904 out=4483 reasoning_tok=0 cum_in=26716 cum_out=5370 msgs=10 reasoning_chars=0 sent=0 visible_chars=17908 gen_chars=1468+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 06  in=12686 out=8 reasoning_tok=0 cum_in=39402 cum_out=5378 msgs=12 reasoning_chars=0 sent=0 visible_chars=32108 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 07  in=12706 out=189 reasoning_tok=0 cum_in=52108 cum_out=5567 msgs=14 reasoning_chars=0 sent=0 visible_chars=32142 gen_chars=627+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

