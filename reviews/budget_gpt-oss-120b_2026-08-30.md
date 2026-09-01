# Token budget — openai/gpt-oss-120b, 2026-08-30

Budget: 50,000 tokens, 25 turns a rollout (PLAN §6). One rollout per selector.

| selector | reward | turns | tokens in | tokens out | total | over budget | stop | tools |
|---|---|---|---|---|---|---|---|---|
| train:1 | 0.0 | 7.0 | 32860.0 | 5779.0 | 38639 | no | no_tools_called | 6 NO write |
| train:12 | 0.0 | 6.0 | 16026.0 | 555.0 | 16581 | no | no_tools_called | 5 NO write |
| train:30 | 0.0 | 5.0 | 6225.0 | 181.0 | 6406 | no | no_tools_called | 4 NO write |

- total tokens: median 16,581, max 38,639, over budget 0/3
- turns: median 6, max 7.0
- reward: mean 0.000 over 3 scored, 0 at 1.0
- tool calls over all rollouts: {'read_file': 10, 'list_files': 3, 'grep': 2}
