# OpenEduCat Batch Name and Code String Length Truncation in Automated Sales Provisioning

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-17                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `openeducat`, `op.batch`, `sale_order`, `varchar_size`, `unique_code`

---

## Problem

When automatically provisioning training batches (`op.batch`) from sales orders (`sale.order`) upon confirmation, long course titles (e.g., "OSHA 30-Hour General Industry Training") or hierarchical batch codes (e.g., `BATCH/OSHA-30-GI/S00056/1`) either truncate silently or trigger a PostgreSQL exception:

```text
psycopg2.errors.StringDataRightTruncation: value too long for type character varying(16)
or
AssertionError: 'OSHA 30-Hour General Industry Tr' != 'OSHA 30-Hour General Industry Training'
```

Additionally, `op.attendance.register` fields `name` and `code` default to `size=16`, crashing automatic attendance register creation when verbose batch names are used.

## Root Cause

In `openeducat_core/models/batch.py`:
- `code = fields.Char('Code', size=16, required=True)`
- `name = fields.Char('Name', size=32, required=True)`
- Constraint: `unique(code)`

In `openeducat_attendance/models/attendance_register.py`:
- `name = fields.Char('Name', size=16, required=True)`
- `code = fields.Char('Code', size=16, required=True)`

When integrating with corporate sales contracts, batch names derived from full professional course titles exceed 32 characters, and unique batch codes formatted with order reference and line ID exceed 16 characters.

## Solution ✅

1. In custom extension module (`openeducat_ghtc`), re-declare widened fields on `op.batch`:

```python
class OpBatch(models.Model):
    _name = 'op.batch'
    _inherit = ['op.batch', 'mail.activity.mixin']

    name = fields.Char('Name', size=128, required=True)
    code = fields.Char('Code', size=64, required=True)

    def init(self):
        super().init()
        try:
            self.env.cr.execute("ALTER TABLE op_batch ALTER COLUMN name TYPE varchar(128);")
            self.env.cr.execute("ALTER TABLE op_batch ALTER COLUMN code TYPE varchar(64);")
        except Exception:
            pass
```

2. When auto-creating `op.attendance.register`, constrain identifiers to 16 characters:

```python
short_name = (batch.name or "ATT-REG")[:16]
short_code = (batch.code or f"ATT{batch.id}")[:16]
register = self.env['op.attendance.register'].create({
    'name': short_name,
    'code': short_code,
    'course_id': batch.course_id.id,
    'batch_id': batch.id,
})
```

3. Guard quotation confirmation with an idempotency check (`if not line.batch_id:`) to prevent duplicate batch creation if quotations are unlocked or re-confirmed.

## ⚠️ Pitfalls

- **Core Module Updates:** If `openeducat_core` is updated, the base definition `size=16` or `size=32` might attempt to shrink the columns unless overridden in your downstream module. Overriding in `init()` guarantees column width in PostgreSQL.
- **Attendance Register Limits:** Never pass string expressions like `f"{batch.name} Attendance Register"` directly to `op.attendance.register` without slicing or widening the column.

## Verification

```bash
/Users/gamal/odoo/odoo17.0/.venv/bin/python3 /Users/gamal/odoo/odoo17.0/odoo-bin \
  -c /Users/gamal/odoo/odoo17.0/openedu17.conf \
  -d openedu17_community \
  -u openeducat_ghtc \
  --test-enable \
  --test-tags /openeducat_ghtc \
  --stop-after-init
```
