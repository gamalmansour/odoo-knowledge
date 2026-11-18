# OpenEduCat Public Forms: `group_public` ACL Leaks Every Record, and `op.admission` NOT NULL Fields Crash the Form

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 17 (OpenEduCat 17.0; same pattern 15–18)   |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `ir.model.access`, `group_public`, `group_portal`, `openeducat`, `op.admission`, `public-form`, `pdpl`, `superuser-tests`

---

## Problem

A custom module that adds a public self-registration form (`auth='public'`) plus a certificate verification page gave itself ACL lines so the pages "would work":

```
access_x_op_student_course_public,...,base.group_public,1,0,0,0
access_x_op_admission_public,...,base.group_public,1,1,1,0
access_x_op_admission_portal,...,base.group_portal,1,1,1,0
```

A live probe on a non-superuser env showed:

```
portal_reads_enrollments  => 43 / 43      # every trainee certificate, marks, photo
portal_reads_admissions   => 29           # incl. national_id of everyone
public_register_create    => NotNullViolation: null value in column "gender" of relation "op_admission"
```

The full test suite was green for these paths.

## Root Cause

1. **ACL without `ir.rule` is global.** A read line for `group_public`/`group_portal` with no record rule means *all* records via JSON-RPC (`/web/dataset/call_kw`) for any portal user. The controllers already used `sudo()`, so the ACL lines added zero functionality and 100% exposure.
2. **`openeducat_admission` declares `email` and `gender` as `required=True`** (DB NOT NULL). A public form that omits gender raises a 500 on every submit.
3. **`TransactionCase` runs as superuser (`env.su=True`)** → ACL gaps and missing-ACL models (`no access rules` warning) never fail in tests. See also `backend/env-su-guard-silently-passes-in-transactioncase.md`.

## Solution ✅

```csv
# REMOVE all base.group_public lines for business models.
# Portal: read-only AND paired with an ir.rule
access_x_op_student_course_portal,...,base.group_portal,1,0,0,0
```

```xml
<record id="rule_student_course_portal_own" model="ir.rule">
    <field name="model_id" ref="openeducat_core.model_op_student_course"/>
    <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
    <field name="domain_force">[('student_id.partner_id', '=', user.partner_id.id)]</field>
</record>
```

- Public controllers: keep `sudo()` but whitelist fields written, and always send `gender` (form field or a flagged default).
- Public verification pages: put a random `verification_token` (UUID) in the QR, not a sequential serial; mask national IDs; never search by national ID publicly.
- Thank-you pages: use `access_token`, never `?ref=<id>` (IDOR).
- Add at least one test per public path run as `self.env(user=portal_user)` / `public_user` with `su=False`.

## ⚠️ Pitfalls

- `--test-tags /my_module` still imports tests of *all* installed modules at post_install; OpenEduCat 17 `openeducat_quiz/tests/test_quiz_common.py` has a broken `from ..controllers import onboard` that aborts the whole run. Workaround: install first, then run `--test-file=<path>` per file.
- Models listed in `models/__init__.py` but missing from `ir.model.access.csv` block even `base.user_admin` (non-superuser) — any flow that `create()`s them (e.g. `sale.order.action_confirm`) raises AccessError in production only.

## References

- Odoo 17 security docs: access rights & record rules.
- Saudi PDPL — national ID & photo are personal data.
