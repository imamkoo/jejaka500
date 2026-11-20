# Deploy cPanel via arsip bertahap (menggantikan FTPS per-file)

## Mengapa berubah

Metode lama mengunggah ±20.000 file satu per satu lewat FTPS. Uji nyata pada
`main` `d7deabd` (run `44729381769`) **dibatalkan setelah 1 jam 46 menit** pada
langkah "Deploy backend (FTPS -> /api)" tanpa selesai.

Pengukuran penyebab:

| Fakta terukur | Nilai |
|---|---|
| File backend yang harus diunggah | 20.032 |
| Di antaranya `vendor/` | 19.429 file (144 MB) |
| Round-trip FTPS per file (perintah + ukuran) | ±2 request/file |
| Body request yang ditolak server | lebih dari ±8 MiB (`413`) |
| Throughput HTTPS terukur | ±0,7–1,5 MiB/s |

Kesimpulan: masalahnya bukan kredensial atau jaringan lambat, tapi **jumlah
round-trip**. Satu arsip backend ±42,6 MiB cukup dikirim dalam 11 potongan.

## Cara kerja sekarang

```
push main → CI sukses → Deploy (cPanel)
  1. build backend + frontend (seperti sebelumnya)
  2. build_archive.py → arsip ZIP  (±43 MiB, 20.007 file) → potong 4 MiB
  3. upload_chunks.py → POST /api/deploy-extract.php per potongan
  4. server: gabung potongan → verifikasi SHA-256 → ekstrak
  5. smoke test HTTP
```

Pemetaan tujuan mengikuti `rsync backend/ → /api`, di mana `/api` adalah app
root Laravel dan `/api/public` adalah docroot yang dilayani web:

| Isi arsip | Mendarat di |
|---|---|
| `public/*` | `/api/public/` (docroot — `index.php`, `.htaccess`, `build/`, `css/`, `js/`) |
| selain `public/` | `/api/` (app root — `app/`, `vendor/`, `artisan`, `routes/`) |

Pemetaan ini dijaga tes perilaku yang mengeksekusi fungsi PHP aslinya
(`.github/scripts/test_deploy_extract_php.py`), karena kesalahan di sini bisa
menimpa front controller SPA.

Yang **tidak pernah** ditimpa arsip: `.env`, `storage/`, `bootstrap/cache/config.php`,
dan helper deploy sendiri.

## Persiapan sekali di server

### 1. Siapkan direktori staging

Lewat **Terminal** cPanel:

```bash
mkdir -p ~/followtheline.id/jejaka500/storage/framework
chmod 755 ~/followtheline.id/jejaka500/storage/framework
```

### 2. Unggah dua helper deploy

Ambil dari repo pada commit yang sedang live (folder `backend/public/`):

- `deploy-extract.php`
- `deploy-secret.php`

Letakkan di `~/followtheline.id/jejaka500/api/`. Karena file ini di-track git,
deploy berikutnya akan memperbaruinya otomatis.

### 3. Buat secret deploy (sekali saja)

```bash
php ~/followtheline.id/jejaka500/api/public/deploy-secret.php
```

Perintah mencetak satu baris secret 64 karakter heksadesimal dan menyimpannya di
`storage/framework/deploy-secret.txt` (di luar docroot, tidak bisa diakses web).

Simpan output itu sebagai **secret** `CPANEL_DEPLOY_SECRET` di
`Settings → Secrets and variables → Actions`.

### 3b. Aktifkan deploy

Isi **variable** `CPANEL_DEPLOY_READY` = `true`. Sebelum ini diisi, job deploy
di-skip (bukan gagal), jadi push ke `main` tidak memunculkan CI merah.

### 4. Pastikan batas upload PHP cukup

`backend/public/.user.ini` berisi `upload_max_filesize = 8M`. File ini ikut
ter-deploy. Untuk cPanel dengan PHP-FPM, `.user.ini` berlaku otomatis. Bila
akun memakai mod_php/LiteSpeed yang mengabaikannya, setel lewat
**MultiPHP INI Editor** untuk domain ini:

```
upload_max_filesize = 8M
post_max_size = 10M
```

Verifikasi:

