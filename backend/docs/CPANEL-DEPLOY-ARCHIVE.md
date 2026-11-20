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
- `deploy-token.php`

Letakkan di `~/followtheline.id/jejaka500/api/`. Karena file ini di-track git,
deploy berikutnya akan memperbaruinya otomatis.

### 3. Buat token deploy

```bash
php ~/followtheline.id/jejaka500/api/public/deploy-token.php
```

Perintah mencetak satu baris token 64 karakter heksadesimal dan menyimpannya di
`storage/framework/deploy-token.txt` (di luar docroot, tidak bisa diakses web).

Simpan output itu sebagai **secret** `CPANEL_DEPLOY_TOKEN` di
`Settings → Secrets and variables → Actions`.

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

## Token sekali pakai — penting

Token **habis setelah satu deploy sukses**. Deploy berikutnya akan gagal di
preflight dengan pesan 403 dari server. Jadi setiap kali mau deploy:

```bash
php ~/followtheline.id/jejaka500/api/public/deploy-token.php
```

lalu perbarui secret `CPANEL_DEPLOY_TOKEN`.

Ini memang disengaja: kalau token bocor, penyerang hanya bisa memakai sisa satu
deploy, dan itupun harus melewati validasi arsip. Otomatisasi pembuatan token
per-run adalah pekerjaan lanjutan (butuh pemanggilan dari server, bukan dari
GitHub).

## Deploy manual

```bash
gh workflow run deploy-cpanel.yml -R imamkoo/jejaka500 --ref main
```

## Cara membaca hasil

| Gejala | Arti |
|---|---|
| Preflight gagal di awal run | secret `CPANEL_DEPLOY_TOKEN` belum diisi sama sekali |
| `403 Forbidden` dari endpoint | token belum dibuat di server, atau sudah terpakai — ulangi langkah 3 |
| `413` pada potongan | `upload_max_filesize`/`post_max_size` masih kecil — langkah 4 |
| `422 Archive checksum mismatch` | potongan rusak saat transit; ulangi run (token belum terpakai) |
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
