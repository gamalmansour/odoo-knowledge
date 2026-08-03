# wkhtmltopdf Not Available in Ubuntu 24.04+ Repos (nor Homebrew on macOS)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All (15, 16, 17, 18, 19)                   |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-03                                 |
| Author        | ENG/Mohamed Saber (macOS: ENG/Gamal Mansour) |

**Tags:** `wkhtmltopdf`, `pdf`, `reports`, `ubuntu`, `apt`, `deb`, `macos`, `homebrew`, `rosetta`

---

## Problem

`wkhtmltopdf` is required by Odoo for PDF report generation. Starting from Ubuntu 24.04 (Noble) and later (25.10 Resolute, 26.04), it is **NOT available** in the official apt repositories.

```
Package wkhtmltopdf is not available, but is referred to by another package.
This may mean that the package is missing, has been obsoleted, or
is only available from another source

Error: Package 'wkhtmltopdf' has no installation candidate
```

## Root Cause

`wkhtmltopdf` was removed from the official Ubuntu repositories starting with Noble (24.04). The wkhtmltopdf project provides its own `.deb` packages via GitHub releases.

## Solution ✅

Download and install the `.deb` package from the official GitHub releases:

```bash
# Download (Jammy build works on all newer Ubuntu versions)
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_amd64.deb -O /tmp/wkhtmltox.deb

# Install
sudo dpkg -i /tmp/wkhtmltox.deb

# Fix any missing dependencies
sudo apt install -f -y

# Cleanup
rm /tmp/wkhtmltox.deb
```

## Solution ✅ — macOS (verified 2026-08-03 on Apple Silicon)

Symptom in the UI: *"Unable to find Wkhtmltopdf on this system. The report
will be shown in html."* — it appears in **every database** because the
binary lives on the machine, not in the DB.

Homebrew no longer ships it (`brew info --cask wkhtmltopdf` →
`No Cask with this name exists`; upstream is unmaintained). Use the official
`.pkg` from the same GitHub releases:

```bash
curl -L -o ~/Downloads/wkhtmltox.pkg https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-2/wkhtmltox-0.12.6-2.macos-cocoa.pkg
sudo installer -pkg ~/Downloads/wkhtmltox.pkg -target /
wkhtmltopdf --version   # -> wkhtmltopdf 0.12.6 (with patched qt)
```

- The pkg is **x86_64** — on Apple Silicon it runs through **Rosetta 2**.
  Check with `arch -x86_64 /usr/bin/true`; install Rosetta first with
  `softwareupdate --install-rosetta` if that fails.
- Installs to `/usr/local/bin/wkhtmltopdf` (+`wkhtmltoimage`), already on PATH.
- Restart Odoo afterwards; the boot log should print
  `Will use the Wkhtmltopdf binary at /usr/local/bin/wkhtmltopdf`.
- **Odoo.sh / Odoo Online are never affected** — the platform preinstalls it;
  this is a local-dev problem only.

## ⚠️ Pitfalls

- **Use the `jammy` (22.04) build** — it works on Noble (24.04), Resolute (25.10), and newer. Don't look for version-specific builds.
- **This installs BOTH `wkhtmltopdf` and `wkhtmltoimage`** — the package is called `wkhtmltox` (with an X).
- **It will auto-install `xfonts-75dpi`** as a dependency — this is normal and needed for proper font rendering.
- **Don't install `wkhtmltopdf` via pip or snap** — Odoo specifically needs the Qt-patched version from this GitHub release.

## Verification

```bash
wkhtmltopdf --version
# Expected: wkhtmltopdf 0.12.6.1 (with patched qt)
```

## References

- Official releases: https://github.com/wkhtmltopdf/packaging/releases
- Odoo docs on wkhtmltopdf: https://www.odoo.com/documentation/19.0/administration/install/install.html
