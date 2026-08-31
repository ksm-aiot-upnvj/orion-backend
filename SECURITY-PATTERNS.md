# ORION — Backend Security Patterns & Developer Guide
**KSM AIoT — Organizational Resource & Integrated Operations Network**  
*Standar: UU Pelindungan Data Pribadi No. 27/2022, GDPR, OWASP Top 10 & ASVS 4.0*

Dokumen ini merupakan panduan teknis wajib bagi seluruh pengembang backend ORION (termasuk pengembang penerus modul Inventaris, Kas & Keuangan, serta Arsip Surat).

---

## 1. Backend-Enforced RBAC (Role-Based Access Control)

Seluruh otorisasi **WAJIB** ditegakkan di layer backend melalui dependency `require_roles` pada `utils/auth_deps.py`.

### Hierarki & Definisi Role Sistem (`SystemRole`)
- `SUPERADMIN`: Ketua Umum, Lead Developer, System Administrator (memiliki akses global).
- `ADMIN_BPH`: Badan Pengurus Harian (Ketua, Wakil Ketua, Sekretaris, Bendahara).
- `KADIV`: Kepala Divisi (Akademik Riset, PSDM, Humas Multimedia).
- `PENGURUS`: Seluruh staf dan pengurus aktif KSM.
- `MEMBER`: Anggota biasa / calon anggota.

### Contoh Penerapan pada Endpoint FastAPI

```python
from fastapi import APIRouter, Depends
from utils.auth_deps import require_roles, SystemRole

router = APIRouter(prefix="/finance", tags=["Kas & Keuangan"])

# Endpoint yang hanya boleh diakses Bendahara / BPH / Superadmin
@router.post("/transactions")
async def create_transaction(
    payload: TransactionCreate,
    current_user: dict = Depends(require_roles(SystemRole.ADMIN_BPH, SystemRole.SUPERADMIN))
):
    # current_user terjamin sudah terverifikasi dan memiliki role yang diizinkan
    ...
```

---

## 2. Pola Anti-BOLA / Anti-IDOR (Broken Object Level Authorization)

Gunakan helper `verify_resource_owner()` untuk memvalidasi kepemilikan data sebelum manipulasi:

```python
from fastapi import APIRouter, Depends, HTTPException
from utils.auth_deps import get_current_user, verify_resource_owner, SystemRole

@router.put("/reimbursements/{reimbursement_id}")
async def update_reimbursement(
    reimbursement_id: str,
    payload: ReimbursementUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    reimbursement = await get_reimbursement_by_id(db, reimbursement_id)
    if not reimbursement:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")

    # Validasi kepemilikan: Hanya pemohon asli atau BPH/Superadmin yang boleh mengedit
    verify_resource_owner(
        current_user=current_user,
        resource_owner_id=reimbursement["requester_user_id"],
        allowed_admin_roles=[SystemRole.SUPERADMIN, SystemRole.ADMIN_BPH]
    )
```

---

## 3. Format Penulisan Audit Log (Append-Only)

Tabel `audit_logs` digunakan bersama oleh seluruh modul ORION. Setiap aksi perubahan data penting wajib dicatat:

```python
from services.audit_log_service import log_audit_event

await log_audit_event(
    session=db,
    action="FINANCE_TRANSACTION_CREATED",
    resource_type="FINANCE",
    resource_id=str(new_transaction["id"]),
    actor_id=current_user["id"],
    actor_name=current_user["full_name"],
    actor_role=current_user["role"],
    ip_address=client_ip,
    details={
        "amount": payload.amount,
        "type": "EXPENSE",
        "category": "Komponen IoT ESP32"
    }
)
```

---

## 4. Konvensi File Upload & Storage

1. **Magic Bytes Validation**: Panggil `validate_image_magic_bytes()` di `services/storage_service.py` untuk memeriksa byte header file asli (JPEG, PNG, WebP).
2. **Pembersihan Metadata**: EXIF (GPS, serial perangkat) dibersihkan secara otomatis.
3. **Format Standar**: Disimpan dalam WebP (maksimal resolusi 1200x1200, kualitas 85%).
4. **Pseudonimisasi**: Nama file digenerate ulang sebagai UUIDv4 murni (`<uuid4>.webp`).
5. **Storage Terisolasi**: File disimpan di luar web root publik (`uploads/`) dan diakses melalui endpoint controller terproteksi.

---

## 5. Rate Limiting Middleware

Gunakan dependency `rate_limit` pada endpoint publik atau yang sensitif terhadap brute force:

```python
from utils.rate_limiter import rate_limit

@router.post("/export-excel", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, scope="finance_export"))])
async def export_excel(...):
    ...
```

---

## 6. Checklist Keamanan "Sebelum Submit PR" (8 Poin Wajib)

- [ ] **1. RBAC Enforced**: Endpoint privat dilindungi `require_roles(...)` atau `get_current_user`.
- [ ] **2. Anti-IDOR Validated**: Validasi kepemilikan data menggunakan `verify_resource_owner()`.
- [ ] **3. Parameterized Query**: Tidak ada interpolasi string SQL mentah.
- [ ] **4. Audit Log Recorded**: Memanggil `log_audit_event(...)` untuk aksi penting.
- [ ] **5. Sanitasi Input**: Teks bebas disanitasi dengan `sanitize_text` / Pydantic validator.
- [ ] **6. Upload Validation**: Validasi ukuran (maks 2MB), MIME type, dan magic bytes.
- [ ] **7. Tidak Ada Secrets**: File `.env`, password, token tidak tercatat di commit Git.
- [ ] **8. Automated Tests Pass**: Seluruh pengujian lolos via `uv run pytest tests`.
