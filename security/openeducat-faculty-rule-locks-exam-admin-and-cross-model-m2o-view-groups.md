# OpenEduCat `group_op_faculty` Record Rule Locks Out `group_op_exam_admin` & `sale_order_id` View Group Sync

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `ir.rule`, `openeducat`, `group_op_faculty`, `group_op_exam_admin`, `sale.order`, `view-validation`, `compute_sudo`

---

## Problem

1. **Exam Officer Sees Zero Courses/Batches:** A standalone Exam Officer granted `openeducat_exam.group_op_exam_admin` opens `Exam Sessions -> New`, and the `Course` / `Batch` dropdowns return `0` matches for courses taught by other instructors.
2. **Coordinator / Trainer `AccessError` Opening `op.batch`:** Non-sales staff (`group_ghtc_coordinator` or `group_ghtc_trainer`) opening `op.batch` crash with:
   ```text
   AccessError: You are not allowed to access 'Sales Order' (sale.order) records.
   ```
3. **Odoo 17 Strict View Validator Crash When Restricting `sale_order_id`:** Adding `groups="..."` to `sale_order_id` causes module load to fail if any `<button invisible="sale_order_id"/>` lacks the exact same `groups="..."`:
   ```text
   ParseError: Field 'sale_order_id' used in modifier 'invisible' (sale_order_id) is restricted to the group(s) ...
   ```

## Root Cause

- Upstream `openeducat_exam/security/op_security.xml` declares `<field name="implied_ids" eval="[(4, ref('openeducat_core.group_op_faculty'))]"/>` on `group_op_exam_admin`. Therefore, any custom `ir.rule` restricting `group_op_faculty` to `('faculty_id.user_id', '=', user.id)` automatically applies to Exam Officers unless an overriding `[(1, '=', 1)]` group rule is also bound to `group_op_exam_admin` (group-scoped `ir.rule`s are OR'd in Odoo).
- OWL `web_read` resolves `display_name` on every visible `Many2one` field in a form view (`sale_order_id`) and triggers non-`compute_sudo` badge computes (`_compute_invoice_count` / `_compute_expense_count`).
- Odoo 17+ validates at XML load time that any field restricted by `groups=` cannot be referenced in `invisible=` / `readonly=` / `required=` expressions of unrestricted sibling elements.

## Solution ✅

1. **Include `group_op_exam_admin` & `group_op_attendance_manager` on the `[(1, '=', 1)]` course/batch `ir.rule`s** so Odoo ORs them with the faculty rule:

```xml
<record id="rule_op_course_admin" model="ir.rule">
    <field name="name">Admin &amp; Exam Officer All Courses Rule</field>
    <field name="model_id" ref="openeducat_core.model_op_course"/>
    <field name="groups" eval="[
        (4, ref('openeducat_core.group_op_back_office_admin')),
        (4, ref('openeducat_exam.group_op_exam_admin')),
        (4, ref('openeducat_attendance.group_op_attendance_manager'))
    ]"/>
    <field name="domain_force">[(1, '=', 1)]</field>
</record>
```

2. **Restrict `sale_order_id` consistently on the Python field, XML `<field>`, AND every `<button invisible="sale_order_id">`, grant read-only ACL/rule to Coordinators, and use `compute_sudo=True` / `.sudo()` for cross-module count badges:**

```python
sale_order_id = fields.Many2one(
    'sale.order',
    groups="sales_team.group_sale_salesman,openeducat_ghtc.group_ghtc_coordinator,openeducat_ghtc.group_ghtc_accountant,openeducat_ghtc.group_ghtc_ceo",
)
```

## ⚠️ Pitfalls

- **Never test RBAC only with `admin`:** Superuser and `base.user_admin` hold `sales_team.group_sale_manager` and `group_op_back_office_admin`, masking both `group_op_faculty` implied-group traps and `sale.order` `web_read` crashes. Always test with single-role `res.users` (`su=False`) in both Python unit tests and Playwright browser contexts.
- **Consistent `compute_sudo=True` across shared compute methods:** Every stored field computed by the same method (e.g. `trainer_fee`, `net_profit`, `profit_margin_pct` on `_compute_financials`) must set `compute_sudo=True` consistently.

## Verification

```bash
python3 tests_e2e/run_e2e.py --tier 2 --port 9998 --gevent-port 8718
```

## References

- Related file: `views/owl-form-button-silently-blocked-by-inherited-required-and-m2m-default-ints.md`
