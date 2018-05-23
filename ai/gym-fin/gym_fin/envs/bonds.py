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

from yield_curve import YieldCurve

from gym_fin.envs.ou_process import OUProcess

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

        "standard_error" is the standard error of the estimated
        continuously compounded annual yield curve yield.

        "time_period" step size in years.

        '''

        self.a = a # Alpha in Wikipedia and hibbert.
        self.sigma = sigma
        self.yield_curve = yield_curve
        self.r0 = r0
        self.standard_error = standard_error
        self.time_period = time_period

        self._sr_cache = {}

        self.reset()

    def reset(self):

        self.adjust = normalvariate(0, self.standard_error)
        self.sir_init = self.yield_curve.spot(0) + self.adjust
        self.sir0 = self.sir_init if self.r0 == None else self.r0

        self.t = 0
        self.oup = OUProcess(self.time_period, self.a, self.sigma, mu = self.sir_init, x = self.sir0) # Underlying random movement in short interest rates.

        self._sir_cache = {}

    def _log_p(self, t):
        '''Return the log present value of a zero coupon bound paying 1 at
        time t according to the typical yield curve.

        '''

        try:
            sr = self._sr_cache[t]
        except KeyError:
            sr = self.yield_curve.spot(t)
            if len(self._sr_cache) < 1000:
                self._sr_cache[t] = sr

        return - t * (sr + self.adjust)

    def _log_present_value(self, t, *, next = False):
        '''Return the present value of a zero coupon bond paying 1 at time t
        into the future when the short term interest rates are given
        by the underlying OU process current or next value depending
        on the value of next.

        '''

        cache_t = self.t + int(next) * self.time_period
        try:
            sir = self._sir_cache[cache_t]
        except KeyError:
            if len(self._sir_cache) >= 100:
                self._sir_cache = {}
            if next:
                sir = self._short_interest_rate(self.oup.next_x)
            else:
                sir = self._short_interest_rate(self.oup.x)
            self._sir_cache[cache_t] = sir

        #  https://en.wikipedia.org/wiki/Hull%E2%80%93White_model P(0, T).
        B = (1 - exp(- self.a * t)) / self.a
        log_P = self._log_p(t) + B * (self.sir_init - sir)

        return log_P

    def present_value(self, t):
        '''Return the present value of a zero coupon bond paying 1 at timet t.'''

        return exp(self._log_present_value(t))

    def _yield(self, t):
        '''Return the current continuously compounded yield of a zero coupon
        bond paying 1 at time t.

        '''

        return - self._log_present_value(t) / t if t > 0 else self._short_interest_rate(self.oup.x)

    def sample(self, duration = 7):
        '''Current real return for a zero coupon bond with duration
        duration.

        '''

        assert duration >= self.time_period

        return exp(self._log_present_value(duration - self.time_period, next = True) - self._log_present_value(duration))

    def step(self):

        self.t += self.time_period
        self.oup.step()

    def _report(self):

        durations = (1, 5, 7, 10, 20, 30)

        self.reset()
        print('duration observed_yield_curve_yield initial_yield')
        for duration in durations:
            r = self._yield(duration)
            r_expect = log(self.yield_curve.discount_rate(duration)) - self._inflation_adjust_yield(duration)
            print(duration, r_expect, r)

        print()

        print('duration mean_yield')
        for duration in durations:
            r = []
            self.reset()
            for _ in range(100000):
                r.append(self._yield(duration))
                self.step()
            print(duration, mean(r))

        if self.yield_curve.date_low:

            year_low = int(self.yield_curve.date_low[:4])
            year_high = int(self.yield_curve.date[:4])

            if year_low != year_high:

                print()

                print('duration observed_standard_deviation_yield standard_deviation_yield')
                for duration in durations:
                    r = []
                    r_expect = []
                    self.reset()
                    for _ in range(10000):
                        r.append(self._yield(duration))
                        self.step()
                    for year in range(year_low, year_high + 1):
                        yield_curve = self._deflate(YieldCurve(self.yield_curve.interest_rate, '{}-12-31'.format(year)))
                        r_expect.append(log(yield_curve.discount_rate(duration)) / self._inflation_adjust_annual(year))
                    print(duration, stdev(r_expect), stdev(r))

                print()

                print('duration observed_volatility_yield volatility_yield')
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
                    for year in range(year_low - 1, year_high + 1):
                        yield_curve = self._deflate(YieldCurve(self.yield_curve.interest_rate, '{}-12-31'.format(year)))
                        r_expect = log(yield_curve.discount_rate(duration)) / self._inflation_adjust_annual(year)
                        if r_expect_old != None:
                            dr_expect.append(r_expect - r_expect_old)
                        r_expect_old = r_expect
                    print(duration, stdev(dr_expect), stdev(dr))

                print()

                print('duration observed_mean_return mean_return observed_standard_deviation standard_deviation')
                for duration in durations:
                    ret = []
                    ret_expect = []
                    r_expect_old = None
                    self.reset()
                    for _ in range(100000):
                        ret.append(self.sample(duration))
                        self.step()
                    for year in range(year_low - 1, year_high + 1):
                        yield_curve = self._deflate(YieldCurve(self.yield_curve.interest_rate, '{}-12-31'.format(year)))
                        r_expect = yield_curve.discount_rate(duration - 1)
                        if r_expect_old != None:
                            ret_expect.append(r_expect ** (1 - duration) / r_expect_old ** - duration / self._inflation_adjust_annual(year))
                        r_expect_old = yield_curve.discount_rate(duration)
                    print(duration, mean(ret_expect), mean(ret), stdev(ret_expect), stdev(ret))

        print()

        self.reset()
        print('sample returns')
        print('short_interest_rate 20_year_real_return 20_year_yield')
        for _ in range(50):
            print(self._short_interest_rate(self.oup.next_x), self.sample(20), self._yield(20))
            self.step()

        self.reset()

class RealBonds(Bonds):

    def __init__(self, *, a = 0.14, sigma = 0.011, yield_curve = None, r0 = None, standard_error = 0, time_period = 1):
        '''Chosen value of sigma, 0.011, intended to produce a short term real
        yield volatility of 0.9-1.0%. The measured value over
        2005-2017 was 1.00%. Obtained value is 0.99%.

        Chosen value of a, 0.14, intended to produce a long term (20
        year) real return standard deviation of 7-8%. The measured
        value over 2005-2017 was 11.4% (when rates were volatile). The
        real nominal bond observed standard deviation is 17.8% whereas
        according to the Credit Suisse Yearbook 11.2% is more typical,
        so by a simple scaling 7.2% seems a reasonable
        expectation for real bonds. Obtained value is 7.3%.

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

    def _inflation_adjust_yield(self, duration):

        return 0

    def _inflation_adjust_annual(self, year):

        return 1

