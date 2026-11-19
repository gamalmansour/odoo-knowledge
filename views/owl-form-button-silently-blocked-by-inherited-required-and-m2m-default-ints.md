# OWL Form Buttons Silently Blocked by Inherited `required="1"` Fields & Raw-Int `Many2many` Wizard Defaults

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `owl`, `views`, `form-controller`, `required`, `many2many`, `transientmodel`, `playwright`, `openeducat`

---

## Problem

1. **Silent OWL Header Button Abort (`beforeExecuteActionButton`):** Backend Python tests (`record.action_approve_enrollment()`, `record.action_open_revoke_wizard()`) pass 100%, yet clicking the exact same `<button type="object">` or `<button type="action">` in the real Odoo 17+ OWL Form UI either does nothing at all (sending zero `/web/dataset/call_button` RPCs) or flashes an invalid field indicator — especially when records were created headlessly (public registration form, webhook, or automated batch sync).
2. **Modal Wizard `onchange` Crash on `Many2many` Raw-Int `default`:** A `TransientModel` wizard defines `enrollment_ids = fields.Many2many(..., default=lambda self: self.env.context.get('active_ids', []))`. Backend `Wizard.with_context(active_ids=...).create(...)` passes, but opening the modal in OWL (`target='new'`) fails during initial `onchange({}, [], spec)` because `default_get` receives raw `int` IDs `[15]` instead of `[Command.set([15])]`.

```text
ValueError: Invalid command: 15
```

## Root Cause

- In Odoo 17+ `FormController.beforeExecuteActionButton()` (`addons/web/static/src/views/form/form_controller.js`), **every** non-cancel form button triggers `await record.save(params)`, which runs client-side `record.checkValidity()` across all fields present in the composed XML view — even if the record is clean (`isDirty === false`) or the field was injected by a third-party inherited view (e.g., `openeducat_admission` injecting `<field name="product_id" required="1"/>` onto `op.student.course`, or `<field name="fees_term_id" required="1" readonly="state not in ('draft','submit','confirm')"/>` onto `op.admission`). Worse: when an empty field is simultaneously `required="1"` and `readonly="1"` (or hidden inside an inactive notebook tab), the user cannot even fill it in the UI.
- When OWL opens a modal form (`target='new'`), it does **not** call `create()` immediately; it calls `onchange({}, [], field_spec)`, which invokes `default_get()`. Unlike `create()`, `onchange` requires `Many2many` defaults to be `[Command.set(ids)]` (or a recordset), and header `<button>` context may supply `active_id` without `active_ids`.

## Solution ✅

1. **Audit all inherited XML views for `required="1"` when adapting vertical suites (e.g., K-12 OpenEduCat -> B2B Corporate Training)** and relax non-applicable view-level `required` attributes with a higher `priority` inheritance:

```xml
<record id="view_op_student_course_form_corporate" model="ir.ui.view">
    <field name="name">op.student.course.form.corporate</field>
    <field name="model">op.student.course</field>
    <field name="inherit_id" ref="openeducat_admission.view_op_student_course_form_admission_inherit"/>
    <field name="priority" eval="20"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='product_id']" position="attributes">
            <attribute name="required">0</attribute>
        </xpath>
    </field>
</record>
```

2. **Always return `[Command.set(...)]` in `Many2many` `default` methods and support both `active_ids` and `active_id`:**

```python
from odoo import Command, api, fields, models


class CertificateRevokeWizard(models.TransientModel):
    _name = 'training.certificate.revoke.wizard'
    _description = 'Revoke Training Certificate'

    @api.model
    def _default_enrollment_ids(self) -> list:
        active_ids = self.env.context.get('active_ids')
        if not active_ids and self.env.context.get('active_id'):
            active_ids = [self.env.context['active_id']]
        return [Command.set(active_ids or [])]

    enrollment_ids = fields.Many2many(
        'op.student.course',
        string='Certificates',
        default=_default_enrollment_ids,
    )
```

## ⚠️ Pitfalls

- **Backend ORM unit tests bypass XML `required="1"` completely:** Calling `record.action_foo()` in Python `TransactionCase` never runs `FormController.beforeExecuteActionButton()`. Always pair ORM tests with Playwright UI clicks and assert `.o_field_widget.o_field_invalid` count is `0`.
- **Test wizard `onchange({}, [], spec)` in unit tests too:** Calling `Wizard.with_context(active_id=rec.id, active_ids=rec.ids).onchange({}, [], spec)` catches raw-int `Many2many` defaults even in fast backend unit tests.
- **Never use `wait_for_load_state("networkidle")` on logged-in Odoo 17+ `/web` pages in Playwright:** Odoo's persistent `/websocket` bus connection prevents `networkidle` from ever resolving; instead synchronize button clicks with `page.expect_response(lambda r: "/web/dataset/call_button" in r.url or "web_save" in r.url)`.

## Verification

```bash
grep -rn 'required="1"\|required="True"' custom_addons/*/views/
# And run Tier 2 Playwright Chromium UI suite:
python3 tests_e2e/run_e2e.py --tier 2 --port 9998 --gevent-port 8718
```

## References

- Odoo 17 Core: `addons/web/static/src/views/form/form_controller.js` (`beforeExecuteActionButton`)
- Related file: `orm/res-config-settings-default-prefix-crashes-default-get-without-default-model.md`
