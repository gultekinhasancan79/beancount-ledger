# Submission texts (drafts — the user pastes these)

## 1) GitHub repository description (one line)

> Deterministic-reward RL environment for bank reconciliation on Beancount ledgers — keyed generative task population, exploit-hardened scorer, sealed fixed-panel evaluation. Built on Prime Intellect's `verifiers`.

## 2) Discord #verifiers pitch (post as-is; English; keep the no-DM rule)

> Hi all — we've published **beancount-ledger** on the Hub: a multi-turn tool-use environment where the agent does real double-entry bookkeeping — bank reconciliation and month-end close on a Beancount ledger — with a **fully deterministic reward** (no LLM judge anywhere).
>
> What makes it different from a benchmark port:
> - **Generative, keyed population** — worlds derive from an HMAC under an evaluator secret; a signed manifest gates production serving. 1,400 preflighted tasks released under our key; anyone can mint their own population under theirs. No golden-ledger files ship, and exact released generated worlds cannot be regenerated from public selector provenance without the evaluator secret.
> - **Exploit-hardened**: an adversarial corpus (12 families) scored against an independent semantic-entitlement oracle; 2,100-seed generator sweeps; a 330-world checker-vs-scorer differential — all zero-gap at release.
> - **Measured, not just shipped**: a sealed, preregistered 4-model × 6-task × 3-arm × 2-replicate experiment (138 valid rollouts). Delivery ranges 0–17% for small open models to 58–92% for stronger ones — a capability-sensitive, non-degenerate performance spread with substantial distance from perfect delivery. One fixed-panel observation: on devstral-2512, **not replaying prior-turn reasoning** improved correct delivery (+0.36; preregistered bootstrap interval excludes zero on this fixed panel) at ~0.53× tokens per correct delivery.
> - Episode contract, replay policy and tool schemas are digest-bound; the whole evidence chain (pre-registration, sealed schedule, rendered tables) ships in the repo.
>
> Hub: <HUB-LINK>  ·  Source: <GITHUB-LINK>
> There's no bookkeeping/accounting environment on the bounty sheet — this fills that category. We'd love a look from the team re: the "environments without a listed figure — ask" route. Feedback welcome!

## 3) Typeform (application-only) — suggested answers

**What do you want to build / what have you built?**
> We have already built and shipped it: `beancount-ledger`, an original RL environment for agentic double-entry bookkeeping (bank reconciliation + month-end close) with a deterministic scorer. It is live on the Hub with full source. Rather than porting an existing benchmark, it fills a category the Hub currently lacks: real accounting with machine-checkable ground truth.

**Scope / what's inside:**
> Six-tool multi-turn episode contract (read/grep/check/write/submit) with disclosed turn+token budgets; a generative world graph that plants omissions, alterations and duplicates and derives everything public from one fact graph; HMAC-keyed task population with signed-manifest production serving (1,400 tasks preflighted 1400/1400 under our key; operators mint their own); an exploit corpus scored by an independent semantic-entitlement oracle (zero gaps at release); and a sealed, preregistered measurement across 4 open-weight models × 6 tasks × 3 episode-contract arms (138 valid rollouts) demonstrating a capability-sensitive, non-degenerate reward signal and a concrete trainer-knob finding on reasoning-replay policy.

**Why us:**
> Fleet AI production experience building agentic evaluation/verification systems; this environment went through a 50+-turn adversarial design-review loop with every reward claim tied to a named oracle. Evidence chain (pre-registration, sealed experiment contract, rendered tables, audit trail) is in the repo.

**Ask:**
> The bounty sheet has no accounting/bookkeeping entry; per the program note ("if an environment doesn't have a listed figure, ask"), we'd like this assessed on the difficulty scale as an application-only contribution.

## 4) Hub environment description (short)

> Bank reconciliation and month-end close on a Beancount ledger. Deterministic reward: parse-gated, component-scored, penalty-checked — no LLM judge. Generative keyed task population (mint your own under your secret); one hand-authored task works with zero setup. Exploit-hardened and evidence-backed: see README for the sealed fixed-panel evaluation.

---
*Fill `<HUB-LINK>`/`<GITHUB-LINK>` at publish time. Keep all statistics in their softened (preregistered-bootstrap) phrasing — do not reintroduce "significant".*
