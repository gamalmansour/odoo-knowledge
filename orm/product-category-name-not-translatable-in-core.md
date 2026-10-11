# product.category.name is NOT translate=True in core Odoo 17

**Category:** ORM / i18n
**Date:** 2026-07-22
**Project:** activity (store API, Batch 2)

## Lesson
`product.template.name` is `translate=True` in core, but **`product.category.name` is not**. Any "return the category name in Arabic" feature that just reads `categ_id.with_context(lang='ar_001').name` silently echoes the source language forever — and the admin has no way to enter a translation at all. The read is a no-op, not an error, so nothing fails visibly.

## Fix
Flip the flag via a one-line inherit in the module that needs it:

```python
class ProductCategory(models.Model):
    _inherit = 'product.category'
    name = fields.Char(translate=True)
```

Existing category names become the source-language term; translations are entered normally (Settings → Translations or the field's globe icon). The `with_context(lang=...)` reads then work unchanged.

## Rule of thumb
Before promising a `_ar`/`_en` pair on ANY field, check `translate=` on the actual core definition (`grep "name = fields" odoo/addons/<module>/models/...`). Don't assume name fields are translatable — many core master-data models (product.category among them) are not.
