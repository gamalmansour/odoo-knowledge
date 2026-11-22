# Portal `website_slides` `403 Forbidden` When Controller Reads Protected Child One2many Without `sudo()`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `website_slides`, `portal`, `403`, `ir.model.access`, `sudo`, `one2many`, `elearning`, `security`

---

## Problem

When a portal user (`base.group_portal`) opens a published eLearning slide (`/slides/slide/<model("slide.slide"):slide>`) that has a custom protected child `One2many` model (such as interactive video cue points storing `correct_option`), the page crashes with `403: Forbidden`:

```text
403: Forbidden
You are not allowed to access 'Interactive Video Cue Point' (ghtc.slide.cue.point) records.
This operation is allowed for the following groups:
- eLearning/Officer
- eLearning/Administrator
```

This commonly slips past unit tests if tests only call JSON-RPC submission endpoints or helper methods directly with `.sudo()` without executing `self.url_open(slide.website_url)` authenticated as a `base.group_portal` user.

## Root Cause

To prevent portal trainees from inspecting answer keys (like `correct_option`) via raw ORM/RPC reads, the child model intentionally omits `base.group_portal` from `ir.model.access.csv` and exposes only a sanitized dictionary through a `.sudo()` helper. However, any single un-`sudo()`ed traversal of the `One2many` field inside a `WebsiteSlides.slide_view` override (e.g., `if slide.ghtc_cue_point_ids.filtered('is_mandatory'):`) executes under `request.env.user` (the portal user) and immediately raises `AccessError` -> HTTP `403 Forbidden`.

## Solution ✅

1. **Always traverse the protected child `One2many` through `slide.sudo()` inside both the controller override and model helpers**, while returning only sanitized data (never answer keys) to QWeb/JS:

```python
# controllers/main.py
if slide.ghtc_interactive_video_enabled and slide.sudo().ghtc_cue_point_ids.filtered('is_mandatory'):
    pending, _done, _total = slide.sudo()._ghtc_has_pending_mandatory_cues(request.env.user.partner_id)
    if pending:
        slide_ctx = slide.with_context(ghtc_defer_auto_complete=True)
        return super().slide_view(slide_ctx, **kwargs)
```

```python
# models/slide_channel.py
mandatory_cues = self.sudo().ghtc_cue_point_ids.filtered('is_mandatory')
```

2. **Add an `HttpCase` portal page render test** that authenticates as `base.group_portal`, hits `slide.website_url`, asserts `HTTP 200`, and verifies sensitive fields are absent from the rendered HTML:

```python
self.authenticate('portal_trainee_el@ghtc.test', 'portal_el_password')
res_slide_page = self.url_open(self.slide1.website_url)
self.assertEqual(res_slide_page.status_code, 200)
self.assertNotIn('correct_option', res_slide_page.text)
```

## ⚠️ Pitfalls

- **Never "fix" this by adding `base.group_portal` read ACL on an answer-key model:** That allows any logged-in trainee to dump `correct_option` via standard RPC calls. Keep the model locked down and read strictly through sanitized `.sudo()` helpers.
- **Always test the full HTML GET route as a real portal user:** Testing only JSON endpoints or backend methods misses controller-level `AccessError` regressions on `slide_view`.

## Verification

```bash
odoo-bin -c openedu.conf -d test_db --test-tags=ghtc_elearning --stop-after-init
```

## References

- Related module: `ghtc_elearning/controllers/main.py`, `ghtc_elearning/models/slide_channel.py`, `ghtc_elearning/tests/test_elearning.py`
