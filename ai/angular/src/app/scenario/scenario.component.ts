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

import { Component, OnInit } from '@angular/core';

import { ApiService } from '../api.service';
import { DefinedBenefit } from '../defined-benefit';
import { ResultComponent } from '../result/result.component';
import { Utils } from '../utils';

@Component({
  selector: 'app-scenario',
  templateUrl: './scenario.component.html',
  styleUrls: ['./scenario.component.css']
})
export class ScenarioComponent implements OnInit {

  public step: number = 0;
  public doneMarket: boolean = false;

  public observeMarketConditions: boolean = true;
  public stocksPricePct: string;
  public stocksVolatilityPct: string;
  public nominalShortRatePct: string;
  public inflationShortRatePct: string;

  public customerName: string = "";
  public scenarioName: string = "";

  public sex: string = "female";
  public age: number = 50;
  public lifeExpectancyAdditional: number = 3;
  public sex2: string = "none";
  public age2: number = 50;
  public lifeExpectancyAdditional2: number = 3;

  public definedBenefits: DefinedBenefit[] = [];
  public editDefinedBenefit: DefinedBenefit = null;

  public definedLiabilities: DefinedBenefit[] = [];

  public pTaxDeferred: number = 0;
  public pTaxFree: number = 0;
  public pTaxableStocks: number = 0;
  public pTaxableBonds: number = 0;
  public pTaxableCash: number = 0;
  public pTaxableOther: number = 0;
  public pTaxableStocksBasis: number = 0;
  public pTaxableBondsBasis: number = 0;
  public pTaxableOtherBasis: number = 0;

  public ageRetirement: number = 67;
  public incomePreretirement: number = 50000;
  public incomePreretirement2: number = 50000;
  public incomePreretirementAgeEndType: string = 'retirement'
  public incomePreretirementAgeEnd: number = 67
  public incomePreretirementAgeEnd2Type: string = 'retirement'
  public incomePreretirementAgeEnd2: number = 67
  public consumePreretirement: number = 30000;
  public have401k: boolean = true;
  public have401k2: boolean = true;
  public spias: boolean = true;

  public scenario: object;

  private report: string;
  private results: any[];
  private commonDir: string;
  private activeResultIndex: number = 0;

  public email: string = null

  public errorMessage: string = null;

