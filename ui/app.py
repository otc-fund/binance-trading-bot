"""
Flask Web Interface for Binance Trading Bot
Provides a simple UI to monitor and control the trading bot
"""

from flask import Flask, render_template, jsonify, request
import os
import sys
import json
from datetime import datetime

# Add the main project directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.database import DatabaseManager
from modules.performance_tracker import PerformanceTracker

app = Flask(__name__)

# Initialize database manager
db_manager = DatabaseManager()
db_manager.connect()

# Initialize performance tracker
perf_tracker = PerformanceTracker(db_manager)


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/api/status')
def get_bot_status():
    """Get current bot status"""
    # For now, return mock status - in a real implementation this would connect to the running bot
    return jsonify({
        'status': 'running',  # or 'stopped', 'paused'
        'running_since': '2024-01-01 12:00:00',
        'current_symbols': ['BTCUSDT', 'ETHUSDT'],
        'total_trades': perf_tracker.performance_metrics['total_trades'],
        'current_balance': 10000.0,  # This would come from the bot
        'pnl_24h': 150.25  # This would come from the bot
    })


@app.route('/api/performance')
def get_performance():
    """Get performance metrics"""
    perf_tracker.calculate_performance_metrics()
    return jsonify(perf_tracker.performance_metrics)


@app.route('/api/trades')
def get_trades():
    """Get recent trades"""
    limit = request.args.get('limit', 50, type=int)
    trades = db_manager.get_trade_history(limit)
    return jsonify(trades)


@app.route('/api/config', methods=['GET', 'POST'])
def get_set_config():
    """Get or update bot configuration"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    
    if request.method == 'POST':
        # Update config
        new_config = request.json
        with open(config_path, 'w') as f:
            json.dump(new_config, f, indent=2)
        return jsonify({'status': 'success'})
    
    # Get config
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
            }
        }
    
    return jsonify(config)


@app.route('/api/control', methods=['POST'])
def control_bot():
    """Control the bot (start, stop, pause)"""
    action = request.json.get('action')
    
    # In a real implementation, this would communicate with the running bot
    # For now, return mock responses
    if action == 'start':
        return jsonify({'status': 'started'})
    elif action == 'stop':
        return jsonify({'status': 'stopped'})
    elif action == 'pause':
        return jsonify({'status': 'paused'})
    else:
        return jsonify({'error': 'Invalid action'}), 400


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)