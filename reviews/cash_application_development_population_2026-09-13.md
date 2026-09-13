# Cash-application development population — MINTING CENSUS AND SERVING EVIDENCE (2026-09-13)

Offline engineering record. **No model was called.** Nothing in this note describes a model, a
score, a difficulty or a training effect, and nothing in it may be cited as evidence of one.

Round 16, decision 5 puts three things before the first measurement: freeze the generator, profile,
catalogue, admission contract and runtime; predeclare 96 development parent groups, 32 per mechanism
stratum, and retain their complete minting census; complete offline validation and signed-manifest
serving checks. This is the record of those three. The first measurement is a separate, later step
with its own frozen rule, and the evaluation split stays unopened.

**What this establishes:** that the generator produces admissible fresh instances under the frozen
specification, and that they serve through the production door exactly as the eleven authored
cash-application tasks do. **What it does not establish:** that the instances are hard, that they
are useful for training, or that any model has been measured on them. No complete screen, no
performance finding, no accreditation.

## The freeze

Frozen before the first group was drawn; freeze digest **`96322c398c8b2fc832ccd368e69e8fa1`**
(`freeze.json`). The declared half is pinned as literals in
`beancount_ledger/graph/cash_population.py` and compared against the live modules by
`tests/test_cash_population.py`, which also moves each declaration in turn to witness that the
comparison can fail.

| what | frozen at |
|---|---|
| family / family generator version | `cash_application` / `1` |
| construction, template, gate implementation | `1` / `1` / `1` |
| profile | `bounded-v1`, digest `310e96729061410467f0e4285976743f` |
| baseline catalogue | `cash_application_baselines/1`, 9 binding + 1 diagnostic |
| admission contract | family manifest schema `1`, preflight contract `1`, 31 gates, gate-set digest `6b246422badd05a6` |
| split map | schema `1`, digest `c41f5d150aec53ccce514f7123206ac5`, structure schema `1` |
| bounds | 64 deterministic attempts per parent pair, 256-reading enumeration bound |

Three digests are **runtime-scoped and recorded rather than pinned**: the baseline catalogue's
digest (`b7fa69753bcf1f5e732968f2819696a4`) binds compiled predicate bytecode; the semantic
components bind the shipped parser's own source digest; the runtime scope names the Unicode database
(`15.0.0`) and the native runtime (CPython 3.12.12, Windows/AMD64). A literal pin on any of them
would report a recompile as a change. `cash_manifest.admit` re-reads all three at the serving door
rather than trusting a record's copy, which is where that comparison belongs.

## The declared population

`cash-application-development-1`: **96 parent groups, 32 per mechanism stratum**, every one of them
in the `development` split, declared in a fixed order before any draw. Membership is a function of
the frozen split map alone — no secret, no sampling, no property of what a group drew. The evaluator
secret enters one layer down, at `parent_seed`, and decides what each declared identity draws, never
which identities exist.

The evaluation split is not opened, and it is not opened by the **absence of a roster entry** rather
than by a prohibition: `fc-harrowfield`, `cr-oysterbank` and `ar-coldharbour` are sealed into
`evaluation`, no released population declares them, and so no selector spells them. The door refuses
them as undeclared members.

## Minting census — 96 groups, 104 attempts, 0 exhausted

Run 2026-09-13 under the evaluator's provisioned key, rotation `142c75fa…`, 138 s.
Complete per-attempt census in `census.json`; aggregates in `aggregates.json`.

| stratum | template family | groups | admitted | exhausted | attempts | accepted | attempt acceptance | attempts / admitted group |
|---|---|---|---|---|---|---|---|---|
| `fallback_continuation` | `fc-quarrymill` | 32 | 32 | 0 | 36 | 32 | 0.889 | 1.125 |
| `credit_residue` | `cr-pikestaff` | 32 | 32 | 0 | 36 | 32 | 0.889 | 1.125 |
| `advice_residue` | `ar-tenterhook` | 32 | 32 | 0 | 32 | 32 | 1.000 | 1.000 |
| **all** | three families | **96** | **96** | **0** | **104** | **96** | **0.923** | **1.083** |

Group acceptance 96/96 = 1.000. Rejection distribution, all eight refusals, per stratum:

