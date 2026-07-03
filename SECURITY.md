# Security

This document describes the security architecture, implemented controls, known limitations, and future improvements for the Drive cloud storage platform.

---

## Authentication

### Implemented

- **JWT access tokens**: Short-lived (30 minutes, configurable). Signed with HS256. Contains `sub` (user UUID), `role`, `type`, `iat`, `exp`, `iss`, `jti`.
- **JWT refresh tokens**: Long-lived (7 days, configurable). Signed with HS256. Stored server-side as SHA-256 hash, never stored as plaintext.
- **Refresh token rotation**: Each refresh operation revokes the old token and issues a new one. Reuse of a revoked token is detected and rejected.
- **Argon2 password hashing**: Passwords hashed with Argon2 via `passlib` (`CryptContext(schemes=["argon2"])`). The `deprecated="auto"` setting ensures algorithm upgrades over time.
- **User enumeration prevention**: Login returns the same error message ("Invalid email or password") for wrong password and nonexistent user, preventing email harvesting.
- **Logout**: Revokes the specific refresh token without affecting other sessions.

### Planned

- **Email verification**: Newly registered users will receive a verification email with a time-limited token.
- **Password reset**: Self-service password reset via email link with expiration.
- **OAuth 2.0 / OpenID Connect**: Google and Microsoft OAuth integration as alternative login methods.
- **Multi-factor authentication (MFA)**: TOTP-based second factor for sensitive operations.
- **Account lockout**: Automatically lock accounts after N consecutive failed login attempts.
- **HS256 → RS256 migration**: Move to asymmetric key signing for multi-service JWT verification.

---

## Authorization

### Implemented

- **Role-Based Access Control (RBAC)**: Three roles — `admin`, `user`, `viewer`.
- **`require_role()` dependency**: Declarative endpoint-level authorization. Example: `require_role(UserRole.ADMIN)` restricts endpoints to admin users.
- **Role claim in JWT**: Each access token carries a `role` claim. The `get_current_user` dependency validates this claim on every authenticated request.
- **Active user check**: The `get_current_user` dependency verifies `is_active == True` on every request, allowing instant deactivation without token invalidation.

### Planned

- **Resource-level permissions**: File/folder-specific permissions (owner, editor, viewer, commenter) as defined in the project spec.
- **Permission inheritance**: Subfolders inherit parent folder permissions unless overridden.
- **Share link access control**: Public links with optional password protection and expiry dates.

---

## JWT Strategy

```
Access Token:
  Header:  {"alg": "HS256", "typ": "JWT"}
  Payload: {"sub": "<uuid>", "role": "<role>", "type": "access",
            "iat": <timestamp>, "exp": <timestamp>, "iss": "drive-api", "jti": "<uuid>"}

Refresh Token:
  Header:  {"alg": "HS256", "typ": "JWT"}
  Payload: {"sub": "<uuid>", "type": "refresh",
            "iat": <timestamp>, "exp": <timestamp>, "iss": "drive-api", "jti": "<uuid>"}
```

- **Signature verification**: Every token is verified using `python-jose` with `verify_exp=True` and `verify_iss=True`.
- **Token type enforcement**: `type` claim distinguishes access tokens from refresh tokens. Refresh endpoints reject access tokens and vice versa.
- **Issuer validation**: `iss` claim must match `JWT_ISSUER` ("drive-api").
- **Secret key management**: `JWT_SECRET_KEY` is stored as `SecretStr` in Pydantic settings. It is never logged, serialized, or exposed in error messages. In production, this should come from Azure Key Vault.

---

## Password Hashing

### Implemented

- **Algorithm**: Argon2 (via `passlib.context.CryptContext`)
- **Configuration**: `schemes=["argon2"]` with `deprecated="auto"`
- **Minimum length**: 8 characters (enforced by Pydantic `Field(min_length=8)`)
- **Maximum length**: 128 characters (prevents DoS via extremely long passwords)

### Planned

- **Password complexity rules**: Require at least one uppercase letter, one lowercase letter, and one digit.
- **Password strength meter**: Integration with `zxcvbn` for real-time strength feedback in the frontend.
- **Breached password check**: Check against Have I Been Pwned API (k-anonymity model) during registration and password change.

---

## Threat Model

### Assets

| Asset | Sensitivity | Storage Location |
|---|---|---|
| User credentials (email, password hash) | High | PostgreSQL |
| JWT secrets | Critical | Environment variables / Azure Key Vault (planned) |
| File content | Varies | Azure Blob Storage |
| File metadata | Medium | PostgreSQL |
| Refresh tokens (hashed) | Medium | PostgreSQL |
| Session state | Low | Redis (planned) |

