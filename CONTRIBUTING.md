# Contributing to Odoo & Enterprise Engineering Knowledge Base

## ⚡ For AI Agents (Antigravity / Gemini / Claude) — Mandatory Workflow

> **CRITICAL CONTEXT RULE:** Do **NOT** read the full `README.md` into your context window. Always use the local sub-20ms **SQLite FTS5 BM25** query CLI (`./kb`) to search and filter by Odoo version.

1. **Step 1 — Pull Latest (Before Starting Any Task):**
   ```bash
   git -C {workspace}/odoo-knowledge pull origin main
   ```
2. **Step 2 — Query via `./kb` Local Search Engine:**
   ```bash
   ./odoo-knowledge/kb "<model_name_or_keyword_or_error>" -v <detected_odoo_version>
   ```
   - Supports boolean queries (`AND`, `OR`, `NOT`), category filters (`-c orm`), tag filters (`-t odoo18`), and output formats (`-f text|markdown|compact|json`).
3. **Step 3 — Read Matching Entries:**
   Read only the matching `.md` files returned by `./kb`. Pay strict attention to **Solution ✅**, **⚠️ Pitfalls**, and **Odoo Versions**.
4. **Step 4 — Contribute Back & Auto-Regenerate Index:**
   - **Existing accurate entry:** No changes needed.
   - **Improved fix or new pitfall found:** Update the `.md` file and bump `Last Verified`.
   - **New problem solved:** Create a new `.md` file from `TEMPLATE.md` in the appropriate category folder.
   - **Rebuild Index & README automatically:**
     ```bash
     python3 {workspace}/odoo-knowledge/tools/kb_indexer.py --force --update-readme
     ```
5. **Step 5 — Commit & Push:**
   ```bash
   git -C {workspace}/odoo-knowledge add -A
   git -C {workspace}/odoo-knowledge commit -m "📝 [CATEGORY] Brief description of what was added/updated"
   git -C {workspace}/odoo-knowledge push origin main
   ```

---

## 📂 Category Directory Structure

### Part I — Odoo ERP Core & Enterprise Architecture
- `setup/` — Installation, configuration, environment, OS dependencies, multi-instance setups, pre-sales seeding
- `database/` — PostgreSQL administration, `datdba` ownership, `unaccent_schema`, safe truncation, DB lifecycle
- `orm/` — Models, fields, `@api.depends`, `@api.constrains`, CRUD overrides, domain business logic
- `views/` — XML views (Form, List, Kanban, Search, Gantt), QWeb PDF reports, actions, XPath
- `frontend/` — OWL 2/3 components, JS widgets, POS screens, Portal JS, WebGL/Canvas client actions
- `backend/` — HTTP/JSON-RPC controllers, REST auth, `TransactionCase`/`HttpCase` testing, server actions, hardware bridges
- `security/` — Access rights (`ir.model.access.csv` / `ir.access.csv`), record rules (`ir.rule`), groups, multi-company
- `performance/` — Query optimization, N+1 prevention, batch engines, PostgreSQL window functions, caching
- `upgrade/` — Version migrations (Odoo 15 → 20), breaking API changes, code replacement cookbooks
- `data_migration/` — Complex Excel/CSV imports, header auto-mapping, relational resolution, ETL pipelines
- `deployment/` — Server provisioning (Ubuntu/Nginx/Systemd), SSL, Docker, zero-downtime upgrade safety
- `Best Practices/` — ERP architecture, Saudi (ZATCA, Etimad, GTPL, SBC, Wafi, Nitaqat) & Egyptian compliance, audit protocols
- `misc/` — Localization (`i18n`/`.po`), e-invoicing (ZATCA/SdI), Salla webhooks, SEO sitemaps, Odoo Apps Store assets

### Part II — Cross-Platform, Mobile & Game Engine R&D
- `cross_platform/` — Isolated non-Odoo R&D: Unity 6 (URP, IL2CPP, Mecanim, Action-RPG), Flutter iOS physical device deployment, Mobile Arabic BiDi, and media pipelines

---

## 🏷️ Naming & Metadata Conventions

- Use descriptive `kebab-case.md` filenames (e.g., `odoo18-product-type-storable-migration-silent-zero-stock-trap.md`).
- Fill in all metadata fields from `TEMPLATE.md`:
  - `Category`: Must match the folder name.
  - `Odoo Versions`: Explicit version list (`16, 17, 18, 19`, `19, 20`, `All`, or `N/A (Unity 6 / Cross-Platform)` for `cross_platform/` entries).
  - `Severity`: `🔴 Critical`, `🟡 Medium`, or `🟢 Low`.
  - `Last Verified`: `YYYY-MM-DD`.
  - `Author`: `ENG/Gamal Mansour`.
  - `Tags`: Comma-separated backtick tags.
- Never manually hand-number rows in `README.md` — always run `python3 tools/kb_indexer.py --force --update-readme` so numbering stays 100% sequential (`1..N`) and synchronized with disk.
