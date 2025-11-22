import asyncio
import logging
import os
from dotenv import load_dotenv
from database_handler import DatabaseHandler
from websocket_client import WebSocketClient
from signal_generator import SignalGenerator
from futures import ApiTradingClient
from config import DB_NAME

load_dotenv()

logger = logging.getLogger(__name__)

class App:
    def __init__(self):
        api_key = os.getenv("API_KEY")
        secret_key = os.getenv("SECRET_KEY")
        if not api_key or not secret_key:
            raise ValueError("API_KEY and SECRET_KEY must be set in the .env file.")

        self.db_handler = DatabaseHandler(DB_NAME)
        self.api_client = ApiTradingClient(api_key=api_key, secret_key=secret_key)
        self.signal_generator = SignalGenerator(self.db_handler, self.api_client)
        self.ws_client = WebSocketClient(self.db_handler, self.signal_generator)
        self.loop = asyncio.get_event_loop()

    async def main(self):
        self.db_handler.connect()
        self.db_handler.create_table()
        self.db_handler.create_signals_table()

        await self.ws_client.run()

    async def shutdown(self, signal_name):
        logging.info(f"Received {signal_name}, shutting down gracefully.")
        await self.ws_client.sio.disconnect()
        self.db_handler.close()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.loop.stop()
