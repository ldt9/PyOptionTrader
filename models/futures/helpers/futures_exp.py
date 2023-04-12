# make a function to calculate the expiration contract code for a future
# based on the current date and the expiration cycle

import datetime as dt

month_codes= {'F':1, 'G':2, 'H':3, 'J':4, 'K':5, 'M':6, 'N':7, 'Q':8, 'U':9, 'V':10, 'X':11, 'Z':12}

def futures_exp(contract, offset=0):
    '''
    This function will take todays date and return the expiration code for the
    futures contract that is currently trading roughly 45 days out.
    :param today: todays date
    :return: string that has the expiration code for the futures contract (ie. 'M3' for June 2023)
    '''

    today = dt.date.today() + dt.timedelta(days=30*offset)
    year = today.year
    # get the last digit in the year
    year = str(year)
    year = year[-1]
    target_exp = today + dt.timedelta(days=45)
    # print the month code for the target expiration
    for key, value in month_codes.items():
        if target_exp.month == value:
            return str(contract)+str(key)+str(year)
