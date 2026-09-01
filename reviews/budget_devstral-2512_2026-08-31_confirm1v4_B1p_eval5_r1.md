# Token budget — devstral-2512, 2026-08-31_confirm1v4_B1p_eval5_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eval:5 | 0.0 | 14.0 | 193229.0 | 18349.0 | 211578 | **yes** | no | piv_submitted | 14 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 211,578, max 211,578, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 14, max 14.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 8, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1, 'grep': 1, 'submit': 1}
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
  turn 06  in=6526 out=6542 reasoning_tok=0 cum_in=17376 cum_out=6654 msgs=12 reasoning_chars=0 sent=0 visible_chars=14563 gen_chars=24276+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=13498 out=65 reasoning_tok=0 cum_in=30874 cum_out=6719 msgs=14 reasoning_chars=0 sent=0 visible_chars=39515 gen_chars=78+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file,read_file]
  turn 08  in=13683 out=7404 reasoning_tok=0 cum_in=44557 cum_out=14123 msgs=17 reasoning_chars=0 sent=0 visible_chars=40013 gen_chars=9587+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=21382 out=8 reasoning_tok=0 cum_in=65939 cum_out=14131 msgs=19 reasoning_chars=0 sent=0 visible_chars=58244 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=21402 out=46 reasoning_tok=0 cum_in=87341 cum_out=14177 msgs=21 reasoning_chars=0 sent=0 visible_chars=58278 gen_chars=103+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=22034 out=2577 reasoning_tok=0 cum_in=109375 cum_out=16754 msgs=23 reasoning_chars=0 sent=0 visible_chars=60175 gen_chars=7200+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 12  in=27241 out=465 reasoning_tok=0 cum_in=136616 cum_out=17219 msgs=25 reasoning_chars=0 sent=0 visible_chars=75187 gen_chars=679+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=stop trunc=False tools=[-]
  turn 13  in=27738 out=1125 reasoning_tok=0 cum_in=164354 cum_out=18344 msgs=27 reasoning_chars=0 sent=0 visible_chars=75991 gen_chars=2410+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 14  in=28875 out=5 reasoning_tok=0 cum_in=193229 cum_out=18349 msgs=29 reasoning_chars=0 sent=0 visible_chars=78435 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

