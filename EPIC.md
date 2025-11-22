# Epic: Real-time Crypto Trading Automation with Signal Generation and Order Execution

**Epic Owner:** Super Boss
**Date:** July 25, 2025

**Description:** This epic aims to build a comprehensive automated cryptocurrency trading system. It will establish a robust pipeline for real-time candlestick data ingestion and storage in a local SQLite database. Leveraging this data, the system will generate buy and sell signals based on predefined technical logic. Crucially, upon signal generation, the system will automatically execute corresponding buy and sell orders via a chosen cryptocurrency exchange's API, moving beyond mere notifications to active trading.

**Source:**
* For candlestick data use WebSocket API refer to "C:\Abhay\CoinSwitch_Bot\Reference Codes\Websocket_logic.py" file
* For trade, and order management use REST API refer to "C:\Abhay\CoinSwitch_Bot\Reference Codes\RestAPI_Logic.py" file
* For API keys/credentials use .env file

---

## Component 1: Real-time Candlestick Data Ingestion and Storage
Status: Complete

**Goal:** To reliably connect to a cryptocurrency exchange's WebSocket API, receive real-time candlestick updates, and store them persistently in a local SQLite database, providing the foundational data for signal generation.

### User Stories:

#### US1.1: As a system, I want to establish and maintain a stable WebSocket connection to the cryptocurrency exchange's API so that I can receive continuous real-time candlestick data.
**Description:** Implement the core logic for connecting to the WebSocket endpoint, handling initial handshake, and ensuring the connection remains active.
**Acceptance Criteria:**
* The system successfully connects to the specified WebSocket API endpoint.
* Automatic reconnection logic is implemented to recover from unexpected disconnections with exponential backoff.
* Connection status (connected/disconnected) can be monitored and logged.

**Tasks (Examples):**
* Implement WebSocket connection and error handling.
* Develop robust reconnection strategy with backoff.

Status: Complete

#### US1.2: As a system, I want to subscribe to specific cryptocurrency pairs and candlestick timeframes (e.g., BTCUSDT 5-minute) via the WebSocket so that I receive only relevant data for trading.
**Description:** Implement the subscription messages required by the exchange's WebSocket API to receive candlestick data for chosen assets and intervals.
**Acceptance Criteria:**
* The system sends correct subscription messages for configured symbols (e.g., BTCUSDT) and timeframes (e.g., 5m).
* Only data corresponding to the subscribed pairs/timeframes is received.
* The list of symbols and timeframes is configurable (e.g., via a JSON configuration file).
**Tasks (Examples):**
* Parse configuration for symbols and timeframes.
* Construct WebSocket subscription messages according to exchange API docs, refer source mentioned in **Source Section**.
* Handle subscription confirmation/errors.
Status: Complete

#### US1.3: As a system, I want to parse raw incoming WebSocket messages into a structured candlestick data format so that it can be processed and stored for signal generation.
**Description:** Develop a parser that can extract the (symbol, candle_start_time, candle_end_time, server_timestamp, open_price, high_price, low_price, close_price, volume, quote_asset_volume, interval, is_final_candle)

* Exchange Output:
["FETCH_CANDLESTICK_CS_PRO",{"o":"118824.7","h":"118892","l":"118824.7","c":"118830.7","v":"67.84","q":"8063152.3621","s":"BTCUSDT","i":"5","x":false,"t":1753387800000,"T":1753388099999,"ts":1753387963037}]

* How to read and store it:
(symbol, candle_start_time, candle_end_time, server_timestamp, open_price, high_price, low_price, close_price, volume, quote_asset_volume, interval, is_final_candle)
        VALUES (:s, :t, :T, :ts, :o, :h, :l, :c, :v, :q, :i, :x)

**Acceptance Criteria:**
* Successfully extracts all specified fields from a sample raw WebSocket message.
* Converts Time to a standardized timestamp format IST dd-mmm-yyyy hh:mm:ss (e.g., 26-Jul-2025 00:20:25).
* Converts price fields (Open, Close, Current, High, Low) to appropriate numeric types (e.g., float).
* Handles Candle Status (e.g., "Open", "Close") correctly.
* Gracefully handles malformed or incomplete messages, logging errors.
**Tasks (Examples):**
* Define an internal data model/object for a candlestick.
* Implement JSON parsing and data extraction logic.
* Write unit tests for the parsing module with various message types.
Status: Complete

#### US1.4: As a system, I want to robustly identify and persist finalized candles to ensure no data is lost from high-frequency streams.
**Description:** Implement a resilient finalization mechanism that stores incoming candlestick updates in an in-memory cache. A candle is considered "finalized" and ready for persistence under two conditions:
1.  **Explicitly:** When a message with an `"x": true` flag is received.
2.  **Implicitly:** When a message with a new, later `candle_start_time` arrives, which proves the previous candle has ended.

This dual approach ensures data integrity and prevents data loss even if the final message (`"x": true`) from the stream is missed.

**Acceptance Criteria:**
*   All real-time updates for an open candle are stored in an in-memory cache, tracking the latest data for each symbol.
*   The system persists a candle to the database if it receives an explicit `"x": true` flag.
*   **The system infers that a candle is finalized and persists it if it receives a message with a `candle_start_time` that is later than the start time of the currently cached candle.**
*   When a candle is finalized implicitly, the last known data payload from that candle is promoted to "final" and stored.
*   The in-memory cache is correctly managed, clearing old data after finalization and tracking the new candle's data. (Fixed a memory leak where the cache was not cleared on implicit finalization).
*   Database write operations are non-blocking to the WebSocket listener to prevent data loss.
Status: Complete

---

## Component 1.5: Scalable Multi-Pair Candlestick Data Ingestion
Status: Complete

