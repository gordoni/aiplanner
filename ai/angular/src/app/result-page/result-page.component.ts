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
import { ActivatedRoute, Router } from '@angular/router';

@Component({
  selector: 'app-result-page',
  templateUrl: './result-page.component.html',
  styleUrls: ['./result-page.component.css']
})
export class ResultPageComponent implements OnInit {

  public aid: string;
  private sub: any;

  constructor(
    private route: ActivatedRoute,
    private router: Router
  ) { }

  navHome() {
    this.router.navigate(['/']);
    return false;
  }

  ngOnInit() {
    this.sub = this.route.params.subscribe(
      params => { this.aid = params['aid']; }
    );
  }

  ngOnDestroy() {
    this.sub.unsubscribe();
  }

}
