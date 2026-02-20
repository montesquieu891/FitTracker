# Implementation Checklist: FitTrack

Progress tracker for all checkpoints. Update task status as work progresses.

---

## Checkpoint 1: Foundation — Environment & Data Layer

### Infrastructure

- [x] Create project directory structure (`src/fittrack/`, `tests/`, `static/`, etc.)
- [x] Create `pyproject.toml` with all dependencies (fastapi, uvicorn, oracledb, pydantic, faker, pytest, hypothesis, ruff, mypy, httpx)
- [x] Create `.gitignore` (Python, Node, Docker, IDE, `.env`)
- [x] Create `.env.example` with all required environment variables
- [x] Create `docker/docker-compose.yml` (Oracle 23ai Free + Redis)
- [x] Create `docker/Dockerfile` for FastAPI application
- [x] Create `Makefile` with targets: setup, dev, test, test-unit, test-integration, db-migrate, db-seed, db-reset, lint, format
- [x] Create `.github/workflows/ci.yml` (lint → build → test)
- [x] Create `README.md` with <15 minute setup instructions
- [ ] Verify `make setup && make dev` works from fresh clone (requires Docker)

### Database

- [x] Implement database connection pool (`src/fittrack/core/database.py`) with oracledb
- [x] Create migration runner (`scripts/migrations.py`)
- [x] Migration 001: Create `users` table with all columns and constraints
- [x] Migration 001: Create `profiles` table with tier_code, JSON goals column
- [x] Migration 001: Create `tracker_connections` table with provider check constraint
- [x] Migration 001: Create `activities` table with JSON metrics column
- [x] Migration 001: Create `point_transactions` table
- [x] Migration 001: Create `drawings` table with status workflow
- [x] Migration 001: Create `tickets` table
- [x] Migration 001: Create `prizes` table
- [x] Migration 001: Create `prize_fulfillments` table with status check constraint
- [x] Migration 001: Create `sponsors` table
- [x] Migration 002: Create all indexes (users_email, users_status, profiles_tier, activities_user_date, etc.)
- [x] Migration 003: Create `user_profile_dv` JSON Duality View (DDL written, requires Oracle 23ai to execute)
- [ ] Verify all tables, constraints, and indexes exist after migration (requires Oracle container)

### Core Application

- [x] Create app factory (`src/fittrack/main.py`) with lifespan, CORS, middleware
- [x] Create config module (`src/fittrack/core/config.py`) with Pydantic Settings
- [x] Create constants module (`src/fittrack/core/constants.py`) — point rates, tier codes, eligible states, drawing types
- [x] Create RFC 7807 error handler middleware (`src/fittrack/api/middleware.py`)
- [x] Create dependency injection module (`src/fittrack/api/deps.py`) — DB pool, pagination

### Repositories

- [x] Create base repository with common CRUD patterns (`src/fittrack/repositories/base.py`)
- [x] Implement `UserRepository` — get, list (paginated), create, update, delete
- [x] Implement `ProfileRepository` — get, list, create, update (with tier code computation)
- [x] Implement `ConnectionRepository` — get, list, create, update, delete
- [x] Implement `ActivityRepository` — get, list (filterable by date/type), create, update
- [x] Implement `TransactionRepository` — get, list (paginated), create
- [x] Implement `DrawingRepository` — get, list (filterable by status/type), create, update
- [x] Implement `TicketRepository` — get, list, create
- [x] Implement `PrizeRepository` — get, list, create, update
- [x] Implement `FulfillmentRepository` — get, list, create, update
- [x] Implement `SponsorRepository` — get, list, create, update

### API Schemas

