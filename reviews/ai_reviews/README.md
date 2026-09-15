# AI review notes

One file per review, `YYYY-MM-DD_<what>_<reviewer>.md` (for example
`2026-09-16_pr9_codex.md`). The reviewer is never the builder (see `AGENTS.md`). The owner merges
after a `SIGNED` note, or overrules in writing in the journal.

A note has, in this order:

```
# Review of <PR or commit>: <one-line subject>

**Reviewer.** Codex | Claude Code. **Builder.** the other one. **Date.**
**Motivating journal entry.** docs/dev_journal/<file>#<heading>
**Verdict.** SIGNED | NOT_SIGNED

## What was checked
The commands run and their outcomes, the files read, the inputs tried (including wrong ones).

## Problems
One per line: `[blocking|minor] <file>:<line or place> — <what is wrong, and how it was shown>`.
"blocking" means the requirement is not met, a published record changed, or a check passes when it
should fail. No problems: say so, with what was tried.

## What the reviewer would not sign
Claims in the builder's entry or the PR text that the evidence does not carry, quoted.
```

The reviewer's job is to refute, not to approve. A review that re-runs nothing is not a review. A
`NOT_SIGNED` note goes back to the builder with the problems; the repaired change gets a new note.
