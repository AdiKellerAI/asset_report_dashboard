---
name: local-dev-stack
description: Use when starting the Flask dev server, running the test suite, or working with the local Postgres container for this repo - docker-compose.yml, the venv, or anything Python-environment related on this Mac.
---

# Local dev stack

## Python environment gotcha (read this first)

Homebrew's Python 3.12/3.13 on this Mac link against a newer `libexpat` than what's
actually on this machine's very new macOS build (26.0.1) - this breaks `platform.mac_ver()`,
which breaks `plistlib`, which crashes **pip itself** (via its `truststore` SSL module) on
any install, in or out of a venv. Fixed by:

```
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib"
```

Already added to `~/.zshrc`, so new interactive shells have it automatically. If a
command run by Claude Code's Bash tool fails with `ValueError: invalid literal for int()
with base 10: ''` or a pip/ensurepip crash, that env var is missing from the shell -
export it inline for the command rather than assuming it's inherited.

The venv itself lives at `.venv/` (gitignored), created with
`/opt/homebrew/bin/python3.12 -m venv .venv`, all deps from `requirements.txt` installed.

## Running the app

```
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib"
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5433/asset_report_dashboard_test"   # or the real Neon URL once handed over
.venv/bin/python wsgi.py
```

Per the `developer-preferences` skill: **always actually load the page in a browser
(or curl it) before calling a UI-touching branch done** - not just green tests.

## Local Postgres for tests (docker-compose.yml)

A Postgres 16 container, port **5433** (not 5432, to avoid clashing with anything else),
db `asset_report_dashboard_test`, user/pass `postgres`/`postgres` - entirely separate from
the real Neon instance.

```
docker compose up -d db          # start
docker compose exec -T db psql -U postgres -d asset_report_dashboard_test -c "\dt"   # inspect
docker compose down               # stop + remove when done
```

## Running migrations + seed data

```
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib"
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5433/asset_report_dashboard_test"
.venv/bin/alembic upgrade head
export FLASK_APP=wsgi.py
.venv/bin/flask seed-db
```

## Running tests

`tests/conftest.py` runs Alembic migrations against `TEST_DATABASE_URL` (defaults to the
same local container above) once per test session, and truncates all tables after each
test - no manual setup needed beyond having the container running.

```
docker compose up -d db
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib"
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5433/asset_report_dashboard_test"
export TEST_DATABASE_URL="$DATABASE_URL"
.venv/bin/python -m pytest -q
docker compose down
```

## Common issues

- Forgetting `DYLD_LIBRARY_PATH` in a non-interactive/tool-invoked shell → pip or any
  `platform.mac_ver()`-touching code crashes. See above.
- Connecting to port 5432 by habit instead of **5433** - this repo's test container
  intentionally uses a non-default port.
- The real `DATABASE_URL` (new database on the GCP Cloud SQL instance shared with the
  `maayan_recipes` project - see the `postgres-instance` memory) has not been handed
  over yet as of Phase 1 - schema/migrations have only been verified against the
  local container so far. Don't assume it's configured.
