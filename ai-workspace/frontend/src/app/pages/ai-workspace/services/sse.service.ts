import { Injectable, NgZone } from '@angular/core';
import { Observable } from 'rxjs';

/**
 * Server-Sent Events client for the Agent Mode execution timeline.
 *
 * The SSE event contract (event types, ordering, reconnect/resume behavior) is still an open
 * question in docs/ai_workspace.md — this implements a generic named-event EventSource wrapper
 * that re-emits every event under its own `event` name. Reconnect-with-last-event-id support is
 * left as a TODO until the backend confirms whether `Last-Event-ID` is honored.
 */
@Injectable({ providedIn: 'root' })
export class SseService {
  constructor(private readonly zone: NgZone) {}

  connect(url: string, eventNames: string[] = ['message']): Observable<MessageEvent> {
    return new Observable<MessageEvent>((subscriber) => {
      const source = new EventSource(url, { withCredentials: true });

      const handler = (event: MessageEvent) => {
        this.zone.run(() => subscriber.next(event));
      };

      eventNames.forEach((name) => source.addEventListener(name, handler as EventListener));

      source.onerror = (error) => {
        this.zone.run(() => subscriber.error(error));
      };

      return () => {
        eventNames.forEach((name) => source.removeEventListener(name, handler as EventListener));
        source.close();
      };
    });
  }
}
