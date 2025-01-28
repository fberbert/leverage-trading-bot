# api.py

import os
import re
import time
import json
import requests
import numpy as np
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
USE_TESTNET = os.getenv("BYBIT_TESTNET", "False").lower() == "true"

BINANCE_BASE_URL = 'https://api.binance.com'

# Inicializa sessão HTTP da Bybit (usando pybit)
# Se quiser usar mainnet, certifique-se de que BYBIT_TESTNET não esteja setado como "true".
session = HTTP(
    testnet=USE_TESTNET,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)


def fetch_open_positions():
    """
    Busca as posições abertas usando a biblioteca pybit (unified_trading).
    Mantém a estrutura de retorno compatível com o código do ui.py.
    """
    try:
        # A chamada abaixo retorna um dict que inclui "result" e, dentro dele, "list".
        response = session.get_positions(category="linear", settleCoin="USDT")
        if "result" not in response or "list" not in response["result"]:
            return None

        position_list = response["result"]["list"]
        if not isinstance(position_list, list):
            return None

        adapted_positions = []
        for pos in position_list:

#Posição: {'symbol': 'BTCUSDT', 'leverage': '20', 'autoAddMargin': 0, 'avgPrice': '103682.9', 'liqPrice': '4771.28168679', 'riskLimitValue': '2000000', 'takeProfit': '', 'positionValue': '103.6829', 'isReduceOnly': False, 'tpslMode': 'Full', 'riskId': 1, 'trailingStop': '0', 'unrealisedPnl': '-0.3332', 'markPrice': '103349.7', 'adlRankIndicator': 2, 'cumRealisedPnl': '5.94638841', 'positionMM': '0.57258882', 'createdTime': '1736570501798', 'positionIdx': 0, 'positionIM': '5.23831932', 'seq': 311874322993, 'updatedTime': '1737176616702', 'side': 'Buy', 'bustPrice': '', 'positionBalance': '0', 'leverageSysUpdatedTime': '', 'curRealisedPnl': '-0.0570256', 'size': '0.001', 'positionStatus': 'Normal', 'mmrSysUpdatedTime': '', 'stopLoss': '', 'tradeMode': 0, 'sessionAvgPrice': ''}
            # print(f"Posição: {pos}")
            symbol = pos.get('symbol', '')
            side = pos.get('side', '')
            size_str = pos.get('size', '0')
            size = float(size_str)
            # print(f"Size: {size}")
            entry_price = float(pos.get('avgPrice', 0))
            leverage = float(pos.get('leverage', 0))
            unrealised_pnl = float(pos.get('unrealisedPnl', 0))
            liq_price = float(pos.get('liqPrice', 0)) if pos.get('liqPrice') else 'N/A'

            # 'positionBalance' costuma ser a margem alocada para a posição
            pos_balance = float(pos.get('positionIM', 0))

            # Calcula currentQty como positivo (long) ou negativo (short)
            current_qty = size if side.lower() == 'buy' else -size

            # Bybit não retorna markPrice diretamente no get_positions (v5).
            # Podemos aproximar com positionValue/size se size > 0
            mark_price = pos.get('markPrice', 0)

            # PnL realizado não vem diretamente aqui, então definimos como 0.
            realized_pnl = float(pos.get('curRealisedPnl', 0)) * 2  # multiplicado por 2 já contando a taxa de fechaemento da posição

            adapted_positions.append({
                "symbol": symbol,
                "avgEntryPrice": entry_price,
                "realLeverage": leverage,
                "maintMargin": pos_balance,
                "realisedPnl": realized_pnl,
                "posMargin": pos_balance,
                "unrealisedPnl": unrealised_pnl,
                "currentQty": current_qty,
                "markPrice": mark_price,
                "liquidationPrice": liq_price
            })
        return adapted_positions

    except Exception as e:
        print(f"Erro ao obter posições Bybit: {e}")
        return None


