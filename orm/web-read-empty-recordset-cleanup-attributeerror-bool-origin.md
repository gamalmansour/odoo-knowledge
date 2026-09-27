# web_read() Override Returning Dummy Row with id=False Crashes UI with AttributeError: 'bool' object has no attribute 'origin'

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-09-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `web_read`, `cleanup`, `many2one`, `empty-recordset`, `AttributeError`, `origin`, `crm.lead`, `access-rules`

---

## Problem

When opening, reloading, or saving a form or list view containing a `Many2one` field whose value is empty (`False`), the Odoo web client crashes with an unhandled RPC server error modal:

```python
RPC_ERROR
Odoo Server Error
Occured on localhost:2525 on model commission.ambassador on 2026-09-27 14:15:58 GMT

Traceback (most recent call last):
  File "/Users/gamal/odoo/odoo18.0/odoo/http.py", line 2166, in _transactioning
    return service_model.retrying(func, env=self.env)
  File "/Users/gamal/odoo/odoo18.0/odoo/service/model.py", line 156, in retrying
    result = func()
  File "/Users/gamal/odoo/odoo18.0/odoo/http.py", line 2133, in _serve_ir_http
    response = self.dispatcher.dispatch(rule.endpoint, args)
  File "/Users/gamal/odoo/odoo18.0/odoo/http.py", line 2381, in dispatch
    result = self.request.registry['ir.http']._dispatch(endpoint)
  File "/Users/gamal/odoo/odoo18.0/addons/base/models/ir_http.py", line 333, in _dispatch
    result = endpoint(**request.params)
  File "/Users/gamal/odoo/odoo18.0/odoo/http.py", line 1928, in kargs_full_wrapper
    return call_kw(*(params[a] for a in args), **kwargs)
  File "/Users/gamal/odoo/odoo18.0/odoo/api.py", line 512, in call_kw
    result = getattr(self, method)(*args, **kwargs)
  File "/Users/gamal/odoo/odoo18.0/addons/web/models/models.py", line 165, in web_read
    for vals in co_records.web_read(field_spec['fields'])
  File "/Users/gamal/odoo/odoo18.0/addons/web/models/models.py", line 117, in <dictcomp>
    vals['id']: cleanup(vals)
  File "/Users/gamal/odoo/odoo18.0/addons/web/models/models.py", line 94, in cleanup
    vals['id'] = vals['id'].origin or False
AttributeError: 'bool' object has no attribute 'origin'
```

---

## Root Cause

In Odoo 17 and 18, `addons/web/models/models.py` processes relational subfields in `web_read()`:

```python
co_records = self[field_name]
many2one_data = {
    vals['id']: cleanup(vals)
    for vals in co_records.web_read(extra_fields)
}
```

Where `cleanup(vals)` assumes `vals['id']` is either a valid integer ID (`int`) or an in-memory `NewId`:

```python
def cleanup(vals: dict) -> dict:
    """ Fixup vals['id'] of a new record. """
    if not vals['id']:
        vals['id'] = vals['id'].origin or False
    return vals
```

When a custom module overrides `web_read` (such as a silencer or rule wrapper on `crm.lead`) and incorrectly returns a dummy record containing `{'id': False, ...}` when `not self`:

```python
# ❌ ANTI-PATTERN: Returning a list with a dummy record on empty recordset
if not self:
    return [self._silencer_build_web_vals(specification, rec=None, default_vals=default_vals)]
```

If an outer record has `field_name = False` (e.g., `lead_id = False` on `commission.lines`), `co_records = self['lead_id']` evaluates to `env['crm.lead'].browse()` (an empty recordset, `len == 0`).
Instead of returning `[]`, the buggy override returns `[{'id': False, ...}]`.
`cleanup(vals)` then evaluates:
```python
if not vals['id']:
    vals['id'] = vals['id'].origin or False  # False has no attribute 'origin'!
```
Because boolean `False` has no attribute `.origin`, python raises `AttributeError: 'bool' object has no attribute 'origin'`.

---

## Solution ✅

### 1. In the `web_read()` Override:
Always return `[]` when `self` is an empty recordset (`if not self:`). Never return a dummy dictionary when there are no records.

Furthermore, if the model filters records by access rights, separate accessible from inaccessible records and ensure any dummy row generated for inaccessible records retains its real integer `rec.id`:

```python
class CrmLeadSilencer(models.Model):
    _inherit = 'crm.lead'

    def web_read(self, specification):
        specification = specification or {}

        # --------------------------------------------------------------
        # 1. Empty recordset contract: MUST return []
        # --------------------------------------------------------------
        if not self:
            return []

        # --------------------------------------------------------------
        # 2. Avoid invalid ids during in-memory create/onchange
        # --------------------------------------------------------------
        real_ids = self._silencer_real_ids()
        if not real_ids:
            return super().web_read(specification)

        # --------------------------------------------------------------
        # 3. Filter accessible vs inaccessible records
        # --------------------------------------------------------------
        try:
            accessible_ids = set(self.with_context(active_test=False)._search([
                ('id', 'in', real_ids)
            ]))
        except Exception:
            try:
                return super().web_read(specification)
            except Exception:
                return [
                    self._silencer_build_web_vals(specification, rec=rec, default_vals={})
                    for rec in self
                ]

        accessible = self.browse([i for i in self.ids if i in accessible_ids])
        inaccessible = self - accessible

        results = []
        if accessible:
            try:
                results.extend(super(CrmLeadSilencer, accessible).web_read(specification))
            except (AccessError, MissingError):
                results.extend([
                    self._silencer_build_web_vals(specification, rec=rec, default_vals={})
                    for rec in accessible
                ])

        if inaccessible:
            # For records the user cannot access: return safe silent dicts
            # with their real ID so Many2one mappings do not crash with KeyError
            results.extend([
                self._silencer_build_web_vals(specification, rec=rec, default_vals={})
                for rec in inaccessible
            ])

        return results
```

---

## ⚠️ Pitfalls

1. **ORM Contract Violation:** In Odoo ORM, `len(model.web_read(...))` must always be `<= len(model)`. An empty recordset (`not self`) must NEVER yield a non-empty list.
2. **KeyError in Many2one dictionary comprehensions:** If `co_records.web_read()` simply drops inaccessible records, the outer model's `many2one_data[values[field_name]]` raises `KeyError`. Inaccessible records in a batch must either be read via `sudo()` or returned with a safe fallback dict preserving `vals['id'] = rec.id`.
3. **Missing View Columns:** When embedding a One2many lines table, verify that all key relationship fields (e.g. `ambassador`, `Date`) are included in both `<list>` and `<form>` views so records are not visually perceived as blank or missing.

---

## Verification

Run python CLI or unit tests reading an empty recordset and checking `web_read()`:

```python
empty_lead = env['crm.lead'].browse()
assert empty_lead.web_read({'display_name': {}}) == []
```

Verify that Many2one fields on child lines with `False` values read cleanly without error:

```python
line = env['commission.lines'].create({'lead_id': False})
res = line.web_read({'lead_id': {'fields': {'display_name': {}}}})
assert res[0]['lead_id'] is False
```

---

## References

- Related: `orm/one2many-empty-when-create-omits-inverse-field.md`
- Odoo Core: `addons/web/models/models.py` (`web_read` and `cleanup`)
