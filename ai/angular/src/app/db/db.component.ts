/* AIPlanner - Deep Learning Financial Planner
 * Copyright (C) 2018 Gordon Irlam
 *
 * All rights reserved. This program may not be used, copied, modified,
 * or redistributed without permission.
 *
 * This program is distributed WITHOUT ANY WARRANTY; without even the
 * implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 * PURPOSE.
 */

import { Component, OnInit, Input, ViewChild } from '@angular/core';

import { DefinedBenefit } from '../defined-benefit';

@Component({
  selector: 'app-db',
  templateUrl: './db.component.html',
  styleUrls: ['./db.component.css']
})
export class DbComponent implements OnInit {

  @Input() public data: DefinedBenefit;

  private newData: DefinedBenefit;

  constructor() {
  }

  toNumber(str: string) {
    if (str === null || str === "")
      return null;
    var v: number = Number(str);
    if (isNaN(v))
      return str;
    return v;
  }

  cancel() {
    this.data.scenario.editDefinedBenefit = null;
  }

  done() {
    Object.assign(this.data, this.newData);
    if (!this.data.scenario.definedBenefits.includes(this.data)) {
      this.data.scenario.definedBenefits.push(this.data);
    }
    this.data.scenario.editDefinedBenefit = null;
  }

  ngOnInit() {
    this.newData = Object.assign(new DefinedBenefit(null, null, null), this.data);
  }

}
