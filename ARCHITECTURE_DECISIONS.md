# Architecture Decision Records (ADR)

This document captures significant architectural decisions for the Drive cloud storage platform. Decisions are recorded chronologically and should not be retroactively modified. New decisions are appended as new ADRs.

---

## ADR-001: FastAPI as the Backend Framework

**Status**: Accepted

**Context**: The project requires a performant, asynchronous Python web framework with native async support, automatic OpenAPI generation, and strong type validation.

**Decision**: Use FastAPI (0.115+) as the primary backend framework.

**Alternatives Considered**:

- **Django + Django REST Framework**: Mature but synchronous-first; async support is bolted on. The ORM, admin panel, and template engine are unnecessary overhead for an API-only backend.
- **Flask + extensions**: Too minimal; requires significant assembly of third-party libraries for async, validation, and documentation. Maintenance burden is high.
- **aiohttp**: Lower-level; lacks integrated OpenAPI docs, dependency injection, and Pydantic validation out of the box.

**Consequences**:

- Automatic OpenAPI/Swagger generation at `/docs` and `/redoc` with zero configuration.
- Native async request handling via Starlette, compatible with SQLAlchemy async and Azure SDK async clients.
- Pydantic v2 integration provides request/response validation, reducing boilerplate.
- Dependency injection system (`Depends`) enables clean separation of concerns.
- FastAPI's ecosystem is actively maintained with strong community adoption.

---

## ADR-002: Clean Architecture

**Status**: Accepted

**Context**: The project spec mandates Clean Architecture with separation of presentation, application, domain, and infrastructure layers. The codebase must be maintainable, testable, and decoupled from frameworks.

**Decision**: Adopt the Clean Architecture pattern with the following layer organization:

```
app/
├── api/          # Presentation — HTTP routes, request handling
├── services/     # Application — orchestrates use cases
├── domain/       # Domain — pure business entities (planned)
├── repositories/ # Infrastructure — data access abstraction
├── models/       # Infrastructure — SQLAlchemy ORM models
├── schemas/      # Interface — Pydantic DTOs
├── middleware/   # Infrastructure — ASGI middleware
├── storage/      # Infrastructure — storage abstraction
├── auth/         # Infrastructure — auth utilities
├── core/         # Shared — config, logging, exceptions
├── config/       # Shared — settings
└── dependencies/ # Shared — DI wiring
```

**Alternatives Considered**:

- **Monolithic service layer**: Mixing business logic with API routes leads to untestable, tightly coupled code. This was explicitly rejected by the project spec.
- **Domain-Driven Design (full)**: Aggregates, value objects, domain events — excessive ceremony for the current scope. Can be adopted incrementally if complexity grows.

**Consequences**:

- Higher initial file count and indirection, but each layer has a single responsibility.
- Repository pattern decouples data access from business logic, enabling mock-based unit testing.
- Service layer can be tested independently of HTTP.
- Future migration to a different framework or storage backend requires minimal changes.

---

## ADR-003: PostgreSQL as the Primary Database

**Status**: Accepted

**Context**: The platform requires ACID transactions, complex queries (search, folder hierarchies), referential integrity, and JSON support for flexible metadata.

**Decision**: Use PostgreSQL 16 as the primary relational database.

**Alternatives Considered**:

- **MySQL**: Weaker JSON support, less mature full-text search, and historically less strict constraint enforcement.
- **SQLite**: Not suitable for concurrent write-heavy workloads; no native UUID type; no connection pooling.
- **MongoDB**: Document model would complicate folder hierarchies and relational integrity. Lack of joins makes reporting and search harder.

**Consequences**:

- PostgreSQL's `gen_random_uuid()` provides server-side UUID generation without application-level coordination.
- Full-text search via `tsvector` / `tsquery` will be used for the search feature (planned Phase 5+).
- Connection pooling via SQLAlchemy's async engine with `pool_pre_ping=True`.
- Native `UUID` column type prevents type mismatch bugs.
- `TIMESTAMPTZ` columns ensure timezone-aware datetime storage.

---

## ADR-004: Azure Blob Storage for File Persistence

**Status**: Accepted

**Context**: The project spec requires Azure integration. Files must not be stored on the application server's filesystem or in the database.

**Decision**: Use Azure Blob Storage as the sole file storage backend, with an abstract `StorageBackend` interface to allow future provider swaps.

**Alternatives Considered**:

