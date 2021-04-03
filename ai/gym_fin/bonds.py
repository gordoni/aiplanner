# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import exp, log, sqrt
from random import normalvariate, seed
from statistics import mean, stdev

import numpy as np

import cython

from spia import YieldCurve

from ai.gym_fin.factory_ou_process import make_ou_process

@cython.cclass
class BondsBase:

    # Cython - Make interest_rate into a property so it can be accessed by the spias module as a surrogate YieldCurve.

    @property
    def interest_rate(self):

        return self._interest_rate

    @interest_rate.setter
    def interest_rate(self, interest_rate):

        self._interest_rate = interest_rate

    def __init__(self):

        self.e = exp(1) # Cython - self.e ** x which uses the C pow function is faster than calling the Python exp(x).

    def reset(self):

        assert False

    def step(self):

        assert False

    @cython.locals(t = cython.double)
    def discount_rate(self, t):

        assert False

    @cython.locals(duration = cython.double)
    def sample(self, duration):

        assert False

    def observe(self):

        assert False

@cython.cclass
class Bonds(BondsBase):
    '''Short rate models - https://en.wikipedia.org/wiki/Short-rate_model .

    Hull-White one-factor model - https://en.wikipedia.org/wiki/Hull%E2%80%93White_model .
    '''

    def __init__(self, *, a, sigma, yield_curve, r0_type, r0, standard_error, static_bonds, time_period):
        '''Initialize a bonds object.

        "a" interest rate mean reversion rate. Default value chosen to
        result in a reasonable estimate for the expected volatility of
        the long term interest rate.

        "sigma" volatility of rates. Default value chosen as a
        reasonable estimate of the expected volatility in the short
        term interest rate.

        "yield_curve" interest rate YieldCurve object representing the
        typical yield curve to use.

        "r0_type" determines the time zero annualized continuously
        compounded interest rate: 'sample' to sample from possible far
        future short interest rates, 'current' to use the current
        yield curve derived short interest rate, or 'value' to use a
        specific value.

        "r0" is the specific value to use for "r0_type" 'value'.

        "standard_error" is the standard error of the estimated
        continuously compounded annual yield curve yield.

        "static_bonds" supresses Hull-White temporal variability.

        "time_period" step size in years.

        '''

        self.a = a # Alpha in Wikipedia and hibbert.
        self.sigma = sigma
        self.yield_curve = yield_curve
        self.r0_type = r0_type
        self.r0 = r0
        self.standard_error = standard_error
        self.static_bonds = static_bonds
        self.time_period = time_period

        super().__init__()

        self.interest_rate = None

        self.mean_short_interest_rate = log(self.yield_curve.discount_rate(0))

        self.oup = make_ou_process(self.time_period, self.a, self.sigma)
            # Underlying random movement in short interest rates.

        self._sr_cache = {}

        self.reset()

    def reset(self):

        self.adjust = normalvariate(0, self.standard_error)
        self.sir_init = self.mean_short_interest_rate + self.adjust
        if self.r0_type == 'current':
            self.sir0 = self.sir_init
        elif self.r0_type == 'sample':
            self.sir0 = normalvariate(self.sir_init, self.sigma / sqrt(2 * self.a))
        elif self.r0_type == 'value':
            assert self.r0 != -1
            self.sir0 = self.r0
        else:
            assert False, 'Invalid short rate type.'

        self.t = 0
        self.oup.reset(mu = self.sir_init, x = self.sir0, norm = 0 if self.static_bonds else None)

        self._lpv_cache_valid = False
        self._lpv_cache = -1
        self._discount_cache = {}

    @cython.locals(next = cython.bint)
    def _short_interest_rate(self, next = False):

        assert False

    @cython.locals(t = cython.double, next = cython.bint)
    def _log_present_value(self, t, next = False):
        '''Return the present value of a zero coupon bond paying 1 at time t
        into the future when the short term interest rates are given
        by the underlying OU process current or next value depending
        on the value of next.

        '''

        sir: cython.double
        if next:
            sir = self._short_interest_rate(True)
        elif self._lpv_cache_valid:
            sir = self._lpv_cache
        else:
            sir = self._short_interest_rate()
            self._lpv_cache_valid = True
            self._lpv_cache = sir

        #  https://en.wikipedia.org/wiki/Hull%E2%80%93White_model P(0, T).
        sr: cython.double; log_P: cython.double; ex: cython.double; B: cython.double
        try:
            sr = self._sr_cache[t]
        except KeyError:
            sr = self.yield_curve.spot(t)
            if len(self._sr_cache) < 1000:
                self._sr_cache[t] = sr
        log_P = - t * (sr + self.adjust)
        ex = self.e ** (- self.a * t)
        B = (1 - ex) / self.a
        log_P += B * (self.sir_init - sir)

        return log_P

    @cython.locals(t = cython.double)
    def discount_rate(self, t):
        '''Return 1 + the annual spot discount rate of a zero coupon bond
        paying 1 at timet t.

        '''

        dr: cython.double
        try:
            dr = self._discount_cache[t]
        except KeyError:
            lpv: cython.double
            if t > 0:
                lpv = self._log_present_value(t)
                lpv = - lpv / t
            else:
                lpv = self._short_interest_rate()
            dr = self.e ** lpv
            if len(self._discount_cache) < 1000:
                self._discount_cache[t] = dr

        return dr

    def _yield(self, t):
        '''Return the current continuously compounded yield of a zero coupon
        bond paying 1 at time t.

        '''

        return - self._log_present_value(t) / t if t > 0 else self._short_interest_rate()

    @cython.locals(duration = cython.double)
    def sample(self, duration):
        '''Current real return for a zero coupon bond with duration
        duration.

        '''

        assert duration >= self.time_period

        nxt: cython.double; cur: cython.double
        nxt = self._log_present_value(duration - self.time_period, True)
        cur = self._log_present_value(duration)

        return self.e ** (nxt - cur)

    def step(self):

        if self.static_bonds:
            return

        self.t += self.time_period
        self._lpv_cache_valid = False
        self._discount_cache = {}
        self.oup.step()

    def _report(self):

        durations = (1, 2, 5, 7, 10, 15, 20, 30)

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
                        if r_old is not None:
                            dr.append(r - r_old)
                        r_old = r
                    dr_expect = []
                    r_expect_old = None
                    for year in range(year_low - 1, year_high + 1):
                        yield_curve = self._deflate(YieldCurve(self.yield_curve.interest_rate, '{}-12-31'.format(year)))
                        r_expect = log(yield_curve.discount_rate(duration)) / self._inflation_adjust_annual(year)
                        if r_expect_old is not None:
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
                        if r_expect_old is not None:
                            ret_expect.append(r_expect ** (1 - duration) / r_expect_old ** - duration / self._inflation_adjust_annual(year))
                        r_expect_old = yield_curve.discount_rate(duration)
                    print(duration, mean(ret_expect), mean(ret), stdev(ret_expect), stdev(ret))

        print()

        self.reset()
        print('sample returns')
        print('short_interest_rate 20_year_real_return 20_year_yield')
        for _ in range(50):
            print(self._short_interest_rate(True), self.sample(20), self._yield(20))
            self.step()

        self.reset()

