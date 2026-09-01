# Token budget — devstral-2512, 2026-08-31_confirm1v4_Ap_train30_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 1.0 | 11.0 | 87880.0 | 12199.0 | 100079 | **yes** | no | piv_submitted | 11 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 100,079, max 100,079, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 11, max 11.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:30 (arm A, BOUND, submitted True)
  turn 01  in=1254 out=6 reasoning_tok=0 cum_in=1254 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1334 out=25 reasoning_tok=0 cum_in=2588 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1664 out=25 reasoning_tok=0 cum_in=4252 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1318 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2764 out=27 reasoning_tok=0 cum_in=7016 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5075 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4282 out=29 reasoning_tok=0 cum_in=11298 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=7259 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=8069 out=25 reasoning_tok=0 cum_in=19367 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=18395 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=8342 out=3822 reasoning_tok=0 cum_in=27709 cum_out=3959 msgs=14 reasoning_chars=0 sent=0 visible_chars=19270 gen_chars=7071+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=12234 out=301 reasoning_tok=0 cum_in=39943 cum_out=4260 msgs=16 reasoning_chars=0 sent=0 visible_chars=26607 gen_chars=919+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=12805 out=4456 reasoning_tok=0 cum_in=52748 cum_out=8716 msgs=18 reasoning_chars=0 sent=0 visible_chars=27998 gen_chars=1627+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 10  in=17556 out=8 reasoning_tok=0 cum_in=70304 cum_out=8724 msgs=20 reasoning_chars=0 sent=0 visible_chars=41940 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 11  in=17576 out=3475 reasoning_tok=0 cum_in=87880 cum_out=12199 msgs=22 reasoning_chars=0 sent=0 visible_chars=41974 gen_chars=5889+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

