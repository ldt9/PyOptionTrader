#!/usr/bin/env python
# -*- coding: utf-8 -*-
from backend.strategy.strategy_base import StrategyBase
from backend.order.order_event import OrderEvent
from backend.order.order_type import OrderType
from backend.data.tick_event import TickType
from backend.data.options_util import *
import logging
import datetime

_logger = logging.getLogger('backend')


class ShortStranglesOptionsStrategy(StrategyBase):
    """
    Manage a short strangle options strategy
    """
    def __init__(self):
        super(ShortStranglesOptionsStrategy, self).__init__()
        self.ticks = 500                   # Initialize to zero
        self.tick_trigger_threshold = 0  # Initialize to zero
        self.chains = None               # Initialize to None, hold options chain data
        self.target_dte = 0              # 45 days to expiration
        self.nearest_exp = None          # nearest expiration date to target expiration
        self.nearest_dte = 0             # nearest dte to target expiration
        self.iv = 0.00                   # implied volatility
        self.target_profit = 0           # equivalent to 50% of credit received
        self.target_stop_loss = 0        # equivalent to 200% of credit received
        self.target_delta = 0            # equivalent to 16 delta or 1 std dev
        _logger.info('ShortStranglesOptionsStrategy initiated')

    def on_tick(self, k):
        super().on_tick(k)     # extra mtm calc
        self.ticks += 1

        # update the options chain every tick threshold
        # TODO: change this to a cron job
        if self.ticks > self.tick_trigger_threshold:
            self.ticks = 0
            self.chains = self.request_options_chain(k.full_symbol)
            _logger.info(f'ShortStranglesOptionsStrategy initializing options on_tick after {self.tick_trigger_threshold} for {k.full_symbol}')
            _logger.info(f'Options Chain: {self.chains}')

            self.nearest_exp, self.nearest_dte = OptionsUtil.update_target_expiration(k.full_symbol, self.chains, self.target_dte)
            _logger.info(f'ShortStranglesOptionsStrategy nearest expiration: {str(self.nearest_exp)}, nearest dte: {str(self.nearest_dte)}')

            contract_str = OptionsUtil.make_contract_str(k.full_symbol, 'OPT', self.nearest_exp.strftime('%Y%m%d'), str(round(k.price)), 'C', 'SMART')
            _logger.info(f'ShortStranglesOptionsStrategy ATM contract string: {contract_str}')

            data = self.request_option_contract_data(contract_str)
            # price = data['OptionPrice']
            # price = float(next(iter(price)))
            # _logger.info(f'ShortStranglesOptionsStrategy ATM option price: {str(price)}')

            self.iv = OptionsUtil.get_chain_iv("py_vollib", data, k.price, self.nearest_dte, 'C')

            # self.iv = data['ImpliedVolatility']
            # self.iv = float(next(iter(self.iv)))
            _logger.info(f'ShortStranglesOptionsStrategy implied volatility: {str(self.iv)}')

            # get the strike price for the option with the given delta
            call_strike = OptionsUtil.get_strike(k.price, self.target_delta, self.nearest_dte, self.iv, 'C', 'up', rounding=5.0)
            _logger.info(f'OrderPerIntervalStrategy call strike: {str(int(call_strike))}')

            put_strike = OptionsUtil.get_strike(k.price, self.target_delta, self.nearest_dte, self.iv, 'P', 'down', rounding=5.0)
            _logger.info(f'OrderPerIntervalStrategy put strike: {str(int(put_strike))}')


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

    # def update_target_expiration(self, target_dte):
    #     try:
    #         # get the nearest monthly expiration
    #         target_exp = datetime.date.today() + datetime.timedelta(days=target_dte)
    #
    #         # convert the list of expirations to datetime objects
    #         expire = []
    #         for exp in list(self.chains['expirations']):
    #             try:
    #                 expire.append(datetime.datetime.strptime(exp, '%Y%m%d').date())
    #             except ValueError:
    #                 _logger.error(f"Could not convert {exp} to date")
    #
    #         # find the nearest monthly expiration in chain.expirations to targetDTE
    #         nearest_exp = min(expire, key=lambda x: abs(x - target_exp))
    #         # _logger.info(f"Nearest expiration: {self.nearest_exp}")
    #
    #         # find the number of days until the nearest monthly expiration
    #         nearest_dte = (nearest_exp - datetime.date.today()).days
    #         # _logger.info(f"Days to expiration: {str(self.nearest_dte)} days")
    #         return nearest_exp, nearest_dte
    #     except Exception as e:
    #         _logger.error(str(e))
    #         _logger.error(f"Could not update target expiration for {self.symbols[0]}.")


