# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2018 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

# 2018 Nominal tax brackets and rates. Amounts treated as real on the assumption that over the long run brackets will be adjusted for inflation.
# Assume take standard deduction.
# Social Security treated as fully taxable.
# Income from SPIA treated as fully taxable.
# Net Investment Income Tax (NIIT) not considered.
# Alternative minimum tax not considered.

federal_standard_deduction_single = 12000
federal_standard_deduction_joint = 24000

federal_table_single = (
    (9525, 0.1),
    (38700, 0.12),
    (82500, 0.22),
    (157500, 0.24),
    (200000, 0.32),
    (500000, 0.35),
    (float('inf'), 0.37),
)

federal_table_joint = (
    (19050, 0.1),
    (77400, 0.12),
    (165000, 0.22),
    (315000, 0.24),
    (400000, 0.32),
    (600000, 0.35),
    (float('inf'), 0.37),
)

federal_long_term_gains_single = (
    (38600, 0),
    (425800, 0.15),
    (float('inf'), 0.2),
)

federal_long_term_gains_joint = (
    (77200, 0),
    (479000, 0.15),
    (float('inf'), 0.2),
)

federal_max_capital_loss = 3000

class Taxes(object):

    def __init__(self, env, taxable_assets, p_taxable_stocks_basis_fraction):

        self.env = env
        self.value = dict(taxable_assets.aa)
        self.basis = {ac: p_taxable_stocks_basis_fraction * value if ac == 'stocks' else value for ac, value in taxable_assets.aa.items()}
        self.cg_carry = 0
        self.capital_gains = 0
        self.qualified_dividends = 0
        self.non_qualified_dividends = 0
        
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

    def tax_table(self, table, income, start):

        tax = 0
        income += start
        for limit, rate in table:
            limit *= self.env.params.time_period
            tax += max(min(income, limit) - start, 0) * rate
            if income < limit:
                break
            start = max(start, limit)

        return tax

    def tax(self, regular_income, single, p_taxable, inflation):

        assert regular_income >= 0

        regular_income += self.non_qualified_dividends
        capital_gains = self.cg_carry + self.capital_gains + self.qualified_dividends
        current_capital_gains = max(capital_gains, - min(federal_max_capital_loss, regular_income))
        self.cg_carry = capital_gains - current_capital_gains
        regular_income += min(current_capital_gains, 0)
        capital_gains = max(current_capital_gains, 0)
        for ac in self.basis:
            self.basis[ac] /= inflation
        self.cg_carry /= inflation

        taxable_regular_income = regular_income - (federal_standard_deduction_single if single else federal_standard_deduction_joint)
        taxable_capital_gains = capital_gains + min(taxable_regular_income, 0)
        taxable_regular_income = max(taxable_regular_income, 0)
        taxable_capital_gains = max(taxable_capital_gains, 0)

        regular_tax = self.tax_table(federal_table_single if single else federal_table_joint, taxable_regular_income, 0)
        capital_gains_tax = self.tax_table(federal_long_term_gains_single if single else federal_long_term_gains_joint, taxable_capital_gains, taxable_regular_income)
        state_tax = (taxable_regular_income + taxable_capital_gains) * self.env.params.tax_state

        self.capital_gains = 0
        self.qualified_dividends = 0
        self.non_qualified_dividends = 0

        if self.env.params.tax:
            tax = regular_tax + capital_gains_tax + state_tax
        else:
            tax = 0

        return tax

    def observe(self):

        if self.env.params.tax:
            basis = sum(self.basis.values())
            cg_carry = self.cg_carry
        else:
            basis = 0
            cg_carry = 0

        return basis, cg_carry
