# fx/bot/__init__.py
from .main import Bot
from .handlers import CommandHandlers
from .registration import RegistrationHandler
from .trading import TradingHandler
from .settings import SettingsHandler
from .admin import AdminHandler
from .middleware import (
    AuthMiddleware, RateLimitMiddleware, ErrorHandler,
    LoggingMiddleware, PerformanceMiddleware, MaintenanceMiddleware,
    combine_middleware
)
from .callbacks import CallbackHandlers
from .keyboards import (
    get_confirmation_keyboard, get_risk_keyboard, get_plans_keyboard,
    get_trade_confirmation_keyboard, get_settings_keyboard,
    get_admin_keyboard, get_pagination_keyboard
)
from .utils import (
    escape_markdown, format_number, format_datetime,
    parse_command_args, validate_trade_format, UserStateManager,
    chunk_text, sanitize_html, extract_symbols
)

__all__ = [
    # Main
    'Bot',
    
    # Handlers
    'CommandHandlers',
    'RegistrationHandler',
    'TradingHandler',
    'SettingsHandler',
    'AdminHandler',
    'CallbackHandlers',
    
    # Middleware
    'AuthMiddleware',
    'RateLimitMiddleware',
    'ErrorHandler',
    'LoggingMiddleware',
    'PerformanceMiddleware',
    'MaintenanceMiddleware',
    'combine_middleware',
    
    # Keyboards
    'get_confirmation_keyboard',
    'get_risk_keyboard',
    'get_plans_keyboard',
    'get_trade_confirmation_keyboard',
    'get_settings_keyboard',
    'get_admin_keyboard',
    'get_pagination_keyboard',
    
    # Utils
    'escape_markdown',
    'format_number',
    'format_datetime',
    'parse_command_args',
    'validate_trade_format',
    'UserStateManager',
    'chunk_text',
    'sanitize_html',
    'extract_symbols'
]