**Goal:** To evolve the existing data ingestion component to concurrently manage WebSocket subscriptions for multiple cryptocurrency pairs, validating that the system architecture can handle increased data volume and processing load efficiently.

### User Stories:

#### US1.5.1: As a developer, I want to configure a list of multiple cryptocurrency pairs for data ingestion so that the system can dynamically subscribe to all specified symbols.
**Description:** Modify the system to read a list of target cryptocurrency pairs from a central configuration file (`config.py`). This removes hardcoded single-symbol logic and allows for easy scaling of subscriptions.
**Acceptance Criteria:**
*   The system reads a list of strings (e.g., `['BTCUSDT', 'ETHUSDT', 'XRPUSDT']`) from `config.py`.
*   The application fails gracefully with a clear error message if the configuration is missing or malformed.
*   The list of symbols is passed correctly to the WebSocket connection manager.

#### US1.5.2: As a system, I want to subscribe to all configured cryptocurrency pairs over a single WebSocket connection using a batching mechanism to efficiently manage subscriptions.
**Description:** Implement the logic to send subscription messages for multiple pairs over one connection. To avoid potential rate-limiting by the exchange, the subscriptions should be sent in small batches with a short delay.
**Acceptance Criteria:**
*   The system establishes a single, persistent WebSocket connection.
*   It iterates through the list of pairs from the configuration and sends a `subscribe` event for each.
*   Subscriptions are sent in batches (e.g., 5 pairs at a time) with a configurable delay between batches.
*   The system correctly handles subscription confirmation/error responses from the exchange for each pair.

#### US1.5.3: As a system, I want to process and cache incoming data for multiple symbols concurrently so that the real-time data for each pair is handled independently.
**Description:** Re-architect the in-memory cache and data processing pipeline to manage data streams from multiple symbols. The best approach is to use a dictionary (hash map) for the in-memory cache, where each key is the symbol name (e.g., 'BTCUSDT'). This ensures data for one symbol does not interfere with another and allows for efficient lookups, which is critical for the future Signal Generation component.
**Acceptance Criteria:**
*   The in-memory cache is structured as a dictionary, with each symbol as a key.
*   Incoming WebSocket messages are parsed, and the data is routed to the correct symbol's cache.
*   Finalized candles from different symbols are independently and correctly passed to the database handler.

#### US1.5.4: As a system, I want to validate that the data ingestion for multiple pairs is performant and maintains data integrity.
**Description:** Implement checks and logging to ensure the scaled-up ingestion process meets performance and reliability standards.
**Acceptance Criteria:**
*   The average time from receiving a raw message to storing the finalized candle in the database is measured and logged.
*   For a given symbol and interval (e.g., 'BTCUSDT' at 1-minute), the number of candles stored in the database matches the expected count for the session duration (e.g., a 5-minute run results in 5 candles).
*   A mechanism is in place to verify that no incoming WebSocket messages are dropped or missed.

#### US1.5.5: As a system, I want to handle subscription or data errors for a single pair in isolation so that an issue with one stream does not disrupt others.
**Description:** Implement robust error handling at the individual symbol level. If a subscription fails, or a corrupt message is received for one pair, the system should log the specific error and attempt to re-subscribe to only that pair without affecting the data flow for other active subscriptions.
**Acceptance Criteria:**
*   An error related to a single symbol (e.g., subscription failure) is logged with the symbol's name.
*   The system continues to process data for all other healthy subscriptions without interruption.
*   An automated re-subscription attempt is made for the failed symbol using an appropriate backoff strategy.

---

## Component 2: Buy/Sell Signal Generation Logic
Status: Complete

**Goal:** To analyze the stored candlestick data in real-time to identify and generate precise buy and sell signals based on the defined trading logic.

### User Stories:

#### US2.1: As a system, I want to retrieve historical closed candlestick data from the SQLite database efficiently so that I can perform calculations for signal generation.
**Description:** Implement functions to query the SQLite database for a sequence of closed candlesticks, ordered by time, for a given crypto pair and interval. This is primarily used to get the `Close` price of the previous candle for sell-side logic.
**Acceptance Criteria:**
*   Queries return the correct data subset based on symbol, timeframe, and time range.
*   Data is retrieved in the correct chronological order.
*   Query performance is acceptable for real-time signal processing requirements.
**Tasks (Examples):**
*   Develop optimized SELECT SQL queries.
*   Implement data fetching functions that return structured candlestick objects.

#### US2.2: As a system, I want to calculate the (Close - Open)% for any given closed candlestick so that it can be used in the Buy Entry Criteria.
**Description:** Create a utility function to compute the percentage change from the Open to the Close price of a candlestick.
**Acceptance Criteria:**
*   Calculates `((Close - Open) / Open) * 100` correctly.
*   Returns a float value.
*   Handles edge cases (e.g., Open price being zero, preventing division by zero).
**Tasks (Examples):**
*   Implement `calculate_close_open_percentage` function.
*   Write comprehensive unit tests for the calculation.

#### US2.3: As a system, I want to calculate the (High - Close)% for any given closed candlestick so that it can be used in the Buy Entry Criteria.
**Description:** Create a utility function to compute the percentage difference between the High and Close price of a candlestick.
**Acceptance Criteria:**
*   Calculates `((High - Close) / High) * 100` correctly.
*   Returns a float value.
*   Handles edge cases (e.g., High price being zero).
**Tasks (Examples):**
*   Implement `calculate_high_close_percentage` function.
*   Write comprehensive unit tests for the calculation.

#### US2.3.1: As a system, I want to create a dedicated database table to store and manage trading signals and their lifecycle.
**Description:** Implement a new table named `Signals` in the SQLite database to persist all generated buy/sell signals, track their status, and link them to exchange order details. This provides a durable record of all trading activity.

**Column Definitions & Update Logic:**

