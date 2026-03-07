# fx/services/signal_processor.py
import re
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import logging

from core.models import TradeSignal
from config.constants import OrderType, PIP_MULTIPLIERS, JPY_SYMBOLS
from config.settings import settings

logger = logging.getLogger(__name__)


class SignalValidationError(Exception):
    """Raised when signal validation fails"""
    pass


class SignalValidator:
    """
    Validates trading signals against user settings and market conditions
    """
    
    def __init__(self, user_settings: Optional[Dict[str, Any]] = None):
        self.user_settings = user_settings or {}
        self.allowed_symbols = self.user_settings.get('allowed_symbols', settings.ALLOWED_SYMBOLS)
        self.blocked_symbols = self.user_settings.get('blocked_symbols', [])
    
    def validate_symbol(self, symbol: str) -> Tuple[bool, str]:
        """Validate if symbol is allowed"""
        if symbol not in self.allowed_symbols:
            return False, f"Symbol {symbol} not in allowed list"
        
        if symbol in self.blocked_symbols:
            return False, f"Symbol {symbol} is blocked"
        
        return True, "Symbol valid"
    
    def validate_risk(self, risk_percentage: float) -> Tuple[bool, str]:
        """Validate risk percentage"""
        max_risk = self.user_settings.get('max_risk_per_trade', 0.05)  # 5% max
        min_risk = self.user_settings.get('min_risk_per_trade', 0.001)  # 0.1% min
        
        if risk_percentage > max_risk:
            return False, f"Risk {risk_percentage:.2%} exceeds maximum {max_risk:.2%}"
        
        if risk_percentage < min_risk:
            return False, f"Risk {risk_percentage:.2%} below minimum {min_risk:.2%}"
        
        return True, "Risk valid"
    
    def validate_price_distance(self, entry: float, current_price: float, 
                               symbol: str) -> Tuple[bool, str]:
        """Validate distance from current price"""
        min_distance = self.user_settings.get('min_distance_from_price', 0)
        if min_distance == 0:
            return True, "Distance check disabled"
        
        # Calculate pip distance
        multiplier = self._get_pip_multiplier(symbol)
        distance_pips = abs(entry - current_price) / multiplier
        
        if distance_pips < min_distance:
            return False, f"Entry too close to market price ({distance_pips:.0f} < {min_distance} pips)"
        
        return True, "Distance valid"
    
    def validate_spread(self, symbol: str, bid: float, ask: float) -> Tuple[bool, str]:
        """Validate spread is within limits"""
        max_spread = self.user_settings.get('max_spread')
        if not max_spread:
            return True, "Spread check disabled"
        
        spread = abs(ask - bid)
        if spread > max_spread:
            return False, f"Spread {spread:.5f} exceeds maximum {max_spread:.5f}"
        
        return True, "Spread valid"
    
    def _get_pip_multiplier(self, symbol: str) -> float:
        """Get pip multiplier for symbol"""
        if symbol == 'XAUUSD':
            return PIP_MULTIPLIERS['gold']
        elif symbol == 'XAGUSD':
            return PIP_MULTIPLIERS['silver']
        elif any(jpy in symbol for jpy in JPY_SYMBOLS):
            return 0.01
        else:
            return PIP_MULTIPLIERS['forex']


