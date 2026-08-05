# An Undefined ir.sequence Silently Names Every Record "New"

| Field         | Value        |
|---------------|--------------|
| Category      | models       |
| Odoo Versions | All          |
| Severity      | 🔴 Critical  |
| Last Verified | 2026-08-05   |
| Author        | ENG/Gamal Mansour |

**Tags:** `ir.sequence`, `next_by_code`, `data-quality`, `silent-failure`, `naming`

---

## Problem

Every subcontract, subcontractor payment application and owner interim payment certificate
in the database carried the same name — the literal string `New`:

```sql
SELECT 'contract_subcontractor' t, count(*) FILTER (WHERE name='New') unnamed, count(*) total
FROM contract_subcontractor
UNION ALL SELECT 'contract_subcontractor_invoice', count(*) FILTER (WHERE name='New'), count(*)
FROM contract_subcontractor_invoice
UNION ALL SELECT 'contract_progress_invoice', count(*) FILTER (WHERE name='New'), count(*)
FROM contract_progress_invoice;

--                t                | unnamed | total
-- --------------------------------+---------+-------
--  contract_subcontractor         |       4 |     4
--  contract_subcontractor_invoice |       8 |     8
--  contract_progress_invoice      |       1 |     1
```

100% unnamed. No error was ever raised, no warning logged, and the full test suite was green.

## Root Cause

The standard naming override looks completely correct:

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('contract.subcontractor') or _('New')
    return super().create(vals_list)
```

But `next_by_code()` **returns `False` for a code that does not exist** — it does not raise.
The `or _('New')` fallback, written as a defensive touch, then swallows the failure whole and
writes the placeholder as if it were a real reference.

The sequence had simply never been added to the module's `data/` XML. Code and data drifted
apart, and nothing in Odoo connects them: no check verifies that every `next_by_code` argument
corresponds to a defined `ir.sequence`.

For financial documents this is severe rather than cosmetic. An interim payment certificate is
cited by number in payment applications, correspondence and claims; a certificate named `New`
cannot be referenced at all, and a register of them cannot be sorted or audited.

## Solution ✅

Audit the whole codebase — this drift is never limited to the one model you noticed. Compare
every code passed to `next_by_code()` against every code defined in XML:

```bash
grep -rhoE "next_by_code\('[^']+'\)" --include="*.py" . \
  | sed "s/next_by_code('//;s/')//" | sort -u > /tmp/used.txt
grep -rhoE "<field name=\"code\">[^<]+</field>" --include="*.xml" . \
  | sed 's/.*>\(.*\)<.*/\1/' | sort -u > /tmp/defined.txt
comm -23 /tmp/used.txt /tmp/defined.txt      # used in code, defined nowhere
```

In this suite that single command turned one observed symptom into **five** missing sequences
across two modules. Define each one:

```xml
<record id="seq_contract_subcontractor" model="ir.sequence">
    <field name="name">Subcontract</field>
    <field name="code">contract.subcontractor</field>
    <field name="prefix">SUB/%(year)s/</field>
    <field name="padding">4</field>
    <field name="number_next">1</field>
    <field name="company_id" eval="False"/>
</record>
```

Confirm against the database, not the file — the XML may be present but unlisted in the
manifest's `data` key:

```sql
SELECT code, prefix FROM ir_sequence WHERE code = 'contract.subcontractor';
```

## ⚠️ Pitfalls

- `next_by_code()` returning `False` is the whole trap. `or _('New')` looks defensive and is
  actually what hides the bug. If a reference is mandatory, fail loudly instead:
  ```python
  seq = self.env['ir.sequence'].next_by_code('contract.subcontractor')
  if not seq:
      raise UserError(_("The subcontract sequence is missing. Contact your administrator."))
  ```
- Sequence XML normally sits in a `noupdate="1"` block, so adding a record is fine but
  **editing an existing one never reaches an existing database** — see
  `security/noupdate-group-change-never-reaches-existing-databases.md`.
- Adding the sequence only fixes records created from now on. Rows already stamped `New`
  stay `New` and need a data-repair migration if the database is not disposable.
- Tests do not catch this: nothing asserts on `name`, and `New` is a perfectly valid string.
  Add an explicit assertion per sequenced model:
  ```python
  self.assertNotEqual(record.name, 'New')
  self.assertTrue(record.name.startswith('SUB/'))
  ```
- Check uniqueness too — two records sharing a reference is the same class of defect.

## Verification

```bash
comm -23 /tmp/used.txt /tmp/defined.txt   # must print nothing
```

## References

- Related file: `security/noupdate-group-change-never-reaches-existing-databases.md`
- Related file: `backend/int-cast-on-config-parameter-crashes-on-human-input.md`
