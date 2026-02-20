# Implementation Plan: FitTrack

## Executive Summary

FitTrack is a gamified fitness platform where users earn points from tracked physical activities and spend them on sweepstakes tickets for prize drawings. The platform targets US adults (18+) in sweepstakes-compliant states, delivered as a responsive web application built on Python/FastAPI with Oracle 23ai and React 18.

The implementation is organized into **8 checkpoints**, progressing from foundational infrastructure through core business workflows to production readiness. Each checkpoint builds incrementally on the previous, delivering demonstrable value at every stage.

**Key technical decisions:**
- Oracle 23ai with relational tables + JSON Duality Views, accessed via python-oracledb (no ORM)
- JWT (RS256) authentication with Google + Apple social login in MVP
- Google Fit + Fitbit tracker integrations (Apple Health deferred to v1.1)
- 15-minute batch sync for activity data
- 30 demographic competition tiers (no Open tier in MVP)
- CSPRNG-based drawing execution with immutable audit trails
- Redis for caching (sessions, leaderboards)

**Major risks:** Oracle 23ai Docker image startup time in CI, fitness API rate limits at scale, sweepstakes legal compliance across states, and drawing integrity requirements demanding rigorous audit trails.

---

## Checkpoint Overview

| Checkpoint | Title                                    | Dependencies | Est. Effort |
| ---------- | ---------------------------------------- | ------------ | ----------- |
| 1          | Foundation: Environment & Data Layer     | None         | 2 weeks     |
| 2          | Authentication & Authorization           | CP1          | 1.5 weeks   |
| 3          | User Profiles & Competition Tiers        | CP2          | 1 week      |
| 4          | Activity Tracking & Points System        | CP3          | 2 weeks     |
| 5          | Leaderboards & Rankings                  | CP4          | 1 week      |
| 6          | Sweepstakes & Prize System               | CP4          | 2 weeks     |
| 7          | Admin Dashboard & Notifications          | CP5, CP6     | 1.5 weeks   |
| 8          | Production Readiness & Hardening         | CP7          | 1.5 weeks   |

---

## Detailed Checkpoint Specifications

---

## Checkpoint 1: Foundation — Environment & Data Layer

### Objective

Establish the complete development environment, database schema, data access layer, synthetic data generation, and CRUD API endpoints for all core entities. Deliver a functional test page that validates the data layer and API. This checkpoint proves the entire stack works end-to-end before building business logic.

### Prerequisites

- [x] Git repository created
- [x] PRD reviewed and architectural decisions finalized

### Deliverables

#### Infrastructure Deliverables

| Component              | Path / Tool                  | Description                                         |
| ---------------------- | ---------------------------- | --------------------------------------------------- |
| Docker Compose         | `docker/docker-compose.yml`  | Oracle 23ai Free + Redis containers                 |
| Dockerfile (API)       | `docker/Dockerfile`          | Python 3.12 FastAPI application image               |
| Makefile               | `Makefile`                   | All dev commands (setup, dev, test, db-*, lint, fmt) |
| Environment template   | `.env.example`               | All required env vars with safe defaults             |
| GitHub Actions CI      | `.github/workflows/ci.yml`   | Lint → Build → Test pipeline skeleton               |
| Python project config  | `pyproject.toml`             | Dependencies, ruff/mypy/pytest config               |
| Git ignore             | `.gitignore`                 | Python, Node, Docker, IDE patterns                   |

#### Code Deliverables

| Component             | Path                                | Description                                            |
| --------------------- | ----------------------------------- | ------------------------------------------------------ |
| App factory           | `src/fittrack/main.py`              | FastAPI app with lifespan, middleware, router includes  |
| Config                | `src/fittrack/core/config.py`       | Pydantic Settings from env vars                        |
| Constants             | `src/fittrack/core/constants.py`    | Point rates, tier codes, eligible states, drawing types |
| DB connection pool    | `src/fittrack/core/database.py`     | python-oracledb pool init/shutdown                     |
| Base repository       | `src/fittrack/repositories/base.py` | Common CRUD patterns (get, list, create, update, delete)|
| User repository       | `src/fittrack/repositories/users.py`| User CRUD operations                                   |
| Profile repository    | `src/fittrack/repositories/profiles.py`| Profile CRUD with tier code computation             |
| Connection repository | `src/fittrack/repositories/connections.py`| Tracker connection CRUD                           |
| Activity repository   | `src/fittrack/repositories/activities.py`| Activity CRUD with pagination/filtering            |
| Transaction repository| `src/fittrack/repositories/transactions.py`| Point transaction CRUD                           |
| Drawing repository    | `src/fittrack/repositories/drawings.py`| Drawing CRUD with status management                |
| Ticket repository     | `src/fittrack/repositories/tickets.py`| Ticket CRUD                                        |
| Prize repository      | `src/fittrack/repositories/prizes.py`| Prize CRUD                                          |
| Fulfillment repository| `src/fittrack/repositories/fulfillments.py`| Prize fulfillment CRUD                          |
| Sponsor repository    | `src/fittrack/repositories/sponsors.py`| Sponsor CRUD                                      |
| API schemas           | `src/fittrack/api/schemas/`         | Pydantic models for all entity request/response types  |
| Health route          | `src/fittrack/api/routes/health.py` | `/health` and `/health/db` endpoints                   |
| Entity CRUD routes    | `src/fittrack/api/routes/`          | CRUD routes for all entities (unprotected in CP1)      |
| Error handling        | `src/fittrack/api/middleware.py`     | RFC 7807 error handler                                |
| Dependencies          | `src/fittrack/api/deps.py`          | DB pool injection, pagination params                  |

#### Database Deliverables

| Item                        | Description                                                      |
| --------------------------- | ---------------------------------------------------------------- |
| Migration: 001_initial      | Create all 10 tables: users, profiles, tracker_connections, activities, point_transactions, drawings, tickets, prizes, prize_fulfillments, sponsors |
| Migration: 002_indexes      | All indexes from PRD Section 7.2                                 |
| Migration: 003_duality_views| JSON Duality View for user_profile_dv                            |

