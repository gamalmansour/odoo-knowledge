# Required + Model-Level `readonly=True` Field Never Reaches create() from the Web Client

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-08-01                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `readonly`, `required`, `force_save`, `wizard`, `default_get`, `web-client`

---

## Problem

A wizard field is filled by `default_get` and declared `required=True, readonly=True` on the MODEL (typical for a context anchor like `picking_id`). Everything works in `odoo shell` and in tests, but saving from the WEB CLIENT dies with:

```
Missing required value for the field 'Transfer' (picking_id).
```

## Root Cause

The web client **omits readonly fields from the save payload**. The value is displayed in the form (default_get filled it), but `create()` receives a dict WITHOUT it → the required constraint fires. Server-side paths (`shell`, tests calling `.create({})`) go through `default_get` directly, so they pass — which is exactly why the test suite stays green while the UI is broken.

## Solution ✅

Keep the field writable at the MODEL level and enforce readonly in the VIEW with `force_save`, which tells the client to include the readonly value in the payload:

```python
picking_id = fields.Many2one('stock.picking', string='Transfer', required=True)  # no readonly
```

```xml
<field name="picking_id" readonly="1" force_save="1"/>
```

Also make `default_get` set the anchor unconditionally (not only inside another branch):

```python
picking_id = values.get('picking_id') or self.env.context.get('active_id')
if picking_id and 'picking_id' in fields_list:
    values['picking_id'] = picking_id
```

## ⚠️ Pitfalls

- **Green tests prove nothing here** — `.create({})` merges `default_get` server-side; only the browser reproduces the missing-payload behavior. Any required-and-readonly combo deserves one manual UI save.
- `force_save` without removing the model-level `readonly` is not enough in some versions — the ORM may ignore client writes to model-readonly fields. Move the readonly to the view.

## Verification

Reproduced on `stock.warehouse.split.wizard` (Odoo 19): UI save crashed while 6/6 tests were green; after moving readonly to the view with `force_save` + unconditional default, the UI flow works and tests stay green.

## References

- Related file: [stock_picking_warehouse_split/wizard/warehouse_split_wizard.py](file:///Users/gamal/odoo/odoo19.0/custom/stock_picking_warehouse_split/wizard/warehouse_split_wizard.py)