- **AWS S3**: Equivalent feature set but spec mandates Azure. The abstraction layer supports S3 as a future option.
- **Local filesystem**: Violates the spec; does not scale horizontally; cannot share files across instances.
- **Database BLOB columns**: Severe performance degradation; bloats database backups; contradicts the spec.

**Consequences**:

- Database stores only file metadata (name, size, content type, blob name).
- Files are referenced by UUID-based blob names to prevent enumeration.
- The `StorageBackend` ABC defines upload, download, delete, move, copy, exists, and health_check — all implemented for Azure.
- Streaming upload uses block-based staging (`stage_block`/`commit_block_list`) to avoid buffering entire files in memory.
- Container name is configurable via `AZURE_STORAGE_CONTAINER_NAME`.

---

## ADR-005: SQLAlchemy 2.x with Async Support

**Status**: Accepted

**Context**: The backend must handle concurrent requests efficiently. The database driver must support async/await natively.

**Decision**: Use SQLAlchemy 2.0+ with `asyncpg` driver and the async session pattern.

**Alternatives Considered**:

- **SQLAlchemy 1.x sync**: Would block the event loop on every database call, requiring thread pool executors and negating FastAPI's async benefits.
- **Tortoise ORM**: Async-native but less mature; smaller ecosystem; fewer production deployments at scale.
- **Raw asyncpg**: Maximum performance but no ORM features; requires manual query building and migration tooling.
- **Prisma Client Python**: Emerging project; not yet production-stable for complex use cases.

**Consequences**:

- `AsyncSession` with `async_sessionmaker` provides session-per-request via FastAPI dependency injection.
- Connection pooling configured through `pool_size`, `max_overflow`, and `pool_pre_ping`.
- Alembic is configured for async migrations using `run_async`.
- `Mapped[]` type annotations from SQLAlchemy 2.0 provide precise column typing.
- Greenlet dependency required for async ORM operations on Python 3.13+.

---

## ADR-006: JWT with Refresh Token Rotation

**Status**: Accepted

**Context**: The platform requires stateless authentication for scalability, with support for token revocation without a central session store.

**Decision**: Use JWT access tokens (short-lived, 30 minutes) combined with refresh tokens (7 days) stored server-side with SHA-256 hashing and rotation on each use.

**Alternatives Considered**:

- **Session-based auth**: Requires sticky sessions or a shared session store (Redis). Increases latency on every authenticated request.
- **JWT only (no refresh tokens)**: Short token lifetimes force frequent re-authentication. Long lifetimes create a revocation problem.
- **OAuth 2.0 / OpenID Connect**: Overkill for an initial single-service deployment. Can be added later as an auth provider integration.
- **Opaque tokens**: Require a database lookup on every request. JWT's self-contained payload avoids this.

**Consequences**:

- Access tokens carry `sub` (user ID) and `role` (RBAC) claims, validated on every request via signature verification.
- Refresh tokens are SHA-256 hashed before storage; the raw token is never stored.
- Token rotation: each refresh consumes the old refresh token and issues a new one. Replay of a used refresh token is detectable (token already revoked).
- `jti` claim included for future token blacklisting.
- All token lifecycle events (creation, revocation) are logged with structured data.
- Argon2 is used for password hashing via `passlib`.

---

## ADR-007: Redis for Caching, Rate Limiting, and Session State

**Status**: Accepted

**Context**: The platform needs a fast, in-memory data store for rate limiting, potential caching, and distributed state.

**Decision**: Use Redis 7 as the caching and state layer.

**Alternatives Considered**:

- **Memcached**: Simpler but lacks persistence, pub/sub, and rich data structures needed for rate limiting.
- **In-memory Python dict**: Does not work across multiple application instances; state lost on restart.
- **Database-based caching**: Adds latency; defeats the purpose of a cache.

**Consequences**:

- Rate limiter middleware uses `INCR` + `EXPIRE` for token-bucket-style counting per IP + endpoint.
- `decode_responses=True` for convenient string handling.
- Connection pooling via `redis.asyncio` with configurable pool size.
- Future use cases: caching folder listings, file metadata, and session blacklists.

---

## ADR-008: UUID Primary Keys

**Status**: Accepted

**Context**: All tables require primary keys. Sequential integer IDs expose enumeration vulnerabilities and complicate multi-tenant or distributed architectures.

**Decision**: Use UUIDv4 as primary keys for all tables, generated server-side via `gen_random_uuid()`.

**Alternatives Considered**:

