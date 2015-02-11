#!/usr/bin/R --vanilla --slave -f

# Computes asset allocation and consumption for a CRRA utility function.
#
# See: http://en.wikipedia.org/wiki/Merton%27s_portfolio_problem
# See: Continuous Time Finance by R. Merton

# Coefficient of relative risk aversion.
gamma = 4

# Subjective discount rate.
rho = 0.0

# Portfolio size.
W = 500000

# Social security and other guaranteed income.
I = 15000

# Remaining life expectancy.
# See: https://www.aacalc.com/calculators/le
# Chosen value is for a male age 65.
e = 17.6

# Factor to multiply life expectancy by because we need to handle a range of life expectancies, not a single outcome as Merton does; prepare for worse cases.
ef = 1.5 # Determined empirically to give good results over a range of scenarios.

# Arithmetic returns vector.
alpha = c(0.065, 0.010)

# The returns covariance matrix.
sigma = matrix(
    c(0.04, 0.0, 0.0, 0.01),
    nrow=2,
    ncol=2,
    byrow=TRUE
)

# Merton allows risk free and borrowing.
# By a process of trial and error I find the risk free rate for which stock plus bonds sums to 1.

r_lo = -1
r_hi = 1

while (abs(r_hi - r_lo) > 1e-9) {

    r = (r_lo + r_hi) / 2

    alpha_r = alpha - r
    wo = solve(sigma) %*% alpha_r / gamma

    if (sum(wo) > 1)
        r_lo <- r
    else
        r_hi <- r
}

# Proof that it summed to one:
stopifnot(abs(sum(wo) - 1) < 0.001)

nu = (rho - (1 - gamma) * (t(alpha_r) %*% solve(sigma) %*% alpha_r / (2 * gamma) + r)) / gamma

# Portfolio consumption amount.
if (nu == 0) {
    C = W / (e * ef)
} else {
    C = nu * (W + I * e * ef) / (1 - exp(- nu * e * ef)) - I
}

'The overall asset allocations:'
# Age and portfolio size invariant.
wo
'The approximate investment portfolio asset allocations:'
# Approximate because we really need compute the NPV of future income.
min(wo[1] + wo[1] * I * e / W, 1)
max(wo[2] - wo[1] * I * e / W, 0)
'The approximate annual portfolio withdrawal amount:'
# Approximate because the exact solution depends on a fixed life expectancy and need NPV of future income when computing C.
C
"Merton's nu parameter:"
nu
