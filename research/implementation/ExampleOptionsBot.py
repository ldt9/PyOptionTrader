# Jacob Amaral Youtube
# https://www.youtube.com/channel/UC3GoIgz6agdJzFNZWJrIR6g
#Imports
from datetime import datetime
from ib_insync import *
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio

class RiskyOptionsBot:
    """
    Risky Options Bot (Python, Interactive Brokers)
    Buy 2 DTE SPY Contracts on 3 consecutive 5-min higher closes and profit target on next bar
    """
    #Initialize variables
    def __init__(self):
        print("Options Bot Running, connecting to IB ...")
        #Connect to IB
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1',7497,clientId=101)
            print("Successfully connected to IB")
        except Exception as e:
            print(str(e))
        # Create SPY Contract
        self.underlying = Stock('SPY', 'SMART', 'USD')
        self.ib.qualifyContracts(self.underlying)
        print("Backfilling data to catchup ...")
        # Request Streaming bars
        self.data = self.ib.reqHistoricalData(self.underlying,
            endDateTime='',
            durationStr='2 D',
            barSizeSetting='1 min',
            whatToShow='TRADES',
            useRTH=False,
            keepUpToDate=True,)

        #Local vars
        self.in_trade = False

        #Get current options chains
        self.chains = self.ib.reqSecDefOptParams(self.underlying.symbol, '', self.underlying.secType, self.underlying.conId)
        #Update Chains every hour - can't update chains in event loop causes asyncio issues
        update_chain_scheduler = BackgroundScheduler(job_defaults={'max_instances': 2})
        update_chain_scheduler.add_job(func=self.update_options_chains,trigger='cron', hour='*')
        update_chain_scheduler.start()
        print("Running Live")
        # Set callback function for streaming bars
        self.data.updateEvent += self.on_bar_update
        self.ib.execDetailsEvent += self.exec_status
        #Run forever
        self.ib.run()
    #Update options chains
    def update_options_chains(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("Updating options chains")
             #Get current options chains
            self.chains = self.ib.reqSecDefOptParams(self.underlying.symbol, '', self.underlying.secType, self.underlying.conId)
            print(self.chains)
        except Exception as e:
            print(str(e))
    #On Bar Update, when we get new data
    def on_bar_update(self, bars: BarDataList, has_new_bar: bool):
        try:
            if has_new_bar:
                #Convert BarDataList to pandas Dataframe
                df = util.df(bars)
                # Check if we are in a trade
                if not self.in_trade:
                    print("Last Close : " + str(df.close.iloc[-1]))
                    #Check for 3 Consecutive Highs
                    if df.close.iloc[-1] > df.close.iloc[-2] and df.close.iloc[-2] > df.close.iloc[-3]:
                        #Found 3 consecutive higher closes get call contract that's $5 higher than underlying
                        for optionschain in self.chains:
                            for strike in optionschain.strikes:
                                if strike > df.close.iloc[-1] + 5 : #Make sure the strike is $5 away so it's cheaper
                                    print("Found 3 consecutive higher closers, entering trade.")
                                    self.options_contract = Option(self.underlying.symbol, optionschain.expirations[1], strike, 'C', 'SMART', tradingClass=self.underlying.symbol)
                                    # We are not in a trade - Let's enter a trade
                                    options_order = MarketOrder('BUY', 1,account=self.ib.wrapper.accounts[-1])
                                    trade = self.ib.placeOrder(self.options_contract, options_order)
                                    self.lastEstimatedFillPrice = df.close.iloc[-1]
                                    self.in_trade = not self.in_trade
                                    return # important so it doesn't keep looping
                else: #We are in a trade
                    if df.close.iloc[-1] > self.lastEstimatedFillPrice:
                        #Sell for profit scalping
                        print("Scalping profit.")
                        options_order = MarketOrder('SELL', 1,account=self.ib.wrapper.accounts[-1])
                        trade = self.ib.placeOrder(self.options_contract, options_order)
        except Exception as e:
            print(str(e))
    #Order Status
    def exec_status(self,trade: Trade,fill: Fill):
        print("Filled")

#Instantiate Class to get things rolling
RiskyOptionsBot()