| stratum | code | n | stage | what the witness says |
|---|---|---|---|---|
| `fallback_continuation` | `DRAW-LAYOUT-REFUSED` | 4 | draw | 2× the carried invoices did not draw distinct dates before the period; 2× the shortfall would empty the last named invoice |
| `credit_residue` | `ACC-CUMULATIVE-REVERSAL-BOUNDED` | 2 | gate | the notes against one sale reverse more than its opening balance (2,332.00 against 2,173.00; 2,415.00 against 2,362.50) |
| `credit_residue` | `DRAW-LAYOUT-REFUSED` | 1 | draw | the carried invoices did not draw distinct dates before the period |
| `credit_residue` | `RENDER-POSTING-COLLISION` | 1 | render | two planted items share the postings `('Assets:AR', '-3186')`, which `candidate/1` would label a merged entry |
| `advice_residue` | — | 0 | — | every declared group was admitted on its first attempt |

Every attempt retains decision 3's nine fields — ordinal, stage, outcome, evaluated rejection codes,
witness, relevant baseline, reading counts, component versions and content digests where rendering
succeeded. 196 content digests were recorded across the 104 attempts (192 admitted variants plus the
four variants of the two gate-refused attempts); all 196 are distinct. Every attempt was evaluated
under one component digest, `41733838b2873d06`.

Gate (o): the nine binding baselines and the one diagnostic were observed on both variants of every
attempt — 1,960 (variant, baseline) observations. **No binding baseline reached a truth**, so no
attempt carries a baseline witness. The largest enumeration was 4 readings (`amount_only`); the
256-reading bound was never approached and **no `VERIFICATION-LIMIT` rejection was recorded**.
`number_order` stayed diagnostic and was recorded on every attempt.

## Offline validation — 192/192 variants

`validation.json`. Each of the 96 admitted groups' two variants, on the artifacts themselves, with
no manifest in the picture:

| gate | result |
|---|---|
| all 31 phase-C gates pass | 192/192 |
| public fold reproduces the private truth register | 192/192 |
| identifiability checker returns exactly **one** reading | 192/192 |
| golden ledger scores `1.000000`, complete, through the frozen `candidate/1` | 192/192 |
| golden register scores `1.000000` with no penalty, through `application/1` | 192/192 |
| `composite/1` over the two is `1.000000` and complete | 192/192 |
| no private construction token on any public surface | 192/192 |

## Serving — 192/192 records, exactly as the authored tasks

The 192 records were signed into the family manifest
(`~/.piv/cash_application_manifest.json`, 654,553 bytes, sha256 `6207c5d4173bed86…`) and then every
one of them was served through the real `beancount_ledger.load_environment`, with the manifest as the
only door — this family has no development bypass. The comparison is made against
`cash_application_001` itself rather than against a literal, so a contract change moves both sides:

| claim | result |
|---|---|
| the door admits the selector at all | 192/192 |
| the served public id is the one the record was signed for | 192/192 |
| the episode profile is `cash_application` | 192/192 |
| the served episode-contract digest equals the authored task's `b11bc1acf02b7e08…` | 192/192 |

The selector (`cash_application:<population>:<family>:<index>:<variant>`) is evaluator-side and
carries private tokens. It never reaches an agent: the dataset row, the prompt and every tool reply
carry only the keyed public id, and the suite asserts the selector appears in neither.

## What was generated

Structural measurements. They describe what was generated; they are not a difficulty, and "harder
for model X" cannot be assigned from an invoice count.

| stratum | customers | invoices (raised in period) | receipts | notes | plants | max alloc / receipt | depth | unpaid in-period | golden ledger bytes | register bytes |
|---|---|---|---|---|---|---|---|---|---|---|
| `fallback_continuation` | 3 | 12 (3) | 4 | 1 | 2 | 3 | 2 | 2–3 | 3,968–4,011 | 3,935–4,042 |
| `credit_residue` | 3 | 11 (3) | 4 | 1 | 2 | 2 | 2 | 3 | 3,953–4,003 | 3,562–3,617 |
| `advice_residue` | 3 | 12 (3) | 4 | 1 | 2 | 2 | 2 | 3 | 4,170–4,223 | 3,847–3,888 |

