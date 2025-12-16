-- SentinelAI Database Initialization Script
-- =========================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create enum types
DO $$ BEGIN
    CREATE TYPE risk_level AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE case_status AS ENUM (
        'OPEN', 
        'UNDER_REVIEW', 
        'ESCALATED', 
        'SAR_FILED', 
        'CLOSED_NO_ACTION', 
        'CLOSED_FALSE_POSITIVE'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE alert_type AS ENUM (
        'STRUCTURING',
        'HIGH_RISK_JURISDICTION',
        'SANCTIONS_HIT',
        'PEP_MATCH',
        'UNUSUAL_ACTIVITY',
        'VELOCITY_BREACH',
        'CRYPTO_RISK',
        'DOCUMENT_MISMATCH',
        'NETWORK_ANOMALY',
        'ML_DETECTED'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE transaction_type AS ENUM (
        'WIRE_TRANSFER',
        'ACH',
        'CRYPTO',
        'CASH',
        'CHECK',
        'CARD',
        'TRADE_FINANCE'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE sentinelai TO sentinel;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'SentinelAI database initialized successfully';
END $$;
