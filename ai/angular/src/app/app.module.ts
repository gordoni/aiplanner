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

import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
/*
import { RouterModule, Routes } from '@angular/router';
*/
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

import { MatDialogModule } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';

import { AppComponent } from './app.component';
import { ScenarioComponent } from './scenario/scenario.component';
import { DbComponent } from './db/db.component';
import { LiabilityComponent } from './liability/liability.component';
import { ApiService } from './api.service';
import { ResultComponent } from './result/result.component';
/*
import { ResultPageComponent } from './result-page/result-page.component';
*/
import { PageNotFoundComponent } from './page-not-found/page-not-found.component';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { InfoComponent } from './info/info.component';
import { ModalComponent } from './modal/modal.component';

/*
const appRoutes: Routes = [
  { path: '', component: ScenarioComponent },
  { path: 'result/:id', component: ResultPageComponent },
  { path: '**', component: PageNotFoundComponent }
];
*/

@NgModule({
  declarations: [
    AppComponent,
    ScenarioComponent,
    DbComponent,
    LiabilityComponent,
    PageNotFoundComponent,
    ResultComponent,
    InfoComponent,
    ModalComponent,
    /* ResultPageComponent, */
  ],
  imports: [
    BrowserModule,
    /* RouterModule.forRoot(appRoutes), */
    HttpClientModule,
    FormsModule,
    BrowserAnimationsModule,
    MatDialogModule,
    MatTooltipModule,
  ],
  providers: [
    ApiService,
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }
