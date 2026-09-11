# Cold adjudication of the cash-application pack — result (2026-09-10, 20:28–20:37 local)

Research note, reviewed before publication; the numerical tables stand, and the claims were narrowed
to what the records support. Companion notes: `reviews/cash_application_screen_2026-09-10.md` (the
Bowline screen) and `reviews/cash_application_six_variant_screen_2026-09-11.md` (the six-variant
screen). **Neither this note nor either screen establishes a population failure rate, accounting
accreditation or a training benefit.**

Executes the rule written before any adjudicator was called
(`cash_application_adjudication_2026-09-10/predeclared.md`). Two adjudicators of different lineages,
neither the screens' subject: `qwen3.7-max` and `deepseek-v4-flash` on Alibaba Model Studio under
Free Quota Only, temperature 0, one call per case each, a 16,000-token cap. Each saw exactly the
eleven public files the agent sees and nothing else — no specification, no scoring code, no truth
register, no hint that a register is scored or that a unique answer exists. Ten calls, nine minutes,
44,755 input and 54,931 output tokens. Cost: zero dollars, operator-reported under Free Quota Only.

## What came back

| case | qwen3.7-max | deepseek-v4-flash |
|---|---|---|
| `cash_application_001` | pass | pass |
| `cash_application_002` | pass | pass |
| `cash_application_003` | one zero-amount line | pass |
| `cash_application_004` | pass | pass |
| `cash_application_005` | one zero-amount line | one zero-amount line |

**Every difference in the table is the same one difference.** Three of the ten answers listed the
withheld invoice `SI-3100` in the first receipt's applied set with an amount of `0.00`, alongside
the two applications that carry money. The remittance advice does name `SI-3100` on that receipt
with `amount_paid` 0.00 and the note "withheld", so the line is a faithful reading of the document.
No adjudicator, on any case, put money on a different invoice, split a receipt differently, applied
the credit note elsewhere, wrote off a different amount, or closed a different balance.

**The comparator was stricter than the shipped contract, and this is the discrepancy that produced
the two non-passing rows.** `application/1`'s `receipts_exact` channel is defined over the applied
multiset *with zero-amount advice lines excluded*. The normalisation is `_canonical_items`, applied
to every receipt's applied and written-off sets in `beancount_ledger/candidate/application.py`; it
has been in place since `03f19ed` on 2026-09-09 and is therefore **pre-existing**, not written in
response to these answers. The adjudication comparator did not exclude them.

Three readings follow from that, and all three are reported rather than one:

| Reading | Result |
|---|---|
| Comparator as executed | Seven passing answers; three cases passed by both models |
| Predeclared classification of the disagreements | Case 3 contested; Case 5 triggered **"both differ the same way"**, hence defective pending examination |
| Corrected comparison using the pre-existing zero normalisation | Ten agreeing answers; all five cases agreed by both models |

**The runner did not implement the full written classification rule, and that discrepancy is
preserved rather than papered over.** `cash_adjudicate.py` sorts every case that did not draw two
passes into a single bucket it prints as `contested`. The predeclared rule has four outcomes, not
two: *both pass*, *one passes one differs* (contested), *both differ the same way* (the authors are
probably wrong — defective, re-examine the evidence) and *both differ differently* (ambiguous —
defective). Case 3 is genuinely the second of those. Case 5, where both adjudicators produced the
**identical** zero-amount line, is the third, and under the rule as written it should have been
recorded as defective pending examination of the evidence — which is what the zero-line examination
above in fact is. The rule was not rewritten after the answers arrived; the runner executed a
coarser version of it, and the middle row of the table states what the written rule would have
returned.

The third row is not arithmetic in this note: `corrected_comparison.py` re-reads the archived
answers, imports `_canonical_items` **from the shipped package** rather than re-implementing it, and
prints both readings side by side with the predeclared rule's four outcomes. Its `as executed`
column reproduces every archived verdict line for line, which is what makes the two readings
comparable. The raw answers are archived so anyone can recount.

## What the adjudicators noticed unprompted

Nobody told them a discrepancy had been planted. They found the planted ledger errors anyway, from
the evidence, and said which document governs:

- Case 1: "The ledger records the 2026-04-28 receipt as 3702.00, but the bank statement and
  remittance advice show 3720.00. Cash application follows the bank statement and remittance advice
  per policy." DeepSeek added that the 21 April cheque for 2,970.00 is missing from the ledger
  altogether.
