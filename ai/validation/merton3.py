#!/usr/bin/env python3

# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from math import log, sqrt

from numpy import array
from numpy.linalg import inv, LinAlgError


def mu_sigma(m, vol):
    
    mu = log(m / sqrt(1 + (vol / m) ** 2))
    sigma = sqrt(log(1 + (vol / m) ** 2))

    return mu, sigma

def solve_merton(gamma, sigma_matrix, alpha, r):

    w = inv(sigma_matrix).dot(array(alpha) - r) / gamma
    return tuple(float(wi) for wi in w) # De-numpyfy.

def solve_merton_no_r(gamma, sigma_matrix, alpha):

    r_lo = -0.1
    r_hi = 0.1
    for _ in range(50):
        r = (r_lo + r_hi) / 2
        w = solve_merton(gamma, sigma_matrix, alpha, r)
        if sum(w) > 1:
            r_lo = r
        else:
            r_hi = r

    return w

if __name__ == '__main__':

    stocks_mu, stocks_sigma = mu_sigma(1.065, 0.174)
    bonds = {
        1: (1.011, 0.023),
        2: (1.007, 0.028),
        5: (1.009, 0.057),
        15: (1.013, 0.112),
    }

    for duration in (1, 2, 5, 15):

        for gamma in (1, 1.5, 3, 6):

            bonds_mu, bonds_sigma = mu_sigma(*bonds[duration])
            sigma_matrix = (
                (stocks_sigma ** 2, 0),
                (0, bonds_sigma ** 2),
            )
            alpha = (stocks_mu + stocks_sigma ** 2 / 2, bonds_mu + bonds_sigma ** 2 / 2)

            w = solve_merton_no_r(gamma, sigma_matrix, alpha)

            print(duration, gamma, w[0])
