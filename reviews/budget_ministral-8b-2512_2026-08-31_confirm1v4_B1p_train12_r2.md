# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B1p_train12_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.0 | 25.0 | 173816.0 | 4349.0 | 178165 | **yes** | no | piv_turn_cap_no_submit | 25 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | False | VALID |

- total tokens: median 178,165, max 178,165, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 25, max 25.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 17, 'read_file': 4, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:12 (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted False)
  turn 01  in=1242 out=6 reasoning_tok=0 cum_in=1242 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1322 out=29 reasoning_tok=0 cum_in=2564 cum_out=35 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4207 out=27 reasoning_tok=0 cum_in=6771 cum_out=62 msgs=6 reasoning_chars=0 sent=0 visible_chars=8933 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=5351 out=25 reasoning_tok=0 cum_in=12122 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=10604 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=6442 out=19 reasoning_tok=0 cum_in=18564 cum_out=106 msgs=10 reasoning_chars=0 sent=0 visible_chars=14343 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 06  in=6475 out=25 reasoning_tok=0 cum_in=25039 cum_out=131 msgs=12 reasoning_chars=0 sent=0 visible_chars=14439 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6566 out=25 reasoning_tok=0 cum_in=31605 cum_out=156 msgs=14 reasoning_chars=0 sent=0 visible_chars=14698 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=6640 out=25 reasoning_tok=0 cum_in=38245 cum_out=181 msgs=16 reasoning_chars=0 sent=0 visible_chars=14848 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=6792 out=25 reasoning_tok=0 cum_in=45037 cum_out=206 msgs=18 reasoning_chars=0 sent=0 visible_chars=15151 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=6897 out=25 reasoning_tok=0 cum_in=51934 cum_out=231 msgs=20 reasoning_chars=0 sent=0 visible_chars=15365 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=7084 out=25 reasoning_tok=0 cum_in=59018 cum_out=256 msgs=22 reasoning_chars=0 sent=0 visible_chars=15749 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=7229 out=25 reasoning_tok=0 cum_in=66247 cum_out=281 msgs=24 reasoning_chars=0 sent=0 visible_chars=16040 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=7416 out=25 reasoning_tok=0 cum_in=73663 cum_out=306 msgs=26 reasoning_chars=0 sent=0 visible_chars=16424 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=7564 out=25 reasoning_tok=0 cum_in=81227 cum_out=331 msgs=28 reasoning_chars=0 sent=0 visible_chars=16733 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=7671 out=25 reasoning_tok=0 cum_in=88898 cum_out=356 msgs=30 reasoning_chars=0 sent=0 visible_chars=16949 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=7792 out=25 reasoning_tok=0 cum_in=96690 cum_out=381 msgs=32 reasoning_chars=0 sent=0 visible_chars=17192 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 17  in=7859 out=25 reasoning_tok=0 cum_in=104549 cum_out=406 msgs=34 reasoning_chars=0 sent=0 visible_chars=17326 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 18  in=7925 out=25 reasoning_tok=0 cum_in=112474 cum_out=431 msgs=36 reasoning_chars=0 sent=0 visible_chars=17459 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 19  in=7991 out=25 reasoning_tok=0 cum_in=120465 cum_out=456 msgs=38 reasoning_chars=0 sent=0 visible_chars=17592 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 20  in=8065 out=25 reasoning_tok=0 cum_in=128530 cum_out=481 msgs=40 reasoning_chars=0 sent=0 visible_chars=17738 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 21  in=8139 out=25 reasoning_tok=0 cum_in=136669 cum_out=506 msgs=42 reasoning_chars=0 sent=0 visible_chars=17884 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 22  in=8204 out=25 reasoning_tok=0 cum_in=144873 cum_out=531 msgs=44 reasoning_chars=0 sent=0 visible_chars=18021 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 23  in=8270 out=8 reasoning_tok=0 cum_in=153143 cum_out=539 msgs=46 reasoning_chars=0 sent=0 visible_chars=18159 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 24  in=8290 out=3802 reasoning_tok=0 cum_in=161433 cum_out=4341 msgs=48 reasoning_chars=0 sent=0 visible_chars=18193 gen_chars=2015+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 25  in=12383 out=8 reasoning_tok=0 cum_in=173816 cum_out=4349 msgs=50 reasoning_chars=0 sent=0 visible_chars=29971 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]

