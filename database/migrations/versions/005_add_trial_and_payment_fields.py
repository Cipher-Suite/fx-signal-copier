# fx/database/migrations/versions/005_add_trial_and_payment_fields.py
"""add trial and payment history fields to users

Revision ID: 005
Revises: 004
Create Date: 2026-03-20 08:00:00.000000

Fixes:
  - TrialService references trial_used/trial_start which didn't exist
  - upgrade_user() references payment_history which didn't exist
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Trial tracking
    op.add_column('users', sa.Column('trial_used', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('trial_start', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('trial_end', sa.DateTime(), nullable=True))
    
    # Payment history (JSON array of payment records)
    op.add_column('users', sa.Column('payment_history', sa.JSON(), nullable=False, server_default='[]'))


def downgrade():
    op.drop_column('users', 'payment_history')
    op.drop_column('users', 'trial_end')
    op.drop_column('users', 'trial_start')
    op.drop_column('users', 'trial_used')
