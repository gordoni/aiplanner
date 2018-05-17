# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import exp, log
from random import normalvariate, seed
from statistics import mean, stdev

from spia import YieldCurve

from ou_process import OUProcess

class Bonds(object):
    '''Short rate models - https://en.wikipedia.org/wiki/Short-rate_model .

    Hull-White one-factor model - https://en.wikipedia.org/wiki/Hull%E2%80%93White_model .
    '''

    def __init__(self, *, a, sigma, yield_curve, r0, standard_error, time_period):
        '''Initialize a bonds object.

        "a" interest rate mean reversion rate. Default value chosen to
        result in a reasonable estimate for the expected volatility of
        the long term interest rate.

        "sigma" volatility of rates. Default value chosen as a
        reasonable estimate of the expected volatility in the short
        term interest rate.

        "yield_curve" interest rate YieldCurve object representing the
        typical yield curve to use.

        "r0" time zero annualized continuously compounded interest
        rate, or none to use the yield curve short interest rate.

        "standard_error" is the standard error of the estimated yield
        curve return level.

        "time_period" step size in years.

        '''

        self.a = a # Alpha in Wikipedia and hibbert.
        self.sigma = sigma
        self.yield_curve = yield_curve
        self.adjust = normalvariate(0, standard_error)
        self.time_period = time_period

        self.sir_mean = log(self.yield_curve.discount_rate(0) + self.adjust)
        self.r0 = self.sir_mean if r0 == None else r0

        self._p_cache = {}

        self.reset()

    def reset(self):

        self.t = 0
        self.oup = OUProcess(self.time_period, self.a, self.sigma, mu = self.sir_mean, x = self.r0) # Underlying random movement in short interest rates.

        self._sir_cache = {}

    def _p(self, t):
        '''Return the present value of a zero coupon bound paying 1 at time t
        according to the typical yield curve.

        '''

        try:
            return self._p_cache[t]
        except KeyError:
            p = (self.yield_curve.discount_rate(t) + self.adjust) ** - t
            if len(self._p_cache) < 1000:
                self._p_cache[t] = p
            return p

    def _present_value(self, oup_x, t):
        '''Return the present value of a zero coupon bond paying 1 at time t
        into the future when the short term interest rates are given
        by the underlying OU process value, oup_x.

        '''

        try:
            sir = self._sir_cache[self.t]
        except KeyError:
            if len(self._sir_cache) >= 100:
                self._sir_cache = {}
            sir = self._sir_cache[self.t] = self._short_interest_rate(oup_x)

        #  https://en.wikipedia.org/wiki/Hull%E2%80%93White_model P(0, T).
        B = (1 - exp(- self.a * t)) / self.a
        P = self._p(t) * exp(B * (self.sir_mean - sir))

        return P

    def present_value(self, t):
        '''Return the present value of a zero coupon bond paying 1 at timet t.'''

        return self._present_value(self.oup.x, t)

    def _yield(self, t):
        '''Return the current continuously compounded yield of a zero coupon
        bond paying 1 at time t.

        '''

        return - log(self._present_value(self.oup.x, t)) / t if t > 0 else self._short_interest_rate(self.oup.x)

    def sample(self, t = 7):
        '''Current return for a zero coupon bond with duration t.'''

        assert t >= self.time_period

        return self._present_value(self.oup.next_x, t - self.time_period) / self._present_value(self.oup.x, t)

    def step(self):

        self.t += self.time_period
        self.oup.step()

    def _report(self):

        durations = (1, 5, 7, 10, 20, 30)
        durations = (10, 20, 25, 30)

        self.reset()
        print('duration initial_expected_yield observed_yield')
        for duration in durations:
            r = self._yield(duration)
            r_expect = log(self.yield_curve.discount_rate(duration))
            print(duration, r_expect, r)

        print()

        print('duration mean_yield')
        for duration in durations:
            r = []
            self.reset()
            for _ in range(10000):
                r.append(self._yield(duration))
                self.step()
            print(duration, mean(r))

        if self.yield_curve.date_str_low:

            year_low = int(self.yield_curve.date_str_low[:4])
            year_high = int(self.yield_curve.date[:4])

            if year_low != year_high:

                print()

                print('duration expect_standard_deviation_yield standard_deviation_yield')
                for duration in durations:
                    r = []
                    r_expect = []
                    self.reset()
                    for _ in range(10000):
                        r.append(self._yield(duration))
                        self.step()
                    for year in range(year_low, year_high + 1):
                        yield_curve = self._deflate(YieldCurve(self.yield_curve.interest_rate, '{}-12-31'.format(year)))
                        r_expect.append(log(yield_curve.discount_rate(duration)))
                    print(duration, stdev(r_expect), stdev(r))

                print()

                print('duration expected_volatility_yield observed_volatility_yield')
                for duration in durations:
                    dr = []
                    r_old = None
                    self.reset()
                    for _ in range(10000):
                        r = self._yield(duration)
                        self.step()
                        if r_old != None:
                            dr.append(r - r_old)
                        r_old = r
                    dr_expect = []
                    r_expect_old = None
                    for year in range(year_low, year_high + 1):
                        yield_curve = self._deflate(YieldCurve(self.yield_curve.interest_rate, '{}-12-31'.format(year)))
                        r_expect = log(yield_curve.discount_rate(duration))
                        if r_expect_old != None:
                            dr_expect.append(r_expect - r_expect_old)
                        r_expect_old = r_expect
                    print(duration, stdev(dr_expect), stdev(dr))

        print()

        print('duration mean_real_return standard_deviation')
        for duration in durations:
            ret = []
            self.reset()
            for _ in range(100000):
                ret.append(self.sample(duration))
                self.step()
            print(duration, mean(ret), stdev(ret))

        print()

        self.reset()
        print('sample returns')
        print('short_interest_rate 20_year_real_return 20_year_yield')
        for _ in range(50):
            print(self._short_interest_rate(self.oup.next_x), self.sample(20), self._yield(20))
            self.step()

        self.reset()

