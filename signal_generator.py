import asyncio
import logging
import uuid
import time
from collections import defaultdict
from config import STALENESS_THRESHOLD_SECONDS, TRAILING_STOP_LOSS_PERCENTAGE, TAKE_PROFIT_STAGES
from order_executor import execute_buy_signal, execute_sell_signal


logger = logging.getLogger(__name__)

class SignalGenerator:
    def __init__(self, db_handler, api_client):
        self.db_handler = db_handler
        self.api_client = api_client
        self._locks = defaultdict(asyncio.Lock)

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
        current_price = float(candle_data.get('c'))
        open_price = float(candle_data.get('o'))
        candle_timestamp = candle_data.get('t') or candle_data.get('candle_start_time')

        # Intra-candle buy signal (US2.7)
        if open_price != 0:
            percentage_increase = ((current_price - open_price) / open_price) * 100
            increase_threshold = 12
            if percentage_increase >= increase_threshold:
                # First check the condition, THEN check the database to prevent loops.
                reason = f'Intra-candle {increase_threshold}% increase'
                if not self.db_handler.has_signal_with_reason_for_candle(symbol, candle_timestamp, reason):
                    self._create_buy_signal(symbol, current_price, candle_data, reason)

        # Closed-candle buy signal (US2.4) with staleness check
        last_candle = self.db_handler.get_last_closed_candle(symbol)
        if not last_candle:
            return

        # Staleness Check
        candle_timestamp_ms = last_candle.get('candle_start_time')
        if candle_timestamp_ms:
            current_timestamp_s = time.time()
            candle_timestamp_s = candle_timestamp_ms / 1000
            candle_age_s = current_timestamp_s - candle_timestamp_s

            if candle_age_s > STALENESS_THRESHOLD_SECONDS:
                logger.warning(f"Skipping buy signal check for {symbol}. Last closed candle is {candle_age_s:.0f}s old (threshold: {STALENESS_THRESHOLD_SECONDS}s).")
                return

        close_open_percentage = self._calculate_close_open_percentage(last_candle['open_price'], last_candle['close_price'])
        high_close_percentage = self._calculate_high_close_percentage(last_candle['high_price'], last_candle['close_price'])

        close_open_threshold = 35 #3.5
        high_close_threshold = 0.05 #0.75
        if close_open_percentage >= close_open_threshold and high_close_percentage <= high_close_threshold: #close_open_percentage >= 4.0 and high_close_percentage <= 1.0:
            # First check the conditions, THEN check the database to prevent loops.
            reason = f'Bullish Momentum ({close_open_threshold}%, {high_close_threshold}%)'
            if not self.db_handler.has_signal_with_reason_for_candle(symbol, last_candle['candle_start_time'], reason):
                self._create_buy_signal(symbol, last_candle['close_price'], last_candle, reason)

    def _check_sell_signal(self, candle_data, open_position):
        symbol = candle_data.get('s')
        current_price = float(candle_data.get('c'))
        entry_price = open_position['Signal_Price']
        signal_id = open_position['Signal_ID']
        reason = None

        # Always update the High Water Mark first
        high_water_mark = open_position['High_Water_Mark'] or entry_price
        if current_price > high_water_mark:
            self.db_handler.update_high_water_mark(signal_id, current_price)
            high_water_mark = current_price  # Use the new HWM for the current check

        # --- Multi-Stage Take-Profit Logic (US 2.10)---
        activated_level = open_position['take_profit_activated'] or 0

        # 1. Check for activation of the next profit stage
        for stage_profit_perc, _ in TAKE_PROFIT_STAGES:
            if stage_profit_perc > activated_level:
                activation_price = entry_price * (1 + stage_profit_perc / 100)
                if current_price >= activation_price:
                    self.db_handler.update_take_profit_level(signal_id, stage_profit_perc)
                    activated_level = stage_profit_perc # Update state for the current tick
                    logging.info(f"Activated {stage_profit_perc}% profit stage for Signal_ID {signal_id}.")
        
        # 2. Determine the current trailing stop percentage
        current_trail_perc = 0
        if activated_level == 0:
            # Stage 0: No profit stage activated, use the initial wide stop-loss
            current_trail_perc = TRAILING_STOP_LOSS_PERCENTAGE
            reason_template = f"Trailing Stop-Loss ({current_trail_perc}%)"
        else:
            # Stage N: A profit stage is active, find the corresponding trail
            for stage_profit_perc, stage_trail_perc in TAKE_PROFIT_STAGES:
                if stage_profit_perc == activated_level:
                    current_trail_perc = stage_trail_perc
                    break
            reason_template = f"Profit Trail Stop ({activated_level}% activation -> {current_trail_perc}% trail)"

        # 3. Apply the exit logic
        if current_trail_perc > 0:
            trailing_stop_price = high_water_mark * (1 - current_trail_perc / 100)
            if current_price <= trailing_stop_price:
                reason = reason_template

        if reason:
            self._create_sell_signal(symbol, current_price, candle_data, reason, open_position['Unique_PositionID'])

    def _calculate_close_open_percentage(self, open_price, close_price):
        if open_price == 0:
            return 0
        return ((close_price - open_price) / open_price) * 100

    def _calculate_high_close_percentage(self, high_price, close_price):
        if high_price == 0:
            return 0
        return ((high_price - close_price) / high_price) * 100

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
