# PyOptionTrador: Option Trading Strategies for Interactive Brokers

## Introduction
I have been interested in stock trading and finance since I came to college. This interest has led to my passion to study the idea of value in the markets. I would like to automate an existing strategy that I currently do manually that has generated consistent profit for me almost 80% of the time. Below is an explanation of the strategy and the results of my backtesting.
**NOTE: This project is for informational purposes only. This project and all information contained herein is not investment advice, and not intended to be investment advice. Any trades you make based on this information are your responsibility alone. The project maker disclaims any liability, loss, or risk resulting directly or indirectly, from the use or application of any of the contents of this project.
I am not affiliated with Interactive Brokers in any way. This repo is open source, free to use, free to contribute, so use it at own risk. There is no promise of future profits nor responsibility of future loses.**

# Implemented Strategies

## Strategy 1: The Short Strangle
<img alt="ShortStrangle.png" src="research/pics/ShortStrangle.png" title="Short Strangle Payoff" width="775" height="471"/>

### High Level Overview:
The delta neutral short strangle trading strategy is an options trading strategy that involves simultaneously selling an out-of-the-money (OTM) call option and an OTM put option on the same underlying security, while maintaining a delta-neutral position. This means that the overall delta, which measures the sensitivity of the options position to changes in the price of the underlying security, is kept close to zero.

The purpose of this strategy is to generate income from the premiums received from selling the call and put options, while taking advantage of the time decay of options. As time passes, the value of options typically decreases, which can result in profits for the trader. The delta-neutral aspect of the strategy aims to reduce the impact of changes in the price of the underlying security on the overall position, as the trader seeks to profit from the time decay of the options rather than relying on directional movements in the underlying security.

The delta-neutral short strangle strategy is typically used in neutral or range-bound markets, where the trader expects the price of the underlying security to remain relatively stable within a certain range. It is considered a high-risk strategy as it involves unlimited risk in case of large price movements in the underlying security beyond the range of the sold options. Therefore, it requires careful risk management, including setting appropriate stop-loss orders or having a plan in place to manage potential losses. Traders who employ this strategy should have a good understanding of options pricing, delta, and risk management techniques.

### Basic Strategy Rules:
 - Sell a call and a put at 16 delta or 1σ strike in the 45 DTE monthly expiration (or as close as possible)
 - Close at 21 DTE win or lose
 - Set profit target at 50% and stop loss at 200% of net credit received

### Optional Management Tips (that will not be implemented but are good to know):
- Sell when IVR and IVx are > 30%
- Roll untested side when it has decayed 50-80% or when price has breached one of strikes
- Roll untested side into a straddle
- Go inverted and roll one untested strike above the tested strike (make sure the credit you have received thus far is greater than the inversion width)
- Roll out in time and recenter your strangle

### Management Flow Charts:
<img alt="UnrealizedRisk_DecisionTree.png" src="research/pics/UR_DecisionTree.png" width="1138" height="525"/>
<br>
<img alt="VIX_DecisionTree.png" src="research/pics/VIX_DecisionTree.png" width="772" height="542"/>

### Advantages:
- Delta Neutral Trading using short options can make a profit without taking any directional risk at time of entry, especially if the underlying stays stagnant for some time after.
- Delta Neutral positions are not affected by small movements made by the underlying but are still affected by time decay as the premium value of the options decay over time.
- By executing a delta neutral position, one can also profit from a decrease in volatility without taking significant directional risk.

### Disadvantages:
- Delta Neutral Trading using short options can turn sour if the underlying continues to trend in one direction for multiple days or weeks.
- Delta Neutral positions are affected by large movements made by the underlying. Theta, or time decay of the premium value of the option, is usually not enough to compensate the large move unless the trade has been on for some time or the deltas are small.
- By executing a delta neutral position with short options, one can lose money from an increase in volatility.

### 3 Year Backtesting Results without VIX Optimization:
<img alt="3yrBacktest.png" src="research/pics/3yr_performance.png"/>

### 3 Year Backtesting Results with VIX Optimization:
<img alt="3yrBacktest.png" src="research/pics/3yr_perfomace_vix_optimized.png"/>

### Takeaways from Backtesting:
- The strategy is profitable over the Short/Medium Term
- VIX Optimization has little effect on the performance of the strategy during this time period
    - This is likely due to the fact that the VIX is not a good indicator of future volatility
    - This also rounds out that complex strategies are not needed to make money in the market
- This means our strategy will have the option to trade using VIX optimization such it pose an advantage in the future, but that we will not be using it for the time being.