#### Synthetic Data Deliverables

| Component          | Path                               | Description                                        |
| ------------------ | ---------------------------------- | -------------------------------------------------- |
| User factory       | `tests/factories/user_factory.py`  | Generate realistic users (all roles, statuses)     |
| Profile factory    | `tests/factories/profile_factory.py`| Profiles across all 30 tiers                      |
| Activity factory   | `tests/factories/activity_factory.py`| Activities with realistic metrics and timestamps |
| Drawing factory    | `tests/factories/drawing_factory.py`| Drawings in all statuses and types                |
| Sponsor factory    | `tests/factories/sponsor_factory.py`| Sponsors with contact info                        |
| Full seed script   | `scripts/seed_data.py`            | Orchestrates factories to populate realistic dataset|

**Seed Data Targets:**
- 50 regular users, 10 premium users, 3 admin users (spread across all 30 tiers)
- 15+ activities per user (varied types, intensities, dates)
- Point transactions matching activity history
- 5 sponsors with logos
- 30 drawings (mix of completed, open, scheduled) with prizes
- Tickets distributed across users and drawings
- 10 prize fulfillments in various workflow states

#### API Endpoints (CP1)

| Method | Path                           | Description                     | Auth |
| ------ | ------------------------------ | ------------------------------- | ---- |
| GET    | `/health`                      | Basic health check              | No   |
| GET    | `/health/db`                   | Database connectivity check     | No   |
| GET    | `/api/v1/users`                | List users (paginated)          | No*  |
| POST   | `/api/v1/users`                | Create user                     | No*  |
| GET    | `/api/v1/users/{id}`           | Get user by ID                  | No*  |
| PUT    | `/api/v1/users/{id}`           | Update user                     | No*  |
| DELETE | `/api/v1/users/{id}`           | Delete user                     | No*  |
| GET    | `/api/v1/profiles`             | List profiles                   | No*  |
| POST   | `/api/v1/profiles`             | Create profile                  | No*  |
| GET    | `/api/v1/profiles/{id}`        | Get profile                     | No*  |
| PUT    | `/api/v1/profiles/{id}`        | Update profile                  | No*  |
| GET    | `/api/v1/connections`          | List connections                | No*  |
| POST   | `/api/v1/connections`          | Create connection               | No*  |
| GET    | `/api/v1/activities`           | List activities (filterable)    | No*  |
| POST   | `/api/v1/activities`           | Create activity                 | No*  |
| GET    | `/api/v1/transactions`         | List point transactions         | No*  |
| POST   | `/api/v1/transactions`         | Create transaction              | No*  |
| GET    | `/api/v1/drawings`             | List drawings (filterable)      | No*  |
| POST   | `/api/v1/drawings`             | Create drawing                  | No*  |
| GET    | `/api/v1/drawings/{id}`        | Get drawing detail              | No*  |
| PUT    | `/api/v1/drawings/{id}`        | Update drawing                  | No*  |
| GET    | `/api/v1/tickets`              | List tickets                    | No*  |
| POST   | `/api/v1/tickets`              | Create ticket                   | No*  |
| GET    | `/api/v1/prizes`               | List prizes                     | No*  |
| POST   | `/api/v1/prizes`               | Create prize                    | No*  |
| GET    | `/api/v1/sponsors`             | List sponsors                   | No*  |
| POST   | `/api/v1/sponsors`             | Create sponsor                  | No*  |
| GET    | `/api/v1/sponsors/{id}`        | Get sponsor                     | No*  |
| PUT    | `/api/v1/sponsors/{id}`        | Update sponsor                  | No*  |
| GET    | `/api/v1/fulfillments`         | List fulfillments               | No*  |
| PUT    | `/api/v1/fulfillments/{id}`    | Update fulfillment              | No*  |

\* Auth is deferred to Checkpoint 2. All endpoints are unprotected in CP1.

#### Test Page Deliverable

| Component      | Path                    | Description                                       |
| -------------- | ----------------------- | ------------------------------------------------- |
| Test HTML page | `static/test_page.html` | Single-page dev tool served at `/test` (dev only) |

**Test Page Features:**
- API endpoint browser with forms for all CRUD operations
- Entity data viewer with sortable/filterable tables
- Database seed button (calls `POST /api/v1/dev/seed`)
- Database reset button (calls `POST /api/v1/dev/reset`)
- Health check status indicators
- Response time display for each request
- Raw JSON response viewer
- Sample reports: user count by tier, point distribution, drawing statistics

#### Test Deliverables

| Test Suite              | Path                                      | Coverage Target |
| ----------------------- | ----------------------------------------- | --------------- |
| Repository unit tests   | `tests/integration/test_*_repository.py`  | >90%            |
| API endpoint tests      | `tests/integration/test_*_routes.py`      | >85%            |
| Factory validation      | `tests/unit/test_factories.py`            | 100%            |
| Schema validation       | `tests/unit/test_schemas.py`              | >90%            |
| Database connectivity   | `tests/integration/test_database.py`      | 100%            |
| Health endpoint         | `tests/integration/test_health.py`        | 100%            |

### Acceptance Criteria