*   **Signal_ID** (INTEGER, PRIMARY KEY, AUTOINCREMENT):
    *   **Definition:** A unique identifier for each row in the table.
    *   **Update Logic:** Automatically generated by the database upon insertion. Never updated.
*   **Unique_PositionID** (TEXT, NOT NULL):
    *   **Definition:** A unique ID (e.g., UUID) that links a buy signal and its corresponding sell signal together, representing a single complete trade or position.
    *   **Update Logic:** Generated once when a `Buy` signal is created. The same ID is used for the corresponding `Sell` signal to close the position.
*   **Symbol** (TEXT, NOT NULL):
    *   **Definition:** The cryptocurrency pair for the signal (e.g., 'BTCUSDT').
    *   **Update Logic:** Set when the signal is first inserted. Never updated.
*   **Signal** (TEXT, NOT NULL):
    *   **Definition:** The type of signal, either 'Buy' or 'Sell'.
    *   **Update Logic:** Set when the signal is first inserted. Never updated.
*   **Signal_Price** (REAL, NOT NULL):
    *   **Definition:** The price at which the signal was triggered.
    *   **Update Logic:** Set when the signal is first inserted. Never updated.
*   **Signal_Timestamp** (INTEGER, NOT NULL):
    *   **Definition:** The timestamp (Unix epoch) when the signal was generated.
    *   **Update Logic:** Set when the signal is first inserted. Never updated.
*   **Trigger_Candle_Timestamp** (INTEGER):
    *   **Definition:** The start time of the candlestick that triggered the signal.
    *   **Update Logic:** Set when the signal is first inserted. Never updated.
*   **Signal_Reason** (TEXT):
    *   **Definition:** The specific condition that triggered the signal (e.g., 'Bullish Momentum', 'Stop-loss triggered').
    *   **Update Logic:** Set when the signal is first inserted. Never updated.
*   **Position_Status** (TEXT, NOT NULL):
    *   **Definition:** The current state of the position in the trading lifecycle. Allowed values: `Pending_Execution`, `Open`, `Partially_Filled`, `Closed`, `Execution_Failed`, `Canceled`.
    *   **Update Logic:** 
        *   Starts as `Pending_Execution` when a signal is first generated.
        *   Updated to `Open` after a buy order is successfully executed by the exchange.
        *   Updated to `Partially_Filled` if the exchange order is only partially completed.
        *   Updated to `Closed` after a sell order is successfully executed.
        *   Updated to `Execution_Failed` if the exchange order fails.
        *   Updated to `Canceled` if the order is canceled on exchange.

*   **Filled_Quantity** (REAL):
    *   **Definition:** The actual quantity of the asset that was successfully bought or sold by the exchange.
    *   **Update Logic:** Set to `NULL` initially. Updated when an order is fully or partially EXECUTED.
*   **Exchange_Order_ID** (TEXT):
    *   **Definition:** The unique order ID returned by the exchange after placing an order.
    *   **Update Logic:** Set to `NULL` on initial signal insertion. Updated with the actual order ID once the exchange confirms the order.
*   **CoinSwitch_TransactionStatus** (TEXT):
    *   **Definition:** The final status of the transaction as reported by the exchange (e.g., 'EXECUTED', 'PARTIALLY_EXECUTED', 'REJECTED').
    *   **Update Logic:** Set to `NULL` initially. Updated when the final status of the exchange order is known.
*   **CoinSwitch_TransactionPrice** (REAL):
    *   **Definition:** The actual average price at which the order was EXECUTED by the exchange.
    *   **Update Logic:** Set to `NULL` initially. Updated when the order is EXECUTED.
*   **CoinSwitch_TransactionTime** (INTEGER):
    *   **Definition:** The timestamp (Unix epoch) when the transaction was completed on the exchange.
    *   **Update Logic:** Set to `NULL` initially. Updated when the order is EXECUTED.

**Acceptance Criteria:**
*   A new table named `Signals` is created in the `Crypto_Data.db` database with the specified schema.
*   The system can successfully insert and update signal records according to the defined logic.
*   The system can query this table to retrieve open positions or historical signals.

**Tasks (Examples):**
*   Write the `CREATE TABLE` SQL statement for the `Signals` table.
*   Implement `insert_signal`, `update_position_status`, and `get_open_position` functions in the database handler.

#### US2.4: As a system, I want to generate a "Buy Signal" for a specific pair only if there is no active position for that same pair.
**Description:** Implement the logic that evaluates the most recently closed candlestick against two conditions. A buy signal is only generated if the entry criteria are met AND the system is not already holding a position for that specific symbol.
*   **Entry Criteria 1:** `(Close - Open)% >= 4.00%`
*   **Entry Criteria 2:** `(High - Close)% <= 1.00%`
**Acceptance Criteria:**
*   A "Buy" signal is triggered only if both entry criteria are met for a closed candle.
*   A "Buy" signal is **NOT** generated for a symbol if an active position for that same symbol already exists.
*   The system can generate a buy signal for 'ETHUSDT' even if a position for 'BTCUSDT' is already active.
*   The signal includes the Symbol, Timestamp, and SignalType: 'BUY'.

#### US2.5: As a system, I want to manage active buy positions on a per-pair basis, tracking their entry price and time.
**Description:** Implement a state management mechanism to track open buy positions for each cryptocurrency pair independently. The ideal structure is an in-memory dictionary where the symbol (e.g., 'BTCUSDT') is the key. This allows the system to hold multiple positions concurrently across different pairs.
**Acceptance Criteria:**
*   When a "Buy Signal" is generated for a symbol, a corresponding "active position" record is created for that symbol's key.
*   The system can hold active positions for multiple pairs (e.g., BTCUSDT and ETHUSDT) at the same time.
*   The system can retrieve the `EntryPrice` and `EntryTime` for any active position using its symbol.
*   When a "Sell Signal" is generated for a symbol, that symbol's position is removed from the active tracking structure.

