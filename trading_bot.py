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

from modules.database import DatabaseManager
from modules.performance_tracker import PerformanceTracker
from modules.pattern_detector import PatternDetector
from modules.risk_manager import RiskManager
from modules.notifications import NotificationSystem



import logging
import sys

# Configure logging to write to a file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
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

        # Initialize modules
        self.db_manager = DatabaseManager()
        self.performance_tracker = PerformanceTracker(self.db_manager)
        self.pattern_detector = PatternDetector(None, self.timeframe)
        self.risk_manager = RiskManager(None, True, self.leverage)
        self.notification_system = NotificationSystem()

        # Load notification settings
        self.recipient_emails = []
        self.enable_notifications = False

        # Trading parameters
        self.symbols = []  # List of symbols to trade
        self.positions = {}  # Current positions
        self.balance = {}  # Account balance
        self.use_leverage = True  # Switch to enable/disable leverage (default: True)
        self.last_signals = {}  # Track last signals to prevent duplicates

    async def initialize_client(self):
        """Initialize the Binance client"""
        try:
            # For testnet, we need to handle the demo environment properly
            # According to Binance docs for demo mode
            if self.testnet:
                # Initialize client for testnet with proper configuration
                self.client = await AsyncClient.create(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    testnet=True
                )
            else:
                # For live trading
                self.client = await AsyncClient.create(
                    api_key=self.api_key,
                    api_secret=self.api_secret
                )

            self.logger.info("Binance client initialized successfully")

            # Set position mode to One-Way (Hedge mode off) to allow simple LONG/SHORT orders
            try:
                # Set the account's position mode to One-Way
                await self.client.futures_change_position_mode(dualSidePosition=False)
                self.logger.info("Position mode set to One-Way (dualSidePosition=False)")
            except Exception as e:
                # This might fail if the account is already in One-Way mode or if not supported
                self.logger.warning(f"Could not change position mode (this is OK if already in One-Way mode): {e}")

            # Initialize modules with client
            if self.pattern_detector:
                self.pattern_detector.client = self.client
            if self.risk_manager:
                self.risk_manager.client = self.client

            # Initialize database
            self.db_manager.connect()

            # Initialize balance tracking after client is set
            # Using the improved futures account methods that should work on testnet
            try:
                # Try to get actual account balance using the new futures methods
                await self.update_balances()
            except Exception as e:
                self.logger.warning(f"Could not update balances: {e}")
                # Set a reasonable default balance if all methods fail
                self.balance = {'USDT': 5000.0}  # Default balance when all account methods fail

        except Exception as e:
            self.logger.error(f"Failed to initialize Binance client: {e}")
            raise

    async def close_client(self):
        """Close the Binance client"""
        if self.client:
            await self.client.close_connection()
            self.logger.info("Binance client closed")

    async def update_balances(self):
        """Update account balances"""
        try:
            # Make sure the risk manager has the client before attempting to get account info
            if self.risk_manager is None:
                self.logger.warning("Risk manager is not set, skipping balance update")
                self.balance = {'USDT': 0.0}
                return

            if self.risk_manager.client is None:
                self.logger.warning("Risk manager client is not set, skipping balance update")
                self.balance = {'USDT': 0.0}
                return

            account_info = await self.risk_manager.get_account_info()
            if account_info and 'USDT' in self.risk_manager.balance:
                self.balance = self.risk_manager.balance
        except AttributeError as ae:
            if "'NoneType' object has no attribute 'get_account'" in str(ae):
                self.logger.warning(f"Client not properly initialized for balance update: {ae}")
                self.balance = {'USDT': 10000.0}  # Default demo balance
            else:
                self.logger.warning(f"Attribute error during balance update: {ae}")
                self.balance = {'USDT': 0.0}
        except Exception as e:
            self.logger.warning(f"Could not update balances: {e}")
            # Set a default balance if API call fails
            self.balance = {'USDT': 0.0}

    async def adjust_price_to_tick_size(self, symbol: str, price: float) -> float:
        """Adjust price to comply with symbol's tick size requirements"""
        try:
            symbol_info = await self.client.futures_exchange_info()
            symbol_detail = None
            for item in symbol_info['symbols']:
                if item['symbol'] == symbol:
                    symbol_detail = item
                    break

            if symbol_detail:
                # Get the tick size for the symbol
                for filter_item in symbol_detail['filters']:
                    if filter_item['filterType'] == 'PRICE_FILTER':
                        tick_size = float(filter_item['tickSize'])
                        # Round the price to the nearest tick size
                        adjusted_price = round(price / tick_size) * tick_size
                        return adjusted_price

            # If no tick size found, return original price
            return price
        except Exception as e:
            self.logger.warning(f"Could not adjust price to tick size for {symbol}: {e}, returning original price")
            return price

    def get_usdt_balance(self) -> float:
        """Get current USDT balance"""
        if 'USDT' in self.balance:
            return self.balance['USDT']
        return 0.0

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

            # Get the symbol's price precision for limit orders
            price_precision = 8  # Default precision
            quantity_precision = 8  # Default quantity precision
            if order_type == ORDER_TYPE_LIMIT and limit_price is not None:
                try:
                    symbol_info = await self.client.futures_exchange_info()
                    symbol_detail = None
                    for item in symbol_info['symbols']:
                        if item['symbol'] == symbol:
                            symbol_detail = item
                            break

                    if symbol_detail:
                        price_precision = symbol_detail['pricePrecision']
                        # Also get quantity precision
                        for filter_item in symbol_detail['filters']:
                            if filter_item['filterType'] == 'LOT_SIZE':
                                quantity_precision = len(filter_item['stepSize'].split('.')[-1]) if '.' in filter_item['stepSize'] else 0
                                break
                except Exception as e:
                    # If we can't get symbol info, use default precision
                    self.logger.warning(f"Could not get symbol precision for {symbol}: {e}")
                    price_precision = 8

            # For futures trading (including testnet), we need to use futures endpoints
            # Check if we're dealing with futures vs spot
            if self.use_leverage:  # Use futures if leverage is enabled
                # Format quantity according to symbol's LOT_SIZE requirements
                formatted_quantity = f"{quantity:.{quantity_precision}f}".rstrip('0').rstrip('.')

                # For futures trading, use futures endpoints
                # Set positionSide to BOTH to allow both long and short positions
                if order_type == ORDER_TYPE_MARKET:
                    order = await self.client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type=ORDER_TYPE_MARKET,
                        quantity=formatted_quantity,
                        # Set position side to BOTH to allow both long/short
                        positionSide='BOTH',
                        # Set margin mode to ISOLATED
                        marginMode='ISOLATED'
                    )
                elif order_type == ORDER_TYPE_LIMIT:
                    if limit_price is not None:
                        # Adjust price to tick size requirements
                        adjusted_price = await self.adjust_price_to_tick_size(symbol, limit_price)
                        price_str = f"{adjusted_price:.{price_precision}f}"
                    else:
                        # For limit orders, we'd need to calculate a price
                        current_price = await self.risk_manager.get_ticker_price(symbol)
                        base_price = current_price * 1.01 if side == SIDE_BUY else current_price * 0.99
                        adjusted_price = await self.adjust_price_to_tick_size(symbol, base_price)
                        price_str = f"{adjusted_price:.{price_precision}f}"

                    order = await self.client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type=ORDER_TYPE_LIMIT,
                        quantity=formatted_quantity,
                        price=price_str,
                        timeInForce=TIME_IN_FORCE_GTC,  # Required for LIMIT orders
                        # Set position side to BOTH to allow both long/short
                        positionSide='BOTH',
                        # Set margin mode to ISOLATED
                        marginMode='ISOLATED'
                    )
                else:
                    raise ValueError(f"Unsupported order type: {order_type}")
            else:  # Spot trading (including testnet)
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
                        current_price = await self.risk_manager.get_ticker_price(symbol)
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
            if e.code == -2015:  # Invalid API-key, IP, or permissions for action
                self.logger.warning(f"API permission issue placing order for {symbol}: {e}. This may be expected on testnet.")
                # Return a mock order to allow simulation to continue
                return {
                    'orderId': 0,
                    'symbol': symbol,
                    'transactTime': 0,
                    'price': str(limit_price or 0),
                    'origQty': str(quantity),
                    'executedQty': str(quantity),
                    'status': 'FILLED',
                    'type': order_type,
                    'side': side
                }
            else:
                self.logger.error(f"Binance API error placing order for {symbol}: {e}")
                return {}
        except Exception as e:
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

        quantity = await self.risk_manager.calculate_position_size(symbol)

        if quantity <= 0:
            self.logger.warning(f"Insufficient funds or invalid quantity for {symbol}")
            return

        # Determine side based on signal
        if signal == 'BUY':
            side = SIDE_BUY
        elif signal == 'SELL':
            side = SIDE_SELL  # For bearish signals, sell to open short position
        else:
            return

        # Check if we already have open orders OR active positions for this symbol to avoid duplicate orders
        try:
            # Get current open orders for this symbol
            open_orders = await self.client.futures_get_open_orders(symbol=symbol)

            # Get current positions for this symbol
            positions = await self.client.futures_position_information(symbol=symbol)
            current_position = None
            for pos in positions:
                if pos['symbol'] == symbol:
                    current_position = pos
                    break

            # Check open orders first
            if open_orders:
                # Count existing orders by type
                existing_buy_orders = [o for o in open_orders if o['side'] == 'BUY']
                existing_sell_orders = [o for o in open_orders if o['side'] == 'SELL']

                # For BUY signals, skip if there's already a BUY order (to open a long position)
                if signal == 'BUY' and existing_buy_orders:
                    existing_prices = [float(o['price']) for o in existing_buy_orders]
                    self.logger.info(f"Skipping BUY signal for {symbol} - already has {len(existing_buy_orders)} BUY order(s) at prices: {existing_prices}")
                    return

                # For SELL signals, skip if there's already a SELL order (to open a short position)
                elif signal == 'SELL' and existing_sell_orders:
                    existing_prices = [float(o['price']) for o in existing_sell_orders]
                    self.logger.info(f"Skipping SELL signal for {symbol} - already has {len(existing_sell_orders)} SELL order(s) at prices: {existing_prices}")
                    return

            # Check active positions
            if current_position:
                position_amount = float(current_position['positionAmt'])
                # If we have an active long position (positive amount) and getting a BUY signal
                if position_amount > 0 and signal == 'BUY':
                    self.logger.info(f"Skipping BUY signal for {symbol} - already has a long position of {position_amount}")
                    return
                # If we have an active short position (negative amount) and getting a SELL signal
                elif position_amount < 0 and signal == 'SELL':
                    self.logger.info(f"Skipping SELL signal for {symbol} - already has a short position of {position_amount}")
                    return

        except Exception as e:
            self.logger.warning(f"Could not check open orders or positions for {symbol}, proceeding with caution: {e}")

        self.logger.info(f"Executing {signal} order for {symbol}, quantity: {quantity}, price: {limit_price}")

        # Set leverage for the symbol before placing the order
        try:
            await self.client.futures_change_leverage(symbol=symbol, leverage=self.leverage)
            self.logger.info(f"Leverage set to {self.leverage}x for {symbol}")
        except Exception as e:
            self.logger.warning(f"Could not set leverage for {symbol}: {e}. This may be normal if leverage is already set.")

        # Place the initial order with stop-loss and take-profit orders together
        order_results = await self.place_initial_order_with_tp_sl(symbol, side, quantity, limit_price)

        if order_results:
            entry_order, stop_loss_order, take_profit_order = order_results
            self.logger.info(f"Successfully executed {signal} order for {symbol} with TP/SL orders")

            # Update last signal to prevent duplicates
            self.last_signals[symbol] = (datetime.now().timestamp(), signal)

            # Send trade notification
            if self.enable_notifications:
                trade_data = {
                    'symbol': symbol,
                    'signal': signal,
                    'entry_price': limit_price,
                    'quantity': quantity,
                    'timestamp': datetime.now().isoformat()
                }
                # Run notification in background to avoid blocking
                import asyncio
                asyncio.create_task(self.send_trade_notification_async(trade_data))
        else:
            self.logger.error(f"Failed to execute {signal} order for {symbol}")

            # Send failure notification
            if self.enable_notifications:
                import asyncio
                asyncio.create_task(self.send_alert_notification_async(
                    'error',
                    f"Failed to execute {signal} order for {symbol}"
                ))

    # OLD FUNCTION - REPLACED BY place_tp_sl_orders
    # async def place_stop_loss_order(self, symbol: str, signal: str, quantity: float, entry_price: float = None):
    #     """
    #     Place a stop-loss order based on the engulfing pattern
    #     For bullish trades: stop-loss exactly 2% below the engulfed candle's low
    #     For bearish trades: stop-loss exactly 2% above the engulfed candle's high
    #
    #     Args:
    #         symbol: Trading pair
    #         signal: Trading signal ('BUY' or 'SELL')
    #         quantity: Quantity to trade
    #         entry_price: Entry price for the trade
    #     """
    #     # Get the last 2 candles to determine the engulfed candle
    #     # klines[-2] is the engulfed candle, klines[-1] is the engulfing candle
    #     klines = await self.pattern_detector.get_klines(symbol, self.timeframe, 3)
    #     if len(klines) < 2:
    #         self.logger.warning(f"Not enough kline data to set stop-loss for {symbol}")
    #         return
    #
    #     # Get the engulfed candle (klines[-2])
    #     engulfed_candle = klines[-2]  # Previous candle (the engulfed one)
    #
    #     # Parse candle data: [open_time, open, high, low, close, volume, ...]
    #     engulfed_open = float(engulfed_candle[1])
    #     engulfed_high = float(engulfed_candle[2])
    #     engulfed_low = float(engulfed_candle[3])
    #     engulfed_close = float(engulfed_candle[4])
    #
    #     # Calculate stop-loss price based on signal and engulfed candle
    #     if signal == 'BUY':  # Bullish engulfing - buy signal
    #         # Stop-loss just below the engulfed candle's low (approximately 1-2% below)
    #         stop_loss_price = engulfed_low * (1 - 0.015)  # 1.5% below the low
    #         stop_price = stop_loss_price  # Same price for trigger
    #     elif signal == 'SELL':  # Bearish engulfing - sell signal
    #         # Stop-loss just above the engulfed candle's high (approximately 1-2% above)
    #         stop_loss_price = engulfed_high * (1 + 0.015)  # 1.5% above the high
    #         stop_price = stop_loss_price  # Same price for trigger
    #     else:
    #         return
    #
    #     # Convert prices to strings with appropriate precision
    #     stop_price_str = f"{stop_loss_price:.8f}"
    #     stop_loss_price_str = f"{stop_loss_price:.8f}"
    #
    #     try:
    #         # Get the symbol's price and quantity precision
    #         price_precision = 8  # Default precision
    #         quantity_precision = 8  # Default quantity precision
    #
    #         try:
    #             symbol_info = await self.client.futures_exchange_info()
    #             symbol_detail = None
    #             for item in symbol_info['symbols']:
    #                 if item['symbol'] == symbol:
    #                     symbol_detail = item
    #                     break
    #
    #             if symbol_detail:
    #                 price_precision = symbol_detail['pricePrecision']
    #                 # Also get quantity precision
    #                 for filter_item in symbol_detail['filters']:
    #                     if filter_item['filterType'] == 'LOT_SIZE':
    #                         quantity_precision = len(filter_item['stepSize'].split('.')[-1]) if '.' in filter_item['stepSize'] else 0
    #                         break
    #
    #                 # Adjust stop price to tick size requirements and format according to the symbol's precision
    #                 adjusted_stop_price = await self.adjust_price_to_tick_size(symbol, stop_loss_price)
    #                 stop_price_str = f"{adjusted_stop_price:.{price_precision}f}"
    #                 stop_loss_price_str = f"{adjusted_stop_price:.{price_precision}f}"
    #             else:
    #                 # Default to 8 decimal places if symbol info not found
    #                 stop_price_str = f"{stop_loss_price:.8f}"
    #                 stop_loss_price_str = f"{stop_loss_price:.8f}"
    #         except Exception as e:
    #             self.logger.warning(f"Could not get symbol precision for {symbol}: {e}")
    #             # Default to 8 decimal places if error occurs
    #             stop_price_str = f"{stop_loss_price:.8f}"
    #             stop_loss_price_str = f"{stop_loss_price:.8f}"
    #
    #         # Format quantity according to symbol's LOT_SIZE requirements
    #         formatted_quantity = f"{quantity:.{quantity_precision}f}".rstrip('0').rstrip('.')
    #
    #         # Place the stop-loss order
    #         if signal == 'BUY':
    #             # For a long position, we place a stop-loss sell order
    #             stop_loss_order = await self.client.futures_create_order(
    #                 symbol=symbol,
    #                 side=SIDE_SELL,
    #                 type='STOP_MARKET',  # Correct futures stop-market order type
    #                 quantity=formatted_quantity,
    #                 stopPrice=stop_price_str,
    #                 # Set position side to BOTH to allow both long/short
    #                 positionSide='BOTH',
    #                 # Set margin mode to ISOLATED
    #                 marginMode='ISOLATED'
    #             )
    #         else:  # SELL signal
    #             # For a short position, we place a stop-loss buy order
    #             stop_loss_order = await self.client.futures_create_order(
    #                 symbol=symbol,
    #                 side=SIDE_BUY,
    #                 type='STOP_MARKET',  # Correct futures stop-market order type
    #                 quantity=formatted_quantity,
    #                 stopPrice=stop_price_str,
    #                 # Set position side to BOTH to allow both long/short
    #                 positionSide='BOTH',
    #                 # Set margin mode to ISOLATED
    #                 marginMode='ISOLATED'
    #             )
    #
    #         self.logger.info(f"Stop-loss order placed for {symbol}: {signal}, Stop: {stop_loss_price_str}, Quantity: {quantity}")
    #
    #         # Place take-profit order at 2.5R
    #         await self.place_take_profit_order(symbol, signal, quantity, entry_price, stop_loss_price)
    #
    #         return stop_loss_order
    #     except Exception as e:
    #         self.logger.error(f"Error placing stop-loss order for {symbol}: {e}")
    #         return {}

    async def place_initial_order_with_tp_sl(self, symbol: str, side: str, quantity: float, limit_price: float = None):
        """
        Place initial order with stop-loss and take-profit orders together as a single bracket order
        For bullish trades: buy limit order + stop-loss market + take-profit market
        For bearish trades: sell limit order + stop-loss market + take-profit market
        
        Args:
            symbol: Trading pair
            side: 'BUY' or 'SELL'
            quantity: Quantity to trade
            limit_price: Entry price for the trade
        """
        # Get the last 2 candles to determine the engulfed candle
        # klines[-2] is the engulfed candle, klines[-1] is the engulfing candle
        klines = await self.pattern_detector.get_klines(symbol, self.timeframe, 3)
        if len(klines) < 2:
            self.logger.warning(f"Not enough kline data to set TP/SL for {symbol}")
            return
        
        # Get the engulfed candle (klines[-2])
        engulfed_candle = klines[-2]  # Previous candle (the engulfed one)
        
        # Parse candle data: [open_time, open, high, low, close, volume, ...]
        engulfed_open = float(engulfed_candle[1])
        engulfed_high = float(engulfed_candle[2])
        engulfed_low = float(engulfed_candle[3])
        engulfed_close = float(engulfed_candle[4])
        
        # Calculate stop-loss price based on signal and engulfed candle
        if side == SIDE_BUY:  # Bullish engulfing - buy signal
            # Stop-loss just below the engulfed candle's low (approximately 1-2% below)
            stop_loss_price = engulfed_low * (1 - 0.015)  # 1.5% below the low
        elif side == SIDE_SELL:  # Bearish engulfing - sell signal
            # Stop-loss just above the engulfed candle's high (approximately 1-2% above)
            stop_loss_price = engulfed_high * (1 + 0.015)  # 1.5% above the high
        else:
            return
        
        # Calculate take-profit price based on 2.5R
        if limit_price is None:
            self.logger.warning(f"Entry price not available for TP/SL calculation for {symbol}")
            return
        
        # Calculate the risk (distance between entry and stop loss)
        risk_distance = abs(limit_price - stop_loss_price)
        
        # Get the symbol's price and quantity precision
        price_precision = 8  # Default precision
        quantity_precision = 8  # Default quantity precision
        
        try:
            symbol_info = await self.client.futures_exchange_info()
            symbol_detail = None
            for item in symbol_info['symbols']:
                if item['symbol'] == symbol:
                    symbol_detail = item
                    break
            
            if symbol_detail:
                price_precision = symbol_detail['pricePrecision']
                # Also get quantity precision
                for filter_item in symbol_detail['filters']:
                    if filter_item['filterType'] == 'LOT_SIZE':
                        quantity_precision = len(filter_item['stepSize'].split('.')[-1]) if '.' in filter_item['stepSize'] else 0
                        break
        except Exception as e:
            self.logger.warning(f"Could not get symbol precision for {symbol}: {e}")
            # Defaults remain as set above
        
        # Format quantity according to symbol's LOT_SIZE requirements
        formatted_quantity = f"{quantity:.{quantity_precision}f}".rstrip('0').rstrip('.')

        # Adjust prices to tick size requirements
        stop_loss_price = await self.adjust_price_to_tick_size(symbol, stop_loss_price)
        stop_price_str = f"{stop_loss_price:.{price_precision}f}"
        
        # Calculate take-profit price
        if side == SIDE_BUY:  # Bullish trade
            # Take profit at exactly 2.5 times the risk distance above entry
            take_profit_price = limit_price + (2.5 * risk_distance)
            take_profit_price = await self.adjust_price_to_tick_size(symbol, take_profit_price)
            take_profit_price_str = f"{take_profit_price:.{price_precision}f}"
        elif side == SIDE_SELL:  # Bearish trade
            # Take profit at exactly 2.5 times the risk distance below entry
            take_profit_price = limit_price - (2.5 * risk_distance)
            take_profit_price = await self.adjust_price_to_tick_size(symbol, take_profit_price)
            take_profit_price_str = f"{take_profit_price:.{price_precision}f}"
        
        # Place the entry order with TP/SL in a single transaction using OCO (One-Cancels-Other) approach
        try:
            # Adjust the limit price to tick size requirements before placing the order
            adjusted_limit_price = await self.adjust_price_to_tick_size(symbol, limit_price)
            
            # Place the main entry order
            entry_order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_LIMIT,
                quantity=formatted_quantity,
                price=f"{adjusted_limit_price:.{price_precision}f}",
                timeInForce=TIME_IN_FORCE_GTC,
                # Set position side to BOTH to allow both long/short
                positionSide='BOTH',
                # Set margin mode to ISOLATED
                marginMode='ISOLATED'
            )
            
            # If entry order succeeds, immediately place stop-loss and take-profit orders as contingent orders
            if entry_order and 'orderId' in entry_order:
                # Place stop-loss order as a conditional order
                if side == SIDE_BUY:  # For a long position, stop-loss is a sell order
                    stop_loss_order = await self.client.futures_create_order(
                        symbol=symbol,
                        side=SIDE_SELL,
                        type='STOP_MARKET',  # Correct futures stop-market order type
                        quantity=formatted_quantity,
                        stopPrice=stop_price_str,
                        # Set position side to BOTH to allow both long/short
                        positionSide='BOTH',
                        # Set margin mode to ISOLATED
                        marginMode='ISOLATED',
                        # Make sure this order is reduce-only to close the position
                        reduceOnly=True
                    )
                else:  # For a short position, stop-loss is a buy order
                    stop_loss_order = await self.client.futures_create_order(
                        symbol=symbol,
                        side=SIDE_BUY,
                        type='STOP_MARKET',  # Correct futures stop-market order type
                        quantity=formatted_quantity,
                        stopPrice=stop_price_str,
                        # Set position side to BOTH to allow both long/short
                        positionSide='BOTH',
                        # Set margin mode to ISOLATED
                        marginMode='ISOLATED',
                        # Make sure this order is reduce-only to close the position
                        reduceOnly=True
                    )
                
                # Place take-profit order as a conditional order
                if side == SIDE_BUY:  # For a long position, take-profit is a sell order
                    take_profit_order = await self.client.futures_create_order(
                        symbol=symbol,
                        side=SIDE_SELL,
                        type='TAKE_PROFIT_MARKET',  # Correct futures take-profit market order type
                        quantity=formatted_quantity,
                        stopPrice=take_profit_price_str,
                        # Set position side to BOTH to allow both long/short
                        positionSide='BOTH',
                        # Set margin mode to ISOLATED
                        marginMode='ISOLATED',
                        # Make sure this order is reduce-only to close the position
                        reduceOnly=True
                    )
                else:  # For a short position, take-profit is a buy order
                    take_profit_order = await self.client.futures_create_order(
                        symbol=symbol,
                        side=SIDE_BUY,
                        type='TAKE_PROFIT_MARKET',  # Correct futures take-profit market order type
                        quantity=formatted_quantity,
                        stopPrice=take_profit_price_str,
                        # Set position side to BOTH to allow both long/short
                        positionSide='BOTH',
                        # Set margin mode to ISOLATED
                        marginMode='ISOLATED',
                        # Make sure this order is reduce-only to close the position
                        reduceOnly=True
                    )
                
                self.logger.info(f"Entry order placed for {symbol}: {side}, Price: {limit_price}, Quantity: {quantity}")
                self.logger.info(f"Stop-loss order placed for {symbol}: {side}, Stop: {stop_price_str}, Quantity: {quantity}, ReduceOnly: True")
                self.logger.info(f"Take-profit order placed for {symbol}: {side}, Target: {take_profit_price_str}, Quantity: {quantity}, ReduceOnly: True")
                
                return entry_order, stop_loss_order, take_profit_order
            else:
                self.logger.error(f"Entry order failed for {symbol}")
                return None, None, None
            
        except Exception as e:
            self.logger.error(f"Error placing entry order with TP/SL for {symbol}: {e}")
            return None, None, None

    async def run_strategy(self, symbol: str):
        """Run a single strategy iteration for a symbol"""
        try:
            # Console output for visibility and log for file output
            strategy_start_msg = f"[STRATEGY] {datetime.now().strftime('%H:%M:%S')} - Running strategy iteration for {symbol}"
            print(strategy_start_msg)
            self.logger.info(f"RUNNING STRATEGY: {strategy_start_msg}")

            signal, limit_price = await self.pattern_detector.get_trading_signal_with_price(symbol, self.timeframe)

            # Console output for visibility and log for file output
            strategy_result_msg = f"[STRATEGY] {datetime.now().strftime('%H:%M:%S')} - Signal for {symbol}: {signal}, Limit Price: {limit_price}"
            print(strategy_result_msg)
            self.logger.info(f"STRATEGY RESULT: {strategy_result_msg}")

            await self.execute_trade(symbol, signal, limit_price)
        except Exception as e:
            # Console output for visibility and log for file output
            strategy_error_msg = f"[STRATEGY ERROR] {datetime.now().strftime('%H:%M:%S')} - Error running strategy for {symbol}: {e}"
            print(strategy_error_msg)
            self.logger.error(f"STRATEGY ERROR: {strategy_error_msg}")

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

                # Print performance report every 10 iterations
                if hasattr(self, '_iteration_count'):
                    self._iteration_count += 1
                else:
                    self._iteration_count = 1

                if self._iteration_count % 10 == 0:  # Print report every 10 cycles
                    self.performance_tracker.print_performance_report()

                # Sleep before next iteration
                await asyncio.sleep(interval)

        except KeyboardInterrupt:
            self.logger.info("Stopping trading bot...")
            self.performance_tracker.print_performance_report()  # Print final report
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the trading bot"""
        self.is_running = False
        await self.close_client()
        self.db_manager.close()
        self.logger.info("Trading bot stopped")

    async def send_trade_notification_async(self, trade_data: Dict):
        """Async wrapper for sending trade notifications"""
        try:
            self.notification_system.send_trade_notification(self.recipient_emails, trade_data)
        except Exception as e:
            self.logger.error(f"Error sending trade notification: {e}")

    async def send_alert_notification_async(self, alert_type: str, message: str):
        """Async wrapper for sending alert notifications"""
        try:
            self.notification_system.send_alert_notification(self.recipient_emails, alert_type, message)
        except Exception as e:
            self.logger.error(f"Error sending alert notification: {e}")

    def load_notification_settings(self, config: Dict):
        """Load notification settings from configuration"""
        notifications_config = config.get('notifications', {})
        self.recipient_emails = notifications_config.get('recipient_emails', [])
        self.enable_notifications = notifications_config.get('enable_notifications', False)

        # Configure SMTP if provided
        smtp_config = notifications_config.get('smtp', {})
        if smtp_config:
            self.notification_system.configure_smtp(
                sender_email=smtp_config.get('sender_email', ''),
                sender_password=smtp_config.get('sender_password', ''),
                smtp_server=smtp_config.get('server', 'smtp.gmail.com'),
                smtp_port=smtp_config.get('port', 587)
            )


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
                "max_position_size_margin": 0.03,  # 3% per trade as specified (before leverage)
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
    bot.risk_manager.risk_settings.update(config.get('risk_management', {}))

    # Load notification settings
    bot.load_notification_settings(config)

    # Store leverage settings
    bot.leverage = config.get('leverage', 4)  # Default to 4x leverage if not specified
    bot.use_leverage = config.get('use_leverage', True)  # Default to using leverage if not specified

    # Run the bot with specified symbols
    symbols = config.get('symbols', ['BTCUSDT'])
    await bot.run(symbols, interval=60)  # Run every minute


if __name__ == "__main__":
    # For testing purposes, we'll run the main function
    # asyncio.run(main())
    pass