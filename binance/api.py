# api.py

import os
import time
import hmac
import hashlib
import requests
import json
import numpy as np
import math
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

BASE_URL = 'https://api.binance.com'

def send_signed_request(http_method, url_path, payload={}):
    query_string = urlencode(payload, True)
    timestamp = int(time.time() * 1000)
    query_string += '&timestamp=' + str(timestamp)
    signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    url = BASE_URL + url_path + '?' + query_string + '&signature=' + signature

    headers = {
        'X-MBX-APIKEY': API_KEY
    }
    if http_method == 'GET':
        response = requests.get(url, headers=headers)
    elif http_method == 'POST':
        response = requests.post(url, headers=headers)
    else:
        raise ValueError('Invalid HTTP method')

    return response

def get_current_price(symbol):
    """Obtém o preço atual para o símbolo fornecido."""
    try:
        url = BASE_URL + '/api/v3/ticker/price'
        params = {'symbol': symbol}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
        else:
            print(f"Erro ao obter preço atual: {response.status_code}, {response.text}")
            return 0
    except Exception as e:
        print(f"Erro em get_current_price: {e}")
        return 0

def get_margin_trades(symbol):
    """Obtém as negociações de margem para um símbolo."""
    try:
        url_path = '/sapi/v1/margin/myTrades'
        params = {
            'symbol': symbol
        }
        response = send_signed_request('GET', url_path, params)
        if response.status_code == 200:
            trades = response.json()
            return trades
        else:
            print(f"Erro ao obter negociações para {symbol}: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        print(f"Erro em get_margin_trades: {e}")
        return []


def fetch_open_positions(position_trackers):
    """Obtém as posições da conta de margem cruzada."""
    try:
        url_path = '/sapi/v1/margin/account'
        response = send_signed_request('GET', url_path)
        if response.status_code == 200:
            data = response.json()
            positions = []

            # Mapeia os ativos para facilitar o acesso
            assets_info = {asset_info['asset']: asset_info for asset_info in data['userAssets']}
            total_asset_of_btc = float(data.get('totalCollateralValueInUSDT', 0))
            total_collateral_value_in_usdt = float(data.get('totalCollateralValueInUSDT', 0))

            for asset_info in data['userAssets']:
                asset = asset_info['asset']
                net_asset = float(asset_info['netAsset'])
                borrowed = float(asset_info['borrowed'])
                free = float(asset_info['free'])
                interest = float(asset_info['interest'])

                # Ignora ativos sem posições significativas
                if net_asset == 0 and borrowed == 0 and interest == 0:
                    continue

                # Ignora USDT aqui, pois o usamos como referência para determinar posições
                if asset == 'USDT':
                    continue

                symbol = asset + 'USDT'

                # Obtém informações do símbolo
                symbol_info = get_symbol_info(symbol)
                if symbol_info is None:
                    continue  # Pula se o símbolo não for encontrado

                # Determina o lado e o tamanho da posição
                position_size = net_asset  # Quantidade do ativo em questão

                # Verifica se há posição significativa
                if abs(position_size) >= 1e-5:
                    # Verifica se há empréstimo associado
                    usdt_info = assets_info.get('USDT', {})
                    borrowed_usdt = float(usdt_info.get('borrowed', 0))
                    net_usdt = float(usdt_info.get('netAsset', 0))

                    if borrowed_usdt > 0 or net_usdt < 0:
                        # Posição LONG: emprestou USDT para comprar o ativo
                        side = 'LONG'
                    elif borrowed > 0 or net_asset < 0:
                        # Posição SHORT: emprestou o ativo para vender por USDT
                        side = 'SHORT'
                    else:
                        # Pode ser um ativo mantido sem margem; ignora
                        continue

                    # Obtém o preço atual
                    current_price = get_current_price(symbol)

                    # Tenta obter o preço de entrada dos position_trackers
                    position_id = symbol  # Usando o símbolo como identificador
                    if position_id in position_trackers:
                        entry_price = position_trackers[position_id]['position']['entry_price']
                        # entry_price = position_trackers['entry_price']
                        leverage = position_trackers[position_id]['position']['leverage']
                        # leverage = position_trackers['leverage']
                    else:
                        # Se não estiver disponível, estima o preço de entrada
                        entry_price = None
                        leverage = 10.0  # Leverage padrão ou ajuste conforme necessário

                    # Se não tivermos o preço de entrada, podemos tentar estimar
                    if entry_price is None and current_price:
                        # Estima o preço de entrada usando o valor emprestado e a quantidade do ativo

                            # total_borrowed_usdt = borrowed_usdt + float(usdt_info.get('interest', 0))
                            # entry_price = total_borrowed_usdt / abs(position_size)
                        # elif side == 'SHORT' and borrowed > 0:
                            # entry_price = current_price  # Como não temos melhor estimativa
                        entry_price = total_collateral_value_in_usdt / total_asset_of_btc

                    # Calcula PNL não realizado
                    if entry_price and current_price:
                        if side == 'LONG':
                            pnl = (current_price - entry_price) * abs(position_size)
                        else:
                            pnl = (entry_price - current_price) * abs(position_size)
                    else:
                        pnl = 0.0
                    # remover 4% do pnl para taxas
                    tax = pnl * 0.04
                    # tax = 0.08 # test

                    # ajustar o preço de acordo com a alavancagem
                    # pnl /= leverage
                    pnl -= tax

                    # print(f"entry price: {entry_price} - current price: {current_price} - pnl: {pnl} - leverage: {leverage}")

                    # Calcula a margem inicial
                    if leverage > 1 and position_size != 0 and entry_price:
                        initial_margin = (abs(position_size) * entry_price) / leverage
                    else:
                        initial_margin = abs(position_size) * entry_price if entry_price else 0.0

                    # Ajusta a margem inicial para juros e taxas
                    total_interest = interest * current_price
                    initial_margin += total_interest

                    # Calcula PNL em porcentagem
                    if initial_margin != 0:
                        pnl_percentage = (pnl / initial_margin) * 100
                    else:
                        pnl_percentage = 0.0

                    # Quantidade em USD
                    amount_usd = initial_margin * leverage

                    # Margem usada
                    margin = initial_margin

                    # Montante emprestado para reembolso
                    if side == 'LONG':
                        borrowed_amount = borrowed_usdt + float(usdt_info.get('interest', 0))
                    else:
                        borrowed_amount = borrowed + interest

                    positions.append({
                        'symbol': symbol,
                        'side': side,
                        'position_size': position_size,
                        'amount_usd': amount_usd,
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'margin': margin,
                        'pnl': pnl,
                        'pnl_percentage': pnl_percentage,
                        'borrowed_amount': abs(borrowed_amount),
                        'leverage': leverage
                    })
                    # print totalAssetOfBtc of position:
                    # print(f"Total Asset of {symbol}: {total_asset_of_btc}")
            return positions
        else:
            print(f"Erro ao obter posições abertas: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        print(f"Erro em fetch_open_positions: {e}")
        return []


def close_position_market(position):
    """Fecha uma posição de margem."""
    try:
        print('Fechando posição:', position)
        symbol = position['symbol']
        side = 'SELL' if position['side'] == 'LONG' else 'BUY'
        amount = abs(position['position_size'])

        # Obtém informações do símbolo para ajustar a quantidade de acordo com LOT_SIZE
        symbol_info = get_symbol_info(symbol)
        if symbol_info is None:
            print("Não foi possível obter informações do símbolo.")
            return

        lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
        min_qty = float(lot_size_filter['minQty'])
        step_size = float(lot_size_filter['stepSize'])

        if amount < min_qty:
            print(f"Tamanho da posição {amount} é menor que minQty {min_qty}, não é possível fechar posição via ordem de mercado.")
        else:
            # Ajusta a quantidade para cumprir com o filtro LOT_SIZE
            quantity_str = adjust_quantity(symbol_info, amount)
            if quantity_str is None:
                print("Não foi possível ajustar a quantidade.")
                return

            print(f"Fechando posição com quantidade: {quantity_str}")
            # Envia ordem de mercado para fechar posição
            url_path = '/sapi/v1/margin/order'
            params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity_str
            }
            response = send_signed_request('POST', url_path, params)
            if response.status_code == 200:
                data = response.json()
                print(f"Ordem de mercado enviada para fechar posição: {data}")
            else:
                print(f"Erro ao enviar ordem de mercado: {response.status_code}, {response.text}")
                return

        base_asset = symbol.replace('USDT', '')
        quote_asset = 'USDT'

        # Funções auxiliares
        def repay_asset(asset, amount):
            repay_amount_str = '{:.8f}'.format(amount).rstrip('0').rstrip('.')
            repay_url = '/sapi/v1/margin/repay'
            repay_params = {
                'asset': asset,
                'amount': repay_amount_str
            }
            repay_response = send_signed_request('POST', repay_url, repay_params)
            if repay_response.status_code == 200:
                repay_data = repay_response.json()
                print(f"Reembolsado ativo emprestado {asset}: {repay_data}")
            else:
                print(f"Erro ao reembolsar ativo {asset}: {repay_response.status_code}, {repay_response.text}")

        def sell_asset(quantity):
            quantity_str = adjust_quantity(symbol_info, quantity)
            if quantity_str is None:
                print(f"Não foi possível ajustar a quantidade para vender {base_asset}.")
                return
            print(f"Vendendo {base_asset}: {quantity_str}")
            sell_params = {
                'symbol': symbol,
                'side': 'SELL',
                'type': 'MARKET',
                'quantity': quantity_str
            }
            sell_response = send_signed_request('POST', '/sapi/v1/margin/order', sell_params)
            if sell_response.status_code == 200:
                sell_data = sell_response.json()
                print(f"Vendido {base_asset}: {sell_data}")
            else:
                print(f"Erro ao vender {base_asset}: {sell_response.status_code}, {sell_response.text}")

        def buy_asset(quantity):
            quantity_str = adjust_quantity(symbol_info, quantity)
            if quantity_str is None:
                print(f"Não foi possível ajustar a quantidade para comprar {base_asset}.")
                return
            print(f"Comprando {base_asset}: {quantity_str}")
            buy_params = {
                'symbol': symbol,
                'side': 'BUY',
                'type': 'MARKET',
                'quantity': quantity_str
            }
            buy_response = send_signed_request('POST', '/sapi/v1/margin/order', buy_params)
            if buy_response.status_code == 200:
                buy_data = buy_response.json()
                print(f"Comprado {base_asset}: {buy_data}")
            else:
                print(f"Erro ao comprar {base_asset}: {buy_response.status_code}, {buy_response.text}")

        # Obtém informações atualizadas da conta
        account_info = get_margin_account()
        asset_info = next((item for item in account_info['userAssets'] if item['asset'] == base_asset), None)
        if asset_info is None:
            print(f"Nenhum dado de conta encontrado para o ativo {base_asset}")
            return

        base_balance = float(asset_info['free'])
        borrowed_base = float(asset_info['borrowed'])
        interest_base = float(asset_info['interest'])
        total_borrowed_base = borrowed_base + interest_base

        # Processamento específico para posições LONG e SHORT
        if position['side'] == 'LONG':
            # Reembolsar USDT emprestado
            usdt_info = next((item for item in account_info['userAssets'] if item['asset'] == 'USDT'), None)
            if usdt_info:
                borrowed_quote = float(usdt_info['borrowed'])
                interest_quote = float(usdt_info['interest'])
                total_borrowed_quote = borrowed_quote + interest_quote
                if total_borrowed_quote > 0:
                    repay_asset('USDT', total_borrowed_quote)
            # Vender qualquer ativo BASE restante por USDT
            account_info = get_margin_account()
            asset_info = next((item for item in account_info['userAssets'] if item['asset'] == base_asset), None)
            if asset_info:
                base_balance = float(asset_info['free'])
                if base_balance >= min_qty:
                    sell_asset(base_balance)
        elif position['side'] == 'SHORT':
            # Comprar ativo BASE necessário para reembolsar o empréstimo
            required_base = total_borrowed_base - base_balance
            if required_base > min_qty:
                buy_asset(required_base)
            # Reembolsar ativo BASE emprestado
            if total_borrowed_base > 0:
                repay_asset(base_asset, total_borrowed_base)
            # Vender qualquer ativo BASE restante por USDT
            account_info = get_margin_account()
            asset_info = next((item for item in account_info['userAssets'] if item['asset'] == base_asset), None)
            if asset_info:
                base_balance = float(asset_info['free'])
                if base_balance >= min_qty:
                    sell_asset(base_balance)

        print("Posição fechada e ativos reembolsados com sucesso.")

        # Transferir fundos da margem para spot e de volta para margem
        # Isso é para garantir que a Binance reconheça a posição como fechada
        # Obter saldo livre de USDT na conta de margem
        account_info = get_margin_account()
        usdt_info = next((item for item in account_info['userAssets'] if item['asset'] == 'USDT'), None)
        if usdt_info:
            free_usdt = float(usdt_info['free'])
            if free_usdt > 0:
                transfer_amount_str = '{:.8f}'.format(free_usdt).rstrip('0').rstrip('.')
                transfer_result = transfer_margin_to_spot('USDT', transfer_amount_str)
                if transfer_result:
                    print(f"Transferido {transfer_amount_str} USDT da margem para spot.")
                    # Agora transfere de volta de spot para margem
                    transfer_result = transfer_spot_to_margin('USDT', transfer_amount_str)
                    if transfer_result:
                        print(f"Transferido {transfer_amount_str} USDT de spot de volta para margem.")
                    else:
                        print("Erro ao transferir USDT de spot de volta para margem.")
                else:
                    print("Erro ao transferir USDT de margem para spot.")
            else:
                print("Nenhum USDT livre na conta de margem para transferir.")
        else:
            print("Nenhum ativo USDT encontrado na conta de margem.")

    except Exception as e:
        print(f"Erro em close_position_market: {e}")

def transfer_margin_to_spot(asset, amount):
    """Transfere ativo da conta de margem para a conta spot."""
    try:
        url_path = '/sapi/v1/margin/transfer'
        params = {
            'asset': asset,
            'amount': amount,
            'type': '2'  # Transferência de margem para spot
        }
        response = send_signed_request('POST', url_path, params)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Erro ao transferir de margem para spot: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Erro em transfer_margin_to_spot: {e}")
        return None

def transfer_spot_to_margin(asset, amount):
    """Transfere ativo da conta spot para a conta de margem."""
    try:
        url_path = '/sapi/v1/margin/transfer'
        params = {
            'asset': asset,
            'amount': amount,
            'type': '1'  # Transferência de spot para margem
        }
        response = send_signed_request('POST', url_path, params)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Erro ao transferir de spot para margem: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Erro em transfer_spot_to_margin: {e}")
        return None

def get_margin_account():
    """Obtém os detalhes da conta de margem cruzada."""
    try:
        url_path = '/sapi/v1/margin/account'
        response = send_signed_request('GET', url_path)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Erro ao obter informações da conta de margem: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Erro em get_margin_account: {e}")
        return None

def open_new_position_market(symbol, side, usd_amount, leverage):
    """Abre uma nova posição de margem com uma ordem de mercado e retorna os detalhes da posição."""
    try:
        print(f"Abrindo nova posição: {side.upper()} ${usd_amount} de {symbol} com leverage x{leverage}")
        # Obtém o preço atual
        price = get_current_price(symbol)
        if price is None or price == 0:
            print("Não foi possível obter o preço atual.")
            return None

        # Obtém informações do símbolo para ajustar a quantidade de acordo com LOT_SIZE
        symbol_info = get_symbol_info(symbol)
        if symbol_info is None:
            print("Não foi possível obter informações do símbolo.")
            return None

        base_asset_precision = symbol_info['baseAssetPrecision']
        # Calcula a quantidade em ativo base
        quantity = (usd_amount * leverage) / price

        # Ajusta a quantidade para cumprir com o filtro LOT_SIZE
        quantity_str = adjust_quantity(symbol_info, quantity)
        if quantity_str is None:
            print("Não foi possível ajustar a quantidade.")
            return None

        # Empréstimo de ativo se necessário
        url_path_borrow = '/sapi/v1/margin/loan'
        if side.upper() == 'BUY':
            # Empréstimo de USDT
            borrow_asset = 'USDT'
            borrow_amount = usd_amount * (leverage - 1)
            borrow_amount_str = '{:.8f}'.format(borrow_amount).rstrip('0').rstrip('.')
        else:
            # Empréstimo de ativo BASE
            base_asset = symbol.replace('USDT', '')
            borrow_asset = base_asset
            borrow_amount = float(quantity_str) * (leverage - 1)
            borrow_amount_str = ('{0:.' + str(base_asset_precision) + 'f}').format(borrow_amount).rstrip('0').rstrip('.')

        # Verifica o máximo que pode ser emprestado
        max_borrowable = get_max_borrowable(borrow_asset)
        if max_borrowable is None:
            print("Não foi possível obter o valor máximo emprestável.")
            return None

        if max_borrowable == 0.0:
            print(f"Não é possível emprestar {borrow_asset} porque o valor máximo emprestável é zero.")
            print("Certifique-se de que você tem garantia suficiente em sua conta de margem.")
            return None

        if float(borrow_amount_str) > max_borrowable:
            print(f"O valor de empréstimo desejado {borrow_amount_str} excede o máximo emprestável {max_borrowable}. Ajustando o valor do empréstimo.")
            borrow_amount_str = ('{0:.' + str(base_asset_precision) + 'f}').format(max_borrowable).rstrip('0').rstrip('.')

            # Ajusta a quantidade de acordo
            if side.upper() == 'SELL':
                adjusted_quantity = max_borrowable / (leverage - 1)
                quantity = adjusted_quantity
                quantity_str = adjust_quantity(symbol_info, quantity)
                if quantity_str is None:
                    print("Não foi possível ajustar a quantidade após verificar o máximo emprestável.")
                    return None

        # Prossegue para emprestar se o valor for maior que zero
        if float(borrow_amount_str) > 0:
            params_borrow = {
                'asset': borrow_asset,
                'amount': borrow_amount_str
            }

            response_borrow = send_signed_request('POST', url_path_borrow, params_borrow)
            if response_borrow.status_code == 200:
                data_borrow = response_borrow.json()
                print(f"Ativo emprestado: {data_borrow}")
            else:
                print(f"Erro ao emprestar ativo: {response_borrow.status_code}, {response_borrow.text}")
                return None
        else:
            print(f"Não é necessário emprestar {borrow_asset}, valor é zero.")

        # Envia ordem de mercado
        url_path_order = '/sapi/v1/margin/order'
        params_order = {
            'symbol': symbol,
            'side': side.upper(),
            'type': 'MARKET',
            'quantity': quantity_str
        }
        response_order = send_signed_request('POST', url_path_order, params_order)
        if response_order.status_code == 200:
            data_order = response_order.json()
            print(f"Ordem de mercado enviada para abrir nova posição: {data_order}")

            # Extrai o preço de entrada dos fills
            fills = data_order.get('fills', [])
            if fills:
                # Calcula o preço médio ponderado de entrada
                total_qty = sum(float(fill['qty']) for fill in fills)
                entry_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / total_qty
            else:
                # Se não houver fills, usa cummulativeQuoteQty
                entry_price = float(data_order['cummulativeQuoteQty']) / float(data_order['executedQty'])

            # Retorna detalhes da posição
            position_details = {
                'symbol': symbol,
                'side': side.upper(),
                'amount_usd': usd_amount,
                'entry_price': entry_price,
                'leverage': leverage,
                'quantity': float(quantity_str)
            }
            return position_details  # Retorna os detalhes para ui.py

        else:
            print(f"Erro ao enviar ordem de mercado: {response_order.status_code}, {response_order.text}")
            return None

    except Exception as e:
        print(f"Erro em open_new_position_market: {e}")
        return None

def get_symbol_info(symbol):
    """Obtém as informações de exchange para o símbolo fornecido."""
    try:
        url = BASE_URL + '/api/v3/exchangeInfo'
        params = {'symbol': symbol}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            symbol_info = data['symbols'][0]
            return symbol_info
        else:
            print(f"Erro ao obter informações do símbolo: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Erro em get_symbol_info: {e}")
        return None

def adjust_quantity(symbol_info, quantity):
    """Ajusta a quantidade para cumprir com o filtro LOT_SIZE."""
    try:
        lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
        min_qty = float(lot_size_filter['minQty'])
        max_qty = float(lot_size_filter['maxQty'])
        step_size = float(lot_size_filter['stepSize'])

        if quantity < min_qty:
            quantity = min_qty
        elif quantity > max_qty:
            quantity = max_qty
        else:
            # Ajusta para o step size mais próximo
            precision = int(round(-math.log(step_size, 10), 0))
            quantity = math.floor(quantity / step_size) * step_size
            quantity = round(quantity, precision)

        quantity_str = ('{0:.' + str(symbol_info['baseAssetPrecision']) + 'f}').format(quantity).rstrip('0').rstrip('.')
        return quantity_str
    except Exception as e:
        print(f"Erro em adjust_quantity: {e}")
        return None

def decide_trade_direction(symbol, rsi_period=14, use_sma=True, use_rsi=True, use_volume=False, granularity=5):
    """Decide a direção do trade com base em dados históricos e uma estratégia combinada."""
    try:
        interval = '1m' if granularity == 1 else '5m'
        limit = 100 if granularity == 1 else 30
        url = BASE_URL + '/api/v3/klines'
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
                return {'decision': 'wait', 'sma': 'N/A', 'rsi': 'N/A', 'volume': 'N/A'}
            close_prices = np.array([float(kline[4]) for kline in data])
            volumes = np.array([float(kline[5]) for kline in data])

            # Calcula SMAs
            sma_short = np.mean(close_prices[-7:])
            sma_long = np.mean(close_prices[-25:])

            # Calcula RSI
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

            # Análise de volume
            avg_volume = np.mean(volumes[-7:])
            current_volume = volumes[-1]

            # Sinais individuais
            sma_signal = 'buy' if sma_short > sma_long else 'sell' if sma_short < sma_long else 'wait'
            rsi_signal = 'buy' if rsi < 30 else 'sell' if rsi > 70 else 'wait'

            # Volume como confirmação
            if current_volume > avg_volume:
                volume_signal = 'go'
                # if close_prices[-1] > close_prices[-2]:
                    # volume_signal = 'buy'
                # elif close_prices[-1] < close_prices[-2]:
                    # volume_signal = 'sell'
                # else:
                    # volume_signal = 'wait'
            else:
                volume_signal = 'wait'

            # Decide a direção com base nos indicadores ativos
            if use_sma and use_rsi and use_volume:
                if sma_signal == rsi_signal and volume_signal == 'go':
                    decision = sma_signal
                else:
                    decision = 'wait'
            elif use_sma and use_rsi:
                if sma_signal == rsi_signal and sma_signal != 'wait':
                    decision = sma_signal
                else:
                    decision = 'wait'
            elif use_sma and use_volume:
                if volume_signal == 'go' and sma_signal != 'wait':
                    decision = sma_signal
                else:
                    decision = 'wait'
            elif use_rsi and use_volume:
                if volume_signal == 'go' and rsi_signal != 'wait':
                    decision = rsi_signal
                else:
                    decision = 'wait'
            elif use_sma:
                decision = sma_signal if sma_signal != 'wait' else 'wait'
            elif use_rsi:
                decision = rsi_signal if rsi_signal != 'wait' else 'wait'
            elif use_volume:
                decision = 'wait'
            else:
                decision = 'wait'

            return {
                "decision": decision,
                "sma": f"{int(sma_short)} | {int(sma_long)} ({sma_signal})",
                "rsi": f"{int(rsi)} ({rsi_signal})",
                "volume": f"{int(current_volume)} agora | {int(avg_volume)} média ({volume_signal})"
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

def fetch_high_low_prices(symbol):
    """Obtém os preços máximos e mínimos de 1 hora para o símbolo fornecido."""
    try:
        url = BASE_URL + '/api/v3/klines'
        params = {
            'symbol': symbol,
            'interval': '1m',
            'limit': 60  # Últimos 60 minutos
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            highs = [float(kline[2]) for kline in data]
            lows = [float(kline[3]) for kline in data]
            high_price = max(highs)
            low_price = min(lows)
            return high_price, low_price
        else:
            print(f"Erro ao obter preços high/low: {response.status_code}, {response.text}")
            return None, None
    except Exception as e:
        print(f"Erro em fetch_high_low_prices: {e}")
        return None, None

def get_max_borrowable(asset):
    """Obtém o valor máximo que pode ser emprestado para um ativo."""
    try:
        url_path = '/sapi/v1/margin/maxBorrowable'
        params = {
            'asset': asset
        }
        response = send_signed_request('GET', url_path, params)
        if response.status_code == 200:
            data = response.json()
            return float(data['amount'])
        else:
            print(f"Erro ao obter máximo emprestável: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Erro em get_max_borrowable: {e}")
        return None

def get_margin_account_balance():
    """Obtém os saldos da conta de margem cruzada."""
    try:
        url_path = '/sapi/v1/margin/account'
        response = send_signed_request('GET', url_path)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Erro ao obter informações da conta de margem: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Erro em get_margin_account_balance: {e}")
        return None

