"""Unit tests for EventBus and Event handling."""

import pytest
from neron.core.events.bus import EventBus
from neron.core.events.event import EmergencyStopEvent, Event


def test_event_subscription_and_publish():
    bus = EventBus()
    received = []

    def handler(ev: Event):
        received.append(ev)

    bus.subscribe("test.event", handler)
    ev = Event(event_type="test.event", payload={"data": 42})
    bus.publish(ev)

    assert len(received) == 1
    assert received[0].payload["data"] == 42


def test_wildcard_subscription():
    bus = EventBus()
    received = []

    bus.subscribe("*", lambda ev: received.append(ev))
    bus.publish(Event(event_type="event.one"))
    bus.publish(Event(event_type="event.two"))

    assert len(received) == 2


def test_unsubscribe():
    bus = EventBus()
    received = []

    def handler(ev: Event):
        received.append(ev)

    bus.subscribe("event.sub", handler)
    bus.publish(Event(event_type="event.sub"))
    assert len(received) == 1

    bus.unsubscribe("event.sub", handler)
    bus.publish(Event(event_type="event.sub"))
    assert len(received) == 1


def test_handler_exception_isolation():
    bus = EventBus()
    received = []

    def faulty_handler(ev: Event):
        raise RuntimeError("Handler failure")

    def safe_handler(ev: Event):
        received.append(ev)

    bus.subscribe("test.fail", faulty_handler)
    bus.subscribe("test.fail", safe_handler)

    # Publishing should not raise and safe_handler should still be invoked
    bus.publish(Event(event_type="test.fail"))
    assert len(received) == 1


def test_emergency_stop_event():
    ev = EmergencyStopEvent(reason="Safety trigger")
    assert ev.event_type == "emergency.stop"
    assert ev.payload["reason"] == "Safety trigger"