### Running in an Azure Client:
- The Azure VM I used was a Standard B2s (2 vcpus, 4 GiB memory)
- The VM is running Windows 10 Pro
<br>
<img alt="VM CLient 1" src="research/pics/vm_client_1.png"/>
<br>
<img alt="VM CLient 1" src="research/pics/vm_client_2.png"/>
<br>
<img alt="VM CLient 1" src="research/pics/vm_client_3.png"/>

### Installation (Windows Only):
**Step 1:** Download the executable from the [models](https://github.com/ldt9/pyoptiontrador/tree/master/models) folder
  - As of 4/12/23, there is only one executable available for the equity short strangle strategy [here](https://github.com/ldt9/pyoptiontrador/tree/master/models/equities/Release) 

**Step 2:** Open your Interactive Brokers Trader Workstation (TWS) and log in

**Step 3:** Make sure your port is set to `7497`, and your client ID is set to `101` on whichever account you want to trade on

**Step 4:** Run the executable

**Step 5:** If you want to make adjustments to the strategy, you can edit the python file and run it locally with the same port and ID settings
  - If you find a strategy setting you like, you can use `Auto-Py-To-Exe` to package the python file following the instructions below

### Packaging with Auto-Py-To-Exe After Making Changes:
**Step 1:** Install Auto-Py-To-Exe using the instructions [here](https://towardsdatascience.com/how-to-easily-convert-a-python-script-to-an-executable-file-exe-4966e253c7e9)

**Step 2:** Open a terminal and run `Auto-To-Py-Exe`

**Step 3:** Select the new python file you want to package following the general instructions previously linked

**Step 4:** **IMPORTANT STEP!** Before you package the client, make sure to add the following packages to the `hidden-libraries` under the `Advanced` drop down.
If you do not do this, the client will open for a few seconds and then immediatley close.
If you add a new library to your python file, you will need to add it to the `hidden-libraries` as well.
- `ib_insync`
- `pandas`
- `aysncio`
- `py_vollib_vectorized`
- `apscheduler`

It should look something like this under the Advanced drop down:
<img alt="auto-py-to-exe" src="research/pics/auto-py-to-exe_hidden_imports.png"/>

### Packages Used:
- [ib_insync](https://ib-insync.readthedocs.io/api.html)
- [pandas](https://pandas.pydata.org/docs/)
- [numpy](https://numpy.org/doc/stable/)
- [matplotlib](https://matplotlib.org/stable/index.html)
- [aysncio](https://docs.python.org/3/library/asyncio.html)
- [py_vollib_vectorized](https://github.com/marcdemers/py_vollib_vectorized)
- [nest_asyncio](https://github.com/erdewit/nest_asyncio)
- [Auto-Py-To-Exe](https://github.com/brentvollebregt/auto-py-to-exe)

### Extending this Strategy:
- Implementing this strategy with futures options instead of equity options
- ~~Use a different broker's API besides Interactive Brokers~~ (After further research, I have decided to stick with Interactive Brokers)
  - ~~The forced restarts can be a hassle if you are trying to trade futures which trade 23/6~~ (This can be avoided as implemented)
- Utilize Docker Containers to run different aspects of the client with less overhead than an exe file
- Make this client more modular/abstract so that it can be used for other strategies (simultaneously) by separating the static aspects of the class into helper functions
  - This is in progress by modeling our strategies based off of [quanttrader's](https://github.com/letianzj/quanttrader) design
- Implement this strategy such that it capitalizes on the IV _difference_ between the Barone-Adesi And Whaley and Black-Scholes models
  - Calculate the IV of the strangle using the Barone-Adesi And Whaley model and the IV of the strangle using the Black-Scholes model
  - If the IV of the strangle using the Barone-Adesi And Whaley model is **greater** than the IV of the strangle using the Black-Scholes model, then **buy** the strangle
  - If the IV of the strangle using the Barone-Adesi And Whaley model is **less** than the IV of the strangle using the Black-Scholes model, then **sell** the strangle
  - Research more [here](https://medium.datadriveninvestor.com/i-needed-money-so-i-invented-baw-iv-trading-921bea493994)
- Implement this strategy using rolling percent change confidence intervals
- Implement this strategy using a neural network or a deep learning model to decide when to enter the strangles
- Make a custom interface for it so that the CPU usage isn't tied up in running TWS or Gateway
  - Possible options for doing this include: [PyGame](https://www.pygame.org/docs/), [Tkinter](https://docs.python.org/3/library/tkinter.html), or [PyQT](https://www.riverbankcomputing.com/static/Docs/PyQt5/).

### More Strategies to Come:
- Iron Condor Strategies
- Short Straddle Strategies