@cython.cclass
class RealBonds(Bonds):

    def __init__(self, *, a = 0.14, sigma = 0.011, yield_curve, r0_type = 'current', r0 = -1, standard_error = 0, static_bonds = False, time_period = 1):
        '''Chosen value of sigma, 0.011, intended to produce a short term real
        yield volatility of 0.9-1.0%. The measured value over
        2005-2019 was 0.99%. Obtained value is 1.00%.

        Chosen value of a, 0.14, intended to produce a long term (15
        year) real return standard deviation of about 6.5%. The observed
        value over 2005-2019 was 8.9% (when rates were volatile). The
        real nominal bond observed standard deviation is 14.9% whereas
        according to the Credit Suisse Yearbook 10.9% is more typical,
        so by a simple scaling 6.5% seems a reasonable expectation for
        real bonds. Obtained value is 6.6%.

        Chosen default yield curve intended to be indicative of the
        present era.

        '''

        super().__init__(a = a, sigma = sigma, yield_curve = yield_curve, r0_type = r0_type, r0 = r0, standard_error = standard_error, static_bonds = static_bonds,
            time_period = time_period)

        self.interest_rate = 'real'

    @cython.locals(next = cython.bint)
    def _short_interest_rate(self, next = False):
        '''Return the annualized continuously compounded current short
        interest rate given the underlying OU process.

        The term structure reveals an investor preference for shorter
        durations rather than true expectations of future rates and so
        is ignored.

        '''

        if next and not self.static_bonds:
            return self.oup.next_x
        else:
            return self.oup.x

    def observe(self):

        return self._short_interest_rate()

    def _deflate(self, yield_curve):

        return yield_curve

    def _inflation_adjust_yield(self, duration):

        return 0

    def _inflation_adjust_annual(self, year):

        return 1

