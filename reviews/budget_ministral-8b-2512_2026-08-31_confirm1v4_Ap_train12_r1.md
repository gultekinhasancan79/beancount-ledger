# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_Ap_train12_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.55 | 10.0 | 60247.0 | 4436.0 | 64683 | **yes** | no | piv_submitted | 10 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 64,683, max 64,683, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 10, max 10.0
- reward: mean 0.550 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 4, 'run_beancount': 2, 'list_files': 1, 'grep': 1, 'write_ledger': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:12 (arm A, BOUND, submitted True)
  turn 01  in=1242 out=6 reasoning_tok=0 cum_in=1242 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1322 out=29 reasoning_tok=0 cum_in=2564 cum_out=35 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4207 out=27 reasoning_tok=0 cum_in=6771 cum_out=62 msgs=6 reasoning_chars=0 sent=0 visible_chars=8933 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=5351 out=25 reasoning_tok=0 cum_in=12122 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=10604 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=6442 out=19 reasoning_tok=0 cum_in=18564 cum_out=106 msgs=10 reasoning_chars=0 sent=0 visible_chars=14343 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 06  in=6475 out=25 reasoning_tok=0 cum_in=25039 cum_out=131 msgs=12 reasoning_chars=0 sent=0 visible_chars=14439 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=6555 out=8 reasoning_tok=0 cum_in=31594 cum_out=139 msgs=14 reasoning_chars=0 sent=0 visible_chars=14662 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 08  in=6575 out=4155 reasoning_tok=0 cum_in=38169 cum_out=4294 msgs=16 reasoning_chars=0 sent=0 visible_chars=14696 gen_chars=3591+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 09  in=11029 out=8 reasoning_tok=0 cum_in=49198 cum_out=4302 msgs=18 reasoning_chars=0 sent=0 visible_chars=27473 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 10  in=11049 out=134 reasoning_tok=0 cum_in=60247 cum_out=4436 msgs=20 reasoning_chars=0 sent=0 visible_chars=27507 gen_chars=485+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

