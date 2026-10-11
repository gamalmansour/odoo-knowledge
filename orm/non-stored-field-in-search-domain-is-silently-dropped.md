# A Non-Stored Field in a Search Domain Is SILENTLY DROPPED, Not an Error

| Field         | Value                    |
|---------------|--------------------------|
| Category      | orm                      |
| Odoo Versions | All                      |
| Severity      | 🔴 Critical              |
| Last Verified | 2026-08-12               |
| Author        | Gamal Mansour            |

**Tags:** `orm`, `search`, `domain`, `non-stored`, `compute`, `silent-failure`, `expression`, `status_in_payment`, `payment_state`, `credit-limit`

---

## Problem

A domain leaf on a computed field that is **not stored** and has **no `search`
method** does not raise. Odoo logs an error and **removes the leaf**, then runs
the rest of the query as if you had never written it.

```python
invoices = self.env['account.move'].search([
    ('partner_id', '=', partner.id),
    ('state', '=', 'posted'),
    ('status_in_payment', 'in', ['not_paid', 'partial']),   # <- vanishes
    ('move_type', '=', 'out_invoice'),
])
```

`account.move.status_in_payment` is non-stored with no search implementation.
The search returns **every posted customer invoice of that partner — paid ones
included**.

The failure is invisible from the outside: no exception, no wrong-looking data,
correct-looking code. It only shows up as behaviour that is *too broad*, months
or years later, blamed on anything but the domain.

## Root Cause

```python
# odoo/osv/expression.py  (~line 1179)
elif not field.store:
    if not field.search:
        _logger.error("Non-stored field %s cannot be searched.", field, exc_info=True)
        # Ignore it: generate a dummy leaf.
        domain = []
```

The design assumption is that dropping one condition is better than failing the
whole request. For a *filter that protects something*, that assumption is
backwards: dropping the filter opens the gate.

The log line exists, but it is one ERROR among thousands in a busy server log,
and nothing in the UI reflects it.

## Solution ✅

**Prove the leaf does anything at all.** Two counts, one difference:

```python
with_leaf    = Model.search_count(domain_with_the_leaf)
without_leaf = Model.search_count(domain_without_it)
assert with_leaf != without_leaf, "the leaf is being dropped"
```

Identical numbers mean the condition is not being applied. On the case below:
2,793 vs 2,793.

**Swap for the stored equivalent.** Most non-stored "status" fields have a stored
sibling carrying the same values:

| Non-stored (drops silently) | Stored replacement |
|---|---|
| `account.move.status_in_payment` | **`payment_state`** — same selection values |
| — | or `('amount_residual', '>', 0)` |

```python
('payment_state', 'in', ['not_paid', 'partial']),   # stored, actually filters
```

**Audit the whole codebase for the pattern**, because one occurrence usually
means the author did not know:

```bash
grep -rn "search(\[" --include="*.py" . | grep -v __pycache__
# then, for each field used in a domain:
#   field.store is False and field.search is None  ->  it is being dropped
```

A quick programmatic check in `odoo shell`:

```python
f = env['account.move']._fields['status_in_payment']
print(f.store, f.search)      # False None  -> dropped
```

## ⚠️ Pitfalls

- **This bites hardest in guard clauses.** Overdue checks, approval gates,
  duplicate detection, quota limits — anywhere the domain exists to *restrict*.
  A dropped leaf in a report shows too many rows and someone notices; a dropped
  leaf in a gate changes who is allowed to do what and nobody does.
- **The error appears in the log on every call**, so it drowns. Grep production
  logs for `cannot be searched` before assuming your code is the first case.
- **Verify per company.** When measuring the impact, aggregate *within* the
  company the transaction belongs to. A first pass that summed across companies
  reported a false regression: a partner's worst delay was 157 days in company A
  but only 48 in company B, and the order — correctly — was judged against
  company B's invoices via the multi-company record rule.
- **Fixing the leaf tightens a gate that had been wide open.** Count who is newly
  affected before deploying, and tell the client. Here the fix left 45 customers
  legitimately blocked and released 53 who should never have been.

## Real-world impact

Odoo 18 Enterprise, live pharmaceutical distributor, defect present for an
unknown period:

| Measure | Value |
|---|---|
| Invoices returned with the leaf / without it | 2,793 / 2,793 — **identical** |
| Fully paid invoices wrongly treated as overdue | **1,401** |
| Customers blocked while owing **nothing** | **16** |
| Customers blocked in total, before / after the fix | 98 / 45 |
| Users unaffected because they held the bypass group | 3 of 8 — which is why nobody reported it |

Reproduced end to end on a restored copy: a customer with 42 invoices,
85,137 SAR billed and **0.00 outstanding** could not confirm a new order —
`Cannot confirm the order! Partner has overdue invoice (INV/…) by 128 days` —
where that invoice was `payment_state = paid`, `amount_residual = 0.00`.

## Verification

After swapping to `payment_state`:

- filtered vs unfiltered counts now differ (1,392 vs 2,793) — the leaf applies
- the paid-up customer confirms
- three real debtors (357k / 165k / 126k SAR, 121–158 days late) still blocked,
  each with the correct message
- 0 customers blocked while owing nothing
