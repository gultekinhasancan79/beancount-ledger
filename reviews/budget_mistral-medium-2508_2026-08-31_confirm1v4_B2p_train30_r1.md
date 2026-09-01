# Token budget — mistral-medium-2508, 2026-08-31_confirm1v4_B2p_train30_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 0.0 | 15.0 | 168919.0 | 16245.0 | 185164 | **yes** | no | piv_submitted (truncated) | 14 incl. write_ledger | B2 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 185,164, max 185,164, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 15, max 15.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'grep': 3, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:30 (arm B2, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1254 out=6 reasoning_tok=0 cum_in=1254 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1334 out=25 reasoning_tok=0 cum_in=2588 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1664 out=25 reasoning_tok=0 cum_in=4252 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1318 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2764 out=27 reasoning_tok=0 cum_in=7016 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5075 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4282 out=29 reasoning_tok=0 cum_in=11298 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=7259 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=8069 out=25 reasoning_tok=0 cum_in=19367 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=18395 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=8342 out=3207 reasoning_tok=0 cum_in=27709 cum_out=3344 msgs=14 reasoning_chars=0 sent=0 visible_chars=19270 gen_chars=6684+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=11619 out=182 reasoning_tok=0 cum_in=39328 cum_out=3526 msgs=16 reasoning_chars=0 sent=0 visible_chars=26220 gen_chars=629+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=11805 out=117 reasoning_tok=0 cum_in=51133 cum_out=3643 msgs=18 reasoning_chars=0 sent=0 visible_chars=26909 gen_chars=301+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=12271 out=196 reasoning_tok=0 cum_in=63404 cum_out=3839 msgs=20 reasoning_chars=0 sent=0 visible_chars=28067 gen_chars=580+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 11  in=12737 out=8000 reasoning_tok=0 cum_in=76141 cum_out=11839 msgs=22 reasoning_chars=0 sent=0 visible_chars=29119 gen_chars=17273+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 12  in=20779 out=163 reasoning_tok=0 cum_in=96920 cum_out=12002 msgs=24 reasoning_chars=0 sent=0 visible_chars=46562 gen_chars=383+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=20977 out=4230 reasoning_tok=0 cum_in=117897 cum_out=16232 msgs=26 reasoning_chars=0 sent=0 visible_chars=47086 gen_chars=653+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 14  in=25501 out=8 reasoning_tok=0 cum_in=143398 cum_out=16240 msgs=28 reasoning_chars=0 sent=0 visible_chars=60244 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 15  in=25521 out=5 reasoning_tok=0 cum_in=168919 cum_out=16245 msgs=30 reasoning_chars=0 sent=0 visible_chars=60278 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

