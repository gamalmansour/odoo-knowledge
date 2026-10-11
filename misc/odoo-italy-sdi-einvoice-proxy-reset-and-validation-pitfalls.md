# Italian E-Invoicing (SdI / FatturaPA): Proxy Client Reset, Anagrafe Tributaria & Cross-Border Validation

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-08                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `sdi`, `fatturapa`, `l10n_it`, `l10n_it_edi`, `e-invoice`, `italy`, `proxy-client`, `anagrafe-tributaria`, `iap`, `export-check`

---

## Problem

When setting up and testing Italian electronic invoicing (`l10n_it_edi` via Odoo Access Point / IAP to the Italian Tax Authority **SdI - Sistema di Interscambio**), developers and implementers encounter a chain of blocking errors:

1. **Proxy Signature / DB Duplicate Error:**
```
Error uploading the e-invoice file IT...
Invalid signature for request. This might be due to another connection to odoo Access Point server. It can occur if you have duplicated your database.
```
Or when changing mode:
```
The company has already registered with the service as 'Test' or 'Official', it cannot change.
```

2. **Schema Rejection on Individual Customers:**
```
The e-invoice has been refused by the SdI.
File non conforme al formato : The content of element 'Anagrafica' is not complete. One of '{Cognome}' is expected. riga: 52 - colonna: 22
```

3. **Tax ID / Codice Fiscale Missing Pre-Check Error:**
```
Errors occurred while creating the e-invoice file:
- Partner(s) should have a VAT number or Codice Fiscale.
- Partner(s) should have a complete address, verify their Street, City, Zipcode and Country.
```

4. **Live Production Anagrafe Tributaria Rejection:**
```
The e-invoice has been refused by the SdI.
1.4.1.2 <CodiceFiscale> non valido : MRTMTT91D08F205J
```

---

## Root Causes

1. **Stale Proxy User & Duplicate Encryption Keys:**
   Odoo registers the company with Odoo's IAP Access Point (`account_edi_proxy_client.user`) using an RSA public/private key pair stored on the server/DB. If a database is duplicated or restored from backup, the private key signature mismatch causes Odoo IAP to reject the connection with 401/Invalid Signature.
2. **Individual Name Splitting (`Nome` vs `Cognome`):**
   In the Italian FatturaPA XML Schema, when `partner.is_company == False`, `<Anagrafica>` strictly requires both `<Nome>` and `<Cognome>`. Odoo extracts `first_name` and `last_name` by splitting `partner.name.split()`. If the partner name has only a single word (e.g. `test`), `last_name` is empty, causing SdI schema validation to fail.
3. **Internal Export Checks on Partners:**
   In `account.move._l10n_it_edi_export_data_check()`:
   - For all full invoices, Odoo requires `street` (or `street2`), `city`, `zip`, and `country_id`.
   - Odoo checks `('vat', 'l10n_it_codice_fiscale')`. If both are empty, Odoo blocks XML generation. Furthermore, `@api.onchange('vat')` resets `l10n_it_codice_fiscale = False` if `vat` is cleared.
4. **SdI Production Database Verification (Anagrafe Tributaria):**
   In Official mode, SdI doesn't merely validate the 16-character format and Luhn/parity checksum. SdI queries the real Italian national tax registry (**Anagrafe Tributaria**). Fictitious/dummy placeholder codes (such as `MRTMTT91D08F205J`) are rejected with Error **00306** (`CodiceFiscale non valido`).

---

## Solution ✅

### 1. Resetting Proxy Client Credentials (The Deadlock / Catch-22 Resolution)
When `Invalid signature for request` occurs due to an expired/desynchronized token, Odoo enters a classic Catch-22:
- Calling `_renew_token()` fails with `Invalid signature for request` (because the server rejects the dead token used to sign the renewal).
- Unlinking the proxy user and re-registering via UI fails with `A user already exists with this identification` (because Odoo IAP central server refuses duplicate company Codice Fiscale).

