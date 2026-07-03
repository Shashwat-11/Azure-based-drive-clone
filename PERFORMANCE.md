# Performance

This document describes the performance characteristics, known bottlenecks, and optimization strategies for the Drive cloud storage platform.

---

## Architecture Considerations

- **Async-first design**: FastAPI + SQLAlchemy async + Azure SDK async ensure the event loop is never blocked by I/O. Database queries, Redis operations, and blob storage calls all release the event loop while waiting.
- **Connection pooling**: SQLAlchemy's `AsyncEngine` uses `pool_size=20` and `max_overflow=10` with `pool_pre_ping=True`. Each request obtains a session from the pool and returns it after the response.
- **Stateless application**: No in-memory session state. All state lives in PostgreSQL, Redis, or Azure Blob Storage. Instances can be scaled horizontally behind a load balancer.
- **Streaming file operations**: `upload_stream` uses Azure's block-based staging (`stage_block`/`commit_block_list`) to avoid buffering entire files. `download_stream` yields chunks via `AsyncIterator[bytes]`. The `download` method currently loads blobs into memory via `readall()` — this is a known limitation for large files.

---

## Current Bottlenecks

| Component | Bottleneck | Mitigation |
|---|---|---|
| PostgreSQL | Single-instance, no read replicas | Sufficient for development and initial deployment. Read replicas planned for production. |
| Redis | Single-instance, no sentinel/cluster | Sufficient for rate limiting. Sentinel/Cluster planned if Redis becomes critical path. |
| File upload | `download()` loads entire blob into memory | Use `download_stream()` for large files. `download()` intended for small file previews only. |
| Token validation | DB query on every `/me` request | JWT signature validation is in-memory. DB query only fetches user to check `is_active` status. |
| Health check | Sequential dependency checks | Three parallel `asyncio.gather()` calls would reduce readiness probe latency. |

---

## Database Optimization

### Indexes (Implemented)

| Table | Index | Type | Purpose |
|---|---|---|---|
| `users` | `ix_users_email` | UNIQUE B-tree | Login lookup, email uniqueness |
| `users` | `ix_users_created_at` | B-tree | Time-range queries |
| `users` | `ix_users_is_deleted` | B-tree | Soft-delete filtering |
| `refresh_tokens` | `ix_refresh_tokens_token_hash` | UNIQUE B-tree | Token lookup (most frequent query) |
| `refresh_tokens` | `ix_refresh_tokens_user_id` | B-tree | Batch revocation by user |
| `refresh_tokens` | `ix_refresh_tokens_created_at` | B-tree | Time-range queries |

### Connection Pooling

```
pool_size: 20         # Concurrent connections maintained
max_overflow: 10      # Additional connections under load (max 30)
pool_timeout: 30s     # Wait before raising TimeoutError
pool_pre_ping: true   # Verify connection is alive before use
```

### Query Patterns

- All queries filter by `is_deleted == False` to exclude soft-deleted rows.
- `get_by_email` uses `SELECT ... WHERE email = $1` with a UNIQUE index — O(log n).
- `get_by_token` uses `SELECT ... WHERE token_hash = $1` with a UNIQUE index — O(log n).
- `revoke_all_for_user` uses `SELECT ... WHERE user_id = $1 AND is_revoked = FALSE` — indexed by `user_id`.

---

## Streaming Uploads (Implemented)

Azure Blob Storage block-based upload strategy:

1. **Each chunk** from the `AsyncIterator[bytes]` is uploaded as a separate block via `stage_block()`.
2. **Block IDs** are sequentially generated using base64 encoding.
3. **After all blocks**, `commit_block_list()` assembles the blob.
4. **Metadata and content type** are set after upload via `set_http_headers()` and `set_metadata()`.

**Trade-off**: Each chunk becomes an API call to Azure. For many small chunks, this increases latency. A future optimization would buffer chunks up to ~4MB before staging a block.

**Memory usage**: O(chunk_size) — only one chunk in memory at a time. No accumulation of chunks in Python lists.

