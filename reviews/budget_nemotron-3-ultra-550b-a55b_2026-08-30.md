# Token budget — nvidia/nemotron-3-ultra-550b-a55b, 2026-08-30

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.

| selector | reward | turns | tokens in | tokens out | total | over budget | stop | tools |
|---|---|---|---|---|---|---|---|---|
| train:1 | 0.0 | 3.0 | 10299.0 | 8275.0 | 18574 | no | no_tools_called (truncated) | 9 NO write |
| train:12 | 0.0 | 3.0 | 10598.0 | 8421.0 | 19019 | no | no_tools_called (truncated) | 9 NO write |
| train:30 | 0.0 | 4.0 | 20398.0 | 8328.0 | 28726 | no | no_tools_called (truncated) | 9 NO write |

- total tokens: median 19,019, max 28,726, over budget 0/3
- turns: median 3, max 4.0
- reward: mean 0.000 over 3 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 24, 'list_files': 3}
