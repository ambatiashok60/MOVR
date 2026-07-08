import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { ReviewSummary } from '../models/review.model';

export interface ApplyChangesRequest {
  runId: string;
  keptFileIds: string[];
}

export interface ApplyChangesResponse {
  appliedFilePaths: string[];
}

@Injectable({ providedIn: 'root' })
export class ReviewService {
  constructor(private readonly http: HttpClient) {}

  getSummary(runId: string): Observable<ReviewSummary> {
    return this.http.get<ReviewSummary>(`${AI_WORKSPACE_API_PREFIX}/agent/runs/${runId}/review-summary`);
  }

  applyChanges(payload: ApplyChangesRequest): Observable<ApplyChangesResponse> {
    return this.http.post<ApplyChangesResponse>(`${AI_WORKSPACE_API_PREFIX}/agent/apply`, payload);
  }
}
