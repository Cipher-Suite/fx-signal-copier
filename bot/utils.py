# fx/bot/main.py
import re
import html
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import humanize
from telegram import Update, ParseMode
from telegram.ext import CallbackContext


def escape_markdown(text: str) -> str:
    """
    Escape Markdown special characters
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def format_number(num: float, decimals: int = 2) -> str:
    """
    Format number with thousand separators
    """
    return f"{num:,.{decimals}f}"


def format_datetime(dt: datetime) -> str:
    """
    Format datetime in a human-readable way
    """
    now = datetime.utcnow()
    diff = now - dt
    
    if diff < timedelta(minutes=1):
        return "just now"
    elif diff < timedelta(hours=1):
        return f"{diff.seconds // 60} minutes ago"
    elif diff < timedelta(days=1):
        return f"{diff.seconds // 3600} hours ago"
    else:
        return dt.strftime("%Y-%m-%d %H:%M")


def parse_command_args(text: str) -> List[str]:
    """
    Parse command arguments, handling quoted strings
    """
    # Simple parsing - split by spaces but respect quotes
    args = []
    current = []
    in_quotes = False
    quote_char = None
    
    for char in text:
        if char in ['"', "'"] and not in_quotes:
            in_quotes = True
            quote_char = char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = None
        elif char == ' ' and not in_quotes:
            if current:
                args.append(''.join(current))
                current = []
        else:
            current.append(char)
    
    if current:
        args.append(''.join(current))
    
    return args


def extract_mentions(text: str) -> List[str]:
    """
    Extract @mentions from text
    """
    return re.findall(r'@(\w+)', text)


def validate_trade_format(text: str) -> tuple[bool, Optional[str]]:
    """
    Validate trade signal format
    Returns (is_valid, error_message)
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    if len(lines) < 4:
        return False, "Signal must have at least 4 lines"
    
    # Check first line
    first_line = lines[0].upper()
    valid_orders = ['BUY', 'SELL', 'BUY LIMIT', 'SELL LIMIT', 'BUY STOP', 'SELL STOP']
    if not any(first_line.startswith(order) for order in valid_orders):
        return False, "First line must start with BUY/SELL [LIMIT/STOP]"
    
    # Check symbol exists
    parts = first_line.split()
    symbol = parts[-1]
    if not re.match(r'^[A-Z]{6}$', symbol):
        return False, f"Invalid symbol format: {symbol}"
    
    # Check entry line
    entry_line = lines[1].upper()
    if 'NOW' not in entry_line:
        try:
            float(entry_line.split()[-1])
        except:
            return False, "Invalid entry price"
    
    # Check SL line
    try:
        float(lines[2].split()[-1])
    except:
        return False, "Invalid stop loss"
    
    # Check TP lines
    for i, line in enumerate(lines[3:5], 1):
        try:
            float(line.split()[-1])
        except:
            if i == 1:
                return False, "At least one take profit required"
            # Second TP is optional
            break
    
    return True, None


def create_progress_bar(percentage: float, length: int = 10) -> str:
    """
    Create a text progress bar
    """
    filled = int(percentage / 100 * length)
    empty = length - filled
    return "█" * filled + "░" * empty


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to max length
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def safe_send_message(update: Update, text: str, **kwargs) -> None:
    """
    Safely send a message with error handling
    """
    try:
        if update.callback_query:
            update.callback_query.message.reply_text(text, **kwargs)
        else:
            update.message.reply_text(text, **kwargs)
    except Exception as e:
        logging.error(f"Failed to send message: {e}")


def get_user_language(update: Update, context: CallbackContext) -> str:
    """
    Get user's preferred language
    """
    # Check context first
    if context.user_data and 'language' in context.user_data:
        return context.user_data['language']
    
    # Check user object
    if update.effective_user and update.effective_user.language_code:
        return update.effective_user.language_code.split('-')[0]
    
    # Default to English
    return 'en'


