# Saudi DCC Consultant Review SLA and Balady/Wafi Geotagged Site Evidence

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `saudi-arabia`, `dcc`, `submittals`, `rfi`, `consultant-sla`, `balady`, `wafi`, `escrow`, `sbc`, `gtpl-article-74`, `eot`, `geotagging`, `exif`

---

## Problem

> In Saudi Arabian contracting (both public works under the Government Tenders & Procurement Law - GTPL and private sector developments):
> 1. **Consultant Review Delays & EOT Claims**: Engineering consultants frequently exceed the statutory review periods (standard 14 calendar days for technical Submittals and 7 days for RFIs per Saudi Public Works Contract Article 40 / FIDIC). Without automated tracking of submission vs. review dates and delay thresholds, contractors fail to substantiate Extension of Time (EOT) claims and delay damages reimbursement under GTPL Article 74.
> 2. **SBC Rejections & Work Stoppages**: Submittals rejected with Review Code C (Revise & Resubmit) or Code D (Rejected) lack visibility across the site team, leading to unauthorized installation of non-compliant materials violating Saudi Building Code (SBC 201/301/401/801).
> 3. **Municipal Balady & Wafi Escrow Audit Failures**: Balady municipal inspectors require contemporaneous photographic evidence tied to the 5 statutory construction inspection stages (excavation, foundations, structural frame, insulation, and MEP). Similarly, the Wafi Off-Plan Sales Committee (لجنة البيع على الخارطة) strictly conditions escrow account milestone disbursements on certified surveyor site photos with verifiable GPS metadata (WGS 84 coordinates). Photos taken without GPS coordinates or with stripped EXIF data are routinely rejected by government auditors.

## Root Cause

> Standard ERP document control and photo capture modules treat submittals and site photos as simple attachments or generic logs without statutory legal SLA logic, SBC compliance classification, or automatic EXIF geolocation extraction. Furthermore, manual entry of GPS latitude/longitude is cumbersome for site foremen and prone to omission or rounding truncation errors (e.g. failing to use `digits=(18, 15)` per high-precision standards).

## Solution ✅

> 1. **Automated Consultant SLA & GTPL Article 74 Claim Eligibility in DCC**:
>    - Add statutory consultant review SLA counters: default 14 days on Submittals (`dcc.submittal`) and 7 days on RFIs (`dcc.rfi`).
>    - Compute `actual_review_days = (date_response - date_submission).days` (or days from submission to today if still pending).
>    - Auto-calculate `consultant_delay_days = max(0, actual_review_days - consultant_sla_days)`.
>    - Automatically flag `is_consultant_delayed = True` and `eot_claim_eligible = True` when delayed, triggering statutory EOT claim alerts and dynamic form view warning banners.
>    - Enforce SBC compliance tracking (`is_sbc_compliant`, `sbc_code_ref`) and consultant accreditation (`consultant_balady_license`, `consultant_sce_no`).
>    - Display high-visibility warning ribbons/banners when Submittals receive Review Code C or Code D to block site deployment.
>
> 2. **Geotagged Site Evidence & Statutory Balady/Wafi Verification in Site Photos**:
>    - Model GPS coordinates (`latitude`, `longitude`) with `digits=(18, 15)` to guarantee sub-meter precision without float truncation.
>    - Implement defensive EXIF metadata extraction (`_extract_exif_metadata`) using Pillow (`PIL.Image`, `PIL.ExifTags`) on upload of `image_1920`: converts GPS DMS (Degrees, Minutes, Seconds) rational numbers to Decimal Degrees (DD) and extracts altitude automatically.
>    - Generate clickable `google_maps_url` for one-click GIS coordinate verification.
>    - Integrate Balady 5 statutory inspection milestones: Excavation & Shoring, Foundations & Ground Beams (SBC 301), Structural Skeleton (SBC 301), Thermal & Water Insulation (SBC 601/801), and MEP & Final Completion.
>    - Support Wafi Off-Plan Escrow verification: milestone completion %, licensed surveyor credentials, and verification status (`wafi_verified`).
>    - Display alert banner when photos marked for Balady or Wafi compliance lack GPS coordinates.