```bash
php -i | grep -E 'upload_max_filesize|post_max_size'
```

### 5. Cek ekstensi PHP `zip`

```bash
php -r 'var_dump(class_exists("ZipArchive"));'
```

Harus `true`. Bila `false`, aktifkan ekstensi `zip` di **Select PHP Version →
Extensions**.

## Autentikasi: tanda tangan HMAC

Setiap request membawa tiga header:

| Header | Isi |
|---|---|
| `X-Deploy-Timestamp` | detik Unix saat request dibuat |
| `X-Deploy-Nonce` | 16 byte acak, sekali pakai |
| `X-Deploy-Signature` | `hex(hmac_sha256(secret, "timestamp:nonce:archive_sha256"))` |

Server memeriksa dengan urutan:

1. Secret ada dan tidak kosong → selain itu `403`.
2. Timestamp berupa angka dan berada dalam **±600 detik** dari jam server.
3. Tanda tangan cocok (`hash_equals`, constant-time).
4. Nonce belum pernah dipakai — penanda disimpan di
   `storage/framework/deploy-nonces/`, dibersihkan otomatis setelah 2× jendela.

**Secret tidak pernah dikirim lewat jaringan.** Yang melintas hanya tanda
tangganya, yang tidak berguna tanpa secret.

### Kenapa tidak lagi butuh langkah manual

Secret dibuat **sekali**. Setiap deploy berikutnya ditandatangani otomatis oleh
workflow, jadi tidak ada lagi "buat token baru tiap deploy".

### Yang tetap membatasi kerusakan

- Tanda tangan hanya berlaku dalam jendela 10 menit.
- Nonce mencegah replay di dalam jendela itu.
- Tanda tangan terikat ke hash arsip, jadi isi tidak bisa diganti di tengah jalan.
- Kalau secret bocor: jalankan ulang `deploy-secret.php` (setelah menghapus
  `storage/framework/deploy-secret.txt`) untuk rotasi, lalu perbarui secret
  GitHub. Server langsung menolak tanda tangan lama.

## Deploy manual

```bash
gh workflow run deploy-cpanel.yml -R imamkoo/jejaka500 --ref main
```

## Cara membaca hasil

| Gejala | Arti |
|---|---|
| Preflight gagal di awal run | secret `CPANEL_DEPLOY_SECRET` belum diisi sama sekali |
| Job deploy `skipped` | variable `CPANEL_DEPLOY_READY` belum `true` — langkah 3b |
| `403 Forbidden` dari endpoint | lihat `[deploy-extract] auth ditolak: …` di error log PHP (alasannya spesifik) |
| `403` dengan alasan `expired` | selisih jam server > 10 menit, atau run diulang dari run lama |
| `403` dengan alasan `replayed nonce` | request yang sama dikirim dua kali; jalankan ulang deploy |
| `403` dengan alasan `bad signature` | secret GitHub ≠ `storage/framework/deploy-secret.txt` |
| `413` pada potongan | `upload_max_filesize`/`post_max_size` masih kecil — langkah 4 |
| `422 Archive checksum mismatch` | potongan rusak saat transit; jalankan ulang deploy |
| `500 Cannot create directory` | izin direktori di app root; periksa owner lewat Terminal |
| Smoke test gagal setelah ekstrak sukses | mapping direktori atau routing, bukan kredensial |

Verifikasi pasca-deploy yang dipakai workflow:

```
/                        200
/up                      200
/api/price-categories    200
/admin/login             200
```

## Masih manual (tidak dijalankan workflow)

Sesuai runbook `CPANEL-DEPLOY.md` §6: migrasi database, `php artisan` (cache,
optimize), dan perubahan `.env` tetap dikerjakan manual lewat Terminal.

## Kalau perlu kembali ke FTPS

`ftps_deploy.py` dan tesnya **masih ada** dan tetap diuji di CI, tetapi tidak
lagi dipanggil workflow. Untuk sementara kembali, ganti empat langkah
"Package/Deploy" di `.github/workflows/deploy-cpanel.yml` dengan pemanggilan
`ftps_deploy.py` seperti sebelumnya. Perlu diketahui: cara itu sudah terbukti
tidak selesai dalam 1 jam 46 menit untuk backend.
