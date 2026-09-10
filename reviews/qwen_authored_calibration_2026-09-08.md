# Three Qwen endpoints on ten authored reconciliation tasks (2026-09-08, 14:22–15:27 local)

Research note, reviewed before publication: tables as recorded, interpretation limited to what
the records support. Companion note: `reviews/wa1b_screen_2026-09-08.md`.
Question (owner, 8 Sep): are the authored worlds easy, or were the four screen subjects simply strong? Zero-cost measurement: the same instrument on three smaller requested Qwen endpoints served by Alibaba Model Studio under Free Quota Only.

**Instrument.** Repository main 5c2a8a4 + db38dff with the uncommitted calibration-runner patch (tests/budget_calibration.py), launched with `--production` (no dev flag, no test secret; inherited environment variables not independently attested); the ten hand-authored `bank_recon_*` tasks — one per company-month, registry ids, no manifest needed — episode contract 3 (digest b16d726a…), 25 turns, episode ceiling 40,000 output tokens, pace 10 s, retries 2 for endpoint weather only. Per-turn cap 40,000 except qwen3-8b, whose route rejects `max_tokens` above 8,192 (`Range of max_tokens should be [1, 8192]`); its arm ran at 8,192 and is labelled so. Requested model IDs only; served checkpoints are not attested.

| world | qwen3-8b (8,192 / 40,000 cap/ceiling) | qwen3-30b-a3b-instruct-2507 (40,000 / 40,000 cap/ceiling) | qwen3.5-27b (40,000 / 40,000 cap/ceiling) |
|---|---|---|---|
| alpine-2025-11 (k=2) | 0.0 · 8 turns · 23,031 out · submitted | 0.183333 · 16 turns · 1,760 out · submitted | 1.0 · 10 turns · 2,962 out · submitted |
| ironwood-2025-10 | — provider 400: JSON tool arguments | 0.0 · 25 turns · 798 out · turn_cap_no_submit | 1.0 · 16 turns · 13,159 out · submitted |
| bluewater-2025-10 | — provider 400: JSON tool arguments | 0.0 · 25 turns · 1,073 out · turn_cap_no_submit | 1.0 · 13 turns · 14,211 out · submitted |
| silverbrook-2025-11 | — SDK validation: finish_reason 'null' | 0.55 · 12 turns · 4,558 out · submitted | 1.0 · 20 turns · 14,355 out · submitted |
| thistle-2026-01 | — provider 400: JSON tool arguments | 0.55 · 11 turns · 4,377 out · submitted | 1.0 · 14 turns · 5,064 out · submitted |
| oakridge-2026-03 | — provider 400: JSON tool arguments | 0.0 · 7 turns · 3,936 out · submitted | 1.0 · 9 turns · 6,253 out · submitted |
| hawthorn-2025-12 | 1.0 · 8 turns · 16,491 out · submitted | 0.275 · 9 turns · 4,323 out · submitted | 1.0 · 13 turns · 9,093 out · submitted |
| falcon-2026-02 | 0.0 · 5 turns · 22,322 out · submitted | 0.0 · 9 turns · 3,949 out · submitted | — quota exhausted (403) |
| redwood-2025-11 | 0.0 · 4 turns · 13,158 out · submitted | 0.275 · 10 turns · 3,957 out · submitted | — quota exhausted (403) |
| maple-2025-12 | — provider 400: JSON tool arguments | 0.0 · 14 turns · 4,618 out · submitted | — quota exhausted (403) |

| requested model ID | scored | mean reward (scored only) | reward 1.0 | reward 0.0 | lost | recorded tokens in / out, scored episodes only |
|---|---|---|---|---|---|---|
| qwen3-8b | 4/10 | 0.250 | 1 | 3 | 6 | 122,905 / 75,002 |
| qwen3-30b-a3b-instruct-2507 | 10/10 | 0.183 | 0 | 5 | 0 | 935,525 / 33,349 |
| qwen3.5-27b | 7/10 | 1.000 | 7 | 0 | 3 | 1,071,314 / 65,097 |

## Reading

