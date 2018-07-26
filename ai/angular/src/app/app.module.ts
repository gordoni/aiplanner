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

import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

import { AppComponent } from './app.component';
import { ScenarioComponent } from './scenario/scenario.component';
import { DbComponent } from './db/db.component';
import { ScenarioService } from './scenario.service';

@NgModule({
  declarations: [
    AppComponent,
    ScenarioComponent,
    DbComponent
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    FormsModule,
  ],
  providers: [
    ScenarioService,
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }
