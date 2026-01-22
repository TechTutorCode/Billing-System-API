-- Database Migration for Hotspot Management Module
-- Run these SQL statements on your PostgreSQL database

-- ============================================
-- 1. CREATE hotspot_packages TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS hotspot_packages (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    download_speed INTEGER NOT NULL,
    upload_speed INTEGER NOT NULL,
    validity_minutes INTEGER NOT NULL,
    shared_users INTEGER NOT NULL DEFAULT 1,
    router_id UUID NOT NULL REFERENCES "Router"(id) ON DELETE CASCADE,
    mikrotik_profile_name VARCHAR,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 2. CREATE hotspot_vouchers TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS hotspot_vouchers (
    id SERIAL PRIMARY KEY,
    mac_address VARCHAR NOT NULL,
    package_id INTEGER NOT NULL REFERENCES hotspot_packages(id) ON DELETE CASCADE,
    profile_name VARCHAR NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE
);

-- ============================================
-- 3. CREATE INDEXES
-- ============================================
-- Indexes for hotspot_packages
CREATE INDEX IF NOT EXISTS ix_hotspot_packages_router_id ON hotspot_packages(router_id);
CREATE INDEX IF NOT EXISTS ix_hotspot_packages_mikrotik_profile_name ON hotspot_packages(mikrotik_profile_name);
CREATE INDEX IF NOT EXISTS ix_hotspot_packages_is_active ON hotspot_packages(is_active);

-- Indexes for hotspot_vouchers
CREATE INDEX IF NOT EXISTS ix_hotspot_vouchers_mac_address ON hotspot_vouchers(mac_address);
CREATE INDEX IF NOT EXISTS ix_hotspot_vouchers_package_id ON hotspot_vouchers(package_id);
CREATE INDEX IF NOT EXISTS ix_hotspot_vouchers_is_active ON hotspot_vouchers(is_active);
CREATE INDEX IF NOT EXISTS ix_hotspot_vouchers_expires_at ON hotspot_vouchers(expires_at);

-- ============================================
-- 4. CREATE UNIQUE CONSTRAINTS
-- ============================================
-- Ensure MAC address is unique per package
CREATE UNIQUE INDEX IF NOT EXISTS uq_mac_package ON hotspot_vouchers(mac_address, package_id);

-- ============================================
-- 5. COMMENTS (Optional - for documentation)
-- ============================================
COMMENT ON TABLE hotspot_packages IS 'Hotspot packages with speed limits and session timeouts';
COMMENT ON TABLE hotspot_vouchers IS 'MAC-based hotspot vouchers for auto-login';
COMMENT ON COLUMN hotspot_packages.download_speed IS 'Download speed in Kbps';
COMMENT ON COLUMN hotspot_packages.upload_speed IS 'Upload speed in Kbps';
COMMENT ON COLUMN hotspot_packages.validity_minutes IS 'Session timeout in minutes';
COMMENT ON COLUMN hotspot_packages.shared_users IS 'Number of concurrent users allowed';
COMMENT ON COLUMN hotspot_vouchers.mac_address IS 'MAC address in format XX:XX:XX:XX:XX:XX';
