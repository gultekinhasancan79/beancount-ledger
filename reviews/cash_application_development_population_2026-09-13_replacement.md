# Cash-application development population — REPLACEMENT MINTING CENSUS AND SERVING EVIDENCE (2026-09-13)

Offline engineering record. **No model was called.** Nothing in this note describes a model, a
score, a difficulty or a training effect, and nothing in it may be cited as evidence of one.

> **This record supersedes
> [`cash_application_development_population_2026-09-13.md`](cash_application_development_population_2026-09-13.md)
> and the population it censused, `cash-application-development-1`.** That note and its five JSON
> files are preserved unaltered as the historical artifact of the rule they were minted under; only
> a supersession banner was added to the note itself. This record's population is
> **`cash-application-development-2`**.

## Why there is a replacement

Round 17, decision 4 found one of the thirty-one admission conditions wrong.
`cumulative_reversal_bounded` checked that a credit note did not reverse more than the **original
sale** it names — which is correct — and then **additionally** rejected any note whose gross
exceeded the invoice's **opening balance**, the amount still owing when the period began.

That second clause was not the intended specification. A credit reverses a sale; the customer having
already part-paid that sale does not shrink what may be credited against it, because the money
already received becomes a refund or an overpayment to apply elsewhere. The accounting correction
says so in terms — *"Do not cap the credit at the unpaid balance"* — and `cash_construct`'s own
constructor was always built on the same rule: *"The bound is the original sale, never the unpaid
balance."* It is also the rule that makes the shipped Bowline case 5 legitimate: SI-3100 is a
1,080.00 sale showing 300.00 open, and CN-0412 credits 540.00 against it.

The cap is removed; the original-sale net and tax constraints, the note's cumulative reach across
several notes against one sale, and the positive-net requirement are retained. The corrected
semantics are versioned: `GATE_VERSION` 2, family preflight contract 2, gate-set digest off
`6b246422badd05a6` and onto `2491e97f97b48cee`.

**Why that forces a new population rather than a re-run.** The 2026-09-13 population was *selected*
under the incorrect restriction. Passing an additional, wrong accounting restriction cannot establish
conformity to the intended specification, whatever the accepted instances themselves look like — the
finding is about the selection rule, not about the 192 goldens that survived it. Decision 4's
instruction is therefore to **declare a replacement population**, and the identifier is part of the
construction identity: because the population name enters `parent_seed`, a new name is a new draw.
`cash-application-development-2` is 96 different company-months over the same 96 declared
(family, index) slots, admitted under contract 2 **from the first attempt onward**. A re-mint under
the old name would have inherited attempt ordinals the corrected rule no longer produces.

`cash-application-development-1` is retired from `RELEASED_POPULATIONS` and recorded in
`SUPERSEDED_POPULATIONS` with its reason. No selector spells it any more, so nothing can be served
under it; its record stays, because a record is history, not a roster.

## The freeze

Frozen before the first group was drawn; freeze digest **`b371a45a0186648e40c7aa18f03efb28`**
(`freeze.json`, `problems: []`, `declared_matches_live: true`). The declared half is pinned as
literals in `beancount_ledger/graph/cash_population.py` and compared against the live modules by
`tests/test_cash_population.py`, which also moves each declaration in turn to witness that the
comparison can fail.

| what | frozen at | moved since 2026-09-13? |
|---|---|---|
| **development population** | **`cash-application-development-2`** | **yes** — was `cash-application-development-1` |
| **superseded populations** | **`cash-application-development-1`** | **yes** — new key |
| family / family generator version | `cash_application` / `1` | no |
| construction, template versions | `1` / `1` | no |
| **gate implementation version** | **`2`** | **yes** — was `1` |
| profile | `bounded-v1`, digest `310e96729061410467f0e4285976743f` | no |
| baseline catalogue | `cash_application_baselines/1`, 9 binding + 1 diagnostic | no |
| **admission contract** | family manifest schema `1`, **preflight contract `2`**, 31 gates, **gate-set digest `2491e97f97b48cee`** | **yes** — was contract `1`, digest `6b246422badd05a6` |
| split map | schema `1`, digest `c41f5d150aec53ccce514f7123206ac5`, structure schema `1` | no |
| bounds | 64 deterministic attempts per parent pair, 256-reading enumeration bound | no |

The gate kept its name and its group, so `gate_set_digest()` — which never sees a predicate's body —
could not have noticed the change on its own. The contract bump is what carries it, and
`tests/test_cash_gate.py` witnesses that directly: restoring contract 1 restores the superseded
digest exactly.

