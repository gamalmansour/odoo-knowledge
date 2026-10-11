# Legacy .less Files in web.assets Crash Bundle Compilation with Missing 'lessc'

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | frontend                                   |
| Odoo Versions | 16, 17, 18                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-05                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `assets`, `lessc`, `scss`, `web.assets_web`, `bundle`, `ui-crash`

---

## Problem

After installing custom or migrated third-party modules (such as legacy OpenEduCat or community themes), the Odoo backend webclient UI is completely broken:
- The background is plain white and typography falls back to serif (Times New Roman).
- App switcher icons render vertically stacked and huge (e.g., full native size 512x512 px) instead of the standard 60px/70px responsive grid.
- No Bootstrap styles or grid classes (`.row`, `.col-*`) are applied.
- The compiled asset stylesheet `/web/assets/.../web.assets_web.min.css` contains an error banner:

```css
/* ## CSS error message ##*/
body::before {
  font-weight: bold;
  content: "A css error occured, using an old style to render this page";
  position: fixed;
  left: 0;
  bottom: 0;
  z-index: 100000000000;
  background-color: #C00;
  color: #DDD;
}

css_error_message {
  content: "Could not execute command 'lessc'This error occurred while compiling the bundle 'web.assets_web' containing: ...";
}
```

## Root Cause

Odoo deprecated LESS support in favor of SCSS starting in v12/v13. In modern Odoo (v16+ and v17+), when an asset path ending with `.less` is registered in `__manifest__.py` under `assets` (e.g. in `web.assets_backend`), Odoo's asset compiler attempts to compile it by executing the system command `lessc` via Python `subprocess`.

If `lessc` (the Node.js LESS compiler) is not installed on the server (the standard situation on macOS, dev environments, and standard Odoo Docker/Debian setups), the compiler fails with `CompileError: Could not execute command 'lessc'`. Because asset compilation is all-or-nothing per bundle, this single error causes the entire `web.assets_web` / `web.assets_backend` stylesheet to fail, returning an empty/error stub to the client browser.

## Solution ✅

1. **Locate the offending `.less` file in the addon:**
   ```bash
   grep -rn "\.less" addons_path/
   ```

2. **Convert the file to SCSS:**
   Most legacy LESS files in Odoo modules are simply nested CSS rules, which are 100% valid SCSS.
   Rename or move the file to `static/src/scss/`:
   ```bash
   mv module_name/static/src/less/style.less module_name/static/src/scss/style.scss
   ```

3. **Update the module `__manifest__.py`:**
   Change the path from `.less` to `.scss`:
   ```python
   'assets': {
       'web.assets_backend': [
           'module_name/static/src/scss/style.scss',
       ],
   },
   ```

4. **Clear corrupted asset attachments & recompile:**
   ```python
   # In Odoo shell:
   env['ir.attachment'].search([('url', 'like', '/web/assets/%')]).unlink()
   ```

5. **Restart Odoo and Hard Refresh Browser:**
   Perform a hard reload (`Ctrl+Shift+R` / `Cmd+Shift+R`) to clear the cached CSS error bundle from the browser.

## ⚠️ Pitfalls

- **Browser HTTP Cache:** Browsers aggressively cache the error CSS response. Even after fixing the file, always perform a hard refresh or test in an incognito window.
- **Do NOT install `lessc` as a workaround:** Adding node-less to the host is fragile and keeps deprecated tech alive. Always migrate `.less` to `.scss` so Odoo compiles it natively using `libsass`.

## Verification

Run a test query in Odoo shell to verify the bundle compiles with full CSS length without error:

```python
bundle = env['ir.qweb']._get_asset_bundle('web.assets_web')
css = bundle.css()
print("Compiled successfully! Attachment count:", len(css), "File:", css[0].url)
```

## References

- Related file: `frontend/owl-client-action-scrolling.md`
