# Country-Specific Business Rules Must Be Per-Company Fields, Not `ir.config_parameter`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-26                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `multi-company`, `ir.config_parameter`, `res.company`, `res.config.settings`, `payroll`, `gratuity`, `snapshot`, `money`, `migration`

---

## Problem

> A business rule that differs **by country** is stored in `ir.config_parameter`.
> That table has **no `company_id` column at all**, so one set of numbers applies to
> every company in the database. In a multi-country group this is not a limitation —
> it is a wrong answer that cannot be corrected from the UI.

Real case (Solargy, Odoo 19): end-of-service gratuity settings stored as three
parameters, in a database holding **two Egyptian companies and one UAE company**.

```python
params = self.env['ir.config_parameter'].sudo()
tier_years = float(params.get_param('solargy_hr.gratuity_tier_years', 5))   # global!
days_first = float(params.get_param('solargy_hr.gratuity_days_first', 15))  # global!
```

Worse, the entitlement ladder was **hardcoded in Python** — the part that varies most
between jurisdictions was the only part that could not be configured at all:

```python
if years < 2.0:  return 0.0        # 57 of 63 employees fell in this bracket
if years < 5.0:  return 1.0 / 3.0
```

## Root Cause

`ir.config_parameter` is a global key/value store. `res.config.settings` fields declared
with `config_parameter=` write to it, so they look per-company in the UI (the settings
page has a company switcher) while being global in the database. The switcher is
misleading, not helpful.

## Solution ✅

**1. Fields on `res.company`, related on the settings.**

```python
class ResCompany(models.Model):
    _inherit = 'res.company'
    solargy_gratuity_days_first = fields.Float(default=15.0)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    solargy_gratuity_days_first = fields.Float(
        related='company_id.solargy_gratuity_days_first', readonly=False)  # NOT config_parameter
```

**2. Ladders / brackets become a One2many, not more scalar fields.** A fixed set of
thresholds bakes one country's shape into the schema. A bracket model
(`company_id`, `key`, `min_value`, `factor`) takes any jurisdiction without a code change.

Resolve it as a **step function**, and make the empty case pay in FULL:

```python
def _resolve_factor(self, ladder, years):
    factor, best = 1.0, None          # empty ladder -> 1.0, never 0.0
    for min_years, f in sorted(ladder or []):
        if years >= min_years and (best is None or min_years >= best):
            best, factor = min_years, f
    return factor
```

An unconfigured company must **overpay, not underpay**. A default of 0.0 silently
withholds a legal entitlement and nobody notices until someone sues.

**3. 🔴 Snapshot the rules onto the transaction record.** This is the step that is easy
to miss and expensive to omit.

Once the rules live on `res.company`, a stored compute that reads them live means that
**the day somebody corrects the configuration, every historical record recomputes**.
For a payout, that silently rewrites amounts already approved and paid.

Copy the rules onto the record at create time — exactly as you would snapshot a wage —
and add them to the locked-basis set:

```python
_LOCKED_BASIS_FIELDS = frozenset({
    'employee_id', 'last_wage', 'contract_start_date',
    'gratuity_tier_years', 'gratuity_days_first', 'gratuity_ladder_json',  # the RULES too
})

@api.depends('reason', 'service_years', 'gratuity_ladder_json')   # record-own only
def _compute_gratuity_factor(self): ...
```

Store the ladder as JSON in a technical `Char`. It doubles as an audit record of
*which rules produced this number*.

**4. Behaviour-neutral migration.** The upgrade must not move a single figure:

```python
def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].sudo().search([])
    companies.write(values_read_from_the_old_parameters)
    companies._seed_default_brackets()      # the ladder that WAS hardcoded
    params.search([('key', 'in', old_keys)]).unlink()   # retire the dead keys
```

Seeding is not optional: without it the hardcoded reduction silently disappears and
every record jumps to full entitlement. Also override `res.company.create` so a company
created next year is seeded too.

## ⚠️ Pitfalls

- **Retire the old parameters.** Leaving them is a trap: someone edits them later and
  nothing happens, because nothing reads them any more.
- **Seed before you switch.** The hardcoded default must become real data, or the
  upgrade is a silent policy change.
- **Guard the "no config" case toward overpayment**, not zero.
- **The settings page's company switcher lies** when the field is `config_parameter=`.
  Anyone testing per-company behaviour there will think it works.
- **Odoo 19: `_sql_constraints` is gone** — use `models.Constraint('UNIQUE(...)', 'msg')`
  as a class attribute. See `Best Practices/odoo-19-warnings.md` §1.
- **`fields.date_utils` does not exist.** Use `from datetime import timedelta` in tests.
- **Never state the law yourself.** Ship the *mechanism* and mark the numbers
  `[TO CONFIRM]`. Seed with whatever preserves existing behaviour, and let the client's
  legal advisor fill in the real values through the UI.

## Verification

```python
# 1. Two companies really do hold different values
company_a.solargy_gratuity_days_first = 15
company_b.solargy_gratuity_days_first = 30

# 2. THE test that matters: a confirmed record is immune to a config change
record.action_confirm()
frozen = record.amount
company_a.solargy_gratuity_days_first = 99
company_a.bracket_ids.unlink()
env.invalidate_all()
assert record.amount == frozen        # must not move

# 3. And a NEW record does pick up the new rules
```

Result on the real database: three companies migrated with **identical values**, so no
figure changed on upgrade; a confirmed settlement stayed at 12,435.76 EGP after Egypt's
rules were rewritten, while a new settlement for the same tenure and wage correctly
computed 74,622.00 EGP under the new ladder. 43 tests, 0 failures.

## Related

- `orm/stored-compute-incomplete-depends-silent-staleness.md` — the opposite failure: a stored figure that should move and doesn't
- `orm/money-flow-reversal-on-refund-cancel-reset-draft.md` — money figures across lifecycle stages
- `security/multi-company-record-rules.md` — the new bracket model needs an `ir.rule`
