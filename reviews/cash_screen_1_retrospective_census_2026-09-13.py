"""Build the retrospective reconstruction the ruling asks for
(round18.answer.md:31), out of measure_budget's OWN pure census functions.

Nothing observed is touched: the nine rows are READ and preserved, the record
is a NEW file beside them.
"""
import ast, hashlib, json, re, sys
from datetime import datetime
from pathlib import Path

ROOT = Path("C:/Users/gulte/Desktop/PIV/beancount-ledger-workflows")
sys.path.insert(0, str(ROOT / "tests"))
import measure_budget as mb

ROWS = ROOT / "reviews/budget_qwen3.7-max-2026-05-20_2026-09-13_cash_screen_1.json"
# The frozen selection, PUBLISHED beside the results rather than read out of a
# scratch directory that will not survive: a record whose inputs are ephemeral
# is not reproducible. The published copy is byte-identical to the frozen one
# (sha256 e582c6cf..., self-digest 321c9715...), which the builder re-checks.
SELECTION = ROOT / "reviews/cash_screen_1_selection_2026-09-13.json"
FROZEN_SELECTION_SHA256 = "e582c6cf5b9053a7029eb9081555bb6f338741ae2ae7257ae3cd3f14ff03a9e7"
# NOT `budget_*.json`: that glob is `arm_table.py`'s row-file loader, and this
# is a census, not a row file. It is published beside its builder so neither
# lives only in scratchpad.
OUT = ROOT / "reviews/cash_screen_1_retrospective_census_2026-09-13.json"
BUILDER = "reviews/cash_screen_1_retrospective_census_2026-09-13.py"
# The runner's own console log, now PUBLISHED beside the evidence. When this
# record was first built the log lived only in scratch, so the lost cell's
# provider error code, type, message and request id had to stay UNKNOWN. They
# are in the log, and a reconstruction that says UNKNOWN about something its
# own linked evidence contains is under-reporting, not caution. Everything the
# log does NOT carry -- task id, times, workspace, usage -- stays UNKNOWN.
LOG = ROOT / "reviews/cash_application_generated_screen_2026-09-13/cash_screen_1_runner.log"
LOG_PATH = "reviews/cash_application_generated_screen_2026-09-13/cash_screen_1_runner.log"
U = mb.UNKNOWN