@cython.cclass
class YieldCurveSum:
#class YieldCurveSum(YieldCurve):
    # Would have liked this to inherit fromYieldCurve, but that would have required the Cython pxd file cimporting YieldCurve, preventing us from importing it above.

    @property
    def date(self):

        return self._date

    @property
    def date_low(self):

        return self._date_low

    @property
    def interest_rate(self):

        return self._interest_rate

    def __init__(self, yield_curve1, yield_curve2, *, weight = 1, offset = 0):

        self.yield_curve1 = yield_curve1
        self.yield_curve2 = yield_curve2
        self.weight = weight
        assert weight in (-1, 0, 1)
        self.offset = offset

        self._interest_rate = self.yield_curve1.interest_rate
        self._date = yield_curve1.date
        self._date_low = yield_curve1.date_low
        self.exp_offset = exp(self.offset)

    def spot(self, y):

        spot1: cython.double; spot2: cython.double
        spot1 = self.yield_curve1.spot(y)
        spot2 = self.yield_curve2.spot(y)
        return spot1 + self.weight * spot2 + self.offset

    def forward(self, y):

        forward1: cython.double; forward2: cython.double
        forward1 = self.yield_curve1.forward(y)
        forward2 = self.yield_curve2.forward(y)
        return forward1 + self.weight * forward2 + self.offset

    def discount_rate(self, y):

        discount1: cython.double; discount2: cython.double
        discount1 = self.yield_curve1.discount_rate(y)
        discount2 = self.yield_curve2.discount_rate(y)
        if self.weight == -1:
            return discount1 / discount2 * self.exp_offset
        elif self.weight == 0:
            return discount1 * self.exp_offset
        else:
            return discount1 * discount2 * self.exp_offset