class YieldCurveSum(object):

    def __init__(self, yield_curve1, yield_curve2, *, weight = 1):

        self.yield_curve1 = yield_curve1
        self.yield_curve2 = yield_curve2
        self.weight = weight

        self.interest_rate = self.yield_curve1.interest_rate
        self.date = yield_curve1.date
        self.date_low = yield_curve1.date_low

    def spot(self, y):

        return self.yield_curve1.spot(y) + self.weight * self.yield_curve2.spot(y)

    def forward(self, y):

        return self.yield_curve1.forward(y) + self.weight * self.yield_curve2.forward(y)

    def discount_rate(self, y):

        return self.yield_curve1.discount_rate(y) * self.yield_curve2.discount_rate(y) ** self.weight

class BreakEvenInflation(Bonds):

    def __init__(self, real_bonds, *, inflation_a = 0.14, inflation_sigma = 0.013, bond_a = 0.14, bond_sigma = 0.013, model_bond_volatility = True,
        nominal_yield_curve = None, inflation_risk_premium = 0, real_liquidity_premium = 0, r0 = None, standard_error = 0, time_period = 1):
        '''Keeping inflation parameters the same as the bond parameters
        simplifies the model.

        Chosen value for inflation_a, 0.14, the same as in the real case.

        Chosen value of inflation_sigma, 0.013, produces a reasonable
        estimate of the long term (20 year) standard deviation of the
        inflation rate (as modeled to provide inflation
        volatility). Measured value was 0.53%. Obtained value was
        0.82%. This seems quite reasonable given inflation has
        recently been constrained. Additionally. the measured short
        term inflation yield volatility is 1.33%, compared to a
        obtained value of 1.17%.

        Chosen value of bond_a, 0.14, the same as in the real case.

        Chosen value of bond_sigma, 0.013, intended to produce a long
        term (20 year) nominal bond real return standard deviation of
        11-12%. The measured value over 2005-2017 was 17.8% (when
        rates were volatile). Obtained value is 11.0%. As in the real
        case this is less than the observed value, and is inline with
        the 11.2% standard deviation for long term government bonds
        reported in the Credit Suisse Global Investment Returns
        Yearbook 2017.

        model_bond_volatility specifies whether the process should be
        such as to provide a reasonable model for the long term
        nominal return standard deviation, or the inflation rate
        standard deviation. In case of the former an inflation rate
        model tracks the process and is used when calling the
        present_value() and observe() functions. When the inflation
        and bond parameters are the same model_bond_volatility has no
        effect.

        Chosen default yield curve intended to be indicative of the
        present era.

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

        deflated_yield_curve = YieldCurveSum(nominal_yield_curve, real_bonds.yield_curve, weight = -1)

        super().__init__(a = a, sigma = sigma, yield_curve = deflated_yield_curve, r0 = r0, standard_error = standard_error, time_period = time_period)

        self.reset()

    def reset(self):

        super().reset()

        # Inflation model OU Process tracks modeled nominal bond standard deviation OU Process.
        self.inflation_oup = OUProcess(self.time_period, self.inflation_a, self.inflation_sigma, mu = self.sir_init, x = self.sir0, norm = self.oup.norm)

    def _sir(self, t, a, sigma):

        # https://www.math.nyu.edu/~benartzi/Slides10.3.pdf page 11.
        return self.yield_curve.forward(t) + (sigma * (1 - exp(- a * t)) / a) ** 2 / 2

    def _short_interest_rate(self, oup_x):
        '''Return the annualized continuously compounded current short
        interest rate given the underlying OU process value, oup_x.

        The term structure reveals the true expectation of future
        inflation and so is incorporated.

        '''

        return self._sir(self.t, self.a, self.sigma) + oup_x - self.sir_init

    def _model_short_interest_rate(self):
        '''Current short interest rate based on fitting the inflation model,
        not the nominal bond yield standard deviation model.

        '''

        return self._sir(self.t, self.inflation_a, self.inflation_sigma) + self.inflation_oup.x - self.sir_init

    def present_value(self, t):

        sir = self._model_short_interest_rate()

        #  https://en.wikipedia.org/wiki/Hull%E2%80%93White_model P(0, T).
        B = (1 - exp(- self.inflation_a * t)) / self.inflation_a
        P = exp(self._log_p(t) + B * (self.sir_init - sir) - self.adjust_rate / self.time_period)

        return P

    def inflation(self):

        return 1 / present_value(self.time_period)

    def step(self):

        super().step()
        self.inflation_oup.step(norm = self.oup.norm)

    def observe(self):

        return (self._model_short_interest_rate(), )

    def _deflate(self, yield_curve):

        return YieldCurveSum(yield_curve, YieldCurve('real', yield_curve.date, date_str_low = yield_curve.date_low), weight = -1)

    def _inflation_adjust_yield(self, duration):

        return 0

    def _inflation_adjust_annual(self, year):

        return 1

class OUProcessTuple(object):

    def __init__(self, *oups):

        self.oups = oups

    @property
    def x(self):

        return tuple(oup.x for oup in self.oups)

    @property
    def next_x(self):

        return tuple(oup.next_x for oup in self.oups)

# Annual inflation rate, needed for manual calibration of Hull-White parameters.
inflation_rate = {
    2004: 0.027,
    2005: 0.034,
    2006: 0.032,
    2007: 0.028,
    2008: 0.038,
    2009: -0.004,
    2010: 0.016,
    2011: 0.032,
    2012: 0.021,
    2013: 0.015,
    2014: 0.016,
    2015: 0.001,
    2016: 0.013,
    2017: 0.021,
}

class NominalBonds(Bonds):

    def __init__(self, real_bonds, inflation, *, time_period = 1):

        self.real_bonds = real_bonds
        self.inflation = inflation
        self.time_period = time_period

        self.yield_curve = inflation.nominal_yield_curve # Only used by _report() for expected values.

        self.reset()

    def reset(self):

        self.real_bonds.reset()
        self.inflation.reset()

        self.oup = OUProcessTuple(self.real_bonds.oup, self.inflation.oup)

    def _short_interest_rate(self, oup_x):

        return self.real_bonds._short_interest_rate(oup_x[0]) + self.inflation._short_interest_rate(oup_x[1])

    def _log_present_value(self, t, *, next = False):

        return self.real_bonds._log_present_value(t, next = next) + self.inflation._log_present_value(t, next = next)

    def _yield(self, t):

        _yield = super()._yield(t)

        return _yield - self.inflation._yield(t)

    def sample(self, duration = 7):

        sample = self.real_bonds.sample(duration) * self.inflation.sample(duration)
        period_inflation = exp(self.inflation._log_present_value(self.time_period))

        return sample * period_inflation

    def step(self):

        self.real_bonds.step()
        self.inflation.step()

    def observe(self):

        return ()

    def _deflate(self, yield_curve):

        return yield_curve

    def _inflation_adjust_yield(self, duration):

        return self.inflation._yield(duration)

    def _inflation_adjust_annual(self, year):

        return 1 + inflation_rate[year]

class BondsMeasuredInNominalTerms(Bonds):

    def __init__(self, bonds, inflation):

        self.bonds = bonds
        self.inflation = inflation
        self.time_period = self.bonds.time_period

        self.yield_curve = YieldCurveSum(bonds.yield_curve, inflation.yield_curve)

    def reset(self):

        self.bonds.reset()
        self.inflation.reset()

        self.oup = OUProcessTuple(self.bonds.oup, self.inflation.oup)

    def _short_interest_rate(self, oup_x):

        return self.bonds._short_interest_rate(oup_x[0]) + self.inflation._short_interest_rate(oup_x[1])

    def _yield(self, t):

        return self.bonds._yield(t) + self.inflation._yield(t)

    def sample(self, duration = 7):

        sample = self.bonds.sample(duration)
        period_inflation = exp(self.inflation._log_present_value(self.time_period))

        return sample / period_inflation

    def step(self):

        self.bonds.step()
        self.inflation.step()

    def _deflate(self, yield_curve):

        return YieldCurve('nominal', yield_curve.date, date_str_low = yield_curve.date_low)

    def _inflation_adjust_yield(self, duration):

        return self.bonds._inflation_adjust_yield(duration)

    def _inflation_adjust_annual(self, year):

        return self.bonds._inflation_adjust_annual(year)

def bonds_init(need_real = True, need_nominal = True, need_inflation = True, real_standard_error = 0, inflation_standard_error = 0, time_period = 1):
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

        sample(duration = 7)

            Returns the time_period multipicative real return (change
            in value) for zero coupon bonds of the appropriate type
            having an initial duration duration years. May be called
            repeatedly with different values for duration. Calling
            with the same value will return the same result, unless
            step() is also called.

        observe()

            Returns a tuple. Current short real interest rate or short
            inflation rate as appropriate. For nominal bonds the tuple
            is empty.

    The nominal_bonds model need to be kept in sync with the real
    bonds and inflation models. Calling reset() or step() on
    nominal_bonds takes care of this by calling the corresponding
    routines on both real bonds and inflation. They should not also be
    called separately.

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
        real_bonds = RealBonds(standard_error = real_standard_error, time_period = time_period)
    else:
        real_bonds = None

    if need_inflation:
        inflation = BreakEvenInflation(real_bonds, standard_error = inflation_standard_error, time_period = time_period)
    else:
        inflation = None

    if need_nominal:
        nominal_bonds = NominalBonds(real_bonds, inflation, time_period = time_period)
    else:
        nominal_bonds = None

    return real_bonds, nominal_bonds, inflation

if __name__ == '__main__':

    seed(0)

    real_bonds, nominal_bonds, inflation = bonds_init()
    modeled_inflation = BreakEvenInflation(real_bonds, model_bond_volatility = False)
    nominal_real_bonds = BondsMeasuredInNominalTerms(real_bonds, inflation)
    nominal_nominal_bonds = BondsMeasuredInNominalTerms(nominal_bonds, inflation)

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

    print('Nominal bonds (in real terms):')
    print()
    nominal_bonds._report()

    print()

    print('Real bonds (in nominal terms):')
    print()
    nominal_real_bonds._report()

    print()

    print('Nominal bonds (in nominal terms):')
    print()
    nominal_nominal_bonds._report()
