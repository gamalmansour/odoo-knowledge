# `ir.actions.report.report_action()` Returns Document Layout Wizard Instead of Printing Report

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 15, 16, 17, 18, 19 (All)                   |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `report_action`, `qweb-pdf`, `base.document.layout`, `config=False`, `ir.actions.report`

---

## Problem

> Calling `self.env.ref('my_module.action_report_custom').report_action(self)` from a Python button action on a fresh database (or newly created company) unexpectedly opens the **`base.document.layout`** configuration wizard (`type: 'ir.actions.act_window'`) instead of printing the QWeb PDF report (`type: 'ir.actions.report'`).

```
AssertionError: 'ir.actions.act_window' != 'ir.actions.report'
KeyError: 'report_name'
```

## Root Cause

> In `odoo/addons/web/models/ir_actions_report.py`, `report_action(self, docids, data=None, config=True)` checks whether `self.env.company.external_report_layout_id` is set whenever `config=True` (the default). On a fresh company or unit test database where no invoice document layout was configured yet, Odoo intercepts the call and redirects the user to `base.document.layout` (`ir.actions.act_window`) — even for custom full-bleed reports (certificates, CR80 ID cards, labels) that do not use `web.external_layout` at all.

## Solution ✅

> Pass `config=False` when invoking `report_action()` for custom QWeb reports that supply their own layout (such as certificates, CR80 ID cards, QR posters, or branded executive reports):

```python
def action_print_operator_card(self) -> dict:
    self.ensure_one()
    return self.env.ref(
        'openeducat_ghtc.action_report_ghtc_operator_card'
    ).report_action(self, config=False)
```

## ⚠️ Pitfalls

- **`report_action(self, config=False)` does NOT return `'id'`:** The returned dictionary contains `type`, `report_name`, `report_type`, `report_file`, `name`, `context`, and `data`. Assert on `action['type'] == 'ir.actions.report'` and `action['report_name']` in unit tests rather than `action['id']`.
- **Keep `config=True` only for standard invoice/quotation reports** that rely on `web.external_layout` and genuinely require the company letterhead wizard on first print.

## Verification

```python
action = record.action_print_operator_card()
self.assertEqual(action['type'], 'ir.actions.report')
self.assertEqual(action['report_name'], 'openeducat_ghtc.report_ghtc_operator_card')
```

## References

- `odoo/addons/base/models/ir_actions_report.py` (`def report_action`)
- `odoo/addons/web/models/ir_actions_report.py` (`base.document.layout` intercept)