```gherkin
Feature: Development Environment Setup

  Scenario: Fresh clone setup
    Given a developer clones the repository
    When they run `make setup && make dev`
    Then Docker containers start (Oracle 23ai Free, Redis)
    And the API server starts on port 8000
    And `/health` returns 200 with status "ok"
    And `/health/db` returns 200 confirming Oracle connectivity

Feature: Database Schema

  Scenario: All tables created
    Given the dev environment is running
    When database migrations have run
    Then all 10 entity tables exist with correct constraints
    And all indexes are created
    And the JSON Duality View is functional

Feature: Synthetic Data

  Scenario: Seed data generation
    Given the database is empty
    When the developer runs `make db-seed`
    Then 63 users are created (50 regular + 10 premium + 3 admin)
    And profiles span all 30 competition tiers
    And each user has 15+ activity records
    And point transactions reconcile with activities
    And 30 drawings exist across all types and statuses
    And 5 sponsors with prizes are created

Feature: CRUD API Endpoints

  Scenario: Entity CRUD operations
    Given seed data exists in the database
    When a GET request is made to any entity list endpoint
    Then a paginated JSON response is returned
    When a POST request creates a new entity
    Then the entity is persisted and returned with an ID
    When a PUT request updates an entity
    Then the changes are persisted
    When a GET request fetches by ID
    Then the correct entity is returned

Feature: Test Page

  Scenario: Test page functionality
    Given the dev server is running
    When a developer navigates to `/test`
    Then the test page loads with forms for all entity endpoints
    And the seed/reset buttons are functional
    And entity data tables display with sample reports
```

### Security Considerations

- No authentication in CP1 (deferred to CP2)
- Test page and dev endpoints (`/api/v1/dev/*`) disabled in production via environment check
- `.env` file excluded from version control; `.env.example` has safe defaults
- Database credentials use non-default values even in dev
- No real PII in seed data (all generated via Faker)

### Definition of Done

- [ ] `make setup && make dev` works from fresh clone in <15 minutes
- [ ] Oracle 23ai Free container starts and accepts connections
- [ ] All 10 tables created with correct schema, constraints, and indexes
- [ ] All repositories implement CRUD operations
- [ ] All API endpoints return correct responses with pagination
- [ ] `make db-seed` generates complete, realistic test data
- [ ] Test page at `/test` demonstrates all CRUD operations and shows sample reports
- [ ] All tests passing: repository >90%, API >85%, factories 100%
- [ ] `make lint` passes (ruff + mypy)
- [ ] CI pipeline runs lint and tests on push
- [ ] README.md documents setup process (<15 min from clone to running)
- [ ] CLAUDE.md is in the repository root

---

## Checkpoint 2: Authentication & Authorization

### Objective

Implement complete authentication system with email registration, social login (Google, Apple), JWT token management, and role-based access control. All previously unprotected endpoints become secured with appropriate authorization rules.

### Prerequisites

- [x] Checkpoint 1 completed
- [x] Google OAuth 2.0 client credentials obtained
- [x] Apple Sign-In service configured

### Deliverables

#### Code Deliverables

| Component            | Path                                        | Description                                        |
| -------------------- | ------------------------------------------- | -------------------------------------------------- |
| Security utilities   | `src/fittrack/core/security.py`             | JWT encode/decode (RS256), password hashing (argon2)|
| Auth service         | `src/fittrack/services/auth.py`             | Registration, login, token refresh, social login    |
| Auth routes          | `src/fittrack/api/routes/auth.py`           | `/auth/*` endpoints                                |
| Auth dependencies    | `src/fittrack/api/deps.py`                  | `get_current_user`, `require_role`, `require_admin` |
| RBAC middleware       | `src/fittrack/api/middleware.py`            | Role-based route protection                        |
| Email service (stub) | `src/fittrack/services/email.py`            | Verification emails (console output in dev)        |
| OAuth providers      | `src/fittrack/services/oauth_providers.py`  | Google + Apple OAuth token verification            |

#### Database Deliverables

| Item                         | Description                                         |
| ---------------------------- | --------------------------------------------------- |
| Migration: 004_auth          | Add `verification_token`, `reset_token` columns to users; add `oauth_accounts` table |
| Migration: 005_sessions      | Create `sessions` table for refresh token tracking  |

#### API Endpoints

| Method | Path                    | Description                        | Auth     |
| ------ | ----------------------- | ---------------------------------- | -------- |
| POST   | `/auth/register`        | Email registration with validation | No       |
| POST   | `/auth/login`           | Email/password login               | No       |
| POST   | `/auth/refresh`         | Refresh access token               | Refresh  |
| POST   | `/auth/verify-email`    | Verify email with token            | No       |
| POST   | `/auth/forgot-password` | Initiate password reset            | No       |
| POST   | `/auth/reset-password`  | Complete password reset             | No       |
| POST   | `/auth/social/google`   | Google OAuth login/register        | No       |
| POST   | `/auth/social/apple`    | Apple Sign-In login/register       | No       |
| POST   | `/auth/logout`          | Invalidate refresh token           | Yes      |
| POST   | `/auth/logout-all`      | Invalidate all sessions            | Yes      |

#### Test Deliverables

| Test Suite                | Path                                    | Coverage Target |
| ------------------------- | --------------------------------------- | --------------- |
| Auth service tests        | `tests/unit/test_auth_service.py`       | >90%            |
| Security utility tests    | `tests/unit/test_security.py`           | >95%            |
| Auth route tests          | `tests/integration/test_auth_routes.py` | >90%            |
| RBAC tests                | `tests/integration/test_rbac.py`        | >90%            |
| Password validation tests | `tests/unit/test_password.py`          | 100%            |
| Age/state validation      | `tests/unit/test_registration.py`      | 100%            |

### Acceptance Criteria

```gherkin
Feature: User Registration

  Scenario: Successful email registration
    Given a new user with valid email, password (12+ chars with complexity), DOB (18+), and eligible state
    When they POST to /auth/register
    Then a 201 response returns with userId
    And a verification email is generated
    And the user status is "pending"

  Scenario: Registration rejected for underage user
    Given a user with DOB indicating age < 18
    When they POST to /auth/register
    Then a 400 response returns with clear error message

  Scenario: Registration rejected for ineligible state
    Given a user from NY, FL, or RI
    When they POST to /auth/register
    Then a 400 response returns explaining sweepstakes ineligibility

Feature: Authentication

  Scenario: JWT login flow
    Given a verified user with known credentials
    When they POST to /auth/login
    Then a 200 response returns with accessToken (1h) and refreshToken (30d)

  Scenario: Social login (Google)
    Given a valid Google OAuth code
    When they POST to /auth/social/google
    Then an account is created or matched and tokens are returned

  Scenario: Account lockout
    Given a user fails login 5 times
    When they attempt a 6th login
    Then a 429 response returns indicating 15-minute lockout

Feature: Authorization

  Scenario: Protected endpoint access
    Given a user with role "user"
    When they access an admin endpoint
    Then a 403 response is returned
    When they access a user endpoint with valid JWT
    Then the request succeeds
```

