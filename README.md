# FitTrack

> Gamified fitness platform: earn points from tracked workouts, spend them on sweepstakes tickets for prize drawings.

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (for Oracle 23ai Free + Redis)

### Setup (host-run API, recommended)

```bash
# Clone and install
git clone <repo-url> && cd FitTracker
pip install -e ".[dev]"

# Start infrastructure (Oracle 23ai Free + Redis) via Compose
make docker-up        # oracle + redis only

# Run database migrations (host → Oracle container)
make db-migrate

# Seed with test data
make db-seed

# Start the API server on host (uvicorn reload)
make dev

# Quick smoke
make smoke            # uses scripts/smoke_http.sh (BASE_URL=http://localhost:8000)
```

### Alternate: API in Docker (compose)

```bash
make docker-up-all    # oracle + redis + api container
# API will be on http://localhost:8000
```

Environment defaults:
- Host-run: `.env` uses `ORACLE_DSN=localhost:1521/FREEPDB1` and `REDIS_URL=redis://localhost:6379/0`
- Compose API: overrides to `ORACLE_DSN=fittrack-oracle:1521/FREEPDB1` and `REDIS_URL=redis://fittrack-redis:6379/0`

### Development

```bash
make test          # Run full test suite (1,270 tests)
make test-unit     # Unit tests only
make test-cov      # Tests with coverage report
make lint          # Ruff lint + mypy type check
make format        # Auto-format code with ruff
make db-reset      # Drop + recreate + seed database
```

The API runs at `http://localhost:8000` with Swagger docs at `/docs`.

## Project Structure

```
src/fittrack/
├── api/              # FastAPI routers, schemas, middleware
│   ├── routes/       # 20 route modules (97 endpoints)
│   ├── schemas/      # Pydantic request/response models
│   ├── deps.py       # Dependency injection (auth, DB pool)
│   └── middleware.py  # Rate limiting, security headers, CORS, compression
├── services/         # Business logic (auth, points, drawings, sync, leaderboard)
├── repositories/     # Data access layer (python-oracledb, no ORM)
├── workers/          # Background jobs (sync, leaderboard refresh)
├── models/           # Domain models / dataclasses
├── core/             # Config, security, constants, logging, context
└── main.py           # App factory

tests/
├── unit/             # 1,261 tests with mocked DB
├── integration/      # Tests against real Oracle container
├── factories/        # Synthetic data generators (Faker)
└── conftest.py       # Shared fixtures

deploy/
├── helm/             # Kubernetes Helm charts
└── terraform/        # OCI infrastructure as code

docs/                 # PRD, deployment, environment, rate limits, backup
scripts/              # Migration & seed scripts
static/               # Dev API tester page
docker/               # Docker Compose + Dockerfiles (dev + prod)
```

## Tech Stack

| Component  | Choice                   |
| ---------- | ------------------------ |
| Language   | Python 3.12              |
| Framework  | FastAPI                  |
| Database   | Oracle 23ai Free (dev) / Autonomous JSON DB (prod) |
| DB Driver  | python-oracledb (thin mode)     |
| Cache      | Redis 7 / OCI Cache (prod)     |
| Auth       | JWT HS256 (dev/staging) + OAuth 2.0          |
| Testing    | pytest + Hypothesis (1,270 tests) |
| Linting    | ruff + mypy              |
| CI/CD      | GitHub Actions           |
| IaC        | Terraform (OCI)          |
| Containers | Docker + Helm (Kubernetes) |

## API Endpoints

97 endpoints across 20 route modules. Key groups:

| Module | Prefix | Endpoints | Description |
| ------ | ------ | --------- | ----------- |
| Health | `/health` | 3 | Liveness, readiness, health check |
| Auth | `/api/v1/auth` | 11 | Register, login, JWT refresh, OAuth, logout |
| Me | `/api/v1/users/me` | 6 | Current user profile, completeness check |
| Users | `/api/v1/users` | 5 | CRUD user management |
| Profiles | `/api/v1/profiles` | 4 | Profile CRUD with tier computation |
| Tiers | `/api/v1/tiers` | 2 | List/view competition tiers |
| Connections | `/api/v1/connections` | 5 | Fitness tracker OAuth & sync |
| Activities | `/api/v1/activities` | 3 | Activity log & summaries |
| Points | `/api/v1/points` | 4 | Balance, transactions, daily cap, streaks |
| Transactions | `/api/v1/transactions` | 2 | Point transaction ledger |
| Leaderboards | `/api/v1/leaderboards` | 2 | Tier leaderboards & user rank |
| Drawings | `/api/v1/drawings` | 13 | Sweepstakes lifecycle & ticket purchase |
| Tickets | `/api/v1/tickets` | 2 | Ticket management |
| Prizes | `/api/v1/prizes` | 2 | Prize management |
| Fulfillments | `/api/v1/fulfillments` | 9 | Prize delivery workflow |
| Sponsors | `/api/v1/sponsors` | 5 | Sponsor CRUD |
| Notifications | `/api/v1/notifications` | 4 | User notification management |
| Admin Users | `/api/v1/admin/users` | 5 | User moderation & point adjustments |
| Admin Analytics | `/api/v1/admin/analytics` | 4 | Dashboard metrics & trends |
| Dev | `/api/v1/dev` | 4 | Seed, reset, migrate (dev only) |

Full interactive docs available at `/docs` (Swagger UI) when running.

## Testing

1,270 tests covering all layers — services, repositories, routes, schemas, and end-to-end:

```bash
make test          # Run full test suite
make test-unit     # Unit tests only
make test-cov      # Tests with coverage report
```

## Production Deployment

FitTrack deploys to OCI using a blue-green strategy on Kubernetes (OKE).

### Build & Deploy

```bash
# Build production image
docker build -f docker/Dockerfile.prod -t oci.example.com/fittrack/api:v1.0.0 .

# Deploy via Helm
helm upgrade --install fittrack deploy/helm/fittrack \
  --namespace fittrack \
  -f deploy/helm/fittrack/values.yaml \
  --set image.tag=v1.0.0
```

### Infrastructure

```bash
# Provision OCI resources
cd deploy/terraform
terraform init
terraform plan
terraform apply
```

### Key Production Features

- **Structured JSON logging** with correlation IDs for request tracing
- **Tiered rate limiting**: Anonymous (10/min), User (100/min), Admin (500/min)
- **Security headers**: HSTS, X-Content-Type-Options, X-Frame-Options, CSP
- **GZip compression** for responses > 500 bytes
- **Health probes**: `/health/live` (liveness) + `/health/ready` (readiness)
- **Multi-stage Docker build** with non-root user, 4 uvicorn workers
- **Horizontal Pod Autoscaler** (2-10 replicas based on CPU/memory)

### Documentation

| Document | Description |
| -------- | ----------- |
| `docs/DEPLOYMENT.md` | Blue-green deployment guide with rollback procedures |
| `docs/ENVIRONMENT_VARIABLES.md` | All environment variables with descriptions |
| `docs/RATE_LIMITS.md` | API rate limit tiers and client best practices |
| `docs/BACKUP_RECOVERY.md` | Backup strategy and disaster recovery procedures |
| `docs/FitTrack-PRD-v1.0.md` | Product Requirements Document |

## License

Private — all rights reserved.
