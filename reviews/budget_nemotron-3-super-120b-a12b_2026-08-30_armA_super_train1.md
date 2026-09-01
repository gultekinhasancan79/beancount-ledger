# Token budget — nvidia/nemotron-3-super-120b-a12b, 2026-08-30_armA_super_train1

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.

| selector | reward | turns | tokens in | tokens out | total | over budget | stop | tools |
|---|---|---|---|---|---|---|---|---|
| train:1 | 0.0 | 25.0 | 592577.0 | 31846.0 | 624423 | **yes** | piv_turn_cap_no_submit (truncated) | 24 incl. write_ledger |

- total tokens: median 624,423, max 624,423, over budget 1/1
- turns: median 25, max 25.0
- reward: mean 0.000 over 1 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 20, 'list_files': 1, 'grep': 1, 'run_beancount': 1, 'write_ledger': 1}
