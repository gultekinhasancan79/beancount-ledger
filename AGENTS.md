# Working agreement for AI collaborators on this repository

Two agents work on this repository with the owner: **Codex** (reads this file) and **Claude Code**
(reads `CLAUDE.md`, which points here). Neither has the other's chat history. What they share is the
repository, so everything that must be known by both lives in the repository, in plain language, and
is written **before the session that produced it ends**.

## The three rules that make two agents one team

1. **Read before you act.** At the start of every session, read this file, then the newest file in
   `docs/dev_journal/`, then `git log --oneline -15`. That is the whole hand-over; if it is not there,
   it did not happen.
2. **Write before you stop.** At the end of every session, append an entry to the newest journal file
   (or open a new one for a new day) under your own name: what the owner said and decided (their
   words, not a paraphrase that shifts the meaning), what changed (commit hashes, files), what is
   open, what you would do next, and any idea or gap you noticed. A session that ends without an
   entry has to be reconstructed from the diff by the other agent, which is slow and lossy.
3. **Nobody merges their own work unreviewed.** The agent who built a change does not judge it. The
   other agent reviews the pull request against the journal entry that motivated it and writes a
   note in `reviews/ai_reviews/` with a verdict, `SIGNED` or `NOT_SIGNED`, and the problems found,
   each with a severity. The owner merges after a `SIGNED` note, or overrules in writing in the
   journal. A review that only says "looks good" is not a review; it names what was checked.

## Roles, and how they rotate

- Whoever the owner talks to about a task is its **builder** for that task. The other agent is its
  **reviewer**. The roles rotate per task, not per agent: both build, both review.
- The reviewer is adversarial on purpose: it tries to refute the builder's claims by running the
  checks itself, reading the diff, and probing wrong inputs. Agreement is reported briefly; a
  disagreement is written out with the evidence.
- When the two disagree, neither decides. Both positions go into the journal with their evidence,
  and the owner rules. The ruling is recorded verbatim.
- Ideas and gaps are welcome from either agent at any time; they go into the journal's **Ideas and
  gaps** section with the reason and the cost, and the owner picks. An idea is not a task until the
  owner says so.

## Rules that never change

- **Money: none.** Never spend money on this project. No paid inference, no credits, no
  subscriptions. If a route starts billing, stop and find a free one.
- **Secrets.** Never read, print, copy or hash `~/.piv/eval_secret`. Never set `PIV_DEV_UNMANIFESTED`
  on a serving path. Never write to `~/.piv` unasked. API keys are never pasted into a chat or a
  file; refer to them by variable name and print at most a key's length.
- **Ask first** for anything that costs money, changes the shipped package's public behaviour,
  publishes or pushes, or needs a card, an account signup or identity verification. **Decide
  yourself** for runs, model roles, scratch code and the next experiment within the agreed plan.
- **Honesty is the product.** State known issues plainly. A defect a careful buyer finds for
  themselves costs more than one we declared. Missing outcomes stay missing; nothing is refilled,
  re-run or substituted. A model's own outputs never certify that model's own results.
- **Measurement hygiene.** One model per ceiling gate. Output-budget exhaustion is its own category,
  never a difficulty claim. Rows taken under different episode budgets are different arms and are
  never pooled. Pre-register a screen's selection before the first model call and quote its digest
  on every row.
- **Tests run with this repository's own virtual environment** (`.venv`), never one borrowed from
  another clone. The full battery is `tests/run_all.py`.
- **Published records are immutable.** A correction is a new file beside the old one, with the old
  value quoted; the old record is never edited in place.

## Language

Files in the repository are written in English. The owner is spoken to in the language they use,
plainly and briefly; a decision put to the owner is one question, not a menu.

## Machine-specific notes

Anything that is true only of a particular machine or account (where keys live, which free quotas
remain, which routes are dead) goes in `AGENTS.local.md` beside this file. That file is ignored by
git and is read after this one when present. It is never committed.
