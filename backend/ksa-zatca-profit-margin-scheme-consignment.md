# KSA ZATCA Profit Margin Scheme (Art. 48) & Consignment VAT in Odoo

- **Category:** `backend`
- **Odoo Versions:** `17.0`, `18.0`, `19.0`, `20.0`
- **Last Verified:** `2026-11-24`
- **Official Source:** ZATCA VAT Implementing Regulations — Article 48 (Profit Margin Method for Eligible Used Goods) & Article 53 (Tax Invoicing):
  - AR: https://zatca.gov.sa/ar/RulesRegulations/Taxes/Pages/default.aspx
  - EN: https://zatca.gov.sa/en/RulesRegulations/Taxes/Pages/default.aspx

## Problem / Business Context
When implementing Odoo for Saudi businesses trading in **pre-owned / second-hand luxury goods or vehicles** (both **Bought Outright** and **Consignment**):
1. Standard Odoo applies 15% VAT on the **full selling price** (e.g., `5,000 SAR → 652.17 SAR VAT`), whereas **KSA VAT Implementing Regulations Article 48** allows eligible used goods purchased from non-taxable individuals (with 0 deductible input VAT) to be taxed at **`15/115` of the profit margin only** (`Selling 5,000 - Vendor Price 4,000 = 1,000 Margin → 130.43 SAR VAT`, `869.57 SAR Net Margin`).
2. Applying a standard 15% *tax-excluded* tax on the rounded net margin (`869.57 * 1.15 = 1,000.0055 → 1,000.01`) causes a **`0.01 SAR` halala rounding drift** on the invoice total (`5,000.01` instead of `5,000.00`).
3. Mixing **Bought Outright** (Principal — Inventory Asset `IAS 2` + Gross Revenue `IFRS 15`) and **Consignment** (Agent — `owner_id` 0 Balance Sheet inventory + Commission Revenue + Vendor Clearing Liability) corrupts both the Balance Sheet and P&L.

## Solution ✅
1. **Use a Dedicated 15% Tax-Included Margin Tax (`price_include_override = 'tax_included'`):**
   - Split the Margin-Scheme Invoice into two lines:
     - **Line 1 (0% / No Tax — Principal / Cost Portion):** `agreed_vendor_price` (e.g., `4,000.00 SAR`).
       - If **Bought Outright:** posts to Pre-Owned Sales Revenue (e.g., `403000`); COGS posts to `505000` on delivery/invoicing.
       - If **Consignment:** posts to **Consignment Vendor Clearing Liability** (e.g., `212200`, reconcilable) — cleared when paying the vendor after buyer settles in full.
     - **Line 2 (15% Tax-Included — Profit Margin):** `margin_gross` (e.g., `1,000.00 SAR`) with `price_include_override = 'tax_included'` tax.
       - Odoo computes **exact** `VAT = 130.43 SAR` (to `251000 Tax Received`), `Net Margin = 869.57 SAR` (to `403000` or `404000 Consignment Commission`), and **exact** `Invoice Total = 5,000.00 SAR` (zero halala drift!).
2. **Inventory Ownership (`stock.quant.owner_id`):**
   - Receive Bought Outright items into a dedicated LMB-owned location (FIFO + Perpetual valuation → Inventory Asset `110110`).
   - Receive Consignment items via an official Stock Receipt (`stock.picking`) into a Consignment location with **`owner_id = vendor_id`** (zero Balance Sheet valuation per IAS 2).
3. **Configurable Eligibility Flag (`margin_scheme_eligible`):**
   - Always include a boolean toggle per item (`margin_scheme_eligible`) because ZATCA requires prior approval and specific item eligibility confirmation from the client's Saudi tax advisor.

## ⚠️ Pitfalls
- **Prior ZATCA Approval Required:** Article 48 cannot be applied without formal ZATCA approval and confirming the item category qualifies as eligible used goods; if any condition is violated, ZATCA requires 15% VAT on the full selling price.
- **Invoice Disclosure (Art. 48 & 53):** The buyer's tax invoice must state that VAT is calculated under the Profit Margin Method and must not show VAT as deductible input tax to the buyer.
- **POS Trap:** Standard Odoo POS applies 15% VAT on the full product price and does not link consignment vendor payout gates — sell margin-scheme / consignment bags through a dedicated Boutique Showcase / Intake sale flow, reserving standard POS for regular 15% retail accessories.