### Security Considerations

- Passwords hashed with Argon2id (memory-hard)
- JWT signed with RS256 (asymmetric — public key for verification only)
- Refresh tokens stored hashed in database
- Rate limiting: 5 login attempts per 15 minutes per IP
- CSRF protection via SameSite cookies
- All previous CRUD endpoints now require authentication
- Admin endpoints require `role: admin`
- Account lockout with progressive backoff

### Definition of Done

- [ ] Email registration with all validations (age, state, password complexity)
- [ ] Email verification flow functional
- [ ] JWT login/refresh/logout working
- [ ] Google and Apple social login working
- [ ] RBAC enforced on all endpoints
- [ ] Account lockout after 5 failed attempts
- [ ] Password reset flow complete
- [ ] All CP1 endpoints require authentication
- [ ] Test page updated with login form
- [ ] All tests passing with required coverage
- [ ] No secrets in codebase

---

## Checkpoint 3: User Profiles & Competition Tiers

### Objective

Implement fitness profile completion flow, automatic tier assignment from profile attributes, and tier-based user querying. Users must complete their profile before accessing main features.

### Prerequisites

- [x] Checkpoint 2 completed (authenticated users exist)

### Deliverables

#### Code Deliverables

| Component          | Path                                          | Description                                  |
| ------------------ | --------------------------------------------- | -------------------------------------------- |
| Profile service    | `src/fittrack/services/profiles.py`           | Profile CRUD with tier computation           |
| Tier engine        | `src/fittrack/services/tiers.py`              | Tier code computation, tier metadata         |
| Profile routes     | `src/fittrack/api/routes/users.py`            | `/users/me/profile` endpoints                |
| Profile middleware | `src/fittrack/api/middleware.py`              | Profile completion check gate                |

#### API Endpoints

| Method | Path                        | Description                       | Auth |
| ------ | --------------------------- | --------------------------------- | ---- |
| GET    | `/api/v1/users/me`          | Get current user with profile     | Yes  |
| PUT    | `/api/v1/users/me/profile`  | Create/update fitness profile     | Yes  |
| GET    | `/api/v1/users/{id}/public` | Get user's public profile         | Yes  |
| GET    | `/api/v1/tiers`             | List all tiers with user counts   | Yes  |
| GET    | `/api/v1/tiers/{code}`      | Get tier details                  | Yes  |

#### Test Deliverables

| Test Suite           | Path                                   | Coverage Target |
| -------------------- | -------------------------------------- | --------------- |
| Tier computation     | `tests/unit/test_tiers.py`             | 100%            |
| Profile service      | `tests/unit/test_profile_service.py`   | >90%            |
| Profile routes       | `tests/integration/test_profile_routes.py` | >85%        |
| Profile gate         | `tests/integration/test_profile_gate.py`   | 100%        |

### Acceptance Criteria

```gherkin
Feature: Fitness Profile

  Scenario: Profile completion with tier assignment
    Given an authenticated user without a profile
    When they PUT /users/me/profile with age_bracket, biological_sex, fitness_level
    Then a profile is created with computed tier_code (e.g. "M-30-39-INT")
    And the user can access main features

  Scenario: Profile update triggers tier recalculation
    Given a user with tier "F-30-39-BEG"
    When they update fitness_level to "intermediate"
    Then tier_code changes to "F-30-39-INT"

  Scenario: Profile gate blocks incomplete users
    Given an authenticated user without a profile
    When they access /activities or /drawings
    Then a 403 response directs them to complete their profile
```

### Definition of Done

- [ ] Profile CRUD functional with all fields from PRD
- [ ] Tier code computed automatically from profile attributes
- [ ] All 30 tier combinations work correctly
- [ ] Profile completion required before main feature access
- [ ] Public profile endpoint exposes only display name, tier, rank
- [ ] Tier listing with user counts functional
- [ ] All tests passing

---

## Checkpoint 4: Activity Tracking & Points System

### Objective

Implement fitness tracker OAuth connections (Google Fit, Fitbit), activity data normalization, the batch sync worker, and the complete points calculation engine with anti-gaming measures. This is the core value engine of the platform.

### Prerequisites

- [x] Checkpoint 3 completed (users have profiles and tiers)
- [x] Google Fit API developer account approved
- [x] Fitbit API developer account approved

### Deliverables

#### Code Deliverables

| Component             | Path                                           | Description                                     |
| --------------------- | ---------------------------------------------- | ----------------------------------------------- |
| Tracker service       | `src/fittrack/services/trackers.py`            | OAuth flow management, token storage             |
| Google Fit client     | `src/fittrack/services/providers/google_fit.py`| Google Fit API client with data fetching         |
| Fitbit client         | `src/fittrack/services/providers/fitbit.py`    | Fitbit API client with data fetching             |
| Provider base         | `src/fittrack/services/providers/base.py`      | Abstract provider interface                      |
| Normalizer            | `src/fittrack/services/normalizer.py`          | Convert provider data to internal Activity format|
| Sync worker           | `src/fittrack/workers/sync_worker.py`          | 15-min batch sync orchestrator                   |
| Points service        | `src/fittrack/services/points.py`              | Points calculation engine with rate table         |
| Anti-gaming service   | `src/fittrack/services/anti_gaming.py`         | Daily cap, workout cap, anomaly detection         |
| Connection routes     | `src/fittrack/api/routes/connections.py`       | Tracker OAuth flow endpoints                     |
| Activity routes       | `src/fittrack/api/routes/activities.py`        | Activity listing, summary                        |
| Points routes         | `src/fittrack/api/routes/points.py`            | Balance, transaction history                     |

