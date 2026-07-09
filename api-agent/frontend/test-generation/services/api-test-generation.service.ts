import { HttpClient } from '@angular/common/http';
import { Injectable, NgZone } from '@angular/core';
import { Observable } from 'rxjs';

import {
  ApiScenarioGenerationResult,
  GenerateApiScenariosRequest,
} from '../models/api-scenario.model';
import {
  GenerateApiTestCodeRequest,
  GenerationEvent,
  GenerationJob,
  QueuedTask,
} from '../models/api-test-generation.model';

export const API_TEST_GENERATION_PREFIX = '/api/api-test-generation';

export interface RepoProfileRequest {
  repo_path: string;
  overwrite?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ApiTestGenerationService {
  constructor(
    private readonly http: HttpClient,
    private readonly zone: NgZone,
  ) {}

  generateApiScenarios(payload: GenerateApiScenariosRequest): Observable<QueuedTask> {
    return this.http.post<QueuedTask>(
      `${API_TEST_GENERATION_PREFIX}/generate-api-scenarios`,
      payload,
    );
  }

  generateApiTestCode(payload: GenerateApiTestCodeRequest): Observable<QueuedTask> {
    return this.http.post<QueuedTask>(
      `${API_TEST_GENERATION_PREFIX}/generate-api-test-code`,
      payload,
    );
  }

  getJob(taskId: string): Observable<GenerationJob> {
    return this.http.get<GenerationJob>(`${API_TEST_GENERATION_PREFIX}/jobs/${taskId}`);
  }

  abort(taskId: string): Observable<GenerationJob> {
    return this.http.post<GenerationJob>(`${API_TEST_GENERATION_PREFIX}/abort/${taskId}`, {});
  }

  checkRepoProfile(payload: RepoProfileRequest): Observable<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>(
      `${API_TEST_GENERATION_PREFIX}/checkRepoProfile`,
      payload,
    );
  }

  generateRepoProfile(payload: RepoProfileRequest): Observable<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>(
      `${API_TEST_GENERATION_PREFIX}/generateRepoProfile`,
      payload,
    );
  }

  streamEvents(taskId: string): Observable<GenerationEvent> {
    return new Observable<GenerationEvent>((subscriber) => {
      const source = new EventSource(`${API_TEST_GENERATION_PREFIX}/events/${taskId}`, {
        withCredentials: true,
      });

      const handle = (event: MessageEvent) => {
        this.zone.run(() => {
          try {
            subscriber.next(JSON.parse(event.data) as GenerationEvent);
          } catch (error) {
            subscriber.error(error);
          }
        });
      };

      const eventNames = ['queued', 'running', 'progress', 'aborting', 'aborted', 'completed', 'failed'];
      eventNames.forEach((name) => source.addEventListener(name, handle as EventListener));

      source.onerror = (error) => {
        this.zone.run(() => subscriber.error(error));
      };

      return () => {
        eventNames.forEach((name) => source.removeEventListener(name, handle as EventListener));
        source.close();
      };
    });
  }

  extractScenarioResult(job: GenerationJob): ApiScenarioGenerationResult | null {
    if (!job.result || !('scenarios' in job.result)) return null;
    return job.result as ApiScenarioGenerationResult;
  }
}
