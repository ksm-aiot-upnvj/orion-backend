# API — Kontrak REST API ORION

| Atribut | Nilai |
|---|---|
| Versi dokumen | 1.0 (API v1) |
| Tanggal | 29 September 2026 |
| Penulis | Tim Pengembang ORION (disusun dengan bantuan asisten AI) |
| Spesifikasi mesin | [openapi.yaml](openapi.yaml) — OpenAPI 3.1, divalidasi `openapi-spec-validator` & `@redocly/cli lint` (0 error) |
| Dokumentasi interaktif | `GET /orion/api/v1/docs` (Swagger UI bawaan FastAPI) |

Dokumen terkait: [SKPL §7](SKPL.md#7-kontrak-api-ringkas) · [FSD](FSD.md) · [SCHEMA](SCHEMA.md) · [WORKFLOW](WORKFLOW.md) · [ARCHITECTURE](ARCHITECTURE.md)

## Daftar Isi

1. [Ringkasan dan status](#1-ringkasan-dan-status)
2. [Konvensi umum](#2-konvensi-umum)
3. [Autentikasi dan otorisasi](#3-autentikasi-dan-otorisasi)
4. [Format error standar](#4-format-error-standar)
5. [Paginasi, filter, sorting, idempotensi, rate limit](#5-paginasi-filter-sorting-idempotensi-rate-limit)
6. [Katalog endpoint](#6-katalog-endpoint)
7. [Kontrak webhook pembayaran](#7-kontrak-webhook-pembayaran-perlu-diskusi)
8. [Aturan validasi field](#8-aturan-validasi-field)
9. [Redirect URL lama](#9-redirect-url-lama)
10. [Riwayat revisi](#10-riwayat-revisi)

---

## 1. Ringkasan dan status

| Status | Operasi | Keterangan |
|---|---|---|
| [ADA-BACKEND] | 40 | Dihasilkan dari `app.openapi()` FastAPI; setiap operasi memuat `x-orion-source` (path:baris handler) |
| [USULAN] | 56 | Inventaris, Keuangan (Opsi A), Laporan, Arsip — rancangan |
| [PERLU-DISKUSI] | 10 | QRIS, pengingat, webhook, transisi approval penuh, verifikasi QR, label QR aset |

Setiap operasi di `openapi.yaml` memiliki ekstensi `x-orion-status`, `x-orion-requirements` (ID FR di [SKPL](SKPL.md)), dan `x-orion-roles`. Operasi [ADA-BACKEND] **tidak boleh** diedit manual di YAML — regenerasi dengan skrip pembangun bila route berubah (lihat [README](../README.md#dokumentasi)).

## 2. Konvensi umum

| Aspek | Konvensi | Status |
|---|---|---|
| Basis URL | `https://<host>/orion/api/v1` (prefix dari `API_V1_STR`); path juga dapat diakses tanpa prefix melalui middleware | [ADA-BACKEND] `main.py:107-117` |
| Versi | Versi mayor di path (`/api/v1`); perubahan tak kompatibel → `/api/v2`, v1 dipertahankan ≥ 1 semester | [ADA-BACKEND] (v1) / [USULAN] (kebijakan) |
| Gaya URL | kebab-case, resource jamak, tanpa trailing slash, aksi non-CRUD sebagai sub-resource kata kerja (`/approve`, `/anonymize`) | [ADA-BACKEND] |
| Format | JSON UTF-8; unggah file `multipart/form-data`; unduh PDF/gambar biner | [ADA-BACKEND] |
| Nama field | `snake_case` | [ADA-BACKEND] |
| Identifier | UUIDv7; beberapa resource menerima identifier alternatif (`{identifier}` = UUID, Member ID, atau NIM) | [ADA-BACKEND] |
| Waktu | ISO 8601 dengan zona; server mengembalikan UTC (`2026-09-29T12:57:40.949317Z`); klien menampilkan Asia/Jakarta (WIB); tanggal murni `YYYY-MM-DD` | [ADA-BACKEND], kecuali `submit_date`/`join_date` berformat `dd/mm/YYYY` (IC-14) |
| Uang | Integer rupiah (tanpa desimal), field `amount` | [USULAN] |
| Enum | Nilai persis seperti di DB (`"S1 Informatika"`, `"Pending"`, `"Aktif"`) | [ADA-BACKEND] |
| Teks | Server meng-HTML-escape input teks sebelum simpan; klien menampilkan apa adanya | [ADA-BACKEND] |
| Header keamanan | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Content-Security-Policy` | [ADA-BACKEND] `main.py:84-103` |
| CORS | Origin dari `CORS_ORIGINS` (+ regex opsional); header `Authorization`, `Content-Type` | [ADA-BACKEND] |

## 3. Autentikasi dan otorisasi

```http
POST /orion/api/v1/auth/login
Content-Type: application/json

{"student_id": "<NIM atau email>", "password": "<password>"}
```

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": "01a0ed07-4027-724b-b3ef-aec6290c957f",
    "member_id": null,
    "student_id": "2099999999",
    "full_name": "Test Superadmin",
    "email": "superadmin@test.local",
    "role": "SUPERADMIN",
    "division": "BPH",
    "avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=admin",
    "is_superadmin": true,
    "is_active": true
  }
}
```

- Kirim `Authorization: Bearer <access_token>` pada endpoint berlabel *Bearer*.
- Access token berlaku 30 menit (`type=access`); perpanjang dengan `POST /auth/refresh` `{"refresh_token": "..."}` — respons berisi pasangan token baru (rotasi). Refresh token **tidak** diterima sebagai bearer.
- Peran & dependency:

| Dependency | Diizinkan |
|---|---|
| `require_pengurus` | Superadmin; role Ketua, Wakil Ketua, Sekretaris, Bendahara, Kepala Divisi, Staff, PENGURUS, KADIV, ADMIN_BPH |
| `can_manage_selection`, `can_manage_members` | Superadmin, Ketua, Wakil Ketua, divisi PSDM |
| `require_roles(SUPERADMIN, ADMIN_BPH)` | Superadmin; Ketua/Wakil/Sekretaris/Bendahara atau divisi BPH |
| `can_manage_inventory` [helper siap] | Superadmin, Ketua, Wakil Ketua, divisi Akademik Riset |
| `can_manage_finance` [helper siap] | Superadmin, Ketua, Wakil Ketua, Bendahara |
| `can_manage_archive` [helper siap] | Superadmin, Ketua, Wakil Ketua, Sekretaris |

Matriks per layar: [FSD §3](FSD.md#3-matriks-rbac).

## 4. Format error standar

**Saat ini [ADA-BACKEND]** (`main.py:136-176`):

| Situasi | Kode | Bentuk body |
|---|---|---|
| Error bisnis (`HTTPException`) | 400/401/403/404/409/413/429/503 | `{"detail": "<pesan Bahasa Indonesia>"}` |
| Validasi request | 422 | `{"detail": [<error Pydantic>], "message": "Format data permintaan tidak valid."}` |
| Error database | 500 | `{"detail": "Terjadi kesalahan operasi database internal.", "error_code": "DB_ERROR"}` |
| Error tak tertangani | 500 | `{"detail": "Terjadi kesalahan internal pada server. ...", "error_code": "INTERNAL_SERVER_ERROR"}` |

Contoh nyata:

```json
// 401 POST /auth/login
{"detail": "NIM / Email atau Password salah. Silakan coba lagi."}

// 400 POST /registrations (NIM ganda)
{"detail": "NIM 2610511777 sudah terdaftar dalam sistem seleksi!"}

// 422 POST /registrations (portfolio_url berskema javascript:)
{
  "detail": [{"type": "value_error", "loc": ["body", "portfolio_url"],
              "msg": "Value error, Tautan harus berupa URL http:// atau https://.",
              "input": "javascript:alert(1)", "ctx": {"error": {}}}],
  "message": "Format data permintaan tidak valid."
}

// 429 (rate limit) — juga header Retry-After
{"detail": "Terlalu banyak permintaan untuk endpoint ini. Batas: 5 per 60 detik. Coba lagi dalam 42 detik."}
```

**Usulan [USULAN]** — tambahkan tanpa mematahkan klien (field `detail` tetap):

```json
{"detail": "Stok tidak mencukupi", "error_code": "INVENTORY_STOCK_INSUFFICIENT", "request_id": "01J9Z...", "fields": null}
```

`error_code` stabil (UPPER_SNAKE) untuk logika klien; `request_id` sama dengan header `X-Request-ID` dan log server (NFR-OBS-01).

## 5. Paginasi, filter, sorting, idempotensi, rate limit

| Aspek | Saat ini | Usulan |
|---|---|---|
| Paginasi | Hanya `GET /audit-logs` (`limit` 1–200, default 100; `offset` ≥ 0) → `{items, total, stats}` | Semua daftar: `limit` (default 50, maks 200), `offset`, respons `{items, total, limit, offset}`; `/members` & `/registrations` saat ini mengembalikan array penuh — tambahkan paginasi dengan mempertahankan bentuk array bila parameter tidak dikirim (kompatibel) |
| Filter | `/members?division=&intake_period=&status=`; `/registrations?status=` | Query param per field + `q` teks bebas; rentang tanggal `from`/`to` (inklusif, WIB) |
| Sorting | Tetap (`created_at`) | `sort=field` atau `sort=-field` (menurun), allow-list per resource |
| Idempotensi | Approve registrasi idempoten bila sudah Accepted | Header `Idempotency-Key` pada POST keuangan/peminjaman/pembayaran; kunci + hash body disimpan 24 jam; kunci sama → respons pertama; body berbeda → 409 |
| Rate limit | Login 5/menit, refresh 30/menit, pendaftaran 10/menit, unggah foto/CV 10/menit per IP → 429 + `Retry-After` | Pindah ke Redis bila > 1 worker |

## 6. Katalog endpoint

Basis semua path: `/orion/api/v1`. Skema request/response lengkap ada di [openapi.yaml](openapi.yaml) (`components.schemas`).

### 6.1 Endpoint [ADA-BACKEND] (40 operasi)

Kolom *Kode* = lokasi handler di `orion-backend/`. `*` = parameter wajib. Kode status = seluruh respons terdokumentasi.


#### Authentication

| Method | Path | Ringkasan | Auth / Peran | Parameter | Request | Response sukses | Kode status | Rate limit | Kebutuhan | Kode |
|---|---|---|---|---|---|---|---|---|---|---|
| POST | `/auth/login` | Login | Publik: Publik | — | `LoginRequest` | 200 `LoginResponse` | 200, 401, 422, 429, 500 | 5/menit/IP | FR-AUTH-01 | `routes/auth_routes.py:23` |
| POST | `/auth/refresh` | Refresh Token | Publik: Publik (refresh token di body) | — | `RefreshTokenRequest` | 200 `RefreshTokenResponse` | 200, 401, 422, 429, 500 | 30/menit/IP | FR-AUTH-02 | `routes/auth_routes.py:43` |
| GET | `/auth/me` | Get Me | Bearer: Pengguna aktif | — | — | 200 `UserOut` | 200, 401, 500 | — | FR-AUTH-03 | `routes/auth_routes.py:60` |
| PUT | `/auth/me` | Update My Profile | Bearer: Pengguna aktif | — | `ProfileUpdate` | 200 `UserOut` | 200, 400, 401, 404, 409, 422, 500 | — | FR-AUTH-03 | `routes/auth_routes.py:66` |
| PUT | `/auth/me/password` | Change Password | Bearer: Pengguna aktif | — | `ChangePasswordRequest` | 200 — | 200, 400, 401, 404, 422, 500 | — | FR-AUTH-04 | `routes/auth_routes.py:78` |
| POST | `/auth/logout` | Logout | Bearer: Pengguna aktif | — | — | 200 — | 200, 401, 500 | — | FR-AUTH-05 | `routes/auth_routes.py:91` |

#### Registrations (Recruitment)

| Method | Path | Ringkasan | Auth / Peran | Parameter | Request | Response sukses | Kode status | Rate limit | Kebutuhan | Kode |
|---|---|---|---|---|---|---|---|---|---|---|
| GET | `/registrations/intake-status` | Get Intake Status | Publik: Publik | — | — | 200 `IntakeStatusResponse` | 200, 500 | — | FR-PUB-04 | `routes/registration_routes.py:47` |
| PUT | `/registrations/intake-status` | Update Intake Status | Bearer: can_manage_selection (Superadmin, Ketua, Wakil Ketua, PSDM) | — | `IntakeStatusUpdate` | 200 `IntakeStatusResponse` | 200, 401, 403, 422, 500 | — | FR-SEL-01 | `routes/registration_routes.py:68` |
| GET | `/registrations` | List Registrations | Bearer: require_pengurus | `status` (query) | — | 200 `RegistrationResponse[]` | 200, 401, 403, 422, 500 | — | FR-SEL-02 | `routes/registration_routes.py:159` |
| POST | `/registrations` | Submit Registration | Publik: Publik | — | `RegistrationCreate` | 201 `RegistrationResponse` | 201, 400, 403, 422, 429, 500, 503 | 10/menit/IP | FR-REG-01, FR-REG-02 | `routes/registration_routes.py:114` |
| GET | `/registrations/{identifier}` | Get Registration | Bearer: require_pengurus | `identifier`* (path) | — | 200 `RegistrationResponse` | 200, 401, 403, 404, 422, 500 | — | FR-SEL-02 | `routes/registration_routes.py:171` |
| DELETE | `/registrations/{identifier}` | Delete Registration | Bearer: can_manage_selection | `identifier`* (path) | — | 200 — | 200, 401, 403, 404, 422, 500 | — | FR-SEL-05 | `routes/registration_routes.py:247` |
| PATCH | `/registrations/{identifier}/approve` | Approve Registration | Bearer: can_manage_selection | `identifier`* (path) | `RegistrationReview` \| null | 200 `RegistrationResponse` | 200, 401, 403, 404, 422, 500 | — | FR-SEL-03 | `routes/registration_routes.py:185` |
| PATCH | `/registrations/{identifier}/reject` | Reject Registration | Bearer: can_manage_selection | `identifier`* (path) | — | 200 `RegistrationResponse` | 200, 401, 403, 404, 422, 500 | — | FR-SEL-04 | `routes/registration_routes.py:208` |
| POST | `/registrations/bulk-delete` | Bulk Delete Registrations | Bearer: can_manage_selection | — | `BulkDeleteRegistrationsRequest` | 200 `BulkDeleteRegistrationsResponse` | 200, 401, 403, 422, 500 | — | FR-SEL-05 | `routes/registration_routes.py:228` |

#### Members & Alumni

| Method | Path | Ringkasan | Auth / Peran | Parameter | Request | Response sukses | Kode status | Rate limit | Kebutuhan | Kode |
|---|---|---|---|---|---|---|---|---|---|---|
| GET | `/members` | List Members | Bearer: require_pengurus | `division` (query), `intake_period` (query), `status` (query) | — | 200 `MemberResponse[]` | 200, 401, 403, 422, 500 | — | FR-MEM-01 | `routes/member_routes.py:27` |
| POST | `/members` | Create Member | Bearer: can_manage_members (Superadmin, Ketua, Wakil Ketua, PSDM) | — | `MemberCreate` | 201 `MemberResponse` | 201, 400, 401, 403, 422, 500 | — | FR-MEM-03 | `routes/member_routes.py:71` |
| GET | `/members/{identifier}/alumni-profile` | Get Alumni Profile | Bearer: require_pengurus | `identifier`* (path) | — | 200 `AlumniProfileResponse` \| null | 200, 401, 403, 404, 422, 500 | — | FR-MEM-08 | `routes/member_routes.py:41` |
| PUT | `/members/{identifier}/alumni-profile` | Update Alumni Profile | Bearer: can_manage_members | `identifier`* (path) | `AlumniProfileUpdate` | 200 `AlumniProfileResponse` | 200, 401, 403, 404, 409, 422, 500 | — | FR-MEM-08 | `routes/member_routes.py:56` |
| GET | `/members/stats` | Get Members Count | Publik: Publik | — | — | 200 — | 200, 500 | — | FR-PUB-01 | `routes/member_routes.py:86` |
| GET | `/members/public` | Get Public Organization Members | Publik: Publik | — | — | 200 `PublicOrganizationMember[]` | 200, 500 | — | FR-PUB-02 | `routes/member_routes.py:97` |
| GET | `/members/{identifier}` | Get Member | Bearer: require_pengurus | `identifier`* (path) | — | 200 `MemberResponse` | 200, 401, 403, 404, 422, 500 | — | FR-MEM-02 | `routes/member_routes.py:107` |
| PUT | `/members/{identifier}` | Update Member | Bearer: can_manage_members | `identifier`* (path) | `MemberUpdate` | 200 `MemberResponse` | 200, 400, 401, 403, 404, 422, 500 | — | FR-MEM-04 | `routes/member_routes.py:121` |
| DELETE | `/members/{identifier}` | Delete Member | Bearer: can_manage_members | `identifier`* (path) | — | 200 — | 200, 401, 403, 404, 422, 500 | — | FR-MEM-06 | `routes/member_routes.py:156` |
| POST | `/members/{identifier}/anonymize` | Anonymize Member | Bearer: can_manage_members | `identifier`* (path) | — | 200 `MemberResponse` | 200, 401, 403, 404, 422, 500 | — | FR-MEM-05 | `routes/member_routes.py:139` |
| POST | `/members/imports` | Import Members Excel | Bearer: can_manage_members | `sheet_name` (query) | `Body_import_members_excel_members_imports_post` | 200 — | 200, 400, 401, 403, 413, 422, 500 | — | FR-MEM-07 | `routes/member_routes.py:173` |
| POST | `/members/{identifier}/access` | Grant Erp Access | Bearer: can_manage_members (SUPERADMIN hanya oleh superadmin) | `identifier`* (path) | `GrantERPAccessRequest` | 200 — | 200, 401, 403, 404, 422, 500 | — | FR-ERP-01 | `routes/member_routes.py:202` |
| DELETE | `/members/{identifier}/access` | Revoke Erp Access | Bearer: can_manage_members | `identifier`* (path) | — | 200 — | 200, 401, 403, 404, 422, 500 | — | FR-ERP-02 | `routes/member_routes.py:222` |
| PUT | `/members/{identifier}/password` | Reset Erp Password | Bearer: can_manage_members | `identifier`* (path) | `ResetMemberPasswordRequest` | 200 — | 200, 401, 403, 404, 422, 500 | — | FR-ERP-03 | `routes/member_routes.py:236` |

#### File Storage & Uploads

| Method | Path | Ringkasan | Auth / Peran | Parameter | Request | Response sukses | Kode status | Rate limit | Kebutuhan | Kode |
|---|---|---|---|---|---|---|---|---|---|---|
| POST | `/uploads/avatars` | Upload Avatar | Publik: Publik | — | `Body_upload_avatar_uploads_avatars_post` | 200 — | 200, 400, 422, 429, 500 | 10/menit/IP | FR-REG-03, FR-FILE-01 | `routes/upload_routes.py:15` |
| GET | `/uploads/avatars/{filename}` | Serve Avatar | Publik: Publik | `filename`* (path) | — | 200 — | 200, 404, 422, 500 | — | FR-FILE-03 | `routes/upload_routes.py:43` |
| DELETE | `/uploads/avatars/{filename}` | Delete Avatar | Bearer: require_roles(SUPERADMIN, ADMIN_BPH) | `filename`* (path) | — | 200 — | 200, 401, 403, 404, 422, 500 | — | FR-FILE-04 | `routes/upload_routes.py:109` |
| GET | `/uploads/tmp/avatars/{filename}` | Serve Staged Avatar | Publik: Publik (pratinjau staging) | `filename`* (path) | — | 200 — | 200, 404, 422, 500 | — | FR-FILE-03 | `routes/upload_routes.py:67` |
| GET | `/uploads/tmp/cvs/{filename}` | Serve Staged Cv | Publik: Publik (pratinjau staging) | `filename`* (path) | — | 200 — | 200, 404, 422, 500 | — | FR-FILE-03 | `routes/upload_routes.py:88` |
| POST | `/uploads/cvs` | Upload Cv | Publik: Publik | — | `Body_upload_cv_uploads_cvs_post` | 200 — | 200, 400, 422, 429, 500 | 10/menit/IP | FR-REG-04, FR-FILE-01 | `routes/upload_routes.py:131` |
| GET | `/uploads/cvs/{filename}` | Serve Cv | Publik: Publik (UUID tak tertebak; no-store) | `filename`* (path) | — | 200 — | 200, 404, 422, 500 | — | FR-FILE-03 | `routes/upload_routes.py:156` |
| DELETE | `/uploads/cvs/{filename}` | Delete Cv | Bearer: require_roles(SUPERADMIN, ADMIN_BPH) | `filename`* (path) | — | 200 — | 200, 401, 403, 404, 422, 500 | — | FR-FILE-04 | `routes/upload_routes.py:182` |

#### Audit Logs

| Method | Path | Ringkasan | Auth / Peran | Parameter | Request | Response sukses | Kode status | Rate limit | Kebutuhan | Kode |
|---|---|---|---|---|---|---|---|---|---|---|
| GET | `/audit-logs` | Get Audit Logs | Bearer: require_pengurus | `limit` (query), `offset` (query) | — | 200 `AuditLogPageOut` | 200, 401, 403, 422, 500 | — | FR-LOG-02 | `routes/log_routes.py:11` |

#### Health

| Method | Path | Ringkasan | Auth / Peran | Parameter | Request | Response sukses | Kode status | Rate limit | Kebutuhan | Kode |
|---|---|---|---|---|---|---|---|---|---|---|
| GET | `/health` | Health Check | Publik: Publik | — | — | 200 — | 200, 500 | — | FR-SYS-01 | `main.py:199` |
| GET | `/health/db` | Db Test | Publik: Publik | — | — | 200 — | 200, 500 | — | FR-SYS-01 | `main.py:210` |

### 6.2 Endpoint [USULAN] (56 operasi)

Rancangan; **belum** ada di kode. Skema lengkap di `openapi.yaml` (`x-orion-status`).

| Method | Path | Ringkasan | Peran | Parameter | Request | Response sukses | Kode status | Kebutuhan |
|---|---|---|---|---|---|---|---|---|
| GET | `/inventory/items` | Inventaris: daftar barang | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `q` (query), `category` (query), `location` (query), `condition` (query), `limit` (query), `offset` (query), `sort` (query) | — | 200 `InventoryItemPage` | 200, 401, 403, 422 | FR-INV-01 |
| POST | `/inventory/items` | Inventaris: tambah barang | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | — | `InventoryItemInput` | 201 `InventoryItem` | 201, 401, 403, 422 | FR-INV-03 |
| GET | `/inventory/items/{item_id}` | Inventaris: detail barang | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `item_id`* (path) | — | 200 `InventoryItem` | 200, 401, 403, 422 | FR-INV-03 |
| PATCH | `/inventory/items/{item_id}` | Inventaris: ubah barang | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `item_id`* (path) | `InventoryItemInput` | 200 `InventoryItem` | 200, 401, 403, 422 | FR-INV-03 |
| DELETE | `/inventory/items/{item_id}` | Inventaris: soft delete barang | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `item_id`* (path) | — | 204 — | 204, 401, 403, 422 | FR-INV-03 |
| GET | `/inventory/items/{item_id}/loans` | Inventaris: riwayat peminjaman per barang | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `item_id`* (path), `limit` (query), `offset` (query), `sort` (query) | — | 200 `LoanPage` | 200, 401, 403, 422 | FR-INV-06 |
| GET | `/inventory/loans` | Inventaris: daftar peminjaman | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `status` (query), `overdue` (query), `borrower` (query), `limit` (query), `offset` (query), `sort` (query) | — | 200 `LoanPage` | 200, 401, 403, 422 | FR-INV-06 |
| POST | `/inventory/loans` | Inventaris: catat peminjaman | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `Idempotency-Key` (header) | `LoanCreate` | 201 `Loan` | 201, 401, 403, 422 | FR-INV-04 |
| GET | `/inventory/loans/{loan_id}` | Inventaris: detail peminjaman | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `loan_id`* (path) | — | 200 `Loan` | 200, 401, 403, 422 | FR-INV-06 |
| POST | `/inventory/loans/{loan_id}/handover` | Inventaris: serah terima (DIAJUKAN → DIPINJAM) | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `loan_id`* (path) | — | 200 `Loan` | 200, 401, 403, 422 | FR-INV-04 |
| POST | `/inventory/loans/{loan_id}/return` | Inventaris: pengembalian (DIPINJAM → DIKEMBALIKAN) | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `loan_id`* (path) | `LoanReturn` | 200 `Loan` | 200, 401, 403, 422 | FR-INV-05 |
| POST | `/inventory/loans/{loan_id}/cancel` | Inventaris: batalkan pengajuan (DIAJUKAN → DIBATALKAN) | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `loan_id`* (path) | — | 200 `Loan` | 200, 401, 403, 422 | FR-INV-04 |
| POST | `/inventory/loans/{loan_id}/report-loss` | Inventaris: laporkan hilang (DIPINJAM → HILANG) | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `loan_id`* (path) | `LetterTransition` | 200 `Loan` | 200, 401, 403, 422 | FR-INV-05 |
| GET | `/members/{identifier}/loans` | Inventaris: riwayat peminjaman per anggota | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `identifier`* (path), `limit` (query), `offset` (query), `sort` (query) | — | 200 `LoanPage` | 200, 401, 403, 422 | FR-INV-06 |
| GET | `/inventory/reports/overdue` | Inventaris: laporan keterlambatan | require_pengurus | `limit` (query), `offset` (query), `sort` (query) | — | 200 `LoanPage` | 200, 401, 403, 422 | FR-INV-07 |
| GET | `/finance/accounts` | Keuangan: daftar akun | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | — | — | 200 `FinAccount[]` | 200, 401, 403, 422 | FR-FIN-06 |
| POST | `/finance/accounts` | Keuangan: tambah akun kas | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | — | `FinAccount` | 201 `FinAccount` | 201, 401, 403, 422 | FR-FIN-06 |
| GET | `/finance/categories` | Keuangan: daftar kategori (akun INCOME/EXPENSE) | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | — | — | 200 `FinAccount[]` | 200, 401, 403, 422 | FR-FIN-06 |
| POST | `/finance/categories` | Keuangan: tambah kategori | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | — | `FinAccount` | 201 `FinAccount` | 201, 401, 403, 422 | FR-FIN-06 |
| GET | `/finance/transactions` | Keuangan: daftar transaksi | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `from` (query), `to` (query), `kind` (query), `account_id` (query), `category_id` (query), `q` (query), `limit` (query), `offset` (query), `sort` (query) | — | 200 `TransactionPage` | 200, 401, 403, 422 | FR-FIN-02 |
| POST | `/finance/transactions` | Keuangan: catat transaksi | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `Idempotency-Key` (header) | `TransactionCreate` | 201 `Transaction` | 201, 401, 403, 422 | FR-FIN-03, FR-FIN-05 |
| GET | `/finance/transactions/{transaction_id}` | Keuangan: detail transaksi | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `transaction_id`* (path) | — | 200 `Transaction` | 200, 401, 403, 422 | FR-FIN-02 |
| POST | `/finance/transactions/{transaction_id}/reversal` | Keuangan: transaksi pembalik (koreksi) | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `transaction_id`* (path), `Idempotency-Key` (header) | `LetterTransition` | 201 `Transaction` | 201, 401, 403, 422 | FR-FIN-04 |
| GET | `/finance/ledgers/cash` | Keuangan: ledger arus kas | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `account_id` (query), `from` (query), `to` (query) | — | 200 `LedgerLine[]` | 200, 401, 403, 422 | FR-FIN-05 |
| GET | `/finance/ledgers/income-expense` | Keuangan: ledger pemasukan-pengeluaran | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `category_id` (query), `activity` (query), `from` (query), `to` (query) | — | 200 `LedgerLine[]` | 200, 401, 403, 422 | FR-FIN-05 |
| GET | `/finance/summaries/monthly` | Keuangan: rekap bulanan | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `year` (query) | — | 200 `MonthlySummary[]` | 200, 401, 403, 422 | FR-FIN-01, FR-FIN-07 |
| POST | `/finance/periods/{period}/close` | Keuangan: tutup buku periode | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `period`* (path) | — | 200 — | 200, 401, 403, 422 | FR-FIN-07 |
| GET | `/finance/dues-periods` | Keuangan: daftar periode iuran | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | — | — | 200 — | 200, 401, 403, 422 | FR-FIN-08 |
| POST | `/finance/dues-periods` | Keuangan: buat periode iuran + tagihan anggota aktif | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | — | `DuesPeriodCreate` | 201 — | 201, 401, 403, 422 | FR-FIN-08 |
| GET | `/finance/dues-periods/{period_id}/invoices` | Keuangan: status bayar per anggota | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `period_id`* (path), `status` (query) | — | 200 `DuesInvoice[]` | 200, 401, 403, 422 | FR-FIN-08 |
| POST | `/finance/dues-invoices/{invoice_id}/payments` | Keuangan: tandai lunas (membuat transaksi otomatis) | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `invoice_id`* (path), `Idempotency-Key` (header) | `DuesPayment` | 201 `DuesInvoice` | 201, 401, 403, 422 | FR-FIN-09 |
| POST | `/reports` | Laporan: buat laporan otomatis (async) | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | — | `ReportRequest` | 202 `Report` | 202, 401, 403, 422 | FR-FIN-12 |
| GET | `/reports/{report_id}` | Laporan: status laporan | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `report_id`* (path) | — | 200 `Report` | 200, 401, 403, 422 | FR-FIN-12 |
| GET | `/reports/{report_id}/file` | Laporan: unduh berkas | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `report_id`* (path) | — | 200 — | 200, 401, 403, 422 | FR-FIN-12 |
| GET | `/letters/incoming` | Arsip: daftar surat masuk | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris); baca sesuai klasifikasi | `q` (query), `from` (query), `to` (query), `classification` (query), `limit` (query), `offset` (query), `sort` (query) | — | 200 `LetterPage` | 200, 401, 403, 422 | FR-ARC-01, FR-ARC-04 |
| POST | `/letters/incoming` | Arsip: catat surat masuk | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | — | `IncomingLetterInput` | 201 `Letter` | 201, 401, 403, 422 | FR-ARC-04 |
| GET | `/letters/incoming/{letter_id}` | Arsip: detail surat masuk | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `letter_id`* (path) | — | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-04 |
| PATCH | `/letters/incoming/{letter_id}` | Arsip: ubah surat masuk | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `letter_id`* (path) | `IncomingLetterInput` | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-04 |
| GET | `/letters/outgoing` | Arsip: daftar surat keluar | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris); baca sesuai klasifikasi | `type_code` (query), `status` (query), `q` (query), `from` (query), `to` (query), `limit` (query), `offset` (query), `sort` (query) | — | 200 `LetterPage` | 200, 401, 403, 422 | FR-ARC-01 |
| POST | `/letters/outgoing` | Arsip: buat draf surat keluar | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) atau pengurus pembuat | — | `OutgoingLetterInput` | 201 `Letter` | 201, 401, 403, 422 | FR-ARC-07 |
| GET | `/letters/outgoing/{letter_id}` | Arsip: detail surat keluar | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `letter_id`* (path) | — | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-07 |
| PATCH | `/letters/outgoing/{letter_id}` | Arsip: ubah draf/revisi (membuat versi baru) | Pembuat / Sekretaris | `letter_id`* (path) | `OutgoingLetterInput` | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-07 |
| GET | `/letters/outgoing/{letter_id}/preview` | Arsip: pratinjau PDF (tanpa nomor final) | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `letter_id`* (path) | — | 200 — | 200, 401, 403, 422 | FR-ARC-07, FR-ARC-08 |
| GET | `/letters/outgoing/{letter_id}/versions` | Arsip: riwayat versi | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `letter_id`* (path) | — | 200 — | 200, 401, 403, 422 | FR-ARC-06 |
| GET | `/letters/outgoing/{letter_id}/document` | Arsip: PDF final surat terbit | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `letter_id`* (path) | — | 200 — | 200, 401, 403, 422 | FR-ARC-07 |
| GET | `/letters/incoming/{letter_id}/attachments` | Arsip: daftar lampiran surat masuk | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `letter_id`* (path) | — | 200 — | 200, 401, 403, 422 | FR-ARC-10 |
| POST | `/letters/incoming/{letter_id}/attachments` | Arsip: unggah lampiran surat masuk (multipart) | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `letter_id`* (path) | — | 201 — | 201, 401, 403, 422 | FR-ARC-04, FR-ARC-10 |
| GET | `/letters/outgoing/{letter_id}/attachments` | Arsip: daftar lampiran surat keluar | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `letter_id`* (path) | — | 200 — | 200, 401, 403, 422 | FR-ARC-10 |
| POST | `/letters/outgoing/{letter_id}/attachments` | Arsip: unggah lampiran surat keluar (multipart) | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `letter_id`* (path) | — | 201 — | 201, 401, 403, 422 | FR-ARC-04, FR-ARC-10 |
| GET | `/letter-templates` | Arsip: daftar template | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `type_code` (query) | — | 200 `LetterTemplate[]` | 200, 401, 403, 422 | FR-ARC-08 |
| POST | `/letter-templates` | Arsip: tambah template (versi baru) | Sekretaris, Superadmin | — | `LetterTemplate` | 201 `LetterTemplate` | 201, 401, 403, 422 | FR-ARC-08 |
| GET | `/letter-templates/{template_id}` | Arsip: detail template | can_manage_archive (Superadmin, Ketua, Wakil Ketua, Sekretaris) | `template_id`* (path) | — | 200 `LetterTemplate` | 200, 401, 403, 422 | FR-ARC-08 |
| PUT | `/letter-templates/{template_id}` | Arsip: aktifkan/ubah metadata template | Sekretaris, Superadmin | `template_id`* (path) | `LetterTemplate` | 200 `LetterTemplate` | 200, 401, 403, 422 | FR-ARC-08 |
| POST | `/letters/outgoing/{letter_id}/publish` | Arsip: transisi publish (DISETUJUI (atau DRAF pada versi minimal) → TERBIT; nomor diberikan) | Sekretaris / Ketua | `letter_id`* (path) | `LetterTransition` | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-05, FR-ARC-06 |
| POST | `/letters/outgoing/{letter_id}/cancel` | Arsip: transisi cancel (→ DIBATALKAN (nomor tidak dipakai ulang)) | Pembuat sebelum terbit; Ketua/Superadmin setelah terbit | `letter_id`* (path) | `LetterTransition` | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-05, FR-ARC-06 |
| POST | `/letters/outgoing/{letter_id}/archive` | Arsip: transisi archive (TERBIT → DIARSIPKAN) | Sekretaris | `letter_id`* (path) | `LetterTransition` | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-05, FR-ARC-06 |

### 6.3 Endpoint [PERLU-DISKUSI] (10 operasi)

Rancangan; **belum** ada di kode. Skema lengkap di `openapi.yaml` (`x-orion-status`).

| Method | Path | Ringkasan | Peran | Parameter | Request | Response sukses | Kode status | Kebutuhan |
|---|---|---|---|---|---|---|---|---|
| GET | `/inventory/items/{item_id}/label` | Inventaris: label QR barang | can_manage_inventory (Superadmin, Ketua, Wakil Ketua, Akademik Riset); baca: require_pengurus | `item_id`* (path) | — | 200 — | 200, 401, 403, 422 | FR-INV-08 |
| POST | `/finance/dues-invoices/{invoice_id}/qris` | Keuangan: buat QRIS dinamis untuk tagihan | Anggota pemilik tagihan / Bendahara | `invoice_id`* (path), `Idempotency-Key` (header) | — | 201 `QrisCharge` | 201, 401, 403, 422 | FR-FIN-10 |
| POST | `/finance/dues-invoices/{invoice_id}/reminders` | Keuangan: kirim ulang pengingat + QR | can_manage_finance (Superadmin, Ketua, Wakil Ketua, Bendahara); baca: require_pengurus | `invoice_id`* (path) | — | 202 — | 202, 401, 403, 422 | FR-FIN-11 |
| POST | `/letters/outgoing/{letter_id}/submit` | Arsip: transisi submit (DRAF/REVISI → DIAJUKAN) | Pembuat / Sekretaris | `letter_id`* (path) | `LetterTransition` | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-05, FR-ARC-06 |
| POST | `/letters/outgoing/{letter_id}/review` | Arsip: transisi review (DIAJUKAN → DITINJAU) | Sekretaris (bukan pembuat) | `letter_id`* (path) | `LetterTransition` | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-05, FR-ARC-06 |
| POST | `/letters/outgoing/{letter_id}/approve` | Arsip: transisi approve (DITINJAU → DISETUJUI) | Ketua / Wakil Ketua (bukan pembuat) | `letter_id`* (path) | `LetterTransition` | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-05, FR-ARC-06 |
| POST | `/letters/outgoing/{letter_id}/reject` | Arsip: transisi reject (DITINJAU → DITOLAK) | Peninjau / Ketua | `letter_id`* (path) | `LetterTransition` | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-05, FR-ARC-06 |
| POST | `/letters/outgoing/{letter_id}/request-revision` | Arsip: transisi request-revision (DITINJAU → REVISI) | Peninjau / Ketua | `letter_id`* (path) | `LetterTransition` | 200 `Letter` | 200, 401, 403, 422 | FR-ARC-05, FR-ARC-06 |
| GET | `/letter-verifications/{verification_code}` | Arsip: verifikasi keaslian surat (QR) | Publik | `verification_code`* (path) | — | 200 `LetterVerification` | 200, 401, 403, 422 | FR-ARC-11 |
| POST | `/webhooks/payments/{provider}` | Webhook: notifikasi pembayaran dari payment gateway | Penyedia pembayaran (tanpa JWT; signature wajib) | `provider`* (path) | `PaymentWebhook` | 200 — | 200, 401, 422 | FR-FIN-10 |

### 6.4 Contoh alur nyata [ADA-BACKEND]

Direkam dari aplikasi terhadap basis data uji lokal (data sintetis).

**Pendaftaran calon anggota**

```http
POST /orion/api/v1/registrations
Content-Type: application/json

{
  "student_id": "2610511777", "full_name": "Calon Contoh", "program_of_study": "S1 Informatika",
  "email": "calon.contoh@example.com", "contact_info": "081200000000", "intake_period": "2026",
  "interest_track": "IoT Embedded", "motivation": "Ingin belajar edge AI.", "consent_given": true,
  "photo": "tmp/avatars/<uuid>.webp", "cv_url": "tmp/cvs/<uuid>.pdf"
}
```

```json
// 201
{
  "id": "01a0ed3e-0955-7275-9582-8fd2ef2f7d88", "student_id": "2610511777", "full_name": "Calon Contoh",
  "program_of_study": "S1 Informatika", "email": "calon.contoh@example.com", "contact_info": "081200000000",
  "intake_period": "2026", "interest_track": ["IoT Embedded"], "motivation": "Ingin belajar edge AI.",
  "photo": "avatars/<uuid>.webp", "cv_url": "cvs/<uuid>.pdf", "portfolio_url": null, "status": "Pending",
  "member_id": null, "review_note": null, "submit_date": "29/09/2026",
  "consent_given": true, "consent_timestamp": "2026-09-29T12:57:40.949317Z"
}
```

Catatan: `photo`/`cv_url` dikirim sebagai path staging dari `POST /uploads/avatars` / `POST /uploads/cvs` dan dikembalikan sebagai path permanen.

**Approve**

```http
PATCH /orion/api/v1/registrations/2610511777/approve
Authorization: Bearer <access_token>
Content-Type: application/json

{"status": "Accepted", "division": null, "role": "Anggota"}
```

```json
// 200 — Member ID berikutnya untuk tahun intake
{"status": "Accepted", "member_id": "AIOT-2026-001", "review_note": "Disetujui oleh Test Superadmin (SUPERADMIN)", "...": "..."}
```

**Audit log**

```http
GET /orion/api/v1/audit-logs?limit=1&offset=0
Authorization: Bearer <access_token>
```

```json
{
  "items": [{
    "id": "01a0ed3e-09f2-777b-82ae-f2eeec7b10f7", "timestamp": "2026-09-29T12:57:41.106954Z",
    "actor_id": "01a0ed07-4027-724b-b3ef-aec6290c957f", "actor_name": "Test Superadmin", "actor_role": "SUPERADMIN",
    "is_superadmin": true, "action": "REGISTRATION_APPROVED", "resource_type": "REGISTRATION",
    "resource_id": "01a0ed3e-0955-7275-9582-8fd2ef2f7d88", "resource_label": "Pendaftar: Calon Contoh (2610511777)",
    "ip_address": null, "user_agent": null,
    "details": "{\"member_id\": \"AIOT-2026-001\", \"student_id\": \"2610511777\"}", "status": "SUCCESS"
  }],
  "total": 359,
  "stats": {"total": 359, "success": 309, "failed": 50, "admin_actions": 212}
}
```


**Publik**

```json
// GET /members/stats
{"total_members": 0, "active_members": 0, "alumni_count": 0}

// GET /registrations/intake-status
{"status": "OPEN", "batch_name": "Penerimaan Anggota Baru Periode 2026", "deadline": "2026-12-31", "quota": 100,
 "updated_at": "2026-09-29T12:35:08.572910Z", "updated_by": "01a0ed07-4027-724b-b3ef-aec6290c957f"}

// GET /health
{"status": "healthy", "service": "orion-backend", "version": "1.0.0", "api_prefix": "/orion/api/v1"}
```

### 6.5 Contoh endpoint usulan [USULAN]

**Catat peminjaman (stok atomik)**

```http
POST /orion/api/v1/inventory/loans
Authorization: Bearer <access_token>
Idempotency-Key: 5f0c2e1a-loan-001

{"item_id": "0190...", "borrower_identifier": "2610511777", "quantity": 1,
 "borrowed_at": "2026-10-01T09:00:00+07:00", "due_at": "2026-10-08T17:00:00+07:00", "status": "DIPINJAM"}
```

```json
// 201
{"id": "0191...", "loan_code": "PJM-2026-0001", "status": "DIPINJAM", "is_overdue": false, "quantity": 1}
// 409 bila available_qty < quantity
{"detail": "Stok tidak mencukupi", "error_code": "INVENTORY_STOCK_INSUFFICIENT"}
```

**Catat pengeluaran (server menyusun double-entry)**

```http
POST /orion/api/v1/finance/transactions
Idempotency-Key: 2c9e-tx-0012

{"txn_date": "2026-10-02", "description": "Pembelian modul ESP32-CAM", "kind": "EXPENSE",
 "amount": 480000, "account_id": "<Kas Tunai>", "category_id": "<Pengadaan Alat Lab>"}
```

```json
// 201
{"number": "FIN-2026-00012", "kind": "EXPENSE", "entries": [
  {"account_name": "Pengadaan Alat Lab", "debit": 480000, "credit": 0},
  {"account_name": "Kas Tunai", "debit": 0, "credit": 480000}]}
```

**Terbitkan surat keluar (penomoran saat terbit)**

```http
POST /orion/api/v1/letters/outgoing/0192.../publish
{"note": "Disahkan Ketua"}
```

```json
// 200
{"status": "TERBIT", "number": "008/KSM-AIoT/FIK-UPNVJ/B/X/2026", "version": 3}
// 409 bila status bukan DISETUJUI (versi penuh) / DRAF (versi minimal)
```

---

## 7. Kontrak webhook pembayaran [PERLU-DISKUSI]

Berlaku hanya bila Opsi B keuangan disetujui (SKPL D-01).

| Aspek | Kontrak |
|---|---|
| Endpoint | `POST /orion/api/v1/webhooks/payments/{provider}` (`midtrans`, `xendit`, …); publik, **tanpa** JWT |
| Payload | Sesuai format penyedia; minimal memuat `order_id` (= `payment_intents.provider_ref`), status transaksi, nominal, id event, signature |
| Verifikasi | Signature dihitung ulang dengan *server key* dari env (`PAYMENT_SERVER_KEY`), dibandingkan secara *constant-time*; nominal & `order_id` harus cocok dengan `payment_intents`; tidak cocok → 401, dicatat `webhook_events.signature_valid=false`, tanpa perubahan data |
| Idempotensi | `UNIQUE (provider, event_id)`; event duplikat → 200 tanpa efek; pelunasan membuat tepat satu transaksi (`dues_invoices.transaction_id` UNIQUE) |
| Respons | 200 secepat mungkin (< 5 detik); pemrosesan berat dilakukan setelah commit event |
| Retry | Penyedia mengulang bila non-2xx (jadwal mengikuti penyedia); server harus aman terhadap pengulangan dan urutan acak (status akhir tidak mundur: `PAID` tidak berubah menjadi `PENDING`) |
| Status | `pending` → `PENDING`; `settlement`/`capture` → `PAID` (+ transaksi keuangan); `expire` → `EXPIRED`; `deny`/`cancel`/`failure` → `FAILED` |
| Lingkungan | `PAYMENT_ENV=sandbox|production`, kunci terpisah, URL webhook terpisah |
| Rekonsiliasi | Job harian membandingkan laporan settlement penyedia dengan `payment_intents` & `fin_transactions` |
| Keamanan tambahan | Allow-list IP penyedia (bila dipublikasikan), batas ukuran body 64 KB, log tanpa data sensitif |

Contoh (gaya Midtrans, ilustrasi):

```json
{
  "order_id": "DUES-2026-10-0190a1b2",
  "transaction_status": "settlement",
  "gross_amount": "20000.00",
  "payment_type": "qris",
  "transaction_id": "a1b2c3d4-...",
  "signature_key": "<sha512(order_id+status_code+gross_amount+server_key)>"
}
```

## 8. Aturan validasi field

| Field | Endpoint | Aturan | Status |
|---|---|---|---|
| `student_id` (login) | `POST /auth/login` | NIM atau email; dicocokkan persis | [ADA-BACKEND] |
| `password` (baru) | `PUT /auth/me/password`, `PUT /members/{id}/password`, `POST /members/{id}/access`, ERP flags | 8 karakter – 72 byte UTF-8 | [ADA-BACKEND] `utils/security.py:82` |
| `email` | `PUT /auth/me` | Format email valid, ≤ 150, unik antar akun (case-insensitive) | [ADA-BACKEND] `schemas/auth.py:29` |
| `full_name` | `PUT /auth/me` | 1–150 karakter | [ADA-BACKEND] |
| `motivation` | `POST /registrations` | ≤ 150 kata | [ADA-BACKEND] `schemas/registration.py:27` |
| `interest_track` | `POST /registrations` | Array/teks dipisah koma; dinormalisasi ke enum (heuristik) | [ADA-BACKEND] `schemas/registration.py:38` |
| `portfolio_url` | registrasi, anggota | Kosong, `http(s)://…`, atau tanpa skema | [ADA-BACKEND] `utils/sanitizer.py:38` |
| `photo`/`cv_url`/`avatar` | registrasi, anggota, profil | Path staging `tmp/<jenis>/<uuid4>.<ext>` yang ada, nilai lama record, atau URL http(s) (khusus avatar) | [ADA-BACKEND] `services/storage_service.py:333` |
| `status` intake | `PUT /registrations/intake-status` | `OPEN`/`CLOSED` (case-insensitive) | [ADA-BACKEND] `schemas/registration.py:69` |
| `deadline` | idem | Tanggal ISO valid `YYYY-MM-DD` | [ADA-BACKEND] |
| `quota` | idem | 0 – 100.000 | [ADA-BACKEND] |
| `batch_name` | idem | 1 – 200 karakter | [ADA-BACKEND] |
| `role` ERP | `POST /members/{id}/access` | `PENGURUS` \| `SUPERADMIN` | [ADA-BACKEND] `schemas/member.py:130` |
| `graduation_year` | alumni profile | `^\d{4}$` | [ADA-BACKEND] |
| `linkedin_url` | alumni profile | URL http(s) valid | [ADA-BACKEND] |
| File foto | `POST /uploads/avatars` | JPEG/PNG/WebP (MIME + magic bytes), ≤ 2 MB | [ADA-BACKEND] |
| File CV | `POST /uploads/cvs` | PDF (`%PDF-`), ≤ 5 MB | [ADA-BACKEND] |
| File impor | `POST /members/imports` | `.xlsx`/`.xlsm`, ≤ 5 MB, sheet ada | [ADA-BACKEND] |
| `student_id` (registrasi) | `POST /registrations` | Tepat 10 digit; angkatan dalam 4 tahun terakhir | [USULAN] (saat ini hanya frontend, IC-04) |
| `amount` | keuangan | Integer > 0 | [USULAN] |
| `quantity` | peminjaman | Integer > 0 dan ≤ stok tersedia | [USULAN] |

## 9. Redirect URL lama

Didefinisikan di `routes/legacy_routes.py:16-31`, diuji `tests/test_legacy_urls.py`. GET/HEAD → 301, metode lain → 308 (metode & body dipertahankan), query string ikut.

| URL lama | URL baru |
|---|---|
| `GET/POST /members/` | `/members` |
| `GET /members/count` | `/members/stats` |
| `GET /members/public/organization` | `/members/public` |
| `POST /members/import-excel` | `/members/imports` |
| `POST /members/{identifier}/reset-password` | `/members/{identifier}/password` |
| `GET/POST /registrations/` | `/registrations` |
| `GET /audit-logs/` | `/audit-logs` |
| `POST /auth/change-password` | `/auth/me/password` |
| `POST /uploads/avatar`, `POST /uploads/cv` | `/uploads/avatars`, `/uploads/cvs` |
| `GET /avatars/{filename}`, `GET /cvs/{filename}` | `/uploads/avatars/{filename}`, `/uploads/cvs/{filename}` |
| `GET /db-test` | `/health/db` |

## 10. Riwayat revisi

| Versi | Tanggal | Penulis | Perubahan |
|---|---|---|---|
| 1.0 | 2026-09-29 | Tim Pengembang (dibantu asisten AI) | Dokumen awal: konvensi, katalog 40 endpoint aktual + 66 usulan, contoh nyata, kontrak webhook, aturan validasi |
