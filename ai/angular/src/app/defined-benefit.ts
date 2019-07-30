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

import { ScenarioComponent } from './scenario/scenario.component';

export class DefinedBenefit {

  public scenario: ScenarioComponent;
  public type: string;
  public owner: string = 'self';
  public amountPer: number = 0;
  public per: string = 'month';
  public age: number;
  public years: number;
  public inflationAdjustment: any;
  public joint: boolean;
  public payoutFractionPct: number;
  public sourceOfFunds: string;
  public exclusionPeriod: number = 0;
  public exclusionAmountPer: number = 0;

  constructor(scenario: ScenarioComponent, type: string, age: number) {
    this.scenario = scenario;
    this.type = type;
    this.age = type == 'Social Security' ? 66 : age;
    this.years = ['Mortgage', 'Child/Dependent'].includes(type) ? 20 : null;
    this.inflationAdjustment = ['Social Security', 'Pension', 'Child/Dependent'].includes(type) ? "cpi" : 0;
    this.joint = ['Income Annuity', 'Reverse Mortgage'].includes(type);
    this.payoutFractionPct = type == 'Income Annuity' ? 60 : (['Reverse Mortgage', 'Mortgage', 'Child/Dependent'].includes(type) ? 100 : 0);
    this.sourceOfFunds = type == 'Income Annuity' ? 'tax_deferred' : (['Reverse Mortgage', 'Mortgage', 'Child/Dependent'].includes(type) ? 'tax_free' : 'taxable');
  }

  amount() {
    return this.annualize(this.amountPer);
  }

  exclusionAmount() {
    return this.annualize(this.exclusionAmountPer);
  }

  annualize(amount: number) {
    if (this.per == 'month')
      return amount * 12;
    else
      return amount;
  }

}
