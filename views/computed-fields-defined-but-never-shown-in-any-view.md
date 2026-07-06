# Computed Fields Defined in Model but Never Surfaced in Any View (Silent UI Gap)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `computed-fields`, `ui-gap`, `qa-checklist`, `documentation`, `evm`

---

## Problem

A model defines a family of computed KPI fields (in our case the full EVM set on
`construction.project`: `planned_value`, `earned_value`, `spi`, `cpi`, `eac`, `etc`, `vac`),
the compute method is correct, help strings are written, and even a code comment says
"They are shown on the form" — but **no view anywhere references the fields**. The fields
silently exist only in the ORM. There is no error, no log, nothing fails: users (and demo
videos, and user guides) just can't see the numbers the module advertises.

Discovered while preparing a client demo: the sales deck and user guide promised
"SPI/CPI live on the Financial Summary tab" — the tab didn't show them. Only one field
(`cpi`) was reachable, indirectly, through an OWL dashboard chart via `search_read`.

## Root Cause

Fields and views live in different files and there is no static check linking them.
When a feature is developed model-first (fields + compute + tests), adding the fields to
the form view is a separate manual step that is easy to forget — and nothing in Odoo
warns about a field that is never displayed. Documentation then gets written from the
model code (which looks complete), hiding the gap further.

## Solution ✅

1. Add the missing fields to the form view where the docs promise them (we added an
   "Earned Value (EVM)" + "Forecast at Completion" pair of groups on the project form's
   Financial Summary page, with red/green `decoration-danger` / `decoration-success` on
   SPI/CPI/VAC, consistent with the sibling groups).
2. Update `i18n/ar.po` with the new group labels and field labels.
3. Upgrade the module: `odoo-bin -u construction_project -d <db> --stop-after-init`.

Quick audit command to find this class of gap in any module — model fields never
referenced by any XML in the module:

```bash
for f in $(grep -hoE "^\s+([a-z_0-9]+) = fields\." mymodule/models/*.py | awk '{print $1}'); do
  grep -rqs "\"$f\"\|'$f'" mymodule/views/ || echo "NOT IN ANY VIEW: $f"
done
```

(Expect false positives for purely technical fields — but every KPI/monetary field in the
output deserves a look.)

## ⚠️ Pitfalls

- **Non-stored computed fields are invisible in list/pivot by default tooling** — they can
  only be shown on forms or fetched via `search_read`; do not promise them in pivots.
- **Docs written from model code inherit the gap**: always verify screenshots/menu paths
  against a running instance (or at least against the view XML), not against `fields.*`
  definitions.
- **`decoration-*` on form fields**: works in Odoo 17 form views; keep it consistent with
  the module's existing usage instead of inventing a new pattern.
- Field named `etc` is a valid field name but shadows nothing — still, grep for the exact
  name with word boundaries when auditing (`\betc\b`) to avoid noise.
