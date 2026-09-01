# Token budget — devstral-2512, 2026-08-31_confirm1v4_B2p_train107hard_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:107:hard | 1.0 | 13.0 | 139902.0 | 13122.0 | 153024 | **yes** | no | piv_submitted (truncated) | 12 incl. write_ledger | B2 | BOUND | True | VALID |

- total tokens: median 153,024, max 153,024, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 13, max 13.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 5, 'grep': 3, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:107:hard (arm B2, BOUND, submitted True)
  turn 01  in=1261 out=6 reasoning_tok=0 cum_in=1261 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=222 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1341 out=25 reasoning_tok=0 cum_in=2602 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=439 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1673 out=25 reasoning_tok=0 cum_in=4275 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1364 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2770 out=27 reasoning_tok=0 cum_in=7045 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5130 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4340 out=29 reasoning_tok=0 cum_in=11385 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=7381 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=8342 out=65 reasoning_tok=0 cum_in=19727 cum_out=177 msgs=12 reasoning_chars=0 sent=0 visible_chars=19501 gen_chars=181+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=8679 out=8000 reasoning_tok=0 cum_in=28406 cum_out=8177 msgs=14 reasoning_chars=0 sent=0 visible_chars=20169 gen_chars=13553+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 08  in=16721 out=24 reasoning_tok=0 cum_in=45127 cum_out=8201 msgs=16 reasoning_chars=0 sent=0 visible_chars=33892 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=16749 out=23 reasoning_tok=0 cum_in=61876 cum_out=8224 msgs=18 reasoning_chars=0 sent=0 visible_chars=33954 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=16776 out=22 reasoning_tok=0 cum_in=78652 cum_out=8246 msgs=20 reasoning_chars=0 sent=0 visible_chars=34011 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=16976 out=4863 reasoning_tok=0 cum_in=95628 cum_out=13109 msgs=22 reasoning_chars=0 sent=0 visible_chars=34533 gen_chars=1747+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 12  in=22127 out=8 reasoning_tok=0 cum_in=117755 cum_out=13117 msgs=24 reasoning_chars=0 sent=0 visible_chars=49592 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 13  in=22147 out=5 reasoning_tok=0 cum_in=139902 cum_out=13122 msgs=26 reasoning_chars=0 sent=0 visible_chars=49626 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

