import sqlite3
import pandas as pd
import numpy as np
import itertools
import pytz
from skopt import gp_minimize
from skopt.space import Real, Integer
from skopt.utils import use_named_args

DB_PATH = 'Crypto_Data.db' # Path is relative to the project root
IST = pytz.timezone('Asia/Kolkata')

def _get_completed_trades():
    """Internal helper to fetch and process all completed trades."""
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT Unique_PositionID, Signal, Signal_Timestamp, Signal_Price, Filled_Quantity, Signal_Reason, Symbol, High_Water_Mark FROM Signals", con)
    con.close()

    if df.empty:
        return None

    # Convert timestamps and localize to IST
    df['Signal_Timestamp'] = pd.to_datetime(df['Signal_Timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert(IST)
    
    buy_signals = df[df['Signal'] == 'Buy'].copy()
    sell_signals = df[df['Signal'] == 'Sell'].copy()

    completed_trades = pd.merge(
        buy_signals, sell_signals, on='Unique_PositionID', suffixes=('_buy', '_sell')
    )

    if not completed_trades.empty:
        quantity = completed_trades['Filled_Quantity_sell'].fillna(1).replace(0, 1)
        completed_trades['PnL'] = (completed_trades['Signal_Price_sell'] - completed_trades['Signal_Price_buy']) * quantity
        completed_trades = completed_trades.sort_values(by='Signal_Timestamp_sell')
    
    return completed_trades

def get_all_trades_data():
    """Gets data for the 'All Trades' table, including advanced metrics."""
    try:
        completed_trades = _get_completed_trades()
        if completed_trades is None or completed_trades.empty:
            return []

        con = sqlite3.connect(DB_PATH)
        candles_df = pd.read_sql_query("SELECT * FROM CandleStick_Data_WebSocket", con)
        con.close()
        candles_df['candle_start_time'] = pd.to_datetime(candles_df['candle_start_time'], unit='ms').dt.tz_localize('UTC').dt.tz_convert(IST)

        all_trades_data = []
        for _, trade in completed_trades.iterrows():
            trade_candles = candles_df[
                (candles_df['symbol'] == trade['Symbol_buy']) &
                (candles_df['candle_start_time'] >= trade['Signal_Timestamp_buy']) &
                (candles_df['candle_start_time'] <= trade['Signal_Timestamp_sell'])
            ]

            highest_price_market = trade_candles['high_price'].max() if not trade_candles.empty else trade['Signal_Price_buy']
            lowest_price_market = trade_candles['low_price'].min() if not trade_candles.empty else trade['Signal_Price_buy']

            highest_perc_change = ((highest_price_market - trade['Signal_Price_buy']) / trade['Signal_Price_buy']) * 100 if trade['Signal_Price_buy'] != 0 else 0
            lowest_perc_change = ((lowest_price_market - trade['Signal_Price_buy']) / trade['Signal_Price_buy']) * 100 if trade['Signal_Price_buy'] != 0 else 0

            high_water_mark_signal = trade['High_Water_Mark_buy']
            peak_capture_perc = ((highest_price_market - high_water_mark_signal) / highest_price_market) * 100 if highest_price_market != 0 else 0
            hold_time_mins = (trade['Signal_Timestamp_sell'] - trade['Signal_Timestamp_buy']).total_seconds() / 60

            trade_data = {
                'buy_date': trade['Signal_Timestamp_buy'].strftime('%Y-%m-%d'),
                'symbol': trade['Symbol_buy'],
                'entry_datetime': trade['Signal_Timestamp_buy'].strftime('%Y-%m-%d %H:%M:%S'),
                'exit_datetime': trade['Signal_Timestamp_sell'].strftime('%Y-%m-%d %H:%M:%S'),
                'hold_time_mins': hold_time_mins,
                'entry_price': trade['Signal_Price_buy'],
                'exit_price': trade['Signal_Price_sell'],
                'pnl': trade['PnL'],
                'high_water_mark_signal': high_water_mark_signal,
                'highest_price_market': highest_price_market,
                'peak_capture_perc': peak_capture_perc,
                'highest_perc_change': highest_perc_change,
                'lowest_perc_change': lowest_perc_change,
                'exit_reason': trade['Signal_Reason_sell']
            }
            all_trades_data.append({k: v if pd.notna(v) else 0 for k, v in trade_data.items()})
        
        return all_trades_data

    except Exception as e:
        print(f"Error in analysis engine (all trades): {e}")
        return { 'error': str(e) }

def get_insights_data():
    """Gets data for the new 'Insights' section."""
    try:
        completed_trades = _get_completed_trades()
        if completed_trades is None or completed_trades.empty:
            return {
                'pnl_by_exit_reason': {},
                'holding_period_distribution': {},
                'pnl_by_holding_period': {}
            }

        # P&L by Exit Reason
        pnl_by_exit_reason = completed_trades.groupby('Signal_Reason_sell')['PnL'].sum().to_dict()

        # Holding Period Analysis
        bins = [0, 1, 4, 12, 24, 48, 168, np.inf]
        labels = ['0-1h', '1-4h', '4-12h', '12-24h', '1-2d', '2-7d', '>7d']
        
        if 'holding_period_hours' not in completed_trades.columns:
            completed_trades['holding_period_hours'] = (completed_trades['Signal_Timestamp_sell'] - completed_trades['Signal_Timestamp_buy']).dt.total_seconds() / 3600

        # Use Categorical to ensure all bins are represented
        completed_trades['holding_period_bucket'] = pd.cut(
            completed_trades['holding_period_hours'], 
            bins=bins, 
            labels=labels, 
            right=False
        )
        
        # Ensure all labels are present in the final dicts
        holding_period_dist = completed_trades['holding_period_bucket'].value_counts().reindex(labels, fill_value=0).to_dict()
        pnl_by_holding_period = completed_trades.groupby('holding_period_bucket')['PnL'].mean().reindex(labels, fill_value=0).fillna(0).to_dict()

        return {
            'pnl_by_exit_reason': pnl_by_exit_reason,
            'holding_period_distribution': holding_period_dist,
            'pnl_by_holding_period': pnl_by_holding_period
        }

    except Exception as e:
        print(f"Error in analysis engine (insights): {e}")
        return { 'error': str(e) }

def get_daily_win_rate_data(period='D'):
    """Calculates the daily win rate."""
    try:
        completed_trades = _get_completed_trades()
        if completed_trades is None or completed_trades.empty:
            return {'labels': [], 'win_rate': []}

        resample_period = period
        if period == 'W':
            resample_period = 'W-MON'
        elif period == 'M':
            resample_period = 'ME'

        completed_trades['win'] = completed_trades['PnL'] > 0
        daily_win_rate = completed_trades.set_index('Signal_Timestamp_buy').resample(resample_period)['win'].mean().fillna(0) * 100

        if period == 'D':
            labels = daily_win_rate.index.strftime('%d-%b')
        elif period == 'W':
            labels = (daily_win_rate.index - pd.to_timedelta(7, unit='d')).strftime('%d-%b')
        elif period == 'M':
            labels = daily_win_rate.index.strftime('%b-%Y')
        else:
            labels = daily_win_rate.index.strftime('%d-%b')

        return {
            'labels': labels.tolist(),
            'win_rate': daily_win_rate.values.tolist()
        }
    except Exception as e:
        print(f"Error in analysis engine (daily win rate): {e}")
        return { 'error': str(e) }

def get_daily_completed_positions_data(period='D'):
    """Calculates the number of completed positions per day."""
    try:
        completed_trades = _get_completed_trades()
        if completed_trades is None or completed_trades.empty:
            return {'labels': [], 'positions': []}

        resample_period = period
        if period == 'W':
            resample_period = 'W-MON'
        elif period == 'M':
            resample_period = 'ME'

        daily_positions = completed_trades.set_index('Signal_Timestamp_buy').resample(resample_period)['Unique_PositionID'].count()

        if period == 'D':
            labels = daily_positions.index.strftime('%d-%b')
        elif period == 'W':
            labels = (daily_positions.index - pd.to_timedelta(7, unit='d')).strftime('%d-%b')
        elif period == 'M':
            labels = daily_positions.index.strftime('%b-%Y')
        else:
            labels = daily_positions.index.strftime('%d-%b')

        return {
            'labels': labels.tolist(),
            'positions': daily_positions.values.tolist()
        }
    except Exception as e:
        print(f"Error in analysis engine (daily completed positions): {e}")
        return { 'error': str(e) }

def get_pnl_charts_data(period='D'):
    """Gets data formatted for the P&L charts, aggregated by a specified period."""
    try:
        completed_trades = _get_completed_trades()
        if completed_trades is None or completed_trades.empty:
            return {'labels': [], 'daily_pnl': [], 'cumulative_pnl': []}

        resample_period = period
        if period == 'W':
            resample_period = 'W-MON'
        elif period == 'M':
            resample_period = 'ME'

        daily_pnl = completed_trades.set_index('Signal_Timestamp_buy').resample(resample_period)['PnL'].sum()
        cumulative_pnl = daily_pnl.cumsum()

        if period == 'D':
            labels = daily_pnl.index.strftime('%d-%b')
        elif period == 'W':
            labels = (daily_pnl.index - pd.to_timedelta(7, unit='d')).strftime('%d-%b')
        elif period == 'M':
            labels = daily_pnl.index.strftime('%b-%Y')
        else:
            labels = daily_pnl.index.strftime('%d-%b')

        return {
            'labels': labels.tolist(),
            'daily_pnl': daily_pnl.values.tolist(),
            'cumulative_pnl': cumulative_pnl.values.tolist()
        }
    except Exception as e:
        print(f"Error in analysis engine (pnl charts): {e}")
        return { 'error': str(e) }

def get_buy_strategy_data(period='D'):
    """Analyzes performance based on buy strategy."""
    try:
        completed_trades = _get_completed_trades()
        if completed_trades is None or completed_trades.empty:
            return {
                'strategy_summary': {},
                'strategy_trending': {}
            }

        # For US-D11.1: Performance Summary
        strategy_summary_df = completed_trades.groupby('Signal_Reason_buy').agg(
            trade_count=('Unique_PositionID', 'count'),
            total_pnl=('PnL', 'sum')
        ).reset_index()

        strategy_summary = {
            'labels': strategy_summary_df['Signal_Reason_buy'].tolist(),
            'trade_counts': strategy_summary_df['trade_count'].tolist(),
            'pnl_values': strategy_summary_df['total_pnl'].tolist()
        }

        # For US-D11.2: P&L Trend
        completed_trades = completed_trades.sort_values(by='Signal_Timestamp_buy')
        
        resample_period = period
        if period == 'W':
            resample_period = 'W-MON'
        elif period == 'M':
            resample_period = 'ME'

        daily_pnl_by_strategy = completed_trades.pivot_table(
            index=pd.to_datetime(completed_trades['Signal_Timestamp_buy'].dt.date),
            columns='Signal_Reason_buy',
            values='PnL',
            aggfunc='sum'
        ).fillna(0)

        daily_pnl_by_strategy = daily_pnl_by_strategy.resample(resample_period).sum()
        cumulative_pnl_by_strategy = daily_pnl_by_strategy.cumsum()

        if period == 'D':
            labels = cumulative_pnl_by_strategy.index.strftime('%d-%b')
        elif period == 'W':
            labels = (cumulative_pnl_by_strategy.index - pd.to_timedelta(7, unit='d')).strftime('%d-%b')
        elif period == 'M':
            labels = cumulative_pnl_by_strategy.index.strftime('%b-%Y')
        else:
            labels = cumulative_pnl_by_strategy.index.strftime('%d-%b')

        strategy_trending = {
            'labels': labels.tolist(),
            'datasets': []
        }
        for strategy_name in cumulative_pnl_by_strategy.columns:
            strategy_trending['datasets'].append({
                'label': strategy_name,
                'data': cumulative_pnl_by_strategy[strategy_name].tolist(),
            })

        return {
            'strategy_summary': strategy_summary,
            'strategy_trending': strategy_trending
        }

    except Exception as e:
        print(f"Error in analysis engine (buy strategy): {e}")
        return { 'error': str(e) }

def get_peak_concurrent_positions_data(period='D'):
    """Calculates the peak number of concurrently open positions for each day."""
    try:
        con = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT Signal, Signal_Timestamp FROM Signals", con)
        con.close()

        if df.empty:
            return {'labels': [], 'data': []}

        df['timestamp'] = pd.to_datetime(df['Signal_Timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert(IST)
        df['change'] = df['Signal'].apply(lambda x: 1 if x == 'Buy' else -1)
        events_df = df[['timestamp', 'change']].sort_values('timestamp')
        events_df['open_positions'] = events_df['change'].cumsum()
        
        resample_period = period
        if period == 'W':
            resample_period = 'W-MON'
        elif period == 'M':
            resample_period = 'ME'

        daily_max = events_df.set_index('timestamp')['open_positions'].resample(resample_period).max()
        daily_max = daily_max.ffill().fillna(0)

        if period == 'D':
            labels = daily_max.index.strftime('%d-%b')
        elif period == 'W':
            labels = (daily_max.index - pd.to_timedelta(7, unit='d')).strftime('%d-%b')
        elif period == 'M':
            labels = daily_max.index.strftime('%b-%Y')
        else:
            labels = daily_max.index.strftime('%d-%b')

        return {
            'labels': labels.tolist(),
            'data': daily_max.astype(int).tolist()
        }
    except Exception as e:
        print(f"Error in analysis engine (peak positions): {e}")
        return {'error': str(e)}

def get_scorecard_kpis():
    """Connects to the DB and calculates all KPIs for the scorecard."""
    try:
        completed_trades = _get_completed_trades()
        
        if completed_trades is None or completed_trades.empty:
            return {
                'total_completed_positions': 0, 'total_realized_pnl': 0,
                'total_open_positions': 0, 'average_holding_period_minutes': 0,
                'win_rate': 0, 'total_commission_incurred': 0,
                'last_updated': pd.Timestamp.now(tz=IST).isoformat()
            }

        total_completed_positions = len(completed_trades)
        pnl = completed_trades['PnL'].sum()
        wins = completed_trades[completed_trades['PnL'] > 0].shape[0]
        win_rate = (wins / total_completed_positions) * 100 if total_completed_positions > 0 else 0
        holding_period = completed_trades['Signal_Timestamp_sell'] - completed_trades['Signal_Timestamp_buy']
        avg_holding_period_minutes = (holding_period.mean().total_seconds()) / 60
        if pd.isna(avg_holding_period_minutes):
            avg_holding_period_minutes = 0

        # Commission Calculation
        buy_value = completed_trades['Signal_Price_buy'] * completed_trades['Filled_Quantity_sell']
        sell_value = completed_trades['Signal_Price_sell'] * completed_trades['Filled_Quantity_sell']
        total_commission_incurred = (buy_value.sum() * 0.004) + (sell_value.sum() * 0.004)

        con = sqlite3.connect(DB_PATH)
        all_signals = pd.read_sql_query("SELECT * FROM Signals", con)
        con.close()
        
        # Convert timestamps for open positions calculation
        all_signals['Signal_Timestamp'] = pd.to_datetime(all_signals['Signal_Timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert(IST)
        
        buy_signals = all_signals[all_signals['Signal'] == 'Buy']
        open_positions_df = buy_signals[~buy_signals['Unique_PositionID'].isin(completed_trades['Unique_PositionID'])]
        total_open_positions = len(open_positions_df)

        return {
            'total_completed_positions': total_completed_positions,
            'total_realized_pnl': pnl,
            'total_open_positions': total_open_positions,
            'average_holding_period_minutes': avg_holding_period_minutes,
            'win_rate': win_rate,
            'total_commission_incurred': total_commission_incurred,
            'last_updated': pd.Timestamp.now(tz=IST).isoformat()
        }

    except Exception as e:
        print(f"Error in analysis engine (scorecard): {e}")
        return { 'error': str(e) }

def get_symbol_performance():
    """Calculates performance metrics grouped by symbol."""
    try:
        completed_trades = _get_completed_trades()
        if completed_trades is None or completed_trades.empty: return []

        symbol_groups = completed_trades.groupby('Symbol_buy')
        summary = symbol_groups.agg(total_pnl=('PnL', 'sum'), trade_count=('PnL', 'count')).reset_index()
        wins_per_symbol = completed_trades[completed_trades['PnL'] > 0].groupby('Symbol_buy').size().reset_index(name='win_count')
        summary = pd.merge(summary, wins_per_symbol, on='Symbol_buy', how='left').fillna(0)
        summary['win_rate'] = (summary['win_count'] / summary['trade_count']) * 100
        return summary.to_dict(orient='records')
    except Exception as e:
        print(f"Error in analysis engine (symbol performance): {e}")
        return { 'error': str(e) }

def run_sell_strategy_optimization(TAKE_PROFIT_PERCENTAGES, TRAILING_STOP_LOSS_PERCENTAGES, PROFIT_TRAIL_PERCENTAGES):
    """Performs a grid search to find the optimal sell strategy parameters."""
    try:
        trades_df = _get_completed_trades()
        if trades_df is None or trades_df.empty: return {'error': 'No completed trades to analyze.'}

        con = sqlite3.connect(DB_PATH)
        candles_df = pd.read_sql_query("SELECT * FROM CandleStick_Data_WebSocket", con)
        con.close()
        candles_df['candle_start_time'] = pd.to_datetime(candles_df['candle_start_time'], unit='ms')

        # Parameter Grid
        param_combinations = list(itertools.product(TAKE_PROFIT_PERCENTAGES, TRAILING_STOP_LOSS_PERCENTAGES, PROFIT_TRAIL_PERCENTAGES))

        best_params = {}
        best_pnl = -np.inf

        for tpp, tslp, ptp in param_combinations:
            total_simulated_pnl = 0
            for _, trade in trades_df.iterrows():
                trade_journey_df = candles_df[(candles_df['symbol'] == trade['Symbol_buy']) & (candles_df['candle_start_time'] >= trade['Signal_Timestamp_buy'])].sort_values(by='candle_start_time').reset_index(drop=True)
                if trade_journey_df.empty: continue

                entry_price = trade['Signal_Price_buy']
                quantity = trade['Filled_Quantity_sell'] if pd.notna(trade['Filled_Quantity_sell']) and trade['Filled_Quantity_sell'] > 0 else 1
                high_water_mark = entry_price
                take_profit_activated = False
                sell_price = 0

                for _, candle in trade_journey_df.iterrows():
                    high_water_mark = max(high_water_mark, candle['high_price'])
                    if not take_profit_activated and high_water_mark >= entry_price * (1 + tpp / 100):
                        take_profit_activated = True
                    
                    stop_price = high_water_mark * (1 - (ptp if take_profit_activated else tslp) / 100)
                    if candle['low_price'] <= stop_price:
                        sell_price = stop_price
                        break
                
                if sell_price == 0: sell_price = trade['Signal_Price_sell']
                total_simulated_pnl += (sell_price - entry_price) * quantity

            if total_simulated_pnl > best_pnl:
                best_pnl = total_simulated_pnl
                best_params = {'tpp': tpp, 'tslp': tslp, 'ptp': ptp}

        original_pnl = trades_df['PnL'].sum()
        original_win_rate = (trades_df[trades_df['PnL'] > 0].shape[0] / len(trades_df)) * 100

        return {
            'best_params': best_params,
            'original_pnl': original_pnl,
            'optimized_pnl': best_pnl,
            'original_win_rate': original_win_rate,
            'trade_count': len(trades_df)
        }
    except Exception as e:
        print(f"Error in analysis engine (optimization): {e}")
        return { 'error': str(e) }

from skopt import gp_minimize
from skopt.space import Real, Integer
from skopt.utils import use_named_args

def run_full_strategy_optimization(BULLISH_MOMENTUM_PERC, BULLISH_WICK_PERC, TAKE_PROFIT_PERCENTAGES, TRAILING_STOP_LOSS_PERCENTAGES, PROFIT_TRAIL_PERCENTAGES):
    """
    Performs a Bayesian Optimization on BOTH buy and sell parameters to find the globally
    optimal strategy. This is computationally intensive.
    """
    try:
        con = sqlite3.connect(DB_PATH)
        candles_df = pd.read_sql_query("SELECT * FROM CandleStick_Data_WebSocket WHERE is_final_candle = 1", con)
        con.close()

        if candles_df.empty:
            return {'error': 'No final candle data available to run optimization.'}

        candles_df['candle_start_time'] = pd.to_datetime(candles_df['candle_start_time'], unit='ms')
        candles_df = candles_df.sort_values(by=['symbol', 'candle_start_time'])

        # --- Define Search Space for Bayesian Optimization ---
        search_space = [
            Integer(1, 10, name='momentum_perc'),
            Real(0.1, 2.0, name='wick_perc'),
            Integer(1, 15, name='tpp'),
            Integer(1, 10, name='tslp'),
            Real(0.5, 5.0, name='ptp')
        ]

        all_results = []

        @use_named_args(search_space)
        def objective(**params):
            momentum_perc = params['momentum_perc']
            wick_perc = params['wick_perc']
            tpp = params['tpp']
            tslp = params['tslp']
            ptp = params['ptp']

            trade_log = []
            pnl_over_time = []

            for symbol, symbol_candles in candles_df.groupby('symbol'):
                in_position = False
                entry_price = 0
                entry_time = None
                high_water_mark = 0
                take_profit_activated = False

                for i in range(len(symbol_candles)):
                    if in_position:
                        current_candle = symbol_candles.iloc[i]
                        high_water_mark = max(high_water_mark, current_candle['high_price'])

                        if not take_profit_activated and high_water_mark >= entry_price * (1 + tpp / 100):
                            take_profit_activated = True

                        stop_price = high_water_mark * (1 - (ptp if take_profit_activated else tslp) / 100)

                        if current_candle['low_price'] <= stop_price:
                            sell_price = stop_price
                            pnl = sell_price - entry_price
                            trade_log.append({'pnl': pnl})
                            pnl_over_time.append(pnl)
                            in_position = False
                        continue

                    if i > 0:
                        candle_to_check = symbol_candles.iloc[i-1]

                        close_open_perc = ((candle_to_check['close_price'] - candle_to_check['open_price']) / candle_to_check['open_price']) * 100 if candle_to_check['open_price'] != 0 else 0
                        high_close_perc = ((candle_to_check['high_price'] - candle_to_check['close_price']) / candle_to_check['high_price']) * 100 if candle_to_check['high_price'] != 0 else 0

                        if close_open_perc >= momentum_perc and high_close_perc <= wick_perc:
                            in_position = True
                            entry_price = candle_to_check['close_price']
                            entry_time = candle_to_check['candle_start_time']
                            high_water_mark = entry_price
                            take_profit_activated = False

            total_pnl = sum(p.get('pnl', 0) for p in trade_log)
            
            # We want to maximize PnL, so we return the negative of it
            return -total_pnl

        # Run Bayesian Optimization
        result = gp_minimize(
            func=objective,
            dimensions=search_space,
            n_calls=100, # Number of iterations
            random_state=42,
            n_jobs=-1
        )

        # Format the results to match the expected output
        best_params_list = result.x
        best_pnl = -result.fun

        # Create a detailed result list for all tested combinations
        for i in range(len(result.x_iters)):
            params = result.x_iters[i]
            pnl = -result.func_vals[i]
            
            # You can calculate other metrics here if needed, but it would require re-running the simulation
            # For now, we'll just report the PnL and parameters for each run.
            all_results.append({
                'pnl': pnl,
                'win_rate': 0, # Placeholder
                'max_drawdown': 0, # Placeholder
                'trade_count': 0, # Placeholder
                'momentum_perc': params[0],
                'wick_perc': params[1],
                'tpp': params[2],
                'tslp': params[3],
                'ptp': params[4]
            })
        
        all_results.sort(key=lambda x: x['pnl'], reverse=True)


        original_trades = _get_completed_trades()
        original_pnl = original_trades['PnL'].sum() if original_trades is not None and not original_trades.empty else 0

        return {
            'summary': {
                'best_pnl': best_pnl,
                'original_pnl': original_pnl,
                'best_params': {
                    'buy': {'momentum': best_params_list[0], 'wick': best_params_list[1]},
                    'sell': {'tpp': best_params_list[2], 'tslp': best_params_list[3], 'ptp': best_params_list[4]}
                }
            },
            'details': all_results
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return { 'error': str(e) }
