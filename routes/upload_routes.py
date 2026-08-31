from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from services.storage_service import StorageService
from utils.auth_deps import get_current_user, require_roles
from utils.rate_limiter import rate_limit

router = APIRouter(prefix="/uploads", tags=["File Storage & Uploads (UU PDP / GDPR Compliant)"])
storage_service = StorageService()


@router.post(
    "/avatar",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="upload_avatar"))],
)
async def upload_avatar(
    file: UploadFile = File(...),
):
    """
    Public / Authenticated endpoint to upload avatar / candidate photo.
    - Validates file size (max 2MB), MIME type, and Magic Bytes.
    - Strips all EXIF metadata (UU PDP / GDPR privacy compliance).
    - Converts & compresses to optimized WebP.
    - Pseudonymizes filename with UUIDv4.
    - Rate limited to 10 uploads / minute per IP.
    """
    relative_path = await storage_service.save_upload_avatar(file)
    filename = Path(relative_path).name

    return {
        "filename": filename,
        "path": relative_path,
        "url": f"/orion/api/v1/uploads/avatars/{filename}",
        "message": "Citra berhasil divalidasi (magic bytes), dibersihkan dari metadata EXIF, dan disimpan dalam format WebP teroptimasi.",
    }


@router.get("/avatars/{filename}")
async def serve_avatar(filename: str):
    """
    Serve sanitized avatar image for <img src="..." /> rendering.
    Safe against directory traversal.
    """
    file_path = storage_service.get_avatar_full_path(filename)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File citra tidak ditemukan atau telah dihapus.",
        )

    return FileResponse(
        path=str(file_path),
        media_type="image/webp",
        headers={
            "Cache-Control": "public, max-age=86400, stale-while-revalidate=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.delete("/avatars/{filename}")
async def delete_avatar(
    filename: str,
    current_user: dict = Depends(require_roles("SUPERADMIN", "ADMIN_BPH")),
):
    """
    Hard delete avatar file from storage (Right to Erasure / Hak untuk Dihapus).
    Requires authenticated user with role SUPERADMIN or ADMIN_BPH.
    """
    deleted = storage_service.delete_avatar(filename)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File citra tidak ditemukan di storage fisik.",
        )

    return {
        "status": "success",
        "message": f"File {filename} telah dihapus permanen dari storage fisik sesuai prinsip Right to Erasure.",
    }
