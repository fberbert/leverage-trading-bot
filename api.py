import os
import time
import hmac
import hashlib
import base64
import requests
import json
import uuid
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("KUCOIN_API_KEY")
API_SECRET = os.getenv("KUCOIN_API_SECRET")
API_PASSWORD = os.getenv("KUCOIN_API_PASSWORD")


def fetch_open_positions():
    """Lista as posições abertas no mercado de futuros."""
    try:
        url = "https://api-futures.kucoin.com/api/v1/positions"
        now = int(time.time() * 1000)
        str_to_sign = str(now) + 'GET' + '/api/v1/positions'
        signature = base64.b64encode(
            hmac.new(
                API_SECRET.encode('utf-8'),
                str_to_sign.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode()

        passphrase = base64.b64encode(
            hmac.new(
                API_SECRET.encode('utf-8'),
                API_PASSWORD.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode()

        headers = {
            "KC-API-KEY": API_KEY,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": str(now),
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return data
        else:
            print(f"Erro ao obter posições: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        print(f"Erro ao obter posições: {e}")
        return []


def fetch_high_low_prices():
    """Obtém os preços High e Low da última hora para XBTUSDTM."""
    try:
        symbol = "XBTUSDTM"
        end_time = int(time.time() * 1000)
        start_time = end_time - (60 * 60 * 1000)
        url = f"https://api-futures.kucoin.com/api/v1/kline/query?symbol={symbol}&granularity=1&from={start_time}&to={end_time}"

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            highs = [float(kline[3]) for kline in data]
            lows = [float(kline[4]) for kline in data]
            if highs and lows:
                high_price = max(highs)
                low_price = min(lows)
                return high_price, low_price
            else:
                return None, None
        else:
            print(f"Erro ao obter preços High/Low: {response.status_code}, {response.text}")
            return None, None
    except Exception as e:
        print(f"Erro ao obter preços High/Low: {e}")
        return None, None


def close_position_market(position):
    """Fecha a posição com uma ordem de mercado."""
    try:
        print('Fechando posição:', position)
        symbol = position['symbol']
        current_qty = position['currentQty']
        if current_qty == 0:
            print("Posição já fechada.")
            return

        side = 'buy' if current_qty < 0 else 'sell'
        size = abs(current_qty)
        client_oid = str(uuid.uuid4())

        url = "https://api-futures.kucoin.com/api/v1/orders"
        now = int(time.time() * 1000)
        request_path = '/api/v1/orders'
        body = {
            "clientOid": client_oid,
            "symbol": symbol,
            "side": side,
            "type": "market",
            "size": str(size),
            "reduceOnly": True,
            "marginMode": "ISOLATED"
        }
        body_json = json.dumps(body)
        str_to_sign = str(now) + 'POST' + request_path + body_json
        signature = base64.b64encode(
            hmac.new(
                API_SECRET.encode('utf-8'),
                str_to_sign.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode()

        passphrase = base64.b64encode(
            hmac.new(
                API_SECRET.encode('utf-8'),
                API_PASSWORD.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode()

        headers = {
            "KC-API-KEY": API_KEY,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": str(now),
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, data=body_json)
        print('Enviar:', body_json)
        print('Response:', response.status_code, response.text)
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"Ordem de mercado enviada para fechar posição: {data}")
        else:
            print(f"Erro ao enviar ordem de mercado: {response.status_code}, {response.text}")

    except Exception as e:
        print(f"Erro em close_position_market: {e}")

def open_new_position_market(symbol, side, size, leverage):
    """Abre uma nova posição com uma ordem de mercado."""
    try:
        print(f"Abrindo nova posição: {side.upper()} {size} contratos de {symbol} com alavancagem x{leverage}")
        client_oid = str(uuid.uuid4())

        url = "https://api-futures.kucoin.com/api/v1/orders"
        now = int(time.time() * 1000)
        request_path = '/api/v1/orders'
        body = {
            "clientOid": client_oid,
            "symbol": symbol,
            "side": side,
            "type": "market",
            "size": str(size),
            "leverage": str(leverage),
            "marginType": "isolated"  # Usar margem isolada
        }
        body_json = json.dumps(body)
        str_to_sign = str(now) + 'POST' + request_path + body_json
        signature = base64.b64encode(
            hmac.new(
                API_SECRET.encode('utf-8'),
                str_to_sign.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode()

        passphrase = base64.b64encode(
            hmac.new(
                API_SECRET.encode('utf-8'),
                API_PASSWORD.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode()

        headers = {
            "KC-API-KEY": API_KEY,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": str(now),
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, data=body_json)
        print('Enviar:', body_json)
        print('Response:', response.status_code, response.text)
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"Ordem de mercado enviada para abrir nova posição: {data}")
        else:
            print(f"Erro ao enviar ordem de mercado: {response.status_code}, {response.text}")

    except Exception as e:
        print(f"Erro em open_new_position_market: {e}")