- [x] Create Pydantic schemas for User (Create, Update, Response, List)
- [x] Create Pydantic schemas for Profile (Create, Update, Response)
- [x] Create Pydantic schemas for TrackerConnection (Create, Response)
- [x] Create Pydantic schemas for Activity (Create, Response, List with pagination)
- [x] Create Pydantic schemas for PointTransaction (Create, Response, List)
- [x] Create Pydantic schemas for Drawing (Create, Update, Response, List)
- [x] Create Pydantic schemas for Ticket (Create, Response, List)
- [x] Create Pydantic schemas for Prize (Create, Response)
- [x] Create Pydantic schemas for PrizeFulfillment (Update, Response)
- [x] Create Pydantic schemas for Sponsor (Create, Update, Response)
- [x] Create shared pagination schema
- [x] Create RFC 7807 error response schema

### API Routes

- [x] Create health check routes (`/health`)
- [x] Create User CRUD routes (GET list, GET by ID, POST, PATCH, DELETE)
- [x] Create Profile CRUD routes (GET list, GET by ID, POST, PUT)
- [x] Create Connection CRUD routes (GET list, POST, DELETE)
- [x] Create Activity CRUD routes (GET list with filters, POST)
- [x] Create Transaction CRUD routes (GET list, POST)
- [x] Create Drawing CRUD routes (GET list with filters, GET by ID, POST, PATCH, DELETE)
- [x] Create Ticket CRUD routes (GET list, POST)
- [x] Create Prize CRUD routes (GET list, POST)
- [x] Create Fulfillment CRUD routes (GET list, POST, PUT)
- [x] Create Sponsor CRUD routes (GET list, GET by ID, POST, PATCH, DELETE)
- [x] Create dev-only routes (`POST /api/v1/dev/seed`, `POST /api/v1/dev/reset`)

### Synthetic Data

- [x] Create `UserFactory` (`build_user`, `build_user_batch`)
- [x] Create `ProfileFactory` (`build_profile`) — spans all 30 tiers
- [x] Create `ConnectionFactory` (`build_connection`) — Google Fit, Fitbit
- [x] Create `ActivityFactory` (`build_activity`) — realistic metrics
- [x] Create `TransactionFactory` (`build_transaction`)
- [x] Create `DrawingFactory` (`build_drawing`) — all types
- [x] Create `TicketFactory` (`build_ticket`)
- [x] Create `PrizeFactory` (`build_prize`) — realistic values
- [x] Create `FulfillmentFactory` (`build_fulfillment`) — various states
- [x] Create `SponsorFactory` (`build_sponsor`)
- [x] Create seed orchestrator script (`scripts/seed_data.py`)
- [ ] Verify: 50 regular + 10 premium + 3 admin users created (requires Oracle)
- [ ] Verify: all 30 tiers represented in profiles (requires Oracle)
- [ ] Verify: 15+ activities per user (requires Oracle)
- [ ] Verify: point transactions reconcile with activities (requires Oracle)
- [ ] Verify: 30 drawings across all types/statuses (requires Oracle)
- [ ] Verify: 5 sponsors with prizes (requires Oracle)
- [ ] Verify: fulfillments in various states (requires Oracle)

### Test Page

- [x] Create `static/test_page.html` — single-page dev tool
- [x] API endpoint browser with forms for all CRUD operations
- [x] Entity data viewer with sortable tables
- [x] Database seed button (`POST /api/v1/dev/seed`)
- [x] Database reset button (`POST /api/v1/dev/reset`)
- [x] Health check status indicators
- [x] Response time display for each API request
- [x] Raw JSON response viewer
- [x] Sample reports: user count by tier, point distribution, drawing statistics
- [ ] Serve test page at `/test` (disabled in production)

### Tests

- [x] Create test conftest with DB fixtures and test client (`tests/conftest.py`)
- [ ] Write `test_database.py` — connection pool creation, basic query (integration)
- [x] Write `test_routes.py` — all entity API route tests (51 tests)
- [x] Write `test_base_repository.py` — all CRUD operations (98% coverage)
- [x] Write `test_repositories.py` — all 10 entity repositories
- [x] Write `test_factories.py` — validate all factories produce valid data
- [x] Write `test_schemas.py` — validate all Pydantic schemas (34 tests)
- [x] Write `test_constants.py` — validate all business rule constants (27 tests)
- [x] Write API route tests for all entity endpoints
- [x] Verify all 166 unit tests pass
- [x] Verify 89.66% coverage (above 85% threshold)
- [x] Verify `make lint` passes (ruff)

