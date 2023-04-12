import sys
from ib_insync import *
import logging
logging.basicConfig(level=logging.DEBUG)
_logger = logging.getLogger("test_reconnect")


def connect_to_ibkr():
    """
    Connect to a running TWS/gateway application.
    """
    print('Trying to connect...')
    max_attempts = 10
    current_reconnect = 0
    delaySecs = 60
    ib.disconnect()
    while True:
        try:
            ib.connect("127.0.0.1", port=7497, clientId=101, timeout=5)
            if ib.isConnected():
                print('Connected')
                break
        except Exception as err:
            print("Connection exception: ", err)
            if current_reconnect < max_attempts:
                current_reconnect += 1
                print('Connect failed')
                print(f'Retrying in {delaySecs} seconds, attempt {current_reconnect} of max {max_attempts}')
                ib.sleep(delaySecs)
            else:
                sys.exit(f"Reconnect Failure after {max_attempts} tries")
    ib.disconnectedEvent += onDisconnected

    # Function to call after successful connection
    # do_something_important_upon_connection()
    print("RAN SOME FUNCTION AFTER CONNECTION")


def onDisconnected():
    print("Disconnect Event")
    print("attempting restart and reconnect...")
    connect_to_ibkr()


ib = IB()
util.patchAsyncio()
connect_to_ibkr()
ib.disconnect()