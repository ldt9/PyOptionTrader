#!/usr/bin/env python
# -*- coding: utf-8 -*-
from ..event.event import *
from .position import Position

class PositionEvent(Event):
    """
    position event directly from live broker
    """
    def __init__(self):
        """
        Initialises order
        """
        self.event_type = EventType.POSITION
        self.full_symbol = ''
        self_sec_type = ''
        self.average_cost = 0.0
        self.size = 0
        self.pre_size = 0
        self.freezed_size = 0
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.account = ''
        self.timestamp = ''

    def to_position(self):
        pos = Position(self.full_symbol, self.average_cost, self.size)
        pos.realized_pnl = self.realized_pnl
        pos.unrealized_pnl = self.unrealized_pnl
        pos.account = self.account

        return pos

    def __str__(self):
        return "Ticker: %s, Cost: %s, Size: %s, opl: %s, rpl: %s" % (
            str(self.full_symbol), str(self.average_cost), str(self.size), str(self.unrealized_pnl), str(self.realized_pnl)
        )
