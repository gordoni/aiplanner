/* AIPlanner - Deep Learning Financial Planner
 * Copyright (C) 2018-2021 Gordon Irlam
 *
 * All rights reserved. This program may not be used, copied, modified,
 * or redistributed without permission.
 *
 * This program is distributed WITHOUT ANY WARRANTY; without even the
 * implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 * PURPOSE.
 */

import { Component, Input, OnChanges, OnInit } from '@angular/core';

import { Utils } from '../utils';

@Component({
  selector: 'app-result',
  templateUrl: './result.component.html',
  styleUrls: ['./result.component.css']
})
export class ResultComponent implements OnInit {

  @Input() public result: object;
  @Input() public scenario: object;

  public errorMessage = null;
  public results: object = null;

  constructor(
    private utils: Utils,
  ) {}

  aaStr(aa) {

    if (aa) {
      var asset_allocation = '';
      var carry = 0;
      for (let alloc of aa) {
        if (asset_allocation)
          asset_allocation += '/';
        var val = Math.round(alloc * 100 + carry);
        asset_allocation += val;
        carry += alloc * 100 - val;
      }
      return asset_allocation;
    } else {
      return null;
    }
  }

  doResult(result) {

    var asset_classes = '';
    for (let ac of result.asset_classes) {
      if (asset_classes)
        asset_classes += '/';
      if (ac.endsWith('bonds'))
        asset_classes += 'bonds';
      else
        asset_classes += ac;
    }

    this.results = {
      'error': null,
      'warnings': result.warnings,
      'gamma': result.rra,
      'consume': this.utils.comma(result.consume),
      'real_spias_purchase': result.real_spias_purchase == null ? null : this.utils.comma(result.real_spias_purchase),
      'nominal_spias_adjust': result.nominal_spias_adjust == null ? null : Math.round(result.nominal_spias_adjust * 1000) / 10,
      'nominal_spias_purchase': result.nominal_spias_purchase == null ? null : this.utils.comma(result.nominal_spias_purchase),
      'asset_classes': asset_classes,
      'asset_allocation': this.aaStr(result.asset_allocation),
      'asset_allocation_tax_free': this.aaStr(result.asset_allocation_tax_free),
      'asset_allocation_tax_deferred': this.aaStr(result.asset_allocation_tax_deferred),
      'asset_allocation_taxable': this.aaStr(result.asset_allocation_taxable),
      'real_bonds_duration': result.real_bonds_duration == null ? null : Math.round(result.real_bonds_duration),
      'nominal_bonds_duration': result.nominal_bonds_duration == null ? null : Math.round(result.nominal_bonds_duration),
      'retirement_contribution': result.retirement_contribution == null ? null : this.utils.comma(result.retirement_contribution),
      'ce': this.utils.comma(result.ce),
      'ce_stderr': this.utils.comma(result.ce_stderr),
      'consume_mean': this.utils.comma(result.consume_mean),
      'consume_stdev': this.utils.comma(result.consume_stdev),
      'consume_preretirement': this.utils.comma(result.consume_preretirement),
      'consume_preretirement_ppf': Math.round(result.consume_preretirement_ppf * 100),
      'consume_low': this.utils.comma(result.consume10),
      'data_dir': '/webapi/data/' + result.aid,
    }
  }

  handleError(error) {
    this.results = {'error': error.message};
  }

  ngOnInit() {
    this.doResult(this.result);
  }

}
