# Project Timeline of Events
## 3/25/23 - Figuring Out the Game Plan
- Tested Making the Strategy in QuantConnect
- Looked for other alternatives because QC is soooooo slow
- Finalized report... might need to add a ~~server~~ VM to the budget (Azure should handle this...)
## 3/26/23
- Downloaded IB Gateway
- Tested a SPX Data function... realized I ~~may~~ need to buy market data
- Have to transfer $550 to IB in order to use their historical data
- Linked bank account to IB, waiting on trial deposits 
- Made a markdown write up of the strategy ~~at the head of the notebook~~ in the README.md
- Started to put a strategy together
- TODO: Research py_vollib, this is going to help me find the implied volatility and delta of the options I want to sell
## 3/27/23
- Still waiting on bank to confirm trial deposits
- QC gets hung up during testing... need to upgrade or find a different solution
- Realization: I can do the same thing in Zorro Trader for free
- Testing Strangles in ZT, works great
- Revising Workshop8.c to my params
## 3/29/23
- Created something similar to what I use, but it's not perfect yet
- Tried to connect Zorro to IB... need Zorro S, gonna have to make my own in Python
- Realized Zorro data wasn't clean to begin with... dodged a bullet there
- Initiated transfer of $550 to IB Account to get historical data
## 3/30/23 to 4/11/23
- Backtested my strategy using OptionOmega, a paid for service, thank you COE Department
- Attached the backtest results to the report in the README.md
- Worked on making the algorithm work using ib_insync
- Connected to IB and pulled historical data and account data
- Created helper functions to narrow the search area for the options algorithm
- Created a function to get the current price of the underlying and the strangle
- Created all necessary functions to create an order, place it, and manage the trade using the described strategy
- Tested the algorithm for a few days on my computer, it works great
- Used auto-py-to-exe to convert the python file to an exe file using PyInstaller
- Ran the exe file on my computer and it works great
- Launched an Azure VM and ran the exe file on it, it works great, going to test it for a day and see how it goes
  - (I have suspicions that the VM might run out of memory because idk if the exe will handle that for me or not)