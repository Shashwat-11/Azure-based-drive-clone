# Architecture Document — Drive

---

## 1. High-Level System Architecture

```
┌──────────────┐     ┌──────────────────────┐     ┌─────────────────────────┐
│   Frontend   │────▶│   Azure Container App  │────▶│   Azure Blob Storage     │
│  Next.js 15  │     │  (FastAPI / Python)    │     │   (File Content)         │
│  React 19    │     │                        │     └─────────────────────────┘
│  TypeScript  │     │  ┌──────────────────┐  │
└──────────────┘     │  │  Rate Limiter    │──│───▶  Azure Managed Redis
                     │  │  (redis-py)      │  │      (Rate Limits + Cache)
                     │  └──────────────────┘  │
                     │                        │
                     │  ┌──────────────────┐  │     ┌─────────────────────────┐
                     │  │  Auth Service    │  │     │  PostgreSQL Flexible    │
                     │  │  (JWT / PyJWT)   │──│────▶│  Server                 │
                     │  └──────────────────┘  │     │  (Users, Files, Folders) │
                     │                        │     └─────────────────────────┘
                     │  ┌──────────────────┐  │
                     │  │  File Service    │  │     ┌─────────────────────────┐
                     │  │  (Storage Layer) │──│────▶│  Azure App Insights     │
                     │  └──────────────────┘  │     │  (Traces, Metrics)      │
                     └────────────────────────┘     └─────────────────────────┘
```

```mermaid
graph TB
    subgraph "Client Layer"
        FE[Next.js 15 Frontend<br/>React 19 + TypeScript]
        CLI[REST API Clients]
    end

    subgraph "Azure Container Apps Environment"
        CA[Container App: ca-drive-backend<br/>FastAPI + Python 3.13]
        subgraph "Backend Services"
            API[API Routes v1]
            AUTH[Auth Service<br/>JWT]
            FS[File Service]
            SS[Storage Service]
            RL[Rate Limiter<br/>redis-py]
            MW[Middleware Stack]
        end
    end

    subgraph "Azure Data Layer"
        PG[(PostgreSQL Flexible Server<br/>Users, Files, Folders,<br/>Permissions, Versions)]
        REDIS[(Azure Managed Redis<br/>Rate Limiting, Caching)]
        BLOB[(Azure Blob Storage<br/>File Content,<br/>Version Management)]
    end

    subgraph "Azure Observability"
        AI[Application Insights<br/>Traces, Metrics, Logs]
        LA[Log Analytics Workspace]
    end

    subgraph "CI/CD"
        GH[GitHub Actions]
        ACR[Azure Container Registry]
    end

    FE -->|HTTPS| CA
    CLI -->|HTTPS| CA
    CA --> API
    API --> AUTH
    API --> FS
    API --> SS
    API --> RL
    API --> MW
    AUTH --> PG
    FS --> PG
    FS --> BLOB
    SS --> BLOB
    RL --> REDIS
    CA -->|OTEL| AI
    AI --> LA
    GH -->|docker push| ACR
    ACR -->|deploy| CA
```

## 2. Request Flow

```mermaid
sequenceDiagram
    actor Client
    participant Ingress as Azure Container App<br/>Ingress (Envoy)
    participant MW1 as SecurityHeaders
    participant MW2 as CorrelationId
    participant MW3 as RequestLogger
    participant MW4 as RateLimiter
    participant MW5 as Metrics
    participant MW6 as CORS
    participant Router as FastAPI Router
    participant Auth as Auth Dependency
    participant Service as Service Layer
    participant Repo as Repository
    participant DB as PostgreSQL

    Client->>Ingress: HTTPS request
    Ingress->>MW1: TLS terminated, forward HTTP
    MW1->>MW2: Add security headers on response
    MW2->>MW3: Attach X-Request-Id / trace_id
    MW3->>MW4: Log request start
    MW4->>MW5: Check rate limits (Redis)
    MW5->>MW6: Record metrics
    MW6->>Router: CORS validation
    Router->>Auth: Extract JWT, validate
    Auth-->>Router: User identity
    Router->>Service: Execute use case
    Service->>Repo: Data access
    Repo->>DB: SQL query (asyncpg)
    DB-->>Repo: Results
    Repo-->>Service: Domain objects
    Service-->>Router: Response data
    Router-->>Client: HTTP response + trace headers
```