```python
# models/dcc_submittal.py (SLA & GTPL Art. 74 Delay Calculation)
@api.depends('date_submitted', 'date_returned', 'consultant_sla_days')
def _compute_consultant_sla(self) -> None:
    today = fields.Date.context_today(self)
    for rec in self:
        if not rec.date_submitted:
            rec.actual_review_days = 0
            rec.consultant_delay_days = 0
            rec.is_consultant_delayed = False
            rec.eot_claim_eligible = False
            continue
        end_date = rec.date_returned or today
        days = (end_date - rec.date_submitted).days
        rec.actual_review_days = max(0, days)
        delay = max(0, rec.actual_review_days - rec.consultant_sla_days)
        rec.consultant_delay_days = delay
        rec.is_consultant_delayed = delay > 0
        rec.eot_claim_eligible = delay > 0
```

```python
# models/site_photo.py (High-Precision Coordinates & Auto EXIF)
latitude = fields.Float(string='Latitude', digits=(18, 15), tracking=True)
longitude = fields.Float(string='Longitude', digits=(18, 15), tracking=True)
google_maps_url = fields.Char(string='Google Maps Location', compute='_compute_google_maps_url', store=True)

@api.model
def _extract_exif_metadata(self, image_base64) -> dict:
    meta = {}
    if not image_base64:
        return meta
    try:
        image_data = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(image_data))
        exif = img.getexif()
        if not exif:
            return meta
        gps_dict = exif.get_ifd(ExifTags.IFD.GPSInfo) if hasattr(ExifTags, 'IFD') else {}
        if gps_dict:
            lat = _dms_to_dd(gps_dict.get(2), gps_dict.get(1))
            lon = _dms_to_dd(gps_dict.get(4), gps_dict.get(3))
            if lat is not None and lon is not None:
                meta['latitude'] = lat
                meta['longitude'] = lon
    except Exception as e:
        _logger.warning("Could not extract EXIF: %s", e)
    return meta
```

## ⚠️ Pitfalls

- **GPS Truncation**: Never use standard Float or `digits=(10, 7)`. Always use `digits=(18, 15)` as documented in `orm/geolocation-precision-digits.md` to prevent coordinate shifting on map pins.
- **EXIF Stripping by Messaging Apps**: Photos forwarded through WhatsApp or Slack have EXIF metadata stripped. Foremen must upload original photos taken directly from the camera or device gallery, or enter GPS coordinates manually.
- **GTPL 30-Day Notice Time-Bar**: While `eot_claim_eligible` flags consultant delay, contractors must serve formal written notice within 30 calendar days of the consultant delay event to preserve rights under GTPL Article 74 and FIDIC Clause 20.1.

## Verification

```bash
# Verify Python syntax and compilation
python3 -m py_compile construction_dcc/models/dcc_submittal.py
python3 -m py_compile construction_site_photo/models/site_photo.py

# Verify XML views parse cleanly
python3 -c "import xml.etree.ElementTree as ET; ET.parse('construction_site_photo/views/site_photo_views.xml')"
```

## References

- Saudi Government Tenders and Procurement Law (GTPL), Royal Decree No. M/128, Article 74 (Contract Extension & Compensation).
- Saudi Standard Public Works Contract, Article 40 (Supervision and Review Turnaround).
- Saudi Building Code (SBC 201, 301, 401, 601, 801).
- Wafi - Off-Plan Sales and Rent Committee Regulations (Ministry of Municipal and Rural Affairs and Housing).
- Related: `orm/geolocation-precision-digits.md`, `Best Practices/saudi-gtpl-claims-eot-and-time-bar-defense.md`.