The population identifier is pinned as a **literal string**, not as `DEVELOPMENT_POPULATION`. A
declaration that read the constant it is meant to pin would agree with every future value of it, and
the identifier moving is the very thing this phase had to do deliberately.

Three digests remain **runtime-scoped and recorded rather than pinned**: the baseline catalogue's
digest (`b7fa69753bcf1f5e732968f2819696a4`) binds compiled predicate bytecode; the semantic
components bind the shipped parser's own source digest (`623ebaf29e32250d…`); the runtime scope names
the Unicode database (`15.0.0`) and the native runtime (CPython 3.12.12, Windows/AMD64). A literal
pin on any of them would report a recompile as a change. `cash_manifest.admit` re-reads all three at
the serving door rather than trusting a record's copy.

## The declared population

`cash-application-development-2`: **96 parent groups, 32 per mechanism stratum**, every one of them
in the `development` split, declared in a fixed order before any draw. Membership is a function of
the frozen split map alone — no secret, no sampling, no property of what a group drew, and no
property of what the superseded population drew. The evaluator secret enters one layer down, at
`parent_seed`, and decides what each declared identity draws, never which identities exist.

The evaluation split is not opened, and it is not opened by the **absence of a roster entry** rather
than by a prohibition: `fc-harrowfield`, `cr-oysterbank` and `ar-coldharbour` are sealed into
`evaluation`, no released population declares them, and so no selector spells them. The door refuses
them as undeclared members. The same mechanism now refuses the superseded population.

## Minting census — 96 groups, 98 attempts, 0 exhausted

Run 2026-09-13 under the evaluator's provisioned key, rotation `142c75fa…`, 437 s.
Complete per-attempt census in `census.json`; aggregates in `aggregates.json`.

| stratum | template family | groups | admitted | exhausted | attempts | accepted | attempt acceptance | attempts / admitted group |
|---|---|---|---|---|---|---|---|---|
| `fallback_continuation` | `fc-quarrymill` | 32 | 32 | 0 | 34 | 32 | 0.941 | 1.063 |
| `credit_residue` | `cr-pikestaff` | 32 | 32 | 0 | 32 | 32 | 1.000 | 1.000 |
| `advice_residue` | `ar-tenterhook` | 32 | 32 | 0 | 32 | 32 | 1.000 | 1.000 |
| **all** | three families | **96** | **96** | **0** | **98** | **96** | **0.980** | **1.021** |

Group acceptance 96/96 = 1.000. 94 groups were admitted on attempt ordinal 0 and two on ordinal 1.
Rejection distribution, both refusals, per stratum:

| stratum | code | n | stage | what the witness says |
|---|---|---|---|---|
| `fallback_continuation` | `DRAW-LAYOUT-REFUSED` | 2 | draw | 2× the shortfall would empty the last named invoice |
| `credit_residue` | — | 0 | — | every declared group was admitted on its first attempt |
| `advice_residue` | — | 0 | — | every declared group was admitted on its first attempt |

Every attempt retains decision 3's nine fields — ordinal, stage, outcome, evaluated rejection codes,
witness, relevant baseline, reading counts, component versions and content digests where rendering
succeeded. 192 content digests were recorded across the 98 attempts (the two refusals are draw-stage
and rendered nothing); all 192 are distinct. Every attempt was evaluated under one component digest,
`150d4adb66657dac`.

Gate (o): the nine binding baselines and the one diagnostic were observed on both variants of every
rendered attempt — 1,920 (variant, baseline) observations. **No binding baseline reached a truth**, so
no attempt carries a baseline witness. The largest enumeration was 2 readings (`amount_only`); the
256-reading bound was never approached and **no `VERIFICATION-LIMIT` rejection was recorded**.
`number_order` stayed diagnostic and was recorded on every rendered attempt.

## What changed in the census

Two comparisons, and they answer different questions. The populations are **different draws**, so the
aggregate comparison is distributional and not a paired one; the replay is the paired measurement.

**Aggregate, superseded vs replacement:**

| | 2026-09-13 (`…development-1`, contract 1) | this record (`…development-2`, contract 2) |
|---|---|---|
| declared groups | 96 | 96 |
| admitted groups | 96 | 96 |
| exhausted groups | 0 | 0 |
| attempts | 104 | **98** |
| attempt acceptance | 0.923 | **0.980** |
| attempts / admitted group | 1.083 | **1.021** |
| `ACC-CUMULATIVE-REVERSAL-BOUNDED` refusals | **2** | **0** |
| `DRAW-LAYOUT-REFUSED` refusals | 5 | 2 |
| `RENDER-POSTING-COLLISION` refusals | 1 | 0 |
| refusals at the **gate** stage | 2 | **0** |
| `credit_residue` attempts for 32 groups | 36 | **32** |
| component digest | `41733838b2873d06` | `150d4adb66657dac` |

