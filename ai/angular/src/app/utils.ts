/* AIPlanner - Deep Learning Financial Planner
 * Copyright (C) 2019 Gordon Irlam
 *
 * All rights reserved. This program may not be used, copied, modified,
 * or redistributed without permission.
 *
 * This program is distributed WITHOUT ANY WARRANTY; without even the
 * implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 * PURPOSE.
 */

import {Injectable} from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class Utils {

  public comma(x) {
    return Math.round(x).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

}