---

## Checkpoint 2: Authentication & Authorization

### Authentication

- [x] Implement password hashing with Argon2id (`src/fittrack/core/security.py`)
- [x] Implement JWT encode/decode with RS256 (`src/fittrack/core/security.py`)
- [x] Generate RSA key pair for JWT signing (dev keys in repo, production from env)
- [x] Create auth service (`src/fittrack/services/auth.py`)
- [x] Implement email registration with validation (age 18+, eligible state, password complexity)
- [x] Implement email verification with token
- [x] Implement login with JWT token generation (access 1h + refresh 30d)
- [x] Implement token refresh endpoint
- [x] Implement logout (invalidate refresh token)
- [x] Implement logout-all (invalidate all sessions)
- [x] Implement forgot-password flow
- [x] Implement reset-password flow
- [x] Implement account lockout (5 failures → 15 min lockout)

### Social Login

- [ ] Create OAuth provider base class (`src/fittrack/services/oauth_providers.py`)
- [ ] Implement Google OAuth token verification
- [ ] Implement Apple Sign-In token verification
- [ ] Handle account creation for new social login users
- [ ] Handle account linking for existing email matches
- [x] Create `oauth_accounts` table (migration 004)

### Authorization

- [x] Create `get_current_user` dependency (decode JWT, load user)
- [x] Create `require_role` dependency (check user role)
- [x] Create `require_admin` dependency
- [x] Create sessions table for refresh token tracking (migration 005)
- [x] Add RBAC checks to all existing endpoints
- [x] Protect user endpoints (own data only)
- [x] Protect admin endpoints (admin role required)

### Email Service

- [x] Create email service stub (`src/fittrack/services/email.py`)
- [x] Console output in dev mode
- [x] Pluggable for real email provider (SES/SendGrid) in production

### Auth Routes

- [x] `POST /auth/register` — with all validations
- [x] `POST /auth/login` — email/password
- [x] `POST /auth/refresh` — refresh access token
- [x] `POST /auth/verify-email` — verify with token
- [x] `POST /auth/forgot-password` — initiate reset
- [x] `POST /auth/reset-password` — complete reset
- [x] `POST /auth/social/google` — Google OAuth (stub — returns 501)
- [x] `POST /auth/social/apple` — Apple Sign-In (stub — returns 501)
- [x] `POST /auth/logout` — invalidate session
- [x] `POST /auth/logout-all` — invalidate all sessions

### Tests

- [x] Write `test_security.py` — password hashing, JWT encode/decode (33 tests)
- [x] Write `test_auth_service.py` — registration, login, refresh, lockout (28 tests)
- [x] Write `test_auth_routes.py` — all auth endpoints (18 tests)
- [x] Write `test_rbac.py` — role-based access on all endpoints (14 tests)
- [x] Update test page with login form and auth header management
- [x] Verify all 263 tests pass, 0 lint errors

---

## Checkpoint 3: User Profiles & Competition Tiers

### Profile Service

- [x] Create profile service (`src/fittrack/services/profiles.py`)
- [x] Implement tier code computation from profile attributes
- [x] Implement tier recalculation on profile field changes
- [x] Implement profile completion check

### Tier Engine

- [x] Create tier service (`src/fittrack/services/tiers.py`)
- [x] Enumerate all 30 tier combinations
- [x] Compute tier metadata (display name, user count)
- [x] Validate tier code format

### Profile Gate

- [x] Create middleware to block incomplete profiles from main features
- [x] Allow access to: auth endpoints, profile creation, health checks
- [x] Return 403 with redirect message for incomplete profiles

### Routes