The draw-stage and render-stage counts differ because the worlds differ; nothing should be read into
them. The line that carries the correction is the gate stage: **the replacement population records
zero accounting-gate refusals, and in particular zero opening-balance refusals, because that clause
no longer exists.**

**Paired replay — are candidates the old rule rejected now admitted? Yes: 2 of 2.**
(`superseded_rejections.json`.) The 2026-09-13 census recorded exactly two parent attempts refused
for `ACC-CUMULATIVE-REVERSAL-BOUNDED`, both in `cr-pikestaff/1` of the superseded population. The
gate appends every failing clause without short-circuiting, so a witness naming only an opening
balance is proof the original-sale bound had already passed — which is what made them identifiable as
false rejections. Both identities were reminted under the corrected contract:

| superseded group | attempt | under contract 1 | under contract 2 |
|---|---|---|---|
| `…/cr-pikestaff/1/0` | ordinal 0 | **refused** `ACC-CUMULATIVE-REVERSAL-BOUNDED` — *the notes against SI-6516 reverse 2,332.00 of an opening balance of 2,173.00* (variant a); *2,226.00 of 2,173.00* (variant b). Group admitted at ordinal 1. | **accepted**, no codes. Group admitted at ordinal 0. |
| `…/cr-pikestaff/1/3` | ordinal 0 | **refused** `ACC-CUMULATIVE-REVERSAL-BOUNDED` — *the notes against SI-3007 reverse 2,415.00 of an opening balance of 2,362.50* (variant b). Group admitted at ordinal 1. | **accepted**, no codes. Group admitted at ordinal 0. |

The replay reminted those two identities against a **fresh** population ledger, so the two
cross-group population gates saw one group rather than ninety-six; every other gate is the live one.
The replay is evidence about the rule, not a serving path: the superseded population stays retired
and none of its instances is signed into any manifest.

## Offline validation — 192/192 variants

`validation.json`. Each of the 96 admitted groups' two variants, on the artifacts themselves, with
no manifest in the picture:

| gate | result |
|---|---|
| all 31 phase-C gates pass (contract 2) | 192/192 |
| public fold reproduces the private truth register | 192/192 |
| identifiability checker returns exactly **one** reading | 192/192 |
| golden ledger scores `1.000000`, complete, through the frozen `candidate/1` | 192/192 |
| golden register scores `1.000000` with no penalty, through `application/1` | 192/192 |
| `composite/1` over the two is `1.000000` and complete | 192/192 |
| no private construction token on any public surface | 192/192 |

192 distinct public ids and 192 distinct public-content digests.

## Serving — 192/192 records, exactly as the authored tasks

The 192 records were signed into the family manifest
(`~/.piv/cash_application_manifest.json`, 654,553 bytes, sha256 `3e29cd3fbeee1261…`, rotation
`142c75fa…`, gate set `2491e97f97b48cee`, contract 2) and then every one of them was served through
the real `beancount_ledger.load_environment`, with the manifest as the only door — this family has no
development bypass. The comparison is made against `cash_application_001` itself rather than against
a literal, so a contract change moves both sides:

| claim | result |
|---|---|
| the door admits the selector at all | 192/192 |
| the served public id is the one the record was signed for | 192/192 |
| the episode profile is `cash_application` | 192/192 |
| the served episode-contract digest equals the authored task's `b11bc1acf02b7e08…` | 192/192 |

The manifest now holds **only** `cash-application-development-2` records; the superseded population's
192 signed records were replaced, and would in any case have been refused at the door, which re-reads
the live gate set and would find `2491e97f97b48cee` where the record says `6b246422badd05a6`.

The selector (`cash_application:<population>:<family>:<index>:<variant>`) is evaluator-side and
carries private tokens. It never reaches an agent: the dataset row, the prompt and every tool reply
carry only the keyed public id, and the suite asserts the selector appears in neither.

## What was generated

Structural measurements. They describe what was generated; they are not a difficulty, and "harder
for model X" cannot be assigned from an invoice count.

