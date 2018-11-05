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

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class ResultService {

  constructor(private http: HttpClient) { }

  doResult(id) {
    return this.http.post('/api/result', {'id': id});
  }
}
