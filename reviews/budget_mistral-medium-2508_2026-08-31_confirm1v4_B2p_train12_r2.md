# Token budget — mistral-medium-2508, 2026-08-31_confirm1v4_B2p_train12_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 1.0 | 17.0 | 182531.0 | 17900.0 | 200431 | **yes** | no | piv_submitted | 17 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 200,431, max 200,431, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 17, max 17.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 9, 'run_beancount': 3, 'grep': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:12 (arm B2, BOUND, submitted True)
  turn 01  in=1254 out=6 reasoning_tok=0 cum_in=1254 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1334 out=26 reasoning_tok=0 cum_in=2588 cum_out=32 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1666 out=26 reasoning_tok=0 cum_in=4254 cum_out=58 msgs=6 reasoning_chars=0 sent=0 visible_chars=1332 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2758 out=26 reasoning_tok=0 cum_in=7012 cum_out=84 msgs=8 reasoning_chars=0 sent=0 visible_chars=5072 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3033 out=28 reasoning_tok=0 cum_in=10045 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=5957 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4178 out=29 reasoning_tok=0 cum_in=14223 cum_out=141 msgs=12 reasoning_chars=0 sent=0 visible_chars=7629 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=7063 out=2289 reasoning_tok=0 cum_in=21286 cum_out=2430 msgs=14 reasoning_chars=0 sent=0 visible_chars=16154 gen_chars=3823+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=9448 out=40 reasoning_tok=0 cum_in=30734 cum_out=2470 msgs=16 reasoning_chars=0 sent=0 visible_chars=20217 gen_chars=70+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=9536 out=27 reasoning_tok=0 cum_in=40270 cum_out=2497 msgs=18 reasoning_chars=0 sent=0 visible_chars=20462 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 10  in=9629 out=226 reasoning_tok=0 cum_in=49899 cum_out=2723 msgs=20 reasoning_chars=0 sent=0 visible_chars=20723 gen_chars=550+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=9935 out=3131 reasoning_tok=0 cum_in=59834 cum_out=5854 msgs=22 reasoning_chars=0 sent=0 visible_chars=21487 gen_chars=526+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 12  in=13361 out=25 reasoning_tok=0 cum_in=73195 cum_out=5879 msgs=24 reasoning_chars=0 sent=0 visible_chars=31389 gen_chars=89+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 13  in=13398 out=4986 reasoning_tok=0 cum_in=86593 cum_out=10865 msgs=26 reasoning_chars=0 sent=0 visible_chars=31512 gen_chars=8624+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 14  in=18647 out=4805 reasoning_tok=0 cum_in=105240 cum_out=15670 msgs=28 reasoning_chars=0 sent=0 visible_chars=40603 gen_chars=8345+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 15  in=23464 out=1980 reasoning_tok=0 cum_in=128704 cum_out=17650 msgs=30 reasoning_chars=0 sent=0 visible_chars=48982 gen_chars=4111+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 16  in=25456 out=65 reasoning_tok=0 cum_in=154160 cum_out=17715 msgs=32 reasoning_chars=0 sent=0 visible_chars=53127 gen_chars=168+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 17  in=28371 out=185 reasoning_tok=0 cum_in=182531 cum_out=17900 msgs=34 reasoning_chars=0 sent=0 visible_chars=61814 gen_chars=492+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

