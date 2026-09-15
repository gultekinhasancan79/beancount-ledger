# The development journal

One file per day, `YYYY-MM-DD.md`, appended to by every agent session and by the owner when they
want a decision on the record. It is the shared memory of the two AI collaborators (see
`AGENTS.md`): neither can read the other's conversations, so what is not written here is unknown
to the other one.

## Entry shape

Every session appends one entry, under a heading with the time and the author:

```
## 14:05 — Claude Code            (or: Codex, or: Owner)

**Owner said / decided.** The owner's words that matter, quoted, not paraphrased.
**Changed.** Commits (hash, one line each), files, records written; what was NOT done and why.
**Verified.** Which checks ran and their outcome (battery N/N, a suite, a script), or "none".
**Open.** Questions waiting on the owner; work left half-done; anything blocked.
**Next.** What this agent would do next, in order.
**Ideas and gaps.** Anything noticed that is not a task yet: a weakness, a missing check, an
idea, with the reason and a rough cost. The owner picks; an idea is not a task until they say so.
```

Rules: append, never rewrite an earlier entry (a correction is a new line that quotes the old one);
one entry per session even when nothing changed ("no change; read the journal and the log"); plain
sentences; every number with its source; no chat-style narration.

## Reading order for a new session

1. `AGENTS.md` (and `AGENTS.local.md` when present).
2. The newest journal file, then the one before it if the newest is short.
3. `git log --oneline -15`.
4. Any `reviews/ai_reviews/` note newer than your last entry.
