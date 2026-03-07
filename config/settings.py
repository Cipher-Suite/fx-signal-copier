# fx/config/settings.py
import os
from typing import List, Optional, Dict, Any
from pydantic import BaseSettings, validator, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings with validation
    """
    
    # App Info
    APP_NAME: str = "FX Signal Copier"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "Telegram Bot for MetaTrader 5 Trading"
    DEBUG: bool = Field(False, env="DEBUG")
    
    # MetaAPI Configuration
    METAAPI_TOKEN: str = Field(..., env="METAAPI_TOKEN")
    METAAPI_ACCOUNT_ID: Optional[str] = Field(None, env="METAAPI_ACCOUNT_ID")
    METAAPI_TIMEOUT: int = Field(30, env="METAAPI_TIMEOUT")
    MAX_CONNECTIONS: int = Field(100, env="MAX_CONNECTIONS")
    CONNECTION_IDLE_TIMEOUT: int = Field(300, env="CONNECTION_IDLE_TIMEOUT")  # 5 minutes
    
    @validator('METAAPI_TOKEN')
    def validate_metaapi_token(cls, v):
        if not v or len(v) < 10:
            raise ValueError("METAAPI_TOKEN must be at least 10 characters")
        return v
    
    # Telegram Configuration
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    BOT_USERNAME: Optional[str] = Field(None, env="BOT_USERNAME")
    ADMIN_USER_IDS: List[int] = Field([], env="ADMIN_USER_IDS")
    USE_WEBHOOK: bool = Field(False, env="USE_WEBHOOK")
    WEBHOOK_URL: Optional[str] = Field(None, env="WEBHOOK_URL")
    WEBHOOK_PORT: int = Field(8443, env="WEBHOOK_PORT")
    WEBHOOK_HOST: str = Field("0.0.0.0", env="WEBHOOK_HOST")
    
    @validator('BOT_TOKEN')
    def validate_bot_token(cls, v):
        if not v or ':' not in v:
            raise ValueError("Invalid BOT_TOKEN format")
        return v
    
    @validator('ADMIN_USER_IDS', pre=True)
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(id.strip()) for id in v.split(',') if id.strip()]
        return v
    
    # Database Configuration
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = Field(20, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(10, env="DATABASE_MAX_OVERFLOW")
    DATABASE_POOL_TIMEOUT: int = Field(30, env="DATABASE_POOL_TIMEOUT")
    DATABASE_ECHO: bool = Field(False, env="DATABASE_ECHO")
    
    @validator('DATABASE_URL')
    def validate_database_url(cls, v):
        if not v:
            raise ValueError("DATABASE_URL must be set")
        # Handle Heroku's postgres:// vs postgresql://
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        return v
    
    # Redis Configuration
    REDIS_URL: Optional[str] = Field(None, env="REDIS_URL")
    REDIS_MAX_CONNECTIONS: int = Field(10, env="REDIS_MAX_CONNECTIONS")
    REDIS_SOCKET_TIMEOUT: int = Field(5, env="REDIS_SOCKET_TIMEOUT")
    
    # Security
    ENCRYPTION_KEY: Optional[str] = Field(None, env="ENCRYPTION_KEY")
    JWT_SECRET: str = Field(..., env="JWT_SECRET")
    JWT_ALGORITHM: str = Field("HS256", env="JWT_ALGORITHM")
    JWT_EXPIRY_HOURS: int = Field(24, env="JWT_EXPIRY_HOURS")
    CORS_ORIGINS: List[str] = Field(["*"], env="CORS_ORIGINS")
    
    @validator('ENCRYPTION_KEY')
    def validate_encryption_key(cls, v):
        if not v:
            import base64
            import os
            # Generate a key for development
            v = base64.urlsafe_b64encode(os.urandom(32)).decode()
        return v
    
    # Trading Configuration
    DEFAULT_RISK_FACTOR: float = Field(0.01, env="DEFAULT_RISK_FACTOR")
    MAX_RISK_FACTOR: float = Field(0.05, env="MAX_RISK_FACTOR")
    MIN_RISK_FACTOR: float = Field(0.001, env="MIN_RISK_FACTOR")
    DEFAULT_MAX_POSITION_SIZE: float = Field(10.0, env="DEFAULT_MAX_POSITION_SIZE")
    ALLOWED_SYMBOLS: List[str] = Field([
        'AUDCAD', 'AUDCHF', 'AUDJPY', 'AUDNZD', 'AUDUSD',
        'CADCHF', 'CADJPY', 'CHFJPY', 'EURAUD', 'EURCAD',
        'EURCHF', 'EURGBP', 'EURJPY', 'EURNZD', 'EURUSD',
        'GBPAUD', 'GBPCAD', 'GBPCHF', 'GBPJPY', 'GBPNZD',
        'GBPUSD', 'NZDCAD', 'NZDCHF', 'NZDJPY', 'NZDUSD',
        'USDCAD', 'USDCHF', 'USDJPY', 'XAGUSD', 'XAUUSD'
    ], env="ALLOWED_SYMBOLS")
    
    @validator('ALLOWED_SYMBOLS', pre=True)
    def parse_symbols(cls, v):
        if isinstance(v, str):
            return [s.strip().upper() for s in v.split(',') if s.strip()]
        return v
    
    # Rate Limiting
    RATE_LIMIT_TRADES: int = Field(5, env="RATE_LIMIT_TRADES")  # per minute
    RATE_LIMIT_CALCULATIONS: int = Field(10, env="RATE_LIMIT_CALCULATIONS")
    RATE_LIMIT_BALANCE: int = Field(30, env="RATE_LIMIT_BALANCE")
    RATE_LIMIT_POSITIONS: int = Field(20, env="RATE_LIMIT_POSITIONS")
    
    # Subscription Plans (prices in USD)
    FREE_PLAN_MAX_TRADES: int = Field(10, env="FREE_PLAN_MAX_TRADES")
    FREE_PLAN_MAX_SIZE: float = Field(1.0, env="FREE_PLAN_MAX_SIZE")
    
    BASIC_PLAN_PRICE: float = Field(9.99, env="BASIC_PLAN_PRICE")
    BASIC_PLAN_MAX_TRADES: int = Field(50, env="BASIC_PLAN_MAX_TRADES")
    BASIC_PLAN_MAX_SIZE: float = Field(5.0, env="BASIC_PLAN_MAX_SIZE")
    
    PRO_PLAN_PRICE: float = Field(29.99, env="PRO_PLAN_PRICE")
    PRO_PLAN_MAX_TRADES: int = Field(200, env="PRO_PLAN_MAX_TRADES")
    PRO_PLAN_MAX_SIZE: float = Field(10.0, env="PRO_PLAN_MAX_SIZE")
    
    ENTERPRISE_PLAN_PRICE: float = Field(99.99, env="ENTERPRISE_PLAN_PRICE")
    ENTERPRISE_PLAN_MAX_TRADES: int = Field(1000, env="ENTERPRISE_PLAN_MAX_TRADES")
    ENTERPRISE_PLAN_MAX_SIZE: float = Field(50.0, env="ENTERPRISE_PLAN_MAX_SIZE")
    
    # Notification Settings
    NOTIFICATION_QUEUE_SIZE: int = Field(100, env="NOTIFICATION_QUEUE_SIZE")
    NOTIFICATION_BATCH_SIZE: int = Field(10, env="NOTIFICATION_BATCH_SIZE")
    NOTIFICATION_RETRY_ATTEMPTS: int = Field(3, env="NOTIFICATION_RETRY_ATTEMPTS")
    
    # Monitoring
    METRICS_ENABLED: bool = Field(True, env="METRICS_ENABLED")
    METRICS_PORT: int = Field(9090, env="METRICS_PORT")
    SENTRY_DSN: Optional[str] = Field(None, env="SENTRY_DSN")
    
    # Logging
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    LOG_FILE: Optional[str] = Field(None, env="LOG_FILE")
    LOG_MAX_BYTES: int = Field(10485760, env="LOG_MAX_BYTES")  # 10MB
    LOG_BACKUP_COUNT: int = Field(5, env="LOG_BACKUP_COUNT")
    
    # Feature Flags
    ENABLE_AUTO_TRADING: bool = Field(True, env="ENABLE_AUTO_TRADING")
    ENABLE_API_ACCESS: bool = Field(True, env="ENABLE_API_ACCESS")
    ENABLE_WEBHOOKS: bool = Field(False, env="ENABLE_WEBHOOKS")
    ENABLE_MULTIPLE_TPS: bool = Field(True, env="ENABLE_MULTIPLE_TPS")
    
    # Payment Processing (if using Stripe)
    STRIPE_API_KEY: Optional[str] = Field(None, env="STRIPE_API_KEY")
    STRIPE_WEBHOOK_SECRET: Optional[str] = Field(None, env="STRIPE_WEBHOOK_SECRET")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create global settings instance
settings = Settings()

# Validate critical settings
if not settings.ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY must be set in production")