| stratum | customers | invoices (raised in period) | receipts | notes | plants | max alloc / receipt | depth | unpaid in-period | golden ledger bytes | register bytes |
|---|---|---|---|---|---|---|---|---|---|---|
| `fallback_continuation` | 3 | 12 (3) | 4 | 1 | 2 | 3 | 2 | 2–3 | 3,977–4,025 | 3,939–4,055 |
| `credit_residue` | 3 | 11 (3) | 4 | 1 | 2 | 2 | 2 | 3 | 3,953–3,993 | 3,567–3,606 |
| `advice_residue` | 3 | 12 (3) | 4 | 1 | 2 | 2 | 2 | 3 | 4,173–4,238 | 3,843–3,912 |

One calendar month and USD throughout, inside every `bounded-v1` bound (golden ledger ≤ 24,000
bytes, register ≤ 8,000). Both polarities are present in every stratum in exactly equal numbers —
32 positive and 32 negative variants each — so "always report a residue" is not a winning habit, and
which variant letter carries the positive condition is a keyed coin rather than a fixed assignment
(positives fall 15a/17b, 18a/14b and 13a/19b across the three strata).

## Limitations

> A versioned, keyed cash-application generator with a frozen development population, deterministic
> accounting checks, golden-artifact validation and signed-manifest serving under the recorded
> repository runtime. No model performance, difficulty, training benefit or generalization beyond the
> development templates has been established.

That is the whole of the claim this deliverable makes. The rest of this section is what stands behind
it and what does not.

1. **No model has been measured on this population.** Every number above is offline and
   deterministic. This note supports no performance, difficulty or training claim of any kind.
2. **The superseded population's evidence does not transfer.** Its 192 accepted goldens were not
   shown to be wrong, and this record makes no claim that they were. What was wrong was the
   *selection*: an additional, incorrect accounting restriction was applied, so passing it could not
   establish conformity to the intended specification. That is why the population was replaced rather
   than re-validated, and why no figure from the 2026-09-13 record is carried forward here.
3. **Admissibility is not difficulty.** Gate (o) searches for resistance to ten *declared* shortcut
   strategies. The authored cases already defeat those while usually being solved by a measured
   subject, so "no binding baseline reaches the truth" says the shortcuts do not work — not that the
   task is hard.
4. **96 groups, three structural templates.** One development family per mechanism stratum is what
   the frozen 60/20/20 map seals, so the 96 groups are 32 company-months each of `fc-quarrymill`,
   `cr-pikestaff` and `ar-tenterhook`. Within a stratum the customer, invoice, receipt, note, plant,
   allocation and dependency counts are therefore **constant**; what varies is the money, the dates,
   the names, the allocation pattern and the polarity. **96 rows are not 96 independent structural
   examples**, and any later sample drawn from here inherits that clustering.
5. **The acceptance rate is a property of this specification and this secret.** 0.980 per attempt
   with zero exhaustions says the corrected construction usually satisfies its own gates on the first
   draw. It is not an estimate for another profile, another template roster or another key, and the
   rise from 0.923 is **not** a measured effect of the correction: these are different worlds, and
   only two of the six fewer refusals are attributable to the removed clause.
6. **Reproducible only by the evaluator.** The population is a public declaration, but what each
   identity draws is keyed. A third party holding this note cannot regenerate the census; they can
   check the declaration, the freeze and the code.
7. **Two runtime-scoped digests are recorded, not pinned**, for the reason given above. A record
   preflighted under Unicode 15.0.0 is refused at the serving door on a runtime reporting anything
   else, by design; re-preflight rather than assume the declared views carry over.
8. **Serving reconstructs the world, and reconstruction runs the admission battery.** The construction
   path fails closed if `tests/world_checks.py` cannot be located, and the wheel deliberately ships
   no tests. Generated cash-application instances therefore serve from a repository checkout and not
   from the published 0.2.0 wheel, which contains no cash-application generation at all. Decision 4
   names this a delivery boundary and asks for the checker to move into the runtime package before any
   installable-release claim; **that work is not done here, and no installable-release claim is made.**

   > **UPDATE, later the same day (2026-09-13).** That work is now done, and the sentences above are
   > kept as the account of the run this record describes rather than rewritten. The battery moved to
   > `beancount_ledger/world_checks.py` (with `beancount_ledger/graph/repair_keys.py`), and
   > `tests/world_checks.py` is a shim binding the old name to that same module object — one
   > implementation, unchanged suite behaviour, `tests/` and `reviews/` still excluded from both
   > artifacts. An installed wheel in a clean throwaway virtual environment, with the repository
   > absent from `sys.path`, then MINTED one declared group per mechanism stratum of this very
   > population and served both variants of each through the real `env.evaluate()` door at reward
   > 1.0, `complete`, register `delivered`, composite 1 — six of six, with the battery recorded as
   > resolving from `site-packages` and shown able to fail on tampered inputs. The evidence is
   > `reviews/installable_serving_check_2026-09-13/`. **The numbers in THIS record were still taken
   > from a repository checkout**, and the wheel measured there is a build of the later tree, not the
   > published 0.2.0 Hub artifact.