#### Database Deliverables

| Item                        | Description                             |
| --------------------------- | --------------------------------------- |
| Migration: 006_daily_points | Add `daily_points_log` table for cap tracking |

#### API Endpoints

| Method | Path                                     | Description                 | Auth |
| ------ | ---------------------------------------- | --------------------------- | ---- |
| GET    | `/api/v1/connections`                    | List user's connections     | Yes  |
| POST   | `/api/v1/connections/{provider}/initiate`| Start OAuth flow            | Yes  |
| POST   | `/api/v1/connections/{provider}/callback`| Complete OAuth flow         | Yes  |
| DELETE | `/api/v1/connections/{provider}`         | Disconnect tracker          | Yes  |
| POST   | `/api/v1/connections/{provider}/sync`    | Force immediate sync        | Yes  |
| GET    | `/api/v1/activities`                     | List activities (filtered)  | Yes  |
| GET    | `/api/v1/activities/summary`             | Dashboard activity summary  | Yes  |
| GET    | `/api/v1/points/balance`                 | Current point balance       | Yes  |
| GET    | `/api/v1/points/transactions`            | Transaction history         | Yes  |

#### Test Deliverables

| Test Suite                  | Path                                        | Coverage Target |
| --------------------------- | ------------------------------------------- | --------------- |
| Points calculation          | `tests/unit/test_points.py`                 | 100%            |
| Points property tests       | `tests/unit/test_points_properties.py`     | Hypothesis      |
| Anti-gaming                 | `tests/unit/test_anti_gaming.py`            | 100%            |
| Data normalization          | `tests/unit/test_normalizer.py`             | >95%            |
| Sync worker                 | `tests/integration/test_sync_worker.py`     | >85%            |
| Connection routes           | `tests/integration/test_connection_routes.py`| >85%           |
| Activity routes             | `tests/integration/test_activity_routes.py` | >85%            |
| Provider mocks              | `tests/unit/test_providers.py`              | >90%            |

### Acceptance Criteria

```gherkin
Feature: Points Calculation

  Scenario: Steps points awarded correctly
    Given a user has synced 10,000 steps
    When points are calculated
    Then 100 points are earned (10 pts per 1,000 steps)
    And a 100-point daily goal bonus is awarded
    And total is capped at 1,000 points for the day

  Scenario: Workout bonus
    Given a user completes a 30-minute vigorous workout
    When points are calculated
    Then 90 active minute points (30 × 3) + 50 workout bonus = 140 points

  Scenario: Daily cap enforcement
    Given a user has already earned 950 points today
    When a new activity would earn 200 points
    Then only 50 points are awarded (capped at 1,000)

Feature: Tracker Connection

  Scenario: OAuth flow
    Given an authenticated user
    When they POST to /connections/fitbit/initiate
    Then an authorization URL is returned
    When the OAuth callback is received
    Then access and refresh tokens are stored (encrypted)
    And initial sync is triggered

Feature: Activity Sync

  Scenario: Batch sync
    Given users with connected trackers due for sync
    When the 15-minute sync worker runs
    Then new activities are fetched, normalized, and stored
    And duplicate activities are detected and skipped
    And points are calculated and awarded
```

### Security Considerations

- OAuth tokens encrypted with AES-256-GCM before database storage
- Proactive token refresh (refresh before expiry)
- Provider API keys stored in environment variables (OCI Vault in production)
- Force-sync endpoint rate limited (1 per 5 minutes per user)

### Definition of Done

- [ ] Google Fit OAuth flow works end-to-end
- [ ] Fitbit OAuth flow works end-to-end
- [ ] Activity data normalized to common format
- [ ] Sync worker processes users in 15-minute batches
- [ ] Duplicate activity detection working
- [ ] Points calculated correctly per PRD rate table
- [ ] Daily cap (1,000 pts) and workout cap (3/day) enforced
- [ ] Point balance updates atomically with optimistic locking
- [ ] Activity summary endpoint returns today/week/month stats
- [ ] Test page shows activity data and point balance
- [ ] All tests passing with Hypothesis property tests for points

---

## Checkpoint 5: Leaderboards & Rankings

### Objective

Implement tier-scoped leaderboards with daily/weekly/monthly/all-time periods, ranking calculation with tie-breaking rules, and Redis caching for leaderboard data.

### Prerequisites

- [x] Checkpoint 4 completed (users earn points from activities)

### Deliverables

#### Code Deliverables

| Component            | Path                                         | Description                              |
| -------------------- | -------------------------------------------- | ---------------------------------------- |
| Leaderboard service  | `src/fittrack/services/leaderboard.py`       | Ranking calculation, tie-breaking        |
| Leaderboard cache    | `src/fittrack/services/cache.py`             | Redis caching for rankings               |
| Leaderboard worker   | `src/fittrack/workers/leaderboard_worker.py` | Periodic recalculation (every 15 min)    |
| Leaderboard routes   | `src/fittrack/api/routes/leaderboards.py`    | Leaderboard API endpoints                |

#### API Endpoints

| Method | Path                             | Description                    | Auth |
| ------ | -------------------------------- | ------------------------------ | ---- |
| GET    | `/api/v1/leaderboards/{period}`  | Get leaderboard for period     | Yes  |
| GET    | `/api/v1/leaderboards/{period}/me` | Get user's rank in period   | Yes  |

#### Test Deliverables

