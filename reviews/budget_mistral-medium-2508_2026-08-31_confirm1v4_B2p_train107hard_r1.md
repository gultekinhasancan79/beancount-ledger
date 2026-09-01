# Token budget — mistral-medium-2508, 2026-08-31_confirm1v4_B2p_train107hard_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:107:hard | 1.0 | 18.0 | 188273.0 | 13019.0 | 201292 | **yes** | no | piv_submitted (truncated) | 17 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 201,292, max 201,292, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 18, max 18.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 8, 'grep': 5, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:107:hard (arm B2, BOUND, submitted True)
  turn 01  in=1261 out=6 reasoning_tok=0 cum_in=1261 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=222 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1341 out=25 reasoning_tok=0 cum_in=2602 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=439 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1673 out=25 reasoning_tok=0 cum_in=4275 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1364 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2770 out=27 reasoning_tok=0 cum_in=7045 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5130 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4340 out=25 reasoning_tok=0 cum_in=11385 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=7381 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4615 out=26 reasoning_tok=0 cum_in=16000 cum_out=134 msgs=12 reasoning_chars=0 sent=0 visible_chars=8268 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=4713 out=26 reasoning_tok=0 cum_in=20713 cum_out=160 msgs=14 reasoning_chars=0 sent=0 visible_chars=8538 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=4806 out=28 reasoning_tok=0 cum_in=25519 cum_out=188 msgs=16 reasoning_chars=0 sent=0 visible_chars=8765 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=5106 out=38 reasoning_tok=0 cum_in=30625 cum_out=226 msgs=18 reasoning_chars=0 sent=0 visible_chars=9252 gen_chars=32+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 10  in=9117 out=8000 reasoning_tok=0 cum_in=39742 cum_out=8226 msgs=20 reasoning_chars=0 sent=0 visible_chars=21404 gen_chars=12669+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 11  in=17159 out=52 reasoning_tok=0 cum_in=56901 cum_out=8278 msgs=22 reasoning_chars=0 sent=0 visible_chars=34243 gen_chars=114+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=17215 out=25 reasoning_tok=0 cum_in=74116 cum_out=8303 msgs=24 reasoning_chars=0 sent=0 visible_chars=34426 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=17244 out=24 reasoning_tok=0 cum_in=91360 cum_out=8327 msgs=26 reasoning_chars=0 sent=0 visible_chars=34485 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=17272 out=199 reasoning_tok=0 cum_in=108632 cum_out=8526 msgs=28 reasoning_chars=0 sent=0 visible_chars=34543 gen_chars=410+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=17475 out=26 reasoning_tok=0 cum_in=126107 cum_out=8552 msgs=30 reasoning_chars=0 sent=0 visible_chars=35021 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=17552 out=4440 reasoning_tok=0 cum_in=143659 cum_out=12992 msgs=32 reasoning_chars=0 sent=0 visible_chars=35222 gen_chars=632+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 17  in=22290 out=22 reasoning_tok=0 cum_in=165949 cum_out=13014 msgs=34 reasoning_chars=0 sent=0 visible_chars=49170 gen_chars=67+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 18  in=22324 out=5 reasoning_tok=0 cum_in=188273 cum_out=13019 msgs=36 reasoning_chars=0 sent=0 visible_chars=49271 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