9. **The census is evaluator-side.** It binds enumerable selectors to public-content digests. It
   belongs beside the manifest and this note; it is not an agent-visible surface and must not become
   one.
10. **The measured neighbours were checked, not assumed.** The 95 legacy tasks' and the eleven
    authored cash tasks' public bytes are byte-identical before and after this phase (rolled
    `dbac991578fcc6292af8d547c335e648c068d1d8320c538001dd9cc9cb500f0b` over all 106),
    `GENERATOR_VERSION` is 9, and the bank family's manifest, its census and `~/.piv/key_id` are
    untouched. The only file this phase wrote outside the repository is the rewritten
    `~/.piv/cash_application_manifest.json`.

## Released with 0.3.0 (2026-09-14)

Added on the day the generator was released, and additive: nothing above is rewritten.

This population is **distributed** in package version **0.3.0** and is described there, in
`README.md` and in `docs/REFERENCE.md`, as a **released development population**. The two words do
different jobs. **Released** describes distribution: the generator, this population's declaration
and the admission battery ship in the wheel, and a package installed from that wheel can mint a
declared group and serve both its variants — measured in
`reviews/installable_serving_check_2026-09-14/` against the 0.3.0 artifact itself. **Development**
describes this population's experimental role, and that role does not change by being distributed.

Specifically, and for the avoidance of doubt: **the split assignment stays exactly as it is**, all
96 declared groups remain in the `development` split, and **the evaluation split remains unopened** —
`fc-harrowfield`, `cr-oysterbank` and `ar-coldharbour` are still sealed into `evaluation`, still
declared by no released population, and still unspellable by any selector.

The correction ships under a NEW package version rather than as a rebuilt 0.2.0 wheel, so no
artifact built from the corrected tree can share the published 0.2.0 identity. Nothing was uploaded
to the Environments Hub here; publishing is the owner's act. Every number in this record still comes
from the repository-checkout run it describes.

## Reproducing this record

```
python tests/preflight_cash_population.py --record reviews/cash_application_development_population_2026-09-13_replacement
```

Runs both phases under the evaluator's provisioned key and rewrites five of the six artifacts in
`reviews/cash_application_development_population_2026-09-13_replacement/`. `--per-stratum N` mints a
bounded stratified prefix instead; `--out PATH` writes the family manifest elsewhere. It exits 1 if
the freeze has moved, if any group is exhausted, if any variant fails offline validation, or if any
signed record is refused at the serving door. The standard battery's `test_cash_population` suite
runs the same machinery on one group per stratum, under its own secret and its own temporary
manifest, and touches neither the evaluator's key nor this record.

`superseded_rejections.json` is the sixth artifact and is produced separately: it reads the 2026-09-13
census, remints every identity whose census recorded an `ACC-CUMULATIVE-REVERSAL-BOUNDED` refusal, and
reports what the corrected contract does with the same attempt ordinal.

## Files

- `freeze.json` — the freeze, declared and runtime-scoped halves, under one digest
- `census.json` — the complete minting census: 96 groups, 98 attempts, every retained field
- `aggregates.json` — acceptance rates, exhaustion counts and rejection distributions, overall and per stratum
- `validation.json` — the seven offline validation gates and the recorded scores for all 192 variants
- `serving.json` — the 192 serving rows against the authored reference's episode contract
- `superseded_rejections.json` — the paired replay of the two refusals the corrected rule overturns

## The superseded record

Preserved, unaltered except for a supersession banner on the note:

- [`cash_application_development_population_2026-09-13.md`](cash_application_development_population_2026-09-13.md)
- `cash_application_development_population_2026-09-13/` — `freeze.json`, `census.json`,
  `aggregates.json`, `validation.json`, `serving.json`, all byte-identical to the day they were
  minted. `tests/test_cash_gate.py` asserts that its `freeze.json` still declares gate version 1 and
  gate set `6b246422badd05a6`, so an edit to it fails the battery.