#### US2.6: As a system, I want to generate a "Sell Signal" for an active position based on real-time price updates or closed candle analysis.
**Description:** Implement logic to monitor for three distinct exit criteria for any symbol with an active position. The first two are checked in real-time on every price update, while the third is checked only at the end of a candle.
*   **Exit Criterion 1 (Real-time Stop-Loss):** The `Current Price` of the open candle drops 0.5% or more below the recorded `EntryPrice`. Logic: `Current Price <= (EntryPrice * 0.995)`.
*   **Exit Criterion 2 (Real-time Trend Reversal):** The `Current Price` of the open candle drops below the `Open Price` of the *previous* closed candle.
*   **Exit Criterion 3 (End-of-Candle Bearish):** The `Close Price` of the most recently finalized candle is lower than its `Open Price`.
**Acceptance Criteria:**
*   A "Sell" signal is triggered if **any** of the three exit criteria are met for a symbol with an active position.
*   Criteria 1 and 2 are evaluated on every incoming WebSocket message for symbols with active positions.
*   Criterion 3 is evaluated only once when a candle is finalized for a symbol with an active position.
*   The signal includes the Symbol, Timestamp, and SignalType: 'SELL'.
*   Once a sell signal is sent for a position, it is not sent again.

#### US2.7: As a system, I want to generate a real-time "Buy Signal" based on intra-candle price movement.
**Description:** Implement logic that evaluates the `Current Price` of the open candle in real-time. A buy signal is generated if the price increases significantly from the candle's open price, indicating strong bullish momentum.
*   **Entry Criterion 1:** `((Current Price - Open Price) / Open Price) * 100 >= 15.00%`

**Acceptance Criteria:**
*   A "Buy" signal is triggered only if the entry criterion is met for an open candle.
*   A "Buy" signal is **NOT** generated for a symbol if an active position for that same symbol already exists.
*   The system can generate a buy signal for 'ETHUSDT' even if a position for 'BTCUSDT' is already active.
*   The signal includes the Symbol, Timestamp, and SignalType: 'BUY'.

#### US2.8: As a trader, I want to use a Trailing Stop-Loss for open positions so that I can protect profits while allowing a trade to continue its upward trend.
**Description:** This feature introduces a dynamic stop-loss that automatically follows the price of an asset as it moves in a favorable direction. Instead of a fixed stop-loss price, the exit point is a percentage below the highest price the asset has reached since the position was opened (the "High Water Mark"). This allows the system to lock in gains and mitigate losses if the market trend reverses.

**Acceptance Criteria:**
*   A new configuration option, `TRAILING_STOP_LOSS_PERCENTAGE`, is available in `config.py` to define the trail percentage.
*   When a buy order is successfully filled, the system records the entry price as the initial "High Water Mark" for that position in the `Signals` table.
*   On every subsequent price update for an open position, the system checks if the current price is higher than the stored "High Water Mark". If it is, the "High Water Mark" is updated to the new current price.
*   A "Sell Signal" with the reason "Trailing Stop-Loss" is generated if the current price drops below the "High Water Mark" by the configured percentage.
*   The trailing stop-loss logic is evaluated as the primary exit condition before other stop-loss types.
*   If `TRAILING_STOP_LOSS_PERCENTAGE` is set to `0` or is not defined, the feature is disabled.

**Tasks (Examples):**
*   Add `TRAILING_STOP_LOSS_PERCENTAGE` to `config.py`.
*   Add a `High_Water_Mark` column to the `Signals` database table.
*   Update the `order_executor` to set the initial `High_Water_Mark` on trade entry.
*   Implement the core trailing stop-loss calculation and trigger logic in `signal_generator.py`.
*   Create a database handler function to efficiently update the `High_Water_Mark` for an active trade.

#### US2.9: As a trader, I want to use a multi-stage exit strategy that activates a tighter, profit-protecting trail after a trade has reached an initial profit target.
**Status: Superseded by US2.10**
**Description:** This feature enhances the existing exit logic by introducing a dynamic, two-stage trailing stop-loss system. The goal is to let profitable trades run while aggressively protecting gains once a certain threshold is met. The system will start with a standard, wider trailing stop-loss. Once the trade hits a configurable initial profit target, the system will switch to a second, tighter trailing stop-loss for the remainder of the trade's lifecycle.

**Acceptance Criteria:**
*   Two new configuration options are available in `config.py`: `TAKE_PROFIT_PERCENTAGE` (the initial profit target that triggers the switch) and `PROFIT_TRAIL_PERCENTAGE` (the new, tighter trail).
*   A new boolean field, `take_profit_activated`, is added to the `Signals` table to track the state of each position.
*   **Stage 1 (Before Activation):** For a new position, the system uses the original `TRAILING_STOP_LOSS_PERCENTAGE` for its exit logic.
*   **Activation:** When the `current_price` reaches `entry_price * (1 + TAKE_PROFIT_PERCENTAGE / 100)`, the `take_profit_activated` flag for that position is set to `True` in the database. The trade does not exit at this point.
*   **Stage 2 (After Activation):** Once the flag is `True`, the system uses two new exit criteria:
    1.  A "Profit Trail Stop" is calculated: `High_Water_Mark * (1 - PROFIT_TRAIL_PERCENTAGE / 100)`. A sell is triggered if the price drops below this.
    2.  A "Target Floor" is enforced: A sell is triggered if the price drops back below the initial `TAKE_PROFIT_PERCENTAGE` level.
*   The original `TRAILING_STOP_LOSS_PERCENTAGE` is ignored once the `take_profit_activated` flag is true.

