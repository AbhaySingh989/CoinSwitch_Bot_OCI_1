# config.py

import os
# Get the database path from an environment variable, or use 'Crypto_Data.db' as a default for local running
DB_NAME = os.getenv('DATABASE_PATH', 'Crypto_Data.db')
TABLE_NAME = "CandleStick_Data_WebSocket"

# Logging Configuration
LOG_FILE = "data_collector.log"

# Trading Pairs and Interval
SYMBOLS = ["BNBUSDT","BTCUSDT","ETHUSDT","XRPUSDT"]
INTERVAL = "5"      # Set the candle interval for 1-minute interval value would be 1

# The maximum age (in seconds) a closed candle can be to trigger a new buy signal.
# This prevents acting on stale data after a restart or disconnect. It looks at the open price for last closed candle
# Set to 120 seconds (for a 1-minute interval - 60 sec+ 60 sec) as a safe default.
STALENESS_THRESHOLD_SECONDS = 1800

# WebSocket Configuration
BASE_URL = "wss://ws.coinswitch.co"
NAMESPACE = "/exchange_2"
SOCKET_PATH = "/pro/realtime-rates-socket/futures/exchange_2"
EVENT_CANDLES = "FETCH_CANDLESTICK_CS_PRO"

# Order Execution Configuration
DRY_RUN = True # Set to False for live trading, True for Dry run
LEVERAGE = 10  # The leverage to be applied (e.g., 10 for 10x).
ORDER_AMOUNT = 10  # The desired amount of quote currency (e.g., USDT) to use for an order *before* leverage.
BUY_SIGNAL_EXECUTION_THRESHOLD_SECONDS = 5  # The maximum time in seconds allowed from signal generation to a confirmed 'EXECUTED' status.
SELL_ORDER_STATUS_MONITORING_TIME = 15 # This is the time in seconds post which the system would make a Get order status call for the sell order placed to confirm the order status  'EXECUTED' from the exchange.
# Strategy-specific Risk Management Configs (Percentage)
# RR_v8 (Regime Reversion v8): 0.10% SL / 0.20% TP
RR_v8_SL_PERCENTAGE = 0.10
RR_v8_TP_PERCENTAGE = 0.20

# BR_v24 (Balanced Reversal v24) & RBR_v26 (Refined Reversal v26): 0.15% SL / 0.15% TP
BR_v24_RBR_v26_SL_PERCENTAGE = 0.15
BR_v24_RBR_v26_TP_PERCENTAGE = 0.15