### Threats Mitigated

| Threat | Mitigation |
|---|---|
| Password brute force | Rate limiting on login endpoint; Argon2 with high memory cost |
| Token theft (XSS) | Short access token lifetime (30 min); HttpOnly cookies (planned) |
| Token replay | Refresh token rotation; `jti` claim for future blacklisting |
| SQL injection | SQLAlchemy parameterized queries; all input validated via Pydantic |
| User enumeration | Identical error messages for login failures |
| Privilege escalation | RBAC enforced on every request; role claim in JWT |
| File enumeration | UUID-based blob names (unguessable) |
| Cross-origin attacks | CORS configured from settings; Security headers middleware |
| Man-in-the-middle | HSTS header (HTTPS only); TLS termination at Azure |
| Credential stuffing | Rate limiting on auth endpoints |

### Threats Not Yet Mitigated

| Threat | Risk Level | Planned Mitigation |
|---|---|---|
| Access token in URL | Low | Tokens only accepted via Authorization header |
| Refresh token in local storage | Medium | HttpOnly, Secure, SameSite cookies (Phase 5+) |
| Large file upload DoS | Medium | Upload size limit (100MB); streaming to prevent memory exhaustion |
| Expired token accumulation | Low | Background cleanup job for revoked/expired refresh tokens |
| Insider threat (DB access) | Medium | Field-level encryption for sensitive metadata (Phase 5+) |

---

## OWASP Considerations

### Implemented Controls

| OWASP Category | Control |
|---|---|
| A01: Broken Access Control | RBAC with `require_role()`; `get_current_user` validates on every request |
| A02: Cryptographic Failures | Argon2 for passwords; SHA-256 for token hashing; JWT with signature verification |
| A03: Injection | SQLAlchemy parameterized queries; Pydantic input validation |
| A04: Insecure Design | Clean Architecture with threat model; security review process |
| A05: Security Misconfiguration | `.env.example` with placeholders; `SecretStr` for secrets; security headers middleware |
| A07: Identification and Authentication Failures | Rate limiting on login; user enumeration prevention; token rotation |

### Controls In Progress

| OWASP Category | Planned Control |
|---|---|
| A05: Security Misconfiguration | Azure Key Vault for production secrets |
| A08: Software and Data Integrity Failures | Docker image signing (CI/CD); dependency vulnerability scanning (Dependabot) |

---

## Input Validation

### Implemented

- **Email**: Validated via Pydantic `EmailStr` (requires `email-validator` package). Maximum length 320 characters.
- **Password**: Minimum 8 characters, maximum 128 characters.
- **Full name**: Minimum 1 character, maximum 255 characters.
- **Request body**: All API inputs validated via Pydantic models. Malformed requests return 422 with detailed error information.
- **Path parameters**: FastAPI validates UUID format for resource IDs.

### Planned

- **File content type validation**: Validate MIME type against an allowlist before accepting uploads.
- **File name sanitization**: Strip or encode special characters in file names.
- **File size validation**: Enforce `MAX_UPLOAD_SIZE_MB` at both the application and proxy/load balancer level.

---

## Rate Limiting

### Implemented

- **Middleware**: `RateLimiterMiddleware` intercepts requests to `/api/v1/auth/login` and `/api/v1/auth/register`.
- **Algorithm**: Redis-based token bucket using `INCR` (increment counter) + `EXPIRE` (set window TTL).
- **Defaults**: 100 requests per 60-second window per IP address + endpoint.
- **Response**: Returns 429 with `Retry-After` header and standardized error body.
- **Graceful degradation**: If Redis is unavailable, the rate limiter bypasses with a warning log — availability over security hardening.

### Planned

- **Global rate limiting**: Apply rate limits to all endpoints, not just auth.
- **Per-user rate limits**: Authenticated users get higher limits than unauthenticated requests.
- **Configurable limits per endpoint**: Different limits for login (stricter) vs. file listing (more permissive).

---

## Security Headers

### Implemented

All HTTP responses include the following security headers (via `SecurityHeadersMiddleware`):

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Enable browser XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer information |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Disable sensitive browser features |
| `Cache-Control` | `no-store, max-age=0` | Prevent caching of sensitive responses |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforce HTTPS (only when `scheme` is HTTPS) |

The headers can be toggled via `SECURE_HEADERS_ENABLED` environment variable.

---

## Secrets Management

### Current Approach (Development)

