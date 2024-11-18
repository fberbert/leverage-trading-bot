#!/bin/env python3

from api import (
    decide_trade_direction
)

def test_decide_trade_direction():
    symbol = 'XBTUSDM'
    print(decide_trade_direction(symbol))

if __name__ == '__main__':
    test_decide_trade_direction()

