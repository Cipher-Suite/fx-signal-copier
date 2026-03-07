# fx/services/notification.py
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio
import logging
from sqlalchemy.orm import Session

from database.repositories import NotificationRepository, UserRepository
from database.models import Notification, User
from config.settings import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Handles all user notifications
    """
    
    def __init__(self, db_session: Session, bot=None):
        self.db = db_session
        self.bot = bot  # Telegram bot instance
        self.notification_repo = NotificationRepository(db_session)
        self.user_repo = UserRepository(db_session)
        
        # Notification templates
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """Load notification templates"""
        return {
            'trade_executed': (
                "✅ **Trade Executed**\n\n"
                "{order_type} {symbol}\n"
                "📊 Size: {size}\n"
                "💰 Risk: ${risk}\n"
                "🎯 Target: ${reward}\n"
                "📈 R:R: 1:{rr}"
            ),
            'trade_failed': (
                "❌ **Trade Failed**\n\n"
                "Symbol: {symbol}\n"
                "Error: {error}\n\n"
                "Please check your connection and try again."
            ),
            'connection_success': (
                "✅ **MT5 Connected**\n\n"
                "Successfully connected to {server}\n"
                "Account: {account}\n"
                "Balance: ${balance}"
            ),
            'connection_failed': (
                "⚠️ **Connection Issue**\n\n"
                "Failed to connect to MT5\n"
                "Error: {error}\n\n"
                "Please check your credentials in /settings"
            ),
            'daily_report': (
                "📊 **Daily Trading Report**\n\n"
                "Date: {date}\n"
                "Trades: {trades}\n"
                "Volume: {volume}\n"
                "P/L: {pnl}\n"
                "Win Rate: {win_rate}%"
            ),
            'subscription_expiring': (
                "⚠️ **Subscription Expiring Soon**\n\n"
                "Your {plan} plan expires on {expiry}\n"
                "Renew now to avoid interruption: /upgrade"
            ),
            'subscription_expired': (
                "❌ **Subscription Expired**\n\n"
                "Your {plan} plan has expired.\n"
                "You've been downgraded to Free plan.\n"
                "Upgrade again: /upgrade"
            ),
            'welcome': (
                "🎉 **Welcome to FX Signal Copier!**\n\n"
                "Your MT5 account has been connected.\n"
                "Start trading with /trade\n"
                "View settings with /settings"
            ),
            'daily_limit': (
                "⚠️ **Daily Trade Limit Reached**\n\n"
                "You've used all {limit} trades for today.\n"
                "Upgrade for more: /upgrade"
            ),
            'error_alert': (
                "⚠️ **System Alert**\n\n"
                "An error occurred:\n"
                "{error}\n\n"
                "Our team has been notified."
            )
        }
    
    async def send_telegram(self, user_id: int, message: str, 
                           parse_mode: str = 'Markdown') -> bool:
        """
        Send a Telegram message to a user
        """
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False
        
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=parse_mode
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram to {user_id}: {e}")
            return False
    
    async def notify_trade_executed(self, user_id: int, trade_data: Dict[str, Any]):
        """Notify user about successful trade execution"""
        template = self.templates['trade_executed']
        message = template.format(
            order_type=trade_data['order_type'],
            symbol=trade_data['symbol'],
            size=trade_data['size'],
            risk=trade_data['risk'],
            reward=trade_data['reward'],
            rr=trade_data.get('rr_ratio', 0)
        )
        
        # Send via Telegram
        await self.send_telegram(user_id, message)
        
        # Create in-app notification
        self.notification_repo.create_notification(
            user_id=user_id,
            title="Trade Executed",
            message=f"{trade_data['order_type']} {trade_data['symbol']} - Size: {trade_data['size']}",
            type='success',
            data=trade_data
        )
    
    async def notify_trade_failed(self, user_id: int, error: str, trade_data: Dict[str, Any]):
        """Notify user about trade failure"""
        template = self.templates['trade_failed']
        message = template.format(
            symbol=trade_data.get('symbol', 'Unknown'),
            error=error[:100]
        )
        
        await self.send_telegram(user_id, message)
        
        self.notification_repo.create_notification(
            user_id=user_id,
            title="Trade Failed",
            message=f"Failed: {error[:50]}...",
            type='error',
            data={'error': error, 'trade_data': trade_data}
        )
    
    async def notify_connection_status(self, user_id: int, success: bool, 
                                      server: str, account: str, 
                                      balance: Optional[float] = None,
                                      error: Optional[str] = None):
        """Notify user about connection status change"""
        if success:
            template = self.templates['connection_success']
            message = template.format(
                server=server,
                account=account,
                balance=balance or 0
            )
            notif_type = 'success'
            title = "MT5 Connected"
        else:
            template = self.templates['connection_failed']
            message = template.format(error=error or "Unknown error")
            notif_type = 'error'
            title = "Connection Failed"
        
        await self.send_telegram(user_id, message)
        
        self.notification_repo.create_notification(
            user_id=user_id,
            title=title,
            message=message[:100],
            type=notif_type,
            data={'server': server, 'account': account, 'error': error}
        )
    
    async def send_daily_report(self, user_id: int, stats: Dict[str, Any]):
        """Send daily trading report"""
        template = self.templates['daily_report']
        message = template.format(
            date=datetime.utcnow().strftime('%Y-%m-%d'),
            trades=stats.get('trades', 0),
            volume=stats.get('volume', 0),
            pnl=stats.get('pnl', 0),
            win_rate=stats.get('win_rate', 0)
        )
        
        await self.send_telegram(user_id, message)
    
    async def check_subscription_expiry(self):
        """Check for expiring subscriptions and notify users"""
        from services.subscription import SubscriptionService
        
        sub_service = SubscriptionService(self.db)
        expiring_soon = sub_service.get_expiring_soon(days=7)
        
        for user, days_left in expiring_soon:
            template = self.templates['subscription_expiring']
            message = template.format(
                plan=user.subscription_tier,
                expiry=user.subscription_expiry.strftime('%Y-%m-%d')
            )
            
            await self.send_telegram(user.telegram_id, message)
            
            self.notification_repo.create_notification(
                user_id=user.id,
                title="Subscription Expiring",
                message=f"Your {user.subscription_tier} plan expires in {days_left} days",
                type='warning',
                data={'expiry': user.subscription_expiry.isoformat()}
            )
    
    async def notify_daily_limit(self, user_id: int, limit: int):
        """Notify user about reaching daily trade limit"""
        template = self.templates['daily_limit']
        message = template.format(limit=limit)
        
        await self.send_telegram(user_id, message)
    
    async def broadcast(self, message: str, user_ids: Optional[List[int]] = None,
                       user_filter: Optional[Dict[str, Any]] = None):
        """
        Broadcast a message to multiple users
        """
        if user_ids:
            users = self.db.query(User).filter(User.telegram_id.in_(user_ids)).all()
        elif user_filter:
            query = self.db.query(User)
            for key, value in user_filter.items():
                if hasattr(User, key):
                    query = query.filter(getattr(User, key) == value)
            users = query.all()
        else:
            users = self.user_repo.get_active_users()
        
        success_count = 0
        fail_count = 0
        
        for user in users:
            try:
                await self.send_telegram(user.telegram_id, message)
                success_count += 1
                await asyncio.sleep(0.05)  # Rate limiting
            except Exception as e:
                logger.error(f"Broadcast failed for user {user.telegram_id}: {e}")
                fail_count += 1
        
        logger.info(f"Broadcast complete: {success_count} success, {fail_count} failed")
        
        return {
            'total': len(users),
            'success': success_count,
            'failed': fail_count
        }
    
    async def send_error_alert(self, error: str, context: Dict[str, Any]):
        """Send error alert to admins"""
        admin_ids = settings.ADMIN_USER_IDS
        
        template = self.templates['error_alert']
        message = template.format(error=error[:200])
        
        for admin_id in admin_ids:
            await self.send_telegram(admin_id, message)
    
    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications for a user"""
        return len(self.notification_repo.get_unread(user_id))
    
    def mark_all_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user"""
        return self.notification_repo.mark_all_as_read(user_id)