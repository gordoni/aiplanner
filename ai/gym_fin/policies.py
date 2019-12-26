# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from json import loads

from ai.gym_fin.asset_allocation import AssetAllocation

class Policy:

    def __init__(self, env):

        self.env = env

    def _pmt(self, rate, nper, pv):

        try:
            return pv * rate * (1 + rate) ** (nper - 1) / ((1 + rate) ** nper - 1)
        except ZeroDivisionError:
            return pv / nper

    def _bonds_type(self):

        assert int(self.env.params.real_bonds) + int(self.env.params.nominal_bonds) + int(self.env.params.iid_bonds) + int(self.env.params.bills) == 1

        if self.env.params.real_bonds:
            return 'real_bonds'
        elif self.env.params.nominal_bonds:
            return 'nominal_bonds'
        elif self.env.params.iid_bonds:
            return 'iid_bonds'
        elif self.env.params.bills:
            return 'bills'
        else:
            assert False

    def policy(self, action):

        if action is not None:
            consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration = action

        if self.env.params.consume_policy == 'constant':

            consume_fraction = self.env.params.consume_initial / self.env.p_plus_income

        elif self.env.params.consume_policy == 'percent_rule':

            if self.env.age < self.env.age_retirement:
                consume_fraction = 0
            else:
                if self.env.age < self.env.age_retirement + self.env.params.time_period:
                    self.consume_rate_initial = self.env.params.consume_policy_fraction * self.env.p_wealth
                consume_fraction = (self.env.net_gi + self.consume_rate_initial) / self.env.p_plus_income

        elif self.env.params.consume_policy == 'guyton_rule2':

            assert self.env.age >= self.env.age_retirement

            if self.env.episode_length == 0:
                consume = self.env.params.consume_initial - self.env.net_gi
            elif self.env.prev_ret * self.env.prev_inflation >= 1:
                consume = self.consume_prev
            else:
                consume = self.consume_prev / self.env.prev_inflation
            self.consume_prev = consume
            consume += self.env.net_gi
            consume_fraction = consume / self.env.p_plus_income

        elif self.env.params.consume_policy == 'guyton_klinger':

            assert self.env.age >= self.env.age_retirement

            if self.env.params.consume_policy_life_expectancy == None:
                life_expectancy = self.env.life_expectancy_both[self.env.episode_length] + self.env.life_expectancy_one[self.env.episode_length]
            else:
                life_expectancy = self.env.params.consume_policy_life_expectancy - self.env.episode_length * self.env.params.time_period
            if self.env.episode_length == 0:
                consume = self.env.params.consume_initial - self.env.net_gi
                self.consume_rate_initial = consume / self.env.p_wealth
            else:
                consume = self.consume_prev
                if consume < 0.8 * self.consume_rate_initial * self.env.p_wealth:
                    consume *= 1.1
                if consume > 1.2 * self.consume_rate_initial * self.env.p_wealth and life_expectancy > 15:
                    consume *= 0.9
                if self.env.prev_ret * self.env.prev_inflation < 1 and consume > self.consume_rate_initial * self.env.p_wealth:
                    consume /= self.env.prev_inflation
            self.consume_prev = consume
            consume += self.env.net_gi
            consume_fraction = consume / self.env.p_plus_income

        elif self.env.params.consume_policy == 'target_percentage':

            assert self.env.age >= self.env.age_retirement

            if self.env.params.consume_policy_life_expectancy == None:
                life_expectancy = self.env.life_expectancy_both[self.env.episode_length] + self.env.life_expectancy_one[self.env.episode_length]
            else:
                life_expectancy = max(1, self.env.params.consume_policy_life_expectancy - self.env.episode_length * self.env.params.time_period)
            if self.env.episode_length == 0:
                self.life_expectancy_initial = life_expectancy
                self.p_initial = self.env.p_wealth
                consume = self.env.params.consume_initial - self.env.net_gi
            elif self._pmt(self.env.params.consume_policy_return, life_expectancy, self.env.p_wealth) >= \
                self._pmt(self.env.params.consume_policy_return, self.life_expectancy_initial, self.p_initial):
                consume = self.consume_prev
            else:
                consume = self.consume_prev / self.env.prev_inflation
            self.consume_prev = consume
            consume += self.env.net_gi
            consume_fraction = consume / self.env.p_plus_income

        elif self.env.params.consume_policy == 'extended_rmd':

            extended_rmd_table = {
                50: 46.5, # IRS Pub. 590B Table II diagonal.
                51: 45.5,
                52: 44.6,
                53: 43.6,
                54: 42.6,
                55: 41.6,
                56: 40.7,
                57: 39.7,
                58: 38.7,
                59: 37.8,
                60: 36.8,
                61: 35.8,
                62: 34.9,
                63: 33.9,
                64: 33.0,
                65: 32.0,
                66: 31.1,
                67: 30.2,
                68: 29.2,
                69: 28.3,
                70: 27.4, # IRS Pub. 590B Table III.
                71: 26.5,
                72: 25.6,
                73: 24.7,
                74: 23.8,
                75: 22.9,
                76: 22.0,
                77: 21.2,
                78: 20.3,
                79: 19.5,
                80: 18.7,
                81: 17.9,
                82: 17.1,
                83: 16.3,
                84: 15.5,
                85: 14.8,
                86: 14.1,
                87: 13.4,
                88: 12.7,
                89: 12.0,
                90: 11.4,
                91: 10.8,
                92: 10.2,
                93: 9.6,
                94: 9.1,
                95: 8.6,
                96: 8.1,
                97: 7.6,
                98: 7.1,
                99: 6.7,
                100: 6.3,
                101: 5.9,
                102: 5.5,
                103: 5.2,
                104: 4.9,
                105: 4.5,
                106: 4.2,
                107: 3.9,
                108: 3.7,
                109: 3.4,
                110: 3.1,
                111: 2.9,
                112: 2.6,
                113: 2.4,
                114: 2.1,
                115: 1.9,
            }

            assert self.env.alive_single[self.env.episode_length] != None or self.env.age == self.env.age2
            if self.env.age < self.env.age_retirement:
                consume = 0
            else:
                rmd_period = extended_rmd_table[min(int(self.env.age), max(extended_rmd_table.keys()))]
                consume = self.env.net_gi + self.env.p_wealth / rmd_period * self.env.params.time_period
            consume_fraction = consume / self.env.p_plus_income

        elif self.env.params.consume_policy == 'pmt':

            if self.env.params.consume_policy_life_expectancy == None:
                life_expectancy = self.env.life_expectancy_both[self.env.episode_length] + self.env.life_expectancy_one[self.env.episode_length]
            else:
                life_expectancy = self.env.params.consume_policy_life_expectancy - self.env.episode_length * self.env.params.time_period
            life_expectancy = max(1, life_expectancy)
            consume = self.env.net_gi + self._pmt(self.env.params.consume_policy_return, life_expectancy, self.env.p_wealth)
            consume_fraction = consume / self.env.p_plus_income

        consume_fraction = max(1e-6, min(consume_fraction, self.env.params.consume_policy_fraction_max / self.env.params.time_period))

        if self.env.params.annuitization_policy in ('age_real', 'age_nominal'):

            if self.env.episode_length == 0:
                self.anuitized = False

            if self.env.couple:
                min_age = min(self.env.age, self.env.age2)
                max_age = max(self.env.age, self.env.age2)
            else:
                min_age = max_age = self.env.age2 if self.env.only_alive2 else self.env.age

            spias_allowed = (self.env.params.couple_spias or not self.env.couple) and \
                min_age >= self.env.params.spias_permitted_from_age and max_age <= self.env.params.spias_permitted_to_age
            spias = spias_allowed and min_age >= self.env.params.annuitization_policy_age
            real_spias_fraction = self.env.params.annuitization_policy_annuitization_fraction if spias and self.env.params.annuitization_policy == 'age_real' else 0
            nominal_spias_fraction = \
                self.env.params.annuitization_policy_annuitization_fraction if spias and self.env.params.annuitization_policy == 'age_nominal' else 0

            if real_spias_fraction or nominal_spias_fraction:
                self.anuitized = True

        elif self.env.params.annuitization_policy == 'none':

            real_spias_fraction = 0
            nominal_spias_fraction = 0

        if self.env.params.asset_allocation_policy == 'age-in-bonds':

            bonds = max(self.env.age / 100, 1)
            asset_allocation = AssetAllocation(**{'stocks': 1 - bonds, self._bonds_type(): bonds})

        elif self.env.params.asset_allocation_policy == 'glide-path':

            t = self.env.age - self.env.age_retirement
            glide_path = loads(self.env.params.asset_allocation_glide_path)
            t0, stocks0 = glide_path[0]
            for t1, stocks1 in glide_path:
                if t < t1:
                    break
                t0, stocks0 = t1, stocks1
            if t0 == t1:
                stocks = stocks0
            else:
                t = min(max(t0, t), t1)
                stocks = (stocks0 * (t1 - t) + stocks1 * (t - t0)) / (t1 - t0)
            asset_allocation = AssetAllocation(**{'stocks': stocks, self._bonds_type(): 1 - stocks})

        elif self.env.params.asset_allocation_policy != 'rl':

            asset_allocation = loads(self.env.params.asset_allocation_policy)
            asset_allocation = AssetAllocation(**asset_allocation)

        if self.env.params.asset_allocation_annuitized_policy != 'asset_allocation_policy' and self.anuitized:

            asset_allocation = loads(self.env.params.asset_allocation_annuitized_policy)
            asset_allocation = AssetAllocation(**asset_allocation)

        if self.env.params.real_bonds:
            if self.env.params.real_bonds_duration != None:
                real_bonds_duration = self.env.params.real_bonds_duration
        else:
            real_bonds_duration = None

        if self.env.params.nominal_bonds:
            if self.env.params.nominal_bonds_duration != None:
                nominal_bonds_duration = self.env.params.nominal_bonds_duration
        else:
            nominal_bonds_duration = None

        return consume_fraction, real_spias_fraction, nominal_spias_fraction, asset_allocation, real_bonds_duration, nominal_bonds_duration
