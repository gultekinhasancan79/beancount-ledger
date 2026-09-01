# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B2p_train107hard_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:107:hard | 0.0 | 9.0 | 69103.0 | 5504.0 | 74607 | **yes** | no | piv_submitted | 9 incl. write_ledger | B2 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 74,607, max 74,607, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 9, max 9.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 3, 'read_file': 2, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:107:hard (arm B2, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1249 out=29 reasoning_tok=0 cum_in=1249 cum_out=29 msgs=2 reasoning_chars=0 sent=0 visible_chars=222 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 02  in=5251 out=44 reasoning_tok=0 cum_in=6500 cum_out=73 msgs=4 reasoning_chars=0 sent=0 visible_chars=12342 gen_chars=205+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 03  in=5369 out=27 reasoning_tok=0 cum_in=11869 cum_out=100 msgs=6 reasoning_chars=0 sent=0 visible_chars=12764 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=6939 out=680 reasoning_tok=0 cum_in=18808 cum_out=780 msgs=8 reasoning_chars=0 sent=0 visible_chars=15015 gen_chars=2123+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 05  in=7797 out=25 reasoning_tok=0 cum_in=26605 cum_out=805 msgs=10 reasoning_chars=0 sent=0 visible_chars=17670 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 06  in=8163 out=22 reasoning_tok=0 cum_in=34768 cum_out=827 msgs=12 reasoning_chars=0 sent=0 visible_chars=18479 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 07  in=8241 out=4496 reasoning_tok=0 cum_in=43009 cum_out=5323 msgs=14 reasoning_chars=0 sent=0 visible_chars=18676 gen_chars=1027+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 08  in=13037 out=8 reasoning_tok=0 cum_in=56046 cum_out=5331 msgs=16 reasoning_chars=0 sent=0 visible_chars=33011 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 09  in=13057 out=173 reasoning_tok=0 cum_in=69103 cum_out=5504 msgs=18 reasoning_chars=0 sent=0 visible_chars=33045 gen_chars=576+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

