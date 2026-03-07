# fx/bot/main.py
import logging
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler,
    ConversationHandler, PicklePersistence
)
from telegram import BotCommand
from sqlalchemy.orm import Session

from config.settings import settings
from database.database import db_manager
from bot.handlers import CommandHandlers
from bot.registration import RegistrationHandler, REGISTRATION_STATES
from bot.trading import TradingHandler, TRADING_STATES
from bot.settings import SettingsHandler, SETTINGS_STATES
from bot.admin import AdminHandler, ADMIN_STATES
from bot.middleware import AuthMiddleware, RateLimitMiddleware, ErrorHandler
from services.mt5_manager import MT5ConnectionManager
from services.notification import NotificationService
from services.cache import CacheService
from services.queue import QueueService, AsyncTaskManager
from services.monitoring import MonitoringService

logger = logging.getLogger(__name__)


class Bot:
    """
    Main bot class - initializes and runs the Telegram bot
    """
    
    def __init__(self):
        # Initialize database
        db_manager.initialize(settings.DATABASE_URL)
        self.db = db_manager.get_session()
        
        # Initialize services
        self.cache = CacheService()
        self.queue = QueueService()
        self.task_manager = AsyncTaskManager()
        self.mt5_manager = MT5ConnectionManager(self.db)
        self.notification = NotificationService(self.db, None)  # Bot will be set later
        self.monitoring = MonitoringService(self.db)
        
        # Initialize bot
        self.updater = Updater(
            settings.BOT_TOKEN,
            persistence=PicklePersistence(filename='bot_persistence'),
            use_context=True
        )
        self.dispatcher = self.updater.dispatcher
        self.bot = self.updater.bot
        
        # Set notification service bot reference
        self.notification.bot = self.bot
        
        # Initialize handlers
        self.command_handlers = CommandHandlers(self.db, self.bot)
        self.registration = RegistrationHandler(self.db, self.bot)
        self.trading = TradingHandler(self.db, self.bot)
        self.settings = SettingsHandler(self.db, self.bot)
        self.admin = AdminHandler(self.db, self.bot)
        
        # Initialize middleware
        self.auth_middleware = AuthMiddleware(self.db)
        self.rate_limiter = RateLimitMiddleware(self.cache)
        self.error_handler = ErrorHandler(self.notification, self.monitoring)
        
        # Setup
        self._setup_middleware()
        self._setup_handlers()
        self._setup_commands()
    
    def _setup_middleware(self):
        """Setup middleware and error handlers"""
        # Add error handler
        self.dispatcher.add_error_handler(self.error_handler.handle)
        
        # Add authentication check to all handlers
        # This will be done per handler in their respective classes
    
    def _setup_handlers(self):
        """Setup all bot handlers"""
        
        # Basic command handlers (no auth required for start/help)
        self.dispatcher.add_handler(CommandHandler("start", self.command_handlers.start))
        self.dispatcher.add_handler(CommandHandler("help", self.command_handlers.help))
        self.dispatcher.add_handler(CommandHandler("about", self.command_handlers.about))
        
        # Registration conversation (no auth required)
        reg_conv = ConversationHandler(
            entry_points=[CommandHandler("register", self.registration.start)],
            states=REGISTRATION_STATES,
            fallbacks=[CommandHandler("cancel", self.registration.cancel)],
            name="registration",
            persistent=True
        )
        self.dispatcher.add_handler(reg_conv)
        
        # Trading conversation (requires auth)
        trade_conv = ConversationHandler(
            entry_points=[CommandHandler("trade", self.auth_middleware.wrap(self.trading.start_trade))],
            states=TRADING_STATES,
            fallbacks=[CommandHandler("cancel", self.trading.cancel)],
            name="trading",
            persistent=True
        )
        self.dispatcher.add_handler(trade_conv)
        
        # Calculate conversation (requires auth)
        calc_conv = ConversationHandler(
            entry_points=[CommandHandler("calculate", self.auth_middleware.wrap(self.trading.start_calculate))],
            states=TRADING_STATES,
            fallbacks=[CommandHandler("cancel", self.trading.cancel)],
            name="calculate",
            persistent=True
        )
        self.dispatcher.add_handler(calc_conv)
        
        # Settings conversation (requires auth)
        settings_conv = ConversationHandler(
            entry_points=[CommandHandler("settings", self.auth_middleware.wrap(self.settings.start))],
            states=SETTINGS_STATES,
            fallbacks=[CommandHandler("cancel", self.settings.cancel)],
            name="settings",
            persistent=True
        )
        self.dispatcher.add_handler(settings_conv)
        
        # Admin commands (requires admin auth)
        self.dispatcher.add_handler(CommandHandler("admin", self.auth_middleware.wrap_admin(self.admin.dashboard)))
        self.dispatcher.add_handler(CommandHandler("stats", self.auth_middleware.wrap_admin(self.admin.stats)))
        self.dispatcher.add_handler(CommandHandler("broadcast", self.auth_middleware.wrap_admin(self.admin.broadcast)))
        
        # Additional command handlers (require auth)
        self.dispatcher.add_handler(CommandHandler(
            "balance", 
            self.auth_middleware.wrap(self.command_handlers.balance)
        ))
        self.dispatcher.add_handler(CommandHandler(
            "positions", 
            self.auth_middleware.wrap(self.command_handlers.positions)
        ))
        self.dispatcher.add_handler(CommandHandler(
            "history", 
            self.auth_middleware.wrap(self.command_handlers.history)
        ))
        self.dispatcher.add_handler(CommandHandler(
            "profile", 
            self.auth_middleware.wrap(self.command_handlers.profile)
        ))
        self.dispatcher.add_handler(CommandHandler(
            "upgrade", 
            self.auth_middleware.wrap(self.command_handlers.upgrade)
        ))
        
        # Callback query handlers
        self.dispatcher.add_handler(CallbackQueryHandler(
            self._handle_callback, pattern="^[a-z_]+:"
        ))
        
        # Fallback for unknown commands
        self.dispatcher.add_handler(CommandHandler(
            "unknown", 
            self.auth_middleware.wrap(self.command_handlers.unknown)
        ))
    
    async def _handle_callback(self, update, context):
        """Route callback queries to appropriate handlers"""
        query = update.callback_query
        data = query.data
        
        # Parse callback data (format: "handler:action:data")
        parts = data.split(':')
        handler_name = parts[0]
        
        if handler_name == 'trade':
            await self.trading.handle_callback(update, context)
        elif handler_name == 'settings':
            await self.settings.handle_callback(update, context)
        elif handler_name == 'admin':
            await self.admin.handle_callback(update, context)
        else:
            await query.answer("Unknown action")
    
    def _setup_commands(self):
        """Setup bot commands for menu"""
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help"),
            BotCommand("register", "Register your MT5 account"),
            BotCommand("trade", "Place a trade"),
            BotCommand("calculate", "Calculate risk without trading"),
            BotCommand("balance", "Check account balance"),
            BotCommand("positions", "View open positions"),
            BotCommand("history", "View trade history"),
            BotCommand("settings", "Configure settings"),
            BotCommand("profile", "View your profile"),
            BotCommand("upgrade", "Upgrade subscription")
        ]
        
        self.bot.set_my_commands(commands)
    
    async def start(self):
        """Start the bot and all services"""
        logger.info("Starting FX Signal Copier Bot...")
        
        # Start services
        await self.mt5_manager.start()
        
        # Start bot
        if settings.USE_WEBHOOK:
            self.updater.start_webhook(
                listen="0.0.0.0",
                port=settings.PORT,
                url_path=settings.BOT_TOKEN,
                webhook_url=f"{settings.APP_URL}/{settings.BOT_TOKEN}"
            )
        else:
            self.updater.start_polling()
        
        logger.info("Bot is running!")
        
        # Start background tasks
        self._start_background_tasks()
        
        self.updater.idle()
    
    def _start_background_tasks(self):
        """Start background tasks"""
        from apscheduler.schedulers.background import BackgroundScheduler
        import atexit
        
        scheduler = BackgroundScheduler()
        
        # Check connections every 5 minutes
        scheduler.add_job(
            self._check_connections,
            'interval',
            minutes=5,
            id='check_connections'
        )
        
        # Collect metrics every 15 minutes
        scheduler.add_job(
            self._collect_metrics,
            'interval',
            minutes=15,
            id='collect_metrics'
        )
        
        # Process expired subscriptions daily at midnight
        scheduler.add_job(
            self._process_expired,
            'cron',
            hour=0,
            minute=0,
            id='process_expired'
        )
        
        # Clean up old data weekly
        scheduler.add_job(
            self._cleanup_old_data,
            'cron',
            day_of_week='sun',
            hour=1,
            minute=0,
            id='cleanup_old_data'
        )
        
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())
    
    async def _check_connections(self):
        """Background task to check user connections"""
        from database.repositories import UserRepository
        
        repo = UserRepository(self.db)
        users = repo.get_users_needing_connection_check(minutes=30)
        
        for user in users:
            try:
                await self.mt5_manager.get_connection(user.telegram_id)
                logger.info(f"Connection check passed for user {user.telegram_id}")
            except Exception as e:
                logger.warning(f"Connection check failed for user {user.telegram_id}: {e}")
                await self.notification.send_telegram(
                    user.telegram_id,
                    "⚠️ *Connection Alert*\n\nUnable to connect to your MT5 account. Please check your credentials in /settings",
                    parse_mode='Markdown'
                )
    
    def _collect_metrics(self):
        """Background task to collect system metrics"""
        self.monitoring.collect_metrics()
    
    def _process_expired(self):
        """Background task to process expired subscriptions"""
        from services.subscription import SubscriptionService
        
        sub_service = SubscriptionService(self.db)
        count = sub_service.process_expired()
        
        if count > 0:
            logger.info(f"Processed {count} expired subscriptions")
    
    def _cleanup_old_data(self):
        """Background task to clean up old data"""
        from database.cleanup import cleanup_old_records
        
        cleanup_old_records(self.db, days=90)
        logger.info("Cleaned up old records")
    
    def stop(self):
        """Stop the bot and cleanup"""
        logger.info("Stopping bot...")
        
        # Stop services
        asyncio.create_task(self.mt5_manager.stop())
        
        # Stop bot
        self.updater.stop()
        
        # Close database
        self.db.close()
        
        logger.info("Bot stopped")