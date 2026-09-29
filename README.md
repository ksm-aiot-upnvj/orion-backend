# ORION Backend — KSM AIoT UPN "Veteran" Jakarta

| Versi | Tanggal | Penulis |
|---|---|---|
| 1.0.0 (API v1) | 29 September 2026 | Tim Pengembang ORION |

**ORION** (*Organizational Resource & Integrated Operations Network*) adalah backend REST API untuk portal publik dan panel pengurus **Kelompok Studi Mahasiswa (KSM) Artificial Intelligence of Things (AIoT)**, Fakultas Ilmu Komputer, UPN "Veteran" Jakarta. Frontend berada di repositori `orion-frontend`.

## Daftar Isi

- [Fitur dan status](#fitur-dan-status)
- [Prasyarat](#prasyarat)
- [Instalasi](#instalasi)
- [Konfigurasi environment](#konfigurasi-environment)
- [Database: skema, migrasi, dan seed](#database-skema-migrasi-dan-seed)
- [Menjalankan aplikasi](#menjalankan-aplikasi)
- [Menjalankan test dan linter](#menjalankan-test-dan-linter)
- [Struktur folder](#struktur-folder)
- [Ringkasan API](#ringkasan-api)
- [Dokumentasi](#dokumentasi)
- [Kontribusi](#kontribusi)
- [Lisensi](#lisensi)
- [Riwayat revisi](#riwayat-revisi)

---

## Fitur dan status

Label: **[ADA-BACKEND]** tersedia di API ini · **[MVP-HTML]** baru prototipe di frontend (data tiruan) · **[USULAN]** rancangan. Rincian: [docs/SKPL.md](docs/SKPL.md).

| Modul | Fitur | Status |
|---|---|---|
| Autentikasi | Login NIM/email, access (30 menit) + refresh token (7 hari, rotasi), profil, ganti password, logout, RBAC berbasis jabatan dengan larangan eskalasi hak | [ADA-BACKEND] |
| Publik | Statistik anggota, struktur kepengurusan, status intake | [ADA-BACKEND] |
| Pendaftaran | Formulir calon anggota, unggah foto (EXIF dihapus, WebP) & CV PDF melalui staging, deadline (WIB) ditegakkan | [ADA-BACKEND] |
| Seleksi | Atur intake, daftar/detail pendaftar, approve (Member ID `AIOT-<tahun>-<NNN>`), reject, hapus tunggal/massal | [ADA-BACKEND] |
| Anggota & alumni | CRUD, impor Excel (`.xlsx` ≤ 5 MB), anonimisasi, hapus permanen, profil alumni | [ADA-BACKEND] |
| Akses ERP | Beri/cabut akses login, reset password anggota | [ADA-BACKEND] |
| Berkas | Staging → promosi, pembersihan otomatis 24 jam, penyajian avatar & CV | [ADA-BACKEND] |
| Audit | Log audit + endpoint baca berpaginasi | [ADA-BACKEND] |
| Platform | Health check, redirect URL lama (301/308), header keamanan, konfigurasi produksi *fail-closed* | [ADA-BACKEND] |
| Inventaris lab | Aset & peminjaman | [MVP-HTML] → [USULAN] (belum ada endpoint) |
| Kas & keuangan | Dua ledger, iuran, laporan | [MVP-HTML] → [USULAN] (belum ada endpoint) |
| Arsip & persuratan | Surat masuk/keluar, penomoran, template | [MVP-HTML] → [USULAN] (belum ada endpoint) |

## Prasyarat

| Perangkat | Versi | Catatan |
|---|---|---|
| Python | ≥ 3.14 | Dikelola otomatis oleh `uv` |
| [uv](https://github.com/astral-sh/uv) | ≥ 0.9 | Manajer dependensi (memakai `uv.lock`) |
| PostgreSQL | ≥ 14 | Wajib (tipe ENUM & ARRAY); TimescaleDB juga dapat dipakai |
| Docker | opsional | Untuk image produksi / database lokal |

## Instalasi

```bash
git clone https://github.com/ksm-aiot-upnvj/orion-backend.git
cd orion-backend
uv sync --frozen
cp .env.example .env
```

Siapkan database kosong (pilih salah satu), ganti `<password-dev>` dengan password pilihan Anda:

```bash
docker run -d --name orion-db -e POSTGRES_DB=orion_dev_db -e POSTGRES_USER=orion_dev_user -e POSTGRES_PASSWORD=<password-dev> -p 5432:5432 postgres:17
```

```sql
-- PostgreSQL native (psql / pgAdmin / DBeaver)
CREATE USER orion_dev_user WITH PASSWORD '<password-dev>';
CREATE DATABASE orion_dev_db OWNER orion_dev_user;
```

## Konfigurasi environment

Variabel dibaca dari environment atau file `.env` (`config/config.py`). **Jangan commit `.env`.**

| Variabel | Wajib | Default | Keterangan |
|---|---|---|---|
| `ENVIRONMENT` | — | `development` | `production` mengaktifkan pemeriksaan keamanan *fail-closed* |
| `DEBUG` | — | `False` | `True` = pesan error rinci di respons + seeder superadmin saat start. Selalu dimatikan di production |
| `PROJECT_NAME`, `API_V1_STR` | — | `ORION - KSM AIoT API`, `/orion/api/v1` | Prefix API |
| `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` | ✓ (atau `DATABASE_URL`) | nilai dev | Koneksi PostgreSQL |
| `DATABASE_URL` | — | — | Menggantikan `PG*`; format `postgresql+asyncpg://user:pass@host:port/db` |
| `JWT_SECRET` | ✓ di production | nilai dev publik | Minimal 32 karakter acak (`openssl rand -hex 32`); app menolak start di production dengan nilai default |
| `JWT_ALGORITHM` | — | `HS256` | Hanya `HS256`/`HS384`/`HS512` |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | — | `30`, `7` | Umur token |
| `SUPERADMIN_NIM`, `SUPERADMIN_NAME`, `SUPERADMIN_EMAIL`, `SUPERADMIN_PW` | ✓ | — | Akun superadmin untuk seeder |
| `CORS_ORIGINS` | — | origin localhost | JSON array origin frontend, mis. `["https://ksm.example.ac.id"]` |
| `CORS_ORIGIN_REGEX` | — | `*.trycloudflare.com` (non-production) | Regex origin tambahan |
| `TRUSTED_PROXY_HOPS` | — | `1` | Jumlah reverse proxy di depan API (cloudflared/Nginx = 1; tanpa proxy = 0) untuk IP klien |
| `UPLOAD_DIR` | — | `uploads` | Direktori berkas (subfolder `avatars/`, `cvs/`, `tmp/`) |
| `STAGED_UPLOAD_TTL_HOURS` | — | `24` | Umur maksimum unggahan staging yang tidak disimpan |
| `IMPORT_DEFAULT_PASSWORD` | — | kosong | Password awal akun hasil impor Excel; kosong = acak (aktifkan via reset password) |
| `LOG_LEVEL` | — | `INFO` | Level log |

## Database: skema, migrasi, dan seed

> **Penting:** migrasi Alembic saat ini **tidak** membangun tabel dasar dari nol (migrasi awal hanya mengubah kolom). `uv run alembic upgrade head` pada database kosong akan gagal. Gunakan langkah di bawah (sama dengan yang dilakukan `entrypoint.sh`). Rencana perbaikan: [docs/SCHEMA.md §6](docs/SCHEMA.md#6-strategi-migrasi).

**Database baru (kosong):**

```bash
uv run python -c "import asyncio, models; from config.db import engine, ensure_enums_and_tables; exec('async def init():\n    async with engine.begin() as conn:\n        await ensure_enums_and_tables(conn)\n    await engine.dispose()'); asyncio.run(init())"
uv run alembic stamp head
uv run python -m utils.seed
```

**Database yang sudah ada (pembaruan skema):**

```bash
uv run alembic upgrade head
```

**Membuat migrasi baru:**

```bash
uv run alembic revision --autogenerate -m "deskripsi singkat"
```

`utils.seed` membuat/memperbarui akun superadmin dari variabel `SUPERADMIN_*` (password tidak dicetak). Konfigurasi intake awal dapat diatur lewat `PUT /registrations/intake-status`.

## Menjalankan aplikasi

**Pengembangan:**

```bash
uv run uvicorn main:app --reload --port 8000
```

API: `http://localhost:8000/orion/api/v1` · Swagger UI: `http://localhost:8000/orion/api/v1/docs` · health: `GET /orion/api/v1/health`.

**Production (tanpa Docker):**

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Gunakan satu proses worker: rate limiter dan tugas pembersih staging berjalan di memori proses.

**Docker:**

```bash
docker build -t orion-backend .
docker run -d --name orion-api --env-file .env -p 8000:8000 -v orion-uploads:/app/uploads orion-backend
```

`entrypoint.sh` menunggu database, membuat skema (DB baru) atau menjalankan `alembic upgrade head` (DB lama), menurunkan hak ke user `orion`, lalu menjalankan uvicorn. Pembersihan berkas yatim satu kali: `uv run python scripts/cleanup_orphan_uploads.py` (daftar saja) lalu `--apply`.

## Menjalankan test dan linter

Test memerlukan PostgreSQL dengan skema terpasang (langkah "Database baru") dan variabel `SUPERADMIN_*` yang sama dengan akun ter-seed.

```bash
uv run pytest -q
uv run ruff check .
```

Status terakhir: 120 test lulus (29-09-2026). Pemindaian keamanan: [SECURITY_AUDIT.md](SECURITY_AUDIT.md).

## Struktur folder

```text
main.py            # app FastAPI, middleware, error handler, lifespan
config/            # Settings (env) dan koneksi DB
routes/            # router per modul + legacy_routes (redirect URL lama)
services/          # logika bisnis + raw SQL berparameter
schemas/           # model Pydantic request/response
models/            # model SQLAlchemy (tabel) & enum
utils/             # RBAC, JWT/bcrypt, rate limiter, IP klien, sanitizer, importer Excel, seeder
migrations/        # Alembic
scripts/           # utilitas pemeliharaan
templates/         # landing page API
tests/             # pytest
docs/              # dokumentasi rekayasa (lihat di bawah)
```

## Ringkasan API

Basis `/orion/api/v1`. Daftar lengkap (40 operasi aktual + rancangan): [docs/API.md](docs/API.md), spesifikasi mesin [docs/openapi.yaml](docs/openapi.yaml).

| Grup | Endpoint utama |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/refresh`, `GET/PUT /auth/me`, `PUT /auth/me/password`, `POST /auth/logout` |
| Publik | `GET /members/stats`, `GET /members/public`, `GET /registrations/intake-status` |
| Registrasi & seleksi | `POST/GET /registrations`, `GET/DELETE /registrations/{identifier}`, `PATCH .../approve`, `PATCH .../reject`, `POST /registrations/bulk-delete`, `PUT /registrations/intake-status` |
| Anggota & ERP | `GET/POST /members`, `GET/PUT/DELETE /members/{identifier}`, `POST .../anonymize`, `GET/PUT .../alumni-profile`, `POST /members/imports`, `POST/DELETE .../access`, `PUT .../password` |
| Berkas | `POST /uploads/avatars`, `POST /uploads/cvs`, `GET/DELETE /uploads/{avatars,cvs}/{filename}`, `GET /uploads/tmp/{avatars,cvs}/{filename}` |
| Audit & sistem | `GET /audit-logs`, `GET /health`, `GET /health/db` |

## Dokumentasi

| Dokumen | Isi |
|---|---|
| [docs/SKPL.md](docs/SKPL.md) | SRS utama: kebutuhan fungsional & non-fungsional, keterlacakan, roadmap, ketidakkonsistenan, daftar diskusi |
| [docs/BRD.md](docs/BRD.md) | Kebutuhan bisnis, KPI, pemangku kepentingan |
| [docs/PRD.md](docs/PRD.md) | Persona, user story, fitur, rilis |
| [docs/FSD.md](docs/FSD.md) | Spesifikasi layar, field, validasi, RBAC |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | Diagram alur proses |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arsitektur saat ini vs target, ADR, migrasi React |
| [docs/API.md](docs/API.md) + [docs/openapi.yaml](docs/openapi.yaml) | Kontrak API |
| [docs/SCHEMA.md](docs/SCHEMA.md) | Skema basis data & ERD |
| [SECURITY_AUDIT.md](SECURITY_AUDIT.md), [SECURITY-PATTERNS.md](SECURITY-PATTERNS.md), [ARCHITECTURE-HANDOFF.md](ARCHITECTURE-HANDOFF.md) | Keamanan & serah terima |

`docs/openapi.yaml` bagian `ADA-BACKEND` dihasilkan dari `app.openapi()`; bila route berubah, perbarui spesifikasi lalu validasi:

```bash
uvx openapi-spec-validator docs/openapi.yaml
```

## Kontribusi

1. Buat branch dari `main`: `feat/<ringkas>`, `fix/<ringkas>`, atau `docs/<ringkas>`.
2. Tulis/perbarui test untuk setiap perubahan perilaku; jalankan `uv run pytest -q` dan `uv run ruff check .`.
3. Perbarui dokumen terkait di `docs/` (label status, ID kebutuhan, `openapi.yaml`).
4. Commit dengan format *conventional commits* (`feat(members): ...`), satu perubahan logis per commit.
5. Buka pull request; minimal satu reviewer dari tim pengembang.
6. Jangan commit secret, `.env`, atau isi `uploads/`.

## Lisensi

Hak cipta © KSM AIoT UPN "Veteran" Jakarta. Belum ada file lisensi terbuka di repositori ini — kode diperlakukan sebagai milik organisasi (*proprietary*) sampai pengurus menetapkan lisensi.

## Riwayat revisi

| Versi | Tanggal | Penulis | Perubahan |
|---|---|---|---|
| 1.0 | 2026-09-29 | Tim Pengembang (dibantu asisten AI) | Ditulis ulang sesuai kode terkini: status fitur, variabel environment lengkap, prosedur DB baru yang benar, test, struktur, dokumentasi |
