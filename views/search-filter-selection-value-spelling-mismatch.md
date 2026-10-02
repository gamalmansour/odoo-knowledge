# Search Filter Hardcoding Selection Value Spelling Variant Silently Yields Empty Results

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `search-view`, `filter`, `selection`, `spelling-mismatch`, `silent-empty`, `labor`, `labour`

---

## Problem

When a user clicks on a search filter in a List or Kanban view (e.g. "Labour"), the view returns zero records even though records exist in the database with that category. No Python or JavaScript error is raised; the filter simply matches nothing because the selection key defined in Python does not match the hardcoded string in the XML filter domain.

Example:
```xml
<!-- In XML search view -->
<filter string="Labour" name="filter_labour" domain="[('cost_type', '=', 'labour')]"/>
```

While in Python:
```python
# In Model definition
cost_type = fields.Selection([
    ('material', 'Material'),
    ('labor', 'Labor'),  # Note American spelling 'labor'
    ('equipment', 'Equipment'),
    ('subcontractor', 'Subcontractor'),
], string='Cost Type')
```

Because SQL queries `WHERE cost_type = 'labour'`, it silently matches 0 rows.

## Root Cause

Different developers or upstream modules use American vs. British English spellings (e.g., `labor` vs. `labour`, `meter` vs. `metre`, `color` vs. `colour`). If an XML search view assumes one spelling and the Python selection field registers another, the domain leaf fails to match.

Furthermore, when data is copied across modules (e.g., from `tender.boq.line` with `labor` to `contract.boq.line` with `labour`), a direct assignment raises `ValueError: Wrong value for contract.boq.line.boq_type: 'labor'`.

## Solution ✅

### 1. In XML Search Views:
Use an `'in'` operator covering both spelling variants, or align with the Python model's exact key:

```xml
<filter string="Labor" name="filter_labor" domain="[('cost_type', 'in', ['labor', 'labour'])]"/>
```

### 2. In Cross-Module Data Transfers:
Defensively map selection values between modules when creating or copying lines:

```python
# When copying from tender BOQ line to contract BOQ line:
def _map_boq_type(tender_type: str) -> str:
    if tender_type == 'labor':
        return 'labour'
    return tender_type
```

## ⚠️ Pitfalls

- Never assume consistent spelling across third-party or inherited modules. Always verify the actual selection keys defined in the target model (`dict(self.fields_get(['field_name'])['field_name']['selection'])`).
- In Odoo 18, check if selection fields allow multiple values or dynamic selection callbacks.

## Verification

Query the database directly or use an automated test asserting that clicking the filter finds the expected records:

```python
records = self.env['construction.cost.rate'].search([('cost_type', 'in', ['labor', 'labour'])])
self.assertTrue(len(records) > 0)
```
