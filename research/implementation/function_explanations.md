# Function Explanations
This file contains explanations of the functions used in the implementation of the program.

### `def __init__()` 
- Constructor for the class. Instantiates the local vars and connects the script to the broker.

### `def connect_to_ibkr()`
- Connects to the broker using the `ib_insync` library. This function is called in the constructor.
- This function is called upon disconnect events to reconnect the program back to the broker during daily restarts.
- Gets the first set of historical trade data to prime the program.
- Gets the option chain for the underlying and stores it in the `self.chains` variable.
- Schedules the `onDisconnected()`, `exec_status()`, `on_bar_update()`, and `on_open_order_update()` event handlers.

### `def get_timestamp()`
- Returns the current timestamp in the format `YYYY-MM-DD HH:MM:SS`.
- This function is used to timestamp the log files.

### `def on_open_order_update(trade: Trade):`
- This function is called when an order is placed or updated.
- It is used to update the `self.order_placed` variable to let the program know an order has been placed and to stop ordering more contracts.

### `def onDisconnected()`
- This function is called when the connection to the broker is lost.

### `def update_options_chain()`
- Update the options chain to get the latest expiration dates and strikes.

### `def update_target_expiration(days)`
- Look for the chain with the nearest DTE expiration to days.

### `def get_strike(delta=0.16, option_type='C', call_strike_rounding='up', put_strike_rounding='down')`
- Get the strike price for the option with the given delta
- delta: delta of the option we want to order 
- option_type: type of option (call or put) 
- call_strike_rounding: rounding method for call strike 
- put_strike_rounding: rounding method for put strike \
- returns the strike price of the desired option

### `def get_chain_iv(nearestDTE)`
- Get the implied volatility of the options chain
- nearestDTE: the expiration date of the options chain

### `def find_strangle(call_delta=0.16, put_delta=-0.16, order='SELL')`
- Get the specified delta call and put to trade at that expiration
- Get only 1 contract of each
- call_delta: delta of the call option we want to order
- put_delta: delta of the put option we want to order
- order: whether we want to buy or sell the options

### `def place_order(self, contract, order_type='short', order_style='bracket', take_profit_factor=0.50, stop_loss_factor=3.00, use_vix_position_sizing=True, quantity=1)`
- Place an order for the strangle strategy
- contract: the contract we want to order
- order_type: type of order to place (short or long)
- order_style: type of order to place (bracket, limit or market)
- take_profit_factor: how much to take profit at
- stop_loss_factor: how much to stop loss at
- use_vix_position_sizing: whether to use vix position sizing or not
- quantity: how many contracts to order if not using VIX position sizing

### `def trade_strangle(self, call_delta=0.16, put_delta=-0.16, order_type='short', order_style='bracket', days=45, take_profit_factor=0.50, stop_loss_factor=3.00, use_vix_position_sizing=True, quantity=1)`
- Trade the strangle strategy
- call_delta: delta of the call option we want to order
- put_delta: delta of the put option we want to order
- order_type: type of order to place (short or long)
- order_style: type of order to place (bracket, limit or market)
- days: how many days until expiration
- take_profit_factor: how much to take profit at
- stop_loss_factor: how much to stop loss at
- use_vix_position_sizing: whether to use vix position sizing or not
- quantity: how many contracts to order if not using VIX position sizing

### `def manage_strangle()`
- If we are in a trade, we want to poll the position and close it if it is 21 DTE or less, the bracket order will take care of the take profit and stop loss
- Otherwise, print some data about the trade

### `def on_bar_update(bars: BarData, has_new_bar: bool)`
- This function is called when a new bar is received.
- If we are not in a trade, we want to check if we should enter a trade
- If we are in a trade, we want to check if we should exit the trade

### `def exec_status(trade: Trade, fill: Fill)`
- This function is called when an order is filled.
- It is used to update the `self.order_placed` variable to let the program know an order has been submitted and to stop ordering more contracts.
- It is also used to update the `self.in_trade` variable to let the program know an order has been filled and to stop ordering more contracts.