def fetch_high_low_prices(symbol):
    """
    Busca o preço High/Low da última hora no par informado, usando o endpoint de kline.
    """
    try:
        end_time = int(time.time() * 1000)
        start_time = end_time - (60 * 60 * 1000)  # 1 hora atrás

        # Caso use "XBTUSDTM", faça um replace para "BTCUSDT", etc., se for necessário.
        # bybit_symbol = symbol.replace("XBT", "BTC").replace("M", "")
        # corrija a linha acima, o M precisa ser no final da string:
        bybit_symbol = re.sub(r"M$", "", symbol.replace("XBT", "BTC"))
        # bybit_symbol = symbol.replace("XBT", "BTC").replace("TRUP", "TRUMP")

        # A biblioteca pybit oferece método get_kline():
        # doc: get_kline(category, symbol, interval, start, end, limit=..., ...)
        response = session.get_kline(
            category="linear",
            symbol=bybit_symbol,
            interval="1",     # 1m
            start=start_time,
            end=end_time,
            limit=200
        )
        if "result" not in response or "list" not in response["result"]:
            return None, None

        klines = response["result"]["list"]
        if not klines:
            return None, None

        # Cada item é do tipo [startTime, open, high, low, close, volume, turnover]
        highs = []
        lows = []
        for kline in klines:
            # kline[2] = high, kline[3] = low
            if len(kline) >= 4:
                high_val = float(kline[2])
                low_val = float(kline[3])
                highs.append(high_val)
                lows.append(low_val)

        if highs and lows:
            return max(highs), min(lows)
        return None, None

    except Exception as e:
        print(f"Erro ao obter preços High/Low Bybit: {e}")
        return None, None



def close_position_market(position):
    """
    Fecha a posição usando ordem de mercado. 
    Cancelará todas as ordens abertas do mesmo símbolo antes de enviar a ordem de fechamento.
    """
    try:
        symbol = position['symbol']
        current_qty = position['currentQty']
        if current_qty == 0:
            print("Posição já fechada.")
            return

        # Determina o símbolo adaptado para Bybit
        bybit_symbol = re.sub(r"M$", "", symbol.replace("XBT", "BTC"))

        # Cancelar todas as ordens abertas para o mesmo símbolo
        cancel_result = session.cancel_all_orders(category="linear", symbol=bybit_symbol)
        if cancel_result is not None:
            print(f"Todas as ordens abertas para {bybit_symbol} foram canceladas.")
        else:
            print(f"Falha ao cancelar ordens para {bybit_symbol}.")

        # Se a posição for short (qty < 0), precisamos de side="Buy" para fechar.
        side_for_close = "Buy" if current_qty < 0 else "Sell"
        size = abs(current_qty)

        result = session.place_order(
            category="linear",
            symbol=bybit_symbol,
            side=side_for_close,
            orderType="Market",
            qty=size,
            timeInForce="GTC",
            reduceOnly=True,
            positionIdx=0  # one-way mode
        )
        if result is not None and "orderId" in result:
            print(f"Ordem de mercado enviada para fechar posição: {result}")
        else:
            print("Falha ao enviar ordem de fechamento na Bybit.")

    except Exception as e:
        print(f"Erro em close_position_market (Bybit): {e}")



def open_new_position_market(symbol, side, size, leverage):
    """
    Abre nova posição Market:
      1) Ajusta a alavancagem (set_leverage)
      2) Cria a ordem de mercado
    """
    try:
        # bybit_symbol = symbol.replace("XBT", "BTC").replace("M", "")
        bybit_symbol = re.sub(r"M$", "", symbol.replace("XBT", "BTC"))
        side_for_bybit = "Buy" if side.lower() == "buy" else "Sell"

        # 1) Ajustar alavancagem:
        # set_leverage(category="linear", symbol="BTCUSDT", buyLeverage=..., sellLeverage=..., tradeMode=0)
        session.set_leverage(
            category="linear",
            symbol=bybit_symbol,
            buyLeverage=str(leverage),
            sellLeverage=str(leverage),
            tradeMode=0  # 0 => isolated, 1 => cross
        )

        # 2) Criar ordem de mercado
        result = session.place_order(
            category="linear",
            symbol=bybit_symbol,
            side=side_for_bybit,
            orderType="Market",
            qty=size,
            timeInForce="GTC",
            reduceOnly=False,
            positionIdx=0
        )
        if result is not None and "orderId" in result:
            print(f"Ordem de mercado enviada para abrir nova posição: {result}")
            # Montamos um dict para que o ui.py continue funcionando
            position_details = {
                'symbol': symbol,
                'side': side.upper(),
                'size': size,
                'leverage': leverage
            }
            return position_details
        else:
            print("Erro ao enviar ordem de abertura na Bybit.")
            return None

    except Exception as e:
        print(f"Erro em open_new_position_market (Bybit): {e}")
        return None


