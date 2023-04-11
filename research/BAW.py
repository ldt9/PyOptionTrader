"""
BAW.PY
Implements the Barone-Adesi And Whaley model for the valuation of American options and their greeks.
"""

import numpy as _np
import cmath as _cm

# Option Styles
_AMERICAN = 'American'
_EUROPEAN = 'European'
# Option Types
_CALL = 'Call'
_PUT = 'Put'
# Output Types
_VALUE = 'Value'
_DELTA = 'Delta'
_GAMMA = 'Gamma'
_VEGA = 'Vega'
_THETA = 'Theta'

_dS = 0.001
_dT = 1 / 365
_dV = 0.00001

_ITERATION_MAX_ERROR = 0.001


def _standardNormalPDF(x):
    val = (1 / (2 * _cm.pi) ** 0.5) * _np.exp(-1 * (x ** 2) / 2)
    return val


def _standardNormalCDF(X):
    y = _np.abs(X)

    if y > 37:
        return 0
    else:
        Exponential = _np.exp(-1 * (y ** 2) / 2)

    if y < 7.07106781186547:
        SumA = 0.0352624965998911 * y + 0.700383064443688
        SumA = SumA * y + 6.37396220353165
        SumA = SumA * y + 33.912866078383
        SumA = SumA * y + 112.079291497871
        SumA = SumA * y + 221.213596169931
        SumA = SumA * y + 220.206867912376
        SumB = 0.0883883476483184 * y + 1.75566716318264
        SumB = SumB * y + 16.064177579207
        SumB = SumB * y + 86.7807322029461
        SumB = SumB * y + 296.564248779674
        SumB = SumB * y + 637.333633378831
        SumB = SumB * y + 793.826512519948
        SumB = SumB * y + 440.413735824752
        _standardNormalCDF = Exponential * SumA / SumB
    else:
        SumA = y + 0.65
        SumA = y + 4 / SumA
        SumA = y + 3 / SumA
        SumA = y + 2 / SumA
        SumA = y + 1 / SumA
        _standardNormalCDF = Exponential / (SumA * 2.506628274631)

    if X > 0:
        return 1 - _standardNormalCDF
    else:
        return _standardNormalCDF


def _priceEuropeanOption(option_type_flag, S, X, T, r, b, v):
    '''
    Black-Scholes
    '''

    d1 = (_np.log(S / X) + (b + v ** 2 / 2) * T) / (v * (T) ** 0.5)
    d2 = d1 - v * (T) ** 0.5

    if option_type_flag == 'Call':
        bsp = S * _np.exp((b - r) * T) * _standardNormalCDF(d1) - X * _np.exp(-r * T) * _standardNormalCDF(d2)
    else:
        bsp = X * _np.exp(-r * T) * _standardNormalCDF(-d2) - S * _np.exp((b - r) * T) * _standardNormalCDF(-d1)

    return bsp


def _priceAmericanOption(option_type_flag, S, X, T, r, b, v):
    '''
    Barone-Adesi-Whaley
    '''

    if option_type_flag == 'Call':
        return _approximateAmericanCall(S, X, T, r, b, v)
    elif option_type_flag == 'Put':
        return _approximateAmericanPut(S, X, T, r, b, v)


def _approximateAmericanCall(S, X, T, r, b, v):
    '''
    Barone-Adesi And Whaley
    '''

    if b >= r:
        return _priceEuropeanOption('Call', S, X, T, r, b, v)
    else:
        Sk = _Kc(X, T, r, b, v)
        N = 2 * b / v ** 2
        k = 2 * r / (v ** 2 * (1 - _np.exp(-1 * r * T)))
        d1 = (_np.log(Sk / X) + (b + (v ** 2) / 2) * T) / (v * (T ** 0.5))
        Q2 = (-1 * (N - 1) + ((N - 1) ** 2 + 4 * k)) ** 0.5 / 2
        a2 = (Sk / Q2) * (1 - _np.exp((b - r) * T) * _standardNormalCDF(d1))
        if S < Sk:
            return _priceEuropeanOption('Call', S, X, T, r, b, v) + a2 * (S / Sk) ** Q2
        else:
            return S - X