| Test Suite             | Path                                        | Coverage Target |
| ---------------------- | ------------------------------------------- | --------------- |
| Ranking calculation    | `tests/unit/test_leaderboard.py`            | 100%            |
| Tie-breaking           | `tests/unit/test_tiebreaking.py`            | 100%            |
| Leaderboard cache      | `tests/integration/test_leaderboard_cache.py`| >85%           |
| Leaderboard routes     | `tests/integration/test_leaderboard_routes.py`| >85%          |

### Acceptance Criteria

```gherkin
Feature: Leaderboards

  Scenario: Tier-scoped ranking
    Given multiple users in tier "M-30-39-INT"
    When the weekly leaderboard is requested
    Then users are ranked by points earned this week
    And the user's rank and position context (±10) are shown
    And tier total users count is displayed

  Scenario: Period resets
    Given it is Monday 00:00 EST
    When the weekly leaderboard resets
    Then all weekly rankings start from zero
    And historical weekly rankings are preserved

  Scenario: Tie-breaking
    Given two users with identical weekly points
    When the leaderboard is generated
    Then the user who reached the total first ranks higher
```

### Definition of Done

- [ ] All four leaderboard periods functional (daily/weekly/monthly/all-time)
- [ ] Rankings scoped to user's tier (30 possible tiers)
- [ ] Tie-breaking rules implemented per PRD
- [ ] Top 100 + contextual ±10 display logic
- [ ] Redis caching with 15-minute refresh
- [ ] Leaderboard worker runs on schedule
- [ ] All tests passing

---

## Checkpoint 6: Sweepstakes & Prize System

### Objective

Implement the complete sweepstakes workflow: drawing management, ticket purchasing, CSPRNG-based winner selection, prize fulfillment tracking, and sponsor management. This is the primary monetization and engagement driver.

### Prerequisites

- [x] Checkpoint 4 completed (users have point balances)

### Deliverables

#### Code Deliverables

| Component           | Path                                        | Description                                    |
| ------------------- | ------------------------------------------- | ---------------------------------------------- |
| Drawing service     | `src/fittrack/services/drawings.py`         | Drawing lifecycle, ticket sales management     |
| Ticket service      | `src/fittrack/services/tickets.py`          | Ticket purchase with point deduction           |
| Drawing executor    | `src/fittrack/services/drawing_executor.py` | CSPRNG winner selection, audit trail           |
| Fulfillment service | `src/fittrack/services/fulfillments.py`     | Prize fulfillment state machine                |
| Sponsor service     | `src/fittrack/services/sponsors.py`         | Sponsor CRUD                                   |
| Drawing worker      | `src/fittrack/workers/drawing_worker.py`    | Scheduled drawing execution                    |
| Drawing routes      | `src/fittrack/api/routes/drawings.py`       | Drawing and ticket endpoints                   |
| Sponsor routes      | `src/fittrack/api/routes/sponsors.py`       | Sponsor admin endpoints                        |

#### API Endpoints

| Method | Path                                        | Description                  | Auth  |
| ------ | ------------------------------------------- | ---------------------------- | ----- |
| GET    | `/api/v1/drawings`                          | List drawings (filtered)     | Yes   |
| GET    | `/api/v1/drawings/{id}`                     | Get drawing details          | Yes   |
| POST   | `/api/v1/drawings/{id}/tickets`             | Purchase tickets             | Yes   |
| GET    | `/api/v1/drawings/{id}/results`             | Get drawing results          | Yes   |
| GET    | `/api/v1/drawings/{id}/my-tickets`          | Get user's tickets           | Yes   |
| POST   | `/api/v1/admin/drawings`                    | Create drawing               | Admin |
| PUT    | `/api/v1/admin/drawings/{id}`               | Update drawing               | Admin |
| POST   | `/api/v1/admin/drawings/{id}/execute`       | Execute drawing              | Admin |
| DELETE | `/api/v1/admin/drawings/{id}`               | Cancel drawing               | Admin |
| GET    | `/api/v1/admin/sponsors`                    | List sponsors                | Admin |
| POST   | `/api/v1/admin/sponsors`                    | Create sponsor               | Admin |
| PUT    | `/api/v1/admin/sponsors/{id}`               | Update sponsor               | Admin |
| GET    | `/api/v1/admin/fulfillments`                | List fulfillments            | Admin |
| PUT    | `/api/v1/admin/fulfillments/{id}`           | Update fulfillment status    | Admin |
| POST   | `/api/v1/admin/fulfillments/{id}/ship`      | Mark shipped with tracking   | Admin |
| POST   | `/api/v1/fulfillments/{id}/confirm-address` | Winner confirms address      | Yes   |

#### Test Deliverables

| Test Suite               | Path                                         | Coverage Target |
| ------------------------ | -------------------------------------------- | --------------- |
| Drawing service          | `tests/unit/test_drawing_service.py`         | >90%            |
| Ticket purchase          | `tests/unit/test_ticket_service.py`          | >95%            |
| Drawing execution        | `tests/unit/test_drawing_executor.py`        | 100%            |
| Fulfillment state machine| `tests/unit/test_fulfillment.py`             | 100%            |
| Drawing routes           | `tests/integration/test_drawing_routes.py`   | >85%            |
| Ticket concurrency       | `tests/integration/test_ticket_concurrency.py`| Critical paths |
| Sponsor routes           | `tests/integration/test_sponsor_routes.py`   | >85%            |

### Acceptance Criteria

```gherkin
Feature: Ticket Purchase

  Scenario: Successful ticket purchase
    Given a user with 1,000 point balance
    When they purchase 5 tickets at 100 points each
    Then 500 points are deducted atomically
    And 5 tickets are created linked to the drawing
    And a point transaction record is created

  Scenario: Insufficient points
    Given a user with 50 point balance
    When they attempt to purchase a 100-point ticket
    Then a 400 error is returned with "insufficient points"

Feature: Drawing Execution

  Scenario: Winner selection
    Given a closed drawing with 4,521 tickets
    When an admin executes the drawing
    Then tickets are snapshot and numbered sequentially
    Then a CSPRNG selects the winning ticket number(s)
    And the random seed is recorded for audit
    And winners are marked on ticket records
    And fulfillment records are created
    And results are immutable (no re-execution)

Feature: Prize Fulfillment

  Scenario: Fulfillment workflow
    Given a winner has been selected
    Then status moves to "winner_notified"
    When the winner confirms their shipping address
    Then status moves to "address_confirmed"
    When admin enters tracking number
    Then status moves to "shipped"
    When delivery is confirmed
    Then status moves to "delivered"
```

