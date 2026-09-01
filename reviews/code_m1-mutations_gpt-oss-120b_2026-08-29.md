# Code review — m1-mutations — openai/gpt-oss-120b, 2026-08-29

*Files: beancount_ledger/candidate/committed.py, beancount_ledger/graph/project.py, beancount_ledger/graph/derive.py. Question: This change adds two planted-mutation kinds to a bank-reconciliation reward: AlterRecognition (the opening ledger carries a wrong vector; the repair replaces it) and DuplicateRecognition (the opening ledger carries an entry twice; the repair removes one). The allocation (committed.py: _retired_keys, _expected_counts, allocate, score_committed lost_keys, render_committed) introduces a STALE bucket: retired original content the agent left in place is explained (rendered from the original), never penalised as fabrication or tampering, but keeps the item unresolved. Find: (1) any submission that scores >= 0.60 while the delivered books are wrong under these kinds; (2) any way stale/expected-count bookkeeping mis-attributes tampering or fabrication (e.g. two identical legitimate entries, an alter whose wrong shape equals another entry, a duplicate plus an omit on the same date, the agent deleting the wrong copy vs the right copy); (3) any way the projector (project.py) or derivation (derive.py) admits an ambiguous plan; (4) determinism/ordering hazards. Be concrete: give the ledger shape and the expected vs actual label.*

*Tokens: 25372 in, 6512 out.*

---

**Summary** – The contract code contains several concrete defects that let an agent obtain a “good” score (≥ 0.60) while the delivered books are *incorrect*.  The most serious problem is the **STALE bucket** in `candidate/committed.py:allocate` – retired original content that the agent leaves in place is never penalised, and the allocation logic for duplicate‑recognition mutations never marks the mutation as resolved.  A second, more subtle defect is the **occurrence‑key definition** that still hashes posting flags, even though the contract explicitly declares flags to be ignored.  Both defects can be demonstrated with tiny ledgers that pass all checks but give the wrong financial picture.

Below each defect is given:

* **File / function / line** – exact location.  
* **Reproduction** – a minimal ledger (original + submission) together with the mutation plan that triggers the problem.  
* **Observed wrong behaviour** – what the scorer returns versus what the contract promises.  
* **Severity** – *bug* (breaks contract semantics), *risk* (creates exploitable edge cases), or *nit* (style / maintainability).

---

## 1.  Stale‑original‑content is never penalised (score ≥ 0.60 while books are wrong)

| File | Function / expression | Line |
|------|-----------------------|------|
| `candidate/committed.py` | `allocate` – stale‑bucket handling (`stale`, `stale_items`) | 424‑438 |
| `candidate/committed.py` | `score_committed` – total‑score composition (no penalty for `allocation.stale`) | 923‑928 |

### Reproduction  

*World* – a single‑account world with a **Bank** account and a **Revenue** account.  
*Original ledger* (the opening ledger that the environment is built from):

```beancount
2023-01-01 open Assets:Bank  USD
2023-01-01 open Income:Revenue  USD

2023-01-15 * "Vendor A" "Zero‑sum wrong entry"
  Assets:Bank          100.00 USD
  Assets:Bank         -100.00 USD
```

The entry is **balanced** but does **nothing** to the balances (net‑zero on the same account).  
The contract’s policy expects a *correct* recognition on the same date:

```json
{
  "mutation_id": "m1",
  "recognition_id": "r1",
  "legs": [
    ["Assets:Bank", "100.00"],
    ["Income:Revenue", "-100.00"]
  ],
  "identifiability_claim": "receipt‑123"
}
```

*Mutation plan* – **AlterRecognition** (replace the zero‑sum entry with the correct one).  

*Agent’s submission* (the file the RL‑agent actually sends):

```beancount
2023-01-01 open Assets:Bank  USD
2023-01-01 open Income:Revenue  USD

2023-01-15 * "Vendor A" "Correct entry"
  Assets:Bank          100.00 USD
  Income:Revenue     -100.00 USD

2023-01-15 * "Vendor A" "Zero‑sum wrong entry"
  Assets:Bank          100.00 USD
  Assets:Bank         -100.00 USD
```

