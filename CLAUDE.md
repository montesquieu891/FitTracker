# FitTrack

> Gamified fitness platform: earn points from tracked workouts, spend them on sweepstakes tickets for prize drawings.

## Overview

FitTrack transforms fitness activity into a competitive, rewarding experience. Users connect fitness trackers (Google Fit, Fitbit), earn points from physical activities, and spend those points on sweepstakes tickets for daily/weekly/monthly/annual prize drawings. Users compete within 30 demographic-based tiers (age × sex × fitness level) on leaderboards. Revenue comes from premium subscriptions and sponsor partnerships. MVP is a responsive web app targeting US adults (18+) in sweepstakes-compliant states.

## Tech Stack

| Component    | Choice                    | Why (if non-obvious)                                               |
| ------------ | ------------------------- | ------------------------------------------------------------------ |
| Language     | Python 3.12               | -                                                                  |
| Framework    | FastAPI                   | Async, auto OpenAPI docs, Pydantic validation                      |
| Database     | Oracle 23ai Free (dev)    | PRD mandates Oracle Autonomous JSON DB; 23ai Free for local Docker |
| DB Driver    | python-oracledb (thin)    | Direct driver, no ORM — use connection pooling                     |
| Auth         | JWT (RS256) + OAuth 2.0   | Social login (Google, Apple) included in MVP                       |
| Frontend     | React 18 + Vite           | Responsive SPA; separate admin UI                                  |
| Cache        | Redis (OCI Cache in prod) | Session management, leaderboard caching                            |
| Queue        | OCI Queue (prod)          | Async job processing (sync, drawings)                              |
| Migrations   | Alembic                   | Schema versioning                                                  |
| Testing      | pytest + Hypothesis       | Property-based tests for points/tier logic                         |
| CI/CD        | GitHub Actions            | Lint → Build → Test → Deploy                                      |
| IaC          | Terraform                 | OCI resource provisioning                                          |
| Containers   | Docker + Docker Compose   | Local dev environment                                              |

## Database Requirements

**CRITICAL**: Use `python-oracledb` driver directly — no SQLAlchemy ORM, no other databases in application code.

- Relational tables with JSON columns where appropriate (per PRD Section 7)
- JSON Duality Views for document-style access patterns
- Functional indexes on queried JSON paths
- Connection pooling via `oracledb.create_pool()`
- Oracle 23ai Free in Docker for local dev (`container-registry.oracle.com/database/free:latest`)
- Redis for caching only (sessions, leaderboards) — not as primary data store

## Project Layout

```
src/fittrack/
├── api/              # FastAPI routers, request/response schemas
│   ├── routes/       # 20 route modules (97 endpoints)
│   ├── schemas/      # Pydantic models for API contracts
│   ├── deps.py       # Dependency injection (auth, db pool)
│   └── middleware.py  # Rate limiting, security headers, CORS, compression
├── services/         # Business logic layer
│   ├── auth.py       # JWT, password hashing, OAuth
│   ├── points.py     # Points calculation engine
│   ├── drawings.py   # Sweepstakes execution, CSPRNG
│   ├── sync.py       # Fitness tracker sync orchestration
│   └── leaderboard.py
├── repositories/     # Data access layer (python-oracledb queries)
├── workers/          # Background jobs (sync, leaderboard refresh)
├── models/           # Domain models / dataclasses
├── core/             # Config, security, constants
│   ├── config.py     # Settings from env vars
│   ├── security.py   # JWT encode/decode, password hashing
│   ├── constants.py  # Point rates, tier codes, eligible states
│   ├── logging.py    # Structured logging (text/JSON)
│   └── context.py    # Request correlation ID context
└── main.py           # FastAPI app factory

tests/
├── unit/             # 1,174 tests (service logic, routes, schemas)
├── integration/      # DB + API tests with Oracle container
├── factories/        # Synthetic data generators (Faker)
└── conftest.py       # Shared fixtures, DB setup

deploy/
├── helm/fittrack/    # Kubernetes Helm charts
└── terraform/        # OCI infrastructure (VCN, ADB, OKE, Redis, Queue)

static/
└── test_page.html    # Dev-only API tester / data viewer

docs/                 # PRD, deployment, environment vars, rate limits, backup
migrations/           # Alembic migration scripts
scripts/              # Seed data, utility scripts
docker/               # Dockerfiles (dev + prod), docker-compose.yml
```

## Domain Concepts

| Term               | Meaning                                                                    |
| ------------------ | -------------------------------------------------------------------------- |
| Tier               | Competition bracket: `{sex}-{age_bracket}-{fitness_level}` (30 combos)    |
| Tier Code          | E.g. `M-18-29-BEG` = Male, 18-29, Beginner                               |
| Points Earned      | Cumulative total (used for leaderboard rank) — never decreases             |
| Point Balance      | Spendable points (earned minus spent) — used to buy tickets               |
| Drawing            | A sweepstakes event (daily/weekly/monthly/annual) with tickets and prizes  |
| Ticket             | Entry into a drawing, purchased with points                                |
| Active Minutes     | Minutes of physical activity at light/moderate/vigorous intensity          |
| Fulfillment        | Workflow for delivering a prize to a winner                                |
| Connection         | OAuth link between a user and a fitness tracker provider                   |

