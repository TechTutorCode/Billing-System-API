-- Database Migration for Subscriptions Module
-- Run these SQL statements on your PostgreSQL database

-- ============================================
-- 1. CREATE subscriptions TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    isp_id UUID NOT NULL REFERENCES "ISP_DETAILS"(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    router_id UUID NOT NULL REFERENCES "Router"(id) ON DELETE CASCADE,
    package_id UUID NOT NULL REFERENCES service_packages(id) ON DELETE CASCADE,
    package_type VARCHAR NOT NULL,
    username VARCHAR NOT NULL,
    password VARCHAR,
    ip_address VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'pending',
    start_at TIMESTAMP WITH TIME ZONE,
    end_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 2. CREATE INDEXES
-- ============================================
-- Index on isp_id for faster lookups
CREATE INDEX IF NOT EXISTS ix_subscriptions_isp_id ON subscriptions(isp_id);

-- Index on customer_id for customer lookups
CREATE INDEX IF NOT EXISTS ix_subscriptions_customer_id ON subscriptions(customer_id);

-- Index on router_id for router lookups
CREATE INDEX IF NOT EXISTS ix_subscriptions_router_id ON subscriptions(router_id);

-- Index on package_id for package lookups
CREATE INDEX IF NOT EXISTS ix_subscriptions_package_id ON subscriptions(package_id);

-- Index on status for filtering
CREATE INDEX IF NOT EXISTS ix_subscriptions_status ON subscriptions(status);

-- Index on package_type for filtering
CREATE INDEX IF NOT EXISTS ix_subscriptions_package_type ON subscriptions(package_type);

-- Index on end_at for expiry queries (critical for background task)
CREATE INDEX IF NOT EXISTS ix_subscriptions_end_at ON subscriptions(end_at);

-- ============================================
-- 3. CREATE UNIQUE CONSTRAINT
-- ============================================
-- Username must be unique per router
ALTER TABLE subscriptions ADD CONSTRAINT uq_router_username 
    UNIQUE (router_id, username);

-- ============================================
-- 4. CREATE subscription_status ENUM TYPE
-- ============================================
-- Note: PostgreSQL enum types are created automatically by SQLAlchemy
-- If you need to create it manually, use:
-- CREATE TYPE subscription_status AS ENUM ('pending', 'active', 'suspended', 'expired', 'terminated');
-- ALTER TABLE subscriptions ALTER COLUMN status TYPE subscription_status USING status::subscription_status;

-- ============================================
-- 5. CREATE subscription_package_type ENUM TYPE
-- ============================================
-- Note: PostgreSQL enum types are created automatically by SQLAlchemy
-- If you need to create it manually, use:
-- CREATE TYPE subscription_package_type AS ENUM ('pppoe', 'static');
-- ALTER TABLE subscriptions ALTER COLUMN package_type TYPE subscription_package_type USING package_type::subscription_package_type;

-- ============================================
-- 6. CREATE TRIGGER FOR updated_at
-- ============================================
-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_subscriptions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_update_subscriptions_updated_at ON subscriptions;
CREATE TRIGGER trigger_update_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_subscriptions_updated_at();

-- ============================================
-- 7. ADD CONSTRAINTS
-- ============================================
-- Ensure status is one of the valid values
ALTER TABLE subscriptions ADD CONSTRAINT check_subscription_status 
    CHECK (status IN ('pending', 'active', 'suspended', 'expired', 'terminated'));

-- Ensure package_type is one of the valid values
ALTER TABLE subscriptions ADD CONSTRAINT check_subscription_package_type 
    CHECK (package_type IN ('pppoe', 'static'));

-- ============================================
-- NOTES
-- ============================================
-- - Username must be unique per router (enforced by unique constraint)
-- - Password is required for PPPoE subscriptions
-- - IP address is required for Static IP subscriptions
-- - Status defaults to 'pending'
-- - Subscriptions are NOT auto-activated on creation
-- - end_at is indexed for efficient expiry queries
-- - updated_at is automatically updated on row modification

