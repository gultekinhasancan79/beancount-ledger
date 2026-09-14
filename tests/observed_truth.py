"""Rebuild a generated cash-application task's TRUTH REGISTER from the public
evidence in an observed workspace, for offline post-run analysis.

WHY THIS EXISTS. `application/1` scores a submission against the family's
`ApplicationInputs`. For an AUTHORED task that object is a call away
(`tests/test_cash_application_scoring.variant`). For a GENERATED task it is
minted under the evaluator's key, which this analysis is not permitted to
read, so a screen's decompositions could not be replayed at all — and the
live breakdown capture failed on all nine rows, so nothing was archived
either. The counterfactual the adjudicator asked to certify is therefore
reconstructed here, from bytes that were preserved.

WHAT IS RECONSTRUCTED, AND FROM WHAT.

  * the CLOSING REGISTER — the channel the counterfactual is about — is built
    ONLY from public evidence: `open_items.csv` for the opening rows and
    their period basis, the delivered ledger's own `Sale SI-...` entries for
    the invoices raised inside the period, and the fold of the receipts and
    credit notes onto those invoices. Not one register row is copied from the
    submission being scored;
  * the RECEIPT and CREDIT-NOTE folds ARE taken from the submission. Folding
    them from the advice would mean re-solving the task, which would prove
    nothing about the scorer. Taking them from the submission makes
    `receipts_exact` and `credit_exact` 1.0 BY CONSTRUCTION, and that
    assumption is not free: see the pin below;
  * the receipts' statement amounts, dates and remittance ids come from
    `bank_statement.csv` and `remittance_advice.csv`; the credit notes' gross
    from `credit_notes.csv`; `closing_ar` and the write-off movement are the
    delivered ledger's OWN closing balances, not a fold of the submission.

THE PIN. A reconstruction is worth nothing on its own word. `application/1`
stamps every outcome with `result_digest`, a domain-separated SHA-256 over
the whole decomposition — total, the three channel fractions, every penalty,
and one state per receipt, invoice, credit note and tie. The delivery receipt
written during the live run carries that digest. If the outcome produced from
this reconstruction reproduces the live `application_result_digest`, then the
decomposition published from it IS the decomposition the live scorer
computed — including the parts assumed rather than derived, because a wrong
assumption changes a state and so changes the digest. Callers MUST check it;
`tests/test_cash_application_scoring.py` does, and so does the published
rescore record.

What this does NOT do: the ledger. `candidate/1` needs the keyed golden, so
`L` cannot be recomputed offline for a generated task; it is carried as the
live-recorded figure and said to be so.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beancount_ledger.candidate import application as A  # noqa: E402
from beancount_ledger.graph.derive import ApplicationInputs  # noqa: E402

RECEIVABLES = "Assets:AR"
WRITE_OFFS = "Expenses:SmallBalanceWriteOffs"
_ZERO = Decimal("0.00")
_SALE = re.compile(r"^Sale (SI-\d+)$")
_TXN = re.compile(r'^(\d{4}-\d{2}-\d{2}) \* "([^"]*)" "(.*)"$')
_POSTING = re.compile(r"^\s+([A-Za-z][A-Za-z0-9:\-]*)\s+(-?[\d,]+\.\d{2})\s+USD\s*$")

#: The files this reconstruction reads. A workspace missing one cannot be
#: reconstructed, and saying so beats a silent partial answer.
REQUIRED = ("cash_application.json", "ledger.beancount", "open_items.csv",
            "bank_statement.csv", "credit_notes.csv", "remittance_advice.csv")


def _q2(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def parse_ledger(text: str) -> tuple[list[dict], dict]:
    """(transactions, balances). A transaction is
    {date, payee, narration, postings: [(account, Decimal)]}; balances are the
    signed sums by account. Deliberately a small reader over the shape the
    family renders, not a Beancount load: the scorer never sees this text and
    this must not depend on a plugin's opinion."""
    transactions, balances, current = [], {}, None
    for line in text.replace("\r\n", "\n").split("\n"):
        header = _TXN.match(line)
        if header:
            current = {"date": header.group(1), "payee": header.group(2),
                       "narration": header.group(3), "postings": []}
            transactions.append(current)
            continue
        posting = _POSTING.match(line)
        if posting and current is not None:
            account, amount = posting.group(1), Decimal(posting.group(2).replace(",", ""))
            current["postings"].append((account, amount))
            balances[account] = balances.get(account, _ZERO) + amount
            continue
        if line.strip() and not line.startswith((" ", "\t")):
            current = None          # an option, an open, a blank: the transaction ended
    return transactions, balances


