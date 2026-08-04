from app import store, worker


def test_sigterm_requeues_inflight():
    store.reset()
    j = worker.enqueue("resize", {"k": 1})
    w = worker.Worker()
    assert w.poll() is not None
    w.handle_sigterm()
    assert w.stopping is True
    assert w.current is None
    assert store.JOBS, "in-flight job was dropped on SIGTERM"
    assert store.JOBS[0]["id"] == j["id"]
    assert store.JOBS[0]["status"] == "pending"
    store.reset()


def test_sigterm_idle_is_noop():
    store.reset()
    w = worker.Worker()
    w.handle_sigterm()
    assert w.stopping is True and store.JOBS == []