- **Auto-increment integers**: Predictable, enumerable. Security risk for user IDs, file IDs, and share links.
- **ULID**: Sortable, but less universally supported than UUID. No native PostgreSQL type.
- **Snowflake IDs**: Require coordination (machine ID, datacenter ID). Overkill for single-service deployment.

**Consequences**:

- `PG_UUID(as_uuid=True)` column type with `server_default=func.gen_random_uuid()`.
- 128-bit keys consume more storage and index space than integers.
- Non-sequential UUIDs can cause index fragmentation; mitigated by PostgreSQL's B-tree optimizations for UUID.
- Future horizontal scaling benefits from non-colliding IDs across instances.

---

## ADR-009: Structured JSON Logging via structlog

**Status**: Accepted

**Context**: Logs must be machine-parseable, traceable across requests, and compatible with Azure Monitor / Log Analytics.

**Decision**: Use `structlog` with JSON rendering to stdout.

**Alternatives Considered**:

- **Standard `logging` with text format**: Not machine-parseable; requires log parsing middleware.
- **OpenTelemetry logging SDK**: More complex; adds overhead without immediate distributed tracing benefit.
- **loguru**: Simpler API but less structured output control; harder to integrate with Azure-native tooling.

**Consequences**:

- Every log entry is a JSON object with keys: `message`, `level`, `timestamp`, `logger`, `trace_id`, plus context-specific fields.
- `structlog.contextvars.merge_contextvars` enables context propagation across async boundaries.
- Correlation IDs (`X-Request-ID`) are included in every log entry.
- JSON output can be ingested directly by Azure Monitor, ELK, or Loki.
- `_rename_event_to_message` processor maps structlog's `event` key to `message` for log aggregator compatibility.

---

## ADR-010: Docker Compose for Development

**Status**: Accepted

**Context**: The project needs a reproducible local development environment with all dependencies (PostgreSQL, Redis, backend, frontend).

**Decision**: Use Docker Compose with separate service definitions and named volumes.

**Alternatives Considered**:

- **Manual local installation**: High onboarding friction; environment drift across developers.
- **Kubernetes (minikube/k3s)**: Excessive complexity for a local dev environment. Docker Compose is simpler and sufficient.
- **Dev Containers (VS Code)**: Good for IDE integration but less universal than Docker Compose.

**Consequences**:

- `docker-compose.yml` defines: postgres (16-alpine), redis (7-alpine), backend (FastAPI with hot reload), frontend (Next.js dev server).
- Named volumes (`postgres_data`, `redis_data`) persist data across container restarts.
- Health checks on postgres and redis ensure backend starts only when dependencies are ready.
- Development Dockerfiles (`Dockerfile.dev`) use volume mounts for hot reload.

---

## ADR-011: Repository Pattern

**Status**: Accepted

**Context**: Data access logic must be separated from business logic to enable testing with mocks and future database changes.

**Decision**: Implement the Repository Pattern where each aggregate root has a corresponding repository class that encapsulates all database queries.

**Alternatives Considered**:

- **Direct SQLAlchemy session in services**: Tightly couples business logic to SQLAlchemy; unable to unit test without a database.
- **Active Record pattern**: Mixes data access with domain logic; violates Single Responsibility Principle.
- **CQRS with separate read/write models**: Overkill for current complexity; can be introduced later if read patterns diverge from write patterns.

**Consequences**:

- `UserRepository` and `RefreshTokenRepository` encapsulate all query logic.
- Repositories accept `AsyncSession` via constructor injection, obtained from FastAPI's dependency system.
- Services depend on repository abstractions (class instances, not interfaces — Python uses duck typing).
- Unit tests can mock repositories without a database connection.

---

## ADR-012: Service Layer

**Status**: Accepted

**Context**: Business logic must be orchestrated in a dedicated layer between API routes and repositories.

**Decision**: Implement a Service Layer where each service class orchestrates one or more repositories and encapsulates business rules.

**Alternatives Considered**:

- **Business logic in API routes**: Violates separation of concerns; routes become untestable monoliths.
- **Domain services only**: Requires rich domain model with entity methods; not yet appropriate given the current anemic domain layer.

**Consequences**:

- `AuthService` orchestrates `UserRepository` and `RefreshTokenRepository`.
- Services are created per-request (not singletons) to ensure fresh session binding.
- Services return Pydantic DTOs, not ORM entities, preventing ORM leakage to the API layer.
- Complex operations (e.g., token rotation: decode + validate + revoke old + issue new) are encapsulated in a single service method.