def localize_text(text_key: str, language: str, **kwargs) -> str:
    """
    Get localized text (simplified - would use proper i18n in production)
    """
    # Simple dictionary for now
    translations = {
        'welcome': {
            'en': "Welcome!",
            'es': "¡Bienvenido!",
            'fr': "Bienvenue!",
            'de': "Willkommen!",
            'pt': "Bem-vindo!",
            'ru': "Добро пожаловать!",
            'zh': "欢迎！",
            'ja': "ようこそ！",
            'ar': "مرحبا!",
            'hi': "स्वागत है!"
        },
        'trade_executed': {
            'en': "Trade executed successfully!",
            'es': "¡Operación ejecutada con éxito!",
            'fr': "Transaction exécutée avec succès!",
            'de': "Trade erfolgreich ausgeführt!",
        },
        # Add more translations as needed
    }
    
    # Get translation or fallback to English
    text = translations.get(text_key, {}).get(language, translations.get(text_key, {}).get('en', text_key))
    
    # Format with kwargs
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    
    return text


class UserStateManager:
    """
    Manage user state in context
    """
    
    @staticmethod
    def set_state(context: CallbackContext, state: str, data: Dict[str, Any] = None) -> None:
        """Set user state"""
        context.user_data['state'] = state
        if data:
            context.user_data['state_data'] = data
    
    @staticmethod
    def get_state(context: CallbackContext) -> Optional[str]:
        """Get current user state"""
        return context.user_data.get('state')
    
    @staticmethod
    def get_state_data(context: CallbackContext) -> Dict[str, Any]:
        """Get state data"""
        return context.user_data.get('state_data', {})
    
    @staticmethod
    def clear_state(context: CallbackContext) -> None:
        """Clear user state"""
        context.user_data.pop('state', None)
        context.user_data.pop('state_data', None)
    
    @staticmethod
    def set_temp_data(context: CallbackContext, key: str, value: Any) -> None:
        """Set temporary data"""
        if 'temp_data' not in context.user_data:
            context.user_data['temp_data'] = {}
        context.user_data['temp_data'][key] = value
    
    @staticmethod
    def get_temp_data(context: CallbackContext, key: str, default: Any = None) -> Any:
        """Get temporary data"""
        return context.user_data.get('temp_data', {}).get(key, default)
    
    @staticmethod
    def clear_temp_data(context: CallbackContext) -> None:
        """Clear temporary data"""
        context.user_data.pop('temp_data', None)


class MessageLimiter:
    """
    Prevent sending too many messages
    """
    
    def __init__(self, max_messages: int = 20, period: int = 60):
        self.max_messages = max_messages
        self.period = period
        self.user_messages = {}
    
    def can_send(self, user_id: int) -> bool:
        """Check if user can send message"""
        now = datetime.utcnow()
        
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        
        # Clean old messages
        self.user_messages[user_id] = [
            t for t in self.user_messages[user_id]
            if now - t < timedelta(seconds=self.period)
        ]
        
        # Check limit
        if len(self.user_messages[user_id]) >= self.max_messages:
            return False
        
        # Add new message
        self.user_messages[user_id].append(now)
        return True


def format_size(bytes: int) -> str:
    """
    Format bytes to human readable size
    """
    return humanize.naturalsize(bytes)


def sanitize_html(text: str) -> str:
    """
    Sanitize text for HTML parsing
    """
    return html.escape(text)


def chunk_text(text: str, max_length: int = 4096) -> List[str]:
    """
    Split long text into chunks for Telegram
    """
    chunks = []
    current_chunk = ""
    
    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 <= max_length:
            if current_chunk:
                current_chunk += '\n' + line
            else:
                current_chunk = line
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def extract_symbols(text: str) -> List[str]:
    """
    Extract potential forex symbols from text
    """
    # Common forex symbols pattern (6 uppercase letters)
    pattern = r'\b[A-Z]{6}\b'
    matches = re.findall(pattern, text)
    
    # Filter to common symbols
    common_symbols = [
        'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD',
        'AUDUSD', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY',
        'XAUUSD', 'XAGUSD', 'BTCUSD', 'ETHUSD'
    ]
    
    return [s for s in matches if s in common_symbols]