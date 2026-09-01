# Token budget — devstral-2512, 2026-08-31_confirm1v4_B2p_train1_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 1.0 | 14.0 | 104578.0 | 11182.0 | 115760 | **yes** | no | piv_submitted (truncated) | 13 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 115,760, max 115,760, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 14, max 14.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 9, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:1 (arm B2, BOUND, submitted True)
  turn 01  in=1258 out=6 reasoning_tok=0 cum_in=1258 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1338 out=25 reasoning_tok=0 cum_in=2596 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1671 out=25 reasoning_tok=0 cum_in=4267 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1330 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2762 out=27 reasoning_tok=0 cum_in=7029 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5072 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3938 out=25 reasoning_tok=0 cum_in=10967 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=6753 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4214 out=26 reasoning_tok=0 cum_in=15181 cum_out=134 msgs=12 reasoning_chars=0 sent=0 visible_chars=7638 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=4290 out=26 reasoning_tok=0 cum_in=19471 cum_out=160 msgs=14 reasoning_chars=0 sent=0 visible_chars=7808 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=4385 out=28 reasoning_tok=0 cum_in=23856 cum_out=188 msgs=16 reasoning_chars=0 sent=0 visible_chars=8073 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=4735 out=29 reasoning_tok=0 cum_in=28591 cum_out=217 msgs=18 reasoning_chars=0 sent=0 visible_chars=8615 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 10  in=7429 out=8000 reasoning_tok=0 cum_in=36020 cum_out=8217 msgs=20 reasoning_chars=0 sent=0 visible_chars=16573 gen_chars=14886+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 11  in=15471 out=29 reasoning_tok=0 cum_in=51491 cum_out=8246 msgs=22 reasoning_chars=0 sent=0 visible_chars=31629 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 12  in=15545 out=2923 reasoning_tok=0 cum_in=67036 cum_out=11169 msgs=24 reasoning_chars=0 sent=0 visible_chars=31845 gen_chars=407+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 13  in=18761 out=8 reasoning_tok=0 cum_in=85797 cum_out=11177 msgs=26 reasoning_chars=0 sent=0 visible_chars=41050 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 14  in=18781 out=5 reasoning_tok=0 cum_in=104578 cum_out=11182 msgs=28 reasoning_chars=0 sent=0 visible_chars=41084 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