class RealBonds(Bonds):

    def __init__(self, *, a = 0.05, sigma = 0.004, yield_curve = None, r0 = None, standard_error = 0, time_period = 1):
        '''Chosen value of sigma, 0.004, intended to produce a short term real
        yield standard deviation of 0.012-0.013. The measured value
        over 2005-2017 was 1.33% (when rates were volatile).

        Chosen value of a, 0.05, intended to produce a long term (20
        year) real yield standard deviation of 0.007-0.008. The
        measured value over 2005-2017 was 0.77%.

        Chosen default yield curve intended to be indicative of the
        present era.

        '''

        if yield_curve == None:
            yield_curve = YieldCurve('real', '2017-12-31', date_str_low = '2005-01-01', adjust = 0)

        super().__init__(a = a, sigma = sigma, yield_curve = yield_curve, r0 = r0, standard_error = standard_error, time_period = time_period)

    def _short_interest_rate(self, oup_x):
        '''Return the annualized continuously compounded current short
        interest rate given the underlying OU process value, oup_x.

        The term structure reveals an investor preference for shorter
        durations rather than true expectations of future rates and so
        is ignored.

        '''

        return oup_x

    def observe(self):

        return (self._short_interest_rate(self.oup.x), )

    def _deflate(self, yield_curve):

        return yield_curve

class DeflatedYieldCurve(object):

    def __init__(self, nominal_yield_curve, real_yield_curve):

        self.nominal_yield_curve = nominal_yield_curve
        self.real_yield_curve = real_yield_curve

        self.interest_rate = nominal_yield_curve.interest_rate
        self.date = nominal_yield_curve.date
        self.date_str_low = nominal_yield_curve.date_str_low

    def discount_rate(self, y):

        return self.nominal_yield_curve.discount_rate(y) / self.real_yield_curve.discount_rate(y)

