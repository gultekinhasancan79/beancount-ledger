# Token budget — ministral-8b-2512, 2026-08-31_confirm1v4_B2p_train12_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B2 (8000 tokens/turn, reasoning replay off). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 29f0ddf85e422a94d127d98f658f2d63248a12402d4ed4da0e14292bd69d65d0, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:12 | 0.0 | 14.0 | 99568.0 | 8089.0 | 107657 | **yes** | no | piv_submitted | 14 incl. write_ledger | B2 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 107,657, max 107,657, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 14, max 14.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'grep': 5, 'read_file': 3, 'run_beancount': 2, 'write_ledger': 2, 'list_files': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:12 (arm B2, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1242 out=6 reasoning_tok=0 cum_in=1242 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=191 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1322 out=29 reasoning_tok=0 cum_in=2564 cum_out=35 msgs=4 reasoning_chars=0 sent=0 visible_chars=408 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=4207 out=27 reasoning_tok=0 cum_in=6771 cum_out=62 msgs=6 reasoning_chars=0 sent=0 visible_chars=8933 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=5351 out=25 reasoning_tok=0 cum_in=12122 cum_out=87 msgs=8 reasoning_chars=0 sent=0 visible_chars=10604 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=6442 out=21 reasoning_tok=0 cum_in=18564 cum_out=108 msgs=10 reasoning_chars=0 sent=0 visible_chars=14343 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 06  in=6484 out=21 reasoning_tok=0 cum_in=25048 cum_out=129 msgs=12 reasoning_chars=0 sent=0 visible_chars=14466 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 07  in=6526 out=20 reasoning_tok=0 cum_in=31574 cum_out=149 msgs=14 reasoning_chars=0 sent=0 visible_chars=14598 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=6567 out=22 reasoning_tok=0 cum_in=38141 cum_out=171 msgs=16 reasoning_chars=0 sent=0 visible_chars=14722 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=6610 out=22 reasoning_tok=0 cum_in=44751 cum_out=193 msgs=18 reasoning_chars=0 sent=0 visible_chars=14828 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[grep]
  turn 10  in=6653 out=8 reasoning_tok=0 cum_in=51404 cum_out=201 msgs=20 reasoning_chars=0 sent=0 visible_chars=14942 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 11  in=6673 out=4448 reasoning_tok=0 cum_in=58077 cum_out=4649 msgs=22 reasoning_chars=0 sent=0 visible_chars=14976 gen_chars=3495+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 12  in=11419 out=3305 reasoning_tok=0 cum_in=69496 cum_out=7954 msgs=24 reasoning_chars=0 sent=0 visible_chars=28625 gen_chars=664+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[write_ledger]
  turn 13  in=15026 out=8 reasoning_tok=0 cum_in=84522 cum_out=7962 msgs=26 reasoning_chars=0 sent=0 visible_chars=39200 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[run_beancount]
  turn 14  in=15046 out=127 reasoning_tok=0 cum_in=99568 cum_out=8089 msgs=28 reasoning_chars=0 sent=0 visible_chars=39234 gen_chars=453+tool_args=? req_cap=8000 wire_cap=8000 provider_model=ministral-8b-2512 finish=tool_calls trunc=False tools=[submit]

