# Portal Controller Savepoint Atomicity, Hidden Form Templates & Image Upload Hardening (Odoo 19)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `portal`, `savepoint`, `atomicity`, `UserError`, `xss`, `svg`, `open-redirect`, `qweb`, `stock.move`, `odoo19`

---

## Problem

Four recurring failure patterns in custom Odoo 19 portal & delivery workflows:

1. **Partial Commit on `UserError` inside Portal Controllers:** Catching `UserError` inside an `@http.route` handler and returning `request.redirect(...)` (HTTP 303) causes Odoo's WSGI layer to **commit** the database transaction — leaving behind already-executed side effects (validated pickings, draft credit notes, draft payments, or prematurely cleared flags) even though the action failed.
2. **Phantom Zero-Amount Rows from Hidden Templates Inside `<form>`:** Placing a `class="d-none"` DOM template `<div id="new-row-template">` inside a `<form>` submits its `<select>` / `<input>` elements on every Save, inserting empty/zero rows (`0.00` cash lines) on every submit.
3. **Stored XSS & Open Redirect on Portal Endpoints:** Accepting `photo.content_type` and raw `photo.read()` without magic-byte/size validation allows `.svg` (`image/svg+xml`) Stored XSS and memory DoS; redirecting directly to `kw.get('redirect_url')` allows phishing redirects; wrapping post-interpolated strings in `Markup(_("...") % user_val)` disables HTML escaping.
4. **Odoo 19 `stock.move` Creation Failure on Return Pickings:** Passing `'name': ...` in `stock.move.create()` fails in Odoo 19 because `stock.move.name` was removed in favor of `'description_picking'`.

## Root Cause

- Odoo only auto-rolls back a request cursor when an exception propagates out of the controller. Swallowing `UserError` to show a friendly flash message commits everything flushed prior to the error.
- HTML `<form>` submits all named inputs inside it regardless of CSS `display: none` (`d-none`).
- `Markup(msg)` treats the already-formatted string as safe HTML; only `Markup(template) % (arg1, arg2)` escapes the interpolated arguments.

## Solution ✅

### 1. Wrap Side-Effecting Model Calls in `request.env.cr.savepoint()`

```python
try:
    with request.env.cr.savepoint():
        visit.action_end_visit(latitude=lat, longitude=lng, ip_addr=ip_addr, accuracy=accuracy)
except UserError as e:
    request.session['visit_error_msg'] = str(e)
```

### 2. Place Reusable DOM Row Templates Outside `<form>`

```xml
<form method="post" t-attf-action="/my/visits/#{visit.id}/update-collection">
    <!-- real form rows only -->
</form>
<!-- Hidden template strictly outside <form> so browser never submits it -->
<div id="new-collection-line-template" class="d-none">...</div>
```

### 3. Validate Uploads by Magic Bytes + Cap Size, Sanitize Redirects, Escape Chatter `Markup`

```python
@staticmethod
def _sanitize_portal_redirect(redirect_url, fallback):
    if redirect_url and isinstance(redirect_url, str):
        cleaned = redirect_url.strip()
        if cleaned.startswith('/my/') and not cleaned.startswith('//') and '\\' not in cleaned and '\r' not in cleaned and '\n' not in cleaned:
            return cleaned
    return fallback

@staticmethod
def _validate_uploaded_image(photo, max_bytes=10 * 1024 * 1024):
    if not photo or not photo.filename:
        return None
    data = photo.read(max_bytes + 1)
    if not data or len(data) > max_bytes:
        return None
    if data.startswith(b'\xff\xd8\xff'):
        return data, 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return data, 'image/png'
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return data, 'image/webp'
    if data.startswith((b'GIF87a', b'GIF89a')):
        return data, 'image/gif'
    return None

# Chatter escaping: wrap the template in Markup BEFORE % interpolation
msg = Markup(_("<span>Customer</span>: <b>%s</b>")) % (partner.name or '')
```

### 4. Odoo 19 Return Picking Move Dict

```python
# Odoo 19: use 'description_picking', NEVER 'name' on stock.move
self.env['stock.move'].sudo().create({
    'description_picking': rline.product_id.display_name,
    'product_id': rline.product_id.id,
    'product_uom_qty': rline.qty,
    'product_uom': rline.product_id.uom_id.id,
    'picking_id': picking.id,
    'location_id': customer_loc.id,
    'location_dest_id': dest_loc.id,
    'partner_id': visit.partner_id.id,
    'company_id': visit.company_id.id,
})
```

## ⚠️ Pitfalls

- **Never put `d-none` row templates inside `<form>`** — `disabled` attributes are easily forgotten or re-enabled by JS; moving the template outside `</form>` is foolproof.
- **Never reset audit flags (like `supervisor_approved`) before `action_end_visit()`** — if closing fails you wipe the approval, and if it succeeds you destroy the audit trail. Reset only on explicit reopen (`action_reopen_visit()`).
- **Guard one-time `init()` backfills with an `ir_config_parameter` sentinel** — otherwise every `-u` upgrade re-runs `UPDATE res_partner SET valid_customer = TRUE`, silently resurrecting blacklisted partners.

## Verification

- Playwright E2E verifying: empty Save submits 0 phantom collection lines, SVG upload rejected while PNG accepted, external `redirect_url` blocked, `UserError` inside `portal_visit_end` rolls back previously created draft credit note via `savepoint()`, and Odoo 19 return picking validates cleanly without `stock.move.name` crash.

## References

- Related file: `upgrade/odoo19-backdate-apply-inventory-and-payment-states.md`
