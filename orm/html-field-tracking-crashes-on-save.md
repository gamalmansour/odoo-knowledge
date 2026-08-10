# `tracking=True` on an Html field raises NotImplementedError on every save

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-10                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `fields`, `mail`, `mail.thread`, `tracking`, `html`, `chatter`, `NotImplementedError`

---

## Problem

Adding `mail.thread` to a model and flipping `tracking=True` on an `Html` field
looks like every other tracked field — it installs cleanly and only breaks the
first time a user actually **saves** a change to that field:

```python
class ActivityCmsPage(models.Model):
    _name = 'activity.cms.page'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    description = fields.Html(translate=True, sanitize=True, tracking=True)  # BOOM on save
```

```
NotImplementedError
  File ".../addons/mail/models/mail_tracking_value.py", line ..., in _create_tracking_values
    raise NotImplementedError('Unsupported tracked field type: %s' % field.type)
```

The module installs fine, demo data loads fine, and every read/list view works —
the crash only fires inside `write()`, on the very first content edit through the
form. Easy to ship and only discover in UAT or production.

## Root Cause

`mail.thread`'s tracking mechanism (`mail_tracking_value._create_tracking_values`,
called from `BaseModel._message_track` on every `write()` that touches a
`tracking=True` field) only knows how to snapshot old/new values for a fixed set
of field types:

```
integer, float, char, text, datetime, date, boolean, selection, many2one, many2many, one2many
```

`Html` isn't on that list (it's arbitrary rich-text markup, not a scalar the
chatter can diff sensibly) — Odoo doesn't validate this at field-declaration time
or at module install, only at the moment a write actually needs to build a
tracking value for that field.

## Solution ✅

Never set `tracking=True` on a `fields.Html(...)` field. Track the fields around
it instead (title, visibility, publish state) and leave a comment explaining why
the content field is deliberately excluded — the chatter still logs THAT an edit
happened (via the other tracked fields / a plain log message), just not a diff of
the markup itself:

```python
# `description` is deliberately NOT tracked: Odoo raises NotImplementedError for
# tracking on Html fields (mail_tracking_value._create_tracking_values supports
# only integer/float/char/text/datetime/date/boolean/selection/m2o/x2m), so
# tracking=True there would crash the form on every save.
name = fields.Char(required=True, translate=True, tracking=True)
description = fields.Html(translate=True, sanitize=True)   # NOT tracked
active = fields.Boolean(default=True, tracking=True)
```

If real content versioning is a genuine requirement, that's a separate revision
model (snapshot rows keyed to the parent record), not field tracking.

## ⚠️ Pitfalls

- `fields.Text`/`fields.Char` are perfectly safe to track — only `Html` (and
  binary-ish types not in the supported list) raise. Don't over-exclude: a
  `Text` testimonial quote or nutrition tip body tracks fine.
- The crash is **write-path only** — a clean `-i`/`-u` install with
  `--test-enable` won't catch it unless a test actually performs a `write()` on
  the Html field with `tracking=True` set. A static grep for
  `fields.Html(` + `tracking=True` on the same field is the fast pre-commit
  check; the reliable one is a repo-wide regression test (see below) that
  iterates the registry so it also catches the NEXT model that makes this
  mistake, not just the one you're looking at today.
- Computed non-stored fields don't crash from this (they're never in a `write()`
  vals dict, so tracking never fires) but `tracking=True` on one is a silent
  no-op — don't confuse "doesn't crash" with "works".

## Verification

Repo-wide regression guard (run as part of the normal test suite, not a one-off
check) — add once, it protects every current AND future model in the addon
namespace:

```python
def test_no_html_field_is_tracked_anywhere(self):
    for model_name in self.env.registry.models:
        if not model_name.startswith('activity.'):
            continue
        for name, field in self.env[model_name]._fields.items():
            if field.type == 'html':
                self.assertFalse(
                    getattr(field, 'tracking', False),
                    'tracking on Html crashes on save: %s.%s' % (model_name, name))
```

Manual repro of the crash (to confirm the guard actually catches it — temporarily
set `tracking=True` on any Html field, then):

```bash
odoo-bin -c conf -d db -i <module> --test-enable --test-tags /<module> --stop-after-init
# a real write() to that field inside a test raises NotImplementedError
```

## References

- Code: `activity/activity_cms/models/activity_cms_page.py` (`description`, the
  first field this was caught on, 2026-08-10) and the guard test in
  `activity/activity_cms/tests/test_cms_models.py::TestCmsPageChatter::test_no_html_field_is_tracked_anywhere`
- Related file: `orm/field-name-collision-with-mail-activity-mixin.md` (a
  different `mail.thread`/`mail.activity.mixin` pitfall — name collision, not
  field-type support)
