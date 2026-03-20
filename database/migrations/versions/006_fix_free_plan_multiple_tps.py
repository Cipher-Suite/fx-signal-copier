# fx/database/migrations/versions/006_fix_free_plan_multiple_tps.py
"""fix free plan supports_multiple_tps

Revision ID: 006
Revises: 005
Create Date: 2026-03-20 08:10:00.000000

The initial migration seeded free plan with supports_multiple_tps=true,
but free users should not have multiple TP support (it's a paid feature).
Also adds missing columns: supports_api, max_symbols, max_connections,
rate_limit_per_second to the seeded plans.
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Fix free plan: multiple TPs should be false
    op.execute("""
        UPDATE subscription_plans 
        SET supports_multiple_tps = false 
        WHERE tier = 'free'
    """)
    
    # Also set correct values for fields that were missing in seed
    op.execute("""
        UPDATE subscription_plans SET 
            supports_api = false,
            max_symbols = 10,
            max_connections = 1,
            rate_limit_per_second = 1,
            support_priority = 'low'
        WHERE tier = 'free'
    """)
    
    op.execute("""
        UPDATE subscription_plans SET 
            supports_api = false,
            max_symbols = 30,
            max_connections = 1,
            rate_limit_per_second = 5,
            support_priority = 'normal'
        WHERE tier = 'basic'
    """)
    
    op.execute("""
        UPDATE subscription_plans SET 
            supports_api = true,
            max_symbols = 0,
            max_connections = 3,
            rate_limit_per_second = 20,
            support_priority = 'high'
        WHERE tier = 'pro'
    """)
    
    op.execute("""
        UPDATE subscription_plans SET 
            supports_api = true,
            max_symbols = 0,
            max_connections = 10,
            rate_limit_per_second = 100,
            support_priority = 'high'
        WHERE tier = 'enterprise'
    """)


def downgrade():
    # Revert free plan to original (wrong) value
    op.execute("""
        UPDATE subscription_plans 
        SET supports_multiple_tps = true 
        WHERE tier = 'free'
    """)
