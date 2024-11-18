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

    def __init__(self):
        super().__init__()
        self.ws_client = None
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    async def handle_message(self, msg):
        """Lida com mensagens recebidas e emite o preço."""
        if msg['topic'] == '/contractMarket/ticker:XBTUSDTM':
            price = float(msg['data']['price'])
            self.price_updated.emit(price)

    async def update_price_via_websocket(self):
        while True:
            try:
                if self.ws_client is None:
                    client = WsToken(key=API_KEY, secret=API_SECRET, passphrase=API_PASSWORD)
                    self.ws_client = await KucoinWsClient.create(None, client, self.handle_message, private=False)
                    await self.ws_client.subscribe('/contractMarket/ticker:XBTUSDTM')
                while True:
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Erro de conexão: {e}. Tentando novamente em 5 segundos...")
                await asyncio.sleep(5)
                self.ws_client = None

    def run(self):
        self.loop.run_until_complete(self.update_price_via_websocket())