class BreakEvenInflation(Bonds):

    def __init__(self, real_bonds, *, inflation_a = 0.15, inflation_sigma = 0.010, bond_a = 0.05, bond_sigma = 0.004, model_bond_volatility = True,
        nominal_yield_curve = None, inflation_risk_premium = 0, real_liquidity_premium = 0, r0 = None, standard_error = 0, time_period = 1):
        '''Chosen value for inflation_a, 0.15, reflects faster reversion
        of the inflation rate to its long term mean.

        Chosen value of inflation_sigma, 0.010, produces reasonable
        estimate of the long term (20 year) standard deviation of the
        inflation rate (as modeled). Measured value was
        0.55%. Obtained value was 0.58%.

        Chosen value of bond_a, 0.05, the same as in the real case.

        Chosen value of bond_sigma, 0.004, produces a slight over
        estimate of the long term (20 year) nominal yield standard
        deviation.  Measured value for 2005-2017 (when nominal yields
        were constrained) was 0.98%. Obtained values was 1.08%.

        model_bond_volatility specifies whether the process should be
        such as to provide a reasonable model for the long term
        nominal yield standard deviation, or the inflation rate
        standard deviation. In case of the former an inflation rate
        model tracks the process and is used when calling the
        present_value() and observe() functions.

        Chosen default yield curve intended to be indicative of the
        present era.

        Note that with the default yield curves there is a slight drop
        in the spot rate from duration 25 to 30. This is the presumed
        cause of 30 year nominal bonds having significantly lower mean
        real returns than 20 year bonds. As soon as the forward rate
        becomes the average 15 year plus forward rate at duration 31
        years the mean returns revert. This drop in spot rates could
        in turn be the result of poor spline interpolation of the
        reported nominal rates by the spia module. See
        http://www.math.ku.dk/~rolf/HaganWest.pdf for a possible
        solution.

        '''
        if nominal_yield_curve == None:
            nominal_yield_curve = YieldCurve('nominal', '2017-12-31', date_str_low = '2005-01-01', adjust = 0)

        self.inflation_a = inflation_a
        self.inflation_sigma = inflation_sigma
        self.nominal_yield_curve = nominal_yield_curve
        self.inflation_risk_premium = inflation_risk_premium
        self.real_liquidity_premium = real_liquidity_premium

        if model_bond_volatility:
            a = bond_a
            sigma = bond_sigma
        else:
            a = inflation_a
            sigma = inflation_sigma

        self.adjust_rate = self.real_liquidity_premium - self.inflation_risk_premium

        deflated_yield_curve = DeflatedYieldCurve(nominal_yield_curve, real_bonds.yield_curve)

        super().__init__(a = a, sigma = sigma, yield_curve = deflated_yield_curve, r0 = r0, standard_error = standard_error, time_period = time_period)

        self.reset()

    def reset(self):

        super().reset()

        # Inflation model OU Process tracks modeled nominal bond standard deviation OU Process.
        self.inflation_oup = OUProcess(self.time_period, self.inflation_a, self.inflation_sigma, mu = self.sir_mean, x = self.r0, norm = self.oup.norm)

        self._sir_cache_t = None

    def _forward(self, t):

        delta = 1e-3
        t = min(t, 1000) # Prevent math underflow.
        return - (log(self._p(t + delta)) - log(self._p(t))) / delta

    def _sir(self, oup_x, a, sigma):

        # https://www.math.nyu.edu/~benartzi/Slides10.3.pdf page 11.
        return self._forward(self.t) + (sigma * (1 - exp(- a * self.t)) / a) ** 2 / 2 + oup_x - self.sir_mean

    def _short_interest_rate(self, oup_x):
        '''Return the annualized continuously compounded current short
        interest rate given the underlying OU process value, oup_x.

        The term structure reveals the true expectation of future
        inflation and so is incorporated.

        '''

        return self._sir(oup_x, self.a, self.sigma)

    def _model_short_interest_rate(self):
        '''Current short interest rate based on fitting the inflation model,
        not the nominal bond yield standard deviation model.

        '''

        return self._sir(self.inflation_oup.x, self.inflation_a, self.inflation_sigma)

    def present_value(self, t):

        if self.t != self._sir_cache_t:

            self._sir_cache_t = self.t
            self._sir_cache = self._model_short_interest_rate()

        #  https://en.wikipedia.org/wiki/Hull%E2%80%93White_model P(0, T).
        B = (1 - exp(- self.inflation_a * t)) / self.inflation_a
        P = self._p(t) * exp(B * (self.sir_mean - self._sir_cache) - self.adjust_rate / self.time_period)

        return P

    def inflation(self):

        return 1 / present_value(self.time_period)

    def step(self):

        super().step()
        return self.inflation_oup.step(norm = self.oup.norm)

    def observe(self):

        return (self._model_short_interest_rate(), )

    def _deflate(self, yield_curve):

        return DeflatedYieldCurve(yield_curve, YieldCurve('real', yield_curve.date, date_str_low = yield_curve.date_str_low))

