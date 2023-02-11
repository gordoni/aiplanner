# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2020-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

from datetime import datetime, timedelta
from html import escape
from re import sub

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table
from reportlab.platypus.flowables import TopPadder
from svglib.svglib import svg2rlg

def generate_report(api, result_dir, results, results_dir):

    def svg(aid, name, width = 5.5 * inch, hAlign = 'CENTER'):

        img = svg2rlg((results_dir + '/' + aid + '/seed_all/aiplanner-' if aid else result_dir + '/') + name + '.svg')
        scale = width / img.minWidth()
        img.width *= scale
        img.height *= scale
        img.scale(scale, scale)
        img.hAlign = hAlign

        return img

    def dollar(x):

        try:
            return '$' + sub(r'\B(?=(\d{3})+(?!\d))', ',', str(round(x)))
        except (TypeError, ValueError):
            return 'n/a' # None or NaN.

    def aa_str(aa):

        if aa:
            asset_allocation = ''
            carry = 0
            for alloc in aa:
                if asset_allocation:
                    asset_allocation += '/'
                val = round(alloc * 100 + carry)
                asset_allocation += str(val)
                carry += alloc * 100 - val
        else:
            asset_allocation = None

        return asset_allocation

    filename = 'aiplanner.pdf'

    pagesize = letter
    pagewidth, pageheight = pagesize
    doc = SimpleDocTemplate(result_dir + '/' + filename, pagesize = pagesize,
        leftMargin = 0.5 * inch, rightMargin = 0.5 * inch, topMargin = 0.5 * inch, bottomMargin = 0.5 * inch,
    )

    customer_name = api.get('customer_name', '')
    scenario_name = api.get('scenario_name', '')
    if not customer_name and not scenario_name:
        customer_name = 'AIPlanner'

    consume_specify = api['age'] < api['age_retirement'] and api.get('consume_preretirement') is not None

    if scenario_name:
        doc.title = customer_name + ' - ' + scenario_name
    else:
        doc.title = customer_name

    styles = getSampleStyleSheet()
    styleH = styles['Heading1']
    styleN = styles['Normal']

    contents = []
    contents.append(Spacer(1, 3 * inch))
    if customer_name:
        s = '<para alignment="center">' + escape(customer_name) + '</para>'
        contents.append(Paragraph(s, styleH))
    if scenario_name:
        s = '<para alignment="center">' + escape(scenario_name) + '</para>'
        contents.append(Paragraph(s, styleH))
    # Don't want to rely on third party pytz library.
    #from pytz import timezone
    #tz = timezone('US/Eastern')
    #date = datetime.now()
    date = datetime.utcnow() - timedelta(hours = 5)
    date_str = date.strftime('%B %-d, %Y')
    s = '<para alignment="center">' + date_str + '</para>'
    contents.append(Paragraph(s, styleN))
    valid_results = tuple(result for result in results if not result['error'])
    if valid_results:
        result = valid_results[0]
        aid = result['aid']
        contents.append(PageBreak())
        s = '<para alignment="center">Life expectancy</para>'
        contents.append(Paragraph(s, styleH))
        contents.append(Spacer(1, 2 * inch))
        contents.append(Paragraph('<para alignment="center">Life expectancy</para>', styleN))
        contents.append(svg(aid, 'alive', width = 7.5 * inch))
        contents.append(PageBreak())
        s = '<para alignment="center">Consumption summary</para>'
        contents.append(Paragraph(s, styleH))
        contents.append(Spacer(1, 0.5 * inch))
        contents.append(Paragraph('<para alignment="center">' + ('Retirement consumption' if consume_specify else 'Consumption') + ' distribution</para>', styleN))
        contents.append(svg(None, 'consume-pdf', width = 7.5 * inch))
        contents.append(Spacer(1, 0.5 * inch))
        contents.append(Paragraph('<para alignment="center">Cummulative consumption distribution</para>', styleN))
        contents.append(svg(None, 'consume-cdf', width = 7.5 * inch))
    for result in sorted(results, key = lambda r: r.get('rra', 0), reverse = True):
        if not result['error']:
            aid = result['aid']
            contents.append(PageBreak())
            s = '<para alignment="center">' + ('Low' if result['rra'] < 2 else 'Moderate' if result['rra'] < 4 else 'High') + ' risk aversion</para>'
            contents.append(Paragraph(s, styleH))
            for warning in result['warnings']:
                s = '<font color="red">WARNING: ' + warning + '</font>'
                contents.append(Paragraph(s, styleN))
            content = []
            s = 'Mean consumption' + (' in retirement' if consume_specify else '') + ': ' + dollar(result['consume_mean']) + '<br/>' + \
                'Consumption uncertainty: ' + dollar(result['consume_stdev']) + '<br/>' + \
                '10% chance of' + (' retirement' if consume_specify else '') + ' consumption below: ' + dollar(result['consume10'])
            content.append(Paragraph(s, styleN))
            content.append(Spacer(1, 0.25 * inch))
            asset_classes = ''
            for ac in result['asset_classes']:
                if asset_classes:
                    asset_classes += '/'
                if ac.endswith('bonds'):
                    asset_classes += 'bonds'
                else:
                    asset_classes += ac
            asset_allocation = aa_str(result['asset_allocation'])
            asset_allocation_tax_free = aa_str(result['asset_allocation_tax_free'])
            asset_allocation_tax_deferred = aa_str(result['asset_allocation_tax_deferred'])
            asset_allocation_taxable = aa_str(result['asset_allocation_taxable'])
            s = 'Current recommended after tax consumption: ' + dollar(result['consume']) + '<br/>' + \
                'Recommended diversified ' + asset_classes + ' asset allocation: ' + asset_allocation + '<br/>'
            if asset_allocation_tax_free and (asset_allocation_tax_deferred or asset_allocation_taxable):
                s += '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tax free (Roth): ' + asset_allocation_tax_free + '<br/>'
            if asset_allocation_tax_deferred and (asset_allocation_tax_free or asset_allocation_taxable):
                s += '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tax deferred (traditional): ' + asset_allocation_tax_deferred + '<br/>'
            if asset_allocation_taxable and (asset_allocation_tax_free or asset_allocation_tax_deferred):
                s += '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Taxable: ' + asset_allocation_taxable + '<br/>'
            s += 'International diversification: optional'
            def duration(d):
                return 'short' if d <= 2 else 'intermediate' if d <= 9 else 'long'
            if result['real_bonds_duration'] is not None:
                s += '<br/>Bonds duration: ' + str(round(result['real_bonds_duration'])) + ' years (' + duration(result['real_bonds_duration']) + ' term TIPS)'
            if result['nominal_bonds_duration'] is not None:
                s += '<br/>Bonds duration: ' + str(round(result['nominal_bonds_duration'])) + ' years (' + duration(result['nominal_bonds_duration']) + \
                    ' term Treasuries)'
            if result['retirement_contribution'] is not None:
                s += '<br/>Recommended retirement plan contribution: ' + dollar(result['retirement_contribution'])
            if result['nominal_spias_purchase'] is not None:
                s += '<br/>Recommended SPIA purchase amount (' + str(round(result['nominal_spias_adjust'] * 1000) / 10) + '% annual adjustment): ' + \
                    dollar(result['nominal_spias_purchase'])
            if result['real_spias_purchase'] is not None:
                s += '<br/>Recommended inflation-indexed SPIA purchase amount: ' + dollar(result['real_spias_purchase'])
            content.append(Paragraph(s, styleN))
            content.append(Spacer(1, 0.25 * inch))
            s = '<font size="8">RRA=' + str(result['rra']) + ' certainty equivalent' + (' retirement' if consume_specify else '') + ' consuption: ' + \
                dollar(result['ce']) + '<br/>' + \
                'Standard error of measurement: ' + dollar(result['ce_stderr']) + '</font>'
            content.append(Paragraph(s, styleN))
            t = Table([
                [content, [svg(aid, 'asset_allocation', width = 2.25 * inch), Spacer(1, 0.25 * inch), svg(aid, 'wealth', width = 2.25 * inch)]]
            ], colWidths = [
                5.25 * inch, None
            ], style = [
                ['VALIGN', (0, 0), (0, 0), 'TOP'],
                ['ALIGN', (1, 0), (1, 0), 'RIGHT'],
                ['LEFTPADDING', (0, 0), (-1, -1), 0],
                ['RIGHTPADDING', (1, 0), (-1, -1), 0],
            ])
            contents.append(t)
            contents.append(Spacer(1, 1 * inch))
            contents.append(Paragraph('<para alignment="center">Consumption confidence region</para>', styleN))
            contents.append(svg(aid, 'consume-cr', width = 7.5 * inch))
            contents.append(PageBreak())
            contents.append(Paragraph('<para alignment="center">' + ('Retirement consumption' if consume_specify else 'Consumption') + ' distribution</para>',
                styleN))
            contents.append(svg(aid, 'consume-pdf'))
            contents.append(Spacer(1, 0.25 * inch))
            contents.append(Paragraph('<para alignment="center">Cummulative consumption distribution</para>', styleN))
            contents.append(svg(aid, 'consume-cdf'))
            contents.append(Spacer(1, 0.25 * inch))
            contents.append(Paragraph('<para alignment="center">Example consumption paths</para>', styleN))
            contents.append(svg(aid, 'paths-consume'))
            contents.append(PageBreak())
            contents.append(Paragraph('<para alignment="center">Example guaranteed income paths</para>', styleN))
            contents.append(svg(aid, 'paths-gi'))
            contents.append(Spacer(1, 0.25 * inch))
            contents.append(Paragraph('<para alignment="center">Example investment paths</para>', styleN))
            contents.append(svg(aid, 'paths-p'))
            contents.append(Spacer(1, 0.25 * inch))
            contents.append(Paragraph('<para alignment="center">Example asset allocation paths</para>', styleN))
            contents.append(svg(aid, 'paths-stocks'))
            contents.append(PageBreak())
            contents.append(Paragraph('<para alignment="center">Residual estate distribution</para>', styleN))
            contents.append(svg(aid, 'estate-pdf'))
            contents.append(Spacer(1, 0.25 * inch))
            contents.append(Paragraph('<para alignment="center">Cummulative estate distribution</para>', styleN))
            contents.append(svg(aid, 'estate-cdf'))
    contents.append(PageBreak())
    s = '<para alignment="center">Scenario parameters</para>'
    contents.append(Paragraph(s, styleH))
    params = dict(api)
    gi = params.get('guaranteed_income', [])
    try:
        del params['guaranteed_income']
    except KeyError:
        pass
    s = ''
    for name, value in sorted(params.items()):
        s += name + ': ' + escape(str(value)) + '<br/>'
    s = '<para size="8" leading="10">' + s + '</para>'
    contents.append(Paragraph(s, styleN))
    if gi:
        contents.append(Spacer(1, 0.25 * inch))
        t = Table([[
            'type', 'owner', 'start', 'end', 'payout', 'adjustment', 'joint', 'payout_fract', 'funds', 'excl_period', 'excl_amount',
        ]] + [[
            g.get('type'), g.get('owner'), g.get('start'), g.get('end'), g.get('payout'), g.get('inflation_adjustment'),
            g.get('joint'), g.get('payout_fraction'), g.get('source_of_funds'), g.get('exclusion_period'), g.get('exclusion_amount'),
        ] for g in gi], style = [
            ['SIZE', (0, 0), (-1, -1), 8],
            ['LEADING', (0, 0), (-1, -1), 10],
            ['ALIGNMENT', (0, 0), (-1, -1), 'CENTER'],
            ['TOPPADDING', (0, 1), (-1, -1), 0],
            ['BOTTOMPADDING', (0, 1), (-1, -1), 0],
        ])
        contents.append(t)
    contents.append(Spacer(1, 0.25 * inch))
    s = '''<para size="7" leading="9">This document is provided without any
warranty; without even the implied warranty of merchantability or
fitness for a particular purpose.</para>'''
    contents.append(TopPadder(Paragraph(s, styleN)))
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.drawString(pagewidth / 2, 0.25 * inch, 'Page ' + str(doc.page))
        canvas.restoreState()
    doc.build(contents, onLaterPages=footer)

    return filename
