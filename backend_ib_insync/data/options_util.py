#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import logging

import numpy as np
import pandas as pd
import py_vollib_vectorized
from py_vollib_vectorized import price_dataframe

_logger = logging.getLogger(__name__)


class OptionsUtil(object):
    """
    Options utility functions
    """
    def __init__(self):
        pass

    @staticmethod
    def update_target_expiration(symbol: str, chains: dict, target_dte: int):
        """
        Update the target expiration date and days to expiration
        :param symbol: Asset Symbol
        :param chains: chains data requested for request_options_chain(symbol)
        :param target_dte: days out to expiration you are targeting
        :return: the nearest expiration date and days to expiration to the target
        """
        try:
            # get the nearest monthly expiration
            target_exp = datetime.date.today() + datetime.timedelta(days=target_dte)

            # convert the list of expirations to datetime objects
            expire = []
            for exp in list(chains['expirations']):
                try:
                    expire.append(datetime.datetime.strptime(exp, '%Y%m%d').date())
                except ValueError:
                    _logger.error(f"Could not convert {exp} to date")

            # find the nearest monthly expiration in chain.expirations to targetDTE
            nearest_exp = min(expire, key=lambda x: abs(x - target_exp))
            # _logger.info(f"Nearest expiration: {self.nearest_exp}")

            # find the number of days until the nearest monthly expiration
            nearest_dte = (nearest_exp - datetime.date.today()).days
            # _logger.info(f"Days to expiration: {str(self.nearest_dte)} days")
            return nearest_exp, nearest_dte
        except Exception as e:
            _logger.error(str(e))
            _logger.error(f"Could not update target expiration for {symbol}.")

    @staticmethod
    def make_contract_str(symbol: str, asset_type: str, exp: str, strike: str, right: str, exchange: str):
        """
        Make a contract string from the given parameters
        :param symbol: Asset Symbol
        :param asset_type: Asset Type
        :param exp: Expiration
        :param strike: Strike
        :param right: Right
        :param exchange: Exchange
        :return: contract string
        """
        try:
            contract_str = str(symbol.split(" ")[0]) + ' ' + str(asset_type) + ' ' + str(exp) + ' ' + str(strike) + ' ' + str(right) + ' ' + str(exchange)
            return contract_str
        except Exception as e:
            _logger.error(str(e))
            _logger.error(f"Could not make contract string for {symbol}.")

    @staticmethod
    def get_chain_iv(source: str, option_data: dict, spot_price: float, dte: int, right: str, rho=0.00):
        """
        Get the implied volatility for the given option chain
        :param source: get the volatility from ib or calculate it using py_vollib
        :param option_data: dictionary of options data gotten from request_options_contract_data(contract_str)
        :param spot_price: spot price of the asset
        :param dte: days to expiration
        :param right: call or put
        :param rho: risk free rate
        :return: implied volatility of the option chain
        """
        try:
            if source == 'ib':
                iv = option_data['ImpliedVolatility']
                return float(next(iter(iv)))
            elif source == 'py_vollib':
                price = option_data['OptionPrice']
                price = float(next(iter(price)))
                return py_vollib_vectorized.vectorized_implied_volatility_black(price,
                                                                                spot_price,
                                                                                int(np.ceil(spot_price / 5) * 5),
                                                                                rho, dte/365, right.lower(),
                                                                                return_as='numpy')
            else:
                _logger.error(f"Invalid type {source}.")
                return None
        except Exception as e:
            _logger.error(str(e))
            _logger.error(f"Could not get chain IV.")

    @staticmethod
    def get_strike(spot_price: float, delta: float, dte: int, iv: float, option_type: str, direction: str, rounding: float, rho=0.00):
        """
        Get the strike price for the option with the given delta
        :param spot_price: current price of the underlying asset
        :param delta: delta of the option we want to order
        :param dte: days to expiration of the option we want to order
        :param iv: implied volatility of the option we want to order
        :param option_type: type of option (call or put)
        :param direction: rounding direction (up or down)
        :param rounding: round puts and calls to nearest X
        :param rho: risk free interest rate
        :return: the strike price of the desired option
        """
        try:
            found = False
            optionToTrade = 0
            for i in range(0, 1000):
                option = pd.DataFrame()
                if option_type.lower() == 'c':
                    option['Flag'] = ['c']  # 'c' for call
                else:
                    option['Flag'] = ['p']  # 'p' for put
                option['S'] = spot_price  # Underlying asset price
                if option_type.lower() == 'c':
                    option['K'] = [round(spot_price) + i]  # Strike(s)
                else:
                    option['K'] = [round(spot_price) - i]  # Strike(s)
                option['T'] = dte/365  # (Annualized) time-to-expiration
                option['R'] = rho  # Interest free rate
                option['IV'] = iv  # Implied Volatility
                result = price_dataframe(option, flag_col='Flag', underlying_price_col='S', strike_col='K',
                                         annualized_tte_col='T', riskfree_rate_col='R', sigma_col='IV',
                                         model='black_scholes', inplace=False)
                if option_type.lower() == 'c':
                    if result['delta'][0] <= delta:  # call delta is positive
                        _logger.info(f"Call Greeks:")
                        optionToTrade = option['K'][0]
                        found = True
                else:
                    if result['delta'][0] >= delta * -1:  # put delta is negative
                        _logger.info(f"Put Greeks:")
                        optionToTrade = option['K'][0]
                        found = True
                if found:
                    _logger.info('\n' + result.to_string(index=False, justify='center'))
                    if direction == 'up':
                        optionToTrade = int(np.ceil(option['K'][0] / rounding)) * rounding
                    elif direction == 'down':
                        optionToTrade = int(np.floor(option['K'][0] / rounding)) * rounding
                    else:
                        optionToTrade = int(round(option['K'][0]))
                    break
            return optionToTrade
        except Exception as e:
            _logger.error(str(e))
            _logger.error(f"Could not get strike.")