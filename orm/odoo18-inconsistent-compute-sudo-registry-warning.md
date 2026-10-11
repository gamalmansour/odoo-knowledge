# Inconsistent 'compute_sudo' on Multi-Field Compute Methods in Odoo 18

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 18, 19                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `compute_sudo`, `registry`, `warning`, `computed-fields`, `odoo18`

---

## Problem

During module loading or server startup in Odoo 18, the ORM surfaces a registry `UserWarning`:

```
UserWarning: model.name: inconsistent 'compute_sudo' for computed fields field_a, field_b, field_c. Either set 'compute_sudo' to the same value on all those fields, or use distinct compute methods for sudoed and non-sudoed fields.
```

---

## Root Cause

In Odoo 18, the model registry checks computed fields that share the same Python compute method (`odoo/modules/registry.py:393`). If one computed field specifies `compute_sudo=True` (or has related/relational fields evaluated in sudo context) while sibling fields computed by the same method do not declare `compute_sudo` (or have it as `False`), the ORM flags this as an inconsistency.

Because the compute method executes once for all attached fields simultaneously on the recordset, executing it in mixed security contexts can lead to partial permissions leaks or unexpected `AccessError`s depending on which field triggers the compute first.

---

## Solution ✅

Ensure all fields calculated by the same compute method share the same `compute_sudo` value:

```python
# BEFORE (Triggers UserWarning in Odoo 18)
count = fields.Integer(compute='_compute_stats', store=True) # compute_sudo is False
lines = fields.Many2many('comodel.name', compute='_compute_stats') # implicit or True

# AFTER (Clean & Consistent)
count = fields.Integer(compute='_compute_stats', compute_sudo=True, store=True)
lines = fields.Many2many('comodel.name', compute='_compute_stats', compute_sudo=True)
```

Alternatively, if some fields must NOT be computed with sudo, split the logic into two separate, dedicated compute methods:
- `_compute_sudo_sensitive_fields()`
- `_compute_public_fields()`

---

## ⚠️ Pitfalls

- **Do Not Ignore Registry Warnings:** In Odoo 18+, registry warnings in CI/CD or strict test runs (`--test-enable`) can escalate or cause subtle cache invalidation anomalies.
- **Relational Many2many in Stored Computes:** If a compute method sets both stored primitives (e.g. `Integer`) and non-stored Many2many relations, always declare explicit relation tables and matching `compute_sudo` to prevent recursive re-computation during the flush cycle.

---

## Verification

Start the Odoo server with `--dev=all` or inspect the startup logs:
```bash
odoo-bin -c odoo.conf -d test_db --stop-after-init
```
Confirm that no `UserWarning: ... inconsistent 'compute_sudo'` appears in the log output.