## 3. Authentication Flow

```mermaid
sequenceDiagram
    actor Client
    participant API as /api/v1/auth
    participant AuthSvc as AuthService
    participant DB as PostgreSQL
    participant JWT as JWT Handler

    Note over Client,DB: ── Registration ──
    Client->>API: POST /register<br/>{email, password, full_name}
    API->>AuthSvc: register(request)
    AuthSvc->>DB: Check email uniqueness
    AuthSvc->>AuthSvc: hash_password(password)<br/>(passlib + argon2)
    AuthSvc->>DB: INSERT INTO users
    DB-->>AuthSvc: User created
    AuthSvc-->>Client: UserResponse (201)

    Note over Client,DB: ── Login ──
    Client->>API: POST /login<br/>{email, password}
    API->>AuthSvc: login(request)
    AuthSvc->>DB: SELECT user by email
    AuthSvc->>AuthSvc: verify_password(password, hash)
    AuthSvc->>JWT: encode_access_token(user)
    JWT-->>AuthSvc: access_token (JWT, 30min)
    AuthSvc->>JWT: encode_refresh_token(user)
    JWT-->>AuthSvc: refresh_token (JWT, 7d)
    AuthSvc->>DB: INSERT refresh_token
    AuthSvc-->>Client: TokenResponse (200)

    Note over Client,DB: ── Authenticated Request ──
    Client->>API: GET /me<br/>Authorization: Bearer {access_token}
    API->>JWT: decode + validate token
    JWT-->>API: User identity
    API->>AuthSvc: get_current_user()
    AuthSvc->>DB: SELECT user
    AuthSvc-->>Client: UserResponse (200)

    Note over Client,DB: ── Token Refresh ──
    Client->>API: POST /refresh<br/>{refresh_token}
    API->>AuthSvc: refresh(request)
    AuthSvc->>DB: Lookup refresh_token
    AuthSvc->>DB: DELETE old refresh_token
    AuthSvc->>JWT: issue new token pair
    AuthSvc->>DB: INSERT new refresh_token
    AuthSvc-->>Client: New TokenResponse (200)
```

## 4. Upload Flow

```mermaid
sequenceDiagram
    actor Client
    participant API as /api/v1/files/upload
    participant FileSvc as FileService
    participant Storage as StorageService
    participant DB as PostgreSQL
    participant Blob as Azure Blob Storage

    Client->>API: POST /upload<br/>multipart/form-data<br/>+ Authorization header
    API->>API: Validate file size + extension
    API->>FileSvc: upload(user, file, folder_id)

    FileSvc->>Storage: generate_blob_name(user, filename)
    Storage-->>FileSvc: unique_blob_name

    FileSvc->>Storage: upload_blob(blob_name, stream)
    Storage->>Blob: upload_blob()<br/>(Azure SDK)
    Blob-->>Storage: blob_created

    FileSvc->>FileSvc: compute_sha256(stream)
    FileSvc->>DB: INSERT INTO files<br/>(name, size, checksum, blob_name, ...)
    FileSvc->>DB: INSERT INTO file_versions<br/>(version 1, current=true)

    FileSvc-->>Client: FileUploadResponse (201)
```

## 5. Deployment Architecture

