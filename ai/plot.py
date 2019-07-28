#!/usr/bin/env python3

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
from math import sin, cos, pi
from os import environ

def bar(fname, names, values, colors, *, barwidth = 130, height = 400, font_size = 20):

    assert all(value >= 0 for value in values)
    maximum = max(values)
    if maximum == 0:
        maximum = 1

    padding = barwidth / 10
    width = len(names) * barwidth + 2 * padding
    label_height = (max(len(name.split(' ')) for name in names) + 0.5) * font_size
    s = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="{x_origin} {y_origin} {width} {height}">
'''.format(x_origin = - padding, y_origin = 0.0, width = width, height = height)
    x = 0
    for name, value, color in zip(names, values, colors):
        barheight = max(value / maximum * (height - label_height), 1.0)
        y = height - barheight - label_height
        s += '''<rect x="{x}" y="{y}" width="{barwidth}" height="{barheight}" fill="{color}" stroke="black" stroke-width="1"/>
'''.format(x = x, y = y, barwidth = barwidth, barheight = barheight, color = color)
        x += barwidth / 2
        y = height - label_height + font_size
        for n in name.split(' '):
            s += '''<text x="{x}" y="{y}" text-anchor="middle" font-size="{font_size}">{n}</text>
'''.format(x = x, y = y, font_size = font_size, n = n)
            y += font_size
        x += barwidth / 2
    s += '</svg>\n'
    with open(fname, 'w') as f:
        f.write(s)

def pie(fname, names, values, colors, *, r = 100, font_size = 16, font_width = 10, de_minus = 0.005):

    assert all(value >= 0 for value in values)
    raw_tot = sum(values)
    vals = tuple(value for value in values if value / raw_tot > de_minus)
    tot = sum(vals)
    assert tot > 0
    count = len(vals)

    half_width = r * 1.05 + font_width * max(len(name) for name in names)
    half_height = r * 1.05 + font_size
    s = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="{x_origin} {y_origin} {width} {height}">
'''.format(x_origin = - half_width, y_origin = - half_height, width = 2 * half_width, height = 2 * half_height)
    x_prev = 0
    y_prev = - r
    c = tot / 4
    for name, value, color in zip(names, values, colors):
        if value / raw_tot <= de_minus:
            continue
        c += value
        x = cos(c / tot * 2 * pi) * r
        y = - sin(c / tot * 2 * pi) * r
        if count > 1:
            large_arc = value / tot > 0.5
            s += '    <path d="M 0, 0 l {x}, {y} A {r}, {r} 0 {large_arc}, 1 {x_prev}, {y_prev} z"'.format(
                r = r, x = x, y = y, x_prev = x_prev, y_prev = y_prev, large_arc = int(large_arc)
            )
        else:
            s += '    <circle cx="0" cy="0" r="{r}"'.format(r = r)
        s += ' fill="{color}" stroke="black" stroke-width="1" stroke-linejoin="round"/>\n'.format(color = color)
        x_prev = x
        y_prev = y
        l = c - value / 2
        x = cos(l / tot * 2 * pi) * r * 1.05
        y = - sin(l / tot * 2 * pi) * r * 1.05
        align = 'start' if x >= 0 else 'end'
        if y > 0:
            y += font_size
        s += '    <text text-anchor="{align}" font-size="20" x="{x}" y="{y}">{name}</text>\n'.format(align = align, x = x, y = y, name = name)
    s += '</svg>\n'
    with open(fname, 'w') as f:
        f.write(s)

def main():

    prefix = environ['AIPLANNER_FILE_PREFIX']

    with open(prefix + '.json') as f:
        interp = loads(f.read())

    asset_classes = interp['asset_classes']
    asset_classes = [ac.replace('_', ' ') for ac in asset_classes]
    num_bonds = sum(1 for ac in asset_classes if ac.endswith('bonds'))
    if num_bonds == 1:
        asset_classes = ['bonds' if ac.endswith('bonds') else ac for ac in asset_classes]
    asset_allocation = interp['asset_allocation']

    pv_preretirement = interp['pv_preretirement_income']
    gi = interp['pv_retired_income']
    taxes = interp['pv_future_taxes']
    p = interp['portfolio_wealth']
    real_spias = interp['real_spias_purchase']
    nominal_spias = interp['nominal_spias_purchase']
    spias = 0
    if real_spias:
        spias += real_spias
    if nominal_spias:
        spias += nominal_spias
    wealth_classes = list(asset_classes)
    wealth_allocation = list(aa * (p - spias) for aa in asset_allocation)
    wealth_classes.append('guaranteed income')
    wealth_allocation.append(gi)
    if real_spias != None or nominal_spias != None:
        wealth_classes.append('new income annuities')
        wealth_allocation.append(spias)
    wealth_classes.append('pre-retirement contributions')
    wealth_allocation.append(pv_preretirement)
    wealth_classes.append('future taxes')
    wealth_allocation.append(taxes)
    wealth_allocation = list(max(w, 0) for w in wealth_allocation)

    colors = ['red', 'green', 'blue', 'yellow', 'orange', 'magenta', 'olive', 'indigo']

    bar(prefix + '-wealth.svg', wealth_classes, wealth_allocation, colors)
    pie(prefix + '-asset_allocation.svg', asset_classes, asset_allocation, colors)

if __name__ == '__main__':
    main()
