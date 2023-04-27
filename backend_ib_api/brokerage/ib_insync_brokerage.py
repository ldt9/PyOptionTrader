#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .brokerage_base import BrokerageBase
from ..event.event import LogEvent
from ..account import AccountEvent
from ..data import TickEvent, TickType, BarEvent
from ..order.order_type import OrderType
from ..order.fill_event import FillEvent
from ..order.order_event import OrderEvent
from ..order.order_status import OrderStatus
from ..position.position_event import PositionEvent
from datetime import datetime
from copy import copy
from threading import Thread
import logging
import sys
import ib_insync as ibi
from ib_insync import *
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import nest_asyncio

_logger = logging.getLogger(__name__)


class InteractiveBrokers(BrokerageBase):
    def __init__(self, msg_event_engine, tick_event_engine, account: str):
        """
        Initialize InteractiveBrokers brokerage.

        Currently, the client is strongly coupled to broker without an incoming queue,
        e.g. client calls broker.place_order to place order directly.

        :param msg_event_engine:  used to broadcast messages the broker generates back to client
        :param tick_event_engine:  used to broadcast market data back to client
        :param account: the IB account
        """
        self.event_engine = msg_event_engine          # save events to event queue
        self.tick_event_engine = tick_event_engine
        self.api = ibi.IB()
        self.account = account
        self.contract_detail_request_contract_dict = {}        # reqid ==> contract
        self.contract_detail_request_symbol_dict = {}          # reqid ==> symbol
        self.sym_contract_dict = {}                            # sym ==> contract
        self.contract_symbol_dict = {}                           # conId ==> symbol
        self.market_data_subscription_dict = {}               # reqId ==> sym
        self.market_data_subscription_reverse_dict = {}       # sym ==> reqId
        self.market_data_tick_dict = {}          # reqid ==> tick_event; to combine tickprice and ticksize
        self.market_depth_subscription_dict = {}
        self.market_depth_subscription_reverse_dict = {}
        self.market_depth_tick_dict = {}        # to combine tickprice and ticksize
        self.hist_data_request_dict = {}
        self.order_dict = {}                            # order id ==> order_event
        self.account_summary_reqid = -1
        self.account_summary = AccountEvent()
        self.account_summary.brokerage = 'IB'
        self.clientid = 0
        self.reqid = 0           # next/available reqid
        self.orderid = 0         # next/available orderid

    def connect(self, host='127.0.0.1', port=7497, clientId=0):
        """
        Connect to IB. Request open orders under clientid upon successful connection.

        :param host: host address
        :param port: socket port
        :param clientId: client id
        """
        max_attempts = 60
        current_reconnect = 0
        delaySecs = 60
        while not self.api.isConnected():
            try:
                self.api.connect(host=host, port=port, clientId=clientId, timeout=5)
                if self.api.isConnected():
                    self.clientid = clientId
                    _logger.info(f'Connected to IBKR: {self.api.isConnected()}')
                    current_reconnect = 0
                    self.api.reqAllOpenOrders()
                    self.api.reqCurrentTime()
                    return
            except Exception as err:
                _logger.info(f"Connection exception: ", err)
                if current_reconnect < max_attempts:
                    current_reconnect += 1
                    _logger.info(f'Connect {current_reconnect} failed')
                    _logger.info(f'Retrying in {delaySecs} seconds, attempt {current_reconnect} of max {max_attempts}')
                    self.api.sleep(delaySecs)
                else:
                    sys.exit(f"Reconnect Failure after {max_attempts} tries")

    def disconnect(self):
        """
        Disconnect from IB
        """
        if not self.api.isConnected():
            return

        self.api.disconnect()
        _logger.info(f'Connected to IBKR: {self.api.isConnected()}')

    def _calculate_commission(self, full_symbol, fill_price, fill_size):
        pass

    def next_order_id(self):
        """
        Return next available order id

        :return: next order id available for next orders
        """
        return self.orderid

    def place_order(self, order_event):
        """
        Place order to IB

        :param order_event: client order to be placed
        :return: no return. An order event is pushed to message queue with order status Acknowledged
        """
        if not self.api.isConnected():
            return

        ib_contract = InteractiveBrokers.symbol_to_contract(order_event.full_symbol)
        if not ib_contract:
            _logger.error(f'Failed to find contract to place order {order_event.full_symbol}')
            return

        ib_order = InteractiveBrokers.order_to_ib_order(order_event)
        if not ib_order:
            _logger.error(f'Failed to create order to place {order_event.full_symbol}')
            return

        if order_event.order_id < 0:
            order_event.order_id = self.orderid
            self.orderid += 1
        order_event.account = self.account
        order_event.timestamp = datetime.now().strftime("%H:%M:%S.%f")
        order_event.order_status = OrderStatus.ACKNOWLEDGED       # acknowledged
        self.order_dict[order_event.order_id] = order_event
        _logger.info(f'Order acknowledged {order_event.order_id}, {order_event.full_symbol}')
        self.event_engine.put(copy(order_event))
        self.api.placeOrder(ib_contract, ib_order)

    def cancel_order(self, order_id):
        """
        Cancel client order.

        :param order_id: order id of the order to be canceled
        :return: no return. If order is successfully canceled, IB will return an orderstatus message.
        """
        if not self.api.isConnected():
            return

        if not order_id in self.order_dict.keys():
            _logger.error(f'Order to cancel not found. order id {order_id}')
            return

        self.order_dict[order_id].cancel_time = datetime.now().strftime("%H:%M:%S.%f")
        self.api.cancelOrder(order_id)  # Note: Not sure if ib_insync can cancel orders this way

    def cancel_all_orders(self):
        """
        Cancel all standing orders, for example, before one wants to shut down completely for some reasons.

        """
        self.api.reqGlobalCancel()

    def subscribe_market_data(self, sym):
        """
        Subscribe market L1 data. Market data for this symbol will then be streamed to client.

        :param sym: the symbol to be subscribed.
        """
        if not self.api.isConnected():
            return

        # it's not going to re-subscribe, because we only call subscribe_market_datas
        # if sym in self.market_data_subscription_reverse_dict.keys():
        #     return

        contract = InteractiveBrokers.symbol_to_contract(sym)
        if not contract:
            _logger.error(f'Failed to find contract to subscribe market data: {sym}')
            return

        self.api.reqContractDetails(contract)
        _logger.info(f'Requesting market data {self.reqid} {sym}')
        self.contract_detail_request_contract_dict[self.reqid] = contract
        self.contract_detail_request_symbol_dict[self.reqid] = sym
        self.reqid += 1
        self.api.reqMktData(contract, '', False, False, [])
        tick_event = TickEvent()
        tick_event.full_symbol = sym
        self.market_data_subscription_dict[self.reqid] = sym
        self.market_data_subscription_reverse_dict[sym] = self.reqid
        self.market_data_tick_dict[self.reqid] = tick_event
        self.reqid += 1

    def subscribe_market_datas(self):
        """
        Subscribe market L1 data for all symbols used in strategies. Market data for this symbol will then be streamed to client.

        """
        syms = list(self.market_data_subscription_reverse_dict.keys())
        for sym in syms:
            self.subscribe_market_data(sym)

    def unsubscribe_market_data(self, sym):
        """
        Unsubscribe market L1 data. Market data for this symbol will stop streaming to client.

        :param sym: the symbol to be subscribed.
        """
        if not self.api.isConnected():
            return

        if not sym in self.market_data_subscription_reverse_dict.keys():
            return

        self.api.cancelMktData(self.market_data_subscription_reverse_dict[sym])

    def subscribe_market_depth(self, sym):
        """
        Subscribe market L2 data. Market data for this symbol will then be streamed to client.

        :param sym: the symbol to be subscribed.
        """
        if not self.api.isConnected():
            return

        if sym in self.market_depth_subscription_reverse_dict.keys():
            return

        contract = InteractiveBrokers.symbol_to_contract(sym)
        if not contract:
            _logger.error(f'Failed to find contract to subscribe market depth: {sym}')
            return

        self.api.reqMktDepth(contract, 5, True)
        self.reqid += 1
        self.market_depth_subscription_dict[self.reqid] = sym
        self.market_depth_subscription_reverse_dict[sym] = self.reqid

    def unsubscribe_market_depth(self, sym):
        """
        Unsubscribe market L2 data. Market data for this symbol will stop streaming to client.

        :param sym: the symbol to be subscribed.
        """
        if not self.api.isConnected():
            return

        if not sym in self.market_depth_subscription_reverse_dict.keys():
            return

        self.api.cancelMktDepth(self.market_depth_subscription_reverse_dict[sym], True)

    def subscribe_account_summary(self):
        """
        Request account summary from broker
        """
        if not self.api.isConnected():
            return

        if self.account_summary_reqid > 0:    # subscribed
            return

        self.account_summary_reqid = self.reqid
        self.api.reqAccountSummary()
        self.reqid += 1

    def unsubscribe_account_summary(self):
        """
        Stop receiving account summary from broker
        """
        if not self.api.isConnected():
            return

        if self.account_summary_reqid == -1:
            return

        _logger.warning(f'ib-insync does not have a cancelAccountSummary method.')
        # self.api.cancelAccountSummary(self.account_summary_reqid)
        self.account_summary_reqid = -1

    def subscribe_positions(self):
        """
        Request existing positions from broker
        """
        self.api.reqPositions()

    def unsubscribe_positions(self):
        """
        Stop receiving existing position message from broker.
        """
        _logger.warning(f'ib-insync does not have a cancelPositions method.')
        # self.api.cancelPositions()

    def request_options_chain(self, symbol):
        """
        Retrieve options chain data. Options chain data for this symbol will then be streamed to client.
        (Only works for stocks)

        TODO: Implement for futures options

        :param symbol: the symbol to get options chain data for
        :return: chain: the options chain data
        """
        if not self.api.isConnected():
            return

        # Find contract id in the contract symbol dictionary on initialized assets
        conid = 0
        for key, value in self.contract_symbol_dict.items():
            if value == symbol:
                conid = key
                break
        if conid == 0:
            _logger.error(f'Failed to find contract id to subscribe options chain: {symbol}')
            return

        # request options chain data
        try:
            contract = symbol.split(' ')
            chain = self.api.reqSecDefOptParams(self.reqid, contract[0], '', contract[1], conid)
            self.reqid += 1
            return chain
        except Exception as e:
            _logger.error(f'Failed to request options chain for {symbol}: {e}')
            return None

    def request_historical_data(self, symbol, end=None):
        """
        Request 1800 S (30 mins) historical bar data from Interactive Brokers.

        :param symbol: the contract whose historical data is requested
        :param end: the end time of the historical data
        :return: no returns; data is broadcasted through message queue
        """
        ib_contract = InteractiveBrokers.symbol_to_contract(symbol)

        if end:
            end_str = end.strftime("%Y%m%d %H:%M:%S")
        else:
            end_str = ''

        self.hist_data_request_dict[self.reqid] = symbol
        self.api.reqHistoricalData(ib_contract, end_str, '1800 S', '1 secs', 'TRADES', False, 1, True, [])  # first 1 is useRTH
        self.reqid += 1

    def cancel_historical_data(self, bars: BarDataList):
        """
        Cancel historical data request. Usually not necessary.

        :param bars: the historical data requested
        """
        self.api.cancelHistoricalData(bars)

    def request_historical_ticks(self, symbol, start_time, reqtype='TICKS'):
        """
        Request historical time and sales data from Interactive Brokers.
        See here https://interactivebrokers.github.io/tws-api/historical_time_and_sales.html

        :param symbol: the contract whose historical data is requested
        :param start_time:  i.e. "20170701 12:01:00". Uses TWS timezone specified at login
        :param reqtype: TRADES, BID_ASK, or MIDPOINT
        :return: no returns; data is broadcasted through message queue
        """
        ib_contract = InteractiveBrokers.symbol_to_contract(symbol)
        self.hist_data_request_dict[self.reqid] = symbol
        self.api.reqHistoricalTicks(ib_contract, start_time, "", 1000, reqtype, True, True, [])
        self.reqid += 1

    def reqCurrentTime(self):
        """
        Request server time on broker side
        """
        self.api.reqCurrentTime()

    def heartbeat(self):
        """
        Request server time as heartbeat
        """
        if self.api.isConnected():
            _logger.info('reqPositions')
            # self.api.reqPositions()
            self.reqCurrentTime()     # EWrapper::currentTime

    def log(self, msg):
        """
        Broadcast server log message through message queue

        :param msg: message to be broadcast
        :return: no return; log meesage is placed into message queue
        """
        timestamp = datetime.now().strftime("%H:%M:%S.%f")
        log_event = LogEvent()
        log_event.timestamp = timestamp
        log_event.content = msg
        self.event_engine.put(log_event)

