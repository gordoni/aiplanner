/* AIPlanner - Deep Learning Financial Planner
 * Copyright (C) 2021 Gordon Irlam
 *
 * All rights reserved. This program may not be used, copied, modified,
 * or redistributed without permission.
 *
 * This program is distributed WITHOUT ANY WARRANTY; without even the
 * implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 * PURPOSE.
 */

import { Component, OnInit, Input } from '@angular/core';

import { MatDialog } from '@angular/material/dialog';

import { ModalComponent } from '../modal/modal.component';

@Component({
  selector: 'app-info',
  templateUrl: './info.component.html',
  styleUrls: ['./info.component.css']
})
export class InfoComponent implements OnInit {

  @Input() public msg: string;
  @Input() public type: 'tooltip' | 'modal' = 'modal';
    /*
     * For both types the text is wrapped with no formatting possible.
     *
     * Tooltip normally works best for both touch and non-touch devices.
     *
     * Tooltip doesn't seem to work on touch based chromium derived browsers.
     * You need to long press, which is non-intuitive, and long press then brings up the system menu.
     *
     * Modals work better for large amonts of text because the width of tooltips is limited.
     *
     * If tooltips and modals are intermixed there is a UI inconsistecy on non-touch devices: some info icons need to be hovered while others need to be clicked.
     */

  constructor(public dialog: MatDialog) { }

  ngOnInit(): void {
  }

  public openDialog() {
      this.dialog.open(ModalComponent, {
        'data': this.msg,
      });
  }

}
