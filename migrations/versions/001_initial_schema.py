"""Initial SentinelAI Schema

Revision ID: 001_initial
Revises: 
Create Date: 2025-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial SentinelAI database schema."""
    
    # Create UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Create enum types
    op.execute("""
        CREATE TYPE customer_type AS ENUM (
            'INDIVIDUAL', 'CORPORATE', 'FINANCIAL_INSTITUTION', 
            'GOVERNMENT', 'NGO', 'OTHER'
        )
    """)
    
    op.execute("""
        CREATE TYPE transaction_type AS ENUM (
            'WIRE_TRANSFER', 'ACH', 'CASH', 'CHECK', 'CRYPTO', 
            'CARD', 'INTERNAL', 'TRADE_FINANCE', 'OTHER'
        )
    """)
    
    op.execute("""
        CREATE TYPE risk_level AS ENUM (
            'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
        )
    """)
    
    op.execute("""
        CREATE TYPE case_status AS ENUM (
            'OPEN', 'UNDER_INVESTIGATION', 'PENDING_REVIEW', 
            'ESCALATED', 'CLOSED_NO_ACTION', 'CLOSED_SAR_FILED', 
            'CLOSED_FALSE_POSITIVE'
        )
    """)
    
    op.execute("""
        CREATE TYPE alert_status AS ENUM (
            'NEW', 'ACKNOWLEDGED', 'INVESTIGATING', 
            'RESOLVED', 'FALSE_POSITIVE', 'ESCALATED'
        )
    """)
    
    # Create customers table
    op.create_table(
        'customers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, 
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('external_id', sa.String(255), nullable=False, unique=True),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('customer_type', sa.Enum('INDIVIDUAL', 'CORPORATE', 'FINANCIAL_INSTITUTION', 
                                           'GOVERNMENT', 'NGO', 'OTHER', 
                                           name='customer_type_enum'), nullable=False),
        sa.Column('country_of_residence', sa.String(3), nullable=True),
        sa.Column('nationality', sa.String(3), nullable=True),
        sa.Column('date_of_birth', sa.Date, nullable=True),
        sa.Column('occupation', sa.String(255), nullable=True),
        sa.Column('account_opened_date', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('risk_rating', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 
                                         name='risk_level_enum'), nullable=True),
        sa.Column('pep_status', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('sanctions_status', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('kyc_verified', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('kyc_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    
    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('external_id', sa.String(255), nullable=False, unique=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.Numeric(20, 4), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('transaction_type', sa.Enum('WIRE_TRANSFER', 'ACH', 'CASH', 'CHECK', 
                                               'CRYPTO', 'CARD', 'INTERNAL', 
                                               'TRADE_FINANCE', 'OTHER',
                                               name='transaction_type_enum'), nullable=False),
        sa.Column('origin_country', sa.String(3), nullable=True),
        sa.Column('destination_country', sa.String(3), nullable=True),
        sa.Column('origin_institution', sa.String(255), nullable=True),
        sa.Column('destination_institution', sa.String(255), nullable=True),
        sa.Column('parties', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('purpose', sa.Text, nullable=True),
        sa.Column('documents', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('crypto_details', postgresql.JSONB, nullable=True),
        sa.Column('transaction_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('risk_score', sa.Float, nullable=True),
        sa.Column('risk_level', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL',
                                         name='risk_level_enum'), nullable=True),
        sa.Column('analysis_status', sa.String(50), nullable=True),
        sa.Column('analysis_result', postgresql.JSONB, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    
    # Create cases table
    op.create_table(
        'cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('case_number', sa.String(50), nullable=False, unique=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'UNDER_INVESTIGATION', 'PENDING_REVIEW',
                                     'ESCALATED', 'CLOSED_NO_ACTION', 'CLOSED_SAR_FILED',
                                     'CLOSED_FALSE_POSITIVE', name='case_status_enum'),
                  nullable=False, server_default='OPEN'),
        sa.Column('priority', sa.Integer, nullable=False, server_default='3'),
        sa.Column('risk_score', sa.Float, nullable=True),
        sa.Column('risk_level', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL',
                                         name='risk_level_enum'), nullable=True),
        sa.Column('assigned_to', sa.String(255), nullable=True),
        sa.Column('assigned_team', sa.String(255), nullable=True),
        sa.Column('sar_filed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('sar_reference', sa.String(100), nullable=True),
        sa.Column('sar_filed_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('related_transactions', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), 
                  nullable=True),
        sa.Column('related_alerts', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), 
                  nullable=True),
        sa.Column('findings', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('recommendations', postgresql.JSONB, nullable=True, server_default='[]'),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_by', sa.String(255), nullable=True),
        sa.Column('closure_reason', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    
    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('alert_number', sa.String(50), nullable=False, unique=True),
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('customers.id', ondelete='CASCADE'), nullable=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('cases.id', ondelete='SET NULL'), nullable=True),
        sa.Column('alert_type', sa.String(100), nullable=False),
        sa.Column('alert_subtype', sa.String(100), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.Enum('NEW', 'ACKNOWLEDGED', 'INVESTIGATING',
                                     'RESOLVED', 'FALSE_POSITIVE', 'ESCALATED',
                                     name='alert_status_enum'),
                  nullable=False, server_default='NEW'),
        sa.Column('severity', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL',
                                       name='risk_level_enum'), nullable=False),
        sa.Column('risk_score', sa.Float, nullable=True),
        sa.Column('triggered_rules', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('agent_analysis', postgresql.JSONB, nullable=True),
        sa.Column('assigned_to', sa.String(255), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(255), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(255), nullable=True),
        sa.Column('resolution_notes', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    
    # Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('actor', sa.String(255), nullable=True),
        sa.Column('actor_type', sa.String(50), nullable=False, server_default='SYSTEM'),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('old_values', postgresql.JSONB, nullable=True),
        sa.Column('new_values', postgresql.JSONB, nullable=True),
        sa.Column('changes', postgresql.JSONB, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    
    # Create risk_profiles table
    op.create_table(
        'risk_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('uuid_generate_v4()')),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('customers.id', ondelete='CASCADE'), 
                  nullable=False, unique=True),
        sa.Column('overall_score', sa.Float, nullable=False, server_default='0'),
        sa.Column('risk_level', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL',
                                         name='risk_level_enum'), nullable=True),
        sa.Column('geo_risk_score', sa.Float, nullable=True),
        sa.Column('behavioral_risk_score', sa.Float, nullable=True),
        sa.Column('transaction_risk_score', sa.Float, nullable=True),
        sa.Column('network_risk_score', sa.Float, nullable=True),
        sa.Column('pep_risk_score', sa.Float, nullable=True),
        sa.Column('sanctions_risk_score', sa.Float, nullable=True),
        sa.Column('crypto_risk_score', sa.Float, nullable=True),
        sa.Column('velocity_metrics', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('risk_factors', postgresql.JSONB, nullable=True, server_default='[]'),
        sa.Column('last_assessment_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_review_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    
    # Create indexes
    op.create_index('ix_customers_external_id', 'customers', ['external_id'])
    op.create_index('ix_customers_name', 'customers', ['name'])
    op.create_index('ix_customers_risk_rating', 'customers', ['risk_rating'])
    op.create_index('ix_customers_country', 'customers', ['country_of_residence'])
    op.create_index('ix_customers_pep', 'customers', ['pep_status'])
    op.create_index('ix_customers_sanctions', 'customers', ['sanctions_status'])
    
    op.create_index('ix_transactions_external_id', 'transactions', ['external_id'])
    op.create_index('ix_transactions_customer_id', 'transactions', ['customer_id'])
    op.create_index('ix_transactions_date', 'transactions', ['transaction_date'])
    op.create_index('ix_transactions_risk_level', 'transactions', ['risk_level'])
    op.create_index('ix_transactions_origin', 'transactions', ['origin_country'])
    op.create_index('ix_transactions_destination', 'transactions', ['destination_country'])
    op.create_index('ix_transactions_type', 'transactions', ['transaction_type'])
    
    op.create_index('ix_cases_number', 'cases', ['case_number'])
    op.create_index('ix_cases_customer_id', 'cases', ['customer_id'])
    op.create_index('ix_cases_status', 'cases', ['status'])
    op.create_index('ix_cases_risk_level', 'cases', ['risk_level'])
    op.create_index('ix_cases_assigned_to', 'cases', ['assigned_to'])
    
    op.create_index('ix_alerts_number', 'alerts', ['alert_number'])
    op.create_index('ix_alerts_transaction_id', 'alerts', ['transaction_id'])
    op.create_index('ix_alerts_customer_id', 'alerts', ['customer_id'])
    op.create_index('ix_alerts_case_id', 'alerts', ['case_id'])
    op.create_index('ix_alerts_status', 'alerts', ['status'])
    op.create_index('ix_alerts_severity', 'alerts', ['severity'])
    op.create_index('ix_alerts_type', 'alerts', ['alert_type'])
    
    op.create_index('ix_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])
    op.create_index('ix_audit_log_actor', 'audit_log', ['actor'])
    op.create_index('ix_audit_log_created', 'audit_log', ['created_at'])
    
    op.create_index('ix_risk_profiles_customer_id', 'risk_profiles', ['customer_id'])
    op.create_index('ix_risk_profiles_risk_level', 'risk_profiles', ['risk_level'])
    
    # Create update trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Apply update triggers
    for table in ['customers', 'transactions', 'cases', 'alerts', 'risk_profiles']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    """Drop all SentinelAI database objects."""
    
    # Drop triggers
    for table in ['customers', 'transactions', 'cases', 'alerts', 'risk_profiles']:
        op.execute(f'DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table}')
    
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column()')
    
    # Drop tables
    op.drop_table('risk_profiles')
    op.drop_table('audit_log')
    op.drop_table('alerts')
    op.drop_table('cases')
    op.drop_table('transactions')
    op.drop_table('customers')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS alert_status')
    op.execute('DROP TYPE IF EXISTS case_status')
    op.execute('DROP TYPE IF EXISTS risk_level')
    op.execute('DROP TYPE IF EXISTS transaction_type')
    op.execute('DROP TYPE IF EXISTS customer_type')
