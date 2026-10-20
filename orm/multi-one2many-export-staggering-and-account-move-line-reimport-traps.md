# Multi-One2many Export Staggering (`invoice_line_ids` + `line_ids`) & Sub-Record Re-Import Traps on `account.move`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19 (All)                       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `account.move`, `account.move.line`, `base_import`, `export`, `one2many`, `invoice_line_ids`, `line_ids`, `account_id`

---

## Problem

When exporting `account.move` records from Odoo with columns from **two different One2many fields** simultaneously—specifically `Invoice lines/*` (`invoice_line_ids`) alongside `Journal Items/*` (`line_ids`)—to bulk-remap `Journal Items/Account` (`line_ids/account_id`) based on `Invoice lines/Product Category/Income Account`:

1. **Staggered / Staircase Row Misalignment:**
   On any multi-line invoice ($N > 1$ invoice lines), Odoo places:
   - **Row 1 of the move:** `invoice_line_ids[0]` (Columns E–H) alongside `line_ids[0]` (Columns I–L).
   - **Rows 2 .. $N$ of the move:** `invoice_line_ids[1..N-1]` in Columns E–H, while `line_ids/*` (Columns I–L, including `Journal Items/External ID`) are **completely blank (`None`)**.
   - **Rows $N+1$ .. $2N$ of the move:** `line_ids[1..M-1]` in Columns I–L, while `invoice_line_ids/*` (Columns E–H) are **completely blank (`None`)**.

2. **Two Re-Import Failures if Mapped Row-by-Row in Excel:**
   - **Spurious Line Creation (`Command.create`):** Putting an account value in `New Journal Items/Account` on rows $2..N$ (where `Journal Items/External ID` is `None`) causes `ir.fields.converter._str_to_one2many` to treat those rows as new sub-records (`id = None`) and emit `Command.create({'account_id': ...})` with zero debit/credit and no label.
   - **Nullified Receivable Account (`converted['account_id'] = False`):** Leaving `New Journal Items/Account` blank on the Receivable/Payable `line_ids` rows (which *do* have `Journal Items/External ID` populated) causes `ir.fields.converter.for_model` (`if not value: converted[field] = False`) to emit `Command.update(ar_line_id, {'account_id': False})`, crashing the import with:
     ```
     Missing required value for the field 'Account' (account_id)
     ```

## Root Cause

- **Export Engine:** Odoo's export engine iterates sub-tables sequentially after the first shared parent row rather than zipping independent One2many relations.
- **Import Engine (`addons/base_import/models/base_import.py` & `odoo/orm/models.py`):**
  - `_convert_import_data` strips rows where all mapped columns are empty (`if any(row)`).
  - `_extract_records` extracts sub-records for `relfield = 'line_ids'` whenever `any(it)` is truthy across `(line_ids/id, line_ids/account_id)`.
  - If `line_ids/id` is empty but `line_ids/account_id` is populated $\rightarrow$ `Command.create`.
  - If `line_ids/id` is populated (e.g., on the `102011 Accounts Receivable` line) but `line_ids/account_id` is empty $\rightarrow$ `Command.update(id, {'account_id': False})`.

## Solution ✅

Group rows by parent move (`External ID` in Column A), collect the ordered `invoice_line_ids` list and the ordered product `line_ids` list per move, verify 1-to-1 product label correspondence, and populate `New Journal Items/Account` **exclusively on rows where `Journal Items/External ID` is present**:

```python
import openpyxl

wb = openpyxl.load_workbook("Journal Entry (account.move).xlsx")
ws = wb["Sheet1"]

# 1. Group rows by move External ID (Col 1)
moves = []
curr = None
for r_idx in range(2, ws.max_row + 1):
    if ws.cell(r_idx, 1).value is not None:
        if curr:
            moves.append(curr)
        curr = {"inv_lines": [], "sales_jis": [], "ar_jis": []}
    prod_disp = ws.cell(r_idx, 5).value
    categ_inc_acc = ws.cell(r_idx, 8).value
    ji_ext_id = ws.cell(r_idx, 9).value
    ji_acc = ws.cell(r_idx, 10).value
    ji_label = ws.cell(r_idx, 12).value

    if prod_disp is not None or categ_inc_acc is not None:
        curr["inv_lines"].append((r_idx, prod_disp, categ_inc_acc))
    if ji_ext_id is not None:
        if ji_acc == "500001 Sales Account":
            curr["sales_jis"].append((r_idx, ji_ext_id, ji_acc, ji_label))
        else:
            curr["ar_jis"].append((r_idx, ji_ext_id, ji_acc, ji_label))
if curr:
    moves.append(curr)

# 2. Populate New Journal Items/Account (Col 11) ONLY on rows with ji_ext_id
for m in moves:
    assert len(m["inv_lines"]) == len(m["sales_jis"])
    for (_, prod_disp, categ_inc_acc), (ji_row, _, _, ji_label) in zip(m["inv_lines"], m["sales_jis"]):
        ws.cell(ji_row, 11).value = categ_inc_acc
    for (ar_row, _, ji_acc, _) in m["ar_jis"]:
        # Preserve existing Receivable/Payable account so import does not write account_id=False
        ws.cell(ar_row, 11).value = ji_acc

wb.save("Journal Entry (account.move).xlsx")
```

## ⚠️ Pitfalls

- **Posted Moves Readonly Guard:** `account.move.write()` blocks modifying `line_ids` when `move.state == 'posted'` (`You cannot modify the following readonly fields on a posted move: line_ids`). Reset posted moves to `draft` before importing `line_ids/account_id` changes, then re-post.
- **Unmapped Columns During Import:** In the Odoo Import Wizard, map **only** `External ID` (`id`), `Journal Items/External ID` (`line_ids/id`), and `New Journal Items/Account` (`line_ids/account_id`). Leave `Invoice lines/*` unmapped so `_convert_import_data` automatically drops the `Invoice lines`-only rows via `if any(row)`.

## Verification

```python
# Confirm every row with ji_ext_id has new_acc, and every row without ji_ext_id has new_acc is None
for r in ws.iter_rows(min_row=2, values_only=True):
    assert (r[8] is not None) == (r[10] is not None)
```
