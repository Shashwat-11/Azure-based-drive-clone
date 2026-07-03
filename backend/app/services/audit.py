from __future__ import annotations

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class AuditService:
    @staticmethod
    def log_upload(
        trace_id: str,
        user_id: str,
        file_id: str,
        folder_id: str | None,
        blob_name: str,
        filename: str,
        checksum: str,
        size: int,
        mime_type: str | None,
    ) -> None:
        logger.info(
            "audit_file_uploaded",
            trace_id=trace_id,
            user_id=user_id,
            file_id=file_id,
            folder_id=folder_id,
            blob_name=blob_name,
            filename=filename,
            checksum=checksum,
            size=size,
            mime_type=mime_type,
        )

    @staticmethod
    def log_download(
        trace_id: str,
        user_id: str,
        file_id: str,
        blob_name: str,
        filename: str,
    ) -> None:
        logger.info(
            "audit_file_downloaded",
            trace_id=trace_id,
            user_id=user_id,
            file_id=file_id,
            blob_name=blob_name,
            filename=filename,
        )

    @staticmethod
    def log_delete(
        trace_id: str,
        user_id: str,
        file_id: str,
        blob_name: str,
        filename: str,
    ) -> None:
        logger.info(
            "audit_file_deleted",
            trace_id=trace_id,
            user_id=user_id,
            file_id=file_id,
            blob_name=blob_name,
            filename=filename,
        )

    @staticmethod
    def log_folder_created(
        trace_id: str,
        user_id: str,
        folder_id: str,
        name: str,
        parent_id: str | None,
    ) -> None:
        logger.info(
            "audit_folder_created",
            trace_id=trace_id,
            user_id=user_id,
            folder_id=folder_id,
            name=name,
            parent_id=parent_id,
        )

    @staticmethod
    def log_folder_deleted(
        trace_id: str,
        user_id: str,
        folder_id: str,
        name: str,
    ) -> None:
        logger.info(
            "audit_folder_deleted",
            trace_id=trace_id,
            user_id=user_id,
            folder_id=folder_id,
            name=name,
        )
