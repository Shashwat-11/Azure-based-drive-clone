# Phase 1

- [x] Initialize project
- [x] Configure FastAPI
- [x] Configure Next.js
- [x] Docker Compose
- [x] PostgreSQL
- [x] Redis
- [x] Alembic
- [x] Azure Storage SDK

---

# Phase 2

- [x] User model
- [x] JWT
- [x] Refresh tokens
- [x] Login
- [x] Register
- [x] RBAC

---

# Phase 3

- [x] Azure Blob upload
- [x] Download
- [x] Delete
- [x] Rename (via folder/file update)
- [x] Folder CRUD
- [x] File metadata APIs
- [x] Streaming upload with SHA-256
- [x] Streaming download
- [x] Transaction compensation (orphan blobs)
- [x] Validation (filename, MIME, extension, size)
- [x] Audit logging

---

# Phase 4

- [x] Folder tree
- [x] Move (file + folder)
- [x] Copy (file + folder)
- [x] Trash (list, restore, empty)
- [x] Recursive soft delete
- [x] Recursive restore
- [x] Permanent delete
- [x] Rename (file + folder)
- [x] Folder size calculation (recursive CTE)
- [x] Breadcrumbs
- [x] Circular reference prevention

---

# Phase 5

- [x] Permission model (Permission, SharedLink tables)
- [x] Share file/folder (create/update/remove permissions)
- [x] List collaborators
- [x] Shared links (create, manage, revoke)
- [x] Password-protected links (Argon2)
- [x] Link expiry and download limits
- [x] Transfer ownership
- [x] Shared with me / Shared by me endpoints
- [x] Permission inheritance (folder → file/subfolder)
- [x] Permission integration into existing file/folder endpoints
- [x] Authorization dependency (require_file_access, require_folder_access)

---

# Phase 6

- [x] FileVersion model with immutable version tracking
- [x] Version creation on upload (version_number, blob_name, checksum, is_current)
- [x] List versions endpoint (paginated by version_number DESC)
- [x] Version download (streaming with checksum header)
- [x] Version restore (creates new version via Azure blob copy)
- [x] Version delete (prevents deleting current or only version)
- [x] Version authorization (shared permissions control access)

---

# Phase 7

- [x] Search by filename, extension, MIME type, folder, size, tag, favorites
- [x] Metadata columns: description, color_label, custom_properties (JSONB)
- [x] Tags: create, list, delete, assign to files, search by tag
- [x] Favorites: add, remove, list, search favorite-only
- [x] Recent files tracking
- [x] Permission-aware search (owner-scoped)
