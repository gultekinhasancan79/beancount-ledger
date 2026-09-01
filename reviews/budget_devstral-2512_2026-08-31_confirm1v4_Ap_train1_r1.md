# Token budget — devstral-2512, 2026-08-31_confirm1v4_Ap_train1_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 0.0 | 11.0 | 95014.0 | 19031.0 | 114045 | **yes** | no | piv_submitted | 11 incl. write_ledger | A | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 114,045, max 114,045, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 11, max 11.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 4, 'write_ledger': 3, 'run_beancount': 2, 'list_files': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:1 (arm A, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1246 out=6 reasoning_tok=0 cum_in=1246 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1326 out=26 reasoning_tok=0 cum_in=2572 cum_out=32 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1660 out=26 reasoning_tok=0 cum_in=4232 cum_out=58 msgs=6 reasoning_chars=0 sent=0 visible_chars=1331 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2752 out=29 reasoning_tok=0 cum_in=6984 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=5074 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=5446 out=28 reasoning_tok=0 cum_in=12430 cum_out=115 msgs=10 reasoning_chars=0 sent=0 visible_chars=13032 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6623 out=4541 reasoning_tok=0 cum_in=19053 cum_out=4656 msgs=12 reasoning_chars=0 sent=0 visible_chars=14714 gen_chars=3478+tool_args=? req_cap=8000 wire_cap=8000 provider_model=devstral-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 07  in=11480 out=8 reasoning_tok=0 cum_in=30533 cum_out=4664 msgs=14 reasoning_chars=0 sent=0 visible_chars=26990 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=11500 out=3079 reasoning_tok=0 cum_in=42033 cum_out=7743 msgs=16 reasoning_chars=0 sent=0 visible_chars=27024 gen_chars=982+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=14883 out=3851 reasoning_tok=0 cum_in=56916 cum_out=11594 msgs=18 reasoning_chars=0 sent=0 visible_chars=36804 gen_chars=2702+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 10  in=19039 out=8 reasoning_tok=0 cum_in=75955 cum_out=11602 msgs=20 reasoning_chars=0 sent=0 visible_chars=48103 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 11  in=19059 out=7429 reasoning_tok=0 cum_in=95014 cum_out=19031 msgs=22 reasoning_chars=0 sent=0 visible_chars=48137 gen_chars=14612+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

