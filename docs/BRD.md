# BRD — Business Requirements Document ORION

| Atribut | Nilai |
|---|---|
| Versi | 1.0 |
| Tanggal | 29 September 2026 |
| Penulis | Tim Pengembang ORION (disusun dengan bantuan asisten AI) |
| Pemilik bisnis | Pengurus Harian KSM AIoT UPN "Veteran" Jakarta |

Dokumen terkait: [PRD](PRD.md) · [SKPL](SKPL.md) · [ARCHITECTURE](ARCHITECTURE.md)

## Daftar Isi

1. [Latar belakang](#1-latar-belakang)
2. [Masalah bisnis](#2-masalah-bisnis)
3. [Tujuan dan indikator keberhasilan](#3-tujuan-dan-indikator-keberhasilan)
4. [Pemangku kepentingan](#4-pemangku-kepentingan)
5. [Ruang lingkup](#5-ruang-lingkup)
6. [Kebutuhan bisnis](#6-kebutuhan-bisnis)
7. [Manfaat](#7-manfaat)
8. [Risiko, asumsi, dan batasan](#8-risiko-asumsi-dan-batasan)
9. [Analisis biaya-manfaat ringkas](#9-analisis-biaya-manfaat-ringkas)
10. [Riwayat revisi](#10-riwayat-revisi)

---

## 1. Latar belakang

KSM AIoT adalah kelompok studi mahasiswa di Fakultas Ilmu Komputer UPN "Veteran" Jakarta yang mengelola rekrutmen anggota, divisi kepengurusan, perangkat laboratorium IoT/AI, kas organisasi, dan persuratan resmi ke fakultas maupun mitra. Selama ini pengelolaan tersebar di Google Form, spreadsheet, grup chat, dan dokumen Word, dengan pengurus yang berganti setiap periode.

ORION (*Organizational Resource & Integrated Operations Network*) dibangun sebagai portal terpadu. Status saat dokumen ini ditulis: portal publik, pendaftaran, seleksi, direktori anggota, akses login pengurus, dan log audit **sudah berjalan** di backend; modul inventaris, keuangan, dan persuratan **baru berupa prototipe HTML** dengan data tiruan (lihat [SKPL §2.2](SKPL.md#22-fungsi-produk-ringkas)).

## 2. Masalah bisnis

| ID | Masalah | Dampak |
|---|---|---|
| MB-01 | Data pendaftar & anggota berulang kali disalin dari Google Form ke spreadsheet | Data ganda/usang, NIM salah ketik, sulit menentukan anggota aktif |
| MB-02 | Hak akses berbagi satu akun/spreadsheet | Tidak ada jejak siapa mengubah apa; risiko kebocoran data pribadi |
| MB-03 | Peminjaman alat lab dicatat informal | Alat hilang/terlambat tanpa penanggung jawab jelas; stok tidak diketahui |
| MB-04 | Bendahara mencatat kas dan iuran di beberapa tempat | Input ganda, selisih saldo, rekap bulanan & LPJ memakan waktu |
| MB-05 | Iuran anggota ditagih manual lewat chat | Tunggakan tidak terpantau |
| MB-06 | Nomor surat keluar diatur manual | Nomor ganda/terlewat, format kop berbeda-beda, arsip sulit dicari |
| MB-07 | Serah terima antar kepengurusan hilang pengetahuan | Sistem & data tidak berkelanjutan |
| MB-08 | Kewajiban UU PDP (persetujuan, hak hapus) belum terdokumentasi | Risiko hukum & reputasi |

## 3. Tujuan dan indikator keberhasilan

| ID | Tujuan | KPI | Target | Cara ukur |
|---|---|---|---|---|
| G-01 | Rekrutmen sepenuhnya daring | % pendaftar yang masuk via ORION | 100% periode berikutnya | Jumlah `registrations` vs pendaftar dilaporkan panitia |
| G-02 | Seleksi lebih cepat | Median waktu submit → keputusan | ≤ 7 hari | `created_at` vs audit `REGISTRATION_APPROVED/REJECTED` |
| G-03 | Sumber data anggota tunggal | Jumlah spreadsheet anggota yang masih dipelihara | 0 setelah 1 periode | Survei pengurus |
| G-04 | Akuntabilitas akses | % aksi administratif tercatat di audit | 100% | Review audit log |
| G-05 | Pelacakan inventaris | % peminjaman tercatat dengan peminjam & tenggat | 100% | `inventory_loans` [USULAN] |
| G-06 | Keterlambatan alat berkurang | Peminjaman terlambat > 7 hari | < 5% | Laporan keterlambatan [USULAN] |
| G-07 | Bendahara tanpa input ganda | Rekap bulanan tersedia tanpa kerja tambahan | ≤ 5 menit per bulan | Waktu membuat laporan [USULAN] |
| G-08 | Kepatuhan iuran | % anggota aktif lunas per periode | ≥ 80% | `dues_invoices` [USULAN] |
| G-09 | Penomoran surat bebas tabrakan | Nomor surat ganda | 0 | UNIQUE constraint + audit [USULAN] |
| G-10 | Keberlanjutan | Serah terima tanpa pengembang lama | Dokumentasi & runbook lengkap | Checklist serah terima |

## 4. Pemangku kepentingan

| Pemangku kepentingan | Kepentingan | Pengaruh | Keterlibatan |
|---|---|---|---|
| Ketua & Wakil Ketua | Keputusan, pengesahan surat, laporan | Tinggi | Menyetujui keputusan [§11 SKPL](SKPL.md#11-daftar-diskusi-dengan-pengurus) |
| Sekretaris | Persuratan & arsip | Tinggi (modul arsip) | Uji penerimaan modul arsip |
| Bendahara | Kas, iuran, LPJ | Tinggi (modul keuangan) | Uji penerimaan modul keuangan |
| Divisi PSDM | Rekrutmen, data anggota | Tinggi | Pengguna utama seleksi & anggota |
| Divisi Akademik Riset | Inventaris lab | Sedang | Pengguna utama inventaris |
| Divisi Humas Multimedia | Konten publik | Rendah | Konten laman publik |
| Anggota | Data diri, iuran, peminjaman | Sedang | Subjek data; calon pengguna portal anggota |
| Calon anggota | Pendaftaran | Rendah | Pengguna publik |
| Fakultas/Jurusan | Menerima surat & LPJ | Sedang | Penerima keluaran |
| Tim pengembang | Pemeliharaan | Tinggi (teknis) | Implementasi & dokumentasi |

## 5. Ruang lingkup

**Dalam lingkup**

- Portal publik & pendaftaran calon anggota; seleksi; direktori anggota & alumni; akses login pengurus; log audit — *sudah ada*.
- Inventaris & peminjaman alat lab; kas & keuangan (dua ledger, iuran, laporan); arsip & persuratan (surat masuk, surat keluar bernomor, template, persetujuan) — *prototipe → pengembangan*.
- Migrasi frontend ke React.

**Di luar lingkup (saat ini)**

- Akuntansi pajak, penggajian, integrasi perbankan langsung (kecuali payment gateway bila disetujui).
- Aplikasi seluler native; integrasi SIAKAD kampus.
- Tanda tangan elektronik tersertifikasi (hanya dibahas sebagai opsi).
- Multi-organisasi (multi-tenant).

## 6. Kebutuhan bisnis

| ID | Kebutuhan bisnis | Masalah | Tujuan | Prioritas | Status dominan | Ditelusuri ke |
|---|---|---|---|---|---|---|
| BR-01 | Organisasi harus menerima & menyeleksi calon anggota secara daring dengan periode, deadline, dan kuota yang dapat diatur | MB-01 | G-01, G-02 | Must | [ADA-BACKEND] | US-04, US-05 |
| BR-02 | Organisasi harus memiliki satu sumber data anggota & alumni yang dapat ditampilkan publik secara aman | MB-01 | G-03 | Must | [ADA-BACKEND] | US-03, US-06, US-08 |
| BR-03 | Akses panel pengurus harus per individu dan sesuai jabatan, tanpa kemungkinan menaikkan hak sendiri | MB-02 | G-04 | Must | [ADA-BACKEND] | US-01, US-02, US-21 |
| BR-04 | Pengelolaan data pribadi harus memenuhi UU PDP: persetujuan, minimasi, hak hapus/anonimisasi | MB-08 | G-04 | Must | [ADA-BACKEND] | US-04, US-07, US-10 |
| BR-05 | Setiap aksi penting harus dapat diaudit | MB-02 | G-04 | Must | [ADA-BACKEND] | US-09 |
| BR-06 | Pengurus harus dapat mengetahui stok alat lab dan siapa meminjam apa sampai kapan | MB-03 | G-05, G-06 | Must | [MVP-HTML] → [USULAN] | US-11, US-12, US-13 |
| BR-07 | Keuangan harus dicatat sekali dan menghasilkan buku kas, pemasukan-pengeluaran, rekap, dan laporan pertanggungjawaban | MB-04 | G-07 | Must | [MVP-HTML] → [USULAN] | US-14, US-15 |
| BR-08 | Iuran anggota harus dapat ditagih dan dipantau per anggota per periode | MB-05 | G-08 | Should | [USULAN] / [PERLU-DISKUSI] | US-16, US-17 |
| BR-09 | Surat keluar harus bernomor unik otomatis, berformat baku per jenis, disetujui sesuai kewenangan, dan diarsipkan bersama surat masuk | MB-06 | G-09 | Must | [MVP-HTML] → [USULAN] | US-18, US-19, US-20 |
| BR-10 | Sistem harus mudah dirawat dan diserahterimakan antar kepengurusan | MB-07 | G-10 | Should | [ADA-BACKEND] (test, docs) / [USULAN] (CI, React) | US-21, US-22 |

## 7. Manfaat

| Manfaat | Kebutuhan | Jenis |
|---|---|---|
| Waktu rekap pendaftar & anggota berkurang dari jam ke menit | BR-01, BR-02 | Efisiensi |
| Jejak audit melindungi pengurus dari tuduhan penyalahgunaan data | BR-03, BR-05 | Tata kelola |
| Kepatuhan UU PDP mengurangi risiko hukum | BR-04 | Kepatuhan |
| Alat lab lebih terjaga; tanggung jawab jelas | BR-06 | Aset |
| LPJ keuangan siap cetak, saldo dapat direkonsiliasi | BR-07 | Transparansi |
| Tunggakan iuran terlihat | BR-08 | Pendapatan |
| Surat resmi seragam, tanpa nomor ganda | BR-09 | Citra organisasi |
| Serah terima lebih cepat | BR-10 | Keberlanjutan |

## 8. Risiko, asumsi, dan batasan

**Risiko bisnis**

| ID | Risiko | Dampak | Mitigasi |
|---|---|---|---|
| RB-01 | Adopsi rendah (pengurus kembali ke spreadsheet) | Sumber data ganda | Pelatihan singkat, fitur ekspor, dukungan fase awal |
| RB-02 | Fitur terlalu kompleks untuk kebutuhan nyata | Waktu & biaya terbuang | Opsi minimal dulu; keputusan eksplisit (SKPL §11) |
| RB-03 | Biaya berulang (gateway, WA API) membebani kas | Defisit | Opsi A tanpa biaya; evaluasi setelah 1 periode |
| RB-04 | Kebocoran data pribadi | Hukum & reputasi | Kontrol keamanan (SECURITY_AUDIT), minimasi data |
| RB-05 | Pengembang utama lulus | Sistem terbengkalai | Dokumentasi, CI, standar kode |

**Asumsi:** lihat [SKPL §2.5](SKPL.md#25-asumsi-dan-ketergantungan) (AS-01 s.d. AS-08).
**Batasan:** anggaran minim, tim pengembang paruh waktu (mahasiswa), hosting sederhana, pergantian pengurus tahunan.

## 9. Analisis biaya-manfaat ringkas

| Komponen | Opsi minimal (rekomendasi fase 2) | Opsi penuh (fase 3) |
|---|---|---|
| Pengembangan (relatif) | ± 8–12 minggu developer paruh waktu (inventaris, keuangan Opsi A, surat keluar minimal, surat masuk) | + 6–10 minggu (QRIS, pengingat, approval penuh, QR verifikasi, portal anggota) |
| Biaya infrastruktur | Server/VPS yang ada; domain; backup ke penyimpanan gratis/murah | + biaya gateway per transaksi (estimasi ±0,7% + MDR QRIS — verifikasi ke penyedia), WA API per percakapan, kemungkinan biaya merchant |
| Manfaat terukur | G-05, G-07, G-09 tercapai; rekap & LPJ otomatis | + G-08 (pelunasan otomatis), beban Bendahara minimal |
| Risiko | Rendah–sedang | Sedang–tinggi (dana, keamanan, legalitas merchant) |
| Kesimpulan | **Nilai tertinggi per biaya** — kerjakan dulu | Lakukan bila data fase 2 menunjukkan tunggakan iuran signifikan |

## 10. Riwayat revisi

| Versi | Tanggal | Penulis | Perubahan |
|---|---|---|---|
| 1.0 | 2026-09-29 | Tim Pengembang (dibantu asisten AI) | Dokumen awal |
