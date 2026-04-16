"""Tests for the in-process event dispatcher."""

import pytest

from utils.events import dispatcher


@pytest.fixture(autouse=True)
def _reset():
    dispatcher._reset_for_tests()
    yield
    dispatcher._reset_for_tests()


def test_register_and_dispatch_invokes_handler():
    received = []

    def handler(payload):
        received.append(payload)

    dispatcher.register("Foo", handler)
    dispatcher.dispatch("Foo", {"x": 1})

    assert received == [{"x": 1}]


def test_double_register_is_idempotent():
    received = []

    def handler(payload):
        received.append(payload)

    dispatcher.register("Foo", handler)
    dispatcher.register("Foo", handler)
    dispatcher.dispatch("Foo", 1)

    assert received == [1]


def test_unknown_event_is_noop():
    dispatcher.dispatch("NoSuchEvent", "anything")


def test_handler_exception_does_not_block_other_handlers():
    received = []

    def boom(_):
        raise RuntimeError("nope")

    def ok(payload):
        received.append(payload)

    dispatcher.register("Event", boom)
    dispatcher.register("Event", ok)
    dispatcher.dispatch("Event", "hello")

    assert received == ["hello"]


def test_unregister_removes_handler():
    received = []

    def handler(payload):
        received.append(payload)

    dispatcher.register("Event", handler)
    dispatcher.unregister("Event", handler)
    dispatcher.dispatch("Event", 1)

    assert received == []


def test_unregister_unknown_handler_is_noop():
    def handler(_):
        pass

    dispatcher.unregister("NoSuchEvent", handler)
    dispatcher.unregister("Event", handler)  # event exists w/ no handler? still fine