class OUProcessTuple(object):

    def __init__(self, *oups):

        self.oups = oups

    @property
    def x(self):

        return tuple(oup.x for oup in self.oups)

    @property
    def next_x(self):

        return tuple(oup.next_x for oup in self.oups)

class NominalBonds(Bonds):

    def __init__(self, real_bonds, inflation, *, time_period = 1):

        self.real_bonds = real_bonds
        self.inflation = inflation
        self.time_period = time_period

        self.yield_curve = self.inflation.nominal_yield_curve

        self.reset()

    def reset(self):

        self.real_bonds.reset()
        self.inflation.reset()

        self.oup = OUProcessTuple(self.real_bonds.oup, self.inflation.oup)

    def _short_interest_rate(self, oup_x):

        return self.real_bonds._short_interest_rate(oup_x[0]) + self.inflation._short_interest_rate(oup_x[1])

    def _present_value(self, oup_x, t):

        return self.real_bonds._present_value(oup_x[0], t) * self.inflation._present_value(oup_x[1], t)

    def sample(self, t = 7):

        sample = super().sample(t)
        period_inflation = self.inflation._present_value(self.oup.oups[1].x, self.time_period)

        return sample * period_inflation

    def step(self):

        self.real_bonds.step()
        self.inflation.step()

    def observe(self):

        return self.real_bonds.observe() + self.inflation.observe()

    def _deflate(self, yield_curve):

        return yield_curve

def init(need_real = True, need_nominal = True, need_inflation = True, time_period = 1):
    '''Return a tuple of objects (real_bonds, nominal_bonds, inflation)
    representing a bond and inflation model. They are each either None
    if they are not needed and have not been computed or provide the
    following methods:

        reset()

            Reset to the initial state.

        step()

            Advance by time time_period.

        present_value(t)

            Return the present value of a zero coupon bond of the
            appropriate type paying 1 in t years.

        sample(t = 7)

            Returns the time_period multipicative real return (change
            in value) for zero coupon bonds of the appropriate type
            having an initial duration t years. May be called
            repeatedly with different values for t. Calling with the
            same value will return the same result, unless step() is
            also called.

        observe()

            Returns a tuple. Current real interest rate and/or
            inflation rate as appropriate.

    Calling reset(), step(), or observe() on nominal_bonds, calls the
    corresponding routines on real_bonds and inflation. They should
    not also be called separately.

    Inflation represents the nominal value of a bond that will earn
    interest at the rate of inflation. inflation defines an additional
    method:

        inflation()

            Returns the inflation rate factor to be experienced over
            the the next time period of length time_period.

    '''

    if need_nominal:
        need_inflation = True
    if need_inflation:
        need_real = True

    if need_real:
        real_bonds = RealBonds(time_period = time_period)
    else:
        real_bonds = None

    if need_inflation:
        inflation = BreakEvenInflation(real_bonds, time_period = time_period)
    else:
        inflation = None

    if need_nominal:
        nominal_bonds = NominalBonds(real_bonds, inflation, time_period = time_period)
    else:
        nominal_bonds = None

    return real_bonds, nominal_bonds, inflation

if __name__ == '__main__':

    seed(0)

    real_bonds, nominal_bonds, inflation = init()
    modeled_inflation = BreakEvenInflation(real_bonds, model_bond_volatility = False)

    print('Real bonds:')
    print()
    real_bonds._report()

    print()

    print('Inflation (as used to provide inflation volatility):')
    print()
    modeled_inflation._report()

    print()

    print('Inflation (as used to provide nominal bond volatility):')
    print()
    inflation._report()

    print()

    print('Nominal bonds (in nominal terms except for returns):')
    print()
    nominal_bonds._report()