---

## ADR-013: Azure Monitor and Application Insights (Planned)

**Status**: Proposed

**Context**: The project spec requires Azure Monitor integration for metrics, distributed tracing, and log analytics.

**Decision**: Integrate Azure Monitor and Application Insights as the primary observability backend once the application is deployed to Azure.

**Alternatives Considered**:

- **Prometheus + Grafana**: Open-source stack requiring self-hosting and maintenance. Azure-native solutions reduce operational burden.
- **Datadog / New Relic**: Third-party SaaS with per-host pricing. Azure-native is cost-effective for Azure-hosted workloads.

**Consequences**:

- Structured JSON logs on stdout will be ingested by Azure Log Analytics via the Azure Monitor agent.
- Application Insights SDK will be added for automatic dependency tracking, request telemetry, and exception tracking.
- The `OpenTelemetry` integration plan will enable vendor-neutral instrumentation with Azure as the exporter.
- Correlation IDs (`trace_id` / `X-Request-ID`) already propagate and can be mapped to Application Insights' `operation_id`.

---

## ADR-014: Repository Pattern

*(Duplicate numbering skipped — see ADR-011)*

---

## ADR-015: Streaming Upload with SHA-256 Chunked Hashing

**Status**: Accepted

**Context**: Phase 3 requires uploads that never buffer entire files in memory while computing a SHA-256 checksum for integrity verification.

**Decision**: Use a `hashing_stream()` async generator wrapper that proxies each chunk to both the SHA-256 hasher and the downstream Azure block uploader. The hasher is updated incrementally as chunks pass through.

**Alternatives Considered**:

- **Full-buffer then hash**: Loads entire file into memory; violates spec; OOM risk on large files.
- **Hash after blob retrieval**: Requires separate download to verify; doubles latency and egress cost.
- **Azure automatic MD5**: Azure provides MD5 but not SHA-256; the spec requires SHA-256.

**Consequences**:

- O(chunk_size) memory usage — only one chunk in memory at a time.
- The hashing wrapper is transparent to the Azure backend; no SDK modifications needed.
- Checksum stored in `files.checksum_sha256` for download verification and future deduplication.

---

## ADR-016: Two-Phase Upload with Compensation

**Status**: Accepted

**Context**: File upload spans two systems (Azure Blob Storage and PostgreSQL). If either system fails, the system must not leave orphaned blobs or database records.

**Decision**: Use a compensation pattern: upload to Azure first, create the database record second. If the database insert fails, delete the uploaded blob from Azure. If the database succeeds but blob deletion later fails (e.g., during a file delete operation), log the error and proceed — the database is the source of truth.

**Alternatives Considered**:

- **Database-first, then upload**: If upload fails, the database record must be rolled back. This is simpler but requires an extra blob list query on cleanup.
- **Two-phase commit across systems**: Distributed transactions are not feasible between Azure Blob and PostgreSQL; even with saga patterns, the complexity is unjustified at this scale.
- **Eventual consistency**: Accept temporary orphan blobs and clean them up via a scheduled job. Requires additional infrastructure.

**Consequences**:

- Compensation is best-effort. If the compensation itself fails, a log entry is emitted and manual cleanup may be needed.
- The system prefers orphan databases (no blob) over orphan blobs (storage costs accumulate silently).
- Delete operations are optimistic: soft-delete the record, attempt blob deletion, log if blob deletion fails.

---

## ADR-017: Blob Naming Convention

**Status**: Accepted

**Context**: Blob names must prevent enumeration, support future multi-tenancy, and allow efficient prefix-based listing.

**Decision**: Use the pattern `{user_id}/{uuid}` where `uuid` is a randomly generated UUIDv4. A future tenant prefix can be prepended (e.g., `{tenant_id}/{user_id}/{uuid}`) without breaking existing names.

**Alternatives Considered**:

- **Original filename as blob name**: Exposes user data structure, allows enumeration, causes collisions.
- **Content-hash-based names (SHA-256)**: Enables deduplication but leaks content identity; two users with the same file would share a blob name.
- **Sequential IDs**: Enumerable, trivial to guess.

**Consequences**:

- Blob names are opaque and 128-bit unguessable.
- User-scoped prefixes enable efficient `list_blobs(name_starts_with="{user_id}/")` operations.
- Renaming a file in the application does not require renaming the blob.