```mermaid
graph TB
    subgraph "GitHub"
        REPO[Source Repository]
        CI[CI Workflow<br/>lint + test + docker build]
        CD[CD Workflow<br/>build + push + deploy + health check]
    end

    subgraph "Azure - Central India"
        ACR[Azure Container Registry<br/>crdriveproduction]
        CAE[Container Apps Environment<br/>cae-drive-production]
        CA_FE[Container App: frontend<br/>Next.js]
        CA_BE[Container App: backend<br/>FastAPI]
        PG[(PostgreSQL Flexible Server<br/>psql-drive-production)]
        REDIS[(Managed Redis<br/>redis-drive-production)]
        BLOB[(Storage Account<br/>stdriveproduction)]
        KV[Key Vault<br/>kv-drive-production]
        AI[Application Insights<br/>appi-drive-production]
    end

    REPO -->|push to main| CI
    CI -->|pass| CD
    CD -->|docker build| ACR
    CD -->|az containerapp update| CAE
    ACR -->|pull image| CA_BE
    CAE -->|hosts| CA_BE
    CAE -->|hosts| CA_FE
    CA_BE -->|asyncpg| PG
    CA_BE -->|rediss://| REDIS
    CA_BE -->|Azure SDK| BLOB
    CA_BE -->|secrets| KV
    CA_BE -->|OTLP traces| AI
```

## 6. Azure Resources

| Resource | Name | SKU / Tier | Purpose |
|---|---|---|---|
| Resource Group | `rg-drive-production` | — | Logical container |
| Container App Environment | `cae-drive-production` | — | Hosts container apps |
| Container App (Backend) | `ca-drive-backend` | 0.5 CPU, 1Gi, 1–3 replicas | FastAPI application |
| Container App (Frontend) | `ca-drive-frontend` (planned) | — | Next.js SSR |
| Container Registry | `crdriveproduction` | Basic | Docker image storage |
| PostgreSQL Flexible Server | `psql-drive-production` | B_Standard_B1ms, v16 | Users, files, folders, permissions, versions |
| Managed Redis | `redis-drive-production` | Balanced_B0 | Rate limiting, caching |
| Storage Account | `stdriveproduction` | Standard LRS | Blob storage for files |
| Key Vault | `kv-drive-production` | Standard | Secrets (JWTs, passwords, storage keys) |
| Log Analytics Workspace | `log-drive-production` | PerGB2018 | Centralized logs |
| Application Insights | `appi-drive-production` | — | Traces, metrics, alerts |

### Container App Ingress

| Setting | Value |
|---|---|
| External ingress | Enabled |
| Target port | 8000 |
| Transport | Auto (HTTP/2 → HTTP/1.1 fallback) |
| Traffic weight | 100% → latest revision |
| Revision mode | Single |

### Backend Environment Variables

| Variable | Source | Encrypted |
|---|---|---|
| `ENVIRONMENT` | Literal `production` | No |
| `DB_HOST` | PostgreSQL FQDN | No |
| `DB_PORT` | `5432` | No |
| `DB_USER` | `drive_admin` | No |
| `DB_PASSWORD` | Key Vault secret `db-password` | Yes |
| `DB_NAME` | `drive` | No |
| `REDIS_HOST` | Managed Redis hostname | No |
| `REDIS_PORT` | `6380` | No |
| `REDIS_SSL` | `true` | No |
| `REDIS_PASSWORD` | Key Vault secret `redis-password` | Yes |
| `JWT_SECRET_KEY` | Key Vault secret `jwt-secret` | Yes |
| `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name | No |
| `AZURE_STORAGE_ACCOUNT_KEY` | Key Vault secret `storage-key` | Yes |
| `AZURE_APPINSIGHTS_CONNECTION_STRING` | App Insights | No |
| `OTEL_ENABLED` | `true` | No |
| `WORKERS` | `1` | No |

## 7. Terraform Architecture

```mermaid
graph TB
    subgraph "Terraform State"
        TF[terraform.tfstate]
    end

    subgraph "Foundation"
        RG[azurerm_resource_group]
        LAW[azurerm_log_analytics_workspace]
    end

    subgraph "Security"
        KV[azurerm_key_vault<br/>+ access policy]
        KV_SECRETS[Key Vault Secrets<br/>db-password<br/>storage-account-key<br/>jwt-secret-key]
    end

    subgraph "Compute"
        CAE[azurerm_container_app_environment]
        CA[azurerm_container_app<br/>ingress: 8000<br/>revision_mode: Single]
    end

    subgraph "Data"
        PSQL[azurerm_postgresql_flexible_server<br/>+ database]
        REDIS[azurerm_managed_redis<br/>+ default_database]
        ST[azurerm_storage_account<br/>+ container]
    end

    subgraph "Registry"
        ACR[azurerm_container_registry]
    end

    subgraph "Observability"
        AI[azurerm_application_insights]
        ALERT_ERR[azurerm_monitor_metric_alert<br/>high error rate]
        ALERT_AVAIL[azurerm_monitor_metric_alert<br/>availability]
    end

    RG --> LAW
    RG --> KV
    RG --> CAE
    RG --> PSQL
    RG --> REDIS
    RG --> ST
    RG --> ACR
    RG --> AI
    KV --> KV_SECRETS
    CAE --> CA
    AI --> ALERT_ERR
    CA --> ALERT_AVAIL
