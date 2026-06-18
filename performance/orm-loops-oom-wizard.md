# OOM and Performance Bottlenecks with Massive ORM Loops in Wizards

**Category:** Performance
**Tags:** #orm #performance #oom #sql #wizard
**Odoo Versions:** 15.0, 16.0, 17.0, 18.0
**Last Verified:** 2026-06-18

## ❌ The Problem / Pitfall
When building wizards or processes that iterate over a large dataset (e.g., thousands of journal entries), developers often use ORM methods directly inside a loop, like this:

```python
entries = self.env['account.move'].search(domain)
# Pitfall 1: Loading all records into memory to sum values
total = sum(abs(e.amount_total) for e in entries)

# Pitfall 2: Massive batch updates using write() causing DB locks
entries.write({'is_sampled_audit': False})

# Pitfall 3: Nested loops fetching relational data
for entry in entries:
    for line in entry.line_ids:
        # Causes an N+1 query problem or massive prefetch bloat
        total += abs(line.balance)
```

**Consequences:**
1. **Out of Memory (OOM):** Fetching `line_ids` for 100k+ records will consume gigabytes of RAM.
2. **Transaction Locks / Timeouts:** Writing to thousands of records at once via `.write()` triggers all related field recomputations and blocks the table.

## ✅ The Solution
Bypass the ORM for read-heavy aggregations and massive batch updates using `Raw SQL` or optimized `read_group`.

### 1. Fast Aggregation
```python
# Using Raw SQL
self.env.cr.execute("""
    SELECT COUNT(id), SUM(ABS(amount_total))
    FROM account_move
    WHERE state = 'posted' AND company_id = %s
""", [company_id])
count, total_val = self.env.cr.fetchone()
```

### 2. Fast Chunked Updates
```python
# Updating records without triggering ORM cascade
chunk_size = 5000
for i in range(0, len(all_ids), chunk_size):
    chunk = all_ids[i:i + chunk_size]
    self.env.cr.execute(
        "UPDATE account_move SET is_sampled_audit = False WHERE id IN %s", 
        [tuple(chunk)]
    )
```

### 3. Fast Relational Aggregation (Impact Reports)
```python
# Instead of looping through entry.line_ids
self.env.cr.execute("""
    SELECT account_id, SUM(ABS(balance))
    FROM account_move_line
    WHERE move_id IN %s
    GROUP BY account_id
""", [tuple(chunk)])
for acct_id, amount in self.env.cr.fetchall():
    totals[acct_id] += amount
```

## ⚠️ Additional Warning
If a field is only logically tied to the model's existing company (e.g., an `account.move` already belongs to one company), **DO NOT** make it `company_dependent=True`. This forces Odoo to store the value in `ir.property` instead of the model's actual table, degrading query performance significantly!
