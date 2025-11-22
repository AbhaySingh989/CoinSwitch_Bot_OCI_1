
import time
import logging
import threading
import json
from config import (
    DB_NAME, LEVERAGE, ORDER_AMOUNT, 
    BUY_SIGNAL_EXECUTION_THRESHOLD_SECONDS, 
    SELL_ORDER_STATUS_MONITORING_TIME, DRY_RUN
)
from futures import ApiTradingClient
from database_handler import DatabaseHandler

logger = logging.getLogger(__name__)

def execute_buy_signal(signal_id, symbol, api_client: ApiTradingClient, price: float):
    """
    Spawns a new thread to execute a buy signal to avoid blocking the main application.
    Passes database connection info and the trigger price instead of the connection object itself.
    """
    thread = threading.Thread(target=lambda: _execute_buy_signal_task(
        signal_id, symbol, api_client, price
    ))
    thread.start()

def _execute_buy_signal_task(signal_id, symbol, api_client: ApiTradingClient, price: float):
    """
    The core task for executing a buy order. This runs in a separate thread.
    It creates its own database connection to ensure thread safety.
    """
    db_handler = DatabaseHandler(DB_NAME)
    db_handler.connect()
    try:
        if DRY_RUN:
            logger.info(f"DRY RUN: Simulating BUY order for Signal ID: {signal_id} for symbol {symbol}")
            
            # In DRY_RUN, assume ORDER_AMOUNT is the target amount to spend.
            # Calculate order_quantity based on ORDER_AMOUNT and price.
            if price == 0:
                logger.error(f"DRY RUN: Cannot calculate order quantity because signal price is zero for Signal ID: {signal_id}.")
                db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Execution_Failed', 'Signal_Reason': 'DRY_RUN: Price is zero'})
                return
            
            raw_order_quantity = (ORDER_AMOUNT * LEVERAGE) / price # Assume full ORDER_AMOUNT is available
            order_quantity = int(raw_order_quantity * 1000) / 1000.0
            logger.info(f"DRY RUN: Calculated Order Quantity: {order_quantity} based on ORDER_AMOUNT {ORDER_AMOUNT} and Price {price}")

            # Simulate successful execution
            execution_details = {
                'Position_Status': 'Open',
                'Filled_Quantity': order_quantity,
                'CoinSwitch_TransactionStatus': 'SIMULATED',
                'CoinSwitch_TransactionPrice': price,
                'CoinSwitch_TransactionTime': int(time.time()),
                'Exchange_Order_ID': f"DRY_RUN_BUY_{signal_id}_{int(time.time())}",
                'High_Water_Mark': price
            }
            db_handler.update_signal_execution_details(signal_id, execution_details)
            logger.info(f"DRY RUN: Simulated BUY order for Signal ID: {signal_id} successfully.")
            return

        # --- LIVE TRADING LOGIC (Existing code) ---
        start_time = time.time()
        logger.info(f"Starting execution for Signal ID: {signal_id} for symbol {symbol}")

        def time_is_up():
            return time.time() - start_time > BUY_SIGNAL_EXECUTION_THRESHOLD_SECONDS

        # 1. Pre-flight Check: Get Wallet Balance
        balance_response = api_client.futures_wallet_balance(params={"exchange": "EXCHANGE_2"})
        logger.info(f"Wallet Balance Response for Signal ID {signal_id}: {balance_response}")

        # Safely navigate the nested structure of the wallet balance response
        try:
            # Get the list of asset balances
            asset_balances = balance_response.get('data', {}).get('base_asset_balances', [])
            if not asset_balances:
                raise ValueError("'base_asset_balances' is empty or not found")

            # Find the USDT balance, which is the quote currency for trading
            usdt_balance_info = next((item for item in asset_balances if item.get('base_asset') == 'USDT'), None)
            if not usdt_balance_info:
                raise ValueError("USDT balance information not found in the response")

            # Get the available balance string
            available_balance_str = usdt_balance_info.get('balances', {}).get('total_available_balance')
            if available_balance_str is None:
                raise ValueError("'total_available_balance' key not found in balances")

            # Convert the balance to a float for calculations
            available_balance = float(available_balance_str)

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to parse wallet balance for Signal ID: {signal_id}. Error: {e}. Response: {balance_response}")
            db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Execution_Failed'})
            return
        final_order_amount = min(ORDER_AMOUNT * LEVERAGE, available_balance * LEVERAGE)
        
        if price == 0:
            logger.error(f"Cannot calculate order quantity because signal price is zero for Signal ID: {signal_id}.")
            db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Execution_Failed'})
            return
            
        raw_order_quantity = final_order_amount / price
        # Round down to 3 decimal places to meet exchange precision requirements
        order_quantity = int(raw_order_quantity * 1000) / 1000.0
        logger.info(f"Available Balance: {available_balance}, Final Order Amount: {final_order_amount}, Raw Quantity: {raw_order_quantity}, Rounded Quantity: {order_quantity}")

        if time_is_up():
            logger.warning(f"Execution timed out after wallet balance check for Signal ID: {signal_id}.")
            db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Critical_Error_Reconciliation_Needed'})
            return

        # 2. Set Leverage
        leverage_payload = {"symbol": symbol, "leverage": LEVERAGE, "exchange": "EXCHANGE_2"}
        leverage_response = api_client.futures_update_leverage(payload=leverage_payload)

        # A successful response contains the 'data' key. An error response will not.
        if 'data' not in leverage_response:
            logger.error(f"Failed to set leverage for Signal ID: {signal_id}. Response: {leverage_response}")
            db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Execution_Failed'})
            return

        logger.info(f"Successfully set leverage to {LEVERAGE}x for Signal ID: {signal_id}")

        if time_is_up():
            logger.warning(f"Execution timed out after setting leverage for Signal ID: {signal_id}.")
            db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Critical_Error_Reconciliation_Needed'})
            return

        # 3. Place Market Buy Order
        order_payload = {
            "symbol": symbol, "side": "BUY", "order_type": "MARKET",
            "quantity": order_quantity, "exchange": "EXCHANGE_2"
        }
        order_response = api_client.futures_create_order(payload=order_payload)

        # As per docs, a successful placement has a 'data' object with 'order_id'
        order_data = order_response.get('data')
        if not order_data or 'order_id' not in order_data:
            logger.error(f"Failed to place order for Signal ID: {signal_id}. Response: {order_response}")
            db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Execution_Failed'})
            return

        order_id = order_data['order_id']
        logger.info(f"Successfully placed order for Signal ID: {signal_id}. Order ID: {order_id}.")
        db_handler.update_signal_execution_details(signal_id, {'Exchange_Order_ID': order_id})

        # 4. Monitor Order Status
        while not time_is_up():
            time.sleep(1)
            status_response = api_client.futures_get_order_by_id(params={"order_id": order_id})

            # As per docs, the order details are nested in response['data']['order']
            order_details = status_response.get('data', {}).get('order')
            if not order_details:
                logger.warning(f"Could not get order details for Order ID: {order_id}. Retrying... Response: {status_response}")
                continue

            order_status = order_details.get('status')
            logger.info(f"Polling status for Order ID: {order_id}. Current status: {order_status}")

            # Handle the final 'EXECUTED' state
            if order_status == 'EXECUTED':
                logger.info(f"Order {order_id} is EXECUTED.")
                execution_price = order_details.get('avg_execution_price')
                execution_details = {
                    'Position_Status': 'Open',
                    'Filled_Quantity': order_details.get('exec_quantity'),
                    'CoinSwitch_TransactionStatus': 'EXECUTED',
                    'CoinSwitch_TransactionPrice': execution_price,
                    'CoinSwitch_TransactionTime': int(time.time()),
                    'High_Water_Mark': execution_price
                }
                db_handler.update_signal_execution_details(signal_id, execution_details)
                return # Exit loop on final status

            # Handle the final 'PARTIALLY_EXECUTED' state
            if order_status == 'PARTIALLY_EXECUTED':
                logger.info(f"Order {order_id} is PARTIALLY_EXECUTED.")
                execution_price = order_details.get('avg_execution_price')
                db_handler.update_signal_execution_details(signal_id, {
                    'Position_Status': 'Partially_Filled',
                    'Filled_Quantity': order_details.get('exec_quantity'),
                    'CoinSwitch_TransactionStatus': 'PARTIALLY_EXECUTED',
                    'CoinSwitch_TransactionPrice': execution_price,
                    'CoinSwitch_TransactionTime': int(time.time()),
                    'High_Water_Mark': execution_price
                })
                return # Exit loop on final status

            # Handle the final 'CANCELLED' state
            if order_status == 'CANCELLED':
                logger.warning(f"Order {order_id} was CANCELLED on the exchange.")
                db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Canceled'})
                return # Exit loop on final status

            # If status is RAISED or CANCELLATION_RAISED, continue polling
            if order_status in ['RAISED', 'CANCELLATION_RAISED']:
                continue

        # 5. Timeout Logic
        logger.warning(f"Execution timed out for Order ID: {order_id}. Performing final status check.")
        final_status_response = api_client.futures_get_order_by_id(params={"order_id": order_id})
        final_order_details = final_status_response.get('data', {}).get('order')

        if not final_order_details:
            logger.critical(f"CRITICAL: Could not get final status for Order ID: {order_id}. Manual reconciliation needed.")
            db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Critical_Error_Reconciliation_Needed'})
        else:
            final_status = final_order_details.get('status')
            if final_status in ['RAISED', 'CANCELLATION_RAISED']:
                logger.critical(f"CRITICAL: Order {order_id} was still {final_status} on timeout. Manual reconciliation needed.")
                db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Critical_Error_Reconciliation_Needed'})

    except Exception as e:
        logger.error(f"CRITICAL ERROR in execution thread for Signal ID {signal_id}: {e}", exc_info=True)
        db_handler.update_signal_execution_details(signal_id, {
            'Position_Status': 'Execution_Failed',
            'Signal_Reason': f'Thread Crash: {e}'
        })
    finally:
        # Ensure the thread-specific database connection is always closed.
        db_handler.close()