One calendar month and USD throughout, inside every `bounded-v1` bound (golden ledger ≤ 24,000
bytes, register ≤ 8,000). Both polarities are present in every stratum in exactly equal numbers —
32 positive and 32 negative variants each — so "always report a residue" is not a winning habit, and
which variant letter carries the positive condition is a keyed coin rather than a fixed assignment.

## Limitations

1. **No model has been measured on this population.** Every number above is offline and
   deterministic. This note supports no performance, difficulty or training claim of any kind.
2. **Admissibility is not difficulty.** Gate (o) searches for resistance to ten *declared* shortcut
   strategies. The authored cases already defeat those while usually being solved by a measured
   subject, so "no binding baseline reaches the truth" says the shortcuts do not work — not that the
   task is hard.
3. **96 groups, three structural templates.** One development family per mechanism stratum is what
   the frozen 60/20/20 map seals, so the 96 groups are 32 company-months each of `fc-quarrymill`,
   `cr-pikestaff` and `ar-tenterhook`. Within a stratum the customer, invoice, receipt, note, plant,
   allocation and dependency counts are therefore **constant**; what varies is the money, the dates,
   the names, the allocation pattern and the polarity. **96 rows are not 96 independent structural
   examples**, and any later sample drawn from here inherits that clustering.
4. **The acceptance rate is a property of this specification and this secret.** 0.923 per attempt
   with zero exhaustions says the frozen construction usually satisfies its own gates on the first
   draw. It is not an estimate for another profile, another template roster or another key: the same
   96 identities under a different evaluator secret draw different worlds and would produce a
   different census.
5. **Reproducible only by the evaluator.** The population is a public declaration, but what each
   identity draws is keyed. A third party holding this note cannot regenerate the census; they can
   check the declaration, the freeze and the code.
6. **Two runtime-scoped digests are recorded, not pinned**, for the reason given above. A record
   preflighted under Unicode 15.0.0 is refused at the serving door on a runtime reporting anything
   else, by design; re-preflight rather than assume the declared views carry over.
7. **Serving reconstructs the world, and reconstruction runs the admission battery.** The construction
   path fails closed if `tests/world_checks.py` cannot be located, and the wheel deliberately ships
   no tests. Generated cash-application instances therefore serve from a repository checkout and not
   from the published 0.2.0 wheel, which contains no cash-application generation at all.
8. **The census is evaluator-side.** It binds enumerable selectors to public-content digests. It
   belongs beside the manifest and this note; it is not an agent-visible surface and must not become
   one.
9. **The measured neighbours were checked, not assumed.** The 95 legacy tasks' and the eleven
   authored cash tasks' public bytes are byte-identical before and after this phase (rolled
   `dbac991578fcc6292af8d547c335e648c068d1d8320c538001dd9cc9cb500f0b` over all 106), `GENERATOR_VERSION`
   is 9, and the bank family's manifest, its census and `~/.piv/key_id` are untouched. The only file
   this phase wrote outside the repository is the new
   `~/.piv/cash_application_manifest.json`.

## Reproducing this record

```
python tests/preflight_cash_population.py --record reviews/cash_application_development_population_2026-09-13
```

Runs both phases under the evaluator's provisioned key and rewrites the five artifacts in
`reviews/cash_application_development_population_2026-09-13/`. `--per-stratum N` mints a bounded
stratified prefix instead; `--out PATH` writes the family manifest elsewhere. It exits 1 if the
freeze has moved, if any group is exhausted, if any variant fails offline validation, or if any
signed record is refused at the serving door. The standard battery's `test_cash_population` suite
runs the same machinery on one group per stratum, under its own secret and its own temporary
manifest, and touches neither the evaluator's key nor this record.

## Files

- `freeze.json` — the freeze, declared and runtime-scoped halves, under one digest
- `census.json` — the complete minting census: 96 groups, 104 attempts, every retained field
- `aggregates.json` — acceptance rates, exhaustion counts and rejection distributions, overall and per stratum
- `validation.json` — the seven offline validation gates and the recorded scores for all 192 variants
- `serving.json` — the 192 serving rows against the authored reference's episode contract