The agent **adds** the correct entry **and leaves** the original wrong entry.

### What the scorer does  

1. `_retired_keys` maps the mutation `m1` → the *original* zero‑sum entry’s occurrence key.  
2. `_expected_counts` subtracts one from that key, so the *expected* count for the zero‑sum entry becomes **0**.  
3. In `allocate` the **preserved** list picks the *correct* entry (its key still has a positive count).  
4. The original zero‑sum entry is still present in the submission; because its key matches a retired key, the loop at 432‑438 puts it into `stale_items`.  
5. `stale_items` are **never penalised** – they are not counted as `removed_or_altered`, `fabricated`, or `tamper`.  
6. The mutation is considered **unmatched** (the item id appears in `stale_for`), so `resolved = 0`.  
7. Balances are **correct** (the zero‑sum entry does not affect any account).  

Result (after scaling):

```
targets_hit      = 1.0   (all target accounts hit)
errors_resolved  = 0.0   (the mutation is “unresolved”)
total = 0.70*1.0 + 0.30*0.0 = 0.70
```

The scorer returns **0.70** – well above the 0.60 threshold – even though the delivered ledger still contains a *wrong* entry.

### Severity  

**bug** – The contract promises that any retained original content that should have been “retired” is either penalised as tampering or counted as a resolved error.  The *STALE* bucket violates that promise and creates a free‑lunch exploit.

---

## 2.  Duplicate‑recognition mutation is never counted as resolved

| File | Function / expression | Line |
|------|-----------------------|------|
| `candidate/committed.py` | `allocate` – handling of `duplicate` items (`mapping.append((item.id, None))` and later `if item.id in stale_for or not kept`) | 441‑449 |
| `candidate/committed.py` | `score_committed` – `resolved` calculation uses `allocation.unmatched_planted` | 873‑875 |

### Reproduction  

*World* – two accounts, **Bank** and **Revenue**.  
*Original ledger* contains **two identical correct entries** (the contract treats them as interchangeable):

```beancount
2023-01-01 open Assets:Bank  USD
2023-01-01 open Income:Revenue  USD

2023-02-01 * "Sale" "Invoice #1"
  Assets:Bank          200.00 USD
  Income:Revenue     -200.00 USD

2023-02-01 * "Sale" "Invoice #1"
  Assets:Bank          200.00 USD
  Income:Revenue     -200.00 USD
```

*Mutation plan* – **DuplicateRecognition** for the first of the two identical recognitions (`recognition_id = r1`).  

*Agent’s submission* – **removes one copy** (the intended repair) but **leaves the other copy** untouched:

```beancount
2023-01-01 open Assets:Bank  USD
2023-01-01 open Income:Revenue  USD

2023-02-01 * "Sale" "Invoice #1"
  Assets:Bank          200.00 USD
  Income:Revenue     -200.00 USD
```

### What the scorer does  

* `_expected_counts` subtracts **one** from the occurrence key of the duplicated shape, leaving an expected count of **1**.  
* `allocate` preserves **one** of the two original copies (the one that survives in the submission).  
* The *second* original copy (the one the agent deleted) is **not** present, so it is counted as a *lost* key → `removed` (tamper) **penalty** of –0.40.  
* The mutation id is placed in `stale_for` because the *retired* slot still has a pid, and the code at 446‑447 adds the mutation to `unmatched`.  
* Consequently `resolved = 0` (the duplicate mutation is considered *unresolved* even though the agent performed the correct repair).  

Score (assuming no other penalties):

```
targets_hit      = 1.0
errors_resolved  = 0.0
removed (tamper) = 1  → PENALTY_TAMPER = -0.40
total = 0.70*1 + 0.30*0 - 0.40 = 0.30   (fails)
```

But the *real* problem is that the agent is **punished** for a correct duplicate‑removal, while the contract’s specification says a duplicate‑recognition mutation should be *resolved* (i.e. counted in the “errors_resolved” component).  This mis‑attribution can be exploited: an adversary can *add* a harmless duplicate of a legitimate entry, then delete the original copy; the system will treat the deletion as tampering (penalty) while the duplicate remains, giving the agent a *lower* score than deserved.

