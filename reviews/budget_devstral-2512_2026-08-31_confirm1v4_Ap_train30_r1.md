# Token budget — devstral-2512, 2026-08-31_confirm1v4_Ap_train30_r1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.
Arm: A (8000 tokens/turn, reasoning replay on). Max total completion tokens: 40000. Timeout 600s, retries 0. Replicate 1.
Sampling pins: temperature=0.0, top_p=1.0, seed=None. prompt_schema_digest 8648cdda14a23da0addc37dbf274baf8407b93d2520a00796ab4f6ff3883d1d5.
replay_contract v1, digest 180288689de672797295e0b4d189856d59830201fcd633794c5dc026169288ed, libraries {'verifiers': '0.3.1', 'openai': '3.5.0'}. SDK retries 0 (ClientConfig.max_retries), framework retries 0. Schedule be443ec836e091823d6538f5dc0f57687af597b9b054534830b431d2916cd763.

| selector | reward | turns | tokens in | tokens out | total | over_plan_budget | ceiling_hit | stop | tools | arm | artifact | submitted | budget_accounting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train:30 | 1.0 | 22.0 | 277076.0 | 18515.0 | 295591 | **yes** | no | piv_submitted | 22 incl. write_ledger | A | BOUND | True | VALID |

- total tokens: median 295,591, max 295,591, over_plan_budget 1/1
- ceiling_hit (stop == piv_output_budget_exhausted): 0/1
- turns: median 22, max 22.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'grep': 11, 'read_file': 7, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
- artifact binding over all rollouts: {'BOUND': 1}
- budget_accounting over all rollouts: {'VALID': 1}
- SUSPICIOUS: none

## Per-turn detail

### train:30 (arm A, BOUND, submitted True)
  turn 01  in=1254 out=6 reasoning_tok=0 cum_in=1254 cum_out=6 msgs=2 reasoning_chars=0 sent=0 visible_chars=189 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[list_files]
  turn 02  in=1334 out=25 reasoning_tok=0 cum_in=2588 cum_out=31 msgs=4 reasoning_chars=0 sent=0 visible_chars=406 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 03  in=1664 out=25 reasoning_tok=0 cum_in=4252 cum_out=56 msgs=6 reasoning_chars=0 sent=0 visible_chars=1318 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 04  in=2764 out=27 reasoning_tok=0 cum_in=7016 cum_out=83 msgs=8 reasoning_chars=0 sent=0 visible_chars=5075 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 05  in=4282 out=29 reasoning_tok=0 cum_in=11298 cum_out=112 msgs=10 reasoning_chars=0 sent=0 visible_chars=7259 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 06  in=8069 out=2076 reasoning_tok=0 cum_in=19367 cum_out=2188 msgs=12 reasoning_chars=0 sent=0 visible_chars=18395 gen_chars=4559+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 07  in=10149 out=23 reasoning_tok=0 cum_in=29516 cum_out=2211 msgs=14 reasoning_chars=0 sent=0 visible_chars=23014 gen_chars=0+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 08  in=10176 out=49 reasoning_tok=0 cum_in=39692 cum_out=2260 msgs=16 reasoning_chars=0 sent=0 visible_chars=23071 gen_chars=80+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 09  in=10574 out=55 reasoning_tok=0 cum_in=50266 cum_out=2315 msgs=18 reasoning_chars=0 sent=0 visible_chars=24008 gen_chars=111+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 10  in=10699 out=165 reasoning_tok=0 cum_in=60965 cum_out=2480 msgs=20 reasoning_chars=0 sent=0 visible_chars=24385 gen_chars=568+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 11  in=10868 out=977 reasoning_tok=0 cum_in=71833 cum_out=3457 msgs=22 reasoning_chars=0 sent=0 visible_chars=25010 gen_chars=2994+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 12  in=11997 out=586 reasoning_tok=0 cum_in=83830 cum_out=4043 msgs=24 reasoning_chars=0 sent=0 visible_chars=28361 gen_chars=1814+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 13  in=12618 out=36 reasoning_tok=0 cum_in=96448 cum_out=4079 msgs=26 reasoning_chars=0 sent=0 visible_chars=30316 gen_chars=26+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 14  in=12699 out=2961 reasoning_tok=0 cum_in=109147 cum_out=7040 msgs=28 reasoning_chars=0 sent=0 visible_chars=30558 gen_chars=5021+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 15  in=15819 out=1367 reasoning_tok=0 cum_in=124966 cum_out=8407 msgs=30 reasoning_chars=0 sent=0 visible_chars=35935 gen_chars=2587+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 16  in=17229 out=759 reasoning_tok=0 cum_in=142195 cum_out=9166 msgs=32 reasoning_chars=0 sent=0 visible_chars=38659 gen_chars=2198+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[read_file]
  turn 17  in=18258 out=118 reasoning_tok=0 cum_in=160453 cum_out=9284 msgs=34 reasoning_chars=0 sent=0 visible_chars=41329 gen_chars=336+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 18  in=18380 out=2919 reasoning_tok=0 cum_in=178833 cum_out=12203 msgs=36 reasoning_chars=0 sent=0 visible_chars=41725 gen_chars=8994+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 19  in=21342 out=330 reasoning_tok=0 cum_in=200175 cum_out=12533 msgs=38 reasoning_chars=0 sent=0 visible_chars=50869 gen_chars=958+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[grep]
  turn 20  in=21716 out=5553 reasoning_tok=0 cum_in=221891 cum_out=18086 msgs=40 reasoning_chars=0 sent=0 visible_chars=51973 gen_chars=3688+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[write_ledger]
  turn 21  in=27569 out=35 reasoning_tok=0 cum_in=249460 cum_out=18121 msgs=42 reasoning_chars=0 sent=0 visible_chars=67976 gen_chars=118+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[run_beancount]
  turn 22  in=27616 out=394 reasoning_tok=0 cum_in=277076 cum_out=18515 msgs=44 reasoning_chars=0 sent=0 visible_chars=68128 gen_chars=1219+tool_args=? req_cap=8000 wire_cap=8000 provider_model=mistral-medium-3-5 finish=tool_calls trunc=False tools=[submit]

