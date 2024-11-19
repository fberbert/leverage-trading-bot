# websocket_client.py

import asyncio
from PyQt5.QtCore import QThread, pyqtSignal
from kucoin.client import WsToken
from kucoin.ws_client import KucoinWsClient
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("KUCOIN_API_KEY")
API_SECRET = os.getenv("KUCOIN_API_SECRET")
API_PASSWORD = os.getenv("KUCOIN_API_PASSWORD")


class PriceWebsocketClient(QThread):
    price_updated = pyqtSignal(float)

    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol
        self.ws_client = None
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._is_running = True

    async def handle_message(self, msg):
        """Handles received messages and emits the price."""
        if msg['topic'] == f'/contractMarket/ticker:{self.symbol}':
            price = float(msg['data']['price'])
            self.price_updated.emit(price)

    async def update_price_via_websocket(self):
        while self._is_running:
            try:
                if self.ws_client is None:
                    client = WsToken(key=API_KEY, secret=API_SECRET, passphrase=API_PASSWORD)
                    self.ws_client = await KucoinWsClient.create(None, client, self.handle_message, private=False)
                    await self.ws_client.subscribe(f'/contractMarket/ticker:{self.symbol}')
                while self._is_running:
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Connection error: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)
                self.ws_client = None

    def stop(self):
        self._is_running = False
        if self.ws_client:
            self.loop.create_task(self.ws_client.unsubscribe(f'/contractMarket/ticker:{self.symbol}'))
            self.ws_client = None

    def run(self):
        self.loop.run_until_complete(self.update_price_via_websocket())

