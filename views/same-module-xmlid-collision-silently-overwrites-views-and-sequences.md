# Same-Module XML ID Collision Silently Overwrites Records Based on Manifest Load Order

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-16                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `xmlid`, `collision`, `ir.sequence`, `ir.ui.view`, `overwrite`, `manifest-load-order`

---

## Problem

When developing modules with multiple XML files (e.g., separating main views from subline views, or splitting sequence files), declaring a `<record id="..." model="...">` with an existing XML ID does **NOT** raise a duplication or parse error. Instead, Odoo performs an in-place silent overwrite of the earlier record with the definition from whichever XML file appears later in `__manifest__.py['data']`.

This results in silent data and UI degradation:
1. **Views:** Form views suddenly lose fields, notebook tabs, or `<chatter/>` because a secondary or simplified view file defined later in the manifest stomped on the primary form.
2. **Sequences:** Numbering prefixes (e.g. annual `WIR/%(y)s/` vs generic `WIR/`) or padding silently revert to an unexpected format without any warning in server logs.

```xml
<!-- In views/tender_boq_views.xml -->
<record id="view_tender_boq_line_form" model="ir.ui.view">
    <field name="name">tender.boq.line.form</field>
    <field name="model">tender.boq.line</field>
    <!-- Has chatter, display_type, sections -->
</record>

<!-- In views/tender_boq_line_views.xml (loaded later in manifest) -->
<record id="view_tender_boq_line_form" model="ir.ui.view">
    <field name="name">tender.boq.line.form</field>
    <!-- Only has breakdown table; NO chatter, NO sections! -->
    <!-- SILENTLY DESTROYS THE EARLIER VIEW! -->
</record>
```

## Root Cause

Odoo's XML data loader uses `ir.model.data` to look up records by `(module, xml_id)`. When an XML ID already exists for the module being installed/updated:
1. It updates the existing `res_id` in PostgreSQL rather than failing with a uniqueness constraint.
2. The attributes and `arch` of the second record completely replace the first record in the database.

## Solution ✅

1. **Audit for Duplicate XML IDs:**
   Run a quick AST or XML parser check across the module to detect duplicate IDs within the same module:

   ```bash
   python3 -c "
   import glob, xml.etree.ElementTree as ET
   seen = {}
   for xf in glob.glob('my_module/**/*.xml', recursive=True):
       tree = ET.parse(xf)
       for elem in tree.getroot().findall('.//*[@id]'):
           eid = elem.get('id')
           if eid in seen:
               print(f'Collision: {eid} in {seen[eid]} and {xf}')
           else:
               seen[eid] = xf
   "
   ```

2. **Unify Dual Views into a Canonical View:**
   Combine the disparate elements into a single rich form view with notebook tabs:
   - Header & action buttons
   - Main sheet fields & section dividers
   - Notebook pages for child one2many breakdowns
   - `<chatter/>` at the bottom

3. **Use Explicit Suffixes for Specialized Popups:**
   If a separate simplified view is needed for modal popups, give it a distinct ID (e.g. `view_tender_boq_line_popup_form`) and bind it explicitly in action windows or contexts.

4. **Deduplicate Sequence Files:**
   Keep all sequence definitions inside a single canonical `data/ir_sequence_data.xml` file, eliminating duplicate files or repeated `<record>` elements.

## ⚠️ Pitfalls

- Odoo will not output any warning or error when a record is overwritten by the same XML ID in another data file within the same module.
- Always check the order in `__manifest__.py['data']` when unexpected view fields disappear after an upgrade.

## Verification

Run an XML duplicate scanner across all module XML files and ensure count is 0:
```bash
python3 -c "
import glob, xml.etree.ElementTree as ET
ids = set()
for f in glob.glob('views/*.xml'):
    for r in ET.parse(f).getroot().findall('.//record'):
        assert r.get('id') not in ids, f'Duplicate: {r.get(\"id\")}'
        ids.add(r.get('id'))
print('All XML IDs unique!')
"
```
