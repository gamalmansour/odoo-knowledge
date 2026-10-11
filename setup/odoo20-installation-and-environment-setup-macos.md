# Odoo 20.0 Environment Setup and Enterprise Installation on macOS (Apple Silicon)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 20.0                                       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-08                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo20`, `setup`, `macos`, `apple-silicon`, `python3.12`, `enterprise`

---

## Problem

When setting up Odoo 20.0 on macOS (Apple Silicon ARM64), the server fails or throws warnings with legacy configurations:
1. Python version: Odoo 20 upstream pins requirements against Python 3.12 (Debian 12 / Ubuntu 24.04 Noble base). Running with older versions (e.g., Python 3.8 or 3.11) misses pinned wheels or fails requirement evaluation.
2. Addons path validation: Odoo 20 strictly enforces that every directory in `addons_path` must contain at least one valid module (`__init__.py` and `__manifest__.py`), otherwise logging `WARNING: option addons_path, invalid addons directory ..., skipped`.
3. CLI options vs Config file: Options like `--dev=all` have `file_exportable=False` in `odoo/tools/config.py`. Adding `dev = all` directly into `.conf` causes `WARNING: unknown option 'dev' in the config file`.
4. Longpolling deprecation: `longpolling_port` is obsolete as WebSocket handling is natively integrated on `http_port`.

## Root Cause

- Odoo 20 core configuration parser strictly validates paths via `_is_addons_path` which scans subdirectories for `__init__.py` and `__manifest__.py`.
- Native gevent/greenlet and cryptography wheels require Python 3.12 ABI on modern macOS systems.
- WebSocket is unified with HTTP server under Werkzeug / h11.

## Solution ✅

### 1. Python 3.12 Virtual Environment
Install Python 3.12 via Homebrew and create `.venv`:
```bash
brew install python@3.12
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip setuptools wheel
```

### 2. Install Requirements
Export postgresql path so `psycopg2` builds correctly:
```bash
PATH="/opt/homebrew/Cellar/postgresql@18/18.3/bin:$PATH" .venv/bin/pip install -r requirements.txt
```

### 3. Addons Path & Custom Modules
Ensure `custom/` contains at least one starter module (with `__init__.py` and `__manifest__.py`) so Odoo's `_is_addons_path()` validates it without skipping.

### 4. Configuration File (`odoo20.conf`)
```ini
[options]
admin_passwd = 1
db_host = localhost
db_port = 5433
db_user = odoo
db_password = False
pg_path = /opt/homebrew/Cellar/postgresql@18/18.3/bin

addons_path = /Users/gamal/odoo/odoo20.0/odoo/addons,/Users/gamal/odoo/odoo20.0/addons,/Users/gamal/odoo/odoo20.0/enterprise,/Users/gamal/odoo/odoo20.0/custom

; Network
http_port = 2020

; Session isolation
data_dir = /Users/gamal/odoo/odoo20.0/data

; Default Database
db_name = odoo20_enterprise
```

### 5. Running Odoo 20
```bash
.venv/bin/python ./odoo-bin -c odoo20.conf
```

## ⚠️ Pitfalls

- Do NOT put `dev = all` in `odoo20.conf`. Use CLI argument `--dev=all` or `ODOO_DEV=all`.
- Do NOT use `longpolling_port` in `odoo20.conf` for Odoo 20.
- Make sure `data_dir` is isolated from Odoo 17/18/19 instances to prevent session cookie / filestore collisions.

## Verification

```bash
curl -sI http://localhost:2020/web/login
# Returns:
# HTTP/1.1 200 OK
# server: odoo/20.0 python-h11/... CPython/3.12.15
```

## References

- Odoo 20.0 Core `odoo/tools/config.py`
- Odoo 20.0 `requirements.txt`
