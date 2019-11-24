/* AIPlanner - Deep Learning Financial Planner
 * Copyright (C) 2018-2019 Gordon Irlam
 *
 * All rights reserved. This program may not be used, copied, modified,
 * or redistributed without permission.
 *
 * This program is distributed WITHOUT ANY WARRANTY; without even the
 * implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 * PURPOSE.
 */

import { Component, Input, OnChanges, OnInit } from '@angular/core';

import { ApiService } from '../api.service';

@Component({
  selector: 'app-result',
  templateUrl: './result.component.html',
  styleUrls: ['./result.component.css']
})
export class ResultComponent implements OnInit {

  @Input() public result: object;

  public errorMessage = null;
  public results: object = null;

  constructor(
    private apiService: ApiService
  ) {}

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

    var asset_allocation = '';
    var carry = 0;
    for (let alloc of result.asset_allocation) {
      if (asset_allocation)
        asset_allocation += '/';
      var val = Math.round(alloc * 100 + carry);
      asset_allocation += val;
      carry += alloc * 100 - val;
    }

    this.results = {
      'error': null,
      'gamma': result.rra,
      'consume': Math.round(result.consume),
      'real_spias_purchase': result.real_spias_purchase == null ? null : Math.round(result.real_spias_purchase),
      'nominal_spias_adjust': result.nominal_spias_adjust == null ? null : Math.round(result.nominal_spias_adjust * 1000) / 10,
      'nominal_spias_purchase': result.nominal_spias_purchase == null ? null : Math.round(result.nominal_spias_purchase),
      'asset_classes': asset_classes,
      'asset_allocation': asset_allocation,
      'real_bonds_duration': result.real_bonds_duration == null ? null : Math.round(result.real_bonds_duration),
      'nominal_bonds_duration': result.nominal_bonds_duration == null ? null : Math.round(result.nominal_bonds_duration),
      'retirement_contribution': result.retirement_contribution == null ? null : Math.round(result.retirement_contribution),
      'ce': Math.round(result.ce),
      'ce_stderr': Math.round(result.ce_stderr),
      'consume_mean': Math.round(result.consume_mean),
      'consume_stdev': Math.round(result.consume_stdev),
      'consume_preretirement': Math.round(result.consume_preretirement),
      'consume_preretirement_ppf': Math.round(result.consume_preretirement_ppf * 100),
      'consume_low': Math.round(result.consume10),
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