@cython.cclass
class Inflation(Bonds):

    @cython.locals(real_bonds = RealBonds)
    def __init__(self, real_bonds, *, inflation_a = 0.12, inflation_sigma = 0.013, bond_a = 0.12, bond_sigma = 0.013, model_bond_volatility = True,
        nominal_yield_curve, inflation_risk_premium = 0, real_liquidity_premium = 0, r0_type = 'current', r0 = -1, standard_error = 0, static_bonds = False,
        time_period = 1):
        '''Keeping inflation parameters the same as the bond parameters
        simplifies the model.

        Chosen value of inflation_sigma, 0.013, produces a reasonable
        estimate of the the short term inflation yield volatility (as
        used to provide nominal bond volatility). Measured value over
        2005-2019 was 1.23%, compared to a obtained value of 1.20%.

        Chosen value of inflation_a, 0.12, produces a reasonable
        estimate of the long term (15 year) standard deviation of the
        inflation rate. Measured value over 2005-2019 was
        0.55%. Obtained value was 1.24%. This seems quite reasonable
        given inflation has recently been constrained. Additionally,
        chosen value intended to produce a long term (15 year) nominal
        bond real return standard deviation of about 11%. The measured
        value over 2005-2019 was 14.4% (when rates were
        volatile). Obtained value is 10.8%. As in the real case this
        is less than the observed value, and is inline with the 10.9%
        standard deviation for long term government bonds reported in
        the Credit Suisse Global Investment Returns Yearbook 2019.

        model_bond_volatility specifies whether the process should be
        such as to provide a reasonable model for the long term
        nominal return standard deviation, or the inflation rate
        standard deviation. In case of the former an inflation rate
        model tracks the process and is used when calling the
        inflation() and observe() functions. When the inflation and
        bond parameters are the same model_bond_volatility has no
        effect.

        Chosen default yield curve intended to be indicative of the
        present era.

        '''
        self.inflation_a = inflation_a
        self.inflation_sigma = inflation_sigma
        self.bond_a = bond_a
        self.bond_sigma = bond_sigma
        self.nominal_yield_curve = nominal_yield_curve
        self.inflation_risk_premium = inflation_risk_premium
        self.real_liquidity_premium = real_liquidity_premium
        self.model_bond_volatility = model_bond_volatility

        if self.model_bond_volatility:
            a = bond_a
            sigma = bond_sigma
        else:
            a = inflation_a
            sigma = inflation_sigma

        self.nominal_premium = self.inflation_risk_premium - self.real_liquidity_premium
        deflated_yield_curve = YieldCurveSum(nominal_yield_curve, real_bonds.yield_curve, weight = -1, offset = - self.nominal_premium)

        self._sir_cache = {}

        if not self.model_bond_volatility:
            # Inflation model OU Process tracks modeled nominal bond standard deviation OU Process.
            self.inflation_oup = make_ou_process(time_period, self.inflation_a, self.inflation_sigma)

        super().__init__(a = a, sigma = sigma, yield_curve = deflated_yield_curve, r0_type = r0_type, r0 = r0, standard_error = standard_error,
            static_bonds = static_bonds, time_period = time_period)

        self.interest_rate = 'inflation'

        self.reset()

    def reset(self):

        #super(Inflation, self).reset() # Cython needed super() args because reset() was cpdefed.
        super().reset()

        if not self.model_bond_volatility:
            self.inflation_oup.reset(mu = self.sir_init, x = self.sir0, norm = self.oup.norm)
        else:
            self.inflation_oup = self.oup

    @cython.locals(t = cython.double, a = cython.double, sigma = cython.double)
    def _sir_no_adjust(self, t, a, sigma):

        sir: cython.double
        try:
            sir = self._sir_cache[t]
        except KeyError:
            # # https://www.math.nyu.edu/~benartzi/Slides10.3.pdf page 11.
            # forward: cython.double; ex: cython.double
            # forward = self.yield_curve.forward(t)
            # ex = self.e ** (- a * t)
            # sir = forward + (sigma * (1 - ex) / a) ** 2 / 2
            sir = self.yield_curve.forward(t)
            if len(self._sir_cache) < 1000:
                self._sir_cache[t] = sir

        return sir

    @cython.locals(next = cython.bint)
    def _short_interest_rate(self, next = False):
        '''Return the annualized continuously compounded current short
        interest rate given the underlying OU process.

        The term structure reveals the true expectation of future
        inflation and so is incorporated.

        '''

        t: cython.double; x: cython.double
        if next and not self.static_bonds:
            t = self.t + self.time_period
            x = self.oup.next_x
        else:
            t = self.t
            x = self.oup.x

        sir: cython.double
        sir = self._sir_no_adjust(t, self.a, self.sigma)

        return self.adjust + sir + x - self.sir_init

    def _model_short_interest_rate(self):
        '''Current short interest rate based on fitting the inflation model,
        not the nominal bond yield standard deviation model.

        '''

        sir: cython.double; x: cython.double
        sir = self._sir_no_adjust(self.t, self.inflation_a, self.inflation_sigma)
        x = self.inflation_oup.x
        return self.adjust + sir + x - self.sir_init

    def inflation(self):

        sir: cython.double
        sir = self._model_short_interest_rate()

        t: cython.double
        t = self.time_period

        #  https://en.wikipedia.org/wiki/Hull%E2%80%93White_model P(0, T).
        sr: cython.double; log_P: cython.double; ex: cython.double; B: cython.double
        try:
            sr = self._sr_cache[t]
        except KeyError:
            sr = self.yield_curve.spot(t)
            if len(self._sr_cache) < 1000:
                self._sr_cache[t] = sr
        log_P = - t * (sr + self.adjust)
        ex = self.e ** (- self.inflation_a * t)
        B = (1 - ex) / self.inflation_a
        log_P += B * (self.sir_init - sir)

        return self.e ** - log_P

    def inflation_long_run_expectation(self):

        infl = self.yield_curve.forward(100)

        return self.e ** infl

    def step(self):

        if self.static_bonds:
            return

        super(Inflation, self).step()
        if not self.model_bond_volatility:
            self.inflation_oup.step(norm = self.oup.norm)

    def observe(self):

        return self._model_short_interest_rate()

    def _deflate(self, yield_curve):

        return YieldCurveSum(yield_curve, YieldCurve('real', yield_curve.date, date_str_low = yield_curve.date_low), weight = -1)

    def _inflation_adjust_yield(self, duration):

        return 0

    def _inflation_adjust_annual(self, year):

        return 1

