# FitTrack Deployment Guide

## Overview

FitTrack uses a blue-green deployment strategy on Oracle Cloud Infrastructure (OCI) with Kubernetes (OKE). This ensures zero-downtime deployments with instant rollback capability.

## Architecture

```
                    ┌─────────────┐
                    │   OCI Load  │
                    │  Balancer   │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
       ┌──────▼──────┐          ┌──────▼──────┐
       │  Blue (v1)  │          │ Green (v2)  │
       │  Namespace  │          │  Namespace  │
       │  (active)   │          │ (standby)   │
       └──────┬──────┘          └──────┬──────┘
              │                         │
       ┌──────▼──────────────────────────▼──────┐
       │     Oracle Autonomous JSON DB          │
       │     + OCI Cache (Redis)                │
       └────────────────────────────────────────┘
```

## Prerequisites

- OCI CLI configured with appropriate credentials
- `kubectl` connected to OKE cluster
- Helm 3.x installed
- Container image pushed to OCI Container Registry
- Database migrations applied (see [Migration Strategy](#migration-strategy))

## Blue-Green Deployment Process

### 1. Prepare the New Version

```bash
# Build and push the new image
docker build -f docker/Dockerfile.prod -t oci.example.com/fittrack/api:v2.0.0 .
docker push oci.example.com/fittrack/api:v2.0.0
```

### 2. Deploy to Standby Environment (Green)

```bash
# Deploy new version to green namespace
helm upgrade --install fittrack-green deploy/helm/fittrack \
  --namespace fittrack-green \
  --create-namespace \
  --set image.tag=v2.0.0 \
  --set env.APP_ENV=production \
  --set ingress.enabled=false \
  -f deploy/helm/fittrack/values.yaml \
  -f deploy/helm/fittrack/values-prod.yaml
```

### 3. Run Smoke Tests Against Green

```bash
# Port-forward to green environment
kubectl port-forward -n fittrack-green svc/fittrack-green 8001:8000 &

# Run health checks
curl http://localhost:8001/health/live
curl http://localhost:8001/health/ready

# Run smoke test suite
APP_ENV=testing BASE_URL=http://localhost:8001 pytest tests/e2e/ -v
```

### 4. Switch Traffic to Green

```bash
# Update the service selector to point to green
kubectl patch service fittrack-lb -n fittrack \
  -p '{"spec":{"selector":{"deployment":"green"}}}'

# Or switch via Ingress annotation
kubectl annotate ingress fittrack-ingress -n fittrack \
  nginx.ingress.kubernetes.io/service-upstream=fittrack-green --overwrite
```

### 5. Verify Green is Serving Traffic

```bash
# Monitor error rates and latency
kubectl logs -n fittrack-green -l app=fittrack --tail=100 -f

# Check health endpoints through the load balancer
curl https://api.fittrack.example.com/health/live
curl https://api.fittrack.example.com/health/ready
```

### 6. Decommission Blue (Previous Version)

```bash
# After monitoring period (15-30 minutes), scale down blue
helm uninstall fittrack-blue -n fittrack-blue

# Keep namespace for next deployment cycle
# Blue becomes the standby for the next release
```

## Rollback Procedure

If issues are detected after switching to green:

```bash
# Immediate rollback: switch traffic back to blue
kubectl patch service fittrack-lb -n fittrack \
  -p '{"spec":{"selector":{"deployment":"blue"}}}'

# Verify blue is healthy
curl https://api.fittrack.example.com/health/ready

# Investigate green issues
kubectl logs -n fittrack-green -l app=fittrack --tail=500
```

**Rollback time target**: < 60 seconds (DNS-free, load balancer switch only).

## Migration Strategy

Database migrations must be **backward-compatible** to support blue-green:

1. **Additive only**: New columns with defaults, new tables, new indexes
2. **No destructive changes** during deployment: column drops happen in a follow-up release after both blue and green run the new schema
3. **Migration order**: Always migrate DB **before** deploying new application code

```bash
# Run migrations against production DB
APP_ENV=production alembic upgrade head

# Verify migration
APP_ENV=production alembic current
```

### Two-Phase Schema Changes

For breaking schema changes, use a two-phase approach:

| Phase | Release N | Release N+1 |
|-------|-----------|-------------|
| Add   | Add new column (nullable) | Remove old column |
| Rename | Add new column, write to both | Drop old column |
| Type change | Add new column with new type | Drop old column |

## Environment-Specific Configuration

| Environment | Namespace | Replicas | DB | Redis |
|-------------|-----------|----------|----|-------|
| Development | fittrack-dev | 1 | Oracle 23ai Free (Docker) | Redis 7 (Docker) |
| Staging | fittrack-staging | 2 | Autonomous JSON DB (Free Tier) | OCI Cache (1 node) |
| Production | fittrack-blue/green | 3+ | Autonomous JSON DB (Paid) | OCI Cache (3 nodes) |

## Monitoring During Deployment

Key metrics to watch during a blue-green switch:

- **HTTP error rate** (5xx responses) — should remain < 0.1%
- **Response latency** (p99) — should not spike above baseline
- **Health probe status** — both `/health/live` and `/health/ready`
- **Database connection pool** — active connections within limits
- **Redis cache hit rate** — no unexpected drops

## CI/CD Pipeline Integration

The GitHub Actions pipeline automates the deployment:

```yaml
# Simplified deployment flow
# 1. Lint + Test (on push/PR)
# 2. Build + Push image (on main merge)
# 3. Deploy to staging (automatic)
# 4. Deploy to production (manual approval)
# 5. Smoke tests
# 6. Traffic switch
```

See `.github/workflows/ci.yml` for the full pipeline definition.

## Disaster Recovery

In case of complete environment failure:

1. Terraform provisions new infrastructure: `cd deploy/terraform && terraform apply`
2. Restore DB from automatic backup (see `docs/BACKUP_RECOVERY.md`)
3. Deploy application via Helm
4. Update DNS records if necessary
5. Verify all health endpoints

## Checklist

Before each production deployment:

- [ ] All tests passing in CI
- [ ] Database migration tested in staging
- [ ] Migration is backward-compatible
- [ ] Container image built and pushed
- [ ] Staging deployment verified
- [ ] On-call engineer notified
- [ ] Rollback plan confirmed
- [ ] Monitoring dashboards open
