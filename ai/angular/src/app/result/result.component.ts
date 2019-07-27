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

  @Input() public aid: string;
  @Input() public gamma: string;

  public errorMessage = null;
  public results: object = null;

  constructor(
    private apiService: ApiService
  ) {}

  doResults(results) {

    var asset_classes = '';
    for (let ac of results.asset_classes) {
      if (asset_classes)
        asset_classes += '/';
      if (ac.endsWith('bonds'))
        asset_classes += 'bonds';
      else
        asset_classes += ac;
    }

    var asset_allocation = '';
    var carry = 0;
    for (let alloc of results.asset_allocation) {
      if (asset_allocation)
        asset_allocation += '/';
      var val = Math.round(alloc * 100 + carry);
      asset_allocation += val;
      carry += alloc * 100 - val;
    }

    this.results = {
      'error': null,
      'consume': Math.round(results.consume),
      'nominal_spias_purchase': results.nominal_spias_purchase == null ? null : Math.round(results.nominal_spias_purchase),
      'asset_classes': asset_classes,
      'asset_allocation': asset_allocation,
      'real_bonds_duration': Math.round(results.real_bonds_duration),
      'retirement_contribution': Math.round(results.retirement_contribution),
      'ce': Math.round(results.ce),
      'ce_stderr': Math.round(results.ce_stderr),
      'consume_preretirement': Math.round(results.consume_preretirement),
      'consume_preretirement_ppf': Math.round(results.consume_preretirement_ppf * 100),
      'ce_low': Math.round(results.ce10),
      'data_dir': '/api/data/' + results.aid,
    }
  }

  handleError(error) {
    this.results = {'error': error.message};
  }

  ngOnChanges() {
    this.errorMessage = null;
    this.results = null;
    this.apiService.get('result/' + this.id + '/' + this.gamma, {}).subscribe(
      results => this.doResults(results),
      error => this.handleError(error)
    );
  }

  ngOnInit() {
  }

}
