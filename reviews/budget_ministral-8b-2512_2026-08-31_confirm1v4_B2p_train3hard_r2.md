# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B2p_train3hard_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:3:hard | 0.0 | 25.0 | 190877.0 | 739.0 | 191616 | **yes** | no | piv_turn_cap_no_submit | 25 NO write | B2 | NO_ARTIFACT/no_write | False | VALID |

- total tokens: median 191,616, max 191,616, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 25, max 25.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 20, 'read_file': 4, 'list_files': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/no_write': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:3:hard (arm B2, NO_ARTIFACT/no_write, submitted False)
  turn 01  in=1242 out=6 reasoning_tok=0 cum_in=1242 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=192 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1322 out=29 reasoning_tok=0 cum_in=2564 cum_out=35 msgs=4 reasoning_chars=0 sent=0 visible_chars=409 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4978 out=27 reasoning_tok=0 cum_in=7542 cum_out=62 msgs=6 reasoning_chars=0 sent=0 visible_chars=11348 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=6511 out=25 reasoning_tok=0 cum_in=14053 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=13540 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=7608 out=19 reasoning_tok=0 cum_in=21661 cum_out=106 msgs=10 reasoning_chars=0 sent=0 visible_chars=17303 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 06  in=7641 out=25 reasoning_tok=0 cum_in=29302 cum_out=131 msgs=12 reasoning_chars=0 sent=0 visible_chars=17399 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=7732 out=25 reasoning_tok=0 cum_in=37034 cum_out=156 msgs=14 reasoning_chars=0 sent=0 visible_chars=17661 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=7799 out=25 reasoning_tok=0 cum_in=44833 cum_out=181 msgs=16 reasoning_chars=0 sent=0 visible_chars=17800 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=7865 out=25 reasoning_tok=0 cum_in=52698 cum_out=206 msgs=18 reasoning_chars=0 sent=0 visible_chars=17933 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=8019 out=25 reasoning_tok=0 cum_in=60717 cum_out=231 msgs=20 reasoning_chars=0 sent=0 visible_chars=18263 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=8083 out=25 reasoning_tok=0 cum_in=68800 cum_out=256 msgs=22 reasoning_chars=0 sent=0 visible_chars=18395 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=8148 out=27 reasoning_tok=0 cum_in=76948 cum_out=283 msgs=24 reasoning_chars=0 sent=0 visible_chars=18528 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=8179 out=32 reasoning_tok=0 cum_in=85127 cum_out=315 msgs=26 reasoning_chars=0 sent=0 visible_chars=18591 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=8215 out=36 reasoning_tok=0 cum_in=93342 cum_out=351 msgs=28 reasoning_chars=0 sent=0 visible_chars=18680 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=8308 out=39 reasoning_tok=0 cum_in=101650 cum_out=390 msgs=30 reasoning_chars=0 sent=0 visible_chars=18849 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=8407 out=39 reasoning_tok=0 cum_in=110057 cum_out=429 msgs=32 reasoning_chars=0 sent=0 visible_chars=19022 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 17  in=8564 out=34 reasoning_tok=0 cum_in=118621 cum_out=463 msgs=34 reasoning_chars=0 sent=0 visible_chars=19285 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 18  in=8653 out=34 reasoning_tok=0 cum_in=127274 cum_out=497 msgs=36 reasoning_chars=0 sent=0 visible_chars=19444 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 19  in=8742 out=36 reasoning_tok=0 cum_in=136016 cum_out=533 msgs=38 reasoning_chars=0 sent=0 visible_chars=19603 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 20  in=8835 out=34 reasoning_tok=0 cum_in=144851 cum_out=567 msgs=40 reasoning_chars=0 sent=0 visible_chars=19772 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 21  in=8923 out=36 reasoning_tok=0 cum_in=153774 cum_out=603 msgs=42 reasoning_chars=0 sent=0 visible_chars=19930 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 22  in=9016 out=33 reasoning_tok=0 cum_in=162790 cum_out=636 msgs=44 reasoning_chars=0 sent=0 visible_chars=20099 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 23  in=9307 out=35 reasoning_tok=0 cum_in=172097 cum_out=671 msgs=46 reasoning_chars=0 sent=0 visible_chars=20615 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 24  in=9346 out=34 reasoning_tok=0 cum_in=181443 cum_out=705 msgs=48 reasoning_chars=0 sent=0 visible_chars=20705 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 25  in=9434 out=34 reasoning_tok=0 cum_in=190877 cum_out=739 msgs=50 reasoning_chars=0 sent=0 visible_chars=20875 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]