#### US2.10: As a trader, I want to implement a multi-stage, tiered take-profit strategy so that I can let profits run while systematically tightening the stop-loss at different profit levels.
**Status: Complete**
**Description:** This feature replaces the previous two-stage exit strategy (US2.9) with a more granular, multi-stage system defined in the configuration. The bot will track the profit percentage of a trade and apply progressively tighter trailing stop-losses as the trade becomes more profitable, allowing for capturing significant gains during strong upward trends while protecting accumulated profits. User Story US2.9 is considered superseded by this implementation.

**Acceptance Criteria:**
*   A new configuration setting, `TAKE_PROFIT_STAGES`, is added to `config.py` to define the profit tiers as a list of tuples (e.g., `TAKE_PROFIT_STAGES = [(5, 4), (15, 7), (50, 10), (75, 15), (100, 20)]`), where each tuple represents `(activation_profit_percentage, profit_trail_percentage)`.
*   **Database Schema Change:** The existing `take_profit_activated` column in the `Signals` table must be modified from its original BOOLEAN type to an INTEGER or REAL type to store the percentage level of the highest activated profit stage (e.g., 5, 15, 50).
*   **Stage 0 (Initial State):** Before the first profit stage is reached, the exit logic uses the existing `TRAILING_STOP_LOSS_PERCENTAGE` from the config.
*   **Stage Activation:** When the `current_price` reaches a new, higher profit target defined in `TAKE_PROFIT_STAGES`, the `take_profit_activated` column for that position is updated to the corresponding activation profit percentage (e.g., if the 15% profit level is reached, the column is updated to `15`).
*   **Stage N (Active State):** The exit logic uses the `profit_trail_percentage` corresponding to the highest value stored in the `take_profit_activated` column. This check is performed against the position's `High_Water_Mark`.
*   The previous configuration variables `TAKE_PROFIT_PERCENTAGE` and `PROFIT_TRAIL_PERCENTAGE` are considered deprecated and are no longer used by the exit logic.

**Tasks (Examples):**
*   Add `TAKE_PROFIT_STAGES` to `config.py`.
*   Update `database_handler.py` to handle the modification of the `take_profit_activated` column schema upon initialization.
*   Update `signal_generator.py` to implement the multi-stage profit checking and exit logic.
*   Create or update a database handler function to update the `take_profit_activated` level with the integer value of the activated stage.


---

## Component 3: Exchange Order Execution
Status: Complete

**Goal:** To securely and reliably execute buy and sell orders on the cryptocurrency exchange via its API, triggered by generated signals, and manage their status.

### User Stories:

#### US3.1: As a developer, I want to securely authenticate with the exchange's trading API so that I can place and manage orders.
**Description:** Implement the necessary authentication mechanism (e.g., API key/secret, HMAC signing) required by the exchange's REST API for trading.
**Acceptance Criteria:**
* The system successfully authenticates with the exchange's trading API.
* Authentication credentials are never hardcoded and are handled securely.
* Authentication failures are logged and handled gracefully.
**Tasks (Examples):**
* Research exchange's REST API documentation for authentication.
* Implement API client with authentication logic.
* Test authentication with a simple endpoint (e.g., getting account balance).

#### US3.2: As a system, I want to execute a leveraged buy order using market price, ensuring the entire transactional process from signal to confirmed fill or cancellation completes within a strict time limit.
**Description:** Upon generating a "Buy Signal", the system must spawn an independent, asynchronous task to manage the order's lifecycle. This task must complete all steps—pre-flight checks, placing a market order, and monitoring for a order fill—before a master timeout expires. The process must be transactional, aborting if any prerequisite API call fails.

**Configuration (`config.py`):**
*   `LEVERAGE` (integer): The leverage to be applied (e.g., 10 for 10x).
*   `ORDER_AMOUNT` (float): The desired amount of quote currency (e.g., USDT) to use for an order *before* leverage.
*   `BUY_SIGNAL_EXECUTION_THRESHOLD_SECONDS` (integer) : The maximum time allowed from **signal generation** to a confirmed `'EXECUTED'` status from the exchange.


**Execution Flow & Acceptance Criteria:**

1.  **Signal Generation & Independent Task Creation:**
    *   The moment a "Buy Signal" is generated, the system spawns a new asynchronous task dedicated solely to this signal's execution.
    *   This task immediately starts a countdown for `BUY_SIGNAL_EXECUTION_THRESHOLD_SECONDS`. All subsequent steps must be completed within this window.

2.  **Transactional Pre-Flight Checks:**
    *   The task calls `futures_wallet_balance()` to get the current available balance. **If it fails,** the task aborts and updates the signal's `Position_Status` to `Execution_Failed`.
    *   The task determines the `final_order_amount` by taking the lesser of the configured `ORDER_AMOUNT` and the available wallet balance.

3.  **Leverage Application:**                                                                                             
    *   The system calls `futures_update_leverage()` to set the desired `LEVERAGE` for the target `symbol`. 
    *   **If the `futures_update_leverage()` call itself fails OR if the timer expires before a successful call can be made:**        
    *   The system must immediately stop the process for this signal.                                                 
    *   It updates the `Signals` table record `Position_Status` to `'Execution_Failed'`.

4.  **Order Placement:**                                                                                     
    *   The system attempts to call `futures_create_order()` with a `"MARKET"` buy for the `final_order_amount`.          
    *   **If the order placement call itself fails OR if the timer expires before a successful call can be made:**        
    *   The system must immediately stop the process for this signal.                                                 
    *   It updates the `Signals` table record `Position_Status` to `'Execution_Failed'`.                              
    *   **If the order is placed successfully within the time limit:**                                                    
    *   The system logs the `order_id` and updates the `Exchange_Order_ID` in the `Signals` table and updates all the relevant columns in `Signals` table as per US2.3.1 


