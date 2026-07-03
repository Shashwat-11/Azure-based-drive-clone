# Observability

This document describes the observability strategy for the Drive cloud storage platform, covering logging, tracing, metrics, health checks, and monitoring integrations.

---

## Structured Logging

### Implemented

The application uses **structlog** to generate structured JSON logs on stdout. Every log entry is a valid JSON object with a consistent schema:

```json
{
  "message": "request_started",
  "level": "info",
  "timestamp": "2026-07-01T12:00:00.000000Z",
  "logger": "app.middleware.request_logger",
  "method": "GET",
  "path": "/api/v1/health",
  "client_ip": "127.0.0.1",
  "trace_id": "a1b2c3d4-..."
}
```

**Processors** (configured in `app/core/logging_config.py`):

| Processor | Purpose |
|---|---|
| `merge_contextvars` | Propagate context across async boundaries |
| `filter_by_level` | Respect log level configuration |
| `add_log_level` | Include `level` field (e.g., "info", "error") |
| `add_logger_name` | Include Python module name |
| `TimeStamper` | ISO 8601 timestamps in UTC |
| `StackInfoRenderer` | Include stack traces for exceptions |
| `format_exc_info` | Format exception information |
| `UnicodeDecoder` | Handle unicode byte sequences |
| `JSONRenderer` | Serialize to JSON with sorted keys |

**Log levels**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (configurable via `LOG_LEVEL`).

---

## Correlation IDs

### Implemented

Every HTTP request receives a unique correlation ID (`X-Request-ID` / `X-Trace-ID` response headers) for end-to-end tracing:

1. **Incoming request**: `RequestLoggerMiddleware` extracts `X-Request-ID` from request headers, or generates a new UUIDv4.
2. **Propagation**: The trace ID is stored in `scope["state"]["trace_id"]` and included in every log entry from that request.
3. **Response headers**: Both `X-Request-ID` and `X-Trace-ID` are returned in the response.
4. **Downstream calls**: When the application makes calls to external services (PostgreSQL, Redis, Azure), the trace ID can be passed via request metadata.

---

## Request Lifecycle

Every HTTP request generates at least two log entries:

```
request_started  →  [processing]  →  request_completed
```

| Field | request_started | request_completed |
|---|---|---|
| `method` | GET / POST / etc. | Same |
| `path` | `/api/v1/...` | Same |
| `client_ip` | Remote address | Same |
| `trace_id` | Correlation UUID | Same |
| `status_code` | — | HTTP status |
| `duration_ms` | — | Wall-clock milliseconds |

Additional log entries (from services, repositories, auth utilities) are interleaved between these two, all sharing the same `trace_id`.

---

## Health Endpoints

### Implemented

| Endpoint | Type | Checks | Response | Purpose |
|---|---|---|---|---|
| `GET /api/v1/health` | Basic | None (process alive) | `{"success": true, "message": "Service is running", "code": "HEALTHY"}` | Load balancer health probe |
| `GET /api/v1/ready` | Readiness | Database (SELECT 1), Redis (PING), Azure Blob (container properties) | `{"success": bool, "code": "READY"|"NOT_READY", "checks": {...}}` | Kubernetes readiness probe |
| `GET /api/v1/live` | Liveness | None | `{"success": true, "message": "Service is alive", "code": "ALIVE"}` | Kubernetes liveness probe |

**Readiness check behavior**:

- Each dependency is checked independently.
- Failures are captured individually (e.g., "database": "healthy", "redis": "unhealthy: ...").
- The overall `success` is `true` only when all checks pass.
- Azure storage check returns `healthy` when Azure is not configured (graceful degradation).

---

## Metrics

### Planned

Application-level metrics will be exposed on a `/metrics` endpoint (Prometheus format) using `prometheus-fastapi-instrumentator` or OpenTelemetry SDK:

| Metric | Type | Labels |
|---|---|---|
| `http_requests_total` | Counter | `method`, `path`, `status_code` |
| `http_request_duration_seconds` | Histogram | `method`, `path` |
| `http_requests_in_flight` | Gauge | — |
| `db_query_duration_seconds` | Histogram | `operation`, `table` |
| `blob_upload_bytes_total` | Counter | `container` |
| `blob_download_bytes_total` | Counter | `container` |
| `auth_failures_total` | Counter | `reason` (wrong_password, not_found, deactivated) |
| `rate_limit_exceeded_total` | Counter | `path` |

**Current status**: The infrastructure for exposing metrics is not yet implemented. Metrics collection will be added as part of the Azure Monitor integration.

---

## Distributed Tracing

### Current State

- Correlation IDs (`trace_id`) are propagated across the request lifecycle, enabling log-based tracing.
- Raw ASGI middleware captures the `scope`, sent and received messages.
- No distributed tracing headers (W3C Trace Context, B3) are propagated to downstream services.

### Planned: OpenTelemetry Integration

**Goal**: Enable end-to-end distributed tracing across FastAPI, PostgreSQL, Redis, and Azure Blob Storage.

**Plan**:

1. Install `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-instrumentation-redis`, `opentelemetry-instrumentation-httpx`.
2. Configure `opentelemetry-exporter-azure-monitor` as the span exporter.
3. Map the existing `trace_id` to OpenTelemetry's `trace_id` (or replace with OTel-generated IDs).
4. Inject trace context headers (`traceparent`, `tracestate`) into outgoing HTTP requests.
5. Propagate trace context to Azure SDK calls via `azure-core-tracing-opentelemetry`.

---

## Azure Monitor Integration

### Planned

Azure resources to be configured for observability:

