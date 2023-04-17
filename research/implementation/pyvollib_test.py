# The usual py_vollib syntax

import numpy as np
import pandas as pd

import py_vollib_vectorized

from py_vollib_vectorized import price_dataframe, get_all_greeks

# We can also price a dataframe easily by specifying a dataframe and the corresponding columns

df = pd.DataFrame()
df['Flag'] = ['c']     # 'c' for call, 'p' for put
df['S'] = 402.62            # Underlying asset price
df['K'] = [435]        # Strike
df['T'] = 43/365            # (Annualized) time-to-expiration
df['R'] = 0.00              # Interest free rate
df['IV'] = 0.204            # Implied Volatility
result = price_dataframe(df, flag_col='Flag', underlying_price_col='S', strike_col='K', annualized_tte_col='T',
                     riskfree_rate_col='R', sigma_col='IV', model='black_scholes', inplace=False)
print(result)
#   Price       delta       gamma       theta       rho        vega
#   2.895588    0.467506    0.046795    -0.045900   0.083035   0.168926
#   0.611094    -0.136447   0.025739    -0.005335   -0.027151  0.092838

def round_to_multiple(number, multiple, direction="up"):
    if direction == "up":
        return int(np.ceil(number / multiple)) * multiple
    elif direction == "down":
        return int(np.floor(number / multiple)) * multiple
    else:
        raise ValueError("direction must be either up or down")


# Make a for loop that finds the call and put options closest to 0.16 delta
spotSPY = 405.5
# currentIV = spotVIX/100
currentIV = 20.4/100
# time = monthlyDTE/365
time = 45/365
ir = 0.00

for i in range(0, 1000):
    df = pd.DataFrame()
    df['Flag'] = ['c']                              # 'c' for call, 'p' for put
    df['S'] = spotSPY                          # Underlying asset price
    df['K'] = [spotSPY + i]                    # Strike(s)
    df['T'] = time                                  # (Annualized) time-to-expiration
    df['R'] = ir                                    # Interest free rate
    df['IV'] = currentIV                            # Implied Volatility
    result = price_dataframe(df, flag_col='Flag', underlying_price_col='S', strike_col='K', annualized_tte_col='T',
                         riskfree_rate_col='R', sigma_col='IV', model='black_scholes', inplace=False)
    if result['delta'][0] <= 0.16:
        print(result['delta'])
        print(round_to_multiple(df['K'][0],5,"up"))
        # print(df['K'][0])
        break

for i in range(0, 1000):
    df = pd.DataFrame()
    df['Flag'] = ['p']                              # 'c' for call, 'p' for put
    df['S'] = spotSPY                          # Underlying asset price
    df['K'] = [spotSPY - i]                    # Strike(s)
    df['T'] = time                                  # (Annualized) time-to-expiration
    df['R'] = ir                                    # Interest free rate
    df['IV'] = currentIV                            # Implied Volatility
    result = price_dataframe(df, flag_col='Flag', underlying_price_col='S', strike_col='K', annualized_tte_col='T',
                         riskfree_rate_col='R', sigma_col='IV', model='black_scholes', inplace=False)
    if result['delta'][0] >= -0.16:
        print(result['delta'])
        print(round_to_multiple(df['K'][0],5,"down"))
        # print(df['K'][0])
        break


price = 12.10
F = 409.37
K = [409]
t = 49/365
r = 0.00
flag = ['c']

iv = py_vollib_vectorized.vectorized_implied_volatility_black(price, F, K, r, t, flag, return_as='numpy')  # equivalent
print(iv)

# We can also price a dataframe easily by specifying a dataframe and the corresponding columns

df = pd.DataFrame()
df['Flag'] = ['c']  # 'c' for call, 'p' for put
df['S'] = 409.37    # Underlying asset price
df['K'] = [409]     # Strike
df['T'] = 48/365    # (Annualized) time-to-expiration
df['R'] = 0.00      # Interest free rate
df['IV'] = 0.199    # Implied Volatility
result = price_dataframe(df, flag_col='Flag', underlying_price_col='S', strike_col='K', annualized_tte_col='T',
                     riskfree_rate_col='R', sigma_col='IV', model='black_scholes', inplace=False)
print(result)