5.  **Monitoring, Reconciliation, and Timeout:**
    *   The task begins polling `futures_get_order_by_id()` to determine the order's status. The polling interval should be 1s.
    *   **Success:** If the order status becomes `EXECUTED` at any point, the process is complete. The `Signals` table is updated (`Position_Status` -> `'Open'`, `Filled_Quantity` recorded, update the other relevant columns as per user story US 2.3.1), and the task terminates.
    *   **Partial Fill Detection:** If the status becomes `PARTIALLY_EXECUTED`, the system immediately updates the `Signals` table (`Position_Status` -> `'Partially_Filled'`, `Filled_Quantity` -> current EXECUTED amount) and continues monitoring.
    *   **Timeout Logic:** When the `BUY_SIGNAL_EXECUTION_THRESHOLD_SECONDS` timer expires, the system performs one final status check on the order:
        *   **Case A: Final status is `RAISED`, `CANCELLATION_RAISED`, or cannot be determined.** The system must **NOT** attempt to cancel. This is a critical safety measure.
            *   The `Position_Status` in the `Signals` table is updated to **`'Critical_Error_Reconciliation_Needed'`**.
            *   A detailed error is logged, and the issue is escalated for **manual human intervention**.
  

#### US3.3: As a system, I want to place sell orders based on the actual `Filled_Quantity` of a position to prevent exchange errors and orphaned assets.
**Description:** When generating a "Sell Signal" for an active position, the order execution module must first retrieve the `Filled_Quantity` from the corresponding `Buy` or `Partially_Filled` signal in the `Signals` table. The subsequent market sell order must be placed for this exact quantity, a ensuring the system only attempts to sell assets it verifiably owns. The system must spawn an independent, asynchronous task to manage the order's lifecycle which pertains to placing a sell order and onetime order status monitoring after a lag of 15 seconds.

**Configuration (`config.py`):**
*   `SELL_ORDER_STATUS_MONITORING_TIME` (integer) : This is the time post which the system would make a Get order status call for the sell order placed to confirm the order status  `'EXECUTED'` from the exchange.

**Execution Flow & Acceptance Criteria:**

1.  **Signal Generation & Independent Task Creation:**
    *   The moment a "Sell Signal" is generated, the system spawns a new asynchronous task dedicated solely to this signal's execution.
    *   This task immediately starts a countdown for `SELL_ORDER_STATUS_MONITORING_TIME`.

2.  **Order Placement:**                                                                                     
    * Before placing a sell order, the system queries the `Signals` table for the position's `Filled_Quantity`.
    * The market sell order sent to the exchange specifies a quantity exactly equal to the `Filled_Quantity`.
    * If `Filled_Quantity` is `NULL` or zero for some reason, no sell order is placed, and a critical error is logged. The `Position_Status` in the `Signals` table is updated to **`'Critical_Error_SellQuantity_Null'`**.
    * This logic applies correctly to positions with a status of `Open` or `Partially_Filled`.
    * Implement `place_sell_order` function using exchange API.
          
    *   **If the order placement call itself fails:**        
    *   The system must immediately stop the process for this signal.                                                 
    *   It updates the `Signals` table record `Position_Status` to `'Execution_Failed'`.                              
    *   **If the order is placed successfully:**                                                    
    *   The system logs the `order_id` and updates the `Exchange_Order_ID` in the `Signals` table and updates all the relevant columns in `Signals` table as per US2.3.1 

5.  **Monitoring, Reconciliation, and Timeout:**
    *   After order placement is successful the system waits till the completion of `SELL_ORDER_STATUS_MONITORING_TIME` to get the final order status
    *   **Success:** If the order status becomes `EXECUTED`, the process is complete. The `Signals` table is updated (`Position_Status` -> `'Closed'`, `Filled_Quantity` recorded, update the other relevant columns as per user story US 2.3.1), and the task terminates.
    *   **Partial Fill Detection:** If the status is anython other than 'EXECUTED', the system immediately updates the `Signals` table (`Position_Status` -> `'Critical_Error_Sell_Order'`, `Filled_Quantity` -> current EXECUTED quantity) update the other relevant columns as per user story US 2.3.1), and the task terminates.


#### US3.4: As a user, I want to be able to switch between a "Live Trading" mode and a "Dry Run" (Paper Trading) mode so that I can test the automated trading logic without risking real capital.
**Description:** Implement a global configuration setting that, when enabled, prevents any actual API calls to the exchange. Instead of just logging the intended action, the system should simulate the entire order lifecycle by immediately marking the order as successfully executed and updating its internal state in the database. This allows for complete end-to-end testing of the signal generation and position management logic.
**Acceptance Criteria:**
*   A clear configuration option (e.g., `DRY_RUN = True/False` in a config file) exists.
*   When `DRY_RUN` is `False`, the system operates in "Live Trading" mode, sending real orders to the exchange.
*   When `DRY_RUN` is `True`, the `order_executor` tasks must adhere to the following simulation logic:
    *   They must **not** make any API calls to the exchange (e.g., for placing orders, checking balances, or getting order status).
    *   They must log the details of the simulated order (e.g., symbol, side, quantity).
    *   Immediately after logging, they must update the `Signals` table as if the order was successfully and completely executed:
        *   For a **buy signal**, the `Position_Status` is set to `'Open'`, and `Filled_Quantity` is populated with the quantity that *would* have been ordered. `CoinSwitch_TransactionPrice` should be populated with the price at which the signal was triggered.
        *   For a **sell signal**, the `Position_Status` is set to `'Closed'`.
*   Logging output must clearly differentiate between `LIVE` and `DRY RUN` trades.


