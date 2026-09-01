# Generated-world reviews — nvidia/nemotron-3-super-120b-a12b, 2026-09-01

*The reviewer saw public files only. The planted truth is appended by the script after each answer.*

---

## train:5 → task-bc549dabae264a1673b1663a

We need to reconcile ledger vs bank statement for July. Identify discrepancies: missing entries, wrong amounts, duplicate entries, timing differences (outstanding checks, deposits in transit). Use policy.

First, compute ledger balance for Assets:Bank:Checking after all July entries plus opening balance.

Opening balance 20540.04.

Now sum all bank checking movements from ledger (debits negative? In ledger, Assets:Bank:Checking is asset, so increase is debit (positive), decrease is credit (negative). In entries, they show Assets:Bank:Checking with amount (positive for debit? Actually they list as e.g., line 32: Assets:Bank:Checking -3250.00 USD (credit). So negative means outflow (check). Positive means inflow (deposit). Let's compute net change.

We'll go through ledger lines affecting Assets:Bank:Checking:

Line 32: -3250.00
72: -541.82
92: +8600.23
96: +8600.23 (duplicate? Actually lines 91-97 duplicate same entry)
110: -2548.83
114: -7455.34
127: -876.10
131: -4026.23
138: +5045.24
143: -458.75
146: +4383.52
160: -422.65
163: +9366.34
189: +14049.52
194: -1000.05
197: +7890.34
210: +8794.10
214: +2420.11
219: -6650.40
222: +970.87
226: +3859.72
230: +7039.16
233: +1299.45
239: -3250.00 (prepayment rent)
242: +1303.14
246: +12571.19

Also line 210? Already accounted. Also line 222 etc.

Let's sum.

I'll compute using mental arithmetic.

Start 0.

-3250.00
-541.82 => -3791.82
+8600.23 => 4808.41
+8600.23 => 13408.64
-2548.83 => 10859.81
-7455.34 => 3404.47
-876.10 => 2528.37
-4026.23 => -1497.86
+5045.24 => 3547.38
-458.75 => 3088.63
+4383.52 => 7472.15
-422.65 => 7049.50
+9366.34 => 16415.84
+14049.52 => 30465.36
-1000.05 => 29465.31
+7890.34 => 37355.65
+8794.10 => 46149.75
+2420.11 => 48569.86
-6650.40 => 41919.46
+970.87 => 42890.33
+3859.72 => 46750.05
+7039.16 => 53789.21
+1299.45 => 55088.66
-3250.00 => 51838.66
+1303.14 => 53141.80
+12571.19 => 65712.99

Net change = +65712.99

Add opening 20540.04 => ledger bank balance = 86253.03

Now compute bank statement ending balance: last line shows balance 62920.71 after all transactions. Wait statement shows balance after last entry 62920.71. Let's verify: Starting balance 20540.04, then apply each statement row.

Let's compute statement net change to see if matches.

Statement rows (date, description, debit, credit):

Row3: debit 3250.00 (check) => -3250
Row4: debit 451.82 => -451.82
Row5: credit 8600.23 => +8600.23
Row6: debit 876.10 => -876.10
Row7: debit 7455.34 => -7455.34
Row8: debit 4026.23 => -4026.23
Row9: debit 458.75 => -458.75
Row10: debit 2548.83 => -2548.83
Row11: credit 5045.24 => +5045.24
Row12: credit 4383.52 => +4383.52
Row13: debit 422.65 => -422.65
Row14: debit 10984.43 => -10984.43
Row15: credit 9366.34 => +9366.34
Row16: credit 14049.52 => +14049.52
Row17: debit 1000.05 => -1000.05
Row18: credit 7890.34 => +7890.34
Row19: credit 2420.11 => +2420.11
Row20: debit 48.50 => -48.50 (maintenance charge)
Row21: credit 970.87 => +970.87
Row22: credit 8794.10 => +8794.10
Row23: debit 6650.40 => -6650.40
Row24: credit 1299.45 => +1299.45
Row25: credit 3859.72 => +3859.72
Row26: credit 1303.14 => +1303.14
Row27: credit 12571.19 => +12571.19

Now sum.

Start 0.

-3250.00
-451.82 => -3701.82
+8600.23 => 4898.41
-876.10 => 4022.31
-7455.34 => -3433.03
-4026.23 => -7459.26
-458.75 => -7918.01
-2548.83 => -10466.84
+5045.24 => -5421.60
+4383.52 => -1038.08
-422.65 => -1460.73
-10984.43 => -12445.16
+9366.34 => -3078.82
+14049.52 => 10970.70
-1000.05 => 9970.65
+7890.34 => 17860.99
+2420.11 => 20281.10
-48.50 => 20232.60
+970.87 => 21203.47
+8794.10 => 29997.57
-6650.40 => 23347.17
+1299.45 => 24646.62
+3859.72 => 28506.34
+1303.14 => 29809.48
+12571.19 => 42380.67

Net change = +42380.67

Add opening 20540.04 => statement ending balance = 62920.71 matches.

Thus ledger bank balance 86253.03 vs statement 62920.71 difference = +23332.32 (ledger higher). Means ledger has extra inflows or missing outflows relative to bank.

We need to identify discrepancies: entries in ledger not matching bank (missing, wrong amount, duplicate). Also timing differences: outstanding checks (ledger has check not yet cleared) and deposits in transit (ledger recorded receipt not yet in bank). Those are not errors.

We need to compare each ledger transaction to bank statement rows.

Let's list ledger bank movements with date, amount, counterparty (description). Then see if bank statement has matching row within clearing window (policy says same amount and counterparty, dated within clearing window for the rail). We need to infer clearing window: likely checks take a few days, ACH same day? Not given. We'll assume: checks may clear same day or next few days; ACH likely same day. But we can use statement dates to match.

Let's extract ledger bank movements:

I'll create list:

1. 2025-07-01? Actually rent check 1599 on 2025-07-01? Entry line 30-32: date 2025-07-01, Foundry Asset Management, amount -3250.00 (check). Bank statement shows CHECK 1599 FOUNDRY ASSET MANAGEMENT on 2025-07-03 debit 3250.00. So ledger date 2025-07-01, bank date 2025-07-03. That's a timing difference (outstanding check? Actually check issued 7/1, cleared 7/3). According to policy, ledger date is transaction date (check issue). Bank processes later, so not error. This is an outstanding check as of statement cutoff? Statement cutoff is 7/31, check cleared 7/3, so it's cleared. Not outstanding. But it's a timing difference in the sense that ledger date differs from bank date, but policy says ledger date never later than statement date for same item, and we do not change it. So not an error.

2. 2025-07-07 Quintero and Sons Stationery debit card -541.82. Bank statement shows DEBIT CARD QUINTERO AND SONS STATIONERY on 2025-07-07 debit 451.82. Wait amount mismatch: ledger -541.82 vs bank -451.82. Difference 90.00. Also description same. This looks like wrong amount in ledger (overstated by 90). Could be a duplicate? Let's check if there is another entry for same vendor same day? No. So ledger has wrong amount.

3. 2025-07-09 Rasmussen and Sons SI-1231 settled in full: +8600.23 (deposit). Bank statement shows ACH IN RASMUSSEN AND SONS, SI-1231 on 2025-07-11 credit 8600.23. Ledger date 2025-07-09, bank date 2025-07-11. That's a deposit in transit? Actually ledger records receipt when received (maybe check received 7/9, deposited 7/11). According to policy, ledger date is transaction date (receipt). Bank processes later, so not error. This is a timing difference (deposit in transit) as of statement cutoff? Since statement includes it on 7/11, it's cleared by month end. Not outstanding.

But note there is duplicate entry lines 91-97: two identical entries for same settlement, both +8600.23 each. That's a duplicate posting (double counted). Bank only has one credit of 8600.23. So ledger has duplicate entry (error). We'll need to remove one.

4. 2025-07-11 Millbrook Provisions SI-1233 sale: +23415.86 AR increase, not bank. No bank movement.

5. 2025-07-11 Millbrook Provisions COGS: inventory change.

6. 2025-07-14 Ironbridge Supplies payment PI-2068: -2548.83 (check? Actually entry shows Liabilities:AP +2548.83, Assets:Bank:Checking -2548.83). Bank statement shows ACH OUT IRONBRIDGE SUPPLIES, PI-2068 on 2025-07-17 debit 2548.83. Ledger date 2025-07-14, bank date 2025-07-17. That's timing difference (ACH maybe same day but appears 3 days later). Not error.

7. 2025-07-14 Ironbridge Supplies payment PI-2069: -7455.34. Bank statement shows ACH OUT IRONBRIDGE SUPPLIES, PI-2069 on 2025-07-16 debit 7455.34. Ledger date 2025-07-14, bank date 2025-07-16. Timing difference.

8. 2025-07-14 Millbrook Provisions SI-1234 sale: +2362.63 AR.

9. 2025-07-14 Millbrook Provisions COGS.

10. 2025-07-15 Quintero and Sons Stationery printer toner -876.10. Bank statement shows DEBIT CARD QUINTERO AND SONS STATIONERY on 2025-07-15 debit 876.10. Matches amount and date exactly. Good.

11. 2025-07-16 Ironbridge Supplies payment PI-2070 check 1600: -4026.23. Bank statement shows CHECK 1600 IRONBRIDGE SUPPLIES on 2025-07-16 debit 4026.23. Matches.

12. 2025-07-16 Ironbridge Supplies stock purchase PI-2075: inventory increase, no bank.

13. 2025-07-16 Rasmussen and Sons SI-1227 settled in full check 7401: +5045.24. Bank statement shows CHECK 7401 RASMUSSEN AND SONS on 2025-07-18 credit 5045.24. Ledger date 2025-07-16, bank date 2025-07-18. Timing difference (check cleared two days later). Not error.

14. 2025-07-17 Quintero and Sons Stationery stationery -458.75. Bank statement shows DEBIT CARD QUINTERO AND SONS STATIONERY on 2025-07-17 debit 458.75. Matches.

15. 2025-07-17 Rasmussen and Sons instalment against SI-1232: +4383.52. Bank statement shows ACH IN RASMUSSEN AND SONS, SI-1232 on 2025-07-18 credit 4383.52. Ledger date 2025-07-17, bank date 2025-07-18. Timing difference.

16. 2025-07-17 Rasmussen and Sons SI-1235 sale: +3859.72 AR.

17. 2025-07-17 Rasmussen and Sons COGS.

18. 2025-07-21 Quintero and Sons Stationery stationery check 1601: -422.65. Bank statement shows CHECK 1601 QUINTERO AND SONS STATIONERY on 2025-07-22 debit 422.65. Ledger date 2025-07-21, bank date 2025-07-22. Timing difference.

19. 2025-07-21 Millbrook Provisions instalment against SI-1233: +9366.34. Bank statement shows ACH IN MILLBROOK PROVISIONS, SI-1233 on 2025-07-23 credit 9366.34. Ledger date 2025-07-21, bank date 2025-07-23. Timing difference.

20. 2025-07-21 Millbrook Provisions SI-1236 sale: +8794.10 AR.

21. 2025-07-21 Millbrook Provisions COGS.

22. 2025-07-21 Rasmussen and Sons SI-1237 sale: +3723.25 AR.

23. 2025-07-21 Rasmussen and Sons COGS.

24. 2025-07-22 Ironbridge Supplies payment PI-2067: -10984.43. Bank statement shows ACH OUT IRONBRIDGE SUPPLIES, PI-2067 on 2025-07-23 debit 10984.43. Ledger date 2025-07-22, bank date 2025-07-23. Timing difference.

25. 2025-07-24 Millbrook Provisions instalment against SI-1233: +14049.52. Bank statement shows ACH IN MILLBROOK PROVISIONS, SI-1233 on 2025-07-25 credit 14049.52. Ledger date 2025-07-24, bank date 2025-07-25. Timing difference.

26. 2025-07-25 Ironbridge Supplies payment PI-2072: -1000.05. Bank statement shows ACH OUT IRONBRIDGE SUPPLIES, PI-2072 on 2025-07-28 debit 1000.05. Ledger date 2025-07-25, bank date 2025-07-28. Timing difference.

27. 2025-07-25 Rasmussen and Sons instalment against SI-1232: +7890.34. Bank statement shows ACH IN RASMUSSEN AND SONS, SI-1232 on 2025-07-28 credit 7890.34. Ledger date 2025-07-25, bank date 2025-07-28. Timing difference.

28. 2025-07-25 Rasmussen and Sons SI-1238 sale: +20951.98 AR.

29. 2025-07-25 Rasmussen and Sons COGS.

30. 2025-07-28 Millbrook Provisions SI-1236 settled in full: +8794.10. Bank statement shows ACH IN MILLBROOK PROVISIONS, SI-1236 on 2025-07-30 credit 8794.10. Ledger date 2025-07-28, bank date 2025-07-30. Timing difference.

31. 2025-07-28 Rasmussen and Sons instalment against SI-1237 check 7402: +2420.11. Bank statement shows CHECK 7402 RASMUSSEN AND SONS on 2025-07-29 credit 2420.11. Ledger date 2025-07-28, bank date 2025-07-29. Timing difference.

32. 2025-07-29 Ironbridge Supplies payment PI-2071: -6650.40. Bank statement shows ACH OUT IRONBRIDGE SUPPLIES, PI-2071 on 2025-07-31 debit 6650.40. Ledger date 2025-07-29, bank date 2025-07-31. Timing difference.

33. 2025-07-29 Millbrook Provisions SI-1230 settled in full: +970.87. Bank statement shows ACH IN MILLBROOK PROVISIONS, SI-1230 on 2025-07-30 credit 970.87. Ledger date 2025-07-29, bank date 2025-07-30. Timing difference.

34. 2025-07-29 Rasmussen and Sons SI-1235 settled in full check 7403: +3859.72. Bank statement shows CHECK 7403 RASMUSSEN AND SONS on 2025-07-31 credit 3859.72. Ledger date 2025-07-29, bank date 2025-07-31. Timing difference.

35. 2025-07-30 Millbrook Provisions SI-1228 settled in full check 7601: +7039.16. Bank statement shows ??? Actually bank statement does not have a line for check 7601? Wait we have line 229: "2025-07-30,ACH IN MILLBROOK PROVISIONS,SI-1228,,7039.16,50537.61". That's an ACH, not check. Ledger says check 7601. Bank shows ACH IN. So mismatch: ledger records a check deposit, bank shows ACH credit. Amount same 7039.16, counterparty Millbrook Provisions, reference SI-1228. So ledger has wrong payment method (check vs ACH) but amount matches. According to policy, we match based on amount and counterparty, dated within clearing window for the rail the row names. The rail differs (check vs ACH). However policy says "A statement row and a ledger entry of the same amount and the same counterparty, dated within the clearing window for the rail the row names, are the same transaction". If rail differs, they are not considered same? Likely they'd still be same transaction but the ledger incorrectly recorded as check instead of ACH. This is an error in narration (payment method) but not amount. However we need to decide if it's a discrepancy: entry booked with wrong amount? No amount correct. Entry booked with wrong description? Might be considered wrong amount? Not amount. Could be considered a misposting? But policy doesn't require matching method. However we might treat as not an error because amount and counterparty match, dates within clearing window (ledger date 2025-07-30, bank date 2025-07-30). So it's same transaction, just ledger description inaccurate but not affecting accounts. So not an error.

36. 2025-07-30 Millbrook Provisions instalment against SI-1234 check 7600: +1299.45. Bank statement shows ??? Actually line 233: "2025-07-31,CHECK 7600 MILLBROOK PROVISIONS,7600,,1299.45,45186.66". That's a check on 2025-07-31 credit 1299.45. Ledger date 2025-07-30, bank date 2025-07-31. Timing difference (check cleared next day). Not error.

37. 2025-07-31 Foundry Asset Management August premises rent settled early check 1602: -3250.00 (prepayment). Bank statement does NOT have this transaction. Let's check statement: no line for check 1602 or Foundry Asset Management on 7/31. So ledger has a check outflow not appearing in statement. Could be outstanding check (issued 7/31, not cleared by month end). According to policy, outstanding checks are timing differences, not errors. So this is an outstanding check.

38. 2025-07-31 Rasmussen and Sons instalment against SI-1237: +1303.14. Bank statement shows ACH IN RASMUSSEN AND SONS, SI-1237 on 2025-07-31 credit 1303.14. Matches date and amount. Good.

39. 2025-07-31 Rasmussen and Sons instalment against SI-1238: +12571.19. Bank statement shows ACH IN RASMUSSEN AND SONS, SI-1238 on 2025-07-31 credit 12571.19. Matches.

Now also need to consider any bank statement rows not matched by ledger (missing entries). Let's list statement rows and see if ledger has matching.

Statement rows:

3. 2025-07-03 CHECK 1599 FOUNDRY ASSET MANAGEMENT 3250 debit -> matched ledger entry (check 1599) though date diff.

4. 2025-07-07 DEBIT CARD QUINTERO AND SONS STATIONERY 451.82 debit -> ledger has -541.82 (wrong amount). So ledger missing correct amount; has wrong amount entry.

5. 2025-07-11 ACH IN RASMUSSEN AND SONS SI-1231 8600.23 credit -> ledger has two entries +8600.23 each on 7/9 (duplicate). So ledger has extra entry (duplicate) and date mismatch.

6. 2025-07-15 DEBIT CARD QUINTERO AND SONS STATIONERY 876.10 debit -> ledger has -876.10 on 7/15 matches.

7. 2025-07-16 ACH OUT IRONBRIDGE SUPPLIES PI-2069 7455.34 debit -> ledger has -7455.34 on 7/14 (timing diff).

8. 2025-07-16 CHECK 1600 IRONBRIDGE SUPPLIES 4026.23 debit -> ledger has -4026.23 on 7/16 matches.

9. 2025-07-17 DEBIT CARD QUINTERO AND SONS STATIONERY 458.75 debit -> ledger has -458.75 on 7/17 matches.

10. 2025-07-17 ACH OUT IRONBRIDGE SUPPLIES PI-2068 2548.83 debit -> ledger has -2548.83 on 7/14 (timing diff).

11. 2025-07-18 CHECK 7401 RASMUSSEN AND SONS 5045.24 credit -> ledger has +5045.24 on 7/16 (timing diff).

12. 2025-07-18 ACH IN RASMUSSEN AND SONS SI-1232 4383.52 credit -> ledger has +4383.52 on 7/17 (timing diff).

13. 2025-07-22 CHECK 1601 QUINTERO AND SONS STATIONERY 422.65 debit -> ledger has -422.65 on 7/21 (timing diff).

14. 2025-07-23 ACH OUT IRONBRIDGE SUPPLIES PI-2067 10984.43 debit -> ledger has -10984.43 on 7/22 (timing diff).

15. 2025-07-23 ACH IN MILLBROOK PROVISIONS SI-1233 9366.34 credit -> ledger has +9366.34 on 7/21 (timing diff).

16. 2025-07-25 ACH IN MILLBROOK PROVISIONS SI-1233 14049.52 credit -> ledger has +14049.52 on 7/24 (timing diff).

17. 2025-07-28 ACH OUT IRONBRIDGE SUPPLIES PI-2072 1000.05 debit -> ledger has -1000.05 on 7/25 (timing diff).

18. 2025-07-28 ACH IN RASMUSSEN AND SONS SI-1232 7890.34 credit -> ledger has +7890.34 on 7/25 (timing diff).

19. 2025-07-29 CHECK 7402 RASMUSSEN AND SONS 2420.11 credit -> ledger has +2420.11 on 7/28 (timing diff).

20. 2025-07-30 ACCOUNT MAINTENANCE CHARGE 48.50 debit -> ledger has no entry for bank fee. According to policy, bank service charges recorded to Expenses:BankFees on date bank applies them. Ledger missing this fee. So missing entry.

21. 2025-07-30 ACH IN MILLBROOK PROVISIONS SI-1230 970.87 credit -> ledger has +970.87 on 7/29 (timing diff).

22. 2025-07-30 ACH IN MILLBROOK PROVISIONS SI-1236 8794.10 credit -> ledger has +8794.10 on 7/28 (timing diff).

23. 2025-07-31 ACH OUT IRONBRIDGE SUPPLIES PI-2071 6650.40 debit -> ledger has -6650.40 on 7/29 (timing diff).

24. 2025-07-31 CHECK 7600 MILLBROOK PROVISIONS 1299.45 credit -> ledger has +1299.45 on 7/30 (timing diff).

25. 2025-07-31 CHECK 7403 RASMUSSEN AND SONS 3859.72 credit -> ledger has +3859.72 on 7/29 (timing diff).

26. 2025-07-31 ACH IN RASMUSSEN AND SONS SI-1237 1303.14 credit -> ledger has +1303.14 on 7/31 matches.

27. 2025-07-31 ACH IN RASMUSSEN AND SONS SI-1238 12571.19 credit -> ledger has +12571.19 on 7/31 matches.

Now also need to consider any ledger entries that have no bank counterpart (i.e., missing in statement) besides the prepayment rent check 1602 and duplicate SI-1231 settlement and wrong amount debit card entry.

Also ledger has entry for Quintero and Sons Stationery debit card on 7/7 with wrong amount -541.82 (should be -451.82). So that's a wrong amount entry.

Also ledger has duplicate SI-1231 settlement (two entries). One of them is correct (should be single). So we have an extra entry (duplicate) that needs removal.

Also ledger has prepayment rent check 1602 on 7/31 not in statement (outstanding check). That's timing difference, not error.

Also ledger has entry for Quintero and Sons Stationery debit card on 7/7 with wrong amount; we need to correct amount to -451.82.

Also ledger missing bank maintenance charge on 7/30: need to add Expenses:BankFees 48.50 debit, Assets:Bank:Checking credit -48.50.

Also ledger has entry for Quintero and Sons Stationery debit card on 7/7 with wrong amount; we need to adjust.

Also ledger has entry for Quintero and Sons Stationery debit card on 7/7 with wrong amount; we need to correct.

Also ledger has entry for Quintero and Sons Stationery debit card on 7/7 with wrong amount; we need to correct.

Also ledger has entry for Quintero and Sons Stationery debit card on 7/7 with wrong amount; we need to correct.

Now also check for any other discrepancies: The ledger entry for Quintero and Sons Stationery debit card on 7/7 is wrong amount; also there is a ledger entry for Quintero and Sons Stationery debit card on 7/7? Actually there is also a ledger entry for Quintero and Sons Stationery debit card on 7/7? Yes line 70-72. That's the only one.

Now also check for any ledger entries that are missing from statement but not outstanding checks/deposits in transit: e.g., the duplicate SI-1231 settlement (one extra) is an error (duplicate). The wrong amount debit card is error. Missing bank fee is error.

Also check for any ledger entries that have amount correct but date mismatched beyond clearing window? Policy says ledger date never later than statement date for same item. All ledger dates are <= statement dates (we saw). So fine.

Now also check for any ledger entries that have amount correct but counterparty mismatched? Eg, the SI-1228 settled in full check 7601 vs ACH IN: counterparty same, amount same, date same, just method diff. Not error.

Now also check for any ledger entries that are missing from statement but are not outstanding checks/deposits in transit: e.g., the prepayment rent check 1602 is outstanding check (issued 7/31, not cleared). That's timing difference.

Now also check for any ledger entries that are deposits in transit: e.g., the SI-1231 settlement on 7/9 vs statement 7/11 is deposit in transit (ledger date earlier). That's timing difference.

Now also check for any ledger entries that are outstanding checks: e.g., check 1602 (prepayment rent) outstanding; also maybe any other checks issued but not cleared by month end: check 1602 only. Also check 7600? Actually check 7600 appears in statement on 7/31 credit, ledger date 7/30, cleared same month, not outstanding. Check 7403 cleared 7/31. Check 7402 cleared 7/29. Check 7601? Actually ledger has check 7601 for SI-1228 settled in full on 7/30, but statement shows ACH IN not check. So not a check.

Thus outstanding checks list: check 1602 (Foundry Asset Management) -3250.00.

Deposits in transit: any ledger receipts not yet in statement by month end? All ledger receipts appear in statement by month end (since statement ends 7/31

### Planted truth (appended after the answer)

- duplicate — duplicated_customer_receipt: 2025-07-09 Rasmussen and Sons (('Assets:AR', '-8600.23'), ('Assets:Bank:Checking', '8600.23')) (evidence: 2025-07-11 ACH IN RASMUSSEN AND SONS)
- omit — unrecorded_bank_fee: 2025-07-30 Cobalt Community Bank (('Assets:Bank:Checking', '-48.5'), ('Expenses:BankFees', '48.5')) (evidence: 2025-07-30 ACCOUNT MAINTENANCE CHARGE)
- alter — transposed_expense_payment: 2025-07-07 Quintero and Sons Stationery (('Assets:Bank:Checking', '-451.82'), ('Expenses:Office', '451.82')) (evidence: 2025-07-07 DEBIT CARD QUINTERO AND SONS STATIONERY)
- outstanding: outstanding_check_7601 2025-07-30 7039.16
- outstanding: outstanding_check_1602 2025-07-31 -3250.00

---

## train:3:hard → task-4ae8e6956492365b2c24b631

We need to reconcile November checking account: compare ledger entries to bank statement rows.

We have ledger entries (including opening balance). Need to list discrepancies: missing entries, wrong amount, duplicate entries, timing differences (outstanding cheques, deposits in transit) not errors.

We must cite policy or master file for each.

We need to produce Part A as a table with columns: Date, Amount, Counterparty, Account to post to, Reason (policy or master). For each discrepancy.

We need to examine ledger entries vs bank statement.

Let's list ledger entries for November (excluding opening). We'll extract each transaction with date, description, amounts.

I'll parse ledger lines.

I'll create a list.

From ledger:

Line 30-32: 2025-11-03 * "Meridian Materials Co" "PI-2076 paid"
    Liabilities:AP +2808.82
    Assets:Bank:Checking -2808.82

So bank outflow 2808.82 to Meridian Materials Co.

Line 34-36: 2025-11-03 * "Nakamura Property Holdings" "November premises rent, check 1061"
    Expenses:Rent +4000
    Assets:Bank:Checking -4000

Outflow 4000 to Nakamura Property Holdings.

Line 38-40: 2025-11-05 * "Eastgate Business Supply" "Packaging and office supplies"
    Expenses:Office +852.57
    Assets:Bank:Checking -852.57

Outflow 852.57 to Eastgate Business Supply.

Line 42-45: 2025-11-05 * "Sprocket Markets" "Invoice SI-1139 raised"
    Assets:AR +8255.57
    Income:Sales -6879.64
    Liabilities:SalesTax-Payable -1375.93

No bank movement.

Line 47-49: 2025-11-05 * "Sprocket Markets" "Cost of goods sold on SI-1139"
    Expenses:COGS +3302.23
    Assets:Inventory -3302.23

No bank.

Line 51-53: 2025-11-07 * "Meridian Materials Co" "PI-2074 paid"
    Liabilities:AP +7581.22
    Assets:Bank:Checking -7581.22

Outflow 7581.22 to Meridian Materials Co.

Line 55-57: 2025-11-10 * "Eastgate Business Supply" "Packaging and office supplies"
    Expenses:Office +131.66
    Assets:Bank:Checking -131.66

Outflow 131.66 to Eastgate Business Supply.

Line 59-61: 2025-11-10 * "Meridian Materials Co" "PI-2079 paid"
    Liabilities:AP +9786.46
    Assets:Bank:Checking -9786.46

Outflow 9786.46 to Meridian Materials Co.

Line 63-65: 2025-11-10 * "Meridian Materials Co" "Stock purchase PI-2080"
    Assets:Inventory +6106.05
    Liabilities:AP -6106.05

No bank.

Line 67-69: 2025-11-10 * "Sprocket Markets" "Customer payment for SI-1138"
    Assets:Bank:Checking +2734.75
    Assets:AR -2734.75

Inflow 2734.75 from Sprocket Markets.

Line 71-74: 2025-11-10 * "Clearwater Mercantile" "Invoice SI-1140 raised"
    Assets:AR +1938.07
    Income:Sales -1615.06
    Liabilities:SalesTax-Payable -323.01

No bank.

Line 76-78: 2025-11-10 * "Clearwater Mercantile" "Cost of goods sold on SI-1140"
    Expenses:COGS +759.08
    Assets:Inventory -759.08

No bank.

Line 80-82: 2025-11-12 * "Sprocket Markets" "Payment on account against SI-1139, check 6601"
    Assets:Bank:Checking +4127.78
    Assets:AR -4127.78

Inflow 4127.78 from Sprocket Markets.

Line 84-86: 2025-11-13 * "Meridian Materials Co" "PI-2075 paid"
    Liabilities:AP +1907.62
    Assets:Bank:Checking -1907.62

Outflow 1907.62 to Meridian Materials Co.

Line 88-90: 2025-11-13 * "Meridian Materials Co" "PI-2077 paid"
    Liabilities:AP +3735.69
    Assets:Bank:Checking -3735.69

Outflow 3735.69 to Meridian Materials Co.

Line 92-95: 2025-11-13 * "Clearwater Mercantile" "Invoice SI-1141 raised"
    Assets:AR +13656.14
    Income:Sales -11380.12
    Liabilities:SalesTax-Payable -2276.02

No bank.

Line 97-99: 2025-11-13 * "Clearwater Mercantile" "Cost of goods sold on SI-1141"
    Expenses:COGS +7624.68
    Assets:Inventory -7624.68

No bank.

Line 101-104: 2025-11-13 * "Lindqvist Family Stores" "Invoice SI-1142 raised"
    Assets:AR +6515.06
    Income:Sales -5429.22
    Liabilities:SalesTax-Payable -1085.84

No bank.

Line 106-108: 2025-11-13 * "Lindqvist Family Stores" "Cost of goods sold on SI-1142"
    Expenses:COGS +2497.44
    Assets:Inventory -2497.44

No bank.

Line 110-112: 2025-11-14 * "Eastgate Business Supply" "Shipping labels and envelopes"
    Expenses:Office +226.48
    Assets:Bank:Checking -226.48

Outflow 226.48 to Eastgate Business Supply.

Line 114-116: 2025-11-17 * "Clearwater Mercantile" "Customer payment for SI-1137"
    Assets:Bank:Checking +1547.57
    Assets:AR -1547.57

Inflow 1547.57 from Clearwater Mercantile.

Line 118-120: 2025-11-17 * "Lindqvist Family Stores" "Payment on account against SI-1142"
    Assets:Bank:Checking +4234.79
    Assets:AR -4234.79

Inflow 4234.79 from Lindqvist Family Stores.

Line 122-124: duplicate? Actually line 122-124 is same as previous? Let's see:

Line 122-124: 2025-11-17 * "Lindqvist Family Stores" "Payment on account against SI-1142"
    Assets:Bank:Checking +4234.79
    Assets:AR -4234.79

Yes duplicate entry (same date, same description). So ledger has two identical entries for same payment.

Line 126-129: 2025-11-17 * "Clearwater Mercantile" "Invoice SI-1143 raised"
    Assets:AR +2878.26
    Income:Sales -2398.55
    Liabilities:SalesTax-Payable -479.71

No bank.

Line 131-133: 2025-11-17 * "Clearwater Mercantile" "Cost of goods sold on SI-1143"
    Expenses:COGS +1631.01
    Assets:Inventory -1631.01

No bank.

Line 135-138: 2025-11-17 * "Lindqvist Family Stores" "Invoice SI-1144 raised"
    Assets:AR +1687.87
    Income:Sales -1406.56
    Liabilities:SalesTax-Payable -281.31

No bank.

Line 140-142: 2025-11-17 * "Lindqvist Family Stores" "Cost of goods sold on SI-1144"
    Expenses:COGS +647.02
    Assets:Inventory -647.02

No bank.

Line 144-147: 2025-11-17 * "Lindqvist Family Stores" "Invoice SI-1145 raised"
    Assets:AR +5633.70
    Income:Sales -4694.75
    Liabilities:SalesTax-Payable -938.95

No bank.

Line 149-151: 2025-11-17 * "Lindqvist Family Stores" "Cost of goods sold on SI-1145"
    Expenses:COGS +2206.53
    Assets:Inventory -2206.53

No bank.

Line 153-155: 2025-11-18 * "Meridian Materials Co" "Stock purchase PI-2081"
    Assets:Inventory +3832.06
    Liabilities:AP -3832.06

No bank.

Line 157-159: 2025-11-18 * "Clearwater Mercantile" "Payment on account against SI-1141, check 6401"
    Assets:Bank:Checking +7510.88
    Assets:AR -7510.88

Inflow 7510.88 from Clearwater Mercantile.

Line 161-164: 2025-11-18 * "Sprocket Markets" "Invoice SI-1146 raised"
    Assets:AR +973.46
    Income:Sales -811.22
    Liabilities:SalesTax-Payable -162.24

No bank.

Line 166-168: 2025-11-18 * "Sprocket Markets" "Cost of goods sold on SI-1146"
    Expenses:COGS +397.50
    Assets:Inventory -397.50

No bank.

Line 170-172: 2025-11-20 * "Eastgate Business Supply" "Packaging and office supplies"
    Expenses:Office +471.22
    Assets:Bank:Checking -471.22

Outflow 471.22 to Eastgate Business Supply.

Line 174-177: 2025-11-21 * "Clearwater Mercantile" "Invoice SI-1147 raised"
    Assets:AR +2470.06
    Income:Sales -2058.38
    Liabilities:SalesTax-Payable -411.68

No bank.

Line 179-181: 2025-11-21 * "Clearwater Mercantile" "Cost of goods sold on SI-1147"
    Expenses:COGS +1193.86
    Assets:Inventory -1193.86

No bank.

Line 183-186: 2025-11-21 * "Sprocket Markets" "Invoice SI-1148 raised"
    Assets:AR +6900.37
    Income:Sales -5750.31
    Liabilities:SalesTax-Payable -1150.06

No bank.

Line 188-190: 2025-11-21 * "Sprocket Markets" "Cost of goods sold on SI-1148"
    Expenses:COGS +3105.17
    Assets:Inventory -3105.17

No bank.

Line 192-194: 2025-11-24 * "Sprocket Markets" "Payment on account against SI-1148"
    Assets:Bank:Checking +3795.20
    Assets:AR -3795.20

Inflow 3795.20 from Sprocket Markets.

Line 196-198: 2025-11-26 * "Lindqvist Family Stores" "Payment on account against SI-1144"
    Assets:Bank:Checking +1097.12
    Assets:AR -1097.12

Inflow 1097.12 from Lindqvist Family Stores.

Line 200-202: 2025-11-26 * "Sprocket Markets" "Payment on account against SI-1146"
    Assets:Bank:Checking +535.40
    Assets:AR -535.40

Inflow 535.40 from Sprocket Markets.

Line 204-206: 2025-11-26 * "Clearwater Mercantile" "Payment on account against SI-1147"
    Assets:Bank:Checking +1482.04
    Assets:AR -1482.04

Inflow 1482.04 from Clearwater Mercantile.

Line 208-210: 2025-11-28 * "Nakamura Property Holdings" "December rent prepaid, check 1063"
    Assets:Prepayments +4000
    Assets:Bank:Checking -4000

Outflow 4000 to Nakamura Property Holdings (prepaid rent).

Line 212-214: 2025-11-28 * "Sprocket Markets" "Payment on account against SI-1139"
    Assets:Bank:Checking +1651.12
    Assets:AR -1651.12

Inflow 1651.12 from Sprocket Markets.

Line 216-218: 2025-11-28 * "Clearwater Mercantile" "Customer payment for SI-1140, check 6402"
    Assets:Bank:Checking +1938.07
    Assets:AR -1938.07

Inflow 1938.07 from Clearwater Mercantile.

Line 220-222: 2025-11-28 * "Lindqvist Family Stores" "Payment on account against SI-1142, check 5400"
    Assets:Bank:Checking +2280.27
    Assets:AR -2280.27

Inflow 2280.27 from Lindqvist Family Stores.

Line 224-226: 2025-11-28 * "Clearwater Mercantile" "Customer payment for SI-1143"
    Assets:Bank:Checking +2878.26
    Assets:AR -2878.26

Inflow 2878.26 from Clearwater Mercantile.

Line 228-230: 2025-11-29 * "Lindqvist Family Stores" "Payment on account against SI-1144"
    Assets:Bank:Checking +295.38
    Assets:AR -295.38

Inflow 295.38 from Lindqvist Family Stores.

Line 232-234: 2025-11-29 * "Clearwater Mercantile" "Payment on account against SI-1147, check 6403"
    Assets:Bank:Checking +988.02
    Assets:AR -988.02

Inflow 988.02 from Clearwater Mercantile.

Line 236-238: 2025-11-30 * "Merchants Row National Bank" "Account maintenance charge"
    Expenses:BankFees +26.50
    Assets:Bank:Checking -26.50

Outflow 26.50 bank fee.

Now let's list bank statement rows (excluding opening balance line). We'll parse each.

Bank statement CSV lines:

2: 2025-11-01 Opening balance carried forward (balance 30470.59) - matches opening.

3: 2025-11-04, ACH OUT MERIDIAN MATERIALS CO, PI-2076, debit 2808.82, balance 27661.77

4: 2025-11-04, CHECK 1061 NAKAMURA PROPERTY HOLDINGS, 1061, debit 4000.00, balance 23661.77

5: 2025-11-05, DEBIT CARD EASTGATE BUSINESS SUPPLY, , debit 852.57, balance 22809.20

6: 2025-11-07, ACH OUT MERIDIAN MATERIALS CO, PI-2074, debit 7581.22, balance 15227.98

7: 2025-11-10, DEBIT CARD EASTGATE BUSINESS SUPPLY, , debit 131.66, balance 15096.32

8: 2025-11-10, ACH OUT MERIDIAN MATERIALS CO, PI-2079, debit 9786.46, balance 5309.86

9: 2025-11-11, ACH IN SPROCKET MARKETS, SI-1138, , credit 2734.75, balance 8044.61

10: 2025-11-13, CHECK 6601 SPROCKET MARKETS, 6601, , credit 4127.78, balance 12172.39

11: 2025-11-14, DEBIT CARD EASTGATE BUSINESS SUPPLY, , debit 226.48, balance 11945.91

12: 2025-11-14, ACH OUT MERIDIAN MATERIALS CO, PI-2075, debit 1907.62, balance 10038.29

13: 2025-11-17, ACH OUT MERIDIAN MATERIALS CO, PI-2077, debit 3735.69, balance 6302.60

14: 2025-11-18, CHECK 6401 CLEARWATER MERCANTILE, 6401, , credit 7510.88, balance 13813.48

15: 2025-11-19, ACH IN CLEARWATER MERCANTILE, SI-1137, , credit 1547.57, balance 15361.05

16: 2025-11-19, ACH IN LINDQVIST FAMILY STORES, SI-1142, , credit 4234.79, balance 19595.84

17: 2025-11-20, DEBIT CARD EASTGATE BUSINESS SUPPLY, , debit 471.22, balance 19124.62

18: 2025-11-24, CHECK 1062 MERIDIAN MATERIALS CO, 1062, debit 9142.46, balance 9982.16

19: 2025-11-25, DEBIT CARD EASTGATE BUSINESS SUPPLY, , debit 204.91, balance 9777.25

20: 2025-11-26, ACH IN CLEARWATER MERCANTILE, SI-1147, , credit 1482.04, balance 11259.29

21: 2025-11-26, ACH IN SPROCKET MARKETS, SI-1148, , credit 3795.20, balance 15054.49

22: 2025-11-27, ACH IN LINDQVIST FAMILY STORES, SI-1144, , credit 1097.12, balance 16151.61

23: 2025-11-28, ACH IN SPROCKET MARKETS, SI-1139, , credit 1651.12, balance 17802.73

24: 2025-11-28, CHECK 6402 CLEARWATER MERCANTILE, 6402, , credit 1938.07, balance 19740.80

25: 2025-11-28, ACH IN CLEARWATER MERCANTILE, SI-1143, , credit 2878.26, balance 22619.06

26: 2025-11-28, ACH IN SPROCKET MARKETS, SI-1146, , credit 535.40, balance 23154.46

27: 2025-11-30, ACCOUNT MAINTENANCE CHARGE, , debit 25.60, balance 23128.86

28: 2025-11-30, CHECK 5400 LINDQVIST FAMILY STORES, 5400, , credit 2280.27, balance 25409.13

29: 2025-11-30, ACH IN LINDQVIST FAMILY STORES, SI-1144, , credit 295.38, balance 25704.51

30: 2025-11-30, CHECK 6403 CLEARWATER MERCANTILE, 6403, , credit 988.02, balance 26692.53

Now compare ledger entries to bank statement.

We need to identify:

- Missing entries: ledger has entries not in bank statement (or vice versa)
- Wrong amount: same counterparty and date but amount differs
- Duplicate entries: ledger has two entries for same bank line (we saw duplicate Lindqvist payment on 2025-11-17)
- Timing differences: outstanding cheques (issued but not cleared) or deposits in transit (recorded but not yet on statement). According to policy, these are not errors.

We need to consider dates: ledger date is transaction date (check issue date). Bank statement date is when bank processed it. Policy says ledger date never later than statement date for same item. So if ledger date earlier than bank date, could be timing difference (outstanding cheque/deposit in transit). If ledger date equals bank date, it's likely same transaction.

We need to match each ledger bank movement to a bank statement row.

Let's list ledger bank movements (inflows/outflows) with date, amount, counterparty, and whether it's debit (outflow) or credit (inflow) per ledger sign (Assets:Bank:Checking negative = outflow, positive = inflow).

I'll create a table.

From ledger:

1. 2025-11-03 outflow 2808.82 to Meridian Materials Co (PI-2076 paid) (debit)
2. 2025-11-03 outflow 4000.00 to Nakamura Property Holdings (rent check 1061)
3. 2025-11-05 outflow 852.57 to Eastgate Business Supply (debit card)
4. 2025-11-07 outflow 7581.22 to Meridian Materials Co (PI-2074 paid)
5. 2025-11-10 outflow 131.66 to Eastgate Business Supply (debit card)
6. 2025-11-10 outflow 9786.46 to Meridian Materials Co (PI-2079 paid)
7. 2025-11-10 inflow 2734.75 from Sprocket Markets (customer payment SI-1138)
8. 2025-11-10 outflow 226.48 to Eastgate Business Supply (shipping labels)
9. 2025-11-12 inflow 4127.78 from Sprocket Markets (payment on account SI-1139, check 6601)
10. 2025-11-13 outflow 1907.62 to Meridian Materials Co (PI-2075 paid)
11. 2025-11-13 outflow 3735.69 to Meridian Materials Co (PI-2077 paid)
12. 2025-11-17 inflow 1547.57 from Clearwater Mercantile (customer payment SI-1137)
13. 2025-11-17 inflow 4234.79 from Lindqvist Family Stores (payment on account SI-1142) [first]
14. 2025-11-17 inflow 4234.79 from Lindqvist Family Stores (payment on account SI-1142) [duplicate]
15. 2025-11-18 inflow 7510.88 from Clearwater Mercantile (payment on account SI-1141, check 6401)
16. 2025-11-20 outflow 471.22 to Eastgate Business Supply (debit card)
17. 2025-11-24 inflow 3795.20 from Sprocket Markets (payment on account SI-1148)
18. 2025-11-26 inflow 1097.12 from Lindqvist Family Stores (payment on account SI-1144)
19. 2025-11-26 inflow 535.40 from Sprocket Markets (payment on account SI-1146)
20. 2025-11-26 inflow 1482.04 from Clearwater Mercantile (payment on account SI-1147)
21. 2025-11-28 outflow 4000.00 to Nakamura Property Holdings (prepaid rent check 1063)
22. 2025-11-28 inflow 1651.12 from Sprocket Markets (payment on account SI-1139)
23. 2025-11-28 inflow 1938.07 from Clearwater Mercantile (customer payment SI-1140, check 6402)
24. 2025-11-28 inflow 2878.26 from Clearwater Mercantile (customer payment SI-1143)
25. 2025-11-28 inflow 535.40 from Sprocket Markets (payment on account SI-1146) Wait we already had that on 26th? Actually line 26 is same as 20? Let's check: ledger line 226? Actually we have line 226? Let's re-check: after line 224-226 we have line 228-230 etc. The inflow 535.40 from Sprocket Markets appears twice? Let's verify.

From ledger:

- Line 200-202: 2025-11-26 * "Sprocket Markets" "Payment on account against SI-1146" (inflow 535.40)
- Line 226? Actually line 226 is not present. Let's scroll: after line 224-226 (Clearwater Mercantile payment SI-1143) we have line 228-230 (Lindqvist payment SI-1144) then line 232-234 (Clearwater Mercantile payment SI-1147) then line 236-238 (bank fee). There's no second 535.40. Wait I misread: earlier we had line 200-202 for 535.40, and line 226? Actually there is also line 226? Let's check original ledger lines near 225:

I'll re-extract from ledger after line 210:

208  2025-11-28 * "Nakamura Property Holdings" "December rent prepaid, check 1063"
209     Assets:Prepayments                        4000.00 USD
210     Assets:Bank:Checking                     -4000.00 USD

211  
212  2025-11-28 * "Sprocket Markets" "Payment on account against SI-1139"
213    Assets:Bank:Checking                      1651.12 USD
214    Assets:AR                                -1651.12 USD

215  
216  2025-11-28 * "Clearwater Mercantile" "Customer payment for SI-1140, check 6402"
217    Assets:Bank:Checking                      1938.07 USD
218    Assets:AR                                -1938.07 USD

219  
220  2025-11-28 * "Clearwater Mercantile" "Customer payment for SI-1143"
221    Assets:Bank:Checking                      2878.26 USD
222    Assets:AR                                -2878.26 USD

223  
224  2025-11-28 * "Sprocket Markets" "Payment on account against SI-1146"
225    Assets:Bank:Checking                       535.40 USD
226    Assets:AR                                 -535.40 USD

227  
228  2025-11-28 * "Lindqvist Family Stores" "Payment on account against SI-1142, check 5400"
229    Assets:Bank:Checking                      2280.27 USD
230    Assets:AR                                -2280.27 USD

231  
232  2025-11-28 * "Clearwater Mercantile" "Customer payment for SI-1143"
... Wait we already had that. Actually line 220-222 was Clearwater Mercantile SI-1143. Then line 224-226 is Sprocket Markets SI-1146. Then line 228-230 Lindqvist SI-1142. Then line 232-234 Clearwater Mercantile SI-1147? Let's continue:

232  2025-11-28 * "Clearwater Mercantile" "Customer payment for SI-1147"
233    Assets:Bank:Checking                       988.02 USD
234    Assets:AR                                 -988.02 USD

235  
236  2025-11-30 * "Merchants Row National Bank" "Account maintenance charge"
237    Expenses:BankFees                           26.50 USD
238    Assets:Bank:Checking                       -26.50 USD

Thus we have:

- Inflow 535.40 from Sprocket Markets on 2025-11-26 (line 200-202)
- Inflow 535.40 from Sprocket Markets on 2025-11-28 (line 224-226) Actually that's a second inflow of same amount on 28th.

So there are two inflows of 535.40 from Sprocket Markets: one on 26th, one on 28th.

Check bank statement: we have an ACH IN SPROCKET MARKETS, SI-1146 on 2025-11-26 credit 3795.20 (that's line 21). Wait that's 3795.20, not 535.40. Actually we have:

Bank statement line 21: 2025-11-26, ACH IN SPROCKET MARKETS, SI-1148, , credit 3795.20

Line 22: 2025-11-26, ACH IN CLEARWATER MERCANTILE, SI-1147, , credit 1482.04

Line 23: 2025-11-27, ACH IN LINDQVIST FAMILY STORES, SI-1144, , credit 1097.12

Line 24: 2025-11-28, ACH IN SPROCKET MARKETS, SI-1139, , credit 1651.12

Line 25: 2025-11-28, ACH IN CLEARWATER MERCANTILE, SI-1143, , credit 2878.26

Line 26: 2025-11-28, ACH IN SPROCKET MARKETS, SI-1146, , credit 535.40

Thus bank statement shows:

- 2025-11-26 credit 3795.20 from Sprocket Markets (SI-1148)
- 2025-11-28 credit 535.40 from Sprocket Markets (SI-1146)

So ledger has:

- 2025-11-26 inflow 535.40 from Sprocket Markets (SI-1146) – but bank shows 3795.20 on that date (SI-1148). So mismatch.
- 2025-11-28 inflow 535.40 from Sprocket Markets (SI-1146) – matches bank statement line 26 (SI-1146) on 28th.

Thus ledger entry on 26th for 535.40 is wrong amount (should be 3795.20) and wrong counterparty? Actually ledger says SI-1146 payment on account, but bank shows SI-1148. So it's a different transaction.

Also ledger has an inflow 3795.20 from Sprocket Markets on 2025-11-24 (line 192-194) which matches bank statement line 18? Wait bank statement line 18 is 2025-11-24 CHECK 1062 MERIDIAN MATERIALS CO debit 9142.46 (that's a debit). Not matching.

Let's check:

### Planted truth (appended after the answer)

- omit — unrecorded_card_payment: 2025-11-25 Eastgate Business Supply (('Assets:Bank:Checking', '-204.91'), ('Expenses:Office', '204.91')) (evidence: 2025-11-25 DEBIT CARD EASTGATE BUSINESS SUPPLY)
- duplicate — duplicated_customer_receipt: 2025-11-17 Lindqvist Family Stores (('Assets:AR', '-4234.79'), ('Assets:Bank:Checking', '4234.79')) (evidence: 2025-11-19 ACH IN LINDQVIST FAMILY STORES)
- alter — transposed_bank_fee: 2025-11-30 Merchants Row National Bank (('Assets:Bank:Checking', '-25.6'), ('Expenses:BankFees', '25.6')) (evidence: 2025-11-30 ACCOUNT MAINTENANCE CHARGE)
- omit — unrecorded_supplier_payment: 2025-11-24 Meridian Materials Co (('Assets:Bank:Checking', '-9142.46'), ('Liabilities:AP', '9142.46')) (evidence: 2025-11-24 CHECK 1062 MERIDIAN MATERIALS CO)
- outstanding: outstanding_check_1063 2025-11-28 -4000.00

---

## eval:11 → task-f93a89fceabf335d06e060ce

**Part A – Reconciliation discrepancies**

| Date       | Amount (USD) | Counterparty                | Account to post (debit / credit)                                 | Reason / citation                                                                 |
|------------|--------------|-----------------------------|-------------------------------------------------------------------|---------------------------------------------------------------------------------|
| 2025‑11‑04 | 386.52       | Gearworks Office Works      | Expenses:Office (debit) / Assets:Bank:Checking (credit)            | Missing debit‑card purchase; vendor default_account = Expenses:Office (vendors.csv); policy: expenses recorded to appropriate expense account. |
| 2025‑11‑30 | 75.43        | Merchants Row National Bank | Remove one duplicate: Expenses:BankFees (debit) / Assets:Bank:Checking (credit) | Bank statement shows only one service charge; policy: bank service charges recorded to Expenses:BankFees on date bank applies them. Duplicate violates policy. |
| 2025‑11‑28 | 4 000.00     | Millbrook Property Group    | **Outstanding check** – no posting (already recorded as credit to Assets:Bank:Checking) | Check 1234 not yet cleared; policy: outstanding checks are timing differences, listed as outstanding item, never removed or adjusted. |

*No deposits in transit were identified; all ledger receipts appear on the statement within the normal clearing window.*

---

**Part B – Realism assessment**

The November activity looks like that of a small trading company: regular rent and office‑supply payments, a steady stream of customer sales with proper sales‑tax splitting, and routine ACH/check settlements with vendors. The narrations match the reference numbers (SI‑xxxx, PI‑xxxx) and the fee wording (“Business account service charge”) is typical. The only implausible element is the duplicate bank‑fee line, which is a plausible data‑entry slip but unlikely to occur twice on the same day for the same amount. Overall the month feels realistic.

- **Realism:** 4 / 5 (minor issue with the duplicate fee entry).  
- **Difficulty:** 3 / 5 (requires spotting a missing expense line, a duplicate fee, and recognizing an outstanding check as a timing difference).

### Planted truth (appended after the answer)

- duplicate — duplicated_bank_fee: 2025-11-30 Merchants Row National Bank (('Assets:Bank:Checking', '-75.43'), ('Expenses:BankFees', '75.43')) (evidence: 2025-11-30 BUSINESS ACCOUNT SERVICE CHARGE)
- omit — unrecorded_card_payment: 2025-11-04 Gearworks Office Works (('Assets:Bank:Checking', '-386.52'), ('Expenses:Office', '386.52')) (evidence: 2025-11-04 DEBIT CARD GEARWORKS OFFICE WORKS)
- outstanding: outstanding_check_1234 2025-11-28 -4000.00