  constructor(
    private apiService: ApiService,
    private utils: Utils,
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

  ageValid() {
    return 10 <= this.age && this.age < 120 && ((this.sex2 == 'none') || 10 <= this.age && this.age2 < 120);
  }

  healthValid() {
    return this.lifeExpectancyAdditional < 10 && ((this.sex2 == 'none') || this.lifeExpectancyAdditional2 < 10);
  }

  highConsume() {
    return this.consumePreretirement > this.incomePreretirement + ((this.sex2 == 'none') ? 0 : this.incomePreretirement2);
  }

  dbTotal(definedItems) {

    var tot: number = 0;
    for (let db of definedItems) {
      if (!['Home Proceeds', 'Credit Card Debt', 'Home Purchase'].includes(db.type))
        tot += db.amount()
    }

    return this.utils.comma(tot)
  }

  pTotal() {
    return this.utils.comma(this.pTaxDeferred + this.pTaxFree + this.pTaxableStocks + this.pTaxableBonds + this.pTaxableCash + this.pTaxableOther);
  }

  pCash() {
    return this.utils.comma(this.pTaxableCash);
  }

  basisTotal() {
    return this.utils.comma(this.pTaxableStocksBasis + this.pTaxableBondsBasis + this.pTaxableCash + this.pTaxableOtherBasis);
  }

  doEdit(db) {
    this.editDefinedBenefit = db;
    return false;
  }

  deleteDb(definedBenefits, index) {
    definedBenefits.splice(index, 1);
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

  gotoStep(step) {
    this.errorMessage = null;
    this.step = step;
    if (step == 0 && !this.doneMarket)
      this.market();
    return false;
  }

  addToDbs(dbs, definedItems, benefit) {
    for (let db of definedItems) {
        var d = {
            'type': db.type.toLowerCase().replace(/ /, '_'),
            'owner': db.owner,
            'start': db.age,
            'end': db.years == null ? null : db.age + db.years,
            'payout': benefit ? db.amount() : - db.amount(),
            'inflation_adjustment': db.inflationAdjustment,
            'joint': db.joint == 'joint',
            'payout_fraction': db.joint == 'single' ? 0 : db.payoutFractionPct / 100,
            'source_of_funds': db.sourceOfFunds,
            'exclusion_period': db.exclusionPeriod,
            'exclusion_amount': db.exclusionAmount(),
        };
        if (! (d.exclusion_period || d.exclusion_amount)) {
            delete d.exclusion_period;
            delete d.exclusion_amount;
        }
        dbs.push(d);
    }
  }

  calculate() {

    for (let dl of this.definedLiabilities) {
      if (dl.type == 'Credit Card Debt') {
        dl.age = this.age;
      }
    }

    var dbs = [];
    this.addToDbs(dbs, this.definedBenefits, true);
    this.addToDbs(dbs, this.definedLiabilities, false);

    var scenario = {
        'observe_market_conditions': this.observeMarketConditions,
        'stocks_price': 1 + Number(this.stocksPricePct) / 100,
        'stocks_volatility': Number(this.stocksVolatilityPct) / 100,
        'real_short_rate': (1 + Number(this.nominalShortRatePct) / 100) / (1 + Number(this.inflationShortRatePct) / 100) - 1,
        'inflation_short_rate': Number(this.inflationShortRatePct) / 100,

        'customer_name': this.customerName,
        'scenario_name': this.scenarioName,

        'sex': this.sex,
        'sex2': (this.sex2 == 'none') ? null : this.sex2,
        'age': this.age,
        'age2': (this.sex2 == 'none') ? 0 : this.age2,
        'life_expectancy_additional': this.lifeExpectancyAdditional,
        'life_expectancy_additional2': (this.sex2 == 'none') ? 0 : this.lifeExpectancyAdditional2,

        'guaranteed_income': dbs,

        'p_tax_deferred': this.pTaxDeferred,
        'p_tax_free': this.pTaxFree,
        'p_taxable_stocks': this.pTaxableStocks,
        'p_taxable_stocks_basis': this.pTaxableStocksBasis,
        'p_taxable_bonds':  this.pTaxableBonds,
        'p_taxable_bonds_basis': this.pTaxableBondsBasis,
        'p_taxable_cash':  this.pTaxableCash,
        'p_taxable_other':  this.pTaxableOther,
        'p_taxable_other_basis': this.pTaxableOtherBasis,

        'age_retirement': this.ageRetirement,
        'income_preretirement': this.incomePreretirement,
        'income_preretirement2': this.incomePreretirement2,
        'income_preretirement_age_end': this.incomePreretirementAgeEndType == 'age' ? this.incomePreretirementAgeEnd : null,
        'income_preretirement_age_end2': this.incomePreretirementAgeEnd2Type == 'age' ? this.incomePreretirementAgeEnd2 : null,
        'consume_preretirement': this.consumePreretirement,
        'have_401k': this.have401k,
        'have_401k2': this.have401k2,

        'spias': this.spias,

        'rra': null,
    };
    if (scenario.sex2 == null) {
        delete scenario.age2;
        delete scenario.life_expectancy_additional2;
        delete scenario.income_preretirement2;
        delete scenario.income_preretirement_age_end2;
        delete scenario.have_401k2;
    }
    this.scenario = scenario;

    this.errorMessage = null;
    this.apiService.post('/api/evaluate', [this.scenario]).subscribe(
      results => this.doResults(results),
      error => this.handleError(error)
    );
    this.step++;

    return false;
  }

  doResults(results) {
     if (results.error) {
       this.errorMessage = results.error;
       this.step--;
     } else {
       this.report = results.result[0].report;
       this.results = results.result[0].results.sort(function(a, b) {return b.rra - a.rra});
       this.results.forEach((result, i) => {
         if (result.error) {
           this.errorMessage = 'Server error: ' + result.error + ' (aid: ' + result.aid + ')';
         }
         result.consume_extra = (i == 0) ? 0 : Math.round((result.consume_mean / this.results[0].consume_mean - 1) * 100) + '%';
         result.consume_uncertainty = Math.round((result.consume_stdev / result.consume_mean) * 100) + '%';
       })
       if (this.errorMessage) {
         this.step--;
         return
       }
       this.commonDir = this.report.match(/^.*\//)[0];
       this.commonDir = this.commonDir.substring(0, this.commonDir.length - 1);
       this.activeResultIndex = Math.min(this.activeResultIndex, this.results.length - 1);
       this.step++;
     }
   }

  gotoRisk(risk) {
    this.activeResultIndex = risk;
  }

  risk(adjust) {
    this.activeResultIndex += adjust;
  }

  subscribe() {
    var request = {
      'email': this.email,
    }
    this.errorMessage = null;
    this.apiService.post('/web/subscribe', request).subscribe(
      results => this.doSubscribe(results),
      error => this.subscribeError(error)
    );

    return false;
  }

  doSubscribe(results) {
    if (results.error) {
       this.errorMessage = results.error;
    } else {
      this.step++;
    }
  }

  subscribeError(error) {
    this.errorMessage = error.message;
  }

  market() {
    this.apiService.get('/api/market', {}).subscribe(
      results => this.doMarket(results),
      error => this.handleError(error)
    );
  }

  doMarket(results) {
    this.stocksPricePct = Math.round((results.stocks_price - 1) * 100).toFixed(0);
    this.stocksVolatilityPct = (results.stocks_volatility * 100).toFixed(0);
    this.nominalShortRatePct = (results.nominal_short_rate * 100).toFixed(1);
    this.inflationShortRatePct = (((1 + results.nominal_short_rate) / (1 + results.real_short_rate) - 1) * 100).toFixed(1);
    this.doneMarket = true;
  }

  handleError(error) {
    this.errorMessage = error.message;
    if (this.step > 0)
      this.step--;
  }

  ngOnInit() {
    this.market();
    var db: DefinedBenefit = new DefinedBenefit(this, 'Social Security', null);
    db.amountPer = 1500;
    this.definedBenefits.push(db);
  }

}
