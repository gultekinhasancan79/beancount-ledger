# Token budget — devstral-2512, 2026-08-31_confirm1v4_B2p_eval5_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eval:5 | 1.0 | 15.0 | 173069.0 | 13812.0 | 186881 | **yes** | no | piv_submitted (truncated) | 15 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 186,881, max 186,881, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 15, max 15.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 8, 'grep': 3, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### eval:5 (arm B2, BOUND, submitted True)
  turn 01  in=1261 out=6 reasoning_tok=0 cum_in=1261 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=219 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1341 out=25 reasoning_tok=0 cum_in=2602 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=436 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1672 out=25 reasoning_tok=0 cum_in=4274 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1353 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2766 out=27 reasoning_tok=0 cum_in=7040 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5095 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3810 out=29 reasoning_tok=0 cum_in=10850 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6574 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6526 out=2481 reasoning_tok=0 cum_in=17376 cum_out=2593 msgs=12 reasoning_chars=0 sent=0 visible_chars=14563 gen_chars=4081+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file,read_file]
  turn 07  in=9127 out=8000 reasoning_tok=0 cum_in=26503 cum_out=10593 msgs=15 reasoning_chars=0 sent=0 visible_chars=19064 gen_chars=15738+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 08  in=17169 out=29 reasoning_tok=0 cum_in=43672 cum_out=10622 msgs=17 reasoning_chars=0 sent=0 visible_chars=34972 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=17243 out=133 reasoning_tok=0 cum_in=60915 cum_out=10755 msgs=19 reasoning_chars=0 sent=0 visible_chars=35188 gen_chars=302+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=17416 out=23 reasoning_tok=0 cum_in=78331 cum_out=10778 msgs=21 reasoning_chars=0 sent=0 visible_chars=35617 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=17511 out=23 reasoning_tok=0 cum_in=95842 cum_out=10801 msgs=23 reasoning_chars=0 sent=0 visible_chars=35874 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=17608 out=48 reasoning_tok=0 cum_in=113450 cum_out=10849 msgs=25 reasoning_chars=0 sent=0 visible_chars=36108 gen_chars=64+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 13  in=17701 out=2950 reasoning_tok=0 cum_in=131151 cum_out=13799 msgs=27 reasoning_chars=0 sent=0 visible_chars=36387 gen_chars=480+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 14  in=20949 out=8 reasoning_tok=0 cum_in=152100 cum_out=13807 msgs=29 reasoning_chars=0 sent=0 visible_chars=45689 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 15  in=20969 out=5 reasoning_tok=0 cum_in=173069 cum_out=13812 msgs=31 reasoning_chars=0 sent=0 visible_chars=45723 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

