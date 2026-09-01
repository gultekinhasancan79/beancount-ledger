# Token budget — devstral-2512, 2026-08-31_confirm1v4_B2p_train30_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 1.0 | 15.0 | 181150.0 | 17284.0 | 198434 | **yes** | no | piv_submitted (truncated) | 14 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 198,434, max 198,434, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 15, max 15.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 8, 'grep': 2, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:30 (arm B2, BOUND, submitted True)
  turn 01  in=1254 out=6 reasoning_tok=0 cum_in=1254 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1334 out=25 reasoning_tok=0 cum_in=2588 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1664 out=25 reasoning_tok=0 cum_in=4252 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1318 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2764 out=27 reasoning_tok=0 cum_in=7016 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5075 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4282 out=29 reasoning_tok=0 cum_in=11298 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=7259 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=8069 out=25 reasoning_tok=0 cum_in=19367 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=18395 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=8342 out=2323 reasoning_tok=0 cum_in=27709 cum_out=2460 msgs=14 reasoning_chars=0 sent=0 visible_chars=19270 gen_chars=5015+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=10735 out=26 reasoning_tok=0 cum_in=38444 cum_out=2486 msgs=16 reasoning_chars=0 sent=0 visible_chars=24551 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=10823 out=2676 reasoning_tok=0 cum_in=49267 cum_out=5162 msgs=18 reasoning_chars=0 sent=0 visible_chars=24760 gen_chars=9126+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 10  in=13769 out=8000 reasoning_tok=0 cum_in=63036 cum_out=13162 msgs=20 reasoning_chars=0 sent=0 visible_chars=34358 gen_chars=17141+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 11  in=21811 out=25 reasoning_tok=0 cum_in=84847 cum_out=13187 msgs=22 reasoning_chars=0 sent=0 visible_chars=51669 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=21840 out=24 reasoning_tok=0 cum_in=106687 cum_out=13211 msgs=24 reasoning_chars=0 sent=0 visible_chars=51729 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=21911 out=4060 reasoning_tok=0 cum_in=128598 cum_out=17271 msgs=26 reasoning_chars=0 sent=0 visible_chars=51858 gen_chars=311+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 14  in=26266 out=8 reasoning_tok=0 cum_in=154864 cum_out=17279 msgs=28 reasoning_chars=0 sent=0 visible_chars=64484 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 15  in=26286 out=5 reasoning_tok=0 cum_in=181150 cum_out=17284 msgs=30 reasoning_chars=0 sent=0 visible_chars=64518 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

