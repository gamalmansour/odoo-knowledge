# POS Cash Payment Method Cannot Be Shared Across Shops in Odoo 19 (Bulk POS Creation Recipe)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `pos`, `pos.payment.method`, `pos.config`, `cash`, `account.journal`, `demo-data`, `bulk-creation`

---

## Problem

When creating many POS shops programmatically (e.g. 22 branches for a demo/rollout) it is tempting
to create ONE cash payment method and assign it to every `pos.config` via `payment_method_ids`.
In Odoo 19 this raises:

```
ValidationError: Validation Error: You cannot assign the same Cash payment method to multiple POS Shops.
Please create a separate Cash payment method for each shop.
```

## Root Cause

`point_of_sale/models/pos_payment_method.py` has a constraint new to this behavior family:

```python
@api.constrains('config_ids', 'is_cash_count', 'journal_id')
def _check_cash_method_single_shop(self):
    for method in self:
        is_cash = method.is_cash_count or (method.journal_id and method.journal_id.type == 'cash')
        if is_cash and len(method.config_ids) > 1:
            raise ValidationError(...)
```

Any payment method whose journal is of type `cash` (or flagged `is_cash_count`) may belong to at
most ONE `pos.config`. Bank-type methods (mada, credit card, STC Pay wallets) CAN be shared freely
across all configs.

## Solution ✅

For N branches create N cash journals + N cash payment methods (one pair per branch), and share the
bank methods:

```python
Journal = env['account.journal']
PM = env['pos.payment.method']
Config = env['pos.config']

# Shared bank methods (mada / card / STC Pay) — one journal + method each, reused by all configs
def get_bank_pm(name, code):
    j = Journal.search([('code', '=', code), ('company_id', '=', company.id)], limit=1) \
        or Journal.create({'name': name, 'code': code, 'type': 'bank', 'company_id': company.id})
    return PM.search([('journal_id', '=', j.id)], limit=1) \
        or PM.create({'name': name, 'journal_id': j.id, 'company_id': company.id})

pm_mada = get_bank_pm('مدى Mada', 'MADA')

for i, branch in enumerate(branches, start=1):
    code = 'CSH%02d' % i                      # journal code max 5 chars
    cj = Journal.create({'name': 'نقدية %s' % branch, 'code': code, 'type': 'cash',
                         'company_id': company.id})
    pm_cash = PM.create({'name': 'كاش - %s' % branch, 'journal_id': cj.id,
                         'company_id': company.id})
    Config.create({'name': branch,
                   'payment_method_ids': [(6, 0, [pm_cash.id, pm_mada.id])]})
```

`pos.config.create()` handles the rest (picking type, sequences, default sale journal) — no need to
pass them.

## ⚠️ Pitfalls

- `account.journal.code` is limited to 5 characters — use compact codes like `CSH01`…`CSH22`.
- The constraint triggers on `config_ids`, `is_cash_count` AND `journal_id` — you also hit it when
  *retargeting* an existing shared method to a cash journal.
- A bank journal method is shareable, so don't waste 22 journals on mada/card — only cash needs
  per-shop isolation.
- Running scripts through `odoo-bin shell` piped from stdin: wrap everything in a function and
  `exec(open('script.py').read())` — blank lines inside piped REPL blocks cause SyntaxError.
- On macOS + pyenv: `python3` resolves per-cwd via `.python-version`; running the same script from
  another directory can silently pick a Python without Pillow/odoo deps.
