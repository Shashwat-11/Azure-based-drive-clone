# Changelog

All notable changes to the Drive cloud storage platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Types of changes:

- **Added**: New features or functionality
- **Changed**: Changes to existing functionality
- **Fixed**: Bug fixes
- **Security**: Security improvements or vulnerability fixes
- **Removed**: Removed features or functionality

---

## v1.0.0 (2026-07-03) — Production Release

178 tests, 82% coverage, 30+ API endpoints. Terraform IaC, GitHub Actions CI/CD.

Full feature set: Authentication, file management with streaming, folder hierarchy, trash, version history, collaboration with shared links, search and discovery, observability, and Azure deployment infrastructure.

---

## [Unreleased]

### Added

- Frontend Container App Terraform resource
- Deployment validation script (`scripts/validate_deployment.sh`)
- Architecture documentation (`docs/architecture.md`)
- Release notes (`docs/RELEASE.md`)

### Changed

- Next.js 15 → 16
- ESLint 8 → 9 (flat config)
- React Query integration across all pages

### Fixed

- SQLAlchemy URL.create() for password encoding in database URLs
- Redis TLS/SSL configuration for Azure Managed Redis
- PostgreSQL firewall rule for Container App egress
- Alembic ConfigParser interpolation crash with URL-encoded passwords
- Production validation: graceful Redis degradation when unavailable

---

## Phase 3 — Production Storage Layer (2026-07-01)

### Added

- **Folder model** with self-referential parent_id for unlimited nesting, unique constraint on (name, parent_id, owner_id)
- **File model** with UUID PK, owner_id, folder_id, original_filename, stored_blob_name, mime_type, extension, checksum_sha256, file_size_bytes, storage_provider, etag, version_number, timestamps, soft delete
- **FolderRepository** and **FileRepository** with paginated listing, soft delete, and duplicate name checking
- **StorageService** with blob name generation (`{user_id}/{uuid}`), SHA-256 hashing during streaming upload, and block-based blob deletion
- **FolderService** orchestrating folder CRUD with conflict detection
- **FileService** orchestrating upload (validate → hash → store blob → create metadata → compensate), download (stream from blob), and delete (soft-delete metadata + delete blob)
- **AuditService** with structured log entries for file upload, download, delete and folder create/delete
- **Folder API** endpoints: `POST /folders`, `GET /folders`, `GET /folders/{id}`, `PATCH /folders/{id}`, `DELETE /folders/{id}`
- **File API** endpoints: `POST /files/upload`, `GET /files`, `GET /files/{id}`, `GET /files/{id}/download`, `DELETE /files/{id}`
- **Transaction compensation**: if DB insert fails after blob upload, the uploaded blob is automatically deleted
- **Validation**: filename (no path traversal), extension (configurable allowlist), MIME type (null byte detection), file size (configurable max)
- **Mock storage backend** in test conftest enabling full-stack file API tests without Azure
- **Alembic migration** (`002_create_folders_and_files`) with proper indexes and constraints
- **33 storage tests** covering folders, files, upload/download, validation, transaction rollback, repository queries, and storage service

### Security

- Blob names use UUIDs (unguessable, not derived from filenames)
- All endpoints require authentication via JWT
- Files are scoped to owner_id — users cannot access other users' files
- Filename path traversal blocked (`/` and `\\` rejected)

---

## Phase 2 — Authentication & Authorization (2026-07-01)

### Added

- **User model** with UUID primary key, email, password hash, full name, role, soft delete support
- **RefreshToken model** with SHA-256 hashed storage, expiry, and revocation tracking
- **JWT access tokens** with 30-minute expiry, signed with HS256, carrying `sub` and `role` claims
- **JWT refresh tokens** with 7-day expiry, rotation on each use (reuse detection)
- **Argon2 password hashing** via `passlib` with recommended defaults
- **Registration endpoint** (`POST /api/v1/auth/register`) with email uniqueness validation
- **Login endpoint** (`POST /api/v1/auth/login`) with user enumeration prevention
- **Token refresh endpoint** (`POST /api/v1/auth/refresh`) with rotation and replay protection
- **Current user endpoint** (`GET /api/v1/auth/me`) returning authenticated user profile
- **Logout endpoint** (`POST /api/v1/auth/logout`) revoking refresh tokens
- **Role-Based Access Control** (RBAC) with `admin`, `user`, and `viewer` roles
- **`require_role()` dependency** for endpoint-level authorization
- **UserRepository** and **RefreshTokenRepository** following the Repository Pattern
- **AuthService** orchestrating registration, authentication, and token lifecycle
- **Alembic migration** (`001_create_users_and_refresh_tokens`) for users and refresh_tokens tables
- **20 auth tests** covering registration, login, token refresh, me, logout, and RBAC scenarios

### Security

- Passwords hashed with Argon2 (via passlib)
- Refresh tokens SHA-256 hashed before database storage
- Token rotation prevents replay attacks
- User enumeration prevented (identical error for wrong password vs. nonexistent user)
- Access token carries role claim for RBAC enforcement

---

## Phase 1 — Project Initialization (2026-07-01)

### Added

