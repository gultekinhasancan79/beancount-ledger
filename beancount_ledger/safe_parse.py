"""The one way this package is allowed to parse submitted content.

`beancount.loader.load_string` imports the module named by a `plugin`
directive. Measured on beancount 3.2.3:

    plugin "base64"   ->  no error, and base64 appears in sys.modules

Importing runs module-level code. Any code path that hands agent-authored text
to the loader therefore executes whatever an already-importable module does at
import time, silently and with no error reported.

This module exists because that hole was fixed in one place and left open in
another. The candidate boundary was migrated to a non-importing parser while
`reward.py` — the scorer the environment actually runs, reachable from the
`write_ledger` tool — kept calling the loader. The write-up said the hole was
closed. It was closed in a layer nothing called.

So the safe parse lives here, once, and both layers import it. A security
property that is reimplemented per call site is a security property that will
be missing from the next call site.

Two defences, in order:

  1. a lexical gate in front of the parser, refusing side-effecting controls
     before any parser sees the bytes;
  2. `parser.parse_string`, which records a `plugin` directive in the option
     map and imports nothing.

The second is the wall — it removes the capability rather than guarding it.
The first is defence in depth and a faster, clearer diagnostic. It is also the
weaker of the two: an earlier version skipped indented lines, and the loader
happily imported the module from ` plugin "x"` while reporting a syntax error,
so the gate lost to a single leading space. Its completeness depends on
agreeing with beancount's lexer, which is why it is not the only wall.
"""

from __future__ import annotations

from beancount.core import data
from beancount.core.number import MISSING
from beancount.ops import validation
from beancount.parser import parser

# Top-level controls refused before parsing. `plugin` is the dangerous one;
# `include` would pull in entries nothing compares; the push/pop pairs fold
# state into later entries without leaving an AST path that records it.
SIDE_EFFECTING_CONTROLS = {
    "plugin": (
        "control.plugin",
        "the loader imports the named module while parsing, so this is refused "
        "before any parser sees the bytes",
    ),
    "include": ("control.include", "would pull in entries no comparison sees"),
    "pushtag": ("control.pushtag", "folds hidden state into later entries"),
    "poptag": ("control.poptag", "folds hidden state into later entries"),
    "pushmeta": ("control.pushmeta", "folds hidden state into later entries"),
    "popmeta": ("control.popmeta", "folds hidden state into later entries"),
}


class UnsafeInput(Exception):
    """Submitted text carrying a construct that must not reach a parser."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def check_controls(text: str) -> tuple[str, str] | None:
    """The first line of defence. Returns (reason, detail) or None.

    Leading whitespace and a byte order mark are stripped before the keyword is
    taken. The first version required column zero, on the reasoning that
    beancount's grammar does — and the loader imported the module from an
    indented `plugin` line anyway, while calling it a syntax error. A gate whose
    completeness depends on agreeing with the lexer loses whenever they
    disagree, and they disagreed on the first variant tested.

    Nothing is lost by being generous: a posting line's first token is an
    account name, which must begin with one of the five root types, so no
    legitimate line inside a transaction can collide with a control keyword.
    """
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip("﻿ \t")
        if not stripped or stripped.startswith(";"):
            continue
        keyword = stripped.split(None, 1)[0] if stripped.split() else ""
        control = SIDE_EFFECTING_CONTROLS.get(keyword)
        if control is not None:
            reason, note = control
            return reason, f"line {number}: {note}"
    return None


def find_elided(entries: list) -> str | None:
    """The first posting with no explicit amount, described, or None.

    `parse_string` does not book, so an omitted amount arrives as the MISSING
    sentinel where the loader would have inferred a number — and downstream
    beancount code, `validation.validate` included, assumes booked entries and
    raises on the sentinel. This runs as a whole-ledger pass before anything
    else touches the entries.
    """
    for entry in entries:
        if not isinstance(entry, data.Transaction):
            continue
        for posting in entry.postings:
            units = posting.units
            if units is None or units is MISSING or getattr(units, "number", None) in (None, MISSING):
                return f"{entry.date} posting to {posting.account} has no explicit amount"
    return None


def safe_parse(text: str) -> tuple[list, list, list, dict]:
    """Parse submitted text without ever importing anything it names.

    Returns `(entries, parse_errors, validation_errors, options_map)`, with
    both error lists holding strings.

    Elision is reported as a parse error rather than silently booked. That is
    a real behavioural difference from the loader and it is the intended one:
    inferring an omitted amount needs a booking model this package does not
    have, and an agent can always write the number.
    """
    gate = check_controls(text)
    if gate is not None:
        reason, detail = gate
        return [], [f"{reason}: {detail}"], [], {}

    try:
        entries, parse_errors, options_map = parser.parse_string(text)
    except Exception as exc:  # the parser is third-party; a crash is a refusal
        return [], [f"parser raised {type(exc).__name__}: {exc}"], [], {}

    parsed = [
        f"{type(e).__name__}: {getattr(e, 'message', e)}" for e in parse_errors
    ]
    if parsed:
        return entries, parsed, [], dict(options_map)

    elided = find_elided(entries)
    if elided is not None:
        return entries, [f"posting.units.elided: {elided}"], [], dict(options_map)

    try:
        found = validation.validate(entries, options_map)
    except Exception as exc:
        return entries, [], [f"validation raised {type(exc).__name__}: {exc}"], dict(options_map)

    validated = [
        f"{type(e).__name__}: {getattr(e, 'message', e)}" for e in found
    ]
    return entries, [], validated, dict(options_map)
