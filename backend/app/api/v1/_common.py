from __future__ import annotations

import uuid as uuid_mod

from fastapi import Request


def get_trace_id(request: Request | None) -> str:
    if request is None:
        return ""
    return getattr(request.state, "trace_id", "")


def parse_uuid(val: str | None) -> uuid_mod.UUID | None:
    if val:
        return uuid_mod.UUID(val)
    return None