- **FastAPI application** with app factory pattern, CORS, and structured exception handlers
- **Clean Architecture folder structure**: `api/`, `config/`, `core/`, `domain/`, `services/`, `repositories/`, `schemas/`, `models/`, `middleware/`, `storage/`, `auth/`, `workers/`
- **Pydantic Settings** (`Settings` class) with environment variable validation for database, Redis, Azure, JWT, rate limiting, CORS, file uploads, and security
- **Structured JSON logging** via `structlog` with correlation ID propagation
- **Correlation ID middleware** (`CorrelationIdMiddleware`) extracting or generating `X-Request-ID` per request
- **Request logger middleware** (`RequestLoggerMiddleware`) logging method, path, status, duration, client IP, and trace ID
- **Custom exception hierarchy** (`AppError` base + `AuthenticationError`, `AuthorizationError`, `NotFoundError`, `ConflictError`, `ValidationError`, `RateLimitError`, `StorageError`, `DatabaseError`, `ServiceUnavailableError`)
- **Global error handlers** returning standardized JSON `{success, message, code, trace_id}` responses
- **Health check endpoints**: `/health`, `/ready` (DB + Redis + Storage checks), `/live`
- **SQLAlchemy 2.x async engine** with `asyncpg` driver, connection pooling, and `pool_pre_ping`
- **Redis async client** with connection pooling and configurable max connections
- **Abstract `StorageBackend` interface** defining upload, download, delete, move, copy, exists, and health_check methods
- **Azure Blob Storage backend** implementing `StorageBackend` with async SDK, streaming, and block-based upload
- **Alembic configuration** with async migration support
- **Docker Compose** for local development with PostgreSQL 16, Redis 7, backend, and frontend services
- **Next.js frontend** scaffold with TypeScript, TailwindCSS, and App Router
- **11 tests** covering health checks, middleware, and error handlers
- **README.md**, `.env.example`, `.gitignore`, `requirements.txt`, `pyproject.toml`

### Changed

- N/A (initial version)

### Fixed

- N/A (initial version)

### Security

- CORS configured from settings
- Secrets managed via `SecretStr` (never logged or serialized)
- All user input validated via Pydantic

---

## Post-Review Fixes (2026-07-01)

### Fixed

- **CRI-001**: `get_engine()` was `async def` but `create_async_engine()` is synchronous. Changed `get_engine()` to sync, preventing coroutine-as-engine bug.
- **HIG-001**: `close_db()` and `close_redis()` are now called in FastAPI lifespan shutdown, preventing connection leaks.
- **HIG-002**: Implemented `RateLimiterMiddleware` using Redis `INCR`/`EXPIRE` for auth endpoints (login, register).
- **HIG-003**: Added `SecurityHeadersMiddleware` injecting `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control`, and conditional HSTS.
- **HIG-004**: Rewrote `upload_stream` to use `stage_block()`/`commit_block_list()` instead of buffering entire file in memory.
- **HIG-005**: Removed dead expression `4 * 1024 * 1024` in `download_stream`.
- **HIG-006**: `RequestLoggerMiddleware` now reads `X-Request-ID` header directly, fixing `trace_id=None` in `request_started` logs. `CorrelationIdMiddleware` falls back to `scope["state"]` if header not present.
- **HIG-007**: Changed `RefreshToken.user_id` from `String(36)` to `PG_UUID(as_uuid=True)` matching `User.id` type. Updated repository and migration.

### Security

- Security headers applied to all HTTP responses
- Rate limiting enforced on authentication endpoints

---

## Phase 3 Review Fixes (2026-07-01)

### Fixed

- **HIG-008**: All audit log events now include `trace_id` for distributed tracing correlation. `AuditService` methods accept `trace_id` as first parameter. `FileService` and `FolderService` propagate `trace_id` from the request via FastAPI's `request.state`.
- **HIG-009**: Upload size validation now occurs in two phases: pre-upload check using `UploadFile.size` (Content-Length header), and post-upload check using the computed file size. Oversized files are rejected before any Azure interaction when Content-Length is known. Post-upload validation failures trigger automatic blob deletion (compensation).

### Security

- Oversized uploads rejected before Azure storage interaction when Content-Length header available
- Post-upload size validation with automatic blob cleanup prevents orphaned storage costs
- Audit logs now traceable end-to-end via correlation IDs

---

## Phase 4 Review Fixes (2026-07-02)

### Fixed

- **CRI-004**: `empty_trash` now processes items in batches of 200 with a loop until the trash is truly empty. Removed the 10,000-item hard limit that silently truncated large trash volumes.
- **CRI-005**: `empty_trash` now cleans up Azure blobs for every permanently deleted file. Uses `StorageService.delete_blob()` directly with best-effort error handling — blob cleanup failures are logged but never block the operation.
- **HIG-011**: Breadcrumb generation now enforces `owner_id` scoping at every level of the parent chain walk. Cross-user breadcrumb access returns 404.

### Security

- Breadcrumb endpoint no longer leaks folder names across user boundaries

---

## System Hardening (2026-07-02) — Full-System Architecture Review Fixes

### Fixed

- **CRI-001**: Authorization dependencies wired into all file/folder endpoints with role-based checks. Editors can now perform all write operations on shared resources. Viewers remain read-only.
- **CRI-002**: Replaced `setattr`-based field assignment in `LinkService.update_link` with explicit field assignments.
- **HIG-001**: JWT access token blacklist in Redis using `jti` claim. `logout` now blacklists access tokens. `get_current_user` checks blacklist on every request.
- **HIG-002**: Rate limiter extended to link access endpoints for password brute-force protection.
- **HIG-003**: `LinkService.create_link` validates resource ownership before link creation.
- **HIG-004**: `is_public=False` enforced — private links require authentication.
- **HIG-005**: Replaced auto-commit with `session.is_modified` check. Read-only requests no longer commit.
- **HIG-006**: Production multi-stage Dockerfile with non-root user, healthcheck, and configurable workers.
- **HIG-007**: Composite permission index added for optimized permission lookups.

### Security

- Access tokens revocable via Redis blacklist; logout immediately invalidates tokens
- Rate limiting on link access endpoints prevents password brute-force
- Private links require authentication; ownership validated before link creation
- Permission hierarchy enforced: editor role required for write, viewer for read
