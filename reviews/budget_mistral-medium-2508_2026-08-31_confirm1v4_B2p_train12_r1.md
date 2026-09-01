# Token budget — mistral-medium-2508, 2026-08-31_confirm1v4_B2p_train12_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.0 | 14.0 | 139632.0 | 11509.0 | 151141 | **yes** | no | piv_submitted (truncated) | 13 incl. write_ledger | B2 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 151,141, max 151,141, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 14, max 14.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 6, 'grep': 3, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:12 (arm B2, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1254 out=6 reasoning_tok=0 cum_in=1254 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1334 out=26 reasoning_tok=0 cum_in=2588 cum_out=32 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1666 out=26 reasoning_tok=0 cum_in=4254 cum_out=58 msgs=6 reasoning_chars=0 sent=0 visible_chars=1332 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2758 out=28 reasoning_tok=0 cum_in=7012 cum_out=86 msgs=8 reasoning_chars=0 sent=0 visible_chars=5072 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3903 out=29 reasoning_tok=0 cum_in=10915 cum_out=115 msgs=10 reasoning_chars=0 sent=0 visible_chars=6744 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6788 out=26 reasoning_tok=0 cum_in=17703 cum_out=141 msgs=12 reasoning_chars=0 sent=0 visible_chars=15269 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=7063 out=8000 reasoning_tok=0 cum_in=24766 cum_out=8141 msgs=14 reasoning_chars=0 sent=0 visible_chars=16154 gen_chars=15057+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 08  in=15105 out=166 reasoning_tok=0 cum_in=39871 cum_out=8307 msgs=16 reasoning_chars=0 sent=0 visible_chars=31381 gen_chars=330+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=15367 out=22 reasoning_tok=0 cum_in=55238 cum_out=8329 msgs=18 reasoning_chars=0 sent=0 visible_chars=31980 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=15425 out=31 reasoning_tok=0 cum_in=70663 cum_out=8360 msgs=20 reasoning_chars=0 sent=0 visible_chars=32123 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=15460 out=104 reasoning_tok=0 cum_in=86123 cum_out=8464 msgs=22 reasoning_chars=0 sent=0 visible_chars=32205 gen_chars=212+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 12  in=15609 out=3032 reasoning_tok=0 cum_in=101732 cum_out=11496 msgs=24 reasoning_chars=0 sent=0 visible_chars=32634 gen_chars=260+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 13  in=18940 out=8 reasoning_tok=0 cum_in=120672 cum_out=11504 msgs=26 reasoning_chars=0 sent=0 visible_chars=42270 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 14  in=18960 out=5 reasoning_tok=0 cum_in=139632 cum_out=11509 msgs=28 reasoning_chars=0 sent=0 visible_chars=42304 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

