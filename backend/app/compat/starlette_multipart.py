"""
Starlette multipart upload size limit override.

Starlette's MultiPartParser defaults max_part_size to 1 MB
(formparsers.py:149, requests.py:273). FastAPI calls
request.form() without arguments, so every file part >1 MB
is rejected before reaching the endpoint handler.

The only supported way to change this is passing max_part_size
to Request.form(), but FastAPI calls it internally. There is
no FastAPI/Starlette configuration setting for this limit.

Upstream issue: https://github.com/encode/starlette/issues/2522

Target: Starlette 1.3.1 (shipped with FastAPI 0.139.0)

This module patches Request.form() to use the application's
MAX_UPLOAD_SIZE_MB setting. Remove this module when Starlette
exposes a supported configuration mechanism.
"""

from __future__ import annotations

from starlette.requests import Request as _StarletteRequest

from app.config.settings import settings

_original_form = _StarletteRequest.form


async def _patched_form(self, *, max_files=1000, max_fields=1000, **kwargs):
    return await _original_form(
        self,
        max_files=max_files,
        max_fields=max_fields,
        max_part_size=settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024,
        **kwargs,
    )


def apply_upload_limit_patch() -> None:
    """Override Starlette's 1 MB default with MAX_UPLOAD_SIZE_MB."""
    _StarletteRequest.form = _patched_form  # type: ignore[method-assign]
