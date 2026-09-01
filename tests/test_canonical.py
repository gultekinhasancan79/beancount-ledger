"""Canonical bytes, bounded numbers, the string policy, and two identities.

    candidate_digest      structural: what was parsed, as written
    semantic_fingerprint  the task's equivalence: what it means

The encoder is pinned by golden vectors with exact bytes, by a
cross-process shuffled-construction test, and by refusals of everything
whose identity would be ambient (floats, sets, non-string keys, NaN). The
numeric bounds are exercised at both gates. The string policy is exercised
in both directions. And the two identities are pinned by paired vectors:
posting order, narration and transaction order change the structural
identity and not the semantic one; an amount changes both; a composed and
a decomposed payee share both, while their source digests differ.

    python tests/test_canonical.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beancount_ledger.candidate import canonical as C  # noqa: E402
from beancount_ledger.candidate.normalise import Accepted, ProtocolFailure, parse_once  # noqa: E402
from beancount_ledger.candidate.schema import SafeParsedSubmission  # noqa: E402


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        for line in str(detail).splitlines()[:12]:
            print(f"      {line}")
    return ok


BASE = """option "operating_currency" "USD"
2025-11-01 open Assets:Bank:Checking USD
2025-11-01 open Assets:AR USD
2025-11-01 open Expenses:BankFees USD
2025-11-01 open Expenses:Office USD
2025-11-01 open Equity:Opening USD
2025-11-01 * "Opening"
  Assets:Bank:Checking  1000.00 USD
  Equity:Opening       -1000.00 USD
2025-11-26 * "Harbor Freight Ltd" "Customer payment for SI-1044"
  Assets:Bank:Checking  4800.00 USD
  Assets:AR            -4800.00 USD
2025-11-30 * "Cascade Bank" "Monthly account service charge"
  Expenses:BankFees  85.00 USD
  Assets:Bank:Checking -85.00 USD
2025-11-30 * "Staples" "Office supplies"
  Expenses:Office  40.00 USD
  Assets:Bank:Checking -40.00 USD
