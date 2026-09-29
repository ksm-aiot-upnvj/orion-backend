# WORKFLOW — Alur Proses ORION

| Atribut | Nilai |
|---|---|
| Versi | 1.0 |
| Tanggal | 29 September 2026 |
| Penulis | Tim Pengembang ORION (disusun dengan bantuan asisten AI) |

Dokumen terkait: [SKPL](SKPL.md) · [FSD](FSD.md) · [API](API.md) · [SCHEMA](SCHEMA.md) · [ARCHITECTURE](ARCHITECTURE.md)

## Daftar Isi

1. [Autentikasi dan otorisasi](#1-autentikasi-dan-otorisasi-ada-backend)
2. [Pendaftaran dan seleksi calon anggota](#2-pendaftaran-dan-seleksi-calon-anggota-ada-backend)
3. [Unggah berkas: staging dan promosi](#3-unggah-berkas-staging-dan-promosi-ada-backend)
4. [Peminjaman dan pengembalian inventaris](#4-peminjaman-dan-pengembalian-inventaris-usulan)
5. [Pencatatan dua ledger](#5-pencatatan-dua-ledger-usulan)
6. [Iuran, pembayaran, dan rekonsiliasi](#6-iuran-pembayaran-dan-rekonsiliasi-usulan--perlu-diskusi)
7. [Surat keluar: pembuatan sampai terbit](#7-surat-keluar-pembuatan-sampai-terbit-usulan--perlu-diskusi)
8. [Pencatatan surat masuk](#8-pencatatan-surat-masuk-usulan)
9. [Pembuatan laporan otomatis](#9-pembuatan-laporan-otomatis-usulan)
10. [Riwayat revisi](#10-riwayat-revisi)

Label status mengikuti [SKPL §1.3](SKPL.md#13-label-status-wajib-dibaca).

---

## 1. Autentikasi dan otorisasi [ADA-BACKEND]

**Aktor:** Pengurus, Frontend, ORION API, PostgreSQL. **Kebutuhan:** FR-AUTH-01..07.
**Narasi:** pengurus login dengan NIM/email; API memverifikasi bcrypt, menerbitkan access (30 menit) dan refresh token (7 hari), dan mencatat audit. Setiap permintaan terlindungi memuat bearer token; dependency RBAC memuat ulang user dari DB (sehingga akun nonaktif langsung ditolak) lalu memeriksa peran. Frontend me-refresh token sebelum kedaluwarsa.

```mermaid
sequenceDiagram
    autonumber
    actor P as Pengurus
    participant FE as Frontend
    participant API as ORION API
    participant DB as PostgreSQL
    P->>FE: NIM/email + password
    FE->>API: POST /auth/login
    API->>API: rate limit 5/menit per IP (proxy tepercaya)
    API->>DB: SELECT user aktif (JOIN members via NIM)
    alt kredensial salah / nonaktif
        API->>DB: INSERT audit AUTH_LOGIN_FAILED
        API-->>FE: 401 pesan seragam
    else valid
        API->>DB: INSERT audit AUTH_LOGIN_SUCCESS
        API-->>FE: access (30m) + refresh (7h) + user
    end
    FE->>API: GET /members (Bearer access)
    API->>API: decode JWT, type == access
    API->>DB: muat user aktif + role efektif
    alt role tidak di allow-list
        API-->>FE: 403
    else diizinkan
        API-->>FE: 200 data
    end
    Note over FE,API: 2 menit sebelum kedaluwarsa
    FE->>API: POST /auth/refresh (refresh token)
    API-->>FE: pasangan token baru (rotasi)
```

---

## 2. Pendaftaran dan seleksi calon anggota [ADA-BACKEND]

**Aktor:** Calon anggota, PSDM/Ketua/Wakil (seleksi), Pengurus lain (baca). **Kebutuhan:** FR-REG-01..04, FR-SEL-01..05.
**Narasi:** calon mengisi formulir selama intake OPEN; server menegakkan deadline (WIB) secara *fail-closed*. Pengurus meninjau; approve membuat anggota dengan Member ID berikutnya untuk tahun intake.

```mermaid
stateDiagram-v2
    [*] --> Pending: POST /registrations (intake OPEN, belum lewat deadline)
    Pending --> Accepted: PATCH approve (PSDM/Ketua/Wakil)
    Pending --> Rejected: PATCH reject
    Rejected --> Accepted: PATCH approve
    Accepted --> Rejected: PATCH reject (anggota yang sudah dibuat tetap ada)
    Pending --> [*]: DELETE / bulk-delete (hak hapus)
    Accepted --> [*]: DELETE (foto dipertahankan bila jadi avatar anggota)
    Rejected --> [*]: DELETE
    note right of Accepted
        Member ID = AIOT-tahun-NNN (maks + 1)
        baris members dibuat, avatar = foto
    end note
```

Catatan: transisi `Rejected → Accepted` dan `Accepted → Rejected` diizinkan kode saat ini; aturan bisnisnya perlu dikonfirmasi pengurus.

---

## 3. Unggah berkas: staging dan promosi [ADA-BACKEND]

**Aktor:** Pengguna (calon/pengurus), ORION API, Disk, PostgreSQL, Task pembersih. **Kebutuhan:** FR-FILE-01..03.

```mermaid
sequenceDiagram
    autonumber
    actor U as Pengguna
    participant API as ORION API
    participant FS as Disk uploads/
    participant DB as PostgreSQL
    U->>API: POST /uploads/avatars (file)
    API->>API: cek MIME + magic bytes, ukuran, hapus EXIF, WebP
    API->>FS: tulis tmp/avatars/uuid.webp
    API-->>U: path tmp/avatars/uuid.webp (pratinjau /uploads/tmp/...)
    U->>API: POST /registrations {photo: tmp/avatars/uuid.webp}
    API->>API: hanya path staging yang sah
    API->>FS: pindah atomik ke avatars/uuid.webp
    API->>DB: INSERT registrasi
    alt DB gagal
        API->>FS: kembalikan ke tmp/ (bisa dicoba ulang)
        API-->>U: 4xx/5xx
    else sukses
        API-->>U: 201 photo = avatars/uuid.webp
    end
    Note over FS: Task tiap jam menghapus tmp/ berumur > 24 jam
```

---

## 4. Peminjaman dan pengembalian inventaris [USULAN]

**Aktor:** Peminjam (anggota), Petugas inventaris (Akademik Riset/Ketua/Wakil), Sistem. **Kebutuhan:** FR-INV-03..07.
**Narasi:** petugas mencatat peminjaman atas nama anggota; stok berkurang secara atomik saat serah terima. Pengembalian mencatat kondisi; unit rusak dipindah ke stok rusak. Keterlambatan dihitung dari tenggat, bukan status tersimpan.

```mermaid
stateDiagram-v2
    [*] --> DIAJUKAN: catat pengajuan
    [*] --> DIPINJAM: catat pinjam langsung (stok berkurang)
    DIAJUKAN --> DIPINJAM: handover (stok berkurang atomik)
    DIAJUKAN --> DIBATALKAN: cancel
    DIPINJAM --> DIKEMBALIKAN: return kondisi BAIK atau RUSAK
    DIPINJAM --> HILANG: report-loss (stok total berkurang)
    DIKEMBALIKAN --> [*]
    DIBATALKAN --> [*]
    HILANG --> [*]
    note right of DIPINJAM
        Terlambat = DIPINJAM dan due_at lewat
        (turunan, tampil di laporan keterlambatan)
    end note
```

```mermaid
sequenceDiagram
    autonumber
    actor PT as Petugas
    participant API as ORION API
    participant DB as PostgreSQL
    PT->>API: POST /inventory/loans (item, peminjam, qty, tenggat)
    API->>DB: BEGIN
    API->>DB: UPDATE inventory_items SET available_qty = available_qty - qty, borrowed_qty = borrowed_qty + qty WHERE id = item AND available_qty >= qty
    alt 0 baris (stok kurang / balapan kalah)
        API->>DB: ROLLBACK
        API-->>PT: 409 Stok tidak mencukupi
    else 1 baris
        API->>DB: INSERT inventory_loans (DIPINJAM, recorded_by)
        API->>DB: INSERT audit_logs
        API->>DB: COMMIT
        API-->>PT: 201 PJM-2026-0001
    end
    PT->>API: POST /inventory/loans/{id}/return (kondisi)
    API->>DB: UPDATE stok (tersedia atau rusak) + status DIKEMBALIKAN
    API-->>PT: 200
```

---

## 5. Pencatatan dua ledger [USULAN]

**Aktor:** Bendahara, Sistem. **Kebutuhan:** FR-FIN-03..05.
**Narasi:** Bendahara mencatat **satu** transaksi; sistem menyusun entri double-entry. Entri pada akun kas membentuk *ledger arus kas*; entri pada akun kategori membentuk *ledger pemasukan-pengeluaran*. Koreksi dilakukan dengan transaksi pembalik.

```mermaid
flowchart TD
    A["Bendahara: catat transaksi<br/>tanggal, keterangan, jenis, nominal,<br/>akun kas, kategori"] --> B{"Jenis?"}
    B -->|Pemasukan| C["Debit akun kas<br/>Kredit akun pendapatan"]
    B -->|Pengeluaran| D["Debit akun beban<br/>Kredit akun kas"]
    B -->|Transfer| E["Debit akun kas tujuan<br/>Kredit akun kas asal"]
    C --> F{"Debit = kredit dan<br/>periode belum ditutup?"}
    D --> F
    E --> F
    F -->|Tidak| X["Tolak 409/422"]
    F -->|Ya| G["Simpan fin_transactions + fin_entries<br/>(immutable)"]
    G --> H["Ledger arus kas<br/>= entri pada akun ASSET"]
    G --> I["Ledger pemasukan-pengeluaran<br/>= entri pada akun INCOME/EXPENSE"]
    G --> J["Audit log"]
    K["Salah input"] --> L["POST reversal: entri kebalikan<br/>+ transaksi benar"]
    L --> G
```

---

## 6. Iuran, pembayaran, dan rekonsiliasi [USULAN] / [PERLU-DISKUSI]

**Aktor:** Bendahara, Anggota, Payment gateway (Opsi B), Sistem. **Kebutuhan:** FR-FIN-08..11.

### 6.1 Opsi A — pelunasan manual [USULAN]

```mermaid
sequenceDiagram
    autonumber
    actor B as Bendahara
    actor A as Anggota
    participant API as ORION API
    participant DB as PostgreSQL
    B->>API: POST /finance/dues-periods (2026-10, Rp20.000, jatuh tempo)
    API->>DB: INSERT dues_periods + dues_invoices untuk semua anggota Aktif
    A->>B: bayar (tunai / transfer / QRIS statis)
    B->>API: POST /finance/dues-invoices/{id}/payments (akun penerima, bukti)
    API->>DB: BEGIN
    API->>DB: INSERT fin_transactions (source=DUES) + fin_entries
    API->>DB: UPDATE dues_invoices SET status=PAID, transaction_id WHERE status=UNPAID
    alt sudah PAID
        API->>DB: ROLLBACK
        API-->>B: 409
    else
        API->>DB: COMMIT
        API-->>B: 201 lunas (tercatat di kedua ledger)
    end
    B->>API: GET /finance/dues-periods/{id}/invoices?status=UNPAID
    API-->>B: daftar anggota belum bayar
```

### 6.2 Opsi B — QRIS dinamis + webhook [PERLU-DISKUSI]

```mermaid
sequenceDiagram
    autonumber
    actor A as Anggota
    participant API as ORION API
    participant PG as Payment gateway
    participant DB as PostgreSQL
    A->>API: POST /finance/dues-invoices/{id}/qris
    API->>DB: INSERT payment_intents (PENDING, expires_at)
    API->>PG: create charge QRIS (order_id, amount)
    PG-->>API: qr_string
    API-->>A: QR + batas waktu
    A->>PG: scan & bayar via e-wallet/m-banking
    PG->>API: POST /webhooks/payments/{provider} (event, signature)
    API->>API: verifikasi signature, nominal, order_id
    alt tidak valid
        API->>DB: INSERT webhook_events (signature_valid=false)
        API-->>PG: 401
    else event duplikat
        API-->>PG: 200 (tanpa efek)
    else settlement
        API->>DB: INSERT webhook_events + transaksi DUES + invoice PAID (satu transaksi DB)
        API-->>PG: 200
    end
    Note over API,PG: QR kedaluwarsa → intent EXPIRED, anggota minta QR baru
    Note over API,DB: Job harian: rekonsiliasi laporan settlement vs transaksi
```

### 6.3 Pengingat [PERLU-DISKUSI]

```mermaid
flowchart LR
    S["Job terjadwal 08.00 WIB"] --> Q{"Tagihan UNPAID<br/>H-3, H0, H+7?"}
    Q -->|Tidak| E["Selesai"]
    Q -->|Ya| O{"Opt-out atau<br/>sudah 3 kali atau<br/>< 48 jam dari kiriman terakhir?"}
    O -->|Ya| E
    O -->|Tidak| N["notification_outbox: EMAIL/WA<br/>tautan + QR baru (Opsi B)"]
    N --> W["Worker kirim + catat status"]
```

---

## 7. Surat keluar: pembuatan sampai terbit [USULAN] / [PERLU-DISKUSI]

**Aktor:** Pembuat (Sekretaris/pengurus), Peninjau (Sekretaris), Pengesah (Ketua/Wakil), Sistem. **Kebutuhan:** FR-ARC-05..09, FR-ARC-11.
**Narasi:** surat dibuat sebagai draf dari template per jenis; pratinjau PDF dibuat server. Versi penuh melewati tinjauan dan persetujuan; versi minimal langsung terbit. **Nomor hanya diberikan saat TERBIT**, dalam transaksi yang mengunci baris counter, sehingga tidak ada nomor ganda dan draf yang batal tidak "memakan" nomor.

```mermaid
stateDiagram-v2
    [*] --> DRAF: buat dari template
    DRAF --> DIAJUKAN: submit
    DIAJUKAN --> DITINJAU: review (bukan pembuat)
    DITINJAU --> REVISI: request-revision
    REVISI --> DIAJUKAN: submit ulang (versi baru)
    DITINJAU --> DITOLAK: reject
    DITINJAU --> DISETUJUI: approve (Ketua/Wakil)
    DISETUJUI --> TERBIT: publish (nomor + PDF final)
    DRAF --> TERBIT: publish (versi minimal, D-04)
    TERBIT --> DIARSIPKAN: archive
    DRAF --> DIBATALKAN: cancel
    DIAJUKAN --> DIBATALKAN: cancel
    REVISI --> DIBATALKAN: cancel
    DISETUJUI --> DIBATALKAN: cancel
    TERBIT --> DIBATALKAN: cancel (Ketua/Superadmin, nomor tetap tercatat)
    DITOLAK --> [*]
    DIARSIPKAN --> [*]
    DIBATALKAN --> [*]
```

```mermaid
sequenceDiagram
    autonumber
    actor S as Sekretaris
    actor K as Ketua
    participant API as ORION API
    participant R as Renderer PDF (WeasyPrint)
    participant DB as PostgreSQL
    S->>API: POST /letters/outgoing (jenis B, variabel, isi)
    API->>API: sanitasi HTML allow-list, validasi skema variabel
    API->>DB: INSERT letters (DRAF) + letter_versions v1
    S->>API: GET /letters/outgoing/{id}/preview
    API->>R: render template Jinja2 (autoescape) tanpa nomor final
    R-->>S: PDF pratinjau
    S->>API: POST .../submit
    K->>API: POST .../approve (catatan)
    API->>DB: INSERT letter_approvals
    S->>API: POST .../publish
    API->>DB: BEGIN
    API->>DB: INSERT ... ON CONFLICT (scope, tahun) DO UPDATE last_number+1 RETURNING (baris terkunci)
    API->>DB: UPDATE letters SET number, status TERBIT (UNIQUE number)
    API->>R: render PDF final (+ QR verifikasi, D-05)
    API->>DB: simpan final_pdf_path, audit, COMMIT
    API-->>S: 200 nomor 008/KSM-AIoT/FIK-UPNVJ/B/X/2026
```

---

## 8. Pencatatan surat masuk [USULAN]

**Aktor:** Sekretaris, Penerima disposisi. **Kebutuhan:** FR-ARC-04, FR-ARC-10.

```mermaid
flowchart TD
    A["Surat fisik/email diterima"] --> B["Sekretaris: POST /letters/incoming<br/>pengirim, nomor pengirim, perihal,<br/>tanggal surat & diterima, klasifikasi"]
    B --> C["Sistem: nomor agenda SM-2026-0001<br/>status DITERIMA"]
    C --> D["Unggah lampiran (scan PDF/gambar)<br/>via staging"]
    D --> E{"Perlu disposisi?"}
    E -->|Ya| F["Pilih penerima disposisi + catatan"]
    E -->|Tidak| G["DIARSIPKAN"]
    F --> H["Penerima menindaklanjuti"] --> G
    G --> I["Dapat dicari; akses sesuai klasifikasi;<br/>retensi default 5 tahun"]
```

---

## 9. Pembuatan laporan otomatis [USULAN]

**Aktor:** Bendahara/Ketua, Worker laporan. **Kebutuhan:** FR-FIN-12, FR-ARC-09.
**Narasi:** laporan diminta secara asinkron; worker mengambil data dari ledger, iuran, dan tabel pengurus (penandatangan), membuat PDF (WeasyPrint) atau XLSX (openpyxl), dan menyimpan hash data sumber sebagai *snapshot*.

```mermaid
sequenceDiagram
    autonumber
    actor B as Bendahara
    participant API as ORION API
    participant W as Worker laporan
    participant DB as PostgreSQL
    participant FS as Penyimpanan berkas
    B->>API: POST /reports (FINANCE_PERIOD, 2026-10, PDF)
    API->>DB: INSERT reports (QUEUED)
    API-->>B: 202 report_id
    W->>DB: ambil job QUEUED (FOR UPDATE SKIP LOCKED)
    W->>DB: ledger kas & kategori, iuran, pengurus aktif (Ketua, Bendahara)
    W->>W: render template laporan
    W->>FS: simpan reports/uuid.pdf
    W->>DB: UPDATE reports DONE, file_path, source_hash
    B->>API: GET /reports/{id}
    API-->>B: DONE + download_url
    B->>API: GET /reports/{id}/file
    API-->>B: application/pdf
```

---

## 10. Riwayat revisi

| Versi | Tanggal | Penulis | Perubahan |
|---|---|---|---|
| 1.0 | 2026-09-29 | Tim Pengembang (dibantu asisten AI) | Dokumen awal: 9 alur (3 aktual, 6 usulan) dengan diagram Mermaid |
