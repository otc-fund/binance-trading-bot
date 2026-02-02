"""
Pattern Detector Module
Handles all pattern detection logic for the trading bot
"""

from binance import Client
from typing import List, Tuple
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class PatternDetector:
    def __init__(self, client, timeframe: str = Client.KLINE_INTERVAL_15MINUTE):
        self.client = client
        self.timeframe = timeframe
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List:
        """Get kline/candlestick data for a symbol"""
        try:
            logger.debug(f"Fetching {limit} klines for {symbol} at {interval}")
            klines = await self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            logger.debug(f"Successfully fetched {len(klines)} klines for {symbol}")
            return klines
        except Exception as e:
            logger.error(f"Error getting klines for {symbol}: {e}")
            return []
    
    async def calculate_volatility(self, klines: List) -> float:
        """
        Calculate volatility based on the average range of the last 5 candles
        
        Args:
            klines: List of candle data
            
        Returns:
            float: Volatility measure (average of high-low ranges)
        """
        if len(klines) < 5:
            return 0.0
        
        # Get the last 5 candles
        recent_candles = klines[-5:]
        
        total_range = 0.0
        for candle in recent_candles:
            high = float(candle[2])
            low = float(candle[3])
            total_range += (high - low)
        
        avg_range = total_range / len(recent_candles)
        return avg_range

    async def detect_engulfing_pattern(self, symbol: str, interval: str = None) -> str:
        """
        Detect bullish and bearish engulfing patterns with exactly 130% body coverage
        and check for excessive volatility in the 3 candles before the engulfed candle
        and volume confirmation on the engulfing candle
        
        Returns:
            'BULLISH_ENGULFING', 'BEARISH_ENGULFING', or 'NONE'
        """
        # Use the instance's timeframe if no interval is provided
        if interval is None:
            interval = self.timeframe
            
        # Get the last 6 candles (3 before engulfed + the engulfed + the engulfing)
        klines = await self.get_klines(symbol, interval, 6)  # Get 6 to have 3 previous + 1 engulfed + 1 engulfing
        if len(klines) < 6:
            return 'NONE'
        
        # Check volatility of the 3 candles before the engulfed candle (klines[-6], klines[-5], klines[-4])
        prev_3_candles = klines[-6:-3]  # The 3 candles before the engulfed candle
        volatility = await self.calculate_volatility(prev_3_candles)
        
        # Calculate average price to normalize volatility measurement
        total_avg_price = 0.0
        for candle in prev_3_candles:
            open_price = float(candle[1])
            close_price = float(candle[4])
            total_avg_price += (open_price + close_price) / 2
        
        avg_price = total_avg_price / len(prev_3_candles) if prev_3_candles else 1.0
        normalized_volatility = volatility / avg_price if avg_price > 0 else 0.0
        
        # Define a threshold for high volatility (e.g., if average range is more than 3% of price)
        volatility_threshold = 0.03  # 3% threshold - adjust as needed
        
        # Get the last 2 candles for engulfing pattern detection
        prev_candle = klines[-2]       # Previous candle (pattern candle - the one being engulfed)
        curr_candle = klines[-1]       # Current candle (engulfing candle)
        
        # Parse candle data: [open_time, open, high, low, close, volume, ...]
        prev_open = float(prev_candle[1])
        prev_high = float(prev_candle[2])
        prev_low = float(prev_candle[3])
        prev_close = float(prev_candle[4])
        prev_volume = float(prev_candle[5])  # Volume is at index 5
        
        curr_open = float(curr_candle[1])
        curr_high = float(curr_candle[2])
        curr_low = float(curr_candle[3])
        curr_close = float(curr_candle[4])
        curr_volume = float(curr_candle[5])  # Volume is at index 5
        
        # Calculate body sizes (absolute difference between open and close)
        prev_body_size = abs(prev_close - prev_open)
        curr_body_size = abs(curr_close - curr_open)
        
        # Calculate average volume of previous candles to compare against
        # Look at the last 5 candles to get average volume (excluding current engulfing candle)
        vol_sum = 0
        vol_count = 0
        for i in range(-6, -1):  # From klines[-6] to klines[-2] (previous 5 candles)
            if abs(i) <= len(klines):  # Make sure we're not out of bounds
                vol_sum += float(klines[i][5])  # Volume is at index 5
                vol_count += 1
        
        avg_volume = vol_sum / vol_count if vol_count > 0 else 0
        
        # Check that the current candle engulfs the previous candle with exactly 130% body size
        if prev_close < prev_open:  # Previous candle is bearish (red)
            # Bullish engulfing: current bullish candle engulfs previous bearish candle with at least 130% body size
            if (curr_close > curr_open and  # Current candle is bullish (green)
                curr_close > prev_open and  # Current closes above previous open
                curr_open < prev_close and  # Current opens below previous close
                curr_body_size >= prev_body_size * 1.30):  # Current body is at least 130% of previous body
                # Check volume confirmation - engulfing candle should have higher than average volume
                volume_confirmed = curr_volume > avg_volume * 1.2  # At least 20% above average volume
                
                # Log when an engulfing pattern is detected before volatility check
                logger.debug(f"Bullish engulfing pattern detected for {symbol} at {curr_close}, checking volume and volatility filters...")
                
                # Log volume information
                logger.debug(f"Volume - Current: {curr_volume:.2f}, Avg: {avg_volume:.2f}, Confirmed: {volume_confirmed}")
                
                if normalized_volatility > volatility_threshold:
                    logger.debug(f"Bullish engulfing pattern for {symbol} rejected due to high volatility ({normalized_volatility:.4f} > {volatility_threshold:.4f})")
                elif not volume_confirmed:
                    logger.debug(f"Bullish engulfing pattern for {symbol} rejected due to insufficient volume (Curr: {curr_volume:.2f} <= Avg: {avg_volume:.2f})")
                else:
                    logger.debug(f"Bullish engulfing pattern for {symbol} passed all filters (Volatility: {normalized_volatility:.4f} <= {volatility_threshold:.4f}, Volume: {curr_volume:.2f} > {avg_volume:.2f})")
                    return 'BULLISH_ENGULFING'
        
        elif prev_close > prev_open:  # Previous candle is bullish (green)
            # Bearish engulfing: current bearish candle engulfs previous bullish candle with at least 130% body size
            if (curr_close < curr_open and  # Current candle is bearish (red)
                curr_close < prev_open and  # Current closes below previous open
                curr_open > prev_close and  # Current opens above previous close
                curr_body_size >= prev_body_size * 1.30):  # Current body is at least 130% of previous body
                # Check volume confirmation - engulfing candle should have higher than average volume
                volume_confirmed = curr_volume > avg_volume * 1.2  # At least 20% above average volume
                
                # Log when an engulfing pattern is detected before volatility check
                logger.debug(f"Bearish engulfing pattern detected for {symbol} at {curr_close}, checking volume and volatility filters...")
                
                # Log volume information
                logger.debug(f"Volume - Current: {curr_volume:.2f}, Avg: {avg_volume:.2f}, Confirmed: {volume_confirmed}")
                
                if normalized_volatility > volatility_threshold:
                    logger.debug(f"Bearish engulfing pattern for {symbol} rejected due to high volatility ({normalized_volatility:.4f} > {volatility_threshold:.4f})")
                elif not volume_confirmed:
                    logger.debug(f"Bearish engulfing pattern for {symbol} rejected due to insufficient volume (Curr: {curr_volume:.2f} <= Avg: {avg_volume:.2f})")
                else:
                    logger.debug(f"Bearish engulfing pattern for {symbol} passed all filters (Volatility: {normalized_volatility:.4f} <= {volatility_threshold:.4f}, Volume: {curr_volume:.2f} > {avg_volume:.2f})")
                    return 'BEARISH_ENGULFING'
        
        return 'NONE'

    async def get_trading_signal_with_price(self, symbol: str, interval: str = None) -> Tuple[str, float]:
        """
        Determine trading signal based ONLY on engulfing patterns and return the limit price
        
        Returns:
            tuple: (signal, limit_price) where signal is 'BUY', 'SELL', or 'HOLD' and limit_price is float or None
        """
        if interval is None:
            interval = self.timeframe
            
        # Get the last 2 candles to determine the engulfing pattern and the opening price of the engulfed candle
        klines = await self.get_klines(symbol, interval, 3)
        if len(klines) < 2:
            return 'HOLD', None
        
        # Get the last 2 candles
        prev_candle = klines[-2]       # Previous candle (the one that was engulfed)
        curr_candle = klines[-1]       # Current candle (engulfing candle)
        
        # Parse candle data: [open_time, open, high, low, close, volume, ...]
        prev_open = float(prev_candle[1])
        prev_high = float(prev_candle[2])
        prev_low = float(prev_candle[3])
        prev_close = float(prev_candle[4])
        
        # Calculate the body of the engulfed candle (absolute difference between open and close)
        prev_body_size = abs(prev_close - prev_open)
        
        # Calculate entry price offset as 60% of the body
        entry_price_offset = prev_body_size * 0.60
        
        # Check for engulfing patterns only using the configured timeframe
        engulfing_signal = await self.detect_engulfing_pattern(symbol, interval)
        
        if engulfing_signal == 'BULLISH_ENGULFING':
            # For bullish engulfing, place buy limit at 60% LOWER than the open of the engulfed candle
            entry_price = prev_open - entry_price_offset
            logger.debug(f"Bullish engulfing signal generated for {symbol}, entry price: {entry_price}")
            return 'BUY', entry_price
        elif engulfing_signal == 'BEARISH_ENGULFING':
            # For bearish engulfing, place sell limit at 60% HIGHER than the open of the engulfed candle
            entry_price = prev_open + entry_price_offset
            logger.debug(f"Bearish engulfing signal generated for {symbol}, entry price: {entry_price}")
            return 'SELL', entry_price
        else:
            logger.debug(f"No engulfing signal for {symbol}, signal: HOLD")
            return 'HOLD', None  # Only trade on engulfing patterns