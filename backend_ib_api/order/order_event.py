#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .order_status import OrderStatus
from .order_flag import OrderFlag
from .order_type import OrderType
from ..event.event import *

class OrderEvent(Event):
    """
    Order event
    """
    def __init__(self):
        """
        order and order status
        """
        self.event_type = EventType.ORDER
        self.order_id = -1
        self.order_type = OrderType.MARKET
        self.order_flag = OrderFlag.OPEN
        self.order_status = OrderStatus.UNKNOWN
        self.full_symbol =  ''
        self.order_size = 0         # short < 0, long > 0
        self.limit_price = 0.0
        self.stop_price = 0.0
        self.fill_size = 0
        self.fill_price = 0.0
        self.create_time = None
        self.fill_time = None
        self.cancel_time = None
        self.account = ''
        self.source = -1              # sid, -1: unknown, 0: discretionary
        self.timestamp = ''

    def __str__(self):
        return "Time: %s, Source: %s, Type: %s, LMT: %s, STP %s Size %s" % (
            self.timestamp, str(self.source), str(self.order_type), str(self.limit_price), str(self.stop_price), str(self.order_size)
        )