## Key Business Rules

- **Age gate**: Users must be 18+. DOB validated at registration, cannot be changed.
- **State eligibility**: NY, FL, RI excluded from MVP (sweepstakes law). Validated at registration.
- **Daily point cap**: 1,000 points/day maximum per user.
- **Workout bonus cap**: Max 3 workout bonuses (50 pts each) per day.
- **Points don't expire**, can't be transferred, have no cash value.
- **Ticket purchases are final** — no refunds to point balance.
- **Ticket sales close 5 minutes before drawing time.**
- **Drawing winner selection**: CSPRNG-based, immutable audit trail, no manual editing of results.
- **Prize forfeit**: Winners have 14 days to confirm address (7-day warning).
- **Tier assignment**: Computed from profile fields — stored as `tier_code` on profile, recalculated on profile change.
- **Leaderboard rank**: Based on points *earned* (not balance) within period. Ties broken by: earliest achievement → more active days → user_id.
- **Duplicate activity detection**: Same user + type + overlapping time window. Priority: primary tracker → most detailed → first received.

## Entities

- **User**: Account with email auth + social login, role (user/premium/admin), point balance, status
- **Profile**: Demographics (age bracket, sex, fitness level), tier code, display name, goals
- **TrackerConnection**: OAuth tokens for Google Fit / Fitbit, sync status
- **Activity**: Normalized fitness event (steps/workout/active_minutes) with metrics JSON
- **PointTransaction**: Ledger entry (earn/spend/adjust) with running balance
- **Drawing**: Sweepstakes event with type, schedule, ticket cost, status workflow
- **Ticket**: User's entry in a drawing, linked to purchase transaction
- **Prize**: Reward item in a drawing, linked to sponsor
- **PrizeFulfillment**: Delivery workflow (pending → notified → confirmed → shipped → delivered)
- **Sponsor**: Company providing prizes (name, contact, logo, status)

## API Patterns

- All responses use RFC 7807 Problem Details for errors
- Pagination: `?page=1&limit=20` → response includes `pagination` object
- Versioned: `/api/v1/...`
- Auth: `Authorization: Bearer <JWT>` header
- Admin endpoints under `/api/v1/admin/...` require `role: admin` in JWT
- All timestamps in ISO 8601 UTC
- UUIDs for all entity IDs (Oracle `RAW(16)` with `SYS_GUID()`)

## Commands

```bash
make setup            # First-time setup (Docker, deps, DB init)
make dev              # Start Docker services + API server
make test             # Run full test suite
make test-unit        # Unit tests only
make test-integration # Integration tests (requires Oracle container)
make db-migrate       # Run pending migrations
make db-seed          # Generate synthetic data
make db-reset         # Drop + recreate + seed
make lint             # ruff + mypy
make format           # ruff format
```

## Gotchas

- **Point balance requires optimistic locking** — concurrent ticket purchases can race. Use a version column on `users.point_balance` or `SELECT ... FOR UPDATE`.
- **Tier code is computed**, not user-selected — always derive from `(biological_sex, age_bracket, fitness_level)`. Never trust client-sent tier codes.
- **Oracle 23ai Free Docker image** is ~3GB and takes 60-90 seconds to start. Account for this in CI timeout settings.
- **python-oracledb thin mode** doesn't need Oracle Client libraries. Use thin mode for simplicity, thick mode only if you need Advanced Queuing.
- **Oracle JSON columns**: Use `IS JSON` check constraint. Query with `JSON_VALUE()`, `JSON_EXISTS()`, `JSON_TABLE()`.
- **Drawing execution must be idempotent** — if the process crashes mid-draw, re-running should produce the same result (snapshot tickets first, then select from snapshot).
- **OAuth token refresh** happens proactively in the sync worker — don't wait for 401 errors.
- **Eligible states list** is defined in code (`core/constants.py`) and validated at registration. The excluded list (NY, FL, RI) will be finalized by Legal before launch.

## Constraints

- MVP: US only, 18+, excludes NY/FL/RI (sweepstakes compliance)
- MVP: Web only — no native mobile apps
- MVP: Google Fit + Fitbit only (Apple Health deferred to v1.1)
- MVP: 15-minute batch sync (not real-time)
- MVP: Manual prize fulfillment by admin (no automation)
- MVP: Premium subscriptions only (no ads)
- Daily point cap: 1,000 points/user/day
- OAuth session: single active session per device

## References

- PRD: `docs/FitTrack-PRD-v1.0.md`
- Deployment: `docs/DEPLOYMENT.md` (blue-green process, rollback)
- Environment Variables: `docs/ENVIRONMENT_VARIABLES.md`
- Rate Limits: `docs/RATE_LIMITS.md`
- Backup & Recovery: `docs/BACKUP_RECOVERY.md`
- API Docs: `/docs` (FastAPI Swagger UI when running)
- Oracle 23ai JSON docs: https://docs.oracle.com/en/database/oracle/oracle-database/23/adjsn/
