# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B2p_eval5_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eval:5 | 0.275 | 6.0 | 29175.0 | 3366.0 | 32541 | no | no | piv_submitted | 5 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 32,541, max 32,541, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 6, max 6.0
- reward: mean 0.275 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 1, 'grep': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### eval:5 (arm B2, BOUND, submitted True)
  turn 01  in=1249 out=31 reasoning_tok=0 cum_in=1249 cum_out=31 msgs=2 reasoning_chars=0 sent=0 visible_chars=219 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 02  in=3967 out=337 reasoning_tok=0 cum_in=5216 cum_out=368 msgs=4 reasoning_chars=0 sent=0 visible_chars=8210 gen_chars=1509+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=stop trunc=False tools=[-]
  turn 03  in=4336 out=37 reasoning_tok=0 cum_in=9552 cum_out=405 msgs=6 reasoning_chars=0 sent=0 visible_chars=9844 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 04  in=4445 out=2835 reasoning_tok=0 cum_in=13997 cum_out=3240 msgs=8 reasoning_chars=0 sent=0 visible_chars=10107 gen_chars=475+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 05  in=7579 out=8 reasoning_tok=0 cum_in=21576 cum_out=3248 msgs=10 reasoning_chars=0 sent=0 visible_chars=19218 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 06  in=7599 out=118 reasoning_tok=0 cum_in=29175 cum_out=3366 msgs=12 reasoning_chars=0 sent=0 visible_chars=19252 gen_chars=530+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

