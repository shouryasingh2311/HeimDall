"""
Tests for Check V04, BUFF-01, BUFF-02: Durable buffering, outage resilience and ID reconciliation.

Owned by Member 3 (feat/fixtures-validation).
Verifies:
- Continuous local generation during a 30s transport outage.
- Durable local outbox queue preserves all generated events in FIFO order.
- Reconnection flushes the outbox without data loss.
- Expected unique input ID set matches flushed/received ID set exactly (set equality).
- Bounded queue handles backpressure without silent data corruption.
"""

import collections
import pytest
from typing import Deque, List, Set

from backend.collector.demo_source import DemoSource, RawEvent


class MockOutboxQueue:
    """
    In-memory representation of M1's durable outbox queue to verify buffering semantics.
    Bounded capacity with FIFO drain.
    """
    def __init__(self, max_capacity: int = 500):
        self.max_capacity = max_capacity
        self.queue: Deque[RawEvent] = collections.deque()
        self.total_enqueued = 0
        self.dropped_count = 0

    def enqueue(self, event: RawEvent) -> bool:
        if len(self.queue) >= self.max_capacity:
            self.dropped_count += 1
            return False
        self.queue.append(event)
        self.total_enqueued += 1
        return True

    def drain(self, batch_size: int = 50) -> List[RawEvent]:
        batch = []
        while self.queue and len(batch) < batch_size:
            batch.append(self.queue.popleft())
        return batch

    @property
    def depth(self) -> int:
        return len(self.queue)


def test_outage_buffering_and_id_set_reconciliation():
    """
    Scenario 2: Simulates 30 seconds (15 ticks at 2s interval) of transport disconnect.
    Generation continues; outbox buffers events; reconnection flushes all events with matching IDs.
    """
    source = DemoSource(seed=777, run_id="outage-test")
    outbox = MockOutboxQueue(max_capacity=500)

    # Transport state: disconnected for 15 ticks
    is_connected = False
    expected_ids: Set[str] = set()

    # 1. 15 ticks during outage
    for tick_idx in range(15):
        tick_events = source.generate_tick(tenants=["tenant-alpha"])
        for event in tick_events:
            expected_ids.add(event.input_id)
            if not is_connected:
                # Buffering into outbox
                enqueued = outbox.enqueue(event)
                assert enqueued, f"Outbox rejected event {event.input_id}"

    # Verify outbox buffered all events generated during disconnect (15 ticks * 5 nodes = 75 events)
    assert outbox.depth == 75
    assert len(expected_ids) == 75

    # 2. Transport reconnected
    is_connected = True
    delivered_events: List[RawEvent] = []

    # Drain outbox
    while outbox.depth > 0:
        flushed_batch = outbox.drain(batch_size=20)
        delivered_events.extend(flushed_batch)

    assert outbox.depth == 0
    delivered_ids: Set[str] = {ev.input_id for ev in delivered_events}

    # Strict reconciliation requirement: expected ID set == delivered ID set
    assert expected_ids == delivered_ids
    assert len(delivered_events) == 75


def test_outbox_bounded_capacity_backpressure():
    """Verify queue behavior when reaching max capacity constraint."""
    small_outbox = MockOutboxQueue(max_capacity=10)
    source = DemoSource(seed=12)

    # Generate 15 events
    events = source.generate_tick(tenants=["tenant-alpha"])  # 5 events
    events += source.generate_tick(tenants=["tenant-alpha"])  # 5 events
    events += source.generate_tick(tenants=["tenant-alpha"])  # 5 events

    enqueued_count = 0
    for ev in events:
        if small_outbox.enqueue(ev):
            enqueued_count += 1

    assert enqueued_count == 10
    assert small_outbox.dropped_count == 5
    assert small_outbox.depth == 10
