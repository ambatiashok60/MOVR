import { Injectable, NgZone } from '@angular/core';
import { Observable } from 'rxjs';

import { GenerationEvent } from '../models/api-test-generation.model';
import { API_TEST_GENERATION_PREFIX } from './api-test-generation.service';

@Injectable({ providedIn: 'root' })
export class ApiTestGenerationEventsService {
  constructor(private readonly zone: NgZone) {}

  stream(taskId: string): Observable<GenerationEvent> {
    return new Observable<GenerationEvent>((subscriber) => {
      // HOST APP: native EventSource cannot receive an Authorization header from an
      // Angular interceptor. Keep this for cookie auth, or replace it with the host's
      // fetch-based SSE client when bearer-token authentication is required.
      const source = new EventSource(`${API_TEST_GENERATION_PREFIX}/events/${taskId}`, {
        withCredentials: true,
      });
      const names = ['queued', 'running', 'progress', 'aborting', 'aborted', 'completed', 'failed'];
      const handle = (event: MessageEvent) => this.zone.run(() => {
        try {
          subscriber.next(JSON.parse(event.data) as GenerationEvent);
        } catch (error) {
          subscriber.error(error);
        }
      });

      names.forEach((name) => source.addEventListener(name, handle as EventListener));
      source.onerror = (error) => this.zone.run(() => subscriber.error(error));

      return () => {
        names.forEach((name) => source.removeEventListener(name, handle as EventListener));
        source.close();
      };
    });
  }
}
