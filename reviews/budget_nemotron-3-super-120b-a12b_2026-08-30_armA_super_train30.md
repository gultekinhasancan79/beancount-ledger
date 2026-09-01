# Token budget — nvidia/nemotron-3-super-120b-a12b, 2026-08-30_armA_super_train30

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.

| selector | reward | turns | tokens in | tokens out | total | over budget | stop | tools |
|---|---|---|---|---|---|---|---|---|
| train:30 | 0.0 | 25.0 | 478810.0 | 45792.0 | 524602 | **yes** | piv_turn_cap_no_submit (truncated) | 22 NO write |

- total tokens: median 524,602, max 524,602, over budget 1/1
- turns: median 25, max 25.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 15, 'grep': 6, 'list_files': 1}