def digest(path: Path) -> dict:
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def lf_sha256(path: Path) -> str:
    """The digest of a TEXT file as the repository stores and checks it out.

    `.gitattributes` is `* text=auto eol=lf`, so every checkout gets LF
    whatever the platform, while a file written by Python on Windows lands
    CRLF. Hashing the raw bytes would publish a figure no checkout can
    reproduce, so the line endings are normalised first."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def log_facts() -> dict:
    """What the runner's console log says about the refusal that ended the run.

    The provider's error body is echoed verbatim in the traceback's final
    line. It is parsed, never retyped, so the record cannot drift from the
    log; the `elapsed` figure is the progress bar's own reading for the cell
    that never finished. Nothing else in the log is about cell 10.
    """
    text = LOG.read_text(encoding="utf-8", errors="replace")
    marker = "openai.PermissionDeniedError: Error code: 403 - "
    line = next((ln for ln in text.splitlines() if ln.startswith(marker)), None)
    if line is None:
        raise SystemExit(f"{LOG_PATH}: no 403 refusal in the log; the cell-10 link cannot be made")
    body = ast.literal_eval(line[len(marker):])["error"]
    elapsed = re.findall(r"0/1 \[(\d\d):(\d\d)<\?, \?it/s, reward=\?\]", text)
    return {
        "http_status": 403,
        "provider_error_code": body.get("code", U),
        "provider_error_type": body.get("type", U),
        "provider_error_message": body.get("message", U),
        "provider_request_id": body.get("id", U),
        "elapsed_before_refusal_seconds": (int(elapsed[-1][0]) * 60 + int(elapsed[-1][1])) if elapsed else U,
    }


rows = json.loads(ROWS.read_text(encoding="utf-8"))
FROM_LOG = log_facts()
assert digest(SELECTION)["sha256"] == FROZEN_SELECTION_SHA256, "the published selection is not the frozen one"
selection = json.loads(SELECTION.read_text(encoding="utf-8"))
order = selection["execution_order"]
assert len(rows) == 9 and len(order) == 12
by_selector = {r["selector"]: r for r in rows}
assert [r["selector"] for r in rows] == order[:9], "the nine rows are not the first nine of the frozen order"

common = {k: rows[0].get(k) for k in ("screen", "selection_digest", "model", "provider", "endpoint",
                                      "session_id", "schedule_id")}
common["screen"] = common.get("screen") or selection["screen"]
common["selection_digest"] = common.get("selection_digest") or selection["self_digest"]

cells = []
for index, selector in enumerate(order):
    ordinal = index + 1
    if selector in by_selector:
        row = dict(by_selector[selector])
        # The row predates `planned_ordinal`/`cell_status`; the ordinal is
        # RECONSTRUCTED from the frozen execution order, and says so.
        entry = mb.cell_disposition(row)
        entry.update(planned_ordinal=ordinal,
                     screen=common["screen"], selection_digest=common["selection_digest"],
                     reconstructed_fields={
                         "planned_ordinal": "the row's own planned_ordinal is null (the field postdates "
                                            "this run); this is its index in the frozen execution order "
                                            f"of {selection['self_digest'][:8]}",
                         "cell_status": "derived by measure_budget.cell_disposition from the row's own "
                                        "reward and quarantined fields"},
                     original_row_preserved={
                         "file": ROWS.name, "index": index,
                         "reward": row.get("reward"),
                         "ledger_total": row.get("ledger_total"),
                         "application_total": row.get("application_total"),
                         "artifact": row.get("artifact"),
                         "application": row.get("application"),
                         "artifact_stored_bytes_digest": row.get("artifact_stored_bytes_digest"),
                         "application_stored_bytes_digest": row.get("application_stored_bytes_digest")})
        cells.append(entry)
    elif ordinal == 10:
        # THE LOST CELL. Reconstructed, never observed: the runner died on the
        # traceback before any record of it was written. Every field the log
        # does not support is UNKNOWN -- not null, not zero.
        cells.append({
            "schema": "piv.cell-disposition/1", "cell_status": mb.CELL_ATTEMPTED_UNSCORED,
            "attempted": True, "quarantined": True, "scored": False,
            "reward": None, "total_tokens": U,
            "selector": selector, "planned_ordinal": ordinal,
            "screen": common["screen"], "selection_digest": common["selection_digest"],
            "schedule_id": common["schedule_id"], "session_id": common["session_id"],
            "model": common["model"], "provider": common["provider"], "endpoint": common["endpoint"],
            "task_id": U, "started_at": U, "finished_at": U,
            "reason": "provider refused the request: free quota exhausted (HTTP 403)",
            "failure_stage": mb.FAILURE_STAGE_INFERENCE,
            "http_status": FROM_LOG["http_status"],
            "provider_error_code": FROM_LOG["provider_error_code"],
            "provider_error_type": FROM_LOG["provider_error_type"],
            "provider_error_message": FROM_LOG["provider_error_message"],
            "provider_request_id": FROM_LOG["provider_request_id"],
            "elapsed_before_refusal_seconds": FROM_LOG["elapsed_before_refusal_seconds"],
            "quota_exhausted": True, "archive_dir": None,
            "stopped_after_planned_ordinal": None,
            "usage_before_failure": {"billed_input_tokens_all_attempts": U,
                                     "billed_output_tokens_all_attempts": U,
                                     "requests_recorded": U, "attempts": U,
                                     "prompt_tokens": U, "completion_tokens": U, "total_tokens": U},
            "trajectory": None, "workspace": U,
            "artifact": U, "application": U,
            "ledger_committed": U, "ledger_scored": U,
            "application_committed": U, "application_scored": U,
            "record": "RECONSTRUCTION -- this cell was never recorded. The 403 escaped one_rollout (the "
                      "defect fixed at 2d6bc76) and the process exited on the traceback, so no row, no "
                      "start record, no archive and no workspace exist for it. What survives is the "
                      "runner's console log, now published beside this record; the fields below are "
                      "parsed out of it, and every field it does not carry stays UNKNOWN.",
            "evidence": {
                "selector, planned ordinal": f"the frozen selection reviews/{SELECTION.name} "
                                             f"({selection['self_digest'][:8]}), execution order index 10",
                "HTTP 403, error code, type, message, request id": f"{LOG_PATH} -- the provider's own error "
                                                                   f"body, echoed verbatim in the traceback "
                                                                   f"that ended the run, parsed rather than "
                                                                   f"retyped",
                "elapsed before the refusal": f"{LOG_PATH} -- the progress bar's reading for the cell that "
                                              f"never finished. The cell therefore SPENT, and its spend is "
                                              f"unrecorded; UNKNOWN below is not zero",
                "everything else": "UNKNOWN: never captured, and not in the log either -- task id, start and "
                                   "end times, workspace, usage, and whether either deliverable was written. "
                                   "A run of the FIXED runner would record all of it "
                                   "(tests/measure_budget.py terminal_row)."},
            "log": {"path": LOG_PATH, **digest(LOG)}})
    else:
        entry = mb.unattempted_cell(common, selector, ordinal,
                                    reason="provider quota exhausted at planned ordinal 10 (HTTP 403); "
                                           "the session made no further request",
                                    stopped_after=10)
        entry["record"] = ("RECONSTRUCTION -- no request was ever made for this cell. It is a different "
                           "object from the lost cell at ordinal 10: not attempted, not quarantined, "
                           "no spend.")
        cells.append(entry)

counts = {}
for entry in cells:
    counts[entry["cell_status"]] = counts.get(entry["cell_status"], 0) + 1

record = {
    "schema": "piv.retrospective-census/1",
    "record_type": "RETROSPECTIVE RECONSTRUCTION -- post-hoc, not an observation",
    "written_at": datetime.now().isoformat(timespec="seconds"),
    "written_by": {"module": "tests/measure_budget.py",
                   "functions": ["cell_disposition", "unattempted_cell", "UNKNOWN"],
                   "added_at": "2d6bc76",
                   "note": "all three were added at 2d6bc76 and are NOT modified by the commit that "
                           "publishes this record, so the build is reproducible from either. No live "
                           "HEAD is recorded: a record cannot name the commit that adds it"},
    "why": ("round18.answer.md:31 -- 'For this historical failure, append a retrospective reconstruction "
            "linked to the log, preserving unknown fields and the original nine rows.' The runner that "
            "ran this screen could not record a failed cell; the fix landed afterwards. This file is the "
            "disposition that runner would have written, reconstructed from what the log does support, "
            "with every unsupported field UNKNOWN."),
    "screen": common["screen"], "selection_digest": common["selection_digest"],
    "subject": selection["subject"]["requested_id"], "split": selection["split"],
    "planned_cells": len(order),
    "disposition": counts,
    "reconstruction_rules": [
        "1. The twelve cells and their order are the frozen selection's `execution_order`, whose "
        "self-digest is the screen's selection digest. Nothing is re-sampled.",
        "2. A cell whose selector appears in the nine observed rows is passed THROUGH "
        "`measure_budget.cell_disposition`, which derives SCORED from the row's own reward and "
        "quarantined fields. The row itself is not modified, and the reward, L, A and both binding "
        "digests are echoed under `original_row_preserved` so this file can be checked against it.",
        "3. `planned_ordinal` is the cell's 1-based index in that order. The rows carry null (the field "
        "postdates the run); every cell says so under `reconstructed_fields`.",
        "4. The cell at ordinal 10 was never recorded at all. It is ATTEMPTED_UNSCORED with reward null. "
        "Its HTTP status, provider error code, type, message and request id are PARSED out of the "
        "published runner log; every field that log does not support is the string UNKNOWN -- never "
        "null, never 0. Each supported fact carries its source under `evidence`.",
        "5. Cells 11 and 12 are `measure_budget.unattempted_cell` entries: attempted false, no task id, "
        "no times, `stopped_after_planned_ordinal` 10.",
    ],
    "builder": {"path": BUILDER, "sha256": lf_sha256(Path(__file__)),
                "note": "published beside this record; re-running it over the same three inputs "
                        "reproduces every field but `written_at`. Every digest here is taken "
                        "over LF bytes, which is what .gitattributes (`* text=auto eol=lf`) "
                        "checks out on every platform"},
    "disposition_note": ("nine scored, one attempted but unscored, two unattempted -- the ruling's own "
                         "disposition (round18.answer.md:7,15). A lost cell and an unattempted cell are "
                         "different objects here, as they now are in the data the fixed runner writes."),
    "observed_log": {
        "rows_file": f"reviews/{ROWS.name}", **digest(ROWS),
        "rows": len(rows),
        "unmodified": "this record READS the nine rows; it does not rewrite, supersede or correct them",
        "per_selector_directory": f"reviews/{ROWS.stem}/",
        "rescued_workspaces": "reviews/cash_application_generated_screen_2026-09-13/workspaces/ (nine cells, "
                              "thirteen files each, copied by hand out of %TEMP% before it was cleaned and "
                              "published there; each file's digests are checked against the result rows by "
                              "reviews/cash_application_generated_screen_2026-09-13/rescore_cash_screen_1.py)",
        "runner_log": {"path": LOG_PATH, **digest(LOG),
                       "note": "the console log of the run, published so the lost cell's reconstruction has "
                               "evidence a reader can check rather than prose to take on trust"},
        "selection_record": {"path": f"reviews/{SELECTION.name}", **digest(SELECTION),
                             "note": "the frozen selection, written before any model call, published "
                                     "here byte-identical to the scratch original"},
        "ruling": "C:/Users/gulte/Desktop/PIV/v10-codex/round18.answer.md",
        "report_to_the_ruling": "C:/Users/gulte/Desktop/PIV/v10-codex/round18.md"},
    "known_limits": [
        "The nine rows' archived breakdowns are all AttributeError: they were produced by the diagnostic "
        "harness before its fix. Their REWARDS are unaffected and are preserved exactly; the "
        "decompositions were replayed separately, as post-run analysis.",
        "The lost cell's usage was never preserved. The nine rows' own 1,084,092 provider-reported "
        "tokens do not reconcile to the console's quota debits, and this record does not claim to.",
        "Every row says provider `nvidia` while recording the Alibaba endpoint. The raw rows are "
        "preserved as they are; the attribution is corrected in analysis, not in the data.",
        "This is a reconstruction. It adds no observation and changes no denominator: the screen remains "
        "twelve planned cells with nine scored outcomes."],
    "cells": cells,
}
# newline="" so the JSON lands LF: byte-identical to what git stores and
# to what every checkout produces.
OUT.write_text(json.dumps(record, indent=1, sort_keys=False, default=str) + "\n",
               encoding="utf-8", newline="")
print("wrote", OUT.name, digest(OUT))
print("disposition", counts)
print("rows file after:", digest(ROWS))
