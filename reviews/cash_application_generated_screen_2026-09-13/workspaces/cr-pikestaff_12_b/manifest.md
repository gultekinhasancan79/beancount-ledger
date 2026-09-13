# File index

| File | Contents |
|---|---|
| `ledger.beancount` | Beancount ledger. Chart of accounts, opening balances at 2027-10-01, and posted October 2027 entries. |
| `bank_statement.csv` | Beacon Row Savings Bank checking account statement. Period 2027-10-01 to 2027-10-31. 7 rows. Columns: date, description, reference, debit, credit, balance. |
| `accounts.csv` | Chart of accounts. 11 rows. Columns: account, type, description. |
| `customers.csv` | Customer master. 3 rows. Columns: customer, terms, default_account. |
| `vendors.csv` | Vendor master. 1 rows. Columns: vendor, terms, default_account. |
| `policy.md` | Bookkeeping policy notes. |
| `archive_prior_period.csv` | Checking account statement. Period 2027-09-01 to 2027-09-30. 3 rows. Same columns as `bank_statement.csv`. |
| `open_items.csv` | Open sales-invoice register at 2027-10-01. 8 rows. Columns: invoice_id, customer, invoice_date, due_date, original_amount, open_balance. |
| `remittance_advice.csv` | Customer remittance advices, one row per advice line. 6 rows. Columns: remittance_id, customer, remittance_date, payment_method, payment_reference, payment_amount, invoice_id, amount_paid, settles_invoice, deduction_amount, note. |
| `credit_notes.csv` | Credit notes issued in the period. 1 row. Columns: credit_note_id, date, customer, invoice_id, net_amount, tax_amount, gross_amount, reason. |