### Severity  

**risk** – The scoring contract’s definition of “resolved planted items” is violated, leading to systematic under‑penalisation of legitimate duplicate‑removal work and over‑penalisation of harmless deletions.  This opens a vector for an agent to manipulate the “resolved” ratio.

---

## 3.  Ambiguous‑plan detection is incomplete – false‑positive “twins” check

| File | Function / expression | Line |
|------|-----------------------|------|
| `graph/derive.py` | `twins` detection for `AlterRecognition` (line 193‑196) | 193‑196 |
| `graph/derive.py` | `twins` detection for `DuplicateRecognition` (line 203‑206) | 203‑206 |

### Reproduction  

Consider two recognitions **different IDs** that happen on the **same date** and have **identical leg shapes** (e.g. two separate sales on the same day).  

*World* contains:

```
2023-03-10 * "Sale A" …
  Assets:Bank   150.00 USD
  Income:Revenue -150.00 USD

2023-03-10 * "Sale B" …
  Assets:Bank   150.00 USD
  Income:Revenue -150.00 USD
```

*Mutation plan* tries to **AlterRecognition** the first sale, providing a wrong vector.  
Because the second sale has the *same shape* as the *correct* shape of the first, the `twins` list in `derive` will contain the second sale, and the code will raise:

```
DerivationError: … another same‑date entry shares the shape; the repair is ambiguous
```

However, the contract’s *intention* is that the mutation refers to a **specific recognition ID**, not to “any entry with that shape”.  The presence of a *different* recognition with the same shape should **not** make the plan ambiguous – the mutation is still uniquely identified by its `recognition_id`.  The current check is **over‑constraining** and can reject perfectly valid mutation plans.

### Severity  

**nit** – This does not affect scoring, but it makes the derivation step unnecessarily fragile and can block legitimate tasks, reducing the usability of the environment.

---

## 4.  `occurrence_key` still hashes posting **flags**, contradicting the contract’s “flags are ignored”

| File | Function / expression | Line |
|------|-----------------------|------|
| `candidate/committed.py` | `occurrence_key` – sorting includes `p["flag"]` and the flag is kept in the dict before hashing | 267‑270 |

### Reproduction  

*Original ledger* (clean):

```beancount
2023-04-01 * "Invoice" "Sale"
  Assets:Bank   100.00 USD
  Income:Revenue -100.00 USD
```

*Agent’s submission* – same postings but adds a **flag** (`*` vs `!`) to the transaction:

```beancount
2023-04-01 ! "Invoice" "Sale"
  Assets:Bank   100.00 USD
  Income:Revenue -100.00 USD
```

Both entries are **identical** for the purposes of the contract (flags are renderer‑owned).  
Nevertheless, `occurrence_key` builds `data = txn.as_canonical()`, **does not delete** the `flag` field, and sorts postings by `(account, amount, currency, flag)`.  Consequently the two transactions produce **different occurrence keys**.  

Effect:

* The flagged submission is treated as a *new* occurrence, not a preservation of the original.  
* The original (unflagged) entry is now considered **missing** → counted in `removed` (tamper) → `PENALTY_TAMPER = -0.40`.  
* The flagged entry is counted as **fabricated** → `PENALTY_FABRICATION = -0.40`.  
* The total score drops by **0.80** even though the financial effect is unchanged.

### Severity  

**bug** – The contract explicitly states (see comment at line 260) that *“flags are ignored”*.  By hashing them, the scorer penalises perfectly valid submissions and breaks the contract’s semantics.

---

## 5.  `allocate` treats a duplicate mutation as *always* unresolved

| File | Function / expression | Line |
|------|-----------------------|------|
| `candidate/committed.py` | `allocate` – duplicate handling (`mapping.append((item.id, None))` and later `if item.id in stale_for or not kept`) | 441‑449 |

### Reproduction  

Same setup as defect 2, but now the **duplicate entry is a zero‑sum entry** (so it does not affect balances).  