### Security Considerations

- Drawing execution uses CSPRNG (Python `secrets` module, OCI Vault in production)
- Drawing results are immutable — no UPDATE allowed after execution
- Audit trail records seed, algorithm, ticket snapshot, timestamp
- Ticket purchase uses `SELECT ... FOR UPDATE` on user balance to prevent race conditions
- Admin-only endpoints require elevated JWT role

### Definition of Done

- [ ] Drawings can be created, scheduled, opened, closed, executed, and cancelled
- [ ] Ticket purchase deducts points atomically
- [ ] CSPRNG winner selection with audit trail
- [ ] Drawing results immutable after execution
- [ ] Prize fulfillment state machine works through all states
- [ ] Forfeit timeout logic (7-day warning, 14-day forfeit)
- [ ] Sponsor CRUD functional
- [ ] Concurrent ticket purchases don't corrupt balances
- [ ] Test page updated with drawing and ticket management
- [ ] All tests passing

---

## Checkpoint 7: Admin Dashboard & Notifications

### Objective

Implement admin management endpoints for user moderation, platform analytics, and the notification system (email + in-app) for winner alerts, verification, and system messages.

### Prerequisites

- [x] Checkpoint 5 completed (leaderboards functional)
- [x] Checkpoint 6 completed (drawings and fulfillment functional)

### Deliverables

#### Code Deliverables

| Component              | Path                                           | Description                                 |
| ---------------------- | ---------------------------------------------- | ------------------------------------------- |
| Admin user service     | `src/fittrack/services/admin_users.py`         | User search, suspend, ban, point adjustment |
| Analytics service      | `src/fittrack/services/analytics.py`           | Platform metrics aggregation                |
| Notification service   | `src/fittrack/services/notifications.py`       | Email + in-app notification dispatch        |
| Email templates        | `src/fittrack/templates/`                      | HTML email templates (Jinja2)               |
| Admin user routes      | `src/fittrack/api/routes/admin_users.py`       | Admin user management endpoints             |
| Analytics routes       | `src/fittrack/api/routes/admin_analytics.py`   | Analytics API endpoints                     |
| Notification routes    | `src/fittrack/api/routes/notifications.py`     | User notification endpoints                 |

#### Database Deliverables

| Item                          | Description                          |
| ----------------------------- | ------------------------------------ |
| Migration: 007_notifications  | Create `notifications` table         |
| Migration: 008_admin_log      | Create `admin_actions_log` table     |

#### API Endpoints

| Method | Path                                      | Description                 | Auth  |
| ------ | ----------------------------------------- | --------------------------- | ----- |
| GET    | `/api/v1/admin/users`                     | Search/list users           | Admin |
| PUT    | `/api/v1/admin/users/{id}/status`         | Suspend/ban/activate user   | Admin |
| POST   | `/api/v1/admin/users/{id}/adjust-points`  | Manual point adjustment     | Admin |
| GET    | `/api/v1/admin/analytics/overview`        | Dashboard metrics           | Admin |
| GET    | `/api/v1/admin/analytics/registrations`   | Registration trends         | Admin |
| GET    | `/api/v1/admin/analytics/activity`        | Activity metrics            | Admin |
| GET    | `/api/v1/admin/analytics/drawings`        | Drawing participation       | Admin |
| GET    | `/api/v1/notifications`                   | User's notifications        | Yes   |
| PUT    | `/api/v1/notifications/{id}/read`         | Mark notification as read   | Yes   |
| GET    | `/api/v1/notifications/unread-count`      | Unread notification count   | Yes   |

#### Test Deliverables

| Test Suite              | Path                                            | Coverage Target |
| ----------------------- | ----------------------------------------------- | --------------- |
| Admin user management   | `tests/integration/test_admin_users.py`         | >85%            |
| Analytics queries       | `tests/integration/test_analytics.py`           | >80%            |
| Notification service    | `tests/unit/test_notifications.py`              | >90%            |
| Notification routes     | `tests/integration/test_notification_routes.py` | >85%            |

### Acceptance Criteria

```gherkin
Feature: Admin User Management

  Scenario: Suspend a user
    Given an admin and a user who violated ToS
    When the admin PUTs status "suspended" to /admin/users/{id}/status
    Then the user's status changes to "suspended"
    And the action is logged in admin_actions_log
    And the user's active sessions are invalidated

Feature: Notifications

  Scenario: Winner notification
    Given a user wins a prize drawing
    Then an in-app notification is created
    And an email is sent within 5 minutes
    And the notification appears in the user's notification feed
```

### Definition of Done

- [ ] Admin can search, view, suspend, ban, and activate users
- [ ] Admin can make manual point adjustments with reason logging
- [ ] Analytics endpoints return meaningful platform metrics
- [ ] Email notifications sent for: verification, password reset, winner notification, fulfillment updates
- [ ] In-app notification system with unread/read tracking
- [ ] All admin actions logged with admin user ID and timestamp
- [ ] All tests passing

---

## Checkpoint 8: Production Readiness & Hardening

### Objective

Harden the application for production deployment: rate limiting, security headers, structured logging, performance optimization, comprehensive E2E tests, and deployment configuration.

### Prerequisites

- [x] Checkpoint 7 completed (all features functional)

### Deliverables

#### Code Deliverables

