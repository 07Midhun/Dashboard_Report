import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("auto_migrate")

SCHEMA_PATCH_SQL = """
-- Ensure users table has all required columns
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL DEFAULT 'Administrator',
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'admin',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(150) DEFAULT 'Administrator';
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) DEFAULT 'admin';
ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'active';
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

UPDATE users SET email = COALESCE(username, 'admin') || '@schnell.local' WHERE email IS NULL;
UPDATE users SET status = 'active' WHERE status IS NULL;
UPDATE users SET role = 'admin' WHERE email = 'admin@gmail.com';

-- Ensure customers table has all required columns
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(200) NOT NULL UNIQUE,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE customers ADD COLUMN IF NOT EXISTS customer_name VARCHAR(200);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'active';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE customers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Ensure regions table
CREATE TABLE IF NOT EXISTS regions (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id) ON DELETE RESTRICT,
    region_name VARCHAR(200) NOT NULL,
    region_code VARCHAR(32) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE regions ADD COLUMN IF NOT EXISTS customer_id INTEGER;
ALTER TABLE regions ADD COLUMN IF NOT EXISTS region_name VARCHAR(200);
ALTER TABLE regions ADD COLUMN IF NOT EXISTS region_code VARCHAR(32);
ALTER TABLE regions ADD COLUMN IF NOT EXISTS corporation VARCHAR(100) DEFAULT 'BBMP';
ALTER TABLE regions ADD COLUMN IF NOT EXISTS division VARCHAR(100) DEFAULT '';
ALTER TABLE regions ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'active';
ALTER TABLE regions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE regions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

ALTER TABLE regions ALTER COLUMN corporation SET DEFAULT 'BBMP';
ALTER TABLE regions ALTER COLUMN division SET DEFAULT '';
UPDATE regions SET corporation = 'BBMP' WHERE corporation IS NULL;
UPDATE regions SET division = '' WHERE division IS NULL;

-- Drop obsolete single-column unique constraints if present
ALTER TABLE regions DROP CONSTRAINT IF EXISTS regions_region_name_key;
ALTER TABLE regions DROP CONSTRAINT IF EXISTS uq_regions_region_name;
ALTER TABLE regions DROP CONSTRAINT IF EXISTS regions_region_code_key;
ALTER TABLE regions DROP CONSTRAINT IF EXISTS uq_regions_region_code;

-- Ensure default customer exists and link orphaned regions
INSERT INTO customers (customer_name, status, created_at, updated_at)
VALUES ('Bangalore (BBMP)', 'active', NOW(), NOW())
ON CONFLICT (customer_name) DO NOTHING;

UPDATE regions 
SET customer_id = (SELECT id FROM customers WHERE customer_name = 'Bangalore (BBMP)' LIMIT 1)
WHERE customer_id IS NULL;

-- Safe backfill for existing regions with NULL or empty region_code
UPDATE regions 
SET region_code = 'BMH' 
WHERE (region_code IS NULL OR region_code = '') 
  AND UPPER(region_name) LIKE '%BOMMANAHALLI%';

UPDATE regions 
SET region_code = 'EAST' 
WHERE (region_code IS NULL OR region_code = '') 
  AND UPPER(region_name) LIKE '%EAST%';

UPDATE regions 
SET region_code = UPPER(SUBSTRING(REGEXP_REPLACE(region_name, '[^a-zA-Z0-9]', '', 'g') FROM 1 FOR 10)) 
WHERE region_code IS NULL OR region_code = '';

UPDATE regions 
SET region_code = 'REG' || id 
WHERE region_code IS NULL OR region_code = '';

-- Ensure zones table
CREATE TABLE IF NOT EXISTS zones (
    id SERIAL PRIMARY KEY,
    region_id INTEGER REFERENCES regions(id) ON DELETE RESTRICT,
    zone_name VARCHAR(200) NOT NULL,
    zone_code VARCHAR(32),
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE zones ADD COLUMN IF NOT EXISTS region_id INTEGER;
ALTER TABLE zones ADD COLUMN IF NOT EXISTS zone_name VARCHAR(200);
ALTER TABLE zones ADD COLUMN IF NOT EXISTS zone_code VARCHAR(32);
ALTER TABLE zones ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'active';
ALTER TABLE zones ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE zones ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Ensure wards table
CREATE TABLE IF NOT EXISTS wards (
    id SERIAL PRIMARY KEY,
    zone_id INTEGER REFERENCES zones(id) ON DELETE RESTRICT,
    ward_code VARCHAR(64) NOT NULL,
    ward_name VARCHAR(200) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE wards ADD COLUMN IF NOT EXISTS zone_id INTEGER;
ALTER TABLE wards ADD COLUMN IF NOT EXISTS region_id INTEGER;
ALTER TABLE wards ADD COLUMN IF NOT EXISTS ward_code VARCHAR(64);
ALTER TABLE wards ADD COLUMN IF NOT EXISTS ward_name VARCHAR(200);
ALTER TABLE wards ADD COLUMN IF NOT EXISTS ward_number VARCHAR(64);
ALTER TABLE wards ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'active';
ALTER TABLE wards ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE wards ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE wards ALTER COLUMN region_id DROP NOT NULL;
ALTER TABLE wards DROP CONSTRAINT IF EXISTS uq_region_ward_number;
UPDATE wards SET ward_number = ward_code WHERE ward_number IS NULL;
UPDATE wards w SET region_id = z.region_id FROM zones z WHERE w.zone_id = z.id AND w.region_id IS NULL;

-- Ensure audit_logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id VARCHAR(64),
    details JSONB,
    ip_address VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action VARCHAR(100);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entity_type VARCHAR(64);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entity_id VARCHAR(64);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS details JSONB;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS ip_address VARCHAR(64);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Ensure revoked_tokens table
CREATE TABLE IF NOT EXISTS revoked_tokens (
    id SERIAL PRIMARY KEY,
    jti VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Ensure user_customer_permissions table
CREATE TABLE IF NOT EXISTS user_customer_permissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    access_level VARCHAR(32) NOT NULL DEFAULT 'read_only',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
"""


def auto_heal_schema(engine: Engine) -> None:
    """Executes safe idempotent schema patches before metadata.create_all."""
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            for statement in SCHEMA_PATCH_SQL.strip().split(";"):
                stmt = statement.strip()
                if stmt:
                    conn.execute(text(stmt))
        logger.info("Database schema auto-heal completed successfully.")
    except Exception as exc:
        logger.warning("Database schema auto-heal notice: %s", exc)

