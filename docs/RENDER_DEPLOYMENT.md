# FitTrack — Guía de despliegue en Render (staging)

Esta guía resume cómo desplegar el backend en **Render** usando el contenedor de producción y cómo verificarlo con el smoke test HTTP.

## 1) Crear el servicio en Render
- Tipo: **Web Service**
- Runtime: **Docker**
- Dockerfile: `docker/Dockerfile.prod`
- Port: `8000`
- Health check path: `/health/live`

## 2) Variables de entorno mínimas (staging)
- `APP_ENV=production`
- `LOG_FORMAT=json`
- `LOG_LEVEL=INFO`
- `CORS_ORIGINS=<origen del frontend o *>`
- `REDIS_URL=<Render Redis URL>`
- `ORACLE_DSN=<host:port/service>` (Oracle externo)
- `ORACLE_USER=<user>`
- `ORACLE_PASSWORD=<password>`
- `JWT_SECRET_KEY=<clave HS256 para staging>`
- `JWT_ALGORITHM=HS256` (valor actual en código)

> Nota: Render **no** provee Oracle. Se requiere Oracle externo (p. ej. OCI Autonomous). Ajusta `ORACLE_DSN`/`ORACLE_USER`/`ORACLE_PASSWORD` a esa instancia.

## 3) Construir y desplegar
Render construirá la imagen automáticamente desde `docker/Dockerfile.prod`. No se necesitan argumentos adicionales.

## 4) Migraciones en staging
Ejecuta las migraciones contra la base de datos de staging desde el contenedor:

```bash
python scripts/migrations.py
# o
make db-migrate
```

Corre el comando desde una shell del servicio en Render o como comando ad-hoc.

## 5) Smoke test post-deploy
Usa el script reutilizable:

```bash
BASE_URL="https://<render-url>" CHECK_DOCS=0 scripts/smoke_http.sh
```

Checks ejecutados:
- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- (opcional) `GET /docs` si `CHECK_DOCS=1` y la ruta está expuesta.

Si todos devuelven 200, el deploy de staging está listo.
