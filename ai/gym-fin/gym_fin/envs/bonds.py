# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from copy import copy
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

        self.reset()

    def reset(self):

        self.oup = OUProcess(self.a, self.sigma, mu = self.sir_mean, x = self.r0) # Underlying random movement in short interest rates.
        self.new_oup = copy(self.oup)
        self.new_oup.step(self.time_period)

    def _p(self, t):
        '''Return the present value of a zero coupon bound paying 1 at time t
        according to the typical yield curve.

        '''

        return (self.yield_curve.discount_rate(t) + self.adjust) ** - t

    def _present_value(self, oup, t):
        '''Return the present value of a zero coupon bond paying 1 at time t
        into the future when the short term interest rates are given
        by the underlying OU process, oup.

        '''

        #  https://en.wikipedia.org/wiki/Hull%E2%80%93White_model P(0, T).
        B = (1 - exp(- self.a * t)) / self.a
        A = self._p(t) * exp(B * self.sir_mean)
        P = A * exp(- B * self._short_interest_rate(oup))

        return P

    def present_value(self, t):
        '''Return the present value of a zero coupon bond paying 1 at timet t.'''

        return self._present_value(self.oup, t)

    def _yield(self, oup, t):
        '''Return the continuously compounded yield of a zero coupon bond
        paying 1 at time t when the short term interest rates are
        given by the underlying OU process, oup.

        '''

        return - log(self._present_value(oup, t)) / t if t > 0 else self._short_interest_rate(oup)

    def sample(self, t = 7):
        '''Current return for a zero coupon bond with duration t.'''

        assert t >= self.time_period

        return self._present_value(self.new_oup, t - self.time_period) / self._present_value(self.oup, t)

    def step(self, time_period = 1):

        self.oup = copy(self.new_oup)
        self.new_oup.step(time_period)

    def observe(self):

        return (self.oup.x, )

    def _report(self):

        durations = (1, 5, 7, 10, 20, 30)

        self.reset()
        print('duration initial_expected_yield observed_yield')
        for duration in durations:
            r = self._yield(self.oup, duration)
            r_expect = log(self.yield_curve.discount_rate(duration))
            print(duration, r_expect, r)

        print()

        print('duration mean_yield')
        for duration in durations:
            r = []
            self.reset()
            for _ in range(10000):
                r.append(self._yield(self.oup, duration))
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
                        r.append(self._yield(self.oup, duration))
                        self.step()
                    for year in range(year_low, year_high + 1):
                        yield_curve = self._deflate(YieldCurve(self.yield_curve.interest_rate, '{}-12-31'.format(year)))
                        r_expect.append(log(yield_curve.discount_rate(duration)))
                    print(duration, stdev(r_expect), stdev(r))

                print()

                print('duration expected_volatility_yield observed_volatility_yield')
                for duration in durations:
                    dr = []
                    self.reset()
                    for _ in range(10000):
                        r_old = self._yield(self.oup, duration)
                        r = self._yield(self.new_oup, duration)
                        self.step()
                        dr.append(r - r_old)
                    dr_expect = []
                    r_expect_old = None
                    for year in range(year_low, year_high + 1):
                        yield_curve = self._deflate(YieldCurve(self.yield_curve.interest_rate, '{}-12-31'.format(year)))
                        r_expect = log(yield_curve.discount_rate(duration))
                        if r_expect_old:
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
            print(self._short_interest_rate(self.new_oup), self.sample(20), self._yield(self.oup, 20))
            self.step()

        self.reset()

