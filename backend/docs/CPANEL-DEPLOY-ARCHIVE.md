# Deploy cPanel via arsip bertahap (menggantikan FTPS per-file)

> **Status verifikasi:** semua fakta di dokumen ini diukur langsung terhadap
> `https://jejaka500.followtheline.id` pada 2026-11-20, bukan disalin dari
> dokumen handover.

## Mengapa berubah

Metode lama mengunggah ±20.000 file satu per satu lewat FTPS. Uji nyata pada
`main` `d7deabd` (run `44729381769`) **dibatalkan setelah 1 jam 46 menit** pada
langkah "Deploy backend (FTPS -> /api)" tanpa selesai.

| Fakta terukur | Nilai |
|---|---|
| File backend yang harus diunggah | 20.032 |
| Di antaranya `vendor/` | 19.429 file (144 MB) |
| Round-trip FTPS per file | ±2 request/file |
| Throughput HTTPS terukur | ±0,7–1,5 MiB/s |

Kesimpulan: masalahnya bukan kredensial, tapi **jumlah round-trip**. Satu arsip
backend ±42,6 MiB cukup dikirim dalam belasan potongan kecil.

## Tata letak server yang sebenarnya

Ini bagian yang **salah di dokumen handover lama** dan menyebabkan deploy
menulis ke tempat yang tidak dilayani.

```
/home/permatat/followtheline.id/jejaka500/     ← DOCROOT web (SPA)
├── .htaccess            ← routing SPA + rewrite /api → api/public/index.php
├── index.html, assets/, fonts/, icons/, sw.js
├── storage -> api/public/storage
└── api/                 ← app root Laravel
    ├── .env             ← DI DALAM docroot (dilindungi aturan, bukan arsitektur)
    ├── app/, vendor/, artisan, routes/, storage/
    └── public/          ← direktorat biasa, BUKAN docroot
        ├── index.php, .htaccess, build/, css/, js/, fonts/
        └── storage -> ...../api/storage/app/public
```

Bukti yang membedakan keduanya:

| Probe | Hasil | Arti |
|---|---|---|
| `GET /api/public/robots.txt` | **200** (berkas asli, ada `last-modified`) | `api/public/` adalah direktori biasa di dalam docroot |
| `GET /api/public/deploy-extract.php` | **405** | PHP **dieksekusi langsung** di `api/public/`, melewati Laravel |
| `GET /api/deploy-extract.php` | **404** | dikirim ke `api/public/index.php`, bukan dibaca sebagai file |
| `GET /api/artisan` | 404 | kode di `api/` tidak diekspos sebagai file |
| `GET /api/.env` | 403 | dilindungi aturan direktori |
| `GET /css/filament/filament/app.css` | 200 `text/css` | aset top-level sudah dilayani benar — jangan diubah |

**Konsekuensi yang harus dipahami:** karena `api/public/` dapat dipanggil
langsung lewat web, setiap berkas `.php` di sana adalah endpoint publik. Karena
itu handler asli **dipindahkan ke `storage/cpanel-deploy/`** — di luar docroot,
sehingga request web tidak bisa menjangkaunya sama sekali. Tanda tangan HMAC
tetap dipertahankan sebagai lapisan kedua.

## Cara kerja sekarang

```
push main → CI sukses → Deploy (cPanel)
  1. build backend + frontend
  2. build_archive.py → ZIP (±43 MiB) → potong 1,5 MiB
  3. upload_chunks.py → POST /api/cpanel-deploy.php per potongan
  4. server (api/cpanel-deploy.php): gabung → verifikasi SHA-256 → ekstrak
  5. smoke test HTTP
```

`api/cpanel-deploy.php` adalah **shim** di docroot yang hanya memuat handler
asli dari luar docroot. Endpoint publiknya:

```
https://jejaka500.followtheline.id/api/public/cpanel-deploy.php
```

> **Catatan penting:** URL ini sengaja berada di `api/public/`, direktori yang
> dieksekusi langsung. Mitigasinya tiga lapis: (1) handler asli di luar docroot,
> (2) HMAC dengan jendela 600 detik + nonce sekali pakai, (3) `GET` ditolak 405.
> `.htaccess` root menambahkan `[F]` untuk helper deploy lama (`deploy-*`) dan
> meloloskan shim baru, tanpa menyentuh routing yang sudah bekerja.

## Pemetaan ulang artefak

| Isi arsip | Mendarat di | Alasan |
|---|---|---|
| `public/*` | `/api/` | Inilah yang **dilayani** — `api/index.php` adalah front controller efektif menurut `.htaccess` root |
| selain `public/` | `/api/` | app root Laravel |

**Keduanya mendarat di `/api/`** karena `.htaccess` root hanya melayani
`api/public/index.php`. Menaruh `index.php` di `api/` **bukan** tabrakan dengan
`api/public/index.php` (berkas berbeda), dan `public/index.php` tetap
diperbarui sebagai berkas biasa untuk konsistensi bila `AllowOverride` berubah.

`.env`, `storage/`, `bootstrap/cache/config.php`, dan `php.ini`/`.user.ini`
tidak pernah ditimpa.

## Ukuran potongan

`upload_max_filesize` terukur **2M** (LiteSpeed mengabaikan `.user.ini`).
Potongan default karenanya **1,5 MiB**, menyisakan ±0,5 MiB untuk overhead
multipart dan header. Naikkan ke 4 MiB hanya setelah `upload_max_filesize`
benar-benar ≥ 8M (lihat "Menaikkan batas upload").

## Instalasi awal (sekali saja, manual)

Semua langkah di bawah dijalankan dari **Terminal cPanel**, bukan dari web.

### 1. Pasang handler + lib di luar docroot

