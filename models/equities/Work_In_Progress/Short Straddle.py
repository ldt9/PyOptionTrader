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

class ShortStrangles():
    '''
    This class is designed to create a short strangle strategy.
    Sell 1 call and 1 put, each at the 50 delta at the monthly expiration closest to 45DTE.
    Close at 50% gain, 200% loss, or 21 days left to expiration. (or otherwise specified)

    These parameters are configurable in the trade_straddle() function.
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
        self.straddle = None
        self.short_call = None
        self.short_put = None
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
        # self.trade_straddle(use_vix_position_sizing=False)

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

    def find_straddle(self, call_delta=0.50, put_delta=-0.50, order='SELL'):

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

            # get the call strike to sell, model it as a put to sell at the same strike
            callToTrade = self.get_strike(delta=put_delta, option_type='P', put_strike_rounding='None')

            # get the put strike to sell
            putToTrade = callToTrade

            # print the strikes to sell
            print("Call to trade: ", callToTrade)
            print("Put to trade: ", putToTrade)

            # make the option contracts
            self.short_call = Option(self.underlying.symbol, nearestDTE, callToTrade, 'C', 'SMART', '100', 'USD')
            self.short_put = Option(self.underlying.symbol, nearestDTE, putToTrade, 'P', 'SMART', '100', 'USD')
            self.ib.qualifyContracts(self.short_call)
            self.ib.qualifyContracts(self.short_put)
            print("Call and Put Contracts Qualified")

            # make the combo order
            self.straddle = Contract()
            self.straddle.symbol = self.short_call.symbol
            self.straddle.secType = 'BAG'
            self.straddle.currency = self.short_call.currency
            self.straddle.exchange = self.short_call.exchange

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

            # add the legs to make a combo order
            self.straddle.comboLegs = [leg1, leg2]
            print("Straddle Options Combo Order Created")

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

    def trade_straddle(self, call_delta=0.50, put_delta=-0.50, order_type='short', order_style='bracket', days=45,
                       take_profit_factor=0.50, stop_loss_factor=3.00, use_vix_position_sizing=True, quantity=1):
        '''
        Trade the Straddle Options Strategy
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

            self.find_straddle(call_delta=call_delta, put_delta=put_delta, order=order)

            self.place_order(contract=self.straddle, order_type=order_type, order_style=order_style,
                             take_profit_factor=take_profit_factor, stop_loss_factor=stop_loss_factor,
                             use_vix_position_sizing=use_vix_position_sizing, quantity=quantity)
        except Exception as e:
            print(str(e))
            print("Could not trade the strangle.")

    def manage_strangle(self):
        if self.in_trade:  # We are in a trade with no open orders
            '''
            If we are in a trade, we want to poll the position and
            close it if it is 21 DTE or less, the bracket order will
            take care of the take profit and stop loss
            '''
            daysToexp = (self.nearestDTE - datetime.date.today()).days
            # if the difference between self.nearestDTE and today is less than 21 days
            if daysToexp <= 21:
                print("Closing Open Strangle Position...")
                # close the position
                # get the market price of the combo order
                combobars = self.ib.reqHistoricalData(
                    contract=self.straddle,
                    endDateTime='',
                    durationStr='60 s',
                    barSizeSetting='1 secs',
                    whatToShow='MIDPOINT',
                    useRTH=True,
                    formatDate=1)
                combo = util.df(combobars)
                avg_price = round(np.nanmean(combo['close']), 2)
                print("Strangle Price: ", avg_price)

                # send the order to IB as a market order
                order = MarketOrder('SELL', 1)
                self.ib.placeOrder(self.straddle, order)
                print("Position closed at 21DTE for a profit of $" + str(
                    self.lastEstimatedTradePrice - avg_price))

                # Clean up and cancel all orders
                self.ib.reqGlobalCancel()

                # reset the local variables
                self.in_trade = not self.in_trade
                return
            else:
                print("Position is still open...")
                print("Days to expiration: ", round(daysToexp), " days")
                callPnl = self.ib.pnlSingle(self.ib.accountSummary()[0].account, '', self.short_call.conId)
                putPnl = self.ib.pnlSingle(self.ib.accountSummary()[0].account, '', self.short_put.conId)
                contractPnl = self.ib.pnlSingle(self.ib.accountSummary()[0].account, '', self.straddle.conId)
                print("Current Call Pnl: $" + str(callPnl))
                print("Current Put Pnl: $" + str(putPnl))
                print("Current Total Open Pnl: $" + str(contractPnl))
                return
        elif not self.in_trade and self.order_placed:  # Waiting on order fill
            print("Waiting on order fill...")
            return
        else:  # Catch all... There's something wrong
            print("Something went wrong...")
            return

    # On Bar Update, when we get new data
    def on_bar_update(self, bars: BarDataList, has_new_bar: bool):
        try:
            if has_new_bar:
                # Convert the BarDataList to a Pandas DataFrame
                self.df = util.df(bars)
                # Check if we are in a trade and no open orders
                if not self.in_trade and not self.order_placed:
                    # Trade a straddle
                    self.trade_straddle(call_delta=0.50, put_delta=-0.50, order_type='short', order_style='bracket',
                                        take_profit_factor=0.50, stop_loss_factor=3.00, use_vix_position_sizing=True,
                                        quantity=1, days=45)
                    return
                else:
                    # Manage the open strangle
                    self.manage_strangle()
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
ShortStrangles()
