# A copy-pasted core method is a version bomb — it detonates at the upgrade, not before

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-12                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `upgrade`, `migration`, `override`, `super`, `copy-paste`, `technical-debt`, `hr.leave`, `action_validate`, `diff`

---

## Problem

During a version upgrade, an override fails on helpers that no longer exist:

```
AttributeError: 'hr.leave' object has no attribute '_prepare_employees_holiday_values'
AttributeError: 'hr.leave' object has no attribute '_get_employees_from_holiday_type'
```

The module installed fine on the old version for years. The method is long — 80,
120, 200 lines — and nobody remembers what in it is actually custom.

## Root Cause

The override does not extend core, it **replaces** it: somebody copied the whole
core method body into the custom module and edited a line or two. That works until
the core method changes, and an upgrade changes it wholesale. In the case above,
Odoo 18 reduced `hr.leave.action_validate` from 117 lines to 27 and moved the
splitting logic into `_split_leaves`, so every helper the copy called had vanished.

The cost is not only the upgrade. For every release the copy sat there, **each core
bug fix to that method was silently discarded** — the module kept running an old
version of core logic that looked current.

## Solution ✅

**Do not port the copy forward. Find the one thing it actually changed, and express
only that.**

```bash
# 1) Get the ORIGINAL core method from the version the copy was made against
sed -n '/def action_validate/,/^    def /p' \
  /path/to/odoo17.0/addons/hr_holidays/models/hr_leave.py > /tmp/core17.py

# 2) Diff the override against it -- the real customization is usually 1-3 lines
diff /tmp/core17.py <(sed -n '/def action_validate/,/^    def /p' custom/models/x.py)
```

In the real case the entire diff was **one commented-out `ValidationError`**: the
business wanted leave requests approved even when they land on a public holiday.
That intent fits in four lines, on the new core:

```python
def action_validate(self, check_state=True):
    """Approve a leave without the public-holiday overlap check."""
    # _get_leaves_on_public_holiday is what raises; returning an empty recordset for
    # the duration of the call suppresses exactly that check and nothing else.
    original = type(self)._get_leaves_on_public_holiday

    def _no_public_holiday_block(records):
        return records.browse()

    type(self)._get_leaves_on_public_holiday = _no_public_holiday_block
    try:
        return super().action_validate(check_state=check_state)
    finally:
        type(self)._get_leaves_on_public_holiday = original
```

117 lines → 4, and every future core fix to the rest of the method is inherited.

**The general shapes**, in order of preference:
1. **Guard + `super()`** — early-return to core when the customization is not in play.
2. **Neutralize the one blocking helper** around a `super()` call, as above, restoring
   it in a `finally`.
3. **Override the small helper the core method calls**, not the core method itself —
   check first whether one exists; Odoo usually factors these out for exactly this.

## ⚠️ Pitfalls

- **Do not migrate the copy line by line.** It is the expensive option *and* the one
  that reproduces the debt for the next upgrade.
- **Restore the patched attribute in a `finally`.** Patching on `type(self)` is
  process-wide; an exception escaping without the restore leaves the check disabled
  for every other user on that worker.
- **Audit for these BEFORE quoting an upgrade.** A method over ~40 lines in a custom
  module that shares a name with a core method is the signature. One cheap sweep:
  `grep -rn "def " custom_modules/ | ...` then compare lengths against core.
- **The commented-out line is the requirement.** Read the diff before deleting
  anything — a `# raise ValidationError(...)` is somebody's business rule, recorded
  in the worst possible place.

## Verification

```bash
# No helper the override calls may be missing from the new core:
python3 -c "import ast,sys; ..."   # or simply run the upgrade with tests:
./odoo-bin -c <conf> -d <db> -u <module> --test-enable --test-tags /<module> --stop-after-init
```

Then exercise the *behaviour the copy existed for* by hand — an upgrade that
installs cleanly proves the override runs, not that it still does its job.

## References

- Fixed in: `HR18/hr_payroll_customs/models/custom_leave.py` (`action_validate`)
- Core (18.0): `addons/hr_holidays/models/hr_leave.py` → `action_validate`, `_split_leaves`
- Related file: `orm/custom-override-replacing-core-method-breaks-all-payments.md`
- Related file: `upgrade/hr-leave-employee-ids-removed-odoo18.md`
