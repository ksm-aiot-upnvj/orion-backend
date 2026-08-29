# ORION Backend — KSM AIoT UPN "Veteran" Jakarta

Layanan backend terintegrasi untuk mendukung seluruh operasional organisasi **Kelompok Studi Mahasiswa (KSM) Artificial Intelligence of Things (AIoT)**, Fakultas Ilmu Komputer, UPN "Veteran" Jakarta.

---

## 🌟 Gambaran Umum
**ORION** (*Organizational Resource & Integrated Operations Network*) berfungsi sebagai pusat pengolahan data dan logika bisnis untuk portal publik maupun panel manajemen pengurus. Backend ini menghubungkan pendaftaran calon anggota, basis data keanggotaan aktif, inventaris riset laboratorium, hingga pembukuan keuangan organisasi.

---

## 🚀 Fitur Utama

- **🔐 Autentikasi & Kontrol Akses Pengurus**  
  Sistem login terproteksi untuk Pengurus Harian (BPH), Kepala Divisi, dan Staff agar dapat mengelola data internal organisasi secara aman.

- **👥 Manajemen Basis Data Anggota**  
  Penyimpanan terpusat profil anggota aktif lintas divisi (Akademik & Riset, PSDM, Humas & Multimedia, BPH) serta tracking direktori alumni.

- **📋 Pipeline Rekrutmen & Seleksi Calon Anggota**  
  Menerima formulir pendaftaran publik secara real-time, memfasilitasi evaluasi berkas oleh tim penyeleksi, serta otomatisasi penerbitan Member ID resmi saat calon anggota disetujui.

- **📦 Integrasi Layanan Operasional**  
  Menyediakan endpoint untuk pengelolaan stok alat lab AIoT, pencatatan transaksi kas, dan arsip persuratan resmi.

---

## 🗄️ Panduan Setup Database PostgreSQL Lokal

Pilih salah satu metode berikut untuk menyiapkan database PostgreSQL di laptop Anda:

### Opsi 1: Menggunakan Docker / TimescaleDB (Paling Cepat & Praktis)
Jalankan perintah berikut di terminal untuk menyalakan container PostgreSQL/TimescaleDB lokal:
```bash
docker run -d \
  --name orion-db \
  -e POSTGRES_DB=orion_dev_db \
  -e POSTGRES_USER=orion_dev_user \
  -e POSTGRES_PASSWORD=orion_dev_password \
  -p 5432:5432 \
  timescale/timescaledb:2.24.0-pg18
```

---

### Opsi 2: Menggunakan PostgreSQL Native / `psql` / pgAdmin / DBeaver
Jika Anda menggunakan instalasi PostgreSQL native di laptop:
1. Buka terminal atau query tool (DBeaver / pgAdmin / `psql -U postgres`).
2. Jalankan perintah SQL berikut:
```sql
-- 1. Buat user / role pengembang
CREATE USER orion_dev_user WITH PASSWORD 'orion_dev_password';

-- 2. Buat database untuk Orion
CREATE DATABASE orion_dev_db OWNER orion_dev_user;

-- 3. Berikan hak akses penuh
GRANT ALL PRIVILEGES ON DATABASE orion_dev_db TO orion_dev_user;
```

---

### Opsi 3: Berbagi Database dengan Stack `smart-hydroponic`
Jika container TimescaleDB dari proyek `smart-hydroponic` sudah berjalan di laptop Anda:
```bash
# Masuk ke terminal PostgreSQL container
docker exec -it timescaledb psql -U postgres

# Jalankan perintah SQL
CREATE USER orion_dev_user WITH PASSWORD 'orion_dev_password';
CREATE DATABASE orion_dev_db OWNER orion_dev_user;
GRANT ALL PRIVILEGES ON DATABASE orion_dev_db TO orion_dev_user;
\q
```

---

## 🛠️ Persiapan & Menjalankan Backend

### 1. Salin Konfigurasi Lingkungan
Buat file `.env` dari contoh yang telah disediakan:
```bash
cp .env.example .env
```
Pastikan kredensial PostgreSQL pada file `.env` sudah sesuai dengan database lokal Anda:
```ini
PGHOST=localhost
PGPORT=5432
PGUSER=orion_dev_user
PGPASSWORD=orion_dev_password
PGDATABASE=orion_dev_db
```

### 2. Pasang Dependensi
Pastikan [uv](https://github.com/astral-sh/uv) atau Python 3.14 sudah terpasang, lalu jalankan:
```bash
uv sync
```

### 3. Terapkan Skema Database & Jalankan Server
```bash
# Terapkan skema tabel terbaru via Alembic
uv run alembic upgrade head

# Jalankan server backend (aktif di http://localhost:8000)
uv run uvicorn main:app --reload --port 8000
```

---

## 🔑 Akun Uji Coba Pengurus (Development)
Saat backend berjalan pada `ENVIRONMENT=development`, Anda dapat langsung login menggunakan akun pengurus:
- **NIM / User ID:** `2210511084` (Dzulfikri Adjmal - Ketua / Super Admin)
- **Password:** `aiotupnvj2026`

---

## 📖 Dokumentasi API Interaktif
Setelah server berjalan, dokumentasi interaktif dapat diakses melalui browser:
- **Swagger UI:** [http://localhost:8000/orion/api/v1/docs](http://localhost:8000/orion/api/v1/docs)
- **Status API:** [http://localhost:8000/orion/api/v1/health](http://localhost:8000/orion/api/v1/health)
