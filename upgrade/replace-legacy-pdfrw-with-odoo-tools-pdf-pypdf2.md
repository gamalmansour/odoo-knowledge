# Replace Legacy `pdfrw` AcroForm Filling with Native `odoo.tools.pdf` (`PyPDF2` / `pypdf`)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `pdfrw`, `PyPDF2`, `pypdf`, `odoo.tools.pdf`, `AcroForm`, `ModuleNotFoundError`, `upgrade`

---

## Problem

> Installing or upgrading a migrated custom module (commonly from Odoo 14/15) that fills AcroForm PDF templates (e.g., certificates, government forms, contracts) crashes registry loading with `ModuleNotFoundError: No module named 'pdfrw'`.

```text
  File ".../dvst_automatic_admission/models/pdf_form_filler.py", line 1, in <module>
    import pdfrw
ModuleNotFoundError: No module named 'pdfrw'
```

## Root Cause

1. `pdfrw` is an abandoned third-party library (last PyPI release `0.4` in 2017) that is not included in Odoo's standard `requirements.txt`.
2. Installing `pdfrw` manually in `.venv` creates a hidden deployment failure on every new staging, Docker, or client production environment.
3. Odoo 16+ already ships `odoo.tools.pdf.fill_form_fields_pdf(writer, form_fields)` backed by `PyPDF2` / `pypdf`, which sets `/NeedAppearances = True` and `/Ff = 1` (read-only) natively.

## Solution ✅

Replace `pdfrw` with `odoo.tools.pdf` in memory (`io.BytesIO`), avoiding both the external dependency and `/tmp/*.pdf` race conditions:

```python
import io
from typing import Any
from odoo.tools import pdf


def fill_pdf_bytes(template_bytes: bytes, data: dict[str, Any]) -> bytes:
    """Fill AcroForm fields in memory and lock them read-only via Odoo core pdf tools."""
    sanitized = {
        str(k): '' if v is None or v is False else str(v)
        for k, v in data.items()
    }
    reader = pdf.PdfFileReader(io.BytesIO(template_bytes), strict=False)
    writer = pdf.PdfFileWriter()
    if hasattr(writer, 'clone_document_from_reader'):
        writer.clone_document_from_reader(reader)
    elif hasattr(writer, 'append'):
        writer.append(reader)
    else:
        for idx in range(reader.getNumPages()):
            writer.addPage(reader.getPage(idx))

    pdf.fill_form_fields_pdf(writer, form_fields=sanitized)
    with io.BytesIO() as buf:
        writer.write(buf)
        return buf.getvalue()
```

## ⚠️ Pitfalls

- **`clone_reader_document_root` vs `clone_document_from_reader`:** In `PyPDF2 2.x`, calling `writer.clone_reader_document_root(reader)` clones ONLY the root catalog with **zero pages** (`len(writer.pages) == 0`), causing `fill_form_fields_pdf` to silently skip all fields and output blank form values! Always use `writer.clone_document_from_reader(reader)` (or `writer.append(reader)` on `pypdf >= 3.0`).
- **Odoo `False` Values in Relational/Char Fields:** Empty Odoo fields evaluate to `False`, which `str(False)` turns into literal `"False"` on printed certificates. Always sanitize `None` and `False` to `''` before calling `fill_form_fields_pdf`.
- **Hardcoded `/tmp/` Paths:** Never write filled certificates to a fixed `/tmp/cert.pdf` path inside a loop; concurrent requests overwrite each other's files or raise `FileNotFoundError` on `os.remove()`. Always use `io.BytesIO`.

## Verification

```bash
./.venv/bin/python3 -c "
import io, sys
sys.path.insert(0, '.')
from odoo.tools import pdf
# Verify reader + clone_document_from_reader + fill_form_fields_pdf round-trip
"
```

## References

- Core reference: `odoo/tools/pdf/__init__.py` (`fill_form_fields_pdf`)
- Core usage example: `addons/sale_pdf_quote_builder/models/ir_actions_report.py`
- Related file: `setup/missing-python-dependency-pandas.md`
