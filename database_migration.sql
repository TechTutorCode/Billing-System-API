-- Database Migration for Package-to-MikroTik Syncing
-- Run these SQL statements on your PostgreSQL database

-- ============================================
-- 1. ALTER service_packages TABLE
-- ============================================
-- Add mikrotik_profile_name column
ALTER TABLE service_packages 
ADD COLUMN IF NOT EXISTS mikrotik_profile_name VARCHAR;

-- Create index on mikrotik_profile_name
CREATE INDEX IF NOT EXISTS ix_service_packages_mikrotik_profile_name 
ON service_packages(mikrotik_profile_name);

-- Add mikrotik_synced column (default false)
ALTER TABLE service_packages 
ADD COLUMN IF NOT EXISTS mikrotik_synced BOOLEAN NOT NULL DEFAULT FALSE;

-- Create index on mikrotik_synced
CREATE INDEX IF NOT EXISTS ix_service_packages_mikrotik_synced 
ON service_packages(mikrotik_synced);

-- Add mikrotik_synced_at column
ALTER TABLE service_packages 
ADD COLUMN IF NOT EXISTS mikrotik_synced_at TIMESTAMP WITH TIME ZONE;

-- ============================================
-- 2. ALTER Router TABLE
-- ============================================
-- Add mikrotik_api_username column (default 'admin')
ALTER TABLE "Router" 
ADD COLUMN IF NOT EXISTS mikrotik_api_username VARCHAR NOT NULL DEFAULT 'admin';

-- Add mikrotik_api_password_encrypted column
ALTER TABLE "Router" 
ADD COLUMN IF NOT EXISTS mikrotik_api_password_encrypted VARCHAR;

-- ============================================
-- 3. UPDATE EXISTING RECORDS (Optional)
-- ============================================
-- Set default values for existing packages
UPDATE service_packages 
SET mikrotik_synced = FALSE 
WHERE mikrotik_synced IS NULL;

-- Set default API username for existing routers (if not already set)
UPDATE "Router" 
SET mikrotik_api_username = 'admin' 
WHERE mikrotik_api_username IS NULL;