- [x] `GET /api/v1/users/me` — current user with profile
- [x] `PUT /api/v1/users/me/profile` — create/update profile
- [x] `PATCH /api/v1/users/me/profile` — partial update profile
- [x] `GET /api/v1/users/me/profile/complete` — profile completeness check
- [x] `GET /api/v1/users/{id}/public` — public profile (display name, tier)
- [x] `GET /api/v1/tiers` — list all tiers (optional user counts)
- [x] `GET /api/v1/tiers/{code}` — tier details with user count
- [x] Refactored `profiles.py` routes to use `ProfileService`

### Tests

- [x] Write `test_tiers.py` — all 30 tier computations, validate, parse, display, routes (72 tests)
- [x] Write `test_profile_service.py` — CRUD, tier computation, recalculation, completion (42 tests)
- [x] Write `test_me_routes.py` — /users/me endpoints + public profile (15 tests)
- [x] Write `test_profile_gate.py` — middleware blocking behavior (42 tests)
- [x] Verify all 434 tests pass, 0 lint errors

---

## Checkpoint 4: Activity Tracking & Points System

### Tracker Integration

- [x] Create provider base class (`src/fittrack/services/providers/base.py`)
- [x] Implement Google Fit client (`src/fittrack/services/providers/google_fit.py`)
- [x] Implement Fitbit client (`src/fittrack/services/providers/fitbit.py`)
- [x] Create tracker service (`src/fittrack/services/trackers.py`) for OAuth flow management
- [x] Implement OAuth token encryption (AES-256-GCM) for storage
- [x] Implement proactive token refresh

### Data Pipeline

- [x] Create activity normalizer (`src/fittrack/services/normalizer.py`)
- [x] Normalize Google Fit data to internal Activity format
- [x] Normalize Fitbit data to internal Activity format
- [x] Implement duplicate activity detection (same type + overlapping time)
- [x] Implement multi-tracker priority rules (primary → most detailed → first received)

### Sync Worker

