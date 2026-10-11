# Creating an account.tax in tests on a bare DB needs country_id AND tax_group_id (Odoo 19)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🟢 Low                                     |
| Last Verified | 2026-08-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `testing`, `account.tax`, `tax_group_id`, `country_id`, `not-null`, `localization`

---

## Problem

A test on a fresh `--without-demo` DB (no localization/chart installed) does
`env['account.tax'].create({'name': ..., 'amount': 14, 'type_tax_use': 'sale'})`
and dies with a raw SQL `NotNullViolation` — first on `country_id`, and after
fixing that, on `tax_group_id`.

## Root Cause

In Odoo 19 both columns are NOT NULL. Their defaults come from the company's
fiscal country and the installed chart's tax groups — a bare test company has
neither, and `create()` reaches INSERT with NULLs (no friendly ValidationError).

## Solution ✅

```python
country = self.env.ref('base.eg')
self.env.company.country_id = country
tax_group = self.env['account.tax.group'].create({
    'name': 'Test Taxes', 'country_id': country.id,
})
tax = self.env['account.tax'].create({
    'name': 'Test VAT 14', 'amount': 14.0, 'type_tax_use': 'sale',
    'country_id': country.id, 'tax_group_id': tax_group.id,
})
```

## ⚠️ Pitfalls

- Fixing only `country_id` still crashes on `tax_group_id` — set BOTH.
- The `account.tax.group` itself needs a matching `country_id`.
- Not an issue on DBs with a fiscal localization installed (defaults resolve).

## Verification

`solargy_sale_lines` `test_taxes_switch`: green on a fresh `-i` DB.
