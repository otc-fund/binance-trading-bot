# Binance Trading Bot

A comprehensive trading bot framework for Binance exchange implementing the 130% Engulfing Pattern strategy with 2% stop-loss and 2.5R take-profit.

## Features

- **130% Engulfing Pattern Detection**: Identifies bullish and bearish engulfing patterns with exactly 130% body size requirement on 15-minute candles
- **Precise Entry Points**: Entry at 30% lower than open of engulfed candle for bulls, 30% higher for bears
- **Volatility Filter**: Checks volatility of the 5 candles before the engulfed candle to avoid trading during high volatility periods
- **Risk Management**: Configurable risk parameters and position sizing
- **Stop Loss & Take Profit**: Automatic stop loss at 2% from engulfed candle's low/high and take profit at 2.5R
- **Comprehensive Performance Tracking**: SQLite database integration with detailed trade history and performance metrics
- **Modular Architecture**: Well-organized code structure for maintainability and scalability
- **Binance API Integration**: Full integration with Binance API for trading operations

## Requirements

- Python 3.8+
- Binance API credentials
- Required packages listed in requirements.txt

## Installation

1. Install required packages: `pip install -r requirements.txt`
2. Set up your Binance API credentials in config.json
3. Run the bot: `python trading_bot.py`

## Configuration

Create a `config.json` file with your API credentials and trading parameters:

```json
{
  "api_key": "your_api_key",
  "api_secret": "your_api_secret",
  "testnet": true,
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "timeframe": "15m",
  "leverage": 4,
  "risk_management": {
    "max_position_size": 0.03,
    "max_daily_loss": 0.05,
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.05
  }
}
```

### Timeframe Options
- "1m": 1 minute candles
- "3m": 3 minute candles
- "5m": 5 minute candles
- "15m": 15 minute candles (default)
- "30m": 30 minute candles
- "1h": 1 hour candles
- And more...

### Leverage
- Configurable leverage (default: 4x)
- Combined with 3% position sizing for effective risk management

## Trading Strategy

The bot implements a sophisticated engulfing pattern strategy:

1. Detects bullish and bearish engulfing patterns on 15-minute candles
2. Requires the engulfing candle to have exactly 130% of the previous candle's body size
3. Ensures the engulfing candle exceeds the previous candle's high (for bullish) or low (for bearish)
4. Applies a volatility filter to avoid trading during high volatility periods
5. Places limit orders at the opening price of the engulfed candle

## Architecture

The bot follows a modular design with the following components:

- **trading_bot.py**: Main bot controller and orchestration
- **modules/database.py**: Handles all database operations for trade history and performance metrics
- **modules/performance_tracker.py**: Manages performance metrics and reporting
- **modules/pattern_detector.py**: Handles all pattern detection logic
- **modules/risk_manager.py**: Manages risk management and position sizing
- **ui/app.py**: Web interface for monitoring and controlling the bot
- **ui/templates/index.html**: Main dashboard UI

## Web Interface

The bot includes a web-based user interface with:

- Real-time bot status monitoring
- Performance metrics dashboard
- Trade history visualization
- Configuration management
- Bot controls (start, stop, pause)

### Running the UI

1. Install the required dependencies:
   ```bash
   cd ui
   pip install -r requirements.txt
   ```

2. Run the bot API server (in one terminal):
   ```bash
   python bot_api.py
   ```

3. Run the UI server (in another terminal):
   ```bash
   cd ui
   python app.py
   ```

4. Open your browser and navigate to `http://localhost:5000`

Alternatively, you can run both with the convenience script:
```bash
python run_ui.py
```

The UI will connect to the running bot instance and provide real-time monitoring and control capabilities.

## Risk Management

The bot includes robust risk management features:

- **Stop Loss**: Automatically places stop loss orders at 2% from the low of the engulfed candle for long positions (or 2% from the high of the engulfed candle for short positions)
- **Take Profit**: Automatically places take profit orders at 2.5R (2.5 times the risk) relative to the stop loss distance
- **Position Sizing**: Calculates position size based on account balance and risk parameters
- **Configurable Parameters**: All risk parameters can be adjusted in the configuration file