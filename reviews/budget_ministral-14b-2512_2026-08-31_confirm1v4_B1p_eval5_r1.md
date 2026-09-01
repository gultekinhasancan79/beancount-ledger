# Token budget — ministral-14b-2512, 2026-08-31_confirm1v4_B1p_eval5_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eval:5 | 0.0 | 10.0 | 48924.0 | 3662.0 | 52586 | **yes** | no | piv_submitted | 10 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 52,586, max 52,586, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 10, max 10.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 5, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### eval:5 (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1249 out=6 reasoning_tok=0 cum_in=1249 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=219 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1329 out=25 reasoning_tok=0 cum_in=2578 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=436 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1660 out=25 reasoning_tok=0 cum_in=4238 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1353 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2754 out=25 reasoning_tok=0 cum_in=6992 cum_out=81 msgs=8 reasoning_chars=0 sent=0 visible_chars=5095 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3028 out=27 reasoning_tok=0 cum_in=10020 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=5977 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4072 out=29 reasoning_tok=0 cum_in=14092 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=7456 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6788 out=8 reasoning_tok=0 cum_in=20880 cum_out=145 msgs=14 reasoning_chars=0 sent=0 visible_chars=15445 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=6808 out=3504 reasoning_tok=0 cum_in=27688 cum_out=3649 msgs=16 reasoning_chars=0 sent=0 visible_chars=15479 gen_chars=1990+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=10608 out=8 reasoning_tok=0 cum_in=38296 cum_out=3657 msgs=18 reasoning_chars=0 sent=0 visible_chars=26477 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=10628 out=5 reasoning_tok=0 cum_in=48924 cum_out=3662 msgs=20 reasoning_chars=0 sent=0 visible_chars=26511 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

