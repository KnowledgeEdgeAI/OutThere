# OutThere backend

**Current implementation: v1 compatibility plus the v2 server core.** The server now implements accounts, shared planning/sync, temporary chat and attachments, albums, splits, coordination, Ripple, discovery, safety, sharing and provider adapters. See [implementation and verification limits](docs/v2-status.md) and [exact inputs](docs/v2-contracts.json). The mobile product screens still require v2 wiring; PostgreSQL and live external services remain unverified.

One Python application, one database, one small worker. This is the first working slice of the [backend design](../docs/backend/design.md).

**Working:** invitation sign-in, rotating sessions, private circles, plans, RSVPs, plan chat, reconnect replay, and automatic room archiving. Optional place search is behind a provider interface.

## Run locally

Install Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/). These commands work in macOS, Linux, and Windows terminals, without activating a virtual environment:

```sh
cd backend
uv sync --locked --python 3.12
uv run alembic upgrade head
uv run outthere serve --reload
```

In another terminal, from `backend/`:

```sh
uv run outthere worker
```

Defaults work without configuration. To customize, copy `.env.example` to `.env` using your editor. SQLite data stays in `backend/data/`. Run commands from this directory so the server, migrations, and worker use the same database.

- Health: <http://127.0.0.1:8000/health>
- HTTP API docs: <http://127.0.0.1:8000/docs>
- WebSocket: `ws://127.0.0.1:8000/v1/ws` — [protocol](docs/protocol.md)

Create a one-use sign-in invitation for each tester:

```sh
uv run outthere invite
```

The printed token expires in 24 hours. Exchange it through the HTTP API with a display name. To sign into an existing account, issue `outthere invite --user-id <UUID>`; a fresh unbound invitation creates a new account.

For a complete two-person walkthrough, create two invitations, then run:

```sh
uv run python examples/two_people.py
```

It prompts for the invitations, creates a circle and plan, sends an RSVP and message, and verifies replay after reconnecting. It writes demo data to the running server.

## Where things live

| Part | Job |
|---|---|
| `main.py`, `contracts.py` | HTTP / WebSocket transport and validated inputs |
| `auth.py`, `people.py` | Sessions, circle ownership, invitations and membership |
| `plans.py`, `rooms.py` | Plan audience, RSVP conflicts, ordered private chat |
| `service.py`, `events.py` | Command deduplication, queries, durable per-user change feeds |
| `models.py`, `db.py`, `migrations/` | Relational schema, transactions and schema upgrades |
| `worker.py` | Leased jobs; archive plan rooms 24 hours after their end |
| `discovery.py`, `integrations/` | Pure geo compatibility rules and optional place search |

Each command commits its data, receipt, and change references together. Only then does it acknowledge success. WebSocket delivery reads that durable feed; a disconnected client resumes from its last saved cursor. Chat bodies live in the database; the future frontend will keep a local copy and an outgoing queue.

## Keep the first deployment small

SQLite is for one host and modest write traffic. PostgreSQL is the intended shared database when adding application instances:

```sh
uv sync --locked --extra postgres
```

Set `OUTTHERE_DATABASE_URL` to a `postgresql+psycopg://…` URL and run migrations. This creates a schema; it does **not** transfer existing SQLite data. PostgreSQL compatibility is designed into the code but has not yet been integration-tested.

Run one server and one worker initially. TLS termination provides HTTPS/WSS outside local development. Polling costs roughly one feed query cycle per connected user per second; add a shared wake-up channel only when measurements justify it. The database feed remains the recovery path.

An optional Dockerfile uses the same commands. Run migrations as a separate release step; run server and worker separately with the same database configuration. The container has not yet been built here.

## Check and continue

```sh
uv run pytest -q
uv run ruff check .
uv run alembic check
```

Tests cover private access, replay, concurrent retries, RSVP conflicts, session revocation, job recovery, geo rules, mocked maps, and migration rollback/reapply. Verified locally on macOS / Python 3.12; Windows, Linux, and PostgreSQL still need runtime checks.

Current verification: see [v2 status](docs/v2-status.md) for the expanded test coverage and deployment limits. The two-user example also passed against a real local HTTP/WebSocket server and a freshly migrated database. The test client emits one upstream HTTPX deprecation warning.

Remaining integration work:

1. Connect the mobile product screens to v2 metadata sync and temporary delivery.
2. Verify PostgreSQL concurrency and deploy shared private storage.
3. Configure Maps/APNs/FCM credentials, verify real devices, and test backups and monitoring.

The legacy v1 permanent feed/message behavior is preserved for v1 clients. V2 temporary retention does not erase those legacy messages or existing backups. Read [v2 status](docs/v2-status.md) before public deployment.

## V2 accounts

`/v2/ws` implements the server event catalog listed in [v2 status](docs/v2-status.md), including phone login/resume/refresh/logout, profile read/update, device list/revoke and ping. Payloads forbid unknown fields. [Exact input schemas](docs/v2-contracts.json) and [implementation notes](docs/v2-status.md) document the current boundary. Authentication results advertise the supported capabilities. V2 tokens cannot call the v1 API.

After migrating, configure `.env` with `OUTTHERE_AUTH_MODE=unverified_phone`, a stable `OUTTHERE_AUTH_RETRY_KEY`, and allowed browser origins including the Expo development URL. Generate the key locally with:

```sh
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep the key out of source control. This mode is explicitly for the agreed prototype: entering a phone does not prove ownership. The default disables phone login. Existing invitation accounts keep their IDs and have no invented phone association. Run the worker as well as the server to clean expired encrypted renewal records and action receipts while idle.

A durable account command contains a stable UUID `action_id` and offset-aware `issued_at`. Profile updates include `expected_version`. The server rejects an intent after seven days, even if its receipt has been cleaned. Retry unchanged intents after unknown outcomes; refresh/review expired or conflicting edits before generating a new intent.

Verified locally: account/session integration, lost refresh response, concurrent mutation retries, wrong-device rejection, live revocation, v1/v2 isolation, strict envelope errors, worker cleanup, schema drift, and seeded legacy migration up/down/up. PostgreSQL concurrency and physical-device runtime remain to be verified before deployment.
