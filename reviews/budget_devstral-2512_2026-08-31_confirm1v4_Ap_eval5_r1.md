# Token budget — devstral-2512, 2026-08-31_confirm1v4_Ap_eval5_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eval:5 | 0.0 | 25.0 | 395665.0 | 22038.0 | 417703 | **yes** | no | piv_turn_cap_no_submit (truncated) | 24 incl. write_ledger | A | NO_ARTIFACT/policy_blocked (policy_blocked) | False | VALID |

- total tokens: median 417,703, max 417,703, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 25, max 25.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 9, 'read_file': 8, 'write_ledger': 3, 'run_beancount': 3, 'list_files': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### eval:5 (arm A, NO_ARTIFACT/policy_blocked (policy_blocked), submitted False)
  turn 01  in=1261 out=6 reasoning_tok=0 cum_in=1261 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=219 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1341 out=25 reasoning_tok=0 cum_in=2602 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=436 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1672 out=25 reasoning_tok=0 cum_in=4274 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1353 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2766 out=27 reasoning_tok=0 cum_in=7040 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5095 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3810 out=29 reasoning_tok=0 cum_in=10850 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6574 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6526 out=28 reasoning_tok=0 cum_in=17376 cum_out=140 msgs=12 reasoning_chars=0 sent=0 visible_chars=14563 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6984 out=8000 reasoning_tok=0 cum_in=24360 cum_out=8140 msgs=14 reasoning_chars=0 sent=0 visible_chars=15239 gen_chars=12639+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 08  in=15026 out=25 reasoning_tok=0 cum_in=39386 cum_out=8165 msgs=16 reasoning_chars=0 sent=0 visible_chars=28048 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=15091 out=34 reasoning_tok=0 cum_in=54477 cum_out=8199 msgs=18 reasoning_chars=0 sent=0 visible_chars=28175 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=15129 out=31 reasoning_tok=0 cum_in=69606 cum_out=8230 msgs=20 reasoning_chars=0 sent=0 visible_chars=28249 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=15164 out=23 reasoning_tok=0 cum_in=84770 cum_out=8253 msgs=22 reasoning_chars=0 sent=0 visible_chars=28318 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=15259 out=155 reasoning_tok=0 cum_in=100029 cum_out=8408 msgs=24 reasoning_chars=0 sent=0 visible_chars=28575 gen_chars=282+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=15506 out=91 reasoning_tok=0 cum_in=115535 cum_out=8499 msgs=26 reasoning_chars=0 sent=0 visible_chars=29050 gen_chars=159+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=15601 out=582 reasoning_tok=0 cum_in=131136 cum_out=9081 msgs=28 reasoning_chars=0 sent=0 visible_chars=29277 gen_chars=1358+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 15  in=16228 out=2867 reasoning_tok=0 cum_in=147364 cum_out=11948 msgs=30 reasoning_chars=0 sent=0 visible_chars=30851 gen_chars=229+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 16  in=19399 out=8 reasoning_tok=0 cum_in=166763 cum_out=11956 msgs=32 reasoning_chars=0 sent=0 visible_chars=39910 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 17  in=19419 out=48 reasoning_tok=0 cum_in=186182 cum_out=12004 msgs=34 reasoning_chars=0 sent=0 visible_chars=39944 gen_chars=100+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 18  in=22157 out=68 reasoning_tok=0 cum_in=208339 cum_out=12072 msgs=36 reasoning_chars=0 sent=0 visible_chars=48034 gen_chars=183+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 19  in=22229 out=103 reasoning_tok=0 cum_in=230568 cum_out=12175 msgs=38 reasoning_chars=0 sent=0 visible_chars=48285 gen_chars=269+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 20  in=22482 out=667 reasoning_tok=0 cum_in=253050 cum_out=12842 msgs=40 reasoning_chars=0 sent=0 visible_chars=48918 gen_chars=1895+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 21  in=23347 out=3338 reasoning_tok=0 cum_in=276397 cum_out=16180 msgs=42 reasoning_chars=0 sent=0 visible_chars=51406 gen_chars=1107+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 22  in=26987 out=8 reasoning_tok=0 cum_in=303384 cum_out=16188 msgs=44 reasoning_chars=0 sent=0 visible_chars=61577 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 23  in=27007 out=5320 reasoning_tok=0 cum_in=330391 cum_out=21508 msgs=46 reasoning_chars=0 sent=0 visible_chars=61611 gen_chars=4179+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 24  in=32627 out=8 reasoning_tok=0 cum_in=363018 cum_out=21516 msgs=48 reasoning_chars=0 sent=0 visible_chars=75035 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 25  in=32647 out=522 reasoning_tok=0 cum_in=395665 cum_out=22038 msgs=50 reasoning_chars=0 sent=0 visible_chars=75069 gen_chars=1169+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]

