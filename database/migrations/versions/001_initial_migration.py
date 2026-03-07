# fx/database/migrations/001_initial_migration.py
"""initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(36), nullable=False),
        sa.Column('telegram_id', sa.Integer(), nullable=False),
        sa.Column('telegram_username', sa.String(100), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('language_code', sa.String(10), server_default='en'),
        sa.Column('mt5_account_id', sa.String(50), nullable=False),
        sa.Column('mt5_password', sa.Text(), nullable=False),
        sa.Column('mt5_server', sa.String(100), nullable=False),
        sa.Column('metaapi_token', sa.Text(), nullable=True),
        sa.Column('default_risk_factor', sa.Float(), nullable=False, server_default='0.01'),
        sa.Column('max_position_size', sa.Float(), nullable=False, server_default='10.0'),
        sa.Column('allowed_symbols', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('blocked_symbols', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('trade_mode', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_banned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ban_reason', sa.String(200), nullable=True),
        sa.Column('subscription_tier', sa.String(50), nullable=False, server_default='free'),
        sa.Column('subscription_expiry', sa.DateTime(), nullable=True),
        sa.Column('subscription_features', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('mt_connected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_connected', sa.DateTime(), nullable=True),
        sa.Column('connection_error', sa.String(200), nullable=True),
        sa.Column('connection_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_volume', sa.Float(), nullable=False, server_default='0'),
        sa.Column('winning_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('losing_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_pips', sa.Float(), nullable=False, server_default='0'),
        sa.Column('daily_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_trade_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_active', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid'),
        sa.UniqueConstraint('telegram_id')
    )
    
    op.create_index('idx_user_telegram_id', 'users', ['telegram_id'])
    op.create_index('idx_user_username', 'users', ['telegram_username'])
    op.create_index('idx_user_subscription', 'users', ['subscription_tier', 'subscription_expiry'])
    op.create_index('idx_user_active', 'users', ['is_active', 'is_verified'])
    
    # Create user_settings table
    op.create_table('user_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notify_on_trade', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_on_error', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_on_connection', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_daily_report', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notify_weekly_report', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notification_hour', sa.Integer(), nullable=False, server_default='9'),
        sa.Column('symbol_risk_overrides', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('auto_tp_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('auto_tp_pips', sa.Integer(), nullable=True),
        sa.Column('auto_sl_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('auto_sl_pips', sa.Integer(), nullable=True),
        sa.Column('min_distance_from_price', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_spread', sa.Float(), nullable=True),
        sa.Column('decimal_places', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('show_pips', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('api_key', sa.String(64), nullable=True, unique=True),
        sa.Column('api_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create trades table
    op.create_table('trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_type', sa.String(20), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('entry_price', sa.Numeric(20, 5), nullable=False),
        sa.Column('stop_loss', sa.Numeric(20, 5), nullable=False),
        sa.Column('take_profits', sa.JSON(), nullable=False),
        sa.Column('position_size', sa.Numeric(20, 2), nullable=False),
        sa.Column('risk_percentage', sa.Float(), nullable=False),
        sa.Column('risk_amount', sa.Numeric(20, 2), nullable=False),
        sa.Column('potential_reward', sa.Numeric(20, 2), nullable=False),
        sa.Column('mt_order_ids', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('signal_text', sa.Text(), nullable=False),
        sa.Column('signal_hash', sa.String(64), nullable=True),
        sa.Column('signal_provider', sa.String(100), nullable=True),
        sa.Column('exit_price', sa.Numeric(20, 5), nullable=True),
        sa.Column('profit_loss', sa.Numeric(20, 2), nullable=True),
        sa.Column('profit_loss_pips', sa.Integer(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid')
    )
    
    op.create_index('idx_trade_user_status', 'trades', ['user_id', 'status'])
    op.create_index('idx_trade_created', 'trades', ['created_at'])
    op.create_index('idx_trade_symbol', 'trades', ['symbol', 'created_at'])
    op.create_index('idx_trade_hash', 'trades', ['signal_hash'])
    
    # Create connection_logs table
    op.create_table('connection_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('server', sa.String(100), nullable=True),
        sa.Column('account_type', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_connection_user_date', 'connection_logs', ['user_id', 'created_at'])
    
    # Create notifications table
    op.create_table('notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(20), nullable=False, server_default='info'),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_delivered', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_notification_user_read', 'notifications', ['user_id', 'is_read'])
    
    # Create subscription_plans table
    op.create_table('subscription_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('tier', sa.String(20), nullable=False),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False),
        sa.Column('price_yearly', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('max_trades_per_day', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_position_size', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('max_symbols', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('supports_multiple_tps', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('supports_auto_trading', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('supports_api', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('support_priority', sa.String(20), nullable=False, server_default='normal'),
        sa.Column('max_connections', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('rate_limit_per_second', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('features', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('stripe_price_id_monthly', sa.String(100), nullable=True),
        sa.Column('stripe_price_id_yearly', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('tier')
    )
    
    # Create api_usage table
    op.create_table('api_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('api_key', sa.String(64), nullable=False),
        sa.Column('endpoint', sa.String(100), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_api_user_date', 'api_usage', ['user_id', 'created_at'])
    
    # Insert default subscription plans
    op.execute("""
        INSERT INTO subscription_plans (name, tier, price_monthly, price_yearly, max_trades_per_day, max_position_size, supports_multiple_tps, supports_auto_trading, description, features)
        VALUES 
        ('Free', 'free', 0, 0, 10, 1.0, true, false, 'Basic plan for getting started', '["10 trades per day", "Basic risk management", "Single TP only"]'),
        ('Basic', 'basic', 9.99, 99.99, 50, 5.0, true, false, 'For active traders', '["50 trades per day", "Multiple TP levels", "Priority support"]'),
        ('Pro', 'pro', 29.99, 299.99, 200, 10.0, true, true, 'Professional trading', '["200 trades per day", "Auto-trading", "API access", "Dedicated support"]'),
        ('Enterprise', 'enterprise', 99.99, 999.99, 1000, 50.0, true, true, 'For trading firms', '["Unlimited trades", "Multiple accounts", "Custom features", "SLA guarantee"]')
    """)

def downgrade():
    op.drop_table('api_usage')
    op.drop_table('subscription_plans')
    op.drop_table('notifications')
    op.drop_table('connection_logs')
    op.drop_table('trades')
    op.drop_table('user_settings')
    op.drop_table('users')
