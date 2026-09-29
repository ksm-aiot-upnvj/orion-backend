import io
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import BinaryIO, Literal

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import settings

logger = logging.getLogger("orion.storage")

UploadKind = Literal["avatars", "cvs"]
KIND_EXTENSIONS: dict[str, str] = {"avatars": "webp", "cvs": "pdf"}

# Staged uploads live in tmp/<kind>/<uuid4>.<ext> until the owning form is saved.
STAGED_PATH_RE = re.compile(
    r"^tmp/(avatars|cvs)/([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\.(webp|pdf)$"
)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB per UU PDP / GDPR guideline
MAX_CV_SIZE_BYTES = 5 * 1024 * 1024  # 5MB for CV PDF


def validate_image_magic_bytes(header: bytes) -> str:
    """
    Validate image magic bytes (file signature) to prevent disguise/polyglot file uploads.
    Supports JPEG, PNG, and WebP.
    """
    if len(header) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File terlalu kecil atau header citra rusak.",
        )
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Header file tidak valid (Magic Bytes mismatch). Harap unggah file citra JPEG, PNG, atau WebP yang asli.",
    )


def validate_pdf_magic_bytes(header: bytes) -> None:
    """Validate PDF magic bytes (%PDF-)."""
    if len(header) < 5 or not header.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Berkas bukan merupakan dokumen PDF yang valid (Magic Bytes mismatch). Harap unggah dokumen PDF asli.",
        )


