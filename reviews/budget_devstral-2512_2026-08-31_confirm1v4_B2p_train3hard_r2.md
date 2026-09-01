# Token budget — devstral-2512, 2026-08-31_confirm1v4_B2p_train3hard_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:3:hard | 1.0 | 10.0 | 75109.0 | 9751.0 | 84860 | **yes** | no | piv_submitted | 10 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 84,860, max 84,860, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 10, max 10.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 6, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:3:hard (arm B2, BOUND, submitted True)
  turn 01  in=1254 out=6 reasoning_tok=0 cum_in=1254 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1334 out=25 reasoning_tok=0 cum_in=2588 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1667 out=25 reasoning_tok=0 cum_in=4255 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1338 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2764 out=27 reasoning_tok=0 cum_in=7019 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5101 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4297 out=29 reasoning_tok=0 cum_in=11316 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=7293 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=7953 out=25 reasoning_tok=0 cum_in=19269 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=18232 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=8229 out=2912 reasoning_tok=0 cum_in=27498 cum_out=3049 msgs=14 reasoning_chars=0 sent=0 visible_chars=19121 gen_chars=6611+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=11207 out=6689 reasoning_tok=0 cum_in=38705 cum_out=9738 msgs=16 reasoning_chars=0 sent=0 visible_chars=25995 gen_chars=6241+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=18192 out=8 reasoning_tok=0 cum_in=56897 cum_out=9746 msgs=18 reasoning_chars=0 sent=0 visible_chars=44312 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=18212 out=5 reasoning_tok=0 cum_in=75109 cum_out=9751 msgs=20 reasoning_chars=0 sent=0 visible_chars=44346 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

