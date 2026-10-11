# Hierarchical Data Import via Dot Notation

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                   |
| Last Verified | 2026-06-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `import`, `hierarchy`, `excel`, `dot-notation`

---

## Problem

> When importing hierarchical records (like a Bill of Quantities or WBS) from Excel, the traditional approach relies on Odoo's default parent/child mapping, which often fails if rows are not strictly ordered or if names are duplicate. Users in construction/engineering heavily prefer **Dot Notation** (e.g., 1, 1.1, 1.1.1) to define hierarchy, but native Odoo import does not parse this structure implicitly.

## Root Cause

> Odoo processes imported rows sequentially. If you only have a flat `code` column with dot notation, Odoo doesn't automatically know that `1.1` should be the `parent_id` of `1.1.1` unless explicitly mapped to a database ID or an `External ID`. During custom wizard imports, if you don't cache the parents, you either have to do heavy SQL queries to find parents or you lose the tree structure entirely.

## Solution ✅

> In your custom Excel import wizard (e.g., `xlrd` or `openpyxl`), use a running dictionary to track the created records by their full string code. When parsing a row, split the code by the last dot to find the parent code, look it up in the dictionary, and link the ID.

```python
        Boq = self.env['project.boq.item']
        full_code_to_record = {}
        
        for r in range(1, sheet.nrows):
            # 1. Safely parse the code, handling floats from Excel
            raw_code = sheet.cell_value(r, 0)
            if isinstance(raw_code, float):
                full_code = str(int(raw_code)) if raw_code.is_integer() else str(raw_code)
            else:
                full_code = str(raw_code).strip()
            
            # 2. Extract parent and current level code
            parent_id = False
            code_to_save = full_code
            if full_code and '.' in full_code:
                parts = full_code.rsplit('.', 1)
                parent_code = parts[0]
                code_to_save = parts[1]
                
                if parent_code in full_code_to_record:
                    parent_id = full_code_to_record[parent_code].id

            # 3. Create the record
            vals = {
                'parent_id': parent_id,
                'code': code_to_save or False,
                # ... other fields
            }
            new_record = Boq.create(vals)
            
            # 4. Cache it for subsequent child rows
            if full_code:
                full_code_to_record[full_code] = new_record
```

## ⚠️ Pitfalls

> - **Float Parsing:** Excel libraries (`xlrd`, `openpyxl`) often read numeric cells as floats (e.g., `1` becomes `1.0`, `1.1` remains `1.1`). You MUST check `is_integer()` and cast appropriately, otherwise `1.0` won't match a child that declares `1` as its parent.
> - **Order Dependency:** This approach strictly requires the Excel rows to be sorted in a top-down hierarchical order (parents before children). If a child appears before its parent, `full_code_to_record` will raise a KeyError or silently set `parent_id=False`.
> - **Trailing Whitespace:** Always `.strip()` the parsed strings to avoid mismatching `1.1 ` with `1.1`.
