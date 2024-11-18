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


import time
import requests
import numpy as np

def decide_trade_direction(symbol):
    """
    Decide a direção do trade com base em dados históricos e uma estratégia combinada.
    Utiliza Médias Móveis Simples (SMA), Índice de Força Relativa (RSI) e volume para identificar sinais.
    Retorna 'buy', 'sell' ou 'wait'.
    """
    try:
        print(f"Analisando o símbolo {symbol} para decidir a direção do trade...")

        # Intervalo para buscar dados: 25 minutos para obter dados suficientes para SMA e RSI
        end_time = int(time.time() * 1000)
        start_time = end_time - (60 * 25 * 1000)  # 80 minutos atrás em milissegundos

        # URL para granularidade de 1 minuto
        params = {
            'symbol': symbol,
            'granularity': 1,  # 1 minuto
            'from': start_time,
            'to': end_time
        }
        url = "https://api-futures.kucoin.com/api/v1/kline/query"

        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json().get("data", [])
            print(f"Obtidos {len(data)} pontos de dados.")
            print(f"Dados: {data}")
            if len(data) < 25:
                print("Dados insuficientes para análise.")
                return 'wait'

            # Extrair preços de fechamento e volumes
            close_prices = np.array([float(kline[2]) for kline in data])  # Índice 2 é o preço de fechamento
            volumes = np.array([float(kline[5]) for kline in data])       # Índice 5 é o volume

            # Calcular SMAs
            sma_short = np.mean(close_prices[-7:])   # SMA de curto prazo (7 períodos)
            sma_long = np.mean(close_prices[-25:])   # SMA de longo prazo (25 períodos)
            print(f"SMA curto prazo (7): {sma_short}")
            print(f"SMA longo prazo (25): {sma_long}")

            # Calcular RSI
            delta = np.diff(close_prices)
            up = delta.copy()
            down = delta.copy()
            up[up < 0] = 0
            down[down > 0] = 0
            period = 14  # Período padrão para RSI

            gain = np.mean(up[-period:])
            loss = -np.mean(down[-period:])
            if loss == 0:
                rsi = 100
            else:
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
            print(f"RSI (14): {rsi}")

            # Análise de Volume
            avg_volume = np.mean(volumes[-7:])    # Volume médio dos últimos 7 períodos
            current_volume = volumes[-1]          # Volume do último período
            print(f"Volume atual: {current_volume}")
            print(f"Volume médio (7): {avg_volume}")

            # Sinais Individuais
            sma_signal = 'buy' if sma_short > sma_long else 'sell' if sma_short < sma_long else 'wait'
            rsi_signal = 'buy' if rsi < 30 else 'sell' if rsi > 70 else 'wait'
            volume_signal = 'buy' if current_volume > avg_volume else 'wait'

            print(f"Sinal SMA: {sma_signal}")
            print(f"Sinal RSI: {rsi_signal}")
            print(f"Sinal Volume: {volume_signal}")

            # Decidir a direção apenas se os três sinais estiverem alinhados
            if sma_signal == rsi_signal == volume_signal and sma_signal != 'wait':
                print(f"Sinal de {sma_signal.upper()} confirmado pelos três indicadores.")
                return sma_signal
            else:
                print("Indicadores não estão alinhados. Aguardando.")
                return 'wait'
        else:
            print(f"Erro ao obter dados históricos: {response.status_code}, {response.text}")
            return 'wait'
    except Exception as e:
        print(f"Erro em decide_trade_direction: {e}")
        return 'wait'

