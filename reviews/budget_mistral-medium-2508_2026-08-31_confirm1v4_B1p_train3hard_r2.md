# Token budget — mistral-medium-2508, 2026-08-31_confirm1v4_B1p_train3hard_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:3:hard | 0.645 | 12.0 | 110334.0 | 18549.0 | 128883 | **yes** | no | piv_submitted | 12 incl. write_ledger | B1 | BOUND | True | VALID |

- total tokens: median 128,883, max 128,883, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 12, max 12.0
- reward: mean 0.645 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 8, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:3:hard (arm B1, BOUND, submitted True)
  turn 01  in=1254 out=6 reasoning_tok=0 cum_in=1254 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1334 out=25 reasoning_tok=0 cum_in=2588 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1667 out=25 reasoning_tok=0 cum_in=4255 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1338 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2764 out=27 reasoning_tok=0 cum_in=7019 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5101 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4297 out=25 reasoning_tok=0 cum_in=11316 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=7293 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4573 out=26 reasoning_tok=0 cum_in=15889 cum_out=134 msgs=12 reasoning_chars=0 sent=0 visible_chars=8182 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=4665 out=26 reasoning_tok=0 cum_in=20554 cum_out=160 msgs=14 reasoning_chars=0 sent=0 visible_chars=8445 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=4759 out=29 reasoning_tok=0 cum_in=25313 cum_out=189 msgs=16 reasoning_chars=0 sent=0 visible_chars=8668 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=8415 out=14272 reasoning_tok=0 cum_in=33728 cum_out=14461 msgs=18 reasoning_chars=0 sent=0 visible_chars=19607 gen_chars=33820+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 10  in=22731 out=3881 reasoning_tok=0 cum_in=56459 cum_out=18342 msgs=20 reasoning_chars=0 sent=0 visible_chars=53643 gen_chars=490+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 11  in=26918 out=27 reasoning_tok=0 cum_in=83377 cum_out=18369 msgs=22 reasoning_chars=0 sent=0 visible_chars=66024 gen_chars=92+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 12  in=26957 out=180 reasoning_tok=0 cum_in=110334 cum_out=18549 msgs=24 reasoning_chars=0 sent=0 visible_chars=66150 gen_chars=632+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

