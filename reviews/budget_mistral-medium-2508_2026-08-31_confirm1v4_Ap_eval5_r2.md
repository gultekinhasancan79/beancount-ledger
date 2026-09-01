# Token budget — mistral-medium-2508, 2026-08-31_confirm1v4_Ap_eval5_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eval:5 | 0.0 | 17.0 | 186797.0 | 12014.0 | 198811 | **yes** | no | piv_submitted (truncated) | 16 incl. write_ledger | A | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 198,811, max 198,811, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 17, max 17.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 9, 'grep': 3, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### eval:5 (arm A, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1261 out=6 reasoning_tok=0 cum_in=1261 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=219 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1341 out=25 reasoning_tok=0 cum_in=2602 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=436 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1672 out=25 reasoning_tok=0 cum_in=4274 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1353 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2766 out=27 reasoning_tok=0 cum_in=7040 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5095 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=3810 out=29 reasoning_tok=0 cum_in=10850 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=6574 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6526 out=28 reasoning_tok=0 cum_in=17376 cum_out=140 msgs=12 reasoning_chars=0 sent=0 visible_chars=14563 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6984 out=25 reasoning_tok=0 cum_in=24360 cum_out=165 msgs=14 reasoning_chars=0 sent=0 visible_chars=15239 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=7258 out=8000 reasoning_tok=0 cum_in=31618 cum_out=8165 msgs=16 reasoning_chars=0 sent=0 visible_chars=16121 gen_chars=13851+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 09  in=15300 out=34 reasoning_tok=0 cum_in=46918 cum_out=8199 msgs=18 reasoning_chars=0 sent=0 visible_chars=30142 gen_chars=55+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=15374 out=28 reasoning_tok=0 cum_in=62292 cum_out=8227 msgs=20 reasoning_chars=0 sent=0 visible_chars=30324 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 11  in=15447 out=301 reasoning_tok=0 cum_in=77739 cum_out=8528 msgs=22 reasoning_chars=0 sent=0 visible_chars=30539 gen_chars=731+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=15820 out=207 reasoning_tok=0 cum_in=93559 cum_out=8735 msgs=24 reasoning_chars=0 sent=0 visible_chars=31527 gen_chars=487+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 13  in=17044 out=204 reasoning_tok=0 cum_in=110603 cum_out=8939 msgs=26 reasoning_chars=0 sent=0 visible_chars=33493 gen_chars=471+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=17322 out=29 reasoning_tok=0 cum_in=127925 cum_out=8968 msgs=28 reasoning_chars=0 sent=0 visible_chars=34198 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 15  in=17396 out=3033 reasoning_tok=0 cum_in=145321 cum_out=12001 msgs=30 reasoning_chars=0 sent=0 visible_chars=34414 gen_chars=605+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 16  in=20728 out=8 reasoning_tok=0 cum_in=166049 cum_out=12009 msgs=32 reasoning_chars=0 sent=0 visible_chars=43851 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 17  in=20748 out=5 reasoning_tok=0 cum_in=186797 cum_out=12014 msgs=34 reasoning_chars=0 sent=0 visible_chars=43885 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

