# Test Environment ORM Compute Quirks for Date Fields

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                   |
| Last Verified | 2026-06-15                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `testing`, `orm`, `compute_fields`, `dates`, `fast_forward`

---

## Problem

> When trying to test cron methods or date-based computations in Odoo `TransactionCase` tests, directly modifying the date values (e.g. `record.issue_date = new_date`) and manually calling compute methods may not trigger dependent compute methods correctly, leading to test assertions failing due to stale object state.

```python
# Example of failing test logic
cert.issue_date = fields.Date.today() - timedelta(days=365)
cert._compute_expiry()
cert._compute_state()

self.assertEqual(cert.state, 'expired') # Fails: 'valid' != 'expired'
```

## Root Cause

> Manually setting Python object attributes bypasses the ORM's automatic tracking of dependencies for compute methods. Even manually invoking `_compute_x()` might not fully update all dependent fields (`_compute_state` which depends on `expiry_date`) if the environment hasn't recognized the chain of writes or flushed properly, especially with stored compute fields.

## Solution ✅

> Use the ORM's `.write()` method to trigger the whole chain of computations natively instead of manually overriding attributes and calling compute functions.

```python
# Step 1: Use write() to update the dependency field
# Odoo's ORM will automatically handle the @api.depends chain
cert.write({'issue_date': fields.Date.today() - timedelta(days=365)})

# Step 2: The dependent compute fields (expiry_date, state) will auto-compute.
self.assertEqual(cert.state, 'expired')
```

## ⚠️ Pitfalls

- **Manual Computation Chain:** Calling `record._compute_field()` manually in tests is an anti-pattern. If dependencies are properly defined using `@api.depends`, a `write()` to the dependency field will trigger all downstream computations natively.
- **Flushing:** In older Odoo versions (14/15) you might have needed `env.flush_all()` or `invalidate_recordset()`, but from Odoo 16+ `write()` triggers computes within the transaction synchronously before the next read in tests.
