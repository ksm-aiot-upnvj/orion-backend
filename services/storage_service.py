import io
import os
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps

from config.config import settings

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB per UU PDP / GDPR guideline


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


class StorageService:
    def __init__(self, base_upload_dir: str | None = None):
        self.base_dir = Path(base_upload_dir or settings.UPLOAD_DIR).resolve()
        self.avatars_dir = self.base_dir / "avatars"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create storage directories if they do not exist."""
        self.avatars_dir.mkdir(parents=True, exist_ok=True)

    def process_and_save_avatar(self, file_stream: BinaryIO, content_type: str | None = None) -> str:
        """
        Process, sanitize, strip EXIF metadata, convert to WebP, and save image securely.
        Returns the relative path: 'avatars/<uuid4>.webp'
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
            relative_path = f"avatars/{filename}"
            target_path = self.avatars_dir / filename

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