def period_sales(transactions: list[dict]) -> list[tuple[str, str, Decimal]]:
    """(invoice_id, customer, period_basis) for every sale RAISED IN THE
    PERIOD, read off the delivered ledger: a `Sale SI-....` narration with a
    positive receivables posting. This is the public fact the diagnosis rests
    on — the omitted invoices were raised inside the period and the solver's
    own ledger says so."""
    sales = []
    for txn in transactions:
        match = _SALE.match(txn["narration"])
        if not match:
            continue
        basis = sum((amount for account, amount in txn["postings"] if account == RECEIVABLES), _ZERO)
        if basis > 0:
            sales.append((match.group(1), txn["payee"], _q2(basis)))
    return sales


def _receipt_lines(workspace: Path) -> list[tuple[str, str, str, Decimal]]:
    """(receipt_id, date, customer, statement credit) for every customer
    receipt on the bank statement, in statement order."""
    advice = _rows(workspace / "remittance_advice.csv")
    by_reference = {row["payment_reference"]: row["customer"] for row in advice}
    lines = []
    for row in _rows(workspace / "bank_statement.csv"):
        if not row.get("credit") or not row.get("reference"):
            continue
        if not row["description"].startswith("ACH IN"):
            continue
        reference = row["reference"]
        customer = by_reference.get(reference) or row["description"][len("ACH IN "):].title()
        lines.append((f"{row['date']}:{reference}", row["date"], customer, _q2(row["credit"])))
    return lines


def _remittance_ids(workspace: Path) -> dict:
    out = {}
    for row in _rows(workspace / "remittance_advice.csv"):
        out.setdefault(row["payment_reference"], row["remittance_id"])
    return out


def reconstruct(workspace: Path, *, application_text: str | None = None):
    """(truth, expected_balances, provenance) for one observed workspace.

    `application_text` defaults to the workspace's delivered
    `cash_application.json`; a counterfactual passes its own bytes AND still
    gets the truth built from the delivered evidence, because a counterfactual
    that moves the answer as well as the submission proves nothing.
    """
    workspace = Path(workspace)
    missing = [name for name in REQUIRED if not (workspace / name).is_file()]
    if missing:
        raise FileNotFoundError(f"{workspace}: no {', '.join(missing)}")

    delivered_text = (workspace / "cash_application.json").read_text(encoding="utf-8")
    transactions, balances = parse_ledger((workspace / "ledger.beancount").read_text(encoding="utf-8"))
    closing_ar = _q2(balances.get(RECEIVABLES, _ZERO))
    write_off_movement = _q2(balances.get(WRITE_OFFS, _ZERO))

    # the submission's own folds, canonicalised by the shipped parse boundary.
    # `parse_application` needs an ApplicationInputs only for the credit-note
    # grosses, so it is run twice: once against a skeleton carrying just those,
    # and (by the caller) once against the finished truth.
    credit_rows = _rows(workspace / "credit_notes.csv")
    skeleton = ApplicationInputs(
        receivables_account=RECEIVABLES, write_off_account=WRITE_OFFS, tolerance=Decimal("25.00"),
        opening_ar=_ZERO, closing_ar=closing_ar, opening_register=(), invoices=(), receipts=(),
        credit_notes=tuple((row["credit_note_id"], row["date"], row["customer"], _q2(row["gross_amount"]),
                            (), _ZERO, "") for row in credit_rows),
        register=())
    delivered = A.parse_application(delivered_text, skeleton)
    if not isinstance(delivered, A.ParsedApplication):
        raise ValueError(f"{workspace}: the delivered application does not parse: {delivered}")

    receipts = []
    remittance = _remittance_ids(workspace)
    for receipt_id, date, customer, amount in _receipt_lines(workspace):
        record = delivered.receipt(receipt_id)
        if record is None:
            raise ValueError(f"{workspace}: the submission has no receipt {receipt_id}; the fold cannot be taken "
                             f"from it and this reconstruction does not re-solve the task")
        reference = receipt_id.split(":", 1)[1]
        receipts.append((receipt_id, date, customer, amount, tuple(sorted(record.applied)),
                         tuple(sorted(record.written_off)), record.unapplied,
                         remittance.get(reference, ""), "", ""))

    credit_notes = []
    for row in credit_rows:
        record = delivered.credit_note(row["credit_note_id"])
        if record is None:
            raise ValueError(f"{workspace}: the submission has no credit note {row['credit_note_id']}")
        credit_notes.append((row["credit_note_id"], row["date"], row["customer"], _q2(row["gross_amount"]),
                             tuple(sorted(record.applied)), record.unapplied, ""))

    # ---- the register, from public evidence only ---------------------------
    opening = [(row["invoice_id"], row["customer"], row["invoice_date"], row["due_date"],
                _q2(row["original_amount"]), _q2(row["open_balance"])) for row in _rows(workspace / "open_items.csv")]
    basis = {row[0]: (row[1], row[5], "register") for row in opening}
    for invoice_id, customer, amount in period_sales(transactions):
        if invoice_id in basis:
            raise ValueError(f"{workspace}: {invoice_id} is both an opening item and an in-period sale")
        basis[invoice_id] = (customer, amount, "sale")

    applied_total, credited, written_off = {}, {}, {}
    for receipt in receipts:
        for invoice_id, amount in receipt[4]:
            applied_total[invoice_id] = applied_total.get(invoice_id, _ZERO) + amount
        for invoice_id, amount in receipt[5]:
            written_off[invoice_id] = written_off.get(invoice_id, _ZERO) + amount
    for credit in credit_notes:
        for invoice_id, amount in credit[4]:
            credited[invoice_id] = credited.get(invoice_id, _ZERO) + amount
    stranded = (set(applied_total) | set(credited) | set(written_off)) - set(basis)
    if stranded:
        raise ValueError(f"{workspace}: the submission applies cash to {sorted(stranded)}, which the public "
                         f"evidence does not carry as invoices")

    register = []
    for invoice_id in sorted(basis):
        customer, face, _source = basis[invoice_id]
        paid, credit, wo = (applied_total.get(invoice_id, _ZERO), credited.get(invoice_id, _ZERO),
                            written_off.get(invoice_id, _ZERO))
        register.append((invoice_id, customer, face, paid, credit, wo, _q2(face - paid - credit - wo)))

    truth = ApplicationInputs(
        receivables_account=RECEIVABLES, write_off_account=WRITE_OFFS, tolerance=Decimal("25.00"),
        opening_ar=_q2(sum((row[5] for row in opening), _ZERO)), closing_ar=closing_ar,
        opening_register=tuple(opening),
        invoices=tuple((invoice_id, basis[invoice_id][0], "", basis[invoice_id][1], basis[invoice_id][2])
                       for invoice_id in sorted(basis)),
        receipts=tuple(receipts), credit_notes=tuple(credit_notes), register=tuple(register))

    expected_balances = ((RECEIVABLES, closing_ar), (WRITE_OFFS, write_off_movement))
    provenance = {
        "register_rows_from_public_evidence": len(register),
        "opening_items": len(opening),
        "in_period_sales": [[invoice_id, str(basis[invoice_id][1])]
                            for invoice_id in sorted(basis) if basis[invoice_id][2] == "sale"],
        "closing_ar_from_delivered_ledger": str(closing_ar),
        "write_off_movement_from_delivered_ledger": str(write_off_movement),
        "receipt_folds_taken_from": "the submission (see the module docstring; pinned by the result digest)",
        "credit_folds_taken_from": "the submission (same pin)",
    }
    if application_text is None:
        return truth, expected_balances, provenance, delivered_text
    return truth, expected_balances, provenance, application_text