| Azure Service | Purpose | Status |
|---|---|---|
| Application Insights | Application performance monitoring, request telemetry, exception tracking, dependency monitoring | Planned |
| Log Analytics Workspace | Centralized log storage and querying (Kusto Query Language) | Planned |
| Azure Monitor Metrics | Infrastructure metrics (CPU, memory, disk, network) from Azure Container Apps | Planned |
| Azure Monitor Alerts | Alert rules based on metric thresholds and log queries | Planned |

**Integration points**:

1. **Logs**: Structured JSON on stdout → Azure Monitor agent → Log Analytics.
2. **Metrics**: OpenTelemetry SDK → Azure Monitor exporter → Application Insights.
3. **Traces**: OpenTelemetry SDK → Azure Monitor exporter → Application Insights (distributed tracing map).
4. **Alerts**: Azure Monitor alert rules on Application Insights metrics (error rate >5%, latency p95 >2s, etc.).

---

## Future Dashboards

### Planned: Application Insights Workbook

A shared Azure Workbook for the Drive platform will include:

- **Overview**: Request rate, error rate, average latency, active users.
- **API Performance**: P50/P95/P99 latency per endpoint, request count by status code.
- **Database**: Query duration percentiles, connection pool utilization, slow queries.
- **Storage**: Upload/download throughput, blob operation latency, error rates.
- **Authentication**: Login success/failure rate, token refresh rate, rate limit hits.
- **Infrastructure**: CPU, memory, instance count (from Container Apps).

**TODO**: Workbook JSON template to be created once Application Insights is integrated.

---

## Future Alerts

**Planned**: Azure Monitor alert rules triggered on:

| Alert | Condition | Severity |
|---|---|---|
| High error rate | `requests/failed > 10% for 5 minutes` | Sev 2 |
| High latency | `requests/duration p95 > 2s for 5 minutes` | Sev 3 |
| Database connection exhaustion | `active connections > 80% of pool max` | Sev 2 |
| Blob storage errors | `storage errors > 5 in 5 minutes` | Sev 1 |
| Authentication spike | `auth failures > 50 in 1 minute` | Sev 3 |
| Rate limit spike | `rate limit hits > 100 in 1 minute` | Sev 3 |
| Instance down | `liveness probe failure > 3 consecutive` | Sev 1 |

Alerts will be routed to:
- Email (development/staging)
- Microsoft Teams or Slack (production)
- PagerDuty or Opsgenie (production, Sev 1/2)

---

## Performance Monitoring

### Current State

- Request duration is logged on every request (`duration_ms` field).
- Database query performance is not instrumented (no query-level timing).
- No infrastructure-level metrics collection (CPU, memory).

### Planned

- SQLAlchemy query logging with timing (enabled via `DB_ECHO=true` in development).
- Application Insights automatic dependency tracking (includes PostgreSQL and Redis call durations).
- `asyncpg` slow query logging via connection hooks.
- Azure Container Apps built-in CPU/memory metrics.

---

## Error Monitoring

### Implemented

- All unhandled exceptions are caught by `unhandled_exception_handler` and logged with full traceback (structured JSON).
- `AppError` subclasses are caught by `app_error_handler` and logged with context (path, method, trace_id, error code).
- Request validation errors are caught by `validation_exception_handler` with detailed field-level error information.
- Every error response includes a `trace_id` that references the corresponding log entry.

### Planned

- Application Insights automatically collects unhandled exceptions and provides error grouping (Smart Detection).
- Custom application error events will be tracked as Application Insights custom events with dimensions (error code, endpoint, user role).

---

## Audit Logging

### Implemented

Security-relevant events are logged at `INFO` or `WARNING` level, each containing a `trace_id` for end-to-end correlation:

- User registration
- Login (success and failure)
- Token creation, refresh, and revocation
- Logout
- File upload, download, and deletion
- Folder creation and deletion
- All events include `trace_id`, `user_id`, and relevant resource identifiers

### Planned

A dedicated audit log table (`audit_logs`) will record:

- Permission changes (who changed what for whom)
- File/folder operations (create, delete, move, share)
- Administrative actions (user deactivation, role changes)
- Failed authorization attempts

Audit logs will be:
- Immutable (append-only table, no update or delete)
- Indexed by user, resource, and timestamp
- Retained for a configurable period
- Exportable to Azure Log Analytics for long-term retention

---

## Current Observability Coverage

| Capability | Status |
|---|---|
| Structured JSON logging | Implemented |
| Correlation IDs (request tracing) | Implemented |
| Request lifecycle logging | Implemented |
| Health checks (/health, /ready, /live) | Implemented |
| Error logging with tracebacks | Implemented |
| Security event logging | Implemented |
| Metrics (Prometheus endpoint) | Not implemented |
| Distributed tracing (OpenTelemetry) | Not implemented |
| Azure Application Insights | Not integrated |
| Azure Log Analytics | Not integrated |
| Dashboards | Not implemented |
| Alerts | Not implemented |
| Audit logging (dedicated) | Not implemented |
| Performance profiling | Not implemented |

---

## Missing Observability Features

Priority-ordered list of features to implement:

1. **Metrics endpoint** (`/metrics`) with Prometheus format — enables Grafana dashboards and Azure Monitor metrics. **Priority: High**.
2. **Application Insights SDK integration** — automatic dependency tracking, request telemetry, exception grouping. **Priority: High**.
3. **Azure Log Analytics integration** — centralized log storage with KQL querying. **Priority: High**.
4. **OpenTelemetry distributed tracing** — end-to-end trace visualization. **Priority: Medium**.
5. **Audit log table** — immutable record of all sensitive operations. **Priority: Medium**.
6. **Azure Monitor alerts** — automated alerting on error rates, latency, and availability. **Priority: Medium**.
7. **Dashboards** — Azure Workbook for operational visibility. **Priority: Low**.
8. **Slow query logging** — identify and optimize expensive database queries. **Priority: Low**.