#---------------------------------------------------------------------------------------------------

    @staticmethod
    def symbol_to_contract(symbol):
        """
        Convert full symbol string to IB contract

        TODO
        CL.HO BAG 174230608 1 NYMEX 257430162 1 NYMEX NYMEX     # Inter-comdty
        ES.NQ BAG 371749798 1 GLOBEX 371749745 1 GLOBEX GLOBEX     # Inter-comdty
        CL.HO BAG 257430162 1 NYMEX 174230608 1 NYMEX NYMEX

        :param symbol: full symbol, e.g. AMZN STK SMART
        :return: IB contract
        """
        symbol_fields = symbol.split(' ')
        ib_contract = Contract()

        if symbol_fields[1] == 'STK':
            # ib_contract = Stock(symbol_fields[0], symbol_fields[2], 'USD')
            ib_contract.localSymbol = symbol_fields[0]
            ib_contract.secType = symbol_fields[1]
            ib_contract.currency = 'USD'
            ib_contract.exchange = symbol_fields[2]
        elif symbol_fields[1] == 'CASH':
            ib_contract.symbol = symbol_fields[0][0:3]     # EUR
            ib_contract.secType = symbol_fields[1]          # CASH
            ib_contract.currency = symbol_fields[0][3:]  # GBP
            ib_contract.exchange = symbol_fields[2]      # IDEALPRO
        elif symbol_fields[1] == 'FUT':
            ib_contract.localSymbol = symbol_fields[0].replace('_', ' ')   # ESM9, in case YM___SEP_20
            ib_contract.secType = symbol_fields[1]      # FUT
            ib_contract.exchange = symbol_fields[2]     # GLOBEX
            ib_contract.currency = 'USD'
        elif symbol_fields[1] == 'OPT':        # AAPL OPT 20201016 128.75 C SMART
            ib_contract.symbol = symbol_fields[0]       # AAPL
            ib_contract.secType = symbol_fields[1]        # OPT
            ib_contract.lastTradeDateOrContractMonth = symbol_fields[2]  # 20201016
            ib_contract.strike = float(symbol_fields[3]) if '.' in symbol_fields[3] else int(symbol_fields[3])      # 128.75
            ib_contract.right = symbol_fields[4]      # C
            ib_contract.exchange = symbol_fields[5]         # SMART
            ib_contract.currency = 'USD'
            ib_contract.multiplier = '100'
        elif symbol_fields[1] == 'FOP':                 # ES FOP 20200911 3450 C 50 GLOBEX
            ib_contract.symbol = symbol_fields[0]       # ES
            ib_contract.secType = symbol_fields[1]        # FOP
            ib_contract.lastTradeDateOrContractMonth = symbol_fields[2]  # 20200911
            ib_contract.strike = float(symbol_fields[3]) if '.' in symbol_fields[3] else int(symbol_fields[3])      # 128.75
            ib_contract.right = symbol_fields[4]      # C
            ib_contract.multiplier = symbol_fields[5]        # 50
            ib_contract.exchange = symbol_fields[6]         # GLOBEX
            ib_contract.currency = 'USD'
        elif symbol_fields[1] == 'CMDTY':               # XAUUSD CMDTY SMART
            ib_contract.symbol = symbol_fields[0]           # XAUUSD
            ib_contract.secType = symbol_fields[1]               # COMDTY
            ib_contract.currency = 'USD'
            ib_contract.exchange = symbol_fields[2]        # SMART
        elif symbol_fields[1] == 'BAG':
            ib_contract.symbol = symbol_fields[0]       # CL.BZ
            ib_contract.secType = symbol_fields[1]        # BAG

            leg1 = ComboLeg()
            leg1.conId = int(symbol_fields[2])          # 174230608
            leg1.ratio = int(symbol_fields[3])          # 1
            leg1.action = "BUY"
            leg1.exchange = symbol_fields[4]            # NYMEX

            leg2 = ComboLeg()
            leg2.conId = int(symbol_fields[5])          # 162929662
            leg2.ratio = int(symbol_fields[6])          # 1
            leg2.action = "SELL"
            leg2.exchange = symbol_fields[7]            # NYMEX

            ib_contract.comboLegs = []
            ib_contract.comboLegs.append(leg1)
            ib_contract.comboLegs.append(leg2)

            ib_contract.exchange = symbol_fields[8]         # NYMEX
            ib_contract.currency = 'USD'
        else:
            _logger.error(f'invalid contract {symbol}')

        return ib_contract

    @staticmethod
    def contract_to_symbol(ib_contract):
        """
        Convert IB contract to full symbol

        :param ib_contract: IB contract
        :return: full symbol
        """
        full_symbol = ''
        if ib_contract.secType == 'STK':
            full_symbol = ' '.join([ib_contract.localSymbol, 'STK', 'SMART'])    # or ib_contract.primaryExchange?
        elif ib_contract.secType == 'CASH':
            full_symbol = ' '.join([ib_contract.symbol+ib_contract.currency, 'CASH', ib_contract.exchange])
        elif ib_contract.secType == 'FUT':
            full_symbol = ' '.join([ib_contract.localSymbol.replace(' ', '_'), 'FUT',
                                    ib_contract.primaryExchange if ib_contract.primaryExchange != ''
                                    else ib_contract.exchange])
        elif ib_contract.secType == 'OPT':
            full_symbol = ' '.join([
                ib_contract.symbol, 'OPT', ib_contract.lastTradeDateOrContractMonth,
                str(ib_contract.strike), ib_contract.right, 'SMART'
            ])
        elif ib_contract.secType == 'FOP':
            full_symbol = ' '.join([
                ib_contract.symbol, 'FOP', ib_contract.lastTradeDateOrContractMonth,
                str(ib_contract.strike), ib_contract.right, ib_contract.multiplier, ib_contract.exchange
            ])
        elif ib_contract.secType == 'COMDTY':
            full_symbol = ' '.join([ib_contract.symbol, 'COMDTY', 'SMART'])
        elif ib_contract.secType == 'BAG':
            full_symbol = ' '.join([ib_contract.symbol, 'COMDTY', 'SMART'])

        return full_symbol


    @staticmethod
    def order_to_ib_order(order_event):
        """
        Convert order event to IB order

        :param order_event: internal representation of order
        :return:  IB representation of order
        """
        ib_order = Order()
        ib_order.action = 'BUY' if order_event.order_size > 0 else 'SELL'
        ib_order.totalQuantity = abs(order_event.order_size)
        if order_event.order_type == OrderType.MARKET:
            ib_order.orderType = 'MKT'
        elif order_event.order_type == OrderType.LIMIT:
            ib_order.orderType = 'LMT'
            ib_order.lmtPrice = order_event.limit_price
        elif order_event.order_type == OrderType.STOP:
            ib_order.orderType = 'STP'
            ib_order.auxPrice = order_event.stop_price
        elif order_event.order_type == OrderType.STOP_LIMIT:
            ib_order.orderType = 'STP LMT'
            ib_order.lmtPrice = order_event.limit_price
            ib_order.auxPrice = order_event.stop_price
        else:
            return None

        return ib_order

    @staticmethod
    def ib_order_to_order(ib_order):
        """
        Convert IB order to order event

        :param ib_order: IB representation of order
        :return: internal representation of order
        """
        order_event = OrderEvent()
        # order_event.order_id = orderId
        # order_event.order_status = orderState.status
        direction = 1 if ib_order.action == 'BUY' else -1
        order_event.order_size = ib_order.totalQuantity * direction
        if ib_order.orderType == 'MKT':
            order_event.order_type = OrderType.MARKET
        elif ib_order.orderType == 'LMT':
            order_event.order_type = OrderType.LIMIT
            order_event.limit_price = ib_order.lmtPrice
        elif ib_order.orderType == 'STP':
            order_event.order_type = OrderType.STOP
            order_event.stop_price = ib_order.auxPrice
        elif ib_order.orderType == 'STP LMT':
            order_event.order_type = OrderType.STOP_LIMIT
            order_event.limit_price = ib_order.lmtPrice
            order_event.stop_price = ib_order.auxPrice
        else:
            order_event.order_type = OrderType.UNKNOWN
            order_event.limit_price = ib_order.lmtPrice
            order_event.stop_price = ib_order.auxPrice

        return order_event