class RealBonds(Bonds):

    def __init__(self, *, a = 0.05, sigma = 0.004,
                 yield_curve = YieldCurve('real', '2017-12-31', date_str_low = '2005-01-01', adjust = 0),
                 r0 = None, standard_error = 0, time_period = 1):
        '''Chosen value of sigma, 0.004, intended to produce a short term real
        yield standard deviation of 0.012-0.013. The measured value
        over 2005-2017 was 1.33% (when rates were volatile).

        Chosen value of a, 0.05, intended to produce a long term (20
        year) real yield standard deviation of 0.007-0.008. The
        measured value over 2005-2017 was 0.77%.

        Chosen yield curve intended to be indicative of the present
        era.

        '''

        super().__init__(a = a, sigma = sigma, yield_curve = yield_curve, r0 = r0, standard_error = standard_error, time_period = time_period)

    def _short_interest_rate(self, oup):
        '''Return the annualized continuously compounded current short
        interest rate given the underlying OU process, oup.

        The term structure reveals an investor preference for shorter
        durations rather than true expectations of future rates and so
        is ignored.

        '''

        return oup.x

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
                 nominal_yield_curve = YieldCurve('nominal', '2017-12-31', date_str_low = '2005-01-01', adjust = 0),
                 inflation_risk_premium = 0, real_liquidity_premium = 0,
                 r0 = None, standard_error = 0, time_period = 1):
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

        Chosen yield curve intended to be indicative of the present
        era.

        '''

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
        
        deflated_yield_curve = DeflatedYieldCurve(nominal_yield_curve, real_bonds.yield_curve)

        super().__init__(a = a, sigma = sigma, yield_curve = deflated_yield_curve, r0 = r0, standard_error = standard_error, time_period = time_period)

    def present_value(self, t):

        return super().present_value(t) * exp((self.inflation_risk_premium - self.real_liquidity_premium) / t)

    def _forward(self, t):

        delta = 1e-3
        t = min(t, 1000) # Prevent math underflow.
        return - (log(self._p(t + delta)) - log(self._p(t))) / delta

    def _volatility_bonus(self, a, sigma, t):

        # https://www.math.nyu.edu/~benartzi/Slides10.3.pdf page 11.
        return sigma ** 2 * (1 - exp(- a * t)) ** 2 / (2 * a ** 2)

    def _short_interest_rate(self, oup):
        '''Return the annualized continuously compounded current short
        interest rate given the underlying OU process, oup.

        The term structure reveals the true expectation of future
        inflation and so is incorporated.

        '''

        return self._forward(oup.t) + self._volatility_bonus(self.a, self.sigma, oup.t) + oup.x - self.sir_mean

    def sample(self, t = 7):
        '''Return the period inflation factor.

        Sampling the short interest rate leads to incorrect estimates
        for the long term inflation rate.  This is because in our
        inflation model there is a term sigma^2 / (2 . a^2).  The
        values used were chosen in order to fit the nominal bond yield
        standard deviation, but these are not the true values for
        these parameters. We correct for this here.

        '''

        # In practice this routine is unlikely to be used.

        assert t >= self.time_period

        sample = self._present_value(self.new_oup, t - self.time_period) / self._present_value(self.oup, t)
        r = self._volatility_bonus(self.inflation_a, self.inflation_sigma, self.oup.t) - self._volatility_bonus(self.a, self.sigma, self.oup.t)
        return sample * exp((r - self.inflation_risk_premium + self.real_liquidity_premium) / self.time_period)

    def _deflate(self, yield_curve):

        return DeflatedYieldCurve(yield_curve, YieldCurve('real', yield_curve.date, date_str_low = yield_curve.date_str_low))

class NominalBonds(Bonds):

    def __init__(self, real_bonds, inflation, *, time_period = 1):

        self.real_bonds = real_bonds
        self.inflation = inflation
        self.time_period = time_period

        self.yield_curve = self.inflation.nominal_yield_curve

    def reset(self):

        self.real_bonds.reset()
        self.inflation.reset()

        self.oup = (self.real_bonds.oup, self.inflation.oup)
        self.new_oup = (self.real_bonds.new_oup, self.inflation.new_oup)

    def _short_interest_rate(self, oup):

        return self.real_bonds._short_interest_rate(oup[0]) + self.inflation._short_interest_rate(oup[1])

    def _present_value(self, oup, t):

        return self.real_bonds._present_value(oup[0], t) * self.inflation._present_value(oup[1], t)

    def sample(self, t = 7):

        sample = super().sample(t)
        period_inflation = self.inflation._present_value(self.oup[1], self.time_period)

        return sample * period_inflation

    def step(self, time_period = 1):

        self.real_bonds.step(time_period)
        self.inflation.step(time_period)

        self.oup = (self.real_bonds.oup, self.inflation.oup) # Replaced by copy.
        #self.new_oup = (self.real_bonds.new_oup, self.inflation.new_oup)

    def observe(self):

        return self.real_bonds.observe() + self.inflation.observe()

    def _deflate(self, yield_curve):

        return yield_curve

def init(time_period = 1):
    '''Return a tuple of objects (real_bonds, inflation, nominal_bonds)
    They each provide the following methods:

        reset()

            Reset to the initial state.

        step()

            Advance by time_period.

        present_value(t)

            Return the present value of a zero coupon bond of the
            appropriate type paying 1 in t years.

        sample(n = 7)

            Returns the time_period multipicative real return (change
            in value) for zero coupon bonds of the appropriate type
            having an initial duration n years. May be called
            repeatedly with different values for n. Calling with the
            same value will return the same result, unless step() is
            also called.

        observe()

            Returns a tuple. Current real interest rate and/or
            inflation rate as appropriate.

    Calling reset(), step(), or observe() on nominal_bonds, calls the
    corresponding routines on real_bonds and inflation. They should
    not also be called separately.

    Inflation represents the nominal value of a bond that will earn
    interest at the rate of inflation.

    '''
    
    real_bonds = RealBonds(time_period = time_period)
    inflation = BreakEvenInflation(real_bonds, time_period = time_period)
    nominal_bonds = NominalBonds(real_bonds, inflation, time_period = time_period)

    return real_bonds, nominal_bonds, inflation

if __name__ == '__main__':

    seed(0)

    real_bonds, nominal_bonds, inflation = init()
    modeled_inflation = BreakEvenInflation(real_bonds, model_bond_volatility = False)

    print('Real bonds:')
    print()
    real_bonds._report()

    print()

    print('Inflation (as modeled):')
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