"""

FEE = ('2025-11-30 * "Cascade Bank" "Monthly account service charge"\n'
       "  Expenses:BankFees  85.00 USD\n  Assets:Bank:Checking -85.00 USD\n")
OFFICE = ('2025-11-30 * "Staples" "Office supplies"\n'
          "  Expenses:Office  40.00 USD\n  Assets:Bank:Checking -40.00 USD\n")
RECEIPT = ('2025-11-26 * "Harbor Freight Ltd" "Customer payment for SI-1044"\n'
           "  Assets:Bank:Checking  4800.00 USD\n  Assets:AR            -4800.00 USD\n")


def parsed(text):
    """(submission, candidate, structural id, semantic id) from an accepted or
    domain-invalid parse; anything else is a test failure."""
    result = parse_once(text)
    if isinstance(result, Accepted):
        return result.submission, result.candidate, result.candidate_digest, result.semantic_fingerprint
    raise AssertionError(f"not parsed: {result}")


# --------------------------------------------------------------------------
# the encoder
# --------------------------------------------------------------------------

GOLDEN_VECTORS = [
    ({"b": 1, "a": "x"}, '{"a":"x","b":1}'),
    (["z", {"k": None}, True, False], '["z",{"k":null},true,false]'),
    ('a"b\\c\n é😀/', '"a\\"b\\\\c\\u000a\\u2028é😀/"'),
    (Decimal("85.00"), "85"),
    (Decimal("0.10"), "0.1"),
    (Decimal("-0.00"), "0"),
    (Decimal("1E+5"), "100000"),
    (Decimal("1.5E-3"), "0.0015"),
    ({"amount": Decimal("4800.00"), "n": 0}, '{"amount":4800,"n":0}'),
    ({"é": 1, "é": 2, "z": 3}, None),   # code-point key order, no normalisation: filled below
]
GOLDEN_VECTORS[-1] = (GOLDEN_VECTORS[-1][0], '{"é":2,"z":3,"é":1}')


def test_golden_vectors_pin_exact_bytes():
    problems = []
    for obj, expected in GOLDEN_VECTORS:
        got = C.canonical_bytes(obj).decode("utf-8")
        if got != expected:
            problems.append(f"{obj!r}: got {got!r}, expected {expected!r}")
    return check("golden vectors: exact canonical bytes", not problems, "\n".join(problems))


def test_the_encoder_refuses_ambient_identity():
    cases = {
        "float": 1.5, "set": {1, 2}, "frozenset": frozenset("ab"), "non-str key": {1: "a"},
        "nan": Decimal("NaN"), "infinity": Decimal("Infinity"), "object": object(),
        "huge exponent": Decimal("1E+999999"), "tiny exponent": Decimal("1E-999999"),
        "21 digits": Decimal("123456789012345678901"), "bool-as-key": {True: 1},
    }
    problems = []
    for label, value in cases.items():
        try:
            C.canonical_bytes(value)
            problems.append(f"{label}: accepted")
        except (C.CanonicalError, C.NumberOutOfBounds):
            pass
    try:
        C.canonical_bytes("x" * (C.MAX_CANONICAL_BYTES + 1))
        problems.append("byte cap not enforced")
    except C.CanonicalError:
        pass
    return check("the encoder refuses floats, sets, non-string keys, NaN, out-of-bound numbers, oversize",
                 not problems, "\n".join(problems))


def test_decimal_canonical_is_value_identity_and_context_free():
    problems = []
    for text, expected in (("85", "85"), ("85.0", "85"), ("85.00", "85"), ("+85", "85"), ("-0", "0"),
                           ("-0.00", "0"), ("0E+9", "0"), ("0.10", "0.1"), ("100", "100"),
                           ("1E+5", "100000"), ("-4800.00", "-4800"), ("0.00000001", "0.00000001")):
        got = C.canonical_decimal(Decimal(text))
        if got != expected:
            problems.append(f"{text}: {got} != {expected}")
    with localcontext() as ctx:
        ctx.prec = 3                                       # normalize() would round here
        if C.canonical_decimal(Decimal("123456.78")) != "123456.78":
            problems.append("canonical form depends on the Decimal context")
    if C.bounded_decimal(Decimal("85.000000000000000")) != Decimal("85.000000000000000"):
        problems.append("a badly spelled 85 was not accepted as the value 85")
    for text, reason in (("1E+16", "number.magnitude"), ("0.000000001", "number.scale"),
                         ("123456789012345678901", "number.precision"), ("NaN", "number.not_finite")):
        try:
            C.bounded_decimal(Decimal(text))
            problems.append(f"{text}: accepted")
        except C.NumberOutOfBounds as exc:
            if exc.reason != reason:
                problems.append(f"{text}: {exc.reason} != {reason}")
    if C.canonical_decimal(Decimal(85)) != C.canonical_decimal(Decimal("85.00")):
        problems.append("int and scaled decimal differ")
    return check("decimal canonical: value identity, signed zero -> 0, context-free, bounded",
                 not problems, "\n".join(problems))


def test_cross_process_shuffled_construction_is_deterministic():
    """Three fresh interpreters, three insertion orders, one digest."""
    script = (
        "import random, sys\n"
        "sys.path.insert(0, sys.argv[2])\n"
        "from decimal import Decimal\n"
        "from beancount_ledger.candidate import canonical as C\n"
        "random.seed(int(sys.argv[1]))\n"
        "items = [('zeta', [3, 2, 1]), ('alpha', {'y': Decimal('85.00'), 'x': 'é'}), ('mid', None), ('tags', ['b', 'a'])]\n"
        "random.shuffle(items)\n"
        "obj = {}\n"
        "for k, v in items:\n"
        "    obj[k] = v\n"
        "print(C.domain_digest(b'piv:test:v1\\0', C.canonical_bytes(obj)))\n"
    )
    digests = set()
    for seed in (1, 2, 3):
        out = subprocess.run([sys.executable, "-c", script, str(seed), str(ROOT)],
                             capture_output=True, text=True, timeout=120)
        digests.add(out.stdout.strip() or f"ERR:{out.stderr[-200:]}")
    ok = len(digests) == 1 and not next(iter(digests)).startswith("ERR")
    return check("cross-process, shuffled construction: one digest", ok, f"{digests}")


def test_canonical_sorted_orders_by_encoded_bytes():
    items = [{"a": Decimal("10")}, {"a": Decimal("9")}, {"a": "x"}]
    ordered = C.canonical_sorted(items)
    encoded = [C.canonical_bytes(i) for i in ordered]
    return check("semantic sets sort by canonical bytes, not object ordering",
                 encoded == sorted(encoded), f"{encoded}")


# --------------------------------------------------------------------------
# the string policy
# --------------------------------------------------------------------------

def test_string_policy_both_directions():
    problems = []
    composed, decomposed = "Café", "Café"
    if C.canonical_text(composed, field="payee") != C.canonical_text(decomposed, field="payee"):
        problems.append("NFC did not unify composed and decomposed text")
    for label, value in (("bidi override", "ab‮cd"), ("control", "a\x07b"), ("zero-width joiner", "a‍b"),
                         ("noncharacter", "a￾b"), ("private use", "ab"), ("too long", "x" * 201),
                         ("not text", 42)):
        try:
            C.canonical_text(value, field="payee")
            problems.append(f"{label}: accepted")
        except C.StringPolicyViolation:
            pass
    for label, value, grammar in (("lowercase root", "assets:Bank", C.ACCOUNT_GRAMMAR),
                                  ("unicode account", "Assets:Bañk", C.ACCOUNT_GRAMMAR),
                                  ("short date", "2025-1-1", C.DATE_GRAMMAR),
                                  ("tag with space", "a b", C.TAG_GRAMMAR),
                                  ("lowercase currency", "usd", C.CURRENCY_GRAMMAR),
                                  ("two-char flag", "**", C.FLAG_GRAMMAR)):
        try:
            C.canonical_identifier(value, grammar, field=label)
            problems.append(f"{label}: accepted (near-match repaired?)")
        except C.StringPolicyViolation:
            pass
    for value, grammar in (("Assets:Bank:Checking", C.ACCOUNT_GRAMMAR), ("2025-11-30", C.DATE_GRAMMAR),
                           ("USD", C.CURRENCY_GRAMMAR), ("*", C.FLAG_GRAMMAR), ("q4-close", C.TAG_GRAMMAR)):
        if C.canonical_identifier(value, grammar, field="ok") != value:
            problems.append(f"{value}: changed by validation")
    return check("string policy: NFC for text, forbidden code points refused, grammars exact and unrepaired",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# structural versus semantic identity, through the boundary
# --------------------------------------------------------------------------

def test_paired_vectors_separate_structural_from_semantic_identity():
    base_sub, base_cand, base_cd, base_sf = parsed(BASE)
    variants = {
        "posting order swapped": BASE.replace(
            "  Expenses:BankFees  85.00 USD\n  Assets:Bank:Checking -85.00 USD\n",
            "  Assets:Bank:Checking -85.00 USD\n  Expenses:BankFees  85.00 USD\n"),
        "narration changed": BASE.replace("Monthly account service charge", "Bank fee for November"),
        "same-date transactions swapped": BASE.replace(FEE + OFFICE, OFFICE + FEE),
        "amount spelled 85 not 85.00": BASE.replace("Expenses:BankFees  85.00 USD", "Expenses:BankFees  85 USD"),
        "amount spelled 85.000000000000000": BASE.replace("Expenses:BankFees  85.00 USD",
                                                          "Expenses:BankFees  85.000000000000000 USD"),
        # The pinned parser sorts by date, so source order ACROSS dates is
        # not observable: this is documented, not a defect, and pinned here.
        "different-date transactions swapped": BASE.replace(RECEIPT + FEE, FEE + RECEIPT),
    }
    same_structure = {"amount spelled 85 not 85.00", "amount spelled 85.000000000000000",
                      "different-date transactions swapped"}
    problems = []
    for label, text in variants.items():
        _, _, cd, sf = parsed(text)
        if sf != base_sf:
            problems.append(f"{label}: semantic fingerprint changed")
        if label in same_structure:
            if cd != base_cd:
                problems.append(f"{label}: structural identity changed")
        elif cd == base_cd:
            problems.append(f"{label}: structural identity did not change")
    _, _, cd, sf = parsed(BASE.replace("Expenses:BankFees  85.00 USD", "Expenses:BankFees  86.00 USD")
                          .replace("Assets:Bank:Checking -85.00 USD", "Assets:Bank:Checking -86.00 USD"))
    if cd == base_cd or sf == base_sf:
        problems.append("an amount change left an identity unchanged")
    from beancount_ledger.beancount_ledger import digests_of
    composed = BASE.replace("Cascade Bank", "Café Bank")
    decomposed = BASE.replace("Cascade Bank", "Café Bank")
    _, _, cd1, sf1 = parsed(composed)
    sub2, _, cd2, sf2 = parsed(decomposed)
    if cd1 != cd2 or sf1 != sf2:
        problems.append("composed and decomposed payee have different identities")
    if digests_of(composed.encode("utf-8"))["logical_text_digest"] == digests_of(decomposed.encode("utf-8"))["logical_text_digest"]:
        problems.append("the source digests did not distinguish composed from decomposed")
    stored = [d.payee for d in sub2.directives if getattr(d, "payee", None) and "Bank" in d.payee]
    if stored != ["Café Bank"]:
        problems.append(f"the candidate did not store the NFC value: {stored!r}")
    return check("paired vectors: order/narration change structural not semantic; amount changes both; NFC unifies",
                 not problems, "\n".join(problems))


def test_the_submission_is_minted_only_by_the_boundary_and_is_immutable():
    problems = []
    try:
        SafeParsedSubmission("USD", None, ())
        problems.append("constructed without the mint")
    except TypeError:
        pass
    sub, cand, _, _ = parsed(BASE)
    for target, attr in ((sub, "title"), (sub.directives[0], "date"), (cand, "operating_currency")):
        try:
            setattr(target, attr, "x")
            problems.append(f"{type(target).__name__}.{attr} is mutable")
        except Exception:
            pass
    if not isinstance(sub.directives, tuple) or not all(isinstance(d.postings, tuple) for d in sub.directives if hasattr(d, "postings")):
        problems.append("nested collections are not tuples")
    source = (ROOT / "beancount_ledger").rglob("*.py")
    users = [p.name for p in source if "_MINT" in p.read_text(encoding="utf-8")]
    if sorted(users) != ["normalise.py", "schema.py"]:
        problems.append(f"the mint is referenced outside the boundary: {users}")
    return check("SafeParsedSubmission: minted only by the boundary, deeply immutable, mint referenced in two files",
                 not problems, "\n".join(problems))


def test_numeric_bounds_at_both_gates():
    problems = []
    huge_run = BASE.replace("Expenses:BankFees  85.00 USD", "Expenses:BankFees  " + "1" * 45 + ".00 USD")
    r = parse_once(huge_run)
    if not isinstance(r, ProtocolFailure) or r.reason != "envelope.number_length":
        problems.append(f"45-digit run: {r}")
    many_digits = BASE.replace("Expenses:BankFees  85.00 USD", "Expenses:BankFees  " + "1" * 25 + ".00 USD")
    r = parse_once(many_digits)
    if not isinstance(r, ProtocolFailure) or r.reason != "number.precision":
        problems.append(f"25 significant digits: {r}")
    exponent = BASE.replace("Expenses:BankFees  85.00 USD", "Expenses:BankFees  8.5E+1 USD")
    r = parse_once(exponent)
    if not isinstance(r, ProtocolFailure) or r.reason != "parse.errors":
        problems.append(f"exponent notation: {r}")
    bidi = BASE.replace("Cascade Bank", "Cascade‮ Bank")
    r = parse_once(bidi)
    if not isinstance(r, ProtocolFailure) or r.reason != "string.forbidden_codepoint":
        problems.append(f"bidi in payee: {r}")
    return check("numeric and string bounds refuse at the lexical gate and at the parsed value, by name",
                 not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# provenance digests
# --------------------------------------------------------------------------

def test_parse_policy_digest_is_declared_data():
    from beancount_ledger.candidate import normalise as N
    problems = []
    view = C.parse_policy_view()
    if view["parser"]["version"] != "3.2.3":
        problems.append(f"parser version not pinned in the policy: {view['parser']}")
    if C.parse_policy_digest() != C.parse_policy_digest():
        problems.append("policy digest is not stable")
    before = C.parse_policy_digest()
    real = N.MAX_LINES
    N.MAX_LINES = real - 1
    try:
        changed = C.parse_policy_digest() != before
    finally:
        N.MAX_LINES = real
    if not changed:
        problems.append("a limit change did not change the policy digest")
    text = json.dumps(view, default=str)
    if "<" in text or "\\\\" in text or ":\\" in text:
        problems.append("the policy view contains a repr, a callable or a path")
    return check("parse policy digest: pinned parser version, stable, sensitive to limits, declared data only",
                 not problems, "\n".join(problems))


def test_task_contract_digest_ignores_documentation_keys():
    task = json.loads((ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json").read_text(encoding="utf-8"))
    base = C.task_contract_digest(task)
    with_doc = dict(task, _extra_doc="commentary")
    changed = dict(task, scored_accounts=list(task["scored_accounts"]) + ["Assets:Inventory"])
    ok = C.task_contract_digest(with_doc) == base and C.task_contract_digest(changed) != base
    return check("task contract digest: _doc keys ignored, a normative change is visible", ok)


def test_rejection_payload_is_bounded_sorted_and_message_free():
    diagnostics = [("parse.errors", 10, 2, "message A"), ("control.plugin", 3, None), ("parse.errors", 10, 1)]
    payload = C.rejection_payload(diagnostics)
    rows = payload["diagnostics"]
    problems = []
    if rows != sorted(rows, key=lambda r: (r["code"], r["line"], r["column"])):
        problems.append("not sorted")
    if any("message" in r for r in rows) or "message A" in json.dumps(payload):
        problems.append("a message entered the payload")
    if rows[0]["column"] != -1:
        problems.append("missing column is not the sentinel -1")
    flood = [("parse.errors", i, 0) for i in range(5000)]
    big = C.rejection_payload(flood)
    if len(big["diagnostics"]) != C.MAX_OUTCOME_DIAGNOSTICS or not big["truncated"]:
        problems.append("diagnostic flood not capped")
    a = C.outcome_digest("ProtocolRejected", payload, "t", "p")
    b = C.outcome_digest("ProtocolRejected", C.rejection_payload([(c, l, col) for c, l, col, *_ in diagnostics]), "t", "p")
    if a != b:
        problems.append("wording changed the outcome identity")
    if C.outcome_digest("Accepted", payload, "t", "p") == a:
        problems.append("the variant tag is not bound")
    if C.outcome_digest("ProtocolRejected", payload, "t2", "p") == a:
        problems.append("the task contract digest is not bound")
    return check("rejection payload: sorted, capped at 50, message-free; outcome digest binds variant and provenance",
                 not problems, "\n".join(problems))


def test_domain_violations_are_accepted_with_names_not_rejected():
    """`Accepted` means safe and representable, not domain-perfect.

    A safely parsed ledger with an unbalanced entry, a posting to an
    undeclared account, a duplicate `open`, or a missing declaration is read,
    closed and identified, and its violations are NAMED so the task policy
    can price each one; only an unsupported shape is a protocol rejection.
    """
    problems = []
    cases = {
        "unbalanced": (BASE.replace("Assets:Bank:Checking -85.00 USD", "Assets:Bank:Checking -80.00 USD"),
                       {"event.unbalanced"}),
        "posting to an undeclared account": (BASE.replace("Expenses:Office  40.00 USD", "Expenses:Rent  40.00 USD"),
                                             {"posting.account_not_open"}),
        "duplicate open": (BASE.replace("2025-11-01 open Assets:AR USD\n",
                                        "2025-11-01 open Assets:AR USD\n2025-11-02 open Assets:AR USD\n"),
                           {"lifecycle.duplicate_open"}),
        "missing opening declaration": (BASE.replace("2025-11-01 open Expenses:Office USD\n", ""),
                                        {"posting.account_not_open"}),
    }
    from beancount_ledger.candidate.policy import apply_policy
    for label, (text, expected) in cases.items():
        r = parse_once(text)
        if not isinstance(r, Accepted):
            problems.append(f"{label}: {type(r).__name__} {r}")
            continue
        codes = {f.code for f in r.domain_findings}
        if not expected <= codes:
            problems.append(f"{label}: findings {sorted(codes)} lack {sorted(expected)}")
        if r.domain_valid:
            problems.append(f"{label}: reported domain-valid")
        if r.submission is None or not r.candidate_digest:
            problems.append(f"{label}: no structural identity")
        outcome = apply_policy(1.0, r.finding_summary)      # the policy reads the SUMMARY
        if not {"total", "gated", "renderable", "zeroed_components"} <= set(outcome):
            problems.append(f"{label}: policy outcome incomplete: {outcome}")
        if set(r.finding_summary.codes) != codes:
            problems.append(f"{label}: summary codes {r.finding_summary.codes} != sample codes {sorted(codes)}")
    one = parse_once(cases["unbalanced"][0])
    if isinstance(one, Accepted) and len(one.domain_findings) != 1:
        problems.append(f"valid plus one violation: {len(one.domain_findings)} findings")
    r = parse_once(BASE + "2025-11-30 balance Assets:AR 0 USD\n")
    if not isinstance(r, ProtocolFailure) or not r.reason.startswith("directive.balance"):
        problems.append(f"unsupported shape: {r}")
    clean = parse_once(BASE)
    if not isinstance(clean, Accepted) or clean.domain_findings or clean.oracle_diagnostics:
        problems.append(f"the base ledger is not accepted clean: {clean}")
    # the oracle is evidence, not authority: it is carried separately and
    # agrees with the normative validator on every case above
    for label, (text, _) in cases.items():
        r = parse_once(text)
        if isinstance(r, Accepted) and not r.oracle_diagnostics:
            problems.append(f"{label}: the differential oracle saw nothing where the validator did")
    return check("domain violations -> Accepted with named findings the policy prices; unsupported shape -> protocol",
                 not problems, "\n".join(problems))


def test_the_digit_scan_is_token_aware():
    """A numeric limit applies to numeric tokens, not to strings or comments."""
    problems = []
    ref41 = "1" * 41
    quoted = BASE.replace('"Customer payment for SI-1044"\n', f'"Customer payment for SI-1044"\n  invoice: "{ref41}"\n')
    r = parse_once(quoted)
    if not isinstance(r, Accepted) or ("invoice", ref41) not in [p for d in r.submission.directives for p in getattr(d, "source_refs", ())]:
        problems.append(f"41-digit quoted reference: {r if not isinstance(r, Accepted) else 'ref not stored'}")
    r = parse_once(BASE + f"; {'2' * 41}\n")
    if not isinstance(r, Accepted):
        problems.append(f"41-digit comment: {r}")
    r = parse_once(BASE.replace('"Office supplies"', '"Office \\" supplies ' + "3" * 43 + '"'))
    if not isinstance(r, Accepted):
        problems.append(f"digits after an escaped quote inside a string: {r}")
    r = parse_once(BASE.replace("Expenses:BankFees  85.00 USD", f"Expenses:BankFees  {'4' * 41}.00 USD"))
    if not isinstance(r, ProtocolFailure) or r.reason != "envelope.number_length":
        problems.append(f"41-digit numeric token: {r}")
    r = parse_once(BASE + '2025-11-30 * "Unclosed\n')
    if not isinstance(r, ProtocolFailure) or r.reason != "lexical.unclosed_string":
        problems.append(f"unclosed string: {r}")
    if C.longest_numeric_digit_run('"111111" ; 2222222\n 3333 x') != 4:
        problems.append("scanner counted digits inside a string or a comment")
    return check("digit scan: quoted references and comments follow their own limits; numeric tokens follow the numeric one",
                 not problems, "\n".join(problems))


def test_unicode_database_is_part_of_the_policy():
    import unicodedata
    problems = []
    view = C.parse_policy_view()
    if view["unicode"]["database_version"] != unicodedata.unidata_version:
        problems.append("Unicode database version not in the policy view")
    if unicodedata.category("‮") != "Cf" or unicodedata.normalize("NFC", "Café") != "Café":
        problems.append("pinned Unicode behaviour changed under this runtime")
    real = C.TEXT_MAX_CODEPOINTS
    before = C.parse_policy_digest()
    C.TEXT_MAX_CODEPOINTS = real - 1
    try:
        if C.parse_policy_digest() == before:
            problems.append("a string-policy change did not change the policy digest")
    finally:
        C.TEXT_MAX_CODEPOINTS = real
    payload = C.rejection_payload([("parse.errors", i, 0) for i in range(20_000)])
    if payload["total"] != C.MAX_TOTAL_DIAGNOSTICS:
        problems.append(f"total not saturated: {payload['total']}")
    return check("policy identity binds the Unicode database and the string limits; diagnostic total saturates",
                 not problems, "\n".join(problems))


PENALTY_KEYS = ("target_misses", "collateral_damage", "unresolved_planted", "removed_or_altered", "fabricated",
                "merged_events", "undocumented", "plug_accounts", "added_prose", "padding", "balance_errors")


def score_vector(detail: dict) -> dict:
    """Every component and penalty of the real scorer, not only the total —
    two unintended movements can cancel in a total."""
    vec = {"total": str(detail.get("total")), "parse_ok": bool(detail.get("parse_ok")),
           "components": {k: str(v) for k, v in (detail.get("components") or {}).items()}}
    for key in PENALTY_KEYS:
        vec[key] = len(detail.get(key) or [])
    return vec


def moved_keys(a: dict, b: dict) -> set:
    return {k for k in a if a[k] != b.get(k)}


# What each (role, field) mutation may move in the real scorer, by contract.
# Narrower than "something moved": an observed mutation must move only the
# named components/penalties (plus the total).
EXPECTED_MOVEMENT = {
    ("pre_existing", "txn.narration"): {"removed_or_altered", "fabricated"},
    ("pre_existing", "txn.payee"): {"removed_or_altered", "fabricated"},
    ("pre_existing", "txn.flag"): {"removed_or_altered", "fabricated"},
    ("pre_existing", "txn.date"): {"removed_or_altered", "fabricated"},
    ("pre_existing", "txn.tags"): {"removed_or_altered", "fabricated"},
    ("pre_existing", "txn.links"): {"removed_or_altered", "fabricated"},
    ("pre_existing", "txn.meta.source_ref"): {"removed_or_altered", "fabricated"},
    ("pre_existing", "txn.meta.other"): {"removed_or_altered", "fabricated"},
    ("pre_existing", "posting.units"): {"removed_or_altered", "fabricated", "target_misses", "collateral_damage", "components"},
    ("pre_existing", "posting.flag"): {"removed_or_altered", "fabricated"},
    ("pre_existing", "posting.cost"): {"removed_or_altered", "fabricated", "balance_errors"},
    ("pre_existing", "posting.price"): {"removed_or_altered", "fabricated", "balance_errors"},
    ("pre_existing", "txn.multiplicity"): {"fabricated", "collateral_damage", "target_misses", "components"},
    ("pre_existing", "open.date"): {"removed_or_altered", "fabricated", "balance_errors"},
    ("pre_existing", "open.account"): {"removed_or_altered", "fabricated", "balance_errors", "plug_accounts"},
    ("pre_existing", "option.title"): {"removed_or_altered"},
    ("pre_existing", "option.operating_currency"): {"removed_or_altered", "balance_errors", "parse_ok", "components",
                                                    "target_misses", "collateral_damage", "fabricated"},
    ("pre_existing", "text.comments"): {"added_prose"},
    ("pre_existing", "text.layout"): {"padding"},
    ("pre_existing", "text.amount_spelling"): {"removed_or_altered"},
    ("planted_repair", "txn.payee"): {"undocumented", "unresolved_planted", "components"},
    ("planted_repair", "txn.flag"): {"unresolved_planted", "components", "fabricated"},
    ("planted_repair", "txn.date"): {"unresolved_planted", "components", "fabricated"},
    ("planted_repair", "posting.units"): {"unresolved_planted", "components", "fabricated", "target_misses", "collateral_damage"},
    ("planted_repair", "posting.account"): {"unresolved_planted", "components", "fabricated", "target_misses",
                                            "collateral_damage", "plug_accounts", "balance_errors"},
    ("planted_repair", "txn.multiplicity"): {"fabricated", "target_misses", "collateral_damage", "components"},
}


def test_every_reward_visible_mutation_changes_the_cache_key():
    """Two layers, against the REAL scorer, per entry role.

    Implementation safety: if the uncached score changes, the conservative
    cache key must change (a real dict cache is primed in both orders).
    Normative contract: a (role, field) mutation declared `ignored` in
    `REWARD_DEPENDENCIES` must move NO component or penalty; one declared
    `observed` must move the score vector and only within its declared
    set. Text-only channels are pinned as the reason the source digest is
    still in the key, and as raw-scorer behaviour being retired.
    """
    from beancount_ledger import reward as R
    from beancount_ledger.beancount_ledger import digests_of
    from beancount_ledger.candidate.mapping import REWARD_DEPENDENCIES

    golden = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")
    original = (ROOT / "beancount_ledger" / "world" / "ledger.beancount").read_text(encoding="utf-8")
    task = R.load_task(ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json")
    task_id = C.task_contract_digest(task)
    policy_id = C.parse_policy_digest()

    header = '2025-11-04 * "Northwind Supplies" "Payment of purchase invoice PI-2211"'
    block = header + "\n  Liabilities:AP                            6200.00 USD\n  Assets:Bank:Checking                     -6200.00 USD\n"
    sale = ('2025-11-07 * "Harbor Freight Ltd" "Sale SI-1044"\n  Assets:AR                                 4800.00 USD\n'
            "  Income:Sales                             -4000.00 USD\n  Liabilities:SalesTax-Payable              -800.00 USD\n")
    cogs = ('2025-11-07 * "Harbor Freight Ltd" "Cost of goods sold on SI-1044"\n'
            "  Expenses:COGS                             2600.00 USD\n  Assets:Inventory                         -2600.00 USD\n")
    rhead = '2025-11-26 * "Harbor Freight Ltd" "Customer payment settling SI-1044"'
    repair = rhead + "\n  Assets:Bank:Checking                      4800.00 USD\n  Assets:AR                                -4800.00 USD\n"
    problems = []
    for needle in (block, sale + "\n" + cogs, repair, 'option "title" "Alpine Trading Co. - FY2025"'):
        if needle not in golden:
            problems.append(f"fixture drift: needle not in golden: {needle[:40]!r}")
    if problems:
        return check("metamorphic cache invariant", False, "\n".join(problems))

    mutations = {
        ("pre_existing", "txn.narration"): golden.replace(header, header.replace("Payment of purchase invoice PI-2211", "Paid PI-2211")),
        ("pre_existing", "txn.payee"): golden.replace(header, header.replace("Northwind Supplies", "Northwind Supplies Ltd")),
        ("pre_existing", "txn.flag"): golden.replace(header, header.replace("2025-11-04 *", "2025-11-04 !")),
        ("pre_existing", "txn.date"): golden.replace(header, header.replace("2025-11-04", "2025-11-05")),
        ("pre_existing", "txn.tags"): golden.replace(header, header + " #paid"),
        ("pre_existing", "txn.links"): golden.replace(header, header + " ^pi-2211"),
        ("pre_existing", "txn.meta.source_ref"): golden.replace(header + "\n", header + '\n  invoice: "PI-2211"\n'),
        ("pre_existing", "txn.meta.other"): golden.replace(header + "\n", header + '\n  note: "x"\n'),
        ("pre_existing", "posting.units"): golden.replace(block, block.replace("6200.00", "6100.00")),
        ("pre_existing", "posting.flag"): golden.replace(block, block.replace("  Liabilities:AP  ", "  ! Liabilities:AP")),
        ("pre_existing", "posting.cost"): golden.replace(block, block.replace("6200.00 USD\n", "6200.00 USD {1.00 USD}\n", 1)),
        ("pre_existing", "posting.price"): golden.replace(block, block.replace("6200.00 USD\n", "6200.00 USD @ 1.00 USD\n", 1)),
        ("pre_existing", "posting.order"): golden.replace(block, header + "\n  Assets:Bank:Checking                     -6200.00 USD\n  Liabilities:AP                            6200.00 USD\n"),
        ("pre_existing", "txn.order.same_date"): golden.replace(sale + "\n" + cogs, cogs + "\n" + sale),
        ("pre_existing", "txn.multiplicity"): golden.replace(block, block + "\n" + block),
        ("pre_existing", "open.date"): golden.replace("2025-01-01 open Assets:Prepayments", "2025-01-02 open Assets:Prepayments"),
        ("pre_existing", "open.account"): golden.replace("2025-01-01 open Assets:Prepayments", "2025-01-01 open Assets:Prepaid"),
        ("pre_existing", "option.title"): golden.replace('"Alpine Trading Co. - FY2025"', '"Alpine Trading"'),
        ("pre_existing", "option.operating_currency"): golden.replace('option "operating_currency" "USD"', 'option "operating_currency" "EUR"'),
        ("pre_existing", "text.comments"): golden + "\n; a note nobody asked for\n",
        ("pre_existing", "text.layout"): golden.replace(block, block + "\n" * 40),
        ("pre_existing", "text.amount_spelling"): golden.replace(block, block.replace("6200.00 USD", "6100.00 + 100.00 USD", 1)),
        ("pre_existing", "text.trailing_whitespace"): golden.replace(header, header + "  "),
        ("planted_repair", "txn.narration"): golden.replace(rhead, rhead.replace("Customer payment settling SI-1044", "Paid")),
        ("planted_repair", "txn.payee"): golden.replace(rhead, rhead.replace("Harbor Freight Ltd", "Harbour Freight")),
        ("planted_repair", "txn.date"): golden.replace(rhead, rhead.replace("2025-11-26", "2025-11-27")),
        ("planted_repair", "txn.flag"): golden.replace(rhead, rhead.replace("2025-11-26 *", "2025-11-26 !")),
        ("planted_repair", "txn.tags"): golden.replace(rhead, rhead + " #recon"),
        ("planted_repair", "txn.links"): golden.replace(rhead, rhead + " ^si-1044"),
        ("planted_repair", "txn.meta.source_ref"): golden.replace(rhead + "\n", rhead + '\n  invoice: "SI-1044"\n'),
        ("planted_repair", "posting.units"): golden.replace(repair, repair.replace("4800.00", "4700.00")),
        ("planted_repair", "posting.account"): golden.replace(repair, repair.replace("Assets:AR  ", "Assets:Inventory")),
        ("planted_repair", "posting.order"): golden.replace(repair, rhead + "\n  Assets:AR                                -4800.00 USD\n  Assets:Bank:Checking                      4800.00 USD\n"),
        ("planted_repair", "txn.multiplicity"): golden.replace(repair, repair + "\n" + repair),
    }

    def identify(text):
        """(candidate identity, reward input) — the reward input is the
        policy's whole information; a rejection's is its outcome digest."""
        r = parse_once(text)
        if isinstance(r, Accepted):
            return r.candidate_digest, C.accepted_reward_input(r)
        if isinstance(r, ProtocolFailure):
            payload = C.rejection_payload([(r.reason, -1, -1)])
            return f"refused:{r.reason}", C.outcome_digest("ProtocolRejected", payload, task_id, policy_id)
        return f"evaluator:{r}", None          # never cacheable

    base_detail = R.score(golden, task, original)
    base_vec = score_vector(base_detail)
    base_cd, base_out = identify(golden)
    base_key = C.score_cache_key(C.RAW_TEXT_ENGINE, base_out, task_id,
                                 digests_of(golden.encode("utf-8"))["logical_text_digest"])
    if base_vec["total"] != "1":
        problems.append(f"golden scores {base_vec['total']}, expected 1")

    cache: dict[str, str] = {}
    unchanged_candidate = set()
    report = []
    for (role, field), text in mutations.items():
        if text == golden:
            problems.append(f"{role}.{field}: the mutation did not apply")
            continue
        vec = score_vector(R.score(text, task, original))
        moved = moved_keys(base_vec, vec)
        cd, out = identify(text)
        logical = digests_of(text.encode("utf-8"))["logical_text_digest"]
        key = C.score_cache_key(C.RAW_TEXT_ENGINE, out, task_id, logical) if out is not None else None
        expected = REWARD_DEPENDENCIES[(role, field)]
        report.append(f"{role:14s} {field:26s} {expected:9s} moved={sorted(moved)}")
        # implementation safety
        if moved and key == base_key:
            problems.append(f"{role}.{field}: score moved but the cache key did not")
        if key is not None:
            cache.clear(); cache[base_key] = base_vec["total"]
            if cache.get(key) not in (None, vec["total"]):
                problems.append(f"{role}.{field}: correct-then-mutated cache returned the wrong score")
            cache.clear(); cache[key] = vec["total"]
            if cache.get(base_key) not in (None, base_vec["total"]):
                problems.append(f"{role}.{field}: mutated-then-correct cache returned the wrong score")
        # normative contract
        if expected == "ignored" and moved:
            problems.append(f"{role}.{field}: declared ignored but moved {sorted(moved)}")
        if expected in ("observed", "text_only"):
            if not moved:
                problems.append(f"{role}.{field}: declared {expected} but nothing moved")
            allowed = EXPECTED_MOVEMENT.get((role, field), set()) | {"total"}
            if not moved <= allowed:
                problems.append(f"{role}.{field}: moved outside its declared set: {sorted(moved - allowed)}")
        if cd == base_cd:
            unchanged_candidate.add((role, field))
    text_only = {k for k, v in REWARD_DEPENDENCIES.items() if v == "text_only" and k in mutations}
    if not text_only <= unchanged_candidate:
        problems.append(f"text-only channels should leave the candidate identity unchanged: {sorted(text_only - unchanged_candidate)}")
    moved_without_candidate = {k for k in unchanged_candidate if moved_keys(base_vec, score_vector(R.score(mutations[k], task, original)))}
    if moved_without_candidate != text_only:
        problems.append(f"mutations moving the score without moving the candidate should be exactly the text-only set: "
                        f"{sorted(moved_without_candidate)} vs {sorted(text_only)}")
    return check("metamorphic, two layers, per role: keys move with scores, no poisoning; ignored moves nothing, "
                 "observed moves only its declared components; text-only channels pinned",
                 not problems, "\n".join(problems) + "\n\n" + "\n".join(report))


def test_the_scorer_reads_no_undeclared_entry_field():
    """Source-level dependency audit: every entry/posting attribute the raw
    scorer reads is declared observed for some role, so a new read cannot
    appear without a disposition and a cache-key projection."""
    import ast
    from beancount_ledger.candidate.mapping import REWARD_DEPENDENCIES

    attr_to_fields = {
        "narration": {"txn.narration"}, "payee": {"txn.payee"}, "tags": {"txn.tags"}, "links": {"txn.links"},
        "flag": {"txn.flag", "posting.flag"}, "meta": {"txn.meta.source_ref", "txn.meta.other"},
        "date": {"txn.date", "open.date"}, "postings": {"txn.multiplicity"}, "units": {"posting.units"},
        "number": {"posting.units"}, "currency": {"posting.units", "open.currencies"},
        "account": {"posting.account", "open.account"}, "cost": {"posting.cost"}, "price": {"posting.price"},
    }
    tree = ast.parse((ROOT / "beancount_ledger" / "reward.py").read_text(encoding="utf-8"))
    read = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr in attr_to_fields}
    observed = {field for (role, field), d in REWARD_DEPENDENCIES.items() if d in ("observed", "text_only")}
    undeclared = sorted(a for a in read if not attr_to_fields[a] & observed)
    return check(f"reward.py reads {len(read)} entry attributes; every one is declared observed for some role",
                 read and not undeclared, f"undeclared reads: {undeclared}; read={sorted(read)}")


def test_the_scanner_boundary_cases():
    f = C.longest_numeric_digit_run
    problems = []
    cases = [
        ("even backslashes close the string", '"a\\\\" ' + "1" * 42, 42),
        ("odd backslashes keep it open", '"a\\" ' + "1" * 42 + '"', 0),
        ("semicolon inside a string is text", '"a;b" ' + "2" * 5, 5),
        ("semicolon after the closing quote is a comment", '"a" ;' + "2" * 50, 0),
        ("CRLF ends a comment", "x\r\n; " + "3" * 50 + "\r\n" + "4" * 7, 7),
        ("escaped quote before a long run, inside", '"q\\" ' + "5" * 50 + '" ' + "6" * 3, 3),
        ("digits inside an account are numeric text", "Assets:" + "7" * 41, 41),
        ("dates, signs, commas and points", "2025-11-30 -1,234.56 +9", 6),
        ("string spanning lines", '"a\nb\n' + "8" * 50 + '\n" 9', 1),
    ]
    for label, text, expected in cases:
        try:
            got = f(text)
        except C.LexicalError as exc:
            got = f"lexical:{exc.reason}"
        if got != expected:
            problems.append(f"{label}: {got!r} != {expected!r}")
    for label, text in (("EOF inside a string", '"abc'), ("EOF after a backslash", '"abc\\'), ("bare CR in a string", '"a\rb')):
        try:
            got = f(text)
            if label != "bare CR in a string":
                problems.append(f"{label}: accepted ({got})")
            elif got != 0:
                problems.append(f"{label}: {got}")
        except C.LexicalError as exc:
            if exc.reason != "lexical.unclosed_string":
                problems.append(f"{label}: {exc.reason}")
    return check("scanner boundary cases: escape parity, semicolon placement, CRLF, EOF states, adjacency",
                 not problems, "\n".join(problems))


def test_the_outcome_identity_binds_the_findings():
    """Two hashes. `reward_input_digest` = candidate + finding SUMMARY: a
    finding moves it, a message edit does not. `committed_outcome_digest`
    adds the diagnostic sample and the renderer version. The score cache is
    keyed per ENGINE: the raw-text engine's key needs the source digest, the
    candidate engine's key refuses it, and the two namespaces never meet.
    And the scorer contract is a separate scope from the parse certificate."""
    from beancount_ledger.candidate.validate import DomainViolation
    problems = []
    r = parse_once(BASE.replace("Assets:Bank:Checking -85.00 USD", "Assets:Bank:Checking -80.00 USD"))
    if not isinstance(r, Accepted) or not r.domain_findings:
        return check("outcome identity", False, f"fixture: {r}")
    base = C.reward_input_digest(r.candidate_digest, r.finding_summary)
    injected = C.summarise_findings(r.domain_findings + (DomainViolation("lifecycle.duplicate_open", "injected"),))
    dropped = C.summarise_findings(())
    reworded = C.summarise_findings(tuple(DomainViolation(f.code, "different wording", f.facts) for f in r.domain_findings))
    if len({base, C.reward_input_digest(r.candidate_digest, injected), C.reward_input_digest(r.candidate_digest, dropped)}) != 3:
        problems.append("a changed finding set left the reward input unchanged")
    if C.reward_input_digest(r.candidate_digest, reworded) != base:
        problems.append("a message edit moved the reward input")
    raw = lambda ri, src="L": C.score_cache_key(C.RAW_TEXT_ENGINE, ri, "t", src)
    if raw(base) == raw(C.reward_input_digest(r.candidate_digest, injected)):
        problems.append("a changed finding set left the cache key unchanged")
    if raw(base) == raw(base, "M"):
        problems.append("the raw engine does not bind the logical source digest")
    for bad in (lambda: C.score_cache_key(C.RAW_TEXT_ENGINE, base, "t", None),
                lambda: C.score_cache_key(C.CANDIDATE_ENGINE, base, "t", "L")):
        try:
            bad()
            problems.append("an engine accepted the other engine's key recipe")
        except C.CanonicalError:
            pass
    if C.score_cache_key(C.CANDIDATE_ENGINE, base, "t") == raw(base):
        problems.append("the two engines share a cache namespace")
    outcome = C.accepted_outcome_digest(r, "t", "p")
    saved = C.RENDERER_VERSION
    C.RENDERER_VERSION = saved + 1
    try:
        if C.accepted_outcome_digest(r, "t", "p") == outcome:
            problems.append("the committed outcome does not bind the renderer version")
        if C.reward_input_digest(r.candidate_digest, r.finding_summary) != base:
            problems.append("a renderer change moved the reward input")
    finally:
        C.RENDERER_VERSION = saved
    parse_before, scorer_before = C.parse_policy_digest(), C.scorer_contract_digest()
    saved = C.ENTITY_MATCHING_VERSION
    C.ENTITY_MATCHING_VERSION = saved + 1
    try:
        if C.scorer_contract_digest() == scorer_before:
            problems.append("an entity-matching change did not move the scorer contract")
        if C.parse_policy_digest() != parse_before:
            problems.append("an entity-matching change invalidated the parse certificate")
    finally:
        C.ENTITY_MATCHING_VERSION = saved
    if "reward_dependencies" in json.dumps(C.parse_policy_view()):
        problems.append("reward disposition is still inside the parse policy")
    if "reward_dependencies" not in C.task_contract_view({"id": "x"})["scorer_contract"]:
        problems.append("the task contract does not bind the scorer contract")
    return check("outcome identity binds the findings; cache key binds source during migration; "
                 "scorer contract is a separate scope from the parse certificate",
                 not problems, "\n".join(problems))


def test_the_policy_reads_the_whole_candidate_not_a_capped_list():
    """501 cheap findings, then the expensive one: the sample of 500 omits
    it, the summary the policy reads does not."""
    problems = []
    cheap = "".join(f'2025-11-30 * "X{i}"\n  Expenses:Office 1.00 USD\n' for i in range(501))
    expensive = '2025-11-30 * "Y"\n  Expenses:Nope 1.00 USD\n  Assets:Bank:Checking -1.00 USD\n'
    r = parse_once(BASE + cheap + expensive)
    if not isinstance(r, Accepted):
        return check("policy reads the whole candidate", False, f"{r}")
    s = r.finding_summary
    sample_codes = {f.code for f in r.domain_findings}
    if len(r.domain_findings) != C.MAX_FINDING_SAMPLE or not s.truncated:
        problems.append(f"sample {len(r.domain_findings)} truncated={s.truncated}")
    if "posting.account_not_open" in sample_codes:
        problems.append("the expensive finding is in the sample — the fixture does not exercise the cap")
    if "posting.account_not_open" not in s.codes or s.total != 502:
        problems.append(f"summary codes {s.codes} total {s.total}")
    from beancount_ledger.candidate.policy import consequences
    if not any(c.gates_all for c in consequences(s)):
        problems.append("the policy did not see the omitted finding")
    a = C.reward_input_digest(r.candidate_digest, s)
    b = C.reward_input_digest(r.candidate_digest, C.summarise_findings(r.domain_findings))
    if a == b:
        problems.append("the reward input binds only the capped sample")
    return check("501 cheap findings then one expensive: sample omits it, summary and reward input carry it",
                 not problems, "\n".join(problems))


def test_the_oracle_comparison_is_per_category_and_asymmetric():
    problems = []
    from beancount_ledger.candidate.validate import DomainViolation
    D = DomainViolation
    if C.oracle_disagreement(["ValidationError: Transaction does not balance: (5.00 USD)", "Something we never modelled"],
                             [D("event.unbalanced", "")]):
        problems.append("an oracle-only line outside the overlap was treated as disagreement")
    if C.oracle_disagreement(["ValidationError: Invalid reference to unknown account 'X'"], [D("event.unbalanced", "")]) \
            != ["unknown_account"]:
        problems.append("an overlap category the oracle reports and we do not was not flagged")
    if C.oracle_disagreement([], [D("posting.after_account_closed", "")]):
        problems.append("our validator being stricter was treated as disagreement (agent-purchasable exclusion)")
    # crossed cases through the real boundary
    two = BASE.replace("Assets:Bank:Checking -85.00 USD", "Assets:Bank:Checking -80.00 USD") \
              .replace("Expenses:Office  40.00 USD", "Expenses:Rent  40.00 USD")
    r = parse_once(two)
    if not isinstance(r, Accepted) or set(r.finding_summary.codes) != {"event.unbalanced", "posting.account_not_open"}:
        problems.append(f"two simultaneous faults: {r if not isinstance(r, Accepted) else r.finding_summary.codes}")
    dup = BASE.replace("Assets:Bank:Checking -85.00 USD", "Assets:Bank:Checking -80.00 USD") \
              .replace("Assets:Bank:Checking -40.00 USD", "Assets:Bank:Checking -30.00 USD")
    r = parse_once(dup)
    if not isinstance(r, Accepted) or dict(r.finding_summary.counts).get("event.unbalanced") != 2:
        problems.append(f"duplicate faults: {r if not isinstance(r, Accepted) else r.finding_summary.counts}")
    stricter = BASE.replace("2025-11-01 open Expenses:Office USD\n",
                            "2025-11-01 open Expenses:Office USD\n2025-10-01 close Expenses:Office\n")
    r = parse_once(stricter)
    if not isinstance(r, Accepted) or "posting.after_account_closed" not in r.finding_summary.codes:
        problems.append(f"ours-only extra finding alongside a shared one should be Accepted: {r}")
    from beancount_ledger.candidate import normalise as N
    real = C.ORACLE_PROJECTION
    C.ORACLE_PROJECTION = dict(real, unknown_account=("Invalid reference to unknown account", {"never.emitted"}))
    try:
        r = parse_once(BASE.replace("Expenses:Office  40.00 USD", "Expenses:Rent  40.00 USD"))
        if not isinstance(r, N.EvaluationFailure) or r.stage != "validator_disagreement":
            problems.append(f"a gap in the normative validator was not an evaluator failure: {r}")
    finally:
        C.ORACLE_PROJECTION = real
    return check("oracle: per-category, asymmetric; crossed cases through the boundary; a validator gap quarantines",
                 not problems, "\n".join(problems))


def test_comparison_policies_are_per_predicate():
    """The reward predicate for the repair's payee is strict; the folding
    lookup is diagnostics only; the raw scorer agrees with the strict one."""
    from beancount_ledger import reward as R
    from beancount_ledger.candidate.entities import canonical_key
    problems = []
    accepted = "Harbor Freight Ltd"
    for spelling in ("Harbor Freight Ltd", "Harbor   Freight  Ltd", " Harbor Freight Ltd "):
        if not C.strict_payee_match(spelling, accepted):
            problems.append(f"strict rejected an equal spelling: {spelling!r}")
    for label, spelling in (("mocking case", "hArBoR fReIgHt lTd"), ("Turkish dotted I", "HARBOR FREİGHT LTD"),
                            ("fullwidth", "Ｈａｒｂｏｒ Ｆｒｅｉｇｈｔ Ｌｔｄ"), ("suffix dropped", "Harbor Freight"),
                            ("punctuation", "Harbor Freight, Ltd."), ("None", None)):
        if C.strict_payee_match(spelling, accepted):
            problems.append(f"strict accepted {label}: {spelling!r}")
        # the folding lookup identifies case, width, suffix and punctuation
        # variants — as a diagnostic; a Turkish dotted I is a different
        # letter under casefold and is not expected to resolve
        if spelling and label != "Turkish dotted I" and canonical_key(spelling) != canonical_key(accepted):
            problems.append(f"the diagnostic lookup should still identify {label}: {spelling!r}")
    if C.strict_payee_match("Paciﬁc Traders", "Pacific Traders"):
        problems.append("strict accepted a ligature")
    if canonical_key("Paciﬁc Traders") != canonical_key("Pacific Traders"):
        problems.append("the diagnostic lookup should fold a compatibility ligature")
    if canonical_key("Definitely not Harbor Freight") == canonical_key(accepted):
        problems.append("the lookup matched by containment")
    for spelling in ("Harbor   Freight  Ltd", "hArBoR fReIgHt lTd"):
        raw_equal = R._normalise_payee(spelling) == R._normalise_payee(accepted)
        if raw_equal != C.strict_payee_match(spelling, accepted):
            problems.append(f"raw scorer and strict predicate disagree on {spelling!r}")
    policies = C.scorer_contract_view()["comparison_policies"]
    if policies["planted_repair.payee"]["used_for"] != "reward" or "diagnostics" not in policies["customer_lookup_for_diagnostics"]["used_for"]:
        problems.append("the contract does not name which policy is reward")
    return check("comparison policies: strict payee predicate for reward (case, Turkish I, fullwidth, suffix refused); "
                 "folding lookup is diagnostics only; raw scorer agrees", not problems, "\n".join(problems))


def test_role_allocation_is_a_multiset():
    """Two identical valid repairs: one discharges the planted event, the
    other is an unexplained addition; the result is invariant under their
    order and under a narration difference between them. Planted predicates
    are validated disjoint when the environment is built."""
    from beancount_ledger import reward as R
    golden = (ROOT / "tests" / "solutions" / "golden.beancount").read_text(encoding="utf-8")
    original = (ROOT / "beancount_ledger" / "world" / "ledger.beancount").read_text(encoding="utf-8")
    task = R.load_task(ROOT / "beancount_ledger" / "tasks" / "bank_recon_001.json")
    rhead = '2025-11-26 * "Harbor Freight Ltd" "Customer payment settling SI-1044"'
    repair = rhead + "\n  Assets:Bank:Checking                      4800.00 USD\n  Assets:AR                                -4800.00 USD\n"
    other = repair.replace("Customer payment settling SI-1044", "Second copy")
    problems = []
    vectors = []
    for label, text in (("A then B", golden.replace(repair, repair + "\n" + other)),
                        ("B then A", golden.replace(repair, other + "\n" + repair)),
                        ("A then A", golden.replace(repair, repair + "\n" + repair))):
        d = R.score(text, task, original)
        vec = score_vector(d)
        vectors.append(vec)
        if len(d["fabricated"]) != 1 or d["unresolved_planted"]:
            problems.append(f"{label}: fabricated={d['fabricated']} unresolved={d['unresolved_planted']}")
    if vectors[0] != vectors[1]:
        problems.append("the score vector depends on the order of two repairs")
    if vectors[0]["fabricated"] != vectors[2]["fabricated"]:
        problems.append("identical and narration-different duplicates are allocated differently")
    # mixed validity: A has the accepted payee, B is repair-shaped with a
    # wrong payee. One allocation: A takes the slot in either order, B is one
    # unexplained addition, and nothing is undocumented — one defect, one
    # penalty. A lone B is the published contract: resolved and undocumented.
    wrong = repair.replace("Harbor Freight Ltd", "Harbour Freight")
    mixed = {}
    for label, text in (("A/B", golden.replace(repair, repair + "\n" + wrong)),
                        ("B/A", golden.replace(repair, wrong + "\n" + repair))):
        d = R.score(text, task, original)
        mixed[label] = score_vector(d)
        if len(d["fabricated"]) != 1 or "Harbour" not in d["fabricated"][0] or d["undocumented"] or d["unresolved_planted"]:
            problems.append(f"{label}: fabricated={d['fabricated']} undocumented={d['undocumented']} "
                            f"unresolved={d['unresolved_planted']}")
    if mixed["A/B"] != mixed["B/A"]:
        problems.append("the mixed-validity vector depends on order")
    lone = R.score(golden.replace(repair, wrong), task, original)
    if lone["unresolved_planted"] or len(lone["undocumented"]) != 1 or lone["fabricated"]:
        problems.append(f"lone wrong-payee repair: resolved={not lone['unresolved_planted']} "
                        f"undocumented={lone['undocumented']} fabricated={lone['fabricated']}")
    entries = R.load_ledger(original)[0]
    if R.audit_planted_disjointness(task, entries):
        problems.append("the shipped task is reported ambiguous")
    doubled = dict(task, planted=task["planted"] + [task["planted"][0]])
    if not R.audit_planted_disjointness(doubled, entries):
        problems.append("two identical planted predicates were not refused")
    first = entries[[isinstance(e, R.data.Transaction) for e in entries].index(True)]
    colliding = dict(task, planted=task["planted"] + [{
        "id": "collides", "date": str(first.date),
        "required_postings": [[p.account, str(p.units.number)] for p in first.postings]}])
    if not R.audit_planted_disjointness(colliding, entries):
        problems.append("a planted predicate equal to a pre-existing transaction was not refused")
    return check("role allocation: duplicate repairs -> one discharge, one addition, order-invariant; "
                 "planted disjointness audited", not problems, "\n".join(problems))


def test_the_policy_takes_only_a_summary_and_saturation_is_reward_equivalent():
    from beancount_ledger.candidate import policy as P
    from beancount_ledger.candidate.validate import DomainViolation
    problems = []
    try:
        P.apply_policy(1.0, [DomainViolation("event.unbalanced", "x")])
        problems.append("the policy accepted a finding sequence")
    except TypeError:
        pass
    # Saturation, exercised for real: lower the threshold, summarise past it
    # through the validator path (the only constructor), price both.
    real_cap = C.MAX_FINDING_COUNT
    C.MAX_FINDING_COUNT = 3
    try:
        outcomes = {n: P.apply_policy(1.0, C.summarise_findings([DomainViolation("event.unbalanced", "")] * n))
                    for n in (1, 3, 7)}
        saturated = C.summarise_findings([DomainViolation("event.unbalanced", "")] * 7)
        if dict(saturated.counts)["event.unbalanced"] != 3 or saturated.total != 3:
            problems.append(f"counts did not saturate: {saturated}")
    finally:
        C.MAX_FINDING_COUNT = real_cap
    if len({json.dumps(o, sort_keys=True) for o in outcomes.values()}) != 1:
        problems.append(f"saturation is not reward-equivalent: {outcomes}")
    P.validate_policy_requirements()
    saved = dict(P.POLICY_REQUIREMENTS["bank_reconciliation"])
    P.POLICY_REQUIREMENTS["bank_reconciliation"]["event.unbalanced"] = "count_by_account"
    try:
        C.scorer_contract_view()
        problems.append("a policy reading an unpreserved reduction built a contract")
    except ValueError:
        pass
    finally:
        P.POLICY_REQUIREMENTS["bank_reconciliation"] = saved
    if C.summarise_findings([DomainViolation(c, "") for c in ("a", "b", "a")]).counts != (("a", 2), ("b", 1)):
        problems.append("summary counts are wrong")
    return check("policy: summary only (a sequence is a TypeError); saturation reward-equivalent; "
                 "an undeclared reduction fails contract construction", not problems, "\n".join(problems))


def test_the_diagnostic_sample_is_a_function_of_the_candidate():
    cheap = "".join(f'2025-11-30 * "X{i}"\n  Expenses:Office 1.00 USD\n' for i in range(501))
    expensive = '2025-11-30 * "Y"\n  Expenses:Nope 1.00 USD\n  Assets:Bank:Checking -1.00 USD\n'
    first, last = parse_once(BASE + expensive + cheap), parse_once(BASE + cheap + expensive)
    if not (isinstance(first, Accepted) and isinstance(last, Accepted)):
        return check("deterministic sample", False, f"{first} / {last}")
    # The structural identity legitimately differs (source order within a
    # date is structural); the semantic identity, the summary, the SAMPLE
    # and therefore the diagnostic part of the committed outcome must not.
    same = ([(f.code, f.message) for f in first.domain_findings] == [(f.code, f.message) for f in last.domain_findings]
            and C.finding_sample_payload(first.domain_findings) == C.finding_sample_payload(last.domain_findings)
            and first.finding_summary == last.finding_summary
            and first.semantic_fingerprint == last.semantic_fingerprint
            and C.committed_outcome_digest("Accepted", "same-reward-input", C.finding_sample_payload(first.domain_findings), "t", "p")
            == C.committed_outcome_digest("Accepted", "same-reward-input", C.finding_sample_payload(last.domain_findings), "t", "p"))
    return check("the diagnostic sample, the summary and the semantic identity do not depend on source order", same,
                 f"first={len(first.domain_findings)} last={len(last.domain_findings)} "
                 f"summary_equal={first.finding_summary == last.finding_summary}")


def test_valid_but_unusual_ledgers_never_raise_and_are_permutation_invariant():
    """A property over parser-produced values: optional fields present and
    absent, empty versus None payee, non-ASCII, escaped quotes, extreme
    allowed decimals, posting flags, tags and links. Candidate construction
    never raises, every ledger is accepted clean (a valid-diversity corpus:
    fairness, not security), and permuting same-date transactions leaves the
    semantic fingerprint and the diagnostic sample unchanged."""
    import random
    accounts = ["Assets:Bank:Checking", "Assets:AR", "Expenses:Office", "Expenses:BankFees", "Income:Sales", "Equity:Opening"]

    def ledger(rng):
        lines = ['option "operating_currency" "USD"'] + [f"2025-11-01 open {a} USD" for a in accounts]
        blocks = []
        for _ in range(rng.randint(1, 8)):
            date = f"2025-11-{rng.randint(2, 30):02d}"
            payee = rng.choice([None, "", "Harbor Freight Ltd", "Café Ünlü", "Cascade Bank"])
            narration = rng.choice(["", "Payment", "Ünlü ödeme", 'a\\"b'])
            header = f"{date} {rng.choice('*!')} " + (f'"{payee}" ' if payee is not None else "") + f'"{narration}"'
            header += rng.choice(["", " #tag1", " #t1 #t2"]) + rng.choice(["", " ^l1"])
            amount = rng.choice(["1.00", "4800.00", "0.10", "9999999999999.99", "85.000"])
            a1, a2 = rng.sample(accounts, 2)
            block = [header]
            if rng.random() < 0.3:
                block.append('  invoice: "SI-1"')
            block += [f"  {rng.choice(['', '! '])}{a1}  {amount} USD", f"  {a2}  -{amount} USD"]
            blocks.append((date, block))
        return lines, blocks

    problems = []
    for seed in range(40):
        rng = random.Random(seed)
        lines, blocks = ledger(rng)
        text = "\n".join(lines + [l for _, b in blocks for l in b]) + "\n"
        try:
            r = parse_once(text)
        except Exception as exc:
            problems.append(f"seed {seed}: raised {type(exc).__name__}: {exc}")
            continue
        if not isinstance(r, Accepted) or not r.domain_valid:
            problems.append(f"seed {seed}: {type(r).__name__} {getattr(r, 'reason', '')} {getattr(r, 'finding_summary', '')}")
            continue
        shuffled = sorted(blocks, key=lambda b: (b[0], rng.random()))      # stable date order, permuted within
        text2 = "\n".join(lines + [l for _, b in shuffled for l in b]) + "\n"
        r2 = parse_once(text2)
        if not isinstance(r2, Accepted) or r2.semantic_fingerprint != r.semantic_fingerprint \
                or r2.domain_findings != r.domain_findings:
            problems.append(f"seed {seed}: same-date permutation changed the semantic identity or the sample")
    return check("40 valid-but-unusual ledgers: never raise, accepted clean, permutation-invariant",
                 not problems, "\n".join(problems[:8]))


def test_every_schema_field_is_classified():
    """A newly added dataclass field fails until every dimension classifies it."""
    from dataclasses import fields
    from beancount_ledger.candidate.mapping import FIELD_DIMENSIONS
    from beancount_ledger.candidate.schema import ParsedLifecycle, ParsedPosting, ParsedTransaction, SafeParsedSubmission
    reflected = {
        ParsedTransaction: {"index": "txn.order.same_date", "date": "txn.date", "flag": "txn.flag", "payee": "txn.payee",
                            "narration": "txn.narration", "tags": "txn.tags", "links": "txn.links",
                            "source_refs": "txn.meta.source_ref", "postings": "txn.multiplicity"},
        ParsedPosting: {"account": "posting.account", "amount": "posting.units", "currency": "posting.units",
                        "flag": "posting.flag"},
        ParsedLifecycle: {"index": "txn.order.same_date", "kind": "open.account", "date": "open.date",
                          "account": "open.account", "currencies": "open.currencies"},
        SafeParsedSubmission: {"operating_currency": "option.operating_currency", "title": "option.title",
                               "directives": "txn.multiplicity"},
    }
    problems = []
    for cls, mapping in reflected.items():
        for f in fields(cls):
            if f.name.startswith("_"):
                continue
            key = mapping.get(f.name)
            if key is None:
                problems.append(f"{cls.__name__}.{f.name}: no dimension mapping")
            elif key not in FIELD_DIMENSIONS or set(FIELD_DIMENSIONS[key]) != {"provenance", "accounting", "reward", "render"}:
                problems.append(f"{cls.__name__}.{f.name} -> {key}: not classified on all four dimensions")
    return check("every reflected schema field is classified on all four dimensions", not problems, "\n".join(problems))


TESTS = [
    test_golden_vectors_pin_exact_bytes,
    test_the_encoder_refuses_ambient_identity,
    test_decimal_canonical_is_value_identity_and_context_free,
    test_cross_process_shuffled_construction_is_deterministic,
    test_canonical_sorted_orders_by_encoded_bytes,
    test_string_policy_both_directions,
    test_paired_vectors_separate_structural_from_semantic_identity,
    test_the_submission_is_minted_only_by_the_boundary_and_is_immutable,
    test_numeric_bounds_at_both_gates,
    test_parse_policy_digest_is_declared_data,
    test_task_contract_digest_ignores_documentation_keys,
    test_rejection_payload_is_bounded_sorted_and_message_free,
    test_domain_violations_are_accepted_with_names_not_rejected,
    test_the_digit_scan_is_token_aware,
    test_unicode_database_is_part_of_the_policy,
    test_every_reward_visible_mutation_changes_the_cache_key,
    test_the_scorer_reads_no_undeclared_entry_field,
    test_the_scanner_boundary_cases,
    test_the_outcome_identity_binds_the_findings,
    test_the_policy_reads_the_whole_candidate_not_a_capped_list,
    test_the_oracle_comparison_is_per_category_and_asymmetric,
    test_comparison_policies_are_per_predicate,
    test_role_allocation_is_a_multiset,
    test_the_policy_takes_only_a_summary_and_saturation_is_reward_equivalent,
    test_the_diagnostic_sample_is_a_function_of_the_candidate,
    test_valid_but_unusual_ledgers_never_raise_and_are_permutation_invariant,
    test_every_schema_field_is_classified,
]


def run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = [t() for t in TESTS]
    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
