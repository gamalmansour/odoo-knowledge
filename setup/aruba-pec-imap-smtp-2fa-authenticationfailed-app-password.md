# Aruba PEC (`@pec.it`) IMAP/SMTP Configuration & `[AUTHENTICATIONFAILED]` 2FA App Password Resolution

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-11                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `fetchmail.server`, `ir.mail_server`, `aruba`, `pec.it`, `imaps.pec.aruba.it`, `smtps.pec.aruba.it`, `AUTHENTICATIONFAILED`, `l10n_it_edi`, `2fa`, `app-password`

---

## Problem

When configuring an Italian **Aruba PEC (`@pec.it`)** mailbox in Odoo (`Settings -> Technical -> Incoming Mail Servers` or `Outgoing Mail Servers`), two errors commonly occur:

1. **Typo in IMAP hostname (`maps.pec.aruba.it` instead of `imaps.pec.aruba.it`):**
```text
No response received. Check server information.
 -2
Name or service not known
```

2. **Valid Webmail password rejected by IMAP/SMTP when 2FA is active:**
```text
Server replied with following exception:
 b'[AUTHENTICATIONFAILED] Authentication failed.'
```

## Root Cause

1. **Server Hostnames:** Aruba PEC's official IMAP SSL endpoint is `imaps.pec.aruba.it` (Port `993`, SSL/TLS), which is a CNAME to `imaprid.arubapec.it`. Missing the leading `i` (`maps.pec.aruba.it`) triggers a Linux DNS lookup failure (`Errno -2: Name or service not known`).
2. **2FA (`Verifica in 2 passaggi`) Enforcement on Aruba PEC:** Once Two-Factor Authentication is enabled on an Aruba PEC mailbox, Aruba's IMAP/POP3/SMTP servers strictly block the main Webmail password for external clients (such as Odoo, Outlook, Thunderbird) and require generating a dedicated **"Password per programmi di posta"** (App Password) from the official Aruba PEC account portal (`https://account.aruba.it/pec`).

## Solution ✅

### Step 1: Verified Aruba PEC Server Parameters for Odoo

| Direction | Odoo Model | Server Type | Server Name | Port | Security |
|---|---|---|---|---|---|
| **Incoming (IMAP)** | `fetchmail.server` | IMAP Server | `imaps.pec.aruba.it` | `993` | `SSL/TLS` ✅ |
| **Incoming (POP3)** | `fetchmail.server` | POP Server | `pop3s.pec.aruba.it` | `995` | `SSL/TLS` ✅ |
| **Outgoing (SMTP)** | `ir.mail_server` | SMTP | `smtps.pec.aruba.it` | `465` | `SSL/TLS` ✅ |

### Step 2: Generate the Dedicated "Password per programmi di posta" (App Password)

1. Log in to the official Aruba PEC Account Management portal:
   - **Live Verified URL:** `https://account.aruba.it/pec`
2. Authenticate using the full `@pec.it` email address, main password, and approve the **2FA push notification / OTP** on the **Aruba PEC** mobile app.
3. In the left sidebar under **Sicurezza** (Security), select **Password per programmi di posta** (Mail client password).
4. Click **Attiva** (or **Genera nuova password**).
   - *Note:* If a warning states that external mail protocols are disabled, open `https://webmail.pec.it` -> Settings (`#settings`) and enable **IMAP / SMTP** access.
5. Copy the generated password (shown only once, valid for 6 months) and paste it into the **Password** field in Odoo's Incoming (`fetchmail.server`) and Outgoing (`ir.mail_server`) Mail Server records.
6. Click **Test & Confirm** in Odoo — status transitions to **`Confirmed`**.

## ⚠️ Pitfalls

- **Dead Portal URL Trap:** Do **NOT** send clients `https://gestione.pec.it` (does not resolve in DNS). Always verify external portal URLs via `curl -ILs` first:
  - Account & App Password Portal: `https://account.aruba.it/pec` (`HTTP 200 OK`)
  - Webmail & Protocol Settings: `https://webmail.pec.it` (`HTTP 200 OK`; `https://gestionemail.pec.it` redirects here)
- **6-Month Expiration:** Aruba PEC's generated `Password per programmi di posta` typically expires after **6 months**. If Odoo suddenly stops fetching/sending PEC emails with `AUTHENTICATIONFAILED` after 6 months, regenerate the App Password from `https://account.aruba.it/pec`.

## Verification

```bash
# Verify DNS & SSL Certificate of Aruba PEC IMAP Server
host -t MX pec.it && host imaps.pec.aruba.it
openssl s_client -connect imaps.pec.aruba.it:993 -crlf </dev/null 2>/dev/null | grep -E "subject=|issuer="

# Verify Aruba PEC Portal URLs are live (HTTP 200 OK)
curl -ILs "https://account.aruba.it/pec" | grep -E "HTTP/"
curl -ILs "https://webmail.pec.it" | grep -E "HTTP/"
```

## References

- [Official Aruba Guide — Come generare la password PEC per programmi di posta con 2FA](https://guide.aruba.it/pec/account-e-sicurezza/password/generare-password-programmi-posta)
- [Aruba PEC Account Management Portal](https://account.aruba.it/pec)