def execute_sell_signal(signal_id, symbol, api_client: ApiTradingClient, position_id: str, price: float):
    """
    Spawns a new thread to execute a sell signal to avoid blocking the main application.
    """
    thread = threading.Thread(target=lambda: _execute_sell_signal_task(
        signal_id, symbol, api_client, position_id, price
    ))
    thread.start()

def _execute_sell_signal_task(signal_id, symbol, api_client: ApiTradingClient, position_id: str, price: float):
    """
    The core task for executing a sell order. This runs in a separate thread.
    """
    db_handler = DatabaseHandler(DB_NAME)
    db_handler.connect()
    try:
        if DRY_RUN:
            logger.info(f"DRY RUN: Simulating SELL order for Signal ID: {signal_id} for Position ID: {position_id}")
            
            # Get the original buy signal's Filled_Quantity
            original_buy_signal = db_handler.get_active_position(position_id)
            simulated_filled_quantity = original_buy_signal['Filled_Quantity'] if original_buy_signal else 0

            # Simulate successful execution
            execution_details = {
                'Position_Status': 'Closed',
                'Filled_Quantity': simulated_filled_quantity, 
                'CoinSwitch_TransactionStatus': 'SIMULATED',
                'CoinSwitch_TransactionPrice': price, # Use the price that triggered the sell signal
                'CoinSwitch_TransactionTime': int(time.time()),
                'Exchange_Order_ID': f"DRY_RUN_SELL_{signal_id}_{int(time.time())}"
            }
            db_handler.update_signal_execution_details(signal_id, execution_details)
            logger.info(f"DRY RUN: Simulated SELL order for Signal ID: {signal_id} successfully.")
            return

        # --- LIVE TRADING LOGIC (Existing code) ---
        logger.info(f"Starting SELL execution for Signal ID: {signal_id} for Position ID: {position_id}")

        # 1. Get the active position to find out the quantity to sell
        active_position = db_handler.get_active_position(position_id)

        if not active_position or not active_position['Filled_Quantity']:
            logger.critical(f"CRITICAL_ERROR_SELLQUANTITY_NULL: No active position or zero Filled_Quantity found for Position ID: {position_id}. Cannot execute sell signal.")
            db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Critical_Error_SellQuantity_Null'})
            return

        sell_quantity = active_position['Filled_Quantity']
        logger.info(f"Found active position. Sell Quantity: {sell_quantity} for Position ID: {position_id}")

        # 2. Place Market Sell Order
        order_payload = {
            "symbol": symbol,
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": sell_quantity,
            "exchange": "EXCHANGE_2"
        }
        order_response = api_client.futures_create_order(payload=order_payload)

        order_data = order_response.get('data')
        if not order_data or 'order_id' not in order_data:
            logger.error(f"Failed to place SELL order for Signal ID: {signal_id}. Response: {order_response}")
            db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Execution_Failed'})
            return

        order_id = order_data['order_id']
        logger.info(f"Successfully placed SELL order for Signal ID: {signal_id}. Order ID: {order_id}.")
        db_handler.update_signal_execution_details(signal_id, {'Exchange_Order_ID': order_id})

        # 3. Monitor Order Status after a delay
        logger.info(f"Waiting for {SELL_ORDER_STATUS_MONITORING_TIME} seconds before checking SELL order status for Order ID: {order_id}.")
        time.sleep(SELL_ORDER_STATUS_MONITORING_TIME)

        status_response = api_client.futures_get_order_by_id(params={"order_id": order_id})
        order_details = status_response.get('data', {}).get('order')

        if not order_details:
            logger.critical(f"CRITICAL_ERROR_SELL_ORDER: Could not get final status for SELL Order ID: {order_id}. Manual reconciliation needed. Response: {status_response}")
            db_handler.update_signal_execution_details(signal_id, {'Position_Status': 'Critical_Error_Sell_Order'})
            return

        order_status = order_details.get('status')
        logger.info(f"Final status check for SELL Order ID: {order_id}. Status: {order_status}")

        if order_status == 'EXECUTED':
            logger.info(f"SELL Order {order_id} is EXECUTED.")
            execution_details = {
                'Position_Status': 'Closed',
                'Filled_Quantity': order_details.get('exec_quantity'),
                'CoinSwitch_TransactionStatus': 'EXECUTED',
                'CoinSwitch_TransactionPrice': order_details.get('avg_execution_price'),
                'CoinSwitch_TransactionTime': int(time.time())
            }
            db_handler.update_signal_execution_details(signal_id, execution_details)
        else:
            logger.error(f"CRITICAL_ERROR_SELL_ORDER: SELL Order {order_id} status was '{order_status}', not 'EXECUTED'. Manual reconciliation needed.")
            execution_details = {
                'Position_Status': 'Critical_Error_Sell_Order',
                'Filled_Quantity': order_details.get('exec_quantity'),
                'CoinSwitch_TransactionStatus': order_status,
                'CoinSwitch_TransactionPrice': order_details.get('avg_execution_price'),
                'CoinSwitch_TransactionTime': int(time.time())
            }
            db_handler.update_signal_execution_details(signal_id, execution_details)

    except Exception as e:
        logger.error(f"CRITICAL ERROR in sell execution thread for Signal ID {signal_id}: {e}", exc_info=True)
        db_handler.update_signal_execution_details(signal_id, {
            'Position_Status': 'Execution_Failed',
            'Signal_Reason': f'Thread Crash: {e}'
        })
    finally:
        db_handler.close()
