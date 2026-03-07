# fx/services/analytics.py
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
import logging

from database.models import User, Trade, ConnectionLog
from database.repositories import UserRepository, TradeRepository

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Provides trading analytics and reporting
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.user_repo = UserRepository(db_session)
        self.trade_repo = TradeRepository(db_session)
    
    def get_user_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        user = self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {}
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get trades in period
        trades = self.db.query(Trade).filter(
            Trade.user_id == user.id,
            Trade.created_at >= cutoff,
            Trade.status == 'executed'
        ).all()
        
        # Basic stats
        total_trades = len(trades)
        if total_trades == 0:
            return {
                'total_trades': 0,
                'period_days': days,
                'message': 'No trades in this period'
            }
        
        # Calculate win/loss
        winning_trades = [t for t in trades if t.profit_loss and t.profit_loss > 0]
        losing_trades = [t for t in trades if t.profit_loss and t.profit_loss < 0]
        
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        
        # Profit/Loss
        total_profit = sum(float(t.profit_loss or 0) for t in winning_trades)
        total_loss = abs(sum(float(t.profit_loss or 0) for t in losing_trades))
        net_profit = total_profit - total_loss
        
        # Volume
        total_volume = sum(float(t.position_size) for t in trades)
        
        # Most traded symbols
        symbol_stats = {}
        for t in trades:
            if t.symbol not in symbol_stats:
                symbol_stats[t.symbol] = {'count': 0, 'volume': 0, 'profit': 0}
            symbol_stats[t.symbol]['count'] += 1
            symbol_stats[t.symbol]['volume'] += float(t.position_size)
            symbol_stats[t.symbol]['profit'] += float(t.profit_loss or 0)
        
        # Best/worst symbols
        best_symbol = max(symbol_stats.items(), key=lambda x: x[1]['profit']) if symbol_stats else None
        worst_symbol = min(symbol_stats.items(), key=lambda x: x[1]['profit']) if symbol_stats else None
        
        # Daily breakdown
        daily_stats = {}
        for t in trades:
            day = t.created_at.date()
            if day not in daily_stats:
                daily_stats[day] = {'trades': 0, 'profit': 0, 'volume': 0}
            daily_stats[day]['trades'] += 1
            daily_stats[day]['profit'] += float(t.profit_loss or 0)
            daily_stats[day]['volume'] += float(t.position_size)
        
        return {
            'period': {
                'days': days,
                'start': cutoff.isoformat(),
                'end': datetime.utcnow().isoformat()
            },
            'summary': {
                'total_trades': total_trades,
                'winning_trades': win_count,
                'losing_trades': loss_count,
                'win_rate': (win_count / total_trades * 100) if total_trades > 0 else 0,
                'total_volume': total_volume,
                'total_profit': total_profit,
                'total_loss': total_loss,
                'net_profit': net_profit
            },
            'averages': {
                'profit_per_trade': net_profit / total_trades if total_trades > 0 else 0,
                'volume_per_trade': total_volume / total_trades if total_trades > 0 else 0,
                'best_trade': max((float(t.profit_loss or 0) for t in trades), default=0),
                'worst_trade': min((float(t.profit_loss or 0) for t in trades), default=0)
            },
            'symbols': {
                'most_traded': best_symbol[0] if best_symbol else None,
                'best_symbol': best_symbol[0] if best_symbol else None,
                'worst_symbol': worst_symbol[0] if worst_symbol else None,
                'breakdown': symbol_stats
            },
            'daily': {
                str(k): v for k, v in daily_stats.items()
            }
        }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics"""
        # User stats
        total_users = self.db.query(User).count()
        active_users = self.db.query(User).filter(User.is_active == True).count()
        verified_users = self.db.query(User).filter(User.is_verified == True).count()
        
        # Subscription stats
        subscription_counts = {}
        for tier in ['free', 'basic', 'pro', 'enterprise']:
            count = self.db.query(User).filter(User.subscription_tier == tier).count()
            subscription_counts[tier] = count
        
        # Trade stats (last 24h)
        day_ago = datetime.utcnow() - timedelta(days=1)
        trades_24h = self.db.query(Trade).filter(Trade.created_at >= day_ago).count()
        
        # Connection stats
        connections_24h = self.db.query(ConnectionLog).filter(
            ConnectionLog.created_at >= day_ago
        ).count()
        
        successful_connections = self.db.query(ConnectionLog).filter(
            ConnectionLog.created_at >= day_ago,
            ConnectionLog.status == 'success'
        ).count()
        
        connection_rate = (successful_connections / connections_24h * 100) if connections_24h > 0 else 0
        
        # Top users by trades
        top_users = self.db.query(
            User.telegram_username,
            func.count(Trade.id).label('trade_count')
        ).join(Trade).group_by(User.id).order_by(
            func.count(Trade.id).desc()
        ).limit(10).all()
        
        return {
            'users': {
                'total': total_users,
                'active': active_users,
                'verified': verified_users,
                'unverified': total_users - verified_users
            },
            'subscriptions': subscription_counts,
            'trades': {
                'last_24h': trades_24h,
                'total': self.db.query(Trade).count()
            },
            'connections': {
                'last_24h': connections_24h,
                'success_rate': round(connection_rate, 2),
                'avg_latency': self._get_avg_latency()
            },
            'top_users': [
                {'username': u[0] or 'Anonymous', 'trades': u[1]}
                for u in top_users
            ]
        }
    
    def _get_avg_latency(self, hours: int = 24) -> float:
        """Get average connection latency"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        result = self.db.query(
            func.avg(ConnectionLog.latency_ms)
        ).filter(
            ConnectionLog.created_at >= cutoff,
            ConnectionLog.latency_ms.isnot(None)
        ).scalar()
        
        return round(result or 0, 2)
    
    def generate_daily_report(self, user_id: int) -> Dict[str, Any]:
        """Generate daily trading report for a user"""
        user = self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {}
        
        today = datetime.utcnow().date()
        today_start = datetime(today.year, today.month, today.day)
        today_end = today_start + timedelta(days=1)
        
        # Get today's trades
        trades = self.db.query(Trade).filter(
            Trade.user_id == user.id,
            Trade.created_at >= today_start,
            Trade.created_at < today_end,
            Trade.status == 'executed'
        ).all()
        
        total_trades = len(trades)
        
        if total_trades == 0:
            return {
                'date': today.isoformat(),
                'trades': 0,
                'message': 'No trades today'
            }
        
        # Calculate stats
        total_volume = sum(float(t.position_size) for t in trades)
        total_pnl = sum(float(t.profit_loss or 0) for t in trades if t.profit_loss)
        
        winning = [t for t in trades if t.profit_loss and t.profit_loss > 0]
        losing = [t for t in trades if t.profit_loss and t.profit_loss < 0]
        
        return {
            'date': today.isoformat(),
            'trades': total_trades,
            'volume': round(total_volume, 2),
            'pnl': round(total_pnl, 2),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': round(len(winning) / total_trades * 100, 2) if total_trades > 0 else 0,
            'best_trade': max((float(t.profit_loss) for t in winning), default=0),
            'worst_trade': min((float(t.profit_loss) for t in losing), default=0),
            'trades_by_symbol': self._group_by_symbol(trades)
        }
    
    def _group_by_symbol(self, trades: List[Trade]) -> Dict[str, Any]:
        """Group trades by symbol"""
        result = {}
        for t in trades:
            if t.symbol not in result:
                result[t.symbol] = {
                    'count': 0,
                    'volume': 0,
                    'pnl': 0
                }
            result[t.symbol]['count'] += 1
            result[t.symbol]['volume'] += float(t.position_size)
            result[t.symbol]['pnl'] += float(t.profit_loss or 0)
        
        return result
    
    def get_performance_chart_data(self, user_id: int, days: int = 30) -> Dict[str, List]:
        """Get data for performance charts"""
        user = self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {'dates': [], 'equity': [], 'trades': []}
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get all trades in period
        trades = self.db.query(Trade).filter(
            Trade.user_id == user.id,
            Trade.created_at >= cutoff,
            Trade.status == 'executed'
        ).order_by(Trade.created_at).all()
        
        if not trades:
            return {'dates': [], 'equity': [], 'trades': []}
        
        # Build equity curve
        dates = []
        equity = []
        trade_counts = []
        
        current_equity = 10000  # Starting equity (could be actual balance)
        daily_trades = 0
        current_date = None
        
        for trade in trades:
            trade_date = trade.created_at.date()
            
            if current_date != trade_date:
                if current_date:
                    dates.append(current_date.isoformat())
                    equity.append(current_equity)
                    trade_counts.append(daily_trades)
                
                current_date = trade_date
                daily_trades = 0
            
            daily_trades += 1
            if trade.profit_loss:
                current_equity += float(trade.profit_loss)
        
        # Add last day
        if current_date:
            dates.append(current_date.isoformat())
            equity.append(current_equity)
            trade_counts.append(daily_trades)
        
        return {
            'dates': dates,
            'equity': equity,
            'trades_per_day': trade_counts
        }