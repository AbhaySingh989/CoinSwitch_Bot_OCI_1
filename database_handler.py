import sqlite3
import logging
from config import DB_NAME, TABLE_NAME

logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self.conn = None

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_name)
            logging.info("Successfully connected to the database.")
        except sqlite3.Error as e:
            logging.error(f"Database connection failed: {e}")
            raise

    def create_table(self):
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            symbol TEXT NOT NULL,
            candle_start_time INTEGER NOT NULL,
            candle_end_time INTEGER,
            server_timestamp INTEGER,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL,
            volume REAL,
            quote_asset_volume REAL,
            interval TEXT,
            is_final_candle BOOLEAN,
            PRIMARY KEY (symbol, candle_start_time)
        );
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(create_table_query)
            self.conn.commit()
            logging.info(f"Table '{TABLE_NAME}' created or already exists.")
        except sqlite3.Error as e:
            logging.error(f"Table creation failed: {e}")
            raise

    def insert_data(self, data):
        insert_query = f"""
        INSERT OR IGNORE INTO {TABLE_NAME} (symbol, candle_start_time, candle_end_time, server_timestamp, open_price, high_price, low_price, close_price, volume, quote_asset_volume, interval, is_final_candle)
        VALUES (:s, :t, :T, :ts, :o, :h, :l, :c, :v, :q, :i, :x);
        """
        try:
            logging.debug(f"Attempting to insert data: {data}")
            cursor = self.conn.cursor()
            cursor.execute(insert_query, data)
            if cursor.rowcount > 0:
                self.conn.commit()
                logging.info(f"New data inserted for symbol {data['s']} at {data['t']}")
            else:
                logging.info(f"Data already exists for symbol {data['s']} at {data['t']}. Skipping insertion.")
            logging.debug(f"Rowcount after insert: {cursor.rowcount}")
        except sqlite3.Error as e:
            logging.error(f"Data insertion failed: {e}")

    def get_last_closed_candle(self, symbol):
        query = f"""
        SELECT * FROM {TABLE_NAME}
        WHERE symbol = ? AND is_final_candle = 1
        ORDER BY candle_start_time DESC
        LIMIT 1;
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (symbol,))
            row = cursor.fetchone()
            if row:
                # Convert tuple to dict
                return dict(zip([c[0] for c in cursor.description], row))
            return None
        except sqlite3.Error as e:
            logging.error(f"Failed to retrieve last closed candle for {symbol}: {e}")
            return None

    def create_signals_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS Signals (
            Signal_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Unique_PositionID TEXT NOT NULL,
            Symbol TEXT NOT NULL,
            Signal TEXT NOT NULL,
            Signal_Price REAL NOT NULL,
            Signal_Timestamp INTEGER NOT NULL,
            Trigger_Candle_Timestamp INTEGER,
            Signal_Reason TEXT,
            Position_Status TEXT NOT NULL,
            Filled_Quantity REAL,
            Exchange_Order_ID TEXT,
            CoinSwitch_TransactionStatus TEXT,
            CoinSwitch_TransactionPrice REAL,
            CoinSwitch_TransactionTime INTEGER,
            High_Water_Mark REAL,
            take_profit_activated INTEGER DEFAULT 0
        );
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            self.conn.commit()
            logging.info("Table 'Signals' created or already exists.")

            # Safely add the column to existing databases
            self._add_take_profit_activated_column()
        except sqlite3.Error as e:
            logging.error(f"Signals table creation failed: {e}")
            raise

    def insert_signal(self, signal_data):
        query = """
        INSERT INTO Signals (Unique_PositionID, Symbol, Signal, Signal_Price, Signal_Timestamp, Trigger_Candle_Timestamp, Signal_Reason, Position_Status)
        VALUES (:Unique_PositionID, :Symbol, :Signal, :Signal_Price, :Signal_Timestamp, :Trigger_Candle_Timestamp, :Signal_Reason, :Position_Status);
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, signal_data)
            self.conn.commit()
            logging.info(f"New signal inserted: {signal_data}")
            return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Signal insertion failed: {e}")
            return None

    def get_latest_signal(self, symbol):
        """Retrieves the most recent signal for a given symbol."""
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Signals WHERE Symbol = ? ORDER BY Signal_ID DESC LIMIT 1", (symbol,))
        return cursor.fetchone()

    def get_open_buy_signal_for_position(self, unique_position_id):
        """Finds the original, open 'Buy' signal for a given position ID."""
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Signals WHERE Unique_PositionID = ? AND Signal = 'Buy' AND Position_Status = 'Open'", (unique_position_id,))
        return cursor.fetchone()

    def get_active_position(self, unique_position_id):
        """Finds the active 'Buy' signal for a given position ID, which can be 'Open' or 'Partially_Filled'."""
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Signals WHERE Unique_PositionID = ? AND Signal = 'Buy' AND Position_Status IN ('Open', 'Partially_Filled')", (unique_position_id,))
        return cursor.fetchone()

    def update_position_status(self, unique_position_id, new_status):
        query = """
        UPDATE Signals
        SET Position_Status = ?
        WHERE Unique_PositionID = ?;
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (new_status, unique_position_id))
            self.conn.commit()
            logging.info(f"Updated position status for {unique_position_id} to {new_status}")
        except sqlite3.Error as e:
            logging.error(f"Failed to update position status for {unique_position_id}: {e}")

    def update_signal_execution_details(self, signal_id, execution_data):
        """
        Updates a signal record with execution details from the exchange.
        :param signal_id: The Signal_ID of the record to update.
        :param execution_data: A dictionary containing the columns to update,
                               e.g., {'Position_Status': 'Open', 'Filled_Quantity': 0.1, ...}
        """
        if not execution_data:
            logging.warning("No execution data provided to update.")
            return

        set_clause = ", ".join([f"{key} = :{key}" for key in execution_data.keys()])
        query = f"UPDATE Signals SET {set_clause} WHERE Signal_ID = :Signal_ID"

        params = execution_data.copy()
        params['Signal_ID'] = signal_id

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            self.conn.commit()
            logging.info(f"Updated execution details for Signal_ID {signal_id}: {execution_data}")
        except sqlite3.Error as e:
            logging.error(f"Failed to update execution details for Signal_ID {signal_id}: {e}")

    def has_signal_with_reason_for_candle(self, symbol, candle_timestamp, reason):
        """
        Checks if a signal with a specific reason has already been generated for a specific candle.
        """
        query = """
        SELECT 1 FROM Signals
        WHERE Symbol = ? AND Trigger_Candle_Timestamp = ? AND Signal_Reason = ?
        LIMIT 1;
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (symbol, candle_timestamp, reason))
            return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logging.error(f"Failed to check for existing signal for {symbol} at {candle_timestamp} with reason {reason}: {e}")
            return False

    def update_high_water_mark(self, signal_id, price):
        """
        Updates the High_Water_Mark for a given signal.
        """
        query = "UPDATE Signals SET High_Water_Mark = ? WHERE Signal_ID = ?"
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (price, signal_id))
            self.conn.commit()
            logging.debug(f"Updated High_Water_Mark for Signal_ID {signal_id} to {price}")
        except sqlite3.Error as e:
            logging.error(f"Failed to update High_Water_Mark for Signal_ID {signal_id}: {e}")

    def get_all_candles(self, symbol):
        """Retrieves all candles for a given symbol, ordered by time."""
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE symbol = ? ORDER BY candle_start_time ASC", (symbol,))
        return cursor.fetchall()

    def get_last_n_candles(self, symbol, n=300):
        """Retrieves the last n finalized candles for a symbol, ordered chronologically (oldest to newest)."""
        self.conn.row_factory = sqlite3.Row
        query = f"""
        SELECT * FROM {TABLE_NAME}
        WHERE symbol = ? AND is_final_candle = 1
        ORDER BY candle_start_time DESC
        LIMIT ?;
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (symbol, n))
            rows = cursor.fetchall()
            # Convert sqlite3.Row to dict and reverse to make it chronological
            candles = [dict(row) for row in rows]
            candles.reverse()
            return candles
        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve last {n} closed candles for {symbol}: {e}")
            return []

    def close(self):
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed.")

    def _add_take_profit_activated_column(self):
        """
        Adds the 'take_profit_activated' column to the Signals table if it doesn't exist.
        This makes schema migration automatic and safe.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(Signals);")
            columns = {row[1]: row[2] for row in cursor.fetchall()} # Use a dict for easier type checking
            
            # If column doesn't exist, add it as INTEGER
            if 'take_profit_activated' not in columns:
                cursor.execute("ALTER TABLE Signals ADD COLUMN take_profit_activated INTEGER DEFAULT 0;")
                self.conn.commit()
                logging.info("Added 'take_profit_activated' column (as INTEGER) to Signals table.")
            # If column exists but is BOOLEAN (or 0/1 integer), it needs migration.
            # For simplicity in this context, we assume a fresh DB or manual migration if data preservation is critical.
            # A full migration would involve renaming table, creating new, copying data, and dropping old table.
            elif columns.get('take_profit_activated') == 'BOOLEAN':
                 logging.warning("Column 'take_profit_activated' is of type BOOLEAN. Manual migration might be needed for old data. Continuing with new logic.")

        except sqlite3.Error as e:
            logging.error(f"Failed to add or verify 'take_profit_activated' column: {e}")
            raise

    def update_take_profit_level(self, signal_id, level):
        """
        Updates the take_profit_activated level for a given signal.
        """
        query = "UPDATE Signals SET take_profit_activated = ? WHERE Signal_ID = ?"
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (level, signal_id))
            self.conn.commit()
            logging.info(f"Updated take_profit_activated level for Signal_ID {signal_id} to {level}")
        except sqlite3.Error as e:
            logging.error(f"Failed to update take_profit_activated level for Signal_ID {signal_id}: {e}")