def score(workspace: Path, application_text: str | None = None):
    """(parsed, outcome, truth, expected_balances, provenance) — the shipped
    parse boundary and the shipped `score_application`, nothing local."""
    truth, expected_balances, provenance, text = reconstruct(workspace, application_text=application_text)
    parsed = A.parse_application(text, truth)
    if not isinstance(parsed, A.ParsedApplication):
        raise ValueError(f"{workspace}: the application does not parse: {parsed}")
    outcome = A.score_application(parsed, truth, expected_balances=expected_balances)
    outcome.verify()
    return parsed, outcome, truth, expected_balances, provenance


def decomposition(outcome) -> dict:
    """The whole outcome as publishable data: both halves of what the failed
    live breakdown was supposed to capture, for the application engine."""
    return {
        "engine": outcome.engine_id,
        "total": str(outcome.total),
        "components": {name: str(value) for name, value in outcome.components},
        "penalties": [list(p) for p in outcome.penalties],
        "receipt_states": {subject: str(state) for subject, state in outcome.receipt_states},
        "invoice_states": {subject: str(state) for subject, state in outcome.invoice_states},
        "credit_states": {subject: str(state) for subject, state in outcome.credit_states},
        "tie_states": {subject: str(state) for subject, state in outcome.tie_states},
        "status": outcome.status,
        "delivered": outcome.delivered,
        "application_digest": outcome.application_digest,
        "result_digest": outcome.result_digest,
    }


def corrected_text(delivered_text: str, rows: list[dict]) -> str:
    """The counterfactual document: the delivered bytes with ONLY the named
    closing rows added, in invoice order, and every other byte of the document
    left alone. Built by editing the parsed document and re-emitting it with
    the delivered file's own formatting, so the published diff is exactly the
    added rows."""
    document = json.loads(delivered_text)
    if json.dumps(document, indent=1) + "\n" != delivered_text:
        raise ValueError("the delivered bytes do not round-trip through this emitter, so a diff against them "
                         "would show reformatting as well as the added rows; refusing to publish one")
    register = list(document["closing_open_items"])
    known = {row["invoice_id"] for row in register}
    for row in rows:
        if row["invoice_id"] in known:
            raise ValueError(f"{row['invoice_id']} is already in the delivered register")
        register.append(row)
    document["closing_open_items"] = sorted(register, key=lambda row: row["invoice_id"])
    return json.dumps(document, indent=1) + "\n"
