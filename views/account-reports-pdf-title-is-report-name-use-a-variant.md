# Accounting Report PDF Title Is Literally `report.name` — Add a Variant, Don't Override the Renderer

| Field         | Value                       |
|---------------|-----------------------------|
| Category      | views                       |
| Odoo Versions | 16, 17, 18 (Enterprise)     |
| Severity      | 🟡 Medium                   |
| Last Verified | 2026-08-11                  |
| Author        | Gamal Mansour               |

**Tags:** `account_reports`, `enterprise`, `pdf`, `report_title`, `variant`, `root_report_id`, `partner-ledger`, `customer-statement`, `config-not-code`

---

## Problem

A client asks for the header of a printed accounting report to change with a
filter — "when I pick Receivable print CUSTOMER STATEMENT, when I pick Payable
print VENDOR STATEMENT".

It reads like custom development: find where the title is rendered, override it,
branch on `options`. That is the wrong instinct twice over, and there is a second
trap sitting in front of it.

**Trap 1 — you are probably not on the report you think you are.**
In `account_reports`, several reports are **variants** of one root report and are
selected from a dropdown at the top of the same screen. They share one
`ir.actions.client`. So the action id, the menu, and the user's description all
say "Partner Ledger" while the thing actually printing is a different
`account.report` record with different columns, a different PDF template and a
different title.

Real example (Odoo 18 Enterprise, out of the box):

| id | Report            | `root_report_id` | PDF template                                    |
|----|-------------------|------------------|-------------------------------------------------|
| 14 | Partner Ledger    | —                | `account_reports.pdf_export_main`                |
| 15 | Customer Statement| **14**           | `account_reports.pdf_export_main_customer_report`|
| 16 | Follow-Up Report  | **14**           | —                                                |

Patch report 14 because the action said "Partner Ledger" and the user sees no
change at all.

**Trap 2 — the title is not computed, it is the record's name.**

```python
# enterprise/account_reports/models/account_report.py  (18.0, ~line 5897)
def _get_pdf_export_html(self, options, lines, additional_context=None, template=None):
    render_values = {
        'report': self,
        'report_title': self.name,      # <-- that is the whole mechanism
        ...
```

There is no hook tying the title to any filter, because the title was never meant
to vary — a report has one name.

## Root Cause

`account.report` is **data**, not code. A "report" is a record carrying its name,
its columns, its filters and its handler. `report_title` is just that record's
`name` rendered into the `o_title` div.

So "I want a different title under a different filter" is not a rendering problem.
It is the statement *"this is a different report"* — and the framework already has
a first-class way to say that: a **variant**.

## Solution ✅

Create a variant record instead of touching Python. Copy the report you actually
print, rename it, and pin its filter:

```python
# odoo shell — wrap in a transaction and roll back while you are still testing
src = env['account.report'].browse(15)        # Customer Statement
new = src.copy()
new.write({'name': 'Vendor Statement', 'filter_account_type': 'payable'})
```

The variant inherits from the source and needs no further setup:

- same `root_report_id` → it appears in the **same dropdown**, beside the original
- same `custom_handler_model_id` → **same PDF template and same visual layout**
- `column_ids` are carried over by `copy()`
- `report_title` is now `'Vendor Statement'`, because the title is the name

`filter_account_type` accepts `receivable` / `payable` / `both` / `disabled` and
pre-selects the matching options in `options['account_type']`
(`_init_options_account_type`, `account_report.py`).

**This is reachable from the UI** — `account.report` has a form view
(`account_reports.account_report_form`), `filter_account_type` and `root_report_id`
are both editable on it, and it lives under the *Accounting Reports* menu. So on
most projects this is **configuration, not development**: no module, no Python,
no upgrade debt.

**Verify by executing, then roll back:**

```python
opts = new.get_options({})
opts['export_mode'] = 'print'
html = new._get_pdf_export_html(opts, [])
# assert the o_title div now contains 'Vendor Statement'
print(len(new.with_company(company)._get_lines(new.with_company(company).get_options({}))))
env.cr.rollback()          # nothing persisted
```

## ⚠️ Pitfalls

- **Identify the printing report before writing a line.** Render both candidates
  and compare — `_get_pdf_export_html` needs no wkhtmltopdf, so this costs seconds:
  `re.search(r"o_title[^>]*>\s*(.*?)</div>", html, re.S)`. Layout tells you too:
  `pdf_export_main_customer_report` centers the title and drops the logo, plain
  `pdf_export_main` does not.
- **`copy()` forces `'<name> (copy)'` and silently ignores a `name` passed in its
  vals.** Always `write({'name': ...})` afterwards, then re-read it.
- **The title is uppercased by CSS**, not by code
  (`static/src/scss/account_pdf_export_template.scss`, `text-transform: uppercase`).
  Never write the string in caps — it double-applies and breaks other languages.
- **Overriding `_get_pdf_export_html` is a shared blast radius.** It serves *every*
  accounting report — Balance Sheet, P&L, tax reports. If you truly must override
  it, scope it to the specific reports and add explicit tests that unrelated report
  titles are unchanged.
- **A variant does not remove handler-added buttons.** They are appended in Python
  inside `_custom_options_initializer` on every options build, so no field or
  setting drops them. On the Customer Statement handler that means the **Send**
  button follows your new vendor report — verified, `['PDF','XLSX','Send']`. A
  variant *isolates* the concern so a later fix is clean; it does not fix it.
- **Read the mail template body before rating that as a risk.** The template named
  `Customer Statement` has a fully neutral subject and body ("the statement of your
  account") and reads fine for a vendor; only the sender resolution
  (`_get_followup_responsible()`) is customer-collections specific. Judging it by
  its *name* overstates the severity.

## Verification

Verified on Odoo 18.0 Enterprise, `account_reports` 18.0, against a 568 MB
production copy — created inside a transaction and rolled back:

- title rendered `'Vendor Statement'` ✅
- appeared in the variant dropdown next to Partner Ledger / Customer Statement /
  Follow-Up Report ✅
- `options['account_type']` reduced to Payable + Non Trade Payable, Payable
  selected ✅
- returned 87 real vendor lines ✅
- PDF template identical to the source report ✅
- `SELECT` after `rollback()` confirmed zero leftover records ✅
