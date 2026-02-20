# FitTrack API Rate Limits

## Overview

FitTrack enforces per-client rate limits to protect the API from abuse and ensure fair usage. Rate limiting is implemented as middleware in the FastAPI application with a sliding-window counter backed by in-memory storage (development) or Redis (production).

## Rate Limit Tiers

| Tier | Limit | Scope | Description |
|------|-------|-------|-------------|
| **Anonymous** | 10 req/min | Per IP address | Unauthenticated requests (login, registration, public endpoints) |
| **Authenticated User** | 100 req/min | Per user ID | Standard authenticated users and premium subscribers |
| **Admin** | 500 req/min | Per user ID | Admin panel operations |

Rate limits are configurable via environment variables:

```bash
RATE_LIMIT_ANONYMOUS=10    # requests per minute
RATE_LIMIT_USER=100        # requests per minute
RATE_LIMIT_ADMIN=500       # requests per minute
```

## Rate Limit Headers

Every API response includes rate limit information in the headers:

| Header | Description | Example |
|--------|-------------|---------|
| `X-RateLimit-Limit` | Maximum requests allowed per window | `100` |
| `X-RateLimit-Remaining` | Requests remaining in current window | `87` |
| `X-RateLimit-Reset` | Unix timestamp when the window resets | `1706900400` |

## Rate Limit Exceeded Response

When a client exceeds their rate limit, the API returns:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 45
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1706900400

{
  "type": "about:blank",
  "title": "Too Many Requests",
  "status": 429,
  "detail": "Rate limit exceeded. Try again in 45 seconds.",
  "instance": "/api/v1/activities"
}
```

## Endpoint-Specific Behavior

### Exempt Endpoints

The following endpoints are **not** rate limited:

| Endpoint | Reason |
|----------|--------|
| `GET /health/live` | Kubernetes liveness probe |
| `GET /health/ready` | Kubernetes readiness probe |

### High-Traffic Endpoints

These endpoints are most likely to trigger rate limits under normal usage:

| Endpoint | Typical Usage Pattern |
|----------|----------------------|
| `POST /api/v1/auth/login` | Authentication attempts |
| `GET /api/v1/leaderboards/{tier}` | Frequent polling for rank updates |
| `GET /api/v1/activities` | Activity feed refreshes |
| `POST /api/v1/activities/sync` | Fitness tracker sync triggers |

## Client Best Practices

### 1. Respect Rate Limit Headers

```javascript
async function apiCall(url) {
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });

  if (response.status === 429) {
    const retryAfter = response.headers.get('Retry-After');
    await sleep(retryAfter * 1000);
    return apiCall(url);  // Retry
  }

  return response.json();
}
```

### 2. Use Exponential Backoff

For repeated 429 responses, implement exponential backoff:

```javascript
async function apiCallWithBackoff(url, attempt = 0) {
  const response = await fetch(url);

  if (response.status === 429) {
    const delay = Math.min(1000 * Math.pow(2, attempt), 60000);
    await sleep(delay);
    return apiCallWithBackoff(url, attempt + 1);
  }

  return response.json();
}
```

### 3. Cache Responses Client-Side

Reduce API calls by caching responses that don't change frequently:

- **Leaderboards**: Cache for 60 seconds (server refreshes every 5 minutes)
- **User profile**: Cache for 5 minutes
- **Drawing list**: Cache for 60 seconds

### 4. Batch Operations

Use bulk endpoints where available instead of making individual requests:

- `POST /api/v1/activities/sync` syncs all tracker data in one call
- `GET /api/v1/drawings?status=active` fetches all active drawings at once

## Testing Environment

In the testing environment (`APP_ENV=testing`), rate limiting is **disabled** to avoid interfering with automated tests.

## Monitoring

Rate limit violations are logged with structured fields:

```json
{
  "event": "rate_limit_exceeded",
  "client_ip": "203.0.113.42",
  "user_id": "a1b2c3d4",
  "tier": "user",
  "limit": 100,
  "path": "/api/v1/activities",
  "correlation_id": "req-abc123"
}
```

Administrators can monitor rate limit patterns through application logs using the `rate_limit_exceeded` event filter.
