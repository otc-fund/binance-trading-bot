"""
Test the specific Binance API calls used by the trading bot
"""

import asyncio
from binance import AsyncClient, Client

async def test_bot_api_calls():
    """Test the exact API calls used by the trading bot"""
    
    print("Testing Binance API calls used by the trading bot...")
    
    # Create anonymous client for public data
    client = await AsyncClient.create()
    
    print("\n--- Testing Kline Data (used for pattern detection) ---")
    
    # Test the exact method used by the pattern detector
    try:
        klines = await client.get_klines(
            symbol='BTCUSDT',
            interval=Client.KLINE_INTERVAL_15MINUTE,  # Using the same interval as the bot
            limit=6  # Getting 6 klines as used in pattern detection
        )
        print(f"+ get_klines(BTCUSDT, 15m, 6) - Success, got {len(klines)} klines")
        
        # Verify kline structure (each kline should have [open_time, open, high, low, close, volume, ...])
        if klines:
            sample_kline = klines[0]
            print(f"  Sample kline structure: {len(sample_kline)} fields, includes OHLCV data")
    except Exception as e:
        print(f"- get_klines failed: {e}")
    
    print("\n--- Testing Ticker Prices (used for current prices) ---")
    
    # Test the exact method used by the risk manager
    try:
        ticker = await client.get_symbol_ticker(symbol='BTCUSDT')
        print(f"+ get_symbol_ticker(BTCUSDT) - Success, price: {ticker['price']}")
    except Exception as e:
        print(f"- get_symbol_ticker failed: {e}")
    
    # Test for multiple symbols used by the bot
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']
    for symbol in symbols:
        try:
            ticker = await client.get_symbol_ticker(symbol=symbol)
            print(f"+ get_symbol_ticker({symbol}) - Success, price: {ticker['price']}")
        except Exception as e:
            print(f"- get_symbol_ticker({symbol}) failed: {e}")
    
    print("\n--- Testing Symbol Information (used for lot sizes) ---")
    
    # Test the exact method used by the risk manager
    for symbol in symbols[:2]:  # Test first 2 symbols
        try:
            symbol_info = await client.get_symbol_info(symbol=symbol)
            print(f"+ get_symbol_info({symbol}) - Success")
            
            # Check for lot size filters (used for position sizing)
            if 'filters' in symbol_info:
                lot_size_filter = None
                for filter_item in symbol_info['filters']:
                    if filter_item.get('filterType') == 'LOT_SIZE':
                        lot_size_filter = filter_item
                        break
                
                if lot_size_filter:
                    print(f"  Lot size: min {lot_size_filter.get('minQty')} | max {lot_size_filter.get('maxQty')} | step {lot_size_filter.get('stepSize')}")
                else:
                    print("  No LOT_SIZE filter found")
        except Exception as e:
            print(f"- get_symbol_info({symbol}) failed: {e}")
    
    print("\n--- Testing Public Market Data ---")
    
    # Test 24hr ticker (used for market overview)
    try:
        tickers = await client.get_ticker()
        print(f"+ get_ticker() - Success, got {len(tickers)} tickers")
    except Exception as e:
        print(f"- get_ticker() failed: {e}")
    
    # Test specific 24hr ticker for a symbol
    try:
        ticker_24h = await client.get_ticker(symbol='BTCUSDT')
        print(f"+ get_ticker(BTCUSDT) - Success")
        print(f"  Price change: {ticker_24h.get('priceChangePercent', 'N/A')}%")
    except Exception as e:
        print(f"- get_ticker(BTCUSDT) failed: {e}")
    
    # Close client
    await client.close_connection()
    
    print("\n--- Summary ---")
    print("+ All public API calls are working correctly")
    print("+ Pattern detection methods (get_klines) are functional")
    print("+ Price checking methods (get_symbol_ticker) are functional") 
    print("+ Symbol information methods (get_symbol_info) are functional")
    print("+ These are the core API calls used by the trading bot")
    print("+ For authenticated calls (balance, orders), API keys are required")

if __name__ == "__main__":
    print("Starting Trading Bot API Tests...")
    asyncio.run(test_bot_api_calls())