"""The thread/queue plumbing behind the window, tested without tkinter."""

from __future__ import annotations

import threading
import time

from meta_still.ui.runner import BackgroundJob, Finished, Log, Step


def wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timed out")


def test_events_reach_the_caller_in_order() -> None:
    job = BackgroundJob()

    def work(report, cancelled):
        report(Log("scanning"))
        report(Step(1, 2))
        report(Step(2, 2))
        return "summary"

    job.start(work)
    wait_until(lambda: not job.running)

    events = job.drain()
    assert events == [Log("scanning"), Step(1, 2), Step(2, 2), Finished(value="summary")]


def test_drain_never_blocks_when_nothing_happened() -> None:
    assert BackgroundJob().drain() == []


def test_a_crash_is_reported_rather_than_lost() -> None:
    """An exception on a worker thread is invisible by default - the window
    would simply sit there looking busy for ever."""
    job = BackgroundJob()

    def work(report, cancelled):
        raise ValueError("moov atom not found")

    job.start(work)
    wait_until(lambda: not job.running)

    events = job.drain()
    assert isinstance(events[0], Log)
    assert "ValueError" in events[0].text
    assert events[-1] == Finished(error="moov atom not found")


def test_cancel_is_visible_to_the_work() -> None:
    job = BackgroundJob()
    seen: list[bool] = []
    release = threading.Event()

    def work(report, cancelled):
        release.wait(timeout=5)
        seen.append(cancelled())
        return None

    job.start(work)
    job.cancel()
    release.set()
    wait_until(lambda: not job.running)

    assert seen == [True]
    assert job.cancelled


def test_two_jobs_cannot_run_at_once() -> None:
    job = BackgroundJob()
    release = threading.Event()

    job.start(lambda report, cancelled: release.wait(timeout=5))
    try:
        wait_until(lambda: job.running)
        raised = False
        try:
            job.start(lambda report, cancelled: None)
        except RuntimeError:
            raised = True
        assert raised
    finally:
        release.set()
        wait_until(lambda: not job.running)