- Case 2: "The ledger records the 2026-04-28 receipt as 2310.00 USD, but the bank statement shows
  2130.00 USD… Applying 2130.00 in invoice-date order (oldest first) allocates 1830.00 to SI-3102
  and 300.00" — the policy rung this case exists to exercise.
- Case 3: "The write-off on SI-3104 for $20.00 is within the $25.00 threshold and the remittance
  advice marks the invoice settled, so it is written off. The $40.00 shortfall on SI-3102 exceeds
  $25.00, so it remains as an open balance." That is the tolerance rule, restated correctly on both
  sides of the line. It was **not** unexplained: the supplied `policy.md` states the 25.00
  threshold, the settled-advice precondition and what happens above the line, and the adjudicator
  read it there.
- Case 4: both spotted the transposed receipt (3,160.00 against the statement's 3,610.00).
- Case 5: both reported the 30.00 of unapplied cash. "The remittance advice for receipt
  GR PAYRUN 0428 totals only 3750 against the 3780 received; the unapplied 30.00 is left as an
  unapplied credit for Gannet Rigging Inc." **This is precisely the field the Bowline screen's
  subject omitted.**

## What this establishes, and what it does not

Across five authored Bowline variants, two requested model IDs reconstructed the specified
applications and closing balances from the public files, given an explicit JSON response schema and
completeness instructions. All ten parsed answers agree with the archived truth under the scorer's
pre-existing zero-application normalization. This supports the sufficiency and intelligibility of
the evidence for these readers on these cases. It does not prove that no alternative interpretation
exists, establish practitioner validity, or measure success in the agent's ledger-repair workflow.
The original comparator results and the subsequent normalization correction are reported separately.

**Agreement does not prove uniqueness**, and disagreement does not by itself prove ambiguity — the
zero-line discrepancy above demonstrates the second directly: two readers differed from the
comparator on a point where the pack was never ambiguous and the comparator was simply stricter than
the contract it was meant to stand for.

Does not establish: that these documents look like real remittances, that a firm would publish this
policy, that 25.00 is a sensible tolerance, or that the family is hard. Those are domain validity,
and a model's agreement is not domain validity. They remain open for a practising accountant,
exactly as declared before the run. It establishes no population failure rate, no accounting
accreditation and no training benefit.

Also worth saying plainly: both adjudicators are models used elsewhere in this project, and one of
them, `qwen3.7-max`, was a subject in an earlier wrong-account screen. Neither is the subject of the
cash-application screens and neither saw this family's design, but they are not independent of the
project's habits of phrasing.

## Records

`reviews/cash_application_adjudication_2026-09-10/` holds the archive:

- `predeclared.md` — the rule, dated before the run;
- `cash_adjudicate.py` — the runner as executed, with exactly two lines rewritten for publication
  (the pointer to the predeclared rule, and a `sys.path` line that named an absolute working-tree
  path and now resolves the repository root from the file's own location); its own header says so.
  No prompt, comparison, model id or output changed;
- `cash_adjudication.jsonl` — every answer in full, with the truth it was compared against, the
  per-case verdicts under the comparator, and token usage;
- `original_verdicts.log` — the original verdicts exactly as the runner printed them;
- `corrected_comparison.py` / `corrected_comparison.json` — the corrected comparison, recomputed
  from the archived answers through the shipped normalisation, with the predeclared rule's four
  outcomes and the as-executed reading beside it.

**The input revision.** `cash_adjudicate.py` renders each case's eleven public files from the
working tree at call time. That tree stood at `26a5a9a` on 2026-09-10 between 20:28 and 20:37; the
next commit, `ba84b07`, is dated 2026-09-11 03:04. Case 2's archived answers contain `TRC0428442`,
the bank trace the payment-identity repair printed on its 28 April statement row — so **this
adjudication used the revised Case 2 reference, not the input the original Bowline screen was
measured against**. That screen ran at `f9fbad1`, where the same row's reference reads
`SI-3104 SI-3102`; `reviews/cash_application_screen_2026-09-10.md` already records the move. The two
measurements therefore read different Case 2 bytes, and neither is evidence about the other's
revision. Historical evidence is valid at its recorded revision, not automatically against every
later checkout.
