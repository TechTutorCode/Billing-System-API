-- Database Migration for Customers Module
-- Run these SQL statements on your PostgreSQL database

-- ============================================
-- 1. CREATE customers TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    isp_id UUID NOT NULL REFERENCES "ISP_DETAILS"(id) ON DELETE CASCADE,
    account_number VARCHAR NOT NULL UNIQUE,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    email VARCHAR,
    phone VARCHAR,
    id_number VARCHAR,
    address VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 2. CREATE INDEXES
-- ============================================
-- Index on isp_id for faster lookups
CREATE INDEX IF NOT EXISTS ix_customers_isp_id ON customers(isp_id);

-- Index on account_number (already unique, but index helps with lookups)
CREATE INDEX IF NOT EXISTS ix_customers_account_number ON customers(account_number);

-- Index on status for filtering
CREATE INDEX IF NOT EXISTS ix_customers_status ON customers(status);

-- Index on email for searching (not unique)
CREATE INDEX IF NOT EXISTS ix_customers_email ON customers(email);

-- Index on phone for searching (not unique)
CREATE INDEX IF NOT EXISTS ix_customers_phone ON customers(phone);

-- ============================================
-- 3. CREATE customer_status ENUM TYPE
-- ============================================
-- Note: PostgreSQL enum types are created automatically by SQLAlchemy
-- If you need to create it manually, use:
-- CREATE TYPE customer_status AS ENUM ('active', 'suspended', 'terminated');
-- ALTER TABLE customers ALTER COLUMN status TYPE customer_status USING status::customer_status;

-- ============================================
-- 4. CREATE TRIGGER FOR updated_at
-- ============================================
-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_customers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_update_customers_updated_at ON customers;
CREATE TRIGGER trigger_update_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_customers_updated_at();

-- ============================================
-- 5. ADD CONSTRAINTS
-- ============================================
-- Ensure status is one of the valid values
ALTER TABLE customers ADD CONSTRAINT check_customer_status 
    CHECK (status IN ('active', 'suspended', 'terminated'));

-- ============================================
-- 6. ADD account_number COLUMN (if table already exists)
-- ============================================
-- If the customers table already exists, add the account_number column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'customers' AND column_name = 'account_number'
    ) THEN
        ALTER TABLE customers ADD COLUMN account_number VARCHAR UNIQUE;
        CREATE INDEX IF NOT EXISTS ix_customers_account_number ON customers(account_number);
        
        -- Generate account numbers for existing customers
        UPDATE customers
        SET account_number = 'cust' || LPAD(ROW_NUMBER() OVER (ORDER BY created_at)::TEXT, 3, '0')
        WHERE account_number IS NULL;
        
        -- Make account_number NOT NULL after populating
        ALTER TABLE customers ALTER COLUMN account_number SET NOT NULL;
    END IF;
END $$;

-- ============================================
-- NOTES
-- ============================================
-- - account_number is unique and auto-generated (format: cust001, cust002, etc.)
-- - Phone and email are NOT unique (multiple customers can share them)
-- - Customers are uniquely identified by UUID and account_number
-- - Status defaults to 'active'
-- - updated_at is automatically updated on row modification
