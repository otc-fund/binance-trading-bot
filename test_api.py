from binance import AsyncClient
import asyncio
import json

async def test_api():
    # Load API credentials from config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    api_key = config['api_key']
    api_secret = config['api_secret']
    
    client = await AsyncClient.create(
        api_key=api_key,
        api_secret=api_secret,
        testnet=True
    )
    
    # Test basic account info
    try:
        account_info = await client.get_account()
        print("Account info retrieved:", account_info)
    except Exception as e:
        print("Error retrieving account info:", e)
    
    # Test getting account balance specifically
    try:
        account_status = await client.get_account_status()
        print("Account status:", account_status)
    except Exception as e:
        print("Error retrieving account status:", e)
    
    # Test getting balances
    try:
        balances = await client.get_asset_balance(asset='USDT')
        print("USDT Balance:", balances)
    except Exception as e:
        print("Error retrieving USDT balance:", e)
    
    # Test getting ticker price
    try:
        ticker = await client.get_symbol_ticker(symbol='BTCUSDT')
        print("BTCUSDT Price:", ticker)
    except Exception as e:
        print("Error retrieving BTCUSDT price:", e)
    
    # Test getting klines (candlestick data)
    try:
        klines = await client.get_klines(symbol='BTCUSDT', interval='5m', limit=5)
        print("BTCUSDT 5m Klines (first 2):", klines[:2])
    except Exception as e:
        print("Error retrieving klines:", e)
    
    await client.close_connection()

# Run the test
if __name__ == "__main__":
    asyncio.run(test_api())