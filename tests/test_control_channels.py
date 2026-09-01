"""Top-level grammar channels, and the one that executes code.

`data.ALL_DIRECTIVES` is not the grammar. It is the union of directive objects
the parser *emits*, and beancount also has top-level control syntax that acts
during parsing and may never appear as a directive at all. A field inventory
can be one hundred percent exhaustive over that union while omitting an entire
class of syntax, which is why this is a separate test from mapping coverage
rather than another case inside it.

One of those controls executes code. Measured on beancount 3.2.3:

    plugin "base64"     ->  no error, and base64 lands in sys.modules

The parser imports the module named by a `plugin` directive while parsing. A
module that does not exist raises a LoadError and the fatal-error rule catches
it; a module that exists is imported silently, and importing runs module-level
code. Since the agent in this environment writes files into the working
directory, a module it controls is a module it can get imported.

Classifying `plugin` as rejected in the mapping table does not help, because
classification happens after parsing and the import happens during it. The only
position where the check works is in front of the parser, which is what the
lexical gate is and why it exists.

    python tests/test_control_channels.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.candidate.normalise import (  # noqa: E402
    SIDE_EFFECTING_CONTROLS,
    ProtocolFailure,
    parse_once,
)

# Every top-level control beancount 3.2.3 accepts. `option` is the one that is
# handled rather than refused; the rest are refused before parsing.
KNOWN_CONTROLS = {
    "option", "include", "plugin", "pushtag", "poptag", "pushmeta", "popmeta",
}

PREAMBLE = 'option "operating_currency" "USD"\n'
BODY = (
    "2025-11-01 open Assets:A USD\n"
    "2025-11-01 open Assets:B USD\n"
    '2025-11-05 * "Northwind Supplies" "N"\n'
    "  Assets:A   1.00 USD\n"
    "  Assets:B  -1.00 USD\n"
)


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines():
            print(f"      {line}")
    return ok


def test_every_control_channel_is_accounted_for():
    """Each known control is either handled or explicitly refused."""
    handled = {"option"}
    covered = handled | set(SIDE_EFFECTING_CONTROLS)
    missing = sorted(KNOWN_CONTROLS - covered)
    return check(
        "every top-level control is handled or refused",
        not missing,
        f"unaccounted for: {missing}",
    )


def test_plugin_does_not_reach_the_parser():
    """The gate must prevent the import, not report it afterwards.

    Asserting on the return value alone would pass even if the module had
    already been imported, so this watches sys.modules across the call. The
    module chosen is one nothing here imports otherwise.
    """
    probe = "colorsys"
    if probe in sys.modules:
        del sys.modules[probe]
    before = set(sys.modules)
    result = parse_once(f'{PREAMBLE}plugin "{probe}"\n{BODY}')
    imported = probe in (set(sys.modules) - before)
    refused = isinstance(result, ProtocolFailure) and result.reason == "control.plugin"
    return check(
        "a plugin directive is refused without importing anything",
        refused and not imported,
        f"refused={refused}, module imported={imported}",
    )


def test_side_effecting_controls_are_refused():
    problems = []
    for keyword, (reason, _) in sorted(SIDE_EFFECTING_CONTROLS.items()):
        line = {
            "plugin": 'plugin "hashlib"',
            "include": 'include "other.beancount"',
            "pushtag": "pushtag #batch",
            "poptag": "poptag #batch",
            "pushmeta": 'pushmeta ref: "x"',
            "popmeta": "popmeta ref:",
        }[keyword]
        result = parse_once(f"{PREAMBLE}{line}\n{BODY}")
        if not isinstance(result, ProtocolFailure) or result.reason != reason:
            got = result.reason if isinstance(result, ProtocolFailure) else "ACCEPTED"
            problems.append(f"{keyword}: expected {reason}, got {got}")
    return check(
        "every side-effecting control is refused with its own reason",
        not problems,
        "\n".join(problems),
    )


def test_the_gate_does_not_over_reject():
    """A control keyword inside a comment is inert and must be accepted.

    The gate's whole risk is becoming a second parser. If it starts matching
    keywords anywhere rather than as a line's first token, it will reject
    submissions that say nothing at all.
    """
    result = parse_once(f'{PREAMBLE}; plugin "hashlib"\n; include "x"\n{BODY}')
    return check(
        "commented-out controls are not refused",
        not isinstance(result, ProtocolFailure),
        result if isinstance(result, ProtocolFailure) else "",
    )


def test_a_narration_mentioning_a_control_is_accepted():
    """Words are not controls. A payee or narration may say anything."""
    body = (
        "2025-11-01 open Assets:A USD\n"
        "2025-11-01 open Assets:B USD\n"
        '2025-11-05 * "Northwind Supplies" "plugin include pushtag"\n'
        "  Assets:A   1.00 USD\n"
        "  Assets:B  -1.00 USD\n"
    )
    result = parse_once(PREAMBLE + body)
    return check(
        "a narration containing control keywords is accepted",
        not isinstance(result, ProtocolFailure),
        result if isinstance(result, ProtocolFailure) else "",
    )


def test_control_prefixes_the_lexer_accepts_are_all_refused():
    """The gate must not depend on agreeing with beancount's lexer.

    The first version skipped indented lines, because controls "must" be at
    column zero. Measured against the loader, that was false in the direction
    that matters:

        ' plugin "colorsys"'   ->  ParserSyntaxError, and colorsys imported

    A leading space produced a syntax error *and* the import, so a gate that
    trusted the column rule let it straight through. Every prefix form the
    lexer tolerates is checked here, and the underlying capability is gone as
    well now that the parser used does not import anything -- but the gate is
    the fast diagnostic, and it should not be the thing that is wrong.
    """
    problems = []
    for label, prefix in (
        ("plain", ""),
        ("leading space", " "),
        ("leading tab", "\t"),
        ("two spaces", "  "),
        ("byte order mark", "﻿"),
        ("bom then space", "﻿ "),
    ):
        text = f'{PREAMBLE}{prefix}plugin "hashlib"\n{BODY}'
        result = parse_once(text)
        if not isinstance(result, ProtocolFailure):
            problems.append(f"{label}: ACCEPTED")
        elif result.reason != "control.plugin":
            problems.append(f"{label}: refused as {result.reason}, not control.plugin")
    return check(
        "every prefix form of a control is refused by the gate",
        not problems,
        "\n".join(problems),
    )


def test_the_parser_in_use_does_not_import_plugins():
    """The capability itself must be absent, not merely guarded.

    This bypasses the gate deliberately and calls the parser directly, because
    the property under test is about the parser rather than about our check.
    `loader.load_string` fails this; `parser.parse_string` passes it, which is
    why the boundary uses the latter.
    """
    from beancount.parser import parser as bc_parser

    probe = "colorsys"
    sys.modules.pop(probe, None)
    before = set(sys.modules)
    bc_parser.parse_string(f'{PREAMBLE}plugin "{probe}"\n{BODY}')
    imported = probe in (set(sys.modules) - before)
    return check(
        "the parser the boundary uses imports nothing from submitted content",
        not imported,
        f"{probe} was imported by the parser itself",
    )


def test_a_token_that_merely_starts_with_a_control_is_not_one():
    """Exact token, not prefix. `plugin-note:` is not `plugin`.

    The gate widened once already, to stop skipping indented lines. Widening a
    matcher is how it starts matching things it should not, and a metadata key
    or account segment beginning with a control word is the obvious near miss.
    Pinning it now means a future widening has to survive this test.
    """
    body = (
        "2025-11-01 open Assets:A USD\n"
        "2025-11-01 open Assets:B USD\n"
        '2025-11-05 * "Northwind Supplies" "N"\n'
        "  Assets:A   1.00 USD\n"
        "  Assets:B  -1.00 USD\n"
    )
    problems = []
    for label, text in (
        ("indented near-miss key", f"{PREAMBLE}  plugin-note: \"x\"\n{body}"),
        ("top-level near-miss key", f"{PREAMBLE}plugincheck 1\n{body}"),
        ("includes-as-a-word", f'{PREAMBLE}; includes are fine here\n{body}'),
    ):
        result = parse_once(text)
        if isinstance(result, ProtocolFailure) and result.reason.startswith("control."):
            problems.append(f"{label}: wrongly refused as {result.reason}")
    return check(
        "a token merely starting with a control word is not treated as one",
        not problems,
        "\n".join(problems),
    )


TESTS = [
    test_every_control_channel_is_accounted_for,
    test_a_token_that_merely_starts_with_a_control_is_not_one,
    test_control_prefixes_the_lexer_accepts_are_all_refused,
    test_the_parser_in_use_does_not_import_plugins,
    test_plugin_does_not_reach_the_parser,
    test_side_effecting_controls_are_refused,
    test_the_gate_does_not_over_reject,
    test_a_narration_mentioning_a_control_is_accepted,
]


def run() -> int:
    import beancount
    print(f"control channels against beancount {beancount.__version__}\n")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
