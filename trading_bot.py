"""
Binance Trading Bot
A comprehensive trading bot framework for Binance exchange
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

from binance import AsyncClient, Client
from binance.enums import *
from binance.exceptions import BinanceAPIException


class BinanceTradingBot:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False, timeframe: str = Client.KLINE_INTERVAL_15MINUTE):
        """
        Initialize the trading bot
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Whether to use Binance testnet
            timeframe: Candle timeframe for analysis (default: 15 minutes)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.timeframe = timeframe
        self.client = None
        self.is_running = False
        self.leverage = 1  # Default to no leverage
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading_bot.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Trading parameters
        self.symbols = []  # List of symbols to trade
        self.strategies = {}  # Dictionary of trading strategies
        self.positions = {}  # Current positions
        self.balance = {}  # Account balance
        self.use_leverage = True  # Switch to enable/disable leverage (default: True)
        self.risk_management = {
            'max_position_size_spot': 0.10,  # Max 10% of account per position for spot trading
            'max_position_size_margin': 0.02,  # Max 2% of account per position for margin trading (before leverage)
            'max_daily_loss': 0.05,  # Max 5% daily loss
            'stop_loss_pct': 0.02,  # 2% stop loss (though stop loss is handled by engulfing pattern)
            'take_profit_pct': 0.05  # 5% take profit (though take profit is handled by 2.5R rule)
        }
    
    async def initialize_client(self):
        """Initialize the Binance client"""
        try:
            if self.testnet:
                self.client = await AsyncClient.create(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    testnet=True
                )
            else:
                self.client = await AsyncClient.create(
                    api_key=self.api_key,
                    api_secret=self.api_secret
                )
            self.logger.info("Binance client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Binance client: {e}")
            raise
    
    async def close_client(self):
        """Close the Binance client"""
        if self.client:
            await self.client.close_connection()
            self.logger.info("Binance client closed")
    
    async def get_account_info(self) -> Dict:
        """Get account information"""
        try:
            account_info = await self.client.get_account()
            self.balance = {asset['asset']: float(asset['free']) for asset in account_info['balances']}
            return account_info
        except BinanceAPIException as e:
            self.logger.error(f"Error getting account info: {e}")
            return {}
    
    async def get_symbol_info(self, symbol: str) -> Dict:
        """Get information about a specific symbol"""
        try:
            return await self.client.get_symbol_info(symbol)
        except BinanceAPIException as e:
            self.logger.error(f"Error getting symbol info for {symbol}: {e}")
            return {}
    
    async def get_ticker_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            ticker = await self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            self.logger.error(f"Error getting ticker price for {symbol}: {e}")
            return 0.0
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List:
        """Get kline/candlestick data for a symbol"""
        try:
            klines = await self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            return klines
        except BinanceAPIException as e:
            self.logger.error(f"Error getting klines for {symbol}: {e}")
            return []
    
    def calculate_sma(self, prices: List[float], period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return 0.0
        return sum(prices[-period:]) / period
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return 0.0
        
        multiplier = 2 / (period + 1)
        ema = prices[0]  # Start with first price
        
        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0  # Neutral value if not enough data
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        
        # Calculate average gain and loss
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """Calculate MACD indicator"""
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)
        macd_line = ema_fast - ema_slow
        
        # For simplicity, returning just the current values
        # A full implementation would track the signal line
        return macd_line, ema_fast, ema_slow
    
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
        and check for excessive volatility in the 5 candles before the engulfed candle
        
        Returns:
            'BULLISH_ENGULFING', 'BEARISH_ENGULFING', or 'NONE'
        """
        # Use the instance's timeframe if no interval is provided
        if interval is None:
            interval = self.timeframe
            
        # Get the last 7 candles (5 before engulfed + the engulfed + the engulfing)
        klines = await self.get_klines(symbol, interval, 7)  # Get 7 to have 5 previous + 1 engulfed + 1 engulfing
        if len(klines) < 7:
            return 'NONE'
        
        # Check volatility of the 5 candles before the engulfed candle (klines[-7], klines[-6], klines[-5], klines[-4], klines[-3])
        prev_5_candles = klines[-7:-2]  # The 5 candles before the engulfed candle
        volatility = await self.calculate_volatility(prev_5_candles)
        
        # Calculate average price to normalize volatility measurement
        total_avg_price = 0.0
        for candle in prev_5_candles:
            open_price = float(candle[1])
            close_price = float(candle[4])
            total_avg_price += (open_price + close_price) / 2
        
        avg_price = total_avg_price / len(prev_5_candles) if prev_5_candles else 1.0
        normalized_volatility = volatility / avg_price if avg_price > 0 else 0.0
        
        # Define a threshold for high volatility (e.g., if average range is more than 3% of price)
        volatility_threshold = 0.03  # 3% threshold - adjust as needed
        
        if normalized_volatility > volatility_threshold:
            # Too volatile, don't trade
            return 'NONE'
        
        # Get the last 2 candles for engulfing pattern detection
        prev_candle = klines[-2]       # Previous candle (pattern candle - the one being engulfed)
        curr_candle = klines[-1]       # Current candle (engulfing candle)
        
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
        
        # Check that the current candle engulfs the previous candle with exactly 130% body size
        if prev_close < prev_open:  # Previous candle is bearish (red)
            # Bullish engulfing: current bullish candle engulfs previous bearish candle with at least 130% body size
            if (curr_close > curr_open and  # Current candle is bullish (green)
                curr_close > prev_open and  # Current closes above previous open
                curr_open < prev_close and  # Current opens below previous close
                curr_body_size >= prev_body_size * 1.30):  # Current body is at least 130% of previous body
                return 'BULLISH_ENGULFING'
        
        elif prev_close > prev_open:  # Previous candle is bullish (green)
            # Bearish engulfing: current bearish candle engulfs previous bullish candle with at least 130% body size
            if (curr_close < curr_open and  # Current candle is bearish (red)
                curr_close < prev_open and  # Current closes below previous open
                curr_open > prev_close and  # Current opens above previous close
                curr_body_size >= prev_body_size * 1.30):  # Current body is at least 130% of previous body
                return 'BEARISH_ENGULFING'
        
        return 'NONE'

    async def get_trading_signal(self, symbol: str) -> str:
        """
        Determine trading signal based ONLY on engulfing patterns
        
        Returns:
            'BUY', 'SELL', or 'HOLD'
        """
        # Check for engulfing patterns only using the configured timeframe
        engulfing_signal = await self.detect_engulfing_pattern(symbol)
        
        if engulfing_signal == 'BULLISH_ENGULFING':
            return 'BUY'
        elif engulfing_signal == 'BEARISH_ENGULFING':
            return 'SELL'
        else:
            return 'HOLD'  # Only trade on engulfing patterns

    async def get_trading_signal_with_price(self, symbol: str):
        """
        Determine trading signal based ONLY on engulfing patterns and return the limit price
        
        Returns:
            tuple: (signal, limit_price) where signal is 'BUY', 'SELL', or 'HOLD' and limit_price is float or None
        """
        # Get the last 2 candles to determine the engulfing pattern and the opening price of the engulfed candle
        klines = await self.get_klines(symbol, self.timeframe, 3)
        if len(klines) < 2:
            return 'HOLD', None
        
        # Get the last 2 candles
        prev_candle = klines[-2]       # Previous candle (the one that was engulfed)
        curr_candle = klines[-1]       # Current candle (engulfing candle)
        
        # Parse candle data: [open_time, open, high, low, close, volume, ...]
        prev_open = float(prev_candle[1])  # Opening of the engulfed candle
        
        # Check for engulfing patterns only using the configured timeframe
        engulfing_signal = await self.detect_engulfing_pattern(symbol)
        
        if engulfing_signal == 'BULLISH_ENGULFING':
            # For bullish engulfing, place buy limit at the opening of the engulfed (previous) candle
            return 'BUY', prev_open
        elif engulfing_signal == 'BEARISH_ENGULFING':
            # For bearish engulfing, place sell limit at the opening of the engulfed (previous) candle
            return 'SELL', prev_open
        else:
            return 'HOLD', None  # Only trade on engulfing patterns
    
    async def place_order(self, symbol: str, side: str, quantity: float, order_type: str = ORDER_TYPE_MARKET, limit_price: float = None) -> Dict:
        """
        Place an order on Binance
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            side: 'BUY' or 'SELL'
            quantity: Amount to trade
            order_type: Order type (MARKET, LIMIT, etc.)
            limit_price: Specific price for limit orders (optional)
        """
        try:
            leverage = getattr(self, 'leverage', 1)
            
            if order_type == ORDER_TYPE_MARKET:
                order = await self.client.order_market(
                    symbol=symbol,
                    side=side,
                    quantity=quantity
                )
            elif order_type == ORDER_TYPE_LIMIT:
                if limit_price is not None:
                    price_str = str(limit_price)
                else:
                    # For limit orders, we'd need to calculate a price
                    current_price = await self.get_ticker_price(symbol)
                    price_str = str(current_price * 1.01 if side == SIDE_BUY else current_price * 0.99)
                
                order = await self.client.order_limit(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price_str
                )
            else:
                raise ValueError(f"Unsupported order type: {order_type}")
            
            self.logger.info(f"Order placed: {order}")
            return order
        except BinanceAPIException as e:
            self.logger.error(f"Error placing order for {symbol}: {e}")
            return {}

    async def execute_trade(self, symbol: str, signal: str, limit_price: float = None):
        """
        Execute a trade based on the given signal
        
        Args:
            symbol: Trading pair
            signal: Trading signal ('BUY', 'SELL', 'HOLD')
            limit_price: Specific price for limit orders (for engulfing patterns)
        """
        if signal == 'HOLD':
            return
        
        quantity = await self.calculate_position_size(symbol)
        
        if quantity <= 0:
            self.logger.warning(f"Insufficient funds or invalid quantity for {symbol}")
            return
        
        side = SIDE_BUY if signal == 'BUY' else SIDE_SELL
        order_type = ORDER_TYPE_LIMIT if limit_price is not None else ORDER_TYPE_MARKET
        
        self.logger.info(f"Executing {signal} order for {symbol}, quantity: {quantity}, type: {order_type}")
        
        # Place the main order
        order_result = await self.place_order(symbol, side, quantity, order_type, limit_price)
        
        if order_result:
            self.logger.info(f"Successfully executed {signal} order for {symbol}")
            
            # Set up stop-loss order based on engulfing pattern
            if 'orderId' in order_result:
                await self.place_stop_loss_order(symbol, signal, quantity, limit_price)
        else:
            self.logger.error(f"Failed to execute {signal} order for {symbol}")
    
    async def place_stop_loss_order(self, symbol: str, signal: str, quantity: float, entry_price: float = None):
        """
        Place a stop-loss order based on the engulfing pattern
        For bullish trades: stop-loss exactly 2% below the engulfed candle's low
        For bearish trades: stop-loss exactly 2% above the engulfed candle's high
        
        Args:
            symbol: Trading pair
            signal: Trading signal ('BUY' or 'SELL')
            quantity: Quantity to trade
            entry_price: Entry price for the trade
        """
        # Get the last 2 candles to determine the engulfed candle
        # klines[-2] is the engulfed candle, klines[-1] is the engulfing candle
        klines = await self.get_klines(symbol, self.timeframe, 3)
        if len(klines) < 2:
            self.logger.warning(f"Not enough kline data to set stop-loss for {symbol}")
            return
        
        # Get the engulfed candle (klines[-2])
        engulfed_candle = klines[-2]  # Previous candle (the engulfed one)
        
        # Parse candle data: [open_time, open, high, low, close, volume, ...]
        engulfed_open = float(engulfed_candle[1])
        engulfed_high = float(engulfed_candle[2])
        engulfed_low = float(engulfed_candle[3])
        engulfed_close = float(engulfed_candle[4])
        
        # Calculate stop-loss price based on signal and engulfed candle
        if signal == 'BUY':  # Bullish engulfing - buy signal
            # Stop-loss exactly 2% below the engulfed candle's low
            stop_loss_price = engulfed_low * (1 - 0.02)  # Exactly 2% below the low
            stop_price = stop_loss_price  # Same price for trigger
        elif signal == 'SELL':  # Bearish engulfing - sell signal
            # Stop-loss exactly 2% above the engulfed candle's high
            stop_loss_price = engulfed_high * (1 + 0.02)  # Exactly 2% above the high
            stop_price = stop_loss_price  # Same price for trigger
        else:
            return
        
        # Convert prices to strings with appropriate precision
        stop_price_str = f"{stop_price:.8f}"
        stop_loss_price_str = f"{stop_loss_price:.8f}"
        
        try:
            # Place the stop-loss order
            if signal == 'BUY':
                # For a long position, we place a stop-loss sell order
                stop_loss_order = await self.client.create_order(
                    symbol=symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_STOP_LOSS_LIMIT,
                    timeInForce=TIME_IN_FORCE_GTC,
                    quantity=quantity,
                    stopPrice=stop_price_str,
                    price=stop_loss_price_str
                )
            else:  # SELL signal
                # For a short position, we place a stop-loss buy order
                stop_loss_order = await self.client.create_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_STOP_LOSS_LIMIT,
                    timeInForce=TIME_IN_FORCE_GTC,
                    quantity=quantity,
                    stopPrice=stop_price_str,
                    price=stop_loss_price_str
                )
            
            self.logger.info(f"Stop-loss order placed for {symbol}: {signal}, Stop: {stop_loss_price_str}, Quantity: {quantity}")
            
            # Place take-profit order at 2.5R
            await self.place_take_profit_order(symbol, signal, quantity, entry_price, stop_loss_price)
            
            return stop_loss_order
        except BinanceAPIException as e:
            self.logger.error(f"Error placing stop-loss order for {symbol}: {e}")
            return {}
    
    async def place_take_profit_order(self, symbol: str, signal: str, quantity: float, entry_price: float = None, stop_loss_price: float = None):
        """
        Place a take-profit order at exactly 2.5R (2.5 times the risk)
        For bullish trades: take-profit at entry price + 2.5*(entry - stop_loss)
        For bearish trades: take-profit at entry price - 2.5*(stop_loss - entry)
        
        Args:
            symbol: Trading pair
            signal: Trading signal ('BUY' or 'SELL')
            quantity: Quantity to trade
            entry_price: Entry price for the trade
            stop_loss_price: Stop-loss price for the trade
        """
        if entry_price is None or stop_loss_price is None:
            self.logger.warning(f"Entry price or stop loss price not available for take-profit calculation for {symbol}")
            return
        
        try:
            # Calculate the risk (distance between entry and stop loss)
            risk_distance = abs(entry_price - stop_loss_price)
            
            if signal == 'BUY':  # Bullish trade
                # Take profit at exactly 2.5 times the risk distance above entry
                take_profit_price = entry_price + (2.5 * risk_distance)
                take_profit_price_str = f"{take_profit_price:.8f}"
                
                # Place take-profit order (limit sell order for long position)
                take_profit_order = await self.client.create_order(
                    symbol=symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_LIMIT,
                    timeInForce=TIME_IN_FORCE_GTC,
                    quantity=quantity,
                    price=take_profit_price_str
                )
                
            elif signal == 'SELL':  # Bearish trade
                # Take profit at exactly 2.5 times the risk distance below entry
                take_profit_price = entry_price - (2.5 * risk_distance)
                take_profit_price_str = f"{take_profit_price:.8f}"
                
                # Place take-profit order (limit buy order to close short position)
                take_profit_order = await self.client.create_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_LIMIT,
                    timeInForce=TIME_IN_FORCE_GTC,
                    quantity=quantity,
                    price=take_profit_price_str
                )
            
            self.logger.info(f"Take-profit order placed for {symbol}: {signal}, Target: {take_profit_price_str}, Quantity: {quantity}")
            return take_profit_order
        except BinanceAPIException as e:
            self.logger.error(f"Error placing take-profit order for {symbol}: {e}")
            return {}
    
    async def calculate_position_size(self, symbol: str) -> float:
        """
        Calculate appropriate position size based on risk management rules
        Uses either 10% for spot or 3% with leverage for margin based on use_leverage flag
        """
        # Get account balance in USDT (or base currency)
        account_info = await self.get_account_info()
        if 'USDT' in self.balance:
            available_balance = self.balance['USDT']
        else:
            # Fallback to calculating from account info
            available_balance = 0
            for asset in account_info.get('balances', []):
                if asset['asset'] == 'USDT':
                    available_balance = float(asset['free'])
                    break
        
        # Determine position size based on leverage setting
        if self.use_leverage:
            # Use margin trading with leverage (3% base position * leverage)
            leverage = getattr(self, 'leverage', 1)  # Use leverage from config, default to 1 if not set
            base_position_size = self.risk_management['max_position_size_margin']  # 3% for margin
            position_value = available_balance * base_position_size * leverage
        else:
            # Use spot trading (10% of account)
            base_position_size = self.risk_management['max_position_size_spot']  # 10% for spot
            position_value = available_balance * base_position_size  # No additional leverage
        
        # Get current price to calculate quantity
        current_price = await self.get_ticker_price(symbol)
        
        if current_price <= 0:
            self.logger.warning(f"Invalid price for {symbol}: {current_price}")
            return 0.0
        
        quantity = position_value / current_price
        
        # Get symbol info for lot size constraints
        symbol_info = await self.get_symbol_info(symbol)
        if symbol_info:
            for filter_item in symbol_info['filters']:
                if filter_item['filterType'] == 'LOT_SIZE':
                    min_qty = float(filter_item['minQty'])
                    max_qty = float(filter_item['maxQty'])
                    step_size = float(filter_item['stepSize'])
                    
                    # Adjust quantity to fit within limits
                    quantity = max(min_qty, min(quantity, max_qty))
                    
                    # Round to step size
                    quantity = round((quantity - (quantity % step_size)) * 100000000) / 100000000
                    break
        
        return quantity
    
    async def execute_trade(self, symbol: str, signal: str, limit_price: float = None):
        """Execute a trade based on the given signal"""
        if signal == 'HOLD':
            return
        
        quantity = await self.calculate_position_size(symbol)
        
        if quantity <= 0:
            self.logger.warning(f"Insufficient funds or invalid quantity for {symbol}")
            return
        
        side = SIDE_BUY if signal == 'BUY' else SIDE_SELL
        
        self.logger.info(f"Executing {signal} order for {symbol}, quantity: {quantity}")
        
        # Place the order
        order_result = await self.place_order(symbol, side, quantity)
        
        if order_result:
            self.logger.info(f"Successfully executed {signal} order for {symbol}")
            
            # Set up stop-loss order based on engulfing pattern
            if 'orderId' in order_result:
                await self.place_stop_loss_order(symbol, signal, quantity, limit_price)
        else:
            self.logger.error(f"Failed to execute {signal} order for {symbol}")
    
    async def run_strategy(self, symbol: str):
        """Run a single strategy iteration for a symbol"""
        try:
            signal, limit_price = await self.get_trading_signal_with_price(symbol)
            self.logger.info(f"Signal for {symbol}: {signal}")
            
            await self.execute_trade(symbol, signal, limit_price)
        except Exception as e:
            self.logger.error(f"Error running strategy for {symbol}: {e}")
    
    async def run(self, symbols: List[str], interval: int = 60):
        """
        Main loop to run the trading bot
        
        Args:
            symbols: List of symbols to trade
            interval: Interval in seconds between strategy runs
        """
        if not self.client:
            await self.initialize_client()
        
        self.symbols = symbols
        self.is_running = True
        
        self.logger.info(f"Starting trading bot for symbols: {symbols}")
        
        try:
            while self.is_running:
                tasks = []
                
                # Run strategy for each symbol concurrently
                for symbol in self.symbols:
                    task = asyncio.create_task(self.run_strategy(symbol))
                    tasks.append(task)
                
                # Wait for all strategies to complete
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Sleep before next iteration
                await asyncio.sleep(interval)
        
        except KeyboardInterrupt:
            self.logger.info("Stopping trading bot...")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the trading bot"""
        self.is_running = False
        await self.close_client()
        self.logger.info("Trading bot stopped")


