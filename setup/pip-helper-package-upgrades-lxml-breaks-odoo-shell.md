# pip Installing a Helper Package into the Odoo venv Silently Upgrades lxml and Breaks odoo-bin

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All (hit on 19, Python 3.11)               |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `pip`, `lxml`, `lxml_html_clean`, `dependencies`, `venv`, `odoo-bin`, `shell`

---

## Problem

After `pip install <some-helper-package>` (e.g. `ddgs` for image search) into the same
pyenv/venv that runs Odoo, `odoo-bin` (including `odoo-bin shell`) crashes on startup:

```
File ".../lxml/html/clean.py", line 18, in <module>
    raise ImportError(
ImportError: lxml.html.clean module is now a separate project lxml_html_clean.
Install lxml[html-clean] or lxml_html_clean directly.
```

## Root Cause

The helper package declared an unpinned `lxml` dependency, so pip **upgraded lxml 4.9.3 → 6.x**
in place. From lxml 5, `lxml.html.clean` was split out into the separate `lxml_html_clean`
project, and Odoo's requirements only add `lxml-html-clean` for `python_version >= '3.12'`
(where lxml 5+ is pinned). On Python 3.11 Odoo pins `lxml==4.9.3` and expects the built-in
clean module — the silent upgrade breaks that contract.

## Solution ✅

If the helper package was a one-off tool (our case — images already downloaded), restore the
exact previous state:

```bash
pip uninstall -y ddgs primp lxml_html_clean
pip install "lxml==4.9.3"          # match requirements.txt pin for your Python version
python3 -c "import lxml.html.clean; print('ok')"
```

If you must keep the helper package permanently, keep the new lxml and add the shim instead:

```bash
pip install lxml_html_clean
```

(Odoo supports lxml 5/6 on newer Pythons, so this combination works — but you're now off the
pinned versions for your Python, so test report rendering/HTML sanitization.)

## ⚠️ Pitfalls

- `pip install` prints the upgrade in its output but it scrolls by — nothing warns you that an
  Odoo-pinned dependency was replaced.
- The breakage only appears on the NEXT `odoo-bin` start, possibly days later, looking totally
  unrelated to the helper install.
- Check `requirements.txt` — the lxml pin is **per Python version** (`4.9.3` on 3.11, `5.2.1` on
  3.12, `6.x` on 3.14+); restore the one matching your interpreter.
- Prefer installing one-off tooling with `pipx` / a separate venv instead of the Odoo venv.
- macOS + pyenv reminder: `python3`/`pip` resolve per-cwd via `.python-version` — make sure you
  are inspecting the same interpreter Odoo actually uses.
