import asyncio
import logging
import uuid
import time
from collections import defaultdict
from config import (
    STALENESS_THRESHOLD_SECONDS,
    RR_v8_SL_PERCENTAGE,
    RR_v8_TP_PERCENTAGE,
    BR_v24_RBR_v26_SL_PERCENTAGE,
    BR_v24_RBR_v26_TP_PERCENTAGE
)
from order_executor import execute_buy_signal, execute_sell_signal


logger = logging.getLogger(__name__)

class SignalGenerator:
    def __init__(self, db_handler, api_client):
        self.db_handler = db_handler
        self.api_client = api_client
        self._locks = defaultdict(asyncio.Lock)

    def _calculate_indicators(self, symbol):
        """
        Fetches closed candles from SQLite database and calculates mathematical indicators 
        for RR_v8, BR_v24, and RBR_v26 strategies in pure vectorized Pandas.
        Returns a DataFrame, or None if history is insufficient.
        """
        import pandas as pd
        import numpy as np

        # Fetch last 300 closed candles to ensure stable EMA 200 calculations
        raw_candles = self.db_handler.get_last_n_candles(symbol, 300)
        if not raw_candles or len(raw_candles) < 200:
            logger.debug(f"Insufficient candle history for {symbol} to calculate indicators (Need >= 200, got {len(raw_candles) if raw_candles else 0})")
            return None

        df = pd.DataFrame(raw_candles)

        # Standardize and cast fields to floats for vector math
        df['close'] = df['close_price'].astype(float)
        df['high'] = df['high_price'].astype(float)
        df['low'] = df['low_price'].astype(float)
        df['volume'] = df['volume'].astype(float)

        # 1. Exponential Moving Averages (EMAs)
        df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()

        # 2. Relative Strength Index (RSI 14) with Wilder's smoothing
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        # 3. Volume Metrics (50-period Median and 20-period SMA)
        df['Vol_Median_50'] = df['volume'].rolling(window=50).median()
        df['Vol_SMA_20'] = df['volume'].rolling(window=20).mean()

        # 4. Average True Range (ATR 14) and 50-period ATR SMA
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATR_14'] = true_range.ewm(alpha=1/14, adjust=False).mean()
        df['ATR_SMA_50'] = df['ATR_14'].rolling(window=50).mean()

        return df

    async def process_candle_data(self, candle_data):
        symbol = candle_data.get('s')
        if not symbol:
            return

        async with self._locks[symbol]:
            latest_signal = self.db_handler.get_latest_signal(symbol)

            # State 1: Signal is Pending Execution - Do nothing, wait for order executor
            if latest_signal and latest_signal['Position_Status'] == 'Pending_Execution':
                logger.debug(f"Signal for {symbol} is Pending_Execution. Skipping signal generation.")
                return

            # State 2: Position is Open - ONLY check for sell signals
            if latest_signal and latest_signal['Signal'] == 'Buy' and latest_signal['Position_Status'] in ['Open', 'Partially_Filled']:
                self._check_sell_signal(candle_data, latest_signal)

            # State 3: A previous Buy signal failed execution. Prevent re-triggering on the same condition.
            elif latest_signal and latest_signal['Signal'] == 'Buy' and latest_signal['Position_Status'] == 'Execution_Failed':
                failed_candle_ts = latest_signal['Trigger_Candle_Timestamp']

                # Check if the failure was caused by the last closed candle. If so, do not re-trigger.
                last_closed_candle = self.db_handler.get_last_closed_candle(symbol)
                if last_closed_candle and last_closed_candle['candle_start_time'] == failed_candle_ts:
                    logger.warning(f"Skipping buy signal for {symbol}. The last closed candle ({failed_candle_ts}) already triggered a failed order.")
                    return  # Exit to prevent the loop

                # Check if the failure was caused by an intra-candle update. If so, do not re-trigger.
                current_candle_ts = candle_data.get('t') or candle_data.get('candle_start_time')
                if current_candle_ts == failed_candle_ts:
                    logger.warning(f"Skipping buy signal for {symbol}. A signal for this same live candle timestamp ({failed_candle_ts}) already failed execution.")
                    return  # Exit to prevent the loop

                # If the failure was on an older candle, it's safe to check for a new signal.
                logger.info(f"Previous buy signal for {symbol} failed on an older candle ({failed_candle_ts}). Checking for new signals.")
                self._check_buy_signal(candle_data)

            # State 4: A previous Sell signal failed. Re-evaluate sell conditions.
            elif latest_signal and latest_signal['Signal'] == 'Sell' and latest_signal['Position_Status'] == 'Execution_Failed':
                original_buy_signal = self.db_handler.get_open_buy_signal_for_position(latest_signal['Unique_PositionID'])
                if original_buy_signal:
                    logger.warning(f"Previous sell signal for {symbol} failed. Re-evaluating sell conditions.")
                    self._check_sell_signal(candle_data, original_buy_signal)
                else:
                    logger.error(f"Failed sell for {symbol} but original buy not found. Checking for new buy signal.")
                    self._check_buy_signal(candle_data)

            # State 5: No active position - Check for a new buy signal
            else:
                self._check_buy_signal(candle_data)

    def _check_buy_signal(self, candle_data):
        symbol = candle_data.get('s')

        # Closed-candle buy signal evaluation with staleness check
        last_candle = self.db_handler.get_last_closed_candle(symbol)
        if not last_candle:
            return

        # 1. Staleness Check: Prevent acting on ancient candles after restart or downtime
        candle_timestamp_ms = last_candle.get('candle_start_time')
        if candle_timestamp_ms:
            current_timestamp_s = time.time()
            candle_timestamp_s = candle_timestamp_ms / 1000
            candle_age_s = current_timestamp_s - candle_timestamp_s

            if candle_age_s > STALENESS_THRESHOLD_SECONDS:
                logger.warning(f"Skipping buy signal check for {symbol}. Last closed candle is {candle_age_s:.0f}s old (threshold: {STALENESS_THRESHOLD_SECONDS}s).")
                return

        # 2. Get historical sliding window and calculate indicators
        df = self._calculate_indicators(symbol)
        if df is None or len(df) == 0:
            return

        # Extract the indicators computed for the last closed candle
        last_row = df.iloc[-1]

        # Safety Check: Verify index alignment
        if int(last_row['candle_start_time']) != int(candle_timestamp_ms):
            logger.warning(f"Index mismatch between db query timestamp ({candle_timestamp_ms}) and pandas df ({last_row['candle_start_time']}) for {symbol}")
            return

        # 3. Strategy Conditions Check (Evaluated in concurrent parallel)

        # A. RR_v8 Strategy (Regime Reversion Bearish Capitulation)
        cond_rr_regime = last_row['close'] < (last_row['EMA_200'] * 0.995)
        cond_rr_momentum = last_row['RSI_14'] < 30
        cond_rr_volume = last_row['volume'] > (last_row['Vol_SMA_20'] * 1.2)

        if cond_rr_regime and cond_rr_momentum and cond_rr_volume:
            reason = "RR_v8_Buy"
            if not self.db_handler.has_signal_with_reason_for_candle(symbol, candle_timestamp_ms, reason):
                self._create_buy_signal(symbol, float(last_row['close']), last_candle, reason)
                return  # Fire at most one buy signal per closed candle

        # B. RBR_v26 Strategy (Refined Reversal Pullback - High Conviction)
        ema_dist_20 = (last_row['close'] - last_row['EMA_20']) / last_row['EMA_20']
        cond_rbr_regime = last_row['close'] > last_row['EMA_200']
        cond_rbr_pullback = ema_dist_20 < -0.003
        cond_rbr_momentum = last_row['RSI_14'] < 38
        cond_rbr_volume = last_row['volume'] > (last_row['Vol_Median_50'] * 1.5)
        cond_rbr_volatility = last_row['ATR_14'] < (last_row['ATR_SMA_50'] * 1.2)

        if cond_rbr_regime and cond_rbr_pullback and cond_rbr_momentum and cond_rbr_volume and cond_rbr_volatility:
            reason = "RBR_v26_Buy"
            if not self.db_handler.has_signal_with_reason_for_candle(symbol, candle_timestamp_ms, reason):
                self._create_buy_signal(symbol, float(last_row['close']), last_candle, reason)
                return

        # C. BR_v24 Strategy (Balanced Reversal Pullback - Standard)
        cond_br_regime = last_row['close'] > last_row['EMA_200']
        cond_br_pullback = ema_dist_20 < -0.003
        cond_br_momentum = last_row['RSI_14'] < 40
        cond_br_volume = last_row['volume'] > (last_row['Vol_Median_50'] * 1.5)

        if cond_br_regime and cond_br_pullback and cond_br_momentum and cond_br_volume:
            reason = "BR_v24_Buy"
            if not self.db_handler.has_signal_with_reason_for_candle(symbol, candle_timestamp_ms, reason):
                self._create_buy_signal(symbol, float(last_row['close']), last_candle, reason)
                return

    def _check_sell_signal(self, candle_data, open_position):
        symbol = candle_data.get('s')
        current_price = float(candle_data.get('c'))
        entry_price = open_position['Signal_Price']
        reason = None

        # Determine the triggering strategy from Signal_Reason
        strategy_reason = open_position['Signal_Reason']

        # Dynamically assign Stop Loss and Take Profit levels
        if strategy_reason == 'RR_v8_Buy':
            sl_pct = RR_v8_SL_PERCENTAGE
            tp_pct = RR_v8_TP_PERCENTAGE
        elif strategy_reason in ['BR_v24_Buy', 'RBR_v26_Buy']:
            sl_pct = BR_v24_RBR_v26_SL_PERCENTAGE
            tp_pct = BR_v24_RBR_v26_TP_PERCENTAGE
        else:
            # Safe Fallback
            sl_pct = BR_v24_RBR_v26_SL_PERCENTAGE
            tp_pct = BR_v24_RBR_v26_TP_PERCENTAGE

        # Calculate exact target prices
        stop_loss_price = entry_price * (1 - sl_pct / 100)
        take_profit_price = entry_price * (1 + tp_pct / 100)

        # Trigger exit instantly when limit is crossed
        if current_price <= stop_loss_price:
            reason = f"Hard Stop Loss ({sl_pct}%)"
            self._create_sell_signal(symbol, current_price, candle_data, reason, open_position['Unique_PositionID'])
            return

        if current_price >= take_profit_price:
            reason = f"Hard Take Profit ({tp_pct}%)"
            self._create_sell_signal(symbol, current_price, candle_data, reason, open_position['Unique_PositionID'])
            return

    def _create_buy_signal(self, symbol, price, candle_data, reason):
        # Handle timestamp fields from either live data ('ts') or database ('server_timestamp')
        signal_ts = candle_data.get('ts') or candle_data.get('server_timestamp')
        trigger_ts = candle_data.get('t') or candle_data.get('candle_start_time')

        signal_data = {
            'Unique_PositionID': str(uuid.uuid4()),
            'Symbol': symbol,
            'Signal': 'Buy',
            'Signal_Price': price,
            'Signal_Timestamp': signal_ts,
            'Trigger_Candle_Timestamp': trigger_ts,
            'Signal_Reason': reason,
            'Position_Status': 'Pending_Execution'
        }
        signal_id = self.db_handler.insert_signal(signal_data)
        if signal_id:
            # The executor now creates its own DB connection, passing the trigger price.
            execute_buy_signal(signal_id, symbol, self.api_client, price)

    def _create_sell_signal(self, symbol, price, candle_data, reason, position_id):
        # Handle timestamp fields from either live data ('ts') or database ('server_timestamp')
        signal_ts = candle_data.get('ts') or candle_data.get('server_timestamp')
        trigger_ts = candle_data.get('t') or candle_data.get('candle_start_time')
        
        signal_data = {
            'Unique_PositionID': position_id,
            'Symbol': symbol,
            'Signal': 'Sell',
            'Signal_Price': price,
            'Signal_Timestamp': signal_ts,
            'Trigger_Candle_Timestamp': trigger_ts,
            'Signal_Reason': reason,
            'Position_Status': 'Pending_Execution'
        }
        signal_id = self.db_handler.insert_signal(signal_data)
        if signal_id:
            execute_sell_signal(signal_id, symbol, self.api_client, position_id, price)
