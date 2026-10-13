# Excel Import Header Auto-Mapping and Many2one Relation Traps in Odoo 18

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | data_migration                             |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-13                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `excel_import`, `base_import`, `many2one`, `header_mapping`, `uom`, `construction`

---

## Problem

When importing Excel sheets into Odoo via the standard UI (`Favorites -> Import records`), users frequently encounter two major issues:
1. **Unmapped Columns:** Columns whose field labels contain a forward slash `/` (such as `Product/Item` or `Source (Project/Tender)`) fail to auto-map in Odoo's import wizard and appear with `Don't Import`.
2. **Missing Relation Errors:** Many2one fields fail with:
```text
No matching record found for value 'XYZ' for field 'Product/Item'
No matching record found for value 'ساعة' for field 'Unit'
```

## Root Cause

1. **The Slash `/` Delimiter Trap:**
   In Odoo's import engine (`addons/base_import/models/base_import.py`, method `_get_mapping_suggestion`), any column header containing `/` is treated as a relational hierarchy path (subfield lookup, e.g. `partner_id/country_id/name`). When a user supplies an Excel header like `Product/Item`, Odoo tries to find a relation named `Product` having a subfield named `Item`, which fails to match the model's direct field `product_id`.
2. **Many2one Matching by Name / UoM Localization:**
   Many2one fields resolve records via `name_search`. If the target model (`uom.uom`) has English base names (`Hours`, `m³`, `t`, `m²`, `Units`, `L`), using localized or colloquial values (like `ساعة` or `طن`) will return empty results and fail validation.

## Solution ✅

### 1. Use Exact Technical Field Names as Excel Column Headers
By naming the first row in the Excel sheet with the model's technical field names, Odoo's `base_import` bypasses label fuzzy-matching and immediately maps all columns with 100% precision:

```python
headers = [
    "date_recorded",
    "product_id",
    "cost_type",
    "uom_id",
    "unit_price",
    "source_reference",
    "region"
]
```

### 2. Supply Exact Relational Search Values
For Many2one fields like `product_id` and `uom_id`:
- For `product_id`: Provide either the exact `display_name` (e.g. `[EQ-EXC-20T] Hydraulic Excavator 20-ton`), the product `name`, or the `default_code` alone.
- For `uom_id`: Provide the exact UoM string stored in `uom.uom` (e.g. `Hours`, `m³`, `t`, `m²`, `Units`, `L`).
- For Selection fields (e.g. `cost_type`): Provide the technical selection key (`equipment`, `material`, `labor`, `subcontractor`, `overhead`).

### 3. Programmatic Dry-Run Validation
Before providing the import file to end users, run a non-destructive dry-run import in an isolated test environment:

```python
import openpyxl, io
from odoo import api, SUPERUSER_ID

with open('import_file.xlsx', 'rb') as f:
    raw_data = f.read()

imp = env['base_import.import'].create({
    'res_model': 'construction.cost.rate',
    'file': raw_data,
    'file_name': 'import_file.xlsx',
    'file_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
})
preview = imp.parse_preview({'has_headers': True})
columns = preview.get('headers')
fields = [preview['matches'][i][0] for i in range(len(columns))]

res = imp.execute_import(fields, columns, {'has_headers': True}, dryrun=True)
assert len(res.get('messages', [])) == 0, f"Import errors: {res.get('messages')}"
print("Validated rows:", len(res.get('ids', [])))
```

## ⚠️ Pitfalls

- **Avoid Special Characters in Headers:** Never use `/`, `\`, or `.` in column headers unless you deliberately intend to do relational sub-field mapping (e.g., `partner_id/name`).
- **Binary Format in base_import:** `base_import.import.file` expects raw binary bytes `b'...'`, not base64-encoded strings, when manipulated directly via python scripts.
- **Selection Values:** Do not invent new selection values in the spreadsheet; they must strictly match the model's defined `selection` list keys or labels.

## Verification

Upload the file via Odoo Web Client:
1. Navigate to target view (e.g., `Tenders -> Cost Database -> Historical Rates`).
2. Click **⚙️ Actions / Favorites -> Import records**.
3. Upload `import_construction_cost_rates.xlsx`.
4. Observe that all 7 columns are auto-mapped without any manual selection needed.
5. Click **Test** -> Should return: `"Everything seems valid."`

## References

- Odoo Core: `addons/base_import/models/base_import.py`
- Model: `construction.cost.rate` in `construction_tender`
