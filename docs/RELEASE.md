# Release Notes

## v1.0.0 — Production Release

### Release Highlights

- Complete auth flow: register, login, JWT refresh, logout
- File management: upload, download, rename, delete, folder browsing
- Production infrastructure on Azure Container Apps
- Automated CI/CD with deployment validation
- Full observability: OpenTelemetry, structured logging, health probes
- 215 backend tests passing
- Production-quality frontend with dark mode

### Infrastructure

- Azure Container Apps (backend + frontend)
- PostgreSQL Flexible Server v16
- Azure Managed Redis (Balanced_B0)
- Azure Blob Storage for file content
- Azure Key Vault for secrets management
- Azure Container Registry for Docker images
- Application Insights for monitoring
- Terraform for infrastructure as code

### Backend

- FastAPI with async SQLAlchemy 2.x
- JWT authentication with refresh token rotation
- Argon2 password hashing
- Rate limiting (Redis-backed, disabled in production pending Entra ID auth)
- Comprehensive middleware stack (security headers, correlation IDs, request logging, metrics)
- Alembic database migrations (7 revisions)
- Repository pattern for data access
- 215 pytest tests covering all phases
- OpenTelemetry tracing to Application Insights
- Structured JSON logging via structlog

### Frontend

- Next.js 16 with App Router
- React 19 + TypeScript
- TailwindCSS 3 (dark mode first)
- React Query for data fetching with cache invalidation
- JWT auto-refresh interceptor
- Auth guard with route protection
- File browser with breadcrumbs, create folder, rename, delete, download
- Recent files, shared-with-me, trash pages
- Toast notifications for all mutations
- Loading skeletons and error states
- ESLint 9 flat config with TypeScript support

### CI/CD

- CI: lint, test, Docker build on every PR and push
- CD: build, push to ACR, deploy, health check on push to main
- Manual deployment validation workflow (12-step smoke test)
- Deployment validation script with auto-cleanup
- Dependabot configured with version ignore rules

### Known Limitations

- Redis rate limiting disabled in production (Balanced_B0 uses Entra ID auth, not access keys)
- File upload/download requires Azure Blob Storage credentials
- Frontend CD workflow not yet automated (Terraform resource exists, manual deploy needed)
- Share dialog UI not yet implemented (backend collaboration APIs exist)
- Version history UI not yet implemented

### Upgrade Notes

- Next.js 15 → 16: `next lint` deprecated, migrated to ESLint CLI
- ESLint 8 → 9: flat config format (`eslint.config.mjs`)
- TailwindCSS 3 → 3.4.x (v4 not compatible — PostCSS plugin moved)
- TypeScript 5.x (v7 not compatible — Next.js 16 supports 5.x)
