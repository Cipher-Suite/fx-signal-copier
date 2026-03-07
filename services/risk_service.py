# fx/services/risk_service.py
"""
Risk management service
Calculates position sizes and risk metrics
"""
import math
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import logging

from core.models import TradeSignal, CalculatedTrade
from config.constants import PIP_MULTIPLIERS, JPY_SYMBOLS

logger = logging.getLogger(__name__)


class RiskService:
    """
    Handles all risk calculations for trades
    """
    
    def __init__(self):
        self.default_risk_factor = 0.01  # 1%
        self.max_risk_factor = 0.05  # 5%
        self.min_risk_factor = 0.001  # 0.1%
    
    def calculate_position_size(self, balance: float, stop_loss_pips: int,
                                risk_factor: float, symbol: str) -> float:
        """
        Calculate position size based on risk
        
        Formula: (Balance * Risk%) / (Stop Loss in Pips * Pip Value)
        Pip Value for 1 standard lot = $10 per pip
        """
        if stop_loss_pips <= 0:
            raise ValueError("Stop loss must be positive")
        
        # Standard lot pip value is $10
        pip_value = 10.0
        
        # Adjust for different symbols if needed
        if symbol in ['XAUUSD', 'XAGUSD']:
            pip_value = 1.0  # Different pip value for metals
        
        # Calculate raw position size in lots
        raw_size = (balance * risk_factor) / (stop_loss_pips * pip_value)
        
        # Round to 2 decimal places (standard lot increments)
        position_size = math.floor(raw_size * 100) / 100
        
        return position_size
    
    def calculate_pips(self, price1: float, price2: float, symbol: str) -> int:
        """Calculate the difference in pips between two prices"""
        multiplier = self._get_pip_multiplier(symbol)
        return abs(round((price1 - price2) / multiplier))
    
    def _get_pip_multiplier(self, symbol: str) -> float:
        """Get pip multiplier for symbol"""
        if symbol == 'XAUUSD':
            return 0.1
        elif symbol == 'XAGUSD':
            return 0.001
        elif any(jpy in symbol for jpy in JPY_SYMBOLS):
            return 0.01
        else:
            return 0.0001
    
    def calculate_risk_reward(self, entry: float, stop_loss: float, 
                             take_profits: List[float]) -> Dict[str, float]:
        """Calculate risk/reward ratio"""
        risk = abs(entry - stop_loss)
        if risk == 0:
            return {'ratio': 0, 'risk': 0, 'avg_reward': 0}
        
        # For multiple TPs, calculate average reward
        if len(take_profits) > 1:
            total_reward = sum(abs(tp - entry) for tp in take_profits)
            avg_reward = total_reward / len(take_profits)
            ratio = avg_reward / risk
        else:
            reward = abs(take_profits[0] - entry)
            ratio = reward / risk
            avg_reward = reward
        
        return {
            'ratio': ratio,
            'risk': risk,
            'avg_reward': avg_reward,
            'risk_usd': None,  # Will be filled with actual USD values
            'reward_usd': None
        }
    
    def calculate_monetary_risk(self, position_size: float, stop_loss_pips: int,
                               symbol: str) -> float:
        """Calculate monetary risk in account currency"""
        pip_value = 10.0 * position_size  # $10 per pip per standard lot
        return pip_value * stop_loss_pips
    
    def calculate_potential_profit(self, position_size: float, take_profit_pips: List[int],
                                  split_position: bool = True) -> List[float]:
        """Calculate potential profit for each TP"""
        profits = []
        
        if split_position and len(take_profit_pips) > 1:
            size_per_tp = position_size / len(take_profit_pips)
            for pips in take_profit_pips:
                profit = (size_per_tp * 10) * pips
                profits.append(round(profit, 2))
        else:
            for pips in take_profit_pips:
                profit = (position_size * 10) * pips
                profits.append(round(profit, 2))
        
        return profits
    
    def calculate_trade(self, signal: TradeSignal, balance: float,
                       risk_factor: Optional[float] = None,
                       user_settings: Optional[Dict[str, Any]] = None) -> CalculatedTrade:
        """
        Calculate all trade metrics
        """
        # Use provided risk factor or default
        risk = risk_factor or self.default_risk_factor
        
        # Check if there's a symbol-specific override
        if user_settings and 'symbol_risk_overrides' in user_settings:
            overrides = user_settings['symbol_risk_overrides']
            if signal.symbol in overrides:
                risk = overrides[signal.symbol]
                logger.info(f"Using symbol override for {signal.symbol}: {risk}")
        
        # Validate risk
        if risk > self.max_risk_factor:
            logger.warning(f"Risk {risk} exceeds maximum, capping at {self.max_risk_factor}")
            risk = self.max_risk_factor
        elif risk < self.min_risk_factor:
            logger.warning(f"Risk {risk} below minimum, using {self.min_risk_factor}")
            risk = self.min_risk_factor
        
        # Calculate stop loss in pips
        stop_loss_pips = self.calculate_pips(signal.entry, signal.stop_loss, signal.symbol)
        
        # Calculate position size
        position_size = self.calculate_position_size(balance, stop_loss_pips, risk, signal.symbol)
        
        # Apply max position size limit
        if user_settings and 'max_position_size' in user_settings:
            max_size = user_settings['max_position_size']
            if position_size > max_size:
                logger.info(f"Position size {position_size} capped at {max_size}")
                position_size = max_size
        
        # Calculate take profits in pips
        take_profit_pips = []
        for tp in signal.take_profits:
            pips = self.calculate_pips(tp, signal.entry, signal.symbol)
            take_profit_pips.append(pips)
        
        # Calculate monetary values
        potential_loss = self.calculate_monetary_risk(position_size, stop_loss_pips, signal.symbol)
        potential_profits = self.calculate_potential_profit(
            position_size, take_profit_pips, 
            split_position=len(signal.take_profits) > 1
        )
        
        # Calculate risk/reward
        rr_info = self.calculate_risk_reward(signal.entry, signal.stop_loss, signal.take_profits)
        
        return CalculatedTrade(
            signal=signal,
            balance=balance,
            position_size=position_size,
            stop_loss_pips=stop_loss_pips,
            take_profit_pips=take_profit_pips,
            potential_loss=potential_loss,
            potential_profits=potential_profits,
            risk_percentage=risk * 100,
            risk_reward_ratio=rr_info['ratio']
        )
    
    def validate_trade_parameters(self, signal: TradeSignal, balance: float,
                                 user_settings: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate if trade parameters are within acceptable limits
        """
        errors = []
        
        # Check balance
        if balance <= 0:
            errors.append("Insufficient balance")
        
        # Check stop loss distance
        sl_pips = self.calculate_pips(signal.entry, signal.stop_loss, signal.symbol)
        min_sl = user_settings.get('min_stop_loss_pips', 10)
        if sl_pips < min_sl:
            errors.append(f"Stop loss too tight: {sl_pips} < {min_sl} pips")
        
        max_sl = user_settings.get('max_stop_loss_pips', 500)
        if sl_pips > max_sl:
            errors.append(f"Stop loss too wide: {sl_pips} > {max_sl} pips")
        
        # Check take profit distances
        for i, tp in enumerate(signal.take_profits):
            tp_pips = self.calculate_pips(tp, signal.entry, signal.symbol)
            min_tp = user_settings.get('min_take_profit_pips', 10)
            if tp_pips < min_tp:
                errors.append(f"TP{i+1} too tight: {tp_pips} < {min_tp} pips")
        
        # Check risk/reward ratio
        rr = self.calculate_risk_reward(signal.entry, signal.stop_loss, signal.take_profits)
        min_rr = user_settings.get('min_risk_reward', 1.0)
        if rr['ratio'] < min_rr:
            errors.append(f"Risk/reward too low: {rr['ratio']:.2f} < {min_rr}")
        
        # Check position size against max
        if user_settings.get('max_position_size'):
            sl_pips = self.calculate_pips(signal.entry, signal.stop_loss, signal.symbol)
            risk = user_settings.get('default_risk_factor', self.default_risk_factor)
            position_size = self.calculate_position_size(balance, sl_pips, risk, signal.symbol)
            
            if position_size > user_settings['max_position_size']:
                errors.append(f"Position size would exceed maximum: {position_size:.2f}")
        
        return len(errors) == 0, errors
    
    def suggest_risk_adjustment(self, signal: TradeSignal, balance: float,
                               user_settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggest risk adjustment to meet user's constraints
        """
        suggestions = {}
        
        # Calculate current metrics
        sl_pips = self.calculate_pips(signal.entry, signal.stop_loss, signal.symbol)
        current_risk = user_settings.get('default_risk_factor', self.default_risk_factor)
        current_size = self.calculate_position_size(balance, sl_pips, current_risk, signal.symbol)
        
        # Check against max position size
        max_size = user_settings.get('max_position_size', float('inf'))
        if current_size > max_size:
            # Calculate risk factor that would achieve max size
            suggested_risk = (max_size * sl_pips * 10) / balance
            suggestions['risk_factor'] = round(suggested_risk, 4)
            suggestions['position_size'] = max_size
            suggestions['message'] = f"Reduce risk to {suggested_risk:.2%} to meet max position size"
        
        # Check min risk/reward
        min_rr = user_settings.get('min_risk_reward', 1.0)
        rr = self.calculate_risk_reward(signal.entry, signal.stop_loss, signal.take_profits)
        if rr['ratio'] < min_rr:
            suggestions['rr_ratio'] = rr['ratio']
            suggestions['message'] = f"Risk/reward {rr['ratio']:.2f} below minimum {min_rr}"
        
        return suggestions