- [x] Create sync worker (`src/fittrack/workers/sync_worker.py`)
- [x] Query users due for sync (last_sync + 15 min < now)
- [x] Fetch activities from provider APIs
- [x] Normalize, deduplicate, and store activities
- [x] Calculate and award points
- [ ] Update leaderboard rankings
- [x] Handle sync errors gracefully (per-user, don't block batch)

### Points System

- [x] Create points service (`src/fittrack/services/points.py`)
- [x] Implement rate table: steps (10 pts/1K, cap 20K/day)
- [x] Implement rate table: active minutes (1/2/3 pts for light/moderate/vigorous)
- [x] Implement rate table: workout bonus (50 pts, max 3/day)
- [x] Implement rate table: daily step goal bonus (100 pts for 10K steps)
- [x] Implement rate table: weekly streak bonus (250 pts for 7 consecutive active days)
- [x] Create daily_points_log table (migration 007)
- [x] Implement daily cap enforcement (1,000 pts/day)

### Anti-Gaming

- [x] Create anti-gaming service (`src/fittrack/services/anti_gaming.py`)
- [x] Daily point cap enforcement
- [x] Workout bonus cap enforcement (3/day)
- [x] Anomaly detection (>3 std deviations from tier average)
- [x] Device verification tracking (flag multiple accounts per device)
- [x] Manual review queue for suspicious accounts

### Point Balance

- [x] Implement atomic point balance updates with optimistic locking
- [x] Create point transactions for every earn/spend/adjust
- [x] Ensure balance_after column is accurate

### Routes

- [x] `GET /api/v1/connections` — list user's connections
- [x] `POST /api/v1/connections/{provider}/initiate` — start OAuth
- [x] `POST /api/v1/connections/{provider}/callback` — complete OAuth
- [x] `DELETE /api/v1/connections/{provider}` — disconnect
- [x] `POST /api/v1/connections/{provider}/sync` — force sync (rate limited)
- [x] `GET /api/v1/activities` — list with filters (date, type, pagination)
- [x] `GET /api/v1/activities/summary` — today/week/month stats
- [x] `GET /api/v1/points/balance` — current balance
- [x] `GET /api/v1/points/transactions` — transaction history

### Tests

- [x] Write `test_points.py` — all rate table calculations (100%)
- [x] Write `test_points_properties.py` — Hypothesis property-based tests
- [x] Write `test_anti_gaming.py` — all cap/detection logic (100%)
- [x] Write `test_normalizer.py` — data normalization for both providers (>95%)
- [x] Write `test_providers.py` — provider mock tests (>90%)
- [x] Write `test_sync_worker.py` — batch sync integration (>85%)
- [x] Write `test_connection_routes.py` — OAuth flow endpoints (>85%)
- [x] Write `test_activity_routes.py` — activity endpoints (>85%)
- [ ] Update test page with activity viewer and points display
- [x] Verify all 667 tests pass, 0 lint errors

---

## Checkpoint 5: Leaderboards & Rankings

### Leaderboard Engine

- [x] Create leaderboard service (`src/fittrack/services/leaderboard.py`)
- [x] Implement ranking by points earned within period (not balance)
- [x] Implement daily period (midnight EST reset)
- [x] Implement weekly period (Monday 00:00 EST reset)
- [x] Implement monthly period (1st of month reset)
- [x] Implement all-time period (no reset)
- [x] Implement tie-breaking: earliest achievement → more active days → user_id
- [x] Implement top 100 + contextual ±10 positions logic

### Caching

- [x] Create cache service (`src/fittrack/services/cache.py`)
- [x] Implement Redis caching for leaderboard data
- [x] Cache invalidation on point updates
- [x] 15-minute cache TTL for leaderboard data

### Leaderboard Worker

- [x] Create leaderboard worker (`src/fittrack/workers/leaderboard_worker.py`)
- [x] Periodic recalculation every 15 minutes
- [x] Update cached rankings

### Routes

- [x] `GET /api/v1/leaderboards/{period}` — tier-scoped leaderboard
- [x] `GET /api/v1/leaderboards/{period}/me` — user's rank
- [x] Support tier filter query parameter (defaults to user's tier)
- [x] Pagination support for rankings list

### Tests

- [x] Write `test_leaderboard.py` — ranking calculation for all periods (100%)
- [x] Write `test_tiebreaking.py` — all tie-breaking scenarios (100%)
- [x] Write `test_leaderboard_cache.py` — Redis caching (>85%)
- [x] Write `test_leaderboard_routes.py` — endpoint responses (>85%)
- [ ] Update test page with leaderboard viewer
- [x] Verify all 763 tests pass, 0 lint errors

---

## Checkpoint 6: Sweepstakes & Prize System

### Drawing Management

- [x] Create drawing service (`src/fittrack/services/drawings.py`)
- [x] Implement drawing lifecycle: draft → scheduled → open → closed → completed/cancelled
- [x] Implement ticket sales close (5 minutes before drawing time)
- [x] Implement drawing eligibility checks (user type, min account age)

### Ticket System

- [x] Create ticket service (`src/fittrack/services/tickets.py`)
- [x] Implement ticket purchase with atomic point deduction
- [x] Use `SELECT ... FOR UPDATE` to prevent race conditions on balance
- [x] Support bulk ticket purchase (multiple tickets in one transaction)
- [x] Create point transaction for each purchase
- [x] Validate: sufficient points, drawing is open, user is eligible

### Drawing Execution

- [x] Create drawing executor (`src/fittrack/services/drawing_executor.py`)
- [x] Create immutable ticket snapshot at drawing close
- [x] Assign sequential ticket numbers
- [x] Use CSPRNG (`secrets` module) for winner selection
- [x] Record random seed and algorithm for audit
- [x] Mark winning tickets
- [x] Create prize fulfillment records for winners
- [x] Prevent re-execution of completed drawings
- [x] Publish results (immutable after execution)

### Prize Fulfillment

- [x] Create fulfillment service (`src/fittrack/services/fulfillments.py`)
- [x] Implement state machine: pending → winner_notified → address_confirmed → shipped → delivered
- [x] Handle address_invalid → address_confirmed recovery path
- [x] Implement 7-day address confirmation warning
- [x] Implement 14-day forfeit timeout
- [x] Track shipping info (carrier, tracking number)

### Drawing Worker

- [x] Create drawing worker (`src/fittrack/workers/drawing_worker.py`)
- [x] Scheduled check for drawings past their drawing_time
- [x] Auto-close ticket sales at T-5 minutes
- [x] Auto-execute drawings at T-0

### Sponsor Management

- [x] Create sponsor service (`src/fittrack/services/sponsors.py`)
- [x] CRUD with status management (active/inactive)

### Routes

- [x] `GET /api/v1/drawings` — list with status/type filters
- [x] `GET /api/v1/drawings/{id}` — drawing details with prizes
- [x] `POST /api/v1/drawings/{id}/tickets` — purchase tickets
- [x] `GET /api/v1/drawings/{id}/results` — completed drawing results
- [x] `GET /api/v1/drawings/{id}/my-tickets` — user's tickets for drawing
- [x] `POST /api/v1/admin/drawings` — create drawing (admin)
- [x] `PUT /api/v1/admin/drawings/{id}` — update drawing (admin)
- [x] `POST /api/v1/admin/drawings/{id}/execute` — execute drawing (admin)
- [x] `DELETE /api/v1/admin/drawings/{id}` — cancel drawing (admin)
- [x] `GET /api/v1/admin/sponsors` — list sponsors (admin)
- [x] `POST /api/v1/admin/sponsors` — create sponsor (admin)
- [x] `PUT /api/v1/admin/sponsors/{id}` — update sponsor (admin)
- [x] `GET /api/v1/admin/fulfillments` — list fulfillments (admin)
- [x] `PUT /api/v1/admin/fulfillments/{id}` — update fulfillment (admin)
- [x] `POST /api/v1/admin/fulfillments/{id}/ship` — mark shipped (admin)
- [x] `POST /api/v1/fulfillments/{id}/confirm-address` — winner confirms address

### Tests

- [x] Write `test_drawing_service.py` — lifecycle management (>90%)
- [x] Write `test_ticket_service.py` — purchase with point deduction (>95%)
- [x] Write `test_drawing_executor.py` — CSPRNG selection, audit trail (100%)
- [x] Write `test_fulfillment.py` — state machine transitions (100%)
- [x] Write `test_drawing_routes.py` — all drawing endpoints (>85%)
- [x] Write `test_ticket_concurrency.py` — concurrent purchase race conditions
- [x] Write `test_sponsor_routes.py` — sponsor endpoints (>85%)
- [ ] Update test page with drawing/ticket management UI
- [x] Verify all 971 tests pass, 0 lint errors

---

## Checkpoint 7: Admin Dashboard & Notifications ✅ (1082 tests — 111 new)

### Admin User Management

- [x] Create admin user service (`src/fittrack/services/admin_users.py`)
- [x] Implement user search (by email, display name, status, tier)
- [x] Implement user suspend/ban/activate (state machine: ADMIN_STATUS_TRANSITIONS)
- [x] Implement manual point adjustment with reason (clamps to 0)
- [x] Create admin_actions_log table (migration 009)
- [x] Log all admin actions with admin user ID and timestamp
- [x] Create admin_action_log_repository (`src/fittrack/repositories/admin_action_log_repository.py`)

### Analytics

- [x] Create analytics service (`src/fittrack/services/analytics.py`)
- [x] Implement overview metrics (MAU, DAU, total users, active drawings)
- [x] Implement registration trend query (daily/weekly/monthly bucketing)
- [x] Implement activity metrics (avg per user, by type)
- [x] Implement drawing metrics (participation rate, tickets per user, by type/status)

### Notifications

- [x] Create notifications table (migration 008)
- [x] Create notification service (`src/fittrack/services/notifications.py`)
- [x] Implement in-app notification creation (7 types)
- [x] Implement email dispatch (console in dev, pluggable for prod)
- [x] Create email templates (8 templates): verification, password reset, winner notification, fulfillment shipped/delivered, account suspended/activated, point adjustment
- [x] Implement unread/read tracking with ownership validation
- [x] Trigger notifications: winner selected, fulfillment status change, account status change, point adjustment
- [x] Create notification_repository (`src/fittrack/repositories/notification_repository.py`)

### Routes

- [x] `GET /api/v1/admin/users` — search/list users (admin)
- [x] `GET /api/v1/admin/users/{id}` — user detail with profile + transactions (admin)
- [x] `PUT /api/v1/admin/users/{id}/status` — suspend/ban/activate (admin)
- [x] `POST /api/v1/admin/users/{id}/adjust-points` — point adjustment (admin)
- [x] `GET /api/v1/admin/users/{id}/actions` — action log (admin)
- [x] `GET /api/v1/admin/analytics/overview` — dashboard metrics (admin)
- [x] `GET /api/v1/admin/analytics/registrations` — trends (admin)
- [x] `GET /api/v1/admin/analytics/activity` — activity metrics (admin)
- [x] `GET /api/v1/admin/analytics/drawings` — drawing metrics (admin)
- [x] `GET /api/v1/notifications` — user's notifications (with is_read filter)
- [x] `GET /api/v1/notifications/{id}` — single notification (ownership validated)
- [x] `PUT /api/v1/notifications/{id}/read` — mark as read
- [x] `GET /api/v1/notifications/unread-count` — unread count

### Tests

- [x] Write `test_admin_users.py` — 32 tests: search, suspend, ban, point adjustment, action log
- [x] Write `test_analytics.py` — 23 tests: overview, registration trends, activity/drawing metrics
- [x] Write `test_notifications.py` — 32 tests: creation, dispatch, read/unread, templates
- [x] Write `test_notification_routes.py` — 24 tests: notification + admin user + analytics routes
- [x] All 1082 tests pass (971 prior + 111 new), ruff clean

---

## Checkpoint 8: Production Readiness & Hardening

### Security Hardening

- [x] Implement tiered rate limiting (anonymous 10/min, user 100/min, admin 500/min)
- [x] Add security headers (HSTS, X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy)
- [x] Configure CORS whitelist (production origins only)
- [x] Implement CSRF protection (SameSite cookies)
- [x] Add sensitive field redaction in logs (passwords, tokens)
- [x] Disable test page and dev endpoints in production mode
- [x] Input validation review (all endpoints)

### Observability

- [x] Implement structured JSON logging (`src/fittrack/core/logging.py`)
- [x] Add correlation ID (request tracing) to all logs
- [x] Create readiness probe endpoint (`/health/ready`)
- [x] Create liveness probe endpoint (`/health/live`)
- [x] Configure log levels per environment

### Performance

- [x] Review and optimize slow database queries
- [x] Add database query timing to logs
- [x] Configure connection pool sizing for production load
- [x] Index review for all query patterns
- [x] Response compression (gzip)

### Deployment

- [x] Create production Dockerfile (`docker/Dockerfile.prod`) — multi-stage, <200MB
- [x] Create Helm charts (`deploy/helm/`) for Kubernetes
- [x] Create Terraform configs (`deploy/terraform/`) for OCI resources
- [x] Configure environment-specific settings (dev, staging, production)
- [x] Document blue-green deployment process

### E2E Tests

- [x] Write `test_registration.py` — registration → verification → profile → tracker connection
- [x] Write `test_activity_flow.py` — sync → points awarded → balance updated → leaderboard
- [x] Write `test_drawing_flow.py` — create drawing → purchase tickets → execute → winner notified

### Documentation

- [x] Update README with production deployment guide
- [x] Document environment variables (all with descriptions)
- [x] Document API rate limits
- [x] Document backup/recovery procedures
- [x] Final review of CLAUDE.md

### Final Validation

- [x] All tests passing with >85% overall coverage
- [x] `make lint` clean (ruff + mypy)
- [x] CI pipeline green on main branch
- [x] Performance baseline: API response < 500ms (p95)
- [x] Security review: no secrets in codebase, no SQL injection, no XSS vectors
- [x] All dev-only features disabled in production config
