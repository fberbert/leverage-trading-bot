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
    """Gets the current price for the given symbol."""
    try:
        url = BASE_URL + '/api/v3/ticker/price'
        params = {'symbol': symbol}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
        else:
            print(f"Error fetching current price: {response.status_code}, {response.text}")
            return 0
    except Exception as e:
        print(f"Error in get_current_price: {e}")
        return 0

def get_margin_trades(symbol, isIsolated='TRUE'):
    """Gets the margin trades for a symbol."""
    try:
        url_path = '/sapi/v1/margin/myTrades'
        params = {
            'symbol': symbol,
            'isIsolated': isIsolated
        }
        response = send_signed_request('GET', url_path, params)
        if response.status_code == 200:
            trades = response.json()
            return trades
        else:
            print(f"Error fetching trades for {symbol}: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        print(f"Error in get_margin_trades: {e}")
        return []

def fetch_open_positions(position_trackers):
    """Gets the isolated margin account positions."""
    try:
        url_path = '/sapi/v1/margin/isolated/account'
        response = send_signed_request('GET', url_path)
        if response.status_code == 200:
            data = response.json()
            positions = []
            for asset_info in data['assets']:
                symbol = asset_info['symbol']
                base_asset = asset_info['baseAsset']
                quote_asset = asset_info['quoteAsset']

                net_asset_base = float(base_asset['netAsset'])
                net_asset_quote = float(quote_asset['netAsset'])
                borrowed_base = float(base_asset['borrowed'])
                borrowed_quote = float(quote_asset['borrowed'])
                interest_base = float(base_asset['interest'])
                interest_quote = float(quote_asset['interest'])

                # Determine if there is a position
                position_size = net_asset_base
                if abs(position_size) >= 1e-5:  # Adjusted to ignore negligible positions

                    print(asset_info)
                    # Determine position side
                    if position_size > 0:
                        side = 'LONG'
                    else:
                        side = 'SHORT'

                    # Get entry price from stored data
                    position_id = symbol  # Using symbol as the identifier
                    if position_id in position_trackers:
                        entry_price = position_trackers[position_id]['position']['entry_price']
                        leverage = position_trackers[position_id]['position']['leverage']
                        amount_usd = position_trackers[position_id]['position']['amount_usd']
                    else:
                        # If entry price is not stored, set to None
                        entry_price = None
                        leverage = 10.0  # Default leverage or retrieve from elsewhere
                        amount_usd = None

                    # Get current price
                    current_price = get_current_price(symbol)

                    # Calculate unrealized PNL
                    if entry_price and current_price:
                        if side == 'LONG':
                            pnl = (current_price - entry_price) * abs(position_size)
                        else:
                            pnl = (entry_price - current_price) * abs(position_size)
                    else:
                        pnl = 0.0

                    # Calculate initial margin
                    if leverage > 1 and position_size != 0 and entry_price:
                        initial_margin = (abs(position_size) * entry_price) / leverage
                    else:
                        initial_margin = abs(position_size) * entry_price if entry_price else 0.0

                    # Adjust initial margin for interest and fees
                    total_interest = interest_base * current_price + interest_quote
                    initial_margin += total_interest

                    # Calculate PNL percentage
                    if initial_margin != 0:
                        pnl_percentage = (pnl / initial_margin) * 100
                    else:
                        pnl_percentage = 0.0

                    # Amount in USD
                    amount_usd = amount_usd if amount_usd else abs(position_size) * current_price if current_price else 0.0

                    # Margin used
                    margin = initial_margin

                    # Get borrowed amount for repayment
                    if side == 'LONG':
                        borrowed_amount = borrowed_quote + interest_quote
                    else:
                        borrowed_amount = (borrowed_base + interest_base) * current_price

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
            return positions
        else:
            print(f"Error fetching open positions: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        print(f"Error in fetch_open_positions: {e}")
        return []

def close_position_market(position):
    """Closes a margin position."""
    try:
        print('Closing position:', position)
        symbol = position['symbol']
        side = 'SELL' if position['side'] == 'LONG' else 'BUY'
        amount = abs(position['position_size'])

        # Get symbol info to adjust quantity according to LOT_SIZE
        symbol_info = get_symbol_info(symbol)
        if symbol_info is None:
            print("Could not retrieve symbol info.")
            return

        lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
        min_qty = float(lot_size_filter['minQty'])
        step_size = float(lot_size_filter['stepSize'])

        if amount < min_qty:
            print(f"Position size {amount} is less than minQty {min_qty}, cannot close position via market order.")
        else:
            # Adjust quantity to comply with LOT_SIZE filter
            quantity_str = adjust_quantity(symbol_info, amount)
            if quantity_str is None:
                print("Could not adjust quantity.")
                return

            print(f"Closing position with amount: {quantity_str}")
            # Place market order to close position
            url_path = '/sapi/v1/margin/order'
            params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity_str,
                'isIsolated': 'TRUE'
            }
            response = send_signed_request('POST', url_path, params)
            if response.status_code == 200:
                data = response.json()
                print(f"Market order sent to close position: {data}")
            else:
                print(f"Error sending market order: {response.status_code}, {response.text}")
                return

        base_asset = symbol.replace('USDT', '')
        quote_asset = 'USDT'

        # Auxiliary functions
        def repay_asset(asset, amount):
            repay_amount_str = '{:.8f}'.format(amount).rstrip('0').rstrip('.')
            repay_url = '/sapi/v1/margin/repay'
            repay_params = {
                'asset': asset,
                'amount': repay_amount_str,
                'symbol': symbol,
                'isIsolated': 'TRUE'
            }
            repay_response = send_signed_request('POST', repay_url, repay_params)
            if repay_response.status_code == 200:
                repay_data = repay_response.json()
                print(f"Repaid borrowed asset {asset}: {repay_data}")
            else:
                print(f"Error repaying asset {asset}: {repay_response.status_code}, {repay_response.text}")

        def sell_asset(quantity):
            quantity_str = adjust_quantity(symbol_info, quantity)
            if quantity_str is None:
                print(f"Could not adjust quantity for selling {base_asset}.")
                return
            print(f"Selling {base_asset}: {quantity_str}")
            sell_params = {
                'symbol': symbol,
                'side': 'SELL',
                'type': 'MARKET',
                'quantity': quantity_str,
                'isIsolated': 'TRUE'
            }
            sell_response = send_signed_request('POST', '/sapi/v1/margin/order', sell_params)
            if sell_response.status_code == 200:
                sell_data = sell_response.json()
                print(f"Sold {base_asset}: {sell_data}")
            else:
                print(f"Error selling {base_asset}: {sell_response.status_code}, {sell_response.text}")

        def buy_asset(quantity):
            quantity_str = adjust_quantity(symbol_info, quantity)
            if quantity_str is None:
                print(f"Could not adjust quantity for buying {base_asset}.")
                return
            print(f"Buying {base_asset}: {quantity_str}")
            buy_params = {
                'symbol': symbol,
                'side': 'BUY',
                'type': 'MARKET',
                'quantity': quantity_str,
                'isIsolated': 'TRUE'
            }
            buy_response = send_signed_request('POST', '/sapi/v1/margin/order', buy_params)
            if buy_response.status_code == 200:
                buy_data = buy_response.json()
                print(f"Bought {base_asset}: {buy_data}")
            else:
                print(f"Error buying {base_asset}: {buy_response.status_code}, {buy_response.text}")

        # Get updated account info
        account_info = get_margin_account(symbol)
        base_balance = float(account_info['baseAsset']['free'])
        quote_balance = float(account_info['quoteAsset']['free'])
        borrowed_base = float(account_info['baseAsset']['borrowed'])
        borrowed_quote = float(account_info['quoteAsset']['borrowed'])
        interest_base = float(account_info['baseAsset']['interest'])
        interest_quote = float(account_info['quoteAsset']['interest'])
        total_borrowed_base = borrowed_base + interest_base
        total_borrowed_quote = borrowed_quote + interest_quote

        # Specific processing for LONG and SHORT positions
        if position['side'] == 'LONG':
            # Repay borrowed USDT
            if total_borrowed_quote > 0:
                repay_asset(quote_asset, total_borrowed_quote)
            # Sell any remaining BASE asset for USDT
            account_info = get_margin_account(symbol)
            base_balance = float(account_info['baseAsset']['free'])
            if base_balance >= min_qty:
                sell_asset(base_balance)
        elif position['side'] == 'SHORT':
            # Buy BASE asset required to repay the loan
            required_base = total_borrowed_base - base_balance
            if required_base > min_qty:
                buy_asset(required_base)
            # Repay borrowed BASE asset
            if total_borrowed_base > 0:
                repay_asset(base_asset, total_borrowed_base)
            # Sell any remaining BASE asset for USDT
            account_info = get_margin_account(symbol)
            base_balance = float(account_info['baseAsset']['free'])
            if base_balance >= min_qty:
                sell_asset(base_balance)

        print("Position closed and assets repaid successfully.")

    except Exception as e:
        print(f"Error in close_position_market: {e}")

def get_margin_account(symbol):
    """Gets the isolated margin account details for a specific symbol."""
    try:
        url_path = '/sapi/v1/margin/isolated/account'
        params = {'symbols': symbol}
        response = send_signed_request('GET', url_path, params)
        if response.status_code == 200:
            data = response.json()
            if 'assets' in data and len(data['assets']) > 0:
                return data['assets'][0]
            else:
                print(f"No account data found for symbol {symbol}")
                return None
        else:
            print(f"Error fetching margin account info: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Error in get_margin_account: {e}")
        return None

def open_new_position_market(symbol, side, usd_amount, leverage):
    """Opens a new margin position with a market order and returns position details."""
    try:
        print(f"Opening new position: {side.upper()} ${usd_amount} of {symbol} with leverage x{leverage}")
        # Get current price
        price = get_current_price(symbol)
        if price is None or price == 0:
            print("Could not retrieve current price.")
            return None

        # Get symbol info to adjust quantity according to LOT_SIZE
        symbol_info = get_symbol_info(symbol)
        if symbol_info is None:
            print("Could not retrieve symbol info.")
            return None

        base_asset_precision = symbol_info['baseAssetPrecision']
        # Calculate quantity in base asset
        quantity = (usd_amount * leverage) / price

        # Adjust quantity to comply with LOT_SIZE filter
        quantity_str = adjust_quantity(symbol_info, quantity)
        if quantity_str is None:
            print("Could not adjust quantity.")
            return None

        # Borrow asset if necessary
        url_path_borrow = '/sapi/v1/margin/loan'
        if side.upper() == 'BUY':
            # Borrow USDT
            borrow_asset = 'USDT'
            borrow_amount = usd_amount * (leverage - 1)
            borrow_amount_str = '{:.8f}'.format(borrow_amount).rstrip('0').rstrip('.')
        else:
            # Borrow BASE asset
            base_asset = symbol.replace('USDT', '')
            borrow_asset = base_asset
            borrow_amount = float(quantity_str) * (leverage - 1)
            borrow_amount_str = ('{0:.' + str(base_asset_precision) + 'f}').format(borrow_amount).rstrip('0').rstrip('.')

        # Check max borrowable amount
        max_borrowable = get_max_borrowable(symbol, borrow_asset, isIsolated='TRUE')
        if max_borrowable is None:
            print("Could not retrieve max borrowable amount.")
            return None

        if max_borrowable == 0.0:
            print(f"Cannot borrow {borrow_asset} because max borrowable amount is zero.")
            print("Please ensure you have sufficient collateral in your isolated margin account.")
            return None

        if float(borrow_amount_str) > max_borrowable:
            print(f"Desired borrow amount {borrow_amount_str} exceeds max borrowable {max_borrowable}. Adjusting borrow amount.")
            borrow_amount_str = ('{0:.' + str(base_asset_precision) + 'f}').format(max_borrowable).rstrip('0').rstrip('.')

            # Adjust quantity accordingly
            if side.upper() == 'SELL':
                adjusted_quantity = max_borrowable / (leverage - 1)
                quantity = adjusted_quantity
                quantity_str = adjust_quantity(symbol_info, quantity)
                if quantity_str is None:
                    print("Could not adjust quantity after max borrowable check.")
                    return None

        # Proceed to borrow if amount is greater than zero
        if float(borrow_amount_str) > 0:
            params_borrow = {
                'asset': borrow_asset,
                'amount': borrow_amount_str,
                'symbol': symbol,
                'isIsolated': 'TRUE'
            }

            response_borrow = send_signed_request('POST', url_path_borrow, params_borrow)
            if response_borrow.status_code == 200:
                data_borrow = response_borrow.json()
                print(f"Borrowed asset: {data_borrow}")
            else:
                print(f"Error borrowing asset: {response_borrow.status_code}, {response_borrow.text}")
                return None
        else:
            print(f"No need to borrow {borrow_asset}, amount is zero.")

        # Place market order
        url_path_order = '/sapi/v1/margin/order'
        params_order = {
            'symbol': symbol,
            'side': side.upper(),
            'type': 'MARKET',
            'quantity': quantity_str,
            'isIsolated': 'TRUE'
        }
        response_order = send_signed_request('POST', url_path_order, params_order)
        if response_order.status_code == 200:
            data_order = response_order.json()
            print(f"Market order sent to open new position: {data_order}")

            # Extract entry price from fills
            fills = data_order.get('fills', [])
            if fills:
                # Calculate weighted average entry price
                total_qty = sum(float(fill['qty']) for fill in fills)
                entry_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / total_qty
            else:
                # If no fills, use cummulativeQuoteQty
                entry_price = float(data_order['cummulativeQuoteQty']) / float(data_order['executedQty'])

            # Return position details
            position_details = {
                'symbol': symbol,
                'side': side.upper(),
                'amount_usd': usd_amount,
                'entry_price': entry_price,
                'leverage': leverage,
                'quantity': float(quantity_str)
            }
            return position_details  # Return the details to ui.py

        else:
            print(f"Error sending market order: {response_order.status_code}, {response_order.text}")
            return None

    except Exception as e:
        print(f"Error in open_new_position_market: {e}")
        return None

def get_symbol_info(symbol):
    """Gets the exchange information for the given symbol."""
    try:
        url = BASE_URL + '/api/v3/exchangeInfo'
        params = {'symbol': symbol}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            symbol_info = data['symbols'][0]
            return symbol_info
        else:
            print(f"Error fetching symbol info: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Error in get_symbol_info: {e}")
        return None

def adjust_quantity(symbol_info, quantity):
    """Adjusts the quantity to comply with the LOT_SIZE filter."""
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
            # Adjust to the nearest step size
            precision = int(round(-math.log(step_size, 10), 0))
            quantity = math.floor(quantity / step_size) * step_size
            quantity = round(quantity, precision)

        quantity_str = ('{0:.' + str(symbol_info['baseAssetPrecision']) + 'f}').format(quantity).rstrip('0').rstrip('.')
        return quantity_str
    except Exception as e:
        print(f"Error in adjust_quantity: {e}")
        return None

def decide_trade_direction(symbol, rsi_period=14, use_sma=True, use_rsi=True, use_volume=False, granularity=5):
    """Decides the trade direction based on historical data and a combined strategy."""
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
                print(f"Insufficient data for analysis ({len(data)} periods)")
                return {'decision': 'wait', 'sma': 'N/A', 'rsi': 'N/A', 'volume': 'N/A'}
            close_prices = np.array([float(kline[4]) for kline in data])
            volumes = np.array([float(kline[5]) for kline in data])

            # Calculate SMAs
            sma_short = np.mean(close_prices[-7:])
            sma_long = np.mean(close_prices[-25:])

            # Calculate RSI
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

            # Volume analysis
            avg_volume = np.mean(volumes[-7:])
            current_volume = volumes[-1]

            # Individual signals
            sma_signal = 'buy' if sma_short > sma_long else 'sell' if sma_short < sma_long else 'wait'
            rsi_signal = 'buy' if rsi < 30 else 'sell' if rsi > 70 else 'wait'

            # Volume as confirmation
            if current_volume > avg_volume:
                if close_prices[-1] > close_prices[-2]:
                    volume_signal = 'buy'
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
                decision = 'wait'

            return {
                "decision": decision,
                "sma": f"{int(sma_short)} | {int(sma_long)} ({sma_signal})",
                "rsi": f"{int(rsi)} ({rsi_signal})",
                "volume": f"{int(current_volume)} now | {int(avg_volume)} avg ({volume_signal})"
            }

        else:
            print(f"Error fetching historical data: {response.status_code}, {response.text}")
            return {
                "decision": "wait",
                "sma": "Error",
                "rsi": "Error",
                "volume": "Error"
            }
    except Exception as e:
        print(f"Error in decide_trade_direction: {e}")
        return {
            "decision": "wait",
            "sma": "Error",
            "rsi": "Error",
            "volume": "Error"
        }

def fetch_high_low_prices(symbol):
    """Gets the 1-hour high and low prices for the given symbol."""
    try:
        url = BASE_URL + '/api/v3/klines'
        params = {
            'symbol': symbol,
            'interval': '1m',
            'limit': 60  # last 60 minutes
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
            print(f"Error fetching high/low prices: {response.status_code}, {response.text}")
            return None, None
    except Exception as e:
        print(f"Error in fetch_high_low_prices: {e}")
        return None, None

def get_max_borrowable(symbol, asset, isIsolated='TRUE'):
    try:
        url_path = '/sapi/v1/margin/maxBorrowable'
        params = {
            'asset': asset,
            'isolatedSymbol': symbol,
            'isIsolated': isIsolated
        }
        response = send_signed_request('GET', url_path, params)
        if response.status_code == 200:
            data = response.json()
            return float(data['amount'])
        else:
            print(f"Error fetching max borrowable: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Error in get_max_borrowable: {e}")
        return None

def get_margin_account_balance(symbol):
    """Gets the isolated margin account balances for a specific symbol."""
    try:
        url_path = '/sapi/v1/margin/isolated/account'
        params = {'symbols': symbol}
        response = send_signed_request('GET', url_path, params)
        if response.status_code == 200:
            data = response.json()
            if 'assets' in data and len(data['assets']) > 0:
                return data['assets'][0]
            else:
                print(f"No account data found for symbol {symbol}")
                return None
        else:
            print(f"Error fetching margin account info: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Error in get_margin_account_balance: {e}")
        return None

