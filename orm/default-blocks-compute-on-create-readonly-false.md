# Stored Writable Computed Field (`compute=... store=True readonly=False`) Skips Compute on Create When `default=` Is Set

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19 (All)                   |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-21                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `compute`, `default`, `readonly`, `store`, `create`

---

## Problem

> A stored, writable computed field (`compute='_compute_status', store=True, readonly=False`) also defines a static `default='pending'`. When creating a record WITH child lines (e.g., `result_line_ids=[Command.create(...)]`) that should immediately compute `'non_compliant'`, the field stays stuck on `'pending'` after `create()`.

```text
AssertionError: 'pending' != 'non_compliant'
```

## Root Cause

> During `Model.create(vals_list)`, Odoo injects `default=` values into `vals` **before** scheduling computed fields. Because the field is `readonly=False`, Odoo treats the injected default as an explicit user-supplied override and **skips** running `_compute_*` during `create()`.

## Solution ✅

> Omit `default=` on stored writable computed fields and set the fallback value inside the `@api.depends(...)` compute method itself (including the One2many field itself in `@api.depends` so empty creation also triggers it).

```python
compliance_result = fields.Selection(
    selection=[
        ('pending', 'Pending Analysis'),
        ('compliant', 'Compliant'),
        ('non_compliant', 'Exceeds Thresholds'),
    ],
    compute='_compute_compliance_result',
    store=True,
    readonly=False,
)

@api.depends('result_line_ids', 'result_line_ids.is_exceeded')
def _compute_compliance_result(self):
    for rec in self:
        if not rec.result_line_ids:
            if not rec.compliance_result:
                rec.compliance_result = 'pending'
            continue
        rec.compliance_result = (
            'non_compliant' if any(l.is_exceeded for l in rec.result_line_ids) else 'compliant'
        )
```

## ⚠️ Pitfalls

- Do not rely on `default=` to initialize a `compute=... store=True readonly=False` field; it silently masks the initial computation whenever records are created programmatically with dependent lines in a single `create()` call.
- Always include the One2many field itself (`'result_line_ids'`) alongside `'result_line_ids.flag'` in `@api.depends` so newly created records with zero lines still initialize to `'pending'`.

## Verification

Create a parent record with violating child lines in a single `create()` call and assert the computed field immediately reflects `'non_compliant'`, and create a second record without child lines and assert it initializes to `'pending'`.
