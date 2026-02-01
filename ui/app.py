"""
Flask Web Interface for Binance Trading Bot
Provides a simple UI to monitor and control the trading bot
"""

from flask import Flask, render_template, jsonify, request
import os
import sys
import json
from datetime import datetime
import requests

app = Flask(__name__)

# API endpoint for the bot
BOT_API_URL = 'http://localhost:5001'


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/api/status')
def get_bot_status():
    """Get current bot status from the bot API"""
    try:
        response = requests.get(f'{BOT_API_URL}/api/status')
        return jsonify(response.json())
    except Exception as e:
        # Return mock data if bot API is not available
        return jsonify({
            'status': 'disconnected',
            'running_since': None,
            'current_symbols': [],
            'total_trades': 0,
            'current_balance': 0.0,
            'pnl_24h': 0.0
        })


@app.route('/api/performance')
def get_performance():
    """Get performance metrics from the bot API"""
    try:
        response = requests.get(f'{BOT_API_URL}/api/performance')
        return jsonify(response.json())
    except Exception as e:
        # Return mock data if bot API is not available
        return jsonify({
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'profit_factor': 0.0
        })


@app.route('/api/trades')
def get_trades():
    """Get recent trades from the bot API"""
    limit = request.args.get('limit', 50, type=int)
    try:
        response = requests.get(f'{BOT_API_URL}/api/trades?limit={limit}')
        return jsonify(response.json())
    except Exception as e:
        # Return empty array if bot API is not available
        return jsonify([])


@app.route('/api/config', methods=['GET', 'POST'])
def get_set_config():
    """Get or update bot configuration via the bot API"""
    if request.method == 'POST':
        # Update config via bot API
        new_config = request.json
        try:
            response = requests.post(f'{BOT_API_URL}/api/config', json=new_config)
            return jsonify(response.json())
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # Get config via bot API
    try:
        response = requests.get(f'{BOT_API_URL}/api/config')
        return jsonify(response.json())
    except Exception as e:
        # Return default config if bot API is not available
        return jsonify({
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
        })


@app.route('/api/control', methods=['POST'])
def control_bot():
    """Control the bot (start, stop, pause) via the bot API"""
    action = request.json.get('action')
    try:
        response = requests.post(f'{BOT_API_URL}/api/control', json={'action': action})
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)