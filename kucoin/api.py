# api.py

import os
import time
import hmac
import hashlib
import base64
import requests
import json
import uuid
import numpy as np
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("KUCOIN_API_KEY")
API_SECRET = os.getenv("KUCOIN_API_SECRET")
API_PASSWORD = os.getenv("KUCOIN_API_PASSWORD")

BINANCE_BASE_URL = 'https://api.binance.com'

def fetch_open_positions():
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
            return None
    except Exception as e:
        print(f"Erro ao obter posições: {e}")
        return None

def fetch_high_low_prices(symbol):
    try:
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
            "marginType": "isolated"
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

            position_details = {
                'symbol': symbol,
                'side': side.upper(),
                'size': size,
                'leverage': leverage
            }
            return position_details
        else:
            print(f"Erro ao enviar ordem de mercado: {response.status_code}, {response.text}")
            return None

    except Exception as e:
        print(f"Erro em open_new_position_market: {e}")
        return None

def decide_trade_direction(symbol, rsi_period=14, use_sma=True, use_rsi=True, use_volume=False, granularity=5, use_high_low=False):
    try:
        interval = '1m' if granularity == 1 else '5m'
        limit = 100 if granularity == 1 else 30
        url = BINANCE_BASE_URL + '/api/v3/klines'
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if len(data) < 25:
                print(f"Dados insuficientes para análise ({len(data)} períodos)")
                return {'decision': 'wait', 'sma': 'N/A', 'rsi': 'N/A', 'volume': 'N/A', 'high_low': 'N/A'}
            close_prices = np.array([float(kline[4]) for kline in data])
            volumes = np.array([float(kline[5]) for kline in data])
            current_price = close_prices[-1]

            sma_short = np.mean(close_prices[-7:])
            sma_long = np.mean(close_prices[-25:])

            delta = np.diff(close_prices)
            up = delta.copy()
            down = delta.copy()
            up[up < 0] = 0
            down[down > 0] = 0
            period = rsi_period
            gain = np.mean(up[-period:])
            loss = -np.mean(down[-period:])
            if loss == 0:
                rsi = 100
            else:
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))

            avg_volume = np.mean(volumes[-7:])
            current_volume = volumes[-1]

            sma_signal = 'buy' if sma_short > sma_long else 'sell' if sma_short < sma_long else 'wait'
            rsi_signal = 'buy' if rsi < 30 else 'sell' if rsi > 70 else 'wait'

            if current_volume > avg_volume:
                volume_signal = 'go'
            else:
                volume_signal = 'wait'

            if use_volume:
                volume_confirmation = volume_signal == 'go'
            else:
                volume_confirmation = True

            if use_high_low:
                highs = np.array([float(kline[2]) for kline in data])
                lows = np.array([float(kline[3]) for kline in data])
                high_price = np.max(highs)
                low_price = np.min(lows)
                distance_to_high = abs(high_price - current_price)
                distance_to_low = abs(current_price - low_price)
                if distance_to_low < distance_to_high:
                    high_low_signal = 'buy'
                else:
                    high_low_signal = 'sell'
                high_low_value = f"({high_low_signal})"
            else:
                high_low_signal = 'wait'
                high_low_value = 'N/A'

            signals = []
            if use_sma:
                signals.append(sma_signal)
            if use_rsi:
                signals.append(rsi_signal)
            if use_high_low:
                signals.append(high_low_signal)

            if len(signals) > 0 and all(s == 'buy' for s in signals) and volume_confirmation:
                decision = 'buy'
            elif len(signals) > 0 and all(s == 'sell' for s in signals) and volume_confirmation:
                decision = 'sell'
            else:
                decision = 'wait'

            return {
                "decision": decision,
                "sma": f"{int(sma_short)} | {int(sma_long)} ({sma_signal})",
                "rsi": f"{int(rsi)} ({rsi_signal})",
                "volume": f"{int(current_volume)} agora | {int(avg_volume)} média ({volume_signal})",
                "high_low": high_low_value
            }

        else:
            print(f"Erro ao obter dados históricos: {response.status_code}, {response.text}")
            return {
                "decision": "wait",
                "sma": "Erro",
                "rsi": "Erro",
                "volume": "Erro",
                "high_low": "Erro"
            }
    except Exception as e:
        print(f"Erro em decide_trade_direction: {e}")
        return {
            "decision": "wait",
            "sma": "Erro",
            "rsi": "Erro",
            "volume": "Erro",
            "high_low": "Erro"
        }

def get_account_overview(currency="USDT"):
    try:
        url = f"https://api-futures.kucoin.com/api/v1/account-overview?currency={currency}"
        now = int(time.time() * 1000)
        str_to_sign = str(now) + 'GET' + f'/api/v1/account-overview?currency={currency}'
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
            data = response.json().get("data", {})
            return data
        else:
            print(f"Erro ao obter saldo: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Erro ao obter saldo: {e}")
        return None

