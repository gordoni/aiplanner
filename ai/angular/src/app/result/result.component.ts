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

import { Component, Input, OnChanges, OnInit } from '@angular/core';

import { ApiService } from '../api.service';

@Component({
  selector: 'app-result',
  templateUrl: './result.component.html',
  styleUrls: ['./result.component.css']
})
export class ResultComponent implements OnInit {

  @Input() public id: string;
  @Input() public mode: string;

  public errorMessage = null;
  public results: object = null;

  constructor(
    private apiService: ApiService
  ) {}

  doResults(results) {
    if (this.mode == 'full' && results.error == 'Results not found.')
      this.results = null;
    else
      this.results = results;
  }

  handleError(error) {
    this.results = {'error': error.message};
  }

  ngOnChanges() {
    this.errorMessage = null;
    this.results = null;
    this.apiService.post('result', {'id': this.id, 'mode': this.mode}).subscribe(
      results => this.doResults(results),
      error => this.handleError(error)
    );
  }

  ngOnInit() {
  }

}
