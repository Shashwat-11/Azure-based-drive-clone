# Handover Document — Drive Cloud Storage Platform

## Project Summary

**Drive** is a production-grade cloud storage platform (Google Drive clone) built with:

- **Backend**: FastAPI (Python 3.13), SQLAlchemy 2.x (async), PostgreSQL 16, Redis 7, Azure Blob Storage
- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS
- **Infrastructure**: Terraform (azurerm v4.80.0, azapi v2.10.0), Azure Container Apps, GitHub Actions
- **Observability**: OpenTelemetry (App Insights), structlog, Prometheus metrics

**Repository**: `github.com/Shashwat-11/Azure-based-drive-clone`

## What Was Done This Session

### Bugs Found and Fixed

1. **PostCSS config breaking Next.js build** (`frontend/postcss.config.mjs`)
   - File used `.mjs` extension (ES module) but contained `module.exports` (CommonJS)
   - Rename: `postcss.config.mjs` → `postcss.config.js`

2. **Dockerfile hiding build failures** (`frontend/Dockerfile`)
   - Had `npm run build || (mkdir -p .next/standalone .next/static && echo "skipped")`
   - Removed the fallback — build failures now propagate correctly
   - Removed redundant `COPY public/` (Next.js standalone bundles `public/`)

3. **OpenTelemetry `trace.sampling` removed** (`backend/app/core/otel.py`)
   - `trace.sampling.TraceIdRatioBased(...)` — `trace.sampling` alias removed in OTEL v1.28+
   - Fixed: `from opentelemetry.sdk.trace.sampling import TraceIdRatioBased`

4. **Database URL parsing crash** (`backend/app/config/settings.py`)
   - Terraform generates random DB passwords with special chars including `@`
   - Old code: `f"postgresql+asyncpg://{user}:{raw_password}@{host}:{port}/{db}"`
   - `@` in password splits the URL at the wrong position → `int(components["port"])` ValueError
   - Fixed: `sqlalchemy.URL.create(...)` — the canonical SQLAlchemy 2.x approach that handles encoding internally

5. **Redis connection timeout in Azure** (`backend/app/config/settings.py` + `infra/terraform/main.tf`)
   - Three issues compounding:
     a) `redis://` instead of `rediss://` (no TLS)
     b) `REDIS_PASSWORD` not set (Azure Managed Redis requires authentication)
     c) Default port 6379 (Azure uses 6380 for TLS)
   - Fixed: Added `REDIS_SSL` flag, uses `rediss://` when `REDIS_SSL=true`, URL-encodes password, added port/tls/password env vars to Terraform

6. **Managed Redis access key retrieval** (`infra/terraform/main.tf`)
   - `azurerm_managed_redis` does not export `primary_access_key`
   - `data.azurerm_redis_cache` can't read Managed Redis instances (different API version)
   - `Microsoft.Cache/redisEnterprise` routes `listKeys` through the database sub-resource
   - Balanced_B0 SKU disables access keys by default (Entra ID only)
   - Solution: `azapi_update_resource` to enable access keys + `data.azapi_resource_action` to call `listKeys` on `databases/default`

7. **CD workflow bugs** (`.github/workflows/cd.yml`)
   - Health check used static `vars.APP_URL` (could become stale if Container App FQDN changes)
   - `curl -sf` had no timeouts — hung forever if container didn't respond
   - Revision `active=true` comparison used `"True"` (capital T) but Azure returns `true` (lowercase)
   - No pre-flight diagnostics, no post-mortem on failure
   - Fixed: dynamic FQDN discovery, `--connect-timeout 10 --max-time 20`, lowercase comparison with whitespace trim, Azure Container App status + revision table + logs in both pre-flight and failure cases

8. **Worker CPU starvation** (`infra/terraform/main.tf`)
   - Docker CMD defaulted to 4 uvicorn workers on 0.5 CPU → CPU contention during startup
   - Added `WORKERS=1` env var to Container App

### New Files Created

| File | Purpose |
|---|---|
| `scripts/validate_deployment.sh` | 12-step deployment smoke test (register → login → upload → download → delete → logout) |
| `.github/workflows/validate-deployment.yml` | Manual `workflow_dispatch` trigger for validation |
| `docs/architecture.md` | Full architecture doc with Mermaid diagrams |
| `frontend/.dockerignore` | Exclude node_modules, .next from Docker build context |

