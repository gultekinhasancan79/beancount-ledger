# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B1p_train3hard_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:3:hard | 0.0 | 16.0 | 123734.0 | 5490.0 | 129224 | **yes** | no | piv_submitted | 15 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 129,224, max 129,224, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 16, max 16.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 8, 'read_file': 3, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:3:hard (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1242 out=6 reasoning_tok=0 cum_in=1242 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1322 out=29 reasoning_tok=0 cum_in=2564 cum_out=35 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4978 out=27 reasoning_tok=0 cum_in=7542 cum_out=62 msgs=6 reasoning_chars=0 sent=0 visible_chars=11348 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=6511 out=25 reasoning_tok=0 cum_in=14053 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=13540 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=7608 out=21 reasoning_tok=0 cum_in=21661 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=17303 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 06  in=7650 out=21 reasoning_tok=0 cum_in=29311 cum_out=129 msgs=12 reasoning_chars=0 sent=0 visible_chars=17422 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 07  in=7692 out=22 reasoning_tok=0 cum_in=37003 cum_out=151 msgs=14 reasoning_chars=0 sent=0 visible_chars=17554 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=7735 out=22 reasoning_tok=0 cum_in=44738 cum_out=173 msgs=16 reasoning_chars=0 sent=0 visible_chars=17688 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=7761 out=22 reasoning_tok=0 cum_in=52499 cum_out=195 msgs=18 reasoning_chars=0 sent=0 visible_chars=17757 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=7805 out=22 reasoning_tok=0 cum_in=60304 cum_out=217 msgs=20 reasoning_chars=0 sent=0 visible_chars=17873 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=7848 out=22 reasoning_tok=0 cum_in=68152 cum_out=239 msgs=22 reasoning_chars=0 sent=0 visible_chars=17993 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=7892 out=27 reasoning_tok=0 cum_in=76044 cum_out=266 msgs=24 reasoning_chars=0 sent=0 visible_chars=18099 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=7923 out=4906 reasoning_tok=0 cum_in=83967 cum_out=5172 msgs=26 reasoning_chars=0 sent=0 visible_chars=18162 gen_chars=2430+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 14  in=13130 out=8 reasoning_tok=0 cum_in=97097 cum_out=5180 msgs=28 reasoning_chars=0 sent=0 visible_chars=33472 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 15  in=13150 out=305 reasoning_tok=0 cum_in=110247 cum_out=5485 msgs=30 reasoning_chars=0 sent=0 visible_chars=33506 gen_chars=895+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=stop trunc=False tools=[-]
  turn 16  in=13487 out=5 reasoning_tok=0 cum_in=123734 cum_out=5490 msgs=32 reasoning_chars=0 sent=0 visible_chars=34526 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

