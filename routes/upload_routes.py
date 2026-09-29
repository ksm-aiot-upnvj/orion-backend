from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from config.config import settings
from services.storage_service import StorageService
from utils.auth_deps import require_roles
from utils.rate_limiter import rate_limit

router = APIRouter(prefix="/uploads", tags=["File Storage & Uploads"])
storage_service = StorageService()


@router.post(
    "/avatars",
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
    The file is only staged (tmp/avatars/...). It becomes permanent when the returned
    `path` is submitted with the owning form; unsaved uploads are purged automatically.
    """
    relative_path = await storage_service.save_upload_avatar(file)
    filename = Path(relative_path).name

    return {
        "filename": filename,
        "path": relative_path,
        "url": f"{settings.API_V1_STR.rstrip('/')}/uploads/tmp/avatars/{filename}",
        "message": "Foto berhasil diunggah dan diproses.",
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
            detail="File foto tidak ditemukan atau telah dihapus.",
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


@router.get("/tmp/avatars/{filename}")  # nosec B108 - URL path, not a filesystem path
async def serve_staged_avatar(filename: str):
    """Serve a staged (not yet saved) avatar so the form can preview it."""
    file_path = storage_service.get_staged_full_path("avatars", filename)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File foto sementara tidak ditemukan atau sudah kedaluwarsa.",
        )

    return FileResponse(
        path=str(file_path),
        media_type="image/webp",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.get("/tmp/cvs/{filename}")  # nosec B108 - URL path, not a filesystem path
async def serve_staged_cv(filename: str):
    """Serve a staged (not yet saved) CV so the form can preview it."""
    file_path = storage_service.get_staged_full_path("cvs", filename)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas CV sementara tidak ditemukan atau sudah kedaluwarsa.",
        )

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={Path(filename).name}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
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
            detail="File foto tidak ditemukan di storage fisik.",
        )

    return {
        "status": "success",
        "message": f"File {filename} telah dihapus permanen dari storage fisik sesuai prinsip Right to Erasure.",
    }


@router.post(
    "/cvs",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="upload_cv"))],
)
async def upload_cv(
    file: UploadFile = File(...),
):
    """
    Public / Authenticated endpoint to upload candidate CV PDF file.
    - Validates file size (max 5MB), MIME type, and Magic Bytes (%PDF-).
    - Pseudonymizes filename with UUIDv4.
    - Rate limited to 10 uploads / minute per IP.
    Staged like avatars: permanent only after the registration form is submitted.
    """
    relative_path = await storage_service.save_upload_cv(file)
    filename = Path(relative_path).name

    return {
        "filename": filename,
        "path": relative_path,
        "url": f"{settings.API_V1_STR.rstrip('/')}/uploads/tmp/cvs/{filename}",
        "message": "Berkas CV berhasil diunggah dan diproses.",
    }


@router.get("/cvs/{filename}")
async def serve_cv(filename: str):
    """
    Serve sanitized CV PDF document for preview / inline browser view.
    Safe against directory traversal.
    """
    file_path = storage_service.get_cv_full_path(filename)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas CV tidak ditemukan atau telah dihapus.",
        )

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={Path(filename).name}",
            # CVs are personal data: never store them in shared caches/CDNs, never index them
            "Cache-Control": "private, no-store",
            "X-Robots-Tag": "noindex, nofollow",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/cvs/{filename}")
async def delete_cv(
    filename: str,
    current_user: dict = Depends(require_roles("SUPERADMIN", "ADMIN_BPH")),
):
    """
    Hard delete CV file from storage (Right to Erasure / Hak untuk Dihapus).
    Requires authenticated user with role SUPERADMIN or ADMIN_BPH.
    """
    deleted = storage_service.delete_cv(filename)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas CV tidak ditemukan di storage fisik.",
        )

    return {
        "status": "success",
        "message": f"Berkas CV {filename} telah dihapus permanen dari server.",
    }