def _approximateAmericanPut(S, X, T, r, b, v):
    '''
    Barone-Adesi-Whaley
    '''

    Sk = _Kp(X, T, r, b, v)
    N = 2 * b / v ** 2
    k = 2 * r / (v ** 2 * (1 - _np.exp(-1 * r * T)))
    d1 = (_np.log(Sk / X) + (b + (v ** 2) / 2) * T) / (v * (T) ** 0.5)
    Q1 = (-1 * (N - 1) - (((N - 1) ** 2 + 4 * k)) ** 0.5) / 2
    a1 = -1 * (Sk / Q1) * (1 - _np.exp((b - r) * T) * _standardNormalCDF(-1 * d1))

    if S > Sk:
        return _priceEuropeanOption('Put', S, X, T, r, b, v) + a1 * (S / Sk) ** Q1
    else:
        return X - S


def _Kc(X, T, r, b, v):
    N = 2 * b / v ** 2
    m = 2 * r / v ** 2
    q2u = (-1 * (N - 1) + ((N - 1) ** 2 + 4 * m) ** 0.5) / 2
    su = X / (1 - 1 / q2u)
    h2 = -1 * (b * T + 2 * v * (T) ** 0.5) * X / (su - X)
    Si = X + (su - X) * (1 - _np.exp(h2))

    k = 2 * r / (v ** 2 * (1 - _np.exp(-1 * r * T)))
    d1 = (_np.log(Si / X) + (b + v ** 2 / 2) * T) / (v * (T) ** 0.5)
    Q2 = (-1 * (N - 1) + ((N - 1) ** 2 + 4 * k) ** 0.5) / 2
    LHS = Si - X
    RHS = _priceEuropeanOption('Call', Si, X, T, r, b, v) + (
                1 - _np.exp((b - r) * T) * _standardNormalCDF(d1)) * Si / Q2
    bi = _np.exp((b - r) * T) * _standardNormalCDF(d1) * (1 - 1 / Q2) + (
                1 - _np.exp((b - r) * T) * _standardNormalPDF(d1) / (v * (T) ** 0.5)) / Q2

    E = _ITERATION_MAX_ERROR

    while _np.abs(LHS - RHS) / X > E:
        Si = (X + RHS - bi * Si) / (1 - bi)
        d1 = (_np.log(Si / X) + (b + v ** 2 / 2) * T) / (v * (T) ** 0.5)
        LHS = Si - X
        RHS = _priceEuropeanOption('Call', Si, X, T, r, b, v) + (
                    1 - _np.exp((b - r) * T) * _standardNormalCDF(d1)) * Si / Q2
        bi = _np.exp((b - r) * T) * _standardNormalCDF(d1) * (1 - 1 / Q2) + (
                    1 - _np.exp((b - r) * T) * _standardNormalCDF(d1) / (v * (T) ** 0.5)) / Q2

    return Si


def _Kp(X, T, r, b, v):
    N = 2 * b / v ** 2
    m = 2 * r / v ** 2
    q1u = (-1 * (N - 1) - ((N - 1) ** 2 + 4 * m) ** 0.5) / 2
    su = X / (1 - 1 / q1u)
    h1 = (b * T - 2 * v * (T) ** 0.5) * X / (X - su)
    Si = su + (X - su) * _np.exp(h1)

    k = 2 * r / (v ** 2 * (1 - _np.exp(-1 * r * T)))
    d1 = (_np.log(Si / X) + (b + v ** 2 / 2) * T) / (v * (T) ** 0.5)
    Q1 = (-1 * (N - 1) - ((N - 1) ** 2 + 4 * k) ** 0.5) / 2
    LHS = X - Si
    RHS = _priceEuropeanOption('Put', Si, X, T, r, b, v) - (
                1 - _np.exp((b - r) * T) * _standardNormalCDF(-1 * d1)) * Si / Q1
    bi = -1 * _np.exp((b - r) * T) * _standardNormalCDF(-1 * d1) * (1 - 1 / Q1) - (
                1 + _np.exp((b - r) * T) * _standardNormalPDF(-d1) / (v * (T) ** 0.5)) / Q1

    E = _ITERATION_MAX_ERROR

    while _np.abs(LHS - RHS) / X > E:
        Si = (X - RHS + bi * Si) / (1 + bi)
        d1 = (_np.log(Si / X) + (b + v ** 2 / 2) * T) / (v * (T) ** 0.5)
        LHS = X - Si
        RHS = _priceEuropeanOption('Put', Si, X, T, r, b, v) - (
                    1 - _np.exp((b - r) * T) * _standardNormalCDF(-1 * d1)) * Si / Q1
        bi = -_np.exp((b - r) * T) * _standardNormalCDF(-1 * d1) * (1 - 1 / Q1) - (
                    1 + _np.exp((b - r) * T) * _standardNormalCDF(-1 * d1) / (v * (T) ** 0.5)) / Q1

    return Si