Dua berkas wajib ada di folder yang sama: `cpanel-deploy-handler.php` dan
`deploy-lib.php`.

```bash
mkdir -p ~/followtheline.id/jejaka500/api/storage/cpanel-deploy
# unggah kedua berkas ke folder itu (scp / File Manager)
ls -la ~/followtheline.id/jejaka500/api/storage/cpanel-deploy/
```

Harapan: terlihat `cpanel-deploy-handler.php` **dan** `deploy-lib.php`.

### 2. Buat secret HMAC

```bash
php ~/followtheline.id/jejaka500/api/storage/cpanel-deploy/cpanel-deploy-handler.php --generate-secret
```

Perintah mencetak 64 hex **sekali**. Simpan sebagai secret GitHub
`CPANEL_DEPLOY_SECRET`. Nilai yang sama ditulis ke
`storage/cpanel-deploy/deploy-secret.txt` (0600, di luar docroot).

Menjalankan ulang perintah itu menolak merotasi bila secret sudah ada. Untuk
rotasi yang disengaja: hapus berkasnya lebih dulu.

### 3. Pasang shim di docroot

```bash
cp cpanel-deploy.php ~/followtheline.id/jejaka500/api/public/cpanel-deploy.php
```

Shim aslinya (`backend/deploy-cpanel/cpanel-deploy.php`) lebih lengkap: ia
memeriksa keberadaan handler dan mengembalikan `503` (bukan fatal error) bila
handler belum terpasang. Intinya tetap satu baris:

```php
<?php
require __DIR__.'/../storage/cpanel-deploy/cpanel-deploy-handler.php';
```

### 4. Verifikasi

```bash
curl -s -o /dev/null -w 'GET  -> %{http_code}\n' \
  https://jejaka500.followtheline.id/api/public/cpanel-deploy.php   # harap 405
curl -s -o /dev/null -w 'POST -> %{http_code}\n' -X POST \
  https://jejaka500.followtheline.id/api/public/cpanel-deploy.php   # harap 403
```

`405` + `403` berarti endpoint hidup dan menolak tanpa tanda tangan. Setelah itu
baru isi di GitHub:

- Secrets → `CPANEL_DEPLOY_SECRET` = keluaran langkah 2
- Variables → `CPANEL_DEPLOY_READY` = `true`

### 5. (Opsional tapi disarankan) Kunci helper lama di `.htaccess` root

`api/public/deploy-extract.php` lama masih bisa dieksekusi lewat web bila
filenya tertinggal. Tambahkan aturan penolakan ke `.htaccess` root:

```bash
cp ~/followtheline.id/jejaka500/.htaccess ~/followtheline.id/jejaka500/.htaccess.bak.$(date +%Y%m%d-%H%M%S)
```

Lalu **di dalam blok `<IfModule mod_rewrite.c>`, paling atas setelah
`RewriteBase /`**, tambahkan:

```apache
    RewriteRule ^api/(public/)?deploy- [F,L]
    RewriteRule ^api/(public/)?(cpanel-deploy|phpcheck)\.php$ [F,L]
    RewriteRule ^api/(\.env(\..*)?|composer\.(json|lock)|artisan)$ [F,L]
```

Verifikasi **segera** setelah menyimpan (jangan ditinggal):

```bash
for p in / /up /api/price-categories /admin/login; do
  printf '%-24s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' https://jejaka500.followtheline.id$p)"
done
curl -s -o /dev/null -w 'deploy-extract %{http_code} (harap 403)\n' \
  https://jejaka500.followtheline.id/api/public/deploy-extract.php
```

Harapan: `/`, `/up`, `/api/price-categories`, `/admin/login` tetap `200`, dan
`deploy-extract` menjadi `403`. **Bila ada yang bukan 200, kembalikan segera:**

```bash
cp ~/followtheline.id/jejaka500/.htaccess.bak.* ~/followtheline.id/jejaka500/.htaccess
```

Versi acuan lengkap ada di `deploy/cpanel/htaccess-root.txt`. Aturan ini
diuji oleh `.github/scripts/test_htaccess_simulation.py` terhadap rute nyata,
tetapi **simulasi tidak menggantikan verifikasi di server** — selalu jalankan
probe di atas.

## Menaikkan batas upload (opsional)

Hanya bila ingin potongan lebih besar. cPanel → **MultiPHP INI Editor** →
domain `jejaka500.followtheline.id`:

```
upload_max_filesize = 8M
post_max_size       = 16M
```

Verifikasi lewat **web**, bukan `php -i` (CLI selalu memakai `php.ini` sendiri):

```bash
cat > ~/followtheline.id/jejaka500/api/public/phpcheck.php <<'EOF'
<?php echo ini_get('upload_max_filesize'), ' / ', ini_get('post_max_size'), ' / ', php_sapi_name(), "\n";
EOF
curl -s https://jejaka500.followtheline.id/api/public/phpcheck.php
rm -f ~/followtheline.id/jejaka500/api/public/phpcheck.php
```

## Penyelesaian masalah

| Gejala | Arti | Tindakan |
|---|---|---|
| `405 POST required` | endpoint hidup, request GET | normal untuk probe |
| `403 Forbidden` | tanda tangan ditolak | lihat `[cpanel-deploy] auth ditolak: …` di error log PHP |
| `413` pada potongan | potongan melebihi `upload_max_filesize` | turunkan potongan atau naikkan batas |
| `422 Unsafe archive entry` | entri arsip berbahaya | arsip salah rakitan — jangan diteruskan |
| `422 Archive checksum mismatch` | potongan tidak utuh | ulangi deploy; periksa batas ukuran |
| `500` di endpoint | handler fatal | cek `error_log` di `~/logs/php.error.log` |