---

## Streaming Downloads (Implemented)

`download_stream()` uses Azure SDK's `download_blob().chunks()` generator:

- Yields chunks as `AsyncIterator[bytes]` without accumulating.
- Default Azure SDK chunk size is applied (typically 4MB).
- Consumer (e.g., FastAPI `StreamingResponse`) can stream directly to the HTTP client.

---

## Caching Strategy

### Redis Usage (Implemented)

| Use Case | Data Structure | TTL |
|---|---|---|
| Rate limiting | String (counter) | 60 seconds |

### Redis Usage (Planned)

| Use Case | Data Structure | TTL | Priority |
|---|---|---|---|
| User session cache | Hash | Session lifetime | Medium |
| File metadata cache | String (JSON) | 5 minutes | High |
| Folder listing cache | String (JSON) + Sorted Set | 1 minute | High |
| Token blacklist | Set + String | Token expiry | Medium |

### Caching Principles

- Cache-aside pattern: check Redis first, fall back to PostgreSQL on miss.
- Invalidation on write: delete or update cached entries when data changes.
- TTL-based expiry for all cache entries to prevent stale data accumulation.
- Redis is optional: the application functions correctly without Redis (rate limiter bypasses gracefully).

---

## Expected Scalability

| Metric | Development | Production (Estimated) |
|---|---|---|
| Concurrent requests | ~50 | ~500–1000 (per instance) |
| Database connections | 20 pool | 40–80 pool |
| File upload size | Up to 100 MB | Up to 10 GB (block-based) |
| Users | Unlimited | Unlimited (horizontally scalable) |
| Files per user | Unlimited | Performance degrades with 100k+ flat files per folder |

---

## Future Optimization Ideas

- **Database read replicas**: Route read queries (file listing, search) to read replicas, keeping the primary for writes.
- **Connection pooling proxy**: PgBouncer in front of PostgreSQL for connection multiplexing under high concurrency.
- **CDN for downloads**: Azure CDN in front of Blob Storage for cached, low-latency file downloads.
- **Async health checks**: Run database, Redis, and storage health checks in parallel using `asyncio.gather()`.
- **Redis Cluster**: For high-availability caching and rate limiting across availability zones.
- **File chunking**: Client-side chunking for uploads >100MB with resume capability.
- **Background thumbnail generation**: Offload image/video preview generation to a background worker.
- **Query result caching**: Cache frequent read queries (e.g., root folder listing) in Redis.

---

## Benchmarks

**TODO**: All benchmark data is pending. Benchmarks will be collected using `pytest-benchmark` and `locust` once the following conditions are met:

- [ ] PostgreSQL running with representative data volume (100k+ users, 1M+ files)
- [ ] Azure Blob Storage with representative file sizes (1KB, 1MB, 100MB, 1GB)
- [ ] Application deployed in an Azure Container App with production-like resources
- [ ] Load test scenario defined (login, upload, download, list, search)

---

## Profiling Tools

| Tool | Purpose | Status |
|---|---|---|
| `pytest --durations=10` | Identify slowest test cases | In use |
| `asyncpg` query logging | Identify slow database queries | Configurable via `DB_ECHO=true` |
| `py-spy` | CPU profiling for async Python | Planned |
| `cProfile` / `snakeviz` | Synchronous code profiling | Planned |
| Application Insights Profiler | Production profiling in Azure | Planned |

---

## Load Testing Strategy

Load tests will be conducted using **Locust** (Python-based, supports async scenarios):

1. **Authentication**: Concurrent login requests with valid and invalid credentials.
2. **File upload**: Concurrent uploads of varying sizes (1KB, 1MB, 100MB).
3. **File download**: Concurrent downloads with streaming verification.
4. **Folder listing**: Paginated listing with deep hierarchies.
5. **Search**: Full-text search with concurrent read/write load.

**TODO**: Locust test scripts and performance targets will be defined in a future phase.