#### US3.5: As a system, I want to respect the exchange's API rate limits to avoid being temporarily or permanently blocked from trading.
**Description:** Implement a rate-limiting mechanism to ensure that the number of API requests sent to the exchange does not exceed the allowed limits.
**Acceptance Criteria:**
* API calls are throttled according to the exchange's documented rate limits.
* The system gracefully handles 429 Too Many Requests responses from the exchange.
* No calls are unnecessarily delayed if within limits.
**Tasks (Examples):**
* Research exchange API rate limits (requests per second/minute).
* Implement a token bucket or leaky bucket algorithm for rate limiting.
* Integrate rate limiter with all outgoing API calls.


#### US3.6: As a system, I want to implement robust error handling, logging, and retry mechanisms for exchange API calls to ensure order reliability and provide visibility into issues.
**Description:** Implement try-catch blocks and specific error handling for common API issues (e.g., network errors, invalid requests, exchange downtime).
**Acceptance Criteria:**
* API call failures are caught and logged with relevant details (error message, timestamp).
* Retries with exponential backoff are attempted for transient network errors.
* Critical errors (e.g., authentication failure, insufficient funds) are escalated (e.g., stop trading, send urgent notification).
**Tasks (Examples):**
* Implement retry decorators or logic for API calls.
* Define custom exceptions for API errors.
* Set up comprehensive logging (e.g., to a file, console).

---

## Critical Cross-Cutting Concerns & Future Considerations (beyond this Epic):

* **Risk Management:**
    * **Stop-Loss Orders:** Implement automated stop-loss placement upon entering a buy position to limit potential losses.
    * **Take-Profit Orders:** Implement automated take-profit placement to secure gains.
    * **Position Sizing:** Dynamically calculate the quantity of crypto to buy/sell based on account balance and risk tolerance.
    * **Max Drawdown/Loss Limits:** Implement circuit breakers to halt trading if daily/total losses exceed a predefined threshold.
* **Performance & Scalability:** Optimize data processing and API interaction for high-frequency trading if needed.
* **Monitoring & Alerting:** Comprehensive dashboard for system health, trade history, and real-time P&L. Advanced alerts for critical events (e.g., connection loss, repeated order failures).
* **Persistence of State:** Ensure that active positions, order statuses, and other critical state are persisted across system restarts (e.g., in the SQLite DB) to prevent data loss.
* **UI/Dashboard:** A user interface to view live charts, signals, open positions, trade history, and system logs.
* **Backtesting Framework:** A robust module to test the entire strategy (signal generation + order execution simulation) on extensive historical data.
* **Security Audit:** Regular security audits of API key storage, communication, and overall system.
* **Regulatory Compliance:** Ensure adherence to local financial regulations for automated trading.
* **Multiple Strategies:** Ability to run and manage multiple trading strategies concurrently.

---

## Component 4: Telegram Core Notifications (Phase 1)
Status: Not Started

**Goal:** To establish a robust, non-blocking notification system using Telegram that alerts the user to critical bot events, such as trade executions and status changes, without impacting core trading performance.

### User Stories:

#### US4.1: As a user, I want to receive instant notifications for every trade execution so that I can monitor my bot's trading activity in real-time.
**Description:** Implement the functionality to send a message to a configured Telegram chat immediately after a buy or sell order is executed, for both live and dry-run modes. The message should clearly indicate the mode.
**Acceptance Criteria:**
*   A message is sent to Telegram upon successful execution of a buy or sell order.
*   The notification message clearly distinguishes between `[LIVE]` and `[DRY RUN]` trades.
*   The notification system runs in a separate thread and does not block the main trading logic.
*   Failures to send a notification (e.g., Telegram API is down) are logged but do not crash the bot or halt trading.

**Tasks (Examples):**
*   Add `python-telegram-bot` and `python-dotenv` to `requirements.txt`.
*   Add Telegram token/chat_id placeholders to `env.example`.
*   Create `telegram_handler.py` to manage the asynchronous, threaded bot connection.
*   Implement a thread-safe queue for sending messages from the main app to the Telegram thread.
*   Integrate queue-based message sending into `order_executor.py`.

#### US4.2: As a user, I want to be notified when the bot starts up or encounters a critical error so that I am aware of the bot's operational status.
**Description:** The bot should send a notification when it successfully initializes. It should also send a specific, high-priority alert if it enters a state that requires manual intervention (e.g., critical API failures).
**Acceptance Criteria:**
*   A "Bot started successfully" message is sent on startup.
*   A "CRITICAL ERROR" message is sent if the bot encounters a situation it cannot resolve.
*   Error notifications are sent through the same non-blocking mechanism.

**Tasks (Examples):**
*   Integrate the message queue into the main application startup sequence in `app.py`.
*   Add notification calls to critical `try...except` blocks in the application.

---

## Component 5: Telegram Basic Interactivity (Phase 2)
Status: Not Started

**Goal:** To enable two-way communication with the bot, allowing the user to query for real-time information using simple commands, building upon the asynchronous foundation.

### User Stories:

#### US5.1: As a user, I want to be able to request the bot's current status via a `/status` command so that I can check on my portfolio without logging into the server.
**Description:** Implement a command handler for `/status`. When received, the bot should query its current state and reply with a summary of open positions and account balance.
**Acceptance Criteria:**
*   The bot responds to the `/status` command in the configured Telegram chat.
*   The reply contains the current account balance.
*   The reply lists any currently open positions, including the symbol and entry price.
*   The command handler runs in the Telegram thread and requests data from the main thread safely.

**Tasks (Examples):**
*   Implement a `CommandHandler` for `/status` in `telegram_handler.py`.
*   Design a thread-safe mechanism to request data from the main application thread.
*   Format the response message clearly.

#### US5.2: As a user, I want to be able to request a summary of my trading performance via a `/profit` command so that I can track my bot's profitability.
**Description:** Implement a command handler for `/profit`. When received, the bot should query the `Signals` table in the database and return a summary of performance for all closed trades.
**Acceptance Criteria:**
*   The bot responds to the `/profit` command.
*   The reply contains the total number of closed trades.
*   The reply contains the total realized Profit & Loss (P&L).
*   The database query is performed efficiently and does not block other bot functions.