def load_config(config_file: str = 'config.json') -> Dict:
    """Load configuration from file"""
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    else:
        # Return default configuration
        return {
            "api_key": "",
            "api_secret": "",
            "testnet": True,
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "leverage": 4,  # 4x leverage
            "use_leverage": True,  # Enable/disable leverage (True for margin trading, False for spot)
            "timeframe": "15m",  # 15-minute timeframe as default
            "risk_management": {
                "max_position_size_margin": 0.02,  # 2% per trade as specified (before leverage)
                "max_daily_loss": 0.05,
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.05
            }
        }


async def main():
    """Main function to run the trading bot"""
    config = load_config()
    
    # Map string timeframe to Binance interval constant
    timeframe_map = {
        "1m": Client.KLINE_INTERVAL_1MINUTE,
        "3m": Client.KLINE_INTERVAL_3MINUTE,
        "5m": Client.KLINE_INTERVAL_5MINUTE,
        "15m": Client.KLINE_INTERVAL_15MINUTE,
        "30m": Client.KLINE_INTERVAL_30MINUTE,
        "1h": Client.KLINE_INTERVAL_1HOUR,
        "2h": Client.KLINE_INTERVAL_2HOUR,
        "4h": Client.KLINE_INTERVAL_4HOUR,
        "6h": Client.KLINE_INTERVAL_6HOUR,
        "8h": Client.KLINE_INTERVAL_8HOUR,
        "12h": Client.KLINE_INTERVAL_12HOUR,
        "1d": Client.KLINE_INTERVAL_1DAY,
        "3d": Client.KLINE_INTERVAL_3DAY,
        "1w": Client.KLINE_INTERVAL_1WEEK,
        "1mo": Client.KLINE_INTERVAL_1MONTH,
    }
    
    # Get timeframe from config, default to 15m if not specified
    timeframe_str = config.get('timeframe', '15m')
    timeframe = timeframe_map.get(timeframe_str, Client.KLINE_INTERVAL_15MINUTE)
    
    # Create trading bot instance
    bot = BinanceTradingBot(
        api_key=config['api_key'],
        api_secret=config['api_secret'],
        testnet=config.get('testnet', False),
        timeframe=timeframe
    )
    
    # Update risk management settings from config
    bot.risk_management.update(config.get('risk_management', {}))
    
    # Store leverage settings
    bot.leverage = config.get('leverage', 1)  # Default to no leverage if not specified
    bot.use_leverage = config.get('use_leverage', True)  # Default to using leverage if not specified
    
    # Run the bot with specified symbols
    symbols = config.get('symbols', ['BTCUSDT'])
    await bot.run(symbols, interval=60)  # Run every minute


if __name__ == "__main__":
    # For testing purposes, we'll run the main function
    # asyncio.run(main())
    pass