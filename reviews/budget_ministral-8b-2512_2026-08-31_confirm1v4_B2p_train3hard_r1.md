# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B2p_train3hard_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:3:hard | 0.0 | 25.0 | 197088.0 | 659.0 | 197747 | **yes** | no | piv_turn_cap_no_submit | 25 NO write | B2 | NO_ARTIFACT/no_write | False | VALID |

- total tokens: median 197,747, max 197,747, over_plan_budget 1/1
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
  turn 08  in=7796 out=25 reasoning_tok=0 cum_in=44830 cum_out=181 msgs=16 reasoning_chars=0 sent=0 visible_chars=17793 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=7861 out=25 reasoning_tok=0 cum_in=52691 cum_out=206 msgs=18 reasoning_chars=0 sent=0 visible_chars=17926 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=7928 out=25 reasoning_tok=0 cum_in=60619 cum_out=231 msgs=20 reasoning_chars=0 sent=0 visible_chars=18065 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=7994 out=25 reasoning_tok=0 cum_in=68613 cum_out=256 msgs=22 reasoning_chars=0 sent=0 visible_chars=18198 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=8188 out=25 reasoning_tok=0 cum_in=76801 cum_out=281 msgs=24 reasoning_chars=0 sent=0 visible_chars=18603 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=8341 out=25 reasoning_tok=0 cum_in=85142 cum_out=306 msgs=26 reasoning_chars=0 sent=0 visible_chars=18927 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 14  in=8495 out=25 reasoning_tok=0 cum_in=93637 cum_out=331 msgs=28 reasoning_chars=0 sent=0 visible_chars=19257 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=8733 out=25 reasoning_tok=0 cum_in=102370 cum_out=356 msgs=30 reasoning_chars=0 sent=0 visible_chars=19791 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=8881 out=25 reasoning_tok=0 cum_in=111251 cum_out=381 msgs=32 reasoning_chars=0 sent=0 visible_chars=20105 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 17  in=9071 out=25 reasoning_tok=0 cum_in=120322 cum_out=406 msgs=34 reasoning_chars=0 sent=0 visible_chars=20529 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 18  in=9179 out=25 reasoning_tok=0 cum_in=129501 cum_out=431 msgs=36 reasoning_chars=0 sent=0 visible_chars=20757 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 19  in=9328 out=25 reasoning_tok=0 cum_in=138829 cum_out=456 msgs=38 reasoning_chars=0 sent=0 visible_chars=21062 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 20  in=9525 out=25 reasoning_tok=0 cum_in=148354 cum_out=481 msgs=40 reasoning_chars=0 sent=0 visible_chars=21490 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 21  in=9674 out=27 reasoning_tok=0 cum_in=158028 cum_out=508 msgs=42 reasoning_chars=0 sent=0 visible_chars=21795 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 22  in=9705 out=34 reasoning_tok=0 cum_in=167733 cum_out=542 msgs=44 reasoning_chars=0 sent=0 visible_chars=21858 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 23  in=9743 out=37 reasoning_tok=0 cum_in=177476 cum_out=579 msgs=46 reasoning_chars=0 sent=0 visible_chars=21946 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 24  in=9784 out=40 reasoning_tok=0 cum_in=187260 cum_out=619 msgs=48 reasoning_chars=0 sent=0 visible_chars=22035 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 25  in=9828 out=40 reasoning_tok=0 cum_in=197088 cum_out=659 msgs=50 reasoning_chars=0 sent=0 visible_chars=22126 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]

