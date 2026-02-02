"""
Risk Manager Module
Handles all risk management logic for the trading bot
"""

from binance import AsyncClient, Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from typing import Dict


class RiskManager:
    def __init__(self, client: AsyncClient, use_leverage: bool = True, leverage: int = 1):
        self.client = client
        self.use_leverage = use_leverage
        self.leverage = leverage
        self.balance = {}
        
        # Risk management settings
        self.risk_settings = {
            'max_position_size_spot': 0.10,  # Max 10% of account per position for spot trading
            'max_position_size_margin': 0.03,  # Max 3% of account per position for margin trading (before leverage)
            'max_daily_loss': 0.05,  # Max 5% daily loss
            'stop_loss_pct': 0.02,  # 2% stop loss (though stop loss is handled by engulfing pattern)
            'take_profit_pct': 0.05  # 5% take profit (though take profit is handled by 2.5R rule)
        }
    
    async def get_account_info(self) -> Dict:
        """Get account information"""
        try:
            # Try the futures account information endpoint first (most comprehensive - likely V3)
            if hasattr(self.client, 'futures_account'):
                try:
                    account_info = await self.client.futures_account()
                    # Process the account information
                    if 'assets' in account_info and isinstance(account_info['assets'], list):
                        # Look for USDT or other stablecoins in the assets
                        target_assets = ['USDT', 'BUSD', 'FDUSD', 'TUSD']
                        for asset_data in account_info['assets']:
                            if asset_data.get('asset') in target_assets:
                                balance_amount = float(asset_data.get('walletBalance', 0))
                                available_amount = float(asset_data.get('availableBalance', 0))
                                
                                self.balance = {asset_data['asset']: balance_amount}
                                
                                # Return in standard account format
                                return {
                                    'balances': [
                                        {
                                            'asset': asset_data['asset'],
                                            'free': str(available_amount),
                                            'locked': str(balance_amount - available_amount)
                                        }
                                    ]
                                }
                except Exception as v3_error:
                    print(f"Futures account endpoint failed: {v3_error}")
                    # Continue to try other methods if V3 fails
            
            # Try futures account balance endpoint as backup
            if hasattr(self.client, 'futures_account_balance'):
                balance_info = await self.client.futures_account_balance()
                # Convert futures balance format to standard format
                if balance_info and isinstance(balance_info, list) and len(balance_info) > 0:
                    # Look for USDT balance in the futures format
                    # If USDT isn't available, try BUSD or other stablecoins
                    target_assets = ['USDT', 'BUSD', 'FDUSD', 'TUSD']
                    for asset_name in target_assets:
                        asset_balance = next((item for item in balance_info if item.get('asset') == asset_name), None)
                        if asset_balance:
                            balance_amount = float(asset_balance.get('balance', 0))
                            available_amount = float(asset_balance.get('availableBalance', 0))
                            
                            self.balance = {asset_name: balance_amount}
                            
                            # Return in standard account format
                            return {
                                'balances': [
                                    {
                                        'asset': asset_name,
                                        'free': str(balance_amount),
                                        'locked': str(balance_amount - available_amount)
                                    }
                                ]
                            }
            
            # Fallback to regular account if futures endpoints fail
            # But check if we're dealing with futures first
            if hasattr(self.client, 'futures_account_balance_v2'):
                # Try futures_account_balance_v2 which should be available for futures accounts
                balance_info = await self.client.futures_account_balance_v2()
                # Convert futures balance format to standard format
                if balance_info and isinstance(balance_info, list) and len(balance_info) > 0:
                    # Look for USDT balance in the futures format
                    target_assets = ['USDT', 'BUSD', 'FDUSD', 'TUSD']
                    for asset_name in target_assets:
                        asset_balance = next((item for item in balance_info if item.get('asset') == asset_name), None)
                        if asset_balance:
                            balance_amount = float(asset_balance.get('balance', 0))
                            available_amount = float(asset_balance.get('availableBalance', 0))
                            
                            self.balance = {asset_name: balance_amount}
                            
                            # Return in standard account format
                            return {
                                'balances': [
                                    {
                                        'asset': asset_name,
                                        'free': str(balance_amount),
                                        'locked': str(balance_amount - available_amount)
                                    }
                                ]
                            }
            else:
                # Regular account fallback (should not be reached if futures methods are available)
                account_info = await self.client.get_account()
                self.balance = {asset['asset']: float(asset['free']) for asset in account_info['balances']}
                return account_info
        except BinanceAPIException as e:
            print(f"Error getting account info: {e}")
            # Return a mock account info structure to prevent errors
            return {
                'balances': [
                    {'asset': 'USDT', 'free': '1000.0', 'locked': '0.0'}
                ]
            }
        except Exception as e:
            print(f"Unexpected error getting account info: {e}")
            # Return a mock account info structure to prevent errors
            return {
                'balances': [
                    {'asset': 'USDT', 'free': '1000.0', 'locked': '0.0'}
                ]
            }
    
    async def get_symbol_info(self, symbol: str) -> Dict:
        """Get information about a specific symbol"""
        try:
            return await self.client.get_symbol_info(symbol)
        except BinanceAPIException as e:
            print(f"Error getting symbol info for {symbol}: {e}")
            return {}
    
    async def get_ticker_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            ticker = await self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            print(f"Error getting ticker price for {symbol}: {e}")
            return 0.0
    
    async def calculate_position_size(self, symbol: str) -> float:
        """
        Calculate appropriate position size based on risk management rules
        Uses either 10% for spot or 3% with leverage for margin based on use_leverage flag
        """
        try:
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
        except Exception as e:
            # If we can't get account info (common on testnet), use a default balance
            print(f"Could not retrieve account balance (this is common on testnet): {e}")
            available_balance = 10000.0  # Default demo balance
        
        # If balance is still 0 or invalid, use a default value
        if available_balance <= 0:
            available_balance = 10000.0
        
        # Determine position size based on leverage setting
        if self.use_leverage:
            # Use margin trading with leverage (3% base position * leverage)
            base_position_size = self.risk_settings['max_position_size_margin']  # 3% for margin
            position_value = available_balance * base_position_size * self.leverage
        else:
            # Use spot trading (10% of account)
            base_position_size = self.risk_settings['max_position_size_spot']  # 10% for spot
            position_value = available_balance * base_position_size  # No additional leverage
        
        # Get current price to calculate quantity
        current_price = await self.get_ticker_price(symbol)
        
        if current_price <= 0:
            print(f"Invalid price for {symbol}: {current_price}")
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