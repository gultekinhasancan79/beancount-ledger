# Token budget — mistral-medium-2508, 2026-08-31_confirm1v4_B1p_train107hard_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: B1 (16000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:107:hard | 0.0 | 12.0 | 185016.0 | 20952.0 | 205968 | **yes** | no | piv_submitted (truncated) | 11 incl. write_ledger | B1 | NO_ARTIFACT/policy_blocked (policy_blocked) | True | VALID |

- total tokens: median 205,968, max 205,968, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 12, max 12.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 6, 'list_files': 1, 'grep': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'NO_ARTIFACT/policy_blocked (policy_blocked)': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:107:hard (arm B1, NO_ARTIFACT/policy_blocked (policy_blocked), submitted True)
  turn 01  in=1261 out=6 reasoning_tok=0 cum_in=1261 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=222 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1341 out=25 reasoning_tok=0 cum_in=2602 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=439 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1673 out=25 reasoning_tok=0 cum_in=4275 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1364 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2770 out=27 reasoning_tok=0 cum_in=7045 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5130 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4340 out=29 reasoning_tok=0 cum_in=11385 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=7381 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=8342 out=16000 reasoning_tok=0 cum_in=19727 cum_out=16112 msgs=12 reasoning_chars=0 sent=0 visible_chars=19501 gen_chars=31881+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=length trunc=True tools=[-]
  turn 07  in=24384 out=27 reasoning_tok=0 cum_in=44111 cum_out=16139 msgs=14 reasoning_chars=0 sent=0 visible_chars=51552 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 08  in=25954 out=22 reasoning_tok=0 cum_in=70065 cum_out=16161 msgs=16 reasoning_chars=0 sent=0 visible_chars=53803 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=26154 out=28 reasoning_tok=0 cum_in=96219 cum_out=16189 msgs=18 reasoning_chars=0 sent=0 visible_chars=54325 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 10  in=26227 out=4750 reasoning_tok=0 cum_in=122446 cum_out=20939 msgs=20 reasoning_chars=0 sent=0 visible_chars=54540 gen_chars=1334+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 11  in=31275 out=8 reasoning_tok=0 cum_in=153721 cum_out=20947 msgs=22 reasoning_chars=0 sent=0 visible_chars=69569 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 12  in=31295 out=5 reasoning_tok=0 cum_in=185016 cum_out=20952 msgs=24 reasoning_chars=0 sent=0 visible_chars=69603 gen_chars=0+tool_args=? req_cap=16000 wire_cap=16000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

