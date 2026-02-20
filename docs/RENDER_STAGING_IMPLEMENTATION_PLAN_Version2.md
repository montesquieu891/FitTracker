# FitTrack — Plan para preparar Staging Deploy en Render (para pasar al agent)

## Objetivo
Preparar el repositorio para poder desplegar un entorno **staging** en **Render** usando el contenedor de producción (`docker/Dockerfile.prod`), sin romper el flujo local (Local Release Candidate sigue verde). El resultado debe incluir documentación y herramientas de validación (smoke tests) para que el deploy sea repetible.

## Contexto (estado actual)
- Backend: FastAPI (Python 3.12) con Oracle + Redis.
- Docker:
  - `docker/Dockerfile` (dev)
  - `docker/Dockerfile.prod` (prod, multi-stage)
  - `docker/docker-compose.yml` (Oracle + Redis + api)
- Health endpoints esperados: `/health`, `/health/live`, `/health/ready`
- No hay frontend React; existe una página de prueba en `static/` servida en dev.

## Alcance (in-scope)
1) Documentar un deploy de staging en Render (paso a paso).
2) Alinear comandos/targets para evitar confusión entre:
   - API corriendo en host (dev) vs API corriendo en Docker (compose)
3) Ajustes mínimos a `docker/docker-compose.yml` para dependencias correctas (oracle+redis).
4) Añadir un **smoke test HTTP** reutilizable tanto local como staging.
5) (Opcional) mejorar CI con un job “nightly integration” (no bloquear PRs).

## Fuera de alcance (out-of-scope)
- Construir frontend React.
- Cambiar de Oracle a Postgres.
- Implementar OCI/OKE full (Terraform/Helm) como destino final.

---

## Definition of Done (aceptación)

### Local (no se rompe)
- `cp .env.example .env`
- `make docker-up && make db-migrate && make db-seed && make dev` funciona en máquina limpia.
- `curl http://localhost:8000/health/live` → 200
- `curl http://localhost:8000/health/ready` → 200 con Oracle+Redis arriba.

### Render (staging)
- Render construye la imagen con `docker/Dockerfile.prod` y levanta servicio en puerto 8000.
- Healthcheck en Render apunta a `/health/live` y pasa.
- `/health/ready` refleja disponibilidad real de dependencias (DB/Redis).
- Existe un procedimiento documentado para correr migraciones en staging.

---

## Tareas concretas para el agent

### 1) Crear documentación de despliegue en Render
**Crear archivo:** `docs/RENDER_DEPLOYMENT.md`

Debe incluir:
- Crear “Web Service” en Render desde el repo.
- Runtime: Docker.
- Dockerfile: `docker/Dockerfile.prod`
- Port: `8000`
- Health check path recomendado: `/health/live`
- Variables de entorno mínimas para staging:
  - `APP_ENV=production`
  - `LOG_FORMAT=json`
  - `LOG_LEVEL=INFO`
  - `CORS_ORIGINS=<origen del frontend o *>` (staging)
  - `REDIS_URL=<Render Redis URL>`
  - `ORACLE_DSN`, `ORACLE_USER`, `ORACLE_PASSWORD` (si se usa Oracle externo)
- Nota explícita: Render no provee Oracle; si el backend es Oracle-only, se necesita Oracle externo (OCI Autonomous u otro).
- Cómo ejecutar migraciones en staging:
  - comando recomendado (ej. `python scripts/migrations.py`)
  - y/o target `make db-migrate` si aplica en el contenedor.
- Validación post-deploy (curl a health endpoints y `/docs` si aplica).

### 2) Alinear “modo host” vs “modo docker” (DX)
Actualizar **README** y/o **Makefile** para dejar claro:
- Modo recomendado para dev:
  - `make docker-up` levanta SOLO `oracle` y `redis`
  - `make dev` corre API en host (uvicorn)
- Modo alternativo:
  - `make docker-up-all` levanta `oracle`, `redis` y `api` por docker compose

Asegurar que los DSNs coinciden:
- host-run: `.env` usa `ORACLE_DSN=localhost:1521/FREEPDB1` y `REDIS_URL=redis://localhost:6379/0`
- docker-run: compose sobreescribe con `ORACLE_DSN=fittrack-oracle:1521/FREEPDB1` y `REDIS_URL=redis://fittrack-redis:6379/0`

### 3) Fix en docker-compose: `api` debe esperar a Oracle y Redis
En `docker/docker-compose.yml`:
- Agregar `oracle` en `depends_on` de `api` con `condition: service_healthy`
- Mantener `redis` igual.

Verificar el healthcheck de Oracle:
- Que realmente se vuelva `healthy` en un tiempo razonable.
- Si el healthcheck actual con `sqlplus` no es confiable, cambiarlo por uno que funcione con esa imagen (mantener simple y robusto).

### 4) Consistencia de configuración JWT (documentar o alinear)
Revisar `.env.example` y documentación:
- Si en el código se usa RS256 con llaves, documentar qué variables/paths se usan en staging.
- Si en dev se usa HS256, documentar “dev-only” y cómo se comporta en prod.
- No introducir secretos reales.

### 5) Agregar smoke test HTTP reutilizable (local + staging)
**Crear archivo:** `scripts/smoke_http.sh`

Requisitos:
- `BASE_URL` (default `http://localhost:8000`)
- retries/timeout (p.ej. 60–120s total)
- verificar:
  - `/health`
  - `/health/live`
  - `/health/ready`
  - opcional: `/docs` (si se decide que en prod/staging puede estar habilitado; si no, permitir skipping por flag)

Agregar target `make smoke` que ejecute el script.

### 6) (Opcional) CI: nightly integration (no bloquear PRs)
- Mantener CI “normal” liviano (unit + lint).
- Agregar workflow `nightly-integration.yml` que:
  - levante Oracle+Redis por compose
  - corra integration tests
  - timeout amplio por startup de Oracle
Esto debe ser opcional y no bloquear merges.

---

## Pasos de verificación (para el agente / reviewer)

### Verificación local
1) `cp .env.example .env`
2) `make docker-up`
3) `make db-migrate`
4) `make db-seed`
5) `make dev`
6) `make smoke`

### Verificación Docker prod build
- `docker build -f docker/Dockerfile.prod -t fittrack:prod .`

### Verificación staging (Render)
- Deploy del Web Service con Dockerfile prod
- `BASE_URL=https://<render-url> scripts/smoke_http.sh`

---

## Riesgos / notas
- Oracle 23ai container tiene startup lento; staging en Render debería conectarse a Oracle externo si se requiere estabilidad.
- Mantener el LRC verde es condición: cambios deben ser mínimos y no alterar el flujo local existente.