- Secrets stored as `SecretStr` in Pydantic settings.
- `.env` file loaded at startup (gitignored).
- `JWT_SECRET_KEY` has a default value for development; must be overridden in staging/production.
- `DB_PASSWORD`, `AZURE_STORAGE_ACCOUNT_KEY`, `AZURE_STORAGE_CONNECTION_STRING` stored as `SecretStr`.

### Azure Key Vault Integration (Planned)

**Goal**: Eliminate hardcoded secrets and `.env` files in production.

**Plan**:

1. Use `azure-identity` `DefaultAzureCredential` for managed identity authentication.
2. Use `azure-keyvault-secrets` to fetch secrets at application startup.
3. Map Key Vault secret names to Pydantic Settings fields.
4. Implement secret rotation without application restart via Key Vault's versioned secrets.
5. Cache secrets in-memory with configurable refresh interval.

---

## File Upload Validation

### Implemented

- **Pre-upload size validation**: `UploadFile.size` (from HTTP Content-Length header) is checked before any Azure interaction. Oversized files are rejected immediately with a 422 response.
- **Post-upload size validation**: After the file is streamed and uploaded, the computed file size is validated again. If the file exceeds the limit (possible when Content-Length is absent or inaccurate), the uploaded Azure blob is automatically deleted to prevent orphaned storage.
- **Size limit**: `MAX_UPLOAD_SIZE_MB` (default 100MB) enforced by application configuration.
- **Extension allowlist**: `ALLOWED_UPLOAD_EXTENSIONS` (default `None` = all allowed, configurable).

### Planned

- **MIME type validation**: Verify file content matches declared MIME type (magic bytes check).
- **Virus scanning interface**: Abstract interface for integration with ClamAV or Azure Defender for Cloud.
- **Content disposition validation**: Prevent HTML/JS file uploads that could be served as XSS payloads.

---

## Logging of Security Events

The following security-relevant events are logged with structured JSON:

| Event | Log Level | Fields |
|---|---|---|
| User registration | INFO | `user_id`, `email` |
| Login success | INFO | `user_id`, `email` |
| Login failure (wrong password) | WARNING | `user_id`, `email` |
| Login failure (nonexistent user) | WARNING | `email` |
| Token creation | INFO | `user_id`, `role` |
| Token refresh | INFO | `user_id` |
| Token revocation | INFO | `token_id`, `user_id` |
| Token decode failure | WARNING | `error` |
| Rate limit exceeded | WARNING | `client_ip`, `path`, `count`, `limit` |
| Account deactivated (login blocked) | WARNING | `user_id` |

---

## Known Security Limitations

1. **HS256 algorithm**: Symmetric signing uses a shared secret. If the secret is compromised, all tokens can be forged. Mitigation: migrate to RS256 (asymmetric) before multi-service deployment.
2. **No token blacklist**: Revoked access tokens are not tracked. An access token remains valid until expiry (30 min max). Mitigation: short token lifetime. JWT `jti` blacklist in Redis is planned.
3. **No email verification**: Anyone can register with any email address. Mitigation: email verification is planned for Phase 5+.
4. **No account lockout**: Brute force is limited only by rate limiting (100 req/min/IP). Mitigation: account lockout after N failures is planned.
5. **Download endpoint memory load**: The `download()` method loads entire blob into memory. Mitigation: use `download_stream()` for large files; `download()` documented as intended for small files only.
6. **Redis as single point of failure for rate limiting**: If Redis is down, rate limiting is bypassed. Mitigation: Redis is not a dependency for core functionality; rate limiting is a defense-in-depth layer.

---

## Future Security Improvements

- [ ] Migrate JWT from HS256 to RS256 with key rotation
- [ ] Implement Azure Key Vault integration for all secrets
- [ ] Add email verification flow
- [ ] Implement account lockout after N failed attempts
- [ ] Add virus scanning interface for uploaded files
- [ ] Implement signed URLs for secure blob access
- [ ] Add field-level encryption for sensitive user metadata
- [ ] Integrate Dependabot or Renovate for automated dependency updates
- [ ] Conduct penetration testing before production deployment
- [ ] Implement Content Security Policy (CSP) headers
- [ ] Add audit logging for all permission changes

---

## Incident Response Considerations

**TODO**: A formal incident response plan will be developed before production deployment. Key areas to address:

- [ ] Incident classification (severity levels)
- [ ] Escalation paths and on-call rotation
- [ ] Communication templates (internal and customer-facing)
- [ ] Forensic data collection (logs, database snapshots)
- [ ] Recovery procedures (token invalidation, data restoration)
- [ ] Post-mortem template and process
