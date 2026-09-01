# Token budget — ministral-14b-2512, 2026-08-31_confirm1v4_Ap_train107hard_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:107:hard | 0.0 | 20.0 | 145744.0 | 5820.0 | 151564 | **yes** | no | piv_submitted | 20 incl. write_ledger | A | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 151,564, max 151,564, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 20, max 20.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 8, 'read_file': 7, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:107:hard (arm A, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1249 out=6 reasoning_tok=0 cum_in=1249 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=222 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1329 out=25 reasoning_tok=0 cum_in=2578 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=439 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1661 out=25 reasoning_tok=0 cum_in=4239 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1364 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2758 out=25 reasoning_tok=0 cum_in=6997 cum_out=81 msgs=8 reasoning_chars=0 sent=0 visible_chars=5130 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3033 out=25 reasoning_tok=0 cum_in=10030 cum_out=106 msgs=10 reasoning_chars=0 sent=0 visible_chars=6017 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=3130 out=25 reasoning_tok=0 cum_in=13160 cum_out=131 msgs=12 reasoning_chars=0 sent=0 visible_chars=6286 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=3222 out=27 reasoning_tok=0 cum_in=16382 cum_out=158 msgs=14 reasoning_chars=0 sent=0 visible_chars=6512 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=4792 out=29 reasoning_tok=0 cum_in=21174 cum_out=187 msgs=16 reasoning_chars=0 sent=0 visible_chars=8763 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=8794 out=8 reasoning_tok=0 cum_in=29968 cum_out=195 msgs=18 reasoning_chars=0 sent=0 visible_chars=20883 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=8814 out=470 reasoning_tok=0 cum_in=38782 cum_out=665 msgs=20 reasoning_chars=0 sent=0 visible_chars=20917 gen_chars=1620+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=9288 out=38 reasoning_tok=0 cum_in=48070 cum_out=703 msgs=22 reasoning_chars=0 sent=0 visible_chars=22625 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=9330 out=36 reasoning_tok=0 cum_in=57400 cum_out=739 msgs=24 reasoning_chars=0 sent=0 visible_chars=22716 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=9370 out=38 reasoning_tok=0 cum_in=66770 cum_out=777 msgs=26 reasoning_chars=0 sent=0 visible_chars=22805 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=9412 out=31 reasoning_tok=0 cum_in=76182 cum_out=808 msgs=28 reasoning_chars=0 sent=0 visible_chars=22898 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=9554 out=282 reasoning_tok=0 cum_in=85736 cum_out=1090 msgs=30 reasoning_chars=0 sent=0 visible_chars=23138 gen_chars=645+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=9893 out=33 reasoning_tok=0 cum_in=95629 cum_out=1123 msgs=32 reasoning_chars=0 sent=0 visible_chars=23931 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 17  in=9984 out=33 reasoning_tok=0 cum_in=105613 cum_out=1156 msgs=34 reasoning_chars=0 sent=0 visible_chars=24086 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 18  in=10075 out=4651 reasoning_tok=0 cum_in=115688 cum_out=5807 msgs=36 reasoning_chars=0 sent=0 visible_chars=24245 gen_chars=1304+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 19  in=15018 out=8 reasoning_tok=0 cum_in=130706 cum_out=5815 msgs=38 reasoning_chars=0 sent=0 visible_chars=39055 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 20  in=15038 out=5 reasoning_tok=0 cum_in=145744 cum_out=5820 msgs=40 reasoning_chars=0 sent=0 visible_chars=39089 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