### Dependency Pinning

`backend/requirements.txt` — added upper bounds to prevent silent breaking changes:
- `opentelemetry-api>=1.20.0,<2.0.0`
- `opentelemetry-sdk>=1.20.0,<2.0.0`
- `opentelemetry-exporter-otlp-proto-http>=1.20.0,<2.0.0`
- `greenlet>=3.0.0,<4.0.0`

### Production Hardening

- **`@model_validator(mode="after")`** in `Settings`: rejects startup if `ENVIRONMENT=production` but JWT_SECRET_KEY, DB_PASSWORD, or REDIS_PASSWORD are still defaults
- **`lifecycle { ignore_changes }`** on container image in Terraform — CD pipeline manages the image, Terraform must not overwrite it
- **Port range validation**: `DB_PORT` and `REDIS_PORT` now have `ge=1, le=65535`

## Current State

### Code

All fixes are committed locally on `main` (commit `f269aa8`). The commit **has NOT been pushed** — GitHub authentication is not configured in this environment.

### Azure Infrastructure

- **Container App** is running an OLD image (before `URL.create()` fix) — `POST /register` returns HTTP 500 due to DB password encoding bug
- **Managed Redis** has access keys disabled — needs `azapi_update_resource` to enable them
- **Terraform plan** is correct and ready to apply — will add Redis env vars + secrets without changing the running image

### What's NOT Done

```
[ ] Push commit to GitHub (git push origin main)
[ ] terraform apply (adds Redis env vars, enables access keys, adds secret)
[ ] CD pipeline deploys new image (triggers on push to main)
[ ] Run validate_deployment.sh against Azure
```

## Deployment Sequence (in order)

```bash
# 1. Push the code
git push origin main

# 2. Apply infrastructure changes (adds Redis config, does NOT change image)
cd infra/terraform
terraform apply

# 3. CD workflow triggers automatically on push to main
#    Watch: https://github.com/Shashwat-11/Azure-based-drive-clone/actions

# 4. After CD completes (health check passes), run smoke test
bash scripts/validate_deployment.sh
```

No downtime between steps 2 and 3 — the `lifecycle { ignore_changes }` in Terraform prevents image rollback.

## Key Architecture Decisions

- **SQLAlchemy URL.create()** over manual f-string interpolation — handles URL encoding per RFC 3986, future-proof
- **azapi provider** over azurerm for Managed Redis keys — azurerm v4.80.0 doesn't expose access keys for `azurerm_managed_redis`
- **Image-only CD** + **Terraform for config** — CD updates only the image; Terraform manages env vars, secrets, scaling. Separation of concerns.
- **`@model_validator` fail-fast** — app crashes at import time if production secrets are missing, rather than failing on first request
- **`lifecycle { ignore_changes }`** on container image — prevents Terraform from overwriting the CD-deployed image

## Files to Know

| File | Role |
|---|---|
| `backend/app/config/settings.py` | All configuration, URL construction, production validation |
| `backend/app/core/otel.py` | OpenTelemetry setup |
| `backend/app/dependencies/database.py` | Database engine + session factory |
| `backend/app/dependencies/redis.py` | Redis client initialization |
| `backend/app/middleware/rate_limiter.py` | Redis-backed rate limiting |
| `infra/terraform/main.tf` | All Azure infrastructure |
| `.github/workflows/cd.yml` | Deployment pipeline |
| `docker-compose.prod.yml` | Local production simulation |
| `scripts/validate_deployment.sh` | Post-deployment smoke test |

## Known Warnings (non-blocking)

- `passlib` internal deprecation: `argon2.__version__` access — harmless, from passlib internals
- `python-jose` is unmaintained — consider migrating to `PyJWT` in future
- `structlog<25.0.0` is pinned — v25 will be a major version, monitor changelog
- Docker network DNS unreliable in this environment — containers can't resolve pypi.org (local dev issue, not Azure)

## If Something Goes Wrong After Deploy

1. Check CD workflow run for diagnostics (it prints Container App status + logs on failure)
2. Run `az containerapp logs show -g rg-drive-production -n ca-drive-backend --tail 100`
3. Run `terraform plan` to check for unintended drift
4. The production validator will block startup if any secret is still default — check env vars in Container App