def decide_trade_direction(symbol, rsi_period=14, use_sma=True, use_rsi=True,
                           use_volume=False, granularity=5, use_high_low=False):
    """
    Esta função permanece igual, pois faz uso da API da Binance para cálculos de RSI, SMA etc.
    """
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

            # SMA curto (7) e longo (25)
            sma_short = np.mean(close_prices[-7:])
            sma_long = np.mean(close_prices[-25:])

            # RSI
            delta = np.diff(close_prices)
            up = delta.copy()
            down = delta.copy()
            up[up < 0] = 0
            down[down > 0] = 0
            gain = np.mean(up[-rsi_period:])
            loss = -np.mean(down[-rsi_period:])
            if loss == 0:
                rsi = 100
            else:
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))

            # Volume
            avg_volume = np.mean(volumes[-7:])
            current_volume = volumes[-1]

            # Sinal da SMA
            if sma_short > sma_long:
                sma_signal = 'buy'
            elif sma_short < sma_long:
                sma_signal = 'sell'
            else:
                sma_signal = 'wait'

            # Sinal do RSI
            if rsi < 30:
                rsi_signal = 'buy'
            elif rsi > 70:
                rsi_signal = 'sell'
            else:
                rsi_signal = 'wait'

            # Confirmação de volume
            volume_signal = 'go' if current_volume > avg_volume else 'wait'
            volume_confirmation = (volume_signal == 'go') if use_volume else True

            # High/Low
            if use_high_low:
                highs = np.array([float(kline[2]) for kline in data])
                lows = np.array([float(kline[3]) for kline in data])
                high_price = np.max(highs)
                low_price = np.min(lows)
                dist_to_high = abs(high_price - current_price)
                dist_to_low = abs(current_price - low_price)
                if dist_to_low < dist_to_high:
                    high_low_signal = 'buy'
                else:
                    high_low_signal = 'sell'
                high_low_value = f"({high_low_signal})"
            else:
                high_low_signal = 'wait'
                high_low_value = 'N/A'

            # Decidir com base nos sinais que foram escolhidos (SMA, RSI, High/Low)
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
            print(f"Erro ao obter dados da Binance: {response.status_code}, {response.text}")
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
    """
    Busca saldo disponível na conta. 
    Para uma conta de derivativos (linear), podemos usar get_wallet_balance.
    """
    try:
        # Se for conta "CONTRACT" (derivativos), ou "UNIFIED", etc.
        # A doc oficial mostra: session.get_wallet_balance(accountType="UNIFIED")
        # Aqui, para manter compatível com o antigo 'CONTRACT', ajustamos:
        response = session.get_wallet_balance(
            accountType="UNIFIED"
        )
        # Normalmente, a resposta vem em algo como:
        # {
        #   "result": {
        #     "list": [
        #       {
        #         "accountType":"CONTRACT",
        #         "coin":[{"coin":"USDT","equity":"1234","availableToWithdraw":"1000","availableBalance":"900",...}]
        #       }
        #     ]
        #   }
        # }

# Resposta da Bybit wallet: {'retCode': 0, 'retMsg': 'OK', 'result': {'list': [{'totalEquity': '1659.03831971', 'accountIMRate': '', 'totalMarginBalance': '', 'totalInitialMargin': '', 'accountType': 'UNIFIED', 'totalAvailableBalance': '', 'accountMMRate': '', 'totalPerpUPL': '-102.27221471', 'totalWalletBalance': '1761.31053443', 'accountLTV': '', 'totalMaintenanceMargin': '', 'coin': [{'availableToBorrow': '', 'bonus': '0', 'accruedInterest': '0', 'availableToWithdraw': '', 'totalOrderIM': '7.21375219', 'equity': '1659.12161219', 'totalPositionMM': '21.93050317', 'usdValue': '1659.0303605', 'unrealisedPnl': '-102.27784', 'collateralSwitch': True, 'spotHedgingQty': '0', 'borrowAmount': '0', 'totalPositionIM': '696.44725257', 'walletBalance': '1761.39945219', 'cumRealisedPnl': '16.74085219', 'locked': '0', 'marginCollateral': True, 'coin': 'USDT'}, {'availableToBorrow': '', 'bonus': '0', 'accruedInterest': '', 'availableToWithdraw': '', 'totalOrderIM': '0', 'equity': '0.048', 'totalPositionMM': '0', 'usdValue': '0.00795921', 'unrealisedPnl': '0', 'collateralSwitch': False, 'spotHedgingQty': '0', 'borrowAmount': '0', 'totalPositionIM': '0', 'walletBalance': '0.048', 'cumRealisedPnl': '0', 'locked': '0', 'marginCollateral': False, 'coin': 'BRL'}]}]}, 'retExtInfo': {}, 'time': 1737540404650}
        print(f"Resposta da Bybit wallet: {response}")
        if "result" not in response or "list" not in response["result"]:
            return None

        wallet_list = response["result"]["list"]
        if not wallet_list:
            return None

        # print(f"response: {response}")
        return {"availableBalance": response["result"]["list"][0]["totalEquity"] or 0}

    except Exception as e:
        print(f"Erro ao obter saldo Bybit: {e}")
        return None

