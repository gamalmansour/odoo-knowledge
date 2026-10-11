# Multi-Market Jurisdiction Switching & Localization Decoupling (Saudi / Egypt / Global)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-10-02                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `localization`, `multi-market`, `construction`, `egypt`, `saudi`, `fidic`, `demo-data`, `res_company`, `res_config_settings`

---

## Problem

When a specialized vertical solution (e.g. Construction / Real Estate Management) contains extensive jurisdiction-specific statutory compliance (such as Saudi Etimad tendering, GTPL Art 75 release gates, Wafi Escrow, Nitaqat/Saudization, ZATCA RETT, Saudi Building Code SBC), deploying the system for clients in another country (such as **Egypt** or international FIDIC contracts) creates critical usability and data integrity problems:
1. **View Pollution:** Irrelevant statutory tabs, fields, badges, and validation alerts (e.g. "Etimad Reference missing", "Saudization rate", "Wafi Escrow account") are displayed on everyday forms.
2. **Workflow Blockers:** Hardcoded national validation constraints (e.g. 10-digit Saudi National ID/Iqama, Saudi Civil Defense clearances) prevent users in other countries from saving or confirming records.
3. **Demo Data Contamination:** Demo data packages seeded with Saudi Riyals (SAR), Saudi government bodies (Balady, MOMRAH, Etimad), and Saudi contractors mix with local currency (EGP, USD) and local projects, confusing stakeholders during pre-sales demonstrations.

## Root Cause

Statutory features and compliance rules were tightly coupled directly into core vertical models without a centralized jurisdiction / market configuration switch on `res.company`. Furthermore, demo data files were hardcoded in manifests without market separation.

## Solution ✅

Implement a 4-tier decoupled localization architecture:

### 1. Centralized Market Configuration on `res.company` and Settings

In `res.company` and `res.config.settings`, define `construction_market` with stored boolean flags:

```python
# models/res_company.py
construction_market = fields.Selection([
    ('global', 'International / FIDIC Standard (عالمي / فيديك)'),
    ('sa', 'Kingdom of Saudi Arabia - GTPL & Wafi (المملكة العربية السعودية)'),
    ('eg', 'Arab Republic of Egypt - Egyptian Code (جمهورية مصر العربية)'),
], string='Regional Market & Compliance Framework', default='global', required=True)

is_saudi_market = fields.Boolean(compute='_compute_market_flags', store=True)
is_egypt_market = fields.Boolean(compute='_compute_market_flags', store=True)

@api.depends('construction_market')
def _compute_market_flags(self):
    for rec in self:
        rec.is_saudi_market = (rec.construction_market == 'sa')
        rec.is_egypt_market = (rec.construction_market == 'eg')
```

Expose this in Settings under Construction Management with a radio widget and an action button to seed market-specific demo data on demand.

### 2. Market-Aware Related Fields and View Conditions

Expose `is_saudi_market` and `is_egypt_market` as related fields on operational models (`tender.opportunity`, `contract.progress.invoice`, `construction.labor.sheet`, `construction.bank.guarantee`, `dlp.warranty`, `realestate.unit`):

```python
is_saudi_market = fields.Boolean(related='company_id.is_saudi_market', string='Is Saudi Market', readonly=True)
is_egypt_market = fields.Boolean(related='company_id.is_egypt_market', string='Is Egyptian Market', readonly=True)
```

In XML views, wrap jurisdiction-specific fields and notebook pages with `invisible="not is_saudi_market"`:

```xml
<field name="is_saudi_market" invisible="1"/>
<group string="Saudi Statutory Final Handover &amp; Safety Gates" invisible="not is_saudi_market">
    <field name="is_final_handover_signed" widget="boolean_toggle"/>
    <field name="civil_defense_final_clearance" widget="boolean_toggle"/>
</group>
```

### 3. Guard Clauses in Python Constraints

Condition jurisdiction-specific constraints so they only execute when the company operates in that market:

```python
@api.constrains('national_id_number')
def _check_national_id(self):
    for rec in self:
        # Only enforce Saudi 10-digit ID rules if operating in Saudi market
        if rec.sheet_id.is_saudi_market and rec.national_id_number:
            if not re.match(r'^[12]\d{9}$', rec.national_id_number):
                raise ValidationError(_("Saudi National ID or Iqama must be exactly 10 digits..."))
```

### 4. Decoupled Market Demo Seeders

Create isolated, standalone demo seeders (e.g. `seed_egypt_hadhoud.py` for Egypt, `seed_saudi_demo.py` for Saudi Arabia). Never bundle contradictory regional demo records in `__manifest__.py['demo']`. Load them programmatically via a Settings button (`action_load_market_demo_data`) or via shell.

---

## ⚠️ Pitfalls

1. **Manifest Menu Load Order:** When submodules or views reference a parent menu (e.g. `menu_realestate_root`), ensure the menu item is declared in an early data file (`views/realestate_menus.xml`) listed before dependent views in `__manifest__.py`. Otherwise, installation fails with `External ID not found: menu_realestate_root`.
2. **Currency Pre-Initialization:** Always set the company country (`base.eg` / `base.sa`) and active currency (`EGP` / `SAR`) BEFORE installing accounting or seeding demo data to avoid chart-of-accounts and currency mismatches.
3. **XML Balancing:** Always run an automated XML validation script across all view files before bulk installation:
   ```bash
   python3 -c "import xml.etree.ElementTree as ET, glob; [ET.parse(f) for f in glob.glob('**/*.xml', recursive=True)]"
   ```

## Verification

1. Set `company.construction_market = 'eg'` in Odoo shell.
2. Confirm `company.is_saudi_market == False` and `company.is_egypt_market == True`.
3. Open Daily Labor Sheet form: verify Saudization rate progress bar and Nitaqat badges are completely hidden.
4. Open Owner Progress Invoice (IPC): verify Etimad compliance page and Saudi Public Works print buttons are hidden.
5. Verify projects, contracts, and tenders are 100% denominated in local currency (e.g. EGP).

## References

- Related: `Best Practices/saudi-construction-labor-saudization-and-sbc-ptw.md`
- Related: `Best Practices/saudi-public-works-etimad-ipc-governance.md`
- Related: `setup/csrf-session-conflict-multi-instance.md`
