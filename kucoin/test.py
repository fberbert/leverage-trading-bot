#!/bin/env python3

from api import (
    decide_trade_direction,
)
from utils import send_email_notification

def test_decide_trade_direction():
    symbol = 'XBTUSDM'
    print(decide_trade_direction(symbol))

def test_list_usdt_contracts():
    print(list_usdt_contracts())


if __name__ == '__main__':
    # test_decide_trade_direction()
    # list_usdt_contracts()
    send_email_notification('Teste', 'Teste de envio de e-mail')

