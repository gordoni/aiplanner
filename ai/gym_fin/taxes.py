# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018-2020 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

# Nominal tax brackets and rates. Amounts treated as real since brackets get adjusted for inflation.
# Assume take standard deduction.
# Alternative minimum tax not considered.
# Average-cost cost basis method used for asset class sales.

class Taxes(object):

    def __init__(self, params, taxable_assets, taxable_basis, cg_init):

        self.params = params
        self.value = dict(taxable_assets.aa)
        self.basis = dict(taxable_basis.aa)
        self.cpi = 1
        self.cg_carry = 0
        self.capital_gains = cg_init
        self.qualified_dividends = 0
        self.non_qualified_dividends = 0
        self.charitable_contributions_carry = 0

        if self.params.tax_table_year == '2018':

            self.federal_standard_deduction_single = 12000
            self.federal_standard_deduction_joint = 24000
            # Ignore small increase in standard deduction for age 65+.

            self.federal_table_single = (
                (9525, 0.1),
                (38700, 0.12),
                (82500, 0.22),
                (157500, 0.24),
                (200000, 0.32),
                (500000, 0.35),
                (float('inf'), 0.37),
            )

            self.federal_table_joint = (
                (19050, 0.1),
                (77400, 0.12),
                (165000, 0.22),
                (315000, 0.24),
                (400000, 0.32),
                (600000, 0.35),
                (float('inf'), 0.37),
            )

            self.federal_long_term_gains_single = (
                (38600, 0),
                (425800, 0.15),
                (float('inf'), 0.2),
            )

            self.federal_long_term_gains_joint = (
                (77200, 0),
                (479000, 0.15),
                (float('inf'), 0.2),
            )

            self.contribution_limit_401k = 18500
            self.contribution_limit_401k_catchup = 24500
            self.contribution_limit_ira = 5500
            self.contribution_limit_ira_catchup = 6500

        elif self.params.tax_table_year == '2019':

            self.federal_standard_deduction_single = 12200
            self.federal_standard_deduction_joint = 24400
            # Ignore small increase in standard deduction for age 65+.

            self.federal_table_single = (
                (9700, 0.1),
                (39475, 0.12),
                (84200, 0.22),
                (160725, 0.24),
                (204100, 0.32),
                (510300, 0.35),
                (float('inf'), 0.37),
            )

            self.federal_table_joint = (
                (19400, 0.1),
                (78950, 0.12),
                (168400, 0.22),
                (321450, 0.24),
                (408200, 0.32),
                (612350, 0.35),
                (float('inf'), 0.37),
            )

            self.federal_long_term_gains_single = (
                (39375, 0),
                (434550, 0.15),
                (float('inf'), 0.2),
            )

            self.federal_long_term_gains_joint = (
                (78750, 0),
                (488850, 0.15),
                (float('inf'), 0.2),
            )

            self.contribution_limit_401k = 19000
            self.contribution_limit_401k_catchup = 25000
            self.contribution_limit_ira = 6000
            self.contribution_limit_ira_catchup = 7000

        elif self.params.tax_table_year == '2020' or self.params.tax_table_year == None:

            self.federal_standard_deduction_single = 12400
            self.federal_standard_deduction_joint = 24800
            # Ignore small increase in standard deduction for age 65+.

            self.federal_table_single = (
                (9875, 0.1),
                (40125, 0.12),
                (85525, 0.22),
                (163300, 0.24),
                (207350, 0.32),
                (518400, 0.35),
                (float('inf'), 0.37),
            )

            self.federal_table_joint = (
                (19750, 0.1),
                (80250, 0.12),
                (171050, 0.22),
                (326600, 0.24),
                (414700, 0.32),
                (622050, 0.35),
                (float('inf'), 0.37),
            )

            self.federal_long_term_gains_single = (
                (40000, 0),
                (441450, 0.15),
                (float('inf'), 0.2),
            )

            self.federal_long_term_gains_joint = (
                (80000, 0),
                (496600, 0.15),
                (float('inf'), 0.2),
            )

            self.contribution_limit_401k = 19500
            self.contribution_limit_401k_catchup = 26000
            self.contribution_limit_ira = 6000
            self.contribution_limit_ira_catchup = 7000

        else:
            assert False, 'No tax table for: ' + self.params.tax_table_year

        self.federal_max_capital_loss = 3000 # Limit not inflation adjusted.

        # Social Security brackets are not inflation adjusted.
        self.ss_taxable_single = (
            (25000, 0),
            (34000, 0.5),
            (float('inf'), 0.85),
        )

        self.ss_taxable_couple = (
            (32000, 0),
            (44000, 0.5),
            (float('inf'), 0.85),
        )

        # Net Investment income tax is not inflation adjusted.
        self.niit_threshold_single = 200000
        self.niit_threshold_couple = 250000
        self.niit_rate = 0.038

        self.charitable_deduction_limit = 0.5

    def buy_sell(self, ac, amount, new_value, ret, dividend_yield, qualified):

        if amount > 0:
            self.basis[ac] += amount
        elif amount < 0:
            amount = - amount
            self.capital_gains += amount * (self.value[ac] - self.basis[ac]) / self.value[ac]
            self.basis[ac] *= 1 - amount / self.value[ac]
        dividend = new_value * dividend_yield
        self.qualified_dividends += dividend * qualified
        self.non_qualified_dividends += dividend * (1 - qualified)
        self.basis[ac] += dividend
        self.value[ac] = new_value

    def unrealized_gains(self):

        return sum(self.value.values()) - sum(self.basis.values())

    def tax_table(self, table, income, start):

        tax = 0
        income += start
        for limit, rate in table:
            limit *= self.params.time_period
            tax += max(min(income, limit) - start, 0) * rate
            if income < limit:
                break
            start = max(start, limit)

        return tax

    def marginal_rate(self, table, income):

        for limit, rate in table:
            limit *= self.params.time_period
            if income < limit:
                break

        return rate

    def calculate_taxes(self, regular_income, social_security, capital_gains, nii, charitable_contributions, single):

        if not self.params.tax:
            return 0, 0

        if social_security != 0:
            regular_income -= social_security
            relevant_income = regular_income + capital_gains + social_security / 2
            ss_table = self.ss_taxable_single if single else self.ss_taxable_couple
            social_security_taxable = min(self.tax_table(ss_table, relevant_income * self.cpi, 0) / self.cpi,
                self.marginal_rate(ss_table, relevant_income * self.cpi) * social_security)
            regular_income += social_security_taxable

        itemized_deduction = min(charitable_contributions, self.charitable_deduction_limit * (regular_income + capital_gains))
        deduction = max(itemized_deduction, self.federal_standard_deduction_single if single else self.federal_standard_deduction_joint)
        self.remaining_charitable_contributions = max(0, charitable_contributions - deduction) # Should limit carry forward to 5 years.
        taxable_regular_income = regular_income - deduction
        taxable_capital_gains = capital_gains + min(taxable_regular_income, 0)
        taxable_regular_income = max(taxable_regular_income, 0)
        taxable_capital_gains = max(taxable_capital_gains, 0)

        nii_taxable = min(nii, max(regular_income - (self.niit_threshold_single if single else self.niit_threshold_couple) / self.cpi, 0))

        regular_tax = self.tax_table(self.federal_table_single if single else self.federal_table_joint, taxable_regular_income, 0) \
            if taxable_regular_income != 0 else 0
        regular_tax += nii_taxable * self.niit_rate
        capital_gains_tax = self.tax_table(self.federal_long_term_gains_single if single else self.federal_long_term_gains_joint,
            taxable_capital_gains, taxable_regular_income) \
            if taxable_capital_gains != 0 else 0

        regular_tax += self.params.tax_fixed
        regular_tax += taxable_regular_income * self.params.tax_state
        capital_gains_tax += taxable_capital_gains * self.params.tax_state

        return regular_tax, capital_gains_tax

    def tax(self, regular_income, social_security, charitable_contributions, single, inflation):

        assert regular_income >= social_security

        if self.params.tax:

            regular_income += self.non_qualified_dividends
            capital_gains = self.cg_carry + self.capital_gains + self.qualified_dividends
            current_capital_gains = max(capital_gains, - min(self.federal_max_capital_loss / self.cpi, regular_income))
            self.cg_carry = capital_gains - current_capital_gains
            regular_income += min(current_capital_gains, 0)
            capital_gains = max(current_capital_gains, 0)
            nii = max(self.capital_gains + self.qualified_dividends + self.non_qualified_dividends, 0)
            charitable_contributions += self.charitable_contributions_carry

            regular_tax, capital_gains_tax = self.calculate_taxes(regular_income, social_security, capital_gains, nii, charitable_contributions, single)
            self.charitable_contributions_carry = self.remaining_charitable_contributions

            total_tax = regular_tax + capital_gains_tax

        else:

            total_tax = 0

        self.capital_gains = 0
        self.qualified_dividends = 0
        self.non_qualified_dividends = 0

        for ac in self.basis:
            self.basis[ac] /= inflation
        self.cg_carry /= inflation

        if not self.params.tax_inflation_adjust_all:
            self.cpi *= inflation

        return total_tax

    def observe(self):

        if self.params.tax:
            basis = sum(self.basis.values())
            cg_carry = self.cg_carry + self.capital_gains # Add in capital_gains to observe effect of cg_init.
        else:
            basis = 0
            cg_carry = 0

        return basis, cg_carry

    def contribution_limit(self, annual_income, age, have_401k, time_period):

        if have_401k:
            limit = self.contribution_limit_401k if age < 50 else self.contribution_limit_401k_catchup
        else:
            limit = self.contribution_limit_ira if age < 50 else self.contribution_limit_ira_catchup
        annual_contribution = min(annual_income, limit)

        return annual_contribution * time_period
