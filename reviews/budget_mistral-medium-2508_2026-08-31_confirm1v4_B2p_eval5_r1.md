# Token budget — mistral-medium-2508, 2026-08-31_confirm1v4_B2p_eval5_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eval:5 | 1.0 | 16.0 | 159526.0 | 11404.0 | 170930 | **yes** | no | piv_submitted (truncated) | 15 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 170,930, max 170,930, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 16, max 16.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 7, 'grep': 3, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
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
  turn 06  in=6526 out=25 reasoning_tok=0 cum_in=17376 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=14563 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6800 out=26 reasoning_tok=0 cum_in=24176 cum_out=163 msgs=14 reasoning_chars=0 sent=0 visible_chars=15445 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=6898 out=8000 reasoning_tok=0 cum_in=31074 cum_out=8163 msgs=16 reasoning_chars=0 sent=0 visible_chars=15695 gen_chars=16331+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 09  in=14940 out=8 reasoning_tok=0 cum_in=46014 cum_out=8171 msgs=18 reasoning_chars=0 sent=0 visible_chars=32196 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=14960 out=182 reasoning_tok=0 cum_in=60974 cum_out=8353 msgs=20 reasoning_chars=0 sent=0 visible_chars=32230 gen_chars=394+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=15182 out=23 reasoning_tok=0 cum_in=76156 cum_out=8376 msgs=22 reasoning_chars=0 sent=0 visible_chars=32751 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=15277 out=34 reasoning_tok=0 cum_in=91433 cum_out=8410 msgs=24 reasoning_chars=0 sent=0 visible_chars=33008 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=15315 out=118 reasoning_tok=0 cum_in=106748 cum_out=8528 msgs=26 reasoning_chars=0 sent=0 visible_chars=33082 gen_chars=228+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 14  in=15478 out=2863 reasoning_tok=0 cum_in=122226 cum_out=11391 msgs=28 reasoning_chars=0 sent=0 visible_chars=33526 gen_chars=250+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 15  in=18640 out=8 reasoning_tok=0 cum_in=140866 cum_out=11399 msgs=30 reasoning_chars=0 sent=0 visible_chars=42608 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 16  in=18660 out=5 reasoning_tok=0 cum_in=159526 cum_out=11404 msgs=32 reasoning_chars=0 sent=0 visible_chars=42642 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

