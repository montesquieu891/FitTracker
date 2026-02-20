.PHONY: setup dev test test-unit test-integration db-migrate db-seed db-reset lint format docker-up docker-up-all docker-down smoke clean worker-sync worker-leaderboard worker-drawing demo

# === First-time setup ===
setup:
	cp -n .env.example .env 2>/dev/null || true
	pip install -e ".[dev]"
	$(MAKE) docker-up
	@echo "Waiting for Oracle to start (up to 120s)..."
	@timeout 120 bash -c 'until python -c "import oracledb; c=oracledb.connect(user=\"fittrack\",password=\"FitTrack_Dev_2026!\",dsn=\"localhost:1521/FREEPDB1\"); c.close(); print(\"DB ready\")" 2>/dev/null; do sleep 5; done' || echo "Oracle may still be starting..."
	$(MAKE) db-migrate
	@echo "Setup complete! Run 'make dev' to start the server."

# === Development server ===
dev:
	uvicorn fittrack.main:app --host 0.0.0.0 --port 8000 --reload --app-dir src

# === Testing ===
test:
	python -m pytest tests/ -v --tb=short

test-unit:
	python -m pytest tests/unit/ -v --tb=short -m "not integration"

test-integration:
	python -m pytest tests/integration/ -v --tb=short -m "integration"

test-cov:
	python -m pytest tests/ -v --tb=short --cov=src/fittrack --cov-report=html --cov-report=term-missing

# === Database ===
db-migrate:
	python -c "from scripts.migrations import run_migrations; import oracledb; c=oracledb.connect(user='fittrack',password='FitTrack_Dev_2026!',dsn='localhost:1521/FREEPDB1'); print(run_migrations(c)); c.close()"

db-seed:
	python scripts/seed_data.py

db-reset:
	python -c "from scripts.migrations import drop_all_tables, run_migrations; import oracledb; c=oracledb.connect(user='fittrack',password='FitTrack_Dev_2026!',dsn='localhost:1521/FREEPDB1'); drop_all_tables(c); run_migrations(c); c.close()"
	$(MAKE) db-seed

# === Docker ===
# Recommended dev flow: bring up infra only, run API on host
docker-up:
	docker compose -f docker/docker-compose.yml up -d oracle redis

# Optional: bring up everything (oracle + redis + api) via compose
docker-up-all:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down

# === Workers ===
worker-sync:
	cd src && python -m fittrack.workers.run sync

worker-leaderboard:
	cd src && python -m fittrack.workers.run leaderboard

worker-drawing:
	cd src && python -m fittrack.workers.run drawing

# === Smoke test ===
smoke:
	@echo "Running HTTP smoke test (BASE_URL=$${BASE_URL:-http://localhost:8000})..."
	@if command -v bash >/dev/null 2>&1; then \
		bash scripts/smoke_http.sh; \
	elif command -v pwsh >/dev/null 2>&1; then \
		pwsh -ExecutionPolicy Bypass -File scripts/smoke_http.ps1; \
	else \
		powershell -ExecutionPolicy Bypass -File scripts/smoke_http.ps1; \
	fi

# === Code quality ===
lint:
	ruff check src/ tests/
	mypy src/fittrack/ --ignore-missing-imports

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

# === One-command demo ===
demo:
	@echo "=== FitTrack Local Demo ==="
	@echo "1/4  Starting infrastructure (Oracle + Redis + API)..."
	$(MAKE) docker-up
	@echo "2/4  Waiting for Oracle to be ready (up to 180s)..."
	@timeout 180 bash -c 'until python -c "import oracledb; c=oracledb.connect(user=\"fittrack\",password=\"FitTrack_Dev_2026!\",dsn=\"localhost:1521/FREEPDB1\"); c.close(); print(\"DB ready\")" 2>/dev/null; do sleep 5; done' || echo "WARNING: Oracle may still be starting..."
	@echo "3/4  Running migrations + seeding data..."
	$(MAKE) db-migrate
	$(MAKE) db-seed
	@echo "4/4  Starting API server..."
	@echo ""
	@echo "  Swagger UI:  http://localhost:8000/docs"
	@echo "  Health:      http://localhost:8000/health"
	@echo "  Test page:   http://localhost:8000/test"
	@echo ""
	uvicorn fittrack.main:app --host 0.0.0.0 --port 8000 --reload --app-dir src

# === Cleanup ===
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage
