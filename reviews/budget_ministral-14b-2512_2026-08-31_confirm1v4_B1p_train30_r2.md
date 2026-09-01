# Token budget — ministral-14b-2512, 2026-08-31_confirm1v4_B1p_train30_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 0.0 | 25.0 | 182278.0 | 571.0 | 182849 | **yes** | no | piv_turn_cap_no_submit | 25 NO write | B1 | NO_ARTIFACT/no_write | False | VALID |

- total tokens: median 182,849, max 182,849, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 25, max 25.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 19, 'read_file': 5, 'list_files': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/no_write': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:30 (arm B1, NO_ARTIFACT/no_write, submitted False)
  turn 01  in=1242 out=6 reasoning_tok=0 cum_in=1242 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1322 out=25 reasoning_tok=0 cum_in=2564 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1652 out=25 reasoning_tok=0 cum_in=4216 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1318 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2752 out=27 reasoning_tok=0 cum_in=6968 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5075 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4270 out=29 reasoning_tok=0 cum_in=11238 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=7259 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=8057 out=25 reasoning_tok=0 cum_in=19295 cum_out=137 msgs=12 reasoning_chars=0 sent=0 visible_chars=18395 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=8330 out=31 reasoning_tok=0 cum_in=27625 cum_out=168 msgs=14 reasoning_chars=0 sent=0 visible_chars=19270 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=8365 out=24 reasoning_tok=0 cum_in=35990 cum_out=192 msgs=16 reasoning_chars=0 sent=0 visible_chars=19353 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=8393 out=22 reasoning_tok=0 cum_in=44383 cum_out=214 msgs=18 reasoning_chars=0 sent=0 visible_chars=19417 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=8419 out=23 reasoning_tok=0 cum_in=52802 cum_out=237 msgs=20 reasoning_chars=0 sent=0 visible_chars=19482 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=8446 out=26 reasoning_tok=0 cum_in=61248 cum_out=263 msgs=22 reasoning_chars=0 sent=0 visible_chars=19549 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=8476 out=22 reasoning_tok=0 cum_in=69724 cum_out=285 msgs=24 reasoning_chars=0 sent=0 visible_chars=19619 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=8502 out=22 reasoning_tok=0 cum_in=78226 cum_out=307 msgs=26 reasoning_chars=0 sent=0 visible_chars=19676 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=8528 out=22 reasoning_tok=0 cum_in=86754 cum_out=329 msgs=28 reasoning_chars=0 sent=0 visible_chars=19733 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=8554 out=22 reasoning_tok=0 cum_in=95308 cum_out=351 msgs=30 reasoning_chars=0 sent=0 visible_chars=19790 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=8580 out=22 reasoning_tok=0 cum_in=103888 cum_out=373 msgs=32 reasoning_chars=0 sent=0 visible_chars=19847 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 17  in=8606 out=22 reasoning_tok=0 cum_in=112494 cum_out=395 msgs=34 reasoning_chars=0 sent=0 visible_chars=19904 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 18  in=8632 out=22 reasoning_tok=0 cum_in=121126 cum_out=417 msgs=36 reasoning_chars=0 sent=0 visible_chars=19961 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 19  in=8658 out=22 reasoning_tok=0 cum_in=129784 cum_out=439 msgs=38 reasoning_chars=0 sent=0 visible_chars=20018 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 20  in=8684 out=22 reasoning_tok=0 cum_in=138468 cum_out=461 msgs=40 reasoning_chars=0 sent=0 visible_chars=20075 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 21  in=8710 out=22 reasoning_tok=0 cum_in=147178 cum_out=483 msgs=42 reasoning_chars=0 sent=0 visible_chars=20132 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 22  in=8736 out=22 reasoning_tok=0 cum_in=155914 cum_out=505 msgs=44 reasoning_chars=0 sent=0 visible_chars=20189 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 23  in=8762 out=22 reasoning_tok=0 cum_in=164676 cum_out=527 msgs=46 reasoning_chars=0 sent=0 visible_chars=20246 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 24  in=8788 out=22 reasoning_tok=0 cum_in=173464 cum_out=549 msgs=48 reasoning_chars=0 sent=0 visible_chars=20303 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 25  in=8814 out=22 reasoning_tok=0 cum_in=182278 cum_out=571 msgs=50 reasoning_chars=0 sent=0 visible_chars=20360 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=ministral-14b-2512 finish=tool_calls trunc=False tools=[grep]

