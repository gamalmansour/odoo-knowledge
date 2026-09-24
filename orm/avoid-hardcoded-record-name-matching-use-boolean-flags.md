# Avoiding String-Hardcoded Business Logic (Name Matching Anti-Pattern) via Explicit Boolean Flags

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `anti-pattern`, `data-integrity`, `i18n`, `localization`, `boolean-flags`, `safe-design`

---

## Problem

Developers frequently write conditional logic based on matching hardcoded strings on a record's name (e.g. checking if a record is "Other", "Default", or "Standard"):

```python
# Hardcoded String Matching Anti-Pattern
@staticmethod
def _is_other(record):
    return bool(record) and (record.name or '').strip().lower() == 'other'
```

This causes silent and catastrophic failures in production:
1. **Localization & Translations:** In multilingual deployments (e.g., Arabic interface), the record's name is translated to `"أخرى"`, causing `record.name.lower() == 'other'` to evaluate to `False`. Conditional UI fields and business flows fail to trigger.
2. **User Renaming:** If a business user edits the name to `"Other Projects"` or `"Unlisted Developer"`, the matching fails.
3. **Missing Seed Data:** Often developers create the `"Other"` record only in transient test cases (`TransactionCase.setUp()`) but fail to ship an XML data file with `noupdate="1"`, leaving production databases with `no_create=True` M2o fields that have no selectable target.

## Root Cause

`name` is a user-facing, mutable, translatable label. Using it as a programmatic system discriminator violates Separation of Concerns.

## Solution ✅

Use an explicit boolean flag on the target model, expose it in the form view, and drive logic through it:

### 1. Model Definition (Target Model)
Add a boolean checkbox:

```python
class ListingProjects(models.Model):
    _inherit = "listing.projects"

    is_other = fields.Boolean(
        string="Is Other / أخرى",
        default=False,
        help="Mark this record as the catch-all 'Other' record.",
    )
```

### 2. Defensive Evaluation with Backward Compatibility
In the dependent model, check the boolean flag primarily, and keep a multi-language fallback:

```python
@staticmethod
def _is_other(record) -> bool:
    if not record:
        return False
    if getattr(record, 'is_other', False):
        return True
    name = (record.name or '').strip().lower()
    return name in ('other', 'أخرى', 'اخرى')
```

### 3. Permanent Seed Data (XML)
Ship a permanent seed record with `noupdate="1"` so every environment has the record available out of the box:

```xml
<odoo>
    <data noupdate="1">
        <record id="project_other" model="listing.projects">
            <field name="name">Other</field>
            <field name="is_other" eval="True"/>
        </record>
    </data>
</odoo>
```

## ⚠️ Pitfalls

- **Relying Only on Checkbox without Fallback:** Existing databases or unit tests that already create records with `name='Other'` will break if you don't provide a graceful fallback to name matching.
- **noupdate Flag:** Always use `noupdate="1"` for system seed records so that customer-side renames or translations are not overwritten during future module upgrades.

## Verification

1. Create a record with `is_other=True` and a non-English name (e.g., `"أخرى"`).
2. Verify that `_is_other(record)` returns `True`.
3. Verify that conditional UI fields appear properly regardless of language or name.
