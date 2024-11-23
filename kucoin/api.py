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

def list_usdt_contracts():
    """Obtains the top 15 futures contracts with USDT sorted by 24h volume."""
    try:
        url = "https://api-futures.kucoin.com/api/v1/contracts/active"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get("data", [])
            print(f"Contratos ativos: {len(data)}")
            
            # Filtrar contratos com USDT
            usdt_contracts = [contract for contract in data if contract.get('rootSymbol') == 'USDT']
            
            # Ordenar pelo volume de 24 horas em ordem decrescente
            usdt_contracts.sort(key=lambda x: x.get("markPrice", 0), reverse=True)
            
            # Limitar aos top 15
            top_15_contracts = usdt_contracts[:15]
            print(f"Top 15 contratos por preço: {len(top_15_contracts)}")

            # Adicionar XBTUSDTM no início da lista, se existir
            # xbt_contract = next((contract for contract in data if contract.get('symbol') == 'XBTUSDTM'), None)
            # if xbt_contract:
                # print(xbt_contract)
                # top_15_contracts.insert(0, xbt_contract)

            # print(f"Top 15 contratos por volume: {top_15_contracts}")
            return top_15_contracts
        else:
            print(f"Erro ao obter contratos: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        print(f"Erro ao obter contratos: {e}")
        return []


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
            raise Exception(f"Erro ao obter posições: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Erro ao obter posições: {e}")
        raise Exception(f"Erro ao obter posições: {e}")


def fetch_high_low_prices(symbol):
    """Obtains the High and Low prices of the last hour for the given symbol."""
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

def decide_trade_direction(symbol, rsi_period=14, use_sma=True, use_rsi=True, use_volume=False, granularity=5):
    """
    Decides the trade direction based on historical data and a combined strategy.
    Uses Simple Moving Averages (SMA), Relative Strength Index (RSI), and volume to identify signals.
    Returns 'buy', 'sell', or 'wait'.
    """
    try:
        # Interval to fetch data: 50 minutes to get enough data for SMA and RSI

        end_time = int(time.time() * 1000)
        start_time = 0
        if granularity == 1:
            start_time = end_time - (60 * 100 * 1 * 1000)  # 100 periods of 1 minutes ago in milliseconds
        elif granularity == 5:
            start_time = end_time - (60 * 30 * 5 * 1000) # 30 periods of 5 minutes ago in milliseconds

        # URL for 5-minute granularity
        params = {
            'symbol': symbol,
            'granularity': granularity,
            'from': start_time,
            'to': end_time
        }
        url = "https://api-futures.kucoin.com/api/v1/kline/query"

        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json().get("data", [])
            if len(data) < 25:
                print(f"Insufficient data for analysis ({len(data)} periods)")
                return {'decision': 'wait', 'sma': 'N/A', 'rsi': 'N/A', 'volume': 'N/A'}

            # Extract closing prices and volumes
            close_prices = np.array([float(kline[2]) for kline in data])  # Index 2 is the closing price
            volumes = np.array([float(kline[5]) for kline in data])       # Index 5 is the volume

            # Calculate SMAs
            sma_short = np.mean(close_prices[-7:])   # Short-term SMA (7 periods)
            sma_long = np.mean(close_prices[-25:])   # Long-term SMA (25 periods)

            # Calculate RSI
            delta = np.diff(close_prices)
            up = delta.copy()
            down = delta.copy()
            up[up < 0] = 0
            down[down > 0] = 0
            # period = 14  # Standard period for RSI
            period = rsi_period

            gain = np.mean(up[-period:])
            loss = -np.mean(down[-period:])
            if loss == 0:
                rsi = 100
            else:
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))

            # Volume analysis
            avg_volume = np.mean(volumes[-7:])    # Average volume of the last 7 periods
            current_volume = volumes[-1]          # Volume of the last period

            # Individual signals
            sma_signal = 'buy' if sma_short > sma_long else 'sell' if sma_short < sma_long else 'wait'
            rsi_signal = 'buy' if rsi < 30 else 'sell' if rsi > 70 else 'wait'

            # Volume as confirmation
            if current_volume > avg_volume:
                # If the price is rising
                if close_prices[-1] > close_prices[-2]:
                    volume_signal = 'buy'
                # If the price is falling
                elif close_prices[-1] < close_prices[-2]:
                    volume_signal = 'sell'
                else:
                    volume_signal = 'wait'
            else:
                volume_signal = 'wait'

            # Decide the direction based on the active indicators
            if use_sma and use_rsi and use_volume:
                if sma_signal == rsi_signal == volume_signal and sma_signal != 'wait':
                    decision = sma_signal
                else:
                    decision = 'wait'
            elif use_sma and use_rsi:
                if sma_signal == rsi_signal and sma_signal != 'wait':
                    decision = sma_signal
                else:
                    decision = 'wait'
            elif use_sma and use_volume:
                if sma_signal == volume_signal and sma_signal != 'wait':
                    decision = sma_signal
                else:
                    decision = 'wait'
            elif use_rsi and use_volume:
                if rsi_signal == volume_signal and rsi_signal != 'wait':
                    decision = rsi_signal
                else:
                    decision = 'wait'
            elif use_sma:
                decision = sma_signal if sma_signal != 'wait' else 'wait'
            elif use_rsi:
                decision = rsi_signal if rsi_signal != 'wait' else 'wait'
            elif use_volume:
                decision = volume_signal if volume_signal != 'wait' else 'wait'
            else:
                decision = 'wait'  # Default to wait if no indicator is active

            # Return the decision along with indicator details
            return {
                    "decision": decision,
                    "sma": f"{int(sma_short)} | {int(sma_long)} ({sma_signal})",
                    "rsi": f"{int(rsi)} ({rsi_signal})",
                    "volume": f"{int(current_volume)} now | {int(avg_volume)} avg ({volume_signal})"
                }

        else:
            print(f"Erro ao obter dados históricos: {response.status_code}, {response.text}")
            return {
                "decision": "wait",
                "sma": "Erro",
                "rsi": "Erro",
                "volume": "Erro"
            }
    except Exception as e:
        print(f"Erro em decide_trade_direction: {e}")
        return {
            "decision": "wait",
            "sma": "Erro",
            "rsi": "Erro",
            "volume": "Erro"
        }

