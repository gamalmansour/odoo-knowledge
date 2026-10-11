# DB restored from a newer build than local code → every module install/upgrade fails

## Metadata
- **Category:** Upgrade
- **Severity:** 🟡 Medium
- **Odoo Versions:** All (hit on 19)
- **Tags:** `ir.ui.view`, `ParseError`, `enterprise`, `build-mismatch`, `-i`, `-u`
- **Last Verified:** 2026-07-25
- **Author:** ENG/Gamal Mansour

## Problem ❌
A DB restored from Odoo Online/a newer server runs fine day-to-day on older
local checkouts — until you `-i` or `-u` ANY module. Then view validation
recompiles the full inherited arch and stored views reference fields/actions
that don't exist in the local code:
```
Field `payslip_generate_and_send_trigger` does not exist
action_open_version_form_view is not a valid action on hr.version
```
It's whack-a-mole: fixing one stale view surfaces the next (settings form,
then hr.version list, …), because the DB's module artifacts are NEWER than
the code on disk. `-u` of the owning module fails on the same
chicken-and-egg validation.

## Solution ✅
- Diagnose: find the stored view via
  `SELECT id, key FROM ir_ui_view WHERE arch_db::text LIKE '%<field>%'`,
  then grep the local addons for the field/method. Present in DB metadata
  (`ir_model_fields.state='base'`) but absent in code = build mismatch.
- Real fix: `git pull` community+enterprise to a build ≥ the DB's, then
  upgrade. Anything else (deactivating stale views one by one) DOWNGRADES
  DB artifacts to older code and can break screens users rely on.
- If updating code is not an option now: DEFER the install (we deferred
  hr_appraisal's 9 records), snapshot first, and restore any view you
  temporarily deactivated (`active=false` → back to `true`).

## ⚠️ Pitfalls
- The mismatch is invisible in normal operation — check it BEFORE promising
  "we'll just install module X" on a restored enterprise DB.
- A failed `-i` rolls back its own work but any manual `UPDATE ir_ui_view
  SET active=false` you did beforehand STAYS — always restore it.
