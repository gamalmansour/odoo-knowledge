# pgvector PostgreSQL Extension Required for Odoo Enterprise AI Module

| Field         | Value                                  |
|---------------|----------------------------------------|
| Category      | setup                                  |
| Odoo Versions | 17, 18, 19                            |
| Severity      | 🔴 Critical                            |
| Last Verified | 2026-06-06                             |
| Author        | ENG/Gamal Mansour                      |

**Tags:** `pgvector`, `postgresql`, `ai`, `enterprise`, `vector`, `embedding`, `extension`, `pg13`, `pg18`

---

## Problem

When upgrading or installing any module that depends on `ai` (Odoo Enterprise AI module), the following error occurs:

```
psycopg2.errors.UndefinedObject: type "vector" does not exist
LINE 1: ...stamp, "write_date" timestamp, "embedding_vector" vector(153...
```

The `enterprise/ai` module uses `pgvector` PostgreSQL extension for RAG (Retrieval-Augmented Generation) AI features. The field `embedding_vector = Vector(size=1536)` in `ai_embedding.py` requires the `vector` type to exist in PostgreSQL.

The `_pre_init_ai` hook tries to run `CREATE EXTENSION IF NOT EXISTS vector` — if pgvector is not installed, this fails silently (or raises UserError), and the table creation then crashes with the above error.

## Root Cause

`pgvector` is an optional PostgreSQL extension (not bundled with PostgreSQL). It must be:
1. Installed as a system package (compiled for your specific PostgreSQL version)
2. Activated per-database with `CREATE EXTENSION vector`

## Solution ✅

### On macOS (Homebrew) — PostgreSQL 16, 17, 18

```bash
brew install pgvector
```

Homebrew's pgvector supports PG16, PG17, PG18 only. Then activate per database:

```bash
psql -U <superuser> -d <your_odoo_db> -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### On macOS (Homebrew) — PostgreSQL 13, 14, 15

Homebrew pgvector does NOT support PG13-15. **Recommended solution:** Migrate to PostgreSQL 16+ instead.

**Migration steps (PG13 → PG18):**

```bash
# 1. Install pgvector on PG18
brew install pgvector

# 2. Set PG18 to a different port (e.g. 5433) if PG13 is on 5432
echo "port = 5433" >> /opt/homebrew/var/postgresql@18/postgresql.conf
brew services restart postgresql@18

# 3. Create odoo user on PG18
psql -p 5433 -U $(whoami) -d postgres -c "CREATE USER odoo WITH CREATEDB SUPERUSER;"

# 4. Create and restore target database
psql -p 5433 -U $(whoami) -d postgres -c "CREATE DATABASE odoo19_dev OWNER odoo;"
pg_dump -p 5432 -U odoo -Fc odoo19_dev > /tmp/odoo19_dev.dump
pg_restore -p 5433 -U odoo -d odoo19_dev --no-owner --role=odoo /tmp/odoo19_dev.dump

# 5. Activate pgvector on the database (as superuser)
psql -p 5433 -U $(whoami) -d odoo19_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 6. Update odoo config (db_port = 5433)
sed -i '' 's/db_port = 5432/db_port = 5433/' odoo19_dev.conf
```

### On Ubuntu/Debian (Linux)

```bash
# For PostgreSQL 14
sudo apt install postgresql-14-pgvector

# For PostgreSQL 15
sudo apt install postgresql-15-pgvector

# For PostgreSQL 16
sudo apt install postgresql-16-pgvector

# Then activate in each database
psql -U postgres -d <db_name> -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### On Odoo.sh (Production)

pgvector is **already available** on Odoo.sh infrastructure. The `_pre_init_ai` hook handles extension creation automatically. No action needed.

## ⚠️ Pitfalls

- **pgvector must match PostgreSQL version** — cannot use PG18 pgvector with PG13 server.
- **pg_restore warnings** about "already exists" constraints are normal when restoring into a non-empty database created with CREATE DATABASE. Use `-Fc` format and `--no-owner` flags.
- **`odoo` user needs SUPERUSER** on PG18 to run `CREATE EXTENSION` (Odoo's pre_init_hook does this).
- The error only appears when the `ai` module or any module depending on it is being installed/upgraded.
- This does NOT affect Odoo Community — `pgvector` is only in Odoo Enterprise `ai` module.

## Verification

After setup, verify:

```bash
psql -p 5433 -U odoo -d odoo19_dev -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
# Expected: vector | 0.8.2
```

Then attempt the upgrade again from Odoo settings.

## References

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Odoo Enterprise AI Module](enterprise/ai/__init__.py)
- Fixed on: local dev environment — migrated from PG13 → PG18 (port 5433)
