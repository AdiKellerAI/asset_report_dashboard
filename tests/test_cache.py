from app import cache


def test_get_or_set_computes_once_and_reuses_within_ttl():
    cache.invalidate_all()
    calls = []

    def compute():
        calls.append(1)
        return "value"

    first = cache.get_or_set(("k",), compute, ttl=60)
    second = cache.get_or_set(("k",), compute, ttl=60)

    assert first == "value"
    assert second == "value"
    assert len(calls) == 1  # second call was a cache hit, compute() not called again


def test_get_or_set_recomputes_after_ttl_expires():
    cache.invalidate_all()
    calls = []

    def compute():
        calls.append(1)
        return len(calls)

    first = cache.get_or_set(("k2",), compute, ttl=-1)  # already-expired TTL
    second = cache.get_or_set(("k2",), compute, ttl=-1)

    assert first == 1
    assert second == 2  # recomputed since the (negative) ttl always looks expired


def test_invalidate_all_clears_everything():
    cache.invalidate_all()
    cache.get_or_set(("k3",), lambda: "value", ttl=60)

    cache.invalidate_all()
    calls = []
    cache.get_or_set(("k3",), lambda: calls.append(1), ttl=60)

    assert calls == [1]  # recomputed - the earlier entry was cleared


def test_different_keys_are_independent():
    cache.invalidate_all()

    a = cache.get_or_set(("a",), lambda: "A", ttl=60)
    b = cache.get_or_set(("b",), lambda: "B", ttl=60)

    assert a == "A"
    assert b == "B"
