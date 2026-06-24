# Print-Ready A4 CSS Layouts for Custom Reports and Profiles

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-06-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `css`, `print`, `pdf`, `layout`, `a4`, `svg`, `page-break`

---

## Problem

When printing HTML pages (like custom Odoo client-facing documents, profiles, or QWeb reports) to PDF, layouts often break:
- Text is awkwardly split across page boundaries.
- Colors and backgrounds are omitted because of browser defaults.
- Detailed AI-generated or raster images look blurred and bloated, failing to convey clear corporate branding.
- Pages overflow or have incorrect margins, causing extra blank pages.

## Root Cause

- Default CSS print styles are often unconfigured, leading browsers to apply auto-pagination and strip background colors.
- Raster images scale poorly and slow down PDF compilation (especially in wkhtmltopdf).
- Lack of explicit page-break and sizing rules inside the CSS.

## Solution ✅

Use a strict CSS/SVG print design system to ensure pixel-perfect, resolution-independent A4 exports.

### 1. Page Sizing & Margins

Set the exact A4 dimensions and disable margins inside `@page`, and override element shadows/borders during printing:

```css
@media print {
  body {
    background-color: transparent;
    padding: 0;
    margin: 0;
  }

  .page {
    box-shadow: none !important;
    border: none !important;
    border-radius: 0 !important;
    margin: 0 !important;
    padding: 20mm 15mm; /* Exact print safe zone padding */
    width: 210mm;
    height: 297mm;
    page-break-after: always;
    break-after: page;
    box-sizing: border-box;
  }

  @page {
    size: A4;
    margin: 0;
  }
}
```

### 2. Resolution-Independent Diagrams (SVG)

Avoid heavy raster images for structural diagrams (like workflows, puzzles, networks). Instead, use clean, inline SVG code.

Example for a clean interlocking jigsaw puzzle:
```xml
<svg viewBox="0 0 240 240" width="200" height="200">
  <path d="M 30,30 L 120,30 L 120,70 C 128,70 135,76 135,84 C 135,92 128,98 120,98 L 120,120 L 98,120 C 98,112 92,105 84,105 C 76,105 70,112 70,120 L 30,120 Z" fill="#ffffff" stroke="#e2e8f0" stroke-width="2"/>
  <path d="M 120,30 L 210,30 L 210,120 L 170,120 C 170,128 176,135 184,135 C 192,135 198,128 198,120 L 120,120 L 120,98 C 128,98 135,92 135,84 C 135,76 128,70 120,70 Z" fill="#1e2875" stroke="#1e2875" stroke-width="2"/>
</svg>
```

### 3. Prevent Content Splitting

For cards, items, and paragraphs, use `page-break-inside: avoid;` to prevent them from splitting across A4 pages:

```css
.card, .partner-card, p {
  page-break-inside: avoid;
  break-inside: avoid;
}
```

## ⚠️ Pitfalls

- **Color Adjust:** Always include `-webkit-print-color-adjust: exact;` and `print-color-adjust: exact;` on `body` or `.page` to force browsers to render background colors/images during print.
- **Spaces in Image Paths:** URL-encode spaces in image paths (e.g. `Markting%20tools%20/` instead of `Markting tools /`) to prevent printing engines from failing to load assets.

## Verification

When printing from Chrome or Odoo:
1. Open the page and press `Ctrl+P` (or `Cmd+P` on Mac).
2. Set **Margins** to `None` (or `Default` if page-size is 210mm x 297mm).
3. Enable **Background graphics** under Options.
4. Verify that each section fits exactly onto its page without spilling onto page margins.
