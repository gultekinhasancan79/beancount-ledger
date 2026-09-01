# Token budget — mistral-medium-2508, 2026-08-31_confirm1v4_B1p_eval5_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eval:5 | 0.0 | 15.0 | 170056.0 | 26164.0 | 196220 | **yes** | no | piv_submitted | 15 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 196,220, max 196,220, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 15, max 15.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 8, 'grep': 2, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### eval:5 (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1261 out=6 reasoning_tok=0 cum_in=1261 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=219 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1341 out=25 reasoning_tok=0 cum_in=2602 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=436 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1672 out=25 reasoning_tok=0 cum_in=4274 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1353 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2766 out=27 reasoning_tok=0 cum_in=7040 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5095 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3810 out=29 reasoning_tok=0 cum_in=10850 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6574 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6526 out=28 reasoning_tok=0 cum_in=17376 cum_out=140 msgs=12 reasoning_chars=0 sent=0 visible_chars=14563 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6984 out=1281 reasoning_tok=0 cum_in=24360 cum_out=1421 msgs=14 reasoning_chars=0 sent=0 visible_chars=15239 gen_chars=2471+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=8337 out=220 reasoning_tok=0 cum_in=32697 cum_out=1641 msgs=16 reasoning_chars=0 sent=0 visible_chars=17960 gen_chars=659+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=8597 out=49 reasoning_tok=0 cum_in=41294 cum_out=1690 msgs=18 reasoning_chars=0 sent=0 visible_chars=18746 gen_chars=74+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=8650 out=718 reasoning_tok=0 cum_in=49944 cum_out=2408 msgs=20 reasoning_chars=0 sent=0 visible_chars=18888 gen_chars=1909+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 11  in=9416 out=14222 reasoning_tok=0 cum_in=59360 cum_out=16630 msgs=22 reasoning_chars=0 sent=0 visible_chars=20967 gen_chars=29342+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 12  in=23682 out=3172 reasoning_tok=0 cum_in=83042 cum_out=19802 msgs=24 reasoning_chars=0 sent=0 visible_chars=50525 gen_chars=338+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 13  in=27157 out=25 reasoning_tok=0 cum_in=110199 cum_out=19827 msgs=26 reasoning_chars=0 sent=0 visible_chars=60525 gen_chars=79+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 14  in=27194 out=5457 reasoning_tok=0 cum_in=137393 cum_out=25284 msgs=28 reasoning_chars=0 sent=0 visible_chars=60638 gen_chars=9427+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 15  in=32663 out=880 reasoning_tok=0 cum_in=170056 cum_out=26164 msgs=30 reasoning_chars=0 sent=0 visible_chars=70099 gen_chars=1427+tool_args=? req_cap=14716 wire_cap=14716 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

