# Odoo Website Menu Hierarchy & Ghost Menu Cleanup (Slides, Forum, Support)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `website`, `menu`, `website.menu`, `slides`, `forum`, `navigation`, `cro`, `b2b`

---

## Problem

When installing default website addons like `website_slides` or `website_forum` on an Odoo database, Odoo automatically injects menu items (`/slides`, `/forum`) into `website.menu` under the top navbar. In high-stakes B2B lead generation websites where these modules have no published content or courses, prospective clients see empty pages ("Courses 0", "Forum 0 posts"), creating an impression of an inactive or broken business. Furthermore, orphaned pages (`oe_structure oe_empty` templates or unpublished pages like `/about-us`) remain in navigation or cause 404 errors.

## Root Cause

`website.menu` records created by module data files attach directly to `website.menu` with `parent_id = top_menu_id`. Even when the corresponding backend channels or forums are empty or unpublished, the menu items may remain visible to public visitors unless explicitly unlinked, unpublished, or filtered out.

## Solution ✅

Use standard Odoo ORM / JSON-RPC to detach or unlink empty ghost menus, and restructure the navigation hierarchy with dropdown parent menus for industry/service offerings:

```python
# 1. Update existing core navigation items
website_id = 1
top_menu = env['website.menu'].search([('website_id', '=', website_id), ('parent_id', '=', False)], limit=1)

# 2. Create or find parent dropdown menu
sectors_menu = env['website.menu'].search([
    ('website_id', '=', website_id),
    ('name', '=', 'حلول القطاعات'),
    ('parent_id', '=', top_menu.id)
], limit=1)
if not sectors_menu:
    sectors_menu = env['website.menu'].create({
        'name': 'حلول القطاعات',
        'url': '#',
        'parent_id': top_menu.id,
        'website_id': website_id,
        'sequence': 30,
    })

# 3. Create child menus under the dropdown parent
submenus = [
    ('قطاع المقاولات والتشييد', '/odoo-for-contracting', 1),
    ('قطاع المصانع والإنتاج', '/odoo-for-manufacturing', 2),
    ('قطاع التجارة والتجزئة', '/odoo-for-retail', 3),
    ('قطاع الشركات والخدمات', '/odoo-for-services', 4),
]
for name, url, seq in submenus:
    existing = env['website.menu'].search([('website_id', '=', website_id), ('url', '=', url)], limit=1)
    if existing:
        existing.write({'parent_id': sectors_menu.id, 'sequence': seq})
    else:
        env['website.menu'].create({
            'name': name,
            'url': url,
            'parent_id': sectors_menu.id,
            'website_id': website_id,
            'sequence': seq,
        })

# 4. Safely unlink ghost menus that have 0 content
ghost_urls = ['/slides', '/forum', '/support', '/about-us']
ghost_menus = env['website.menu'].search([
    ('website_id', '=', website_id),
    ('url', 'in', ghost_urls)
])
ghost_menus.unlink()
```

## ⚠️ Pitfalls

- **Module Upgrade Re-creation**: If a module (e.g. `website_slides`) is upgraded (`-u website_slides`), Odoo's XML data loading might recreate the default menu item if `noupdate="0"`. If preserving the module is necessary, setting `is_visible = False` or removing the channel preserves data while keeping the navbar clean.
- **RTL & Mobile Offcanvas Drawer**: In dark-themed Odoo websites, Bootstrap's `.offcanvas.o_navbar_mobile` defaults to a light/white background, which creates a jarring visual flash on mobile devices. Always inject matching dark CSS for `.offcanvas.o_navbar_mobile` in `website.custom_code_head`.

## Verification

Check rendered HTML to confirm no ghost links and verify dropdown structure:

```bash
curl -s https://your-domain.com/ | grep -E "(/slides|/forum|/odoo-for-contracting)"
```

## References

- Odoo Official Documentation: `website.menu` model and Bootstrap navbar rendering.
