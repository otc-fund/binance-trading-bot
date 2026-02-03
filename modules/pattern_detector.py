"""
Pattern Detector Module
Handles all pattern detection logic for the trading bot
"""

from binance import Client
from typing import List, Tuple
from decimal import Decimal
import logging
from datetime import datetime

# Get logger and ensure it has the same handlers as the main trading bot
logger = logging.getLogger(__name__)

# Add file handler to ensure logging to file
file_handler = logging.FileHandler('trading_bot.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Prevent adding duplicate handlers
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all log levels


class PatternDetector:
    def __init__(self, client, timeframe: str = Client.KLINE_INTERVAL_15MINUTE):
        self.client = client
        self.timeframe = timeframe
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List:
        """Get kline/candlestick data for a symbol"""
        try:
            # Console output for visibility and log for file output
            kline_request_msg = f"[KLINE REQUEST] {datetime.now().strftime('%H:%M:%S')} - Fetching {limit} klines for {symbol} at {interval}"
            print(kline_request_msg)
            logger.info(kline_request_msg)
            
            klines = await self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            # Console output for visibility and log for file output
            kline_response_msg = f"[KLINE RESPONSE] {datetime.now().strftime('%H:%M:%S')} - Successfully fetched {len(klines)} klines for {symbol}"
            print(kline_response_msg)
            logger.info(kline_response_msg)
            
            # Log details about all klines in the response (up to the last 4 for visibility)
            if klines:
                # Determine how many candles to log (up to 4 for the last 4 candles)
                candles_to_log = min(len(klines), 4)
                
                for i in range(1, candles_to_log + 1):
                    candle = klines[-i]  # Get the i-th most recent candle
                    position = f"{i}{'st' if i==1 else 'nd' if i==2 else 'rd' if i==3 else 'th'} most recent"
                    open_price = candle[1]
                    high = candle[2]
                    low = candle[3]
                    close = candle[4]
                    volume = candle[5]
                    
                    # Console output for visibility and log for file output
                    kline_details_msg = f"[KLINE DETAILS] {datetime.now().strftime('%H:%M:%S')} - {position} candle for {symbol} - O: {open_price}, H: {high}, L: {low}, C: {close}, V: {volume}"
                    print(kline_details_msg)
                    logger.info(kline_details_msg)
            
            return klines
        except Exception as e:
            # Console output for visibility and log for file output
            kline_error_msg = f"[KLINE ERROR] {datetime.now().strftime('%H:%M:%S')} - Error getting klines for {symbol}: {e}"
            print(kline_error_msg)
            logger.error(kline_error_msg)
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
        Detect bullish and bearish 130%+ engulfing patterns
        in the last 4 candles, checking each pair for potential patterns
        
        Returns:
            'BULLISH_ENGULFING', 'BEARISH_ENGULFING', or 'NONE'
        """
        # Use the instance's timeframe if no interval is provided
        if interval is None:
            interval = self.timeframe
            
        # Get the last 4 candles to check for engulfing patterns
        klines = await self.get_klines(symbol, interval, 4)
        if len(klines) < 2:
            return 'NONE'
        
        # Check for engulfing patterns in the last 4 candles by examining each consecutive pair
        # For 4 candles we have positions [0, 1, 2, 3], we check pairs: [2,3], [1,2], [0,1]
        # Or in negative indexing: [-2,-1], [-3,-2], [-4,-3]
        for i in range(len(klines)-2, -1, -1):  # Go backwards from second-to-last to first
            # Get the current pair of candles
            prev_candle = klines[i]      # Previous candle (the one being engulfed)
            curr_candle = klines[i+1]    # Current candle (engulfing candle)
            
            # Parse candle data: [open_time, open, high, low, close, volume, ...]
            prev_open = float(prev_candle[1])
            prev_high = float(prev_candle[2])
            prev_low = float(prev_candle[3])
            prev_close = float(prev_candle[4])
            
            curr_open = float(curr_candle[1])
            curr_high = float(curr_candle[2])
            curr_low = float(curr_candle[3])
            curr_close = float(curr_candle[4])
            
            # Calculate body sizes (absolute difference between open and close)
            prev_body_size = abs(prev_close - prev_open)
            curr_body_size = abs(curr_close - curr_open)
            
            # Check that the current candle engulfs the previous candle with at least 130% body size
            if prev_close < prev_open:  # Previous candle is bearish (red)
                # Bullish engulfing: current bullish candle engulfs previous bearish candle with at least 130% body size
                if (curr_close > curr_open and  # Current candle is bullish (green)
                    curr_close > prev_open and  # Current closes above previous open
                    curr_open < prev_close and  # Current opens below previous close
                    curr_body_size >= prev_body_size * 1.30):  # Current body is at least 130% of previous body
                    # NEW: Allow any 130%+ engulfing pattern without volume/volatility filters
                    logger.debug(f"Bullish 130%+ engulfing pattern for {symbol} detected at position {i} and approved (volume/volatility checks temporarily disabled)")
                    return 'BULLISH_ENGULFING'
            
            elif prev_close > prev_open:  # Previous candle is bullish (green)
                # Bearish engulfing: current bearish candle engulfs previous bullish candle with at least 130% body size
                if (curr_close < curr_open and  # Current candle is bearish (red)
                    curr_close < prev_open and  # Current closes below previous open
                    curr_open > prev_close and  # Current opens above previous close
                    curr_body_size >= prev_body_size * 1.30):  # Current body is at least 130% of previous body
                    # NEW: Allow any 130%+ engulfing pattern without volume/volatility filters
                    logger.debug(f"Bearish 130%+ engulfing pattern for {symbol} detected at position {i} and approved (volume/volatility checks temporarily disabled)")
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
        
        # Check for engulfing patterns only using the configured timeframe
        engulfing_signal = await self.detect_engulfing_pattern(symbol, interval)
        
        if engulfing_signal == 'BULLISH_ENGULFING':
            # For bullish engulfing, place buy limit at 60% of the way from the low to the high of the engulfed candle
            # This means 60% of the range added to the low
            prev_range = prev_high - prev_low
            entry_price = prev_low + (prev_range * 0.60)
            logger.debug(f"Bullish engulfing signal generated for {symbol}, entry price: {entry_price} (60% of engulfed candle range from low: {prev_low} to high: {prev_high})")
            return 'BUY', entry_price
        elif engulfing_signal == 'BEARISH_ENGULFING':
            # For bearish engulfing, place sell limit at 60% of the way from the high to the low of the engulfed candle
            # This means 60% of the range subtracted from the high
            prev_range = prev_high - prev_low
            entry_price = prev_high - (prev_range * 0.60)
            logger.debug(f"Bearish engulfing signal generated for {symbol}, entry price: {entry_price} (60% of engulfed candle range from high: {prev_high} to low: {prev_low})")
            return 'SELL', entry_price
        else:
            logger.debug(f"No engulfing signal for {symbol}, signal: HOLD")
            return 'HOLD', None  # Only trade on engulfing patterns