**Tasks (Examples):**
*   Implement a `CommandHandler` for `/profit` in `telegram_handler.py`.
*   Add a function to `database_handler.py` to calculate the P&L from the `Signals` table.
*   Ensure the database call is handled in a non-blocking way from the Telegram thread.

---

## Component 6: Telegram Advanced Control & Analysis (Phase 3)
Status: Not Started

**Goal:** To provide advanced, real-time control over the bot's trading operations and enable on-demand data analysis directly from Telegram.

### User Stories:

#### US6.1: As a user, I want to be able to command the bot to immediately close an open position via a `/forceexit` command so that I have manual override capability.
**Description:** Implement a command handler for `/forceexit`. This command will trigger the `order_executor` to place a market sell order for the currently open position.
**Acceptance Criteria:**
*   The bot responds to the `/forceexit` command.
*   If a position is open, the bot initiates the sell order execution flow.
*   The bot provides feedback on whether the force exit command was successful.
*   The command is ignored if no position is currently open.
*   A thread-safe mechanism is used to pass the command from the Telegram thread to the main application thread.

**Tasks (Examples):**
*   Implement a `CommandHandler` for `/forceexit`.
*   Design a command queue or similar mechanism to send commands to the main thread.
*   Modify the main application loop to listen for and act on these commands.

#### US6.2: As a user, I want to be able to request a price chart for a symbol via a `/chart` command so that I can perform quick visual analysis.
**Description:** Implement a command handler for `/chart <symbol>`. The bot will generate a simple price chart image for the requested symbol and send it as a photo.
**Acceptance Criteria:**
*   The bot responds to `/chart <symbol>` (e.g., `/chart BTC/INR`).
*   A PNG image of the recent price history for the symbol is generated.
*   The image is sent as a photo to the Telegram chat.
*   The chart generation process runs asynchronously and does not block other bot functions.

**Tasks (Examples):**
*   Add a charting library like `matplotlib` to `requirements.txt`.
*   Implement a `CommandHandler` for `/chart`.
*   Create a function to fetch historical data and generate a chart image.
*   Use the `send_photo` method from the Telegram API.

#### US6.3: As a user, I want to execute read-only SQL queries against the database via a Telegram command so that I can perform custom data analysis on the go.
**Description:** Implement a `/query` command that allows the execution of arbitrary, read-only SQL queries. This provides ultimate flexibility for data analysis directly from a mobile device. For security, the command must strictly validate that only `SELECT` statements are executed.
**Acceptance Criteria:**
*   The bot responds to `/query <SQL_STATEMENT>`.
*   The command handler validates that the query string starts with `SELECT` (case-insensitive) and rejects any other SQL command (`UPDATE`, `DELETE`, `INSERT`, `DROP`, etc.).
*   If the query is valid, it is executed against the `Crypto_Data.db` database.
*   The query results are formatted into a readable, monospaced text message and sent back to the user.
*   The bot replies with a clear error message if the SQL syntax is invalid or the query fails for any other reason.

**Tasks (Examples):**
*   Implement a `CommandHandler` for `/query`.
*   Write a robust validation function to ensure only `SELECT` statements are permitted.
*   Integrate the `database_handler` to execute the query from the Telegram thread.
*   Implement result-to-text formatting logic, handling potential for large result sets.

---

## Epic: Dashboard Integration and Enhancement

**Status:** Planning

**Objective:** Integrate the standalone Flask dashboard into the main bot application to enable unified deployment on a single AWS server. The dashboard will be enhanced for performance and simplified by removing deprecated features.

### User Stories / Requirements:

**1. US-DI-01: Unified Application for AWS Deployment**

*   **As a** Bot Operator,
*   **I want** the Flask dashboard and the core trading bot to run as a single, integrated application,
*   **So that** I can deploy the entire system as one service on an AWS EC2 instance, staying within the 750-hour free tier limit.

**Acceptance Criteria:**
*   The application starts with a single `python main.py` command.
*   The dashboard runs in a non-blocking background thread.
*   The core trading bot's performance and latency are not negatively impacted by the dashboard's operation.

**2. US-DI-02: Remote Dashboard Access**

*   **As a** Bot Operator,
*   **I want** to access the live dashboard from my mobile phone's web browser,
*   **So that** I can monitor the bot's performance remotely.

**Acceptance Criteria:**
*   The Flask web server is configured to be accessible from public IP addresses (`host='0.0.0.0'`).
*   Instructions are available for configuring AWS EC2 Security Groups to allow inbound traffic on the dashboard's port.

**3. US-DI-03: High-Concurrency Database Access**

*   **As a** System Architect,
*   **I want** the database to handle simultaneous read (dashboard) and write (bot) operations without conflict,
*   **So that** "database is locked" errors are eliminated and system stability is ensured.

**Acceptance Criteria:**
*   The SQLite connection is configured to use **Write-Ahead Logging (WAL)** mode (`PRAGMA journal_mode=WAL;`).
*   The `analysis_engine` is refactored to use a centralized `DatabaseHandler`, ensuring all parts of the application use the same robust connection settings.
*   Database connection timeouts are implemented to handle transient locks gracefully.

**4. US-DI-04: Dashboard Simplification**

*   **As a** Bot Operator,
*   **I want** the "All Trades" table and the "Strategy Optimization" sections removed from the dashboard,
*   **So that** the interface is simplified and only shows relevant, high-level analytics.

**Acceptance Criteria:**
*   The corresponding HTML, JavaScript, and Python code for the removed sections are deleted from the codebase.
*   The dashboard loads correctly without the removed features.

---