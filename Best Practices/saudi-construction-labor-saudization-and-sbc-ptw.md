# Saudi Construction Labor Saudization & SBC Civil Defense PTW Compliance

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-arabia`, `saudization`, `nitaqat`, `qiwa`, `sbc`, `civil-defense`, `ptw`, `construction-labor`, `hse`

---

## Problem

Construction companies executing projects in Saudi Arabia face severe regulatory penalties, project shutdowns, and immediate stop-work orders if:
1. **Labor & Saudization Violations**:
   - Total site labor drops below statutory Nitaqat localization thresholds (e.g. Red / Low Green tier blocks Ministry of Human Resources / Qiwa visas and Etimad public sector milestone payments).
   - Engineering professions violate the mandatory 25% Saudization quota under Saudi Council of Engineers regulations.
   - Workers on site possess invalid or forged Saudi National IDs or Iqamas (e.g. non-10-digit IDs or Arabic-Indic unicode numerals accepted by naive `\d` regex, causing government portal rejections).
2. **Safety & Civil Defense Violations (SBC 201 / 801)**:
   - Hot work (welding, cutting) executed without a dedicated certified Fire Watcher, without verified on-site suppression equipment, without an 11-meter combustible clearance, or with post-work watch duration under the mandatory 60-minute continuous observation period (SBC 801 Chapter 35).
   - Working at height conducted on condemned or uninspected scaffolding (RED tag), or without verified 100% harness tie-off, causing fatal fall risks and Civil Defense / Salamah sanctions.
   - Deep excavations (>1.2m) commenced without underground utility clearances (SEC, NWC, Telecom) or without certified shoring / sloping (SBC 201).

---

## Root Cause

Generic construction ERP implementations treat daily labor logs and safety permits as passive informational forms rather than active legal and regulatory gates:
- Labor attendance sheets track raw headcounts without segregating Saudi citizens vs expatriate residents, computing live Saudization percentages, or warning site management when falling below Nitaqat thresholds.
- Permits to work allow site supervisors to bypass critical safety controls (like fire watch duration or scaffolding inspection tags) under pressure to meet tight project deadlines.

---

## Solution ✅

Implement automated Saudi regulatory compliance engines across both `construction_labor` and `construction_hse`:

### 1. Labor Saudization & Qiwa Engine (`construction.labor.sheet`)
- Compute live Saudization and Engineering Saudization percentages:
  $$\text{Saudization Rate} = \frac{\text{Saudi Workers}}{\text{Total Workers}} \times 100$$
- Classify Nitaqat Tiers dynamically:
  - **Platinum**: $\ge 30\%$
  - **High Green**: $20\% \le \text{Rate} < 30\%$
  - **Mid Green**: $12\% \le \text{Rate} < 20\%$
  - **Low Green**: $6\% \le \text{Rate} < 12\%$
  - **Red**: $< 6\%$
- Enforce strict ASCII regex validation on National IDs / Iqamas (preventing Arabic-Indic digits per KB entry 45):
  - Saudi Citizens: 10 ASCII digits starting with `1`.
  - Expatriate Residents (Iqama): 10 ASCII digits starting with `2`.

```python
@api.constrains('national_id_number')
def _check_national_id_number(self):
    saudi_id_regex = re.compile(r'^[12][0-9]{9}$')
    for rec in self:
        if rec.national_id_number and not saudi_id_regex.match(rec.national_id_number):
            raise ValidationError(
                _("Invalid Saudi National ID or Iqama number. Must be exactly 10 ASCII digits starting with 1 (Citizen) or 2 (Expat).")
            )
```

### 2. Saudi Building Code (SBC 201/801) & Civil Defense PTW Gates (`hse.permit`)
- **SBC 801 Fire Prevention Gate**:
  - Requires certified fire watcher name and certification number.
  - Enforces minimum 60-minute post-work continuous fire watch (`post_work_fire_watch_minutes >= 60`).
  - Verifies 11-meter flammable clearance and fire extinguishers on-site.
- **Scaffolding Tag & Fall Protection Gate**:
  - Blocks submission if scaffolding is tagged `red` (Danger / Do Not Use).
  - Enforces 100% tie-off harness verification.
- **SBC 201 Excavation Gate**:
  - Enforces underground utility clearance and shoring / sloping installation.

---

## ⚠️ Pitfalls

1. **`\d` vs `[0-9]` in Regex**:
   Never use `^\d{10}$` for National IDs or Iqamas. Python's `re` matches Arabic-Indic digits (١٢٣...) with `\d`. Always use `^[12][0-9]{9}$`.
2. **Fire Watch Bypass**:
   Supervisors often attempt to set `post_work_fire_watch_minutes` to 0 or 15 mins to close permits before shift end. SBC 801 mandates 60 minutes minimum; enforce this at the model level in `action_submit()`.
3. **Scaffolding Inspection Expiry**:
   Scaffolding tags must be re-inspected after adverse weather (e.g. sandstorms or rain common in KSA) or every 7 days. Ensure red tags strictly abort permit activation.

---

## Verification

1. Run automated unit tests in `construction_labor`:
   ```bash
   python3 -m unittest test_labor_sheet.TestLaborSheet.test_07_saudization_and_nitaqat_computation
   python3 -m unittest test_labor_sheet.TestLaborSheet.test_08_saudi_national_id_validation
   ```
2. Verify Python syntax and XML view compilation:
   ```bash
   python3 -m py_compile models/hse_permit.py
   ```

---

## References

- Saudi Building Code (SBC 201 - Building Construction & Geotechnical)
- Saudi Building Code (SBC 801 - Saudi Fire Code)
- Saudi Ministry of Human Resources & Social Development (MHRSD) Nitaqat & Qiwa Regulations
- Related files:
  - `construction_labor/models/labor_sheet.py`
  - `construction_hse/models/hse_permit.py`
  - `Best Practices/saudi-public-works-etimad-ipc-governance.md`