# Annual inflation rate, needed for manual calibration of Hull-White parameters.
# CPI-U not seasonally adjusted, percent change from year ago - https://fred.stlouisfed.org/series/CPIAUCNS
# or CPI-U 12-month percent change Dec - https://data.bls.gov/cgi-bin/surveymost?cu
inflation_rate = {
    2004: 0.033,
    2005: 0.034,
    2006: 0.025,
    2007: 0.041,
    2008: 0.001,
    2009: 0.027,
    2010: 0.015,
    2011: 0.030,
    2012: 0.017,
    2013: 0.015,
    2014: 0.008,
    2015: 0.007,
    2016: 0.021,
    2017: 0.021,
    2018: 0.019,
    2019: 0.023,
    2020: 0.014,
}

@cython.cclass
class NominalBonds(Bonds):

    @cython.locals(inflation = Inflation)
    def __init__(self, real_bonds, inflation, *, real_bonds_adjust = 0, nominal_bonds_adjust = 0, time_period = 1):

        self.real_bonds = real_bonds
        self.inflation = inflation
        self.real_bonds_adjust = real_bonds_adjust
        self.nominal_bonds_adjust = nominal_bonds_adjust
        self.time_period = time_period

        super(Bonds, self).__init__()

        self.interest_rate = 'nominal'

        self.yield_curve = YieldCurveSum(inflation.nominal_yield_curve, inflation.nominal_yield_curve, weight = 0, offset = self.nominal_bonds_adjust - self.real_bonds_adjust) # Only used by _report() for expected values.

        self.reset()

    def reset(self):

        self.real_bonds.reset()
        self.inflation.reset()

        self._discount_cache = {}

    def _short_interest_rate(self, next = False):

        real_sir: cython.double; inflation_sir: cython.double
        real_sir = self.real_bonds._short_interest_rate(next)
        inflation_sir = self.inflation._short_interest_rate(next)
        return real_sir - self.real_bonds_adjust + inflation_sir + self.inflation.nominal_premium + self.nominal_bonds_adjust

    @cython.locals(t = cython.double)
    def _log_present_value(self, t, next = False):

        real_pv: cython.double; inflation_pv: cython.double
        real_pv = self.real_bonds._log_present_value(t, next)
        inflation_pv = self.inflation._log_present_value(t, next)
        return real_pv + inflation_pv - (self.inflation.nominal_premium + self.nominal_bonds_adjust) * t

    def _yield(self, t):

        _yield = super()._yield(t)

        return _yield - self.inflation._yield(t) - self.real_bonds_adjust

    @cython.locals(duration = cython.double)
    def sample(self, duration):

        real_sample: cython.double; inflation_sample: cython.double; inflation_log_pv: cython.double; period_inflation_reduction: cython.double
        real_sample = self.real_bonds.sample(duration)
        inflation_sample = self.inflation.sample(duration)
        inflation_log_pv = self.inflation._log_present_value(self.time_period)
        period_inflation_reduction = self.e ** \
            (inflation_log_pv + (self.inflation.nominal_premium + self.nominal_bonds_adjust - self.real_bonds_adjust) * self.time_period)

        return real_sample * inflation_sample * period_inflation_reduction

    def step(self):

        self.real_bonds.step()
        self.inflation.step()

        self._discount_cache = {}

    def observe(self):

        return 0.0

    def _deflate(self, yield_curve):

        return yield_curve

    def _inflation_adjust_yield(self, duration):

        return self.inflation._yield(duration)

    def _inflation_adjust_annual(self, year):

        return 1 + inflation_rate[year]

