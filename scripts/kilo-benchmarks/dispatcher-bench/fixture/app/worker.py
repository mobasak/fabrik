"""Job worker: pulls from store.JOBS (FIFO), processes one job at a time."""
from __future__ import annotations

from app import notify, settings, store


def enqueue(kind: str, payload: dict) -> dict:
    job = {"id": f"job_{len(store.JOBS) + 1:05d}", "kind": kind, "payload": payload, "status": "pending"}
    store.JOBS.append(job)
    return job


class Worker:
    def __init__(self, env: dict | None = None):
        self.conf = settings.load(env or {})
        self.current: dict | None = None
        self.stopping = False

    def poll(self) -> dict | None:
        if self.current is None and store.JOBS:
            self.current = store.JOBS.pop(0)
            self.current["status"] = "running"
        return self.current

    def finish(self) -> None:
        if self.current is not None:
            self.current["status"] = "done"
            notify.send("ops", f"job {self.current['id']} done")
            self.current = None

    def handle_sigterm(self, *_args) -> None:
        # Shutdown: stop polling and drop out of the loop.
        self.stopping = True
        self.current = None
