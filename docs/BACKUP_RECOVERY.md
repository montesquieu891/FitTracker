# FitTrack Backup & Recovery Procedures

## Overview

FitTrack uses Oracle Autonomous JSON Database on OCI, which provides automated backups. This document covers backup strategies, recovery procedures, and disaster recovery planning.

## Backup Strategy

### Automatic Backups (Oracle Autonomous DB)

Oracle Autonomous Database includes automatic backups at no additional cost:

| Backup Type | Frequency | Retention | RPO |
|-------------|-----------|-----------|-----|
| Incremental | Daily | 60 days | 24 hours |
| Full | Weekly | 60 days | 7 days |
| Archive Log | Continuous | 60 days | Near-zero |

Automatic backups are managed entirely by OCI — no manual configuration required.

### Manual Backups

Create manual backups before major deployments or schema changes:

```bash
# Create a manual backup via OCI CLI
oci db autonomous-database-backup create \
  --autonomous-database-id <db-ocid> \
  --display-name "pre-migration-v2.0.0-$(date +%Y%m%d)" \
  --type FULL

# List existing backups
oci db autonomous-database-backup list \
  --autonomous-database-id <db-ocid> \
  --output table
```

### Application-Level Backups

For data export and cross-region backup:

```bash
# Export critical tables via Oracle Data Pump
expdp fittrack_app/<password>@fittrack_prod_tp \
  schemas=FITTRACK \
  directory=DATA_PUMP_DIR \
  dumpfile=fittrack_backup_%U.dmp \
  logfile=fittrack_export.log \
  parallel=4 \
  compression=ALL

# Upload to Object Storage
oci os object put \
  --bucket-name fittrack-backups-prod \
  --file fittrack_backup_01.dmp \
  --name "$(date +%Y/%m/%d)/fittrack_backup_01.dmp"
```

### Redis Cache

Redis data is ephemeral cache — no backup required. The cache rebuilds automatically from the database:

- **Leaderboard cache**: Refreshed every 5 minutes by the background worker
- **Session data**: Users re-authenticate if cache is lost (JWT-based auth is stateless)

## Recovery Procedures

### Scenario 1: Point-in-Time Recovery (Data Corruption)

Restore the database to a specific point in time before the corruption occurred:

```bash
# Restore to a specific timestamp
oci db autonomous-database restore \
  --autonomous-database-id <db-ocid> \
  --timestamp "2025-01-15T10:30:00Z"
```

**Steps:**
1. Identify the timestamp of data corruption from logs
2. Stop the application (scale replicas to 0)
3. Perform point-in-time restore
4. Verify data integrity
5. Restart the application
6. Verify application health via `/health/ready`

**Expected recovery time**: 15-60 minutes depending on database size.

### Scenario 2: Full Database Restore (Complete Loss)

Restore from the most recent full backup:

```bash
# List available backups
oci db autonomous-database-backup list \
  --autonomous-database-id <db-ocid> \
  --sort-by TIMECREATED \
  --sort-order DESC

# Restore from backup
oci db autonomous-database restore-from-backup \
  --autonomous-database-id <db-ocid> \
  --backup-id <backup-ocid>
```

**Steps:**
1. Scale down all application pods
2. Restore from backup
3. Run any pending Alembic migrations: `alembic upgrade head`
4. Verify data integrity with spot checks
5. Scale up application pods
6. Monitor error rates for 30 minutes

**Expected recovery time**: 30-120 minutes.

### Scenario 3: Region Failover (Disaster Recovery)

If the primary OCI region is unavailable:

1. **Provision new infrastructure** in the DR region:
   ```bash
   cd deploy/terraform
   terraform workspace select dr
   terraform apply -var="region=us-phoenix-1"
   ```

2. **Restore database** from cross-region backup or standby:
   ```bash
   # If using Autonomous Data Guard (cross-region)
   oci db autonomous-database failover \
     --autonomous-database-id <standby-db-ocid>
   ```

3. **Deploy application** to new OKE cluster:
   ```bash
   helm install fittrack deploy/helm/fittrack \
     --namespace fittrack \
     -f deploy/helm/fittrack/values-prod.yaml \
     --set image.tag=<current-version>
   ```

4. **Update DNS** to point to the new region's load balancer

**Target RTO**: 4 hours | **Target RPO**: 1 hour (with cross-region standby)

### Scenario 4: Accidental Table Drop

```sql
-- Oracle Flashback: recover dropped table (within undo retention)
FLASHBACK TABLE fittrack.activities TO BEFORE DROP;

-- Or query data as it existed at a past time
SELECT * FROM fittrack.users AS OF TIMESTAMP
  TO_TIMESTAMP('2025-01-15 10:00:00', 'YYYY-MM-DD HH24:MI:SS');
```

### Scenario 5: Redis Cache Failure

Redis is a cache layer — no data loss occurs on Redis failure.

1. Application falls back to database queries (higher latency)
2. Restart/replace Redis: `kubectl rollout restart deployment/redis`
3. Cache rebuilds automatically via background workers
4. Monitor until cache hit rate normalizes

## Backup Verification

### Monthly Backup Test

Perform a restore test monthly to verify backup integrity:

1. Create a test Autonomous DB instance from the latest backup
2. Connect and verify row counts for critical tables
3. Run a subset of integration tests against the restored DB
4. Document results in the backup test log
5. Terminate the test instance

```bash
# Create clone from backup for verification
oci db autonomous-database create-from-backup \
  --compartment-id <compartment-ocid> \
  --display-name "backup-verify-$(date +%Y%m)" \
  --backup-id <backup-ocid> \
  --cpu-core-count 1 \
  --data-storage-size-in-tbs 1 \
  --admin-password <temp-password>
```

### Critical Tables to Verify

| Table | Verification Query |
|-------|-------------------|
| `users` | `SELECT COUNT(*) FROM users WHERE status = 'active'` |
| `point_transactions` | `SELECT SUM(points) FROM point_transactions WHERE type = 'earn'` |
| `drawings` | `SELECT COUNT(*) FROM drawings WHERE status = 'completed'` |
| `tickets` | `SELECT COUNT(*) FROM tickets` |
| `prize_fulfillments` | `SELECT COUNT(*) FROM prize_fulfillments WHERE status != 'delivered'` |

## Retention Policy

| Data Type | Retention | Storage |
|-----------|-----------|---------|
| Automatic DB backups | 60 days | OCI (included) |
| Manual DB backups | 1 year | OCI Object Storage |
| Data Pump exports | 1 year | OCI Object Storage (Archive) |
| Application logs | 90 days | OCI Logging |
| Audit logs | 7 years | OCI Object Storage (Archive) |

## Contacts

| Role | Responsibility |
|------|---------------|
| On-call Engineer | First responder for incidents |
| Database Admin | Backup/restore execution |
| Platform Lead | DR decision authority |
| Security Lead | Data breach assessment |