@cython.cclass
class CorporateBonds(BondsBase):

    def __init__(self, nominal_bonds, corporate_nominal_spread):

        self.nominal_bonds = nominal_bonds
        self.corporate_nominal_spread = corporate_nominal_spread

        super().__init__()

        self.exp_spread = exp(self.corporate_nominal_spread)

        self.interest_rate = 'corporate'

    def discount_rate(self, t):

        nominal_discount: cython.double
        nominal_discount = self.nominal_bonds.discount_rate(t)
        return nominal_discount * self.exp_spread

class BondsMeasuredInNominalTerms(Bonds):

    def __init__(self, bonds, inflation):

        self.bonds = bonds
        self.inflation = inflation
        self.time_period = self.bonds.time_period

        super(Bonds, self).__init__()

        self.yield_curve = YieldCurveSum(bonds.yield_curve, inflation.yield_curve)

    def reset(self):

        self.bonds.reset()
        self.inflation.reset()

    def _short_interest_rate(self, next = False):

        return self.bonds._short_interest_rate(next) + self.inflation._short_interest_rate(next)

    def _yield(self, t):

        return self.bonds._yield(t) + self.inflation._yield(t)

    def sample(self, duration):

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

@cython.cclass
class BondsSet:

    def __init__(self, need_real = True, need_nominal = True, need_inflation = True, need_corporate = True,
        fixed_real_bonds_rate = -1, fixed_nominal_bonds_rate = -1,
        real_bonds_adjust = 0, inflation_adjust = 0, nominal_bonds_adjust = 0, corporate_nominal_spread = 0,
        static_bonds = False, date_str = '2020-12-31', date_str_low = '2018-01-01',
        real_r0_type = 'current', real_short_rate = -1, real_standard_error = 0,
        inflation_r0_type = 'current', inflation_short_rate = -1, inflation_standard_error = 0,
        time_period = 1):
        '''Create a BondsSet.

            fixed_real_bonds_rate and fixed_nominal_bonds_rate:

                If not -1 use for a constant yield curve. Does not
                supress random Hull-White temporal variability.

            real_bonds_adjust, inflation_adjust, and
            nominal_bonds_adjust, corporate_nominal_spread:

                Adjustments to apply across the yield curve.

            static_bonds

                Supress random Hull-White temporal variability.

            date_str and date_str_low:

                Last and first date to use in construcing the typical
                yield curve to use.

        real_r0_type, real_short_rate, real_standard_error,
        inflation_r0_type, inflation_short_rate,
        inflation_standard_error:

               r0_type, r0, and standard_error parameters for real and
               inflation Bonds objects.

        Returns a BondsSet object having attributes "real", "nominal",
        "corporate", and "inflation" representing a bond and inflation
        model. They are each either None if they are not needed and
        have not been computed or provide the following methods
        (except for "corporate" which only provides discount_rate()):

            reset()

                Reset to the initial state.

            step()

                Advance by time time_period.

            discount_rate(t)

                Return the 1 + the annualized spot rate over term t
                years for bonds of the appropriate type.

            sample(duration)

                Returns the time_period multipicative real return
                (change in value) for zero coupon bonds of the
                appropriate type having an initial duration duration
                years. May be called repeatedly with different values
                for duration. Calling with the same value will return
                the same result, unless step() is also called.

            observe()

                Returns current short real interest rate or short
                inflation rate as appropriate. For nominal bonds zero
                is returned.

        The nominal_bonds model need to be kept in sync with the real
        bonds and inflation models. Calling reset() or step() on
        nominal_bonds takes care of this by calling the corresponding
        routines on both real bonds and inflation. They should not
        also be called separately.

        Inflation represents the nominal value of a bond that will
        earn interest at the rate of inflation. inflation defines two
        additional methods:

            inflation()

                Returns the inflation rate factor to be experienced
                over the the next time period of length time_period.

            inflation_long_run_expectation():

                Returns the long run annual inflation expectation
                factor.

        '''

        self.time_period = time_period

        if need_corporate:
            need_nominal = True
        if need_nominal:
            need_inflation = True
        if need_inflation:
            need_real = True

        if need_real:
            if fixed_real_bonds_rate != -1:
                adjust = (1 + fixed_real_bonds_rate) * (1 + real_bonds_adjust) - 1
                yield_curve = YieldCurve('fixed', '2017-12-31', adjust = adjust)
            else:
                yield_curve = YieldCurve('real', date_str, date_str_low = date_str_low, adjust = real_bonds_adjust, permit_stale_days = 2)
            self.real = RealBonds(yield_curve = yield_curve, static_bonds = static_bonds, r0_type = real_r0_type, r0 = real_short_rate,
                standard_error = real_standard_error, time_period = time_period)
        else:
            self.real = None

        if need_inflation:
            if fixed_nominal_bonds_rate != -1:
                adjust = (1 + fixed_nominal_bonds_rate) * (1 + real_bonds_adjust) - 1
                nominal_yield_curve = YieldCurve('fixed', '2017-12-31', adjust = adjust)
            else:
                nominal_yield_curve = YieldCurve('nominal', date_str, date_str_low = date_str_low, adjust = real_bonds_adjust, permit_stale_days = 2)
            inflation_risk_premium = - log(1 + inflation_adjust)
            self.inflation = Inflation(self.real, nominal_yield_curve = nominal_yield_curve, inflation_risk_premium = inflation_risk_premium,
                r0_type = inflation_r0_type, r0 = inflation_short_rate,
                standard_error = inflation_standard_error, static_bonds = static_bonds, time_period = time_period)
        else:
            self.inflation = None

        if need_nominal:
            real_bonds_adjust = log(1 + real_bonds_adjust)
            adjust = log(1 + nominal_bonds_adjust)
            self.nominal = NominalBonds(self.real, self.inflation, real_bonds_adjust = real_bonds_adjust, nominal_bonds_adjust = adjust, time_period = time_period)
        else:
            self.nominal = None

        if need_corporate:
            corporate_nominal_spread = (1 + corporate_nominal_spread) / (1 + nominal_bonds_adjust) - 1
            self.corporate = CorporateBonds(self.nominal, corporate_nominal_spread)
        else:
            self.corporate = None

