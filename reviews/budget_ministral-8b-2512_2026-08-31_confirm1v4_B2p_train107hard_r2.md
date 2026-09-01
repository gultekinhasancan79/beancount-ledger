# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B2p_train107hard_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:107:hard | 0.0 | 7.0 | 55594.0 | 5244.0 | 60838 | **yes** | no | piv_submitted | 6 incl. write_ledger | B2 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 60,838, max 60,838, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 7, max 7.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 2, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:107:hard (arm B2, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1249 out=31 reasoning_tok=0 cum_in=1249 cum_out=31 msgs=2 reasoning_chars=0 sent=0 visible_chars=222 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 02  in=5253 out=38 reasoning_tok=0 cum_in=6502 cum_out=69 msgs=4 reasoning_chars=0 sent=0 visible_chars=12344 gen_chars=172+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 03  in=5365 out=27 reasoning_tok=0 cum_in=11867 cum_out=96 msgs=6 reasoning_chars=0 sent=0 visible_chars=12733 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=6935 out=4949 reasoning_tok=0 cum_in=18802 cum_out=5045 msgs=8 reasoning_chars=0 sent=0 visible_chars=14984 gen_chars=2476+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 05  in=12178 out=8 reasoning_tok=0 cum_in=30980 cum_out=5053 msgs=10 reasoning_chars=0 sent=0 visible_chars=30573 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 06  in=12198 out=186 reasoning_tok=0 cum_in=43178 cum_out=5239 msgs=12 reasoning_chars=0 sent=0 visible_chars=30607 gen_chars=673+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=stop trunc=False tools=[-]
  turn 07  in=12416 out=5 reasoning_tok=0 cum_in=55594 cum_out=5244 msgs=14 reasoning_chars=0 sent=0 visible_chars=31405 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

