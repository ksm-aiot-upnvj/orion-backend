import functools
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from services.auth_service import AuthService
from utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/orion/api/v1/auth/login", auto_error=False)


# Standard Role Constants for ORION
class SystemRole:
    SUPERADMIN = "SUPERADMIN"       # Ketua Umum, Lead Developer, Server Admin
    ADMIN_BPH = "ADMIN_BPH"         # Badan Pengurus Harian (Ketua, Wakil, Sekretaris, Bendahara)
    KADIV = "KADIV"                 # Kepala Divisi (Riset, PSDM, Humas, dll.)
    PENGURUS = "PENGURUS"           # Seluruh Pengurus Aktif KSM
    MEMBER = "MEMBER"               # Anggota Biasa / Calon


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Validate JWT Bearer Token and return authenticated user dictionary from database.
    Enforces active user account check.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autentikasi diperlukan. Silakan login terlebih dahulu.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token autentikasi tidak valid atau telah kedaluwarsa.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Data sesi tidak lengkap.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format UUID user tidak valid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pengguna tidak ditemukan atau akun telah dinonaktifkan.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> dict | None:
    """Optional authentication for endpoints that support both anonymous and logged-in users."""
    if not token:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None


async def require_pengurus(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Enforce that authenticated user is an active Pengurus / BPH / Superadmin.
    Anggota Umum (role == 'Anggota') is completely denied access (HTTP 403 Forbidden).
    """
    if current_user.get("is_superadmin") or (current_user.get("role") or "").upper() == "SUPERADMIN":
        return current_user

    role = (current_user.get("role") or "").strip()
    if role.lower() == "anggota" or not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses Ditolak: Modul ini hanya dapat diakses oleh Pengurus KSM AIoT.",
        )
    return current_user


async def can_manage_selection(current_user: dict = Depends(require_pengurus)) -> dict:
    """
    Write authorization for Candidate Selection (Intake config, Approve, Reject, Delete).
    Allowed: Superadmin, Ketua, Wakil Ketua, or PSDM Division.
    Humas Multimedia (PDD) and other divisions are Read-Only (HTTP 403).
    """
    if current_user.get("is_superadmin") or (current_user.get("role") or "").upper() == "SUPERADMIN":
        return current_user

    role = (current_user.get("role") or "").strip()
    division = (current_user.get("division") or "").strip()

    if role in ("Ketua", "Wakil Ketua") or division == "PSDM":
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Akses Ditolak: Modifikasi seleksi hanya diizinkan untuk Divisi PSDM, Ketua, atau Wakil Ketua. Hak akses Anda: Read-Only.",
    )


async def can_manage_members(current_user: dict = Depends(require_pengurus)) -> dict:
    """
    Write authorization for Member directory (Create, Update, Delete, Import Excel, Anonymize).
    Allowed: Superadmin, Ketua, Wakil Ketua, or PSDM Division.
    """
    if current_user.get("is_superadmin") or (current_user.get("role") or "").upper() == "SUPERADMIN":
        return current_user

    role = (current_user.get("role") or "").strip()
    division = (current_user.get("division") or "").strip()

    if role in ("Ketua", "Wakil Ketua") or division == "PSDM":
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Akses Ditolak: Pengelolaan anggota hanya diizinkan untuk Divisi PSDM, Ketua, atau Wakil Ketua. Hak akses Anda: Read-Only.",
    )


async def can_manage_inventory(current_user: dict = Depends(require_pengurus)) -> dict:
    """
    Write authorization for Hardware Inventory.
    Allowed: Superadmin, Ketua, Wakil Ketua, or Akademik Riset Division.
    """
    if current_user.get("is_superadmin") or (current_user.get("role") or "").upper() == "SUPERADMIN":
        return current_user

    role = (current_user.get("role") or "").strip()
    division = (current_user.get("division") or "").strip()

    if role in ("Ketua", "Wakil Ketua") or division == "Akademik Riset":
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Akses Ditolak: Pengelolaan inventaris hanya diizinkan untuk Divisi Akademik & Riset, Ketua, atau Wakil Ketua. Hak akses Anda: Read-Only.",
    )


async def can_manage_finance(current_user: dict = Depends(require_pengurus)) -> dict:
    """
    Write authorization for Kas & Keuangan.
    Allowed: Superadmin, Ketua, Wakil Ketua, or Bendahara.
    """
    if current_user.get("is_superadmin") or (current_user.get("role") or "").upper() == "SUPERADMIN":
        return current_user

    role = (current_user.get("role") or "").strip()

    if role in ("Ketua", "Wakil Ketua", "Bendahara"):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Akses Ditolak: Pengelolaan kas keuangan hanya diizinkan untuk Bendahara, Ketua, atau Wakil Ketua. Hak akses Anda: Read-Only.",
    )


async def can_manage_archive(current_user: dict = Depends(require_pengurus)) -> dict:
    """
    Write authorization for Arsip & Surat Resmi.
    Allowed: Superadmin, Ketua, Wakil Ketua, or Sekretaris.
    """
    if current_user.get("is_superadmin") or (current_user.get("role") or "").upper() == "SUPERADMIN":
        return current_user

    role = (current_user.get("role") or "").strip()

    if role in ("Ketua", "Wakil Ketua", "Sekretaris"):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Akses Ditolak: Pengelolaan arsip surat hanya diizinkan untuk Sekretaris, Ketua, atau Wakil Ketua. Hak akses Anda: Read-Only.",
    )


def require_roles(*allowed_roles: str) -> Callable:
    """
    Backend-Enforced RBAC Dependency with support for Member roles and System roles.
    """
    normalized_roles = {r.upper() for r in allowed_roles}

    async def role_checker(current_user: dict = Depends(require_pengurus)) -> dict:
        user_role = (current_user.get("role") or "").upper()
        is_super = current_user.get("is_superadmin") or user_role == SystemRole.SUPERADMIN

        if is_super or user_role in normalized_roles:
            return current_user

        # Support BPH alias (Ketua, Wakil, Sekretaris, Bendahara)
        if "ADMIN_BPH" in normalized_roles and (user_role in ("KETUA", "WAKIL KETUA", "SEKRETARIS", "BENDAHARA") or (current_user.get("division") or "").upper() == "BPH"):
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Akses ditolak: Operasi ini membutuhkan role {', '.join(allowed_roles)}. Role Anda: '{user_role}'.",
        )

    return role_checker


def verify_resource_owner(
    current_user: dict,
    resource_owner_id: str | uuid.UUID,
    allowed_admin_roles: list[str] | None = None
) -> bool:
    """
    Anti-BOLA / Anti-IDOR Authorization Helper (UU PDP & OWASP ASVS V4.1).
    Validates whether current authenticated user owns the resource or has sufficient administrative role.
    
    Usage:
        verify_resource_owner(current_user, target_user_id, allowed_admin_roles=["SUPERADMIN", "ADMIN_BPH"])
    """
    if allowed_admin_roles is None:
        allowed_admin_roles = [SystemRole.SUPERADMIN, SystemRole.ADMIN_BPH]

    user_id_str = str(current_user.get("id"))
    target_id_str = str(resource_owner_id)

    # 1. Ownership match
    if user_id_str == target_id_str:
        return True

    # 2. Administrative privilege bypass
    user_role = (current_user.get("role") or "").upper()
    admin_roles_normalized = {r.upper() for r in allowed_admin_roles}
    if user_role in admin_roles_normalized:
        return True

    # 3. Access denied
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Akses ditolak: Anda tidak memiliki izin untuk mengakses atau memodifikasi sumber daya pengguna lain (Anti-IDOR).",
    )


def require_role(role_name: str):
    """
    Decorator alternative for RBAC authorization enforcement on route handlers.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any):
            # Inspect kwargs for current_user
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Autentikasi diperlukan sebelum mengevaluasi role.",
                )
            user_role = (current_user.get("role") or "").upper()
            if user_role != SystemRole.SUPERADMIN and user_role != role_name.upper():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Akses ditolak: Membutuhkan role '{role_name}'.",
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator
