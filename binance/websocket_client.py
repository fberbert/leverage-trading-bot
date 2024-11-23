# websocket_client.py

import asyncio
from PyQt5.QtCore import QThread, pyqtSignal
import websockets
import json

class PriceWebsocketClient(QThread):
    price_updated = pyqtSignal(float)

    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol.lower()
        self.ws = None
        self._is_running = True

    async def connect(self):
        url = f"wss://stream.binance.com:9443/ws/{self.symbol}@miniTicker"
        self.ws = await websockets.connect(url)
        while self._is_running:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                price = float(data['c'])  # 'c' is close price
                self.price_updated.emit(price)
            except Exception as e:
                print(f"Error in websocket: {e}")
                await asyncio.sleep(5)

    def run(self):
        asyncio.run(self.connect())

    def stop(self):
        self._is_running = False
        if self.ws:
            asyncio.get_event_loop().run_until_complete(self.ws.close())
