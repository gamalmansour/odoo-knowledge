# ZATCA QR Code (`l10n_sa_qr_code_str`) Empty When Retrofitting `l10n_sa` onto Existing Company with Posted Entries

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-16                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `l10n_sa`, `zatca`, `qr_code`, `account_fiscal_country_id`, `account.move`, `res.company`

---

## Problem

> When installing `l10n_sa` and `l10n_gcc_invoice` on an existing Odoo database that already has `account` installed and posted `account.move.line` entries:
> 1. Setting `country_id = ref('base.sa')` and `vat` on `base.main_company` still leaves `invoice.l10n_sa_qr_code_str` empty (`''`) after calling `action_post()`.
> 2. Attempting to also set `currency_id = ref('base.SAR')` in XML fails module upgrade with:

```
odoo.exceptions.UserError: You cannot change the currency of the company since some journal items already exist.
```

## Root Cause

1. In `addons/l10n_sa/models/account_move.py`, `_post()` checks `if move.country_code == 'SA' and move.is_sale_document():` before populating `l10n_sa_confirmation_datetime`.
2. On `account.move`, `country_code` is `related='company_id.account_fiscal_country_id.code'` — **not** `company_id.country_id.code`. If `account` was initialized before `country_id` was set to Saudi Arabia, `account_fiscal_country_id` remains `US` (or False), so `l10n_sa_confirmation_datetime` stays False and `_compute_qr_code_str` produces `''`.
3. `account` locks `res.company.currency_id` as soon as `SELECT count(*) FROM account_move_line > 0`.

## Solution ✅

1. Activate `base.SAR` without overwriting `base.main_company.currency_id` when journal items already exist.
2. Explicitly set **both** `country_id` and `account_fiscal_country_id` to `base.sa` (plus a 15-digit `vat`) on `base.main_company`:

```xml
<record id="base.main_company" model="res.company">
    <field name="country_id" ref="base.sa"/>
    <field name="account_fiscal_country_id" ref="base.sa"/>
    <field name="vat">312659575100003</field>
</record>
```

3. Ensure `invoice_date` is set on `out_invoice` / `out_refund` before `super()._post()`, because `datetime.combine(move.invoice_date, ...)` requires a non-empty `invoice_date`.

## ⚠️ Pitfalls

- **Never include `<field name="currency_id" ref="base.SAR"/>` on `base.main_company` in an addon XML** if `account` may already have posted demo or historical journal items.
- **CLI Test Runner WebSocket Hang:** When running `-u <module> --test-enable --stop-after-init` while a browser tab is open on the live server port (e.g. `8017`), pass `--http-port=8099` so the open browser WebSocket reconnect does not block process shutdown.

## Verification

```python
inv.action_post()
assert bool(inv.l10n_sa_qr_code_str)  # Base64 TLV ZATCA Phase-1 QR payload
```

## References

- `odoo/addons/l10n_sa/models/account_move.py`
