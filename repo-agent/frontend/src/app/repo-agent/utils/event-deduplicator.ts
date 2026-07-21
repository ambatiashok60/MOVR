/** Tracks the last processed sequence per run so replayed/duplicate SSE events
 *  are ignored (idempotent event application). */
export class EventDeduplicator {
  private lastSequence = 0;

  reset(): void {
    this.lastSequence = 0;
  }

  /** Returns true if this event is new and should be applied. */
  accept(sequence: number | undefined): boolean {
    if (typeof sequence !== 'number') return true;
    if (sequence <= this.lastSequence) return false;
    this.lastSequence = sequence;
    return true;
  }

  get current(): number {
    return this.lastSequence;
  }
}
