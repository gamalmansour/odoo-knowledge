# Dynamic Notebook Page Tab Titles in Odoo 18 OWL via FormCompiler Patch

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | frontend                                   |
| Odoo Versions | 18 (OWL 2)                                 |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-26                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `owl`, `FormCompiler`, `compileNotebook`, `notebook`, `tabs`, `dynamic-title`, `odoo18`

---

## Problem

In Odoo Form views, `<page string="Plan 1">` titles inside a `<notebook>` are static XML strings evaluated at view compilation time. When legacy or Mobile-App-integrated models expose fixed slot tabs (`Plan 1` .. `Plan 16`) alongside dynamic label fields (`payment_plan_label_1` .. `payment_plan_label_16`), users see generic `Plan 1` / `Plan 2` headers instead of meaningful labels like `Equal - 4 Years`.

Replacing the 16-tab XML structure with a custom widget would break external API/Mobile App assumptions or require rewriting every slot view.

## Root Cause

Odoo 18's `FormCompiler.prototype.compileNotebook` compiles `<page>` elements into an OWL `<Notebook>` component passing a `pages` object whose `title` property is hardcoded to the XML `string` attribute (`"Plan 1"`).

## Solution ✅

Patch `FormCompiler.prototype.compileNotebook` in a small backend JS asset (`web.assets_backend`) to replace the compiled `title` expression with a reactive lookup against `props.record.data.<label_field>` (falling back to the static string when empty):

```javascript
/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormCompiler } from "@web/views/form/form_compiler";

const PLAN_TAB_RE = /^Plan\s+(\d{1,2})$/;
const TARGET_MODELS = new Set(["listing.projects", "listing.units"]);

patch(FormCompiler.prototype, {
    compileNotebook(el, params) {
        const notebook = super.compileNotebook(el, params);
        const resModel = this.templates?.form?.getAttribute?.("res_model") || params?.resModel;
        if (resModel && !TARGET_MODELS.has(resModel)) {
            return notebook;
        }
        const slots = notebook.querySelectorAll("t[t-set-slot]");
        for (const slot of slots) {
            const titleAttr = slot.getAttribute("title");
            if (!titleAttr) {
                continue;
            }
            const cleanTitle = titleAttr.replace(/^['"]|['"]$/g, "");
            const match = PLAN_TAB_RE.exec(cleanTitle);
            if (!match) {
                continue;
            }
            const slotNum = parseInt(match[1], 10);
            if (slotNum >= 1 && slotNum <= 16) {
                const labelField = `payment_plan_label_${slotNum}`;
                slot.removeAttribute("title");
                slot.setAttribute(
                    "t-att-title",
                    `props.record.data.${labelField} || '${cleanTitle}'`
                );
            }
        }
        return notebook;
    },
});
```

Register the file in `__manifest__.py` under `'web.assets_backend'`.

## ⚠️ Pitfalls

- Ensure each `payment_plan_label_N` field is actually referenced in the `<form>` arch (even if `readonly="1"` or `invisible="1"`), otherwise Odoo 18's web client will not include it in `activeFields` and `props.record.data[labelField]` will be `undefined`.
- Always keep the fallback (`|| 'Plan N'`) so unsaved/empty records never render an empty tab header.
- Scope the patch to target models or a strict regex (`^Plan\s+\d{1,2}$`) so unrelated forms are untouched.

## Verification

1. Upgrade the module and restart the Odoo server (manifest asset changes require a restart).
2. Open a record with populated `payment_plan_label_1` (e.g. `Equal - 4 Years`) and confirm the tab header renders `Equal - 4 Years` while updating live if the label changes.

## References

- Core compiler: `addons/web/static/src/views/form/form_compiler.js` (`compileNotebook`)
- Core patch pattern: `addons/mail/static/src/chatter/web/form_compiler.js`