if __name__ == '__main__':

    seed(0)
    np.random.seed(0)

    bonds = BondsSet()
    modeled_inflation = Inflation(bonds.real, nominal_yield_curve = bonds.nominal.yield_curve, model_bond_volatility = False)
    nominal_real_bonds = BondsMeasuredInNominalTerms(bonds.real, bonds.inflation)
    nominal_nominal_bonds = BondsMeasuredInNominalTerms(bonds.nominal, bonds.inflation)

    print('Real bonds:')
    print()
    bonds.real._report()

    print()

    print('Inflation (as used to provide inflation volatility):')
    print()
    modeled_inflation._report()

    print()

    print('Inflation rates:')
    print()
    print('period mean_inflation_rates standard_deviation_inflation_rates')
    bonds.nominal.reset()
    inflation = []
    for _ in range(100000):
        inflation.append(log(bonds.inflation.inflation()))
        bonds.nominal.step()
    durations = (1, 2, 5, 7, 10, 15, 20, 30)
    for duration in durations:
        block_length = round(duration / bonds.time_period)
        infl = tuple(mean(inflation[i:i + block_length]) for i in range(0, len(inflation) - block_length + 1, block_length))
        print(duration, mean(infl), stdev(infl))

    print()

    print('Inflation (as used to provide nominal bond volatility):')
    print()
    bonds.inflation._report()

    print()

    print('Nominal bonds (in real terms):')
    print()
    bonds.nominal._report()

    print()

    print('Real bonds (in nominal terms):')
    print()
    nominal_real_bonds._report()

    print()

    print('Nominal bonds (in nominal terms):')
    print()
    nominal_nominal_bonds._report()
