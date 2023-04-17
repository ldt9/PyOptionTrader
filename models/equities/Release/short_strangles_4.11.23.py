# Imports
import logging
import sys
import ib_insync as ibi
import pandas as pd
import numpy as np
import py_vollib_vectorized
from ib_insync import *
from py_vollib_vectorized import price_dataframe
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import nest_asyncio

class ShortStrangles:

    '''
    This class is designed to create a short strangle strategy.
    Sell 1 call and 1 put, each at the 16 delta at the monthly expiration closest to 45DTE.
    Close at 50% gain, 200% loss, or 21 days left to expiration.

    These parameters are configurable in the trade_strangle() function.
    '''

    def __init__(self):
        print(f"{self.get_timestamp()} Initializing Options Strategy...")

        # Instantiate local vars
        self.ib = ibi.IB()
        self._logger = logging.getLogger(__name__)
        self.bar_count = 0
        self.underlying = None
        self.data = None
        self.df = None
        self.chains = None
        self.in_trade = False
        self.order_placed = False
        self.strangle = None
        self.short_call = None
        self.short_put = None
        self.currentIV = 0.0
        self.nearestDTE = None
        self.daysToexp = 0.0
        self.lastEstimatedTradePrice = 0.0
        self.takeProfitPrice = 0.0
        self.stopLossPrice = 0.0
        self.open_order_log = []
        self.previous_unique_orders = 0
        self.trade_log = []
        self.previous_unique_trades = 0

        # Run the main loop by connecting to IBKR
        self.connect_to_ibkr()

    # Initialize the class
    def connect_to_ibkr(self):
        # Connect to IB
        max_attempts = 60
        current_reconnect = 0
        delaySecs = 60
        while not self.ib.isConnected():
            try:
                self.ib.connect("127.0.0.1", port=7497, clientId=101, timeout=5)
                if self.ib.isConnected():
                    print(f'{self.get_timestamp()} Connected to IBKR')
                    current_reconnect = 0
                    break
            except Exception as err:
                print(f"{self.get_timestamp()} Connection exception: ", err)
                if current_reconnect < max_attempts:
                    current_reconnect += 1
                    print(f'{self.get_timestamp()} Connect failed')
                    print(f'{self.get_timestamp()} Retrying in {delaySecs} seconds, attempt {current_reconnect} of max {max_attempts}')
                    self.ib.sleep(delaySecs)
                else:
                    sys.exit(f"{self.get_timestamp()} Reconnect Failure after {max_attempts} tries")
        try:
            # Create Equity "Contract" for ticker to trade
            self.underlying = Stock('SPY', 'SMART', 'USD')

            # self.self.ib.reqMarketDataType(3) # delayed market data, comment out for real-time data
            self.ib.qualifyContracts(self.underlying)

            # Request Streaming Bars
            print(f"{self.get_timestamp()} Backfilling data...")
            self.data = self.ib.reqHistoricalData(self.underlying,
                                                  endDateTime='',
                                                  durationStr='1 D',
                                                  barSizeSetting='1 min',
                                                  whatToShow='TRADES',
                                                  useRTH=False,
                                                  keepUpToDate=True)

            # Debugging Data Import
            # self.df = util.df(self.data)
            # print(test_data)

            # Get current options chains
            self.chains = self.ib.reqSecDefOptParams(self.underlying.symbol, '', self.underlying.secType,
                                                     self.underlying.conId)
            # Update the chain every hour - can't update more frequently than this without asyncio issues
            update_chain_scheduler = BackgroundScheduler(job_defaults={'max_instances': 2})
            update_chain_scheduler.add_job(func=self.update_options_chains, trigger='cron', hour='*')
            update_chain_scheduler.start()

            print(f"{self.get_timestamp()} Running Live...")

            # Set callback function for events
            self.ib.disconnectedEvent += self.onDisconnected
            self.data.updateEvent += self.on_bar_update
            self.ib.execDetailsEvent += self.exec_status
            self.ib.openOrderEvent += self.on_open_order_update

            # Run the main loop
            util.patchAsyncio()
            nest_asyncio.apply()
            self.ib.run()

            # Every time this timer times out after a disconnect event
            # it will try to reconnect to IBKR...
            # To mitigate this, make this timer reallllllly long
            # It will still reconnect on disconnect events and pickup
            # the main loop where it left off, but make this sleep timer
            # long enough that it won't reconnect too often (ie. 50yrs)
            self.ib.sleep(60*60*365*50)
        except Exception as err:
            print("Problem running strategy code: ", err)

    def get_timestamp(self):
        # Get the current datetime
        now = datetime.datetime.now()
        # Format the datetime as a string with seconds
        timestamp = now.strftime("[%Y-%m-%d %I:%M:%S%p]")
        return timestamp

    def on_open_order_update(self, trade: Trade):
        # Add the order to the log
        conId = trade.contract.comboLegs[0].conId
        self.open_order_log.append(conId)
        # Count the current number of unique orders
        current_unique_orders = len(set(self.open_order_log))
        # Check if a new unique order is added
        if current_unique_orders > self.previous_unique_orders:
            print(f"{self.get_timestamp()} New Order Created")
            self.previous_unique_orders = current_unique_orders
            self.order_placed = not self.order_placed
            print(f"{self.get_timestamp()} Trade Placed")

    def onDisconnected(self):
        print(f"{self.get_timestamp()} Disconnect Event")
        print(f"{self.get_timestamp()} attempting restart and reconnect...")
        self.connect_to_ibkr()

    # Update the options chain
    def update_options_chains(self):

        '''
        Update the options chain to get the latest expiration dates and strikes
        :return: None
        '''

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print(f"{self.get_timestamp()} Updating Options Chains...")
            # Get current options chain
            self.chains = self.ib.reqSecDefOptParams(self.underlying.symbol, '', self.underlying.secType,
                                                     self.underlying.conId)
            print(f"{self.get_timestamp()} Options Chains Updated.")
            print(self.chains)
        except Exception as e:
            print(str(e))
            print(f"{self.get_timestamp()} Could not update options chains.")

    def update_target_expiration(self, days):

        '''
        Look for the chain with the nearest DTE expiration to days
        :param days: number of days until expiration
        '''

        try:
            # chain = next(c for c in self.chains if c.tradingClass == 'SPX' and c.exchange == 'SMART') # for index
            chain = next(c for c in self.chains if c.exchange == 'SMART')  # for stock

            # get the nearest monthly expiration
            targetDTE = datetime.date.today() + datetime.timedelta(days=days)

            # convert chain.expirations to datetime.date
            expire = [datetime.datetime.strptime(exp, '%Y%m%d').date() for exp in chain.expirations]

            # find the nearest monthly expiration in chain.expirations to targetDTE
            self.nearestDTE = min(expire, key=lambda x: abs(x - targetDTE))

            # find the number of days until the nearest monthly expiration
            self.daysToexp = (self.nearestDTE - datetime.date.today()).days / 365
            print(f"{self.get_timestamp()} Days to expiration: ", round(self.daysToexp * 365), " days")
            print(f"{self.get_timestamp()} Expiration date: ", self.nearestDTE)
        except Exception as e:
            print(str(e))
            print(f"{self.get_timestamp()} Could not update target expiration.")

    def get_strike(self, delta=0.16, option_type='C', call_strike_rounding='up', put_strike_rounding='down'):

        '''
        Get the strike price for the option with the given delta
        :param delta: delta of the option we want to order
        :param option_type: type of option (call or put)
        :param call_strike_rounding: rounding method for call strike
        :param put_strike_rounding: rounding method for put strike
        :return: the strike price of the desired option
        '''

        try:
            optionToTrade = 0
            for i in range(0, 1000):
                option = pd.DataFrame()
                if option_type == 'C':
                    option['Flag'] = ['c']  # 'c' for call
                else:
                    option['Flag'] = ['p']  # 'p' for put
                option['S'] = self.df.close.iloc[-1]  # Underlying asset price
                if option_type == 'C':
                    option['K'] = [round(self.df.close.iloc[-1]) + i]  # Strike(s)
                else:
                    option['K'] = [round(self.df.close.iloc[-1]) - i]  # Strike(s)
                option['T'] = self.daysToexp  # (Annualized) time-to-expiration
                option['R'] = 0.00  # Interest free rate
                option['IV'] = self.currentIV  # Implied Volatility
                result = price_dataframe(option, flag_col='Flag', underlying_price_col='S', strike_col='K',
                                         annualized_tte_col='T',
                                         riskfree_rate_col='R', sigma_col='IV', model='black_scholes',
                                         inplace=False)
                if option_type == 'C':
                    if result['delta'][0] <= delta:  # call delta is positive
                        print(f"{self.get_timestamp()} Call Greeks:")
                        print(result)
                        print(f"{self.get_timestamp()} Raw Call Strike to Trade: ", option['K'][0])
                        if call_strike_rounding == 'up':
                            optionToTrade = int(np.ceil(option['K'][0] / 5)) * 5
                        elif call_strike_rounding == 'down':
                            optionToTrade = int(np.floor(option['K'][0] / 5)) * 5
                        else:
                            optionToTrade = int(round(option['K'][0]))
                        print(f"{self.get_timestamp()} Call Strike to Trade: ", optionToTrade)
                        break
                else:
                    if result['delta'][0] >= delta:  # put delta is negative
                        print(f"{self.get_timestamp()} Put Greeks:")
                        print(result)
                        print(f"{self.get_timestamp()} Raw Put Strike to Trade: ", option['K'][0])
                        if put_strike_rounding == 'up':
                            optionToTrade = int(np.ceil(option['K'][0] / 5)) * 5
                        elif put_strike_rounding == 'down':
                            optionToTrade = int(np.floor(option['K'][0] / 5)) * 5
                        else:
                            optionToTrade = int(round(option['K'][0]))
                        print(f"{self.get_timestamp()} Put Strike to Trade: ", optionToTrade)
                        break
            return optionToTrade
        except Exception as e:
            print(str(e))
            print(f"{self.get_timestamp()} Could not get strike.")

    def get_chain_iv(self, nearestDTE):

        '''
        Get the IV of the option with the given strike
        :param nearestDTE: expiration date of the chain
        '''

        try:
            # Create an ATM call contract to get the current IV of the chain
            atmCall = Option(self.underlying.symbol, nearestDTE, int(np.ceil(self.df.close.iloc[-1] / 5)) * 5, 'C',
                             'SMART')
            self.ib.qualifyContracts(atmCall)
            atmCallPrices = self.ib.reqHistoricalData(atmCall,
                                                      endDateTime='',
                                                      durationStr='60 s',
                                                      barSizeSetting='1 secs',
                                                      whatToShow='MIDPOINT',
                                                      useRTH=False,
                                                      keepUpToDate=True, )
            atmCallPricesdf = util.df(atmCallPrices)
            atmCallPrice = round(np.nanmean(atmCallPricesdf['close']), 2)
            print(f"{self.get_timestamp()} ATM Call Price: ", atmCallPrice)

            # calculate the current IV of the chain using the ATM call price
            self.currentIV = py_vollib_vectorized.vectorized_implied_volatility_black(atmCallPrice,
                                                                                      self.df.close.iloc[-1],
                                                                                      int(np.ceil(self.df.close.iloc[
                                                                                                      -1] / 5) * 5),
                                                                                      0.00, self.daysToexp, 'c',
                                                                                      return_as='numpy')
            print(f"{self.get_timestamp()} Current IV: ", str(self.currentIV))
        except Exception as e:
            print(str(e))
            print(f"{self.get_timestamp()} Could not get chain IV.")

    def find_strangle(self, call_delta=0.16, put_delta=-0.16, order='SELL'):

        '''
        Get the specified delta call and put to trade at that expiration
        Get only 1 contract of each
        :param call_delta: delta of the call we want to order
        :param put_delta: delta of the put we want to order
        :param order: whether we are buying or selling the option
        '''

        try:
            # Get the current IV of the chain expiration
            nearestDTE = self.nearestDTE.strftime('%Y%m%d')
            self.get_chain_iv(nearestDTE=nearestDTE)

            # get the call strike to sell
            callToTrade = self.get_strike(delta=call_delta, option_type='C')

            # get the put strike to sell
            putToTrade = self.get_strike(delta=put_delta, option_type='P')

            # print the strikes to sell
            print(f"{self.get_timestamp()} Call to trade: ", callToTrade)
            print(f"{self.get_timestamp()} Put to trade: ", putToTrade)

            # make the option contracts
            self.short_call = Option(self.underlying.symbol, nearestDTE, callToTrade, 'C', 'SMART', '100', 'USD')
            self.short_put = Option(self.underlying.symbol, nearestDTE, putToTrade, 'P', 'SMART', '100', 'USD')
            self.ib.qualifyContracts(self.short_call)
            self.ib.qualifyContracts(self.short_put)
            print(f"{self.get_timestamp()} Call and Put Contracts Qualified")

            # make the combo order
            self.strangle = Contract()
            self.strangle.symbol = self.short_call.symbol
            self.strangle.secType = 'BAG'
            self.strangle.currency = self.short_call.currency
            self.strangle.exchange = self.short_call.exchange

            # call leg
            leg1 = ComboLeg()
            leg1.conId = self.short_call.conId
            leg1.ratio = 1
            leg1.action = order
            leg1.exchange = self.short_call.exchange

            # put leg
            leg2 = ComboLeg()
            leg2.conId = self.short_put.conId
            leg2.ratio = 1
            leg2.action = order
            leg2.exchange = self.short_put.exchange

            self.strangle.comboLegs = [leg1, leg2]
            print(f"{self.get_timestamp()} Strangle Options Combo Order Created")

        except Exception as e:
            print(str(e))
            print(f"{self.get_timestamp()} Could not find strangle.")

    def place_order(self, contract, order_type='short', order_style='bracket', take_profit_factor=0.50,
                    stop_loss_factor=3.00, use_vix_position_sizing=True, quantity=1):

        '''
        Place an order for the strangle strategy:
        :param contract: contract to trade
        :param order_type: type of order to place (long or short)
        :param order_style: style of order to place (bracket, limit or market)
        :param take_profit_factor: how much to take profit at
        :param stop_loss_factor: how much to stop loss at
        :param use_vix_position_sizing: whether to use vix position sizing or not
        :param quantity: quantity of contracts to trade if not using VIX position sizing
        '''

        try:
            # get the market price of the combo order
            combobars = self.ib.reqHistoricalData(
                contract=contract,
                endDateTime='',
                durationStr='60 s',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1)
            combo = util.df(combobars)
            # catchall for debug purposes
            if not combo.empty:
                combobars = self.ib.reqHistoricalData(
                    contract=contract,
                    endDateTime='',
                    durationStr='60 s',
                    barSizeSetting='1 min',
                    whatToShow='MIDPOINT',
                    useRTH=True,
                    formatDate=1)
                combo = util.df(combobars)
            avg_price = round(np.nanmean(combo['close']), 2)
            print(f"{self.get_timestamp()} Order Price: ", avg_price)

            # send the order to IB as a bracket order with a stop loss and take profit
            if order_type == 'short': self.lastEstimatedTradePrice = round(avg_price * 0.995, 2)
            if order_type == 'long': self.lastEstimatedTradePrice = round(avg_price * 1.005, 2)
            self.takeProfitPrice = round(avg_price * take_profit_factor, 2)
            self.stopLossPrice = round(avg_price * stop_loss_factor, 2)
            what_if_order = LimitOrder('BUY', 1, self.lastEstimatedTradePrice)

            # create a what if order to see what our margin requirements are
            whatif = self.ib.whatIfOrder(contract, what_if_order)
            margin = float(whatif.initMarginChange)
            print(f"{self.get_timestamp()} Initial Margin: ", margin)

            # get the position size based on our account value and margin requirements
            acc_sum = self.ib.accountSummary()
            account_value = 0
            for av in acc_sum:
                if av.tag == 'AvailableFunds':
                    account_value = float(av.value)
                    print(f"{self.get_timestamp()} Account Value: ", account_value)

            # get the position size to default contract quantity if not using VIX position sizing
            position_size = quantity

            # get the position size based on VIX position sizing
            if use_vix_position_sizing:
                if 0.10 <= self.currentIV < 0.15:
                    position_size = int(np.floor(account_value * 0.25 / margin))
                    print(f"{self.get_timestamp()} IV is between 10 and 15...\n{self.get_timestamp()} Position size is 25% of account value\n{self.get_timestamp()} Trading {position_size} contracts")
                if 0.15 <= self.currentIV < 0.20:
                    position_size = int(np.floor(account_value * 0.30 / margin))
                    print(f"{self.get_timestamp()} IV is between 15 and 20...\n{self.get_timestamp()} Position size is 30% of account value\n{self.get_timestamp()} Trading {position_size} contracts")
                if 0.20 <= self.currentIV < 0.30:
                    position_size = int(np.floor(account_value * 0.35 / margin))
                    print(f"{self.get_timestamp()} IV is between 20 and 30...\n{self.get_timestamp()} Position size is 35% of account value\n{self.get_timestamp()} Trading {position_size} contracts")
                if 0.30 <= self.currentIV < 0.40:
                    position_size = int(np.floor(account_value * 0.40 / margin))
                    print(f"{self.get_timestamp()} IV is between 30 and 40...\n{self.get_timestamp()} Position size is 40% of account value\n{self.get_timestamp()} Trading {position_size} contracts")
                if self.currentIV >= 0.40:
                    position_size = int(np.floor(account_value * 0.50 / margin))
                    print(f"{self.get_timestamp()} IV is greater than 40...\n{self.get_timestamp()} Position size is 50% of account value\n{self.get_timestamp()} Trading {position_size} contracts")

            if order_style == 'bracket':
                IV_adjusted_bracket = self.ib.bracketOrder('BUY', position_size, self.lastEstimatedTradePrice,
                                                           self.takeProfitPrice,
                                                           self.stopLossPrice)
                for o in IV_adjusted_bracket:
                    self.ib.placeOrder(contract, o)
            elif order_style == 'limit':
                self.ib.placeOrder(contract, LimitOrder('BUY', position_size, self.lastEstimatedTradePrice))
            elif order_style == 'market':
                self.ib.placeOrder(contract, MarketOrder('BUY', position_size))
        except Exception as e:
            print(str(e))
            print(f"{self.get_timestamp()} Could not place order.")

    def trade_strangle(self, call_delta=0.16, put_delta=-0.16, order_type='short', order_style='bracket', days=45,
                       take_profit_factor=0.50, stop_loss_factor=3.00, use_vix_position_sizing=True, quantity=1):
        '''
        Trade the Strangle Options Strategy
        :param call_delta: delta of the call
        :param put_delta: delta of the put
        :param order_type: long or short
        :param order_style: bracket, limit or market
        :param days: how many days to expiration
        :param take_profit_factor: where to take profit on the premium
        :param stop_loss_factor: where to stop loss on the premium
        :param use_vix_position_sizing: whether to use vix position sizing or not
        :param quantity: how many to buy if we don't use vix position sizing
        :return: None
        '''

        try:
            self.update_target_expiration(days=days)

            order = 'BUY'
            if order_type == 'short':
                order = 'SELL'

            self.find_strangle(call_delta=call_delta, put_delta=put_delta, order=order)

            self.place_order(contract=self.strangle, order_type=order_type, order_style=order_style,
                             take_profit_factor=take_profit_factor, stop_loss_factor=stop_loss_factor,
                             use_vix_position_sizing=use_vix_position_sizing, quantity=quantity)
        except Exception as e:
            print(str(e))
            print(f"{self.get_timestamp()} Could not trade the strangle.")

    def manage_strangle(self):
        if self.in_trade:  # We are in a trade with no open orders
            '''
            If we are in a trade, we want to poll the position and
            close it if it is 21 DTE or less, the bracket order will
            take care of the take profit and stop loss
            '''
            # get the days to expiration
            daysToexp = (self.nearestDTE - datetime.date.today()).days

            # get the market price of the combo order
            combobars = self.ib.reqHistoricalData(
                contract=self.strangle,
                endDateTime='',
                durationStr='60 s',
                barSizeSetting='1 secs',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1)
            combo = util.df(combobars)
            curr_price = round(np.nanmean(combo['close']), 2)
            print(f"{self.get_timestamp()} Strangle Price: ", curr_price)

            # if the difference between self.nearestDTE and today is less than 21 days
            if daysToexp <= 21:
                print(f"{self.get_timestamp()} Closing Open Strangle Position...")
                # close the position
                # send the order to IB as a market order
                order = MarketOrder('SELL', 1)
                self.ib.placeOrder(self.strangle, order)
                print(f"{self.get_timestamp()} Position closed at 21DTE for a profit of $" + str(
                                                round(curr_price - self.lastEstimatedTradePrice, 2)))

                # Clean up and cancel all orders
                self.ib.reqGlobalCancel()

                # reset the local variables
                self.in_trade = not self.in_trade
                return
            else:
                print(f"{self.get_timestamp()} Position is still open...")
                print(f"{self.get_timestamp()} Days to expiration: ", round(daysToexp), " days")
                print(f"{self.get_timestamp()} Current Total Open Pnl: $" + str(
                                                round(curr_price - self.lastEstimatedTradePrice, 2)))
                return
        elif not self.in_trade and self.order_placed:  # Waiting on order fill
            print(f"{self.get_timestamp()} Waiting on order fill...")
            return
        else:  # Catch all... There's something wrong
            print(f"{self.get_timestamp()} Something went wrong...")
            return

    # On Bar Update, when we get new data
    def on_bar_update(self, bars: BarDataList, has_new_bar: bool):
        self.bar_count += 1
        if self.bar_count == 5:
            self.bar_count = 0
            try:
                print(f"{self.get_timestamp()} New Bar Received...")
                # Convert the BarDataList to a Pandas DataFrame
                self.df = util.df(self.data)
                # Check if we are in a trade and no open orders
                if not self.in_trade and not self.order_placed:
                    # Trade a strangle
                    self.trade_strangle(call_delta=0.16, put_delta=-0.16, order_type='short', order_style='bracket',
                                        take_profit_factor=0.50, stop_loss_factor=3.00, use_vix_position_sizing=False,
                                        quantity=1, days=45)
                else:
                    # Manage the strangle
                    self.manage_strangle()
            except Exception as e:
                print(str(e))
                print(f"{self.get_timestamp()} Could not update bars.")

    def exec_status(self, trade: Trade, fill: Fill):
        # Add the order to the log
        conId = trade.contract.comboLegs[0].conId
        self.trade_log.append(conId)
        # Count the current number of unique orders
        current_unique_trades = len(set(self.trade_log))
        # Check if a new unique order is added
        if current_unique_trades > self.previous_unique_trades:
            print(f"{self.get_timestamp()} New Trade Created")
            self.previous_unique_trades = current_unique_trades
            self.order_placed = not self.order_placed
            self.in_trade = not self.in_trade
            print(f"{self.get_timestamp()} Trade Executed: " + str(trade))
            print(f"{self.get_timestamp()} Fill: " + str(fill))


# create the bot
ShortStrangles()
