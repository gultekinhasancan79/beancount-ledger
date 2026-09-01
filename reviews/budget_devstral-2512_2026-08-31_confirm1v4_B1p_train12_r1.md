# Token budget — devstral-2512, 2026-08-31_confirm1v4_B1p_train12_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 1.0 | 12.0 | 74304.0 | 11652.0 | 85956 | **yes** | no | piv_submitted | 12 incl. write_ledger | B1 | BOUND | True | VALID |

- total tokens: median 85,956, max 85,956, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 12, max 12.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 8, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:12 (arm B1, BOUND, submitted True)
  turn 01  in=1254 out=6 reasoning_tok=0 cum_in=1254 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1334 out=25 reasoning_tok=0 cum_in=2588 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1665 out=25 reasoning_tok=0 cum_in=4253 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1331 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2756 out=27 reasoning_tok=0 cum_in=7009 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5070 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3900 out=25 reasoning_tok=0 cum_in=10909 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=6741 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=4174 out=26 reasoning_tok=0 cum_in=15083 cum_out=134 msgs=12 reasoning_chars=0 sent=0 visible_chars=7625 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=4248 out=26 reasoning_tok=0 cum_in=19331 cum_out=160 msgs=14 reasoning_chars=0 sent=0 visible_chars=7799 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=4340 out=28 reasoning_tok=0 cum_in=23671 cum_out=188 msgs=16 reasoning_chars=0 sent=0 visible_chars=8059 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=4631 out=29 reasoning_tok=0 cum_in=28302 cum_out=217 msgs=18 reasoning_chars=0 sent=0 visible_chars=8525 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 10  in=7516 out=11422 reasoning_tok=0 cum_in=35818 cum_out=11639 msgs=20 reasoning_chars=0 sent=0 visible_chars=17050 gen_chars=14926+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 11  in=19233 out=8 reasoning_tok=0 cum_in=55051 cum_out=11647 msgs=22 reasoning_chars=0 sent=0 visible_chars=41352 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 12  in=19253 out=5 reasoning_tok=0 cum_in=74304 cum_out=11652 msgs=24 reasoning_chars=0 sent=0 visible_chars=41386 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

