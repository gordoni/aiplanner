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
  public per: string;
  public age: number;
  public years: number;
  public inflationAdjustment: any;
  public joint: string;
  public payoutFractionPct: number;
  public sourceOfFunds: string;
  public exclusionPeriod: number = 0;
  public exclusionAmountPer: number = 0;

  constructor(scenario: ScenarioComponent, type: string, age: number) {
    this.scenario = scenario;
    this.type = type;
    this.per = ['Home Proceeds', 'College Expenses', 'Home Purchase'].includes(type) ? 'year' : 'month';
    this.age = type == 'Social Security' ? 67 : age;
    this.years = ['Mortgage', 'Child/Dependent'].includes(type) ? 20 : ['College Expenses'].includes(type) ? 4 : ['Home Proceeds', 'Home Purchase'] ? 1 : null;
    this.inflationAdjustment = ['Social Security', 'Pension', 'Home Proceeds', 'Child/Dependent', 'College Expenses', 'Home Purchase'].includes(type) ? "cpi" :
        type == 'Income Annuity' ? 0.02 : 0;
    this.joint = ['Income Annuity', 'Reverse Mortgage'].includes(type) ? 'joint' : (['Pension'].includes(type) ? 'single' : 'survivor');
    this.payoutFractionPct = ['Pension', 'Income Annuity'].includes(type) ? 60 :
        (['Reverse Mortgage', 'Home Proceeds', 'Mortgage', 'Child/Dependent', 'College Expenses', 'Home Purchase'].includes(type) ? 100 : 0);
    this.sourceOfFunds = type == 'Income Annuity' ? 'tax_deferred' :
        (['Reverse Mortgage', 'Home Proceeds', 'Mortgage', 'Child/Dependent', 'College Expenses', 'Home Purchase'].includes(type) ? 'tax_free' : 'taxable');
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
