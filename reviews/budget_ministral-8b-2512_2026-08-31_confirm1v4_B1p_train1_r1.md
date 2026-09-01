# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B1p_train1_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:1 | 1.0 | 19.0 | 123959.0 | 4193.0 | 128152 | **yes** | no | piv_submitted | 19 incl. write_ledger | B1 | BOUND | True | VALID |

- total tokens: median 128,152, max 128,152, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 19, max 19.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'grep': 10, 'read_file': 5, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:1 (arm B1, BOUND, submitted True)
  turn 01  in=1246 out=6 reasoning_tok=0 cum_in=1246 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1326 out=29 reasoning_tok=0 cum_in=2572 cum_out=35 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4020 out=27 reasoning_tok=0 cum_in=6592 cum_out=62 msgs=6 reasoning_chars=0 sent=0 visible_chars=8367 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=5196 out=25 reasoning_tok=0 cum_in=11788 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=10048 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=6287 out=25 reasoning_tok=0 cum_in=18075 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=13790 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=6563 out=19 reasoning_tok=0 cum_in=24638 cum_out=131 msgs=12 reasoning_chars=0 sent=0 visible_chars=14675 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 07  in=6596 out=25 reasoning_tok=0 cum_in=31234 cum_out=156 msgs=14 reasoning_chars=0 sent=0 visible_chars=14771 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=6690 out=24 reasoning_tok=0 cum_in=37924 cum_out=180 msgs=16 reasoning_chars=0 sent=0 visible_chars=15035 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=6774 out=25 reasoning_tok=0 cum_in=44698 cum_out=205 msgs=18 reasoning_chars=0 sent=0 visible_chars=15181 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=6848 out=25 reasoning_tok=0 cum_in=51546 cum_out=230 msgs=20 reasoning_chars=0 sent=0 visible_chars=15336 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=6923 out=25 reasoning_tok=0 cum_in=58469 cum_out=255 msgs=22 reasoning_chars=0 sent=0 visible_chars=15492 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=6997 out=25 reasoning_tok=0 cum_in=65466 cum_out=280 msgs=24 reasoning_chars=0 sent=0 visible_chars=15647 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=7064 out=25 reasoning_tok=0 cum_in=72530 cum_out=305 msgs=26 reasoning_chars=0 sent=0 visible_chars=15790 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=7131 out=25 reasoning_tok=0 cum_in=79661 cum_out=330 msgs=28 reasoning_chars=0 sent=0 visible_chars=15930 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=7199 out=26 reasoning_tok=0 cum_in=86860 cum_out=356 msgs=30 reasoning_chars=0 sent=0 visible_chars=16071 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=7288 out=25 reasoning_tok=0 cum_in=94148 cum_out=381 msgs=32 reasoning_chars=0 sent=0 visible_chars=16219 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 17  in=7363 out=3553 reasoning_tok=0 cum_in=101511 cum_out=3934 msgs=34 reasoning_chars=0 sent=0 visible_chars=16367 gen_chars=2505+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 18  in=11214 out=8 reasoning_tok=0 cum_in=112725 cum_out=3942 msgs=36 reasoning_chars=0 sent=0 visible_chars=27668 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 19  in=11234 out=251 reasoning_tok=0 cum_in=123959 cum_out=4193 msgs=38 reasoning_chars=0 sent=0 visible_chars=27702 gen_chars=834+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

