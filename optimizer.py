
import pandas as pd
from skopt import gp_minimize
from skopt.space import Real, Integer
from skopt.utils import use_named_args
import time
from database_handler import DatabaseHandler
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Backtesting Logic ---

def run_backtest(params):
    """
    Runs a backtest with the given parameters.
    This is a simplified simulation and does not include all the complexities of the live system.
    """
    db_handler = DatabaseHandler()
    db_handler.connect()
    # Assuming you have a function to get all historical data for a symbol
    # You might need to create this function in your DatabaseHandler
    historical_data = db_handler.get_all_candles('BTCUSDT') # Example symbol
    if not historical_data:
        logger.error("No historical data found for backtesting.")
        return 0

    balance = 1000  # Starting balance in USDT
    position = None
    entry_price = 0
    high_water_mark = 0
    is_tp_activated = False

    for candle in historical_data:
        close_price = candle['close_price']
        open_price = candle['open_price']
        high_price = candle['high_price']

        # --- Sell Logic ---
        if position == 'long':
            high_water_mark = max(high_water_mark, close_price)

            # Check for TP activation
            if not is_tp_activated:
                initial_tp_price = entry_price * (1 + params['take_profit_percentage'] / 100)
                if close_price >= initial_tp_price:
                    is_tp_activated = True

            # Apply exit logic based on state
            if is_tp_activated:
                profit_trail_stop_price = high_water_mark * (1 - params['profit_trail_percentage'] / 100)
                if close_price <= profit_trail_stop_price:
                    balance = balance * (close_price / entry_price)
                    position = None
                    is_tp_activated = False
                    logger.info(f"Sold at {close_price:.2f} (Profit Trail). Balance: {balance:.2f}")
            else:
                trailing_stop_price = high_water_mark * (1 - params['trailing_stop_loss'] / 100)
                if close_price <= trailing_stop_price:
                    balance = balance * (close_price / entry_price)
                    position = None
                    logger.info(f"Sold at {close_price:.2f} (Trailing Stop). Balance: {balance:.2f}")

        # --- Buy Logic ---
        if position is None:
            # Closed-candle buy signal
            close_open_percentage = ((close_price - open_price) / open_price) * 100 if open_price != 0 else 0
            high_close_percentage = ((high_price - close_price) / high_price) * 100 if high_price != 0 else 0

            if close_open_percentage >= params['close_open_threshold'] and high_close_percentage <= params['high_close_threshold']:
                position = 'long'
                entry_price = close_price
                high_water_mark = close_price
                logger.info(f"Bought at {entry_price:.2f}. Balance: {balance:.2f}")

    # If still in a position at the end, close it at the last price
    if position == 'long':
        balance = balance * (historical_data[-1]['close_price'] / entry_price)

    db_handler.close()
    return balance


# --- Optimization ---

# 1. Define the search space for the parameters
search_space = [
    Real(0.1, 5.0, name='trailing_stop_loss'),
    Real(0.1, 10.0, name='take_profit_percentage'),
    Real(0.1, 5.0, name='profit_trail_percentage'),
    Integer(1, 10, name='close_open_threshold'),
    Real(0.1, 2.0, name='high_close_threshold'),
]

# 2. Define the objective function
@use_named_args(search_space)
def objective(**params):
    """
    The objective function to minimize.
    We want to maximize profit, so we return the negative profit.
    """
    start_time = time.time()
    profit = run_backtest(params)
    end_time = time.time()
    logger.info(f"Backtest completed in {end_time - start_time:.2f}s. Profit: {profit:.2f}")
    
    # We want to maximize profit, so we return the negative of it
    return -profit

if __name__ == '__main__':
    # 3. Run the optimization
    n_calls = 100  # Number of iterations
    logger.info(f"Starting Bayesian Optimization with {n_calls} calls...")
    
    result = gp_minimize(
        objective,
        search_space,
        n_calls=n_calls,
        random_state=42,
        n_jobs=-1  # Use all available CPU cores
    )

    # 4. Print the results
    logger.info("Optimization finished.")
    logger.info(f"Best score (negative profit): {-result.fun:.2f}")
    logger.info("Best parameters found:")
    for param, value in zip(search_space, result.x):
        logger.info(f"- {param.name}: {value}")

