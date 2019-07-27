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

import { Component, OnInit } from '@angular/core';

import { ApiService } from '../api.service';
import { DefinedBenefit } from '../defined-benefit';
import { ResultComponent } from '../result/result.component';

@Component({
  selector: 'app-scenario',
  templateUrl: './scenario.component.html',
  styleUrls: ['./scenario.component.css']
})
export class ScenarioComponent implements OnInit {

  public step: number = 0;
  public doneMarket: boolean = false;

  public stocksPricePct: number;
  public nominalShortRatePct: string;
  public inflationShortRatePct: string;

  public sex: string = "female";
  public age: number = 50;
  public lifeExpectancyAdditional: number = 3;
  public sex2: string = "none";
  public age2: number = 50;
  public lifeExpectancyAdditional2: number = 3;

  public definedBenefits: DefinedBenefit[] = [];
  public editDefinedBenefit: DefinedBenefit = null;

  public pTaxDeferred: number = 0;
  public pTaxFree: number = 0;
  public pTaxableBonds: number = 0;
  public pTaxableStocks: number = 0;
  public pTaxableStocksBasis: number = 0;

  public ageRetirement: number = 66;
  public incomePreretirement: number = 60000;
  public incomePreretirement2: number = 60000;
  public consumePreretirement: number = 40000;
  public have401k: boolean = true;
  public have401k2: boolean = true;
  public spias: boolean = true;

  public gamma: string = "3";

  private result_aid: string = null;

  public email: string = null
  public name: string = "My Results";

  public run_queue_length = null;

  public errorMessage: string = null;

  constructor(
    private apiService: ApiService,
  ) {}

  health(individual: string) {
    var leAdditional: number = (individual == 'self') ? this.lifeExpectancyAdditional : this.lifeExpectancyAdditional2;
    if (leAdditional >= 4)
      return "Excellent";
    if (leAdditional >= 2)
      return "Good";
    if (leAdditional >= 0)
      return "Fair";
    else
      return "Poor";
  }

  dbTotal() {

    var tot: number = 0;
    for (let db of this.definedBenefits) {
      tot += db.amount()
    }

    return tot;
  }

  pTotal() {
    return this.pTaxDeferred + this.pTaxFree + this.pTaxableBonds + this.pTaxableStocks;
  }

  doEdit(db) {
    this.editDefinedBenefit = db;
    return false;
  }

  deleteDb(index) {
    this.definedBenefits.splice(index, 1);
    return false;
  }

  addDb(type) {
    var db: DefinedBenefit = new DefinedBenefit(this, type, this.age);
    this.editDefinedBenefit = db;
    return false;
  }

  dbValid() {
    return !this.editDefinedBenefit;
  }

  nextStep() {
    this.errorMessage = null;
    this.step++;
    return false;
  }

  prevStep() {
    this.errorMessage = null;
    this.step--;
    return false;
  }

  firstStep() {
    this.result_id = null;
    this.errorMessage = null;
    this.step = 1;
    return false;
  }

  calculate() {

    var dbs = [];
    for (let db of this.definedBenefits) {
        dbs.push({
            'type': db.type,
            'owner': db.owner,
            'age': db.age,
            'payout': db.amount(),
            'inflation_adjustment': db.inflationAdjustment,
            'joint': db.joint,
            'payout_fraction': db.payoutFractionPct / 100,
            'source_of_funds': db.sourceOfFunds,
            'exclusion_period': db.exclusionPeriod,
            'exclusion_amount': db.exclusionAmount(),
        });
    }

    var scenario = {
        'stocks_price': this.stocksPricePct / 100,
        'real_short_rate_type': 'value',
        'real_short_rate_value': (1 + Number(this.nominalShortRatePct) / 100) / (1 + Number(this.inflationShortRatePct) / 100) - 1,
        'inflation_short_rate_type': 'value',
        'inflation_short_rate_value': Number(this.inflationShortRatePct) / 100,

        'sex': this.sex,
        'sex2': (this.sex2 == 'none') ? null : this.sex2,
        'age_start': this.age,
        'age_start2': (this.sex2 == 'none') ? 0 : this.age2,
        'life_expectancy_additional': this.lifeExpectancyAdditional,
        'life_expectancy_additional2': (this.sex2 == 'none') ? 0 : this.lifeExpectancyAdditional2,

        'guaranteed_income': dbs,

        'p_tax_deferred': this.pTaxDeferred,
        'p_tax_free': this.pTaxFree,
        'p_taxable_bonds':  this.pTaxableBonds,
        'p_taxable_stocks': this.pTaxableStocks,
        'p_taxable_stocks_basis': this.pTaxableStocksBasis,

        'age_retirement': this.ageRetirement,
        'income_preretirement': this.incomePreretirement,
        'income_preretirement2': this.incomePreretirement,
        'consume_preretirement': this.consumePreretirement,
        'have_401k': this.have401k,
        'have_401k2': this.have401k2,
        'spias': this.spias,

        'gamma': Number(this.gamma),
    };

    this.errorMessage = null;
    this.apiService.post('scenario', scenario).subscribe(
      results => this.doResults(results),
      error => this.handleError(error)
    );
    this.step++;

    return false;
  }

  doResults(results) {
     this.result_aid = results[0]['aid'];
     this.step++;
   }

  subscribe() {
    var request = {
      'email': this.email,
    }
    this.errorMessage = null;
    this.apiService.post('subscribe', request).subscribe(
      results => this.doSubscribe(results),
      error => this.handleError(error)
    );
    this.step++;

    return false;
  }

  doSubscribe(results) {
    this.step++;
  }

  doMarket(results) {
    this.stocksPricePct = Math.round(results.stocks_price * 100);
    this.nominalShortRatePct = (results.nominal_short_rate - 1) * 100).toFixed(1);
    this.inflationShortRatePct = (((1 + results.nominal_short_rate) / (1 + results.real_short_rate) - 1) * 100).toFixed(1);
    this.doneMarket = true;
  }

  handleError(error) {
    this.errorMessage = error.message;
    if (this.step > 0)
      this.step--;
  }

  ngOnInit() {
    this.apiService.get('market', {}).subscribe(
      results => this.doMarket(results),
      error => this.handleError(error)
    );
    var db: DefinedBenefit = new DefinedBenefit(this, 'Social Security', null);
    db.amountPer = 1500;
    this.definedBenefits.push(db);
  }

}
