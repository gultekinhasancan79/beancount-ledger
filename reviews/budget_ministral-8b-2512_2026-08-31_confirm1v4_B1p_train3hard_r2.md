# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B1p_train3hard_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:3:hard | 0.0 | 14.0 | 108156.0 | 5252.0 | 113408 | **yes** | no | piv_submitted | 13 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 113,408, max 113,408, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 14, max 14.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 5, 'read_file': 4, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:3:hard (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1242 out=6 reasoning_tok=0 cum_in=1242 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1322 out=29 reasoning_tok=0 cum_in=2564 cum_out=35 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4978 out=27 reasoning_tok=0 cum_in=7542 cum_out=62 msgs=6 reasoning_chars=0 sent=0 visible_chars=11348 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=6511 out=25 reasoning_tok=0 cum_in=14053 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=13540 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=7608 out=19 reasoning_tok=0 cum_in=21661 cum_out=106 msgs=10 reasoning_chars=0 sent=0 visible_chars=17303 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 06  in=7641 out=25 reasoning_tok=0 cum_in=29302 cum_out=131 msgs=12 reasoning_chars=0 sent=0 visible_chars=17399 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=7732 out=44 reasoning_tok=0 cum_in=37034 cum_out=175 msgs=14 reasoning_chars=0 sent=0 visible_chars=17661 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=7780 out=22 reasoning_tok=0 cum_in=44814 cum_out=197 msgs=16 reasoning_chars=0 sent=0 visible_chars=17759 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=7860 out=25 reasoning_tok=0 cum_in=52674 cum_out=222 msgs=18 reasoning_chars=0 sent=0 visible_chars=17896 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=7924 out=25 reasoning_tok=0 cum_in=60598 cum_out=247 msgs=20 reasoning_chars=0 sent=0 visible_chars=18028 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=7989 out=4825 reasoning_tok=0 cum_in=68587 cum_out=5072 msgs=22 reasoning_chars=0 sent=0 visible_chars=18161 gen_chars=3239+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 12  in=13110 out=8 reasoning_tok=0 cum_in=81697 cum_out=5080 msgs=24 reasoning_chars=0 sent=0 visible_chars=33276 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 13  in=13130 out=167 reasoning_tok=0 cum_in=94827 cum_out=5247 msgs=26 reasoning_chars=0 sent=0 visible_chars=33310 gen_chars=597+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=stop trunc=False tools=[-]
  turn 14  in=13329 out=5 reasoning_tok=0 cum_in=108156 cum_out=5252 msgs=28 reasoning_chars=0 sent=0 visible_chars=34032 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

