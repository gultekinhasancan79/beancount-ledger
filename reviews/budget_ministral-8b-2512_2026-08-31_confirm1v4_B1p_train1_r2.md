# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B1p_train1_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 0.0 | 22.0 | 146724.0 | 4282.0 | 151006 | **yes** | no | piv_submitted | 22 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 151,006, max 151,006, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 22, max 22.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 14, 'read_file': 4, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:1 (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1246 out=6 reasoning_tok=0 cum_in=1246 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1326 out=29 reasoning_tok=0 cum_in=2572 cum_out=35 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4020 out=27 reasoning_tok=0 cum_in=6592 cum_out=62 msgs=6 reasoning_chars=0 sent=0 visible_chars=8367 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=5196 out=25 reasoning_tok=0 cum_in=11788 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=10048 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=6287 out=19 reasoning_tok=0 cum_in=18075 cum_out=106 msgs=10 reasoning_chars=0 sent=0 visible_chars=13790 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 06  in=6320 out=25 reasoning_tok=0 cum_in=24395 cum_out=131 msgs=12 reasoning_chars=0 sent=0 visible_chars=13886 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6414 out=25 reasoning_tok=0 cum_in=30809 cum_out=156 msgs=14 reasoning_chars=0 sent=0 visible_chars=14150 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=6482 out=25 reasoning_tok=0 cum_in=37291 cum_out=181 msgs=16 reasoning_chars=0 sent=0 visible_chars=14294 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=6556 out=25 reasoning_tok=0 cum_in=43847 cum_out=206 msgs=18 reasoning_chars=0 sent=0 visible_chars=14449 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=6631 out=25 reasoning_tok=0 cum_in=50478 cum_out=231 msgs=20 reasoning_chars=0 sent=0 visible_chars=14605 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=6705 out=25 reasoning_tok=0 cum_in=57183 cum_out=256 msgs=22 reasoning_chars=0 sent=0 visible_chars=14760 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=6772 out=25 reasoning_tok=0 cum_in=63955 cum_out=281 msgs=24 reasoning_chars=0 sent=0 visible_chars=14903 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=6839 out=25 reasoning_tok=0 cum_in=70794 cum_out=306 msgs=26 reasoning_chars=0 sent=0 visible_chars=15043 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=6907 out=25 reasoning_tok=0 cum_in=77701 cum_out=331 msgs=28 reasoning_chars=0 sent=0 visible_chars=15184 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=6982 out=25 reasoning_tok=0 cum_in=84683 cum_out=356 msgs=30 reasoning_chars=0 sent=0 visible_chars=15332 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=7216 out=25 reasoning_tok=0 cum_in=91899 cum_out=381 msgs=32 reasoning_chars=0 sent=0 visible_chars=15818 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 17  in=7396 out=25 reasoning_tok=0 cum_in=99295 cum_out=406 msgs=34 reasoning_chars=0 sent=0 visible_chars=16193 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 18  in=7598 out=25 reasoning_tok=0 cum_in=106893 cum_out=431 msgs=36 reasoning_chars=0 sent=0 visible_chars=16608 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 19  in=7753 out=25 reasoning_tok=0 cum_in=114646 cum_out=456 msgs=38 reasoning_chars=0 sent=0 visible_chars=16922 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 20  in=7944 out=3813 reasoning_tok=0 cum_in=122590 cum_out=4269 msgs=40 reasoning_chars=0 sent=0 visible_chars=17316 gen_chars=1835+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 21  in=12057 out=8 reasoning_tok=0 cum_in=134647 cum_out=4277 msgs=42 reasoning_chars=0 sent=0 visible_chars=28716 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 22  in=12077 out=5 reasoning_tok=0 cum_in=146724 cum_out=4282 msgs=44 reasoning_chars=0 sent=0 visible_chars=28750 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

