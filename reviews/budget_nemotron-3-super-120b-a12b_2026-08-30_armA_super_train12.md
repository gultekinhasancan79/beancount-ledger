# Token budget — nvidia/nemotron-3-super-120b-a12b, 2026-08-30_armA_super_train12

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.

| selector | reward | turns | tokens in | tokens out | total | over budget | stop | tools |
|---|---|---|---|---|---|---|---|---|
| train:12 | 0.0 | 14.0 | 199303.0 | 37830.0 | 237133 | **yes** | piv_submitted (truncated) | 12 incl. write_ledger |

- total tokens: median 237,133, max 237,133, over budget 1/1
- turns: median 14, max 14.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 6, 'run_beancount': 2, 'list_files': 1, 'grep': 1, 'write_ledger': 1, 'submit': 1}