**The Proven Workaround (No Odoo Support Ticket Needed):**
1. Unlink the dead proxy user:
```python
env['account_edi_proxy_client.user'].sudo().search([('proxy_type', '=', 'l10n_it_edi')]).unlink()
# In V18+, also remove any dangling keys:
if 'certificate.key' in env:
    env['certificate.key'].sudo().search([('name', 'ilike', 'l10n_it_edi%')]).unlink()
```
2. In **Settings → Companies → [Company]**, temporarily change **Codice Fiscale** to a unique, valid 16-character Italian personal tax code with valid checksum (e.g. the legal representative's CF). *Do NOT use public test codes like `MRTMTT91D08F205J` as they may already be registered on the IAP server.*
3. In **Accounting → Settings → Italian Electronic Invoicing**, select **Official**, tick **Allow Odoo to process invoices**, and click **Save**. The IAP server registers a brand new `id_client` and issues a fresh, active `refresh_token`.
4. Immediately return to **Settings → Companies → [Company]** and restore the company's original 11-digit Codice Fiscale / VAT (e.g. `14472720961`).
5. Outbound invoices will now transmit through the newly authorized proxy client, while the generated XML properly reflects the company's real tax identity. SdI validates and accepts the invoice cleanly.


### 2. Ensuring Individual Customer Names Split Correctly
Always ensure the customer name contains at least two words (First name + Surname):
- ❌ Bad: `Test` (generates only `<Nome>Test</Nome>`, missing `<Cognome>`)
- ✅ Good: `Mario Rossi` or `Test Client` (generates `<Nome>Test</Nome><Cognome>Client</Cognome>`)

### 3. Testing Real Italian B2C vs B2B vs Cross-Border (Estero)
- **Italian B2C (Consumer):**
  - Name: Two-word name
  - Country: `Italy`
  - Codice Fiscale: Must be a **real, living citizen's Codice Fiscale** registered in Anagrafe Tributaria (e.g. the company owner's or representative's CF).
  - Tax ID: Empty.
  - Codice Destinatario: `0000000`.
- **Italian B2B (Company):**
  - Customer Type: Company
  - Country: `Italy`
  - Tax ID (P.IVA) & Codice Fiscale: Must be a valid, active Italian business (e.g. `01114601006` for Poste Italiane S.p.A.).
  - Codice Destinatario: Partner's 7-character code (or `0000000` / PEC).
- **Cross-Border / Foreign Guest (e.g. Vacation Rentals, Tourists, EU/Non-EU):**
  - Address: Fill all 4 fields (`Street`, `City`, `ZIP`, `Country`).
  - Country: Foreign Country (e.g. `Germany`, `France`, `US`).
  - Tax ID: Valid foreign VAT (e.g. `DE129273398`) or `NA` if consumer without VAT.
  - Codice Destinatario: Automatically set to `XXXXXXX`.
  - SdI accepts foreign invoices directly without querying Anagrafe Tributaria.

---

## ⚠️ Pitfalls

- **Do NOT Issue Credit Notes for Rejected Invoices:** Under Italian law, an invoice rejected by SdI (`SdI Rejected`) is legally non-existent. **Do not create a Credit Note**. Simply click **Reset to Draft**, delete the rejected XML attachment, correct the data, and re-send with the exact same invoice number within 5 days.
- **Third-Party EDI Modules:** Third-party modules (such as `electra_fatturazione_elettronica`) may override `l10n_it_edi` settings and inject non-standard transmission protocols. Uninstall conflicting modules before using standard Odoo IAP.
- **VAT Onchange Wipeout:** Changing or clearing the `vat` field will trigger `_l10n_it_onchange_vat()` which sets `l10n_it_codice_fiscale = False`. Always check `Codice Fiscale` after editing `Tax ID`.

---

## Verification

1. Go to **Accounting → Customers → Invoices**.
2. On invoice, click **Send & Print** with **E-invoice XML** checked.
3. Verify in Chatter:
   > *"The e-invoice file IT... was sent to the SdI for validation."*
4. Click **Fetch notifications** after 1-3 minutes.
5. Status changes to:
   > *"The e-invoice file IT... was accepted and successfully forwarded to [Partner] by the SdI."*
   Badge displays **Accepted by SdI** (or **Delivered**).

---

## References

- Agenzia delle Entrate Technical Specifications: `FatturaPA v1.2`
- SdI Error Code Dictionary: Error 00306 (`CodiceFiscale non valido`)
- Odoo source module: `addons/l10n_it_edi`