class SignalProcessor:
    """
    Processes raw text signals into structured trade objects
    Supports multiple signal formats and sources
    """
    
    def __init__(self):
        self.signal_patterns = {
            'standard': self._parse_standard_format,
            'compact': self._parse_compact_format,
            'json': self._parse_json_format,
        }
    
    def process(self, text: str, source: str = 'telegram') -> TradeSignal:
        """
        Process a raw signal text into a TradeSignal object
        """
        # Clean the text
        text = text.strip()
        
        # Try different parsers
        for parser_name, parser_func in self.signal_patterns.items():
            try:
                signal = parser_func(text)
                if signal:
                    # Add metadata
                    signal.metadata = {
                        'source': source,
                        'received_at': datetime.utcnow(),
                        'raw_text': text,
                        'hash': self._calculate_hash(text)
                    }
                    return signal
            except Exception as e:
                logger.debug(f"Parser {parser_name} failed: {e}")
                continue
        
        raise SignalValidationError("Could not parse signal with any known format")
    
    def _parse_standard_format(self, text: str) -> Optional[TradeSignal]:
        """
        Parse standard format:
        BUY/SELL [LIMIT/STOP] SYMBOL
        Entry PRICE or NOW
        SL PRICE
        TP1 PRICE
        TP2 PRICE (optional)
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        if len(lines) < 4:
            return None
        
        try:
            # Parse first line: ORDER_TYPE SYMBOL
            first_line_parts = lines[0].upper().split()
            
            # Handle order type with possible spaces (e.g., "BUY LIMIT")
            if len(first_line_parts) >= 3 and first_line_parts[1] in ['LIMIT', 'STOP']:
                order_text = f"{first_line_parts[0]} {first_line_parts[1]}"
                symbol = first_line_parts[2]
            else:
                order_text = first_line_parts[0]
                symbol = first_line_parts[1]
            
            # Convert to OrderType enum
            try:
                order_type = OrderType(order_text.title())
            except ValueError:
                logger.warning(f"Invalid order type: {order_text}")
                return None
            
            # Parse entry
            entry_line = lines[1].upper()
            if 'NOW' in entry_line:
                entry = None  # Market order
            else:
                entry = float(entry_line.split()[-1])
            
            # Parse stop loss
            stop_loss = float(lines[2].split()[-1])
            
            # Parse take profits (at least 1, max 2)
            take_profits = []
            for line in lines[3:5]:  # Max 2 TPs
                try:
                    tp = float(line.split()[-1])
                    take_profits.append(tp)
                except (ValueError, IndexError):
                    break
            
            if not take_profits:
                logger.warning("No take profits found")
                return None
            
            return TradeSignal(
                order_type=order_type,
                symbol=symbol,
                entry=entry,
                stop_loss=stop_loss,
                take_profits=take_profits
            )
            
        except (ValueError, IndexError) as e:
            logger.debug(f"Standard format parsing failed: {e}")
            return None
    
    def _parse_compact_format(self, text: str) -> Optional[TradeSignal]:
        """
        Parse compact format:
        BUY EURUSD 1.1000 SL 1.0950 TP1 1.1050 TP2 1.1100
        """
        # Pattern: ORDER SYMBOL [PRICE] SL PRICE TP1 PRICE [TP2 PRICE]
        pattern = r'^(BUY|SELL|BUY\s+LIMIT|SELL\s+LIMIT|BUY\s+STOP|SELL\s+STOP)\s+(\w+)(?:\s+(\d+\.?\d*|NOW))?\s+SL\s+(\d+\.?\d*)(?:\s+TP1\s+(\d+\.?\d*))?(?:\s+TP2\s+(\d+\.?\d*))?$'
        
        match = re.match(pattern, text.upper())
        if not match:
            return None
        
        groups = match.groups()
        
        try:
            order_text = groups[0]
            symbol = groups[1]
            entry_str = groups[2]
            sl = float(groups[3])
            tp1 = float(groups[4]) if groups[4] else None
            tp2 = float(groups[5]) if groups[5] else None
            
            # Convert order type
            try:
                order_type = OrderType(order_text.title())
            except ValueError:
                return None
            
            # Parse entry
            entry = None
            if entry_str and entry_str != 'NOW':
                entry = float(entry_str)
            
            # Build take profits
            take_profits = []
            if tp1:
                take_profits.append(tp1)
            if tp2:
                take_profits.append(tp2)
            
            if not take_profits:
                return None
            
            return TradeSignal(
                order_type=order_type,
                symbol=symbol,
                entry=entry,
                stop_loss=sl,
                take_profits=take_profits
            )
            
        except (ValueError, TypeError) as e:
            logger.debug(f"Compact format parsing failed: {e}")
            return None
    
    def _parse_json_format(self, text: str) -> Optional[TradeSignal]:
        """
        Parse JSON format:
        {"order_type": "BUY", "symbol": "EURUSD", "entry": 1.1000, ...}
        """
        import json
        
        try:
            data = json.loads(text)
            
            # Validate required fields
            required = ['order_type', 'symbol', 'stop_loss', 'take_profits']
            if not all(field in data for field in required):
                return None
            
            # Convert order type
            try:
                order_type = OrderType(data['order_type'].title())
            except ValueError:
                return None
            
            # Parse entry
            entry = data.get('entry')
            if entry and isinstance(entry, str) and entry.upper() == 'NOW':
                entry = None
            elif entry:
                entry = float(entry)
            
            return TradeSignal(
                order_type=order_type,
                symbol=data['symbol'],
                entry=entry,
                stop_loss=float(data['stop_loss']),
                take_profits=[float(tp) for tp in data['take_profits']]
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"JSON format parsing failed: {e}")
            return None
    
    def _calculate_hash(self, text: str) -> str:
        """Calculate hash of signal for duplicate detection"""
        # Normalize text
        normalized = ' '.join(text.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def extract_symbols(self, text: str) -> List[str]:
        """Extract potential symbols from text"""
        words = re.findall(r'\b[A-Z]{6}\b', text.upper())
        return [w for w in words if w in settings.ALLOWED_SYMBOLS]
    
    def is_duplicate(self, signal: TradeSignal, recent_signals: List[TradeSignal]) -> bool:
        """Check if signal is duplicate of recent signals"""
        for recent in recent_signals:
            if (recent.symbol == signal.symbol and
                recent.order_type == signal.order_type and
                abs(recent.stop_loss - signal.stop_loss) < 0.0001):
                return True
        return False


class SignalEnricher:
    """
    Enriches signals with additional data
    """
    
    def __init__(self):
        pass
    
    def add_pip_values(self, signal: TradeSignal) -> Dict[str, Any]:
        """Add pip values to signal"""
        # Determine pip multiplier
        if signal.symbol == 'XAUUSD':
            multiplier = 0.1
        elif signal.symbol == 'XAGUSD':
            multiplier = 0.001
        elif 'JPY' in signal.symbol:
            multiplier = 0.01
        else:
            multiplier = 0.0001
        
        # Calculate SL in pips
        if signal.entry:
            sl_pips = abs(signal.stop_loss - signal.entry) / multiplier
        else:
            sl_pips = None
        
        # Calculate TPs in pips
        tp_pips = []
        if signal.entry:
            for tp in signal.take_profits:
                tp_pips.append(abs(tp - signal.entry) / multiplier)
        
        return {
            'sl_pips': sl_pips,
            'tp_pips': tp_pips,
            'pip_multiplier': multiplier
        }
    
    def estimate_risk_reward(self, signal: TradeSignal) -> Dict[str, float]:
        """Estimate risk/reward ratio"""
        if not signal.entry:
            return {'rr_ratio': None}
        
        risk = abs(signal.entry - signal.stop_loss)
        if risk == 0:
            return {'rr_ratio': 0}
        
        # Average reward (for multiple TPs)
        avg_reward = sum(abs(tp - signal.entry) for tp in signal.take_profits) / len(signal.take_profits)
        
        return {
            'rr_ratio': avg_reward / risk,
            'risk': risk,
            'avg_reward': avg_reward
        }