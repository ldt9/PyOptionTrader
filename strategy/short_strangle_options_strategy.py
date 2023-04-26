#!/usr/bin/env python
# -*- coding: utf-8 -*-
from backend.strategy.strategy_base import StrategyBase
from backend.order.order_event import OrderEvent
from backend.order.order_type import OrderType
from backend.data.tick_event import TickType
import logging
import datetime

_logger = logging.getLogger('backend')


class ShortStranglesOptionsStrategy(StrategyBase):
    """
    Manage a short strangle options strategy
    """
    def __init__(self):
        super(ShortStranglesOptionsStrategy, self).__init__()
        self.ticks = 0                   # Initialize to zero
        self.tick_trigger_threshold = 0  # Initialize to zero
        self.chains = {}                 # Initialize to None, hold options chain data
        self.target_dte = 0              # 45 days to expiration
        self.target_profit = 0           # equivalent to 50% of credit received
        self.target_stop_loss = 0        # equivalent to 200% of credit received
        self.target_delta = 0            # equivalent to 16 delta or 1 std dev
        _logger.info('OrderPerIntervalStrategy initiated')

    def on_tick(self, k):
        super().on_tick(k)     # extra mtm calc
        self.ticks += 1

        # self.chains = self.request_options_chain(self.symbols[0])
        # _logger.info(f'Chain: {self.chains}')

        # update the options chain every tick threshold
        # TODO: change this to a cron job
        if self.ticks > self.tick_trigger_threshold:
            self.chains = self.request_options_chain(self.symbols[0])
            self.update_target_expiration(self.target_dte)
            _logger.info(f'OrderPerIntervalStrategy initializing options on_tick after {self.tick_trigger_threshold} for {k.full_symbol}')
            self.ticks = 0

        # if k.tick_type != TickType.TRADE:
        #     print(k, f'{self.ticks}/{self.tick_trigger_threshold}')
        # if (k.full_symbol == self.symbols[0]) & (self.ticks > self.tick_trigger_threshold):
        #     o = OrderEvent()
        #     o.full_symbol = k.full_symbol
        #     o.order_type = OrderType.MARKET
        #     o.order_size = self.direction
        #     self.direction = 1 if self.direction == -1 else -1
        #     _logger.info(f'OrderPerIntervalStrategy order placed on ticks {self.ticks}, {k.price}')
        #     self.place_order(o)
        #     self.ticks = 0
        # else:
        #     self.ticks += 1

    def update_target_expiration(self, target_dte):
        try:
            chain = next(c for c in self.chains if c.exchange == 'SMART')

            _logger.info(f"Chain: {chain}")

            # get the nearest monthly expiration
            targetDTE = datetime.date.today() + datetime.timedelta(days=target_dte)

            # convert chain.expirations to datetime.date
            expire = [datetime.datetime.strptime(exp, '%Y%m%d').date() for exp in chain.expirations]

            # find the nearest monthly expiration in chain.expirations to targetDTE
            nearestDTE = min(expire, key=lambda x: abs(x - targetDTE))

            # find the number of days until the nearest monthly expiration
            daysToexp = (nearestDTE - datetime.date.today()).days / 365
            _logger.info(f"Days to expiration: ", round(daysToexp * 365), " days")
            _logger.info(f"Expiration date: ", nearestDTE)
        except Exception as e:
            _logger.error(str(e))
            _logger.error(f"Could not update target expiration for {self.symbols[0]}.")


