# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_Ap_train1_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 0.0 | 20.0 | 133353.0 | 3982.0 | 137335 | **yes** | no | piv_submitted | 19 incl. write_ledger | A | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 137,335, max 137,335, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 20, max 20.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 11, 'read_file': 4, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:1 (arm A, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1246 out=6 reasoning_tok=0 cum_in=1246 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1326 out=29 reasoning_tok=0 cum_in=2572 cum_out=35 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4020 out=27 reasoning_tok=0 cum_in=6592 cum_out=62 msgs=6 reasoning_chars=0 sent=0 visible_chars=8367 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=5196 out=25 reasoning_tok=0 cum_in=11788 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=10048 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=6287 out=19 reasoning_tok=0 cum_in=18075 cum_out=106 msgs=10 reasoning_chars=0 sent=0 visible_chars=13790 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 06  in=6320 out=25 reasoning_tok=0 cum_in=24395 cum_out=131 msgs=12 reasoning_chars=0 sent=0 visible_chars=13886 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6414 out=25 reasoning_tok=0 cum_in=30809 cum_out=156 msgs=14 reasoning_chars=0 sent=0 visible_chars=14150 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=6489 out=25 reasoning_tok=0 cum_in=37298 cum_out=181 msgs=16 reasoning_chars=0 sent=0 visible_chars=14298 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=6723 out=25 reasoning_tok=0 cum_in=44021 cum_out=206 msgs=18 reasoning_chars=0 sent=0 visible_chars=14784 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=6797 out=25 reasoning_tok=0 cum_in=50818 cum_out=231 msgs=20 reasoning_chars=0 sent=0 visible_chars=14939 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=6871 out=25 reasoning_tok=0 cum_in=57689 cum_out=256 msgs=22 reasoning_chars=0 sent=0 visible_chars=15094 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=6938 out=25 reasoning_tok=0 cum_in=64627 cum_out=281 msgs=24 reasoning_chars=0 sent=0 visible_chars=15237 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=7006 out=25 reasoning_tok=0 cum_in=71633 cum_out=306 msgs=26 reasoning_chars=0 sent=0 visible_chars=15381 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=7081 out=25 reasoning_tok=0 cum_in=78714 cum_out=331 msgs=28 reasoning_chars=0 sent=0 visible_chars=15537 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=7148 out=25 reasoning_tok=0 cum_in=85862 cum_out=356 msgs=30 reasoning_chars=0 sent=0 visible_chars=15677 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=7216 out=27 reasoning_tok=0 cum_in=93078 cum_out=383 msgs=32 reasoning_chars=0 sent=0 visible_chars=15818 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 17  in=7247 out=3375 reasoning_tok=0 cum_in=100325 cum_out=3758 msgs=34 reasoning_chars=0 sent=0 visible_chars=15881 gen_chars=1632+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 18  in=10915 out=8 reasoning_tok=0 cum_in=111240 cum_out=3766 msgs=36 reasoning_chars=0 sent=0 visible_chars=26491 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 19  in=10935 out=211 reasoning_tok=0 cum_in=122175 cum_out=3977 msgs=38 reasoning_chars=0 sent=0 visible_chars=26525 gen_chars=573+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=stop trunc=False tools=[-]
  turn 20  in=11178 out=5 reasoning_tok=0 cum_in=133353 cum_out=3982 msgs=40 reasoning_chars=0 sent=0 visible_chars=27223 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

