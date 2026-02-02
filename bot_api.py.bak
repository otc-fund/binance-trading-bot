"""
API Server for Binance Trading Bot
Provides API endpoints for the web UI to communicate with the running bot
"""

from flask import Flask, jsonify, request
import threading
import time
from datetime import datetime
import json
import os
import sys

# Add the main project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_bot import BinanceTradingBot
from modules.database import DatabaseManager
from modules.performance_tracker import PerformanceTracker
from config_manager import SecureConfigManager


import logging
import sys

class BotAPI:
    def __init__(self):
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('bot_api.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.bot = None
        self.db_manager = DatabaseManager()
        self.performance_tracker = PerformanceTracker(self.db_manager)
        self.is_running = False
        self.running_since = None
        
        # Create Flask app
        self.app = Flask(__name__)
        self.setup_routes()
    
    def setup_routes(self):
        """Setup API routes"""
        @self.app.route('/api/status')
        def get_bot_status():
            return jsonify({
                'status': 'running' if self.is_running else 'stopped',
                'running_since': self.running_since.isoformat() if self.running_since else None,
                'total_trades': self.performance_tracker.performance_metrics['total_trades'],
                'current_symbols': getattr(self.bot, 'symbols', []) if self.bot else [],
                'current_balance': self.get_current_balance(),
                'pnl_24h': 0.0  # Placeholder
            })
        
        @self.app.route('/api/performance')
        def get_performance():
            self.performance_tracker.calculate_performance_metrics()
            return jsonify(self.performance_tracker.performance_metrics)
        
        @self.app.route('/api/trades')
        def get_trades():
            limit = request.args.get('limit', 50, type=int)
            trades = self.db_manager.get_trade_history(limit)
            return jsonify(trades)
        
        @self.app.route('/api/config', methods=['GET', 'POST'])
        def get_set_config():
            config_manager = SecureConfigManager()
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            
            if request.method == 'POST':
                # Update config
                new_config = request.json
                # Save as temporary file, then encrypt
                with open(config_path, 'w') as f:
                    json.dump(new_config, f, indent=2)
                
                # Re-encrypt the config file
                try:
                    config_manager.encrypt_config()
                except Exception as e:
                    # If encryption fails, save as unencrypted but warn
                    print(f"Warning: Could not encrypt config: {e}")
                
                return jsonify({'status': 'success'})
            
            # Get config
            try:
                config = config_manager.load_config()
            except Exception as e:
                # If loading encrypted config fails, try regular file
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                else:
                    # Default config
                    config = {
                        "api_key": "",
                        "api_secret": "",
                        "testnet": True,
                        "symbols": ["BTCUSDT", "ETHUSDT"],
                        "leverage": 4,
                        "use_leverage": True,
                        "timeframe": "15m",
                        "risk_management": {
                            "max_position_size_margin": 0.03,
                            "max_daily_loss": 0.05,
                            "stop_loss_pct": 0.02,
                            "take_profit_pct": 0.05
                        },
                        "notifications": {
                            "enable_notifications": False,
                            "recipient_emails": [],
                            "smtp": {
                                "sender_email": "",
                                "sender_password": "",  # Use app password for Gmail
                                "server": "smtp.gmail.com",
                                "port": 587
                            }
                        }
                    }
            
            return jsonify(config)
        
        @self.app.route('/api/control', methods=['POST'])
        def control_bot():
            action = request.json.get('action')
            
            if action == 'start':
                return self.start_bot()
            elif action == 'stop':
                return self.stop_bot()
            elif action == 'pause':
                return self.pause_bot()
            else:
                return jsonify({'error': 'Invalid action'}), 400
        
        @self.app.route('/api/balance')
        def get_balance():
            return jsonify({'balance': self.get_current_balance()})
        
        @self.app.route('/api/logs')
        def get_logs():
            """Return recent log entries from the trading bot log file"""
            try:
                import os
                log_file = 'trading_bot.log'
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    # Return the last 50 lines
                    recent_lines = lines[-50:] if len(lines) > 50 else lines
                    log_content = ''.join(recent_lines)
                    
                    return jsonify({
                        'logs': log_content,
                        'count': len(recent_lines),
                        'total_lines': len(lines)
                    })
                else:
                    return jsonify({
                        'logs': 'Log file not found',
                        'count': 0,
                        'total_lines': 0
                    })
            except Exception as e:
                return jsonify({
                    'logs': f'Error reading logs: {str(e)}',
                    'count': 0,
                    'total_lines': 0
                })
    
    def get_current_balance(self):
        """Get the current account balance"""
        if self.bot and hasattr(self.bot, 'balance'):
            if 'USDT' in self.bot.balance and self.bot.balance['USDT'] is not None:
                return self.bot.balance['USDT']
            # If balance is not set properly, return the default hardcoded value
            elif self.bot.balance and len(self.bot.balance) > 0:
                # Try to get any available balance value
                for asset, amount in self.bot.balance.items():
                    if isinstance(amount, (int, float)):
                        return amount
        # Return the hardcoded initial balance for testnet
        return 5000.0
    
    def start_bot(self):
        """Start the trading bot"""
        if not self.is_running:
            # Load config
            config = self.load_config()
            
            # Create and initialize bot
            self.bot = BinanceTradingBot(
                api_key=config['api_key'],
                api_secret=config['api_secret'],
                testnet=config.get('testnet', False),
                timeframe=self.get_binance_timeframe(config.get('timeframe', '15m'))
            )
            
            # Update risk management settings
            self.bot.risk_manager.risk_settings.update(config.get('risk_management', {}))
            
            # Load notification settings
            self.bot.load_notification_settings(config)
            
            # Store leverage settings
            self.bot.leverage = config.get('leverage', 1)
            self.bot.use_leverage = config.get('use_leverage', True)
            
            # Initialize client
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Initialize database connection for this thread
            self.db_manager.connect()
            
            # Start bot in a separate thread
            def run_bot():
                try:
                    loop.run_until_complete(self.bot.initialize_client())
                    self.is_running = True
                    self.running_since = datetime.now()
                    symbols = config.get('symbols', ['BTCUSDT'])
                    loop.run_until_complete(self.bot.run(symbols, interval=60))
                except Exception as e:
                    self.logger.error(f"Error in bot thread: {e}")
                    self.is_running = False
                    self.running_since = None
                    # Close any resources that were opened
                    if hasattr(self.bot, 'close_client'):
                        try:
                            loop.run_until_complete(self.bot.close_client())
                        except:
                            pass
                    # Close database connection
                    self.db_manager.close()
            
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            
            return jsonify({'status': 'started'})
        else:
            return jsonify({'status': 'already running'})
    
    def stop_bot(self):
        """Stop the trading bot"""
        if self.is_running and self.bot:
            self.bot.is_running = False
            self.is_running = False
            # Close database connection
            self.db_manager.close()
            return jsonify({'status': 'stopped'})
        else:
            return jsonify({'status': 'already stopped'})
    
    def pause_bot(self):
        """Pause the trading bot"""
        # For now, we'll just return a placeholder response
        # In a full implementation, you'd have a pause mechanism
        return jsonify({'status': 'paused'})
    
    def load_config(self):
        """Load configuration from file (with encryption support)"""
        config_manager = SecureConfigManager()
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        
        try:
            # Try to load using secure config manager (handles both encrypted and unencrypted)
            return config_manager.load_config()
        except Exception as e:
            # If secure loading fails, try regular file loading
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
            else:
                return {
                    "api_key": "",
                    "api_secret": "",
                    "testnet": True,
                    "symbols": ["BTCUSDT", "ETHUSDT"],
                    "leverage": 4,
                    "use_leverage": True,
                    "timeframe": "15m",
                    "risk_management": {
                        "max_position_size_margin": 0.03,
                        "max_daily_loss": 0.05,
                        "stop_loss_pct": 0.02,
                        "take_profit_pct": 0.05
                    },
                    "notifications": {
                        "enable_notifications": False,
                        "recipient_emails": [],
                        "smtp": {
                            "sender_email": "",
                            "sender_password": "",  # Use app password for Gmail
                            "server": "smtp.gmail.com",
                            "port": 587
                        }
                    }
                }
    
    def get_binance_timeframe(self, timeframe_str):
        """Map string timeframe to Binance interval constant"""
        from binance import Client
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
        return timeframe_map.get(timeframe_str, Client.KLINE_INTERVAL_15MINUTE)
    
    def run(self, host='0.0.0.0', port=5001):
        """Run the API server"""
        print(f"Starting Bot API server on {host}:{port}")
        self.app.run(debug=False, host=host, port=port, threaded=True)


if __name__ == '__main__':
    bot_api = BotAPI()
    bot_api.run()