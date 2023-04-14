// Quite simple options trading system
#include <contract.c>

#define PREMIUM	0.50
#define NWEEKS	6   // expiration

int i;
var Price;

CONTRACT* findCall(int Expiry,var Premium)
{
    for(i=0; i<1000; i++) {
        if(!contract(CALL,Expiry,Price+0.5*i)) return 0;
        if(between(ContractBid,0.1,Premium)) return ThisContract;
    }
    return 0;
}

CONTRACT* findPut(int Expiry,var Premium)
{
    for(i=0; i<1000; i++) {
        if(!contract(PUT,Expiry,Price-0.5*i)) return 0;
        if(between(ContractBid,0.1,Premium)) return ThisContract;
    }
    return 0;
}

void run()
{
    set(PARAMETERS,TESTNOW);	// generate and use optimized parameters
    StartDate = 20110201;
    EndDate = 20221230;
    BarPeriod = 1440;
    BarZone = ET;
    BarOffset = 15*60+20; // trade at 15:20 ET
    LookBack = 1;
//    var PREMIUM = optimize(0.25,0.25,3.00,0.25);
//    Stop = PREMIUM * 3; // stop loss at 200% of premium
    set(PLOTNOW);
    set(PRELOAD|LOGFILE);

    assetList("AssetsIB");
    asset("SPY"); // unadjusted!
    Multiplier = 100;

// load today's contract chain
    contractUpdate(Asset,0,CALL|PUT);
    Price = priceClose();

    printf("\nCurrent Price of SPY = %f",Price);

    var val = 0;
    var open = 0;

    for (open_trades) {
        if (TradeIsOpen) {
            val += TradeProfit/Multiplier;
            open += TradePriceOpen;
            printf("\nTradePriceOpen = %f", TradePriceOpen);
        }
    }

    printf("\nCurrent Open Profit = %f",val);
    printf("\nOpening Price = %f",open);

    if (val >= open*0.50 | val <= open*-3.30) {
        exitShort("*");
        exitLong("*");
    }

//    if (val >= open*optimize(0.5,0.05,1,0.05) | val <= open*-1*optimize(3.0,0.5,5,0.25)) {
//        exitShort("*");
//        exitLong("*");
//    }

// all expired? enter new options
    if(!NumOpenShort) {
        CONTRACT *Call = findCall(45,PREMIUM);
        CONTRACT *Put = findPut(45,PREMIUM);
//        CONTRACT *Call = findCall(optimize(45,7,60,1),PREMIUM);
//        CONTRACT *Put = findPut(optimize(45,7,60,1),PREMIUM);
        if(Call && Put) {
            MarginCost = 0.5*(0.15*Price-min(Call->fStrike-Price,Price-Put->fStrike));
            contract(Call); enterShort();
            contract(Put); enterShort();
        }
    }

    // if excercised, sell remaining underlying at market
    contractSellUnderlying();
}