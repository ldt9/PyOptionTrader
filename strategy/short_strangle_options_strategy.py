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
        # TODO: change this to a cron job instead of tick based
        if self.ticks > self.tick_trigger_threshold:
            self.ticks = 0

            # request the options chain
            self.chains = self.request_options_chain(k.full_symbol)
            _logger.info(f'ShortStranglesOptionsStrategy initializing options on_tick after {self.tick_trigger_threshold} for {k.full_symbol}')
            _logger.info(f'Options Chain: {self.chains}')

            # update the target expiration and days to expiration
            self.nearest_exp, self.nearest_dte = OptionsUtil.update_target_expiration(k.full_symbol, self.chains, self.target_dte)
            _logger.info(f'ShortStranglesOptionsStrategy nearest expiration: {str(self.nearest_exp)}, nearest dte: {str(self.nearest_dte)}')

            # get the ATM option contract string
            atm_contract_str = OptionsUtil.make_contract_str(k.full_symbol, 'OPT', self.nearest_exp.strftime('%Y%m%d'), str(round(k.price)), 'C', 'SMART')
            _logger.info(f'ShortStranglesOptionsStrategy ATM contract string: {atm_contract_str}')

            # get the necessary option contract data
            atm_data = self.request_option_contract_data(atm_contract_str)

            # get the implied volatility for the ATM option
            self.iv = OptionsUtil.get_chain_iv("py_vollib", atm_data, k.price, self.nearest_dte, 'C')
            _logger.info(f'ShortStranglesOptionsStrategy implied volatility: {str(self.iv)}')

            # get the strike price for the options with the given delta
            call_strike = OptionsUtil.get_strike(k.price, self.target_delta, self.nearest_dte, self.iv, 'C', 'up', rounding=5.0)
            _logger.info(f'OrderPerIntervalStrategy call strike: {str(int(call_strike))}')
            put_strike = OptionsUtil.get_strike(k.price, self.target_delta, self.nearest_dte, self.iv, 'P', 'down', rounding=5.0)
            _logger.info(f'OrderPerIntervalStrategy put strike: {str(int(put_strike))}')

            # get the option contract strings
            call_contract_str = OptionsUtil.make_contract_str(k.full_symbol, 'OPT', self.nearest_exp.strftime('%Y%m%d'), str(int(call_strike)), 'C', 'SMART')
            put_contract_str = OptionsUtil.make_contract_str(k.full_symbol, 'OPT', self.nearest_exp.strftime('%Y%m%d'), str(int(put_strike)), 'P', 'SMART')

            # TODO: grab the contract details for the call and put options from the broker class, pass through the base and manager classes
            # TODO: make an order event in the form of a bag using the conID's from the contract details and pass it to place_order(o)
            # TODO: add a on_fill method to handle the in_trade boolean, stops, and take profits
            # TODO: add a managment method for managing the trade at 21 DTE

