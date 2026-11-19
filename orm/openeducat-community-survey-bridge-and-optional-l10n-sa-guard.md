# Bridging OpenEduCat Quiz Sync to Community `survey` and Guarding Optional `l10n_sa` Dependencies

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `openeducat`, `survey`, `l10n_sa`, `community-purity`, `decoupling`, `enterprise-removal`

---

## Problem

> Custom OpenEduCat extension modules often hard-depend on Enterprise/commercial addons (`openeducat_lms`, `openeducat_quiz`) and regional localizations (`l10n_sa`, `l10n_gcc_invoice`). On pure Odoo Community or multi-country deployments, installation fails with missing module / missing field errors:

```
odoo.modules.loading: Some modules have unmet dependencies: openeducat_lms, openeducat_quiz, l10n_sa
KeyError: 'l10n_sa_confirmation_datetime'
ValueError: Model not found: op.quiz.result
```

## Root Cause

1. `openeducat_quiz` / `openeducat_lms` are not part of pure Community OpenEduCat, whereas Odoo's standard `survey` module provides scored assessments (`survey.survey`, `survey.user_input`).
2. `l10n_sa` is a country-specific fiscal localization; hardcoding `l10n_sa` in `depends`, referencing `l10n_sa_confirmation_datetime` unconditionally in `account.move._post()`, or forcing `l10n_sa` tax/company records in `data/` blocks non-SA companies and pure Community installs without `l10n_sa` installed.

## Solution ✅

### 1. Replace `openeducat_lms` / `openeducat_quiz` with Community `survey`
- Replace `'openeducat_lms'` in `__manifest__.py` `depends` with `'survey'`.
- Add `survey_id = fields.Many2one('survey.survey', domain="[('scoring_type', '!=', 'no_scoring')]")` on `op.course` and `op.batch` (with batch overriding course).
- Inherit `survey.user_input` and hook `create()`/`write()` when `state == 'done'` (excluding `test_entry=True` and `scoring_type == 'no_scoring'`):

```python
class SurveyUserInputGHTC(models.Model):
    _inherit = 'survey.user_input'

    def _sync_survey_score_to_enrollment(self, target_batches=None):
        done_inputs = self.filtered(
            lambda r: r.state == 'done' and not r.test_entry
            and r.survey_id and r.survey_id.scoring_type != 'no_scoring'
        )
        for user_input in done_inputs:
            # Resolve op.student via partner_id or case-insensitive email fallback
            # Match op.student.course by batch_id.survey_id or (not batch_id.survey_id and course_id.survey_id)
            pct = round(user_input.scoring_percentage or 0.0, 2)
            for enr in enrollments:
                min_pass = enr.course_id.min_passing_marks if enr.course_id else 70.0
                passed = bool(user_input.scoring_success) and (pct >= min_pass)
                enr.write({'marks': pct, 'exam_status': 'pass' if passed else 'fail'})
```

### 2. Guard Optional `l10n_sa` References in `account.move`
- Remove `l10n_sa` / `l10n_gcc_invoice` from `depends`.
- Guard `l10n_sa_confirmation_datetime` dynamically in `account.move._post()`:

```python
for move in self:
    if (
        'l10n_sa_confirmation_datetime' in move._fields
        and move.is_sale_document()
        and move.company_id.country_id.code == 'SA'
        and not move.l10n_sa_confirmation_datetime
    ):
        inv_date = move.invoice_date or today
        move.l10n_sa_confirmation_datetime = datetime.combine(
            inv_date, fields.Datetime.now().time()
        )
```

## ⚠️ Pitfalls

- **Inherited `required=True` on Core Models vs `at_install` Tests:** When a downstream module adds `required=True` (without SQL default) on an upstream core model (`op.faculty`, `op.student.course`), Odoo creates a PostgreSQL `NOT NULL` constraint. On any DB where the downstream module is already installed, running upstream `at_install` tests (`TestCore`, `TestAdmission`) fails with `psycopg2.errors.NotNullViolation` because core `at_install` tests execute before the downstream module's Python defaults are loaded into the registry.
- **Uninstalling Legacy Modules Before Archiving:** Always uninstall unwanted/conflicting modules via Odoo (`button_immediate_uninstall`) BEFORE moving their folders out of `addons_path`, otherwise stale `ir_module_module` rows trigger `not installable, skipped` warnings on every boot.
- **Demo-Dependent Unit Tests on `--without-demo=all` DBs:** Third-party OCA modules like `report_xlsx` include unit tests targeting demo XML IDs (`report_xlsx.partner_xlsx`), which fail on production/no-demo DB clones unless filtered with `--test-tags`.

## Verification

```bash
# 1. Verify fresh no-demo install & tests
odoo-bin -c openedu.conf -d test_nodemo -i openeducat_ghtc --without-demo=all --test-enable --test-tags /openeducat_ghtc --stop-after-init

# 2. Verify cloned DB tests
createdb -O odoo -T acad2 acad2_test
odoo-bin -c openedu.conf -d acad2_test --test-enable --test-tags /openeducat_ghtc --stop-after-init
```

## References

- Related file: `setup/leftover-module-not-installable-skipped-cleanup.md`
- Related file: `backend/l10n-sa-zatca-qr-empty-on-existing-company-fiscal-country.md`
