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

import { Component, OnInit } from '@angular/core';

import { ScenarioService } from '../scenario.service';
import { DefinedBenefit } from '../defined-benefit';

@Component({
  selector: 'app-scenario',
  templateUrl: './scenario.component.html',
  styleUrls: ['./scenario.component.css']
})
export class ScenarioComponent implements OnInit {

  public step: number = 0;
  public sex: string = "male";
  public age: number = 50;
  public lifeExpectancyAdditional: number = 2;

  public definedBenefits: DefinedBenefit[] = [];
  public editDefinedBenefit: DefinedBenefit = null;

  public pTaxDeferred: number = 0;
  public pTaxFree: number = 0;
  public pTaxableBonds: number = 0;
  public pTaxableStocks: number = 0;
  public pTaxableStocksBasis: number = 0;

  public retirementAge: number = 66;

  public gamma: number = 3;

  public errorMessage = null;

  public consume: number;
  public assetAllocation: string;
  public dataDir: string;

  constructor(private scenarioService: ScenarioService) {
  }

  health() {
    if (this.lifeExpectancyAdditional >= 4)
      return "Excellent";
    if (this.lifeExpectancyAdditional >= 2)
      return "Good";
    if (this.lifeExpectancyAdditional >= 0)
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
    this.step++;
    return false;
  }

  editSteps() {
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
        'sex': this.sex,
        'age_start': this.age,
        'life_expectancy_additional': this.lifeExpectancyAdditional,

        'defined_benefits': dbs,

        'p_tax_deferred': this.pTaxDeferred,
        'p_tax_free': this.pTaxFree,
        'p_taxable_bonds':  this.pTaxableBonds,
        'p_taxable_stocks': this.pTaxableStocks,
        'p_taxable_stocks_basis': this.pTaxableStocksBasis,

        'retirement_age': this.retirementAge,

        'gamma': this.gamma,
    };

    this.errorMessage = null;
    this.scenarioService.doScenario(scenario).subscribe(
      results => this.doResults(this, results),
      error => this.handleError(this, error)
    );
    this.step++;

    return false;
  }

  handleError(scenario, error) {
    scenario.errorMessage = error.message;
    this.step--;
  }

  doResults(scenario, results) {
    scenario.consume = results.consume;
    scenario.assetAllocation = results.asset_allocation;
    scenario.dataDir = results.data_dir;

    scenario.step++;
  }

  ngOnInit() {
    var db: DefinedBenefit = new DefinedBenefit(this, 'Social Security', null);
    db.amountPer = 1300;
    this.definedBenefits.push(db);
  }

}
