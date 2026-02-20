# FitTrack Environment Variables

All configuration is managed through environment variables. No secrets should be committed to version control.

## Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_ENV` | Yes | `development` | Environment mode: `development`, `testing`, or `production` |
| `SECRET_KEY` | Yes | `dev-secret-key-change-in-production` | Application secret for session signing and CSRF. **Must be changed in production.** Use a 64+ character random string. |
| `LOG_LEVEL` | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FORMAT` | No | `text` | Log output format: `text` (human-readable) or `json` (structured, for production) |
| `CORS_ORIGINS` | No | `*` | Comma-separated list of allowed CORS origins. Example: `https://fittrack.com,https://admin.fittrack.com`. Use `*` only in development. |

## Rate Limiting

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RATE_LIMIT_ANONYMOUS` | No | `10` | Requests per minute for unauthenticated clients (per IP) |
| `RATE_LIMIT_USER` | No | `100` | Requests per minute for authenticated users |
| `RATE_LIMIT_ADMIN` | No | `500` | Requests per minute for admin users |

## Database (Oracle)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ORACLE_DSN` | Yes | `localhost:1521/FREEPDB1` | Oracle connection string. Format: `host:port/service_name` |
| `ORACLE_USER` | Yes | `fittrack` | Oracle database username |
| `ORACLE_PASSWORD` | Yes | `FitTrack_Dev_2026!` | Oracle database password. **Change in production.** |
| `ORACLE_POOL_MIN` | No | `2` | Minimum connections in the Oracle connection pool |
| `ORACLE_POOL_MAX` | No | `10` | Maximum connections in the Oracle connection pool |
| `ORACLE_POOL_INCREMENT` | No | `1` | Number of connections to add when pool needs to grow |

## Cache (Redis)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis connection URL. Format: `redis://[:password@]host:port/db` |

## Authentication (JWT)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_PRIVATE_KEY` | Yes | (dev key) | RSA private key (PEM format) for signing JWTs. For RS256 algorithm. |
| `JWT_PUBLIC_KEY` | Yes | (dev key) | RSA public key (PEM format) for verifying JWTs. |
| `JWT_ALGORITHM` | No | `RS256` | JWT signing algorithm |
| `JWT_EXPIRATION_MINUTES` | No | `30` | Access token expiration time in minutes |
| `JWT_REFRESH_EXPIRATION_DAYS` | No | `7` | Refresh token expiration time in days |

## OAuth Providers

### Google Fit

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_FIT_CLIENT_ID` | Yes* | — | Google OAuth 2.0 client ID for Google Fit API |
| `GOOGLE_FIT_CLIENT_SECRET` | Yes* | — | Google OAuth 2.0 client secret |

### Fitbit

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FITBIT_CLIENT_ID` | Yes* | — | Fitbit OAuth 2.0 client ID |
| `FITBIT_CLIENT_SECRET` | Yes* | — | Fitbit OAuth 2.0 client secret |

### Apple (Future - v1.1)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APPLE_CLIENT_ID` | No | — | Apple Sign-In client ID |
| `APPLE_CLIENT_SECRET` | No | — | Apple Sign-In client secret |

> *Required for fitness tracker sync functionality. Not required for basic application startup.

## Production Configuration Example

```bash
# Application
APP_ENV=production
SECRET_KEY=your-64-char-cryptographically-random-secret-key-here-change-me!!
LOG_LEVEL=INFO
LOG_FORMAT=json
CORS_ORIGINS=https://fittrack.com,https://admin.fittrack.com

# Rate Limiting
RATE_LIMIT_ANONYMOUS=10
RATE_LIMIT_USER=100
RATE_LIMIT_ADMIN=500

# Database
ORACLE_DSN=adb.us-ashburn-1.oraclecloud.com:1522/fittrack_prod_tp
ORACLE_USER=fittrack_app
ORACLE_PASSWORD=<strong-production-password>
ORACLE_POOL_MIN=4
ORACLE_POOL_MAX=20
ORACLE_POOL_INCREMENT=2

# Cache
REDIS_URL=redis://fittrack-cache.redis.us-ashburn-1.oci.oraclecloud.com:6379/0

# JWT Keys (use actual PEM-formatted keys)
JWT_PRIVATE_KEY=<RSA-private-key-PEM>
JWT_PUBLIC_KEY=<RSA-public-key-PEM>
JWT_EXPIRATION_MINUTES=15
JWT_REFRESH_EXPIRATION_DAYS=7

# OAuth
GOOGLE_FIT_CLIENT_ID=<google-client-id>.apps.googleusercontent.com
GOOGLE_FIT_CLIENT_SECRET=<google-client-secret>
FITBIT_CLIENT_ID=<fitbit-client-id>
FITBIT_CLIENT_SECRET=<fitbit-client-secret>
```

## Generating Secrets

```bash
# Generate a random SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Generate RS256 JWT key pair
openssl genrsa -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
```

## Kubernetes Secrets

For Kubernetes deployments, store sensitive variables in a Secret:

```bash
kubectl create secret generic fittrack-secrets \
  --from-literal=SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
  --from-literal=ORACLE_DSN="adb.us-ashburn-1.oraclecloud.com:1522/fittrack_prod_tp" \
  --from-literal=ORACLE_USER="fittrack_app" \
  --from-literal=ORACLE_PASSWORD="<password>" \
  --from-literal=REDIS_URL="redis://cache:6379/0" \
  --from-file=JWT_PRIVATE_KEY=jwt_private.pem \
  --from-file=JWT_PUBLIC_KEY=jwt_public.pem \
  --namespace fittrack
```

Non-sensitive configuration is set via the Helm chart `values.yaml` `env` block. See `deploy/helm/fittrack/values.yaml`.