```

**Provisioning order**: Resource Group → Log Analytics / Key Vault → PostgreSQL / Redis / Storage / ACR → Container App Environment → Container App → Alerts.

**Sensitive outputs**: `acr_admin_password`, `storage_account_key`, `container_app_fqdn`.

## 8. CI/CD Pipeline

```mermaid
graph LR
    subgraph "CI (on PR + push to main)"
        CHECKOUT[Checkout]
        BACKEND_TEST[Backend Tests<br/>pytest + ruff + bandit]
        DOCKER_BUILD[Docker Build<br/>backend + frontend]
        CHECKOUT --> BACKEND_TEST
        CHECKOUT --> DOCKER_BUILD
    end

    subgraph "CD (on push to main + tags)"
        CHECKOUT_CD[Checkout]
        AZURE_LOGIN[Azure Login]
        BUILD_PUSH[Build + Push to ACR]
        DEPLOY[az containerapp update]
        WAIT_PROV[Wait for provisioning<br/>poll provisioningState]
        WAIT_ACTIVE[Wait for active revision<br/>poll revision.active]
        HEALTH[Health Check<br/>12 retries × 10s<br/>+ pre-flight diagnostics<br/>+ post-mortem on failure]
        CHECKOUT_CD --> AZURE_LOGIN
        AZURE_LOGIN --> BUILD_PUSH
        BUILD_PUSH --> DEPLOY
        DEPLOY --> WAIT_PROV
        WAIT_PROV --> WAIT_ACTIVE
        WAIT_ACTIVE --> HEALTH
    end

    CI -->|on main| CD
