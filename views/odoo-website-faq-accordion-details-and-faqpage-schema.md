# Odoo Website FAQ Accordions via HTML5 `<details>` & `FAQPage` Schema Injection

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All (14, 15, 16, 17, 18, 19)              |
| Severity      | 🟢 Low                                     |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `seo`, `schema`, `faq`, `faqpage`, `rich-snippets`, `website`, `qweb`, `details`

---

## Problem

Building accordion FAQ sections in Odoo Website Builder often relies on heavy Bootstrap JS collapse components (`data-bs-toggle="collapse"`) or third-party jQuery plugins that can cause conflicts during PJAX page transitions, or break accessibility and search engine crawler extraction. Furthermore, without Google-compliant `FAQPage` JSON-LD Structured Data, the website misses out on massive SERP visibility (expandable accordion rich snippets on Google Page 1).

## Root Cause

Bootstrap collapse attributes require unique element IDs and event bindings. In Odoo's dynamic website environment, IDs often get duplicated during copy-paste or snippet drops, leading to broken toggle behavior. Moreover, standard Odoo views do not output schema markup for custom FAQs automatically.

## Solution ✅

Use native HTML5 `<details>` and `<summary>` elements styled with modern CSS (glassmorphism/dark theme) for zero-JS accordions, paired with an exact matching `FAQPage` JSON-LD schema injected into `website.custom_code_head`:

```html
<!-- 1. Native HTML5 Zero-JS Accordion in QWeb Arch -->
<section id="faq" class="faq-section">
    <div class="faq-accordion">
        <details class="faq-item">
            <summary class="faq-question">
                <span>ما هي تكلفة تطبيق نظام Odoo ERP في مصر؟</span>
                <span class="faq-icon">▾</span>
            </summary>
            <p class="faq-answer">
                تعتمد تكلفة تطبيق Odoo على حجم نشاط شركتك وعدد المستخدمين...
            </p>
        </details>
    </div>
</section>
```

```html
<!-- 2. JSON-LD Schema in website.custom_code_head -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "ما هي تكلفة تطبيق نظام Odoo ERP في مصر؟",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "تعتمد تكلفة تطبيق Odoo على حجم نشاط شركتك وعدد المستخدمين..."
      }
    }
  ]
}
</script>
```

## ⚠️ Pitfalls

- **Text Consistency**: Google strictly enforces that the text in `acceptedAnswer.text` must match the visible text on the page verbatim. Discrepancies between visible text and schema can lead to Google ignoring the structured data.
- **RTL Support**: When implementing accordions in Arabic, ensure `dir="rtl"` is applied and summary flexbox uses `justify-content: space-between` so the arrow indicator appears correctly on the left side of the title.

## Verification

Test the page URL with Google Rich Results Test tool or inspect `<head>` for valid JSON-LD:
```bash
curl -s https://your-domain.com/ | grep -A 10 "FAQPage"
```