def _checkBadFlagInput(option_style_flag, output_flag, option_type_flag):
    styles = (_AMERICAN, _EUROPEAN)
    if option_style_flag not in styles:
        raise ValueError('Option Style must be one of %s' % (styles))
    outputs = (_VALUE, _DELTA, _GAMMA, _VEGA, _THETA)
    if output_flag not in outputs:
        raise ValueError('Output Type must be one of %s' % (outputs))
    types = (_CALL, _PUT)
    if option_type_flag not in types:
        raise ValueError('Option Type must be one of %s' % (types))


def _checkBadNumericInput(spot_price, strike_price, expiration_time_in_years, interest_rate_dec_pa, carry_rate_dec_pa,
                          volatility_dec_pa):
    if spot_price <= 0:
        raise ValueError('Spot Price must be > 0')
    if strike_price <= 0:
        raise ValueError('Strike Price must be > 0')
    if expiration_time_in_years <= 0:
        raise ValueError('Time until Expiration must be > 0')
    if interest_rate_dec_pa <= 0 or interest_rate_dec_pa >= 1:
        raise ValueError('Interest rate in annualized decimal format must be > 0 and < 1.00')
    if carry_rate_dec_pa <= 0 or carry_rate_dec_pa >= 1:
        raise ValueError('Carry Rate in annualized decimal format must be > 0 and < 1.00')
    if volatility_dec_pa <= 0 or volatility_dec_pa >= 10.00:
        raise ValueError('Volatility in annualized decimal format must be > 0 and < 10.00 ')


def getValue(option_style_flag, output_flag, option_type_flag, spot_price, strike_price, expiration_time_in_years,
             interest_rate_dec_pa, carry_rate_dec_pa, volatility_dec_pa):
    '''Returns the value of a financial option according to the specified flag and numeric inputs,
    Keyword arguments:
    option_style_flag -- specifies the style of option to be valued. Must be contained in ('American', 'European')
    output_flag -- specifies the option characteristic value to be calculated.
                    For price, give 'Price'.
                    For an option greek, give one of ('Delta', 'Gamma', 'Vega', 'Theta').
    option_type_flag -- specifies the type of option to be valued. Must be contained in ('Call', 'Put')
    spot_price -- Spot price of the underlying asset. Must be > 0.
    strike_price -- Strike price of the option. Must be > 0.
    expiration_time_in_years -- Time until Expiration. Must be > 0.
    interest_rate_dec_pa -- Interest rate in annualized decimal format. Must be > 0 and < 1.00.
    carry_rate_dec_pa -- Carry rate in annualized decimal format. Must be > 0 and < 1.00.
    volatility_dec_pa -- Volatility in annualized decimal format. Must be > 0 and < 10.00
    '''

    S = spot_price
    X = strike_price
    T = expiration_time_in_years
    r = interest_rate_dec_pa
    b = carry_rate_dec_pa
    v = volatility_dec_pa

    _checkBadFlagInput(option_style_flag, output_flag, option_type_flag)
    _checkBadNumericInput(S, X, T, r, b, v)

    if option_style_flag == _AMERICAN:

        if output_flag == _VALUE:
            return _priceAmericanOption(option_type_flag, S, X, T, r, b, v)
        elif output_flag == _DELTA:
            return (_priceAmericanOption(option_type_flag, S + _dS, X, T, r, b, v) - _priceAmericanOption(
                option_type_flag, S - _dS, X, T, r, b, v)) / (2 * _dS)
        elif output_flag == _GAMMA:
            return (_priceAmericanOption(option_type_flag, S + _dS, X, T, r, b, v) - 2 * _priceAmericanOption(
                option_type_flag, S, X, T, r, b, v) + _priceAmericanOption(option_type_flag, S - _dS, X, T, r, b,
                                                                           v)) / _dS ** 2
        elif output_flag == _VEGA:
            return (_priceAmericanOption(option_type_flag, S + _dS, X, T, r, b, v + _dV) - _priceAmericanOption(
                option_type_flag, S + _dS, X, T, r, b, v - _dV)) / 2
        elif output_flag == _THETA:
            return _priceAmericanOption(option_type_flag, S + _dS, X, T - _dT, r, b, v) - _priceAmericanOption(
                option_type_flag, S + _dS, X, T, r, b, v)

    elif option_style_flag == _EUROPEAN:

        # TODO implement Greeks for european options
        if output_flag == _VALUE:
            return _priceEuropeanOption(option_type_flag, S, X, T, r, b, v)