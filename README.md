# AIPlanner, AACalc, and Opal

The sources contained here comprise three asset allocation and
consumption planning calculators based on mathematical principles,
plus a SPIA pricing calculator.

AIPlanner uses deep reinforcement learning. It is computationally
extremely demanding to train, but fast once trained.

AACalc attempts to shoehorn everything into Merton's portfolio
problem. It is fast, and easy to use.

Opal is a research calculator that uses stochastic dynamic
programming. It is complex, computationally demanding, and limited in
terms of the scenarios it can handle.

The SPIA pricing calculator computes actuarially fair SPIA prices
using up to date real, nominal, or corporate bond yield curves
obtained from the U.S. Treasury.

## AIPlanner

Notable features of AIPlanner:

  - A heuristic approach that should deliver certainty equivalent
    performance that is within a few percent of the optimal solution.

  - The ability to train a single model for a variety of different
    scenarios.

  - Mortality handled probabilistically using mortality tables.

  - A GJR-GARCH model of stock volatility. Volatility of stock returns
    is partially predicatable, based on the prior period volatility.

  - A Shiller-esque model of stock prices. Stock prices may be over or
    undervalued, and mean revert to the random walk following fair
    price.

  - A Hull-White single factor bond model. Bonds have a yield curve,
    the yield curve evolves over time, and bond prices and returns
    reflect changes in the yield curve.

  - Gradual SPIA annuitization depending on age, wealth, and relative
    risk aversion.

  - Incorporation of the effects of standard error on the known values
    for stock and bond returns.

  - Taxation of assets based on an approximation to the U.S. tax code.

  - A web based API for strategy querying and evaluation.

  - A Monte-Carlo simulator to assess strategy performance.

  - An Angular web based front end.

## AACalc

Notable features of AACalc:

  - The closer the scenario is to Merton's portfolio problem, the more
    accurate the results.

  - A balance sheet approach - asset allocation can't be performed in
    isolation, but must be performed by taking into account the
    presence and size of Social Security, Pensions, 401(k)s, and
    income annuities.

  - Future contributions - the impact of any possible future
    contributions is handled by entering their expected annual amount,
    growth rate, and volatility.

  - Liability matching bonds - inflation indexed zero coupon bonds
    with a duration matching that of anticipated retirement cash flows
    are used as the risk free asset.

  - Income annuities - income annuities are a valuable tool in the
    retirement toolbox. This calculator optionally recommends the
    purchase of inflation indexed income annuities, that is single
    premium immediate annuities or deferred income annuities.

  - Admit what we don't know - returns from the stock market are
    unpredictable. We generate a range of results for different
    plausible scenarios.

## Opal

Notable features of Opal:

  - Delivers, to within the limits of floating point calculations, the
    optimal solution for the simplified scenarios it is capable of
    handling.

  - Uses stochastic dynamic programming to compute optimal asset
    allocation and consumption strategies assuming time-wise
    independent returns.

  - A Monte-Carlo simulator to assess strategy performance.

  - A variety of correlation preserving bootstrapping and synthetic
    return generation options for the Monte Carlo simulator.

  - The ability to report the odds of portfolio failure, the time
    spent in the portfolio failure state, and certainty equivalent
    consumption metrics.

  - Optional handling of taxation in the Monte Carlo simulator using a
    variety of lot based accounting modules.

  - Mortality handled stochastically using mortality tables.

  - In addition to the standard asset classes, the ability to handle
    liability matching bonds, real annuities, and nominal annuities.  Be
    warned though the annuity code often appears to invoke numerical
    instabilities.

  - When handling 3 or more asset classes the ability to speed up
    performance in exchange for some loss of optimality by using mean
    variance optimization thanks to the Systematic Investor Toolbox.

  - Graphical display of the optimal strategy and its performance
    thanks to GNUPLOT.

  - An optional deprecated web based front end to the program.

## SPIA pricing calculator

Notable features of the SPIA pricing calculator:

  - Uses a variety of mortality tables.

  - Use of the current U.S. Treasury real and nominal yield curves,
    and the high quality markets corporate bond curve.

  - An optional web based front end.

## Demo

  - See https://www.aiplanner.com/ for AIPlanner.

  - See https://www.aacalc.com/ for AACalc and the SPIA pricing
    calculator.

  - Opal no longer has a functioning web based front end that can be
    used for demos. It is command line only.

## License

  - AIPlanner is not Open Source, but is free for non-commercial use.
    Commercial use licenses are also available.

  - AACalc, Opal, and the SPIA pricing calculator have been released
    as Open Source. They are licensed under the GNU Affero GPL. Note,
    the Affero GPL requires that if you use the licensed code as part
    of a web service then you must release your code.

  - See the file LICENSE in the relevant sub-directories for further
    details.

## Implementation

  - Runs on Ubuntu 20.04 Linux and possibly other systems.

  - AIPlanner is written in Python, on top of Ray RLlib and PyTorch,
    with calls out to GNUPLOT.

  - The Opal backend is written in Java with call outs to R and
    GNUPLOT.

  - The AIPlanner web frontend is written in Angular. The remaining
    web frontends are written in Python using the Django framework.

  - The AIPlanner and Opal backends can be either run standalone, or
    in a server configuration talking to the frontend.

  - The AIPlanner and Opal backends perform minimal input sanity
    checking; responsibility for input sanity checking pushed on to
    frontend.

  - The Opal backend uses hill climbing to avoid exhaustive search of
    the solution space.

## Getting started

  - It is suggested that Amazon EC2 be used for development work.

  - Obtain the sources:

        sudo apt install git
        git clone https://github.com/gordoni/aiplanner.git

  - If might do development work:

        cd aiplanner
        git config --global user.name "<FirstName> <LastName>"
        git config --global user.email "<user@email.com>"

  - See ai/README for the Angular frontended Python based AIPlanner.

  - See web/README for the Django frontended Python based AACalc.

  - See opal/README for the Java based Opal.
