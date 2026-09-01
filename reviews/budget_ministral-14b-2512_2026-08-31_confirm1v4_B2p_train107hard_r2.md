# Token budget — ministral-14b-2512, 2026-08-31_confirm1v4_B2p_train107hard_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:107:hard | 0.55 | 11.0 | 53195.0 | 5500.0 | 58695 | **yes** | no | piv_submitted | 11 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 58,695, max 58,695, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 11, max 11.0
- reward: mean 0.550 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'list_files': 1, 'run_beancount': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:107:hard (arm B2, BOUND, submitted True)
  turn 01  in=1249 out=6 reasoning_tok=0 cum_in=1249 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=222 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1329 out=25 reasoning_tok=0 cum_in=2578 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=439 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1661 out=25 reasoning_tok=0 cum_in=4239 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1364 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2758 out=25 reasoning_tok=0 cum_in=6997 cum_out=81 msgs=8 reasoning_chars=0 sent=0 visible_chars=5130 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3033 out=25 reasoning_tok=0 cum_in=10030 cum_out=106 msgs=10 reasoning_chars=0 sent=0 visible_chars=6017 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=3130 out=25 reasoning_tok=0 cum_in=13160 cum_out=131 msgs=12 reasoning_chars=0 sent=0 visible_chars=6286 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=3222 out=27 reasoning_tok=0 cum_in=16382 cum_out=158 msgs=14 reasoning_chars=0 sent=0 visible_chars=6512 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=4792 out=29 reasoning_tok=0 cum_in=21174 cum_out=187 msgs=16 reasoning_chars=0 sent=0 visible_chars=8763 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=8794 out=8 reasoning_tok=0 cum_in=29968 cum_out=195 msgs=18 reasoning_chars=0 sent=0 visible_chars=20883 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=8814 out=5300 reasoning_tok=0 cum_in=38782 cum_out=5495 msgs=20 reasoning_chars=0 sent=0 visible_chars=20917 gen_chars=3192+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 11  in=14413 out=5 reasoning_tok=0 cum_in=53195 cum_out=5500 msgs=22 reasoning_chars=0 sent=0 visible_chars=37421 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

