import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

@Component({
  selector: 'app-result-page',
  templateUrl: './result-page.component.html',
  styleUrls: ['./result-page.component.css']
})
export class ResultPageComponent implements OnInit {

  public id: string;
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
      params => { this.id = params['id']; }
    );
  }

  ngOnDestroy() {
    this.sub.unsubscribe();
  }

}
