# Token budget — ministral-14b-2512, 2026-08-31_confirm1v4_Ap_train1_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 0.383333 | 10.0 | 53003.0 | 4189.0 | 57192 | **yes** | no | piv_submitted | 10 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 57,192, max 57,192, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 10, max 10.0
- reward: mean 0.383 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 5, 'list_files': 1, 'run_beancount': 1, 'write_ledger': 1, 'grep': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:1 (arm A, BOUND, submitted True)
  turn 01  in=1246 out=6 reasoning_tok=0 cum_in=1246 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1326 out=25 reasoning_tok=0 cum_in=2572 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1659 out=25 reasoning_tok=0 cum_in=4231 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1330 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2750 out=27 reasoning_tok=0 cum_in=6981 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5072 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3926 out=29 reasoning_tok=0 cum_in=10907 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6753 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6620 out=25 reasoning_tok=0 cum_in=17527 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=14711 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6896 out=8 reasoning_tok=0 cum_in=24423 cum_out=145 msgs=14 reasoning_chars=0 sent=0 visible_chars=15596 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=6916 out=3399 reasoning_tok=0 cum_in=31339 cum_out=3544 msgs=16 reasoning_chars=0 sent=0 visible_chars=15630 gen_chars=2134+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=10614 out=432 reasoning_tok=0 cum_in=41953 cum_out=3976 msgs=18 reasoning_chars=0 sent=0 visible_chars=26354 gen_chars=1326+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=11050 out=213 reasoning_tok=0 cum_in=53003 cum_out=4189 msgs=20 reasoning_chars=0 sent=0 visible_chars=27740 gen_chars=961+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