class StorageService:
    def __init__(self, base_upload_dir: str | None = None):
        self.base_dir = Path(base_upload_dir or settings.UPLOAD_DIR).resolve()
        self.avatars_dir = self.base_dir / "avatars"
        self.cvs_dir = self.base_dir / "cvs"
        self.tmp_dir = self.base_dir / "tmp"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create storage directories if they do not exist."""
        for kind in KIND_EXTENSIONS:
            (self.base_dir / kind).mkdir(parents=True, exist_ok=True)
            (self.tmp_dir / kind).mkdir(parents=True, exist_ok=True)

    def process_and_save_avatar(self, file_stream: BinaryIO, content_type: str | None = None) -> str:
        """
        Process, sanitize, strip EXIF metadata, convert to WebP, and stage image securely.
        Returns the staged relative path: 'tmp/avatars/<uuid4>.webp' (see promote_upload).
        """
        # Read file bytes to check size
        file_stream.seek(0, os.SEEK_END)
        size = file_stream.tell()
        file_stream.seek(0)

        if size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ukuran file terlalu besar ({size / 1024 / 1024:.2f}MB). Maksimal 2MB.",
            )

        if size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File tidak boleh kosong.",
            )

        # 1. Magic Bytes Validation (Check first 16 bytes)
        header = file_stream.read(16)
        file_stream.seek(0)
        validate_image_magic_bytes(header)

        try:
            # 2. Open image with Pillow to validate structure
            image = Image.open(file_stream)
            image.verify()  # Validate image integrity

            # Re-open because verify() closes or invalidates the stream
            file_stream.seek(0)
            image = Image.open(file_stream)

            # Auto-orient based on EXIF before stripping metadata
            image = ImageOps.exif_transpose(image) or image

            # Convert to RGB (or RGBA if transparent)
            if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
                sanitized_image = Image.new("RGBA", image.size)
                sanitized_image.paste(image, (0, 0))
            else:
                sanitized_image = Image.new("RGB", image.size)
                sanitized_image.paste(image, (0, 0))

            # Resize if dimensions exceed 1200x1200 to optimize storage while maintaining high resolution
            sanitized_image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)

            # Pseudonymization: Pure random UUIDv4
            file_uuid = uuid.uuid4()
            filename = f"{file_uuid}.webp"
            relative_path = f"tmp/avatars/{filename}"
            target_path = self.tmp_dir / "avatars" / filename

            # Save as optimized WebP without any EXIF or metadata
            output_buffer = io.BytesIO()
            sanitized_image.save(
                output_buffer,
                format="WEBP",
                quality=85,
                method=6,
                optimize=True,
            )

            with open(target_path, "wb") as f:
                f.write(output_buffer.getvalue())

            return relative_path

        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Format citra tidak valid atau rusak: {e!s}",
            ) from e

    async def save_upload_avatar(self, upload_file: UploadFile) -> str:
        """Process and save an uploaded avatar UploadFile."""
        if upload_file.content_type and upload_file.content_type.lower() not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tipe file tidak didukung. Harap unggah file citra (JPEG, PNG, atau WebP).",
            )

        return self.process_and_save_avatar(upload_file.file, upload_file.content_type)

    def get_avatar_full_path(self, filename: str) -> Path | None:
        """Resolve full filesystem path for a given avatar filename safely against path traversal."""
        # Sanitize filename
        safe_filename = Path(filename).name
        file_path = (self.avatars_dir / safe_filename).resolve()

        # Prevent Path Traversal: ensure target file is strictly inside avatars directory
        try:
            file_path.relative_to(self.avatars_dir.resolve())
        except ValueError:
            return None

        if file_path.exists() and file_path.is_file():
            return file_path
        return None

    def delete_avatar(self, relative_or_filename: str | None) -> bool:
        """
        Hard delete (Right to Erasure) physical avatar file from storage.
        Accepts 'avatars/uuid.webp' or 'uuid.webp' or full path.
        """
        if not relative_or_filename:
            return False

        # If it's an external URL, do not unlink
        if relative_or_filename.startswith(("http://", "https://")):
            return False

        filename = Path(relative_or_filename).name
        file_path = self.get_avatar_full_path(filename)

        if file_path and file_path.exists():
            try:
                file_path.unlink()
                return True
            except OSError:
                return False
        return False

    def process_and_save_cv(self, file_stream: BinaryIO, content_type: str | None = None) -> str:
        """
        Validate, sanitize, and stage candidate CV PDF securely.
        Returns the staged relative path: 'tmp/cvs/<uuid4>.pdf' (see promote_upload).
        """
        file_stream.seek(0, os.SEEK_END)
        size = file_stream.tell()
        file_stream.seek(0)

        if size > MAX_CV_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ukuran berkas CV terlalu besar ({size / 1024 / 1024:.2f}MB). Maksimal 5MB.",
            )

        if size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Berkas CV tidak boleh kosong.",
            )

        # Magic Bytes Validation for PDF
        header = file_stream.read(16)
        file_stream.seek(0)
        validate_pdf_magic_bytes(header)

        file_uuid = uuid.uuid4()
        filename = f"{file_uuid}.pdf"
        relative_path = f"tmp/cvs/{filename}"
        target_path = self.tmp_dir / "cvs" / filename

        with open(target_path, "wb") as f:
            while chunk := file_stream.read(65536):
                f.write(chunk)

        return relative_path

    async def save_upload_cv(self, upload_file: UploadFile) -> str:
        """Process and save an uploaded CV PDF UploadFile."""
        ct = (upload_file.content_type or "").lower()
        fn = (upload_file.filename or "").lower()
        if ct not in ("application/pdf", "application/x-pdf") and not fn.endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format berkas CV harus berupa dokumen PDF (.pdf).",
            )
        return self.process_and_save_cv(upload_file.file, upload_file.content_type)

    def get_cv_full_path(self, filename: str) -> Path | None:
        """Resolve full filesystem path for a given CV filename safely against path traversal."""
        safe_filename = Path(filename).name
        file_path = (self.cvs_dir / safe_filename).resolve()

        try:
            file_path.relative_to(self.cvs_dir.resolve())
        except ValueError:
            return None

        if file_path.exists() and file_path.is_file():
            return file_path
        return None

    def delete_cv(self, relative_or_filename: str | None) -> bool:
        """
        Hard delete (Right to Erasure) physical CV file from storage.
        Accepts 'cvs/uuid.pdf' or 'uuid.pdf' or full path.
        """
        if not relative_or_filename:
            return False

        if relative_or_filename.startswith(("http://", "https://")):
            return False

        filename = Path(relative_or_filename).name
        file_path = self.get_cv_full_path(filename)

        if file_path and file_path.exists():
            try:
                file_path.unlink()
                return True
            except OSError:
                return False
        return False

    def get_staged_full_path(self, kind: UploadKind, filename: str) -> Path | None:
        """Resolve a staged (not yet saved) upload for preview, safe against path traversal."""
        safe_filename = Path(filename).name
        if not STAGED_PATH_RE.match(f"tmp/{kind}/{safe_filename}"):
            return None
        file_path = self.tmp_dir / kind / safe_filename
        return file_path if file_path.is_file() else None

    def promote_upload(self, staged_path: str, kind: UploadKind) -> str:
        """
        Move a staged upload (tmp/<kind>/<uuid>.<ext>) into permanent storage.
        Returns the permanent relative path '<kind>/<uuid>.<ext>'.
        Only server-issued staged paths are accepted, so clients can never point
        a record at an arbitrary (or someone else's) stored file.
        """
        match = STAGED_PATH_RE.match(staged_path or "")
        if not match or match.group(1) != kind or match.group(3) != KIND_EXTENSIONS[kind]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referensi berkas unggahan tidak valid. Silakan unggah ulang berkas.",
            )

        filename = f"{match.group(2)}.{match.group(3)}"
        source = self.tmp_dir / kind / filename
        if not source.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Berkas unggahan sudah kedaluwarsa atau tidak ditemukan. Silakan unggah ulang berkas.",
            )

        os.replace(source, self.base_dir / kind / filename)
        return f"{kind}/{filename}"

    def unpromote_upload(self, final_path: str | None) -> None:
        """Move a promoted file back to staging (rollback when the DB write fails, so the user can retry)."""
        if not final_path:
            return
        kind, _, filename = final_path.partition("/")
        if kind not in KIND_EXTENSIONS or not STAGED_PATH_RE.match(f"tmp/{kind}/{filename}"):
            return
        source = self.base_dir / kind / filename
        if source.is_file():
            os.replace(source, self.tmp_dir / kind / filename)

    def commit_upload_field(
        self,
        value: str | None,
        kind: UploadKind,
        keep_values: set[str | None] | None = None,
        allow_external: bool = False,
    ) -> tuple[str | None, str | None]:
        """
        Resolve a client-submitted file field into the value to store.
        Returns (value_to_store, newly_promoted_path_or_None).
        - empty            -> None (clears the field)
        - in keep_values   -> unchanged (file already stored on the record)
        - http(s) URL      -> as-is when allow_external (e.g. generated avatars)
        - tmp/<kind>/...   -> promoted into permanent storage
        Anything else is rejected.
        """
        if not value:
            return None, None
        if keep_values and value in keep_values:
            return value, None
        if allow_external and value.startswith(("http://", "https://")):
            return value, None
        promoted = self.promote_upload(value, kind)
        return promoted, promoted

    def delete_upload(self, relative_path: str | None) -> bool:
        """Delete a stored avatar or CV by its relative path."""
        if not relative_path:
            return False
        if relative_path.startswith("cvs/"):
            return self.delete_cv(relative_path)
        if relative_path.startswith("avatars/"):
            return self.delete_avatar(relative_path)
        return False

    def purge_stale_staged(self, max_age_seconds: float) -> int:
        """Delete staged uploads that were never saved into a record. Returns number of files removed."""
        cutoff = time.time() - max_age_seconds
        removed = 0
        for kind in KIND_EXTENSIONS:
            for file_path in (self.tmp_dir / kind).iterdir():
                try:
                    if file_path.is_file() and file_path.stat().st_mtime < cutoff:
                        file_path.unlink()
                        removed += 1
                except OSError as e:
                    logger.warning("Failed to purge staged upload %s: %s", file_path.name, e)
        return removed


async def is_upload_referenced(session: AsyncSession, relative_path: str) -> bool:
    """Check whether any record still points at a stored file (files can be shared, e.g. registration photo -> member avatar)."""
    stmt = text(
        """
        SELECT EXISTS (SELECT 1 FROM registrations WHERE photo = :p OR cv_url = :p)
            OR EXISTS (SELECT 1 FROM members WHERE avatar = :p)
            OR EXISTS (SELECT 1 FROM users WHERE avatar = :p)
        """
    )
    result = await session.execute(stmt, {"p": relative_path})
    return bool(result.scalar())


async def release_upload(session: AsyncSession, relative_path: str | None) -> bool:
    """Delete a stored file once no record references it anymore. Call after the DB change is committed."""
    if not relative_path or relative_path.startswith(("http://", "https://")):
        return False
    if await is_upload_referenced(session, relative_path):
        return False
    return StorageService().delete_upload(relative_path)
