# region imports
from AlgorithmImports import *


# endregion

class VirtualYellowGiraffe(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2020, 3, 1)
        self.SetCash(100000)
        self.equity = self.AddEquity("SPY", Resolution.Daily)
        self.symbol = self.equity.Symbol
        self.InitOptionsAndGreeks(self.equity)

    def OnData(self, data):

        ## If we're done warming up, and not invested, Sell a put.
        if (not self.IsWarmingUp) and (not self.Portfolio.Invested):
            if data.Bars.ContainsKey(self.symbol):
                self.SellAnOTMStrangle()

        ## If we're assigned stock sell/cover the shares immediatley
        # order = self.Transactions.GetOrderById(orderEvent.OrderId)
        # if order.Type == OrderType.OptionExercise:
        #     self.Liquidate(orderEvent.Symbol.Underlying)

        ## If we're in a trade, check to see if we're at 50% gain or 200% loss on the position
        # for holding in self.Portfolio:
        #     if holding.Invested:
        #         unrealized_pnl_percent = holding.UnrealizedProfitPercent
        #         if unrealized_pnl_percent >= 50:
        #             self.Liquidate(holding.Symbol)
        #         elif unrealized_pnl_percent <= -200:
        #             self.Liquidate(holding.Symbol)

        ## If we're in a trade, check to see if it's 21 DTE or not, close if it is
        for sym in self.Portfolio.Keys:
            optionClass = self.Securities[sym]
            if optionClass.Symbol.SecurityType == SecurityType.Option and self.Portfolio.Invested:
                expiries = [x.Key.ID.Date for x in self.Portfolio if
                            x.Value.Invested and x.Value.Type == SecurityType.Option]
                today = self.Time.date()
                days_to_expiry = (expiries[0].date() - today).days + 1
                # self.Debug(f"The days to expiry are: {days_to_expiry}")
                if days_to_expiry <= 21:
                    self.Liquidate()

    ## Initialize Options settings, chain filters, pricing models, etc
    ## ====================================================================
    def InitOptionsAndGreeks(self, theEquity):

        ## 1. Specify the data normalization mode (must be 'Raw' for options)
        theEquity.SetDataNormalizationMode(DataNormalizationMode.Raw)

        ## 2. Set Warmup period of at least 30 days
        self.SetWarmup(30, Resolution.Daily)

        ## 3. Set the security initializer to call SetMarketPrice
        self.SetSecurityInitializer(lambda x: x.SetMarketPrice(self.GetLastKnownPrice(x)))

        ## 4. Subscribe to the option feed for the symbol
        theOptionSubscription = self.AddOption(theEquity.Symbol)

        ## 5. set the pricing model, to calculate Greeks and volatility
        theOptionSubscription.PriceModel = OptionPriceModels.CrankNicolsonFD()  # both European & American, automatically

        ## 6. Set the function to filter out strikes and expiry dates from the option chain
        theOptionSubscription.SetFilter(self.OptionsFilterFunction)

    ## Sell an OTM Strangle.
    ## Use Delta to select a put & call contract to sell
    ## ==================================================================
    def SellAnOTMStrangle(self):

        ## Sell a 16 delta strangle expiring in 45 days
        putContract = self.SelectContractByDelta(self.equity.Symbol, .16, 45, OptionRight.Put)
        callContract = self.SelectContractByDelta(self.equity.Symbol, .16, 45, OptionRight.Call)

        ## construct an order message -- good for debugging and order records
        orderMessage = f"Stock @ ${self.CurrentSlice[self.equity.Symbol].Close} | " + f"Sell {putContract.Symbol} " + f"({round(putContract.Greeks.Delta, 2)} Delta)" + f" | Sell {callContract.Symbol} " + f"({round(callContract.Greeks.Delta, 2)} Delta)"
        self.Debug(f"{self.Time} {orderMessage}")

        ## Create Legs for the trade to avoid entering only one leg open at a time
        legs = [
            Leg.Create(callContract.Symbol, -1),
            Leg.Create(putContract.Symbol, -1)
        ]
        self.ComboMarketOrder(legs, 1, False, orderMessage)

    ## Get an options contract that matches the specified criteria:
    ## Underlying symbol, delta, days till expiration, Option right (put or call)
    ## ============================================================================
    def SelectContractByDelta(self, symbolArg, strikeDeltaArg, expiryDTE, optionRightArg=OptionRight.Call):

        canonicalSymbol = self.AddOption(symbolArg)
        # canonicalSymbol = self.AddIndexOption(symbolArg)
        theOptionChain = self.CurrentSlice.OptionChains[canonicalSymbol.Symbol]
        theExpiryDate = self.Time + timedelta(days=expiryDTE)

        ## Filter the Call/Put options contracts
        filteredContracts = [x for x in theOptionChain if x.Right == optionRightArg]

        ## Sort the contracts according to their closeness to our desired expiry
        contractsSortedByExpiration = sorted(filteredContracts, key=lambda p: abs(p.Expiry - theExpiryDate),
                                             reverse=False)
        closestExpirationDate = contractsSortedByExpiration[0].Expiry

        ## Get all contracts for selected expiration
        contractsMatchingExpiryDTE = [contract for contract in contractsSortedByExpiration if
                                      contract.Expiry == closestExpirationDate]

        ## Get the contract with the contract with the closest delta
        closestContract = min(contractsMatchingExpiryDTE, key=lambda x: abs(abs(x.Greeks.Delta) - strikeDeltaArg))

        return closestContract

    ## The options filter function.
    ## Filter the options chain so we only have relevant strikes & expiration dates.
    ## =============================================================================
    def OptionsFilterFunction(self, optionsContractsChain):

        strikeCount = 100  # no of strikes around underyling price => for universe selection
        minExpiryDTE = 30  # min num of days to expiration => for uni selection
        maxExpiryDTE = 50  # max num of days to expiration => for uni selection

        return optionsContractsChain.IncludeWeeklys() \
            .Strikes(-strikeCount, strikeCount) \
            .Expiration(timedelta(minExpiryDTE), timedelta(maxExpiryDTE))
