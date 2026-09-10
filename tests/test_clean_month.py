"""The CLEAN-MONTH ASSURANCE PACK: four tasks, one instruction, two claims.

Every other suite asks whether the agent can find and repair what was
planted. A buyer asks the opposite question first, because it is the one that
decides whether they can point the thing at real books:

    does the agent damage a month that already reconciles?

The pack answers it with two company-months, each shipped twice. The CLEAN
task on a month plants nothing at all, so the correct deliverable is the
opening ledger unchanged, written back and submitted; the SINGLE-ERROR task
on the same month plants exactly one discrepancy, so leaving that same ledger
alone fails. Both carry the same neutral instruction, byte for byte, so
nothing in the prompt tells the two apart — the books do.

    clean_month_maple         / single_error_maple          maple-2025-12
    clean_month_silverbrook   / single_error_silverbrook    silverbrook-2025-11

A clean month is only worth shipping if it is genuinely tempting, so each one
leaves legitimate features standing that an over-eager agent will want to
"correct": a purchase invoice open at the cut-off and correctly unpaid, an
insurance premium correctly sitting in Assets:Prepayments rather than an
expense, bank charges already booked at the statement's figures, and timing
items in the ledger that the statement does not show. Each is supported by
the public files — the statement row, the vendor master's default account,
the terms, the policy section — so the evidence says they are right.

What is witnessed here:

  * the four tasks are in the registry, load without the evaluator secret,
    and share one prompt string that names no company, month, bank or count;
  * the pair on a month is the SAME books one entry apart: one expected
    ledger, and the clean task's opening ledger IS that expected ledger;
  * through the real `env.evaluate` door — `list_files -> read_file ->
    write_ledger(unchanged) -> submit` — a clean month scores 1.0, closes
    complete, and stops at `piv_submitted` with the artifact bound. The tool
    loop accepts a deliverable that changed nothing; there is no protocol
    refusal for "nothing to fix";
  * three invented corrections on a clean month — reclassifying the
    legitimate prepayment to an expense, "paying" the correctly open
    invoice, deleting the timing item that has not cleared — each score
    below 1.0, and each trips the channel it should and not the one it
    should not;
  * the single-error counterpart's untouched original scores below 1.0 with
    its one item unresolved, and its evidenced repair scores 1.0.

The features the damage cases attack are NAMED here as literal payees,
references and accounts, and every one of them is asserted to occur in the
public ledger before it is used. A world that drifts breaks this suite loudly
rather than quietly making it test nothing.

    python tests/test_clean_month.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (str(ROOT), str(ROOT / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from beancount_ledger import beancount_ledger as env_mod  # noqa: E402
from beancount_ledger.candidate import committed as K  # noqa: E402
from beancount_ledger.graph.derive import derive_contract  # noqa: E402
from beancount_ledger.graph.worlds import REGISTRY  # noqa: E402
from beancount_ledger.graph.worlds._assurance import ASSURANCE_PROMPT  # noqa: E402

from world_checks import decoded_public, score_text  # noqa: E402

#: The pack, as (clean task, single-error task) on one company-month.
PAIRS = (
    ("clean_month_maple", "single_error_maple", "maple-2025-12"),
    ("clean_month_silverbrook", "single_error_silverbrook", "silverbrook-2025-11"),
)
CLEAN_TASKS = tuple(pair[0] for pair in PAIRS)
ERROR_TASKS = tuple(pair[1] for pair in PAIRS)

#: The legitimate features each clean month leaves standing, named by the
#: strings that must occur in its public ledger. `check_the_features_exist`
#: asserts every one of them before any damage case is built from it, so the
#: penalty witnesses cannot silently start editing nothing.
FEATURES = {
    "clean_month_maple": {
        "prepayment_payee": "Shieldstone Mutual Insurance",
        "prepayment_mark": "check 4174",
        "prepayment_account": "Assets:Prepayments",
        "expense_account": "Expenses:Insurance",
        "open_invoice_payee": "Fernleigh Laboratory Supplies",
        "open_invoice_mark": "PI-5148",
        "open_invoice_amount": "1917.30",
        "payables_account": "Liabilities:AP",
        "bank_account": "Assets:Bank:Checking",
        "payment_date": "2025-12-31",
        "timing_payee": "Kilbride Property Holdings",
        "timing_mark": "check 4175",
    },
    "clean_month_silverbrook": {
        "prepayment_payee": "Larkin Mutual Insurance",
        "prepayment_mark": "check 3058",
        "prepayment_account": "Assets:Prepayments",
        "expense_account": "Expenses:Insurance",
        "open_invoice_payee": "Deverell Dental Products",
        "open_invoice_mark": "PI-5210",
        "open_invoice_amount": "4286.90",
        "payables_account": "Liabilities:AP",
        "bank_account": "Assets:Bank:Checking",
        "payment_date": "2025-11-30",
        "timing_payee": "Maple Row Family Dentistry",
        "timing_mark": "check 10388",
    },
}


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:40]:
            print(f"      {line}")
    return ok


def inputs_for(task_id: str):
    return derive_contract(*REGISTRY[task_id])[1]


# --------------------------------------------------------------------------
# ledger surgery: the three invented corrections, built from the text
# --------------------------------------------------------------------------

def _find_header(lines, payee: str, mark: str) -> int:
    """The index of the transaction header line for this payee and mark.
    Exactly one must match: a payee with two entries in the month (a rent
    check and a rent prepayment; a sale and its receipt) is why the mark is
    part of the address."""
    hits = [i for i, line in enumerate(lines)
            if line[:1].isdigit() and f'"{payee}"' in line and mark in line]
    if len(hits) != 1:
        raise LookupError(f"{len(hits)} transactions match payee {payee!r} and mark {mark!r}")
    return hits[0]


def _block_end(lines, start: int) -> int:
    """One past the last posting line of the transaction that starts at
    `start` — postings are the indented lines that follow it."""
    end = start + 1
    while end < len(lines) and lines[end].startswith("  "):
        end += 1
    return end


def reclassify_prepayment(text: str, f: dict) -> str:
    """Book the legitimate prepayment straight to an expense instead. The
    entry is right as it stands: the vendor master gives the insurer
    Assets:Prepayments and the policy makes a premium for the next month's
    cover an asset."""
    lines = text.splitlines(keepends=True)
    start = _find_header(lines, f["prepayment_payee"], f["prepayment_mark"])
    for i in range(start + 1, _block_end(lines, start)):
        if lines[i].startswith(f"  {f['prepayment_account']} "):
            lines[i] = lines[i].replace(f["prepayment_account"], f["expense_account"], 1)
            return "".join(lines)
    raise LookupError(f"no {f['prepayment_account']} posting under {f['prepayment_payee']}")


def pay_the_open_invoice(text: str, f: dict) -> str:
    """Settle a purchase invoice that is correctly still open at the cut-off.
    Nothing on the statement pays it and its terms put it in the next month;
    the entry is an invention."""
    return text.rstrip("\n") + (
        f'\n\n{f["payment_date"]} * "{f["open_invoice_payee"]}" '
        f'"Payment of purchase invoice {f["open_invoice_mark"]}"\n'
        f'  {f["payables_account"]}   {f["open_invoice_amount"]} USD\n'
        f'  {f["bank_account"]}  -{f["open_invoice_amount"]} USD\n'
    )


def delete_the_timing_item(text: str, f: dict) -> str:
    """Remove the entry the statement does not show. It is a timing item —
    written before the cut-off, cleared after it — not an error."""
    lines = text.splitlines(keepends=True)
    start = _find_header(lines, f["timing_payee"], f["timing_mark"])
    end = _block_end(lines, start)
    while end < len(lines) and not lines[end].strip():
        end += 1
    return "".join(lines[:start] + lines[end:])


#: Each invented correction, with the channel it MUST trip and a channel it
#: must NOT: an assertion that only says "something went wrong" would pass
#: for the wrong reason.
DAMAGE_CASES = (
    ("reclassify the legitimate prepayment to an expense", reclassify_prepayment,
     ("removed_or_altered", "fabricated", "collateral_damage"), ()),
    ("pay the invoice that is correctly still open", pay_the_open_invoice,
     ("fabricated", "collateral_damage"), ("removed_or_altered",)),
    ("delete the timing item that has not cleared", delete_the_timing_item,
     ("removed_or_altered", "collateral_damage"), ("fabricated",)),
)


# --------------------------------------------------------------------------
# the real door
# --------------------------------------------------------------------------

def deliver(task_id: str, ledger_text: str) -> dict:
    """One scripted conforming rollout through the real `env.evaluate` door,
    delivering `ledger_text`: `list_files -> read_file -> write_ledger ->
    submit`. The same shape `tests/liveness_witness.py` drives, on a registry
    task rather than a minted selector, so no evaluator secret is involved."""
    import measure_budget as mb
    import test_episode_contract as tec

    names = {tool.__name__ for tool in env_mod.PUBLIC_TOOLS}
    for required in ("list_files", "read_file", "write_ledger", "submit"):
        if required not in names:
            raise SystemExit(f"the package no longer exposes a {required!r} tool: {sorted(names)}")
    script = [tec.calls(("l1", "list_files", {})),
              tec.calls(("r1", "read_file", {"path": env_mod.LEDGER})),
              tec.calls(("w1", "write_ledger", {"content": ledger_text})),
              tec.calls(("s1", "submit", {}))]
    env = env_mod.load_environment(task_id)
    results = asyncio.run(env.evaluate(client=tec.TurnScript(script), model="scripted-conforming",
                                       num_examples=1, rollouts_per_example=1, max_concurrent=1,
                                       save_results=False,
                                       # `bind_artifact` reads the rollout id, the phase and the
                                       # workspace out of the rollout's own state; anything less than
                                       # its declared column set makes the binding fail for a missing
                                       # column rather than for a real mismatch.
                                       state_columns=list(mb.BASE_STATE_COLUMNS)))
    out = results["outputs"][0]
    artifact = mb.bind_artifact(out, env_mod)
    return {
        "reward": out.get("reward"),
        "stop": out.get("stop_condition"),
        "phase": out.get("piv_phase"),
        "error": out.get("error"),
        "submitted": artifact.get("submitted"),
        "artifact": artifact.get("artifact"),
        "tools": mb.tool_names(out.get("completion") or []),
    }


# --------------------------------------------------------------------------
# the tests
# --------------------------------------------------------------------------

def test_the_pack_is_registered_and_shares_one_instruction():
    problems = []
    for clean, error, world_id in PAIRS:
        for task_id in (clean, error):
            if task_id not in REGISTRY:
                problems.append(f"{task_id} is not in REGISTRY")
                continue
            if REGISTRY[task_id][0].id != world_id:
                problems.append(f"{task_id} is on world {REGISTRY[task_id][0].id}, not {world_id}")
    if problems:
        return check("the four assurance tasks are registered on their company-months", False, "\n".join(problems))

    prompts = {task_id: inputs_for(task_id).prompt for pair in PAIRS for task_id in pair[:2]}
    if len(set(prompts.values())) != 1:
        problems.append(f"the four tasks do not share one prompt: { {k: v[:60] for k, v in prompts.items()} }")
    elif next(iter(prompts.values())) != ASSURANCE_PROMPT:
        problems.append("the shared prompt is not _assurance.ASSURANCE_PROMPT")
    # A neutral instruction cannot name the company, the month, the bank or
    # the number of differences — any of those would split the pair for a
    # model that never opened the ledger.
    tells = ["Maple", "Silverbrook", "December", "November", "Wattle", "Harlow",
             "veterinary", "clinic", "dental", "corrected", "error", "discrepanc",
             "missing", "wrong amount", "duplicate", "nothing to"]
    for tell in tells:
        if tell.lower() in ASSURANCE_PROMPT.lower():
            problems.append(f"the shared instruction contains the tell {tell!r}")
    if "ledger.beancount" not in ASSURANCE_PROMPT:
        problems.append("the shared instruction does not ask for the write-back to ledger.beancount")
    return check("the four tasks are registered and carry one neutral instruction, byte for byte",
                 not problems, "\n".join(problems))


def test_the_registry_ids_load_without_the_evaluator_secret():
    problems = []
    saved = {name: os.environ.pop(name, None) for name in ("PIV_EVAL_SECRET", "PIV_DEV_UNMANIFESTED")}
    try:
        for task_id in CLEAN_TASKS + ERROR_TASKS:
            try:
                env_mod.load_environment(task_id)
            except Exception as exc:
                problems.append(f"{task_id}: load_environment raised {type(exc).__name__}: {exc}")
    finally:
        for name, value in saved.items():
            if value is not None:
                os.environ[name] = value
    return check("all four ids build an environment with no evaluator secret set, like the other registry tasks",
                 not problems, "\n".join(problems))


def test_the_pair_is_the_same_books_one_entry_apart():
    problems = []
    for clean, error, _world in PAIRS:
        c, e = inputs_for(clean), inputs_for(error)
        if c.planted:
            problems.append(f"{clean} plants {[p.id for p in c.planted]}; a clean month plants nothing")
        if len(e.planted) != 1:
            problems.append(f"{error} plants {len(e.planted)} items, not exactly one")
        if c.golden_text != e.golden_text:
            problems.append(f"{clean} and {error} do not share one expected ledger; they are not the same month")
        if c.original_text != c.golden_text:
            problems.append(f"{clean}: the opening ledger is not the expected ledger, so the correct deliverable "
                            f"is not the ledger as it stands")
        if e.original_text == e.golden_text:
            problems.append(f"{error}: the opening ledger already equals the expected ledger; nothing was planted")
        if c.scored_accounts:
            problems.append(f"{clean}: scored accounts {list(c.scored_accounts)} on a month with no residual")
    return check("each pair is one expected ledger, with the clean month's opening ledger already equal to it",
                 not problems, "\n".join(problems))


def test_the_tempting_features_are_in_the_public_ledger():
    """Every string the damage cases address occurs in the bytes the agent
    reads. Without this the surgery below could quietly stop editing
    anything and every penalty witness would still 'pass'."""
    problems = []
    for task_id in CLEAN_TASKS:
        public = decoded_public(inputs_for(task_id))
        ledger, vendors = public["ledger.beancount"], public["vendors.csv"]
        statement = public["bank_statement.csv"]
        f = FEATURES[task_id]
        for key in ("prepayment_payee", "prepayment_mark", "prepayment_account",
                    "open_invoice_payee", "open_invoice_mark", "open_invoice_amount",
                    "payables_account", "bank_account", "timing_payee", "timing_mark"):
            if f[key] not in ledger:
                problems.append(f"{task_id}: the ledger does not carry {key}={f[key]!r}")
        if f["expense_account"] not in public["accounts.csv"]:
            problems.append(f"{task_id}: {f['expense_account']} is not in the chart")
        # the prepayment is evidenced as a prepayment, not as an expense
        if f"{f['prepayment_payee']},due on receipt,{f['prepayment_account']}" not in vendors:
            problems.append(f"{task_id}: vendors.csv does not book {f['prepayment_payee']} to "
                            f"{f['prepayment_account']}")
        # the open invoice is evidenced as unpaid: no statement row settles it
        if f["open_invoice_mark"] in statement:
            problems.append(f"{task_id}: the statement carries a row for {f['open_invoice_mark']}, so the "
                            f"invoice is not open at the cut-off")
        # the timing item is evidenced as a timing item: in the books, not on
        # the statement
        if f["timing_mark"].split()[-1] in statement:
            problems.append(f"{task_id}: the statement shows {f['timing_mark']}, so it is not a timing item")
    return check("every legitimate feature the damage cases attack is present and evidenced in the public files",
                 not problems, "\n".join(problems))


def test_the_unchanged_clean_ledger_is_accepted_and_scores_one():
    """The whole claim, through the production door: the agent writes back
    the ledger it read, unchanged, and submits. The tool loop must take it —
    a protocol that refused a no-op write would make a clean month
    undeliverable — and the scorer must pay 1.0 for it."""
    problems = []
    for task_id in CLEAN_TASKS:
        inputs = inputs_for(task_id)
        observed = deliver(task_id, inputs.original_text)
        if observed["error"]:
            problems.append(f"{task_id}: the rollout recorded an error: {observed['error']}")
        if observed["reward"] != 1.0:
            problems.append(f"{task_id}: reward {observed['reward']!r}, expected 1.0 for the unchanged ledger")
        if observed["stop"] != "piv_submitted":
            problems.append(f"{task_id}: stop condition {observed['stop']!r}, expected piv_submitted")
        if observed["phase"] != env_mod.EpisodePhase.TERMINAL.value or not observed["submitted"]:
            problems.append(f"{task_id}: phase {observed['phase']!r} / submitted {observed['submitted']!r}; "
                            f"write_ledger then submit must end the episode")
        if observed["artifact"] != "BOUND":
            problems.append(f"{task_id}: artifact {observed['artifact']}, expected BOUND")
        if observed["tools"] != ["list_files", "read_file", "write_ledger", "submit"]:
            problems.append(f"{task_id}: the executed tools were {observed['tools']}")
        # and the scorer's own view of the same text
        env = K.load_contract(inputs)
        outcome, failure = score_text(inputs.original_text, env, task_id)
        if failure:
            problems.append(failure)
        elif not (outcome.total == Decimal("1") and outcome.complete):
            problems.append(f"{task_id}: the unchanged ledger scores {outcome.total} complete={outcome.complete}")
    return check("a clean month delivered unchanged through the real door scores 1.0, closes complete and stops "
                 "at piv_submitted; the tool loop does not refuse a deliverable that changed nothing",
                 not problems, "\n".join(problems))


def test_an_invented_correction_on_a_clean_month_is_penalised():
    problems = []
    witnessed = 0
    for task_id in CLEAN_TASKS:
        inputs = inputs_for(task_id)
        env = K.load_contract(inputs)
        f = FEATURES[task_id]
        for label, damage, must_fire, must_not_fire in DAMAGE_CASES:
            try:
                text = damage(inputs.original_text, f)
            except LookupError as exc:
                problems.append(f"{task_id}: could not build '{label}': {exc}")
                continue
            if text == inputs.original_text:
                problems.append(f"{task_id}: '{label}' changed nothing; the witness would be vacuous")
                continue
            outcome, failure = score_text(text, env, f"{task_id}: {label}")
            if failure:
                problems.append(failure)
                continue
            witnessed += 1
            if outcome.total >= Decimal("1"):
                problems.append(f"{task_id}: '{label}' still scores {outcome.total}; damage is not priced")
            if outcome.complete:
                problems.append(f"{task_id}: '{label}' is reported as a complete close")
            for channel in must_fire:
                if not list(getattr(outcome, channel)):
                    problems.append(f"{task_id}: '{label}' did not trip {channel}; the penalty came from "
                                    f"somewhere else")
            for channel in must_not_fire:
                if list(getattr(outcome, channel)):
                    problems.append(f"{task_id}: '{label}' tripped {channel}, which this damage does not do: "
                                    f"{list(getattr(outcome, channel))}")
    if witnessed != len(CLEAN_TASKS) * len(DAMAGE_CASES):
        problems.append(f"only {witnessed} of {len(CLEAN_TASKS) * len(DAMAGE_CASES)} damage cases were scored")
    return check(f"{len(CLEAN_TASKS) * len(DAMAGE_CASES)} invented corrections on the clean months each score "
                 f"below 1.0 through the channel they should, and not through one they should not",
                 not problems, "\n".join(problems))


def test_the_single_error_counterpart_bites():
    problems = []
    for _clean, task_id, _world in PAIRS:
        inputs = inputs_for(task_id)
        env = K.load_contract(inputs)
        planted = [p.id for p in inputs.planted]
        original, failure = score_text(inputs.original_text, env, f"{task_id}: original")
        if failure:
            problems.append(failure)
        else:
            if original.total >= Decimal("1"):
                problems.append(f"{task_id}: leaving the ledger unchanged scores {original.total}; the planted "
                                f"error is not priced")
            if sorted(original.unresolved_planted) != sorted(planted):
                problems.append(f"{task_id}: unresolved {list(original.unresolved_planted)}, expected {planted}")
        golden, failure = score_text(inputs.golden_text, env, f"{task_id}: golden")
        if failure:
            problems.append(failure)
        elif not (golden.total == Decimal("1") and golden.complete):
            problems.append(f"{task_id}: the evidenced repair scores {golden.total} complete={golden.complete}")
    return check("on each single-error counterpart the untouched ledger fails with its one item unresolved and "
                 "the evidenced repair scores 1.0",
                 not problems, "\n".join(problems))


TESTS = [
    test_the_pack_is_registered_and_shares_one_instruction,
    test_the_registry_ids_load_without_the_evaluator_secret,
    test_the_pair_is_the_same_books_one_entry_apart,
    test_the_tempting_features_are_in_the_public_ledger,
    test_the_unchanged_clean_ledger_is_accepted_and_scores_one,
    test_an_invented_correction_on_a_clean_month_is_penalised,
    test_the_single_error_counterpart_bites,
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
