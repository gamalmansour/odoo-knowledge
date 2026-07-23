# An Inheriting View Whose xpath Targets a Field Added by the Base Form Must Load AFTER It — Fresh Install (odoo.sh) Fails, `-u` Hides It

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-23                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `inheritance`, `manifest`, `load-order`, `xpath`, `fresh-install`, `odoo-sh`, `ParseError`

---

## Problem

Deploying to a **fresh** database (odoo.sh build, or a new customer) aborts:

```
odoo.tools.convert.ParseError: while parsing .../contract_fidic_views.xml:159
Error while parsing or validating view:
Element '<xpath expr="//field[@name='payment_days']">' cannot be located in parent view
```

…yet `-u <module>` on the developer database worked fine every time. The field `payment_days` exists, the base form has it, the xpath is correct.

## Root Cause

The inheriting view (`contract_fidic_views.xml`) is listed in the manifest `data` list **before** the base view file (`contract_owner_views.xml`) that adds `payment_days` to the form:

```python
'data': [
    ...
    'views/contract_fidic_views.xml',    # inherits view_contract_owner_form, xpaths payment_days
    'views/contract_p3_views.xml',       # also inherits it
    'views/contract_owner_views.xml',    # ← DEFINES the form WITH payment_days, loads too late
    ...
]
```

On a **fresh install** Odoo processes data files top-to-bottom; when it applies the inheriting view, the base form in the DB does not yet contain `payment_days`, so the xpath cannot locate it. On an **incremental `-u`** the base form already carried `payment_days` from a previous upgrade, so the inheriting view finds it regardless of order — which is exactly why the bug is invisible in day-to-day dev and only bites the first clean deploy.

## Solution ✅

List every base view file **before** the files that inherit it (and before files whose xpaths target fields the base adds):

```python
'views/contract_owner_views.xml',            # base form (defines payment_days, the tabs, …)
'views/contract_subcontractor_views.xml',    # base subcontractor-invoice form
...
# these inherit the two forms above → load them last
'views/contract_fidic_views.xml',
'views/contract_p3_views.xml',
```

Same rule applies to menus/actions referenced by xmlid, and to a field one file adds and another file's xpath targets.

## ⚠️ Pitfalls

- **`-u` never reproduces this.** Verify on a throwaway DB with a real fresh install:
  ```bash
  dropdb cctest_fresh; ./odoo-bin -c conf -d cctest_fresh -i <module> --stop-after-init --without-demo=all
  ```
  Exit 0 = the manifest order is deploy-safe; a ParseError here is what odoo.sh would have thrown.
- The error blames the **inheriting** file and line; the fix is in the **manifest order**, not that file.
- A cross-file field/xpath dependency is easy to create by splitting a form across several view files (base + FIDIC + P3 tabs here). Keep the base form's own file first.
- Only ONE file should *define* a given field's placement in the base arch; others *inherit*. If two files both add the same anchor, order still matters.

## Verification

```bash
dropdb cctest_fresh 2>/dev/null
./odoo-bin -c odoo17_dev.conf -d cctest_fresh -i construction_contract --stop-after-init --without-demo=all
# EXIT=0, no ParseError → safe for odoo.sh
```

## References

- Hit deploying `construction_contract` v17.0.1.12.0 to odoo.sh — `contract_fidic_views.xml` / `contract_p3_views.xml` (P2/P3 tabs) inherited `view_contract_owner_form` but were listed before `contract_owner_views.xml` (which the P1 `payment_days` field lives in). Fixed by moving both inheriting files to the end of the view block.
- Related file: `views/xml-load-order-manifest.md`
- Related file: `setup/clean-db-install-verification-demo-as-data-and-missing-rule-fields.md`
