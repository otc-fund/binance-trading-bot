# Binance Trading Bot

A comprehensive trading bot framework for Binance exchange with advanced pattern recognition capabilities.

## Features

- **Engulfing Pattern Detection**: Identifies bullish and bearish engulfing patterns with at least 150% body size requirement
- **Volatility Filter**: Checks volatility of the 3 candles before the engulfed candle to avoid trading during high volatility periods
- **Limit Orders**: Places limit orders at the opening price of the engulfed (previous) candle
- **Risk Management**: Configurable risk parameters and position sizing
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
  "risk_management": {
    "max_position_size": 0.1,
    "max_daily_loss": 0.05,
    "stop_loss_pct": 0.05,
    "take_profit_pct": 0.10
  }
}
```

## Trading Strategy

The bot implements a sophisticated engulfing pattern strategy:

1. Detects bullish and bearish engulfing patterns
2. Requires the engulfing candle to have at least 150% of the previous candle's body size
3. Ensures the engulfing candle exceeds the previous candle's high (for bullish) or low (for bearish)
4. Applies a volatility filter to avoid trading during high volatility periods
5. Places limit orders at the opening price of the engulfed candle