# Token budget — devstral-2512, 2026-08-31_confirm1v4_B1p_train30_r2

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 2.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 0.0 | 11.0 | 117223.0 | 24850.0 | 142073 | **yes** | no | piv_submitted | 11 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 142,073, max 142,073, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 11, max 11.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 6, 'list_files': 1, 'grep': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:30 (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1254 out=6 reasoning_tok=0 cum_in=1254 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1334 out=26 reasoning_tok=0 cum_in=2588 cum_out=32 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1665 out=26 reasoning_tok=0 cum_in=4253 cum_out=58 msgs=6 reasoning_chars=0 sent=0 visible_chars=1319 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2766 out=28 reasoning_tok=0 cum_in=7019 cum_out=86 msgs=8 reasoning_chars=0 sent=0 visible_chars=5077 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4285 out=29 reasoning_tok=0 cum_in=11304 cum_out=115 msgs=10 reasoning_chars=0 sent=0 visible_chars=7262 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=8072 out=3646 reasoning_tok=0 cum_in=19376 cum_out=3761 msgs=12 reasoning_chars=0 sent=0 visible_chars=18398 gen_chars=6592+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 07  in=11788 out=533 reasoning_tok=0 cum_in=31164 cum_out=4294 msgs=14 reasoning_chars=0 sent=0 visible_chars=25257 gen_chars=1755+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=12591 out=2591 reasoning_tok=0 cum_in=43755 cum_out=6885 msgs=16 reasoning_chars=0 sent=0 visible_chars=27485 gen_chars=6393+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=15186 out=13643 reasoning_tok=0 cum_in=58941 cum_out=20528 msgs=18 reasoning_chars=0 sent=0 visible_chars=33935 gen_chars=17859+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 10  in=29131 out=8 reasoning_tok=0 cum_in=88072 cum_out=20536 msgs=20 reasoning_chars=0 sent=0 visible_chars=64310 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 11  in=29151 out=4314 reasoning_tok=0 cum_in=117223 cum_out=24850 msgs=22 reasoning_chars=0 sent=0 visible_chars=64344 gen_chars=7474+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

