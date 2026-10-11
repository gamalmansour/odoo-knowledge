# A public (no-login) image-proxy route needs an explicit model whitelist + record gate, or `/web/image` itself, to avoid IDOR / 401s for headless app callers

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `ir.binary`, `image`, `web/image`, `public`, `auth=public`, `idor`, `controllers`, `rest-api`

---

## Problem

A headless/mobile-app API serves product (or any other model's) images by
pointing `image_url` at Odoo's built-in `/web/image/<model>/<id>/<field>`
route. For a caller that is **not** a `res.users` web session (e.g. the
Activity platform's app users, who are `res.partner` + a custom JWT, never
logged into the web client), that route 401s or redirects to `/web/login`
instead of streaming the image — the client sees a broken image, not a photo.

## Root Cause

`/web/image/...` (`addons/web/controllers/binary.py`, `content_image`) is
`auth="public"` itself, but it resolves the record and streams via
`request.env['ir.binary']._get_image_stream_from(record, field, ...)`
**without** an extra `sudo()` — access is evaluated as the current recordset
env, i.e. the public web user (`base.public_user`), not a JWT-bearer identity
your custom auth layer just validated. If the model/record isn't world
readable to `base.group_public` (typical once real ACLs/record rules are in
play), the stream call raises and the controller falls back to a
placeholder or a `web.login`-redirecting flow depending on config — not a
clean `200` with the real image.

## Solution ✅

Don't reuse `/web/image` for a headless API. Add your own thin, public route
that:

1. **Whitelists the model as a literal tuple, checked before any
   `request.env[model]` lookup** — this is the actual IDOR barrier. Never let
   a path parameter pick an arbitrary model string that reaches the ORM.
   ```python
   _IMAGE_MODELS = ('product.template', 'product.product')

   @http.route('/api/v1/store/image/<string:model>/<int:rec_id>', type='http',
               auth='public', methods=['GET'], csrf=False, cors='*')
   def product_image(self, model, rec_id, **kwargs):
       if model not in _IMAGE_MODELS:
           return api_utils.json_error('not_found', _('Image not found.'), status=404)
       record = request.env[model].sudo().browse(rec_id).exists()
       if not record:
           return api_utils.json_error('not_found', _('Image not found.'), status=404)
   ```
2. **Re-derive the "is this actually public content" gate yourself**, same as
   any other public endpoint in the module (here: resolve a variant to its
   template, then require the same flags the JSON serializer already uses):
   ```python
       tmpl = record if model == 'product.template' else record.product_tmpl_id
       if not tmpl.activity_store_ok or not tmpl.sale_ok:
           return api_utils.json_error('not_found', _('Image not found.'), status=404)
   ```
3. **Stream via `ir.binary` under `sudo()`** — this is the one place a
   deliberate `sudo()` is correct: you already re-imposed your own business
   gate in step 2, so bypassing ACLs here doesn't skip a check, it replaces
   Odoo's generic one with your module's specific one:
   ```python
       stream = request.env['ir.binary'].sudo()._get_image_stream_from(record.sudo(), 'image_512')
       return stream.get_response()
   ```
4. Point every serializer's `image_url` at the new route instead of
   `/web/image/...`.

## ⚠️ Pitfalls

- **Don't wrap this route in a per-request DB-logging decorator** (e.g. a
  `log_api_request` that opens a second cursor to persist an API-call log).
  An image route is the highest-traffic endpoint in a module — every
  thumbnail on every screen, not once per page load like a JSON list — so
  logging every hit will flood the log table and add cursor pressure far
  faster than any JSON route. This is a real "deployed 6 months, now it's
  slow" failure mode, not a hypothetical.
- Existence-check on a **cheap** resized field (e.g. `image_256`) for the
  `image_url: None` decision, but **stream** a larger one (e.g. `image_512`)
  from the route — don't force-decode the full `image_1920` just to know
  "does this record have an image".
- `_get_image_stream_from` silently falls back to a placeholder image when
  the field is empty (by design) — your 404 has to come from the
  whitelist/existence/business-gate checks *before* that call, not from
  "stream came back empty".
- This pattern generalizes: any Activity module image field
  (`activity.venue`, `activity.activity`, `activity.coach`, …) currently
  served via `/web/image/...` in a public catalogue controller has the same
  latent 401/redirect risk for a non-web-session caller — it just hasn't
  been reported yet because those reads happen to work under whatever the
  public user's default ACLs allow today. Any of them getting a client
  complaint should reuse this exact whitelist+gate+sudo pattern, not patch
  `/web/image` itself.

## Verification

```bash
# 200, real image bytes, NO Authorization header / web session at all
curl -i http://localhost:8069/api/v1/store/image/product.template/<id>

# 404 — model not in the whitelist, never reaches request.env[model]
curl -i http://localhost:8069/api/v1/store/image/res.partner/<id>

# 404 — whitelisted model, but record fails the business gate
# (activity_store_ok=False or sale_ok=False)
curl -i http://localhost:8069/api/v1/store/image/product.template/<non_store_id>
```

## References

- `odoo/addons/base/models/ir_binary.py` — `_get_image_stream_from`,
  `_get_stream_from` (the non-sudo access check that causes the 401 when
  reused as-is under a non-`res.users` caller).
- `addons/web/controllers/binary.py` — `content_image` (`/web/image`'s own
  implementation, for comparison).
- Related file: `orm/field-name-collision-with-mail-activity-mixin.md`
  (same module, different Batch-2 lesson: naming a field `activity_ids`).
- Implementation: `activity/activity_store/controllers/store_controller.py`
  (`product_image` route, `_IMAGE_MODELS`).
