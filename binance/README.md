# Leverage Trading Bot

A real-time trading bot designed for scalping on cryptocurrency markets. This bot fetches real-time Bitcoin price data using the KuCoin API and employs technical analysis strategies like SMA (Simple Moving Average), RSI (Relative Strength Index), and volume analysis to decide when to enter trades. The bot supports automated leverage trading and includes configurable settings for precise control.

## Features

- **Real-Time Price Monitoring**: Fetches live Bitcoin prices using KuCoin WebSocket and REST APIs.
- **Automated Trading**: Opens and closes trades based on SMA, RSI, and volume analysis.
- **Configurable Strategies**:
  - Customizable trailing stop loss for scalping:
    - Between 16%-30%: Default 5%
    - Between 31%-50%: Default 8%
    - Above 50%: Default 10%
  - Dynamic leverage control.
- **Custom Alerts**: Set custom price alerts that trigger sound notifications.
- **Graphical User Interface**: Minimalist GUI built with PyQt5 for configuration and trade monitoring.
- **Error Handling**: Resilient to API data gaps and adapts to market conditions.

## Screenshot

<p align="center">
  <img src="screenshot.jpg" alt="Leverage Trading Bot Screenshot">
</p>

## Requirements

- Python 3.x
- `PyQt5` for GUI
- `numpy` for calculations
- `requests` for API interaction
- `python-dotenv` for environment variable management
- `pygame` for sound playback

### Install Dependencies

To install the necessary dependencies, run:
```bash
$ pip install PyQt5 numpy requests python-dotenv pygame
```

## Usage

1. **Prepare API Credentials**:
    - Create a `.env` file in the project directory containing your KuCoin API credentials:
      ```env
      KUCOIN_API_KEY=your_api_key
      KUCOIN_API_SECRET=your_api_secret
      KUCOIN_API_PASSWORD=your_api_password
      ```

2. **Run the Bot**: Execute the main script `main.py`:
    ```bash
    $ python3 main.py
    ```

3. **Configure Settings**:
    - Set leverage, stop loss thresholds, and trade direction through the GUI.
    - Enable or disable automatic position opening after a trade is closed.

4. **Monitor Trades**:
    - View open positions and performance in the GUI.
    - The bot will decide when to open or close positions based on configured strategies.

5. **Alert Trigger**:
    - Enter a target price in the alert field. If the price is reached, a sound will play.

### Trade Logic
The bot uses the following indicators for trading decisions:
- **Simple Moving Averages (SMA)**:
  - SMA(7): Short-term average
  - SMA(25): Long-term average
- **Relative Strength Index (RSI)**:
  - Identifies overbought (>70) and oversold (<30) conditions.
- **Volume Analysis**:
  - Confirms signals with significant volume changes.

The bot opens a trade only when SMA, RSI, and volume signals align. If conditions are unclear, it waits and recalculates.

### Controls
- **Set Alert Price**: Press **Enter** after typing a value in the alert field.
- **Close Window**: Use the GUI close button or `Esc`.

## Configuration

- **Customizable Trailing Stop Loss**: Adjust percentages based on trade conditions.
- **Dynamic Trade Direction**:
  - `Invert`: Open in the opposite direction of the last trade.
  - `Keep`: Maintain the direction of the last trade.
  - `Long`: Always buy.
  - `Short`: Always sell.
- **Trade Monitoring**:
  - View live positions, margin, PnL, and stop loss thresholds.

## File Structure
```text
├── leverage-trading-bot.py  # Main script file
├── api.py                   # API interaction logic
├── ui.py                    # PyQt5 GUI
├── sound.py                 # Sound alert handler
├── assets/
│   └── sounds/
│       └── alert.mp3        # Sound file for notifications
├── .env                     # KuCoin API credentials
└── README.md                # Documentation
```

## Notes
- Ensure an active internet connection for API interaction.
- Adjust the trailing stop loss and leverage settings to match your risk tolerance.
- The bot is designed for educational purposes. Always test in a simulated environment before live trading.

## Author
Fábio Berbert de Paula  
[GitHub Repository](https://github.com/fberbert/leverage-trading-bot)
