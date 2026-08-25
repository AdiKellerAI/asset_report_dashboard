"""A tiny in-memory TTL cache for expensive read queries (dashboard/trends
aggregation, the tables-page listings) against the real remote Neon
Postgres - a network round trip per query is the dominant cost (see
docs/PROJECT_STATUS.md's dashboard-load-time fix), not data volume, so
caching computed results in the server's memory speeds up every client
(desktop or mobile) equally - unlike a client-side cache, which would have
to be built and warmed separately per device.

Explicitly invalidated whenever /manage or /upload writes new data (see
their routes), rather than relying purely on the TTL, so a change is never
stale for the TTL's duration - the TTL is just a safety net for anything
that mutates data outside those two paths.

Process-local (a plain dict): fine for this app's single dev-server
process. Would need a shared store (e.g. Redis) if this ever ran as
multiple Cloud Run instances/workers - not the case yet (Phase 4, not
deployed).
"""

import time

_store = {}
# Long, since staleness is handled by invalidate_all() on every /manage or
# /upload write (event-driven), not by this TTL - it's only a safety net for
# anything that mutates data outside those two paths. A short TTL just meant
# re-paying a full Neon round trip (measured ~150-300ms each) for pages Adi
# had already visited minutes earlier - part of the "still very slow"
# report, 2026-08-25, alongside the redundant-query fix in dashboard.py.
DEFAULT_TTL = 3600  # seconds


def get_or_set(key, compute, ttl=DEFAULT_TTL):
    now = time.monotonic()
    cached = _store.get(key)
    if cached is not None and now - cached[1] < ttl:
        return cached[0]
    value = compute()
    _store[key] = (value, now)
    return value


def invalidate_all():
    _store.clear()
