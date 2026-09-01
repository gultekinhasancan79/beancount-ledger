# Token budget — nvidia/nemotron-3-ultra-550b-a55b, 2026-08-30_armA_train12

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.

| selector | reward | turns | tokens in | tokens out | total | over budget | stop | tools |
|---|---|---|---|---|---|---|---|---|
| train:12 | 1.0 | 7.0 | 58915.0 | 17444.0 | 76359 | **yes** | piv_submitted (truncated) | 12 incl. write_ledger |

- total tokens: median 76,359, max 76,359, over budget 1/1
- turns: median 7, max 7.0
- reward: mean 1.000 over 1 scored, 1 at 1.0
- tool calls over all rollouts: {'read_file': 8, 'list_files': 1, 'write_ledger': 1, 'run_beancount': 1, 'submit': 1}
