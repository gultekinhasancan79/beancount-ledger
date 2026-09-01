# Token budget — ministral-14b-2512, 2026-08-31_confirm1v4_B1p_train3hard_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:3:hard | 0.215 | 9.0 | 44402.0 | 5000.0 | 49402 | no | no | piv_submitted | 9 incl. write_ledger | B1 | BOUND | True | VALID |

- total tokens: median 49,402, max 49,402, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 9, max 9.0
- reward: mean 0.215 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 5, 'list_files': 1, 'run_beancount': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:3:hard (arm B1, BOUND, submitted True)
  turn 01  in=1242 out=6 reasoning_tok=0 cum_in=1242 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1322 out=25 reasoning_tok=0 cum_in=2564 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1655 out=25 reasoning_tok=0 cum_in=4219 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1338 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2752 out=25 reasoning_tok=0 cum_in=6971 cum_out=81 msgs=8 reasoning_chars=0 sent=0 visible_chars=5101 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3028 out=27 reasoning_tok=0 cum_in=9999 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=5990 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4561 out=29 reasoning_tok=0 cum_in=14560 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=8182 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=8217 out=8 reasoning_tok=0 cum_in=22777 cum_out=145 msgs=14 reasoning_chars=0 sent=0 visible_chars=19121 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=8237 out=4850 reasoning_tok=0 cum_in=31014 cum_out=4995 msgs=16 reasoning_chars=0 sent=0 visible_chars=19155 gen_chars=3499+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=13388 out=5 reasoning_tok=0 cum_in=44402 cum_out=5000 msgs=18 reasoning_chars=0 sent=0 visible_chars=34547 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

