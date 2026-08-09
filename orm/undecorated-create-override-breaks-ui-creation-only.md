# Undecorated `create()` override breaks creation from the UI while server-side create keeps working

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-09                                 |
| Author        | Gamal Mansour                              |

**Tags:** `orm`, `create`, `model_create_multi`, `api-decorator`, `call_kw`, `rpc`, `typeerror`

---

## Problem

> A `create()` override is written **without any `@api` decorator**. Every
> server-side create keeps working (button handlers, crons, `self.env[...]
> .create(...)` from other Python), so the bug stays invisible for months.
> The moment a user tries to create the record **from a form view**, it blows up.

```python
class CommissionTcr(models.Model):
    _name = "commission.tcr"

    def create(self, vals):            # ← no decorator at all
        vals["name"] = self._next_sequence()
        return super().create(vals)
```

```
TypeError: create() missing 1 required positional argument: 'vals'
```

Real case (LXET brokerage, Odoo 18): `commission.tcr.create()` and
`kpis.goal.tracker.create()` were both undecorated. TCRs were only ever created
from a button on `crm.lead`, and goal trackers only from a cron — so the form
"Create" button had never been exercised in staging. Both were dead on arrival
for any user who tried to add a record manually.

## Root Cause

`call_kw` decides how to dispatch an RPC by inspecting the method's `_api`
attribute, which the decorators set (`odoo/api.py`).

- `@api.model_create_multi` → method is **model-style**, receives `vals_list`.
- `@api.model` → method is **model-style**, ORM wraps it via
  `model_create_single` so it receives one `vals` dict at a time.
- **no decorator** → method is treated as **record-style**. `call_kw_multi`
  consumes the first RPC argument (the `[vals]` list the web client sends) as
  the record **ids**, then calls `create()` with no remaining arguments.

So the web client's payload is silently reinterpreted as an id list and the
required `vals` parameter is never passed. Server-side Python calls are
unaffected because they bypass `call_kw` entirely and pass `vals` positionally.

That asymmetry is the whole trap: **the code path that is tested works, the
code path that is not tested is the broken one.**

## Solution ✅

Always decorate. In V15+ the correct form is batch-aware:

```python
from odoo import api, models

class CommissionTcr(models.Model):
    _name = "commission.tcr"

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> "CommissionTcr":
        """Assign the TCR reference before delegating to super."""
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("commission.tcr")
        return super().create(vals_list)
```

Audit an existing codebase in one command:

```bash
# find create() overrides with no @api decorator on the preceding line
grep -rn -B2 "def create(self" --include="*.py" your_addons/ \
  | grep -A2 "def create" | grep -B1 "def create" | grep -v "@api"
```

Then verify the UI path actually works — a unit test that only calls
`Model.create({...})` will **not** catch this. Exercise `call_kw`:

```python
def test_create_from_ui(self):
    """Reproduce the web client's RPC shape, not the Python shape."""
    rec_id = self.env["commission.tcr"].with_user(self.sales_manager).create(
        [{"name": self.partner.id, "unit_price": 1_000_000.0}]
    )
    self.assertTrue(rec_id.exists())
```

## ⚠️ Pitfalls

- **`@api.model` on `create()` is not a fix, it is a downgrade.** It works, but
  Odoo 18 emits a `DeprecationWarning` at import and degrades batch creation to
  one INSERT per record. On an import of 10k units that is a real cost. Use
  `@api.model_create_multi`.
- **Two `create()` definitions on the same class silently shadow.** Python keeps
  the last one defined; the first never runs and no warning is emitted. Seen in
  the same project — a decorated `create()` setting a deadline field was
  overridden 360 lines later by an undecorated one, so the deadline was never
  set and the feature depending on it appeared to "work sometimes". Grep for
  `def create(` per file and expect exactly one hit.
- **Batch-unsafe bodies.** After adding `@api.model_create_multi`, re-read the
  body: any `res.user_id.id` or `self.some_field` on the returned recordset will
  raise a singleton error the first time someone creates two records at once
  (import, `copy()` of multiple records, Data Import).
- Same rule applies to `_name_search` and `default_get` overrides — check the
  decorator whenever an override "works from code but not from the UI".

## Related

- [[onchange-only-computation-breaks-nonform-create]] — the mirror image: works
  from the form, breaks from every other path.
- [[write-override-atomicity-pattern]]
- [[undefined-ir-sequence-silently-names-every-record-new]]
