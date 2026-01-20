-- Migration script to rename mikrotik_api_password_encrypted to mikrotik_api_password
-- This changes the column to store passwords in plain text instead of encrypted

-- Step 1: Check if the old column exists and rename it
DO $$
BEGIN
    -- Check if the old column exists
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'Router' 
        AND column_name = 'mikrotik_api_password_encrypted'
    ) THEN
        -- Rename the column
        ALTER TABLE "Router" 
        RENAME COLUMN mikrotik_api_password_encrypted TO mikrotik_api_password;
        
        RAISE NOTICE 'Column renamed successfully from mikrotik_api_password_encrypted to mikrotik_api_password';
    ELSE
        -- Check if the new column already exists
        IF EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'Router' 
            AND column_name = 'mikrotik_api_password'
        ) THEN
            RAISE NOTICE 'Column mikrotik_api_password already exists. Migration may have already been run.';
        ELSE
            -- Create the new column if neither exists
            ALTER TABLE "Router" 
            ADD COLUMN mikrotik_api_password VARCHAR;
            
            RAISE NOTICE 'New column mikrotik_api_password created (old column did not exist)';
        END IF;
    END IF;
END $$;

-- Step 2: Verify the migration
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'Router' 
AND column_name IN ('mikrotik_api_password', 'mikrotik_api_password_encrypted')
ORDER BY column_name;
