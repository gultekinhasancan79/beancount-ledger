# Token budget — devstral-2512, 2026-08-31_confirm1v4_B1p_train1_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 1.0 | 14.0 | 167808.0 | 20225.0 | 188033 | **yes** | no | piv_submitted | 14 incl. write_ledger | B1 | BOUND | True | VALID |

- total tokens: median 188,033, max 188,033, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 14, max 14.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'run_beancount': 3, 'list_files': 1, 'grep': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:1 (arm B1, BOUND, submitted True)
  turn 01  in=1258 out=6 reasoning_tok=0 cum_in=1258 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1338 out=25 reasoning_tok=0 cum_in=2596 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1671 out=25 reasoning_tok=0 cum_in=4267 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1330 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2762 out=27 reasoning_tok=0 cum_in=7029 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5072 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3938 out=29 reasoning_tok=0 cum_in=10967 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6753 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6632 out=25 reasoning_tok=0 cum_in=17599 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=14711 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6908 out=26 reasoning_tok=0 cum_in=24507 cum_out=163 msgs=14 reasoning_chars=0 sent=0 visible_chars=15596 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=7003 out=9901 reasoning_tok=0 cum_in=31510 cum_out=10064 msgs=16 reasoning_chars=0 sent=0 visible_chars=15861 gen_chars=18174+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 09  in=16916 out=24 reasoning_tok=0 cum_in=48426 cum_out=10088 msgs=18 reasoning_chars=0 sent=0 visible_chars=34069 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=17577 out=3807 reasoning_tok=0 cum_in=66003 cum_out=13895 msgs=20 reasoning_chars=0 sent=0 visible_chars=36016 gen_chars=2483+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 11  in=21687 out=8 reasoning_tok=0 cum_in=87690 cum_out=13903 msgs=22 reasoning_chars=0 sent=0 visible_chars=47297 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 12  in=21707 out=6124 reasoning_tok=0 cum_in=109397 cum_out=20027 msgs=24 reasoning_chars=0 sent=0 visible_chars=47331 gen_chars=11240+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 13  in=27843 out=57 reasoning_tok=0 cum_in=137240 cum_out=20084 msgs=26 reasoning_chars=0 sent=0 visible_chars=58605 gen_chars=128+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 14  in=30568 out=141 reasoning_tok=0 cum_in=167808 cum_out=20225 msgs=28 reasoning_chars=0 sent=0 visible_chars=66700 gen_chars=465+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

