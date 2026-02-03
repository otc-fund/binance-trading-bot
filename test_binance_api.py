"""
Binance API Test Script
Tests all Binance API calls used by the trading bot
"""

import asyncio
import os
from binance import AsyncClient

# Note: Set your API credentials as environment variables or update these values
# os.environ['BINANCE_API_KEY'] = 'your_api_key_here'
# os.environ['BINANCE_API_SECRET'] = 'your_api_secret_here'

async def test_binance_api():
    """Test all Binance API calls"""
    
    # Get API credentials from environment or use placeholders
    api_key = os.getenv('BINANCE_API_KEY', 'YOUR_API_KEY_HERE')
    api_secret = os.getenv('BINANCE_API_SECRET', 'YOUR_API_SECRET_HERE')
    
    # For testnet
    testnet = True
    
    print("Initializing Binance client...")
    try:
        if testnet:
            client = await AsyncClient.create(
                api_key=api_key,
                api_secret=api_secret,
                testnet=True
            )
        else:
            client = await AsyncClient.create(
                api_key=api_key,
                api_secret=api_secret
            )
        print("+ Client initialized successfully")
    except Exception as e:
        print(f"- Client initialization failed: {e}")
        return
    
    # Test futures account balance methods
    print("\n--- Testing Futures Account Balance Methods ---")
    
    try:
        # Test futures_account_balance_v2
        balance_v2 = await client.futures_account_balance_v2()
        print(f"+ futures_account_balance_v2() - Success, got {len(balance_v2)} assets")
        if balance_v2:
            print(f"  Sample: {balance_v2[0]}")
    except Exception as e:
        print(f"- futures_account_balance_v2() failed: {e}")
    
    try:
        # Test futures_account_balance
        balance = await client.futures_account_balance()
        print(f"+ futures_account_balance() - Success, got {len(balance)} assets")
        if balance:
            print(f"  Sample: {balance[0]}")
    except Exception as e:
        print(f"- futures_account_balance() failed: {e}")
    
    try:
        # Test futures_account
        account = await client.futures_account()
        print(f"+ futures_account() - Success")
        if 'assets' in account:
            print(f"  Assets: {len(account['assets'])} assets")
        if 'positions' in account:
            print(f"  Positions: {len(account['positions'])} positions")
    except Exception as e:
        print(f"- futures_account() failed: {e}")
    
    # Test kline/candlestick data
    print("\n--- Testing Kline Data Methods ---")
    
    symbols_to_test = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']
    intervals_to_test = ['1m', '5m', '15m', '1h']
    
    for symbol in symbols_to_test[:2]:  # Test first 2 symbols to avoid too many calls
        for interval in intervals_to_test[:2]:  # Test first 2 intervals
            try:
                klines = await client.get_klines(
                    symbol=symbol,
                    interval=f'1{interval}',  # Format like Client.KLINE_INTERVAL_1MINUTE
                    limit=5
                )
                print(f"+ get_klines({symbol}, 1{interval}) - Success, got {len(klines)} klines")
            except Exception as e:
                print(f"- get_klines({symbol}, 1{interval}) failed: {e}")
    
    # Test ticker price
    print("\n--- Testing Ticker Price Methods ---")
    
    for symbol in symbols_to_test[:2]:
        try:
            ticker = await client.get_symbol_ticker(symbol=symbol)
            print(f"+ get_symbol_ticker({symbol}) - Success, price: {ticker.get('price', 'N/A')}")
        except Exception as e:
            print(f"- get_symbol_ticker({symbol}) failed: {e}")
    
    # Test symbol info
    print("\n--- Testing Symbol Information ---")
    
    for symbol in symbols_to_test[:2]:
        try:
            symbol_info = await client.get_symbol_info(symbol=symbol)
            print(f"+ get_symbol_info({symbol}) - Success")
            if symbol_info and 'filters' in symbol_info:
                lot_size_filter = next((f for f in symbol_info['filters'] if f.get('filterType') == 'LOT_SIZE'), None)
                if lot_size_filter:
                    print(f"  Lot size: min {lot_size_filter.get('minQty')} step {lot_size_filter.get('stepSize')}")
        except Exception as e:
            print(f"- get_symbol_info({symbol}) failed: {e}")
    
    # Test order methods (without actually placing orders)
    print("\n--- Testing Order Methods ---")
    
    try:
        # Test getting open orders (should return empty list if no orders)
        orders = await client.futures_get_open_orders(symbol='BTCUSDT')
        print(f"+ futures_get_open_orders(BTCUSDT) - Success, got {len(orders)} open orders")
    except Exception as e:
        print(f"- futures_get_open_orders(BTCUSDT) failed: {e}")
    
    try:
        # Test getting account positions
        positions = await client.futures_position_information()
        print(f"+ futures_position_information() - Success, got {len(positions)} positions")
        if positions:
            for pos in positions[:2]:  # Show first 2 positions
                print(f"  Position: {pos.get('symbol', 'N/A')} | P&L: {pos.get('unRealizedProfit', 'N/A')}")
    except Exception as e:
        print(f"- futures_position_information() failed: {e}")
    
    # Close client
    await client.close_connection()
    print("\n+ All tests completed!")

if __name__ == "__main__":
    print("Starting Binance API Tests...")
    asyncio.run(test_binance_api())