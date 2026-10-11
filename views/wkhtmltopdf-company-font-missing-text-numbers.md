# wkhtmltopdf Renders Blank Numbers and Disconnected Arabic Letters When Custom Company Fonts Missing on OS

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views / setup                              |
| Odoo Versions | 15, 16, 17, 18                             |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-10-06                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `wkhtmltopdf`, `pdf`, `fonts`, `tajawal`, `roboto`, `arabic`, `reports`, `macos`, `linux`

---

## Problem

When printing any QWeb PDF report (e.g. Sales Quotation / Order `sale.report_saleorder`, Invoices `account.report_invoice`), the output PDF renders with:
1. **Empty / missing numbers and English text:** The table cells, prices, quantities, and dates appear completely blank or invisible, even though borders and backgrounds render.
2. **Disconnected Arabic letters:** Arabic text appears as isolated, disjointed glyphs (e.g., `ر ا ت خ م د` instead of `خدمات`).
3. Text extraction tools (like `PyPDF2` or `pdftotext`) show null bytes (`\x00\x00\x00`) or missing text blocks for digits.

No Python traceback or Odoo server error is logged; wkhtmltopdf finishes with return code `0`.

---

## Root Cause

Odoo allows companies to select a document layout font in **Settings > Companies > Document Layout** (stored in `res_company.font`, e.g., `Tajawal`, `Roboto`, `Lato`, `Montserrat`, `Open_Sans`, `Oswald`, `Raleway`).

When generating the PDF:
1. Odoo compiles CSS styles (`.o_company_X_layout { font-family: 'Tajawal' !important; }`) into `web.report_assets_common` / `web.report_assets_pdf`.
2. Odoo does **not** bundle local `@font-face` definitions inside the wkhtmltopdf HTML payload for these Google fonts.
3. wkhtmltopdf relies on the **host operating system font rasterizer** (CoreText on macOS, fontconfig / FreeType on Linux) to resolve the font family.
4. If the chosen font family is **not installed on the host OS**, WebKit fails to map the glyph outlines:
   - Numbers and Latin characters fail to load glyph bounding boxes and render as invisible / empty characters.
   - Arabic text loses shaping/joining rules and renders as separated characters.

Additionally, compiled report CSS is cached in `ir.attachment` records (`url LIKE '/web/assets/%report_assets%'`). Even if fonts or company settings change, wkhtmltopdf will keep using the stale cached CSS until the attachments are removed or regenerated.

---

## Solution ✅

### 1. Install Odoo's Google TTF Fonts into Host Operating System

Odoo ships all supported Google fonts under `addons/web/static/fonts/google/`. Copy them into the OS font library:

**On macOS:**
```bash
cp -r /path/to/odoo/addons/web/static/fonts/google/*/*.ttf ~/Library/Fonts/
fc-cache -f ~/Library/Fonts/
```

**On Ubuntu / Debian Linux:**
```bash
sudo mkdir -p /usr/local/share/fonts/truetype/odoo
sudo cp -r /path/to/odoo/addons/web/static/fonts/google/*/*.ttf /usr/local/share/fonts/truetype/odoo/
sudo fc-cache -f -v
```

Verify that the system font rasterizer now sees the fonts:
```bash
fc-list : family | grep -iE 'tajawal|roboto|lato|montserrat|open sans' | sort -u
```

### 2. Purge Stale Report Asset Attachments in Odoo

Clear the compiled report asset bundles so Odoo re-compiles the CSS clean with the correct font definitions:

```bash
python3 odoo-bin shell -c odoo.conf -d <dbname> --no-http << 'EOF'
attachments = env['ir.attachment'].search([('url', '=like', '/web/assets/%report_assets%')])
print(f"Purging {len(attachments)} cached report asset attachments...")
attachments.unlink()
env.cr.commit()
print("Purge complete.")
EOF
```

### 3. Ensure multi-company font coverage

If different companies in a multi-company database use different fonts (e.g., Company 1 uses `Tajawal`, Company 2 uses `Roboto`), ensure all referenced fonts are installed on the OS.

---

## ⚠️ Pitfalls

- **Do NOT try to fix this by modifying QWeb templates with inline SVG fonts:** wkhtmltopdf (WebKit 0.12.x) has notorious memory leaks and slow rendering when embedding large base64 WOFF/TTF data URIs in QWeb templates. Installing TrueType fonts on the host OS is 10x faster and native.
- **Multi-DB environments:** If your Odoo instance hosts multiple databases without `db_filter`, wkhtmltopdf HTTP requests without cookies may hit the DB selector and fail with 404 (`ContentNotFoundError`). Ensure `db_filter` or `report.url` is configured.
- **Font Cache Persistence:** On containerized deployments (Docker), remember to mount or copy the fonts into the Docker image during the build stage (`COPY addons/web/static/fonts/google/ /usr/local/share/fonts/`).

---

## Verification

Render a PDF report via curl or browser and convert to PNG via `pdftoppm`:

```bash
curl -s -b "session_id=<your_session_id>" "http://localhost:8069/report/pdf/sale.report_saleorder/<order_id>" -o /tmp/test_report.pdf
pdftoppm -png -r 150 /tmp/test_report.pdf /tmp/test_report_page
```

Check the rendered PNG:
1. Verify company logo and typography.
2. Confirm all digits, unit prices, and totals are crisp and readable.
3. Confirm Arabic words are fully connected and formatted correctly.

---

## References

- Related: `setup/wkhtmltopdf-not-in-ubuntu-repos.md`
- Related: `views/wkhtmltopdf-report-overlapping-header-columns.md`
