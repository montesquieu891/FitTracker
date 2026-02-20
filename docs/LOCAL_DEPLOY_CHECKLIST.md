# FitTrack — Checklist para “usable localmente” + pruebas asociadas

Objetivo: que desde un *fresh clone* puedas levantar FitTrack y usarlo localmente (Swagger + endpoints + seed + workers) con señales claras de salud y un set mínimo de pruebas que lo garantice.

---

## Definición de “local usable” (criterio de salida)

Se considera “local usable” cuando se cumple TODO:

- [x] `cp .env.example .env` (sin editar) + `make docker-up` levanta Oracle + Redis (y opcionalmente API) sin errores
- [x] `make db-migrate` aplica migraciones sin intervención manual
- [x] `make db-seed` carga datos mínimos (o "demo") sin fallar
- [x] API corriendo en `http://localhost:8000`
- [x] `/health` devuelve 200
- [x] `/health/live` devuelve 200
- [x] `/health/ready` devuelve 200 cuando Oracle y Redis están OK (y !=200 si no)
- [x] `/docs` carga (Swagger)
- [x] (opcional) `/test` carga en dev y NO carga en prod

---

## A. Infraestructura local (Docker) — checklist + tests

### A1) Docker Compose: Oracle + Redis listos antes del API
- [x] `docker/docker-compose.yml` tiene healthchecks que funcionan para `oracle` y `redis`
- [x] `api` **depende de** `oracle` y `redis` (si `api` se corre por compose)
- [x] Puertos expuestos: Oracle `1521`, Redis `6379`, API `8000`

**Pruebas**
- Manual:
  - [x] `docker compose -f docker/docker-compose.yml up -d oracle redis`
  - [x] `docker ps` muestra ambos containers "Up (healthy)"
  - [x] `docker exec -it fittrack-redis redis-cli ping` → `PONG`
- Automatizable (smoke script):
  - [x] Script `scripts/smoke_local.sh` espera a que los healthchecks estén `healthy` y falla si pasan X minutos

### A2) `.env` y defaults
- [x] `.env.example` contiene defaults dev seguros y consistentes con el código
- [x] `ORACLE_DSN` apunta a `localhost:1521/FREEPDB1` para host-run
- [x] `REDIS_URL` apunta a `redis://localhost:6379/0` para host-run

**Pruebas**
- [x] Unit: "config loads" (Pydantic Settings) con `.env.example` sin valores faltantes
- [x] Manual: `python -c "from fittrack.core.config import settings; print(settings.APP_ENV)"`

---

## B. Backend API (FastAPI) — checklist + tests

### B1) Arranque del API
- [x] `make dev` levanta `uvicorn fittrack.main:app` en 0.0.0.0:8000 (o localhost:8000)
- [x] El API NO crashea si Oracle tarda; readiness refleja estado real (ideal)

**Pruebas**
- Manual:
  - [x] `make dev` y ver log “Application startup complete”
- Automatizable:
  - [x] `curl -sf http://localhost:8000/health` → 0
  - [x] `curl -sf http://localhost:8000/health/live` → 0
  - [x] `curl -sf http://localhost:8000/health/ready` → 0 tras levantar DB/Redis

### B2) Health endpoints con semántica correcta
- [x] `/health` = ok básico
- [x] `/health/live` = proceso vivo (no depende de DB)
- [x] `/health/ready` = listo para servir (depende de DB y/o Redis)

**Pruebas**
- [x] Integration: test que `/health/live` responde 200 aunque DB no esté
- [x] Integration: test que `/health/ready` responde !=200 si DB no está conectable
- [x] Integration: test que `/health/ready` responde 200 si DB responde query simple

### B3) Swagger disponible en dev
- [x] `/docs` disponible cuando `APP_ENV=development`

**Pruebas**
- [x] Integration: GET `/docs` contiene “Swagger UI”

---

## C. Base de datos (Oracle) — checklist + tests

### C1) Migraciones idempotentes
- [x] `make db-migrate` se puede correr múltiples veces sin romper
- [x] Migraciones crean tablas/índices esperados

**Pruebas**
- [x] Integration: `scripts/migrations.py` corre 2 veces seguidas y termina OK
- [x] Integration: query de verificación de 3-5 tablas clave (ej: `users`, `profiles`, `activities`, `drawings`, `tickets`)
- [x] Integration: verifica al menos 1 índice importante existe (ej: `users_email`)

