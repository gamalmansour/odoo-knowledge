# Empty `<script>` Tags in QWeb/XML Views Collapsed by lxml to `<script/>` Causing Frontend SyntaxError

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All (14, 15, 16, 17, 18, 19)              |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `qweb`, `xml`, `lxml`, `script`, `syntaxerror`, `frontend`, `toast`, `self-closing`

---

## Problem

When embedding third-party script tags (e.g. `<script src="https://unpkg.com/.../lib.js" type="module"></script>`) in custom QWeb templates, XML views, or `s_embed_code` snippets, navigating between pages (especially via PJAX / frontend routing) triggers a brief (1-second) error toast:
```
Uncaught SyntaxError: Unexpected token '<'
```
or scripts following the `<script>` tag fail to execute properly.

## Root Cause

Odoo stores view architectures (`arch_db` in `ir.ui.view`) as XML. When Odoo or Python's XML parser (`lxml.etree` / `xml.etree.ElementTree`) parses and serializes XML, any empty element with no text or child nodes like `<script src="..."></script>` is automatically normalized to a self-closing XML tag:
```xml
<script src="https://unpkg.com/.../lib.js" type="module" />
```
While valid in pure XML, in HTML5 `<script>` is **NOT** a void/self-closing element. Web browsers ignore the slash `/` in `<script .../>` and treat the tag as remaining open. Consequently, the browser interprets the subsequent HTML (such as `<style>` or `<div>`) as JavaScript content inside the unclosed `<script>` tag, immediately raising `SyntaxError: Unexpected token '<'`.

Even if a developer manually edits the view to `<script src="..."></script>`, the next time Odoo saves `arch_db` through the ORM or XML loader, `lxml` collapses it back to `<script .../>`!

## Solution ✅

Force the XML parser to serialize the tag with an explicit closing `</script>` by placing non-empty content (such as a short JavaScript comment or space) inside the `<script>` element:

```xml
<!-- ❌ BAD: Empty tag will be serialized by lxml as <script ... /> -->
<script src="https://unpkg.com/@lottiefiles/dotlottie-wc@0.8.11/dist/dotlottie-wc.js" type="module"></script>

<!-- ✅ GOOD: Non-empty inner content forces lxml to serialize as <script ...>/* comment */</script> -->
<script src="https://unpkg.com/@lottiefiles/dotlottie-wc@0.8.11/dist/dotlottie-wc.js" type="module">/* odoo */</script>
```

In Python / script updates:
```python
import re

fixed_arch = re.sub(
    r'<script([^>]*?)(\s*/>|></script>)',
    r'<script\1>/* script-closed */</script>',
    arch_db
)
view.write({'arch_db': fixed_arch})
```

## ⚠️ Pitfalls

- **Saving via Odoo Studio or Website Editor**: If someone re-saves an embed snippet through the web UI, ensure the snippet HTML includes the inner comment `/* odoo */`, otherwise the editor's XML normalization will re-collapse the empty tag.
- **PJAX / Frontend Navigation Error Flashes**: Because Odoo's frontend website framework replaces page content dynamically without a full window reload, this syntax error appears as a fleeting 1-second red notification before the new page finishes rendering.

## Verification

Curl the website page and verify that no self-closing `<script .../>` tags exist in the output:

```bash
curl -s https://your-domain.com/ | grep -E "<script[^>]*/>"
# Should return 0 matches
```

## References

- HTML5 Specification: Elements that cannot be self-closing (`<script>`, `<div>`, `<iframe>`).
- Python `lxml` documentation on empty tag serialization.
