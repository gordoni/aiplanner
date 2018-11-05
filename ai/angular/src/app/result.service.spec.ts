import { TestBed, inject } from '@angular/core/testing';

import { ResultService } from './result.service';

describe('ResultService', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ResultService]
    });
  });

  it('should be created', inject([ResultService], (service: ResultService) => {
    expect(service).toBeTruthy();
  }));
});