```

### CD Health Check Details

1. **Pre-flight diagnostics** (before first curl):
   - DNS resolution of Container App FQDN
   - Container App status (provisioning state, FQDN, target port)
   - Revision status table (name, active, replicas, health state)
   - Container logs (last 50 lines)

2. **Curl retry loop**: 12 attempts × `--connect-timeout 10 --max-time 20` × 10s sleep = ~2 minutes max

3. **Post-mortem diagnostics** (on failure):
   - Container App status snapshot
   - Revision table
   - Container logs (last 100 lines)
   - Last HTTP response body

4. **Validation script**: `scripts/validate_deployment.sh` (12-step smoke test, also available as `workflow_dispatch` in `validate-deployment.yml`)

## 9. Backend Layer Architecture

```
backend/
├── app/
│   ├── api/v1/           # Presentation — HTTP endpoints
│   │   ├── auth.py       #   /auth/{register,login,me,refresh,logout}
│   │   ├── files.py      #   /files/{upload,download,delete,copy,move,rename}
│   │   ├── folders.py    #   /folders/{create,list,delete,rename}
│   │   ├── collaboration.py  # /collaboration/{share,links,permissions}
│   │   ├── versions.py   #   /versions/{list,restore,download}
│   │   ├── discovery.py  #   /discovery/{search,recent,favorites,tags}
│   │   └── health.py     #   /health, /live, /ready, /startup
│   │
│   ├── services/         # Application — use case orchestration
│   │   ├── auth.py       #   Registration, login, token management
│   │   ├── file.py       #   Upload, download, metadata
│   │   ├── folder.py     #   CRUD, nesting
│   │   ├── sharing.py    #   Links, permissions, collaboration
│   │   ├── storage.py    #   Blob abstraction, checksums
│   │   ├── versioning.py #   Version tracking, restore
│   │   ├── discovery.py  #   Search, favorites, recent
│   │   └── audit.py      #   Audit logging
│   │
│   ├── repositories/     # Infrastructure — data access
│   │   ├── user.py
│   │   ├── file.py
│   │   ├── folder.py
│   │   ├── sharing.py
│   │   └── versioning.py
│   │
│   ├── models/           # Infrastructure — SQLAlchemy ORM
│   │   ├── base.py       #   Declarative base
│   │   ├── user.py       #   User, RefreshToken
│   │   ├── file.py       #   File, Folder
│   │   ├── sharing.py    #   Permission, SharedLink
│   │   ├── versioning.py #   FileVersion
│   │   └── discovery.py  #   Tag, Favorite, RecentFile
│   │
│   ├── schemas/          # Interface — Pydantic DTOs
│   │   ├── auth.py       #   RegisterRequest, LoginRequest, TokenResponse
│   │   ├── file.py       #   FileUploadResponse, FileMetadataResponse
│   │   └── ...
│   │
│   ├── middleware/        # Infrastructure — ASGI middleware
│   │   ├── security_headers.py      # HSTS, X-Frame-Options, CSP
│   │   ├── correlation_id.py        # X-Request-Id / trace_id
│   │   ├── request_logger.py        # Structured request logging
│   │   ├── rate_limiter.py          # Redis-backed rate limiting
│   │   ├── metrics.py               # Prometheus-compatible counters
│   │   └── timeout.py               # Request timeout (60s)
│   │
│   ├── auth/             # Infrastructure — JWT + password
│   │   ├── jwt.py        #   Token encode/decode
│   │   └── password.py   #   Argon2 hashing (passlib)
│   │
│   ├── storage/          # Infrastructure — blob abstraction
│   │   ├── base.py       #   StorageBackend interface
│   │   └── azure_blob.py #   Azure Blob Storage implementation
│   │
│   ├── dependencies/     # Shared — DI providers
│   │   ├── auth.py       #   get_current_user, require_role
│   │   ├── database.py   #   get_db (AsyncSession)
│   │   ├── redis.py      #   get_redis (async Redis client)
│   │   └── storage.py    #   get_storage_service
│   │
│   ├── core/             # Shared — config, utilities
│   │   ├── config/       #   Pydantic Settings
│   │   ├── logging_config.py  # structlog configuration
│   │   ├── otel.py       #   OpenTelemetry setup
│   │   ├── error_handlers.py  # Global exception handlers
│   │   └── exceptions.py      # AppError, StorageError, etc.
│   │
│   └── main.py           # Application factory + lifespan
│
├── migrations/           # Alembic database migrations
│   ├── env.py           # Async migration runner
│   └── versions/        # 001–007 migration scripts
│
├── tests/                # pytest + pytest-asyncio
│   ├── conftest.py      # Fixtures: test DB (SQLite), mock storage, auth
│   ├── test_health.py
│   ├── test_auth.py
│   ├── test_phase*.py   # Phase 1–7 feature tests
│   ├── test_storage.py
│   ├── test_middleware.py
│   ├── test_error_handlers.py
│   ├── test_regression_fixes.py
│   └── e2e/             # End-to-end tests
│
├── Dockerfile.prod       # Multi-stage production image
├── Dockerfile.dev        # Development hot-reload image
├── requirements.txt      # Pinned dependencies
├── pyproject.toml        # Python project config
└── alembic.ini           # Alembic configuration
```

## 10. Database Schema

```mermaid
erDiagram
    users ||--o{ files : owns
    users ||--o{ folders : owns
    users ||--o{ refresh_tokens : has
    users ||--o{ permissions : granted
    users ||--o{ favorites : has
    users ||--o{ recent_files : accesses

    folders ||--o{ folders : parent
    folders ||--o{ files : contains

    files ||--o{ file_versions : has
    files ||--o{ permissions : on
    files ||--o{ shared_links : linked
    files ||--o{ favorites : favorited
    files ||--o{ recent_files : accessed
    files ||--o{ tags : tagged

    users {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        enum role "user|admin"
        bool is_active
        bool is_verified
        datetime created_at
        datetime updated_at
        bool is_deleted
    }

    refresh_tokens {
        uuid id PK
        uuid user_id FK
        string token UK
        datetime expires_at
        datetime created_at
    }

    folders {
        uuid id PK
        string name
        uuid owner_id FK
        uuid parent_id FK
        datetime created_at
        datetime updated_at
        bool is_deleted
    }

    files {
        uuid id PK
        string name
        bigint size
        string mime_type
        string checksum
        string blob_name UK
        uuid owner_id FK
        uuid folder_id FK
        json metadata
        datetime created_at
        datetime updated_at
        bool is_deleted
    }

    file_versions {
        uuid id PK
        uuid file_id FK
        int version_number
        string blob_name
        bigint size
        string checksum
        bool is_current
        datetime created_at
    }

    permissions {
        uuid id PK
        uuid resource_id
        string resource_type
        uuid user_id FK
        enum role "owner|editor|commenter|viewer"
        datetime created_at
    }

    shared_links {
        uuid id PK
        uuid resource_id
        string resource_type
        uuid owner_id FK
        string token UK
        string password_hash
        enum access_level "view|comment|edit"
        datetime expires_at
        bool is_active
        datetime created_at
    }

    tags {
        uuid id PK
        string name
        uuid user_id FK
        datetime created_at
    }
```

## 11. Middleware Execution Order

Requests pass through middleware in this order:

```
Client Request
    │
    ▼
┌─────────────────────────┐
│ 1. RequestTimeout       │  60s timeout per request
├─────────────────────────┤
│ 2. SecurityHeaders      │  HSTS, XFO, XSS, CSP, cache-control
├─────────────────────────┤
│ 3. CorrelationId        │  X-Request-Id, X-Trace-Id headers
├─────────────────────────┤
│ 4. RequestLogger        │  Structured JSON logging (structlog)
├─────────────────────────┤
│ 5. RateLimiter          │  Redis-backed, path-specific limits
├─────────────────────────┤
│ 6. Metrics              │  Prometheus-compatible counters
├─────────────────────────┤
│ 7. CORS                 │  Origin validation
├─────────────────────────┤
│ FastAPI Router          │  JWT auth dependency → Service → Repository
└─────────────────────────┘
    │
    ▼
Client Response
```

## 12. Technology Stack Summary

| Layer | Technology | Version |
|---|---|---|
| **Backend Framework** | FastAPI | ≥0.115, <1.0 |
| **Python** | CPython | 3.13 |
| **ASGI Server** | Uvicorn | ≥0.30, <1.0 |
| **ORM** | SQLAlchemy (async) | ≥2.0.30, <3.0 |
| **Database Driver** | asyncpg | ≥0.29, <1.0 |
| **Migrations** | Alembic | ≥1.13, <2.0 |
| **Validation** | Pydantic | ≥2.7, <3.0 |
| **Configuration** | pydantic-settings | ≥2.3, <3.0 |
| **Auth — Hashing** | passlib + argon2 | ≥1.7.4, <2.0 |
| **Auth — Tokens** | python-jose + cryptography | ≥3.3, <4.0 |
| **Redis Client** | redis-py (async) | ≥5.0, <6.0 |
| **Blob Storage** | azure-storage-blob | ≥12.20, <13.0 |
| **Azure Identity** | azure-identity | ≥1.16, <2.0 |
| **Logging** | structlog | ≥24.2, <25.0 |
| **Tracing** | OpenTelemetry (API + SDK + OTLP) | ≥1.20, <2.0 |
| **HTTP Client** | httpx | ≥0.27, <1.0 |
| **Testing** | pytest + pytest-asyncio | — |
| **Frontend Framework** | Next.js | 15.x |
| **Frontend UI** | React | 19.x |
| **CSS** | Tailwind CSS | 3.4 |
| **IaC** | Terraform + azurerm | ≥1.5 / ~>4.0 |
| **CI/CD** | GitHub Actions | — |
| **Container Runtime** | Docker (multi-stage) | — |
