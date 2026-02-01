# Binance Trading Bot UI

A web-based user interface for monitoring and controlling the Binance Trading Bot.

## Features

- Real-time bot status monitoring
- Performance metrics dashboard
- Trade history visualization
- Configuration management
- Bot controls (start, stop, pause)

## Installation

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Make sure you have the main trading bot modules installed in your environment

## Usage

1. Run the Flask application:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to `http://localhost:5000`

## Architecture

The UI connects to the backend modules to retrieve:
- Performance metrics
- Trade history
- Bot status
- Configuration settings

## Endpoints

- `GET /` - Main dashboard
- `GET /api/status` - Bot status
- `GET /api/performance` - Performance metrics
- `GET /api/trades` - Trade history
- `GET/POST /api/config` - Configuration management
- `POST /api/control` - Bot controls

## Security Note

For production use, make sure to:
- Add authentication
- Secure API endpoints
- Use HTTPS
- Protect sensitive configuration data