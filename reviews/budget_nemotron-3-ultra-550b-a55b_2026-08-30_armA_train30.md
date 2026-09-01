# Token budget — nvidia/nemotron-3-ultra-550b-a55b, 2026-08-30_armA_train30

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.

| selector | reward | turns | tokens in | tokens out | total | over budget | stop | tools |
|---|---|---|---|---|---|---|---|---|
| train:30 | 0.0 | 11.0 | 174634.0 | 21624.0 | 196258 | **yes** | piv_submitted (truncated) | 16 incl. write_ledger |

- total tokens: median 196,258, max 196,258, over budget 1/1
- turns: median 11, max 11.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 10, 'run_beancount': 3, 'list_files': 1, 'write_ledger': 1, 'submit': 1}
