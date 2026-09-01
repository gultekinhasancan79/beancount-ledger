# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B1p_train107hard_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:107:hard | 0.55 | 6.0 | 43446.0 | 5287.0 | 48733 | no | no | piv_submitted | 6 incl. write_ledger | B1 | BOUND | True | VALID |

- total tokens: median 48,733, max 48,733, over_plan_budget 0/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 6, max 6.0
- reward: mean 0.550 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 2, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:107:hard (arm B1, BOUND, submitted True)
  turn 01  in=1249 out=31 reasoning_tok=0 cum_in=1249 cum_out=31 msgs=2 reasoning_chars=0 sent=0 visible_chars=222 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 02  in=5253 out=47 reasoning_tok=0 cum_in=6502 cum_out=78 msgs=4 reasoning_chars=0 sent=0 visible_chars=12344 gen_chars=208+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 03  in=5374 out=27 reasoning_tok=0 cum_in=11876 cum_out=105 msgs=6 reasoning_chars=0 sent=0 visible_chars=12769 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=6944 out=5062 reasoning_tok=0 cum_in=18820 cum_out=5167 msgs=8 reasoning_chars=0 sent=0 visible_chars=15020 gen_chars=2919+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 05  in=12303 out=8 reasoning_tok=0 cum_in=31123 cum_out=5175 msgs=10 reasoning_chars=0 sent=0 visible_chars=31084 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 06  in=12323 out=112 reasoning_tok=0 cum_in=43446 cum_out=5287 msgs=12 reasoning_chars=0 sent=0 visible_chars=31118 gen_chars=395+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

