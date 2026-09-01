# Token budget — mistral-medium-2508, 2026-08-31_confirm1v4_Ap_train107hard_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:107:hard | 1.0 | 20.0 | 283787.0 | 15651.0 | 299438 | **yes** | no | piv_submitted (truncated) | 19 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 299,438, max 299,438, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 20, max 20.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 10, 'grep': 4, 'run_beancount': 2, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:107:hard (arm A, BOUND, submitted True)
  turn 01  in=1261 out=6 reasoning_tok=0 cum_in=1261 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=222 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1341 out=25 reasoning_tok=0 cum_in=2602 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=439 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1673 out=25 reasoning_tok=0 cum_in=4275 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1364 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2770 out=27 reasoning_tok=0 cum_in=7045 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5130 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4340 out=29 reasoning_tok=0 cum_in=11385 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=7381 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=8342 out=2273 reasoning_tok=0 cum_in=19727 cum_out=2385 msgs=12 reasoning_chars=0 sent=0 visible_chars=19501 gen_chars=4012+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=10687 out=26 reasoning_tok=0 cum_in=30414 cum_out=2411 msgs=14 reasoning_chars=0 sent=0 visible_chars=23783 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=10780 out=38 reasoning_tok=0 cum_in=41194 cum_out=2449 msgs=16 reasoning_chars=0 sent=0 visible_chars=24010 gen_chars=62+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 09  in=11068 out=8000 reasoning_tok=0 cum_in=52262 cum_out=10449 msgs=18 reasoning_chars=0 sent=0 visible_chars=24959 gen_chars=17732+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 10  in=19109 out=35 reasoning_tok=0 cum_in=71371 cum_out=10484 msgs=20 reasoning_chars=0 sent=0 visible_chars=42861 gen_chars=77+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=19322 out=31 reasoning_tok=0 cum_in=90693 cum_out=10515 msgs=22 reasoning_chars=0 sent=0 visible_chars=43460 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=19357 out=27 reasoning_tok=0 cum_in=110050 cum_out=10542 msgs=24 reasoning_chars=0 sent=0 visible_chars=43537 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 13  in=19871 out=480 reasoning_tok=0 cum_in=129921 cum_out=11022 msgs=26 reasoning_chars=0 sent=0 visible_chars=44362 gen_chars=815+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=20355 out=25 reasoning_tok=0 cum_in=150276 cum_out=11047 msgs=28 reasoning_chars=0 sent=0 visible_chars=45245 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=20463 out=106 reasoning_tok=0 cum_in=170739 cum_out=11153 msgs=30 reasoning_chars=0 sent=0 visible_chars=45470 gen_chars=345+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 16  in=20581 out=29 reasoning_tok=0 cum_in=191320 cum_out=11182 msgs=32 reasoning_chars=0 sent=0 visible_chars=45849 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 17  in=20655 out=190 reasoning_tok=0 cum_in=211975 cum_out=11372 msgs=34 reasoning_chars=0 sent=0 visible_chars=46065 gen_chars=451+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 18  in=20890 out=4266 reasoning_tok=0 cum_in=232865 cum_out=15638 msgs=36 reasoning_chars=0 sent=0 visible_chars=46731 gen_chars=262+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 19  in=25451 out=8 reasoning_tok=0 cum_in=258316 cum_out=15646 msgs=38 reasoning_chars=0 sent=0 visible_chars=60305 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 20  in=25471 out=5 reasoning_tok=0 cum_in=283787 cum_out=15651 msgs=40 reasoning_chars=0 sent=0 visible_chars=60339 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

