"""
Simple Binance API Test Script
Tests basic connectivity to Binance API without requiring API keys
"""

import asyncio
from binance import AsyncClient

async def test_binance_api():
    """Test basic Binance API connectivity"""
    
    print("Testing Binance API connectivity...")
    
    # Test without API keys first to check general connectivity
    try:
        # Create client without authentication (limited functionality)
        client = await AsyncClient.create()
        print("+ Anonymous client created successfully")
        
        # Test public endpoints that don't require authentication
        print("\n--- Testing Public Endpoints ---")
        
        try:
            # Test ping endpoint
            result = await client.ping()
            print("+ ping() - Success")
        except Exception as e:
            print(f"- ping() failed: {e}")
        
        try:
            # Test time endpoint
            time_result = await client.get_server_time()
            print(f"+ get_server_time() - Success, server time: {time_result['serverTime']}")
        except Exception as e:
            print(f"- get_server_time() failed: {e}")
        
        try:
            # Test exchange info
            exchange_info = await client.get_exchange_info()
            print(f"+ get_exchange_info() - Success, {len(exchange_info['symbols'])} symbols available")
        except Exception as e:
            print(f"- get_exchange_info() failed: {e}")
        
        try:
            # Test ticker price for a common pair
            ticker = await client.get_symbol_ticker(symbol='BTCUSDT')
            print(f"+ get_symbol_ticker(BTCUSDT) - Success, price: {ticker['price']}")
        except Exception as e:
            print(f"- get_symbol_ticker(BTCUSDT) failed: {e}")
        
        try:
            # Test klines for a common pair
            klines = await client.get_klines(symbol='BTCUSDT', interval='1m', limit=5)
            print(f"+ get_klines(BTCUSDT, 1m, 5) - Success, got {len(klines)} klines")
        except Exception as e:
            print(f"- get_klines(BTCUSDT, 1m, 5) failed: {e}")
        
        # Close anonymous client
        await client.close_connection()
        
    except Exception as e:
        print(f"- Failed to create anonymous client: {e}")
    
    print("\n--- Testing Testnet Connectivity ---")
    
    # Test testnet connection (will fail without proper credentials but should connect to the right endpoint)
    try:
        test_client = await AsyncClient.create(testnet=True)
        print("- Testnet client created (credentials needed for actual API calls)")
        await test_client.close_connection()
    except Exception as e:
        print(f"? Testnet client creation: {e} (expected without credentials)")
    
    print("\n+ Basic API connectivity test completed!")

if __name__ == "__main__":
    print("Starting Binance API Connectivity Test...")
    asyncio.run(test_binance_api())