*Original ledger*:

```beancount
2023-05-01 open Assets:Bank  USD
2023-05-01 open Income:Revenue  USD

2023-05-15 * "Zero‑sum duplicate"
  Assets:Bank   0.00 USD
  Assets:Bank   0.00 USD
```

*Mutation plan* – `DuplicateRecognition` for that entry.  

*Agent’s submission* – **removes one copy**, leaving the other (still zero‑sum).

Result:

* `allocation.unmatched_planted` contains the duplicate’s id (because `item.id in stale_for`).  
* `resolved = 0` even though the duplicate was correctly removed.  

Thus the *errors_resolved* component never reflects a successful duplicate‑removal, artificially lowering the score for a correct repair.

### Severity  

**risk** – Agents cannot ever earn the “resolved” credit for duplicate mutations, which skews the reward landscape and incentivises agents to *avoid* using the duplicate‑mutation kind.

---

## 6.  Expected‑count bookkeeping does not respect `expected_count` > 1 (future‑proofness)

| File | Function / expression | Line |
|------|-----------------------|------|
| `candidate/committed.py` | `_expected_counts` – subtracts exactly **one** per retired key | 247‑249 |
| `candidate/committed.py` | `load_contract` – rejects any `expected_count != 1` for duplicate items | 303‑304 |

### Explanation  

The `PlantedItem` dataclass supports an `expected_count` field (the number of correct copies a duplicate mutation should leave).  The allocation code, however, **always subtracts exactly one** from the original count (`counts[key] -= 1`).  If the contract were ever extended to allow `expected_count = 2` (i.e. “keep two copies”), the bookkeeping would be wrong, leading to stale‑original‑content being mis‑classified.  The current rejection in `load_contract` hides the bug, but the code path is already present and could be unintentionally enabled by a future change.

### Severity  

**risk** – Hidden logic that will break as soon as the policy is relaxed; an adversary could exploit the mismatch by crafting a mutation plan that pretends `expected_count = 1` while the underlying world actually contains more copies, causing the scorer to mis‑attribute tampering.

---

## 7.  Determinism / ordering hazard in `allocate` – reliance on list order of `retired_by_item`

| File | Function / expression | Line |
|------|-----------------------|------|
| `candidate/committed.py` | `retired_by_item` is a **dict** built from a loop over `env.planted` (preserves insertion order) | 229‑240 |
| `candidate/committed.py` | `stale_for` built from `stale_items` (order‑dependent) | 438‑439 |

### Explanation  

Python 3.7+ preserves insertion order for dicts, but the contract’s specification treats the *allocation* as **canonical occurrence order** – it must be *independent* of the order in which planted items were supplied.  Because `retired_by_item` is a plain dict, the *first* planted item that retires a given key wins the slot in `retired_slots[key].pop(0)`.  If two planted items retire the *same* original key (e.g. two `alter` mutations that both target the same wrong entry – a situation that should be impossible but can be forced by a malformed mutation plan), the allocation outcome depends on the order of the mutations in the plan, not on any canonical rule.  This violates the contract’s determinism guarantee.

### Severity  

**risk** – In a multi‑agent competition where mutation plans are generated automatically, a nondeterministic tie‑break could lead to different scores for the same logical plan, breaking reproducibility.

---

# Overall Impact

* The **STALE bucket** (defect 1) alone lets an agent achieve a **0.70** score while the delivered ledger still contains a *wrong* entry.  This directly violates the contract’s guarantee that “any retained original content that should have been retired is penalised as tampering or fabrication”.
* Defects 2, 5, 6, 7 together make the *duplicate‑recognition* mutation effectively unusable for gaining the “resolved” credit and open subtle nondeterministic behaviour.
* Defect 4 (flags in `occurrence_key`) creates a **false‑positive tampering** penalty for perfectly valid submissions that merely change a flag, contradicting the contract’s own comment.
* Defect 3 is a usability nit but may cause unnecessary derivation failures.

These issues should be fixed before the environment is released for a deterministic‑reward RL benchmark.