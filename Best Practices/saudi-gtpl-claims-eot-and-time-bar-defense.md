# Saudi Public Works GTPL Claims, EOT & Statutory Time-Bar Defense

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-arabia`, `gtpl`, `claims`, `eot`, `time-bar`, `fidic`, `prolongation-costs`, `tia`, `critical-path`, `contracting`

---

## Problem

Contractors executing government and public infrastructure projects in the Kingdom of Saudi Arabia under the Government Tenders and Procurement Law (GTPL - نظام المنافسات والمشتريات الحكومية) or FIDIC conditions suffer severe financial losses, liquidated damages (up to 10% contract value), and claim rejections due to three systemic failures:

1. **Statutory Time-Bar Defense (الدفع بسقوط الحق بالتقادم التعاقدي)**:
   - Delay events occur on site (e.g. late possession of site, regulatory permit freezes, employer variations), but the project team fails to issue a formal contractual Notice of Claim within the mandatory statutory window (typically 30 calendar days under Saudi GTPL standard contract or 28 days under FIDIC Sub-Clause 20.1).
   - Once the statutory window lapses, government audit entities and the Board of Grievances (ديوان المظالم) uphold the employer's Time-Bar defense, resulting in total forfeiture of the contractor's right to extension of time and financial compensation.

2. **Unsubstantiated Prolongation Costs (ضياع التعويض عن تكاليف التمديد الموقعية غير المباشرة)**:
   - When an Extension of Time (EOT) is granted, contractors frequently claim arbitrary lump-sum delay damages. Government audit and claims committees summarily reject these figures without an itemized breakdown of site overheads, idling equipment (standby rates), extended supervision staff, and bank guarantee extension fees.

3. **Non-Critical Path Delay Rejections (غياب التحليل الجنائي للجدول الزمني)**:
   - Submitting delay claims for off-critical path activities without forensic Schedule Delay Analysis (e.g. Time Impact Analysis - TIA), which are instantly dismissed by the supervisory consultant.

---

## Root Cause

Generic ERP claim tracking modules treat claims as plain text issue logs with static dates:
- No countdown clock or automated status tracking for statutory notice deadlines.
- Absence of structured statutory categorization aligned with GTPL Article 74 (المادة 74 من نظام المنافسات).
- Cost claim fields accept arbitrary monetary figures without structured prolongation calculation models.

---

## Solution ✅

Implement an end-to-end Saudi GTPL & FIDIC Claims & EOT engine on `claim.record` and `claim.delay.event`:

### 1. Statutory Notice & Time-Bar Engine (`claim.record`)

Compute the statutory notice deadline and time-bar status dynamically:

```python
@api.depends('event_date', 'notice_date', 'notice_due_date', 'status')
def _compute_time_bar_status(self):
    today = fields.Date.context_today(self)
    for rec in self:
        if not rec.notice_due_date:
            rec.time_bar_status = 'within_time'
            rec.days_to_notice_deadline = 0
            rec.is_time_barred = False
            continue

        if rec.notice_date:
            if rec.notice_date <= rec.notice_due_date:
                rec.time_bar_status = 'within_time'
                rec.is_time_barred = False
            else:
                rec.time_bar_status = 'time_barred'
                rec.is_time_barred = True
            rec.days_to_notice_deadline = 0
        else:
            diff_days = (rec.notice_due_date - today).days
            rec.days_to_notice_deadline = diff_days
            if diff_days < 0:
                rec.time_bar_status = 'time_barred'
                rec.is_time_barred = True
            elif diff_days <= 7:
                rec.time_bar_status = 'expiring_soon'
                rec.is_time_barred = False
            else:
                rec.time_bar_status = 'within_time'
                rec.is_time_barred = False
```

Enforce GTPL 30-day default notice period on government projects:
```python
@api.onchange('is_saudi_gtpl_claim')
def _onchange_is_saudi_gtpl_claim(self):
    if self.is_saudi_gtpl_claim and (not self.notice_period_days or self.notice_period_days == 28):
        self.notice_period_days = 30
```

### 2. GTPL Article 74 Grounds Mapping

Classify claims strictly according to statutory grounds for extension and liquidated damages waiver:
- `additional_works`: Additional works / Variations requiring extra time (Art. 74/1).
- `unfunded_budget`: Insufficient annual budget appropriations (Art. 74/2).
- `delayed_site_handover`: Delayed site handover or obstacles caused by government entity (Art. 74/3).
- `entity_suspension`: Formal project suspension order by employer.
- `regulatory_changes`: Change in public regulations, tariffs, or statutory fees.
- `force_majeure`: Force majeure or exceptional emergency circumstances (Art. 74/4).

### 3. Prolongation Costs & Site Overheads Engine

Calculate indirect site prolongation costs mathematically:
$$\text{Total Prolongation} = \text{Staff} + \text{Equipment Standby} + \text{Guarantee Fees} + (\text{Daily Site Overhead} \times \text{Days})$$

```python
@api.depends('staff_prolongation_cost', 'equipment_idling_cost', 'guarantee_extension_fees',
             'daily_site_overhead', 'granted_days', 'claimed_days')
def _compute_total_prolongation_cost(self):
    for rec in self:
        days = rec.granted_days if rec.granted_days > 0 else rec.claimed_days
        rec.total_prolongation_cost = (
            (rec.staff_prolongation_cost or 0.0) +
            (rec.equipment_idling_cost or 0.0) +
            (rec.guarantee_extension_fees or 0.0) +
            ((rec.daily_site_overhead or 0.0) * (days or 0))
        )
```

---

## ⚠️ Pitfalls

1. **Failure to Use `context_today(self)` for Countdown**:
   Using `datetime.date.today()` evaluates against server UTC time. In Saudi Arabia (UTC+3), late-night entries can shift the countdown by a day, causing false time-bar alerts or premature expiry. Always use `fields.Date.context_today(self)`.
2. **PO File Duplicate Messages**:
   Do NOT declare identical `msgid` entries for list headers and field strings (e.g. `Title`, `Project`, `Status`). Merge translation references to prevent `msgfmt` compilation errors.
3. **Delay Concurrency vs Employer Default**:
   If a delay event overlaps with contractor-caused concurrent delays, EOT may be granted as non-compensable (time only, no prolongation cost). Ensure `is_advisory_shown` flags concurrent delays before approving financial prolongation amounts.

---

## Verification

1. **Python Compilation Verification**:
   ```bash
   python3 -m py_compile models/claim_record.py models/claim_delay_event.py
   ```
2. **XML Parse & Structure Check**:
   ```bash
   python3 -c "import xml.etree.ElementTree as ET; ET.parse('views/claim_record_views.xml')"
   ```
3. **PO Translation Validation**:
   ```bash
   msgfmt -c -v i18n/ar.po -o /dev/null
   ```

---

## References

- Saudi Government Tenders and Procurement Law (نظام المنافسات والمشتريات الحكومية - المرسوم الملكي م/128، المادة 74 ولائحته التنفيذية)
- FIDIC Conditions of Contract for Construction (Red Book 2017, Sub-Clause 8.4, 8.5, 20.1)
- Saudi Board of Grievances Public Contracting Case Law (أحكام المحاكم الإدارية بديوان المظالم بشأن السقوط بالتقادم)
- Related files:
  - `construction_claims_eot/models/claim_record.py`
  - `construction_claims_eot/models/claim_delay_event.py`
  - `construction_claims_eot/views/claim_record_views.xml`
  - `Best Practices/saudi-public-works-etimad-ipc-governance.md`
