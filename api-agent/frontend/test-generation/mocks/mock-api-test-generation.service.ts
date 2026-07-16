import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay } from 'rxjs/operators';

import { GenerateApiScenariosRequest } from '../models/api-scenario.model';
import {
  GenerateApiTestCodeRequest,
  GenerationJob,
  QueuedTask,
} from '../models/api-test-generation.model';
import {
  ApiTestGenerationService,
  RepoProfileRequest,
} from '../services/api-test-generation.service';
import { mockJob } from './api-test-generation.fixtures';

/**
 * Drop-in mock for ApiTestGenerationService — same public contract, no backend.
 *
 * Used for design reviews: the UI behaves exactly as it will against the real
 * FastAPI service (queue → SSE progress → job refresh), with fixture payloads
 * that mirror the worktop.api_agent response schemas.
 */
@Injectable()
export class MockApiTestGenerationService extends ApiTestGenerationService {
  private readonly jobs = new Map<string, GenerationJob>();
  private counter = 0;

  override generateApiScenarios(_: GenerateApiScenariosRequest): Observable<QueuedTask> {
    return this.queue('scenarios');
  }

  override generateApiTestCode(_: GenerateApiTestCodeRequest): Observable<QueuedTask> {
    return this.queue('code');
  }

  override getJob(taskId: string): Observable<GenerationJob> {
    const job = this.jobs.get(taskId) ?? mockJob(taskId, 'scenarios');
    return of(job).pipe(delay(200));
  }

  override abort(taskId: string): Observable<GenerationJob> {
    const job = { ...(this.jobs.get(taskId) ?? mockJob(taskId, 'scenarios')) };
    job.status = 'aborted';
    job.abort_requested = true;
    this.jobs.set(taskId, job);
    return of(job).pipe(delay(150));
  }

  override checkRepoProfile(_: RepoProfileRequest): Observable<Record<string, unknown>> {
    return of({ exists: true, profile: { languages: ['java'], api_styles: ['rest'] } }).pipe(
      delay(200),
    );
  }

  override generateRepoProfile(_: RepoProfileRequest): Observable<Record<string, unknown>> {
    return of({ generated: true }).pipe(delay(400));
  }

  private queue(kind: 'scenarios' | 'code'): Observable<QueuedTask> {
    this.counter += 1;
    const taskId = `mock-${kind}-${this.counter}`;
    this.jobs.set(taskId, mockJob(taskId, kind));
    return of({ queued: true, task_id: taskId }).pipe(delay(250));
  }
}
