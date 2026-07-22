# Section Grouping Silently Lost When Copying a Sectioned Line List Across Modules

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `copy`, `sections`, `display_type`, `line_section`, `two-pass`, `data-loss`, `boq`

---

## Problem

A sectioned line list (BOQ, sale order lines, anything using `display_type='line_section'`) is copied from one model to another — tender BOQ → contract BOQ, quote → order, template → document. Visually the result looks right: the section header rows are there, in the right order. But the grouping is gone — nothing knows which item belongs to which section any more.

The failure is invisible in the UI because **section rendering and section membership are two different things**:

- `display_type='line_section'` + the `section_and_note_text` widget makes a row *look* like a section header. That is presentation.
- A `section_id` many2one on each item is what *records* the membership. That is data.

Copy only the first and you get a list that looks grouped but cannot be grouped, subtotalled, or rebuilt.

## Root Cause

Two compounding mistakes:

1. **The destination model never got the `section_id` field.** The copy code faithfully copied `display_type` and `is_section`, so it read as complete in review — but the membership had nowhere to land. Verify against the schema, not the copy code:
   ```sql
   select column_name from information_schema.columns
   where table_name='contract_boq_line' and column_name like '%section%';
   -- only is_section -> the link was never storable
   ```
2. **Even with the field, a single-pass copy cannot set it.** A line's section may not have been created yet when the line itself is copied, so `section_id` would resolve to a stale id or nothing.

## Solution ✅

Add the mirror field, then copy in **two passes**:

```python
section_id = fields.Many2one(
    'contract.boq.line', string='Section', ondelete='set null',
    domain="[('contract_id','=',contract_id),('display_type','=','line_section')]",
)

def _import_boq_to_contract(self, contract):
    line_map = {}                                   # source line id -> copied line
    for line in self.boq_line_ids:
        new_line = self.env['contract.boq.line'].create({...})
        line_map[line.id] = new_line
        # ...children/breakdowns...

    # Second pass: the section may not have existed during pass one.
    # Group by section so N sections cost N writes, not one per item.
    items_by_section = {}
    for line in self.boq_line_ids.filtered('section_id'):
        if line_map.get(line.id):
            items_by_section.setdefault(line.section_id.id, []).append(line_map[line.id].id)
    for src_section_id, dst_line_ids in items_by_section.items():
        new_section = line_map.get(src_section_id)
        if not new_section:
            continue                                # stale link -> leave unsectioned
        self.env['contract.boq.line'].browse(dst_line_ids).section_id = new_section.id
```

Back the field with a constraint — the view domain is UI-only and does not stop an import or a data file:

```python
@api.constrains('section_id', 'contract_id')
def _check_section_id(self):
    for rec in self:
        if not rec.section_id:
            continue
        if rec.section_id == rec:
            raise ValidationError(_("A BOQ line cannot be its own section: %s") % (rec.name or ''))
        if rec.section_id.contract_id != rec.contract_id:
            raise ValidationError(_("The section of BOQ line '%s' must belong to the same contract.") % (rec.name or ''))
```

## ⚠️ Pitfalls

- **`sequence` is not a substitute for `section_id`.** Order is presentation; membership is data. Real symptom found in the field: every line in both the source and destination had `sequence = 10`, so ordering held *only* by the `id` tiebreak of insertion order. It looked correct until someone dragged one row — then the sequences were rewritten, the accidental order was gone, and with no `section_id` there was nothing left to rebuild the grouping from.
- **Do not "fix" that by auto-numbering on import.** BOQ ordering is the estimator's manual input; a system that renumbers 10/20/30 on every import silently overwrites a human decision. Copy `sequence` verbatim and solve grouping with `section_id`.
- **Never fall back to the source section id.** If `line_map` has no entry for the section (stale/cross-document link), leave the item unsectioned. Writing the source id points the copy at another document's section — worse than null.
- **A stale link is not a crash, it is silent corruption.** Nothing raises; the item just joins the wrong group. This is why the constraint matters more than the domain.
- **Section rows must not carry a `section_id` of their own** — assert it in tests, or nested-section bugs appear later.
- **Existing records need a backfill**, and the copy usually already stores the provenance (`tender_boq_line_id`), so the link is recoverable:
  ```sql
  -- COUNT FIRST, never write straight to a customer DB
  select c.contract_id, count(*) from contract_boq_line c
  join tender_boq_line t on t.id = c.tender_boq_line_id
  where t.section_id is not null and c.section_id is null group by 1;
  ```

## Verification

```bash
./odoo-bin -c odoo17_dev.conf -d <db> -u construction_contract --test-enable --stop-after-init
```

Assert on the *shape*, not just the counts: line count, section count, every item's `section_id` resolving inside the new document, `display_type='line_section'` on the target, unsectioned items staying unsectioned, and `sequence` copied verbatim.

## References

- Implemented in `construction_contract` v17.0.1.7.0 — `models/contract_boq_line.py`, `models/tender_opportunity.py` (`_import_boq_to_contract`), `views/contract_boq_views.xml`, `tests/test_boq_section_transfer.py` (8 tests)
- Related file: `orm/carry-register-across-lifecycle-stages.md` — same cross-module `create()`-copy shape, for risk registers
