import { Injectable } from '@angular/core';
import { Observable, concatMap, from, of } from 'rxjs';
import { delay } from 'rxjs/operators';

import { GenerationEvent } from '../models/api-test-generation.model';
import { ApiTestGenerationEventsService } from './../services/api-test-generation-events.service';
import { mockEvents } from './api-test-generation.fixtures';

/**
 * Drop-in mock for the SSE stream: replays the same event sequence the real
 * backend publishes (queued → running → progress… → completed), spaced out so
 * the execution timeline animates the way it will in production.
 */
@Injectable()
export class MockApiTestGenerationEventsService extends ApiTestGenerationEventsService {
  override stream(taskId: string): Observable<GenerationEvent> {
    const kind = taskId.includes('code') ? 'code' : 'scenarios';
    return from(mockEvents(taskId, kind)).pipe(
      concatMap((event) => of(event).pipe(delay(650))),
    );
  }
}
