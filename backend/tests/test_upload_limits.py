"""Tests for the Starlette multipart upload size compatibility module."""

from __future__ import annotations

from starlette.formparsers import MultiPartException
from starlette.requests import Request

from app.compat.starlette_multipart import _original_form, _patched_form


class TestUploadLimitPatch:
    """Verify the multipart size limit patch is correctly applied."""

    def test_patched_form_passes_max_part_size(self) -> None:
        """_patched_form should exist and call _original_form."""
        assert _patched_form is not _original_form
        assert callable(_patched_form)

    def test_override_is_applied(self) -> None:
        """After importing app.main, Request.form should be our patched version."""
        import app.main  # noqa: F401 — triggers apply_upload_limit_patch()

        assert Request.form is _patched_form


class TestMultipartExceptionHandler:
    """Verify the MultiPartException handler is registered."""

    def test_handler_registered(self) -> None:
        """The FastAPI app should have a handler for MultiPartException."""
        import app.main

        app = app.main.app
        handlers = dict(app.exception_handlers)

        assert MultiPartException in handlers, (
            "MultiPartException handler not registered. "
            "Expected add_exception_handler(MultiPartException, multipart_exception_handler)"
        )

    def test_handler_is_multipart_handler(self) -> None:
        """The registered handler should be multipart_exception_handler."""
        import app.main
        from app.core.error_handlers import multipart_exception_handler

        app = app.main.app
        handler = dict(app.exception_handlers).get(MultiPartException)
        assert handler is multipart_exception_handler
