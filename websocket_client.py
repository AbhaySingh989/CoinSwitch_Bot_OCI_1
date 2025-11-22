import asyncio
import logging
import time
import socketio
from config import BASE_URL, NAMESPACE, SOCKET_PATH, EVENT_CANDLES, SYMBOLS, INTERVAL

logger = logging.getLogger(__name__)

# In-memory cache for multiple symbols
in_memory_cache = {}

class WebSocketClient:
    def __init__(self, db_handler, signal_generator):
        self.sio = socketio.AsyncClient(logger=True, engineio_logger=True, ssl_verify=False)
        self.db_handler = db_handler
        self.signal_generator = signal_generator
        self.is_connected = False

    async def connect(self):
        while not self.is_connected:
            try:
                await self.sio.connect(
                    BASE_URL,
                    namespaces=[NAMESPACE],
                    transports=["websocket"],
                    socketio_path=SOCKET_PATH,
                )
                self.is_connected = True
                logging.info("WebSocket connected successfully.")
            except socketio.exceptions.ConnectionError as e:
                logging.error(f"Connection failed: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)

    async def subscribe_to_pairs(self, event_name, pairs, batch_size=5, delay=0.2):
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i + batch_size]
            for pair in batch:
                try:
                    subscribe_data = {"event": "subscribe", "pair": pair}
                    await self.sio.emit(event_name, subscribe_data, namespace=NAMESPACE)
                    logging.info(f"Subscribed to {pair} for event: {event_name}")
                except Exception as e:
                    logging.error(f"Subscription failed for {pair}: {e}")
                    # Add retry logic here if needed
            await asyncio.sleep(delay)  # Prevent rate limiting

    def setup_handlers(self):
        @self.sio.on("connect", namespace=NAMESPACE)
        async def on_connect():
            logging.info("Socket connected and namespace is open.")
            pairs_to_subscribe = [f"{symbol}_{INTERVAL}" for symbol in SYMBOLS]
            await self.subscribe_to_pairs(EVENT_CANDLES, pairs_to_subscribe)

        @self.sio.on("disconnect", namespace=NAMESPACE)
        def on_disconnect():
            self.is_connected = False
            logging.warning("WebSocket disconnected.")

        @self.sio.on(EVENT_CANDLES, namespace=NAMESPACE)
        async def on_candles(data):
            start_time = time.time()
            logger.debug(f"Received raw data in on_candles: {data}")
            payload = None
            if isinstance(data, list) and len(data) > 1 and isinstance(data[1], dict):
                payload = data[1]
            elif isinstance(data, dict):
                payload = data
            
            if payload is None:
                logger.error(f"Unexpected data format received: {data}")
                return
            
            logger.debug(f"Extracted payload: {payload}")

            symbol = payload.get('s', 'UNKNOWN')
            symbol_interval = f"{symbol}_{payload.get('i', 'UNKNOWN')}"
            current_candle_start_time = payload.get('t')

            # Get the last known state for this symbol
            cached_data = in_memory_cache.get(symbol_interval)
            last_candle_start_time = cached_data.get('last_candle_start_time') if cached_data else None

            # Real-time signal checks on every update
            await self.signal_generator.process_candle_data(payload)

            # --- Resilient Candle Finalization Logic ---
            
            # 1. Check for implicit finalization (new candle detected)
            if last_candle_start_time and current_candle_start_time > last_candle_start_time:
                logger.info(f"New candle detected for {symbol_interval}. Finalizing previous candle implicitly.")
                
                # Get the last payload of the previous candle
                final_payload = cached_data.get('last_payload')
                if final_payload:
                    # Promote to final and process
                    final_payload['x'] = True
                    self.db_handler.insert_data(final_payload)
                
                # Clear the cache for the old candle and reset for the new one
                in_memory_cache.pop(symbol_interval, None)
                logger.info(f"Cleared cache for {symbol_interval} after implicit finalization.")
                in_memory_cache[symbol_interval] = {
                    'last_candle_start_time': current_candle_start_time,
                    'last_payload': payload
                }

            # 2. Check for explicit finalization (x:true flag)
            elif payload.get('x', False):
                logger.info(f"Explicit final candle detected for {symbol_interval}. Attempting to insert into DB.")
                self.db_handler.insert_data(payload)
                
                # Clear the cache for the completed candle
                in_memory_cache.pop(symbol_interval, None)
                logger.info(f"Cleared cache for {symbol_interval} after explicit final candle.")

            # 3. If it's just a regular update for the current candle
            else:
                if not cached_data:
                     in_memory_cache[symbol_interval] = {'last_candle_start_time': current_candle_start_time}
                in_memory_cache[symbol_interval]['last_payload'] = payload
                logger.debug(f"Updated cache for {symbol_interval} with latest payload.")

            processing_time = (time.time() - start_time) * 1000
            logger.debug(f"Candle for {symbol_interval} processed in {processing_time:.2f} ms.")

    async def run(self):
        self.setup_handlers()
        await self.connect()
        await self.sio.wait()