**qwen3.5-27b:** All seven scored episodes submitted with reward 1.0; the remaining three attempts encountered quota-exhaustion errors. This is a ceiling result for those seven tasks and that requested endpoint under the recorded settings. It does not establish a threshold for other models.

**qwen3-30b-a3b-instruct-2507:** All ten episodes were scored, with mean reward 0.1833333 and no reward-1.0 outcome. Five submitted episodes received positive partial reward, three submitted episodes received zero, and two reached the turn cap without submission or an accepted ledger revision. These summary records do not establish the exact sequence of attempted actions or the accounting cause of each failure.

**qwen3-8b, per-turn cap 8,192:** Four episodes were scored: Hawthorn received 1.0 and three received zero. Five further episodes ended with provider errors concerning JSON tool arguments; one ended with SDK validation failure on response metadata (`finish_reason` returned as the literal string `'null'`). The scored-only mean of 0.25 describes four surviving episodes, not the ten-task battery. One observed success establishes feasibility on that case, not population-wide reachability or reliability.

These measurements show endpoint-specific differences on authored reconciliation tasks. They do not isolate model size, establish equivalence with the WA screen, or demonstrate learning benefit. The development decision remains a bounded clean-month assurance pack followed by an allocation prototype.

The requested `qwen3-30b-a3b-instruct-2507` endpoint produced five zero rewards and five positive partial rewards across ten authored tasks, with no reward-1.0 episode. The battery therefore yielded nonconstant terminal rewards for this policy under the recorded settings. Training utility has not been tested.

## Instrument defect surfaced by the five 400s

The pinned framework catches malformed tool-argument JSON and answers the model with the environment's `PUBLIC_TOOL_ERROR` (verifiers `tool_env.py`, `error_formatter`), but its client then re-serialises the original `tool_call.arguments` verbatim into the next request (`openai_chat_completions_client.py`, `from_chat_message`), so a provider that validates arguments refuses the whole conversation from then on. The episode is lost as a provider failure rather than continued. Review ruled this a shared instrument defect, to be fixed under episode contract 4 (provider-valid replay of rejected calls, raw call retained in the audit record, bounded feedback, ordinary budgets charged, `candidate/1` unchanged) before further measurements. The five lost 8B rows are not converted to reward 0; the archive lacks the raw offending responses.

## Related measurements

- The abandoned first qwen3-8b launch at the common 40k cap: its JSON holds five rows (alpine … thistle), each a 400 for an unsupported `max_tokens`; the log shows one more rejection before the restart. No model output was recorded. Archived as `small_qwen3-8b_cap40k_aborted.json`.
- Historical ten-task ceiling batteries under the previous instrument (episode contract 2, 7 Sep, operator scratch archive `dense/ceiling_*.json`, not in the repository, requested IDs): minimax/minimax-m3:free 10/10 at 1.0; qwen3.8-max 8/10; qwen3.8-flash 8 of 8 scored (2 lost); qwen3.7-plus 7/10; qwen-3.8-27b on Cerebras 4/10 at 1.0 (mean 0.535); kimi-k3 1 scored (9 lost). Different digest and prompt; retained as measurements of their own instrument, not comparable cell for cell with today's rows.
- The wa1b/screen-1 subjects ran on four company-months with constructed control/treatment variants, not this ten-task battery; no equivalence is claimed.

## Limitations

Ten tasks, one episode each, no repeated sampling of any task; three requested endpoints of one vendor family, differing in generation, architecture (the 30B-A3B is 30.5B total / 3.3B active, non-thinking; the 27B is dense and supports thinking) and serving behaviour, so differences are not attributable to size; the 8B arm at a different per-turn cap; quota cut the 27B at seven; lost episodes carry no usage totals. Zero charges reported by the operator under Free Quota Only; a quota-exhaustion 403 does not audit the whole run's charges. API usage (27B: 1,136,411 recorded tokens) is not reconciled against the account's quota accounting.

## Records

`reviews/qwen_authored_calibration_2026-09-08/`: the three result JSONs (rows carry per-turn cap, ceiling, route, tokens, stop reason, workspace path), the aborted 40k qwen3-8b JSON, and the three logs. Launch settings are in this note; the calibration patch is the uncommitted diff of tests/budget_calibration.py at the time of the run.
