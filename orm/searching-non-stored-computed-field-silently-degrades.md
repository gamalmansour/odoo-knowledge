# Searching a non-stored computed field silently returns the WRONG record (domain leaf degrades to always-true)

## Metadata
- **Category:** ORM
- **Severity:** 🔴 Critical
- **Odoo Versions:** All
- **Tags:** `orm`, `search`, `computed-field`, `non-stored`, `domain`, `multi-company`, `money-routing`
- **Last Verified:** 2026-07-20
- **Author:** ENG/Gamal Mansour

## Problem ❌
A `search()` whose domain filters on a **non-stored computed field** does NOT raise — it silently returns the wrong records. In the log you only get a non-fatal ERROR line, and the call proceeds as if the leaf were `TRUE`:
```text
ERROR <db> odoo.osv.expression: Non-stored field res.company.country_id cannot be searched.
```
Real-world hit (Activity app, money-routing): a helper mapped a country to its company with
```python
# activity_enrollment/models/activity_subscription.py  (BROKEN)
company = self.env['res.company'].sudo().search(
    [('country_id', '=', country.id)], limit=1)   # res.company.country_id is NON-STORED
```
`res.company.country_id` (`odoo/addons/base/models/res_company.py`) is `compute='_compute_address'`, `inverse='_inverse_country'`, **no `store=True`, no `search=`**. Odoo cannot turn the leaf into SQL, drops it, and the search degrades to **"first company by `_order` (`sequence, name`)"** — completely ignoring `country`. The cart / subscription / invoice then lands on an **arbitrary company's chart of accounts & VAT config**.

It shipped green because the test DB had ONE company that happened to sort first — the tests never exercised 2+ companies with distinct countries, so "wrong company" and "right company" were the same record.

## Root Cause 🔍
A domain leaf must be translatable to SQL. For that, the field must be either **stored** (real column) or provide a **`search=` method** (a compute-only field with a search callback). `res.company.country_id` is neither: it is recomputed from `partner_id`'s contact address on the fly. `odoo/osv/expression.py`, when it meets a non-stored field with no search method, logs the ERROR above and replaces the leaf with a dummy always-true term instead of raising — so the bug is silent at runtime.

## Solution ✅
Search the **stored seam** the computed field is derived from / writes back to, not the computed field itself.

For `res.company.country_id`, the inverse `_inverse_country` writes the value onto `partner_id.country_id` (stored on `res.partner`), and `res.company.create` seeds the same field from the `country_id` create value. So filter through the partner:

**Before:**
```python
self.env['res.company'].search([('country_id', '=', country.id)], limit=1)   # silently wrong
```
**After:**
```python
self.env['res.company'].search([('partner_id.country_id', '=', country.id)], limit=1)  # real SQL JOIN
```
General recipe, pick one:
1. **Traverse to the stored source** in the domain (`partner_id.country_id`) — cheapest, no schema change. Preferred.
2. Make the field a **stored related** field (`related='partner_id.country_id', store=True`) when you own the model — but NEVER re-declare a core field like `res.company.country_id` as stored; you'd change core semantics globally.
3. Add an explicit **`search=` method** to the computed field (`fields.X(compute=..., search='_search_x')`) when there is no single stored source.

## ⚠️ Pitfalls
- **It never crashes.** There is no exception to catch — only a log ERROR and a wrong result. Grep your logs for `cannot be searched` after any multi-company / catalog / routing work.
- **Tests with a single record hide it.** Any test asserting "the right one is picked" MUST create **2+ records with distinct key values**; with one record the wrong answer equals the right answer. This is exactly how the money-routing bug passed CI.
- **`address_get(['contact'])` edge case:** `res.company.country_id`'s compute reads the *contact* child partner, while the inverse writes `partner_id.country_id`. For a company with child contacts these can differ — matching on `partner_id.country_id` matches what the company form's Country field actually sets, which is the correct stored source of truth.
- **Defensive log for the "one-per-X" contract:** if the domain is meant to return a single record (one company per country), `search(limit=2)` and warn when `len > 1`, so a misconfiguration surfaces instead of silently billing an arbitrary entity.

## Verification
```python
# odoo-bin shell / a TransactionCase — proves the filter now respects the key
Company = env['res.company']
sa, eg = env.ref('base.sa'), env.ref('base.eg')
c_sa = Company.create({'name': 'KSA', 'country_id': sa.id})
c_eg = Company.create({'name': 'EG',  'country_id': eg.id})
Sub = env['activity.subscription']
assert Sub._company_for_country(sa) == c_sa
assert Sub._company_for_country(eg) == c_eg          # BROKEN code returns c_sa (or main) for BOTH
assert Sub._company_for_country(sa) != Sub._company_for_country(eg)
```
Also confirm the log no longer contains `Non-stored field res.company.country_id cannot be searched`.

## References
- Odoo core: `odoo/addons/base/models/res_company.py` (`country_id` = `compute='_compute_address'`, `inverse='_inverse_country'`)
- Odoo core: `odoo/osv/expression.py` (non-stored, non-searchable leaf handling)
- Fixed in: `activity/activity_enrollment/models/activity_subscription.py` → `_company_for_country`
- Same-family precedent (already avoided the helper): `activity/activity_media/controllers/media_controller.py`
- Related file: `orm/related-field-keyerror-reference.md`
