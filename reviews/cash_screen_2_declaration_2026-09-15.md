# Cash-application screen 2 — declaration, written before any model call

**15 September 2026, 02:50 local, before the first request.** This note declares the second screen on
the generated development population, under the rulings of the review round of 15 September (round 19).
Nothing below may change once the first request is sent; a change is a new screen with a new selection
digest.

## The selection, frozen

`reviews/cash_screen_2_selection_2026-09-15.json`, self-digest
`2abd628c966480439e1a3a7bb11ac601b5ba79dd5d97bf30bb2ed6ff7ffea843`, written by
`docs/evaluation_pack/freeze_selection.py` from the population's own serving record
(`reviews/cash_application_development_population_2026-09-13_replacement/serving.json`, bound by sha256 in
the record), seed `cash-application-screen-2:2026-09-15`, four parent groups per mechanism stratum drawn
uniformly from the 32 eligible in each, both variants, execution order drawn: **24 cells**. Development
split only; the evaluation split stays closed.

Drawn groups: `ar-tenterhook` 8, 29, 30, 19; `cr-pikestaff` 13, 8, 9, 1; `fc-quarrymill` 26, 30, 14, 25.
**Overlap with screen 1's six groups (fc 4, 1; cr 6, 12; ar 22, 24): none.** Overlap was allowed and not
sought; the draw simply did not produce any.

The worlds are this evaluator's, minted under the production key and served from the family manifest at
its provisioned path (654,553 bytes, sha256 `3e29cd3fbeee1261…`, the identity the population record
publishes; re-hashed before this note and equal). The population's serving record carries no manifest
identity field, so the selection record says so and this note binds it instead.

## The two model records, frozen together

Same draw, same order, same arm; two separate records, never pooled.

| role | requested id | route |
|---|---|---|
| subject | `nvidia/nemotron-3-ultra-550b-a55b:free` | OpenRouter, `https://openrouter.ai/api/v1`, key variable `OPENROUTER_API_KEY` |
| comparator | `inclusionai/ling-3.0-flash-fin:free` | same |

Disclosures. Nemotron 3 Ultra and Super have earlier **bank-family** records in this repository
(`reviews/budget_nemotron-3-ultra-550b-a55b_2026-08-30.json`,
`reviews/generated_nemotron-3-super-120b-a12b_2026-09-01.md`); this is not a lineage new to the project,
only new to the cash-application family. Ling 3.0 Flash Fin is a **finance-oriented** model by its vendor's
description; nothing here establishes a specialisation in this accounting task. The comparator's generated
cells start only after the subject's are closed. Calendar separation and the served endpoints are recorded
on every row; differences between the two records are observations of served endpoints, not an isolated
effect of model architecture.

## The arm

From the selection record's `arm` block, and passed to the runner explicitly on every invocation:
per-turn cap 40,000 tokens (`--max-tokens`), episode ceiling 40,000 (`--max-total-completion-tokens`),
25 turns, reasoning replay on, temperature 0, top_p 1, no model seed, **request timeout 3,600 s** (a new
transport setting relative to screen 1's 180 s, declared here), `--retries 0` governing the pacing wrapper
and framework re-runs (one request per turn; SDK retries are fixed at 0 in the runner), provider label
`openrouter`, fresh context per episode, pacing interval the runner's default 6 s (recorded on every row).
The runner is the repository's `tests/measure_budget.py` at the commit that carries this note or later:
the 429 pacing loop is bounded by `--retries` there, and a `:free` model id no longer writes into an NTFS
alternate data stream.

## Protocol witnesses, declared

Before any generated cell, one full episode per endpoint on the authored task `cash_application_001`, under
the same arm, tagged `cash_screen_2_witness`, archived under its own rows file and **excluded from the
screen's denominator**. Acceptance is that the runner completes the tool-call and replay cycle and
preserves the artifacts and the disposition; **reward is not the criterion**. An accounting error in a
witness earns nothing and changes nothing. A demonstrated serialisation or instrumentation defect stops the
screen until it is repaired and a separately identified verification run has passed.

## Scheduling and the daily allowance

OpenRouter's free tier for this account (no purchased credits) is 50 requests a day and 20 a minute, and
failed requests count. One durable queue across nights, keyed by selection digest, model and ordinal:
witnesses first, then the subject's 24 cells in the frozen order, then the comparator's. A new episode is
launched only when at least 25 requests remain in the accounted allowance (rows finished today, start
records without a terminal row counted as 25 each, and every probe or other use written in a manual
ledger); at most four cells a night; the night stops at the first provider refusal. Up to twelve nights per
model are reserved; six is a best case. The comparator may end incomplete and is reported against 24.

A cell that meets a refusal is closed as attempted-unscored, with one exception: a documented **platform**
daily-limit rejection of the episode's **first** inference request, before any model response (HTTP 429 from
OpenRouter itself, status, error body, request id and rate-limit headers preserved on the row, exactly one
request sent, zero completion tokens), may be launched **once** more on a later night with the identical
selector, ordinal and arm; a second such rejection closes it. Anything ambiguous is not eligible. An item
with a start record and no terminal row is reported for a person and never relaunched by the scheduler.

## What this screen can and cannot say

Per-model dispositions against 24; the accounting-channel decompositions; paired comparisons where both
observations exist, with missing counterparts visible. The experimental units are twelve parent groups
represented by twenty-four variant episodes across three development templates. No pooling with screen 1;
no claim about unseen templates, training benefit, difficulty or general accounting competence.
