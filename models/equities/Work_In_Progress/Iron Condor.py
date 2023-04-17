# Imports
import asyncio
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

class IronCondors():
    '''
    This class is designed to create an iron condor strategy.
    Sell 1 call and 1 put, and buy 1 further OTM call and 1 OTM put
    each at the specified delta at the specified DTE.
    Close at 50% gain, 100% loss or otherwise specified.

    These parameters are configurable in the trade_ironcondor() function.
    '''

    # Initialize the class
    def __init__(self):
        print("Initializing Options Strategy...")
        # Connect to IB
        try:
            self.ib = ibi.IB()
            self.ib.connect('localhost', 7497, clientId=101)  # Paper Trading through TWS
            # self.ib.connect('localhost', 4002, clientId=101) # Paper Trading through IB Gateway
            print("Connected to Interactive Brokers.")
        except Exception as e:
            print(str(e))
            print("Could not connect to Interactive Brokers.")

        # Create Equity "Contract" for ticker to trade
        self.underlying = Stock('SPY', 'SMART', 'USD')
        # self.ib.reqMarketDataType(3) # delayed market data, comment out for real-time data
        self.ib.qualifyContracts(self.underlying)

        print("Backfilling data...")
        # Request Streaming Bars
        self.data = self.ib.reqHistoricalData(self.underlying,
                                              endDateTime='',
                                              durationStr='2 D',
                                              barSizeSetting='1 min',
                                              whatToShow='TRADES',
                                              useRTH=False,
                                              keepUpToDate=True)

        # Debugging Data Import
        # self.df = util.df(self.data)
        # print(test_data)

        # Local Variables
        self.df = None
        self.in_trade = False
        self.order_placed = False
        self.ironcondor = None
        self.short_call = None
        self.short_put = None
        self.long_call = None
        self.long_put = None
        self.currentIV = 0.0
        self.nearestDTE = None
        self.daysToexp = 0.0
        self.lastEstimatedTradePrice = 0.0
        self.takeProfitPrice = 0.0
        self.stopLossPrice = 0.0

        # Get current options chains
        self.chains = self.ib.reqSecDefOptParams(self.underlying.symbol, '', self.underlying.secType,
                                                 self.underlying.conId)
        # Update the chain every hour - can't update more frequently than this without asyncio issues
        update_chain_scheduler = BackgroundScheduler(job_defaults={'max_instances': 1})
        update_chain_scheduler.add_job(func=self.update_options_chains, trigger='cron', hour='*')
        update_chain_scheduler.start()
        print("Running Live...")

        # Run the main loop
        nest_asyncio.apply()

        # Debug Trading Strangles
        # self.df = util.df(self.data)
        # self.trade_ironcondor(use_vix_position_sizing=False)
        # self.trade_ironcondor(short_call_delta=0.05, short_put_delta=-0.05, long_call_delta=0.50, long_put_delta=-0.50,
        #                       order_type='long', order_style='bracket', take_profit_factor=1.00, days=7,
        #                       stop_loss_factor=2.00, use_vix_position_sizing=False, quantity=1, trade_width=False,
        #                       short_option_qty=18, long_option_qty=1)

        # Set callback function for streaming bars
        self.data.updateEvent += self.on_bar_update
        self.ib.execDetailsEvent += self.exec_status

        # Run Forever
        self.ib.run()

    # Update the options chain
    def update_options_chains(self):

        '''
        Update the options chain to get the latest expiration dates and strikes
        :return: None
        '''

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("Updating Options Chains...")
            # Get current options chain
            self.chains = self.ib.reqSecDefOptParams(self.underlying.symbol, '', self.underlying.secType,
                                                     self.underlying.conId)
            print("Options Chains Updated.")
            print(self.chains)
        except Exception as e:
            print(str(e))
            print("Could not update options chains.")

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
            print("Days to expiration: ", round(self.daysToexp * 365), " days")
            print("Expiration date: ", self.nearestDTE)
        except Exception as e:
            print(str(e))
            print("Could not update target expiration.")

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
                        print("Call Greeks:")
                        print(result)
                        print("Raw Call Strike to Trade: ", option['K'][0])
                        if call_strike_rounding == 'up':
                            optionToTrade = int(np.ceil(option['K'][0] / 5)) * 5
                        elif call_strike_rounding == 'down':
                            optionToTrade = int(np.floor(option['K'][0] / 5)) * 5
                        else:
                            optionToTrade = int(round(option['K'][0]))
                        print("Call Strike to Trade: ", optionToTrade)
                        break
                else:
                    if result['delta'][0] >= delta:  # put delta is negative
                        print("Put Greeks:")
                        print(result)
                        print("Raw Put Strike to Trade: ", option['K'][0])
                        if put_strike_rounding == 'up':
                            optionToTrade = int(np.ceil(option['K'][0] / 5)) * 5
                        elif put_strike_rounding == 'down':
                            optionToTrade = int(np.floor(option['K'][0] / 5)) * 5
                        else:
                            optionToTrade = int(round(option['K'][0]))
                        print("Put Strike to Trade: ", optionToTrade)
                        break
            return optionToTrade
        except Exception as e:
            print(str(e))
            print("Could not get strike.")

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
            print("ATM Call Price: ", atmCallPrice)

            # calculate the current IV of the chain using the ATM call price
            self.currentIV = py_vollib_vectorized.vectorized_implied_volatility_black(atmCallPrice,
                                                                                      self.df.close.iloc[-1],
                                                                                      int(np.ceil(self.df.close.iloc[
                                                                                                      -1] / 5) * 5),
                                                                                      0.00, self.daysToexp, 'c',
                                                                                      return_as='numpy')
            print("Current IV: ", str(self.currentIV))
        except Exception as e:
            print(str(e))
            print("Could not get chain IV.")

    def find_iron_condor(self, short_call_delta=0.10, short_put_delta=-0.10, long_call_delta=0.02, long_put_delta=-0.02,
                         trade_width=True, call_spread_width=3, put_spread_width=3, short_option_qty=1,
                         long_option_qty=1, order='SELL'):

        '''
        Get the specified delta call and put to trade at that expiration
        Get only 1 contract of each
        :param short_call_delta: delta of the short call we want to order
        :param short_put_delta: delta of the short put we want to order
        :param long_call_delta: delta of the long call we want to order
        :param long_put_delta: delta of the long put we want to order
        :param trade_width: whether we are trading a width or a delta for the outside options
        :param call_spread_width: width of the call spread
        :param put_spread_width: width of the put spread
        :param short_option_qty: quantity of the short option
        :param long_option_qty: quantity of the long option
        :param order: whether we are buying or selling the option
        '''

        try:
            # Get the current IV of the chain expiration
            nearestDTE = self.nearestDTE.strftime('%Y%m%d')
            self.get_chain_iv(nearestDTE=nearestDTE)

            longcallToTrade = 0
            # get the call strike to sell
            shortcallToTrade = self.get_strike(delta=short_call_delta, option_type='C', call_strike_rounding='None')
            if trade_width:
                longcallToTrade = shortcallToTrade + call_spread_width
            else:
                longcallToTrade = self.get_strike(delta=long_call_delta, option_type='C', call_strike_rounding='None')

            longputToTrade = 0
            # get the put strike to sell
            shortputToTrade = self.get_strike(delta=short_put_delta, option_type='P', put_strike_rounding='None')
            if trade_width:
                longputToTrade = shortputToTrade - put_spread_width
            else:
                longputToTrade = self.get_strike(delta=long_put_delta, option_type='P', put_strike_rounding='None')

            # print the strikes to sell
            print("Call Spread to trade: " + str(shortcallToTrade) + "/" + str(longcallToTrade))
            print("Put Spread to trade: " + str(shortputToTrade) + "/" + str(longputToTrade))

            # make the option contracts
            self.short_call = Option(self.underlying.symbol, nearestDTE, shortcallToTrade, 'C', 'SMART', '100', 'USD')
            self.long_call = Option(self.underlying.symbol, nearestDTE, longcallToTrade, 'C', 'SMART', '100', 'USD')
            self.short_put = Option(self.underlying.symbol, nearestDTE, shortputToTrade, 'P', 'SMART', '100', 'USD')
            self.long_put = Option(self.underlying.symbol, nearestDTE, longputToTrade, 'P', 'SMART', '100', 'USD')
            self.ib.qualifyContracts(self.short_call)
            self.ib.qualifyContracts(self.long_call)
            self.ib.qualifyContracts(self.short_put)
            self.ib.qualifyContracts(self.long_put)
            print("Call and Put Contracts Qualified")

            # make the combo order
            self.ironcondor = Contract()
            self.ironcondor.symbol = self.short_call.symbol
            self.ironcondor.secType = 'BAG'
            self.ironcondor.currency = self.short_call.currency
            self.ironcondor.exchange = self.short_call.exchange

            # short call leg
            leg1 = ComboLeg()
            leg1.conId = self.short_call.conId
            leg1.exchange = self.short_call.exchange

            # long call leg
            leg2 = ComboLeg()
            leg2.conId = self.long_call.conId
            leg2.exchange = self.long_call.exchange

            # short put leg
            leg3 = ComboLeg()
            leg3.conId = self.short_put.conId
            leg3.exchange = self.short_put.exchange

            # short put leg
            leg4 = ComboLeg()
            leg4.conId = self.long_put.conId
            leg4.exchange = self.long_put.exchange

            # Route the Orders based on position order (short/long)
            if order == 'SELL':
                leg1.ratio = short_option_qty
                leg1.action = 'SELL'
                leg2.ratio = long_option_qty
                leg2.action = 'BUY'
                leg3.ratio = short_option_qty
                leg3.action = 'SELL'
                leg4.ratio = long_option_qty
                leg4.action = 'BUY'
            else:
                leg1.ratio = long_option_qty
                leg1.action = 'BUY'
                leg2.ratio = short_option_qty
                leg2.action = 'SELL'
                leg3.ratio = long_option_qty
                leg3.action = 'BUY'
                leg4.ratio = short_option_qty
                leg4.action = 'SELL'

            # add the legs to make a combo order
            self.ironcondor.comboLegs = [leg1, leg2, leg3, leg4]
            print("Iron Condor Options Combo Order Created")

        except Exception as e:
            print(str(e))
            print("Could not get chain IV.")

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
            if combo.empty:
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
            print("Order Price: ", avg_price)

            # send the order to IB as a bracket order with a stop loss and take profit
            if order_type == 'short': self.lastEstimatedTradePrice = round(avg_price * 0.995, 2)
            if order_type == 'long': self.lastEstimatedTradePrice = round(avg_price * 1.005, 2)
            self.takeProfitPrice = round(avg_price * take_profit_factor, 2)
            self.stopLossPrice = round(avg_price * stop_loss_factor, 2)
            what_if_order = LimitOrder('BUY', 1, self.lastEstimatedTradePrice)

            # create a what if order to see what our margin requirements are
            whatif = self.ib.whatIfOrder(contract, what_if_order)
            margin = float(whatif.initMarginChange)
            print("Initial Margin: ", margin)

            # get the position size based on our account value and margin requirements
            acc_sum = self.ib.accountSummary()
            account_value = 0
            for av in acc_sum:
                if av.tag == 'AvailableFunds':
                    account_value = float(av.value)
                    print("Account Value: ", account_value)

            # get the position size to default contract quantity if not using VIX position sizing
            position_size = quantity

            # get the position size based on VIX position sizing
            if use_vix_position_sizing:
                if 0.10 <= self.currentIV < 0.15:
                    position_size = int(np.floor(account_value * 0.25 / margin))
                    print("IV is between 10 and 15...\nPosition size is 25% of account value\nTrading {} contracts".format(
                        position_size))
                    print("Trade Placed")
                if 0.15 <= self.currentIV < 0.20:
                    position_size = int(np.floor(account_value * 0.30 / margin))
                    print("IV is between 15 and 20...\nPosition size is 30% of account value\nTrading {} contracts".format(
                        position_size))
                if 0.20 <= self.currentIV < 0.30:
                    position_size = int(np.floor(account_value * 0.35 / margin))
                    print("IV is between 20 and 30...\nPosition size is 35% of account value\nTrading {} contracts".format(
                        position_size))
                if 0.30 <= self.currentIV < 0.40:
                    position_size = int(np.floor(account_value * 0.40 / margin))
                    print("IV is between 30 and 40...\nPosition size is 40% of account value\nTrading {} contracts".format(
                        position_size))
                if self.currentIV >= 0.40:
                    position_size = int(np.floor(account_value * 0.50 / margin))
                    print("IV is greater than 40...\nPosition size is 50% of account value\nTrading {} contracts".format(
                        position_size))

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

            # set the trade to order placed
            self.order_placed = not self.order_placed
            print("Trade Placed")
        except Exception as e:
            print(str(e))
            print("Could not place order.")

    def manage_ironcondor(self):
        if self.in_trade:  # We are in a trade with no open orders
            # get the market price of the combo order
            combobars = self.ib.reqHistoricalData(
                contract=self.ironcondor,
                endDateTime='',
                durationStr='60 s',
                barSizeSetting='1 secs',
                whatToShow='MIDPOINT',
                useRTH=True,
                formatDate=1)
            combo = util.df(combobars)
            avg_price = round(np.nanmean(combo['close']), 2)
            print("Iron Condor Price: ", avg_price)
            return
        elif not self.in_trade and self.order_placed:  # Waiting on order fill
            print("Waiting on order fill...")
            return
        else:  # Catch all... There's something wrong
            print("Something went wrong...")
            return

    def trade_ironcondor(self, short_call_delta=0.10, short_put_delta=-0.10, long_call_delta=0.30, long_put_delta=-0.30,
                         call_spread_width=3, put_spread_width=3, order_type='short', order_style='bracket', days=0,
                         take_profit_factor=0.50, stop_loss_factor=2.00, use_vix_position_sizing=False, quantity=1,
                         short_option_qty=1, long_option_qty=1, trade_width=True):
        '''
        Trade the Iron Condor Options Strategy
        :param short_call_delta: call delta for our short call
        :param short_put_delta: put delta for our short put
        :param long_call_delta: call delta for our long call
        :param long_put_delta: put delta for our long put
        :param call_spread_width: width of the call spread
        :param put_spread_width: width of the put spread
        :param order_type: short or long
        :param order_style: bracket, limit or market
        :param days: usually 0 DTE but could be more if needed
        :param take_profit_factor: when to take profits
        :param stop_loss_factor: when to stop out
        :param use_vix_position_sizing: whether to use vix position sizing or not
        :param quantity: how many contracts to trade if we don't use vix position sizing
        :param short_option_qty: how many short options to trade
        :param long_option_qty: how many long options to trade
        :param trade_width: whether to trade the width of the spread or trade delta of the long options
        :return: None
        '''

        try:
            self.update_target_expiration(days=days)

            order = 'BUY'
            if order_type == 'short':
                order = 'SELL'

            self.find_iron_condor(short_call_delta=short_call_delta, short_put_delta=short_put_delta,
                                  long_call_delta=long_call_delta, long_put_delta=long_put_delta, trade_width=trade_width,
                                  call_spread_width=call_spread_width, put_spread_width=put_spread_width, order=order,
                                  short_option_qty=short_option_qty, long_option_qty=long_option_qty)

            self.place_order(contract=self.ironcondor, order_type=order_type, order_style=order_style,
                             take_profit_factor=take_profit_factor, stop_loss_factor=stop_loss_factor,
                             use_vix_position_sizing=use_vix_position_sizing, quantity=quantity)
        except Exception as e:
            print(str(e))
            print("Could not trade the iron condor.")

    # On Bar Update, when we get new data
    def on_bar_update(self, bars: BarDataList, has_new_bar: bool):
        try:
            if has_new_bar:
                # Convert the BarDataList to a Pandas DataFrame
                self.df = util.df(bars)
                # Check if we are in a trade and no open orders
                if not self.in_trade and not self.order_placed:
                    # Trade a 0 DTE iron condor
                    self.trade_ironcondor(short_call_delta=0.10, short_put_delta=-0.10, call_spread_width=25, put_spread_width=25,
                                          order_type='short', order_style='bracket', take_profit_factor=0.50, days=0,
                                          stop_loss_factor=2.00, use_vix_position_sizing=False, quantity=1, trade_width=True)

                    # Trade Free Money Strategy
                    self.trade_ironcondor(short_call_delta=0.05, short_put_delta=-0.05, long_call_delta=0.50, long_put_delta=-0.50,
                                          order_type='long', order_style='bracket', take_profit_factor=1.00, days=7,
                                          stop_loss_factor=2.00, use_vix_position_sizing=False, quantity=1, trade_width=False,
                                          short_option_qty=18, long_option_qty=1)
                    return
            else:
                # print("No New Bars Available...")
                return
        except Exception as e:
            print(str(e))
            print("Could not update bars.")

    def exec_status(self, trade: Trade, fill: Fill):
        print("Order status update: " + str(fill))
        self.in_trade = not self.in_trade
        self.order_placed = not self.order_placed
        return


# create the bot
IronCondors()