### C2) Seed mínimo para demo local
- [x] `make db-seed` crea usuarios y entidades mínimas para navegar endpoints
- [x] Seed es razonablemente rápido (< 60s en máquina normal)

**Pruebas**
- [x] Integration: luego de seed, `GET /api/v1/users` devuelve >0
- [x] Integration: luego de seed, existe al menos 1 drawing y 1 sponsor

---

## D. Autenticación mínima para uso local — checklist + tests

### D1) Flujo básico email/password
- [x] `POST /api/v1/auth/register` crea usuario (dev)
- [x] `POST /api/v1/auth/login` devuelve access token
- [x] Endpoints protegidos exigen JWT

**Pruebas**
- [x] Integration: register → login → llamar endpoint protegido (ej. `/api/v1/users/me`) con Bearer token
- [x] Integration: endpoint protegido sin token → 401/403

> Nota: OAuth social (Google/Apple) puede quedar stubeado en local al inicio, siempre que el core funcione.

---

## E. Workers locales — checklist + tests

### E1) Comandos para correr workers manualmente
- [x] `make worker-sync` (o comando equivalente)
- [x] `make worker-leaderboard`
- [x] `make worker-drawing`

**Pruebas**
- [x] Integration: ejecutar worker una vez contra DB seeded y comprobar que:
  - [x] sync no crashea si no hay conexiones OAuth reales (debe degradar con logs)
  - [x] leaderboard recalcula cache (si Redis disponible)
  - [x] drawing worker no ejecuta nada si no hay drawings due (comportamiento estable)

---

## F. “Dev-only” features (test page, endpoints dev) — checklist + tests

### F1) Test page y endpoints dev solo en development
- [x] `/test` existe en dev
- [x] `/api/v1/dev/*` existe en dev
- [x] En `APP_ENV=production` deben devolver 404 o 403

**Pruebas**
- [x] Integration: con `APP_ENV=production`, GET `/test` → 404/403
- [x] Integration: con `APP_ENV=production`, POST `/api/v1/dev/seed` → 404/403
- [x] Integration: con `APP_ENV=development`, funcionan

---

## G. “One-command local demo” (script) — checklist + tests

### G1) Script/target para demo local
- [x] `make demo` hace:
  - docker-up (infra)
  - db-migrate
  - db-seed (mínimo)
  - arranca API (o te indica el comando)
- [x] `scripts/demo.ps1` — Windows/PowerShell equivalent

**Pruebas**
- [x] Manual: `make demo` en fresh clone (verified via dry-run + individual steps)
- [ ] Automatizable: en CI (opcional) un job nightly que construya y haga smoke test

---

## H. Checklist de pruebas recomendadas (suite mínima)

### H1) Unit (rápidas, sin DB)
- [x] Config loads
- [x] Servicios puros: points, tiers, anti_gaming
- [x] JWT encode/decode y password hashing
- [x] Validaciones (edad/estado)

Comando:
- [x] `make test-unit` o `pytest -m "not integration"`

### H2) Integration (requieren Oracle+Redis)
- [x] Health ready/live semantics
- [x] Migrations idempotent
- [x] Seed + sanity API reads
- [x] Auth basic flow con DB real

Comando:
- [x] `make test-integration` o `pytest -m integration`

### H3) Smoke local (cero “pytest”, solo curl)
- [x] `/health`
- [x] `/health/live`
- [x] `/health/ready`
- [x] `/docs`

Comando:
- [x] `scripts/smoke_local.sh`

---

## Plan de ejecución (orden recomendado)

1) [x] Fresh clone + `cp .env.example .env`
2) [x] `make docker-up` (infra)
3) [x] `make db-migrate`
4) [x] `make db-seed`
5) [x] `make dev`
6) [x] Smoke: `scripts/smoke_local.sh`
7) [x] Suite: `make test` (o unit primero)

---

## Anomalías a vigilar (cosas que suelen romper local)

- Oracle “healthy” tarda 2–5 minutos la primera vez (start_period en compose)
- `api` arrancando antes de DB si falta `depends_on: oracle`
- `.env.example` (HS256) vs implementación real (RS256) — alinear o documentar
- `ORACLE_DSN` distinto si corres API dentro de Docker vs en host