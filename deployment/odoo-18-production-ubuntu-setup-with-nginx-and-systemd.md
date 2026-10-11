# Odoo 18.0 Community Production Installation on Ubuntu 24.04/22.04 LTS

| Field         | Value                                                              |
|---------------|--------------------------------------------------------------------|
| Category      | deployment                                                         |
| Odoo Versions | 18                                                                 |
| Severity      | 🔴 Critical                                                        |
| Last Verified | 2026-09-26                                                         |
| Author        | ENG/Gamal Mansour                                                  |

**Tags:** `odoo18`, `deployment`, `ubuntu`, `nginx`, `systemd`, `postgresql`, `wkhtmltopdf`, `rtlcss`, `websocket`, `production`

---

## Problem

Deploying Odoo 18.0 Community on Ubuntu servers (especially Ubuntu 24.04 Noble Numbat) frequently encounters multiple critical failures:
1. `wkhtmltopdf` is removed from official Ubuntu 24.04 repos.
2. Missing `rtlcss` npm package breaks the Arabic UI layout with `A css error occured, using an old style to render this page`.
3. Running Odoo without a reverse proxy or with unconfigured websocket routing causes live chat, discuss, and bus notifications to fail or drop connections.
4. Unbounded log growth in `/var/log/odoo/` fills the root partition after several months, causing PostgreSQL to panic and crash.
5. In worker mode (`workers > 0`), omitting memory limits (`limit_memory_soft` and `limit_memory_hard`) or request limits leads to gradual memory exhaustion and unhandled OOM termination.

---

## Root Cause

- Ubuntu 24.04 removed Qt4/Qt5-patched `wkhtmltopdf` packages from standard apt mirrors.
- Odoo 18 relies on Node.js `rtlcss` for compiling dynamic RTL stylesheets.
- In multi-worker mode, Odoo divides traffic: standard HTTP runs on `http_port` (default 8069) while gevent/websocket connections run on `gevent_port` (default 8072). Nginx must route `/websocket` explicitly to 8072 with `Upgrade` and `Connection "upgrade"` headers.
- Long-running Python workers can experience memory fragmentation over time without worker recycling (`limit_request`).

---

## Solution ✅

Follow this automated and hardened architecture:

### 1. System Dependencies & Python Dev Headers
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
    curl wget git build-essential \
    python3-dev python3-pip python3-venv \
    libpq-dev libldap2-dev libsasl2-dev libssl-dev \
    libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev \
    libfreetype-dev liblcms2-dev libblas-dev libatlas-base-dev \
    nodejs npm nginx certbot python3-certbot-nginx logrotate ufw
```
*(Note: on Ubuntu 24.04 install `libmagic1t64`; on Ubuntu 22.04 install `libmagic1`)*

### 2. RTL-CSS (Global)
```bash
sudo npm install -g rtlcss
```

### 3. Wkhtmltopdf (Official Patched Qt Build)
```bash
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_amd64.deb -O /tmp/wkhtmltox.deb
sudo dpkg -i /tmp/wkhtmltox.deb || sudo apt-get install -f -y
rm -f /tmp/wkhtmltox.deb
```

### 4. Dedicated Isolated User & Directories
```bash
sudo useradd -m -d /opt/odoo18 -U -r -s /bin/bash odoo18
sudo -u odoo18 git clone --depth 1 --branch 18.0 https://github.com/odoo/odoo.git /opt/odoo18/odoo
sudo -u odoo18 python3 -m venv /opt/odoo18/venv
sudo -u odoo18 /opt/odoo18/venv/bin/pip install --upgrade pip wheel setuptools
sudo -u odoo18 /opt/odoo18/venv/bin/pip install -r /opt/odoo18/odoo/requirements.txt
sudo -u odoo18 /opt/odoo18/venv/bin/pip install psycopg2-binary phonenumbers pypdf cryptography pandas
```

### 5. PostgreSQL Database User
```bash
sudo apt-get install -y postgresql postgresql-client
sudo systemctl enable --now postgresql
sudo -u postgres createuser -s odoo18
```

### 6. Production Config (`/etc/odoo18.conf`)
```ini
[options]
admin_passwd = <SECURE_RANDOM_MASTER_PASSWORD>
db_host = False
db_port = False
db_user = odoo18
db_password = False
addons_path = /opt/odoo18/odoo/addons,/opt/odoo18/custom-addons
data_dir = /var/lib/odoo18
logfile = /var/log/odoo18/odoo18.log
log_level = info
proxy_mode = True
workers = 5
max_cron_threads = 2
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_request = 8192
limit_time_cpu = 600
limit_time_real = 1200
http_port = 8069
gevent_port = 8072
list_db = True
```

### 7. Nginx with Websocket Routing
```nginx
upstream odoo18_backend {
    server 127.0.0.1:8069;
}

upstream odoo18_chat {
    server 127.0.0.1:8072;
}

server {
    listen 80;
    server_name yourdomain.com;
    client_max_body_size 100M;

    proxy_read_timeout 3600;
    proxy_connect_timeout 3600;
    proxy_send_timeout 3600;

    location /websocket {
        proxy_pass http://odoo18_chat;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://odoo18_backend;
        proxy_redirect off;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location ~* /[^/]+/static/ {
        proxy_cache_valid 200 60m;
        proxy_buffering on;
        expires 864000;
        proxy_pass http://odoo18_backend;
    }
}
```

---

## ⚠️ Pitfalls

1. **Missing `proxy_mode = True`:** If missing from `odoo.conf`, client IP addresses recorded in logs and audit trails will always be `127.0.0.1`, breaking session cookies and geo-restrictions.
2. **Websocket Upstream:** Directing `/websocket` to 8069 instead of 8072 in multi-worker mode breaks instant messaging notifications.
3. **Log Rotation:** Missing `/etc/logrotate.d/odoo18` can cause disk exhaustion within 3-6 months. Always use `copytruncate`.
4. **Port Exposure:** Leaving ports 8069 and 8072 open to the public internet allows bypassing Nginx protections. Close them with UFW and expose only 80 and 443.

---

## Verification

```bash
# Check Odoo service
sudo systemctl status odoo18

# Check Nginx config & status
sudo nginx -t
sudo systemctl status nginx

# Verify wkhtmltopdf
wkhtmltopdf --version

# Verify rtlcss
rtlcss --version

# Test HTTP and Websocket endpoints
curl -I http://127.0.0.1:8069
```

---

## References

- [Odoo Official 18.0 Installation Guide](https://www.odoo.com/documentation/18.0/administration/on_premise/packages.html)
- Related: `setup/system-dependencies-ubuntu.md`, `setup/wkhtmltopdf-not-in-ubuntu-repos.md`, `setup/missing-rtlcss-css-error.md`
