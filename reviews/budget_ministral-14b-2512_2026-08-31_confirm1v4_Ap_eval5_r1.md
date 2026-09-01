# Token budget — ministral-14b-2512, 2026-08-31_confirm1v4_Ap_eval5_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eval:5 | 0.0 | 18.0 | 174215.0 | 12878.0 | 187093 | **yes** | no | piv_submitted | 18 incl. write_ledger | A | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 187,093, max 187,093, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 18, max 18.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 5, 'run_beancount': 5, 'write_ledger': 4, 'grep': 2, 'list_files': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### eval:5 (arm A, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1249 out=6 reasoning_tok=0 cum_in=1249 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=219 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1329 out=25 reasoning_tok=0 cum_in=2578 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=436 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1660 out=25 reasoning_tok=0 cum_in=4238 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1353 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2754 out=25 reasoning_tok=0 cum_in=6992 cum_out=81 msgs=8 reasoning_chars=0 sent=0 visible_chars=5095 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3028 out=27 reasoning_tok=0 cum_in=10020 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=5977 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4072 out=29 reasoning_tok=0 cum_in=14092 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=7456 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6788 out=8 reasoning_tok=0 cum_in=20880 cum_out=145 msgs=14 reasoning_chars=0 sent=0 visible_chars=15445 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=6808 out=3256 reasoning_tok=0 cum_in=27688 cum_out=3401 msgs=16 reasoning_chars=0 sent=0 visible_chars=15479 gen_chars=1713+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=10365 out=8 reasoning_tok=0 cum_in=38053 cum_out=3409 msgs=18 reasoning_chars=0 sent=0 visible_chars=26022 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=10385 out=193 reasoning_tok=0 cum_in=48438 cum_out=3602 msgs=20 reasoning_chars=0 sent=0 visible_chars=26056 gen_chars=674+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=10582 out=35 reasoning_tok=0 cum_in=59020 cum_out=3637 msgs=22 reasoning_chars=0 sent=0 visible_chars=26813 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=10621 out=2991 reasoning_tok=0 cum_in=69641 cum_out=6628 msgs=24 reasoning_chars=0 sent=0 visible_chars=26896 gen_chars=610+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 13  in=13912 out=8 reasoning_tok=0 cum_in=83553 cum_out=6636 msgs=26 reasoning_chars=0 sent=0 visible_chars=36338 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 14  in=13932 out=3337 reasoning_tok=0 cum_in=97485 cum_out=9973 msgs=28 reasoning_chars=0 sent=0 visible_chars=36372 gen_chars=627+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 15  in=17571 out=8 reasoning_tok=0 cum_in=115056 cum_out=9981 msgs=30 reasoning_chars=0 sent=0 visible_chars=46847 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 16  in=17591 out=2884 reasoning_tok=0 cum_in=132647 cum_out=12865 msgs=32 reasoning_chars=0 sent=0 visible_chars=46881 gen_chars=640+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 17  in=20774 out=8 reasoning_tok=0 cum_in=153421 cum_out=12873 msgs=34 reasoning_chars=0 sent=0 visible_chars=56089 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 18  in=20794 out=5 reasoning_tok=0 cum_in=174215 cum_out=12878 msgs=36 reasoning_chars=0 sent=0 visible_chars=56123 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[submit]