| Component              | Path                                           | Description                              |
| ---------------------- | ---------------------------------------------- | ---------------------------------------- |
| Rate limiter           | `src/fittrack/api/middleware.py`               | Tiered rate limiting per PRD             |
| Security headers       | `src/fittrack/api/middleware.py`               | HSTS, CSP, X-Frame-Options, etc.        |
| Structured logging     | `src/fittrack/core/logging.py`                 | JSON log output with request tracing     |
| Health checks          | `src/fittrack/api/routes/health.py`            | Readiness + liveness probes              |
| Production Dockerfile  | `docker/Dockerfile.prod`                       | Multi-stage production build             |
| Helm charts            | `deploy/helm/`                                 | Kubernetes deployment manifests          |
| Terraform config       | `deploy/terraform/`                            | OCI infrastructure definitions           |

#### Test Deliverables

| Test Suite        | Path                                 | Coverage Target   |
| ----------------- | ------------------------------------ | ----------------- |
| E2E: Registration | `tests/e2e/test_registration.py`     | Critical path     |
| E2E: Activity     | `tests/e2e/test_activity_flow.py`    | Critical path     |
| E2E: Drawing      | `tests/e2e/test_drawing_flow.py`     | Critical path     |
| Performance       | `tests/performance/`                  | Baseline targets  |
| Security          | `tests/security/`                     | OWASP Top 10      |

### Acceptance Criteria

```gherkin
Feature: Production Security

  Scenario: Rate limiting
    Given an anonymous client
    When they exceed 10 requests/minute
    Then a 429 response is returned with Retry-After header

  Scenario: Security headers
    Given any API response
    Then it includes HSTS, X-Content-Type-Options, X-Frame-Options headers

Feature: E2E Flows

  Scenario: Complete user journey
    Given a new user registers and verifies email
    When they complete their profile
    And connect a fitness tracker
    And activities are synced and points awarded
    And they purchase tickets for an open drawing
    Then their point balance reflects the purchase
    And tickets appear in the drawing
```

### Definition of Done

- [ ] Rate limiting enforced at all tiers (anonymous, user, admin)
- [ ] Security headers on all responses
- [ ] Structured JSON logging with correlation IDs
- [ ] Readiness and liveness health probes
- [ ] Production Docker build < 200MB
- [ ] E2E tests cover 3 critical user journeys
- [ ] Performance baseline established (API response < 500ms p95)
- [ ] Terraform scripts provision OCI resources
- [ ] Test page disabled in production mode
- [ ] All dev endpoints disabled in production
- [ ] README updated with production deployment guide
- [ ] All tests passing with overall >85% coverage

---

## Risk Register

| ID  | Risk                                          | Probability | Impact   | Mitigation                                                                     |
| --- | --------------------------------------------- | ----------- | -------- | ------------------------------------------------------------------------------ |
| R1  | Oracle 23ai Docker image slow startup in CI   | High        | Medium   | Cache Docker layers; use service containers; increase CI timeout to 5 min      |
| R2  | Fitness API rate limits exceeded during sync   | Medium      | High     | Queue-based processing; respect rate headers; exponential backoff              |
| R3  | Concurrent ticket purchases corrupt balances   | Medium      | Critical | `SELECT ... FOR UPDATE` on balance; integration test for concurrency           |
| R4  | Drawing result tampering claims                | Low         | Critical | CSPRNG audit trail; immutable results; third-party audit provision             |
| R5  | OAuth token expiry causes mass sync failures   | Medium      | Medium   | Proactive refresh 5 min before expiry; clear error messaging to users          |
| R6  | Sweepstakes law violation in excluded state     | Low         | Critical | State validation at registration; blocked at API level; legal review pre-launch|
| R7  | Seed data generation too slow for CI           | Medium      | Low      | Reduce CI seed to minimum viable; full seed only in nightly builds             |
| R8  | Google/Apple OAuth review delays               | Medium      | High     | Start OAuth app review process immediately; mock providers for dev/CI          |
| R9  | Password/token leakage in logs                 | Low         | Critical | Structured logging with sensitive field redaction; automated secret scanning   |
| R10 | Premium subscription payment integration       | Low (v1.1)  | Medium   | Deferred to v1.1; use Stripe for PCI compliance                               |

---

## Assumptions

| ID  | Assumption                                                              | Impact if Wrong                     | Validation                                      |
| --- | ----------------------------------------------------------------------- | ----------------------------------- | ----------------------------------------------- |
| A1  | Oracle 23ai Free Docker image is feature-compatible with Autonomous DB  | Migration issues at deploy time     | Test key features (JSON, Duality Views) early    |
| A2  | Google Fit + Fitbit cover majority of MVP target users                  | Reduced adoption                    | Market research; add Apple Health in v1.1        |
| A3  | 15-minute sync interval is acceptable for MVP users                     | User dissatisfaction                | Beta feedback; plan real-time for scale phase    |
| A4  | 1,000 point daily cap prevents gaming without frustrating power users   | Churn or gaming                     | Monitor outlier distributions post-launch        |
| A5  | python-oracledb thin mode has all features needed (no thick mode)       | Need Oracle Client libraries in CI  | Verify JSON Duality View support in thin mode    |
| A6  | Social login (Google + Apple) can be approved before MVP launch         | Must fall back to email-only auth   | Begin OAuth app review in CP2                    |
| A7  | Gift cards are sufficient initial prizes (no physical fulfillment MVP)  | Lower engagement                    | Start with digital prizes; add physical in v1.1  |
| A8  | 63 seed users are sufficient to demonstrate all features/tiers          | Thin demo data                      | Scale seed if needed; ensure all 30 tiers covered|
| A9  | Email-based verification (no MFA) is adequate security for MVP          | Account takeover risk               | Add MFA in v1.1; monitor for suspicious logins   |
| A10 | Prize values under $600 avoid 1099 tax reporting requirements           | Compliance failure                  | Legal review of prize value thresholds           |
